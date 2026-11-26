# Teaching data: plan, items, pretest, quizzes, cards, map

You write four JSON files by hand: plan.json, items.json, cards.json and map.json. The command checks them, assigns variants, picks the items to ask, logs answers and renders the rest. Every file below lives in the unit folder `<workspace>/courses/<course>/<unit>/`.

A command that reads plan.json, items.json, assignment.json, cards.json or map.json and finds it malformed exits 1 with one line on stderr that starts with the file's name. Fix the named file, then rerun the command.

## plan.json

One JSON object holding the twelve keys `course`, `unit`, `goal`, `content_type`, `note_language`, `lecture_language`, `duration_s`, `outputs`, `sections`, `concepts`, `tracked`, `output_target`, and optionally `quote_density`. A missing plan.json is a `FileNotFoundError`: exit 1, one stderr line that starts with `plan.json:`. Every command that reads plan.json rejects an existing one (a `PlanError`: exit 1, one stderr line that starts with `plan.json:`) when, and only when:
- its bytes are not UTF-8 or not valid JSON (a leading byte-order mark is accepted), or its top level is not an object;
- one of the twelve keys is missing (extra keys are ignored);
- `course` or `unit` cannot be a folder name (the rule below);
- `note_language` or `lecture_language` is not a string, is "auto" in any letter case, or is not two or three lowercase letters;
- `goal` is not deep, exam or quick; `output_target` is not markdown or obsidian; `quote_density`, when present, is not light, standard or dense;
- `duration_s` is neither a number nor null (true and false are not numbers);
- `outputs` is not a list of strings, or does not hold explanation;
- `concepts` is not a list, or one of its entries is not an object with a string `id`;
- `tracked` is not a list, names an id that no concept has, names one twice, or does not hold exactly `min(5, len(concepts))` ids.

Nothing else is checked. `content_type`, `sections`, each concept's `name`, `type` and `citations`, and the other members of `outputs` are yours to get right, as the list further below says.

**Course and unit names.** Each is a non-empty string with no leading or trailing whitespace, none of `/ \ : * ? " < > |`, no control character, not `.` or `..`, no trailing dot, and not a Windows device name (CON, PRN, AUX, NUL, COM1 to COM9, LPT1 to LPT9, in any letter case, also before an extension, as in `con.txt`). `progress due` and `progress render` apply the same rule to their `--course`. Write `CS 101 - Intro`, not `CS 101: Intro`.

- `goal`: deep, exam or quick. `output_target`: markdown or obsidian (a notion profile is written as markdown).
- `quote_density`: light, standard or dense, from the profile; left out, it is standard. It sets the quote-ratio window of a Chinese, Japanese or Korean note of a lecture in another script (see [writing](writing.md), the quote measure): light 0.15–0.6, standard 0.4–1.2, dense 1.0–2.0. A note in the lecture's own script is not affected.
- `content_type`: formula, code, concept or mixed; it steers the item kinds below.
- `note_language`, `lecture_language`: lowercase primary subtags such as "en", "zh", "ja"; never "auto".
- `duration_s`: the lecture length in seconds, a number, or null when unknown.
- `outputs`: a list of strings from explanation, pretest, quiz, cards, map. It always holds explanation: the gate reads explanation.md, so `profile set outputs`, the profile loader and every command that reads plan.json reject a list without it.
- `concepts`: a list of `{"id", "name", "type", "citations"}`. `type` is one of `definition`, `theorem`, `method`, `example`, `pitfall` (the map node types); `citations` are plain strings such as `"(slide 1)"` or `"(13:42)"`. Give every concept its own id, in the map's id style (letters, digits and underscores, starting with a letter), so a concept can also be a map node.
- `tracked`: `min(5, len(concepts))` distinct concept ids.
- `sections`: a list of objects, one per planned H2 section of the note: `{"title": "…", "concepts": [ids], "citations": ["(slide 1)", …]}`.

```json
{
  "course": "Intro Statistics",
  "unit": "Week 04 - Estimators",
  "goal": "deep",
  "content_type": "formula",
  "note_language": "en",
  "lecture_language": "en",
  "duration_s": 2950.0,
  "outputs": ["explanation", "pretest", "quiz", "cards", "map"],
  "sections": [
    {"title": "Why estimators can be biased", "concepts": ["bias"], "citations": ["(slides 2–4)", "(1:10–6:40)"]}
  ],
  "concepts": [
    {"id": "bias", "name": "Bias of an estimator", "type": "definition", "citations": ["(slide 3)", "(4:12)"]}
  ],
  "tracked": ["bias"],
  "output_target": "markdown"
}
```

