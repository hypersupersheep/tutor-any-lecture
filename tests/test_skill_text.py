# tests/test_skill_text.py
import argparse
import re
from pathlib import Path

import pytest
import yaml

from tutor_any_lecture.cli import build_parser
from tutor_any_lecture.config import config_dir

SKILL = Path("skills/tutor-any-lecture/SKILL.md")
TEACHING = SKILL.parent / "references" / "teaching.md"
GUARDRAILS = [
    "Never type, store or ask for passwords.",
    "Never read browser cookies.",
    "Download media only when the profile allows it.",
    "Never circumvent DRM, and never use the learner's passwords or cookies. Downloading audio is the learner's choice and responsibility, through the public_video_audio switch.",
    "Every claim you attribute to the lecturer carries a (slide N) or (mm:ss) citation.",
]
CARD_NOTICE = (
    "Card-writing rules adapted from anki-card-forge (https://github.com/FrostySL/anki-card-forge), "
    "MIT License, Copyright (c) 2026 Lukas Sinning."
)
# U+3000-30FF, U+3400-9FFF, U+AC00-D7AF, U+FF00-FFEF
CJK = re.compile("[　-ヿ㐀-鿿가-힯＀-￯]")
AGENT_SPECIFIC = ["javascript_tool", "Claude in Chrome", "mcp__"]


# ---- local helpers ----

