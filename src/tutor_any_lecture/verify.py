"""The delivery gate: nine checks over one unit folder, written to verify.json.

``run_verify(unit)`` reads only files inside the unit and the packaged
``data/banned_phrases/<language>.txt``. The checks always come in the same order and under the
same names; a check whose output is not in plan.json is a PASS entry marked skipped.
"""

from __future__ import annotations

import json
import re
import unicodedata
from bisect import bisect_right
from importlib import resources
from pathlib import Path

from .cards import load_cards, miss_rewritten, validate_cards
from .checks import NOT_APPLIED, CheckResult
from .citations import format_seconds, link_time_problems, link_times, parse, resolve, time_link_platform
from .conceptmap import load_map, validate_map
from .items import load_items, validate_items
from .notecheck import (
    CALLOUT_START_RE,
    CALLOUT_TYPES,
    INLINE_QUOTE_RE,
    THRESHOLDS,
    check_note,
    cited_quote_contexts,
    cited_quotes,
    marker_sections,
    measure_note,
    strip_marker_sections,
)
from .plan import load_plan, read_json, read_text
from .slides import load_pages, max_label
from .source import SourceInfo

# verify removes code exactly as check_note and units() do.
from .textstats import (
    ANGLE_URL_RE,
    BARE_URL_RE,
    BRACKET_MATH_RE,
    CJK_RE,
    DISPLAY_MATH_RE,
    INLINE_CODE_RE,
    INLINE_MATH_RE,
    MD_LINK_URL_RE,
    PAREN_MATH_RE,
    strip_code,
    unsegmented,
)
from .transcript import Transcript
from .unit import UnitPaths

REPORT_PASS = "Automated checks passed; not visually reviewed."
REPORT_FAIL = "Automated checks failed."
SKIPPED = "skipped: not in plan.outputs"
MISSING_TRANSCRIPT = "sources/transcript.json missing"
DURATION_UNKNOWN = "duration unknown: time citations not range-checked"
SEVERITY = {"PASS": 0, "WARN": 1, "FAIL": 2}

# "\$" is a literal currency sign: hidden behind this placeholder while math is removed.
_DOLLAR_PLACEHOLDER = "\ue000"

# "slides N–M" (en dash or hyphen-minus) is a range when N <= M; "slide N" takes one number.
# Any number of them on a line.
NOT_COVERED_SLIDE_RE = re.compile(r"slides\s+(\d+)\s*[–-]\s*(\d+)|slides?\s+(\d+)", re.IGNORECASE)

# terms
NOTE_CALLOUT_RE = re.compile(r"^\s*>\s*\[!NOTE\]", re.IGNORECASE)
CALLOUT_TAG_RE = re.compile(r"\[![A-Za-z]+\][+-]?")
LINK_TARGET_RE = re.compile(r"\]\([^)\n]*\)")
URL_RE = re.compile(r"<https?://[^>\s]*>|https?://\S+")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>\n]*>")
LATIN_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ɏḀ-ỿ]+")
# Languages that capitalise every noun: a capital marks no term there.
NOUN_CAPITAL_LANGS = ("de", "lb")
# A Markdown link inside a citation group: shown as its text.
CITATION_LINK_RE = re.compile(r"\[([^\]\n]*)\]\([^()\s]*\)")

# quote_source: editorial marks split a quote; a cited time looks this far either side.
EDITORIAL_RE = re.compile(r"…|\.\.\.|\[[^\]\n]*\]")
NOT_LETTER_OR_DIGIT_RE = re.compile(r"[\W_]+")
CJK_SPACE_RE = re.compile(rf" (?={CJK_RE.pattern})|(?<={CJK_RE.pattern}) ")
# In normalised text a word ends at a space, at a CJK character or at either end.
_CJK_CHARS = CJK_RE.pattern[1:-1]
WORD_EDGE_BEFORE = rf"(?<![^ {_CJK_CHARS}])"
WORD_EDGE_AFTER = rf"(?![^ {_CJK_CHARS}])"
QUOTE_WINDOW_S = 60
QUOTE_MIN_WORDS = 3
QUOTE_SHOWN_CHARS = 40

