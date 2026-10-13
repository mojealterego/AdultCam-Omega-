"""Real FFmpeg two-to-eight receiver loopback simulcast test with synthetic video.

Only synthesized color bars are emitted and all FFmpeg endpoints are constructed
as literal 127.0.0.1 RTMP URLs. No media is retained or forwarded remotely.
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time

from .rtmp_probe import _receiver_command, measure_frames


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def run_synthetic_multistream(*, receivers: int = 2, duration: int = 3) -> dict:
    if type(receivers) is not int or not 2 <= receivers <= 8:
        raise ValueError('Liczba prywatnych odbiorników: 2–8.')
    if type(duration) is not int or not 2 <= duration <= 120:
        raise ValueError('Czas testu: 2–120 sekund.')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('Wymagany jest zainstalowany program FFmpeg.')

    ports: set[int] = set()
    while len(ports) < receivers:
        ports.add(_free_tcp_port())
    urls = [f'rtmp://127.0.0.1:{port}/live/synthetic-only'
            for port in sorted(ports)]
    receive_processes: list[subprocess.Popen] = []
    frames = []
    sender_rc = None
    try:
        for url in urls:
            receive_processes.append(subprocess.Popen(
                _receiver_command(ffmpeg, url, duration),
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL))
        time.sleep(0.3)
        # Tee muxer sends exactly the same synthetic frames to all private sinks.
        # No shell, no external URLs, no stream keys, no unsafe fallback output.
        destinations = '|'.join(f'[f=flv:onfail=abort]{url}' for url in urls)
        sender = subprocess.run([
            ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'error', '-re',
            '-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=5',
            '-t', str(duration), '-map', '0:v:0', '-c:v', 'flv',
            '-f', 'tee', destinations,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
           timeout=duration+25, check=False)
        sender_rc = sender.returncode
        receiver_results = []
        for receiver in receive_processes:
            try:
                output, _ = receiver.communicate(timeout=duration+12)
            except subprocess.TimeoutExpired:
                receiver.kill()
                output, _ = receiver.communicate()
            frames.append(measure_frames(output.decode('utf-8', 'replace')))
            receiver_results.append(receiver.returncode)
        verified = (sender_rc == 0 and len(frames) == receivers
                    and all(count >= 3 for count in frames)
                    and all(code == 0 for code in receiver_results))
    except subprocess.TimeoutExpired:
        verified = False
    finally:
        for receiver in receive_processes:
            if receiver.poll() is None:
                receiver.kill()
                receiver.communicate()

    return {
        'result': 'LOCAL_SIMULCAST_VERIFIED' if verified else 'NOT_VERIFIED',
        'receiver_count': receivers,
        'received_frames': frames,
        'sender_exit_code': sender_rc,
        'transport': 'RTMP_LOOPBACK_ONLY',
        'broadcast_to_external_platforms': False,
        'contains_real_people': False,
        'wrote_media_files': False,
        'platform_delivery': 'UNVERIFIED',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='AdultCam Ω prywatny test multistreamingu FFmpeg')
    parser.add_argument('--receivers', type=int, default=2)
    parser.add_argument('--duration', type=int, default=3)
    args = parser.parse_args(argv)
    try:
        result = run_synthetic_multistream(receivers=args.receivers,
                                           duration=args.duration)
    except (RuntimeError, ValueError) as exc:
        parser.exit(2, f'{exc}\n')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['result'] == 'LOCAL_SIMULCAST_VERIFIED' else 2


if __name__ == '__main__':
    sys.exit(main())
