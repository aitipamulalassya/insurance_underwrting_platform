from datetime import datetime
from decimal import Decimal

from psycopg.types.json import Jsonb

from api.database import get_connection


def generate_payment_id(cur):
    cur.execute(
        """
        SELECT COALESCE(
            MAX(
                substring(
                    payment_id
                    FROM '^PAY-[0-9]{4}-([0-9]+)$'
                )::BIGINT
            ),
            0
        ) + 1 AS next_id
        FROM payments
        WHERE payment_id ~ '^PAY-[0-9]{4}-[0-9]+$'
        """
    )

    next_id = cur.fetchone()["next_id"]
    return f"PAY-{datetime.now().year}-{next_id:06d}"

def record_payment(
    quote_id: str,
    amount: Decimal,
    payment_reference: str | None = None
):
    with get_connection() as conn:
        with conn.cursor() as cur:

        # Use the same lock as ordinary payment creation.
            cur.execute(
            "SELECT pg_advisory_xact_lock(20261032)"
        )

            # Serialize payment creation for this workflow.
           

            # Lock and validate the quote.
            cur.execute(
                """
                SELECT
                    quote_id,
                    quote_status,
                    calculated_premium,
                    currency
                FROM quotes
                WHERE quote_id = %s
                FOR UPDATE
                """,
                (quote_id,)
            )

            quote = cur.fetchone()

            if not quote:
                raise ValueError("Quote not found.")

            if quote["quote_status"] != "ACCEPTED":
                raise ValueError(
                    "Payment can only be recorded for an ACCEPTED quote. "
                    f"Current status: {quote['quote_status']}"
                )

            expected_amount = Decimal(str(quote["calculated_premium"]))

            if amount != expected_amount:
                raise ValueError(
                    f"Payment amount must match the calculated premium "
                    f"of {expected_amount}."
                )

            # Prevent another pending or confirmed payment for this quote.
            cur.execute(
                """
                SELECT payment_id, payment_status
                FROM payments
                WHERE quote_id = %s
                  AND payment_status IN ('PENDING', 'CONFIRMED')
                LIMIT 1
                """,
                (quote_id,)
            )

            existing_payment = cur.fetchone()

            if existing_payment:
                raise ValueError(
                    "An active payment already exists for this quote: "
                    f"{existing_payment['payment_id']} "
                    f"({existing_payment['payment_status']})."
                )

            payment_id = generate_payment_id(cur)

            cur.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    quote_id,
                    amount,
                    currency,
                    payment_status,
                    payment_reference
                )
                VALUES (%s, %s, %s, %s, 'PENDING', %s)
                RETURNING recorded_at
                """,
                (
                    payment_id,
                    quote_id,
                    amount,
                    quote["currency"],
                    payment_reference
                )
            )

            payment = cur.fetchone()

            return {
                "message": "Payment recorded successfully. Verification is pending.",
                "payment_id": payment_id,
                "quote_id": quote_id,
                "amount": float(amount),
                "currency": quote["currency"],
                "payment_status": "PENDING",
                "recorded_at": payment["recorded_at"]
            }


def confirm_payment(payment_id: str, verifier_reference: str):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT pg_advisory_xact_lock(20261033)"
            )

            cur.execute(
                """
                SELECT
                    payment_id,
                    quote_id,
                    policy_id,
                    endorsement_id,
                    amount,
                    currency,
                    payment_status,
                    payment_reference
                FROM payments
                WHERE payment_id = %s
                FOR UPDATE
                """,
                (payment_id,)
            )

            payment = cur.fetchone()

            if not payment:
                raise ValueError("Payment not found.")

            if payment["payment_status"] != "PENDING":
                raise ValueError(
                    "Only PENDING payments can be confirmed. "
                    f"Current status: {payment['payment_status']}"
                )

            # Endorsement payment validation.
            if payment["endorsement_id"] is not None:

                cur.execute(
                    """
                    SELECT
                        endorsement_id,
                        policy_id,
                        additional_premium,
                        endorsement_status,
                        activated_at
                    FROM endorsements
                    WHERE endorsement_id = %s
                    FOR UPDATE
                    """,
                    (payment["endorsement_id"],)
                )

                endorsement = cur.fetchone()

                if not endorsement:
                    raise ValueError(
                        "Associated endorsement not found."
                    )

                if endorsement["endorsement_status"] != "APPROVED":
                    raise ValueError(
                        "Endorsement must be approved before payment."
                    )

                if endorsement["activated_at"] is not None:
                    raise ValueError(
                        "Endorsement is already activated."
                    )

                if payment["amount"] != endorsement["additional_premium"]:
                    raise ValueError(
                        "Payment amount does not match endorsement premium."
                    )

            cur.execute(
                """
                UPDATE payments
                SET
                    payment_status = 'CONFIRMED',
                    confirmed_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s
                RETURNING confirmed_at
                """,
                (payment_id,)
            )

            confirmed = cur.fetchone()

            if payment["endorsement_id"] is not None:

                event_details = {
                    "payment_id": payment_id,
                    "endorsement_id": payment["endorsement_id"],
                    "amount": str(payment["amount"]),
                    "currency": payment["currency"],
                    "payment_reference": payment["payment_reference"],
                    "verified_by": verifier_reference
                }

                cur.execute(
                    """
                    INSERT INTO policy_events (
                        policy_id,
                        event_type,
                        previous_status,
                        new_status,
                        actor_reference,
                        event_reason,
                        event_details
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING policy_event_id
                    """,
                    (
                        endorsement["policy_id"],
                        "ENDORSEMENT_PAYMENT_CONFIRMED",
                        "ACTIVE",
                        "ACTIVE",
                        verifier_reference,
                        "Additional endorsement premium confirmed.",
                        Jsonb(event_details)
                    )
                )

                event = cur.fetchone()

                return {
                    "message": "Endorsement payment confirmed successfully",
                    "payment_id": payment_id,
                    "endorsement_id": payment["endorsement_id"],
                    "payment_status": "CONFIRMED",
                    "confirmed_at": confirmed["confirmed_at"],
                    "policy_event_id": event["policy_event_id"]
                }

            # Existing ordinary quote payment workflow.
            event_details = {
                "payment_id": payment_id,
                "amount": str(payment["amount"]),
                "currency": payment["currency"],
                "payment_reference": payment["payment_reference"],
                "verified_by": verifier_reference,
                "verification_status": "CONFIRMED"
            }

            cur.execute(
                """
                INSERT INTO quote_events (
                    quote_id,
                    event_type,
                    previous_status,
                    new_status,
                    actor_reference,
                    event_reason,
                    event_details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING quote_event_id
                """,
                (
                    payment["quote_id"],
                    "PAYMENT_CONFIRMED",
                    "ACCEPTED",
                    "ACCEPTED",
                    verifier_reference,
                    "Payment verified and confirmed.",
                    Jsonb(event_details)
                )
            )

            event = cur.fetchone()

            return {
                "message": "Payment confirmed successfully",
                "payment_id": payment_id,
                "quote_id": payment["quote_id"],
                "payment_status": "CONFIRMED",
                "confirmed_at": confirmed["confirmed_at"],
                "quote_event_id": event["quote_event_id"]
            }
        
def record_endorsement_payment(
    endorsement_id: str,
    payment_reference: str | None = None
):
    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT pg_advisory_xact_lock(20261036)"
            )

            cur.execute(
                """
                SELECT
                    e.endorsement_id,
                    e.policy_id,
                    e.additional_premium,
                    e.endorsement_status,
                    e.activated_at,
                    p.quote_id,
                    p.currency
                FROM endorsements e
                JOIN policies p
                    ON p.policy_id = e.policy_id
                WHERE e.endorsement_id = %s
                FOR UPDATE OF e
                """,
                (endorsement_id,)
            )

            endorsement = cur.fetchone()

            if not endorsement:
                raise ValueError("Endorsement not found.")

            if endorsement["endorsement_status"] != "APPROVED":
                raise ValueError(
                    "Only approved endorsements can receive payment."
                )

            if endorsement["activated_at"] is not None:
                raise ValueError(
                    "This endorsement has already been activated."
                )

            amount = Decimal(str(endorsement["additional_premium"]))

            if amount <= 0:
                raise ValueError(
                    "This endorsement does not require additional payment."
                )

            cur.execute(
                """
                SELECT payment_id, payment_status
                FROM payments
                WHERE endorsement_id = %s
                """,
                (endorsement_id,)
            )

            existing = cur.fetchone()

            if existing:
                raise ValueError(
                    "A payment already exists for this endorsement: "
                    f"{existing['payment_id']} "
                    f"({existing['payment_status']})."
                )

            payment_id = generate_payment_id(cur)

            cur.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    quote_id,
                    amount,
                    currency,
                    payment_status,
                    payment_reference,
                    endorsement_id
                )
                VALUES (%s, %s, %s, %s, 'PENDING', %s, %s)
                RETURNING recorded_at
                """,
                (
                    payment_id,
                    endorsement["quote_id"],
                    amount,
                    endorsement["currency"],
                    payment_reference,
                    endorsement_id
                )
            )

            payment = cur.fetchone()

            return {
                "message": "Endorsement payment recorded successfully",
                "payment_id": payment_id,
                "endorsement_id": endorsement_id,
                "policy_id": endorsement["policy_id"],
                "amount": float(amount),
                "currency": endorsement["currency"],
                "payment_status": "PENDING",
                "recorded_at": payment["recorded_at"]
            }