## items.json

One JSON object with exactly two keys:
- `"tracked"`: an object keyed by concept id, whose value is an object keyed by variant letter (`"A"`, `"B"`, `"C"`, optionally `"D"`, `"E"`);
- `"practice"`: a list.

Every item, tracked or practice, is an object with exactly the nine keys `id`, `concept`, `kind`, `prompt`, `answer`, `rubric`, `citation`, `difficulty`, `variant`. `id`, `concept`, `prompt`, `answer`, `rubric` and `citation` are strings; `difficulty` is a small integer (1 easy to 3 hard). A tracked item's `variant` equals its letter key and its `concept` equals its concept key; a practice item has `"variant": null`. Ids are unique across the whole file. `kind` is one of `recall`, `apply`, `transfer`, `predict_output`, `complete_code`, `which_method`, `contrast`. `rubric` says what a full answer must contain and what earns half; `citation` is a plain citation string.

Label each item by what it really asks. An item that asks the learner to state a definition or a formula, or to repeat the lecture's own worked example, is `recall`; an `apply` item gives new numbers or a new case.

The variants of one concept share one rubric: write it once for A and, for B, C, D and E, change only the specifics (the numbers, the case). The answer in the note's pretest section answers the pretest variant only (the one `items next --phase pre` prints), never the others, in at most two sentences: the result and the idea it rests on, with its citation. It shows no worked steps (no `=`, no intermediate result), so the post and day-7 variants cannot be answered by copying it; the worked steps belong in the section's prose, on the lecturer's own example (see [writing](writing.md), No restating).

`tracked` holds the plan's tracked concepts only, each with A, B and C, so the bank is at least 3 × the tracked count plus the practice items. A short synthetic example (variants B and C of `bias` have the same shape as A, with their own ids and prompts, `"variant": "B"` and `"variant": "C"`):

```json
{
  "tracked": {
    "bias": {
      "A": {"id": "bias-A", "concept": "bias", "kind": "apply",
            "prompt": "An estimator averages to 2θ over many samples. What is its bias?",
            "answer": "θ: bias is the expected estimate minus the true value (slide 3).",
            "rubric": "1: says θ and uses expectation minus truth; 0.5: right idea, wrong sign.",
            "citation": "(slide 3, 4:12)", "difficulty": 1, "variant": "A"}
    }
  },
  "practice": [
    {"id": "p1", "concept": "bias", "kind": "contrast",
     "prompt": "How can an estimator be unbiased and still be a poor choice?",
     "answer": "Unbiased only fixes the average; a large variance still spreads estimates widely (5:30).",
     "rubric": "1: names variance or spread; 0.5: says 'can still be wrong' with no reason.",
     "citation": "(5:30)", "difficulty": 2, "variant": null}
  ]
}
```

`tutor-any-lecture items validate --unit DIR` runs the item checks on their own: `variants`, `apply_share`, `citation`, `prompt_overlap`, `tracked_leak`, `tracked_vs_practice`, `pretest_complete`. The gate runs the same checks.

## Tracked concepts and variants

5 tracked concepts per unit (all when fewer). Each has parallel variants A, B and C: the same concept and difficulty, a different surface (other numbers, another case, another direction). All variants of one concept share one `kind` and ask in the same form, so that if one asks for a number, every one does; a concept whose variants differ in kind fails `variants`. `tutor-any-lecture items assign --unit DIR` assigns them at random to pre, post and d7 and records the result in assignment.json; it reuses an existing assignment.json unless `--force` is given. D and E, for d1 and d21, are optional; they get every item check that A, B and C get. Parallel variants of one concept must differ enough that no variant's prompt reaches 0.6 containment in another variant's prompt, in either direction: the `variants` check fails each pair that does, as `<concept>: variants A and D overlap at 0.75`.

## Practice items

In-note checks (`tal:check`), extra practice and interleaved items use practice items only. A practice prompt must not overlap a tracked prompt: containment ≥ 0.6 either way fails `tracked_vs_practice`.

## Order of work

