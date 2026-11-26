import importlib.metadata
import subprocess

import pytest

from tutor_any_lecture.ffmpeg import (
    TEXT_SUBTITLE_CODECS,
    Stream,
    extract_audio,
    ffmpeg_exe,
    media_duration,
    media_streams,
    parse_streams,
    sample_gray_frames,
    save_frame,
    subtitle_vtt,
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


def srt_time(seconds):
    # local helper: seconds as an SRT clock, HH:MM:SS,mmm
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def healthy_cues():
    # local helper: ten cues of 3 s each over a 30 s tone; cue 1 is styled
    cues = [(3 * i, 3 * i + 3, f"Sentence number {i + 1} about the lecture.") for i in range(10)]
    cues[0] = (0, 3, "<i>Sentence number 1</i> about the lecture.")
    return cues


def make_subtitled(folder, name, audio_codec, subtitle_codec, cues):
    # local helper: a 30 s tone with one subtitle track written from ``cues`` (start, end, text)
    folder.mkdir(parents=True, exist_ok=True)
    srt = folder / "subs.srt"
    srt.write_text(
        "".join(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n\n" for n, (a, b, text) in enumerate(cues, 1)),
        encoding="utf-8", newline="\n",
    )
    subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
         "-i", str(srt), "-map", "0:a", "-map", "1:s", "-c:a", audio_codec, "-c:s", subtitle_codec,
         str(folder / name)],
        check=True, capture_output=True,
    )
    return folder / name


def test_subtitle_vtt_reads_a_text_track(tmp_path):
    mkv = make_subtitled(tmp_path / "课程 资料", "lecture.mkv", "flac", "srt", healthy_cues())
    vtt = subtitle_vtt(mkv, 1)
    assert vtt.startswith("WEBVTT")
    assert "Sentence number 10 about the lecture." in vtt
    assert subtitle_vtt(mkv, 0) is None   # the audio stream
    assert TEXT_SUBTITLE_CODECS == ("subrip", "srt", "ass", "ssa", "webvtt", "mov_text", "text")
