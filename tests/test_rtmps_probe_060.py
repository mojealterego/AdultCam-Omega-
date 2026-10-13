"""Real loopback encrypted media test; does not claim platform delivery."""
import shutil
import pytest
from adultcam.rtmps_probe import synthetic_tls_roundtrip


def test_probe_rejects_invalid_duration():
    with pytest.raises(ValueError):
        synthetic_tls_roundtrip(duration=1)


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('openssl'),
                    reason='FFmpeg and OpenSSL required for TLS roundtrip')
def test_synthetic_rtmps_verified_tls_and_frames():
    report=synthetic_tls_roundtrip(duration=3)
    assert report['verification']=='RECEIVER_VIDEO_FRAMES', report
    assert report['tls_verified'] is True
    assert report['video_frames']>=3
    assert report['network_scope']=='127.0.0.1_ONLY'
    assert report['platform_delivery']=='UNVERIFIED'
    assert report['obs_tested'] is False
    assert report['wrote_media_files'] is False
