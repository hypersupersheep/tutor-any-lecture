import subprocess
import sys
from pathlib import Path

import pytest

from tools.doc_commands import (
    check_cli_command,
    check_installer_command,
    cli_commands,
    code_texts,
    documents,
    install_command,
    installer_commands,
    installer_flags,
    relative_links,
)
from tutor_any_lecture.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "tutor-any-lecture" / "SKILL.md"
FENCE = "```"
# A fenced prompt line like the README's step 2.
PROMPT_LINE = (
    "2. In that folder, run `bash install.sh --yes` on macOS or Linux, or "
    "`powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Yes` on Windows."
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def where(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def skill_documents() -> list[Path]:
    """SKILL.md and the references of every skill: the documents outside the repository root."""
    return [p for p in documents(ROOT) if p.relative_to(ROOT).parts[0] == "skills"]


# ---- D1 ----

def test_code_texts_take_spans_and_fenced_lines():
    text = "\n".join([
        "Run `tutor-any-lecture verify --unit DIR` now.",
        FENCE + "bash",
        "tutor-any-lecture selftest",
        FENCE,
        FENCE + "text",
        "2. run `bash install.sh --yes` here",
        FENCE,
    ])
    assert code_texts(text) == [
        (1, "tutor-any-lecture verify --unit DIR"),
        (3, "tutor-any-lecture selftest"),
        (6, "bash install.sh --yes"),
    ]


@pytest.mark.parametrize("text", [
    FENCE + "text\nInstall tutor-any-lecture for me.\n" + FENCE,
    "Run `tutor-any-lecture …` here.",
    "Copied to `~/.claude/skills/tutor-any-lecture/`.",
    "Lists `tutor-any-lecture` among its skills.",
])
def test_prose_mentions_are_not_commands(text):
    assert cli_commands(text) == []


def test_a_path_to_the_command_counts():
    assert cli_commands("`.venv/bin/tutor-any-lecture selftest`") == [(1, ".venv/bin/tutor-any-lecture selftest")]


# ---- D2 ----

def test_every_documented_command_parses():
    parser = build_parser()
    problems = [
        f"{where(path)}:{line}: {command}: {problem}"
        for path in documents(ROOT)
        for line, command in cli_commands(read(path))
        for problem in check_cli_command(command, parser)
    ]
    assert problems == []


def test_documents_hold_commands():
    counts = {path: len(cli_commands(read(path))) for path in documents(ROOT)}
    assert sum(counts.values()) >= 90
    assert len([p for p, n in counts.items() if n]) >= 12
    assert counts[SKILL] >= 25


def test_documents_are_listed_in_order():
    docs = [where(p) for p in documents(ROOT)]
    assert docs[:3] == ["README.md", "README.zh-CN.md", "CONTRIBUTING.md"]
    assert "skills/tutor-any-lecture/SKILL.md" in docs
    assert "skills/tutor-any-lecture/references/gate.md" in docs
    assert any(d.startswith("skills/tutor-any-lecture/references/agents/") for d in docs)


def test_unknown_subcommand_is_reported():
    assert check_cli_command("tutor-any-lecture acquire fetch --url U", build_parser()) == [
        "unknown subcommand 'fetch' after 'tutor-any-lecture acquire'"
    ]


def test_unknown_flag_is_reported():
    assert check_cli_command("tutor-any-lecture verify --unit DIR --strict", build_parser()) == [
        "unknown flag '--strict' for 'tutor-any-lecture verify'"
    ]


def test_choice_values_are_checked():
    parser = build_parser()
    assert check_cli_command("tutor-any-lecture items next --unit DIR --phase later", parser) == [
        "'--phase' takes one of pre, post, d1, d7, d21; got 'later'"
    ]
    command = "tutor-any-lecture progress log --unit DIR --item ID --phase post --score high --confidence K"
    assert check_cli_command(command, parser) == ["'--score' takes one of 0.0, 0.5, 1.0; got 'high'"]


def test_too_many_arguments_are_reported():
    assert check_cli_command("tutor-any-lecture profile set a b c", build_parser()) == [
        "too many arguments for 'tutor-any-lecture profile set': 'c'"
    ]


def test_unbalanced_quotes_are_reported():
    assert check_cli_command('tutor-any-lecture profile set outputs "[explanation', build_parser()) == [
        "cannot split the command: No closing quotation"
    ]


@pytest.mark.parametrize("command", [
    "tutor-any-lecture acquire import --file F --unit DIR [--duration SEC | --media FILE] [--force]",
    "tutor-any-lecture acquire panopto --extract <path shown in the tool result> --unit DIR",
    'tutor-any-lecture profile set outputs "[explanation, quiz]"',
    "tutor-any-lecture progress log --unit DIR --item ID --phase post --score S --confidence K [--date YYYY-MM-DD]",
])
def test_placeholders_and_optional_parts_pass(command):
    assert check_cli_command(command, build_parser()) == []


def test_a_misspelt_flag_in_a_copy_of_the_skill_is_reported_with_its_line():
    lines = read(SKILL).splitlines()
    line, command = next((n, c) for n, c in cli_commands(read(SKILL)) if "--unit" in c)
    lines[line - 1] = lines[line - 1].replace("--unit", "--unti", 1)
    parser = build_parser()
    problems = [
        (n, p) for n, c in cli_commands("\n".join(lines)) for p in check_cli_command(c, parser)
    ]
    assert problems and problems[0][0] == line
    assert "unknown flag '--unti'" in problems[0][1]


# ---- D3 ----

def test_documented_installer_flags_exist():
    flags = installer_flags(ROOT)
    found, problems = 0, []
    for path in documents(ROOT):
        for line, text in installer_commands(read(path)):
            found += 1
            problems += [f"{where(path)}:{line}: {text}: {p}" for p in check_installer_command(text, flags)]
    assert problems == []
    assert found >= 5


def test_installer_flags_are_read_from_the_scripts():
    flags = installer_flags(ROOT)
    assert {"--dry-run", "--yes", "--with-asr", "--cli-only", "--agents", "--from", "--help"} <= flags["install.sh"]
    assert {"-dryrun", "-yes", "-withasr", "-clionly", "-agents", "-from"} <= flags["install.ps1"]
    assert "-rest" not in flags["install.ps1"] and "-true" not in flags["install.ps1"]


def test_unknown_installer_flag_is_reported():
    flags = installer_flags(ROOT)
    assert check_installer_command("bash install.sh --yes --force", flags) == ["unknown flag '--force' for install.sh"]
    command = "powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -yes -Force"
    assert check_installer_command(command, flags) == ["unknown flag '-Force' for install.ps1"]
    command = 'powershell -NoProfile -ExecutionPolicy Bypass -File "<skill folder>\\scripts\\install.ps1" -Yes -Force'
    assert check_installer_command(command, flags) == ["unknown flag '-Force' for install.ps1"]


# ---- D4 ----

def test_links_in_every_skill_document_resolve():
    checked, missing = 0, []
    for path in skill_documents():
        for target in relative_links(read(path)):
            checked += 1
            if not (path.parent / target).exists():
                missing.append(f"{where(path)}: {target}")
    assert missing == []
    assert checked >= 60


def test_links_inside_code_are_not_links():
    assert relative_links("see `[x](<url>&t=1)` and [y](gate.md#top)") == ["gate.md"]


# ---- D5 ----

def test_readme_names_both_checkout_install_commands():
    text = read(ROOT / "README.md")
    posix = install_command(text, "posix")
    assert posix.startswith("bash install.sh") and "--yes" in posix.split()
    assert "-Yes" in install_command(text, "windows").split()


def test_install_command_is_taken_from_the_prompt():
    text = "\n".join([FENCE + "text", PROMPT_LINE, FENCE])
    assert install_command(text, "posix") == "bash install.sh --yes"
    assert install_command(text, "windows") == "powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Yes"


def test_install_command_skips_dry_runs_and_add_ons():
    text = "Try `bash install.sh --dry-run`, then `bash install.sh --yes --with-asr`, or `bash install.sh --yes --agents claude`."
    assert install_command(text, "posix") == "bash install.sh --yes --agents claude"


def test_install_command_refuses_shell_syntax():
    with pytest.raises(ValueError) as caught:
        install_command("Run `bash install.sh --yes; rm -rf x`.", "posix")
    assert str(caught.value) == "the posix install command holds shell syntax: bash install.sh --yes; rm -rf x"


def test_install_command_reports_a_missing_command():
    with pytest.raises(ValueError) as caught:
        install_command("Nothing here.", "windows")
    assert str(caught.value) == "no windows checkout install command found"


def test_install_command_cli(tmp_path):
    good = tmp_path / "good.md"
    good.write_text("\n".join([FENCE + "text", PROMPT_LINE, FENCE]) + "\n", encoding="utf-8", newline="\n")
    bad = tmp_path / "bad.md"
    bad.write_text("No command here.\n", encoding="utf-8", newline="\n")
    script = str(ROOT / "tools" / "doc_commands.py")

    def run(path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, script, "install-command", "--system", "posix", str(path)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )

    ok = run(good)
    assert ok.returncode == 0 and ok.stdout == "bash install.sh --yes\n"
    failed = run(bad)
    assert failed.returncode == 1 and failed.stdout == ""
    assert len(failed.stderr.splitlines()) == 1
    assert failed.stderr.rstrip("\n").endswith(": no posix checkout install command found")
