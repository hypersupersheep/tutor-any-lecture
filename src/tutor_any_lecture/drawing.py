"""The concept map as an editable Excalidraw drawing, one per view, from map.json alone.

Pure Python: no browser, no network. The layout is deterministic, so the same map gives
the same file byte for byte:

- the main line (the view's nodes with ``order``) runs down one column in lecture order,
  each node numbered ``(<order>) <label>`` as in the Mermaid export;
- every other node sits in the row of the main node a breadth-first search over the
  view's edges reaches it from first, to the right of the column;
- nodes no main node reaches, or every node of a view without a main line, are "loose":
  rows of at most three below the main rows.

The five kinds differ by shape, stroke width and dash, never by hue; a node with
``key: true`` gets the palette's highlight fill. A legend below the nodes names the
kinds, in Chinese when the unit's plan.json has ``note_language`` zh. Every colour comes
from ``load_palette()``, called on each render.
"""

from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path

from .conceptmap import NODE_TYPES, UnknownView, load_checked_map, view_file
from .palette import load_palette
from .plan import load_plan
from .unit import UnitPaths

LABEL_SIZE, LABEL_LIMIT = 20, 220
VERB_SIZE, VERB_LIMIT = 16, 160
LEGEND_SIZE = 16
LINE_HEIGHT = 1.25
BOX_PAD_X, BOX_PAD_Y, BOX_MIN_W = 40, 30, 120
ELLIPSE_SCALE = 1.42  # an ellipse that holds the box its text needs
SIDE_GAP = 200        # between the column and a side node, and between side or loose nodes
ROW_GAP = 100         # between rows, and between the nodes and the legend
LOOSE_PER_ROW = 3
GAP = 6               # an arrow stops this far from a box; also its binding gap
LANE_X, LANE_STEP = -60, 40
LEGEND_W, LEGEND_H = 48, 32
LEGEND_TEXT_DX, LEGEND_TEXT_DY, LEGEND_ITEM_GAP = 12, 6, 40

# kind -> (element type, strokeWidth, strokeStyle, roundness)
STYLES = {
    "definition": ("rectangle", 2, "solid", None),
    "theorem": ("rectangle", 4, "solid", None),
    "method": ("rectangle", 2, "solid", {"type": 3}),
    "example": ("ellipse", 2, "solid", None),
    "pitfall": ("rectangle", 2, "dashed", None),
}
KEY_STYLE = ("rectangle", 2, "solid", None)
LEGEND_NAMES = {
    "en": {"definition": "definition", "theorem": "theorem", "method": "method",
           "example": "example", "pitfall": "pitfall", "key": "key idea"},
    "zh": {"definition": "定义", "theorem": "定理", "method": "方法",
           "example": "例子", "pitfall": "易错点", "key": "重点"},
}

# The header and warning the Obsidian Excalidraw plugin writes into a drawing it saves.
OBSIDIAN_WARNING = (
    "==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠== You can decompress Drawing data "
    "with the command palette: 'Decompress current Excalidraw file'. For more info check in plugin settings under 'Saving'"
)


# ---- text ------------------------------------------------------------------------


