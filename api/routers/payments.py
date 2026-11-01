from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.database import get_connection
from api.schemas import PaymentCreateRequest
from api.services.payment_service import (
    record_payment,
    confirm_payment
)

router = APIRouter()


class PaymentConfirmationRequest(BaseModel):
    verifier_reference: str = Field(min_length=1, max_length=100)


@router.get("/payments")
def list_payments(
    status: str = Query(default="PENDING", pattern="^(PENDING|CONFIRMED|FAILED)$"),
    limit: int = Query(default=100, ge=1, le=500),
):
    """List payments for authorized operations UI selection."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    payment_id,
                    quote_id,
                    amount,
                    currency,
                    payment_status,
                    payment_reference,
                    recorded_at,
                    confirmed_at
                FROM payments
                WHERE payment_status = %s
                ORDER BY recorded_at DESC
                LIMIT %s
                """,
                (status, limit),
            )
            payments = cur.fetchall()

    return {"count": len(payments), "payments": payments}


@router.post("/quotes/{quote_id}/payments", status_code=201)
def create_payment(
    quote_id: str,
    payload: PaymentCreateRequest
):
    try:
        return record_payment(
            quote_id=quote_id,
            amount=payload.amount,
            payment_reference=payload.payment_reference
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/payments/{payment_id}/confirm")
def confirm_payment_endpoint(
    payment_id: str,
    payload: PaymentConfirmationRequest
):
    try:
        return confirm_payment(
            payment_id=payment_id,
            verifier_reference=payload.verifier_reference
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
