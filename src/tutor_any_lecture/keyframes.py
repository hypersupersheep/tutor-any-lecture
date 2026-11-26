"""Key frames of a local video with no slides: a perceptual hash and which frames to keep."""

from __future__ import annotations

import math

# A frame whose 32x32 gray pixels span less than this is blank (a black or white screen).
BLANK_RANGE = 16
# Two hashes this many bits apart or fewer show the same picture.
DUPLICATE_BITS = 6
# Kept frames are at least this many seconds apart.
MIN_GAP_SECONDS = 8.0
# At most this many key frames per video.
MAX_FRAMES = 120

_SIDE = 32  # the hash reads the frame at 32x32 pixels
_LOW = 8  # and keeps the 8x8 lowest frequencies of its DCT
# _COS[u][x] = cos(pi * (2x + 1) * u / 64), shared by the rows and the columns.
_COS = [[math.cos(math.pi * (2 * x + 1) * u / (2 * _SIDE)) for x in range(_SIDE)] for u in range(_LOW)]


def frame_hash(image) -> int | None:
    """A 64-bit perceptual hash (pHash) of a Pillow image of any size and mode; None when it is blank.

    The image is read as 32x32 gray pixels. Its 8x8 lowest DCT-II coefficients (unnormalised,
    rows first, then columns), in row-major order, are compared with their median: bit 63 is
    the first coefficient, bit 0 the last, each 1 when the coefficient is above the median.
    Size, mild scaling and JPEG noise move few bits; a different picture moves many.
    """
    from PIL import Image

    with image.convert("L") as gray, gray.resize((_SIDE, _SIDE), Image.Resampling.LANCZOS) as small:
        data = small.tobytes()  # getdata() is deprecated; tobytes() is row-major, one byte a pixel
    if max(data) - min(data) < BLANK_RANGE:
        return None
    rows = [data[y * _SIDE:(y + 1) * _SIDE] for y in range(_SIDE)]
    # r[y][u]: the 8 coefficients of each row.
    r = [[sum(p * c for p, c in zip(row, _COS[u])) for u in range(_LOW)] for row in rows]
    values = [
        sum(r[y][u] * _COS[v][y] for y in range(_SIDE))
        for v in range(_LOW)
        for u in range(_LOW)
    ]
    ordered = sorted(values)
    median = (ordered[31] + ordered[32]) / 2
    result = 0
    for value in values:
        result = (result << 1) | (value > median)
    return result


def hamming(a: int, b: int) -> int:
    """The number of bits in which ``a`` and ``b`` differ."""
    return bin(a ^ b).count("1")


def select_frames(candidates) -> list[int]:
    """The indices of the candidates to keep, ascending, from ``(seconds, hash_or_None)`` in time order.

    A candidate is skipped when it is blank (no hash), when it comes less than
    ``MIN_GAP_SECONDS`` after the last kept one, or when it is a near-duplicate of any kept
    one. When more than ``MAX_FRAMES`` survive, ``MAX_FRAMES`` of them are taken evenly,
    the first and the last among them.
    """
    kept: list[int] = []
    hashes: list[int] = []
    last = None
    for i, (seconds, h) in enumerate(candidates):
        if h is None:
            continue
        if last is not None and seconds - last < MIN_GAP_SECONDS:
            continue
        if any(hamming(h, other) <= DUPLICATE_BITS for other in hashes):
            continue
        kept.append(i)
        hashes.append(h)
        last = seconds
    m = len(kept)
    if m > MAX_FRAMES:
        kept = [kept[round(i * (m - 1) / (MAX_FRAMES - 1))] for i in range(MAX_FRAMES)]
    return kept