# quote_source: who speaks. A transcript segment may begin with a speaker label of one to
# four words of capitals (each at least two characters), an optional number, then ": ".
SPEAKER_LABEL_RE = re.compile(r"([A-Z][A-Z.'-]+(?: [A-Z][A-Z.'-]+){0,3}(?: \d+)?): ")
STUDENT_LABEL_WORDS = ("STUDENT", "STUDENTS", "AUDIENCE")
SPEAKER_CHECK_LANGS = ("en", "zh")
# (English words, matched whole and ignoring case; Chinese words, matched as substrings)
STUDENT_WORDS = (("student", "students", "audience"), ("学生", "同学", "听众"))
SPEECH_WORDS = (
    ("says", "said", "asks", "asked", "answers", "answered", "replies", "replied", "responds", "responded",
     "suggests", "suggested", "adds", "added"),
    ("说", "问", "答", "提出", "指出"),
)
LECTURER_WORDS = (("lecturer", "professor", "teacher", "instructor"), ("讲师", "老师", "教授"))

# banned_phrases: a list file is named by a language's primary subtag; a space between two
# CJK characters is dropped, and a phrase end in a letter or digit outside CJK needs a word edge.
BANNED_LANG_RE = re.compile(r"[a-z]{2,8}")
CJK_PAIR_SPACE_RE = re.compile(rf"(?<={CJK_RE.pattern}) (?={CJK_RE.pattern})")
ALNUM_CHAR_RE = re.compile(r"[^\W_]")

# numbers, read after NFKC: ASCII digits with an optional decimal part, optional spaces or
# tabs, then a unit; or 百分之 before the number (a percent); or a currency sign and the
# first digit after it. A number is compared by its key: the number as written plus the
# unit's key. English forms ignore ASCII case only (so Turkish ı or İ is never read as i)
# and end at a word boundary; the rest are as written.
NUMBER_UNITS = {
    "%": ("%", "percent"),
    "bp": ("bp", "bps", "基点"),
    "year": ("year", "years", "年", "년"),
    "month": ("month", "months", "个月", "個月", "ヶ月", "か月", "カ月", "개월"),
    "week": ("week", "weeks", "周", "週", "星期", "个星期", "個星期", "週間"),
    "day": ("day", "days", "天", "日間"),
    "hour": ("hour", "hours", "小时", "小時", "个小时", "個小時", "時間", "시간"),
    "minute": ("minute", "minutes", "分钟", "分鐘", "分間"),
}
_UNIT_KEY = {form: key for key, forms in NUMBER_UNITS.items() for form in forms}
_UNIT_FORMS_RE = "|".join(
    # (?ai:...) folds ASCII case inside the form only; \b after it keeps Unicode word rules
    rf"(?ai:{re.escape(form)})\b" if form.isascii() and form.isalpha() else re.escape(form)
    for form in sorted(_UNIT_KEY, key=len, reverse=True)  # longest first: 个星期 before 星期
)
_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
NUMBER_RE = re.compile(
    rf"百分之(?P<percent_of>{_NUMBER})"
    rf"|(?<![0-9])(?P<number>{_NUMBER})[ \t]*(?P<unit>{_UNIT_FORMS_RE})"
    r"|[£$€¥]\s?\d",
)
# Not numbers: a calendar year (1000 to 2999 before 年 or 년) and an ordinal (right after 第).
CALENDAR_YEAR_UNITS = ("年", "년")
ORDINAL_PREFIX = "第"


# ---------------------------------------------------------------- text views


def _without_note_callouts(text: str) -> str:
    """``text`` without its NOTE callouts (tutor additions), each from its tag line to the last '>' line."""
    lines = text.split("\n")
    kept: list[str] = []
    i = 0
    while i < len(lines):
        if NOTE_CALLOUT_RE.match(lines[i]):
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                i += 1
            continue
        kept.append(lines[i])
        i += 1
    return "\n".join(kept)


def _code_and_math_free(md: str) -> tuple[str, str]:
    """(code_free, note_text): the note without code; then the lecture prose without math.

    Code goes as in check_note: fenced blocks whole, inline spans deleted. note_text, which
    the terms and numbers checks read, also leaves out the four marker sections and the
    NOTE callouts. Math goes as units() excludes it: $$…$$, \\[…\\], \\(…\\), then inline
    $…$ by the pandoc rule.
    """
    code_free = strip_code(md)
    text = _without_note_callouts(strip_marker_sections(code_free)).replace("\\$", _DOLLAR_PLACEHOLDER)
    for pattern in (DISPLAY_MATH_RE, BRACKET_MATH_RE, PAREN_MATH_RE, INLINE_MATH_RE):
        text = pattern.sub(" ", text)
    return code_free, text.replace(_DOLLAR_PLACEHOLDER, "\\$")


