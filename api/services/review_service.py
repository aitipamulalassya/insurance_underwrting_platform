
from psycopg.types.json import Jsonb

from api.database import get_connection
from api.schemas_review import HumanReviewRequest


def get_review_queue():
    """Return quotes waiting for underwriting review."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    q.quote_id,
                    q.applicant_id,
                    q.asset_id,
                    q.product_id,
                    q.requested_start_date,
                    q.requested_end_date,
                    q.requested_coverage_amount,
                    q.calculated_premium,
                    q.currency,
                    q.quote_status,
                    q.created_at,
                    ud.decision_type AS automated_recommendation,
                    ud.risk_score,
                    ud.risk_category,
                    ud.decision_reason AS automated_reason
                FROM quotes q
                LEFT JOIN underwriting_decisions ud
                    ON ud.quote_id = q.quote_id
                   AND ud.is_final = FALSE
                WHERE q.quote_status IN (
                    'PENDING_REVIEW',
                    'REFERRED'
                )
                ORDER BY q.created_at ASC
            """)

            return cur.fetchall()


def get_review_details(quote_id: str):
    """Return complete information required for underwriting review."""

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Quote, applicant, asset and product details
            cur.execute("""
                SELECT
                    q.*,
                    a.*,
                    ia.*,
                    p.product_line
                FROM quotes q
                JOIN applicants a
                    ON a.applicant_id = q.applicant_id
                JOIN insured_assets ia
                    ON ia.asset_id = q.asset_id
                JOIN products p
                    ON p.product_id = q.product_id
                WHERE q.quote_id = %s
            """, (quote_id,))

            quote = cur.fetchone()

            if not quote:
                raise ValueError("Quote not found")

            # Selected coverages
            cur.execute("""
                SELECT
                    qc.*,
                    co.coverage_code,
                    co.coverage_name
                FROM quote_coverages qc
                JOIN coverage_options co
                    ON co.coverage_option_id = qc.coverage_option_id
                WHERE qc.quote_id = %s
                ORDER BY co.coverage_code
            """, (quote_id,))

            coverages = cur.fetchall()

            # Original risk observations
            cur.execute("""
                SELECT *
                FROM quote_risk_observations
                WHERE quote_id = %s
                ORDER BY observation_id
            """, (quote_id,))

            observations = cur.fetchall()

            # Individual risk factor assessments
            cur.execute("""
                SELECT *
                FROM quote_risk_assessments
                WHERE quote_id = %s
                ORDER BY assessment_id
            """, (quote_id,))

            assessments = cur.fetchall()

            # Automated and human decision history
            cur.execute("""
                SELECT *
                FROM underwriting_decisions
                WHERE quote_id = %s
                ORDER BY decided_at
            """, (quote_id,))

            decisions = cur.fetchall()

            return {
                "quote": quote,
                "coverages": coverages,
                "risk_observations": observations,
                "risk_assessments": assessments,
                "decision_history": decisions
            }


def submit_human_decision(
    quote_id: str,
    payload: HumanReviewRequest
):
    """Save a human underwriting decision and audit event."""

    status_mapping = {
        "APPROVE": "APPROVED",
        "REFER": "REFERRED",
        "DECLINE": "DECLINED"
    }

    new_status = status_mapping[payload.decision_type]

    # REFER requires additional review.
    # APPROVE and DECLINE are final decisions.
    is_final = payload.decision_type in (
        "APPROVE",
        "DECLINE"
    )

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Serialize decision ID generation.
            cur.execute(
                "SELECT pg_advisory_xact_lock(20261031)"
            )

            # Lock quote while reviewing it.
            cur.execute("""
                SELECT quote_status
                FROM quotes
                WHERE quote_id = %s
                FOR UPDATE
            """, (quote_id,))

            quote = cur.fetchone()

            if not quote:
                raise ValueError("Quote not found")

            previous_status = quote["quote_status"]

            if previous_status not in (
                "PENDING_REVIEW",
                "REFERRED"
            ):
                raise ValueError(
                    f"Quote cannot be reviewed from status: {previous_status}"
                )

            # Prevent a second final decision.
            cur.execute("""
                SELECT decision_id
                FROM underwriting_decisions
                WHERE quote_id = %s
                  AND is_final = TRUE
                LIMIT 1
            """, (quote_id,))

            if cur.fetchone():
                raise ValueError(
                    "A final underwriting decision already exists"
                )

            # Retrieve original automated recommendation.
            cur.execute("""
                SELECT
                    risk_score,
                    risk_category,
                    ruleset_version
                FROM underwriting_decisions
                WHERE quote_id = %s
                  AND is_final = FALSE
                ORDER BY decided_at DESC
                LIMIT 1
            """, (quote_id,))

            automated = cur.fetchone()

            if not automated:
                raise ValueError(
                    "Automated underwriting recommendation not found"
                )

            # Generate a unique human decision ID.
            cur.execute("""
                SELECT decision_id
                FROM underwriting_decisions
                WHERE decision_id LIKE %s
                ORDER BY decision_id DESC
                LIMIT 1
            """, (f"UND-{quote_id}-R%",))

            existing = cur.fetchone()

            review_number = 1

            if existing:
                try:
                    review_number = int(
                        existing["decision_id"].rsplit("R", 1)[1]
                    ) + 1
                except (ValueError, IndexError):
                    raise ValueError(
                        "Could not generate the next review decision ID"
                    )

            decision_id = f"UND-{quote_id}-R{review_number}"

            if len(decision_id) > 24:
                raise ValueError(
                    "Generated decision ID exceeds 24 characters"
                )

            # Insert human decision separately.
            # Original automated decision remains unchanged.
            cur.execute("""
                INSERT INTO underwriting_decisions (
                    decision_id,
                    quote_id,
                    decision_type,
                    risk_score,
                    risk_category,
                    decision_reason,
                    approval_authority,
                    reviewer_reference,
                    decided_at,
                    ruleset_version,
                    is_final
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, %s, %s
                )
            """, (
                decision_id,
                quote_id,
                payload.decision_type,
                automated["risk_score"],
                automated["risk_category"],
                payload.decision_reason,
                payload.approval_authority,
                payload.reviewer_reference,
                automated["ruleset_version"],
                is_final
            ))

            # Update quote status.
            cur.execute("""
                UPDATE quotes
                SET quote_status = %s
                WHERE quote_id = %s
            """, (
                new_status,
                quote_id
            ))

            # Prepare audit event details.
            event_details = {
                "decision_id": decision_id,
                "decision_type": payload.decision_type,
                "is_final": is_final,
                "risk_score": (
                    float(automated["risk_score"])
                    if automated["risk_score"] is not None
                    else None
                ),
                "risk_category": automated["risk_category"],
                "approval_authority": payload.approval_authority
            }

            # Insert audit event.
            # PostgreSQL automatically generates quote_event_id.
            cur.execute("""
                INSERT INTO quote_events (
                    quote_id,
                    event_type,
                    previous_status,
                    new_status,
                    event_at,
                    actor_reference,
                    event_reason,
                    event_details
                )
                VALUES (
                    %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, %s, %s, %s
                )
                RETURNING quote_event_id
            """, (
                quote_id,
                "UNDERWRITING_REVIEW",
                previous_status,
                new_status,
                payload.reviewer_reference,
                payload.decision_reason,
                Jsonb(event_details)
            ))

            event = cur.fetchone()

            return {
                "message": "Human underwriting decision saved successfully",
                "quote_id": quote_id,
                "decision_id": decision_id,
                "quote_event_id": event["quote_event_id"],
                "decision_type": payload.decision_type,
                "quote_status": new_status,
                "is_final": is_final
            }
