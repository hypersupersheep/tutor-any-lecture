import io
import itertools
import json
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tutor_any_lecture import ffmpeg, keyframes
from tutor_any_lecture.cli import main
from tutor_any_lecture.ffmpeg import Stream, sample_gray_frames
from tutor_any_lecture.keyframes import (
    DUPLICATE_BITS,
    SAMPLE_SECONDS,
    extract_keyframes,
    frame_hash,
    hamming,
    select_frames,
)
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


def picture(background, boxes, seconds):
    # local helper: a lavfi source of filled boxes (x, y, w, h, colour) on a 320x240 background, 5 fps
    fills = "".join(f",drawbox=x={x}:y={y}:w={w}:h={h}:c={c}:t=fill" for x, y, w, h, c in boxes)
    return f"color=c={background}:s=320x240:r=5:d={seconds}{fills}"


# Slide-like pictures of flat boxes. Unlike ffmpeg's test patterns (rgbtestsrc and pal75bars
# have DCT coefficients exactly at the hash's median, so a few bits flip from one ffmpeg build
# to the next), none is symmetric and every coefficient sits well away from the median.
TITLE = (0, 0, 320, 50, "0x142878")
TEXT = ("white", [TITLE, (20, 80, 250, 20, "gray"), (30, 135, 200, 20, "gray"), (20, 170, 230, 20, "gray")])
FIGURE = ("white", [TITLE, (30, 90, 110, 90, "gray"), (170, 70, 130, 130, "0xC83C28")])
# The synthetic lecture, (seconds, kind, background, boxes) in order: the text slide; the same
# slide with a small box (a near-duplicate); a figure; a dark slide; a striped one. Every scene
# lasts at least 12 s, so a frame kept up to 2 samples late is still 8 s from the next scene's,
# and every cut falls at an odd second, between two samples.
SCENES = [
    (13, "distinct", *TEXT),
    (14, "duplicate", TEXT[0], [*TEXT[1], (270, 210, 20, 10, "gray")]),
    (14, "distinct", *FIGURE),
    (14, "distinct", "0x1e1e1e", [(140, 120, 160, 110, "0xe6e6e6"), (10, 10, 100, 60, "0x808080")]),
    (13, "distinct", "0x606060", [(0, 0, 60, 240, "0xf0f0f0"), (200, 0, 40, 240, "black"),
                                  (100, 170, 220, 50, "0xb0b0b0")]),
]
STARTS = list(itertools.accumulate([0, *(seconds for seconds, *_ in SCENES)]))  # the last is the end, 68 s
SPANS = [(STARTS[i], STARTS[i + 1], kind) for i, (_, kind, *_) in enumerate(SCENES)]
GRAPH = "".join(f"{picture(background, boxes, seconds)}[s{i}];"
                for i, (seconds, _, background, boxes) in enumerate(SCENES))
GRAPH += "".join(f"[s{i}]" for i in range(len(SCENES))) + f"concat=n={len(SCENES)}:v=1:a=0[v]"
FRAMES = [f"frame-{n:03d}.jpg" for n in range(1, 5)]
EXPECTED = [(n, None, "", f"../keyframes/{name}") for n, name in enumerate(FRAMES, start=1)]
CANDIDATES = (34, 35)  # 68 s, one candidate every 2 s
LINK_MESSAGE = (
    "keyframes reads a video file on this computer, not a link: "
    "from a video site the tool takes captions or audio only"
)


def bundled_ffmpeg():
    # local helper: the binary bundled with imageio-ffmpeg, or None when it has none
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        return None


@pytest.fixture(scope="module", params=["path", "bundled"])
def ffmpeg_build(request):
    # local fixture: each ffmpeg build on this machine in turn, as the binary the package uses
    on_path = shutil.which("ffmpeg")
    if request.param == "path":
        if on_path is None:
            pytest.skip("no ffmpeg on PATH")
        exe = on_path
    else:
        exe = bundled_ffmpeg()
        if exe is None:
            pytest.skip("imageio-ffmpeg has no ffmpeg binary here")
        if on_path is not None and os.path.samefile(on_path, exe):
            pytest.skip("the bundled ffmpeg is the one on PATH")
    patch = pytest.MonkeyPatch()
    patch.setattr(ffmpeg, "ffmpeg_exe", lambda: exe)
    yield exe
    patch.undo()


