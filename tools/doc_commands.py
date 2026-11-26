"""Check the documents' commands, installer flags and links against the code.

The documents are README.md, README.zh-CN.md and CONTRIBUTING.md, then every
skills/*/SKILL.md, then every .md under skills/*/references/. Their code (inline code
spans and the lines of fenced blocks) holds `tutor-any-lecture ...` commands, which are
checked against the CLI's parser, and installer commands, whose flags are checked
against the installers themselves.

Standard library only, and the package is never imported: the functions that need the
CLI's parser take it as an argument, and the CI workflow runs this script with a bare
runner Python.

    python tools/doc_commands.py install-command --system posix|windows FILE

prints the README's checkout-install command for that system, the line CI runs as
written.
"""

import argparse
import re
import shlex
import sys
from pathlib import Path

ROOT_DOCUMENTS = ("README.md", "README.zh-CN.md", "CONTRIBUTING.md")
COMMAND_NAMES = ("tutor-any-lecture", "tutor-any-lecture.exe")
ELLIPSES = ("…", "...")
INSTALLERS = ("install.sh", "install.ps1")
SHELLS = ("bash", "sh", "powershell", "pwsh")

_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_SPAN = re.compile(r"`([^`\n]+)`")
_ANGLE = re.compile(r"<[^<>]*>")
_PLACEHOLDER = re.compile(r"^[A-Z][A-Z0-9_-]*$")
_SEPARATORS = ("&&", "||", ";")
_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\s]+)\)")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_SH_FLAG = re.compile(r"(?<![\w-])--?[a-z][a-z-]*")
_PS_PARAM = re.compile(r"\]\s*\$(\w+)\s*[,)]")
_SHELL_SYNTAX = set(";&|$<>()`")
# Tokens of a checkout-install command: split on whitespace and on shell syntax, so that
# "--yes;" still holds "--yes" and its command is refused rather than passed over.
_INSTALL_TOKEN_BREAK = re.compile(r"[\s;&|$<>()`]+")


# ---- D1: documents, code and commands ----------------------------------------

def documents(root: Path) -> list[Path]:
    """The checked documents, in order; the three root documents must exist."""
    root = Path(root)
    docs = []
    for name in ROOT_DOCUMENTS:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"{path}: a checked document is missing")
        docs.append(path)
    docs += sorted(root.glob("skills/*/SKILL.md"))
    docs += sorted(p for p in root.glob("skills/*/references/**/*.md") if p.is_file())
    return docs


def _fenced(lines: list[str]):
    """(line number, line, inside a fence) for each line that is not a fence line itself."""
    marker = None  # the opening fence: its character and length
    for number, line in enumerate(lines, 1):
        m = _FENCE.match(line)
        if marker is None:
            if m:
                marker = m.group(1)
                continue
            yield number, line, False
        else:
            # A fence closes on a line of the same character, at least as long, and nothing else.
            if m and m.group(1)[0] == marker[0] and len(m.group(1)) >= len(marker) \
                    and not line.strip().strip(marker[0]):
                marker = None
                continue
            yield number, line, True


def code_texts(text: str) -> list[tuple[int, str]]:
    """(line number, text) of each inline code span outside fences and each fenced line.

    A fenced line holding a pair of backticks gives its spans instead (the README's
    pasted prompt). Blank texts are skipped.
    """
    out = []
    for number, line, fenced in _fenced(text.splitlines()):
        if fenced and not _SPAN.search(line):
            pieces = [line]
        else:
            pieces = _SPAN.findall(line)
        out += [(number, p.strip()) for p in pieces if p.strip()]
    return out


def _last_component(token: str) -> str:
    return re.split(r"[/\\]", token)[-1]


def cli_commands(text: str) -> list[tuple[int, str]]:
    """The code texts that run the command: `tutor-any-lecture` (or a path to it) and an argument."""
    out = []
    for number, code in code_texts(text):
        tokens = code.split()
        if len(tokens) >= 2 and _last_component(tokens[0]) in COMMAND_NAMES and tokens[1] not in ELLIPSES:
            out.append((number, code))
    return out


# ---- D2: every documented command parses ----------------------------------------