def _slide_number(page) -> int:
    return int(page.label) if page.label is not None else page.n


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


# ---------------------------------------------------------------- folding


def _entry(name: str, status: str, details: list[str]) -> dict:
    return {"name": name, "status": status, "details": details}


def _fold(name: str, results: list[CheckResult]) -> dict:
    """One entry: the worst sub-result, with each non-PASS detail as "<sub-name>: <detail>"."""
    status = max((r.status for r in results), key=SEVERITY.__getitem__, default="PASS")
    details: list[str] = []
    for r in results:
        if r.status == "PASS":
            continue
        if r.details:
            details.extend(f"{r.name}: {d}" for d in r.details)
        else:
            details.append(r.name)
    return _entry(name, status, details)


def _skipped(name: str) -> dict:
    return _entry(name, "PASS", [SKIPPED])


def _error_detail(file_name: str, e: Exception) -> str:
    message = str(e)
    return message if message.startswith(file_name) else f"{file_name}: {message}"


# ---------------------------------------------------------------- checks


def _citation_problems(cits, pages, duration, transcript, slides_only) -> dict:
    details = resolve(cits, max_label(pages) if pages else None, duration)
    if transcript is None:
        if slides_only:
            details += [f"time citation in a slides-only unit: {c.raw}" for c in cits if c.kind == "time"]
        else:
            details.append(MISSING_TRANSCRIPT)
    if details:
        return _entry("citations", "FAIL", details)
    if duration is None and any(c.kind == "time" for c in cits):
        return _entry("citations", "WARN", [DURATION_UNKNOWN])
    return _entry("citations", "PASS", [])


def _check_citations(cits, pages, duration, transcript, slides_only, md: str, source, lang: str) -> dict:
    """The citation problems, then the quote_source and time_links sub-results folded in
    as "<sub-name>: <detail>"."""
    entry = _citation_problems(cits, pages, duration, transcript, slides_only)
    for sub in (_check_quote_source(md, transcript, pages, lang), _check_time_links(md, source)):
        if sub.status != "PASS":
            folded = _fold("citations", [sub])
            entry["status"] = max(entry["status"], folded["status"], key=SEVERITY.__getitem__)
            entry["details"] += folded["details"]
    return entry


def _check_time_links(md: str, source) -> CheckResult:
    """WARN: times a video unit has not linked yet, and links that point at another time."""
    details: list[str] = []
    if source is not None and source.kind in ("url", "platform") and source.url and time_link_platform(source.url):
        n = link_times(md, source.url)[1]
        if n:
            citations = "time citation is" if n == 1 else "time citations are"
            details.append(
                f"{n} {citations} not linked to the video: run tutor-any-lecture cite link --unit DIR"
            )
    details += link_time_problems(md)
    return CheckResult("time_links", "WARN" if details else "PASS", details)


# ---------------------------------------------------------------- quote_source


