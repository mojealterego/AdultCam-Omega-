"""Acceptance tests for fail-closed OBS control without a real broadcast."""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from adultcam import app as app_module
from adultcam.app import create_app

DEST = 'rtmps://ingest.example.invalid/live'


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD', 'local-only-long-password-test')
    monkeypatch.setenv('ADULTCAM_DB_PATH', str(tmp_path / 'state.sqlite3'))
    monkeypatch.setenv('ADULTCAM_OBS_ALLOWED_SERVERS', DEST)
    monkeypatch.setenv('OBS_WS_PASSWORD', 'test-obs-password')
    with TestClient(create_app(), base_url='http://localhost') as client:
        client.auth = ('operator', 'local-only-long-password-test')
        client.headers['X-AdultCam-Request'] = '1'
        yield client


def ready_session(api):
    assert api.post('/api/attestations', json={'adults_verified':True,'informed_consent':True,'account_authorized':True,'terms_checked':True}).status_code == 201
    sid = api.post('/api/sessions', json={'title':'controlled live'}).json()['id']
    assert api.post(f'/api/sessions/{sid}/transition',json={'to_state':'READY'}).status_code == 200
    return sid


def action(api, sid, op, key):
    response = api.post('/api/actions',json={'operation':op,'session_id':sid,'idempotency_key':key})
    assert response.status_code == 201, response.text
    return response.json()['id']


def approve(api, aid):
    return api.post(f'/api/actions/{aid}/approve', headers={'X-AdultCam-Confirm':'I_APPROVE'})


def mock_obs(state, calls, *, server=DEST, key='never-leak-this-stream-key', fail_after_start=False):
    def rpc(url, password, kind):
        calls.append(kind)
        if kind == 'GetStreamServiceSettings':
            return {'streamServiceType':'rtmp_custom','streamServiceSettings':{'server':server,'key':key,'password':'also-secret'}}
        if kind == 'GetStreamStatus':
            return {'outputActive':state['active'], 'outputDuration':2500,'outputSkippedFrames':0,'internalSecret':'do-not-show'}
        if kind == 'StartStream':
            state['active']=True
            if fail_after_start:
                raise OSError('Lost confirmation containing PRIVATE_PASSWORD')
        if kind == 'StopStream':
            state['active']=False
        return {}
    return rpc


def test_host_header_rebinding_rejected(api):
    assert api.get('/api/health', headers={'Host':'evil.example'}).status_code == 400


def test_start_checks_exact_destination_and_does_not_disclose_keys(api, monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls))
    sid=ready_session(api)
    result=approve(api,action(api,sid,'start_stream','good-start'))
    assert result.status_code == 200, result.text
    assert result.json()['receipt']['status']=='SUCCEEDED'
    assert result.json()['receipt']['scope']=='OBS_OUTPUT_ONLY'
    assert calls==['GetStreamStatus','GetStreamServiceSettings','StartStream','GetStreamStatus']
    status=api.get('/api/obs/status')
    assert status.status_code == 200
    assert status.json()['platform_delivery']=='UNVERIFIED'
    dashboard=api.get('/api/dashboard').text
    for secret in ('never-leak-this-stream-key','also-secret','do-not-show'):
        assert secret not in dashboard + result.text + status.text
    stop=approve(api,action(api,sid,'stop_stream','good-stop'))
    assert stop.json()['receipt']['status']=='SUCCEEDED'
    assert calls[-3:]==['GetStreamStatus','StopStream','GetStreamStatus']


def test_unapproved_destination_fail_closed_and_no_start(api,monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls,server='rtmps://unapproved.example.invalid/live'))
    sid=ready_session(api)
    result=approve(api,action(api,sid,'start_stream','blocked-target'))
    assert result.json()['receipt']['status']=='FAILED'
    assert result.json()['receipt']['reason_code']=='DESTINATION_NOT_ALLOWED'
    assert 'StartStream' not in calls
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='READY'


