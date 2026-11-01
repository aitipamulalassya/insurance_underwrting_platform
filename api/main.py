
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.extensions import initialize_extensions, router as extensions_router
from api.routers.security import router as security_router
from api.routers.lookups import router as lookups_router

from api.routers import (
    health,
    products,
    applicants,
    quotes,
    underwriting,
    quote_creation,
    acceptance,
    endorsement_activation,
    endorsement_review,
    endorsements,
    policies,
    review,
    payments,
    anomalies,
    catalog,
)

from api.routers.renewals import router as renewals_router


app = FastAPI(
    title="Insurance Underwriting API",
    description=(
        "APIs for insurance quotes, risk assessment, "
        "underwriting, policies, endorsements, renewals "
        "and anomaly detection."
    ),
    version="1.0.0"
)


# Health
app.include_router(
    health.router,
    prefix="/api",
    tags=["Health"]
)

# Read-only catalog listings (policies, endorsements, coverage options)
app.include_router(catalog.router, prefix="/api", tags=["Catalog"])

# Products
app.include_router(
    products.router,
    prefix="/api",
    tags=["Products"]
)

# Applicants
app.include_router(
    applicants.router,
    prefix="/api",
    tags=["Applicants"]
)

# Quotes
app.include_router(
    quotes.router,
    prefix="/api",
    tags=["Quotes"]
)

# Automated Underwriting
app.include_router(
    underwriting.router,
    prefix="/api",
    tags=["Underwriting"]
)

# Quote Creation
app.include_router(
    quote_creation.router,
    prefix="/api",
    tags=["Quote Creation"]
)

# Human Underwriting Review
app.include_router(
    review.router,
    prefix="/api",
    tags=["Human Underwriting Review"]
)

# Quote Acceptance
app.include_router(
    acceptance.router,
    prefix="/api",
    tags=["Quote Acceptance"]
)

# Payments
app.include_router(
    payments.router,
    prefix="/api",
    tags=["Payments"]
)

# Policies
app.include_router(
    policies.router,
    prefix="/api",
    tags=["Policies"]
)

# Endorsements
app.include_router(
    endorsements.router,
    prefix="/api",
    tags=["Endorsements"]
)

# Endorsement Review
app.include_router(
    endorsement_review.router,
    prefix="/api",
    tags=["Endorsement Review"]
)

# Endorsement Activation
app.include_router(
    endorsement_activation.router,
    prefix="/api",
    tags=["Endorsement Activation"]
)

# Renewals
app.include_router(
    renewals_router,
    prefix="/api",
    tags=["Renewals"]
)

# Anomaly Detection
app.include_router(
    anomalies.router,
    prefix="/api/anomalies",
    tags=["Anomaly Detection"]
)


@app.get("/")
def root():
    return {
        "message": "Insurance Underwriting API is running",
        "version": "1.0.0",
        "documentation": "/docs"
    }

# Additive extension tables; CREATE TABLE IF NOT EXISTS preserves existing business records.
@app.on_event("startup")
def startup_extensions():
    initialize_extensions()

app.include_router(security_router, prefix="/api", tags=["Authentication and Users"])
app.include_router(lookups_router, prefix="/api", tags=["Searchable record lookups"])
app.include_router(extensions_router, prefix="/api", tags=["Documents, Assistant, Exceptions and Reports"])

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from api.security import decode_token
class AccessControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path=request.url.path
        if request.method != 'OPTIONS' and path.startswith('/api/') and not path.startswith('/api/auth/') and path != '/api/health':
            header=request.headers.get('authorization','')
            if not header.lower().startswith('bearer '): return JSONResponse({'detail':'Login required'},status_code=401)
            try: user=decode_token(header.split(' ',1)[1])
            except Exception: return JSONResponse({'detail':'Invalid or expired access token'},status_code=401)
            role=user.get('role')
            # Customers may only access their quote/payment journey; all internal operations are blocked.
            if role=='CUSTOMER':
                if not (path.startswith('/api/quotes/') or path=='/api/customer/quotes' or path.startswith('/api/payments/')):
                    return JSONResponse({'detail':'Customer role can only access its linked quote and payment journey'},status_code=403)
                from api.database import get_connection
                applicant_id=None
                try:
                    with get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute('SELECT applicant_id FROM app_users WHERE user_id=%s',(int(user['sub']),))
                            account=cur.fetchone(); applicant_id=account['applicant_id'] if account else None
                            if not applicant_id: return JSONResponse({'detail':'Customer account is not linked to an applicant record'},status_code=403)
                            parts=[p for p in path.split('/') if p]
                            if path=='/api/customer/quotes':
                                cur.execute('SELECT 1 FROM app_users WHERE user_id=%s AND role=\'CUSTOMER\' AND applicant_id=%s',(int(user['sub']),applicant_id))
                            elif len(parts)>=3 and parts[1]=='quotes':
                                cur.execute('SELECT 1 FROM quotes WHERE quote_id=%s AND applicant_id=%s',(parts[2],applicant_id))
                            elif len(parts)>=3 and parts[1]=='payments':
                                if request.method == 'POST' and len(parts) >= 4 and parts[3] == 'confirm':
                                    return JSONResponse({'detail':'Customers cannot verify or confirm payments'},status_code=403)
                                cur.execute('SELECT 1 FROM payments p JOIN quotes q ON q.quote_id=p.quote_id WHERE p.payment_id=%s AND q.applicant_id=%s',(parts[2],applicant_id))
                            else: return JSONResponse({'detail':'Unsupported customer operation'},status_code=403)
                            if not cur.fetchone(): return JSONResponse({'detail':'This record does not belong to the signed-in customer'},status_code=403)
                except Exception:
                    return JSONResponse({'detail':'Could not verify customer record ownership'},status_code=403)
            if role=='OPERATIONS_ANALYST' and (path.startswith('/api/auth/users') or (path.startswith('/api/anomalies/') and request.method=='PUT')):
                return JSONResponse({'detail':'Operations analysts cannot perform this action'},status_code=403)
            if role=='OPERATIONS_ANALYST' and ('/review' in path or path.endswith('/decision')) and path.startswith('/api/endorsements'):
                return JSONResponse({'detail':'Only risk reviewers or administrators can review endorsements'},status_code=403)
            if role=='OPERATIONS_ANALYST' and path.endswith('/decision') and path.startswith('/api/underwriting/'):
                return JSONResponse({'detail':'Only risk reviewers or administrators can record underwriting decisions'},status_code=403)
            if role=='RISK_REVIEWER' and request.method in ('POST','PUT','DELETE') and (path.startswith('/api/quotes') or path.startswith('/api/applicants')):
                return JSONResponse({'detail':'Risk reviewers have read/review access, not submission-management access'},status_code=403)
            if role=='RISK_REVIEWER' and request.method=='POST' and (path.startswith('/api/payments/') or path.startswith('/api/renewals')):
                return JSONResponse({'detail':'Risk reviewers cannot process payments or renewal operations'},status_code=403)
            if role=='RISK_REVIEWER' and request.method=='POST' and (path.startswith('/api/policies/') or path.endswith('/payment') or path.endswith('/activate')):
                return JSONResponse({'detail':'Risk reviewers may review endorsements but cannot create, pay or activate them'},status_code=403)
            if role=='RISK_REVIEWER' and request.method=='POST' and path.endswith('/issue-policy'):
                return JSONResponse({'detail':'Only operations staff or administrators can issue a policy after payment verification'},status_code=403)
        return await call_next(request)
app.add_middleware(AccessControlMiddleware)

# CORS is registered last so browser clients also receive headers on 401/403 responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
