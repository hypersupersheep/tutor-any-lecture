# tests/test_public_docs.py
"""The public documents say what this version does, in both languages, and name only real paths."""
import re
from pathlib import Path

import pytest

from tutor_any_lecture.config import config_dir

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
READMES = [README, README_ZH]
PUBLIC_DOCS = READMES
SAMPLE_NOTE = ROOT / "src" / "tutor_any_lecture" / "data" / "sample" / "explanation.md"

POSITION = {
    README: "A tutor built from your own lectures: it tests you, cites the lecturer, schedules your review.",
    README_ZH: "用你自己的课做成的家教:它考你,引用老师的原话,替你安排复习。",
}
SUBTITLE = {
    README: (
        "It quizzes you first, explains the lecture in the lecturer's own words, cites the minute and the slide, "
        "quizzes you again, and sends your misses to Anki."
    ),
    README_ZH: "先考你,再按老师原话讲,标到分钟和课件页,讲完再考,错题进 Anki。",
}
OTHER_LANGUAGE_LINK = {README: "[简体中文](README.zh-CN.md)", README_ZH: "[English](README.md)"}

H2_EN = [
    "What one lecture becomes",
    "A look at the bundled sample",
    "How it works",
    "Install",
    "Quick start",
    "What to ask",
    "Optional extras",
    "Safety and privacy",
    "FAQ",
    "Upgrading and removing",
    "Contributing",
    "Acknowledgements",
    "License",
]
H2_ZH = [
    "一节课会变成什么",
    "内置样例节选",
    "工作流程",
    "安装",
    "快速开始",
    "怎么提要求",
    "可选的附加产出",
    "安全和隐私",
    "常见问题",
    "升级和卸载",
    "参与贡献",
    "致谢",
    "许可",
]
H2 = {README: H2_EN, README_ZH: H2_ZH}

INSTALL_ROUTES = {
    README: [
        "A. npx skills add (recommended)",
        "B. Claude Code plugin",
        "C. Ask your agent to install it",
        "D. Claude.ai upload",
    ],
    README_ZH: [
        "方式一:npx skills add(推荐)",
        "方式二:Claude Code 插件",
        "方式三:让 agent 替你安装",
        "方式四:Claude 网页版上传",
    ],
}
FAQ = {
    README: [
        "Which agents does it work with?",
        "Which sources can it read?",
        "Does anything leave my computer?",
        "Can the notes be in English, or another language?",
        "Do I need a Mac?",
        "How do I get the cards into Anki?",
        "When are reviews due?",
        "Can I turn the quiz off?",
        "What does Windows need?",
    ],
    README_ZH: [
        "支持哪些 agent?",
        "能读哪些材料?",
        "有什么会离开我的电脑?",
        "笔记能用英文或别的语言写吗?",
        "一定要 Mac 吗?",
        "卡片怎么导入 Anki?",
        "复习什么时候到期?",
        "能关掉测验吗?",
        "Windows 需要什么?",
    ],
}
COMMAND_PREFIXES = ("tutor-any-lecture", "npx", "/plugin", "bash", "powershell", "git", "uv")
PATH_PREFIXES = ("skills/", "src/", "tests/", "tools/", ".github/", ".claude-plugin/")
ROOT_FILES = {
    "install.sh", "install.ps1", "pyproject.toml", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md",
    "SECURITY.md", "THIRD_PARTY_NOTICES.md", "README.md", "README.zh-CN.md",
}
V1_LEFTOVERS = [
    "note_stats", "writing-rules.md", "quotes.md", "lecture-tutor", "lecture_wN", "Dublin cobbler",
    "Claude Code skills", "any recording, every time", "come out in Chinese", "笔记用中文写",
]
TEMPLATE_TRACES = ["·", "→", "shields.io", "<img", "<picture", "!["]


# ---- local helpers ----

def read(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def h2_of(path: Path, name: str) -> str:
    """The H2 of `path` for the English section name `name` (its Chinese twin in README.zh-CN.md)."""
    return H2[path][H2_EN.index(name)] if path == README_ZH else name


def section(path: Path, name: str) -> str:
    """The section of a README under the H2 `name` (given in English), up to the next H2."""
    lines = read(path).splitlines()
    heading = "## " + h2_of(path, name)
    start = lines.index(heading)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start + 1:end])


def h3s(text: str) -> list[str]:
    return [line[4:].strip() for line in text.splitlines() if line.startswith("### ")]


LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\s]+)\)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def relative_links(text: str) -> list[str]:
    """Targets of Markdown links [text](target) that are not URLs, anchors or absolute paths; #fragments dropped."""
    out = []
    for target in LINK.findall(text):
        target = target.split("#", 1)[0]
        if not target or SCHEME.match(target) or target.startswith(("/", "\\", "~")):
            continue
        out.append(target)
    return out


CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^\s*(`{3}|~{3})")  # a line opening or closing a fenced block


def code_texts(text: str) -> list[str]:
    """Inline code spans outside fences, every line inside fenced blocks, and the code spans on those lines."""
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(line)
        out.extend(CODE_SPAN.findall(line))
    return out


def code_spans(text: str) -> list[str]:
    """Every inline code span, on fenced lines too (fence markers themselves skipped)."""
    return [s for line in text.splitlines() if not FENCE.match(line) for s in CODE_SPAN.findall(line)]


def commands(text: str) -> set[str]:
    """Fenced lines and code spans, stripped, that start with a command name."""
    return {t.strip() for t in code_texts(text) if t.strip().startswith(COMMAND_PREFIXES)}


def named_paths(text: str) -> list[str]:
    """Code spans that name a repository path: a known top folder, or a root file name."""
    return [s for s in code_spans(text) if s.startswith(PATH_PREFIXES) or s in ROOT_FILES]


def path_exists(name: str) -> bool:
    target = ROOT / name
    return target.is_dir() if name.endswith("/") else target.exists()


def blockquote_lines(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        if line.startswith(">"):
            body = line[1:]
            body = body[1:] if body.startswith(" ") else body
            if body.strip():
                out.append(body)
    return out


def table_rows(text: str) -> list[str]:
    """Table lines of a section, less its header and separator."""
    rows = [line for line in text.splitlines() if line.startswith("|")]
    return rows[2:]


def all_caps_heading(line: str) -> bool:
    """A heading of two or more words in which every word that holds a letter is in capitals."""
    words = [w for w in line.lstrip("#").split() if any(c.lower() != c.upper() for c in w)]
    return len(words) >= 2 and all(w == w.upper() for w in words)


def denylist_terms() -> list[str]:
    denylist = config_dir() / "denylist.txt"
    if not denylist.exists():
        pytest.skip(f"no denylist at {denylist}")
    terms = [s.strip() for s in read(denylist).splitlines()]
    terms = [t for t in terms if t and not t.startswith("#")]
    return [t[:-1] if t.endswith("*") else t for t in terms]


# ---- R1. sections and the first screen ----

@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_readme_sections_in_order(path):
    assert [line[3:] for line in read(path).splitlines() if line.startswith("## ")] == H2[path]


@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_readme_first_screen(path):
    lines = read(path).splitlines()
    assert lines[0] == "# Tutor Any Lecture"
    assert f"**{POSITION[path]}**" in lines[:8]
    assert SUBTITLE[path] in lines[:8]
    assert any(OTHER_LANGUAGE_LINK[path] in line for line in lines[:8])


def test_readmes_have_the_same_subsections():
    counts = {name: [len(h3s(section(p, name))) for p in READMES] for name in H2_EN}
    assert all(en == zh for en, zh in counts.values()), counts
    assert counts["Install"] == [4, 4]
    assert counts["FAQ"] == [9, 9]
    assert counts["Upgrading and removing"] == [2, 2]


# ---- R2. what one lecture becomes, and the sample ----

@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_readme_outputs_name_the_unit_files(path):
    text = section(path, "What one lecture becomes")
    for s in ("explanation.md", "items.json", "assignment.json", "cards.tsv", "map.json", "overview.mmd",
              "verify.json", "<course>.jsonl", "note_language"):
        assert s in text, s


def test_readme_excerpt_comes_from_the_bundled_sample():
    sample_lines = set(read(SAMPLE_NOTE).splitlines())
    excerpts = []
    for path, word in ((README, "synthetic"), (README_ZH, "合成")):
        text = section(path, "A look at the bundled sample")
        quoted = blockquote_lines(text)
        assert len(quoted) >= 2
        assert [line for line in quoted if line not in sample_lines] == []
        assert word in text
        excerpts.append(quoted)
    assert excerpts[0] == excerpts[1]


# ---- R3. how it works, and what to ask ----

@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_readme_how_it_works_names_the_gate(path):
    text = section(path, "How it works")
    assert len([line for line in text.splitlines() if re.match(r"^\d+\. ", line)]) == 8
    assert "tutor-any-lecture verify --unit DIR" in text
    assert "skills/tutor-any-lecture/references/gate.md" in relative_links(text)


@pytest.mark.parametrize("path, word", [(README, "experimental"), (README_ZH, "实验性")], ids=["en", "zh"])
def test_readme_requests_table_has_nine_rows(path, word):
    text = section(path, "What to ask")
    rows = table_rows(text)
    assert len(rows) == 9
    assert [r for r in rows if "experimental" in r or "实验性" in r] == []
    assert word in text


# ---- R4. install and quick start ----

@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_install_routes_in_spec_order(path):
    assert h3s(section(path, "Install")) == INSTALL_ROUTES[path]


@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_readme_quick_start_runs_selftest(path):
    assert "tutor-any-lecture selftest" in section(path, "Quick start")


# ---- R5. optional extras ----

@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_readme_extras_say_what_they_need(path):
    text = section(path, "Optional extras")
    for s in ("skills/tutor-any-lecture/scripts/tts_synthesize.py", "skills/handwritten-notes-pdf/",
              "skills/excalidraw-concept-map/", "mlx-audio", "websocket-client", "CHROME_PATH"):
        assert s in text, s
    assert "does not copy" in text or "不会复制" in text


# ---- R6. safety and privacy ----

@pytest.mark.parametrize("path, word", [(README, "telemetry"), (README_ZH, "遥测")], ids=["en", "zh"])
def test_readme_safety_states_the_settings(path, word):
    text = section(path, "Safety and privacy")
    for s in ("`downloads`", "`ask`", "`allow`", "`public_video_audio`", word, "agent"):
        assert s in text, s


# ---- R7. FAQ ----

@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_faq_questions(path):
    assert h3s(section(path, "FAQ")) == FAQ[path]


# ---- R8. upgrading and removing ----

@pytest.mark.parametrize("path", READMES, ids=lambda p: p.name)
def test_readme_upgrading_and_removing(path):
    text = section(path, "Upgrading and removing")
    for s in ("git pull", "--cli-only", "uv tool uninstall tutor-any-lecture", "~/.tutor-any-lecture", "cli-path",
              "~/.claude/skills/tutor-any-lecture", "~/TutorAnyLecture"):
        assert s in text, s


# ---- T1. the same commands in both READMEs ----

def test_readmes_show_the_same_commands():
    en, zh = commands(read(README)), commands(read(README_ZH))
    assert en == zh, (sorted(en - zh), sorted(zh - en))
    assert len(en) >= 10


# ---- T2. every path a public doc names exists ----

def test_public_docs_name_only_existing_paths():
    missing = []
    for doc in PUBLIC_DOCS:
        text = read(doc)
        missing += [(doc.name, t) for t in relative_links(text) if not (doc.parent / t).exists()]
        missing += [(doc.name, p) for p in named_paths(text) if not path_exists(p)]
    assert missing == []
    checked = relative_links(read(README)) + named_paths(read(README))
    assert len(checked) >= 8
    github_docs = [d for d in PUBLIC_DOCS if d.parent.name == ".github" or d.parent.parent.name == ".github"]
    assert [(d.name, relative_links(read(d))) for d in github_docs if relative_links(read(d))] == []


def test_v1_showcase_is_gone():
    left = [p for d in ("assets", "examples") for p in (ROOT / d).rglob("*")
            if p.is_file() and p.name != ".DS_Store"]
    assert left == []


# ---- T3. no v1 leftover, no template trace, no private term ----

def test_public_docs_hold_no_v1_leftovers():
    found = [(d.name, s) for d in PUBLIC_DOCS for s in V1_LEFTOVERS if s in read(d)]
    assert found == []


def test_public_docs_avoid_template_traces():
    found = []
    for doc in PUBLIC_DOCS:
        text = read(doc)
        found += [(doc.name, s) for s in TEMPLATE_TRACES if s in text]
        if "d97757" in text.lower():
            found.append((doc.name, "D97757"))
        found += [(doc.name, line) for line in text.splitlines() if line.startswith("#") and all_caps_heading(line)]
    assert found == []


def test_public_docs_hold_no_private_terms():
    terms = [t.casefold() for t in denylist_terms()]
    docs = list(PUBLIC_DOCS) + [ROOT / "CHANGELOG.md"]
    hits = [(d.name, i) for d in docs for i, t in enumerate(terms) if t and t in read(d).casefold()]
    # Report the term's position in the list only, never the term itself.
    assert hits == []


def test_template_trace_helpers_catch_what_they_must():
    assert all_caps_heading("## WHAT IT DOES")
    assert not all_caps_heading("## FAQ")
    assert not all_caps_heading("### A. npx skills add (recommended)")
    assert not all_caps_heading("## 一节课会变成什么")
    assert blockquote_lines("> one\n>\n> two\ntext") == ["one", "two"]
    assert commands("```text\nrun `bash install.sh --yes` now\n```") == {"bash install.sh --yes"}
