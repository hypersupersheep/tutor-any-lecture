"""The transcript contract: segments, transcript.json, the input parsers and the health check."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .plan import read_json
from .textstats import join_lines


class EmptyTranscript(ValueError):
    """An input file held no timed segment."""


class AcquireError(RuntimeError):
    """An input could not be read, or an external tool or ASR backend failed."""


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[dict] | None = None


@dataclass
class Transcript:
    segments: list[Segment]
    language: str | None

    def to_json(self) -> str:
        """The exact text of transcript.json."""
        segments = []
        for s in self.segments:
            d = {"start": s.start, "end": s.end, "text": s.text}
            if s.words is not None:
                d["words"] = s.words
            segments.append(d)
        return json.dumps({"language": self.language, "segments": segments}, ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_json(cls, path: Path) -> Transcript:
        """Read transcript.json. A missing key or a wrong type raises ValueError("transcript.json: …")."""
        data = read_json(path, "transcript.json")
        if not isinstance(data, dict) or "segments" not in data or "language" not in data:
            raise ValueError('transcript.json: the top level must be an object with "language" and "segments"')
        if not isinstance(data["language"], (str, type(None))):
            raise ValueError(f"transcript.json: language must be text or null, got {data['language']!r}")
        if not isinstance(data["segments"], list):
            raise ValueError("transcript.json: segments must be a list")
        segments = [_segment(d, n) for n, d in enumerate(data["segments"])]
        return cls(segments, data["language"])

    def text(self) -> str:
        return " ".join(s.text for s in self.segments)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _segment(d, n: int) -> Segment:
    where = f"transcript.json: segment {n}"
    if not isinstance(d, dict):
        raise ValueError(f"{where} is not an object")
    missing = [k for k in ("start", "end", "text") if k not in d]
    if missing:
        raise ValueError(f"{where} is missing {', '.join(missing)}")
    if not (_is_number(d["start"]) and _is_number(d["end"])):
        raise ValueError(f"{where}: start and end must be numbers")
    if not isinstance(d["text"], str):
        raise ValueError(f"{where}: text must be text, got {d['text']!r}")
    words = d.get("words")
    if words is not None and not isinstance(words, list):
        raise ValueError(f"{where}: words must be a list or null")
    return Segment(d["start"], d["end"], d["text"], words)


def primary_subtag(code: str | None) -> str | None:
    """"en-orig" -> "en", "zh-Hans" -> "zh"; None, "" and "auto" -> None."""
    if not code:
        return None
    tag = code.strip().lower().replace("_", "-").split("-")[0]
    if not tag or tag == "auto":
        return None
    return tag


# --- text input -------------------------------------------------------------


def _normalise(text: str) -> str:
    """Strip one leading BOM and turn CRLF, then lone CR, into LF."""
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _collapse(text: str) -> str:
    return " ".join(text.split())


_TS = r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})"
_TIMING = re.compile(rf"\s*{_TS}\s*-->\s*{_TS}(?:\s+.*)?")
# Only real WebVTT tags; only v and lang take an annotation after a space, so "<c and y>" is text.
_VTT_TAG = re.compile(r"</?(?:c|i|b|u|ruby|rt)(?:\.[^\s>]+)?>|</?(?:v|lang)(?:\.[^\s>]+)?(?:[ \t][^>]*)?>")
_VTT_TIME_TAG = re.compile(r"<(\d+:)?\d{2}:\d{2}\.\d{3}>")


def _ms_to_seconds(h: str | None, m: str, s: str, ms: str) -> float:
    # Integer milliseconds divided once, so "00:00:03.010" is exactly 3.01.
    return (int(h or 0) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms)) / 1000


def _blocks(text: str) -> list[list[str]]:
    """Blocks of lines; only a zero-length line ends one (a space-only line is payload)."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in _normalise(text).split("\n"):
        if line == "":
            if current:
                blocks.append(current)
            current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _read_cues(text: str, clean=None) -> list[Segment]:
    """The cue reader shared by SRT and VTT. ``clean`` removes format-specific tags.

    Each payload line is cleaned first, so a tag at a line end cannot hide a character from
    ``join_lines``; the lines are then joined with ``join_lines`` (no space at a break between
    two characters of a script written without spaces) and whitespace is collapsed.
    """
    segments: list[Segment] = []
    for block in _blocks(text):
        idx = next((i for i, line in enumerate(block) if "-->" in line), None)
        if idx is None:  # WEBVTT header, NOTE, STYLE, REGION
            continue
        m = _TIMING.fullmatch(block[idx])
        if m is None:
            continue
        start = _ms_to_seconds(*m.group(1, 2, 3, 4))
        end = _ms_to_seconds(*m.group(5, 6, 7, 8))
        lines = block[idx + 1:]
        if clean is not None:
            lines = [clean(line) for line in lines]
        payload = _collapse(join_lines(lines))
        if payload:
            segments.append(Segment(start, end, payload))
    return segments


def _clean_vtt(payload: str) -> str:
    # Entities are decoded after the tags are removed, so "&lt;i&gt;" stays as text.
    return html.unescape(_VTT_TIME_TAG.sub("", _VTT_TAG.sub("", payload)))


def parse_srt(text: str) -> list[Segment]:
    return _read_cues(text)


def parse_vtt(text: str) -> list[Segment]:
    return _read_cues(text, _clean_vtt)


def clock_seconds(text: str) -> float:
    """A clock time to seconds: ``m:ss``, ``mm:ss`` or ``h:mm:ss`` (the first part may be longer).

    The one parser of written clock times, for transcripts, Panopto stamps and citations.
    Any other number of parts raises ``ValueError``, and so does a part that is not a number.
    """
    parts = [int(p) for p in text.split(":")]
    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    if len(parts) == 3:
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    raise ValueError(f"not a clock time (m:ss or h:mm:ss): {text!r}")


_STAMP = re.compile(r"^\s*\[(\d+:\d{2}(?::\d{2})?)\]\s*(.*)$")


def parse_stamped_txt(text: str, duration: float | None) -> list[Segment]:
    """Lines like ``[m:ss] text`` or ``[h:mm:ss] text``; unstamped lines continue the previous one,
    joined to it with ``join_lines``."""
    stamped: list[list] = []  # [start, text]
    for line in _normalise(text).split("\n"):
        m = _STAMP.match(line)
        if m:
            stamp, rest = m.groups()
            stamped.append([clock_seconds(stamp), rest])
        elif line.strip() and stamped:
            stamped[-1][1] = join_lines([stamped[-1][1], line])
    return _close_stamped(stamped, duration)


def _close_stamped(stamped: list[list], duration: float | None) -> list[Segment]:
    """``[start, text]`` pairs to segments: empty texts are dropped, each segment ends where the
    next starts, and the last ends 5 s after its start, or at ``duration`` when that is sooner.

    Shared by ``parse_stamped_txt`` and the header layout of ``parse_meeting_export``.
    """
    kept = [(start, _collapse(t)) for start, t in stamped if _collapse(t)]
    segments: list[Segment] = []
    for i, (start, t) in enumerate(kept):
        if i + 1 < len(kept):
            end = kept[i + 1][0]
        else:
            end = max(start, min(start + 5, duration or start + 5))
        segments.append(Segment(start, end, t))
    return segments


# A meeting export's time: [h:]m:s, with an optional fraction whose first three digits are ms.
_RANGE_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,7}))?"
_RANGE = re.compile(rf"{_RANGE_TIME}\s*-->\s*{_RANGE_TIME}")
_CUE_NUMBER = re.compile(r"[0-9]+")
# A header: a speaker (optional) and a start time [h:]m:ss, alone on its line.
_HEADER = re.compile(r"(?:(.+?)\s+)?((?:\d+:)?\d+:\d{2})")
_SPEAKER_NUMBER = re.compile(r"\d{1,3}")
_TRANSCRIPTION_NOTICES = ("started transcription", "stopped transcription")


