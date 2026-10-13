"""Opt-in local OBS monitor process; exits cleanly on SIGINT/SIGTERM.

Start separately from the HTTP app to avoid duplicate pollers in multi-worker
web servers. No provider writes, no OBS broadcast commands, no retries.
"""
import argparse
import json
import os
import signal
import threading

from .database import Database
from .monitor import monitor_once
from .obs import request as obs_request
from .stream_control import StreamPolicy


def main(argv=None, *, rpc=None, stop_event=None) -> int:
    parser = argparse.ArgumentParser(description='AdultCam local OBS safety monitor')
    parser.add_argument('--once', action='store_true', help='Perform a single OBS status poll')
    parser.add_argument('--interval', type=int, default=30, help='Poll seconds (15–3600)')
    args = parser.parse_args(argv)
    if not args.once and not 15 <= args.interval <= 3600:
        parser.error('--interval must be between 15 and 3600 seconds')
    db = Database(os.getenv('ADULTCAM_DB_PATH',str(__import__('pathlib').Path.home()/'.adultcam-omega'/'adultcam.sqlite3')))
    policy = StreamPolicy.from_env(os.getenv('ADULTCAM_OBS_ALLOWED_SERVERS',''))
    url = os.getenv('OBS_WS_URL','ws://127.0.0.1:4455')
    password = os.getenv('OBS_WS_PASSWORD','')
    stop = stop_event or threading.Event()
    if not args.once and stop_event is None:
        # Runtime-installed signal handlers are only legal in main thread.
        for name in (signal.SIGINT, signal.SIGTERM):
            signal.signal(name,lambda _signum,_frame: stop.set())
    while not stop.is_set():
        result=monitor_once(db,rpc or obs_request,url,password,policy)
        # Only allowed, sanitized status fields are printed; no private URL/key.
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if args.once:
            return 0 if result['outcome'] in ('OK','DEFERRED') else 2
        stop.wait(args.interval)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
