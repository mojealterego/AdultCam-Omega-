import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from adultcam.database import Database, utc_now


def test_startup_does_not_steal_running_action_but_recovers_stale(tmp_path):
    path = str(tmp_path / 'private' / 'state.sqlite3')
    database = Database(path)
    with database.connect() as c:
        sid = c.execute("INSERT INTO sessions(title,state,updated_at) VALUES ('live','READY',?)", (utc_now(),)).lastrowid
        c.execute("INSERT INTO action_intents(operation,session_id,idempotency_key,status,risk_class,policy_decision,created_at,updated_at) VALUES ('start_stream',?, 'a', 'EXECUTING','R4','ALLOW',?,?)", (sid, utc_now(), utc_now()))
    new_instance = Database(path)
    with new_instance.connect() as c:
        assert c.execute("SELECT status FROM action_intents WHERE id=1").fetchone()[0] == 'EXECUTING'
        old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec='seconds')
        c.execute("UPDATE action_intents SET updated_at=? WHERE id=1", (old,))
    restarted = Database(path)
    with restarted.connect() as c:
        assert c.execute("SELECT status FROM action_intents WHERE id=1").fetchone()[0] == 'UNKNOWN'
    if os.name == 'posix':
        assert (Path(path).stat().st_mode & 0o777) == 0o600
