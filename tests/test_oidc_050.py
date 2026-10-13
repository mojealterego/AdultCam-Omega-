"""Security invariants for optional, JWT-verified remote API access."""
from datetime import datetime, timedelta, timezone
import base64

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from adultcam.app import create_app


@pytest.fixture
def identity(monkeypatch, tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_numbers()

    def b64num(n):
        return base64.urlsafe_b64encode(n.to_bytes((n.bit_length() + 7) // 8, 'big')).rstrip(b'=').decode()

    jwks = {'keys': [{'kty': 'RSA', 'use': 'sig', 'alg': 'RS256', 'kid': 'key-1',
                      'n': b64num(public.n), 'e': b64num(public.e)}]}
    from jwt import PyJWKClient
    monkeypatch.setattr(PyJWKClient, 'fetch_data', lambda self: jwks)
    monkeypatch.setenv('ADULTCAM_AUTH_MODE', 'oidc')
    monkeypatch.setenv('ADULTCAM_OIDC_ISSUER', 'https://identity.example.test/')
    monkeypatch.setenv('ADULTCAM_OIDC_AUDIENCE', 'adultcam-omega-api')
    monkeypatch.setenv('ADULTCAM_OIDC_JWKS_URL', 'https://identity.example.test/.well-known/jwks.json')
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD', 'a-local-password-longer-than-16')
    monkeypatch.setenv('ADULTCAM_DB_PATH', str(tmp_path / 'oidc.sqlite3'))
    monkeypatch.setenv('ADULTCAM_OBS_ALLOWED_SERVERS', 'rtmp://127.0.0.1:19350/live')

    def token(roles, *, audience='adultcam-omega-api', issuer='https://identity.example.test/',
              expires=120, algorithm='RS256'):
        now = datetime.now(timezone.utc)
        payload = {'iss': issuer, 'aud': audience, 'sub': 'operator-123',
                   'iat': now, 'exp': now + timedelta(seconds=expires),
                   'adultcam_roles': roles}
        return jwt.encode(payload, key if algorithm == 'RS256' else 'unsafe-shared-secret-exceeds-32-bytes-for-tests',
                          algorithm=algorithm, headers={'kid': 'key-1'})

    with TestClient(create_app(), base_url='http://localhost') as client:
        yield client, token


def test_missing_or_spoofed_identity_is_rejected(identity):
    client, token = identity
    assert client.get('/api/dashboard').status_code == 401
    assert client.get('/api/dashboard', auth=('operator', 'a-local-password-longer-than-16')).status_code == 401
    assert client.get('/api/dashboard', headers={'X-AdultCam-Role': 'admin'}).status_code == 401
    assert client.get('/api/dashboard', headers={'Authorization': 'Bearer fake.token'}).status_code == 401


def test_valid_viewer_may_read_but_not_mutate(identity):
    client, token = identity
    headers = {'Authorization': 'Bearer ' + token(['viewer']), 'X-AdultCam-Request': '1'}
    assert client.get('/api/dashboard', headers=headers).status_code == 200
    assert client.get('/api/auth/me', headers=headers).json()['role'] == 'viewer'
    assert client.post('/api/sessions', headers=headers, json={'title': 'Forbidden'}).status_code == 403
    assert client.post('/api/ledger', headers=headers, json={
        'platform': 'Demo', 'currency': 'USD', 'category': 'TIP', 'amount_minor': 100}).status_code == 403


def test_operator_can_prepare_session_but_cannot_edit_finance_or_attestation(identity):
    client, token = identity
    headers = {'Authorization': 'Bearer ' + token(['operator']), 'X-AdultCam-Request': '1'}
    assert client.post('/api/sessions', headers=headers, json={'title': 'Test'}).status_code == 201
    assert client.post('/api/attestations', headers=headers, json={
        'adults_verified': True, 'informed_consent': True,
        'account_authorized': True, 'terms_checked': True}).status_code == 403
    assert client.post('/api/ledger', headers=headers, json={
        'platform': 'Demo', 'currency': 'USD', 'category': 'TIP', 'amount_minor': 100}).status_code == 403


def test_admin_can_record_attestation_and_ledger(identity):
    client, token = identity
    headers = {'Authorization': 'Bearer ' + token(['admin']), 'X-AdultCam-Request': '1'}
    assert client.post('/api/attestations', headers=headers, json={
        'adults_verified': True, 'informed_consent': True,
        'account_authorized': True, 'terms_checked': True}).status_code == 201
    assert client.post('/api/ledger', headers=headers, json={
        'platform': 'Demo', 'currency': 'USD', 'category': 'TIP', 'amount_minor': 100}).status_code == 201
    events = client.get('/api/dashboard', headers=headers).json()['events']
    written = [e for e in events if e['kind'] in ('LEDGER_MANUAL_ENTRY', 'ATTESTATION_RECORDED')]
    assert len(written) == 2
    assert all(e['detail']['operator_subject'] == 'operator-123' for e in written)


@pytest.mark.parametrize('changes', [
    {'audience': 'other-api'},
    {'issuer': 'https://wrong.example.test/'},
    {'expires': -100},
    {'algorithm': 'HS256'},
    {'roles': 'admin'},
    {'roles': ['administrator']},
])
def test_invalid_tokens_do_not_grant_access(identity, changes):
    client, make_token = identity
    options = {'roles': ['viewer']}
    options.update(changes)
    tok = make_token(**options)
    status = client.get('/api/dashboard', headers={'Authorization': 'Bearer ' + tok}).status_code
    assert status in {401, 403}


def test_oidc_requires_explicit_tls_issuer_and_jwks(monkeypatch, tmp_path):
    monkeypatch.setenv('ADULTCAM_AUTH_MODE', 'oidc')
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD', 'a-local-password-longer-than-16')
    monkeypatch.setenv('ADULTCAM_DB_PATH', str(tmp_path / 'test.sqlite3'))
    monkeypatch.setenv('ADULTCAM_OIDC_AUDIENCE', 'adultcam-api')
    monkeypatch.setenv('ADULTCAM_OIDC_ISSUER', 'http://idp.invalid')
    monkeypatch.setenv('ADULTCAM_OIDC_JWKS_URL', 'http://idp.invalid/jwks.json')
    with pytest.raises(ValueError):
        create_app()
