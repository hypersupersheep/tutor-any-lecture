Adapter: Blackboard. Slides and other files on a Blackboard course, read in the browser, and the transcript file of a Video Studio recording. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<blackboard_url>` is the institution's Blackboard address (the profile's `platforms` key `blackboard`, or ask the learner).

## Platform

Blackboard, Anthology's learning platform, where courses post documents, files and recordings on the Course Content page. Slide files go to `tutor-any-lecture slides --pdf F --unit DIR [--images]`, or a `.pptx` deck to `tutor-any-lecture slides --pptx F --unit DIR` (when the course posts both, use the PDF), then `tutor-any-lecture slides suspects --unit DIR`. A Video Studio transcript goes to `tutor-any-lecture acquire import --file F --unit DIR`. Recordings embedded from a capture or meeting platform go through its adapter: [panopto](panopto.md), [echo360](echo360.md), [kaltura](kaltura.md), [yuja](yuja.md) or [zoom](zoom.md).

## URL patterns

Its public documentation does not list the page addresses. Write them with placeholders, never a real institution's address:
- the institution's Blackboard: `<blackboard_url>`; a course: `<course>`, with its Course Content page;
- one document, file or recording: `<id>`.

## Where transcripts/captions live

For Video Studio recordings (a tool that needs its own licence), captions show automatically; the transcript opens from Settings (the gear) next to the progress bar, and the download button at the top of the transcript panel saves a VTT with time stamps and speaker narration ([Video Studio Playback and Accessibility](https://help.anthology.com/blackboard/student/en/course-content-and-materials/video-studio/video-studio-playback-and-accessibility.html)). For a recording embedded from another platform, that platform's adapter applies. The way in is the VTT, saved by the learner and given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when a transcript shows but no download is offered, stop and offer the ways below; never have the agent copy or retype it.

When there is none: a recording with no transcript, or a video file with no captions. Offer [import](import.md) with a file the learner has, [local](local.md) with a recording the platform lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. Open the course's Course Content page and find the unit's material; note each document's attached files and each recording.
3. Download a slide file only as the profile's `downloads` allows: with ask (the default), ask the learner before each download; with allow, take only files Blackboard itself offers.
4. Run `tutor-any-lecture slides --pdf F --unit DIR` on the slide PDF, or `tutor-any-lecture slides --pptx F --unit DIR` on a deck. Outcomes as in [moodle](moodle.md), step 4.
5. For a Video Studio recording, open Settings, then the transcript's download button, then run `tutor-any-lecture acquire import --file F --unit DIR` on the VTT, outcomes as in [import](import.md); for a recording from another platform, follow its adapter.
6. With a transcript in, run `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never start a test or an assignment, and never post in a discussion or a journal.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. A document's files show inline or as attachments; some file types must be downloaded to be read ([Documents](https://help.anthology.com/blackboard/instructor/en/course-and-content-management/add-content/documents.html)). Where the institution uses Ally, a file's menu also offers Alternative Formats ([ORIGINAL Types of Course Content](https://help.anthology.com/blackboard/student/en/original-course-view/content-in-your-courses/types-of-course-content.html)); use the original slide file. A Video Studio recording offers its download button only when the instructor allows it ([Edit and Manage Video Studio Content](https://help.anthology.com/blackboard/instructor/en/course-and-content-management/add-content/video-studio/edit-and-manage-video-studio-content.html)); when offered, ask the learner to download it themselves and use [local](local.md); when not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented.

## Known pitfalls

- Instructors can hide a document until they show it; a missing week is not an error.
- A Video Studio transcript opens from Settings, not from a button of its own; when the video is shown at one-quarter size, View Transcript below it opens a read-only window instead.
- A Video Studio transcript of a video with audio descriptions on also holds the description text; leave it out of quotes.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Video Studio Playback and Accessibility](https://help.anthology.com/blackboard/student/en/course-content-and-materials/video-studio/video-studio-playback-and-accessibility.html)
- [Edit and Manage Video Studio Content](https://help.anthology.com/blackboard/instructor/en/course-and-content-management/add-content/video-studio/edit-and-manage-video-studio-content.html)
- [Video Studio](https://help.anthology.com/blackboard/instructor/en/course-and-content-management/add-content/video-studio.html)
- [Documents](https://help.anthology.com/blackboard/instructor/en/course-and-content-management/add-content/documents.html)
- [ORIGINAL Types of Course Content](https://help.anthology.com/blackboard/student/en/original-course-view/content-in-your-courses/types-of-course-content.html)