def _quote_norm(text: str) -> str:
    """NFKC, casefold, every run of non-letters-or-digits one space, stripped; no space next to CJK."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = NOT_LETTER_OR_DIGIT_RE.sub(" ", text).strip()
    return CJK_SPACE_RE.sub("", text)


def _joined(texts) -> tuple[str, list[int]]:
    """``_quote_norm`` of the texts joined by spaces, and where each text starts in it.

    Built piece by piece, so the result equals ``_quote_norm(" ".join(texts))``.
    """
    out = ""
    starts: list[int] = []
    for t in texts:
        n = _quote_norm(t)
        if out and n and not (CJK_RE.match(out[-1]) or CJK_RE.match(n[0])):
            out += " "
        starts.append(len(out))
        out += n
    return out, starts


def _quote_parts(quote: str) -> list[str]:
    """The normalised parts between editorial marks, without the parts too short to check.

    Inline code keeps its text (only the backticks go) and a Markdown link is read as its
    text: neither is an editorial mark.
    """
    text = INLINE_CODE_RE.sub(lambda m: NOT_LETTER_OR_DIGIT_RE.sub(" ", m.group(0).strip("`")), quote)
    text = MD_LINK_URL_RE.sub(lambda m: m.group(1).lstrip("!")[1:-1], text)
    parts = []
    for raw in EDITORIAL_RE.split(text):
        part = _quote_norm(raw)
        if CJK_RE.search(part):
            long_enough = len(part.replace(" ", "")) >= THRESHOLDS["quote_min_cjk_chars"]
        else:
            long_enough = len(part.split()) >= QUOTE_MIN_WORDS
        if long_enough:
            parts.append(part)
    return parts


def _part_at(part: str, text: str) -> int:
    """Where ``part`` starts in the normalised ``text``, or -1.

    A part in a CJK script may start anywhere; any other part matches only as a run of
    whole words, so "rest rate is now fix" is not in "the interest rate is now fixed".
    """
    if CJK_RE.search(part):
        return text.find(part)
    m = re.search(WORD_EDGE_BEFORE + re.escape(part) + WORD_EDGE_AFTER, text)
    return m.start() if m else -1


def _speaker_labels(segments) -> list[str | None] | None:
    """The speaker label in force at each segment, or None when the transcript has no labels.

    A transcript has labels when at least two segments begin with one. The label in force
    at a segment is its own, else the nearest earlier labelled segment's.
    """
    own = [m.group(1) if (m := SPEAKER_LABEL_RE.match(s.text.lstrip())) else None for s in segments]
    if sum(label is not None for label in own) < 2:
        return None
    in_force: list[str | None] = []
    current = None
    for label in own:
        current = label or current
        in_force.append(current)
    return in_force


class _QuoteSources:
    """The transcript and the slides, normalised once for every quote of a note."""

    def __init__(self, transcript, pages) -> None:
        self.segments = transcript.segments if transcript is not None else None
        self.pages = pages
        if self.segments is not None:
            self.all_text, self.starts = _joined(s.text for s in self.segments)
            self.labels = _speaker_labels(self.segments)
        else:
            self.all_text, self.starts = "", []
            self.labels = None
        self.slide_texts = [(_slide_number(p), _quote_norm(p.text)) for p in pages]

    def _window(self, c) -> tuple[str, list[int], list[int]]:
        """The normalised transcript text around a time citation, where each segment starts
        in it, and those segments' indexes."""
        lo = c.start - QUOTE_WINDOW_S
        hi = (c.end if c.end is not None else c.start) + QUOTE_WINDOW_S
        indexes = [i for i, s in enumerate(self.segments) if s.start <= hi and s.end >= lo]
        text, starts = _joined(self.segments[i].text for i in indexes)
        return text, starts, indexes

    def cited(self, c) -> str | None:
        """The text at one citation; None for a time when the unit has no transcript."""
        if c.kind == "slide":
            lo, hi = _span(c.start, c.end)
            return _joined(p.text for p in self.pages if lo <= _slide_number(p) <= hi)[0]
        if self.segments is None:
            return None
        return self._window(c)[0]

    def speaker(self, parts: list[str], cits) -> tuple[str, float] | None:
        """(label, segment start) of the speaker of a quote, or None when no label is in force.

        The first time citation, in citation order, whose window holds every part decides;
        the speaker is the label in force at the segment where the first part begins.
        """
        if self.labels is None:
            return None
        for c in cits:
            if c.kind != "time":
                continue
            text, starts, indexes = self._window(c)
            if all(_part_at(part, text) >= 0 for part in parts):
                k = indexes[bisect_right(starts, _part_at(parts[0], text)) - 1]
                label = self.labels[k]
                return (label, self.segments[k].start) if label else None
        return None

    def find(self, part: str) -> str | None:
        """Where ``part`` is: "at m:ss" in the transcript, else "on slide N", else None."""
        pos = _part_at(part, self.all_text)
        if pos >= 0:
            return f"at {format_seconds(self.segments[bisect_right(self.starts, pos) - 1].start)}"
        for n, text in self.slide_texts:
            if _part_at(part, text) >= 0:
                return f"on slide {n}"
        return None


def _word_positions(text: str, words: tuple[tuple[str, ...], tuple[str, ...]]) -> list[int]:
    """Where the words occur in ``text``: English as whole words ignoring case, Chinese as substrings."""
    english, chinese = words
    pattern = r"(?<![A-Za-z])(?:" + "|".join(english) + r")(?![A-Za-z])"
    found = [m.start() for m in re.finditer(pattern, text, re.IGNORECASE)]
    for word in chinese:
        found += [m.start() for m in re.finditer(re.escape(word), text)]
    return found


