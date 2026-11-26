"""Office files (.pptx, .docx): zip packages of XML parts, read with the standard library.

Every way a file can be broken (not a zip, password-protected, an old binary format, a
missing or damaged part, a part that is not XML) ends in one ``AcquireError`` that names
the file. Elements and attributes are matched by local name, so Strict OOXML files read
like the usual ones.
"""

from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

from .transcript import AcquireError

# A part is read with at most this many bytes (plus one, to tell a longer part).
MAX_PART_BYTES = 64 * 1024 * 1024

# An OLE compound file: how an encrypted Office file, and the old binary formats, are stored.
_COMPOUND_FILE = bytes.fromhex("D0CF11E0A1B11AE1")
_OLD_FORMAT = {".pptx": ".ppt", ".docx": ".doc"}
# What reading a damaged member raises: a bad CRC or header, broken deflate data, a
# truncated stream, a compression method zipfile does not support.
_UNREADABLE_MEMBER = (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError)


def local_name(tag: str) -> str:
    """``{namespace}name`` → ``name``."""
    return tag.rpartition("}")[2]


def namespace(tag: str) -> str:
    """``{namespace}name`` → ``namespace``; ``""`` for an unqualified name."""
    return tag[1:].partition("}")[0] if tag.startswith("{") else ""


def namespaced_attribute(element: ET.Element, name: str) -> str | None:
    """The value of the namespaced attribute whose local name is ``name``, else ``None``.

    ``namespaced_attribute(sldId, "id")`` is ``r:id`` in either relationships namespace;
    an unqualified ``id`` beside it is never read.
    """
    for key, value in element.attrib.items():
        if key.startswith("{") and local_name(key) == name:
            return value
    return None


def children(element: ET.Element | None, name: str) -> list[ET.Element]:
    """The direct children of ``element`` with local name ``name`` (none for ``None``)."""
    if element is None:
        return []
    return [c for c in element if local_name(c.tag) == name]


def child(element: ET.Element | None, name: str) -> ET.Element | None:
    """The first direct child of ``element`` with local name ``name``, else ``None``."""
    found = children(element, name)
    return found[0] if found else None


class OfficePackage:
    """An open .pptx or .docx; a context manager that closes the zip on exit.

    Opening refuses a file that is not a zip or that is password-protected. A failed
    open leaves no handle behind, so the file can be deleted at once (Windows included).
    """

    def __init__(self, path: Path, kind: str) -> None:
        if kind not in _OLD_FORMAT:
            raise ValueError(f"kind must be one of {', '.join(_OLD_FORMAT)}; got {kind!r}")
        self.path = Path(path)
        self.kind = kind
        self.name = self.path.name
        with open(self.path, "rb") as f:
            head = f.read(len(_COMPOUND_FILE))
        if head == _COMPOUND_FILE:
            raise self._protected()
        try:
            # ZipFile closes the file itself when its constructor fails.
            self._zip = zipfile.ZipFile(self.path)
        except (zipfile.BadZipFile, EOFError, ValueError) as e:
            raise self._unreadable("it is not a zip archive") from e
        if any(info.flag_bits & 0x1 for info in self._zip.infolist()):
            self._zip.close()
            raise self._protected()

    def __enter__(self) -> OfficePackage:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._zip.close()

    def _protected(self) -> AcquireError:
        return AcquireError(
            f"{self.name} is password-protected or an old {_OLD_FORMAT[self.kind]} file: "
            f"save it as a {self.kind} file without a password, then try again"
        )

    def _unreadable(self, why: str) -> AcquireError:
        return AcquireError(f"{self.name} is not a readable {self.kind} file: {why}")

    def xml(self, part: str, required: bool = True) -> ET.Element | None:
        """The root element of ``part``; ``None`` for a missing part when not ``required``.

        The part is read with a bound (``MAX_PART_BYTES``) and refused if it holds a
        DOCTYPE, so no entity is ever expanded.
        """
        try:
            info = self._zip.getinfo(part)
        except KeyError:
            if not required:
                return None
            raise self._unreadable(f"it has no {part}") from None
        try:
            with self._zip.open(info) as f:
                data = f.read(MAX_PART_BYTES + 1)
        except _UNREADABLE_MEMBER as e:
            raise self._unreadable(f"{part} cannot be read") from e
        if len(data) > MAX_PART_BYTES:
            raise self._unreadable(f"{part} is larger than {MAX_PART_BYTES // 2**20} MB")
        # NUL bytes removed, so a UTF-16 part's DOCTYPE is found as well.
        if b"<!DOCTYPE" in data.replace(b"\x00", b""):
            raise self._unreadable(f"{part} is not valid XML")
        try:
            return ET.fromstring(data)
        except (ET.ParseError, LookupError, ValueError) as e:  # LookupError: an unknown encoding
            raise self._unreadable(f"{part} is not valid XML") from e

    def relationships(self, part: str) -> dict[str, tuple[str, str]]:
        """``{id: (type, target part)}`` from ``<folder>/_rels/<file>.rels``; ``{}`` without one.

        A target is resolved against the part's folder, or from the package root when it
        starts with ``/``. External targets (``TargetMode="External"``) are left out.
        """
        folder, file = posixpath.split(part)
        root = self.xml(posixpath.join(folder, "_rels", f"{file}.rels"), required=False)
        if root is None:
            return {}
        found: dict[str, tuple[str, str]] = {}
        for rel in root:
            if local_name(rel.tag) != "Relationship" or rel.get("TargetMode") == "External":
                continue
            rid, target = rel.get("Id"), rel.get("Target")
            if not rid or not target:
                continue
            if target.startswith("/"):
                resolved = posixpath.normpath(target.lstrip("/"))
            else:
                resolved = posixpath.normpath(posixpath.join(folder, target))
            found[rid] = (rel.get("Type") or "", resolved)
        return found


# Inside a paragraph, these subtrees hold no text of it: a nested paragraph (a text box's
# content) gives lines of its own, and properties hold tab stops (w:tabs/w:tab), not tabs.
_NOT_PARAGRAPH_TEXT = frozenset({"p", "pPr", "rPr"})


def _paragraph_text(paragraph: ET.Element) -> str:
    """The text of one ``w:p``: ``w:t`` texts, ``w:tab`` as a tab, ``w:br``/``w:cr`` as a newline.

    ``w:delText`` and ``w:instrText`` are other names, so deleted text and field codes are
    not read. Walked with a stack, so a deeply nested part cannot exhaust the recursion limit.
    """
    parts: list[str] = []
    stack = list(reversed(paragraph))
    while stack:
        element = stack.pop()
        name = local_name(element.tag)
        if name in _NOT_PARAGRAPH_TEXT:
            continue
        if name == "t":
            parts.append(element.text or "")
        elif name == "tab":
            parts.append("\t")
        elif name in ("br", "cr"):
            parts.append("\n")
        stack.extend(reversed(element))
    return "".join(parts)


def docx_lines(path: Path) -> list[str]:
    """The text lines of a .docx's ``word/document.xml``, stripped, blank lines dropped.

    Every ``w:p`` in document order (table cells included) gives its lines; a paragraph
    nested in a text box comes after the paragraph that holds it, apart from its text.
    """
    with OfficePackage(path, ".docx") as pkg:
        root = pkg.xml("word/document.xml")
    lines: list[str] = []
    # iter() walks in document order, a parent before what it holds.
    for element in root.iter():
        if local_name(element.tag) == "p":
            lines.extend(_paragraph_text(element).split("\n"))
    return [line.strip() for line in lines if line.strip()]
