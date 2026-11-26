Adapter: Microsoft Teams and Stream. A lecture held as a Teams meeting, or its recording played in Stream: the transcript file Teams or Stream lets the learner save, read in the browser or the Teams app. It needs an agent with browser tools for the web pages (see [claude-code](../agents/claude-code.md), [codex](../agents/codex.md), [generic](../agents/generic.md)). `<teams_url>` is the organization's Microsoft 365 address where the recordings are stored (the profile's `platforms` key `teams`, or ask the learner).

## Platform

Microsoft Teams, a meeting platform: lectures are held in meetings, transcribed and recorded; the recordings and transcripts are stored in the organizer's or the channel's Microsoft 365 files (SharePoint) and play in the Microsoft 365 video player (Stream). A transcript file the learner saved, a `.vtt` or a `.docx`, goes to `tutor-any-lecture acquire import --file F --unit DIR [--force]` (see [import](import.md), which reads both). A recording the learner downloaded goes to `tutor-any-lecture acquire local --file F --unit DIR` (see [local](local.md)). Slides go through the adapter of the platform that posts them, for example [moodle](moodle.md).

## URL patterns

Its public documentation does not list the addresses. Write them with placeholders, never a real organization's address:
- the organization's Microsoft 365 address: `<teams_url>`; a class team or channel: `<course>`;
- one recording or transcript, a file in the organization's Microsoft 365 files: `<id>`.

## Where transcripts/captions live

- A meeting's transcript: in the past meeting's chat, Recap, then Transcript; the arrow next to Download offers `.docx` or `.vtt` ([Start, stop, and download live transcripts in Microsoft Teams meetings](https://support.microsoft.com/en-us/teams/meetings/start-stop-and-download-live-transcripts-in-microsoft-teams-meetings)). It is stored in the organizer's Microsoft 365 files.
- A recording in the video player: the Transcript button at the upper right shows the transcript; a WebVTT download sits under Video settings, Transcript and captions, for people with edit permission on the video ([View, edit, and manage video transcripts and captions](https://support.microsoft.com/en-us/clipchamp/stream-pages/view-edit-and-manage-video-transcripts-and-captions)).

The way in is the `.vtt` or `.docx`, saved by the learner (or sent by the organizer) and given to `tutor-any-lecture acquire import --file F --unit DIR`. This adapter reads no transcript off the page: an attendee who can view the transcript but not download it stops here and is offered the ways below; never have the agent copy or retype it.

When there is none: a meeting that was not transcribed has no transcript, and live captions are not kept in the recording. Offer [import](import.md) with a file the learner has (the organizer can send the `.docx` or `.vtt`), [local](local.md) with a recording Teams lets the learner download, or a slides-only unit.

## Read-only steps

1. Use the browser's existing login. At a sign-in page, stop and ask the learner to sign in; never type credentials. Where the school or the platform allows it, suggest that the learner ticks the option to stay signed in when they sign in, so the agent stops at sign-in pages less often. If the agent is connected to a password manager that asks the learner to confirm each item it fills, the learner may let it fill the sign-in; the agent never sees, types or stores the password. At a "Verify you are human" check, stop and hand it to the learner.
2. When the learner already has the `.docx` or `.vtt`, take that file.
3. Otherwise, in Teams, open the past meeting's chat, then Recap, then Transcript, and confirm the meeting and date with the learner. When Download is offered, choose `.vtt` (or `.docx`); the learner saves it, or the agent saves it only as the profile's `downloads` allows. Without Download, stop and tell the learner: ask the organizer for the file.
4. Run `tutor-any-lecture acquire import --file F --unit DIR` on it. Outcomes as in [import](import.md).
5. If there are slides, run `tutor-any-lecture slides --pdf F --unit DIR` (or `--pptx F`), then `tutor-any-lecture slides suspects --unit DIR`.

Never click submit, post, edit, share, delete or booking controls, never post in a meeting chat, never open Video settings to change anything, and never change Manage access.

## Downloads offered?

This adapter does not download the recording; it reads a caption or transcript file the platform lets the learner save. By default the organizer and co-organizers download the transcript; attendees in the same organization can view it but not download it unless the organizer or the IT admin allows it, and people from another organization cannot view it afterwards. Only the meeting organizer can download the recording; everyone invited can view it ([Play, share, and download meeting recordings in Microsoft Teams](https://support.microsoft.com/en-us/teams/meetings/play-share-and-download-meeting-recordings-in-microsoft-teams)). When the recording is not offered to the learner, stop and tell the learner; when they have it, use [local](local.md). The profile's `downloads` applies to every file: ask (the default) asks before every download; allow takes only what the platform itself offers. DRM is never circumvented. Switching on `public_video_audio` (see [url](url.md)) is the learner's choice and responsibility; the tool never uses the learner's login, so a recording behind a sign-in stays out of reach of `acquire url`.

## Known pitfalls

- The organizer chooses who has access to the recording and transcript (Everyone, Organizers and co-organizers, or Specific people), so an attendee may see neither ([Customize who can access a recording or transcript in Microsoft Teams](https://support.microsoft.com/en-us/office/customize-who-can-access-a-recording-or-transcript-in-microsoft-teams-65869725-a7d7-407c-91d4-8b7b8c8d0d0b)).
- Under Manage access, the organizer can give a person Can't download, which hides the transcript download ([Edit or delete a meeting transcript in Microsoft Teams](https://support.microsoft.com/en-us/teams/meetings/edit-or-delete-a-meeting-transcript-in-microsoft-teams)).
- Recordings expire after a time the IT admin sets, and an expired one goes to the recycle bin; save the transcript soon after the lecture.
- Live captions are not captured in recordings or downloads; only a transcript started in the meeting is kept.

## Verified by (name/date) or "experimental"

experimental

Written from public documentation read on 2026-11-26; not yet run on a real lecture:
- [Start, stop, and download live transcripts in Microsoft Teams meetings](https://support.microsoft.com/en-us/teams/meetings/start-stop-and-download-live-transcripts-in-microsoft-teams-meetings)
- [View, edit, and manage video transcripts and captions](https://support.microsoft.com/en-us/clipchamp/stream-pages/view-edit-and-manage-video-transcripts-and-captions)
- [Play, share, and download meeting recordings in Microsoft Teams](https://support.microsoft.com/en-us/teams/meetings/play-share-and-download-meeting-recordings-in-microsoft-teams)
- [Customize who can access a recording or transcript in Microsoft Teams](https://support.microsoft.com/en-us/office/customize-who-can-access-a-recording-or-transcript-in-microsoft-teams-65869725-a7d7-407c-91d4-8b7b8c8d0d0b)
- [Edit or delete a meeting transcript in Microsoft Teams](https://support.microsoft.com/en-us/teams/meetings/edit-or-delete-a-meeting-transcript-in-microsoft-teams)
