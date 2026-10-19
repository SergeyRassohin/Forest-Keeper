import os, sys, secrets, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC,datetime,timedelta
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from tests.test_auth import isolated_environment
from app.main import create_app
from app.auth.models import User,UserRole,AuthSession,AuditEvent
from app.auth.security import hash_password,token_digest
from app.common.database import make_engine
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select,func
from sqlalchemy.engine import make_url
from pydantic import SecretStr
O={'Origin':'https://localhost:8443'}
def check(cond, label):
    if not cond: raise AssertionError(label)
    print('PASS',label,flush=True)
gen=isolated_environment(); cfg=next(gen); engine=make_engine(cfg)
try:
    env=os.environ.copy(); env['FK_DATABASE_URL']=cfg.database_url.get_secret_value()
    pw=secrets.token_urlsafe(20)
    cmd=[sys.executable,'-m','app.auth.bootstrap','--login','review_admin','--full-name','Review','--password-stdin']
    def boot(): return subprocess.run(cmd,input=pw+'\n',text=True,capture_output=True,env=env)
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda _:boot(),range(2)))
    check(sorted(r.returncode for r in results)==[0,1],'BOOT-02 concurrent bootstrap exactly one success')
    check(boot().returncode==1,'BOOT-02 repeated bootstrap refuses')
    with Session(engine) as s:
        u=s.scalar(select(User)); check([r.role_code for r in u.roles]==['ADMIN'],'BOOT-01 only ADMIN')
        a=s.scalar(select(AuditEvent).where(AuditEvent.event_type=='ADMIN_BOOTSTRAPPED'))
        check(a.user_id is None and a.object_id==u.id,'BOOT-01 audit actor and target')
    with TestClient(create_app(settings=cfg),base_url='https://localhost:8443') as c:
        res=c.post('/api/v1/auth/login',json={'login':'REVIEW_ADMIN','password':pw},headers=O)
        check(res.status_code==200,'AUTH-01 uppercase login')
        admin=res.json()['access_token']; h={'Authorization':'Bearer '+admin}
        for role in ['VIEWER','REVIEWER','DATA_OWNER','ADMIN','NONE','COMBINED']:
            roles=[] if role=='NONE' else ['ADMIN','REVIEWER'] if role=='COMBINED' else [role]
            body={'login':'role_'+role.lower(),'full_name':'Review','password':pw,'roles':roles+roles}
            r=c.post('/api/v1/users',json=body,headers=h); check(r.status_code==201,'USER-01/02 create '+role)
            check(sorted(r.json()['roles'])==sorted(roles),'USER-02 deduplicate '+role)
            check(c.post('/api/v1/users',json={**body,'login':body['login'].upper()},headers=h).status_code==409,'USER-02 duplicate '+role)
            with TestClient(create_app(settings=cfg),base_url='https://localhost:8443') as d:
                r=d.post('/api/v1/auth/login',json={'login':body['login'],'password':pw})
                check(r.status_code==200,'USER-01 new login '+role)
                perms=r.json()['user']['permissions']; token=r.json()['access_token']
                expected=[200,403 if role=='NONE' else 200,200 if 'ADMIN' in roles else 403,200 if 'ADMIN' in roles else 403]
                actual=[d.get('/api/v1/'+p).status_code for p in ['auth/me','dashboard','users','version']]
                check(actual==expected,'RBAC-01 real GET endpoints '+role)
                r=d.post('/api/v1/users',json={**body,'login':'child_'+role.lower()},headers=O)
                check(r.status_code==(201 if 'ADMIN' in roles else 403),'RBAC-01 real POST '+role)
                if role=='COMBINED':check('decision.create' in perms and 'rule.activate' not in perms,'RBAC-03 combined roles')
                if role=='ADMIN':check('decision.create' not in perms,'RBAC-03 no implicit business rights')
        for data in ['{', '{"login":"x","password":"x","extra":1}', '{"login":"","password":""}']:
            check(c.post('/api/v1/auth/login',content=data,headers={'Content-Type':'application/json'}).status_code==422,'AUTH-04 malformed/extra/empty')
        body={'login':'csrf_target','full_name':'Review','password':pw,'roles':[]}
        for headers in [{},{'Origin':'https://evil.invalid'}]:
            check(c.post('/api/v1/users',json=body,headers=headers).status_code==403,'CSRF-01 user create forbidden')
        for extra in [{'status':'ACTIVE'},{'password_hash':'bad'},{'roles':['SUPER_ADMIN']},{'password':'short'},{'password':'x'*129}]:
            check(c.post('/api/v1/users',json={**body,**extra},headers=h).status_code==422,'USER-03 reject invalid fields')
        for auth in ['Bearer forged','Bearer '+'x'*257,'Basic invalid']:
            check(c.get('/api/v1/auth/me',headers={'Authorization':auth}).status_code==401,'SESSION-03 no cookie fallback')
        with Session(engine) as s:
            record=s.get(AuthSession,token_digest(admin)); check(record is not None,'STORE-01 digest only')
            check(s.get(AuthSession,admin) is None,'STORE-01 raw token absent')
            record.created_at=datetime.now(UTC)-timedelta(minutes=6); s.commit()
        check(c.post('/api/v1/users',json=body,headers=h).status_code==403,'USER-04 stale admin denied')
        r=c.post('/api/v1/auth/login',json={'login':'review_admin','password':pw},headers=O)
        check(r.status_code==200 and r.json()['access_token']!=admin,'STORE-01 distinct tokens')
        check(c.post('/api/v1/users',json=body,headers=O).status_code==201,'USER-04 reauthentication restores creation')
        with Session(engine) as s:
            events=s.scalars(select(AuditEvent)).all(); payload=repr([e.payload for e in events])
            check(pw not in payload and admin not in payload,'AUDIT-02 no credentials in payload')
            check({'USER_CREATED','ROLES_ASSIGNED','AUTH_LOGIN'} <= {e.event_type for e in events},'AUDIT-01 event types')
    lim=cfg.model_copy(update={'auth_rate_prefix':cfg.auth_rate_prefix+'extra:','login_account_limit':100,'login_ip_limit':2,'login_window_seconds':2})
    with TestClient(create_app(settings=lim),base_url='https://localhost:8443') as c:
        codes=[c.post('/api/v1/auth/login',json={'login':'missing'+str(i),'password':'incorrect'},headers={'X-Forwarded-For':'192.0.2.'+str(i)}).status_code for i in range(3)]
        check(codes==[401,401,429],'FAIL-02 peer IP limit ignores forged XFF')
        time.sleep(2.2)
        check(c.post('/api/v1/auth/login',json={'login':'missing','password':'incorrect'}).status_code==401,'FAIL-01 limit window expires (2s isolated configuration)')
    badredis=cfg.model_copy(update={'redis_url':SecretStr('redis://127.0.0.1:1/0')})
    with TestClient(create_app(settings=badredis),base_url='https://localhost:8443') as c:
        check(c.post('/api/v1/auth/login',json={'login':'review_admin','password':pw}).status_code==503,'FAIL-03 real Redis connection failure fails closed')
    badurl=make_url(cfg.database_url.get_secret_value()).set(port=1).render_as_string(hide_password=False)
    badpg=cfg.model_copy(update={'database_url':SecretStr(badurl)})
    with TestClient(create_app(settings=badpg),base_url='https://localhost:8443',raise_server_exceptions=False) as c:
        check(c.get('/api/v1/health').status_code==503,'FAIL-04 unreachable PostgreSQL health degraded')
        r=c.get('/api/v1/auth/me',headers=h)
        check(r.status_code==500 and 'Traceback' not in r.text and pw not in r.text,'FAIL-04 PostgreSQL outage no authorization or traceback')
    with TestClient(create_app(settings=cfg),base_url='https://localhost:8443') as c:
        check(c.post('/api/v1/auth/login',json={'login':'review_admin','password':pw}).status_code==200,'FAIL-03/04 healthy configuration recovers')
finally:
    engine.dispose()
    try:next(gen)
    except StopIteration:pass
