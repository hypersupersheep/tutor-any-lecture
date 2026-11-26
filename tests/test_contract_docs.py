"""The writing contract, the teaching rules and the gate, as the skill's documents state them."""

import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "tutor-any-lecture"
HEADING_RE = re.compile(r"^(#{1,6}) ")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
CJK_RE = re.compile(r"[㐀-䶿一-鿿぀-ヿ가-힯]")


# ---------------------------------------------------------------- local helpers


def read(rel: str) -> str:
    """A file under skills/tutor-any-lecture/."""
    return (SKILL_DIR / rel).read_text(encoding="utf-8")


def _outside_fences(lines: list[str]) -> list[bool]:
    """For each line, whether it lies outside a fenced block (a fence line is inside)."""
    out, fence = [], None
    for line in lines:
        if fence is not None:
            out.append(False)
            if line.lstrip().startswith(fence):
                fence = None
            continue
        m = FENCE_RE.match(line)
        if m:
            fence = m.group(1)
        out.append(m is None)
    return out


def section(text: str, heading: str) -> str:
    """From the line equal to ``heading`` to the next heading of the same or a higher level.

    Lines inside fenced blocks are never headings.
    """
    lines = text.split("\n")
    outside = _outside_fences(lines)
    (start,) = [i for i, line in enumerate(lines) if line == heading and outside[i]]
    level = len(HEADING_RE.match(heading).group(1))
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if outside[i] and (m := HEADING_RE.match(lines[i])) and len(m.group(1)) <= level
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def fences(text: str) -> list[list[str]]:
    """The lines inside each fenced block of ``text``, fence lines left out."""
    lines = text.split("\n")
    out: list[list[str]] = []
    current: list[str] | None = None
    fence = None
    for line in lines:
        if fence is not None:
            if line.lstrip().startswith(fence):
                out.append(current)
                fence, current = None, None
            else:
                current.append(line)
            continue
        m = FENCE_RE.match(line)
        if m:
            fence, current = m.group(1), []
    return out


def paragraph_starting(text: str, start: str) -> str:
    """The paragraph (up to the next blank line) whose first line starts with ``start``."""
    (para,) = [p for p in text.split("\n\n") if p.startswith(start)]
    return para


# ---------------------------------------------------------------- the writing contract

ATTRIBUTION_SENTENCES = (
    "Every clause of a sentence you attribute to the lecturer is in the span it cites.",
    "Context, a contrast or a consequence that you add goes into a sentence of its own that does not name the "
    "lecturer, or into a NOTE callout; when the lecturer names one side of a contrast, write only that side.",
    "What you add is never attributed to the lecturer: it stands in a sentence that does not name the lecturer, "
    "or in a NOTE callout.",
    "Give a quote to the speaker the transcript names; when a student's words are inaudible and the lecturer "
    "restates them, write that the lecturer restated a student's answer.",
)
ERRATA_SLIP = (
    "The Should be cell names whose slip it was (\"lecturer's slip, corrected\") only when the transcript's "
    "speaker labels or the lecturer's own words show it; otherwise it says \"speaker unclear\"."
)


def test_writing_states_attribution_rules():
    writing = read("references/writing.md")
    faithful = section(writing, "## Faithful to the lecturer")
    for s in ATTRIBUTION_SENTENCES:
        assert s in faithful, s
    assert writing.count("Give a quote to the speaker the transcript names") == 1
    assert "a term the lecturer uses before defining it" in section(writing, "## Callouts")
    assert ERRATA_SLIP in section(writing, "## Marker sections")


DERIVATION_BLOCK = [
    "### Derivation: <what is derived>",
    "<the steps, each naming the rule it uses>",
    "*Why <the step in question>?*",
    "<details><summary>Answer</summary>",
    "<the answer, quoting the lecturer, with its citation>",
    "</details>",
]