def _range_seconds(h: str | None, m: str, s: str, fraction: str | None) -> float:
    # Only the first three digits of the fraction count, padded on the right: ".5" is 500 ms.
    return _ms_to_seconds(h, m, s, (fraction or "")[:3].ljust(3, "0"))


def _is_speaker(name: str) -> bool:
    """1 to 60 characters and 1 to 6 words, not starting lowercase, a digit only in a last word of 1 to 3 digits.

    One pair of surrounding ``[]`` or ``()`` is removed first. The guards keep sentences
    ("the meeting ends at 5:30"), dates ("03/11/2026 14:00") and numbered lines
    ("Week 12 starts 9:00") out of the headers, and let "Speaker 2" in.
    """
    if len(name) >= 2 and (name[0], name[-1]) in (("[", "]"), ("(", ")")):
        name = name[1:-1].strip()
    words = name.split()
    if not 1 <= len(name) <= 60 or not 1 <= len(words) <= 6 or name[0].islower():
        return False
    if any(c.isdigit() for word in words[:-1] for c in word):
        return False
    last = words[-1]
    return not any(c.isdigit() for c in last) or _SPEAKER_NUMBER.fullmatch(last) is not None


def _header_seconds(line: str) -> float | None:
    """The start time of a header line (``Alice Smith   0:03``, ``[Alice Smith] 00:00:03``, ``0:03``), else None."""
    m = _HEADER.fullmatch(line)
    if m is None or (m.group(1) is not None and not _is_speaker(m.group(1))):
        return None
    return clock_seconds(m.group(2))


def parse_meeting_export(lines: list[str], duration: float | None) -> list[Segment]:
    """The lines of a meeting transcript export (a Teams DOCX, a Zoom TXT), read in one layout.

    Range layout, when any line is ``<t> --> <t>``: the lines up to the next range are its
    text, the first of them the speaker when there are two or more; a line of digits alone
    right before a range is a cue number and is dropped. Header layout, else,
    when any line is a speaker and a start time, or a time alone: the lines up to the next
    header are its text, and a segment ends where the next starts. Stamped layout, else:
    ``parse_stamped_txt``. The text lines of one segment are joined with ``join_lines``.
    Speaker names never reach the text; lines before the first time,
    and the "started transcription" and "stopped transcription" notices, are dropped.
    """
    lines = [line.strip() for line in lines]
    lines = [line for line in lines if line and not line.casefold().endswith(_TRANSCRIPTION_NOTICES)]

    ranges = [_RANGE.fullmatch(line) for line in lines]
    if any(ranges):
        # A line of digits alone right before a range is a cue number, not text.
        keep = [
            not (_CUE_NUMBER.fullmatch(line) and i + 1 < len(lines) and ranges[i + 1] is not None)
            for i, line in enumerate(lines)
        ]
        lines = [line for line, k in zip(lines, keep) if k]
        ranges = [m for m, k in zip(ranges, keep) if k]
        segments: list[Segment] = []
        starts = [i for i, m in enumerate(ranges) if m is not None]
        for k, i in enumerate(starts):
            block = lines[i + 1:starts[k + 1] if k + 1 < len(starts) else len(lines)]
            if len(block) >= 2:
                block = block[1:]  # the speaker
            text = _collapse(join_lines(block))
            if text:
                m = ranges[i]
                start, end = _range_seconds(*m.group(1, 2, 3, 4)), _range_seconds(*m.group(5, 6, 7, 8))
                segments.append(Segment(start, end, text))
        return segments

    headers = [_header_seconds(line) for line in lines]
    if any(start is not None for start in headers):
        stamped: list[list] = []  # [start, text]
        for line, start in zip(lines, headers):
            if start is not None:
                stamped.append([start, ""])
            elif stamped:
                stamped[-1][1] = join_lines([stamped[-1][1], line])
        return _close_stamped(stamped, duration)

    return parse_stamped_txt("\n".join(lines), duration)


# The SRT timing parse_srt reads, with two-digit hours and comma milliseconds on both sides.
_SRT_TS = r"\d{2}:\d{2}:\d{2},\d{3}"
_SRT_TIMING = re.compile(rf"\s*{_SRT_TS}\s*-->\s*{_SRT_TS}(?:\s+.*)?")
_WEBVTT_SIGNATURE = re.compile(r"WEBVTT(?:[ \t].*)?")