def _wrong_speaker(lead_in: str, tail: str, label: str) -> bool:
    """The note gives a quote to a student and the label does not, or the other way round."""
    student_label = label.split()[0] in STUDENT_LABEL_WORDS
    students = _word_positions(lead_in, STUDENT_WORDS)
    if students:
        last = max(students)
        speech = any(pos > last for pos in _word_positions(lead_in, SPEECH_WORDS))
        lecturer = any(pos > last for pos in _word_positions(lead_in, LECTURER_WORDS))
        if speech and not lecturer and not student_label:
            return True
    return student_label and not students and not _word_positions(tail, STUDENT_WORDS)


def _primary_subtag(lang: str) -> str:
    return re.split(r"[-_]", (lang or "").lower(), maxsplit=1)[0]


def _checks_speakers(lang: str) -> bool:
    return _primary_subtag(lang) in SPEAKER_CHECK_LANGS


def _check_quote_source(md: str, transcript, pages, lang: str) -> CheckResult:
    """Every cited quote is found at the place it cites (WARN when only elsewhere, FAIL when nowhere).

    A quote with no part long enough to check is a WARN, and so is an inline quote that the
    note gives to the wrong speaker (in an English or Chinese note, by the transcript's labels).
    A quote in a script the checks cannot split (``unsegmented``) is not looked up: WARN.
    """
    sources = _QuoteSources(transcript, pages)
    details: list[str] = []
    worst = "PASS"
    quotes = cited_quotes(md)
    inline = cited_quote_contexts(md)
    # The inline quotes are the last entries of cited_quotes, in the same order.
    contexts = [None] * (len(quotes) - len(inline)) + [(lead, tail) for _, _, lead, tail in inline]
    for (quote, cits), context in zip(quotes, contexts):
        parts = _quote_parts(quote)
        places = [t for t in (sources.cited(c) for c in cits) if t is not None]
        if not places:
            continue  # only times in a unit without a transcript
        shown = quote if len(quote) <= QUOTE_SHOWN_CHARS else quote[:QUOTE_SHOWN_CHARS] + "…"
        if unsegmented(quote):
            details.append(f"quote '{shown}': {NOT_APPLIED}")
            worst = max(worst, "WARN", key=SEVERITY.__getitem__)
            continue
        cited = ", ".join(_dedupe([CITATION_LINK_RE.sub(r"\1", c.raw) for c in cits]))
        if not parts:
            details.append(f"quote '{shown}' cited {cited} has no part of three words or six CJK characters to check")
            worst = max(worst, "WARN", key=SEVERITY.__getitem__)
            continue
        missing = [part for part in parts if not any(_part_at(part, place) >= 0 for place in places)]
        if not missing:
            speaker = sources.speaker(parts, cits) if context is not None and _checks_speakers(lang) else None
            if speaker is not None and _wrong_speaker(*context, speaker[0]):
                details.append(f"quote '{shown}' is {speaker[0]}'s words at {format_seconds(speaker[1])}")
                worst = max(worst, "WARN", key=SEVERITY.__getitem__)
            continue
        found = [sources.find(part) for part in missing]
        if all(found):
            details.append(f"quote '{shown}' is not at {cited}; found {found[0]}")
            worst = max(worst, "WARN", key=SEVERITY.__getitem__)
        else:
            details.append(f"quote '{shown}' cited {cited} is not in the transcript or the slides")
            worst = "FAIL"
    return CheckResult("quote_source", worst, details)


def _span(start, end) -> tuple[int, int]:
    """The inclusive slide range from ``start`` to ``end`` (or ``start`` alone), in either order."""
    a = int(start)
    b = int(end) if end else a
    return min(a, b), max(a, b)


def _check_coverage(cits, pages, md) -> dict:
    # Ranges are kept as (low, high) pairs, so a huge range costs nothing.
    spans = [_span(c.start, c.end) for c in cits if c.kind == "slide"]
    not_covered = "\n".join(marker_sections(md)["not-covered"])
    for first, last, single in NOT_COVERED_SLIDE_RE.findall(not_covered):
        if single:
            spans.append(_span(single, None))
        else:
            # "slides 5–3" is not a range: it lists slide 5.
            spans.append(_span(first, last) if int(first) <= int(last) else _span(first, None))
    details = [
        f"slide {n} is neither cited nor listed in the not-covered section"
        for n in sorted({_slide_number(p) for p in pages})
        if not any(lo <= n <= hi for lo, hi in spans)
    ]
    return _entry("coverage", "FAIL" if details else "PASS", details)


