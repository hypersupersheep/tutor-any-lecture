"""Local media (a video or audio file on disk) to a transcript: a subtitle track inside it, else ASR."""

from __future__ import annotations

import dataclasses
import importlib.metadata
import os
import shutil
import stat
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from tutor_any_lecture import __version__, asr, slides

from ..ffmpeg import TEXT_SUBTITLE_CODECS, extract_audio, media_duration, media_streams, subtitle_vtt
from ..profile import Profile
from ..source import SourceInfo, sha256_file, slide_digests
from ..transcript import AcquireError, EmptyTranscript, Health, Transcript, health, parse_vtt
from ..unit import UnitPaths, refuse_overwrite

# The tool's temporary folders sit under one parent in the system temp folder: on POSIX
# "tutor-any-lecture-<uid>", private to the user (mode 0700); on Windows, where the
# temp folder already belongs to one user, "tutor-any-lecture".
TEMP_PARENT = "tutor-any-lecture"
# A folder under the parent older than this was left by a run that was killed outright.
STALE_SECONDS = 24 * 3600


def _sweep_stale(parent: Path) -> None:
    """Remove the folders under ``parent`` older than ``STALE_SECONDS``. Errors are ignored."""
    try:
        entries = list(parent.iterdir())
    except OSError:
        return
    cutoff = time.time() - STALE_SECONDS
    for entry in entries:
        try:
            info = entry.lstat()
            if entry.is_symlink() or not entry.is_dir() or info.st_mtime >= cutoff:
                continue
            shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue


