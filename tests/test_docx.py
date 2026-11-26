import json
from pathlib import Path

import pytest

from fixtures.make_office import make_docx, office_zip
from tutor_any_lecture.cli import main
from tutor_any_lecture.office import docx_lines
from tutor_any_lecture.source import sha256_file
from tutor_any_lecture.transcript import AcquireError, Segment, Transcript, parse_meeting_export, parse_stamped_txt
from tutor_any_lecture.unit import UnitPaths

ROOT = Path(__file__).resolve().parents[1]
COMPOUND_FILE = bytes.fromhex("D0CF11E0A1B11AE1") + bytes(504)

DOCX_PARAGRAPHS = [
    "Alice Smith\t0:03",
    "Welcome to\nthe course.",
    "  ",
    "<w:p><w:r><w:t>Kept</w:t></w:r><w:del><w:r><w:delText>Gone</w:delText></w:r></w:del></w:p>",
    "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>In a table</w:t></w:r></w:p></w:tc></w:tr></w:tbl>",
    "<w:p><w:r><w:t>A</w:t><w:cr/><w:t>B</w:t></w:r></w:p>",
    '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText>PAGE</w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>7</w:t></w:r>'
    '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>',
    "<w:p><w:r><w:t>Outer</w:t></w:r><w:r><w:txbxContent><w:p><w:r><w:t>Inner</w:t></w:r></w:p>"
    "</w:txbxContent></w:r></w:p>",
]

# A Teams transcript saved as Word, in the layout with the speaker and a time on one line.
HEADER_LINES = [
    "Lecture 3 - Discounting",
    "November 3, 2026, 2:00PM",
    "Alice Smith started transcription",
    "Alice Smith\t0:03",
    "Welcome to the course.",
    "Alice Smith   1:02",
    "Today we cover discounting",
    "and why it matters.",
    "Speaker 2   1:02:03",
    "What rate do we use?",
    "Alice Smith stopped transcription",
]
HEADER_SEGMENTS = [
    Segment(3.0, 62.0, "Welcome to the course."),
    Segment(62.0, 3723.0, "Today we cover discounting and why it matters."),
    Segment(3723.0, 3728.0, "What rate do we use?"),
]


# ---- D1: a .docx becomes lines -------------------------------------------------


@pytest.mark.parametrize("strict", [False, True], ids=["transitional", "strict"])
def test_docx_paragraphs_become_lines(tmp_path, strict):
    path = make_docx(tmp_path, DOCX_PARAGRAPHS, strict=strict)
    assert docx_lines(path) == [
        "Alice Smith\t0:03", "Welcome to", "the course.", "Kept", "In a table", "A", "B", "7", "Outer", "Inner",
    ]


def test_docx_without_its_document_part(tmp_path):
    path = office_zip(tmp_path, "notes.docx", {"[Content_Types].xml": "<Types/>"})
    with pytest.raises(AcquireError) as caught:
        docx_lines(path)
    assert str(caught.value) == "notes.docx is not a readable .docx file: it has no word/document.xml"


# ---- D2: three layouts of a meeting export -------------------------------------


def test_teams_range_layout():
    lines = [
        "0:0:0.0 --> 0:0:4.990", "Alice Smith", "Welcome to the course.",
        "0:0:4.990 --> 0:0:9.120", "Alice Smith", "Today we cover discounting", "and why it matters.",
        "0:0:9.120 --> 0:0:12.0", "What rate do we use?",
    ]
    assert parse_meeting_export(lines, None) == [
        Segment(0.0, 4.99, "Welcome to the course."),
        Segment(4.99, 9.12, "Today we cover discounting and why it matters."),
        Segment(9.12, 12.0, "What rate do we use?"),
    ]
    assert parse_meeting_export(["00:00:03,570 --> 00:00:07,110", "Bob Jones", "Yes."], None) == [
        Segment(3.57, 7.11, "Yes."),
    ]
    assert parse_meeting_export(["0:0:1.2345678 --> 0:0:2.5", "Done."], None) == [Segment(1.234, 2.5, "Done.")]


def test_teams_header_layout():
    assert parse_meeting_export(HEADER_LINES, None) == HEADER_SEGMENTS
    assert parse_meeting_export(HEADER_LINES, 3725.0)[-1].end == 3725.0


def test_zoom_header_layout():
    lines = ["[Alice Smith] 00:00:03", "Welcome to the course.", "[Bob Jones] 00:01:02", "What rate do we use?"]
    assert parse_meeting_export(lines, None) == [
        Segment(3.0, 62.0, "Welcome to the course."),
        Segment(62.0, 67.0, "What rate do we use?"),
    ]


