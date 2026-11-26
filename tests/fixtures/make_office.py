"""Write minimal Office packages (.pptx) as zips of XML parts. Test fixture; no dependencies."""
import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

_NAMESPACES = {
    False: {
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    },
    True: {  # Strict OOXML
        "p": "http://purl.oclc.org/ooxml/presentationml/main",
        "a": "http://purl.oclc.org/ooxml/drawingml/main",
        "r": "http://purl.oclc.org/ooxml/officeDocument/relationships",
    },
}
_EXTRA_NAMESPACES = {
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "a14": "http://schemas.microsoft.com/office/drawing/2010/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}
_PACKAGE_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"


def office_zip(folder: Path, name: str, parts: dict, encrypted: str | None = None) -> Path:
    """Zip ``parts`` (part name to str or bytes), every member deflated; returns the path.

    ``encrypted`` names a member whose central-directory record gets bit 0 of its
    general-purpose flag set, as a password-protected zip marks it.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for part, data in parts.items():
            z.writestr(part, data.encode("utf-8") if isinstance(data, str) else data)
    if encrypted is not None:
        _set_encrypted_flag(path, encrypted)
    return path


def _set_encrypted_flag(path: Path, member: str) -> None:
    data = bytearray(path.read_bytes())
    end = data.rfind(b"PK\x05\x06")
    count = struct.unpack_from("<H", data, end + 10)[0]
    offset = struct.unpack_from("<I", data, end + 16)[0]
    for _ in range(count):
        assert data[offset:offset + 4] == b"PK\x01\x02"
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, offset + 28)
        name = data[offset + 46:offset + 46 + name_len].decode("utf-8")
        if name == member:
            flags = struct.unpack_from("<H", data, offset + 8)[0]
            struct.pack_into("<H", data, offset + 8, flags | 1)
            path.write_bytes(bytes(data))
            return
        offset += 46 + name_len + extra_len + comment_len
    raise KeyError(member)


def _root_attributes(strict: bool) -> str:
    ns = {**_NAMESPACES[strict], **_EXTRA_NAMESPACES}
    return " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in ns.items())


def _rel_type(strict: bool, name: str) -> str:
    return f"{_NAMESPACES[strict]['r']}/{name}"


def _rels(entries: list[tuple[str, str, str]]) -> str:
    body = "".join(f'<Relationship Id="{i}" Type="{t}" Target="{target}"/>' for i, t, target in entries)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{_PACKAGE_RELS}">{body}</Relationships>'


def _paragraphs(text: str) -> str:
    return "".join(f"<a:p><a:r><a:t>{escape(line)}</a:t></a:r></a:p>" for line in text.split("\n"))


def _text_shape(text: str, shape_id: int = 2, placeholder: str | None = None) -> str:
    ph = f'<p:ph type="{placeholder}"/>' if placeholder else ""
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Shape {shape_id}"/><p:cNvSpPr/><p:nvPr>{ph}</p:nvPr></p:nvSpPr>'
        f"<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>{_paragraphs(text)}</p:txBody></p:sp>"
    )


def _sp_tree(shapes: str) -> str:
    return (
        '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f"<p:grpSpPr/>{shapes}</p:spTree></p:cSld>"
    )


def _notes_slide(text: str, strict: bool) -> str:
    shapes = (
        '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image"/><p:cNvSpPr/><p:nvPr><p:ph type="sldImg"/></p:nvPr>'
        "</p:nvSpPr><p:spPr/></p:sp>"
        '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes"/><p:cNvSpPr/><p:nvPr><p:ph type="body" idx="1"/></p:nvPr>'
        f"</p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>{_paragraphs(text)}</p:txBody></p:sp>"
        '<p:sp><p:nvSpPr><p:cNvPr id="4" name="Slide Number"/><p:cNvSpPr/><p:nvPr><p:ph type="sldNum" idx="5"/>'
        '</p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:fld id="{0}" type="slidenum">'
        "<a:t>1</a:t></a:fld></a:p></p:txBody></p:sp>"
    )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:notes {_root_attributes(strict)}>{_sp_tree(shapes)}</p:notes>'


def make_pptx(
    folder: Path,
    slides: list[str],
    name: str = "deck.pptx",
    notes: dict[int, str] | None = None,
    order: list[int] | None = None,
    absolute: bool = False,
    strict: bool = False,
) -> Path:
    """A .pptx with one slide file per entry of ``slides`` (slide1.xml, slide2.xml, ...).

    A slide is a str (one text shape, "\\n" between paragraphs) or raw XML starting with
    "<", put into ``p:spTree`` as written. ``notes`` maps a slide's file number to its
    notes text. ``order`` lists file numbers in ``sldIdLst`` order (default: file order);
    a number with no slide file gets an ``sldId`` whose ``r:id`` has no relationship.
    ``absolute`` writes relationship targets from the package root; ``strict`` uses the
    Strict OOXML namespaces.
    """
    notes = notes or {}
    order = list(range(1, len(slides) + 1)) if order is None else order
    parts: dict[str, str] = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": _rels([("rId1", _rel_type(strict, "officeDocument"), "ppt/presentation.xml")]),
    }
    ids = "".join(f'<p:sldId id="{256 + k}" r:id="rId{number}"/>' for k, number in enumerate(order))
    parts["ppt/presentation.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<p:presentation {_root_attributes(strict)}><p:sldIdLst>{ids}</p:sldIdLst></p:presentation>"
    )
    presentation_rels = []
    for number, slide in enumerate(slides, start=1):
        target = f"/ppt/slides/slide{number}.xml" if absolute else f"slides/slide{number}.xml"
        presentation_rels.append((f"rId{number}", _rel_type(strict, "slide"), target))
        shapes = slide if slide.startswith("<") else _text_shape(slide)
        parts[f"ppt/slides/slide{number}.xml"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f"<p:sld {_root_attributes(strict)}>{_sp_tree(shapes)}</p:sld>"
        )
        if number in notes:
            notes_target = (
                f"/ppt/notesSlides/notesSlide{number}.xml" if absolute else f"../notesSlides/notesSlide{number}.xml"
            )
            parts[f"ppt/slides/_rels/slide{number}.xml.rels"] = _rels(
                [("rId1", _rel_type(strict, "notesSlide"), notes_target)]
            )
            parts[f"ppt/notesSlides/notesSlide{number}.xml"] = _notes_slide(notes[number], strict)
    parts["ppt/_rels/presentation.xml.rels"] = _rels(presentation_rels)
    return office_zip(folder, name, parts)
