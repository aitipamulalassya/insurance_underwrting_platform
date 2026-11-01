# YottaFlex Underwriting Frontend

React + TypeScript + Vite + Tailwind CSS frontend for the uploaded Insurance Underwriting FastAPI backend.

## Requirements
- Node.js 20 or newer
- npm
- Backend running at `http://127.0.0.1:8000`

## Setup
```bash
cd frontend
npm install
```

Create `.env` from `.env.example` if the backend URL differs:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Run the frontend:
```bash
npm run dev
```
Open `http://localhost:5173`.

Build for production:
```bash
npm run build
npm run preview
```

## Pages
- Overview dashboard
- Applicants
- Products
- Quotes (list, details, audit history, quote creation)
- Underwriting review queue and human decisions
- Policy issue action and policy audit history lookup
- Endorsement creation, review, payment and activation
- Renewals (generate offers, respond, generate quote, expire offers)
- Anomaly detection and finding inspection

## Backend integration notes
The UI uses the actual routes registered in `api/main.py` and the corresponding router modules. It does not assume that unsupported list APIs exist.

The backend includes read-only list endpoints for policies, endorsements and coverage options:
- `GET /api/policies`
- `GET /api/endorsements`
- `GET /api/coverage-options`

Quote creation loads coverage options from the database. Policy and endorsement pages display the actual records returned by these endpoints. Policy audit history remains available by policy ID.

The backend still does not expose a general payments list endpoint; payment actions are available through the existing workflow endpoints.

## API CORS
The supplied `api/main.py` does not configure CORS middleware. If the browser blocks requests from `http://localhost:5173`, add this to the FastAPI app setup in `api/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Restart the backend after adding middleware. This changes only API browser access configuration; it does not modify database records.

## Data safety
The frontend performs only the actions exposed by the backend. It does not run SQL, delete records, reset the database, or create synthetic seed data automatically.


## Authentication and additional modules

The app now requires a signed-in account. Create the first administrator from the login screen, then create role accounts under **Users**. Customer accounts require an existing applicant ID. New pages: AI knowledge assistant, document management, reports and user administration. The backend adds database tables additively and does not reset business data. See the root README for setup, role permissions, limitations and smoke tests.
