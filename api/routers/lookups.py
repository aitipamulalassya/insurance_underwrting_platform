from fastapi import APIRouter, Request, Query
from api.database import get_connection
from api.security import current_user, require_roles
router=APIRouter()

@router.get('/lookups/{kind}')
def lookup(kind:str, request:Request, q:str=Query(default='',max_length=100), limit:int=Query(default=100,ge=1,le=250), product_id:str|None=None):
    user=current_user(request)
    require_roles(user,'ADMIN','OPERATIONS_ANALYST','RISK_REVIEWER')
    term=f'%{q.strip()}%'
    sqls={
      'applicants':("SELECT applicant_id AS id, concat_ws(' ',first_name,last_name) AS label, email AS detail FROM applicants WHERE (%s='' OR applicant_id ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s OR email ILIKE %s) ORDER BY last_name,first_name LIMIT %s", lambda:[q,term,term,term,term,limit]),
      'assets':("SELECT asset_id AS id, concat_ws(' · ',asset_type,asset_description,registration_number) AS label, concat_ws(' · ',asset_value,location_city) AS detail FROM insured_assets WHERE (%s='' OR asset_id ILIKE %s OR asset_type ILIKE %s OR asset_description ILIKE %s OR registration_number ILIKE %s) ORDER BY asset_id LIMIT %s",lambda:[q,term,term,term,term,limit]),
      'products':("SELECT product_id AS id, product_name AS label, product_code AS detail FROM products WHERE (%s='' OR product_id ILIKE %s OR product_name ILIKE %s OR product_code ILIKE %s) ORDER BY product_name LIMIT %s",lambda:[q,term,term,term,limit]),
      'coverage-options':("SELECT coverage_option_id AS id, coverage_name AS label, product_id AS detail FROM coverage_options WHERE (%s IS NULL OR product_id=%s) AND (%s='' OR coverage_option_id ILIKE %s OR coverage_name ILIKE %s OR product_id ILIKE %s) ORDER BY coverage_name LIMIT %s",lambda:[product_id,product_id,q,term,term,term,limit]),
      'policies':("SELECT policy_id AS id, policy_id AS label, concat_ws(' · ',applicant_id,policy_status) AS detail FROM policies WHERE (%s='' OR policy_id ILIKE %s OR applicant_id ILIKE %s) ORDER BY policy_id DESC LIMIT %s",lambda:[q,term,term,limit]),
      'quotes':("SELECT quote_id AS id, quote_id AS label, concat_ws(' · ',applicant_id,quote_status) AS detail FROM quotes WHERE (%s='' OR quote_id ILIKE %s OR applicant_id ILIKE %s) ORDER BY created_at DESC LIMIT %s",lambda:[q,term,term,limit]),
      'endorsements':("SELECT endorsement_id AS id, endorsement_id AS label, concat_ws(' · ',policy_id,endorsement_status) AS detail FROM endorsements WHERE (%s='' OR endorsement_id ILIKE %s OR policy_id ILIKE %s) ORDER BY requested_at DESC LIMIT %s",lambda:[q,term,term,limit]),
    }
    if kind not in sqls: return []
    sql,params=sqls[kind]
    with get_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql,params()); return cur.fetchall()
