
import csv
import random
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP


SEED = 20261022

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "master"
QUOTE_DIR = BASE_DIR / "data" / "quotes"

random.seed(SEED)


def read_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def main():
    quotes = read_csv(QUOTE_DIR / "quotes.csv")
    coverage_options = read_csv(DATA_DIR / "coverage_options.csv")

    # Group coverage options by their actual product.
    coverages_by_product = {}

    for coverage in coverage_options:
        product_id = coverage["product_id"]
        coverages_by_product.setdefault(product_id, []).append(coverage)

    output_rows = []

    for quote in quotes:
        quote_id = quote["quote_id"]
        product_id = quote["product_id"]

        product_coverages = coverages_by_product.get(product_id, [])

        if not product_coverages:
            raise ValueError(
                f"No coverage options found for product {product_id}"
            )

        mandatory = [
            c for c in product_coverages
            if c["is_mandatory"].lower() == "true"
        ]

        optional = [
            c for c in product_coverages
            if c["is_mandatory"].lower() == "false"
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
            quote["requested_coverage_amount"]
        )

        # Respect each coverage option's own limits.
        selected_limits = []

        for coverage in selected:
            minimum = Decimal(coverage["min_limit"])
            maximum = Decimal(coverage["max_limit"])

            selected_limit = max(
                minimum,
                min(requested_amount, maximum)
            )

            selected_limits.append(selected_limit)

        total_limit = sum(selected_limits)

        total_premium = Decimal(quote["calculated_premium"])
        remaining_premium = total_premium

        for index, (coverage, limit) in enumerate(
            zip(selected, selected_limits)
        ):
            if index == len(selected) - 1:
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
                "quote_id": quote_id,
                "coverage_option_id": coverage["coverage_option_id"],
                "selected_limit": str(limit),
                "coverage_premium": str(allocated_premium),
            })

    output_path = QUOTE_DIR / "quote_coverages.csv"

    with open(
        output_path,
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
            ],
        )

        writer.writeheader()
        writer.writerows(output_rows)

    print("Coverage mapping repaired!")
    print("Quotes processed:", len(quotes))
    print("Coverage links generated:", len(output_rows))
    print("Output:", output_path)


if __name__ == "__main__":
    main()
