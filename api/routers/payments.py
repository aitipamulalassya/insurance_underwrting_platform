from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.schemas import PaymentCreateRequest
from api.services.payment_service import (
    record_payment,
    confirm_payment
)

router = APIRouter()


class PaymentConfirmationRequest(BaseModel):
    verifier_reference: str = Field(min_length=1, max_length=100)


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