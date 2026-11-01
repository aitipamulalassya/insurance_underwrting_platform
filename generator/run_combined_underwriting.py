
from datetime import date

from generator.run_underwriting import (
    get_connection,
    load_product_rules,
    load_observations,
    save_factor_assessments,
    save_decision,
    calculate_age,
    RULESET_VERSION,
)

from generator.risk_engine import assess_quote
from generator.eligibility_engine import assess_eligibility
from generator.underwriting_orchestrator import (
    make_underwriting_decision,
)


REFERENCE_DATE = date(2026, 10, 30)
BATCH_SIZE = 200


def load_quote_bundles(conn):
    query = """
        SELECT
            q.quote_id,
            q.product_id,
            q.requested_start_date,

            a.date_of_birth,

            ia.asset_type,
            ia.asset_value,
            ia.purchase_date,

            p.product_id AS selected_product_id,
            p.product_line,
            p.min_asset_value,
            p.max_asset_value,
            p.min_asset_age_years,
            p.max_asset_age_years,
            p.is_active,
            p.effective_from,
            p.effective_to

        FROM quotes q

        JOIN applicants a
            ON a.applicant_id = q.applicant_id

        JOIN insured_assets ia
            ON ia.asset_id = q.asset_id

        JOIN products p
            ON p.product_id = q.product_id

        ORDER BY q.quote_id;
    """

    return conn.execute(query).fetchall()



def load_selected_coverages(conn, quote_id):
    query = """
        SELECT
            co.coverage_option_id,
            co.product_id,
            co.min_limit,
            co.max_limit,
            co.effective_from,
            co.effective_to,
            qc.selected_limit AS coverage_limit

        FROM quote_coverages qc

        JOIN coverage_options co
            ON co.coverage_option_id = qc.coverage_option_id

        WHERE qc.quote_id = %s;
    """

    return conn.execute(query, (quote_id,)).fetchall()

def run():
    counts = {
        "processed": 0,
        "approve": 0,
        "refer": 0,
        "decline": 0,
        "eligible": 0,
        "ineligible": 0,
    }

    rules_cache = {}

    with get_connection() as conn:

        quotes = load_quote_bundles(conn)

        print("Starting combined underwriting...")
        print("Quotes found:", len(quotes))

        for index, quote in enumerate(quotes, start=1):

            quote_id = quote["quote_id"]
            product_id = quote["product_id"]

            # --------------------------------
            # 1. Load product risk rules
            # --------------------------------

            if product_id not in rules_cache:
                rules_cache[product_id] = load_product_rules(
                    conn,
                    product_id,
                )

            rules = rules_cache[product_id]

            # --------------------------------
            # 2. Load risk observations
            # --------------------------------

            observations = load_observations(
                conn,
                quote_id,
            )

            observations["APPLICANT_AGE"] = calculate_age(
                quote["date_of_birth"],
                REFERENCE_DATE,
            )

            observations["ASSET_AGE"] = calculate_age(
                quote["purchase_date"],
                REFERENCE_DATE,
            )

            # --------------------------------
            # 3. Run risk engine
            # --------------------------------

            risk_result = assess_quote(
                product_risk_rules=rules,
                observed_values=observations,
                asset_age_limit=quote["max_asset_age_years"],
            )

            # Preserve calculated factor assessments.
            save_factor_assessments(
                conn,
                quote_id,
                risk_result.factor_assessments,
            )

            # --------------------------------
            # 4. Prepare product information
            # --------------------------------

            product = {
                "product_id": quote["selected_product_id"],
                "product_line": quote["product_line"],
                "min_asset_value": quote["min_asset_value"],
                "max_asset_value": quote["max_asset_value"],
                "min_asset_age_years": quote["min_asset_age_years"],
                "max_asset_age_years": quote["max_asset_age_years"],
                "is_active": quote["is_active"],
                "effective_from": quote["effective_from"],
                "effective_to": quote["effective_to"],
            }

            asset = {
                "asset_type": quote["asset_type"],
                "asset_value": quote["asset_value"],
                "purchase_date": quote["purchase_date"],
            }

            coverages = load_selected_coverages(
                conn,
                quote_id,
            )

            # --------------------------------
            # 5. Run eligibility engine
            # --------------------------------

            eligibility_result = assess_eligibility(
                product=product,
                asset=asset,
                selected_coverages=coverages,
                requested_start_date=quote["requested_start_date"],
                reference_date=REFERENCE_DATE,
            )

            # --------------------------------
            # 6. Combine both results
            # --------------------------------

            combined_result = make_underwriting_decision(
                eligibility=eligibility_result,
                risk=risk_result,
            )

            # --------------------------------
            # 7. Save combined decision
            # --------------------------------

            save_decision(
                conn,
                quote_id,
                combined_result,
            )

            # --------------------------------
            # 8. Update counters
            # --------------------------------

            counts["processed"] += 1
            counts[combined_result.decision_type.lower()] += 1
            counts[combined_result.eligibility_status.lower()] += 1

            if index % BATCH_SIZE == 0:
                print(
                    f"Processed {index}/{len(quotes)} quotes..."
                )

        print("\nCombined underwriting completed!")

        for key, value in counts.items():
            print(f"{key.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    run()
