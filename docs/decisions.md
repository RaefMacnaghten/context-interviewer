# Decision log

This file records the design decisions made on this project, so that a reader can see which thinking was the author's and which was AI-assisted. Each entry is written from the author's conversation with the AI assistant (Claude, via Claude Code) and from the author's submitted board answers. The author's messages and submitted answers are copied exactly, including typos, spacing and capitalisation, and appear as blockquotes. The AI's side is summarised, except for short recommendation lines and option texts, which are quoted. Entries are added on the day of the decision or later, always under the true date of the decision. Nothing is backdated and no entry is invented. Entries run oldest first, newest last, and every entry has the same fields in the same order. Entries with the same date are ordered by board question number, with decisions made outside the board after them.

Several entries refer to the design question board. This is a set of 38 design questions in nine themes that the AI prepared on 11 Nov 2026 (described in the report "IIS interviewer idea: scoping board and report", 11 Nov 2026). Each question offers two to four options and marks one as the AI's recommendation. The author ticks an option and can add his own words. Where his words go beyond or change the ticked option, his words are the answer. The board builds on the author's Assignment 1 literature review, "Act, ask or wait? Closing the context gap in agents that work on people's tasks".

The first round of answers, covering questions 1 to 7, is taken from the author's submitted board answers, received 17 Nov 2026. In all seven he ticked the recommended option. In three (questions 2, 6 and 7) he also wrote an answer of his own. For those three, the positions are the author's, and some of the submitted sentences were suggested by the AI in conversation and adopted by him. Each entry says which parts were original and which were AI-assisted, as far as the record supports.

## 1. Whether the interviewer idea is the project

**Date:** 17 Nov 2026

**Question:** Design question board, question 1: is the interviewer idea your IIS project?

**AI recommendation:** "Yes. Commit to it now."

**Author's decision:** The author ticked the recommended option, "Yes. Commit to it now.", and wrote no words of his own.

**Why:** No reason was recorded.

**Original / AI-assisted:** The option wording was the AI's. The choice to accept it was the author's.

## 2. The problem statement

**Date:** 17 Nov 2026

**Question:** Design question board, question 2: what is the problem, in one sentence? The board offered four options. Option 1 was that asking has a price, guessing has a price, and tools pick one blindly. The other three were that agents act on incomplete instructions and fill the blanks by guessing, that people do not know what an agent needs to be told, and that the answers are already in people's files and nobody reads them first.

**AI recommendation:** Option 1: "Asking has a price and guessing has a price, and tools pick one blindly."

In the discussion that followed, the AI agreed that all four options are links in one chain: people do not know what to tell an agent, so instructions are incomplete, some answers are in their files, and for the rest the tool must ask or guess. It argued for keeping one sentence, because the module asks for one intelligent behaviour and the evaluation hangs off that sentence. It agreed that elicitation quality is the right measure, and pointed out that quality alone can be gamed by asking everything, so it must be paired with cost. It advised against measuring in a real niche for Assignment 2, because that would need participants. It suggested a merged one-sentence wording.

**Author's decision:** The author overruled the recommended framing. His messages in the discussion, in order:

> Is the wider problem not all of these things that the system is trying to solve? The literature review is a component of the implementation in my eyes?

> But is option 1 really the thing that should be measured for this tool's efficacy? Should how well the agent elicits information for a niche not the measure? or am i wrong here?

> All 4 are components of the problem. We should be measuring the quality of the agent's elicitation of correct infpormation paired with the ideas in option 1

His position: all four options are components of one problem, and the measure is the quality of elicitation of correct information, paired with the cost idea in option 1.

On the board he ticked the recommended option, option 1, and submitted this answer in his own words. His words change the ticked option, so his words are the answer:

> All four are components of one problem: an agent needs information the person has not given it, and every way of getting it (reading their files, asking, guessing or waiting) has a cost that current tools do not weigh. We should measure the quality of the agent's elicitation of correct information, paired with that cost: correct facts in the brief against questions asked.

**Why:** In the author's view the wider problem is everything the system is trying to solve, not one of the four options alone, and the literature review is a component of the implementation. He also questioned whether option 1 by itself is the right thing to measure, and held that the tool should be judged on how well it elicits correct information.

**Original / AI-assisted:** Original: the reframing of the problem as all four components, and the choice of measure. AI-assisted: the ordering of the four options into one chain, and the argument that quality must be paired with cost. The AI suggested a merged one-sentence wording in the discussion. The record does not say sentence by sentence how much of the submitted answer is that suggestion, so this entry does not claim it.

## 3. Who the person is

**Date:** 17 Nov 2026

**Question:** Design question board, question 3: who is the person, and in which moment?

**AI recommendation:** "Anyone about to hand an everyday task to an agent for the first time."

**Author's decision:** The author ticked the recommended option, "Anyone about to hand an everyday task to an agent for the first time.", and wrote no words of his own.

**Why:** No reason was recorded.

**Original / AI-assisted:** The option wording was the AI's. The choice to accept it was the author's.

