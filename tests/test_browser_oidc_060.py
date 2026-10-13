"""OIDC browser security checks on real FastAPI ASGI and signed test JWTs."""
import base64
from datetime import datetime,timedelta,timezone
from urllib.parse import parse_qs,urlparse
import jwt
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from adultcam.app import create_app


def b64(n):
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length()+7)//8,'big')).rstrip(b'=').decode()


@pytest.fixture
def browser(monkeypatch,tmp_path):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    pub=key.public_key().public_numbers()
    jwks={'keys':[{'kty':'RSA','use':'sig','alg':'RS256','kid':'k',
                   'n':b64(pub.n),'e':b64(pub.e)}]}
    from jwt import PyJWKClient
    monkeypatch.setattr(PyJWKClient,'fetch_data',lambda _:jwks)
    for name,value in {
        'ADULTCAM_AUTH_MODE':'oidc',
        'ADULTCAM_OIDC_ISSUER':'https://identity.example.test/',
        'ADULTCAM_OIDC_AUDIENCE':'adultcam-api',
        'ADULTCAM_OIDC_JWKS_URL':'https://identity.example.test/keys',
        'ADULTCAM_OIDC_AUTHORIZATION_URL':'https://identity.example.test/authorize',
        'ADULTCAM_OIDC_TOKEN_URL':'https://identity.example.test/token',
        'ADULTCAM_OIDC_CLIENT_ID':'operator-ui',
        'ADULTCAM_PUBLIC_ORIGIN':'https://control.example.test',
        'ADULTCAM_DB_PATH':str(tmp_path/'state.sqlite3'),
        'ADULTCAM_ADMIN_PASSWORD':'secret-password-longer-than-16',
    }.items():monkeypatch.setenv(name,value)
    state={'role':'operator','subject':'test-operator','nonce':''}
    def token_pair(*_args,**_kwargs):
        now=datetime.now(timezone.utc)
        shared={'iss':'https://identity.example.test/','sub':state['subject'],
                'iat':now,'exp':now+timedelta(minutes=10)}
        access=jwt.encode({**shared,'aud':'adultcam-api','adultcam_roles':[state['role']]},
                          key,algorithm='RS256',headers={'kid':'k'})
        identity=jwt.encode({**shared,'aud':'operator-ui','nonce':state['nonce']},
                            key,algorithm='RS256',headers={'kid':'k'})
        return {'access_token':access,'id_token':identity}
    from adultcam import browser_auth
    monkeypatch.setattr(browser_auth,'exchange_token',token_pair)
    with TestClient(create_app(),base_url='https://localhost') as client:
        yield client,state


def signin(client,state,role='operator',subject='test-operator'):
    login=client.get('/auth/login',follow_redirects=False)
    assert login.status_code==303
    query=parse_qs(urlparse(login.headers['location']).query)
    assert query['code_challenge_method']==['S256']
    state.update(nonce=query['nonce'][0],role=role,subject=subject)
    callback=client.get('/auth/callback',params={'code':'one-time-code',
                          'state':query['state'][0]},follow_redirects=False)
    assert callback.status_code==303
    assert callback.headers['location']=='/'
    assert 'HttpOnly' in callback.headers['set-cookie']
    assert 'Secure' in callback.headers['set-cookie']
    return client.get('/api/auth/csrf').json()['csrf_token']


def test_browser_login_csrf_and_logout(browser):
    client,state=browser
    csrf=signin(client,state)
    assert client.get('/api/auth/me').json()['source']=='oidc_browser'
    assert client.get('/').status_code==200
    assert client.post('/api/sessions',json={'title':'no csrf'},
                       headers={'Origin':'https://control.example.test',
                                'X-AdultCam-Request':'1'}).status_code==403
    headers={'Origin':'https://control.example.test','X-AdultCam-Request':'1',
             'X-AdultCam-CSRF':csrf}
    assert client.post('/api/sessions',json={'title':'approved'},headers=headers).status_code==201
    session_created=next(x for x in client.get('/api/dashboard').json()['events']
                         if x['kind']=='SESSION_CREATED')
    assert session_created['detail']['operator_subject']=='test-operator'
    assert client.post('/auth/logout',headers=headers).status_code==204
    assert client.get('/api/dashboard').status_code==401


def test_independent_roles_and_revocation(browser):
    admin,state=browser
    csrf=signin(admin,state,'admin','admin-A')
    with TestClient(admin.app,base_url='https://localhost') as viewer:
        signin(viewer,state,'viewer','viewer-B')
        assert viewer.get('/api/dashboard').json()['ledger']==[]
        assert viewer.post('/api/sessions',json={'title':'denied'},
                           headers={'Origin':'https://control.example.test',
                                    'X-AdultCam-Request':'1'}).status_code==403
        assert viewer.get('/api/auth/sessions').status_code==403
        headers={'Origin':'https://control.example.test','X-AdultCam-Request':'1',
                 'X-AdultCam-CSRF':csrf}
        assert admin.post('/api/auth/sessions/revoke',headers=headers,
                          json={'subject':'viewer-B'}).json()['revoked_sessions']==1
        assert viewer.get('/api/dashboard').status_code==401
        assert admin.get('/api/dashboard').status_code==200


def test_weak_public_origin_rejected(browser,monkeypatch):
    monkeypatch.setenv('ADULTCAM_PUBLIC_ORIGIN','http://control.example.test')
    with pytest.raises(ValueError):create_app()
