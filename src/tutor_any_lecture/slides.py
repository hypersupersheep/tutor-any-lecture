"""Slides: PDF pages, PowerPoint slides or photos of slides → sources/slides/pages.json, footer labels, and slide terms."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .office import OfficePackage, child, children, local_name, namespace, namespaced_attribute
from .plan import read_json
from .source import SLIDE_PHOTO_SUFFIXES, SourceInfo, add_slide_digest, set_slide_digests, sha256_file
from .textstats import cjk_runs, cjk_script
from .transcript import AcquireError
from .unit import UnitPaths

# A footer such as "3/12" or " 3 / 12 " on the last non-empty line of a page.
FOOTER_RE = re.compile(r"^\s*(\d+)\s*/\s*\d+\s*$")


@dataclass
class Page:
    n: int  # 1-based PDF page number, or the slide's position in a .pptx deck
    label: str | None
    text: str
    image: str | None = None
    notes: str | None = None  # a .pptx slide's speaker notes ("" for none); None for a PDF page
    time: float | None = None  # the second of the recording the page is shown at, when known


def _last_nonempty_line(text: str) -> str | None:
    for line in reversed(text.split("\n")):
        if line.strip():
            return line
    return None


def _footer_label(text: str) -> str | None:
    last = _last_nonempty_line(text)
    if last is None:
        return None
    m = FOOTER_RE.match(last)
    return m.group(1) if m else None


def extract_pdf(pdf: Path, unit: Path, images: bool = False) -> list[Page]:
    """Read every page of ``pdf`` into the unit's pages.json (and page images when asked).

    The PDF is opened and its text read before anything is created in the unit, so an
    unreadable file (not a PDF, damaged, encrypted) raises ``AcquireError`` and writes nothing.

    The PDF's sha256 goes into source.json's ``inputs_sha256``: a new slides-only
    source.json when the unit has none, else an entry added to the existing one (a
    malformed one raises ``ValueError`` before anything is written).
    """
    pdf = Path(pdf)
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf}")
    source = UnitPaths(unit).source
    if source.exists():
        SourceInfo.read(source)  # a malformed source.json stops the run here, unchanged

    import importlib.metadata

    import pdfplumber  # imported here so the rest of this module stays cheap to import

    try:
        doc = pdfplumber.open(pdf)
    # pdfplumber and pdfminer raise many unrelated types on a bad file (PdfminerException,
    # PSEOF, KeyError, zlib.error, ...); this try holds only the pdfplumber calls.
    except Exception as e:
        raise AcquireError(f"{pdf.name} is not a readable PDF") from e
    with doc:
        try:
            texts = [page.extract_text() or "" for page in doc.pages]
        except Exception as e:
            raise AcquireError(f"{pdf.name} is not a readable PDF") from e

        paths = UnitPaths(unit).ensure()
        slides_dir = paths.pages.parent
        slides_dir.mkdir(exist_ok=True)  # before the first page image or pages.json
        pages: list[Page] = []
        for n, (page, text) in enumerate(zip(doc.pages, texts), start=1):
            image = None
            if images:
                image = f"page-{n:03d}.png"
                # Rendering (pypdfium2 and Pillow) raises many unrelated types, as opening does.
                try:
                    page.to_image(resolution=110).save(slides_dir / image)
                except Exception as e:
                    raise AcquireError(f"could not render page {n} of {pdf.name}") from e
            pages.append(Page(n, _footer_label(text), text, image))

    write_pages(paths.pages, pages)
    _record_deck(paths, pdf, {"pdfplumber": importlib.metadata.version("pdfplumber")})
    return pages


# Keys left out of a pages.json entry when they are None, so a PDF's entries keep their four keys.
_OMITTED_WHEN_NONE = ("notes", "time")


def write_pages(path: Path, pages: list[Page]) -> None:
    """Write ``pages`` to the pages.json at ``path``, creating its folder.

    ``notes`` and ``time`` are written only where they are not ``None``. Every writer of
    pages.json goes through this function.
    """
    path = Path(path)
    payload = [
        {k: v for k, v in dataclasses.asdict(p).items() if not (k in _OMITTED_WHEN_NONE and v is None)}
        for p in pages
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _record_deck(paths: UnitPaths, deck: Path, tool_versions: dict) -> None:
    """Add the deck's sha256 to source.json, or write a slides-only source.json when there is none."""
    digest = sha256_file(deck)
    if paths.source.exists():
        add_slide_digest(paths.source, deck.name, digest)
    else:
        SourceInfo(
            kind="slides-only",
            title=deck.stem,
            url=None,
            platform=None,
            duration=None,
            lecture_language=None,
            acquisition="slides",
            health={},
            tool_versions=tool_versions,
            inputs_sha256={deck.name: digest},
        ).write(paths.source)


