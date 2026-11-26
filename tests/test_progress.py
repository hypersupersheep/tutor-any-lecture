import dataclasses
import json
from datetime import date, datetime

import pytest

from tutor_any_lecture.cli import main
from tutor_any_lecture.plan import PlanError
from tutor_any_lecture.profile import set_value
from tutor_any_lecture.progress import (
    Attempt,
    confident_but_wrong,
    due,
    load_attempts,
    log_attempt,
    normalized_gain,
    paired_scores,
    render_progress,
    retention,
    unit_scores,
)

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


def mk_post(unit, day):
    """Five post attempts, all on `day`."""
    return [
        attempt(ts=f"{day.isoformat()}T10:00:00+00:00", unit=unit, item_id=f"c{i}-B", concept=f"c{i}")
        for i in range(1, 6)
    ]


def write_attempts(ws, attempts=None):
    """Log attempts into workspace `ws`; default: unit u1 with pre 0.2 / post 0.9 / d7 0.7."""
    if attempts is None:
        attempts = mk(unit="u1", pre=[0, 0, 1, 0, 0], post=[1, 1, 1, 0.5, 1], d7=[1, 0.5, 1, 0.5, 0.5])
    for a in attempts:
        log_attempt(a, ws)


def unit_dir(tmp_path):
    """A unit folder whose name differs from plan.unit, with plan.json and items.json.

    Course "C", unit "U1"; one tracked concept "c1" with variants A, B, C (ids "c1-A",
    "c1-B", "c1-C"); one practice item "p1" (variant None); every item has citation
    "(slide 2, 01:00)". The layout is the one load_plan and load_items read. assignment.json
    gives c1 pre A, post B, d7 C.
    """
    u = tmp_path / "课程 资料" / "第1周"
    u.mkdir(parents=True)
    plan = {
        "course": "C", "unit": "U1", "goal": "deep", "content_type": "concept",
        "note_language": "en", "lecture_language": "en", "duration_s": 180,
        "outputs": ["explanation", "pretest", "quiz", "cards", "map"], "sections": [],
        "concepts": [{"id": "c1", "name": "Concept one", "type": "definition", "citations": ["(slide 2, 01:00)"]}],
        "tracked": ["c1"], "output_target": "markdown",
    }

    def item(id, variant, kind):
        return {
            "id": id, "concept": "c1", "kind": kind, "prompt": f"Prompt {id}?", "answer": "A.",
            "rubric": "R.", "citation": "(slide 2, 01:00)", "difficulty": 2, "variant": variant,
        }

    items = {
        "tracked": {"c1": {v: item(f"c1-{v}", v, "apply") for v in "ABC"}},
        "practice": [item("p1", None, "recall")],
    }
    assignment = {"seed": "C|U1", "concepts": {"c1": {"pre": "A", "post": "B", "d7": "C"}}}
    for name, obj in (("plan.json", plan), ("items.json", items), ("assignment.json", assignment)):
        write_json(u / name, obj)
    return u


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def add_variant(u, letter, concept="c1", kind="apply"):
    """Add variant `letter` (id "<concept>-<letter>") to a tracked concept of the unit's items.json."""
    path = u / "items.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    items["tracked"][concept][letter] = {
        "id": f"{concept}-{letter}", "concept": concept, "kind": kind, "prompt": f"Prompt {concept}-{letter}?",
        "answer": "A.", "rubric": "R.", "citation": "(slide 2, 01:00)", "difficulty": 2, "variant": letter,
    }
    write_json(path, items)


# ---- scores ----------------------------------------------------------------


def test_gain_and_retention():
    att = mk(unit="u1", pre=[0, 0, 1, 0, 0], post=[1, 1, 1, 0.5, 1], d7=[1, 0.5, 1, 0.5, 0.5])
    s = unit_scores(att)
    assert s["u1"] == {"pre": 0.2, "post": 0.9, "d7": 0.7}
    assert normalized_gain(s) == pytest.approx(0.875)
    assert retention(s) == pytest.approx(0.7 / 0.9)


def test_pre_perfect_excluded():
    assert normalized_gain({"u": {"pre": 1.0, "post": 1.0}}) is None


def test_practice_excluded_and_confident_but_wrong():
    p = attempt(item_id="p1", variant=None, phase="practice", score=0, confidence=3)
    att = mk(unit="u1", pre=[0, 1]) + [p]
    assert unit_scores(att) == {"u1": {"pre": 0.5}}
    assert confident_but_wrong(att) == [p]


# ---- due list --------------------------------------------------------------


def test_due_dates():
    att = mk_post(unit="u1", day=date(2026, 11, 20))
    assert [(x["phase"], x["optional"]) for x in due(att, date(2026, 11, 21))] == [("d1", True)]
    assert [(x["phase"], x["optional"]) for x in due(att, date(2026, 11, 27))] == [("d7", False)]


def test_due_entry_keys_and_order():
    att = mk_post(unit="u1", day=date(2026, 11, 20))
    att.append(attempt(ts="2026-11-21T09:00:00+00:00", item_id="c1-D", variant="D", phase="d1"))
    assert due(att, date(2026, 12, 11)) == [
        {"unit": "u1", "phase": "d7", "due": "2026-11-27", "optional": False, "answered": 0, "remaining": None},
        {"unit": "u1", "phase": "d21", "due": "2026-12-11", "optional": True, "answered": 0, "remaining": None},
    ]
    assert due(att, date(2026, 11, 26)) == []


def test_due_uses_date_as_written_in_ts():
    att = [attempt(ts="2026-11-20T23:30:00-08:00")]
    assert [x["due"] for x in due(att, date(2026, 11, 21))] == ["2026-11-21"]


# ---- log -------------------------------------------------------------------