def test_missing_allowlist_blocks_start(api,monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls))
    sid=ready_session(api)
    monkeypatch.delenv('ADULTCAM_OBS_ALLOWED_SERVERS')
    # The policy is configured when the application is started; create another instance with a new DB.
    api.app.state.allowed_servers = frozenset()
    result=approve(api,action(api,sid,'start_stream','no-policy'))
    assert result.json()['receipt']['status']=='FAILED'
    assert 'StartStream' not in calls


def test_unknown_start_blocks_future_starts_until_explicit_reconciliation(api,monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls,fail_after_start=True))
    sid=ready_session(api)
    first=action(api,sid,'start_stream','lost-start')
    receipt=approve(api,first).json()['receipt']
    assert receipt['status']=='UNKNOWN'
    assert 'PRIVATE_PASSWORD' not in str(receipt)
    # Even though the session is still READY, the unknown start is a global safety lock.
    assert api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'next-start'}).status_code==409
    # Reconciliation must be explicitly confirmed; no implicit trust in an API read.
    assert api.post('/api/obs/reconcile',json={'action_id':first}).status_code==403
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls))
    reconciled=api.post('/api/obs/reconcile',json={'action_id':first},headers={'X-AdultCam-Confirm':'I_APPROVE'})
    assert reconciled.status_code==200, reconciled.text
    assert reconciled.json()['observed_active'] is True
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='LIVE_PUBLIC'
    assert api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'third-start'}).status_code==409


def test_reconcile_unknown_inactive_allows_fresh_start(api,monkeypatch):
    calls=[]; state={'active':False}
    def bad_rpc(url,password,kind):
        calls.append(kind)
        if kind=='GetStreamStatus':
            raise ConnectionError('preflight failed')
    monkeypatch.setattr(app_module,'obs_request',bad_rpc)
    sid=ready_session(api)
    first=action(api,sid,'start_stream','first')
    response=approve(api,first)
    assert response.json()['receipt']['status']=='FAILED'  # No RPC to StartStream was issued.
    # Build an unknown outcome: RPC StartStream ran but readback failed.
    state={'active':False}
    counter={'status':0}
    def uncertain_rpc(url,password,kind):
        if kind=='GetStreamStatus':
            counter['status']+=1
            if counter['status'] == 2:
                raise ConnectionError('connection closed after StartStream')
        return mock_obs(state,calls)(url,password,kind)
    monkeypatch.setattr(app_module,'obs_request',uncertain_rpc)
    second=action(api,sid,'start_stream','second')
    assert approve(api,second).json()['receipt']['status']=='UNKNOWN'
    state['active']=False # Operator OBS-side inspection confirms output inactive.
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls))
    res=api.post('/api/obs/reconcile',json={'action_id':second},headers={'X-AdultCam-Confirm':'I_APPROVE'})
    assert res.status_code==200 and res.json()['observed_active'] is False
    assert api.post('/api/actions',json={'operation':'start_stream','session_id':sid,'idempotency_key':'third'}).status_code==201
    assert api.post('/api/obs/reconcile',json={'action_id':second},headers={'X-AdultCam-Confirm':'I_APPROVE'}).status_code==409


def test_active_observer_must_not_override_unverified_destination_on_reconcile(api,monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls,fail_after_start=True))
    sid=ready_session(api)
    aid=action(api,sid,'start_stream','lost')
    assert approve(api,aid).json()['receipt']['status']=='UNKNOWN'
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls,server='rtmps://other.example.invalid/live'))
    res=api.post('/api/obs/reconcile',json={'action_id':aid},headers={'X-AdultCam-Confirm':'I_APPROVE'})
    assert res.status_code==409
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='READY'


