from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from api.database import get_connection
from api.security import hash_password, verify_password, issue_token, current_user, require_roles, ROLES
router=APIRouter()
class Login(BaseModel): email: str; password: str
class UserCreate(BaseModel): full_name:str=Field(min_length=2,max_length=120); email:str; password:str=Field(min_length=8); role:str; applicant_id:str|None=None
@router.post('/auth/bootstrap-admin')
def bootstrap_admin(p:UserCreate):
    if p.role!='ADMIN': raise HTTPException(400,'First account must be ADMIN')
    with get_connection() as c:
      with c.cursor() as q:
        q.execute('SELECT COUNT(*) AS n FROM app_users');
        if q.fetchone()['n']>0: raise HTTPException(409,'Initial administrator already exists')
        q.execute('INSERT INTO app_users(full_name,email,password_hash,role) VALUES(%s,%s,%s,%s) RETURNING user_id,full_name,email,role,created_at',(p.full_name,p.email.lower(),hash_password(p.password),'ADMIN'))
        u=q.fetchone()
    return {'user':u,'access_token':issue_token(u),'token_type':'bearer'}
@router.post('/auth/login')
def login(p:Login):
    with get_connection() as c:
      with c.cursor() as q: q.execute('SELECT * FROM app_users WHERE lower(email)=lower(%s) AND is_active=TRUE',(p.email,)); u=q.fetchone()
    if not u or not verify_password(p.password,u['password_hash']): raise HTTPException(401,'Invalid email or password')
    return {'user':{'user_id':u['user_id'],'full_name':u['full_name'],'email':u['email'],'role':u['role']},'access_token':issue_token(u),'token_type':'bearer'}
@router.get('/auth/me')
def me(request:Request):
    u=current_user(request); return {'user_id':u['sub'],'full_name':u['name'],'email':u['email'],'role':u['role']}
@router.get('/auth/users')
def users(request:Request):
    u=current_user(request); require_roles(u,'ADMIN')
    with get_connection() as c:
      with c.cursor() as q: q.execute('SELECT user_id,full_name,email,role,is_active,created_at FROM app_users ORDER BY created_at DESC'); return q.fetchall()
@router.post('/auth/users')
def create_user(p:UserCreate,request:Request):
    u=current_user(request); require_roles(u,'ADMIN')
    if p.role not in ROLES: raise HTTPException(400,'Unknown role')
    if p.role=='CUSTOMER' and not p.applicant_id: raise HTTPException(400,'Customer accounts must be linked to an applicant_id')
    with get_connection() as c:
      with c.cursor() as q:
       try: q.execute('INSERT INTO app_users(full_name,email,password_hash,role,applicant_id) VALUES(%s,%s,%s,%s,%s) RETURNING user_id,full_name,email,role,applicant_id,is_active,created_at',(p.full_name,p.email.lower(),hash_password(p.password),p.role,p.applicant_id)); return q.fetchone()
       except Exception as e: raise HTTPException(409,'Email already exists or user could not be created')
