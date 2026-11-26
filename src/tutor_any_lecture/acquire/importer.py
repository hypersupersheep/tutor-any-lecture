"""Import a transcript file the user already has.

It reads SRT, VTT, Whisper JSON, text stamped ``[m:ss]``, a Zoom transcript saved as TXT
and a Teams transcript saved as DOCX; any other file ends in one error that lists these.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from .. import __version__, ffmpeg
from ..office import docx_lines
from ..source import SourceInfo, sha256_file, slide_digests
from ..transcript import (
    AcquireError,
    EmptyTranscript,
    Health,
    Segment,
    Transcript,
    health,
    parse_meeting_export,
    parse_srt,
    parse_txt,
    parse_vtt,
    parse_whisper_json,
)
from ..unit import UnitPaths, refuse_overwrite

IMPORT_ACCEPTS = (
    "acquire import reads .srt, .vtt, .json (Whisper segments), .txt (lines stamped [m:ss], or a Zoom transcript) "
    "and .docx (a Teams transcript)"
)
_SUFFIXES = (".srt", ".vtt", ".json", ".txt", ".docx")


def _media_seconds(media: Path) -> float:
    """The duration of the lecture recording ``media``, read with ffmpeg."""
    if not media.is_file():
        raise FileNotFoundError(f"{media} does not exist or is not a file")
    seconds = ffmpeg.media_duration(media)
    if seconds is None or seconds <= 0:
        raise AcquireError(f"could not read a duration from {media.name}; pass --duration instead")
    return seconds


def _parse_text(file: Path, suffix: str, duration: float | None) -> list[Segment]:
    """The segments of a text transcript (.srt, .vtt, .json or .txt)."""
    try:
        text = file.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{file.name} is not UTF-8 text: save it as UTF-8 ({IMPORT_ACCEPTS})") from None
    if suffix == ".srt":
        return parse_srt(text)
    if suffix == ".vtt":
        return parse_vtt(text)
    if suffix == ".json":
        try:
            obj = json.loads(text)
        except (ValueError, RecursionError):  # RecursionError: nesting deeper than the parser goes
            raise ValueError(f"{file.name} is not valid JSON: {IMPORT_ACCEPTS}") from None
        if isinstance(obj, dict) and "segments" not in obj:
            raise ValueError(f"{file.name} holds no Whisper segments: {IMPORT_ACCEPTS}")
        return parse_whisper_json(obj)
    # A .txt stamped [m:ss] reads as it always has; one without a stamp reads as the SRT or
    # VTT file it holds, else in the layouts of a meeting export (a Zoom transcript).
    return parse_txt(text, duration)


def import_transcript(
    file: Path, unit: Path, duration: float | None, force: bool, media: Path | None = None
) -> Health:
    """Import ``file`` into the unit. ``media``, the lecture's recording, gives the duration."""
    file = Path(file)
    paths = UnitPaths(unit)
    # The guard comes first, before the input is read; it keys on transcript.json only.
    refuse_overwrite(unit, force)
    suffix = file.suffix.lower()
    # Checked before the media file is probed, and before the input is read.
    if suffix not in _SUFFIXES:
        raise AcquireError(f"{file.name} is not a transcript file: {IMPORT_ACCEPTS}")
    if media is not None:
        if duration is not None:
            raise ValueError("give the duration or a media file, not both")
        duration = _media_seconds(Path(media))

    if suffix == ".docx":
        # A Word file is a zip of XML parts; it is never decoded as text.
        segments = parse_meeting_export(docx_lines(file), duration)
    else:
        segments = _parse_text(file, suffix, duration)
    if not segments:
        raise EmptyTranscript("no timed segments found")

    h = health(segments, duration)
    paths.ensure()
    # An import never claims a language, also when a Whisper JSON file names one.
    paths.transcript.write_text(Transcript(segments, None).to_json(), encoding="utf-8", newline="\n")
    SourceInfo(
        kind="transcript",
        title=file.stem,
        url=None,
        platform=None,
        duration=duration,
        lecture_language=None,
        acquisition="import",
        health=dataclasses.asdict(h),
        tool_versions={"tutor-any-lecture": __version__},
        inputs_sha256={**slide_digests(paths.source), file.name: sha256_file(file)},
    ).write(paths.source)
    return h
