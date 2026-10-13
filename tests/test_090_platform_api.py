"""Read-only account-scoped endpoint requires user authorization."""
import pytest
from fastapi.testclient import TestClient
from adultcam.app import create_app
from adultcam.platform_status import TwitchHelixReadOnly, PlatformStatusError


@pytest.fixture
def api(monkeypatch,tmp_path):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD','test-password-should-be-long-enough')
    monkeypatch.setenv('ADULTCAM_DB_PATH',str(tmp_path/'test.sqlite3'))
    monkeypatch.setenv('ADULTCAM_TWITCH_CLIENT_ID','client-id')
    monkeypatch.setenv('ADULTCAM_TWITCH_TOKEN','private-token')
    monkeypatch.setenv('ADULTCAM_TWITCH_BROADCASTER_ID','12345')
    monkeypatch.delenv('ADULTCAM_OIDC_ISSUER',raising=False)
    with TestClient(create_app(),base_url='http://localhost') as client:
        yield client


def test_auth_required_and_twitch_is_read_only(api,monkeypatch):
    fake={'state':'LIVE','platform_delivery':'UNVERIFIED','content_policy':'NON_ADULT_ONLY'}
    monkeypatch.setattr(TwitchHelixReadOnly,'read_status',lambda _:fake)
    uri='/api/platforms/twitch/status'
    assert api.get(uri).status_code==401
    result=api.get(uri,auth=('operator','test-password-should-be-long-enough'))
    assert result.status_code==200
    assert result.json()['platform_delivery']=='UNVERIFIED'
    assert result.json()['content_policy']=='NON_ADULT_ONLY'
    assert api.post(uri,auth=('operator','test-password-should-be-long-enough')).status_code==405


def test_transport_errors_do_not_expose_secrets(api,monkeypatch):
    def error(_):raise PlatformStatusError('UPSTREAM_401')
    monkeypatch.setattr(TwitchHelixReadOnly,'read_status',error)
    result=api.get('/api/platforms/twitch/status',
                   auth=('operator','test-password-should-be-long-enough'))
    assert result.status_code==503
    assert result.json()['detail']=='UPSTREAM_401'
    assert 'private-token' not in result.text
