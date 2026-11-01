# Database Design — YottaFlex Insurance Underwriting Platform

## Overview

The project uses PostgreSQL to store insurance underwriting data as related entities. The schema separates applicant and asset master data, insurance products and coverages, quote processing, underwriting decisions, policy lifecycle records, payments, renewals, endorsements, and event history.

## Main entities and responsibilities

| Entity/table | Responsibility |
|---|---|
| `applicants` | Applicant identity and contact details. |
| `insured_assets` | Assets associated with applicants. |
| `products` | Insurance product definitions, eligibility ranges and base rates. |
| `coverage_options` | Coverage choices belonging to products, with limits and effective dates. |
| `risk_factors` | Risk-factor definitions and categories. |
| `product_risk_factors` | Product-specific risk-factor weights, thresholds and missing-data actions. |
| `quotes` | Quote request, premium, validity and customer acceptance state. |
| `quote_coverages` | Coverage options and selected limits/premiums for a quote. |
| `underwriting_decisions` | Risk score/category, human/system decision details, reason and ruleset version. |
| `policies` | Issued policy linked to its originating quote, applicant, asset and product. |
| `payments` | Payment record and confirmation state; payment is simulated in this project. |
| `endorsements` | Policy change requests, before/after values, decision and additional premium. |
| `renewals` | Renewal offer, response, proposed dates/premium and resulting renewed policy. |
| `quote_events` | Quote status/event history with actor, reason and details. |
| `policy_events` | Policy lifecycle history with actor, reason and details. |

## Relationships

- One applicant can own multiple insured assets.
- A product can have multiple coverage options and multiple mapped risk factors.
- A quote belongs to an applicant, insured asset and product.
- A quote can select multiple coverages through `quote_coverages`.
- Underwriting decisions are recorded against quotes.
- A policy is issued from a quote; the schema enforces one policy per quote with a unique constraint.
- Endorsements and renewal offers belong to policies.
- Quote and policy events preserve lifecycle history separately from the current status columns.
- Payments reference the quote and may be associated with a policy, endorsement or renewal.

## Integrity and validation choices

- Primary keys identify each record; foreign keys protect relationships between records.
- `CHECK` constraints restrict status/category values and validate positive amounts, date ranges and numeric limits.
- `UNIQUE` constraints prevent duplicate business identifiers and selected duplicate lifecycle records.
- Indexes support common lookups by applicant, asset, quote status, policy dates, decision quote and policy event timeline.
- `JSONB` stores endorsement before/after values and event details where the structure can vary.
- Timestamp columns record when important records and lifecycle events were created or decided.

## Schema evolution

`schema.sql` represents the initial schema baseline from the supplied pgAdmin SQL. `migrations.sql` consolidates later changes found in the development SQL history: endorsement activation, payment links to endorsements/renewals, renewal quote links, renewed-policy references, and renewal offer expiry tracking. Repeated inspection queries and test-specific data updates from the development history are intentionally excluded.

## Setup notes

1. Create a PostgreSQL database named `insurance_underwriting_db` (or use the database name configured by the application).
2. Run `schema.sql` against that database for a new/empty database.
3. Run `migrations.sql` only when evolving a database created from the baseline schema. Review the current schema first; do not run the baseline over a populated database as a substitute for migrations.
4. Configure the backend connection string/environment variables to point to the same database.
5. Verify the tables and row counts before connecting the application.

## Important implementation note

The supplied SQL history contains development-time inspection queries and test-specific statements. Those are not part of the clean setup scripts. The scripts in this package preserve the documented table design and consolidate the later structural changes; they do not contain the user's existing application data.
