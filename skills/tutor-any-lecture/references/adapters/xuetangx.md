Adapter: 学堂在线 (xuetangx). A lecture in a course on 学堂在线 (XuetangX), read in the browser: slides and subtitle files the learner can save or already has. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). The site's address is the same for everyone, `https://www.xuetangx.com`; the profile's `platforms` key `xuetangx` is optional and, when set, replaces that address.

## Platform

学堂在线, a Chinese site for online courses; its pages call it "精品在线课程学习平台" (a platform for learning quality online courses) ([About XuetangX](https://www.xuetangx.com/about)). A subtitle or transcript file the learner has goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a recording the learner has goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)); a slide PDF goes to `tutor-any-lecture slides --pdf F --unit DIR`.

## URL patterns

Its public documentation does not list the address of a course or a lecture. Write them with placeholders, never a school's own address:
- the site: `https://www.xuetangx.com`, or the profile's `xuetangx` value when it is set;
- a course: `<course>`; one lecture video in it: `<id>`.

## Where transcripts/captions live

Its public documentation does not say whether a lecture video has subtitles, where the player shows them, or whether a learner can save them as a file. The way in is a subtitle or transcript file the learner already has, given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no subtitles off the player: when subtitles show but no file is offered, stop and offer the ways below; never have the agent copy or retype them.

When there is none: no subtitle file. Offer [import](import.md) with a file the learner has (the teacher may share one), [local](local.md) with a recording the learner has, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. Open the course and the lecture the learner names, and confirm its title with them.
4. Where the course offers its slides or a subtitle file for download, the learner saves it, or the agent saves it in the browser only as the profile's `downloads` allows; a file the learner already has needs no page at all.
5. Run `tutor-any-lecture slides --pdf F --unit DIR` on a slide PDF (or `--pptx F` on a deck). With a subtitle file, run `tutor-any-lecture acquire import --file F --unit DIR`, outcomes as in [import](import.md), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never enrol or pay for the learner, never answer an exercise or an exam, and never post in a discussion.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. A staff reply on the site's community pages says its videos cannot be downloaded, for copyright reasons, and points to caching them in the mobile app instead ([Why can't XuetangX videos be downloaded?](https://www.xuetangx.com/community/post/3630)). A video cached in the app stays in the app: never take it out. When a recording is offered as a file, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a lecture behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- Its public documentation does not say whether a course's slides can be downloaded; when they are only shown on the page, ask the learner for the file rather than capturing the page.
- The staff reply on downloads is a forum answer ([Why can't XuetangX videos be downloaded?](https://www.xuetangx.com/community/post/3630)), not a help article; check what the course page offers today.
- Its public documentation does not say whether a school's own course runs under another address; when the learner's address differs, set the profile's `xuetangx` value to it.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [About XuetangX](https://www.xuetangx.com/about)
- [Why can't XuetangX videos be downloaded? 为什么学堂在线的视频不能下载？](https://www.xuetangx.com/community/post/3630)

These pages could be read only through search-engine extracts, because they could not be opened directly: https://www.xuetangx.com/about, https://www.xuetangx.com/community/post/3630.
