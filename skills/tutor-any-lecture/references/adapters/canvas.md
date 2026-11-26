Adapter: Canvas. Slides and other files on a Canvas course, read in the browser, and the transcript file of a recording in Canvas Studio. It needs an agent with browser tools (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<canvas_url>` is the institution's Canvas address (the profile's `platforms` key `canvas`, or ask the learner).

## Platform

Canvas, Instructure's learning platform, where courses post slides, files and pages in Modules and Files, and link recordings. Slide files go to `tutor-any-lecture slides --pdf F --unit DIR [--images]`, or a `.pptx` deck to `tutor-any-lecture slides --pptx F --unit DIR` (when the course posts both, use the PDF), then `tutor-any-lecture slides suspects --unit DIR`. A Canvas Studio transcript goes to `tutor-any-lecture acquire import --file F --unit DIR`. Recordings embedded from a capture or meeting platform go through its adapter: [panopto](panopto.md), [echo360](echo360.md), [kaltura](kaltura.md) or [zoom](zoom.md).

## URL patterns

Its public documentation does not list the page addresses. Write them with placeholders, never a real institution's address:
- the institution's Canvas: `<canvas_url>`; a course: `<course>`, with its Modules and Files pages;
- one module item, file or Studio media item: `<id>`.

## Where transcripts/captions live

Not in Canvas itself for most recordings: an external tool item in a module opens the capture platform, and that platform's adapter applies ([How do I view Modules as a student?](https://community.instructure.com/en/kb/articles/661313-how-do-i-view-modules-as-a-student)). Media in Canvas Studio, Instructure's video tool, shows a Caption icon when it has captions; its More Options menu offers Download Transcript, and Download Media when the media is not copyright protected ([How do I download media files or media transcript files in Studio?](https://community.instructure.com/en/en/kb/articles/660507-how-do-i-download-media-files-or-media-transcript-files-in-studio)). Its public documentation does not say in which format that transcript downloads, or whether a student watching course media gets the link. A video uploaded through the editor can carry caption or subtitle files ([How do I manage video options in the Rich Content Editor?](https://community.instructure.com/en/en/kb/articles/662932-how-do-i-manage-video-options-in-the-rich-content-editor)); its public documentation does not say whether a student can download them. The way in is a caption or transcript file the learner saved, given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: when captions show but no download is offered, stop and offer the ways below; never have the agent copy or retype them.

When there is none: no Download Transcript link means the media has no captions. Offer [import](import.md) with a file the learner has, [local](local.md) with a recording the platform lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. Open the course's Modules page and find the unit's module; if Modules is hidden, use the Syllabus or the course home page. Note each item's type by its icon: a file, a page, an external tool.
3. Download a slide file only as the profile's `downloads` allows: with ask (the default), ask the learner before each download; with allow, take only files Canvas itself offers.
4. Run `tutor-any-lecture slides --pdf F --unit DIR` on the slide PDF, or `tutor-any-lecture slides --pptx F --unit DIR` on a deck. Outcomes as in [moodle](moodle.md), step 4.
5. For a recording, follow the adapter of the platform its external tool opens; for Canvas Studio media, More Options, then Download Transcript, then `tutor-any-lecture acquire import --file F --unit DIR`, outcomes as in [import](import.md).
6. With a transcript in, run `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never mark an item done, never open a quiz, and never post in a discussion or a page.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. Course files can be viewed and downloaded by a student, when the instructor shows the Files link ([How do I view my user files?](https://community.instructure.com/en/en/kb/articles/662843-how-do-i-view-my-user-files)); a module's file items are files to view or download. Canvas Studio offers Download Media only for media that is not copyright protected; when the recording is offered, ask the learner to download it themselves and use [local](local.md); when it is not, stop and tell the learner. The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented.

## Known pitfalls

- Instructors can lock a module until a date, and require items in order; a locked item is not readable yet, so tell the learner rather than working around it.
- The Modules link or the Files link may be hidden; reach the files through the Syllabus or the course home page.
- Canvas Studio's download links are a legacy add-on, available with some Canvas plans only; a missing link may be the plan, not the media.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [How do I view Modules as a student?](https://community.instructure.com/en/kb/articles/661313-how-do-i-view-modules-as-a-student)
- [How do I view my user files?](https://community.instructure.com/en/en/kb/articles/662843-how-do-i-view-my-user-files)
- [How do I download media files or media transcript files in Studio?](https://community.instructure.com/en/en/kb/articles/660507-how-do-i-download-media-files-or-media-transcript-files-in-studio)
- [How do I manage video options in the Rich Content Editor?](https://community.instructure.com/en/en/kb/articles/662932-how-do-i-manage-video-options-in-the-rich-content-editor)