def test_stamped_layout():
    lines = ["[0:00] Welcome back to the course", "[0:07] Today we cover discounting", "and why it matters"]
    segments = parse_meeting_export(lines, None)
    assert segments == parse_stamped_txt("\n".join(lines), None)
    assert len(segments) == 2


def test_lines_that_are_not_headers():
    lines = ["Alice Smith 0:03", "Welcome.", "the meeting ends at 5:30", "03/11/2026 14:00", "Week 12 starts 9:00"]
    assert parse_meeting_export(lines, None) == [
        Segment(3.0, 8.0, "Welcome. the meeting ends at 5:30 03/11/2026 14:00 Week 12 starts 9:00"),
    ]


def test_no_time_stamps_no_segments():
    assert parse_meeting_export(["Week 3 reading list", "Chapter 2"], None) == []


# ---- D3: acquire import reads a .docx, and Zoom's .txt ---------------------------


def test_cli_imports_a_teams_docx(tmp_path, capsys):
    folder = tmp_path / "课程 资料"
    path = make_docx(folder, HEADER_LINES, name="Lecture 3.docx")
    unit = folder / "第1周"
    assert main(["acquire", "import", "--file", str(path), "--unit", str(unit)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    paths = UnitPaths(unit)
    assert Transcript.from_json(paths.transcript).segments == HEADER_SEGMENTS
    source = json.loads(paths.source.read_text(encoding="utf-8"))
    assert source["title"] == "Lecture 3"
    assert source["kind"] == "transcript" and source["acquisition"] == "import"
    assert source["inputs_sha256"] == {"Lecture 3.docx": sha256_file(path)}


def _zip_without_document(folder: Path, name: str) -> Path:
    return office_zip(folder, name, {"[Content_Types].xml": "<Types/>"})


def _raw(data: bytes):
    def build(folder: Path, name: str) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        return folder / name
    return build


@pytest.mark.parametrize("name, build, message", [
    ("notes.docx", _raw(b"PK not really"), "notes.docx is not a readable .docx file: it is not a zip archive"),
    ("notes.docx", _raw(COMPOUND_FILE),
     "notes.docx is password-protected or an old .doc file: save it as a .docx file without a password, "
     "then try again"),
    ("notes.docx", _zip_without_document, "notes.docx is not a readable .docx file: it has no word/document.xml"),
    ("handout.docx", lambda folder, name: make_docx(folder, ["Week 3 reading list"], name=name),
     "no timed segments found"),
], ids=["not-a-zip", "compound-file", "no-document-part", "no-time-stamps"])
def test_cli_docx_errors_are_the_error_object(tmp_path, capsys, name, build, message):
    path = build(tmp_path / "课程 资料", name)
    unit = tmp_path / "课程 资料" / "第1周"
    assert main(["acquire", "import", "--file", str(path), "--unit", str(unit)]) == 1
    assert capsys.readouterr().out == json.dumps({"status": "error", "message": message}) + "\n"
    assert not UnitPaths(unit).transcript.exists()


def test_cli_imports_a_zoom_txt(tmp_path, capsys):
    path = tmp_path / "zoom.txt"
    path.write_text("[Alice Smith] 00:00:03\nWelcome to the course.\n", encoding="utf-8", newline="\n")
    unit = tmp_path / "u"
    assert main(["acquire", "import", "--file", str(path), "--unit", str(unit)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert Transcript.from_json(UnitPaths(unit).transcript).segments == [Segment(3.0, 8.0, "Welcome to the course.")]


# ---- W1: documents name DOCX transcripts -----------------------------------------


def _read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_documents_name_docx_transcripts(monkeypatch, capsys):
    adapter = _read("skills", "tutor-any-lecture", "references", "adapters", "import.md")
    assert "`.docx`" in adapter and "Teams" in adapter and "Zoom" in adapter
    assert "DOCX is not read" not in adapter and "and any other suffix" not in adapter
    assert "kind of file it does not read" in _read("skills", "tutor-any-lecture", "references", "gate.md")
    readme = _read("README.md")
    assert "a Teams DOCX export" in readme and "a Zoom transcript TXT" in readme and "Zoom DOCX" not in readme
    readme_zh = _read("README.zh-CN.md")
    assert "Teams 导出的 DOCX" in readme_zh and "Zoom 的 TXT 转写" in readme_zh
    changelog = _read("CHANGELOG.md").split("\n## ")[1]  # the newest entry
    assert "DOCX" in changelog and "Zoom transcript TXT" in changelog

    monkeypatch.setenv("COLUMNS", "80")
    with pytest.raises(SystemExit) as exc:
        main(["acquire", "--help"])
    assert exc.value.code == 0
    assert "(.srt, .vtt, .json, .txt, .docx)" in " ".join(capsys.readouterr().out.split())