1. Write items.json.
2. Run `tutor-any-lecture items assign --unit DIR`.
3. Write the pretest section of explanation.md from `tutor-any-lecture items next --unit DIR --phase pre` (its `items`, in the printed order).
4. Write the rest of the note with plain time citations, then always run `tutor-any-lecture cite link --unit DIR`, again after every edit (it links them where the video's address allows); then cards.json and map.json for the listed outputs.

## Item kinds by content_type

At least 50% of all items, tracked and practice together, are apply/transfer kinds (every kind except recall). Prompts are paraphrased, never copied from the note: containment of a prompt in any sentence of the lecture prose stays below 0.6 (character 3-grams for CJK, word 2-grams otherwise).

| content_type | lean on |
|---|---|
| formula | derivation and "why" items, apply |
| code | `predict_output`, `complete_code` |
| concept | `contrast`, `which_method`, cases |
| mixed | a combination of the above |

Goal quick: a quiz session asks 5–8 items. items.json still carries A, B and C for every tracked concept and at least 50% apply/transfer items; the `variants` and `apply_share` checks do not relax for quick.

**Examples and why prompts.** After a worked example of the lecturer's, the section's `tal:check` asks a faded example (a parallel case whose first steps the prompt works, the last ones left for the learner), then a setup-only item (the parallel case alone); both are practice items of kind `apply`. Every derivation ends with one "why does this step hold" prompt, its answer folded and quoting the lecturer with a citation. Their forms are in [writing](writing.md), Derivations, examples and teaching order.

## Asking one item

The same protocol for every phase: pre, post, d1, d7, d21 and practice.
1. Ask one item at a time. The learner answers in their own words.
2. Before you say whether the answer was right, ask how sure they are: 1 guessing, 2 unsure, 3 sure.
3. Grade 0, 0.5 or 1 against the rubric, and name the rubric line you applied. Then show the cited answer; never before the attempt.
4. Log the score and the confidence together: `tutor-any-lecture progress log --unit DIR --item ID --phase P --score S --confidence K [--exposure E] [--date YYYY-MM-DD] [--answer TEXT]` (no `--course`: course and unit come from plan.json). It appends one line to `<workspace>/progress/<course>.jsonl`, with the item's prompt and the concepts its phase holds, and prints that attempt with `path`, the log file. `--answer TEXT` keeps the learner's answer (surrounding spaces dropped); the progress page shows it beside a confident wrong answer. An answer given on another day (a review done late, or logged afterwards) takes that day as `--date`, so gain and retention count the right days; the default is today. An unknown item id exits 2; a date not written YYYY-MM-DD exits 2.

**Each item in its own phase.** A practice item is logged only with `--phase practice`, a D variant only with d1, an E variant only with d21, and an A, B or C variant only in the phase of pre, post and d7 that assignment.json gives its letter. Any other `--phase` exits 1 with `item ID belongs to phase OWN, not GIVEN` and writes nothing. An A, B or C item needs assignment.json: a missing one exits 1 and names the file.

`tutor-any-lecture items next --unit DIR --phase P` prints `{"phase", "items", "missing"}` for P in pre|post|d1|d7|d21 (`practice` is not a phase there). Practice uses items of the `practice` list of items.json only (`tutor-any-lecture items get --unit DIR --id ID` fetches one by id), logged with `--phase practice`; a tracked item is logged only in its own phase.

A line of the log that cannot be read (not JSON, a missing key, a value outside its set) is skipped: every command that reads the log prints `warning: <log file>: line N skipped: <reason>` on stderr and carries on. Logs written by earlier versions load as they are.

## Pretest

The pretest is asked in chat after the gate passes and before the learner is given the note (explanation.md is delivered only once the pretest is logged), whether or not they attended, when plan.outputs lists both "pretest" and "quiz". Without "quiz" there is no pretest and no post quiz, and nothing is logged for that unit: a logged pretest with no post quiz would leave a `post` entry due for ever. Before the first question, and again when reporting the score, tell the learner that a low pretest score is normal: guessing first makes the lecture stick better. Ask the `pre` items as above, and record how the learner met the lecture with `--exposure` when they tell you (none, attended, watched; unknown otherwise). Then ask the learner to read the note and to say when they have.

The score changes three things, and it never triggers a rewrite of the note:
- **Reading focus.** After the last item, name the sections that plan.json's `sections` give for each concept scored below 1, in note order, as the ones to read closely. When every concept scored 1, say the note can be read at the usual pace.
- **Folded supplements.** Point to the folded why answers in those sections (see [writing](writing.md), Derivations, examples and teaching order).
- **The next unit's level.** With the profile's `level` at auto, a unit is written for a beginner when the pretest mean is below 0.4, for an intermediate learner from 0.4 to 0.8 inclusive, and for an advanced one above 0.8. The pretest mean is the mean, over concepts, of each concept's `pre` score in the newest earlier unit of the same course in `<workspace>/progress/<course>.jsonl` (the unit whose `pre` lines come last in that log), on the 0 to 1 scale of the logged scores; the progress page shows the same mean times 100. With no such unit, the conversation alone decides, and a level set in the profile always wins. The level changes how much background a note explains, never its citations, faithfulness or length window.

## Post quiz

When the learner says they have read the note, ask them, before the first item, to answer with the note closed. Get the items with `tutor-any-lecture items next --unit DIR --phase post`, ask and log each one as above with `--phase post`, then run `tutor-any-lecture cards add-misses --unit DIR` (when "cards" is in plan.outputs). The reviews are counted from the day the post quiz is complete: the latest of the days on which each of its concepts got its first post attempt. Until then nothing but that post quiz is due, and no learning gain can be measured.

## Reviews and "quiz me"

**Which course.** The course the learner names. When they name none, the courses are the log files under `<workspace>/progress/`: each `<course>.jsonl` is one course.

**What is due.** `tutor-any-lecture progress due --course C [--date YYYY-MM-DD]` prints a list of `{"unit", "phase", "due", "optional", "answered", "remaining"}` entries, oldest first, for today or the given day (to see what tomorrow brings, or to pair with a dated `progress log`). A phase is complete when each concept it holds has an attempt; one stopped part-way is partial, and its entry has `"answered"` (how many concepts have an attempt) and `"remaining"` (the sorted ids of the rest): ask only the items of those concepts. A phase not started has `"answered": 0` and `"remaining": null`.
- `post`: the unit's post quiz is not complete; it is due on the unit's first pretest day (its first post day when there was no pretest). Run it as in Post quiz.
- `d1`, `d7`, `d21`: 1, 7 and 21 days after the post quiz is complete, listed until each is complete. d1 and d21 are optional: d1 lapses once d7 is due or started, and d21 lapses 14 days after it is due. d7 never lapses. Get the items with `tutor-any-lecture items next --unit DIR --phase P`; for d1 and d21, read `missing` in its output, write the D (d1) or E (d21) variants for those concepts into items.json first, then run `tutor-any-lecture items validate --unit DIR` and ask them only when it exits 0 (or skip the optional review). Ask and log with `--phase P`, then run `tutor-any-lecture cards add-misses --unit DIR` (when "cards" is in plan.outputs).

For an entry, DIR is `<workspace>/courses/<course>/<unit>`. Anything the learner wants beyond what is due is practice: practice items, logged with `--phase practice`. Practice misses make no cards.

**Interleaving.** From a course's third unit on, a quiz may add up to two items from earlier units of the same course whose plan.json lists "quiz". Only practice items are reused, never a tracked variant, and each is logged against its own unit (`--unit` that unit's folder) with `--phase practice`.

