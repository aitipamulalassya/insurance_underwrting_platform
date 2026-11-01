
import os
import json
from datetime import date
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

from generator.risk_engine import assess_quote, RULESET_VERSION


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

BATCH_SIZE = 200


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing from .env")

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )


def calculate_age(birth_date, reference_date):
    return (
        reference_date.year
        - birth_date.year
        - (
            (reference_date.month, reference_date.day)
            < (birth_date.month, birth_date.day)
        )
    )


def load_quotes(conn):
    query = """
        SELECT
            q.quote_id,
            q.product_id,
            a.date_of_birth,
            ia.purchase_date,
            p.max_asset_age_years
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



def load_product_rules(conn, product_id):
    query = """
        SELECT
            rf.factor_code,
            rf.is_required,
            prf.factor_weight,
            prf.low_risk_threshold,
            prf.high_risk_threshold,
            prf.missing_data_action
        FROM product_risk_factors prf
        JOIN risk_factors rf
            ON rf.risk_factor_id = prf.risk_factor_id
        WHERE prf.product_id = %s
        ORDER BY rf.factor_code;
    """

    return conn.execute(query, (product_id,)).fetchall()


def load_observations(conn, quote_id):
    query = """
        SELECT factor_code, observed_value
        FROM quote_risk_observations
        WHERE quote_id = %s;
    """

    rows = conn.execute(query, (quote_id,)).fetchall()

    return {
        row["factor_code"]: row["observed_value"]
        for row in rows
    }


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

def save_factor_assessments(conn, quote_id, assessments):
    query = """
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

    for item in assessments:
        conn.execute(
            query,
            (
                quote_id,
                Jsonb(make_json_compatible(item.observed_value)),
                item.normalized_score,
                item.factor_weight,
                item.weighted_score,
                item.explanation,
                RULESET_VERSION,
                item.factor_code,
            ),
        )


def save_decision(conn, quote_id, result):
    existing = conn.execute(
        """
        SELECT decision_id
        FROM underwriting_decisions
        WHERE quote_id = %s
        ORDER BY decided_at DESC
        LIMIT 1;
        """,
        (quote_id,),
    ).fetchone()

    values = (
        result.decision_type,
        result.risk_score,
        result.risk_category,
        result.decision_reason,
        "UNDERWRITING_ENGINE",
        RULESET_VERSION,
        False,
    )

    if existing:
        conn.execute(
            """
            UPDATE underwriting_decisions
            SET
                decision_type = %s,
                risk_score = %s,
                risk_category = %s,
                decision_reason = %s,
                approval_authority = %s,
                ruleset_version = %s,
                is_final = %s,
                decided_at = CURRENT_TIMESTAMP
            WHERE decision_id = %s;
            """,
            values + (existing["decision_id"],),
        )

    else:
        column = conn.execute(
            """
            SELECT data_type, column_default, is_identity
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'underwriting_decisions'
              AND column_name = 'decision_id';
            """
        ).fetchone()

        if not column:
            raise RuntimeError(
                "Could not find underwriting_decisions.decision_id"
            )

        data_type = column["data_type"]
        is_identity = column["is_identity"]
        column_default = column["column_default"]

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
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, %s, %s
                );
                """,
                (quote_id,) + values,
            )

        elif data_type in (
            "character varying", "text", "character"
        ):
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
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, %s, %s
                );
                """,
                (decision_id, quote_id) + values,
            )

        else:
            raise RuntimeError(
                "Unsupported decision_id column configuration"
            )


def run():
    reference_date = date(2026, 10, 30)

    counts = {
        "processed": 0,
        "approve": 0,
        "refer": 0,
        "decline": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
        "unknown": 0,
    }

    with get_connection() as conn:
        quotes = load_quotes(conn)

        rules_cache = {}

        print("Starting underwriting assessment...")
        print("Quotes found:", len(quotes))

        for index, quote in enumerate(quotes, start=1):
            quote_id = quote["quote_id"]
            product_id = quote["product_id"]

            if product_id not in rules_cache:
                rules_cache[product_id] = load_product_rules(
                    conn, product_id
                )

            rules = rules_cache[product_id]

            observations = load_observations(conn, quote_id)

            # Derive applicant age and asset age from source records.
            observations["APPLICANT_AGE"] = calculate_age(
                quote["date_of_birth"],
                reference_date,
            )

            observations["ASSET_AGE"] = calculate_age(
                quote["purchase_date"],
                reference_date,
            )

            result = assess_quote(
                product_risk_rules=rules,
                observed_values=observations,
                asset_age_limit=quote["max_asset_age_years"],
            )

            save_factor_assessments(
                conn,
                quote_id,
                result.factor_assessments,
            )

            save_decision(conn, quote_id, result)

            # This is a recommendation, not a final policy approval.
            conn.execute(
                """
                UPDATE quotes
                SET quote_status = 'PENDING_REVIEW'
                WHERE quote_id = %s;
                """,
                (quote_id,),
            )

            counts["processed"] += 1
            counts[result.decision_type.lower()] += 1
            counts[result.risk_category.lower()] += 1

            if index % BATCH_SIZE == 0:
                print(
                    f"Processed {index}/{len(quotes)} quotes..."
                )

        print("\nUnderwriting assessment completed!")

        for key, value in counts.items():
            print(f"{key.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    run()
