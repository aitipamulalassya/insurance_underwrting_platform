
from fastapi import APIRouter, HTTPException, Query

from api.database import get_connection

router = APIRouter()


@router.get("/underwriting/decisions")
def get_underwriting_decisions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    decision_type: str | None = None
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if decision_type:
                cur.execute(
                    """
                    SELECT *
                    FROM underwriting_decisions
                    WHERE decision_type = %s
                    ORDER BY decided_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (decision_type.upper(), limit, offset)
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM underwriting_decisions
                    ORDER BY decided_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset)
                )

            decisions = cur.fetchall()

    return {
        "count": len(decisions),
        "limit": limit,
        "offset": offset,
        "decisions": decisions
    }


@router.get("/underwriting/decisions/{quote_id}")
def get_quote_decision(quote_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
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

    if not decisions:
        raise HTTPException(
            status_code=404,
            detail="No underwriting decision found for this quote"
        )

    return {
        "quote_id": quote_id,
        "total_decisions": len(decisions),
        "decisions": decisions
    }


@router.get("/underwriting/summary")
def get_underwriting_summary():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    decision_type,
                    is_final,
                    COUNT(*) AS total_decisions,
                    COUNT(DISTINCT reviewer_reference)
                        AS total_reviewers
                FROM underwriting_decisions
                GROUP BY decision_type, is_final
                ORDER BY decision_type, is_final
                """
            )

            summary = cur.fetchall()

            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_decisions,
                    COUNT(*) FILTER (
                        WHERE is_final = TRUE
                    ) AS final_decisions,
                    COUNT(*) FILTER (
                        WHERE is_final = FALSE
                    ) AS non_final_decisions
                FROM underwriting_decisions
                """
            )

            totals = cur.fetchone()

    return {
        "totals": totals,
        "decision_breakdown": summary
    }