def test_log_rejects_bad_score(tmp_path):
    with pytest.raises(ValueError):
        log_attempt(attempt(score=0.7), tmp_path)
    assert not (tmp_path / "progress" / "C.jsonl").exists()


def test_log_round_trip_null_variant(tmp_path):
    a = attempt(item_id="p1", variant=None, phase="practice", score=0, confidence=3, citation="(第2页, 01:00)")
    p = log_attempt(a, tmp_path)
    assert p == tmp_path / "progress" / "C.jsonl"
    raw = p.read_text(encoding="utf-8")
    assert '"variant": null' in raw and "第2页" in raw and raw.endswith("\n")
    assert load_attempts("C", tmp_path) == [a]
    assert load_attempts("Other", tmp_path) == []


def test_log_round_trip_unicode_line_separators(tmp_path):
    # json.dumps(ensure_ascii=False) writes U+2028, U+2029 and U+0085 raw; they must not split a record.
    a = attempt(citation="a b c\x85d", concept="x y")
    log_attempt(a, tmp_path)
    log_attempt(attempt(), tmp_path)
    assert load_attempts("C", tmp_path) == [a, attempt()]


# ---- page ------------------------------------------------------------------


def test_render_headline(tmp_path):
    write_attempts(tmp_path)
    p = render_progress("C", tmp_path, date(2026, 11, 27))
    assert p.read_text(encoding="utf-8").splitlines()[2].startswith(
        "Across 1 units: pre 0.20 → post 0.90, normalized gain 0.88"
    )


def test_render_page_content(tmp_path):
    write_attempts(tmp_path)
    log_attempt(attempt(item_id="p1", variant=None, phase="practice", score=0, confidence=3), tmp_path)
    p = render_progress("C", tmp_path, date(2026, 11, 27))
    assert p == tmp_path / "progress" / "C.md"
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[:2] == ["# Progress — C", ""]
    assert lines[2] == (
        "Across 1 units: pre 0.20 → post 0.90, normalized gain 0.88; post 0.90 → day 7 0.70, retention 0.78."
    )
    assert "| unit | pre → post | gain | post → day 7 | retention |" in lines
    assert "| u1 | 0.20 → 0.90 | 0.88 | 0.90 → 0.70 | 0.78 |" in lines
    assert "····○·········◆···●··  u1" in lines
    by_concept = lines[lines.index("## By concept"):lines.index("## Due today")]
    assert [x for x in by_concept if x.startswith(("○", "●", "◆", "·"))] == [
        "○···················●◆  c1",
        "○·········◆·········●  c2",
        "····················○●◆  c3",
        "○·········●◆··········  c4",
        "○·········◆·········●  c5",
    ]
    assert lines[lines.index("## Due today") + 2] == "None."
    assert lines[lines.index("## Confident but wrong") + 2] == "- u1: p1 (c1), practice, (01:00)"


def test_headline_omits_missing_parts(tmp_path):
    write_attempts(tmp_path, mk(unit="u1", pre=[0, 0, 1, 0, 0], post=[1, 1, 1, 0.5, 1]))
    lines = render_progress("C", tmp_path, date(2026, 11, 20)).read_text(encoding="utf-8").splitlines()
    assert lines[2] == "Across 1 units: pre 0.20 → post 0.90, normalized gain 0.88."
    assert "| u1 | 0.20 → 0.90 | 0.88 | 0.90 → — | — |" in lines
    assert lines[lines.index("## Due today") + 2] == "None."


def test_render_without_attempts(tmp_path):
    # A log with only a practice attempt: no tracked attempts yet.
    write_attempts(tmp_path, [attempt(item_id="p1", variant=None, phase="practice", score=1)])
    lines = render_progress("C", tmp_path, date(2026, 11, 20)).read_text(encoding="utf-8").splitlines()
    assert lines[:3] == ["# Progress — C", "", "No tracked attempts yet."]
    assert "## Units" not in lines and "## By concept" not in lines
    assert lines[lines.index("## Confident but wrong") + 2] == "None."


# ---- CLI -------------------------------------------------------------------


def test_cli_log_records_plan_names(tmp_path, capsys):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    code = main([
        "progress", "log", "--unit", str(u), "--item", "c1-B", "--phase", "post",
        "--score", "0.5", "--confidence", "2", "--exposure", "watched", "--workspace", str(ws),
    ])
    assert code == 0
    (a,) = load_attempts("C", ws)
    assert (a.course, a.unit) == ("C", "U1") and u.name != a.unit
    assert (a.item_id, a.variant, a.concept, a.citation) == ("c1-B", "B", "c1", "(slide 2, 01:00)")
    assert (a.phase, a.score, a.confidence, a.exposure) == ("post", 0.5, 2, "watched")
    assert datetime.fromisoformat(a.ts).utcoffset() is not None
    assert json.loads(capsys.readouterr().out)["unit"] == "U1"


def test_cli_log_practice_item_has_null_variant(tmp_path):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    code = main([
        "progress", "log", "--unit", str(u), "--item", "p1", "--phase", "practice",
        "--score", "0", "--confidence", "3", "--workspace", str(ws),
    ])
    assert code == 0
    (a,) = load_attempts("C", ws)
    assert a.variant is None and a.exposure == "unknown" and a.score == 0


def test_cli_log_unknown_item_exits_2(tmp_path, capsys):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    code = main([
        "progress", "log", "--unit", str(u), "--item", "nope", "--phase", "post",
        "--score", "1", "--confidence", "2", "--workspace", str(ws),
    ])
    assert code == 2
    assert "nope" in capsys.readouterr().err
    assert load_attempts("C", ws) == []


def test_cli_progress_log_takes_a_date(tmp_path, capsys):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    argv = ["progress", "log", "--unit", str(u), "--item", "c1-C", "--phase", "d7",
            "--score", "1", "--confidence", "3", "--workspace", str(ws)]
    assert main([*argv, "--date", "2026-11-27"]) == 0
    (a,) = load_attempts("C", ws)
    stamp = datetime.fromisoformat(a.ts)
    assert stamp.date() == date(2026, 11, 27) and stamp.utcoffset() is not None
    assert json.loads(capsys.readouterr().out)["ts"] == a.ts
    # without --date the attempt is stamped today
    assert main(argv) == 0
    assert datetime.fromisoformat(load_attempts("C", ws)[1].ts).date() == date.today()
    for bad in ("2026-13-01", "27/11/2026", "20261127", "tomorrow"):
        with pytest.raises(SystemExit) as e:
            main([*argv, "--date", bad])
        assert e.value.code == 2
    assert len(load_attempts("C", ws)) == 2


def test_cli_progress_due_rejects_a_bad_date(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["progress", "due", "--course", "C", "--date", "2026-02-30", "--workspace", str(tmp_path)])
    assert e.value.code == 2


def test_cli_log_takes_no_course(tmp_path):
    u = unit_dir(tmp_path)
    with pytest.raises(SystemExit) as e:
        main([
            "progress", "log", "--course", "C", "--unit", str(u), "--item", "c1-B",
            "--phase", "post", "--score", "1", "--confidence", "2", "--workspace", str(tmp_path / "ws"),
        ])
    assert e.value.code == 2


def test_cli_due_prints_json(tmp_path, capsys):
    write_attempts(tmp_path, mk_post(unit="u1", day=date(2026, 11, 20)))
    code = main(["progress", "due", "--course", "C", "--date", "2026-11-27", "--workspace", str(tmp_path)])
    assert code == 0
    assert json.loads(capsys.readouterr().out) == [
        {"unit": "u1", "phase": "d7", "due": "2026-11-27", "optional": False, "answered": 0, "remaining": None},
    ]


def test_cli_workspace_defaults_to_profile(tmp_cfg, tmp_path, capsys):
    ws = tmp_path / "my ws"
    set_value("workspace", str(ws))
    write_attempts(ws, mk_post(unit="u1", day=date(2026, 11, 20)))
    assert main(["progress", "due", "--course", "C", "--date", "2026-11-27"]) == 0
    assert [x["phase"] for x in json.loads(capsys.readouterr().out)] == ["d7"]


def test_cli_render_writes_page(tmp_path, capsys):
    write_attempts(tmp_path)
    assert main(["progress", "render", "--course", "C", "--workspace", str(tmp_path)]) == 0
    page = tmp_path / "progress" / "C.md"
    assert page.read_text(encoding="utf-8").splitlines()[0] == "# Progress — C"
    assert json.loads(capsys.readouterr().out) == {"path": str(page)}


# ---- unsafe names and malformed files (Task 21) -----------------------------


