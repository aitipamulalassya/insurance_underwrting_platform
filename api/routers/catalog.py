from fastapi import APIRouter, Query
from api.database import get_connection

router = APIRouter()


@router.get("/policies")
def list_policies(
    status: str | None = Query(default=None),
    applicant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Read-only policy listing with optional status/applicant filters."""
    clauses = []
    params = []
    if status:
        clauses.append("policy_status = %s")
        params.append(status.upper())
    if applicant_id:
        clauses.append("applicant_id = %s")
        params.append(applicant_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT *
                FROM policies
                {where}
                ORDER BY issued_at DESC NULLS LAST, policy_id
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            return cur.fetchall()


@router.get("/endorsements")
def list_endorsements(
    policy_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Read-only endorsement listing with optional policy/status filters."""
    clauses = []
    params = []
    if policy_id:
        clauses.append("policy_id = %s")
        params.append(policy_id)
    if status:
        clauses.append("endorsement_status = %s")
        params.append(status.upper())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT *
                FROM endorsements
                {where}
                ORDER BY requested_at DESC NULLS LAST, endorsement_id
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            return cur.fetchall()


@router.get("/coverage-options")
def list_coverage_options(
    product_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Read-only coverage catalogue listing, optionally scoped to product."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if product_id:
                cur.execute(
                    """
                    SELECT *
                    FROM coverage_options
                    WHERE product_id = %s
                    ORDER BY coverage_option_id
                    LIMIT %s OFFSET %s
                    """,
                    (product_id, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM coverage_options
                    ORDER BY product_id, coverage_option_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            return cur.fetchall()