## 4. The folder of materials

**Date:** 17 Nov 2026

**Question:** Design question board, question 4: is the folder of materials essential, or a bonus?

**AI recommendation:** "Essential. Read first, ask second."

**Author's decision:** The author ticked the recommended option, "Essential. Read first, ask second.", and wrote no words of his own.

**Why:** No reason was recorded.

**Original / AI-assisted:** The option wording was the AI's. The choice to accept it was the author's.

## 5. What a marker must see working

**Date:** 17 Nov 2026

**Question:** Design question board, question 5: what must a marker be able to see working on 20 November?

**AI recommendation:** "One thin real pass: folder in, a few real decisions to ask or not, a brief out."

**Author's decision:** The author ticked the recommended option, "One thin real pass: folder in, a few real decisions to ask or not, a brief out.", and wrote no words of his own.

**Why:** No reason was recorded.

**Original / AI-assisted:** The option wording was the AI's. The choice to accept it was the author's.

## 6. The single result for the Assignment 3 talk

**Date:** 17 Nov 2026

**Question:** Design question board, question 6: what is the single result you want to show in the Assignment 3 talk?

**AI recommendation:** "One plot: facts captured against questions asked, for three ask rules."

After the discussion in entry 2, the AI revised this: keep the plot, but plot correct facts, checked against the hidden answer sheet, not just facts captured, and show the silent wrong guesses for each rule on the same slide. It also advised logging, for every gap and from day one, the source (file, question or guess), whether it was correct, and the running question count.

**Author's decision:** The author's messages in the discussion were two questions to the AI:

> gIVEN what we just discussed, what shouold I do/ say for here?

> What does 'one plot' mean here for question 6

On the board he ticked the recommended option and submitted this answer in his own words. His words change the ticked option, so his words are the answer:

> Plot correct facts, checked against the hidden answer sheet, not just facts captured. Show silent wrong guesses for each rule on the same slide, as a marker on each point or a small second panel. Log from day one, for every gap: where the answer came from (file, question or guess), whether it was correct, and the running question count.

**Why:** The result shown in the talk has to match the measure chosen in entry 2, where the author insisted on correct information. A plot of facts captured would count wrong facts as well as right ones, which is not what the author asked to be measured.

**Original / AI-assisted:** Original: the requirement for correctness, which comes from entry 2. AI-assisted: the specific change to the plot and the list of what to log, which the AI suggested in the discussion and the author adopted in his submitted answer.

## 7. Reuse after the module

**Date:** 17 Nov 2026

**Question:** Design question board, question 7: do you want to use this yourself after the module? Here "the brief" means the document the interviewer produces for the agent.

**AI recommendation:** "Coursework first. Keep only the brief format reusable."

After the author's first message below, the AI warned that "Anythign that could be used for wider use cases" is unbounded and contradicts "Nothing else needs to be reusable". It suggested naming three reusable things (the brief format, the per-gap decision log, and the ask rule kept as a plain table) and adding no other abstraction.

**Author's decision:** The author's message in the discussion:

> Anythign that could be used for wider use cases, should be made in a manner that can be expanded upon.

He paired that with wording the AI had suggested earlier and he adopted:

> Also keep the per-gap decision log in a clean, documented format alongside the brief. It is the evaluation data for A3, and it is what a later corrections loop would read. Nothing else needs to be reusable. Keep everything problem-agnostic.

On the board he ticked the recommended option and submitted this answer in his own words. His words go beyond the ticked option, so his words are the answer:

> Coursework first. Three things should be reusable: the brief format, the per-gap decision log, and the ask rule kept as a plain table that can be changed without touching code. The log is the evaluation data for A3 and what a later corrections loop would read. For everything else, do not build for reuse, but do not hard-code anything specific to one task either. Add no extra abstraction for future use cases. Keep everything problem-agnostic.

**Why:** The author wants the parts that could serve wider use cases to be built so they can be expanded later. The submitted answer gives the reason for the per-gap decision log: it is the evaluation data for Assignment 3, and it is what a later corrections loop would read.

**Original / AI-assisted:** Original: wanting wider reuse. AI-assisted: the bounded three-item version and the wording about the per-gap decision log, which the AI suggested in the discussion and the author adopted.

## 8. Keep this log

**Date:** 17 Nov 2026

**Question:** Whether the author's decisions and developments in thought are being tracked in the project repository, as evidence of his input.

**AI recommendation:** The record this entry was written from does not summarise the AI's reply to the author's first message, so none is given here.

**Author's decision:** The author's messages, in order:

> are we tracking all decisions / developments in thought on my side in the project repo, to properly evidence my input?

> yes start the decision log

**Why:** To evidence the author's input. The module allows AI use and asks for it to be recorded briefly in the README, and the rubric rewards a record that "distinguishes original, reused and assisted work".

**Original / AI-assisted:** Original: the question about evidencing his input, and the decision to keep a log. AI-assisted: the layout and text of this file, which the AI drafted from the author's verbatim messages and submitted board answers.
