"""Offline Twitch Helix adapter tests; no real API credentials or traffic."""
import httpx
import pytest
from adultcam.platform_status import TwitchHelixReadOnly, PlatformStatusError


def adapter(handler):
    client=httpx.Client(transport=httpx.MockTransport(handler))
    return TwitchHelixReadOnly(client_id='client-only',bearer_token='private-token',
                              broadcaster_id='12345',client=client,monotonic=lambda:1000)


def test_live_helix_status_does_not_claim_delivery():
    requests=[]
    def mock(request):
        requests.append(request)
        assert request.method=='GET'
        assert str(request.url)=='https://api.twitch.tv/helix/streams?user_id=12345'
        assert request.headers['Client-Id']=='client-only'
        assert request.headers['Authorization']=='Bearer private-token'
        return httpx.Response(200,json={'data':[{'id':'s1','user_id':'12345','type':'live'}]})
    obj=adapter(mock)
    value=obj.read_status()
    assert value['state']=='LIVE'
    assert value['platform_delivery']=='UNVERIFIED'
    assert value['broadcast_control']=='DISABLED'
    assert value['content_policy']=='NON_ADULT_ONLY'
    assert obj.read_status()['cached'] is True and len(requests)==1


def test_mismatched_channel_never_reports_live():
    obj=adapter(lambda _:httpx.Response(200,json={'data':[{'id':'s1','user_id':'9999','type':'live'}]}))
    assert obj.read_status()['state']=='UNVERIFIED'


def test_empty_official_result_is_offline_not_delivery_confirmation():
    obj=adapter(lambda _:httpx.Response(200,json={'data':[]}))
    value=obj.read_status()
    assert value['state']=='OFFLINE' and value['platform_delivery']=='UNVERIFIED'


def test_upstream_failures_are_sanitized_without_retries():
    for code in [401,403,429,500]:
        calls=[]
        def respond(_):
            calls.append(1)
            return httpx.Response(code,text='Bearer private-token')
        with pytest.raises(PlatformStatusError) as error:
            adapter(respond).read_status()
        assert error.value.code=='UPSTREAM_'+str(code)
        assert 'private-token' not in str(error.value)
        assert len(calls)==1


def test_credentials_and_id_cannot_inject_query_parameters():
    for cid,token,uid in [('', 'token', '12345'),('id','','12345'),('id','token','1&user_id=999')]:
        with pytest.raises(ValueError):
            TwitchHelixReadOnly(client_id=cid,bearer_token=token,broadcaster_id=uid)
