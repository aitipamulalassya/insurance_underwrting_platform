# YottaFlex Insurance Underwriting Platform

A web application for managing insurance underwriting workflows, from applicant and asset data through quote generation, risk assessment, premium calculation, underwriting review, payment processing, and policy operations.

## 1. Problem this project addresses

Insurance submissions involve multiple related records and decisions. Teams need to check whether an applicant and insured asset are eligible, calculate risk and premium, record an underwriting decision, and track the quote through payment and policy operations.

This project brings those activities into one workflow and separates responsibilities across four roles:

- **Customer** – views their own quotes and policies, responds to eligible offers, and initiates the simulated payment flow.
- **Risk Reviewer / Underwriter** – reviews risk information and records an underwriting decision.
- **Operations Analyst** – handles operational steps such as payment verification and policy processing.
- **Admin** – monitors users, records, workflow activity, and operational exceptions.

Actual permissions must be enforced by the backend APIs, not only by hiding frontend controls.

## 2. Main capabilities

- Applicant, insured asset, product, coverage option, and risk-factor master data.
- Quote generation and quote management.
- Risk assessment and risk categorization.
- Premium calculation using product rates and risk loading.
- Underwriting review and decision tracking.
- Simulated payment workflow.
- Policy, endorsement, and renewal workflows.
- Anomaly monitoring and investigation.


**Payment note:** The payment workflow is simulated. This project does not claim to integrate a live payment gateway.

## 3. Technology

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| Database | PostgreSQL |

## 4. High-level workflow

1. Create or select an applicant and insured asset.
2. Select an insurance product and eligible coverage.
3. Generate a quote.
4. Calculate risk and premium.
5. Route the quote for underwriting review when required.
6. Record the authorized human underwriting decision.
7. Allow the customer to respond to an approved quote.
8. Customer initiates the simulated payment.
9. Operations verifies the payment.
10. An authorized Operations Analyst processes policy issuance.
11. Manage subsequent endorsements and renewal offers through their respective review and operational steps.

The automated risk recommendation and the final human underwriting decision are separate concepts. A recommendation should not be presented as a human approval.

## 5. Assumptions and key decisions

- The solution models a simplified insurance underwriting workflow for the assignment; it is not a complete production insurance core system.
- Product rates, coverage limits, risk factors, and eligibility rules are based on the project data and configured business logic.
- Payment is simulated so the workflow can be demonstrated without processing real money.
- Underwriting decisions are kept separate from operational tasks such as payment verification and policy issuance.
- Role permissions and customer data ownership should be checked by backend endpoints.
- Existing database records should be preserved during development and troubleshooting.

### Trade-offs

- **Rule-based calculations:** Risk and premium logic are easier to inspect and test than an opaque end-to-end prediction, but the configured rules need domain review before real-world use.
- **Simulated payments:** This makes the operational journey demonstrable without a payment provider, but it does not validate real payment settlement, refunds, or gateway security.
- **Assignment-focused scope:** The implementation prioritizes the required workflow over production-scale infrastructure, exhaustive edge-case coverage, and external integrations.

## 6. Project structure

The project contains separate frontend, backend, and generator areas. The exact files may vary by branch or submitted package.

```text
insurance_underwriting_master_generator/
├── frontend/       # React + TypeScript + Vite application
├── generator/      # Master-data and underwriting generation modules
├── requirements.txt
└── ...
```

## 7. Prerequisites

Install the following before running the project:

- Python (a version compatible with the packages in `requirements.txt`)
- Node.js and npm
- PostgreSQL
- Git (if cloning the repository)


## 8. Configuration

1. Open the project folder.
2. Check the backend configuration and any provided `.env.example` or setup configuration file.
3. Create the local environment file in the location expected by the backend.
4. Set the PostgreSQL host, port, database name, username, and password to match your local database.
5. Do not commit `.env` files.

Use the variable names already defined by the project's configuration or example environment file. Do not rename configuration variables unless the backend code is updated to use the new names.

**Database safety:** Point the application to a development database. If you already have project data, do not drop the database or delete its Docker volume as a setup step. Use the database initialization or migration process supplied with the project, if present.

## 9. Install and run

Open a terminal in the project root.

### Backend

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

The backend development server should start at the address printed by Uvicorn. If the command cannot find `api.main`, check that the terminal is in the directory expected by the project layout.

### Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite normally serves the development frontend at:

```text
http://localhost:5173
```

Open that address in a browser. Keep the backend and database running while using the application.

### Production frontend build

From the `frontend` directory:

```bash
npm run build
```

The build runs TypeScript project compilation and the Vite production build. The generated production files are written to `frontend/dist/`.

A successful build confirms that the frontend compiles and bundles. It does not, by itself, prove that the backend, database, authentication, or every user workflow works end to end.

## 10. Generate underwriting data (if required)

From the project root, the recorded underwriting generator command is:

```bash
python -m generator.run_underwriting
```

Run data-generation commands only after checking their configuration and target database. Confirm whether a command inserts or updates records before running it against a database containing data you need to preserve.

A previously recorded run processed 4,000 quotes and reported:
- 641 APPROVE / LOW
- 3,359 REFER
- 0 DECLINE

These are outputs from that recorded run, not guaranteed results for every dataset or configuration.

## 11. Testing approach and recorded evidence

Testing during development included running the data generators and calculation-engine test scripts, reviewing generated output, investigating database import errors, building the frontend, and manually reviewing application screens for different roles.

Recorded test outputs include:

| Check | Recorded result |
|---|---|
| Risk engine test | Risk score 12.0; category LOW; decision APPROVE |
| Premium engine test | Coverage amount 1,000,000; base rate 0.025; base premium 25,000.00; risk loading 1.2000; final premium 30,000.00 |
| Quote generation | 4,000 quotes; 9,296 quote-coverage links; 12,000 risk observations |
| Underwriting generator | 4,000 quotes processed; 641 APPROVE / LOW, 3,359 REFER, 0 DECLINE |
| Frontend production build | `tsc -b && vite build` completed successfully; 2,276 modules transformed |

The frontend build also reported non-blocking optimization warnings about a module being both statically and dynamically imported and a minified JavaScript chunk larger than 500 KB. The build succeeded, but these warnings indicate possible future code-splitting and bundle-size improvements.

These results demonstrate that the corresponding commands ran and produced the recorded outputs. They do not establish exhaustive test coverage or production readiness.

## 12. Limitations and future improvements

- Payment is simulated; no live payment gateway, settlement, refund, or reconciliation integration is claimed.
- Risk and premium rules are assignment-level logic and require validation by insurance domain specialists before real-world use.
- Further end-to-end testing is needed for edge cases, concurrent actions, authorization boundaries, and all workflow transitions.
- UI and operational review identified improvements that may still need implementation. A recommendation should not be assumed to be completed functionality.
- Production deployment would require additional security review, monitoring, secrets management, backups, performance testing, and operational controls.

## 13. Troubleshooting

**Backend cannot connect to PostgreSQL**
- Confirm PostgreSQL is running.
- Check the database connection settings used by the backend.
- Confirm the database exists and the configured user has the required permissions.
- Check the backend terminal for the exact connection error.

**Frontend cannot reach the backend**
- Confirm the backend is running.
- Check the frontend API base URL and backend CORS configuration.
- Check the browser developer console and backend logs.

**Frontend build warning**
- A successful build with warnings is still a successful build. Review the import strategy and bundle splitting before treating the warnings as resolved.



---

