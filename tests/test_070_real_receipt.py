"""End-to-end (localhost) synthetic RTMPS frame reception + signed evidence."""
import shutil
from datetime import datetime, timezone
import uuid

import pytest
from adultcam.ingest_receipts import signature, verify_proof
from adultcam.rtmps_probe import synthetic_tls_roundtrip


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('openssl'),
                    reason='ffmpeg and openssl required')
def test_actual_rtmps_receipt_can_be_signed_and_verified():
    report = synthetic_tls_roundtrip(duration=2)
    assert report['verification'] == 'RECEIVER_VIDEO_FRAMES', report
    assert report['tls_verified'] is True
    assert report['video_frames'] >= 3
    body = {
        'session_id': 3, 'receiver_id': 'local-test-ingest',
        'nonce': uuid.uuid4().hex,
        'received_frames': report['video_frames'],
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'transport': 'RTMPS', 'scope': 'OWNED_INGEST',
    }
    key = 'a-dedicated-test-only-receiver-hmac-secret-long'
    proof = verify_proof(body, signature(key, body), key, {'local-test-ingest'})
    assert proof.received_frames >= 3
    assert proof.platform_delivery == 'UNVERIFIED'
