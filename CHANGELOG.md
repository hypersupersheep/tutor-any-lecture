# Changelog

Newest first. Version ids are `X.Y.Z` for a release, `X.Y.Z-rc.N` for a release candidate and `X.Y.Z-dev.N` for work in progress, which is never tagged; a release's tag is `v` followed by its id.

## 2.0.0-dev.0

- Install it on macOS, Linux or Windows with one installer script, which sets up the `tutor-any-lecture` command and adds the skill to Claude Code, Codex or any agent that reads skills from `~/.agents`.
- Start from what you have: a video or audio file, a YouTube or Bilibili link, a Panopto recording, a transcript or caption file (a Teams DOCX export or a Zoom transcript TXT too), a slide PDF or PowerPoint deck, or photos of slides when your agent can read images. A subtitle track inside a video file is used first, and a recording without captions is transcribed on your own computer once you add speech recognition. A video without slides gives key frames that the note cites as slides. Experimental adapters, written from public documentation, describe Canvas, Blackboard, Brightspace, Echo360, Kaltura, Zoom and Teams/Stream.
- Take a short pretest before you read, then read an explanation note in which every claim about what the lecturer said cites its slide or its time in the recording.
- After reading, answer a graded quiz, saying how sure you are before you hear the result; reviews of the same ideas come back one, seven and twenty-one days later with new versions of the questions.
- Get Anki cards for the core ideas, an extra card for each quiz question you missed, and a concept map of the lecture, as Mermaid flowcharts and as editable Excalidraw drawings.
- See your quiz results and what is due next on a progress page for each course, written by `progress render` in your note language (English or Chinese), opening with one sentence and a chart of your scores.
- Every note passes an automatic check before you see it: citations, slide coverage, structure, quiz items, cards and the map are checked, and nothing is delivered while a check fails.
- Run `tutor-any-lecture doctor` to see whether your computer is ready and how to fix what is missing; a built-in self-test runs a bundled sample lecture through the whole process offline, and a second bundled sample shows the same lecture as a Chinese note.