def _is_private(path: Path) -> bool:
    """A real directory (not a symbolic link), owned by this user, writable by no one else."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return (
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.getuid()
        and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    )


def _shared_parent(base: Path) -> Path | None:
    """The tool's parent under ``base``, created when missing; None when it cannot be trusted.

    Someone else could have put a folder, a link or a file at the POSIX path first: such
    a path is never used, so it never holds this user's audio and is never swept.
    """
    if os.name == "nt":
        parent = base / TEMP_PARENT
        parent.mkdir(parents=True, exist_ok=True)
        return parent
    parent = base / f"{TEMP_PARENT}-{os.getuid()}"
    try:
        parent.mkdir(mode=0o700)
    except FileExistsError:
        pass  # checked below, never changed: it may not be ours
    else:
        os.chmod(parent, 0o700)  # mkdir's mode is narrowed by the umask; set it exactly
    return parent if _is_private(parent) else None


def _new_run_folder() -> tuple[Path, Path | None]:
    """A new folder for this run, and the fresh parent to remove with it (None if shared).

    The shared parent is swept of stale folders first. When it cannot be used, the run
    gets a fresh private parent of its own and sweeps nothing.
    """
    base = Path(tempfile.gettempdir())
    parent = None
    try:
        parent = _shared_parent(base)
        if parent is not None:
            _sweep_stale(parent)
            return Path(tempfile.mkdtemp(prefix="run-", dir=parent)), None
    except OSError:
        # Fall back to a fresh parent. A trusted parent holding nothing goes first, so a
        # failed run leaves no empty folder behind.
        if parent is not None:
            _remove_if_empty(parent)
    own = None
    try:
        own = Path(tempfile.mkdtemp(prefix=f"{TEMP_PARENT}-", dir=base))
        return Path(tempfile.mkdtemp(prefix="run-", dir=own)), own
    except OSError as e:
        if own is not None:
            _remove_if_empty(own)
        raise AcquireError(f"could not create a temporary folder in {base}: {e}") from e


def _remove_if_empty(folder: Path) -> None:
    """Remove ``folder`` if it is empty; otherwise, or on any error, leave it."""
    try:
        folder.rmdir()  # rmdir removes only an empty folder
    except OSError:
        pass


@contextmanager
def temp_dir():
    """A new folder under the tool's temp parent, removed when the block ends, however it ends.

    Outside the unit and the user's folders. ``main`` turns SIGTERM into ``SystemExit``,
    so a stopped command removes it too. Raises ``AcquireError`` when no temporary folder
    can be created.
    """
    tmp, own_parent = _new_run_folder()
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if tmp.exists():
            print(f"warning: could not delete the temporary folder {tmp}; delete it by hand", file=sys.stderr)
        elif own_parent is not None:
            shutil.rmtree(own_parent, ignore_errors=True)


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{path} does not exist or is not a file")


def transcribe_audio(
    audio: Path,
    unit: Path,
    profile: Profile,
    force: bool,
    budget_minutes: float | None = None,
    backend: str | None = None,
    model: str | None = None,
) -> Health:
    """Transcribe ``audio`` as it is (no extraction) into the unit."""
    refuse_overwrite(unit, force)
    audio = Path(audio)
    _require_file(audio)
    return _transcribe_into_unit(audio, audio, media_duration(audio), unit, profile, budget_minutes, backend, model)


def acquire_local(
    file: Path,
    unit: Path,
    profile: Profile,
    force: bool,
    budget_minutes: float | None = None,
) -> Health:
    """Write ``file``'s first healthy text subtitle track into the unit as its transcript.

    Without one, extract ``file``'s audio to a temp folder, transcribe it into the unit and
    delete the audio. ``budget_minutes`` matters only then.
    """
    refuse_overwrite(unit, force)
    file = Path(file)
    _require_file(file)
    duration = media_duration(file)
    h = _embedded_track_into_unit(file, duration, unit)
    if h is not None:
        return h
    # Before the extraction, so a missing backend costs no audio work.
    backend, model = asr.resolve_backend()
    # Removed also when transcription fails or the command is stopped.
    with temp_dir() as tmp:
        wav = tmp / "audio.wav"
        extract_audio(file, wav)
        return _transcribe_into_unit(wav, file, duration, unit, profile, budget_minutes, backend, model)


def _embedded_track_into_unit(file: Path, duration: float | None, unit: Path) -> Health | None:
    """Write the first healthy text subtitle track of ``file``, in file order; None when there is none.

    Only a file with audio, or with a video stream that is not a cover picture, has its
    tracks read: a bare subtitle file is one ``subrip`` stream to ffmpeg. A track ffmpeg
    cannot convert, an empty one and an unhealthy one are skipped, and nothing is written
    for them.
    """
    streams = media_streams(file)
    if not any(s.kind == "audio" or (s.kind == "video" and not s.attached_pic) for s in streams):
        return None
    for stream in streams:
        if stream.kind != "subtitle" or stream.codec not in TEXT_SUBTITLE_CODECS:
            continue
        text = subtitle_vtt(file, stream.index)
        if text is None:
            continue
        segments = parse_vtt(text)
        if not segments:
            continue
        h = health(segments, duration)
        if not h.ok:
            continue
        paths = UnitPaths(unit).ensure()
        # The track's language tag is not trusted as the lecture's language.
        paths.transcript.write_text(Transcript(segments, None).to_json(), encoding="utf-8", newline="\n")
        SourceInfo(
            kind="local",
            title=file.stem,
            url=None,
            platform=None,
            duration=duration,
            lecture_language=None,
            acquisition="embedded",
            health=dataclasses.asdict(h),
            tool_versions={"tutor-any-lecture": __version__},
            inputs_sha256={**slide_digests(paths.source), file.name: sha256_file(file)},
        ).write(paths.source)
        return h
    return None


def _transcribe_into_unit(
    audio: Path,
    origin: Path,
    duration: float | None,
    unit: Path,
    profile: Profile,
    budget_minutes: float | None,
    backend: str | None,
    model: str | None,
) -> Health:
    """Transcribe ``audio``; write transcript.json and source.json describing ``origin``, ``duration`` long."""
    language = None if profile.lecture_language == "auto" else profile.lecture_language
    prompt = slides.slide_terms(slides.load_pages(unit))
    budget = asr.default_budget_minutes(duration) if budget_minutes is None else budget_minutes
    name, model = asr.resolve_backend(backend, model)

    transcript = asr.transcribe(audio, language, prompt, budget, backend=name, model=model)
    if not transcript.segments:
        raise EmptyTranscript("no timed segments found")

    h = health(transcript.segments, duration)
    paths = UnitPaths(unit).ensure()
    paths.transcript.write_text(transcript.to_json(), encoding="utf-8", newline="\n")
    SourceInfo(
        kind="local",
        title=origin.stem,
        url=None,
        platform=None,
        duration=duration,
        lecture_language=transcript.language,
        acquisition="asr",
        health=dataclasses.asdict(h),
        tool_versions=_tool_versions(name, model, getattr(transcript, "device", None)),
        inputs_sha256={**slide_digests(paths.source), origin.name: sha256_file(origin)},
    ).write(paths.source)
    return h


def _tool_versions(name: str, model: str | None, device: str | None) -> dict:
    # device: what asr.transcribe reports (an AsrTranscript); None for any other transcript.
    versions = {"asr_backend": name, "asr_model": model, "asr_device": device}
    package = asr.BACKEND_PACKAGES.get(name)
    if package is not None:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions
