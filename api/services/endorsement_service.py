from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from psycopg.types.json import Jsonb

from api.database import get_connection


def generate_endorsement_id(cur):
    cur.execute(
        """
        SELECT COALESCE(
            MAX(
                substring(
                    endorsement_id
                    FROM '^END-[0-9]{4}-([0-9]+)$'
                )::BIGINT
            ),
            0
        ) + 1 AS next_id
        FROM endorsements
        WHERE endorsement_id ~ '^END-[0-9]{4}-[0-9]+$'
        """
    )

    next_id = cur.fetchone()["next_id"]
    return f"END-{datetime.now().year}-{next_id:06d}"
def create_coverage_endorsement(
    policy_id: str,
    payload
):
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Serialize endorsement requests to protect sequence generation.
            cur.execute(
                "SELECT pg_advisory_xact_lock(20261035)"
            )

            # Lock and retrieve the policy.
            cur.execute(
                """
                SELECT
                    policy_id,
                    quote_id,
                    product_id,
                    policy_start_date,
                    policy_end_date,
                    policy_status,
                    premium_amount,
                    currency
                FROM policies
                WHERE policy_id = %s
                FOR UPDATE
                """,
                (policy_id,)
            )

            policy = cur.fetchone()

            if not policy:
                raise ValueError("Policy not found.")

            if policy["policy_status"] != "ACTIVE":
                raise ValueError(
                    "Endorsements can only be requested for ACTIVE policies."
                )

            # Validate the requested effective date.
            if payload.effective_date < policy["policy_start_date"]:
                raise ValueError(
                    "Endorsement effective date cannot be before "
                    "the policy start date."
                )

            if payload.effective_date > policy["policy_end_date"]:
                raise ValueError(
                    "Endorsement effective date cannot be after "
                    "the policy end date."
                )

            # Retrieve the original coverage and its product limits.
            cur.execute(
                """
                SELECT
                    qc.coverage_option_id,
                    qc.selected_limit,
                    qc.coverage_premium,
                    co.coverage_name,
                    co.coverage_code,
                    co.min_limit,
                    co.max_limit,
                    co.product_id
                FROM quote_coverages qc
                JOIN coverage_options co
                    ON co.coverage_option_id = qc.coverage_option_id
                WHERE qc.quote_id = %s
                  AND qc.coverage_option_id = %s
                  AND co.product_id = %s
                FOR UPDATE OF qc
                """,
                (
                    policy["quote_id"],
                    payload.coverage_option_id,
                    policy["product_id"]
                )
            )

            coverage = cur.fetchone()

            if not coverage:
                raise ValueError(
                    "The requested coverage does not belong to this policy."
                )

            old_limit = Decimal(str(coverage["selected_limit"]))
            new_limit = Decimal(str(payload.new_selected_limit))

            if new_limit <= old_limit:
                raise ValueError(
                    "This first version supports coverage increases only. "
                    f"Current limit: {old_limit}; "
                    f"requested limit: {new_limit}."
                )

            if new_limit < Decimal(str(coverage["min_limit"])):
                raise ValueError(
                    f"Coverage limit cannot be below "
                    f"{coverage['min_limit']}."
                )

            if new_limit > Decimal(str(coverage["max_limit"])):
                raise ValueError(
                    f"Coverage limit cannot exceed "
                    f"{coverage['max_limit']}."
                )

            # Calculate the additional premium using the existing
            # coverage premium-to-limit ratio.
            old_coverage_premium = Decimal(
                str(coverage["coverage_premium"])
            )

            if old_limit <= 0:
                raise ValueError(
                    "Original coverage limit must be greater than zero."
                )

            additional_limit = new_limit - old_limit

            premium_rate = old_coverage_premium / old_limit

            additional_premium = (
                additional_limit * premium_rate
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            # Generate endorsement sequence for this policy.
            cur.execute(
                """
                SELECT COALESCE(MAX(endorsement_sequence), 0) + 1
                    AS next_sequence
                FROM endorsements
                WHERE policy_id = %s
                """,
                (policy_id,)
            )

            sequence = cur.fetchone()["next_sequence"]

            endorsement_id = generate_endorsement_id(cur)

            previous_values = {
                "coverage_option_id": coverage["coverage_option_id"],
                "coverage_code": coverage["coverage_code"],
                "coverage_name": coverage["coverage_name"],
                "selected_limit": str(old_limit),
                "coverage_premium": str(old_coverage_premium)
            }

            proposed_values = {
                "coverage_option_id": coverage["coverage_option_id"],
                "coverage_code": coverage["coverage_code"],
                "coverage_name": coverage["coverage_name"],
                "previous_limit": str(old_limit),
                "proposed_limit": str(new_limit),
                "additional_limit": str(additional_limit),
                "original_coverage_premium": str(
                    old_coverage_premium
                ),
                "additional_premium": str(additional_premium),
                "currency": policy["currency"],
                "request_reason": payload.request_reason
            }

            # Save the request. Original coverage is not modified here.
            cur.execute(
                """
                INSERT INTO endorsements (
                    endorsement_id,
                    policy_id,
                    endorsement_sequence,
                    endorsement_type,
                    effective_date,
                    previous_values,
                    proposed_values,
                    additional_premium,
                    endorsement_status,
                    decision_reason
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING requested_at
                """,
                (
                    endorsement_id,
                    policy_id,
                    sequence,
                    "COVERAGE_CHANGE",
                    payload.effective_date,
                    Jsonb(previous_values),
                    Jsonb(proposed_values),
                    additional_premium,
                    "PENDING",
                    None
                )
            )

            saved = cur.fetchone()

            return {
                "message": "Endorsement request created successfully",
                "endorsement_id": endorsement_id,
                "policy_id": policy_id,
                "endorsement_sequence": sequence,
                "endorsement_type": "COVERAGE_CHANGE",
                "endorsement_status": "PENDING",
                "coverage_name": coverage["coverage_name"],
                "previous_limit": float(old_limit),
                "proposed_limit": float(new_limit),
                "additional_premium": float(additional_premium),
                "currency": policy["currency"],
                "effective_date": payload.effective_date,
                "requested_at": saved["requested_at"]
            }