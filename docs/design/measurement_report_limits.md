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
is reported and approved before it is fixed. Here every section is still
awaiting confirmation, so the binding part today is the *record* of what was
built and why, not a confirmed behaviour.

Related documents: `unified_measurement_management.md` (the life of a
measurement; §M-PROPOSED holds this feature's two messages),
`verification_printing_and_target.md` (how a verification sheet is printed and
which reference the report uses), `tool_availability.md` (DRAFT; the report is
● for a selection that has a measurement).

The sources this design was built from are named in the research folder's
`CS-METRICS-SPEC.md`: the free official previews of ISO 12647-7:2016 and
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
Custom ISO 12647-7 · Custom ISO 12647-8 (each Custom set starts from its
parent's values).

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
the row, or the sheet is not graded; N-A when the chart or the reference
cannot supply the row, with the reason beside it.

A sheet is **graded** only when it is a verification measurement with a
reference that is not a raw drift check. A profiling measurement (the run's
own chart, printed raw) is never graded: every row INFO. This changes 4.2.0,
where a profiling sheet printed FAIL against the chart's design.

Per column (Overall): N-A when the set has no limit-bearing row; INFO when the
sheet is not graded; FAIL when any row fails; COND for every ISO column (its
values are applied to a chart that is not the standard's chart, footnote ¹);
COND when any row is COND or a required row is N-A; PASS otherwise. The
Overall cell carries its reason as text. The report never prints the word
"conforms" and never puts a standard's name in a verdict sentence.

## 5. Where the set lives, and when it may change

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

* Preferences → Reports holds the **defaults**: the editable sets' overrides,
  the "Default for new runs" marker, and the checkbox "Allow editing of
  thresholds after the first verification measurement" (off).
* A profile run is **bound** at its first verification measurement, before and
  independent of the autosave setting: the default set's effective limits are
  copied into `runs/runN/meta.json` (`compliance_*` fields). Every dated
  verification of that run is judged with that copy (Knut D9/D20). A later
  change to the set in Preferences does not reach a bound run.
* The run's limits are **locked** once a verification has been measured. The
  report window's "Unlock this run's limits" may be ticked only when the
  Preferences checkbox allows it, after a confirmation naming the run and the
  number of dated verifications. Unlocking archives every dated report once
  (`reports/old/<timestamp>/`, a copy) and recalculates every dated report of
  that run once, rewriting each file in place (Knut D23; nothing is deleted).
  Changing the set or the run's numbers afterwards recalculates once more.
* A run whose set id a later ChromIQ no longer knows keeps its values and
  verdicts and shows the set as "(historical)" (Knut D23).
* A measurement that is not in a run (an imported file in Downloads) is judged
  with the default set for the session; nothing is written anywhere.
* Column visibility in the Report limits window is remembered per profile run
  when opened from the report window, and in Preferences when opened there
  (Knut K-b).

## 6. What a saved report carries

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
reader (S-3); report types (D28); the tone-ramp generator, the approved-chart
list and the uniformity form (N5). The ISO numbers (S-2).
