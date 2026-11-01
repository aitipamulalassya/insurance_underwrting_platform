
from fastapi import APIRouter, HTTPException

from api.services.endorsement_activation_service import (
    activate_endorsement
)

router = APIRouter()


@router.post(
    "/endorsements/{endorsement_id}/activate"
)
def activate_endorsement_endpoint(endorsement_id: str):

    try:
        return activate_endorsement(endorsement_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )