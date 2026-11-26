import json
import re
import string
import xml.etree.ElementTree as ET
from datetime import date
from importlib import resources
from pathlib import Path
from types import SimpleNamespace

from tutor_any_lecture.cli import main
from tutor_any_lecture.palette import load_palette
from tutor_any_lecture.progress import Attempt, log_attempt, page_language, render_progress
from tutor_any_lecture.unit import find_unit

# ---- local helpers ---------------------------------------------------------

VARIANT = {"pre": "A", "post": "B", "d7": "C"}
DAY = {"pre": "2026-11-20", "post": "2026-11-20", "d7": "2026-11-27"}


def attempt(**over):
    """One valid Attempt; keyword arguments override fields."""
    base = dict(
        ts="2026-11-20T10:00:00+00:00", course="C", unit="u1", item_id="c1-B",
        variant="B", concept="c1", phase="post", score=1, confidence=2,
        citation="(01:00)", exposure="unknown",
    )
    base.update(over)
    return Attempt(**base)


def mk(unit, pre=(), post=(), d7=()):
    """Tracked attempts for one unit: the i-th score of a phase belongs to concept c<i>."""
    out = []
    for phase, scores in (("pre", pre), ("post", post), ("d7", d7)):
        for i, s in enumerate(scores, start=1):
            out.append(
                attempt(
                    ts=f"{DAY[phase]}T10:00:00+00:00", unit=unit,
                    item_id=f"c{i}-{VARIANT[phase]}", variant=VARIANT[phase],
                    concept=f"c{i}", phase=phase, score=s,
                )
            )
    return out


def write_attempts(ws, attempts=None):
    """Log attempts into workspace `ws`; default: unit u1 with pre 0.2 / post 0.9 / d7 0.7."""
    if attempts is None:
        attempts = mk(unit="u1", pre=[0, 0, 1, 0, 0], post=[1, 1, 1, 0.5, 1], d7=[1, 0.5, 1, 0.5, 0.5])
    for a in attempts:
        log_attempt(a, ws)


