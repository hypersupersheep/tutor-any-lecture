Adapter: Coursera. A lecture video in a Coursera course, read in the browser: the subtitle or transcript file the course page lets the learner save. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). The site's address is the same for everyone, `https://www.coursera.org`; the profile's `platforms` key `coursera` is optional and, when set, replaces that address.

## Platform

Coursera, an online course site: a course is a set of modules under "Course Material", and a lecture is a video that opens in the site's player ([Watch video lectures](https://www.coursera.support/s/article/209818643-Watch-video-lectures)). A subtitle or transcript file the learner saved goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a lecture video the learner downloaded goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)); a slide PDF from the course goes to `tutor-any-lecture slides --pdf F --unit DIR`.

## URL patterns

Its public documentation does not list the address of a course or a lecture. Write them with placeholders:
- the site: `https://www.coursera.org`, or the profile's `coursera` value when it is set;
- a course: `<course>`; one lecture video in it: `<id>`.

## Where transcripts/captions live

In the Downloads section below the video player, which offers the lecture video, Subtitles (a WebVTT file) and Transcript (the subtitles as a text file to read) ([Download videos](https://www.coursera.support/s/article/learner-000001476?language=en_US)). Lecture videos carry closed-caption subtitles in the course's own language ([Accommodations for learners with disabilities](https://www.coursera.support/s/article/learner-000001416?language=en_US)). The player's gear icon, then Subtitles, picks the language; a language marked "auto" was translated automatically ([Change video settings](https://www.coursera.support/s/article/learner-000001308?language=en_US)). Translated subtitles and transcripts can be downloaded too ([Translations for course content](https://www.coursera.support/s/article/learner-000002049?language=en_US)): take the lecture's own language, never an "auto" one.

The learner saves the `.vtt` file and the agent gives it to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when the player shows subtitles but no download is offered, stop and offer the ways below; never have the agent copy or retype them.

When there is none: no Downloads section and no Subtitles item. Offer [import](import.md) with a file the learner has, [local](local.md) with a lecture video the site lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. Open the course, the module under "Course Material" and the lecture the learner names, and confirm its title with them.
4. In the Downloads section below the player, choose Subtitles in the lecture's own language and save the WebVTT file; the learner saves it, or the agent saves it in the browser only as the profile's `downloads` allows.
5. Run `tutor-any-lecture acquire import --file F --unit DIR` on that file. Outcomes as in [import](import.md).
6. If there are slides, run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never enrol or pay for the learner, never open a graded assignment or quiz, and never mark an item complete.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. The same Downloads section offers the lecture video in a choice of quality, and the mobile app saves a module's videos for offline viewing; a downloaded video has the original-language audio only ([Download videos](https://www.coursera.support/s/article/learner-000001476?language=en_US)). When the video is offered, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a lecture behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- Its public documentation does not say whether the Transcript text file carries times; without `[m:ss]` stamps `acquire import` finds no timed segments, so prefer the WebVTT Subtitles file.
- A language marked "auto" in the subtitle menu is a machine translation ([Change video settings](https://www.coursera.support/s/article/learner-000001308?language=en_US)); its mistakes would pass into the note, so take the lecture's own language.
- A translated language is listed for a course only once most of its video subtitles are translated ([Translations for course content](https://www.coursera.support/s/article/learner-000002049?language=en_US)); a missing language is not a missing file.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Download videos](https://www.coursera.support/s/article/learner-000001476?language=en_US)
- [Watch video lectures](https://www.coursera.support/s/article/209818643-Watch-video-lectures)
- [Change video settings](https://www.coursera.support/s/article/learner-000001308?language=en_US)
- [Accommodations for learners with disabilities](https://www.coursera.support/s/article/learner-000001416?language=en_US)
- [Translations for course content](https://www.coursera.support/s/article/learner-000002049?language=en_US)
