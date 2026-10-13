"""Local real RTMPS/TLS media probe with generated, synthetic frames only.

This does not test OBS Studio or remote delivery to any streaming platform.
"""
from __future__ import annotations

import json
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .rtmp_probe import measure_frames


def _available_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _bridge(connection: ssl.SSLSocket, source_port: int) -> None:
    try:
        with connection, socket.create_connection(('127.0.0.1', source_port), timeout=8) as upstream:
            stop = threading.Event()

            def pump(src: socket.socket, dst: socket.socket) -> None:
                try:
                    while not stop.is_set():
                        data = src.recv(65536)
                        if not data:
                            break
                        dst.sendall(data)
                except (OSError, ssl.SSLError):
                    pass
                finally:
                    stop.set()
                    try:
                        dst.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass

            t = threading.Thread(target=pump, args=(connection, upstream), daemon=True)
            t.start()
            pump(upstream, connection)
            t.join(timeout=8)
    except (OSError, ssl.SSLError):
        return


def _tls_front(ssl_ctx: ssl.SSLContext, port: int, source_port: int, ready: threading.Event) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', port))
        server.listen(1)
        server.settimeout(15)
        ready.set()
        try:
            conn, _addr = server.accept()
            with ssl_ctx.wrap_socket(conn, server_side=True) as wrapped:
                _bridge(wrapped, source_port)
        except (OSError, ssl.SSLError):
            return


def synthetic_tls_roundtrip(*, duration: int = 3) -> dict:
    """Send synthetic FFmpeg video through authenticated local TLS into FFmpeg RTMP sink."""
    if type(duration) is not int or not 2 <= duration <= 30:
        raise ValueError('RTMPS test duration must be 2..30 seconds.')
    ffmpeg, openssl = shutil.which('ffmpeg'), shutil.which('openssl')
    if not ffmpeg or not openssl:
        raise RuntimeError('FFmpeg and OpenSSL are required.')
    with tempfile.TemporaryDirectory(prefix='adultcam-rtmps-') as directory:
        cert = Path(directory) / 'cert.pem'
        key = Path(directory) / 'key.pem'
        issued = subprocess.run([
            openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
            '-keyout', str(key), '-out', str(cert), '-days', '1',
            '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
        ], capture_output=True, timeout=15)
        if issued.returncode != 0:
            raise RuntimeError('Cannot create local ephemeral certificate.')
        tls_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        tls_ctx.load_cert_chain(str(cert), str(key))
        plain_port, tls_port = _available_port(), _available_port()
        if plain_port == tls_port:
            tls_port = _available_port()
        plain_url = f'rtmp://127.0.0.1:{plain_port}/live/omega-test'
        tls_url = f'rtmps://127.0.0.1:{tls_port}/live/omega-test'
        receiver = subprocess.Popen([
            ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-stats_period', '0.2', '-progress', 'pipe:1',
            '-listen', '1', '-i', plain_url,
            '-t', str(duration), '-map', '0:v:0', '-an', '-f', 'null', '-',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ready = threading.Event()
        front = threading.Thread(target=_tls_front, args=(tls_ctx, tls_port, plain_port, ready), daemon=True)
        front.start()
        ready.wait(timeout=3)
        received = 0
        try:
            time.sleep(0.4)
            sender = subprocess.run([
                ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-re', '-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=5',
                '-t', str(duration), '-c:v', 'flv', '-f', 'flv',
                '-tls_verify', '1', '-ca_file', str(cert), tls_url,
            ], capture_output=True, timeout=duration + 18)
            try:
                out, _err = receiver.communicate(timeout=duration + 12)
                received = measure_frames(out.decode('utf-8', 'replace'))
            except subprocess.TimeoutExpired:
                receiver.kill()
                out, _err = receiver.communicate()
                received = measure_frames(out.decode('utf-8', 'replace'))
        finally:
            if receiver.poll() is None:
                receiver.kill()
                receiver.communicate()
            front.join(timeout=3)
        verified = sender.returncode == 0 and receiver.returncode == 0 and received >= 3
        return {'verification': 'RECEIVER_VIDEO_FRAMES' if verified else 'NOT_VERIFIED',
                'tls_verified': bool(verified), 'network_scope': '127.0.0.1_ONLY',
                'video_frames': received, 'sender_exit_status': sender.returncode,
                'receiver_exit_status': receiver.returncode,
                'platform_delivery': 'UNVERIFIED', 'obs_tested': False,
                'source': 'SYNTHETIC_TEST_PATTERN', 'wrote_media_files': False}


def main() -> int:
    try:
        result = synthetic_tls_roundtrip()
        print(json.dumps(result, sort_keys=True))
        return 0 if result['verification'] == 'RECEIVER_VIDEO_FRAMES' else 2
    except (RuntimeError, ValueError, subprocess.TimeoutExpired):
        print('RTMPS test failed or timed out (no media details logged).', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
