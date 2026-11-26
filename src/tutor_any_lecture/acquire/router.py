"""Classify the files in a materials folder and plan the acquisition commands.

``route()`` only plans: it starts no process, writes no file, creates no folder and
makes no network call. The only files it opens are the ``.json``, ``.txt`` and ``.docx``
files in the folder: a ``.txt`` or ``.docx`` is a transcript only when it has time stamps.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..office import docx_lines
from ..slides import photo_order
from ..source import SLIDE_DECK_SUFFIXES, SLIDE_PHOTO_SUFFIXES
from ..transcript import parse_meeting_export, parse_txt
from ..unit import UnitPaths
from .panopto import load_extract

T = "tutor-any-lecture"

# How much of a .txt is read to tell a transcript from other text.
_TXT_HEAD_BYTES = 64 * 1024

_BY_SUFFIX = {
    **{s: "video" for s in (".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v")},
    **{s: "audio" for s in (".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg")},
    **{s: "transcript" for s in (".srt", ".vtt")},
    **{s: "slides" for s in SLIDE_DECK_SUFFIXES},
    **{s: "images" for s in (".jpg", ".jpeg", ".png", ".heic")},
}
_CLASSES = ("video", "audio", "transcript", "slides", "images", "other")

_QUESTION_TEXT = {
    "transcript": "More than one transcript file. Which one belongs to this lecture?",
    "media": "More than one video or audio file. Which one is the lecture recording?",
    "pdf": "More than one PDF. Which one holds the lecture slides?",
    "pptx": "More than one PowerPoint deck. Which one holds the lecture slides?",
    "video": "More than one video file. Which one shows the lecture's slides or board?",
    "unsafe-name": "These file names contain characters that are unsafe on a command line; "
    "rename them, then run the route again.",
}

# Characters a shell would act on. A file whose name holds one is never put into a step:
# an agent that pastes the argv into a shell line would run part of the name.
_UNSAFE_CHARACTERS = frozenset('$`"\\;|&<>')


def _is_unsafe_name(name: str) -> bool:
    return any(c in _UNSAFE_CHARACTERS or ord(c) < 32 or ord(c) == 127 for c in name)


def _is_panopto_extract(path: Path) -> bool:
    """A dict with a ``transcript`` string and no ``segments`` list."""
    try:
        data = load_extract(path)
    except Exception:
        return False
    return isinstance(data.get("transcript"), str) and not isinstance(data.get("segments"), list)


def _is_importable(path: Path) -> bool:
    """A dict with a ``segments`` list, or a non-empty list of dicts with start, end and text."""
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except Exception:
        return False
    if isinstance(data, dict):
        return isinstance(data.get("segments"), list)
    if isinstance(data, list) and data:
        return all(isinstance(e, dict) and {"start", "end", "text"} <= e.keys() for e in data)
    return False


def _is_timed_txt(path: Path) -> bool:
    """The first 64 KiB give a segment, read as ``acquire import`` reads a .txt."""
    try:
        with open(path, "rb") as f:
            text = f.read(_TXT_HEAD_BYTES).decode("utf-8-sig", errors="replace")
        return bool(parse_txt(text, None))
    except Exception:
        return False


def _is_timed_docx(path: Path) -> bool:
    """A .docx whose lines give a segment; one that cannot be read is not a transcript."""
    try:
        return bool(parse_meeting_export(docx_lines(path), None))
    except Exception:
        return False


def route(folder: Path, unit: Path | None = None) -> dict:
    """Return the plan for ``folder``: ``{"files", "slide_source", "steps", "questions"}``."""
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"folder not found: {folder}")
    root = folder.resolve()

    if unit is None:
        u = "<unit>"
        paths = UnitPaths(Path("<unit>"))

        def w(p: Path) -> str:
            return p.as_posix()
    else:
        u = str(Path(unit).resolve())
        paths = UnitPaths(Path(unit).resolve())

        def w(p: Path) -> str:
            return str(p)

    files: dict[str, list[str]] = {c: [] for c in _CLASSES}
    unsafe: list[str] = []  # listed under "other", named in a question, never planned
    panopto: set[str] = set()  # transcript paths that are Panopto extracts
    pdfs: list[str] = []
    pptx: list[str] = []
    for name in sorted(p.name for p in folder.iterdir()):
        if name.startswith("."):
            continue
        path = folder / name
        if not path.is_file():
            continue
        f = str(root / name)
        if _is_unsafe_name(name):
            # Checked before the file is opened or classified.
            files["other"].append(f)
            unsafe.append(f)
            continue
        suffix = path.suffix.lower()
        if suffix == ".json":
            if _is_panopto_extract(path):
                cls = "transcript"
                panopto.add(f)
            elif _is_importable(path):
                cls = "transcript"
            else:
                cls = "other"
        elif suffix == ".txt":
            cls = "transcript" if _is_timed_txt(path) else "other"
        elif suffix == ".docx":
            cls = "transcript" if _is_timed_docx(path) else "other"
        else:
            cls = _BY_SUFFIX.get(suffix, "other")
        files[cls].append(f)
        if suffix == ".pdf":
            pdfs.append(f)
        elif suffix == ".pptx":
            pptx.append(f)

    transcripts = files["transcript"]
    # The images slides --photos reads (JPEG and PNG, never HEIC), in its page order.
    photos = [str(p) for p in photo_order(f for f in files["images"] if Path(f).suffix.lower() in SLIDE_PHOTO_SUFFIXES)]
    # Video and audio together, in file-name order.
    media = sorted(files["video"] + files["audio"], key=lambda s: Path(s).name)

    if pdfs:
        slide_source = "pdf"
    elif pptx:
        slide_source = "pptx"
    elif len(photos) >= 3:
        slide_source = "photos"
    elif len(files["images"]) >= 3:
        slide_source = "photos-deferred"
    elif files["video"]:
        slide_source = "keyframes"
    else:
        slide_source = "none"

    # One recording beside a transcript to import gives the lecture's duration.
    media_for_import = media[0] if len(media) == 1 else None

    def transcript_argv(f: str) -> list[str]:
        if f in panopto:
            return [T, "acquire", "panopto", "--extract", f, "--unit", u]
        if media_for_import is not None:
            return [T, "acquire", "import", "--file", f, "--media", media_for_import, "--unit", u]
        return [T, "acquire", "import", "--file", f, "--unit", u]

    def slides_argv(f: str) -> list[str]:
        return [T, "slides", "--pdf", f, "--unit", u]

    def pptx_argv(f: str) -> list[str]:
        return [T, "slides", "--pptx", f, "--unit", u]

    def photos_argv(fs: list[str]) -> list[str]:
        return [T, "slides", "--photos", *fs, "--unit", u]

    def keyframes_argv(f: str) -> list[str]:
        return [T, "keyframes", "--video", f, "--unit", u]

    def local_argv(f: str) -> list[str]:
        return [T, "acquire", "local", "--file", f, "--unit", u]

    def step(argv, reads, writes, network=False, gpu=False, runnable=True) -> dict:
        return {"argv": argv, "network": network, "gpu": gpu, "reads": reads, "writes": writes, "runnable": runnable}

    steps: list[dict] = []
    if len(transcripts) == 1:
        f = transcripts[0]
        if f in panopto:
            writes = [w(paths.transcript), w(paths.chapters), w(paths.source)]
            reads = [f]
        else:
            writes = [w(paths.transcript), w(paths.source)]
            reads = [f] if media_for_import is None else [f, media_for_import]
        steps.append(step(transcript_argv(f), reads, writes))
    if len(pdfs) == 1:
        f = pdfs[0]
        # slides --pdf records the PDF's digest in source.json, creating it when missing.
        steps.append(step(slides_argv(f), [f], [w(paths.pages), w(paths.source)]))
    elif not pdfs and len(pptx) == 1:
        # A PDF wins over a deck; slides --pptx records its digest as slides --pdf does.
        f = pptx[0]
        steps.append(step(pptx_argv(f), [f], [w(paths.pages), w(paths.source)]))
    elif slide_source == "photos":
        # No deck: the photos are the slides, and slides --photos records their digests too.
        steps.append(step(photos_argv(photos), list(photos), [w(paths.pages), w(paths.source)]))
    elif slide_source == "keyframes" and len(files["video"]) == 1:
        # No deck and no photos: the video's key frames are the slides. Audio never counts.
        # keyframes leaves source.json alone: the transcript step records the video's digest.
        f = files["video"][0]
        steps.append(step(keyframes_argv(f), [f], [w(paths.pages), w(paths.keyframes)]))
    if not transcripts and len(media) == 1:
        f = media[0]
        # The first transcription may download the ASR model.
        steps.append(step(local_argv(f), [f], [w(paths.transcript), w(paths.source)], network=True, gpu=True))
    if slide_source.endswith("-deferred"):
        reads = {"photos-deferred": files["images"]}
        steps.append(step([T], list(reads[slide_source]), [], runnable=False))

    def question(about: str, candidates: list[str], make_argv) -> dict:
        return {
            "about": about,
            "candidates": list(candidates),
            "argv": [make_argv(c) for c in candidates] if make_argv is not None else [],
            "text": _QUESTION_TEXT[about],
        }

    questions: list[dict] = []
    if unsafe:
        questions.append(question("unsafe-name", unsafe, None))
    if len(transcripts) > 1:
        questions.append(question("transcript", transcripts, transcript_argv))
    if not transcripts and len(media) > 1:
        questions.append(question("media", media, local_argv))
    if slide_source == "keyframes" and len(files["video"]) > 1:
        questions.append(question("video", files["video"], keyframes_argv))
    if len(pdfs) > 1:
        questions.append(question("pdf", pdfs, slides_argv))
    if not pdfs and len(pptx) > 1:
        questions.append(question("pptx", pptx, pptx_argv))

    return {"files": files, "slide_source": slide_source, "steps": steps, "questions": questions}
