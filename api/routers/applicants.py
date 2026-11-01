
from fastapi import APIRouter, HTTPException, Query

from api.database import get_connection

router = APIRouter()


@router.get("/applicants")
def get_applicants(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM applicants
                ORDER BY applicant_id
                LIMIT %s OFFSET %s
                """,
                (limit, offset)
            )
            return cur.fetchall()


@router.get("/applicants/{applicant_id}")
def get_applicant(applicant_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM applicants
                WHERE applicant_id = %s
                """,
                (applicant_id,)
            )
            applicant = cur.fetchone()

    if applicant is None:
        raise HTTPException(
            status_code=404,
            detail="Applicant not found"
        )

    return applicant
