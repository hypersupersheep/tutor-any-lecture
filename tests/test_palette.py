import json
import re
from pathlib import Path

import pytest

from tutor_any_lecture.palette import load_palette

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "tutor_any_lecture"

ROLES = {
    "ink": "#121212",
    "paper": "#FDFDFC",
    "source": "#1D2BD6",
    "correction": "#D3222A",
    "highlight": "#FFF24A",
    "progress_pre": "#B8B8B8",
    "progress_post": "#121212",
    "progress_d7": "#5F5F5F",
}


def write_palette(path, roles):
    path.write_text(json.dumps(roles, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def test_packaged_palette_has_every_role():
    palette = load_palette()
    assert palette == ROLES
    assert all(value.lower() != "#d97757" for value in palette.values())


def test_palette_missing_role_is_named(tmp_path):
    roles = {k: v for k, v in ROLES.items() if k not in ("source", "ink")}
    path = write_palette(tmp_path / "palette.json", roles)
    with pytest.raises(ValueError) as e:
        load_palette(path)
    assert str(e.value).endswith("missing role(s): ink, source")


def test_palette_bad_value_is_named(tmp_path):
    path = write_palette(tmp_path / "palette.json", {**ROLES, "ink": "#12345"})
    with pytest.raises(ValueError) as e:
        load_palette(path)
    assert str(e.value) == "palette.json: ink must be #RRGGBB, got '#12345'"


def test_no_colour_literal_in_package_code():
    colour = re.compile(r"#[0-9A-Fa-f]{6}\b")
    files = sorted(PACKAGE.rglob("*.py"))
    assert files
    found = [
        f"{path.relative_to(PACKAGE)}:{n}"
        for path in files
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if colour.search(line)
    ]
    assert found == []
