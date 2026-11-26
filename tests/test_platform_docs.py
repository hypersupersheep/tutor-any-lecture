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
