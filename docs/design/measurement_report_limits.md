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
| **PASS / FAIL / COND / INFO / N-A** | the five verdict words (Knut, K-f). COND is short for CONDITIONAL; N-A keeps Knut's hyphen. **Since 2026-09-21 COND is an OVERALL word only** and no row can be judged into it (§14); it stays defined because reports saved before that day carry it on rows |
| **recommendation / should-limit** | a limit the set recommends rather than requires. Drawn in brackets, `[number, "should"]` in a values file, `Limit.is_should` in code. It is judged and aggregated exactly like a required limit; what it changes is that the row carries a numbered NOTE (§14) |
| **bound** | a profile run has a copy of a set's limits in its `meta.json` |
| **locked** | the run has a measured verification and has not been unlocked |
| **Overall** | the one word for a whole column (one dated verification) |

## 2. The rows and the sets

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Rows are grouped by population (shape A, Knut K-a): Paper · Solid colours ·
Control strip · Grey ramp of the measured chart · All patches of the measured
chart · Selected patches of the chart · Not evaluated by ChromIQ.
The full list, with each row's unit, status and formula, is
`workflow/compliance_sets.py::ROWS`.

That sixth heading read "Selected patches of the standard's chart" until
2026-09-18, when Knut changed it (S2w of `issue_182_answers.md`, B8-397) in the
same ruling that gave the two rows under it ChromIQ's own definition of their
population. Under the old heading, ChromIQ's own definition would have been the
attributing-coverage-to-a-standard mistake `compliance_sets.py` already records
being made twice.

Five rows of that table had NO detection method until the same ruling: the
three control-strip rows and the two gamut populations. They are computable
now, so **no row is left in the `unknown` status**, and the three control-strip
rows depend on the chart DECLARING its own strip
(`<chart stem>.control-strip.json`, or a CGATS `CONTROL_STRIP_IDS` keyword).

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
> and from a ChromIQ default everywhere else.** Today the parent has none, so
> every row ChromIQ can measure carries one of those defaults
> (`compliance_sets.py::custom_defaults`); a licence holder who points
> `CHROMIQ_COMPLIANCE_ISO_FILE` at their own copy still starts from theirs, row
> by row. The two read-only ISO columns are unchanged and still hold nothing.
>
> **No value of either standard is involved, and the numbers say so.** A test
> pins the *source* of every number rather than the numbers themselves, so one
> cannot later drift toward a real tolerance for looking more realistic. The
> note under the limits table says whose numbers these are, in both windows.
> The owner's standing rule (`docs/design/issue_182_answers.md`) is unchanged
> and unbroken.
>
> **WHAT THOSE DEFAULTS ARE CHANGED AGAIN ON 2026-09-21.** Until that day they
> were one shared table of ChromIQ's own figures, 1.5, 2.0 and 3.0, and this
> paragraph said so. They are now Knut's researched industry figures where his
> research covers a row and ChromIQ's own numbers where it does not. See
> §2a.
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

### §2a · Where the two Custom columns' starting numbers come from

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Knut, #182, 2026-09-21:

> *"I have filled in the json file with the threshold limits I have manually
> set, based on findings from research online of industry practice and
> reasoned limits from the industry, which are independently set by various
> actors in the industry, companies or communities, not based on ISO standard
> values. I would like these to be set as default for the two Custom ISO
> 12647 columns."*

**A Custom column now draws its starting numbers from three places, in this
order of precedence.** Where more than one could answer a row, the earlier one
wins.

1. **A licence holder's own values file**, for the rows their copy of the
   standard answers. Unchanged.
2. **Knut's researched industry figures** (`compliance_sets::_CUSTOM_INDUSTRY`),
   given PER COLUMN because his file follows each standard's own structure.
3. **ChromIQ's own numbers** (`compliance_sets::_CUSTOM_CHROMIQ_FILL`), for
   the rows his research does not cover, so that Knut's 2026-09-11 rule still
   holds: every metric ChromIQ can measure arrives with a limit to be judged
   against.

Measured against the repository's own empty values file, Custom ISO 12647-7
carries 10 researched figures and 8 ChromIQ numbers; Custom ISO 12647-8
carries 9 and 9. Both columns carry 18 limits, one on every measurable row.

**NEITHER SOURCE 2 NOR SOURCE 3 IS A STANDARD'S PUBLISHED VALUE, AND THE APP
SAYS SO.** The Report limits window's description of its columns is generated
from `compliance_sets::custom_default_counts`, so it names exactly the sources
that have a limit behind them and cannot go on claiming one that does not. The
two `SetDef` blurbs, the report guide's own paragraph and
M-THRESHOLDS-NOT-CERTIFICATION say the same thing in their own words. That a
column NAMED after a standard while holding numbers that are not that
standard's must say so is the attribution this file has had to correct four
times.

**Knut's file also fills rows ChromIQ cannot judge today.** Seven of them for
12647-7 and nine for 12647-8. Those are deliberately NOT defaults: a number on
a row nothing is ever compared with is the shape of "a column that checked
nothing said PASS". They arrive with the detection that makes each row
computable.

**The two columns are no longer identical.** They held the same number on
every row while one table served both. Six numbered rows now differ between
them, so a reader CAN read one Custom run against the other, which the demo
pack's README previously said they could not.

**AND A NUMBER THE USER SET IS NOT MOVED BY ONE WE SHIP.** A per-user override
in Preferences and a run's own bound copy in `meta.json` both survive a change
of the shipped defaults; a row nobody has set takes the new number. Proved by
`tests/test_a_users_own_limit_survives_a_new_default.py`, which asserts the
defaults actually moved before it asserts anything survived them.

**OPEN, PUT TO KNUT AND NOT ANSWERED HERE.** In the ISO values file he sent two
days earlier, two of the six rows the two sets share were looser in 12647-8
than in 12647-7. In this file all six are identical across the two sets. He has
been asked whether that is deliberate; what he sent is what is built.

Factory values (Knut K4/Q1): ChromIQ default 2.0 / 2.0 / 2.0 / 3.0 / 3.0 on
the five ΔE00 rows; tight 1.0 / 1.0 / 1.0 / 1.5 / 1.5; quick 4.0 / 4.0 / 4.0 /
6.0 / 6.0. The grey-balance pair carries 1.5/3.0, 1.0/2.0 and 3.0/7.0 in the
three ChromIQ sets and is an **ordinary limit** in each of them.

> **THIS CHANGED ON 2026-09-21 AND THE NUMBERS DID NOT.** The pair was a
> **recommendation** (shown in brackets) in every ChromIQ set until that day,
> on Sebastian's S-10, and exceeding it read COND rather than FAIL. Knut ruled
> the bracket off ChromIQ's own sets, and off `ramps_30_70_dl_max` in Custom
> ISO 12647-7 with it, so that a bracket only ever appears where a standard is
> involved. See §14. **No set ChromIQ ships marks any row a recommendation
> now**; the notation remains for a licence holder's own values file and for a
> row a user marks in one of the two editable Custom columns.

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

Per row: PASS when the value is within the limit; FAIL when over it,
**whether the set requires that limit or only recommends it** (§14); INFO when
the set puts no limit on the row, or the sheet is not graded, **or the row
itself could not be graded, or the chosen report type judges nothing**; N-A
when the chart or the reference cannot supply the row, with the reason beside
it.

> **COND WAS THE WORD FOR "OVER A RECOMMENDED LIMIT" UNTIL 2026-09-21.** It is
> retired as a row word; see §14 for the ruling and for what replaces it. A
> report saved before that day still holds the word on rows and is shown as it
> was recorded.

> **TWO CAUSES OF INFO WERE MISSING FROM THIS SENTENCE, AND KNUT HAS SEEN
> NEITHER.** An adversarial round drove them on 2026-09-11 and found the
> report's own "How to read" paragraph denying, on page 2, the cause it
> asserted on page 4.
>
> **A ROW that cannot be graded, on a sheet that is. WITHDRAWN 2026-09-13.**
> CH-17 said the grey-balance rows are shown for information when nobody
> recorded how the sheet was printed and the reference is the chart's own
> design, because in absolute Lab the paper's own tint would fail the row. The
> observation is true and the conclusion was Knut's to draw. He drew the other
> one:
>
> > *"the grey metric tests is not about the printer, it is about verifying
> > that the profile created for a specific paper or process condition measures
> > within set acceptable thresholds. The verdicts should be given, but a note
> > can be given in a numbered list of notes, where a verdict is commented, for
> > example regarding the tint of a paper and profile combination."*
>
> **CH-17a replaces it.** The grey rows are judged like every other row. Where
> the grading carries a caveat, the caveat is a NOTE: see §12. Nothing in this
> document ungrades a single row any more; the only things that withhold a
> verdict are the sheet (§4) and the type (§10).
>
> A report SAVED under CH-17 keeps the verdicts it was saved with, per the rule
> that a run keeps its values and verdicts. So an old dated report shows INFO
> on the grey rows where a new one shows a word and a note, and that is
> correct rather than a drift.
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
could be checked**; FAIL when any row fails; COND when any row carries the word
COND, which only a report saved before 2026-09-21 can; PASS otherwise. The
Overall cell carries its reason as text. The report never prints the word
"conforms" and never puts a standard's name in a verdict sentence.

> **TWO CLAUSES WERE STRUCK FROM THAT SENTENCE AND THE DATES MATTER.** It read
> "COND for every ISO column (its values are applied to a chart that is not the
> standard's chart, footnote ¹); COND when any row is COND **or a required row
> is N-A**". The second clause went on 2026-09-21 with Knut's N-A ruling (R1 in
> §14). The first went on 2026-09-22 when he retired the ISO cap itself:
> *"Implement this. The note is sufficient ... ChromIQ's results are only
> indications that results that PASS likely fulfil the standard ... It is not
> proof that results fulfil the standard. The report text notes should explain
> this detail."* Footnote ¹ is still the reason such a column carries its
> caveat; it is no longer a reason the word is capped.

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

> **THIS ONE RULE IS CONFIRMED. Confirmed by: Knut, 2026-09-13.** He questioned
> it on 2026-09-13 having read one of these columns on the demo pack, *"Why are
> most of them INFO, when the thresholds are set and can be tested. Verdict
> should be given when report is calculated"*, and the question was put back to
> him with what overturning it would cost: a profiling sheet's distance from
> the chart's design IS the printer's own error before any profile exists, so
> on an ordinary set it reads FAIL on nearly every row, on nearly every
> printer, every time, by design. His answer, 19:54 the same evening:
> *"For now, leave it as is."*
>
> The confirmation is of **12b and nothing else**. The rest of this section is
> still ⏳ awaiting confirmation, and the marker above says so.

## 5. Where the set lives, and when it may change

> ### ⏳ SUPERSEDED 2026-09-17, AWAITING IMPLEMENTATION: a set change may no longer recalculate a saved report
>
> **Confirmed by:** *nobody yet.* Knut ruled it; nothing is built.
>
> This section says, twice below, that choosing a set in the report window
> *"re-binds the run and recalculates that date's saved reports, archiving them
> first"*, and credits the archive-then-recalculate rule to **D23**. Knut's
> beta-20 test overturns his own D23:
>
> > *"When changing Judged Against, while several reports have been saved and
> > exist, a pop message appears: 'This run (run3) has 2 saved reports. Changing
> > the limit set recalculates every one of them with the new numbers…'. This is
> > wrong functionality. If a report has been generated, those reports shall not
> > be recalculated if I want to create a new report with a different Judged
> > Against threshold set."*
>
> **Why it is more than one sentence.** The lock apparatus in this section
> exists to keep the DATES comparable by binding one set to a RUN. Knut's new
> model makes comparability a property of the DOCUMENT instead: a saved report
> is to carry the settings it was made with, including which measurements were
> included, and selecting it is to restore them (his beta-20 text, registered as
> B8-311). Once a report carries its own set and its own list of dates, the run
> no longer has to hold the yardstick for it, and the question this section is
> built around changes shape.
>
> **What the code does today**, measured rather than read
> (`MeasurementReportDialog._recalculate_run`): every live
> `reports/report_*.json` of the run is copied into `reports/old/<stamp>/`,
> content-hash deduped, then re-stamped with the run's new limits and rewritten
> in place. On the demo project's run3 the archived copy kept `chromiq_quick` /
> PASS and the live file became `chromiq_default` / FAIL. Nothing on disk goes
> inconsistent if it stops: `_yardstick_of` already prefers a report's OWN
> recorded set over the run's, because the run's profiling report is
> deliberately never recalculated.
>
> **Two doors he did not name, and they are open questions for him.** The same
> recalculation runs from *"Unlock this run's limits"* and from the Report
> limits window's own Save. His ruling is about the "Judged against" pulldown.
> His B8-311 model implies none of the three may rewrite a saved report, but
> that is an inference and is not being treated as his answer.
>
> Registered as **B8-310**. Until it is built and he has confirmed it, the
> paragraphs below remain the specification and the code follows them.

> ### ⏳ AWAITING IMPLEMENTATION: what changing a limit set does, and to which report
>
> **Ruled by:** Knut, 2026-09-18, on issue #182.
> **Confirmed by:** *nobody yet.* Nothing has been built, so there is nothing
> for anyone to confirm; this records his ruling in his own words so that the
> build is measured against the document and not against the window.
>
> He elaborated the ruling above the following morning, and said plainly that
> today's behaviour is wrong:
>
> > *"The limit set selected, and the other settings in the 'Settings for
> > selected report showing' frame belongs to a specific report, which is
> > identified in the selection field I called 'Current Report Showing'.
> > Changing the 'judged against' parameter would then only change the limit
> > set for that selected report in 'Current Report Showing', and that would
> > show a red text notifying that settings have changed and to click Generate
> > Report to recalculate and regenerate the report selected (not all
> > reports). Unlocking a run's limits and saving a change in the Edit limits
> > window must result in the same behaviour. When 'Current Report Showing' is
> > set to 'New report....' then the settings specified only applies to the new
> > report created."*
>
> Four rules follow, and none of them may be guessed at:
>
> | # | Rule |
> |---|---|
> | N.1 | The settings in "Settings for selected report showing" belong to the ONE report named in "Current Report Showing". |
> | N.2 | Changing "Judged against" recalculates NOTHING by itself. It marks that one report as stale and shows the red notice: settings have changed, click Generate report. |
> | N.3 | Unlocking a run's limits, and saving a change in the Edit limits window, do exactly the same thing to the same one report. |
> | N.4 | With "New report..." selected, the settings apply to the report about to be created and to no existing one. |
>
> **N.2 and N.3 cannot be built before a saved report is a DOCUMENT.** Measured
> on screen and registered as B8-311: with "Show all measurement runs" ticked,
> one press of Generate report writes one file per dated verification, eleven
> on the run it was driven on, and the pulldown goes from eleven entries to
> twenty-two. "Current Report Showing" names one document, so a document-level
> record has to exist before there is anything for a limit set to belong to.
> The fields are known (type, set id and label, the thresholds copy, the two
> tick boxes and the list of measurements included) and the block is additive,
> so `REPORT_SCHEMA` stays 7.
>
> **The archive-then-recalculate rule below is untouched by this** and must be
> re-read before anything changes: a report that has been SAVED is a record,
> and N.2 is about a report being VIEWED. Registered as **B8-352**, with
> B8-310 naming two of the doors that recalculate today.

