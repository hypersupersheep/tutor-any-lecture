"""Language-aware text measures: units (CJK characters or words), n-grams, overlap.

Pure functions, standard library only. Code, LaTeX and URLs never count as prose.
"""

from __future__ import annotations

import re
import unicodedata

CJK_LANGS = {"zh", "ja", "ko"}
# The one table of CJK code points: script name -> inclusive ranges. Every module reads it.
CJK_SCRIPTS: dict[str, tuple[tuple[int, int], ...]] = {
    # 々 〆 〇, Extension A, the Unified Ideographs, the compatibility ideographs, planes 2 and 3
    "han": ((0x3005, 0x3007), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x3FFFF)),
    "hiragana": ((0x3040, 0x309F),),
    # katakana, its phonetic extensions, the halfwidth forms
    "katakana": ((0x30A0, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F)),
    "hangul": ((0xAC00, 0xD7AF),),
}
# The body of a regex character class over every range, so verify can build on CJK_RE.pattern.
CJK_CLASS = "".join(f"\\U{lo:08X}-\\U{hi:08X}" for ranges in CJK_SCRIPTS.values() for lo, hi in ranges)
CJK_RE = re.compile("[" + CJK_CLASS + "]")
# Written without spaces between words: these scripts, CJK punctuation and the fullwidth forms.
UNSPACED_SCRIPTS = frozenset({"han", "hiragana", "katakana"})
UNSPACED_RANGES = ((0x3001, 0x303F), (0xFF01, 0xFF65))
WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
ALNUM_RE = re.compile(r"[^\W_]")

_FENCE_OPEN_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"(`+).+?\1")

DISPLAY_MATH_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)
BRACKET_MATH_RE = re.compile(r"\\\[.*?\\\]", re.DOTALL)
PAREN_MATH_RE = re.compile(r"\\\(.*?\\\)", re.DOTALL)
# Inline $…$ on one line: opening $ before a non-space, closing $ after a non-space and
# not before a digit, so "$5 and $10" is left alone.
INLINE_MATH_RE = re.compile(r"\$(?=\S)[^$\n]*?(?<=\S)\$(?!\d)")
MD_LINK_URL_RE = re.compile(r"(!?\[[^\]\n]*\])\([^)\n]*\)")
ANGLE_URL_RE = re.compile(r"<https?://[^>\s]*>")
BARE_URL_RE = re.compile(r"https?://\S+")

# The scripts the word and quote checks can split: by spaces, or one CJK character at a
# time. A script is the first word of a character's Unicode name.
SPLIT_SCRIPTS = frozenset({
    "LATIN", "GREEK", "CYRILLIC", "ARMENIAN", "GEORGIAN", "HEBREW", "ARABIC", "CJK", "IDEOGRAPHIC",
    "HIRAGANA", "KATAKANA", "HANGUL", "FULLWIDTH", "HALFWIDTH", "MODIFIER",
})
_NAME_WORD_RE = re.compile(r"[ -]")


def is_cjk_language(lang: str) -> bool:
    """True when the primary subtag of `lang` is zh, ja or ko ("zh-CN" yes, "auto" no)."""
    primary = re.split(r"[-_]", (lang or "").lower(), maxsplit=1)[0]
    return primary in CJK_LANGS


def cjk_range_script(ch: str) -> str | None:
    """The script of ``CJK_SCRIPTS`` whose range holds ``ch``, whatever its category."""
    cp = ord(ch)
    for script, ranges in CJK_SCRIPTS.items():
        if any(lo <= cp <= hi for lo, hi in ranges):
            return script
    return None


def cjk_script(ch: str) -> str | None:
    """The CJK script of ``ch``; None outside the ranges and for punctuation (``・``, ``゠``)."""
    if unicodedata.category(ch).startswith("P"):
        return None
    return cjk_range_script(ch)


def unspaced(ch: str) -> bool:
    """True for a character of a script written without spaces: Han and kana (any category),
    CJK punctuation (U+3001 to U+303F) and the fullwidth forms (U+FF01 to U+FF65).
    Hangul is not unspaced: Korean puts spaces between words."""
    cp = ord(ch)
    return cjk_range_script(ch) in UNSPACED_SCRIPTS or any(lo <= cp <= hi for lo, hi in UNSPACED_RANGES)


def join_lines(lines: list[str]) -> str:
    """Lines joined into one text: each stripped, empty ones dropped, and two neighbours
    joined with no space when the left one ends and the right one starts with an
    ``unspaced`` character, else with one space. Spaces inside a line stay."""
    out = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if out and not (unspaced(out[-1]) and unspaced(line[0])):
            out += " "
        out += line
    return out


