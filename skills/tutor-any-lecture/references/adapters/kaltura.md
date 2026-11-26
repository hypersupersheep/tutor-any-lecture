Adapter: Kaltura. A lecture recording in a Kaltura player, read in the browser: the caption or transcript file the player lets the learner save. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<kaltura_url>` is the institution's Kaltura video portal address (the profile's `platforms` key `kaltura`, or ask the learner).

## Platform

Kaltura, a video platform whose player sits in a video portal (a media page per recording) and in learning platforms. A caption or transcript file the learner saved goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a recording the learner downloaded goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)). Slides posted in a learning platform go through that platform's adapter, for example [moodle](moodle.md).

## URL patterns

Its public documentation does not list the page addresses of a portal. Write them with placeholders, never a real institution's address:
- the video portal: `<kaltura_url>`; one recording's media page: `<kaltura_url>/…/<id>`, `<id>` being the media entry;
- a course in the portal or in a learning platform: `<course>`; a learning platform page that embeds the player is reached through that platform's adapter.

## Where transcripts/captions live

In caption files attached to the recording: the player reads WebVTT (`.vtt`), SubRip (`.srt`) and SMPTE-TT, and shows them with its CC button ([Captions and audio tracks in the player](https://knowledge.kaltura.com/help/player-captions)). Where the player has the transcript plugin, the same captions appear in a panel beside the video, made from a captions file ordered by hand or through Kaltura's REACH service ([Transcript plugin](https://knowledge.kaltura.com/help/transcript)). Two ways in, when the institution offers them:
- the Download plugin (a download arrow at the top right of the player) lists, under Captions, the caption files to download ([Download plugin](https://knowledge.kaltura.com/help/player-download)): prefer a `.vtt` or `.srt` file;
- the transcript plugin's menu (three dots) has Download current transcript, a plain text file in the selected language.

The learner saves the file and the agent gives it to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when the panel shows text but neither download is offered, stop and offer the ways below; never have the agent copy or retype it.

When there is none: no CC button and no transcript panel means the recording has no captions file. Offer [import](import.md) with a file the learner has, [local](local.md) with a recording the platform lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. Open the media page or the learning platform page the learner names, and confirm the title with them.
4. Open the Download plugin and, under Captions, pick the lecture language's `.vtt` or `.srt`; without it, use Download current transcript. The learner saves the file, or the agent saves it in the browser only as the profile's `downloads` allows.
5. Run `tutor-any-lecture acquire import --file F --unit DIR` on that file. Outcomes as in [import](import.md).
6. If there are slides, run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, and never use Share, likes, comments, Create with AI or the Actions menu on a media page ([Media page in legacy Video Portal](https://knowledge.kaltura.com/help/media-page)).

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. The Download plugin can also offer the recording's video files and attachments, where the institution set it up; the transcript download is on by default and an administrator may switch it off. When the recording is offered, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a recording behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- Its public documentation does not say whether the plain text of Download current transcript carries times; without `[m:ss]` stamps `acquire import` finds no timed segments, so prefer a `.vtt` or `.srt` caption file.
- With several caption languages, the transcript download takes the language currently selected; switch to the lecture language first ([Transcript plugin](https://knowledge.kaltura.com/help/transcript)).
- The download and transcript options appear only where the institution set them up; a missing menu item is a setting, not an error.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Transcript plugin](https://knowledge.kaltura.com/help/transcript)
- [Download plugin](https://knowledge.kaltura.com/help/player-download)
- [Captions and audio tracks in the player](https://knowledge.kaltura.com/help/player-captions)
- [Media page in legacy Video Portal](https://knowledge.kaltura.com/help/media-page)
