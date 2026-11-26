import json
import shutil

import pytest
from conftest import fx
from tutor_any_lecture.citations import link_unit
from tutor_any_lecture.cli import main
from tutor_any_lecture.unit import UnitPaths
from tutor_any_lecture.notecheck import measure_note
from tutor_any_lecture.verify import format_measures, run_verify

CHECK_NAMES = ["citations", "coverage", "terms", "numbers", "structure",
               "items", "cards", "map", "banned_phrases"]


# ---------------------------------------------------------------- local helpers


def copy_fixture(name, tmp_path):
    """A copy of a fixture unit; tests never run verify on the committed folders."""
    dst = tmp_path / name
    shutil.copytree(fx("units", name), dst)
    return dst


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def drop_duration(u):
    paths = UnitPaths(u)
    plan = _read_json(paths.plan)
    plan["duration_s"] = None
    _write_json(paths.plan, plan)
    source = _read_json(paths.source)
    source["duration"] = None
    _write_json(paths.source, source)


def append_to_note(u, text):
    path = UnitPaths(u).explanation
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def set_outputs(u, outputs):
    path = UnitPaths(u).plan
    plan = _read_json(path)
    plan["outputs"] = outputs
    _write_json(path, plan)


def entry(r, name):
    return next(c for c in r["checks"] if c["name"] == name)


# ---------------------------------------------------------------- tests


def test_ok_unit_passes(tmp_path):
    r = run_verify(copy_fixture("ok", tmp_path))
    assert r["overall"] == "PASS" and r["report"] == "Automated checks passed; not visually reviewed."


def test_bad_unit_fails_named_checks(tmp_path):
    r = run_verify(copy_fixture("bad", tmp_path))
    assert r["overall"] == "FAIL"
    assert {"citations", "coverage", "items"} <= {c["name"] for c in r["checks"] if c["status"] == "FAIL"}
    assert r["report"] == "Automated checks failed."


def test_cli_exit_codes(tmp_path):
    assert main(["verify", "--unit", str(copy_fixture("bad", tmp_path))]) == 1