def _normalise(text: str) -> str:
    return " ".join(text.casefold().replace("-", " ").split())


def _terms_text(note_text: str) -> str:
    text = HTML_COMMENT_RE.sub(" ", note_text)
    text = HTML_TAG_RE.sub(" ", text)
    text = CALLOUT_TAG_RE.sub(" ", text)
    text = LINK_TARGET_RE.sub("]", text)
    return URL_RE.sub(" ", text)


def _terms(text: str) -> list[str]:
    """Runs of 2+ Capitalized words joined by one space or hyphen, and words with an
    internal capital that lie in no such run, in document order."""
    words = list(LATIN_WORD_RE.finditer(text))
    found: list[tuple[int, str]] = []
    in_run: set[int] = set()
    i = 0
    while i < len(words):
        j = i
        if words[i].group()[0].isupper():
            while (
                j + 1 < len(words)
                and words[j + 1].group()[0].isupper()
                and text[words[j].end() : words[j + 1].start()] in (" ", "-")
            ):
                j += 1
        if j > i:
            found.append((words[i].start(), text[words[i].start() : words[j].end()]))
            in_run.update(range(i, j + 1))
        i = j + 1
    for k, w in enumerate(words):
        if k not in in_run and any(ch.isupper() for ch in w.group()[1:]):
            found.append((w.start(), w.group()))
    return _dedupe([term for _, term in sorted(found)])


def _without_reader_guide(text: str) -> str:
    """``text`` without the lines between its H1 and its first H2: the table of contents and
    the paragraph that tells the reader how to read the note. Headings stay; a note with no
    H2 is left whole."""
    lines = text.split("\n")
    first_h2 = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if first_h2 is None:
        return text
    return "\n".join([line for line in lines[:first_h2] if line.startswith("# ")] + lines[first_h2:])


# The callout type names (NOTE, WARNING, …) are the note's own vocabulary, not lecture terms.
_CALLOUT_NAMES = {name.casefold() for name in CALLOUT_TYPES}


def _check_terms(note_text: str, sources: str, lang: str) -> dict:
    """WARN: capitalised terms of the prose that are in no source; not applied where
    capitals do not mark terms (German, Luxembourgish) or the prose is ``unsegmented``."""
    text = _terms_text(_without_reader_guide(note_text))
    if _primary_subtag(lang) in NOUN_CAPITAL_LANGS or unsegmented(text):
        return _entry("terms", "WARN", [NOT_APPLIED])
    haystack = _normalise(sources)
    details = [
        f"not in the transcript or slides: {term}"
        for term in _terms(text)
        if term.casefold() not in _CALLOUT_NAMES and _normalise(term) not in haystack
    ]
    return _entry("terms", "WARN" if details else "PASS", details)


def _is_calendar_year(number: str, unit: str) -> bool:
    return unit in CALENDAR_YEAR_UNITS and number.isdigit() and len(number) == 4 and 1000 <= int(number) <= 2999


def _numbers(text: str) -> dict[str, str]:
    """Each number's key, in order of first use, with its first match as written: after
    NFKC, each run of whitespace one space."""
    text = unicodedata.normalize("NFKC", text)
    found: dict[str, str] = {}
    for m in NUMBER_RE.finditer(text):
        if m.group("percent_of") is not None:
            key = m.group("percent_of") + "%"
        elif m.group("number") is not None:
            number, unit = m.group("number"), m.group("unit")
            if _is_calendar_year(number, unit) or text[: m.start()].endswith(ORDINAL_PREFIX):
                continue
            key = number + _UNIT_KEY[unit.lower()]
        else:
            key = "".join(m.group().split())
        found.setdefault(key, " ".join(m.group().split()))
    return found


def _check_numbers(note_text: str, sources: str) -> dict:
    """WARN: numbers with a unit or a currency sign on one side only, compared by key and
    shown as written."""
    in_note, in_sources = _numbers(note_text), _numbers(sources)
    details = [f"in the sources, not in the note: {shown}" for key, shown in in_sources.items() if key not in in_note]
    details += [f"in the note, not in the sources: {shown}" for key, shown in in_note.items() if key not in in_sources]
    return _entry("numbers", "WARN" if details else "PASS", details)


