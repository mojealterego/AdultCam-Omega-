"""Optional safety interlock prevents starting the wrong OBS scene.

Scene-name verification is NOT pixel-level proof of anonymization.
"""
from adultcam.stream_control import StreamPolicy, run_obs_action


def fake_rpc(scene, calls):
    def rpc(_url, _password, op):
        calls.append(op)
        if op == 'GetStreamStatus':
            return {'outputActive': False}
        if op == 'GetStreamServiceSettings':
            return {'streamServiceType':'rtmp_custom',
                    'streamServiceSettings':{'server':'rtmps://ingest.example.test/live','key':'hidden'}}
        if op == 'GetCurrentProgramScene':
            return {'currentProgramSceneName': scene}
        return {}
    return rpc


def test_protected_scene_policy_blocks_incorrect_scene_without_start():
    calls=[]
    policy=StreamPolicy(frozenset({'rtmps://ingest.example.test/live'}), required_scene='OPAQUE_SAFE')
    result=run_obs_action(fake_rpc('UNPROTECTED', calls),'ws://127.0.0.1:4455','password','start_stream',policy)
    assert result['status']=='FAILED'
    assert result['reason_code']=='PRIVACY_SCENE_MISMATCH'
    assert 'StartStream' not in calls


def test_unreadable_scene_fails_closed_before_start():
    calls=[]
    def rpc(url,password,op):
        if op=='GetCurrentProgramScene':
            raise ConnectionError('never-send-camera-input')
        return fake_rpc('SAFE',calls)(url,password,op)
    policy=StreamPolicy(frozenset({'rtmps://ingest.example.test/live'}), required_scene='OPAQUE_SAFE')
    result=run_obs_action(rpc,'ws://127.0.0.1:4455','password','start_stream',policy)
    assert result['status']=='FAILED'
    assert 'StartStream' not in calls
    assert 'never-send-camera-input' not in str(result)


def test_blank_required_scene_cannot_be_configured():
    from pytest import raises
    with raises(ValueError):
        StreamPolicy.from_env('rtmps://ingest.example.test/live', required_scene='  ')
