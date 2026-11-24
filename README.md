# ElicitAgent (context-interviewer)

Prose word count: 1953 words (code blocks, commands, inline code and file paths are not counted).

IIS coursework project. ElicitAgent reads a folder of materials that a person wants an agent to work from, lists what the agent would need to know, and for each gap decides whether to read a file, ask, guess and mark it, or wait. It then writes a brief for the agent and a gap trace that records every decision. "ElicitAgent" is a working name.

## Status

Each part is labelled exactly as it is: **implemented** (built and run), **simulated** (runs on the scripted stand-in model, not a language model) or **planned** (named, not built). Stage numbers follow the approved build plan.

| Part | Status | Notes |
|---|---|---|
| Stage 0: two task folders (`tasks/rota`, `tasks/inbox`) | implemented | All content invented. Both answer sheets are **DRAFT, NOT LOCKED**: AI-drafted suggestions, to be written and locked by the author. |
| Stage 1: the thin pass | implemented | Folder in, items under the eight headings and "Other", the ask table chooses, questions in three kinds, brief and gap trace out. Run on the real model (`claude-sonnet-5-5`) on the rota task on 24 Nov 2026, and on the simulated model. |
| Stage 2: the main screen, side by side | planned | |
| Stage 3: clash spotting (P11) | planned | |
| Stage 4: confirm, edit, reject on every item | planned | |
| Stage 5: the end screen (P10) | planned | |
| Stage 6: the question limit and order of value (P6 to P9) | planned | |
| Stage 7: "why this question" panel and source passage | planned | |
| Model access: Anthropic API | implemented | Key read only from `ANTHROPIC_API_KEY`. Model name is one config value. |
| Model access: scripted stand-in | simulated | Fixed estimates from `tasks/<task>/simulated-model.json`. Every run with it is labelled simulated in the page, the brief and every gap-trace line. Written for the rota task only; the inbox task has none yet. |
| Ask table (`asktable.toml`) | implemented | Both rules, the five fixed settings, harm bands, question costs, the named-person rule. |
| Automated tests | implemented | `uv run pytest`: the ask table and the gap trace fields. |
| Test harness (a script plays the person) | planned | |
| The full test (138 runs) | planned | For the Assignment 3 talk, not this build. |

### What has actually been run

| Date | Task | Model | What ran |
|---|---|---|---|
| 24 Nov 2026 | rota | simulated | Thin pass end to end in the web page: 26 items, 8 questions, brief written. |
| 24 Nov 2026 | rota | real, `claude-sonnet-5-5` | Thin pass end to end in the web page: 50 items listed by the model, 3 questions asked under the cost-weighted rule at k = 1, brief and gap trace written. The run exposed two problems that the stand-in hid; both are fixed (see the development record). |

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

Then open <http://127.0.0.1:8765/>, pick a task folder (or type any folder path), and press "Read the folder".

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

**Tests.**

```sh
uv run pytest
```

## How it works

1. **Read the folder.** Text, Markdown, CSV, PDFs that contain text, and code or any other plain-text file. Images and spreadsheets other than CSV are skipped and listed, because they are planned.
2. **List items.** The model lists what the agent needs to know under eight headings (Goal and deliverable, People, Times, Rules, Preferences, What the agent may do, How we know it is done, Resources) and "Other". Each item is tagged stated or inferred and must hold or nice if possible, with its document and exact passage. The tool checks that each passage really is in its document, and that any numbers in a stated value appear in its passage; if not, the item counts as inferred.
3. **Estimate.** For each item the model only estimates the chance a guess would be wrong and answers two yes-or-no checks: could a mistake be undone, and would the person notice it.
4. **Decide.** The ask table, not the model, chooses the way. The two checks give a harm band (low 1, medium 3, high 9). The question kind sets its cost (confirm 0.5 when there is one candidate value, choose 1 for two to four, open 2 otherwise, and always open for a personal fact about a named person). The cost-weighted rule asks when chance wrong x harm is at least k x cost; the build uses k = 1. If it does not ask: a value the folder states is read from the file; a personal fact about a named person is left open, never guessed; a value whose wrong guess could not be undone waits; an item with nothing to guess from is left open; anything else is guessed and marked assumed.
5. **Ask.** One question at a time, with its one line of reason and its cost. Every question can be answered, skipped (the item stays open) or answered "nobody can answer this", with an optional note of who could supply it (the item becomes "cannot be done"). Skipping still costs the question.
6. **Write.** The brief lists what the agent must ask first, what cannot be done and who needs to supply it, and every settled item under its heading with its state and source. The gap trace has one line per decision and per reply.

### The ask table

`asktable.toml` is the developer's file. It holds both rules and can be changed without touching code:

