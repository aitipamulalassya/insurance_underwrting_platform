from decimal import Decimal
from psycopg.types.json import Jsonb

from api.database import get_connection


def review_endorsement(
    endorsement_id: str,
    decision: str,
    reviewer_reference: str,
    decision_reason: str
):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Lock the endorsement and its associated policy.
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

            if endorsement["endorsement_status"] != "PENDING":
                raise ValueError(
                    "Only PENDING endorsements can be reviewed. "
                    f"Current status: "
                    f"{endorsement['endorsement_status']}"
                )

            if endorsement["policy_status"] != "ACTIVE":
                raise ValueError(
                    "Endorsement review requires an ACTIVE policy."
                )

            previous_status = endorsement["endorsement_status"]

            if decision == "REJECT":

                cur.execute(
                    """
                    UPDATE endorsements
                    SET
                        endorsement_status = 'REJECTED',
                        decision_reason = %s
                    WHERE endorsement_id = %s
                    """,
                    (decision_reason, endorsement_id)
                )

                event_details = {
                    "endorsement_id": endorsement_id,
                    "endorsement_sequence": endorsement[
                        "endorsement_sequence"
                    ],
                    "decision": "REJECT",
                    "decision_reason": decision_reason
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
                        "ENDORSEMENT_REJECTED",
                        "ACTIVE",
                        "ACTIVE",
                        reviewer_reference,
                        decision_reason,
                        Jsonb(event_details)
                    )
                )

                event = cur.fetchone()

                return {
                    "message": "Endorsement rejected successfully",
                    "endorsement_id": endorsement_id,
                    "policy_id": endorsement["policy_id"],
                    "endorsement_status": "REJECTED",
                    "decision_reason": decision_reason,
                    "policy_event_id": event["policy_event_id"]
                }

            # APPROVE: validate the stored request before applying it.
                        # APPROVE: validate the request, but do not apply the change.

            if endorsement["endorsement_type"] != "COVERAGE_CHANGE":
                raise ValueError(
                    "This review implementation currently supports "
                    "COVERAGE_CHANGE endorsements only."
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

            if new_limit <= old_limit:
                raise ValueError(
                    "Proposed coverage limit must exceed the original limit."
                )

            if additional_premium < 0:
                raise ValueError("Invalid additional premium.")

            # Lock and verify the original coverage.
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
                raise ValueError(
                    "Original policy coverage could not be found."
                )

            if Decimal(str(coverage["selected_limit"])) != old_limit:
                raise ValueError(
                    "Original coverage has changed since the endorsement "
                    "was requested. Manual review is required."
                )

            if Decimal(str(coverage["coverage_premium"])) != (
                old_coverage_premium
            ):
                raise ValueError(
                    "Original coverage premium has changed since the "
                    "endorsement was requested."
                )

            if new_limit < Decimal(str(coverage["min_limit"])):
                raise ValueError("Proposed limit is below the minimum.")

            if new_limit > Decimal(str(coverage["max_limit"])):
                raise ValueError("Proposed limit exceeds the maximum.")

            # Approval only. Do not update quote_coverages or policies.
            cur.execute(
                """
                UPDATE endorsements
                SET
                    endorsement_status = 'APPROVED',
                    decision_reason = %s
                WHERE endorsement_id = %s
                """,
                (decision_reason, endorsement_id)
            )

            event_details = {
                "endorsement_id": endorsement_id,
                "endorsement_sequence": endorsement[
                    "endorsement_sequence"
                ],
                "coverage_option_id": coverage_option_id,
                "previous_limit": str(old_limit),
                "proposed_limit": str(new_limit),
                "additional_premium": str(additional_premium),
                "effective_date": endorsement[
                    "effective_date"
                ].isoformat(),
                "reviewed_by": reviewer_reference,
                "decision_reason": decision_reason
            }

            # Record approval only, not activation.
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
                    "ENDORSEMENT_APPROVED",
                    "ACTIVE",
                    "ACTIVE",
                    reviewer_reference,
                    decision_reason,
                    Jsonb(event_details)
                )
            )

            event = cur.fetchone()

            return {
                "message": "Endorsement approved successfully. "
                           "Coverage changes are pending activation.",
                "endorsement_id": endorsement_id,
                "policy_id": endorsement["policy_id"],
                "endorsement_status": "APPROVED",
                "coverage_option_id": coverage_option_id,
                "previous_limit": float(old_limit),
                "proposed_limit": float(new_limit),
                "additional_premium": float(additional_premium),
                "policy_event_id": event["policy_event_id"]
            }