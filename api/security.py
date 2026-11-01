import os, json, hmac, hashlib, base64, time
from fastapi import HTTPException, Request
from api.database import get_connection

SECRET=os.getenv('JWT_SECRET','CHANGE_THIS_LOCAL_DEMO_SECRET_BEFORE_DEPLOYMENT').encode()
ROLES={'ADMIN','OPERATIONS_ANALYST','RISK_REVIEWER','CUSTOMER'}
def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def _unb64(s): return base64.urlsafe_b64decode(s+'='*((4-len(s)%4)%4))
def hash_password(password, salt=None):
    salt=salt or os.urandom(16)
    dk=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000)
    return _b64(salt)+'.'+_b64(dk)
def verify_password(password, stored):
    try:
        s,h=stored.split('.'); return hmac.compare_digest(_b64(hashlib.pbkdf2_hmac('sha256',password.encode(),_unb64(s),310000)),h)
    except Exception: return False
def issue_token(user):
    payload={'sub':str(user['user_id']),'email':user['email'],'role':user['role'],'name':user['full_name'],'exp':int(time.time())+8*3600}
    body=_b64(json.dumps(payload,separators=(',',':')).encode()); sig=_b64(hmac.new(SECRET,body.encode(),hashlib.sha256).digest())
    return body+'.'+sig
def decode_token(token):
    try:
        body,sig=token.split('.'); expected=_b64(hmac.new(SECRET,body.encode(),hashlib.sha256).digest())
        if not hmac.compare_digest(sig,expected): raise ValueError()
        data=json.loads(_unb64(body))
        if data['exp']<time.time(): raise ValueError()
        return data
    except Exception: raise HTTPException(status_code=401,detail='Invalid or expired access token')
def current_user(request: Request):
    auth=request.headers.get('authorization','')
    if not auth.lower().startswith('bearer '): raise HTTPException(status_code=401,detail='Login required')
    return decode_token(auth.split(' ',1)[1])
def require_roles(user, *roles):
    if user['role'] not in roles and user['role']!='ADMIN': raise HTTPException(status_code=403,detail='Your role cannot perform this action')
