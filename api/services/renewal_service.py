
from datetime import datetime
from api.database import get_connection
from decimal import Decimal

from api.schemas import QuoteCreateRequest, CoverageSelection
from api.services.quote_service import create_quote

def create_renewal_quote(renewal_id: str):
    """
    Generate a new underwriting quote from an accepted renewal.

    Existing coverage selections and risk observations are carried
    forward, but eligibility, risk and premium are recalculated.
    """

    with get_connection() as conn:
        renewal = conn.execute(
            """
            SELECT
                r.renewal_id,
                r.policy_id,
                r.renewal_status,
                r.proposed_start_date,
                r.proposed_end_date,
                p.applicant_id,
                p.asset_id,
                p.product_id,
                p.quote_id AS original_quote_id
            FROM renewals r
            JOIN policies p
                ON p.policy_id = r.policy_id
            WHERE r.renewal_id = %s
            """,
            (renewal_id,)
        ).fetchone()

        if not renewal:
            raise ValueError("Renewal not found.")

        if renewal["renewal_status"] != "ACCEPTED":
            raise ValueError(
                "Only ACCEPTED renewals can generate a quote."
            )

        # Retrieve original policy coverage selections.
        coverage_rows = conn.execute(
            """
            SELECT
                coverage_option_id,
                selected_limit
            FROM quote_coverages
            WHERE quote_id = %s
            ORDER BY coverage_option_id
            """,
            (renewal["original_quote_id"],)
        ).fetchall()

        if not coverage_rows:
            raise ValueError(
                "Original policy has no coverage selections."
            )

        # Retrieve original risk observations.
        observation_rows = conn.execute(
            """
            SELECT factor_code, observed_value
            FROM quote_risk_observations
            WHERE quote_id = %s
            """,
            (renewal["original_quote_id"],)
        ).fetchall()

        risk_observations = {
            row["factor_code"]: row["observed_value"]
            for row in observation_rows
        }

        payload = QuoteCreateRequest(
            applicant_id=renewal["applicant_id"],
            asset_id=renewal["asset_id"],
            product_id=renewal["product_id"],
            requested_start_date=renewal["proposed_start_date"],
            requested_end_date=renewal["proposed_end_date"],
            coverages=[
                CoverageSelection(
                    coverage_option_id=row["coverage_option_id"],
                    selected_limit=Decimal(
                        str(row["selected_limit"])
                    )
                )
                for row in coverage_rows
            ],
            risk_observations=risk_observations
        )

    # Create the new quote using the existing underwriting engine.
    result = create_quote(
        payload,
        renewal_id=renewal_id
    )

    return {
        "message": "Renewal quote generated successfully.",
        "renewal_id": renewal_id,
        "original_policy_id": renewal["policy_id"],
        "original_quote_id": renewal["original_quote_id"],
        **result
    }

def generate_renewal_id(cur):
    """Generate a unique renewal ID."""

    cur.execute(
        """
        SELECT COALESCE(
            MAX(
                substring(
                    renewal_id
                    FROM '^REN-[0-9]{4}-([0-9]+)$'
                )::BIGINT
            ),
            0
        ) + 1 AS next_id
        FROM renewals
        WHERE renewal_id ~ '^REN-[0-9]{4}-[0-9]+$'
        """
    )

    next_id = cur.fetchone()["next_id"]
    return f"REN-{datetime.now().year}-{next_id:06d}"


