"""Fail-closed privacy transform: invalid/stale/lost detections produce only black."""
import io
import pytest

from adultcam.privacy_frames import FaceBox, PrivacyGate, process_raw_rgb24


def test_missing_or_untrusted_detection_blackouts_every_pixel():
    gate = PrivacyGate(width=4,height=3,expected_faces=1)
    raw = bytes(range(36))
    assert gate.render(raw, None) == bytes(36)
    assert gate.render(raw, []) == bytes(36)
    assert gate.render(raw, [FaceBox(0,0,2,2,0.3)]) == bytes(36)
    assert gate.render(raw, [FaceBox(-1,0,3,3,1)]) == bytes(36)
    assert gate.render(raw, [FaceBox(0,0,4,3,1),FaceBox(1,1,2,2,1)]) == bytes(36)


def test_approved_face_region_is_blacked_out_but_not_other_pixels():
    gate=PrivacyGate(width=4,height=3,expected_faces=1)
    raw=bytes([255]*36)
    out=gate.render(raw,[FaceBox(1,0,3,2,0.99)])
    assert len(out)==len(raw)
    for y in range(3):
        for x in range(4):
            pixel=out[3*(y*4+x):3*(y*4+x)+3]
            assert pixel == (bytes(3) if (1<=x<3 and y<2) else bytes([255]*3))


def test_truncated_frame_is_never_output():
    source=io.BytesIO(bytes([120]*35))
    sink=io.BytesIO()
    with pytest.raises(ValueError):
        process_raw_rgb24(source,sink,width=4,height=3)
    assert sink.getvalue()==b''


def test_opaque_stream_processes_multiple_frames_without_leaking():
    raw=bytes([254]*72)
    source=io.BytesIO(raw)
    sink=io.BytesIO()
    assert process_raw_rgb24(source,sink,width=4,height=3)==2
    assert sink.getvalue()==bytes(72)


def test_invalid_dimensions_rejected():
    with pytest.raises(ValueError):
        PrivacyGate(width=0,height=20)
    with pytest.raises(ValueError):
        PrivacyGate(width=6000,height=6000)
