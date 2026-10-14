"""Offline-first provider catalog. These are unconnected future account slots."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Provider:
    slug: str
    label: str
    available_adapter: str

PROVIDERS=(
    Provider('chaturbate','Chaturbate','READ_ONLY_OFFICIAL_STATS_ADAPTER_UNCONNECTED'),
    Provider('twitch','Twitch','READ_ONLY_HELIX_ADAPTER_UNCONNECTED'),
    Provider('showup','ShowUp','MANUAL_ONLY_NEEDS_TERMS_REVIEW'),
)
PROVIDER_BY_SLUG={p.slug:p for p in PROVIDERS}

def public_catalog()->list[dict]:
    return [{'platform_id':p.slug,'label':p.label,'implementation':p.available_adapter,
             'external_account_connected':False,
             'operator_action_required':'CREATE_ACCOUNT_AND_GRANT_AUTHORIZATION',
             'stream_control_capability':'NOT_AVAILABLE'} for p in PROVIDERS]

def public_slot(row:dict)->dict:
    return {'id':row['id'],'platform_id':row['platform_id'],
            'account_label':row['account_label'],'status':row['status'],
            'connected':False,'external_requests_sent':0,
            'external_revocation_performed':False,
            'created_at':row['created_at'],'updated_at':row['updated_at'],
            'next_step':'CREATE_ACCOUNT_AND_AUTHORIZE_EXTERNALLY'
              if row['status']=='AWAITING_AUTHORIZATION'
              else 'NONE' if row['status']=='DISABLED' else 'PREPARE_CONNECTION'}