def generate_renewal_offers(lead_days: int = 60):
    """
    Generate renewal offers for active policies approaching expiry.

    The current policy premium is used as the provisional
    renewal premium. Risk reassessment can update this later.
    """

    if not 1 <= lead_days <= 730:
        raise ValueError("lead_days must be between 1 and 730.")

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Serialize renewal offer generation.
            cur.execute(
                "SELECT pg_advisory_xact_lock(20261037)"
            )

            # Find active policies approaching expiry.
            cur.execute(
                """
                SELECT
                    p.policy_id,
                    p.policy_end_date,
                    p.premium_amount,
                    p.currency
                FROM policies p
                WHERE p.policy_status = 'ACTIVE'
                  AND p.policy_end_date >= CURRENT_DATE
                  AND p.policy_end_date <= (
                      CURRENT_DATE + (%s * INTERVAL '1 day')
                  )::date
                  AND NOT EXISTS (
                      SELECT 1
                      FROM renewals r
                      WHERE r.policy_id = p.policy_id
                        AND r.renewal_year =
                            EXTRACT(YEAR FROM p.policy_end_date)::INTEGER
                  )
                ORDER BY p.policy_end_date
                FOR UPDATE OF p
                """,
                (lead_days,)
            )

            policies = cur.fetchall()

            generated = []

            for policy in policies:

                renewal_id = generate_renewal_id(cur)

                proposed_start_date = policy["policy_end_date"]

                cur.execute(
                    """
                    SELECT
                        (%s::date + INTERVAL '1 year')::date
                        AS proposed_end_date
                    """,
                    (proposed_start_date,)
                )

                proposed_end_date = cur.fetchone()[
                    "proposed_end_date"
                ]

                renewal_year = proposed_start_date.year

                # Store the renewal offer.
                cur.execute(
                    """
                    INSERT INTO renewals (
                        renewal_id,
                        policy_id,
                        renewal_year,
                        proposed_start_date,
                        proposed_end_date,
                        proposed_premium,
                        renewal_status,
                        offer_expires_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, 'OFFERED',
                        LEAST(CURRENT_DATE + 30, %s::date)
                    )
                    RETURNING offer_generated_at, offer_expires_at
                    """,
                    (
                        renewal_id,
                        policy["policy_id"],
                        renewal_year,
                        proposed_start_date,
                        proposed_end_date,
                        policy["premium_amount"],
                        policy["policy_end_date"]
                    )
                )
                offer = cur.fetchone()

                generated.append({
                    "renewal_id": renewal_id,
                    "policy_id": policy["policy_id"],
                    "renewal_year": renewal_year,
                    "proposed_start_date": proposed_start_date,
                    "proposed_end_date": proposed_end_date,
                    "proposed_premium": float(
                        policy["premium_amount"]
                    ),
                    "currency": policy["currency"],
                    "renewal_status": "OFFERED",
                    "offer_generated_at": offer["offer_generated_at"],
                    "offer_expires_at": offer["offer_expires_at"]
                })

            return {
                "message": "Renewal offer generation completed.",
                "lead_days": lead_days,
                "offers_generated": len(generated),
                "renewals": generated
            }


def respond_to_renewal(
    renewal_id: str,
    decision: str,
    decision_reason: str
):
    decision = decision.upper()

    if decision not in ("ACCEPT", "DECLINE"):
        raise ValueError("Decision must be ACCEPT or DECLINE.")

    new_status = (
        "ACCEPTED" if decision == "ACCEPT" else "DECLINED"
    )

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    renewal_id,
                    policy_id,
                    renewal_status,
                    proposed_premium,
                    proposed_start_date,
                    proposed_end_date,
                    offer_expires_at
                FROM renewals
                WHERE renewal_id = %s
                FOR UPDATE
                """,
                (renewal_id,)
            )

            renewal = cur.fetchone()

            if not renewal:
                raise ValueError("Renewal offer not found.")

            if renewal["renewal_status"] != "OFFERED":
                raise ValueError(
                    "Only OFFERED renewals can receive a response. "
                    f"Current status: {renewal['renewal_status']}"
                )

            # Expiry date is inclusive: the customer may respond
            # through offer_expires_at. Expire only after that date.
            cur.execute("SELECT CURRENT_DATE AS today")
            today = cur.fetchone()["today"]

            if today > renewal["offer_expires_at"]:
                cur.execute(
                    """
                    UPDATE renewals
                    SET
                        renewal_status = 'EXPIRED',
                        expired_at = CURRENT_TIMESTAMP,
                        decision_reason =
                            'Renewal offer expired without customer response.'
                    WHERE renewal_id = %s
                      AND renewal_status = 'OFFERED'
                    """,
                    (renewal_id,)
                )

                return {
                    "message": "Renewal offer has expired.",
                    "renewal_id": renewal_id,
                    "policy_id": renewal["policy_id"],
                    "renewal_status": "EXPIRED",
                    "offer_expires_at": renewal["offer_expires_at"]
                }

            cur.execute(
                """
                UPDATE renewals
                SET
                    renewal_status = %s,
                    responded_at = CURRENT_TIMESTAMP,
                    decision_reason = %s
                WHERE renewal_id = %s
                RETURNING responded_at
                """,
                (
                    new_status,
                    decision_reason,
                    renewal_id
                )
            )

            result = cur.fetchone()

            return {
                "message": (
                    "Renewal offer accepted successfully."
                    if decision == "ACCEPT"
                    else "Renewal offer declined successfully."
                ),
                "renewal_id": renewal_id,
                "policy_id": renewal["policy_id"],
                "renewal_status": new_status,
                "proposed_premium": float(
                    renewal["proposed_premium"]
                ),
                "proposed_start_date": renewal[
                    "proposed_start_date"
                ],
                "proposed_end_date": renewal[
                    "proposed_end_date"
                ],
                "responded_at": result["responded_at"]
            }


def get_renewals(status: str | None = None):
    """Return renewal offers with their quote, payment and policy details."""

    allowed_statuses = {
        "OFFERED",
        "ACCEPTED",
        "DECLINED",
        "EXPIRED",
        "INELIGIBLE"
    }

    if status is not None:
        status = status.upper()

        if status not in allowed_statuses:
            raise ValueError(
                "Invalid renewal status. Allowed values: "
                + ", ".join(sorted(allowed_statuses))
            )

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    r.renewal_id,
                    r.policy_id AS original_policy_id,
                    r.renewed_policy_id,
                    r.renewal_year,
                    r.offer_generated_at,
                    r.offer_expires_at,
                    r.expired_at,
                    r.proposed_start_date,
                    r.proposed_end_date,
                    r.proposed_premium,
                    r.renewal_status,
                    r.responded_at,
                    r.decision_reason,

                    q.quote_id AS renewal_quote_id,
                    q.quote_status,
                    q.calculated_premium,

                    p.payment_id,
                    p.payment_status,
                    p.amount AS payment_amount,
                    p.confirmed_at AS payment_confirmed_at

                FROM renewals r

                LEFT JOIN quotes q
                    ON q.renewal_id = r.renewal_id

                LEFT JOIN payments p
                    ON p.renewal_id = r.renewal_id

                WHERE (
                    %s::VARCHAR IS NULL
                    OR r.renewal_status = %s::VARCHAR
                )

                ORDER BY r.offer_generated_at DESC
                """,
                (status, status)
            )
            records = cur.fetchall()

            return {
                "total_renewals": len(records),
                "renewals": records
            }


