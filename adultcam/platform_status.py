"""Official, read-only Twitch Helix status adapter for non-adult streams.

Twitch forbids pornographic streaming. Helix LIVE status is not proof of
end-to-end delivery of a specific video or authorization to broadcast.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Callable
import httpx

HELIX_URL = 'https://api.twitch.tv/helix/streams'
CACHE_SECONDS = 30.0


class PlatformStatusError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class TwitchHelixReadOnly:
    def __init__(self, *, client_id: str, bearer_token: str, broadcaster_id: str,
                 client: httpx.Client | None = None,
                 monotonic: Callable[[], float] = time.monotonic):
        if not client_id or not isinstance(client_id, str) or len(client_id) > 128 or not re.fullmatch(r'[A-Za-z0-9_-]+', client_id):
            raise ValueError('Invalid OAuth client ID')
        if not bearer_token or not isinstance(bearer_token, str) or len(bearer_token) > 2048 or not re.fullmatch(r'[A-Za-z0-9_-]+', bearer_token):
            raise ValueError('Invalid OAuth bearer token')
        if not isinstance(broadcaster_id, str) or not re.fullmatch(r'[0-9]{1,30}', broadcaster_id):
            raise ValueError('Invalid Twitch broadcaster ID')
        self._client_id = client_id
        self._bearer_token = bearer_token
        self._broadcaster_id = broadcaster_id
        self._client = client
        self._clock = monotonic
        self._last_monotonic: float | None = None
        self._latest: dict | None = None

    def read_status(self) -> dict:
        now = self._clock()
        if self._latest is not None and self._last_monotonic is not None:
            if 0 <= now - self._last_monotonic < CACHE_SECONDS:
                return {**self._latest, 'cached': True}
        try:
            if self._client is None:
                with httpx.Client(timeout=httpx.Timeout(5), follow_redirects=False, trust_env=False) as owned:
                    response = self._send(owned)
            else:
                response = self._send(self._client)
            if response.status_code != 200:
                raise PlatformStatusError(f'UPSTREAM_{response.status_code}')
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
                raise PlatformStatusError('INVALID_RESPONSE')
            data = payload['data']
            if not data:
                state = 'OFFLINE'
            elif len(data) == 1 and isinstance(data[0], dict) and (
                    data[0].get('user_id') == self._broadcaster_id and
                    data[0].get('type') == 'live' and
                    isinstance(data[0].get('id'), str)):
                state = 'LIVE'
            else:
                state = 'UNVERIFIED'
        except PlatformStatusError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise PlatformStatusError('STATUS_UNAVAILABLE') from None
        result = {
            'platform': 'TWITCH',
            'source': 'OFFICIAL_HELIX_READ_ONLY',
            'broadcaster_id': self._broadcaster_id,
            'state': state,
            'observed_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'cached': False,
            'content_policy': 'NON_ADULT_ONLY',
            'broadcast_control': 'DISABLED',
            'platform_delivery': 'UNVERIFIED',
        }
        self._latest = result
        self._last_monotonic = now
        return result.copy()

    def _send(self, client: httpx.Client) -> httpx.Response:
        return client.get(HELIX_URL, params={'user_id': self._broadcaster_id}, headers={
            'Client-Id': self._client_id,
            'Authorization': f'Bearer {self._bearer_token}',
            'Accept': 'application/json',
        }, timeout=5, follow_redirects=False)


CHaturbate_STATS_URL = 'https://chaturbate.com/statsapi/'
CHaturbate_CACHE_SECONDS = 300.0


class ChaturbateStatsReadOnly:
    """Owner-authorized official read-only user statistics.

    Official API requires a secret query parameter; never log the full URL
    or HTTP traces, and only call the pinned HTTPS origin.
    """

    def __init__(self, *, username: str, token: str,
                 client: httpx.Client | None = None,
                 monotonic: Callable[[], float] = time.monotonic):
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,64}', username):
            raise ValueError('Invalid broadcaster username')
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9]{24}', token):
            raise ValueError('Invalid stats API token')
        self._username=username
        self._token=token
        self._client=client
        self._clock=monotonic
        self._recent=None
        self._timestamp=None

    def read_status(self) -> dict:
        now=self._clock()
        if self._timestamp is not None and self._recent is not None and 0 <= now-self._timestamp<CHaturbate_CACHE_SECONDS:
            return {**self._recent,'cached':True}
        try:
            if self._client is None:
                with httpx.Client(timeout=httpx.Timeout(5),follow_redirects=False,trust_env=False) as client:
                    response=self._send(client)
            else:
                response=self._send(self._client)
            if response.status_code != 200:
                raise PlatformStatusError(f'UPSTREAM_{response.status_code}')
            payload=response.json()
            if not isinstance(payload,dict):
                raise PlatformStatusError('INVALID_RESPONSE')
            duration=payload.get('time_online')
            if payload.get('username') != self._username or type(duration) is not int:
                state='UNVERIFIED'
            elif duration == -1:
                state='OFFLINE_REPORTED'
            elif 0 <= duration <= 60*24*365:
                state='ONLINE_REPORTED'
            else:
                state='UNVERIFIED'
        except PlatformStatusError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise PlatformStatusError('STATUS_UNAVAILABLE') from None
        result={'platform':'CHATURBATE','source':'OFFICIAL_OWNER_STATS_API',
                'state':state,'broadcaster':self._username,
                'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'provider_refresh_seconds':300,'cached':False,
                'broadcast_control':'DISABLED','platform_delivery':'UNVERIFIED'}
        self._recent=result
        self._timestamp=now
        return result.copy()

    def _send(self, client: httpx.Client) -> httpx.Response:
        return client.get(CHaturbate_STATS_URL,
                          params={'username':self._username,'token':self._token},
                          headers={'Accept':'application/json'},
                          timeout=5,follow_redirects=False)
