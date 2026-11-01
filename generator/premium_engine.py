
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


RULESET_VERSION = "1.0.0"
RISK_LOADING_FACTOR = Decimal("0.50")


@dataclass
class PremiumResult:
    coverage_amount: Decimal
    base_rate: Decimal
    base_premium: Decimal
    risk_score: Decimal
    risk_loading: Decimal
    final_premium: Decimal
    currency: str = "INR"


def calculate_premium(
    coverage_amount,
    base_rate,
    risk_score,
):
    """
    Calculate premium using product base rate
    and underwriting risk score.
    """

    coverage = Decimal(str(coverage_amount))
    rate = Decimal(str(base_rate))

    if coverage <= 0:
        raise ValueError("Coverage amount must be positive")

    if rate <= 0:
        raise ValueError("Product base rate must be positive")

    if risk_score is None:
        raise ValueError(
            "Cannot calculate risk-adjusted premium without a risk score"
        )

    score = Decimal(str(risk_score))

    if not Decimal("0") <= score <= Decimal("100"):
        raise ValueError("Risk score must be between 0 and 100")

    base_premium = coverage * rate

    risk_loading = (
        Decimal("1")
        + (score / Decimal("100")) * RISK_LOADING_FACTOR
    )

    final_premium = base_premium * risk_loading

    return PremiumResult(
        coverage_amount=coverage,
        base_rate=rate,
        base_premium=base_premium.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        risk_score=score,
        risk_loading=risk_loading.quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        ),
        final_premium=final_premium.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
    )
