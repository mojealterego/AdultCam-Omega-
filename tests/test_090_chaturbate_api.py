"""Protected read-only owner status API; offline fake provider."""
import pytest
from fastapi.testclient import TestClient
from adultcam.app import create_app
from adultcam.platform_status import ChaturbateStatsReadOnly, PlatformStatusError


@pytest.fixture
def api(monkeypatch,tmp_path):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD','a-test-password-long-enough')
    monkeypatch.setenv('ADULTCAM_DB_PATH',str(tmp_path/'test.sqlite3'))
    monkeypatch.setenv('ADULTCAM_CHATURBATE_USERNAME','ownchannel')
    monkeypatch.setenv('ADULTCAM_CHATURBATE_STATS_TOKEN','A'*24)
    monkeypatch.delenv('ADULTCAM_OIDC_ISSUER',raising=False)
    with TestClient(create_app(),base_url='http://localhost') as client:
        yield client


def test_auth_read_only_and_delivery_not_claimed(api,monkeypatch):
    monkeypatch.setattr(ChaturbateStatsReadOnly,'read_status',
        lambda _:{'state':'ONLINE_REPORTED','platform_delivery':'UNVERIFIED'})
    uri='/api/platforms/chaturbate/status'
    assert api.get(uri).status_code==401
    result=api.get(uri,auth=('operator','a-test-password-long-enough'))
    assert result.status_code==200
    assert result.json()['platform_delivery']=='UNVERIFIED'
    assert api.post(uri,auth=('operator','a-test-password-long-enough')).status_code==405


def test_upstream_credentials_are_never_returned(api,monkeypatch):
    def fail(_):raise PlatformStatusError('UPSTREAM_401')
    monkeypatch.setattr(ChaturbateStatsReadOnly,'read_status',fail)
    result=api.get('/api/platforms/chaturbate/status',auth=('operator','a-test-password-long-enough'))
    assert result.status_code==503
    assert 'A'*24 not in result.text
