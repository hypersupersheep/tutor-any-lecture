"""Citations in a note: (slide 15), (13:42–14:05), (~13:40), ([13:42](URL)) and mixes.

`parse` finds them, `resolve` checks them against the slide count and the duration, and
`link_times` turns plain times into links to the video (`link_unit`: ``cite link``) in the
time form of the video's platform (`TIME_LINK_FORMS`). Standard library only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple
from urllib.parse import SplitResult, parse_qsl, urlsplit

from .textstats import INLINE_CODE_RE, fenced_lines

TIME = r"\d{1,2}:\d{2}(?::\d{2})?"
TIME_RE = re.compile(TIME)
# A time token: a bare timestamp, or a Markdown link whose text is the timestamp.
# The URL is ignored; it contains no spaces or parentheses.


def _token(n: str) -> str:
    return rf"(?:\[(?P<{n}l>{TIME})\]\([^()\s]*\)|(?P<{n}b>{TIME}))"


DASH = r"\s*[-–]\s*"
# Only these parts: "slide N", "slides N–M", "T", "T–T", "~T", "~T–T". So "slide 14-16",
# "slides 4" and "~ 13:40" leave text after the part, and _parse_group drops the group.
PART_RE = re.compile(
    rf"(?P<slide>slides\s+(?P<r1>\d+){DASH}(?P<r2>\d+)|slide\s+(?P<s1>\d+))"
    rf"|(?P<time>(?P<tilde>~)?{_token('a')}(?:{DASH}{_token('z')})?)",
    re.IGNORECASE,
)
SEP_RE = re.compile(r"\s*[,，]\s*")
LINK = r"\[[^\]\n]*\]\([^()\s]*\)"
# A parenthesised group on one line; a Markdown link inside it keeps its own parentheses.
GROUP_RE = re.compile(rf"\((?P<a>(?:{LINK}|[^()（）\n])*)\)|（(?P<b>(?:{LINK}|[^()（）\n])*)）")


@dataclass
class Citation:
    kind: str  # "slide" or "time"
    start: float | str
    end: float | str | None
    estimated: bool
    raw: str
    line: int


def _seconds(t: str) -> float:
    parts = [int(p) for p in t.split(":")]
    if len(parts) == 3:
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    return float(parts[0] * 60 + parts[1])


def _parts(content: str) -> list[re.Match]:
    """The PART_RE matches of one group's content, or [] when it is not a citation list."""
    out: list[re.Match] = []
    pos = 0  # no whitespace inside the parentheses before the first part or after the last
    while True:
        m = PART_RE.match(content, pos)
        if not m:
            return []
        out.append(m)
        if m.end() == len(content):
            return out
        sep = SEP_RE.match(content, m.end())
        if not sep:
            return []
        pos = sep.end()


def _parse_group(content: str, raw: str, line: int) -> list[Citation]:
    """All parts of one group, or [] when its content is not a citation list."""
    out: list[Citation] = []
    for m in _parts(content):
        if m.group("s1"):
            out.append(Citation("slide", m.group("s1"), None, False, raw, line))
        elif m.group("slide"):
            out.append(Citation("slide", m.group("r1"), m.group("r2"), False, raw, line))
        else:
            start = m.group("al") or m.group("ab")
            end = m.group("zl") or m.group("zb")
            out.append(
                Citation(
                    "time",
                    _seconds(start),
                    _seconds(end) if end else None,
                    m.group("tilde") is not None,
                    raw,
                    line,
                )
            )
    return out


def parse(md: str) -> list[Citation]:
    """Every citation in `md`, in document order. Code is not skipped here."""
    out: list[Citation] = []
    for g in GROUP_RE.finditer(md):
        content = g.group("a") if g.group("a") is not None else g.group("b")
        line = md.count("\n", 0, g.start()) + 1
        out.extend(_parse_group(content, g.group(0), line))
    return out


