Adapter: Echo360 (EchoVideo). A lecture recording on Echo360, read in the browser: the transcript file its player lets the learner save. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<echo360_url>` is the institution's Echo360 address (the profile's `platforms` key `echo360`, or ask the learner).

## Platform

Echo360's EchoVideo, a lecture capture and video platform; courses publish recordings to a class list, and learning platforms embed its player. Its transcripts are made by automatic speech recognition, and closed captions are a separate track, often made by people ([Transcriptions vs. Closed Captions](https://support.echo360.com/hc/en-us/articles/11077352568077-EchoVideo-Transcriptions-vs-Closed-Captions)). The transcript file goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a recording the learner downloaded goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)). Slides posted in a learning platform go through that platform's adapter, for example [moodle](moodle.md).

## URL patterns

Its public documentation does not list the page addresses. Write them with placeholders, never a real institution's address:
- the institution's Echo360 address: `<echo360_url>`;
- a course (section) and its class list: `<course>`; one class or media item: `<id>`;
- a learning platform page that embeds the player: follow that platform's adapter, then open the player from it.

## Where transcripts/captions live

Behind the player's Transcript button, a panel beside the video; in the legacy classroom, at the top right of the window ([Viewing Media Transcripts](https://support.echo360.com/hc/en-us/articles/11077285975565-EchoVideo-Viewing-Media-Transcripts)). In the newer player, Download opens a window whose Transcript tab offers TXT and VTT; the VTT carries the cue times, the TXT only speakers and text. The legacy classroom's download icon, left of the transcript search box, saves a TXT. Captions and transcripts are both WebVTT. The way in is the VTT, saved by the learner and given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when the panel shows text but no download is offered, stop and offer the ways below; never have the agent copy or retype it.

When there is none: no Transcript button means the transcript is still being made or the institution has not switched transcription on. Offer [import](import.md) with a file the learner has, [local](local.md) with a recording Echo360 lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. Open the course's class list, then the class the learner names, and confirm the title and date with them.
4. Open the transcript: Transcript in the player. Then Download and, on its Transcript tab, VTT. The learner saves the file, or the agent saves it in the browser only as the profile's `downloads` allows.
5. Run `tutor-any-lecture acquire import --file F --unit DIR` on that VTT. Outcomes as in [import](import.md).
6. If there are slides, run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, and never answer a poll, post in Discussions or open Media Details.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. Its documentation says any viewer can download a transcript, and a viewer of a public link only the transcript ([Using the Media Player Tools](https://support.echo360.com/hc/en-us/articles/11077027768333-EchoVideo-Using-the-Media-Player-Tools)). Instructors switch the download of a recording (MP4 video, MP3 audio) on or off per section, and some institutions allow audio only ([Downloading Media From the Class List](https://support.echo360.com/hc/en-us/articles/11077552130701-EchoVideo-Downloading-Media-From-the-Class-List)). When the recording is offered, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a recording behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- Interactive media with polls shows the transcript only up to the first unanswered poll, and offers no download until every poll is answered; never answer one for the learner ([Viewing Media Transcripts](https://support.echo360.com/hc/en-us/articles/11077285975565-EchoVideo-Viewing-Media-Transcripts)).
- The TXT download has speakers and text but no times, so `acquire import` finds no timed segments; ask for the VTT.
- A public link can be private (viewers must sign in), switched off or deleted, which shows a "content not found" error ([Generating an Access Link and Embed Code for Media](https://support.echo360.com/hc/en-us/articles/11077615534477-EchoVideo-Generating-an-Access-Link-and-Embed-Code-for-Media)).
- An older embed shows a transcript panel only if a transcript existed when its embed code was made; open the class in Echo360 itself.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [EchoVideo: Viewing Media Transcripts](https://support.echo360.com/hc/en-us/articles/11077285975565-EchoVideo-Viewing-Media-Transcripts)
- [EchoVideo: Using the Media Player Tools](https://support.echo360.com/hc/en-us/articles/11077027768333-EchoVideo-Using-the-Media-Player-Tools)
- [EchoVideo: Downloading Media From the Class List](https://support.echo360.com/hc/en-us/articles/11077552130701-EchoVideo-Downloading-Media-From-the-Class-List)
- [EchoVideo: Transcriptions vs. Closed Captions](https://support.echo360.com/hc/en-us/articles/11077352568077-EchoVideo-Transcriptions-vs-Closed-Captions)
- [EchoVideo: Generating an Access Link and Embed Code for Media](https://support.echo360.com/hc/en-us/articles/11077615534477-EchoVideo-Generating-an-Access-Link-and-Embed-Code-for-Media)
