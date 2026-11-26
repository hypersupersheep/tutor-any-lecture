import json
import os
import re
import shutil
from pathlib import Path
from importlib import resources

import pytest

from tutor_any_lecture import citations, doctor, notecheck, textstats
from tutor_any_lecture.cli import main
from tutor_any_lecture.selftest import run_selftest

SAMPLE_FILES = [
    "lecture.vtt", "slides.pdf", "plan.json", "explanation.md",
    "items.json", "cards.json", "map.json",
]
GATE_ENTRIES = ["citations", "coverage", "items", "cards", "map"]


def test_selftest_passes():
    assert run_selftest()["ok"] is True


def test_selftest_keep_leaves_unit(tmp_path, tmp_cfg):
    unit = tmp_path / "unit"
    assert main(["selftest", "--keep", str(unit)]) == 0
    assert (unit / "verify.json").exists()
    assert (unit / "explanation.md").exists()


def test_sample_in_package():
    sample = resources.files("tutor_any_lecture").joinpath("data", "sample")
    assert [n for n in SAMPLE_FILES if not sample.joinpath(n).is_file()] == []


def test_sample_gate_entries_pass(tmp_path):
    unit = tmp_path / "课程 资料" / "unit"
    result = run_selftest(unit)
    assert result["ok"] is True
    assert [s["name"] for s in result["steps"]] == [
        "import", "slides", "items assign", "cards export", "map mermaid", "verify",
    ]
    checks = json.loads((unit / "verify.json").read_text(encoding="utf-8"))["checks"]
    status = {c["name"]: c["status"] for c in checks}
    assert [n for n in GATE_ENTRIES if status[n] != "PASS"] == []


def test_selftest_refuses_nonempty_dir(tmp_path):
    mine = tmp_path / "plan.json"
    mine.write_text("mine\n", encoding="utf-8", newline="\n")
    assert main(["selftest", "--keep", str(tmp_path)]) == 3
    assert mine.read_text(encoding="utf-8") == "mine\n"
    assert not (tmp_path / "sources").exists()


# ---- the sample models good work ----

SAMPLE_TOPICS = ["Simple and compound interest", "Growth over n years", "Compounding frequency"]
# The bundled samples by note language, and each one's folder under data/.
SAMPLES = {"en": "sample"}
SOURCE_NAMES = ("lecture.vtt", "slides.pdf")


def sample_text(sample: str, name: str) -> str:
    """A root file of one sample; lecture.vtt and slides.pdf always come from data/sample/."""
    folder = "sample" if name in SOURCE_NAMES else SAMPLES[sample]
    return resources.files("tutor_any_lecture").joinpath("data", folder, name).read_text(encoding="utf-8")


def sample_json(name: str, sample: str = "en"):
    return json.loads(sample_text(sample, name))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """sample -> (unit folder, verify.json) of one selftest run; each sample is generated once."""
    cache: dict = {}

    def build(sample: str):
        if sample not in cache:
            unit = tmp_path_factory.mktemp(f"sample-{sample}") / "unit"
            assert run_selftest(unit)["ok"] is True
            cache[sample] = unit, json.loads((unit / "verify.json").read_text(encoding="utf-8"))
        return cache[sample]

    return build


def test_sample_note_has_one_h2_per_topic(tmp_path):
    unit = tmp_path / "unit"
    assert run_selftest(unit)["ok"] is True
    md = (unit / "explanation.md").read_text(encoding="utf-8")
    h2 = [line[3:].strip() for line in md.split("\n") if line.startswith("## ")]
    assert h2 == ["Pretest", *SAMPLE_TOPICS, "Not covered and errata"]
    assert [s["title"] for s in sample_json("plan.json")["sections"]] == SAMPLE_TOPICS


# ---- S1. a fourteen-minute lecture on the same slides ----

VTT_TIME = r"(\d\d):(\d\d):(\d\d)\.(\d\d\d)"
CUE_RE = re.compile(rf"^{VTT_TIME} --> {VTT_TIME}$", re.MULTILINE)


