Adapter: Zoom. A lecture held or recorded in Zoom: the transcript file Zoom lets the learner save, from a meeting or a shared cloud recording read in the browser. It needs an agent with browser tools for the recording page (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<zoom_url>` is the Zoom web address of the institution's account (the profile's `platforms` key `zoom`, or ask the learner).

## Platform

Zoom, a meeting platform; lectures are held in meetings and recorded to the cloud, then shared as a link. A transcript file the learner saved goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]`: a cloud recording's `.vtt`, or a meeting transcript `.txt` (see [import](import.md), which reads both). A recording the learner downloaded goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)). Slides go through the adapter of the platform that posts them, for example [moodle](moodle.md).

## URL patterns

Its public documentation does not show the address form of a shared recording. Write it with placeholders, never a real institution's address or a passcode:
- the account's web address: `<zoom_url>`; a shared cloud recording: `<zoom_url>/…/<id>`;
- a course page that lists the recordings, in a learning platform: `<course>`, reached through that platform's adapter.

## Where transcripts/captions live

- A cloud recording with audio transcription has a separate VTT file, "Audio transcript", in the host's list of recordings, and the transcript beside the video on the playback page ([Using audio transcription for cloud recordings](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0064927)). Closed captions are another file, `CC.VTT` ([Understanding recording file formats](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0064394)).
- In a meeting with Meeting transcripts on, More, then Transcript opens the panel, and Save transcript saves a `.txt` into the learner's `Documents/Zoom` folder ([Using Meeting transcripts](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0085682)).

A viewer of a shared recording sees the transcript only when the host's account allows it; its public documentation does not say whether that viewer can download the transcript file. The way in is a `.vtt` or `.txt` the learner saved (or received from the host), given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when the playback page shows a transcript but no download is offered, stop and offer the ways below; never have the agent copy or retype it.

When there is none: no transcript beside the video and no saved file. Offer [import](import.md) with a file the learner has (the host may share the `.vtt`), [local](local.md) with a recording Zoom lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner. A shared recording may ask for a passcode: the learner types it, the agent never does.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. When the learner already saved a transcript (a meeting's `.txt` in `Documents/Zoom`, or a recording's `.vtt`), take that file.
4. Otherwise open the shared recording and confirm the title and date with the learner; if the page offers the transcript or the recording for download, the learner saves it, or the agent saves it only as the profile's `downloads` allows.
5. Run `tutor-any-lecture acquire import --file F --unit DIR` on the `.vtt` or `.txt`. Outcomes as in [import](import.md).
6. If there are slides, run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never register for an on-demand recording for the learner, and never change a recording's settings.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. The host's account decides what a viewer of a shared link gets: Cloud recording downloads lets anyone with the link download the video, Only the host can download cloud recordings keeps it to the host, and the link may need a passcode or a sign-in, which the agent never types ([Managing cloud recording settings](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065362)). When the recording is offered, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a recording behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- Since 2026-05-18, saved closed captions are no longer offered; only Meeting transcripts keep the text after the meeting ([Saving closed captions in a meeting](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0063899)).
- The audio transcript arrives after the recording, announced by a second email; a new recording may not have one yet.
- The transcript is made in English unless the host changes the recording's language and makes it again; a lecture in another language may need that first.
- Viewers can see the transcript and the chat only on recordings made after the host allowed it.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Using audio transcription for cloud recordings](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0064927)
- [Understanding recording file formats](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0064394)
- [Managing cloud recording settings](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065362)
- [Using Meeting transcripts](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0085682)
- [Saving closed captions in a meeting](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0063899)
