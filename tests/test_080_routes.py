"""Routing plans remain local and unverified, even with owned ingest evidence."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from adultcam.app import create_app
from adultcam.database import Database


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD', 'a-valid-local-operator-password')
    monkeypatch.setenv('ADULTCAM_DB_PATH', str(tmp_path / 'routes.sqlite3'))
    monkeypatch.setenv('ADULTCAM_INGEST_HMAC_KEY', 'a' * 40)
    monkeypatch.setenv('ADULTCAM_INGEST_RECEIVERS', 'alpha,beta')
    monkeypatch.delenv('ADULTCAM_OIDC_ISSUER', raising=False)
    with TestClient(create_app(), base_url='http://localhost') as client:
        client.auth = ('operator', 'a-valid-local-operator-password')
        client.headers['X-AdultCam-Request'] = '1'
        client.state_db_path = str(tmp_path / 'routes.sqlite3')
        yield client


def new_session(api):
    response = api.post('/api/sessions', json={'title':'Synthetic simulcast'})
    assert response.status_code == 201, response.text
    return response.json()['id']


def route(api, sid, key='alpha', audience='PUBLIC', capability='OWNED_INGEST_TEST'):
    return api.post('/api/routes', json={
        'session_id':sid, 'route_key':key, 'platform':'OWNED_LAB',
        'audience':audience, 'capability':capability,
        'receiver_id': key if capability=='OWNED_INGEST_TEST' else None
    })


def proof(api, sid, receiver, nonce):
    body={'receiver_id':receiver,'session_id':sid,'nonce':nonce,'received_frames':10,
          'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
          'transport':'RTMPS','scope':'OWNED_INGEST'}
    msg=json.dumps(body,sort_keys=True,separators=(',',':'),
                   ensure_ascii=False,allow_nan=False).encode('utf-8')
    sig=hmac.new(b'a'*40,msg,hashlib.sha256).hexdigest()
    return api.post('/api/ingest/receipts',json=body,
                    headers={'X-AdultCam-Ingest-Signature':sig})


def test_two_signed_receivers_never_confirm_external_platform(api):
    sid=new_session(api)
    for receiver in ('alpha','beta'):
        r=route(api,sid,receiver)
        assert r.status_code==201 and r.json()['execution_state']=='PLAN_ONLY', r.text
        assert proof(api,sid,receiver,'unique-nonce-'+receiver+'-for-test-123456').status_code==201
    result=api.get('/api/routes/evaluate',params={'session_id':sid,'audience':'PUBLIC'}).json()
    assert result['decision']=='LAB_EVIDENCE_ONLY'
    assert result['owned_receivers_with_fresh_proof']==2
    assert result['external_actions_performed']==0
    assert result['platform_delivery']=='UNVERIFIED'
    assert result['private_transition_authorized'] is False


def test_private_is_blocked_if_public_plan_remains(api):
    sid=new_session(api)
    assert route(api,sid,'alpha','PRIVATE').status_code==201
    assert route(api,sid,'beta','PUBLIC').status_code==201
    result=api.get('/api/routes/evaluate',params={'session_id':sid,'audience':'PRIVATE'}).json()
    assert result['decision']=='BLOCKED_PUBLIC_ROUTE'
    assert result['private_transition_authorized'] is False


def test_manual_is_not_connected(api):
    sid=new_session(api)
    assert route(api,sid,'manual','PUBLIC','MANUAL_ONLY').status_code==201
    result=api.get('/api/routes/evaluate',params={'session_id':sid,'audience':'PUBLIC'}).json()
    assert result['decision']=='BLOCKED_MANUAL_ONLY'
    assert result['platform_delivery']=='UNVERIFIED'


def test_routes_require_auth_and_unique_registered_receivers(api):
    sid=new_session(api)
    assert route(api,sid,'alpha').status_code==201
    assert route(api,sid,'alpha').status_code==409
    assert route(api,sid,'unknown').status_code==409
    assert api.post('/api/routes',json={},auth=None).status_code==401
    assert api.post('/api/routes',headers={'X-AdultCam-Request':''},json={}).status_code==403
    assert api.post('/api/routes',json={
        'session_id':sid,'route_key':'unexpected','platform':'X','audience':'PUBLIC',
        'capability':'CONNECTED_API','receiver_id':'beta'}).status_code==422


def test_old_receipt_is_never_current_evidence(api):
    sid=new_session(api)
    assert route(api,sid).status_code==201
    assert proof(api,sid,'alpha','nonce-for-old-evidence-123456789').status_code==201
    old=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat(timespec='seconds')
    with Database(api.state_db_path).connect() as conn:
        conn.execute("UPDATE ingest_receipts SET recorded_at=? WHERE receiver_id='alpha'",(old,))
    result=api.get('/api/routes/evaluate',params={'session_id':sid,'audience':'PUBLIC'}).json()
    assert result['decision']=='BLOCKED_MISSING_FRESH_RECEIPT'
    assert result['owned_receivers_with_fresh_proof']==0


def test_live_route_modification_is_blocked(api):
    sid=new_session(api)
    with Database(api.state_db_path).connect() as conn:
        conn.execute("UPDATE sessions SET state='LIVE_PUBLIC' WHERE id=?",(sid,))
    assert route(api,sid).status_code==409


def test_delete_is_only_local_and_audited(api):
    sid=new_session(api)
    created=route(api,sid)
    rid=created.json()['id']
    out=api.delete(f'/api/routes/{rid}')
    assert out.status_code==200
    assert out.json()['external_actions_performed']==0
    assert api.get('/api/routes',params={'session_id':sid}).json()['routes']==[]
    assert api.delete(f'/api/routes/{rid}').status_code==404
