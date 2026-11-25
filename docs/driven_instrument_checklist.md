# Checklist: an instrument ChromIQ drives itself

One page, for the FIRST brief of a new driven instrument (a table, a strip reader, a chart
reader) and for every review of it. The why behind each line is in
[`docs/adding_an_instrument.md`](adding_an_instrument.md), section 12b; the general instrument
checklist is [`docs/adding_an_instrument_checklist.md`](adding_an_instrument_checklist.md).
Every line was missing from the first brief of the i1iO 2 table drive and cost a round.

## Before any code

- [ ] Recordings of the maker's program from an owner, made with the newest recording tool,
      each paired with the file the maker's program saved in that same session.
- [ ] Timeline and command list made from them (`scripts/recording_timeline.py`); the
      allow-list, speeds, timeouts and caps derived from what was recorded, each with its source.
- [ ] Every number about the device in one facts module, with its source and confidence.
- [ ] A console tester program for a volunteer's device: only recorded lines, every step
      explained and confirmed, a true state and a way out after each, a log that can be analysed
      (template: [`docs/templates/tester_program_step.md`](templates/tester_program_step.md)).
- [ ] An independent safety review before EVERY offer to an owner
      ([`docs/templates/safety_review_brief.md`](templates/safety_review_brief.md)).

## Building it into the app

- [ ] A job with no UI (steps return ids and the true state, never sentences, never answer
      their own questions) and a thin panel; one replaceable factory as the seam for tests.
- [ ] Wire-identity tests: the job sends byte for byte what the reviewed tester program sent.
- [ ] A simulator with its own copy of the recorded timings and limits, every fault at every
      line, and no answer that is only a belief (mark beliefs; replace them when a device answers).
- [ ] One writer, one gate; computed lines from a few builders only; the swept path checked.
- [ ] The QUESTIONS table written first ([`docs/templates/questions_table.md`](templates/questions_table.md)).
- [ ] A hands-off confirmation before every move that follows a question, and a guard at the
      single writer that refuses a move while one is owed; a test fixture fails any test in
      which that guard fired.
- [ ] No default button; Enter, Return and Space never answer; a hands-off answer is accepted
      only after it has been visible for a moment.
- [ ] An "in use" marker written on open, cleared on a clean close, asked about at the next START.
- [ ] "Switch it off" first wherever a move may still be waiting; truthful state texts.
- [ ] A level check after calibration; the chart's identity (and a verification's date)
      recorded per session, so readings never complete another chart.

- [ ] The simulated device reads WHAT LIES ON IT (an image at a true place), never the expected
      values: only then can a test show a wrong sheet, another page, a shift or an uncut sheet
      (`tests/i1io_table/bed_sim.py`).
- [ ] Every row is held against what the chart expects before it is kept; what is dropped leaves
      nothing in any file anybody reads, also after a crash (`workflow/i1io/table/identity.py`).

## Presentation and parity

- [ ] In the Measure tab under START, like a hand measurement; never a blocking window over
      the tab; nothing covers the preview; exactly one red Stop.
- [ ] The first measurement asks after each step; later ones quiet, their questions in pop-ups
      built through the app's shared dialog helpers.
- [ ] A choice needed once is asked once and remembered (changeable in Preferences).
- [ ] Same as the hand path, reusing its code: every run type saved by its own rules, the
      START guards, the completion window, the lock (quit, close box, shortcuts, tab switch,
      Preferences), Manual and Guided.
- [ ] Preview marks from the same geometry that draws the chart; expected beside measured.
- [ ] Inside the instrument's existing Beta switch; Beta off changes nothing (tests).

## Proof and release

- [ ] On-screen proof with a real chart in the fully styled app
      (`scripts/driven_instrument_proof_driver.py`), readings near the expected colours at the
      device's pace, a narrow window, one other language; every picture checked against INDEX.md.
- [ ] Planted faults in copies of the tree (`scripts/planted_faults.py`); every survivor
      gets a test.
- [ ] Independent reviews after every build round
      ([`docs/templates/review_brief.md`](templates/review_brief.md)); findings measured, not only read.
- [ ] A translation challenger pass over every new string, the safety sentences first.
- [ ] No edit while any test tier runs; three green release gates on the final tree, each
      exit code read from pytest itself.
- [ ] Release notes, ⓘ and consent say the same honest limits
      ([`docs/templates/release_notes_honest_limits.md`](templates/release_notes_honest_limits.md)).

## When real results arrive

- [ ] Every recorded line against the app's allow-list (`scripts/recording_vs_allowlist.py`),
      computed lines rebuilt byte for byte.
- [ ] Raw readings replayed through the app's own instrument library and compared with the
      maker's saved file; constants changed only with that evidence, and the simulator with them.
- [ ] "First try" stays in every text until a real device has shown it working.
