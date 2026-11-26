# tests/test_platform_docs.py
"""The platform adapters keep the template, name their profile key, and never ask for a password or cookie."""
import re
from pathlib import Path

import pytest

from tutor_any_lecture.profile import PLATFORM_KEYS

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "skills" / "tutor-any-lecture" / "references" / "adapters"
TEMPLATE = ADAPTERS / "TEMPLATE.md"
PROFILE_DOC = ROOT / "skills" / "tutor-any-lecture" / "references" / "profile.md"
GENERAL = {"TEMPLATE", "import", "local", "url", "photos"}

STAY = (
    "Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in "
    "when they sign in, so the agent stops at sign-in pages less often."
)
PWM = (
    "If the agent is connected to a password manager that asks the learner to confirm each item it fills, "
    "the learner may let it fill the sign-in; the agent never sees, types or stores the password."
)


# ---- local helpers ----

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def all_adapters() -> list[Path]:
    return sorted(ADAPTERS.glob("*.md"))


def platform_adapters() -> list[Path]:
    return [p for p in all_adapters() if p.stem not in GENERAL]


def new_adapters() -> list[Path]:
    return [p for p in platform_adapters() if p.stem not in {"moodle", "panopto"}]


def h2_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("## ")]


def before_first_h2(text: str) -> str:
    lines = text.splitlines()
    end = next(i for i, line in enumerate(lines) if line.startswith("## "))
    return "\n".join(lines[:end])


