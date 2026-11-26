import pytest

from fixtures.make_office import make_docx, office_zip
from tutor_any_lecture.office import docx_lines
from tutor_any_lecture.transcript import AcquireError, Segment, parse_meeting_export, parse_stamped_txt

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