def read(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def split_frontmatter(text: str) -> tuple[str, str]:
    """(frontmatter YAML, body); the body is everything after the closing --- line."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    return "\n".join(lines[1:end]), "\n".join(lines[end + 1:])


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(split_frontmatter(read(path))[0]) or {}


def body(path: Path) -> str:
    return split_frontmatter(read(path))[1]


LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\s]+)\)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def relative_links(path: Path) -> list[str]:
    """Targets of Markdown links [text](target) that are not URLs, anchors or absolute paths; #fragments dropped."""
    out = []
    for target in LINK.findall(read(path)):
        target = target.split("#", 1)[0]
        if not target or SCHEME.match(target) or target.startswith(("/", "\\", "~")):
            continue
        out.append(target)
    return out


CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^\s*(`{3}|~{3})")  # a line opening or closing a fenced block
CMD = re.compile(r"(?:^|[\s(])tutor-any-lecture((?:[ \t]+[a-z][a-z-]*(?=\s|$)){1,2})")


def code_texts(text: str) -> list[str]:
    """Inline code spans outside fences, plus every line inside fenced blocks."""
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(line)
        else:
            out.extend(CODE_SPAN.findall(line))
    return out


def subcommands_mentioned(path: Path) -> list[str]:
    """Space-joined subcommand paths ("doctor", "acquire route") from `tutor-any-lecture ...` in code."""
    paths = []
    for chunk in code_texts(read(path)):
        for m in CMD.finditer(chunk):
            paths.append(" ".join(m.group(1).split()))
    return paths


def cli_subcommands() -> list[str]:
    """Every subcommand path of build_parser(), at every depth ("acquire", "acquire route")."""
    paths = []

    def walk(parser: argparse.ArgumentParser, prefix: str) -> None:
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    path = f"{prefix} {name}".strip()
                    paths.append(path)
                    walk(sub, path)

    walk(build_parser(), "")
    return paths


# ---- tests ----

def test_length():
    assert len(read(SKILL).splitlines()) <= 150


def test_description_triggers():
    desc = frontmatter(SKILL)["description"][:180].lower()
    assert all(w in desc for w in ["lecture", "notes", "quiz"])


def test_guardrails_present():
    t = read(SKILL)
    for s in GUARDRAILS:
        assert s in t


def test_referenced_files_exist():
    assert not [p for p in relative_links(SKILL) if not (SKILL.parent / p).exists()]


def test_subcommands_exist():
    assert set(subcommands_mentioned(SKILL)) <= set(cli_subcommands())


def test_no_private_terms():
    denylist = config_dir() / "denylist.txt"
    if not denylist.exists():
        pytest.skip(f"no denylist at {denylist}")
    terms = [s.strip() for s in read(denylist).splitlines()]
    terms = [t for t in terms if t and not t.startswith("#")]
    text = "\n".join(read(p) for p in sorted(SKILL.parent.rglob("*.md"))).lower()
    assert not [t for t in terms if t.lower() in text]


def test_body_agent_neutral():
    b = body(SKILL)
    assert not CJK.search(b)
    assert not [s for s in AGENT_SPECIFIC if s in b]


def test_helpers_not_vacuous():
    assert len(relative_links(SKILL)) >= 5 and len(set(subcommands_mentioned(SKILL))) >= 6


def test_step0_names_installers():
    t = read(SKILL)
    for name in ("scripts/install.sh", "scripts/install.ps1"):
        assert f"`{name}`" in t
        assert (SKILL.parent / name).exists()


def test_card_rules_notice():
    assert CARD_NOTICE in read(TEACHING)


# ---- task 27: the post quiz, installing, the asr add-on ----

README = Path("README.md")
README_ZH = Path("README.zh-CN.md")
NOTICES_POINTER = "The full notice is in THIRD_PARTY_NOTICES.md."
# "git" as a word of its own: not part of "GitHub", whatever script stands beside it.
GIT_WORD = re.compile(r"(?<![A-Za-z])git(?![A-Za-z])")


def install_section(path: Path) -> str:
    """The README's install section: from its "## Install" (or "## 安装") heading to the next H2."""
    lines = read(path).splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() in ("## Install", "## 安装"))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def requirements_line(path: Path) -> str:
    """The line of the install section that starts with the bold Requirements label."""
    return next(
        line for line in install_section(path).splitlines() if line.startswith(("**Requirements:**", "**需要**"))
    )


def test_skill_has_the_post_quiz_step():
    t = read(SKILL)
    assert "--phase post" in t
    assert "cards add-misses" in t


def test_step0_uses_cli_only_and_windows_powershell():
    t = read(SKILL)
    for s in ("--cli-only", "-CliOnly", "powershell -NoProfile -ExecutionPolicy Bypass -File"):
        assert s in t


def test_install_docs_never_give_pwsh_alone():
    texts = {"SKILL.md": read(SKILL), "README.md": install_section(README), "README.zh-CN.md": install_section(README_ZH)}
    assert [name for name, text in texts.items() if "pwsh -File" in text] == []
    # The sections are real: each names the Windows installer.
    assert all("install.ps1" in text for text in texts.values())


def test_readmes_name_git_in_requirements():
    for path in (README, README_ZH):
        line = requirements_line(path)
        assert GIT_WORD.search(line), f"{path}: {line}"
        assert "Node.js" in line and "npx skills add" in line


def test_asr_is_described_as_an_add_on():
    t = read(SKILL)
    assert "--with-asr" in t
    assert "-WithAsr" in t


def test_teaching_points_to_third_party_notices():
    t = read(TEACHING)
    assert CARD_NOTICE in t and NOTICES_POINTER in t
    # Right after the attribution line, which stays as it is.
    between = t[t.index(CARD_NOTICE) + len(CARD_NOTICE) : t.index(NOTICES_POINTER)]
    assert between.strip() == ""
    assert Path("THIRD_PARTY_NOTICES.md").is_file()


# ---- task 29: what the first real lecture showed ----

DELIVER_SENTENCE = re.compile(r"\bdeliver (?:the|its) files\b", re.IGNORECASE)


def test_pretest_comes_before_delivery():
    text = read(SKILL)
    # The pretest step: the command that logs a pretest answer, and the H2 that holds it.
    step = text.index("--phase pre --score")
    heading = text.rindex("\n## ", 0, step) + 1
    title = text[heading:text.index("\n", heading)].lower()
    deliver = DELIVER_SENTENCE.search(text)
    assert deliver is not None
    # The heading and the pretest step itself come before the first sentence that delivers the files,
    # and the heading names the pretest before any delivery.
    assert heading < step < deliver.start(), (title, text[deliver.start():deliver.start() + 60])
    assert "pretest" in title
    if "deliver" in title:
        assert title.index("pretest") < title.index("deliver")


def test_documents_name_the_new_flags_and_commands():
    skill, teaching = read(SKILL), read(TEACHING)
    writing = read(SKILL.parent / "references" / "writing.md")
    assert "acquire url --url U --info" in skill
    assert "tutor-any-lecture cite link --unit DIR" in skill and "cite link" in writing
    assert "--date" in skill and "--date" in teaching
    assert "quote_density" in skill and "quote_density" in teaching
    assert "quote_density" in read(SKILL.parent / "references" / "profile.md")
    assert "overview-<view>.mmd" in read(SKILL.parent / "references" / "output-targets" / "markdown.md")
    assert "overview-<view>.mmd" in teaching


def test_docs_leave_the_audio_choice_to_the_learner():
    url_doc = read(SKILL.parent / "references" / "adapters" / "url.md")
    assert "responsibility" in url_doc
    for text in (url_doc, read(SKILL)):
        assert "not downloaded" not in text and "never downloaded" not in text


def test_guardrail_leaves_audio_to_the_learner():
    t = read(SKILL)
    assert "never use the learner's passwords or cookies" in t
    assert "downloads are disabled" not in t
    references = sorted((SKILL.parent / "references").rglob("*"))
    for path in (p for p in references if p.is_file()):
        assert "downloads are disabled" not in read(path), path


def step0_section() -> str:
    """SKILL.md's Step 0: from its heading to the next H2."""
    lines = read(SKILL).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## Step 0"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
    return "\n".join(lines[start:end])


def test_step0_compares_versions_and_names_the_selftest_line():
    step0 = step0_section()
    for s in (
        "doctor --json --skill '<skill folder>'",
        "`skill_version`",
        "second-to-last stdout line",
        "the last stdout line is the selftest command",
    ):
        assert s in step0, s


# ---- the audio rule once; stop when Download is off ----

def guardrails_section() -> list[str]:
    """SKILL.md's Guardrails section, as lines: from its heading to the next H2."""
    lines = read(SKILL).splitlines()
    start = lines.index("## Guardrails")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
    return lines[start + 1:end]


def test_guardrails_state_the_audio_rule_once():
    assert len([line for line in guardrails_section() if "responsibility" in line]) == 1


def test_panopto_stops_when_download_is_off():
    t = read(SKILL.parent / "references" / "adapters" / "panopto.md")
    assert "If Download is greyed out or missing, stop and tell the learner" in t
    assert "ask the learner to download it themselves" in t
    assert "Use it only when the profile's `downloads` allows it" not in t


# ---- unfinished reviews, the d21 lapse, phases for progress log (M2a Task 5) ----


def section(text: str, title: str) -> str:
    """The H2 section ``## <title>`` of ``text``, up to the next H2."""
    start = text.index(f"\n## {title}\n")
    end = text.find("\n## ", start + 1)
    return text[start:] if end < 0 else text[start:end]


def test_documents_name_the_review_rules():
    quiz = section(read(SKILL), "Quiz me and reviews")
    for s in ("items validate --unit DIR", "remaining", "own phase", "progress render --course C [--date YYYY-MM-DD]"):
        assert s in quiz, s
    teaching = read(TEACHING)
    for s in ("--answer TEXT", '"remaining"', "14 days", "progress render --course C [--date YYYY-MM-DD]"):
        assert s in teaching, s
    gate = read(SKILL.parent / "references" / "gate.md")
    (cards_row,) = [line for line in gate.splitlines() if line.startswith("| `cards` |")]
    assert "`concept`" in cards_row


# ---- always run cite link; time forms, quotation marks, the speaker rule ----

REFERENCES = SKILL.parent / "references"
ALWAYS_RUN = "always run `tutor-any-lecture cite link --unit dir`"
NEVER_SAID = (
    "do not run `cite link`",
    "do not run it there",
    "for a unit from a link, run",
    "when the unit came from a link, run",
    "for a unit from a link, `tutor-any-lecture cite link",
)


def test_documents_always_run_cite_link():
    url_doc = REFERENCES / "adapters" / "url.md"
    docs = [SKILL, REFERENCES / "gate.md", REFERENCES / "writing.md", TEACHING, url_doc, REFERENCES / "adapters" / "panopto.md"]
    for path in docs:
        low = read(path).lower()
        for s in NEVER_SAID:
            assert s not in low, (path, s)
    for path in (SKILL, REFERENCES / "gate.md", REFERENCES / "writing.md", TEACHING):
        assert ALWAYS_RUN in read(path).lower(), path
    assert read(url_doc).lower().count(ALWAYS_RUN) >= 2
    assert "`tutor-any-lecture cite link --unit DIR` again" in read(REFERENCES / "gate.md")


def test_writing_names_every_time_link_form():
    from tutor_any_lecture.citations import TIME_LINK_FORMS

    writing = read(REFERENCES / "writing.md")
    for row in TIME_LINK_FORMS:
        assert row.label in writing and f"`{row.written}`" in writing, row


def test_writing_lists_every_quotation_mark_pair():
    from tutor_any_lecture.notecheck import QUOTE_PAIRS

    writing = read(REFERENCES / "writing.md")
    for o, c in QUOTE_PAIRS:
        assert o + "…" + c in writing, (o, c)
    assert "write a title in italics" in writing


def test_writing_states_the_speaker_rule():
    assert "Give a quote to the speaker the transcript names" in read(REFERENCES / "writing.md")


def test_gate_states_what_the_checks_cannot_read():
    gate = read(REFERENCES / "gate.md")
    for phrase in ("not applied for this language", "Thai", "German", "年", "details_shape", "math_form"):
        assert phrase in gate, phrase


def test_writing_has_one_math_rule():
    writing = read(REFERENCES / "writing.md")
    assert "Write math as `$…$` and `$$…$$` only" in writing
    assert "`\\$`" in writing


def test_writing_skeleton_answers_have_blank_lines():
    answer = "   <details><summary>Answer</summary>\n\n   <cited answer>\n\n   </details>"
    assert read(REFERENCES / "writing.md").count(answer) == 2


def test_documents_state_how_cjk_is_read():
    sentence = (
        "In a Chinese, Japanese or Korean deck, the slide terms are the runs of 2 to 10 characters of one script"
        " (Han, katakana or Hangul) between spaces, punctuation and changes of script, hiragana runs left out;"
        " a suspect is a stretch of the transcript as long as a slide term of 4 to 10 characters that differs"
        " from it in one character and is not on the slides, such as 弃权定价 heard for 期权定价."
    )
    assert sentence in read(TEACHING)
    writing = read(REFERENCES / "writing.md")
    assert "Han characters, kana and Hangul syllables" in writing
    assert (
        "The CJK windows were set on Chinese notes; for Japanese and Korean notes they are estimates,"
        " and every length rule is a WARN."
    ) in writing
