from importlib import resources

import pytest
from conftest import fx, names_by_status, status_of

from tutor_any_lecture.citations import link_times
from tutor_any_lecture.notecheck import (
    QUOTE_PAIRS,
    check_note,
    cited_quote_contexts,
    cited_quotes,
    marker_sections,
    measure_note,
    strip_marker_sections,
)
from tutor_any_lecture.textstats import units

BAD_NOTE = fx("notes", "bad_note.md").read_text(encoding="utf-8")
QUICK_NOTE_1200_WORDS_90MIN = fx("notes", "quick_note_1200_words_90min.md").read_text(encoding="utf-8")

MARKED = """## Part one

Prose one.

<!-- tal:check -->
1. First question?
<details><summary>Answer</summary>Because.</details>
<!-- /tal:check -->

## Part two

Prose two.

<!-- tal:check -->
1. Second question?
<details><summary>Answer</summary>Indeed.</details>
<!-- /tal:check -->
"""

F = "`" * 3
CODE_NOTE = (
    "## A\n\nText (slide 1).\n\n"
    + F
    + "python\n# 1.2 not a heading\n#### nor this\nprint(\"a string literal that is long enough\")\n<!-- tal:check -->\n"
    + F
    + "\n\n"
    + "Use `print(\"another long string literal here\")` now.\n"
)

# 68 CJK characters of prose (2 in the heading, 3 x 22 in the paragraph); the blockquote has
# 38 non-whitespace characters once its citation is left out, so the ratio is 0.56: below 1.0
ZH_NOTE = (
    "## 复利\n\n"
    + "本金每一期都把利息并入,下一期按更大的本金计息。" * 3
    + "\n\n> Interest is added to the balance each period. (slide 2, 0:40)\n"
)


def test_fail_rules():
    r = names_by_status(check_note(BAD_NOTE, "en", "deep", 90, "markdown"))
    assert {
        "h4",
        "numbered_heading",
        "quotes_per_paragraph",
        "callout_type",
        "uncited_blockquote",
        "toc_mismatch",
        "details_missing",
        "uncited_quote",
    } <= r["FAIL"]


def test_warns_scale_with_goal():
    assert 1150 <= units(QUICK_NOTE_1200_WORDS_90MIN, "en") <= 1250
    quick = names_by_status(check_note(QUICK_NOTE_1200_WORDS_90MIN, "en", "quick", 90, "markdown"))
    assert "length" not in quick.get("WARN", set())
    deep = names_by_status(check_note(QUICK_NOTE_1200_WORDS_90MIN, "en", "deep", 90, "markdown"))
    assert "length" in deep.get("WARN", set())


def test_unknown_duration_warns():
    r = names_by_status(check_note(QUICK_NOTE_1200_WORDS_90MIN, "en", "quick", None, "markdown"))
    assert "duration" in r["WARN"] and "length" not in r["WARN"]


def test_marker_sections_repeated_check():
    s = marker_sections(MARKED)
    assert set(s) == {"pretest", "check", "not-covered", "errata"}
    assert s["check"] == [
        "1. First question?\n<details><summary>Answer</summary>Because.</details>",
        "1. Second question?\n<details><summary>Answer</summary>Indeed.</details>",
    ]
    assert s["pretest"] == [] and s["not-covered"] == [] and s["errata"] == []
    assert status_of(check_note(MARKED, "en", "deep", 90, "markdown"), "markers") == "PASS"


def test_strip_marker_sections():
    assert strip_marker_sections(MARKED) == "## Part one\n\nProse one.\n\n\n## Part two\n\nProse two.\n\n"


def test_unclosed_marker_fails():
    md = "## A\n\n<!-- tal:pretest -->\n1. Q?\n"
    assert status_of(check_note(md, "en", "deep", 90, "markdown"), "markers") == "FAIL"
    assert marker_sections(md)["pretest"] == []
    assert strip_marker_sections(md) == md


def test_code_is_ignored():
    assert "FAIL" not in names_by_status(check_note(CODE_NOTE, "en", "deep", 90, "markdown"))
    assert marker_sections(CODE_NOTE)["check"] == []
    assert strip_marker_sections(CODE_NOTE) == CODE_NOTE


