import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adultcam.app import create_app


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD', 'long-test-password-123456')
    monkeypatch.setenv('ADULTCAM_DB_PATH', str(tmp_path / 'test.sqlite3'))
    monkeypatch.setenv('OBS_WS_URL', 'ws://127.0.0.1:4455')
    monkeypatch.setenv('OBS_WS_PASSWORD', 'test-obs-password')
    monkeypatch.setenv('ADULTCAM_OBS_ALLOWED_SERVERS', 'rtmps://ingest.example.invalid/live')
    app = create_app()
    with TestClient(app, base_url='http://localhost') as client:
        client.auth = ('operator', 'long-test-password-123456')
        client.headers['X-AdultCam-Request'] = '1'
        yield client


def profile(api):
    response = api.post('/api/profiles', json={'platform': 'demo-network', 'alias': 'stage-alias', 'public_url': 'https://example.org/u/stage-alias'})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_authentication_and_csrf(api):
    assert api.get('/api/dashboard', auth=None).status_code == 401
    assert api.get('/api/dashboard').status_code == 200
    assert api.post('/api/profiles', headers={'X-AdultCam-Request': ''}, json={'platform':'demo','alias':'test'}).status_code == 403
    assert api.post('/api/profiles', headers={'Origin': 'https://attacker.invalid'}, json={'platform':'demo','alias':'test'}).status_code == 403


def test_manual_status_deduplicates_events(api):
    p = profile(api)
    a = api.post(f'/api/profiles/{p}/observations', json={'status':'ONLINE', 'source':'MANUAL'}).json()
    b = api.post(f'/api/profiles/{p}/observations', json={'status':'ONLINE', 'source':'MANUAL'}).json()
    assert a['changed'] is True and b['changed'] is False
    d = api.get('/api/dashboard').json()
    assert len(d['profiles']) == 1
    assert d['profiles'][0]['status'] == 'ONLINE'
    assert len([e for e in d['events'] if e['kind']=='PROFILE_STATUS']) == 1
    c = api.post(f'/api/profiles/{p}/observations', json={'status':'OFFLINE','source':'MANUAL'}).json()
    assert c['changed'] is True


def test_broadcast_requires_attestation_and_ready_session(api):
    r = api.post('/api/sessions',json={'title':'Evening show'})
    assert r.status_code == 201
    sid = r.json()['id']
    blocked = api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'first'})
    assert blocked.status_code == 409
    attest = api.post('/api/attestations',json={'adults_verified':True,'informed_consent':True,'account_authorized':True,'terms_checked':True})
    assert attest.status_code == 201
    still_blocked = api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'first'})
    assert still_blocked.status_code == 409
    assert api.post(f'/api/sessions/{sid}/transition',json={'to_state':'READY'}).status_code == 200
    intent = api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'first'})
    assert intent.status_code == 201 and intent.json()['status'] == 'PENDING_APPROVAL'
    duplicate = api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'first'})
    assert duplicate.status_code == 200 and duplicate.json()['id'] == intent.json()['id']
    assert api.get('/api/dashboard').json()['actions'][0]['status'] == 'PENDING_APPROVAL'


def test_invalid_transitions_are_blocked(api):
    sid = api.post('/api/sessions',json={'title':'Morning'}).json()['id']
    assert api.post(f'/api/sessions/{sid}/transition',json={'to_state':'LIVE_PUBLIC'}).status_code == 409
    assert api.post(f'/api/sessions/{sid}/transition',json={'to_state':'READY'}).status_code == 409


def test_revenue_ledger_and_analytics(api):
    r=api.post('/api/ledger',json={'platform':'demo','currency':'USD','amount_minor':1250,'category':'TIP'})
    assert r.status_code == 201
    r=api.post('/api/ledger',json={'platform':'demo','currency':'USD','amount_minor':-250,'category':'REFUND'})
    assert r.status_code == 201
    r=api.post('/api/ledger',json={'platform':'demo','currency':'USD','amount_minor':-5,'category':'TIP'})
    assert r.status_code == 422
    dashboard=api.get('/api/dashboard').json()
    assert dashboard['revenue_by_currency']['USD']==1000
    assert len(dashboard['ledger']) == 2


def test_no_claimed_external_execution(api):
    a = api.post('/api/attestations',json={'adults_verified':True,'informed_consent':True,'account_authorized':True,'terms_checked':True})
    assert a.status_code == 201
    sid = api.post('/api/sessions',json={'title':'show'}).json()['id']
    assert api.post(f'/api/sessions/{sid}/transition',json={'to_state':'READY'}).status_code==200
    action=api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'sample'}).json()
    assert action['status']=='PENDING_APPROVAL'
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='READY'


