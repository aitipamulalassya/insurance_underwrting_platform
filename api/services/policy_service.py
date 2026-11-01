
from datetime import datetime

from psycopg.types.json import Jsonb

from api.database import get_connection


def generate_policy_id(cur):
    """Generate a unique policy ID without modifying existing records."""

    cur.execute(
        """
        SELECT COALESCE(
            MAX(
                substring(
                    policy_id
                    FROM '^POL-[0-9]{4}-([0-9]+)$'
                )::BIGINT
            ),
            0
        ) + 1 AS next_id
        FROM policies
        WHERE policy_id ~ '^POL-[0-9]{4}-[0-9]+$'
        """
    )

    next_id = cur.fetchone()["next_id"]
    year = datetime.now().year

    return f"POL-{year}-{next_id:06d}"


def issue_policy(quote_id: str, issued_by: str):

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Serialize policy issuance operations.
            cur.execute(
                "SELECT pg_advisory_xact_lock(20261034)"
            )

            # --------------------------------------------------
            # 1. Lock and retrieve the quote.
            # --------------------------------------------------

            cur.execute(
                """
                SELECT
                    quote_id,
                    renewal_id,
                    applicant_id,
                    asset_id,
                    product_id,
                    requested_start_date,
                    requested_end_date,
                    calculated_premium,
                    currency,
                    quote_status,
                    applicant_accepted_at
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
                    "Only ACCEPTED quotes can be issued as policies. "
                    f"Current status: {quote['quote_status']}"
                )

            if quote["applicant_accepted_at"] is None:
                raise ValueError(
                    "Customer acceptance timestamp is missing."
                )

            # --------------------------------------------------
            # 2. Validate associated renewal, if applicable.
            # --------------------------------------------------

            renewal = None

            if quote["renewal_id"] is not None:

                cur.execute(
                    """
                    SELECT
                        renewal_id,
                        policy_id,
                        renewal_status,
                        proposed_start_date,
                        proposed_end_date,
                        renewed_policy_id
                    FROM renewals
                    WHERE renewal_id = %s
                    FOR UPDATE
                    """,
                    (quote["renewal_id"],)
                )

                renewal = cur.fetchone()

                if not renewal:
                    raise ValueError(
                        "Associated renewal record not found."
                    )

                if renewal["renewal_status"] != "ACCEPTED":
                    raise ValueError(
                        "Renewal must be ACCEPTED before policy issuance."
                    )

                if renewal["renewed_policy_id"] is not None:
                    raise ValueError(
                        "A renewed policy has already been issued: "
                        f"{renewal['renewed_policy_id']}"
                    )

                if (
                    quote["requested_start_date"]
                    != renewal["proposed_start_date"]
                ):
                    raise ValueError(
                        "Renewal quote start date does not match "
                        "the accepted renewal offer."
                    )

                if (
                    quote["requested_end_date"]
                    != renewal["proposed_end_date"]
                ):
                    raise ValueError(
                        "Renewal quote end date does not match "
                        "the accepted renewal offer."
                    )

                # Verify the original policy still exists.
                cur.execute(
                    """
                    SELECT policy_id, policy_status
                    FROM policies
                    WHERE policy_id = %s
                    FOR UPDATE
                    """,
                    (renewal["policy_id"],)
                )

                original_policy = cur.fetchone()

                if not original_policy:
                    raise ValueError(
                        "Original policy associated with renewal "
                        "could not be found."
                    )

                if original_policy["policy_status"] != "ACTIVE":
                    raise ValueError(
                        "Original policy must be ACTIVE to issue "
                        "its renewal."
                    )

            # --------------------------------------------------
            # 3. Prevent duplicate policy issuance.
            # --------------------------------------------------

            cur.execute(
                """
                SELECT policy_id
                FROM policies
                WHERE quote_id = %s
                """,
                (quote_id,)
            )

            existing_policy = cur.fetchone()

            if existing_policy:
                raise ValueError(
                    "A policy has already been issued for this quote: "
                    f"{existing_policy['policy_id']}"
                )

            # --------------------------------------------------
            # 4. Lock and verify the confirmed payment.
            # --------------------------------------------------

            if renewal is not None:

                cur.execute(
                    """
                    SELECT
                        payment_id,
                        amount,
                        currency,
                        payment_status,
                        confirmed_at
                    FROM payments
                    WHERE quote_id = %s
                      AND renewal_id = %s
                      AND endorsement_id IS NULL
                      AND payment_status = 'CONFIRMED'
                      AND policy_id IS NULL
                    FOR UPDATE
                    """,
                    (
                        quote_id,
                        renewal["renewal_id"]
                    )
                )

            else:

                cur.execute(
                    """
                    SELECT
                        payment_id,
                        amount,
                        currency,
                        payment_status,
                        confirmed_at
                    FROM payments
                    WHERE quote_id = %s
                      AND renewal_id IS NULL
                      AND endorsement_id IS NULL
                      AND payment_status = 'CONFIRMED'
                      AND policy_id IS NULL
                    FOR UPDATE
                    """,
                    (quote_id,)
                )

            payments = cur.fetchall()

            if not payments:
                raise ValueError(
                    "Cannot issue policy. No eligible confirmed "
                    "payment exists."
                )

            if len(payments) > 1:
                raise ValueError(
                    "Multiple confirmed payments exist for this quote. "
                    "Manual reconciliation is required."
                )

            payment = payments[0]

            if payment["confirmed_at"] is None:
                raise ValueError(
                    "Payment confirmation timestamp is missing."
                )

            if payment["currency"] != quote["currency"]:
                raise ValueError(
                    "Payment currency does not match quote currency."
                )

            if payment["amount"] != quote["calculated_premium"]:
                raise ValueError(
                    "Confirmed payment amount does not match "
                    "the calculated quote premium."
                )

            # --------------------------------------------------
            # 5. Generate new policy identifier.
            # --------------------------------------------------

            policy_id = generate_policy_id(cur)

            # --------------------------------------------------
            # 6. Create the new policy.
            # --------------------------------------------------

            cur.execute(
                """
                INSERT INTO policies (
                    policy_id,
                    quote_id,
                    applicant_id,
                    asset_id,
                    product_id,
                    policy_start_date,
                    policy_end_date,
                    policy_status,
                    accepted_at,
                    payment_confirmed_at,
                    premium_amount,
                    currency
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                RETURNING issued_at
                """,
                (
                    policy_id,
                    quote["quote_id"],
                    quote["applicant_id"],
                    quote["asset_id"],
                    quote["product_id"],
                    quote["requested_start_date"],
                    quote["requested_end_date"],
                    "ACTIVE",
                    quote["applicant_accepted_at"],
                    payment["confirmed_at"],
                    quote["calculated_premium"],
                    quote["currency"]
                )
            )

            policy = cur.fetchone()

            # --------------------------------------------------
            # 7. Link confirmed payment to new policy.
            # --------------------------------------------------

            cur.execute(
                """
                UPDATE payments
                SET policy_id = %s
                WHERE payment_id = %s
                  AND policy_id IS NULL
                """,
                (
                    policy_id,
                    payment["payment_id"]
                )
            )

            if cur.rowcount != 1:
                raise ValueError(
                    "Payment could not be linked to the policy. "
                    "It may already be associated with another policy."
                )

            # --------------------------------------------------
            # 8. Prepare audit event.
            # --------------------------------------------------

            is_renewal = renewal is not None

            event_type = (
                "POLICY_RENEWED"
                if is_renewal
                else "POLICY_ISSUED"
            )

            event_reason = (
                "Renewed policy issued after renewal acceptance "
                "and confirmed payment."
                if is_renewal
                else "Policy issued after customer acceptance "
                     "and confirmed payment."
            )

            event_details = {
                "quote_id": quote_id,
                "payment_id": payment["payment_id"],
                "renewal_id": (
                    renewal["renewal_id"]
                    if is_renewal
                    else None
                ),
                "original_policy_id": (
                    renewal["policy_id"]
                    if is_renewal
                    else None
                ),
                "premium_amount": str(
                    quote["calculated_premium"]
                ),
                "currency": quote["currency"],
                "policy_start_date": (
                    quote["requested_start_date"].isoformat()
                ),
                "policy_end_date": (
                    quote["requested_end_date"].isoformat()
                ),
                "issued_by": issued_by
            }

            # --------------------------------------------------
            # 9. Record policy event.
            # --------------------------------------------------

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
                    policy_id,
                    event_type,
                    None,
                    "ACTIVE",
                    issued_by,
                    event_reason,
                    Jsonb(event_details)
                )
            )

            event = cur.fetchone()

            # --------------------------------------------------
            # 10. Link renewed policy to renewal record.
            # --------------------------------------------------

            if is_renewal:

                cur.execute(
                    """
                    UPDATE renewals
                    SET renewed_policy_id = %s
                    WHERE renewal_id = %s
                      AND renewed_policy_id IS NULL
                      AND renewal_status = 'ACCEPTED'
                    """,
                    (
                        policy_id,
                        renewal["renewal_id"]
                    )
                )

                if cur.rowcount != 1:
                    raise ValueError(
                        "Could not link the renewed policy "
                        "to its renewal record."
                    )

            # --------------------------------------------------
            # 11. Return result.
            # --------------------------------------------------

            return {
                "message": (
                    "Renewed insurance policy issued successfully."
                    if is_renewal
                    else "Insurance policy issued successfully."
                ),
                "policy_id": policy_id,
                "quote_id": quote_id,
                "renewal_id": (
                    renewal["renewal_id"]
                    if is_renewal
                    else None
                ),
                "original_policy_id": (
                    renewal["policy_id"]
                    if is_renewal
                    else None
                ),
                "payment_id": payment["payment_id"],
                "policy_status": "ACTIVE",
                "policy_start_date": quote["requested_start_date"],
                "policy_end_date": quote["requested_end_date"],
                "premium_amount": float(
                    quote["calculated_premium"]
                ),
                "currency": quote["currency"],
                "issued_at": policy["issued_at"],
                "policy_event_type": event_type,
                "policy_event_id": event["policy_event_id"]
            }
