
from fastapi import APIRouter, HTTPException

from api.database import get_connection

router = APIRouter()


@router.get("/health")
def health_check():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT current_database() AS database_name"
                )
                result = cur.fetchone()

        return {
            "status": "healthy",
            "database": result["database_name"],
            "database_status": "connected"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed"
        )
