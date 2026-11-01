
from generator.eligibility_engine import EligibilityResult
from generator.risk_engine import RiskAssessment
from generator.underwriting_orchestrator import make_underwriting_decision


def create_risk(category, score, decision):
    return RiskAssessment(
        risk_score=score,
        risk_category=category,
        decision_type=decision,
        decision_reason=f"Test risk category: {category}",
        factor_assessments=[],
    )


eligible = EligibilityResult(
    is_eligible=True,
    status="ELIGIBLE",
    reasons=["All eligibility checks passed"],
)

ineligible = EligibilityResult(
    is_eligible=False,
    status="INELIGIBLE",
    reasons=["Asset value exceeds product maximum"],
)


test_cases = [
    (
        "Eligible + Low risk",
        eligible,
        create_risk("LOW", 20, "APPROVE"),
        "APPROVE",
    ),
    (
        "Eligible + Medium risk",
        eligible,
        create_risk("MEDIUM", 50, "REFER"),
        "REFER",
    ),
    (
        "Eligible + High risk",
        eligible,
        create_risk("HIGH", 85, "REFER"),
        "REFER",
    ),
    (
        "Ineligible + Low risk",
        ineligible,
        create_risk("LOW", 20, "APPROVE"),
        "DECLINE",
    ),
    (
        "Eligible + Unknown risk",
        eligible,
        create_risk("UNKNOWN", None, "REFER"),
        "REFER",
    ),
]


for name, eligibility, risk, expected in test_cases:
    result = make_underwriting_decision(
        eligibility,
        risk,
    )

    print(
        f"{name}: {result.decision_type}"
    )

    assert result.decision_type == expected


print("\nAll orchestrator tests passed!")
