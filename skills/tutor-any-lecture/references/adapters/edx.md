Adapter: edX. A lecture video in an edX course, read in the browser: the transcript file the edX video player lets the learner save. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). The site's address is the same for everyone, `https://www.edx.org`; the profile's `platforms` key `edx` is optional and, when set, replaces that address.

## Platform

edX, an online course site whose course videos play in the edX video player. A transcript file the learner saved goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a video the learner downloaded goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)); a slide PDF from the course, such as a handout below the video, goes to `tutor-any-lecture slides --pdf F --unit DIR`.

## URL patterns

Its public documentation does not list the address of a course or a video. Write them with placeholders:
- the site: `https://www.edx.org`; a course: `<course>`; one unit with a video: `<id>`;
- courses on an Open edX site, which has its own learner's guide ([edX.org Learner's Guide: General Information](https://edx.readthedocs.io/projects/open-edx-learner-guide/en/latest/front_matter/index.html)), live at that site's own address: set the profile's `edx` value to it, and it replaces `https://www.edx.org` above.

## Where transcripts/captions live

In the video player: "Show transcript" shows the whole transcript beside the video, "Show or hide closed captioning" shows captions on it, the Language menu picks a translation when there is one, and "Download transcript" saves it as a SubRip (`.srt`) or a text (`.txt`) file ([Watching Videos on the edX Video Player](https://edx.readthedocs.io/projects/open-edx-learner-guide/en/latest/SFD_video_player.html)). Many courses, not all, let learners download transcripts; the `.srt` file has the times and the `.txt` file has none ([Do edX course videos have transcripts or captions?](https://support.edx.org/hc/en-us/articles/207205917-Do-edX-course-videos-have-transcripts-or-captions)). The course team decides, through the setting "Allow transcript downloads" ([Manage Video Transcripts](https://docs.openedx.org/en/latest/educators/how-tos/course_development/manage_video_transcripts.html)).

The learner saves the `.srt` file and the agent gives it to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when the transcript shows but "Download transcript" is missing, stop and offer the ways below; never have the agent copy or retype it.

When there is none: no transcript beside the video and no download. Offer [import](import.md) with a file the learner has, [local](local.md) with a video the course lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. Open the course and the unit the learner names, and confirm the video's title with them.
4. Below the player, choose "Download transcript", then the `.srt` file, in the lecture's own language; the learner saves it, or the agent saves it in the browser only as the profile's `downloads` allows.
5. Run `tutor-any-lecture acquire import --file F --unit DIR` on that file. Outcomes as in [import](import.md).
6. If there are slides, run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never enrol or pay for the learner, never answer a problem or open an exam, and never post in a discussion.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. "Download video" appears only where the course team made the video available for download, and handouts only where the team attached them ([Watching Videos on the edX Video Player](https://edx.readthedocs.io/projects/open-edx-learner-guide/en/latest/SFD_video_player.html)). When the video is offered, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a video behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- The `.txt` transcript has no times ([Do edX course videos have transcripts or captions?](https://support.edx.org/hc/en-us/articles/207205917-Do-edX-course-videos-have-transcripts-or-captions)), so `acquire import` finds no timed segments in it: take the `.srt`.
- A video hosted on YouTube can show two sets of captions when the learner's YouTube account always shows captions ([Watching Videos on the edX Video Player](https://edx.readthedocs.io/projects/open-edx-learner-guide/en/latest/SFD_video_player.html)); selecting "CC" again hides one set.
- The player shows only the controls that apply to a video: a missing "Download transcript" or Language menu is the course's choice, not an error.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Watching Videos on the edX Video Player](https://edx.readthedocs.io/projects/open-edx-learner-guide/en/latest/SFD_video_player.html)
- [Do edX course videos have transcripts or captions?](https://support.edx.org/hc/en-us/articles/207205917-Do-edX-course-videos-have-transcripts-or-captions)
- [Manage Video Transcripts](https://docs.openedx.org/en/latest/educators/how-tos/course_development/manage_video_transcripts.html)
- [edX.org Learner's Guide: General Information](https://edx.readthedocs.io/projects/open-edx-learner-guide/en/latest/front_matter/index.html)

These pages could be read only through search-engine extracts, because they could not be opened directly: https://support.edx.org/hc/en-us/articles/207205917-Do-edX-course-videos-have-transcripts-or-captions.
