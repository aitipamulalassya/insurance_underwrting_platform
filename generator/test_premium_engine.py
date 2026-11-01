
from generator.premium_engine import calculate_premium


result = calculate_premium(
    coverage_amount=1_000_000,
    base_rate=0.025,
    risk_score=40,
)

print("Coverage amount:", result.coverage_amount)
print("Base rate:", result.base_rate)
print("Base premium:", result.base_premium)
print("Risk score:", result.risk_score)
print("Risk loading:", result.risk_loading)
print("Final premium:", result.final_premium)

assert result.base_premium == 25000
assert result.final_premium == 30000

print("\nPremium engine test passed!")
