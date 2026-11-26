import ast
import struct
import sys
import zipfile
from pathlib import Path

import pytest

from fixtures.make_office import office_zip
from tutor_any_lecture import office
from tutor_any_lecture.office import OfficePackage
from tutor_any_lecture.transcript import AcquireError

COMPOUND_FILE = bytes.fromhex("D0CF11E0A1B11AE1") + bytes(504)
PRESENTATION = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst>'
    + "".join(f'<p:sldId id="{256 + k}" r:id="rId{k + 1}"/>' for k in range(40))
    + "</p:sldIdLst></p:presentation>"
)


def test_office_reader_uses_only_the_standard_library():
    tree = ast.parse(Path(office.__file__).read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.append(node.module)
    assert names
    assert all(name.split(".")[0] in sys.stdlib_module_names for name in names), names


def test_relationship_targets_resolve(tmp_path):
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"'
        ' Target="../notesSlides/notesSlide1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"'
        ' Target="/ppt/media/a.png"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"'
        ' Target="https://example.com" TargetMode="External"/>'
        "</Relationships>"
    )
    path = office_zip(tmp_path, "deck.pptx", {
        "ppt/presentation.xml": PRESENTATION,
        "ppt/slides/slide1.xml": "<x/>",
        "ppt/slides/_rels/slide1.xml.rels": rels,
    })
    with OfficePackage(path, ".pptx") as pkg:
        found = pkg.relationships("ppt/slides/slide1.xml")
        assert set(found) == {"rId1", "rId2"}
        assert found["rId1"][1] == "ppt/notesSlides/notesSlide1.xml"
        assert found["rId2"][1] == "ppt/media/a.png"
        assert found["rId1"][0].endswith("/notesSlide")
        assert pkg.relationships("ppt/presentation.xml") == {}


def raw(data):
    def build(folder, name):
        path = folder / name
        path.write_bytes(data)
        return path
    return build


def zipped(parts, encrypted=None):
    def build(folder, name):
        return office_zip(folder, name, parts, encrypted=encrypted)
    return build


def damaged(folder, name):
    # local helper: one byte in the middle of presentation.xml's compressed data flipped
    path = office_zip(folder, name, {"ppt/presentation.xml": PRESENTATION})
    with zipfile.ZipFile(path) as z:
        info = z.getinfo("ppt/presentation.xml")
    data = bytearray(path.read_bytes())
    start = info.header_offset
    assert data[start:start + 4] == b"PK\x03\x04"
    name_len, extra_len = struct.unpack_from("<HH", data, start + 26)
    middle = start + 30 + name_len + extra_len + info.compress_size // 2
    data[middle] ^= 0xFF
    path.write_bytes(bytes(data))
    return path


BROKEN = [
    ("deck.pptx", ".pptx", raw(b"not a zip"),
     "deck.pptx is not a readable .pptx file: it is not a zip archive"),
    ("notes.docx", ".docx", raw(b""),
     "notes.docx is not a readable .docx file: it is not a zip archive"),
    ("deck.pptx", ".pptx", raw(COMPOUND_FILE),
     "deck.pptx is password-protected or an old .ppt file: save it as a .pptx file without a password, "
     "then try again"),
    ("notes.docx", ".docx", raw(COMPOUND_FILE),
     "notes.docx is password-protected or an old .doc file: save it as a .docx file without a password, "
     "then try again"),
    ("deck.pptx", ".pptx", zipped({"[Content_Types].xml": "<Types/>"}),
     "deck.pptx is not a readable .pptx file: it has no ppt/presentation.xml"),
    ("deck.pptx", ".pptx", zipped({"ppt/presentation.xml": "<p:presentation"}),
     "deck.pptx is not a readable .pptx file: ppt/presentation.xml is not valid XML"),
    ("deck.pptx", ".pptx", zipped({"ppt/presentation.xml": '<!DOCTYPE x [<!ENTITY a "aa">]><x>&a;</x>'}),
     "deck.pptx is not a readable .pptx file: ppt/presentation.xml is not valid XML"),
    ("deck.pptx", ".pptx", zipped({"ppt/presentation.xml": PRESENTATION}, encrypted="ppt/presentation.xml"),
     "deck.pptx is password-protected or an old .ppt file: save it as a .pptx file without a password, "
     "then try again"),
    ("deck.pptx", ".pptx", damaged,
     "deck.pptx is not a readable .pptx file: ppt/presentation.xml cannot be read"),
]


@pytest.mark.parametrize(
    "name, kind, build, message", BROKEN,
    ids=["not-a-zip", "empty", "compound-pptx", "compound-docx", "no-part", "bad-xml", "doctype",
         "encrypted-member", "damaged-member"],
)
def test_broken_office_files_end_in_one_error(tmp_path, name, kind, build, message):
    path = build(tmp_path, name)
    with pytest.raises(AcquireError) as caught:
        with OfficePackage(path, kind) as pkg:
            pkg.xml("ppt/presentation.xml")
    assert str(caught.value) == message
    path.unlink()  # fails on Windows while a handle is still open
    assert not path.exists()


def test_missing_optional_part_is_none(tmp_path):
    path = office_zip(tmp_path, "deck.pptx", {"ppt/presentation.xml": PRESENTATION})
    with OfficePackage(path, ".pptx") as pkg:
        assert pkg.xml("ppt/slides/slide9.xml", required=False) is None
        assert office.local_name(pkg.xml("ppt/presentation.xml").tag) == "presentation"


def test_large_parts_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(office, "MAX_PART_BYTES", 10)
    part = "<x>" + "a" * 13 + "</x>"
    assert len(part) == 20
    path = office_zip(tmp_path, "deck.pptx", {"ppt/presentation.xml": part})
    with pytest.raises(AcquireError) as caught:
        with OfficePackage(path, ".pptx") as pkg:
            pkg.xml("ppt/presentation.xml")
    assert str(caught.value).startswith(
        "deck.pptx is not a readable .pptx file: ppt/presentation.xml is larger than"
    )
    path.unlink()
    assert not path.exists()
