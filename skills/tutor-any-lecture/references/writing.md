# Writing contract for explanation.md

This file says what the explanation note looks like. Read it before writing and check the note against it afterwards. The note follows the lecture as it was given and keeps the lecturer's points and best explanations faithfully. It is not a preview note (a systematic text that lets someone skip the lecture); the two are different genres with different uses.

Why it looks like this: headings help recall only where the topic really changes (Hyönä and Lorch 2004), so forced sections hurt; self-explanation prompts work when they ask why, not what (Bisra et al. 2018); practice questions should match the format of the assessment (Dunlosky et al. 2013); and formatting is best steered by positive examples rather than bans. The rules were tuned on real lectures and revised once after a with-rules versus without-rules comparison.

`tutor-any-lecture verify --unit DIR` enforces the numeric parts of this contract (see [gate](gate.md)). The numbers below are the ones in `notecheck.THRESHOLDS`, which is what verify enforces; its `measures:` line prints what it measured, also on PASS.

**Units of measure.** Length is counted over the lecture prose: the note without code (fenced blocks and inline code) and without the four marker sections. Within it, math (`$…$`, `$$…$$`, `\(…\)`, `\[…\]`) and URLs are left out and a link counts its text only; everything else counts: the H1 and every heading, the table of contents, the how-to-read lines, callouts of every type, blockquotes and quoted text, tables and citations. A Chinese, Japanese or Korean note counts CJK characters only (Latin letters, digits and punctuation count nothing, so English quotes add nothing); any other note counts words, a word being a run of letters or digits joined by inner apostrophes or hyphens, so `(slide 1, 0:42)` is four words. `slide N` is the number printed in the slide's footer (the 15 of "15/32"), not the PDF page index: incremental builds make a PDF much longer than its footer count. If a page has no footer number, cite its PDF page number.

## Language and terms

The note is written in `plan.note_language`. The `terms` setting decides how technical terms appear:
- `bilingual`: when the lecture language and the note language differ, write each term one way throughout: in the note's language, with the lecturer's original in parentheses at its first use (`二元关系 (binary relation)`), then the note-language term alone;
- `note`: the note language only;
- `original`: the lecturer's term only.

Use one spelling of each term across the note, items.json, cards.json and map.json.

Which checks can read which languages, and what they report when they cannot, is in [gate](gate.md), Languages.

Write directly: conclusion first, no greetings, no wrap-up. When you report the lecturer's position, write "the lecturer says", not "we think". Write headings in sentence case: a run of capitalised words, or a word with a capital inside it (an acronym, a CamelCase name), that does not appear in the transcript or slides draws a `terms` warning. NOTE callouts and the marker sections are exempt, and so are the lines between the H1 and the first H2 (the table of contents and the how-to-read lines) and the callout type names NOTE, IMPORTANT, WARNING and CAUTION anywhere.

## Skeleton

```markdown
# <Unit title>

- [Pretest](#pretest)
- [<Topic 1>](#<slug>)
- [Not covered and errata](#not-covered-and-errata)

How to read this note: <two or three sentences, in the note language>

## Pretest

<!-- tal:pretest -->
1. <pre-variant prompt, verbatim from items.json>
   <details><summary>Answer</summary>

   <cited answer>

   </details>
<!-- /tal:pretest -->

## <Topic 1>

*(slides 2–4, 0:40–3:10)*

<paragraphs>

<!-- tal:check -->
1. <practice prompt, verbatim from items.json>
   <details><summary>Answer</summary>

   <cited answer>

   </details>
<!-- /tal:check -->

## <Topic 2>
...

## Not covered and errata

<!-- tal:not-covered -->
- slide 9: <one sentence on why it was not covered>
<!-- /tal:not-covered -->

<!-- tal:errata -->
> [!CAUTION]
> Transcript and slide errata
>
> | Time | Heard | Should be |
> |---|---|---|
> | 12:31 | eigenvaloo | eigenvalue |
<!-- /tal:errata -->
```

