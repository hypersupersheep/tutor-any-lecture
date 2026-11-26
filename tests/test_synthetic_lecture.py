import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import pytest

import tools.synthetic_lecture as synthetic_lecture
from tools.synthetic_lecture import (
    EXPECTED_WORDS,
    LECTURE_TEXT,
    SMALL_MODELS,
    build_lecture,
    find_ffmpeg,
    main,
    system_synthesizer,
)
from tutor_any_lecture import asr
from tutor_any_lecture.ffmpeg import ffmpeg_exe, media_duration

ODD = Path("课程 资料") / "第1周"
HEALTHY = {
    "coverage": 0.97, "repetition": 0.0, "spots_ok": True, "overrun": False,
    "loop": False, "ok": True, "duration_known": True,
}
SEGMENTS = [
    "Today we look at compound interest and how money grows.",
    "The interest rate is the price of money for one year.",
    "With compound interest you earn interest on interest, year after year.",
    "A higher rate makes money grow faster over the years.",
]


# ---- S1 ----

def test_lecture_text_holds_the_expected_words():
    assert LECTURE_TEXT.isascii()
    assert 150 <= len(LECTURE_TEXT.split()) <= 220
    tokens = re.findall(r"[a-z']+", LECTURE_TEXT.casefold())
    assert EXPECTED_WORDS == ("interest", "compound", "money", "rate", "year")
    for word in EXPECTED_WORDS:
        assert len([t for t in tokens if t.startswith(word)]) >= 2, word


# ---- S2 ----

class Recorder:
    """A stand-in for subprocess.run that records the call and returns `returncode`."""

    def __init__(self, returncode=0, stderr=""):
        self.calls = []
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, self.returncode, stdout="", stderr=self.stderr)


def patch_tools(monkeypatch, run, found=True):
    monkeypatch.setattr(synthetic_lecture.shutil, "which", lambda name: f"/bin/{name}" if found else None)
    monkeypatch.setattr(synthetic_lecture.subprocess, "run", run)


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_system_synthesizer_runs_the_platform_tool(platform, tmp_path, monkeypatch):
    monkeypatch.setenv("PSModulePath", r"C:\Program Files\PowerShell\7\Modules")
    run = Recorder()
    patch_tools(monkeypatch, run)
    text_file = tmp_path / "lecture.txt"
    out = tmp_path / "out"
    out.mkdir()
    audio = system_synthesizer(platform)(text_file, out)
    (argv, kwargs), = run.calls
    if platform == "linux":
        assert audio == out / "lecture.wav"
        assert argv == ["espeak-ng", "-v", "en-us", "-s", "150", "-w", str(out / "lecture.wav"), "-f", str(text_file)]
    elif platform == "darwin":
        assert audio == out / "lecture.aiff"
        assert argv == ["say", "-r", "170", "-o", str(out / "lecture.aiff"), "-f", str(text_file)]
    else:
        assert audio == out / "lecture.wav"
        script = out / "synthesize.ps1"
        assert argv == [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
            str(text_file), str(out / "lecture.wav"),
        ]
        assert script.is_file()
        env = kwargs["env"]
        assert env and not [k for k in env if k.casefold() == "psmodulepath"]


@pytest.mark.parametrize("platform, message", [
    ("linux", "espeak-ng is not on PATH; install it with: sudo apt-get install espeak-ng"),
    ("darwin", "say is not on PATH; it ships with macOS"),
    ("win32", "powershell is not on PATH; Windows PowerShell 5.1 ships with Windows"),
])
def test_missing_synthesiser_names_the_install(platform, message, tmp_path, monkeypatch):
    run = Recorder()
    patch_tools(monkeypatch, run, found=False)
    with pytest.raises(RuntimeError) as caught:
        system_synthesizer(platform)(tmp_path / "lecture.txt", tmp_path)
    assert str(caught.value) == message
    assert run.calls == []


@pytest.mark.parametrize("platform, tool", [("linux", "espeak-ng"), ("darwin", "say"), ("win32", "powershell")])
def test_a_failing_synthesiser_names_its_last_error_line(platform, tool, tmp_path, monkeypatch):
    patch_tools(monkeypatch, Recorder(returncode=1, stderr="starting\nno voice found\n\n"))
    with pytest.raises(RuntimeError) as caught:
        system_synthesizer(platform)(tmp_path / "lecture.txt", tmp_path)
    assert str(caught.value) == f"{tool} failed: no voice found"


