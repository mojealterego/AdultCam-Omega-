"""Offline official owner stats. No traffic to provider in tests."""
import httpx
import pytest
from adultcam.platform_status import ChaturbateStatsReadOnly, PlatformStatusError


def adapter(handler):
    return ChaturbateStatsReadOnly(username='ownchannel',token='A'*24,
        client=httpx.Client(transport=httpx.MockTransport(handler)),monotonic=lambda:1000)


def test_own_online_stats_do_not_expose_finances_or_token():
    seen=[]
    def mock(req):
        seen.append(req)
        assert req.method=='GET'
        assert req.url.host=='chaturbate.com' and req.url.path=='/statsapi/'
        assert req.url.params['username']=='ownchannel'
        assert req.url.params['token']=='A'*24
        return httpx.Response(200,json={'username':'ownchannel','time_online':25,
                                        'num_viewers':7,'token_balance':500})
    a=adapter(mock);value=a.read_status()
    assert value['state']=='ONLINE_REPORTED'
    assert value['platform_delivery']=='UNVERIFIED'
    assert 'token' not in value and 'token_balance' not in value
    assert 'A'*24 not in repr(value)
    assert a.read_status()['cached'] is True and len(seen)==1


def test_minus_one_offline_status_does_not_prove_delivery():
    value=adapter(lambda _:httpx.Response(200,json={
        'username':'ownchannel','time_online':-1})).read_status()
    assert value['state']=='OFFLINE_REPORTED'
    assert value['platform_delivery']=='UNVERIFIED'


def test_mismatch_and_unexpected_age_are_unverified():
    for data in [{'username':'different','time_online':3},
                 {'username':'ownchannel','time_online':'3'},
                 {'username':'ownchannel','time_online':-999}]:
        assert adapter(lambda _:httpx.Response(200,json=data)).read_status()['state']=='UNVERIFIED'


def test_errors_are_sanitized_and_not_retried():
    seen=[]
    def mock(_):
        seen.append(1)
        return httpx.Response(402,text='secret'+'A'*24)
    with pytest.raises(PlatformStatusError) as e:adapter(mock).read_status()
    assert e.value.code=='UPSTREAM_402'
    assert 'secret' not in str(e.value) and len(seen)==1


def test_input_validation_rejects_invalid_ids_and_tokens():
    for username,token in [('ab&x=1','A'*24),('ownchannel','bad'),('../admin','A'*24)]:
        with pytest.raises(ValueError):
            ChaturbateStatsReadOnly(username=username,token=token)
