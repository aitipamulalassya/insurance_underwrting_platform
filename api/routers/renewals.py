
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.services.renewal_service import (
    generate_renewal_offers,
    respond_to_renewal,
    create_renewal_quote,
    get_renewals,
    get_renewal,
    expire_renewal_offers,
)

router = APIRouter()


# -------------------------------
# Request schema
# -------------------------------

class RenewalDecisionRequest(BaseModel):
    decision: str
    decision_reason: str = Field(
        min_length=3,
        max_length=500
    )


# -------------------------------
# Generate renewal offers
# -------------------------------

@router.post("/renewals/generate")
def generate_renewals_endpoint(
    lead_days: int = Query(default=60, ge=1, le=730)
):
    try:
        return generate_renewal_offers(lead_days)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# -------------------------------
# Customer accepts or declines
# -------------------------------

@router.post("/renewals/{renewal_id}/decision")
def renewal_decision_endpoint(
    renewal_id: str,
    payload: RenewalDecisionRequest
):
    try:
        return respond_to_renewal(
            renewal_id=renewal_id,
            decision=payload.decision,
            decision_reason=payload.decision_reason
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# -------------------------------
# Generate renewal quote
# -------------------------------

@router.post(
    "/renewals/{renewal_id}/quote",
    status_code=201
)
def create_renewal_quote_endpoint(renewal_id: str):
    try:
        return create_renewal_quote(renewal_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# -------------------------------
# List all renewals
# -------------------------------

@router.get("/renewals")
def list_renewals_endpoint(
    status: str | None = Query(default=None)
):
    try:
        return get_renewals(status)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# -------------------------------
# Get one renewal's details
# -------------------------------

@router.get("/renewals/{renewal_id}")
def get_renewal_endpoint(renewal_id: str):
    try:
        return get_renewal(renewal_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )


# -------------------------------
# Expire unanswered renewal offers
# -------------------------------

@router.post("/renewals/expire")
def expire_renewals_endpoint():
    try:
        return expire_renewal_offers()

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )
