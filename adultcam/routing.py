"""Fail-closed multi-destination planning and read-only evidence projection.

No platform keys or credentials, connector writes, stream command, or
private-room transition is permitted through this module.
"""
from __future__ import annotations

from datetime import datetime, timezone


EVIDENCE_WINDOW_SECONDS = 90
MAX_ROUTES_PER_SESSION = 8


def evaluate_route_plan(routes: list[dict], receipts: list[dict],
                        audience: str, *, now: datetime | None = None) -> dict:
    """Project the permitted laboratory evidence; never authorize broadcast.

    A signed local ingest receipt proves only a trusted *owned* receiver
    attested it received frames. It is not a platform confirmation or proof
    of effective face masking, and never allows private transitions.
    """
    if audience not in {'PUBLIC', 'PRIVATE'}:
        raise ValueError('Invalid audience')
    now = now or datetime.now(timezone.utc)
    fresh: set[str] = set()
    for receipt in receipts:
        try:
            recorded = datetime.fromisoformat(receipt['recorded_at'])
            if recorded.tzinfo is None:
                continue
            age = (now - recorded.astimezone(timezone.utc)).total_seconds()
            if (0 <= age <= EVIDENCE_WINDOW_SECONDS
                    and receipt['received_frames'] > 0):
                fresh.add(receipt['receiver_id'])
        except (ValueError, TypeError, KeyError):
            continue

    route_summary = []
    proved = 0
    for route in routes:
        local_proof = (route['capability'] == 'OWNED_INGEST_TEST'
                       and route['receiver_id'] in fresh)
        proved += int(local_proof)
        route_summary.append({
            'route_key': route['route_key'],
            'platform': route['platform'],
            'audience': route['audience'],
            'capability': route['capability'],
            'owned_receiver_evidence': 'FRESH_RECEIPT' if local_proof else 'UNVERIFIED',
            'platform_delivery': 'UNVERIFIED',
        })

    if not routes:
        decision = 'BLOCKED_EMPTY_PLAN'
    elif audience == 'PRIVATE' and any(r['audience'] == 'PUBLIC' for r in routes):
        decision = 'BLOCKED_PUBLIC_ROUTE'
    elif any(r['audience'] != audience for r in routes):
        decision = 'BLOCKED_AUDIENCE_MISMATCH'
    elif any(r['capability'] != 'OWNED_INGEST_TEST' for r in routes):
        decision = 'BLOCKED_MANUAL_ONLY'
    elif proved != len(routes):
        decision = 'BLOCKED_MISSING_FRESH_RECEIPT'
    else:
        decision = 'LAB_EVIDENCE_ONLY'

    return {
        'decision': decision,
        'audience': audience,
        'route_count': len(routes),
        'owned_receivers_with_fresh_proof': proved,
        'routes': route_summary,
        'private_transition_authorized': False,
        'external_actions_performed': 0,
        'platform_delivery': 'UNVERIFIED',
        'warning': 'PLAN_ONLY_NO_EXTERNAL_STREAM_OR_PRIVACY_GUARANTEE',
    }
