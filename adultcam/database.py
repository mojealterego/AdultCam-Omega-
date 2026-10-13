"""SQLite persistence with WAL and append-only audit/events."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Database:
    def __init__(self, path: str):
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.initialize()
        if os.name == 'posix':
            os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA busy_timeout = 10000')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        with self.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.executescript('''
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY, platform TEXT NOT NULL, alias TEXT NOT NULL,
                    public_url TEXT, status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                    updated_at TEXT NOT NULL, UNIQUE(platform, alias)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'PREPARE', updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attestations (
                    id INTEGER PRIMARY KEY, attested_at TEXT NOT NULL,
                    adults_verified INTEGER NOT NULL, informed_consent INTEGER NOT NULL,
                    account_authorized INTEGER NOT NULL, terms_checked INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_intents (
                    id INTEGER PRIMARY KEY, operation TEXT NOT NULL, session_id INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
                    risk_class TEXT NOT NULL, policy_decision TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    receipt_json TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY, platform TEXT NOT NULL, category TEXT NOT NULL,
                    currency TEXT NOT NULL, amount_minor INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS obs_reconciliations (
                    action_id INTEGER PRIMARY KEY REFERENCES action_intents(id),
                    observed_active INTEGER NOT NULL CHECK(observed_active IN (0,1)),
                    checked_at TEXT NOT NULL, operator TEXT NOT NULL,
                    result_code TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY, subject TEXT NOT NULL,
                    session_id INTEGER, status TEXT NOT NULL CHECK(status IN ('OPEN','RESOLVED')),
                    reason_code TEXT NOT NULL, occurrences INTEGER NOT NULL,
                    opened_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
                    resolved_at TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_incident_subject
                    ON incidents(subject) WHERE status='OPEN';
                CREATE TABLE IF NOT EXISTS monitor_state (
                    id INTEGER PRIMARY KEY CHECK(id=1),last_checked_at TEXT NOT NULL,
                    last_result TEXT NOT NULL, last_reason_code TEXT,
                    last_observed_active INTEGER CHECK(last_observed_active IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS stream_routes (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    route_key TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    audience TEXT NOT NULL CHECK(audience IN ('PUBLIC','PRIVATE')),
                    capability TEXT NOT NULL CHECK(capability IN ('MANUAL_ONLY','OWNED_INGEST_TEST')),
                    receiver_id TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, route_key),
                    CHECK((capability='MANUAL_ONLY' AND receiver_id IS NULL) OR
                          (capability='OWNED_INGEST_TEST' AND receiver_id IS NOT NULL))
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_route_per_owned_receiver
                  ON stream_routes(session_id, receiver_id)
                  WHERE receiver_id IS NOT NULL;
                CREATE TABLE IF NOT EXISTS ingest_receipts (
                    id INTEGER PRIMARY KEY,
                    receiver_id TEXT NOT NULL,
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    nonce TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    received_frames INTEGER NOT NULL CHECK(received_frames > 0),
                    recorded_at TEXT NOT NULL,
                    UNIQUE(receiver_id, nonce)
                );
                CREATE INDEX IF NOT EXISTS ingest_receipts_by_session
                    ON ingest_receipts(session_id, recorded_at);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL,
                    detail_json TEXT NOT NULL, observed_at TEXT NOT NULL,
                    correlation_id TEXT NOT NULL
                );
            ''')
            # Do not steal another process's in-flight operation during startup.
            # Stale actions (a process crash) remain UNKNOWN, requiring explicit reconciliation.
            self.expire_stale_actions(c)

    @staticmethod
    def expire_stale_actions(c):
        # Individual OBS requests have a five-second timeout; 90 seconds is intentionally
        # much longer than the expected complete operation, and is not a retry.
        stale_before = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat(timespec='seconds')
        c.execute("UPDATE action_intents SET status='UNKNOWN', updated_at=? WHERE status='EXECUTING' AND updated_at < ?",
                  (utc_now(), stale_before))

    @staticmethod
    def event(c, kind: str, subject: str, detail: dict, correlation: str):
        c.execute('INSERT INTO events(kind,subject,detail_json,observed_at,correlation_id) VALUES(?,?,?,?,?)',
                  (kind, subject, json.dumps(detail, ensure_ascii=False), utc_now(), correlation))

    @staticmethod
    def rows(c, query: str, params=()):
        return [dict(row) for row in c.execute(query, params).fetchall()]