def test_quote_rule_follows_lecture_language():
    # A ratio of 0.56 is below the dense window (1.0-2.0) and inside the standard one (0.4-1.2).
    dense = check_note(ZH_NOTE, "zh", "deep", 90, "markdown", "en", quote_density="dense")
    assert status_of(dense, "quote_ratio") == "WARN" and status_of(dense, "quote_share") == "PASS"
    assert status_of(check_note(ZH_NOTE, "zh", "deep", 90, "markdown", "en"), "quote_ratio") == "PASS"
    assert status_of(check_note(ZH_NOTE, "zh", "deep", 90, "markdown"), "quote_ratio") == "PASS"


def zh_note_with_quote(chars):
    """Local helper: 100 CJK characters of prose and one English blockquote of ``chars`` letters.

    The citation stands on the line after the blockquote, so the quote ratio is ``chars / 100``.
    """
    return "## A\n\n" + "利" * 100 + "\n\n> " + "x" * chars + "\n\n(slide 2, 0:40)\n"


@pytest.mark.parametrize("density, window", [
    ("light", (0.15, 0.6)),
    ("standard", (0.4, 1.2)),
    ("dense", (1.0, 2.0)),
])
def test_quote_window_follows_quote_density(density, window):
    def status(chars):
        results = check_note(zh_note_with_quote(chars), "zh", "deep", 90, "markdown", "en", quote_density=density)
        return status_of(results, "quote_ratio")

    lo, hi = (round(x * 100) for x in window)
    assert status(lo) == "PASS" and status(hi) == "PASS"
    assert status(lo - 5) == "WARN" and status(hi + 5) == "WARN"


def test_same_language_share_ignores_quote_density():
    note = "## A\n\n" + " ".join(["word"] * 20) + ' "a quotation of some length here, long enough to count" (0:30).\n'
    for d in ("light", "standard", "dense"):
        assert status_of(check_note(note, "en", "deep", 90, "markdown", "en", quote_density=d), "quote_share") == "PASS"
        # 44 quoted characters over the prose's 130 non-space characters (the citation is left out)
        assert measure_note(note, "en", "deep", 90, "en", quote_density=d)["quote_share"] == {
            "value": 0.34, "window": [0.1, 0.4],
        }
    with pytest.raises(ValueError):
        check_note(note, "en", "deep", 90, "markdown", "en", quote_density="heavy")


def test_h2_count_cap_scales_with_duration():
    def note(n):
        return "\n\n".join(f"## Part {i}\n\nSome prose." for i in range(n)) + "\n"

    # cap = max(16, ceil(16 * duration_min / 90)): 16 at 90 minutes, 32 at 180
    assert status_of(check_note(note(16), "en", "deep", 90, "markdown"), "h2_count") == "PASS"
    assert status_of(check_note(note(17), "en", "deep", 90, "markdown"), "h2_count") == "WARN"
    assert status_of(check_note(note(32), "en", "deep", 180, "markdown"), "h2_count") == "PASS"
    assert status_of(check_note(note(33), "en", "deep", 180, "markdown"), "h2_count") == "WARN"


def test_unknown_goal_raises():
    with pytest.raises(ValueError):
        check_note("## A\n\nText.\n", "en", "fast", 90, "markdown")


def details_of(results, name):
    """Local helper: the details of the result called ``name``."""
    return next(r.details for r in results if r.name == name)


def test_marker_problem_reports_raw_line():
    # line 1 heading; lines 2-8 a fenced block (five code lines); line 9 an unclosed marker
    md = "# Title\n" + F + "python\n" + "x = 1\n" * 5 + F + "\n<!-- tal:check -->\n1. Q?\n"
    assert md.split("\n")[8] == "<!-- tal:check -->"
    results = check_note(md, "en", "deep", 90, "markdown")
    assert details_of(results, "markers") == ["line 9: <!-- tal:check --> is never closed"]



