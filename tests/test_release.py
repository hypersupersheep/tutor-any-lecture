# tests/test_release.py
import ast
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from packaging.version import Version

from tools.build_skill_zip import build_zip, skill_folders
from tools.build_skill_zip import main as zip_main
from tools.release_check import check, main, semver_to_pep440

ROOT = Path(__file__).resolve().parents[1]
SCHEME_MESSAGE = "is not X.Y.Z, X.Y.Z-dev.N or X.Y.Z-rc.N"


# ---- local helpers ----

def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_tree(root: Path, release_id: str, changelog: str | None = None) -> Path:
    """Write the five places that carry the release id, plus a CHANGELOG.md, all agreeing on release_id."""
    skill = root / "skills" / "tutor-any-lecture"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "VERSION").write_text(release_id + "\n", encoding="utf-8", newline="\n")
    package = root / "src" / "tutor_any_lecture"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text(
        f'"""A synthetic package."""\n\n__version__ = "{semver_to_pep440(release_id)}"\n',
        encoding="utf-8",
        newline="\n",
    )
    plugin_dir = root / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    write_json(plugin_dir / "plugin.json", {"name": "tutor-any-lecture", "version": release_id})
    write_json(
        plugin_dir / "marketplace.json",
        {
            "name": "tutor-any-lecture",
            "owner": {"name": "Test"},
            "metadata": {"version": release_id},
            "plugins": [
                {"name": "other-plugin", "version": "0.0.1"},
                {"name": "tutor-any-lecture", "version": release_id},
            ],
        },
    )
    if changelog is None:
        changelog = f"# Changelog\n\nNewest first.\n\n## {release_id}\n\n- Something a learner can do.\n"
    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8", newline="\n")
    return root


def set_init_version(root: Path, value: str) -> None:
    (root / "src" / "tutor_any_lecture" / "__init__.py").write_text(
        f'__version__ = "{value}"\n', encoding="utf-8", newline="\n"
    )


def set_plugin_version(root: Path, value) -> None:
    path = root / ".claude-plugin" / "plugin.json"
    data = read_json(path)
    if value is None:
        del data["version"]
    else:
        data["version"] = value
    write_json(path, data)


def set_metadata_version(root: Path, value: str) -> None:
    path = root / ".claude-plugin" / "marketplace.json"
    data = read_json(path)
    data["metadata"]["version"] = value
    write_json(path, data)


def set_market_plugin_version(root: Path, value: str) -> None:
    path = root / ".claude-plugin" / "marketplace.json"
    data = read_json(path)
    for entry in data["plugins"]:
        if entry["name"] == "tutor-any-lecture":
            entry["version"] = value
    write_json(path, data)


def git(cwd, *args):
    """Run git in cwd with a fixed identity and no signing; return the CompletedProcess."""
    cmd = [
        "git",
        "-c", "user.name=Test",
        "-c", "user.email=test@example.invalid",
        "-c", "commit.gpgsign=false",
        "-c", "init.defaultBranch=main",
        *args,
    ]
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


