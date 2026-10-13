"""Fail-closed synthetic RGB24 video invariants."""
import io
import pytest
from adultcam.privacy_pipeline import SafeRGBPipeline, process_rgb24_stream
from adultcam.privacy_frames import FaceBox


def high_confidence(*_):
    return [FaceBox(2,2,4,4,confidence=0.98)]


def test_without_detector_every_pixel_is_black():
    frame=b'\xff'*(8*8*3)
    gate=SafeRGBPipeline(8,8,detector=None)
    assert gate.transform(frame)==bytes(len(frame))
    assert gate.state=='BLACKOUT'


def test_padded_box_masks_face_without_raw_passthrough():
    frame=b'\xff'*(8*8*3)
    gate=SafeRGBPipeline(8,8,detector=high_confidence,padding_ratio=0.5)
    result=gate.transform(frame)
    assert result != frame and result != bytes(len(frame))
    assert result[:3]==b'\xff'*3
    assert result[(2*8+2)*3:(2*8+2)*3+3]==b'\x00'*3


def test_missing_or_low_confidence_detections_return_black():
    frame=b'\xff'*(8*8*3)
    for faces in [[],[FaceBox(2,2,4,4,0.20)],
                  [FaceBox(2,2,4,4,0.99)]*2]:
        assert SafeRGBPipeline(8,8,detector=lambda *_:faces).transform(frame)==bytes(len(frame))


def test_crashed_detector_never_releases_unprotected_video():
    gate=SafeRGBPipeline(8,8,detector=lambda *_:(_ for _ in ()).throw(RuntimeError('secret')))
    assert gate.transform(b'\xff'*(8*8*3))==bytes(8*8*3)
    assert 'secret' not in gate.reason


def test_truncated_frame_is_not_forwarded():
    frame=b'\xff'*(8*8*3)
    output=io.BytesIO()
    gate=SafeRGBPipeline(8,8,detector=None)
    with pytest.raises(ValueError):
        process_rgb24_stream(io.BytesIO(frame+frame[:14]),output,gate)
    assert output.getvalue()==bytes(len(frame))