def _split(command: str) -> list[str]:
    """Steps 1 and 2: placeholders, a POSIX split, optional brackets, pipes and separators.

    Raises ValueError (shlex's) when the command cannot be split.
    """
    tokens = shlex.split(_ANGLE.sub("PLACEHOLDER", command), posix=True)
    out = []
    for token in tokens:
        token = token.strip("[]")
        if not token or token == "|":
            continue
        if token in _SEPARATORS:
            break
        if token.startswith("--") and "=" in token:
            flag, value = token.split("=", 1)
            out += [flag, value]
        else:
            out.append(token)
    return out


def _subparsers(parser: argparse.ArgumentParser):
    return next((a for a in parser._actions if isinstance(a, argparse._SubParsersAction)), None)


def _positionals(parser: argparse.ArgumentParser) -> list:
    return [a for a in parser._actions if not a.option_strings and not isinstance(a, argparse._SubParsersAction)]


def _capacity(positionals: list) -> float:
    """How many tokens the positional arguments take at most."""
    total = 0.0
    for action in positionals:
        if action.nargs in ("*", "+", argparse.REMAINDER):
            return float("inf")
        total += 1 if action.nargs in (None, "?") else action.nargs
    return total


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER.match(value)) or any(e in value for e in ELLIPSES)


def _among_choices(action, value: str) -> bool:
    try:
        converted = action.type(value) if action.type else value
    except Exception:
        return False
    return converted in action.choices


def check_cli_command(command: str, parser: argparse.ArgumentParser) -> list[str]:
    """The problems of one documented command against the parser; [] when it is sound."""
    try:
        tokens = _split(command)[1:]
    except ValueError as e:
        return [f"cannot split the command: {e}"]

    # Step 3: descend through the subcommands.
    path = "tutor-any-lecture"
    while tokens and not tokens[0].startswith("-"):
        sub = _subparsers(parser)
        if sub is None:
            break
        if tokens[0] in sub.choices:
            parser = sub.choices[tokens[0]]
            path += " " + tokens.pop(0)
            continue
        if _positionals(parser):
            break
        return [f"unknown subcommand '{tokens[0]}' after '{path}'"]

    # Step 4: flags and their values.
    options = {s: a for a in parser._actions for s in a.option_strings}
    problems, leftover = [], []
    while tokens:
        token = tokens.pop(0)
        if not token.startswith("-"):
            leftover.append(token)
            continue
        action = options.get(token)
        if action is None:
            problems.append(f"unknown flag '{token}' for '{path}'")
            continue
        if action.nargs == 0 or not tokens or tokens[0].startswith("-"):
            continue
        value = tokens.pop(0)
        if action.choices is not None and not _is_placeholder(value) and not _among_choices(action, value):
            choices = ", ".join(str(c) for c in action.choices)
            problems.append(f"'{token}' takes one of {choices}; got '{value}'")

    # Step 5: what is left are positionals.
    capacity = _capacity(_positionals(parser))
    if len(leftover) > capacity:
        extra = " ".join(leftover[int(capacity):])
        problems.append(f"too many arguments for '{path}': '{extra}'")
    return problems


# ---- D3: installer flags ----------------------------------------------------------

def _heredoc(text: str, start: str) -> str:
    """The body of the heredoc that the line `start` opens (`cat <<'EOF'`), up to its EOF line."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith(start):
            m = re.search(r"<<-?\s*'?\"?(\w+)", line)
            if m is None:
                break
            end = m.group(1)
            body = []
            for later in lines[i + 1:]:
                if later.strip() == end:
                    return "\n".join(body)
                body.append(later)
    raise ValueError(f"no heredoc opened by {start!r}")


def _param_block(text: str) -> str:
    """The text inside a PowerShell script's `param(...)`, parentheses balanced."""
    start = re.search(r"(?im)^\s*param\s*\(", text)
    if start is None:
        raise ValueError("no param( block")
    depth, i = 1, start.end()
    while depth:
        if i >= len(text):
            raise ValueError("the param( block is not closed")
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        i += 1
    return text[start.end():i]


def installer_flags(root: Path) -> dict[str, set[str]]:
    """The flags each installer accepts, read from the skill's own scripts.

    install.sh: every flag inside its `usage` heredoc. install.ps1: `-` plus each
    parameter name in its param( block except Rest, lowercased.
    """
    scripts = Path(root) / "skills" / "tutor-any-lecture" / "scripts"
    sh = (scripts / "install.sh").read_text(encoding="utf-8")
    usage = sh[sh.index("usage()"):]
    sh_flags = set(_SH_FLAG.findall(_heredoc(usage, "cat <<")))
    ps = (scripts / "install.ps1").read_text(encoding="utf-8")
    names = _PS_PARAM.findall(_param_block(ps))
    ps_flags = {"-" + n.lower() for n in names if n.lower() != "rest"}
    return {"install.sh": sh_flags, "install.ps1": ps_flags}


