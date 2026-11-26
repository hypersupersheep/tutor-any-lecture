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
        "blackboard", "brightspace", "canvas", "echo360", "kaltura", "moodle", "panopto", "teams", "yuja", "zoom"
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
VIDEO = {"echo360", "kaltura", "yuja", "zoom"}
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
        for link in ("panopto.md", "echo360.md", "kaltura.md", "yuja.md", "zoom.md"):
            assert f"({link})" in text, (stem, link)
