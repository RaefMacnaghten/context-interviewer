# Practice tasks

These ten folders are invented practice tasks for trying the tool out. They are not the test. The test tasks are `tasks/rota` and `tasks/inbox`, and nothing here changes them.

Every organisation, person, place and figure in them is invented. They were written on 25 Nov 2026 by an AI agent, from a short description of what each one should exercise, and copied here unchanged: the first six for the first overnight round, the last four for the second. Each folder holds `intent.txt` (what the person wants the agent to do, in their own words) and `materials/` (the folder the tool reads). There is no answer sheet here: the practice answer sheets are drafts kept outside this repository, written by a separate AI agent that saw only the materials, the intent line and the column definitions.

| Folder | What it exercises |
|---|---|
| `plant-care` | Many gaps that are easy to guess and low in harm: whether the tool guesses and marks rather than asking everything. |
| `cafe-order` | Gaps with the same chance of being wrong but different harm: whether the harm changes the decision. |
| `litter-pick` | The question limit, the order of value, files the tool skips (an image and a spreadsheet), and "not available here". |
| `renewals` | Facts about named people, privacy, and actions that cannot be undone. |
| `supplier-invoices` | Reading tables and spotting where they disagree. |
| `issue-triage` | Reading code and plain-text files and working out the project's conventions. |
| `family-birthdays` | Second round. Gaps the folder mostly hints at rather than states, with strong, medium and weak hints crossed with low, medium and high harm, plus a few that cannot be guessed. |
| `flat-bills-split` | Second round, the same design as `family-birthdays`. |
| `hall-bookings-week` | Second round, the same design as `family-birthdays`. |
| `school-run-rota` | Second round, the same design as `family-birthdays`. |

A dry run on one of them needs its practice answer sheet passed with `--sheet`, for example:

```sh
uv run elicitagent dry-run practice/plant-care --model anthropic --sheet /path/to/plant-care-answer-sheet.md --runs-dir /path/outside/the/repo
```
