# Contributing

Thank you for helping. This page says what a first contribution can be, how to set up the tests, and the rules every change follows.

## A first contribution: a platform adapter

An adapter tells the agent how to get one lecture's transcript, slides and details from one lecture platform into a unit folder. It is a Markdown file, plus its name in the profile's list of platforms.

1. Copy [skills/tutor-any-lecture/references/adapters/TEMPLATE.md](skills/tutor-any-lecture/references/adapters/TEMPLATE.md) to a new file beside it, named as its naming paragraph says: `<platform>.md`, the platform's usual name in lower-case ASCII letters and digits, starting with a letter (for example `canvas.md`).
2. Keep its seven headings, in their order, and fill in each one.
3. Use only the commands that exist today (`tutor-any-lecture --help` lists them); an adapter adds no command. It may bring one read-only helper script, `<platform>_extract.js`, as the template's helper scripts paragraph describes.
4. Add the platform's name to `PLATFORM_KEYS` in `src/tutor_any_lecture/profile.py`, in alphabetical order, and to the `platforms` bullet of `skills/tutor-any-lecture/references/profile.md`; `tests/test_platform_docs.py` checks that they agree with the file names.
5. Write no real institution's address: use placeholders such as `<moodle_url>`, `<panopto_url>` and `<course>`.
6. Under "Verified by", write "experimental" until the steps have been followed on a real lecture; then name the run without personal names, for example "a contributor, 2026-11".

If you would rather ask for an adapter than write one, open an issue with the "Platform adapter" template.

## Development setup

You need Python 3.10 or later and git.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q -m "not slow"
```

On Windows, use `.venv\Scripts\python` in place of `.venv/bin/python`. The tests marked `slow` need a cached speech model and are left out by `-m "not slow"`; everything else runs offline.

## Rules

- Tests stay offline and use synthetic fixtures. A test never contacts a video site, a model hub or any other service.
- No material from a real course, and no names of people, institutions or courses, in code, tests, documents or commit messages.
- An example lecture comes only from an openly licensed source, with its attribution.
- `skills/tutor-any-lecture/SKILL.md` stays in English, names no agent's own tools, and stays within the limits that `tests/test_skill_text.py` checks.
- Code is MIT licensed. Nothing is copied from a GPL project. Code or text adapted from another project keeps its notice in `THIRD_PARTY_NOTICES.md`.
- A commit message is one short line.
- A change that users will notice adds a line to `CHANGELOG.md` under its newest heading.

Report a security problem as [SECURITY.md](SECURITY.md) says, never in a public issue.
