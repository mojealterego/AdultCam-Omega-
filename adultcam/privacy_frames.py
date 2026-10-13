"""Minimal fail-closed RGB24 privacy transport primitive.

No face detector is bundled. In absence of a trusted, timely detection result,
all pixels are replaced with opaque black. Bounding boxes alone are NOT
sufficient to certify that every person has been anonymized; deployment must
separately validate detectors, scene topology, timing, and outputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Iterable


@dataclass(frozen=True)
class FaceBox:
    x0: int
    y0: int
    x1: int
    y1: int
    confidence: float


class PrivacyGate:
    def __init__(self, *, width: int, height: int, expected_faces: int = 1,
                 min_confidence: float = 0.90):
        if (type(width) is not int or type(height) is not int
                or not 1 <= width <= 4096 or not 1 <= height <= 2160
                or width * height > 4_000_000):
            raise ValueError('Nieprawidłowy rozmiar klatki RGB24.')
        if type(expected_faces) is not int or expected_faces not in (1, 2):
            raise ValueError('Tylko jedno- i dwuosobowy tryb testowy.')
        if not 0.75 <= min_confidence <= 1.0:
            raise ValueError('Niewłaściwy próg pewności.')
        self.width, self.height = width, height
        self.expected_faces = expected_faces
        self.min_confidence = min_confidence

    def render(self, frame: bytes, detections: list[FaceBox] | None) -> bytes:
        size = self.width * self.height * 3
        if not isinstance(frame, bytes) or len(frame) != size:
            raise ValueError('Ucięta lub źle sformatowana klatka.')
        blackout = bytes(size)
        if detections is None or not isinstance(detections, list) or len(detections) != self.expected_faces:
            return blackout
        for face in detections:
            if (not isinstance(face, FaceBox) or
                any(type(n) is not int for n in (face.x0, face.y0, face.x1, face.y1)) or
                not (0 <= face.x0 < face.x1 <= self.width and 0 <= face.y0 < face.y1 <= self.height) or
                not isinstance(face.confidence, (float, int)) or
                not self.min_confidence <= face.confidence <= 1.0):
                return blackout
        result = bytearray(frame)
        for face in detections:
            for y in range(face.y0, face.y1):
                begin = 3 * (y * self.width + face.x0)
                finish = 3 * (y * self.width + face.x1)
                result[begin:finish] = bytes(finish - begin)
        return bytes(result)


def process_raw_rgb24(source: BinaryIO, sink: BinaryIO, *, width: int,
                      height: int) -> int:
    """Blackout-by-default filter. Stdout contains only complete redacted frames.

    This stream has no face detector. It is a safe test/BRB frame source, not an
    operational selective face masker. Caller must stop on errors.
    """
    gate = PrivacyGate(width=width, height=height)
    size = width * height * 3
    count = 0
    while True:
        frame = source.read(size)
        if not frame:
            return count
        if len(frame) != size:
            raise ValueError('Niekompletna klatka: wyjście zatrzymane.')
        sink.write(gate.render(frame, None))
        sink.flush()
        count += 1


def main(argv: list[str] | None = None) -> int:
    """Byte-clean stdout: only blacked-out frames, never logging or raw input."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='AdultCam Ω full-frame privacy blackout (raw RGB24)')
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        process_raw_rgb24(sys.stdin.buffer, sys.stdout.buffer,
                          width=args.width, height=args.height)
    except (ValueError, BrokenPipeError) as exc:
        print('Privacy output stopped: invalid/incomplete stream.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
