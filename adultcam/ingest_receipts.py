"""Authenticated evidence from a *controlled, owned* RTMPS ingest receiver.

A valid receipt only proves the sender holding this scoped secret attested to
receiving frames. This is not independent platform-side confirmation and never
upgrades OBS stream state or external platform delivery.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re

_FIELDS = frozenset({'receiver_id', 'session_id', 'nonce', 'received_frames',
                     'observed_at', 'transport', 'scope'})
_IDENTIFIER = re.compile(r'^[a-zA-Z0-9_-]{3,80}$')
_NONCE = re.compile(r'^[a-zA-Z0-9_-]{12,128}$')


@dataclass(frozen=True)
class IngestProof:
    receiver_id: str
    session_id: int
    nonce: str
    received_frames: int
    observed_at: str
    verification: str = 'OWNED_INGEST_RECEIVED'
    platform_delivery: str = 'UNVERIFIED'


def canonical_payload(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def signature(key: str, body: dict) -> str:
    if not isinstance(key, str) or len(key.encode('utf-8')) < 32:
        raise ValueError('Wymagany odrębny klucz HMAC (minimum 32 bajty).')
    return hmac.new(key.encode('utf-8'), canonical_payload(body), hashlib.sha256).hexdigest()


def verify_proof(body: dict, supplied_signature: str, key: str,
                 receivers: set[str], *, clock: datetime | None = None) -> IngestProof:
    if not isinstance(body, dict) or body.keys() != _FIELDS:
        raise ValueError('Niezgodny schemat podpisanego dowodu odbioru.')
    if not isinstance(body['receiver_id'], str) or not _IDENTIFIER.fullmatch(body['receiver_id']):
        raise ValueError('Nieprawidłowy odbiornik.')
    if body['receiver_id'] not in receivers:
        raise ValueError('Niezarejestrowany odbiornik.')
    if type(body['session_id']) is not int or body['session_id'] < 1:
        raise ValueError('Nieprawidłowa sesja.')
    if type(body['received_frames']) is not int or not 1 <= body['received_frames'] <= 10_000_000:
        raise ValueError('Brak pozytywnego potwierdzenia odebranych klatek.')
    if not isinstance(body['nonce'], str) or not _NONCE.fullmatch(body['nonce']):
        raise ValueError('Nieprawidłowy nonce.')
    if body['transport'] != 'RTMPS' or body['scope'] != 'OWNED_INGEST':
        raise ValueError('Nieobsługiwany rodzaj dowodu.')
    try:
        observed = datetime.fromisoformat(body['observed_at'])
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError('Brak strefy czasowej.')
        current = clock or datetime.now(timezone.utc)
        if abs((current - observed).total_seconds()) > 90:
            raise ValueError('Dowód jest nieaktualny.')
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('Niewłaściwy znacznik czasu dowodu.') from exc
    if not isinstance(supplied_signature, str) or not re.fullmatch(r'[0-9a-f]{64}', supplied_signature):
        raise ValueError('Brak poprawnego podpisu dowodu.')
    expected = signature(key, body)
    if not hmac.compare_digest(supplied_signature, expected):
        raise ValueError('Błędny podpis dowodu.')
    return IngestProof(**{k: body[k] for k in ('receiver_id', 'session_id', 'nonce',
                                              'received_frames', 'observed_at')})
