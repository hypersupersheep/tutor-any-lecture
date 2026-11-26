import itertools
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

from tutor_any_lecture.config import config_dir

ROOT = Path(__file__).resolve().parents[1]
CANON = Path("skills/tutor-any-lecture/scripts")
SH_FILES = [Path("install.sh"), CANON / "install.sh"]
PS1_FILES = [Path("install.ps1"), CANON / "install.ps1"]
GIT_SOURCE = "git+https://github.com/hypersupersheep/tutor-any-lecture"
PS = shutil.which("pwsh") or shutil.which("powershell")

needs_bash = pytest.mark.skipif(sys.platform == "win32", reason="bash")
needs_ps = pytest.mark.skipif(PS is None, reason="needs pwsh or powershell")


def home(tmp_path):
    """Environment for an installer subprocess: every home-like folder points into
    tmp_path, and the interpreter running pytest comes first on PATH."""
    env = dict(os.environ)
    for key in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME"):
        env[key] = str(tmp_path)
    if sys.platform == "win32":
        for key, sub in (("APPDATA", "Roaming"), ("LOCALAPPDATA", "Local")):
            folder = tmp_path / "AppData" / sub
            folder.mkdir(parents=True, exist_ok=True)
            env[key] = str(folder)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    # PowerShell would otherwise write a telemetry id into the home folder it is given.
    env["POWERSHELL_TELEMETRY_OPTOUT"] = "1"
    return env


def run(argv, env):
    """Run an installer with no terminal attached; return its stdout as text."""
    proc = subprocess.run(
        argv,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="bash")
def test_sh_dry_run_plans_without_changes(tmp_path):
    out = run(["bash", "install.sh", "--dry-run", "--agents", "claude"], env=home(tmp_path))
    assert "PLAN: uv tool install" in out or "PLAN: python -m venv" in out
    assert not (tmp_path / ".claude").exists()


@pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("pwsh") is None, reason="pwsh on Windows"
)
def test_ps1_dry_run(tmp_path):
    out = run(["pwsh", "-File", "install.ps1", "-DryRun"], env=home(tmp_path))
    assert "PLAN:" in out


def test_no_curl_pipe():
    for path in SH_FILES:
        assert "| sh" not in path.read_text(encoding="utf-8")
    for path in PS1_FILES:
        assert "iex" not in path.read_text(encoding="utf-8").lower()


@pytest.mark.skipif(sys.platform == "win32", reason="bash")
def test_wrapper_matches_canonical_dry_run(tmp_path):
    env = home(tmp_path)
    args = ["--dry-run", "--agents", "claude"]
    wrapper = run(["bash", "install.sh", *args], env=env)
    canonical = run(["bash", str(CANON / "install.sh"), *args], env=env)
    assert wrapper == canonical
    assert "PLAN:" in wrapper


@pytest.mark.skipif(sys.platform == "win32", reason="bash")
@pytest.mark.parametrize("xdg_set", [True, False], ids=["xdg-set", "xdg-unset"])
def test_sh_cli_path_matches_config_dir(tmp_path, monkeypatch, xdg_set):
    env = home(tmp_path)
    if not xdg_set:
        del env["XDG_CONFIG_HOME"]
    for key in ("HOME", "XDG_CONFIG_HOME"):
        if key in env:
            monkeypatch.setenv(key, env[key])
        else:
            monkeypatch.delenv(key, raising=False)
    out = run(["bash", "install.sh", "--dry-run", "--agents", "claude"], env=env)
    assert "PLAN: write " + str(config_dir() / "cli-path") in out


@pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("pwsh") is None, reason="pwsh on Windows"
)
def test_ps1_cli_path_matches_config_dir(tmp_path, monkeypatch):
    env = home(tmp_path)
    monkeypatch.setenv("APPDATA", env["APPDATA"])
    out = run(["pwsh", "-File", "install.ps1", "-DryRun"], env=env)
    assert "PLAN: write " + str(config_dir() / "cli-path") in out


# ---- shared helpers for the flag and stop tests ------------------------------


def run_rc(argv, env, cwd=ROOT):
    """Run an installer with no terminal attached; return the CompletedProcess."""
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def sh(*args):
    return ["bash", str(ROOT / "install.sh"), *args]


def ps(*args, script=None):
    script = script or (ROOT / "install.ps1")
    policy = ["-ExecutionPolicy", "Bypass"] if sys.platform == "win32" else []
    return [PS, "-NoProfile", *policy, "-File", str(script), *args]


def snapshot(folder):
    return sorted(str(p) for p in folder.rglob("*"))


def is_shell_file(path, folder):
    """A path PowerShell writes for itself into the home folder it is given:
    .cache/powershell, .local/share/powershell, AppData/Local/Microsoft/PowerShell."""
    parts = Path(path).relative_to(folder).parts
    return any("powershell" in part.lower() or part == "Microsoft" for part in parts)


def new_paths(folder, before):
    """Paths under ``folder`` that are not in the snapshot ``before``, leaving out the
    shell's own files and every new directory that exists only as their parent."""
    seen = set(before)
    new = [Path(p) for p in snapshot(folder) if p not in seen]
    shell = {p for p in new if is_shell_file(p, folder)}
    holders = {a for p in shell for a in p.parents if a in new}

    def holds_only_shell_files(d):
        return all(q in shell or q in holders for q in new if d in q.parents)

    left_out = shell | {d for d in holders if holds_only_shell_files(d)}
    return [str(p) for p in new if p not in left_out]


def tool_dir(tmp_path, *names):
    """A folder holding links to just the named tools, to stand in for PATH."""
    bin_dir = tmp_path / "tools"
    bin_dir.mkdir()
    for name in names:
        real = shutil.which(name)
        assert real, name
        (bin_dir / name).symlink_to(real)
    return bin_dir


def copied_skill(tmp_path):
    """A copy of the skill folder with no pyproject.toml above it."""
    dest = tmp_path / "copy" / "skills" / "tutor-any-lecture"
    shutil.copytree(ROOT / "skills" / "tutor-any-lecture", dest)
    return dest


def fake_tool(folder, name, sh_body, cmd_body):
    """A stand-in program: a #!/bin/sh script (mode 0o755), or a .cmd file on Windows."""
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        path = folder / f"{name}.cmd"
        path.write_text("@echo off\r\n" + cmd_body + "\r\n", encoding="utf-8", newline="")
    else:
        path = folder / name
        path.write_text("#!/bin/sh\n" + sh_body + "\n", encoding="utf-8", newline="\n")
        path.chmod(0o755)
    return path


def fake_git(folder, log, code):
    """A git that logs $GIT_TERMINAL_PROMPT $GCM_INTERACTIVE and its arguments, then exits ``code``."""
    return fake_tool(
        folder,
        "git",
        f"printf '%s\\n' \"$GIT_TERMINAL_PROMPT $GCM_INTERACTIVE $*\" >> '{log}'\nexit {code}",
        f'>>"{log}" echo %GIT_TERMINAL_PROMPT% %GCM_INTERACTIVE% %*\r\nexit /b {code}',
    )


def with_fakes(env, folder):
    """``env`` with ``folder`` first on PATH."""
    env = dict(env)
    env["PATH"] = str(folder) + os.pathsep + env["PATH"]
    return env


def write_version(skill, version):
    """Write VERSION into a skill copy, or remove it when ``version`` is None."""
    if version is None:
        (skill / "VERSION").unlink()
    else:
        (skill / "VERSION").write_text(version + "\n", encoding="utf-8", newline="\n")


REPO_URL = "https://github.com/hypersupersheep/tutor-any-lecture"
# VERSION as written into a skill copy -> the release tag it installs from (None: the default branch).
VERSION_CASES = {
    "2.0.0": "2.0.0",
    "2.0.0-rc.1": "2.0.0-rc.1",
    "2.0.0-dev.0": None,
    "2.0.0.dev0": None,
    "02.0.0": None,
    "2.0.0-RC.1": None,
    None: None,
}
NO_RELEASE_ID = "PLAN: install from the default branch (the skill folder has no release id in VERSION)"


def ls_remote_log(tag):
    return f"0 never -c credential.helper= ls-remote --exit-code --tags {REPO_URL} refs/tags/v{tag}"