- Each answer has a blank line above and below it inside `<details>`, as in the skeleton: the blank lines let Markdown and math render inside the block.
- Start the note with one H1 (a style rule; verify does not check it). Then the table of contents, then the "how to read this note" lines, then the sections.
- **How to read this note** (kept from v1, shortened): the body holds only what the lecturer said and the slides show, in lecture order; quoted text is verbatim from the slides or the recording, with `…` marking a cut and `[ ]` an insertion; `(slide N)` is the footer number and `(mm:ss)` the recording time; note boxes are tutor additions, caution boxes are errata and doubts; equations are numbered so they can be referred to. Add or drop half a sentence to fit the unit (for example, no exercises).
- **Table of contents.** One list item per H2 that you want listed. Each link must match an H2: `[text](#slug)` for markdown (see [markdown](output-targets/markdown.md)), `[[#Heading]]` with the heading text exactly for obsidian (see [obsidian](output-targets/obsidian.md)). Keep `[ ] | #` out of H2 text. The obsidian target's `[[#…]]` links and `==highlights==` do not render on GitHub: write for the markdown target when the note will be read there. On the markdown target never write `[[#…]]` links: the gate does not check them there, and GitHub shows them as text.
- **Optional sections.** "What the lecturer said about the course" collects arrangements, assessment, readings and exam scope that the lecturer scattered across the session, with every time range on its anchor line. "Exercises" and a formula quick-reference table appear only when the source has exercises or formulas (see below).

The fixed strings follow the note language. The skeleton shows the English forms; a Chinese note writes `## 课前测` for the pretest heading, `## 未讲到的内容和勘误` for the last heading, `<details><summary>答案</summary>` for each answer, `> 转写稿和课件勘误` for the errata title and `| 时间 | 听到的 | 应为 |` for its table header, and starts the how-to-read lines with `阅读说明：`. The table of contents links the headings as they are written. The gate requires none of the English forms: it finds an answer by its `<details` tag, whatever the summary says.

## Headings and anchor lines

One H2 per topic change by the lecturer, in lecture order; a 90-minute lecture usually has 10 to 16. Take topic changes from the lecturer's transition sentences ("so, bond valuation") and the slide sections; sources/chapters.json, when present, is a hint only (its chapters are often too fine and their titles often wrong). The single exception to lecture order is the optional course-arrangements section.

H3 appears only for three things, and its title starts with "Derivation:", "Worked example:" or "Class discussion:"; usually 3 to 6 per lecture. The gate does not read H3 titles, so a note in another language writes these prefixes in its own language (in Chinese `推导：`, `例题：`, `课堂讨论：`). An H3 holds only the derivation or example itself; the lecturer's asides during it go back into the H2 prose (they may follow the H3). There is no H4. A heading may start with a number (`## 2008 crisis and rates`), but never with an outline prefix such as `1.`, `2)`, `1.2` or `1.2.3` (`## 1. Rates` fails the gate). A section shorter than 150 CJK characters or 90 words is thin: merge it into the previous one. Headings in a Chinese, Japanese or Korean note join their parts with that language's punctuation (`## 复利：两种算法`), not bare spaces: the markdown slug drops the punctuation (`#复利两种算法`) but turns each space into `-`.

The first line of every topic H2 is an italic anchor line written as a citation, for example `*(slides 14–16, 40:38–48:34)*` or, with several time ranges, `*(5:45–12:08, 36:47–40:29)*`. Fixed sections (pretest, not covered and errata, exercises, formula table) have no anchor line.

## What a section is made of

Each H2 holds one to six paragraphs; a paragraph completes one step of reasoning (roughly 60 to 250 CJK characters or 40 to 150 words; over 300 CJK characters or 180 words is too long). A display equation `$$…$$` belongs to its paragraph. Write math as `$…$` and `$$…$$` only, and number a key formula with `\tag{n}` inside its display, `$$…\tag{n}$$`; `\(…\)` and `\[…\]` do not render on GitHub and draw a `math_form` warning. Write a currency sign as `\$`, so it is not read as math. Inside a paragraph the content keeps this order, using only the parts that exist: why the lecturer introduces the idea, then the definition (verbatim, cited), then intuition or a concrete example (examples before symbols), then the formula or derivation (key formulas numbered, each derivation step naming the rule it uses), then a worked example, then the most common mistake.