# Placeholders whose text is not the slide's: the slide number, the date, the footer.
_SKIPPED_PLACEHOLDERS = frozenset({"sldNum", "dt", "ftr"})
# OMML, how an equation is stored: never read, so its m:t is not taken for an a:t.
_MATH_NAMESPACES = frozenset({
    "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "http://purl.oclc.org/ooxml/officeDocument/math",
})
_PRESENTATION = "ppt/presentation.xml"


def _placeholder_type(sp) -> str | None:
    """The ``p:ph`` type of a shape (``"obj"`` when the placeholder names none); ``None`` for no placeholder."""
    ph = child(child(child(sp, "nvSpPr"), "nvPr"), "ph")
    if ph is None:
        return None
    return ph.get("type", "obj")


def _first_choice(alternate):
    """The first ``mc:Choice`` of an ``mc:AlternateContent``; ``mc:Fallback`` is never read."""
    return child(alternate, "Choice")


def _paragraph_lines(p) -> list[str]:
    """One ``a:p``: the ``a:t`` of its runs and fields, a line ended at each ``a:br``."""
    lines: list[str] = []
    current: list[str] = []

    def walk(container) -> None:
        for el in container:
            if namespace(el.tag) in _MATH_NAMESPACES:
                continue
            name = local_name(el.tag)
            if name in ("r", "fld"):
                t = child(el, "t")
                if t is not None and t.text:
                    current.append(t.text)
            elif name == "br":
                lines.append("".join(current))
                current.clear()
            elif name == "AlternateContent":
                choice = _first_choice(el)
                if choice is not None:
                    walk(choice)

    walk(p)
    lines.append("".join(current))
    return lines


def _body_lines(tx_body) -> list[str]:
    return [line for p in children(tx_body, "p") for line in _paragraph_lines(p)]


def _tree_lines(container, keep) -> list[str]:
    """The text lines of the shapes in ``container`` (an spTree, a group, an mc:Choice), in document order.

    ``keep`` takes a shape's placeholder type and says whether its text is read.
    Pictures, charts and SmartArt are not read; a table's cells are, row by row.
    """
    lines: list[str] = []
    for el in container:
        name = local_name(el.tag)
        if name == "sp":
            if keep(_placeholder_type(el)):
                lines += _body_lines(child(el, "txBody"))
        elif name == "grpSp":
            lines += _tree_lines(el, keep)
        elif name == "graphicFrame":
            table = child(child(child(el, "graphic"), "graphicData"), "tbl")
            for row in children(table, "tr"):
                for cell in children(row, "tc"):
                    lines += _body_lines(child(cell, "txBody"))
        elif name == "AlternateContent":
            choice = _first_choice(el)
            if choice is not None:
                lines += _tree_lines(choice, keep)
    return lines


def _shape_text(root, keep) -> str:
    """The text of a slide or notes slide: stripped lines, blank ones dropped, joined with "\\n"."""
    tree = child(child(root, "cSld"), "spTree")
    if tree is None:
        return ""
    return "\n".join(line.strip() for line in _tree_lines(tree, keep) if line.strip())


def _read_deck(pkg: OfficePackage) -> list[Page]:
    """Every slide of the deck, in the order of ``p:sldIdLst``, each ``r:id`` resolved through the relationships."""
    rels = pkg.relationships(_PRESENTATION)
    ids = children(child(pkg.xml(_PRESENTATION), "sldIdLst"), "sldId")
    if not ids:
        raise AcquireError(f"{pkg.name} has no slides")
    pages: list[Page] = []
    for n, sld_id in enumerate(ids, start=1):
        rel = rels.get(namespaced_attribute(sld_id, "id"))  # r:id; the unqualified id is not read
        slide = pkg.xml(rel[1], required=False) if rel is not None and rel[0].endswith("/slide") else None
        if slide is None:
            raise AcquireError(f"{pkg.name} is not a readable .pptx file: slide {n} is missing")
        text = _shape_text(slide, lambda kind: kind not in _SKIPPED_PLACEHOLDERS)
        notes = ""
        for rel_type, target in pkg.relationships(rel[1]).values():
            if rel_type.endswith("/notesSlide"):
                notes_slide = pkg.xml(target, required=False)
                if notes_slide is not None:
                    notes = _shape_text(notes_slide, lambda kind: kind == "body")
                break
        pages.append(Page(n, None, text, None, notes))
    return pages