def assert_source_follows_version(proc, version, log):
    assert proc.returncode == 0, proc.stderr
    tag = VERSION_CASES[version]
    branch = [ln for ln in (proc.stdout + proc.stderr).splitlines() if "default branch" in ln]
    if tag is not None:
        assert f'"{GIT_SOURCE}@v{tag}"' in proc.stdout
        assert branch == []
        assert log.read_text(encoding="utf-8").splitlines() == [ls_remote_log(tag)]
        return
    assert f'"{GIT_SOURCE}"' in proc.stdout
    assert "@v" not in proc.stdout
    if version == "2.0.0-dev.0":
        expected = (
            "PLAN: install from the default branch "
            "(VERSION 2.0.0-dev.0 is a development version, which is never tagged)"
        )
    else:
        expected = NO_RELEASE_ID
    assert branch == [expected]
    assert not log.exists()


# pyproject.toml bytes beside a copied skills/ folder -> whether that folder is the checkout.
PYPROJECTS = [
    pytest.param(b'[project]\r\nname = "tutor-any-lecture"\r\n', True, id="this-project-crlf"),
    pytest.param(b'[project]\nname = "other-project"\n', False, id="other-project"),
    pytest.param(
        b'[tool.x]\nname = "tutor-any-lecture"\n[project]\nname = "other"\n', False, id="name-in-another-table"
    ),
]


def test_ps1_files_are_ascii_for_windows_powershell():
    # Windows PowerShell 5.1 reads a script without a BOM in the ANSI code page.
    for path in PS1_FILES:
        assert (ROOT / path).read_bytes().isascii(), path


# A ternary, `$a ? $b : $c`, outside string literals: a lone ? and later a lone :.
PS_TERNARY = re.compile(r"(?<=\s)\?(?=\s)[^\n]*?\s:(?=\s)")
PS_STRING = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")


def test_ps1_avoids_powershell_7_only_operators():
    # The ternary pattern finds what it is meant to find, and leaves strings alone.
    assert PS_TERNARY.search("$x = $ok ? 'yes' : 'no'")
    assert not PS_TERNARY.search(PS_STRING.sub("''", "Write-Host 'Proceed ? [y/N] : '"))
    for path in PS1_FILES:
        code = "\n".join(
            line.split("#", 1)[0] for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        )
        for token in ("??", "&&", "||", "?."):
            assert token not in code, (path, token)
        bare = PS_STRING.sub("''", code)
        assert not PS_TERNARY.search(bare), (path, "ternary")


def test_ps1_declares_the_new_flags():
    for path in PS1_FILES:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "[switch]$WithAsr" in text and "[switch]$CliOnly" in text, path
    canonical = (ROOT / CANON / "install.ps1").read_text(encoding="utf-8")
    assert "#   -WithAsr" in canonical and "#   -CliOnly" in canonical
    header = "\n".join(itertools.takewhile(lambda line: line.startswith("#"), canonical.splitlines()))
    assert "default branch" in header


def test_installers_carry_the_real_run_lines():
    for name in ("install.sh", "install.ps1"):
        text = (ROOT / CANON / name).read_text(encoding="utf-8")
        assert "Installing from the default branch: VERSION " in text, name
        assert "Installing from the default branch: the skill folder has no release id in VERSION." in text, name


# ---- install.sh ---------------------------------------------------------------


@needs_bash
def test_sh_unknown_flag_exits_2(tmp_path):
    assert run_rc(sh("--bogus", "--dry-run"), home(tmp_path)).returncode == 2


@needs_bash
def test_sh_unknown_agent_exits_2(tmp_path):
    assert run_rc(sh("--agents", "robot", "--dry-run"), home(tmp_path)).returncode == 2


@needs_bash
def test_sh_cli_only_with_agents_exits_2(tmp_path):
    proc = run_rc(sh("--cli-only", "--agents", "claude", "--dry-run"), home(tmp_path))
    assert proc.returncode == 2
    assert "--cli-only" in proc.stderr


