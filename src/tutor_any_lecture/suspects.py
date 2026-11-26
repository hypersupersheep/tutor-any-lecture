"""ASR suspects: transcript words, or stretches of CJK text, that look like a misheard slide term.

Flag only, never fix: the transcript is read and left byte-identical. The agent turns
sources/suspects.json into the errata table of the note.
"""

from __future__ import annotations

import difflib
import json
import unicodedata
from pathlib import Path

from .slides import Page, load_pages, term_list
from .textstats import cjk_runs, cjk_script
from .transcript import Transcript
from .unit import UnitPaths

THRESHOLD = 0.8
# Word endings cut off to find a plain inflection of a slide term ("payments", "included").
INFLECTION_ENDINGS = ("ing", "ed", "es", "s", "e", "d")
# The lengths of a CJK slide term that is compared: a shorter one leaves too little to tell
# a mishearing from another word, and term_list keeps no run longer than 10.
CJK_TERM_MIN, CJK_TERM_MAX = 4, 10


def norm(s: str) -> str:
    """Compare form: NFKD, combining marks removed, casefolded (ignores case and diacritics)."""
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(c for c in decomposed if unicodedata.combining(c) == 0).casefold()


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _stems(word: str) -> set[str]:
    """``word`` and ``word`` minus each of ``INFLECTION_ENDINGS`` it ends with, when 4+ characters remain.

    Two words whose stems meet are inflections of one another ("includes" and "included"
    share "include"); a word that differs in its middle ("schedual") shares none.
    """
    stems = {word}
    for ending in INFLECTION_ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            stems.add(word[: -len(ending)])
    return stems


def _best_match(key: str, matchers: list[tuple[str, difflib.SequenceMatcher]]) -> tuple[str, float]:
    """The slide term closest to ``key`` and its ratio; ties go to the earlier term.

    Each matcher holds one normalised term as its second sequence. Terms whose quick
    upper bounds are already below the threshold are skipped: they cannot be flagged,
    and a best ratio below the threshold is never reported.
    """
    best_term, best = matchers[0][0], -1.0
    for term, matcher in matchers:
        matcher.set_seq1(key)
        if matcher.real_quick_ratio() < THRESHOLD or matcher.quick_ratio() < THRESHOLD:
            continue
        ratio = matcher.ratio()
        if ratio > best:
            best_term, best = term, ratio
    return best_term, best


# CJK terms keyed by (written length, free position, NFKC form without that position); each
# entry is (order in term_list, the term, its NFKC character at the free position).
CjkIndex = dict[tuple[int, int, str], list[tuple[int, str, str]]]


def _cjk_index(terms: list[str]) -> CjkIndex:
    """The CJK terms (every character has a ``cjk_script``, 4 to 10 characters), indexed by
    length and by the one position a window may differ in."""
    index: CjkIndex = {}
    for order, term in enumerate(terms):
        if not CJK_TERM_MIN <= len(term) <= CJK_TERM_MAX or any(cjk_script(c) is None for c in term):
            continue
        form = _nfkc(term)
        for i, ch in enumerate(form):
            index.setdefault((len(term), i, form[:i] + form[i + 1:]), []).append((order, term, ch))
    return index


def _cjk_nearest(window: str, form: str, index: CjkIndex) -> str | None:
    """The first term (in term_list order) of ``window``'s written length whose NFKC form
    differs from ``form`` (the window's NFKC form) in exactly one position, else None."""
    best: tuple[int, str] | None = None
    for i, ch in enumerate(form):
        for order, term, term_ch in index.get((len(window), i, form[:i] + form[i + 1:]), ()):
            if term_ch != ch and (best is None or order < best[0]):
                best = (order, term)
    return best[1] if best is not None else None


def flag_suspects(transcript: Transcript, pages: list[Page], lang: str) -> list[dict]:
    """Transcript tokens close to, but not found in, the slides.

    Latin path: each run of letters of no CJK script (``cjk_runs``) is a token, compared
    after ``norm`` with every slide term; a ratio of ``THRESHOLD`` or more is a suspect. A
    token whose stems meet the stems of a slide term is a plain inflection of that term
    ("payments" for "payment"), not a suspect.

    CJK path: every window of a CJK run as long as a CJK term (``_cjk_index``) is compared,
    after NFKC (``norm``'s NFKD would split a Hangul syllable), with the terms of that length;
    it is a suspect when it is not in the NFKC slide text and differs from a term in exactly
    one position. Its ratio is ``(L - 1) / L`` for a term of L characters; ``THRESHOLD`` does
    not apply.

    One entry per segment for each distinct compared form, ``heard`` as the segment first
    has it; entries come in order of where the heard text starts, the shorter first.
    ``lang`` is kept for the interface; tokens are chosen by script, so it has no effect.
    """
    terms = term_list(pages)
    if not terms:
        return []
    term_stems = set().union(*(_stems(norm(t)) for t in terms))
    # Token first, term second, as in SequenceMatcher(None, norm(token), norm(term), autojunk=False).
    matchers = [(t, difflib.SequenceMatcher(None, "", norm(t), autojunk=False)) for t in terms]
    page_text = "\n".join(p.text for p in pages)
    slide_text = norm(page_text)
    slide_nfkc = _nfkc(page_text)
    index = _cjk_index(terms)
    lengths = sorted({length for length, _, _ in index})

    # One computation per distinct compared form: None means "not a suspect".
    cache: dict[str, tuple[str, float] | None] = {}
    cjk_cache: dict[tuple[int, str], str | None] = {}
    found: list[dict] = []
    for segment in transcript.segments:
        time = float(segment.start)
        reported: set[str] = set()
        reported_cjk: set[str] = set()
        for run, script in cjk_runs(segment.text):
            if script is not None:
                for offset in range(len(run)):
                    for length in lengths:
                        if offset + length > len(run):
                            break
                        window = run[offset:offset + length]
                        form = _nfkc(window)
                        if form in reported_cjk:
                            continue
                        if (length, form) not in cjk_cache:
                            cjk_cache[length, form] = None if form in slide_nfkc else _cjk_nearest(window, form, index)
                        nearest = cjk_cache[length, form]
                        if nearest is not None:
                            reported_cjk.add(form)
                            ratio = round((length - 1) / length, 3)
                            found.append({"time": time, "heard": window, "nearest": nearest, "ratio": ratio})
                continue
            key = norm(run)
            if key in reported:
                continue
            if key not in cache:
                if key in slide_text:
                    cache[key] = None
                else:
                    term, ratio = _best_match(key, matchers)
                    cache[key] = (term, ratio) if ratio >= THRESHOLD else None
            hit = cache[key]
            if hit is None or _stems(key) & term_stems:
                continue
            reported.add(key)
            found.append({"time": time, "heard": run, "nearest": hit[0], "ratio": round(hit[1], 3)})
    return found


def write_suspects(unit: Path) -> list[dict]:
    """Flag the unit's transcript against its slides and write sources/suspects.json."""
    paths = UnitPaths(unit)
    if not paths.transcript.is_file():
        raise FileNotFoundError(f"transcript not found: {paths.transcript}; run an acquisition first")
    transcript = Transcript.from_json(paths.transcript)
    pages = load_pages(unit)
    found = flag_suspects(transcript, pages, transcript.language or "")
    paths.suspects.parent.mkdir(parents=True, exist_ok=True)
    paths.suspects.write_text(json.dumps(found, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return found