def h2_section(text: str, heading: str) -> str:
    """The lines after ``## <heading>`` up to the next ``## `` line, heading left out."""
    lines = text.splitlines()
    start = lines.index(f"## {heading}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start + 1:end])


def after_last_h2(text: str) -> str:
    lines = text.splitlines()
    last = max(i for i, line in enumerate(lines) if line.startswith("## "))
    return "\n".join(lines[last + 1:])


SENSITIVE = re.compile(r"password|cookie|credential|passcode", re.IGNORECASE)
NEGATION = re.compile(r"\b(never|not|no|without)\b|n't", re.IGNORECASE)


def sentences(text: str) -> list[str]:
    """Pieces of each line, split at whitespace that follows ., ! or ?."""
    return [s for line in text.splitlines() for s in re.split(r"(?<=[.!?])\s+", line) if s]


def password_or_cookie_instructions(text: str) -> list[str]:
    """Sentences that name a password, cookie, credential or passcode without a negation."""
    return [s for s in sentences(text) if SENSITIVE.search(s) and not NEGATION.search(s)]


# ---- A1. the template's headings, and whether it was verified ----

@pytest.mark.parametrize("path", [p for p in all_adapters() if p != TEMPLATE], ids=lambda p: p.name)
def test_every_adapter_keeps_the_template_headings(path):
    template = h2_lines(read(TEMPLATE))
    assert len(template) == 7
    assert h2_lines(read(path)) == template


@pytest.mark.parametrize("path", [p for p in all_adapters() if p != TEMPLATE], ids=lambda p: p.name)
def test_every_adapter_says_whether_it_was_verified(path):
    assert "experimental" in after_last_h2(read(path)).casefold()


# ---- A2. a platform's name is its file name and its profile key ----

def test_platform_keys_are_the_platform_adapters():
    stems = [p.stem for p in platform_adapters()]
    assert set(PLATFORM_KEYS) == set(stems)
    assert list(PLATFORM_KEYS) == sorted(PLATFORM_KEYS)
    for path in platform_adapters():
        assert re.fullmatch(r"[a-z][a-z0-9]*", path.stem), path.name
        first = read(path).splitlines()[0]
        assert "`platforms`" in first and f"`{path.stem}`" in first, path.name
    bullet = next(line for line in read(PROFILE_DOC).splitlines() if line.startswith("  - for `platforms`"))
    for key in PLATFORM_KEYS:
        assert f"`{key}`" in bullet, key


def test_template_says_how_a_platform_is_named():
    head = before_first_h2(read(TEMPLATE))
    for s in ("**Naming.**", "PLATFORM_KEYS", "tests/test_platform_docs.py", "<canvas_url>", "adds no new command"):
        assert s in head, s


# ---- A4. what a helper script may do ----

def test_template_says_what_a_helper_script_may_do():
    head = before_first_h2(read(TEMPLATE))
    for s in ("**Helper scripts.**", "scripts/<platform>_extract.js", "fetch", "document.cookie", '{"segments"',
              "`.json`", "acquire import --file F --unit DIR", "Without such a script"):
        assert s in head, s


# ---- A5. sign-in advice in every browser adapter ----

def test_browser_adapters_hold_the_sign_in_advice():
    for path in [TEMPLATE, ADAPTERS / "moodle.md", ADAPTERS / "panopto.md"] + new_adapters():
        text = read(path)
        assert STAY in text and PWM in text, path.name
    for path in new_adapters():
        steps = h2_section(read(path), "Read-only steps")
        assert STAY in steps and PWM in steps, path.name


# ---- A6. no adapter asks for a password or a cookie ----

@pytest.mark.parametrize("path", all_adapters(), ids=lambda p: p.name)
def test_no_adapter_asks_for_a_password_or_cookie(path):
    assert password_or_cookie_instructions(read(path)) == []


def test_the_password_check_catches_instructions():
    for bad in ("Ask the learner for their password.", "Paste the session cookie into the command.",
                "Type the Zoom passcode for them."):
        assert password_or_cookie_instructions(bad) == [bad]
    for good in ("Never type a password.", "The tool uses no cookies.", PWM):
        assert password_or_cookie_instructions(good) == []


# ---- A3. the profile accepts every platform key ----

def test_profile_accepts_every_platform_key(tmp_cfg):
    from tutor_any_lecture.profile import set_value

    assert PLATFORM_KEYS == (
        "blackboard", "brightspace", "canvas", "chaoxing", "coursera", "echo360", "edx", "icourse163", "kaltura",
        "moodle", "panopto", "teams", "xuetangx", "yuketang", "zoom"
    )
    profile = set_value("platforms", "{" + ", ".join(f"{k}: https://{k}.example.org" for k in PLATFORM_KEYS) + "}")
    assert profile.platforms == {k: f"https://{k}.example.org" for k in PLATFORM_KEYS}


def test_an_unknown_platform_names_the_allowed_keys(tmp_cfg):
    from tutor_any_lecture.profile import ProfileError, set_value

    with pytest.raises(ProfileError) as caught:
        set_value("platforms", "{videosite: https://example.org}")
    assert str(caught.value) == "platforms: 'videosite' is not allowed; allowed keys: " + ", ".join(PLATFORM_KEYS)


# ---- A7. each new adapter fills the template the same way ----

LMS = {"canvas", "blackboard", "brightspace"}
COURSE_SITES = ("coursera", "edx", "icourse163", "xuetangx", "yuketang", "chaoxing")
VIDEO = {"echo360", "kaltura", "zoom"} | set(COURSE_SITES)
MEETING = {"zoom", "teams"}
DOES_NOT_DOWNLOAD = (
    "This adapter does not download the recording; it reads a caption or transcript file the platform lets the "
    "learner save."
)
AGENT_SPECIFIC = ["javascript_tool", "Claude in Chrome", "mcp__"]
FENCE_LINE = re.compile(r"^\s*(`{3}|~{3})")


def adapter(stem: str) -> str:
    return read(ADAPTERS / f"{stem}.md")


@pytest.mark.parametrize("path", new_adapters(), ids=lambda p: p.name)
def test_new_adapters_fill_the_template(path):
    text = read(path)
    lines = text.splitlines()
    assert lines[0].startswith("Adapter: ") and "../agents/" in lines[0]
    assert re.search(r"`tutor-any-lecture [^`]+`", h2_section(text, "Platform"))
    where = h2_section(text, "Where transcripts/captions live")
    assert any(line.startswith("When there is none:") for line in where.splitlines())
    assert "[import](import.md)" in where and "acquire import --file F --unit DIR" in where
    steps = h2_section(text, "Read-only steps")
    assert any(line.startswith("1. ") for line in steps.splitlines())
    assert "stop and ask the learner to sign in" in steps
    downloads = h2_section(text, 'Downloads offered?')
    for s in ("`downloads`", "DRM", DOES_NOT_DOWNLOAD):
        assert s in downloads, s
    if path.stem not in LMS:
        assert "public_video_audio" in downloads and "url.md" in downloads
    pitfalls = h2_section(text, "Known pitfalls")
    assert len([line for line in pitfalls.splitlines() if line.startswith("- ")]) >= 2
    assert len(lines) <= 60
    assert "![" not in text
    assert not any(FENCE_LINE.match(line) for line in lines)
    for word in AGENT_SPECIFIC + ["downloads are disabled"]:
        assert word not in text, word


# ---- A8. experimental, and the pages it was written from ----

CITATION = re.compile(r"^- \[[^\]]+\]\((https://[^)\s]+)\)$")
INSTITUTION_ENDINGS = (".edu", ".ac.uk", ".edu.cn", ".edu.au", ".ac.jp", ".edu.hk", ".ac.nz", ".edu.sg")


def verified_section(text: str) -> list[str]:
    return [line for line in h2_section(text, 'Verified by (name/date) or "experimental"').splitlines() if line.strip()]


@pytest.mark.parametrize("path", new_adapters(), ids=lambda p: p.name)
def test_new_adapters_are_experimental_and_cite_their_sources(path):
    lines = verified_section(read(path))
    assert lines[0] == "experimental"
    assert re.fullmatch(
        r"Written from public documentation read on [0-9]{4}-[0-9]{2}-[0-9]{2}; not yet run on a real lecture:", lines[1]
    )
    assert [line for line in lines[2:] if CITATION.match(line)]


@pytest.mark.parametrize("path", new_adapters(), ids=lambda p: p.name)
def test_cited_pages_are_not_institution_pages(path):
    hosts = [re.match(r"https://([^/?#]+)", m.group(1)).group(1).lower()
             for m in map(CITATION.match, verified_section(read(path))) if m]
    assert hosts
    assert [h for h in hosts if h.endswith(INSTITUTION_ENDINGS)] == []


# ---- A10. a public link is tried with acquire url --info first ----

def test_video_adapters_try_the_link_first():
    for stem in sorted(VIDEO):
        text = adapter(stem)
        assert "acquire url --url U --info" in text and "(url.md)" in text, stem


# ---- A11. where each kind of platform hands over ----

def test_meeting_players_hand_over_transcript_files():
    for stem in sorted(MEETING):
        text = adapter(stem)
        assert "acquire import --file F --unit DIR" in text and "(import.md)" in text, stem


def test_learning_platforms_hand_over_slides_and_recordings():
    for stem in sorted(LMS):
        text = adapter(stem)
        assert "slides --pdf F --unit DIR" in text, stem
        for link in ("panopto.md", "echo360.md", "kaltura.md", "zoom.md"):
            assert f"({link})" in text, (stem, link)


# ---- B2. the course sites ----

CHINESE_FIRST = {
    "icourse163": "Adapter: 中国大学MOOC (icourse163).",
    "xuetangx": "Adapter: 学堂在线 (xuetangx).",
    "yuketang": "Adapter: 雨课堂 (yuketang).",
    "chaoxing": "Adapter: 学习通 (chaoxing).",
}
FIXED_ADDRESS = (
    "A site whose address is the same for everyone writes it in full; its `platforms` value is optional and, "
    "when set, replaces that address."
)


def test_course_sites_have_adapters():
    for stem in COURSE_SITES:
        assert (ADAPTERS / f"{stem}.md").is_file(), stem
        assert stem in PLATFORM_KEYS, stem


def test_chinese_platform_adapters_name_both_names():
    for stem, expected in CHINESE_FIRST.items():
        first = adapter(stem).splitlines()[0]
        # up to and including the first full stop that is followed by a space
        assert first[: first.index(". ") + 1] == expected, stem


@pytest.mark.parametrize("path", new_adapters(), ids=lambda p: p.name)
def test_url_patterns_name_a_placeholder_or_the_vendor_site(path):
    patterns = h2_section(read(path), "URL patterns")
    assert f"<{path.stem}_url>" in patterns or "https://" in patterns
    assert "<course_id>" not in patterns


def test_template_says_a_fixed_address_is_written_in_full():
    assert FIXED_ADDRESS in before_first_h2(read(TEMPLATE))


# ---- A12. the documents point to the new adapters ----

def faq_answer(text: str, question: str) -> str:
    lines = text.splitlines()
    start = lines.index(f"### {question}")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("#"))
    return "\n".join(lines[start + 1:end])