def test_refuses_unsupported_operations(api):
    assert api.post('/api/actions',json={'operation':'send_mass_messages','session_id':1,'idempotency_key':'x'}).status_code == 422
    assert api.post('/api/profiles', json={'platform': 'x', 'alias':'a', 'public_url':'javascript:alert(1)'}).status_code == 422


def test_operator_receipt_observed_and_no_duplicate_execution(api, monkeypatch):
    from adultcam import app as app_module
    calls=[]
    def fake_obs(url,password,request_type):
        calls.append(request_type)
        if request_type == 'GetStreamStatus':
            return {'outputActive': 'StartStream' in calls and 'StopStream' not in calls}
        if request_type == 'GetStreamServiceSettings':
            return {'streamServiceType':'rtmp_custom', 'streamServiceSettings':{'server':'rtmps://ingest.example.invalid/live','key':'test-private-key'}}
        return {}
    monkeypatch.setattr(app_module,'obs_request',fake_obs)
    api.post('/api/attestations',json={'adults_verified':True,'informed_consent':True,'account_authorized':True,'terms_checked':True})
    sid=api.post('/api/sessions',json={'title':'verified'}).json()['id']
    api.post(f'/api/sessions/{sid}/transition',json={'to_state':'READY'})
    first=api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'unique-key'}).json()
    assert api.post(f"/api/actions/{first['id']}/approve").status_code==403
    result=api.post(f"/api/actions/{first['id']}/approve",headers={'X-AdultCam-Confirm':'I_APPROVE'})
    assert result.status_code==200 and result.json()['receipt']['status']=='SUCCEEDED'
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='LIVE_PUBLIC'
    assert api.post(f"/api/actions/{first['id']}/approve",headers={'X-AdultCam-Confirm':'I_APPROVE'}).status_code==409
    stop=api.post('/api/actions',json={'operation':'stop_stream','session_id':sid,'idempotency_key':'stop-key'}).json()
    result=api.post(f"/api/actions/{stop['id']}/approve",headers={'X-AdultCam-Confirm':'I_APPROVE'})
    assert result.json()['receipt']['status']=='SUCCEEDED'
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='ENDING'
    assert calls == ['GetStreamStatus','GetStreamServiceSettings','StartStream','GetStreamStatus',
                     'GetStreamStatus','StopStream','GetStreamStatus']


def test_emergency_stop_after_start_unknown(api, monkeypatch):
    from adultcam import app as app_module
    def broken_obs(url, password, kind):
        if kind == 'GetStreamStatus':
            return {'outputActive':False}
        if kind == 'GetStreamServiceSettings':
            return {'streamServiceType':'rtmp_custom','streamServiceSettings':{'server':'rtmps://ingest.example.invalid/live','key':'private-key'}}
        if kind == 'StartStream':
            raise OSError('OBS unavailable after attempting StartStream')
    monkeypatch.setattr(app_module,'obs_request', broken_obs)
    api.post('/api/attestations',json={'adults_verified':True,'informed_consent':True,'account_authorized':True,'terms_checked':True})
    sid=api.post('/api/sessions',json={'title':'unsafe reply'}).json()['id']
    api.post(f'/api/sessions/{sid}/transition',json={'to_state':'READY'})
    start=api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'try-start'}).json()
    res=api.post(f"/api/actions/{start['id']}/approve",headers={'X-AdultCam-Confirm':'I_APPROVE'}).json()
    assert res['receipt']['status']=='UNKNOWN'
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='READY'
    stop=api.post('/api/actions',json={'operation':'stop_stream','session_id':sid,'idempotency_key':'emergency'}).json()
    assert stop['status']=='PENDING_APPROVAL'


def test_ready_session_blocks_duplicate_active_start(api):
    api.post('/api/attestations',json={'adults_verified':True,'informed_consent':True,'account_authorized':True,'terms_checked':True})
    sid=api.post('/api/sessions',json={'title':'A'}).json()['id']
    api.post(f'/api/sessions/{sid}/transition',json={'to_state':'READY'})
    assert api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'one'}).status_code==201
    assert api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'two'}).status_code==409


def test_console_html(api):
    content=api.get('/')
    assert content.status_code==200
    assert '<html lang="pl">' in content.text
    assert 'Control Tower' in content.text
