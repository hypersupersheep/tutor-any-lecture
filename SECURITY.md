# Security

## Reporting a vulnerability

Report a vulnerability privately: open the repository's Security tab on GitHub and press the "Report a vulnerability" button. Never report one in a public issue, a pull request or a discussion. Say what you did, what happened, and the version: the `VERSION` file in the skill folder, or the output of `tutor-any-lecture doctor --json --skill <skill folder>`.

## In scope

- The installers: `install.sh`, `install.ps1` and the two scripts under `skills/tutor-any-lecture/scripts/` that they start.
- The guardrails on passwords, browser cookies, DRM and downloads: anything that makes the tool or the skill type or store a password, read cookies, get around DRM, or download what its settings do not allow.
- Shell or path injection through file names, folder names, links or the files a learner gives it.
- Any leak of a learner's data: transcripts, notes, answers or settings sent anywhere the documents do not say.

## Out of scope

- A lecture platform's own terms of use.
- The content of a learner's lecture material.

## Supported versions

The newest release and the default branch.