def test_unknown_platform_has_no_synthesiser():
    with pytest.raises(RuntimeError) as caught:
        system_synthesizer("freebsd")
    assert str(caught.value) == "no speech synthesiser for platform 'freebsd'"


def test_windows_script_is_ascii(tmp_path, monkeypatch):
    patch_tools(monkeypatch, Recorder())
    system_synthesizer("win32")(tmp_path / "lecture.txt", tmp_path)
    script = (tmp_path / "synthesize.ps1").read_bytes()
    assert script.isascii()
    text = script.decode("ascii")
    assert "System.Speech" in text and "SetOutputToWaveFile" in text
    assert "param([string]$TextFile, [string]$WavFile)" in text


# ---- S3 ----

def write_wav(path: Path, seconds: float = 3.0, rate: int = 16000) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return path


def fake_synthesizer(text_file: Path, out_dir: Path) -> Path:
    assert text_file.read_text(encoding="utf-8") == LECTURE_TEXT
    return write_wav(out_dir / "lecture.wav")


def test_build_lecture_muxes_the_audio_into_a_video(tmp_path):
    out = tmp_path / ODD
    video = build_lecture(out, fake_synthesizer, ffmpeg_exe())
    assert video == out / "lecture.mp4"
    assert (out / "lecture.txt").read_bytes() == LECTURE_TEXT.encode("utf-8")
    duration = media_duration(video)
    assert duration is not None and abs(duration - 3.0) <= 1.0


@pytest.mark.parametrize("written", [None, b""])
def test_build_lecture_fails_when_synthesis_writes_nothing(written, tmp_path):
    def silent(text_file: Path, out_dir: Path) -> Path:
        audio = out_dir / "lecture.wav"
        if written is not None:
            audio.write_bytes(written)
        return audio

    out = tmp_path / ODD
    with pytest.raises(RuntimeError) as caught:
        build_lecture(out, silent, ffmpeg_exe())
    assert str(caught.value) == f"speech synthesis wrote no audio: {out / 'lecture.wav'}"
    assert not (out / "lecture.mp4").exists()


def test_build_lecture_reports_the_end_of_ffmpeg_errors(tmp_path, monkeypatch):
    stderr = "\n".join(f"line {n}" for n in range(1, 8)) + "\n\n"
    run = Recorder(returncode=1, stderr="")
    run.stderr = stderr.encode("utf-8")
    monkeypatch.setattr(synthetic_lecture.subprocess, "run", run)
    with pytest.raises(RuntimeError) as caught:
        build_lecture(tmp_path, fake_synthesizer, "ffmpeg")
    message = str(caught.value)
    assert "\n" not in message
    assert all(f"line {n}" in message for n in range(3, 8))
    assert "line 2" not in message
    (argv, _), = run.calls
    assert argv == [
        "ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i", "color=c=white:s=640x360:r=5",
        "-i", str(tmp_path / "lecture.wav"), "-shortest", "-c:v", "mpeg4", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(tmp_path / "lecture.mp4"),
    ]


def test_find_ffmpeg_prefers_the_path(monkeypatch):
    monkeypatch.setattr(synthetic_lecture.shutil, "which", lambda name: "/opt/bin/ffmpeg")
    assert find_ffmpeg() == "/opt/bin/ffmpeg"


def test_find_ffmpeg_names_both_ways_to_get_it(monkeypatch):
    monkeypatch.setattr(synthetic_lecture.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)  # the import now raises ImportError
    with pytest.raises(RuntimeError) as caught:
        find_ffmpeg()
    assert str(caught.value) == "ffmpeg is not available: install ffmpeg, or pip install imageio-ffmpeg"


def test_build_cli_prints_the_path(tmp_path, monkeypatch, capsys):
    out = tmp_path / ODD
    monkeypatch.setattr(synthetic_lecture, "system_synthesizer", lambda platform=sys.platform: fake_synthesizer)
    monkeypatch.setattr(synthetic_lecture, "find_ffmpeg", ffmpeg_exe)
    assert main(["build", "--out", str(out)]) == 0
    stdout = capsys.readouterr().out
    assert len(stdout.splitlines()) == 1
    assert json.loads(stdout) == {"path": str(out / "lecture.mp4")}