# ---- rules that had no test (Task 21) ---------------------------------------


def test_nested_marker_is_a_problem():
    md = ("## A\n\nText.\n\n<!-- tal:check -->\n<!-- tal:pretest -->\n1. Q?\n"
          "<!-- /tal:pretest -->\n<!-- /tal:check -->\n")
    results = check_note(md, "en", "deep", 90, "markdown")
    assert status_of(results, "markers") == "FAIL"
    assert "line 5: <!-- tal:check --> is not closed before the next marker" in details_of(results, "markers")


def test_unknown_marker_name_is_a_problem():
    md = "## A\n\n<!-- tal:quiz -->\n1. Q?\n<!-- /tal:quiz -->\n"
    assert details_of(check_note(md, "en", "deep", 90, "markdown"), "markers") == [
        "line 3: unknown marker <!-- tal:quiz -->",
        "line 5: unknown marker <!-- /tal:quiz -->",
    ]


def test_close_without_open_is_a_problem():
    md = "## A\n\nText.\n<!-- /tal:check -->\n"
    assert details_of(check_note(md, "en", "deep", 90, "markdown"), "markers") == [
        "line 4: <!-- /tal:check --> closes nothing"
    ]


def test_second_errata_section_is_a_problem():
    section = "<!-- tal:errata -->\n> [!CAUTION]\n> The slide says 5%. (slide 1)\n<!-- /tal:errata -->\n"
    md = "## A\n\nText.\n\n" + section + "\n" + section
    assert details_of(check_note(md, "en", "deep", 90, "markdown"), "markers") == [
        "line 10: second 'errata' section"
    ]


def test_toc_mismatch_on_obsidian_target():
    md = "- [[#Present]]\n- [[#Missing|shown]]\n\n## Present\n\nText.\n"
    results = check_note(md, "en", "deep", 90, "obsidian")
    assert details_of(results, "toc_mismatch") == ["TOC link [[#Missing]] matches no H2"]
    fixed = md.replace("[[#Missing|shown]]", "[[#Present|again]]")
    assert status_of(check_note(fixed, "en", "deep", 90, "obsidian"), "toc_mismatch") == "PASS"


def test_duplicate_heading_slugs_get_suffixes():
    md = ("- [Intro](#intro)\n- [Intro again](#intro-1)\n- [Third](#intro-2)\n\n"
          "## Intro\n\nA.\n\n## Intro\n\nB.\n")
    assert details_of(check_note(md, "en", "deep", 90, "markdown"), "toc_mismatch") == [
        "TOC link #intro-2 matches no H2"
    ]


# ---- headings and length (Task 23) -------------------------------------------


@pytest.mark.parametrize("heading, status", [
    ("## 1. Present value", "FAIL"),
    ("## 2) Discounting", "FAIL"),
    ("## 1.2 Annuities", "FAIL"),
    ("## 1.2.3 Perpetuities", "FAIL"),
    ("## 2008 financial crisis", "PASS"),
    ("## 3 worked examples", "PASS"),
])
def test_numbered_heading_means_an_outline_prefix(heading, status):
    md = f"{heading}\n\nSome prose.\n"
    assert status_of(check_note(md, "en", "deep", 90, "markdown"), "numbered_heading") == status


def test_length_ceiling_has_a_floor():
    def note(words):
        return "## Part\n\n" + " ".join(["word"] * (words - 1)) + "\n"

    assert units(note(300), "en") == 300
    assert status_of(check_note(note(300), "en", "deep", 3, "markdown"), "length") == "PASS"
    assert status_of(check_note(note(500), "en", "deep", 3, "markdown"), "length") == "WARN"
    # the lower bound is unchanged: 26 words a minute for deep
    assert status_of(check_note(note(70), "en", "deep", 3, "markdown"), "length") == "WARN"
    cjk = "## 复利\n\n" + "利" * 700 + "\n"
    assert status_of(check_note(cjk, "zh", "deep", 3, "markdown"), "length") == "PASS"
    assert status_of(check_note(cjk + "利" * 200 + "\n", "zh", "deep", 3, "markdown"), "length") == "WARN"


