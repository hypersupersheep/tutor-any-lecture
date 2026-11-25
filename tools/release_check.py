"""Check that every place carrying the release id agrees, before a release is made.

The release id lives in skills/tutor-any-lecture/VERSION in SemVer form (X.Y.Z,
X.Y.Z-dev.N or X.Y.Z-rc.N). The plugin files carry the same text, __version__ carries
its PEP 440 twin, and the newest CHANGELOG.md entry is headed by it. For a release the
tag must be "v" + the id, a -dev id is never tagged, and the tagged commit must be on
the given branch.

Standard library only, and the package is never imported: the release workflow runs
this before anything is installed.

    python tools/release_check.py [--root DIR] [--tag TAG] [--on REF] [--notes FILE]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_NAME = "tutor-any-lecture"
VERSION_FILE = Path("skills") / "tutor-any-lecture" / "VERSION"
INIT_FILE = "src/tutor_any_lecture/__init__.py"
PLUGIN_FILE = ".claude-plugin/plugin.json"
MARKET_FILE = ".claude-plugin/marketplace.json"
CHANGELOG_FILE = "CHANGELOG.md"

# [0-9], never \d: \d also accepts digits from other scripts.
_NUMBER = "(?:0|[1-9][0-9]*)"
_RELEASE_ID = re.compile(rf"({_NUMBER}\.{_NUMBER}\.{_NUMBER})(?:-(dev|rc)\.({_NUMBER}))?")
_INIT_VERSION = re.compile(r'^__version__\s*=\s*"([^"\n]*)"[ \t]*$', re.MULTILINE)
_DATE = "[0-9]{4}-[0-9]{2}-[0-9]{2}"


def semver_to_pep440(release_id: str) -> str:
    """The PEP 440 twin of a release id: X.Y.Z, X.Y.Z.devN or X.Y.ZrcN."""
    match = _RELEASE_ID.fullmatch(release_id) if isinstance(release_id, str) else None
    if match is None:
        raise ValueError(f"'{release_id}' is not X.Y.Z, X.Y.Z-dev.N or X.Y.Z-rc.N")
    core, kind, number = match.groups()
    if kind is None:
        return core
    return f"{core}.dev{number}" if kind == "dev" else f"{core}rc{number}"


def _read_version(root: Path) -> tuple[str | None, str | None]:
    """(release id, None) or (None, the one VERSION problem)."""
    path = root / VERSION_FILE
    if not path.is_file():
        return None, "VERSION: missing"
    try:
        # newline="" keeps a CRLF visible, so it counts as other content.
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError:
        text = ""
    body = text[:-1]
    if not text.endswith("\n") or "\n" in body or "\r" in body:
        return None, "VERSION: must be one line holding the release id, then a newline"
    try:
        semver_to_pep440(body)
    except ValueError as err:
        return None, f"VERSION: {err}"
    return body, None


def _check_init(root: Path, release_id: str) -> list[str]:
    path = root / INIT_FILE
    if not path.is_file():
        return [f"{INIT_FILE}: missing"]
    text = path.read_text(encoding="utf-8", errors="replace")
    match = _INIT_VERSION.search(text)
    if match is None:
        return [f"{INIT_FILE}: no __version__ line"]
    twin = semver_to_pep440(release_id)
    if match.group(1) != twin:
        return [f"{INIT_FILE}: __version__ is '{match.group(1)}', expected '{twin}'"]
    return []


def _load_json(root: Path, name: str):
    """(data, None) or (None, a problem line)."""
    path = root / name
    if not path.is_file():
        return None, f"{name}: missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, f"{name}: not valid JSON"


def _compare(name: str, field: str, holder, release_id: str) -> list[str]:
    if not isinstance(holder, dict) or "version" not in holder:
        return [f"{name}: {field} is missing, expected '{release_id}'"]
    got = holder["version"]
    if got != release_id:
        return [f"{name}: {field} is '{got}', expected '{release_id}'"]
    return []


def _check_plugin(root: Path, release_id: str) -> list[str]:
    data, problem = _load_json(root, PLUGIN_FILE)
    if problem:
        return [problem]
    return _compare(PLUGIN_FILE, "version", data, release_id)


def _check_marketplace(root: Path, release_id: str) -> list[str]:
    data, problem = _load_json(root, MARKET_FILE)
    if problem:
        return [problem]
    if not isinstance(data, dict):
        data = {}
    problems = _compare(MARKET_FILE, "metadata.version", data.get("metadata"), release_id)
    plugins = data.get("plugins")
    entries = [p for p in plugins if isinstance(p, dict)] if isinstance(plugins, list) else []
    entry = next((p for p in entries if p.get("name") == PLUGIN_NAME), None)
    if entry is None:
        problems.append(f"{MARKET_FILE}: no plugin named '{PLUGIN_NAME}'")
    else:
        problems += _compare(MARKET_FILE, f"plugins[{PLUGIN_NAME}].version", entry, release_id)
    return problems


def _changelog(root: Path, release_id: str) -> tuple[list[str], list[str]]:
    """(problems, notes): the newest entry must be headed by release_id and hold notes."""
    path = root / CHANGELOG_FILE
    if not path.is_file():
        return [f"{CHANGELOG_FILE}: missing"], []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if start is None:
        return [f"{CHANGELOG_FILE}: no '## ' heading"], []
    heading = lines[start]
    if not re.fullmatch(rf"## {re.escape(release_id)}(?: - {_DATE})?", heading):
        return [f"{CHANGELOG_FILE}: newest heading is '{heading}', expected '## {release_id}'"], []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    notes = lines[start + 1:end]
    while notes and not notes[0].strip():
        notes.pop(0)
    while notes and not notes[-1].strip():
        notes.pop()
    if not notes:
        return [f"{CHANGELOG_FILE}: the entry for {release_id} is empty"], []
    return [], notes


def _check_tag(release_id: str, tag: str) -> list[str]:
    if "-dev." in release_id:
        return [f"tag: VERSION '{release_id}' is a -dev id, and a -dev id is never tagged"]
    if tag != "v" + release_id:
        return [f"tag: '{tag}' is not 'v{release_id}'"]
    return []


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _check_on(root: Path, on: str) -> list[str]:
    try:
        proc = _git(root, "merge-base", "--is-ancestor", "HEAD", on)
    except FileNotFoundError:
        return [f"git: cannot check {on}: git not found"]
    if proc.returncode == 0:
        return []
    if proc.returncode == 1:
        sha = _git(root, "rev-parse", "HEAD").stdout.strip()
        return [f"git: the tagged commit {sha[:7]} is not on {on}"]
    first = (proc.stderr.splitlines() or [""])[0]
    return [f"git: cannot check {on}: {first}"]


def _inspect(root, tag=None, on=None) -> tuple[list[str], str | None, list[str]]:
    """(problems, release id, newest changelog notes)."""
    root = Path(root)
    release_id, problem = _read_version(root)
    if problem:
        return [problem], None, []
    problems = _check_init(root, release_id)
    problems += _check_plugin(root, release_id)
    problems += _check_marketplace(root, release_id)
    changelog_problems, notes = _changelog(root, release_id)
    problems += changelog_problems
    if tag is not None:
        problems += _check_tag(release_id, tag)
    if on is not None:
        problems += _check_on(root, on)
    return problems, release_id, notes


def check(root, tag=None, on=None) -> list[str]:
    """Problem lines, in a fixed order; empty when every place agrees."""
    return _inspect(root, tag, on)[0]


def _print_json(obj) -> None:
    # Non-ASCII is escaped only on Windows, where the console may not be UTF-8.
    print(json.dumps(obj, ensure_ascii=sys.platform == "win32"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="release_check.py",
        description="Check that VERSION, __version__, the plugin files and CHANGELOG.md agree.",
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="repository root (default: the folder above tools/)")
    parser.add_argument("--tag", help="the release tag, which must be v + VERSION")
    parser.add_argument("--on", help="a ref the checked-out commit must be on, such as origin/main")
    parser.add_argument("--notes", type=Path, help="write the newest CHANGELOG.md entry here")
    args = parser.parse_args(argv)

    problems, release_id, notes = _inspect(args.root, args.tag, args.on)
    if problems:
        for line in problems:
            print(line, file=sys.stderr)
        return 1
    result = {"status": "ok", "release_id": release_id, "python_version": semver_to_pep440(release_id)}
    if args.notes is not None:
        try:
            args.notes.write_text("\n".join(notes) + "\n", encoding="utf-8", newline="\n")
        except OSError as err:
            print(f"--notes: cannot write {args.notes}: {err.strerror or err}", file=sys.stderr)
            return 1
        result["path"] = str(args.notes)
    _print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
