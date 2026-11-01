from fastapi import APIRouter, HTTPException

from api.schemas import QuoteAcceptanceRequest
from api.services.acceptance_service import accept_quote

router = APIRouter()


@router.post("/quotes/{quote_id}/accept")
def accept_quote_endpoint(
    quote_id: str,
    payload: QuoteAcceptanceRequest
):
    try:
        return accept_quote(
            quote_id,
            payload.customer_reference
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )