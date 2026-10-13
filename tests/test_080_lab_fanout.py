"""Actual multi-receiver media transport proof: synthetic frames, localhost only."""
import shutil
import pytest
from adultcam.simulcast_lab import run_synthetic_multistream


def test_invalid_multi_receiver_requests_are_refused():
    with pytest.raises(ValueError):
        run_synthetic_multistream(receivers=1, duration=2)
    with pytest.raises(ValueError):
        run_synthetic_multistream(receivers=9, duration=2)
    with pytest.raises(ValueError):
        run_synthetic_multistream(receivers=2, duration=121)


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg unavailable')
def test_two_local_rtmp_sinks_receive_frames_from_one_source():
    out = run_synthetic_multistream(receivers=2, duration=3)
    assert out['result'] == 'LOCAL_SIMULCAST_VERIFIED', out
    assert out['receiver_count'] == 2
    assert len(out['received_frames']) == 2
    assert all(n >= 5 for n in out['received_frames'])
    assert out['broadcast_to_external_platforms'] is False
    assert out['contains_real_people'] is False
    assert out['platform_delivery'] == 'UNVERIFIED'
