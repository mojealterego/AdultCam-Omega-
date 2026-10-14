"""Fail-closed production gate: independent Ed25519 auditor and SHA-256 evidence.

A valid signature confirms reviewed bytes, not that real hardware tests happened.
The independent reviewer must verify authenticity of real-world evidence.
"""
from __future__ import annotations
import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

REQUIRED_CHECKS = (
    'real_obs_studio_start_stop',
    'authorized_platform_api_and_delivery',
    'end_to_end_privacy_fail_closed',
    'public_private_exclusion_verified',
    'oidc_https_rbac_security_audit',
    'android_s24_ultra_device_acceptance',
    'age_consent_and_platform_terms_review',
    'incident_response_and_rollback_drill',
    'backup_restore_and_retention_review',
)
MAX_BUNDLE_BYTES = 256 * 1024
MAX_EVIDENCE_BYTES = 1024 * 1024
MAX_EVIDENCE_AGE = timedelta(days=30)


@dataclass(frozen=True)
class GateResult:
    approved: bool
    status: str
    reason_codes: tuple[str, ...]
    checks: tuple[str, ...] = ()

    def as_dict(self):
        return {'approved': self.approved, 'status': self.status,
                'reason_codes': list(self.reason_codes),
                'checks': list(self.checks), 'release': '1.0.0',
                'external_streams_started': False}


def _parse_time(raw):
    if not isinstance(raw, str):
        raise ValueError('BAD_TIME')
    result = datetime.fromisoformat(raw)
    if result.tzinfo is None:
        raise ValueError('NAIVE_TIME')
    return result.astimezone(timezone.utc)


def _parse_json(data):
    obj = json.loads(data)
    if not isinstance(obj, dict):
        raise ValueError('BAD_JSON')
    return obj


def _proof_file(directory, name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\\.json', name):
        raise ValueError('BAD_PATH')
    file = directory / name
    if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(directory.resolve()):
        raise ValueError('BAD_ARTIFACT')
    if file.stat().st_size > MAX_EVIDENCE_BYTES:
        raise ValueError('OVERSIZED_ARTIFACT')
    return file


def evaluate_release(bundle_path, reviewer_public_key, *, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        path = Path(bundle_path).expanduser()
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BUNDLE_BYTES:
            return GateResult(False, 'BLOCKED', ('MISSING_OR_OVERSIZED_BUNDLE',))
        doc = _parse_json(path.read_bytes())
        signature = doc.pop('signature', None)
        if not isinstance(signature, str) or len(signature) > 256:
            raise ValueError('MISSING_SIGNATURE')
        if not isinstance(reviewer_public_key, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', reviewer_public_key):
            raise ValueError('UNPINNED_REVIEW_KEY')
        if doc.get('project') != 'AdultCam Omega' or doc.get('release') != '1.0.0' or doc.get('schema_version') != 1:
            raise ValueError('WRONG_RELEASE')
        payload = json.dumps(doc, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode('utf-8')
        padded = signature + '=' * (-len(signature) % 4)
        signature_raw = base64.urlsafe_b64decode(padded)
        if len(signature_raw) != 64:
            raise ValueError('BAD_SIGNATURE_LENGTH')
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(reviewer_public_key)).verify(signature_raw, payload)
        issued, expires = _parse_time(doc.get('issued_at')), _parse_time(doc.get('expires_at'))
        if not (now - MAX_EVIDENCE_AGE <= issued <= now + timedelta(minutes=5)
                and issued < now < expires <= issued + MAX_EVIDENCE_AGE):
            raise ValueError('STALE_RELEASE_REVIEW')
        checks = doc.get('checks')
        if not isinstance(checks, dict) or set(checks) != set(REQUIRED_CHECKS):
            raise ValueError('INCOMPLETE_RELEASE_REVIEW')
        for check_name in REQUIRED_CHECKS:
            item = checks[check_name]
            if not isinstance(item, dict) or item.get('status') != 'PASS':
                raise ValueError('CHECK_NOT_PASSED')
            sha = item.get('sha256')
            if not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{64}', sha):
                raise ValueError('INVALID_HASH')
            file = _proof_file(path.parent, item.get('evidence'))
            raw = file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError('EVIDENCE_TAMPERED')
            proof = _parse_json(raw)
            if proof.get('check_id') != check_name or proof.get('passed') is not True:
                raise ValueError('EVIDENCE_DOES_NOT_PASS')
            observed = _parse_time(proof.get('observed_at'))
            if not (now - MAX_EVIDENCE_AGE <= observed <= now + timedelta(minutes=5)):
                raise ValueError('STALE_EVIDENCE')
            if not isinstance(proof.get('review_reference'), str) or len(proof['review_reference']) < 8:
                raise ValueError('UNTRACEABLE_REVIEW')
        return GateResult(True, 'REVIEW_EVIDENCE_VERIFIED', (), REQUIRED_CHECKS)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, InvalidSignature, binascii.Error) as exc:
        reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'[A-Z_]{4,64}', str(exc)) else 'INVALID_OR_UNTRUSTED_EVIDENCE'
        return GateResult(False, 'BLOCKED', (reason,))


def enforce_mode():
    mode = os.getenv('ADULTCAM_RELEASE_MODE', 'development')
    if mode not in ('development', 'staging', 'production'):
        raise RuntimeError('RELEASE_GATE_BLOCKED: invalid ADULTCAM_RELEASE_MODE')
    if mode != 'production':
        return GateResult(False, 'NON_PRODUCTION_MODE', ('NOT_PRODUCTION',))
    required = (
        'ADULTCAM_OIDC_ISSUER', 'ADULTCAM_OIDC_AUDIENCE',
        'ADULTCAM_OIDC_JWKS_URL', 'ADULTCAM_OIDC_CLIENT_ID',
        'ADULTCAM_OIDC_AUTHORIZATION_URL', 'ADULTCAM_OIDC_TOKEN_URL',
        'ADULTCAM_PUBLIC_ORIGIN',
    )
    if any(not os.getenv(key) for key in required):
        raise RuntimeError('RELEASE_GATE_BLOCKED: verified OIDC and HTTPS required')
    origin = urlsplit(os.getenv('ADULTCAM_PUBLIC_ORIGIN', ''))
    if (origin.scheme != 'https' or not origin.hostname or origin.username
            or origin.password or origin.query or origin.fragment or origin.path
            or origin.hostname in {'localhost', '127.0.0.1'}):
        raise RuntimeError('RELEASE_GATE_BLOCKED: trusted HTTPS origin required')
    result = evaluate_release(os.getenv('ADULTCAM_RELEASE_BUNDLE', ''),
                              os.getenv('ADULTCAM_RELEASE_REVIEW_PUBKEY', ''))
    if not result.approved:
        raise RuntimeError('RELEASE_GATE_BLOCKED: ' + result.reason_codes[0])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='AdultCam Omega release evidence gate')
    parser.add_argument('--bundle', default=os.getenv('ADULTCAM_RELEASE_BUNDLE', ''))
    parser.add_argument('--review-pubkey', default=os.getenv('ADULTCAM_RELEASE_REVIEW_PUBKEY', ''))
    args = parser.parse_args(argv)
    result = evaluate_release(args.bundle, args.review_pubkey)
    print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.approved else 2


if __name__ == '__main__':
    sys.exit(main())
