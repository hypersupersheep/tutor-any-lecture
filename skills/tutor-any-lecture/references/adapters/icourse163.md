Adapter: 中国大学MOOC (icourse163). A lecture in a course on 中国大学MOOC (China University MOOC), read in the browser: the slide documents the course lets the learner save, and a subtitle or video file the learner already has. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). The site's address is the same for everyone, `https://www.icourse163.org`; the profile's `platforms` key `icourse163` is optional and, when set, replaces that address.

## Platform

中国大学MOOC, a Chinese online course site. A course's teaching units hold "视频" (video), which is required, and "文档" (document), PDF files only, beside quizzes and discussions ([Teachers' guide: publishing a unit](https://help.icourse163.org/help-doc/oc-mooc-manual4.html)). A slide document goes to `tutor-any-lecture slides --pdf F --unit DIR`. A subtitle or transcript file the learner has goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a recording the learner has goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)).

## URL patterns

Its public documentation does not list the address of a course or a lecture. Write them with placeholders, never a school's own address:
- the site: `https://www.icourse163.org`, or the profile's `icourse163` value when it is set;
- a course: `<course>`; one unit or video in it: `<id>`.

## Where transcripts/captions live

In the player, where the teacher added them: the teachers' guide for a school's own courses says a teacher can add subtitles to a video, in Chinese and English ([Teachers' guide for school courses: publishing a unit](https://help.icourse163.org/help-doc/oc-manual4.html)). Its public documentation does not say whether a learner can save a subtitle file, or in which format. The way in is a subtitle or transcript file the learner already has, given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no subtitles off the player: when subtitles show but no file is offered, stop and offer the ways below; never have the agent copy or retype them.

When there is none: no subtitle file. Offer [import](import.md) with a file the learner has, [local](local.md) with a recording the learner has, or a slides-only unit from the course's PDF documents.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. Open the course and the unit the learner names, and confirm its title with them. A course that has ended may be reached from "我的课程" (my courses) through "查看存档" (view the archive) ([Official answers on watching videos](https://www.icourse163.org/forum/1001974001/topic-1003237244.htm)).
4. On the "课件—文档" (courseware, documents) page, "文档下载" (download the document), at the document's lower right, saves the PDF ([Official answers on watching videos](https://www.icourse163.org/forum/1001974001/topic-1003237244.htm)). The learner saves it, or the agent saves it in the browser only as the profile's `downloads` allows.
5. Run `tutor-any-lecture slides --pdf F --unit DIR` on that PDF. With a subtitle file the learner has, run `tutor-any-lecture acquire import --file F --unit DIR`, outcomes as in [import](import.md), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never enrol the learner, never answer a quiz, an exam or a question placed inside a video, and never post in a discussion.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. A course's PDF documents have "文档下载" (download the document) ([Official answers on watching videos](https://www.icourse163.org/forum/1001974001/topic-1003237244.htm)), and the site's app page lists "课件下载" (courseware download) ([Mobile app page](https://www.icourse163.org/mobile.htm)). Its public documentation does not say whether a learner can download a video on the website. When a recording is offered, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a lecture behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- After a course ends, the course team decides what stays open: some courses close, some stay open to enrolled learners, some open parts to everyone ([Official answers on watching videos](https://www.icourse163.org/forum/1001974001/topic-1003237244.htm)).
- A missing video may not be uploaded yet: the course outline and the announcements give the upload times ([Official answers on watching videos](https://www.icourse163.org/forum/1001974001/topic-1003237244.htm)).
- Teachers can upload Chinese and English subtitles ([Teachers' guide for school courses: publishing a unit](https://help.icourse163.org/help-doc/oc-manual4.html)); its public documentation does not say whether a lecture in another language can have subtitles.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Official answers on watching videos, 【官方答疑帖】关于视频观看问题](https://www.icourse163.org/forum/1001974001/topic-1003237244.htm)
- [Teachers' guide for school courses: publishing a unit, 老师操作指南-发布教学单元内容](https://help.icourse163.org/help-doc/oc-manual4.html)
- [Teachers' guide: publishing a unit, 发布教学单元内容](https://help.icourse163.org/help-doc/oc-mooc-manual4.html)
- [Mobile app page, 移动端下载](https://www.icourse163.org/mobile.htm)
