"""The ffmpeg binary: find it, read a media file's duration and streams, extract 16 kHz mono audio."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .transcript import AcquireError

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
# One stream of input 0: "Stream #0:3[0x4](fre): Subtitle: hdmv_pgs_subtitle (pgssub), ..."
_STREAM_RE = re.compile(r"^\s*Stream #0:(\d+)(?:\[0x[0-9A-Fa-f]+\])?(?:\(([^)]*)\))?: (\w+): ([^\s,]+)")


@dataclass(frozen=True)
class Stream:
    """One stream of a media file, as ``ffmpeg -i`` lists it."""

    index: int
    kind: str  # video, audio, subtitle, data or attachment
    codec: str
    language: str | None  # the tag in brackets; None when missing or "und"
    attached_pic: bool  # a cover picture, not the recording's picture


def ffmpeg_exe() -> str:
    """ffmpeg on PATH, otherwise the binary bundled with imageio-ffmpeg.

    Raises ``AcquireError`` when neither exists (imageio-ffmpeg missing, or its binary gone).
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        # Raises RuntimeError when the bundled binary is missing for this platform.
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError) as e:
        raise AcquireError("ffmpeg is not available: install ffmpeg, or reinstall imageio-ffmpeg") from e


def stderr_tail(raw: bytes, lines: int = 10) -> str:
    """The last ``lines`` lines of ffmpeg's stderr, decoded as UTF-8 with replacement."""
    text = raw.decode("utf-8", errors="replace").strip()
    return "\n".join(text.splitlines()[-lines:])


def media_duration(path: Path) -> float | None:
    """Seconds from ffmpeg's ``Duration:`` line, or None when it has none (e.g. ``N/A``)."""
    # "ffmpeg -i" with no output file exits non-zero by design, so no check=True here.
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(path)],
        capture_output=True,
    )
    m = _DURATION_RE.search(proc.stderr.decode("utf-8", errors="replace"))
    if m is None:
        return None
    h, mins, secs = m.groups()
    return int(h) * 3600 + int(mins) * 60 + float(secs)


def parse_streams(text: str) -> list[Stream]:
    """The streams of input 0 in ``ffmpeg -i`` output; lines from the first ``Output #`` on are not read."""
    streams: list[Stream] = []
    for line in text.splitlines():
        if line.startswith("Output #"):
            break
        m = _STREAM_RE.match(line)
        if m is None:
            continue
        index, language, kind, codec = m.groups()
        streams.append(Stream(
            int(index), kind.lower(), codec, None if language in (None, "und") else language,
            "(attached pic)" in line,
        ))
    return streams


def media_streams(path: Path) -> list[Stream]:
    """The streams of ``path``; a file ffmpeg cannot read gives ``[]``."""
    # As in media_duration, "ffmpeg -i" with no output file exits non-zero by design.
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(path)],
        capture_output=True,
    )
    return parse_streams(proc.stderr.decode("utf-8", errors="replace"))


def extract_audio(src: Path, dst_wav: Path) -> None:
    """Write ``src``'s audio to ``dst_wav`` as 16 kHz mono 16-bit PCM."""
    proc = subprocess.run(
        [ffmpeg_exe(), "-nostdin", "-y", "-i", str(src),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst_wav)],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AcquireError(f"ffmpeg could not extract audio from {src}:\n{stderr_tail(proc.stderr)}")
