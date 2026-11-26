import io
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tutor_any_lecture import keyframes
from tutor_any_lecture.cli import main
from tutor_any_lecture.ffmpeg import Stream, ffmpeg_exe
from tutor_any_lecture.keyframes import DUPLICATE_BITS, extract_keyframes, frame_hash, hamming, select_frames
from tutor_any_lecture.slides import load_pages
from tutor_any_lecture.transcript import AcquireError
from tutor_any_lecture.unit import UnitPaths

# ---- K2: a perceptual hash written with Pillow ------------------------------------


def slide_a():
    # local helper: a title bar and three text-like bars
    image = Image.new("RGB", (320, 240), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 320, 50], fill=(20, 40, 120))
    for y, width in ((80, 260), (125, 200), (170, 230)):
        draw.rectangle([30, y, 30 + width, y + 20], fill=(90, 90, 90))
    return image


def slide_b():
    # local helper: the same title bar, a figure and a block
    image = Image.new("RGB", (320, 240), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 320, 50], fill=(20, 40, 120))
    draw.ellipse([170, 70, 300, 200], fill=(200, 60, 40))
    draw.rectangle([30, 90, 140, 180], fill=(90, 90, 90))
    return image


def slide_c():
    # local helper: a dark slide with a light triangle
    image = Image.new("RGB", (320, 240), (30, 30, 30))
    ImageDraw.Draw(image).polygon([(0, 240), (320, 0), (320, 240)], fill=(230, 230, 230))
    return image


def checkerboard():
    # local helper: 64x48 pixels alternating between 100 and 110
    image = Image.new("L", (64, 48))
    image.frombytes(bytes(100 if (x + y) % 2 else 110 for y in range(48) for x in range(64)))
    return image


def test_frame_hash_ignores_size_and_jpeg_noise():
    with slide_a() as a:
        h = frame_hash(a)
        with a.resize((640, 480)) as big:
            assert hamming(h, frame_hash(big)) <= 2
        buffer = io.BytesIO()
        a.save(buffer, "JPEG", quality=30)
    buffer.seek(0)
    with Image.open(buffer) as jpeg:
        assert hamming(h, frame_hash(jpeg)) <= 2


def test_frame_hash_tells_different_slides_apart():
    with slide_a() as a, slide_b() as b, slide_c() as c:
        ha, hb, hc = frame_hash(a), frame_hash(b), frame_hash(c)
    assert hamming(ha, hb) > 6
    assert hamming(ha, hc) > 6
    assert hamming(hb, hc) > 6


def test_blank_frames_have_no_hash():
    with Image.new("L", (64, 48), 0) as black:
        assert frame_hash(black) is None
    with Image.new("RGB", (64, 48), (250, 250, 250)) as white:
        assert frame_hash(white) is None
    with checkerboard() as board:
        assert frame_hash(board) is None
    with slide_a() as a:
        h = frame_hash(a)
    assert isinstance(h, int) and 0 <= h < 2**64


# ---- K3: which candidates are kept ---------------------------------------------


def test_near_duplicates_of_any_kept_frame_are_dropped():
    assert DUPLICATE_BITS == 6
    assert select_frames([(0.0, 0), (10.0, 2**64 - 1), (20.0, 7), (30.0, 127)]) == [0, 1, 3]


def test_kept_frames_are_at_least_8_seconds_apart():
    assert select_frames([(0.0, 0), (4.0, 2**64 - 1), (8.0, 2**64 - 1), (14.0, 2**32 - 1)]) == [0, 2]


def test_blank_candidates_are_never_kept():
    assert select_frames([(0.0, None), (10.0, 0), (20.0, None)]) == [1]


def test_at_most_120_frames_spread_over_the_lecture():
    rng = random.Random(13)
    candidates = [(10.0 * k, rng.getrandbits(64)) for k in range(200)]
    kept = select_frames(candidates)
    assert kept == [round(i * 199 / 119) for i in range(120)]
    assert kept[0] == 0 and kept[-1] == 199


# ---- K4 to K6: key frames become the unit's slide pages ---------------------------