@needs_bash
def test_sh_agent_names_ignore_case(tmp_path):
    proc = run_rc(sh("--agents", "Claude", "--dry-run"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert str(tmp_path / ".claude" / "skills" / "tutor-any-lecture") in proc.stdout


@needs_bash
def test_sh_dry_run_creates_nothing(tmp_path):
    env = home(tmp_path)
    before = snapshot(tmp_path)
    proc = run_rc(sh("--dry-run", "--with-asr", "--agents", "claude,codex,agents"), env)
    assert proc.returncode == 0, proc.stderr
    assert snapshot(tmp_path) == before == []


@needs_bash
def test_sh_help_names_the_new_flags(tmp_path):
    proc = run_rc(sh("--help"), home(tmp_path))
    assert proc.returncode == 0
    assert "--with-asr" in proc.stdout and "--cli-only" in proc.stdout
    assert "default branch" in proc.stdout


@needs_bash
def test_sh_with_asr_names_the_extra(tmp_path):
    proc = run_rc(sh("--dry-run", "--with-asr"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "tutor-any-lecture[asr] @ " in proc.stdout
    assert "tutor-any-lecture[asr] @ " + "file://" + quote(str(ROOT.resolve())) in proc.stdout
    assert "PLAN: --with-asr on" in proc.stdout


@needs_bash
def test_sh_without_asr_installs_the_plain_package(tmp_path):
    proc = run_rc(sh("--dry-run"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "[asr]" not in proc.stdout
    assert "PLAN: --with-asr off" in proc.stdout and "PLAN: --cli-only off" in proc.stdout


@needs_bash
def test_sh_with_asr_file_url_for_a_folder_with_space_and_cjk(tmp_path):
    source = tmp_path / "课程 资料" / "第1周"
    source.mkdir(parents=True)
    proc = run_rc(sh("--dry-run", "--with-asr", "--from", str(source)), home(tmp_path / "h"))
    assert proc.returncode == 0, proc.stderr
    url = "file://" + quote(str(source.resolve()))
    assert "%20" in url and "tutor-any-lecture[asr] @ " + url in proc.stdout


@needs_bash
def test_sh_cli_only_copies_no_skill(tmp_path):
    (tmp_path / ".claude").mkdir()
    proc = run_rc(sh("--dry-run", "--cli-only"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "PLAN: copy" not in proc.stdout
    assert str(tmp_path / ".claude") not in proc.stdout
    assert "PLAN: write " in proc.stdout
    assert "PLAN: --cli-only on" in proc.stdout


@needs_bash
def test_sh_refuses_git_bash(tmp_path):
    fake = tmp_path / "fake"
    fake.mkdir()
    uname = fake / "uname"
    uname.write_text("#!/bin/sh\necho MINGW64_NT-10.0\n", encoding="utf-8", newline="\n")
    uname.chmod(0o755)
    env = home(tmp_path)
    env["PATH"] = str(fake) + os.pathsep + env["PATH"]
    proc = run_rc(sh("--dry-run", "--with-asr", "--agents", "claude"), env)
    assert proc.returncode == 3
    lines = [ln for ln in proc.stderr.splitlines() if "powershell" in ln]
    assert any("powershell -NoProfile -ExecutionPolicy Bypass -File" in ln for ln in lines)
    command = next(ln for ln in lines if ln.startswith("powershell "))
    assert "install.ps1" in command
    assert "-DryRun" in command and "-WithAsr" in command and '-Agents "claude"' in command


@needs_bash
def test_sh_missing_git_for_git_source_exits_3(tmp_path):
    script = tmp_path / "install.sh"
    shutil.copy(ROOT / CANON / "install.sh", script)
    env = home(tmp_path)
    # only what the script runs before the git check; no git
    env["PATH"] = str(tool_dir(tmp_path, "uname", "dirname"))
    proc = run_rc([shutil.which("bash"), str(script), "--dry-run"], env)
    assert proc.returncode == 3
    assert "needs git" in proc.stderr and "--from" in proc.stderr
    assert len(proc.stderr.strip().splitlines()) == 1


@needs_bash
@pytest.mark.parametrize("version", list(VERSION_CASES), ids=lambda v: v or "no-VERSION")
def test_sh_skill_copy_source_follows_version(tmp_path, version):
    skill = copied_skill(tmp_path)
    write_version(skill, version)
    log = tmp_path / "git.log"
    fake_git(tmp_path / "fakes", log, 0)
    env = with_fakes(home(tmp_path / "h"), tmp_path / "fakes")
    proc = run_rc(["bash", str(skill / "scripts" / "install.sh"), "--dry-run"], env)
    assert_source_follows_version(proc, version, log)


@needs_bash
def test_sh_missing_tag_ends_in_one_line(tmp_path):
    skill = copied_skill(tmp_path)
    write_version(skill, "2.0.0-rc.1")
    fake_git(tmp_path / "fakes", tmp_path / "git.log", 2)
    env = with_fakes(home(tmp_path / "h"), tmp_path / "fakes")
    proc = run_rc(["bash", str(skill / "scripts" / "install.sh"), "--dry-run"], env)
    assert proc.returncode == 3
    lines = proc.stderr.strip().splitlines()
    assert len(lines) == 1
    assert "v2.0.0-rc.1" in lines[0] and "--from" in lines[0]
    assert "PLAN:" not in proc.stdout


@needs_bash
@pytest.mark.parametrize("pyproject, is_checkout", PYPROJECTS)
def test_sh_checkout_must_name_this_project(tmp_path, pyproject, is_checkout):
    skill = copied_skill(tmp_path)
    write_version(skill, "2.0.0-dev.0")
    checkout = skill.parents[1]
    (checkout / "pyproject.toml").write_bytes(pyproject)
    fake_git(tmp_path / "fakes", tmp_path / "git.log", 0)
    env = with_fakes(home(tmp_path / "h"), tmp_path / "fakes")
    proc = run_rc(["bash", str(skill / "scripts" / "install.sh"), "--dry-run"], env)
    assert proc.returncode == 0, proc.stderr
    if is_checkout:
        assert f'"{checkout.resolve()}"' in proc.stdout
        assert GIT_SOURCE not in proc.stdout
    else:
        assert f'"{GIT_SOURCE}"' in proc.stdout


def canonical_sh():
    """The repository's own install.sh, run by bash's full path: the checkout is the
    source, so no git is needed, and PATH may leave bash out."""
    return [shutil.which("bash"), str(ROOT / CANON / "install.sh"), "--dry-run"]


def exits(code):
    return f"exit {code}", f"exit /b {code}"


@needs_bash
@pytest.mark.parametrize("method", ["uv", "venv"])
def test_sh_reinstall_always_rebuilds(tmp_path, method):
    env = home(tmp_path / "h")
    fakes = tmp_path / "fakes"
    if method == "uv":
        fake_tool(fakes, "uv", *exits(0))
    else:
        fake_tool(fakes, "python3", *exits(0))
    env["PATH"] = str(fakes) + os.pathsep + str(tool_dir(tmp_path, "uname", "dirname"))
    proc = run_rc(canonical_sh(), env)
    assert proc.returncode == 0, proc.stderr
    if method == "uv":
        assert 'PLAN: uv tool install --force --reinstall "' in proc.stdout
    else:
        assert '-m pip install --upgrade --force-reinstall "' in proc.stdout


@needs_bash
def test_sh_python_without_venv_module_exits_3(tmp_path):
    env = home(tmp_path / "h")
    fakes = tmp_path / "fakes"
    fake_tool(fakes, "python3", 'case "$*" in *ensurepip*) exit 1 ;; esac\nexit 0', "exit /b 0")
    env["PATH"] = str(fakes) + os.pathsep + str(tool_dir(tmp_path, "uname", "dirname"))
    proc = run_rc(canonical_sh(), env)
    assert proc.returncode == 3
    lines = proc.stderr.strip().splitlines()
    assert len(lines) == 1
    assert "python3-venv" in lines[0] and "uv" in lines[0]


ODD_HOME = ("课程 资料", "it's")


@needs_bash
@pytest.mark.parametrize("method", ["venv", "uv"])
def test_sh_plan_ends_with_the_selftest_command(tmp_path, method):
    home_dir = tmp_path.joinpath(*ODD_HOME)
    home_dir.mkdir(parents=True)
    env = home(home_dir)
    fakes = tmp_path / "fakes"
    fake_tool(fakes, "python3" if method == "venv" else "uv", *exits(0))
    env["PATH"] = str(fakes) + os.pathsep + str(tool_dir(tmp_path, "uname", "dirname"))
    proc = run_rc(canonical_sh(), env)
    assert proc.returncode == 0, proc.stderr
    prefix = "PLAN: print the selftest command: "
    last = proc.stdout.splitlines()[-1]
    if method == "uv":
        assert last == prefix + "'<uv tool bin folder>/tutor-any-lecture' selftest"
        return
    cli = f"{home_dir}/.tutor-any-lecture/venv/bin/tutor-any-lecture"
    assert last == prefix + "'" + cli.replace("'", "'\\''") + "' selftest"
    assert shlex.split(last[len(prefix):]) == [cli, "selftest"]


@needs_bash
def test_sh_plan_asks_doctor_about_this_skill(tmp_path):
    proc = run_rc(sh("--dry-run"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    skill = (ROOT / "skills" / "tutor-any-lecture").resolve()
    assert f'PLAN: run tutor-any-lecture doctor --json --skill "{skill}"' in proc.stdout.splitlines()


# ---- install.ps1 --------------------------------------------------------------


@needs_ps
def test_ps1_unknown_flag_exits_2(tmp_path):
    assert run_rc(ps("-Bogus", "-DryRun"), home(tmp_path)).returncode == 2


@needs_ps
def test_ps1_unknown_agent_exits_2(tmp_path):
    assert run_rc(ps("-Agents", "robot", "-DryRun"), home(tmp_path)).returncode == 2


@needs_ps
def test_ps1_cli_only_with_agents_exits_2(tmp_path):
    proc = run_rc(ps("-CliOnly", "-Agents", "claude", "-DryRun"), home(tmp_path))
    assert proc.returncode == 2


@needs_ps
def test_ps1_agent_names_ignore_case(tmp_path):
    proc = run_rc(ps("-Agents", "Claude", "-DryRun"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "PLAN: copy " in proc.stdout


@needs_ps
def test_ps1_dry_run_creates_nothing(tmp_path):
    env = home(tmp_path)
    before = snapshot(tmp_path)
    proc = run_rc(ps("-DryRun", "-WithAsr", "-Agents", "claude,codex,agents"), env)
    assert proc.returncode == 0, proc.stderr
    assert new_paths(tmp_path, before) == []


def test_new_paths_leaves_out_only_the_shell_files(tmp_path):
    """The dry-run check ignores PowerShell's start-up files and nothing else."""
    (tmp_path / "AppData" / "Local").mkdir(parents=True)
    before = snapshot(tmp_path)
    shell_files = [
        tmp_path / ".cache" / "powershell" / "StartupProfileData-NonInteractive",
        tmp_path / ".local" / "share" / "powershell" / "Modules",
        tmp_path / "AppData" / "Local" / "Microsoft" / "PowerShell" / "StartupProfileData-NonInteractive",
    ]
    for f in shell_files:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("", encoding="utf-8", newline="\n")
    assert new_paths(tmp_path, before) == []
    # A file of the installer's own is still caught, with the new folders that hold it,
    # even inside a folder the shell also wrote to.
    own = tmp_path / ".local" / "share" / "tutor-any-lecture" / "cli-path"
    own.parent.mkdir(parents=True)
    own.write_text("x", encoding="utf-8", newline="\n")
    empty = tmp_path / ".claude"
    empty.mkdir()
    assert new_paths(tmp_path, before) == [
        str(empty),
        str(tmp_path / ".local"),
        str(tmp_path / ".local" / "share"),
        str(own.parent),
        str(own),
    ]


@needs_ps
def test_ps1_with_asr_names_the_extra(tmp_path):
    proc = run_rc(ps("-DryRun", "-WithAsr"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "tutor-any-lecture[asr] @ file:///" in proc.stdout
    assert "PLAN: -WithAsr on" in proc.stdout


@needs_ps
def test_ps1_cli_only_copies_no_skill(tmp_path):
    (tmp_path / ".claude").mkdir()
    proc = run_rc(ps("-DryRun", "-CliOnly"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "PLAN: copy" not in proc.stdout
    assert "PLAN: write " in proc.stdout
    assert "PLAN: -CliOnly on" in proc.stdout


@needs_ps
def test_ps1_missing_git_for_git_source_exits_3(tmp_path):
    script = tmp_path / "install.ps1"
    shutil.copy(ROOT / CANON / "install.ps1", script)
    env = home(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    env["PATH"] = str(empty)
    proc = run_rc(ps("-DryRun", script=script), env)
    assert proc.returncode == 3
    assert "needs git" in proc.stderr and "-From" in proc.stderr


@needs_ps
@pytest.mark.parametrize("version", list(VERSION_CASES), ids=lambda v: v or "no-VERSION")
def test_ps1_skill_copy_source_follows_version(tmp_path, version):
    skill = copied_skill(tmp_path)
    write_version(skill, version)
    log = tmp_path / "git.log"
    fake_git(tmp_path / "fakes", log, 0)
    env = with_fakes(home(tmp_path / "h"), tmp_path / "fakes")
    proc = run_rc(ps("-DryRun", script=skill / "scripts" / "install.ps1"), env)
    assert_source_follows_version(proc, version, log)


@needs_ps
def test_ps1_missing_tag_ends_in_one_line(tmp_path):
    skill = copied_skill(tmp_path)
    write_version(skill, "2.0.0-rc.1")
    fake_git(tmp_path / "fakes", tmp_path / "git.log", 2)
    env = with_fakes(home(tmp_path / "h"), tmp_path / "fakes")
    proc = run_rc(ps("-DryRun", script=skill / "scripts" / "install.ps1"), env)
    assert proc.returncode == 3
    lines = proc.stderr.strip().splitlines()
    assert len(lines) == 1
    assert "v2.0.0-rc.1" in lines[0] and "-From" in lines[0]
    assert "PLAN:" not in proc.stdout


@needs_ps
def test_ps1_puts_back_what_it_changed(tmp_path):
    skill = copied_skill(tmp_path)
    write_version(skill, "2.0.0")
    fake_git(tmp_path / "fakes", tmp_path / "git.log", 0)
    env = with_fakes(home(tmp_path / "h"), tmp_path / "fakes")
    script = str(skill / "scripts" / "install.ps1").replace("'", "''")
    driver = tmp_path / "driver.ps1"
    driver.write_text(
        "\ufeff"
        "$env:GIT_TERMINAL_PROMPT = '1'\n"
        "Remove-Item -LiteralPath Env:GCM_INTERACTIVE -ErrorAction SilentlyContinue\n"
        "$before = [Console]::OutputEncoding.CodePage\n"
        f"& '{script}' -DryRun\n"
        "$same = ($before -eq [Console]::OutputEncoding.CodePage)\n"
        "[Console]::Out.WriteLine('[' + $env:GIT_TERMINAL_PROMPT + '][' + $env:GCM_INTERACTIVE + '][' + $same + ']')\n",
        encoding="utf-8",
        newline="\n",
    )
    proc = run_rc(ps(script=driver), env)
    assert proc.stdout.splitlines()[-1] == "[1][][True]", proc.stderr


@needs_ps
@pytest.mark.parametrize("pyproject, is_checkout", PYPROJECTS)
def test_ps1_checkout_must_name_this_project(tmp_path, pyproject, is_checkout):
    skill = copied_skill(tmp_path)
    write_version(skill, "2.0.0-dev.0")
    checkout = skill.parents[1]
    (checkout / "pyproject.toml").write_bytes(pyproject)
    fake_git(tmp_path / "fakes", tmp_path / "git.log", 0)
    env = with_fakes(home(tmp_path / "h"), tmp_path / "fakes")
    proc = run_rc(ps("-DryRun", script=skill / "scripts" / "install.ps1"), env)
    assert proc.returncode == 0, proc.stderr
    if is_checkout:
        assert f'"{checkout}"' in proc.stdout
        assert GIT_SOURCE not in proc.stdout
    else:
        assert f'"{GIT_SOURCE}"' in proc.stdout


def canonical_ps(*args):
    """The repository's own install.ps1: the checkout is the source, so no git is needed."""
    return ps(*args, script=ROOT / CANON / "install.ps1")


@needs_ps
@pytest.mark.parametrize("method", ["uv", "venv"])
def test_ps1_reinstall_always_rebuilds(tmp_path, method):
    env = home(tmp_path / "h")
    fakes = tmp_path / "fakes"
    fake_tool(fakes, "uv" if method == "uv" else "python", *exits(0))
    env["PATH"] = str(fakes)
    proc = run_rc(canonical_ps("-DryRun"), env)
    assert proc.returncode == 0, proc.stderr
    if method == "uv":
        assert 'PLAN: uv tool install --force --reinstall "' in proc.stdout
    else:
        assert '-m pip install --upgrade --force-reinstall "' in proc.stdout


@needs_ps
def test_ps1_names_the_store_alias(tmp_path):
    env = home(tmp_path / "h")
    alias_dir = tmp_path / "Microsoft" / "WindowsApps"
    fake_tool(alias_dir, "python", *exits(9009))
    env["PATH"] = str(alias_dir)
    proc = run_rc(canonical_ps("-DryRun"), env)
    assert proc.returncode == 3
    last = proc.stderr.strip().splitlines()[-1]
    assert last.startswith("Note: the 'python' on PATH")
    assert "Microsoft Store alias" in last


@needs_ps
@pytest.mark.parametrize("method", ["venv", "uv"])
def test_ps1_plan_ends_with_the_selftest_command(tmp_path, method):
    home_dir = tmp_path.joinpath(*ODD_HOME)
    home_dir.mkdir(parents=True)
    env = home(home_dir)
    fakes = tmp_path / "fakes"
    fake_tool(fakes, "python" if method == "venv" else "uv", *exits(0))
    env["PATH"] = str(fakes)
    proc = run_rc(canonical_ps("-DryRun"), env)
    assert proc.returncode == 0, proc.stderr
    prefix = "PLAN: print the selftest command: "
    last = proc.stdout.splitlines()[-1]
    if method == "uv":
        assert last == prefix + "& '<uv tool bin folder>\\tutor-any-lecture.exe' selftest"
        return
    local = env.get("LOCALAPPDATA") or str(home_dir) + "\\AppData\\Local"
    cli = local + "\\tutor-any-lecture\\venv\\Scripts\\tutor-any-lecture.exe"
    assert last == prefix + "& '" + cli.replace("'", "''") + "' selftest"


@needs_ps
def test_ps1_plan_asks_doctor_about_this_skill(tmp_path):
    proc = run_rc(ps("-DryRun"), home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    skill = ROOT / "skills" / "tutor-any-lecture"
    assert f'PLAN: run tutor-any-lecture doctor --json --skill "{skill}"' in proc.stdout.splitlines()


# ---- packaging ------------------------------------------------------------------


def test_sdist_includes_only_public_files():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"^\[tool\.hatch\.build\.targets\.sdist\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    assert section, "no sdist target"
    include = re.search(r"^include\s*=\s*\[(.*?)\]", section.group(1), re.M | re.S)
    assert include, "no include list"
    entries = re.findall(r'"([^"]*)"', include.group(1))
    # Each entry is anchored at the repository root, so none matches at any depth.
    assert entries == [
        "/src",
        "/README.md",
        "/README.zh-CN.md",
        "/LICENSE",
        "/THIRD_PARTY_NOTICES.md",
        "/pyproject.toml",
    ]


def ci_steps():
    import yaml

    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def test_ci_runs_the_installer_under_windows_powershell_5_1():
    runs = [s["run"] for s in ci_steps() if s.get("shell") == "powershell"]
    base = "powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1"
    assert any(base + " -DryRun" in r for r in runs)
    assert any(base + " -Yes -From . -Agents claude" in r for r in runs)
    assert any("cli-path" in r and "selftest" in r for r in runs)
    # The 5.1 install must write cli-path itself: the earlier pwsh install's file is removed first.
    real = [r for r in runs if base + " -Yes -From . -Agents claude" in r]
    assert len(real) == 1
    removal = real[0].find("Remove-Item")
    assert removal != -1 and "cli-path" in real[0][removal:real[0].find(base)]
    assert removal < real[0].find(base)


def test_ci_installs_from_a_folder_with_space_and_cjk_on_every_os():
    runs = [s.get("run", "") for s in ci_steps()]
    odd = [r for r in runs if "课程 资料" in r and "selftest" in r]
    assert any("install.sh" in r for r in odd) and any("install.ps1" in r for r in odd)


def test_ci_never_installs_asr_and_doctor_must_be_ready():
    runs = [s.get("run", "") for s in ci_steps()]
    assert not any("asr" in r.lower() for r in runs)
    doctor = [r for r in runs if "doctor" in r]
    assert doctor
    assert not any("-eq 3" in r for r in doctor)
