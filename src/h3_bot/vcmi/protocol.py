"""Bounded UTF-8 newline-delimited JSON framing."""

from typing import BinaryIO

MAX_FRAME_BYTES = 4 * 1024 * 1024


def read_frame(stream: BinaryIO) -> bytes:
    frame = stream.readline(MAX_FRAME_BYTES + 1)
    if not frame.endswith(b"\n") or len(frame) > MAX_FRAME_BYTES:
        raise ValueError("Missing, truncated, or oversized NDJSON frame")
    return frame
