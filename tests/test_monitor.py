"""Monitor safety contract: read-only OBS RPC; durable incidents and no auto-start."""
import pytest
from fastapi.testclient import TestClient

from adultcam import app as app_module
from adultcam.app import create_app
from adultcam.database import Database
from adultcam.monitor import monitor_once
from adultcam.stream_control import StreamPolicy

DEST = 'rtmps://ingest.example.invalid/live'


def fake_obs(active=True, *, offline=False, destination=DEST, reconnecting=False):
    calls = []
    def rpc(url, password, method):
        calls.append(method)
        if offline:
            raise ConnectionError('token-is-secret')
        if method == 'GetStreamStatus':
            return {'outputActive':active, 'outputReconnecting':reconnecting, 'key':'secret'}
        if method == 'GetStreamServiceSettings':
            return {'streamServiceType':'rtmp_custom', 'streamServiceSettings':{'server':destination,'key':'a-private-key'}}
        raise AssertionError('Monitor may not send broadcast commands')
    return rpc, calls


@pytest.fixture
def config(tmp_path):
    return Database(str(tmp_path/'monitor.sqlite3'))


def run(db, rpc):
    return monitor_once(db, rpc, 'ws://127.0.0.1:4455', 'password', StreamPolicy(frozenset({DEST})))


def seed_live(db):
    with db.connect() as c:
        cur = c.execute("INSERT INTO sessions(title,state,updated_at) VALUES('live','LIVE_PUBLIC','2026-10-13T00:00:00+00:00')")
        return cur.lastrowid


def incidents(db):
    with db.connect() as c:
        return [dict(row) for row in c.execute('SELECT * FROM incidents ORDER BY id')]


def test_monitor_detects_failure_without_retry_or_secret_exposure(config):
    sid=seed_live(config)
    rpc,calls=fake_obs(offline=True)
    first=run(config,rpc)
    second=run(config,rpc)
    assert first['outcome']=='ALERT'
    assert first['session_state']=='RECOVERY'
    assert first['platform_delivery']=='UNVERIFIED'
    assert second['new_incident'] is False
    assert len(incidents(config))==1
    assert incidents(config)[0]['occurrences']==2
    assert calls==['GetStreamStatus','GetStreamStatus']
    assert 'token-is-secret' not in str(first)+str(second)+str(incidents(config))
    with config.connect() as c:
        assert c.execute('SELECT state FROM sessions WHERE id=?',(sid,)).fetchone()['state']=='RECOVERY'


def test_monitor_does_not_auto_recover_when_output_returns(config):
    sid=seed_live(config)
    bad,_=fake_obs(active=False)
    assert run(config,bad)['session_state']=='RECOVERY'
    good,calls=fake_obs(active=True)
    recovered=run(config,good)
    assert recovered['outcome']=='ALERT'
    assert recovered['session_state']=='RECOVERY'
    assert recovered['reason_code']=='OPERATOR_RECONCILIATION_REQUIRED'
    assert 'StartStream' not in calls
    with config.connect() as c:
        assert c.execute('SELECT state FROM sessions WHERE id=?',(sid,)).fetchone()['state']=='RECOVERY'


def test_unmanaged_obs_output_creates_one_incident_and_resolves(config):
    rpc,calls=fake_obs(active=True)
    assert run(config,rpc)['reason_code']=='UNMANAGED_OBS_OUTPUT'
    assert run(config,rpc)['new_incident'] is False
    inactive,_=fake_obs(active=False)
    assert run(config,inactive)['outcome']=='OK'
    assert incidents(config)[0]['status']=='RESOLVED'
    assert calls==['GetStreamStatus','GetStreamServiceSettings']*2


def test_destination_mismatch_never_discloses_key(config):
    seed_live(config)
    rpc,calls=fake_obs(active=True,destination='rtmps://other.invalid/live')
    status=run(config,rpc)
    assert status['reason_code']=='DESTINATION_NOT_ALLOWED'
    assert status['session_state']=='RECOVERY'
    assert 'other.invalid' not in str(status)
    assert 'a-private-key' not in str(status)


def test_monitor_defers_during_approval(config):
    seed_live(config)
    with config.connect() as c:
        c.execute("INSERT INTO action_intents(operation,session_id,idempotency_key,status,risk_class,policy_decision,created_at,updated_at) VALUES('start_stream',1,'hold','EXECUTING','R4','ALLOW','2026-10-13T22:00:00+00:00','2999-01-01T00:00:00+00:00')")
    rpc,calls=fake_obs()
    status=run(config,rpc)
    assert status['outcome']=='DEFERRED'
    assert not calls


def test_authenticated_monitor_routes(tmp_path, monkeypatch):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD','very-long-testing-password')
    monkeypatch.setenv('ADULTCAM_DB_PATH',str(tmp_path/'app.sqlite3'))
    monkeypatch.setenv('ADULTCAM_OBS_ALLOWED_SERVERS',DEST)
    monkeypatch.setenv('OBS_WS_PASSWORD','private')
    rpc,calls=fake_obs(active=False)
    monkeypatch.setattr(app_module,'obs_request',rpc)
    with TestClient(create_app(),base_url='http://localhost') as client:
        assert client.get('/api/monitor/status').status_code==401
        client.auth=('operator','very-long-testing-password')
        assert client.get('/api/monitor/status').status_code==200
        assert client.post('/api/monitor/check').status_code==403
        response=client.post('/api/monitor/check',headers={'X-AdultCam-Request':'1'})
        assert response.status_code==200, response.text
        assert response.json()['outcome']=='OK'
        assert client.get('/api/monitor/status').json()['last_result']=='OK'
        assert client.get('/api/platforms/capabilities').json()['verified_integrations']==0


def test_cli_worker_one_shot_records_monitor_state(tmp_path, monkeypatch, capsys):
    from adultcam.monitor_worker import main
    monkeypatch.setenv('ADULTCAM_DB_PATH',str(tmp_path/'state.sqlite3'))
    monkeypatch.setenv('ADULTCAM_OBS_ALLOWED_SERVERS',DEST)
    rpc,calls=fake_obs(active=False)
    assert main(['--once'],rpc=rpc)==0
    assert '"outcome": "OK"' in capsys.readouterr().out
    assert calls==['GetStreamStatus']


def test_cli_worker_interval_bounds(tmp_path, monkeypatch):
    from adultcam.monitor_worker import main
    monkeypatch.setenv('ADULTCAM_DB_PATH',str(tmp_path/'state.sqlite3'))
    with pytest.raises(SystemExit) as err:
        main(['--interval','1'])
    assert err.value.code==2