def write_plan(folder, course, unit, concepts, note_language="en"):
    """A valid plan.json in `folder` for `course` and `unit`; `concepts` is [(id, name), ...]."""
    folder.mkdir(parents=True, exist_ok=True)
    plan = {
        "course": course, "unit": unit, "goal": "deep", "content_type": "concept",
        "note_language": note_language, "lecture_language": note_language, "duration_s": 180,
        "outputs": ["explanation", "pretest", "quiz", "cards", "map"], "sections": [],
        "concepts": [{"id": cid, "name": name, "type": "definition", "citations": ["(slide 1)"]}
                     for cid, name in concepts],
        "tracked": [cid for cid, _ in concepts][:5], "output_target": "markdown",
    }
    (folder / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    return folder


def plan_ns(note_language, concepts=()):
    """A stand-in plan: only note_language and concepts are read."""
    return SimpleNamespace(note_language=note_language,
                           concepts=[{"id": cid, "name": name} for cid, name in concepts])


def render_lines(ws, today, **kw):
    return render_progress("C", ws, today, **kw).read_text(encoding="utf-8").splitlines()


def tables():
    text = resources.files("tutor_any_lecture").joinpath("data", "progress_strings.json").read_text(encoding="utf-8")
    return json.loads(text)


def fields(template):
    return {name for _, name, _, _ in string.Formatter().parse(template) if name is not None}


# ---- L1 --------------------------------------------------------------------


def test_tables_have_the_same_keys_and_placeholders():
    t = tables()
    assert set(t) == {"en", "zh"}
    assert set(t["en"]) == set(t["zh"])
    for key in t["en"]:
        assert fields(t["en"][key]) == fields(t["zh"][key]), key


def test_chinese_strings_hold_no_english():
    for key, value in tables()["zh"].items():
        bare = re.sub(r"\{[^{}]*\}", "", value)
        assert not re.search(r"[A-Za-z]", bare), key


# ---- L2 --------------------------------------------------------------------


def test_lang_flag_wins_and_is_normalised():
    att = [attempt()]
    plans = {"u1": plan_ns("zh")}
    assert page_language("zh", att, plans) == ("zh", None)
    assert page_language("ZH-cn", att, plans) == ("zh", None)
    assert page_language("en_GB", att, plans) == ("en", None)


def test_unknown_language_falls_back_once():
    att = [attempt()]
    assert page_language("ja", att, {}) == ("en", "no progress page text for language 'ja'; the page is in English")
    assert page_language(None, att, {"u1": plan_ns("ko")}) == (
        "en", "no progress page text for language 'ko'; the page is in English"
    )


def test_newest_unit_sets_the_language():
    plans = {"u-old": plan_ns("en"), "u-new": plan_ns("zh")}
    att = [attempt(unit="u-old"), attempt(unit="u-new")]
    assert page_language(None, att, plans) == ("zh", None)
    att.append(attempt(unit="u-old"))
    assert page_language(None, att, plans) == ("zh", None)
    assert page_language(None, att, {}) == ("en", None)


# ---- L3 --------------------------------------------------------------------


def chinese_workspace(tmp_path):
    ws = tmp_path / "ws"
    write_plan(ws / "courses" / "课程" / "第1周", "课程", "第1周",
               [("c1", "现值公式"), ("c2", "复利频率")], note_language="zh")
    base = dict(course="课程", unit="第1周", exposure="unknown", confidence=2)
    day1, day7 = "2026-11-20T10:00:00+00:00", "2026-11-27T10:00:00+00:00"
    for a in (
        Attempt(ts=day1, item_id="现值-前", variant="A", concept="c1", phase="pre", score=0,
                citation="（第2页，01:00）", prompt="现值怎么算？", **base),
        Attempt(ts=day1, item_id="复利-前", variant="A", concept="c2", phase="pre", score=0,
                citation="（第3页，02:00）", prompt="复利多久计一次？", **base),
        Attempt(ts=day1, item_id="现值-后", variant="B", concept="c1", phase="post", score=1,
                citation="（第2页，01:00）", prompt="一年后的一百元今天值多少？", **base),
        Attempt(ts=day1, item_id="复利-后", variant="B", concept="c2", phase="post", score=0,
                citation="（第3页，02:00）", prompt="按月计息的实际年利率是多少？", answer="百分之六",
                **{**base, "confidence": 3}),
        Attempt(ts=day7, item_id="现值-复", variant="C", concept="c1", phase="d7", score=1,
                citation="（第2页，01:00）", prompt="贴现率升高时现值怎样变？", assigned=["c1", "c2"], **base),
    ):
        log_attempt(a, ws)
    return ws


def test_chinese_page_has_no_english(tmp_path):
    ws = chinese_workspace(tmp_path)
    page_path = render_progress("课程", ws, date(2026, 11, 28))
    page = page_path.read_text(encoding="utf-8")
    lines = page.splitlines()
    assert lines[0] == "# 学习进度 — 课程"
    assert "已答 1/2" in page
    partial_note = tables()["zh"]["partial_note"]
    assert partial_note in lines
    assert any(line.startswith("- 第1周") and line.endswith("，已答 1/2") for line in lines)
    shown = [line for line in lines if not line.startswith("![")]
    assert [line for line in shown if re.search(r"[A-Za-z]", line)] == []
    root = svg_root(page_path.with_suffix(".svg"))
    words = [el.text or "" for el in root.iter() if el.tag in (f"{SVG}text", f"{SVG}title")]
    words += [child.tail or "" for el in root.iter() for child in el if el.tag == f"{SVG}text"]
    assert len(words) > 10
    assert [w for w in words if re.search(r"[A-Za-z]", w)] == []


# ---- N1 --------------------------------------------------------------------


def test_plan_is_found_under_another_folder_name(tmp_path):
    ws = tmp_path / "ws"
    write_plan(ws / "courses" / "C" / "U1", "C", "Other", [("c1", "One")])
    broken = ws / "courses" / "C" / "a broken"
    broken.mkdir(parents=True)
    (broken / "plan.json").write_text("{", encoding="utf-8", newline="\n")
    write_plan(ws / "courses" / "C" / "week 1", "C", "U1", [("c1", "One")])
    found = find_unit(ws, "C", "U1")
    assert found is not None
    folder, plan = found
    assert folder == ws / "courses" / "C" / "week 1"
    assert plan.unit == "U1"
    assert find_unit(ws, "C", "U9") is None


# ---- N2 --------------------------------------------------------------------


def concept_names_workspace(tmp_path):
    ws = tmp_path / "ws"
    write_plan(ws / "courses" / "C" / "week 1", "C", "U1", [("c2", "Second idea"), ("c1", "Concept one")])
    write_attempts(ws, [
        attempt(unit="U1", item_id="c1-A", variant="A", concept="c1", phase="pre", score=0),
        attempt(unit="U1", item_id="c9-A", variant="A", concept="c9", phase="pre", score=1),
        attempt(unit="U1", item_id="c2-A", variant="A", concept="c2", phase="pre", score=0),
        attempt(unit="U1", item_id="c1-B", variant="B", concept="c1", phase="post", score=0, confidence=3,
                citation="(slide 2, 01:00)"),
        attempt(unit="U1", item_id="c2-B", variant="B", concept="c2", phase="post", score=1),
    ])
    return ws


def test_rows_show_concept_names(tmp_path):
    ws = concept_names_workspace(tmp_path)
    lines = render_lines(ws, date(2026, 11, 20))
    rows = [x for x in lines[lines.index("### U1"):lines.index("## Due today")] if x.startswith("| ")]
    assert [x for x in rows if not x.startswith("| concept |")] == [
        "| Second idea | 0 | 100 | — |",
        "| Concept one | 0 | 0 | — |",
        "| c9 | 100 | — | — |",
    ]
    assert "- U1: c1-B (Concept one), post quiz, (slide 2, 01:00)" in lines
    rows = chart_rows(tmp_path / "ws" / "progress" / "C.svg")
    after = rows[rows.index(("section", "U1")) + 1:]
    assert [r[1] for r in after] == ["Second idea", "Concept one", "c9"]


def test_concept_name_with_a_pipe_is_escaped_in_the_table(tmp_path):
    ws = tmp_path / "ws"
    write_plan(ws / "courses" / "C" / "u1", "C", "u1", [("c1", "a|b")])
    write_attempts(ws, mk(unit="u1", pre=[0], post=[1]))
    assert "| a\\|b | 0 | 100 | — |" in render_lines(ws, date(2026, 11, 20))


# ---- H1 --------------------------------------------------------------------


def test_negative_gain_is_a_whole_percent(tmp_path):
    write_attempts(tmp_path / "a", mk(unit="u1", pre=[0.5, 0.5], post=[0, 0.5]))
    assert "| u1 | 50 → 25 | -50% | 25 → — | — |" in render_lines(tmp_path / "a", date(2026, 11, 20))
    write_attempts(tmp_path / "b", mk(unit="u1", pre=[0.5] + [0] * 100, post=[0] * 101))
    lines = render_lines(tmp_path / "b", date(2026, 11, 20))
    assert "| u1 | 0 → 0 | 0% | 0 → — | — |" in lines
    assert "-0%" not in "\n".join(lines)


# ---- H2 --------------------------------------------------------------------


def test_sentence_counts_units(tmp_path):
    write_attempts(tmp_path, mk(unit="u1", pre=[0, 1]) + mk(unit="u2", pre=[0.5]))
    assert render_lines(tmp_path, date(2026, 11, 20))[2] == "Across 2 units: your pretest average is 50."


def test_sentence_skips_an_undefined_gain(tmp_path):
    write_attempts(tmp_path / "a", mk(unit="u1", pre=[1], post=[1]))
    first = render_lines(tmp_path / "a", date(2026, 11, 20))[2]
    assert first == "Across 1 unit: your pretest average is 100; your post quiz average is 100."
    write_attempts(tmp_path / "b", mk(unit="u1", post=[0], d7=[0]))
    second = render_lines(tmp_path / "b", date(2026, 11, 27))[2]
    assert second == "Across 1 unit: your post quiz average is 0; your day-7 review average is 0."
    assert "—" not in first and "—" not in second


def test_chinese_sentence(tmp_path):
    write_attempts(tmp_path)
    lines = render_lines(tmp_path, date(2026, 11, 27), lang="zh")
    assert lines[2] == "共 1 节课：读讲解前平均 20 分，读完后 90 分，标准化增益 88%；一周后保持了课后分数的 78%。"


# ---- Y1 --------------------------------------------------------------------


def test_image_line_survives_spaces(tmp_path):
    write_attempts(tmp_path, [attempt(course="CS 101 - Intro")])
    page = render_progress("CS 101 - Intro", tmp_path, date(2026, 11, 20))
    (image,) = [x for x in page.read_text(encoding="utf-8").splitlines() if x.startswith("![")]
    assert image.endswith("](<CS 101 - Intro.svg>)")
    assert (page.parent / "CS 101 - Intro.svg").is_file()


def test_notices_collect_the_fallback(tmp_path):
    write_attempts(tmp_path)
    notices = []
    lines = render_lines(tmp_path, date(2026, 11, 27), lang="ja", notices=notices)
    assert lines[0] == "# Progress — C"
    assert notices == ["no progress page text for language 'ja'; the page is in English"]


# ---- G1, G2: the chart -------------------------------------------------------

SVG = "{http://www.w3.org/2000/svg}"
FORBIDDEN = ("<script", "<style", "@font-face", "url(", "href")


def svg_root(path):
    return ET.parse(path).getroot()


def own_text(el):
    """The text of `el` itself, without the text of a <title> child."""
    return (el.text or "") + "".join(child.tail or "" for child in el)


def mark_x(el):
    if el.tag == f"{SVG}circle":
        return float(el.get("cx"))
    return float(el.get("points").split()[0].split(",")[0])


def chart_rows(path):
    """The chart's rows, top to bottom: ("section", label) or ("row", label, {phase: [x, ...]})."""
    out = []
    for el in svg_root(path):
        if el.tag == f"{SVG}text" and el.get("class") == "section":
            out.append(("section", own_text(el)))
        elif el.tag == f"{SVG}g" and el.get("class") == "row":
            (label,) = el.findall(f"{SVG}text")
            marks = {}
            for mark in el:
                if mark.get("class") in ("pre", "post", "d7"):
                    marks.setdefault(mark.get("class"), []).append(mark_x(mark))
            out.append(("row", own_text(label), marks))
    return out


def row_titles(path):
    """The <title> of each data row and section row that has one, by its shown label."""
    out = {}
    for el in svg_root(path):
        if el.get("class") in ("row", "section"):
            title = el.find(f"{SVG}title")
            if title is not None:
                label = el if el.get("class") == "section" else el.find(f"{SVG}text")
                out[own_text(label)] = title.text
    return out


def colours(path):
    return [v for el in svg_root(path).iter() for k, v in el.attrib.items() if k in ("fill", "stroke")]


def test_svg_is_well_formed_and_self_contained(tmp_path):
    write_attempts(tmp_path)
    page = render_progress("C", tmp_path, date(2026, 11, 27))
    chart = page.with_suffix(".svg")
    root = svg_root(chart)
    assert root.tag == f"{SVG}svg"
    assert (root.get("width"), root.get("height"), root.get("viewBox")) == ("720", "304", "0 0 720 304")
    assert root.get("role") == "img"
    first, second = list(root)[:2]
    assert first.tag == f"{SVG}title" and first.text == "Progress — C"
    assert second.tag == f"{SVG}rect" and second.get("fill") == load_palette()["paper"]
    text = chart.read_text(encoding="utf-8")
    assert [s for s in FORBIDDEN if s in text] == []
    assert [k for el in root.iter() for k in el.attrib if k.lower().startswith("on")] == []
    assert "\r" not in chart.read_bytes().decode("utf-8")


def test_svg_takes_its_colours_from_the_palette(tmp_path, monkeypatch):
    write_attempts(tmp_path)
    chart = render_progress("C", tmp_path, date(2026, 11, 27)).with_suffix(".svg")
    allowed = set(load_palette().values()) | {"none"}
    assert colours(chart) and set(colours(chart)) <= allowed
    other = {role: f"#0{n}0{n}0{n}" for n, role in enumerate(load_palette(), start=1)}
    monkeypatch.setattr("tutor_any_lecture.palette.load_palette", lambda path=None: dict(other))
    render_progress("C", tmp_path, date(2026, 11, 27))
    assert set(colours(chart)) <= set(other.values()) | {"none"}
    assert {other["paper"], other["progress_pre"], other["progress_post"], other["progress_d7"]} <= set(colours(chart))
    assert "#121212" not in chart.read_text(encoding="utf-8")


def test_svg_written_without_attempts(tmp_path):
    write_attempts(tmp_path, [attempt(item_id="p1", variant=None, phase="practice", score=1)])
    chart = render_progress("C", tmp_path, date(2026, 11, 20)).with_suffix(".svg")
    root = svg_root(chart)
    assert root.get("height") == "80"
    assert root.find(f"{SVG}g[@class='row']") is None
    assert root.find(f"{SVG}text[@class='section']") is None


def test_svg_rows_follow_the_tables(tmp_path):
    write_attempts(tmp_path / "a")
    rows = chart_rows(render_progress("C", tmp_path / "a", date(2026, 11, 27)).with_suffix(".svg"))
    assert [r[:2] for r in rows] == [
        ("section", "Units"), ("row", "u1"), ("section", "u1"),
        ("row", "c1"), ("row", "c2"), ("row", "c3"), ("row", "c4"), ("row", "c5"),
    ]
    assert rows[1][2] == {"pre": [348], "post": [656], "d7": [568]}
    # gain pairs c2 only, retention c3 only; the chart's unit row shows unit_scores means 50, 75, 50
    write_attempts(tmp_path / "b", [
        attempt(item_id="c1-A", variant="A", concept="c1", phase="pre", score=1),
        attempt(item_id="c2-A", variant="A", concept="c2", phase="pre", score=0),
        attempt(item_id="c2-B", variant="B", concept="c2", phase="post", score=0.5),
        attempt(item_id="c3-B", variant="B", concept="c3", phase="post", score=1),
        attempt(ts="2026-11-27T10:00:00+00:00", item_id="c3-C", variant="C", concept="c3", phase="d7", score=0.5),
    ])
    rows = chart_rows(render_progress("C", tmp_path / "b", date(2026, 11, 27)).with_suffix(".svg"))
    assert rows[1] == ("row", "u1", {"pre": [474], "post": [590], "d7": [486]})


def test_rows_y_and_marks_follow_the_layout(tmp_path):
    write_attempts(tmp_path, mk(unit="u1", pre=[0.5]))
    root = svg_root(render_progress("C", tmp_path, date(2026, 11, 20)).with_suffix(".svg"))
    section = root.find(f"{SVG}text[@class='section']")
    assert (section.get("x"), section.get("y"), section.get("font-weight")) == ("16", "83", "bold")
    rows = root.findall(f"{SVG}g[@class='row']")
    label = rows[0].find(f"{SVG}text")
    assert (label.get("x"), label.get("y")) == ("28", "111")
    pre = rows[0].find(f"{SVG}circle[@class='pre']")
    assert (pre.get("cx"), pre.get("cy"), pre.get("r"), pre.get("stroke-width")) == ("480", "106", "6", "2")
    palette = load_palette()
    assert (pre.get("fill"), pre.get("stroke")) == (palette["paper"], palette["progress_pre"])
    root2 = svg_root(render_progress_d7(tmp_path / "d7"))
    d7 = root2.find(f"{SVG}g[@class='row']/{SVG}polygon[@class='d7']")
    assert d7.get("points") == "480,100 486,106 480,112 474,106"
    assert d7.get("fill") == palette["progress_d7"]
    post = root2.find(f"{SVG}g[@class='row']/{SVG}circle[@class='post']")
    assert (post.get("r"), post.get("fill")) == ("5", palette["progress_post"])


def render_progress_d7(ws):
    write_attempts(ws, mk(unit="u1", post=[1], d7=[0.5]))
    return render_progress("C", ws, date(2026, 11, 27)).with_suffix(".svg")


def test_long_and_cjk_labels_are_cut(tmp_path):
    ws = tmp_path / "ws"
    latin = "A very long concept name that runs past it ok"
    cjk = "一二三四五六七八九十一二三四五六七八九十"
    unit = "A unit name far longer than thirty columns"
    assert (len(latin), len(cjk)) == (45, 20)
    write_plan(ws / "courses" / "C" / "u", "C", unit, [("c1", latin), ("c2", cjk), ("c3", "R&D <基础>")])
    write_attempts(ws, [attempt(unit=unit, item_id=f"{c}-A", variant="A", concept=c, phase="pre", score=0)
                        for c in ("c1", "c2", "c3")])
    chart = render_progress("C", ws, date(2026, 11, 20)).with_suffix(".svg")
    labels = [r[1] for r in chart_rows(chart)]
    assert labels == ["Units", unit[:29] + "…", unit[:29] + "…", latin[:29] + "…", cjk[:14] + "…", "R&D <基础>"]
    titles = row_titles(chart)
    assert titles[latin[:29] + "…"] == latin
    assert titles[cjk[:14] + "…"] == cjk
    assert titles[unit[:29] + "…"] == unit
    assert "R&D <基础>" not in titles


# ---- C1, D1: the command and the documents --------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "tutor-any-lecture"


def test_cli_render_in_chinese(tmp_path, capsys):
    write_attempts(tmp_path)
    assert main(["progress", "render", "--course", "C", "--lang", "zh", "--workspace", str(tmp_path)]) == 0
    page = tmp_path / "progress" / "C.md"
    assert page.read_text(encoding="utf-8").splitlines()[0] == "# 学习进度 — C"
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"paths": [str(page), str(page.with_suffix(".svg"))], "lang": "zh"}
    assert captured.err == ""


def test_cli_unknown_language_says_so_once(tmp_path, capsys):
    write_attempts(tmp_path)
    assert main(["progress", "render", "--course", "C", "--lang", "ja", "--workspace", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert captured.err == "no progress page text for language 'ja'; the page is in English\n"
    assert json.loads(captured.out)["lang"] == "en"
    assert (tmp_path / "progress" / "C.md").read_text(encoding="utf-8").splitlines()[0] == "# Progress — C"


def test_cli_render_follows_the_newest_unit(tmp_path, capsys):
    ws = chinese_workspace(tmp_path)
    assert main(["progress", "render", "--course", "课程", "--workspace", str(ws), "--date", "2026-11-28"]) == 0
    assert json.loads(capsys.readouterr().out)["lang"] == "zh"


def test_documents_name_the_language_flag_and_the_chart():
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    teaching = (SKILL_DIR / "references" / "teaching.md").read_text(encoding="utf-8")
    markdown = (SKILL_DIR / "references" / "output-targets" / "markdown.md").read_text(encoding="utf-8")
    gate = (SKILL_DIR / "references" / "gate.md").read_text(encoding="utf-8")
    assert "--lang" in skill and "--lang" in teaching
    assert "<course>.svg" in teaching and "<course>.svg" in markdown
    (writes,) = [line for line in gate.splitlines() if line.startswith("**Commands that write a file**")]
    assert "`progress render`" in writes.split("{\"paths\": […]}", 1)[1]