def test_writing_places_why_prompts_and_faded_examples():
    writing = read("references/writing.md")
    heading = "## Derivations, examples and teaching order"
    assert writing.split("\n").count(heading) == 1
    part = section(writing, heading)
    for s in (
        'Every derivation ends with one "why does this step hold" prompt',
        "*为什么<那一步>？*",
        "a faded example (a parallel case with new numbers whose first steps the prompt works, asking for the last ones)",
        "a setup-only item (a parallel case alone)",
        "Explain a term or result before the first sentence that uses it",
        "A derivation or a worked example shows at most 15 steps in one run",
    ):
        assert s in part, s
    blocks = [lines for lines in fences(part) if DERIVATION_BLOCK[0] in lines]
    assert len(blocks) == 1
    block = blocks[0]
    while block and not block[-1].strip():
        block = block[:-1]
    # The six lines in order, one blank line between each.
    assert block == [x for line in DERIVATION_BLOCK for x in (line, "")][:-1]
    teaching = read("references/teaching.md")
    assert "faded example" in teaching and "setup-only" in teaching
    assert "**Why prompts.**" not in teaching


NOTE_LANGUAGE_SPANS = (
    "`## 课前测`",
    "`## 未讲到的内容和勘误`",
    "`<details><summary>答案</summary>`",
    "`> 转写稿和课件勘误`",
    "`| 时间 | 听到的 | 应为 |`",
    "`阅读说明：`",
)


def test_writing_allows_note_language_strings():
    writing = read("references/writing.md")
    assert "The fixed strings follow the note language." in writing
    for s in NOTE_LANGUAGE_SPANS:
        assert s in writing, s
    (skeleton,) = [lines for lines in fences(section(writing, "## Skeleton")) if "# <Unit title>" in lines]
    stripped = [line.strip() for line in skeleton]
    opens = [i for i, line in enumerate(stripped) if line == "<details><summary>Answer</summary>"]
    closes = [i for i, line in enumerate(stripped) if line == "</details>"]
    assert opens and len(opens) == len(closes)
    assert all(stripped[i + 1] == "" for i in opens)
    assert all(stripped[i - 1] == "" for i in closes)
    terms = "Use one spelling of each term across the note, items.json, cards.json and map.json."
    assert terms in section(writing, "## Language and terms")
    overview = section(read("references/teaching.md"), "## Overview map")
    assert "Node labels and edge verbs are written in plan.note_language" in overview
    assert '"用于"' in overview


def test_writing_settles_quotes_measures_and_targets():
    writing = read("references/writing.md")
    for s in (
        "A definition or a result that the reader should see whole, one sentence or more, goes in a blockquote "
        "with its citation on its last line; shorter words of the lecturer go inline.",
        "`quote_ratio` applies only to a Chinese, Japanese or Korean note of a lecture in another script; every "
        "other pair uses `quote_share`, including an English note of a Chinese lecture and a Japanese note of a "
        "Chinese lecture.",
        "The obsidian target's `[[#…]]` links and `==highlights==` do not render on GitHub: write for the markdown "
        "target when the note will be read there.",
        "On the markdown target never write `[[#…]]` links: the gate does not check them there, and GitHub shows "
        "them as text.",
    ):
        assert s in writing, s


def test_documents_agree_on_checks_suspects_and_duration():
    writing = read("references/writing.md")
    assert writing.count("at most one per H2 section") == 2
    assert "(one per section quiz)" not in writing
    skill = read("SKILL.md")
    assert (
        "With a transcript and slides, run `tutor-any-lecture slides suspects --unit DIR`; "
        "a unit without slides skips it."
    ) in skill
    imp = read("references/adapters/import.md")
    assert "do not ask for it on the first run" in imp
    assert "ask for the media length" not in imp


# ---------------------------------------------------------------- teaching


def test_teaching_states_what_the_pretest_changes():
    teaching = read("references/teaching.md")
    for s in (
        "read closely",
        "below 0.4",
        "0.4 to 0.8",
        "above 0.8",
        "a level set in the profile always wins",
        "in at most two sentences",
        "no worked steps",
        "with the note closed",
        "never triggers a rewrite of the note",
    ):
        assert s in teaching, s
    assert "in at most two sentences" in read("references/writing.md")
    (level_row,) = [line for line in read("references/profile.md").splitlines() if line.startswith("| `level` |")]
    assert "newest earlier unit's pretest mean" in level_row
    assert ", later," not in level_row


def test_teaching_grades_by_rubric_line_and_interleaves_quiz_units():
    teaching = read("references/teaching.md")
    assert "name the rubric line you applied" in teaching
    assert 'whose plan.json lists "quiz"' in teaching
    assert 'whose plan.json lists "quiz"' in read("SKILL.md")
