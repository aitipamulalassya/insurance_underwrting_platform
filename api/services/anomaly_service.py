
from decimal import Decimal

from api.database import get_connection


def _serialize(value):
    """Convert database values into JSON-friendly values."""

    if isinstance(value, Decimal):
        return float(value)

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return value


def _make_anomaly(
    anomaly_id,
    anomaly_type,
    severity,
    entity_type,
    entity_id,
    description,
    details
):
    """Create a consistent anomaly response."""

    return {
        "anomaly_id": anomaly_id,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "description": description,
        "details": {
            key: _serialize(value)
            for key, value in details.items()
        }
    }


# ============================================================
# 1-5. MAIN ANOMALY DETECTION
# ============================================================

def detect_anomalies():

    anomalies = []

    with get_connection() as conn:
        with conn.cursor() as cur:

            # ------------------------------------------------
            # 1. POLICY ISSUED WITHOUT CUSTOMER ACCEPTANCE
            # ------------------------------------------------

            cur.execute("""
                SELECT
                    p.policy_id,
                    p.quote_id,
                    p.applicant_id,
                    p.accepted_at AS policy_accepted_at,
                    q.quote_status,
                    q.applicant_accepted_at AS quote_accepted_at,
                    p.issued_at

                FROM policies p

                JOIN quotes q
                    ON q.quote_id = p.quote_id

                WHERE
                    q.applicant_accepted_at IS NULL
                    OR q.quote_status <> 'ACCEPTED'

                ORDER BY p.issued_at DESC;
            """)

            for row in cur.fetchall():

                anomalies.append(
                    _make_anomaly(
                        anomaly_id=(
                            f"POLICY_ACCEPTANCE_{row['policy_id']}"
                        ),
                        anomaly_type="POLICY_WITHOUT_ACCEPTANCE",
                        severity="HIGH",
                        entity_type="POLICY",
                        entity_id=row["policy_id"],
                        description=(
                            "A policy was issued, but its linked quote "
                            "does not show valid customer acceptance."
                        ),
                        details=dict(row)
                    )
                )

            # ------------------------------------------------
            # 2. PREMIUM MISMATCH
            #
            # Exclude quotes with an activated endorsement.
            # Compare calculated premium with coverage premiums.
            # ------------------------------------------------

            cur.execute("""
                SELECT
                    q.quote_id,
                    q.calculated_premium,

                    COALESCE(
                        SUM(qc.coverage_premium),
                        0
                    ) AS total_coverage_premium,

                    q.calculated_premium -
                    COALESCE(
                        SUM(qc.coverage_premium),
                        0
                    ) AS difference

                FROM quotes q

                LEFT JOIN quote_coverages qc
                    ON qc.quote_id = q.quote_id

                WHERE NOT EXISTS (
                    SELECT 1
                    FROM policies p

                    JOIN endorsements e
                        ON e.policy_id = p.policy_id

                    WHERE p.quote_id = q.quote_id
                      AND e.activated_at IS NOT NULL
                )

                GROUP BY
                    q.quote_id,
                    q.calculated_premium

                HAVING ABS(
                    q.calculated_premium -
                    COALESCE(SUM(qc.coverage_premium), 0)
                ) > 0.01

                ORDER BY q.quote_id;
            """)

            premium_rows = cur.fetchall()

            for row in premium_rows:

                # Check whether an unactivated endorsement
                # explains the premium difference.

                cur.execute(
                    """
                    SELECT
                        e.endorsement_id,
                        e.endorsement_status,
                        e.additional_premium,
                        e.activated_at

                    FROM endorsements e

                    JOIN policies p
                        ON p.policy_id = e.policy_id

                    WHERE p.quote_id = %s
                      AND ABS(e.additional_premium) = ABS(%s)
                      AND e.activated_at IS NULL

                    ORDER BY e.requested_at
                    """,
                    (
                        row["quote_id"],
                        row["difference"]
                    )
                )

                matching_endorsements = cur.fetchall()

                endorsement_details = [
                    {
                        "endorsement_id": e["endorsement_id"],
                        "status": e["endorsement_status"],
                        "additional_premium": _serialize(
                            e["additional_premium"]
                        ),
                        "activated_at": None
                    }
                    for e in matching_endorsements
                ]

                if matching_endorsements:

                    description = (
                        "The calculated quote premium differs from "
                        "the current coverage premium total. An "
                        "endorsement has an additional premium "
                        "matching the discrepancy, but no activation "
                        "timestamp. Review its payment and activation "
                        "audit history."
                    )

                else:

                    description = (
                        "The calculated quote premium differs from "
                        "the sum of its coverage premiums. Financial "
                        "reconciliation is required."
                    )

                anomalies.append(
                    _make_anomaly(
                        anomaly_id=(
                            f"PREMIUM_MISMATCH_{row['quote_id']}"
                        ),
                        anomaly_type="PREMIUM_MISMATCH",
                        severity="MEDIUM",
                        entity_type="QUOTE",
                        entity_id=row["quote_id"],
                        description=description,
                        details={
                            **dict(row),
                            "matching_unactivated_endorsements": (
                                endorsement_details
                            )
                        }
                    )
                )

            # ------------------------------------------------
            # 3. ENDORSEMENT COVERAGE LIMIT EXCEEDED
            # ------------------------------------------------

            cur.execute("""
                SELECT
                    e.endorsement_id,
                    e.policy_id,
                    e.endorsement_type,
                    e.endorsement_status,
                    e.effective_date,

                    e.proposed_values,

                    e.proposed_values->>'coverage_code'
                        AS coverage_code,

                    e.proposed_values->>'coverage_option_id'
                        AS coverage_option_id,

                    e.proposed_values->>'proposed_limit'
                        AS proposed_limit,

                    co.max_limit,
                    co.min_limit

                FROM endorsements e

                JOIN coverage_options co
                    ON co.coverage_option_id =
                       e.proposed_values->>'coverage_option_id'

                WHERE
                    CASE
                        WHEN (
                            e.proposed_values->>'proposed_limit'
                        ) ~ '^[0-9]+([.][0-9]+)?$'
                        THEN (
                            e.proposed_values->>'proposed_limit'
                        )::numeric > co.max_limit

                        ELSE FALSE
                    END

                ORDER BY e.requested_at DESC;
            """)

            for row in cur.fetchall():

                anomalies.append(
                    _make_anomaly(
                        anomaly_id=(
                            f"ENDORSEMENT_LIMIT_{row['endorsement_id']}"
                        ),
                        anomaly_type="ENDORSEMENT_LIMIT_EXCEEDED",
                        severity="HIGH",
                        entity_type="ENDORSEMENT",
                        entity_id=row["endorsement_id"],
                        description=(
                            "The proposed endorsement coverage limit "
                            "exceeds the maximum allowed coverage limit."
                        ),
                        details=dict(row)
                    )
                )

            # ------------------------------------------------
            # 4. RENEWAL FOR CANCELLED POLICY
            # ------------------------------------------------

            cur.execute("""
                SELECT
                    r.renewal_id,
                    r.policy_id,
                    r.renewal_year,
                    r.renewal_status,
                    r.proposed_start_date,
                    r.proposed_end_date,
                    p.policy_status

                FROM renewals r

                JOIN policies p
                    ON p.policy_id = r.policy_id

                WHERE p.policy_status = 'CANCELLED'

                ORDER BY r.offer_generated_at DESC;
            """)

            for row in cur.fetchall():

                anomalies.append(
                    _make_anomaly(
                        anomaly_id=(
                            f"CANCELLED_POLICY_RENEWAL_{row['renewal_id']}"
                        ),
                        anomaly_type="RENEWAL_FOR_CANCELLED_POLICY",
                        severity="HIGH",
                        entity_type="RENEWAL",
                        entity_id=row["renewal_id"],
                        description=(
                            "A renewal record exists for a cancelled policy."
                        ),
                        details=dict(row)
                    )
                )

            # ------------------------------------------------
            # 5. OVERLAPPING POLICY PERIODS
            #
            # Consecutive policies are not considered overlapping.
            # ------------------------------------------------

            cur.execute("""
                SELECT
                    p1.policy_id AS first_policy_id,
                    p2.policy_id AS second_policy_id,
                    p1.asset_id,

                    p1.policy_start_date AS first_start_date,
                    p1.policy_end_date AS first_end_date,

                    p2.policy_start_date AS second_start_date,
                    p2.policy_end_date AS second_end_date,

                    p1.policy_status AS first_policy_status,
                    p2.policy_status AS second_policy_status

                FROM policies p1

                JOIN policies p2
                    ON p1.asset_id = p2.asset_id
                   AND p1.policy_id < p2.policy_id

                WHERE
                    p1.policy_status <> 'CANCELLED'
                    AND p2.policy_status <> 'CANCELLED'

                    AND p1.policy_start_date < p2.policy_end_date
                    AND p2.policy_start_date < p1.policy_end_date

                ORDER BY p1.asset_id;
            """)

            for row in cur.fetchall():

                first_id = row["first_policy_id"]
                second_id = row["second_policy_id"]

                anomalies.append(
                    _make_anomaly(
                        anomaly_id=(
                            f"OVERLAPPING_POLICIES_"
                            f"{first_id}_{second_id}"
                        ),
                        anomaly_type="OVERLAPPING_POLICY_PERIODS",
                        severity="HIGH",
                        entity_type="POLICY",
                        entity_id=f"{first_id}, {second_id}",
                        description=(
                            "Two non-cancelled policies for the same "
                            "asset have overlapping coverage periods."
                        ),
                        details=dict(row)
                    )
                )

    # --------------------------------------------------------
    # 6. COVERAGE CHANGED WITHOUT ENDORSEMENT ACTIVATION
    # --------------------------------------------------------

    anomalies.extend(
        detect_unactivated_coverage_changes()
    )

    return anomalies


