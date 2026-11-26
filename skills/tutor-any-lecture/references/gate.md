# The delivery gate

`tutor-any-lecture verify --unit DIR` checks one unit folder and writes verify.json there. Add `--json` to print the result as one JSON line instead of a table. Nothing is delivered until overall is PASS.

## Statuses

Each check is PASS, WARN or FAIL. **Overall is PASS iff no check is FAIL**; warnings do not block delivery, but read them and fix what is real. verify.json holds `checks` (each `{"name", "status", "details"}`), `overall`, `warnings` (the number of WARN checks), `measures` and `report`, which is exactly one of:
- `Automated checks passed; not visually reviewed.`
- `Automated checks failed.`

Exit 0 on PASS, 1 on FAIL.

**After a visual check.** After a visual check (below), and only then, say in chat `Automated checks passed; reviewed once visually.` in place of the printed PASS line. Say it only when you rendered the note and walked the eight points yourself in this session. verify still prints and records its own line; never edit verify.json.

**What was measured.** `measures` records, whether the checks passed or not: `minutes`; `length` (`unit`, `total`, `per_min` and its `window`); `time_citations` and `quotes` (`per_min` and the `min` for the goal); `quote_share` or `quote_ratio` (`value` and `window`; the other is null); `h2` (`count` and `max`). Per-minute values and limits are null when the duration is unknown. `length`'s `total`, `per_min` and `window` are null when the length rules are not applied for the note's language. After its table, verify prints them on one line before the report line, for example `measures: length 52.3 words/min (26-53); time citations 0.8/min (>= 0.67); quotes 0.31/min (>= 0.22); quote share 0.18 (0.1-0.4); H2 12 (<= 16)`. Read it on PASS too: it shows how close the note is to each limit.

**Languages.** English and Chinese are first-class. Other languages written with spaces between words are checked like English. Where most letters of the note are in a script the checks cannot split into words (Thai, Lao, Khmer, Burmese, Devanagari and other Indic scripts), `length`, `thin_section` and `long_paragraph` (under `structure`) and `terms` report `not applied for this language` as a WARN, never a FAIL, and so does the lookup of each cited quote written in such a script (`quote '…': not applied for this language`, under `citations`). `terms` is also not applied to German (or Luxembourgish), which capitalises every noun. That WARN cannot be fixed: mention it at delivery. `banned_phrases` has lists for English and Chinese only; for a note in any other language it is a PASS with the detail `not applied for this language: <language>` (for example `not applied for this language: ja`), not a WARN, because a missing list is not a defect in the note.

## The nine checks, in order

