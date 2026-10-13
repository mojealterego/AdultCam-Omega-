"""Real loopback websocket protocol integration, using an in-process OBS mock.

No connection to an external platform or actual live broadcast is made.
"""
import json
import threading

from fastapi.testclient import TestClient
from websockets.sync.server import serve

from adultcam.app import create_app
from adultcam.obs import auth_response

PASS = 'mock-OBS-only-strong-password'
SALT = 'lM1GncleQOaCu9lT1yeUZhFYnqhsLLP1G5lAGo3ixaI='
CHALLENGE = '+IxH4CnCiqpX1rM9scsNynZzbOe4KhDeYcTNS3PDaeY='
DEST = 'rtmps://mock-ingest.example.invalid/live'


def test_authenticated_obs_v5_wire_start_and_stop_with_secret_redaction(tmp_path, monkeypatch):
    state = {'live': False, 'verified_identifications': 0, 'rpc': []}

    def handler(ws):
        ws.send(json.dumps({'op': 0, 'd': {'rpcVersion': 1,
                                        'authentication': {'salt': SALT, 'challenge': CHALLENGE}}}))
        ident = json.loads(ws.recv())
        assert ident['op'] == 1
        assert ident['d']['authentication'] == auth_response(PASS, SALT, CHALLENGE)
        state['verified_identifications'] += 1
        ws.send(json.dumps({'op':2,'d':{'negotiatedRpcVersion':1}}))
        req = json.loads(ws.recv())
        assert req['op'] == 6
        kind = req['d']['requestType']
        state['rpc'].append(kind)
        if kind == 'StartStream':
            state['live'] = True
            result = {}
        elif kind == 'StopStream':
            state['live'] = False
            result = {}
        elif kind == 'GetStreamStatus':
            result = {'outputActive': state['live'],'hiddenInternal':'DO_NOT_RETURN_THIS'}
        elif kind == 'GetStreamServiceSettings':
            result = {'streamServiceType':'rtmp_custom',
                      'streamServiceSettings':{'server':DEST, 'key':'PRIVATE_STREAM_KEY',
                                               'password':'PRIVATE_SERVICE_PASSWORD'}}
        else:
            raise AssertionError(f'Unexpected RPC: {kind}')
        ws.send(json.dumps({'op':7,'d':{'requestType':kind,
                                      'requestId':req['d']['requestId'],
                                      'requestStatus':{'result':True,'code':100},
                                      'responseData':result}}))

    with serve(handler, '127.0.0.1', 0) as srv:
        port = srv.socket.getsockname()[1]
        thread=threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD', 'only-for-this-test-password')
        monkeypatch.setenv('ADULTCAM_DB_PATH', str(tmp_path / 'adultcam.sqlite3'))
        monkeypatch.setenv('OBS_WS_URL', f'ws://127.0.0.1:{port}')
        monkeypatch.setenv('OBS_WS_PASSWORD', PASS)
        monkeypatch.setenv('ADULTCAM_OBS_ALLOWED_SERVERS', DEST)
        with TestClient(create_app(), base_url='http://localhost') as api:
            api.auth = ('operator','only-for-this-test-password')
            api.headers['X-AdultCam-Request'] = '1'
            assert api.post('/api/attestations',json={
                'adults_verified': True, 'informed_consent':True,
                'account_authorized':True,'terms_checked':True}).status_code == 201
            sid = api.post('/api/sessions', json={'title':'dummy OBS wire'}).json()['id']
            assert api.post(f'/api/sessions/{sid}/transition',json={'to_state':'READY'}).status_code == 200
            start = api.post('/api/actions', json={'operation':'start_stream',
                                                    'session_id':sid,'idempotency_key':'wire-start'}).json()['id']
            a = api.post(f'/api/actions/{start}/approve', headers={'X-AdultCam-Confirm':'I_APPROVE'})
            assert a.status_code == 200
            assert a.json()['receipt']['status']=='SUCCEEDED'
            assert state['live'] is True
            status = api.get('/api/obs/status')
            assert status.json()['status']['outputActive'] is True
            stop = api.post('/api/actions', json={'operation':'stop_stream',
                                                  'session_id':sid,'idempotency_key':'wire-stop'}).json()['id']
            b = api.post(f'/api/actions/{stop}/approve', headers={'X-AdultCam-Confirm':'I_APPROVE'})
            assert b.json()['receipt']['status']=='SUCCEEDED'
            assert state['live'] is False
            assert state['rpc'][:4] == ['GetStreamStatus','GetStreamServiceSettings',
                                      'StartStream','GetStreamStatus']
            assert state['verified_identifications'] == len(state['rpc'])
            dashboard = api.get('/api/dashboard').text
            for secret in ('PRIVATE_STREAM_KEY','PRIVATE_SERVICE_PASSWORD','DO_NOT_RETURN_THIS'):
                assert secret not in dashboard + a.text + b.text + status.text
        srv.shutdown()
        thread.join(timeout=3)