# 64 s at 5 fps: bars (0 s), the same bars with a small box (21 s, a near-duplicate), a colour
# test picture (31 s), another (45 s), other bars (49 s).
GRAPH = (
    "smptebars=s=320x240:r=5:d=21[a];"
    "smptebars=s=320x240:r=5:d=10,drawbox=x=20:y=20:w=40:h=20:c=white:t=fill[b];"
    "rgbtestsrc=s=320x240:r=5:d=14[c];"
    "yuvtestsrc=s=320x240:r=5:d=4[d];"
    "pal75bars=s=320x240:r=5:d=15[e];"
    "[a][b][c][d][e]concat=n=5:v=1:a=0[v]"
)
FRAMES = [f"frame-{n:03d}.jpg" for n in range(1, 5)]
EXPECTED = [
    (1, None, "", "../keyframes/frame-001.jpg", 0.0),
    (2, None, "", "../keyframes/frame-002.jpg", 32.0),
    (3, None, "", "../keyframes/frame-003.jpg", 46.0),
    (4, None, "", "../keyframes/frame-004.jpg", 54.0),
]
LINK_MESSAGE = (
    "keyframes reads a video file on this computer, not a link: "
    "from a video site the tool takes captions or audio only"
)


@pytest.fixture(scope="module")
def lecture_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "lecture.mkv"
    subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", "-filter_complex", GRAPH, "-map", "[v]",
         "-c:v", "mpeg4", "-q:v", "2", str(path)],
        check=True, capture_output=True,
    )
    return path


@pytest.fixture
def lecture(tmp_path, lecture_video):
    # local fixture: the encoded video copied beside a fresh unit, in a folder with a space and CJK
    folder = tmp_path / "课程 资料"
    folder.mkdir()
    video = folder / "第1周 lecture.mkv"
    shutil.copyfile(lecture_video, video)
    return video, folder / "第1周"


def make_tone(path):
    # local helper: 2 s of sine from ffmpeg lavfi
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg_exe(), "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(path)],
                   check=True, capture_output=True)
    return path


def names(folder):
    # local helper: the file names in a folder, sorted
    return sorted(p.name for p in folder.iterdir())


def page_tuples(pages):
    return [(p.n, p.label, p.text, p.image, p.time) for p in pages]


def assert_nothing_written(unit):
    sources = unit / "sources"
    assert not UnitPaths(unit).pages.exists()
    assert not (sources / "keyframes").exists()
    assert not (sources / "keyframes.partial").exists()