| check | what it catches | worst status |
|---|---|---|
| `citations` | a slide number above the last slide; a time more than 2 s past the duration; a time citation in a slides-only unit; a unit with no `sources/transcript.json` that is not slides-only; `quote_source`: a cited quote that is in neither the transcript nor the slides (FAIL), or that is there but not at the place it cites (WARN, naming where it was found), a cited quote with no part of three words or six CJK characters to check (WARN), and an inline quote the note gives to another speaker than the transcript's speaker labels name (WARN, `quote '…' is LECTURER's words at 1:45`), see [writing](writing.md), Faithful to the lecturer; `time_links`: in a unit whose video address has a time form, time citations not yet linked (run `cite link`), and in any unit a time link whose address points at another time or holds no time (WARN); see [writing](writing.md), Citations | FAIL |
| `coverage` | a slide that is neither cited anywhere in the note nor listed (`slide N` or `slides N–M`) in the `tal:not-covered` section | FAIL |
| `terms` | capitalised multi-word terms and words with an inner capital, in the lecture prose, that appear in neither the transcript nor the slides; the lines between the H1 and the first H2 and the callout type names are skipped | WARN |
| `numbers` | numbers with a unit or a currency sign (£, $, €, ¥) that are in the sources but not in the lecture prose, or the other way round. Both sides are read after NFKC, so `３％` is `3%`; a number is compared by its unit, so `5 years` meets `5年`, and shown as written. The units: `%` (percent, and 百分之 before the number), bp (bps, 基点), years (年, 년), months (个月, 個月, ヶ月, か月, カ月, 개월), weeks (周, 週, 星期, 个星期, 個星期, 週間), days (天, 日間), hours (小时, 小時, 个小时, 個小時, 時間, 시간), minutes (分钟, 分鐘, 分間). Calendar years (`2008年`), ordinals (`第3周`), a month's name (`3月`) and number words ("five percent", 五年) are not read | WARN |
| `structure` | the note rules of [writing](writing.md): markers, H4, headings with an outline prefix (`1.`, `1.2`), callout types, TOC links, `<details>` answers, `details_shape` (anywhere in the note outside code, Exercises too: a `<details>` that is never closed, a `</details>` that closes nothing, a block whose first text is not `<summary>…</summary>` on one line), quotes per paragraph and their citations, uncited blockquotes (FAIL); length, time citations and quotes per minute, H2 count, thin sections, long paragraphs, bold, highlights, bullets, `math_form` (`\(…\)` or `\[…\]`, which GitHub does not render, and a `$` outside math, which is written `\$`), quote share or quote ratio (the ratio's window set by plan.json's `quote_density`) (WARN) | FAIL |
| `items` | items.json against plan.json and the note: `variants` (also two variants of one concept whose prompts overlap), `apply_share`, `citation`, `prompt_overlap`, `tracked_leak`, `tracked_vs_practice` (FAIL); `pretest_complete` (WARN); a missing items.json or assignment.json (FAIL) | FAIL |
| `cards` | `count` over the cap, `duplicates`, an empty `citation`, a `concept` that is not a concept id of plan.json (FAIL); `back_length` over 350 characters (WARN) | FAIL |
| `map` | map.json schema, node types, edges without a verb or with an unknown end, views over 12 nodes, nodes in no view | FAIL |
| `banned_phrases` | stock phrases from the list of plan.json's `note_language` (`data/banned_phrases/en.txt`, `data/banned_phrases/zh.txt`), such as "delve", "it's worth noting", "in summary", 综上所述, matched as whole words (so "delved" is not "delve") and across line breaks, in the note's own words: quoted spans, blockquotes that are not callouts, code, HTML comments, link addresses and URLs are not read; callouts, marker sections, headings and `<details>` answers are | WARN |

**Skipped checks.** `items` is skipped when neither "quiz" nor "pretest" is in plan.outputs, `cards` when "cards" is not, and `map` when "map" is not. A skipped check is PASS with the detail `skipped: not in plan.outputs`. A listed output whose file is missing is FAIL.

**Lecture prose.** `terms` and `numbers` read the lecture prose only: the note without its marker sections (pretest, checks, not covered, errata), NOTE callouts, code and math. A number that appears only in a pretest answer does not count as in the note.

**Unknown duration.** When neither plan.json nor source.json gives a duration, the per-minute checks are skipped and `structure` reports a WARN; time citations are not range-checked and `citations` reports a WARN. Unknown duration is never a FAIL on its own.

**Slides-only units.** Without `sources/transcript.json` a unit passes only when source.json's `kind` is "slides-only" (what `tutor-any-lecture slides --pdf F --unit DIR` writes into a unit that has no source.json), and then any time citation is a FAIL. Such a note cites slides only.

## The loop

1. Always run `tutor-any-lecture cite link --unit DIR` (it links the plain time citations where the video's address allows; see [writing](writing.md), Citations). Run `tutor-any-lecture cards export --unit DIR` when "cards" is in plan.outputs and `tutor-any-lecture map mermaid --unit DIR` when "map" is.
2. Run `tutor-any-lecture verify --unit DIR`.
3. For each FAIL, read its details, fix the file they name (usually explanation.md, items.json, cards.json or map.json) and rerun. After any change to explanation.md, run `tutor-any-lecture cite link --unit DIR` again before verify. After an items.json change, keep assignment.json unless a tracked concept changed; then rerun `tutor-any-lecture items assign --unit DIR --force` and rewrite the pretest section.
4. If three verify runs in a row end in FAIL with the same check and the same details, stop fixing. Tell the learner in plain words which check failed and what its details say, and that the note did not pass. Leave the files in the unit folder and never present them as passed.
5. Stop at PASS. Fix WARNs that point at a real problem; leave the rest and explain them at delivery.

**Honest reporting.** At delivery, give the `report` line exactly as printed (or the visual line above, after a visual check), then one plain sentence per WARN left, in the note language, saying what it means for the learner. For `numbers: in the sources, not in the note: 20 years`, an English note says "The recording mentions 20 years, which the note does not."; a Chinese note says "录音里提到了 20 年，笔记里没有写。". Never say the note was reviewed visually, read by a person or checked against the recording when it was not.

## The visual check

### When

Only for a showcase unit (one made to be shown to others), or when a check or the learner reported a problem that only rendering can confirm. Never otherwise.

### How to render

- A markdown note: a Markdown preview that shows GitHub alerts, `<details>` and `$` math. For a showcase unit that is GitHub's own file view; for a learner's unit it is a local preview, and the unit is never uploaded to a site to be rendered.
- An obsidian note: Obsidian's reading view of the vault copy.
- Each map file (`overview.mmd`, or `overview-<view>.mmd` for each view): inside a `mermaid` code fence of a scratch note, shown the same way; the scratch note is not delivered.

An agent that cannot see the rendered page does not do the check, and its report line stays the printed one.

### The eight points

1. Callouts render as boxes of their type; no `[!NOTE]` or stray `>` shows as text.
2. Every `<details>` shows only its summary until opened, opens to its answer, and the text after it is visible.
3. Every formula renders, numbered equations show their numbers, no raw `\tag` or lone `$` shows, and a `\$` shows as a currency sign.
4. Every table of contents entry jumps to its section.
5. Citations read as plain parentheses and, where `cite link` linked the times, one time link per section opens the video at the cited second.
6. The errata table and any formula table show as tables with a header row.
7. The prose reads as paragraphs, not walls of bullets or bold; headings are in sentence case; no template traces show (headings in capitals, middle-dot separators, an arrow after a link).
8. Each map view renders as a diagram, every label reads whole, and no view shows more than 12 nodes.

### One round

Render once, walk the eight points, and fix what they show in one round. Then run `tutor-any-lecture cite link --unit DIR` (when explanation.md changed) and `tutor-any-lecture verify --unit DIR` again, and stop: there is no second visual round.

## Exit codes

| code | meaning |
|---|---|
| 0 | PASS or WARN, a healthy transcript, doctor ready |
| 1 | verify or validate FAIL; an unhealthy or empty transcript; selftest not ok; a missing file (plan.json, explanation.md, map.json, assignment.json for `items next` and for `progress log` of an A, B or C item, a slide PDF, a transcript for `slides suspects`, a progress log for `progress render`, a materials folder for `acquire route`); a malformed file: plan.json, items.json, assignment.json, cards.json or map.json (one stderr line naming the file), or profile.yaml, and a value that `profile set` rejects (a `ProfileError` naming the key); an acquisition input that could not be read or parsed, or a tool or ASR backend that failed (an `error` object, below); an item logged outside its own phase (`progress log`) |
| 2 | usage error (a wrong or missing flag, `slides` without `--pdf` and `--unit`, a bare `acquire`, `acquire url` with neither `--unit` nor `--info`, a `--date` not written YYYY-MM-DD), an unknown item id (`items get`, `progress log`), an unknown `--view` for `map mermaid` |
| 3 | needs the user: doctor not ready; consent required (`profile set public_video_audio on`); a file needed from the user (`needs_user_file`); ASR time budget exceeded (rerun with a larger `--budget-minutes`); speech recognition not installed (run the installer again with `--with-asr`, Windows `-WithAsr`); the output exists (rerun with `--force`); `selftest --keep` on a folder that exists and is not empty (pick a new or empty one) |
| 130 | interrupted with Ctrl+C |
| 143 | stopped by a signal, such as a shell timeout; the command cleaned up after itself and can be run again |

## Acquisition JSON

`acquire import`, `acquire panopto`, `acquire local`, `acquire url` and `transcribe` print exactly one JSON object on stdout:
- `{"status": "ok", "health": {…}}`, exit 0; for `acquire url` also `title` (the video's) and `acquisition` (the track used: "cc", "auto" or "asr"), here and in `unhealthy`;
- `{"status": "unhealthy", "health": {…}}`, exit 1: the transcript was written but failed a health check; for `acquire url` these are caption tracks, kept and reported when no healthy track exists and audio may not be used. Show the health numbers and tell the learner before planning on that transcript; a rerun needs `--force`;
- `{"status": "error", "message": …}`, exit 1, nothing written. The causes: the input file is missing or is a folder; the source had no timed text (`no timed segments found`); the input is not UTF-8 or could not be parsed; profile.yaml is malformed; a tool (ffmpeg, yt-dlp) or the ASR backend failed; the video page could not be read (private, removed, region- or login-locked); the URL is a playlist (one video per unit). Show `message` to the learner;
- `acquire url` only: `{"status": "needs_user_file", "message": …}`, exit 3: no usable captions, and audio may not or cannot be downloaded: the switch is off, or the audio download failed, for example behind a login.

`health` has the keys `coverage` (share of the duration the segments span, healthy from 0.9), `repetition` (share of segments repeating the previous one, healthy up to 0.5), `spots_ok` (segments near 10%, 50% and 90% of the duration), `overrun` (a segment ends more than 2 s after the duration), `loop` (five or more identical segments in a row), `ok`, and `duration_known`. With an unknown duration, coverage and spots cannot be measured and count as fine.

`acquire url --url U --info` reads only the video page: it needs no `--unit`, writes nothing and prints `{"status": "ok", "title", "duration", "uploader", "manual_captions": [language codes], "automatic_captions": true|false}`, or the `error` object above (exit 1).

**Commands that write a file** end by printing one JSON object that names it: `{"path"}`, or `{"paths": […]}` for several (`map mermaid` on a map with views; `progress render`, the page and its chart, with `lang`). `cards export`, `cards add-misses` (with `added`), `cite link` (with `linked`, and `reason` when it links nothing), `items assign` (the assignment, with `path`), `slides --pdf` and `slides suspects` (with their counts), `map mermaid`, `progress log` (the attempt, with `path`) and `progress render` do so.

An existing `sources/transcript.json` without `--force` stops the command before any work (exit 3, one line on stderr). A budget or backend problem (exit 3) is also one stderr line, with no JSON on stdout.