# ---- quote measures without citations or addresses ---------------------------

YT = "https://www.youtube.com/watch?v=abc"
PANOPTO = "https://example.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=0f3c9a2e-1b4d-4e5f-8a6b-7c8d9e0f1a2b"


def share(md):
    return measure_note(md, "en", "deep", 3.0, "en")["quote_share"]["value"]


def test_quote_measures_are_the_same_before_and_after_cite_link():
    md = resources.files("tutor_any_lecture").joinpath("data", "sample", "explanation.md").read_text(encoding="utf-8")
    plain = measure_note(md, "en", "deep", 3.0, "en")
    assert plain["quote_share"]["value"] == 0.2
    for url in (YT, PANOPTO):
        linked, count = link_times(md, url)
        assert count > 0
        assert measure_note(linked, "en", "deep", 3.0, "en") == plain


def test_quote_share_leaves_citations_and_link_addresses_out():
    inline = "## A\n\nxxxxxxxxxx “abcdefghijklmnopqrst” (0:30)\n"
    assert share(inline) == 0.57
    assert share(link_times(inline, YT)[0]) == 0.57
    block = "## A\n\n" + "x" * 40 + "\n\n> " + "y" * 20 + " (0:30)\n"
    assert share(block) == 0.31
    assert share(link_times(block, YT)[0]) == 0.31
    assert share("## A\n\n[xxxxxxxxxx](https://example.org/a/long/address) “abcdefghijklmnopqrst” (0:30)\n") == 0.57


def test_quote_ratio_leaves_citations_out():
    md = "## A\n\n" + "利" * 100 + "\n\n> " + "x" * 40 + " (slide 2, [0:40](https://www.youtube.com/watch?v=abc&t=40s))\n"
    assert measure_note(md, "zh", "deep", 3.0, "en")["quote_ratio"]["value"] == 0.4


# ---- quotation marks of other languages; short CJK quotes ----------------------


def quotes_in(sentence):
    return [q for q, _ in cited_quotes("## A\n\n" + sentence + "\n")]


@pytest.mark.parametrize("o, c", QUOTE_PAIRS)
def test_quotation_marks_of_other_languages_are_quotes(o, c):
    md = f"## A\n\nThe lecturer put it {o}interest earns interest too{c} plainly.\n"
    assert status_of(check_note(md, "en", "deep", 90, "markdown"), "uncited_quote") == "FAIL"
    cited = md.replace(" plainly.", " plainly (0:30).")
    assert [q for q, _ in cited_quotes(cited)] == ["interest earns interest too"]


def test_low_and_high_marks_pair():
    assert quotes_in("„interest earns interest too“ and „the balance grows each year“ (0:30).") == [
        "interest earns interest too", "the balance grows each year"]


def test_apostrophe_does_not_close_a_single_quote():
    assert quotes_in("‘the lecturer’s rate is fixed now’ (0:30).") == ["the lecturer’s rate is fixed now"]


def test_short_cjk_quote_counts_from_six_characters():
    def uncited(md, lang):
        return status_of(check_note(md, lang, "deep", 90, "markdown"), "uncited_quote")

    assert uncited("## A\n\n" + "利" * 20 + "“复利就是利滚利”。\n", "zh") == "FAIL"
    assert uncited("## A\n\n" + "利" * 20 + "“利滚利效应”。\n", "zh") == "PASS"
    assert uncited('## A\n\nThe phrase "abcdefghijklmn" here.\n', "en") == "PASS"


def test_cited_quote_contexts_give_the_lead_in_and_the_tail():
    md = (
        "## A\n\n> A blockquote of some length here. (0:10)\n\n"
        'It rose. Then a student asked: "does the rate change every year" in class (0:30); later.\n'
    )
    contexts = cited_quote_contexts(md)
    assert [q for q, _, _, _ in contexts] == [q for q, _ in cited_quotes(md)][1:]
    ((quote, cits, lead_in, tail),) = contexts
    assert quote == "does the rate change every year" and [c.raw for c in cits] == ["(0:30)"]
    assert lead_in == " Then a student asked: " and tail == " in class (0:30)"


