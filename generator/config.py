SEED = 20261022
REFERENCE_DATE = "2026-10-30"
OUTPUT_DIR = "data/master"
APPLICANT_COUNT = 3000
ASSET_COUNT = 3000

PRODUCTS = [
    {
        "product_id": "PRD-2026-000001",
        "product_code": "MOTOR-STD",
        "product_name": "Motor Insurance",
        "product_line": "MOTOR",
        "description": "Synthetic private motor insurance product.",
        "min_asset_value": "50000.00",
        "max_asset_value": "10000000.00",
        "min_asset_age_years": 0,
        "max_asset_age_years": 20,
        "base_rate": "0.025000",
    },
    {
        "product_id": "PRD-2026-000002",
        "product_code": "HOME-STD",
        "product_name": "Home Insurance",
        "product_line": "HOME",
        "description": "Synthetic residential property insurance product.",
        "min_asset_value": "500000.00",
        "max_asset_value": "100000000.00",
        "min_asset_age_years": 0,
        "max_asset_age_years": 80,
        "base_rate": "0.004000",
    },
    {
        "product_id": "PRD-2026-000003",
        "product_code": "BUSINESS-STD",
        "product_name": "Business Property Insurance",
        "product_line": "BUSINESS",
        "description": "Synthetic commercial property insurance product.",
        "min_asset_value": "1000000.00",
        "max_asset_value": "500000000.00",
        "min_asset_age_years": 0,
        "max_asset_age_years": 100,
        "base_rate": "0.006000",
    },
]

COVERAGES = [
    ("COV-2026-000001", "PRD-2026-000001", "OWN_DAMAGE", "Own Damage", "Damage to insured vehicle", 10000, 8000000, True),
    ("COV-2026-000002", "PRD-2026-000001", "THEFT", "Theft Protection", "Theft protection", 10000, 8000000, False),
    ("COV-2026-000003", "PRD-2026-000001", "THIRD_PARTY", "Third Party Liability", "Third party liability cover", 100000, 10000000, True),
    ("COV-2026-000004", "PRD-2026-000002", "FIRE", "Fire Protection", "Fire-related property damage", 100000, 80000000, True),
    ("COV-2026-000005", "PRD-2026-000002", "THEFT_HOME", "Home Theft Protection", "Theft of covered household property", 50000, 20000000, False),
    ("COV-2026-000006", "PRD-2026-000002", "STRUCTURE", "Building Structure", "Residential building structure cover", 100000, 100000000, True),
    ("COV-2026-000007", "PRD-2026-000003", "COMM_FIRE", "Commercial Fire", "Fire protection for commercial property", 500000, 400000000, True),
    ("COV-2026-000008", "PRD-2026-000003", "EQUIPMENT", "Equipment Protection", "Commercial equipment cover", 100000, 100000000, False),
    ("COV-2026-000009", "PRD-2026-000003", "BUSINESS_INTERRUPTION", "Business Interruption", "Synthetic business interruption cover", 100000, 150000000, False),
]

RISK_FACTORS = [
    ("RSK-2026-000001", "CLAIM_COUNT_3Y", "Claims in Previous 3 Years", "Number of claims reported in the previous three years.", "CLAIMS", "NUMERIC", True),
    ("RSK-2026-000002", "ASSET_AGE", "Asset Age", "Age of the insured asset in years.", "ASSET", "NUMERIC", True),
    ("RSK-2026-000003", "ASSET_VALUE", "Asset Value", "Declared value of the insured asset in INR.", "ASSET", "NUMERIC", True),
    ("RSK-2026-000004", "LOCATION_RISK", "Location Risk Score", "Synthetic location risk score from 0 to 100.", "LOCATION", "NUMERIC", True),
    ("RSK-2026-000005", "SAFETY_FEATURES", "Safety Features Present", "Whether required safety features are present.", "ASSET", "BOOLEAN", False),
    ("RSK-2026-000006", "APPLICANT_AGE", "Applicant Age", "Applicant age in completed years.", "APPLICANT", "NUMERIC", True),
    ("RSK-2026-000007", "PROPERTY_SECURITY", "Property Security", "Synthetic property security category.", "ASSET", "CATEGORICAL", False),
]