def cjk_runs(text: str) -> list[tuple[str, str | None]]:
    """The maximal runs of letters, in order, each with its script.

    A CJK letter is a character ``cjk_script`` names; any other alphabetic character is a
    letter of script None. Digits, punctuation and spaces end a run, and so does a change of
    script, including one between han, hiragana and katakana.
    """
    runs: list[tuple[str, str | None]] = []
    current: list[str] = []
    current_script: str | None = None
    for ch in text:
        script = cjk_script(ch)
        if script is not None or ch.isalpha():
            if current and script != current_script:
                runs.append(("".join(current), current_script))
                current = []
            current.append(ch)
            current_script = script
        elif current:
            runs.append(("".join(current), current_script))
            current = []
    if current:
        runs.append(("".join(current), current_script))
    return runs


def unsegmented(text: str) -> bool:
    """True when most letters of ``text`` are in a script the checks cannot split into words.

    After NFC, each letter and each mark is counted, except the generic COMBINING marks
    (they belong to no script). More than half of the counted characters must lie outside
    SPLIT_SCRIPTS (a character without a Unicode name is outside): Thai, Lao, Khmer, Burmese
    and the Indic scripts write vowel signs as marks and often no spaces between words.
    """
    counted = other = 0
    for ch in unicodedata.normalize("NFC", text):
        if not (ch.isalpha() or unicodedata.category(ch).startswith("M")):
            continue
        name = unicodedata.name(ch, "")
        if name.startswith("COMBINING"):
            continue
        counted += 1
        # "THAI CHARACTER SARA II" -> THAI; "CJK UNIFIED IDEOGRAPH-5229" -> CJK; no name -> ""
        if _NAME_WORD_RE.split(name, maxsplit=1)[0] not in SPLIT_SCRIPTS:
            other += 1
    return counted > 0 and other * 2 > counted


def fenced_lines(lines: list[str]) -> list[bool]:
    """For each line, whether it belongs to a fenced code block (its fences included).

    The one fence rule of the package: a fence opens on a line matching ^\\s*(```|~~~)
    and closes on the next line that, after its leading whitespace, starts with the same
    three characters (an indented or longer fence closes it too), or at the end of the text.
    """
    out: list[bool] = []
    fence: str | None = None
    for line in lines:
        if fence is not None:
            out.append(True)
            if line.lstrip().startswith(fence):
                fence = None
            continue
        m = _FENCE_OPEN_RE.match(line)
        if m:
            fence = m.group(1)
        out.append(m is not None)
    return out


def strip_code(md: str) -> str:
    """Drop fenced code blocks whole and delete inline code spans.

    Every line outside a fenced block is kept, so the result has one line per such line.
    """
    lines = md.split("\n")
    return "\n".join(
        INLINE_CODE_RE.sub("", line) for line, fenced in zip(lines, fenced_lines(lines)) if not fenced
    )


def strip_markup(text: str) -> str:
    """Remove code, LaTeX and URLs; Markdown link text stays."""
    text = strip_code(text)
    text = DISPLAY_MATH_RE.sub(" ", text)
    text = BRACKET_MATH_RE.sub(" ", text)
    text = PAREN_MATH_RE.sub(" ", text)
    text = INLINE_MATH_RE.sub(" ", text)
    text = MD_LINK_URL_RE.sub(r"\1", text)
    text = ANGLE_URL_RE.sub(" ", text)
    text = BARE_URL_RE.sub(" ", text)
    return text


def units(text: str, lang: str) -> int:
    """CJK characters for CJK languages, words otherwise, after strip_markup."""
    clean = strip_markup(text)
    if is_cjk_language(lang):
        return len(CJK_RE.findall(clean))
    return len(WORD_RE.findall(clean))


def ngrams(text: str, lang: str) -> set[str]:
    """CJK: character 3-grams over letters and digits. Otherwise: word 2-grams."""
    low = text.lower()
    if is_cjk_language(lang):
        chars = "".join(ALNUM_RE.findall(low))
        return {chars[i : i + 3] for i in range(len(chars) - 2)}
    words = WORD_RE.findall(low)
    return {f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)}


def containment(a: str, b: str, lang: str) -> float:
    """|A∩B| / |A| over n-grams; 0.0 when A is empty."""
    na, nb = ngrams(a, lang), ngrams(b, lang)
    if not na:
        return 0.0
    return len(na & nb) / len(na)


def _char_norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def char_jaccard(a: str, b: str) -> float:
    """Jaccard of character 3-grams, lowercased, whitespace collapsed, punctuation kept.

    When both texts are too short for a 3-gram: 1.0 if they are equal, else 0.0.
    """
    na, nb = _char_norm(a), _char_norm(b)
    ga = {na[i : i + 3] for i in range(len(na) - 2)}
    gb = {nb[i : i + 3] for i in range(len(nb) - 2)}
    union = ga | gb
    if not union:
        return 1.0 if na == nb else 0.0
    return len(ga & gb) / len(union)