def extract_pptx(pptx: Path, unit: Path) -> list[Page]:
    """Read every slide of ``pptx`` into the unit's pages.json: text and speaker notes, no images.

    The whole deck is read before anything is created in the unit, so a broken file
    (not a zip, password-protected, a missing or damaged part) raises ``AcquireError``
    and writes nothing. source.json is handled as ``extract_pdf`` handles it.
    """
    pptx = Path(pptx)
    if not pptx.is_file():
        raise FileNotFoundError(f"PPTX not found: {pptx}")
    paths = UnitPaths(unit)
    if paths.source.exists():
        SourceInfo.read(paths.source)  # a malformed source.json stops the run here, unchanged
    with OfficePackage(pptx, ".pptx") as pkg:
        pages = _read_deck(pkg)
    paths.ensure()
    write_pages(paths.pages, pages)
    _record_deck(paths, pptx, {"tutor-any-lecture": __version__})
    return pages


# The copy of a photo of a slide in sources/slides/, as ``extract_photos`` names it.
PHOTO_COPY_RE = re.compile(r"photo-[0-9]{3,}\.(?:jpg|png)")
# The longest side, in pixels, of a copy an agent is asked to read.
_LONGEST_SIDE = 2000
# EXIF orientations 2 to 8 mean the camera stored the picture mirrored or turned.
_ORIENTATION_TAG = 0x0112
_SUFFIX_OF_FORMAT = {"JPEG": "jpg", "PNG": "png"}


def _natural_key(name: str) -> list:
    """``IMG_2`` before ``IMG_10``: digit runs compare as numbers, the rest without letter case.

    ``re.split`` with a group gives text at even places and digits at odd ones, so two keys
    never compare a number with text.
    """
    return [int(part) if i % 2 else part.casefold() for i, part in enumerate(re.split(r"([0-9]+)", name))]


def photo_order(paths) -> list[Path]:
    """``paths`` in natural file-name order; equal keys are ordered by the whole path."""
    return sorted((Path(p) for p in paths), key=lambda p: (_natural_key(p.name), str(p)))


def _check_photo_names(photos: list[Path]) -> None:
    """The checks that need no image read: count, suffix, existence, a photo given twice."""
    if len(photos) < 3:
        raise ValueError(f"slides --photos needs at least 3 photos, got {len(photos)}")
    for photo in photos:
        suffix = photo.suffix.lower()
        if suffix == ".heic":
            raise ValueError(f"{photo.name}: HEIC photos are not read; export them as JPEG or PNG")
        if suffix not in SLIDE_PHOTO_SUFFIXES:
            raise ValueError(f"{photo.name}: photos must be JPEG or PNG (.jpg, .jpeg, .png)")
        if not photo.is_file():
            raise FileNotFoundError(f"photo not found: {photo}")
    seen: set[Path] = set()
    for photo in photos:
        resolved = photo.resolve()
        if resolved in seen:
            raise ValueError(f"the same photo is given twice: {photo.name}")
        seen.add(resolved)


