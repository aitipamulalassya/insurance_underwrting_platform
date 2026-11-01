
import random
import csv
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

from generator.run_underwriting import get_connection


SEED = 20261022
random.seed(SEED)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "quotes"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():

    with get_connection() as conn:

        quotes = conn.execute("""
            SELECT
                quote_id,
                product_id,
                requested_coverage_amount,
                calculated_premium
            FROM quotes
            ORDER BY quote_id;
        """).fetchall()

        coverage_options = conn.execute("""
            SELECT
                coverage_option_id,
                product_id,
                min_limit,
                max_limit,
                is_mandatory
            FROM coverage_options
            ORDER BY coverage_option_id;
        """).fetchall()

    coverages_by_product = {}

    for coverage in coverage_options:
        coverages_by_product.setdefault(
            coverage["product_id"], []
        ).append(coverage)

    output_rows = []

    for quote in quotes:

        product_coverages = coverages_by_product.get(
            quote["product_id"], []
        )

        if not product_coverages:
            raise ValueError(
                f"No coverage options for {quote['product_id']}"
            )

        mandatory = [
            c for c in product_coverages
            if c["is_mandatory"]
        ]

        optional = [
            c for c in product_coverages
            if not c["is_mandatory"]
        ]

        selected = mandatory.copy()

        if optional:
            selected.extend(
                random.sample(
                    optional,
                    k=random.randint(0, len(optional))
                )
            )

        requested_amount = Decimal(
            str(quote["requested_coverage_amount"])
        )

        selected_data = []

        for coverage in selected:

            minimum = Decimal(str(coverage["min_limit"]))
            maximum = Decimal(str(coverage["max_limit"]))

            limit = max(
                minimum,
                min(requested_amount, maximum)
            )

            selected_data.append((coverage, limit))

        total_limit = sum(
            limit for _, limit in selected_data
        )

        total_premium = Decimal(
            str(quote["calculated_premium"])
        )

        remaining_premium = total_premium

        for index, (coverage, limit) in enumerate(selected_data):

            if index == len(selected_data) - 1:
                allocated_premium = remaining_premium
            else:
                allocated_premium = (
                    total_premium * limit / total_limit
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

                remaining_premium -= allocated_premium

            output_rows.append({
                "quote_id": quote["quote_id"],
                "coverage_option_id": coverage["coverage_option_id"],
                "selected_limit": str(limit),
                "coverage_premium": str(allocated_premium),
            })

    output_file = OUTPUT_DIR / "quote_coverages.csv"

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "quote_id",
                "coverage_option_id",
                "selected_limit",
                "coverage_premium",
            ]
        )

        writer.writeheader()
        writer.writerows(output_rows)

    print("Database-based coverage generation complete!")
    print("Quotes:", len(quotes))
    print("Coverage links:", len(output_rows))
    print("Output:", output_file)


if __name__ == "__main__":
    main()
