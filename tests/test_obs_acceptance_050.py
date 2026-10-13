"""Read-only, real OBS hardware admission checks (wire mocked in unit tests)."""
import pytest

from adultcam.obs_acceptance import check_test_readiness


SERVER = 'rtmp://127.0.0.1:19350/live'


def make_rpc(*, server=SERVER, key='omega-test', scene='ADULTCAM_SYNTHETIC_TEST',
             active=False, connecting=False, fail=False):
    called = []

    def rpc(url, password, command):
        called.append(command)
        if fail:
            raise RuntimeError('dangerous-secret-in-error')
        return {
            'GetStreamStatus': {'outputActive': active, 'outputReconnecting': connecting},
            'GetStreamServiceSettings': {
                'streamServiceType': 'rtmp_custom',
                'streamServiceSettings': {'server': server, 'key': key}},
            'GetCurrentProgramScene': {'currentProgramSceneName': scene},
            'GetVersion': {'obsVersion': '31.0.0'},
        }[command]
    return rpc, called


def test_ready_is_read_only_and_cannot_confirm_platform():
    rpc, calls = make_rpc()
    receipt = check_test_readiness(rpc, 'ws://127.0.0.1:4455', 'pwd', port=19350)
    assert receipt['result'] == 'READY_FOR_MANUAL_TEST'
    assert receipt['platform_delivery'] == 'UNVERIFIED'
    assert receipt['obs_tested'] is True
    assert receipt['obs_command_sent'] is False
    assert set(calls) == {'GetStreamStatus', 'GetStreamServiceSettings', 'GetCurrentProgramScene'}


@pytest.mark.parametrize('changes,code', [
    ({'server': 'rtmps://external.invalid/live'}, 'WRONG_DESTINATION'),
    ({'server': 'rtmp://localhost:19350/live'}, 'WRONG_DESTINATION'),
    ({'key': 'some-real-stream-secret'}, 'TEST_KEY_NOT_SET'),
    ({'scene': 'Camera'}, 'WRONG_SCENE'),
    ({'active': True}, 'ALREADY_ACTIVE'),
    ({'connecting': True}, 'ALREADY_ACTIVE'),
    ({'fail': True}, 'OBS_READ_FAILED'),
])
def test_preflight_fail_closed_without_disclosing_keys(changes, code):
    rpc, calls = make_rpc(**changes)
    receipt = check_test_readiness(rpc, 'ws://127.0.0.1:4455', 'pwd', port=19350)
    assert receipt['result'] == 'BLOCKED'
    assert receipt['reason_code'] == code
    assert 'some-real-stream-secret' not in str(receipt)
    assert 'dangerous-secret-in-error' not in str(receipt)
    assert not any(name in calls for name in ('StartStream', 'StopStream'))


def test_remote_obs_endpoint_denied_before_network():
    rpc, calls = make_rpc()
    with pytest.raises(ValueError):
        check_test_readiness(rpc, 'ws://10.0.0.4:4455', 'pwd', port=19350)
    assert calls == []