def test_concurrent_approvals_only_one_enters_obs(api,monkeypatch):
    entered=threading.Event(); release=threading.Event(); calls=[]; state={'active':False}
    def rpc(url,password,kind):
        if kind=='StartStream':
            entered.set()
            assert release.wait(timeout=5)
        return mock_obs(state,calls)(url,password,kind)
    monkeypatch.setattr(app_module,'obs_request',rpc)
    sid=ready_session(api)
    start=action(api,sid,'start_stream','start-race')
    stop=action(api,sid,'stop_stream','stop-race')
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(approve,api,start)
        assert entered.wait(timeout=5)
        duplicate=approve(api,stop)
        assert duplicate.status_code==409
        release.set()
        assert pending.result(timeout=5).json()['receipt']['status']=='SUCCEEDED'
    assert calls.count('StartStream')==1
    assert calls.count('StopStream')==0


def test_stop_for_another_session_cannot_corrupt_active_session(api, monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls))
    first=ready_session(api)
    assert approve(api,action(api,first,'start_stream','one-start')).json()['receipt']['status']=='SUCCEEDED'
    second=api.post('/api/sessions',json={'title':'not-live'}).json()['id']
    response=api.post('/api/actions',json={'operation':'stop_stream','session_id':second,'idempotency_key':'unsafe-stop'})
    assert response.status_code==409
    assert state['active'] is True
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='PREPARE'


def test_cancel_pending_action_releases_start_lock_without_obs_rpc(api, monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls))
    sid=ready_session(api)
    first=action(api,sid,'start_stream','cancel-me')
    result=api.post(f'/api/actions/{first}/cancel')
    assert result.status_code==200
    assert result.json()['status']=='CANCELLED'
    assert approve(api,first).status_code==409
    assert action(api,sid,'start_stream','fresh') > first
    assert calls==[]


def test_obs_audit_check_enters_and_exits_recovery_from_observed_state(api,monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls))
    sid=ready_session(api)
    assert approve(api,action(api,sid,'start_stream','start')).json()['receipt']['status']=='SUCCEEDED'
    state['active']=False
    check=api.post('/api/obs/check')
    assert check.status_code==200 and check.json()['state']=='RECOVERY'
    assert check.json()['platform_delivery']=='UNVERIFIED'
    state['active']=True
    second=api.post('/api/obs/check')
    assert second.status_code==200 and second.json()['state']=='LIVE_PUBLIC'
    assert len([e for e in api.get('/api/dashboard').json()['events'] if e['kind']=='OBS_STATE_DRIFT'])==2


def test_obs_recovery_active_unapproved_destination_stays_recovery(api,monkeypatch):
    calls=[]; state={'active':False}
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls))
    sid=ready_session(api)
    assert approve(api,action(api,sid,'start_stream','start2')).json()['receipt']['status']=='SUCCEEDED'
    state['active']=False
    assert api.post('/api/obs/check').json()['state']=='RECOVERY'
    state['active']=True
    monkeypatch.setattr(app_module,'obs_request',mock_obs(state,calls,server='rtmps://bad.example.invalid/live'))
    check=api.post('/api/obs/check')
    assert check.status_code==200 and check.json()['state']=='RECOVERY'
    assert check.json()['destination_policy']=='DESTINATION_NOT_ALLOWED'


def test_obs_start_reconnecting_is_not_false_success(api,monkeypatch):
    state={'active':False}; calls=[]
    def rpc(url,password,kind):
        value=mock_obs(state,calls)(url,password,kind)
        if kind=='GetStreamStatus' and state['active']:
            value['outputReconnecting']=True
        return value
    monkeypatch.setattr(app_module,'obs_request',rpc)
    sid=ready_session(api)
    first=action(api,sid,'start_stream','reconnecting')
    result=approve(api,first)
    assert result.json()['receipt']['status']=='UNKNOWN'
    assert result.json()['receipt']['reason_code']=='OBS_RECONNECTING'
    assert api.get('/api/dashboard').json()['sessions'][0]['state']=='READY'
    assert api.post('/api/obs/reconcile', json={'action_id':first},headers={'X-AdultCam-Confirm':'I_APPROVE'}).status_code==409


def test_local_console_security_response_headers(api):
    response = api.get('/')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