def parse_txt(text: str, duration: float | None) -> list[Segment]:
    """A ``.txt`` transcript, as ``acquire import`` and the router read it.

    Lines stamped ``[m:ss]`` read with ``parse_stamped_txt``, as a .txt always has. Failing
    that, a caption file saved as .txt reads as one: ``parse_vtt`` when its first line (after a
    BOM and blank lines) is ``WEBVTT``, ``parse_srt`` when its first timing line is SRT timing.
    Anything else is read in the layouts of a meeting export (``parse_meeting_export``).
    """
    stamped = parse_stamped_txt(text, duration)
    if stamped:
        return stamped
    lines = _normalise(text).splitlines()
    first = next((line.strip() for line in lines if line.strip()), "")
    if _WEBVTT_SIGNATURE.fullmatch(first):
        return parse_vtt(text)
    timing = next((line for line in lines if "-->" in line), None)
    if timing is not None and _SRT_TIMING.fullmatch(timing):
        return parse_srt(text)
    return parse_meeting_export(lines, duration)


def parse_whisper_json(obj) -> list[Segment]:
    """Accepts ``{"segments": [...]}`` or a bare list of segment objects.

    Malformed input raises ``ValueError`` (never ``KeyError`` or ``TypeError``), so the
    CLI reports it as one error line. Items are counted from 1 in the messages.
    """
    items = obj.get("segments", []) if isinstance(obj, dict) else obj
    if not isinstance(items, list):
        raise ValueError("expected a list of segments")
    segments: list[Segment] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"segment {i} is not an object")
        text = item.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            continue
        if item.get("start") is None or item.get("end") is None:
            raise ValueError(f"segment {i} has no start or end time")
        try:
            start, end = float(item["start"]), float(item["end"])
        except (TypeError, ValueError):
            raise ValueError(f"segment {i} has a start or end time that is not a number") from None
        segments.append(Segment(start, end, text, item.get("words")))
    return segments


# --- health -----------------------------------------------------------------


@dataclass
class Health:
    coverage: float
    repetition: float
    spots_ok: bool
    overrun: bool
    loop: bool
    ok: bool
    duration_known: bool
    # What coverage, spot checks and overrun were measured against: "lecture" (a length from
    # outside the transcript: the recording, the video page, --duration), "transcript" (the
    # transcript's own last stamp, so coverage and overrun hold by construction) or "none" (no length).
    length_basis: str


def health(segments: list[Segment], duration: float | None, from_transcript: bool = False) -> Health:
    """The health of ``segments`` against the lecture length ``duration``.

    ``from_transcript`` says that ``duration`` was read from the transcript itself.
    """
    has_length = duration is not None and duration > 0
    length_basis = ("transcript" if from_transcript else "lecture") if has_length else "none"
    if not segments:
        return Health(
            coverage=0.0, repetition=0.0, spots_ok=False, overrun=False, loop=False, ok=False,
            duration_known=duration is not None, length_basis=length_basis,
        )

    norm = [" ".join(s.text.casefold().split()) for s in segments]
    repeats = 0
    run = longest = 1
    for prev, cur in zip(norm, norm[1:]):
        if cur == prev:
            repeats += 1
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    repetition = repeats / len(segments)
    loop = longest >= 5

    duration_known = has_length
    if duration_known:
        coverage = (max(s.end for s in segments) - min(s.start for s in segments)) / duration
        spots_ok = all(
            any(abs(s.start - frac * duration) <= 60 for s in segments) for frac in (0.1, 0.5, 0.9)
        )
        overrun = any(s.end > duration + 2 for s in segments)
    else:
        coverage, spots_ok, overrun = 1.0, True, False

    ok = coverage >= 0.9 and repetition <= 0.5 and spots_ok and not overrun and not loop
    return Health(coverage, repetition, spots_ok, overrun, loop, ok, duration_known, length_basis)
