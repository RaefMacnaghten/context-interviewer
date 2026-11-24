# Decision log

This file records the design decisions made on this project, so that a reader can see which thinking was the author's and which was AI-assisted. Each entry is written from the author's conversation with the AI assistant (Claude, via Claude Code) and from the author's submitted board answers. The author's messages and submitted answers are copied exactly, including typos, spacing and capitalisation, and appear as blockquotes. The AI's side is summarised, except for short recommendation lines and option texts, which are quoted. Entries are added on the day of the decision or later, always under the true date of the decision. Nothing is backdated and no entry is invented. Entries run oldest first, newest last, and every entry has the same fields in the same order. Entries with the same date are ordered by board question number, with decisions made outside the board after them, in the order of the record.

Several entries refer to the design question board. This is a set of 38 design questions in nine themes that the AI prepared on 11 Nov 2026 (described in the report "IIS interviewer idea: scoping board and report", 11 Nov 2026). Each question offers two to four options and marks one as the AI's recommendation. The author ticks an option and can add his own words. Where his words go beyond or change the ticked option, his words are the answer. The board builds on the author's Assignment 1 literature review, "Act, ask or wait? Closing the context gap in agents that work on people's tasks".

The first round of answers, covering questions 1 to 7, is taken from the author's submitted board answers, received 17 Nov 2026. In all seven he ticked the recommended option. In three (questions 2, 6 and 7) he also wrote an answer of his own. For those three, the positions are the author's, and some of the submitted sentences were suggested by the AI in conversation and adopted by him. Each entry says which parts were original and which were AI-assisted, as far as the record supports.

Entries 1 to 4, 12, 14 to 31 and the closing section were added on 24 Nov 2026 from the conversation with the AI assistant and the design question board, each under the true date of its decision (11, 17, 18 to 19 and 24 Nov 2026), so nothing reads as backdated. Entries 5 to 11 and 13 are the first eight entries, renumbered into date order, with their cross-references updated and otherwise unchanged. Where the record holds only the AI's own summary at the time of what the author had challenged, the entry labels it as the AI's summary and never sets it as a blockquote or in his voice. Where the record has both his words and such a summary, both are given, each labelled.

Entries 32 and 33 were added on 24 Nov 2026, after the author's own real-model run on the rota task, from his message about that run and the AI's reading of the run's gap trace, which is labelled as the AI's reading.

Entries 14 to 20 cover the nine design lines the AI set out on 18 Nov 2026, with its own table of what each line first said, what it became and why. Seven of the nine lines changed because of the author's challenges on 18 and 19 Nov 2026, one entry per line; the record does not give a finer date for each. Lines 7 and 9 changed as consequences or for naming, not from a challenge, so they have no entry. The closing section lists items the AI raised and the author confirmed.

## 1. The idea: an interview tool that works from a folder of materials

**Date:** 11 Nov 2026

**Question:** What the IIS project should be.

**AI recommendation:** The record does not give an AI recommendation that came before this idea, so none is given here.

**Author's decision:** The author proposed the project in this message in the conversation with the AI assistant:

> What if I made it an interview tool to ascertain all aspects of a given problem required for agentic implementation / while building up a viewable model of the problem in parallel. Making appropraite review gates / editable parts of appropriate things... Perhaps I could work under the assumption is has access to a folder of materials that the user wants to use to run / build the agent with?

This set the whole project: an interview, a viewable model of the problem built up in parallel, review points and editable parts, and a folder of materials to work from.

**Why:** No reason was recorded beyond the message itself.

**Original / AI-assisted:** Original: the idea, the viewable model of the problem, the review points and the folder of materials. AI-assisted: nothing is recorded for this message.

## 2. The tool is problem-agnostic

**Date:** 11 Nov 2026

**Question:** How wide the tool's scope should be.

**AI recommendation:** The record does not give an AI recommendation for this, so none is given here.

**Author's decision:** The author proposed making the tool problem-agnostic, in his words "making it problem agnostic", rather than tying it to one kind of setting.

**Why:** His reason is not recorded in this log.

