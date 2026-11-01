from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field
from api.database import get_connection
from api.security import current_user, require_roles
import re, uuid, os
router=APIRouter()
DOC_DIR=Path(__file__).resolve().parents[1]/'data'/'uploaded_documents'
DOC_DIR.mkdir(parents=True,exist_ok=True)
def initialize_extensions():
  with get_connection() as c:
    with c.cursor() as q:
      q.execute("""CREATE TABLE IF NOT EXISTS app_users(user_id BIGSERIAL PRIMARY KEY,full_name VARCHAR(120) NOT NULL,email VARCHAR(255) UNIQUE NOT NULL,password_hash TEXT NOT NULL,role VARCHAR(30) NOT NULL CHECK(role IN ('ADMIN','OPERATIONS_ANALYST','RISK_REVIEWER','CUSTOMER')),is_active BOOLEAN NOT NULL DEFAULT TRUE,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
      q.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS applicant_id VARCHAR(80)")
      q.execute("""CREATE TABLE IF NOT EXISTS underwriting_documents(document_id UUID PRIMARY KEY,entity_type VARCHAR(30) NOT NULL,entity_id VARCHAR(80) NOT NULL,original_name TEXT NOT NULL,stored_name TEXT NOT NULL,mime_type TEXT,uploaded_by BIGINT REFERENCES app_users(user_id),uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),extracted_text TEXT)""")
      q.execute("ALTER TABLE underwriting_documents ADD COLUMN IF NOT EXISTS rag_indexed_at TIMESTAMPTZ")
      q.execute("""CREATE TABLE IF NOT EXISTS anomaly_cases(anomaly_id TEXT PRIMARY KEY,status VARCHAR(20) NOT NULL DEFAULT 'OPEN',assigned_to BIGINT REFERENCES app_users(user_id),resolution_notes TEXT,updated_by BIGINT REFERENCES app_users(user_id),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
      q.execute("""CREATE TABLE IF NOT EXISTS assistant_feedback(feedback_id BIGSERIAL PRIMARY KEY,question TEXT NOT NULL,answer TEXT NOT NULL,asked_by BIGINT REFERENCES app_users(user_id),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
class CaseUpdate(BaseModel): status:str=Field(pattern='^(OPEN|INVESTIGATING|RESOLVED|WONT_FIX)$'); resolution_notes:str=''
class Ask(BaseModel): question:str=Field(min_length=3,max_length=1500)
GUIDELINES=[
('Product eligibility','Eligibility is determined using the selected product rules, including asset type, asset value and asset age. An application outside a configured minimum or maximum eligibility range must be referred or declined according to the eligibility engine result.','Product rules'),
('Risk assessment','Risk assessment uses configured risk factors and observations. Missing mandatory risk information should be treated as UNKNOWN and referred for human review. Low risk can be approved automatically; medium and high risk should be referred for review.','Underwriting policy'),
('Underwriting decisions','APPROVE means the configured rules permit progression. REFER means a qualified reviewer must inspect the case. DECLINE means an eligibility or underwriting rule blocks progression. Human reviewers should record a decision and reason.','Decision governance'),
('Premium calculation','The prototype premium calculation uses coverage amount multiplied by the configured product base rate, then applies the risk loading. The formula is a synthetic demonstration assumption and is not a production actuarial rating model.','Pricing methodology'),
('Approval authority','Automated recommendations do not replace human approval for referred cases. A reviewer should inspect eligibility, risk observations, supporting documents and premium details before recording the final decision.','Approval workflow'),
('Renewals','A renewal offer should be evaluated against the existing policy status, renewal period, eligibility, updated risk information and premium. Cancelled policies should not be renewed. Expired offers should not be accepted.','Renewal procedure'),
('Endorsements','An endorsement changes policy coverage only after the required review and payment steps are complete and activation is recorded. An approved but unactivated endorsement must not be treated as an effective coverage change.','Endorsement procedure'),
('Exceptions and audit','An anomaly is a signal for investigation, not an automatic correction. Preserve the original transaction, document the investigation, record the resolution and retain the audit trail.','Exception handling')]
def tokens(s): return set(re.findall(r'[a-z0-9]{3,}',s.lower()))
@router.post('/assistant/ask')
def ask(p:Ask,request:Request):
  u=current_user(request); require_roles(u,'ADMIN','OPERATIONS_ANALYST','RISK_REVIEWER')
  from api.rag import index_guidelines, index_document, retrieve, generate_answer
  try:
    index_guidelines(GUIDELINES)
    with get_connection() as c:
      with c.cursor() as q:
        q.execute('SELECT document_id::text AS document_id,original_name,extracted_text FROM underwriting_documents WHERE extracted_text IS NOT NULL AND extracted_text<>%s AND rag_indexed_at IS NULL ORDER BY uploaded_at DESC LIMIT 100',('',))
        pending=q.fetchall()
    for doc in pending:
      count=index_document(doc['document_id'],doc['original_name'],doc['extracted_text'])
      with get_connection() as c:
        with c.cursor() as q: q.execute('UPDATE underwriting_documents SET rag_indexed_at=NOW() WHERE document_id=%s',(doc['document_id'],))
    chosen=retrieve(p.question, limit=5)
  except HTTPException:
    raise
  except Exception as exc:
    raise HTTPException(503, f'RAG is not available. Check pgvector installation and Gemini configuration: {exc}')
  if not chosen:
    answer='I could not find sufficiently relevant passages in the indexed underwriting guidance or uploaded documents. Please consult an authorized reviewer; no underwriting decision should be inferred.'
  else:
    answer=generate_answer(p.question, chosen)
  with get_connection() as c:
    with c.cursor() as q: q.execute('INSERT INTO assistant_feedback(question,answer,asked_by) VALUES(%s,%s,%s)',(p.question,answer,int(u['sub'])))
  return {'answer':answer,'sources':[{'title':d['title'],'document_id':d.get('document_id'),'chunk_index':d['chunk_index'],'similarity':round(float(d['similarity']),4),'excerpt':d['content'][:500]} for d in chosen],'grounded':bool(chosen),'retrieval':'pgvector_cosine','generation_model':os.getenv('GEMINI_MODEL','gemini-2.5-flash') if chosen else None}
@router.post('/documents')
async def upload_document(request:Request,entity_type:str=Form(...),entity_id:str=Form(...),file:UploadFile=File(...)):
  u=current_user(request); require_roles(u,'ADMIN','OPERATIONS_ANALYST','RISK_REVIEWER')
  name=Path(file.filename or 'upload').name
  if Path(name).suffix.lower() not in {'.txt','.md','.pdf'}: raise HTTPException(400,'Only PDF, TXT and Markdown files are supported')
  raw=await file.read()
  if len(raw)>10*1024*1024: raise HTTPException(413,'Maximum document size is 10 MB')
  text=''
  if Path(name).suffix.lower() in {'.txt','.md'}: text=raw.decode('utf-8',errors='replace')
  elif Path(name).suffix.lower()=='.pdf':
    try:
      from pypdf import PdfReader
      import io
      text='\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(raw)).pages)
    except Exception: text=''
  docid=str(uuid.uuid4()); stored=docid+Path(name).suffix.lower(); (DOC_DIR/stored).write_bytes(raw)
  with get_connection() as c:
    with c.cursor() as q:
      q.execute('INSERT INTO underwriting_documents(document_id,entity_type,entity_id,original_name,stored_name,mime_type,uploaded_by,extracted_text) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING document_id,entity_type,entity_id,original_name,uploaded_at',(docid,entity_type.upper(),entity_id,name,stored,file.content_type,int(u['sub']),text))
      saved=q.fetchone()
  indexed=False
  if text.strip():
    try:
      from api.rag import index_document
      index_document(docid, name, text)
      with get_connection() as c:
        with c.cursor() as q: q.execute('UPDATE underwriting_documents SET rag_indexed_at=NOW() WHERE document_id=%s',(docid,))
      indexed=True
    except Exception:
      # Preserve the upload; the assistant indexes pending documents on the next question.
      indexed=False
  saved['rag_indexed']=indexed
  return saved
@router.get('/documents')
def list_documents(request:Request,entity_type:str|None=None,entity_id:str|None=None):
  u=current_user(request); require_roles(u,'ADMIN','OPERATIONS_ANALYST','RISK_REVIEWER')
  where=[]; vals=[]
  if entity_type: where.append('entity_type=%s'); vals.append(entity_type.upper())
  if entity_id: where.append('entity_id=%s'); vals.append(entity_id)
  sql='SELECT document_id,entity_type,entity_id,original_name,mime_type,uploaded_at,uploaded_by,(extracted_text IS NOT NULL AND extracted_text<>\'\') AS text_extracted,(rag_indexed_at IS NOT NULL) AS rag_indexed FROM underwriting_documents '+(('WHERE '+' AND '.join(where)) if where else '')+' ORDER BY uploaded_at DESC'
  with get_connection() as c:
    with c.cursor() as q: q.execute(sql,vals); return q.fetchall()
@router.get('/documents/{document_id}/download')
def download_document(document_id:str,request:Request):
  from fastapi.responses import FileResponse
  u=current_user(request); require_roles(u,'ADMIN','OPERATIONS_ANALYST','RISK_REVIEWER')
  with get_connection() as c:
    with c.cursor() as q: q.execute('SELECT stored_name,original_name,mime_type FROM underwriting_documents WHERE document_id=%s',(document_id,)); row=q.fetchone()
  if not row: raise HTTPException(404,'Document not found')
  path=DOC_DIR/row['stored_name']
  if not path.exists(): raise HTTPException(404,'Stored file is missing')
  return FileResponse(path,filename=row['original_name'],media_type=row['mime_type'] or 'application/octet-stream')
@router.get('/anomalies/{anomaly_id}/case')
def get_case(anomaly_id:str,request:Request):
  u=current_user(request); require_roles(u,'ADMIN','RISK_REVIEWER','OPERATIONS_ANALYST')
  with get_connection() as c:
    with c.cursor() as q: q.execute('SELECT ac.*,au.full_name AS assigned_name FROM anomaly_cases ac LEFT JOIN app_users au ON au.user_id=ac.assigned_to WHERE anomaly_id=%s',(anomaly_id,)); row=q.fetchone()
  return row or {'anomaly_id':anomaly_id,'status':'OPEN','resolution_notes':''}
@router.put('/anomalies/{anomaly_id}/case')
def update_case(anomaly_id:str,p:CaseUpdate,request:Request):
  u=current_user(request); require_roles(u,'ADMIN','RISK_REVIEWER')
  with get_connection() as c:
    with c.cursor() as q:
      q.execute('INSERT INTO anomaly_cases(anomaly_id,status,resolution_notes,updated_by,updated_at) VALUES(%s,%s,%s,%s,NOW()) ON CONFLICT(anomaly_id) DO UPDATE SET status=EXCLUDED.status,resolution_notes=EXCLUDED.resolution_notes,updated_by=EXCLUDED.updated_by,updated_at=NOW() RETURNING *',(anomaly_id,p.status,p.resolution_notes,int(u['sub'])))
      return q.fetchone()
@router.get('/reports/summary')
def reports(request:Request):
  u=current_user(request); require_roles(u,'ADMIN','OPERATIONS_ANALYST','RISK_REVIEWER')
  with get_connection() as c:
    with c.cursor() as q:
      result={}
      for key,sql in [('quotes',"SELECT COUNT(*)::int AS total, COUNT(*) FILTER(WHERE quote_status='ACCEPTED')::int AS accepted FROM quotes"),('policies',"SELECT COUNT(*)::int AS total, COUNT(*) FILTER(WHERE policy_status='ACTIVE')::int AS active FROM policies"),('renewals',"SELECT COUNT(*)::int AS total, COUNT(*) FILTER(WHERE renewal_status='ACCEPTED')::int AS accepted FROM renewals"),('endorsements',"SELECT COUNT(*)::int AS total FROM endorsements")]:
        try: q.execute(sql); result[key]=q.fetchone()
        except Exception: c.rollback(); result[key]={'unavailable':'Schema/column differs; inspect source records'}
      try: q.execute('SELECT COALESCE(SUM(calculated_premium),0)::numeric(18,2) AS quoted_premium FROM quotes'); result['premium']=q.fetchone()
      except Exception: c.rollback(); result['premium']={'quoted_premium':0}
      try: q.execute('SELECT role,COUNT(*)::int AS users FROM app_users GROUP BY role'); result['users']=q.fetchall()
      except Exception: result['users']=[]
      return result

@router.get('/customer/quotes')
def customer_quotes(request:Request):
  u=current_user(request)
  if u['role']!='CUSTOMER': raise HTTPException(403,'Customer portal endpoint is reserved for customer accounts')
  with get_connection() as c:
    with c.cursor() as q:
      q.execute('SELECT applicant_id FROM app_users WHERE user_id=%s',(int(u['sub']),)); a=q.fetchone()
      if not a or not a['applicant_id']: raise HTTPException(403,'Customer account is not linked to an applicant record')
      q.execute('''SELECT q.quote_id,q.applicant_id,q.product_id,q.quote_status,q.calculated_premium,q.created_at,q.applicant_accepted_at, p.payment_id,p.payment_status,p.amount AS payment_amount FROM quotes q LEFT JOIN LATERAL (SELECT payment_id,payment_status,amount FROM payments WHERE quote_id=q.quote_id ORDER BY recorded_at DESC LIMIT 1) p ON TRUE WHERE q.applicant_id=%s ORDER BY q.created_at DESC''',(a['applicant_id'],))
      return q.fetchall()
