Adapter: local files. A recording or slide deck already on the learner's computer, transcribed on this machine.

## Platform

The learner's own files: a lecture video or audio recording, and the slide PDF or PowerPoint deck, or key frames taken from a video that comes without slides. Speech recognition (ASR) runs locally: mlx-whisper on Apple Silicon, faster-whisper elsewhere. It is an add-on that the installer adds with `--with-asr` (Windows `-WithAsr`); doctor is ready without it. Commands:
- `tutor-any-lecture acquire local --file F --unit DIR [--force] [--budget-minutes N]` for a video or audio file (the audio track is extracted with ffmpeg first);
- `tutor-any-lecture transcribe --audio F --unit DIR [--backend B] [--model M] [--budget-minutes N] [--force]` for an audio file transcribed as it is, optionally with a chosen backend (mlx or faster) and model;
- `tutor-any-lecture slides --pdf F --unit DIR [--images]` for the slides;
- `tutor-any-lecture slides --pptx F --unit DIR` for a PowerPoint deck (text and speaker notes, no page images);
- `tutor-any-lecture keyframes --video F --unit DIR [--force]` for the key frames of a video with no slides.

## URL patterns

None: file paths. Paths with spaces or non-Latin characters work, because every command takes its arguments as a list. Video: .mp4, .mkv, .mov, .webm, .avi, .m4v. Audio: .mp3, .m4a, .wav, .aac, .flac, .ogg. For a whole folder of materials, `tutor-any-lecture acquire route --folder <materials> --unit DIR` sorts the files and plans these commands (see SKILL.md, Acquire).

## Where transcripts/captions live

Nowhere yet: local ASR makes the transcript. If the learner already has a transcript or caption file for the recording, use the [import](import.md) adapter instead; it is faster and usually more accurate.

## Read-only steps

1. **Slides first.** When there is a slide PDF, run `tutor-any-lecture slides --pdf F --unit DIR` (a PowerPoint deck: `tutor-any-lecture slides --pptx F --unit DIR`) before any transcription: the ASR prompt is built from the slide terms in `sources/slides/pages.json`. It prints `{"status": "ok", "pages": N, "labelled": M, "path": …}` (M is the number of pages with a footer number; with `--pptx` also `"notes": K`, the slides with speaker notes) and exits 0. It writes `sources/slides/pages.json` and, when the unit has no `sources/source.json`, a slides-only `source.json` (`"kind": "slides-only"`); an existing source.json gains the deck's digest; nothing else in it changes. Running it again replaced pages.json without `--force`. `--images` (with `--pdf` only) also saves one PNG per page.
2. **Slides only.** With no recording, stop here: the unit is slides-only, and its note cites slides only, never times.
3. **Key frames.** For a video that comes with no slide deck and no photos of slides, run `tutor-any-lecture keyframes --video F --unit DIR`. It samples the video every 2 seconds, drops blank frames and near-duplicates of a frame already kept, keeps frames at least 8 seconds apart and at most 120 of them, and saves each full size as `sources/keyframes/frame-NNN.jpg`. They become the unit's pages in `sources/slides/pages.json`: page N has `image` (`../keyframes/frame-NNN.jpg`, relative to `sources/slides/`), `time` (the second it was taken at) and an empty text. It prints `{"status": "ok", "frames": N, "candidates": M, "path": …}` (M is the number of frames sampled) and exits 0; source.json is left as it is. An existing pages.json stops it with exit 3 and one stderr line: rerun with `--force` to replace the pages and the key frames. It reads a file on this computer and never a link: from a video site the tool takes captions or audio only. It decodes the whole video once, so a long lecture takes minutes: use a long timeout, the longest your shell tool allows. Cite frame N as (slide N), and give its time as well when that helps; list the frames you do not use in the not-covered section. When Step 0's `vision` check is ok, read each frame and give its page the text you read with `tutor-any-lecture slides text --unit DIR --page N --file F`, before `acquire local` (the ASR prompt reads slide terms; the frame's time stays). Otherwise leave the text empty and do not quote a frame. The tool has no OCR for key frames: without image reading, the text stays empty.
4. **Transcribe.** Run `tutor-any-lecture acquire local --file F --unit DIR` (or `tutor-any-lecture transcribe --audio F --unit DIR` for an audio file as it is). It can run for many minutes: use the longest timeout your shell tool allows, or run it in the background; a stopped run cleans up and can be started again. The first transcription may download the speech model. The time budget defaults to `max(30, 2 × the media length in minutes)` minutes; `--budget-minutes N` changes it.
5. **Outcome.** One JSON object on stdout:
   - `{"status": "ok", "health": {…}}`, exit 0: `sources/transcript.json` and `sources/source.json` (`"kind": "local"`, `"acquisition": "asr"`) are written;
   - `{"status": "unhealthy", "health": {…}}`, exit 1: the files are written, but read `status`, show the health numbers (`coverage`, `repetition`, `spots_ok`, `overrun`, `loop`) and tell the learner before planning on that transcript;
   - `{"status": "error", "message": …}`, exit 1, nothing written: the input file does not exist or is a folder, no timed text came out, the file could not be read or decoded, or ffmpeg or the ASR backend failed. Show `message` to the learner;
   - exit 3, one line on stderr and no JSON: transcription did not finish within the budget (rerun with a larger `--budget-minutes`); speech recognition is not installed (the line says so: tell the learner it is a large download, several hundred megabytes and more on Apple Silicon, and with their agreement run the installer again with `--with-asr`, Windows `-WithAsr`, as SKILL.md, Step 0 says); a backend named with `--backend` is unknown or not installed (the line names the package); or the transcript already exists (rerun with `--force` to replace it).
6. **Suspects.** Run `tutor-any-lecture slides suspects --unit DIR`. On a run it printed `{"status": "ok", "suspects": N}` and exited 0, writing `sources/suspects.json`, a list of `{"time", "heard", "nearest", "ratio"}` (time in seconds). Run before any transcript exists, it prints the error object `{"status": "error", "message": "transcript not found: …; run an acquisition first"}` and exits 1. It never edits the transcript.

## Downloads offered?

Nothing from the internet, except the speech model on the first transcription (doctor's `asr_model` check reports whether it is cached). The learner's files are only read; the extracted audio is a temporary file that is deleted.

## Known pitfalls

- On a machine without a GPU a 90-minute lecture can take a long time; check doctor first and raise `--budget-minutes` rather than retrying blindly.
- Recognition is weakest on names, numbers and formulas. The slide terms in the ASR prompt help; `slides suspects` flags what remains, and the note's errata section reports it. The transcript itself is never edited.
- Key frames and a slide deck do not mix in one unit: `keyframes` and `slides` each replace pages.json with their own pages, and a deck's digest stays in source.json after `keyframes` replaces its pages.
- A recording that starts long before the lecture (room noise, a break) can lower the health numbers; tell the learner rather than trimming the file yourself.

## Verified by (name/date) or "experimental"

experimental