# ============================================================
# 6. COVERAGE CHANGED WITHOUT ENDORSEMENT ACTIVATION
# ============================================================

def detect_unactivated_coverage_changes():

    anomalies = []

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    e.endorsement_id,
                    e.policy_id,
                    p.quote_id,

                    e.endorsement_status,
                    e.endorsement_type,

                    e.previous_values,
                    e.proposed_values,

                    e.additional_premium,
                    e.activated_at,

                    qc.selected_limit AS current_limit,
                    qc.coverage_premium AS current_coverage_premium,

                    CASE
                        WHEN (
                            e.previous_values->>'selected_limit'
                        ) ~ '^[0-9]+([.][0-9]+)?$'
                        THEN (
                            e.previous_values->>'selected_limit'
                        )::numeric
                        ELSE NULL
                    END AS previous_limit,

                    CASE
                        WHEN (
                            e.previous_values->>'coverage_premium'
                        ) ~ '^[0-9]+([.][0-9]+)?$'
                        THEN (
                            e.previous_values->>'coverage_premium'
                        )::numeric
                        ELSE NULL
                    END AS previous_coverage_premium

                FROM endorsements e

                JOIN policies p
                    ON p.policy_id = e.policy_id

                JOIN quote_coverages qc
                    ON qc.quote_id = p.quote_id
                   AND qc.coverage_option_id =
                       e.proposed_values->>'coverage_option_id'

                WHERE
                    e.activated_at IS NULL

                    AND e.endorsement_type = 'COVERAGE_CHANGE'

                    AND e.endorsement_status = 'APPROVED'

                    AND (
                        e.previous_values->>'selected_limit'
                    ) ~ '^[0-9]+([.][0-9]+)?$'

                    AND (
                        e.previous_values->>'coverage_premium'
                    ) ~ '^[0-9]+([.][0-9]+)?$'

                    AND (
                        e.proposed_values->>'proposed_limit'
                    ) ~ '^[0-9]+([.][0-9]+)?$'

                    -- Current limit matches proposed endorsement limit.
                    AND qc.selected_limit =
                        CASE
                            WHEN (
                                e.proposed_values->>'proposed_limit'
                            ) ~ '^[0-9]+([.][0-9]+)?$'
                            THEN (
                                e.proposed_values->>'proposed_limit'
                            )::numeric
                            ELSE NULL
                        END

                    -- Current premium matches the proposed premium.
                    AND qc.coverage_premium =
                        (
                            CASE
                                WHEN (
                                    e.previous_values->>'coverage_premium'
                                ) ~ '^[0-9]+([.][0-9]+)?$'
                                THEN (
                                    e.previous_values->>'coverage_premium'
                                )::numeric
                                ELSE NULL
                            END
                            + e.additional_premium
                        )

                    -- There must not be a corresponding activation event.
                    AND NOT EXISTS (
                        SELECT 1
                        FROM policy_events pe

                        WHERE pe.policy_id = e.policy_id
                          AND pe.event_type = 'ENDORSEMENT_ACTIVATED'
                          AND pe.event_details->>'endorsement_id' =
                              e.endorsement_id
                    )

                ORDER BY e.requested_at DESC;
            """)

            for row in cur.fetchall():

                anomalies.append(
                    _make_anomaly(
                        anomaly_id=(
                            "UNACTIVATED_COVERAGE_CHANGE_"
                            f"{row['endorsement_id']}"
                        ),
                        anomaly_type=(
                            "COVERAGE_CHANGED_WITHOUT_ACTIVATION"
                        ),
                        severity="HIGH",
                        entity_type="ENDORSEMENT",
                        entity_id=row["endorsement_id"],
                        description=(
                            "Current policy coverage matches the proposed "
                            "endorsement values, but the endorsement has "
                            "no activation timestamp or corresponding "
                            "activation audit event. Investigate this "
                            "potential underwriting control failure."
                        ),
                        details=dict(row)
                    )
                )

    return anomalies


# ============================================================
# ANOMALY SUMMARY
# ============================================================

def get_anomaly_summary(anomalies):

    total = len(anomalies)

    high = sum(
        1
        for item in anomalies
        if item["severity"] == "HIGH"
    )

    medium = sum(
        1
        for item in anomalies
        if item["severity"] == "MEDIUM"
    )

    by_type = {}

    for item in anomalies:

        anomaly_type = item["anomaly_type"]

        by_type[anomaly_type] = (
            by_type.get(anomaly_type, 0) + 1
        )

    return {
        "total_anomalies": total,
        "high_severity": high,
        "medium_severity": medium,
        "by_type": by_type
    }