def test_cli_json_and_pass_exit(tmp_path, capsys):
    code = main(["verify", "--unit", str(copy_fixture("ok", tmp_path)), "--json"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.endswith("\n") and out.count("\n") == 1
    r = json.loads(out)
    assert r["overall"] == "PASS" and [c["name"] for c in r["checks"]] == CHECK_NAMES


def test_unknown_duration_degrades(tmp_path):
    u = copy_fixture("ok", tmp_path)
    drop_duration(u)
    r = run_verify(u)
    assert r["overall"] == "PASS"
    assert next(c for c in r["checks"] if c["name"] == "citations")["status"] == "WARN"


def test_slides_only_unit_passes(tmp_path):
    r = run_verify(copy_fixture("slides_only", tmp_path))
    assert r["overall"] == "PASS"


def test_slides_only_time_citation_fails(tmp_path):
    u = copy_fixture("slides_only", tmp_path)
    append_to_note(u, "\n\nThe balance is updated once a month (0:30).\n")
    assert entry(run_verify(u), "citations")["status"] == "FAIL"


def test_code_is_not_a_citation(tmp_path):
    u = copy_fixture("slides_only", tmp_path)
    append_to_note(u, "\n\nCall `rev(1:20)` to reverse a vector.\n\n```r\ntotal <- sum(1:10)\n```\n")
    assert entry(run_verify(u), "citations")["status"] == "PASS"


def test_missing_transcript_fails(tmp_path):
    u = copy_fixture("ok", tmp_path)
    UnitPaths(u).transcript.unlink()
    c = entry(run_verify(u), "citations")
    assert c["status"] == "FAIL" and "sources/transcript.json missing" in c["details"]


def test_nine_checks_in_order(tmp_path):
    u = copy_fixture("bad", tmp_path)
    r = run_verify(u)
    assert [c["name"] for c in r["checks"]] == CHECK_NAMES
    assert r["warnings"] == sum(c["status"] == "WARN" for c in r["checks"])
    assert json.loads(UnitPaths(u).verify.read_text(encoding="utf-8")) == r


def test_structure_folds_sub_results(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, "\n\n#### Too deep\n\nA short paragraph (slide 1).\n")
    c = entry(run_verify(u), "structure")
    assert c["status"] == "FAIL" and any(d.startswith("h4: ") for d in c["details"])


def test_outputs_skip_checks(tmp_path):
    u = copy_fixture("ok", tmp_path)
    set_outputs(u, ["explanation"])
    paths = UnitPaths(u)
    for f in (paths.items, paths.assignment, paths.cards_json, paths.map):
        f.unlink()
    r = run_verify(u)
    assert r["overall"] == "PASS"
    for name in ("items", "cards", "map"):
        assert entry(r, name) == {"name": name, "status": "PASS", "details": ["skipped: not in plan.outputs"]}


def test_listed_output_missing_file_fails(tmp_path):
    u = copy_fixture("ok", tmp_path)
    paths = UnitPaths(u)
    for f in (paths.items, paths.cards_json, paths.map):
        f.unlink()
    r = run_verify(u)
    assert {"items", "cards", "map"} <= {c["name"] for c in r["checks"] if c["status"] == "FAIL"}


def test_inline_math_is_not_currency(tmp_path):
    u = copy_fixture("ok", tmp_path)
    before = entry(run_verify(u), "numbers")
    append_to_note(u, "\n\nThe count doubles at each step, $2^n$ in total (slide 1).\n")
    assert entry(run_verify(u), "numbers") == before


def test_terms_numbers_and_banned_phrases_warn(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, "\n\nIn practice the Monte Carlo run took 3 days, a tapestry of GBM output (slide 1).\n")
    r = run_verify(u)
    assert r["overall"] == "PASS"
    assert entry(r, "terms") == {"name": "terms", "status": "WARN", "details": [
        "not in the transcript or slides: Monte Carlo", "not in the transcript or slides: GBM"]}
    assert entry(r, "numbers") == {"name": "numbers", "status": "WARN", "details": [
        "in the note, not in the sources: 3 days"]}
    assert entry(r, "banned_phrases") == {"name": "banned_phrases", "status": "WARN", "details": [
        "banned phrase: tapestry"]}


def test_malformed_files_fail_their_checks(tmp_path):
    u = copy_fixture("ok", tmp_path)
    paths = UnitPaths(u)
    paths.map.write_text("{", encoding="utf-8", newline="\n")
    paths.cards_json.write_text('{"id": "card-1"}\n', encoding="utf-8", newline="\n")
    paths.assignment.write_text("not json\n", encoding="utf-8", newline="\n")
    r = run_verify(u)
    for name, file_name in (("items", "assignment.json"), ("cards", "cards.json"), ("map", "map.json")):
        c = entry(r, name)
        assert c["status"] == "FAIL" and len(c["details"]) == 1 and c["details"][0].startswith(file_name + ": ")


def test_cli_table_ends_with_report(tmp_path, capsys):
    code = main(["verify", "--unit", str(copy_fixture("bad", tmp_path))])
    lines = capsys.readouterr().out.splitlines()
    assert code == 1
    assert lines[0] == "FAIL  citations" and "      slide 9 > 3" in lines
    assert lines[-1] == "Automated checks failed."



def five_slide_unit(tmp_path, not_covered):
    """Local helper: the ok unit with slides 4 and 5 added and this not-covered line."""
    u = copy_fixture("ok", tmp_path)
    pages_path = UnitPaths(u).pages
    pages = _read_json(pages_path)
    pages += [{"n": n, "label": str(n), "text": f"Extra slide {n}", "image": None} for n in (4, 5)]
    _write_json(pages_path, pages)
    path = UnitPaths(u).explanation
    md = path.read_text(encoding="utf-8")
    assert "- slide 3\n" in md
    path.write_text(md.replace("- slide 3\n", not_covered), encoding="utf-8", newline="\n")
    return u


def test_not_covered_accepts_ranges(tmp_path):
    assert entry(run_verify(five_slide_unit(tmp_path / "a", "- slides 3–5\n")), "coverage") == {
        "name": "coverage", "status": "PASS", "details": []}
    assert entry(run_verify(five_slide_unit(tmp_path / "b", "- slide 3, slides 4-5\n")), "coverage")[
        "status"] == "PASS"
    assert entry(run_verify(five_slide_unit(tmp_path / "c", "")), "coverage") == {
        "name": "coverage", "status": "FAIL", "details": [
            f"slide {n} is neither cited nor listed in the not-covered section" for n in (3, 4, 5)]}



def test_coverage_expands_slide_ranges(tmp_path):
    def unit(name, extra):
        u = copy_fixture("ok", tmp_path / name)
        path = UnitPaths(u).explanation
        md = path.read_text(encoding="utf-8").replace("- slide 3\n", "")
        path.write_text(md + extra, encoding="utf-8", newline="\n")
        return u

    assert entry(run_verify(unit("bare", "")), "coverage")["details"] == [
        "slide 3 is neither cited nor listed in the not-covered section"]
    cited = unit("cited", "\nThe limit case is continuous compounding (slides 2–3).\n")
    assert entry(run_verify(cited), "coverage") == {"name": "coverage", "status": "PASS", "details": []}


def test_escaped_dollar_is_currency(tmp_path):
    u = copy_fixture("ok", tmp_path)
    # Unescaped, "$5 a month, or $" would read as inline math and vanish.
    append_to_note(u, "\n\nThe fee is \\$5 a month, or \\$x for the year (slide 1).\n")
    assert "in the note, not in the sources: $5" in entry(run_verify(u), "numbers")["details"]


# ---------------------------------------------------------------- quote_source (Task 23)


def quote_source_details(r):
    """Local helper: the quote_source details folded into the citations entry, prefix removed."""
    return [d[len("quote_source: "):] for d in entry(r, "citations")["details"] if d.startswith("quote_source: ")]


def add_segment(u, start, end, text):
    """Local helper: append one segment to the unit's transcript.json."""
    path = UnitPaths(u).transcript
    data = _read_json(path)
    data["segments"].append({"start": start, "end": end, "text": text})
    _write_json(path, data)


def test_invented_blockquote_fails_quote_source(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, "\n\n> The bank pays a bonus rate to every customer who never withdraws. (slide 1, 1:15)\n")
    c = entry(run_verify(u), "citations")
    assert c["status"] == "FAIL"
    assert quote_source_details(run_verify(u)) == [
        "quote 'The bank pays a bonus rate to every cust…' cited (slide 1, 1:15) "
        "is not in the transcript or the slides"
    ]


def test_invented_inline_quote_fails_quote_source(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, '\n\nThe lecturer warned that "banks always round the rate down" (slide 2, 2:40).\n')
    r = run_verify(u)
    assert entry(r, "citations")["status"] == "FAIL"
    assert quote_source_details(r) == [
        "quote 'banks always round the rate down' cited (slide 2, 2:40) is not in the transcript or the slides"
    ]


@pytest.mark.parametrize("text", [
    '\n\n- The lecturer warned that "banks always round the rate down" (slide 2, 2:40).\n',
    '\n\n> [!WARNING] Rounding\n> The lecturer warned that "banks always round the rate down".\n'
    "> (slide 2, 2:40)\n",
    "\n\n| Claim | Where |\n|---|---|\n"
    '| "banks always round the rate down" | (slide 2, 2:40) |\n',
], ids=["bullet", "callout", "table"])
def test_invented_inline_quote_outside_paragraphs_fails_quote_source(tmp_path, text):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, text)
    r = run_verify(u)
    assert entry(r, "citations")["status"] == "FAIL"
    assert quote_source_details(r) == [
        "quote 'banks always round the rate down' cited (slide 2, 2:40) is not in the transcript or the slides"
    ]


def test_quote_far_from_cited_time_warns(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 600.0, 630.0, "Some banks print the effective annual rate next to every advertised APR.")
    append_to_note(u, '\n\nAs the lecturer put it, "some banks print the effective annual rate" (0:30).\n')
    r = run_verify(u)
    assert entry(r, "citations")["status"] == "WARN"
    assert quote_source_details(r) == [
        "quote 'some banks print the effective annual ra…' is not at (0:30); found at 10:00"
    ]


def test_quote_on_another_slide_warns(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, '\n\nThe deck ends on "Continuous compounding: the limit as the period shrinks to zero" (slide 1).\n')
    r = run_verify(u)
    assert entry(r, "citations")["status"] == "WARN"
    assert quote_source_details(r) == [
        "quote 'Continuous compounding: the limit as the…' is not at (slide 1); found on slide 3"
    ]


def test_quote_with_ellipsis_and_brackets_passes(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 178.0, 180.0, "Remember: the balance on your statement already has interest included.")
    append_to_note(
        u,
        '\n\nThe statement shows "the balance on your statement … [that is] already has interest included" (2:59).\n\n'
        "> With compound interest … the interest you earned [it is] added to the balance (1:15)\n",
    )
    r = run_verify(u)
    assert entry(r, "citations") == {"name": "citations", "status": "PASS", "details": []}


def test_quote_punctuation_and_case_do_not_matter(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(
        u,
        "\n\n> WITH COMPOUND INTEREST — the interest you earned is added to the balance; "
        "and next period, it earns interest too! (1:15)\n\n"
        "The slide reads “Simple — interest on the DEPOSIT only.” (slide 1).\n",
    )
    r = run_verify(u)
    assert entry(r, "citations") == {"name": "citations", "status": "PASS", "details": []}


def test_cjk_quote_ignores_spaces(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 170.0, 178.0, "复利 就是 利息 也会 生出 利息。")
    append_to_note(u, "\n\n> 复利就是利息也会生出利息 (2:55)\n")
    assert quote_source_details(run_verify(u)) == []
    append_to_note(u, "\n\n> 单利就是本金永远不会变多 (2:55)\n")
    assert quote_source_details(run_verify(u)) == [
        "quote '单利就是本金永远不会变多' cited (2:55) is not in the transcript or the slides"
    ]


def test_time_only_quote_without_transcript_has_no_quote_source(tmp_path):
    u = copy_fixture("slides_only", tmp_path)
    append_to_note(u, "\n\n> The balance is updated once a month by the bank. (0:30)\n")
    append_to_note(u, '\nThe lecturer said "rate … balance … interest" (0:30).\n')
    c = entry(run_verify(u), "citations")
    assert c["status"] == "FAIL" and quote_source_details(run_verify(u)) == []


def test_bundled_sample_passes_quote_source(tmp_path):
    from tutor_any_lecture.selftest import run_selftest

    unit = tmp_path / "sample"
    assert run_selftest(unit)["ok"] is True
    r = _read_json(UnitPaths(unit).verify)
    assert quote_source_details(r) == []
    assert entry(r, "citations")["status"] in ("PASS", "WARN")


def test_quote_parts_match_whole_words(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 178.0, 180.0, "The interest rate is now fixed.")
    append_to_note(u, '\n\nThe lecturer said "interest rate is now fixed" (2:59).\n')
    assert entry(run_verify(u), "citations") == {"name": "citations", "status": "PASS", "details": []}
    append_to_note(u, '\n\nAn invented quote reads "rest rate is now fix" (2:59).\n')
    r = run_verify(u)
    assert entry(r, "citations")["status"] == "FAIL"
    assert quote_source_details(r) == [
        "quote 'rest rate is now fix' cited (2:59) is not in the transcript or the slides"
    ]


def test_quote_with_inline_code_matches(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 178.0, 180.0, "Use np.mean to average the column.")
    append_to_note(u, '\n\nThe tip was "use `np.mean` to average the column" (2:59).\n')
    assert entry(run_verify(u), "citations") == {"name": "citations", "status": "PASS", "details": []}


def test_quote_with_markdown_link_matches(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 178.0, 180.0, "Read the chapter on compound growth before the next lecture.")
    append_to_note(
        u,
        '\n\nThe homework: "read the [chapter on compound growth](https://example.org/ch3) '
        'before the next lecture" (2:59).\n',
    )
    assert entry(run_verify(u), "citations") == {"name": "citations", "status": "PASS", "details": []}


def test_quote_in_list_item_with_citation_on_next_line_is_checked(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, '\n\n- The lecturer warned that "banks always round the rate down"\n  (slide 2, 2:40).\n')
    r = run_verify(u)
    assert entry(r, "citations")["status"] == "FAIL"
    assert quote_source_details(r) == [
        "quote 'banks always round the rate down' cited (slide 2, 2:40) is not in the transcript or the slides"
    ]


# ---------------------------------------------------------------- prose-only numbers and terms (Task 23)


def test_numbers_ignore_marker_sections_and_notes(tmp_path):
    u = copy_fixture("ok", tmp_path)
    before = entry(run_verify(u), "numbers")
    append_to_note(
        u,
        "\n\n<!-- tal:errata -->\n> [!CAUTION]\n> The slide says 5% a month. (slide 1)\n<!-- /tal:errata -->\n"
        "\n> [!NOTE]\n> Over 3 years the gap grows to £40 or more.\n",
    )
    assert entry(run_verify(u), "numbers") == before
    append_to_note(u, "\nOver 3 years the gap grows (slide 1).\n")
    assert "in the note, not in the sources: 3 years" in entry(run_verify(u), "numbers")["details"]


def test_terms_ignore_marker_sections(tmp_path):
    u = copy_fixture("ok", tmp_path)
    before = entry(run_verify(u), "terms")
    append_to_note(
        u,
        "\n\n<!-- tal:check -->\n1. Would a Monte Carlo run of GBM paths change the answer?\n\n"
        "<details><summary>Answer</summary>\n\nNo.\n\n</details>\n<!-- /tal:check -->\n",
    )
    assert entry(run_verify(u), "terms") == before
    append_to_note(u, "\nIn the end a Monte Carlo run would agree (slide 1).\n")
    assert "not in the transcript or slides: Monte Carlo" in entry(run_verify(u), "terms")["details"]


def test_a_page_not_yet_transcribed_warns(tmp_path):
    not_yet = "slide 2 is not yet transcribed: read sources/slides/photo-002.jpg, then run slides text --page 2"

    def unit(name, image, extra_page=False):
        u = copy_fixture("slides_only", tmp_path / name)
        path = UnitPaths(u).pages
        pages = _read_json(path)
        pages[1].update(text="", image=image)
        if extra_page:
            pages.append({"n": 4, "label": "4", "text": "Annuities", "image": None})
        _write_json(path, pages)
        return u

    assert entry(run_verify(unit("photo", "photo-002.jpg")), "coverage") == {
        "name": "coverage", "status": "WARN", "details": [not_yet]}
    assert entry(run_verify(unit("none", None)), "coverage") == {"name": "coverage", "status": "PASS", "details": []}
    assert entry(run_verify(unit("frame", "../keyframes/frame-002.jpg")), "coverage") == {
        "name": "coverage", "status": "PASS", "details": []}
    assert entry(run_verify(unit("uncited", "photo-002.jpg", extra_page=True)), "coverage") == {
        "name": "coverage", "status": "FAIL",
        "details": ["slide 4 is neither cited nor listed in the not-covered section", not_yet]}


def test_not_covered_singular_takes_one_number(tmp_path):
    u = five_slide_unit(tmp_path / "a", "- slide 3 - 5 worked examples skipped\n")
    assert entry(run_verify(u), "coverage") == {"name": "coverage", "status": "FAIL", "details": [
        f"slide {n} is neither cited nor listed in the not-covered section" for n in (4, 5)]}
    reversed_range = five_slide_unit(tmp_path / "b", "- slides 5–3\n")
    assert entry(run_verify(reversed_range), "coverage")["details"] == [
        f"slide {n} is neither cited nor listed in the not-covered section" for n in (3, 4)]


# ---------------------------------------------------------------- broken sources files (Task 23)


@pytest.mark.parametrize("name, breakage", [
    ("source.json", lambda d: d.pop("acquisition")),
    ("source.json", lambda d: d.update(duration="long")),
    ("transcript.json", lambda d: d["segments"][0].pop("start")),
    ("transcript.json", lambda d: d["segments"][1].update(text=None)),
    ("pages.json", lambda d: d[0].pop("text")),
    ("pages.json", lambda d: d[2].update(n="3")),
])
def test_cli_verify_broken_sources_files_are_one_line(tmp_path, capsys, name, breakage):
    u = copy_fixture("ok", tmp_path)
    paths = UnitPaths(u)
    path = {"source.json": paths.source, "transcript.json": paths.transcript, "pages.json": paths.pages}[name]
    data = _read_json(path)
    breakage(data)
    _write_json(path, data)
    assert main(["verify", "--unit", str(u)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.endswith("\n") and captured.err.count("\n") == 1
    assert captured.err.startswith(name)


# ---- what the gate measured; the reader's guide (Task 29, L7, L9) ---------------


MEASURE_KEYS = {"minutes", "length", "time_citations", "quotes", "quote_share", "quote_ratio", "h2"}


def test_measures_are_reported_on_pass(tmp_path, capsys):
    u = copy_fixture("ok", tmp_path)
    r = run_verify(u)
    assert r["overall"] == "PASS"
    m = r["measures"]
    assert set(m) == MEASURE_KEYS
    assert m["minutes"] == 3.0
    assert m["length"]["unit"] == "words" and m["length"]["window"] == [26, 133.33]
    assert m["length"]["per_min"] == round(m["length"]["total"] / 3, 2)
    assert m["time_citations"] == {"per_min": 1.0, "min": 0.67}
    assert m["quotes"] == {"per_min": 0.33, "min": 0.22}
    assert m["quote_ratio"] is None and m["quote_share"]["window"] == [0.1, 0.4]
    assert 0 < m["quote_share"]["value"] < 1
    assert m["h2"] == {"count": 3, "max": 16}
    assert json.loads(UnitPaths(u).verify.read_text(encoding="utf-8"))["measures"] == m
    # the table: one measures line after the checks, before the report line
    assert main(["verify", "--unit", str(u)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "Automated checks passed; not visually reviewed."
    assert lines[-2].startswith("measures: ") and sum(x.startswith("measures:") for x in lines) == 1
    assert lines[-2] == (
        f"measures: length {m['length']['per_min']} words/min (26-133.33); time citations 1.0/min (>= 0.67); "
        f"quotes 0.33/min (>= 0.22); quote share {m['quote_share']['value']} (0.1-0.4); H2 3 (<= 16)"
    )


def test_measures_are_reported_on_fail_and_without_duration(tmp_path):
    r = run_verify(copy_fixture("bad", tmp_path))
    assert r["overall"] == "FAIL" and set(r["measures"]) == MEASURE_KEYS
    u = copy_fixture("ok", tmp_path / "unknown")
    drop_duration(u)
    m = run_verify(u)["measures"]
    assert m["minutes"] is None and m["length"]["per_min"] is None and m["length"]["window"] is None
    assert m["time_citations"]["per_min"] is None and m["h2"] == {"count": 3, "max": None}


def test_terms_ignore_the_how_to_read_paragraph(tmp_path):
    u = copy_fixture("ok", tmp_path)
    path = UnitPaths(u).explanation
    md = path.read_text(encoding="utf-8")
    guide = (
        "How to read this note: WARNING boxes mark common mistakes, CAUTION boxes hold errata "
        "and IMPORTANT boxes key results, as the Reading Guide Convention says.\n\n"
    )
    first_h2 = md.index("## ")
    path.write_text(md[:first_h2] + guide + md[first_h2:], encoding="utf-8", newline="\n")
    assert entry(run_verify(u), "terms") == {"name": "terms", "status": "PASS", "details": []}
    # callout type names are no terms in the body either; an invented term still is
    append_to_note(u, "\n\nThe note marks a common mistake with a WARNING box and a tutor addition with a NOTE box (slide 1).\n")
    assert entry(run_verify(u), "terms")["status"] == "PASS"
    append_to_note(u, "\n\nHere the Reading Guide Convention applies (slide 1).\n")
    assert entry(run_verify(u), "terms")["details"] == ["not in the transcript or slides: Reading Guide Convention"]


def test_card_with_an_unknown_concept_fails_the_gate(tmp_path):
    u = copy_fixture("ok", tmp_path)
    path = UnitPaths(u).cards_json
    cards = _read_json(path)
    (first,) = [c for c in cards if c["id"] == "card-1"]
    first["concept"] = "nope"
    _write_json(path, cards)
    cards_entry = entry(run_verify(u), "cards")
    assert cards_entry["status"] == "FAIL"
    assert cards_entry["details"] == ["concept: card-1: concept 'nope' is not a concept id in plan.json"]


# ---------------------------------------------------------------- time links


YT = "https://www.youtube.com/watch?v=x"


def set_source(u, kind, url):
    """Local helper: give the unit's source.json this kind and address."""
    path = UnitPaths(u).source
    source = _read_json(path)
    source.update(kind=kind, url=url)
    _write_json(path, source)


def replace_in_note(u, old, new):
    path = UnitPaths(u).explanation
    md = path.read_text(encoding="utf-8")
    assert old in md
    path.write_text(md.replace(old, new), encoding="utf-8", newline="\n")


def test_unlinked_times_in_a_video_unit_warn(tmp_path):
    u = copy_fixture("ok", tmp_path)
    set_source(u, "url", YT)
    assert entry(run_verify(u), "citations") == {"name": "citations", "status": "WARN", "details": [
        "time_links: 3 time citations are not linked to the video: run tutor-any-lecture cite link --unit DIR"]}
    link_unit(u)
    assert entry(run_verify(u), "citations") == {"name": "citations", "status": "PASS", "details": []}
    other = copy_fixture("ok", tmp_path / "other")
    set_source(other, "url", "https://video.example.com/watch?v=x")
    assert entry(run_verify(other), "citations") == {"name": "citations", "status": "PASS", "details": []}


def test_one_unlinked_time_is_one_citation(tmp_path):
    u = copy_fixture("ok", tmp_path)
    set_source(u, "platform", YT)
    link_unit(u)
    append_to_note(u, "\n\nThe rate is fixed for the year (slide 1, 0:50).\n")
    assert entry(run_verify(u), "citations")["details"] == [
        "time_links: 1 time citation is not linked to the video: run tutor-any-lecture cite link --unit DIR"]


def test_a_time_link_that_points_elsewhere_warns(tmp_path):
    u = copy_fixture("ok", tmp_path)
    set_source(u, "url", YT)
    link_unit(u)
    replace_in_note(u, "&t=42s)", "&t=40s)")
    assert entry(run_verify(u), "citations") == {"name": "citations", "status": "WARN", "details": [
        "time_links: time link 0:42 points at 0:40"]}
    replace_in_note(u, "&t=40s", "")
    assert entry(run_verify(u), "citations") == {"name": "citations", "status": "WARN", "details": [
        "time_links: time link 0:42 has no time in its address"]}


def test_quote_source_detail_shows_citations_without_addresses(tmp_path):
    u = copy_fixture("ok", tmp_path)
    set_source(u, "url", YT)
    append_to_note(u, '\n\nThe lecturer warned that "banks always round the rate down" (slide 2, 2:40).\n')
    link_unit(u)
    assert quote_source_details(run_verify(u)) == [
        "quote 'banks always round the rate down' cited (slide 2, 2:40) is not in the transcript or the slides"
    ]


# ---------------------------------------------------------------- quotation marks; short quotes


def test_guillemet_quote_is_checked_against_the_transcript(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, "\n\nThe lecturer warned that «banks always round the rate down» (slide 2, 2:40).\n")
    r = run_verify(u)
    assert entry(r, "citations")["status"] == "FAIL"
    assert quote_source_details(r) == [
        "quote 'banks always round the rate down' cited (slide 2, 2:40) is not in the transcript or the slides"
    ]


def test_quote_with_no_checkable_part_warns(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, '\n\nThe lecturer said "rate … balance … interest" (1:15).\n')
    r = run_verify(u)
    assert entry(r, "citations")["status"] == "WARN"
    assert quote_source_details(r) == [
        "quote 'rate … balance … interest' cited (1:15) has no part of three words or six CJK characters to check"
    ]


# ---------------------------------------------------------------- the speaker of a quote


COMPUTER = "It depends on the strength of your computer"
LABELLED = [(100, 105, "STUDENT: [INAUDIBLE]"), (105, 110, f"LECTURER: {COMPUTER}.")]
STUDENT_ANSWERED = f'\n\nA student answered: "{COMPUTER}" (1:45).\n'


def speaker_unit(tmp_path, segments, note):
    """Local helper: the ok unit with these segments added and this text appended to the note."""
    u = copy_fixture("ok", tmp_path)
    for start, end, text in segments:
        add_segment(u, start, end, text)
    append_to_note(u, note)
    return u


def test_quote_given_to_a_student_but_labelled_lecturer_warns(tmp_path):
    r = run_verify(speaker_unit(tmp_path, LABELLED, STUDENT_ANSWERED))
    assert entry(r, "citations")["status"] == "WARN"
    assert quote_source_details(r) == ["quote 'It depends on the strength of your compu…' is LECTURER's words at 1:45"]


def test_student_words_given_to_no_student_warn(tmp_path):
    segments = [(100, 105, "STUDENT: Does the rate change every single year?"), (105, 110, "LECTURER: Good question.")]
    quote = '"does the rate change every single year" (1:40).\n'
    r = run_verify(speaker_unit(tmp_path / "a", segments, "\n\nThe lecturer was asked " + quote))
    assert quote_source_details(r) == ["quote 'does the rate change every single year' is STUDENT's words at 1:40"]
    r = run_verify(speaker_unit(tmp_path / "b", segments, "\n\nA student asked " + quote))
    assert quote_source_details(r) == []


def test_speaker_check_is_silent_without_labels(tmp_path):
    unlabelled = [(start, end, text.split(": ", 1)[1]) for start, end, text in LABELLED]
    assert quote_source_details(run_verify(speaker_unit(tmp_path / "a", unlabelled, STUDENT_ANSWERED))) == []
    # labels exist, but none is in force at the segment the quote starts in
    segments = [(100, 105, f"{COMPUTER}."), (105, 110, "STUDENT: Thanks."), (110, 115, "LECTURER: Right.")]
    assert quote_source_details(run_verify(speaker_unit(tmp_path / "b", segments, STUDENT_ANSWERED))) == []


def test_students_without_a_speech_verb_make_no_speaker_claim(tmp_path):
    note = f'\n\nFor n students, "{COMPUTER.lower()}" (1:45).\n'
    assert quote_source_details(run_verify(speaker_unit(tmp_path, LABELLED, note))) == []


def test_speaker_check_never_reads_blockquotes_or_other_languages(tmp_path):
    # a student's words as a blockquote, and the first test's claim in a note in French
    asked = [(100, 105, "STUDENT: Does the rate change every single year?"), (105, 110, "LECTURER: Good question.")]
    block = speaker_unit(tmp_path / "block", asked, "\n\n> Does the rate change every single year? (1:40)\n")
    assert quote_source_details(run_verify(block)) == []
    french = speaker_unit(tmp_path / "fr", LABELLED, STUDENT_ANSWERED)
    plan = _read_json(UnitPaths(french).plan)
    plan["note_language"] = "fr"
    _write_json(UnitPaths(french).plan, plan)
    assert quote_source_details(run_verify(french)) == []


# ---------------------------------------------------------------- scripts the checks cannot split

# synthetic: "compound interest is interest that comes from interest"
THAI = "ดอกเบี้ยทบต้นคือดอกเบี้ยที่เกิดจากดอกเบี้ย"
THAI_NOTE = "## ดอกเบี้ย\n\n" + (THAI + " ") * 40 + "(0:30)\n"


def test_measures_line_when_length_is_not_applied():
    line = format_measures(measure_note(THAI_NOTE, "th", "deep", 3.0, "th"))
    assert line.startswith("measures: length not applied for this language; time citations ")
    unknown = format_measures(measure_note(THAI_NOTE, "th", "deep", None, "th"))
    assert unknown.startswith("measures: length not applied for this language; quote share ")


def set_languages(u, note_language, lecture_language=None):
    """Local helper: set plan.json's note_language, and lecture_language when given."""
    path = UnitPaths(u).plan
    plan = _read_json(path)
    plan["note_language"] = note_language
    if lecture_language is not None:
        plan["lecture_language"] = lecture_language
    _write_json(path, plan)


def test_thai_quote_is_not_looked_up(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 178.0, 180.0, THAI)
    append_to_note(u, '\n\nThe lecturer said "ต้นคือดอกเบี้ยที่เกิดจากดอกเบี้ย" (2:59).\n')
    r = run_verify(u)
    assert r["overall"] == "PASS" and entry(r, "citations")["status"] == "WARN"
    assert quote_source_details(r) == ["quote 'ต้นคือดอกเบี้ยที่เกิดจากดอกเบี้ย': not applied for this language"]


def test_terms_not_applied_for_german(tmp_path):
    sentence = "\n\nDie Zinsen werden Im Zweiten Jahr berechnet (slide 1).\n"
    en = copy_fixture("ok", tmp_path / "en")
    append_to_note(en, sentence)
    assert entry(run_verify(en), "terms") == {"name": "terms", "status": "WARN", "details": [
        "not in the transcript or slides: Die Zinsen", "not in the transcript or slides: Im Zweiten Jahr"]}
    de = copy_fixture("ok", tmp_path / "de")
    set_languages(de, "de")
    append_to_note(de, sentence)
    assert entry(run_verify(de), "terms") == {
        "name": "terms", "status": "WARN", "details": ["not applied for this language"]}


def test_terms_not_applied_to_unsegmented_prose(tmp_path):
    u = copy_fixture("ok", tmp_path)
    set_languages(u, "th")
    path = UnitPaths(u).explanation
    md = path.read_text(encoding="utf-8")
    body = md[md.index("## Interest on interest"):md.index("<!-- tal:check -->")]
    thai_body = "## ดอกเบี้ย\n\n" + (THAI + " ") * 30 + "Reading Guide Convention (slide 1, 0:42).\n\n"
    path.write_text(md.replace(body, thai_body), encoding="utf-8", newline="\n")
    assert entry(run_verify(u), "terms") == {
        "name": "terms", "status": "WARN", "details": ["not applied for this language"]}


@pytest.mark.parametrize("language, segment, sentence", [
    ("ja", "複利とは利息にも利息がつくことです。", "講師は「複利とは利息にも利息がつく」と述べる (2:59)。"),
    ("ko", "복리는 이자에도 이자가 붙는 것입니다.", "강사는 “복리는 이자에도 이자가 붙는 것”이라고 말한다 (2:59)."),
    ("es", "El interés compuesto genera interés sobre el interés.",
     "El profesor dice «el interés compuesto genera interés sobre el interés» (2:59)."),
    ("de", "Zinseszins bedeutet Zinsen auf Zinsen.", "Der Dozent sagt „Zinseszins bedeutet Zinsen auf Zinsen“ (2:59)."),
])
def test_other_language_notes_get_no_false_fail(tmp_path, language, segment, sentence):
    u = copy_fixture("ok", tmp_path)
    set_languages(u, language, language)
    add_segment(u, 178.0, 180.0, segment)
    append_to_note(u, "\n\n" + sentence + "\n")
    r = run_verify(u)
    assert [c["name"] for c in r["checks"] if c["status"] == "FAIL"] == []
    assert r["overall"] != "FAIL"
    assert quote_source_details(r) == []


# ---------------------------------------------------------------- numbers across widths and languages


def test_numbers_match_across_widths_and_languages(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 170.0, 175.0, "A rate of 3% for 5 years, then 3 months more.")
    append_to_note(u, "\n\n利率是３％，存5年，再存3个月 (2:52).\n")
    assert entry(run_verify(u), "numbers") == {"name": "numbers", "status": "PASS", "details": []}


def test_chinese_percent_and_cjk_units(tmp_path):
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 170.0, 175.0, "That is 5 percent a year.")
    append_to_note(u, "\n\n百分之5的利率，等了10年 (2:52).\n")
    assert entry(run_verify(u), "numbers") == {
        "name": "numbers", "status": "WARN", "details": ["in the note, not in the sources: 10年"]}


def test_calendar_years_ordinals_and_month_names_are_not_numbers(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, "\n\n2008年的危机在第3周讲到，3月开始 (slide 1).\n")
    assert entry(run_verify(u), "numbers") == {"name": "numbers", "status": "PASS", "details": []}


def test_numbers_are_shown_as_written(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, "\n\nIt took 20  years (slide 1).\n")
    assert entry(run_verify(u), "numbers") == {
        "name": "numbers", "status": "WARN", "details": ["in the note, not in the sources: 20 years"]}


def test_english_units_ignore_ascii_case_only(tmp_path):
    # Turkish dotless ı and dotted İ equal i only when case is folded beyond ASCII: they are
    # not unit forms and must not crash the check. ASCII case is still ignored.
    u = copy_fixture("ok", tmp_path)
    add_segment(u, 170.0, 175.0, "It took 5 MINUTES.")
    append_to_note(u, "\n\nIt took 5 Minutes, then 7 mınutes and 9 MİNUTES (2:52).\n")
    assert entry(run_verify(u), "numbers") == {"name": "numbers", "status": "PASS", "details": []}


# ---------------------------------------------------------------- stock phrases

EN_PHRASES = [
    "delve", "it's worth noting", "in conclusion", "in summary", "navigate the complexities", "tapestry",
    "a testament to", "delves", "delved", "delving", "it is worth noting", "it's important to note",
    "it is important to note", "it's important to remember", "to summarize", "to sum up", "let's dive in",
    "let's dive into", "deep dive", "dive deep", "in today's fast-paced world", "in the realm of",
    "plays a crucial role", "plays a pivotal role", "unlock the power", "harness the power", "game-changer",
    "game changer", "embark on a journey", "ever-evolving", "I hope this helps", "great question",
]
ZH_PHRASES = [
    "值得注意的是", "总而言之", "综上所述", "不难发现", "让我们一起",
    "值得一提的是", "需要注意的是", "总的来说", "不言而喻", "毋庸置疑", "至关重要", "扮演着重要的角色",
    "深入探讨", "让我们来看看", "希望对你有所帮助", "在当今社会", "随着科技的发展", "一言以蔽之",
]


def set_note_language(u, lang):
    path = UnitPaths(u).plan
    plan = _read_json(path)
    plan["note_language"] = lang
    _write_json(path, plan)


def test_stock_phrase_lists_per_language():
    from importlib import resources

    data = resources.files("tutor_any_lecture").joinpath("data")
    for name, expected in (("en.txt", EN_PHRASES), ("zh.txt", ZH_PHRASES)):
        text = data.joinpath("banned_phrases", name).read_text(encoding="utf-8")
        lines = text.split("\n")
        if lines[-1] == "":
            lines = lines[:-1]
        assert lines == expected
        assert all(line and line == line.strip() for line in lines)
        assert len({line.casefold() for line in lines}) == len(lines)
    assert len(EN_PHRASES) == 32 and len(ZH_PHRASES) == 18
    assert not data.joinpath("banned_phrases.txt").is_file()


def test_stock_phrases_follow_the_note_language(tmp_path):
    u = copy_fixture("ok", tmp_path / "a")
    set_note_language(u, "zh")
    append_to_note(u, "\n\n让我们一起看 delve 的例子 (slide 1)。\n")
    assert entry(run_verify(u), "banned_phrases") == {
        "name": "banned_phrases", "status": "WARN", "details": ["banned phrase: 让我们一起"]}

    u = copy_fixture("ok", tmp_path / "b")
    set_note_language(u, "zh")
    append_to_note(u, "\n\n让我们\n一起看 (slide 1)。\n")
    assert entry(run_verify(u), "banned_phrases")["details"] == ["banned phrase: 让我们一起"]

    u = copy_fixture("ok", tmp_path / "c")
    set_note_language(u, "ja")
    append_to_note(u, "\n\n让我们一起看 delve 的例子 (slide 1)。\n")
    assert entry(run_verify(u), "banned_phrases") == {
        "name": "banned_phrases", "status": "PASS", "details": ["not applied for this language: ja"]}


def test_stock_phrases_match_whole_words(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, "\n\nThe result was a testament towards care, and the tapestrylike grid helped (slide 1).\n")
    assert entry(run_verify(u), "banned_phrases") == {"name": "banned_phrases", "status": "PASS", "details": []}
    append_to_note(u, "\n\nDelve into it. It’s worth noting the rate, in\nsummary, compounds (slide 1).\n")
    assert entry(run_verify(u), "banned_phrases")["details"] == [
        "banned phrase: delve", "banned phrase: it's worth noting", "banned phrase: in summary"]


def test_stock_phrases_skip_quotations_code_and_links(tmp_path):
    u = copy_fixture("ok", tmp_path)
    append_to_note(u, "\n\n".join([
        "",
        'He said "in summary" twice (0:10).',
        "The slide says “in conclusion” (slide 1).",
        "> It is a tapestry of ideas. (0:10)",
        "The word `delve` is code (slide 1).",
        "```\ndelve\n```",
        "See [rates](https://example.org/delve) (slide 1).",
    ]) + "\n")
    assert entry(run_verify(u), "banned_phrases") == {"name": "banned_phrases", "status": "PASS", "details": []}
    append_to_note(u, "\n> [!NOTE]\n> In summary, the rate compounds.\n")
    assert entry(run_verify(u), "banned_phrases") == {
        "name": "banned_phrases", "status": "WARN", "details": ["banned phrase: in summary"]}


def test_measures_line_says_n_a_without_prose():
    from tutor_any_lecture.notecheck import measure_note
    from tutor_any_lecture.verify import format_measures

    line = format_measures(measure_note("## A\n\nplain words\n", "zh", "deep", 90.0, "en"))
    assert "quote ratio n/a (0.4-1.2)" in line
    assert "None" not in line


def test_quotes_with_newly_counted_cjk_characters_are_found(tmp_path):
    u = copy_fixture("ok", tmp_path)
    set_languages(u, "ja", "ja")
    add_segment(u, 178.0, 180.0, "人々は〇から複利を学ぶ。")
    append_to_note(u, "\n\n講師は「人々は〇から複利を学ぶ」と述べる (2:59)。\n")
    r = run_verify(u)
    assert [c["name"] for c in r["checks"] if c["status"] == "FAIL"] == []
    assert quote_source_details(r) == []
