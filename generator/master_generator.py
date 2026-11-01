import csv
import random
from datetime import date, datetime
from pathlib import Path

from faker import Faker

from generator.config import (
    SEED, REFERENCE_DATE, OUTPUT_DIR, APPLICANT_COUNT, ASSET_COUNT,
    PRODUCTS, COVERAGES, RISK_FACTORS
)

fake = Faker("en_IN")
Faker.seed(SEED)
random.seed(SEED)
REFERENCE = date.fromisoformat(REFERENCE_DATE)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def applicant_rows():
    rows = []

    for n in range(1, APPLICANT_COUNT + 1):
        dob = fake.date_of_birth(
            minimum_age=21,
            maximum_age=75
        )

        rows.append({
            "applicant_id": f"APP-2026-{n:06d}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "date_of_birth": dob.isoformat(),
            "email": f"applicant{n:06d}@example.test",
            "phone": f"+91{random.randint(6000000000, 9999999999)}",
            "address_line": fake.street_address(),
            "city": fake.city(),
            "state": fake.state(),
            "postal_code": fake.postcode(),
            "applicant_status": "ACTIVE" if random.random() < 0.96 else "INACTIVE",
            "created_at": "2026-10-01T09:00:00+05:30",
        })

    return rows
def asset_rows(applicants):
    rows = []
    for n in range(1, ASSET_COUNT + 1):
        owner = applicants[n - 1]
        kind = ["VEHICLE", "HOME", "COMMERCIAL_PROPERTY"][(n - 1) % 3]
        if kind == "VEHICLE":
            value = round(random.uniform(300000, 6000000), 2)
            desc = random.choice(["Hatchback", "Sedan", "SUV", "Motorcycle"])
            reg = f"TS{random.randint(1, 99):02d}AB{n:04d}"
        elif kind == "HOME":
            value = round(random.uniform(1500000, 80000000), 2)
            desc = random.choice(["Apartment", "Independent house", "Villa"])
            reg = f"HOME-{n:06d}"
        else:
            value = round(random.uniform(3000000, 250000000), 2)
            desc = random.choice(["Office building", "Warehouse", "Retail premises"])
            reg = f"BIZ-{n:06d}"
        purchase_year = random.randint(2005, 2025)
        purchase_date = date(purchase_year, random.randint(1, 12), random.randint(1, 28))
        rows.append({
            "asset_id": f"AST-2026-{n:06d}",
            "applicant_id": owner["applicant_id"],
            "asset_type": kind,
            "asset_description": desc,
            "asset_value": f"{value:.2f}",
            "purchase_date": purchase_date.isoformat(),
            "registration_number": reg,
            "location_city": owner["city"],
            "location_state": owner["state"],
            "asset_status": "ACTIVE",
            "created_at": "2026-10-01T09:00:00+05:30",
        })
    return rows


def main():
    out = Path(OUTPUT_DIR)
    applicants = applicant_rows()
    assets = asset_rows(applicants)

    product_fields = list(PRODUCTS[0].keys()) + ["is_active", "effective_from", "effective_to"]
    products = [
        {**p, "is_active": True, "effective_from": "2026-01-01", "effective_to": ""}
        for p in PRODUCTS
    ]

    coverage_fields = [
        "coverage_option_id", "product_id", "coverage_code", "coverage_name",
        "description", "min_limit", "max_limit", "is_mandatory",
        "effective_from", "effective_to"
    ]
    coverages = [{
        "coverage_option_id": c[0], "product_id": c[1], "coverage_code": c[2],
        "coverage_name": c[3], "description": c[4], "min_limit": f"{c[5]:.2f}",
        "max_limit": f"{c[6]:.2f}", "is_mandatory": c[7],
        "effective_from": "2026-01-01", "effective_to": ""
    } for c in COVERAGES]

    risk_fields = [
        "risk_factor_id", "factor_code", "factor_name", "description",
        "factor_category", "data_type", "is_required", "effective_from", "effective_to"
    ]
    risks = [{
        "risk_factor_id": r[0], "factor_code": r[1], "factor_name": r[2],
        "description": r[3], "factor_category": r[4], "data_type": r[5],
        "is_required": r[6], "effective_from": "2026-01-01", "effective_to": ""
    } for r in RISK_FACTORS]

    mapping_rows = []
    for product in PRODUCTS:
        for risk in RISK_FACTORS:
            # Product-specific factors: all products use claims, asset age/value, location;
            # vehicle adds safety features, property products add property security.
            if risk[1] in {"CLAIM_COUNT_3Y", "ASSET_AGE", "ASSET_VALUE", "LOCATION_RISK", "APPLICANT_AGE"}:
                weight = 1.0 if risk[1] in {"CLAIM_COUNT_3Y", "LOCATION_RISK"} else 0.5
            elif product["product_line"] == "MOTOR" and risk[1] == "SAFETY_FEATURES":
                weight = 0.7
            elif product["product_line"] in {"HOME", "BUSINESS"} and risk[1] == "PROPERTY_SECURITY":
                weight = 0.7
            else:
                continue
            mapping_rows.append({
                "product_id": product["product_id"],
                "risk_factor_id": risk[0],
                "factor_weight": f"{weight:.4f}",
                "low_risk_threshold": "30.0000",
                "high_risk_threshold": "70.0000",
                "missing_data_action": "REFER",
                "effective_from": "2026-01-01",
                "effective_to": "",
            })

    write_csv(out / "applicants.csv", applicants, list(applicants[0].keys()))
    write_csv(out / "insured_assets.csv", assets, list(assets[0].keys()))
    write_csv(out / "products.csv", products, product_fields)
    write_csv(out / "coverage_options.csv", coverages, coverage_fields)
    write_csv(out / "risk_factors.csv", risks, risk_fields)
    write_csv(out / "product_risk_factors.csv", mapping_rows, list(mapping_rows[0].keys()))

    print("Master data generation complete.")
    print(f"Seed: {SEED}")
    print(f"Applicants: {len(applicants)}")
    print(f"Insured assets: {len(assets)}")
    print(f"Products: {len(products)}")
    print(f"Coverage options: {len(coverages)}")
    print(f"Risk factors: {len(risks)}")
    print(f"Product-risk mappings: {len(mapping_rows)}")
    print(f"Output: {out.resolve()}")


if __name__ == "__main__":
    main()
