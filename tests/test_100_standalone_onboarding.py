"""Offline account slots are never real provider connections."""
import os
import pytest
from fastapi.testclient import TestClient
from adultcam.app import create_app

@pytest.fixture
def api(tmp_path,monkeypatch):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD','long-test-operator-password-verified')
    monkeypatch.setenv('ADULTCAM_DB_PATH',str(tmp_path/'slots.sqlite'))
    monkeypatch.setenv('ADULTCAM_OPERATION_MODE','OFFLINE_LAB')
    monkeypatch.setenv('ADULTCAM_OBS_ALLOWED_SERVERS','rtmps://remote.invalid/live')
    monkeypatch.setenv('ADULTCAM_CHATURBATE_USERNAME','valid_name')
    monkeypatch.setenv('ADULTCAM_CHATURBATE_STATS_TOKEN','never-use-this-secret')
    with TestClient(create_app(),base_url='http://localhost') as c:
        c.auth=('operator','long-test-operator-password-verified')
        c.headers['X-AdultCam-Request']='1'
        yield c

def create_slot(api,label='test'):
    return api.post('/api/platform-connections',json={
        'platform_id':'chaturbate','account_label':label})

def test_lab_mode_has_no_external_reads(api):
    health=api.get('/api/health').json()
    assert health['operation_mode']=='OFFLINE_LAB'
    assert health['external_platform_integrations']=='DISABLED_BY_LAB_MODE'
    assert api.get('/api/platforms/chaturbate/status').status_code==409
    assert api.get('/api/platform-registry').json()['external_requests_sent']==0

def test_plan_account_is_never_connected(api):
    result=create_slot(api)
    assert result.status_code==201,result.text
    item=result.json()
    assert item['status']=='NOT_CONNECTED' and not item['connected']
    assert item['external_requests_sent']==0
    assert len(api.get('/api/platform-connections').json()['connections'])==1
    assert 'never-use-this-secret' not in api.get('/api/platform-connections').text

def test_prepare_remains_unconnected(api):
    item=create_slot(api).json()
    result=api.post('/api/platform-connections/'+str(item['id'])+'/prepare')
    assert result.status_code==200
    assert result.json()['status']=='AWAITING_AUTHORIZATION'
    assert result.json()['connected'] is False
    assert result.json()['external_requests_sent']==0

def test_rejects_secrets_unknown_services_and_duplicates(api):
    assert api.post('/api/platform-connections',json={
        'platform_id':'chaturbate','account_label':'xxyy','token':'secret'}).status_code==422
    assert api.post('/api/platform-connections',json={
        'platform_id':'http://127.0.0.1','account_label':'xxyy'}).status_code==422
    assert create_slot(api,'Alfa').status_code==201
    assert create_slot(api,'alfa').status_code==409
    assert any(e['kind']=='PLATFORM_SLOT_CREATED' for e in
               api.get('/api/dashboard').json()['events'])

def test_disable_is_not_account_revocation(api):
    slot=create_slot(api).json()['id']
    result=api.post('/api/platform-connections/'+str(slot)+'/disable')
    assert result.status_code==200
    assert result.json()['status']=='DISABLED'
    assert not result.json()['external_revocation_performed']
    assert api.post('/api/platform-connections/'+str(slot)+'/prepare').status_code==409

def test_lab_start_is_blocked_even_with_allowlisted_external_server(api):
    assert api.post('/api/attestations',json={
        'adults_verified':True,'informed_consent':True,
        'account_authorized':True,'terms_checked':True}).status_code==201
    sid=api.post('/api/sessions',json={'title':'offline'}).json()['id']
    assert api.post('/api/sessions/'+str(sid)+'/transition',
                    json={'to_state':'READY'}).status_code==200
    assert api.post('/api/actions',json={'session_id':sid,
                    'operation':'start_stream','idempotency_key':'once'}).status_code==409

def test_local_slots_persist_after_restart(tmp_path,monkeypatch):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD','long-test-operator-password-verified')
    monkeypatch.setenv('ADULTCAM_DB_PATH',str(tmp_path/'durable.sqlite'))
    monkeypatch.setenv('ADULTCAM_OPERATION_MODE','OFFLINE_LAB')
    with TestClient(create_app(),base_url='http://localhost') as one:
        one.auth=('operator','long-test-operator-password-verified')
        one.headers['X-AdultCam-Request']='1'
        assert create_slot(one,'durable').status_code==201
    with TestClient(create_app(),base_url='http://localhost') as two:
        two.auth=('operator','long-test-operator-password-verified')
        assert two.get('/api/platform-connections').json()['connections'][0]['account_label']=='durable'

def test_lab_launcher_is_hard_pinned(monkeypatch):
    from adultcam.app import serve_standalone
    got=[]
    monkeypatch.setattr('adultcam.app.serve',lambda:got.append(os.getenv('ADULTCAM_OPERATION_MODE')))
    monkeypatch.setenv('ADULTCAM_OPERATION_MODE','STANDARD')
    serve_standalone()
    assert got==['OFFLINE_LAB']
    monkeypatch.setenv('ADULTCAM_RELEASE_MODE','production')
    with pytest.raises(RuntimeError):serve_standalone()