**Original / AI-assisted:** Original: the problem-agnostic scope. AI-assisted: nothing is recorded for this decision.

## 3. The link to the author's Assignment 1 review

**Date:** 11 Nov 2026

**Question:** How the project relates to the author's Assignment 1 literature review.

**AI recommendation:** The record does not give an AI recommendation for this, so none is given here.

**Author's decision:** The author's message:

> This was my A1 topic - i feel like it could actually fit in?

This tied the project to his own Assignment 1 review, "Act, ask or wait? Closing the context gap in agents that work on people's tasks".

**Why:** No reason was recorded beyond the message itself.

**Original / AI-assisted:** Original: the link to his own review. AI-assisted: nothing is recorded for this decision.

## 4. Settle design intent by questions before any screens

**Date:** 11 Nov 2026

**Question:** Whether to work from the first set of screens the AI had drafted, or to settle the design intent first.

**AI recommendation:** The AI had drafted a first board of 34 screens.

**Author's decision:** The author rejected that board as premature and chose to settle design intent by questions first:

> The iis board that was generated lookjs good but there is loads of it when i have barely scoped out the idea, but I think beforehand I should have done a grilling session in a lavish to pin down design intent

His word "lavish" here refers to [the design question board tool].

**Why:** In his words, there was "loads of it when i have barely scoped out the idea".

**Original / AI-assisted:** Original: rejecting the screens as premature, and the choice to settle design intent by questions first. AI-assisted: the rejected screens.

## 5. Whether the interviewer idea is the project

**Date:** 17 Nov 2026

**Question:** Design question board, question 1: is the interviewer idea your IIS project?

**AI recommendation:** "Yes. Commit to it now."

**Author's decision:** The author ticked the recommended option, "Yes. Commit to it now.", and wrote no words of his own.

**Why:** No reason was recorded.

**Original / AI-assisted:** The option wording was the AI's. The choice to accept it was the author's.

## 6. The problem statement

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

## 7. Who the person is

**Date:** 17 Nov 2026

**Question:** Design question board, question 3: who is the person, and in which moment?

**AI recommendation:** "Anyone about to hand an everyday task to an agent for the first time."

**Author's decision:** The author ticked the recommended option, "Anyone about to hand an everyday task to an agent for the first time.", and wrote no words of his own.

**Why:** No reason was recorded.

**Original / AI-assisted:** The option wording was the AI's. The choice to accept it was the author's.

## 8. The folder of materials

**Date:** 17 Nov 2026

**Question:** Design question board, question 4: is the folder of materials essential, or a bonus?

**AI recommendation:** "Essential. Read first, ask second."

**Author's decision:** The author ticked the recommended option, "Essential. Read first, ask second.", and wrote no words of his own.

**Why:** No reason was recorded.

**Original / AI-assisted:** The option wording was the AI's. The choice to accept it was the author's.

## 9. What a marker must see working

**Date:** 17 Nov 2026

**Question:** Design question board, question 5: what must a marker be able to see working on 20 November?

**AI recommendation:** "One thin real pass: folder in, a few real decisions to ask or not, a brief out."

**Author's decision:** The author ticked the recommended option, "One thin real pass: folder in, a few real decisions to ask or not, a brief out.", and wrote no words of his own.

**Why:** No reason was recorded.

**Original / AI-assisted:** The option wording was the AI's. The choice to accept it was the author's.

## 10. The single result for the Assignment 3 talk

**Date:** 17 Nov 2026

**Question:** Design question board, question 6: what is the single result you want to show in the Assignment 3 talk?

**AI recommendation:** "One plot: facts captured against questions asked, for three ask rules."

After the discussion in entry 6, the AI revised this: keep the plot, but plot correct facts, checked against the hidden answer sheet, not just facts captured, and show the silent wrong guesses for each rule on the same slide. It also advised logging, for every gap and from day one, the source (file, question or guess), whether it was correct, and the running question count.

**Author's decision:** The author's messages in the discussion were two questions to the AI:

> gIVEN what we just discussed, what shouold I do/ say for here?

> What does 'one plot' mean here for question 6

