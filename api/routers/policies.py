
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.database import get_connection
from api.services.policy_service import issue_policy

router = APIRouter()


# -------------------------------
# Request schema
# -------------------------------

class PolicyIssueRequest(BaseModel):
    issued_by: str = Field(
        min_length=1,
        max_length=100
    )


# -------------------------------
# Issue policy
# -------------------------------

@router.post("/quotes/{quote_id}/issue-policy", status_code=201)
def issue_policy_endpoint(
    quote_id: str,
    payload: PolicyIssueRequest
):
    try:
        return issue_policy(
            quote_id=quote_id,
            issued_by=payload.issued_by
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# -------------------------------
# Get policy audit history
# -------------------------------

@router.get("/policies/{policy_id}/audit-history")
def get_policy_audit_history(policy_id: str):
    """
    Retrieve the complete event history of a policy.

    Includes:
    - Policy issuance
    - Policy renewal
    - Endorsement approval
    - Endorsement payment confirmation
    - Endorsement activation
    """

    with get_connection() as conn:
        with conn.cursor() as cur:

            # 1. Verify policy exists.
            cur.execute(
                """
                SELECT *
                FROM policies
                WHERE policy_id = %s
                """,
                (policy_id,)
            )

            policy = cur.fetchone()

            if not policy:
                raise HTTPException(
                    status_code=404,
                    detail="Policy not found"
                )

            # 2. Retrieve all policy events.
            cur.execute(
                """
                SELECT *
                FROM policy_events
                WHERE policy_id = %s
                ORDER BY event_at ASC, policy_event_id ASC
                """,
                (policy_id,)
            )

            events = cur.fetchall()

    # 3. Build chronological timeline.
    timeline = []

    for event in events:
        timeline.append({
            "policy_event_id": event["policy_event_id"],
            "event_type": event["event_type"],
            "previous_status": event["previous_status"],
            "new_status": event["new_status"],
            "event_at": event["event_at"],
            "actor_reference": event["actor_reference"],
            "event_reason": event["event_reason"],
            "event_details": event["event_details"]
        })

    return {
        "policy_id": policy_id,
        "policy_status": policy["policy_status"],
        "policy_start_date": policy["policy_start_date"],
        "policy_end_date": policy["policy_end_date"],
        "total_events": len(events),
        "audit_timeline": timeline
    }
