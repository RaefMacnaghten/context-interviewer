# ElicitAgent (context-interviewer)

Prose word count: 1503 words (code blocks, commands, inline code and file paths are not counted).

IIS coursework project. A person says in one or two sentences what they want an agent to do and hands over a folder of materials for it to work from. ElicitAgent reads the folder, lists what the agent would need to know, and fills what the folder states from the files. For each gap that is left, it decides whether to ask, guess and mark it, or wait. It then writes a brief for the agent and a gap trace that records every decision. "ElicitAgent" is a working name.

## Status

Each part is labelled exactly as it is: **implemented** (built and run), **simulated** (runs on the scripted stand-in model, not a language model) or **planned** (named, not built). Each part in detail: [docs/how-it-works.md](docs/how-it-works.md#each-part-in-detail). Every run, with dates and models: [docs/runs.md](docs/runs.md).

| Part | Status | Notes |
|---|---|---|
| Stage 0: two task folders (`tasks/rota`, `tasks/inbox`) | implemented | All content invented; both answer sheets are **DRAFT, NOT LOCKED**. |
| Stage 1: the thin pass | implemented | Folder in, items under the eight headings and "Other", brief and gap trace out; run on the real and the simulated model. |
| Stage 2: the main screen, side by side | implemented | The question on the left, the brief in progress on the right. |
| Stage 3: clash spotting (P11) | implemented | A clash is always asked as a choose question showing both passages, never guessed. |
| Stage 4: confirm, edit, reject on every item | implemented | The person's own corrections; no question cost. |
| Stage 5: the end screen (P10) | implemented | One review stop, then the brief with its ask-first and "not available here" lists. |
| Gaps the tool cannot guess are asked (25 Nov 2026, replacing the must-hold branch of plan change 1) | implemented | Asked while questions remain under the limit; the rule decides only the gaps the tool could guess. |
| Personal facts about a named person (plan change 3) | implemented | Never guessed; asked by what the files hold. |
| Stage 6: the question limit and order of value (P6 to P9) | implemented | Most valuable first; the limit is a number of questions, starting at 8. |
| Stage 7: "why this question" panel and source passage | implemented | The rule's working; each passage shown in place. |
| The intent box (what the person wants the agent to do) | implemented | The person's one or two sentences become the first goal item. |
| The folder tree before reading | implemented | Each file marked "will be read" or "skipped" with the reason. |
| Reading progress | implemented | The real progress the server has, step by step; no made-up percentage. |
| The screens: a dark theme | implemented | System fonts only; checked at desktop and phone widths. |
| Model access: Anthropic API | implemented | Key read only from `ANTHROPIC_API_KEY`. |
| Model access: scripted stand-in | simulated | Fixed estimates; rota task only. |
| Ask table (`asktable.toml`) | implemented | Both rules, the five fixed settings, harm bands and question costs; exactly three outcomes for a gap. |
| Automated tests | implemented | `uv run pytest`. |
| Test harness (a script plays the person) | implemented | `uv run elicitagent dry-run tasks/rota`; the sheets are drafts, so no number is a result. |
| The full test (138 runs) | planned | For the Assignment 3 talk, not this build. |

## Stack

- Python 3.11 or later, managed with [uv](https://docs.astral.sh/uv/). Dependencies are pinned in `pyproject.toml` and locked in `uv.lock`: `anthropic` (the API client) and `pypdf` (text from PDFs). `pytest` for tests.
- A small local web server from the Python standard library, and a page in plain HTML, CSS and JavaScript. No build step.
- The tool calls the Anthropic API with the model `claude-sonnet-5-5` by default. Set `ELICITAGENT_MODEL` to use another model.
- AI tools used to build it: Claude, through Claude Code. The code in this repository was written by an AI coding agent (Claude Opus 5.5 in Claude Code) from the author's approved build plan. See "Use of AI" below.

## How to run

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). From the repository folder:

```sh
uv run elicitagent serve
```

Then open <http://127.0.0.1:8765/>, pick a task folder (or type any folder path; a task folder such as `tasks/rota` means its `materials/`, so the answer sheet is never read), say in the box beside it what you want the agent to do (or leave it empty), and press "Read the folder". Picking one of the task folders fills the box from its `intent.txt`.

**With the simulated model (no key needed).** The rota task has a scripted stand-in. Choose "Simulated" in the Model box, or start the server with:

```sh
uv run elicitagent serve --model simulated
```

**With your own key (real model).** The tool reads the key only from the `ANTHROPIC_API_KEY` environment variable. No key is stored in this repository. Either export it in your shell, or put it in a file outside the repository and pass that file to this one command:

```sh
export ANTHROPIC_API_KEY=your-key-here
uv run elicitagent serve --model anthropic
# or
uv run --env-file /path/outside/the/repo/elicitagent.env elicitagent serve --model anthropic
```

`.env.example` shows the variable name. With "Automatic", the tool uses the API when the variable is set and the simulated model otherwise, and the page always says which one is in use.

Each run writes `brief.md` and `gap-trace.jsonl` under `runs/<task>/` (not committed).

**A dry run with a script playing the person** ([how it marks](docs/how-it-works.md#the-dry-run)):

```sh
uv run elicitagent dry-run tasks/rota --model simulated
```

**Tests.**

```sh
uv run pytest
```

## Development record

The design decisions are recorded with dates in [docs/decisions.md](docs/decisions.md); the entry numbers below point to it. The full narrative of each change is in [docs/development-record.md](docs/development-record.md).

- **Design, 11 to 19 Nov 2026.** The author's idea and scope, the design question board and the nine design lines, seven of which changed because of his challenges (entries 1 to 20).
- **Plan, 24 Nov 2026.** His decisions and corrections (entries 21 to 31); he approved the build plan (P1 to P14, stages 0 to 7) with two changes.
- **Stages 0 to 7, 24 Nov 2026.** One commit per stage, then: reading the folder before the ask table, the "not available here" wording, the intent box, a clash always asked, the folder tree, reading progress and the dark restyle.
- **Plan changes, 24 Nov 2026,** after the author's own real-model run: the must-hold branch, the limit in questions, and named-person facts asked by what the files hold (entries 32 to 34).
- **25 Nov 2026.** "Still open" at the top of the brief; independently drafted answer sheets; gaps the tool cannot guess asked while questions remain, replacing the must-hold branch (entry 35, which supersedes 32); the rota task made monthly; the limit screen wording fixed.

## Use of AI

AI assistance (Claude, via Claude Code) was used for design discussion, drafting and, for this build, writing the code. The full section is in [docs/development-record.md](docs/development-record.md#use-of-ai-in-full).

- **What was the author's:** the idea (entry 1); the problem-agnostic scope (entry 2); the process, which settled design intent by questions before any screens and made the question board adapt to his answers (entries 4 and 12); the challenges that changed seven of the nine design lines (entries 14 to 20); his corrections of 24 Nov 2026 (entries 21 to 30); and the questions from his own runs that led to entries 32 to 35.
- **What was the AI's:** the drafting and wording of the design and the plan, including the 14 points (P1, P3, P4 and P14 were settled in discussion with him); the items it raised and he confirmed (listed in the log's closing section); the decision log, drafted from his verbatim messages; and the code.

In his words:

> all lines / ideas were drafted by the AI from my initial description of the tool and how I wanted it to work.

> it was an iterative process for all of the points, right? I gave a lot of my own personal input on how I wanted it to be so it was drafted by AI and refined and edited, and/or accepted by me, depending on the quality of the AI's proposition.

- **The code.** The code, tests and task materials were written by an AI coding agent (Claude Opus 5.5 in Claude Code) from the author's approved plan.
- **The answer sheets.** Both were drafted by an independent AI agent that saw only the task's materials, its intent line, the headings and the column definitions. The rota sheet then carries the author's first-round review (nine rows edited, three removed, none yet ticked as checked) and an AI's monthly rewording, listed with before and after at its top. Both remain **DRAFT, NOT LOCKED** until he checks and locks them.
- **At run time.** The tool calls a language model (`claude-sonnet-5-5` by default) to list items and to make the estimates. The ask table, not the model, decides what to do.

## Where the other files are

- [docs/how-it-works.md](docs/how-it-works.md): each part in detail, the steps, the screens, the ask table, the gap trace, the dry run, the task folders, and what is named but not built.
- [docs/runs.md](docs/runs.md): every run, with dates and models.
- [docs/development-record.md](docs/development-record.md): the full development narrative and the full "Use of AI" section.
- [docs/decisions.md](docs/decisions.md): the decision log, entry by entry.
- `tasks/rota` and `tasks/inbox`: each task's `materials/`, `intent.txt` and draft answer sheet; `asktable.toml`: the ask table.

## Named, not built

- Planned: the brief itself as the page; "Check again" on an item.
- Next steps: reusing a brief across months; testing with real people; spreadsheets beyond CSV; images; a second review stop for the file list; pin and split; topics marked "always ask me"; the dry run; capture from chat sessions; questions on a phone; comparing versions.
- Closed: a free-form definition of a gap; fixed headings with "Other" are kept.

Reasons: [docs/how-it-works.md](docs/how-it-works.md#named-not-built).
