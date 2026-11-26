import json
import zipfile
from pathlib import Path

import pytest

from fixtures.make_office import make_pptx, office_zip
from fixtures.make_pdf import make_pdf
from tutor_any_lecture import cli
from tutor_any_lecture.acquire import router
from tutor_any_lecture.acquire.importer import import_transcript
from tutor_any_lecture.cli import main
from tutor_any_lecture.slides import Page, extract_pdf, extract_pptx, load_pages
from tutor_any_lecture.source import SLIDE_DECK_SUFFIXES, sha256_file
from tutor_any_lecture.transcript import AcquireError
from tutor_any_lecture.unit import UnitPaths


def shape(paragraphs, placeholder=None):
    # local helper: one p:sp; each paragraph is a list of runs (str) or the XML of a:p's content
    ph = f'<p:ph type="{placeholder}"/>' if placeholder else ""
    body = "".join(
        "<a:p>" + ("".join(f"<a:r><a:t>{run}</a:t></a:r>" for run in p) if isinstance(p, list) else p) + "</a:p>"
        for p in paragraphs
    )
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="9" name="s"/><p:cNvSpPr/><p:nvPr>{ph}</p:nvPr></p:nvSpPr>'
        f"<p:spPr/><p:txBody><a:bodyPr/>{body}</p:txBody></p:sp>"
    )


def presentation_ids(path):
    # local helper: the attributes of every sldId in presentation.xml, as written
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("ppt/presentation.xml"))
    return [dict(e.attrib) for e in root.iter() if e.tag.endswith("}sldId")]


@pytest.mark.parametrize("strict", [False, True], ids=["transitional", "strict"])
@pytest.mark.parametrize("absolute", [False, True], ids=["relative", "absolute"])
def test_slides_follow_the_presentation_order(tmp_path, absolute, strict):
    deck = make_pptx(tmp_path / "a", ["Alpha", "Beta", "Gamma"], order=[3, 1, 2], absolute=absolute, strict=strict)
    pages = extract_pptx(deck, tmp_path / "unit-a")
    assert [p.text for p in pages] == ["Gamma", "Alpha", "Beta"]
    assert [p.n for p in pages] == [1, 2, 3]
    assert all(p.label is None and p.image is None for p in pages)
    ids = presentation_ids(deck)
    assert [{k.rpartition("}")[2]: v for k, v in a.items() if "}" not in k} for a in ids] == [
        {"id": "256"}, {"id": "257"}, {"id": "258"}]
    assert [next(v for k, v in a.items() if k.endswith("}id")) for a in ids] == ["rId3", "rId1", "rId2"]

    ten = [f"S{k}" for k in range(1, 11)]
    deck = make_pptx(tmp_path / "b", ten, absolute=absolute, strict=strict)
    assert [p.text for p in extract_pptx(deck, tmp_path / "unit-b")] == ten


def test_missing_slides_are_errors(tmp_path):
    deck = make_pptx(tmp_path / "a", ["Alpha"], order=[1, 2])
    with pytest.raises(AcquireError) as caught:
        extract_pptx(deck, tmp_path / "unit-a")
    assert str(caught.value) == "deck.pptx is not a readable .pptx file: slide 2 is missing"
    assert not (tmp_path / "unit-a").exists()

    deck = make_pptx(tmp_path / "b", [])
    with pytest.raises(AcquireError) as caught:
        extract_pptx(deck, tmp_path / "unit-b")
    assert str(caught.value) == "deck.pptx has no slides"
    assert not (tmp_path / "unit-b").exists()

    with pytest.raises(FileNotFoundError) as caught:
        extract_pptx(tmp_path / "gone.pptx", tmp_path / "unit-c")
    assert str(caught.value) == f"PPTX not found: {tmp_path / 'gone.pptx'}"
    assert not (tmp_path / "unit-c").exists()


def test_slide_text_in_reading_order(tmp_path):
    tree = "".join([
        shape([["Compound interest"]], "title"),
        shape([["Rate applies to the balance"], ["Past interest", " included"]]),
        shape(['<a:fld id="{1}" type="slidenum"><a:t>3</a:t></a:fld>'], "sldNum"),
        '<p:grpSp><p:nvGrpSpPr><p:cNvPr id="20" name="g"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        + shape([["Grouped note"]]) + "</p:grpSp>",
        '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="21" name="t"/><p:cNvGraphicFramePr/><p:nvPr/>'
        '</p:nvGraphicFramePr><p:xfrm/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/'
        'drawingml/2006/table"><a:tbl><a:tblGrid/><a:tr h="1">'
        "<a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Year</a:t></a:r></a:p></a:txBody></a:tc>"
        "<a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Balance</a:t></a:r></a:p></a:txBody></a:tc>"
        "</a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>",
        shape([["Week 3 footer"]], "ftr"),
        shape([["1/12/2026"]], "dt"),
        shape(["<a:r><a:t>Line one</a:t></a:r><a:br/><a:r><a:t>line two</a:t></a:r>"]),
        '<mc:AlternateContent><mc:Choice Requires="a14">'
        + shape(["<a:r><a:t>Rate r</a:t></a:r><a14:m><m:oMath><m:r><m:t>x</m:t></m:r></m:oMath></a14:m>"])
        + "</mc:Choice><mc:Fallback>" + shape([["Rate r"]]) + "</mc:Fallback></mc:AlternateContent>",
        shape(["", "<a:r><a:t>   </a:t></a:r>"]),
    ])
    deck = make_pptx(tmp_path, [tree])
    [page] = extract_pptx(deck, tmp_path / "unit")
    assert page.text == (
        "Compound interest\nRate applies to the balance\nPast interest included\nGrouped note\n"
        "Year\nBalance\nLine one\nline two\nRate r"
    )
    assert page.text.count("Rate r") == 1 and "x" not in page.text


