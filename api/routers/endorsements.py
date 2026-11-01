from fastapi import APIRouter, HTTPException

from api.schemas import EndorsementCreateRequest
from api.services.endorsement_service import (
    create_coverage_endorsement
)
from api.services.payment_service import record_endorsement_payment
from pydantic import BaseModel, Field
router = APIRouter()

class EndorsementPaymentRequest(BaseModel):
    payment_reference: str | None = Field(
        default=None,
        max_length=100
    )
    
@router.post(
    "/policies/{policy_id}/endorsements",
    status_code=201
)
def create_endorsement_endpoint(
    policy_id: str,
    payload: EndorsementCreateRequest
):
    try:
        return create_coverage_endorsement(
            policy_id=policy_id,
            payload=payload
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )
@router.post(
    "/endorsements/{endorsement_id}/payment",
    status_code=201
)
def create_endorsement_payment(
    endorsement_id: str,
    payload: EndorsementPaymentRequest
):
    try:
        return record_endorsement_payment(
            endorsement_id=endorsement_id,
            payment_reference=payload.payment_reference
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )