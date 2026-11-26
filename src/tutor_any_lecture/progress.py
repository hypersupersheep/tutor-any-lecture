"""The progress log: one JSON line per quiz attempt, unit scores, gain, retention, the due list and the page."""

from __future__ import annotations

import dataclasses
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from . import items as itembank
from .items import ASSIGNED_PHASES, OPTIONAL_PHASES, find_item, load_items
from .plan import load_plan, safe_name
from .progress_svg import ChartRow, write_chart
from .unit import UnitPaths, find_unit

PHASES = ("pre", "post", "d1", "d7", "d21", "practice")
SCORES = (0, 0.5, 1)
CONFIDENCES = (1, 2, 3)
EXPOSURES = ("none", "attended", "watched", "unknown")

# Phases shown on the page, in the sentence and in the chart.
TRACKED_PHASES = ("pre", "post", "d7")
# Review phases: days after the post quiz is complete, and whether the review is optional.
REVIEWS = (("d1", 1, True), ("d7", 7, False), ("d21", 21, True))
# The optional d21 is no longer offered this many days after it is due.
D21_LAPSE_DAYS = 14
# The order of entries due on the same day: the post quiz first, then the reviews.
DUE_ORDER = {"post": 0, **{phase: n for n, (phase, _, _) in enumerate(REVIEWS, start=1)}}
# The page's language when neither the flag nor a unit's plan names one with a table.
DEFAULT_LANGUAGE = "en"
# How much of an item's prompt (and of the learner's answer) the confident-but-wrong list shows.
PROMPT_SHOWN = 60


@dataclass
class Attempt:
    ts: str
    course: str
    unit: str
    item_id: str
    variant: str | None
    concept: str
    phase: str
    score: float
    confidence: int
    citation: str
    exposure: str
    # The item's prompt when it was asked; None in lines logged before prompts were kept.
    prompt: str | None = None
    # The learner's answer as given, when the agent passed one.
    answer: str | None = None
    # The concepts this attempt's phase holds, sorted; None for practice and in lines
    # logged before it was kept (then one attempt completes a phase, as it did then).
    assigned: list[str] | None = None


ATTEMPT_FIELDS = tuple(f.name for f in dataclasses.fields(Attempt))
# The keys every log line has; the later ones may be absent from lines written before them.
REQUIRED_KEYS = ATTEMPT_FIELDS[: ATTEMPT_FIELDS.index("prompt")]


def _progress_dir(workspace: Path) -> Path:
    return Path(workspace) / "progress"


def _course_file(workspace: Path, course: str, suffix: str) -> Path:
    """``<workspace>/progress/<course><suffix>``; PlanError when ``course`` is not a safe folder name."""
    return _progress_dir(workspace) / f"{safe_name(course, 'course')}{suffix}"


def log_path(course: str, workspace: Path) -> Path:
    """The course's log file, ``<workspace>/progress/<course>.jsonl``."""
    return _course_file(workspace, course, ".jsonl")


def log_attempt(a: Attempt, workspace: Path) -> Path:
    """Append ``a`` as one JSON line to ``<workspace>/progress/<course>.jsonl`` and return that path."""
    # Check every value set before touching the disk, so a bad attempt leaves no trace.
    # bool is a subclass of int (True == 1) and 2.0 == 2, so the types are checked as well.
    for name, value in (("score", a.score), ("confidence", a.confidence)):
        if isinstance(value, bool):
            raise ValueError(f"attempt {name} must be a number, not {value!r}")
    if not isinstance(a.confidence, int):
        raise ValueError(f"attempt confidence must be an integer, got {a.confidence!r}")
    for name, value, allowed in (
        ("phase", a.phase, PHASES),
        ("score", a.score, SCORES),
        ("confidence", a.confidence, CONFIDENCES),
        ("exposure", a.exposure, EXPOSURES),
    ):
        if value not in allowed:
            raise ValueError(f"attempt {name} must be one of {', '.join(map(str, allowed))}, got {value!r}")
    path = _course_file(workspace, a.course, ".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(dataclasses.asdict(a), ensure_ascii=False) + "\n")
    return path


def load_attempts(course: str, workspace: Path) -> list[Attempt]:
    """The attempts of ``<workspace>/progress/<course>.jsonl`` in file order; a missing file gives []."""
    path = _course_file(workspace, course, ".jsonl")
    if not path.exists():
        return []
    # Split on "\n" only: str.splitlines() also breaks at U+2028/U+2029/U+0085, which
    # json.dumps(ensure_ascii=False) leaves raw inside string values.
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        if not line.strip():
            continue
        parsed = _parse_line(line)
        if isinstance(parsed, Attempt):
            out.append(parsed)
        else:
            # Not the warnings module: a skipped line must not stop a command run with -W error.
            print(f"warning: {path}: line {n} skipped: {parsed}", file=sys.stderr)
    return out


def _is_string(v) -> bool:
    return isinstance(v, str)


def _is_iso_time(v) -> bool:
    if not isinstance(v, str):
        return False
    try:
        datetime.fromisoformat(v)
    except ValueError:
        return False
    return True


def _is_number_in(allowed):
    # bool is a subclass of int (True == 1), so it is refused by name.
    return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v in allowed


def _is_optional_string(v) -> bool:
    return v is None or isinstance(v, str)


# The test each field's value must pass, in field order.
_FIELD_TESTS = {
    "ts": _is_iso_time,
    "course": _is_string,
    "unit": _is_string,
    "item_id": _is_string,
    "variant": lambda v: v is None or v in ("A", "B", "C", "D", "E"),
    "concept": _is_string,
    "phase": lambda v: isinstance(v, str) and v in PHASES,
    "score": _is_number_in(SCORES),
    "confidence": lambda v: isinstance(v, int) and not isinstance(v, bool) and v in CONFIDENCES,
    "citation": _is_string,
    "exposure": lambda v: isinstance(v, str) and v in EXPOSURES,
    "prompt": _is_optional_string,
    "answer": _is_optional_string,
    "assigned": lambda v: v is None or (isinstance(v, list) and all(isinstance(x, str) for x in v)),
}


def _parse_line(line: str) -> Attempt | str:
    """The attempt one log line holds, or the reason it cannot be read.

    Keys the dataclass does not know are ignored, so a log written by a later version loads.
    """
    try:
        obj = json.loads(line)
    except ValueError:
        return "not valid JSON"
    if not isinstance(obj, dict):
        return "not a JSON object"
    missing = [k for k in REQUIRED_KEYS if k not in obj]
    if missing:
        return f"missing {', '.join(missing)}"
    values = {k: obj.get(k) for k in ATTEMPT_FIELDS}
    for field in ATTEMPT_FIELDS:
        if not _FIELD_TESTS[field](values[field]):
            return f"bad value for {field}: {values[field]!r}"
    return Attempt(**values)


def _stamp(day: date | None) -> str:
    """The local time now, with its UTC offset, moved to ``day`` when one is given."""
    now = datetime.now()
    # A naive local time made aware by astimezone() gets the offset in force on that day.
    moment = datetime.combine(day if day is not None else now.date(), now.time())
    return moment.astimezone().isoformat(timespec="seconds")


def _own_phase(item, paths: UnitPaths) -> tuple[str, dict | None]:
    """The one phase ``item`` is asked in, and the unit's assignment when it was read for that.

    Practice items belong to practice, D to d1 and E to d21; A, B and C belong to the phase
    of pre, post and d7 whose letter in assignment.json is the item's variant.
    """
    if item.variant is None:
        return "practice", None
    for phase, letter in OPTIONAL_PHASES.items():
        if item.variant == letter:
            return phase, None
    if not paths.assignment.exists():
        raise FileNotFoundError(
            f"{paths.assignment} not found: run `tutor-any-lecture items assign --unit DIR` first"
        )
    # Read and checked as `items next` and `items assign` read and check it.
    assignment = itembank._read_assignment(paths.assignment)
    itembank._check_assignment(assignment, ASSIGNED_PHASES)
    letters = assignment["concepts"].get(item.concept)
    for phase in ASSIGNED_PHASES:
        if letters is not None and letters[phase] == item.variant:
            return phase, assignment
    raise ValueError(f"item {item.id} has no phase in assignment.json")


def _assigned(phase: str, items: dict, assignment: dict | None) -> list[str] | None:
    """The concepts ``phase`` holds, sorted: assignment.json's for pre, post and d7, the
    tracked concepts with a D (d1) or E (d21) variant, and None for practice."""
    if phase in ASSIGNED_PHASES:
        return sorted(assignment["concepts"])
    if phase in OPTIONAL_PHASES:
        letter = OPTIONAL_PHASES[phase]
        return sorted(cid for cid, variants in items["tracked"].items() if letter in variants)
    return None


def log_from_unit(
    unit: Path,
    item_id: str,
    phase: str,
    score: float,
    confidence: int,
    exposure: str,
    workspace: Path,
    day: date | None = None,
    answer: str | None = None,
) -> Attempt:
    """Log one attempt at ``item_id``; course, unit, variant, concept and citation come from the unit's files.

    ``day`` is the day the answer was given (default: today), for an answer logged later.
    ``answer`` is the learner's answer, kept without surrounding whitespace (empty: None).
    An item given a phase other than its own raises ValueError and writes nothing.
    """
    paths = UnitPaths(unit)
    plan = load_plan(paths.plan)
    items = load_items(paths.items)
    item = find_item(items, item_id)
    own, assignment = _own_phase(item, paths)
    if phase != own:
        raise ValueError(f"item {item.id} belongs to phase {own}, not {phase}")
    answer = answer.strip() if answer is not None else None
    a = Attempt(
        ts=_stamp(day),
        course=plan.course,
        unit=plan.unit,
        item_id=item.id,
        variant=item.variant,
        concept=item.concept,
        phase=phase,
        score=score,
        confidence=confidence,
        citation=item.citation,
        exposure=exposure,
        prompt=item.prompt,
        answer=answer or None,
        assigned=_assigned(phase, items, assignment),
    )
    log_attempt(a, workspace)
    return a


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values)


def _phase_means(attempts) -> dict[str, float]:
    """Mean score per phase over every attempt, phases in order of first appearance."""
    by_phase: dict[str, list[float]] = {}
    for a in attempts:
        by_phase.setdefault(a.phase, []).append(a.score)
    return {phase: _mean(scores) for phase, scores in by_phase.items()}


def _day(a: Attempt) -> date:
    """The attempt's day: the date as written in ts, no timezone conversion."""
    return datetime.fromisoformat(a.ts).date()


@dataclass
class _PhaseState:
    """What the log holds for one unit and one phase."""

    first_days: dict[str, date]  # each concept with an attempt: its first day in the phase
    assigned: list[str] | None  # the concepts the phase holds, from the newest line that says

    def _expected(self) -> list[str]:
        return sorted(set(self.assigned or ()))

    @property
    def remaining(self) -> list[str]:
        """The assigned concepts with no attempt yet, sorted."""
        return [c for c in self._expected() if c not in self.first_days]

    @property
    def complete(self) -> bool:
        # With no line naming the phase's concepts (a log written before they were kept),
        # one attempt completes the phase, as it did then.
        return not self.remaining

    @property
    def size(self) -> int:
        return len(self._expected())

    @property
    def answered(self) -> int:
        return self.size - len(self.remaining)

    def completion_day(self) -> date:
        """The latest of the assigned concepts' first days; the phase's first day without them."""
        expected = self._expected()
        if not expected:
            return min(self.first_days.values())
        return max(self.first_days[c] for c in expected)


def _phase_states(attempts) -> dict[str, dict[str, _PhaseState]]:
    """For each unit, in order of first appearance, the state of every phase it has an attempt in, practice aside."""
    states: dict[str, dict[str, _PhaseState]] = {}
    for a in attempts:
        if a.phase == "practice":
            continue
        st = states.setdefault(a.unit, {}).setdefault(a.phase, _PhaseState({}, None))
        day = _day(a)
        if a.concept not in st.first_days or day < st.first_days[a.concept]:
            st.first_days[a.concept] = day
        if a.assigned is not None:  # file order: the newest line that names them wins
            st.assigned = a.assigned
    return states


def _partial(states, unit: str, phase: str) -> bool:
    st = states.get(unit, {}).get(phase)
    return st is not None and not st.complete


def unit_scores(attempts) -> dict[str, dict[str, float]]:
    """For each unit, the mean score of each complete phase: the mean over concepts of each
    concept's mean there. Practice attempts and partial phases are left out, and so is a unit
    with no complete phase.
    """
    states = _phase_states(attempts)
    by_unit: dict[str, dict[str, dict[str, list[float]]]] = {}
    for a in attempts:
        if a.phase != "practice":
            by_unit.setdefault(a.unit, {}).setdefault(a.phase, {}).setdefault(a.concept, []).append(a.score)
    out: dict[str, dict[str, float]] = {}
    for unit, phases in by_unit.items():
        means = {
            phase: _mean(_mean(scores) for scores in concepts.values())
            for phase, concepts in phases.items()
            if states[unit][phase].complete
        }
        if means:
            out[unit] = means
    return out


def paired_scores(attempts, first: str, second: str) -> dict[str, dict[str, float]]:
    """For each unit, the mean ``first`` and ``second`` scores over the concepts attempted in both phases.

    A concept's score in a phase is the mean of its attempts there. A unit with no such concept,
    or with either phase partial, is left out.
    """
    states = _phase_states(attempts)
    by_unit: dict[str, dict[str, dict[str, list[float]]]] = {}
    for a in attempts:
        if a.phase in (first, second):
            by_unit.setdefault(a.unit, {}).setdefault(a.concept, {}).setdefault(a.phase, []).append(a.score)
    out: dict[str, dict[str, float]] = {}
    for unit, concepts in by_unit.items():
        if _partial(states, unit, first) or _partial(states, unit, second):
            continue
        both = [phases for phases in concepts.values() if first in phases and second in phases]
        if both:
            out[unit] = {phase: _mean(_mean(c[phase]) for c in both) for phase in (first, second)}
    return out


def _gain_means(scores) -> tuple[float, float] | None:
    """(mean pre, mean post) over the units with pre and post and pre < 1; None when there is none."""
    units = [s for s in scores.values() if "pre" in s and "post" in s and s["pre"] < 1]
    if not units:
        return None
    return _mean(s["pre"] for s in units), _mean(s["post"] for s in units)


def normalized_gain(scores) -> float | None:
    """(mean post - mean pre) / (1 - mean pre) over the units with pre and post and pre < 1.

    ``scores`` is ``paired_scores(attempts, "pre", "post")``, so each unit compares the same concepts.
    """
    means = _gain_means(scores)
    if means is None:
        return None
    pre, post = means
    return (post - pre) / (1 - pre)


def _retention_means(scores) -> tuple[float, float] | None:
    """(mean post, mean d7) over the units with both; None when none qualifies or the mean post is 0."""
    units = [s for s in scores.values() if "post" in s and "d7" in s]
    if not units:
        return None
    post = _mean(s["post"] for s in units)
    if post == 0:
        return None
    return post, _mean(s["d7"] for s in units)


def retention(scores) -> float | None:
    """mean d7 / mean post over the units with both; None when none qualifies or the mean post is 0.

    ``scores`` is ``paired_scores(attempts, "post", "d7")``, so each unit compares the same concepts.
    """
    means = _retention_means(scores)
    if means is None:
        return None
    post, d7 = means
    return d7 / post


def _due_entry(unit: str, phase: str, when: date, optional: bool, st: _PhaseState | None) -> dict:
    """One due entry; a partial phase says how many concepts are answered and which remain."""
    partial = st is not None and not st.complete
    return {
        "unit": unit,
        "phase": phase,
        "due": when.isoformat(),
        "optional": optional,
        "answered": st.answered if partial else 0,
        "remaining": st.remaining if partial else None,
    }


def due(attempts, today: date) -> list[dict]:
    """What is due by ``today`` and not yet complete.

    A phase is complete when each of its assigned concepts has an attempt (for lines that
    name none, after one attempt). The post quiz is listed until it is complete, due on the
    unit's first pre day (its first post day without a pretest). Reviews d1, d7 and d21 are
    due 1, 7 and 21 days after the day the post quiz became complete. The optional d1
    lapses once the unit's d7 is due or started; the optional d21, 14 days after it is due.
    """
    out = []
    for unit, phases in _phase_states(attempts).items():
        post = phases.get("post")
        if post is None or not post.complete:
            # Due on the first pre day, or the first post day of a unit with no pretest.
            first = phases["pre"] if "pre" in phases else post
            if first is not None:
                start = min(first.first_days.values())
                if start <= today:
                    out.append(_due_entry(unit, "post", start, False, post))
            continue
        done = post.completion_day()
        d7_reached = "d7" in phases or done + timedelta(days=7) <= today
        for phase, days, optional in REVIEWS:
            when = done + timedelta(days=days)
            st = phases.get(phase)
            if phase == "d1" and d7_reached:
                continue
            if phase == "d21" and when + timedelta(days=D21_LAPSE_DAYS) <= today:
                continue
            if (st is None or not st.complete) and when <= today:
                out.append(_due_entry(unit, phase, when, optional, st))
    out.sort(key=lambda e: (e["due"], e["unit"], DUE_ORDER[e["phase"]]))
    return out


def confident_but_wrong(attempts) -> list[Attempt]:
    """Attempts answered with confidence 3 and scored 0, in input order."""
    return [a for a in attempts if a.confidence == 3 and a.score == 0]




# ---- the page ----------------------------------------------------------------


@lru_cache(maxsize=None)
def _tables() -> dict[str, dict[str, str]]:
    """The page's fixed text by language, from data/progress_strings.json."""
    text = resources.files("tutor_any_lecture").joinpath("data", "progress_strings.json").read_text(encoding="utf-8")
    return json.loads(text)


class _Text:
    """The page's fixed text in one language; a key ending .one or .other is a plural pair."""

    def __init__(self, lang: str) -> None:
        self._table = _tables()[lang]

    def __call__(self, key: str, **values) -> str:
        return self._table[key].format(**values)

    def plural(self, key: str, n: int) -> str:
        return self(f"{key}.{'one' if n == 1 else 'other'}", n=n)

    def phase(self, phase: str) -> str:
        return self(f"phase.{phase}")


def _language_key(code: str) -> str:
    """``ZH-cn`` -> ``zh``, ``en_GB`` -> ``en``: stripped, lowercased, the part before the first - or _."""
    return code.strip().lower().replace("_", "-").split("-")[0]


def page_language(lang: str | None, attempts, plans) -> tuple[str, str | None]:
    """The table the page is written from, and a notice when the language asked for has none.

    The language is ``lang`` when given, else the note language of the newest unit with a
    plan in ``plans`` (the newest: the unit whose first line comes last in the log), else
    English. A language with no table gives English and the notice; no plan gives English
    and no notice. Only ``.note_language`` of a plan is read.
    """
    if lang is None:
        units = list(dict.fromkeys(a.unit for a in attempts))
        lang = next((plans[u].note_language for u in reversed(units) if u in plans), None)
        if lang is None:
            return DEFAULT_LANGUAGE, None
    key = _language_key(lang)
    if key in _tables():
        return key, None
    return DEFAULT_LANGUAGE, f"no progress page text for language '{lang}'; the page is in English"


