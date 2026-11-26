Adapter template. Copy this file to `adapters/<platform>.md` (named as below), keep the seven headings in this order, and fill each one. An adapter describes how to get one lecture's transcript, slides and metadata into a unit folder with the existing `tutor-any-lecture` commands; it adds no new command.

**Naming.** The file is `<platform>.md`, where `<platform>` is the platform's usual name in lower-case ASCII letters and digits, starting with a letter (for example `canvas`, `echo360`, `icourse163`). The same word is the platform's key in the profile's `platforms`: add it to `PLATFORM_KEYS` in `src/tutor_any_lecture/profile.py`, in alphabetical order, and to the `platforms` bullet of [profile](../profile.md); `tests/test_platform_docs.py` checks that the three agree. Write the platform's base address as its key followed by `_url`, in angle brackets (for example `<canvas_url>`), and name the key in the document's first line. A site whose address is the same for everyone writes it in full; its `platforms` value is optional and, when set, replaces that address.

**Helper scripts.** When a platform shows its transcript only on the page, with no export, an adapter may bring one page script, `scripts/<platform>_extract.js` in this skill's folder, as [panopto](panopto.md) does with `scripts/panopto_extract.js` (which has its own importer, `acquire panopto`). The script only reads the page: it clicks nothing, fills nothing, sends no request (no `fetch`, no `XMLHttpRequest`), and never reads `document.cookie`, local or session storage, or a token in the address. It returns one JSON object, saved unchanged to a `.json` file (`acquire import` picks its parser by the suffix) and given to an existing command: Whisper-style segments (`{"segments": [{"start", "end", "text"}]}`, times in seconds) for `tutor-any-lecture acquire import --file F --unit DIR`. The adapter names the script in its Read-only steps and stays experimental until the script has run on a real lecture. Without such a script, an adapter reads no transcript off the page and never has the agent copy or retype one: it reads a caption or transcript file the platform lets the learner save (VTT, SRT, TXT or DOCX, as [import](import.md) lists), through `acquire import`.

## Platform

What the platform is, who typically uses it, and which `tutor-any-lecture` command its material ends up in (`acquire import`, `acquire panopto`, `acquire local`, `acquire url`, `transcribe`, `slides --pdf`, or `slides --pptx`), with the exact flags, for example `tutor-any-lecture acquire import --file F --unit DIR [--duration SEC] [--force]`.

## URL patterns

The page addresses the agent will see, with placeholders for everything institution-specific: `<moodle_url>`, `<panopto_url>`, `<course>`, `<unit>`, `<id>`. No real institution's address.

## Where transcripts/captions live

Where on the page, or in which export, the timed text is found, and in which format. Say what to do when there is none.

## Read-only steps

Numbered steps the learner or agent can follow without changing anything on the platform: open, read, export what the platform offers. Then the command, and its outcome:
- for `acquire …` and `transcribe`: one JSON object on stdout, `{"status": "ok", "health": {…}}` (exit 0), `{"status": "unhealthy", "health": {…}}` (exit 1), `{"status": "error", "message": …}` (exit 1), and the exit-3 cases (see [gate](../gate.md));
- on exit 1 the agent reads `status`: for `unhealthy` it shows the health numbers and tells the learner before planning on that transcript; for `error` it shows `message`;
- an existing `sources/transcript.json` is replaced only with `--force` (otherwise exit 3).

Never click submit, post, edit, share or booking controls. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password.

## Downloads offered?

Which downloads the platform itself offers (and to whom), and how the profile's `downloads` setting applies: ask (default) asks before every download; allow permits only downloads the platform itself offers. Never circumvent DRM, and never use the learner's passwords or cookies; downloading audio is the learner's choice and responsibility, through the public_video_audio switch.

## Known pitfalls

Delays before material appears, misleading labels, empty transcripts, tokens in URLs that must not be read or recorded, bot checks to hand to the user.

## Verified by (name/date) or "experimental"

Who verified the steps on a real lecture and when, without personal names (for example "a contributor, 2026-11"), or "experimental" when no real run is known.
