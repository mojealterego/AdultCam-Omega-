"""Fail-closed RGB24 privacy transform for authorized footage only.

Without verified detector every frame is black. External input and OBS
must be wired so no raw-camera fallback can bypass this process.
"""
from __future__ import annotations

import argparse
import sys
from typing import BinaryIO, Callable
from .privacy_frames import FaceBox, PrivacyGate

FaceDetector = Callable[[bytes, int, int], list[FaceBox] | None]


class SafeRGBPipeline:
    def __init__(self, width: int, height: int, *, detector: FaceDetector | None,
                 expected_faces: int = 1, min_confidence: float = 0.90,
                 padding_ratio: float = 0.35):
        if not 0 <= padding_ratio <= 1:
            raise ValueError('Padding ratio out of range')
        self.gate = PrivacyGate(width=width, height=height, expected_faces=expected_faces,
                                min_confidence=min_confidence)
        self.detector = detector
        self.padding_ratio = padding_ratio
        self.width = width
        self.height = height
        self.state = 'BLACKOUT'
        self.reason = 'NO_VERIFIED_DETECTOR'

    def transform(self, frame: bytes) -> bytes:
        size = self.width*self.height*3
        if not isinstance(frame, bytes) or len(frame) != size:
            self.state = 'BLACKOUT'
            self.reason = 'INVALID_FRAME'
            raise ValueError('Incomplete RGB24 frame')
        if self.detector is None:
            return self._blackout('NO_VERIFIED_DETECTOR')
        try:
            faces = self.detector(frame, self.width, self.height)
        except Exception:
            return self._blackout('DETECTION_FAILED')
        if not isinstance(faces, list) or len(faces) != self.gate.expected_faces:
            return self._blackout('FACE_COUNT_MISMATCH')
        padded = []
        for face in faces:
            if not isinstance(face, FaceBox) or not self.gate.min_confidence <= face.confidence <= 1:
                return self._blackout('LOW_CONFIDENCE')
            if not (0 <= face.x0 < face.x1 <= self.width and 0 <= face.y0 < face.y1 <= self.height):
                return self._blackout('INVALID_FACE_REGION')
            dx = int((face.x1-face.x0)*self.padding_ratio + 0.5)
            dy = int((face.y1-face.y0)*self.padding_ratio + 0.5)
            padded.append(FaceBox(max(0,face.x0-dx), max(0,face.y0-dy),
                                  min(self.width,face.x1+dx), min(self.height,face.y1+dy),
                                  face.confidence))
        result = self.gate.render(frame, padded)
        if result == bytes(size):
            return self._blackout('INVALID_OR_COMPLETE_BLACKOUT')
        self.state='MASKED'
        self.reason='DETECTION_ACCEPTED_NOT_CERTIFIED'
        return result

    def _blackout(self, reason: str) -> bytes:
        self.state='BLACKOUT'
        self.reason=reason
        return bytes(self.width*self.height*3)


def process_rgb24_stream(source: BinaryIO, sink: BinaryIO, processor: SafeRGBPipeline) -> int:
    expected = processor.width*processor.height*3
    frames = 0
    while True:
        frame = source.read(expected)
        if not frame:
            return frames
        if len(frame) != expected:
            raise ValueError('Truncated RGB24 input frame')
        out = processor.transform(frame)
        if len(out) != expected:
            raise RuntimeError('Invalid privacy output size')
        sink.write(out)
        sink.flush()
        frames += 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='AdultCam fail-closed RGB24 filter')
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        pipeline = SafeRGBPipeline(args.width, args.height, detector=None)
        process_rgb24_stream(sys.stdin.buffer, sys.stdout.buffer, pipeline)
        return 0
    except (ValueError, BrokenPipeError, OSError):
        print('Privacy pipeline stopped: invalid stream.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