The body of a paragraph is your explanation; quotes are the evidence set into it. At most 3 quotes per paragraph; quote definitions, results and the lecturer's own explanations, never transitions, repetitions or a second phrasing of the same point (paraphrase those and cite the time). Quote where the lecturer's own wording matters (a definition, the statement of a result, a phrase worth remembering), in whole clauses, not as fragments spliced into a sentence of yours. A definition or a result that the reader should see whole, one sentence or more, goes in a blockquote with its citation on its last line; shorter words of the lecturer go inline. A note in another language than the lecture is written in its own language, with the quotes set into it. A WARN from the quote measure (below) is advice, not a target: never add quotes to reach a number. Lists are only for parallel items: the formula table, the errata table, the exercise list and the item lists in marker sections. Reasoning, explanation and cause go into sentences. At most 15 bold spans in the note, at most one bolded conclusion per section.

`==highlights==` are for the obsidian target only, at most 8, and only for two triggers: the lecturer says something will or will not be examined, or an exercise uses the formula or convention directly. The markdown target has no highlights.

A paragraph written the right way (an illustrative finance example; the quotes are invented for the illustration, not real lecture words):

```markdown
Discrete compounding starts from £1 (slide 15). At rate $r$ paid once a year, the account holds $(1+r)$ after one year; at $r=10\%$ that is £1.10. After two years it holds the first year's $(1+r)$ plus interest on it: $(1+r)+(1+r)\times r=(1+r)^2$, or £1.21. The lecturer stresses why: in the second year not only the principal earns, because "the interest you earned last year earns interest too", so the result is a square and not $1+2r$ (44:38–44:53). For $n$ years it is $(1+r)^n$, and "give it fifty years and the number gets very large" (45:15–45:19).
```

The same content as fragments (what appeared without rules): a bold label, then three bullets "after 1 year: $1+r$", "after 2 years: $(1+r)^2$", "after $n$ years: $(1+r)^n$". The same content as a pile of quotes (what appeared with rules but no cap): every clause is a quote, and the explanation disappears. The first version links the lecturer's reason, words and formula into one argument; the second cuts them into items that explain nothing; the third only quotes.

## Derivations, examples and teaching order

Every derivation ends with one "why does this step hold" prompt about a step whose reason the lecturer gave, and a derivation with no such step has no prompt. The prompt closes the derivation's H3, with its answer folded:

```markdown
### Derivation: <what is derived>

<the steps, each naming the rule it uses>

*Why <the step in question>?*

<details><summary>Answer</summary>

<the answer, quoting the lecturer, with its citation>

</details>
```

In a Chinese note the prompt line is `*为什么<那一步>？*` and the H3 starts with `推导：`. The answer is lecture prose: the quote checks read it, so its quote must be at the place it cites.

After a worked example the lecturer gives (an H3 `Worked example:`), the section's `tal:check` holds first a faded example (a parallel case with new numbers whose first steps the prompt works, asking for the last ones), then a setup-only item (a parallel case alone). Both are practice items of kind `apply` from items.json, printed verbatim like every check item.

Explain a term or result before the first sentence that uses it. When the lecturer uses a term before defining it, keep the lecture's order and add a NOTE callout of one sentence with its meaning where the term first appears. A derivation or a worked example shows at most 15 steps in one run: cut a longer one into runs of at most 15 steps, each ending with a sentence that says what it has shown.

## Faithful to the lecturer