# ---- scripts the checks cannot split into words --------------------------------

# synthetic: "compound interest is interest that comes from interest"
THAI = "ดอกเบี้ยทบต้นคือดอกเบี้ยที่เกิดจากดอกเบี้ย"
THAI_NOTE = "## ดอกเบี้ย\n\n" + (THAI + " ") * 40 + "(0:30)\n"


def test_word_rules_are_not_applied_to_thai():
    results = check_note(THAI_NOTE, "th", "deep", 3.0, "markdown", "th")
    for name in ("length", "thin_section", "long_paragraph"):
        assert status_of(results, name) == "WARN", name
        assert details_of(results, name) == ["not applied for this language"], name
    unknown = check_note(THAI_NOTE, "th", "deep", None, "markdown", "th")
    assert details_of(unknown, "length") == ["skipped: duration unknown"]
    assert status_of(unknown, "thin_section") == "WARN"
    assert measure_note(THAI_NOTE, "th", "deep", 3.0, "th")["length"] == {
        "unit": "words", "total": None, "per_min": None, "window": None}


# ---- details blocks and math forms -----------------------------------------------


def sample_note():
    return resources.files("tutor_any_lecture").joinpath("data", "sample", "explanation.md").read_text(encoding="utf-8")


def details_shape(md):
    results = check_note(md, "en", "deep", 90, "markdown")
    return status_of(results, "details_shape"), details_of(results, "details_shape")


def test_details_must_be_balanced_and_have_a_summary():
    assert details_shape("## A\n\nText.\n\n<details>\nAnswer.\n") == (
        "FAIL", ["line 5: <details> has no <summary>", "line 5: <details> is never closed"])
    assert details_shape("## A\n\nText.\n</details>\n") == ("FAIL", ["line 4: </details> closes nothing"])
    assert details_shape("## A\n\n```\nx\n```\n\n<details>\nAnswer.\n</details>\n") == (
        "FAIL", ["line 7: <details> has no <summary>"])
    assert details_shape("## A\n\n<details>\n\n<summary>Answer</summary>\n\nYes.\n\n</details>\n") == ("PASS", [])
    assert details_shape("## A\n\n```html\n<details>\nAnswer.\n```\n") == ("PASS", [])
    assert details_shape(sample_note()) == ("PASS", [])


def test_details_shape_comes_after_details_missing():
    names = [r.name for r in check_note(sample_note(), "en", "deep", 90, "markdown")]
    assert names[names.index("details_missing") + 1] == "details_shape"


MATH_NOTE = "## A\n\nThe rate \\(r\\) grows.\n\n\\[ x^2 \\]\n\nIt costs $5 today.\n\nFine: $r$, $$x$$ and \\$5.\n"


def test_math_forms_github_does_not_render_warn():
    def math_form(md):
        results = check_note(md, "en", "deep", 90, "markdown")
        return status_of(results, "math_form"), details_of(results, "math_form")

    three = [
        "line 3: \\( … \\) does not render on GitHub: write $…$",
        "line 5: \\[ … \\] does not render on GitHub: write $$…$$",
        "line 7: unescaped $ outside math: write \\$ for a currency sign",
    ]
    assert math_form(MATH_NOTE) == ("WARN", three)
    assert math_form(MATH_NOTE + "$$\nx\n$$\n\nIt costs $5.\n") == (
        "WARN", three + ["line 14: unescaped $ outside math: write \\$ for a currency sign"])
    assert math_form(sample_note()) == ("PASS", [])
    names = [r.name for r in check_note(MATH_NOTE, "en", "deep", 90, "markdown")]
    assert names[names.index("bullets") + 1] == "math_form"


def test_quote_densities_have_one_source():
    from tutor_any_lecture import notecheck, plan

    assert notecheck.QUOTE_DENSITIES is plan.QUOTE_DENSITIES
    assert tuple(notecheck.THRESHOLDS["cross_language_quote_ratio"]) == plan.QUOTE_DENSITIES
