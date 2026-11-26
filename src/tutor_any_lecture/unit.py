"""The unit folder contract: fixed file names inside one lecture unit."""

from __future__ import annotations

from pathlib import Path

from .plan import Plan, PlanError, load_plan, safe_name


class UnitPaths:
    """Paths of the files in a unit folder. Only ``ensure()`` touches the disk."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @property
    def transcript(self) -> Path:
        return self.root / "sources" / "transcript.json"

    @property
    def source(self) -> Path:
        return self.root / "sources" / "source.json"

    @property
    def chapters(self) -> Path:
        return self.root / "sources" / "chapters.json"

    @property
    def suspects(self) -> Path:
        return self.root / "sources" / "suspects.json"

    @property
    def pages(self) -> Path:
        return self.root / "sources" / "slides" / "pages.json"

    @property
    def plan(self) -> Path:
        return self.root / "plan.json"

    @property
    def explanation(self) -> Path:
        return self.root / "explanation.md"

    @property
    def items(self) -> Path:
        return self.root / "items.json"

    @property
    def assignment(self) -> Path:
        return self.root / "assignment.json"

    @property
    def cards_json(self) -> Path:
        return self.root / "cards.json"

    @property
    def cards_tsv(self) -> Path:
        return self.root / "cards.tsv"

    @property
    def map(self) -> Path:
        return self.root / "map.json"

    @property
    def mermaid(self) -> Path:
        return self.root / "overview.mmd"

    @property
    def verify(self) -> Path:
        return self.root / "verify.json"

    def ensure(self) -> UnitPaths:
        """Create ``sources/slides/`` (and its parents) and return ``self``."""
        (self.root / "sources" / "slides").mkdir(parents=True, exist_ok=True)
        return self


def refuse_overwrite(unit: Path, force: bool) -> None:
    """The overwrite guard every acquisition calls first, before it reads its input.

    Keyed on transcript.json only: a slides-only source.json may be replaced freely.
    """
    transcript = UnitPaths(unit).transcript
    if transcript.exists() and not force:
        raise FileExistsError(f"{transcript} already exists; rerun with --force to replace it")


def _plan_of(path: Path, course: str, unit: str) -> Plan | None:
    """The plan at ``path`` when it loads and names ``course`` and ``unit``; otherwise None."""
    try:
        plan = load_plan(path)
    except (PlanError, ValueError, OSError, RecursionError):
        return None
    return plan if (plan.course, plan.unit) == (course, unit) else None


def find_unit(workspace: Path, course: str, unit: str) -> tuple[Path, Plan] | None:
    """The folder of the unit ``unit`` of ``course`` and the plan loaded there, or None.

    ``<workspace>/courses/<course>/<unit>/plan.json`` comes first; else the first, in sorted
    path order, of ``<workspace>/courses/*/*/plan.json`` whose course and unit match. A plan
    that does not load is skipped without a message. Nothing is written.
    """
    courses = Path(workspace) / "courses"
    direct = None
    try:
        direct = courses / safe_name(course, "course") / safe_name(unit, "unit") / "plan.json"
    except PlanError:
        pass  # not a folder name: only the search below can find it
    candidates = [direct] if direct is not None else []
    candidates += [p for p in sorted(courses.glob("*/*/plan.json")) if p != direct]
    for path in candidates:
        plan = _plan_of(path, course, unit)
        if plan is not None:
            return path.parent, plan
    return None