On the board he ticked the recommended option and submitted this answer in his own words. His words change the ticked option, so his words are the answer:

> Plot correct facts, checked against the hidden answer sheet, not just facts captured. Show silent wrong guesses for each rule on the same slide, as a marker on each point or a small second panel. Log from day one, for every gap: where the answer came from (file, question or guess), whether it was correct, and the running question count.

**Why:** The result shown in the talk has to match the measure chosen in entry 6, where the author insisted on correct information. A plot of facts captured would count wrong facts as well as right ones, which is not what the author asked to be measured.

**Original / AI-assisted:** Original: the requirement for correctness, which comes from entry 6. AI-assisted: the specific change to the plot and the list of what to log, which the AI suggested in the discussion and the author adopted in his submitted answer.

## 11. Reuse after the module

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

## 12. Make the question board adapt to the author's answers

**Date:** 17 Nov 2026

**Question:** Whether the rest of the design question board should stay as first drafted after the author's first answers.

**AI recommendation:** The record does not give an AI recommendation for this, so none is given here.

**Author's decision:** The author's message:

> I feel like i've given input that will adjust how the rest of the 31 questions would be framed to me / the options presented. Would it be a good idea to regenerate the lavish?

His word "lavish" here refers to [the design question board tool]. This made the design question board adapt to his answers.

**Why:** In his words, his input "will adjust how the rest of the 31 questions would be framed to me / the options presented".

**Original / AI-assisted:** Original: making the board adapt to his answers. AI-assisted: the questions and options themselves.

## 13. Keep this log

**Date:** 17 Nov 2026

**Question:** Whether the author's decisions and developments in thought are being tracked in the project repository, as evidence of his input.

**AI recommendation:** The record this entry was written from does not summarise the AI's reply to the author's first message, so none is given here.

**Author's decision:** The author's messages, in order:

> are we tracking all decisions / developments in thought on my side in the project repo, to properly evidence my input?

> yes start the decision log

**Why:** To evidence the author's input. The module allows AI use and asks for it to be recorded briefly in the README, and the rubric rewards a record that "distinguishes original, reused and assisted work".

**Original / AI-assisted:** Original: the question about evidencing his input, and the decision to keep a log. AI-assisted: the layout and text of this file, which the AI drafted from the author's verbatim messages and submitted board answers.

## 14. Design line 1, Ways to handle a gap

**Date:** 18 to 19 Nov 2026

**Question:** Design line 1 of nine: ways to handle a gap.

**AI recommendation:** The AI's first version: four ways, one kind of question.

**Author's decision:** After his challenge the line became: "ask" split into confirm and open questions.

The AI's summary at the time of what he had challenged: "Your point that a one-tap question is not the same burden as a typed one".

**Why:** No reason was recorded beyond the challenge.

**Original / AI-assisted:** Original: the challenge. AI-assisted: the first version of the line and the wording of the change.

## 15. Design line 2, The ask table

**Date:** 18 to 19 Nov 2026

**Question:** Design line 2 of nine: the ask table.

**AI recommendation:** The AI's first version: a table the user can read and edit, plus a "how I decide" screen.

**Author's decision:** After his challenge the line became: the developer's file; the user sees one line of reason.

His words:

> On line 2 are we going to keep the reason for the question but not show the rule?

The AI's summary at the time of what he had challenged: "Your point that users will not maintain ask rules".

**Why:** No reason was recorded beyond the challenge.

**Original / AI-assisted:** Original: the challenge. AI-assisted: the first version of the line and the wording of the change.

## 16. Design line 3, What a gap is

**Date:** 18 to 19 Nov 2026

**Question:** Design line 3 of nine: what a gap is.

**AI recommendation:** The AI's first version: a "fact" under six headings, with a claim that a preference can never be found in a file. Later, a "discovery rate" measured from planted items that the headings do not list.

**Author's decision:** After his challenge the line became: "items" under eight headings plus "other", tagged stated or inferred. After a second challenge on the same line, the discovery rate was dropped.

His words:

> on line 3 can you check that with respect to the literature review for me?

The AI's summary at the time of what he had challenged: "You preferred 'items' and challenged the preference claim, which was wrong".

His words on the discovery rate:

> But wouldn't the following example that you used be just like a fact?... How much point is there in doing this discovery stuff? Are there actually things that can't fit in the current headings?

**Why:** The AI's summary at the time says the preference claim was wrong. No other reason was recorded beyond the challenges.

**Original / AI-assisted:** Original: the two challenges. AI-assisted: the first version of the line and the wording of the change.

## 17. Design line 4, Cost of a question

**Date:** 18 to 19 Nov 2026

**Question:** Design line 4 of nine: cost of a question.

**AI recommendation:** The AI's first version: every question counts as one.

**Author's decision:** After his challenge the line became: three tiers of question cost, re-checked under other weights.

The AI's summary at the time of what he had challenged: "You questioned whether equal cost was right. It was not."

His words:

> Does it make a massive difference as to the values we choose right now, assuming that we test them?

**Why:** The AI's summary at the time says equal cost was not right. No other reason was recorded.

**Original / AI-assisted:** Original: the challenge. AI-assisted: the first version of the line and the wording of the change.

## 18. Design line 5, Tuning

**Date:** 18 to 19 Nov 2026

**Question:** Design line 5 of nine: tuning.

**AI recommendation:** The AI's first version: three fixed rules, giving three points.

**Author's decision:** After his challenge the line became: one threshold per rule, giving a curve.

The AI's summary at the time of what he had challenged: "Your point that a curve should be possible by testing versions on synthetic data".

**Why:** No reason was recorded beyond the challenge.

**Original / AI-assisted:** Original: the challenge. AI-assisted: the first version of the line and the wording of the change.

## 19. Design line 6, Where an item came from

**Date:** 18 to 19 Nov 2026

**Question:** Design line 6 of nine: where an item came from.

**AI recommendation:** The AI's first version: "file, question or guess".

**Author's decision:** After his challenge the line became: the document name plus the exact passage.

The AI's summary at the time of what he had challenged: "You asked which file I meant. The line was unclear and had lost detail".

**Why:** The AI's summary at the time says the line was unclear and had lost detail.

**Original / AI-assisted:** Original: the challenge. AI-assisted: the first version of the line and the wording of the change.

## 20. Design line 8, Rules compared

**Date:** 18 to 19 Nov 2026

**Question:** Design line 8 of nine: rules compared.

**AI recommendation:** The AI's first version: always ask, never ask and cost-weighted.

**Author's decision:** After his challenge the line became: two curves, confidence-only against cost-weighted.

The AI's summary at the time of what he had challenged: "Your point that beating two extremes is a weak claim".

His words:

> Has the claim gone to comparing these two rule types? Are we not trying to say what the optimal rule set is

**Why:** The AI's summary at the time says that beating two extremes is a weak claim.

**Original / AI-assisted:** Original: the challenge. AI-assisted: the first version of the line and the wording of the change.

## 21. Keep the options full size

**Date:** 24 Nov 2026

**Question:** Whether any options should be cut down to fit the deadline.

**AI recommendation:** The AI had offered options sized to the deadline. The record does not quote them.

**Author's decision:** The author's message:

> have thas meant that anything has decreased in scope? I don't want to not answer any important questions now. We have the time to make this work.

This reversed the deadline-sized options; the full-size options were restored.

**Why:** In his words: "I don't want to not answer any important questions now. We have the time to make this work."

**Original / AI-assisted:** Original: the decision to keep the full-size options. AI-assisted: the options themselves.

## 22. The question limit is a checkpoint

**Date:** 24 Nov 2026

**Question:** What happens when the question limit is reached, and in what order questions are asked.

**AI recommendation:** The AI had proposed a hard question limit.

**Author's decision:** The author's message:

> when they reach the limit, the model should tell them how many more questions it thinks it might need... with the option for the person to continue or stop. Ask in order of value... If I stop at the limit, low-harm gaps are guessed and marked assumed, high-harm gaps are left open.

This turned the hard limit into a checkpoint and set the order of questions and the rule for stopping.

