from adultcam.monitor import _probe
from adultcam.stream_control import StreamPolicy


def test_privacy_scene_drift_is_reported_as_incident_reason():
    calls=[]
    def rpc(_url, _password, request):
        calls.append(request)
        if request == 'GetStreamStatus': return {'outputActive': True, 'outputReconnecting': False}
        if request == 'GetStreamServiceSettings':
            return {'streamServiceType': 'rtmp_custom',
                    'streamServiceSettings':{'server':'rtmps://my-allowed-ingest.test/live','key':'secret'}}
        if request == 'GetCurrentProgramScene': return {'currentProgramSceneName':'CAMERA_RAW'}
        raise AssertionError(request)
    policy=StreamPolicy(frozenset({'rtmps://my-allowed-ingest.test/live'}), required_scene='ANONYMIZED')
    result=_probe(rpc,'ws://127.0.0.1:4455','password',policy)
    assert result.reason == 'PRIVACY_SCENE_DRIFT'
    assert 'StopStream' not in calls


def test_privacy_scene_matching_allows_monitor_read_only():
    def rpc(_url, _password, request):
        return {'GetStreamStatus': {'outputActive':True},
                'GetStreamServiceSettings': {'streamServiceType':'rtmp_custom',
                    'streamServiceSettings':{'server':'rtmps://my-allowed-ingest.test/live','key':'secret'}},
                'GetCurrentProgramScene': {'currentProgramSceneName':'ANONYMIZED'}}[request]
    result=_probe(rpc,'ws://127.0.0.1:4455','password',
                 StreamPolicy(frozenset({'rtmps://my-allowed-ingest.test/live'}),required_scene='ANONYMIZED'))
    assert result.reason is None
