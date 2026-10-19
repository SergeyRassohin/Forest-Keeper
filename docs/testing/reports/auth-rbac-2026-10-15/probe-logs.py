import os,sys,json,ssl,subprocess,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from tests.e2e_accounts import main
from unittest.mock import patch
with patch('sys.argv',['e2e_accounts','prepare']):main()
try:
    data=json.loads(Path('../deploy/local/e2e.json').read_text())
    account=data['VIEWER']
    ctx=ssl.create_default_context(cafile='../deploy/local/tls/dev.crt')
    req=urllib.request.Request('https://localhost:8443/api/v1/auth/login',data=json.dumps(account).encode(),headers={'Content-Type':'application/json','Origin':'https://localhost:8443'})
    # Fixture contains only login/password; build the request explicitly.
    req.data=json.dumps({'login':account['login'],'password':account['password']}).encode()
    with urllib.request.urlopen(req,context=ctx) as res: token=json.load(res)['access_token']
    req=urllib.request.Request('https://localhost:8443/api/v1/auth/logout',data=b'',headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,context=ctx) as res: assert res.status==204
    logs=subprocess.run(['docker','compose','logs','--no-color','backend','frontend','worker'],capture_output=True,text=True,check=True).stdout
    assert account['password'] not in logs and token not in logs
    print('PASS AUDIT-02 runtime logs contain neither synthetic password nor raw token')
finally:
    with patch('sys.argv',['e2e_accounts','cleanup']):main()
