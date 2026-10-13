"""Fail-closed OBS stream control and sanitized broadcast evidence.

The module deliberately does not know accounts, stream keys, or provider APIs.
An OBS output being active is *not* evidence that a remote platform received it.
"""
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class StreamPolicy:
    allowed_servers: frozenset[str]
    required_scene: str | None = None

    @classmethod
    def from_env(cls, raw: str, required_scene: str | None = None) -> 'StreamPolicy':
        values = [item.strip() for item in raw.split(',') if item.strip()]
        approved = frozenset(item for item in values if _valid_destination(item))
        if len(approved) != len(values):
            raise ValueError('Nieprawidłowy adres RTMP/RTMPS na liście dozwolonych serwerów OBS.')
        if required_scene is not None and (not required_scene.strip() or len(required_scene) > 120):
            raise ValueError('Nieprawidłowa nazwa sceny bezpieczeństwa.')
        return cls(approved, required_scene)

    def verify(self, response: dict) -> str | None:
        if not self.allowed_servers:
            return 'DESTINATION_POLICY_NOT_CONFIGURED'
        if not isinstance(response, dict) or response.get('streamServiceType') != 'rtmp_custom':
            return 'UNSUPPORTED_STREAM_SERVICE'
        settings = response.get('streamServiceSettings')
        if not isinstance(settings, dict):
            return 'INVALID_STREAM_SETTINGS'
        server = settings.get('server')
        if not isinstance(server, str) or server not in self.allowed_servers:
            return 'DESTINATION_NOT_ALLOWED'
        if not isinstance(settings.get('key'), str) or not settings['key'].strip():
            return 'MISSING_STREAM_KEY'
        return None


def _valid_destination(value: str) -> bool:
    try:
        parts = urlsplit(value)
        return ((parts.scheme == 'rtmps' or
                 (parts.scheme == 'rtmp' and parts.hostname in {'127.0.0.1', 'localhost'}))
                and bool(parts.hostname)
                and parts.username is None and parts.password is None
                and not parts.query and not parts.fragment and not any(ch.isspace() for ch in value))
    except ValueError:
        return False


def active_value(status: dict) -> bool:
    if not isinstance(status, dict) or type(status.get('outputActive')) is not bool:
        raise ValueError('OBS nie zwrócił jednoznacznej wartości outputActive.')
    return status['outputActive']


def public_status(status: dict) -> dict:
    """Allowlist of non-credential, non-source fields from OBS status."""
    active = active_value(status)
    safe = {'outputActive': active}
    for field in ('outputReconnecting', 'outputCongestion', 'outputSkippedFrames',
                  'outputTotalFrames', 'outputDuration'):
        value = status.get(field)
        if isinstance(value, (bool, float, int)) and not isinstance(value, str):
            safe[field] = value
    return safe


def run_obs_action(rpc, url: str, password: str, operation: str, policy: StreamPolicy) -> dict:
    """Exactly-once-at-most command attempt, with preflight/uncertain outcome distinction."""
    adapter = 'OBS_WEBSOCKET_V5'
    if operation == 'start_stream' and not password:
        return {'status':'FAILED','adapter':adapter,'reason_code':'OBS_AUTH_NOT_CONFIGURED'}
    try:
        current = active_value(rpc(url, password, 'GetStreamStatus'))
        if operation == 'start_stream':
            if current:
                return {'status':'FAILED','adapter':adapter,'reason_code':'OBS_ALREADY_ACTIVE'}
            if not policy.allowed_servers:
                return {'status':'FAILED','adapter':adapter,'reason_code':'DESTINATION_POLICY_NOT_CONFIGURED'}
            destination = rpc(url, password, 'GetStreamServiceSettings')
            denied = policy.verify(destination)
            if denied:
                return {'status':'FAILED','adapter':adapter,'reason_code':denied}
            if policy.required_scene is not None:
                observed_scene = rpc(url, password, 'GetCurrentProgramScene')
                if observed_scene.get('currentProgramSceneName') != policy.required_scene:
                    return {'status':'FAILED','adapter':adapter,'reason_code':'PRIVACY_SCENE_MISMATCH'}
        elif operation == 'stop_stream':
            if not current:
                return {'status':'SUCCEEDED','adapter':adapter,'scope':'OBS_OUTPUT_ONLY',
                        'result':{'outputActive':False, 'already_inactive':True}}
        else:
            return {'status':'FAILED','adapter':adapter,'reason_code':'UNKNOWN_OPERATION'}
    except Exception as exc:
        # No command was transmitted; preflight failed with a known no-action outcome.
        return {'status':'FAILED','adapter':adapter,'reason_code':'PREFLIGHT_FAILED',
                'error_type':type(exc).__name__}

    # After the command begins, transport failure may mean the command did execute.
    try:
        rpc(url, password, 'StartStream' if operation == 'start_stream' else 'StopStream')
        status = rpc(url, password, 'GetStreamStatus')
        observed = active_value(status)
        expected = operation == 'start_stream'
        if expected and status.get('outputReconnecting') is True:
            return {'status':'UNKNOWN','adapter':adapter,'reason_code':'OBS_RECONNECTING',
                    'result':{'outputActive':observed}}
        if observed == expected:
            return {'status':'SUCCEEDED','adapter':adapter,'scope':'OBS_OUTPUT_ONLY',
                    'result':{'outputActive':observed}}
        return {'status':'UNKNOWN','adapter':adapter,'reason_code':'OBS_STATE_MISMATCH',
                'result':{'outputActive':observed}}
    except Exception as exc:
        return {'status':'UNKNOWN','adapter':adapter,'reason_code':'OBS_COMMAND_OUTCOME_UNKNOWN',
                'error_type':type(exc).__name__}
