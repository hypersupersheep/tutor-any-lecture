import json
import re
import string
from datetime import date
from importlib import resources
from types import SimpleNamespace

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


def test_notices_collect_the_fallback(tmp_path):
    write_attempts(tmp_path)
    notices = []
    lines = render_lines(tmp_path, date(2026, 11, 27), lang="ja", notices=notices)
    assert lines[0] == "# Progress — C"
    assert notices == ["no progress page text for language 'ja'; the page is in English"]
