from fastapi import APIRouter, HTTPException

from api.schemas_review import HumanReviewRequest
from api.services.review_service import (
    get_review_queue,
    get_review_details,
    submit_human_decision
)

router = APIRouter()


@router.get("/underwriting/review-queue")
def review_queue_endpoint():
    try:
        return get_review_queue()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/underwriting/review-queue/{quote_id}")
def review_details_endpoint(quote_id: str):
    try:
        return get_review_details(quote_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/underwriting/review-queue/{quote_id}/decision")
def human_decision_endpoint(
    quote_id: str,
    payload: HumanReviewRequest
):
    try:
        return submit_human_decision(quote_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))