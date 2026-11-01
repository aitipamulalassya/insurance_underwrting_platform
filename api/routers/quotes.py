
from fastapi import APIRouter, HTTPException, Query

from api.database import get_connection

router = APIRouter()


@router.get("/quotes")
def get_quotes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = None
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    """
                    SELECT *
                    FROM quotes
                    WHERE quote_status = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (status.upper(), limit, offset)
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM quotes
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset)
                )

            quotes = cur.fetchall()

    return {
        "count": len(quotes),
        "limit": limit,
        "offset": offset,
        "quotes": quotes
    }


@router.get("/quotes/{quote_id}/audit-history")
def get_quote_audit_history(quote_id: str):
    """
    Return the chronological audit history of a quote.

    Combines:
    - Quote lifecycle events
    - Automated underwriting decisions
    - Human underwriting decisions
    - Risk assessment records
    """

    with get_connection() as conn:
        with conn.cursor() as cur:

            # 1. Verify quote exists.
            cur.execute(
                """
                SELECT *
                FROM quotes
                WHERE quote_id = %s
                """,
                (quote_id,)
            )

            quote = cur.fetchone()

            if not quote:
                raise HTTPException(
                    status_code=404,
                    detail="Quote not found"
                )

            # 2. Retrieve quote lifecycle events.
            cur.execute(
                """
                SELECT *
                FROM quote_events
                WHERE quote_id = %s
                ORDER BY event_at ASC
                """,
                (quote_id,)
            )

            quote_events = cur.fetchall()

            # 3. Retrieve underwriting decisions.
            cur.execute(
                """
                SELECT *
                FROM underwriting_decisions
                WHERE quote_id = %s
                ORDER BY decided_at ASC
                """,
                (quote_id,)
            )

            decisions = cur.fetchall()

            # 4. Retrieve risk assessments.
            cur.execute(
                """
                SELECT *
                FROM quote_risk_assessments
                WHERE quote_id = %s
                ORDER BY assessment_id ASC
                """,
                (quote_id,)
            )

            risk_assessments = cur.fetchall()

    # 5. Build a unified chronological timeline.
    timeline = []

    for event in quote_events:
        timeline.append({
            "source": "QUOTE_EVENT",
            "timestamp": event["event_at"],
            "event_type": event["event_type"],
            "previous_status": event["previous_status"],
            "new_status": event["new_status"],
            "actor_reference": event["actor_reference"],
            "event_reason": event["event_reason"],
            "event_details": event["event_details"]
        })

    for decision in decisions:
        timeline.append({
            "source": "UNDERWRITING_DECISION",
            "timestamp": decision["decided_at"],
            "event_type": decision["decision_type"],
            "risk_score": decision["risk_score"],
            "risk_category": decision["risk_category"],
            "decision_reason": decision["decision_reason"],
            "approval_authority": decision["approval_authority"],
            "reviewer_reference": decision["reviewer_reference"],
            "ruleset_version": decision["ruleset_version"],
            "is_final": decision["is_final"],
            "decision_id": decision["decision_id"]
        })

    timeline.sort(
        key=lambda item: item["timestamp"]
    )

    return {
        "quote_id": quote_id,
        "current_quote_status": quote["quote_status"],
        "total_quote_events": len(quote_events),
        "total_underwriting_decisions": len(decisions),
        "total_risk_assessments": len(risk_assessments),
        "audit_timeline": timeline,
        "risk_assessments": risk_assessments
    }


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM quotes
                WHERE quote_id = %s
                """,
                (quote_id,)
            )

            quote = cur.fetchone()

            if quote is None:
                raise HTTPException(
                    status_code=404,
                    detail="Quote not found"
                )

            cur.execute(
                """
                SELECT *
                FROM quote_coverages
                WHERE quote_id = %s
                """,
                (quote_id,)
            )

            coverages = cur.fetchall()

            cur.execute(
                """
                SELECT *
                FROM underwriting_decisions
                WHERE quote_id = %s
                ORDER BY decided_at DESC
                """,
                (quote_id,)
            )

            decisions = cur.fetchall()

            cur.execute(
                """
                SELECT *
                FROM quote_risk_assessments
                WHERE quote_id = %s
                ORDER BY assessment_id
                """,
                (quote_id,)
            )

            risk_assessments = cur.fetchall()

    return {
        "quote": quote,
        "coverages": coverages,
        "underwriting_decisions": decisions,
        "risk_assessments": risk_assessments
    }
