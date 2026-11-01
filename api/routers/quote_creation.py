
from fastapi import APIRouter, HTTPException

from api.schemas import QuoteCreateRequest
from api.services.quote_service import create_quote

router = APIRouter()


@router.post("/quotes", status_code=201)
def create_quote_endpoint(payload: QuoteCreateRequest):
    try:
        return create_quote(payload)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )
