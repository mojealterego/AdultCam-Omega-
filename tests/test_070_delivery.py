"""Receiver evidence must be cryptographically attributable and never promoted to platform receipt."""
from datetime import datetime, timedelta, timezone
import json
import os
import pytest
from fastapi.testclient import TestClient

from adultcam.ingest_receipts import IngestProof, canonical_payload, signature, verify_proof
from adultcam.app import create_app

SECRET = 'a-strong-local-test-key-with-more-than-32-bytes'


def make_proof(**changes):
    record = {'receiver_id': 'my-private-ingest', 'session_id': 7,
              'nonce': 'a-globally-unique-test-nonce', 'received_frames': 15,
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'transport': 'RTMPS', 'scope': 'OWNED_INGEST'}
    record.update(changes)
    return record


def test_valid_proof_is_owned_ingest_only():
    body = make_proof()
    proof = verify_proof(body, signature(SECRET, body), SECRET, {'my-private-ingest'})
    assert proof.platform_delivery == 'UNVERIFIED'
    assert proof.verification == 'OWNED_INGEST_RECEIVED'


@pytest.mark.parametrize('override', [
    {'received_frames': 0}, {'received_frames': -1}, {'scope': 'EXTERNAL_PLATFORM'},
    {'transport': 'RTMP'}, {'receiver_id': 'unregistered'},
    {'observed_at': (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()},
    {'observed_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()},
])
def test_invalid_evidence_never_promotes_delivery(override):
    body = make_proof(**override)
    with pytest.raises(ValueError):
        verify_proof(body, signature(SECRET, body), SECRET, {'my-private-ingest'})


def test_signature_binds_every_field_and_is_constant_length():
    body = make_proof()
    sig = signature(SECRET, body)
    assert len(sig) == 64
    with pytest.raises(ValueError):
        verify_proof({**body, 'received_frames': 999}, sig, SECRET, {'my-private-ingest'})
    with pytest.raises(ValueError):
        verify_proof(body, 'invalid', SECRET, {'my-private-ingest'})


def test_canonical_signature_independent_of_json_order():
    body = make_proof()
    assert canonical_payload(body) == canonical_payload(dict(reversed(list(body.items()))))


def test_api_replay_protection_and_no_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('ADULTCAM_ADMIN_PASSWORD', 'a-local-admin-password-is-long')
    monkeypatch.setenv('ADULTCAM_DB_PATH', str(tmp_path / 'db.sqlite3'))
    monkeypatch.setenv('ADULTCAM_INGEST_HMAC_KEY', SECRET)
    monkeypatch.setenv('ADULTCAM_INGEST_RECEIVERS', 'my-private-ingest')
    with TestClient(create_app(), base_url='http://localhost') as client:
        client.auth = ('operator', 'a-local-admin-password-is-long')
        client.headers['X-AdultCam-Request'] = '1'
        profile = client.post('/api/sessions', json={'title': 'Private testing'})
        sid = profile.json()['id']
        body = make_proof(session_id=sid)
        sig = signature(SECRET, body)
        denied = client.post('/api/ingest/receipts', json=body)
        assert denied.status_code == 401 or denied.status_code == 403
        denied = client.post('/api/ingest/receipts', json=body, headers={'X-AdultCam-Ingest-Signature':'0'*64})
        assert denied.status_code == 403
        accepted = client.post('/api/ingest/receipts', json=body,
                               headers={'X-AdultCam-Ingest-Signature': sig})
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()['verification'] == 'OWNED_INGEST_RECEIVED'
        assert accepted.json()['platform_delivery'] == 'UNVERIFIED'
        assert SECRET not in accepted.text
        assert sig not in accepted.text
        replay = client.post('/api/ingest/receipts', json=body, headers={'X-AdultCam-Ingest-Signature': sig})
        assert replay.status_code == 409
        history = client.get(f'/api/ingest/receipts?session_id={sid}')
        assert history.status_code == 200
        assert len(history.json()['receipts']) == 1
        assert SECRET not in history.text
        assert sig not in history.text
