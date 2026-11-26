"""The progress chart: the page's scores as dots on one 0 to 100 scale, in one SVG file.

The chart holds no script, no style sheet, no font file and no link: its colours come from
``palette.load_palette()`` at render time, its words from the page's tables, its font from
the system. A filled background makes it read the same in light and dark viewers.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from . import palette

WIDTH = 720
TOP = 64  # y where the first row begins
ROW_HEIGHT = 28
BOTTOM = 16  # space under the last row
SCALE_X0 = 260  # x of score 0
SCALE_STEP = 4.4  # pixels per point, so 100 sits at x 700
TICKS = (0, 25, 50, 75, 100)
SIDE_BY_SIDE = 12  # distance between marks of equal scores in one row
LABEL_COLUMNS = 30  # a wider label is cut to 29 columns and "…"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif"
PHASES = ("pre", "post", "d7")  # mark order: in the legend, and side by side in a row


@dataclass
class ChartRow:
    """One row of the chart: a section label (``scores`` None) or a labelled row of marks."""

    label: str
    scores: dict[str, int] | None = None  # 0 to 100 by phase; a missing phase draws no mark


def _num(x: float) -> str:
    """``x`` to one decimal, without a trailing ``.0``."""
    text = f"{round(x, 1):.1f}"
    return text[:-2] if text.endswith(".0") else text


def _x(score: float) -> float:
    return SCALE_X0 + SCALE_STEP * score


def _clean(value: str) -> str:
    """``value`` on one line, without the control characters XML cannot hold."""
    return "".join(c for c in " ".join(value.split()) if c >= " ")


def _text(value: str) -> str:
    """``value`` as XML character data."""
    return escape(_clean(value))


def _columns(char: str) -> int:
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def _cut(label: str) -> str | None:
    """The label cut to its longest prefix of at most 29 columns plus "…", or None when it fits in 30."""
    if sum(map(_columns, label)) <= LABEL_COLUMNS:
        return None
    kept, used = [], 0
    for char in label:
        used += _columns(char)
        if used > LABEL_COLUMNS - 1:
            break
        kept.append(char)
    return "".join(kept) + "…"


def _mark(phase: str, x: float, y: int, colours: dict[str, str]) -> str:
    if phase == "pre":
        return (f'<circle class="pre" cx="{_num(x)}" cy="{y}" r="6" fill="{colours["paper"]}" '
                f'stroke="{colours["progress_pre"]}" stroke-width="2"/>')
    if phase == "post":
        return f'<circle class="post" cx="{_num(x)}" cy="{y}" r="5" fill="{colours["progress_post"]}"/>'
    points = f"{_num(x)},{y - 6} {_num(x + 6)},{y} {_num(x)},{y + 6} {_num(x - 6)},{y}"
    return f'<polygon class="d7" points="{points}" fill="{colours["progress_d7"]}"/>'


def _marks(scores: dict[str, int], y: int, colours: dict[str, str]) -> list[str]:
    """The row's marks; marks of equal scores stand side by side, centred on the score."""
    shown = [p for p in PHASES if scores.get(p) is not None]
    out = []
    for phase in shown:
        same = [p for p in shown if scores[p] == scores[phase]]
        offset = (same.index(phase) - (len(same) - 1) / 2) * SIDE_BY_SIDE
        out.append(_mark(phase, _x(scores[phase]) + offset, y, colours))
    return out


def _label(label: str, x: int, y: int, ink: str, attributes: str = "") -> tuple[str, str, str]:
    """A row label's parts: the <title> that holds a cut label whole (else ""), the <text>
    opening tag, and the text shown."""
    label = _clean(label)
    cut = _cut(label)
    title = f"<title>{escape(label)}</title>" if cut is not None else ""
    return title, f'<text{attributes} x="{x}" y="{y}" fill="{ink}">', escape(cut if cut is not None else label)


def chart_svg(title: str, legend: list[str], rows: list[ChartRow]) -> str:
    """The chart as SVG text. ``legend`` labels pre, post and d7, in that order."""
    colours = palette.load_palette()
    ink = colours["ink"]
    height = TOP + ROW_HEIGHT * len(rows) + BOTTOM
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" font-family="{FONT}" font-size="13">',
        f"<title>{_text(title)}</title>",
        f'<rect x="0" y="0" width="{WIDTH}" height="{height}" fill="{colours["paper"]}"/>',
        '<g class="legend">',
    ]
    for i, (phase, text) in enumerate(zip(PHASES, legend)):
        out.append(_mark(phase, 22 + 150 * i, 24, colours))
        out.append(f'<text x="{34 + 150 * i}" y="29" fill="{ink}">{_text(text)}</text>')
    out += ["</g>", '<g class="axis">']
    for v in TICKS:
        x = _num(_x(v))
        out.append(f'<text x="{x}" y="52" text-anchor="middle" fill="{ink}">{v}</text>')
        out.append(f'<line x1="{x}" y1="{TOP}" x2="{x}" y2="{height - BOTTOM}" stroke="{ink}" stroke-opacity="0.15"/>')
    out.append("</g>")
    for k, row in enumerate(rows):
        y = TOP + ROW_HEIGHT * k + ROW_HEIGHT // 2
        if row.scores is None:
            title_el, opening, shown = _label(row.label, 16, y + 5, ink, ' class="section" font-weight="bold"')
            out.append(f"{opening}{title_el}{shown}</text>")
        else:
            title_el, opening, shown = _label(row.label, 28, y + 5, ink)
            out.append(f'<g class="row">{title_el}{opening}{shown}</text>')
            out += _marks(row.scores, y, colours)
            out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def write_chart(path: Path, title: str, legend: list[str], rows: list[ChartRow]) -> Path:
    """Write the chart to ``path`` as UTF-8 with ``\\n`` line ends and return ``path``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(chart_svg(title, legend, rows), encoding="utf-8", newline="\n")
    return path
