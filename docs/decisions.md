# Decision log

This file records the design decisions made on this project, so that a reader can see which thinking was the author's and which was AI-assisted. Each entry is written from the author's conversation with the AI assistant (Claude, via Claude Code). The author's messages are copied exactly, including typos, spacing and capitalisation, and appear as blockquotes. The AI's side is summarised, except for short recommendation lines, which are quoted. Entries are added on the day of the decision or later, always under the true date of the decision. Nothing is backdated and no entry is invented. Entries run oldest first, newest last, and every entry has the same fields in the same order.

Several entries refer to the design question board. This is a set of 38 design questions in nine themes that the AI prepared on 11 Nov 2026 (described in the report "IIS interviewer idea: scoping board and report", 11 Nov 2026). Each question offers two to four options and marks one as the AI's recommendation. The author answers in his own words. The board builds on the author's Assignment 1 literature review, "Act, ask or wait? Closing the context gap in agents that work on people's tasks".

Where an entry says the submitted wording is not yet recorded, the author's discussion of the question is recorded here, but the final text he submitted on the board has not been copied into this file yet. It will be added under the same entry, with the date it was added.

## 1. The problem statement

**Date:** 17 Nov 2026

**Question:** Design question board, question 2: what is the problem, in one sentence? The board offered four options. Option 1 was that asking has a price, guessing has a price, and tools pick one blindly. The other three were that agents act on incomplete instructions and fill the blanks by guessing, that people do not know what an agent needs to be told, and that the answers are already in people's files and nobody reads them first.

**AI recommendation:** Option 1: "Asking has a price and guessing has a price, and tools pick one blindly."

In the discussion that followed, the AI agreed that all four options are links in one chain: people do not know what to tell an agent, so instructions are incomplete, some answers are in their files, and for the rest the tool must ask or guess. It argued for keeping one sentence, because the module asks for one intelligent behaviour and the evaluation hangs off that sentence. It agreed that elicitation quality is the right measure, and pointed out that quality alone can be gamed by asking everything, so it must be paired with cost. It advised against measuring in a real niche for Assignment 2, because that would need participants. It suggested a merged one-sentence wording.

**Author's decision:** The author overruled the recommended framing. His messages, in order:

> Is the wider problem not all of these things that the system is trying to solve? The literature review is a component of the implementation in my eyes?

> But is option 1 really the thing that should be measured for this tool's efficacy? Should how well the agent elicits information for a niche not the measure? or am i wrong here?

> All 4 are components of the problem. We should be measuring the quality of the agent's elicitation of correct infpormation paired with the ideas in option 1

His position: all four options are components of one problem, and the measure is the quality of elicitation of correct information, paired with the cost idea in option 1. The submitted wording of his board answer is not yet recorded here and will be added.

**Why:** In the author's view the wider problem is everything the system is trying to solve, not one of the four options alone, and the literature review is a component of the implementation. He also questioned whether option 1 by itself is the right thing to measure, and held that the tool should be judged on how well it elicits correct information.

**Original / AI-assisted:** Original: the reframing of the problem as all four components, and the choice of measure. AI-assisted: the ordering of the four options into one chain, and the argument that quality must be paired with cost.

## 2. The single result for the Assignment 3 talk

**Date:** 17 Nov 2026

**Question:** Design question board, question 6: what is the single result you want to show in the Assignment 3 talk?

**AI recommendation:** "One plot: facts captured against questions asked, for three ask rules."

After decision 1, the AI revised this: keep the plot, but plot correct facts, checked against the hidden answer sheet, not just facts captured, and show the silent wrong guesses for each rule on the same slide. It also advised logging, for every gap and from day one, the source (file, question or guess), whether it was correct, and the running question count.

**Author's decision:** The author's messages on this question were two questions to the AI:

> gIVEN what we just discussed, what shouold I do/ say for here?

> What does 'one plot' mean here for question 6

The direction follows from decision 1, where the author insisted on correct information. The submitted wording of his board answer is not yet recorded here and will be added.

**Why:** The result shown in the talk has to match the measure chosen in decision 1. A plot of facts captured would count wrong facts as well as right ones, which is not what the author asked to be measured.

**Original / AI-assisted:** Original: the requirement for correctness, which comes from decision 1. AI-assisted: the specific change to the plot and the list of what to log.

## 3. Reuse after the module

**Date:** 17 Nov 2026

**Question:** Design question board, question 7: do you want to use this yourself after the module? Here "the brief" means the document the interviewer produces for the agent.

**AI recommendation:** "Coursework first. Keep only the brief format reusable."

After the author's message below, the AI warned that "Anythign that could be used for wider use cases" is unbounded and contradicts "Nothing else needs to be reusable". It suggested naming three reusable things (the brief format, the per-gap decision log, and the ask rule kept as a plain table) and adding no other abstraction.

**Author's decision:** The author's message:

> Anythign that could be used for wider use cases, should be made in a manner that can be expanded upon.

He paired that with wording the AI had suggested earlier and he adopted:

> Also keep the per-gap decision log in a clean, documented format alongside the brief. It is the evaluation data for A3, and it is what a later corrections loop would read. Nothing else needs to be reusable. Keep everything problem-agnostic.

The submitted wording of his board answer is not yet recorded here and will be added.

**Why:** The author wants the parts that could serve wider use cases to be built so they can be expanded later. The adopted wording gives the reason for the per-gap decision log: it is the evaluation data for Assignment 3, and it is what a later corrections loop would read.

**Original / AI-assisted:** Original: wanting wider reuse. AI-assisted: the bounded three-item version and the wording about the per-gap decision log.

## 4. Keep this log

**Date:** 17 Nov 2026

**Question:** Whether the author's decisions and developments in thought are being tracked in the project repository, as evidence of his input.

**AI recommendation:** The record this entry was written from does not summarise the AI's reply to the author's first message, so none is given here.

**Author's decision:** The author's messages, in order:

> are we tracking all decisions / developments in thought on my side in the project repo, to properly evidence my input?

> yes start the decision log

**Why:** To evidence the author's input. The module allows AI use and asks for it to be recorded briefly in the README, and the rubric rewards a record that "distinguishes original, reused and assisted work".

**Original / AI-assisted:** Original: the question about evidencing his input, and the decision to keep a log. AI-assisted: the layout and text of this file, which the AI drafted from the author's verbatim messages.
