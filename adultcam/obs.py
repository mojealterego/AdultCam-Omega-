"""OBS WebSocket v5 adapter; no credential storage or implicit retries."""
import base64
import hashlib
import json
import uuid
import time
from urllib.parse import urlsplit

from websockets.sync.client import connect


class OBSFailure(RuntimeError):
    pass


def auth_response(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode('utf-8')).digest()).decode('ascii')
    return base64.b64encode(hashlib.sha256((secret + challenge).encode('utf-8')).digest()).decode('ascii')


def request(url: str, password: str, request_type: str, timeout: float = 5.0) -> dict:
    """Execute exactly one OBS v5 RPC; surface transport uncertainty to caller."""
    parsed = urlsplit(url)
    if parsed.scheme != 'ws' or parsed.hostname not in {'127.0.0.1', 'localhost'} or parsed.username or parsed.password:
        raise OBSFailure('OBS WebSocket musi działać lokalnie (127.0.0.1/localhost).')
    deadline = time.monotonic() + timeout
    with connect(url, open_timeout=timeout, close_timeout=timeout, max_size=1_000_000) as ws:
        hello = json.loads(ws.recv(timeout=max(0.01, deadline - time.monotonic())))
        if hello.get('op') != 0 or hello.get('d', {}).get('rpcVersion', 0) < 1:
            raise OBSFailure('Nieobsługiwany protokół OBS WebSocket.')
        identify = {'rpcVersion': 1}
        if password and 'authentication' not in hello['d']:
            raise OBSFailure('OBS WebSocket musi mieć włączone uwierzytelnianie.')
        if 'authentication' in hello['d']:
            if not password:
                raise OBSFailure('OBS wymaga hasła w OBS_WS_PASSWORD.')
            challenge = hello['d']['authentication']
            identify['authentication'] = auth_response(password, challenge['salt'], challenge['challenge'])
        ws.send(json.dumps({'op':1,'d':identify}))
        identified = json.loads(ws.recv(timeout=max(0.01, deadline - time.monotonic())))
        if identified.get('op') != 2:
            raise OBSFailure('OBS nie potwierdził uwierzytelnienia.')
        req_id = str(uuid.uuid4())
        ws.send(json.dumps({'op':6,'d':{'requestType':request_type,'requestId':req_id}}))
        while True:
            if time.monotonic() >= deadline:
                raise OBSFailure('Upłynął całkowity limit czasu żądania OBS.')
            message = json.loads(ws.recv(timeout=max(0.01, deadline - time.monotonic())))
            if message.get('op') == 7 and message.get('d',{}).get('requestId') == req_id:
                response = message['d']
                if not response.get('requestStatus', {}).get('result'):
                    raise OBSFailure(f"OBS odmówił: {response.get('requestStatus', {}).get('code', '?')}")
                return response.get('responseData', {})
