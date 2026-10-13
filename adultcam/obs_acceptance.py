"""A read-only safety gate for a real, locally installed OBS test stream.

This checker never calls StartStream, StopStream or any provider endpoint.
It does NOT verify the contents of the scene or downstream receipt.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlsplit

from .obs import request as obs_request

TEST_SCENE = 'ADULTCAM_SYNTHETIC_TEST'
TEST_KEY = 'omega-test'


def check_test_readiness(rpc, url: str, password: str, *, port: int) -> dict:
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError('Port odbiornika musi mieścić się w zakresie 1024–65535.')
    parts = urlsplit(url)
    if (parts.scheme != 'ws' or parts.hostname not in ('127.0.0.1', 'localhost') or
            parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError('OBS WebSocket musi być podłączony wyłącznie przez loopback.')
    if not password:
        raise ValueError('Wymagane lokalne hasło OBS WebSocket.')

    receipt = {'result': 'BLOCKED', 'reason_code': 'OBS_READ_FAILED',
               'obs_tested': False, 'obs_command_sent': False,
               'expected_scene': TEST_SCENE, 'network_scope': '127.0.0.1_ONLY',
               'platform_delivery': 'UNVERIFIED'}
    try:
        status = rpc(url, password, 'GetStreamStatus')
        if status.get('outputActive') is not False or status.get('outputReconnecting') is True:
            receipt['reason_code'] = 'ALREADY_ACTIVE'
            return receipt
        scene = rpc(url, password, 'GetCurrentProgramScene')
        if scene.get('currentProgramSceneName') != TEST_SCENE:
            receipt['reason_code'] = 'WRONG_SCENE'
            return receipt
        service = rpc(url, password, 'GetStreamServiceSettings')
        settings = service.get('streamServiceSettings')
        if service.get('streamServiceType') != 'rtmp_custom' or not isinstance(settings, dict):
            receipt['reason_code'] = 'WRONG_DESTINATION'
            return receipt
        if settings.get('server') != f'rtmp://127.0.0.1:{port}/live':
            receipt['reason_code'] = 'WRONG_DESTINATION'
            return receipt
        if settings.get('key') != TEST_KEY:
            receipt['reason_code'] = 'TEST_KEY_NOT_SET'
            return receipt
    except Exception:
        # Deliberately never return exception descriptions containing credentials.
        return receipt
    receipt['result'] = 'READY_FOR_MANUAL_TEST'
    receipt['reason_code'] = None
    receipt['obs_tested'] = True
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Read-only gate for a local, real OBS synthetic RTMP test')
    parser.add_argument('--check', action='store_true', required=True,
                        help='Check local OBS; never start/stop stream')
    parser.add_argument('--port', type=int, default=19350)
    args = parser.parse_args(argv)
    try:
        report = check_test_readiness(obs_request,
                    os.getenv('OBS_WS_URL', 'ws://127.0.0.1:4455'),
                    os.getenv('OBS_WS_PASSWORD', ''), port=args.port)
    except ValueError as exc:
        parser.exit(2, f'{exc}\n')
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report['result'] == 'READY_FOR_MANUAL_TEST' else 2


if __name__ == '__main__':
    sys.exit(main())