def seconds(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def test_sample_lecture_is_fourteen_minutes():
    vtt = sample_text("en", "lecture.vtt")
    lines = [line for line in vtt.split("\n") if "-->" in line]
    assert lines[0].startswith("00:00:00.000 ")
    assert lines[-1].endswith(" 00:14:00.000")
    spans = [(seconds(*c[:4]), seconds(*c[4:])) for c in CUE_RE.findall(vtt)]
    assert len(spans) == len(lines)
    assert [i for i, (a, b) in enumerate(spans) if not 6 <= b - a <= 12] == []
    assert [i for i in range(1, len(spans)) if spans[i][0] != spans[i - 1][1]] == []
    assert "effect of annual rate" in vtt
    for sample in SAMPLES:
        assert sample_json("plan.json", sample)["duration_s"] == 840


# ---- S2. the notes sit in the middle of their length windows ----


@pytest.mark.parametrize("sample", SAMPLES)
def test_samples_sit_mid_window(built, sample):
    measures = built(sample)[1]["measures"]
    lo, hi = (w * measures["minutes"] for w in measures["length"]["window"])
    assert lo + 0.3 * (hi - lo) <= measures["length"]["total"] <= lo + 0.7 * (hi - lo)


# ---- S3. the English note shows every element of the contract ----


def h2_sections(md: str) -> dict[str, str]:
    """Each H2's text, by its heading, up to the next H2."""
    out: dict[str, str] = {}
    heading = None
    for line in md.split("\n"):
        if line.startswith("## "):
            heading = line[3:].strip()
            out[heading] = ""
        elif heading is not None:
            out[heading] += line + "\n"
    return out


def next_nonblank(lines: list[str], i: int) -> str:
    return next(x for x in lines[i + 1:] if x.strip())


def blockquotes(lines: list[str]) -> list[list[str]]:
    """Maximal runs of '>' lines."""
    out: list[list[str]] = []
    run: list[str] = []
    for line in lines + [""]:
        if line.startswith(">"):
            run.append(line)
        elif run:
            out.append(run)
            run = []
    return out


QUOTE_RE = re.compile(r"\"([^\"\n]+)\"|“([^”\n]+)”")


def quotes_of(text: str) -> list[str]:
    return [a or b for a, b in QUOTE_RE.findall(text)]


def assert_body_elements(prose: str, derivation: str, why: str, answer: str, example: str) -> None:
    """The body elements that S3 and S9 share, in the note language's forms."""
    lines = prose.split("\n")
    for callout in ("> [!NOTE]", "> [!IMPORTANT]", "> [!WARNING]"):
        assert callout in lines, callout
    plain = [b for b in blockquotes(lines) if not b[0].startswith("> [!")]
    assert len(plain) == 1
    assert citations.parse(plain[0][-1]) != []
    derivations = [i for i, line in enumerate(lines) if line.startswith("### " + derivation)]
    assert len(derivations) == 1
    end = next((i for i in range(derivations[0] + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    prompts = [i for i in range(derivations[0], end) if re.match(why, lines[i])]
    assert len(prompts) == 1
    assert next_nonblank(lines, prompts[0]) == f"<details><summary>{answer}</summary>"
    assert [line for line in lines if line.startswith("### " + example)] != []
    assert re.search(r"\$\$[^\n]*\\tag\{1\}[^\n]*\$\$", prose)
    quotes = quotes_of(prose)
    assert [q for q in quotes if re.search(r"\[[^\]]+\]", q)] != []
    assert [q for q in quotes if "…" in q] != []


def errata_rows(md: str) -> list[list[str]]:
    """The data rows of the tal:errata table, as stripped cells."""
    body = "\n".join(notecheck.marker_sections(md)["errata"])
    rows = [line.lstrip("> ").strip() for line in body.split("\n") if line.lstrip("> ").startswith("|")]
    return [[c.strip() for c in row.strip("|").split("|")] for row in rows[2:]]


def test_english_sample_shows_every_contract_element():
    md = sample_text("en", "explanation.md")
    h2 = [line[3:].strip() for line in md.split("\n") if line.startswith("## ")]
    assert h2 == ["Pretest", *SAMPLE_TOPICS, "Not covered and errata"]
    assert_body_elements(
        notecheck.strip_marker_sections(md), "Derivation:", r"^\*Why .+\?\*$", "Answer", "Worked example:"
    )
    bodies = notecheck.marker_sections(md)
    assert len(bodies["not-covered"]) == 1
    assert re.search(r"^- \d+:\d\d–\d+:\d\d: ", bodies["not-covered"][0], re.MULTILINE)
    assert len(bodies["errata"]) == 1
    errata = bodies["errata"][0].split("\n")
    for line in ("> [!CAUTION]", "> Transcript and slide errata", "> | Time | Heard | Should be |"):
        assert line in errata, line
    rows = errata_rows(md)
    assert len(rows) >= 2
    assert [r for r in rows if r[1] == "effect of annual rate"] != []
    assert [r for r in rows if r[2].endswith("(lecturer's slip, corrected)")] != []


# ---- S4. pretest answers state the result and its idea ----

SENTENCE_END_RE = re.compile(r"[.!?。！？](?=\s|$)")
DETAILS_RE = re.compile(r"<details><summary>[^<\n]*</summary>(.*?)</details>", re.DOTALL)


def without_citations(text: str) -> str:
    for c in citations.parse(text):
        text = text.replace(c.raw, " ")
    return text


@pytest.mark.parametrize("sample", SAMPLES)
def test_pretest_answers_state_result_and_idea(sample):
    pretest = notecheck.marker_sections(sample_text(sample, "explanation.md"))["pretest"]
    assert len(pretest) == 1
    answers = [without_citations(a).strip() for a in DETAILS_RE.findall(pretest[0])]
    assert len(answers) == len(sample_json("plan.json", sample)["tracked"])
    assert [a for a in answers if len(SENTENCE_END_RE.findall(a)) > 2] == []
    assert [a for a in answers if "=" in a] == []


# ---- S5. the worked example fades ----


@pytest.mark.parametrize("sample", SAMPLES)
def test_growth_section_fades_its_worked_example(sample):
    practice = {it["id"]: it for it in sample_json("items.json", sample)["practice"]}
    faded, setup = practice["faded-growth"], practice["setup-growth"]
    for item in (faded, setup):
        assert (item["kind"], item["concept"]) == ("apply", "growth_formula")
    title = sample_json("plan.json", sample)["sections"][1]["title"]
    checks = notecheck.marker_sections(h2_sections(sample_text(sample, "explanation.md"))[title])["check"]
    assert len(checks) == 1
    assert 0 <= checks[0].find(faded["prompt"]) < checks[0].find(setup["prompt"])
    assert len(faded["prompt"]) > len(setup["prompt"])


# ---- S6. real paragraphs ----

LAST_H2 = {"en": "Not covered and errata", "zh": "未讲到的内容和勘误"}
PARAGRAPH_UNITS = {"en": (40, 150), "zh": (60, 250)}
NOT_A_PARAGRAPH_RE = re.compile(r"^(#|\*\(|>|<|\$\$|\||- |\d+\. )")


def paragraphs(md: str, sample: str) -> list[list[str]]:
    """The prose paragraphs from the first topic H2 to the last H2, outside <details> blocks."""
    lines = DETAILS_RE.sub("", notecheck.strip_marker_sections(md)).split("\n")
    first = lines.index("## " + sample_json("plan.json", sample)["sections"][0]["title"])
    lines = lines[first:lines.index("## " + LAST_H2[sample])]
    blocks: list[list[str]] = []
    block: list[str] = []
    for line in lines + [""]:
        if line.strip():
            block.append(line)
        elif block:
            blocks.append(block)
            block = []
    return [
        b for b in blocks
        if not NOT_A_PARAGRAPH_RE.match(b[0]) and not (len(b) == 1 and re.fullmatch(r"\*[^*]+\*", b[0]))
    ]


@pytest.mark.parametrize("sample", SAMPLES)
def test_sample_paragraphs_are_real_paragraphs(sample):
    found = paragraphs(sample_text(sample, "explanation.md"), sample)
    assert len(found) >= 3
    lo, hi = PARAGRAPH_UNITS[sample]
    for para in found:
        assert [line for line in para[1:] if not line.startswith("$$")] == [], para[0][:40]
        assert lo <= textstats.units("\n".join(para), sample) <= hi, para[0][:40]


# ---- S7. errata come from the transcript ----


@pytest.mark.parametrize("sample", SAMPLES)
def test_sample_errata_rows_come_from_the_transcript(sample):
    vtt = sample_text(sample, "lecture.vtt").casefold()
    rows = errata_rows(sample_text(sample, "explanation.md"))
    assert len(rows) >= 2
    assert [r for r in rows if r[1].strip().casefold() not in vtt] == []


def test_sample_gate_has_no_warnings(tmp_path):
    unit = tmp_path / "unit"
    assert run_selftest(unit)["ok"] is True
    result = json.loads((unit / "verify.json").read_text(encoding="utf-8"))
    assert [(c["name"], c["details"]) for c in result["checks"] if c["status"] != "PASS"] == []
    assert result["warnings"] == 0


def test_sample_effective_rate_has_a_numeric_variant():
    answers = [item["answer"] for item in sample_json("items.json")["tracked"]["effective_rate"].values()]
    assert [a for a in answers if re.search(r"\d+(?:\.\d+)?%", a)] != []


def test_sample_variants_are_parallel():
    """A, B and C of each concept share a kind, and all ask for a number or none does."""
    for cid, variants in sample_json("items.json")["tracked"].items():
        assert len({v["kind"] for v in variants.values()}) == 1, cid
        # a digit in the answer once its citations are removed: the item asks for a number
        numeric = {bool(re.search(r"\d", re.sub(r"\([^)]*\)", "", v["answer"]))) for v in variants.values()}
        assert len(numeric) == 1, cid


# ---- failure paths and cleanup ----

STEP_NAMES = ["import", "slides", "items assign", "cards export", "map mermaid", "verify"]


def fail_cards_export(monkeypatch, seen: list | None = None) -> None:
    """Make the "cards export" step raise RuntimeError; record the unit folder it was given."""

    def boom(unit):
        if seen is not None:
            seen.append(unit)
        raise RuntimeError("boom")

    monkeypatch.setattr("tutor_any_lecture.selftest.export_tsv", boom)


def test_selftest_stops_at_the_first_failing_step(monkeypatch, tmp_path):
    fail_cards_export(monkeypatch)
    result = run_selftest(tmp_path / "unit")
    assert result["ok"] is False
    assert [s["name"] for s in result["steps"]] == STEP_NAMES[:4]
    assert [s["ok"] for s in result["steps"]] == [True, True, True, False]
    assert not (tmp_path / "unit" / "verify.json").exists()


def test_selftest_reports_the_exception_name(monkeypatch, tmp_path, tmp_cfg):
    fail_cards_export(monkeypatch)
    assert run_selftest(tmp_path / "unit")["steps"][-1]["detail"] == "RuntimeError: boom"
    assert main(["selftest"]) == 1


def test_selftest_removes_its_folder_after_a_failure(monkeypatch):
    seen: list = []
    fail_cards_export(monkeypatch, seen)
    assert run_selftest()["ok"] is False
    assert len(seen) == 1
    assert not seen[0].exists() and not seen[0].parent.exists()


def test_selftest_ignores_cleanup_errors(monkeypatch):
    """The temporary folder cannot be removed: run_selftest still returns its result."""
    refused: list[Path] = []

    def rmtree(path, *args, **kwargs):
        refused.append(Path(path))
        raise PermissionError(13, "Permission denied", os.fspath(path))

    monkeypatch.setattr("tutor_any_lecture.selftest.rmtree", rmtree)
    result = run_selftest()
    # The cleanup was attempted, once, on the folder the run used, and it failed.
    assert len(refused) == 1 and (refused[0] / "unit" / "verify.json").is_file()
    shutil.rmtree(refused[0])
    assert result["ok"] is True
    assert [s["name"] for s in result["steps"]] == STEP_NAMES


# ---- the doctor line ----


def doctor_report(ready, failing=()):
    """A doctor report: python ok, and each (name, fix) in ``failing`` not ok."""
    checks = [{"name": "python", "ok": True, "detail": "3.12", "fix": ""}]
    checks += [{"name": name, "ok": False, "detail": "not found", "fix": fix} for name, fix in failing]
    return {"ready": ready, "checks": checks, "version": "0.0.0"}


@pytest.mark.parametrize(
    "report, line",
    [
        pytest.param(
            doctor_report(False, [("ffmpeg", "Reinstall tutor-any-lecture."), ("browser", "Optional: install Chrome.")]),
            "doctor: not ready; required not ok: ffmpeg; optional not ok: browser",
            id="required-and-optional",
        ),
        pytest.param(doctor_report(True), "doctor: ready", id="all-ok"),
    ],
)
def test_selftest_prints_one_doctor_line(monkeypatch, tmp_path, capsys, report, line):
    monkeypatch.setattr(doctor, "run_doctor", lambda: report)
    unit = tmp_path / "unit"
    assert main(["selftest", "--keep", str(unit)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [ln for ln in lines if ln.startswith("doctor:")] == [line]
    i = lines.index(line)
    assert lines[i - 1].startswith("ok    verify: ")
    assert lines[i + 1] == f"unit folder: {unit}"


def test_selftest_doctor_line_keeps_the_failing_exit_code(monkeypatch, capsys):
    fail_cards_export(monkeypatch)
    monkeypatch.setattr(doctor, "run_doctor", lambda: doctor_report(True))
    assert main(["selftest"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "doctor: ready" in lines
    assert lines[-1] == "doctor: ready"
