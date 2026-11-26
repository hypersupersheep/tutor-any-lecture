"""The colour roles every renderer draws with, read from ``data/palette.json``.

No renderer holds a colour of its own: each asks ``load_palette()`` for a role's value,
so one file decides how every page and chart looks.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

ROLES = (
    "ink", "paper", "source", "correction", "highlight",
    "progress_pre", "progress_post", "progress_d7",
)
_COLOUR_RE = re.compile(r"#[0-9A-Fa-f]{6}")  # applied with fullmatch


def load_palette(path: Path | None = None) -> dict[str, str]:
    """Each role's colour, ``#RRGGBB``: from ``path``, or from the packaged ``data/palette.json``.

    A missing role or a value of another form raises ValueError naming it.
    """
    if path is None:
        text = resources.files("tutor_any_lecture").joinpath("data", "palette.json").read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ValueError(f"palette.json: not valid JSON: {e}") from None
    if not isinstance(data, dict):
        raise ValueError("palette.json: the top level must be an object")
    missing = sorted(role for role in ROLES if role not in data)
    if missing:
        raise ValueError(f"palette.json: missing role(s): {', '.join(missing)}")
    for role in ROLES:
        value = data[role]
        if not (isinstance(value, str) and _COLOUR_RE.fullmatch(value)):
            raise ValueError(f"palette.json: {role} must be #RRGGBB, got '{value}'")
    return {role: data[role] for role in ROLES}