def _check_items(p: UnitPaths, plan, md: str, lang: str) -> dict:
    if "quiz" not in plan.outputs and "pretest" not in plan.outputs:
        return _skipped("items")
    if not p.items.exists():
        return _entry("items", "FAIL", ["items.json missing"])
    try:
        items = load_items(p.items)
    except ValueError as e:
        return _entry("items", "FAIL", [_error_detail("items.json", e)])
    assignment = None
    if p.assignment.exists():
        try:
            assignment = read_json(p.assignment, "assignment.json")
        except ValueError as e:
            return _entry("items", "FAIL", [_error_detail("assignment.json", e)])
    try:
        results = validate_items(items, plan, md, lang, assignment)
    except ValueError as e:
        return _entry("items", "FAIL", [_error_detail("assignment.json", e)])
    entry = _fold("items", results)
    if assignment is None:
        entry["status"] = "FAIL"
        entry["details"].append("assignment.json missing")
    return entry


def _check_cards(p: UnitPaths, plan, lang: str) -> dict:
    if "cards" not in plan.outputs:
        return _skipped("cards")
    if not p.cards_json.exists():
        return _entry("cards", "FAIL", ["cards.json missing"])
    try:
        cards = load_cards(p.cards_json)
    except ValueError as e:
        return _entry("cards", "FAIL", [_error_detail("cards.json", e)])
    concepts = [c["id"] for c in plan.concepts]
    results = validate_cards(cards, plan.goal, lang, concepts=concepts)
    # A missing or unreadable items.json is reported by the items check, not here.
    try:
        items = load_items(p.items)
    except (OSError, ValueError):
        items = None
    results.append(miss_rewritten(cards, items))
    return _fold("cards", results)


def _check_map(p: UnitPaths, plan) -> dict:
    if "map" not in plan.outputs:
        return _skipped("map")
    if not p.map.exists():
        return _entry("map", "FAIL", ["map.json missing"])
    try:
        m = load_map(p.map)
    except ValueError as e:
        return _entry("map", "FAIL", [_error_detail("map.json", e)])
    return _fold("map", validate_map(m))


def _banned_phrases(lang: str) -> list[str] | None:
    """The stock phrases listed for the note language's primary subtag, or None when it has no list."""
    subtag = _primary_subtag(lang)
    if not BANNED_LANG_RE.fullmatch(subtag):
        return None
    path = resources.files("tutor_any_lecture").joinpath("data", "banned_phrases", f"{subtag}.txt")
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return [line.strip() for line in text.split("\n") if line.strip()]


def _without_lecture_blockquotes(text: str) -> str:
    """``text`` without the lines of each blockquote that does not start as a callout."""
    kept: list[str] = []
    in_quote = keep = False
    for line in text.split("\n"):
        if line.lstrip().startswith(">"):
            if not in_quote:
                keep = bool(CALLOUT_START_RE.match(line))
            in_quote = True
            if keep:
                kept.append(line)
        else:
            in_quote = False
            kept.append(line)
    return "\n".join(kept)


def _phrase_norm(text: str) -> str:
    """NFKC, casefold, ’ read as ', every run of whitespace one space; no space between two CJK characters."""
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return CJK_PAIR_SPACE_RE.sub("", " ".join(text.split()))


def _banned_text(md: str) -> str:
    """The agent's own words: the note without code, HTML comments, link targets and URLs,
    quoted spans (as the gate pairs quotation marks) and blockquotes that are not callouts."""
    text = HTML_COMMENT_RE.sub(" ", strip_code(md))
    text = MD_LINK_URL_RE.sub(r"\1", text)
    text = BARE_URL_RE.sub(" ", ANGLE_URL_RE.sub(" ", text))
    text = _without_lecture_blockquotes(text)
    text = "\n".join(INLINE_QUOTE_RE.sub(" ", line) for line in text.split("\n"))
    return _phrase_norm(text)


