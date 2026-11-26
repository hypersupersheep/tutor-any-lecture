"""A synthetic lecture for a real speech-recognition run, and a check of its transcript.

The weekly workflow speaks LECTURE_TEXT with the system's own speech synthesiser
(espeak-ng on Linux, say on macOS, System.Speech on Windows), muxes the audio into a
video with ffmpeg, has `tutor-any-lecture acquire local` transcribe it, and checks the
unit it wrote:

    python tools/synthetic_lecture.py build --out DIR
    python tools/synthetic_lecture.py check --unit DIR

Standard library only at module level: the workflow runs this with a bare runner Python.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

LECTURE_TEXT = (
    "Good morning. Today we study compound interest, one of the most useful ideas in finance. "
    "Suppose you put one hundred pounds in a savings account that pays an interest rate of five "
    "percent a year. After the first year the bank adds five pounds, so you have one hundred and "
    "five pounds. With simple interest you would earn the same five pounds every year. With "
    "compound interest the interest itself starts to earn interest. In the second year the rate "
    "applies to one hundred and five pounds, so the money grows a little faster. After ten years "
    "the balance is about one hundred and sixty three pounds, not one hundred and fifty. The rule "
    "is short: multiply by one plus the rate, once for each year. Two things decide how much money "
    "you end with: the rate and the time. A higher rate helps, but time helps even more, because "
    "compound growth builds on itself. This is why saving early matters. A small amount of money "
    "left alone for many years can grow larger than a big amount saved late. Next week we will "
    "see how the same rule works for loans and debt."
)
EXPECTED_WORDS = ("interest", "compound", "money", "rate", "year")
# What asr.select_model chooses on a CPU runner (faster-whisper) and on an Apple Silicon
# runner under 16 GiB (mlx). `acquire local` has no --model flag, so the weekly run
# cannot force a model; a larger choice fails the check loudly.
SMALL_MODELS = ("small", "mlx-community/whisper-small-mlx")
WORDS_NEEDED = 4

WINDOWS_SCRIPT = """\
param([string]$TextFile, [string]$WavFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.SetOutputToWaveFile($WavFile)
    $synth.Speak([System.IO.File]::ReadAllText($TextFile))
} finally {
    $synth.Dispose()
}
"""


# ---- speech synthesis -------------------------------------------------------------

def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else "no error output"


def _run_tool(tool: str, argv: list, env=None) -> None:
    proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"{tool} failed: {_last_line(proc.stderr)}")


def _require(tool: str, missing: str) -> None:
    if shutil.which(tool) is None:
        raise RuntimeError(f"{tool} is not on PATH; {missing}")


def _espeak(text_file: Path, out_dir: Path) -> Path:
    _require("espeak-ng", "install it with: sudo apt-get install espeak-ng")
    audio = Path(out_dir) / "lecture.wav"
    _run_tool("espeak-ng", ["espeak-ng", "-v", "en-us", "-s", "150", "-w", str(audio), "-f", str(text_file)])
    return audio


def _say(text_file: Path, out_dir: Path) -> Path:
    _require("say", "it ships with macOS")
    audio = Path(out_dir) / "lecture.aiff"
    _run_tool("say", ["say", "-r", "170", "-o", str(audio), "-f", str(text_file)])
    return audio


def _system_speech(text_file: Path, out_dir: Path) -> Path:
    _require("powershell", "Windows PowerShell 5.1 ships with Windows")
    out_dir = Path(out_dir)
    script = out_dir / "synthesize.ps1"
    script.write_text(WINDOWS_SCRIPT, encoding="ascii", newline="\n")
    audio = out_dir / "lecture.wav"
    # Python runs inside a pwsh step; Windows PowerShell 5.1 started from it would inherit
    # PowerShell 7's module path, which can stop Add-Type from loading.
    env = {k: v for k, v in os.environ.items() if k.casefold() != "psmodulepath"}
    argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
            str(text_file), str(audio)]
    _run_tool("powershell", argv, env=env)
    return audio


_SYNTHESIZERS = {"linux": _espeak, "darwin": _say, "win32": _system_speech}


def system_synthesizer(platform: str = sys.platform):
    """The function `synthesize(text_file, out_dir) -> Path` that speaks a text file on `platform`."""
    try:
        return _SYNTHESIZERS[platform]
    except KeyError:
        raise RuntimeError(f"no speech synthesiser for platform '{platform}'") from None


# ---- the video ------------------------------------------------------------------------

def find_ffmpeg() -> str:
    """ffmpeg on PATH, else the binary that imageio-ffmpeg bundles."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        raise RuntimeError("ffmpeg is not available: install ffmpeg, or pip install imageio-ffmpeg") from None