def test_speaker_notes_are_kept_apart(tmp_path):
    notes = "Mention the 1626 example\nAsk the class"
    deck = make_pptx(tmp_path, ["Compound interest\nRate applies", "Summary"], notes={1: notes})
    unit = tmp_path / "unit"
    pages = extract_pptx(deck, unit)
    assert [p.notes for p in pages] == [notes, ""]
    assert "Mention" not in pages[0].text
    stored = json.loads(UnitPaths(unit).pages.read_text(encoding="utf-8"))
    assert stored == [
        {"n": 1, "label": None, "text": "Compound interest\nRate applies", "image": None, "notes": notes},
        {"n": 2, "label": None, "text": "Summary", "image": None, "notes": ""},
    ]
    assert load_pages(unit) == pages


def test_pages_json_notes_must_be_text(tmp_path):
    path = UnitPaths(tmp_path).pages
    path.parent.mkdir(parents=True)
    entry = {"n": 1, "label": None, "text": "Summary", "image": None, "notes": 3}
    path.write_text(json.dumps([entry]) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError) as caught:
        load_pages(tmp_path)
    assert str(caught.value) == "pages.json: entry 0: notes must be text or null, got 3"
    entry["notes"] = None
    path.write_text(json.dumps([entry]) + "\n", encoding="utf-8", newline="\n")
    assert load_pages(tmp_path) == [Page(1, None, "Summary", None, None)]


def test_deck_digests_follow_the_newest_deck(tmp_path):
    unit = tmp_path / "unit"
    deck = make_pptx(tmp_path, ["Compound interest"])
    vtt = tmp_path / "cues.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nCompound interest\n", encoding="utf-8", newline="\n")
    pdf = make_pdf(tmp_path, ["Compound interest\n1/1"])

    def inputs():
        return json.loads(UnitPaths(unit).source.read_text(encoding="utf-8"))["inputs_sha256"]

    extract_pptx(deck, unit)
    import_transcript(vtt, unit, None, False)
    assert inputs() == {"cues.vtt": sha256_file(vtt), "deck.pptx": sha256_file(deck)}
    extract_pdf(pdf, unit)
    assert inputs() == {"cues.vtt": sha256_file(vtt), "slides.pdf": sha256_file(pdf)}
    extract_pptx(deck, unit)
    assert inputs() == {"cues.vtt": sha256_file(vtt), "deck.pptx": sha256_file(deck)}

    other = UnitPaths(tmp_path / "other")
    other.ensure()
    other.source.write_bytes(b'{"kind": "transcript"}\n')
    with pytest.raises(ValueError, match="source.json"):
        extract_pptx(deck, tmp_path / "other")
    assert not other.pages.exists()

    assert {s for s, cls in router._BY_SUFFIX.items() if cls == "slides"} == set(SLIDE_DECK_SUFFIXES)


def test_slides_only_source_from_a_deck(tmp_path):
    deck = make_pptx(tmp_path, ["Compound interest"], name="Week Deck.pptx")
    extract_pptx(deck, tmp_path / "unit")
    src = json.loads(UnitPaths(tmp_path / "unit").source.read_text(encoding="utf-8"))
    from tutor_any_lecture import __version__

    assert src["kind"] == "slides-only" and src["acquisition"] == "slides" and src["title"] == "Week Deck"
    assert src["tool_versions"] == {"tutor-any-lecture": __version__}
    assert src["inputs_sha256"] == {"Week Deck.pptx": sha256_file(deck)}


# ---- slides --pptx on the command line ------------------------------------------


def test_cli_slides_pptx(tmp_path, capsys):
    folder = tmp_path / "课程 资料"
    deck = make_pptx(folder, ["Compound interest", "Discounting", "Summary"], name="Lecture Deck.PPTX",
                     notes={2: "Ask the class"})
    unit = folder / "第1周"
    assert main(["slides", "--pptx", str(deck), "--unit", str(unit)]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "status": "ok", "pages": 3, "labelled": 0, "notes": 1, "path": str(UnitPaths(unit).pages),
    }
    assert captured.err == ""
    src = json.loads(UnitPaths(unit).source.read_text(encoding="utf-8"))
    assert src["kind"] == "slides-only" and src["title"] == "Lecture Deck"
    assert src["inputs_sha256"] == {"Lecture Deck.PPTX": sha256_file(deck)}