`tutor-any-lecture progress render --course C [--date YYYY-MM-DD] [--lang CODE]` writes the progress page `<workspace>/progress/<course>.md` and, beside it, the chart `<workspace>/progress/<course>.svg` that the page embeds, and prints `{"paths": [page, chart], "lang"}`. The page opens with one sentence built from its numbers (normalized gain, retention, or a phase's average), then has a table of units (pre → post, gain, post → day 7, retention), a table per unit of each concept's pre, post and day-7 scores (concepts by their plan.json names), what is due on the given day (default today), and confident-but-wrong answers with the start of each item's prompt and of the learner's answer. Every score is on one 0 to 100 scale, and gain and retention are percentages. The chart shows each unit's and each concept's scores as dots on that scale (○ pretest, ● post quiz, ◆ day-7 review; marks of equal scores stand side by side), drawn in the bundled palette's colours. A partial phase shows as "k of n" in its cell (k of its n concepts have an attempt), stays out of every mean, gain and retention until it is complete, and its due line ends `, k of n answered`. The page's language is `--lang` when given, else the note language of the course's newest unit whose plan.json is found, else English. English and Chinese have page text; any other language gives the English page and one line on stderr that says so.

## Cards

Core cards at most 25 per unit (10 for goal quick). Miss cards come from `tutor-any-lecture cards add-misses --unit DIR`, which adds one card for each item scored below 1 in a post, d1, d7 or d21 attempt of the unit, at most 10 per unit over all its reviews (once a unit has 10, later misses add none; the gate fails more than 10), not counted against the core cap. It copies the item's whole prompt and answer, so after each run rewrite every new miss card in cards.json to the rules below (one point, a clear cue on the front, a short back), keeping its `id`, `kind` and `citation`, then run `cards export` again. The gate warns (`miss_rewritten`) while a miss card's front is still its item's whole prompt. The rules, for core and miss cards alike:
- one point per card, answered by recall;
- a clear cue on the front that does not leak the answer;
- difficulty around 90% success with some effort;
- only what will be examined;
- the back cites its source;
- backs over 350 characters draw a WARN;
- fronts whose character 3-gram Jaccard is ≥ 0.8 are duplicates (FAIL).

Card-writing rules adapted from anki-card-forge (https://github.com/FrostySL/anki-card-forge), MIT License, Copyright (c) 2026 Lukas Sinning.

The full notice is in THIRD_PARTY_NOTICES.md.

**Card text.** Write fronts and backs as plain text. `cards export` converts three things for Anki: `$…$` and `$$…$$` math (into MathJax delimiters; write `\$` for a literal dollar sign), backticked code, and fenced code blocks; line breaks become line breaks. Write no HTML: `<`, `>` and `&` are escaped, so a tag shows as text. Put the source in `citation`, not in the back: the export appends the citation under the back, unless the back already ends with it (trailing punctuation and spaces aside, full-width parentheses counting as ordinary ones).

GUIDs are stable (derived from course, unit and card id), so re-importing cards.tsv updates cards without losing review history: never renumber card ids. cards.json is a top-level list of `{"id", "concept", "front", "back", "citation", "kind"?}`; `kind` is "core" (the default) or "miss", and every value is a string. A card's `concept` must be a concept id of plan.json, or the `concept` check of `cards` fails. `tutor-any-lecture cards export --unit DIR` writes cards.tsv for Anki's import.

```json
[
  {"id": "c01", "concept": "bias", "front": "Bias of an estimator: definition?",
   "back": "$E[\\hat\\theta] - \\theta$: the expected value of the estimator minus the true parameter.", "citation": "(slide 3)"}
]
```

## Overview map

map.json is `{"nodes": [{"id", "label", "type", "order"?, "key"?, "citation"?}], "edges": [{"from", "to", "verb"}], "views": [{"id", "nodes"}]?}`.
- Node types: definition, theorem, method, example, pitfall.
- A node id uses letters, digits and underscores, starts with a letter, and is not `end`.
- Every edge names existing nodes and has a verb.
- `order` numbers the main line in lecture order, each value used once. `key: true` marks the idea the rest of the view depends on, at most one per view.
- Node labels and edge verbs are written in plan.note_language: in English, verbs such as "defines", "is used in", "fails when"; in Chinese, "定义", "用于", "不适用于".
- At most 12 nodes per view. A map of more than 12 nodes needs views, and then every node belongs to at least one view.

`tutor-any-lecture map validate --unit DIR` checks it. `tutor-any-lecture map mermaid --unit DIR` writes one Mermaid file per view, `overview-<view>.mmd` (a view id must be usable in a file name), and prints `{"paths": […]}`; a map without views goes whole into `overview.mmd` and prints `{"path"}`. `--view ID` writes only that view, to `overview.mmd`; an unknown view exits 2. Deliver the per-view files of a map with views, never a whole map of more than 12 nodes.

`tutor-any-lecture map render --unit DIR` draws the map as editable Excalidraw files: `map-<view>.excalidraw` for each view, or `map.excalidraw` for a map without views or with `--view ID`. `--obsidian` writes `.excalidraw.md` files in their place, for the Obsidian Excalidraw plugin. An existing drawing is kept: the command exits 3 and writes nothing unless you add `--force`, which you never do once the learner may have edited it. The main line runs down one column in order, each other node sits beside the main-line node it joins, shape and stroke tell the five kinds apart, a key node is highlighted, and the legend is in Chinese when plan.note_language is zh, otherwise in English.

## Suspects and the errata section

`tutor-any-lecture slides suspects --unit DIR` writes `sources/suspects.json`: transcript words that look like a slide term, each with the time, the heard word and the nearest slide term. A suspect is a lead, not a finding. List in the errata section only real transcription errors: a word the recording says differently from what the transcript wrote. A suspect that is an inflection of the slide's word ("payments" for "payment") or is simply correct is not listed. In a Chinese, Japanese or Korean deck, the slide terms are the runs of 2 to 10 characters of one script (Han, katakana or Hangul) between spaces, punctuation and changes of script, hiragana runs left out; a suspect is a stretch of the transcript as long as a slide term of 4 to 10 characters that differs from it in one character and is not on the slides, such as 弃权定价 heard for 期权定价.

The gate requires only that the `tal:errata` markers pair up and that there is at most one errata section; it does not compare the section with suspects.json, and the section's text counts as neither prose nor quotes. A unit with no real errata may leave the section out.
