"""Build one upload-ready ZIP per skill folder, with the folder at the top of the archive.

skills/<name>/ holding a SKILL.md becomes <out>/<name>.zip, whose entries are
<name>/<path inside the folder>. This is the archive a person uploads to Claude on the
web. The name carries no version, so a link to the latest release's asset never changes.

Builds of the same tree with the same Python give the same bytes: entries are written
in sorted order with a fixed date, system and mode, whatever the clock, the checkout's
file modes or the folder walk order.

Standard library only; the package is never imported.

    python tools/build_skill_zip.py --out DIR [--root DIR]
"""

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

SKIPPED_DIRS = {"__pycache__", ".git"}
SKIPPED_FILES = {".DS_Store"}
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
UNIX = 3


def skill_folders(root) -> list[Path]:
    """The direct children of root/skills that hold a SKILL.md, sorted by name."""
    skills = Path(root) / "skills"
    if not skills.is_dir():
        return []
    found = [child for child in skills.iterdir() if child.is_dir() and (child / "SKILL.md").is_file()]
    return sorted(found, key=lambda child: child.name)


def _entries(folder: Path) -> list[tuple[str, Path]]:
    """(archive name, file) for every file kept, sorted by archive name."""
    entries = []
    for current, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS]
        for filename in filenames:
            if filename in SKIPPED_FILES or filename.endswith(".pyc"):
                continue
            path = Path(current) / filename
            entries.append((f"{folder.name}/{path.relative_to(folder).as_posix()}", path))
    return sorted(entries)


def build_zip(folder, out_dir) -> Path:
    """Write out_dir/<folder name>.zip and return its path."""
    folder = Path(folder)
    target = Path(out_dir) / f"{folder.name}.zip"
    with zipfile.ZipFile(target, "w") as archive:
        for name, path in _entries(folder):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = UNIX
            mode = 0o755 if name.endswith(".sh") else 0o644
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, path.read_bytes())
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_skill_zip.py",
        description="Build one upload-ready ZIP per skill folder.",
    )
    parser.add_argument("--out", type=Path, required=True, help="folder to write the ZIPs into")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="repository root (default: the folder above tools/)")
    args = parser.parse_args(argv)

    folders = skill_folders(args.root)
    if not folders:
        print(f"no skill folder with a SKILL.md under {args.root / 'skills'}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    paths = sorted(str(build_zip(folder, args.out)) for folder in folders)
    # Non-ASCII is escaped only on Windows, where the console may not be UTF-8.
    print(json.dumps({"paths": paths}, ensure_ascii=sys.platform == "win32"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
