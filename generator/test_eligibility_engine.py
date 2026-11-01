
from datetime import date

from generator.eligibility_engine import assess_eligibility


product = {
    "product_id": "PRD-2026-000001",
    "product_line": "MOTOR",
    "is_active": True,
    "effective_from": date(2026, 1, 1),
    "effective_to": date(2027, 12, 31),
    "min_asset_value": 50000,
    "max_asset_value": 10000000,
    "min_asset_age_years": 0,
    "max_asset_age_years": 20,
}

asset = {
    "asset_type": "VEHICLE",
    "asset_value": 600000,
    "purchase_date": date(2021, 1, 1),
}

coverages = [
    {
        "product_id": "PRD-2026-000001",
        "coverage_option_id": "COV-2026-000001",
        "coverage_limit": 500000,
        "min_limit": 10000,
        "max_limit": 8000000,
    }
]

result = assess_eligibility(
    product=product,
    asset=asset,
    selected_coverages=coverages,
    requested_start_date=date(2026, 11, 1),
    reference_date=date(2026, 10, 30),
)

print("Eligibility:", result.status)

for reason in result.reasons:
    print("-", reason)

assert result.is_eligible is True

print("\nEligibility engine test passed!")
