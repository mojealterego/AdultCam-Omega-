"""Authenticated local-first HTTP API and responsive operator console."""
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, field_validator

from .database import Database, utc_now
from .domain import action_policy, session_transition_allowed
from .obs import request as obs_request
from .monitor import monitor_once, monitor_status
from .stream_control import StreamPolicy, active_value, public_status, run_obs_action
from .strategy import build_ten_hour_plan, build_month_plan

APP_ROOT = Path(__file__).resolve().parent
basic = HTTPBasic(auto_error=False)


class ProfileIn(BaseModel):
    platform: str = Field(min_length=2, max_length=80, pattern=r'^[\w. -]+$')
    alias: str = Field(min_length=1, max_length=120)
    public_url: str | None = None

    @field_validator('public_url')
    @classmethod
    def valid_public_url(cls, v):
        if v is None or v == '':
            return None
        parsed = urlparse(v)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError('Wymagany publiczny adres HTTPS bez danych uwierzytelniających.')
        return v


class ObservationIn(BaseModel):
    status: str = Field(pattern=r'^(ONLINE|OFFLINE|UNVERIFIED)$')
    source: str = Field(pattern=r'^(MANUAL)$')


class SessionIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)


class TransitionIn(BaseModel):
    to_state: str = Field(pattern=r'^(PREPARE|READY|LIVE_PUBLIC|RECOVERY|ENDING|CLOSED)$')


class AttestationIn(BaseModel):
    adults_verified: bool
    informed_consent: bool
    account_authorized: bool
    terms_checked: bool


class ActionIn(BaseModel):
    operation: str = Field(pattern=r'^(start_stream|stop_stream)$')
    session_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=120)


class ReconcileIn(BaseModel):
    action_id: int = Field(gt=0)


class RecoveryApprovalIn(BaseModel):
    session_id: int = Field(gt=0)


class LedgerIn(BaseModel):
    platform: str = Field(min_length=2, max_length=80)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    category: str = Field(pattern=r'^(TIP|PRIVATE|SUBSCRIPTION|OTHER|REFUND)$')
    amount_minor: int = Field(ge=-100_000_000, le=100_000_000)

    @field_validator('amount_minor')
    @classmethod
    def amount_sign(cls, value, info):
        cat = info.data.get('category')
        if (cat == 'REFUND' and value >= 0) or (cat != 'REFUND' and value <= 0):
            raise ValueError('Dodatni przychód lub ujemny zwrot wymagany.')
        return value