@pytest.fixture(scope="module")
def lecture_video(tmp_path_factory, ffmpeg_build):
    path = tmp_path_factory.mktemp("video") / "lecture.mkv"
    subprocess.run(
        [ffmpeg_build, "-hide_banner", "-nostdin", "-filter_complex", GRAPH, "-map", "[v]",
         "-c:v", "mpeg4", "-q:v", "2", str(path)],
        check=True, capture_output=True,
    )
    return path


@pytest.fixture
def lecture(tmp_path, ffmpeg_build, lecture_video):
    # local fixture: the encoded video copied beside a fresh unit, in a folder with a space and CJK
    folder = tmp_path / "课程 资料"
    folder.mkdir()
    video = folder / "第1周 lecture.mkv"
    shutil.copyfile(lecture_video, video)
    return video, folder / "第1周"


def make_tone(path):
    # local helper: 2 s of sine from ffmpeg lavfi
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg.ffmpeg_exe(), "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(path)],
                   check=True, capture_output=True)
    return path


def names(folder):
    # local helper: the file names in a folder, sorted
    return sorted(p.name for p in folder.iterdir())


def page_tuples(pages):
    return [(p.n, p.label, p.text, p.image, p.time) for p in pages]


def assert_one_page_per_scene(pages):
    # local helper: one page for each distinct scene, in order, taken at most 2 samples after the
    # scene starts, and none for the near-duplicate; which source frame an ffmpeg build puts at a
    # 2 s sample does not matter
    assert [(p.n, p.label, p.text, p.image) for p in pages] == EXPECTED
    distinct = [(start, end) for start, end, kind in SPANS if kind == "distinct"]
    assert len(pages) == len(distinct)
    for page, (start, _) in zip(pages, distinct):
        assert start <= page.time <= start + 2 * SAMPLE_SECONDS
    duplicates = [(start, end) for start, end, kind in SPANS if kind == "duplicate"]
    assert [p.time for p in pages if any(start <= p.time < end for start, end in duplicates)] == []


def sampled_hashes(video, index):
    # local helper: the hash of each candidate frame the package samples, in time order
    hashes = []
    for frame in sample_gray_frames(video, index, SAMPLE_SECONDS):
        with Image.frombytes("L", (64, 64), frame) as image:
            hashes.append(frame_hash(image))
    return hashes


def scene_margins(video):
    # local helper: for the ffmpeg build in use, the largest distance between two samples of one
    # scene, the largest between the first scene and its near-duplicate, and the smallest
    # between two distinct scenes
    by_scene = [[] for _ in SCENES]
    for k, h in enumerate(sampled_hashes(video, 0)):
        for i, (start, end, _) in enumerate(SPANS):
            if start <= k * SAMPLE_SECONDS < end:
                by_scene[i].append(h)
    assert all(by_scene), "every scene has a sample"
    distinct = [i for i, (_, _, kind) in enumerate(SPANS) if kind == "distinct"]
    duplicates = [i for i, (_, _, kind) in enumerate(SPANS) if kind == "duplicate"]
    return {
        "same": max(hamming(a, b) for hashes in by_scene for a in hashes for b in hashes),
        "duplicate": max(hamming(a, b) for i in duplicates for a in by_scene[0] for b in by_scene[i]),
        "distinct": min(hamming(a, b) for i, j in itertools.combinations(distinct, 2)
                        for a in by_scene[i] for b in by_scene[j]),
    }


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


def test_synthetic_scenes_keep_their_margins(ffmpeg_build, lecture_video):
    margins = scene_margins(lecture_video)
    assert margins["same"] <= 2
    assert margins["duplicate"] <= DUPLICATE_BITS - 2
    assert margins["distinct"] >= DUPLICATE_BITS + 6


def test_keyframes_of_a_synthetic_lecture(ffmpeg_build, lecture):
    video, unit = lecture
    pages, candidates = extract_keyframes(video, unit)
    assert_one_page_per_scene(pages)
    assert page_tuples(load_pages(unit)) == page_tuples(pages)
    raw = json.loads(UnitPaths(unit).pages.read_text(encoding="utf-8"))
    assert [set(entry) for entry in raw] == [{"n", "label", "text", "image", "time"}] * 4
    assert candidates in CANDIDATES
    folder = unit / "sources" / "keyframes"
    assert names(folder) == FRAMES
    for name in FRAMES:
        with Image.open(folder / name) as image:
            assert (image.format, image.size) == ("JPEG", (320, 240))
    assert not (unit / "sources" / "source.json").exists()


def test_keyframe_times_follow_the_file_when_the_video_starts_late(tmp_path, ffmpeg_build):
    # 30 s of audio, and a video track that starts 6 s later: the text slide from 6 s on the
    # file's timeline, the figure from 15 s. Frame k must be the picture at k * 2 s of the file,
    # not of the video track, or the times (and the saved frames) would run 6 s early. The
    # samples before 6 s repeat the first picture, so on the sampled timeline the text slide
    # starts at 0 s; the figure's page must come from 15 s on, not from 9 s.
    folder = tmp_path / "课程 资料"
    folder.mkdir()
    video = folder / "第1周 lecture.mkv"
    subprocess.run(
        [ffmpeg_build, "-hide_banner", "-nostdin",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
         "-itsoffset", "6", "-f", "lavfi",
         "-i", f"{picture(*TEXT, 9)}[a];{picture(*FIGURE, 9)}[b];[a][b]concat=n=2:v=1:a=0",
         "-map", "0:a", "-map", "1:v", "-c:a", "flac", "-c:v", "mpeg4", "-q:v", "2", str(video)],
        check=True, capture_output=True,
    )
    unit = folder / "第1周"
    pages, candidates = extract_keyframes(video, unit)
    starts = (0.0, 15.0)
    assert len(pages) == len(starts)
    for page, start in zip(pages, starts):
        assert start <= page.time <= start + 2 * SAMPLE_SECONDS
    assert candidates in (12, 13)  # 0 s to the end of the video at 24 s, every 2 s

    # Each saved frame shows the picture that was hashed for its time, and not the other one:
    # it is closer to its own sample than to the other page's, by at least 6 bits.
    sampled = sampled_hashes(video, 1)
    for page, other in zip(pages, reversed(pages)):
        with Image.open(unit / "sources" / "slides" / page.image) as saved:
            h = frame_hash(saved)
        own = hamming(h, sampled[round(page.time / SAMPLE_SECONDS)])
        elsewhere = hamming(h, sampled[round(other.time / SAMPLE_SECONDS)])
        assert own < elsewhere
        assert elsewhere - own >= 6


def test_keyframes_errors_name_the_video(ffmpeg_build, lecture, monkeypatch):
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


def test_keyframes_replace_only_with_force(ffmpeg_build, lecture):
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
    assert_one_page_per_scene(pages)
    assert names(folder) == FRAMES

    partial = unit / "sources" / "keyframes.partial"
    partial.mkdir()
    (partial / "x.jpg").write_bytes(b"stray")
    extract_keyframes(video, unit, force=True)
    assert not partial.exists()
    assert names(folder) == FRAMES


def test_a_failed_run_changes_nothing(ffmpeg_build, lecture, monkeypatch):
    video, unit = lecture
    pages, _ = extract_keyframes(video, unit)
    assert_one_page_per_scene(pages)
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


def test_cli_keyframes_prints_the_pages_path(ffmpeg_build, lecture, capsys):
    video, unit = lecture
    argv = ["keyframes", "--video", str(video), "--unit", str(unit)]
    assert main(argv) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    out = json.loads(lines[0])
    path = unit / "sources" / "slides" / "pages.json"
    assert out["status"] == "ok" and out["frames"] == 4 and out["candidates"] in CANDIDATES
    assert out["path"] == str(path)
    assert_one_page_per_scene(load_pages(unit))
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


def test_cli_keyframes_input_errors_are_json_objects(tmp_path, capsys, ffmpeg_build):
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


# ---- K8: the documents ------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "tutor-any-lecture"


def read(path):
    return path.read_text(encoding="utf-8")


def test_documents_name_keyframes():
    local = read(SKILL_DIR / "references" / "adapters" / "local.md")
    assert "tutor-any-lecture keyframes --video F --unit DIR" in local
    assert "slides text" in local
    assert "keyframes --video F --unit DIR" in read(SKILL_DIR / "SKILL.md")
    assert "`keyframes`" in read(SKILL_DIR / "references" / "gate.md")
    assert "sources/keyframes/" in read(SKILL_DIR / "references" / "output-targets" / "markdown.md")
    stale = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "skills").rglob("*.md"))
             if "keyframes-deferred" in read(p)]
    assert stale == []