def _wide(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("W", "F")


def text_width(text: str, size: float) -> float:
    """A wide or fullwidth character counts ``size``, every other one ``0.6 * size``."""
    wide = sum(1 for ch in text if _wide(ch))
    return wide * size + (len(text) - wide) * size * 0.6


def _pieces(text: str) -> list[tuple[str, str]]:
    """The runs between break points, each with what precedes it: " " (a dropped space) or ""."""
    runs: list[tuple[str, str]] = []
    run, before = "", ""
    for ch in " ".join(text.split()):
        if ch == " ":
            runs.append((before, run))
            run, before = "", " "
        elif run and (_wide(ch) or _wide(run[-1])):
            # Either side wide: a line may break between the two characters.
            runs.append((before, run))
            run, before = ch, ""
        else:
            run += ch
    if run:
        runs.append((before, run))
    return runs


def wrap(text: str, limit: float, size: float) -> list[str]:
    """Greedy lines no wider than ``limit`` (see ``text_width``), breaking at spaces and next to wide characters.

    Whitespace runs collapse to one space. A run without a break point that is wider than
    ``limit`` starts a new line and is split between characters, each piece as wide as fits.
    """
    lines: list[str] = []
    line = ""
    for before, run in _pieces(text):
        joined = line + before + run if line else run
        if text_width(joined, size) <= limit:
            line = joined
            continue
        if line:
            lines.append(line)
        line = ""
        for ch in run:
            if line and text_width(line + ch, size) > limit:
                lines.append(line)
                line = ""
            line += ch
    if line:
        lines.append(line)
    return lines


class _Text:
    """A text wrapped to its limit and measured."""

    def __init__(self, original: str, size: float, limit: float | None) -> None:
        self.original = original
        self.size = size
        self.lines = (wrap(original, limit, size) if limit is not None else [original]) or [""]
        self.width = max(text_width(line, size) for line in self.lines)
        self.height = len(self.lines) * size * LINE_HEIGHT


# ---- layout -----------------------------------------------------------------------


class _Box:
    def __init__(self, node: dict, position: int) -> None:
        self.node = node
        self.position = position  # in map.json
        label = node["label"]
        if "order" in node:
            label = f"({node['order']}) {label}"
        self.text = _Text(label, LABEL_SIZE, LABEL_LIMIT)
        w = max(self.text.width + BOX_PAD_X, BOX_MIN_W)
        h = self.text.height + BOX_PAD_Y
        if node["type"] == "example":
            w, h = round(w * ELLIPSE_SCALE), round(h * ELLIPSE_SCALE)
        self.w, self.h = w, h
        self.x = self.y = 0.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def reach(self, dx: float, dy: float) -> float:
        """How far the outline lies from the centre along the unit direction (dx, dy)."""
        a, b = self.w / 2, self.h / 2
        if self.node["type"] == "example":
            return 1 / math.hypot(dx / a, dy / b)
        return min(a / abs(dx) if dx else math.inf, b / abs(dy) if dy else math.inf)


def _place_row(boxes: list[_Box], top: float) -> float:
    """Centre every box on the row's middle; returns the row's bottom."""
    height = max(box.h for box in boxes)
    for box in boxes:
        box.y = top + (height - box.h) / 2
    return top + height


def _place_across(boxes: list[_Box], left: float) -> None:
    for box in boxes:
        box.x = left
        left = box.x + box.w + SIDE_GAP


def _view_of(m: dict, view_id: str | None) -> tuple[list[dict], list[dict]]:
    """The view's nodes and edges, in map.json order; the whole map when ``view_id`` is None."""
    nodes, edges = m["nodes"], m["edges"]
    if view_id is None:
        return nodes, edges
    view = next((v for v in m.get("views") or [] if v["id"] == view_id), None)
    if view is None:
        raise UnknownView(f"unknown view: {view_id}")
    keep = set(view["nodes"])
    return ([n for n in nodes if n["id"] in keep],
            [e for e in edges if e["from"] in keep and e["to"] in keep])


def _layout(nodes: list[dict], edges: list[dict]) -> list[_Box]:
    """Every node's box, placed; returned in layout order (main rows, then loose rows)."""
    boxes = {node["id"]: _Box(node, n) for n, node in enumerate(nodes)}
    main = sorted((b for b in boxes.values() if "order" in b.node), key=lambda b: b.node["order"])

    # Breadth-first from every main node at once: each node gets the first main node that reaches it.
    anchor: dict[str, tuple[str, int]] = {b.node["id"]: (b.node["id"], 0) for b in main}
    queue = [b.node["id"] for b in main]
    for current in queue:
        root, distance = anchor[current]
        for edge in edges:
            if edge["from"] == current:
                other = edge["to"]
            elif edge["to"] == current:
                other = edge["from"]
            else:
                continue
            if other not in anchor:
                anchor[other] = (root, distance + 1)
                queue.append(other)

    ordered: list[_Box] = []
    bottom = None
    if main:
        column = max(b.w for b in main)
        top = 0.0
        for head in main:
            head.x = (column - head.w) / 2
            side = sorted(
                (b for b in boxes.values()
                 if b is not head and anchor.get(b.node["id"], (None,))[0] == head.node["id"]),
                key=lambda b: (anchor[b.node["id"]][1], b.position),
            )
            _place_across(side, column + SIDE_GAP)
            row = [head, *side]
            bottom = _place_row(row, top)
            ordered += row
            top = bottom + ROW_GAP

    loose = [b for b in boxes.values() if b.node["id"] not in anchor]
    top = 0.0 if bottom is None else bottom + ROW_GAP
    for start in range(0, len(loose), LOOSE_PER_ROW):
        row = loose[start:start + LOOSE_PER_ROW]
        _place_across(row, 0.0)
        top = _place_row(row, top) + ROW_GAP
        ordered += row
    return ordered


# ---- elements -----------------------------------------------------------------------


def _num(value: float):
    """A coordinate for the file: two decimals, and an int when it is whole."""
    value = round(value, 2) + 0.0  # + 0.0 turns -0.0 into 0.0
    return int(value) if value.is_integer() else value


def _base(element_id: str, kind: str, x, y, w, h, ink: str, style=("", 2, "solid", None), fill="transparent"):
    _, stroke_width, stroke_style, roundness = style
    return {
        "id": element_id,
        "type": kind,
        "x": _num(x), "y": _num(y), "width": _num(w), "height": _num(h),
        "angle": 0,
        "strokeColor": ink,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": stroke_width,
        "strokeStyle": stroke_style,
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": roundness,
        "seed": 0,
        "version": 1,
        "versionNonce": 0,
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
    }


def _text_element(element_id: str, text: _Text, x, y, ink: str, container: str | None,
                  align: str = "center", valign: str = "middle") -> dict:
    element = _base(element_id, "text", x, y, text.width, text.height, ink)
    element.update({
        "boundElements": None,
        "text": "\n".join(text.lines),
        "originalText": text.original,
        "fontSize": text.size,
        "fontFamily": 2,
        "lineHeight": LINE_HEIGHT,
        "textAlign": align,
        "verticalAlign": valign,
        "containerId": container,
    })
    return element


def _arrow_points(src: _Box, dst: _Box, lane: float | None) -> list[tuple[float, float]]:
    if lane is not None:
        return [(src.x - GAP, src.cy), (lane, src.cy), (lane, dst.cy), (dst.x - GAP, dst.cy)]
    dx, dy = dst.cx - src.cx, dst.cy - src.cy
    length = math.hypot(dx, dy)
    dx, dy = dx / length, dy / length
    start = src.reach(dx, dy) + GAP
    end = dst.reach(dx, dy) + GAP
    return [(src.cx + dx * start, src.cy + dy * start), (dst.cx - dx * end, dst.cy - dy * end)]


def build_scene(m: dict, view_id: str | None = None, language: str = "en") -> dict:
    """The Excalidraw scene of the map, or of one view; ``language`` "zh" names the legend in Chinese.

    Expects a map that passes ``validate_map``. Raises UnknownView for an unknown ``view_id``.
    """
    palette = load_palette()
    ink, highlight = palette["ink"], palette["highlight"]
    nodes, edges = _view_of(m, view_id)
    boxes = _layout(nodes, edges)

    elements: list[dict] = []
    shape_of: dict[str, dict] = {}
    box_of: dict[str, _Box] = {}
    for k, box in enumerate(boxes, 1):
        shape_id = f"node-{k}"
        style = STYLES[box.node["type"]]
        fill = highlight if box.node.get("key") is True else "transparent"
        shape = _base(shape_id, style[0], box.x, box.y, box.w, box.h, ink, style, fill)
        shape["boundElements"] = [{"type": "text", "id": f"{shape_id}-text"}]
        shape["customData"] = {"node": box.node["id"]}
        text = _text_element(f"{shape_id}-text", box.text, box.cx - box.text.width / 2,
                             box.cy - box.text.height / 2, ink, shape_id)
        elements += [shape, text]
        shape_of[box.node["id"]] = shape
        box_of[box.node["id"]] = box

    main_rank = {b.node["id"]: n for n, b in enumerate(
        sorted((b for b in boxes if "order" in b.node), key=lambda b: b.node["order"]), 1)}
    leftmost = min((b.x for b in boxes), default=0.0)
    skips = 0
    drawn = [e for e in edges if e["from"] != e["to"]]
    for j, edge in enumerate(drawn, 1):
        arrow_id = f"edge-{j}"
        src, dst = box_of[edge["from"]], box_of[edge["to"]]
        lane = None
        if edge["from"] in main_rank and edge["to"] in main_rank \
                and abs(main_rank[edge["from"]] - main_rank[edge["to"]]) >= 2:
            lane = LANE_X - LANE_STEP * skips
            skips += 1
        points = _arrow_points(src, dst, lane)
        leftmost = min([leftmost, *(p[0] for p in points)])
        x0, y0 = points[0]
        xs = [p[0] - x0 for p in points]
        ys = [p[1] - y0 for p in points]
        arrow = _base(arrow_id, "arrow", x0, y0, max(xs) - min(xs), max(ys) - min(ys), ink,
                      ("arrow", 2, "solid", None))
        arrow.update({
            "boundElements": [{"type": "text", "id": f"{arrow_id}-text"}],
            "points": [[_num(x), _num(y)] for x, y in zip(xs, ys)],
            "lastCommittedPoint": None,
            "startBinding": {"elementId": shape_of[edge["from"]]["id"], "focus": 0, "gap": GAP},
            "endBinding": {"elementId": shape_of[edge["to"]]["id"], "focus": 0, "gap": GAP},
            "startArrowhead": None,
            "endArrowhead": "arrow",
            "customData": {"from": edge["from"], "to": edge["to"]},
        })
        middle = (len(points) - 1) // 2
        (ax, ay), (bx, by) = points[middle], points[middle + 1]
        verb = _Text(edge["verb"], VERB_SIZE, VERB_LIMIT)
        label = _text_element(f"{arrow_id}-text", verb, (ax + bx) / 2 - verb.width / 2,
                              (ay + by) / 2 - verb.height / 2, ink, arrow_id)
        elements += [arrow, label]
        for end in ("from", "to"):  # two shapes: an edge from a node to itself is not drawn
            shape_of[edge[end]]["boundElements"].append({"type": "arrow", "id": arrow_id})

    names = LEGEND_NAMES["zh" if language == "zh" else "en"]
    items = [(STYLES[kind], "transparent", names[kind]) for kind in NODE_TYPES]
    if any(b.node.get("key") is True for b in boxes):
        items.append((KEY_STYLE, highlight, names["key"]))
    top = max((b.y + b.h for b in boxes), default=0.0) + ROW_GAP
    x = leftmost
    for i, (style, fill, name) in enumerate(items, 1):
        item_id = f"legend-{i}"
        elements.append(_base(item_id, style[0], x, top, LEGEND_W, LEGEND_H, ink, style, fill))
        text = _Text(name, LEGEND_SIZE, None)
        text_x = x + LEGEND_W + LEGEND_TEXT_DX
        elements.append(_text_element(f"{item_id}-text", text, text_x, top + LEGEND_TEXT_DY, ink, None,
                                      "left", "top"))
        x = text_x + text.width + LEGEND_ITEM_GAP

    for seed, element in enumerate(elements, 1):
        element["seed"] = seed
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "tutor-any-lecture",
        "elements": elements,
        "appState": {"viewBackgroundColor": palette["paper"], "gridSize": None},
        "files": {},
    }


