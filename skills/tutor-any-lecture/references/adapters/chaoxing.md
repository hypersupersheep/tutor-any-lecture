Adapter: 学习通 (chaoxing). A lecture in a course on 学习通 (Chaoxing's learning platform), read in the browser: slides and subtitle or recording files the learner can save or already has. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<chaoxing_url>` is the address of the learner's 学习通 course site (the profile's `platforms` key `chaoxing`, or ask the learner).

## Platform

学习通, Chaoxing's platform for course learning and for sharing and managing knowledge, with an app that also brings Chaoxing's books, journals and videos ([学习通 app page](https://app.chaoxing.com/)). Slides the learner saved go to `tutor-any-lecture slides --pdf F --unit DIR` (a deck: `tutor-any-lecture slides --pptx F --unit DIR`). A subtitle or transcript file the learner has goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a recording the learner has goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)).

## URL patterns

Its public documentation does not list which address a school's 学习通 uses, or the address of a course or a chapter. Write them with placeholders, never a school's own address:
- the learner's course site: `<chaoxing_url>`;
- a course: `<course>`; one chapter or video in it: `<id>`.

## Where transcripts/captions live

Its public documentation does not say whether a course video has subtitles, or whether a learner can save them as a file. The way in is a subtitle or transcript file the learner already has, given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no subtitles off the player: when subtitles show but no file is offered, stop and offer the ways below; never have the agent copy or retype them.

When there is none: no subtitle file. Offer [import](import.md) with a file the learner has (the teacher may share one), [local](local.md) with a recording the learner has, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. Open the course and the chapter the learner names, and confirm its title with them. Do not play the chapter's videos (see Known pitfalls).
4. Where the chapter offers its slides or a subtitle file for download, the learner saves it, or the agent saves it in the browser only as the profile's `downloads` allows; a file the learner already has needs no page at all.
5. Run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`). With a subtitle file, run `tutor-any-lecture acquire import --file F --unit DIR`, outcomes as in [import](import.md), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never sign in to a class or answer a quiz or an exam for the learner, and never post in a discussion.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. Its public documentation does not say whether a learner can download a course's videos or slides on the website. When a recording is offered as a file, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a lecture behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- Watching counts: on one of Chaoxing's own live courses, a chapter's "任务点" (task point) turns green once its video is watched, and viewing time counts toward the score ([Common questions of a Chaoxing live course](https://mooc1.chaoxing.com/mooc-ans/nodedetailcontroller/visitnodedetail?courseId=227592166&knowledgeId=631346824)); its public documentation does not say whether every course works this way, so the agent never plays a video for the learner.
- The same page says that on that course the computer and WeChat versions do not record study data accurately, a computer records only viewing time, and the app is recommended ([Common questions of a Chaoxing live course](https://mooc1.chaoxing.com/mooc-ans/nodedetailcontroller/visitnodedetail?courseId=227592166&knowledgeId=631346824)); what the agent sees in the browser may differ from the app.
- Its public documentation does not say whether a school's site and the main site show a course the same way; ask the learner for the address they use.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [学习通 app page](https://app.chaoxing.com/)
- [Common questions of a Chaoxing live course, 常见问题](https://mooc1.chaoxing.com/mooc-ans/nodedetailcontroller/visitnodedetail?courseId=227592166&knowledgeId=631346824)
