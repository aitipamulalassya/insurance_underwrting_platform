from typing import Literal
from pydantic import BaseModel, Field


class HumanReviewRequest(BaseModel):
    decision_type: Literal["APPROVE", "REFER", "DECLINE"]
    reviewer_reference: str = Field(min_length=2, max_length=100)
    approval_authority: str = Field(min_length=2, max_length=100)
    decision_reason: str = Field(min_length=10, max_length=2000)