**Why:** No reason was recorded beyond the message itself.

**Original / AI-assisted:** Original: the checkpoint, the order of value and the stopping rule. AI-assisted: the hard limit he changed.

## 23. The harm scale and the question costs

**Date:** 24 Nov 2026

**Question:** Whether harm on a 1 to 9 scale and question cost on a different scale can be compared.

**AI recommendation:** The record does not give an AI recommendation for this, so none is given here.

**Author's decision:** The author's message:

> why is harm 1-9, when ask cost is a different scale. does that make sense? Does it not amtter giving we are testing different values of k?

This led to the harm-ratio sensitivity check.

**Why:** No reason was recorded beyond the question itself.

**Original / AI-assisted:** Original: the question that led to the check. AI-assisted: the form of the check.

## 24. What cannot be undone is never guessed

**Date:** 24 Nov 2026

**Question:** What the tool does with a gap in the medium harm band.

**AI recommendation:** The record does not give an AI recommendation for this, so none is given here.

**Author's decision:** The author's message:

> What about for medium harm bands?

This led to the rule that what cannot be undone is never guessed.

**Why:** No reason was recorded beyond the question itself.

**Original / AI-assisted:** Original: the question that led to the rule. AI-assisted: the wording of the rule.

## 25. The second task: an inbox instead of a group trip

**Date:** 24 Nov 2026

**Question:** Which task to use as the second test task.

**AI recommendation:** The AI had proposed a group trip.

**Author's decision:** The author's message:

> Are there / richer / more interesting ideas for the second test than a group trip? Perhaps one that is more indicitative of eliciting the information required for an effective agent in a useful setting?

This replaced the group-trip task with the inbox task.

**Why:** In his words, a task "more indicitative of eliciting the information required for an effective agent in a useful setting".

**Original / AI-assisted:** Original: the call for a richer task. AI-assisted: the inbox task's materials.

## 26. Which file types the tool reads

**Date:** 24 Nov 2026

**Question:** Which kinds of file the tool reads from the folder.

**AI recommendation:** The record does not give an AI recommendation for this, so none is given here.

**Author's decision:** The author's messages, in order:

> would it not make sense for it be able to read spreadsheets or images or code or other important files

> ok just add processing code / plain-text files. CSV is fine for now with no images.

This set the file types: code and plain-text files, CSV, and no images for now.

**Why:** No reason was recorded beyond the messages themselves.

**Original / AI-assisted:** Original: the choice of file types. AI-assisted: nothing is recorded for this decision.

## 27. Reading the folder comes before the ask table

**Date:** 24 Nov 2026

**Question:** Whether "read a file" is one of the ask table's outcomes.

**AI recommendation:** The AI's diagram and build plan had "read a file" as one of the ways the ask table could handle a gap.

**Author's decision:** The author's message:

> Why is read a file an option here, when the gap would have arisen from the reading the files in the first place?

This caught an error in the AI's diagram and build plan. Reading the folder moved in front of the rule.

**Why:** In his words, the gap "would have arisen from the reading the files in the first place".

**Original / AI-assisted:** Original: catching the error. AI-assisted: the corrected wording of the plan and the code.

## 28. A false label: "I can't answer this"

**Date:** 24 Nov 2026

**Question:** Whether the reply "Nobody can answer this" is true.

**AI recommendation:** The AI's label was "Nobody can answer this".

**Author's decision:** The author's message:

> Actually someone can answer it in the world, is it?

This caught a false label. "Nobody can answer this" became "I can't answer this", and the fifth state, first called "cannot be done", is now named "Not available here".

**Why:** In his words: "someone can answer it in the world".

**Original / AI-assisted:** Original: catching the false label. AI-assisted: the new wording.

## 29. A missing step: the intent box

**Date:** 24 Nov 2026

**Question:** Whether the person states what they want the agent to do.

**AI recommendation:** The AI's plan had no such step.

**Author's decision:** The author's message:

> Is there a step in the program where you state the intent of what you want the agent to do?

This found a missing step. The intent box was added.