def test_build_cli_reports_a_runtime_error(tmp_path, monkeypatch, capsys):
    def no_synthesizer(platform=sys.platform):
        raise RuntimeError("no speech synthesiser for platform 'freebsd'")

    monkeypatch.setattr(synthetic_lecture, "system_synthesizer", no_synthesizer)
    assert main(["build", "--out", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "no speech synthesiser for platform 'freebsd'\n"


# ---- S4 ----

def write_unit(unit: Path, segments=SEGMENTS, health=HEALTHY, model="small", acquisition="asr") -> Path:
    sources = unit / "sources"
    sources.mkdir(parents=True)
    transcript = {
        "language": "en",
        "segments": [{"start": 5.0 * n, "end": 5.0 * n + 4.5, "text": t} for n, t in enumerate(segments)],
    }
    source = {
        "kind": "local", "title": "lecture", "url": None, "platform": None, "duration": 20.0,
        "lecture_language": "en", "acquisition": acquisition, "health": health,
        "tool_versions": {"asr_backend": "faster", "asr_model": model, "asr_device": "cpu"},
        "inputs_sha256": {"lecture.mp4": "0" * 64},
    }
    for name, data in (("transcript.json", transcript), ("source.json", source)):
        (sources / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8", newline="\n")
    return unit


def check(unit: Path, capsys) -> tuple[int, list[str]]:
    code = main(["check", "--unit", str(unit)])
    return code, capsys.readouterr().out.splitlines()


def test_check_passes_a_healthy_unit(tmp_path, capsys):
    code, lines = check(write_unit(tmp_path / ODD), capsys)
    assert lines == [
        "PASS transcript: 4 segments",
        "PASS health: coverage 0.97",
        "PASS acquisition: asr",
        "PASS model: small",
        "PASS words: found 5 of 5",
    ]
    assert code == 0


def test_check_fails_on_missing_words(tmp_path, capsys):
    segments = ["Today we talk about interest on money.", "Money earns interest every year."]
    code, lines = check(write_unit(tmp_path / ODD, segments=segments), capsys)
    assert "FAIL words: found 3 of 5 (missing: compound, rate)" in lines
    assert code == 1


def test_check_fails_on_a_large_model(tmp_path, capsys):
    code, lines = check(write_unit(tmp_path / ODD, model="large-v3-turbo"), capsys)
    assert "FAIL model: expected one of small, mlx-community/whisper-small-mlx, got large-v3-turbo" in lines
    assert code == 1


def test_check_fails_on_another_acquisition(tmp_path, capsys):
    code, lines = check(write_unit(tmp_path / ODD, acquisition="import"), capsys)
    assert "FAIL acquisition: expected asr, got import" in lines
    assert code == 1


def test_check_fails_on_an_unhealthy_transcript(tmp_path, capsys):
    health = {"coverage": 0.42, "repetition": 0.0, "spots_ok": True, "overrun": False, "loop": False,
              "ok": False, "duration_known": True}
    code, lines = check(write_unit(tmp_path / ODD, health=health), capsys)
    assert (
        'FAIL health: coverage 0.42 {"coverage": 0.42, "duration_known": true, "loop": false, "ok": false, '
        '"overrun": false, "repetition": 0.0, "spots_ok": true}'
    ) in lines
    assert len(lines) == 5
    assert code == 1


@pytest.mark.parametrize("transcript", [None, b"not json", b'{"segments": "none"}'])
def test_check_reports_a_missing_transcript(transcript, tmp_path, capsys):
    unit = write_unit(tmp_path / ODD)
    path = unit / "sources" / "transcript.json"
    if transcript is None:
        path.unlink()
    else:
        path.write_bytes(transcript)
    code, lines = check(unit, capsys)
    assert lines == [f"FAIL transcript: no sources/transcript.json in {unit}"]
    assert code == 1


@pytest.mark.parametrize("source", [None, b"[]", b'{"health": {}, "acquisition": "asr"}'])
def test_check_reports_a_missing_source(source, tmp_path, capsys):
    unit = write_unit(tmp_path / ODD)
    path = unit / "sources" / "source.json"
    if source is None:
        path.unlink()
    else:
        path.write_bytes(source)
    code, lines = check(unit, capsys)
    assert lines == [f"FAIL source: no sources/source.json in {unit}"]
    assert code == 1


def test_small_models_match_the_command_selection(monkeypatch):
    monkeypatch.setattr(asr, "_ram_bytes", lambda: 8 * asr.GIB)
    monkeypatch.setattr(asr, "_cuda_devices", lambda: 0)
    assert {asr.select_model("mlx"), asr.select_model("faster")} == set(SMALL_MODELS)
