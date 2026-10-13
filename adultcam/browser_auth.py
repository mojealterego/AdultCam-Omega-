"""Server-side OIDC browser login with Authorization Code + PKCE, nonce and CSRF."""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from .auth import OidcVerifier, Principal, _secure_url
from .database import Database

FLOW_TTL = 300
SESSION_TTL = 900
SESSION_COOKIE = '__Host-ac-omega'
FLOW_COOKIE = '__Host-ac-oauth'


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _validate_https_endpoint(value: str, issuer: str) -> str:
    if not value or _secure_url(value) != _secure_url(issuer):
        raise ValueError('OAuth endpoints must use the issuer HTTPS host and port.')
    parsed = urlsplit(value)
    if not parsed.path or parsed.query or parsed.fragment:
        raise ValueError('OAuth endpoints require a fixed URL path.')
    return value


@dataclass(frozen=True)
class BrowserConfig:
    public_origin: str
    authorization_url: str
    token_url: str
    client_id: str


def load_browser_config(oidc: OidcVerifier | None) -> BrowserConfig | None:
    public = os.getenv('ADULTCAM_PUBLIC_ORIGIN', '')
    auth_url = os.getenv('ADULTCAM_OIDC_AUTHORIZATION_URL', '')
    token_url = os.getenv('ADULTCAM_OIDC_TOKEN_URL', '')
    client_id = os.getenv('ADULTCAM_OIDC_CLIENT_ID', '')
    if not any([public, auth_url, token_url, client_id]):
        return None
    if oidc is None or not all([public, auth_url, token_url, client_id]):
        raise ValueError('Browser OIDC requires issuer, client, HTTPS origin and both endpoints.')
    origin = urlsplit(public)
    if (origin.scheme != 'https' or not origin.hostname or origin.path or
            origin.query or origin.fragment or origin.username or origin.password or
            public != f'https://{origin.netloc}' or not public.isascii()):
        raise ValueError('ADULTCAM_PUBLIC_ORIGIN must be an exact HTTPS origin.')
    if not 2 <= len(client_id) <= 200 or '\n' in client_id or '\r' in client_id:
        raise ValueError('Invalid OIDC client ID.')
    return BrowserConfig(public, _validate_https_endpoint(auth_url, oidc.issuer),
                         _validate_https_endpoint(token_url, oidc.issuer), client_id)


def exchange_token(token_url: str, client_id: str, redirect_uri: str,
                   code: str, verifier: str) -> dict:
    with httpx.Client(timeout=6, follow_redirects=False, trust_env=False) as client:
        response = client.post(token_url, data={
            'grant_type': 'authorization_code', 'client_id': client_id,
            'redirect_uri': redirect_uri, 'code': code, 'code_verifier': verifier,
        }, headers={'Accept': 'application/json'})
    if response.status_code != 200 or len(response.content) > 131072:
        raise ValueError('OIDC exchange failed.')
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError('Invalid OIDC token response.')
    return payload


class BrowserSessions:
    def __init__(self, db: Database, config: BrowserConfig, oidc: OidcVerifier):
        self.db, self.config, self.oidc = db, config, oidc
        with db.connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS oauth_browser_flows (
                    state_sha TEXT PRIMARY KEY, cookie_sha TEXT NOT NULL,
                    verifier TEXT NOT NULL, nonce TEXT NOT NULL, expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_browser_sessions (
                    token_sha TEXT PRIMARY KEY, csrf_sha TEXT NOT NULL,
                    subject TEXT NOT NULL, role TEXT NOT NULL, expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS oauth_browser_sessions_expire
                    ON oauth_browser_sessions(expires_at);
            ''')

    def redirect_uri(self) -> str:
        return self.config.public_origin + '/auth/callback'

    def initiate(self) -> RedirectResponse:
        state, cookie, verifier, nonce = (secrets.token_urlsafe(32) for _ in range(4))
        challenge = _b64(hashlib.sha256(verifier.encode('ascii')).digest())
        with self.db.connect() as c:
            c.execute('DELETE FROM oauth_browser_flows WHERE expires_at<=?', (int(time.time()),))
            c.execute('INSERT INTO oauth_browser_flows VALUES(?,?,?,?,?)',
                      (_hash(state), _hash(cookie), verifier, nonce, int(time.time()) + FLOW_TTL))
        params = {
            'response_type': 'code', 'client_id': self.config.client_id,
            'redirect_uri': self.redirect_uri(), 'scope': 'openid',
            'state': state, 'nonce': nonce,
            'code_challenge': challenge, 'code_challenge_method': 'S256',
        }
        response = RedirectResponse(self.config.authorization_url + '?' + urlencode(params), status_code=303)
        response.set_cookie(FLOW_COOKIE, cookie, max_age=FLOW_TTL,
                            secure=True, httponly=True, samesite='lax', path='/')
        response.headers['Cache-Control'] = 'no-store'
        return response

    def complete(self, state: str, code: str, browser_cookie: str | None) -> RedirectResponse:
        if not state or not code or not browser_cookie or max(map(len, (state, code, browser_cookie))) > 8192:
            raise HTTPException(401, 'Missing OIDC login state.')
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM oauth_browser_flows WHERE state_sha=?',
                            (_hash(state),)).fetchone()
            if row:
                c.execute('DELETE FROM oauth_browser_flows WHERE state_sha=?', (_hash(state),))
        if (row is None or row['expires_at'] <= int(time.time()) or
                not secrets.compare_digest(row['cookie_sha'], _hash(browser_cookie))):
            raise HTTPException(401, 'OIDC state expired or browser cookie mismatch.')
        try:
            tokens = exchange_token(self.config.token_url, self.config.client_id,
                                    self.redirect_uri(), code, row['verifier'])
            access_token, id_token = tokens['access_token'], tokens['id_token']
            if not isinstance(access_token, str) or not isinstance(id_token, str):
                raise ValueError('Invalid tokens.')
            principal = self.oidc.verify(access_token)
            header = jwt.get_unverified_header(id_token)
            if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
                raise ValueError('Invalid token algorithm.')
            signing_key = self.oidc.jwks.get_signing_key(header['kid']).key
            identity = jwt.decode(id_token, signing_key, algorithms=['RS256'],
                                  issuer=self.oidc.issuer, audience=self.config.client_id,
                                  leeway=15, options={'require':['iss','aud','sub','iat','exp']})
            if identity.get('nonce') != row['nonce'] or identity.get('sub') != principal.subject:
                raise ValueError('OIDC nonce or subject mismatch.')
        except (KeyError, jwt.PyJWTError, ValueError, PermissionError, TypeError, httpx.HTTPError):
            raise HTTPException(401, 'OIDC validation failed.') from None
        token, csrf = secrets.token_urlsafe(36), secrets.token_urlsafe(36)
        with self.db.connect() as c:
            c.execute('DELETE FROM oauth_browser_sessions WHERE expires_at<=?', (int(time.time()),))
            c.execute('INSERT INTO oauth_browser_sessions VALUES(?,?,?,?,?)',
                      (_hash(token), _hash(csrf), principal.subject, principal.role,
                       int(time.time()) + SESSION_TTL))
            self.db.event(c, 'OPERATOR_LOGIN', principal.subject,
                          {'auth_source':'oidc_browser','role':principal.role}, secrets.token_hex(16))
        response = RedirectResponse('/', status_code=303)
        response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL, secure=True,
                            httponly=True, samesite='strict', path='/')
        response.delete_cookie(FLOW_COOKIE, secure=True, httponly=True, samesite='lax', path='/')
        return response

    def authenticate(self, request: Request) -> tuple[Principal, str] | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token or len(token) > 200:
            return None
        with self.db.connect() as c:
            row = c.execute('SELECT * FROM oauth_browser_sessions WHERE token_sha=?',
                            (_hash(token),)).fetchone()
        if row is None or row['expires_at'] <= int(time.time()):
            return None
        return Principal(row['subject'], row['role'], 'oidc_browser'), row['csrf_sha']

    def csrf(self, request: Request, supplied: str) -> bool:
        result = self.authenticate(request)
        return bool(result and supplied and secrets.compare_digest(result[1], _hash(supplied)))

    def renew_csrf(self, request: Request) -> str:
        token = request.cookies.get(SESSION_COOKIE, '')
        if self.authenticate(request) is None:
            raise HTTPException(401, 'Browser session expired.')
        csrf = secrets.token_urlsafe(36)
        with self.db.connect() as c:
            c.execute('UPDATE oauth_browser_sessions SET csrf_sha=? WHERE token_sha=?',
                      (_hash(csrf), _hash(token)))
        return csrf

    def logout(self, request: Request) -> None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return
        with self.db.connect() as c:
            row = c.execute('SELECT subject FROM oauth_browser_sessions WHERE token_sha=?',
                            (_hash(token),)).fetchone()
            c.execute('DELETE FROM oauth_browser_sessions WHERE token_sha=?', (_hash(token),))
            if row:
                self.db.event(c, 'OPERATOR_LOGOUT', row['subject'],
                              {'auth_source':'oidc_browser'}, secrets.token_hex(16))

    def list_sessions(self) -> list[dict]:
        with self.db.connect() as c:
            return self.db.rows(c,
                'SELECT subject,role,expires_at FROM oauth_browser_sessions '
                'WHERE expires_at>? ORDER BY subject,expires_at', (int(time.time()),))

    def revoke_subject(self, subject: str, actor: Principal) -> int:
        if not subject or not 1 <= len(subject) <= 256 or actor.role != 'admin':
            raise ValueError('Invalid subject or permission.')
        with self.db.connect() as c:
            result = c.execute('DELETE FROM oauth_browser_sessions WHERE subject=?', (subject,))
            self.db.event(c, 'OPERATOR_SESSIONS_REVOKED', subject,
                          {'revoked_sessions': result.rowcount, 'actor': actor.subject,
                           'auth_source': actor.source}, secrets.token_hex(16))
            return result.rowcount
