
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator
   

class CoverageSelection(BaseModel):
    coverage_option_id: str = Field(min_length=1)
    selected_limit: Decimal = Field(gt=0)


class QuoteCreateRequest(BaseModel):
    applicant_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)

    requested_start_date: date
    requested_end_date: date

    coverages: list[CoverageSelection] = Field(min_length=1)

    risk_observations: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_policy_dates(self):
        if self.requested_end_date <= self.requested_start_date:
            raise ValueError(
                "Policy end date must be after start date"
            )

        return self

class QuoteAcceptanceRequest(BaseModel):
    customer_reference: str | None = Field(
        default=None,
        max_length=100
    )
class PaymentCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_reference: str | None = Field(
        default=None,
        max_length=255
    )
 


class EndorsementCreateRequest(BaseModel):
    coverage_option_id: str = Field(min_length=1, max_length=50)

    new_selected_limit: Decimal = Field(gt=0)

    effective_date: date

    request_reason: str = Field(
        min_length=10,
        max_length=1000
    )
class EndorsementDecisionRequest(BaseModel):
    decision: str = Field(min_length=1)
    reviewer_reference: str = Field(
        min_length=1,
        max_length=100
    )
    decision_reason: str = Field(
        min_length=10,
        max_length=1000
    )

    @model_validator(mode="after")
    def validate_decision(self):
        self.decision = self.decision.upper()

        if self.decision not in ("APPROVE", "REJECT"):
            raise ValueError(
                "Decision must be APPROVE or REJECT."
            )

        return self