# YottaFlex Insurance Underwriting Platform

A role-based insurance workflow application for applicant and asset
data, quote generation, eligibility and risk assessment, premium
calculation, underwriting review, customer acceptance, simulated payment
verification, and policy operations.

## 1. Problem

Insurance underwriting involves connected records, eligibility rules,
risk factors, premium calculations, approvals, customer responses, and
operational hand-offs. This project brings these steps into one
traceable workflow and separates system recommendations from human
underwriting decisions.

## Roles and Responsibilities

The system supports four main user roles, each with specific responsibilities.

| Role | Responsibilities |
|---|---|
| **Customer** | View available quotes, review coverage and premium details, accept or reject a quote, and complete the simulated payment process. |
| **Operations Analyst** | Monitor underwriting operations, verify payment status, confirm payment records, and support policy issuance and related operational activities. |
| **Risk / Compliance Reviewer** | Review risk assessments, examine underwriting decisions and exceptions, and review cases that require additional approval. |
| **System Administrator** | Manage user access and roles, oversee system configuration, and monitor overall application operations. |

### Role-Based Access

- Customers can access their own quote and policy-related information.
- Operations Analysts handle payment verification and operational workflows.
- Risk / Compliance Reviewers handle risk-related reviews and exceptions.
- Administrators manage users and system-level access.

Each role is intended to support clear responsibility, controlled access, and traceability throughout the underwriting workflow.
## 2. Assumptions and key decisions

-   The project uses synthetic applicant, asset, product, coverage, and
    risk data.
-   Product eligibility, risk thresholds, and premium rates are
    configurable assignment-level rules.
-   Risk and premium calculations are deterministic and rule-based; the
    risk engine is not an LLM.
-   Payment is simulated. No real payment gateway or money transfer is
    involved.
-   Roles separate customer, risk reviewer, operations analyst, and
    administrator activities.

## 3. Trade-offs

-   **Rule-based risk engine:** transparent and testable, but rules and
    thresholds need insurance-domain validation.
-   **Synthetic data:** makes the workflow reproducible, but does not
    represent a real insurer's portfolio.
-   **Simulated payment:** demonstrates payment verification and policy
    issuance without gateway integration.
-   **Assignment scope:** focuses on the required workflow rather than
    production-scale security, integrations, and operations.

## 4. Technology

-   Frontend: React, TypeScript, Vite
-   Backend: Python, FastAPI
-   Database: PostgreSQL with the `pgvector` extension
-   Data generation: Python CSV generators

## 5. Prerequisites

Install Python 3.12 or a compatible version, Node.js 20+ with npm, PostgreSQL with the `pgvector` extension, and Git. Start your local PostgreSQL server before setting up the database.

## 6. Setup and run the application

### Step 1: Create the PostgreSQL database

Open pgAdmin and connect to your PostgreSQL server. In the Query Tool, run:

```sql
CREATE DATABASE insurance_underwriting_db;
```

Connect to the new `insurance_underwriting_db` database. Run these SQL files in this order:

1. `database/schema.sql`
2. `database/migrations.sql`

The PostgreSQL server must have the `pgvector` extension installed.

### Step 2: Create and configure the local environment

From the project root, create and activate a Python virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy the environment example and update the values in `.env`:

```powershell
Copy-Item .env.example .env
```

Configure your database connection and required settings:

```env
DATABASE_URL=postgresql://YOUR_USER:YOUR_PASSWORD@localhost:5432/insurance_underwriting_db
JWT_SECRET=replace-with-a-long-random-secret
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

`DATABASE_URL` and `JWT_SECRET` are required. Gemini settings are used by the document/RAG assistant features. Use your own API key for those features. Do not commit `.env` or real credentials.

Configure the frontend environment:

```powershell
Copy-Item frontend/.env.example frontend/.env
```

The supplied frontend example points to `http://127.0.0.1:8000`. Change `VITE_API_BASE_URL` only if your backend uses another address.

### Step 3: Generate the CSV files

From the project root, with the virtual environment activated, run:

```powershell
python -m generator.master_generator
python -m generator.quote_generator
```

The generated files are saved in `data/master/` and `data/quotes/`.

### Step 4: Import the CSV files into PostgreSQL

In pgAdmin, open the target table, right-click it, and select **Import/Export Data**. Choose the CSV file, set the format to CSV, enable **Header**, and map the CSV columns to the database columns.

Import the files in this order:

| CSV file | PostgreSQL table | Expected rows |
|---|---|---:|
| `data/master/applicants.csv` | `applicants` | 3,000 |
| `data/master/products.csv` | `products` | 3 |
| `data/master/risk_factors.csv` | `risk_factors` | 7 |
| `data/master/insured_assets.csv` | `insured_assets` | 3,000 |
| `data/master/coverage_options.csv` | `coverage_options` | 9 |
| `data/master/product_risk_factors.csv` | `product_risk_factors` | 18 |
| `data/quotes/quotes.csv` | `quotes` | 4,000 |
| `data/quotes/quote_coverages.csv` | `quote_coverages` | 9,298 |
| `data/quotes/risk_observations.csv` | `quote_risk_observations` | 12,000 |

**Important column mappings:**

- In `quote_coverages.csv`, map `coverage_limit` to the database column `selected_limit`.
- For `risk_observations.csv`, import only `quote_id`, `factor_code`, and `observed_value`. Do not import `observation_id` or `created_at`; PostgreSQL generates them.
- Map columns by name. Do not assume the CSV and database column orders are the same.
- If the CSV data is already imported, do not import it again.

### Step 5: Run the combined underwriting process

After importing all CSV files, run this command from the project root:

```powershell
python -m generator.run_combined_underwriting
```

This runs the combined product eligibility and risk assessment process and saves the underwriting recommendations.

### Step 6: Run the backend

From the project root, activate the virtual environment if it is not already active, then run:

```powershell
.venv\Scripts\Activate.ps1
uvicorn api.main:app --reload
```

Backend: `http://127.0.0.1:8000`

API documentation: `http://127.0.0.1:8000/docs`

Keep this terminal running.

### Step 7: Install and run the frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`).




## 11. Limitations

-   Payments are simulated; there is no real gateway, settlement, or
    refund processing.
-   Risk and eligibility rules use synthetic assignment data and are not
    validated insurance underwriting policy.
-   A passing unit test or frontend build does not prove every role,
    API, and end-to-end workflow is production-ready.


