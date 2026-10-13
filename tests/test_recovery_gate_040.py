"""Red/green safety tests for explicit, fail-closed OBS recovery."""

import pytest
from fastapi.testclient import TestClient

from adultcam import app as app_module
from adultcam.app import create_app

DEST = 'rtmps://ingest.example.invalid/live'


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD', 'this-is-a-long-test-secret')
    monkeypatch.setenv('ADULTCAM_DB_PATH', str(tmp_path / 'state.sqlite3'))
    monkeypatch.setenv('ADULTCAM_OBS_ALLOWED_SERVERS', DEST)
    monkeypatch.setenv('OBS_WS_PASSWORD', 'test-password')
    with TestClient(create_app(), base_url='http://localhost') as client:
        client.auth = ('operator', 'this-is-a-long-test-secret')
        client.headers['X-AdultCam-Request'] = '1'
        yield client


def live_then_recovery(api, monkeypatch):
    state = {'active': False, 'reconnecting': False, 'server': DEST, 'offline': False, 'calls': []}

    def rpc(url, password, operation):
        state['calls'].append(operation)
        if state['offline']:
            raise ConnectionError('sensitive-token-must-not-escape')
        if operation == 'GetStreamStatus':
            return {'outputActive': state['active'], 'outputReconnecting': state['reconnecting']}
        if operation == 'GetStreamServiceSettings':
            return {'streamServiceType': 'rtmp_custom', 'streamServiceSettings': {
                'server': state['server'], 'key': 'super-secret-key'}}
        if operation == 'StartStream':
            state['active'] = True
        if operation == 'StopStream':
            state['active'] = False
        return {}

    monkeypatch.setattr(app_module, 'obs_request', rpc)
    assert api.post('/api/attestations', json={
        'adults_verified': True, 'informed_consent': True,
        'account_authorized': True, 'terms_checked': True}).status_code == 201
    sid = api.post('/api/sessions', json={'title': 'Controlled test'}).json()['id']
    assert api.post(f'/api/sessions/{sid}/transition', json={'to_state': 'READY'}).status_code == 200
    action = api.post('/api/actions', json={
        'session_id': sid, 'operation': 'start_stream', 'idempotency_key': 'start-once'}).json()['id']
    approved = api.post(f'/api/actions/{action}/approve', headers={'X-AdultCam-Confirm': 'I_APPROVE'})
    assert approved.json()['receipt']['status'] == 'SUCCEEDED'
    state['offline'] = True
    assert api.post('/api/obs/check').json()['state'] == 'RECOVERY'
    state['offline'] = False
    return sid, state


def test_observation_must_not_exit_recovery(api, monkeypatch):
    sid, state = live_then_recovery(api, monkeypatch)
    result = api.post('/api/obs/check')
    assert result.status_code == 200
    assert result.json()['state'] == 'RECOVERY'
    assert result.json()['platform_delivery'] == 'UNVERIFIED'
    assert api.get('/api/dashboard').json()['sessions'][0]['state'] == 'RECOVERY'
    assert state['calls'].count('StartStream') == 1


def test_recovery_requires_explicit_approval_and_verified_output(api, monkeypatch):
    sid, state = live_then_recovery(api, monkeypatch)
    uri = '/api/obs/recovery/approve'
    assert api.post(uri, json={'session_id': sid}).status_code == 403
    state['reconnecting'] = True
    assert api.post(uri, json={'session_id': sid}, headers={'X-AdultCam-Confirm': 'I_APPROVE'}).status_code == 409
    state['reconnecting'] = False
    state['server'] = 'rtmps://other.invalid/live'
    assert api.post(uri, json={'session_id': sid}, headers={'X-AdultCam-Confirm': 'I_APPROVE'}).status_code == 409
    state['server'] = DEST
    result = api.post(uri, json={'session_id': sid}, headers={'X-AdultCam-Confirm': 'I_APPROVE'})
    assert result.status_code == 200, result.text
    assert result.json()['state'] == 'LIVE_PUBLIC'
    assert result.json()['platform_delivery'] == 'UNVERIFIED'
    assert result.json()['obs_command_sent'] is False
    assert state['calls'].count('StartStream') == 1
    assert api.post(uri, json={'session_id': sid}, headers={'X-AdultCam-Confirm': 'I_APPROVE'}).status_code == 409


def test_recovery_failure_is_sanitized_and_never_marks_live(api, monkeypatch):
    sid, state = live_then_recovery(api, monkeypatch)
    state['offline'] = True
    result = api.post('/api/obs/recovery/approve', json={'session_id': sid},
                      headers={'X-AdultCam-Confirm': 'I_APPROVE'})
    assert result.status_code == 503
    assert 'sensitive-token' not in result.text
    assert api.get('/api/dashboard').json()['sessions'][0]['state'] == 'RECOVERY'


def test_recovery_denied_when_attestation_expires(api, monkeypatch, tmp_path):
    from adultcam.database import Database
    sid, state = live_then_recovery(api, monkeypatch)
    with Database(str(tmp_path / 'state.sqlite3')).connect() as c:
        c.execute("UPDATE attestations SET attested_at='2020-01-01T00:00:00+00:00'")
    result = api.post('/api/obs/recovery/approve', json={'session_id': sid},
                      headers={'X-AdultCam-Confirm': 'I_APPROVE'})
    assert result.status_code == 409
    assert api.get('/api/dashboard').json()['sessions'][0]['state'] == 'RECOVERY'
    assert state['calls'].count('StartStream') == 1


def test_recovery_denied_if_output_is_inactive(api, monkeypatch):
    sid, state = live_then_recovery(api, monkeypatch)
    state['active'] = False
    result = api.post('/api/obs/recovery/approve', json={'session_id': sid},
                      headers={'X-AdultCam-Confirm': 'I_APPROVE'})
    assert result.status_code == 409
    assert api.get('/api/dashboard').json()['sessions'][0]['state'] == 'RECOVERY'
