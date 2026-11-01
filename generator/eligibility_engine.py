
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class EligibilityResult:
    is_eligible: bool
    status: str
    reasons: list[str] = field(default_factory=list)


def to_decimal(value):
    return Decimal(str(value))


def to_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def check_asset_product_compatibility(asset_type, product_line):
    """
    Check whether an asset type matches a product line.
    """

    compatibility = {
        "VEHICLE": "MOTOR",
        "HOME": "HOME",
        "COMMERCIAL_PROPERTY": "BUSINESS",
    }

    expected_line = compatibility.get(
        str(asset_type).upper()
    )

    if expected_line is None:
        return False

    return expected_line in str(product_line).upper()


def assess_eligibility(
    product: dict[str, Any],
    asset: dict[str, Any],
    selected_coverages: list[dict[str, Any]],
    requested_start_date: date,
    reference_date: date | None = None,
) -> EligibilityResult:

    if reference_date is None:
        reference_date = date.today()

    reasons = []

    # 1. Product active status
    if not product["is_active"]:
        reasons.append("Insurance product is inactive")

    # 2. Product effective dates
    effective_from = to_date(product["effective_from"])

    effective_to = product.get("effective_to")

    if effective_to is not None:
        effective_to = to_date(effective_to)

    if requested_start_date < effective_from:
        reasons.append(
            "Requested coverage starts before product effective date"
        )

    if effective_to and requested_start_date > effective_to:
        reasons.append(
            "Requested coverage starts after product expiry date"
        )

    # 3. Product and asset compatibility
    if not check_asset_product_compatibility(
        asset["asset_type"],
        product["product_line"],
    ):
        reasons.append(
            "Insured asset type is incompatible with the product"
        )

    # 4. Asset value eligibility
    asset_value = to_decimal(asset["asset_value"])

    min_asset_value = to_decimal(product["min_asset_value"])
    max_asset_value = to_decimal(product["max_asset_value"])

    if not min_asset_value <= asset_value <= max_asset_value:
        reasons.append(
            f"Asset value {asset_value} is outside product limits "
            f"({min_asset_value} - {max_asset_value})"
        )

    # 5. Asset age eligibility
    purchase_date = to_date(asset["purchase_date"])

    asset_age = (
        reference_date.year
        - purchase_date.year
        - (
            (reference_date.month, reference_date.day)
            < (purchase_date.month, purchase_date.day)
        )
    )

    min_asset_age = int(product["min_asset_age_years"])
    max_asset_age = int(product["max_asset_age_years"])

    if not min_asset_age <= asset_age <= max_asset_age:
        reasons.append(
            f"Asset age {asset_age} years is outside product limits "
            f"({min_asset_age} - {max_asset_age} years)"
        )

    # 6. Coverage validation
    if not selected_coverages:
        reasons.append("No coverage options selected")

    for coverage in selected_coverages:

        coverage_product_id = coverage.get("product_id")

        if (
            coverage_product_id is not None
            and coverage_product_id != product["product_id"]
        ):
            reasons.append(
                f"Coverage {coverage['coverage_option_id']} "
                "does not belong to the selected product"
            )
            continue

        coverage_limit = to_decimal(coverage["coverage_limit"])

        min_limit = to_decimal(coverage["min_limit"])
        max_limit = to_decimal(coverage["max_limit"])

        if not min_limit <= coverage_limit <= max_limit:
            reasons.append(
                f"Coverage {coverage['coverage_option_id']} limit "
                f"{coverage_limit} is outside permitted limits "
                f"({min_limit} - {max_limit})"
            )

    if reasons:
        return EligibilityResult(
            is_eligible=False,
            status="INELIGIBLE",
            reasons=reasons,
        )

    return EligibilityResult(
        is_eligible=True,
        status="ELIGIBLE",
        reasons=["All product and coverage eligibility checks passed"],
    )