Every definition, theorem and result in the body maps to a slide or a time. Definitions and theorems are quoted verbatim from the slides with `(slide N)`; the lecturer's key spoken explanations are quoted verbatim from the transcript with `(mm:ss)` or a time range. Cite only the real source: slide content cites the slide, spoken content the time, both when both apply. Every clause of a sentence you attribute to the lecturer is in the span it cites. Context, a contrast or a consequence that you add goes into a sentence of its own that does not name the lecturer, or into a NOTE callout; when the lecturer names one side of a contrast, write only that side. If the lecturer says this course teaches you to make programs fast, do not write that the lecturer says other courses only teach you to make them run. A student's remark may be quoted as "a student answers: …" with its time and the lecturer's response. Give a quote to the speaker the transcript names; when a student's words are inaudible and the lecturer restates them, write that the lecturer restated a student's answer. When the transcript labels its speakers (`LECTURER: `, `STUDENT 2: `), an English or Chinese note that gives a lecturer's words to a student, or a student's words to no student, gets a `quote_source` WARN that names the label and the time (`quote '…' is STUDENT's words at 1:40`).

**Quotation marks mean a quotation.** In the note, every span inside quotation marks of any of these pairs, `"…"`, `“…”`, `„…“`, `„…”`, `«…»`, `»…«`, `‘…’`, `‚…‘`, `‹…›`, `「…」`, `『…』`, `＂…＂`, of 15 characters or more, or 6 or more when it holds a CJK character, must be the lecturer's or the slide's own words, and the gate checks it: in the lecture prose such a span needs a citation in its paragraph (`uncited_quote`, FAIL) and is looked up at the place it cites (`quote_source`, below). Marks pair left to right on one line, never nested; an `’` followed by a letter or digit is an apostrophe. A paraphrase or an example in your own words takes no quotation marks, also in a Chinese note, where “…” is otherwise common for emphasis. A title, a term or an emphasised phrase takes no quotation marks of any kind (『…』 and 「…」 included); write a title in italics.

**Quotes are verbatim**, in the lecture's language (a note in another language still quotes the lecture's own words), copied from the transcript or the slide they cite. Two editorial marks are allowed: `…` (or `...`) marks an omission, such as filler words ("uh", "you know") or a self-repetition you cut; `[ ]` marks an insertion, such as `[the rate]` for a pronoun, or the slide's word in place of a mis-heard one. Letter case and punctuation may differ; words may not. The gate (`quote_source`, reported under `citations`) checks every cited quote of the lecture prose (an inline quote of 15 characters or more, or 6 or more when the span holds a CJK character, or a blockquote that is not a callout; in a paragraph, list item, table row or callout): each run of three or more words (six or more CJK characters) between editorial marks must be in the text it cites, that is the cited slide, or the transcript within 60 seconds of the cited time or range. A quote found only elsewhere in the transcript or slides is a WARN that names where it was found: fix the citation. A quote found nowhere is a FAIL: copy the words again, or paraphrase and drop the quotation marks. A quote with no such run at all, only short fragments between marks ("rate … balance"), cannot be checked and is a WARN: quote a whole clause, or paraphrase.

Keep the lecturer's notation. A notation clash in the slides (one letter, two meanings) goes into a CAUTION callout; the body keeps the notation. When the slides give only a numeric example, a general form may go in the body, followed by a sentence saying the slides give only the example and the general form is a rewrite. Steps the lecturer skipped may be filled in a NOTE callout, using the method the lecturer named.

The transcript is machine-made: names and numbers are often wrong ("forty years" for "four years", "80%" for "8%"). Numbers, names, institutions and formulas follow the slides. Inside a quote, correct a clear mis-hearing only when the slides confirm the right word: write that word in `[ ]` in place of the mis-heard one, and list the error in the errata section. Small talk before the lecture and during the break stays out; say in the not-covered section, in one sentence, which time range was the break. A substantive exchange during the break may go into the body or a NOTE callout, marked as during the break.

Order of writing: first pull the quotes you will use, with their sources, into a scratch file `quotes.md` in the unit folder (a working file, never a deliverable); then write the body around them; then check every sentence attributed to the lecturer against `quotes.md` and delete it or move it into a NOTE callout when it is not there. What you add is never attributed to the lecturer: it stands in a sentence that does not name the lecturer, or in a NOTE callout. Last, walk through the slides page by page: each page's definitions, formulas and examples land in some section, or the page is listed as not covered.

## Callouts

GitHub alert syntax `> [!TYPE]`, with exactly four types:
- `> [!NOTE]`: a tutor addition, not from the lecture;
- `> [!IMPORTANT]`: a key result;
- `> [!WARNING]`: a common mistake;
- `> [!CAUTION]`: transcript or slide errata and doubts.

Any other type fails the gate. Answers always go in `<details><summary>Answer</summary>…</details>`, never in a callout.

A NOTE callout holds only five kinds of content: derivation steps the lecturer skipped; numbers computed from an expression the slides only state; one or two sentences linking the unit to earlier or later material; context, a contrast or a consequence you add (see Faithful to the lecturer); a one-sentence meaning of a term the lecturer uses before defining it (see Derivations, examples and teaching order). Each box is at most 150 CJK characters or 90 words (LaTeX not counted), at most two per section. It may end with one "why" or "how" question for the reader, never a "what" question and never an item prompt. When referring to later material, write "later, when X is covered"; do not invent week or session numbers. Proper names you add yourself belong in a NOTE callout (the `terms` check skips NOTE callouts).

## Marker sections

explanation.md carries machine-readable sections between paired markers: `<!-- tal:NAME -->` opens and `<!-- /tal:NAME -->` closes. NAME is one of `pretest`, `check`, `not-covered`, `errata`. `check` occurs at most one per H2 section, at the section's end; the others at most once in the note. Authoring rule: each marker on its own line; headings stay outside the markers; never nested; never inside a code fence. An unclosed, nested, unknown or duplicated marker, or a close marker with no matching open, fails the gate (`markers`).

What the sections print:
- `pretest`: exactly the prompts of the variants assigned to phase `pre`, one per tracked concept, in the order `tutor-any-lecture items next --unit DIR --phase pre` prints them (sorted concept id), each as a numbered item followed by a `<details>` answer.
- `check`: practice items only, verbatim from items.json, each numbered and followed by a `<details>` answer. Never a tracked item.
- `not-covered`: every slide the lecture did not cover, written as `slide N`, or `slides N–M` for a run (en dash or hyphen), with a sentence on why; the break, if any, in one sentence. The gate reads this section only for slide numbers, so a unit without slides needs nothing in it: write the break and any skipped stretch of the recording in plain sentences (`- 0:12–0:50: small talk before the lecture`), or leave the section out.
- `errata`: the real transcription errors among `sources/suspects.json` (heard word, nearest slide term, time in seconds; write it as mm:ss), flagged, never silently fixed. A suspect that is an inflection of the slide's word, or simply correct, is not listed (see [teaching](teaching.md), Suspects). The lecturer's own slips go here too (say whether they corrected themselves), and slide typos with the slide number in the time column. The Should be cell names whose slip it was ("lecturer's slip, corrected") only when the transcript's speaker labels or the lecturer's own words show it; otherwise it says "speaker unclear". The gate checks only the markers of this section; with no errata, leave the section out.

Every numbered item in `pretest` and `check` needs its `<details>` answer before the next numbered item. The answer cites its source. Start the answer after one blank line below `<summary>Answer</summary>`, as in the skeleton: on the same line, the `terms` check reads "Answer" and a capitalised first word of the answer as one term.

**No restating.** The lecture prose (the note with every marker section removed) never restates an item prompt: no sentence of it may reach 0.6 containment of any prompt. For each tracked concept, the section that covers it gives the cited answer to that concept's pretest question in its own prose. The answer under each pretest item gives the result in at most two sentences, the result and the idea it rests on, with its citation, and no worked steps; the worked steps belong in the section's prose, on the lecturer's own example (see [teaching](teaching.md), items.json).

## Citations

Every claim attributed to the lecturer carries `(slide N)`, `(mm:ss)` or `(slide N, mm:ss)`; ranges `(slides 14–16)`, `(13:42–14:05)`; an estimated time is written `(~13:40)`. Past one hour write `(1:02:03)`. Full-width parentheses `（…）` are accepted. Cite the slide's footer number; if a page has none, its PDF page number. A slides-only unit cites slides only.

The gate reads a parenthesis as a citation only when it holds nothing but citation parts separated by commas: `slide N`, `slides N–M` (plural, with a range), a time, a time range, `~` directly before a time. `(slide 14-16)`, `(slides 4)` and `(see slide 4)` are not citations. A slide number above the last slide, or a time more than 2 seconds past the duration, fails the gate.

**Time links.** Write plain time citations, then always run `tutor-any-lecture cite link --unit DIR` before the gate, and run it again after edits; never write these links by hand. When source.json's `kind` is "url" or "platform" and its `url` has a time form, it turns every plain time citation outside code into a link to that second of the video, inside the parentheses, in the form of the address's platform:

| platform | address | time form |
|---|---|---|
| YouTube | `youtube.com/watch?v=…` (or `www.`, `m.`), `youtu.be/…` | `t=<seconds>s` |
| Bilibili | `bilibili.com/video/…` (or `www.`, `m.`) | `t=<seconds>` |
| Vimeo | `vimeo.com/<digits>` (or `www.`) | `#t=<seconds>s` |
| Panopto | any host, `…/Pages/Viewer.aspx?id=…` | `start=<seconds>` |

