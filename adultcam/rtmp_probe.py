"""Private, loopback-only RTMP receiver for transport acceptance checks.

This is deliberately not a platform adapter or remote delivery verifier. Frames
are discarded (``-f null -``); no stream keys or user media are retained.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


_FRAME = re.compile(r"^frame=(\\d{1,10})$")


def measure_frames(progress: str) -> int:
    """Count only numeric FFmpeg output progress from the receiving side."""
    numbers = []
    for line in progress.splitlines():
        match = _FRAME.fullmatch(line.strip())
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0)


def _allocate_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def _receiver_command(ffmpeg: str, url: str, duration: int) -> list[str]:
    return [ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'error',
            '-stats_period', '0.2', '-progress', 'pipe:1',
            '-listen', '1', '-i', url, '-t', str(duration),
            '-map', '0:v:0', '-an', '-f', 'null', '-']


def _sender_command(ffmpeg: str, url: str, duration: int) -> list[str]:
    return [ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'error',
            '-re', '-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=5',
            '-t', str(duration), '-c:v', 'flv', '-f', 'flv', url]


def run_private_probe(*, mode: str, port: int, duration: int,
                      confirmed: bool, timeout: int = 45) -> dict:
    """Receive actual RTMP packets on localhost using FFmpeg, without disk writes.

    ``synthetic`` mode sends generated test bars. ``obs`` mode listens for the
    operator's separate local OBS test stream; a positive result proves only
    that media arrived at this private receiver, not which app sent it.
    """
    if mode not in {'synthetic', 'obs'}:
        raise ValueError('Nieobsługiwany tryb testu RTMP.')
    if mode == 'obs' and not confirmed:
        raise ValueError('Tryb OBS wymaga jawnej zgody --confirm-test-only.')
    if type(port) is not int or port != 0 and not 1024 <= port <= 65535:
        raise ValueError('Port: 0 (automatyczny) lub 1024–65535.')
    if mode == 'obs' and port == 0:
        raise ValueError('Dla trybu OBS podaj stały port, np. 19350.')
    if type(duration) is not int or not 2 <= duration <= 120:
        raise ValueError('Czas próbki musi wynosić 2–120 sekund.')
    if type(timeout) is not int or not 10 <= timeout <= 180:
        raise ValueError('Limit całkowity musi wynosić 10–180 sekund.')
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        raise RuntimeError('Brak lokalnego ffmpeg w PATH.')

    listen_port = _allocate_local_port() if port == 0 else port
    # Both source and sink use only loopback. No public endpoint, no RTMPS keys.
    url = f'rtmp://127.0.0.1:{listen_port}/live/omega-test'
    received = 0
    sender_rc: int | None = None
    receiver_rc: int | None = None
    receiver = subprocess.Popen(_receiver_command(ffmpeg, url, duration),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if mode == 'synthetic':
            time.sleep(0.3)
            try:
                sender = subprocess.run(_sender_command(ffmpeg, url, duration),
                                        capture_output=True, timeout=min(timeout, duration + 12),
                                        check=False)
                sender_rc = sender.returncode
            except subprocess.TimeoutExpired:
                sender_rc = None
        try:
            output, _errors = receiver.communicate(timeout=timeout)
            receiver_rc = receiver.returncode
            # FFmpeg's error text may embed network URL/path: never return it.
            received = measure_frames(output.decode('utf-8', 'replace'))
        except subprocess.TimeoutExpired:
            receiver.kill()
            output, _errors = receiver.communicate()
            receiver_rc = receiver.returncode
            received = measure_frames(output.decode('utf-8', 'replace'))
    finally:
        if receiver.poll() is None:
            receiver.kill()
            receiver.communicate()

    verified = (received >= 3 and receiver_rc == 0 and
                (mode == 'obs' or sender_rc == 0))
    return {
        'verification': 'RECEIVER_VIDEO_FRAMES' if verified else 'NOT_VERIFIED',
        'network_scope': '127.0.0.1_ONLY',
        'source': 'GENERATED_COLOR_BARS' if mode == 'synthetic' else 'USER_PROVIDED_LOCAL_RTMP',
        'video_frames': received,
        'receiver_exit_status': receiver_rc,
        'sender_exit_status': sender_rc,
        'obs_tested': False,  # Cannot identify the upstream sender from frame data.
        'platform_delivery': 'UNVERIFIED',
        'wrote_media_files': False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='AdultCam Ω prywatny test transportu RTMP')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-test', action='store_true', help='Generuj syntetyczne klatki na loopback')
    modes.add_argument('--listen-obs', action='store_true', help='Nasłuch lokalnego testowego strumienia OBS')
    parser.add_argument('--confirm-test-only', action='store_true', help='Potwierdź test bez prawdziwej emisji')
    parser.add_argument('--port', type=int, default=19350)
    parser.add_argument('--duration', type=int, default=5)
    parser.add_argument('--timeout', type=int, default=45)
    args = parser.parse_args(argv)
    try:
        report = run_private_probe(mode='obs' if args.listen_obs else 'synthetic',
                                   port=args.port, duration=args.duration,
                                   confirmed=args.confirm_test_only, timeout=args.timeout)
    except (RuntimeError, ValueError) as exc:
        parser.exit(2, f'{exc}\\n')
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report['verification'] == 'RECEIVER_VIDEO_FRAMES' else 2


if __name__ == '__main__':
    sys.exit(main())
