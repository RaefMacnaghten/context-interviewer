# quillnote

A small command-line notebook. Write notes in Markdown, tag them, search them,
export them, and (experimentally) sync them between machines.

## Install

    pipx install quillnote

Requires Python 3.9 or newer. Latest release: 1.4.1.

## Usage

    quillnote new "Shopping list" --tag home
    quillnote search tea --since 2026-01-01
    quillnote export --format md --out notes/
    quillnote sync --remote https://sync.example.org   # experimental

Notes live in `~/.quillnote` unless you set `QUILLNOTE_HOME`.

## Getting help

Usage questions are best asked on the discussions board. Bugs go in the issue tracker.
If you think you've found a security problem, please email security@quillnote.example.org
instead of opening an issue.

## Maintainers

- Ada Testwell (lead)
- Perpetua Inkwell (Windows and packaging; on parental leave until 12 January 2027)
- Rowan Testcase (sync)
- Basil Example (docs, weekends)

quillnote is a volunteer project. Thank you for your patience.
