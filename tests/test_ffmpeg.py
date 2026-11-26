import importlib.metadata
import subprocess

import pytest

from tutor_any_lecture.ffmpeg import (
    Stream,
    extract_audio,
    ffmpeg_exe,
    media_duration,
    media_streams,
    parse_streams,
    sample_gray_frames,
    save_frame,
)
from tutor_any_lecture.transcript import AcquireError


def make_tone(path):
    # local helper: 2 s of sine from ffmpeg lavfi
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg_exe(), "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(path)],
                   check=True, capture_output=True)
    return path


def test_extract_audio_and_duration(tmp_path):
    # 2 s of sine from ffmpeg lavfi, in a folder with spaces and CJK
    src = tmp_path / "第 1 周" / "tone.wav"
    src.parent.mkdir()
    subprocess.run([ffmpeg_exe(), "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(src)],
                   check=True, capture_output=True)
    assert abs(media_duration(src) - 2.0) < 0.1
    extract_audio(src, tmp_path / "o.wav")
    assert (tmp_path / "o.wav").stat().st_size > 0


STREAMS_TEXT = """\
Input #0, matroska,webm, from 'lecture.mkv':
  Metadata:
    ENCODER         : Lavf61.7.100
  Duration: 00:01:04.00, start: 0.000000, bitrate: 1234 kb/s
  Stream #0:0: Video: mpeg4 (Simple Profile), yuv420p, 320x240, 5 fps
  Stream #0:1(eng): Audio: flac, 44100 Hz, mono
  Stream #0:2(eng): Subtitle: subrip (srt) (default)
  Stream #0:3[0x4](fre): Subtitle: hdmv_pgs_subtitle (pgssub), 1920x1080
  Stream #0:4[0x5](und): Video: mjpeg (Baseline), 300x300 (attached pic)
Stream mapping:
  Stream #0:0 -> #0:0 (mpeg4 (native) -> wrapped_avframe (native))
Output #0, null, to 'pipe:':
  Stream #0:0: Video: wrapped_avframe, yuv420p, 320x240, 5 fps
"""


def test_parse_streams_reads_input_streams():
    assert parse_streams(STREAMS_TEXT) == [
        Stream(0, "video", "mpeg4", None, False),
        Stream(1, "audio", "flac", "eng", False),
        Stream(2, "subtitle", "subrip", "eng", False),
        Stream(3, "subtitle", "hdmv_pgs_subtitle", "fre", False),
        Stream(4, "video", "mjpeg", None, True),
    ]


def test_media_streams_of_a_tone(tmp_path):
    tone = make_tone(tmp_path / "课程 资料" / "tone.wav")
    assert media_streams(tone) == [Stream(0, "audio", "pcm_s16le", None, False)]
    text = tmp_path / "课程 资料" / "x.mp4"
    text.write_text("not a video\n", encoding="utf-8", newline="\n")
    assert media_streams(text) == []


def test_frame_helpers_name_the_file(tmp_path):
    tone = make_tone(tmp_path / "课程 资料" / "tone.wav")
    with pytest.raises(AcquireError) as e:
        sample_gray_frames(tone, 5, 2.0)
    assert str(e.value).startswith("ffmpeg could not read frames from tone.wav")
    dst = tmp_path / "课程 资料" / "frame-001.jpg"
    with pytest.raises(AcquireError) as e:
        save_frame(tone, 0, 0.0, dst)
    assert str(e.value).startswith("ffmpeg could not save the frame at 0 s of tone.wav")


def test_pillow_comes_with_pdfplumber():
    requires = importlib.metadata.requires("pdfplumber") or []
    assert any(r.lower().startswith("pillow") for r in requires)