def create_app() -> FastAPI:
    password = os.getenv('ADULTCAM_ADMIN_PASSWORD', '')
    if len(password) < 16:
        raise RuntimeError('Ustaw ADULTCAM_ADMIN_PASSWORD (co najmniej 16 znaków).')
    db = Database(os.getenv('ADULTCAM_DB_PATH', str(Path.home() / '.adultcam-omega' / 'adultcam.sqlite3')))
    obs_url = os.getenv('OBS_WS_URL','ws://127.0.0.1:4455')
    obs_password = os.getenv('OBS_WS_PASSWORD','')
    policy = StreamPolicy.from_env(os.getenv('ADULTCAM_OBS_ALLOWED_SERVERS', ''))
    app = FastAPI(title='AdultCam Ω', version='0.4.0', docs_url=None, redoc_url=None)
    app.state.allowed_servers = policy.allowed_servers
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1'])

    @app.middleware('http')
    async def local_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'none'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        return response

    def auth(credentials: HTTPBasicCredentials | None = Depends(basic)):
        if (credentials is None or not secrets.compare_digest(credentials.username, 'operator')
                or not secrets.compare_digest(credentials.password, password)):
            raise HTTPException(401, 'Uwierzytelnienie wymagane.', headers={'WWW-Authenticate':'Basic realm="AdultCam Omega"'})
        return 'operator'

    def mutating(request: Request, user: str = Depends(auth)):
        origin = request.headers.get('origin')
        if origin:
            here = f'{request.url.scheme}://{request.url.netloc}'
            if origin != here:
                raise HTTPException(403, 'Nieprawidłowy Origin.')
        if request.headers.get('X-AdultCam-Request') != '1':
            raise HTTPException(403, 'Brak nagłówka anty-CSRF.')
        return user

    def get_attested(c) -> bool:
        row = c.execute('SELECT * FROM attestations ORDER BY id DESC LIMIT 1').fetchone()
        if not row or not all([row['adults_verified'], row['informed_consent'],row['account_authorized'],row['terms_checked']]):
            return False
        return datetime.fromisoformat(row['attested_at']) >= datetime.now(timezone.utc) - timedelta(hours=24)

    def require_session(c, sid: int):
        row = c.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        if not row:
            raise HTTPException(404, 'Nie znaleziono sesji.')
        return dict(row)

    @app.get('/')
    def index(_: str = Depends(auth)):
        return FileResponse(APP_ROOT / 'web' / 'index.html')

    @app.get('/api/health')
    def health():
        return {'status':'OK', 'version':'0.4.0','external_platform_integrations':'NOT_CONNECTED'}

    @app.get('/api/dashboard')
    def dashboard(_: str = Depends(auth)):
        with db.connect() as c:
            profiles = db.rows(c,'SELECT * FROM profiles ORDER BY id DESC LIMIT 100')
            sessions = db.rows(c,'SELECT * FROM sessions ORDER BY id DESC LIMIT 100')
            actions = db.rows(c,'SELECT * FROM action_intents ORDER BY id DESC LIMIT 100')
            events = db.rows(c,'SELECT * FROM events ORDER BY id DESC LIMIT 100')
            ledger = db.rows(c,'SELECT * FROM ledger ORDER BY id DESC LIMIT 100')
            totals = db.rows(c,'SELECT currency,SUM(amount_minor) AS amount_minor FROM ledger GROUP BY currency')
            for e in events:
                e['detail'] = json.loads(e.pop('detail_json'))
            for a in actions:
                a['receipt'] = json.loads(a.pop('receipt_json')) if a.get('receipt_json') else None
            return {'profiles':profiles,'sessions':sessions,'actions':actions,'events':events,
                    'ledger':ledger,'revenue_by_currency':{r['currency']:r['amount_minor'] for r in totals},
                    'attestation_current':get_attested(c),
                    'integration_states':{'OBS':'LOCAL_ADAPTER_NOT_LIVE_VERIFIED','EXTERNAL_PLATFORMS':'MANUAL_ONLY'},
                    'unresolved_obs_actions': db.rows(c, "SELECT a.id,a.operation,a.session_id FROM action_intents a LEFT JOIN obs_reconciliations r ON r.action_id=a.id WHERE a.status='UNKNOWN' AND r.action_id IS NULL ORDER BY a.id")}

    @app.get('/api/platforms/capabilities')
    def platform_capabilities(_: str = Depends(auth)):
        # External services remain MANUAL_ONLY until authorized integrations and
        # current provider terms have been independently verified.
        return {'verified_integrations':0,'providers':[],
                'default_capability':'MANUAL_ONLY',
                'transmission_destination':'OBS_OUTPUT_ONLY',
                'platform_delivery':'UNVERIFIED'}

    @app.get('/api/monitor/status')
    def read_monitor(_: str = Depends(auth)):
        return monitor_status(db)

    @app.post('/api/monitor/check')
    def check_monitor(_: str = Depends(mutating)):
        return monitor_once(db,obs_request,obs_url,obs_password,
                            StreamPolicy(app.state.allowed_servers))

    @app.post('/api/attestations',status_code=201)
    def attest(body: AttestationIn, _: str = Depends(mutating)):
        if not all([body.adults_verified,body.informed_consent,body.account_authorized,body.terms_checked]):
            raise HTTPException(409, 'Wszystkie wymagane oświadczenia muszą być prawdziwe.')
        when = utc_now()
        with db.connect() as c:
            result=c.execute('INSERT INTO attestations(attested_at,adults_verified,informed_consent,account_authorized,terms_checked) VALUES(?,?,?,?,?)',
                             (when,1,1,1,1))
            db.event(c,'ATTESTATION_RECORDED',str(result.lastrowid),{'kind':'operator_self_attestation'},str(uuid.uuid4()))
        return {'id':result.lastrowid,'recorded_at':when,'verification':'OPERATOR_SELF_ATTESTATION_ONLY'}

    @app.post('/api/profiles',status_code=201)
    def new_profile(body: ProfileIn, _: str = Depends(mutating)):
        with db.connect() as c:
            try:
                cur=c.execute('INSERT INTO profiles(platform,alias,public_url,updated_at) VALUES(?,?,?,?)',
                              (body.platform, body.alias,body.public_url,utc_now()))
            except sqlite3.IntegrityError:
                raise HTTPException(409,'Profil jest już dodany.')
            db.event(c,'PROFILE_CREATED',str(cur.lastrowid),{'platform':body.platform,'alias':body.alias},str(uuid.uuid4()))
            return {'id':cur.lastrowid,'status':'UNVERIFIED'}

    @app.post('/api/profiles/{pid}/observations',status_code=201)
    def observe(pid: int, body: ObservationIn, _: str = Depends(mutating)):
        with db.connect() as c:
            row=c.execute('SELECT * FROM profiles WHERE id=?',(pid,)).fetchone()
            if not row:
                raise HTTPException(404,'Nie znaleziono profilu.')
            if row['status'] == body.status:
                return {'changed':False,'status':body.status}
            c.execute('UPDATE profiles SET status=?,updated_at=? WHERE id=?',(body.status,utc_now(),pid))
            db.event(c,'PROFILE_STATUS',str(pid),{'from':row['status'],'to':body.status,'source':body.source},str(uuid.uuid4()))
            return {'changed':True,'status':body.status}

    @app.post('/api/sessions',status_code=201)
    def new_session(body: SessionIn, _: str = Depends(mutating)):
        with db.connect() as c:
            cur=c.execute('INSERT INTO sessions(title,state,updated_at) VALUES(?,?,?)',(body.title,'PREPARE',utc_now()))
            db.event(c,'SESSION_CREATED',str(cur.lastrowid),{'title':body.title},str(uuid.uuid4()))
            return {'id':cur.lastrowid,'state':'PREPARE'}

    def has_pending_or_unknown_start(c, sid: int) -> bool:
        return c.execute("SELECT 1 FROM action_intents a LEFT JOIN obs_reconciliations r ON r.action_id=a.id WHERE a.session_id=? AND a.operation='start_stream' AND (a.status IN ('PENDING_APPROVAL','EXECUTING') OR (a.status='UNKNOWN' AND r.action_id IS NULL)) LIMIT 1", (sid,)).fetchone() is not None

    @app.post('/api/sessions/{sid}/transition')
    def transition(sid:int, body:TransitionIn, _: str=Depends(mutating)):
        with db.connect() as c:
            row=require_session(c,sid)
            # LIVE_PUBLIC is only reached upon an OBS-confirmed successful stream start.
            if body.to_state == 'LIVE_PUBLIC' or (row['state'] in {'LIVE_PUBLIC','RECOVERY'} and body.to_state == 'ENDING'):
                raise HTTPException(409,'Przejście LIVE/ENDING wymaga potwierdzenia OBS, nie zmiany ręcznej.')
            if body.to_state == 'CLOSED' and has_pending_or_unknown_start(c, sid):
                raise HTTPException(409,'Przed zamknięciem wymagane uzgodnienie niepewnego uruchomienia OBS.')
            decision=session_transition_allowed(row['state'],body.to_state,get_attested(c))
            if decision.verdict != 'ALLOW':
                raise HTTPException(409,decision.reason)
            c.execute('UPDATE sessions SET state=?,updated_at=? WHERE id=?',(body.to_state,utc_now(),sid))
            db.event(c,'SESSION_TRANSITION',str(sid),{'from':row['state'],'to':body.to_state},str(uuid.uuid4()))
            return {'id':sid,'state':body.to_state}

    def has_unresolved_obs(c):
        return c.execute("SELECT a.id FROM action_intents a LEFT JOIN obs_reconciliations r ON r.action_id=a.id WHERE (a.status='UNKNOWN' AND r.action_id IS NULL) OR a.status='EXECUTING' LIMIT 1").fetchone() is not None

    @app.post('/api/actions',status_code=201)
    def new_action(body: ActionIn, _: str=Depends(mutating)):
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            db.expire_stale_actions(c)
            existing=c.execute('SELECT * FROM action_intents WHERE idempotency_key=?',(body.idempotency_key,)).fetchone()
            if existing:
                if existing['operation'] != body.operation or existing['session_id'] != body.session_id:
                    raise HTTPException(409,'Klucz idempotencji został użyty dla innego zamiaru.')
                return JSONResponse(status_code=200, content={'id':existing['id'],'status':existing['status'],'reused':True})
            session=require_session(c,body.session_id)
            if body.operation == 'start_stream' and has_unresolved_obs(c):
                raise HTTPException(409,'Nierozstrzygnięta operacja OBS; wymagane zatwierdzone uzgodnienie statusu.')
            if body.operation == 'start_stream':
                other = c.execute("SELECT id FROM sessions WHERE state IN ('LIVE_PUBLIC','RECOVERY') LIMIT 1").fetchone()
                if other:
                    raise HTTPException(409,'Trwa inna aktywna sesja. Globalna blokada OBS.')
                pending = c.execute("SELECT id FROM action_intents WHERE operation='start_stream' AND status='PENDING_APPROVAL' LIMIT 1").fetchone()
                if pending:
                    raise HTTPException(409,'Inny zamiar START OBS oczekuje lub trwa.')
            if body.operation == 'stop_stream':
                another = c.execute("SELECT 1 FROM sessions WHERE id<>? AND state IN ('LIVE_PUBLIC','RECOVERY') LIMIT 1",
                                    (body.session_id,)).fetchone()
                if another:
                    raise HTTPException(409,'STOP musi dotyczyć aktywnej sesji OBS, a nie innej sesji.')
            decision=action_policy(body.operation,session['state'],get_attested(c))
            if decision.verdict not in ('ALLOW','ALLOW_WITH_CONDITIONS'):
                raise HTTPException(409,decision.reason)
            cur=c.execute('INSERT INTO action_intents(operation,session_id,idempotency_key,status,risk_class,policy_decision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                          (body.operation,body.session_id,body.idempotency_key,'PENDING_APPROVAL',decision.risk_class,decision.verdict,utc_now(),utc_now()))
            db.event(c,'ACTION_INTENT',str(cur.lastrowid),{'operation':body.operation,'policy':decision.verdict},str(uuid.uuid4()))
            return {'id':cur.lastrowid,'status':'PENDING_APPROVAL','risk':decision.risk_class}

    @app.post('/api/actions/{aid}/approve')
    def approve(aid:int, request:Request, _:str=Depends(mutating)):
        if request.headers.get('X-AdultCam-Confirm') != 'I_APPROVE':
            raise HTTPException(403,'Wymagane świadome zatwierdzenie X-AdultCam-Confirm: I_APPROVE.')
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            db.expire_stale_actions(c)
            action=c.execute('SELECT * FROM action_intents WHERE id=?',(aid,)).fetchone()
            if not action:
                raise HTTPException(404,'Nie znaleziono operacji.')
            if action['status'] != 'PENDING_APPROVAL':
                raise HTTPException(409,'Operacja została już obsłużona lub jest w toku.')
            # A durable, SQLite-arbitrated single-flight gate across processes/threads.
            if c.execute("SELECT id FROM action_intents WHERE status='EXECUTING' LIMIT 1").fetchone():
                raise HTTPException(409,'Inna operacja OBS jest wykonywana.')
            if action['operation']=='start_stream' and has_unresolved_obs(c):
                raise HTTPException(409,'Nieznany poprzedni wynik OBS wymaga uzgodnienia przed uruchomieniem.')
            session=require_session(c,action['session_id'])
            policy_decision=action_policy(action['operation'],session['state'],get_attested(c))
            if action['operation'] == 'start_stream':
                other = c.execute("SELECT id FROM sessions WHERE state IN ('LIVE_PUBLIC','RECOVERY') LIMIT 1").fetchone()
                if other:
                    raise HTTPException(409,'Trwa inna aktywna sesja. Globalna blokada OBS.')
            if action['operation'] == 'stop_stream':
                another=c.execute("SELECT 1 FROM sessions WHERE id<>? AND state IN ('LIVE_PUBLIC','RECOVERY') LIMIT 1",
                                  (action['session_id'],)).fetchone()
                if another:
                    raise HTTPException(409,'STOP dotyczy niewłaściwej sesji OBS.')
            if policy_decision.verdict not in ('ALLOW','ALLOW_WITH_CONDITIONS'):
                raise HTTPException(409,policy_decision.reason)
            c.execute("UPDATE action_intents SET status='EXECUTING',updated_at=? WHERE id=?",(utc_now(),aid))
            db.event(c,'ACTION_APPROVED',str(aid),{'operation':action['operation']},str(uuid.uuid4()))
        receipt = run_obs_action(obs_request, obs_url, obs_password, action['operation'],
                                 StreamPolicy(app.state.allowed_servers))
        with db.connect() as c:
            c.execute('UPDATE action_intents SET status=?,receipt_json=?,updated_at=? WHERE id=?',
                      (receipt['status'],json.dumps(receipt),utc_now(),aid))
            db.event(c,'ACTION_RECEIPT',str(aid),receipt,str(uuid.uuid4()))
            if receipt['status']=='SUCCEEDED':
                state='LIVE_PUBLIC' if action['operation']=='start_stream' else 'ENDING'
                c.execute('UPDATE sessions SET state=?,updated_at=? WHERE id=?',(state,utc_now(),action['session_id']))
                db.event(c,'SESSION_TRANSITION',str(action['session_id']),
                         {'to':state,'via':'OBS_OUTPUT_CONFIRMED','platform_delivery':'UNVERIFIED'},str(uuid.uuid4()))
        return {'id':aid,'receipt':receipt}

    @app.post('/api/actions/{aid}/cancel')
    def cancel_action(aid:int, _:str=Depends(mutating)):
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            db.expire_stale_actions(c)
            action=c.execute('SELECT * FROM action_intents WHERE id=?',(aid,)).fetchone()
            if not action:
                raise HTTPException(404,'Nie znaleziono operacji.')
            if action['status'] != 'PENDING_APPROVAL':
                raise HTTPException(409,'Anulować można wyłącznie niewykonany zamiar.')
            c.execute("UPDATE action_intents SET status='CANCELLED',updated_at=? WHERE id=?",(utc_now(),aid))
            db.event(c,'ACTION_CANCELLED',str(aid),{'operation':action['operation']},str(uuid.uuid4()))
            return {'id':aid,'status':'CANCELLED','obs_command_sent':False}

    @app.post('/api/obs/check')
    def check_observed_output(_:str=Depends(mutating)):
        """Manual audit: local OBS output only, never a remote platform receipt."""
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            db.expire_stale_actions(c)
            if c.execute("SELECT 1 FROM action_intents WHERE status='EXECUTING' LIMIT 1").fetchone():
                raise HTTPException(409,'Trwa operacja OBS; sprawdzenie jest odroczone.')
            live = db.rows(c,"SELECT * FROM sessions WHERE state IN ('LIVE_PUBLIC','RECOVERY') ORDER BY id")
            if len(live) > 1:
                raise HTTPException(409,'Kilka aktywnych sesji w bazie — wymagana interwencja operatora.')
            try:
                snapshot=obs_request(obs_url,obs_password,'GetStreamStatus')
                observed=active_value(snapshot)
                reconnecting = snapshot.get('outputReconnecting') is True
                denied=None
                if observed:
                    denied=StreamPolicy(app.state.allowed_servers).verify(
                        obs_request(obs_url,obs_password,'GetStreamServiceSettings'))
            except Exception:
                if live and live[0]['state']=='LIVE_PUBLIC':
                    sid=live[0]['id']
                    c.execute("UPDATE sessions SET state='RECOVERY',updated_at=? WHERE id=?",(utc_now(),sid))
                    db.event(c,'OBS_MONITOR_UNKNOWN',str(sid),{'reason':'OBS_READ_FAILED'},str(uuid.uuid4()))
                return {'connection':'NEEDS_VERIFICATION',
                        'state':'RECOVERY' if live else 'NO_ACTIVE_SESSION',
                        'observed_active':None,'platform_delivery':'UNVERIFIED'}
            state=live[0]['state'] if live else 'NO_ACTIVE_SESSION'
            if live:
                sid=live[0]['id']
                # Read-only audits can downgrade LIVE to RECOVERY, but must never
                # silently upgrade RECOVERY to LIVE. Operator must approve a
                # separate recovery gate after an OBS recheck.
                desired = 'RECOVERY' if (not observed or reconnecting or denied) else state
                if desired != state:
                    c.execute('UPDATE sessions SET state=?,updated_at=? WHERE id=?',(desired,utc_now(),sid))
                    db.event(c,'OBS_STATE_DRIFT',str(sid),
                             {'from':state,'to':desired,'observed_active':observed,
                              'destination_policy':denied,'platform_delivery':'UNVERIFIED'},str(uuid.uuid4()))
                    state=desired
            return {'connection':'CONNECTED_API','state':state,
                    'unmanaged_obs_output':bool(observed and not live),
                    'observed_active':observed,'output_reconnecting':reconnecting,
                    'destination_policy':denied,'platform_delivery':'UNVERIFIED'}

    @app.post('/api/obs/recovery/approve')
    def approve_recovery(body: RecoveryApprovalIn, request: Request, _: str = Depends(mutating)):
        """Human-approved, read-only recovery: no OBS broadcast command."""
        if request.headers.get('X-AdultCam-Confirm') != 'I_APPROVE':
            raise HTTPException(403, 'Wymagane świadome zatwierdzenie przywrócenia stanu OBS.')
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            db.expire_stale_actions(c)
            session = require_session(c, body.session_id)
            if session['state'] != 'RECOVERY':
                raise HTTPException(409, 'Przywracanie wymaga stanu RECOVERY.')
            if not get_attested(c):
                raise HTTPException(409, 'Wymagane aktualne oświadczenie operatora.')
            if has_unresolved_obs(c):
                raise HTTPException(409, 'Trwająca lub nieuzgodniona operacja OBS.')
            if c.execute("SELECT 1 FROM sessions WHERE id<>? AND state IN ('LIVE_PUBLIC','RECOVERY') LIMIT 1",
                         (body.session_id,)).fetchone():
                raise HTTPException(409, 'Wykryto inną aktywną sesję.')
            # A previously authorized START is necessary; a raw OBS output may
            # belong to another application/session and is not enough evidence.
            last_start = c.execute(
                "SELECT a.id, a.status, r.observed_active FROM action_intents a "
                "LEFT JOIN obs_reconciliations r ON a.id=r.action_id "
                "WHERE a.session_id=? AND a.operation='start_stream' ORDER BY a.id DESC LIMIT 1",
                (body.session_id,)).fetchone()
            if not last_start or not (last_start['status'] == 'SUCCEEDED' or
                    (last_start['status'] == 'UNKNOWN' and last_start['observed_active'] == 1)):
                raise HTTPException(409, 'Brak potwierdzonego wcześniejszego uruchomienia dla tej sesji.')
            last_stop = c.execute(
                "SELECT id FROM action_intents WHERE session_id=? AND operation='stop_stream' "
                "AND status IN ('SUCCEEDED','UNKNOWN','EXECUTING') AND id>? LIMIT 1",
                (body.session_id, last_start['id'])).fetchone()
            if last_stop:
                raise HTTPException(409, 'Późniejsza operacja STOP wymaga oddzielnej kontroli.')
            if not obs_password:
                raise HTTPException(409, 'Brak uwierzytelnienia OBS.')
            try:
                status = obs_request(obs_url, obs_password, 'GetStreamStatus')
                if not active_value(status) or status.get('outputReconnecting') is True:
                    raise HTTPException(409, 'OBS nie nadaje stabilnie.')
                destination = obs_request(obs_url, obs_password, 'GetStreamServiceSettings')
                reason = StreamPolicy(app.state.allowed_servers).verify(destination)
                if reason:
                    raise HTTPException(409, 'Cel nadawania OBS nie został zatwierdzony.')
            except HTTPException:
                raise
            except Exception:
                # Do not expose transport exception strings containing secrets.
                raise HTTPException(503, 'Nie udało się zweryfikować statusu OBS.')
            c.execute('UPDATE sessions SET state=?,updated_at=? WHERE id=?',
                      ('LIVE_PUBLIC', utc_now(), body.session_id))
            db.event(c, 'RECOVERY_OPERATOR_APPROVED', str(body.session_id),
                     {'from': 'RECOVERY', 'to': 'LIVE_PUBLIC', 'via': 'OBS_READ_ONLY',
                      'platform_delivery': 'UNVERIFIED'}, str(uuid.uuid4()))
            return {'session_id': body.session_id, 'state': 'LIVE_PUBLIC',
                    'obs_command_sent': False, 'platform_delivery': 'UNVERIFIED',
                    'operator_approval': 'RECORDED'}

    @app.post('/api/obs/reconcile')
    def reconcile(body:ReconcileIn, request:Request, _:str=Depends(mutating)):
        if request.headers.get('X-AdultCam-Confirm') != 'I_APPROVE':
            raise HTTPException(403,'Wymagane potwierdzenie operatora przed uzgodnieniem OBS.')
        with db.connect() as c:
            # Hold SQLite write lock across a bounded OBS snapshot, serializing approvals.
            c.execute('BEGIN IMMEDIATE')
            db.expire_stale_actions(c)
            if c.execute("SELECT 1 FROM action_intents WHERE status='EXECUTING' LIMIT 1").fetchone():
                raise HTTPException(409,'Operacja OBS trwa; uzgodnienie jest niedostępne.')
            action=c.execute('SELECT * FROM action_intents WHERE id=?',(body.action_id,)).fetchone()
            if not action:
                raise HTTPException(404,'Nie znaleziono operacji.')
            if action['status'] != 'UNKNOWN' or c.execute('SELECT 1 FROM obs_reconciliations WHERE action_id=?',(body.action_id,)).fetchone():
                raise HTTPException(409,'Operacja nie wymaga uzgodnienia lub została już uzgodniona.')
            try:
                snapshot=obs_request(obs_url,obs_password,'GetStreamStatus')
                observed=active_value(snapshot)
                if observed and snapshot.get('outputReconnecting') is True:
                    raise HTTPException(409,'OBS ponawia połączenie: nie można uzgodnić stabilnego stanu.')
                if observed and action['operation'] == 'start_stream':
                    destination=obs_request(obs_url,obs_password,'GetStreamServiceSettings')
                    reason=StreamPolicy(app.state.allowed_servers).verify(destination)
                    if reason:
                        raise HTTPException(409,'Aktywne OBS ma niezatwierdzony cel; wymagane ręczne zatrzymanie/wyjaśnienie.')
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(503,'OBS nie zwrócił wiarygodnego statusu. Uzgodnienie nie zostało zapisane.')
            code='OBS_ACTIVE' if observed else 'OBS_INACTIVE'
            c.execute('INSERT INTO obs_reconciliations(action_id,observed_active,checked_at,operator,result_code) VALUES(?,?,?,?,?)',
                      (body.action_id,int(observed),utc_now(),'operator',code))
            db.event(c,'OBS_RECONCILED',str(body.action_id),
                     {'observed_active':observed,'platform_delivery':'UNVERIFIED'},str(uuid.uuid4()))
            session=require_session(c,action['session_id'])
            new_state=None
            if observed and action['operation']=='start_stream' and session['state']=='READY':
                new_state='LIVE_PUBLIC'
            elif not observed and action['operation']=='stop_stream' and session['state'] in ('LIVE_PUBLIC','RECOVERY'):
                new_state='ENDING'
            if new_state:
                c.execute('UPDATE sessions SET state=?,updated_at=? WHERE id=?',
                          (new_state,utc_now(),action['session_id']))
                db.event(c,'SESSION_TRANSITION',str(action['session_id']),
                         {'from':session['state'],'to':new_state,'via':'OBS_RECONCILIATION',
                          'platform_delivery':'UNVERIFIED'},str(uuid.uuid4()))
            return {'action_id':body.action_id,'observed_active':observed,
                    'result_code':code,'platform_delivery':'UNVERIFIED',
                    'previous_action_outcome':'UNKNOWN','session_state':new_state or session['state']}

    @app.get('/api/strategy/ten-hour')
    def ten_hour(_: str = Depends(auth)):
        return {'plan':build_ten_hour_plan(), 'kind':'TEMPLATE_NOT_LIVE'}

    @app.get('/api/strategy/thirty-day')
    def thirty_day(_: str = Depends(auth)):
        return {'plan':build_month_plan(), 'kind':'TEMPLATE_NOT_LIVE'}

    @app.get('/api/obs/status')
    def obs_status(_:str=Depends(auth)):
        try:
            result=obs_request(obs_url,obs_password,'GetStreamStatus')
            return {'connection':'CONNECTED_API','status':public_status(result),
                    'platform_delivery':'UNVERIFIED'}
        except Exception as exc:
            return {'connection':'NEEDS_VERIFICATION','error_type':type(exc).__name__}

    @app.post('/api/ledger',status_code=201)
    def new_ledger(body:LedgerIn, _:str=Depends(mutating)):
        with db.connect() as c:
            cur=c.execute('INSERT INTO ledger(platform,category,currency,amount_minor,created_at) VALUES(?,?,?,?,?)',
                          (body.platform,body.category,body.currency,body.amount_minor,utc_now()))
            db.event(c,'LEDGER_MANUAL_ENTRY',str(cur.lastrowid),{'amount_minor':body.amount_minor,'currency':body.currency},str(uuid.uuid4()))
            return {'id':cur.lastrowid, 'source':'MANUAL'}

    return app


def serve():
    import uvicorn
    host=os.getenv('ADULTCAM_HOST','127.0.0.1')
    if host not in {'127.0.0.1','localhost'}:
        raise RuntimeError('Tryb lokalny: nasłuch dozwolony wyłącznie na loopback. Dostęp zdalny wymaga osobnej warstwy HTTPS/OIDC.')
    uvicorn.run(create_app(),host='127.0.0.1',port=int(os.getenv('ADULTCAM_PORT','8765')))
