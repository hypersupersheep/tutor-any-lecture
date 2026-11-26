Adapter: 雨课堂 (yuketang). A lesson taught with 雨课堂 (Rain Classroom), read in its web version: the slides the teacher pushed, and a subtitle or recording file the learner already has. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<yuketang_url>` is the address of the learner's 雨课堂 site (the profile's `platforms` key `yuketang`, or ask the learner).

## Platform

雨课堂, a classroom tool: during a lesson the students receive the teacher's slides in step with the teacher, and after class the teacher can push slides, with a voice explanation per page, through a WeChat notice ([Usage help](https://www.yuketang.cn/static/html/faq.html)). It has a computer client with an Office add-in and a phone app, both for teachers and students, and a web version, "登录网页版" (sign in to the web version) ([Download page](https://www.yuketang.cn/download)). Slides the learner saved go to `tutor-any-lecture slides --pdf F --unit DIR` (a deck: `tutor-any-lecture slides --pptx F --unit DIR`). A subtitle or transcript file the learner has goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md)); a recording the learner has goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)).

## URL patterns

Its public documentation does not list which address a school's 雨课堂 uses, or the address of a course or a lesson. Write them with placeholders, never a school's own address:
- the learner's 雨课堂 site: `<yuketang_url>`; on the main site the web version sits under `/web` ([Download page](https://www.yuketang.cn/download));
- a course: `<course>`; one lesson in it: `<id>`.

## Where transcripts/captions live

Its public documentation does not say whether a lesson is recorded, whether a recording has subtitles, or whether a learner can save either as a file. The way in is a subtitle or transcript file the learner already has, given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when text shows but no file is offered, stop and offer the ways below; never have the agent copy or retype it.

When there is none: no subtitle or transcript file. Offer [import](import.md) with a file the learner has, [local](local.md) with a recording the learner has, or a slides-only unit from the lesson's slides.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. A code to scan with a phone is the learner's to scan.
2. When the learner's link opens without a sign-in, run `tutor-any-lecture acquire url --url U --info` first; it writes nothing. `"status": "ok"` means the [url](url.md) adapter takes the link; `"status": "error"` (exit 1) means go on with this adapter.
3. In the web version, open the course and the lesson the learner names, and confirm its title and date with them.
4. Where the lesson offers its slides for download, the learner saves them, or the agent saves them in the browser only as the profile's `downloads` allows; slides the learner already has need no page at all.
5. Run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`). With a subtitle file, run `tutor-any-lecture acquire import --file F --unit DIR`, outcomes as in [import](import.md), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never join a class or answer a question or a "试卷" (test paper) for the learner, and never press a slide's "不懂" (don't understand) or "收藏" (bookmark) button.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. Its public documentation does not say whether a learner can download the slides or a recording of a lesson. When a recording is offered as a file, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a lesson behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- A student marks a slide "不懂" (don't understand) to review it later or "收藏" (bookmark) to keep it ([Usage help](https://www.yuketang.cn/static/html/faq.html)); the marks are the learner's own, so the agent never sets them.
- Slides pushed after class arrive as a WeChat notice on the learner's phone ([Usage help](https://www.yuketang.cn/static/html/faq.html)), which the agent cannot open; ask the learner for the lesson in the web version or for the file.
- Its help centre lists a section "学生常见问题" (students' common questions) ([Help centre](https://www.yuketang.cn/help?detail=52)), but its public documentation does not say whether a student can save a lesson's slides; ask the learner when the page offers no file.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Usage help, 雨课堂使用帮助](https://www.yuketang.cn/static/html/faq.html)
- [Download page, 雨课堂下载](https://www.yuketang.cn/download)
- [Help centre, 雨课堂帮助中心](https://www.yuketang.cn/help?detail=52)
