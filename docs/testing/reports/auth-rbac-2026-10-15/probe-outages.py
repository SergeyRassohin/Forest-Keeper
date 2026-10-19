import os,sys,time,subprocess,secrets,json,socket
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path.cwd()))
from app.common.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import SecretStr
from alembic import command
from alembic.config import Config
from app.auth.models import User,UserRole
from app.auth.security import hash_password
from app.common.database import make_engine
from sqlalchemy.orm import Session
suffix=uuid4().hex[:10]; pg='fk-review-pg-'+suffix; redis='fk-review-redis-'+suffix
password=secrets.token_urlsafe(24); env={**os.environ,'POSTGRES_PASSWORD':password}
def docker(*args):return subprocess.run(['docker',*args],capture_output=True,text=True,env=env,check=True).stdout.strip()
def ok(v,label):
    assert v,label
    print('PASS',label,flush=True)
def freeport():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); return sock.getsockname()[1]
pgport=freeport(); redisport=freeport()
try:
    docker('run','-d','--name',pg,'-e','POSTGRES_PASSWORD','-p',f'127.0.0.1:{pgport}:5432','pgvector/pgvector:pg17')
    docker('run','-d','--name',redis,'-p',f'127.0.0.1:{redisport}:6379','redis:7.4-alpine')
    pp=json.loads(docker('inspect',pg))[0]['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort']
    rp=json.loads(docker('inspect',redis))[0]['NetworkSettings']['Ports']['6379/tcp'][0]['HostPort']
    for i in range(50):
        r=subprocess.run(['docker','exec',pg,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True)
        if r.returncode==0:break
        time.sleep(.3)
    url=f'postgresql+psycopg://postgres:{password}@127.0.0.1:{pp}/postgres'
    cfg=Settings(database_url=SecretStr(url),redis_url=SecretStr(f'redis://127.0.0.1:{rp}/0'))
    os.environ['FK_DATABASE_URL']=url
    os.environ['FK_REDIS_URL']=cfg.redis_url.get_secret_value()
    command.upgrade(Config('alembic.ini'),'head')
    e=make_engine(cfg)
    with Session(e) as s:
        s.add(User(login='outage_viewer',full_name='Review',password_hash=hash_password(password),roles=[UserRole(role_code='VIEWER')]))
        s.commit()
    e.dispose()
    with TestClient(create_app(settings=cfg),base_url='https://localhost:8443',raise_server_exceptions=False) as c:
        body={'login':'outage_viewer','password':password}
        r=c.post('/api/v1/auth/login',json=body);ok(r.status_code==200,'outage baseline login')
        token=r.json()['access_token']; h={'Authorization':'Bearer '+token}
        docker('stop','-t','1',redis)
        ok(c.post('/api/v1/auth/login',json=body).status_code==503,'FAIL-03 actual Redis stop denies login')
        docker('start',redis)
        for i in range(50):
            r=subprocess.run(['docker','exec',redis,'redis-cli','ping'],capture_output=True)
            if r.returncode==0 and b'PONG' in r.stdout:break
            time.sleep(.2)
        codes=[]
        for i in range(20):
            code=c.post('/api/v1/auth/login',json=body).status_code; codes.append(code)
            if code==200:break
            time.sleep(.2)
        print('Redis recovery statuses',codes,flush=True)
        ok(codes[-1]==200,'FAIL-03 actual Redis restart recovery')
        docker('stop','-t','1',pg)
        ok(c.get('/api/v1/health').status_code==503,'FAIL-04 actual PostgreSQL stop health503')
        r=c.get('/api/v1/auth/me',headers=h)
        ok(r.status_code==500 and 'Traceback' not in r.text and password not in r.text,'FAIL-04 actual PostgreSQL stop denies API safely')
        docker('start',pg)
        for i in range(50):
            if c.get('/api/v1/health').status_code==200:break
            time.sleep(.3)
        ok(c.get('/api/v1/auth/me',headers=h).status_code==200,'FAIL-04 actual PostgreSQL restart recovers same session')
finally:
    for name in [pg,redis]:subprocess.run(['docker','rm','-f','-v',name],capture_output=True)