def build_lecture(out_dir: Path, synthesize, ffmpeg: str, text: str = LECTURE_TEXT) -> Path:
    """Speak `text` and mux it under a white picture into out_dir/lecture.mp4."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_file = out_dir / "lecture.txt"
    text_file.write_text(text, encoding="utf-8", newline="\n")
    audio = Path(synthesize(text_file, out_dir))
    if not audio.is_file() or audio.stat().st_size == 0:
        raise RuntimeError(f"speech synthesis wrote no audio: {audio}")
    video = out_dir / "lecture.mp4"
    argv = [ffmpeg, "-nostdin", "-y", "-f", "lavfi", "-i", "color=c=white:s=640x360:r=5", "-i", str(audio),
            "-shortest", "-c:v", "mpeg4", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)]
    proc = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        tail = [ln.strip() for ln in stderr.splitlines() if ln.strip()][-5:]
        raise RuntimeError("ffmpeg failed: " + " | ".join(tail))
    return video


# ---- the check --------------------------------------------------------------------------

def _read_object(path: Path):
    """The JSON object in `path`, or None when it is missing, unreadable or not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _words_found(text: str) -> list[str]:
    tokens = re.findall(r"[a-z']+", text.casefold())
    return [w for w in EXPECTED_WORDS if any(t.startswith(w) for t in tokens)]


def _coverage(health: dict) -> str:
    value = health.get("coverage")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.2f}"
    return json.dumps(value)


def check_unit(unit: Path) -> list[str]:
    """The check lines for a unit that `acquire local` wrote, each starting PASS or FAIL."""
    unit = Path(unit)
    transcript = _read_object(unit / "sources" / "transcript.json")
    if transcript is None or not isinstance(transcript.get("segments"), list):
        return [f"FAIL transcript: no sources/transcript.json in {unit}"]
    source = _read_object(unit / "sources" / "source.json")
    if (source is None or not isinstance(source.get("health"), dict) or "acquisition" not in source
            or not isinstance(source.get("tool_versions"), dict)):
        return [f"FAIL source: no sources/source.json in {unit}"]

    segments = transcript["segments"]
    health, acquisition = source["health"], source["acquisition"]
    model = source["tool_versions"].get("asr_model")
    text = " ".join(str(s.get("text", "")) for s in segments if isinstance(s, dict))
    found = _words_found(text)
    missing = [w for w in EXPECTED_WORDS if w not in found]

    lines = [("PASS " if segments else "FAIL ") + f"transcript: {len(segments)} segments"]
    if health.get("ok") is True:
        lines.append(f"PASS health: coverage {_coverage(health)}")
    else:
        lines.append(f"FAIL health: coverage {_coverage(health)} {json.dumps(health, sort_keys=True)}")
    if acquisition == "asr":
        lines.append("PASS acquisition: asr")
    else:
        lines.append(f"FAIL acquisition: expected asr, got {acquisition}")
    if model in SMALL_MODELS:
        lines.append(f"PASS model: {model}")
    else:
        lines.append(f"FAIL model: expected one of {', '.join(SMALL_MODELS)}, got {model}")
    words = f"words: found {len(found)} of {len(EXPECTED_WORDS)}"
    if len(found) >= WORDS_NEEDED:
        lines.append("PASS " + words)
    else:
        lines.append(f"FAIL {words} (missing: {', '.join(missing)})")
    return lines


# ---- command line ------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="synthetic_lecture.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="speak the lecture and write DIR/lecture.mp4")
    build.add_argument("--out", required=True, metavar="DIR")
    chk = sub.add_parser("check", help="check the transcript that acquire local wrote into a unit")
    chk.add_argument("--unit", required=True, metavar="DIR")
    args = parser.parse_args(argv)

    if args.command == "build":
        try:
            path = build_lecture(Path(args.out), system_synthesizer(), find_ffmpeg())
        except (RuntimeError, OSError) as e:
            print(" ".join(str(e).split()), file=sys.stderr)
            return 1
        print(json.dumps({"path": str(path)}, ensure_ascii=(sys.platform == "win32")))
        return 0

    lines = check_unit(Path(args.unit))
    for line in lines:
        print(line)
    return 0 if all(line.startswith("PASS ") for line in lines) else 1


if __name__ == "__main__":
    sys.exit(main())
