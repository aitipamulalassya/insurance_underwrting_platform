
from generator.risk_engine import assess_quote


rules = [
    {
        "factor_code": "CLAIM_COUNT_3Y",
        "factor_weight": 1.0,
        "is_required": True,
        "missing_data_action": "REFER",
        "low_risk_threshold": 30,
        "high_risk_threshold": 70,
    },
    {
        "factor_code": "LOCATION_RISK",
        "factor_weight": 1.0,
        "is_required": True,
        "missing_data_action": "REFER",
        "low_risk_threshold": 30,
        "high_risk_threshold": 70,
    },
    {
        "factor_code": "APPLICANT_AGE",
        "factor_weight": 0.5,
        "is_required": True,
        "missing_data_action": "REFER",
        "low_risk_threshold": 30,
        "high_risk_threshold": 70,
    },
]

observations = {
    "CLAIM_COUNT_3Y": 0,
    "LOCATION_RISK": 20,
    "APPLICANT_AGE": 30,
}

result = assess_quote(rules, observations)

print("Risk score:", result.risk_score)
print("Risk category:", result.risk_category)
print("Decision:", result.decision_type)
print("Reason:", result.decision_reason)

print("\nFactor details:")

for factor in result.factor_assessments:
    print(
        factor.factor_code,
        factor.normalized_score,
        factor.factor_weight,
        factor.weighted_score,
    )