Seconds are whole; a time already in the address is replaced and its other parameters keep their order; spaces and parentheses are percent-encoded. On YouTube a time becomes `([13:42](<url>&t=822s))`. A range links its start only: `([13:42](<url>&t=822s)–14:05)`. A slide and a time: `(slide 15, [13:42](<url>&t=822s))`. The `~` stays before the bracket: `(~[13:40](<url>&t=820s))`. Linked times are left alone, so running it again changes nothing; it prints `{"path", "linked"}`. When it cannot link, the note is unchanged and `reason` says why: `no source.json in the unit: no video to link to`, `the source is not an online video`, `source.json has no video address`, or `no time links for <host>: the times stay plain`. The gate's `time_links` WARN (under `citations`) names the time citations of a linkable unit that are not linked yet (run `cite link`), and any time link whose address points at another time than its text or holds no time. Citation strings in items.json, cards.json and map.json stay plain.

## Length by goal and duration

Per minute of lecture, CJK characters / words of lecture prose (counted as in Units of measure, above); deep | exam | quick:

| per minute | deep | exam | quick |
|---|---|---|---|
| total length | 44–89 / 26–53 | 30–70 / 18–42 | 10–25 / 6–15 |
| time citations | ≥ 0.67 | ≥ 0.5 | ≥ 0.2 |
| verbatim quotes | ≥ 0.22 | ≥ 0.15 | ≥ 0.07 |

**The length window.** The note's length divided by the minutes must fall in the row's range, with one exception for short lectures: the top of the window is never below 400 words (800 CJK characters) in total, so a short lecture may still have real paragraphs. The top per minute is therefore `max(table top, 400 / minutes)` for words and `max(table top, 800 / minutes)` for CJK characters; the bottom does not change. For a 3-minute lecture at goal deep that is 26–133.3 words per minute, 78 to 400 words in all.

Over the top of the window, first check for content the lecturer did not give; under the bottom, check the slide-by-slide walk for gaps. When the duration is unknown these per-minute checks are skipped with a warning.

**Goal and coverage.** No extra sections inserted into lecture prose; goal changes length and coverage. Every goal keeps citations and faithfulness. There is no "speed-read" block, no "to-do for next week", no "interview questions", no summary at the end.

## Structure rules the gate enforces

- No H4 or deeper; no heading that starts with an outline prefix (`1.`, `2)`, `1.2`, `1.2.3`) (FAIL). A heading that starts with a plain number passes.
- At most `max(16, ceil(16 × minutes / 90))` H2s (WARN).
- An H2 section of fewer than 150 CJK characters / 90 words is thin (WARN); a section whose prose is all inside marker sections is not counted.
- A paragraph over 300 CJK characters / 180 words is too long (WARN).
- At most 3 inline quotes per paragraph, and a paragraph with a quote carries a citation (FAIL). Quotes are text in `"…"`, `“…”`, `„…“`, `„…”`, `«…»`, `»…«`, `‘…’`, `‚…‘`, `‹…›`, `「…」`, `『…』`, `＂…＂` on one line, counted from 15 characters, or from 6 when the span holds a CJK character.
- Every non-callout blockquote is cited in it or on the next non-blank line (FAIL).
- At most 15 bold spans (WARN); `==highlights==` at most 8 for obsidian and none for markdown (WARN).
- Bullet lines at most 10% of the prose lines (WARN); table rows and table-of-contents lines are not bullet lines.
- The quote measure (WARN), over the lecture prose. Its top side, *quoted characters*, is the non-space characters inside every inline quote of 15 or more characters, or 6 or more when the span holds a CJK character (the marks not counted), plus those of every non-callout blockquote line (the `>` not). Citations and link addresses are left out on both sides: a citation group counts nothing, a link or image counts its text only and a URL nothing, so `cite link` leaves the measure as it was. A note that quotes a lecture in its own script divides them by all non-space characters of the prose, other markup included, and expects 10–40% (`quote_share`). A Chinese, Japanese or Korean note of a lecture in another script divides them by its length in CJK characters (`quote_ratio`), and the window follows `quote_density` in plan.json: light 0.15–0.6, standard 0.4–1.2 (the default), dense 1.0–2.0. `quote_ratio` applies only to a Chinese, Japanese or Korean note of a lecture in another script; every other pair uses `quote_share`, including an English note of a Chinese lecture and a Japanese note of a Chinese lecture. Worked example: a Chinese note has 3,000 CJK characters of prose and quotes an English lecture 30 times, each quote about as long as “the interest you earned last year earns interest too”, which counts 44 (letters only: the spaces and the marks count nothing); 30 × 44 = 1,320 quoted characters over 3,000 CJK characters is a ratio of 0.44: inside the light and the standard window, below the dense one.
- TOC links must match H2s: `[[#Heading]]` for obsidian, `[text](#slug)` for markdown (FAIL).
- Callout types and `<details>` answers as above; marker problems (FAIL).

