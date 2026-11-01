
import csv
import random
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal

from generator.premium_engine import calculate_premium


SEED = 20261022
QUOTE_COUNT = 4000

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "master"
OUTPUT_DIR = BASE_DIR / "data" / "quotes"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

random.seed(SEED)


def read_csv(filename):
    with open(
        DATA_DIR / filename,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        return list(csv.DictReader(file))


def write_csv(filename, rows):
    if not rows:
        print(f"No records generated for {filename}")
        return

    with open(
        OUTPUT_DIR / filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)


def get_value(row, *names):
    for name in names:
        if name in row and row[name] not in ("", None):
            return row[name]

    raise KeyError(
        f"None of these columns were found: {names}. "
        f"Available columns: {list(row.keys())}"
    )


def match_product(asset_type, products):
    asset_type = asset_type.upper()

    if asset_type == "VEHICLE":
        target = "MOTOR"
    elif asset_type == "HOME":
        target = "HOME"
    elif asset_type == "COMMERCIAL_PROPERTY":
        target = "BUSINESS"
    else:
        raise ValueError(
            f"Unsupported asset type: {asset_type}"
        )

    matches = [
        p for p in products
        if target in get_value(
            p, "product_line", "product_code"
        ).upper()
    ]

    if not matches:
        raise ValueError(
            f"No product found for asset type {asset_type}"
        )

    return matches[0]


def main():
    applicants = read_csv("applicants.csv")
    assets = read_csv("insured_assets.csv")
    products = read_csv("products.csv")
    coverages = read_csv("coverage_options.csv")

    applicants_by_id = {
        get_value(a, "applicant_id"): a
        for a in applicants
    }

    quote_rows = []
    coverage_rows = []
    risk_observation_rows = []

    reference_date = date(2026, 10, 30)

    for number in range(1, QUOTE_COUNT + 1):

        asset = assets[(number - 1) % len(assets)]

        applicant_id = get_value(asset, "applicant_id")
        applicant = applicants_by_id[applicant_id]

        asset_id = get_value(asset, "asset_id")
        asset_type = get_value(asset, "asset_type").upper()

        asset_value = Decimal(
            get_value(asset, "asset_value", "insured_value")
        )

        product = match_product(asset_type, products)

        product_id = get_value(product, "product_id")
        base_rate = Decimal(get_value(product, "base_rate"))

        product_coverages = [
            c for c in coverages
            if get_value(c, "product_id") == product_id
        ]

        if not product_coverages:
            raise ValueError(
                f"No coverage options for {product_id}"
            )

        selected_coverages = [
            c for c in product_coverages
            if get_value(c, "is_mandatory").lower() == "true"
        ]

        optional_coverages = [
            c for c in product_coverages
            if get_value(c, "is_mandatory").lower() == "false"
        ]

        if optional_coverages:
            selected_coverages += random.sample(
                optional_coverages,
                k=random.randint(0, len(optional_coverages))
            )

        if not selected_coverages:
            raise ValueError(
                f"No valid coverage selected for {product_id}"
            )

        coverage_amount = asset_value

        # Temporary synthetic risk score.
        risk_score = Decimal(str(random.randint(0, 100)))

        if risk_score <= 30:
            quote_status = "APPROVED"
        else:
            quote_status = "REFERRED"

        premium = calculate_premium(
            coverage_amount=coverage_amount,
            base_rate=base_rate,
            risk_score=risk_score,
        )

        start_date = reference_date + timedelta(
            days=random.randint(1, 60)
        )

        end_date = start_date + timedelta(days=365)

        quote_id = f"QTE-2026-{number:06d}"

        quote_rows.append({
            "quote_id": quote_id,
            "applicant_id": applicant_id,
            "asset_id": asset_id,
            "product_id": product_id,
            "requested_start_date": start_date.isoformat(),
            "requested_end_date": end_date.isoformat(),
            "requested_coverage_amount": str(coverage_amount),
            "calculated_premium": str(premium.final_premium),
            "currency": "INR",
            "quote_status": quote_status,
            "applicant_accepted_at": "",
            "quote_valid_until": (
                start_date + timedelta(days=30)
            ).isoformat(),
            "created_at": reference_date.isoformat(),
        })

        # Allocate the total premium across selected coverages.
        # Currently each coverage receives an equal share because
        # each coverage uses the same coverage limit.

        coverage_limits = [
            coverage_amount for _ in selected_coverages
        ]

        total_limit = sum(coverage_limits)

        remaining_premium = premium.final_premium

        for index, (coverage, limit) in enumerate(
            zip(selected_coverages, coverage_limits)
        ):

            if index == len(selected_coverages) - 1:
                coverage_premium = remaining_premium

            else:
                coverage_premium = (
                    premium.final_premium
                    * limit
                    / total_limit
                ).quantize(Decimal("0.01"))

                remaining_premium -= coverage_premium

            coverage_rows.append({
                "quote_id": quote_id,
                "coverage_option_id": get_value(
                    coverage,
                    "coverage_option_id",
                    "coverage_id"
                ),
                "coverage_limit": str(limit),
                "coverage_premium": str(coverage_premium),
            })

        # Generate synthetic factor observations.
        risk_observation_rows.extend([
            {
                "quote_id": quote_id,
                "factor_code": "CLAIM_COUNT_3Y",
                "observed_value": str(random.randint(0, 3)),
            },
            {
                "quote_id": quote_id,
                "factor_code": "ASSET_VALUE",
                "observed_value": str(asset_value),
            },
            {
                "quote_id": quote_id,
                "factor_code": "LOCATION_RISK",
                "observed_value": str(random.randint(0, 100)),
            },
        ])

    write_csv("quotes.csv", quote_rows)
    write_csv("quote_coverages.csv", coverage_rows)
    write_csv("risk_observations.csv", risk_observation_rows)

    print("\nQuote generation completed!")
    print("Seed:", SEED)
    print("Quotes:", len(quote_rows))
    print("Quote coverage links:", len(coverage_rows))
    print("Risk observations:", len(risk_observation_rows))
    print("Output directory:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