def test_documents_point_to_the_new_adapters():
    skill = read(ROOT / "skills" / "tutor-any-lecture" / "SKILL.md")
    assert "`references/adapters/<platform>.md`" in skill
    assert (
        "a page on Canvas, Blackboard, Brightspace, Echo360, Kaltura, Zoom, Teams, Coursera, edX or a Chinese course "
        "platform (icourse163, xuetangx, yuketang, chaoxing): its experimental adapter"
    ) in skill
    assert "Pages read in a browser (Panopto, Moodle and the platforms above)" in skill
    readme, readme_zh = read(ROOT / "README.md"), read(ROOT / "README.zh-CN.md")
    assert (
        "Experimental adapters, written from public documentation and not yet run on a real lecture, describe "
        "Canvas, Blackboard, Brightspace, Echo360, Kaltura, Zoom, Teams/Stream, Coursera, edX, 中国大学MOOC, 学堂在线, "
        "雨课堂 and 学习通."
    ) in faq_answer(readme, "Which sources can it read?")
    assert (
        "实验性的 adapter 按公开文档写成,还没在真实的课上跑过,覆盖 Canvas、Blackboard、Brightspace、Echo360、Kaltura、"
        "Zoom、Teams/Stream、Coursera、edX、中国大学MOOC、学堂在线、雨课堂和学习通。"
    ) in faq_answer(readme_zh, "能读哪些材料?")
    agents = faq_answer(readme, "Which agents does it work with?")
    assert (
        "Browser tools are needed only for pages read in a browser: Panopto, Moodle and the platforms of the "
        "experimental adapters."
    ) in agents
    assert "only for Panopto and Moodle pages" not in agents
    agents_zh = faq_answer(readme_zh, "支持哪些 agent?")
    assert "只有在浏览器里读的页面需要浏览器工具:Panopto、Moodle,以及实验性 adapter 里的平台。" in agents_zh
    assert "只有 Panopto 和 Moodle 页面" not in agents_zh
    changelog = read(ROOT / "CHANGELOG.md").split("\n## ")[1]
    bullet = next(line for line in changelog.splitlines() if line.startswith("- Start from what you have:"))
    assert bullet.endswith(
        "Experimental adapters, written from public documentation, describe Canvas, Blackboard, Brightspace, "
        "Echo360, Kaltura, Zoom, Teams/Stream, Coursera, edX, 中国大学MOOC, 学堂在线, 雨课堂 and 学习通."
    )
    url_doc = read(ADAPTERS / "url.md")
    assert "their experimental adapters" in url_doc
    pitfall = next(line for line in url_doc.splitlines() if line.startswith("- A video that needs a login"))
    assert pitfall.endswith("On Coursera, edX and the Chinese course platforms, follow their experimental adapters.")
    contributing = read(ROOT / "CONTRIBUTING.md")
    for s in ("PLATFORM_KEYS", "tests/test_platform_docs.py", "helper script"):
        assert s in contributing, s
