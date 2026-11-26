Adapter: transcript import. A transcript or caption file the learner already has.

## Platform

Any source that exports timed text: caption files, a speech-to-text tool's output, and the transcript exports of meeting and lecture-capture platforms such as Zoom, Teams and Panopto. Command: `tutor-any-lecture acquire import --file F --unit DIR [--duration SEC | --media FILE] [--force]`; `--media` reads the lecture's length from its video or audio file.

## URL patterns

None: a file path. Paths with spaces or non-Latin characters work.

## Where transcripts/captions live

In the file the learner gives you. The parser is chosen by the file's suffix:
- `.srt`: SubRip, with `,` or `.` before the milliseconds;
- `.vtt`: WebVTT, header and cue settings allowed;
- `.json`: Whisper-style segments, either `{"segments": [{"start", "end", "text"}, …]}` or a bare list of such objects (times in seconds);
- `.txt`: timestamped text, one line per segment starting with `[m:ss]` or `[h:mm:ss]`; a line without a stamp continues the previous segment. A `.txt` with no `[m:ss]` stamp is read as WebVTT when its first line is `WEBVTT`, as SubRip when its first timing line is SubRip's (`00:00:01,000 --> 00:00:02,000`), and else in the layouts of the `.docx` bullet, which is how a Zoom transcript saved in the meeting reads (`[Alice Smith] 00:00:03`, then the text);
- `.docx`: a Teams transcript saved as Word, read in three layouts: a range line such as `0:0:3.570 --> 0:0:7.110`, then the speaker and the text; the speaker and a start time on one line, such as `Alice Smith   0:03` or `[Alice Smith] 00:00:03`, then the text; `[m:ss]` stamped lines. Speaker names and the lines before the first time are left out.

Files may be UTF-8 with or without a byte-order mark, with Windows or Unix line endings. Any other file, such as `.doc`, `.rtf` or `.pdf`, ends in `error` with a message that lists the five kinds; ask the learner for one of them.

## Read-only steps

1. When the recording itself is at hand, pass it as `--media FILE`; otherwise, when the learner already gave the lecture's length, pass it in seconds as `--duration SEC` (not both). If they did not, do not ask for it on the first run. Without it the duration is unknown: the health check cannot measure coverage, and the gate's per-minute checks become warnings.
2. If there are slides, run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F` for a PowerPoint deck), before or after the import; the source.json the import writes only gains the deck's digest, and nothing else in it changes.
3. Run `tutor-any-lecture acquire import --file F --unit DIR`, with the `--media FILE` or `--duration SEC` of step 1 when there is one.
4. Outcome, one JSON object on stdout:
   - `{"status": "ok", "health": {…}}`, exit 0: `sources/transcript.json` and `sources/source.json` (`"kind": "transcript"`, `"acquisition": "import"`) are written;
   - `{"status": "unhealthy", "health": {…}}`, exit 1: the files are written, but read `status`, show the health numbers (`coverage`, `repetition`, `spots_ok`, `overrun`, `loop`) and tell the learner before planning on that transcript. A transcript that covers only part of the lecture, or ends after the given duration, lands here;
   - `{"status": "error", "message": …}`, exit 1, nothing written: the file does not exist, is not one of these kinds, held no timed text (`no timed segments found`), was not UTF-8, or could not be parsed. Show `message` to the learner and ask for another export;
   - exit 3, one line on stderr: the unit already has `sources/transcript.json`; rerun with `--force` to replace it.
5. Run `tutor-any-lecture slides suspects --unit DIR` when the unit has slides.

## Downloads offered?

Nothing is downloaded. Where the learner gets the file depends on their platform; if `downloads` is ask, ask before you fetch an export for them from a page.

## Known pitfalls

- A plain-text transcript with neither `[m:ss]` stamps nor a speaker-and-time line has no timed segments and fails with `error`; ask for the timed export.
- The last segment of a timestamped TXT has no end time; it is taken as 5 seconds, or up to the duration.
- Speaker names written into the cue text stay in it, so leave them out of quotes; VTT voice tags and the speaker lines of a DOCX export or a Zoom TXT are dropped.

## Verified by (name/date) or "experimental"

experimental