def test_progress_refuses_unsafe_course(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(PlanError):
        log_attempt(attempt(course="../x"), ws)
    with pytest.raises(PlanError):
        render_progress("../x", ws, date(2026, 11, 20))
    with pytest.raises(PlanError):
        load_attempts("../x", ws)
    outside = [p for p in tmp_path.rglob("*") if p != ws and ws / "progress" not in (p, *p.parents)]
    assert outside == []


def test_cli_progress_log_malformed_items_is_one_line(tmp_path, capsys):
    u = unit_dir(tmp_path)
    (u / "items.json").write_text("{", encoding="utf-8", newline="\n")
    ws = tmp_path / "ws"
    code = main([
        "progress", "log", "--unit", str(u), "--item", "c1-B", "--phase", "post",
        "--score", "1", "--confidence", "2", "--workspace", str(ws),
    ])
    assert code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.endswith("\n") and captured.err.count("\n") == 1
    assert captured.err.startswith("items.json:")
    assert not ws.exists()


@pytest.mark.parametrize("field, value", [("score", True), ("confidence", True), ("confidence", 2.0)])
def test_log_rejects_bool_and_float_values(tmp_path, field, value):
    with pytest.raises(ValueError):
        log_attempt(attempt(**{field: value}), tmp_path)
    assert not (tmp_path / "progress" / "C.jsonl").exists()



# ---- rules that had no test (Task 21) ---------------------------------------


@pytest.mark.parametrize("field, value", [("phase", "d3"), ("confidence", 4), ("exposure", "seen")])
def test_log_rejects_bad_phase_confidence_exposure(tmp_path, field, value):
    with pytest.raises(ValueError):
        log_attempt(attempt(**{field: value}), tmp_path)
    assert not (tmp_path / "progress" / "C.jsonl").exists()


def test_table_escapes_pipe_in_unit_name(tmp_path):
    write_attempts(tmp_path, mk(unit="a|b", pre=[0], post=[1]))
    lines = render_progress("C", tmp_path, date(2026, 11, 20)).read_text(encoding="utf-8").splitlines()
    assert "| a\\|b | 0.00 → 1.00 | 1.00 | 1.00 → — | — |" in lines


def test_cli_bare_progress_is_usage():
    with pytest.raises(SystemExit) as e:
        main(["progress"])
    assert e.value.code == 2


RENDERED_PAGE = """# Progress — C

Across 1 units: pre 0.00 → post 1.00, normalized gain 1.00.

## Units

| unit | pre → post | gain | post → day 7 | retention |
|---|---|---|---|---|
| u1 | 0.00 → 1.00 | 1.00 | 1.00 → — | — |

Gain and retention compare only the concepts attempted in both phases, and the means beside them are over those concepts.

Each strip runs from 0 to 100 in 21 columns: ○ pre, ● post, ◆ day 7; marks of equal scores stand side by side.

```text
○···················●  u1
```

## By concept

### u1

```text
○···················●  c1
```

## Due today

- u1: d1 (optional), due 2026-11-21

## Confident but wrong

- u1: p1 (c1), practice, (0:30)
"""


def test_rendered_page_layout(tmp_path):
    write_attempts(tmp_path, [
        attempt(item_id="c1-A", variant="A", phase="pre", score=0),
        attempt(item_id="c1-B", variant="B", phase="post", score=1, confidence=3),
        attempt(item_id="p1", variant=None, phase="practice", score=0, confidence=3, citation="(0:30)"),
    ])
    page = render_progress("C", tmp_path, date(2026, 11, 21))
    assert page.read_text(encoding="utf-8") == RENDERED_PAGE


# ---- paired gain and retention, what is due (Task 23) ------------------------


def test_gain_pairs_concepts(tmp_path):
    att = [
        attempt(item_id="c1-A", variant="A", concept="c1", phase="pre", score=1),
        attempt(item_id="c2-A", variant="A", concept="c2", phase="pre", score=0),
        attempt(item_id="c2-B", variant="B", concept="c2", phase="post", score=0.5),
    ]
    assert paired_scores(att, "pre", "post") == {"u1": {"pre": 0.0, "post": 0.5}}
    assert normalized_gain(paired_scores(att, "pre", "post")) == pytest.approx(0.5)
    write_attempts(tmp_path, att)
    lines = render_progress("C", tmp_path, date(2026, 11, 20)).read_text(encoding="utf-8").splitlines()
    assert lines[2] == "Across 1 units: pre 0.00 → post 0.50, normalized gain 0.50."
    assert "| u1 | 0.00 → 0.50 | 0.50 | 0.50 → — | — |" in lines


def test_retention_pairs_concepts(tmp_path):
    att = mk(unit="u1", post=[1, 0.5], d7=[0.5])
    assert paired_scores(att, "post", "d7") == {"u1": {"post": 1.0, "d7": 0.5}}
    assert retention(paired_scores(att, "post", "d7")) == pytest.approx(0.5)
    write_attempts(tmp_path, att)
    lines = render_progress("C", tmp_path, date(2026, 11, 27)).read_text(encoding="utf-8").splitlines()
    assert lines[2] == "Across 1 units: post 1.00 → day 7 0.50, retention 0.50."
    assert "| u1 | — → 0.75 | — | 1.00 → 0.50 | 0.50 |" in lines
    # no concept with both phases: the value is missing
    lonely = mk(unit="u2", post=[1]) + [attempt(unit="u2", item_id="c2-C", variant="C", concept="c2", phase="d7")]
    assert paired_scores(lonely, "post", "d7") == {}
    assert retention(paired_scores(lonely, "post", "d7")) is None


def test_due_lists_post_after_pretest():
    att = mk(unit="u1", pre=[0, 1]) + [attempt(ts="2026-11-22T10:00:00+00:00", unit="u1", item_id="c3-A",
                                               variant="A", concept="c3", phase="pre", score=0)]
    att += mk_post(unit="u2", day=date(2026, 11, 20))
    assert due(att, date(2026, 11, 20)) == [
        {"unit": "u1", "phase": "post", "due": "2026-11-20", "optional": False, "answered": 0, "remaining": None},
    ]
    assert due(att, date(2026, 11, 19)) == []


def test_optional_d1_expires_at_d7():
    att = mk_post(unit="u1", day=date(2026, 11, 20))
    assert [x["phase"] for x in due(att, date(2026, 11, 26))] == ["d1"]
    assert due(att, date(2026, 11, 27)) == [
        {"unit": "u1", "phase": "d7", "due": "2026-11-27", "optional": False, "answered": 0, "remaining": None},
    ]
    early_d7 = att + [attempt(ts="2026-11-25T10:00:00+00:00", item_id="c1-C", variant="C", phase="d7")]
    assert due(early_d7, date(2026, 11, 25)) == []


def test_render_refuses_unknown_course(tmp_path):
    write_attempts(tmp_path)
    with pytest.raises(FileNotFoundError) as e:
        render_progress("Nope", tmp_path, date(2026, 11, 20))
    assert str(e.value) == "no progress log for course 'Nope'"
    assert not (tmp_path / "progress" / "Nope.md").exists()
    with pytest.raises(FileNotFoundError) as e:
        render_progress("Bob's notes", tmp_path, date(2026, 11, 20))
    assert str(e.value) == "no progress log for course 'Bob's notes'"


def test_page_means_agree_with_the_gain(tmp_path):
    # Gain pairs c2 only (pre 0, post 0.5); retention pairs c3 only (post 1, d7 0.5).
    write_attempts(tmp_path, [
        attempt(item_id="c1-A", variant="A", concept="c1", phase="pre", score=1),
        attempt(item_id="c2-A", variant="A", concept="c2", phase="pre", score=0),
        attempt(item_id="c2-B", variant="B", concept="c2", phase="post", score=0.5),
        attempt(item_id="c3-B", variant="B", concept="c3", phase="post", score=1),
        attempt(ts="2026-11-27T10:00:00+00:00", item_id="c3-C", variant="C", concept="c3", phase="d7", score=0.5),
    ])
    page = render_progress("C", tmp_path, date(2026, 11, 27)).read_text(encoding="utf-8")
    lines = page.splitlines()
    assert lines[2] == (
        "Across 1 units: pre 0.00 → post 0.50, normalized gain 0.50; post 1.00 → day 7 0.50, retention 0.50."
    )
    assert "| u1 | 0.00 → 0.50 | 0.50 | 1.00 → 0.50 | 0.50 |" in lines
    assert "pre 0.50 → post 0.50" not in page
    # the per-concept lines keep every attempt
    by_concept = lines[lines.index("## By concept"):lines.index("## Due today")]
    assert [x for x in by_concept if x.startswith(("○", "●", "◆", "·"))] == [
        "····················○  c1",
        "○·········●··········  c2",
        "··········◆·········●  c3",
    ]


# ---- the progress page after a live run (Task 29, L13) -------------------------


def test_equal_scores_show_both_marks(tmp_path):
    write_attempts(tmp_path, mk(unit="u1", pre=[1, 0, 0.5], post=[1, 0, 1], d7=[1, 0.5, 1]))
    lines = render_progress("C", tmp_path, date(2026, 11, 27)).read_text(encoding="utf-8").splitlines()
    by_concept = lines[lines.index("## By concept"):lines.index("## Due today")]
    strips = [x for x in by_concept if x.startswith(("○", "●", "◆", "·"))]
    assert strips == [
        "····················○●◆  c1",
        "○●·········◆··········  c2",
        "··········○·········●◆  c3",
    ]
    assert all(mark in line for line in strips for mark in "○●◆")


def test_confident_wrong_shows_the_prompt(tmp_path):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    items_path = u / "items.json"
    items = json.loads(items_path.read_text(encoding="utf-8"))
    prompt = "A loan charges half a percent a month;\n  what is its effective yearly rate, and why is it above six percent?"
    items["tracked"]["c1"]["B"]["prompt"] = prompt
    items_path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert main(["progress", "log", "--unit", str(u), "--item", "c1-B", "--phase", "post", "--score", "0",
                 "--confidence", "3", "--workspace", str(ws)]) == 0
    (a,) = load_attempts("C", ws)
    assert a.prompt == prompt
    # an attempt logged before prompts were kept still renders, without one
    log_attempt(attempt(item_id="p1", variant=None, phase="practice", score=0, confidence=3, unit="U1"), ws)
    lines = render_progress("C", ws, date(2026, 11, 20)).read_text(encoding="utf-8").splitlines()
    start = lines.index("## Confident but wrong") + 2
    assert lines[start:start + 2] == [
        '- U1: c1-B (c1) "A loan charges half a percent a month; what is its effective…", post, (slide 2, 01:00)',
        "- U1: p1 (c1), practice, (01:00)",
    ]


# ---- old logs and malformed lines (M2a Task 5) ------------------------------

REQUIRED = dict(
    ts="2026-11-20T10:00:00+00:00", course="C", unit="u1", item_id="c1-B", variant="B",
    concept="c1", phase="post", score=1, confidence=2, citation="(01:00)", exposure="unknown",
)


def write_raw(path, lines):
    """Write `lines` (strings) to `path`, one per line, creating its folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8", newline="\n")


def test_old_log_lines_load(tmp_path):
    write_raw(tmp_path / "progress" / "C.jsonl", [
        json.dumps(REQUIRED),
        json.dumps({**REQUIRED, "prompt": "Q?"}),
        json.dumps({**REQUIRED, "future": 1}),
    ])
    first, second, third = load_attempts("C", tmp_path)
    assert (first.prompt, first.answer, first.assigned) == (None, None, None)
    assert second.prompt == "Q?"
    assert third == first


def malformed_lines(**fields):
    """Eight log lines: 1 and 8 valid, 2 to 7 malformed or blank, as the warning tests expect."""
    valid = {**REQUIRED, **fields}
    no_score = {k: v for k, v in valid.items() if k != "score"}
    return [
        json.dumps(valid),
        "{bad",
        "[1, 2]",
        json.dumps(no_score),
        json.dumps({**valid, "score": 0.7}),
        "",
        json.dumps({**valid, "ts": "yesterday"}),
        json.dumps({**valid, "ts": "2026-11-21T10:00:00+00:00"}),
    ]


def warnings_for(path):
    return "".join(
        f"warning: {path}: line {n} skipped: {reason}\n"
        for n, reason in (
            (2, "not valid JSON"),
            (3, "not a JSON object"),
            (4, "missing score"),
            (5, "bad value for score: 0.7"),
            (7, "bad value for ts: 'yesterday'"),
        )
    )


def test_malformed_lines_are_skipped_with_a_warning(tmp_path, capsys):
    path = tmp_path / "progress" / "C.jsonl"
    write_raw(path, malformed_lines())
    att = load_attempts("C", tmp_path)
    assert att == [Attempt(**REQUIRED), Attempt(**{**REQUIRED, "ts": "2026-11-21T10:00:00+00:00"})]
    captured = capsys.readouterr()
    assert captured.err == warnings_for(str(path))
    assert captured.out == ""


@pytest.mark.parametrize("field, value, shown", [
    ("ts", 5, "5"),
    ("course", None, "None"),
    ("variant", "F", "'F'"),
    ("phase", "d3", "'d3'"),
    ("score", True, "True"),
    ("confidence", 2.0, "2.0"),
    ("exposure", "seen", "'seen'"),
    ("prompt", 3, "3"),
    ("answer", ["x"], "['x']"),
    ("assigned", ["c1", 2], "['c1', 2]"),
    ("assigned", "c1", "'c1'"),
])
def test_each_bad_value_is_named(tmp_path, capsys, field, value, shown):
    path = tmp_path / "progress" / "C.jsonl"
    write_raw(path, [json.dumps({**REQUIRED, field: value})])
    assert load_attempts("C", tmp_path) == []
    assert capsys.readouterr().err == f"warning: {path}: line 1 skipped: bad value for {field}: {shown}\n"


def test_missing_keys_are_named_in_field_order(tmp_path, capsys):
    path = tmp_path / "progress" / "C.jsonl"
    write_raw(path, [json.dumps({k: v for k, v in REQUIRED.items() if k not in ("unit", "exposure")})])
    assert load_attempts("C", tmp_path) == []
    assert capsys.readouterr().err == f"warning: {path}: line 1 skipped: missing unit, exposure\n"


def test_cli_commands_survive_a_malformed_line(tmp_path, capsys):
    import shutil

    from conftest import fx

    u = tmp_path / "unit"
    shutil.copytree(fx("units", "ok"), u)
    ws = tmp_path / "ws"
    path = ws / "progress" / "demo-course.jsonl"
    write_raw(path, malformed_lines(course="demo-course", unit="unit-01", item_id="ci-B", concept="compound-interest"))
    expected = warnings_for(str(path))
    for argv in (
        ["progress", "due", "--course", "demo-course", "--workspace", str(ws)],
        ["progress", "render", "--course", "demo-course", "--workspace", str(ws)],
        ["cards", "add-misses", "--unit", str(u), "--workspace", str(ws)],
    ):
        assert main(argv) == 0, argv
        captured = capsys.readouterr()
        assert captured.out.count("\n") == 1 and isinstance(json.loads(captured.out), (list, dict))
        assert captured.err == expected


# ---- progress log: its own phase, assigned concepts, the answer (M2a Task 5) ---


def log_argv(u, ws, item, phase, *extra):
    return ["progress", "log", "--unit", str(u), "--item", item, "--phase", phase,
            "--score", "1", "--confidence", "2", "--workspace", str(ws), *extra]


@pytest.mark.parametrize("item, phase, message", [
    ("p1", "post", "item p1 belongs to phase practice, not post"),
    ("c1-A", "post", "item c1-A belongs to phase pre, not post"),
    ("c1-B", "practice", "item c1-B belongs to phase post, not practice"),
    ("c1-D", "d7", "item c1-D belongs to phase d1, not d7"),
])
def test_cli_log_refuses_an_item_outside_its_phase(tmp_path, capsys, item, phase, message):
    u = unit_dir(tmp_path)
    add_variant(u, "D")
    ws = tmp_path / "ws"
    assert main(log_argv(u, ws, item, phase)) == 1
    captured = capsys.readouterr()
    assert captured.err == message + "\n"
    assert captured.out == ""
    assert not (ws / "progress" / "C.jsonl").exists()


def test_cli_log_needs_the_assignment_for_a_tracked_item(tmp_path, capsys):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    (u / "assignment.json").unlink()
    assert main(log_argv(u, ws, "c1-B", "post")) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith(str(u / "assignment.json") + " not found")
    assert captured.out == "" and not (ws / "progress" / "C.jsonl").exists()
    assert main(log_argv(u, ws, "p1", "practice")) == 0
    capsys.readouterr()
    write_json(u / "assignment.json", {"seed": "C|U1", "concepts": {}})
    assert main(log_argv(u, ws, "c1-B", "post")) == 1
    assert capsys.readouterr().err == "item c1-B has no phase in assignment.json\n"
    # an assignment lacking a phase fails as `items assign` fails on it
    write_json(u / "assignment.json", {"seed": "C|U1", "concepts": {"c1": {"pre": "A", "post": "B"}}})
    assert main(log_argv(u, ws, "c1-B", "post")) == 1
    assert capsys.readouterr().err == 'assignment.json: concept c1 has no "d7"\n'
    assert len(load_attempts("C", ws)) == 1


def test_cli_log_records_the_assigned_concepts(tmp_path):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    assert main(log_argv(u, ws, "c1-A", "pre")) == 0
    add_variant(u, "D")
    assert main(log_argv(u, ws, "c1-D", "d1")) == 0
    assert main(log_argv(u, ws, "p1", "practice")) == 0
    assert [a.assigned for a in load_attempts("C", ws)] == [["c1"], ["c1"], None]


def test_cli_log_keeps_the_answer(tmp_path):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    assert main(log_argv(u, ws, "c1-B", "post", "--answer", "  six percent ")) == 0
    assert main(log_argv(u, ws, "c1-B", "post", "--answer", "  ")) == 0
    assert main(log_argv(u, ws, "c1-B", "post")) == 0
    assert [a.answer for a in load_attempts("C", ws)] == ["six percent", None, None]


def test_cli_log_prints_the_log_path(tmp_path, capsys):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    assert main(log_argv(u, ws, "c1-B", "post", "--answer", "x")) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["path"] == str(ws / "progress" / "C.jsonl")
    assert (ws / "progress" / "C.jsonl").exists()
    (a,) = load_attempts("C", ws)
    assert printed == {**dataclasses.asdict(a), "path": printed["path"]}
    # every new line carries all fourteen keys, in field order
    line = (ws / "progress" / "C.jsonl").read_text(encoding="utf-8").split("\n")[0]
    assert list(json.loads(line)) == [f.name for f in dataclasses.fields(Attempt)]
    assert len(dataclasses.fields(Attempt)) == 14


# ---- a phase is done when every assigned concept has an attempt (M2a Task 5) ---

FIVE = ["c1", "c2", "c3", "c4", "c5"]


def at(day, phase, concept, score=1, **over):
    """One attempt at `concept` in `phase` on `day` (YYYY-MM-DD), assigned the five concepts."""
    letter = {"pre": "A", "post": "B", "d7": "C", "d1": "D", "d21": "E"}[phase]
    return attempt(ts=f"{day}T10:00:00+00:00", item_id=f"{concept}-{letter}", variant=letter,
                   concept=concept, phase=phase, score=score, **{"assigned": FIVE, **over})


def test_post_must_be_complete_before_reviews():
    att = [at("2026-11-01", "pre", c, 0) for c in FIVE] + [at("2026-11-01", "post", c) for c in FIVE[:2]]
    assert [x["phase"] for x in due(att, date(2026, 11, 2))] == ["post"]
    att += [at("2026-11-03", "post", c) for c in FIVE[2:]]
    assert [(x["phase"], x["due"]) for x in due(att, date(2026, 11, 4))] == [("d1", "2026-11-04")]


def test_partial_post_without_pretest_is_offered():
    att = [at("2026-11-01", "post", c) for c in FIVE[:2]]
    assert due(att, date(2026, 11, 2)) == [
        {"unit": "u1", "phase": "post", "due": "2026-11-01", "optional": False, "answered": 2,
         "remaining": ["c3", "c4", "c5"]},
    ]


def test_optional_d21_lapses_after_two_weeks():
    att = mk_post(unit="u1", day=date(2026, 11, 20))
    assert [x["phase"] for x in due(att, date(2026, 12, 24))] == ["d7", "d21"]
    assert [x["phase"] for x in due(att, date(2026, 12, 25))] == ["d7"]
    att.append(at("2026-12-11", "d21", "c1", assigned=["c1", "c2"]))
    (d21,) = [x for x in due(att, date(2026, 12, 24)) if x["phase"] == "d21"]
    assert (d21["answered"], d21["remaining"]) == (1, ["c2"])
    assert [x["phase"] for x in due(att, date(2026, 12, 25))] == ["d7"]


def test_unit_score_averages_concepts():
    att = [
        attempt(concept="c1", score=0),
        attempt(concept="c1", score=1),
        attempt(item_id="c2-B", concept="c2", score=1),
    ]
    assert unit_scores(att) == {"u1": {"post": 0.75}}


def test_partial_phase_is_left_out_of_the_means():
    three = ["c1", "c2", "c3"]
    att = [at("2026-11-20", "post", c, assigned=three) for c in three]
    att.append(at("2026-11-27", "d7", "c1", 0.5, assigned=three))
    assert "d7" not in unit_scores(att)["u1"]
    assert unit_scores(att)["u1"] == {"post": 1.0}
    assert paired_scores(att, "post", "d7") == {}


def test_only_partial_phases_give_no_headline(tmp_path):
    write_attempts(tmp_path, [at("2026-11-20", "pre", c, 0) for c in FIVE[:2]])
    lines = render_progress("C", tmp_path, date(2026, 11, 20)).read_text(encoding="utf-8").splitlines()
    assert lines[2] == "No complete phase yet."
    assert "| u1 | 2 of 5 → — | — | — → — | — |" in lines
    assert PARTIAL_NOTE in lines


PARTIAL_NOTE = (
    'A phase shown as "k of n" is partial: k of its n tracked concepts have an attempt so far, '
    "and it stays out of every mean, gain and retention until the rest are answered."
)


def five_concept_unit(tmp_path):
    """Course "C", unit "U5": c1 to c5 tracked, variants A, B, C each, assigned pre A, post B, d7 C."""
    u = tmp_path / "unit five"
    u.mkdir()
    concepts = [{"id": c, "name": f"Concept {c}", "type": "definition", "citations": ["(slide 1)"]} for c in FIVE]
    plan = {
        "course": "C", "unit": "U5", "goal": "deep", "content_type": "concept",
        "note_language": "en", "lecture_language": "en", "duration_s": 180,
        "outputs": ["explanation", "pretest", "quiz", "cards", "map"], "sections": [],
        "concepts": concepts, "tracked": FIVE, "output_target": "markdown",
    }
    tracked = {
        c: {
            v: {"id": f"{c}-{v}", "concept": c, "kind": "apply", "prompt": f"Prompt {c}-{v}?", "answer": "A.",
                "rubric": "R.", "citation": "(slide 1)", "difficulty": 2, "variant": v}
            for v in "ABC"
        }
        for c in FIVE
    }
    assignment = {"seed": "C|U5", "concepts": {c: {"pre": "A", "post": "B", "d7": "C"} for c in FIVE}}
    write_json(u / "plan.json", plan)
    write_json(u / "items.json", {"tracked": tracked, "practice": []})
    write_json(u / "assignment.json", assignment)
    return u


def log_scores(u, ws, phase, scores, day, concepts=FIVE):
    letter = {"pre": "A", "post": "B", "d7": "C"}[phase]
    for c, score in zip(concepts, scores):
        assert main(["progress", "log", "--unit", str(u), "--item", f"{c}-{letter}", "--phase", phase,
                     "--score", str(score), "--confidence", "2", "--date", day, "--workspace", str(ws)]) == 0


def test_interrupted_day_7_review_is_offered_again(tmp_path, capsys):
    u = five_concept_unit(tmp_path)
    ws = tmp_path / "ws"
    log_scores(u, ws, "pre", [0, 0, 1, 0, 0], "2026-11-01")
    log_scores(u, ws, "post", [1, 1, 1, 0.5, 1], "2026-11-01")
    log_scores(u, ws, "d7", [1, 0.5], "2026-11-08")
    capsys.readouterr()
    due_argv = ["progress", "due", "--course", "C", "--workspace", str(ws), "--date"]
    render_argv = ["progress", "render", "--course", "C", "--workspace", str(ws), "--date"]
    assert main([*due_argv, "2026-11-09"]) == 0
    assert capsys.readouterr().out == (
        '[{"unit": "U5", "phase": "d7", "due": "2026-11-08", "optional": false, "answered": 2, '
        '"remaining": ["c3", "c4", "c5"]}]\n'
    )
    assert main([*render_argv, "2026-11-09"]) == 0
    capsys.readouterr()
    page = (ws / "progress" / "C.md").read_text(encoding="utf-8")
    lines = page.splitlines()
    assert lines[2] == "Across 1 units: pre 0.20 → post 0.90, normalized gain 0.88."
    assert "| U5 | 0.20 → 0.90 | 0.88 | 0.90 → 2 of 5 | — |" in lines
    assert lines[lines.index(PAIRED_NOTE_TEXT) + 2] == PARTIAL_NOTE
    assert "- U5: d7, due 2026-11-08, 2 of 5 answered" in lines
    (strip,) = [x for x in lines if x.endswith("  U5")]
    assert "○" in strip and "●" in strip and "◆" not in strip

    log_scores(u, ws, "d7", [1, 0.5, 0.5], "2026-11-10", concepts=FIVE[2:])
    capsys.readouterr()
    assert main([*due_argv, "2026-11-10"]) == 0
    assert capsys.readouterr().out == "[]\n"
    assert main([*render_argv, "2026-11-10"]) == 0
    lines = (ws / "progress" / "C.md").read_text(encoding="utf-8").splitlines()
    assert "| U5 | 0.20 → 0.90 | 0.88 | 0.90 → 0.70 | 0.78 |" in lines
    assert PARTIAL_NOTE not in lines


PAIRED_NOTE_TEXT = (
    "Gain and retention compare only the concepts attempted in both phases, "
    "and the means beside them are over those concepts."
)


def test_confident_wrong_shows_the_answer(tmp_path):
    u = unit_dir(tmp_path)
    ws = tmp_path / "ws"
    assert main(["progress", "log", "--unit", str(u), "--item", "c1-B", "--phase", "post", "--score", "0",
                 "--confidence", "3", "--answer", "six percent", "--workspace", str(ws)]) == 0
    lines = render_progress("C", ws, date.today()).read_text(encoding="utf-8").splitlines()
    start = lines.index("## Confident but wrong") + 2
    assert lines[start] == '- U1: c1-B (c1) "Prompt c1-B?", post, (slide 2, 01:00); answered "six percent"'


def test_cli_render_takes_a_date(tmp_path, capsys):
    write_attempts(tmp_path, mk_post(unit="u1", day=date(2026, 11, 20)))
    argv = ["progress", "render", "--course", "C", "--workspace", str(tmp_path), "--date"]

    def due_today(day):
        assert main([*argv, day]) == 0
        lines = (tmp_path / "progress" / "C.md").read_text(encoding="utf-8").splitlines()
        return lines[lines.index("## Due today") + 2]

    assert due_today("2026-11-21") == "- u1: d1 (optional), due 2026-11-21"
    assert due_today("2026-11-20") == "None."
    with pytest.raises(SystemExit) as e:
        main([*argv, "2026-02-30"])
    assert e.value.code == 2


def test_log_from_the_earlier_code_works_everywhere(tmp_path, capsys):
    import shutil

    from conftest import fx

    u = tmp_path / "unit"
    shutil.copytree(fx("units", "ok"), u)
    ws = tmp_path / "ws"
    base = dict(course="demo-course", unit="unit-01", citation="(slide 1)", exposure="unknown", confidence=2)

    def line(item_id, variant, concept, phase, score, prompt=None, **over):
        obj = {"ts": "2026-11-20T10:00:00+00:00", "course": base["course"], "unit": base["unit"],
               "item_id": item_id, "variant": variant, "concept": concept, "phase": phase, "score": score,
               "confidence": over.get("confidence", 2), "citation": base["citation"], "exposure": "unknown"}
        if prompt is not None:
            obj["prompt"] = prompt
        return json.dumps(obj)

    write_raw(ws / "progress" / "demo-course.jsonl", [
        line("ci-A", "A", "compound-interest", "pre", 0),
        line("cf-A", "A", "compounding-frequency", "pre", 1, prompt="Q cf-A?"),
        line("ci-B", "B", "compound-interest", "post", 0, prompt="Q ci-B?", confidence=3),
        line("cf-C", "C", "compounding-frequency", "post", 1, prompt="Q cf-C?"),
    ])
    wsarg = ["--workspace", str(ws)]

    def run(argv):
        code = main([*argv, *wsarg])
        captured = capsys.readouterr()
        assert captured.err == "", argv
        return code, captured.out

    code, out = run(["progress", "due", "--course", "demo-course", "--date", "2026-11-21"])
    assert code == 0
    assert json.loads(out) == [
        {"unit": "unit-01", "phase": "d1", "due": "2026-11-21", "optional": True, "answered": 0, "remaining": None},
    ]
    code, _ = run(["progress", "render", "--course", "demo-course", "--date", "2026-11-21"])
    assert code == 0
    page = (ws / "progress" / "demo-course.md").read_text(encoding="utf-8")
    assert "| unit-01 | 0.50 → 0.50 | 0.00 | 0.50 → — | — |" in page.splitlines()
    code, _ = run(["progress", "log", "--unit", str(u), "--item", "ci-C", "--phase", "d7", "--score", "1",
                   "--confidence", "2", "--date", "2026-11-27"])
    assert code == 0
    att = load_attempts("demo-course", ws)
    assert len(att) == 5
    assert all(a.answer is None and a.assigned is None for a in att[:4])
    assert att[4].assigned == ["compound-interest", "compounding-frequency"]
    code, out = run(["progress", "due", "--course", "demo-course", "--date", "2026-11-27"])
    assert code == 0
    (entry,) = json.loads(out)
    assert (entry["phase"], entry["due"], entry["answered"], entry["remaining"]) == (
        "d7", "2026-11-27", 1, ["compounding-frequency"]
    )
    code, out = run(["cards", "add-misses", "--unit", str(u)])
    assert code == 0
    assert json.loads(out)["added"] == 1
