# Measurement Report limit sets — Design Record (#182)

> **Status:** design record for issue #182, written 2026-09-08 from the rulings
> in that issue (Knut, 2026-09-04 to 2026-09-07) and built into
> `v4.2.1-beta.1`. Nothing in this document is confirmed behaviour yet: every
> section below is **⏳ Awaiting confirmation**, and a section is promoted only
> when Knut or Sebastian says on the issue that what the app does is what it
> should do (CLAUDE.md, "only CONFIRMED behaviour may be written into a
> specification").
>
> The tolerance numbers of ISO 12647-7:2016 and ISO 12647-8:2021 are NOT in
> this document, not in the code and not in the repository. Whether they may
> ship is Sebastian's open question S-2; until then the two ISO columns read
> `?` and cannot be chosen for a run.

**These specifications are binding.** Knut's rule (2026-08-06): they are
consulted before code in this area changes, and a fault that contradicts them
is reported and approved before it is fixed. Here every section still waits
for confirmation, so the binding part today is the *record* of what was built
and why, not a confirmed behaviour.

Related documents: `unified_measurement_management.md` (the life of a
measurement; §M-PROPOSED holds this feature's two messages),
`verification_printing_and_target.md` (how a verification sheet is printed and
which reference the report uses), `tool_availability.md` (DRAFT; the report is
● for a selection that has a measurement).

The sources this design was built from, named here rather than by reference to
a file nobody on the project can open: the free official previews of
ISO 12647-7:2016 and
ISO 12647-8:2021, CGATS/Idealliance TR 015-2022, the Idealliance G7 Master
Pass/Fail Requirements v35, and ChromIQ's own code. Where a clause was not
readable the row reads `?` and nothing was inferred.

---

## 1. Vocabulary

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

| word | meaning |
|---|---|
| **limit set** | one column of the limits table: the numbers a report is judged against, one per row. The user-facing word is "limit set"; the code says "compliance set" |
| **row** | a *population × statistic*: which patches, which number. "All patches, average" and "Control-strip patches, average" are different rows |
| **PASS / FAIL / COND / INFO / N-A** | the five verdict words (Knut, K-f). COND is short for CONDITIONAL; N-A keeps Knut's hyphen |
| **bound** | a profile run has a copy of a set's limits in its `meta.json` |
| **locked** | the run has a measured verification and has not been unlocked |
| **Overall** | the one word for a whole column (one dated verification) |

## 2. The rows and the sets

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Rows are grouped by population (shape A, Knut K-a): Paper · Solid colours ·
Control strip · Grey ramp of the measured chart · All patches of the measured
chart · Selected patches of the standard's chart · Not evaluated by ChromIQ.
The full list, with each row's unit, status and formula, is
`workflow/compliance_sets.py::ROWS`.

Sets, in order: ChromIQ default (recommended) · ChromIQ tight · Quick check ·
ISO 12647-7:2016 values (read-only) · ISO 12647-8:2021 values (read-only) ·
Custom ISO 12647-7 · Custom ISO 12647-8.

> **WHAT A CUSTOM SET STARTS FROM CHANGED ON 2026-09-11, ON KNUT'S RULING.**
> This line said "each Custom set starts from its parent's values", which was
> true of the *structure* and, with the data file shipping empty, meant that
> every cell of both Custom columns read `?` or `–`. Neither column had a
> limit-bearing row, so neither could be chosen, and no metric could be
> exercised through either.
>
> Knut, 2026-09-11: *"the table columns for 'Custom ISO 12647-7' and 'Custom
> ISO 12647-8' should have selection boxes for all metrics that ChromIQ can
> check, because it is a custom threshold set. […] For testing purposes you can
> set a reasonable value, such as for the ChromIQ default, but those thresholds
> that are not part of ChromIQ default must have set a reasonable value […]
> even if they are not same as those standards (that is not relevant for
> testing the metrics). This applies also to the report limits window in
> Preferences ==> Reports tab. Thus, make sure the metrics have a value that
> can be tested against."*
>
> **So a Custom set starts from its parent's value where the parent HAS one,
> and from ChromIQ's own number everywhere else.** Today the parent has none,
> so every row ChromIQ can measure carries a ChromIQ number
> (`compliance_sets.py::_CUSTOM_PLACEHOLDER`); a licence holder who points
> `CHROMIQ_COMPLIANCE_ISO_FILE` at their own copy still starts from theirs, row
> by row. The two read-only ISO columns are unchanged and still hold nothing.
>
> **No value of either standard is involved, and the numbers say so.** Every
> placeholder is one of ChromIQ default's own figures, 1.5, 2.0 or 3.0, reused
> on the rows ChromIQ default does not limit because it is the right order of
> magnitude for a ΔE00, a ΔCh, a ΔH\*ab or a ΔL\* and for no other reason. A
> test pins the *source* of every number rather than the numbers themselves, so
> one cannot later drift toward a real tolerance for looking more realistic.
> The note under the limits table says whose numbers these are, in both
> windows. The owner's standing rule
> (`docs/design/issue_182_answers.md`) is unchanged and unbroken.
>
> **Only rows ChromIQ can measure get one.** The five rows whose status is
> `unknown`, the three control-strip rows and the two selected-patch rows,
> still read `?` and still have no spin box: ChromIQ does not know which
> patches those populations are, so a number there would be a limit nothing is
> ever compared with. That is the one part of Knut's sentence *"those that
> today are shown as ? shall also have selection boxes"* that is not built, and
> it is an open question rather than an omission: see §11.
>
> Knut has not seen any of this yet.

Factory values (Knut K4/Q1): ChromIQ default 2.0 / 2.0 / 2.0 / 3.0 / 3.0 on
the five ΔE00 rows; tight 1.0 / 1.0 / 1.0 / 1.5 / 1.5; quick 4.0 / 4.0 / 4.0 /
6.0 / 6.0. The grey-balance pair is a **recommendation** (shown in brackets) in
every ChromIQ set, (1.5)/(3.0), (1.0)/(2.0), (3.0)/(7.0), until a healthy
printer has been measured (Sebastian's S-10); exceeding it reads COND, never
FAIL.

A cell is one of: a number (required), a number in brackets (recommended),
`–` (the set puts no limit on the row), `✕` (ChromIQ cannot measure it; the
row stays so the user sees what the standard asks, Knut K2/D16), `?` (the
number is in a clause ChromIQ does not hold or may not show).

## 3. What each row measures

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

* The five ΔE00 rows are the report's existing statistics. The **95th
  percentile is the nearest-rank value**, rank ⌈0.95 n⌉, and the same rank
  splits the best 95 % from the worst 5 %. Below 20 patches the worst 5 % is
  empty and that row reads N-A; the best 95 % and the 95th percentile are then
  every patch, and the report says so.
* **Grey balance of the grey ramp**: ΔCh = √(Δa\*² + Δb\*²) of each R = G = B
  patch against its own reference value under the report's yardstick, average
  and largest. The ramp counts patches with max(R,G,B) − min(R,G,B) ≤ 1.0; it
  is eligible with at least 8 distinct levels (the paper patch counts as a
  level), a lightest level ≥ 90 and a darkest ≤ 10; the paper patch is left
  out of the statistics, composite black stays in. This is the same
  arithmetic as the ISO near-neutral rows; the standards' aim is
  characterization data, ChromIQ's aim is the chart's design (footnote ²).
  TR 015's substrate-relative aim is deliberately not used: a perfect
  relative-intent print scores 0 against the design and up to 1.78 ΔCh
  against that aim.
* **Single-colour ramps 30 % to 70 %**: per device axis (and the grey axis),
  |ΔL\*| against the reference over patches whose tone value lies in
  30..70 %, largest; eligible with at least 3 distinct tone values spanning
  ≥ 20 %. A recommendation (ISO 12647-8:2021 4.2.7 is a *should*).
* Rows needing a reference file for the printing condition (paper white
  against the reference paper, solid colours, CMY hue difference) read N-A
  until such a reference exists (Knut D31: "a reference measurement file you
  supply" is the footing; the reading of such a file is not built yet).

## 4. The verdict words

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Per row: PASS when the value is within the limit; FAIL when over a required
limit; COND when over a recommended one; INFO when the set puts no limit on
the row, or the sheet is not graded, **or the row itself could not be graded,
or the chosen report type judges nothing**; N-A when the chart or the reference
cannot supply the row, with the reason beside it.

> **TWO CAUSES OF INFO WERE MISSING FROM THIS SENTENCE, AND KNUT HAS SEEN
> NEITHER.** An adversarial round drove them on 2026-09-11 and found the
> report's own "How to read" paragraph denying, on page 2, the cause it
> asserted on page 4.
>
> **A ROW that cannot be graded, on a sheet that is.** CH-17: the grey-balance
> rows are shown for information when nobody recorded how the sheet was
> printed and the reference is the chart's own design, because in absolute Lab
> the paper's own tint would fail the row. That has shipped since the rows
> existed; only this sentence was behind.
>
> **A TYPE that judges nothing.** Report type T4, "Printing record (not
> graded)", withholds every verdict by the user's choice. That gap has since
> been filled: §10 describes the six types, so the sentence that used to stand
> here, *"This document does not describe the report types at all, `grep
> "Printing record"` over it returns nothing"*, is no longer true of this
> document and the check it named now returns four hits. It is corrected rather
> than deleted because it was the reason §10 was written.

A sheet is **graded** unless it is the run's own **profiling** chart (a file
directly in `runs/runN/`, printed raw by definition) or a raw drift check.
What a sheet *is* comes from where it lives: a file in
`runs/runN/verifications/<date>/`, or one whose stem ends in `-verify`, is a
verification whether or not it carries the `CHROMIQ_VERIFICATION` keyword (the
keyword exists only since June 2026); a file in no run at all (an i1Profiler
export added to the report) is graded as 4.2.0 graded it. Only the profiling
chart changes: every row INFO where 4.2.0 printed FAIL against the chart's
design.

Per column (Overall): N-A when the set has no limit-bearing row; INFO when the
sheet is not graded; **N-A when the set has limit-bearing rows but NONE of them
could be checked**; FAIL when any row fails; COND for every ISO column (its
values are applied to a chart that is not the standard's chart, footnote ¹);
COND when any row is COND or a required row is N-A; PASS otherwise. The
Overall cell carries its reason as text. The report never prints the word
"conforms" and never puts a standard's name in a verdict sentence.

> **THE THIRD CLAUSE IS NEW, 2026-09-11, AND IT CORRECTS A FAULT RATHER THAN A
> RULE.** Without it a column whose limit-bearing rows are all N-A, and where
> every missing row is a RECOMMENDATION rather than a requirement, fell through
> every clause to PASS, under the sentence *"Every value this limit set
> requires was checked and is within its limit"*, with nothing checked at all.
>
> It was found building report type T3, which shows the two bracketed
> grey-balance rows and nothing else, so it meets that state on the first chart
> without an 8-step grey ramp, which is most of them. It is reachable in the
> full report too, on a measurement with very few patches.
>
> The clause it revises was written here and confirmed by nobody, and it never
> contemplated "nothing was checked", so this is a gap being closed rather than
> a ruling being overturned. **Knut has not seen it yet.** The reason reads:
>
> > This chart supplied none of the values this limit set puts a limit on, so
> > there is nothing to judge. The rows above say what is missing; add those
> > patches to the chart in Create Chart to have them checked.

**A sheet that is not graded says WHY, not just that it is not.** Knut's 12b
(2026-09-09) allowed INFO for a profiling run's report on one condition, in his
words: *"since the measurements are not a verification run and will most often
not fall within set accuracy threshold values. In this case the report output
must explain this."* The Overall reason therefore reads:

> This sheet is not graded, so its numbers are shown for information only. It
> was measured to build a profile rather than to check one, and a profiling
> measurement is expected to fall outside the accuracy limits. That is normal
> here, and it is not a fault.

The sentence it replaced said the sheet was not graded and stopped, which meets
the letter of INFO and none of his condition: a reader seeing large numbers and
no verdict cannot tell whether something is wrong.

## 5. Where the set lives, and when it may change

> **REVISED 2026-09-10 on Knut's report, and it moved for two reasons.** This
> section said the run's limits lock once a verification has been measured.
>
> **A run that is not BOUND has nothing to lock.** The lock never asked whether
> one was, so a project made before #182, which never gets a set copied onto it
> and never will, showed a greyed pulldown over a value stored nowhere: an
> unbound run's limits come from the live Preferences default and are re-read
> every time. Driven on screen, the "Default for new runs" radio in the limits
> window then moved that greyed pulldown, the window contradicted its own report
> body, and on a measurement with no recorded verdict four rows flipped from
> PASS to FAIL on screen with nothing written to disk.
>
> **And one measurement is not a history.** Knut: *"When only one measurement is
> done, I should be allowed to choose the type of report I want to print, and
> which limits to judge against."* The lock exists so that every dated
> verification of a run is judged the same way and the dates stay comparable.
> With one date there is nothing yet to be comparable with. Measured, changing
> the set at that point rewrites three keys, archives the report it replaces and
> leaves eighteen keys of measured data untouched.
>
> **So: the limits lock once a SECOND dated verification of the run has been
> measured, and only on a run that is bound.** Below that, the set may be chosen
> in the report window; choosing one re-binds the run and recalculates that
> date's saved reports, archiving them first, exactly as the unlock path does.
> The unlock gate itself is unchanged.
>
> Still to be confirmed by a human: whether the lock protects comparability
> across DATES, which is what this assumes, or fixes the yardstick the moment any
> verdict is printed, which is stricter; and whether the second verification may
> close the window silently or should say so.



**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

* Preferences → Reports holds the **defaults**: the editable sets' overrides,
  the "Default for new runs" marker, and the checkbox "Allow editing of
  thresholds after the first verification measurement" (off).
* A profile run is **bound** at its first verification measurement, before and
  independent of the autosave setting: the default set's effective limits are
  copied into `runs/runN/meta.json` (`compliance_*` fields). Every dated
  verification of that run is judged with that copy (Knut D9/D20). A later
  change to the set in Preferences does not reach a bound run.
* The run's limits are **locked** once the run is bound AND a second dated
  verification has been measured, and not before. The revision note at the
  head of this section says why both conditions are there and which report
  each came from; this bullet used to state only the second half of the
  first sentence, so a reader who skipped the note read the superseded rule
  as the specification. The
  report window's "Unlock this run's limits" may be ticked only when the
  Preferences checkbox allows it, after a confirmation naming the run and the
  number of dated verifications. Every recalculation (the unlock itself, a set
  change, a change of the run's numbers) first copies each dated report whose
  content has no copy yet into `reports/old/<timestamp>/`, then rewrites the
  file in place (Knut D23; nothing is deleted). A date whose copy cannot be
  written is not rewritten and is named in a window. Identical content is never
  copied twice. A ticked "Unlock" can always be unticked, even after Preferences
  stops allowing edits, so a run can be locked again.
* A **duplicated run** carries its source's choice of set and column visibility
  but not the copy of its numbers: it is bound afresh, to that set, at its own
  first verification measurement.
* A run whose set id a later ChromIQ no longer knows keeps its values and
  verdicts and shows the set as "(historical)" (Knut D23).
* A measurement that is not in a run (an imported file in Downloads) is judged
  with the default set for the session; nothing is written anywhere.
* Column visibility in the Report limits window is remembered per profile run
  when opened from the report window, and in Preferences when opened there
  (Knut K-b). **It is a VIEW setting and nothing else.** Hiding a column asks
  no question, recalculates nothing, and never binds a run to a limit set;
  a refusal of a question about the run's NUMBERS leaves the column choice
  standing, because the ticks were never in that question. The one exception
  is the lock: a run that becomes locked while the window is open has every
  key this window wrote put back, the column choice included, since the
  question there is whether the window may write to the run at all.

  > **BOTH HALVES OF THAT WERE FAULTS UNTIL 2026-09-11, AND THEY WERE ONE
  > FAULT.** Knut reported them separately: *"it is not remembered what I
  > turned off some columns"*, and, on a run with one dated verification and
  > one saved report, a window saying *"This run (run1) has one saved report.
  > Changing the limit set recalculates it with the new numbers…"* with the
  > ruling *"This should only come when thresholds are changed, not if table
  > columns are hidden or shown."*
  >
  > One term carried the column choice into the branch that asks about, and
  > rewrites, a history. Driven in a real window: unticking the two ISO columns
  > raised that question, and answering Cancel, the only sensible answer to a
  > question about a limit set nobody touched, ran the undo and put
  > `compliance_columns` back to empty. With no saved report there was no
  > question at all and the same click bound an unbound run.

## 6. What a saved report carries

> **REVISED 2026-09-10, because the decision below had a consequence nobody
> traced.** "The schema is not bumped, so no report on disk is re-derived" was
> deliberate and is still right about VERDICTS. It was wrong about rows that had
> never been computed at all.
>
> Version 4.2.0 already wrote schema 7 and had no grey balance in its builder,
> so every report saved by 4.2.0 and the first two betas passed the staleness
> test, was never rebuilt, and showed N-A on both grey rows for ever. Surveyed
> on one real disk: 58 saved reports, none carrying a grey block, 33 of them
> already at schema 7. The reason printed beside the N-A said the measurement
> file could not be read again, which is untrue: it was never asked for, and the
> number it was hiding was in the same folder.
>
> **So a report missing a block the current builder always writes is stale, at
> any schema.** The rebuild already carries the saved verdict across untouched,
> so this computes rows that were never computed and re-grades nothing. The rule
> lives in one function, `_report_needs_rebuilding`, so a test can exercise the
> real thing rather than a copy of it.
>
> Still to be confirmed by a human: whether a rebuild should also be offered
> explicitly, which is Knut's "Generate Report button" question. It is not
> needed for a limits change, because closing the limits window already
> re-judges every live-graded column; what neither path can do is re-read the
> measurement file, which is what this revision addresses for these two blocks
> only.



**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Additive to the schema-7 report (the schema is not bumped, so no report on
disk is re-derived): `pass_thresholds` (the old pair, still written),
`compliance` (set id, set label, the run's copy of the limits, the edited
flag), `verdict.rows[].word`, `verdict.overall`, `verdict.summary`,
`grey_balance`, `ramps_30_70`, `de00.p95_rule`, `de00.small_sample`. A report
saved before the words existed shows the recorded pass/fail as words; one with
no verdict at all is graded live against the run's set and says so.

## 7. Settings migration

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Schema 23: the two keys `report_pass_threshold_avg` / `_max` are read once. A
stored pair that echoes 2.0 / 3.0 is dropped; a moved value becomes an
override on ChromIQ default, per value (the average on the three average
rows, the maximum on the two maximum rows), so no user's verdicts move. The
two keys are then removed and never re-created.

## 8. First open after upgrading from 4.2.0

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

What a 4.2.0 user sees the first time: the two spin boxes are gone and the
"Judged against" row is in their place; the results grid has two grey-balance
rows, N-A on most existing verification charts (no 8-step grey ramp), and the
Overall row; on a chart with fewer than 20 patches the worst-5 % row reads
N-A; a profiling measurement reads INFO where it read Fail; a report saved
without a verdict reads "not recorded" as before. The strip under the pulldown
names what the chart cannot supply. Nothing on disk changed.

## 9. Not built in this record

The reading of a user-supplied characterization file and its copy into the
run's `verifications/reference/` folder (Knut K-e); the CMYK measurement
reader (S-3); the tone-ramp generator, the approved-chart list and the
uniformity form (N5). The ISO numbers (S-2). Of the six report types of §10,
the two that judge against a printing condition the user supplies.

## 10. The report type (D28)

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Written 2026-09-11 from Knut's rulings of 2026-09-09 and 2026-09-11 in the
issue, and built in `v4.3.0-beta.4`. His rulings are his; what the app does
with them is not confirmed by anybody.

**Six names, in one pulldown above "Judged against".** Colour summary (one
page), Full colour check, Grey and tone check, Printing record (not graded),
and below a rule, Validation print check (ISO 12647-8) and Contract proof
check (ISO 12647-7). The heading over that rule reads "Against a printing
condition you supply".

**The type belongs to the profile run,** as the limit set does, so every dated
verification of a run produces the same kind of document and the dates stay
comparable. Another run in the project may use a different one. When the runs
loaded into one window disagree, the window falls back to Full colour check
and says so under the pulldown: a window produces one document, and that is
the only answer that withholds nothing and loses no verdict a run recorded.

**Choosing a type recalculates nothing.** A limit set decides what a
measurement is judged against; a type decides which document is produced from
numbers that do not move. No saved report is touched.

**A run may hold reports of several types** (Knut, 2026-09-11: *"the user may
have several uses for different reports"*). **Generate report** writes a dated
report of the type now chosen. The line under the pulldown lists the types the
run has already produced, counted from the files on disk rather than from
anything the window remembers, and it comes before the sentence explaining the
type being pointed at.

**What each type is.**

* **T2, Full colour check** is today's report, unchanged, and is the default
  for every report written before this existed and every run nobody has chosen
  for. Nothing on disk was re-derived to make the type work.
* **T4, Printing record (not graded)** shows the same figures and judges none
  of them: every judged row reads INFO, with a paragraph saying why. A row
  nobody could measure still reads N-A, because "we could not measure this" is
  not a judgement being withheld. Nothing is written; switching back to T2
  brings the same verdicts.
* **T3, Grey and tone check** keeps three rows, the two grey-balance rows and
  the 30 % to 70 % ramp row, and drops the colour rows rather than showing them
  as not applicable. Its one word is about the rows it shows, and the guide
  above them explains only those rows.
* **T1, Colour summary (one page)** is written as its own document rather than
  the full report with rows removed. It carries the run's description at the
  top of the scope section and nothing when that is empty, one line of
  statistics with the verdict, sixteen example colours taken from the chart
  that was measured and spread across what the printer can make, the eight cube
  corners, and the sentence that ChromIQ measures against published values and
  does not certify. No customer or job name (Knut, 2026-09-11: *"No customer
  of job name per today"*). It is about ONE measurement, the one the window is
  on, so the tick that widens every other report to the whole history is
  disabled while it is chosen.

**A type this build cannot produce is shown and refused,** not hidden, and it
is never honoured: the run refuses to store one, and a stored one, which a
project made on a later ChromIQ can carry home, is read as Full colour check.
What is on disk is left alone so that later ChromIQ still finds the choice.

**Not built here:** T5 and T6. Their figures are published in standards
ChromIQ has no permission to include (§9, S-2).

### ⏳ FIXED 2026-09-12: a limit-set change rewrote the TYPE of every saved report

**Confirmed by:** *nobody yet.* **Reported 2026-09-11 and fixed 2026-09-12.**
The half that is not a ruling was corrected: a report generated AS a document
keeps being that document, and a report with no type of its own still follows
the run, which is what it renders as anyway. Both earlier intentions survive
and nothing is lost, so no ruling was needed for that part. What is still open
is only whether a typeless report SHOULD be stamped at all, which changes
nothing a reader sees. Driven on screen
against `ChromIQ-Report-Limit-Demos/Report-Limits-Report-Types/run1`. 

**What was driven.** That run ships three saved reports of one measurement, a
Colour summary, a Full colour check and a Printing record, which is the state
the paragraph above asks for. The window opened on it, the type pulldown was
left where it was, and **one** limit set was chosen. Before:

```
report_2026-11-02_10-00-00.json     Colour summary (one page)
report_2026-11-02_10-00-00_2.json   Full colour check
report_2026-11-02_10-00-00_3.json   Printing record (not graded)
line under the pulldown: Already generated for this run:
    Colour summary (one page) (2), Full colour check (1),
    Printing record (not graded) (1)
```

After, with nothing else touched:

```
report_2026-11-02_10-00-00.json     Colour summary (one page)
report_2026-11-02_10-00-00_2.json   Colour summary (one page)
report_2026-11-02_10-00-00_3.json   Colour summary (one page)
line under the pulldown: Already generated for this run:
    Colour summary (one page) (4)
```

**Where it comes from.** `MeasurementReportDialog._recalculate_run` calls
`stamp_report_type(rep, ctx.run)` on every saved report of every date. Its own
comment says why it was added: a recalculation used to leave reports "claiming
the type the run held when they were first saved, so the record said one thing
and the run another". That reasoning holds while a run has ONE type, which is
what was true when it was written. Knut's ruling of 2026-09-11 that a run may
hold reports of several types makes the run's current choice the wrong source:
the type belongs to the DOCUMENT, which is why it is stored on the report at
all.

**Which rules it touches.**

* *"A run may hold reports of several types"* survives only until the next
  limit-set change, which is an ordinary action a user takes for an unrelated
  reason.
* *"The line under the pulldown lists the types the run has already produced,
  counted from the files on disk"* then names documents nobody generated
  (three extra Colour summaries) and hides two that were.
* Nothing is lost: `reports/old/<timestamp>/` keeps the originals with their
  true types, and §5's archive-then-rewrite rule worked exactly as written.
  What is wrong is what the LIVE files say they are.

**What is NOT claimed here.** Whether the right answer is to leave each saved
report's type alone, to stamp only reports that have none, or something else,
is a ruling, not a defect report. §5 says a recalculation rewrites the verdict;
it has never said anything about the type, and the clause that would settle it
does not exist yet.

**Reproduction:** `scripts/drive_report_types_onscreen.py` drives it as part of
its sweep; the isolated one-action version is in the proof folder for this
round.

## 11. The words the report prints (Knut, 2026-09-11)

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Written from Knut's report of 2026-09-11 and built the same day. His rulings
are his; what the app does with them is confirmed by nobody.

**Report Scope.** The run's description is followed by an empty line before
"The following profile verification runs are included:", so the two do not read
as one paragraph (*"add a new line as empty space before the text…"*). The gap
is `_gap()`, the report's own empty line, the one used under every section
heading.

**"How to read this report" — the five verdict words are five bullets.**
*"This paragraph must describe each 5 words, one at a time in a bullet list,
organised and orderly, not in a messy bulk."* One lead sentence, then one
bullet each for PASS, FAIL, COND, INFO and N-A. Every clause of the paragraph
it replaces survives; what is not about one of the five words (the drift
column, the rule for a column's Overall, what an ISO-named column holds) moved
into a paragraph under the list.

**The report no longer says what it does not claim.** The paragraph used to end
*"and this report never says that anything conforms to a standard"*. Knut:
*"Rephrase so that report text states what the report shows […] which actually
has the opposite effect of building confidence in the report results."* It now
reads that a column named after a standard holds that standard's published
tolerance values applied to the chart you printed, rather than to that
standard's own chart and control strip, so its Overall reads COND at best. Same
fact, stated positively, and the COND cap is no longer unexplained.

**Two classes of sentence, and only the first was touched.**

* **Defensive prose.** A sentence ChromIQ wrote for its own comfort, which no
  grant requires. The struck sentence was the only one of these. Removing it
  does not touch the promise made to Idealliance on 2026-09-09, recorded in
  `docs/design/issue_182_answers.md`: what was promised is that ChromIQ never
  *prints* that a print "conforms to", "is certified to" or "qualifies as"
  anything. That is a promise of ABSENCE, and deleting a denial keeps it.
* **Grant-required.** A sentence a rights holder's terms require to EXIST.
  Fogra's *"It is not a certification, approval or endorsement by …"* beside
  every reference set, and Idealliance's *"GRACoL is a registered trademark of
  PRINTING United Alliance."* Both are untouched and both are still pinned by
  `tests/test_chromiq_never_claims_conformance.py::REQUIRED_DENIALS`. So are
  the two sentences Knut did not rule on, which belong to the Report limits
  window (M-THRESHOLDS-NOT-CERTIFICATION) and to the one-page summary, not to
  the paragraph he read.

**Bound, and locked, explained in the report.** *"what is the difference
between bound and locked? Be specific in the explanation, so that user
understands that chosen limits are bound to chosen 'ChromIQ default' thresholds
as this was used for the first dated verification run of the included
measurement sets."* A paragraph in "How to read this report" now says it, and
it is §5 of this document in his terms: the run holds a copy of the set chosen
when its first dated verification was measured, every later date is judged
against that copy so the dates can be compared, a later change in Preferences
does not reach a bound run, and the copy is locked once a second dated
verification has been measured.

**"(edited)" beside a set name was correct.** Knut read *"Judged against:
ChromIQ default (recommended) (edited)"* and asked why, having edited nothing.
The flag is derived, never stored as a claim: `is_edited` compares the run's
stored copy with the set's effective values, and on the run he was reading the
demo pack had written an edited copy on purpose. It is a fact about the demo
data, not a fault in the flag; the demo pack's own descriptions are being
rewritten separately. Measured: a run bound and left alone reads `edited=False`
for all seven sets.

## 12. Open questions from 2026-09-11

* **The five `?` rows with no spin box.** Knut asked for boxes on *"those that
  today are shown as ?"*. Eleven of the sixteen `?` cells are now numbers. The
  five that are not are the three control-strip rows and the two
  selected-patch rows, whose status is `unknown` because ChromIQ does not know
  which patches of a chart make up those populations. A number typed there
  could never be compared with anything, so the row would read N-A whatever the
  user set: a control that cannot be tested. Building it was refused on that
  ground and is recorded here instead. **For Knut:** should those five rows
  offer a value that ChromIQ will always answer "not applicable" to, or stay
  read-only until ChromIQ can identify a control strip and the standard's
  selected patches in a measured chart?
* **Every measurable row now carries a number in both Custom columns**,
  including the rows the parent standard puts no limit over, which used to read
  `–`. Knut's sentence allows either reading (*"Those that normally are not
  included in the report are set to '-', but shall still be possible to include
  by changing the value"*, then *"make sure the metrics have a value that can
  be tested against"*). The second was followed, because it is the one that
  makes every metric exercisable in the demo pack. A user can set any of them
  back to `–` with the spin box.