def failing_on_second_call(error):
    # local helper: the real save_frame, except that its second call raises ``error``
    real = keyframes.save_frame
    calls = []

    def save(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise error
        return real(*args, **kwargs)

    return save


def test_keyframes_of_a_synthetic_lecture(lecture):
    video, unit = lecture
    pages, candidates = extract_keyframes(video, unit)
    assert page_tuples(pages) == EXPECTED
    assert page_tuples(load_pages(unit)) == EXPECTED
    raw = json.loads(UnitPaths(unit).pages.read_text(encoding="utf-8"))
    assert [set(entry) for entry in raw] == [{"n", "label", "text", "image", "time"}] * 4
    assert candidates in (32, 33)
    folder = unit / "sources" / "keyframes"
    assert names(folder) == FRAMES
    for name in FRAMES:
        with Image.open(folder / name) as image:
            assert (image.format, image.size) == ("JPEG", (320, 240))
    assert not (unit / "sources" / "source.json").exists()


def test_keyframes_errors_name_the_video(lecture, monkeypatch):
    video, unit = lecture
    monkeypatch.setattr(keyframes, "media_streams", lambda path: [
        Stream(0, "video", "mjpeg", None, True), Stream(1, "audio", "aac", None, False),
    ])
    with pytest.raises(AcquireError) as e:
        extract_keyframes(video, unit)
    assert str(e.value) == "第1周 lecture.mkv has no video stream to take key frames from"
    assert_nothing_written(unit)

    monkeypatch.undo()
    monkeypatch.setattr(keyframes, "sample_gray_frames", lambda *args, **kwargs: [])
    with pytest.raises(AcquireError) as e:
        extract_keyframes(video, unit)
    assert str(e.value) == "no frames could be read from 第1周 lecture.mkv"
    assert_nothing_written(unit)

    monkeypatch.setattr(keyframes, "sample_gray_frames", lambda *args, **kwargs: [bytes(4096)] * 3)
    with pytest.raises(AcquireError) as e:
        extract_keyframes(video, unit)
    assert str(e.value) == "every frame of 第1周 lecture.mkv is blank: no key frames to keep"
    assert_nothing_written(unit)


def test_unit_paths_name_the_keyframes_folder(tmp_path):
    assert UnitPaths(tmp_path).keyframes == tmp_path / "sources" / "keyframes"


def test_keyframes_replace_only_with_force(lecture):
    video, unit = lecture
    extract_keyframes(video, unit)
    pages_json = UnitPaths(unit).pages
    before = pages_json.read_bytes()
    with pytest.raises(FileExistsError):
        extract_keyframes(video, unit)
    assert pages_json.read_bytes() == before

    folder = unit / "sources" / "keyframes"
    (folder / "frame-099.jpg").write_bytes(b"stray")
    pages, _ = extract_keyframes(video, unit, force=True)
    assert page_tuples(pages) == EXPECTED
    assert names(folder) == FRAMES

    partial = unit / "sources" / "keyframes.partial"
    partial.mkdir()
    (partial / "x.jpg").write_bytes(b"stray")
    extract_keyframes(video, unit, force=True)
    assert not partial.exists()
    assert names(folder) == FRAMES


def test_a_failed_run_changes_nothing(lecture, monkeypatch):
    video, unit = lecture
    extract_keyframes(video, unit)
    pages_json = UnitPaths(unit).pages
    folder = unit / "sources" / "keyframes"
    before = pages_json.read_bytes()
    for error in (AcquireError("boom"), KeyboardInterrupt()):
        monkeypatch.setattr(keyframes, "save_frame", failing_on_second_call(error))
        with pytest.raises(type(error)):
            extract_keyframes(video, unit, force=True)
        assert pages_json.read_bytes() == before
        assert names(folder) == FRAMES
        assert not (unit / "sources" / "keyframes.partial").exists()
        assert not (unit / "sources" / "keyframes.old").exists()
        monkeypatch.undo()

    # A fresh unit: the failure leaves no pages and no key frames.
    fresh = unit.parent / "第2周"
    monkeypatch.setattr(keyframes, "save_frame", failing_on_second_call(AcquireError("boom")))
    with pytest.raises(AcquireError):
        extract_keyframes(video, fresh)
    assert_nothing_written(fresh)
    assert not (fresh / "sources" / "keyframes.old").exists()


def test_cli_keyframes_prints_the_pages_path(lecture, capsys):
    video, unit = lecture
    argv = ["keyframes", "--video", str(video), "--unit", str(unit)]
    assert main(argv) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    out = json.loads(lines[0])
    path = unit / "sources" / "slides" / "pages.json"
    assert out["status"] == "ok" and out["frames"] == 4 and out["candidates"] in (32, 33)
    assert out["path"] == str(path)
    assert Path(out["path"]).is_absolute() and Path(out["path"]).is_file()

    assert main(argv) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    err = captured.err.splitlines()
    assert len(err) == 1 and err[0].endswith("rerun with --force to replace it")

    assert main([*argv, "--force"]) == 0
    assert json.loads(capsys.readouterr().out)["frames"] == 4


@pytest.mark.parametrize("link", ["https://www.youtube.com/watch?v=abc", "HTTP://video.example/lecture.mp4"])
def test_cli_keyframes_refuses_a_link(tmp_path, capsys, link):
    unit = tmp_path / "unit"
    assert main(["keyframes", "--video", link, "--unit", str(unit)]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "error", "message": LINK_MESSAGE}
    assert len(captured.out.splitlines()) == 1
    assert captured.err == ""
    assert not unit.exists()


def test_cli_keyframes_input_errors_are_json_objects(tmp_path, capsys):
    folder = tmp_path / "课程 资料"
    unit = folder / "第1周"
    missing = folder / "nope.mp4"
    tone = make_tone(folder / "tone.wav")

    def run(video):
        assert main(["keyframes", "--video", str(video), "--unit", str(unit)]) == 1
        captured = capsys.readouterr()
        assert captured.err == "" and len(captured.out.splitlines()) == 1
        out = json.loads(captured.out)
        assert out["status"] == "error"
        return out["message"]

    assert run(missing) == f"{missing.absolute()} does not exist or is not a file"
    assert run(tone) == "tone.wav has no video stream to take key frames from"
    assert run("C:\\x\\lecture.mp4").endswith("does not exist or is not a file")
