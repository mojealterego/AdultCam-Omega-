"""OBS-only read monitor with persistent, deduplicated incidents.

Monitoring must not send StartStream/StopStream, perform provider writes, or
turn RECOVERY into LIVE_PUBLIC without the operator's separate audit request.
"""
import uuid
from dataclasses import dataclass

from .database import Database, utc_now
from .stream_control import StreamPolicy, active_value


@dataclass(frozen=True)
class Probe:
    active: bool | None
    reconnecting: bool
    reason: str | None


def _probe(rpc, url: str, password: str, policy: StreamPolicy) -> Probe:
    try:
        snapshot = rpc(url, password, 'GetStreamStatus')
        active = active_value(snapshot)
        reconnecting = snapshot.get('outputReconnecting') is True
        if not active:
            return Probe(False, reconnecting, None)
        destination = rpc(url, password, 'GetStreamServiceSettings')
        reason = policy.verify(destination)
        if reason is None and policy.required_scene is not None:
            scene = rpc(url, password, 'GetCurrentProgramScene')
            if scene.get('currentProgramSceneName') != policy.required_scene:
                reason = 'PRIVACY_SCENE_DRIFT'
        return Probe(True, reconnecting, reason)
    except Exception:
        # Exception messages can contain credentials: never persist or return them.
        return Probe(None, False, 'OBS_READ_FAILED')


def _record_incident(c, db: Database, subject: str, reason: str, session_id: int | None):
    existing = c.execute(
        "SELECT id, occurrences FROM incidents WHERE subject=? AND status='OPEN'", (subject,)
    ).fetchone()
    now = utc_now()
    if existing:
        c.execute('UPDATE incidents SET occurrences=occurrences+1,last_seen_at=?,reason_code=? WHERE id=?',
                  (now, reason, existing['id']))
        return False
    cur = c.execute('INSERT INTO incidents(subject,session_id,status,reason_code,occurrences,opened_at,last_seen_at) '
                    "VALUES(?,?,'OPEN',?,1,?,?)", (subject,session_id,reason,now,now))
    db.event(c,'MONITOR_INCIDENT_OPENED',str(cur.lastrowid),
             {'subject':subject,'reason_code':reason,'session_id':session_id},str(uuid.uuid4()))
    return True


def _close_incident(c, db: Database, subject: str):
    current = c.execute("SELECT id FROM incidents WHERE subject=? AND status='OPEN'",(subject,)).fetchone()
    if current:
        c.execute("UPDATE incidents SET status='RESOLVED',resolved_at=? WHERE id=?",(utc_now(),current['id']))
        db.event(c,'MONITOR_INCIDENT_RESOLVED',str(current['id']),
                 {'subject':subject},str(uuid.uuid4()))


def monitor_once(db: Database, rpc, obs_url: str, obs_password: str,
                 policy: StreamPolicy) -> dict:
    """Single bounded poll; never retries an OBS command or trusts upstream delivery.

    Compare snapshots on both sides of network I/O. A concurrent approval or
    session transition invalidates the probe rather than applying stale state.
    """
    with db.connect() as c:
        db.expire_stale_actions(c)
        executing = c.execute("SELECT 1 FROM action_intents WHERE status='EXECUTING' LIMIT 1").fetchone()
        if executing:
            return {'outcome':'DEFERRED','reason_code':'OBS_ACTION_EXECUTING',
                    'platform_delivery':'UNVERIFIED'}
        before = db.rows(c,"SELECT id,state,updated_at FROM sessions WHERE state IN ('LIVE_PUBLIC','RECOVERY') ORDER BY id")
        if len(before)>1:
            return {'outcome':'DEFERRED','reason_code':'MULTIPLE_ACTIVE_SESSIONS',
                    'platform_delivery':'UNVERIFIED'}

    observed = _probe(rpc,obs_url,obs_password,policy)
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        db.expire_stale_actions(c)
        if c.execute("SELECT 1 FROM action_intents WHERE status='EXECUTING' LIMIT 1").fetchone():
            return {'outcome':'DEFERRED','reason_code':'OBS_ACTION_EXECUTING',
                    'platform_delivery':'UNVERIFIED'}
        after = db.rows(c,"SELECT id,state,updated_at FROM sessions WHERE state IN ('LIVE_PUBLIC','RECOVERY') ORDER BY id")
        if before != after:
            return {'outcome':'DEFERRED','reason_code':'SESSION_CHANGED_DURING_PROBE',
                    'platform_delivery':'UNVERIFIED'}

        sid=after[0]['id'] if after else None
        state=after[0]['state'] if after else 'NO_ACTIVE_SESSION'
        subject=f'SESSION:{sid}' if sid is not None else 'OBS:UNMANAGED'
        if sid is None:
            if observed.active is True:
                reason = 'UNMANAGED_OBS_OUTPUT'
            elif observed.active is None:
                reason = 'OBS_READ_FAILED'
            else:
                reason = None
        elif observed.active is None:
            reason='OBS_READ_FAILED'
        elif observed.reconnecting:
            reason='OBS_RECONNECTING'
        elif observed.reason:
            reason=observed.reason
        elif observed.active is False:
            reason='OBS_OUTPUT_INACTIVE'
        elif state=='RECOVERY':
            reason='OPERATOR_RECONCILIATION_REQUIRED'
        else:
            reason=None

        if sid is not None and reason and state=='LIVE_PUBLIC':
            c.execute("UPDATE sessions SET state='RECOVERY',updated_at=? WHERE id=?",(utc_now(),sid))
            db.event(c,'MONITOR_SESSION_RECOVERY',str(sid),
                     {'reason_code':reason,'platform_delivery':'UNVERIFIED'},str(uuid.uuid4()))
            state='RECOVERY'

        new_incident = _record_incident(c,db,subject,reason,sid) if reason else False
        if reason is None:
            _close_incident(c,db,subject)
        if sid is not None:
            _close_incident(c,db,'OBS:UNMANAGED')
        outcome='ALERT' if reason else 'OK'
        c.execute('INSERT INTO monitor_state(id,last_checked_at,last_result,last_reason_code,last_observed_active) '
                  'VALUES(1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                  'last_checked_at=excluded.last_checked_at,last_result=excluded.last_result,'
                  'last_reason_code=excluded.last_reason_code,last_observed_active=excluded.last_observed_active',
                  (utc_now(),outcome,reason,None if observed.active is None else int(observed.active)))
        return {'outcome':outcome,'reason_code':reason,'new_incident':new_incident,
                'session_id':sid,'session_state':state,'observed_active':observed.active,
                'platform_delivery':'UNVERIFIED'}


def monitor_status(db: Database) -> dict:
    with db.connect() as c:
        last=c.execute('SELECT * FROM monitor_state WHERE id=1').fetchone()
        open_incidents=db.rows(c,"SELECT id,subject,session_id,reason_code,occurrences,opened_at,last_seen_at "
                                   "FROM incidents WHERE status='OPEN' ORDER BY id DESC LIMIT 100")
        return {'last_checked_at':last['last_checked_at'] if last else None,
                'last_result':last['last_result'] if last else 'NEVER_RUN',
                'last_reason_code':last['last_reason_code'] if last else None,
                'last_observed_active':bool(last['last_observed_active']) if last and last['last_observed_active'] is not None else None,
                'open_incidents':open_incidents,'platform_delivery':'UNVERIFIED'}