**Why:** No reason was recorded beyond the question itself.

**Original / AI-assisted:** Original: finding the missing step. AI-assisted: the design and code of the intent box.

## 30. The name

**Date:** 24 Nov 2026

**Question:** What the tool is called.

**AI recommendation:** The record does not give an AI recommendation for this, so none is given here.

**Author's decision:** The author named the tool "Elicit", then wrote "ok make the name ElicitAgent instead."

**Why:** No reason was recorded.

**Original / AI-assisted:** Original: the name. AI-assisted: nothing is recorded for this decision.

## 31. The author's account of authorship

**Date:** 24 Nov 2026

**Question:** How the design was drafted and decided.

**AI recommendation:** The record does not give an AI recommendation for this, so none is given here.

**Author's decision:** The author's own account, in two messages:

> it was drafted by AI and refined and edited, and/or accepted by me, depending on the quality of the AI's proposition

> all lines / ideas were drafted by the AI from my initial description of the tool and how I wanted it to work

**Why:** No reason was recorded beyond the account itself.

**Original / AI-assisted:** Original: the account, which is his. AI-assisted: nothing is recorded for this entry.

## 32. Must-hold items are asked, not left open

**Date:** 24 Nov 2026

**Question:** Why the tool stopped asking with items still open, and what it should do with an item that must hold and that the rule will not guess.

**AI recommendation:** The AI's reading of his run's trace, not his words: the run stopped with 6 items open at question cost 3 of 8; a low-harm open question could never be asked, because chance wrong x harm was at most 1 against an open question's cost of 2; and leaving an item open or waiting was treated as free, although the brief hands it to the agent as "ask before you do this". The AI proposed a must-hold branch: an item that must hold and that the rule will not guess (it would wait, it has nothing to guess from, or it is a personal fact about a named person) is asked now, most valuable first, within the limit; an item that is only nice if possible may stay open; and every waiting or open item can be answered on the end screen.

**Author's decision:** The author's message, after his own real-model run:

> Why is it not asking me any more questions? There are 6 more open items?

He agreed the must-hold branch as proposed. This is a change to the approved plan.

**Why:** His question found that the tool left must-hold items for the agent to ask when he was there to answer them.

**Original / AI-assisted:** Original: finding the problem in his own run. AI-assisted: the reading of the trace and the design of the branch.

## 33. The question limit is a number of questions

**Date:** 24 Nov 2026

**Question:** What the person sees as the question limit.

**AI recommendation:** The approved plan (P9) counted the limit in question cost, which the person saw as "question cost 3 of 8". The AI's reading of his run's trace, not his words: his run stopped at question cost 3 of 8 after two questions. The AI proposed that the limit shown to the person be a number of questions, starting at 8, with question cost kept inside the rule, the gap trace and the "why this question" panel.

**Author's decision:** The author's message, after his own real-model run, as in entry 32:

> Why is it not asking me any more questions? There are 6 more open items?

He agreed the change. It replaces P9's person-facing wording; question cost stays the test's cost axis.

**Why:** The AI's reason, which he agreed: a count of questions is what the person can judge, and question cost is the rule's own unit.

**Original / AI-assisted:** Original: the question that found the problem. AI-assisted: the reading of the trace and the change to the limit.

## AI-raised, confirmed by the author

These were raised by the AI and confirmed by the author. They are not claimed as his ideas. The record lists them without a date for each.

- **Personal facts about a named person are never guessed.** AI-raised, confirmed by the author.
- **The targeted second look in the folder.** AI-raised, confirmed by the author.
- **The fifth state, now named "Not available here".** It was first called "cannot be done", and was suggested by the AI from Wang et al.'s four kinds of gap. AI-raised, confirmed by the author: he asked what it was and then wrote "Add the 5th state".
- **The two yes-or-no harm checks.** The AI's recommendation. AI-raised, confirmed by the author.
- **The third rule (the model decides freely), the skip button, the source expansion and the "why this question" panel.** Offered by the AI as options B, D, F and G. AI-raised, confirmed by the author: he asked whether they were really much extra work and chose to add them.
