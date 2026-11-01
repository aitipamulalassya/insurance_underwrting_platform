from fastapi import APIRouter, HTTPException

from api.schemas import EndorsementDecisionRequest
from api.services.endorsement_review_service import review_endorsement

router = APIRouter()


@router.post("/endorsements/{endorsement_id}/decision")
def review_endorsement_endpoint(
    endorsement_id: str,
    payload: EndorsementDecisionRequest
):
    try:
        return review_endorsement(
            endorsement_id=endorsement_id,
            decision=payload.decision,
            reviewer_reference=payload.reviewer_reference,
            decision_reason=payload.decision_reason
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )