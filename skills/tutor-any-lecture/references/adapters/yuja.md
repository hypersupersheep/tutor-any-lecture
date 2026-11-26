Adapter: YuJa. A lecture recording in YuJa's media player, read in the browser: the transcript or caption file the platform lets the learner save. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<yuja_url>` is the institution's YuJa address (the profile's `platforms` key `yuja`, or ask the learner).

## Platform

YuJa, a video platform whose media player (Lumina) shows course recordings with captions and an interactive transcript, on its own site and inside learning platforms. A transcript or caption file the learner saved goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a recording the learner downloaded goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)). Slides posted in a learning platform go through that platform's adapter, for example [moodle](moodle.md).

## URL patterns

Its public documentation does not list the page addresses. Write them with placeholders, never a real institution's address:
- the institution's YuJa site: `<yuja_url>`; a course channel: `<course>`; one recording: `<id>`;
- a learning platform page that embeds the player is reached through that platform's adapter.

## Where transcripts/captions live

In the media player: Show Transcript opens the interactive transcript on the right of the video, for a video with spoken audio, and the panel has a Download Transcript button ([Downloading Notes, Resources and Transcripts in the Lumina Media Player](https://support.yuja.com/hc/en-us/articles/360048657534-Downloading-Notes-Resources-and-Transcripts-in-the-Lumina-Media-Player)). Its public documentation does not say in which format that button saves the transcript. Caption files are SubRip (`.srt`); the documented way to download one is from the media's Accessibility details, a creator's view ([Downloading Captions Files for Lumina Media](https://support.yuja.com/hc/en-us/articles/360051103814-Downloading-Captions)). The way in is a file in a format [import](import.md) reads, saved by the learner and given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when the panel shows text but no download is offered, stop and offer the ways below; never have the agent copy or retype it.

When there is none: no Show Transcript button and no captions means the recording has neither. Offer [import](import.md) with a file the learner has (an `.srt` from the course's staff, for example), [local](local.md) with a recording the platform lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. Open the recording the learner names and confirm the title with them.
4. Click Show Transcript, then Download Transcript. The learner saves the file, or the agent saves it in the browser only as the profile's `downloads` allows. Check its suffix: `.vtt`, `.srt`, `.txt` or `.docx` go on; any other (a PDF, for example) stops here with the ways above.
5. Run `tutor-any-lecture acquire import --file F --unit DIR` on that file. Outcomes as in [import](import.md).
6. If there are slides, run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, and never use Create Clip or write notes in the player.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. The player's settings can offer Download Media, an audio or video file of the recording, when the organization and the content creator allow it ([Using Settings and Menu Bar Options](https://support.yuja.com/hc/en-us/articles/360049339513-Using-Settings-and-Menu-Bar-Options)); the creator switches it on per recording with Download from Media Player ([Configuring Lumina Media Downloads](https://support.yuja.com/hc/en-us/articles/360047304953-Configuring-Downloading-for-Media-Content)). When it is offered, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a recording behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- YuJa's Video Compliance Player saves its transcript as a PDF, which `acquire import` does not read ([Using the Video Compliance Player](https://support.yuja.com/hc/en-us/articles/40335053746071-Using-the-Video-Compliance-Player)); ask for another export.
- Which player options appear depends on the organization's and the content creator's settings; a missing button is a setting, not an error.
- The transcript is offered only for a video with spoken audio.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Downloading Notes, Resources and Transcripts in the Lumina Media Player](https://support.yuja.com/hc/en-us/articles/360048657534-Downloading-Notes-Resources-and-Transcripts-in-the-Lumina-Media-Player)
- [Downloading Captions Files for Lumina Media](https://support.yuja.com/hc/en-us/articles/360051103814-Downloading-Captions)
- [Using Settings and Menu Bar Options](https://support.yuja.com/hc/en-us/articles/360049339513-Using-Settings-and-Menu-Bar-Options)
- [Configuring Lumina Media Downloads](https://support.yuja.com/hc/en-us/articles/360047304953-Configuring-Downloading-for-Media-Content)
- [Using the Video Compliance Player](https://support.yuja.com/hc/en-us/articles/40335053746071-Using-the-Video-Compliance-Player)