def _names_script(token: str) -> str | None:
    last = _last_component(token)
    return last if last in INSTALLERS else None


def installer_commands(text: str) -> list[tuple[int, str]]:
    """The code texts that run an installer: a shell or the script first, and a token naming the script."""
    out = []
    for number, code in code_texts(text):
        tokens = [t.strip("\"'") for t in code.split()]
        if not tokens:
            continue
        first = tokens[0]
        if (first in SHELLS or _names_script(first)) and any(_names_script(t) for t in tokens):
            out.append((number, code))
    return out


def check_installer_command(text: str, flags: dict[str, set[str]]) -> list[str]:
    """The flags after the script that the script does not accept; [] when all exist."""
    try:
        tokens = _split(text)
    except ValueError as e:
        return [f"cannot split the command: {e}"]
    script_at = next((i for i, t in enumerate(tokens) if _names_script(t)), None)
    if script_at is None:
        # A POSIX split eats the backslashes of an unquoted Windows path (C:\x\install.ps1):
        # find the script among the whitespace tokens instead.
        tokens = [t.strip("\"'[]") for t in _ANGLE.sub("PLACEHOLDER", text).split()]
        script_at = next((i for i, t in enumerate(tokens) if _names_script(t)), None)
    if script_at is None:
        return [f"no token names {' or '.join(INSTALLERS)}"]
    script = _names_script(tokens[script_at])
    known = flags[script]
    problems = []
    for token in tokens[script_at + 1:]:
        if not token.startswith("-"):
            continue
        name = token.lower() if script == "install.ps1" else token
        if name not in known:
            problems.append(f"unknown flag '{token}' for {script}")
    return problems


# ---- D4: links ----------------------------------------------------------------------

def relative_links(text: str) -> list[str]:
    """Targets of Markdown links outside code that are relative paths; #fragments dropped."""
    out = []
    for _, line, fenced in _fenced(text.splitlines()):
        if fenced:
            continue
        for target in _LINK.findall(_SPAN.sub(" ", line)):
            target = target.split("#", 1)[0]
            if not target or _SCHEME.match(target) or target.startswith(("/", "\\", "~", "<")):
                continue
            out.append(target)
    return out


# ---- D5: the README's checkout-install command ---------------------------------------

_INSTALL = {
    "posix": (["bash", "install.sh"], "--yes", ["--dry-run", "--with-asr", "--cli-only", "--from"]),
    "windows": (
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "install.ps1"],
        "-Yes",
        ["-DryRun", "-WithAsr", "-CliOnly", "-From"],
    ),
}


def install_command(text: str, system: str) -> str:
    """The first checkout-install command for `system` (posix or windows) in the text.

    It installs for real with no add-on: --yes (-Yes) and no dry run, speech
    recognition, CLI-only or other source. Raises ValueError when there is none, or when
    the chosen text holds shell syntax, so it can be run as written.
    """
    start, yes, excluded = _INSTALL[system]
    start = [t.casefold() for t in start]
    excluded = {t.casefold() for t in excluded}
    for _, code in code_texts(text):
        tokens = [t.casefold() for t in _INSTALL_TOKEN_BREAK.split(code) if t]
        if tokens[:len(start)] != start or yes.casefold() not in tokens or excluded & set(tokens):
            continue
        if _SHELL_SYNTAX & set(code):
            raise ValueError(f"the {system} install command holds shell syntax: {code}")
        return code
    raise ValueError(f"no {system} checkout install command found")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="doc_commands.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    ic = sub.add_parser("install-command", help="print the checkout-install command a document gives")
    ic.add_argument("--system", required=True, choices=sorted(_INSTALL))
    ic.add_argument("file", metavar="FILE")
    args = parser.parse_args(argv)
    try:
        text = Path(args.file).read_text(encoding="utf-8")
        command = install_command(text, args.system)
    except (OSError, ValueError) as e:
        print(f"{args.file}: {e}", file=sys.stderr)
        return 1
    print(command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
