Adapter: Brightspace. Slides and other files in a Brightspace course's Content, read in the browser, and the caption file of a video in its Media player. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<brightspace_url>` is the institution's Brightspace address (the profile's `platforms` key `brightspace`, or ask the learner).

## Platform

Brightspace, D2L's learning platform, where courses post modules and topics in the Content tool: documents, slides, videos and links to recordings. Slide files go to `tutor-any-lecture slides --pdf F --unit DIR [--images]`, or a `.pptx` deck to `tutor-any-lecture slides --pptx F --unit DIR` (when the course posts both, use the PDF), then `tutor-any-lecture slides suspects --unit DIR`. A caption file from the Media player goes to `tutor-any-lecture acquire import --file F --unit DIR`. Recordings embedded from a capture or meeting platform go through its adapter: [panopto](panopto.md), [echo360](echo360.md), [kaltura](kaltura.md) or [zoom](zoom.md).

## URL patterns

Its public documentation does not list the page addresses. Write them with placeholders, never a real institution's address:
- the institution's Brightspace: `<brightspace_url>`; a course: `<course>`, with its Content page;
- one module, topic or video: `<id>`.

## Where transcripts/captions live

In Brightspace's Media player: Settings (the gear), then View transcript shows the transcript beside the video; Download then offers Transcript (.txt), plain text with no time codes, and Captions (.vtt), with time codes ([View and download audio-video transcripts](https://community.d2l.com/brightspace/kb/articles/2891-view-and-download-audio-video-transcripts)). View transcript appears only when the video has captions, added or made automatically. For a recording embedded from another platform, that platform's adapter applies. The way in is the Captions (.vtt), saved by the learner and given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when captions show but no download is offered, stop and offer the ways below; never have the agent copy or retype them.

When there is none: no View transcript option means the video has no captions. Offer [import](import.md) with a file the learner has, [local](local.md) with a recording the platform lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. Open Content from the course's navigation bar, then the unit's module in the table of contents; note each topic: a document, a video, a link to another platform ([Navigate course content in the Learner Experience or in the Content Experience](https://community.d2l.com/brightspace/kb/articles/6051-navigate-course-content-in-the-learner-experience-or-in-the-content-experience)).
3. Download a slide file only as the profile's `downloads` allows: with ask (the default), ask the learner before each download; with allow, take only files Brightspace itself offers.
4. Run `tutor-any-lecture slides --pdf F --unit DIR` on the slide PDF, or `tutor-any-lecture slides --pptx F --unit DIR` on a deck. Outcomes as in [moodle](moodle.md), step 4.
5. For a video in the Media player, Settings, View transcript, then Download and Captions (.vtt); run `tutor-any-lecture acquire import --file F --unit DIR` on it, outcomes as in [import](import.md). For a recording from another platform, follow its adapter.
6. With a transcript in, run `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never start a quiz or an assignment, and never post in a discussion.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. Students view course files inline and can download or print them when their role has the permission, which the institution sets; a downloaded document keeps its own format ([What types of files can I use for course content?](https://community.d2l.com/brightspace/kb/articles/23031-what-types-of-files-can-i-use-for-course-content)). The Content page also offers Print and Download for studying offline. Its public documentation does not say whether a learner can download the video itself from the Media player; when no download of the recording is offered, stop and tell the learner, and when the learner has the file, use [local](local.md). The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented.

## Known pitfalls

- Brightspace converts uploaded documents to PDF to show them inline, while a download keeps the original format; take the original slide file.
- The Transcript (.txt) download has no time codes, so `acquire import` finds no timed segments; take the Captions (.vtt).
- Automatic captions can be wrong; slides and `slides suspects` matter more there.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [View and download audio-video transcripts](https://community.d2l.com/brightspace/kb/articles/2891-view-and-download-audio-video-transcripts)
- [Navigate course content in the Learner Experience or in the Content Experience](https://community.d2l.com/brightspace/kb/articles/6051-navigate-course-content-in-the-learner-experience-or-in-the-content-experience)
- [What types of files can I use for course content?](https://community.d2l.com/brightspace/kb/articles/23031-what-types-of-files-can-i-use-for-course-content)