def format_seconds(d: float) -> str:
    """Seconds as m:ss, or h:mm:ss from one hour on."""
    total = int(d)
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _as_written(raw: str, seconds: float) -> str:
    for tok in TIME_RE.findall(raw):
        if _seconds(tok) == seconds:
            return tok
    return format_seconds(seconds)


def resolve(cits: list[Citation], max_slide: int | None, duration: float | None) -> list[str]:
    """Problems with the citations, in citation order (start before end)."""
    problems: list[str] = []
    for c in cits:
        if c.kind == "slide":
            if max_slide is None:
                continue
            n = max(int(c.start), int(c.end)) if c.end is not None else int(c.start)
            if n > max_slide:
                problems.append(f"slide {n} > {max_slide}")
        elif duration is not None:
            for t in (c.start, c.end):
                if t is not None and t > duration + 2:
                    problems.append(f"{_as_written(c.raw, t)} > duration {format_seconds(duration)}")
    return problems


# ---------------------------------------------------------------- time links

# Inline code is masked with this private-use character, one per character, so positions
# in a masked line are positions in the line itself.
_CODE_MASK = "\ue002"
# Characters that would end a Markdown link target, and their percent-encodings.
_URL_ESCAPES = {" ": "%20", "(": "%28", ")": "%29"}


class TimeLinkForm(NamedTuple):
    """How one platform's address points at a second of the video."""

    name: str
    label: str
    written: str  # the form as the documents print it
    param: str  # the parameter that holds the time
    suffix: str  # written after the seconds
    in_fragment: bool  # the parameter is in the #fragment, not in the query


TIME_LINK_FORMS = (
    TimeLinkForm("youtube", "YouTube", "t=<seconds>s", "t", "s", False),
    TimeLinkForm("bilibili", "Bilibili", "t=<seconds>", "t", "", False),
    TimeLinkForm("vimeo", "Vimeo", "#t=<seconds>s", "t", "s", True),
    TimeLinkForm("panopto", "Panopto", "start=<seconds>", "start", "", False),
)


def _query_value(query: str, name: str) -> str | None:
    """The first value of parameter ``name`` in a query string, or None."""
    return next((v for k, v in parse_qsl(query, keep_blank_values=True) if k == name), None)


def _is_youtube(parts: SplitResult) -> bool:
    if parts.hostname == "youtu.be":
        return len(parts.path) > 1
    return parts.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com") and parts.path == "/watch" and bool(
        _query_value(parts.query, "v")
    )


def _is_bilibili(parts: SplitResult) -> bool:
    return parts.hostname in ("bilibili.com", "www.bilibili.com", "m.bilibili.com") and parts.path.startswith("/video/")


def _is_vimeo(parts: SplitResult) -> bool:
    first = parts.path.split("/")[1] if parts.path.startswith("/") else ""
    return parts.hostname in ("vimeo.com", "www.vimeo.com") and re.fullmatch(r"[0-9]+", first) is not None


def _is_panopto(parts: SplitResult) -> bool:
    return parts.path.lower().endswith("/pages/viewer.aspx") and bool(_query_value(parts.query, "id"))


# Which addresses each row's time form applies to, by the row's name.
_ADDRESS_TESTS = {"youtube": _is_youtube, "bilibili": _is_bilibili, "vimeo": _is_vimeo, "panopto": _is_panopto}


def _encoded(url: str) -> str:
    for char, escape in _URL_ESCAPES.items():
        url = url.replace(char, escape)
    return url


def _split(url: str) -> SplitResult | None:
    """The parts of the (encoded) address, or None when it cannot be split."""
    try:
        return urlsplit(url)
    except ValueError:  # an unclosed "[" in the host
        return None


def _form_of(url: str) -> TimeLinkForm | None:
    """The row whose address test the (encoded) address passes, or None."""
    parts = _split(url)
    if parts is None:
        return None
    return next((row for row in TIME_LINK_FORMS if _ADDRESS_TESTS[row.name](parts)), None)


def time_link_platform(url: str) -> str | None:
    """The ``name`` of the row of ``TIME_LINK_FORMS`` that ``url`` belongs to, or None."""
    row = _form_of(_encoded(url))
    return row.name if row is not None else None


