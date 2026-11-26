"""Run the bundled sample unit through the offline pipeline, up to the delivery gate.

``run_selftest`` copies one bundled sample into a unit folder and runs import → slides →
items assign → cards export → map mermaid → verify on it: ``en`` (the default), the
English note in ``data/sample/``, or ``zh``, a Chinese note of the same lecture in
``data/sample-zh/``, which shares the lecture and the slides of ``data/sample/``. It
needs no ASR, no network, no profile and no config dir, so it also runs from an
installed wheel on a fresh machine.
"""

from __future__ import annotations

import tempfile
from importlib import resources
from pathlib import Path
from shutil import rmtree

from .acquire.importer import import_transcript
from .cards import export_tsv
from .conceptmap import export_mermaid
from .items import assign_unit
from .plan import load_plan
from .slides import extract_pdf
from .unit import UnitPaths
from .verify import run_verify

# Sample files copied to the unit root, and the inputs copied to <unit>/sources/.
ROOT_FILES = ("plan.json", "explanation.md", "items.json", "cards.json", "map.json")
SOURCE_FILES = ("lecture.vtt", "slides.pdf")
# Each sample's folder under data/; every sample takes its SOURCE_FILES from data/sample/.
SAMPLES = {"en": "sample", "zh": "sample-zh"}


def _check_sample(sample: str) -> None:
    if sample not in SAMPLES:
        raise ValueError(f"unknown sample {sample!r}; expected one of {', '.join(SAMPLES)}")


def _read_sample(sample: str = "en") -> dict[str, bytes]:
    """Every file of one sample, its bytes by name: the root files from the sample's folder,
    the source files from data/sample/. Raises ValueError for an unknown sample and
    FileNotFoundError when a file is missing."""
    _check_sample(sample)
    data = resources.files("tutor_any_lecture").joinpath("data")
    out: dict[str, bytes] = {}
    for name in SOURCE_FILES + ROOT_FILES:
        folder = SAMPLES["en"] if name in SOURCE_FILES else SAMPLES[sample]
        f = data.joinpath(folder, name)
        if not f.is_file():
            raise FileNotFoundError(f"sample file missing from the package: data/{folder}/{name}")
        out[name] = f.read_bytes()
    return out


def _copy_sample(files: dict[str, bytes], unit: Path) -> None:
    (unit / "sources").mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        target = unit / "sources" / name if name in SOURCE_FILES else unit / name
        target.write_bytes(data)


def _run_steps(unit: Path) -> list[dict]:
    """Run the six steps in order and stop at the first one that fails. "items assign" and
    "map mermaid" call the functions behind those commands, so the map is validated too."""
    paths = UnitPaths(unit)

    def import_step() -> tuple[bool, str]:
        # The lecture length for the transcript's health comes from plan.json.
        plan = load_plan(paths.plan)
        h = import_transcript(unit / "sources" / "lecture.vtt", unit, float(plan.duration_s), False)
        verdict = "healthy" if h.ok else "unhealthy"
        return h.ok, f"transcript {verdict} (coverage {h.coverage:.2f}, repetition {h.repetition:.2f})"

    def slides_step() -> tuple[bool, str]:
        pages = extract_pdf(unit / "sources" / "slides.pdf", unit)
        return bool(pages), f"{len(pages)} pages"

    def assign_step() -> tuple[bool, str]:
        assign_unit(unit, False)
        return paths.assignment.is_file(), paths.assignment.name

    def cards_step() -> tuple[bool, str]:
        path = export_tsv(unit)
        return path.exists(), path.name

    def map_step() -> tuple[bool, str]:
        # One file (no views, or one view) or one per view; a failing map raises MapInvalid.
        written = export_mermaid(unit)
        written = written if isinstance(written, list) else [written]
        return all(path.is_file() for path in written), ", ".join(path.name for path in written)

    def verify_step() -> tuple[bool, str]:
        result = run_verify(unit)
        ok = result["overall"] == "PASS"
        failed = [c["name"] for c in result["checks"] if c["status"] == "FAIL"]
        detail = result["report"] if ok else f"{result['report']} FAIL: {', '.join(failed)}"
        return ok, detail

    steps: list[dict] = []
    for name, step in (
        ("import", import_step),
        ("slides", slides_step),
        ("items assign", assign_step),
        ("cards export", cards_step),
        ("map mermaid", map_step),
        ("verify", verify_step),
    ):
        try:
            ok, detail = step()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        steps.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            break
    return steps


def _run(files: dict[str, bytes], unit: Path) -> dict:
    _copy_sample(files, unit)
    steps = _run_steps(unit)
    return {"ok": len(steps) == 6 and all(s["ok"] for s in steps), "steps": steps}


def run_selftest(tmp: Path | None = None, sample: str = "en") -> dict:
    """Generate the unit of one bundled sample (``en`` or ``zh``) and run the offline
    pipeline on it.

    With ``tmp``, the unit is generated in that folder (created if missing) and left
    there; a ``tmp`` that exists and is not an empty directory raises FileExistsError
    before anything is written. Without it, a temporary folder is used and removed. An
    unknown ``sample`` raises ValueError before anything is written.
    """
    _check_sample(sample)
    if tmp is not None:
        tmp = Path(tmp)
        if tmp.exists() and (not tmp.is_dir() or any(tmp.iterdir())):
            raise FileExistsError(f"{tmp} exists and is not empty; pick a new or empty folder")
    files = _read_sample(sample)
    if tmp is not None:
        tmp.mkdir(parents=True, exist_ok=True)
        return _run(files, tmp)
    d = Path(tempfile.mkdtemp(prefix="tutor-any-lecture-selftest-"))
    try:
        return _run(files, d / "unit")
    finally:
        # A cleanup that fails (a file Windows still holds open, a folder that refuses
        # removal) never changes the result: what cannot be removed stays in the system
        # temp folder.
        try:
            rmtree(d)
        except OSError:
            pass
