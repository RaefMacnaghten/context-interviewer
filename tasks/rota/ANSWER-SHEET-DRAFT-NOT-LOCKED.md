# DRAFT, NOT LOCKED: answer sheet for the rota task. To be written and locked by the author.

**Status: draft.** Every row below is an AI-drafted suggestion so that the test harness has something to run against. None of it is the author's answer yet. The author edits, deletes or replaces any row, then locks the sheet in a commit (date and file hash) before the rule is finished. Until then this sheet is not the answer sheet and no result from it is a result.

The task: a person hands the volunteer rota for a small music event to an agent. The folder the tool reads is `materials/`. The person's request is in `request.txt`. Everything is invented: the event, the hall and every name.

The tool never reads this file. Only the test harness does, to play the person and to mark items.

## How the harness reads this sheet

- One row per item. The harness matches a question to a row by heading and by the words in "Item".
- "Where the answer lives" is one of: `file: <document>`, `head` (only in the person's head) or `nowhere`. A `nowhere` row is answered "nobody can answer this"; its "Who could supply it" column names who could.
- Rows with form `exact` or `yes or no` are marked by script. Rows with form `free text` are left for the author to mark by hand.

## Rows (all AI-drafted suggestions)

| Id | Heading | Item | Right answer | Form | Question tier | Must hold or nice if possible | Where the answer lives | Who could supply it | Drafted by |
|---|---|---|---|---|---|---|---|---|---|
| R01 | Goal and deliverable | What the agent must produce | A shift-by-shift volunteer rota covering every role from setup to pack down | free text | confirm | must hold | file: event-plan.md | | AI suggestion |
| R02 | Goal and deliverable | Format of the rota | spreadsheet | exact | choose | nice if possible | file: last-year-notes.txt | | AI suggestion |
| R03 | People | Who counts as a team lead | Ada Testwell and Dev Placeholder | exact | choose | must hold | head | | AI suggestion |
| R04 | People | Kit Inventa availability on the day | 14:00 to 18:00 | exact | open | must hold | head | | AI suggestion |
| R05 | People | Whether Fenn Mockridge can work the bar | no | yes or no | confirm | must hold | file: volunteers.csv | | AI suggestion |
| R06 | People | Whether Edie Fictional can be the first aider on the day | yes | yes or no | open | must hold | head | | AI suggestion |
| R07 | Times | Setup start time | 12:00 | exact | confirm | must hold | file: event-plan.md | | AI suggestion |
| R08 | Times | Time the hall must be empty | 22:00 | exact | choose | must hold | file: hall-email.txt | | AI suggestion |
| R09 | Times | Key collection time | 11:30 | exact | confirm | must hold | file: hall-email.txt | | AI suggestion |
| R10 | Times | Shift length | 2 hours | exact | confirm | nice if possible | file: event-plan.md | | AI suggestion |
| R11 | Rules | Bar staff must be over 18 | yes | yes or no | confirm | must hold | file: roles-and-rules.md | | AI suggestion |
| R12 | Rules | Personal licence holder on every bar shift | yes | yes or no | confirm | must hold | file: roles-and-rules.md | | AI suggestion |
| R13 | Rules | Maximum hours per volunteer | 4 hours, except team leads | exact | confirm | must hold | file: roles-and-rules.md | | AI suggestion |
| R14 | Rules | First aider on site whenever the public are in | yes | yes or no | confirm | must hold | file: roles-and-rules.md | | AI suggestion |
| R15 | Preferences | Keep Cora and Lou on the same shift | yes | yes or no | confirm | nice if possible | file: last-year-notes.txt | | AI suggestion |
| R16 | Preferences | No split shifts | yes | yes or no | confirm | nice if possible | file: last-year-notes.txt | | AI suggestion |
| R17 | Preferences | Keep Juno and Ivo on different shifts | yes | yes or no | confirm | nice if possible | file: volunteers.csv | | AI suggestion |
| R18 | What the agent may do | Whether the agent may email the rota to volunteers itself | no | yes or no | confirm | must hold | head | | AI suggestion |
| R19 | What the agent may do | Whether the agent may give a volunteer a role they did not sign up for | no | yes or no | confirm | must hold | file: roles-and-rules.md | | AI suggestion |
| R20 | How we know it is done | Every role filled at every hour with the required number | yes | yes or no | confirm | must hold | file: roles-and-rules.md | | AI suggestion |
| R21 | How we know it is done | Date the organiser must approve the rota by | 27 February 2027 | exact | open | must hold | head | | AI suggestion |
| R22 | Resources | The volunteer list to use | volunteers.csv | exact | confirm | must hold | file: volunteers.csv | | AI suggestion |
| R23 | Resources | Hall alarm code for locking up | (none: not issued yet) | exact | open | must hold | nowhere | the hall caretaker | AI suggestion |
| R24 | Other | Each volunteer gets a food token noted on the rota | yes | yes or no | confirm | nice if possible | head | | AI suggestion |

## What this draft is meant to cover (from the plan)

- R23 is the planted "cannot be done" gap: the answer is nowhere yet.
- Items in each place: in a file (for example R07), only in the person's head (R03, R04, R18) and nowhere (R23). Asking about a row whose answer lives in a file is a wasted question.
- R08 is a clash: the event plan says pack down runs to 22:30 and the hall email says the hall must be empty by 22:00.
- R04 and R06 are facts about named people, so the open-question rule is exercised.
- R18 is an action that cannot be undone (sending email). R17 is a mistake the person would not notice until the day.