def head_sha(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").stdout.decode("utf-8").strip()


def imported_top_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


# ---- V1: one id, two spellings ----

@pytest.mark.parametrize(
    "semver, twin",
    [
        ("2.0.0", "2.0.0"),
        ("2.0.0-dev.0", "2.0.0.dev0"),
        ("2.0.0-rc.1", "2.0.0rc1"),
        ("10.20.30-rc.12", "10.20.30rc12"),
    ],
)
def test_pep440_twin_of_each_form(semver, twin):
    assert semver_to_pep440(semver) == twin
    assert str(Version(semver)) == twin


@pytest.mark.parametrize(
    "text",
    [
        "2.0.0.dev0",
        "2.0.0-dev",
        "2.0.0-rc",
        "2.0.0-beta.1",
        "v2.0.0",
        "2.0",
        "02.0.0",
        "2.0.0-rc.01",
        "２.0.0",
        " 2.0.0",
        "2.0.0\n",
    ],
)
def test_ids_outside_the_scheme_are_refused(text):
    with pytest.raises(ValueError) as err:
        semver_to_pep440(text)
    assert str(err.value) == f"'{text}' {SCHEME_MESSAGE}"


# ---- V2: five places agree ----

def test_a_consistent_tree_has_no_problems(tmp_path):
    write_tree(tmp_path, "2.0.0-rc.1")
    assert check(tmp_path) == []


@pytest.mark.parametrize(
    "change, expected",
    [
        (
            lambda root: set_init_version(root, "2.0.0rc2"),
            "src/tutor_any_lecture/__init__.py: __version__ is '2.0.0rc2', expected '2.0.0rc1'",
        ),
        (
            lambda root: set_plugin_version(root, "2.0.0-rc.2"),
            ".claude-plugin/plugin.json: version is '2.0.0-rc.2', expected '2.0.0-rc.1'",
        ),
        (
            lambda root: set_metadata_version(root, "2.0.0-rc.2"),
            ".claude-plugin/marketplace.json: metadata.version is '2.0.0-rc.2', expected '2.0.0-rc.1'",
        ),
        (
            lambda root: set_market_plugin_version(root, "2.0.0-rc.2"),
            ".claude-plugin/marketplace.json: plugins[tutor-any-lecture].version is '2.0.0-rc.2', "
            "expected '2.0.0-rc.1'",
        ),
        (
            lambda root: set_plugin_version(root, None),
            ".claude-plugin/plugin.json: version is missing, expected '2.0.0-rc.1'",
        ),
    ],
    ids=["init", "plugin", "metadata", "market-plugin", "plugin-missing-key"],
)
def test_each_place_that_disagrees_is_named(tmp_path, change, expected):
    write_tree(tmp_path, "2.0.0-rc.1")
    change(tmp_path)
    assert check(tmp_path) == [expected]


def test_a_bad_version_file_stops_the_check(tmp_path):
    write_tree(tmp_path, "2.0.0-rc.1")
    version = tmp_path / "skills" / "tutor-any-lecture" / "VERSION"

    version.write_text("2.0.0.dev0\n", encoding="utf-8", newline="\n")
    assert check(tmp_path) == [f"VERSION: '2.0.0.dev0' {SCHEME_MESSAGE}"]

    version.write_text("2.0.0-rc.1", encoding="utf-8", newline="\n")
    assert check(tmp_path) == ["VERSION: must be one line holding the release id, then a newline"]

    version.unlink()
    assert check(tmp_path) == ["VERSION: missing"]


# ---- V3: the newest CHANGELOG entry is the release ----

def test_changelog_heading_may_carry_a_date(tmp_path):
    write_tree(tmp_path, "2.0.0-rc.1", "# Changelog\n\n## 2.0.0-rc.1 - 2026-12-01\n\n- A note.\n")
    assert check(tmp_path) == []

    write_tree(tmp_path, "2.0.0-rc.1", "# Changelog\n\n## [2.0.0-rc.1]\n\n- A note.\n")
    assert check(tmp_path) == ["CHANGELOG.md: newest heading is '## [2.0.0-rc.1]', expected '## 2.0.0-rc.1'"]


def test_an_older_entry_on_top_is_named(tmp_path):
    write_tree(tmp_path, "2.0.0-rc.2", "# Changelog\n\n## 2.0.0-rc.1\n\n- A note.\n")
    assert check(tmp_path) == ["CHANGELOG.md: newest heading is '## 2.0.0-rc.1', expected '## 2.0.0-rc.2'"]


def test_an_empty_entry_is_a_problem(tmp_path):
    write_tree(tmp_path, "2.0.0-rc.2", "# Changelog\n\n## 2.0.0-rc.2\n\n\n## 2.0.0-rc.1\n\n- Older.\n")
    assert check(tmp_path) == ["CHANGELOG.md: the entry for 2.0.0-rc.2 is empty"]


def test_notes_are_the_newest_entry(tmp_path, capsys):
    changelog = (
        "# Changelog\n\nNewest first.\n\n"
        "## 2.0.0-rc.2 - 2026-12-08\n\n"
        "- First new thing.\n"
        "### Fixed\n"
        "- A fix.\n\n"
        "## 2.0.0-rc.1\n\n"
        "- Older thing.\n"
    )
    tree = write_tree(tmp_path / "tree", "2.0.0-rc.2", changelog)
    notes = tmp_path / "notes.md"
    assert main(["--root", str(tree), "--notes", str(notes)]) == 0
    assert notes.read_text(encoding="utf-8") == "- First new thing.\n### Fixed\n- A fix.\n"
    out = json.loads(capsys.readouterr().out)
    assert out["path"] == str(notes)


# ---- V4: the tag is v plus VERSION ----

def test_tag_must_be_v_plus_version(tmp_path):
    write_tree(tmp_path, "2.0.0-rc.1")
    assert check(tmp_path, tag="v2.0.0rc1") == ["tag: 'v2.0.0rc1' is not 'v2.0.0-rc.1'"]
    assert check(tmp_path, tag="2.0.0-rc.1") == ["tag: '2.0.0-rc.1' is not 'v2.0.0-rc.1'"]


@pytest.mark.parametrize("release_id", ["2.0.0-rc.1", "2.0.0"])
def test_rc_and_final_tags_pass(tmp_path, release_id):
    write_tree(tmp_path, release_id)
    assert check(tmp_path, tag="v" + release_id) == []


def test_dev_id_is_never_tagged(tmp_path):
    write_tree(tmp_path, "2.0.0-dev.0")
    assert check(tmp_path, tag="v2.0.0-dev.0") == [
        "tag: VERSION '2.0.0-dev.0' is a -dev id, and a -dev id is never tagged"
    ]


# ---- V5: the tagged commit is on main ----

@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_commit_not_on_main_is_refused(tmp_path):
    repo = write_tree(tmp_path / "repo", "2.0.0-rc.1")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "--no-verify", "-m", "A")
    a = head_sha(repo)
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "extra.txt").write_text("B\n", encoding="utf-8", newline="\n")
    git(repo, "add", "extra.txt")
    git(repo, "commit", "-q", "--no-verify", "-m", "B")
    b = head_sha(repo)

    assert check(repo, on="main") == [f"git: the tagged commit {b[:7]} is not on main"]

    git(repo, "checkout", "-q", a)
    assert check(repo, on="main") == []

    problems = check(repo, on="nope")
    assert len(problems) == 1
    assert problems[0].startswith("git: cannot check nope: ")


