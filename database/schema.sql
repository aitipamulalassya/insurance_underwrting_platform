-- YottaFlex Insurance Underwriting Platform
-- PostgreSQL schema baseline
-- Run against the project database (insurance_underwriting_db).
-- This script creates the initial relational schema. It does not DROP objects.
-- Apply only to a new/empty project database; for an existing database,
-- inspect its schema first and use the migration script as appropriate.

BEGIN;
CREATE TABLE applicants (
    applicant_id VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    date_of_birth DATE NOT NULL,
    email VARCHAR(254) NOT NULL UNIQUE,
    phone VARCHAR(30),
    address_line VARCHAR(200),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20),
    applicant_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (applicant_status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (date_of_birth < CURRENT_DATE)
);

CREATE TABLE insured_assets (
    asset_id VARCHAR(20) PRIMARY KEY,
    applicant_id VARCHAR(20) NOT NULL REFERENCES applicants(applicant_id),
    asset_type VARCHAR(30) NOT NULL
        CHECK (asset_type IN ('VEHICLE', 'HOME', 'COMMERCIAL_PROPERTY')),
    asset_description VARCHAR(250) NOT NULL,
    asset_value NUMERIC(14,2) NOT NULL CHECK (asset_value > 0),
    purchase_date DATE,
    registration_number VARCHAR(50) UNIQUE,
    location_city VARCHAR(100),
    location_state VARCHAR(100),
    asset_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (asset_status IN ('ACTIVE', 'INACTIVE', 'DISPOSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (purchase_date IS NULL OR purchase_date <= CURRENT_DATE)
);

CREATE TABLE products (
    product_id VARCHAR(20) PRIMARY KEY,
    product_code VARCHAR(30) NOT NULL UNIQUE,
    product_name VARCHAR(100) NOT NULL UNIQUE,
    product_line VARCHAR(30) NOT NULL
        CHECK (product_line IN ('MOTOR', 'HOME', 'BUSINESS')),
    description TEXT,
    min_asset_value NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (min_asset_value >= 0),
    max_asset_value NUMERIC(14,2) NOT NULL CHECK (max_asset_value > min_asset_value),
    min_asset_age_years INTEGER NOT NULL DEFAULT 0 CHECK (min_asset_age_years >= 0),
    max_asset_age_years INTEGER NOT NULL CHECK (max_asset_age_years >= min_asset_age_years),
    base_rate NUMERIC(10,6) NOT NULL CHECK (base_rate > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from DATE NOT NULL,
    effective_to DATE,
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE coverage_options (
    coverage_option_id VARCHAR(20) PRIMARY KEY,
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    coverage_code VARCHAR(30) NOT NULL,
    coverage_name VARCHAR(100) NOT NULL,
    description TEXT,
    min_limit NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (min_limit >= 0),
    max_limit NUMERIC(14,2) NOT NULL CHECK (max_limit > min_limit),
    is_mandatory BOOLEAN NOT NULL DEFAULT FALSE,
    effective_from DATE NOT NULL,
    effective_to DATE,
    UNIQUE (product_id, coverage_code, effective_from),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE risk_factors (
    risk_factor_id VARCHAR(20) PRIMARY KEY,
    factor_code VARCHAR(40) NOT NULL UNIQUE,
    factor_name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    factor_category VARCHAR(30) NOT NULL
        CHECK (factor_category IN ('APPLICANT', 'ASSET', 'LOCATION', 'CLAIMS', 'OTHER')),
    data_type VARCHAR(20) NOT NULL
        CHECK (data_type IN ('NUMERIC', 'BOOLEAN', 'CATEGORICAL')),
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from DATE NOT NULL,
    effective_to DATE,
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

-- Product-to-risk-factor many-to-many relationship and transparent factor values.
CREATE TABLE product_risk_factors (
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    risk_factor_id VARCHAR(20) NOT NULL REFERENCES risk_factors(risk_factor_id),
    factor_weight NUMERIC(8,4) NOT NULL CHECK (factor_weight >= 0),
    low_risk_threshold NUMERIC(14,4),
    high_risk_threshold NUMERIC(14,4),
    missing_data_action VARCHAR(20) NOT NULL DEFAULT 'REFER'
        CHECK (missing_data_action IN ('REFER', 'DECLINE', 'ALLOW')),
    effective_from DATE NOT NULL,
    effective_to DATE,
    PRIMARY KEY (product_id, risk_factor_id, effective_from),
    CHECK (high_risk_threshold IS NULL OR low_risk_threshold IS NULL
           OR high_risk_threshold >= low_risk_threshold),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE quotes (
    quote_id VARCHAR(20) PRIMARY KEY,
    applicant_id VARCHAR(20) NOT NULL REFERENCES applicants(applicant_id),
    asset_id VARCHAR(20) NOT NULL REFERENCES insured_assets(asset_id),
    renewal_id VARCHAR(50),
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    requested_start_date DATE NOT NULL,
    requested_end_date DATE NOT NULL,
    requested_coverage_amount NUMERIC(14,2) NOT NULL CHECK (requested_coverage_amount > 0),
    calculated_premium NUMERIC(14,2) NOT NULL CHECK (calculated_premium >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    quote_status VARCHAR(25) NOT NULL
        CHECK (quote_status IN ('DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REFERRED',
                                'DECLINED', 'ACCEPTED', 'REJECTED', 'EXPIRED')),
    applicant_accepted_at TIMESTAMPTZ,
    quote_valid_until DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (requested_end_date > requested_start_date),
    CHECK (quote_valid_until >= requested_start_date),
    CHECK (applicant_accepted_at IS NULL OR quote_status = 'ACCEPTED')
);
ALTER TABLE quotes
ADD CONSTRAINT fk_quotes_renewal
FOREIGN KEY (renewal_id)
REFERENCES renewals(renewal_id);
-- A quote may select multiple coverage options.
CREATE TABLE quote_coverages (
    quote_id VARCHAR(20) NOT NULL REFERENCES quotes(quote_id),
    coverage_option_id VARCHAR(20) NOT NULL REFERENCES coverage_options(coverage_option_id),
    selected_limit NUMERIC(14,2) NOT NULL CHECK (selected_limit > 0),
    coverage_premium NUMERIC(14,2) NOT NULL CHECK (coverage_premium >= 0),
    PRIMARY KEY (quote_id, coverage_option_id)
);

CREATE TABLE underwriting_decisions (
    decision_id VARCHAR(24) PRIMARY KEY,
    quote_id VARCHAR(20) NOT NULL REFERENCES quotes(quote_id),
    decision_type VARCHAR(20) NOT NULL
        CHECK (decision_type IN ('APPROVE', 'REFER', 'DECLINE')),
    risk_score NUMERIC(8,4) CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_category VARCHAR(20)
        CHECK (risk_category IN ('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN')),
    decision_reason TEXT NOT NULL,
    approval_authority VARCHAR(30),
    reviewer_reference VARCHAR(100),
    decided_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ruleset_version VARCHAR(30) NOT NULL,
    is_final BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE policies (
    policy_id VARCHAR(20) PRIMARY KEY,
    quote_id VARCHAR(20) NOT NULL UNIQUE REFERENCES quotes(quote_id),
    applicant_id VARCHAR(20) NOT NULL REFERENCES applicants(applicant_id),
    asset_id VARCHAR(20) NOT NULL REFERENCES insured_assets(asset_id),
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    policy_start_date DATE NOT NULL,
    policy_end_date DATE NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    policy_status VARCHAR(20) NOT NULL
        CHECK (policy_status IN ('ACTIVE', 'CANCELLED', 'EXPIRED', 'LAPSED')),
    accepted_at TIMESTAMPTZ NOT NULL,
    payment_confirmed_at TIMESTAMPTZ NOT NULL,
    premium_amount NUMERIC(14,2) NOT NULL CHECK (premium_amount >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    CHECK (policy_end_date > policy_start_date),
    CHECK (issued_at >= accepted_at),
    CHECK (issued_at >= payment_confirmed_at)
);

CREATE TABLE endorsements (
    endorsement_id VARCHAR(40) PRIMARY KEY,
    policy_id VARCHAR(20) NOT NULL REFERENCES policies(policy_id),
    endorsement_sequence INTEGER NOT NULL CHECK (endorsement_sequence > 0),
    endorsement_type VARCHAR(30) NOT NULL
        CHECK (endorsement_type IN ('ASSET_CHANGE', 'COVERAGE_CHANGE', 'DETAIL_CORRECTION', 'OTHER')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_date DATE NOT NULL,
    previous_values JSONB NOT NULL,
    proposed_values JSONB NOT NULL,
    additional_premium NUMERIC(14,2) NOT NULL DEFAULT 0,
    endorsement_status VARCHAR(20) NOT NULL
        CHECK (endorsement_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    decision_reason TEXT,
    UNIQUE (policy_id, endorsement_sequence),
    CHECK (additional_premium >= 0)
);

CREATE TABLE renewals (
    renewal_id VARCHAR(40) PRIMARY KEY,
    policy_id VARCHAR(20) NOT NULL REFERENCES policies(policy_id),
    renewal_year INTEGER NOT NULL,
    offer_generated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    proposed_start_date DATE NOT NULL,
    proposed_end_date DATE NOT NULL,
    proposed_premium NUMERIC(14,2) NOT NULL CHECK (proposed_premium >= 0),
    renewal_status VARCHAR(20) NOT NULL
        CHECK (renewal_status IN ('OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'INELIGIBLE')),
    responded_at TIMESTAMPTZ,
    decision_reason TEXT,
    UNIQUE (policy_id, renewal_year),
    CHECK (proposed_end_date > proposed_start_date),
    CHECK (responded_at IS NULL OR responded_at >= offer_generated_at)
);

-- Explicit history: never rely only on the current status column.
CREATE TABLE policy_events (
    policy_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_id VARCHAR(20) NOT NULL REFERENCES policies(policy_id),
    event_type VARCHAR(30) NOT NULL,
    previous_status VARCHAR(20),
    new_status VARCHAR(20),
    event_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor_reference VARCHAR(100),
    event_reason TEXT,
    event_details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE quote_events (
    quote_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quote_id VARCHAR(20) NOT NULL REFERENCES quotes(quote_id),
    event_type VARCHAR(30) NOT NULL,
    previous_status VARCHAR(25),
    new_status VARCHAR(25),
    event_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor_reference VARCHAR(100),
    event_reason TEXT,
    event_details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE payments (
    payment_id VARCHAR(24) PRIMARY KEY,
    quote_id VARCHAR(20) NOT NULL REFERENCES quotes(quote_id),
    policy_id VARCHAR(20) UNIQUE REFERENCES policies(policy_id),
    amount NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    payment_status VARCHAR(20) NOT NULL
        CHECK (payment_status IN ('PENDING', 'CONFIRMED', 'FAILED', 'REFUNDED')),
    payment_reference VARCHAR(100) UNIQUE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMPTZ
);

-- =====================================================
-- QUOTE RISK ASSESSMENTS
-- =====================================================
CREATE TABLE IF NOT EXISTS quote_risk_assessments (

    assessment_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,

    quote_id VARCHAR(50) NOT NULL
        REFERENCES quotes(quote_id),

    risk_factor_id VARCHAR(50) NOT NULL
        REFERENCES risk_factors(risk_factor_id),

    observed_value JSONB NOT NULL,

    normalized_score NUMERIC(5,2),

    factor_weight NUMERIC(8,4) NOT NULL
        CHECK (factor_weight >= 0),

    weighted_score NUMERIC(10,4)
        CHECK (weighted_score >= 0),

    assessment_reason TEXT NOT NULL,

    assessed_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    ruleset_version VARCHAR(30) NOT NULL,

    CONSTRAINT quote_risk_assessments_normalized_score_check
        CHECK (
            normalized_score >= 0
            AND normalized_score <= 100
        ),

    CONSTRAINT uq_quote_risk_factor
        UNIQUE (quote_id, risk_factor_id)
);
CREATE TABLE quote_risk_observations (
    observation_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    quote_id VARCHAR(50) NOT NULL REFERENCES quotes(quote_id),
    factor_code VARCHAR(100) NOT NULL,
    observed_value JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- QUOTE RISK OBSERVATIONS
-- =====================================================



-- =====================================================
-- UNDERWRITING DOCUMENT CHUNKS
-- Requires the pgvector extension.
-- =====================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE underwriting_document_chunks (
    chunk_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    document_id UUID
        REFERENCES underwriting_documents(document_id)
        ON DELETE CASCADE,
    source_title TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_document_chunk
        UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_assets_applicant ON insured_assets(applicant_id);
CREATE INDEX IF NOT EXISTS idx_quotes_applicant ON quotes(applicant_id);
CREATE INDEX IF NOT EXISTS idx_quotes_asset ON quotes(asset_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(quote_status);
CREATE INDEX IF NOT EXISTS idx_policies_applicant ON policies(applicant_id);
CREATE INDEX IF NOT EXISTS idx_policies_asset_dates ON policies(asset_id, policy_start_date, policy_end_date);
CREATE INDEX IF NOT EXISTS idx_decisions_quote ON underwriting_decisions(quote_id);
CREATE INDEX IF NOT EXISTS idx_renewals_policy ON renewals(policy_id);
CREATE INDEX IF NOT EXISTS idx_policy_events_policy_time ON policy_events(policy_id, event_at);

COMMIT;
