"""slides --photos and slides text: photos of slides become the unit's pages."""

import hashlib
import json
import socket

import PIL
import pytest
from PIL import Image

from fixtures.make_pdf import make_pdf
from tutor_any_lecture import doctor
from tutor_any_lecture.acquire.importer import import_transcript
from tutor_any_lecture.cli import main
from tutor_any_lecture.slides import extract_pdf, photo_order
from tutor_any_lecture.unit import UnitPaths

ORIENTATION = 0x0112


# ---- local helpers ----

def folder_of(tmp_path):
    """The materials folder every test writes its photos into."""
    return tmp_path / "课程 资料" / "第1周"


def unit_of(tmp_path):
    """The unit folder; it does not exist before the first run."""
    return folder_of(tmp_path) / "unit"


def write_photo(path, size=(40, 30), fmt=None, orientation=None, colour=(200, 40, 40)):
    """A small one-colour photo; JPEG unless the name ends in .png or ``fmt`` names a format."""
    if fmt is None:
        fmt = "PNG" if path.suffix.lower() == ".png" else "JPEG"
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, colour)
    options = {}
    if orientation is not None:
        exif = Image.Exif()
        exif[ORIENTATION] = orientation
        options["exif"] = exif.tobytes()
    image.save(path, fmt, **options)
    return path


def photos(tmp_path, *names):
    return [write_photo(folder_of(tmp_path) / name) for name in names]


