import ast
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SYSTEMS = {"ubuntu-latest", "macos-latest", "windows-latest"}
POSIX_INSTALL = "bash install.sh --yes --from . --agents claude"
WINDOWS_INSTALL = "powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Yes -From . -Agents claude"


def workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def job(name: str, job_name: str) -> dict:
    jobs = workflow(name)["jobs"]
    assert job_name in jobs, f"{name} has no job {job_name}"
    return jobs[job_name]


def runs(job_: dict) -> list[str]:
    return [step.get("run", "") for step in job_["steps"]]


def uses(job_: dict) -> list[str]:
    return [step.get("uses", "") for step in job_["steps"]]


def assert_three_systems(job_: dict) -> None:
    strategy = job_["strategy"]
    assert set(strategy["matrix"]["os"]) == SYSTEMS
    assert strategy["fail-fast"] is False


def assert_python_3_12(job_: dict) -> None:
    setup = [s for s in job_["steps"] if s.get("uses") == "actions/setup-python@v5"]
    assert len(setup) == 1 and str(setup[0]["with"]["python-version"]) == "3.12"


def module_imports(tree: ast.Module) -> list[str]:
    """Modules imported at module level, inside module-level if and try blocks too."""
    names = []

    def visit(statements) -> None:
        for node in statements:
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.append(node.module)
            elif isinstance(node, ast.If):
                visit(node.body)
                visit(node.orelse)
            elif isinstance(node, ast.Try):
                visit(node.body)
                for handler in node.handlers:
                    visit(handler.body)
                visit(node.orelse)
                visit(node.finalbody)

    visit(tree.body)
    return names


@pytest.mark.parametrize("script", ["tools/doc_commands.py", "tools/synthetic_lecture.py"])
def test_tools_run_on_a_bare_python(script):
    tree = ast.parse((ROOT / script).read_text(encoding="utf-8"))
    imported = module_imports(tree)
    assert imported
    outside = [name for name in imported if name.split(".")[0] not in sys.stdlib_module_names]
    assert outside == []


def test_ci_installs_without_uv_on_every_system():
    no_uv = job("ci.yml", "install-no-uv")
    assert_three_systems(no_uv)
    assert_python_3_12(no_uv)
    assert not any(u.startswith("astral-sh/setup-uv") for u in uses(no_uv))
    texts = runs(no_uv)
    # The first step that runs anything fails when uv is on PATH.
    first = next(r for r in texts if r)
    assert "uv" in first and "exit 1" in first
    assert len([r for r in texts if "PLAN: python -m venv" in r]) >= 2
    assert any(POSIX_INSTALL in r for r in texts)
    assert any(WINDOWS_INSTALL in s.get("run", "") and s.get("shell") == "pwsh" for s in no_uv["steps"])
    assert len([r for r in texts if "cli-path" in r and "venv" in r and "selftest" in r]) >= 2


def test_ci_runs_the_readme_install_command():
    readme = job("ci.yml", "readme-install")
    assert_three_systems(readme)
    assert_python_3_12(readme)
    assert any(u.startswith("astral-sh/setup-uv") for u in uses(readme))
    text = "\n".join(runs(readme))
    for needed in [
        "install-command --system posix",
        "install-command --system windows",
        'eval "$cmd"',
        "Invoke-Expression $cmd",
        "git clone",
        "SKILL.md",
        "selftest",
        "cli-path",
    ]:
        assert needed in text, needed


@pytest.mark.parametrize("name", ["ci.yml"])
def test_windows_steps_end_with_their_exit_code(name):
    steps = [s for j in workflow(name)["jobs"].values() for s in j["steps"]]
    windows = [s for s in steps if s.get("shell") in ("pwsh", "powershell")]
    assert windows
    endings = {s.get("name", ""): s["run"].rstrip().splitlines()[-1].strip() for s in windows}
    assert {n: e for n, e in endings.items() if e != "exit $LASTEXITCODE"} == {}