- cost-weighted: ask when (chance wrong) x (harm) >= k x (question cost); k = 0.25, 0.5, 1, 2, 4.
- confidence-only: ask when (chance wrong) >= t; t = 0.1, 0.2, 0.3, 0.4, 0.5.
- the model decides freely (no threshold), always ask and never ask.
- harm ratios 1, 2, 4 and 1, 5, 25 beside 1, 3, 9, and the question weight sets (1, 1, 1) and (0.25, 1, 4), kept for re-scoring in the test.

### The gap trace

One JSON object per line (`gap-trace.jsonl`). Every line has every field: time, task, run, rule, threshold, model, model_kind (real or simulated), run_label, item, item_label, heading, stated_or_inferred, must_hold_or_nice, chance_wrong (the model's estimate), can_undo, would_notice, harm_band, harm, question_kind, question_cost, way (which of the five ways), reason (the one line), event (decided, answer, skip, nobody can answer, and later edit, reject and the limit events), value, source_document, source_passage, question_count, running_cost, limit_reached and outcome (filled in by the test: correct, wrong or left open).

## Task folders

- `tasks/rota`: the volunteer rota for a small music event. This is the example that carries the report.
- `tasks/inbox`: handing an inbox to a triage agent: a CSV of 40 invented emails and a notes file of rules.

Each has `materials/` (what the tool reads), `request.txt` (what the person asks the agent to do) and an answer sheet named `ANSWER-SHEET-DRAFT-NOT-LOCKED.md`. The tool never reads the answer sheet. Every name, address, event and email is invented; addresses use `example.org` style domains.

**The answer sheets are drafts.** Every row in them is an AI-drafted suggestion, added so that the harness has something to run against. They are the author's to write, and he locks each in a commit (date and file hash) before the rule is finished. Until then no result from them is a result.

## Named, not built

Listed as planned:

- The brief itself as the page (not the starting point, because the tool's order of questions and the document's order conflict).
- "Check again" on an item.

Next steps: testing with real people; spreadsheets beyond CSV; images; a second review stop for the file list; pin and split (confirm, edit and reject cover every correction the test needs); topics marked "always ask me" (tuning stays out of the interface, and the limit is the person's control); the dry run; capture from chat sessions; questions on a phone; comparing versions.

Closed: a free-form definition of a gap. Fixed headings with "Other" are kept, because free-form gaps cannot be checked against an answer sheet.

## Development record

- 11 to 24 Nov 2026: design questions and answers, recorded with dates in [docs/decisions.md](docs/decisions.md) for the early decisions.
- 24 Nov 2026: the author approved the build plan (14 points, P1 to P14, and the build order in stages 0 to 7), with two changes of his own: the harm-ratio check gets its own runs, for the talk (P1), and "the model decides freely" is added as a third rule, as a single point (P2).
- 24 and 25 Nov 2026: this build, as the commits show, one commit per stage.
- 24 Nov 2026, during stage 1: the first real-model run showed two problems the stand-in had hidden. The page printed a stray "null" under some questions, and the model marked a value as stated from a passage that did not contain it (22:00 from a line saying 22:30). Fixed: the page bug, a check that numbers in a stated value appear in its passage, and a tighter instruction for item labels.

## Use of AI

AI assistance (Claude, via Claude Code) was used for design discussion, drafting and, for this build, writing the code.

**The design.** The ideas began from the author's own description of the tool and how he wanted it to work. The AI drafted lines from that description; the author refined, edited or accepted each over several rounds, with his own input on how it should work. In his words:

> all lines / ideas were drafted by the AI from my initial description of the tool and how I wanted it to work.

> it was an iterative process for all of the points, right? I gave a lot of my own personal input on how I wanted it to be so it was drafted by AI and refined and edited, and/or accepted by me, depending on the quality of the AI's proposition.

The wording of the plan's 14 points (P1 to P14) is the AI's, not the author's. P1, P3, P4 and P14 were settled in discussion with him; the others were the AI's proposals, which he approved with the plan, with his two changes above. [docs/decisions.md](docs/decisions.md) records each early decision with its date, what the AI recommended, what the author decided in his own words, and which parts were original and which were AI-assisted. The log itself was drafted with AI assistance from the author's verbatim messages.

**The code.** The code, tests, task materials and draft answer sheets in this repository were written by an AI coding agent (Claude Opus 5.5 in Claude Code) from the author's approved plan, on 24 and 25 Nov 2026. The two answer sheets are drafts for the author to write and lock.

**At run time.** The tool itself calls a language model (`claude-sonnet-5-5` by default) to list items and to make the estimates. The ask table, not the model, decides what to do.
