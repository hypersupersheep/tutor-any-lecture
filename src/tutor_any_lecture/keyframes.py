"""Key frames of a local video with no slides, as the unit's slide pages.

The video is sampled every ``SAMPLE_SECONDS`` as small gray frames; each is hashed
(``frame_hash``), and ``select_frames`` keeps those that are neither blank nor
near-duplicates and are far enough apart. The kept frames are saved full size to
``sources/keyframes/frame-NNN.jpg`` and become the pages of ``sources/slides/pages.json``,
each with its time, so the note cites them as ``(slide N)``.
"""

from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

from .ffmpeg import media_streams, sample_gray_frames, save_frame
from .slides import Page, write_pages
from .transcript import AcquireError
from .unit import UnitPaths

# A frame whose 32x32 gray pixels span less than this is blank (a black or white screen).
BLANK_RANGE = 16
# Two hashes this many bits apart or fewer show the same picture.
DUPLICATE_BITS = 6
# Kept frames are at least this many seconds apart.
MIN_GAP_SECONDS = 8.0
# At most this many key frames per video.
MAX_FRAMES = 120
# One candidate frame every this many seconds, read at this many pixels a side.
SAMPLE_SECONDS = 2.0
_SAMPLE_SIZE = 64

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


def _put_right(folder: Path, partial: Path, old: Path) -> None:
    """Undo what a killed run left: its partial folder goes; its old folder comes back, or goes."""
    shutil.rmtree(partial, ignore_errors=True)
    if old.exists():
        if folder.exists():
            shutil.rmtree(old, ignore_errors=True)
        else:
            old.rename(folder)


def extract_keyframes(video: Path, unit: Path, force: bool = False) -> tuple[list[Page], int]:
    """Save the key frames of ``video`` into the unit and write them as its slide pages.

    Returns the pages and the number of candidate frames read. Page n shows
    ``sources/keyframes/frame-<n:03d>.jpg`` (its ``image`` relative to ``sources/slides/``)
    and carries the second it was taken at; its text stays empty. An existing pages.json
    stops the run (``FileExistsError``) unless ``force``, before the video is read. A
    missing video, one with no video stream, or one with no frame to keep raises before
    the unit changes. The frames are saved to ``sources/keyframes.partial/`` and swapped in
    with pages.json at the end; any exception up to then, ``KeyboardInterrupt`` and
    ``SystemExit`` included, leaves the old key frames and pages.json as they were.
    source.json is neither read nor written.
    """
    from PIL import Image

    video = Path(video)
    paths = UnitPaths(unit)
    if paths.pages.exists() and not force:
        raise FileExistsError(f"{paths.pages} already exists; rerun with --force to replace it")
    if not video.is_file():
        raise FileNotFoundError(f"{video} does not exist or is not a file")
    stream = next((s for s in media_streams(video) if s.kind == "video" and not s.attached_pic), None)
    if stream is None:
        raise AcquireError(f"{video.name} has no video stream to take key frames from")
    frames = sample_gray_frames(video, stream.index, SAMPLE_SECONDS, _SAMPLE_SIZE)
    if not frames:
        raise AcquireError(f"no frames could be read from {video.name}")
    candidates = []
    for k, frame in enumerate(frames):
        with Image.frombytes("L", (_SAMPLE_SIZE, _SAMPLE_SIZE), frame) as image:
            candidates.append((k * SAMPLE_SECONDS, frame_hash(image)))
    kept = select_frames(candidates)
    if not kept:
        raise AcquireError(f"every frame of {video.name} is blank: no key frames to keep")

    folder = paths.keyframes
    partial = folder.with_name("keyframes.partial")
    old = folder.with_name("keyframes.old")
    _put_right(folder, partial, old)
    had_folder = folder.exists()
    temporary = paths.pages.with_name("pages.json.partial")
    pages: list[Page] = []
    try:
        partial.mkdir(parents=True)
        for n, i in enumerate(kept, start=1):
            seconds = candidates[i][0]
            name = f"frame-{n:03d}.jpg"
            save_frame(video, stream.index, seconds, partial / name)
            pages.append(Page(n, None, "", f"../keyframes/{name}", time=seconds))
        if had_folder:
            folder.rename(old)
        partial.rename(folder)
        write_pages(temporary, pages)
        os.replace(temporary, paths.pages)
    except BaseException:
        # An error, Ctrl+C or a stop signal: put the unit back as it was, then raise again.
        shutil.rmtree(partial, ignore_errors=True)
        if old.exists():  # the old frames were moved aside; whatever is in their place is new
            shutil.rmtree(folder, ignore_errors=True)
            old.rename(folder)
        elif not had_folder:
            shutil.rmtree(folder, ignore_errors=True)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    shutil.rmtree(old, ignore_errors=True)  # a leftover is removed by the next run
    return pages, len(candidates)