def _whole(x: float) -> int:
    """``x`` (0 to 1) on the 0 to 100 scale: times 100, halves away from zero.

    Rounding to 6 decimals first keeps float noise from flipping a tie; int() turns -0 into 0.
    """
    return int((Decimal(str(round(x, 6))) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _score(x: float | None) -> str:
    return "—" if x is None else str(_whole(x))


def _percent(x: float | None) -> str:
    return "—" if x is None else f"{_whole(x)}%"


def _cell(text: str) -> str:
    """``text`` inside a Markdown table cell."""
    return text.replace("|", "\\|")


def _separator(header: str) -> str:
    """The separator line under a Markdown table ``header``."""
    return "|" + "---|" * (header.count("|") - 1)


def _plans(workspace: Path, course: str, attempts) -> dict:
    """The plan of every unit in the log that ``find_unit`` finds, by unit name."""
    plans = {}
    for unit in dict.fromkeys(a.unit for a in attempts):
        found = find_unit(workspace, course, unit)
        if found is not None:
            plans[unit] = found[1]
    return plans


def concept_names(plan) -> dict[str, str]:
    """Each concept id of ``plan``, in plan order, with the label it is shown by: its name
    when that is a non-empty string (on one line), else its id. No plan: no names."""
    names: dict[str, str] = {}
    for c in getattr(plan, "concepts", None) or ():
        if not isinstance(c, dict) or not isinstance(c.get("id"), str):
            continue
        name = c.get("name")
        label = " ".join(name.split()) if isinstance(name, str) else ""
        names.setdefault(c["id"], label or c["id"])
    return names


def tracked_units(attempts) -> list[str]:
    """Every unit with an attempt in pre, post or d7, complete or not, in order of first appearance."""
    return [u for u, phases in _phase_states(attempts).items() if any(p in phases for p in TRACKED_PHASES)]


def concept_rows(attempts, unit: str, plan) -> list[tuple[str, dict[str, float]]]:
    """Each concept of ``unit`` with an attempt in pre, post or d7: its label and the mean
    of its attempts in each of those phases.

    Concepts come in the plan's order, then the rest by id; the label is the plan's name,
    else the id.
    """
    by_concept: dict[str, list[Attempt]] = {}
    for a in attempts:
        if a.unit == unit and a.phase in TRACKED_PHASES:
            by_concept.setdefault(a.concept, []).append(a)
    names = concept_names(plan)
    order = [c for c in names if c in by_concept] + sorted(c for c in by_concept if c not in names)
    return [(names.get(c, c), _phase_means(by_concept[c])) for c in order]


def _sentence(t: _Text, tracked: list[str], scores, gains, retained) -> str:
    """The page's conclusion: one sentence built from the numbers below it.

    The gain clause covers pre and post, the retention clause post and day 7; each phase
    neither covers gets the mean of its unit means. Clauses follow the first phase they cover.
    """
    if not tracked:
        return t("nothing_yet")
    clauses: list[tuple[int, str]] = []
    covered: set[str] = set()
    gain = normalized_gain(gains)
    if gain is not None:
        pre, post = _gain_means(gains)
        clauses.append((0, t("gain_clause", pre=_score(pre), post=_score(post), gain=_percent(gain))))
        covered |= {"pre", "post"}
    kept = retention(retained)
    if kept is not None:
        clauses.append((1, t("retention_clause", retention=_percent(kept))))
        covered |= {"post", "d7"}
    for k, phase in enumerate(TRACKED_PHASES):
        means = [scores[u][phase] for u in tracked if phase in scores.get(u, {})]
        if means and phase not in covered:
            clauses.append((k, t("average_clause", phase=t.phase(phase), mean=_score(_mean(means)))))
    if not clauses:  # every phase is partial
        return t("no_complete_phase")
    clauses.sort(key=lambda clause: clause[0])
    return t("sentence", opening=t.plural("opening", len(tracked)),
             clauses=t("clause_sep").join(text for _, text in clauses))


def _unit_row(t: _Text, unit: str, s: dict[str, float], states: dict[str, _PhaseState], gains, retained) -> str:
    """One row of the units table: pre → post, gain, post → day 7, retention.

    Where a unit has concepts attempted in both phases of a pair, the pair shows their means
    and the gain or retention beside it is computed from them; otherwise each phase shows the
    unit's mean over concepts (``unit_scores``), or ``partial`` for a partial phase, and the
    gain or retention is missing.
    """

    def value(phase: str) -> str:
        st = states.get(phase)
        if st is not None and not st.complete:
            return t("partial", k=st.answered, n=st.size)
        return _score(s.get(phase))

    if unit in gains:
        pre_post = f"{_score(gains[unit]['pre'])} → {_score(gains[unit]['post'])}"
        gain = normalized_gain({unit: gains[unit]})
    else:
        pre_post, gain = f"{value('pre')} → {value('post')}", None
    if unit in retained:
        post_d7 = f"{_score(retained[unit]['post'])} → {_score(retained[unit]['d7'])}"
        kept = retention({unit: retained[unit]})
    else:
        post_d7, kept = f"{value('post')} → {value('d7')}", None
    cells = [_cell(unit), pre_post, _percent(gain), post_d7, _percent(kept)]
    return "| " + " | ".join(cells) + " |"


def _concept_table(t: _Text, rows: list[tuple[str, dict[str, float]]]) -> str:
    header = t("concepts_header")
    lines = [header, _separator(header)]
    for label, means in rows:
        cells = [_cell(label), *(_score(means.get(p)) for p in TRACKED_PHASES)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _prompt_start(prompt: str) -> str:
    """The prompt on one line, cut at a word to at most PROMPT_SHOWN characters, with "…" when cut."""
    text = " ".join(prompt.split())
    if len(text) <= PROMPT_SHOWN:
        return text
    head = text[: PROMPT_SHOWN + 1]
    cut = head.rfind(" ")
    return (head[:cut] if cut > 0 else text[:PROMPT_SHOWN]).rstrip() + "…"


def _wrong_line(t: _Text, a: Attempt, names: dict[str, dict[str, str]]) -> str:
    prompt = t("wrong_prompt", text=_prompt_start(a.prompt)) if a.prompt else ""
    answer = t("wrong_answer", text=_prompt_start(a.answer)) if a.answer and a.answer.strip() else ""
    concept = names.get(a.unit, {}).get(a.concept, a.concept)
    line = t("wrong_line", unit=a.unit, item=a.item_id, concept=concept, prompt=prompt,
             phase=t.phase(a.phase), citation=a.citation)
    return line + answer


def _due_line(t: _Text, e: dict) -> str:
    line = t("due_line", unit=e["unit"], phase=t.phase(e["phase"]),
             optional=t("optional") if e["optional"] else "", date=e["due"])
    if e["remaining"] is not None:
        line += t("due_partial", k=e["answered"], n=e["answered"] + len(e["remaining"]))
    return line


def _chart_rows(t: _Text, tracked: list[str], scores, rows_by_unit) -> list[ChartRow]:
    """The chart's rows: the units with their ``unit_scores`` means, then each unit's concepts."""
    if not tracked:
        return []

    def whole(means: dict[str, float]) -> dict[str, int]:
        return {p: _whole(means[p]) for p in TRACKED_PHASES if p in means}

    rows = [ChartRow(t("units_heading"))]
    rows += [ChartRow(u, whole(scores.get(u, {}))) for u in tracked]
    for u in tracked:
        rows.append(ChartRow(u))
        rows += [ChartRow(label, whole(means)) for label, means in rows_by_unit[u]]
    return rows


def render_progress(course: str, workspace: Path, today: date, lang: str | None = None,
                    notices: list[str] | None = None) -> Path:
    """Write the progress page ``<workspace>/progress/<course>.md`` and, beside it, the chart
    ``<course>.svg`` it embeds; return the page's path.

    The page's language is ``lang``, else the newest unit's note language, else English
    (``page_language``); with ``notices`` a list, the fallback notice is appended to it.
    A course with no log raises FileNotFoundError and writes nothing.
    """
    if not _course_file(workspace, course, ".jsonl").exists():
        raise FileNotFoundError(f"no progress log for course '{course}'")
    attempts = load_attempts(course, workspace)  # once, so each skipped line warns once
    plans = _plans(workspace, course, attempts)
    key, notice = page_language(lang, attempts, plans)
    if notice is not None and notices is not None:
        notices.append(notice)
    t = _Text(key)
    names = {unit: concept_names(plan) for unit, plan in plans.items()}

    scores = unit_scores(attempts)
    gains = paired_scores(attempts, "pre", "post")
    retained = paired_scores(attempts, "post", "d7")
    states = _phase_states(attempts)
    tracked = tracked_units(attempts)
    rows_by_unit = {u: concept_rows(attempts, u, plans.get(u)) for u in tracked}
    page = _course_file(workspace, course, ".md")
    chart = page.with_suffix(".svg")

    blocks = [f"# {t('title', course=course)}", _sentence(t, tracked, scores, gains, retained)]
    if tracked:
        header = t("units_header")
        table = [header, _separator(header)]
        table += [_unit_row(t, u, scores.get(u, {}), states[u], gains, retained) for u in tracked]
        partial = any(_partial(states, u, p) for u in tracked for p in TRACKED_PHASES)
        blocks += [
            f"![{t('chart_alt')}](<{chart.name}>)",
            f"## {t('units_heading')}",
            "\n".join(table),
            t("scale_note"),
            *([t("partial_note")] if partial else []),
            f"## {t('concepts_heading')}",
        ]
        for u in tracked:
            blocks += [f"### {u}", _concept_table(t, rows_by_unit[u])]

    due_lines = [_due_line(t, e) for e in due(attempts, today)]
    blocks += [f"## {t('due_heading')}", "\n".join(due_lines) or t("none")]
    wrong_lines = [_wrong_line(t, a, names) for a in confident_but_wrong(attempts)]
    blocks += [f"## {t('wrong_heading')}", "\n".join(wrong_lines) or t("none")]

    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("\n\n".join(blocks) + "\n", encoding="utf-8", newline="\n")
    legend = [t.phase(p) for p in TRACKED_PHASES]
    write_chart(chart, t("title", course=course), legend, _chart_rows(t, tracked, scores, rows_by_unit))
    return page