# ---- files ------------------------------------------------------------------------


def scene_json(scene: dict) -> str:
    return json.dumps(scene, ensure_ascii=False, indent=2) + "\n"


def obsidian_md(scene: dict) -> str:
    """The scene in the Obsidian Excalidraw plugin's ``.excalidraw.md`` form."""
    lines = ["---", "", "excalidraw-plugin: parsed", "tags: [excalidraw]", "", "---", OBSIDIAN_WARNING, "", "",
             "# Excalidraw Data", "", "## Text Elements"]
    for element in scene["elements"]:
        if element["type"] == "text":
            lines += [f"{element['originalText']} ^{element['id']}", ""]
    lines += ["%%", "## Drawing", "```json", json.dumps(scene, ensure_ascii=False, indent=2), "```", "%%", ""]
    return "\n".join(lines)


def legend_language(unit: Path) -> str:
    """"zh" when the unit's plan.json has note_language zh, else "en"; a missing plan.json means "en".

    A malformed plan.json raises what ``load_plan`` raises.
    """
    path = UnitPaths(unit).plan
    if not path.exists():
        return "en"
    return "zh" if load_plan(path).note_language == "zh" else "en"


def render_map(unit: Path, view_id: str | None = None, obsidian: bool = False,
               force: bool = False) -> Path | list[Path]:
    """Write the map as editable Excalidraw drawings; nothing is written if any step fails.

    With ``view_id``, or for a map without views: ``map.excalidraw`` (that view, or the
    whole map), and its path is returned. A map with views: ``map-<view id>.excalidraw``
    per view, in view order, and the list of their paths. ``obsidian`` writes
    ``.excalidraw.md`` files in their place. The map is checked as ``load_checked_map``
    checks it; an existing target raises FileExistsError unless ``force``.
    """
    m = load_checked_map(unit)
    root = UnitPaths(unit).root
    suffix = ".excalidraw.md" if obsidian else ".excalidraw"
    views = m.get("views") or []
    if view_id is not None or not views:
        _view_of(m, view_id)  # an unknown view ends here, before anything is written
        targets = [(view_id, root / f"map{suffix}")]
    else:
        targets = []
        for view in views:
            view_file(unit, view["id"])  # an id that cannot name a file: the same one-line ValueError
            targets.append((view["id"], root / f"map-{view['id']}{suffix}"))
    language = legend_language(unit)
    if not force:
        for _, target in targets:
            if target.exists():
                raise FileExistsError(f"{target} already exists; rerun with --force to replace it")
    scenes = [(target, build_scene(m, vid, language)) for vid, target in targets]
    for target, scene in scenes:
        text = obsidian_md(scene) if obsidian else scene_json(scene)
        target.write_text(text, encoding="utf-8", newline="\n")
    paths = [target for target, _ in scenes]
    return paths if view_id is None and views else paths[0]