def get_renewal(renewal_id: str):
    """Return complete details of one renewal."""

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    r.renewal_id,
                    r.policy_id AS original_policy_id,
                    r.renewed_policy_id,
                    r.renewal_year,
                    r.offer_generated_at,
                    r.offer_expires_at,
                    r.expired_at,
                    r.proposed_start_date,
                    r.proposed_end_date,
                    r.proposed_premium,
                    r.renewal_status,
                    r.responded_at,
                    r.decision_reason,

                    original.policy_status AS original_policy_status,
                    original.policy_start_date AS original_start_date,
                    original.policy_end_date AS original_end_date,
                    original.premium_amount AS original_premium,

                    q.quote_id AS renewal_quote_id,
                    q.quote_status,
                    q.calculated_premium,
                    q.applicant_accepted_at,

                    payment.payment_id,
                    payment.amount AS payment_amount,
                    payment.currency AS payment_currency,
                    payment.payment_status,
                    payment.payment_reference,
                    payment.recorded_at,
                    payment.confirmed_at,

                    renewed.policy_status AS renewed_policy_status,
                    renewed.policy_start_date AS renewed_start_date,
                    renewed.policy_end_date AS renewed_end_date,
                    renewed.premium_amount AS renewed_premium,
                    renewed.issued_at

                FROM renewals r

                JOIN policies original
                    ON original.policy_id = r.policy_id

                LEFT JOIN quotes q
                    ON q.renewal_id = r.renewal_id

                LEFT JOIN payments payment
                    ON payment.renewal_id = r.renewal_id

                LEFT JOIN policies renewed
                    ON renewed.policy_id = r.renewed_policy_id

                WHERE r.renewal_id = %s
                """,
                (renewal_id,)
            )

            renewal = cur.fetchone()

            if not renewal:
                raise ValueError("Renewal not found.")

            return renewal

def expire_renewal_offers():
    """
    Expire unanswered renewal offers after their stored expiry date.

    offer_expires_at is inclusive. An offer expires on the day after
    that date. Accepted, declined and already expired offers are untouched.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Prevent concurrent expiry jobs from processing the same rows.
            cur.execute(
                "SELECT pg_advisory_xact_lock(20261038)"
            )

            cur.execute(
                """
                UPDATE renewals
                SET
                    renewal_status = 'EXPIRED',
                    expired_at = CURRENT_TIMESTAMP,
                    decision_reason = COALESCE(
                        decision_reason,
                        'Renewal offer expired without customer response.'
                    )
                WHERE renewal_status = 'OFFERED'
                  AND offer_expires_at < CURRENT_DATE
                RETURNING
                    renewal_id,
                    policy_id,
                    renewal_year,
                    offer_generated_at,
                    offer_expires_at,
                    expired_at,
                    proposed_start_date,
                    proposed_end_date,
                    proposed_premium,
                    renewal_status
                """
            )

            expired_records = cur.fetchall()

            return {
                "message": "Renewal offer expiry process completed.",
                "expired_count": len(expired_records),
                "expired_renewals": expired_records
            }
