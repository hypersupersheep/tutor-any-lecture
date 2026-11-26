# Tutor Any Lecture

**A tutor built from your own lectures: it tests you, cites the lecturer, schedules your review.**

It quizzes you first, explains the lecture in the lecturer's own words, cites the minute and the slide, quizzes you again, and sends your misses to Anki.

[简体中文](README.zh-CN.md)

Tutor Any Lecture is an agent skill and a command-line tool, both named `tutor-any-lecture`. Your agent reads the lecture, writes the note and asks the questions; the command gets the transcript, checks the note before you see it, logs your answers and works out which reviews are due.

## What one lecture becomes

Each lecture becomes a unit: the folder `<workspace>/courses/<course>/<unit>/`, where the workspace is `~/TutorAnyLecture` unless you change it.

| File | What it is |
|---|---|
| `explanation.md` | The note, in lecture order. Every claim about what the lecturer said is cited `(slide N)` or `(mm:ss)`; for a video link, each time links to that second of the video. It holds a pretest section, short checks with folded answers, the slides the lecture did not cover, and an errata list for misheard captions. |
| `items.json`, `assignment.json` | The questions: three parallel variants of each tracked concept, assigned at random to the pretest, the post quiz and the day-7 review. |
| `cards.json`, `cards.tsv` | Anki cards. `cards.tsv` imports through Anki's File, Import. |
| `map.json`, `overview.mmd` or `overview-<view>.mmd` | The concept map: five node kinds (definition, theorem, method, example, pitfall), a verb on every edge, at most 12 nodes per view, written out as Mermaid that GitHub renders. |
| `verify.json` | The gate's result. |
| `sources/` | The transcript, the slide text, and where the material came from. |
| `progress/<course>.jsonl`, `progress/<course>.md`, in the workspace | Every quiz attempt, and the progress page. |

The note is written in the language of the `note_language` setting, by default the language you talk to your agent in. The `outputs` setting picks which of these a unit gets; the explanation is always one of them.

## A look at the bundled sample

This is part of the note of the bundled synthetic sample, a three-minute mini-lecture on compound interest with three slides, which `tutor-any-lecture selftest` runs through the gate. The whole note is [src/tutor_any_lecture/data/sample/explanation.md](src/tutor_any_lecture/data/sample/explanation.md).

> The lecturer starts from a bank that pays a yearly rate on a deposit (0:09). Slide 1 gives the two ways to pay it. Under simple interest "the rate applies to the deposit only"; under compound interest "the rate applies to the balance, past interest included" (slide 1).
>
> The rate is the same in both; only its base differs. "Last year's interest is now part of the balance, and this year it earns interest too" (0:36). The lecturer calls this the whole trick and adds that "people call it interest on interest" (0:45). So compounding is not a higher rate but a base that grows every year by the interest already earned.

## How it works

1. **Check.** The skill's Step 0 runs `tutor-any-lecture doctor --json --skill <skill folder>`, and on first use `tutor-any-lecture selftest`.
2. **Acquire.** The transcript and the slides go into the unit folder. Captions are used before speech recognition.
3. **Plan.** The agent writes plan.json, with five tracked concepts (all of them when the lecture has fewer).
4. **Write.** The agent writes the items, then the note with plain time citations, which `tutor-any-lecture cite link --unit DIR` turns into links for a video link, then the cards and the map.
5. **Gate.** `tutor-any-lecture verify --unit DIR` runs nine checks: citations, coverage, terms, numbers, structure, items, cards, map and banned phrases. A FAIL blocks delivery; the agent fixes the file and reruns until the result is PASS. What each check catches is in [skills/tutor-any-lecture/references/gate.md](skills/tutor-any-lecture/references/gate.md).
6. **Pretest.** Before you see the note, the agent asks the pretest in chat, one question at a time, and asks how sure you are before it grades your answer.
7. **Post quiz.** After you have read the note, it asks the post quiz the same way. The questions you miss become Anki cards.
8. **Reviews.** Reviews come 1, 7 and 21 days after your first post quiz (days 1 and 21 are optional), and `tutor-any-lecture progress render --course C` writes the progress page.

## Install

**Requirements:** an agent that loads skills and runs shell commands (Claude Code, Codex and others); [uv](https://docs.astral.sh/uv/) or Python 3.10+; git, for route C's clone and for the first-use install of routes A and D; Node.js only for `npx skills add`. Works on macOS, Linux and Windows x64.

### A. npx skills add (recommended)

```bash
npx skills add hypersupersheep/tutor-any-lecture
```

This copies the skill into your agent's skills folder. Success check: your agent lists `tutor-any-lecture` among its skills. The command-line tool is installed on first use: the skill's Step 0 runs `tutor-any-lecture doctor --json --skill <skill folder>`, and when the command is missing it offers to run the installer that ships inside the skill, `skills/tutor-any-lecture/scripts/install.sh` (on Windows `skills/tutor-any-lecture/scripts/install.ps1`), with `--cli-only` (`-CliOnly`), since the skill is already in place.

### B. Claude Code plugin

```text
/plugin marketplace add hypersupersheep/tutor-any-lecture
/plugin install tutor-any-lecture@tutor-any-lecture
```

Success check: `/plugin` shows `tutor-any-lecture` as installed. The command-line tool is installed on first use, as in route A.

### C. Ask your agent to install it

Paste this into your agent:

```text
Install tutor-any-lecture for me. After each step, check the result. If a check fails, stop and tell me what you saw.

1. Clone https://github.com/hypersupersheep/tutor-any-lecture into a folder of your choice.
   Check: the folder contains install.sh and install.ps1.
2. In that folder, run `bash install.sh --yes` on macOS or Linux, or `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Yes` on Windows (also from Git Bash; `bash install.sh` is not for Windows). Do not pipe any download into a shell. It can take several minutes.
   Check: the exit code is 0, and the last line it printed is the selftest command with the command's full path. On exit code 3, show me what it printed and stop.
3. Run the command from that last line (on Windows, in PowerShell).
   Check: the exit code is 0. The same full path is stored in the file ${XDG_CONFIG_HOME:-$HOME/.config}/tutor-any-lecture/cli-path (on Windows: %APPDATA%\tutor-any-lecture\cli-path) for later sessions.
4. Look for tutor-any-lecture/SKILL.md in your own skills folder (for example ~/.claude/skills/ or ~/.codex/skills/).
   Check: the file exists. If it does not, run the installer again with `--agents` followed by claude, codex or agents (on Windows: `-Agents`).
```

The installer uses `uv tool install` when uv is present. Otherwise it creates a private environment in `~/.tutor-any-lecture/venv` (`%LOCALAPPDATA%\tutor-any-lecture\venv` on Windows). It installs nothing into your system Python and never downloads a script to run it. It then records the command's full path in the `cli-path` file, copies the skill to the agents it finds (`~/.claude`, `~/.codex`, `~/.agents`), runs `tutor-any-lecture doctor --json --skill <skill folder>` on its own skill folder, and prints the selftest command as its last line. Exit codes: 0 ready, 1 failed or cancelled, 2 bad option, 3 needs action (it prints what to do). Add `--dry-run` (`-DryRun`) to see the plan without changing anything, and `--cli-only` (`-CliOnly`) to install the command without copying the skill.

Speech recognition is an add-on, needed only for audio or video that has no captions. It is a large download (several hundred megabytes, more on Apple Silicon), so the installer leaves it out unless you add `--with-asr` (`-WithAsr`); you can run the installer again with it later. Captions, transcripts and slides work without it.

### D. Claude.ai upload

Zip the folder `skills/tutor-any-lecture` and upload it as a skill in Claude.ai. Success check: Claude.ai lists `tutor-any-lecture` among your skills. Claude.ai cannot process large local videos, so this route works from slides, captions and transcripts only. Step 0 still runs there; when doctor cannot become ready, use an agent on your own computer.

## Quick start

With route C, run the selftest command that the installer printed as its last line. With routes A, B and D the agent runs selftest itself on first use. When the command is on your PATH, this is the same:

```bash
tutor-any-lecture selftest
```

It runs the bundled sample through the whole pipeline, the gate included. It needs no network and no speech model; exit code 0 means the install works. Then give your agent a lecture: "Teach me this lecture: <file, folder or link>".

## What to ask

Ask your agent in plain words; it picks the commands.

| You say | What happens |
|---|---|
| "Teach me this lecture: week4.mp4" | A local video or audio file is transcribed on your computer with the speech-recognition add-on. With a caption or transcript file beside it, that file is imported instead. |
| "Teach me the lecture in this folder" | `acquire route` sorts the folder's files and plans the steps; the agent asks you only what it cannot tell. |
| "Teach me this video: <YouTube or Bilibili link>" | Captions are used first. The audio is downloaded only with the audio switch on (see Safety and privacy). |
| "Use this transcript: lecture.vtt" | An SRT, VTT, JSON or timestamped TXT transcript is imported. |
| "Make a note from these slides: slides.pdf" | A slide PDF alone makes a slides-only unit, whose note cites slides, never times. |
| "Teach me this Panopto recording" | The transcript is read from the Panopto viewer. This needs an agent with browser tools. |
| "Quiz me on <course>" | The agent asks what is due; when nothing is, practice items. |
| "What is due today?" | `progress due` lists the post quizzes and reviews due. |
| "Show my progress" | `progress render` writes the course's progress page. |

Every source adapter is marked experimental in its reference until a real run has been recorded: see the "Verified by" section of each file under `skills/tutor-any-lecture/references/adapters/`.

## Optional extras

Extras are optional and never part of the gate.

- **Audio lesson.** Experimental, for Apple Silicon only, and its rules are written in Chinese. It is made only when you ask for it: the agent writes a script for listening and runs `skills/tutor-any-lecture/scripts/tts_synthesize.py` with a Python that has `mlx-audio` and numpy installed, with ffmpeg and ffprobe on PATH.
- **Review sheet and hand-drawn map.** Two separate companion skills: `skills/handwritten-notes-pdf/` turns a light markup file into a grid-paper PDF, and `skills/excalidraw-concept-map/` turns a Mermaid file into an Obsidian `.excalidraw.md`, with an optional `.excalidraw` file and a PNG. Their instructions are written in Chinese. `npx skills add` offers all three skills and the Claude Code plugin brings all three, while the installer of route C copies only `skills/tutor-any-lecture` and does not copy them. So after route C, or for any other agent, copy `skills/handwritten-notes-pdf/` and `skills/excalidraw-concept-map/` into your agent's skills folder yourself. They need a Python with `websocket-client`, which you install by hand, and Chrome or Chromium, which they find through `CHROME_PATH`, the default Chrome location on macOS, or `google-chrome`, `google-chrome-stable`, `chromium` or `chromium-browser` on PATH; on Windows, set `CHROME_PATH`. They load their libraries and fonts from the network each time they render.

## Safety and privacy

- **No passwords.** It never types, stores or asks for a password. At a login page or a "Verify you are human" check it stops and hands over to you.
- **No browser cookies.** It never reads them.
- **Read-only on every platform.** No submissions, posts or bookings. In Panopto it never presses Edit, Cuts, Streams, Download or Share.
- **Downloads follow the `downloads` setting.** `ask`, the default, asks before every download a platform itself offers; `allow` permits those without asking. DRM is never circumvented.
- **Video audio follows `public_video_audio`.** It is off by default. Turning it on shows a notice and records the day you accepted it. From then on, when a video has no usable captions, the audio track alone is downloaded, transcribed on your computer and deleted. The decision and the responsibility are yours for every address you give. A recording behind a sign-in is out of reach, because the tool never uses your login.
- **What stays local.** There is no telemetry. The tool keeps transcripts, items and progress on your computer. Your agent reads them as it reads any file you give it, so they go to that agent's model provider under its terms. The tool uses the network for the addresses you give it, for installing, once for the speech model on the first transcription, and, for the extras, for the audio model's first download and the libraries and fonts the companion pages load.
- **Personal study.** Do not redistribute recordings, or notes made from copyrighted lectures.

## FAQ

### Which agents does it work with?

Any agent that loads skills and runs shell commands. The skill carries notes for Claude Code and Codex, and a generic note for the others, under `skills/tutor-any-lecture/references/agents/`. Browser tools are needed only for Panopto and Moodle pages.

### Which sources can it read?

Local video and audio files, folders of materials, YouTube and Bilibili links, transcript files (SRT, VTT, JSON or timestamped TXT), slide PDFs, and Panopto recordings through an agent with browser tools. A PPTX deck or photos of slides must be exported to PDF first.

### Does anything leave my computer?

There is no telemetry, and the tool keeps transcripts, items and progress on your computer. Your agent reads those files as it reads any file you give it, so they go to that agent's model provider under its terms. The tool uses the network for the addresses you give it, for installing, and once for the speech model on the first transcription; the extras also download the audio model once and load libraries and fonts when they render.

### Can the notes be in English, or another language?

Yes. The note is written in the language of the `note_language` setting, by default the language you talk to your agent in. To fix it, run `tutor-any-lecture profile set note_language en` with the language code you want.

### Do I need a Mac?

No. Speech recognition uses mlx-whisper on Apple Silicon and faster-whisper elsewhere, and the rest runs on macOS, Linux and Windows. Only the audio lesson needs Apple Silicon.

### How do I get the cards into Anki?

Import `cards.tsv` with Anki's File, Import. The cards keep stable ids, so importing the file again updates them without losing their review history.

### When are reviews due?

1, 7 and 21 days after your first post quiz on a unit; the day-1 and day-21 reviews are optional. Ask your agent "What is due today?", or run `tutor-any-lecture progress due --course C`.

### Can I turn the quiz off?

Yes: `tutor-any-lecture profile set outputs "[explanation, cards, map]"` leaves out the pretest and the quiz. The explanation always stays.

### What does Windows need?

Windows x64; Windows PowerShell 5.1 or PowerShell 7 to run `install.ps1` (`bash install.sh` is not for Windows, Git Bash included); uv or Python 3.10+; and git for route C and for the first-use install of routes A and D.

## Upgrading and removing

### Upgrading

Route C: run `git pull` in the checkout, then the installer again (`bash install.sh --yes`, or on Windows `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Yes`), which rebuilds the command and copies the skill again. Routes A, B and D: get the skill again, by rerunning `npx skills add hypersupersheep/tutor-any-lecture`, by updating it from Claude Code's `/plugin` menu, or by uploading a new ZIP. Such an update brings a new skill but keeps the old command, so when the skill's Step 0 reports that the command and the skill differ (the `skill_version` check of `tutor-any-lecture doctor --json --skill <skill folder>`), it offers to rerun the skill's installer with `--cli-only` (`-CliOnly` on Windows). Your settings and units are kept.

### Removing

- The command: `uv tool uninstall tutor-any-lecture` when uv installed it; otherwise delete the folder `~/.tutor-any-lecture` (`%LOCALAPPDATA%\tutor-any-lecture` on Windows).
- The config folder `${XDG_CONFIG_HOME:-$HOME/.config}/tutor-any-lecture` (`%APPDATA%\tutor-any-lecture` on Windows), which holds `cli-path` and `profile.yaml`.
- The skill copies: `~/.claude/skills/tutor-any-lecture`, `~/.codex/skills/tutor-any-lecture` and `~/.agents/skills/tutor-any-lecture`. For routes A and B, remove the skill with the tool you added it with.
- The workspace `~/TutorAnyLecture` holds your units and progress: delete it only when you no longer want them.

## Contributing

Contributions are welcome, and a platform adapter is the suggested first one. Please report a security problem privately, never in a public issue.

## Acknowledgements

- [PyYAML](https://github.com/yaml/pyyaml), [pdfplumber](https://github.com/jsvine/pdfplumber), [yt-dlp](https://github.com/yt-dlp/yt-dlp), and [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg), which brings [FFmpeg](https://ffmpeg.org).
- [mlx-whisper](https://github.com/ml-explore/mlx-examples) and [faster-whisper](https://github.com/SYSTRAN/faster-whisper), for speech recognition.
- [anki-card-forge](https://github.com/FrostySL/anki-card-forge), from which the card rules are adapted; its notice is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- The [Agent Skills](https://github.com/anthropics/skills) format.
- For the extras: [mlx-audio](https://github.com/Blaizzy/mlx-audio) with Qwen3-TTS, [Excalidraw](https://github.com/excalidraw/excalidraw), [mermaid-to-excalidraw](https://github.com/excalidraw/mermaid-to-excalidraw), [KaTeX](https://katex.org), and the Patrick Hand, Xiaolai SC and Excalifont fonts that the companion pages load.

## License

[MIT](LICENSE). The libraries and fonts that the companion pages load at render time keep their own licences.