Besides structure, verify checks citations and quotes (above), slide coverage (every slide is cited or listed in `tal:not-covered`), terms, numbers with units, the items, cards and map, and the stock phrases listed for the note language ("delve", "it's worth noting", "in conclusion", "in summary", 综上所述 and similar; English and Chinese have lists), found as whole words in your own words only: quotations, blockquotes that are not callouts, code and links are not read, while callouts, marker sections, headings and answers are; see [gate](gate.md). The terms and numbers checks read the lecture prose only: the marker sections, NOTE callouts, code and math are left out, so a number that appears only in the pretest or an answer does not count as in the note.

## Exercises, formula table and v1 structures

- **v1 structures mapped to the v2 note model.**
  - v1's fixed "self-test" section (6–10 questions, answers in `> [!note]-` boxes) is replaced by `tal:check` sections: at most one per H2 section, at its end, built only from practice items, each answer inside `<details><summary>Answer</summary>…</details>`. The pretest is the `tal:pretest` section; neither marker section holds hand-written questions that are not in items.json.
  - v1's `> [!warning]` errata callout and correction table become a `> [!CAUTION]` callout inside the `tal:errata` section (rows: time, heard, should be).
  - v1's YAML front matter is dropped: the gate and the CLI read plan.json and source.json, not the note's front matter. In particular there is no `lecturer:` field and no teacher name anywhere. The "how to read this note" paragraph is kept, shortened, as the first lines after the H1 and the TOC, in the note language.
  - v1's "Exercises" section and formula quick-reference table are optional sections: allowed only when the source has exercises or formulas. They are ordinary H2 sections of lecture prose (cited, within the length and bullet limits), and any exercise answer is folded in `<details>`. The formula table may use table rows, which are not bullet lines.
  - v1's working file `quotes.md` stays a scratch file in the unit folder's working area, never a deliverable and never listed in the output table.
- **Exercises.** For each exercise say which formula applies and what to watch for; put the numeric answer, computed with code rather than by hand, in `<details><summary>Answer</summary>…</details>`. When the wording is ambiguous, pick the reading of the slides' closest example, say which and why, and give the other reading's answer in the same `<details>`.
- **Formula table.** Columns: number, formula, where it is used. One line after the table may state the exam conventions the lecturer gave. The note ends there.

## Example

For a complete note that passes the gate, run `tutor-any-lecture selftest --keep DIR`: it leaves a generated unit in DIR.
