
from datetime import date
from decimal import Decimal

from psycopg.types.json import Jsonb

from api.database import get_connection


def activate_endorsement(endorsement_id: str):

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Prevent concurrent endorsement activation operations.
            cur.execute(
                "SELECT pg_advisory_xact_lock(20261037)"
            )

            # Fetch and lock endorsement and policy.
            cur.execute(
                """
                SELECT
                    e.endorsement_id,
                    e.policy_id,
                    e.endorsement_sequence,
                    e.endorsement_type,
                    e.effective_date,
                    e.previous_values,
                    e.proposed_values,
                    e.additional_premium,
                    e.endorsement_status,
                    e.activated_at,
                    p.quote_id,
                    p.policy_status,
                    p.premium_amount,
                    p.currency
                FROM endorsements e
                JOIN policies p
                    ON p.policy_id = e.policy_id
                WHERE e.endorsement_id = %s
                FOR UPDATE OF e, p
                """,
                (endorsement_id,)
            )

            endorsement = cur.fetchone()

            if not endorsement:
                raise ValueError("Endorsement not found.")

            if endorsement["endorsement_status"] != "APPROVED":
                raise ValueError(
                    "Only APPROVED endorsements can be activated."
                )

            if endorsement["activated_at"] is not None:
                raise ValueError(
                    "This endorsement has already been activated."
                )

            if endorsement["policy_status"] != "ACTIVE":
                raise ValueError(
                    "The associated policy is not ACTIVE."
                )

            if endorsement["endorsement_type"] != "COVERAGE_CHANGE":
                raise ValueError(
                    "Only COVERAGE_CHANGE endorsements are supported "
                    "by this activation service."
                )

            if endorsement["effective_date"] > date.today():
                raise ValueError(
                    "The endorsement effective date has not arrived. "
                    f"Effective date: {endorsement['effective_date']}."
                )

            previous_values = endorsement["previous_values"]
            proposed_values = endorsement["proposed_values"]

            if not isinstance(previous_values, dict):
                raise ValueError("Invalid previous_values data.")

            if not isinstance(proposed_values, dict):
                raise ValueError("Invalid proposed_values data.")

            coverage_option_id = proposed_values.get(
                "coverage_option_id"
            )

            if not coverage_option_id:
                raise ValueError(
                    "Coverage option ID is missing from endorsement."
                )

            try:
                old_limit = Decimal(
                    str(previous_values["selected_limit"])
                )

                new_limit = Decimal(
                    str(proposed_values["proposed_limit"])
                )

                old_coverage_premium = Decimal(
                    str(previous_values["coverage_premium"])
                )

                additional_premium = Decimal(
                    str(endorsement["additional_premium"])
                )

            except (KeyError, ValueError, TypeError):
                raise ValueError(
                    "Invalid numeric values in endorsement data."
                )

            if new_limit <= old_limit:
                raise ValueError(
                    "Proposed coverage must be greater than original coverage."
                )

            if additional_premium < 0:
                raise ValueError("Invalid additional premium.")

            # Lock and inspect the original quote coverage.
            cur.execute(
                """
                SELECT
                    qc.selected_limit,
                    qc.coverage_premium,
                    co.min_limit,
                    co.max_limit
                FROM quote_coverages qc
                JOIN coverage_options co
                    ON co.coverage_option_id = qc.coverage_option_id
                WHERE qc.quote_id = %s
                  AND qc.coverage_option_id = %s
                FOR UPDATE OF qc
                """,
                (
                    endorsement["quote_id"],
                    coverage_option_id
                )
            )

            coverage = cur.fetchone()

            if not coverage:
                raise ValueError("Original coverage was not found.")

            current_limit = Decimal(
                str(coverage["selected_limit"])
            )

            current_coverage_premium = Decimal(
                str(coverage["coverage_premium"])
            )

            if current_limit != old_limit:
                raise ValueError(
                    "Current coverage does not match the original "
                    "endorsement values. Manual reconciliation required."
                )

            if current_coverage_premium != old_coverage_premium:
                raise ValueError(
                    "Current coverage premium differs from the original "
                    "endorsement values. Manual reconciliation required."
                )

            if new_limit < Decimal(str(coverage["min_limit"])):
                raise ValueError("Proposed limit is below the minimum.")

            if new_limit > Decimal(str(coverage["max_limit"])):
                raise ValueError("Proposed limit exceeds the maximum.")

            # Additional payment is required only when premium is positive.
            payment = None

            if additional_premium > 0:

                cur.execute(
                    """
                    SELECT
                        payment_id,
                        amount,
                        currency,
                        payment_status,
                        confirmed_at
                    FROM payments
                    WHERE endorsement_id = %s
                    FOR UPDATE
                    """,
                    (endorsement_id,)
                )

                payment = cur.fetchone()

                if not payment:
                    raise ValueError(
                        "Additional endorsement payment has not been recorded."
                    )

                if payment["payment_status"] != "CONFIRMED":
                    raise ValueError(
                        "Additional endorsement payment is not confirmed."
                    )

                if payment["confirmed_at"] is None:
                    raise ValueError(
                        "Payment confirmation timestamp is missing."
                    )

                if Decimal(str(payment["amount"])) != additional_premium:
                    raise ValueError(
                        "Confirmed payment amount does not match "
                        "the endorsement premium."
                    )

                if payment["currency"] != endorsement["currency"]:
                    raise ValueError(
                        "Payment currency does not match policy currency."
                    )

            # Apply the approved coverage change.
            new_coverage_premium = (
                old_coverage_premium + additional_premium
            )

            cur.execute(
                """
                UPDATE quote_coverages
                SET
                    selected_limit = %s,
                    coverage_premium = %s
                WHERE quote_id = %s
                  AND coverage_option_id = %s
                """,
                (
                    new_limit,
                    new_coverage_premium,
                    endorsement["quote_id"],
                    coverage_option_id
                )
            )

            if cur.rowcount != 1:
                raise ValueError(
                    "Coverage update could not be completed."
                )

            new_policy_premium = (
                Decimal(str(endorsement["premium_amount"]))
                + additional_premium
            )

            cur.execute(
                """
                UPDATE policies
                SET premium_amount = %s
                WHERE policy_id = %s
                """,
                (
                    new_policy_premium,
                    endorsement["policy_id"]
                )
            )

            if cur.rowcount != 1:
                raise ValueError(
                    "Policy premium update could not be completed."
                )

            # Mark the endorsement as activated.
            cur.execute(
                """
                UPDATE endorsements
                SET activated_at = CURRENT_TIMESTAMP
                WHERE endorsement_id = %s
                  AND activated_at IS NULL
                RETURNING activated_at
                """,
                (endorsement_id,)
            )

            # IMPORTANT FIX:
            # Fetch the timestamp returned by UPDATE ... RETURNING.
            activation = cur.fetchone()

            if not activation:
                raise ValueError(
                    "Endorsement activation could not be completed."
                )

            # Prepare audit event details.
            event_details = {
                "endorsement_id": endorsement_id,
                "endorsement_sequence": endorsement[
                    "endorsement_sequence"
                ],
                "coverage_option_id": coverage_option_id,
                "previous_limit": str(old_limit),
                "new_limit": str(new_limit),
                "previous_coverage_premium": str(
                    old_coverage_premium
                ),
                "new_coverage_premium": str(
                    new_coverage_premium
                ),
                "additional_premium": str(additional_premium),
                "new_policy_premium": str(new_policy_premium),
                "effective_date": endorsement[
                    "effective_date"
                ].isoformat(),
                "payment_id": (
                    payment["payment_id"] if payment else None
                )
            }

            # Insert policy audit event.
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
                    "ENDORSEMENT_ACTIVATED",
                    "ACTIVE",
                    "ACTIVE",
                    "SYSTEM",
                    "Approved endorsement activated on its effective date.",
                    Jsonb(event_details)
                )
            )

            event = cur.fetchone()

            return {
                "message": "Endorsement activated successfully",
                "endorsement_id": endorsement_id,
                "policy_id": endorsement["policy_id"],
                "endorsement_status": "APPROVED",
                "activated_at": activation["activated_at"].isoformat(),
                "coverage_option_id": coverage_option_id,
                "previous_limit": float(old_limit),
                "new_limit": float(new_limit),
                "additional_premium": float(additional_premium),
                "new_policy_premium": float(new_policy_premium),
                "payment_id": (
                    payment["payment_id"] if payment else None
                ),
                "policy_event_id": event["policy_event_id"]
            }