def _phrase_re(phrase: str) -> re.Pattern:
    """``phrase`` normalised; an end in a letter or digit outside CJK sits at a word edge."""
    norm = _phrase_norm(phrase)

    def needs_edge(ch: str) -> bool:
        return bool(ALNUM_CHAR_RE.match(ch)) and not CJK_RE.match(ch)

    before = r"(?<![^\W_])" if needs_edge(norm[0]) else ""
    after = r"(?![^\W_])" if needs_edge(norm[-1]) else ""
    return re.compile(before + re.escape(norm) + after)


def _check_banned(md: str, lang: str) -> dict:
    """WARN: stock phrases of the note language's list in the agent's own words, matched as
    whole words; PASS, not applied, for a language with no list."""
    phrases = _banned_phrases(lang)
    if phrases is None:
        return _entry("banned_phrases", "PASS", [f"{NOT_APPLIED}: {lang}"])
    text = _banned_text(md)
    details = [f"banned phrase: {phrase}" for phrase in phrases if _phrase_re(phrase).search(text)]
    return _entry("banned_phrases", "WARN" if details else "PASS", details)


# ---------------------------------------------------------------- the gate


def _span_text(window) -> str:
    return f"{window[0]}-{window[1]}"


def format_measures(m: dict) -> str:
    """The ``measures:`` line verify prints after its table (ASCII only).

    A ``length`` without a ``total`` was not applied for the note's language.
    """
    if m["length"]["total"] is None:
        length = f"length {NOT_APPLIED}"
    elif m["minutes"] is None:
        length = f"length {m['length']['total']} {m['length']['unit']} (duration unknown: no per-minute values)"
    else:
        length = f"length {m['length']['per_min']} {m['length']['unit']}/min ({_span_text(m['length']['window'])})"
    if m["minutes"] is None:
        parts = [length]
    else:
        parts = [
            length,
            f"time citations {m['time_citations']['per_min']}/min (>= {m['time_citations']['min']})",
            f"quotes {m['quotes']['per_min']}/min (>= {m['quotes']['min']})",
        ]
    for key, name in (("quote_ratio", "quote ratio"), ("quote_share", "quote share")):
        if m[key] is not None:
            parts.append(f"{name} {m[key]['value']} ({_span_text(m[key]['window'])})")
    h2 = m["h2"]
    parts.append(f"H2 {h2['count']}" + (f" (<= {h2['max']})" if h2["max"] is not None else ""))
    return "measures: " + "; ".join(parts)


def run_verify(unit: Path) -> dict:
    """Run the nine checks on ``unit``, write verify.json and return the same object.

    A missing or invalid plan.json, or a missing explanation.md, propagates and
    writes nothing.
    """
    unit = Path(unit)
    p = UnitPaths(unit)
    plan = load_plan(p.plan)
    md = read_text(p.explanation, "explanation.md")
    source = SourceInfo.read(p.source) if p.source.exists() else None
    transcript = Transcript.from_json(p.transcript) if p.transcript.exists() else None
    pages = load_pages(unit)

    slides_only = transcript is None and source is not None and source.kind == "slides-only"
    if slides_only:
        duration = None
    elif plan.duration_s is not None:
        duration = plan.duration_s
    elif source is not None:
        duration = source.duration
    else:
        duration = None
    lang = plan.note_language
    code_free, note_text = _code_and_math_free(md)
    cits = parse(code_free)
    sources = "\n".join([transcript.text() if transcript is not None else ""] + [pg.text for pg in pages])

    checks = [
        _check_citations(cits, pages, duration, transcript, slides_only, md, source, lang),
        _check_coverage(cits, pages, md),
        _check_terms(note_text, sources, lang),
        _check_numbers(note_text, sources),
        _fold(
            "structure",
            check_note(
                md,
                lang,
                plan.goal,
                duration / 60 if duration is not None else None,
                plan.output_target,
                lecture_lang=plan.lecture_language,
                quote_density=plan.quote_density,
            ),
        ),
        _check_items(p, plan, md, lang),
        _check_cards(p, plan, lang),
        _check_map(p, plan),
        _check_banned(md, lang),
    ]
    overall = "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PASS"
    minutes = duration / 60 if duration is not None else None
    result = {
        "checks": checks,
        "overall": overall,
        "warnings": sum(1 for c in checks if c["status"] == "WARN"),
        # What structure measured, recorded whether it passed or not.
        "measures": measure_note(md, lang, plan.goal, minutes, plan.lecture_language, plan.quote_density),
        "report": REPORT_PASS if overall == "PASS" else REPORT_FAIL,
    }
    p.verify.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result