def run(argv, capsys):
    """(exit code, stdout, stderr) of one command."""
    code = main([str(a) for a in argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def run_photos(paths, unit, capsys, *extra):
    return run(["slides", "--photos", *paths, "--unit", unit, *extra], capsys)


def stored_pages(unit):
    return json.loads(UnitPaths(unit).pages.read_text(encoding="utf-8"))


def slides_dir(unit):
    return UnitPaths(unit).pages.parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---- P2. three or more photos become the unit's pages ----

def test_photos_become_pages_in_name_order(tmp_path, capsys):
    given = photos(tmp_path, "IMG_10.jpg", "img_2.JPG", "IMG_1.png")
    unit = unit_of(tmp_path)
    code, out, err = run_photos(given, unit, capsys)
    assert code == 0 and err == ""
    assert json.loads(out) == {"status": "ok", "pages": 3, "path": str(UnitPaths(unit).pages)}
    assert stored_pages(unit) == [
        {"n": 1, "label": None, "text": "", "image": "photo-001.png"},
        {"n": 2, "label": None, "text": "", "image": "photo-002.jpg"},
        {"n": 3, "label": None, "text": "", "image": "photo-003.jpg"},
    ]
    originals = {"photo-001.png": "IMG_1.png", "photo-002.jpg": "img_2.JPG", "photo-003.jpg": "IMG_10.jpg"}
    for copy, original in originals.items():
        assert (slides_dir(unit) / copy).read_bytes() == (folder_of(tmp_path) / original).read_bytes()


def test_photo_order_is_natural(tmp_path):
    folder = folder_of(tmp_path)
    given = ["slide 3.jpeg", "IMG_10.jpg", "a.jpg", "img_2.JPG", "1.jpg", "IMG_1.png"]
    expected = ["1.jpg", "a.jpg", "IMG_1.png", "img_2.JPG", "IMG_10.jpg", "slide 3.jpeg"]
    assert photo_order([folder / n for n in given]) == [folder / n for n in expected]


# ---- P3. copies an agent can read ----

def test_a_turned_photo_is_copied_upright(tmp_path, capsys):
    folder = folder_of(tmp_path)
    turned = write_photo(folder / "1.jpg", size=(40, 20), orientation=6)
    plain = [write_photo(folder / "2.jpg"), write_photo(folder / "3.png")]
    unit = unit_of(tmp_path)
    assert run_photos([turned, *plain], unit, capsys)[0] == 0
    with Image.open(slides_dir(unit) / "photo-001.jpg") as copy:
        assert copy.format == "JPEG" and copy.size == (20, 40)
        assert copy.getexif().get(ORIENTATION) in (None, 1)
    assert (slides_dir(unit) / "photo-002.jpg").read_bytes() == plain[0].read_bytes()
    assert (slides_dir(unit) / "photo-003.png").read_bytes() == plain[1].read_bytes()


def test_a_large_photo_is_scaled_to_2000_pixels(tmp_path, capsys):
    folder = folder_of(tmp_path)
    wide = write_photo(folder / "1.png", size=(2400, 1200))
    tall = write_photo(folder / "2.jpg", size=(1500, 3000))
    small = write_photo(folder / "3.jpg")
    unit = unit_of(tmp_path)
    assert run_photos([wide, tall, small], unit, capsys)[0] == 0
    with Image.open(slides_dir(unit) / "photo-001.png") as copy:
        assert copy.format == "PNG" and copy.size == (2000, 1000)
    with Image.open(slides_dir(unit) / "photo-002.jpg") as copy:
        assert copy.format == "JPEG" and copy.size == (1000, 2000)


# ---- P4. what --photos refuses, before it writes anything ----

def case_two_photos(tmp_path):
    return photos(tmp_path, "1.jpg", "2.jpg"), "slides --photos needs at least 3 photos, got 2"


def case_missing_photo(tmp_path):
    missing = folder_of(tmp_path) / "3.jpg"
    return [*photos(tmp_path, "1.jpg", "2.jpg"), missing], f"photo not found: {missing}"


def case_heic(tmp_path):
    heic = folder_of(tmp_path) / "a.heic"
    heic.parent.mkdir(parents=True, exist_ok=True)
    heic.write_bytes(b"not read")
    return [*photos(tmp_path, "1.jpg", "2.jpg"), heic], "a.heic: HEIC photos are not read; export them as JPEG or PNG"


def case_gif(tmp_path):
    gif = write_photo(folder_of(tmp_path) / "a.gif", fmt="GIF")
    return [*photos(tmp_path, "1.jpg", "2.jpg"), gif], "a.gif: photos must be JPEG or PNG (.jpg, .jpeg, .png)"


def case_not_an_image(tmp_path):
    fake = folder_of(tmp_path) / "fake.jpg"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_bytes(b"not an image")
    return [*photos(tmp_path, "1.jpg", "2.jpg"), fake], "fake.jpg is not a readable JPEG or PNG image"


def case_gif_named_png(tmp_path):
    anim = write_photo(folder_of(tmp_path) / "anim.png", fmt="GIF")
    return [*photos(tmp_path, "1.jpg", "2.jpg"), anim], "anim.png is not a readable JPEG or PNG image"


def case_given_twice(tmp_path):
    one, two = photos(tmp_path, "1.jpg", "2.jpg")
    return [one, two, one], "the same photo is given twice: 1.jpg"


@pytest.mark.parametrize("case", [
    case_two_photos, case_missing_photo, case_heic, case_gif, case_not_an_image, case_gif_named_png,
    case_given_twice,
], ids=lambda c: c.__name__[len("case_"):])
def test_photo_errors_name_the_file_and_write_nothing(tmp_path, capsys, case):
    given, message = case(tmp_path)
    unit = unit_of(tmp_path)
    code, out, err = run_photos(given, unit, capsys)
    assert code == 1
    assert json.loads(out) == {"status": "error", "message": message}
    assert len(out.splitlines()) == 1 and err == ""
    assert not unit.exists()


def test_malformed_source_json_stops_photos(tmp_path, capsys):
    unit = unit_of(tmp_path)
    paths = UnitPaths(unit).ensure()
    paths.source.write_text("{}\n", encoding="utf-8", newline="\n")
    code, out, err = run_photos(photos(tmp_path, "1.jpg", "2.jpg", "3.jpg"), unit, capsys)
    assert code == 1 and err == ""
    result = json.loads(out)
    assert result["status"] == "error" and result["message"].startswith("source.json: ")
    assert not slides_dir(unit).exists()
    assert paths.source.read_text(encoding="utf-8") == "{}\n"


def test_cli_slides_photos_usage(tmp_path, capsys):
    given = [str(p) for p in photos(tmp_path, "1.jpg", "2.jpg", "3.jpg")]
    pdf = str(tmp_path / "slides.pdf")
    deck = str(tmp_path / "deck.pptx")
    unit = str(unit_of(tmp_path))
    for argv in (
        ["slides", "--photos", *given],
        ["slides", "--photos", *given, "--pdf", pdf, "--unit", unit],
        ["slides", "--photos", *given, "--pptx", deck, "--unit", unit],
        ["slides", "--photos", *given, "--images", "--unit", unit],
        ["slides", "--pdf", pdf, "--unit", unit, "--force"],
    ):
        code, out, err = run(argv, capsys)
        assert code == 2, argv
        assert out == ""
        lines = err.splitlines()
        assert len(lines) == 1 and "slides --photos" in lines[0]
        assert not unit_of(tmp_path).exists()


# ---- P5. source.json records each photo ----

def test_photos_write_a_slides_only_source(tmp_path, capsys):
    given = photos(tmp_path, "1.jpg", "2.png", "3.jpg")
    unit = unit_of(tmp_path)
    assert run_photos(given, unit, capsys)[0] == 0
    source = json.loads(UnitPaths(unit).source.read_text(encoding="utf-8"))
    assert source["kind"] == "slides-only" and source["acquisition"] == "slides"
    assert source["title"] == "第1周"
    assert source["tool_versions"] == {"Pillow": PIL.__version__}
    assert source["inputs_sha256"] == {
        "photo-001.jpg": sha256(given[0]), "photo-002.png": sha256(given[1]), "photo-003.jpg": sha256(given[2]),
    }


def test_photo_digests_survive_an_import_and_give_way_to_a_deck(tmp_path, capsys):
    unit = unit_of(tmp_path)
    vtt = folder_of(tmp_path) / "lecture.vtt"
    vtt.parent.mkdir(parents=True, exist_ok=True)
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nCompound interest\n", encoding="utf-8", newline="\n")
    import_transcript(vtt, unit, None, False)
    given = photos(tmp_path, "1.jpg", "2.jpg", "3.jpg")
    assert run_photos(given, unit, capsys)[0] == 0
    with_photos = {
        "lecture.vtt": sha256(vtt),
        "photo-001.jpg": sha256(given[0]), "photo-002.jpg": sha256(given[1]), "photo-003.jpg": sha256(given[2]),
    }

    def inputs():
        return json.loads(UnitPaths(unit).source.read_text(encoding="utf-8"))["inputs_sha256"]

    assert inputs() == with_photos
    import_transcript(vtt, unit, None, True)
    assert inputs() == with_photos
    pdf = make_pdf(tmp_path / "deck", ["Compound interest\n1/1"])
    extract_pdf(pdf, unit)
    assert inputs() == {"lecture.vtt": sha256(vtt), "slides.pdf": sha256(pdf)}


# ---- P6. a rerun keeps page text unless forced ----

def test_a_rerun_keeps_page_text_unless_forced(tmp_path, capsys):
    given = photos(tmp_path, "1.jpg", "2.jpg", "3.jpg")
    unit = unit_of(tmp_path)
    assert run_photos(given, unit, capsys)[0] == 0
    pages_json = UnitPaths(unit).pages
    entries = stored_pages(unit)
    entries[0]["text"] = "Compound interest"
    pages_json.write_text(json.dumps(entries) + "\n", encoding="utf-8", newline="\n")
    before = pages_json.read_bytes()

    code, out, err = run_photos(given, unit, capsys)
    assert code == 3 and out == ""
    assert err.splitlines() == [f"{pages_json} already holds page text; rerun with --force to replace it"]
    assert pages_json.read_bytes() == before

    code, out, err = run_photos(given, unit, capsys, "--force")
    assert code == 0 and err == ""
    assert stored_pages(unit)[0]["text"] == ""


def test_a_rerun_removes_old_copies_only(tmp_path, capsys):
    unit = unit_of(tmp_path)
    assert run_photos(photos(tmp_path, "1.jpg", "2.jpg", "3.jpg", "4.jpg"), unit, capsys)[0] == 0
    notes = slides_dir(unit) / "notes.md"
    notes.write_text("kept\n", encoding="utf-8", newline="\n")
    assert run_photos(photos(tmp_path, "a.jpg", "b.jpg", "c.jpg"), unit, capsys)[0] == 0
    assert not (slides_dir(unit) / "photo-004.jpg").exists()
    assert notes.read_text(encoding="utf-8") == "kept\n"
    assert sorted(p.name for p in slides_dir(unit).iterdir()) == [
        "notes.md", "pages.json", "photo-001.jpg", "photo-002.jpg", "photo-003.jpg",
    ]

    own = [slides_dir(unit) / f"photo-00{k}.jpg" for k in (1, 2, 3)]
    before = [p.read_bytes() for p in own]
    code, out, err = run_photos(own, unit, capsys, "--force")
    assert code == 0 and err == ""
    assert [p.read_bytes() for p in own] == before
    assert [e["image"] for e in stored_pages(unit)] == ["photo-001.jpg", "photo-002.jpg", "photo-003.jpg"]


# ---- P7. slides text gives one page its text ----

def photo_unit(tmp_path, capsys):
    """A unit made from three photos, its pages without text."""
    unit = unit_of(tmp_path)
    assert run_photos(photos(tmp_path, "1.jpg", "2.jpg", "3.jpg"), unit, capsys)[0] == 0
    return unit


def text_file(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def run_text(unit, page, file, capsys, *extra):
    return run(["slides", "text", "--unit", unit, "--page", page, "--file", file, *extra], capsys)


def test_slides_text_sets_one_page(tmp_path, capsys):
    unit = photo_unit(tmp_path, capsys)
    page_text = text_file(tmp_path, "第2页.txt", b"\xef\xbb\xbfCompound interest\r\nr = 5%\r\n\r\n")
    code, out, err = run_text(unit, 2, page_text, capsys)
    assert code == 0 and err == ""
    assert json.loads(out) == {"status": "ok", "page": 2, "remaining": [1, 3], "path": str(UnitPaths(unit).pages)}
    entries = stored_pages(unit)
    assert entries[1]["text"] == "Compound interest\nr = 5%"
    assert [e["text"] for e in entries[::2]] == ["", ""]
    assert not any("time" in e for e in entries)


def test_slides_text_records_and_keeps_a_time(tmp_path, capsys):
    unit = photo_unit(tmp_path, capsys)
    page_text = text_file(tmp_path, "p2.txt", b"Compound interest\n")
    assert run_text(unit, 2, page_text, capsys, "--time", "754.5")[0] == 0
    assert stored_pages(unit)[1]["time"] == 754.5
    other = text_file(tmp_path, "p2b.txt", b"Discounting\n")
    assert run_text(unit, 2, other, capsys, "--force")[0] == 0
    entries = stored_pages(unit)
    assert entries[1]["text"] == "Discounting" and entries[1]["time"] == 754.5
    assert "time" not in entries[0] and "time" not in entries[2]


def test_slides_text_errors(tmp_path, capsys):
    unit = photo_unit(tmp_path, capsys)
    pages_json = UnitPaths(unit).pages
    good = text_file(tmp_path, "p.txt", b"Compound interest\n")

    def error(argv_unit, page, file, message, *extra):
        before = pages_json.read_bytes() if pages_json.exists() else None
        code, out, err = run_text(argv_unit, page, file, capsys, *extra)
        assert code == 1 and err == ""
        assert json.loads(out) == {"status": "error", "message": message}
        assert (pages_json.read_bytes() if pages_json.exists() else None) == before

    missing = tmp_path / "missing.txt"
    error(unit, 1, missing, f"text file not found: {missing}")
    error(unit, 1, text_file(tmp_path, "latin.txt", b"caf\xe9\n"), "latin.txt is not UTF-8 text")
    error(unit, 1, text_file(tmp_path, "blank.txt", b"\xef\xbb\xbf \r\n\t\r\n"), "blank.txt holds no text")
    error(unit, 9, good, "pages.json has no page 9")
    bare = tmp_path / "bare"
    UnitPaths(bare).ensure()
    error(bare, 1, good, f"{UnitPaths(bare).pages} not found; run slides --photos or slides --pdf first")

    entries = stored_pages(unit)
    entries[0]["time"] = -1
    pages_json.write_text(json.dumps(entries) + "\n", encoding="utf-8", newline="\n")
    error(unit, 2, good, "pages.json: entry 0: time must be seconds (a number from 0) or null, got -1")
    del entries[0]["time"]
    pages_json.write_text(json.dumps(entries) + "\n", encoding="utf-8", newline="\n")

    assert run_text(unit, 1, good, capsys)[0] == 0
    before = pages_json.read_bytes()
    code, out, err = run_text(unit, 1, good, capsys)
    assert code == 3 and out == ""
    assert err.splitlines() == ["page 1 already has text; rerun with --force to replace it"]
    assert pages_json.read_bytes() == before

    pdf = make_pdf(tmp_path / "deck", ["Compound interest\n1/1"])
    given = [str(p) for p in photos(tmp_path, "a.jpg", "b.jpg", "c.jpg")]
    text_argv = ["text", "--unit", str(unit), "--page", "2", "--file", str(good)]
    for parent in (["--pdf", str(pdf)], ["--pptx", str(tmp_path / "deck.pptx")], ["--photos", *given, "--unit", str(unit)]):
        code, out, err = run(["slides", *parent, *text_argv], capsys)
        assert code == 2 and out == ""
        assert len(err.splitlines()) == 1 and "slides text" in err
    assert pages_json.read_bytes() == before

    for time in ("-1", "x", "nan", "inf"):
        with pytest.raises(SystemExit) as exc:
            main(["slides", "text", "--unit", str(unit), "--page", "2", "--file", str(good), "--time", time])
        assert exc.value.code == 2
        assert capsys.readouterr().out == ""
    assert pages_json.read_bytes() == before


# ---- N1. photos go nowhere ----

def test_photo_commands_open_no_connection(tmp_path, monkeypatch, capsys):
    def refuse(*args, **kwargs):
        raise AssertionError("a photo command opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    unit = photo_unit(tmp_path, capsys)
    page_text = text_file(tmp_path, "p1.txt", b"Compound interest\n")
    code, out, err = run_text(unit, 1, page_text, capsys)
    assert code == 0 and json.loads(out)["remaining"] == [2, 3]
    monkeypatch.setattr(doctor, "CHECKS", [c for c in doctor.CHECKS if c.name == "vision"])
    assert doctor.run_doctor(vision_word="x")["checks"] == [
        {"name": "vision", "ok": False, "detail": "'x' is not the word in the probe image",
         "fix": doctor.CHECKS[0].fix}
    ]