def _photo_copy(photo: Path, data: bytes) -> tuple[bytes, str]:
    """The bytes of the copy of one photo and its suffix (``jpg`` or ``png``, from its format).

    A photo stored turned (EXIF orientation 2 to 8) or longer than 2000 px is re-encoded:
    upright, scaled to 2000 px on its longer side, JPEG at quality 90 or PNG. Any other photo
    is copied byte for byte. A file Pillow cannot open or verify, or one that is neither a
    JPEG nor a PNG, raises ``AcquireError``.
    """
    from PIL import Image, ImageOps

    unreadable = f"{photo.name} is not a readable JPEG or PNG image"
    # Pillow raises many unrelated types on a bad file (UnidentifiedImageError, SyntaxError,
    # OSError, struct.error, ...); these tries hold only Pillow calls.
    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = image.format
            image.verify()
    except Exception as e:
        raise AcquireError(unreadable) from e
    if fmt not in _SUFFIX_OF_FORMAT:
        raise AcquireError(unreadable)
    suffix = _SUFFIX_OF_FORMAT[fmt]
    try:
        with Image.open(io.BytesIO(data)) as image:  # verify() leaves the image unusable: open it again
            turned = image.getexif().get(_ORIENTATION_TAG) in range(2, 9)
            if not turned and max(image.size) <= _LONGEST_SIDE:
                return data, suffix
            upright = ImageOps.exif_transpose(image)
        if max(upright.size) > _LONGEST_SIDE:
            scale = _LONGEST_SIDE / max(upright.size)
            size = (max(1, round(upright.width * scale)), max(1, round(upright.height * scale)))
            upright = upright.resize(size, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        if fmt == "JPEG":
            upright.save(out, "JPEG", quality=90)
        else:
            upright.save(out, "PNG")
    except Exception as e:
        raise AcquireError(unreadable) from e
    return out.getvalue(), suffix


def extract_photos(photos, unit: Path, force: bool = False) -> list[Page]:
    """Copy three or more photos of slides into the unit's sources/slides/ and write pages.json.

    Page k is the k-th photo in natural file-name order (``photo_order``), copied to
    ``photo-<k:03d>.jpg`` or ``.png``; its text stays empty until ``set_page_text`` gives it.
    Every photo is checked and read into memory before the unit changes, so an error
    (``ValueError``, ``FileNotFoundError``, ``AcquireError``) writes nothing, and a photo that
    lives in sources/slides/ survives the removal of the old copies. Page text already given
    stops the run (``FileExistsError``) unless ``force``. source.json records the sha256 of
    each original photo under its copy's name: a new slides-only one when the unit has none,
    else in place of the slide entries of the existing one.
    """
    import PIL

    given = [Path(p) for p in photos]
    _check_photo_names(given)
    ordered = photo_order(given)
    copies = []
    for k, photo in enumerate(ordered, start=1):
        data = photo.read_bytes()
        copy, suffix = _photo_copy(photo, data)
        copies.append((f"photo-{k:03d}.{suffix}", copy, hashlib.sha256(data).hexdigest()))

    paths = UnitPaths(unit)
    if paths.source.exists():
        SourceInfo.read(paths.source)  # a malformed source.json stops the run here, unchanged
    existing = load_pages(unit)  # a malformed pages.json stops the run here, unchanged
    if not force and any(p.text.strip() for p in existing):
        raise FileExistsError(f"{paths.pages} already holds page text; rerun with --force to replace it")

    paths.ensure()
    slides_dir = paths.pages.parent
    slides_dir.mkdir(exist_ok=True)  # before the first copy
    for old in slides_dir.iterdir():
        if PHOTO_COPY_RE.fullmatch(old.name) and old.is_file():
            old.unlink()
    pages: list[Page] = []
    for k, (name, copy, _) in enumerate(copies, start=1):
        (slides_dir / name).write_bytes(copy)
        pages.append(Page(k, None, "", name))
    write_pages(paths.pages, pages)

    digests = {name: digest for name, _, digest in copies}
    if paths.source.exists():
        set_slide_digests(paths.source, digests)
    else:
        SourceInfo(
            kind="slides-only",
            title=ordered[0].absolute().parent.name,
            url=None,
            platform=None,
            duration=None,
            lecture_language=None,
            acquisition="slides",
            health={},
            tool_versions={"Pillow": PIL.__version__},
            inputs_sha256=digests,
        ).write(paths.source)
    return pages


def _read_page_text(path: Path) -> str:
    """The text an agent wrote for one page: UTF-8 (a BOM allowed), line ends made ``\\n``, stripped."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"text file not found: {path}")
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{path.name} is not UTF-8 text") from None
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError(f"{path.name} holds no text")
    return text


def set_page_text(unit: Path, n: int, text_file: Path, time: float | None = None, force: bool = False) -> list[Page]:
    """Give page ``n`` of the unit's pages.json the text in ``text_file`` (and its ``time``, when given).

    Any page may be given, from photos, a PDF or a deck; the other keys of every entry stay.
    A page that already has text is replaced only with ``force`` (else ``FileExistsError``).
    Returns every page, as written.
    """
    text = _read_page_text(text_file)
    path = UnitPaths(unit).pages
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run slides --photos or slides --pdf first")
    pages = load_pages(unit)
    index = next((i for i, p in enumerate(pages) if p.n == n), None)
    if index is None:
        raise ValueError(f"pages.json has no page {n}")
    if pages[index].text.strip() and not force:
        raise FileExistsError(f"page {n} already has text; rerun with --force to replace it")
    changes = {"text": text} if time is None else {"text": text, "time": float(time)}
    pages[index] = dataclasses.replace(pages[index], **changes)
    write_pages(path, pages)
    return pages


def remaining_pages(pages: list[Page]) -> list[int]:
    """The ``n`` of the pages that have an image and no text yet, ascending."""
    return sorted(p.n for p in pages if p.image is not None and not p.text.strip())


def load_pages(unit: Path) -> list[Page]:
    """The pages stored in the unit's pages.json, or ``[]`` when there is none."""
    path = UnitPaths(unit).pages
    if not path.exists():
        return []
    data = read_json(path, "pages.json")
    if not isinstance(data, list):
        raise ValueError("pages.json: the top level must be a list of pages")
    return [_page(d, k) for k, d in enumerate(data)]


def _page(d, k: int) -> Page:
    """One entry of pages.json; a missing key or a wrong type raises ValueError("pages.json: …")."""
    where = f"pages.json: entry {k}"
    if not isinstance(d, dict):
        raise ValueError(f"{where} is not an object")
    missing = [key for key in ("n", "label", "text") if key not in d]
    if missing:
        raise ValueError(f"{where} is missing {', '.join(missing)}")
    if not isinstance(d["n"], int) or isinstance(d["n"], bool):
        raise ValueError(f"{where}: n must be a whole number, got {d['n']!r}")
    for key in ("label", "image", "notes"):
        if not isinstance(d.get(key), (str, type(None))):
            raise ValueError(f"{where}: {key} must be text or null, got {d[key]!r}")
    if d["label"] is not None and not d["label"].isdecimal():
        raise ValueError(f"{where}: label must be digits or null, got {d['label']!r}")
    if not isinstance(d["text"], str):
        raise ValueError(f"{where}: text must be text, got {d['text']!r}")
    time = d.get("time")
    if time is not None:
        # bool is a subclass of int, but true/false is not a time.
        if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0:
            raise ValueError(f"{where}: time must be seconds (a number from 0) or null, got {time!r}")
        time = float(time)
    return Page(d["n"], d["label"], d["text"], d.get("image"), d.get("notes"), time=time)


def max_label(pages: list[Page]) -> int:
    """The highest slide number: the footer label when present, else the page number."""
    return max((int(p.label) if p.label is not None else p.n for p in pages), default=0)


def _strip_outer(chunk: str) -> str:
    """Drop leading and trailing characters that are not letters or digits."""
    start, end = 0, len(chunk)
    while start < end and not chunk[start].isalnum():
        start += 1
    while end > start and not chunk[end - 1].isalnum():
        end -= 1
    return chunk[start:end]


def _term_class(token: str) -> int | None:
    """1: inner capital or a digit (GBM, Black-Scholes, L2); 2: a word of 6+ letters; else None."""
    if any(c.isupper() for c in token[1:]) or any(c.isdigit() for c in token):
        return 1
    if token.isalpha() and len(token) >= 6:
        return 2
    return None


def _pieces(chunk: str) -> list[tuple[str, bool]]:
    """``chunk`` cut into maximal stretches of CJK letters (True) and of other characters (False)."""
    pieces: list[tuple[str, bool]] = []
    for ch in chunk:
        cjk = cjk_script(ch) is not None
        if pieces and pieces[-1][1] == cjk:
            pieces[-1] = (pieces[-1][0] + ch, cjk)
        else:
            pieces.append((ch, cjk))
    return pieces


def _chunk_terms(chunk: str) -> list[tuple[str, int]]:
    """The terms of one whitespace chunk, in order, with their class.

    A stretch of other characters goes through the Latin rules (outer strip, then
    ``_term_class``). A stretch of CJK letters is cut into its runs of one script; a run of
    2 to 10 characters that is not hiragana is a class 2 term, as written. Unclassed tokens
    are not recorded, so they never block a later spelling.
    """
    terms: list[tuple[str, int]] = []
    for piece, cjk in _pieces(chunk):
        if not cjk:
            token = _strip_outer(piece)
            cls = _term_class(token) if token else None
            if cls is not None:
                terms.append((token, cls))
            continue
        for run, script in cjk_runs(piece):
            if script != "hiragana" and 2 <= len(run) <= 10:
                terms.append((run, 2))
    return terms


def term_list(pages: list[Page]) -> list[str]:
    """Distinctive slide terms, uncapped: class 1 in first-seen order, then class 2.

    Each whitespace chunk is read as pieces (``_chunk_terms``), so a deck in Chinese,
    Japanese or Korean gives its runs of one script between punctuation as terms.
    """
    seen: set[str] = set()
    by_class: dict[int, list[str]] = {1: [], 2: []}
    for page in pages:
        lines = page.text.split("\n")
        # Skip the footer line ("3/12"), tested on the text itself rather than page.label.
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                if FOOTER_RE.match(lines[i]):
                    lines = lines[:i] + lines[i + 1:]
                break
        for line in lines:
            for chunk in line.split():
                for token, cls in _chunk_terms(chunk):
                    key = token.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    by_class[cls].append(token)
    return by_class[1] + by_class[2]


def slide_terms(pages: list[Page], limit_chars: int = 200) -> str:
    """Slide terms joined by ", ", at most ``limit_chars`` long, never cutting a term."""
    out = ""
    for term in term_list(pages):
        candidate = f"{out}, {term}" if out else term
        if len(candidate) > limit_chars:
            break
        out = candidate
    return out
