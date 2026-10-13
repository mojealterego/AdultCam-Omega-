"""Public, loopback-only transport proof without third-party broadcasting."""
import shutil

import pytest

from adultcam.rtmp_probe import measure_frames, run_private_probe


def test_frame_counter_only_trusts_numeric_receiver_progress():
    assert measure_frames('frame=2\\nprogress=continue\\nframe=10\\nprogress=end') == 10
    assert measure_frames('frame=99secret\\nframe=-1\\nframe=none\\n') == 0


def test_invalid_ports_or_modes_are_rejected():
    with pytest.raises(ValueError):
        run_private_probe(mode='obs', port=19350, duration=2, confirmed=False)
    with pytest.raises(ValueError):
        run_private_probe(mode='synthetic', port=80, duration=2, confirmed=True)
    with pytest.raises(ValueError):
        run_private_probe(mode='synthetic', port=19350, duration=200, confirmed=True)


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not installed')
def test_real_ffmpeg_loopback_video_receipt():
    result = run_private_probe(mode='synthetic', port=0, duration=2, confirmed=True)
    assert result['verification'] == 'RECEIVER_VIDEO_FRAMES', result
    assert result['video_frames'] >= 3
    assert result['network_scope'] == '127.0.0.1_ONLY'
    assert result['platform_delivery'] == 'UNVERIFIED'
    assert result['obs_tested'] is False
    assert result['source'] == 'GENERATED_COLOR_BARS'