def test_cli_slides_pptx_usage(tmp_path, capsys):
    deck = make_pptx(tmp_path, ["Compound interest"])
    pdf = make_pdf(tmp_path, ["Compound interest\n1/1"])
    unit, a, b = tmp_path / "unit", tmp_path / "A", tmp_path / "B"
    for argv in (
        ["slides"],
        ["slides", "--pptx", str(deck)],
        ["slides", "--pdf", str(pdf), "--pptx", str(deck), "--unit", str(unit)],
        ["slides", "--pptx", str(deck), "--unit", str(a), "suspects", "--unit", str(b)],
    ):
        assert main(argv) == 2, argv
        captured = capsys.readouterr()
        assert captured.err == cli._SLIDES_USAGE + "\n" and captured.out == ""
    assert main(["slides", "--pptx", str(deck), "--unit", str(unit), "--images"]) == 2
    captured = capsys.readouterr()
    assert captured.err == (
        "slides --images works with --pdf only: a .pptx gives its text and speaker notes, no page images\n"
    )
    assert captured.out == ""
    assert not unit.exists() and not a.exists() and not b.exists()


@pytest.mark.parametrize("flag, name", [
    ("--pptx", "notes.docx"), ("--pdf", "deck.pptx"), ("--pptx", "slides.pdf"), ("--pdf", "deck.key"),
])
def test_cli_slides_names_what_it_reads(tmp_path, capsys, flag, name):
    path = tmp_path / name
    path.write_bytes(b"not read")
    unit = tmp_path / "unit"
    assert main(["slides", flag, str(path), "--unit", str(unit)]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "error", "message": (
        f"{name} cannot be read with {flag}: slides reads a .pdf file with --pdf, a .pptx file with --pptx "
        "and three or more .jpg, .jpeg or .png photos with --photos (save .ppt, .key and .odp decks as PDF first)"
    )}
    assert captured.err == ""
    assert not unit.exists()


def broken_not_a_zip(path):
    path.write_bytes(b"not a zip")


def broken_compound_file(path):
    path.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + bytes(504))


def broken_no_presentation(path):
    office_zip(path.parent, path.name, {"[Content_Types].xml": "<Types/>"})


@pytest.mark.parametrize("build, message", [
    (broken_not_a_zip, "deck.pptx is not a readable .pptx file: it is not a zip archive"),
    (broken_compound_file, "deck.pptx is password-protected or an old .ppt file: "
                           "save it as a .pptx file without a password, then try again"),
    (broken_no_presentation, "deck.pptx is not a readable .pptx file: it has no ppt/presentation.xml"),
], ids=["not-a-zip", "compound-file", "no-presentation"])
def test_cli_broken_pptx_is_the_error_object(tmp_path, capsys, build, message):
    path = tmp_path / "deck.pptx"
    build(path)
    unit = tmp_path / "unit"
    assert main(["slides", "--pptx", str(path), "--unit", str(unit)]) == 1
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"status": "error", "message": message}
    assert captured.err == ""
    assert not unit.exists()
    path.unlink()
    assert not path.exists()


# ---- the documents send decks to slides --pptx ------------------------------------


ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "tutor-any-lecture"


def doc(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_documents_send_pptx_decks_to_slides():
    command = "`tutor-any-lecture slides --pptx F --unit DIR`"
    skill = doc("skills", "tutor-any-lecture", "SKILL.md")
    assert command in skill and "then `slides`, then `acquire local`" in skill and "a PPTX deck" not in skill
    adapters = SKILL_DIR / "references" / "adapters"
    local = (adapters / "local.md").read_text(encoding="utf-8")
    moodle = (adapters / "moodle.md").read_text(encoding="utf-8")
    for text in (local, moodle):
        assert command in text
        assert "run an acquisition first` on stderr" not in text
        assert "an existing source.json gains the deck's digest" in text
        assert "never overwrites an existing source.json" not in text
        assert "an existing source.json is left alone" not in text
    for name in ("url.md", "import.md"):
        assert "--pptx F" in (adapters / name).read_text(encoding="utf-8"), name
    gate = (SKILL_DIR / "references" / "gate.md").read_text(encoding="utf-8")
    for text in (
        (SKILL_DIR / "references" / "output-targets" / "markdown.md").read_text(encoding="utf-8"),
        gate,
        (adapters / "TEMPLATE.md").read_text(encoding="utf-8"),
    ):
        assert "`slides --pptx`" in text
    assert "Speaker notes" in gate and "never put them in quotation marks" in gate
    readme = doc("README.md")
    assert "PowerPoint (.pptx)" in readme and "A PPTX deck or photos of slides must be exported to PDF first" not in readme
    readme_zh = doc("README.zh-CN.md")
    assert "PowerPoint(.pptx)" in readme_zh and "PPTX 课件或课件照片要先导出成 PDF" not in readme_zh
    changelog = doc("CHANGELOG.md")
    newest = changelog.split("\n## ")[1]
    assert "PowerPoint" in newest
