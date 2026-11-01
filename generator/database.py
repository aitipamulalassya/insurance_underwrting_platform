
import os
import psycopg

from dotenv import load_dotenv
from psycopg.types.json import Jsonb
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing from .env")

    return psycopg.connect(DATABASE_URL)


def fetch_quote(quote_id):
    """Fetch the quote and its applicant, asset and product details."""

    query = """
        SELECT
            q.quote_id,
            q.applicant_id,
            q.asset_id,
            q.product_id,
            q.requested_coverage_amount,
            a.date_of_birth,
            ia.asset_type,
            ia.asset_value,
            ia.purchase_date,
            p.max_asset_age_years,
            p.max_asset_value
        FROM quotes q
        JOIN applicants a
            ON a.applicant_id = q.applicant_id
        JOIN insured_assets ia
            ON ia.asset_id = q.asset_id
        JOIN products p
            ON p.product_id = q.product_id
        WHERE q.quote_id = %s;
    """

    with get_connection() as conn:
        return conn.execute(query, (quote_id,)).fetchone()


def fetch_product_risk_rules(product_id):
    """Load the risk factors configured for a product."""

    query = """
        SELECT
            rf.factor_code,
            rf.data_type,
            rf.is_required,
            prf.factor_weight,
            prf.low_threshold,
            prf.high_threshold,
            prf.missing_data_action
        FROM product_risk_factors prf
        JOIN risk_factors rf
            ON rf.risk_factor_id = prf.risk_factor_id
        WHERE prf.product_id = %s;
    """

    with get_connection() as conn:
        return conn.execute(query, (product_id,)).fetchall()




def save_risk_assessments(quote_id, assessments, ruleset_version):
    """
    Save individual factor-level risk assessments.

    assessments should contain:
    factor_code, observed_value, normalized_score,
    factor_weight, weighted_score, reason
    """

    insert_query = """
        INSERT INTO quote_risk_assessments (
            quote_id,
            risk_factor_id,
            observed_value,
            normalized_score,
            factor_weight,
            weighted_score,
            assessment_reason,
            ruleset_version
        )
        SELECT
            %s,
            rf.risk_factor_id,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        FROM risk_factors rf
        WHERE rf.factor_code = %s
        ON CONFLICT (quote_id, risk_factor_id)
        DO UPDATE SET
            observed_value = EXCLUDED.observed_value,
            normalized_score = EXCLUDED.normalized_score,
            factor_weight = EXCLUDED.factor_weight,
            weighted_score = EXCLUDED.weighted_score,
            assessment_reason = EXCLUDED.assessment_reason,
            assessed_at = CURRENT_TIMESTAMP,
            ruleset_version = EXCLUDED.ruleset_version;
    """

    with get_connection() as conn:
        for item in assessments:
            conn.execute(
                insert_query,
                (
                    quote_id,
                    Jsonb(item["observed_value"]),
                    item["normalized_score"],
                    item["factor_weight"],
                    item["weighted_score"],
                    item["reason"],
                    ruleset_version,
                    item["factor_code"],
                ),
            )


def save_underwriting_decision(quote_id, result, ruleset_version):
    """Save the overall underwriting recommendation."""

    with get_connection() as conn:
        column_info = conn.execute(
            """
            SELECT data_type, column_default, is_identity
            FROM information_schema.columns
            WHERE table_name = 'underwriting_decisions'
              AND column_name = 'decision_id'
            """
        ).fetchone()

        if not column_info:
            raise RuntimeError("decision_id column was not found")

        data_type, column_default, is_identity = column_info

        values = (
            result.decision,
            result.risk_score,
            result.risk_category,
            result.reason,
            "UNDERWRITING_ENGINE",
            ruleset_version,
            quote_id,
        )

        if is_identity == "YES" or column_default is not None:
            conn.execute(
                """
                INSERT INTO underwriting_decisions (
                    quote_id,
                    decision_type,
                    risk_score,
                    risk_category,
                    decision_reason,
                    approval_authority,
                    decided_at,
                    ruleset_version,
                    is_final
                )
                VALUES (%s, %s, %s, %s, %s, %s,
                        CURRENT_TIMESTAMP, %s, TRUE)
                """,
                (
                    quote_id,
                    result.decision,
                    result.risk_score,
                    result.risk_category,
                    result.reason,
                    "UNDERWRITING_ENGINE",
                    ruleset_version,
                ),
            )

        elif data_type in ("character varying", "text", "character"):
            decision_id = f"UND-{quote_id}"

            conn.execute(
                """
                INSERT INTO underwriting_decisions (
                    decision_id,
                    quote_id,
                    decision_type,
                    risk_score,
                    risk_category,
                    decision_reason,
                    approval_authority,
                    decided_at,
                    ruleset_version,
                    is_final
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        CURRENT_TIMESTAMP, %s, TRUE)
                """,
                (
                    decision_id,
                    quote_id,
                    result.decision,
                    result.risk_score,
                    result.risk_category,
                    result.reason,
                    "UNDERWRITING_ENGINE",
                    ruleset_version,
                ),
            )

        else:
            raise RuntimeError(
                "Unsupported decision_id configuration. "
                "Check the decision_id column in pgAdmin."
            )
