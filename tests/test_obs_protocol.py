"""Local WebSocket fixture: no real broadcaster or external network involved."""
import base64
import json
import socket
import threading

import pytest
from websockets.sync.server import serve

from adultcam.obs import OBSFailure, auth_response, request


def test_auth_response_matches_protocol_sha256_definition():
    # OBS official sample challenge/salt from their generated protocol documentation.
    result = auth_response('supersecretpassword',
                           'lM1GncleQOaCu9lT1yeUZhFYnqhsLLP1G5lAGo3ixaI=',
                           '+IxH4CnCiqpX1rM9scsNynZzbOe4KhDeYcTNS3PDaeY=')
    assert len(base64.b64decode(result)) == 32


def test_obs_websocket_v5_request_round_trip():
    seen = []
    def handler(ws):
        ws.send(json.dumps({'op':0,'d':{'rpcVersion':1}}))
        identify = json.loads(ws.recv())
        seen.append(identify['op'])
        ws.send(json.dumps({'op':2,'d':{'negotiatedRpcVersion':1}}))
        rpc = json.loads(ws.recv())
        seen.append(rpc['d']['requestType'])
        ws.send(json.dumps({'op':7,'d':{
            'requestType':rpc['d']['requestType'],
            'requestId':rpc['d']['requestId'],
            'requestStatus':{'result':True,'code':100},
            'responseData':{'outputActive':False}
        }}))

    with serve(handler,'127.0.0.1',0) as srv:
        port=srv.socket.getsockname()[1]
        t=threading.Thread(target=srv.serve_forever,daemon=True)
        t.start()
        data=request(f'ws://127.0.0.1:{port}','','GetStreamStatus',timeout=3)
        assert data=={'outputActive':False}
        assert seen==[1,'GetStreamStatus']
        srv.shutdown()
        t.join(timeout=3)


def test_obs_refuses_remote_host():
    with pytest.raises(OBSFailure):
        request('ws://localhost:4455@evil.example:4455','bad','StartStream')
    with pytest.raises(OBSFailure):
        request('ws://192.0.2.5:4455','bad','StartStream')
