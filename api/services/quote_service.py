
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from psycopg.types.json import Jsonb

from api.database import get_connection

from generator.premium_engine import calculate_premium
from generator.eligibility_engine import assess_eligibility
from generator.risk_engine import assess_quote
from generator.underwriting_orchestrator import (
    make_underwriting_decision,
)

from generator.run_underwriting import (
    calculate_age,
    load_product_rules,
    save_factor_assessments,
    save_decision,
)


def make_json_compatible(value):
    """Convert Python values into JSON-compatible values."""

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: make_json_compatible(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            make_json_compatible(item)
            for item in value
        ]

    return value

def create_quote(payload, renewal_id=None):
    today = date.today()

    with get_connection() as conn:

        # --------------------------------------------------
        # 1. Validate applicant
        # --------------------------------------------------
        if renewal_id is not None:
            renewal = conn.execute(
                """
                SELECT
                    r.renewal_id,
                    r.policy_id,
                    r.renewal_status,
                    r.proposed_start_date,
                    r.proposed_end_date,
                    p.applicant_id,
                    p.asset_id,
                    p.product_id
                FROM renewals r
                JOIN policies p
                    ON p.policy_id = r.policy_id
                WHERE r.renewal_id = %s
                FOR UPDATE OF r
                """,
                (renewal_id,)
            ).fetchone()

            if not renewal:
                raise ValueError("Renewal not found.")

            if renewal["renewal_status"] != "ACCEPTED":
                raise ValueError(
                    "Only ACCEPTED renewals can generate renewal quotes."
                )

            if (
                payload.requested_start_date
                != renewal["proposed_start_date"]
                or payload.requested_end_date
                != renewal["proposed_end_date"]
            ):
                raise ValueError(
                    "Quote dates must match the accepted renewal period."
                )

            if (
                payload.applicant_id != renewal["applicant_id"]
                or payload.asset_id != renewal["asset_id"]
                or payload.product_id != renewal["product_id"]
            ):
                raise ValueError(
                    "Renewal quote details must match the original policy."
                )

            existing_renewal_quote = conn.execute(
                """
                SELECT quote_id
                FROM quotes
                WHERE renewal_id = %s
                """,
                (renewal_id,)
            ).fetchone()

            if existing_renewal_quote:
                raise ValueError(
                    "A quote already exists for this renewal: "
                    f"{existing_renewal_quote['quote_id']}"
                )
        applicant = conn.execute(
            """
            SELECT *
            FROM applicants
            WHERE applicant_id = %s
            """,
            (payload.applicant_id,)
        ).fetchone()

        if not applicant:
            raise ValueError("Applicant not found")

        # --------------------------------------------------
        # 2. Validate asset ownership
        # --------------------------------------------------

        asset = conn.execute(
            """
            SELECT *
            FROM insured_assets
            WHERE asset_id = %s
              AND applicant_id = %s
            """,
            (payload.asset_id, payload.applicant_id)
        ).fetchone()

        if not asset:
            raise ValueError(
                "Asset not found or does not belong to applicant"
            )

        # --------------------------------------------------
        # 3. Validate product
        # --------------------------------------------------

        product = conn.execute(
            """
            SELECT *
            FROM products
            WHERE product_id = %s
            """,
            (payload.product_id,)
        ).fetchone()

        if not product:
            raise ValueError("Product not found")

        if not product["is_active"]:
            raise ValueError("Selected insurance product is inactive")

        if payload.requested_start_date < product["effective_from"]:
            raise ValueError(
                "Policy starts before product effective date"
            )

        if (
            product["effective_to"] is not None
            and payload.requested_end_date > product["effective_to"]
        ):
            raise ValueError(
                "Policy ends after product expiry date"
            )

        # --------------------------------------------------
        # 4. Load selected coverage options
        # --------------------------------------------------

        selected_coverages = []
        seen_ids = set()

        for selection in payload.coverages:

            coverage_id = selection.coverage_option_id

            if coverage_id in seen_ids:
                raise ValueError(
                    f"Duplicate coverage selected: {coverage_id}"
                )

            seen_ids.add(coverage_id)

            coverage = conn.execute(
                """
                SELECT *
                FROM coverage_options
                WHERE coverage_option_id = %s
                  AND product_id = %s
                """,
                (coverage_id, payload.product_id)
            ).fetchone()

            if not coverage:
                raise ValueError(
                    f"Coverage {coverage_id} "
                    "does not belong to the selected product"
                )

            if selection.selected_limit < coverage["min_limit"]:
                raise ValueError(
                    f"Coverage {coverage_id} is below minimum limit "
                    f"{coverage['min_limit']}"
                )

            if selection.selected_limit > coverage["max_limit"]:
                raise ValueError(
                    f"Coverage {coverage_id} exceeds maximum limit "
                    f"{coverage['max_limit']}"
                )

            if payload.requested_start_date < coverage["effective_from"]:
                raise ValueError(
                    f"Coverage {coverage_id} is not yet effective"
                )

            if (
                coverage["effective_to"] is not None
                and payload.requested_end_date > coverage["effective_to"]
            ):
                raise ValueError(
                    f"Coverage {coverage_id} expires "
                    "before the requested policy end date"
                )

            selected_coverages.append({
                **coverage,
                "coverage_limit": selection.selected_limit
            })

        # --------------------------------------------------
        # 5. Validate mandatory coverage selections
        # --------------------------------------------------

        mandatory_coverages = conn.execute(
            """
            SELECT coverage_option_id
            FROM coverage_options
            WHERE product_id = %s
              AND is_mandatory = TRUE
              AND effective_from <= %s
              AND (
                  effective_to IS NULL
                  OR effective_to >= %s
              )
            """,
            (
                payload.product_id,
                payload.requested_start_date,
                payload.requested_end_date
            )
        ).fetchall()

        selected_ids = {
            item["coverage_option_id"]
            for item in selected_coverages
        }

        missing_coverages = [
            item["coverage_option_id"]
            for item in mandatory_coverages
            if item["coverage_option_id"] not in selected_ids
        ]

        if missing_coverages:
            raise ValueError(
                "Mandatory coverage options missing: "
                + ", ".join(missing_coverages)
            )

        # --------------------------------------------------
        # 6. Run eligibility engine
        # --------------------------------------------------

        eligibility = assess_eligibility(
            product=dict(product),
            asset=dict(asset),
            selected_coverages=selected_coverages,
            requested_start_date=payload.requested_start_date,
            reference_date=today
        )

        # --------------------------------------------------
        # 7. Load product risk rules
        # --------------------------------------------------

        rules = load_product_rules(conn, payload.product_id)

        if not rules:
            raise ValueError(
                "No risk rules configured for selected product"
            )

        # --------------------------------------------------
        # 8. Prepare risk observations
        # --------------------------------------------------

        observations = dict(payload.risk_observations)

        derived_factors = {
            "APPLICANT_AGE",
            "ASSET_AGE",
            "ASSET_VALUE"
        }

        supplied_factors = set(observations)

        available_factors = supplied_factors | derived_factors

        missing_factors = [
            rule["factor_code"]
            for rule in rules
            if rule["is_required"]
            and rule["factor_code"] not in available_factors
        ]

        if missing_factors:
            raise ValueError(
                "Required risk information missing: "
                + ", ".join(missing_factors)
            )

        observations["APPLICANT_AGE"] = calculate_age(
            applicant["date_of_birth"],
            today
        )

        observations["ASSET_AGE"] = calculate_age(
            asset["purchase_date"],
            today
        )

        observations["ASSET_VALUE"] = asset["asset_value"]

        # --------------------------------------------------
        # 9. Calculate risk
        # --------------------------------------------------

        risk = assess_quote(
            product_risk_rules=rules,
            observed_values=observations,
            asset_age_limit=product["max_asset_age_years"]
        )

        # --------------------------------------------------
        # 10. Combine eligibility and risk
        # --------------------------------------------------

        decision = make_underwriting_decision(
            eligibility=eligibility,
            risk=risk
        )

        # --------------------------------------------------
        # 11. Calculate premium
        # --------------------------------------------------

        if risk.risk_score is None:
            raise ValueError(
                "Cannot calculate premium without a valid risk score"
            )

        coverage_amount = max(
            item["coverage_limit"]
            for item in selected_coverages
        )

        premium = calculate_premium(
            coverage_amount=coverage_amount,
            base_rate=product["base_rate"],
            risk_score=risk.risk_score
        )

        calculated_premium = premium.final_premium

        if calculated_premium <= 0:
            raise ValueError(
                "Calculated premium must be greater than zero"
            )

        # --------------------------------------------------
        # 12. Generate a unique quote ID
        # --------------------------------------------------

        conn.execute(
            "SELECT pg_advisory_xact_lock(20261030)"
        )

        sequence = conn.execute(
            """
            SELECT COALESCE(
                MAX(SUBSTRING(quote_id FROM '[0-9]+$')::BIGINT),
                0
            ) + 1 AS next_number
            FROM quotes
            WHERE quote_id LIKE 'QTE-2026-%'
            """
        ).fetchone()["next_number"]

        quote_id = f"QTE-2026-{sequence:06d}"

        # --------------------------------------------------
        # 13. Create quote
        # --------------------------------------------------

        quote_valid_until = (
            payload.requested_start_date + timedelta(days=30)
        )

        quote = conn.execute(
            """
            INSERT INTO quotes (
                quote_id,
                renewal_id,
                applicant_id,
                asset_id,
                product_id,
                requested_start_date,
                requested_end_date,
                requested_coverage_amount,
                calculated_premium,
                currency,
                quote_status,
                quote_valid_until,
                created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, 'INR', 'PENDING_REVIEW', %s,
                CURRENT_TIMESTAMP
            )
            RETURNING *
            """,
            (
                quote_id,
                renewal_id,
                payload.applicant_id,
                payload.asset_id,
                payload.product_id,
                payload.requested_start_date,
                payload.requested_end_date,
                coverage_amount,
                calculated_premium,
                quote_valid_until
            )
        ).fetchone()
        # --------------------------------------------------
        # 14. Allocate premium across coverages
        # --------------------------------------------------

        total_limit = sum(
            (
                item["coverage_limit"]
                for item in selected_coverages
            ),
            Decimal("0")
        )

        if total_limit <= 0:
            raise ValueError("Total coverage limit must be positive")

        remaining_premium = calculated_premium

        for index, item in enumerate(selected_coverages):

            if index == len(selected_coverages) - 1:
                coverage_premium = remaining_premium

            else:
                coverage_premium = (
                    calculated_premium
                    * item["coverage_limit"]
                    / total_limit
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

                remaining_premium -= coverage_premium

            conn.execute(
                """
                INSERT INTO quote_coverages (
                    quote_id,
                    coverage_option_id,
                    selected_limit,
                    coverage_premium
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    quote_id,
                    item["coverage_option_id"],
                    item["coverage_limit"],
                    coverage_premium
                )
            )

        
        # --------------------------------------------------
        # 15. Save risk observations
        # --------------------------------------------------

        for factor_code, value in observations.items():
            json_value = make_json_compatible(value)

            conn.execute(
                """
                INSERT INTO quote_risk_observations (
                    quote_id,
                    factor_code,
                    observed_value
                )
                VALUES (%s, %s, %s)
                """,
                (
                    quote_id,
                    factor_code,
                    Jsonb(json_value)
                )
            )

        # --------------------------------------------------
        # 16. Save factor assessments
        # --------------------------------------------------

        save_factor_assessments(
            conn,
            quote_id,
            risk.factor_assessments
        )

        # --------------------------------------------------
        # 17. Save underwriting recommendation
        # --------------------------------------------------

        save_decision(
            conn,
            quote_id,
            decision
        )

        # --------------------------------------------------
        # 18. Return API response
        # --------------------------------------------------

        return {
            "message": "Quote created successfully",
            "quote_id": quote_id,
            "quote_status": "PENDING_REVIEW",
            "eligibility_status": decision.eligibility_status,
            "decision_type": decision.decision_type,
            "risk_score": decision.risk_score,
            "risk_category": decision.risk_category,
            "decision_reason": decision.decision_reason,
            "coverage_amount": coverage_amount,
            "calculated_premium": calculated_premium,
            "currency": "INR",
            "is_final": False
        }