> ### ⏳ BUILT 2026-09-18 FOR ONE OF THE THREE DOORS: "Judged against" now recalculates nothing
>
> **Ruled by:** Knut, 2026-09-18, on issue #182.
> **Confirmed by:** *nobody yet.* This records what the code now does, so that
> the next reader is not left with a section that describes the opposite.
>
> Asked directly whether his ruling supersedes **D23**, he answered
> *"Agreed. D23 stands."*, and on Generate, *"It is better that existing
> reports are not overwritten. A user could instead select and delete old
> reports they do not want."*
>
> **The two are read as one rule, and this is the reading that was built.** D23,
> as the last bullet of this section states it, is about HOW a recalculation is
> done: *"first copies each dated report whose content has no copy yet into
> `reports/old/<timestamp>/`, then rewrites the file in place … nothing is
> deleted"*. Whether one happens at all is decided by his beta-20 ruling and by
> N.2 above. So the "Judged against" pulldown now:
>
> * **rewrites no saved report, of any shape**, and therefore archives none:
>   nothing is kept first because nothing changes. Driven on screen before and
>   after, on a project holding reports of four shapes, the count went from
>   **3 of 8 files rewritten** to **0 of 8**, with no entry in the list renamed
>   and no copy left in `reports/old`;
> * **asks nothing**, because the question it used to ask promised exactly that
>   recalculation;
> * **still binds the run** to the chosen set, which is the yardstick for the
>   dated verifications still to come and for any measurement carrying no
>   verdict of its own;
> * and leaves the red "the settings have changed, press Generate report" line
>   as the whole of what happens on screen, which is N.2's second half.
>
> **A report that records no limit set of its own is the case that decides the
> reading.** A rewrite is the only thing that can stamp a set ONTO such a file,
> and the list names an entry from what its file records, so the rewrite is
> what made two of Knut's entries claim "ChromIQ tight" over a press nobody
> made. Archiving a copy first would have kept the old bytes and still left the
> live file lying about itself.
>
> **THE OTHER TWO DOORS ARE UNCHANGED**: unlocking a run's limits, and saving a
> change in the Report limits window, still recalculate the run's dated reports
> and still archive each first. Whether N.3 (*"Unlocking a run's limits and
> saving a change in the Edit limits window must result in the same
> behaviour"*) reaches them is an open question for Knut, registered as
> **B8-310**, and nothing here assumes an answer.
>
> Registered as **B8-384**. The last bullet of this section still describes all
> three doors recalculating; it is left as the record of what was agreed, with
> this block saying which of it is still true of the code.

> ### ⏳ BUILT 2026-09-18 FOR A SECOND DOOR: unlocking a run recalculates nothing
>
> **Ruled by:** Knut, 2026-09-18, on issue #182.
> **Confirmed by:** *nobody yet.* This records what the code now does.
>
> He read the window that appears when *"Unlock this run's limits"* is ticked,
> quoted it back in full, and ruled:
>
> > *"The description is wrong. All dated reports shall NOT be recalculated,
> > only the selected report will be recalculated and report text recreated
> > according to new values."*
> >
> > *"A selected 'Report shown' can have all the settings unlocked, as
> > previously mentioned, and a change of the settings will update the selected
> > report only. If a new report is to be created, then the user must select
> > 'New report...' option in 'Report shown'."*
>
> **What was built, and why it is "nothing" rather than "one report".**
> Unlocking changes no number: it only lets the user change one. Under N.2 and
> N.3 a change then belongs to the ONE report named in "Report shown", marks it
> stale and is applied by pressing Generate report. So the unlock door now
> calls no recalculation at all, rewrites no file and archives none. Re-stamping
> files with numbers nobody has changed yet would be a rewrite that says
> nothing, and for a generated document it would break the rule the block above
> is built on: a document records the settings it was made with and is never
> recalculated under its reader.
>
> **The question in front of it lost the clause that was false**, and gained
> nothing: the replacement sentence is new user-facing text and waits in
> §M-PROPOSED of `unified_measurement_management.md`, unapproved.
>
> **ONE DOOR STILL RECALCULATES: the Report limits window's Save.** It asks its
> own question at the moment the rewrite happens, which is the right moment for
> it, so no warning was lost with the unlock door's. Whether N.3 reaches that
> door too is **still an open question for Knut** and is deliberately not
> assumed: his words cover it (*"saving a change in the Edit limits window must
> result in the same behaviour"*), and re-aiming another round's guards on an
> inference is how this window has been broken before. It stays **B8-310**.
>
> Registered as **B8-391**.



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
> in the report window; choosing one re-binds the run. (It also recalculated
> that date's saved reports, archiving them first, exactly as the unlock path
> does. **That half is superseded** by Knut's ruling of 2026-09-18 and is no
> longer what the code does: see the "BUILT 2026-09-18" block at the head of
> this section.) The unlock gate itself is unchanged.
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
  *⏳ Awaiting confirmation (beta 37, challenge round B, H3).*
  **Confirmed by:** *nobody yet.* T4 prints neither the note saying what a PASS under a
  standard's name is, nor the guide paragraph about such columns, nor the
  line under each sheet saying "This verdict was recorded when the report
  was saved, against the limit set …": it grades nothing, so all three were
  about words the page never shows. Its "Judged against" row stays, as
  Knut's earlier design names the set there; whether it should is a
  question put to him (the beta-37 register entry).
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
reads that a read-only column named after a standard holds that standard's
published tolerance values and nothing else, that ChromIQ ships none of them, so
such a column is empty unless a licence holder has supplied its figures, and
that an editable column starts from those supplied figures where there are any
and from ChromIQ's own numbers where there are none. Either way the values are
applied to the chart you printed rather than to that standard's own chart and
control strip. Same fact, stated positively.

**AND THE CAP IT USED TO EXPLAIN IS GONE, ON KNUT'S RULING OF 2026-09-22.** The
paragraph ended "so their Overall reads COND at best" until that day. He struck
it: *"Implement this. The note is sufficient. Most users are just interested in
knowing if the measurements passed against the criteria set, and we do not
supply charts that are defined by a standard, do we? Not even the metrics we
define are 'the standard's metrics', because they are our own design ... so
ChromIQ's results are only indications that results that PASS likely fulfil the
standard ... It is not proof that results fulfil the standard. The report text
notes should explain this detail."* Such a column now reads PASS or FAIL like
any other, and the paragraph ends instead with what that PASS is: an indication
that the print would likely meet the standard, and not proof that it does.

**The whole weight of the promise is now on that note**, which was true of the
word before and is worth stating plainly. `applies_a_standard` decides whether
it is printed, `STANDARD_CAVEAT` is what it says, and
`tests/test_a_custom_iso_column_carries_the_same_caveat.py` asks for it with
exactly the strictness it used to ask for the word.

*(The sentence recorded here until 2026-09-12 was "a column named after a
standard holds that standard's published tolerance values", which took three
attempts to make true. See §2k of `issue_182_answers.md`: it is false of the
editable columns, false of the read-only ones as ChromIQ ships, and the second
correction was false in the one state it was written to cover. None of these
strings is state-aware, so each is now a condition rather than a state.)*

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

**THE REPORT IS A DOCUMENT PRINTED FOR SOMEONE WHO HAS NEVER SEEN THE WINDOW
(Knut, beta 20, 2026-09-17).** *"the text must be written as if it is a
separate document printed for a customer, and that customer knows nothing of
the Measurement Report windows, buttons, selections that can be made or
changed ... shall only contain data and results relating to that one reports
settings, and not show information that other reports exist with other 'judged
against' threshold sets."*

Two rules, and both are now pinned by
`tests/test_the_report_reads_as_a_printed_document.py`, which renders every
report type and refuses a list of phrases:

* **No window vocabulary.** Five sentences named something only the window has,
  and each is gone: *"runs in the list above are hidden by you (unticked)"*,
  *"the limit set chosen in this window"*, *"ticked in Preferences → Reports"*,
  *"the reason is shown when you point at the cell"* (a printed sheet has no
  hover) and *"use Check & Refine ▸ Analyse Profile Quality"*.
* **No other reports and no other limit sets.** The Report Scope block that
  named every measurement left out AND the set each was judged against is
  removed, twelve entries on the demo project. The `kind == "compliance"`
  warning is removed with it; it was already unreachable, because
  `_one_limit_set` narrows the runs before it is asked, and the branch is kept
  empty so a future change to that narrowing meets this ruling and not the old
  paragraph.

**What replaces them, and why something had to.** Sebastian's rule of
2026-08-10 still stands: a filtered report may never pass as the complete
history. So the Scope now states, in the document's own voice and without
saying who filtered it or why, *"This report covers {n} of the {total}
measurements recorded for this run."* Unticked and judged-on-other-numbers are
the same fact to the reader: not in here.

*⏳ **What is counted, awaiting confirmation (2026-09-22, B8-778 K14).** The
code had drifted from this sentence to "recorded for this project" and counted
every run's sheet plus every dated verification, so Knut's Printing record of
three profile runs said "1 of the 18". On his ruling that the count relate to
the run type and to the measurements in "Included measurements": a document of
verifications is counted against the dated verifications of the runs in that
list ("recorded for this run", "for these runs"), and a document of profiling
sheets against the project's profiling measurements ("recorded for this
project's profile runs"). A document mixing both kinds keeps the old count.
Whatever is counted is still read off the disk, never out of the window.*
**Confirmed by:** *nobody yet.*

**Still open, and it is Knut's:** a measurement left out is no longer named
anywhere at all, including in the WINDOW. If he wants the window (not the
document) to keep saying which measurements it dropped and why, that is a new
window message and needs its own wording.

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


---

## 12. Notes on a verdict

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Knut's ruling of 2026-09-13, quoted in full at CH-17a above, asks for two
things: the verdicts are given, and *"a note can be given in a numbered list of
notes, where a verdict is commented"*. The second half is a mechanism this
document did not have, so it is written down here.

**CH-30. A note comments a verdict; a reason explains its absence.** They are
different fields and they may never be merged.

| | when it appears | what it says |
|---|---|---|
| `reason` | the row has NO verdict: it reads N-A, or INFO because nothing could be judged | why the row could not be judged |
| `notes` | the row HAS a verdict: PASS, FAIL or CONDITIONAL | what a reader should know when weighing the number |

Merging them is what produced a grey row with no verdict on a chart that had
supplied every value the row needed.

**CH-31. A note lives and dies with the verdict it comments.** If anything later
withdraws the verdict, the note goes with it. The Printing record (§10, T4)
withholds every verdict by the user's choice, so it prints no notes: a note
there would comment a judgement the document does not make, and naming two rows
of eight would imply the other six had been judged. This is not a property that
holds once at judging time; it holds after every transformation of the rows.

**CH-32. One numbering for the whole document, in row order, from 1.** One
number per distinct note however many rows carry it: a note on three rows is one
note naming three rows, not three notes saying the same thing. A report holding
several measurements numbers across all of them, because two "note 1" on one
page is two documents.

**CH-33. The verdict cell carries the number.** A numbered list nobody is
pointed at is a paragraph. The marker and the list come from one computation, so
they cannot disagree about which note is note 1.

**The one note that exists so far** is `printing_unrecorded`, on the two
grey-balance rows, when nobody recorded how the sheet was printed and the
reference is the chart's own design. It says that the row is judged against the
chart's own design in absolute Lab, that the paper's own tint is inside that
measurement, and that a good print on a warm or tinted paper therefore reads
higher than the profile deserves. That is Knut's own example, *"regarding the
tint of a paper and profile combination"*.

**CH-34. A report that was never saved is not a report that lost its verdict.**
Two different absences, and until 2026-09-13 the window printed the second
sentence for both. A column built live from a measurement with no report beside
it is worked out now, against the run's current set, and says so; a report
found on disk with no `verdict` block was saved by a ChromIQ that did not keep
one, and says that instead. Knut, reading the wrong one of the two on a run's
own profiling measurement: *"The statemend 'It was saved by a version of
ChromIQ that did not yet keep the verdict together with the measurements' seems
wrong."* It was. See B8-110.

The distinction is not cosmetic. The first sentence tells a reader nothing is
missing and offers the Preferences tick that would save one next time; the
second tells them their file is old and their data was discarded. ChromIQ saves
a report under a dated verification and not under the sheet a profile was built
from, so the first case is the everyday one and it was the one being described
as damage.


---

## 13. The list of generated reports (Knut, 2026-09-18)

**⏳ AWAITING IMPLEMENTATION.** **Ruled by:** Knut, 2026-09-18, on issue #182.
**Confirmed by:** *nobody yet.* Nothing below is built, so there is nothing for
anyone to confirm. It is written here in his words, before any code, so the
build is measured against the document and not against the window.

This section supersedes the "Saved reports" pulldown as it exists today. It is
the model his five beta-21 defects are all symptoms of, and it is why he wrote
*"The measurement report does not behave as specified, so I will not comment
until it is implemented."*

### 13.1 What he specified

> *"I suggest that the area on the right side of the Report Type, to the right
> of the help icon, is made into a selectable and scrollable selection box,
> similar to the selection box listing measurements included in the report, but
> in this box, the already generated reports can be clicked, which reads the
> report files and brings the report back into the window (with all its
> settings used), without having to re-generate anything.*
>
> *This selection box needs height to show at least 3 to 4 rows of text, and
> only one named report can be selected at a time … Whenever I then change
> report type or Judged against, or limit values, or the checkboxes for "Show
> all measurement runs" or "Show detailed data for each run", then it is
> checked if this report type and judged against combination already exists. If
> it exists the user will be asked if he wants to update the existing report
> (overwrite) or create a new report. The list of reports need to have names
> generated, with date and time, that reflect their selections, so that a user
> can distinguish between them. F.ex. "Run type, Judged agains, All runs, with
> details, <date_time>" … It is possible that this List of Existing reports
> needs more space than possible on the right side of Report type field. Then
> it may need to be below the Generate Report button, and above the Report type
> field … Having this list, also requires a "Delete Selected Report" button …
> which then creates a dated report folder in the old/ folder where the files
> for that report is moved to … It is allowed to have several reports in the
> list of generated reports with the same setup and name, only distinguished by
> the date and time. If a report is selected and then viewed in the Measurement
> Report window, changing limits (or other settings that affect the report)
> will update that report, unless user answers in the mentioned popup message
> that he wants to create and generate a new report with the changes made."*

### 13.2 The rules, numbered

| # | Rule |
|---|---|
| L.1 | The generated reports are a **list box**, 3 to 4 rows tall, scrollable, one selection at a time. |
| L.2 | Clicking one **reads its files and brings that report back into the window with every setting it was made with**, and regenerates nothing. |
| L.3 | Each entry's **name is generated from its own settings plus date and time**: report type, limit set, whether all runs were included, whether detailed data was shown. |
| L.4 | Several reports may share a setup and a name, distinguished only by date and time. |
| L.5 | Changing report type, "Judged against", a limit value, or either checkbox, **checks whether that combination already exists** and, if it does, **asks**: update the existing report, or create a new one. |
| L.6 | With a report loaded, a settings change **updates that report**, unless the user answers the question by asking for a new one. |
| L.7 | A **"Delete Selected Report"** button MOVES that report's files into an `old/` folder; nothing is destroyed. Which `old/` depends on the report's span: one dated verification → that date's folder; several dates of one run → the run's `verifications/old/`; several profile runs → the project's. |
| L.8 | **SUPERSEDED by L.8b.** Placement: the list goes below **Generate report** and above **Report type**, with **Generate report** and **Delete Selected Report** beside it on ONE LINE. *(Revised by Knut, 2026-09-19: the rule first said stacked vertically "so the buttons read as belonging to the list", which is what beta 22 shipped. Shown the released window, Basti asked whether the two buttons, the pulldown and its help button could share a line; Knut answered "Implement the one line suggestion, then we can review on the released beta." The buttons still sit immediately beside the pulldown, so the original intent holds; what changes is that the window stops spending 34 px of height on the arrangement.)* It may be collapsible. |
| L.8b | **The whole area between the title's coloured line and the graph tabs is laid out from Knut's mockup.** *"Analyse the position of all components in the image and place them accordingly. Note that a frame called 'Report settings' encompass all the relevant buttons and input controls that are related to the settings for a report. The report shown is above the frame, with its help icon, and two text elements: the text 'Click a report to load ...' to the right of the 'report shown' (and its help icon) and the 'Already generated...' below the 'report shown' input box. Below the 'Report settings' frame there are 4 buttons and a help icon (starting left with Generate Report, then Delete Selected Report, then Save Report As PDF, then Reveal Folder, then help icon). Inside the 'Report settings' frame all the remaining buttons and elements are placed carefully. Replicate that."* |
| L.9 | The window says to pick a report to load one, and says "click Generate Report to create the first report" when the list is empty. |
| L.10 | Report limits: the column "This run" becomes **"This report"**, reflects the LOADED report's limits, and is editable for the loaded report when unlocked. Editing a shared set (e.g. "ChromIQ tight") affects every report using it but changes no report until it is regenerated, and a warning window must say so. Thresholds of a report that is NOT loaded may not be edited. |

### 13.2b L.8b in full, and where L.8 stops applying

**Ruled by:** Knut, 2026-09-19, on issue #182, with a mockup image saved at
`~/Desktop/ChromIQ-knut-beta25-batch/mockup-report-window-layout.png`. His
words are quoted verbatim in L.8b above. **The old L.8 text is left standing,
marked superseded, rather than overwritten**: it is what beta 22 and beta 25
shipped, and the two rulings a day apart are the record of how the window got
here.

What L.8b changes against L.8, read off the image and measured on it:

| element | L.8 (beta 25 as shipped) | L.8b (his mockup) |
|---|---|---|
| "Report shown" | fourth row down, with Generate report and Delete Selected Report to its LEFT on the same line | the FIRST row under the intro sentence, with only its help button and the hint to its right |
| "Already generated for this run: …" | rides on the "Report type" row, elided against the type's own description | its own line directly under the pulldown, starting at the pulldown's left edge |
| Add / Remove / Clear, the measurement list, Report type, Judged against, Edit limits, Unlock, the two tick boxes | loose rows of the window | all inside a frame titled **"Report settings"** |
| the measurement list | unlabelled, tooltip only | labelled **"Included Measurements in report:"** |
| Report type and Judged against | two independent rows, the pulldowns 32 px out of line | one grid, the two pulldowns on one left edge |
| the two tick boxes | on the Save-as-PDF row | to the right of the **Report type** pulldown |
| Generate report, Delete Selected Report, Save report as PDF, Reveal folder | split across two rows, two of them beside the pulldown | one row UNDER the frame, in that order, help icon last |

**What it costs, measured (B8-460).** The frame's title and margins, the list's
new label and the "Already generated" line no longer sharing a row add 61 px to
the window's own unshrinkable minimum, of which 39 were bought back by
tightening the spacings inside the frame and 30 more are given back by
`_compact_the_settings_frame`, a rung of `showEvent`'s ladder that runs only
when the screen cannot take the roomy version. Measured against the 800 px
screen this window's floor is designed for: 781 px before that rung, 751 after,
against a 760 px cap, with the report view keeping every pixel it had.

### 13.3 What the app does today, measured

Driven on screen 2026-09-18,
`scripts/drive_b22_knuts_five_report_defects.py`, on a project with one profile
run, two dated verifications and two saved reports. Photographs and the JSON
are in `~/Desktop/ChromIQ-beta22-proof/knut-report-and-warnings/D-five-defects/`.

| his defect | measured |
|---|---|
| the arrangement | "Saved reports" sits at y=388, BELOW Report type (y=292) and Judged against (y=340); L.8 puts it between Generate report (y=250) and Report type. The three boxes are 301 / 264 / 478 px wide and not aligned. There is no Delete-Selected-Report button beside the list, no empty-list sentence, and the list is a one-row pulldown rather than a 3-to-4-row box. |
| picking one does not update the window | picking each entry in turn: the selection sticks, and the rendered document's hash **does not change**. |
| picking one does not restore its settings | Report type and "Judged against" do not move when the selection changes. *(On this project both saved reports share a type and a set, so this reading is structural rather than decisive; the decisive evidence is that nothing in the pick path writes to those controls.)* |
| Generate adds reports instead of rebuilding the selected one | **one press of Generate wrote TWO files**, one per dated verification: 2 files on disk → 4. Ticking "Show all measurement runs" and pressing Generate again wrote **two more**: 4 → 6. Nothing was rebuilt. |
| changing "Judged against" relabels every entry and writes another | all **six** entries were relabelled from "ChromIQ default (recommended)" to "ChromIQ tight", and **all six files were rewritten in place**, including the two originals that carried no recorded set at all. One confirmation was shown, *"Change this run's limit set?"*. No new file was added on this project; Knut saw a third report created on his, which has more reports of more shapes. |

### 13.3b Knut's rulings of the same evening, and what they removed

**Ruled by:** Knut, 2026-09-18, on issue #182, answering three questions put to
him after the five defects above were measured. **Confirmed by:** *nobody yet* —
these are his words; what the app now does with them is not confirmed.

| # | His ruling |
|---|---|
| K.1 | **SUPERSEDED by K.7 (§13.8), 2026-09-19.** *"Nothing is ever overwritten, and there is no update-or-create question. It is better that existing reports are not overwritten. A user could instead select and delete old reports they do not want."* So Generate report always wrote a NEW report and the user pruned the list with Delete Selected Report. The question L.5 describes was **withdrawn** on this ruling: it was in §M-PROPOSED of `unified_measurement_management.md`, never had an `M-` id, and nothing in the code referred to it. *(Knut reinstated a three-button form of that question on 2026-09-19, in his own words and ending "This feature overrules a previous ruling that Generate Report always should create a new report." The text above is left standing, marked superseded rather than overwritten, because it is what betas 22 to 25 shipped and the two rulings a day apart are the record of how the window got here. K.7 and §13.8 carry the new one. L.5 and L.6 come back with it, in the shape §13.8 states.)* |
| K.2 | **D23 stands.** Asked whether the archive-then-recalculate rule still held after his beta-20 report, he answered *"Agreed. D23 stands."* Changing "Judged against" must not rewrite, relabel or touch a saved report on disk. **BUILT 2026-09-18** for that one door, including for reports written by an earlier ChromIQ: see the "BUILT 2026-09-18" block in §5 for the reading of D23 that was taken and why, and B8-384 for the before-and-after measurement. |
| K.3 | **A pulldown is acceptable.** *"It is ok that 'Current Report Showing' is a pulldown list if that saves space in the window."* So L.1's 3-to-4-row scrolling box is not built; what survives of it is the NAME an entry carries, which matters more when one row is visible at a time. |
| K.4 | **One report is one line, whatever it spans.** *"If I make a report that has all dated verifications included, and this report outputs a text representing all of those measurements, that is still only ONE report listed in the pulldown."* |
| K.5 | **The per-dated-verification records count too.** *"If the list of reports in 'Current Report Showing' have one report per dated verification (by default created during measurement), then each of those reports, when selecting one, should load and show with its report text in the window. And each of those will automatically have the settings updated to what was used when generating those reports (Correct report type, correct Judge Against used, 'Show all measurement runs' OFF (since it is only one date), etc.)"* |
| K.6 | He proposes renaming the control **"Current Report Showing"**. The wording is his and is **not settled**: he offered it twice as a suggestion (*"a better name could be given if you find a better wording for its use"*). |

**And one question he asked back, answered in §13.5.**

> *"When verification measurements are made, a measurement report is saved, but
> this should only save the raw data needed to generate a report. If an actual
> report is generated, then that report is probably using some default
> settings. Are these defaults specified somewhere?"*

### 13.4 What has to exist before any of this can be built

**A saved report is not a document today.** It is a per-measurement verdict
record: that is why one press of Generate writes one file per dated
verification, and why "the report selected" has no single file to rebuild.
L.1 to L.7 all name one document, so the document-level record (B8-311) is the
first thing, and it is additive: type, set id and label, the thresholds copy,
both tick boxes, and the list of measurements included. `REPORT_SCHEMA` stays 7.

**The question of L.5 is new user-facing text** and is in §M-PROPOSED of
`unified_measurement_management.md`, unapproved, with the two things about it
that his paragraph can be read two ways.

**Nothing may be deleted or renamed on disk by this change.** Every report a
user already has must still open, and L.7 moves files rather than removing them.

Registered as **B8-380** to **B8-384**, under B8-375.

### 13.5 The defaults the automatic measurement-time report uses

**Measured 2026-09-18 in `ui/tabs/tab_measure.py::_maybe_save_measurement_report`,
which is the only place ChromIQ writes a report by itself.** This answers K.6's
question and nothing here is a proposal.

| what | where it comes from | written down anywhere? |
|---|---|---|
| whether a report is written at all | Preferences ▸ Reports ▸ "Save measurement report", **off** as shipped | the preference is on screen; the default is not in any document |
| the report **type** | `run_report_type(run)`: the profile run's stored type, and `t2_full_colour_check` for a run that has never had one chosen | D9 and D28 say the type belongs to the run; the FALLBACK is `REPORT_TYPE_DEFAULT` in the code and appears in no document |
| the **limit set** | `TabMeasure._report_limits_for(ti3)`: the run's bound copy, or the Preferences default set for a run that is not bound | §5 of this document, in full |
| **"Show all measurement runs"** | not recorded, and nothing sets it: the two tick boxes are report-window view settings that do not exist at measurement time | **nowhere** |
| **"Show detailed data for each run"** | the same | **nowhere** |

**So: two of the five are specified, one is in the code only, and the two tick
boxes are specified nowhere at all**, because until the document record existed
there was nothing for a saved report to record them in.

What the window now does about the last two is K.5's own sentence and no more:
an entry that records no document of its own is loaded with its own recorded
type and limit set, and with both tick boxes OFF, *"since it is only one date"*.
Nothing is written to disk to achieve that. Whether the automatic record should
itself carry a document block, so that those two are a fact on disk rather than
an inference at load time, is **not built and is a question for Knut**: it would
also take every such record out of reach of §5's unlock recalculation, which is
B8-310 ground.

### 13.6 The defaults, specified (Knut, 2026-09-18)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, 2026-09-18, on issue #182,
answering §13.5 above. **Confirmed by:** *nobody yet.* Built for beta 22 on his
instruction (*"Please add all of this in beta 22, not in beta 23"*); what the
app now does with his words is not confirmed by anyone.

| # | Rule |
|---|---|
| P.1 | **Preferences ▸ Reports** holds the Measurement Report DEFAULTS. The frame is named **"Measurement Report Defaults"**. |
| P.2 | Under the **Report limits…** button, a **"Report type, default"** pulldown. It is used when the report window opens on a run that has generated nothing, when **"New report…"** is chosen, and for the report written automatically after a measurement. |
| P.3 | Two tick boxes give the defaults for **"Show all measurement runs"** and **"Show detailed data for each run"**. **Both default ON.** |
| P.4 | **No "Judged against" selector** in that frame: *"The Report Limits button contain the Judged Against default chosen, so no separate selection box is needed."* It is `compliance_default_set`. |
| P.5 | The report written automatically during a measurement carries **both tick boxes OFF**, always, *"that is natural because it is one measurement only"*, and ignores P.3. |
| P.6 | The **type still belongs to the RUN** (D9). P.2 is what a run that never chose gets: *"The type belongs to the run, yes, but the default should be the 'Full colour check'."* |
| P.7 | **"Save measurement report after each measurement"** in Preferences is **default ON**, and the Measure tab shows a **"Save measurement report"** control that starts from it. With the preference OFF the control starts OFF and the user may still turn it on. It is **remembered per run**, like every other Measure setting. |
| P.8 | The automatic record carries a **document block of its own**, so both tick boxes are a fact on disk rather than an inference at load time. |
| P.9 | **"New report…"** is the **first** entry of "Report shown". Choosing it loads every default from Preferences, which the user may then change; nothing is written until Generate report is pressed. |
| P.10 | Opening the window selects **the latest report created**, with the settings it was made with — not "New report…". |

**What P.7 measured, and it corrects §13.5's table.** *"whether a report is
written at all"* is listed there as *"Preferences ▸ Reports ▸ 'Save measurement
report', **off** as shipped"*. That is **wrong**: `save_measurement_report` has
been `True` in `core/settings.py` since schema 10, and `_migrate_save_report_
default` exists to drop a stored echo of the old `False`. The row was read off
`self._settings.get("save_measurement_report", False)` in `tab_measure.py`,
whose second argument never applies because `AppSettings.get` falls back to
`DEFAULTS`. So the shipped default did not change; what is new is the control on
the Measure tab and its per-run memory.

### 13.7 The flags a generated report's name carries (Knut, 2026-09-18)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, 2026-09-18.
**Confirmed by:** *nobody yet.*

> *"The report names created should include flags that indicate the settings,
> just as Report type and Judged against"*

| # | Rule |
|---|---|
| F.1 | "Show all measurement runs" ON and every date included → **"All dates"**. |
| F.2 | OFF, more than one date in the list, exactly one included → **"One date"**. |
| F.3 | OFF, more than one in the list, more than one included but not all → **"Multiple dates"**. |
| F.4 | The list holds ONE measurement → **"Show all measurement runs" is set OFF automatically**, and the name carries **"One date"**, *"including all the automatically created reports during measurement"*. |
| F.5 | "Show detailed data for each run" ON → **"Detailed"**. |

**F.4 is a behaviour rule, not a naming one**, and it beats P.3: a window whose
list holds one measurement turns that box off and greys it, whatever
Preferences says. It is given back when the list grows, so opening a window on
one sheet and then adding a project widens the report exactly as before.

**The flag is decided from what the document COVERS, not from the tick box
alone**, so it cannot disagree with the page: one measurement is "One date"
whatever the box says. It is stored in the document block as an **id**
(`all_dates` / `one_date` / `multiple_dates`) and translated when the name is
DISPLAYED, exactly as the type id and the set id beside its English label
already are. Nothing of a report's name is written to disk, so a report named
on a German machine reads in English on an English one.

**F.3's state cannot be reached from the window as it is built**, and that is
reported rather than built around: with "Show all measurement runs" OFF,
`_runs_for_report` returns the ONE measurement the window is on and the row
ticks are not consulted, so "OFF with several ticked" produces no document of
several. The flag is computed from the member list, so the day that changes
this says the right word without being touched.

### 13.8 K.7 in full: Generate report asks, and a report keeps its creation stamp

**Ruled by:** Knut, 2026-09-19, on issue #182, in the same comment as L.8b.
**Confirmed by:** *nobody yet.* This is his ruling and what the code now does
with it; nobody has confirmed that what it does is what it should do.

> *"When a report from 'Report shown' is selected, as we know, all settings are
> updated reflecting the selected reports settings when it was created/saved.
> If any of the settings are changed, a red text message will show user that he
> must click Generate Report to apply settings. When Generate Report is then
> clicked, the user must be shown a popup message with following text (or
> similar):*
>
> *Settings were modified for the selected report. / What do you want to do? /
> 1. Update selected report with selected settings. / 2. Create new report with
> selected settings. / 3. Cancel*
>
> *The window must then have three buttons: Update, Create New and Cancel.*
>
> *Update button will keep the current selected report, then append on the
> ending of the report name " - updated `<date> <time>`", then recalculate and
> update the report text according to the new settings. The same function is
> used as when 'New report...' option is selected then Generate Report clicked,
> but is instead updating the selected report.*
>
> *'Create New' button will perform the same function as if 'New report...'
> option is selected, then use the selected settings, then recalculate and
> update the report text according to the new settings. A new report will be
> created.*
>
> *Cancel aborts the Generate Report function.*
>
> *This feature overrules a previous ruling that Generate Report always should
> create a new report."*

…and, in the same breath:

> *"when a report created the first time the trailing ' - saved `<date>
> <time>`' should not be added (created time stamp already part of the
> beginning of the name)."*

| # | Rule |
|---|---|
| K.7 | **Generate report ASKS** when a report from "Report shown" is selected AND one of its settings has been changed since the page was drawn. Three buttons: **Update**, **Create New**, **Cancel**. This supersedes K.1. |
| K.7a | **Update** keeps the selected report: its document id and its creation stamp do not move, the files it is made of are rewritten in place, and its name gains *" - updated `<date> <time>`"*. |
| K.7b | **Create New** is "New report…" followed by Generate: a new report, with the settings on screen. |
| K.7c | **Cancel** aborts Generate report. Nothing is written. |
| K.7d | **A report created the first time carries no trailing "saved" stamp**, because its creation time is at the beginning of its name. |
| K.8 | **All five settings of a selected report are restored** when it is selected and when the window opens on it: the included-measurements ticks, Report type, Judged against, "Show all measurement runs" and "Show detailed data for each run". This supersedes the half of B8-388 that left the two tick boxes to Preferences. |

**What the build does with them, measured (B8-490, B8-491).**

* K.7's condition is one predicate, `_settings_were_modified`, shared with the
  red line, so the line and the question cannot disagree about whether
  anything moved.
* K.7a is `rewrite_report`, the same function §5's archive-then-recalculate
  rule uses, so a dated verification never ends up with two live reports of one
  press. The stamps are kept in an `updated` list inside the document block;
  `REPORT_SCHEMA` stays **7** and the key is written only when there is one.
* K.7 and K.7b are ONE writer, `_write_the_document`, which is his sentence
  *"The same function is used"*.
* K.7d took the creation stamp to the FRONT of the name rather than merely
  dropping the trailing one: his parenthesis was false of this build, where a
  document's name began with its report type, and dropping the stamp alone
  would have left reports of one measurement indistinguishable.
* K.8's one narrowing: a report written before the document record existed
  lists no measurements, so its two tick boxes follow K.5's inference and its
  MEASUREMENT ticks are left alone. Imposing an inferred list would narrow
  every project made before this beta to one sheet.

**⏳ TWO THINGS ARE OPEN AND ARE NOT BUILT.**

1. **A second Update: append or replace?** He said Update appends
   *" - updated `<date> <time>`"* and did not say what the next one does. The
   default taken is **replace**, so a name says when the report was created and
   when it was last updated and nothing else. Every stamp is kept on disk, so
   `measurement_report.NAME_SHOWS_EVERY_UPDATE` switches it with nothing to
   recover. **Awaiting his word.**
2. **Which report the window OPENS on** when the latest one records no document
   of its own. His comment says twice that the latest created report is
   selected whatever it records, but both sentences sit inside the held
   storage/naming ruling, and changing it would take R24-F1 with it. B8-492.

The popup's wording is **M-REPORT-UPDATE-OR-NEW**, in §M-PROPOSED of
`unified_measurement_management.md` and **not approved**: he wrote it and ended
*"(or similar)"*.

**NOT IN THIS SECTION, AND NOT BUILT:** which folder a report lives in, the
`report_profiling` / `report_verification` tags, what each run type offers in
"Report type", the run number at the front of a profiling run's entry, and
Delete moving a report to `reports/old/date_ReportId`. All of it is from the
same comment and all of it moves files a user already has.

## 14. The verdict ruling of 2026-09-21: COND retired, and the metric note

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Knut ruled on this in writing on #182 between 00:46 and 01:06 (CEST) on
2026-09-21, and revised himself twice inside those twenty minutes. What is
recorded here is the ruling as it stood at the end, not as it started; the
withdrawn version is written down as well, because it is the part most likely
to be rebuilt by mistake.

### 14.1 What he ruled

1. **The bracket stays in the table cells**, with one line of legend in the
   Report limits window saying what it means, *"alongside what –, ? and ✕
   mean"*.
2. **A reference number at the end of each metric's label**, pointing to a note
   below the table: *"there should be a note associated with the metric its
   self, like a reference number at the end of the metric label-name, pointing
   to a note below the table in the Report Limits window (and in the report
   text also a number on the metric name, pointing to a note in the report
   text)."*
3. **The note** says the standard calls the metric recommended rather than
   required, and that it may be applied optionally.
4. **COND is retired as a row word.** *"it might be better to standardise on
   all metrics being tested against a threshold shows as FAIL or PASS (always,
   also for the standards), and the COND term is retired, all tests that fail
   or pass are handled equally."* His reasoning, which is the part worth
   keeping: outside the ISO sets a recommended row is *"just another metric to
   include as a test"*, so a third word carries no information there and costs
   understanding everywhere.
5. **Every should-limit leaves ChromIQ's own set definitions.** He first asked
   for it of the Custom ISO 12647-7 row, *"the thresholds that use a bracket,
   ex. '(3,00)', should not have a bracket, since it is not a
   'recommended'/'should' type metric"*, and then agreed to the three ChromIQ
   sets as well: *"Remove them, so a bracket only ever appears where a standard
   is involved, and ChromIQ's own sets have requirements and nothing else."*

### 14.2 What he WITHDREW, and which must not be built

At 00:46 he asked that a failed recommendation still leave the overall result
PASS, and that the note say so. **At 00:55 he withdrew both**:

> *"I recommend that all thresholds tested against are treated the same, so
> there is no need to have special handling of the results of a metric with
> 'should' (recommended, not required). If the test is applied the report shall
> show the result as is, and the overall result follows as normal... So do not
> do this '...and does not affect the overall result of the ISO 12647
> verification.' and do not do this 'A failed recommendation must still leave
> the measurement's overall result PASS, provided every required metric
> passes.'"*

So **the aggregation does not change at all**. A failed recommendation sinks a
column exactly as any other failure does, and **the note may not say otherwise**:
a sentence excusing such a row from the Overall would be false of the code as
well as against the ruling that replaced it.

### 14.3 What this means in the table

| | before 2026-09-21 | after |
|---|---|---|
| a value over a **required** limit | FAIL | FAIL |
| a value over a **recommended** limit | COND | **FAIL**, plus a numbered note |
| a value within either | PASS | PASS |
| the column's **Overall** | unchanged | unchanged |
| rows marked "should" in ChromIQ's own sets | 7 | **0** |

The bracket, `Limit.is_should` and the `[number, "should"]` form in a values
file **all stay in the data**: they are what decides which rows carry a note.
Only the displayed word goes.

### 14.4 The consequence Knut was told about before it was built

After §14.1 point 5, **no bracket appears anywhere by default**, because a
licence holder's own values file and the two editable Custom columns are the
only remaining sources of a should-limit. A fully green test suite therefore
proves nothing about the note path, and the note was demonstrated to him on
screen through a hand-marked should-limit in a Custom column instead, which
touches no real standard value.

### 14.5 Reports saved before the ruling

A saved report carries the verdicts it was saved with, COND included, and
**they are not rewritten**: a saved verdict is the record §5 keeps comparable
across dates. Such a row is shown exactly as recorded, and the word is still
defined and still explained in the report's own guide, which now says it is an
Overall word, that rows do not use it, and what it meant on a row in a report
saved before ChromIQ 4.3.0. Generating the report again judges it by today's
rule.

### 13.9 "Show all measurement runs" is REMOVED, and the ticks decide (Knut, 2026-09-20)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, 2026-09-20, in his beta 29
review on issue #182. **Confirmed by:** *nobody yet.*

This section records a ruling and what was built from it. Nobody has confirmed
that what the app now does is what it should do.

**What he ruled, and why.** He began by correcting the record on what the box
meant:

> *"Note that the 'Show all...' check mark does not mean show all measurements
> existing in the 'included measurements in report' list. No... It means show
> all measurement runs that was ticked (selected) in the 'included measurements
> in report' list at the time the report was created/updated. So if a report
> was created with 5 out of 11 measurements ticked/selected, then selecting
> 'Show all measurement runs' will show all of those in the report. Thus, the
> checkbox should actually be named 'Show all measurements selected'. The help
> text for 'Show all measurement runs' describes that either ONE or ALL
> measurements are included depending on the state is OFF or ON. This
> description basically makes it impossible to show multiple measurement dates
> (neither one or all) and cannot be correct."*

…and then ruled the box out rather than renaming it:

> *"I realise now this checkbox is not a reasonable feature to have (and has
> evolved to something that it was not originally used) and should be removed,
> as any report created should show in the report the selected/ticked
> measurements a user chose. The feature that actually is desired here is a
> button 'Select All' that helps the user to tick all measurement dates in the
> 'included measurements in report' list, so the user does not need to manually
> click all of them, and a button 'Deselect All' that unticks all measurements
> in the 'included measurements in report' list. These to buttons should be
> placed to the right side of the 'included measurements in report' input
> selection box, since the 'included measurements in report' input box has too
> much available space compared to the width of its content. These tow buttons
> then ONLY select or clear the selection of the listed measurements to be
> included, and the user must manually select which measurement to include if
> he wants ONE or multiple measurements to be part of the report. Remove the
> feature 'Show all measurement runs' totally from the design, and any feature
> that belongs to that button. The conflicts described above, between 'Show all
> ...' checkbox and the selected measurements are then not relevant, and only
> the selected/ticked measurements shall be part of the report when
> created/updated (always)."*

| # | Rule |
|---|---|
| R.1 | **"Show all measurement runs" does not exist**, in the report window or in Preferences, and neither does anything built on it. |
| R.2 | **Select all** and **Deselect all** sit to the RIGHT of the included-measurements list. They tick and untick every measurement row and **change nothing else**. |
| R.3 | **A report covers exactly the measurements that are ticked. Always**, at creation and at update. |
| R.4 | The included-measurements list is **never disabled**, under any report type. |
| R.5 | A one-page **Colour summary** covers ONE measurement. With more than one ticked, Generate report **says so and stops**, moving no tick (M-REPORT-ONE-PAGE-ONE-DATE, §M-PROPOSED, **not approved**). |
| R.6 | **Selecting a report ticks the measurements that report was built from**, and nothing else, whether or not it records a document block. |

**What R.1 removed from this document.** These rules are superseded and are
recorded here rather than deleted, so a reader of §13.6 and §13.7 is not left
following a rule about a control that is gone:

* **P.3** (§13.6): the two Preferences tick boxes. One is left, "Show detailed
  data for each run, by default".
* **F.1** (§13.7): *"'Show all measurement runs' ON and every date included →
  'All dates'"*. The flag was already decided from what the document COVERS
  rather than from the box, so the wording changes and the behaviour does not:
  **every loaded measurement covered → "All dates"**.
* **F.4** (§13.7): the rule that a one-measurement list turns the box off
  automatically and greys it. There is no box to turn off. The naming half of
  F.4 stands: one measurement is still **"One date"**.
* **F.3's caveat** (§13.7): *"F.3's state cannot be reached from the window as
  it is built"*, because `_runs_for_report` returned the single loaded
  measurement when the box was off and never read the ticks. It is reachable
  now, and it is the ordinary case: tick some but not all and the flag is
  **"Multiple dates"**.
* **K.8** (§13.8): still stands, minus one of its five. **Four settings** are
  restored when a report is selected: the included-measurements ticks, Report
  type, Judged against, and "Show detailed data for each run".

**What R.3 fixed, which is the reason he wanted the box gone.** `_runs_for_report`
read the box FIRST and the list second. With the box ON it was the history
minus what was unticked; with it OFF it was the measurement the window was
opened on, **and the ticks were not consulted at all**. That second branch is
what he met from both directions:

> *"Selecting report type 'Grey and tone check' with 'Show all...' OFF and many
> measurements included (ticked), the generate report. This unselected all but
> the last measurement without a warning."*

> *"If I try this again, but now only with one measurement ticked, the
> measurement I had ticked was unticked and the last measurement in the list
> was automatically ticked (I did not ask for that). This is also wrong."*

Neither was a conflict rule misfiring. The ticks were never read.

**R.4 and the freeze.** The list was disabled under the one-page type, and a
second rule drew every row but one as unticked while the model kept them. He
met both at once:

> *"Now I tried selecting report type Colour summary. Then the 'included
> measurements in report' became unticked for all measurements and it froze, so
> I cannot scroll or select."*

They had not been unticked; they had been drawn that way. Both rules came from
B8-523, whose stated justification was that the list is disabled and so nothing
a user can press could disagree with the drawing. Removing the freeze removed
the justification. B8-590 and B8-591 carry what was measured.

**Still open, and NOT decided by this ruling.** He asked, in the same comment,
that Full Colour Check not be offered when the run type is Profiling. There is
no run-type gating of the report-type pulldown at all today, and §13.8 already
lists *"what each run type offers in 'Report type'"* as not built. Which types
each run type offers, and what a Profiling run's default becomes when the
current default is withdrawn from it, is his decision. B8-598. **He decided it
on 2026-09-22: see §13.10.**

### 13.10 Which report types each run type offers (Knut, 2026-09-22)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, #182 comment 5781159382,
against beta 34. **Confirmed by:** *nobody yet.* This records his ruling and
what was built from it (B8-778 K13); nobody has confirmed the built behaviour.

> *"The report type 'Printing record' is still available when run type is
> verification, but should not be available. And, when run type is Profiling,
> all report types are still available, but only 'Printing record' should be
> available. When run type is Profiling, and measurement reports are generated
> after a finished measurement, only the 'Printing record' type should be
> created, as this is the only report type relevant for when profiling. When
> run type is verification, the current default in preferences -> report is
> used (unless another default was chosen for the run). The help text for the
> report type needs to explain when which report types are available."*

What was built, and the assumptions it rests on (each is his to overturn):

* **The measurement decides, not the bar.** The report window has no run type
  of its own; it is opened on a measurement, so that measurement's kind is
  used: a run's own sheet is profiling, a dated verification is verification.
  The automatic report asks the same question the same way.
* **Profiling: Printing record only. Verification: every buildable type but
  the Printing record.** The others are shown greyed with a sentence saying
  why, as an unbuilt type is (§10), not hidden.
* **A measurement with no run** (a file outside any project, and a
  calibration) keeps every type, as before. *Assumption:* a calibration is not
  a profile run, so the rule is not applied to it. **Overturned for
  calibration by K26 (§18.1):** under Run type Calibration the window makes
  no report at all and opens empty.
* **Preferences "Report type, default" applies to every measurement that is
  not a profiling measurement** (verifications, calibrations and files outside
  a project), so the Printing record is greyed there, and a stored Printing
  record default (legal until beta 35) is read as Full colour check. Nothing
  on disk is rewritten.
* **A saved report of a type its kind no longer allows** (a Printing record
  of a verification saved by beta 34) is shown as recorded, and Update or
  Create New writes the type the kind allows; the question then says the
  settings were modified, because they will be. A saved report that records
  NO type follows its run (§10), so a profiling sheet's is labelled and drawn
  as a Printing record. *Assumption:* what a document IS is not changed by
  opening it.
* This amends §10 ("T2 ... is the default for every report written before this
  existed and every run nobody has chosen for") and §13.6 P.2 and P.6, which
  now hold for verification measurements only.

**K19 (Knut, #182 comment 5785414710, 2026-09-23), ⏳ awaiting confirmation,
Confirmed by: *nobody yet*.**

> *"It has been specified that the counting of reports when in run type
> verification shall only count reports that can exist as report types for a
> verification run. Also, when run type is profiling, then only reports that
> are of type 'Printing record' shall be counted. This also applies to the
> population of the contents in the Report shows pulldown"*

Built (B8-809): "Already generated for this run" and "Report shown" count and
list only the types the window's kind allows, from the folders that kind lives
in (a profiling sheet's reports in the run's folder, a verification's in its
dated folders). This **narrows the bullet above**: a saved report of a type its
kind no longer allows is no longer offered in the list at all (it stays on
disk, untouched), where it was shown as recorded. *Assumption:* "run type" here
is the window's measurement, as in the first bullet; adding a measurement of
the other kind makes it the window's subject (B8-803 is open on that).

### 13.11 Where a report lives, and which folders the list reads (K23, Knut 2026-09-23)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, #182 comments 5787117741
(the rule) and 5787380408 (accepting the proposal in 5787131342).
**Confirmed by:** *nobody yet.* This records his ruling and what was built
from it (B8-816); nobody has confirmed the built behaviour.

> *"For single measurements: ".../runN/verifications/<date_time>/reports/"
> For multiple measurements within same measurement set(within same profile
> run): ".../runN/verifications/reports/" For multiple measurements across
> different measurement sets of different profile runs:
> ".../printer_profile_project_name/reports/""*, and for a profiling run
> *"For single measurements: ".../runN/reports/""*, several runs in the
> project's `reports/`.

Accepted in 5787380408: each date keeps its own small verdict record in its
own folder, *"it is not a report, it is never listed or counted"*; reports
already on users' disks stay where they are and are shown and counted by what
they cover.

What was built:

* **Where.** `document_home` decides from what the report COVERS (its ticked
  measurements): one folder, that folder's `reports/`; several dates of one
  profile run, `runN/verifications/reports/`; anything across profile runs,
  `<project>/reports/`.
* **What is written.** A report of one measurement is one file in that
  measurement's folder, as before: it is the report and the date's verdict
  record at once. A report of several measurements is a **document file** in
  its home (its document block with `"role": "document"`, no measurement
  data) and, in each measurement folder the press may write into (the
  window's own run, as before), a **verdict record**: the same per-measurement
  report with `"role": "record"`. The lock, the trend, the recorded-verdict
  rows and recalculation read the records exactly as they read every report
  file before.
* **What is listed and counted.** "Report shown" and "Already generated for
  this run" read the reports folders of the measurements in "Included
  measurements" of the profile bar's Run type, plus the two shared folders,
  where a document is taken only when it covers one of those measurements
  (compared from `runs/` down, so a moved project still finds it). A verdict
  record is never an entry and never counted.
* **Which measurements.** Every measurement in "Included measurements",
  ticked or not. *ANSWERED by Knut in K25 (5789263863, Q1), see §13.12:* the
  assumption recorded here before (NOT the other runs' profiling sheets a
  Profiling window gathers by itself) was the opposite of his rule, and is
  withdrawn.
* **Update** decides the home again from the new ticks: the document file is
  rewritten in place, moved (the old one archived into its `reports/old/`
  first, D23) or retired when the report now covers one measurement, whose
  file then becomes the report; a measurement taken out keeps its file as a
  verdict record. All or nothing, as before.
* **Delete Selected Report** of a report with a document file moves that one
  file, into `verifications/old/<stamp>/` or `<project>/old/<stamp>/` (§13.2
  L.7); the verdict records stay in their dates.
* **Legacy.** Nothing is moved or rewritten by opening a project. A report of
  several dates written before this (one file per date, one id, no role) is
  listed and counted once, from the dates it covers. An Update of such a
  report writes it by this rule (its files archived first).
* **A report is shown whole (beta 37, challenge round A, F1).** A report
  selected in "Report shown", or the one the window opens on, that records
  measurements the window has not loaded, loads them into "Included
  measurements" before anything is drawn (found from `runs/` down, so a moved
  project finds them too; a folder no longer holding its measurement is left
  out). The page then shows every date the report covers, and because the
  window now holds measurements from more than one place, Generate report is
  greyed with the several-places reason, and the handler refuses as well:
  an Update can no longer rewrite a report narrower than it is. Before this, a
  report across run1 and run2 opened from run2 showed one date, Generate said
  "Nothing was changed", and Update rewrote it about that one date.

### 13.12 "Report shown" is grouped; the names stay (K25, Knut 2026-09-23)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, #182 comments 5789263863
(the K23 answers, Q1 to Q6) and 5789532633 (the correction: names stay, the
list is grouped). **Confirmed by:** *nobody yet.* This records his ruling and
what was built from it (B8-826); nobody has confirmed the built behaviour.

> *"For both run type verification and run type profiling the report names
> keep their names, but are grouped according to which measurement sets have
> been added, where they come from, and what a report includes."*

What was built:

* **Names.** Unchanged: "One date", "Multiple dates", "All dates" on every
  entry, profiling and verification alike. **Amended by K26 (§18.6):** on a
  Profiling window they are "Run1", "Run2", …, "Multiple runs", "All runs".
* **Whether the list is grouped** is decided by the measurements in "Included
  measurements" (the folders §13.11 reads, of the profile bar's Run type):

  **Amended by K26 (§18.10):** the reports the list OFFERS count as well, so
  one report covering two profile runs groups the list from the start.

  | the measurements come from | headings |
  |---|---|
  | one profile run | none, as before |
  | several runs of one project | `Run1`, `Run2`, ... |
  | several projects | the project name, with `Run1`, `Run2`, ... under it |

* **Where one report goes** is decided by what it COVERS: the folders its
  document records, and the folders of its files, compared by project and
  run folder NAME so a moved project groups the same. One run: under that
  run. Several runs of one project: under that project's "Reports including
  multiple runs". More than one project: under "Reports including multiple
  projects", last.
* **Order.** "New report…" first. Projects with the window's own first, the
  others by name; runs in number order; the multi-run group after the runs;
  newest first inside every group.
* **The headings** are the Create Chart preset pulldown's: a separator before
  each top-level heading, a bold row with no data whose item is disabled, so
  it can be read and not chosen. A run under a project is indented and has no
  separator of its own. A run heading's tooltip is its folder
  (`<project>/runs/run1`).
* **The label** reads "Report shown:" when the list is grouped, and "Report
  shown (runN):" when it is not.
* **Profiling (Q1).** "Already generated for this run" and "Report shown"
  count and list the Printing records of EVERY measurement in the list,
  which on a Profiling window includes every run's profiling sheet. The
  window still opens on the newest report of its OWN run; a run with none
  opens on "New report…" with its defaults, never on another run's report.
* **The trend (Q1).** Draws only the measurements a report includes (its
  ticks). The report made at the end of a measurement covers that one
  measurement, so the window opened on it ticks one row and the graphs show
  the existing "at least two measurements" text. This was already so and is
  now pinned by a test.
* **A report across projects** is filed where §13.11's `document_home` puts
  it, the projects' common folder (`<output folder>/reports/`). That folder is
  now read by the list and the counter; before, such a report was written and
  never listed or counted. Selecting it loads the other project's
  measurements it covers (§13.11, "a report is shown whole"), found in the
  project of that name beside this one, so a copied or moved pack loads its
  own copy.
* **M-REPORT-DELETE (Q5)** says "the measurement(s) it describes"
  (§M-PROPOSED, revised).
* **"Where are my files" (Q6)** has rows for the saved reports in
  `runs/runN/verifications/reports/` and the project's `reports/`.

Open with Knut (B8-826): whether "Reports including multiple runs" is the
right place for a report across runs of one project; whether a one-run list
should stay flat when a report across runs covers one of its measurements;
whether "Already generated for this run" should say "for these measurements"
now that it counts other runs; and whether a report across projects belongs
outside every project.


## 15. ChromIQ's own two repeatability rows (#182, 2026-09-22)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, 2026-09-22, on issue #182:
*"Do as you recommend and we can review the result implemented on a release."*
**Confirmed by:** *nobody yet.* This section records a design he approved and
what was built from it. Nobody has confirmed that what the app now does is what
it should do.

### 15.1 Why these two rows are different from every other row here

Every other numeric row in this table comes from a document somebody else
wrote. These two do not. They are computed from the user's own measurements of
the user's own prints, no standard defines them, nobody licenses them, and they
can be judged for a printer user who holds no document at all.

That shapes every decision about them:

* the group heading is **"Repeatability, measured by ChromIQ"**, the only
  heading in the table that names its own author, because a row here is read
  against the column it sits under and two of those columns are named after a
  standard;
* each row's help text says, in as many words, *"This row is ChromIQ's own. No
  standard defines it"*;
* both read `–` in the two read-only ISO columns. Those columns hold a
  standard's published values, and no standard published these.

`repeatability_de00_max` is a DIFFERENT row and is deliberately untouched. It
stays `unmeasurable` under "Not evaluated by ChromIQ": it is a standard's
criterion over that standard's own timed protocol, and repointing it at a
number ChromIQ can compute would be the false attribution this record already
describes being removed from this window more than once.

### 15.2 Row A, repeat patches within one sheet

`repeat_patches_de00_max`, ΔE00, status `build`. The largest ΔE00 between
patches of one measured sheet that ask for the SAME device colour.

* **The population.** Patches whose device values agree to two decimal places
  are one group; groups of one are not repeats of anything. The grouping is
  `ti3_analysis.device_repeat_groups`, shared with the Ti3 Info window's own
  duplicate figure, so the application holds one definition of a repeat patch.
  That window keeps its long-standing ΔEab statistic; this row is ΔE00 because
  it stands beside thirty other ΔE00 rows and is judged against a ΔE00 limit.
* **Judged** when the sheet carries at least **2** groups
  (`REPEAT_WITHIN_MIN_GROUPS`). One group is one colour, and where a chart
  repeats anything it repeats the two ends, so a one-group reading would stand
  for nothing else on the sheet. Of 101 measured sheets on this machine that
  carry repeats at all, none carries fewer than two.
* **Refused** with `no_repeat_patches` when the chart never asks for the same
  colour twice, and with `too_few_repeat_groups` when it asks twice for one
  colour only. Two codes, because the two send a reader to different places.
* **It needs no reference values and no second print**, which is the point of
  it: it is answerable where every reference row is not.

### 15.3 Row B, the same chart measured again

`repeat_measurement_de00_max`, ΔE00, status `build`. The largest ΔE00 between
this measurement and the one before it, patch for patch.

* **The population.** Each dated verification of a run is compared with the one
  **immediately before it**, never with the first of the series: repeatability
  is the scatter between repeats, and a worst-over-all-history would grow for
  ever and leave one bad day condemning every measurement after it.
* Patches are paired by `SAMPLE_ID`, as the rest of the report pairs them, and
  a pair is kept only when both files agree about the device values that patch
  was asked for, within `PATCH_IDENTITY_TOL`. A chart rebuilt between the two
  dates therefore drops out instead of being read as the printer moving.
* **Judged** from the second measurement onward, when at least **14** patches
  survive that test (`REPEAT_ACROSS_MIN_PATCHES`). Fourteen is
  `ceil(ln 0.5 / ln 0.95)`: the count at which the largest of what was read
  first has an even chance of having touched the worst twentieth of the chart,
  which is the same five per cent the best-95, worst-5 and 95th-percentile rows
  are already cut at.
* **Refused** with `no_earlier_measurement` before the second measurement, and
  with `too_few_shared_patches` when the two measurements turn out not to be of
  the same chart.

### 15.4 The limits, and what they were derived from

| set | Row A | Row B |
|---|---|---|
| ChromIQ default | 2.0 | 3.0 |
| ChromIQ tight | 1.0 | 1.5 |
| Quick check | 4.0 | 6.0 |
| Custom ISO 12647-7 / -8 | 2.0 | 3.0 |
| ISO 12647-7 / -8 (read-only) | `–` | `–` |

Nothing here was looked up in, derived from, or checked against any standard.
Every number is one ChromIQ default already uses, and the measurements each was
checked against are:

* **Row A.** Twenty-one sheets on this machine that a real instrument read and
  that carry repeat patches: within-sheet maxima from **0.32 to 1.999**, median
  **0.698**. The worst is the sheet with by far the most comparisons (1,168
  patches, 110 groups, 192 pairs) and on it 95 % of pairs are under 0.724, so
  that maximum is a single-patch defect rather than the sheet's repeatability.
* **Row B.** The demo pack's dated series, nine consecutive pairs: maxima
  **0.0 to 4.49**, median **1.75**. There is no genuine print-to-print
  repeatability series on this machine to check it against, and that is stated
  rather than papered over.

**Row B's limit may never be tighter than Row A's.** Row B's population
contains Row A's entirely and adds a second print and a second day.

**The demo pack's WITHIN-sheet numbers are not evidence for Row A.**
`scripts/make_demo_projects.py` synthesises each reading as the chart value
plus `drift` plus `random.uniform(-0.35, 0.35)`, and `drift` shifts every patch
of a sheet equally, so it cancels in a within-sheet difference. What is left is
the jitter generator reseeded per date. The dated series IS evidence for Row B,
where the drift between dates is real and intended.

### 15.5 The amendment to §3.3, which is the part that needs a ruling

`set_summary` demotes a column to COND when a REQUIRED row reads N-A, on the
reading that the set asked for something and did not get it. That is right for
every row the rule was written for: a chart either has a grey ramp or the user
can go and get one.

It is not right for these two. Row B is N-A on every FIRST measurement of a
chart, which is the ordinary state of most reports anybody has, so under the
unamended rule a user who measured a verification sheet once and passed every
accuracy limit would read **COND instead of PASS**, because ChromIQ cannot yet
say whether the printer repeats. Row A is the same shape: roughly half the
charts ChromIQ ships repeat a colour and half do not.

So `compliance_sets.POPULATION_MAY_BE_ABSENT` names exactly these two rows, and
`set_summary` leaves them out of the **completeness arithmetic only**. The row
is still shown, still reads N-A, and still carries its own reason sentence.
Nothing else about the summary changes.

**The question for Knut:** is *"a row whose population may honestly not exist
is not a gap in what was checked"* the right carve-out, and are these the right
two rows for it? No other row may join that set without the same argument being
made and confirmed.

---

### 15.6 ⏳ Awaiting confirmation: Knut ANSWERED, and his rule is broader

**Confirmed by:** *nobody yet.*

He was asked the question in §15.5 and answered it on 2026-09-21 by widening
it. His words:

> *"'Row B is N-A on every first measurement' should not influence the overall
> verdict, as Not Applicable must not be counted as a fail, so the overall
> verdict should show PASS, not COND, if all others pass. I say, a metric that
> is not applicable should not have verdict conditional because COND does not
> indicate which of the verdicts cause the COND. I would say that the N-A for
> the first measurement instead should have a super-script number, pointing to
> a note, where the note explains why it is N-A for the first measurement. When
> all other metrics PASS, that N-A is not applicable, thus not relevant for the
> verdict, thus overall verdict becomes PASS (or FAIL if some metric fails)."*

Two rules, and the first replaces §15.5 rather than amending it.

**R1. An N-A never demotes a column, whatever row it is on.** Not a carve-out
for two rows: a general rule about the word. `set_summary` no longer counts
required N-A rows at all, and there is no list of exempt rows for it to
consult. COND survives as an Overall word for a report saved before
2026-09-21, whose stored rows still carry it, and for nothing else: the
ISO-named column was the other way in until Knut retired that cap on
2026-09-22.

*What this changes beyond the two repeatability rows,* measured over one N-A
row per distinct cause an ordinary chart can produce: a required grey row on a
chart with no grey ramp, a required paper-white row on a chart with no white,
a required control-strip row on a chart that declares no strip, and both
repeatability rows. Every one of those used to read COND on an otherwise clean
column and now reads PASS. A recommended row reading N-A never demoted a
column and is unchanged.

**R2. An N-A cell carries a raised number pointing to a note saying why.** The
numbered-note mechanism already built for §12 is reused rather than a second
one written, so the marker on the cell and the item in the list come from one
numbering and cannot disagree about which note is note 1. The note's sentence
is the row's existing refusal reason, which already names what that row needs
(*"this is the first measurement of this chart, so there is nothing to compare
it with; the row is judged from the second measurement onward"*), so no new
wording was invented for it.

`judge` had deliberately given an N-A row no notes, on the reading that *"a
note beside an N-A would be a footnote on an absence, which is what `reason`
is already for"*. R2 overrules that reading. Where two measurements in one
report give one reason code two different sentences (several reasons count
something, such as how many patches a control strip declares), they take two
numbers rather than sharing one and printing one run's count beside both.

**What `POPULATION_MAY_BE_ABSENT` still does.** The set is not deleted, and it
no longer touches any verdict. What is left is a question R1 does not answer:
two MESSAGES promise something about the **chart** (*"add those patches to the
chart in Create Chart"*, and the note formerly headed *"Not computed on this
chart"*), and nothing can be added to a chart to answer whether it has been
measured twice. The set decides which rows may appear under such a promise. If
that is the wrong place for it, say so; it governs wording, not verdicts.

**One thing R1 does NOT make true.** The unqualified PASS sentence, *"Every
value this limit set requires was checked and is within its limit"*, is still
false whenever a required row reads N-A: the verdict is now rightly PASS, but
the sentence is a claim about what was **checked**, and a value that could not
be worked out was not checked. So a column reaching PASS with anything left
over says the count instead:

> *"{checked} of {total} values checked, all within this limit set's limits.
> The other {not_computed} could not be worked out from this measurement, and
> a value that could not be worked out is not counted as a failure."*

with a singular form for one. **This wording is proposed, not settled.** It
matters most on report type T1, the one-page colour summary, which carries no
row table and no notes, so that sentence is the only thing on the page that
can say a row was left unanswered.

**These specifications are binding.**

---

## 16. Evenness across the sheet, nine locations (#182, 2026-09-22)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, 2026-09-22, on issue #182
(comment 5785774676), answering the F1 analysis
(`~/Desktop/ChromIQ-beta36-proof/F1-evenness/REPORT.md`) and Basti's reply
5785894881. **Confirmed by:** *nobody yet.* This section records the method he
ruled and what was built from it (B8-814). Nobody has confirmed that what the
app now does is what it should do, and eight questions below are his.

### 16.1 The method

For one measured sheet:

1. **Every patch against its own expected colour.** The residual is the
   measured Lab minus the aim Lab the ΔE00 rows already use, in the same
   yardstick (absolute, or media-relative where the report normalises) and
   with the same patches left out (the eight declared cube corners of a FROM
   PROFILE GAMUT chart). Where the report separates colours the profile could
   never print, only the within-gamut patches count, as they do for the words.
   Nothing is matched by grey or by brightness (Knut, Q1: *"yes, do it"*).
2. **Positions come from the chart's `.ti2`**, by `SAMPLE_ID`: `SAMPLE_LOC`
   (strip label + patch number), `PASSES_IN_STRIPS2` (strips per page),
   `STEPS_IN_PASS` (rows). A chartread `.ti3` carries no `SAMPLE_LOC`. A patch
   whose device values in the measurement disagree with the chart's by more
   than `PATCH_IDENTITY_TOL` is left out and counted.
3. **Nine areas.** Each page with at least 9 strips and 9 rows
   (`measurement_report.EVENNESS_MIN_GRID`, one constant) is divided into three
   bands of strips and three bands of rows, whole strips and rows only, the
   remainder in the MIDDLE band (10 = 3 + 4 + 3). The same ninth of every such
   page is pooled (5745765820 items 1 and 4).
4. **Two numbers.** Each area's colour is a neutral L\* 50 plus its mean
   residual, the construction behind every number Knut was shown (0.81 and
   0.45 on the real sheet, noise 0.27 and 0.16):
   * `uniformity_sd`, **"Evenness across the sheet, nine locations"**: the
     largest ΔE00 between any two of the nine areas;
   * `uniformity_de00_max_from_mean`, **"… largest difference from the
     mean"**: the largest ΔE00 between an area and the plain mean of the nine
     area colours (each area counts once).
5. **The noise guard** (Q2: *"Your suggestion is good. Do not use the stricter
   version."*). The same arithmetic runs on the same patches with their areas
   shuffled, 500 times from a fixed seed (`EVENNESS_SHUFFLES`,
   `EVENNESS_SEED`), so a report is reproducible to the digit. The 95th
   percentile (nearest rank) of each number over the shuffles is that row's
   noise. **A row gives no verdict (N-A) when its noise is not below its
   limit**, and the note names the noise and the fewest patches in an area.
   The comparison needs the limit, so it is made in `judge`
   (`evenness_withheld`); the presets window and the pre-flight ask the same
   function. A sheet that is not graded (a profiling sheet, a raw drift check)
   shows its number as INFO whatever the noise.
6. **Where.** The block keeps, per area, its patch count, mean ΔL\*, Δa\*,
   Δb\* and its ΔE00 from the mean, and the worst pair and worst area. The
   report names an area by the labels printed on the sheet ("strips P to AF,
   rows 15 to 20"; several pages: "strips A to D and M to P"), never "top
   left", because which way up a strip runs depends on the instrument.

### 16.2 The rows, the limits, the heading

The two ids are **kept** (`outer_gamut_226` is the precedent): a run's stored
limits, a saved verdict and a licence holder's values file key on them. They
leave "Not evaluated by ChromIQ" for a group of their own, **"Evenness across
the sheet"**, status `build`, unit ΔE00. The first label drops "(spread of L\*,
a\*, b\*)", which was the standards' statistic and is not the one computed.

| set | nine locations | from the mean |
|---|---|---|
| ChromIQ default | 1.5 | 1.0 |
| ChromIQ tight | 1.5 | 1.0 |
| Quick check | 1.5 | 1.0 |
| Custom ISO 12647-7 / -8 | 1.5 | 1.0 |
| ISO 12647-7 / -8 (read-only) | `?` | `?` |

1.5 is Knut's (Q4: *"keep 1.5 for pairwise row"*). 1.0 is Basti's proposal
that Knut leaned towards (*"largest diff 1.0 I think may be ok … I am not
sure though"*) and is **awaiting his confirmation**. The reason the two differ:
with nine areas, 1.125 D ≤ P ≤ 2 D, so a blotch trips the from-the-mean row
first and a gradient trips the pairwise row first; both at 1.5 would make the
second row never say anything the first had not.

### 16.3 Notes on the results (Knut, Q5)

* Every PASS or FAIL on either row carries a numbered note on likely causes:
  the printer (banding, a partly blocked or misaligned head), the paper (not
  flat, not the same all over), and on a strip instrument the instrument
  drifting during the reading, which shows across the strips because the
  strips are read in order. No ChromIQ how-to (K18).
* Each such verdict also carries a note naming the area furthest from the
  mean, the two areas furthest apart, and the sheet's noise.
* The one-page summary, which has no notes list, carries one short paragraph
  when an evenness row was judged: the words, the area furthest from the
  mean, and the causes.
* An N-A carries its reason as a note, written to Knut's rule of 2026-09-23:
  what the MEASURED CHART lacks, never what to add or where.

| reason | the note says |
|---|---|
| `evenness_no_layout` | no chart file beside the measurement records where each patch was printed |
| `evenness_no_positions` | the chart's layout does not say which strip and row each patch is in |
| `evenness_grid_too_small` | the measured chart has S strips and R rows on its largest page; at least 9 of each are needed |
| `evenness_empty_area` | one of the nine areas holds no patch with an aim value |
| `evenness_noisy_pairwise` / `_from_mean` | the measured sheet is too noisy to judge the row: its own noise figure, and the row's limit it is not below. No patch count (beta 37, see below) |

The report window's strip ("these rows read N-A … add patches to the chart")
leaves out the two FILE reasons, which no patch can answer.

**⏳ Awaiting confirmation (beta 37, challenge rounds A F3 and B H2/M7).**
**Confirmed by:** *nobody yet.* The noise note used to say "the measured
chart has 42 patches in the emptiest ninth of the page, too few for this
row" on the evenness demo's noisy date, while the notes beside it judged the
same chart's 42-patch areas on its three other dates: on a measured sheet it
is the sheet's readings that scatter. The note now names the noise and the
limit and no patch count, and the strip leaves the two noise reasons out as
well, since nothing added to the chart answers them. When every row the strip
lists is an evenness row, its closing sentence is M-REPORT-CHART-MISMATCH-
LAYOUT (strips and rows on one page) instead of the general one that names
the grey ramp. The pre-print windows (presets, pre-flight) keep their own
estimate, which is about patch counts, because before printing there is no
measured noise.

### 16.4 Everywhere metrics are judged (Knut, Q5)

* **The Measurement Report**, every type that includes the rows: T1 and T2
  judge them; T3 (grey and tone) is about other rows; T4 judges nothing.
* **"Which presets can be used for verification?"** and **the Measure tab's
  pre-flight** ask the report's own arithmetic. The page grid is exact for a
  laid-out chart (the pre-flight's chart, the window's first line, the
  prebuilt bundles that ship a `.ti2`) and for a built-in ENGINE preset, whose
  grid the layout engine's own arithmetic predicts without writing a file
  (held to a real build by a test). A printtarg preset has no grid until
  printtarg runs and says so (`evenness_laid_out_later`). The noise cannot be
  known before printing, so these two windows use an **estimate for a typical
  print**: a residual of 1.1 per L\*, a\*, b\* component, calibrated so the
  estimate reproduces the F1 real sheet's noise (1.41 at 30 patches per area),
  and say it is an estimate. The pre-flight, which knows no set yet, asks
  against the loosest limit any set puts on the row.
* **The star is not decided by these rows** (question E4 below).

### 16.5 Questions for Knut

* **E1. A short last page.** "At least 9 columns and 9 rows per page": built
  as "a page under 9 by 9 is left out and the chart is judged on the rest",
  and the report names the pages left out. Or should such a page refuse the
  whole chart?
* **E2. The 75 % page coverage requirement** (5744704621 requirement 2,
  answered in 5745765820 item 3) is not in the rulings of 2026-09-22 and is
  not built. A `.ti2` records the paper size but not where the patch block
  sits. Is it still wanted?
* **E3. Tight and quick. ANSWERED by Knut, 2026-09-23 (5789263863): "Yes",
  all three ChromIQ sets carry 1.5 / 1.0, built.** It was built as half and
  double of default (0.75 / 0.5 and 3.0 / 2.0), the rule every other row
  follows. At 0.75 the noise must be
  under 0.75 too, which takes about four times the patches, so most charts
  read N-A on tight. Or should all three ChromIQ sets carry 1.5 / 1.0?
* **E4. The star.** At 1.5 the rows want about 30 patches in every ninth of
  the page, roughly 270 on one page; the one-page verification presets the
  star marks are 77 to 204. The rows are therefore shown as missing in the
  presets window but do not take the star away. Should they?
* **E5. The Custom columns.** Both start from ChromIQ's own 1.5 / 1.0. Your
  own values file may carry researched figures for these rows; ChromIQ does
  not read it here. Do you want those as the Custom starting numbers?
* **E6. The ISO structure.** Both rows stay in the two ISO columns' structure
  (the standards do limit evenness), so those cells read `?`. A licence
  holder's figure for the first row was written for a spread statistic, not
  for the pairwise ΔE00 now computed. Keep the rows in the ISO structure?
* **E7. CONFIRMED by Knut, 2026-09-23: 1.0 on the from-the-mean row.**
  **E7. The 1.0** on the from-the-mean row (16.2).
* **E8. The yardstick.** Evenness uses the same yardstick as the other rows,
  so a sheet printed through its profile with a white-mapping intent is read
  media-relative: every reading is divided by the sheet's lightest patch.
  Driven on the demo project: when the paper-white patch happened to sit in
  the one area printed lighter, the whole sheet shifted by a colour-dependent
  amount, the noise rose from 0.3 to 3.7 and both rows read N-A. Should
  evenness always be judged in absolute Lab, whatever the other rows use?

### 16.6 Beta 38: page coverage (E2), the i1Pro 3 Plus case (E4), the yardstick research (E8)

**⏳ AWAITING CONFIRMATION.** **Ruled by:** Knut, 2026-09-23 (5789263863 E2,
E4, E8; E2 approved at 75 % in 5789539407). **Confirmed by:** *nobody yet.*
Registered as B8-828 (E2), B8-829 (E4) and B8-830 (E8). Proof:
`~/Desktop/ChromIQ-beta38-proof/evenness-followups/`.

**E2, built.** A page counts for evenness only when it has at least 9 strips
and 9 rows AND its patch block covers at least
`measurement_report.EVENNESS_MIN_PAGE_COVERAGE` (0.75, one constant) of the
paper:

    coverage = (paper width - left - right) x (paper height - top - bottom)
               / (paper width x paper height)

with left, right, top and bottom the distances from each paper edge to the
first patch, which is what Create Chart's "Measured from Preview" shows.
`workflow/page_coverage.py` reads them from the files beside the chart, in the
panel's own order: the engine geometry in `<stem>.channels.json`
(`margin_inspector.measure_from_engine`), else the page TIFF
(`measure_margins`), else the derived patch rectangles a prebuilt bundle keeps.
A dated verification's `chart/` snapshot holds no page images, so it borrows
the live chart's while the live `.ti2` is byte for byte the snapshot's. The
presets window predicts a built-in engine preset's coverage from the layout
engine's own geometry, widened the way the panel widens a built chart.

| case | result |
|---|---|
| no page reaches 9 by 9 | `evenness_grid_too_small`, as before (asked first) |
| pages of 9 by 9 exist, none covers 75 % | `evenness_page_coverage_too_small`: *"the patches on page N of the measured chart cover X % of the page; at least 75 % is needed"* (several pages: *"pages 1, 2 … cover at most X % of their page"*). X is rounded DOWN to one decimal |
| no file says where the patches sit | `evenness_no_page_geometry`: *"no file of the measured chart records where its patches sit on the page, so how much of the page they cover is not known"*. A file reason: left off the strip |
| some pages pass, some do not | the others are judged; the notes name each page left out and why |

The presets window and the pre-flight read the same arithmetic, with the
lines *"On no page of this chart with at least 9 strips and 9 rows do the
patches cover at least 75 % of the page."* and *"This chart's files do not
record where its patches sit on the page, …"*. Neither takes the star (a
layout shortfall). M-REPORT-CHART-MISMATCH-LAYOUT now ends "…and with patches
that cover most of the page" (PROPOSED). The help text quotes the 75 %.

**What it does to the built-ins, measured (engine presets, 172):** 123 fail
the 75 % floor, 12 fail the grid first, 37 pass. Knut's own 572-patch i1Pro A4 chart
covers **68.4 %** (margins 26.0 / 6.0 / 38.2 / 19.1 mm: the 26 mm clip
border, 38 mm top and 19 mm bottom, which together leave the jig's 240 mm
strip, cap an A4 portrait i1Pro page at 70.8 % even with no right margin). The
evenness demo's judged run is therefore now his 837-patch "no clip border"
chart (80.1 %), and the 572 chart is run 4, which reads N-A.

**E4, checked.** The 24 i1Pro 3 Plus presets are 11 strips by **14** rows (A4),
11 by **13** (Letter), 16 by 21 (A3) and 7 by 12 (the two 84-patch charts), not
11 by 15. By the 9 by 9 floor and the noise rule alone, Knut's expectation
holds: the one-page A4 and Letter charts are too noisy on a typical print
(estimated 2.0 / 1.2 against 1.5 / 1.0), every chart of two pages or more can
be judged, and so can the one-page A3. **With E2 at 75 %, none can:** the
family's own margins (28 mm clip band, 40 top, 20 bottom, 10 right) leave
65.3 % of an A4 page, 64.6 % of a Letter page and 74.7 % of an A3 page.
`tests/test_beta38_i1pro3plus_evenness.py` pins both answers.

**E8, researched, NOT changed.** The published uniformity tests (ISO 12647-7
§4.3.3, ISO 12647-8 §4.2.2.1, Idealliance) compare absolute CIELAB readings of
the same patch at different places on one sheet; none normalises to paper
white. The recommendation (judge evenness in absolute Lab whatever the other
rows use) waits for Knut. Findings:
`~/Desktop/ChromIQ-beta38-proof/evenness-followups/E8-research.md`.

**Questions for Knut (beta 38):**

* **E2/E4-a.** At 75 % no i1Pro 3 Plus preset and no i1Pro A4 preset with a
  clip border can ever be judged on evenness, the A3 i1Pro 3 Plus charts by 0.3
  of a point. Keep 75 %, lower it (70 % admits the A3 family; 64 % admits A4
  and Letter), or measure the block against the area inside the instrument's
  own minimum margins instead of the whole paper?
* **E4-b.** "11 columns by 15 rows per strip": the shipped presets are 11 by 14
  (A4) and 11 by 13 (Letter). Is that the chart you meant?
* **E8.** Judge evenness in absolute Lab always?

## 17. Trend graphs for the judged metrics (#182 K20/K21, 2026-09-23)

### ⏳ AWAITING CONFIRMATION

**Confirmed by:** *nobody yet.*

What Knut asked for: 5785414710 (the graph question and the limit lines),
answered by the proposal 5785894881 and his rulings 5787117741 ("graph
question", "Limit lines") and 5787380408 (Paper white). What was built, as
driven on screen on the demo packs:

1. **The four tabs that existed stay as they were**: Colour accuracy (ΔE00)
   with its dotted Avg and Max lines, Paper white (L*), Darkest black (L*)
   and Cube corners. They show whenever a report is loaded. Darkest black
   has no limit line, because no row judges it.
2. **Six new tabs, one per group of related metrics, at most two metrics
   each, each metric with its own dotted limit line:**

   | tab | metrics (rows), line word | unit |
   |---|---|---|
   | Paper white, diff | Paper white, difference from the reference paper, "Max" | ΔE00 |
   | Grey balance (ΔCh) | grey ramp average "Avg", largest "Max" | ΔCh |
   | Tone (ΔL*) | single-colour ramps 30 % to 70 %, "Max" | ΔL* |
   | Control strip (ΔE00) | average "Avg", 95th percentile "P95" | ΔE00 |
   | Repeatability (ΔE00) | repeat patches on one sheet "Sheet", the same chart measured again "Again" | ΔE00 |
   | Evenness (ΔE00) | nine locations "Pairs", largest difference from the mean "Mean" | ΔE00 |

   "Paper white, diff" sits beside "Paper white (L*)"; the other five follow
   "Cube corners" in the order Knut accepted them. The control strip plots
   its average and its 95th percentile, not its largest: the 95th percentile
   is the same kind of number as the largest without jumping on one misread
   patch, which would stretch the axis and flatten the trend.
3. **A new tab is shown, and printed in the PDF, only when at least one of
   its rows was judged for the report**: some measurement the document
   covers has a PASS, FAIL or COND on it. A row that is N-A, INFO or has no
   limit in the set does not count, and a raw drift check is never judged.
   Within a shown tab only the judged rows are plotted, so every plotted
   line has its limit line. The legend names each metric exactly as the
   results table does.
4. **A limit line sits at the limit the report was judged against**: the
   number printed beside the verdict in the results table (a saved report's
   recorded set, or the run's set when it is judged live). The graphs are
   redrawn together with the page, so after a change of "Judged against"
   they follow it when the report is generated, like everything else on
   the page. In the PDF they are drawn from the settings the document was
   built with.
5. **A line outside the plotted range is not in view.** The y-axis is scaled
   from the measured values alone; it is never widened to bring a line into
   view. The line appears once a measurement comes close enough to it.
6. Each new line is dotted, in its metric's colour; its word sits in the
   left margin beside the axis numbers, or at the line's left end when it
   would collide with a number or with the other line (the Avg / Max rule).
7. An evenness value the results table withholds because the sheet's own
   noise is not below the limit is not plotted against that limit.
8. The axes, the date labels and the note shown while fewer than two
   measurements have a value are the same as on the other tabs.
9. **The PDF**: Colour accuracy is printed twice as tall as before, so a
   small change between dates stays visible; the other graphs keep their
   height. Each graph is kept together with its title, and graphs that do
   not fit move to the next page.
10. **A metric with a single value is drawn as a point** (beta 37, challenge
    round B, H6), a larger marker since there is no line to see it on, in
    the window and the PDF. "The same chart measured again" has nothing to
    compare on a chart's first date, so on three dates it can have one value;
    that value was in the table and missing from the graph.

### 17.1 Every graph explains itself (#182 K25, 2026-09-23)

#### ⏳ AWAITING CONFIRMATION

**Confirmed by:** *nobody yet.*

What Knut asked for: 5789263863, the graph section (answers 2 and 5),
acknowledged in 5789282445. What was built, as driven on screen on the demo
packs (`~/Desktop/ChromIQ-beta38-proof/graphs/REPORT.md`):

11. **The limit words follow the Colour accuracy rule on every graph.** One
    piece of code places every graph's words, so the rule of item 6 is the
    same everywhere: in the left margin beside the axis numbers while they
    fit; inside the plot, the upper line's word above its line and the lower
    one's below, when a word would land within 9 px of an axis number or
    within 11 px of the other word. New: a word placed inside the plot also
    keeps clear of the graph's own lines, points and red x. Where the left
    end of its line is crossed by a data line it moves along its own line to
    the first clear place; where there is none it stays at the left end. A
    word is never left out. **Withdrawn by K26 (§18.9):** a word stays at the
    left end of its line even over a data line; nothing slides.
12. **Every limit word has a description.** Pointing at the word on screen
    shows it as a tooltip; the PDF prints the same text under the graph, one
    line per limit line, marked with a short dotted stroke in the line's
    colour. The text is the word, the limit with its unit, and what it is the
    limit for, for example *"Pairs (1.5 ΔE00): the limit for the largest
    difference between any two of the nine areas of the sheet."* A line the
    plotted range does not reach has no word on the graph to point at; the
    PDF still lists it, followed by *"Outside the range of values shown."*
13. **Two lines above each graph in the PDF**, under its title: what the
    graph is and what it shows, written for whoever the PDF is handed to (no
    ChromIQ instructions, no history). Each is at most two lines at the
    picture's width, in English and in German.
14. **Units on the data labels.** Every legend entry carries its unit, as
    Colour accuracy's "Average ΔE, all patches" already did: the judged rows
    as "<row label> (ΔE00)", "(ΔCh)" or "(ΔL*)", Cube corners as "White
    (ΔE00)" and so on. Paper white and Darkest black already said L*.
15. **A withheld date is a small red x.** A date whose value exists but was
    not judged (today: evenness, when the sheet's own noise is not below the
    limit) stays on the date axis and is drawn as a red x on that metric:
    * at the neighbouring date's value when only one of the two dates beside
      it has a point for that metric;
    * at the mean of the two when both have;
    * just above the x-axis when neither has (no date beside it, or the date
      beside it is withheld too). When a date beside it gets a point, the x
      moves up by the same rule.

    The neighbours are the dates immediately beside it on the axis
    (**amended by K26, §18.9:** the NEAREST dates that have a value). Pointing
    at the x shows *"<date>, <metric>: not judged, because <the same sentence
    as the results table's N-A>."*; the PDF prints the same text under the
    graph, after the line descriptions, marked with a red ×.
16. **Unchanged:** the tab scroll arrows; and a report of one measurement
    still shows "A trend graph needs at least two measurement runs…" in its
    graphs, with no red x.

## 18. K26: Knut's rulings on the beta 37 and K25 questions (#182, 2026-09-23)

### ⏳ AWAITING CONFIRMATION

**Ruled by:** Knut, #182 comments 5792484060 (the answers) and 5792576954
(group "Report shown" from the start); our reply 5792508391.
**Confirmed by:** *nobody yet.* This records his rulings and what was built
from them (B8-832), driven on screen (`~/Desktop/ChromIQ-beta38-proof/k26/`).
Nobody has confirmed the built behaviour.

**18.1 Run type Calibration makes no report.** *"Run type= Calibration should
not allow any reports, and the measurement report window should have
disabled/locked selection fields ... The measurement report window should not
load any text or reports and open as empty."*

* The window asks the profile bar (the window's parents, as §13.12 reads the
  Run type). Under Calibration it loads nothing, whatever measurement the
  door hands it: the Tools menu and every "Open measurement report" button of
  the Measure tab reach the same constructor. The report view is blank, the
  graphs are hidden, and every selection field and report button is disabled:
  "Report shown", Add / Remove / Clear, the measurement list, Select all /
  Deselect all, Report type, Judged against, Show limits…, Unlock, "Show
  detailed data for each run", Generate report, Delete Selected Report, Save
  report as PDF…, Reveal folder. Close and the help icons stay live.
  The Measure tab's own report button, which asked for a measurement first
  ("Measure this chart first"), opens this window under Calibration.
* In place of "Already generated…" a red line reads *"Measurement reports can
  only be made with Run type Profiling or Verification"*; its tooltip says
  what to change (§M-PROPOSED, M-REPORT-NOT-FOR-CALIBRATION).
* A window with no profile bar behind it cannot know the Run type and behaves
  as before.
* The Report type help no longer says a calibration can have any type.
* **Not changed, and asked (B8-832):** the report the Measure tab writes by
  itself after a calibration measurement.

**18.2 "Bound, and locked" left the report.** *"Remove it from the report, and
make sure this information is in the relevant help text."* The paragraph is
gone from "How to read this report". The same two sentences are in the "Judged
against" help; the help card's glossary already had "Bound" and "Locked", and
its "Locked" entry no longer says an unlock recalculates the saved reports
(nothing is recalculated since B8-391).

**18.3 The Printing record keeps "Judged against".** *"keep the judged against
row, which defines the thresholds shown."* Nothing changed.

**18.4 The Colour accuracy graph plots the judged figures.** *"Yes, use the
within-gamut figures."* Each date plots what its verdict judged
(`graded_de00`): the within-gamut figures where the sheet's colours were split
by the profile's gamut, all patches where they were not. With a within-gamut
date on the axis the two "all patches" legend entries read "all judged
patches", and the PDF description says the figures are within the profile's
gamut where the sheet was split by it. The Avg / Max lines are unchanged.

**18.5 A project whose folder is not named what its files carry** (a Finder
duplicate, "X copy"). *"the user should be given the option, with a popup
window, to rename the project. This interface and function should already
exist and just has to be modified a tiny bit to allow this case."*

* When a project is opened and its `project.json` name is not its folder's
  name, the existing rename chooser comes up before anything of the project is
  shown, with its heading and introduction from M-PROJECT-FOLDER-RENAMED
  (§M-PROPOSED) and two choices: **Rename the project to "<name>"** and
  **Leave it as it is**. <name> is what the "Printer profile project name"
  field shows.
* Rename renames every ChromIQ file carrying the old name, and the manifest,
  in place; a folder whose name ChromIQ would not give a project (a space, as
  in "X copy") becomes "X-copy" as every rename does. A failure is reported
  (M-PROJECT-FOLDER-RENAME-FAILED) and nothing else runs.
* A project with a built profile is offered the same rename; the option says
  the profile keeps the name written inside it. *Assumption:* the ordinary
  rename refuses a built profile, but refusing here leaves the copy unable to
  find any of its files (asked, B8-832).

**18.6 Profiling names.** *"When run type is set to Profiling: The name tags
become Run1, Run2, ..., then Multiple runs and All runs"*. On a Profiling
window a report of one measurement is named after the run it covers, one of
several but not all is "Multiple runs", all of them "All runs". Verification
keeps "One date", "Multiple dates", "All dates". The grouping of §13.12 stays.

**18.7 "for these measurements".** On a Profiling window the line under
"Report shown" reads "Already generated for these measurements: …" (and "No
report has been generated for these measurements yet."). Verification keeps
"for this run".

**18.8 `<output folder>/reports/`** is created only by the first report across
projects. Opening, listing, counting and loading create nothing there, which
a test pins. Driven: while the window holds measurements of two projects,
Generate report is greyed ("Measurements from more than one place are
loaded"), so the window itself writes no report across projects today.
*Found, not changed (another change set owns it):* "Save report
as PDF…" creates the report's folder before its file chooser opens, so a
cancelled PDF of a page across projects leaves `<output folder>/reports/`
behind, empty.

**18.9 The red x and the limit words.**

* A red x takes the NEAREST date on each side that has a value: at that value
  when one side has one, at the mean when both do, just above the x-axis when
  neither does (§17.1 item 15, amended).
* Two red crosses on one date whose places would overlap sit one above the
  other, one tooltip box apart (13 px), the later metric above; below instead
  when above would leave the plot.
* A limit word placed inside the plot stays at the left end of its line even
  over a data line, as on Colour accuracy before beta 38 (§17.1 item 11,
  amended). The tooltips and the PDF descriptions stay.

**18.10 "Report shown" is grouped from the start** (5792576954: *"'Report
shown' should be grouped from the start, because one of the reports it offers
covers two profile runs."*). Whether the list has headings is decided by the
measurements in "Included measurements in report" AND by what the reports it
offers cover: one report covering two profile runs groups it before that
report is selected.

**18.11 The evenness demo** (*"Fix it."*): on a synthetic sheet no patch that is
not the paper reads lighter than the lightest paper patch, so the noisy date's
paper white is the paper (`scripts/make_evenness_demo.py`).
