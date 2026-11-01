
from dataclasses import dataclass

from generator.risk_engine import RiskAssessment
from generator.eligibility_engine import EligibilityResult


@dataclass
class UnderwritingResult:
    decision_type: str
    eligibility_status: str
    risk_category: str
    risk_score: float | None
    decision_reason: str
    is_final: bool = False


def make_underwriting_decision(
    eligibility: EligibilityResult,
    risk: RiskAssessment,
) -> UnderwritingResult:

    # Rule 1: Ineligible products cannot be approved.
    if not eligibility.is_eligible:
        return UnderwritingResult(
            decision_type="DECLINE",
            eligibility_status="INELIGIBLE",
            risk_category=risk.risk_category,
            risk_score=risk.risk_score,
            decision_reason=(
                "Eligibility requirements not satisfied: "
                + "; ".join(eligibility.reasons)
            ),
        )

    # Rule 2: Missing required risk information needs review.
    if risk.risk_category == "UNKNOWN":
        decision = "REFER"

    # Rule 3: Only eligible, low-risk quotes receive
    # an approval recommendation.
    elif risk.risk_category == "LOW":
        decision = "APPROVE"

    # Rule 4: Medium and high risk require manual review.
    else:
        decision = "REFER"

    reason = (
        f"Eligibility: {eligibility.status}. "
        f"Risk category: {risk.risk_category}. "
        f"Underwriting recommendation: {decision}. "
        f"Risk explanation: {risk.decision_reason}"
    )

    return UnderwritingResult(
        decision_type=decision,
        eligibility_status=eligibility.status,
        risk_category=risk.risk_category,
        risk_score=risk.risk_score,
        decision_reason=reason,
    )
