"""Readiness checks: is this machine ready to run tutor-any-lecture?

Each check is a small function listed in ``CHECKS``. ``run_doctor`` runs them in order
and never raises: a check that raises is reported as not ok. Dependencies (``asr``,
``ffmpeg``, ``config``, ``yt_dlp``, the ASR backends) are imported inside the check that
needs them, so the report still comes out when one of them is missing. No check makes a
network call, downloads anything, starts a browser or runs ffmpeg.
"""

from __future__ import annotations

import hashlib
import os
import platform
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__


@dataclass(frozen=True)
class Check:
    name: str
    required: bool
    fn: Callable[[], tuple]  # returns (ok, detail) or (ok, detail, fix); may raise
    fix: str                 # one line; what to do when the check is not ok (unless fn gives one)


# --- helpers ----------------------------------------------------------------------

_VERSION_RE = re.compile(r"(\d+)\.(\d+)")


def _version_of(text: str) -> tuple[int, int] | None:
    """The first ``major.minor`` in ``text``, or None."""
    m = _VERSION_RE.search(text)
    if m is None:
        return None
    return int(m.group(1)), int(m.group(2))


def _tool_version(name: str) -> tuple[int, int] | None:
    """The version that ``<name> --version`` prints, or None when the program is not on PATH."""
    exe = shutil.which(name)
    if exe is None:
        return None
    try:
        proc = subprocess.run([exe, "--version"], stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return _version_of(proc.stdout.decode("utf-8", errors="replace"))


def _browser_candidates() -> list[str]:
    """Default Chromium-family browsers to try on this OS (CHROME_PATH not included).

    macOS: app-bundle paths, always with forward slashes whatever the host. Windows:
    ``.exe`` paths under the program-files folders. Linux: bare command names, looked up
    on PATH by ``check_browser``.
    """
    if sys.platform == "darwin":
        apps = [
            "Google Chrome.app/Contents/MacOS/Google Chrome",
            "Chromium.app/Contents/MacOS/Chromium",
            "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
        roots = ["/Applications", os.path.expanduser("~/Applications")]
        return [posixpath.join(root, app) for root in roots for app in apps]
    if sys.platform == "win32":
        exes = [
            r"Google\Chrome\Application\chrome.exe",
            r"Chromium\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe",
        ]
        roots = [os.environ.get(v) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        return [str(Path(root) / exe) for root in roots if root for exe in exes]
    # Command names, looked up on PATH by check_browser.
    return [
        "google-chrome", "google-chrome-stable", "chromium",
        "chromium-browser", "microsoft-edge", "microsoft-edge-stable",
    ]


def _find_browser(candidate: str) -> str | None:
    """A bare command name is looked up on PATH; anything else must be an existing file."""
    if os.path.basename(candidate) == candidate:
        return shutil.which(candidate)
    return candidate if Path(candidate).is_file() else None


class _BrokenPackage(Exception):
    """A package is installed (find_spec locates it) but importing it raises."""

    def __init__(self, package: str, error: Exception) -> None:
        super().__init__(f"{package} is installed but cannot be imported: {type(error).__name__}: {error}")
        self.package = package


def _model_cached(backend: str, model: str) -> bool:
    """``asr.model_cached``, with a package that is installed but fails to import
    reported as ``_BrokenPackage``. Never downloads.
    """
    from . import asr

    try:
        return asr.model_cached(backend, model)
    except Exception as e:
        raise _BrokenPackage(asr.CACHE_LOOKUP[backend][0], e) from e


# --- the checks -------------------------------------------------------------------

def check_python() -> tuple[bool, str]:
    return sys.version_info >= (3, 10), platform.python_version()


def check_ffmpeg() -> tuple[bool, str]:
    from . import ffmpeg

    p = ffmpeg.ffmpeg_exe()
    return bool(p), p or "not found"


def check_asr_backend() -> tuple[bool, str]:
    # select_backend probes with find_spec; it never imports a backend (mlx may abort on import).
    from . import asr

    backend = asr.select_backend()
    return True, f"{backend} (device: {asr.select_device(backend)})"


def check_yt_dlp() -> tuple[bool, str]:
    import yt_dlp

    return True, yt_dlp.version.__version__


def check_config_dir() -> tuple[bool, str]:
    from .config import config_dir

    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    fd, probe = tempfile.mkstemp(dir=d)
    os.close(fd)
    os.remove(probe)
    return True, str(d)


_JS_MINIMUMS = (("deno", (2, 3)), ("node", (22, 0)))


def check_js_runtime() -> tuple[bool, str]:
    found = []
    for name, minimum in _JS_MINIMUMS:
        v = _tool_version(name)
        if v is None:
            continue
        if v >= minimum:
            return True, f"{name} {v[0]}.{v[1]}"
        found.append(f"{name} {v[0]}.{v[1]}")
    if found:
        return False, ", ".join(found) + " (need deno >= 2.3 or node >= 22)"
    return False, "deno and node not found"


def check_browser() -> tuple[bool, str]:
    candidates = []
    chrome_path = os.environ.get("CHROME_PATH")
    if chrome_path:
        candidates.append(chrome_path)
    candidates.extend(_browser_candidates())
    for p in candidates:
        found = _find_browser(p)
        if found:
            return True, found
    return False, "not found"


def check_asr_model() -> tuple:
    from . import asr

    backend = asr.select_backend()
    model = asr.select_model(backend)
    try:
        cached = _model_cached(backend, model)
    except _BrokenPackage as e:
        return False, str(e), f"Optional: reinstall {e.package}"
    if cached:
        return True, model
    # A backend is installed; only its model is missing, and that needs no installer.
    return False, f"{model} is not cached", _MODEL_FIX


def check_command() -> tuple[bool, str]:
    """Reachable the way SKILL.md calls it: the bare name on PATH, else the path in cli-path."""
    from .config import config_dir

    found = shutil.which("tutor-any-lecture")
    if found:
        return True, f"on PATH: {found}"
    record = config_dir() / "cli-path"
    if not record.is_file():
        return False, f"not on PATH and no {record}"
    lines = record.read_text(encoding="utf-8").splitlines()
    path = lines[0].strip() if lines else ""
    if not path:
        return False, "cli-path is empty"
    if Path(path).is_file():
        return True, f"cli-path: {path}"
    return False, f"cli-path names {path}, which does not exist"


# A release id (the skill's VERSION): X.Y.Z, X.Y.Z-dev.N or X.Y.Z-rc.N, no leading zeros.
_NUM = r"(0|[1-9][0-9]*)"
_RELEASE_ID_RE = re.compile(rf"{_NUM}\.{_NUM}\.{_NUM}(?:-(dev|rc)\.{_NUM})?")


def _pep440(release_id: str) -> str | None:
    """The PEP 440 twin of a release id (X.Y.Z-dev.N -> X.Y.Z.devN, X.Y.Z-rc.N -> X.Y.ZrcN),
    or None when ``release_id`` is not one."""
    m = _RELEASE_ID_RE.fullmatch(release_id)
    if m is None:
        return None
    base = ".".join(m.group(1, 2, 3))
    if m.group(4) is None:
        return base
    return f"{base}.dev{m.group(5)}" if m.group(4) == "dev" else f"{base}rc{m.group(5)}"


# The skill folder that ``run_doctor`` was given, for the length of that call only.
_skill: Path | None = None


def check_skill_version() -> tuple[bool, str]:
    """Do this command and the skill folder that calls it carry the same release?"""
    skill = _skill
    if skill is None:
        return True, "not compared (pass --skill <skill folder>)"
    version_file = skill / "VERSION"
    if not version_file.is_file():
        return False, f"no VERSION file in {skill}"
    release_id = version_file.read_text(encoding="utf-8").strip()
    twin = _pep440(release_id)
    # __version__ is looked up at call time, so a test can patch it.
    if release_id == __version__ or (twin is not None and twin == __version__):
        return True, f"{release_id} (command {__version__})"
    if twin is not None:
        return False, f"skill {release_id}, command {__version__}"
    return False, f"VERSION holds '{release_id}', which is not a release id"


# The SHA-256 of the one word shown in the skill's assets/vision-probe.png, casefolded and
# UTF-8 encoded. Only the digest is kept, so no file holds the word an agent could read
# instead of the image.
VISION_PROBE_SHA256 = "33f38545e00a507fba8be0243f5d19ee24dac952e6664422f91c32df2c63ff0b"

# The word the agent read in the probe image, given to ``run_doctor``, for the length of that call only.
_vision_word: str | None = None


def check_vision() -> tuple[bool, str]:
    """Can the agent that runs this command read images? It says by the word it read in the probe."""
    word = _vision_word
    if word is None:
        return True, "not checked (pass --vision-word WORD)"
    shown = word.strip()
    # VISION_PROBE_SHA256 is looked up at call time, so a test can patch it.
    if hashlib.sha256(shown.casefold().encode("utf-8")).hexdigest() == VISION_PROBE_SHA256:
        return True, "the word in the probe image was read"
    return False, f"'{shown}' is not the word in the probe image"


# Speech recognition is an optional extra: a machine without it is still ready.
_ASR_FIX = (
    "Optional: needed only for audio or video without captions. "
    "Run the installer again with --with-asr (Windows: -WithAsr)."
)
_MODEL_FIX = "Optional: the model downloads once, on the first transcription."
_COMMAND_FIX = "Optional: run the installer again; it records the command's full path in cli-path."
_SKILL_FIX = (
    "Optional: the command and this skill differ; "
    "reinstall the command with the skill's installer and --cli-only (Windows: -CliOnly)."
)
VISION_FIX = (
    "Optional: this agent cannot read images, so photos of slides cannot be used; ask for the slides as a PDF."
)

CHECKS: list[Check] = [
    Check("python", True, check_python,
          "Install Python 3.10 or newer and reinstall tutor-any-lecture with it."),
    Check("ffmpeg", True, check_ffmpeg,
          "Reinstall tutor-any-lecture (imageio-ffmpeg bundles ffmpeg), or install ffmpeg and put it on PATH."),
    Check("yt_dlp", True, check_yt_dlp,
          "Reinstall tutor-any-lecture so yt-dlp is installed."),
    Check("config_dir", True, check_config_dir,
          "Make the tutor-any-lecture config folder writable, "
          "or point XDG_CONFIG_HOME (APPDATA on Windows) at a writable folder."),
    Check("js_runtime", False, check_js_runtime,
          "Optional: install deno 2.3+ or node 22+ if a YouTube extraction asks for a JavaScript runtime."),
    Check("browser", False, check_browser,
          "Optional: install Chrome, Chromium or Edge, or set CHROME_PATH to the browser executable; "
          "it is used only for rendered outputs."),
    Check("asr_backend", False, check_asr_backend, _ASR_FIX),
    Check("asr_model", False, check_asr_model, _ASR_FIX),
    Check("command", False, check_command, _COMMAND_FIX),
    Check("skill_version", False, check_skill_version, _SKILL_FIX),
    Check("vision", False, check_vision, VISION_FIX),
]


def run_doctor(skill: Path | None = None, vision_word: str | None = None) -> dict:
    """Run every check in ``CHECKS`` (read at call time). Never raises.

    ``skill`` is the skill folder whose VERSION ``skill_version`` compares with this
    command's version; ``vision_word`` is the word the agent read in the probe image, for
    ``vision``. Each is kept in a module-level value for the length of the call, so every
    check stays a function of no arguments.
    """
    global _skill, _vision_word
    _skill = Path(skill) if skill is not None else None
    _vision_word = vision_word
    try:
        checks = []
        ready = True
        for c in CHECKS:
            fix = c.fix
            try:
                result = c.fn()
                ok, detail = bool(result[0]), result[1]
                if len(result) > 2:  # the check named a fix more specific than its default
                    fix = result[2]
            except Exception as e:
                ok, detail = False, f"{type(e).__name__}: {e}"
            checks.append({"name": c.name, "ok": ok, "detail": detail, "fix": "" if ok else fix})
            if c.required and not ok:
                ready = False
        return {"ready": ready, "checks": checks, "version": __version__}
    finally:
        _skill = None
        _vision_word = None
