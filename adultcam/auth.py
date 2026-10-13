"""Fail-closed, opt-in JWT verification for a trusted OIDC issuer.

Browser OAuth login and TLS termination are external responsibilities. This
module only verifies already-issued JWT access tokens for API requests.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient, PyJWKClientError


_ROLES = {'viewer': 0, 'operator': 1, 'admin': 2}


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    source: str

    def allows(self, role: str) -> bool:
        return _ROLES[self.role] >= _ROLES[role]


def _secure_url(value: str) -> tuple[str, int | None]:
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or not u.hostname or u.username or u.password or
                u.fragment or u.query or u.port == 0):
            raise ValueError('Wymagany bezpieczny, jednoznaczny adres HTTPS IdP.')
        return u.hostname.lower(), u.port
    except (ValueError, TypeError) as exc:
        raise ValueError('Wymagany bezpieczny, jednoznaczny adres HTTPS IdP.') from exc


class OidcVerifier:
    def __init__(self, issuer: str, audience: str, jwks_url: str):
        if not issuer or not issuer.strip() or not audience or not audience.strip():
            raise ValueError('Brak identyfikatora OIDC issuer lub audience.')
        if _secure_url(issuer) != _secure_url(jwks_url):
            raise ValueError('JWKS musi pochodzić z tego samego źródła HTTPS co issuer.')
        self.issuer = issuer
        self.audience = audience
        # Short timeout, no permanent cache for keys revoked by the IdP.
        self.jwks = PyJWKClient(jwks_url, cache_keys=False, cache_jwk_set=True,
                                lifespan=120, timeout=3)

    def verify(self, token: str) -> Principal:
        if not token or len(token) > 16384:
            raise ValueError('Nieprawidłowy token dostępu.')
        try:
            header = jwt.get_unverified_header(token)
            # Ignore untrusted header parameters such as jku, jwk, x5u and alg
            # except for rejecting everything but the pinned RS256 algorithm.
            if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
                raise ValueError('Niedozwolony algorytm tokenu.')
            key = self.jwks.get_signing_key(header['kid']).key
            payload = jwt.decode(token, key, algorithms=['RS256'],
                                 issuer=self.issuer, audience=self.audience,
                                 leeway=15,
                                 options={'require': ['iss', 'aud', 'sub', 'iat', 'exp']})
            subject = payload['sub']
            if not isinstance(subject, str) or not 1 <= len(subject) <= 256:
                raise ValueError('Brak tożsamości w tokenie.')
            roles = payload.get('adultcam_roles')
            if not isinstance(roles, list) or not roles or not all(isinstance(x, str) for x in roles):
                raise PermissionError('Brak listy przypisanych ról.')
            permitted = [r for r in roles if r in _ROLES]
            if not permitted:
                raise PermissionError('Nie przyznano uprawnień AdultCam.')
            return Principal(subject=subject, role=max(permitted, key=_ROLES.get), source='oidc')
        except PermissionError:
            raise
        except (jwt.PyJWTError, PyJWKClientError, ValueError, KeyError, TypeError) as exc:
            # Do not include token or upstream exception text in HTTP responses.
            raise ValueError('Nieprawidłowy token dostępu.') from exc


def load_oidc() -> OidcVerifier | None:
    mode = os.getenv('ADULTCAM_AUTH_MODE', 'local')
    if mode == 'local':
        return None
    if mode != 'oidc':
        raise ValueError('ADULTCAM_AUTH_MODE: dozwolone local lub oidc.')
    return OidcVerifier(issuer=os.getenv('ADULTCAM_OIDC_ISSUER', ''),
                        audience=os.getenv('ADULTCAM_OIDC_AUDIENCE', ''),
                        jwks_url=os.getenv('ADULTCAM_OIDC_JWKS_URL', ''))