def no_time_links(url: str) -> str:
    """``no time links for <host>``: the lower-case host, or the address itself when it has none."""
    parts = _split(_encoded(url))
    host = parts.hostname if parts is not None else None
    return f"no time links for {host or url}"


def time_url(url: str, seconds: float) -> str:
    """``url`` pointing at ``seconds`` (whole seconds), in the time form of its platform.

    In the query the row's parameter is dropped wherever it stands, with the fragment,
    and ``param=<seconds><suffix>`` is appended (``?`` when the query is empty, else
    ``&``); in the fragment the query is kept and the fragment becomes the time. Spaces
    and parentheses are percent-encoded so the link survives in Markdown. An address in
    no row raises ValueError.
    """
    encoded = _encoded(url)
    row = _form_of(encoded)
    if row is None:
        raise ValueError(no_time_links(url))
    time = f"{row.param}={int(seconds)}{row.suffix}"
    rest = encoded.partition("#")[0]
    if row.in_fragment:
        return f"{rest}#{time}"
    base, _, query = rest.partition("?")
    params = [p for p in query.split("&") if p and p.split("=", 1)[0] != row.param]
    return f"{base}?{'&'.join([*params, time])}"


def _mask_code(line: str) -> str:
    return INLINE_CODE_RE.sub(lambda m: _CODE_MASK * len(m.group(0)), line)


def link_times(md: str, url: str) -> tuple[str, int]:
    """``md`` with every plain time citation linked to ``url`` at that second, and how many.

    In each citation group (as ``parse`` reads them) the start time of each time part
    becomes ``[m:ss](<url at that time>)``: the end of a range stays plain, a ``~`` stays
    before the link, slides are left alone. Times already linked are kept, so running it
    again changes nothing. Code (fenced blocks and inline spans) is never touched.
    """
    lines = md.split("\n")
    count = 0
    for i, (line, fenced) in enumerate(zip(lines, fenced_lines(lines))):
        if fenced:
            continue
        spans: list[tuple[int, int]] = []  # (start, end) of each plain start time in the line
        for g in GROUP_RE.finditer(_mask_code(line)):
            name = "a" if g.group("a") is not None else "b"
            offset = g.start(name)
            for m in _parts(g.group(name)):
                if m.group("ab"):
                    spans.append((offset + m.start("ab"), offset + m.end("ab")))
        for start, end in reversed(spans):
            token = line[start:end]
            line = f"{line[:start]}[{token}]({time_url(url, _seconds(token))}){line[end:]}"
        lines[i] = line
        count += len(spans)
    return "\n".join(lines), count


def link_unit(unit: Path) -> dict:
    """``cite link``: link the time citations of the unit's explanation.md to its video.

    A unit whose source.json has kind "url" or "platform" and a ``url`` in a row of
    ``TIME_LINK_FORMS`` is linked: ``{"path", "linked"}``. Any other unit is left as it
    is, and ``{"path", "linked": 0, "reason"}`` says why. A missing explanation.md
    raises FileNotFoundError.
    """
    from .plan import read_text
    from .source import SourceInfo
    from .unit import UnitPaths

    paths = UnitPaths(unit)
    if not paths.explanation.exists():
        raise FileNotFoundError(f"explanation.md: not found in {paths.root}")
    report = {"path": str(paths.explanation), "linked": 0}
    source = SourceInfo.read(paths.source) if paths.source.exists() else None
    if source is None:
        reason = "no source.json in the unit: no video to link to"
    elif source.kind not in ("url", "platform"):
        reason = "the source is not an online video"
    elif not source.url:
        reason = "source.json has no video address"
    elif time_link_platform(source.url) is None:
        reason = f"{no_time_links(source.url)}: the times stay plain"
    else:
        md = read_text(paths.explanation, "explanation.md")
        linked, count = link_times(md, source.url)
        if count:
            paths.explanation.write_text(linked, encoding="utf-8", newline="\n")
        report["linked"] = count
        return report
    report["reason"] = reason
    return report
