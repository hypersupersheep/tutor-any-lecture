Adapter: photos of slides. Three or more JPEG or PNG photos the learner took of the slides (on a phone, from the screen or the projection) become the unit's pages; you read each photo and give its text.

## Platform

Photos on the learner's computer, with no slide PDF or deck. This works only for an agent that can read images: Step 0 shows you `assets/vision-probe.png` and passes the word you read to doctor, and its `vision` check is ok only when that word is right. When `vision` is not ok, or Step 0 ran with `--vision-word none`, stop here: tell the learner that photos cannot be used by this agent and ask for the slides as a PDF (then `tutor-any-lecture slides --pdf F --unit DIR`). Commands:
- `tutor-any-lecture slides --photos <photo files> --unit DIR [--force]` copies the photos into the unit, one page each;
- `tutor-any-lecture slides text --unit DIR --page N --file F [--time S] [--force]` gives page N the text in the UTF-8 file F.

## URL patterns

None: file paths, given one per argument (`<photo files>` stands for them). Only `.jpg`, `.jpeg` and `.png` are read, in any letter case; HEIC photos are not: ask for them as JPEG or PNG. Pages follow the natural order of the file names, whatever the order on the command line: digits count as numbers and letter case is ignored, so `IMG_2.jpg` comes before `IMG_10.jpg`. When the names do not follow the slides' order, ask the learner to rename them first. `tutor-any-lecture acquire route --folder <materials> --unit DIR` plans the `slides --photos` step, in this order, for a folder with three or more such photos and no PDF or deck.

## Where transcripts/captions live

Photos hold no transcript and no text the tool can read: the text of each page is what you read in its photo. A recording of the same lecture is acquired as usual (see [local](local.md), [import](import.md), [url](url.md)), after the pages have their text.

## Read-only steps

1. **Copy.** Run `tutor-any-lecture slides --photos <photo files> --unit DIR`. It copies page k to `sources/slides/photo-<k:03d>.jpg` (or `.png`), turned upright and scaled to 2000 px on its longer side when needed, and writes `sources/slides/pages.json` with empty text; when the unit has no source.json it writes a slides-only one (`"kind": "slides-only"`); in an existing source.json the photos' digests take the place of any earlier slides' digests, and nothing else changes. It prints `{"status": "ok", "pages": N, "path": …}`, exit 0.
2. **Read each page.** For each page, open `sources/slides/<image>` (the `image` of its entry in pages.json) and write only what the slide says, in reading order (title, then the body, line by line), to a UTF-8 text file. Add nothing of your own: no summary, no explanation, no text you guess where the photo is unreadable. Then run `tutor-any-lecture slides text --unit DIR --page N --file F`. It prints `{"status": "ok", "page": N, "remaining": [...], "path": …}`, exit 0; `remaining` lists the pages that have an image and no text yet. Follow it until it is empty.
3. **Before any transcription.** Give every page its text before you acquire the recording: the ASR prompt and `slides suspects` read the slide terms from pages.json.
4. **Time.** Pass `--time S` only when you know the second of the recording at which the slide is shown (for example from a time stamp the learner gives); otherwise leave it out. Without `--time` a page keeps the time it had.
5. **Outcome.** Errors print `{"status": "error", "message": …}` on stdout, exit 1, and change nothing: fewer than three photos, a missing photo or text file, a HEIC or other file that is not JPEG or PNG, a file that is not a readable image, one photo given twice, a text file that is not UTF-8 or holds no text, a unit without pages.json for `slides text`, a page number pages.json does not have, or a malformed source.json or pages.json. Exit 3, one line on stderr: `slides --photos` on a unit whose pages already have text, or `slides text` on a page that already has text; rerun with `--force` to replace it (`slides --photos --force` starts every page from empty text again). Exit 2: a usage error, such as `--photos` without `--unit` or with `--pdf`, `--pptx` or `--images`.
6. **Gate.** A photo page left without text is "not yet transcribed": `coverage` in [gate](../gate.md) gives a WARN naming its photo and the `slides text` command to run.

## Downloads offered?

None. The tool copies the photos into the unit and sends them nowhere; it makes no network call. Your agent reads the copies as it reads any file you give it.

## Known pitfalls

- A photo taken at an angle, blurred or cut off: write only what you can read and tell the learner which pages were hard to read; never fill gaps from memory.
- Two photos of the same slide, or photos out of order: ask the learner which to keep and to rename them, then rerun `slides --photos` (with `--force` when pages already have text).
- `slides --photos` run again on the same unit replaces the earlier copies (`photo-NNN` files) and starts the pages from empty text; other files in `sources/slides/` stay.

## Verified by (name/date) or "experimental"

experimental: no real run on a learner's photos is known yet.