# ---- V6: the check's command line ----

def test_cli_ok_prints_one_json_line(tmp_path, capsys):
    tree = write_tree(tmp_path, "2.0.0-rc.1")
    assert main(["--root", str(tree), "--tag", "v2.0.0-rc.1"]) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"status": "ok", "release_id": "2.0.0-rc.1", "python_version": "2.0.0rc1"}
    assert captured.err == ""


def test_cli_problems_go_to_stderr_and_exit_1(tmp_path, capsys):
    tree = write_tree(tmp_path / "tree", "2.0.0-rc.1")
    set_plugin_version(tree, "2.0.0-rc.2")
    notes = tmp_path / "notes.md"
    assert main(["--root", str(tree), "--tag", "v2.0.0", "--notes", str(notes)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        ".claude-plugin/plugin.json: version is '2.0.0-rc.2', expected '2.0.0-rc.1'",
        "tag: 'v2.0.0' is not 'v2.0.0-rc.1'",
    ]
    assert not notes.exists()


def test_cli_unknown_option_exits_2(capsys):
    with pytest.raises(SystemExit) as err:
        main(["--bogus"])
    assert err.value.code == 2


def test_check_runs_as_a_plain_script(tmp_path):
    tree = write_tree(tmp_path / "课程 资料", "2.0.0-rc.1")
    proc = subprocess.run(
        [sys.executable, "tools/release_check.py", "--root", str(tree)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["release_id"] == "2.0.0-rc.1"


# ---- V7 and C1: today's id and its CHANGELOG entry ----

def repository_release_id() -> str:
    return (ROOT / "skills" / "tutor-any-lecture" / "VERSION").read_text(encoding="utf-8").strip()


def test_repository_release_identity_agrees():
    import tutor_any_lecture

    assert check(ROOT) == []
    assert tutor_any_lecture.__version__ == semver_to_pep440(repository_release_id())


def test_changelog_entry_for_this_version(tmp_path, capsys):
    notes_file = tmp_path / "notes.md"
    assert main(["--root", str(ROOT), "--notes", str(notes_file)]) == 0
    capsys.readouterr()
    notes = notes_file.read_text(encoding="utf-8")
    bullets = [line for line in notes.splitlines() if line.startswith("- ")]
    assert 5 <= len(bullets) <= 9
    for pattern in (r"\bM[12][a-c]?\b", "TBD", "later version", "next version", "coming soon"):
        assert not re.search(pattern, notes, re.IGNORECASE), pattern


def test_release_tools_use_only_the_standard_library():
    for name in ("release_check.py", "build_skill_zip.py"):
        for module in imported_top_names(ROOT / "tools" / name):
            assert module in sys.stdlib_module_names, f"{name} imports {module}"


# ---- Z1 to Z3: one upload-ready ZIP per skill folder ----

def write_skill_tree(root: Path) -> Path:
    demo = root / "skills" / "demo"
    for rel, data in (
        ("SKILL.md", b"---\nname: demo\n---\n# Demo\n"),
        ("scripts/run.sh", b"#!/usr/bin/env bash\necho demo\n"),
        ("references/课程 资料.md", "# 资料\n".encode("utf-8")),
        ("__pycache__/x.pyc", b"\x00\x01"),
        (".DS_Store", b"\x00"),
    ):
        path = demo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    empty = root / "skills" / "empty"
    empty.mkdir(parents=True)
    (empty / "notes.md").write_text("no skill here\n", encoding="utf-8", newline="\n")
    return root


def test_zip_holds_the_skill_folder_at_the_top(tmp_path):
    tree = write_skill_tree(tmp_path / "tree")
    folders = skill_folders(tree)
    assert [f.name for f in folders] == ["demo"]
    out = tmp_path / "out"
    out.mkdir()
    built = [build_zip(f, out) for f in folders]
    assert built == [out / "demo.zip"]
    assert sorted(p.name for p in out.iterdir()) == ["demo.zip"]
    with zipfile.ZipFile(out / "demo.zip") as zf:
        assert zf.namelist() == ["demo/SKILL.md", "demo/references/课程 资料.md", "demo/scripts/run.sh"]


def test_repository_zips_are_upload_ready(tmp_path):
    folders = skill_folders(ROOT)
    assert "tutor-any-lecture" in [f.name for f in folders]
    for folder in folders:
        build_zip(folder, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(f.name + ".zip" for f in folders)
    with zipfile.ZipFile(tmp_path / "tutor-any-lecture.zip") as zf:
        names = zf.namelist()
        assert all(name.startswith("tutor-any-lecture/") for name in names)
        for name in ("tutor-any-lecture/SKILL.md", "tutor-any-lecture/VERSION", "tutor-any-lecture/scripts/install.sh"):
            assert name in names
        assert zf.read("tutor-any-lecture/SKILL.md") == (ROOT / "skills" / "tutor-any-lecture" / "SKILL.md").read_bytes()


def test_zip_bytes_are_reproducible(tmp_path):
    tree = write_skill_tree(tmp_path / "tree")
    first, second = tmp_path / "one", tmp_path / "two"
    first.mkdir()
    second.mkdir()
    folder = tree / "skills" / "demo"
    build_zip(folder, first)
    build_zip(folder, second)
    assert (first / "demo.zip").read_bytes() == (second / "demo.zip").read_bytes()
    with zipfile.ZipFile(first / "demo.zip") as zf:
        infos = {info.filename: info for info in zf.infolist()}
    assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos.values())
    assert (infos["demo/scripts/run.sh"].external_attr >> 16) & 0o777 == 0o755
    assert (infos["demo/SKILL.md"].external_attr >> 16) & 0o777 == 0o644


def test_zip_cli_prints_the_paths(tmp_path, capsys):
    tree = write_skill_tree(tmp_path / "tree")
    out = tmp_path / "dist" / "new"
    (tree / "skills" / "second").mkdir()
    (tree / "skills" / "second" / "SKILL.md").write_text("# Second\n", encoding="utf-8", newline="\n")
    assert zip_main(["--out", str(out), "--root", str(tree)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"paths": [str(out / "demo.zip"), str(out / "second.zip")]}
    assert (out / "demo.zip").is_file() and (out / "second.zip").is_file()
    # a second run replaces the files of the same name
    assert zip_main(["--out", str(out), "--root", str(tree)]) == 0
    assert json.loads(capsys.readouterr().out) == printed


def test_zip_cli_without_skills_exits_1(tmp_path, capsys):
    (tmp_path / "skills" / "empty").mkdir(parents=True)
    assert zip_main(["--out", str(tmp_path / "dist"), "--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [f"no skill folder with a SKILL.md under {tmp_path / 'skills'}"]


# ---- R1 and R2: the release workflow ----

def load_workflow(name: str) -> dict:
    import yaml

    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def trigger(workflow: dict):
    # PyYAML reads the key `on` as True.
    return workflow.get("on", workflow.get(True))


def runs(job: dict) -> list[str]:
    return [step["run"] for step in job.get("steps", []) if "run" in step]


def test_release_workflow_runs_only_on_version_tags():
    assert trigger(load_workflow("release.yml")) == {"push": {"tags": ["v*"]}}


def test_only_the_publish_job_may_write():
    wf = load_workflow("release.yml")
    assert wf["permissions"] == {"contents": "read"}
    for name, job in wf["jobs"].items():
        if name == "publish":
            assert job["permissions"] == {"contents": "write"}
        else:
            assert "permissions" not in job, name


def test_ci_can_be_called_by_the_release():
    on = trigger(load_workflow("ci.yml"))
    assert "workflow_call" in on
    assert "push" in on and "pull_request" in on


def test_release_workflow_checks_identity_and_main_first():
    check_job = load_workflow("release.yml")["jobs"]["check"]
    assert "needs" not in check_job
    assert check_job["runs-on"] == "ubuntu-latest"
    checkout = next(s for s in check_job["steps"] if s.get("uses") == "actions/checkout@v4")
    assert checkout["with"]["fetch-depth"] == 0
    setup = next(s for s in check_job["steps"] if s.get("uses") == "actions/setup-python@v5")
    assert str(setup["with"]["python-version"]) == "3.12"
    commands = "\n".join(runs(check_job))
    assert "git fetch --no-tags origin +refs/heads/main:refs/remotes/origin/main" in commands
    assert 'tools/release_check.py --tag "$GITHUB_REF_NAME" --on origin/main' in commands


def test_release_workflow_runs_the_ci_workflow():
    test_job = load_workflow("release.yml")["jobs"]["test"]
    assert test_job["uses"] == "./.github/workflows/ci.yml"
    assert test_job["needs"] == "check"


def test_release_workflow_publishes_after_check_and_tests():
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    publish = load_workflow("release.yml")["jobs"]["publish"]
    assert publish["needs"] == ["check", "test"]
    commands = runs(publish)
    joined = "\n".join(commands)
    assert '--notes "$RUNNER_TEMP/notes.md"' in joined
    assert "tools/build_skill_zip.py --out dist" in joined
    release = [c for c in commands if "gh release create" in c]
    assert len(release) == 1
    for part in ("dist/*.zip", "--verify-tag", '--notes-file "$RUNNER_TEMP/notes.md"', "--prerelease"):
        assert part in release[0], part
    assert "secrets." not in text
