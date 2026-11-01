
from dataclasses import dataclass
from typing import Any


RULESET_VERSION = "1.0.0"


@dataclass
class FactorAssessment:
    factor_code: str
    observed_value: Any
    normalized_score: float | None
    factor_weight: float
    weighted_score: float | None
    explanation: str


@dataclass
class RiskAssessment:
    risk_score: float | None
    risk_category: str
    decision_type: str
    decision_reason: str
    factor_assessments: list[FactorAssessment]
    ruleset_version: str = RULESET_VERSION


# --------------------------------------------------
# 1. Convert raw factor values into scores from 0-100
# --------------------------------------------------

def normalize_factor(
    factor_code: str,
    value: Any,
    asset_age_limit: int = 20,
) -> tuple[float, str]:

    if value is None:
        raise ValueError(f"Missing value for {factor_code}")

    if factor_code == "CLAIM_COUNT_3Y":
        claims = int(value)

        if claims < 0:
            raise ValueError("Claim count cannot be negative")

        score = min(claims * 25, 100)
        return float(score), f"{claims} claims in previous 3 years"

    if factor_code == "ASSET_AGE":
        age = float(value)

        if age < 0:
            raise ValueError("Asset age cannot be negative")

        score = min((age / max(asset_age_limit, 1)) * 100, 100)
        return score, f"Asset age is {age} years"

    if factor_code == "ASSET_VALUE":
        asset_value = float(value)

        if asset_value <= 0:
            raise ValueError("Asset value must be positive")

        # Synthetic assumption: higher insured value receives
        # a higher exposure score. This is not a real-world
        # actuarial risk relationship.
        score = min((asset_value / 10_000_000) * 100, 100)
        return score, f"Insured asset value is INR {asset_value:.2f}"

    if factor_code == "LOCATION_RISK":
        score = float(value)

        if not 0 <= score <= 100:
            raise ValueError("Location risk must be between 0 and 100")

        return score, f"Location risk score is {score}"

    if factor_code == "SAFETY_FEATURES":
        has_safety = str(value).strip().lower() in {
            "true", "yes", "1"
        }

        score = 20.0 if has_safety else 80.0
        return score, (
            "Required safety features are present"
            if has_safety
            else "Required safety features are absent"
        )

    if factor_code == "APPLICANT_AGE":
        age = int(value)

        if age < 18 or age > 120:
            raise ValueError("Applicant age is outside the supported range")

        if age < 25:
            score = 70.0
        elif age <= 60:
            score = 20.0
        else:
            score = 50.0

        return score, f"Applicant age is {age} years"

    if factor_code == "PROPERTY_SECURITY":
        security = str(value).strip().upper()

        security_scores = {
            "HIGH": 10.0,
            "MEDIUM": 40.0,
            "LOW": 80.0,
            "NONE": 100.0,
        }

        if security not in security_scores:
            raise ValueError(
                f"Unsupported property security category: {security}"
            )

        return (
            security_scores[security],
            f"Property security category is {security}",
        )

    raise ValueError(f"Unsupported risk factor: {factor_code}")


# --------------------------------------------------
# 2. Calculate weighted risk score
# --------------------------------------------------

def calculate_weighted_score(
    assessments: list[FactorAssessment],
) -> float:

    valid = [
        item for item in assessments
        if item.normalized_score is not None
    ]

    total_weight = sum(item.factor_weight for item in valid)

    if total_weight <= 0:
        raise ValueError("Total factor weight must be positive")

    total_weighted_score = sum(
        item.normalized_score * item.factor_weight
        for item in valid
    )

    return round(total_weighted_score / total_weight, 2)


# --------------------------------------------------
# 3. Classify risk using database thresholds
# --------------------------------------------------

def classify_risk(
    risk_score: float | None,
    low_threshold: float,
    high_threshold: float,
) -> str:

    if risk_score is None:
        return "UNKNOWN"

    if low_threshold >= high_threshold:
        raise ValueError("Low threshold must be below high threshold")

    if risk_score <= low_threshold:
        return "LOW"

    if risk_score <= high_threshold:
        return "MEDIUM"

    return "HIGH"


# --------------------------------------------------
# 4. Evaluate one quote's risk factors
# --------------------------------------------------

def assess_quote(
    product_risk_rules: list[dict],
    observed_values: dict[str, Any],
    asset_age_limit: int = 20,
) -> RiskAssessment:

    factor_assessments = []
    missing_required = []

    for rule in product_risk_rules:
        factor_code = rule["factor_code"]
        weight = float(rule["factor_weight"])

        is_required = bool(rule["is_required"])
        missing_action = rule["missing_data_action"].upper()

        low_threshold = float(rule["low_risk_threshold"])
        high_threshold = float(rule["high_risk_threshold"])

        value = observed_values.get(factor_code)

        if value is None:
            if is_required:
                missing_required.append(factor_code)

            factor_assessments.append(
                FactorAssessment(
                    factor_code=factor_code,
                    observed_value=None,
                    normalized_score=None,
                    factor_weight=weight,
                    weighted_score=None,
                    explanation=(
                        f"Missing factor. Configured action: {missing_action}"
                    ),
                )
            )
            continue

        score, explanation = normalize_factor(
            factor_code,
            value,
            asset_age_limit,
        )

        factor_assessments.append(
            FactorAssessment(
                factor_code=factor_code,
                observed_value=value,
                normalized_score=score,
                factor_weight=weight,
                weighted_score=round(score * weight, 4),
                explanation=explanation,
            )
        )

    if missing_required:
        return RiskAssessment(
            risk_score=None,
            risk_category="UNKNOWN",
            decision_type="REFER",
            decision_reason=(
                "Required risk information is missing: "
                + ", ".join(missing_required)
            ),
            factor_assessments=factor_assessments,
        )

    risk_score = calculate_weighted_score(factor_assessments)

    # The product mapping thresholds define risk categories.
    # They do not independently define approval authority.
    first_rule = product_risk_rules[0]

    category = classify_risk(
        risk_score,
        float(first_rule["low_risk_threshold"]),
        float(first_rule["high_risk_threshold"]),
    )

    # Conservative initial policy:
    # low risk -> approve recommendation
    # medium/high risk -> manual review
    # Eligibility and authority rules will be evaluated separately.
    decision_type = "APPROVE" if category == "LOW" else "REFER"

    reason = (
        f"Weighted risk score: {risk_score:.2f}. "
        f"Risk category: {category}. "
        f"Decision recommendation: {decision_type}."
    )

    return RiskAssessment(
        risk_score=risk_score,
        risk_category=category,
        decision_type=decision_type,
        decision_reason=reason,
        factor_assessments=factor_assessments,
    )
