# Measurement Report limit sets — Design Record (#182)

> **Status:** design record for issue #182, written 2026-09-08 from the rulings
> in that issue (Knut, 2026-09-04 to 2026-09-07) and built into
> `v4.2.1-beta.1`. A section is promoted to confirmed only when Knut or
> Sebastian says on the issue that what the app does is what it should do
> (CLAUDE.md, "only CONFIRMED behaviour may be written into a
> specification"). On 2026-09-23 Knut confirmed the built behaviour of the
> beta 34 to beta 38 records
> ([5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113),
> *"confirmed except §18.1"*); each block he confirmed says so and names him.
> Every other section is still **⏳ Awaiting confirmation**.
>
> The tolerance numbers of ISO 12647-7:2016 and ISO 12647-8:2021 are NOT in
> this document and not in the code. ~~Whether they may ship is Sebastian's
> open question S-2; until then the two ISO columns read `?` and cannot be
> chosen for a run.~~ **Superseded by §23 (2026-09-23):** S-2 is answered in
> principle by DIN's written statement that values alone are not
> reproduction. The repository's `data/compliance_sets/iso12647.json` may carry
> them, as values only, each set empty or complete; filling it waits on the
> owner's go-ahead, and until then the two ISO columns still read `?`.

**These specifications are binding.** Knut's rule (2026-08-06): they are
consulted before code in this area changes, and a fault that contradicts them
is reported and approved before it is fixed. The blocks marked confirmed
below are confirmed behaviour; everywhere else the binding part is the
*record* of what was built and why, not a confirmed behaviour.

## Index of Knut's rulings, beta 34 to beta 38 (2026-09-22 and 2026-09-23)

Knut, #182, 2026-09-23
([5792874817](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792874817)):
*"Record all verified and agreed behaviour into the design specification
document, so that it is kept and changes are compared against agreed behaviour
to protect against wrong implementations in the future."*

Every ruling he gave on #182 from the morning of 2026-09-22 (his beta 32
review, built into beta 35) to beta 38 is listed here, with the section that
records it. Each such section carries a **Record** block: the rule in plain
words (his words where they are the rule), the comment and date, **Built:**
where in the code, **Verified by:** the tests that go red if the rule breaks,
**Proof:** the on-screen proof folder, and its **Status**. A comment number
`N` is `https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-N`.

What the status words mean. **Agreed** means Knut gave the rule, so it is agreed
behaviour from the day he gave it. Whether what was BUILT from it is right is a
separate question, and it stays open until he confirms it. **Knut confirmed
the built result of every section on the confirmation list except §18.1 on
2026-09-23**
([5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)):
those rows read "confirmed by Knut 2026-09-23", and their sections carry
**Confirmed by:** Knut. §18.1 is superseded by his Calibration rule
(5794078008), confirmed as a rule and built in beta 39 (§18.12, the built
result awaiting his confirmation). The rule of
§13.9 / G7 is confirmed and built in beta 39 (§13.13, B8-848), the built
result awaiting his confirmation. The other §20 gaps stay open.

| section | subject | Knut's ruling | status |
|---|---|---|---|
| §11 | "Bound, and locked" explained in the report | 2026-09-11 | superseded by §18.2 (removed from the report) |
| §11 | "This report covers n of the total": counted by run type and by the list (K14) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.8 | Generate asks about a selected report even when nothing changed (K4) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.8 | An Update re-creates a report by today's rules; an older report keeps its text until then | 2026-09-22, 5773668311 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.9 | A report that judges nothing keeps every ticked measurement (K16) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.9 | One report, one limit set, applied to every measurement it includes, across runs | 2026-09-22, 5773668311; confirmed 2026-09-23, 5794311113 | agreed; rule confirmed by Knut 2026-09-23 (5794311113); built in beta 39 (§13.13, B8-848), the built result awaiting confirmation |
| §13.10 | Report types by run type; the automatic report follows (K13) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.10 | "The measurement decides, not the bar" | assumption, 2026-09-22 | superseded by K24 (the profile bar decides) |
| §13.10 | A calibration keeps every report type | assumption, 2026-09-22 | superseded by §18.1 (no report under Calibration), which is itself superseded by the Calibration rule of 5794078008 (every type but the Printing record; built in beta 39, §18.12) |
| §13.10 | A saved report of a disallowed type is "shown as recorded" | assumption, 2026-09-22 | superseded by K19 (not offered in the list) |
| §13.10 | The report type can be chosen with two runs' measurements added (K17) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.10 | Counts and list hold only the types the run type allows (K19) | 2026-09-23, 5785414710 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.10 | The profile bar's Run type decides what the window lists and counts (K24) | 2026-09-23, 5787117741 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.11 | Where a report lives, and which folders the list reads (K23) | 2026-09-23, 5787117741, 5787380408 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.11 | Update moves an older report into the new place; Delete leaves each date's verdict record | 2026-09-23, 5789263863 | agreed; built, confirmed by Knut 2026-09-23 (5794311113). The records half is superseded by K31 (§25.1, §25.6): no record is written; records already on disk are read-only history |
| §13.11 | "Save report as PDF" opens the report's own reports/ folder (K9) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.11 | A new report's PDF name carries that report's own time (K12) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.12 | "Report shown" grouped by run and by project (K25) | 2026-09-23, 5789263863, 5789532633 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §13.12 | "Names stay" on a Profiling window | our reading of 5789532633 | superseded by §18.6 (a misreading: Profiling names are Run1, Run2, …) |
| §14 | A ChromIQ set never carries a "recommended" note (K3) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §14 | The ISO COND cap is retired; the caveat carries the qualification | 2026-09-22, 5774852534 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §14.5 | The guide explains what COND meant before ChromIQ 4.3.0 | 2026-09-21 | superseded by K18 (§19.1) |
| §16 | Evenness: method, noise guard, 9 by 9, limits, cause notes (F1 answers 1 to 5) | 2026-09-22, 5785774676 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §16 | 9 by 9 stays the minimum grid (12 by 12 considered and dropped) | 2026-09-23, 5787380408 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §16.5 | E1 a page under 9 by 9 is left out, the others judged | 2026-09-23, 5789263863 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §16.5 | E3 tight and quick at half and double (0.75 / 0.5, 3.0 / 2.0) | as first built | superseded by E3 (all three ChromIQ sets 1.5 / 1.0) |
| §16.5 | E3 all three ChromIQ sets carry 1.5 / 1.0 | 2026-09-23, 5789263863 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §16.5 | E4 the evenness rows do not take a preset's star | 2026-09-23, 5789263863 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §16.5 | E5 / E6 Custom columns 1.5 / 1.0; rows stay in the ISO structure | 2026-09-23, 5789263863 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §16.5 | E7 1.0 on the from-the-mean row | 2026-09-23, 5789263863 | agreed (Knut: "confirmed", of the value); built, confirmed by Knut 2026-09-23 (5794311113) |
| §16.6 | E2 page coverage at 75 % | 2026-09-23, 5789539407 | superseded by 60 % (5792912682) |
| §16.6 | E2 page coverage at 60 %, from the "Measured from Preview" margins | 2026-09-23, 5792912682 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §16.6 | E4 the i1Pro 3 Plus 11 by 14 presets as their own case | 2026-09-23, 5789263863, 5792928823 | agreed; checked, confirmed by Knut 2026-09-23 (5794311113) |
| §16.6 | E8 judge evenness in absolute Lab? | 2026-09-23, 5789263863 | superseded by his answer "Yes" (5795087247, §21.1) |
| §21.1 | E8 evenness always judged in absolute Lab, whatever the print's intent | 2026-09-23, 5795087247 | agreed; built in beta 39, awaiting confirmation. Supersedes the "same yardstick" clause of §16.1 item 1 |
| §21.2 | B8-483 the grey ramp's required steps picked roughly evenly spaced, within a few percent of full scale | 2026-09-22, 5775993270; 2026-09-23, 5795087247 | agreed; built in beta 39 (4 % of full scale), awaiting confirmation (gap G13 built) |
| §21.3 | R2 the pre-flight widened to show the full paragraph (*"Leave the window wider as previously specified"*) | 2026-09-22, 5781645939; 2026-09-23, 5795087247 | agreed; built in beta 39, awaiting confirmation (gap G5 built) |
| §21.4 | A report deleted across projects goes to `<ChromIQ default folder>/old/<date>/`, shown in "Where are my files?" | 2026-09-23, 5795087247 | folder agreed ("Yes"); the help card rows built in beta 39, awaiting confirmation |
| §17 | Trend graphs for the judged metrics, each with its own limit line (K20/K21) | 2026-09-23, 5785414710, 5787117741, 5787380408 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §17.1 | Every graph explains its lines, its red x and itself (K25 graphs) | 2026-09-23, 5789263863, 5789532633 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §17.1 | A limit word slides along its line off a data line | as first built | superseded by §18.9 (stays at the left end) |
| §17.1 | A red x's neighbours are the dates directly beside it | 2026-09-23, 5789263863 | superseded by §18.9 (nearest dates with a value) |
| §18.1 | K26: Run type Calibration opens empty and locked | 2026-09-23, 5792484060 | built in beta 38; NOT confirmed; superseded by the Calibration rule below |
| §18.1 | Calibration rule: every type but the Printing record, `cal/reports/`, Cal / Multiple cals / All cals, grouped by project | 2026-09-23, 5794078008 (our summary 5794100213) | rule confirmed by Knut 2026-09-23 (5794311113); built in beta 39 (§18.12) |
| §18.12 | Run type Calibration as built in beta 39: the kind, `cal/reports/`, the list, the names, the grouping, Generate, the automatic report | 2026-09-23, 5794078008, 5794311113 | built; the built result ⏳ awaiting confirmation |
| §18.2 to §18.11 | K26: Bound and locked, Judged against row, within-gamut graph, folder rename, Profiling names, "these measurements", shared folder, red x, grouping from the start, demo white | 2026-09-23, 5792484060, 5792576954 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.1 | Report text is for a customer: no ChromIQ how-to, no history (K18) | 2026-09-22, 5774852534; 2026-09-23, 5785414710 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.2 | An N-A note names what the measured chart lacks, nothing to do (K22) | 2026-09-23, 5787117741 | agreed; built, confirmed by Knut 2026-09-23 (5794311113). Supersedes S2w "each names the thing to change" (2026-09-18) |
| §19.3 | The one-page summary gives its numbers with their unit (K10) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.4 | The paper white line prints L\*, a\* and b\* (K5) | 2026-09-22, 5781159382 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.5 | The verification pre-flight: only before the first measurement, a generic count (K2) | 2026-09-22, 5777667003, 5781159382, 5784377277 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.6 | "Unlock this run's limits" is dim with fewer than two dated verifications | 2026-09-22, 5777805448 | superseded by K31 (§25.4): the box, the lock and the Preferences option are removed |
| §19.7 | Before printing, say that a metric the chart cannot answer can be set to "-" | 2026-09-22, 5774104083 | agreed; built, confirmed by Knut 2026-09-23 (5794311113). Its layout ruling R2 is built in beta 39 (§21.3) |
| §19.8 | Sheets with different patch counts: an information note, set apart from body text (R4) | 2026-09-22, 5774104083, 5781645939 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.9 | A report type says which metrics it judges; "Restore defaults"; the per-type column cancelled | 2026-09-22, 5777326491 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) (the sentence has no test: gap G9) |
| §19.10 | Restore Used Chart restores the chart's fields only | 2026-09-22, 5774852534, 5775260868 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.11 | A per-target row a stored block lacks opens on its default | 2026-09-22, 5775260868 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.12 | Knut's eight i1Pro presets built in (K1); the demo pack follows every rule (K15) | 2026-09-22, 5781159382, 5781197240, 5776517563; 2026-09-23, 5787117741 | agreed; built, confirmed by Knut 2026-09-23 (5794311113) |
| §19.13 | "New report…" on a bound run shows the run's own set, and says so | 2026-09-22, 5776479532 | superseded by K31 (§25.5): a run is never bound; New report starts on Preferences, unless the run has a default of its own chosen in Edit limits |
| §22 | K28: the judged figures on the one-page summary; one vocabulary; a "–" row leaves everywhere; "For information (no limit applies)"; the general N-A rule; the several-runs Run description; B8-845's texts | 2026-09-23, 5795087247 | agreed; built in beta 39 (B8-849), NOT confirmed |
| §24 | K30: every loaded report can be generated again and Update renames it; limits belong to the report across places; projects in two folders share the ChromIQ folder's reports/; a lone project's heading; the words of a report across places and of a calibration | 2026-09-23, 5798461562 | agreed; built in beta 39 (B8-852 to B8-859), NOT confirmed; the one-run limits window, asked in B8-853, is decided by K31 (§25.3) |
| §25 | K31: a report is the only thing (no verdict records); Update and New report from any window; a widened one-date report becomes a report of those dates; the limit set belongs to the report, one set always; "Unlock this run's limits" and the run lock removed; New report starts on Preferences unless the run has its own default | 2026-09-23, 5801677743 (our 5798697107, 5801707986) | ruled by Knut; built in beta 40 (B8-890 to B8-899), the built result ⏳ awaiting confirmation |
| §26 | K31 metrics: the "How evenness was judged" line and the evenness help text; rule A on the 30 to 70 % tone ramp; version 1 names everywhere, "within gamut" on a split sheet; "Within and beyond the gamut together"; a FROM PROFILE GAMUT chart's neutral aims as its grey steps | 2026-09-23, 5801677743 | agreed; built for beta 40 (B8-900 to B8-909), NOT confirmed |
| §20 | Rulings not built, or built without a test or proof (G1 to G13) | 2026-09-22 to 2026-09-23 | gaps, listed one by one |
| §29 | A row ChromIQ cannot measure reads ✕ in every limit set, never "–" | 2026-09-24, 5815435713 | agreed; built for beta 42 (B8-979), NOT confirmed |
| §30 | K33: "Any" beside "All metrics", the presets window's intro, why 18 and not 21, Knut's figures in both Custom ISO sets, the ISO report types offered, a wider "Judged against" help that says when to use which set | 2026-09-24, 5816565326 | ruled by Knut; built for beta 42 (B8-992 to B8-998), NOT confirmed; three figures and the count put back to him |
| §31 | K34: a deleted profile run named in Report Scope; a failed folder rename brings the choices back; "Report shown" by the report's own date; the paper patch, N-A without one; a FROM PROFILE GAMUT chart's reference paper is its profile's media white | 2026-09-24, 5817809396 | recommendations accepted by Knut; built for beta 42 (B8-1011 to B8-1016), NOT confirmed; two message texts proposed |
| §33 | K37: a white-mapped sheet whose chart has no paper patch is judged against the paper white of the profile it was printed through, with a numbered note; absolute Lab with a note on each row only when no profile can be read | 2026-09-24, 5822758830 | recommendation (e) accepted by Knut; built for beta 42 (B8-1081 to B8-1084), NOT confirmed; two message texts proposed |
| §34 | K37 (i): on a FROM PROFILE GAMUT chart the control strip compares its seven ink and black corner patches with the profile's prediction, the cube-corner table keeps the ideal values, and a note says so | 2026-09-24, 5823088098 (our 5823015844) | approved by Knut; built for beta 42 (B8-1085 to B8-1088), NOT confirmed; two message texts proposed |
| §36 | K40: every preset laid out behind the scenes for the evenness rows (printtarg or the layout engine, a "Working…" row, never a blocked window); the tone row of a FROM PROFILE GAMUT chart on its neutral aims; a demo project whose one chart answers every metric | 2026-09-25, 5832026677 | ruled by Knut; built for beta 43 (B8-1121 to B8-1125), NOT confirmed; the tone value of a neutral aim (100 − L\*) is ours to confirm |

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
> and from a ChromIQ default everywhere else.** *(Narrowed by §23: "the
> parent's value" means a figure from a licence holder's own file. A value
> ChromIQ SHIPS fills the read-only column and not the Custom one.)* Today the
> parent has none, so
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

**A Custom column draws its starting numbers from two places, in this order
of precedence.** Where both could answer a row, the earlier one wins.

1. **Knut's researched industry figures** (`compliance_sets::_CUSTOM_INDUSTRY`),
   given PER COLUMN because his file follows each standard's own structure.
2. **ChromIQ's own numbers** (`compliance_sets::_CUSTOM_CHROMIQ_FILL`), for
   the rows his research does not cover, so that Knut's 2026-09-11 rule still
   holds: every metric ChromIQ can measure arrives with a limit to be judged
   against.

**No values file fills a Custom column, not even a licence holder's own.**
Until 2026-09-24 a licence holder's own file came first, and on a machine that
has one both Custom columns became copies of the read-only ISO columns beside
them. Knut, #182 5815346140, 2026-09-24:

> *"we recently said that the industry limits that I set as defaults for the
> Custom ISO 12648-7 and Custom ISO 12648-8 limit sets should be used, thus
> they should no longer be copies from the ISO 12648-7 and ISO 12648-8 limit
> sets, but rather alternative limit sets to the standards. Set the default
> limits for Custom ISO 12648-7 and Custom ISO 12648-8 to the industry limits
> previously decided."*

A values file, shipped or the user's own, fills only the read-only ISO column.
Pinned by `tests/test_compliance_sets.py::test_a_licence_holders_own_file_never_fills_a_custom_column`.

**Knut's second set of figures (K33, 2026-09-24, awaiting confirmation).**
Knut, #182
[5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326):
*"I suggest adding thresholds to the both the Custom ISO limit sets so that all
metrics are included, as follows: "Maximum deltaE00, solid colours" = 3,00;
"Maximum deltaH\*ab, cyan, magenta and yellow solids" = 2,50; "Average
deltaE00, lowest 95%" = 2,00; "Average deltaE00, highest 5%" = 2,00; "Maximum
deltaE00, all patches" = 2,00; "Average deltaE00, outer-gamut patches" = 2,50;
"Average deltaE00, surface-gamut patches" = 3,00; "Maximum deltaL\*,
single-colour ramps" = 2,00."* Each label is a row's English label. They join
source 1, for both columns, on every row where the column took ChromIQ's own
number. **Where a new figure would replace one of his own figures of
2026-09-21, the earlier figure is kept and the choice is his** (§30.2):

| Column | Row | Kept (2026-09-21) | Proposed (K33) |
|---|---|---|---|
| Custom ISO 12647-7 | Maximum ΔE00, solid colours | 2.0 | 3.00 |
| Custom ISO 12647-7 | Average ΔE00, outer-gamut patches | 4.0 | 2.50 |
| Custom ISO 12647-8 | Average ΔE00, surface-gamut patches | 4.0 | 3.00 |

Two proposed figures equal what the column already held from 2026-09-21
(ΔH\*ab 2.5 in -7, the ramp row 2.0 in -8) and change nothing.

Measured against the repository's values file (which fills only the read-only
columns), each Custom column now carries **15 researched figures and 5 ChromIQ
numbers**, 20 limits, one on every row ChromIQ can measure. Before K33 the
split was 10 and 10 (-7) and 9 and 11 (-8); this paragraph said "10 and 8, 9
and 9, 18 limits", which had not counted the two repeatability rows. The five
rows neither set of his figures covers are one control-strip row (the 95th
percentile in -7, the maximum in -8), ChromIQ's two repeatability rows and the
two evenness rows.

**Ruled by Knut, #182 5831473881 (2026-09-25):**

> *"The intention was, for those settings that only is set in one of the
> Custom ISO limit set, that the one that does not have a number, takes that
> number from the other Custom ISO set, so that all the 21 metrics are defined
> with thresholds for the Custom ISO sets. For the three mentioned above, use
> 3,00 for all of them."*

So the three rows in the table above are **3.00** (Custom ISO 12647-7 solid
colours and outer-gamut patches, Custom ISO 12647-8 surface-gamut patches), and
a row only one Custom set's research covers takes that figure in the other set
too: the control-strip maximum (4.0, from -7) in -8, and the control-strip
95th percentile (4.0, from -8) in -7. **That was done once, by writing the two
figures into the tables**, not as a rule the program applies: Knut, #182
5831783959, *"this was not a general rule, but a one time operation to set the
new default values."*

Knut, #182 5831860724 (2026-09-25), on the four rows that were still
ChromIQ's: *"I thought I gave you the default numbers I wanted for the Custom
ISO settings for these 4."* His file of 2026-09-21 did carry the two
**evenness** rows (Custom ISO 12647-7: 1.0 and 1.0; Custom ISO 12647-8: 1.5 and
1.0), and they were never taken. They are now. Its "repeatability" row is
"print to print and day to day" (✕, ChromIQ cannot measure it), not ChromIQ's
two repeatability rows, so those two keep ChromIQ's numbers (2.0 and 3.0). Each
Custom column: **18 researched figures, 2 ChromIQ**, 20 limits. Each
Custom column now carries **16 researched figures and 4 ChromIQ numbers**, 20
limits. The four are ChromIQ's two repeatability rows and the two evenness
rows, which neither set of his figures covers. ⏳ Awaiting confirmation.
**Confirmed by:** *nobody yet.*

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

**~~OPEN, PUT TO KNUT AND NOT ANSWERED HERE.~~ ANSWERED: DELIBERATE (A13).**
In the ISO values file he sent two days earlier, two of the six rows the two
sets share were looser in 12647-8 than in 12647-7. In this file all six are
identical across the two sets. Asked whether that is deliberate (A13 of
5802027116), Knut answered, 2026-09-24, [5817809396](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817809396): *"The six identical
rows are deliberate."* What he sent is what is built, and nothing changes.

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
**Amended by §29 (Knut, 2026-09-24, beta 42):** a row ChromIQ cannot measure
reads `✕` in EVERY set, ChromIQ's own three included, and never `–`; `–` is
left for a row ChromIQ can judge that the set puts no limit on.

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
  level), a lightest level ≥ 90 and a darkest ≤ 10, and (since beta 39,
  §21.2) at least 8 of its levels roughly evenly spaced; the paper patch is
  left out of the statistics, composite black stays in. **On a chart built
  FROM PROFILE GAMUT the steps are its neutral aims instead, placed by L\*
  (§26.5, K31, beta 40).** This is the same
  arithmetic as the ISO near-neutral rows; the standards' aim is
  characterization data, ChromIQ's aim is the chart's design (footnote ²).
  TR 015's substrate-relative aim is deliberately not used: a perfect
  relative-intent print scores 0 against the design and up to 1.78 ΔCh
  against that aim.
* **Single-colour ramps 30 % to 70 %**: per device axis (and the grey axis),
  |ΔL\*| against the reference over patches whose tone value lies in
  30..70 %, largest; eligible with at least 3 distinct tone values spanning
  ≥ 20 %. A recommendation (ISO 12647-8:2021 4.2.7 is a *should*).
  **Amended by §26.2 (K31 rule A, beta 40):** three of those steps must also
  be roughly evenly spaced (4 points), else `ramp_steps_bunched`.
* Rows needing a reference file for the printing condition (paper white
  against the reference paper, solid colours, CMY hue difference) read N-A
  until such a reference exists (Knut D31: "a reference measurement file you
  supply" is the footing; the reading of such a file is not built yet).

## 4. The verdict words

**⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

Per row: PASS when the value is within the limit; FAIL when over it,
**whether the set requires that limit or only recommends it** (§14); INFO when
the set puts no limit on the row (**SUPERSEDED by K28, §22.3: such a row is
not in the report at all**), or the sheet is not graded, **or the row
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

> **SUPERSEDED by K31 (§25, Knut, #182 [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743), beta 40).** A run is no longer bound to a set, nothing is locked, and nothing in this section binds, locks, unlocks or recalculates any more. The limit set belongs to the report; a profile run holds at most its own default for new reports, chosen in Edit limits. What is below is kept as the history of the rule and of what an older meta.json may still carry (`compliance_bound_at`, `compliance_unlocked`, a stored copy), which this build reads and never sets (a meta.json it saves carries them empty).

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

**Amended (challenge 5 of beta 42, B8-1091 and B8-1094, not confirmed):** a
rebuilt report's kept verdict is shown with the report's own record, not with
the rebuild's explanations (§33.6's amendment), and only Generate works a
report out again from disk (§28.10's amendment).

**Amended (K39, Knut 5831246553, 2026-09-25, not confirmed):** the line that
says so, M-REPORT-WORKED-OUT-EARLIER, is approved without its last sentence
("Update works the report out again."), which named a button; it now ends
*"A newer report of the same measurements would be worked out the current
way."* (§35). And with nothing changed, Generate report asks whether to
update in words that say when an Update would change such a report (§28,
27.12).

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
uniformity form (N5). ~~The ISO numbers (S-2).~~ *(Prepared, §23: the file
and every text are ready; the values go in on the owner's go-ahead.)* Of the
six report types of §10,
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
*Amended (challenge 3 of beta 42, B8-1031, not confirmed):* since the ISO
values ship (§23, §30.6) the heading reads "For a published ISO standard",
and the two lines under the ISO names read "For a validation print, to be
judged against the values of ISO 12647-8." and "For a contract proof, to be
judged against the values of ISO 12647-7, the stricter of the two." Both stay
true when a licence holder lays a file of their own over the shipped values,
and neither claims a print conforms.

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
  **Confirmed by:** *nobody yet.* (Beta 39, G12: T4 now prints the notes
  explaining its N-A rows and has no Result column in its detailed table,
  §12 CH-31a.) T4 prints neither the note saying what a PASS under a
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
  does not certify. *(§37.2, K42-2, not confirmed: under a limit set
  named after a standard that sentence is the caveat's "A PASS means …", and
  it is the last paragraph of the Result section, not the foot of the page.)* No customer or job name (Knut, 2026-09-11: *"No customer
  of job name per today"*). It is about ONE measurement, the one the window is
  on, so the tick that widens every other report to the whole history is
  disabled while it is chosen.

**A type this build cannot produce is shown and refused,** not hidden, and it
is never honoured: the run refuses to store one, and a stored one, which a
project made on a later ChromIQ can carry home, is read as Full colour check.
What is on disk is left alone so that later ChromIQ still finds the choice.

**Not built here:** T5 and T6. ~~Their figures are published in standards
ChromIQ has no permission to include (§9, S-2).~~ *(§23: once a standard's
values ship, the greyed entry says only that the report is still being built;
while they do not, it still names the figures.)* **Amended by §30.6 (K33,
2026-09-24, awaiting confirmation):** T5 and T6 are built and offered while
their standard's values are loaded.

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
published tolerance values and nothing else, that ChromIQ ships none of them
*(superseded: K18 rewrote this paragraph, and §23 prepares the values to ship)*, so
such a column is empty unless a licence holder has supplied its figures, and
that an editable column starts from those supplied figures where there are any
and from ChromIQ's own numbers where there are none. Either way the values are
applied to the chart you printed rather than to that standard's own chart and
control strip. Same fact, stated positively.

> **Wording superseded by K18 (§19.1), 2026-09-23.** "the chart you printed"
> is now "the printed test chart": report text is written for a customer who
> never sees the chart. The fact the paragraph states is unchanged.

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

> **Wording revised, re-challenge R2 of beta 39 (#2), 2026-09-23 (B8-912).**
> Two clauses of the note and of this paragraph were false or a claim. "Its
> limits may differ from the standard's published values" is false of a
> read-only ISO column once §23 ships that standard's values, which is the one
> state such a column is judged in; and "an indication that the print would
> likely meet the standard" is a hedged conformance claim in text handed to a
> customer (K18), beside a Report limits window that says a report can never
> say a print conforms. Both now state what was judged and against what: "This
> limit set is named after a standard. Its limits were applied to the values
> measured on the printed test chart with ChromIQ's own metrics, not to that
> standard's own chart and control strip with its own methods, so this is not
> a test against that standard. A PASS means that the measured values are
> inside these limits. It is not proof that the print meets the standard, and
> where these limits are wider than the standard's own it says nothing about
> the standard." Knut's "not proof" and his condition on the limits (§19.1)
> are kept; his "likely fulfil" is not. The "How to read" paragraph is printed
> only in a report with a column judged against a standard's set, which is
> exactly when the note it points to is printed. This changes wording Knut
> asked for, so it waits for him.
> **⏳ Awaiting confirmation.** **Confirmed by:** *nobody yet.*

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

> **SUPERSEDED by K26 (§18.2), Knut 2026-09-23
> ([5792484060](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792484060) Q2):**
> *"Remove it from the report, and make sure this information is in the
> relevant help text."* The paragraph is no longer in the report; the same
> sentences are in the "Judged against" help. The two paragraphs above it
> stand.

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

*✅ **What is counted, confirmed (2026-09-22, B8-778 K14; confirmed
2026-09-23).** The
code had drifted from this sentence to "recorded for this project" and counted
every run's sheet plus every dated verification, so Knut's Printing record of
three profile runs said "1 of the 18". On his ruling that the count relate to
the run type and to the measurements in "Included measurements": a document of
verifications is counted against the dated verifications of the runs in that
list ("recorded for this run", "for these runs"), and a document of profiling
sheets against the project's profiling measurements ("recorded for this
project's profile runs"). A document mixing both kinds keeps the old count.
Whatever is counted is still read off the disk, never out of the window.*
**Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
This confirms the K14 count only; the rest of §11 still waits under its own
marker above.

**Record (K14).**
* **Rule:** the "This report covers n of the total" sentence counts only what
  relates to the run type and to the measurements in "Included measurements":
  *"it should only show relating to run type is Profiling, and the
  measurements selected in included measurements input box."* A report that
  covers everything it could cover says nothing.
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K14 of B8-778).
* **Built:** the Report Scope count in `ui/dialogs/measurement_report_dialog.py`
  (B8-790, commit a52c8fdb); wording reworked by B8-799 ("profile run", a
  count instead of "these runs").
* **Verified by:** `tests/test_the_report_reads_as_a_printed_document.py::`
  `test_a_printing_record_counts_the_projects_profiling_measurements`,
  `test_a_verification_report_of_every_date_of_its_run_says_nothing`,
  `test_the_total_is_what_the_project_records_not_what_is_loaded`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K14-coverage-count/` (beta 35 "1
  of the 18"; fixed "1 of the 3 measurements recorded for this project's
  profile runs").
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

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

**CH-31a. ⏳ Awaiting confirmation (G12, beta 39).** **Confirmed by:**
*nobody yet.* Amends CH-31 after Knut's question on the Printing record with
"Show detailed data" on (5774852534, 2026-09-22): *"The sections with detailed
data still shows PASS and FAIL, or if a metric could not be checked. Should
there be a note there instead, so a user knows why a metric could not be
checked?"*, and his "OK" (5775260868) to *"notes wherever a verdict is shown,
suppressed where none is"*. Two kinds of note are told apart:

* a note that COMMENTS a verdict (the grey rows' printing note, the
  recommended-limit note, the evenness causes and "where on the sheet") lives
  and dies with the verdict, as CH-31 says, and the Printing record prints
  none of them;
* a note that EXPLAINS AN ABSENCE (every N-A reason, §19.2) is not about a
  verdict, so the Printing record prints it: each N-A row carries its raised
  number in the Report Results grid and in the detailed table, and the list is
  headed "Notes on the values above:" with the closing sentence "A value that
  could not be worked out says nothing about the printer; each note above says
  why." (no word about failures).

On the Printing record the detailed "Colour accuracy" table has no Result
column: a value that could not be worked out reads a dash with its note
number, and no PASS, FAIL, COND, INFO or N-A appears in the detailed section.
The gamut paragraph under it no longer says "The Result judges".

On EVERY type the detailed table carries the same note numbers the Report
Results grid gives the row (CH-32, CH-33), and lists the notes it points at
under itself, because in the PDF the detailed section starts on a page of its
own.

Built in `ui/dialogs/measurement_report_dialog.py` (`_note_the_absences`,
`_notes_list_html`, `_run_detail_html`); verified by
`tests/test_g12_notes_where_a_value_is_shown.py`; proof
`~/Desktop/ChromIQ-beta39-proof/notes/` (B8-845).

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
| K.7e | **Create New is first and the default** (K32, Knut on beta 41, #182 5813851807): *"Move Create New button to be the first button on the left and Update button to be the middle button. Make sure bullet list description also has same sequence, Create New button in first bullet etc. The Create New button should be default selected, so than an enter would Create New by default (Safest)."* Buttons from the left: **Create New**, **Update**, **Cancel**; Enter creates a new report; the numbered list is in the same order. Both variants of the question (settings modified, nothing changed). |
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

> **Since built, on later rulings:** the folders in §13.11 (K23), what each run
> type offers in §13.10 (K13), the Profiling names in §18.6 (K26). The
> paragraph above is kept as the state of 2026-09-19.

**✅ K4, 2026-09-22: Generate asks even when nothing was changed.**
**Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)),
for the two records below (K4, and an Update re-creating a report). The K.7
block at the head of §13.8, with its two open points, is not covered by this
confirmation and keeps its own line.

**Record (K4).**
* **Rule:** with a report selected in "Report shown", Generate report never
  writes a new report without asking. Knut: *"I clicked Generate Report button
  (without any settings having been changed.). This resulted in a new report
  being created, without user being asked if I want to create a new or update
  the selected"*. This widens K.7: the question is asked whether or not a
  setting changed. With nothing changed its headline says so
  (M-REPORT-UNCHANGED-UPDATE-OR-NEW, §M-PROPOSED, not approved); the three
  buttons are K.7's. Adding or removing a measurement, or a saved type the
  run type no longer allows, counts as a change (B8-799, B8-809).
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K4 of B8-778).
* **Built:** `_document_being_updated` in
  `ui/dialogs/measurement_report_dialog.py` (B8-792, commit 265216d5). Update
  archives every file it rewrites into `reports/old/` first, and writes all or
  nothing (`core/file_manager.py::archive_report_files`, B8-782, B8-793).
* **Verified by:** `tests/test_generate_report_asks_what_to_do.py::`
  `test_the_question_is_asked_only_when_both_halves_of_his_sentence_hold`,
  `test_the_unchanged_question_says_nothing_was_changed`,
  `test_update_copies_every_file_it_rewrites_into_old_first`,
  `test_a_file_whose_archive_fails_is_not_rewritten`,
  `test_an_update_that_cannot_write_one_date_writes_none_of_them`;
  `tests/test_round3_a_features_since_265216d5.py::`
  `test_adding_a_measurement_is_a_change_to_the_selected_report`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K4-generate-unchanged/` and
  `~/Desktop/ChromIQ-beta36-proof/D23-update-archives/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (an Update re-creates the report; an older report keeps its text).**
* **Rule:** *"If a report was made before 21 September that report would
  contain the results and report text at the time the report was saved. Only
  if a user updates that report after 21 September that report would be
  re-created fully with all new wordings and changes done for a release of the
  app after that date. So the settings used belong to the report that is
  created"*. Opening a saved report shows it as saved; Update rebuilds it with
  today's wording and rules, the previous version archived first. His
  2026-09-23 answer (5789263863, Q2) says the same of a report written before
  the K23 folders: *"Yes, update it."*
* **Ruling:** Knut, 2026-09-22,
  [5773668311](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5773668311).
* **Built:** Update is `_write_the_document` / `rewrite_report` (K.7a); a saved
  report is read, never rewritten, on open (§14.5, §5).
* **Verified by:** `tests/test_generate_report_asks_what_to_do.py::`
  `test_update_copies_every_file_it_rewrites_into_old_first`;
  `tests/test_k23_report_folders.py::`
  `test_a_legacy_document_of_several_dates_counts_once_and_stays`,
  `test_update_rewrites_the_document_file_in_place_and_archives_it`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/D23-update-archives/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)). This answers
  question 9 of our 5784140521 as far as his words go.

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

> **The guide's history clause is SUPERSEDED by K18 (§19.1), Knut 2026-09-23:**
> *"A report text shall never explain something in the past, only the current
> functionality ... Only explain what the meaning of COND is and how to
> understand it when it occurs."* The guide now defines COND by its meaning
> only, with no ChromIQ version in it. A saved COND is still shown as
> recorded and still defined.

### 14.6 Records of the verdict rulings of 2026-09-22

**✅ Confirmed.** **Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)),
for both records below.

**Record (the ISO COND cap is retired).**
* **Rule:** a column named after a standard reads PASS or FAIL for the metrics
  that ran, like every other column: *"Implement this. The note is
  sufficient."* The qualification lives in the caveat under the results
  (and in the one-page summary's footer), which says the chart is not the
  standard's, the metrics are ChromIQ's own, and a PASS is an indication, not
  proof. The overall result is PASS or FAIL for what was checked; a metric
  that could not be checked is N-A with a note saying why, and never makes a
  column COND (*"The overall results must show PASS or FAIL for the metrics
  that were executed"*, 5774104083).
* **Ruling:** Knut, 2026-09-22,
  [5774852534](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5774852534)
  and [5774104083](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5774104083).
* **Built:** `workflow/compliance_sets.py::set_summary` (the cap removed, the
  COND case answered first) and `STANDARD_CAVEAT` (B8-760, commits 44e36ca1,
  4eed2a45; B8-769, B8-770); the caveat text corrected for a Custom set by K18
  (B8-808).
* **Verified by:** `tests/test_a_custom_iso_column_carries_the_same_caveat.py::`
  `test_every_row_within_its_limit_reads_PASS_and_still_carries_the_caveat`,
  `test_the_caveat_says_it_is_not_proof`,
  `test_no_user_facing_string_still_teaches_the_retired_cap`,
  `test_the_glossary_says_what_replaced_it`;
  `tests/test_a_saved_pass_under_a_standard_is_never_bare.py::`
  `test_the_caveat_is_in_the_report_body_and_the_pdf`;
  `tests/test_the_one_page_summary_prints_on_one_page.py::`
  `test_a_standard_named_column_gets_the_caveat_on_this_page`,
  `test_it_is_still_one_page_with_the_caveat_on_it`;
  `tests/test_an_absence_never_makes_a_column_conditional.py::`
  `test_and_the_one_cause_that_does_remain_still_reaches_it`.
* **Proof:** no on-screen folder recorded for this change; the caveat on the
  page appears in the beta 36 and 37 report photographs
  (`~/Desktop/ChromIQ-beta36-proof/final-challenge/`). Gap G10 (§20).
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (K3: no "standard" note under a set that is not a standard).**
* **Rule:** a note about what "the standard" calls recommended is printed only
  under a set derived from a standard. Knut, on Quick check: *"The test refers
  to the standard, which is not used as reference or to compare results
  against for the current settings. This is a bug."* A ChromIQ set never
  carries a recommendation, whatever an older stored copy of it says; nothing
  on disk is rewritten.
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K3 of B8-778), with §14.1 point 5.
* **Built:** `workflow/compliance_sets.py::set_marks_recommendations`, read by
  every reader of a stored copy (B8-795, commit cbf4f083).
* **Verified by:** `tests/test_a_note_about_a_standard_needs_a_standard.py::`
  `test_a_chromiq_set_never_carries_a_recommendation`,
  `test_the_quick_check_page_says_nothing_about_a_standard`,
  `test_a_set_derived_from_a_standard_keeps_its_note`,
  `test_the_runs_own_copy_is_read_without_the_relic`,
  `test_the_loaded_quick_check_documents_limits_carry_no_recommendation`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K3-standard-note/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

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

**✅ K16 confirmed.** **Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)),
for the K16 record below only. R.1 to R.6 above keep the marker at the head of
this section.

**Record (K16, R.3 on a report that judges nothing).**
* **Rule:** R.3 above, reported broken on beta 34: *"I then tried to select 2
  of the three measurements and generate report, and selecting Create New in
  popup window. The new report is created, but the report is named with flag
  'One date', and the 2 selected measurements were automatically changed to one
  selection. This is wrong, as reported before."* A Printing record, which
  judges nothing, covers exactly the ticked measurements whatever sets they
  were once judged against; with two of three ticked it is "Multiple dates"
  (on a Profiling window "Multiple runs", §18.6).
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K16 of B8-778).
* **Built:** `_one_limit_set` in `ui/dialogs/measurement_report_dialog.py`
  narrows only a report that judges (B8-786, commit 8ae07e4f).
* **Verified by:** `tests/test_a_report_is_written_against_one_limit_set.py::`
  `test_a_printing_record_keeps_every_ticked_measurement`,
  `test_profiling_sheets_are_not_narrowed_under_any_type`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K16-two-of-three/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (one report, one limit set, across runs). Built in beta 39 (§13.13,
gap G7 of §20), awaiting confirmation.**
* **Rule:** a report is judged against ITS OWN limit set, and that one set is
  applied to every measurement the report includes, even when they belong to
  different profile runs whose own reports used other sets: *"The project
  across both profile runs' verification measurements have only one defined
  limit set ... The same settings are used in that report to check the metrics
  for the selected measurements to include, even if the measurements belong in
  separate profile runs dated verification runs."* And: *"It does not matter
  if one report uses a metric as recommendation ('should') and the other report
  uses required ('shall'), those reports are separate."*
* **Ruling:** Knut, 2026-09-22,
  [5773668311](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5773668311).
* **Built (beta 39, B8-848):** across profile runs and across projects, as
  ruled: every included measurement is judged against the report's own set
  (§13.13). Before beta 39, not as ruled: `_one_limit_set` narrowed a GRADED
  report to the measurements judged against one set (his ruling of
  2026-09-16), so verifications judged against different sets and ticked
  together lost all but one set's dates (B8-786 "NOT decided here", B8-793
  A-4). Within ONE profile run it still does (a date recorded against a set
  the run was later re-bound away from); whether G7 reaches that case too is
  a question in B8-848. Question 8 of our
  [5784140521](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5784140521)
  asked which rule wins and has no answer yet; his words above, given earlier
  the same day, read as an answer.
* **Rule confirmed:** Knut, 2026-09-23
  ([5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)),
  answering question 8 of 5784140521: *"Yes, I confirm 'the report's own limit
  set applies to every included measurement, whatever each run is bound
  to.'"* This settles question 8.
* **Verified by:** `tests/test_g7_reports_across_places.py` (8 tests, each
  red on the mutation in its docstring), and the retargeted
  `tests/test_a_report_says_what_it_is_and_what_judged_it.py::`
  `test_two_runs_bound_to_different_sets_are_judged_by_the_reports_set`,
  `tests/test_a_report_is_written_against_one_limit_set.py::`
  `test_renaming_the_project_does_not_pull_another_set_into_the_document`,
  `test_the_limit_split_survives_the_window_repainting_itself`.
* **Proof:** `~/Desktop/ChromIQ-beta39-proof/g7/` (REPORT.md, photographs,
  folder listings before and after every press).
* **Status:** agreed rule, confirmed by Knut 2026-09-23; built in beta 39;
  the built result ⏳ awaiting confirmation. **Confirmed by:** *nobody yet.*

### 13.10 Which report types each run type offers (Knut, 2026-09-22)

**✅ CONFIRMED.** **Ruled by:** Knut, #182 comment 5781159382,
against beta 34. **Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
This records his ruling and what was built from it (B8-778 K13), and he has
confirmed the built behaviour (K13, K17, K19, K24). Not covered: what a
calibration offers (the bullet on "a measurement with no run" below), which
§18.1 and its replacement decide.

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

* ~~**The measurement decides, not the bar.**~~ **SUPERSEDED by K24 (below),
  2026-09-23:** the profile bar's Run type decides; the measurement is asked
  only by a window with no bar behind it. *As first built:* the report window
  had no run type of its own; it was opened on a measurement, so that
  measurement's kind was used: a run's own sheet is profiling, a dated
  verification is verification. The automatic report asks the same question
  the same way (it has no window, so this half stands).
* **Profiling: Printing record only. Verification: every buildable type but
  the Printing record.** The others are shown greyed with a sentence saying
  why, as an unbuilt type is (§10), not hidden.
* **A measurement with no run** (a file outside any project, and a
  calibration) keeps every type, as before. *Assumption:* a calibration is not
  a profile run, so the rule is not applied to it. **Overturned for
  calibration by K26 (§18.1):** under Run type Calibration the window makes
  no report at all and opens empty. **§18.1 is itself replaced** by the
  Calibration rule of 5794078008 (every type but the Printing record),
  built in beta 39; see §18.12.
* **Preferences "Report type, default" applies to every measurement that is
  not a profiling measurement** (verifications, calibrations and files outside
  a project), so the Printing record is greyed there, and a stored Printing
  record default (legal until beta 35) is read as Full colour check. Nothing
  on disk is rewritten.
* **A saved report of a type its kind no longer allows** (a Printing record
  of a verification saved by beta 34) ~~is shown as recorded~~ (**SUPERSEDED
  by K19 below:** it is no longer offered in the list or counted; it stays on
  disk untouched), and Update or
  Create New writes the type the kind allows; the question then says the
  settings were modified, because they will be. A saved report that records
  NO type follows its run (§10), so a profiling sheet's is labelled and drawn
  as a Printing record. *Assumption:* what a document IS is not changed by
  opening it.
* This amends §10 ("T2 ... is the default for every report written before this
  existed and every run nobody has chosen for") and §13.6 P.2 and P.6, which
  now hold for verification measurements only.

**K19 (Knut, #182 comment 5785414710, 2026-09-23), ✅ confirmed,
Confirmed by: Knut, 2026-09-23 (#182 comment 5794311113).**

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
disk, untouched), where it was shown as recorded. ~~*Assumption:* "run type"
here is the window's measurement, as in the first bullet; adding a measurement
of the other kind makes it the window's subject (B8-803 is open on that).~~
**SUPERSEDED by K24 (below):** "run type" is the profile bar's.

**✅ K17 and K24, 2026-09-22 and 2026-09-23.** **Confirmed by:** Knut,
2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (K13).**
* **Rule:** his words at the head of this section. Profiling offers only the
  Printing record; Verification offers every type but the Printing record;
  the report written by itself after a Profiling measurement is a Printing
  record; after a Verification measurement it is Preferences' default unless
  the run chose another; the Report type help says which types are available
  when.
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K13 of B8-778).
* **Built:** `workflow/measurement_report.py::report_types_for_kind`,
  `workflow/run_compliance.py::report_type_default_for` (B8-787, commit
  c9b6ee9d); the greyed types and their sentence in
  `ui/dialogs/measurement_report_dialog.py`; Preferences greys the Printing
  record.
* **Verified by:** `tests/test_the_report_type_pulldown_stores_on_the_run.py::`
  `test_a_profiling_measurement_offers_only_the_printing_record`,
  `test_a_verification_never_offers_the_printing_record`,
  `test_a_forced_printing_record_on_a_verification_is_refused_and_writes_nothing`,
  `test_the_automatic_report_of_a_profiling_measurement_is_a_printing_record`;
  `tests/test_the_measurement_report_defaults_are_knuts.py::`
  `test_a_printing_record_default_is_refused_for_a_verification`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K13-types-by-run-type/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (K17).**
* **Rule:** with measurements of two profile runs added, the report type can
  still be chosen: *"I select some measurements from both sets, but now I am
  not allowed to select report type at all."* The choice is the window's for
  the session and is written to neither run; a greyed Generate report says
  why in its tooltip, and the advice it gives works ("Remove Profile's
  Measurements…").
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K17 of B8-778).
* **Built:** the type pulldown and Generate tooltip in
  `ui/dialogs/measurement_report_dialog.py` (B8-785, commit 17353929; the
  tooltip's advice corrected by B8-789 and B8-799).
* **Verified by:** `tests/test_the_report_type_pulldown_stores_on_the_run.py::`
  `test_with_two_runs_ticked_the_type_can_be_chosen_and_neither_run_is_written`,
  `test_a_greyed_generate_says_why_when_only_another_run_is_ticked`,
  `test_with_two_runs_ticked_generate_is_live` (the last two retargeted by
  G7, §13.13: two runs loaded no longer grey Generate);
  `tests/test_round_2b_text_findings.py::`
  `test_a_measurement_in_no_run_says_why_generate_is_grey`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K17-two-runs-type/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (K19).**
* **Rule:** his words quoted above: "Already generated…" and "Report shown"
  count and list only report types the Run type allows (a verification's
  types under Verification, the Printing record under Profiling), from the
  folders of the measurements in the list.
* **Ruling:** Knut, 2026-09-23,
  [5785414710](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5785414710).
* **Built:** `workflow/measurement_report.py::generated_report_types`,
  `ui/dialogs/measurement_report_dialog.py::_saved_documents` (B8-809, commit
  8930cead).
* **Verified by:** `tests/test_k19_counts_follow_the_run_type.py::`
  `test_a_verification_counts_no_profiling_record`,
  `test_each_filter_holds_on_its_own`, `test_the_list_offers_only_the_kinds_types`,
  `test_an_untyped_report_is_counted_as_it_is_labelled`.
* **Proof:** no on-screen folder of its own (tests only); its folder rules
  were driven with K23 in `~/Desktop/ChromIQ-beta37-proof/report-folders/`.
  Gap G10 (§20).
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (K24).**
* **Rule:** *"The open measurement window strictly shows and lists and counts
  report types that are allowed according to the set 'run type' in the
  profile bar. So a user must exit the measurement report window and change run
  type to profiling, then enter measurement report window again, in order to
  show, list and count reports of 'printing record' type."* Adding a
  measurement of the other kind never changes what the window is.
* **Ruling:** Knut, 2026-09-23,
  [5787117741](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5787117741).
* **Built:** `ui/dialogs/measurement_report_dialog.py::_window_kind` asks
  `_bar_kind` (the profile bar through the window's parents); only a window
  with no bar falls back to the measurement (B8-812, commit 749fc27e). One
  press that would write both kinds is refused (B8-803, B8-811).
* **Verified by:** `tests/test_k24_the_bar_decides_the_kind.py::`
  `test_a_verification_bar_keeps_the_window_a_verification`,
  `test_a_profiling_bar_makes_a_profiling_window`;
  `tests/test_final_round_before_beta36.py::`
  `test_both_kinds_loaded_generate_is_refused_and_says_why`.
* **Proof:** `~/Desktop/ChromIQ-beta37-proof/report-folders/` (the K24 case in
  its REPORT.md) and `~/Desktop/ChromIQ-beta37-proof/fixes/f4-probe/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 13.11 Where a report lives, and which folders the list reads (K23, Knut 2026-09-23)

**✅ CONFIRMED.** **Ruled by:** Knut, #182 comments 5787117741
(the rule) and 5787380408 (accepting the proposal in 5787131342).
**Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
This records his ruling and what was built from it (B8-816), and he has
confirmed the built behaviour (K23, K25 Q2 and Q3, K9, K12).

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

  > **SUPERSEDED by K31 (§25, Knut, #182 [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743), beta 40).** A report of several measurements writes its one document
  > file and nothing into the measurements' folders: no verdict record, in
  > any run. The document file carries each measurement's verdict
  > (`judged`). Records an earlier ChromIQ wrote are read-only history
  > (§25.6). ⏳ Awaiting confirmation. **Confirmed by:** *nobody yet.*

  > **SUPERSEDED IN PART by G7 (§13.13, beta 39) for a report ACROSS
  > PLACES** (several profile runs, or several projects), after Knut's
  > 5773668311 and [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113): *"the report's own limit set applies to every
  > included measurement, whatever each run is bound to"*. Such a document
  > file also records each measurement's verdict against the report's set,
  > and the window's own run gets its record ONLY where the record cannot
  > contradict the run: a profiling sheet (no set grades it), or a date
  > whose run is judged by the same yardstick as the report. A date whose
  > run is bound to another set gets no record and keeps the verdict it has.
  > ⏳ Awaiting confirmation. **Confirmed by:** *nobody yet.*
* **What is listed and counted.** "Report shown" and "Already generated for
  this run" read the reports folders of the measurements in "Included
  measurements" of the profile bar's Run type, plus the two shared folders,
  where a document is taken only when it covers one of those measurements
  (compared from `runs/` down, so a moved project still finds it). A verdict
  record is never an entry and never counted.

  > **AMENDED by G7 (§13.13, beta 39), the folder across projects only.**
  > Compared from `runs/` down alone, a report of P/run1 and Q/run1 was also
  > offered in R/run1's window, because every project has a `runs/run1`.
  > A document in the folder across projects is now compared by project
  > name AND `runs/` path (every name the window's project has had, so a
  > renamed project still finds it), as §18.12 already compares a
  > calibration (Knut, [5794078008](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794078008): that list *"can only show reports belonging"*
  > to what is listed). A document inside a project is compared as before.
  > ⏳ Awaiting confirmation. **Confirmed by:** *nobody yet.*
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

  > **SUPERSEDED by K31 (§25, Knut, #182 [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743), beta 40).** An Update writes no record and moves, rewrites or
  > archives none; a measurement taken out of a report keeps its own
  > report of one date and nothing else; Delete moves the one document file
  > and leaves the dates as they are (there is nothing of the report in
  > them). A report of one date that an Update widens becomes a report of
  > those dates (§25.2). ⏳ Awaiting confirmation. **Confirmed by:** *nobody yet.*
* **Legacy.** Nothing is moved or rewritten by opening a project. A report of
  several dates written before this (one file per date, one id, no role) is
  listed and counted once, from the dates it covers. An Update of such a
  report writes it by this rule (its files archived first).
* **A report is shown whole (beta 37, challenge round A, F1).** A report
  selected in "Report shown", or the one the window opens on, that records
  measurements the window has not loaded, loads them into "Included
  measurements" before anything is drawn (found from `runs/` down, so a moved
  project finds them too; a folder no longer holding its measurement is left
  out). The page then shows every date the report covers, ~~and because the
  window now holds measurements from more than one place, Generate report is
  greyed with the several-places reason, and the handler refuses as well:
  an Update can no longer rewrite a report narrower than it is~~. Before this, a
  report across run1 and run2 opened from run2 showed one date, Generate said
  "Nothing was changed", and Update rewrote it about that one date.
  **SUPERSEDED by G7 (§13.13, beta 39; Knut [5794078008](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794078008) point 3 and [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)):** a
  report across places is written whole, so Generate is live over it and an
  Update rewrites it about every date it covers. ⏳ Awaiting confirmation. **Confirmed by:** *nobody yet.*

**Record (K23).**
* **Rule:** his folder rule quoted at the head of this section, for a
  verification and for a profiling run; the counted and listed reports come
  from the folders the measurements in "Included measurements" point to, of
  the Run type's kinds only. Each date keeps its own verdict record, never
  listed or counted; reports already on disk stay where they are and are shown
  and counted by what they cover (*"Yes, leave them where they are, and show
  and count them by what they cover."*). And his test requirement: *"Every
  setting, variety, type that may occur ... must be tested multiple times,
  using demo project data, on screen on real app, while monitoring what
  happens in files and locations"*.
* **Ruling:** Knut, 2026-09-23,
  [5787117741](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5787117741)
  and [5787380408](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5787380408)
  (accepting our 5787131342).
* **Built:** `workflow/measurement_report.py::document_home`,
  `shared_report_folders`; `core/file_manager.py::archive_report_files`; the
  list and line in `ui/dialogs/measurement_report_dialog.py`
  (`_saved_documents`, `_measurement_dirs_of_the_list`,
  `_load_the_documents_other_measurements`, `_drop_borrowed_sources`)
  (B8-816, commits 11cd81a3, 2dc9a43f; B8-818 A-F1; B8-825). The demo pack's
  Report-Limits-Report-Folders holds every combination.
* **Verified by:** `tests/test_k23_report_folders.py` (21 tests), among them
  `test_where_a_document_lives`,
  `test_several_dates_write_one_document_file_and_a_record_per_date`,
  `test_a_deleted_document_leaves_its_records_unlisted_and_uncounted`,
  `test_a_legacy_document_of_several_dates_counts_once_and_stays`,
  `test_a_cross_run_document_is_listed_where_it_covers_and_nowhere_else`,
  `test_update_to_one_date_retires_the_document_file_and_back`,
  `test_the_cross_run_path_a_profiling_window_has`;
  `tests/test_beta37_a_report_is_shown_whole.py::`
  `test_opening_run2_on_the_cross_run_report_loads_run1s_date`,
  `test_picking_the_report_in_the_list_loads_it_whole_and_writes_nothing`,
  `test_new_report_unloads_what_the_cross_run_report_loaded`.
* **Proof:** `~/Desktop/ChromIQ-beta37-proof/report-folders/`,
  `~/Desktop/ChromIQ-beta37-proof/fixes/`, `~/Desktop/ChromIQ-beta37-proof/r1-fixed/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (K25 Q2 and Q3: Update moves, Delete leaves the records).**
* **Rule:** an Update of a report of several dates written before K23 rewrites
  it in the new place and layout, its old files archived in `old/` first
  (*"Yes, update it."*). Delete Selected Report moves the report to `old/` and
  leaves each date's verdict record, because that record is the date's result
  (*"Yes."*).
* **Ruling:** Knut, 2026-09-23,
  [5789263863](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789263863)
  (the report-folder questions 2 and 3).
* **Built:** as described under "Update" and "Delete Selected Report" above.
* **Verified by:** `tests/test_k23_report_folders.py::`
  `test_update_rewrites_the_document_file_in_place_and_archives_it`,
  `test_a_deleted_document_leaves_its_records_unlisted_and_uncounted`,
  `test_a_legacy_document_of_several_dates_counts_once_and_stays`.
* **Proof:** `~/Desktop/ChromIQ-beta37-proof/report-folders/`.
* **Superseded in part by K31 (§25.1, Knut [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743)):** "leaves each
  date's verdict record" no longer applies to a report made from beta 40 on,
  which writes none. The confirmation below is of the rule as it was.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (K9: the PDF folder).**
* **Rule:** "Save report as PDF…" opens at the `reports/` folder the report's
  own measurements and the Run type decide, as the file-structure help card
  says; *"Make sure this is tested on screen on working app for all the levels
  the report feature should save reports and pdfs in."* The PDF folder follows
  where the document lives (this section).
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K9 of B8-778).
* **Built:** `ui/dialogs/measurement_report_dialog.py::_report_dir` and
  `_export_pdf`, which now logs the folder and the file (B8-794, commit
  1bd6ea22). A cancelled save leaves no empty folder behind (commit 78a4f00b).
* **Verified by:** `tests/test_the_report_reads_as_a_printed_document.py::`
  `test_a_report_of_several_profiling_runs_is_saved_in_the_projects_reports`;
  `tests/test_k23_report_folders.py::test_the_pdf_folder_agrees_with_where_the_document_lives`;
  `tests/test_k26_rulings.py::test_a_cancelled_pdf_save_leaves_no_reports_folder`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K9-pdf-folder/` (all four levels,
  on screen). Not driven: the OS-native save dialog, which no driver can
  operate; ChromIQ hands it the same folder.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (K12: the PDF name).**
* **Rule:** a PDF's suggested name carries the time of the report it is made
  from, never the previous PDF's: *"the pre-filled in name in the file dialog
  is the same as the previous PDF I created, even though the report I now made
  the pdf for has a different created time."* An updated report's name carries
  its last update.
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K12 of B8-778).
* **Built:** `ui/dialogs/measurement_report_dialog.py::_report_filename` reads
  the document's time (B8-783), and the page records which document it shows
  as it is drawn (B8-793 A-3, A-6).
* **Verified by:** `tests/test_measurement_report.py::`
  `test_the_pdf_name_carries_the_documents_time_not_the_windows`;
  `tests/test_generate_report_asks_what_to_do.py::`
  `test_after_an_update_the_pdf_is_not_offered_the_earlier_pdfs_name`,
  `test_a_page_that_is_no_longer_the_saved_document_takes_neither_its_time_nor_its_name`.
* **Proof:** no on-screen folder of its own; driven inside
  `~/Desktop/ChromIQ-beta36-proof/round-A-report-fixes/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 13.12 "Report shown" is grouped; the names stay (K25, Knut 2026-09-23)

**✅ CONFIRMED.** **Ruled by:** Knut, #182 comments 5789263863
(the K23 answers, Q1 to Q6) and 5789532633 (the correction: names stay, the
list is grouped). **Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
This records his ruling and what was built from it (B8-826), with the
amendments of §18.6 and §18.10, and he has confirmed the built behaviour.

> *"For both run type verification and run type profiling the report names
> keep their names, but are grouped according to which measurement sets have
> been added, where they come from, and what a report includes."*

What was built:

* **Names.** ~~Unchanged: "One date", "Multiple dates", "All dates" on every
  entry, profiling and verification alike.~~ **SUPERSEDED by K26 (§18.6): this
  bullet was a misreading.** His correction 5789532633 was about Run type
  Verification only; for Profiling his first message stood, and he said so
  plainly in 5792484060: *"No, both are used. I was very very clear about
  this"*. On a Profiling window the names are "Run1", "Run2", …, "Multiple
  runs", "All runs"; on a Verification window "One date", "Multiple dates",
  "All dates". The grouping below applies to both.
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

~~Open with Knut (B8-826)~~ **All four ANSWERED by Knut, 2026-09-23
([5792484060](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792484060)
and [5792576954](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792576954)),
built in §18:** "Reports including multiple runs" inside the project, *"That
is ok."*; a list is grouped from the start when a report it offers covers two
profile runs (§18.10); "for these measurements" on a Profiling window
(§18.7); a report across projects in `<output folder>/reports/`, a folder made
only by the first such report (§18.8). He also ruled (Q6) that no other
PROJECT is loaded: only the other project's measurements are added to
"Included measurements", and the report opens with the settings it was made
with. That is what "a report is shown whole" (§13.11) does.

**Record (K25, the list).**
* **Rule:** his words at the head of this section and in §18.6. Under Run type
  Verification: one run's measurements, flat, "One date" / "Multiple dates" /
  "All dates"; several runs of one project, grouped under `Run1`, `Run2`;
  several projects, the project name as main heading and `Run1`, `Run2` under
  it; a report including measurements of more than one project under
  "Reports including multiple projects". Under Profiling the same grouping,
  with the Run names of §18.6. *"For both run type=verification and run
  type=profiling the report names are grouped according to which measurement
  sets have been added, where they come from (location of files), and what a
  report includes"*. On a Profiling window, "Already generated…" and "Report
  shown" list and count every run's Printing records the included
  measurements point to; the report written at the end of a measurement covers
  that one measurement, and its graphs show the "at least two measurements"
  text (5789532633). M-REPORT-DELETE says "the measurement(s) it describes";
  "Where are my files" lists `verifications/reports/` and `<project>/reports/`.
* **Ruling:** Knut, 2026-09-23,
  [5789263863](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789263863)
  (Q1 to Q6), [5789532633](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789532633),
  and the corrections in 5792484060 and 5792576954 (§18.6, §18.10).
* **Built:** `ui/dialogs/measurement_report_dialog.py::_grouped_documents`,
  `_add_report_group_heading`, `_measurement_dirs_of_the_list`,
  `_open_on_the_latest_report`, `_load_the_documents_other_measurements`;
  `workflow/measurement_report.py::shared_report_folders` (B8-826, commits
  7566f20d to bb177b8f).
* **Verified by:** `tests/test_report_shown_is_grouped_by_run_and_project.py::`
  `test_one_run_is_not_grouped`, `test_several_runs_are_grouped_under_run_headings`,
  `test_a_heading_can_be_seen_and_not_chosen`,
  `test_several_projects_are_grouped_by_project_then_run`,
  `test_a_report_across_projects_is_counted`,
  `test_profiling_lists_and_counts_every_run_s_printing_record`,
  `test_a_profiling_window_opens_on_its_own_run_s_report`,
  `test_the_automatic_record_of_one_measurement_ticks_one`,
  `test_the_delete_message_says_measurement_s`,
  `test_the_file_guide_names_the_shared_report_folders`,
  `test_a_report_across_projects_loads_the_other_project_from_where_it_is_now`;
  `tests/test_trend_graphs_explain_themselves.py::`
  `test_one_measurement_still_shows_the_two_measurement_text`.
* **Proof:** `~/Desktop/ChromIQ-beta38-proof/report-list/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).


### 13.13 Reports across profile runs and across projects (G7, beta 39)

#### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* The RULES are Knut's and confirmed; what
follows is what was BUILT from them, driven on screen
(`~/Desktop/ChromIQ-beta39-proof/g7/`), and it waits for him to say that it
is what he meant. Registered as B8-848.

> *"a user may need to see how a printers profile has changed across
> different periods that are saved as different projects"* (Knut,
> [5794078008](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794078008), point 3)
>
> *"Yes, I confirm 'the report's own limit set applies to every included
> measurement, whatever each run is bound to.'"* (Knut, [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113))
>
> *"The project across both profile runs' verification measurements have
> only one defined limit set ... The same settings are used in that report
> to check the metrics for the selected measurements to include, even if
> the measurements belong in separate profile runs dated verification
> runs."* (Knut, [5773668311](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5773668311))

What was built:

* **A report across places.** The ticked measurements live in more than one
  PLACE: a profile run (its own sheet and its dated verifications are one
  place) or a project's calibration. Several dates of one run are one place,
  as before (K23).
* **Generate is live** with several places loaded, under Verification,
  Profiling and Calibration. The two several-places sentences on the button
  are gone. It still refuses, and says why, when: a ticked measurement is
  outside a ChromIQ project ~~or the projects are in two folders~~ (Knut names
  ONE folder for a report across projects, `<ChromIQ default
  folder>/reports/`; **SUPERSEDED by K30 (§24.4): projects in two folders are
  no longer refused, their report goes to `<ChromIQ folder>/reports/`**);
  every ticked measurement belongs to another place (a
  report of that place alone belongs to that place's own window, whose run
  type and set it would be filed under); a profiling sheet and verifications
  are ticked together (FC-2, unchanged); under Calibration, a ticked
  measurement is not a project's calibration.
* **One limit set, the report's own:** the "Judged against" choice. Every
  included measurement is judged against it, whatever its run is bound to.
  Nothing is left out for having been judged against another set
  (`_one_limit_set` does not narrow across places).
* **Where it is written** (K23/K25, as built): several runs of one project,
  `<project>/reports/`; several projects (runs or calibrations), the folder
  across projects (`<ChromIQ folder>/reports/`), made by the first such
  write and not before.
* **What is written.** One document file. Each measurement entry in its
  block carries `judged`: that measurement's verdict against the report's
  set (`pass_thresholds`, `compliance`, `verdict`, as a saved report carries
  them). The page of a saved report across places shows those words and
  never recalculates them.
* **The dated per-date verdict records.** A record in a measurement's folder
  is that measurement's result (§5): the lock, the trend, the newest-file
  choice and the delete rule read it there. So a record is written only into
  the window's own run, and only where it cannot contradict the run: a
  profiling sheet (no set grades it, §3), or a date whose run is judged by
  the same yardstick as the report. A date whose run is bound to another set
  gets none and keeps its own recorded verdict. Nothing is written into
  another run's folder, and nothing into any `cal/` for a report across
  projects. No run is bound, re-bound or unlocked by any of this.

  > **SUPERSEDED by K31 (§25, Knut, #182 [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743), beta 40).** No record is written into any folder, the window's own
  > run included: Knut, *"When a report covers more than one run or
  > project, should GENERATE REPORT write anything into the dates' own
  > folders? Answer: no."* ⏳ Awaiting confirmation. **Confirmed by:** *nobody yet.*
* **Update, Create New, Delete, archiving** as before, all or nothing:
  Update rewrites the document file in place with its previous content in
  `reports/old/<stamp>/` first (D23), or moves it when its home changes;
  Delete moves it into `old/<stamp>/` beside its folder; the dates keep
  their files. A report across places written before beta 39 (verdict
  records in each date) is shown from its records until it is updated; an
  Update writes it by this rule, re-stamping its records' document block
  (their verdicts untouched, archived first).
* **Listing and counting** as built for K23/K25: under "Reports including
  multiple runs" or "Reports including multiple projects", counted in
  "Already generated". A report in the folder across projects is offered
  only in a window whose list it covers by project name and `runs/` path
  (the leak fixed in §13.11's amendment).
* **The limit-set controls with several places loaded.** "Judged against"
  is live: it chooses the report's own set and binds no run, even when a
  run among the places is locked; its tooltip says so. ~~"Show limits…" and
  "Unlock this run's limits" stay greyed with their existing sentences:
  limits are edited, and a lock lifted, for one profile run at a time.~~
  **SUPERSEDED by K30 (§24.3, Knut 5798461562):** the limits button is live
  and edits the REPORT's own limits ("This report"); "Unlock this run's
  limits" stays greyed. ⏳ Awaiting confirmation. **Confirmed by:** *nobody yet.*
  **SUPERSEDED by K31 (§25.3, §25.4):** the same with ONE profile run
  loaded, and "Unlock this run's limits" is removed. ⏳ Awaiting confirmation.
  **Confirmed by:** *nobody yet.*
* **One measurement, one row.** A profiling sheet gathers every run's sheet
  of its project; a second source that gathers a sheet already loaded no
  longer lists it twice.

Record (G7).
* **Rule:** his words at the head of this section.
* **Ruling:** Knut, [5773668311](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5773668311) (2026-09-22), confirmed
  [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113) (2026-09-23); [5794078008](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794078008) point 3 (2026-09-23).
* **Built:** `workflow/measurement_report.py::document_spans_places`,
  `across_places_refusal`, `JUDGED_KEY`, `judged_block`,
  `recorded_judgement`, `shared_documents` (with `_named_coverage_key`);
  `ui/dialogs/measurement_report_dialog.py::_spans_places`,
  `_judged_by_the_document`, `_judged_live`, `_records_across_places`,
  `_reports_to_generate`, `_write_the_document`, `_on_generate_report`,
  `_on_set_chosen`, `_sync_limit_controls`, `_sync_type_combo`,
  `_one_limit_set`, `_append_source` (B8-848).
* **Verified by:** `tests/test_g7_reports_across_places.py` (8 tests, each
  red on the mutation in its docstring):
  `test_a_report_across_two_runs_is_one_document_judged_by_its_own_set`,
  `test_a_date_whose_run_has_the_reports_set_keeps_its_record`,
  `test_the_saved_report_shows_the_verdicts_it_recorded`,
  `test_a_report_across_projects_lives_in_the_folder_across_them`,
  `test_projects_in_two_folders_share_the_chromiq_folder` (renamed and retargeted by K30, §24.4),
  `test_update_and_delete_of_a_report_across_projects`,
  `test_a_calibration_report_across_projects`,
  `test_a_sheet_another_source_gathers_again_is_one_row`; and
  `tests/test_report_window_limit_controls.py::`
  `test_two_runs_loaded_the_pulldown_chooses_the_reports_set`,
  `tests/test_the_report_type_pulldown_stores_on_the_run.py::`
  `test_with_two_runs_ticked_generate_is_live`,
  `test_a_greyed_generate_says_why_when_only_another_run_is_ticked`,
  `tests/test_beta37_a_report_is_shown_whole.py::`
  `test_update_of_the_cross_run_report_keeps_both_dates`.
* **Proof:** `~/Desktop/ChromIQ-beta39-proof/g7/` (REPORT.md, photographs,
  the folders listed before and after every press).
* **Status:** rule agreed and confirmed; the built result ⏳ awaiting
  confirmation. **Confirmed by:** *nobody yet.*

### 13.14 What a rename, a run delete and a read-only folder do to saved reports (challenge C, beta 39)

#### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* No rule of Knut's covers these cases; what
follows is the obviously safe behaviour that was BUILT after tester C of
beta 39 found it missing (`~/Desktop/ChromIQ-beta39-proof/challenge-C-files/
REPORT.md`, items 1, 2, 3, 4, 7, 8 and 11), driven on screen before and after
(`~/Desktop/ChromIQ-beta39-proof/challenge-C-fixes/`). Registered as B8-870
to B8-873. Every point is a question for Knut.

What the tester measured, on the demo pack:

* an **Update** of a report across projects, from the side that could not
  find one of its measurements (the other project renamed), archived the
  whole report and rewrote it about the one date it had found (§13.13 says
  an Update rewrites it about every date it covers); a date whose `.ti3` was
  deleted did the same, and one such date retired a report across projects
  into a one-date report;
* after a **rename**, the reports in `<ChromIQ folder>/reports/` kept the
  old folder name: the other side showed "1 of the 3", calibration reports
  1 cal, and the renamed side's Report Scope named the chart by its old name;
* the bar's **Delete of a profile run** renumbered the later runs and
  rewrote their `meta.json` only: a one-run record of run 3 (now run 2) was
  listed as "Multiple runs", an All runs report found "1 of the 5";
* **Delete Selected Report** in a read-only folder copied the report into
  `old/` and left the original, under a raw "[Errno 13] Permission denied";
  **Update** there said only "The log says why."

What was built:

* **An Update never drops a covered measurement in silence.** Before it
  writes, it compares what the report records with what the press would
  cover (`workflow.measurement_report.update_losses`). A recorded
  measurement it cannot find because its PROJECT cannot be found refuses the
  press, writes nothing, and names each measurement and why
  (M-REPORT-UPDATE-NOT-FOUND). A measurement whose project is there but whose
  run was deleted, whose dated folder is gone or whose `.ti3` is gone (§13.11
  leaves such a folder out) is ASKED about (M-REPORT-UPDATE-LEAVES-OUT,
  Cancel the default); "Update without them" writes the report without them,
  archived first as every Update is. A measurement that is found and merely
  not ticked is left out as before: that is the user's choice.
* **A rename rewrites every report that names the project.** `Project.rename`
  (the name field's rename and the folder-renamed window, B8-841, both end
  there) rewrites, in the project's own reports, the folder across projects
  beside it and the reports of the projects beside it, exactly the
  references to the project: the recorded folders and keys of each
  `document.measurements` entry, and in the project's own reports the `ti3`,
  `chart` and `profile` stems (`core.report_refs`). All or nothing,
  archiving nothing, each file's modification time kept (the window decides
  which report is the newest by it). A report outside the project is not
  rewritten for a name that another project beside it still has: that is a
  Finder duplicate's original, and those reports are its own.
* **A renamed project is found by its former name.** A report the rename did
  not rewrite (written before this, or in a folder ChromIQ may not write)
  still names the old folder; `resolve_recorded_folder` now also looks for
  the ONE project beside the report's projects that has that name in its
  `former_names` (none when two claim it).
* **The Scope names the chart by the project's current name**
  (`current_chart_name`): a name that starts with one of the project's
  former names is printed with the current one.
* **A run delete renumbers the reports with the runs.** Every report of the
  project, the folder across projects beside it and the projects beside it
  that names a run by number is rewritten with `meta.json`: `runs/run3`
  becomes `runs/run2`, and a reference to the DELETED run becomes
  `runs/run2.deleted`, which is on no disk, so it can never point at the run
  that took its number (an Update of that report then says "its profile run
  was deleted"). Checked writable before anything moves; a report that could
  not follow refuses the delete with nothing changed.
* **Delete Selected Report is all or nothing** (`move_report_files`): every
  source folder and the destination are asked first, and a step that fails
  anyway puts back what moved and removes the folders it made; the window
  says which folder and what to do (M-REPORT-DELETE-FAILED).
* **A refused Update or Generate names the folder** it may not write in and
  the remedy (M-REPORT-NOT-WRITABLE). A failure that is not a folder
  ChromIQ may not write in keeps the older sentence.
* Nothing under an `old/` folder is ever rewritten: an archive is history.

What re-challenge R1 of beta 39 then found, and what was changed
(`~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-behaviour/REPORT.md` items 1,
2, 4 and 6; `~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-fixes/`; B8-916,
B8-918 and B8-919):

* **A reference is rewritten only when it names THIS project.** Matching by
  name alone reached other projects: a run deleted in a renamed Finder
  duplicate renumbered 14 reports of its original, and a run deleted in a
  renamed project renumbered all 30 reports of a new project that had taken
  its former name. A run delete and a rename now rewrite a reference only
  when the app's own reading of it (`resolve_recorded_folder`, seen from
  where the report's file is: the project it is inside, or the folder across
  projects) lands inside the project being changed; outside the project, a
  name that another existing project folder beside it holds is never used to
  match, whatever `former_names` says. The same rule keeps a rename of an
  original from rewriting the reports inside its Finder duplicate.
* **An Update never writes a report that covers nothing.** "Update without
  them" was offered even when EVERY measurement of the report was gone, and
  wrote the report with an empty list under its old verdict and scope. The
  press is now refused before anything is written
  (M-REPORT-UPDATE-NOTHING-LEFT, which names Delete Selected Report and
  Create New), and a document that records no measurement (only a build
  before this one wrote one) carries "covers no measurement" in its name.
* **A project moved into a sub-folder of the ChromIQ folder is still
  found** (the choice made between the two the round offered: resolve it, or
  show it as missing). §24.4 lets projects live in sub-folders of the ChromIQ
  folder, and a report across projects names the other project where it
  was: moved into `Group/`, it loaded 1 of its 2 dates with no note and
  Generate said "Nothing was changed". `resolve_recorded_folder` now also
  searches the ChromIQ folder and its sub-folders, one level down, for the
  ONE project that answers to the recorded name (its folder, its files or a
  former name); two that answer are neither, and the Update is then refused
  as for a project that cannot be found (M-REPORT-UPDATE-NOT-FOUND). The
  moved project's measurement is then ticked as well: a recorded key that
  matches no row is read the same way and matched by folder and creation
  stamp (`_recorded_keys_where_they_are_now`), where before only a report
  none of whose keys matched was mapped.
* **The ChromIQ folder's `reports/` follows a rename and a run delete too**
  (B8-920, the beta 39 help audit). A report across projects in two
  folders lives there (§24.4), and it was searched only when it happened to
  be the folder beside the project, so a project in a sub-folder (or
  outside the ChromIQ folder) left it naming its old folder and its old run
  numbers. It is now searched with the others, under the same rule: a
  reference is rewritten only when it resolves to this project, never when
  its recorded folder is another existing project.

**DECIDED (Knut, 2026-09-24, [5817809396](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817809396), answering A3 to A7 of
5802027116: *"the recommended is accepted"*).** Question 1 (A3): refuse, as
built. Question 2 (A4): ask, as built. Question 3 (A5): yes. Question 4 (A6):
add the Scope line, built for beta 42 (§31.1, B8-1011). Question 5 (A7):
refuse, as built. These are decided rules; the built behaviour still waits for
his confirmation. Questions 6 and 7 were not in that post and stay open.

Questions for Knut (1 to 5 decided above):

1. An Update whose covered project cannot be found is REFUSED outright, with
   no "update without it" button, because a report across projects would
   otherwise be narrowed from the side that happens not to see the other
   project. Is refusing right, or should the user be offered the choice as
   for a deleted measurement?
2. A measurement gone from disk (its run deleted, its folder or `.ti3`
   removed) is left out of an Update only when the user says so. Is the
   question right, or should §13.11's "left out" apply without asking?
3. A rename rewrites the reports of OTHER projects (the verdict records of
   a report across projects) and of the folder across projects, touching
   only their references to the renamed project. Is that acceptable, given
   that §13.13 otherwise writes nothing into another project's folder?
4. A reference to a deleted run becomes `runs/runN.deleted`. Should the
   report instead be told the run is gone in some other visible way (a note
   in its Scope)?
5. A run delete is refused when a report that must be renumbered cannot be
   written. Is that right, or should the run be deleted and the report left
   naming the old number?
6. A report whose every measurement is gone cannot be Updated at all; the
   window offers Delete Selected Report and Create New. Is that right, or
   should the Update be allowed to keep it as a record of what it was?
7. A project moved into a sub-folder of the ChromIQ folder is found by its
   name, one sub-folder level down, when exactly one project answers to it.
   Should the search go deeper, or should a moved project instead be shown
   as missing with the reason?

Record (challenge C, beta 39).
* **Rule:** none of Knut's covers these cases; this is the safe behaviour,
  awaiting his ruling on the five questions above.
* **Built:** `core/report_refs.py`; `core/file_manager.py::Project.rename`
  (`_rename_report_references`), `move_report_files`;
  `core/run_delete.py::delete_run`; `workflow/measurement_report.py::
  update_losses`, `resolve_recorded_folder` (step 3b), `current_chart_name`,
  `report_scope`; `workflow/measurement_messages.py` (the four messages,
  `report_gone_line`); `ui/dialogs/measurement_report_dialog.py::
  _update_leaves_out`, `_ask_leave_out`, `_on_delete_report`,
  `_say_generated` (B8-870 to B8-873).
* **Verified by:** `tests/test_challenge_c_report_files.py` (11 tests, each
  red on the mutation in its docstring).
* **Proof:** `~/Desktop/ChromIQ-beta39-proof/challenge-C-fixes/`.
* **Status:** ⏳ awaiting confirmation. **Confirmed by:** *nobody yet.*

Record (re-challenge R1, beta 39).
* **Rule:** none of Knut's covers these cases; the safe behaviour, awaiting
  his ruling on questions 6 and 7 above.
* **Built:** `core/report_refs.py::refers_here` (used by
  `run_references_plan` and `rename_references_plan`);
  `workflow/measurement_report.py::resolve_recorded_folder` (step 3c,
  `_projects_in_the_chromiq_folder`); `workflow/measurement_messages.py`
  (M-REPORT-UPDATE-NOTHING-LEFT); `ui/dialogs/measurement_report_dialog.py::
  _update_leaves_out`, `_write_the_document`, `_document_label`,
  `_recorded_keys_where_they_are_now` (B8-916,
  B8-918, B8-919).
* **Verified by:** `tests/test_r1_report_references_follow_the_project.py`,
  `tests/test_r1_an_update_never_writes_a_report_of_nothing.py`,
  `tests/test_r1_a_moved_project_is_found_in_the_chromiq_folder.py`, each red
  on the mutation in its docstring.
* **Proof:** `~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-fixes/`.
* **Status:** ⏳ awaiting confirmation. **Confirmed by:** *nobody yet.*

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
it with; the row is judged from the second measurement onward"*; **since
beta 39 it ends at "nothing to compare it with"**, §22.7), so no new
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

**✅ CONFIRMED.** **Ruled by:** Knut, 2026-09-22, on issue #182
(comment 5785774676), answering the F1 analysis
(`~/Desktop/ChromIQ-beta36-proof/F1-evenness/REPORT.md`) and Basti's reply
5785894881. **Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
This section records the method he ruled and what was built from it (B8-814),
and he has confirmed the built behaviour (§16 and §16.5b). His eight questions
below were answered on 2026-09-23 except E8, which he answered the same
day (5795087247, *"Yes"*): evenness is judged in absolute Lab whatever the
print's intent. That answer supersedes one clause of item 1 of §16.1 and is
recorded in §21.1.

### 16.1 The method

For one measured sheet:

1. **Every patch against its own expected colour.** The residual is the
   measured Lab minus the aim Lab the ΔE00 rows already use, ~~in the same
   yardstick (absolute, or media-relative where the report normalises)~~
   **SUPERSEDED by E8** ([5795087247](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5795087247), §21.1): the
   readings are always as measured (absolute Lab); on a sheet the report reads
   media-relative, the aims are carried onto the paper instead. And
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
   (**The two names are SUPERSEDED by §26.3:** "Maximum ΔE00, between two of
   the nine sheet areas" and "Maximum ΔE00, one sheet area against the whole
   sheet".)
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
sure though"*) and then ruled on 2026-09-23 (E7, 5789263863: *"confirmed."*),
so the NUMBER is agreed; the built behaviour still waits, as everywhere here.
The three ChromIQ sets carried half and double (0.75 / 0.5, 3.0 / 2.0) until
E3 (**superseded**, 5789263863: *"Yes"* to 1.5 / 1.0 in all three). The reason the two differ:
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

**✅ Confirmed (beta 37, challenge rounds A F3 and B H2/M7).**
**Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)),
as part of §16's noise guard and cause notes. The noise note used to say "the measured
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
  (held to a real build by a test). ~~A printtarg preset has no grid until
  printtarg runs and says so (`evenness_laid_out_later`).~~ **SUPERSEDED by
  K40-1 (§36.1):** every preset is laid out behind the scenes the way
  Generate lays it out, a printtarg preset by printtarg itself. The noise cannot be
  known before printing, so these two windows use an **estimate for a typical
  print**: a residual of 1.1 per L\*, a\*, b\* component, calibrated so the
  estimate reproduces the F1 real sheet's noise (1.41 at 30 patches per area),
  and say it is an estimate. The pre-flight, which knows no set yet, asks
  against the loosest limit any set puts on the row.
* **The star is not decided by these rows** (question E4 below).

### 16.5 Questions for Knut

**All eight ANSWERED on 2026-09-23**
([5789263863](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789263863)),
except E8, whose decision waits on research (§16.6). His answers, in short:
E1 *"a page under 9 × 9 is left out and the other pages are judged"*; E2 yes,
from the "Measured from Preview" margins (§16.6); E3 *"Yes"*, 1.5 / 1.0 in all
three ChromIQ sets; E4 *"No"*, the rows do not take the star, check an i1Pro 3
Plus multi-page preset (§16.6); E5 *"I do not have any other numbers"*, so the
Custom columns keep 1.5 / 1.0; E6 *"Yes"*, the rows stay in the read-only ISO
columns, filled by the file round trip; E7 *"confirmed"*; E8 *"Do an
investigation to see what is normal practice."* The questions as they were put
follow.

* **E1. A short last page.** "At least 9 columns and 9 rows per page": built
  as "a page under 9 by 9 is left out and the chart is judged on the rest",
  and the report names the pages left out. Or should such a page refuse the
  whole chart?
* **E2. The 75 % page coverage requirement** (5744704621 requirement 2,
  answered in 5745765820 item 3) is not in the rulings of 2026-09-22 and is
  not built. A `.ti2` records the paper size but not where the patch block
  sits. Is it still wanted? **ANSWERED by Knut: yes, at 75 % (5789539407),
  then lowered to 60 % (5792912682). Built, §16.6.**
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

### 16.5b Records of the evenness rulings

**✅ Confirmed.** **Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)),
for the three records below.

**Record (the method, F1 answers 1 to 5).**
* **Rule:** each patch against its own expected colour, averaged per area
  (*"yes, do it"*); no verdict while the sheet's own noise (95th percentile) is
  not below the limit, not the stricter half-limit version (*"Your suggestion
  is good. Do not use the stricter version."*); keep 9 by 9, *"so dividing
  into areas is good to show which area of the page gives an out of accepted
  (or normal) results"*; 1.5 pairwise; notes on likely causes *"in the help
  text, but also as notes on the results in the report text, for any report
  type that has enabled this metric"*; and *"This feature must be implemented
  all the places where metrics are judged, like the Create Chart button 'Which
  presets can be used for verification', the warning popup message when
  entering Measure tab, and the measurement report etc."*
* **Ruling:** Knut, 2026-09-22,
  [5785774676](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5785774676),
  on the analysis in 5784750595; the earlier rulings of 5745765820 (remainder
  to the middle band, pages pooled).
* **Built:** `workflow/measurement_report.py::evenness_from_residuals`,
  `evenness_block`, `evenness_withheld`, `EVENNESS_MIN_GRID`,
  `EVENNESS_SHUFFLES`, `EVENNESS_SEED`; the presets window and pre-flight
  through `workflow/preset_eligibility.py` (B8-814, commit 63aafc37; the noise
  note B8-818).
* **Verified by:** `tests/test_evenness_across_the_sheet.py` (26 tests), among
  them `test_the_remainder_goes_to_the_middle_band`,
  `test_the_positions_come_from_the_chart_and_not_from_the_file_order`,
  `test_a_gradient_across_the_sheet_fails_the_pairwise_row_first`,
  `test_one_area_off_fails_the_from_mean_row_first`,
  `test_a_noisy_sheet_is_not_judged_and_says_its_noise`,
  `test_the_noise_rule_is_strictly_below`, `test_the_noise_is_reproducible`,
  `test_the_causes_note_is_customer_text`,
  `test_the_report_names_the_area_by_the_labels_printed_on_it`,
  `test_the_predicted_grid_is_the_grid_the_engine_builds`;
  `tests/test_beta37_evenness_noise_is_not_a_patch_count.py::`
  `test_the_noise_note_names_the_noise_and_the_limit_and_no_patch_count`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/F1-evenness/` (the analysis),
  `~/Desktop/ChromIQ-beta37-proof/evenness/` (on screen),
  `~/Desktop/ChromIQ-beta37-proof/fixes/` (the noise note, English and German).
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (9 by 9 stays).**
* **Rule:** *"First I would like to using 12x12 ... but then I see that the
  i1Pro 3 Plus charts have 11 x 14 charts. Thus 9x9 as minimum it must be."*
* **Ruling:** Knut, 2026-09-23,
  [5787380408](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5787380408).
* **Built:** `EVENNESS_MIN_GRID` = 9, one constant.
* **Verified by:** `tests/test_evenness_across_the_sheet.py::test_nine_by_nine_is_the_floor_exactly`;
  `tests/test_beta38_evenness_page_coverage.py::test_the_grid_floor_is_asked_first`.
* **Proof:** `~/Desktop/ChromIQ-beta37-proof/evenness/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (E1, E3, E4, E5, E6, E7).**
* **Rule:** E1 a page under 9 by 9 is left out and the other pages judged; E3
  1.5 / 1.0 in ChromIQ default, tight and Quick check (**supersedes** half and
  double); E4 the rows never take a preset's star, the feedback says which
  metrics a chart can and cannot answer; E5 the Custom columns start from
  1.5 / 1.0; E6 both rows stay in the read-only ISO columns, with no number
  until a licence holder's file supplies one; E7 1.0 on the from-the-mean row.
* **Ruling:** Knut, 2026-09-23,
  [5789263863](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789263863).
* **Built:** `workflow/compliance_sets.py` factory limits (commit 86083f46 for
  E3); `evenness_from_residuals` for E1; `workflow/preset_eligibility.py` for
  E4.
* **Verified by:** `tests/test_evenness_across_the_sheet.py::`
  `test_a_short_last_page_is_left_out_not_fatal`,
  `test_the_limits_knut_gave_and_the_half_and_double_rule` (it asserts 1.5 /
  1.0 in all five editable sets and nothing in the two read-only ones, despite
  its name), `test_a_preset_not_laid_out_yet_says_so_and_keeps_its_star`,
  `test_the_rows_are_computable_under_their_own_heading`.
* **Proof:** `~/Desktop/ChromIQ-beta37-proof/evenness/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 16.6 Beta 38: page coverage (E2), the i1Pro 3 Plus case (E4), the yardstick research (E8)

**✅ CONFIRMED (E2 and E4).** **Confirmed by:** Knut, 2026-09-23 (#182
comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
E8 was research only here; Knut answered it the same day (5795087247,
*"Yes"*), built in beta 39 and recorded in §21.1.
**Ruled by:** Knut, 2026-09-23 (5789263863 E2, E4, E8; E2 approved at 75 % in
5789539407, then **lowered to 60 %** in
[5792912682](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792912682):
*"lower the threshold to 60%. instrument's minimum margins are general rules
that not always works."*; the E4 chart named in 5792928823).
Registered as B8-828 (E2), B8-829 (E4) and B8-830 (E8).
Proof: `~/Desktop/ChromIQ-beta38-proof/evenness-followups/` (built at 75 %)
and `~/Desktop/ChromIQ-beta38-proof/evenness-60/` (at 60 %).

**E2, built.** A page counts for evenness only when it has at least 9 strips
and 9 rows AND its patch block covers at least
`measurement_report.EVENNESS_MIN_PAGE_COVERAGE` (**0.60**, one constant; it
was 0.75 until Knut's 5792912682) of the paper:

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
| pages of 9 by 9 exist, none covers 60 % | `evenness_page_coverage_too_small`: *"the patches on page N of the measured chart cover X % of the page; at least 60 % is needed"* (several pages: *"pages 1, 2 … cover at most X % of their page"*). X is rounded DOWN to one decimal, so 59.96 % reads 59.9; the floor reads "60" |
| exactly 60 % | counted (the floor is inclusive) |
| no file says where the patches sit | `evenness_no_page_geometry`: *"no file of the measured chart records where its patches sit on the page, so how much of the page they cover is not known"*. A file reason: left off the strip |
| some pages pass, some do not | the others are judged; the notes name each page left out and why |

The presets window and the pre-flight read the same arithmetic, with the
lines *"On no page of this chart with at least 9 strips and 9 rows do the
patches cover at least 60 % of the page."* and *"This chart's files do not
record where its patches sit on the page, …"*. Neither takes the star (a
layout shortfall). M-REPORT-CHART-MISMATCH-LAYOUT now ends "…and with patches
that cover most of the page" (PROPOSED). The help text quotes the 60 %.

**What it does to the built-ins, measured (engine presets, 172):**

| floor | refused by coverage | refused by the grid first | pass both floors |
|---|---|---|---|
| 75 % (as first built) | 123 | 12 | 37 |
| **60 % (Knut, 5792912682)** | **4** | **12** | **156** |

At 60 % the four refused by coverage are the half-page i1Pro charts (312
patches on A4 and Letter at 8 mm, 324 at 7.5 mm): 12 strips by 26 rows on the
left half of the page, 34 to 37 % covered. Knut's own 572-patch i1Pro A4
chart covers **68.4 %** (margins 26.0 / 6.0 / 38.2 / 19.1 mm) and is now
counted. Passing both floors is not yet being judged: the noise rule (§16.1)
still asks for enough patches in each ninth.

**E4, checked.** Knut's chart is the 11 by 14 one (5792928823). The 24 i1Pro
3 Plus presets are 11 strips by **14** rows (A4), 11 by **13** (Letter), 16 by
21 (A3) and 7 by 12 (the two 84-patch charts). Their own margins (28 mm clip
band, 40 top, 20 bottom, 10 right) leave 65.3 % of an A4 page, 64.6 % of a
Letter page and 74.7 % of an A3 page, all over 60 %, so at 60 % **Knut's
expectation holds**, against ChromIQ default (1.5 / 1.0):

| preset | pages | evenness rows | why |
|---|---|---|---|
| A4 and Letter, 84 patches | 1 | N-A | 7 strips, under the 9 by 9 grid |
| A4 154, Letter 143 | 1 | N-A | about 17 patches in each ninth; a typical print's noise is 2.0 / 1.2 |
| A4 308 to 2002, Letter 286 to 2002 | 2 to 14 | answered | the same ninth of every page counted together: noise 1.39 / 0.84 at two pages, falling |
| A3 336 | 1 | answered | 16 by 21, 35 patches in each ninth: noise 1.24 / 0.75 |
| A3 672 to 2016 | 2 to 6 | answered | |

20 of the 24 answer both rows; the four refused are all one-page charts.
`tests/test_beta38_i1pro3plus_evenness.py` pins each preset's grid, coverage,
estimated noise and answer.

**E8, researched here; answered and built in beta 39 (§21.1).** The published uniformity tests (ISO 12647-7
§4.3.3, ISO 12647-8 §4.2.2.1, Idealliance) compare absolute CIELAB readings of
the same patch at different places on one sheet; none normalises to paper
white. The recommendation (judge evenness in absolute Lab whatever the other
rows use) waits for Knut. Findings:
`~/Desktop/ChromIQ-beta38-proof/evenness-followups/E8-research.md`.

**Questions for Knut (beta 38):**

* **E2/E4-a.** Answered: 60 % (5792912682).
* **E4-b.** Answered: the 11 by 14 chart (5792928823).
* **E8.** Judge evenness in absolute Lab always? **Answered: "Yes"
  (5795087247), §21.1.**

**Record (E2, page coverage).**
* **Rule:** a page counts for evenness only when its patches cover at least
  **60 %** of it, computed from the four "Measured from Preview" margins
  (*"Could the Measured from Preview numbers be used to calculate, so that
  these things are not re-measured on-screen? 9 strips and 9 rows may still
  cover just a limited part of a page, thus the uniformity test has limited
  value."*; *"Yes"*; then *"lower the threshold to 60%. instrument's minimum
  margins are general rules that not always works."*). The report, the presets
  window and the pre-flight ask the same floor.
* **SUPERSEDED:** the 75 % floor of 5789539407, built first (commit bbeb82b7),
  which shut out 123 of 172 built-in engine presets.
* **Ruling:** Knut, 2026-09-23,
  [5789263863](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789263863) (E2),
  [5789539407](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789539407) (75 %),
  [5792912682](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792912682) (60 %).
* **Built:** `workflow/page_coverage.py`;
  `workflow/measurement_report.py::EVENNESS_MIN_PAGE_COVERAGE` (0.60, one
  constant) in `evenness_from_residuals`; the reasons
  `evenness_page_coverage_too_small` and `evenness_no_page_geometry`
  (B8-828, commits bbeb82b7, c0a319b0).
* **Verified by:** `tests/test_beta38_evenness_page_coverage.py::`
  `test_knuts_formula_on_the_margins`, `test_the_floor_is_60_percent_and_inclusive`,
  `test_the_floor_is_one_constant`,
  `test_an_uncovered_page_is_left_out_and_the_others_judged`,
  `test_a_chart_with_no_page_geometry_is_na_and_stays_off_the_strip`,
  `test_the_note_names_the_page_and_its_share_rounded_down`,
  `test_a_built_chart_reads_what_measured_from_preview_shows`,
  `test_a_dated_snapshot_borrows_the_live_charts_pages_only_if_identical`,
  `test_the_presets_window_and_the_preflight_ask_the_same_floor`,
  `test_the_built_in_engine_presets_against_the_60_percent_floor`,
  `test_the_help_text_quotes_the_floor`.
* **Proof:** `~/Desktop/ChromIQ-beta38-proof/evenness-60/` (60 %) and
  `~/Desktop/ChromIQ-beta38-proof/evenness-followups/` (75 %, superseded).
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (E4, the i1Pro 3 Plus case).**
* **Rule:** *"It is likely a one page target will not fulfil the requirement,
  but a multipage preset should then be possible to use. This should be
  checked and verified as a separate case"*; the chart is the 11 by 14 one.
* **Ruling:** Knut, 2026-09-23,
  [5789263863](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789263863),
  [5792928823](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792928823).
* **Built:** no code of its own; answered by the 60 % floor (B8-829).
* **Verified by:** `tests/test_beta38_i1pro3plus_evenness.py::`
  `test_each_presets_grid_and_coverage_as_predicted`,
  `test_each_presets_estimated_noise_on_a_typical_print`,
  `test_a_one_page_i1pro3plus_chart_fails_and_a_multi_page_one_answers`,
  `test_the_family_splits_four_refused_twenty_answering`,
  `test_a_real_build_agrees_with_the_prediction`.
* **Proof:** `~/Desktop/ChromIQ-beta38-proof/evenness-60/`.
* **Status:** agreed; the checked result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

**Record (E8, the yardstick).** Research done here; **superseded by the
record in §21.1**, which builds his answer. As it stood in beta 38: the
published tests compare absolute CIELAB, and the recommendation to judge
evenness in absolute Lab always waited for Knut's decision (B8-830,
`~/Desktop/ChromIQ-beta38-proof/evenness-followups/E8-research.md`). Listed as
G8 in §20.

## 17. Trend graphs for the judged metrics (#182 K20/K21, 2026-09-23)

### ✅ Confirmed behaviour

**Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

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

   (**The tab names "Paper white, diff", "Tone (ΔL*)" and "Cube corners",
   the legend "Black L\*" and the line word "Pairs" are SUPERSEDED by §26.3:**
   "Paper white difference (ΔE00)", "Tone ramps 30 to 70 % (ΔL*)", "Cube
   corners (ΔE00)", "Darkest black L\*", "Areas"; the row names are the
   version 1 names.)
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
   *(The placement is SUPERSEDED by §28.5, Knut's K32 ruling of
   2026-09-24: each word is placed on its own.)*
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

**Record (K20/K21).**
* **Rule:** a trend graph is shown, and printed, only for metrics that have
  values tested against a threshold: *"a graph is only shown and printed IF the
  metric has values tested agains a threshold."* Each metric that benefits gets
  a graph, *"each group show maximum two metrics with their own independent
  threshold level line, no more... and that each metric within a group are
  related metrics"*; a dotted line sits at the threshold the report was judged
  against and *"shall dynamically follow the threshold settings relevant for
  the report"*; a line far from the data is out of view until the data comes
  near it; Colour accuracy may print twice as tall in the PDF; keep the Paper
  white L\* graph and add "Paper white, diff". His follow-ups of 5789263863:
  each new line in its metric's colour, Avg and Max stay grey (*"Yes."*); the
  line words are *"ok"*; the tab scroll arrows *"should stay as is"*; average
  plus 95th percentile for the control strip (*"I think so."*).
* **Ruling:** Knut,
  [5785414710](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5785414710) (2026-09-22),
  [5787117741](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5787117741),
  [5787380408](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5787380408),
  [5789263863](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789263863) (2026-09-23).
* **Built:** `ui/dialogs/measurement_report_dialog.py::_judged_trend_limits`,
  `_trend_plan`, `_PDF_ACCURACY_SCALE`, `_TrendChart`;
  `workflow/measurement_report.py::report_trend` (B8-817, commit 1d29569c).
* **Verified by:** `tests/test_trend_graphs_for_judged_metrics.py` (12 tests):
  `test_every_group_holds_at_most_two_related_rows_that_exist`,
  `test_the_paper_white_tabs_are_both_there_in_knuts_order`,
  `test_a_tab_shows_only_while_one_of_its_rows_is_judged`,
  `test_each_line_sits_at_the_limit_the_report_was_judged_against`,
  `test_only_the_judged_rows_of_a_group_are_plotted`,
  `test_a_report_that_judges_nothing_shows_none_of_the_new_tabs`,
  `test_a_line_outside_the_data_range_neither_shows_nor_moves_the_axis`,
  `test_a_withheld_evenness_value_is_not_plotted_against_its_limit`,
  `test_the_pdf_prints_the_shown_tabs_and_leaves_the_hidden_out`,
  `test_colour_accuracy_is_printed_twice_as_tall`;
  `tests/test_beta37_round_fixes.py::test_a_series_with_one_value_is_drawn_as_a_point`.
  Not pinned by any test: the line colours (grey Avg / Max, a colour per new
  metric) and the tab scroll arrows (gap G11, §20).
* **Proof:** `~/Desktop/ChromIQ-beta37-proof/graphs/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 17.1 Every graph explains itself (#182 K25, 2026-09-23)

#### ✅ Confirmed behaviour

**Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)),
with items 11 and 15 as amended by §18.9.

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

**Record (K25, the graphs).**
* **Rule:** *"Make sure to also implement the feature in Colour accuracy tab
  dictating what happens when a threshold label comes close to a graph's line,
  or y-axis labels etc."*; every label described under its graph in the PDF,
  the same text as a tooltip on screen; at most a two-line description above
  each printed graph; units on every data label; a withheld date as a small
  red x at the neighbouring value, the mean of both neighbours, or just above
  the x-axis, explained by tooltip and in the PDF. One measurement: the
  existing "at least two" text (5789532633). Items 11 and 15 were then amended
  by K26 (§18.9): the word stays at the left end, the neighbours are the
  nearest dates with a value; a date the chart could not supply gets no red x
  (*"No."*).
* **Ruling:** Knut, 2026-09-23,
  [5789263863](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789263863)
  (graph answers 2 and 5), [5789532633](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5789532633).
* **Built:** `ui/dialogs/measurement_report_dialog.py::_TrendChart`,
  `_LIMIT_NOTES`, `_TREND_ABOUT`, `_with_unit`, `_withheld_mark_value`,
  `_export_pdf` (B8-827, commit 9f216988).
* **Verified by:** `tests/test_trend_graphs_explain_themselves.py::`
  `test_the_red_x_height_follows_knuts_three_cases`,
  `test_a_withheld_date_stays_on_the_axis_with_its_reason`,
  `test_the_red_x_is_painted_red_where_the_rule_puts_it`,
  `test_every_tab_places_its_words_by_the_accuracy_rule`,
  `test_hovering_a_word_or_a_red_x_shows_the_text_the_pdf_prints`,
  `test_a_line_out_of_view_is_still_described_and_says_so`,
  `test_every_shown_tab_has_units_and_a_note_per_line`,
  `test_every_graph_description_fits_two_lines_in_the_pdf`,
  `test_the_pdf_prints_the_description_above_and_the_key_under`,
  `test_every_limit_word_has_a_note_written_for_it`,
  `test_one_measurement_still_shows_the_two_measurement_text`.
* **Proof:** `~/Desktop/ChromIQ-beta38-proof/graphs/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

## 18. K26: Knut's rulings on the beta 37 and K25 questions (#182, 2026-09-23)

### ✅ Confirmed behaviour (§18.2 to §18.11); §18.1 superseded

**Ruled by:** Knut, #182 comments 5792484060 (the answers) and 5792576954
(group "Report shown" from the start); our reply 5792508391.
**Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113):
*"confirmed except §18.1"*), for §18.2 to §18.11. This records his rulings and
what was built from them (B8-832), driven on screen
(`~/Desktop/ChromIQ-beta38-proof/k26/`). §18.1 is NOT confirmed: it is
superseded by the Calibration rule recorded under it.

**18.1 Calibration rule, confirmed; built in beta 39 (§18.12).**
**Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113):
*"This is changed. Description of 'Run type = Calibration, beta 39. Built as
you describe:' confirmed."*). The rule is Knut's
[5794078008](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794078008)
(*"The run type set to calibration should be able to make a report after all.
I retract my statement that the measurement report window should not allow
making reports in this run type."*), as summarised in our
[5794100213](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794100213):

* every report type except the Printing record;
* the measurement from `<project>/cal/`, and reports saved to and read from
  `<project>/cal/reports/`; "Included measurements" lists the measurement in
  the `cal/` folder, and holds several when another project's calibration is
  added;
* a report across projects in `<ChromIQ default folder>/reports/`, a folder
  made only when such a report is created;
* "Report shown" lists only reports of Run type Calibration, from those two
  `reports/` folders;
* name tags **Cal** (one calibration), **Multiple cals** (several across
  projects, not all in the list), **All cals** (every one in the list);
* "Report shown" grouped under each project's name, with reports of several
  projects under "Reports including multiple projects".

**Status:** rule confirmed; **built in beta 39**, recorded in §18.12, where the
built result awaits confirmation. Beta 38's empty, locked window described
next is removed.

> **18.1 as built in beta 38, SUPERSEDED by the Calibration rule above
> (Knut, 2026-09-23, 5794078008 and 5794311113). Not confirmed; kept as the
> record of what beta 38 does.**

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
(nothing is recalculated since B8-391). *Beta 38 challenge round (F7):* the
folder guide ("Where are my files") said the same in two more places and
called `reports/old/` "copied, never moved"; it now says that an unlock changes
no saved report, and that an Update and "Delete Selected Report" move a report
into `reports/old/<stamp>/`.

**18.3 The Printing record keeps "Judged against".** *"keep the judged against
row, which defines the thresholds shown."* Nothing changed.

**18.4 The Colour accuracy graph plots the judged figures.** *"Yes, use the
within-gamut figures."* Each date plots what its verdict judged
(`graded_de00`): the within-gamut figures where the sheet's colours were split
by the profile's gamut, all patches where they were not. With a within-gamut
date on the axis the two "all patches" legend entries read "all judged
patches", and the PDF description says the figures are within the profile's
gamut where the sheet was split by it. The Avg / Max lines are unchanged.
> **The "all judged patches" legend clause is SUPERSEDED by K28 item 2 (§22.2,
> Knut 2026-09-23, [5795087247](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5795087247)):** one name per metric everywhere, so the
> legend reads the row's own name ("Average ΔE00, all patches") on every
> graph, and the within-gamut fact is carried by the graph's description, the
> results intro and the one-page summary (§22.1). The rest of 18.4 stands.
*Beta 38 challenge round (F9):* the legend names its unit as every other graph
does, "Average, all patches (ΔE00)", where it said "Average ΔE, all patches".

**18.5 A project whose folder is not named what its files carry** (a Finder
duplicate, "X copy"). **Amended by §31.2 (A8, Knut [5817809396](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817809396), answer
(b)):** a rename that fails says why and then offers the three choices again;
it no longer leaves the project open, not renamed. *"the user should be given the option, with a popup
window, to rename the project. This interface and function should already
exist and just has to be modified a tiny bit to allow this case."*

* When a project is opened and its `project.json` name is not its folder's
  name, the existing rename chooser comes up before anything of the project is
  shown, with its heading and text from M-PROJECT-FOLDER-RENAMED
  (§M-PROPOSED). <name> is what the "Printer profile project name" field
  shows.
* **Three choices, and no "Leave it as it is"** (Knut, 2026-09-23,
  [5794078008](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794078008),
  which replaces the two choices first built): *"(1) rename the project to the
  project folder's name; (2) define a new name, which reuses the existing
  target-rename entry; (3) Cancel, which closes the project"*, each explained
  by a bullet in the window's text. Buttons: **Cancel** · **Choose another
  name…** · **Rename the project to "<name>"** (default). "Choose another name…"
  opens the existing project-name window prefilled with <name>, and the
  project is renamed to what is typed exactly as by the name field
  (`rename_existing_project`); cancelling that window returns to the three
  choices. Cancel (and Escape) closes the project: the app goes back to the
  state Close Project leaves, and nothing is written.
* Rename renames every ChromIQ file carrying the old name, and the manifest,
  in place; a folder whose name ChromIQ would not give a project (a space, as
  in "X copy") becomes "X-copy" as every rename does. A failure is reported
  (M-PROJECT-FOLDER-RENAME-FAILED, which says what went wrong in words) and
  nothing else runs.
* A project with a built profile is offered the same rename, and the rename
  bullet says the profile keeps the name written inside it. Knut answered the
  question (B8-832) *"Yes"* in 5794078008.
* **What a rename does on disk (beta 38 challenge round, F1 and F3).** A name
  that differs only in case (a folder renamed "report-limits" beside files
  called "Report-Limits") is the file itself on a case-insensitive volume, not
  a stranger: it is renamed in two steps through a temporary name, and nothing
  is moved aside. A file is moved aside ("…_conflicted_at_renaming_procedure")
  only when a different file holds the name. The whole rename is planned
  first and refused before anything moves when it cannot finish (two files
  would take one name, a folder ChromIQ may not write in), and a step that
  fails anyway is undone, so "Nothing was changed" in the failure message is
  true. ChromIQ's ordinary rename changes the case of a project's name the
  same way. Every file carrying the old name moves, `*.control-strip.json`
  included.
* **The reports a renamed project already has stay its own (F2).** A saved
  report records its measurements' folders under the name the project had
  when it was written. The rename records that name in `project.json`
  (`former_names`), and the report window reads a folder recorded under one
  of the project's own names, or a report of one project filed inside it, as
  THIS project's, and the measurement file under its new name. It never
  reaches into another folder that merely has the old name (a Finder
  duplicate's original, beside it), and it files the copy's reports under the
  copy's own runs.

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
behind, empty. *Fixed since:* the folder is removed when a save is cancelled
(K26 merge) and, since the beta 38 challenge round (F4), whenever the PDF is
saved anywhere else; it stays only when the PDF is written into it.

**18.9 The red x and the limit words.**

* A red x takes the NEAREST date on each side that has a value: at that value
  when one side has one, at the mean when both do, just above the x-axis when
  neither does (§17.1 item 15, amended).
* Two red crosses on one date whose places would overlap sit one above the
  other, one tooltip box apart (13 px), and **the lower value's cross stays
  lower** (beta 38 challenge round, F8; it used to be the later metric above,
  which drew "largest difference from the mean" 0.114 above "nine locations"
  0.203). When that would leave the plot at the top, the higher cross stays
  and the lower one goes below it.
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

**Record (K26).** **Ruling:** Knut, 2026-09-23,
[5792484060](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792484060)
and [5792576954](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5792576954);
each item quotes him above. **Proof:** `~/Desktop/ChromIQ-beta38-proof/k26/`
(`scripts/drive_k26.py`: drive-calib, drive-gamut, drive-rename, drive-list,
drive-shared, drive-redx). **Status:** every item agreed; the built result
of 18.2 to 18.11 is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182
comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
18.1 as built is superseded by the Calibration rule (built in beta 39, §18.12).
Commits 1ecea062, c198d508, 78a4f00b (B8-832).

| item | built | verified by (`tests/test_k26_rulings.py` unless named) |
|---|---|---|
| 18.1 Calibration (beta 38; REMOVED in beta 39, §18.12) | was `_bar_run_type`, `_calibration_controls`, `_lock_for_calibration` and M-REPORT-NOT-FOR-CALIBRATION; all removed, the message withdrawn from §M-PROPOSED | its four window tests were removed with it; `test_every_door_hands_the_window_a_parent_that_knows_the_run_type` stays (four doors since beta 39) |
| 18.2 Bound, and locked | `_bound_and_locked_help` (the "Judged against" help); the paragraph removed from the report guide | `tests/test_report_window_limit_controls.py::test_bound_and_locked_is_explained_in_the_help_not_the_report` |
| 18.3 Judged against row | nothing changed | `test_the_printing_record_keeps_its_judged_against_row` |
| 18.4 within-gamut graph | `_series_is_within_gamut`, `_METRIC_LABELS_JUDGED`, `_TREND_ACCURACY_LABELS`, `_TREND_ABOUT_DE_JUDGED`; `workflow/measurement_report.py::graded_de00` | `test_the_accuracy_trend_plots_what_the_verdict_judged`, `test_the_graph_says_its_figures_are_the_judged_ones`, `test_the_judged_description_fits_two_lines`, `tests/test_beta38_challenge_fixes.py::test_the_accuracy_legend_names_its_unit_as_the_others_do` |
| 18.5 folder rename | `ui/tabs/tab_chart.py::_offer_rename_for_a_renamed_folder`, `_close_after_folder_rename_cancelled`; `ui/dialogs/target_change_dialog.py::_build_folder_renamed_ui`; `workflow/measurement_messages.py::folder_renamed_texts`, `rename_failure_reason`; `core/file_manager.py::rename_existing_project`, `Project.rename`, `same_entry`, `ProjectRenameRefused`; `workflow/measurement_report.py::resolve_recorded_folder`, `names_of_project`, `renamed_file_name` | `test_a_finder_duplicate_is_offered_the_rename_and_renamed`, `test_cancel_closes_the_project_and_writes_nothing`, `test_choose_another_name_renames_to_the_name_typed`, `test_a_folder_already_named_as_chromiq_would_is_renamed_in_place`, `test_a_project_whose_names_agree_is_not_asked`, `test_the_chooser_offers_three_choices_in_its_folder_mode`; `tests/test_beta38_challenge_fixes.py::test_a_case_only_folder_keeps_its_built_profile`, `test_after_a_case_only_rename_no_date_is_listed_twice`, `test_the_ordinary_rename_changes_the_case_of_the_folder_too`, `test_a_rename_that_fails_part_way_is_undone`, `test_a_rename_that_cannot_finish_is_refused_before_anything_moves`, `test_the_failure_message_says_what_went_wrong_in_words`, `test_a_rename_carries_the_control_strip_declarations`, `test_a_renamed_duplicate_reads_only_its_own_measurements`, `test_a_renamed_duplicate_loads_its_own_other_run`, `test_the_old_name_never_reaches_into_the_original` |
| 18.6 Profiling names | `_scope_tag`, `_run_tag` | `test_a_profiling_window_names_reports_after_their_runs`, `test_a_verification_window_keeps_its_date_names` |
| 18.7 "these measurements" | the line under "Report shown" | `test_a_profiling_window_with_nothing_generated_says_these_measurements` |
| 18.8 shared folder | `document_home`; `_export_pdf` removes a folder it made unless the PDF is written into it | `test_the_shared_reports_folder_waits_for_a_report_across_projects`, `test_a_cancelled_pdf_save_leaves_no_reports_folder`, `test_a_pdf_saved_elsewhere_leaves_no_reports_folder` |
| 18.9 red x and words | `_withheld_mark_value`, `_stack_withheld_marks`, `_WITHHELD_STACK_PX` | `tests/test_trend_graphs_explain_themselves.py::test_the_red_x_height_follows_knuts_three_cases`, `test_two_red_crosses_on_one_date_sit_one_above_the_other`, `test_the_stacking_rule_stays_inside_the_plot`, `test_a_word_inside_the_plot_stays_at_the_left_end_over_a_data_line`; `tests/test_beta38_challenge_fixes.py::test_the_lower_value_s_cross_stays_lower` |
| 18.10 grouped from the start | `_grouped_documents` counts what the offered reports cover | `test_report_shown_is_grouped_from_the_start` |
| 18.11 demo white | `scripts/make_evenness_demo.py` | `test_the_evenness_demo_noisy_date_takes_the_paper_as_paper_white` |

~~Still open with Knut from this section (B8-832): whether "should not allow
any reports" also stops the report the Measure tab writes by itself after a
calibration measurement (not changed).~~ Answered by the Calibration rule
(5794078008): a calibration makes reports after all, so the question no longer
arises; what the automatic report does under that rule is built with it in
beta 39. Whether a project with a BUILT profile
may be renamed by 18.5 is answered: *"Yes"* (5794078008). The beta 38
challenge round's fixes to 18.2, 18.4, 18.5, 18.8 and 18.9, and the three
choices of 5794078008, are B8-833 to B8-841 (B8-842 and B8-843 are open);
proof `~/Desktop/ChromIQ-beta38-proof/fixes/`.

### 18.12 Run type Calibration makes reports (beta 39)

#### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* The RULE is Knut's and he confirmed it
(5794311113, of our summary 5794100213); what follows is what was BUILT from
it, driven on screen (`~/Desktop/ChromIQ-beta39-proof/calibration/`), and it
waits for him to say that it is what he meant. It supersedes §18.1 as built in
beta 38 (the empty, locked window).

> *"The run type set to calibration should be able to make a report after all.
> I retract my statement that the measurement report window should not allow
> making reports in this run type. ... Allowed report types are all except the
> printing record, and measurements are stored under project_name/cal/ folder
> and reports (with included one measurement for a project) are stored and
> read from project_name/cal/reports/, and "Included measurements..." lists
> the measurement in the cal/ folder. If another cal-folder's measurement is
> selected (which is only possible selecting in a different project), then the
> "Included measurements..." list will hold multiple measurement sets. IF a
> report is created that selects measurements across projects, then that is
> stored same as the other run types, in the <ChromIQ default folder>/reports/
> (only created if a report is created across projects). Reposts shown pulldown
> can only show reports belonging to run type = calibration and can only save
> or read reports from the two reports/ folders mentioned. The report names
> shall have tags "Cal" (when only one calibration), or "Multiple cals" when
> more than one included measurement across projects (but not all listed in
> "Included measurements..." list ), or "All cals" when all measurement sets in
> "Included measurements..." list are included across projects for a report.
> The "Report shown" dropdown list should then group the reports (that include
> one measurement) with group-headings according to the project name the
> measurements and reports belong to. And reports with multiple measurements
> included (across projects) are grouped under "Reports including multiple
> projects".* (Knut, 5794078008)

What was built:

* **The kind.** Run type Calibration is a kind of its own
  (`KIND_CALIBRATION`): every report type but the Printing record, which the
  Report type pulldown shows greyed with a sentence saying why. A window with
  no profile bar behind it takes the kind from its measurement: a project's
  `cal/` folder is a calibration. A folder merely named `cal` outside a
  project is not.
* **The window opens on the calibration**, from every door: Tools ▸
  Measurement report and the Measure tab's report button hand it
  `<project>/cal/<project>-cal.ti3`. Not measured yet: the Measure tab says
  "Measure this chart first", as it does for a run.
* **"Included measurements"** lists the calibration's measurement. A
  calibration of another project is added with "Add Profile's Measurements…"
  (its `cal/<name>-cal.ti3`), and the list then holds several measurement
  sets.
* **"Report shown" and "Already generated…"** read `<project>/cal/reports/` of
  every calibration in the list, and the folder across projects
  (`<ChromIQ folder>/reports/`, where a document covering calibrations of
  several projects lives, §13.11), of the types Calibration allows. Never a
  run's folders, never the project's own `reports/`. The line reads "Already
  generated for these measurements" (the Profiling wording, §18.7), because
  the list may hold several projects' calibrations.
* **A report across projects is offered only where it covers a calibration
  in the list**, compared by project name AND `cal`, so a report of P and Q is
  not offered in R's window just because R has a `cal/` too. A moved pack
  finds the other project's `cal/` beside this one (§13.11).
* **Names.** "Cal" for a report of one project's calibration; for a report of
  several projects' calibrations, "All cals" when it included every
  measurement set listed when it was made, "Multiple cals" otherwise. *As for
  "All dates" and "Multiple dates", the word is fixed when the report is
  made, not recalculated against what the list holds later.* A calibration
  measured again is still one calibration, so a report of its two
  measurements is "Cal".
* **Grouping.** One project's calibration in the list, and no offered report
  covering another project: no headings (§13.12's rule for one run). Otherwise
  a heading per project name with that project's reports directly under it
  (a calibration has no run, so there is no run heading), and reports of
  several projects under "Reports including multiple projects", last. *This
  is our reading of "grouped ... according to the project name" for the case
  with one project: say if a lone project should carry its heading too.*
  **ANSWERED by Knut, "ok" (5798461562): a lone project carries its heading
  (§24.5).**
* **The window opens on the newest report covering its calibration**
  (§13.12's rule). When that is a report across projects ("All cals" in the
  demo pack), it loads the calibrations it covers (§13.11, "a report is shown
  whole"), ~~and Generate is greyed until "New report…" is chosen~~
  (**superseded by G7, §13.13**: Generate is live, and Update rewrites the
  report across projects). *Say if a Calibration window should open on its
  own "Cal" report instead.* **ANSWERED by Knut (5798461562): *"No. Open on
  most recent report."*, and Generate is live over it (§24.1).**
* **Generate report** writes a report of the window's own calibration into
  `<project>/cal/reports/` (one file, one document, as for one dated
  verification). "New report…" starts from the Preferences default type,
  fitted (a Printing record default reads as Full colour check), and the
  Preferences default limit set: a calibration binds no set and stores no
  type. ~~With another project's calibration loaded, Generate is greyed and
  its tooltip says calibrations of more than one project are loaded; a report
  across projects is not written from the window yet (the §13.9 / G7
  work).~~ **SUPERSEDED by G7 (§13.13, beta 39; Knut [5794078008](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794078008): a report that
  *"selects measurements across projects ... is stored same as the other
  run types, in the <ChromIQ default folder>/reports/"*):** with another
  project's calibration loaded and ticked, Generate writes one document in
  the folder across projects, judged against the report's own set, and
  nothing into either `cal/`. ⏳ Awaiting confirmation. **Confirmed by:** *nobody yet.*
  Under Calibration a run's measurement is never written, even when a Remove
  left one first in the list.
* **Delete Selected Report** moves a calibration's report to
  `cal/reports/old/<stamp>/`. It is never refused: a calibration has no dated
  series and no bound limit set for its last report to keep (§5).
* **Save report as PDF…** opens `cal/reports/` for one calibration, the
  folder across projects for several (§13.11's rule).
* **The report ChromIQ writes by itself after a calibration measurement**
  (with "Save measurement report" on) follows the Verification pattern: the
  Preferences default type, never the Printing record, judged against the
  Preferences default set, one document named "Cal", in
  `<project>/cal/reports/`. Before beta 39 it was written there too, but a
  stored Printing record default made it a Printing record.
* **The help.** The Report type help says a calibration can have every type
  but the Printing record; "Where are my files" has a row for
  `cal/reports/report_*.json` and a folder entry for `cal/reports/`.
* **M-REPORT-NOT-FOR-CALIBRATION is withdrawn** from §M-PROPOSED, never having
  been approved.
* **`cal/reports/` survives a new calibration chart.** `Calibration.reset`
  archives files only, so the reports stay while the measurement they
  describe moves to `cal/old/<stamp>/`; such a report keeps the numbers it
  was saved with, as a run's does after it is measured again.

**Record (beta 39, Calibration).**
* **Rule:** his words at the head of this section.
* **Ruling:** Knut, 2026-09-23,
  [5794078008](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794078008),
  confirmed as described in our
  [5794100213](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794100213)
  by [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113).
* **Built:** `workflow/measurement_report.py::KIND_CALIBRATION`,
  `report_types_for_kind`, `is_calibration_dir`, `measurement_dir_kind`,
  `_project_folder_of`, `project_relative`, `resolve_recorded_folder`,
  `shared_report_folders`, `_coverage_key`;
  `ui/dialogs/measurement_report_dialog.py::_bar_kind`, `_window_kind`,
  `_is_calibration_window`, `_own_cal_dir`, `_calibration_dirs_of_the_list`,
  `_scope_tag`, `_grouped_documents`, `_own_place`, `_saved_documents`,
  `_generated_types_line`, `_sync_type_combo`, `_reports_to_generate`,
  `_on_generate_report`, `_report_type_now`, `_load_the_defaults`;
  `ui/tabs/tab_measure.py::_open_measurement_report`,
  `_stamp_the_automatic_document`; `ui/file_guide.py` (B8-844).
* **Verified by:** `tests/test_calibration_reports.py` (16 tests, each proved
  red on the mutation in its docstring):
  `test_a_calibration_offers_every_type_but_the_printing_record`,
  `test_the_folders_of_a_calibration`,
  `test_a_moved_pack_finds_the_other_projects_calibration`,
  `test_a_calibration_window_lists_counts_and_writes_its_own_reports`,
  `test_a_new_calibration_report_starts_from_the_preferences_type`,
  `test_a_window_with_no_bar_on_a_calibration_is_a_calibration_window`,
  `test_delete_moves_a_calibration_report_into_cal_reports_old`,
  `test_several_calibrations_are_grouped_by_project`,
  `test_multiple_cals_and_all_cals`,
  `test_a_report_of_two_calibrations_is_not_offered_to_a_third`,
  `test_a_calibration_s_reports_are_not_counted_on_a_profiling_window`,
  `test_under_calibration_a_run_s_measurement_is_never_written`,
  `test_the_automatic_report_of_a_calibration_is_never_a_printing_record`,
  `test_the_measure_tab_button_opens_the_calibration_s_measurement`,
  `test_the_type_help_says_what_a_calibration_can_have`,
  `test_the_withdrawn_red_line_is_gone`.
* **Proof:** `~/Desktop/ChromIQ-beta39-proof/calibration/` (REPORT.md and
  photographs; the demo pack's calibrations in
  Report-Limits-Report-Folders, -Second and -Report-Types).
* **Status:** rule agreed and confirmed; the built result ⏳ awaiting
  confirmation. **Confirmed by:** *nobody yet.*

## 19. Report text, pre-flight and window rulings of 2026-09-22 and 2026-09-23

**✅ CONFIRMED.** **Confirmed by:** Knut, 2026-09-23 (#182 comment
[5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
This section records rulings that had no home in §10 to §18. Each is agreed
behaviour from the day Knut gave it, and he has confirmed what was built from
§19.1 to §19.13. Not covered: R2 of §19.7 (not built, gap G5), question 14 of
§19.5 (unanswered), and the §M-PROPOSED wordings named here, which stay
proposed in `unified_measurement_management.md`.

### 19.1 Report text is written for a customer (K18)

**Record.**
* **Rule:** *"The report text itself shall not say anything about how to use
  the ChromIQ tool. The report may be given to a customer and knows nothing
  about ChromIQ, and shall not be presented with information on the usage of
  ChromIQ. This is a general rule for all text generated for the reports."*
  (5774852534). And: *"A report text shall never explain something in the
  past, only the current functionality ... the text shall never explain any
  ChromIQ related functions or user related notes and tips for ChromIQ."*
  (5785414710). So: no "you", no window vocabulary, no ChromIQ history; "the
  test chart used" and "the printed test chart" in place of "this chart" and
  "the chart you printed"; *"when a report judges nothing"* in place of "when
  you chose a report type that judges nothing"; the standard caveat true of a
  Custom set, a PASS being an indication *"as long as the defined limits stay
  within the limits defined by the standard"*. The windows (pre-flight,
  presets window, help) may name ChromIQ controls: they are not report text.
  This sharpens the beta 20 rule already in §11 ("a separate document printed
  for a customer").
* **Ruling:** Knut, 2026-09-22,
  [5774852534](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5774852534),
  and 2026-09-23,
  [5785414710](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5785414710).
* **Built:** the report guide, metric blurbs, notes and summaries in
  `ui/dialogs/measurement_report_dialog.py` and
  `workflow/compliance_sets.py::STANDARD_CAVEAT` (B8-808 commit 8930cead,
  B8-811 commit fe6e9b64, B8-818 commit 7ef2fac4; "Bound, and locked" left the
  report by K26, §18.2).
* **Verified by:** `tests/test_final_round_before_beta36.py::`
  `test_the_guide_explains_no_chromiq_mechanics`,
  `test_the_recorded_verdict_sentence_names_no_ChromIQ_action`;
  `tests/test_beta37_report_text.py::test_no_metric_blurb_speaks_to_the_reader`,
  `test_the_report_neither_speaks_to_the_reader_nor_explains_chromiq`,
  `test_what_the_rising_numbers_mean_is_a_statement_not_advice`;
  `tests/test_beta37_round_fixes.py::`
  `test_a_printing_record_carries_no_standard_caveat_and_no_provenance`;
  `tests/test_a_recommended_metric_carries_a_note.py::`
  `test_a_stored_COND_verdict_is_still_a_word_the_app_defines`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/final-challenge/`,
  `~/Desktop/ChromIQ-beta37-proof/challenge-B/`, `~/Desktop/ChromIQ-beta37-proof/fixes/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
* **Sharpened by Knut, 2026-09-25 (K39-1,
  [5831246553](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5831246553)):**
  *"This part "Update works the report out again." is not according to
  rules for report text and notifications in the report. It refers to
  features, actions or buttons in the app interface, which shall never be
  part of the notes or the report text. Make sure all reports and notes do
  not directly mention such things, but if helpful for a user or customer to
  understand instead mentions topics in a general term without referring to
  features, actions or buttons in the app interface."* So report text (the
  page in the window, the PDF, Report Scope, the notes, the reading guide,
  the graphs, and every §M message printed in a report) names no feature,
  action, button, menu, tab, window or pulldown of the app; where it helps,
  it speaks of the topic in general terms. Window text (dialogs, tooltips,
  status lines, the red line, the empty page) still may. The rule is ruled;
  the audit and what was changed for it are §35, **awaiting confirmation**
  (the confirmation above covers §19.1 as it stood on 2026-09-23).

### 19.2 An N-A note names what the measured chart lacks (K22)

**Record.**
* **Rule:** *"could you instead state what is missing, without mentioning
  what to add? ... the rule becomes 'each names the thing missing in the
  measured chart'."* Every reason behind an N-A note says what is missing in
  "the measured chart" and gives no instruction. **SUPERSEDES** S2w of
  2026-09-18 ("each names the thing to change", `issue_182_answers.md`). The
  window's own help keeps its levers, because that is ChromIQ talking to its
  user.
* **Ruling:** Knut, 2026-09-23,
  [5787117741](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5787117741).
* **Built:** `ui/dialogs/measurement_report_dialog.py::_reason_sentence` and
  `_note_the_absences` (B8-813, commit 2bba3053); the evenness reasons in §16.3.
* **Verified by:** `tests/test_final_round_before_beta36.py::`
  `test_every_na_note_names_what_is_missing_and_nothing_to_do`;
  `tests/test_the_five_rows_that_had_no_detection.py::`
  `test_every_new_reason_becomes_a_sentence_that_says_what_to_do`;
  `tests/test_beta37_report_text.py::`
  `test_the_closing_sentence_says_why_and_not_what_a_row_needs`.
* **Proof:** none of its own (tests only). Gap G10.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.3 Numbers carry their unit (K10)

**Record.**
* **Rule:** *"The results does not say the normal proper units or ΔE00. These
  things do not take much space and should always be present when presenting
  numbers."* The one-page summary reads "Average difference 0.87 ΔE00; Largest
  2.75 ΔE00". The graphs follow the same rule (§17.1 item 14).
  **The wording is SUPERSEDED by K28 item 2 (§22.2):** the line now reads
  "Average ΔE00, all patches: 0.87; Maximum ΔE00, all patches: 2.75", the one
  name carrying the unit; the rule (a number carries its unit) stands.
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K10 of B8-778).
* **Built:** the one-page result line (B8-796, commit 28e27723).
* **Verified by:** `tests/test_t1_is_one_page_to_hand_over.py::`
  `test_the_result_line_gives_its_numbers_with_their_unit`.
* **Proof:** none of its own (tests only). Gap G10.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.4 The paper white line prints L\*, a\* and b\* (K5)

**Record.**
* **Rule:** a swatch can always be read against its numbers: *"'Paper white &
  darkest black' Shows White (1) - L\* 100.0 ... But the colored box in front
  of white shows as light blue."* The line prints L\*, a\* and b\* whenever the
  record carries them, never "nan" or "-0.0". The blue was the demo data (a
  D65 white), fixed with K15 (§19.12).
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K5 of B8-778).
* **Built:** `workflow/measurement_report.py::point_lab` and the "Paper white &
  darkest black" section (B8-779 commit 6bf0601e, B8-793 A-7).
* **Verified by:** `tests/test_one_paper_white_has_one_answer.py::`
  `test_the_swatch_line_prints_a_and_b_as_well_as_l`,
  `test_the_line_never_prints_nan_or_minus_zero`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K5-paper-white/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.5 The verification pre-flight (K2 and the beta 32 findings)

**Record.**
* **Rule:** the "Before you measure this verification chart" window appears
  only while a chart exists without a measurement, before measuring starts:
  *"The message should appear if only if a chart exists without a
  measurement, before a user starts to measure."* A run with a measured
  dated verification never shows it again (*"Are you checking the location of
  the ti3 file in the same location as the chart? for verification runs the
  ti3 file is in the dated folder"*). Its count is generic, over every report
  type and limit set, because no report exists yet: *"This chart can answer
  17 of the 18 metrics that available report types and limit sets can use."*
  The opening sentence is clear; the "finished page images" clause is gone.
  Wording: M-VERIFY-PREFLIGHT, §M-PROPOSED of
  `unified_measurement_management.md`, not approved.
* **Ruling:** Knut, 2026-09-22,
  [5777667003](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5777667003)
  (beta 32), [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382)
  (K2, beta 34), [5784377277](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5784377277)
  (beta 35, still seen).
* **Built:** `ui/tabs/tab_measure.py::_verification_preflight_due`,
  `_run_has_a_measured_verification` (B8-765, B8-776 commit 528b7cfc, B8-784);
  `workflow/preset_eligibility.py::rows_any_report_can_ask`, `assess_any`.
* **Verified by:** `tests/test_the_verification_preflight_fires_for_its_preconditions.py::`
  `test_not_owed_on_a_new_dated_verification_once_the_run_has_history`,
  `test_the_window_says_what_the_presets_window_says`,
  `test_the_window_frames_it_with_the_catalogue`;
  `tests/test_adversary_k2_528b7cfc.py::`
  `test_GAP_history_is_read_from_the_SELECTED_profile_run_not_the_current_one`,
  `test_GAP_an_empty_first_date_does_not_hide_a_measured_later_one`;
  `tests/test_round_c_guards_since_beta35.py::`
  `test_a_dated_folder_printed_but_never_read_is_not_history`;
  `tests/test_beta37_a_preflight_asked_while_one_is_open_is_not_lost.py::`
  `test_a_request_met_by_an_open_window_is_made_again_when_it_closes`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K2-preflight-history/`,
  `~/Desktop/ChromIQ-beta36-proof/K2-knuts-own-project/` (his own project),
  `~/Desktop/ChromIQ-beta36-proof/adversary-k2/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)). Question 14
  of 5784140521 (a date holding only `reads/read1.ti3`, and one whose
  measurement a Replace moved to `old/`) is his and unanswered.

### 19.6 "Unlock this run's limits" with fewer than two dated verifications

> **SUPERSEDED by K31 (§25, Knut, #182 [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743), beta 40).** *"I agree that the 'Unlock this run's limits' is no longer
> needed"*: the box, its help icon, its two question windows, the run lock
> and the Preferences option "Allow editing of thresholds after the first
> verification measurement" are removed (§25.4). The record below is the
> history of the rule; the tests it names are retired.

**Record.**
* **Rule:** *"Since there is only one dated verification, and the judged
  agains selection box is editable, it does not make sense to allow to unlock.
  The checkbox should be greyed out and not clickable, but a tool-tip should
  say that the limit set and the Edit Limit button will by default be locked
  when two or more dated verification runs exist"*.
* **Ruling:** Knut, 2026-09-22,
  [5777805448](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5777805448).
* **Built:** the enable rule follows `locked` in
  `ui/dialogs/measurement_report_dialog.py` (B8-766, commit d8ad16b7); the
  tooltip names the two-date lock.
* **Verified by:** `tests/test_report_window_limit_controls.py::`
  `test_the_unlock_box_is_dead_while_there_is_nothing_to_unlock`;
  `tests/test_final_round_before_beta36.py::`
  `test_after_clear_list_unlock_says_nothing_is_loaded`.
* **Proof:** none of its own (tests only). Gap G10.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.7 Before printing: a metric the chart cannot answer, and "-"

**Record.**
* **Rule:** the pre-flight and "Which presets can be used for verification?"
  tell the user that a report judging a metric the chart cannot answer will
  carry a note for it, and that the metric can be turned off in Report limits
  (threshold "-") for a cleaner report to hand a customer: *"This type of
  information allows the user to understand that it is possible to change the
  report text to be more clean"*. Said only where the chart really falls
  short. Wording: M-VERIFY-UNCHECKED-METRICS, §M-PROPOSED, not approved.
* **Ruling:** Knut, 2026-09-22,
  [5774104083](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5774104083)
  (the place for it confirmed in 5774852534).
* **Built:** the two windows' paragraph (B8-767, commit 44e36ca1; rewritten by
  B8-773). The pre-flight carries ONE line pointing at the presets window,
  because the full paragraph took the popup past a 13 inch screen. **Knut then
  ruled (R2, 5781645939): *"The popup window can be made wider, so that it does
  not become as tall, and no scrolling is needed in that window. The current
  text shown in beta 34 was ok."* Built in beta 39, §21.3.**
* **Verified by:** `tests/test_knuts_two_warnings_of_2026_09_22.py::`
  `test_the_set_really_decides_whether_such_a_row_is_shown`,
  `test_the_message_says_what_decides_it_and_qualifies_the_lever`,
  `test_the_preset_window_prints_it_under_a_chart_that_falls_short`,
  `test_and_never_under_a_chart_that_falls_short_of_nothing`,
  `test_the_preflight_says_it_too_when_the_chart_falls_short`.
* **Proof:** `~/Desktop/ChromIQ-beta35-proof/preflight-height/`.
* **Status:** agreed; the part that is built is confirmed. **Confirmed by:**
  Knut, 2026-09-23 (#182 comment
  [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).
  R2 built in beta 39 (§21.3), awaiting confirmation.

### 19.8 Sheets with different patch counts: an information note (R4)

**Record.**
* **Rule:** *"it is not an error, and a user may want to compare the outputs
  from different charts, but there should be a warning informing that some of
  the measurements selected to be included in the report are using different
  charts with different number of patches measured, and thus the results for
  judged metrics may differ slightly"* (5774104083), and it must be *"a clear
  information note, not the same font and colour as other bread-text, so that
  the note is not hidden"* (R4, 5781645939), in no warning colour. Wording:
  M-REPORT-PATCH-COUNTS-DIFFER, §M-PROPOSED, not approved.
* **Ruling:** Knut, 2026-09-22,
  [5774104083](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5774104083),
  [5781645939](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781645939).
* **Built:** `report_scope`'s `notes` key and the note box in
  `ui/dialogs/measurement_report_dialog.py` (B8-768 commit 44e36ca1, B8-774,
  B8-797 commit f19e9ca2).
* **Verified by:** `tests/test_knuts_two_warnings_of_2026_09_22.py::`
  `test_two_patch_counts_make_one_note_in_column_order`,
  `test_a_sheet_with_no_recorded_count_is_not_a_second_count`,
  `test_the_note_is_never_appended_to_the_red_warning_block`,
  `test_the_rendered_note_carries_the_counts_and_is_not_the_fail_colour`,
  `test_the_note_is_set_apart_from_body_text`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/R4-note-box/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.9 A report type says which metrics it judges; "Restore defaults"

**Record.**
* **Rule:** the Report limits window and the report say which rows the chosen
  type covers, and every column's "Restore this column" button reads "Restore
  defaults". The per-report-type "This Report Type Checks" column he proposed
  is **cancelled**: *"I think that these two things are sufficient for now.
  cancel the design of making a checkmark for each report type."*
* **Ruling:** Knut, 2026-09-22,
  [5777029221](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5777029221)
  (the request) and
  [5777326491](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5777326491)
  (the ruling).
* **Built:** `ui/dialogs/measurement_report_dialog.py::_type_covers_sentence`,
  read from `workflow/measurement_report.py::REPORT_TYPE_ROWS`; the button in
  `ui/dialogs/thresholds_dialog.py` (commit 6456b7ec, in beta 34; B8-763).
* **Verified by:** the button: `tests/test_a_short_button_is_short_on_screen.py::`
  `test_the_ceiling_is_the_windows_own_small_button` (it matches on "Restore
  defaults"). **The sentence: no test** (gap G9).
* **Proof:** `~/Desktop/ChromIQ-beta34-proof/challenge-round-38/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.10 Restore Used Chart restores the chart's fields only

**Record.**
* **Rule:** *"The Description and the seven compliance fields are the run's
  and stay."* What belongs to neither chart nor run survives too (*"It sounds
  like they should survive too."*). What the chart owns is restored as it was
  when the measurement started, including the absence of a control-strip
  declaration: *"The restore shall restore what existed at the time when the
  chart was backed up ... and if that chart did not have a control-strip
  declaration, then the restored chart in verifications/ folder should not
  have it either."* The limit binding stays on the run (*"keep 'the binding
  stays on the run'"*, 5775993270).
* **Ruling:** Knut, 2026-09-22,
  [5774852534](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5774852534),
  [5775260868](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5775260868),
  [5775993270](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5775993270).
* **Built:** `workflow/verify_chart_snapshot.py::CHART_META_KEYS`; the previous
  file is archived first (B8-740, commit 13a6e7dc). B8-731 (the control-strip
  case) is correct behaviour by his ruling.
* **Verified by:** `tests/test_a_restore_archives_the_side_file_it_overwrites.py::`
  `test_restore_takes_only_the_charts_fields_from_the_snapshot`,
  `test_a_snapshot_meta_that_cannot_be_read_changes_no_live_field`,
  `test_the_replaced_side_file_is_archived_before_it_is_overwritten`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/B8-740-restore/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.11 A per-target row the stored block lacks opens on its default

**Record.**
* **Rule:** switching to a target whose saved settings have no entry for an
  option puts that option on its documented default, not the previous
  target's value (*"You fix seems reasonable."*). The calibration's own rows
  are left alone while the calibration is the selected target. This belongs
  to `per_target_settings.md` and is recorded here because it was ruled in the
  same batch.
* **Ruling:** Knut, 2026-09-22,
  [5775260868](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5775260868).
* **Built:** `ui/tabs/tab_chart.py::load_target_settings` (B8-732, commit
  2cb9e3fe).
* **Verified by:** `tests/test_a_fresh_run_opens_on_its_own_defaults.py::`
  `test_a_row_the_stored_block_lacks_opens_on_its_default`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/B8-732-fixed/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.12 Knut's i1Pro presets (K1) and the demo pack (K15)

**Record.**
* **Rule:** his eight 7.5 mm i1Pro "Maximised - No Clip-border" presets are
  built in like the others (*"to be added as built-in like the others"*). The
  demo projects follow every rule the app follows: report names, run types,
  the Create Chart verification presets that must really trigger FAIL where
  they claim to (*"The demo projects package must be updated to follow all the
  rules"*), and every report location, report type and run type combination
  (*"Make sure the demo projects have created runs and projects that tests all
  variations of the above locations of reports and report types and run
  type."*, 5787117741).
* **Ruling:** Knut, 2026-09-22,
  [5781159382](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781159382) (K1),
  [5781197240](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5781197240),
  [5776517563](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5776517563) (K15);
  2026-09-23, [5787117741](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5787117741).
* **Built:** the presets and their registration in `ui/tabs/tab_chart.py`
  (B8-801, commit 6313bc9f, `docs/dev_builtin_presets.md`);
  `scripts/make_report_limit_demos.py`, `scripts/make_verification_preset_demos.py`,
  `scripts/make_evenness_demo.py` (B8-804 commit 3484e0a9, B8-807, and the
  K23 and K25 packs).
* **Verified by:** `tests/test_i1pro75_maximised_builtin_presets.py::`
  `test_chart_builds_with_the_sheet_pages_and_patches_its_name_promises`,
  `test_every_chart_registered`, `test_they_are_offered_in_the_verification_window`;
  `tests/test_the_demo_pack_covers_every_report_type.py::`
  `test_the_pack_prints_on_paper_and_not_on_the_d65_white`,
  `test_no_plan_gives_a_verification_a_type_its_kind_refuses`;
  `tests/test_the_demo_pack_says_what_its_own_data_shows.py::`
  `test_a_paper_white_on_a_colour_patch_stops_the_build`;
  `tests/test_the_demo_presets_pair_on_every_requirement.py::`
  `test_each_pair_shows_under_the_choice_its_name_gives`.
* **Proof:** `~/Desktop/ChromIQ-beta36-proof/K1-i1pro-presets/`,
  `~/Desktop/ChromIQ-beta36-proof/K15-demo-pack/`,
  `~/Desktop/ChromIQ-beta36-proof/B8-807-demo-pack/`,
  `~/Desktop/ChromIQ-beta37-proof/report-folders/demo-pack/`,
  `~/Desktop/ChromIQ-beta38-proof/report-list/demo-pack/`.
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

### 19.13 "New report…" on a bound run shows the run's own set

> **SUPERSEDED by K31 (§25, Knut, #182 [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743), beta 40).** No run is bound. *"the starting choice for 'New report...'
> should be the the defaults in preferences -> reports first, then the
> default in the Edit limits for that run, if it changed to be different
> from the preferences default"* (§25.5). An older run's bound set is read
> as that run's own default for new reports.

**Record.**
* **Rule:** Preferences supplies the default when the run has no bound set; a
  bound run shows its own set, and the window says so (*"so as you said and
  recommend"*). This keeps §5: a report is never stamped with numbers the run
  is not bound to.
* **Ruling:** Knut, 2026-09-22,
  [5776479532](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5776479532)
  (B8-526, recorded in B8-764; the register entry B8-526 itself still reads
  OPEN).
* **Built:** before beta 34: the "Judged against" tooltip under "New report…"
  in `ui/dialogs/measurement_report_dialog.py` (B8-526).
* **Verified by:** no test is named for this ruling (gap G9).
* **Proof:** the register names `~/Desktop/ChromIQ-beta28-proof/knut-beta26-review/defaults/`,
  which is no longer on disk (gap G10).
* **Status:** agreed; the built result is confirmed. **Confirmed by:** Knut, 2026-09-23 (#182 comment [5794311113](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5794311113)).

## 20. Rulings not built, or built without a test or proof

**⏳ AWAITING CONFIRMATION.** **Confirmed by:** *nobody yet.* Every item is a
rule Knut gave or a request he made; each says what exists today. None is to
be built without re-reading his comment first, and every one that is not
built waits on a question to him or on work not yet done.

| # | ruling | comment, date | what exists |
|---|---|---|---|
| G1 | K6 one vocabulary for the metric names, in the graphs, "Overview of Measurement Metrics", Report limits, help and messages: *"Make sure we are using the correct names in the reports, windows, help text, warnings, popup messages etc."* | 5781159382, 2026-09-22 | **Built in beta 39 (§22.2, B8-849), awaiting confirmation.** NOT built. Questions 1 and 2 of 5784140521 (the exact i1Profiler-style names; which population a table shows) unanswered; the graph's population is settled by §18.4 |
| G2 | K7 a metric whose threshold is "-" disappears from Report Results, the Overview, the detailed data and the graph | 5781159382, 2026-09-22 | **Built in beta 39 (§22.3, B8-849), awaiting confirmation.** NOT built. Question 3 of 5784140521 (the Overview table too?) unanswered |
| G3 | K8 report rows with no Report limits row (Paper white L\*, Black L\*, the per-colour ΔE00 rows, Spread): which limit each belongs to, and should notes say so | 5781159382, 2026-09-22 | **Built in beta 39 (§22.4, B8-849), awaiting confirmation.** Answered by measurement in 5784140521; question 4 (keep them under "For information", or remove) unanswered. Not built |
| G4 | R1 the one-page summary: *"keep 1"*, and analyse option 3 with the Run description limited to 2 lines | 5781645939, 2026-09-22 | **Answered (K28 item 7: keep option 1, A4 only); the dead list code removed in beta 39 (§22.5).** Option 1 is what runs. Option 3 analysed (`~/Desktop/ChromIQ-beta36-proof/design-R3-R2-R1/`): it did not fit A4 with a 2-line description. Question 7 unanswered; the 2-line limit and its help text NOT built |
| G5 | R2 the pre-flight popup made wider so the full beta 34 paragraph fits with no scrolling | 5781645939, 2026-09-22; 5795087247, 2026-09-23 | **Built in beta 39** (§21.3): *"Leave the window wider as previously specified."* |
| G6 | R3 the ISO-derived sets stop showing rows nothing can answer (*"agreed, do that"*) | 5781645939, 2026-09-22 | **Superseded by the general N-A rule of K28 item 5 (§22.5), awaiting confirmation.** NOT built. Questions 5 and 6 of 5784140521 (by reason or by set; should the full report still name what was left out) unanswered |
| G7 | One report, one limit set, applied to every measurement it includes, across runs (§13.9); Generate across projects (5794078008 point 3) | 5773668311, 2026-09-22; rule confirmed 5794311113, 2026-09-23; 5794078008, 2026-09-23 | Rule **confirmed by Knut, 2026-09-23** (5794311113): *"the report's own limit set applies to every included measurement, whatever each run is bound to"*, which answers question 8 of 5784140521. **Built in beta 39, awaiting confirmation** (§13.13, B8-848): Generate across profile runs and across projects, in Verification, Profiling and Calibration; one document file judged against the report's set; `tests/test_g7_reports_across_places.py`; proof `~/Desktop/ChromIQ-beta39-proof/g7/`. Within one profile run, dates recorded against another set are still narrowed (question in B8-848) |
| G8 | E8 judge evenness in absolute Lab (*"Do an investigation to see what is normal practice."*) | 5789263863, 5795087247, 2026-09-23 | **Built in beta 39** (§21.1): he answered *"Yes"* |
| G9 | Built rulings with no test that goes red: the type-covers sentence (§19.9); the "New report…" set tooltip (§19.13) | 5777326491, 5776479532, 2026-09-22 | Built, unpinned |
| G10 | Built rulings with no on-screen proof folder of their own: K19 (§13.10), K22 (§19.2), K10 (§19.3), the unlock box (§19.6), the ISO cap (§14.6); K12 only inside round A; B8-526's proof folder gone | as listed | Tests only |
| G11 | Graph details he answered with no test: the line colours (grey Avg and Max, a colour per new metric), the tab scroll arrows staying as they are | 5789263863, 2026-09-23 | Built as he answered, unpinned |
| G12 | Notes wherever a verdict is shown, including the Printing record's detailed sections, suppressed where none is (*"OK"*); and *"Yes, check that all notes are printed"* (all 19 absence notes on screen) | 5774852534, 5775260868, 2026-09-22 | **Built in beta 39, awaiting confirmation** (§12 CH-31a, B8-845): the record explains its N-A rows and gives no verdict word in its detailed sections; every type's detailed table carries the document's note numbers. All 27 reason codes (the 19 plus the 8 evenness codes) driven on screen and saved to PDF, `~/Desktop/ChromIQ-beta39-proof/notes/REPORT.md`; `printing_unrecorded` prints only as an INFO reason from a report saved before 2026-09-13 (never N-A). Five questions in B8-845 |
| G13 | B8-483 the grey ramp subset evenly spaced, no two picked patches close enough to lump (*"How close can two patches picked come to each other"*) | 5775993270, 5776479532, 2026-09-22; 5795087247, 2026-09-23 | **Built in beta 39** (§21.2), 4 % of full scale |

## 21. K28: evenness in absolute Lab, the grey ramp's spacing, the wider pre-flight, the ChromIQ folder's old/ (#182, beta 39)

**⏳ AWAITING CONFIRMATION.** **Confirmed by:** *nobody yet.* The four
rulings are Knut's
([5795087247](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5795087247),
2026-09-23, answering our questions; our summary
[5795122579](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5795122579)),
so they are agreed; what was BUILT from them waits for his confirmation.
Registered as B8-846. Proof: `~/Desktop/ChromIQ-beta39-proof/k28-a/`.

### 21.1 E8: evenness is judged in absolute Lab, whatever the print's intent

**Record.**
* **Rule:** *"E8: judge evenness in absolute Lab always, whatever the print's
  intent? … Answer: Yes."* The research behind the question:
  `~/Desktop/ChromIQ-beta38-proof/evenness-followups/E8-research.md` (every
  published uniformity test compares absolute CIELAB readings of one sheet
  with itself).
* **SUPERSEDES** the clause of §16.1 item 1 (confirmed 2026-09-23) that the
  residual is taken *"in the same yardstick (absolute, or media-relative where
  the report normalises)"*. The rest of §16 stands.
* **Built as:**
  * the READINGS are always the sheet as measured (`absolute_lab` in
    `build_report`); nothing is divided by the lightest patch for evenness;
  * on a sheet the ΔE00 rows read media-relative (printed through its profile
    with an intent that maps paper white, against a design or device
    reference), each AIM is carried onto the paper instead:
    aim XYZ × paper white / D50 (`aims_on_the_paper`), the ICC.1 6.3.2.2
    scaling run the other way. **This part is our construction, not Knut's
    words, and is the thing to confirm.** Why it is there, measured on the
    837-patch demo chart printed relative on a paper of L\* 95.5, b\* -3
    (`e8_three_ways.txt`): the readings as measured against the ideal-paper
    design aims make the paper's own tint read as unevenness, colour by
    colour, which raised the sheet's noise from 0.18 to 1.0 and turned a
    drift that fails (1.51) into a pass (1.33). One scale on every aim cannot
    make one ninth differ from another; with it the noise is 0.17 and the
    drift fails again (1.47). The paper white is the same lightest patch the
    ΔE00 rows use (`lightest_and_darkest`, the one rule);
  * a sheet printed absolute, or against a colorimetric reference, keeps its
    aims as designed: nothing changes for it;
  * the evenness block records `"yardstick": "absolute"` and `"aims":
    "on_the_paper"` or `"as_designed"`;
  * the evenness help text says the readings are taken as measured, and that
    on such a sheet each aim is carried onto the paper (**its wording is
    SUPERSEDED by §26.1**, the text Knut approved);
  * **not changed:** the report's "How the colours were judged" line
    describes the ΔE00 rows only. Whether it should also say that evenness is
    read as measured is an open question (report rendering, not built here).
    **Answered by §26.1:** a separate "How evenness was judged" line, shown
    only when an evenness row is in the report.
* **Built:** `workflow/measurement_report.py::build_report` (the
  `evenness_ref` wiring), `aims_on_the_paper`, `evenness_block`;
  `workflow/compliance_sets.py::_D_EVENNESS`; the demo's run8
  (`scripts/make_evenness_demo.py`).
* **Verified by:** `tests/test_beta39_k28a.py::`
  `test_a_white_mapped_sheet_is_read_as_measured_for_evenness`,
  `test_the_paper_is_not_counted_as_unevenness`,
  `test_an_absolute_sheet_keeps_its_aims_as_designed`,
  `test_aims_on_the_paper_is_one_scale_for_every_patch`,
  `test_the_help_text_says_evenness_is_read_as_measured`.
* **Proof:** on screen, run8 of the evenness demo: dates 2026-10-08 and
  2026-10-15 judged (blotch: from-the-mean FAIL 1.17, noise 0.24 / 0.14);
  `e8_before_after.txt`, `e8_three_ways.txt`.
* **Status:** agreed; built; awaiting confirmation.

### 21.2 B8-483: the grey ramp's required steps are roughly evenly spaced

**Record.**
* **Rule:** *"pick the required number of steps out of a longer neutral ramp
  so that they are roughly evenly spaced, within a few percent of full scale,
  so the chosen steps are not bunched together. Build it that way? … Yes."*
  His original words (5775993270): *"the patches that represent the minimum
  number should be picked out from the existing neutral grey patches, and
  those should have an approximate even spacing, else the outer black and
  white positions can be fulfilled, but the patches between them cramped into
  lumps"*.
* **Built as** (`pick_even_grey_steps`, asked after the three existing
  conditions of §3):
  * m positions evenly spaced from the ramp's own darkest to its own lightest
    grey level (the end rules, ≤ 10 and ≥ 90, are unchanged);
  * for each position, the nearest grey level on the chart, which must lie
    within **`GREY_SPACING_TOL` = 4.0 device units, i.e. 4 % of full scale**
    of it (inclusive) and be a different level from the pick before;
  * m starts at the required 8 and the first m that works is taken, up to the
    number of distinct levels. More than 8 is allowed because a perfectly
    even 11-step ramp (0, 10 … 100) holds no 8 steps within 4 of an 8-step
    spacing (14.3 is 4.3 from both 10 and 20) and is not bunched;
  * so two neighbouring picks are never more than 100 / 7 + 2 × 4 = **22.3 %**
    of full scale apart on a full ramp, the ceiling proposed to him on
    2026-09-22 (5776479532);
  * a ramp that fails reads N-A on both grey rows with the new reason
    `grey_steps_bunched`; the note names the level nothing is near (*"none lies
    within 4 of the level 13.4 on a scale from 0 (black) to 100 (white)"*),
    and the presets window says *"The grey steps on this chart are bunched
    together"*. It is a patch shortfall, so it decides the star;
  * **the statistics are unchanged**: the average and largest ΔCh still run
    over every grey patch (§3). The picked levels are recorded in the block
    (`picked_levels`) and decide only whether the ramp meets the step rule.
    Whether the figure should be taken over the picked steps only is an open
    question.
* **Measured:** all 181 built-in charts that had an eligible grey ramp keep
  it (at 3, 4 or 5 alike); the demo pack's Q1 chart (0, then seven steps
  within 90.0 to 93.6) is refused and is now requirement R14's FAIL side.
  The demo charts whose ramps were uneven by accident (the pairs R05 to R10,
  R08's ramp, the surface pairs' ramp kept off the cube faces, and Q2) were
  re-spaced so each pair still moves one requirement only
  (`make_verification_preset_demos.py`, whose `--check` reads 14
  requirements, 32 presets, 0 not doing what they claim).
* **Built:** `workflow/measurement_report.py::GREY_SPACING_TOL`,
  `pick_even_grey_steps`, `grey_balance_block`, `REASON_GREY_STEPS_BUNCHED`;
  `workflow/preset_eligibility.py::PATCH_SHORTFALL_REASONS`;
  `ui/dialogs/preset_verification_dialog.py::reason_line`;
  `ui/dialogs/measurement_report_dialog.py::_reason_sentence` (one entry);
  `workflow/compliance_sets.py::_D_GREY_RAMP`, `_R_GREY_RAMP`.
* **Verified by:** `tests/test_beta39_k28a.py::`
  `test_a_bunched_ramp_is_refused_and_says_where`,
  `test_an_even_ramp_with_more_steps_than_required_passes`,
  `test_the_tolerance_is_four_and_inclusive`,
  `test_the_statistics_still_cover_every_grey`,
  `test_no_built_in_chart_loses_its_grey_rows`,
  `test_the_help_text_quotes_the_tolerance`,
  `test_the_na_note_names_the_level_and_tells_nothing_to_do`,
  `test_the_presets_window_counts_it_as_a_patch_shortfall`;
  `tests/test_the_demo_presets_pair_on_every_requirement.py` (R14, and an
  independent reimplementation of the rule).
* **Proof:** on screen, "Which presets can be used for verification?" on the
  R14 FAIL and PASS presets and the control, with the picked steps.
* **Status:** agreed; built; awaiting confirmation.

### 21.3 R2: the pre-flight is widened to show the full paragraph

**Record.**
* **Rule:** R2 (5781645939): *"The popup window can be made wider, so that it
  does not become as tall, and no scrolling is needed in that window. The
  current text shown in beta 34 was ok."*; asked again with a shorter
  paragraph at 810 px or today's at 970 px: *"Leave the window wider as
  previously specified."*
* **SUPERSEDES** the one-line pre-flight of §19.7 (B8-773) wherever the screen
  can hold the wide box.
* **Built as:**
  * where the chart falls short, the pre-flight carries the FULL
    M-VERIFY-UNCHECKED-METRICS paragraph (its heading and body, the presets
    window's own text) in place of the one line;
  * the box wraps its text at `PREFLIGHT_TEXT_WIDTH` = 920 px (a box 968 px
    wide), held inside Qt's own width ceiling (screen width − 480, less the
    margins) so the text is never broken mid-word;
  * **the 13-inch guard.** Once the box is on screen, its frame is compared
    with the screen's work area; if it does not fit, the one line goes back
    in (the beta 38 popup). Asked of the SHOWN frame because the size hint
    before `exec()` read 683 px for a frame that opened at 827.
* **Measured on screen** (this machine, work area 1079 px): English 968 × 827
  px, German 968 × 875. A 13-inch MacBook Air has about 918 px of work area
  with the Dock hidden or at the side, so both fit; with the Dock at the
  bottom about 860, where English (827) fits and German (875) falls back to
  the one line (driven with the guard handed 860: German frame 731 px, the OK
  button and the tick on screen). Qt's width ceiling on a 1470 px wide Air is
  990 (derived from the ceiling measured here, not measured on an Air), so
  the 968 box fits its width.
* **Built:** `ui/tabs/tab_measure.py::PREFLIGHT_TEXT_WIDTH`,
  `preflight_text_width`, `_preflight_fits`,
  `_verification_preflight_message(short=)`,
  `_show_verification_preflight_now`.
* **Verified by:** `tests/test_beta39_k28a.py::`
  `test_the_width_is_held_inside_qts_own_ceiling`,
  `test_a_screen_too_short_for_the_wide_box_gets_the_one_line`,
  `test_the_popup_is_widened_and_guarded`;
  `tests/test_knuts_two_warnings_of_2026_09_22.py::`
  `test_the_preflight_says_it_too_when_the_chart_falls_short` (rewritten: it
  asserted the one line).
* **Proof:** photographs of the whole popup, English and German, and the
  German fallback at 860 px.
* **Status:** agreed; built; awaiting confirmation.

### 21.4 The ChromIQ folder's own old/ in "Where are my files?"

**Record.**
* **Rule:** *"Deleting a report across projects moves it to <ChromIQ default
  folder>/old/<date>/ … Is that the right place? Answer: Yes. This
  outside-of-project folder also needs to be visible in the help card for
  'Where are my files?'"*
* **Built as:** the folder diagram gains a root "Your ChromIQ folder/"
  (~/ChromIQ or the custom output folder) with `reports/` (reports across
  several projects) and `old/` (such a report after "Delete Selected Report",
  in a folder named with the moment). The project's own `old/` (a report
  across several of its runs, deleted) was missing from the diagram and is
  added beside it. The files table's cross-project row names the old/
  destination too.
* **Built:** `ui/file_guide.py::_structure`, the files table.
* **Verified by:** `tests/test_beta39_k28a.py::`
  `test_the_folder_guide_shows_the_chromiq_folders_own_old`.
* **Proof:** on screen, the card scrolled to the rows, English and German.
* **Status:** folder agreed; the help card rows built; awaiting confirmation.

## 22. K28: what a report shows (#182, 2026-09-23, beta 39)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5795087247](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5795087247),
answering 5794332548 (the questions of 5784140521, renumbered); our reply
5795122579. The rulings are agreed from that day; what was built from them
(B8-849) waits for his confirmation. Proof: `~/Desktop/ChromIQ-beta39-proof/k28-b/`
(REPORT.md, EN and DE, on screen, with PDFs). Tests:
`tests/test_k28b_one_vocabulary.py`, each proved red on the mutation in its
docstring. This section SUPERSEDES the clauses marked so in §4, §15.6, §18.4,
§19.3 and gaps G1 to G4 and G6 of §20.

**21.1 The one-page summary uses the judged figures, and says so.** *"Yes, and
the reports need to show that the figures judged are within-gamut."* The
one-page result line prints `graded_de00` (within the profile's gamut where the
sheet was split by it) and counts "{n} of {total} patches"; the sentence under
it adds *"The judged figures are those of the patches within the profile's
gamut."* The full report's results intro says the words judge the within-gamut
figures only where a row shown uses that split (the five ΔE00 rows and the two
evenness rows) and the type grades: not on a Grey and tone check, not on a
Printing record. The graph says it in its description (§18.4).

**21.2 One vocabulary.** *"all metrics in report, in graphs and in Report Limits
window, and in all help texts, use the same label/name ... The text can mention
in parenthesis that lowest 95 % is 95th percentile."* The five names, in
i1Profiler's order with the unit:

| row | name |
|---|---|
| `all_de00_avg` | Average ΔE00, all patches |
| `best95_de00_avg` | Average ΔE00, lowest 95 % |
| `worst5_de00_avg` | Average ΔE00, highest 5 % |
| `all_de00_max` | Maximum ΔE00, all patches |
| `all_de00_p95` | Maximum ΔE00, lowest 95 % (95th percentile) |

They live in `compliance_sets.ROWS` only; the Report Results grid, How to
read, the detailed tables, the Overview, the graph legends, the Report Limits
window, the presets window, the notes and the one-page summary read them from
there (the parallel tables `_METRIC_LABELS`, `_TREND_ACCURACY_LABELS` and the
"all judged patches" variants are gone). A legend does not add "(ΔE00)" to a
name that carries it. The help texts (graph descriptions, the window guide,
the help card glossary, the N-A sentences, the presets window) say "lowest
95 %" and "highest 5 %". The other rows keep their labels, one per row, from
the same table; whether they should take the same word order is asked (B8-849).

**21.3 A "–" limit removes the row everywhere.** *"Yes"* (the Overview too). A
row whose limit is "–" is not in Report Results, How to read, the detailed
table, the Overview, or the Colour accuracy graph, whose Avg / Max limit line
is not drawn for a "–" member either (`legacy_pair` would draw 2.0 / 3.0). It
applies on every type, the Printing record included. Nothing is counted
differently: the Overall word and "X of Y checked" count limit-bearing rows
only.

**21.4 "For information (no limit applies)".** *"keep them under a heading 'For
information (no limit applies)'"*. The Overview carries the heading as a block
row above Spread, Paper white L\*, Black L\* and the eight corner ΔE00; the
detailed table carries it as a row above Spread, and the detailed section as a
heading above paper white and the cube corners; the one-page summary's corner
table is headed "Cube corners, for information (no limit applies)".

**21.5 The general N-A rule.** *"Any limit set selected shall stop showing rows
no chart can answer, only if the metric/row for a selected limit set has '-'
for its limit. If the limit set has defined a threshold value for that
metric/row, then the report shall continue to show those rows ... as N-A and
with a superscript number as reference to a note ... This is the general
rule."* It holds for every set and supersedes R3 (G6, never built). *"The
reference numbers on all N-A results ... this is the information stating what
was left out. Thus no other info needs to be repeated after that. This also
applies to the one-page summary."* and *"Keep option 1. Only use A4."* No
report lists the unchecked rows apart from the notes (checked: "Measured but
not graded" names INFO rows, not N-A ones; the D25 strip is a window control,
not report text); the unused one-page list (`_unchecked_rows_for`) is deleted.
The rows a note covers are joined by "; ", because the names now hold commas.

**21.6 Several runs or projects: the Run description (B8-798).** *"The report
should under the 'Run Description' heading inform the user that the report
includes data from multiple runs (or multiple projects ...), thus not written
here. Then refer back to the Scope section."* The document's own measurements
decide: one run prints THAT run's description (not the window's); several runs
print *"This report includes measurements from several runs, so no single run
description is given. The list below shows the measurements included."*;
several projects the same with *"... from each project."*

**21.7 B8-845's report texts (K18, K22).** `no_earlier_measurement` ends at
*"so there is nothing to compare it with"*; `evenness_empty_area` says *"holds
no measured patch with an aim value"* (and *"within the profile's gamut"* on a
split sheet); a measurement with no device values gives its grey, ramp and
gamut rows the new reason `no_device_values` (*"the measured chart carries no
device values (the RGB numbers each patch was printed from)"*) instead of
`not_computed`; the guide's INFO bullet no longer names "no limit on the row"
and, on a report that judges nothing, says so instead of promising a note; the
N-A bullet points at the raised number. The Printing record keeps its Limit
column (§18.3, "Judged against" defines the thresholds shown).

**Built:** `workflow/compliance_sets.py::ROWS`;
`ui/dialogs/measurement_report_dialog.py` (`_drop_dash_rows`,
`_dash_row_ids`, `_accuracy_thresholds`, `_comparison_table_html`,
`_run_detail_html`, `_one_page_html`, `WITHIN_GAMUT_ROWS`,
`_run_description`, `_several_places_notice`, `_reason_sentence`,
`_how_to_read_html`); `workflow/measurement_report.py::build_report`
(`REASON_NO_DEVICE_VALUES`).
**Status:** agreed; built in beta 39; **not confirmed**.

## 23. #182 S-2: the ISO 12647 values are prepared to ship, values only (2026-09-23)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**The decision.** DIN's legal department answered the owner in writing on
2026-09-23, about ISO 12647-8 and as a statement of the general rule:

> *"wenn Sie definitiv nur Werte aus der Norm verwenden – keine Bilder, keine
> Seiten, keine Texte, dann fällt das nicht unter Vervielfältigung."*
> (If you definitely use only values from the standard, no images, no pages, no
> texts, that does not count as reproduction.)

The owner delegated the decision and agreed that it covers ISO 12647-7 and
ISO 12647-8 alike. So Sebastian's S-2 is answered in principle: both sets may
ship **as values only**, in `data/compliance_sets/iso12647.json`, under
ChromIQ's own row names, help texts and layout, with no wording, table, figure
or clause text of either standard. **Filling the file waits on the owner's
explicit go-ahead**; everything else is built so that it is the only step left
(`scripts/install_iso_12647_values_into_repo.py SOURCE.json [--set 7|8]`, which
copies only the two set objects, keeps the file's own `_readme`, refuses half a
set, and prints counts and True/False, never a value). Until then the file's
two sets are empty and the app behaves exactly as before.

**The file.** Each set is EMPTY or COMPLETE: only row ids that standard limits
(`compliance_sets._ISO_ROWS`), every row ChromIQ can judge present, and every
cell a number or `[number, "should"]`. A row ChromIQ cannot measure reads `✕`
whatever it holds, so it may be left out. Its `_readme` quotes DIN's sentence
with a translation.

**What a set that ships changes on screen** (driven with a file of made-up
placeholder numbers standing in for the shipped one; proof below):

1. Its read-only column carries a number on every row ChromIQ can judge, and
   it becomes a choice in the Measurement Report's "Judged against" pulldown
   and for a run. A set that does not ship reads `?` and is not a choice.
2. **The Custom column beside it does not move.** It keeps Knut's researched
   industry figures and ChromIQ's own numbers (§2a). §2a's first source, "a
   licence holder's own values file", is read literally: a shipped value is
   not one, so it fills the read-only column and not the Custom one
   (`compliance_sets.supplied_iso_rows`). This narrows §2's "a Custom set
   starts from its parent's value where the parent HAS one".
3. **A licence holder's own file is laid OVER the shipped one, row by row**,
   where it used to be read instead of it. A number they give wins its row; a
   row they leave null (the template writes one per row) keeps the shipped
   figure; their figures still become the Custom column's starting numbers.
   Reading their file instead would have taken every shipped figure away from
   someone who supplied three rows of the other set.
4. The texts that said ChromIQ ships no ISO values say what ships. Where the
   text is generated, it asks `compliance_sets.shipped_iso_sets()`:
   the Report limits window's column paragraph (one clause per ISO column:
   ships, supplied, or empty) and its note on the Custom columns; the first
   line of the ISO half of "Reference values"; the reason a greyed ISO report
   type gives (the paywall reason only while that standard's values do not
   ship). Where the text is static (help card glossary, "Where are my files?",
   the Report type help in Preferences, the pairing help, the Reference values
   steps), it is rewritten as a condition that is true in both states.
   M-THRESHOLDS-NOT-CERTIFICATION is revised the same way (§M-PROPOSED).

**Not changed:** the certification promise and the standard caveat (a column
named after a standard is still applied to the printed chart, and a PASS is an
indication, not proof); the two ISO report types stay unbuilt; the template a
licence holder saves stays all nulls.

**Built:** `data/compliance_sets/iso12647.json` (`_readme` only; both sets
empty), `data/compliance_sets/README.md`, `data/compliance_sets/LICENSE`;
`workflow/compliance_sets.py` (`_bundled_iso_path`, `_load_iso_numbers`,
`supplied_iso_rows`, `shipped_iso_sets`, `factory_limits`,
`custom_default_counts`, `iso_values_template`);
`ui/dialogs/thresholds_dialog.py` (`_columns_paragraph`,
`_iso_columns_sentence`, the Custom note); `ui/dialogs/reference_values_dialog.py`
(`iso_source`); `ui/dialogs/measurement_report_dialog.py` (`_not_built_line`,
`_PAIRING_HELP`); `ui/dialogs/settings_dialog.py`; `ui/dialogs/welcome_dialog.py`;
`ui/file_guide.py`; `workflow/measurement_messages.py`;
`scripts/install_iso_12647_values_into_repo.py`.
**Verified by:** `tests/test_iso_values_ship_as_values_only.py` (the file is
empty or complete; a shipped set judges its read-only column and leaves the
Custom one on Knut's figures; a licence holder's number wins its row and a null
keeps the shipped one; the texts in the empty, one-set and both-set states; the
install script), each guard proved red on a mutation; the older emptiness tests
in `test_compliance_sets.py`, `test_a_custom_column_is_not_a_standards_column.py`
and `test_the_limits_window_says_what_its_columns_hold.py` now hold whichever
state the file is in. No test asserts a value of either standard.
**Proof:** `~/Desktop/ChromIQ-beta39-proof/iso-12647-ships/` (REPORT.md; on
screen, EN and DE; the repository file as it is, and one pass with placeholder
numbers standing in for a shipped ISO 12647-8).
**Register:** B8-851.
**Status:** the values SHIP (filled 2026-09-23 on Knut's yes, #182
5798461562, with `scripts/install_iso_12647_values_into_repo.py`: 18 cells for
ISO 12647-7, 19 for ISO 12647-8); the suite holds both states (the empty one
by fixture, `tests/helpers/iso_files.py`); the demo pack has runs bound to
both read-only columns, designed from the file at build time; driven on
screen after the fill (`~/Desktop/ChromIQ-beta39-proof/iso-12647-ships/after-fill/`);
**not confirmed**.
## 24. K30: every loaded report can be generated again, limits belong to the report, projects in two folders, and the words of a report across places (#182, 2026-09-23, beta 39)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5798461562](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5798461562)
(2026-09-23), answering our 5794100213 / 5795122579 questions; and the
challenge rounds A and B of beta 39 (`~/Desktop/ChromIQ-beta39-proof/challenge-A-behaviour/`,
`challenge-B-text/`). The rulings are agreed from that day; what was built
from them (B8-852 to B8-859) waits for his confirmation. Proof:
`~/Desktop/ChromIQ-beta39-proof/k30/` (REPORT.md, EN and DE, on screen,
with PDFs). Tests: `tests/test_k30_rulings.py`, each proved red on the
mutation in its docstring (`k30/mutations.txt`). This section SUPERSEDES the
clauses marked so in §13.11, §13.13 and §18.12.

**24.1 A loaded report can always be generated again.** *"The reports
settings are loaded, and the user should be able to modify the settings and
select Generate Report, which then gives a popup window where user can choose
to update selected report or create a new report, or cancel. This is the
standard behaviour I have specified for all reports that are loaded, also
those loading when report window is opened."* Since G7 (§13.13) no path greys
Generate for a loaded report because it spans places; the one that remained
for a report across projects (projects in two folders) is gone with 24.4.
Driven: a Calibration window opens on its newest report ("All cals" in the
demo pack), Generate is live, a press with nothing changed asks
(M-REPORT-UNCHANGED-UPDATE-OR-NEW) and Cancel writes nothing; with a setting
changed it asks M-REPORT-UPDATE-OR-NEW. The window still opens on the most
recent report (*"No. Open on most recent report."*). Generate is still greyed,
each time with its reason, for: a measurement outside every ChromIQ project, a
profiling sheet and verifications ticked together (FC-2), ticks all in
another place, under Calibration a profile run's measurement ticked (24.8),
and a calibration whose measurement is not on disk (24.8).

**24.2 Update renames the report.** *"If update is chosen, then name of the
report is updated too, according to the settings, as per standard
behaviour."* It already was: the scope flag is worked out from the
measurements the press covers (`_document_scope`), so an "All cals" report
updated with one project unticked is named "Multiple cals", with the
"updated" stamp of §13.8. Pinned by a test and driven.

**24.3 Limits belong to the report, across places.** *"Why is editing limits
is per run? I have not specified this. I have specified the opposite that all
settings belong to a report, not a specific run"*. With measurements of more
than one place loaded, the limits button is live and reads "Edit limits…";
the Report limits window's first column is **"This report"**, editable, and
its **"Used for this report"** row picks the report's set. A change binds,
unlocks and rewrites no run and no saved report: it is the report's own
limits for the session, the red line comes up, and Generate report writes
them into the document (`compliance.thresholds`, `edited`), asking Update /
Create New / Cancel when a report is selected. The Colour accuracy graph's
Avg / Max lines follow the report's limits (they followed the window's run).
Choosing another set in "Judged against" drops the edited numbers.

> **⚠ NOT DECIDED: THE WINDOW WITH ONE PROFILE RUN.** With one place loaded,
> the limits window still edits THE RUN's limits, and "Judged against"
> still binds the run, as §5 builds them. Moving that to the report too would
> change behaviour Knut confirmed on 2026-09-23 (§19.6 "Unlock this run's
> limits", §19.13 "New report… on a bound run shows the run's own set"), which
> this round may not decide. It is asked of him (B8-853).
>
> **DECIDED by K31 (§25.3, Knut [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743)):** with one profile run
> loaded too, the limits window is the report's ("This report"), and
> "Judged against" binds nothing. §19.6 and §19.13 are superseded with it.

**24.4 Projects in two folders share the ChromIQ folder's `reports/`.** *"I
propose that the ChromIQ default folder is always used, in this situation, no
matter if one of the projects, or both, are kept is sub folders of ChromIQ
default folder."* A report of projects side by side in one folder stays in
that folder's `reports/` (§13.11, §18.8); a report of projects in different
folders is written to `<ChromIQ folder>/reports/` (Preferences' output folder,
else `~/ChromIQ`), is listed and counted from there, its PDF is offered there,
and Delete moves it to `<ChromIQ folder>/old/<stamp>/`. The refusal "the
projects are in one folder" is gone. "Where are my files?", the help of
"Report shown" and the help of "Included measurements…" say so.

**24.5 A lone project carries its heading.** *"ok"*. In a Calibration window
whose list holds one project's calibration and offers no report of another
project, that project's reports sit under a heading with its name. Profiling
and Verification keep §13.12's rule (one run, no heading).

**24.6 A "–" row leaves every report type.** *"Yes, all report types. It was
a general rule."* Confirmed of the code (the Printing record included) and
pinned by a test.

**24.7 The words of a report across places, of a calibration, and of what a
row judges (challenge B).**
* B1: several runs or projects, "This report judges the profiles built in
  P, run 1; P, run 2. Each was verified … The measurements it covers, and the
  profile run each comes from, are listed under Report Scope."; the title
  names every chart when they differ across places.
* B8: across places, Report Scope lists one line per place ("P, run 1
  (P-verify)"), so the several-runs notice can be answered from it.
* B2 / B10: a calibration's report is titled "Measurement Report -
  Calibration of Printer" (a third Preferences line, "Calibration
  measurements:"); its Scope says "The following calibration measurements are
  included: P, calibration · 1 measurement".
* B3 (§22.1): How to read says the verdict words judge the within-gamut
  figures only where a row shown is fed by the split and the type grades; the
  detailed table puts a row that counts every patch (grey balance, ramps)
  under "All patches", and its note under the table says "The Result judges
  the within-gamut figures" only where a row in it uses the split.
* B4 (§17 item 4): a Printing record's Colour accuracy graph draws no limit
  line and its description calls the patches measured, not judged.
* B7 (§19.1): "This verdict was recorded against the limit set X when the
  report was made."; "These figures show how one profile holds up over
  time …"; the detailed intro no longer tells the reader to tick a checkbox.
  The German heading "So liest du diesen Bericht" became "So ist dieser
  Bericht zu lesen" (no "du" in report text).
* B9: the "Worst patches" heading is the first row of its table, which does
  not break across a page.
* B11 (German, Measurement Report texts only): Testchart (never Testform),
  Zielwert (never Sollwert), Anmerkung for a numbered note (never Hinweis),
  "innerhalb des Profil-Gamuts".
* B6: the Report limits intro speaks of the one "Reference values…" button
  below, in English and German. Since the ISO values ship (§23) the sentence
  is shown only when neither ISO set is selectable.
* B5: the release demo package's run descriptions and README use the §22.2
  names, explain no ChromIQ control, state the project count once and point
  at `scripts/make_release_demo_package.py`.

**24.8 The Calibration window (challenge A).**
* F3: a calibration stores no type, so the line "The runs loaded here were set
  to different report types…" no longer appears in a Calibration window.
* F4: a profile run's measurement ticked beside the window's own calibration:
  Generate stays greyed (a calibration report covers calibrations only) and
  says so, not "Every ticked measurement belongs to another profile run".
* F5: a calibration whose measurement is not on disk (moved to `cal/old/` by
  a new chart) opens with its saved reports listed and openable; Generate is
  greyed with its reason; a window with nothing loaded has no live "Unlock
  this run's limits".
* F6: the orange strip names every row the page cannot answer, on every sheet
  it shows, not the window's own sheet only.

**24.9 The window after challenge C (RW-fix, B8-880 to B8-886).** Not a
new ruling: the rules above and §13.13 / §17, made true where challenge C
found them false. Awaiting confirmation with the rest of this section.
* "Report shown" names what the window holds: the loaded report, or "New
  report…" with the Preferences defaults. After a Delete the entry the list
  lands on is loaded whole; picking the entry the list is already on loads
  it when the window does not hold it.
* Every greyed Generate report says why, in its tooltip and on the line
  beside the buttons, including an empty list and a list with nothing
  ticked.
* No button of the report window, the Report limits window or the
  Reference values window answers Return.
* An Update over the same measurements keeps its scope flag; a change of
  membership still renames it (24.2).
* "Already generated for this run" and the "(runN)" labels only while
  everything counted or ticked is that run's; otherwise "for these
  measurements" and no run name. A calibration's row counts measurements.
* A Grey and tone check draws no Colour accuracy limit line: it judges no
  colour-accuracy row (§17 item 4).
* A report of a run whose measurements another report had borrowed keeps
  them when it is picked, and a measurement the user adds is the user's;
  Generate never writes a loaded report as a new one without the question
  (K4).

**Built:** `workflow/measurement_report.py::chromiq_folder`,
`document_home`, `across_places_refusal`, `shared_report_folders`;
`ui/dialogs/thresholds_dialog.py::ReportLimitsColumn`, `report_column`;
`ui/dialogs/measurement_report_dialog.py::_open_report_limits_window`,
`_sticky_limits`, `_doc_settings`, `_thresholds`, `_sync_limit_controls`,
`_grouped_documents`, `_types_of_loaded_runs`, `_sync_type_combo`,
`_mismatch_text`, `_report_kind`, `_places_of`, `_what_this_report_judges`,
`_report_profile_name`, `_report_title`, `_scope_html`, `_how_to_read_html`,
`_run_detail_html`, `_trend_plan`, `_trend_extras`, `_verdict_provenance`,
`_report_dir`, `_a_calibration_with_saved_reports`;
`ui/dialogs/tools_dialogs.py::_report_seed`; `core/settings.py`
(`report_title_calibration`); `ui/dialogs/settings_dialog.py`;
`ui/file_guide.py`; the demo generators (B5).
**Status:** agreed; built in beta 39 (B8-852 to B8-859), NOT confirmed.

## 25. K31: a report is the only thing there is, and its limit set is its own (#182, 2026-09-23, beta 40)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743)
(2026-09-23), answering our post
[5798697107](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5798697107)
(sections 0b, 0c, 0d, 1, 2 and 8) and our reply 5801707986; and
[5801750910](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801750910)
for the help texts. Where he answered *"Agreed."* to a proposal of ours, the
proposal is his ruling from that day and is quoted as such; what was BUILT from
it (B8-890 to B8-899) waits for his confirmation, and so do the decisions in
§25.6, which are ours. Proof: `~/Desktop/ChromIQ-beta40-proof/k31-a-report-model/`
(REPORT.md; on screen, English and German, with file listings, size and sha1,
before and after every press). Tests: `tests/test_k31_report_model.py`, each
proved red on the mutation in its docstring (`mutations.txt` in the proof
folder).

This section SUPERSEDES: §5 (a run bound to a set, the lock, the
recalculation), the K23 verdict records of §13.11 (and the "Delete leaves each
date's verdict record" half of its K25 record), the G7 records and the
"window's own run" rule of §13.13, §19.6 ("Unlock this run's limits"), §19.13
("New report…" on a bound run) and the open one-run clause of §24.3 (B8-853).

**25.1 A report is the only thing (sections 1 and 8 of our post).**
* *"Should a report of several measurements stop writing verdict records
  altogether?"* **Agreed.** *"When a report covers more than one run or
  project, should GENERATE REPORT write anything into the dates' own
  folders?"* **Answer: no.**
* Built: a report of ONE measurement is one file in that measurement's own
  `reports/` folder, as before. A report of SEVERAL is one document file in
  the folder `document_home` names (§13.11, §24.4), and each of its
  measurement entries carries that measurement's verdict against the report's
  set (`judged`: `pass_thresholds`, `compliance`, `verdict`). Nothing is
  written into the measurements' own folders, in any run or project.
* The report ChromIQ writes by itself after a measurement is that date's own
  report of one date, with the starting choice's settings (§25.5). A
  measurement binds nothing and writes nothing into the run's `meta.json`.
* Everything that read "the newest file in a date's folder" (the date's own
  row, the trend graph, the bar, "Already generated") reads the date's own
  report: a verdict record is never that file (§25.6).

**25.2 Update and New report from any window (section 0b / 0d).**
* *"With a report selected, may GENERATE REPORT > Update rewrite that report
  where it lives, whichever profile run the window was opened from?"*
  **Agreed.** *"With 'Create New', or 'New report...', and only another run's
  dates ticked, may the new report be saved where those dates decide?"*
  **Agreed.**
* Built: the filter that kept only the window's own run's rows is gone. What
  Generate covers is what is ticked; where it saves is decided by the ticks.
  It is still refused (greyed, with its reason) for: nothing ticked, a
  measurement outside every ChromIQ project in a report across places, and
  under Calibration a measurement that is not a calibration.
* Knut's case, driven: a window opened from run 2, run 1 added, run 1's
  report of one date selected, only that date ticked, Update: that report is
  rewritten in run 1's own `reports/` folder, its previous version in
  `reports/old/<stamp>/`, and no other file anywhere changes.
* *"that is the logical thing, if a user chooses to update the automatically
  created reports of one date."* A report of one date updated to cover more
  dates becomes a report of those dates: it keeps its id, it is written where
  the dates decide, its name follows ("Multiple dates", "All dates", or the
  run and project names across places), and its one-date file is archived
  into that date's `reports/old/<stamp>/` and taken out of the live folder,
  never deleted. When that file is the date's ONLY own report, the report
  of one date stays and the widened report is a new one (§25.7, Knut
  5806297940).

**25.3 The limit set belongs to the report (section 0c; G7 Q2).**
* *"changing the reports settings does not change the report, and its
  binding to a limit set, unless you click Generate Report"*; *"Go for option
  (a) One set for the whole report, always."*
* Built: "Judged against" and "Edit limits…" change only the settings of the
  report shown, in memory; the red line says to press Generate report, and
  nothing is judged again or written until then. The limits window always
  opens on the report's own column, "This report", beside every set, with the
  "Used for this report" row choosing its set, whether one profile run or many
  are loaded. Every ticked measurement is judged against the report's one
  set, within one run too: a date whose own report was judged against another
  set is judged again against the report's set on the page and in the file.
* Closing the limits window with nothing of the report's changed leaves the
  report's settings as they were: a "Judged against" change made before
  opening it still counts, the red line stays, and Generate asks the
  "settings changed" question (found on screen in the beta 40 drive, where
  the close re-rendered the page and took the change as the new baseline).
* What the window may still write, neither of which is a report's setting:
  which COLUMNS the limits window shows (a view setting remembered per profile
  run, K-b), and the run's own default for new reports (§25.5).
* **Correction for Knut to confirm (B8-943, beta 40 challenge B, 4).** The
  list above left out the Preferences half of the window, which the window
  has always written: the columns beside "This report" are the app-wide sets,
  and a number changed there, or a click on the **"Default for new reports"**
  row, is stored in Preferences, Reports at once, exactly as from Preferences
  itself, before Close and without Generate report. No saved report changes
  by it, and the report on screen does not either (its set is its own). The
  "Edit limits…" tooltip said *"A change applies to this report only"*, which
  was true of the first column only; it now says both halves: a change in
  "This report" applies to this report only and is applied by Generate
  report, and the other columns and "Default for new reports" are the
  settings of Preferences, Reports, stored at once. The "Default for new
  reports" radios opened from a report say the same in their tooltip. We kept
  the behaviour and made the text true, rather than hold the Preferences
  click until Close, because the columns beside it (the same Preferences
  sets) have always written at once, and one half of the Preferences
  settings waiting for Close while the other half does not would be a second
  rule to learn.

**25.4 "Unlock this run's limits" and the run lock are removed (section 2).**
*"I agree that the 'Unlock this run's limits' is no longer needed."*

* **What the lock protected.** Until K31 a profile run was BOUND to a limit
  set at its first verification (a copy of the set's numbers in
  `runs/runN/meta.json`) and LOCKED from its second, so every dated
  verification of the run was judged against the same numbers and the run's
  history stayed comparable: a later change of "Judged against" could not
  quietly make an old date's PASS a FAIL, because the only way to change the
  set was the unlock box and its question, which recalculated (and, after
  2026-09-17, archived) the saved reports.
* **Why it is no longer needed.** Comparability is now a property of the
  REPORT, not of the run. A report carries its own set and the verdicts it
  gave (§25.1), judges every measurement it covers against that one set
  (§25.3), and is never recalculated by a later change of any set (Knut,
  2026-09-17, §5's banner). So the dates inside one report are compared on
  the same numbers by construction, and a saved report cannot be changed by
  anything but its own Update. With no verdict records left in the dates
  (§25.1) there is no second copy of a verdict that a set change could make
  disagree with the report.
* **What was removed.** The checkbox "Unlock this run's limits" and its help
  icon; the two question windows it raised (recalculate the run's saved
  reports, put the lock back); the Preferences option "Allow editing of
  thresholds after the first verification measurement" (`compliance_allow_
  edit_after_measurement`, no longer written or read); the binding of a run
  at its first verification (`bind_run`, `ensure_bound`); the lock
  (`is_locked`, `may_unlock`, `set_run_unlocked`) and the run's own edited
  column (`set_run_limits`); the recalculation of a run's saved reports; and
  every sentence about binding and locking in the tooltips, the help icons,
  the window guide, the Dictionary ("Bound (a run's limits)", "Locked /
  Unlock this run's limits"), the verification card and Preferences.
* **What a user loses.** (1) A run no longer forces its dates onto one set:
  if the Preferences default changes between two measurements, the automatic
  reports of those two dates are judged against different sets. Each is
  still that date's own report, saying what it was judged against, and any
  report of both judges both against one set. A run's own default (§25.5)
  keeps one run's new reports on one set when that is wanted. (2) A run
  cannot carry edited numbers of its own any more: edited numbers belong to
  a report ("This report"), or to a Custom set in Preferences for use across
  reports. An older run's edited copy is still read, as that run's starting
  numbers, until a default is chosen for it in Edit limits. (3) Nothing stops
  a user making a report of a run's dates against another set; that is the
  point of the ruling, and the reports already saved are not changed by it.
* **Old files.** A `meta.json` written by an earlier ChromIQ reads without
  error: `compliance_bound_at` and `compliance_unlocked` are ignored, a stored
  set is the run's default for new reports, and its stored copy is used as
  that default's numbers.

**25.5 Where "New report…" starts.** *(A1 of 5802027116, the run's own
default, "(a)": decided by Knut, 2026-09-24, [5817809396](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817809396), as built here.)* *"the starting choice for 'New
report...' should be the the defaults in preferences -> reports first, then
the default in the Edit limits for that run, if it changed to be different
from the preferences default."*
* The limit set: the run's own default when it has one, else the Preferences
  default set. The run's own default is chosen in the Report limits window's
  row **"Default for this run"**, shown when the window is opened from a
  report of one profile run (with several runs loaded there is no one run to
  give a default to). **"One profile run" is the report's (B8-940, beta 40
  challenge B, 1):** every ticked measurement lies in that run. A Profiling
  window lists every run's sheet of its project from one source, so the row
  was shown, and live, for a report of three profile runs; it is now hidden
  whenever the ticked measurements lie in more than one run (or a measurement
  in no run is among them). The "Judged against" help says so: *"When every
  measurement ticked is of one profile run, it also sets which limit set new
  reports of that run start on."* Choosing the same set as the Preferences default clears
  the run's own, so the run follows Preferences again. The row writes only
  that run's `meta.json`; no report changes. The Preferences row is now
  called **"Default for new reports"** (it was "Default for new runs").
* The report type: always the Preferences default ("Report type, default"),
  fitted to the kind of measurement. A run's stored type (an earlier
  ChromIQ's) is read only to name a report that recorded no type of its own.
* The same starting choice is what the automatic report after a measurement
  uses (§25.1).
* The "Judged against" tooltip under "New report…" says which applies: the
  run's own default and where it was chosen, and the Preferences one.

**25.6 Decisions of ours under the ruling, for Knut to confirm.**
* **Records already on disk are read-only history.** A verdict record written
  by betas 37 to 39 is never a date's own row, never listed or counted, and
  never rewritten, moved, archived or deleted, not even by an Update of the
  report it belongs to (which then carries every verdict itself). It still
  speaks for its report while that report is loaded and has not been
  updated, as before. Deleting a record would lose a verdict a customer may
  have been given; moving it would change nothing the user sees.
* A Profiling window whose default ticks cover every run's sheet makes a
  report across runs when Generate is pressed without changing the ticks
  (its home is the project's `reports/`), as K25 asked of the ticks.
* A "New report…" whose ticks are all another run's starts on the window's
  run's own default, because that is the run the window was opened from.
* The refusal to delete the only saved report of a dated verification (the
  date's own report is its result) is unchanged. *(A2 of 5802027116, "(a)
  keep the refusal": decided by Knut, 2026-09-24, [5817809396](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817809396).)* It counts the date's own
  reports of one date only: a verdict record, or a copy of a report of
  several dates that a build before K23 wrote into each date, is not a
  spare (B8-936).
* A date whose folder holds no own report of one date (only records, or
  only pre-K23 copies) is listed as a measurement with no saved report of
  its own: its measured numbers, judged live against the report's set and
  marked "(not saved)", as a date measured with the report switched off.
  The files are still listed as the reports they belong to (B8-936,
  B8-938).

**25.7 Widening a date's ONLY report of one date: keep the date's own
report (B8-937, beta 40 challenge A, finding 3).**

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5806297940](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5806297940)
(2026-09-24): *"go for (a) Keep the date's own report."* The rule is his; the
behaviour BUILT from it waits for his confirmation.

* **The conflict.** §25.2 makes a report of one date, updated to cover more
  dates, a report of those dates, and archives its one-date file. When that
  file is the date's ONLY own report, the date is left with none, which is
  exactly what Delete refuses (§25.6: the date's own report is its result).
  Driven on screen in `~/Desktop/ChromIQ-beta40-proof/challenge-A-behaviour/
  d1` (diffs/003-S2): after the Update the date read an old verdict record
  as its row.
* **The question we put to Knut.** *"An Update that widens a date's only report of
  one date to several dates: should (a) the one-date report stay where it is,
  untouched, and the widened report be written as a new report of those dates
  (what Create New does); (b) ChromIQ ask first, naming the date that would
  be left without a report of its own; or (c) the Update widen it as §25.2
  says, leaving the date with no report of its own?"* We recommended (a),
  and it was first built as the interim; Knut then ruled (a).
* **Built: option (a).** It needs no new message text. An
  Update that would widen the only own one-date report of any date it covers
  leaves that file untouched and writes the widened report as a new report
  (a new id, no "updated" stamp), in the folder the dates decide; the list
  then shows both. When every such date keeps another own report of one date,
  the Update widens as §25.2 says (id kept, the one-date file archived).
  `_update_would_orphan_a_date`, `_write_the_document`;
  `tests/test_b40a_report_model_fixes.py`
  (`test_widening_a_dates_only_report_keeps_it_and_writes_a_new_one`,
  `test_widening_a_report_the_date_has_a_spare_of_still_widens`).

**Built:** `workflow/run_compliance.py` (`run_limits`, `set_run_default_set`,
`run_default_set_id`, `new_report_type`; the binding and the lock removed);
`ui/dialogs/measurement_report_dialog.py` (`_reports_to_generate`,
`_write_the_document`, `_judged_by_the_document`, `_one_limit_set`,
`_report_limits`, `_on_set_chosen`, `_open_report_limits_window`,
`_sync_limit_controls`, `_on_type_chosen`, `_report_type_now`,
`_one_row_per_measurement`; the unlock box, its questions and
`_recalculate_run` removed); `ui/dialogs/thresholds_dialog.py`
(`ReportLimitsColumn`, the "Default for this run" row); `ui/tabs/tab_measure.py`
(`_report_limits_for`); `ui/dialogs/settings_dialog.py`, `core/settings.py`
(the option removed); the help texts of `ui/dialogs/welcome_dialog.py`,
`ui/file_guide.py` and `workflow/measurement_messages.py`
(M-VERIFY-UNCHECKED-METRICS, still PROPOSED); the demo generators.
**Status:** ruled by Knut (5801677743); built in beta 40 (B8-890 to B8-899),
the built result ⏳ awaiting confirmation, and §25.6 awaiting his decision.

## 26. K31 metrics: evenness wording, the tone ramp's spacing, version 1 names, within and beyond the gamut, a FROM PROFILE GAMUT chart's grey steps (#182, 2026-09-23, beta 40)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743)
(2026-09-23), answering sections 3 to 7 of our 5798697107; our reply
5801707986. The RULINGS are agreed from that day; what was BUILT from them
(B8-900 to B8-909) waits for his confirmation. Proof:
`~/Desktop/ChromIQ-beta40-proof/k31-b-metrics/` (on screen, EN and DE, with
PDFs). Tests: `tests/test_k31_metrics.py`, each proved red on the mutation in
its docstring (`k31-b-metrics/mutations.txt`); the demo pairs in
`tests/test_the_demo_presets_pair_on_every_requirement.py`. This section
SUPERSEDES the clauses marked so in §3, §16.1, §17, §21.1 and §22.2.

**26.1 Evenness: which readings are used** (section 3, *"Both texts
approved."*).
* The report's "How this verification was produced" block carries a line of
  its own, **only when an evenness row is in the report** (in the run's
  verdict rows, after a "–" limit and the report type have filtered them):
  **"How evenness was judged: from the readings as the instrument took them,
  by comparing the nine areas of this sheet with each other."** German:
  *"Wie die Gleichmäßigkeit beurteilt wurde: aus den Messwerten, so wie das
  Messgerät sie aufgenommen hat, indem die neun Bereiche dieses Bogens
  miteinander verglichen wurden."* The "How the colours were judged" line is
  unchanged.
* The help icon of both evenness rows replaces the paragraph "The readings
  are taken as measured, …" with the two approved paragraphs word for word
  ("Which readings are used. Evenness compares the nine areas of this one
  sheet with each other, …" and "Some sheets are printed with an intent that
  makes the paper the white, …"). The Dictionary entry "Judged relative to
  paper white (media-relative)" says the same in one sentence and names the
  new line.
* **Correction for Knut to confirm (B8-941, beta 40 challenge B, 2).** An
  evenness row that reads **N-A** does not count as "in the report" for this
  line: nothing was judged, so a line saying how evenness *was* judged is not
  true of it. The line is printed only when at least one evenness row of that
  sheet carries a value (PASS, FAIL or INFO). Found on screen: both evenness
  rows N-A (too few strips on the page) under the line "How evenness was
  judged: … by comparing the nine areas of this sheet". The approved wording
  is unchanged.
* Neither text is a message window, so neither is in §M; both are recorded
  here as the approved wording.
* **Built:** `ui/dialogs/measurement_report_dialog.py::_printing_block_html`,
  `_evenness_row_is_in_report`; `workflow/compliance_sets.py::_D_EVENNESS`;
  `ui/dialogs/welcome_dialog.py` (Dictionary).
* **Verified by:** `test_the_evenness_line_is_there_only_with_an_evenness_row`,
  `test_both_evenness_help_icons_carry_the_approved_text`.

**26.2 The 30 to 70 % tone ramp: rule A** (section 4, *"Implement rule A,
update all relevant text and help text relevant. And update the demo project
package to test the requirements for this metric with the new rule."*).
* On each of the four axes, after the unchanged count (at least 3 distinct
  steps) and span (at least 20 points), `RAMP_MIN_STEPS` positions evenly
  spaced from the ramp's own lowest to its own highest step in the band must
  each have a step within `RAMP_SPACING_TOL` = 4.0 points (the grey ramp's
  `GREY_SPACING_TOL`, inclusive), by the grey ramp's own
  `pick_even_grey_steps`. More steps may be picked when they fit, as on the
  grey ramp. An axis that has the count and span but not the spacing is
  refused with the new reason **`ramp_steps_bunched`**, and the note names the
  tone value nothing is near: *"the mid-tone steps of the measured chart are
  bunched together: none lies within 4 percentage points of the tone value
  50 %, and 3 roughly
  evenly spaced steps between 30 % and 70 % on one ramp are needed"*. A chart
  short of steps or span keeps `no_ramp`.
  *Corrected in beta 40 challenge B (B8-950):* the tolerance carries its unit
  ("percentage points" of tone value; it read "within 4 of"), and the level
  is printed with the decimal comma of the report's language ("59,4" in
  German). Awaiting confirmation with the rest of this section.
* The metric's help icon states the rule; its lever names Single Channel Steps
  (-s) and Grey Axis Steps (-g); the presets window says *"The mid-tone steps
  of this chart's tone ramps are bunched together: no ramp has 3 of them
  roughly evenly spaced between 30 % and 70 %."* and files it as a patch
  shortfall; the report's help paragraph on what a chart must carry and the
  Dictionary entry "ΔL* (lightness difference)" say it.
* **Counted after the build** (the presets window's own code over every
  preset, `k31-b-metrics/tone_ramp_count_after.txt`): **185 of 185 built-in
  presets answer the tone row**, as measured before; of the 31 demo presets
  with a readable chart 28 answer, and the three that do not are R09 FAIL and
  R10 FAIL (`no_ramp`) and the new **R15 FAIL** (`ramp_steps_bunched`). The grey
  rows are unchanged by it (185 of 185).
* **The demo package:** the open preset Q2 (40, 59.4, 60) became requirement
  **R15**'s FAIL side, beside a PASS side at 40, 50 and 60 that differs in
  nothing else (`make_verification_preset_demos.py --check`: 15 requirements,
  33 presets, 0 not doing what they claim). The pack's independent
  reimplementation carries the rule from Knut's words.
* **Built:** `workflow/measurement_report.py::RAMP_SPACING_TOL`,
  `REASON_RAMP_STEPS_BUNCHED`, `ramps_block`;
  `workflow/preset_eligibility.py::PATCH_SHORTFALL_REASONS`;
  `ui/dialogs/preset_verification_dialog.py::reason_line`;
  `ui/dialogs/measurement_report_dialog.py::_reason_sentence`, `_CHART_HELP`;
  `workflow/compliance_sets.py::_D_RAMPS`, `_R_RAMPS`;
  `scripts/make_verification_preset_demos.py` (R15).
* **Verified by:** `test_bunched_mid_tones_are_refused_and_named`,
  `test_evenly_spaced_mid_tones_pass_and_the_tolerance_is_four_inclusive`,
  `test_too_few_steps_is_still_no_ramp`,
  `test_the_na_note_and_the_presets_window_name_the_bunching`,
  `test_the_help_icon_states_rule_a`, `test_no_built_in_preset_loses_the_tone_row`,
  `test_no_open_question_is_left_in_the_pack`.

**26.3 Version 1 names everywhere** (section 5, *"Use version 1 everywhere
and implement your recommendations. Accepted."*).
* Every row of `compliance_sets.ROWS` carries its version 1 name (statistic,
  unit, then the patches), which is the one name the Report limits windows,
  Report Results, How to read, the detailed data, the Overview, the
  one-page summary, the help icons, the notes and the graph legends print.
  "Maximum", never "largest"; every name with a unit carries it. The rows
  version 1 left unchanged keep their names.

  | row | name |
  |---|---|
  | `substrate_de00_max` | ΔE00, paper white against the reference paper |
  | `substrate_overprinted_de00_max` | ΔE00, overprinted proofing paper against the production paper |
  | `solids_de00_max` | Maximum ΔE00, solid colours |
  | `cmy_solids_dhab_max` | Maximum ΔH\*ab, cyan, magenta and yellow solids |
  | `spot_solids_de00_max` | Maximum ΔE00, spot colours |
  | `control_strip_de00_avg` / `_max` / `_p95` | Average ΔE00, control strip / Maximum ΔE00, control strip / Maximum ΔE00, control strip, lowest 95 % (95th percentile) |
  | `grey_balance_neutral_ramp_avg` / `_max` | Average ΔCh, grey balance of the grey ramp / Maximum ΔCh, grey balance of the grey ramp |
  | `outer_gamut_226_de00_avg` | Average ΔE00, outer-gamut patches |
  | `surface_gamut_de00_avg` | Average ΔE00, surface-gamut patches |
  | `ramps_30_70_dl_max` | Maximum ΔL\*, single-colour ramps 30 % to 70 % |
  | `repeat_patches_de00_max` | Maximum ΔE00, repeat patches on one sheet |
  | `repeat_measurement_de00_max` | Maximum ΔE00, the same chart measured again |
  | `uniformity_sd` | Maximum ΔE00, between two of the nine sheet areas |
  | `uniformity_de00_max_from_mean` | Maximum ΔE00, one sheet area against the whole sheet |
  | `repeatability_de00_max` | Maximum ΔE00, print to print and day to day |
  | `permanence_de00_max` | Maximum ΔE00, permanence in storage |
  | `fading_24h_de00_max` | Maximum ΔE00, fading in the dark, first 24 hours |

* Figures with no limit: the Overview's "Spread (std. dev.)" is **"Standard
  deviation ΔE00, all patches"**; "Black L\*" is **"Darkest black L\*"** in
  the Overview and the graph legend (one name with the tab "Darkest black
  (L\*)"); the corners keep "{corner} ΔE00". Detailed data headings: **"Paper
  white and darkest black (L\*)"**, **"Colour accuracy (ΔE00 against the
  chart's design)"**, **"Cube corners (ΔE00)"**.
* Graphs: tabs **"Paper white difference (ΔE00)"**, **"Tone ramps 30 to 70 %
  (ΔL\*)"**, **"Cube corners (ΔE00)"** (tab and title), so every tab carries
  its unit; the evenness line word "Pairs" is **"Areas"**; the other words
  stay.
* Help prose says "maximum" where it named the statistic "largest" (the
  control strip, repeatability, evenness and 95th-percentile help, the
  Dictionary's 95th percentile), and the verification help card names the
  three reference metrics by their names.
* i18n: the keys are renamed textually in all fourteen catalogues; German by
  hand, with no form of address in report text (§19.1); the twelve other
  languages carry the English under the beta rule.
* **Built:** `workflow/compliance_sets.py::ROWS`;
  `ui/dialogs/measurement_report_dialog.py::_METRIC_LABELS`,
  `_TREND_GROUPS`, the tab and legend of `_trend_configs`,
  `_comparison_table_html`, `_run_detail_html`, `_detailed_section_html`;
  `ui/dialogs/welcome_dialog.py`; `data/i18n/*.json`.
* **Verified by:** `test_every_row_carries_its_version_1_name`,
  `test_a_name_says_maximum_never_largest_and_carries_its_unit`,
  `test_every_graph_tab_carries_a_unit`, `test_the_darkest_black_has_one_name`,
  `test_the_evenness_line_word_is_areas`,
  `test_the_german_report_texts_address_nobody`; `tests/test_k28b_one_vocabulary.py`
  (unchanged: the five names).

**26.4 "Within gamut" in the judged names; within and beyond is information
only** (section 5 point 4 and section 6, *"Agreed, do as recommended."*).
* On a document that holds a sheet split by the profile's gamut, the seven
  rows judged on the within-gamut patches (the five colour-accuracy rows and
  the two evenness rows, `WITHIN_GAMUT_ROWS`) carry their within-gamut name,
  e.g. **"Average ΔE00, all patches within gamut"**, in Report Results, How
  to read, the notes and the graph legends (decided for the document), and in
  each sheet's detailed table and one-page summary (decided for that sheet).
  A document with no split sheet prints the plain names. One list,
  `compliance_sets.IN_GAMUT_LABELS`, through `row_name`.
* The Overview keeps its three blocks; the third, "All patches together", is
  **"Within and beyond the gamut together"**. The beyond and together figures
  carry no limit and are never judged, as before.
* **No text says a FROM PROFILE GAMUT chart is split**, and none may: such a
  chart is never split (every colour is chosen inside the gamut). The "all
  patches" help icon and the Dictionary entry now say so in as many words.
* **Built:** `workflow/compliance_sets.py::IN_GAMUT_LABELS`, `row_name`,
  `_D_ALL_PATCHES`, `_D_EVENNESS`;
  `ui/dialogs/measurement_report_dialog.py::_row_name`, `_doc_is_split`
  (used by the grid, the guide, the notes, the detail table, the one-page
  summary and the legends), `_comparison_table_html`;
  `ui/dialogs/welcome_dialog.py` (Dictionary "Within / beyond the profile's
  gamut").
* **Verified by:** `test_the_within_gamut_names_are_exactly_the_split_rows`,
  `test_a_split_report_names_the_judged_figures_within_gamut`,
  `test_the_overview_block_is_within_and_beyond_together`.

**26.5 A FROM PROFILE GAMUT chart's grey steps are its neutral aims**
(section 7, *"Implement option (a) On a FROM PROFILE GAMUT chart, use the
chart's neutral AIMS as its grey steps."*).
* On a chart that carries a colorimetric reference (`reference_source ==
  "colorimetric"` in the report; the chart's `-reference.ti3` in the presets
  window), the grey steps are the patches whose AIM is neutral:
  `hypot(a*, b*) < NEUTRAL_AIM_CHROMA_MAX` = 1.0, the test Create Chart itself
  uses to pick those neutrals (`gamut_target.select_gamut_targets`). The eight
  cube corners are never steps (their reference is the ideal device corner).
* Each step is placed by its aim's **L\*** (0 to 100), and the device rules
  are asked of those levels: at least `GREY_MIN_LEVELS` = 8 distinct steps; 8
  of them within `GREY_SPACING_TOL` = 4 L\* of an even spacing between the
  ramp's own ends (the "same 4 on a 0 to 100 scale" of the proposal).
* **Our construction, to confirm:** the ENDS are the chart's own reach, not the
  device rule's fixed 90 and 10: the lightest neutral aim within
  `NEUTRAL_AIM_END_REACH` = 10 L\* of the lightest aim on the chart, the
  darkest within 10 of the darkest (corners excluded). The fixed 10 would
  refuse every paper whose black is lighter than L\* 10, which is most matte
  papers, on the kind of chart that is made of what the paper can print.
* The ΔCh is each step's measured a\*, b\* against its aim, over every step
  (the bare paper left out by device value, as on a device ramp).
* Four reasons of its own, because the device sentences ("R = G = B", "add
  grey steps") are false on such a chart: `too_few_neutral_aims`,
  `neutral_aims_bunched` (names the L\* nothing is near),
  `neutral_aims_no_white`, `neutral_aims_no_black`. The presets window's lever
  for them is a larger chart ("about one patch in eight is a neutral aim"),
  never "add grey steps" (`compliance_sets.remedy_for`); the grey rows' help
  icon, the report's help paragraph, the verification help card and the
  Dictionary entry "Grey ramp" say how such a chart's grey steps are found.
* **Tester A's case, before and after** (challenge A, F2; 400 and 100
  patches, FROM PROFILE GAMUT, default intent, Folders-Second run1): before,
  both grey rows read N-A with `grey_steps_bunched` in the presets window and
  in the report; after, both are answered in both
  (`k31-b-metrics/`, driven on screen).
* **Not changed, and a question:** the 30 to 70 % tone ramp's grey axis
  still finds its steps by device R = G = B, on every chart. Option (a) was
  ruled for the grey rows; whether a FROM PROFILE GAMUT chart's tone row should
  take its neutral aims too (and by which tone value: an L\* is not a tone
  value) is left for Knut. Measured on the challenge A charts, the tone row is
  answered by the device greys of the middle band (spread 0.4 to 1.0).
  **ANSWERED by K40-2 (Knut, 5832026677: "Yes"), §36.2:** the tone row's grey
  axis is the neutral aims on such a chart, placed at 100 − L\*.
* The demo package: the FROM PROFILE GAMUT runs of the report demo projects
  now design their greys on the neutral aims (`grey_stat_indices`), because
  the report began to judge rows it had read N-A on them.
* **Built:** `workflow/measurement_report.py::NEUTRAL_AIM_CHROMA_MAX`,
  `NEUTRAL_AIM_END_REACH`, the four reasons, `_neutral_aim_grey_block`,
  `grey_balance_block(neutral_aims=, corner_ids=)`, `build_report`;
  `workflow/preset_eligibility.py::_colorimetric_aims`, `_perfect_print`,
  `row_remedy`; `workflow/compliance_sets.py::_D_GREY_RAMP`, `_R_GREY_RAMP`,
  `remedy_for`, `GREY_AIM_REASONS`;
  `ui/dialogs/preset_verification_dialog.py::reason_line`;
  `ui/dialogs/measurement_report_dialog.py::_reason_sentence`;
  `scripts/make_report_limit_demos.py::grey_stat_indices`.
* **Verified by:** `test_the_device_rule_refuses_the_charts_of_challenge_a`,
  `test_the_presets_window_answers_the_grey_rows_of_a_gamut_chart`,
  `test_the_report_of_a_gamut_verification_answers_the_grey_rows`,
  `test_the_corners_are_never_grey_steps`, `test_the_ends_are_the_charts_own_reach`,
  `test_a_neutral_aim_is_what_create_chart_calls_neutral`,
  `test_bunched_aims_are_named_with_their_lightness`,
  `test_the_lever_on_a_gamut_chart_is_a_larger_chart_not_grey_steps`,
  `test_the_two_spellings_of_the_aim_reasons_agree`.

**26.6 The German heading of the reading guide** stays "So ist dieser Bericht
zu lesen" (Knut: *"use your recommendation, then if Sebastian says
differently you can alter it"*); the owner decides.

**Status:** agreed; built for beta 40 (B8-900 to B8-909), NOT confirmed.

## 27. "All metrics" in "Which presets can be used for verification?" (#182, 2026-09-24, beta 42)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Asked for by:** Knut, #182
[5814820283](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5814820283)
(2026-09-24): *"The Judged against options visible in 'Which presets can be
used for verification?' window should have an option 'All Metrics' that
ignores the limit sets selected thresholds and will then check the presets and
the current chart loaded against ALL metrics, to see which supports the most
metrics. The 'All Metrics' option should be the default when opening the
window, as we do not know what the user will pick when later creating
reports."* It also answers question (2) of the K15 demo-pack entry in the
register: the window now opens on a choice that asks every metric. Nothing in
this document said which choice the window opens on, so nothing here is
contradicted. Register: B8-974.

* **Amended by §30 (K33, 2026-09-24):** the Report type pulldown opens on
  **Any** beside All metrics, so the window's default counts what any report
  of a verification can judge; both pulldowns still change on their own. The
  count line under All metrics now also says that the two repeatability
  metrics are not counted (§30.3).
* **Rule:** "Judged against" in that window offers **All metrics** as its FIRST
  entry, above every selectable limit set, and the window opens on it every
  time. The last choice is not remembered: the pulldown is filled afresh on
  each open.
* **What it counts:** every metric a report of the chosen report type can
  judge, whether or not any limit set puts a limit on it. That is every row
  ChromIQ can compute (status now, build or ref), which on a Colour summary or
  Full colour check is **18**, the same 18 the Measure tab's pre-flight names
  (§19.5). Derived from the rows, never from the sets, so emptying a Custom
  column cannot shrink it. Left out, as under every limit set: the rows ChromIQ
  cannot measure at all (no set can put a limit on them, §2), and the two
  repeatability rows (§15), which are not a property of a chart.
* **What it keeps:** the Report type pulldown still narrows. Grey and tone
  check asks its 3 metrics; a Printing record judges nothing ("Nothing is
  judged"). The evenness rows are judged against the loosest limit any set
  puts on them, as in the pre-flight (§16.4).
* **What it shows:** the "Metrics answered" column reads "n of 18 metrics" for
  every chart, the line under the pulldowns reads *"All metrics: a report of
  this type can verify 18 metrics of a chart, whichever limit set it is judged
  against."*, and a chart that answers them all is told *"This chart answers
  every metric a report of this type can judge."* (no limit set named). Every
  limit set still gives the counts it gave before.
* **Measured on screen** (Report-Limits-Every-Limit-Set, run1, Verification):
  before, the window opened on ChromIQ default, "9 metrics", the current chart
  "7 of 9", and 152 of 185 presets "answering every metric asked"; after, it
  opens on All metrics, "18 metrics", the current chart "13 of 18", the
  built-in presets 13 to 15 of 18, and **0** of 185 answer all 18: the three
  reference metrics need a chart built FROM PROFILE GAMUT, which no preset is.
* **Also changed with it:** the FROM PROFILE GAMUT lever of the three
  reference metrics said "this row" and "the row", which this window (Knut,
  beta 25) never says; it now says "metric". It was already visible under the
  Custom ISO sets and became visible on opening.
* **Built:** `workflow/preset_eligibility.py::ALL_METRICS`,
  `rows_every_metric`, `rows_asked`, `assess`;
  `ui/dialogs/preset_verification_dialog.py::PresetVerificationDialog._build`,
  `refresh`, `_show_detail`, `detail_lines(every_metric=)`;
  `workflow/compliance_sets.py::_R_REFERENCE`;
  `scripts/make_verification_preset_demos.py::opening_choice`.
* **Verified by:** `tests/test_all_metrics_is_the_default_and_counts_every_metric.py`
  (`test_judged_against_offers_all_metrics`,
  `test_the_window_opens_on_all_metrics_every_time`,
  `test_all_metrics_asks_every_metric_not_the_rows_a_set_switches_on`,
  `test_all_metrics_still_follows_the_report_type`,
  `test_the_column_total_is_every_metric`,
  `test_the_detail_pane_names_no_limit_set_under_all_metrics`), each proved
  red on its mutation.
* **Proof:** `~/Desktop/ChromIQ-beta42-proof/all-metrics/` (on screen, EN and
  DE, before and after).

**Status:** built for beta 42 (B8-974), NOT confirmed.

## 28. K32: the question's order, the Printing record's rows, the Overview on screen, the limit words, the tab bar, an empty list (#182, beta 42)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5813851807](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5813851807),
[5814107188](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5814107188),
[5814390886](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5814390886),
[5814558912](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5814558912)
and 5814673639 (2026-09-24). Where he described the behaviour, the description
is his ruling; what was BUILT waits for his confirmation. Proof:
`~/Desktop/ChromIQ-beta42-proof/knut-k32/` (on screen, EN and DE, before and
after). Register: B8-969 to B8-978.

**27.1 The Update / Create New question** (K.7e in §13.8): buttons from the
left Create New, Update, Cancel; Create New is the default (Enter), Escape is
Cancel; the numbered list in the same order; both variants
(M-REPORT-UPDATE-OR-NEW and M-REPORT-UNCHANGED-UPDATE-OR-NEW, §M).

**27.2 A Printing record lists the rows of the report's own set.** §25.3 holds
for a Profiling window too: every sheet is judged against the report's set,
so the Printing record's results (all INFO, N-A with its note), its "Judged
against" line and its heading name that set. It listed each sheet's own
automatic report's rows (ChromIQ default on every demo sheet): a fault, not
a design. The different patch counts had nothing to do with it.

**27.3 A Printing record says why it has four graphs.** §17 item 3 is
unchanged (a judged metric's graph only where one of its rows was judged).
Under the results of a Printing record, window and PDF: *"This report is not
graded, so it carries no graph of a judged metric: each of those graphs is
drawn against its limit. The graphs it carries show colour accuracy, paper
white, darkest black and the cube corners."* German: *"Dieser Bericht wird
nicht bewertet, daher enthält er keine Grafik einer bewerteten Kennzahl: Jede
dieser Grafiken wird gegen ihren Grenzwert gezeichnet. Die enthaltenen
Grafiken zeigen Farbgenauigkeit, Papierweiß, dunkelstes Schwarz und die
Würfelecken."* **Question for Knut:** should a Printing record draw the
judged metrics' graphs without limit lines instead? **Amended (challenge 2
of beta 42, B8-1005, not confirmed):** the second sentence names only the
graphs actually drawn. A record of one measurement draws none, and says
instead *"It carries no other graph either: a graph needs at least two
measurements, and this report has one."* (German: *"Er enthält auch keine
andere Grafik: Eine Grafik braucht mindestens zwei Messungen, und dieser
Bericht hat eine."*); a record that draws some names those, in tab order.

**27.4 Metric tables on screen.** The window fits its metric tables (Report
Results and the Overview) to its own page width, never fewer than four dates
a table, each table filled before the next begins (five dates are 4 + 1); the PDF
fits them to the paper and shares the dates out evenly, as before. A table may be 1.5 px over the text
width (Qt's rounding of the Metric column's share), which had halved a four
date table in both. The page is laid out when it is drawn. **Amended
(challenge 2 of beta 42, B8-1003, not confirmed):** in the window a metric
table is 99.5% of the page, not 100%: at 100% Qt laid it out one pixel wider
than the page and the view carried a one-pixel horizontal scroll bar. The
page is never wider than its view, at any width and after a resize; the PDF
keeps 100%.

**27.5 Limit words (amends §17 item 6).** Each word on its own: in the left
margin, centred on its line, when it is no wider than the margin and clear of
the axis numbers and of another margin word; otherwise at the left end of its
line, above or below it (a step further out only when both print over
something), on the side that prints over least: another word or a red x
first, then another limit line, then data lines. Every graph, window and PDF.
**Amended (challenge 2 of beta 42, B8-1004, not confirmed):** a word stays
beside its OWN line: a place with another limit line between the word and its
line is taken only when every other place prints over another word. (Avg's
word, with Max's in the margin a few pixels above, had stepped up past the
Max line, where it read as Max's.)

**27.6 The graph tab bar.** With more tabs than fit: at the left end the
first tab at the edge and the left arrow greyed; at the right end the last tab
against the arrows and the right arrow greyed; between, both arrows live and
a fifth of each hidden neighbour showing (inside Knut's 1/6 to 1/4); a partly
shown tab is clicked like any tab and comes whole. `ui/peek_tab_bar.py`,
reusable, used only here. **Amended (challenge 2 of beta 42, B8-1002, not
confirmed):** a greyed arrow is PAINTED greyed (about a quarter of the live
arrow's contrast), in the light, dark and neutral appearances; the style had
painted a disabled arrow exactly like a live one, because none of the three
palettes sets Qt's disabled colours.
**Amended by Knut, #182
[5817448879](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817448879)
(2026-09-24), built for beta 42 (B8-1008), not confirmed:** *"Do "The
alternative would be to always start the row at the left edge and let the
tabs run up to the arrows, so there is never an empty gap. ""* The row now
fills the scroll area in every state: at the left end the first tab is at the
edge and the next hidden tab fills the rest up to the arrows; in the middle
the left neighbour shows a fifth of itself, the whole tabs follow and the
next hidden tab fills the rest; at the right end the last tab is against the
arrows and the left neighbour fills the rest from the edge. A peek that fills
the rest is no longer held to 1/6..1/4. The greyed look of the arrows is kept.
And: *"today, the title "Trend over time (this printer)" is shown between the
tab-bar arrows and the right edge of the window. The graphs belong to the
generated report, so "(this printer)" can be removed, giving more space for
the tabs."* The title is "Trend over time" (German "Verlauf über die Zeit"),
beside the tab bar, over the PDF's graphs and in the welcome window's help.
**Amended by Knut, #182 5832746557 (K42-1, beta 43, B8-1141 and B8-1142),
not confirmed:** see §37.1: the arrows have the outline of every other button
and are Qt's own scroll-button width again, about half of beta 42's.

**27.7 Nothing measured, nothing listed.** Opened on a selection with nothing
of its own kind measured, the Measurement Report's list is empty and nothing
is added from anywhere else: a verification run with no dated verification
(it listed the project's profiling sheets), a Profiling window when no run of
the project has a sheet (a run with no sheet borrowed a dated verification),
a calibration with no measurement (already so). The empty page says why:
*"This verification run has no dated measurement yet, so there is nothing to
report on. Measure its chart on the Measure tab, or add measurements with
“Add Profile's Measurements…”."* / *"No profile run of this project has a
measurement yet, …"* / *"This calibration has no measurement yet, …"*
(German by hand in the catalogue). The Measure tab's own button still says
"Measure this chart first" there.

**27.8 Switching Run type (measured, not a ruling).** Profiling to
Verification on Report-Limits-Evenness held the window for 1.1 s and then
3.2 s: the Create Chart tab's preset warm-up took four charts a tick, 0.57 s
each with page TIFFs. A tick now stops after 50 ms; the longest stall is one
chart (about 1 s on this machine).

**27.9 The sentence beside "Report shown"** (Knut, 5815133233): wrapped to up
to three lines, each drawn whole, and only then shortened with "…" (the whole
sentence stays in its tooltip). It was capped at two.

**27.10 Adding measurements never rewrites the report** (Knut, 5815133233):
measurements added with "Add Profile's Measurements…" to a window that already
shows a report come in UNTICKED; the page, the graphs and the PDF stay the
report on screen, and ticking an added row is a changed setting like any other
(the red line, and Generate asks). A window that was EMPTY is filled, ticked,
as before (our decision, put to Knut: it has no report to keep).
**Audit of every other way the page could change without Generate**, redone
after Knut's ruling below (challenge 2 of beta 42; by reading every caller of
`_render`, `_refresh` and `_refresh_trend`, and each path driven on screen,
`~/Desktop/ChromIQ-beta42-proof/challenge2-fixes/`):

**Knut's ruling, #182
[5816794672](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816794672)
(2026-09-24)**, on the four paths the list below used to leave redrawing:

> *"Remove Profile's Measurements, Clear List, re-adding a file that changed
> on disk", these should all result in the red warning text appearing that
> settings have changed, and never automatically change a report.*
>
> *In the case when not all settings have values, for ex. if the list of
> "Included Measurements..." is empty or no measurement is selected, then it
> would be natural that Generate Report is greyed out. Are there other cases
> when the Generate Report button is greyed out?*
>
> *Changing the settings while Generate Report is greyed out and it is not
> allowed or possible to generate a report, then it makes no sense to allow
> changing settings. The report text should never automatically be updated in
> any situation, as a report is a record of history and shall never we
> changed unless deliberately done by a user.*

What the window does now (built for beta 42, B8-1001; NOT confirmed):

* **The page, its graphs and its PDF change only through a door that shows a
  report:** Generate report, a report chosen in "Report shown", "New
  report…", Delete Selected Report (which shows the next one), and the
  window's first page. Every other path keeps the page as drawn.
* Report type, Judged against, "Show detailed data", a tick, Select all,
  Deselect all, the "This report" column of the limits window: the red line
  only (unchanged). **The line now also compares what the page COVERS**
  (each ticked measurement and the disk stamp of its file), not only the
  settings.
* **Remove Profile's Measurements**: the list loses the measurement; the
  page, the graphs and the PDF stay the report on screen; the red line comes
  up when the page covered what was removed (removing an added, unticked
  measurement changes nothing). The PDF is built from the measurements the
  page was drawn from, so it is still the page (Knut, 2026-09-18).
* **Clear List**: the list empties, the page stays, the red line comes up,
  Save report as PDF… stays live (the page is a report), Generate is greyed
  ("No measurement is loaded"). "Report shown" moves to "New report…" as
  before (R2A-6), so Generate can never Update a report that is no longer in
  the list. Measurements added afterwards come in UNTICKED, as over any page
  that shows a report.
* **A file added again that changed on disk**: the list reads it again; the
  page does not; the red line comes up.
* **A setting changed while Generate is greyed**: the page stays. Report
  type, Judged against and "Show detailed data" are GREYED while Generate is
  (Knut: *"it makes no sense to allow changing settings"*), because no reason
  Generate is greyed for is answered by those three. The list, its buttons
  (tick, Select all, Deselect all, Add, Remove, Clear), "Report shown", Edit
  limits… and Save report as PDF… stay live: they are how a reader un-greys
  Generate, looks at another report, or keeps the one on screen. With
  NOTHING ticked the red line stays down as B8-601 ruled (it would ask for a
  press that cannot happen), unless the page has lost a measurement it
  covered.
* **The question after Generate** (M-REPORT-UPDATE-OR-NEW /
  M-REPORT-UNCHANGED-UPDATE-OR-NEW) now also compares the controls with the
  SELECTED SAVED REPORT's own limit set and type, so it cannot say "Nothing
  was changed for the selected report" over a set that is not the saved
  report's (the challenge drove exactly that, and Update rewrote a ChromIQ
  default report as ChromIQ tight).
* **Mixed kinds (FC-2) counts only TICKED measurements**: a press writes the
  ticked ones and nothing else, so an unticked profiling sheet beside a
  verification's dates (the way K32 adds it) no longer greys Generate. Its
  tooltip now says "ticked together … Untick one kind, or remove it".

**Amended (challenge 5 of beta 42, B8-1092, not confirmed): the PDF prints
the page's own rows.** The snapshot above kept the measurements, and the
four settings were put back for the export, and still the PDF judged the rows
again: touching one control drops the loaded document's claim on the
controls, and the export then judged every row live against today's numbers
(measured: the page FAIL, FAIL, Overall FAIL; the PDF after ticking only
"Show detailed data" PASS, PASS, Overall PASS). Each time the page is drawn
the rows it was drawn from are kept, with their verdicts, and the export
prints exactly those, with the document's claim as it stood when the page
was drawn. Verified after each of: a setting touched, a tick, Add Profile's
Measurements, Remove Profile's Measurements and Clear List, by the verdict
words read out of the written PDF
(`tests/test_c5_a_saved_report_is_its_own_record.py`).

**Amended (challenge 5 of beta 42, B8-1094, not confirmed): Generate works
the report out again from disk.** Create New and Update read each ticked
measurement, its print record and the run's profile again at the press, and
judge that; they no longer write what the window read when it opened (a
saved report that was not stale, or one rebuilt then). Opening a saved report
stays a record (§6). The page under "New report…" before the press is still
the window's reading (question for Knut, B8-1093).

**Every condition that greys Generate report, and the reason shown under it**
(`_sync_type_combo`; the reason is the button's tooltip and the line under
it, `_set_generate_why`). For Knut's question:

1. No measurement in the list: *"No measurement is loaded. Add a profile's
   measurements to the list to generate a report."*
2. Every measurement unticked: *"No measurement is ticked in the list, so
   there is nothing to report on. Tick one to generate a report."*
3. A profiling sheet and dated verifications TICKED together (FC-2):
   *"Measurements of a profiling sheet and of verifications are ticked
   together, and each has its own kind of report. Untick one kind, or remove
   it with Remove Profile's Measurements…, to save a report. Save report as
   PDF… saves the report shown here."*
4. Measurements of several places ticked and one of them is in no ChromIQ
   project: *"A report across profile runs or projects is saved only when
   every ticked measurement is in a ChromIQ project. Save report as PDF…
   saves the report shown here."*
5. The window's own measurement is in no profile run (a file opened from
   outside a project): *"This measurement is not part of a profile run, so
   there is no run to save a report into. Save report as PDF… saves the
   report shown here."*
6. Run type Calibration with a profile run's measurement ticked: *"With Run
   type Calibration, a report covers calibrations only, and a profile run's
   measurement is ticked. Untick it to save a report of the calibrations.
   …"* (and the plural variant for {n} measurements).
7. Run type Calibration on a measurement that is not a project's
   calibration: *"With Run type Calibration, Generate report saves a report
   of a project's calibration, and the measurement this window is on is not
   one. …"*
8. Run type Calibration whose calibration has not been measured since its
   chart was made: *"The calibration has not been measured since its chart
   was made, so there is no measurement to report on. Its earlier reports
   can still be opened, and Save report as PDF… saves the report shown
   here."*

Of these, 1 and 2 are the two Knut named; 3, 4 and 6 are answered in the
list (untick or remove); 5, 7 and 8 belong to the measurement the window
was opened on, and in the usual case nothing in the window answers them. **Question for Knut:** in 5, 7 and 8 the window can never generate, so
with the settings greyed its page is fixed at what it opened with: a file
from outside a project can no longer be looked at against another limit set
before saving its PDF. Keep that (his rule as written), or let such a
window redraw on a setting change, since it holds no saved report to keep?

**27.11 "New report…" keeps the report shown (K39-3, Knut, #182
[5831246553](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5831246553),
2026-09-25; built for beta 43, B8-1113, NOT confirmed).** Asked whether
"New report…" should read the measurements again, since it shows no saved
report, Knut answered:

> *"No. Selecting "New report…" will not change whatever report is
> currently visible, but loads the default settings for "New report…", and
> should then also show a red text message telling user to modify settings as
> desired and then press Generate Report to apply and make a new report.
> Generate Report will then update the viewed report on screen. However, if a
> user selects "New report…", and then goes back to selecting the previously
> selected report, then that report reloads, as normal when selecting a
> report. This implies that, if a user had made changes to the settings,
> those are reverted to what the report has stored when the report is
> re-selected."*

What the window does (`_start_new_report(chosen=True)`, `_new_report_pending`,
`_show_stale_banner`, `_word_the_stale_line`):

* **Chosen by the reader** in "Report shown", with the mouse or the keyboard
  (Up, Down), over a page that shows a report: the Preferences defaults of a
  new report go into the controls (type, "Judged against", "Show detailed
  data"; every measurement of the list ticked, as before), the page, its
  graphs and Save report as PDF… stay the report shown (the PDF also keeps
  that report's Report Scope and creation line), Delete Selected Report is
  greyed ("New report…" is not a report), and the red line reads
  M-REPORT-NEW-REPORT-SETTINGS (§M-PROPOSED): *"⚠ New report: change the
  settings as wanted, then press “Generate report” to make it. The report
  shown stays as it is until then."* It is up whatever the settings are,
  until a report is drawn.
* **Generate report** then writes the new report and draws it; the line
  goes.
* **The previous report chosen again** reloads as any report does: its own
  stored settings come back (a change made after "New report…" is gone), its
  page is drawn, the line goes.
* **"New report…" when the list holds no report**: the window opens on
  "New report…" with its page drawn from the defaults and no red line
  (nothing was chosen); choosing "New report…" again keeps that page and
  shows the line.
* **A calibration window** behaves the same.
* **The doors that must replace the page** are unchanged: a delete that
  took the report shown and lands on "New report…" draws (the deleted report
  may not stay on screen), and so does a Generate that found its report
  gone from the list.
* **The page under "New report…" is still the window's reading** of each
  measurement, and only Generate works them out again from disk (B8-1094),
  which answers the second question of B8-1093 ("No").

**27.12 The unchanged question has a variant for a report this version works
out differently (K39-2, Knut, #182
[5831246553](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5831246553):
"Yes"; built for beta 43, B8-1112, NOT confirmed).** With a saved report
selected and nothing changed, Generate report asks
M-REPORT-UNCHANGED-UPDATE-OR-NEW (approved) only when an Update would print
the same results. The window works each measurement the Update would write
out again from disk, exactly as the Update does (`_worked_out_again`, once
per press), judges it against the report's own limit set, and compares each
row's name, word and number (two decimals) and the Overall word with the
rows the page was drawn from; a change in how the rows are explained
(B8-1091's `_worked_out_differently`, the test behind
M-REPORT-WORKED-OUT-EARLIER) counts too
(`_update_would_change_the_report`). When they differ it asks
M-REPORT-WORKED-OUT-DIFFERENTLY-UPDATE-OR-NEW (§M-PROPOSED), *"This version
works the selected report out differently"*, with the same numbered list and
the same buttons: Create New, Update, Cancel from the left, Create New the
default. A changed setting still asks M-REPORT-UPDATE-OR-NEW.

**Proof (27.11, 27.12):** `~/Desktop/ChromIQ-beta43-proof/k39-report/` (on
screen, EN and DE, before and after). **Verified by:**
`tests/test_k39_update_question_and_new_report.py`.

**Proof:** `~/Desktop/ChromIQ-beta42-proof/challenge2-fixes/` (on screen, EN
and DE, before and after). **Verified by:**
`tests/test_c2_the_page_changes_only_with_generate.py` (six tests, one per
path, each red on its mutation) and the two older guards it amends,
`tests/test_the_report_waits_for_the_generate_button.py::test_nothing_waits_for_a_button_that_cannot_be_pressed`
and `tests/test_report_window_limit_controls.py::test_an_external_file_is_judged_but_nothing_is_written`.

## 29. A row ChromIQ cannot measure reads ✕ in every limit set (#182, 2026-09-24, beta 42)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Asked for by:** Knut, #182
[5815435713](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5815435713)
(2026-09-24), on Preferences > Reports > Report limits: *"Opening help text
for 'Maximum deltaE00, spot colours'. The help text says '... and the cell
shows a cross in every limit set.'. This is not true. The three ChromIQ limit
sets show '-'. There are many other rows/metrics that ChromIQ does not
evaluate, but still shows '-' and not 'x' for a limit set. I guess they should
show x on all limit sets, when ChromIQ does not evaluate that metric at all."*
Register: B8-979.

It changes the cell rule of §2 (`✕` only where a standard limits the row,
D16), which is recorded there as amended; the change is Knut's own ruling, so
it is recorded rather than put to him as a fault.

* **Rule:** every row whose status is "cannot be measured by ChromIQ" (twelve
  rows today: three under Paper, the spot-colour row, and the eight under "Not
  evaluated by ChromIQ") reads `✕` in every column of the Report limits
  window: ChromIQ default, ChromIQ tight, Quick check, both read-only ISO
  columns and both Custom columns, whether or not the standard behind a column
  limits the row. `–` now means only "the set puts no limit on a row ChromIQ
  can judge".
* **A report's own column ("This report")** shows `✕` on those rows too. A
  report saved before this change stored "–" (`null`) there in ChromIQ's own
  three sets; it is SHOWN as `✕` and the stored copy is not rewritten by
  looking at it.
* **What does not change:** no verdict, no word and no count. These rows never
  carry a value, and a `–` without a value and a `✕` both give no word, so a
  Measurement Report's rows, its overall verdict and every "n of N" figure are
  the same as before, in every set. A report saved before the change is not
  called "(edited)": a stored "–" and a factory `✕` are the same yardstick
  (neither carries a number). An override on such a row is still ignored.
* **The texts are now true as written:** the row's help text ("the cell shows
  a cross in every limit set"), the window's legend ("✕ ChromIQ cannot
  measure it") and its title help ("✕ means ChromIQ cannot measure it at
  all").
* **One sentence is not, and is not changed here** because it is a §M
  catalogue message (`M_THRESHOLDS_NOT_CERTIFICATION`) and new message text
  needs approval: *"Such a column reads “–” for a row the standard puts no
  limit on"*. A read-only ISO column now reads `✕` on a row its standard does
  not limit when ChromIQ cannot measure that row (for example "Macro-uniformity
  score" under ISO 12647-7). Proposed wording, for approval: *"Such a column
  reads “–” for a row ChromIQ can measure that the standard puts no limit on,
  and ? where it limits the row but no number has been supplied for it."*
* **Also changed with it:** the demo pack's README paragraph on the two Custom
  columns' "shape" difference has nothing to name any more. That difference
  was entirely `✕` against `–` on these rows; it is printed only when the two
  columns' numbers are the same, which they are not, so the README does not
  change.
* **Measured on screen, before:** 42 of the 84 cells of the twelve rows read
  "–" (every row in the three ChromIQ columns; in the ISO and Custom columns
  each row that standard does not limit), in English and German. **After:**
  84 of 84 read `✕`, in both languages.
* **Built:** `workflow/compliance_sets.py::mark_unmeasurable`,
  `factory_limits`; `ui/dialogs/thresholds_dialog.py::ThresholdsDialog._limits_of`.
* **Verified by:**
  `tests/test_a_row_chromiq_cannot_measure_reads_a_cross_in_every_set.py`
  (`test_every_set_reads_a_cross_on_every_row_chromiq_cannot_measure`,
  `test_every_other_row_is_exactly_what_it_was`,
  `test_the_cross_moves_no_count_and_no_limit_bearing_row`,
  `test_a_copy_stored_before_the_ruling_is_not_called_edited`,
  `test_the_report_judges_and_counts_exactly_as_before`,
  `test_the_help_text_of_such_a_row_is_now_true`,
  `test_a_reports_own_column_reads_the_cross_too`), each proved red on its
  mutation.
* **Proof:** `~/Desktop/ChromIQ-beta42-proof/x-and-prefs/` (on screen, EN and
  DE, before and after).

**Status:** built for beta 42 (B8-979), NOT confirmed.

## 30. K33: "Any" and "Sort by" in the presets window, why 18 and not 21, Knut's figures in both Custom ISO sets, the ISO report types offered, and a wider "Judged against" help (#182, 2026-09-24, beta 42)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326),
[5817191535](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817191535)
and 5817448879 (2026-09-24). Where he described the behaviour, the description
is his ruling; what was BUILT waits for his confirmation. Proof:
`~/Desktop/ChromIQ-beta42-proof/knut-k33/` (on screen, EN and DE, before and
after; REPORT.md). Register: B8-992 to B8-999.

**30.1 "Any", the default Report type of the presets window (B8-996).** Knut:
*"the Report type should instead also have an option called "Any", which is
the default, set together with "All metrics" as default for judged against.
Report type and judged against shall still be able to individually change if
desired."* "Any" is the first Report type entry and the window opens on it
beside All metrics, every time. It counts what any report a verification can
be made into would judge: the union, in table order, over the report types
ChromIQ can produce for a verification (the Printing record, a profiling
sheet's report, asks nothing). Under All metrics that is 18, the same as Full
colour check; under a limit set it is that set's rows over every such type.
Nothing is ever generated as "Any". The count line reads *"All metrics: a
report of any type can verify 18 metrics of a chart, whichever limit set it is
judged against."* or, under a limit set, *"A report of any type, judged
against this limit set, asks to verify n metrics of a chart during
verification."* Amends §27.

**30.2 Knut's figures in both Custom ISO sets (B8-998).** Recorded in §2a with
his words and the row each of his labels names. Added where the row took
ChromIQ's own number. Kept where his new figure would replace his own figure
of 2026-09-21, **for him to decide**: Custom ISO 12647-7 solid colours 2.0
(proposed 3.00) and outer-gamut patches 4.0 (proposed 2.50); Custom ISO
12647-8 surface-gamut patches 4.0 (proposed 3.00). Each Custom column now
starts from 15 researched figures and 5 of ChromIQ's own, 20 limits (16 and 4
since Knut's ruling of 2026-09-25, §2a: the three kept figures are 3.00 and
each column takes the other's figure where it has none). **Every
row ChromIQ can measure already had a limit in some set before this change**
(the two Custom columns carried all 20), and still does. Noted for him, not
changed: with "Maximum ΔE00, all patches" at 2.00, the rows it bounds
("Average ΔE00, all patches" 2.0, "Average ΔE00, highest 5 %" 2.00, and the
95th percentile 4.0) can never be the row that fails on their own, because a
maximum of 2.0 keeps every average and percentile at or under 2.0.

**30.3 Why the window counts 18 and Knut counts 21 (B8-995).** Knut: *"When I
count all the metrics what are supported, it is 21 metrics. It seems all
metrics are not selected for any of the current limit sets, and I guess this
is what limits the 18 above."* Measured, not guessed:

* ChromIQ's row table has 32 rows. 12 are "ChromIQ cannot measure" and read ✕
  in every set (§29). **20 can be computed.**
* All metrics does not depend on any limit set (§27), so adding limits cannot
  move it. Before K33 the two Custom columns already put a limit on all 20.
* Of the 20, the window leaves out ChromIQ's two repeatability rows (§15),
  "Maximum ΔE00, repeat patches on one sheet" and "Maximum ΔE00, the same
  chart measured again": they depend on a measurement being repeated, not on
  the chart, so no preset can be better or worse at them. 20 − 2 = **18**.
* **No 21st metric exists** in ChromIQ's table: every other row is one ChromIQ
  cannot measure. So 21 cannot be reached by counting what a report can judge;
  it could be 20 plus one of the ✕ rows (the spot-colour row sits among the
  solids and looks like one). **Question for Knut:** which 21 he counted.
* What changed: the count line under All metrics now says so in the window,
  *"ChromIQ's two repeatability metrics are not counted here: they depend on
  measuring the chart again, not on the chart."* The count stays 18.

**30.4 The intro sentence (B8-997).** Knut: *"the intro sentence shall say
what the fields [do], even if the default is set to show any and all metrics.
However, the sentence is hard to read and understand, so the wording should be
rephrased for easier understanding."* Now: *"Every preset ChromIQ ships, and
your own, with the number of metrics its chart can answer. The two fields below
choose which metrics are counted: the ones a report of that type, judged
against that limit set, would check. “Any” and “All metrics” count every metric
a report can check. Click a preset to see what it can and cannot answer;
double-click it to load it in Create Chart and close this window."* German by
hand.

**30.5 "Sort by" (B8-999).** Knut, 5817191535, and 5817448879 (it must work
the same whether the check box is ticked or not). Right of "Show only the
presets made for verification": **Preset pulldown order** (the default) and
**Most metrics answered first**. Today's order was measured, not assumed: it
is the Create Chart Preset pulldown's own order, which is **not
alphabetical**: in each group the ready-made charts "by Pharmacist" first,
then the rest from the smallest sheet up and, on one sheet size, by patch size
and count; your own presets alphabetically. The second choice sorts each group
by how many of the counted metrics a preset's chart answers, most first; a tie
keeps the pulldown order; a preset that cannot be checked goes last. Groups
never move and a preset never leaves its group; the current chart stays first.
It sorts the list as filtered, ticked or not. Not remembered: the window opens
on the pulldown order.

**30.6 The ISO report types are offered (B8-994).** Knut: *"for run type
verification, the report type options often do not allow selecting the
"Validation print check" or "Contract proof check". These should be available
now."* Measured on screen before the change, on every verification run of
every demo project (86 runs, 17 projects): the two were greyed in **every**
window, with *"Not available yet: this report is still being built."* The
cause was not a per-chart condition: both were declared unbuilt in
`REPORT_TYPE_MENU` (§10, "Not built here: T5 and T6"). Now:

* Both are built, and offered for a verification or a calibration **while
  their standard's values are loaded** (shipped, or supplied by the user). No
  per-chart condition was found that should grey them: a chart that cannot
  answer a row the chosen set limits already shows it N-A, with the strip
  saying why (M-REPORT-CHART-MISMATCH), as for every type.
* What such a report is: the Full colour check document, headed "Report type:
  Validation print check (ISO 12647-8)" or "… Contract proof check (ISO
  12647-7)". Which set it is judged against is the "Judged against" pulldown's,
  as for every type; the help's existing words stand: the ISO types belong with
  the matching ISO set, "the pairs above are the usual habits, not rules".
  **Question for Knut:** should choosing one of them also switch "Judged
  against" to its standard's set? **Answered in §32.1** (Knut, 5820871320): yes,
  and while one is chosen only the four ISO sets can be chosen. The
  sentence below, "the pairs above are the usual habits, not rules", no
  longer holds for these two types; the help says so.
* With no values of that standard loaded, the entry is greyed and says:
  *"Not available: no values of this standard are loaded. They ship with
  ChromIQ; if they are missing, supply them with “Reference values…” in the
  Report limits window."*
* The release demo pack makes the ordinary-chart runs of the two read-only
  ISO sets in Report-Limits-Every-Limit-Set into these two types.
* Amends §10 ("Not built here: T5 and T6") and the "When you would reach for
  each" help, which said they were greyed.

**30.7 The "Judged against" help (B8-992, B8-993).** Knut: *"The help text
window for Judged against is very tall, so the window should be made wider.
Also, I cannot find any recommendation of what type of situation the ISO limit
sets normally would be used for."*

* The "Judged against" and "Report type" help windows open 900 px wide (they
  opened 616 × 971 px on a 1728 × 1079 screen). Measured, the part that has to
  be scrolled: "Judged against" 414 px → 254 px in English, 574 → 382 in German,
  with a paragraph added; "Report type" 398 → 110 and 622 → 206.
* A paragraph "When to judge against which set" in the "Judged against" help
  and in the Report limits window's title help: ISO 12647-7 for contract proofs
  (a hard-copy proof on a proofing system that printer and customer agree
  shows the job's colour), ISO 12647-8 for validation prints (the intended
  colour, less strictly than a contract proof, for example to approve a layout
  or a design), the two Custom ISO sets as an alternative from industry
  practice you can tune, ChromIQ's own three sets for your own printer, and
  that ChromIQ does not certify that a print conforms to a standard.
* Found while there and corrected: the two Custom ISO sets' own descriptions
  still said they start "from the published figures … where a licence holder
  has supplied them", which stopped being true with B8-978.

* **Built:** `workflow/preset_eligibility.py::ANY_REPORT_TYPE`,
  `rows_every_metric`, `rows_asked`;
  `ui/dialogs/preset_verification_dialog.py` (`_build`, `refresh`,
  `_sorted_members`, `SORT_PULLDOWN`, `SORT_MOST_ANSWERED`);
  `workflow/measurement_report.py` (`REPORT_TYPE_MENU`, `REPORT_TYPE_ISO_SET`,
  `iso_type_values_missing`, `report_type_is_built`);
  `ui/dialogs/measurement_report_dialog.py` (`_ISO_USE_HELP`,
  `JUDGED_AGAINST_HELP_WIDTH`, `_not_built_line`, `_iso_values_missing_line`);
  `ui/dialogs/thresholds_dialog.py::_iso_use_paragraph`;
  `workflow/compliance_sets.py::_CUSTOM_INDUSTRY` and the two Custom `SetDef`
  blurbs; `scripts/make_report_limit_demos.py`,
  `scripts/make_verification_preset_demos.py::opening_choice`.
* **Verified by:** `tests/test_any_report_type_is_the_default_beside_all_metrics.py`,
  `tests/test_the_presets_window_sorts_within_each_group.py`,
  `tests/test_the_iso_report_types_are_offered_when_their_values_are_loaded.py`,
  `tests/test_the_judged_against_help_is_wide_and_says_when_to_use_each_set.py`,
  `tests/test_compliance_sets.py::test_knuts_k33_figures_fill_only_the_rows_that_took_ours`,
  each proved red on its mutation.

**Status:** built for beta 42 (B8-992 to B8-999), NOT confirmed.


## 31. K34: Knut's answers to section A of 5802027116: a deleted run in Report Scope, a failed folder rename, the order of "Report shown", the paper patch, the reference paper of a FROM PROFILE GAMUT chart (#182, 2026-09-24, beta 42)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5817809396](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817809396)
(2026-09-24), answering section A of our post
[5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116):
*"For all the other topics under "A. Questions that need your decision": the
recommended is accepted."* The recommendation he accepted is the rule; what
was BUILT from it waits for his confirmation. Proof:
`~/Desktop/ChromIQ-beta42-proof/knut-k34/` (on screen, EN and DE, before and
after; REPORT.md). Register: B8-1011 to B8-1016.

**31.1 A report that covers a deleted profile run says so in Report Scope
(A6, B8-1011).** The profile bar's Delete renumbers the later runs and turns
a saved report's reference to the deleted run into `runs/runN.deleted`
(§13.14), which no folder answers. Measured before the change: a report of
three runs, run 2 deleted, showed two measurements and said nothing about the
third; only an Update said "its profile run was deleted". Now, while a saved
report that names such a run is shown, Report Scope (window and PDF) ends
with M-REPORT-SCOPE-RUN-DELETED (**PROPOSED**, §M-PROPOSED):

> **Part of this report has since been deleted**
> This report also covered a profile run that has since been deleted (run 2
> when the report was written). Its measurements are no longer in the report.

The run is named by the number it had when the report was written, because
the run now called run 2 is a different one (the later runs were numbered
again). With several deleted runs the plural body names them all ("run 2 and
run 4"); a report across projects names each with its project ("P, run 2").
"New report…" never carries the line: nothing saved is shown. German by hand.

**31.2 The folder-renamed window when the rename fails (A8 (b), B8-1012).**
If the chosen rename fails (for example a folder with the new name is already
there), M-PROJECT-FOLDER-RENAME-FAILED says why, as before, and then the
three choices come back: rename to the folder's name, choose another name, or
Cancel, which closes the project (§18.5, Knut 5794078008). Before, the project
stayed open, not renamed, and ChromIQ found none of its files until it was
closed and opened again. Cancel is always one of the three, so the window
never loops without an exit. The message's words are unchanged (approved);
its last sentence ("the project is open as it was") is still true at the
moment it is shown.

**31.3 "Report shown": newest first by the report's own creation date (A9,
B8-1013, answers B8-843 (1)).** Inside each heading the order was the time the
FILES were written, so reports ChromIQ wrote itself came out right and copied
or restored ones did not (a demo project listed 2026-12-08 before 2026-12-15).
Now the order is read from the report:

1. the document's own `created` (every report since B8-383; an Update keeps
   it, §13.8);
2. **fallback for a report without a document date** (written before the
   document block): the stamp `save_report` writes into its file name,
   `report_YYYY-MM-DD_HH-MM-SS`, the second it was saved;
3. a file name in no such shape: the file's own time, the only evidence left.

The file time stays only as the tie-break between two reports of the same
second. The groups and their order are unchanged (§13.12).

**31.4 Paper white is the chart's own paper patch (A10 (a), B8-1014, answers
B8-806 F13).** "Paper white" was the lightest measured patch. It is now the
patch printed with NO INK:

| device space | the paper patch |
|---|---|
| RGB (every chart the report reads today) | every channel at 100 (device 100, 100, 100), within 0.5 |
| CMY, CMYK and any n-colour ink space | every channel at 0, within 0.5. `parse_ti3` refuses such a measurement for the report today ("only RGB charts are supported"), so this row is defined for the day it is lifted, in `paper_patch_rows`, the same rule `reference_sets.paper_lab` already uses for a reference file |

Of several paper patches (most charts carry more than one), the lightest, so
a chart WITH a paper patch reads exactly the patch it read before unless a
coloured patch was lighter than the paper. A measurement with no device
columns (an i1Profiler export of a chart it did not generate) takes the
device values from its chart by SAMPLE_ID, as the rest of the report pairs
it.

**A chart with no paper patch:**
* "Paper white" reads **N-A** with a numbered note, in the detailed section's
  "Paper white and darkest black" and in the Overview table; the note is
  M-REPORT-NO-PAPER-PATCH (**PROPOSED**): *"This chart has no patch printed
  with no ink, so the paper white could not be measured, and nothing on this
  sheet is judged relative to the paper."* It takes the document's one
  numbering (after the limit rows' notes, so no row's number moves) and is
  listed under the name "Paper white". German by hand.
* The Paper white (L\*) graph draws no point for that sheet (no paper white
  is recorded); the darkest black is recorded and drawn as before.
* **Nothing is judged relative to the paper.** What that touches, and what
  it does instead:

| what used the paper white | with no paper patch |
|---|---|
| the media-relative yardstick (a sheet printed through its profile with an intent that maps paper white, against the chart's design or device reference: pairing 3, `verification_printing_and_target.md`): every reading divided by the paper white | **amended by §33 (K37):** the sheet is judged media-relative with the paper white of the profile it was printed through, the note M-REPORT-PAPER-WHITE-FROM-PROFILE says so; only when no profile can be read is it judged in **absolute Lab** as measured, with M-REPORT-NO-PAPER-PATCH on the line and M-REPORT-JUDGED-ABSOLUTE-NO-PAPER-WHITE on each row that moves (`yardstick_no_paper` recorded in both cases; `paper_white_used` says which). Before §33: absolute Lab in every case (analysed in §32.6) |
| evenness on such a sheet: each aim carried onto the paper (§21.1) | aims as designed, readings as measured |
| the five ΔE00 rows, the worst patches, the cube corners, grey balance, the tone ramps and the control strip on such a sheet | judged in absolute Lab, as on a sheet printed absolute |
| "Paper white, difference from the reference paper" | unchanged: it reads the chart's declared white CORNER (only a FROM PROFILE GAMUT chart answers it, and it always carries one); N-A without it, as before |
| the paper white line, the Overview row, the Paper white (L\*) graph | N-A with the note / no point |
| a sheet printed absolute, or against a colorimetric reference | nothing changes: it was never divided by the paper |

* **Every place that picked "the lightest patch", checked:**
  `measurement_report.measurement_facts` (the recorded paper white) and the
  yardstick in `build_report` now take the paper patch;
  `lightest_and_darkest` keeps only its DARKEST half's use (the darkest black
  is still the darkest reading, which is what that line says);
  `measurement_report.GREY_LIGHTEST_MIN` and the neutral-aim reach are about
  grey steps, not the paper, unchanged; `reference_convert._PAPER_IS_THE_LIGHTEST`
  already takes the NO-INK patch of an i1Profiler file; `ti3_analysis`
  (the ".ti3 analysis" Tool's paper/ink contrast of a PROFILING chart, not
  the report) still takes the lightest reading, unchanged and not asked;
  the demo generator (`make_report_limit_demos.apply_design`) now anchors on
  the paper patch and designs a chart without one in absolute Lab.
* **A report saved before beta 42 is worked out again from its measurement
  when the window reads it**, as for every block the builder has since
  written (`ALWAYS_BUILT_BLOCKS` gains `paper_patch`; the saved verdict is
  carried across untouched, §6). Found on screen: without it, "New report…"
  on the demo pack's no-paper-patch run still printed the L\* 82 grey as
  White, because every date there had a saved report.

**31.5 The reference paper of a FROM PROFILE GAMUT chart is the profile's
media white (A11, B8-1015, answers B8-804 point 1).** Measured first, on the
current build (beta 41 code, the challenge-2 copy of the release demo pack,
51 dated FROM PROFILE GAMUT verifications in 4 projects): the row compared
the bare paper with the reference's W corner, which `gamut_target` writes as
device white read as sRGB: **L\* 100.00, a\* 0.01, b\* -0.01** on every one
of them. The pack's profiles describe papers of L\* 94.0 to 96.0 (for
example 95.51 / 0.20 / 1.40 in Report-Limits-Profile-Gamut), and the pack
had designed its papers against the ideal white (every paper read L\* 100.0).
A real paper of exactly the profile's white, 95.5 / 0.21 / 1.41, reads
**2.98 ΔE00** against that ideal, on every sheet. Our note of B8-804 was
right.

Built, as Knut accepted:
* The chart's colorimetric reference records the paper the profile
  describes, its media white (`wtpt`, L\*a\*b\* D50), as
  `CHROMIQ_PROFILE_WHITE_LAB`, and the profile's file name as
  `CHROMIQ_PROFILE` (`gamut_target.select_gamut_targets`,
  `write_colorimetric_reference`).
* The bare-paper corner (the declared corner at device white) AIMS AT THAT
  PAPER wherever the reference is read (`read_colorimetric_reference`, and
  `build_report` for an older reference), so the row, the cube-corner table's
  "Expected" white and a control-strip rung on that patch read one
  comparison. The other seven corners keep their ideal aims (§9a rule 2).
* **An older reference** (every FROM PROFILE GAMUT chart built before beta
  42) records no white: the run's own built profile, the profile such a chart
  of that run is built from, is asked instead
  (`paper_reference_of`, recorded as `paper_reference_from: run_profile`).
* **Old behaviour kept for other charts:** with neither (no white recorded
  and no profile in the run) the row keeps the old comparison with the W
  corner's own aim. On every other chart the row is N-A as before (it needs
  a colorimetric reference, §3). A Fogra reference set keeps comparing with
  the paper THAT reference describes (`reference_sets.substrate_de00`).
* Measured after, the same 51 dates of the same (unrebuilt) pack: the row
  reads 2.63 to 18.57 against the profiles' own whites, where it read 0.52 to
  9.01 against the ideal. The pack's papers had been designed on the ideal
  white (every one reads L\* 100.0), so on that pack no date passes any more
  until it is rebuilt.
* **The demo pack:** `make_report_limit_demos.apply_design` designs the paper
  from the corner's aim, which is now the profile's white, so a rebuilt pack
  again demonstrates PASS and FAIL for this row (checked by the release
  tier's `tests/test_the_release_demo_package.py`, B8-1016). Measured on the
  pack rebuilt from this tree: every one of the 51 dates now aims at its
  profile's own white (L\* 94.0 to 96.0), the papers read 0.52 to 1.52 on
  the PASS dates and 3.02 to 9.02 on the FAIL dates, as designed.
* **Answered "no" by Knut (5820871320), analysed in §32.5:** the six ink corners and
  black keep the ideal sRGB aims (L\* 100 white, the textbook primaries),
  and the control strip ChromIQ declares on a verification chart includes
  those corners, so its ΔE00 carries the gap between the ideal primaries and
  what the printer can print. §9a keeps the corners out of the five ΔE00
  statistics for exactly that reason; the strip was not asked about.

**31.6 Decided without a change (A1 to A5, A7, A13 to A16).** Recorded where
the specification asked them: A3, A4, A5 and A7 are §13.14's questions 1, 2,
3 and 5 (refuse, ask, yes, refuse: as built); A1 is §25.5's run default
(the "Default for this run" row, built in beta 40); A2 is §25.6's refusal to
delete a dated verification's only report (kept); A14 keeps the title
naming the verification chart (B8-811 FC-6; not a question in this
document); A13 is recorded in §2a; A15 in `issue_182_answers.md` §2; A16 in
`reference_charts_and_cmyk_to_rgb.md`. These are DECIDED by Knut's answer;
none of them is "confirmed" behaviour by it, which is section B of the post.

* **Built:** `workflow/measurement_report.py` (`paper_patch_rows`,
  `paper_white_row`, `_device_values_of`, `measurement_facts`, the yardstick
  in `build_report`, `paper_corner_ids`, `paper_reference_of`,
  `deleted_runs_of`); `workflow/gamut_target.py`
  (`profile_media_white_lab`, `GamutSelection.profile_white_lab`,
  `write_colorimetric_reference`, `read_colorimetric_reference`);
  `workflow/measurement_messages.py` (M-REPORT-SCOPE-RUN-DELETED,
  M-REPORT-NO-PAPER-PATCH, `deleted_runs_label`);
  `ui/dialogs/measurement_report_dialog.py` (`_scope_deleted_runs_html`,
  `_report_created_at`, `_saved_documents`, `_note_numbering`,
  `_run_detail_html`, the Overview's paper white cell);
  `ui/tabs/tab_chart.py` (`_offer_rename_for_a_renamed_folder`,
  `_folder_renamed_choice`); `scripts/make_report_limit_demos.py`
  (`apply_design`, `paper_white_lines`).
* **Verified by:** `tests/test_k34_knuts_section_a.py` (20 tests, each red on
  the mutation in its docstring), and the release tier's
  `tests/test_the_release_demo_package.py`.

**Status:** built for beta 42 (B8-1011 to B8-1016), NOT confirmed.


## 32. K36: an ISO report type is judged against an ISO set, no ISO type for a calibration run, the three terms of a report's scope, the paper-patch note, and two analyses (#182, 2026-09-24, beta 42)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5820871320](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5820871320)
(2026-09-24), answering our
[5820168457](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5820168457)
and the ISO question before it; and 5821015462 (*"also check all the help
cards to get the right wording used"*). Where he described the behaviour, the
description is his ruling; what was BUILT waits for his confirmation. Proof:
`~/Desktop/ChromIQ-beta42-proof/knut-k36/` (on screen, EN and DE, before and
after; REPORT.md; `analysis/`). Register: B8-1061 to B8-1069.

**32.1 An ISO report type is judged against an ISO set (K36-1, B8-1061 to
B8-1063).** Knut: *"I think (a), but a user should only be allowed to select
between the 4 ISO options in judged against, and the other options are
greyed while having selected Validation print check or Contract proof check.
Then the user still has room for playing around with limit values."*

* Choosing "Validation print check (ISO 12647-8)" or "Contract proof check
  (ISO 12647-7)" KEEPS "Judged against" when it is one of the four ISO sets
  below, the other standard's included; otherwise it sets it to that
  standard's read-only set (ISO 12647-8:2021 values, ISO 12647-7:2016
  values), never the Custom one, and drops the report's own edited numbers
  as any change of set does (K30). **Amended by Knut, #182
  [5822758830](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5822758830)
  (2026-09-24), answer 4, built for beta 42 (B8-1075), not confirmed:**
  *"Keep whatever was in the "Judged against", as long as it is one of the 4
  that are allowed. If selected "Judged against" are one of the other types
  not allowed, then the "Judged against" is set to the matching ISO 12647
  type that belongs to the Report type (not the custom ISO)."* It read
  "always" before, and moved a Custom ISO set to the read-only one.
* While such a type is chosen, "Judged against" offers only ISO 12647-7,
  ISO 12647-8, Custom ISO 12647-7 and Custom ISO 12647-8; ChromIQ default,
  ChromIQ tight and Quick check are shown greyed, each with the tooltip
  *"Not with the report type “{type}”: it is judged against one of the four
  ISO limit sets (…). Choose another report type to judge against this
  set."* The user may move among the four. Choosing any other type makes
  every set choosable again and leaves the set where it is, **except that
  a set an ISO type MOVED is put back** (challenge 4 of beta 42, B8-1073,
  B8-1074, Basti's option (a), not confirmed): the pulldown takes every
  wheel notch and arrow key as a choice, so walking it past an ISO type
  replaced the set for good. The set the ISO type replaced (in the report
  window with the report's own edited numbers) is remembered and restored
  when the type leaves the two ISO types; a set the ISO type kept needs
  nothing restored. The same in Preferences' "Report type, default".
* **Every place both are chosen together:**

| place | what pairs with what | behaviour |
|---|---|---|
| Measurement Report window | "Report type" with "Judged against" | as above |
| Edit limits…, row "Used for this report" | the report's type | the three ChromIQ radios greyed with the same tooltip |
| Edit limits… and Preferences' Report limits…, row "Default for new reports"; Edit limits…, row "Default for this run" | Preferences' "Report type, default" | greyed the same way while that default is an ISO type, and still greyed after any number in the window is edited (B8-1071: an edit re-enabled them) |
| Preferences, Reports, "Report type, default" | the default limit set | choosing an ISO type keeps an ISO default set and otherwise makes its standard's set the default set (buffered, written by Save), remembering the set it replaced for when the type leaves the ISO types; Save keeps an ISO default set beside an ISO default type |
| the settings store itself (`AppSettings`, B8-1072) | `report_default_type` with `compliance_default_set` | no write leaves an ISO default type beside a non-ISO default set: the set is held to the type on every write (logged), and a pair already on disk is repaired to the standard's set when it is read (logged) |
| "Which presets can be used for verification?" | its Report type with its Judged against | choosing an ISO type keeps one of the four ISO sets and otherwise moves Judged against to its standard's set; ChromIQ's three sets greyed; "All metrics" stays choosable (it is not a set). This refines §30.1's "individually change" for the two ISO types only |
| a new report ("New report…"), the report written after a measurement, the verification pre-flight | Preferences' type with the run's own default set, else Preferences' set | an ISO type with a non-ISO starting set starts on the type's standard's set, and an ISO starting set is kept (`set_held_to_type`, `limits_held_to_type`); nothing is written onto the run |

* **A saved report that combines an ISO type with another set** (every
  report written before this rule could): it opens as it was saved, the two
  pulldowns showing its own pair. A NEW Generate of that pair is refused:
  Generate is greyed and the line under it says *"A report of the type
  “{type}” is judged against one of the four ISO limit sets. This report was
  saved with another set and is shown as it was saved. Choose an ISO set in
  “Judged against”, or another report type, to generate it again."* The two
  pulldowns stay live because they are the way out (`_grey_what_cannot_help`
  is asked without this reason; "Show detailed data" is greyed with Generate
  as before). Choosing an ISO set raises the red line and Generate asks
  M-REPORT-UPDATE-OR-NEW, unchanged (measured on screen:
  `knut-k36/after-*/photographs/*-k1s-*`). Nothing on disk is rewritten.
* The Report type help's "Any set can be chosen with any type" now says the
  two ISO types are the exception.

**32.2 A calibration run offers no ISO report type (K36-2, B8-1064).** Knut:
*"[Should a Calibration run offer the two ISO types at all?] No, but the limit
sets can still be chosen, if the user wants to use those metrics and threshold
values in the report."* This reverses §30.6 (B8-994) for Calibration only.
`report_types_for_kind(KIND_CALIBRATION)` is every type but the Printing
record and the two ISO types; the two are shown greyed with *"Not for a
calibration run: the two ISO report types are for verification runs. A
calibration run's report can still be judged against an ISO limit set,
chosen in “Judged against”."* Every limit set, the four ISO ones included,
stays choosable for a calibration report (32.1 does not reach it, no ISO type
being possible). A Preferences default of an ISO type is fitted to the kind,
so a calibration's report starts as a Full colour check.

**32.3 The three terms of a report's scope (K36-3, B8-1065, B8-1066).**
Knut: *"when saying "profile run" do you mean the report was for measurements
when run type is profiling? Maybe a the terms to differentiate between the
different reports' scope could be (suggest something better if you want)
"profile run", "verification run" and "calibration run"? Maybe the message
should take this into account too, and that the wording used is recorded in
the help card Dictionary, so it is clearly defined. Then the use of these
terms should be standardised in all help text and report texts, so that
there is no confusing terms being used."*

Inventory first (the user-facing catalogue, 6,222 strings): "profile run" in
108, "verification run" in 36, "calibration run" in 3, "profiling run" in 9,
"measurement run" in 10, "profiling / verification / calibration
measurement" in 49, "run type" in 71; 574 `tr()` literals in the code name a
run in some form. The app's own meaning of "profile run" is the NUMBERED run
(the "Profile run" box of the Profile-run bar, `runs/runN/`), which holds its
profiling measurement AND its verifications, and "verification run" was
already used for that run seen with Run type Verification. Knut's three terms
are kept, defined so that they fit that model:

* **Profile run**: one numbered run of a project (run 1, run 2, …), holding
  one profile's chart, profiling measurement, profile and verification run.
  A measurement report of it (Run type Profiling) is a Printing record of its
  profiling measurement.
* **Verification run**: the checks of one profile run's finished profile
  (Run type Verification): its verification chart and a dated verification
  measurement per check, in the run's "verifications" folder. Its reports
  judge the dated measurements.
* **Calibration run**: the project's one calibration (Run type Calibration),
  in its "cal" folder. Its reports judge its measurement; no ISO type.

**Accepted by Knut** (the wording of these three Dictionary definitions),
#182 [5822998064](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5822998064)
(2026-09-24): *"Perfect. Accepted."* This accepts the three definitions as
worded; it does not confirm the rest of §32, and the sweep of the other help
texts (B8-1066, below) stays open.

So M-REPORT-SCOPE-RUN-DELETED's "profile run" is the numbered run, whichever
of its measurements the report covered: its words stand and it is APPROVED
(Knut: *"Given the above, the message is accepted."*).

Changed to the terms: the three Dictionary entries (Verification run new,
Profile run and Calibration run rewritten) and the Run type entry; the help
cards' "profiling run" and "a Verification run"; the file guide's "profiling
runs"; the report text: Report Scope's headings ("The following verification
run(s) / profile run(s) / calibration run(s) is/are included:", where it read
"profile verification run" and "profile's measurement run"), a profiling
report's count ("· 3 profile runs"), "Detailed data per measurement",
"Measurement of {date}, {n} patches", "measurements" where "runs" meant
measurements (the mixed-instrument and missing-corner warnings, the trend
graph's empty line, the several-places line). A dated verification is still
counted as a measurement (B8-928). German by hand (Profillauf,
Verifizierungslauf, Kalibrierungslauf).

**The rest of the sweep is OPEN (B8-1066):** the full sweep is over the
60-string threshold, so the other help texts and tooltips (87 flagged strings
of the 574, in 16 files) wait in the register with their list.

**32.4 M-REPORT-NO-PAPER-PATCH names the sheet (K36-4, B8-1067).** Knut:
*"do you mean the "chart sheet" or do you mean "nothing in this report"? Make
sure the text cannot be misunderstood. Then this message is accepted."* The
code decides it PER MEASURED SHEET: `build_report` finds the paper patch and
chooses the yardstick for each measurement on its own, and the note is on
that sheet's "Paper white" line (one number shared by every sheet that
carries it). Now: *"The chart of this measured sheet has no patch printed
with no ink, so the paper white of this sheet could not be measured. Every
colour on this sheet is therefore judged as measured, in absolute Lab, and
none relative to the paper. Only the sheets that carry this note are
affected, not the rest of the report."* APPROVED (§M).

**32.5 The other seven cube corners of a FROM PROFILE GAMUT chart (K36-5,
B8-1068; analysis, no change).** Knut: *"no. It is the ideal corner values
that are put into the ti1 file of a chart, and they are used and compared
against that. IS there a disadvantage in doing this? or the other method?
There are also consequences for the code to change this."*

* What "Expected" is today. The .ti1 carries the corners' INK amounts
  (device 0 / 100); the Lab a corner is compared with lives in the chart's
  colorimetric reference (`…-reference.ti3`), where `gamut_target` writes
  each device corner read as sRGB (`_corner_ideal_labs`), and since §31.5
  the white corner the profile's paper. So a corner's ΔE00 is the distance of
  this printer's primary from an ideal sRGB primary, plus any drift.
* Measured. On the demo pack (synthetic profiles close to sRGB) the ideal and
  the profile's prediction differ by 1.8 to 6.1 ΔE00 for the six ink corners
  and 0.1 for black (`analysis/k36_5.txt`). Through a vendor profile of a
  real printer (Epson ET-8500, Premium Luster) they differ by 5.8 (red) to
  47.8 (green), black 4.0 (`analysis/k36_5_vendor_profile_corners.txt`).
* Ideal aims (today). For: fixed and printer-independent, the same reading
  every chart kind uses, so the corner trend compares across charts, profile
  rebuilds and projects; no dependency on the profile's accuracy; nothing to
  change. Against: the number is not an accuracy figure (it is mostly the
  printer's gamut), and on a real printer it is large on every sheet.
  §9a already keeps the corners out of the five ΔE00 statistics for that
  reason, but **the control strip ChromIQ declares on a verification chart
  includes the corners**, so the three control-strip rows carry the gap too,
  and a set that limits them can fail a print for its gamut.
* Profile-predicted aims. For: the corners would measure accuracy like
  every other patch of the chart (whose aims are the profile's reachable
  colours), and the control strip would mean what it says. Against: the aims
  depend on the profile, so corner trends across profiles stop comparing;
  charts made before would keep ideal aims unless the run's profile is asked
  (as §31.5 does for white), which re-works old reports' numbers on an
  Update; the aims come from the profile under test.
* Code that would change: `gamut_target.select_gamut_targets`,
  `write_colorimetric_reference`, `read_colorimetric_reference` (profile
  aims for `CORNER_DEVICES`, recorded with their source), `build_report`'s
  fallback for older references (`paper_reference_of` generalised), §9a
  rule 2, the control strip, the corner trend graph's meaning,
  `make_report_limit_demos.apply_design`, their tests and the release demo
  pack.
* Recommendation: keep "no", as Knut decided. The one disadvantage worth
  acting on is independent of it: **question for Knut**, should the seven
  ink and black corners be left out of the control-strip rows on a FROM
  PROFILE GAMUT chart, as they are left out of the five ΔE00 statistics?
* **Answered (5822998064, 5823088098):** not left out; compared in the
  strip with the profile's prediction instead, option (i). Built, §34.

**32.6 A sheet printed through its profile with a white-mapping intent whose
chart has no paper patch (K36-6, B8-1069; analysis, not built).** Knut:
*"'A sheet printed relative', do you mean printed as relative intent? You
have to analyse the consequence in doing this, or other alternatives, so
that best and most correct way is practiced. I suspect the metrics that this
affects should get a note that explains why the results may be off, but that
the metrics are still performed and judged, with the possible effect that
results may be effected or even fail... Make the analysis to check what is
best. The user could also as an alternative be asked to enter the
manufacturer's brightness value for the paper used."*

* What "printed relative" means in the code: the print record says
  `colour: through-profile` with an intent other than absolute (relative
  colorimetric, perceptual or saturation), or the route `external-cm`, and
  the chart's reference is its design or device values. Such a sheet is
  normally read MEDIA-RELATIVE: every XYZ reading is scaled by the sheet's
  paper white onto D50 (ICC media-relative colorimetry) before it is
  compared. With no paper patch (B8-1014) it is compared as measured.
* Measured on the demo pack (`analysis/k36_6.txt`, `k36_6_measure.py`):
  12 such sheets (5 runs), each re-printed in simulation on four papers
  (the sheet put onto the ideal paper, then onto the paper P); judged
  media-relative (the right answer) and absolute (as built). Absolute minus
  media-relative, median over the sheets:

| row | L* 95.5 / 0.2 / 1.4 | L* 94 / 0.5 / 3 (warm) | L* 96 / 1.5 / -5 (OBA) | L* 96 / 0 / 0 |
|---|---|---|---|---|
| Average ΔE00, all patches | +1.96 | +2.88 | +2.20 | +1.64 |
| Maximum ΔE00, lowest 95 % | +2.55 | +3.71 | +3.56 | +2.22 |
| Average ΔE00, control strip | +2.01 | +3.03 | +2.40 | +1.66 |
| Average ΔE00, surface-gamut patches | +1.88 | +2.80 | +2.09 | +1.56 |
| Maximum ΔCh, grey balance | +1.00 | +2.46 | +4.38 | +0.05 |
| Maximum ΔL*, ramps 30 % to 70 % | +3.61 | +4.96 | +3.20 | +3.20 |

  Under Custom ISO 12647-7 "Average ΔE00, all patches" turned PASS to FAIL
  on 10 or 11 of the 12 sheets on every paper. The error is a BIAS, always
  upward and of known cause (the paper's own tone and lightness), not noise.
  Evenness (4 sheets, `k36_6_even.txt`): an even sheet's "between two of the
  nine areas" rose from 0.10 to 0.53 to 0.76, because the offset differs by
  colour and the areas hold different colours; 4 of 16 verdicts changed.
* Every row affected on such a sheet: the five ΔE00 statistics, the three
  control-strip rows, the surface-gamut and outer-gamut averages, the solid
  colours (ΔE00 and ΔH*ab), both grey-balance rows, the 30 % to 70 % ramps,
  the two evenness rows (less), and the cube-corner table and worst patches
  (information). Not affected: the two repeatability rows (readings compared
  with readings), the paper white and darkest black lines, and "Paper white,
  difference from the reference paper" (it needs a colorimetric reference,
  which is never read media-relative).
* The options:
  * (a) absolute, as built: every row biased upward by 1.6 to 5 on typical
    papers; verdicts wrong in a known direction, silently apart from the
    paper white note.
  * (b) absolute plus a numbered note on each affected row: honest, but the
    FAIL words stay wrong for a reason ChromIQ knows; a report with a
    customer-facing FAIL and a note saying "may be off" is the weakest kind
    of verdict.
  * (c) N-A: correct, loses every row of the sheet.
  * (d) a paper white the user types: a manufacturer's ISO brightness
    (ISO 2470-1, R457, a %) or CIE whiteness (ISO 11475) is ONE number about
    blue reflectance and cannot be turned into L*a*b*: it is not usable. Some
    makers publish CIE L*a*b*, usable only when its illuminant, observer,
    measurement condition (M0 / M1 / M2) and backing match the user's
    instrument; on an OBA paper M0 against M2 alone moves b* by several
    units. A typed white about 1 ΔE00 off the sheet's paper moved the
    averages by about 0.2 and the maxima by about 0.5 (`standin` column).
  * (e) the profile's media white: the sheet was printed THROUGH that
    profile (its file is in the print record, and it is the run's own
    profile), and the profile's media white is this paper, measured by the
    same instrument when the profile was built. Error only from batch,
    ageing and instrument drift, typically under 1 ΔE00, so about 0.2 on the
    averages. Available in every case that is affected.
* **Answered by Knut (5822758830): (e), with (b) only without a profile; built, §33.**
* Recommendation, NOT built (it is not (b), and it changes which numbers a
  report shows): **(e)**, with a numbered note saying that the paper white
  was taken from the profile's media white because the chart has no paper
  patch (a §M-PROPOSED text); (b) only when no profile can be read; the
  profile's white never used when the chart has a paper patch. **Question
  for Knut.**

* **Built:** `workflow/measurement_report.py` (`ISO_JUDGED_AGAINST`,
  `set_allowed_for_type`, `set_held_to_type`, `report_types_for_kind`);
  `workflow/run_compliance.py::limits_held_to_type`;
  `ui/dialogs/measurement_report_dialog.py` (`_on_type_chosen`,
  `_on_set_chosen`, `_grey_the_sets_the_type_refuses`,
  `_hold_the_set_to_the_type`, `_type_refuses_the_set`, the Generate state,
  `_sync_type_combo`, `_scope_html`, the report help texts);
  `ui/dialogs/thresholds_dialog.py::_hold_radio_to_type`;
  `ui/dialogs/settings_dialog.py::_on_default_type_chosen`;
  `ui/dialogs/preset_verification_dialog.py::_on_type_changed`;
  `ui/tabs/tab_measure.py` (`_report_limits_for`, `_preflight_selection`);
  `workflow/measurement_messages.py`; `ui/dialogs/welcome_dialog.py`
  (GLOSSARY); `ui/getting_started.py`, `ui/main_actions.py`,
  `ui/file_guide.py`.
* **Verified by:** `tests/test_k36_knuts_5820871320.py` (14 tests, each red
  on the mutation in its docstring, `analysis/mutations.txt`).

**Status:** 32.1 to 32.4 built for beta 42 (B8-1061 to B8-1067), NOT
confirmed; 32.5 and 32.6 analysed, questions with Knut.


## 33. K37: a white-mapped sheet whose chart has no paper patch is judged against its profile's paper white (#182, 2026-09-24, beta 42)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5822758830](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5822758830)
(2026-09-24), answer 1, on the recommendation of §32.6: *"Recommendation:
(e), with a numbered note on the sheet, and (b) only when no profile can be
read."* The recommendation he accepted is the rule; what was BUILT from it
waits for his confirmation. Proof: `~/Desktop/ChromIQ-beta42-proof/knut-k37/`
(on screen, EN and DE, before and after; REPORT.md; `analysis/`). Register:
B8-1081 to B8-1084.

**33.1 Which sheets.** A sheet printed through its profile with an intent that
maps white to the paper (the print record's colour `through-profile` with an
intent other than absolute, or the route `external-cm`), judged against the
chart's design or device reference, whose chart has NO patch printed with no
ink (§31.4). Every other sheet is unchanged: a sheet with a paper patch still
uses its own paper patch, and the profile's white is never used then; an
absolute or raw print, a sheet with no print record and a colorimetric
reference are judged as measured, as before.

**33.2 (e): the paper white of the profile (B8-1081).** In order:

1. the profile the print record names (`profile_path`), when that file is
   still on disk: the profile the sheet went through;
2. else the run's own built profile, the profile such a sheet of that run is
   printed through and the one §31.5 (A11) asks for a FROM PROFILE GAMUT
   chart. One reader serves both (`_run_profile_white`).

The profile's media white (`wtpt`, `gamut_target.profile_media_white_lab`) is
put into XYZ and every reading is scaled by it onto D50, exactly as a sheet's
own paper patch is (ICC media-relative colorimetry); evenness carries its aims
onto that paper (`aims_on_the_paper`, §21.1). The report records it as
`paper_white_used = {"from": "profile", "source": "printed_through" |
"run_profile", "profile": <file name>, "lab": [L, a, b]}`.

* **"Paper white" still reads N-A**: the sheet's paper was not measured, and
  the profile's white is not written as the sheet's paper white. The Paper
  white (L\*) graph draws no point for such a sheet, as for every sheet with
  no paper patch (§31.4). Seen on screen and not changed: with no point on
  either date, that graph says "A trend graph needs at least two
  measurements", which is the existing placeholder and not the reason
  (B8-1084).
* **The note on the "Paper white" line** is M-REPORT-PAPER-WHITE-FROM-PROFILE
  (**PROPOSED**, §M-PROPOSED), filled in per sheet with the profile's file
  name and its white:

  > The chart of this measured sheet has no patch printed with no ink, so
  > the paper white of this sheet could not be measured. The sheet was
  > printed with an intent that maps white to the paper, so its colours are
  > judged relative to the paper white recorded in the profile {profile}
  > (L\* {L}, a\* {a}, b\* {b}), which is the paper that profile was made
  > for. If this sheet's paper differs from it (another batch, or paper that
  > has aged), the results can be off by a little. Only the sheets that
  > carry this note are affected, not the rest of the report.

  Two sheets through one profile share one number; two through different
  profiles get one each.
* **M-REPORT-NO-PAPER-PATCH (approved) and this rule.** Its second sentence,
  "Every colour on this sheet is therefore judged as measured, in absolute
  Lab, and none relative to the paper", is FALSE on an (e) sheet. So on such a
  sheet the (e) note takes its place (it also says why Paper white reads N-A);
  M-REPORT-NO-PAPER-PATCH stays, word for word, on every sheet with no paper
  patch that is judged in absolute Lab, which is where it is true. No approved
  word changes.
* **"How the colours were judged"** (the printing block) reads, on such a
  sheet: *"relative to the paper white recorded in the profile {profile},
  because this sheet's chart has no paper patch: the print mapped white to the
  paper, so the paper itself is not counted against the profile"* (report
  text, not a §M message; new, for Knut to read with the two notes).

**33.3 (b): no profile can be read (B8-1082).** Neither the print record's
profile nor a built profile in the run: the sheet is judged in absolute Lab,
as before K37 (`paper_white_used = {"from": "unavailable"}`).
M-REPORT-NO-PAPER-PATCH stays on the "Paper white" line, and every row the
paper white moves carries M-REPORT-JUDGED-ABSOLUTE-NO-PAPER-WHITE
(**PROPOSED**), one number for all of them, where the row has a verdict:

> This sheet was printed with an intent that maps white to the paper, so its
> colours should be judged relative to its paper white. Its chart has no
> patch printed with no ink, and no profile could be read to take the paper
> white from, so these rows are judged as measured, in absolute Lab. The
> paper's own lightness and tint then count against every colour, so these
> results can read worse than the print is (on typical papers by about 1.5
> to 3 ΔE00 on the averages), and a limit can fail for that reason alone.
> Only the sheets that carry this note are affected.

The rows (`ROWS_MOVED_BY_THE_PAPER_WHITE`, from §32.6): the five ΔE00
statistics, the three control-strip rows, the surface-gamut and outer-gamut
averages, both grey-balance rows, the 30 % to 70 % ramps and the two evenness
rows. Not the repeatability rows (readings against readings) and not the rows
that need a colorimetric reference (such a sheet never has one).

**33.4 Measured (B8-1083).** `analysis/k37_measure.py`, the K36-6 script
re-run on the built code: the same 12 relative-intent sheets of the demo pack
(copy of the challenge-2 pack), each with its paper patch, put onto a
simulated paper, then reported three ways by `build_report`: media-relative
on the sheet's own paper patch (the right answer), (e) with the paper patch
ignored and the run's profile read as the app reads it, and (b). Built (e)
minus media-relative, median [min, max] over the 12 sheets:

| row | paper = the profile's white | the profile's white + about 1 ΔE00 (batch, ageing) |
|---|---|---|
| Average ΔE00, all patches | +0.00 [-0.00, +0.00] | -0.03 [-0.10, +0.19] |
| Average ΔE00, lowest 95 % | +0.00 | -0.03 [-0.10, +0.21] |
| Average ΔE00, control strip | +0.00 | +0.03 [-0.01, +0.12] |
| Average ΔE00, surface-gamut patches | +0.00 | -0.00 [-0.07, +0.29] |
| Maximum ΔE00, lowest 95 % | +0.00 [+0.00, +0.01] | +0.24 [-0.06, +0.42] |
| Maximum ΔCh, grey balance | +0.00 | +0.56 [+0.41, +0.72] |
| Maximum ΔL\*, ramps 30 % to 70 % | -0.00 | -0.33 [-0.43, +0.39] |

(b), absolute, on the same sheets: +2.12 [+1.34, +2.60] and +1.89 [+1.03,
+2.26] on "Average ΔE00, all patches". Under Custom ISO 12647-7 "Average
ΔE00, all patches" changed verdict on **0 of 12** sheets under (e) on the
profile's paper and **1 of 12** with the 1 ΔE00 drift (a border sheet, FAIL
to PASS), where (b) turned PASS to FAIL on 11 and 10 of 12. Every verdict of
the set: 0 of 240 changed under (e) on the profile's paper, 2 of 240 with the
drift; (b) changed 85 and 80.

A paper the profile was NOT made for is outside the rule's premise and was
measured for honesty: against the four fixed papers of §32.6, (e) moved
"Average ΔE00, all patches" by +0.12, +0.68, +1.26 and +0.42 (median; the
L\* 96 / 1.5 / -5 OBA paper is about 6 ΔE00 from the profile's white), still
below absolute Lab's +1.64 to +2.87.

On screen (the packs below): the chart's two dates with their paper patches
read "Maximum ΔE00, all patches" 2.25 / 1.10 media-relative; the same
measurements with the paper patches taken out read 3.53 / 3.24 FAIL on the
tree before (absolute), 2.26 / 1.10 under (e), and 3.53 / 3.38 FAIL with the
(b) note when the run's profile is moved away.

**33.5 The demo pack.** No demo sheet is this case: the one chart without a
paper patch (Report-Limits-Strip-And-Gamut/run4) ships with no print record
on purpose, so it stays absolute and keeps M-REPORT-NO-PAPER-PATCH.
`make_report_limit_demos.apply_design` now anchors a relative design of a
chart with no paper patch on the run's profile's white (`paper_white_lab`),
so a future run of that shape is designed the way the report reads it. The
release package lists both new messages with the one step outside ChromIQ that
raises each (`MESSAGE_DEMOS`).

**33.6 A report saved before K37** carries no `paper_white_used` and is worked
out again from its measurement when the window reads it (`ALWAYS_BUILT_BLOCKS`,
§6; the saved verdict carried across untouched).

**Amended (challenge 5 of beta 42, B8-1091, not confirmed): beside its kept
verdict such a report is shown as it was SAVED.** Rebuilding it computes the
blocks it never had; it does not explain its words. The page of a saved
report is drawn from its record: the saved report, completed with the blocks
it lacks, never overwritten by them, and WITHOUT a rule block it did not
record (`paper_patch`, `paper_white_used`, `strip_corner_aims`), because that
block would explain the kept words by a rule they were not worked out by. So a
white-mapped sheet with no paper patch saved before K37 keeps its absolute
numbers, its "Paper white" line carries the approved M-REPORT-NO-PAPER-PATCH
(true of it), and the (e) note and line are not shown. Where this version
would work the report out differently, Report Scope says so once,
M-REPORT-WORKED-OUT-EARLIER (proposed then; APPROVED by Knut, 5831246553,
without its last sentence, K39-1, §35): *"This report was worked out by an
earlier version of ChromIQ and is shown as it was saved. This version works
some of its rows out differently. A newer report of the same measurements
would be worked out the current way."* (It ended *"; Update works the report
out again."*, which named a button.) A
report of several dates records, beside each verdict, the yardstick and the
rule blocks (`judged_block`) from now on. A new report and every live
judgement use this version's working. Measured on screen,
`~/Desktop/ChromIQ-beta42-proof/challenge5-fixes/`.

* **Built:** `workflow/measurement_report.py` (`profile_paper_white`,
  `_run_profile_white`, `paper_reference_of` on the shared reader,
  `PAPER_WHITE_*`, `paper_white_used`, the yardstick in `build_report`,
  `NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE`, `ROWS_MOVED_BY_THE_PAPER_WHITE`,
  `row_values`); `workflow/measurement_messages.py` (the two messages);
  `ui/dialogs/measurement_report_dialog.py` (`_paper_white_from_profile`,
  `_paper_white_note_code`, `_note_numbering`, `_note_sentence`, the Paper
  white line, the printing block, `ALWAYS_BUILT_BLOCKS`);
  `scripts/make_report_limit_demos.py` (`apply_design`);
  `scripts/make_release_demo_package.py` (`MESSAGE_DEMOS`, `RULE_DEMOS`);
  `scripts/drive_b42_k37.py` (the drive).
* **Verified by:** `tests/test_k37_paper_white_from_the_profile.py` (9 tests,
  each red on the mutation in its docstring, `analysis/k37_mutations.txt`).

**Status:** built for beta 42 (B8-1081 to B8-1084), NOT confirmed; two
message texts and the "How the colours were judged" line proposed.

**Words approved, reworded (Knut, #182 [5824834975](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5824834975), 2026-09-25):** he approves M-REPORT-PAPER-WHITE-FROM-PROFILE and M-REPORT-JUDGED-ABSOLUTE-NO-PAPER-WHITE once "sheet" is made clear (he could not tell whether it meant the measured chart, a metric or the report). The bodies quoted above are the words he was shown; the approved bodies name the measurement instead ("The chart of this measurement …", "In this measurement …") and end *"Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual."* The current words are in §M of `unified_measurement_management.md`. M-REPORT-NO-PAPER-PATCH was reworded the same way; its approval (5820871320) is kept. The behaviour is unchanged and still awaits confirmation.


## 34. K37 (i): on a FROM PROFILE GAMUT chart the control strip compares its corner patches with the profile's prediction (#182, 2026-09-24, beta 42)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5823088098](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5823088098)
(2026-09-24): *"Regarding "May we build (i) for beta 42?": Answer: Yes do
so."* The proposal he approved is ours,
[5823015844](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5823015844),
answering his question in
[5822998064](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5822998064)
(*"is it possible to instead choose those seven other cube corners (black,
cyan, magenta, yellow, red, green, blue) to be the corner values within the
gamut? IS that a solution that improves the outcome?"*): *"(i) Keep the same
patches, and judge them in the control strip against the colour the profile
predicts for them. … The cube-corner table and its trend graph keep the ideal
values, as you decided, so their meaning does not change. … A short note
would say so. This applies only to FROM PROFILE GAMUT charts; every other
chart kind is unchanged."* This answers §32.5's question. Proof:
`~/Desktop/ChromIQ-beta42-proof/knut-k37/` (before-i-*, after-i-*). Register:
B8-1085 to B8-1088.

**34.1 What is compared with what (B8-1085).** On a FROM PROFILE GAMUT chart
(a colorimetric reference), in the three control-strip rows only, each of the
seven ink and black corner rungs (composite black, cyan, magenta, yellow,
red, green, blue; the rungs `solid_*` of `workflow/control_strip.py`, found by
the chart's own corner declaration) is compared with the Lab the profile
predicts for its device value (`profile_corner_predictions`: the device value
run forward through the profile with the chart's own intent, `xicclu -ff`).
The bare-paper rung keeps the profile's paper (§31.5). Every other rung is
unchanged: it already aims at the profile's colour.

* **The profile:** the run's own built profile, the one a FROM PROFILE GAMUT
  chart of that run is built from and the one §31.5 and §33 read the paper
  white from (`_run_profile_path`, one reader for all three). This holds for
  charts made before and after this change: the prediction is not stored in
  the chart; it is asked when the report is built. (A limit of that: if the
  profile was rebuilt after the chart was made, the prediction is the new
  profile's, while the chart's other aims were chosen through the old one.
  The report's "the profile has been rebuilt since this sheet was printed"
  line already says when that is the case.)
* **Unchanged, as Knut decided in §32.5:** the cube-corner table, the corner
  trend graph, "Solid colours, largest", "Cyan, magenta and yellow solids,
  largest hue difference" and "Paper white, difference from the reference
  paper" keep the ideal (and §31.5 paper) aims.
* **No profile, or no ArgyllCMS to ask:** today's comparison with the ideal
  values stays (`strip_corner_aims = {"from": "ideal"}`), and the strip rows
  say so.
* **Every other chart kind:** unchanged (`{"from": "not_applicable"}`).
* The report records `strip_corner_aims` (from, profile, which ids); a report
  saved before is worked out again when the window reads it
  (`ALWAYS_BUILT_BLOCKS`, §6).
  **Amended (challenge 5 of beta 42, B8-1091, not confirmed):** beside its
  kept verdict such a report is shown as it was saved (§33.6's amendment):
  its strip rows keep their saved words and notes, no rebuilt
  `strip_corner_aims` is shown with them, and Report Scope carries
  M-REPORT-WORKED-OUT-EARLIER where this version compares the corners with
  the profile's prediction. A report generated with no profile on disk
  compares them with the ideal values and says so
  (M-REPORT-STRIP-CORNERS-IDEAL), because Generate reads the run's profile
  again at the press (B8-1094).

**34.2 The note (B8-1086).** On such a sheet the three control-strip rows,
wherever they carry a verdict, carry one numbered note,
M-REPORT-STRIP-CORNERS-PREDICTED (**PROPOSED**, §M-PROPOSED):

> On this sheet the chart's solid ink, overprint and black patches are
> compared two ways. In the cube-corner table each is compared with its
> ideal value, which shows how far this printer's colour is from the ideal
> one. In the control-strip rows each is compared with the colour the
> profile predicts for it, like every other patch of this chart, which shows
> how accurately it was printed.

and, when no profile could be read, M-REPORT-STRIP-CORNERS-IDEAL
(**PROPOSED**):

> No profile could be read to predict the colours of this sheet's solid ink,
> overprint and black patches, so in the control-strip rows they are
> compared with their ideal values, as in the cube-corner table. That
> difference is mostly how far this printer's colours are from the ideal
> ones, not a printing error, so these rows can read worse than the print
> is. Only the sheets that carry this note are affected.

The note is on the rows and not on the cube-corner table: the table has no
verdict to number. Its text names the table, so a reader of either finds the
other. German by hand.

**34.3 Measured on the demo pack (B8-1087).** `analysis/k37i_strip.py`,
`k37i_compare.txt`, `k37i_rebuilt_summary.txt`.

* **The shipped pack as it is (challenge-2 copy, 51 FROM PROFILE GAMUT
  dates), the tree before against the built code:** the strip's average rose
  by +1.16 median [+1.00, +1.80], its largest difference by +1.66 [+0.00,
  +3.49], and against the set each date was saved with 24 strip verdicts
  turned PASS to FAIL (none the other way). That is the pack's own design,
  not the printer: the generator put every corner EXACTLY on its ideal value
  (so the corner rows could be designed), which no printer can do, and the
  corner then sits the whole ideal-to-prediction gap (1.4 to 8.1 ΔE00 for the six inks on
  these profiles, blue the largest) from what the strip now compares it
  with.
* **So the generator was adjusted, and the four projects that hold such
  charts rebuilt with it** (`--only`, 102 dated verifications, 102 matching
  their design; `analysis/rebuilt-subset/generator-build.txt`). The overprints
  R, G, B (judged only in the strip) go on the prediction, which is what a
  printer prints; the solids C, M, Y and the black (judged by the corner rows
  too) go between their two aims (`_between_two_aims`): the designed hue
  difference from the ideal kept exactly, inside 85 % of the run's own
  solid-colour limit, and otherwise as near the prediction as that allows.
  Measured on the rebuilt dates: every strip verdict is the one its date
  designs. On Report-Limits-Second-Route, whose profile lies furthest from
  the ideal, the strip's largest difference on the dates designed to pass
  fell from 3.93 to 11.12 (the ideal comparison, FAIL on 10 dates designed to
  pass) to 2.34 to 5.89, and those dates now PASS.
* **One cell cannot be met on this kind of chart and is now designed over:**
  the tight column (ChromIQ tight, 1.5 on "Solid colours, largest" and 1.5 on
  the strip's largest difference). The ideal and the prediction of a solid
  lie 3.0 to 4.9 ΔE00 apart on these profiles, more than both limits
  together, so the solids are kept inside the solid-colour row (no other
  chart kind can show it passing) and "Control-strip patches, largest
  difference" stays over on that column's FROM PROFILE GAMUT dates
  (Every-Limit-Set/run4, Second-Route/run4); the dates say so, and the same
  column's ordinary chart shows the row passing. This is Knut's decision
  meeting physics, and worth his eye: on a real printer the solids against
  their ideal values will usually read well over a tight limit.

**34.4 On screen.** Report-Limits-Second-Route/run2, "New report…", every
date, judged against Custom ISO 12647-7 (chosen the same way in every drive):
before, the strip rows carry no note; after, on the rebuilt pack, the two
strip rows carry M-REPORT-STRIP-CORNERS-PREDICTED ("1)"), largest 2.34 PASS on
the dates designed to pass; with the run's profile moved away and the saved
reports removed, the same rows carry M-REPORT-STRIP-CORNERS-IDEAL and read
6.83 FAIL. The cube-corner table reads the ideal comparison in all three.
(Under Custom ISO 12647-7, which is not this run's own set, "Solid colours,
largest" fails on the rebuilt dates: the generator places the solids inside
the run's OWN limit, ChromIQ default's.)

* **Built:** `workflow/measurement_report.py` (`_run_profile_path`,
  `profile_corner_predictions`, `corner_predictions_through`,
  `CORNER_AIMS_*`, `strip_corner_aims`, `strip_ref` in `build_report`,
  `NOTE_STRIP_CORNERS_*` in `row_values`); `workflow/measurement_messages.py`;
  `ui/dialogs/measurement_report_dialog.py` (`_note_sentence`,
  `ALWAYS_BUILT_BLOCKS`); `scripts/make_report_limit_demos.py`
  (`_between_two_aims`, `_corner_budgets`, `corner_bound` in
  `matrix_dates`, the strip solver on the strip's own aims);
  `scripts/make_release_demo_package.py`; `scripts/drive_b42_k37.py` (scene
  i).
* **Verified by:** `tests/test_k37_paper_white_from_the_profile.py`
  (`test_i_*`, 7 tests, each red on the mutation in its docstring,
  `analysis/k37_mutations.txt`), and the release tier's demo-package tests.

**Status:** built for beta 42 (B8-1085 to B8-1088), NOT confirmed; two
message texts proposed.

**Words approved, reworded (Knut, #182 [5824834975](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5824834975), 2026-09-25):** he approves M-REPORT-STRIP-CORNERS-PREDICTED and M-REPORT-STRIP-CORNERS-IDEAL once "sheet" is made clear (he could not tell whether it meant the measured chart, a metric or the report). The bodies quoted above are the words he was shown; the approved bodies name the measurement instead ("The chart of this measurement …", "In this measurement …") and end *"Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual."* The current words are in §M of `unified_measurement_management.md`. M-REPORT-NO-PAPER-PATCH was reworded the same way; its approval (5820871320) is kept. The behaviour is unchanged and still awaits confirmation.


## 35. K39: report text names no feature, action or button of the app (#182, 2026-09-25, beta 43)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5831246553](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5831246553)
(2026-09-25), on M-REPORT-WORKED-OUT-EARLIER:

> *"This part "Update works the report out again." is not according to rules
> for report text and notifications in the report. It refers to features,
> actions or buttons in the app interface, which shall never be part of the
> notes or the report text. Make sure all reports and notes do not directly
> mention such things, but if helpful for a user or customer to understand
> instead mentions topics in a general term without referring to features,
> actions or buttons in the app interface. Besides this, the message is
> approved."*

The rule is his and is recorded in §19.1. What follows is what was done for
it; the rewordings wait for his confirmation. Register B8-1111 and B8-1114.

**35.1 What counts as report text.** The page of the Measurement Report
window, the PDF, Report Scope, Report Results and its numbered notes, the
Overview, "How to read this report", the detailed section, the graphs and
the lines printed with them, the metric names and blurbs, the standard
caveat, the summary reasons, and every §M message printed in a report (the
catalogue marks them "window and PDF" or "report text"; M-REPORT-PATCH-
COUNTS-DIFFER is printed too). Window text may name controls: the question
boxes, the red line, the reasons under "Generate report", tooltips, the
settings help, and the empty page (which is shown only when there is no
report, and is never saved or printed).

**35.2 How it was audited.** (a) Every `tr()` literal of the functions that
compose the report (`REPORT_FUNCTIONS` in the guard test below) was read.
(b) The page and the PDF body were composed for 107 measurements of the
beta 41 demo pack (`~/Desktop/ChromIQ-beta42-proof/challenge-2/pack/`, a
copy), for every saved report in "Report shown" and for "New report…" with
every measurement ticked under every report type and limit set the window
offers, detail on: 3,397 distinct sentences, each searched for the words of
the app's interface. (c) The German of every such text was searched for the
German words of the interface.

**35.3 What was changed (old → new).**

| where | old | new |
|---|---|---|
| Report Scope, M-REPORT-WORKED-OUT-EARLIER (§M, APPROVED with this change, 5831246553) | "This report was worked out by an earlier version of ChromIQ and is shown as it was saved. This version works some of its rows out differently; Update works the report out again." | "This report was worked out by an earlier version of ChromIQ and is shown as it was saved. This version works some of its rows out differently. A newer report of the same measurements would be worked out the current way." |
| Report Scope, the count of a verification report across profile runs | "This report covers {n} of the {total} measurements recorded for the {runs} profile runs it was chosen from." | "This report covers {n} of the {total} measurements recorded for the {runs} profile runs it is drawn from." |
| Detailed data, a FROM PROFILE GAMUT chart whose reference file is missing, first paragraph | "… measured against the wrong yardstick, so ChromIQ shows none at all." | "… measured against the wrong yardstick, so none are shown." |
| the same, second paragraph | "If the file was moved, put it back next to the chart in the run's “verifications” folder and reopen this report. If it is gone for good, generate the verification chart again — a fresh chart brings a fresh reference with it." | "The reference file belongs next to the chart in the run's “verifications” folder and is not there. A chart made again carries a reference of its own." |
| a trend graph with fewer than two values (printed in the PDF, B8-1084) | "Fewer than two of the ticked measurements have a value for this graph, so it draws no trend. The notes under the results say why a value is missing." | "Fewer than two of the measurements in this report have a value for this graph, so it draws no trend. The notes under the results say why a value is missing." |

German by hand for each. No other approved §M message printed in a report
names the app, so none went back to awaiting approval.

**35.4 Kept, as window text** (B8-1114, for Knut's eye): the empty page's
three sentences ("… Measure its chart on the Measure tab, or add measurements
with “Add Profile's Measurements…”."); two placeholders of an empty graph that
the PDF never prints ("Choose a report type or a limit set that judges them to
see their trend.", "Add another measurement, or tick more of the measurements
in the list above. “Select all” ticks every one of them."); the hover text of
a saved COND cell ("Generate the report again to have it judged by today's
rule.").

**35.5 The guard.** `tests/test_report_text_names_no_part_of_the_app.py`
scans the four sources of report text (the report functions' `tr()` literals,
the tables they print from, the §M messages printed in a report, and the
rendered page and PDF body of a graded report, a Printing record and a saved
report worked out earlier) and the German of each, for the controls by name
("Generate", "Update", "Create New", "Edit limits", "Preferences", "Report
shown", "New report…", the list's buttons, the tabs), the words for controls
(button, tab, menu, pulldown, tick box, dialog) and the verbs a reader
operates them with (click, press the …, tick, choose, reopen). An exception
goes into its `ALLOWED` table with the reason, never into the pattern.

* **Built:** `workflow/measurement_messages.py`,
  `ui/dialogs/measurement_report_dialog.py` (`_scope_html`,
  `_run_detail_html`, `_TrendChart.empty_reason`), `data/i18n/*.json`.
* **Verified by:** `tests/test_report_text_names_no_part_of_the_app.py`
  (each test red on the mutation in its docstring).
* **Proof:** `~/Desktop/ChromIQ-beta43-proof/k39-report/` (on screen, EN
  and DE, before and after).

## 36. K40: every preset laid out behind the scenes, the tone row on a FROM PROFILE GAMUT chart's neutral aims, and a demo project that answers every metric (#182, 2026-09-25, beta 43)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5832026677](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5832026677)
(2026-09-25), answering the K39-8 analysis
(`~/Desktop/ChromIQ-beta43-proof/k39-export-import/REPORT.md`):

> *"the presets are mostly created with ChromIQ layout engine, not printtarg.
> Also, each preset has all layout information, so the "Which presets can be
> used for verification" must layout that preset behind the scenes, if
> needed, so that the window can judge it."*

and to its two questions, *"Yes"* (row 20 on a FROM PROFILE GAMUT chart uses
the neutral aims, as the grey rows do) and *"yes"* (a demo project with such a
chart). The rulings are his; what was BUILT from them waits for his
confirmation. This section SUPERSEDES the "laid out later" clause of §16.4 and
answers the question left open in §26.5. Register B8-1121 to B8-1125. Proof:
`~/Desktop/ChromIQ-beta43-proof/knut-k40/` (on screen, EN and DE, before and
after; REPORT.md).

**36.1 K40-1: every preset reaches the evenness rows with its own layout.**
A preset is judged with the layout Generate would give it, and nothing else:

| the preset | its layout | how the page is known |
|---|---|---|
| a built-in with a layout-engine recipe | the recipe | the engine's own arithmetic (`_predicted_grid`), as since beta 37 |
| a built-in "Full layout setup" ENGINE preset | the recipe selecting it builds (`tab_chart.fls_engine_recipe`) | the same; until K40-1 two of them read "laid out later" |
| a built-in printtarg preset without a `.ti2` beside it (none ships today) | printtarg | laid out behind the scenes, as below |
| a user preset saved with the engine on | the `layout_recipe` it stores | the engine's arithmetic |
| a user preset saved with the engine off | printtarg, with the arguments Generate builds from the preset's own rows (`chart_creator.printtarg_layout_argv` over `ChartCreator._build_printtarg_args`) | printtarg run on a copy of the patch set in a temporary folder; its `.ti2` and page images read by the report's own `chart_grid` (strips, rows, the 60 % coverage from the page image), then the folder removed |
| a chart with a `.ti2` beside it (the prebuilt bundles, the current chart) | that `.ti2` | `chart_grid`, as before |

* **Never in the window's thread** (*"It must never block the window"*). A
  printtarg layout, and any preset whose answer the tab's idle warming has not
  reached yet, is worked out on one background thread
  (`workflow/preset_layout.py`). Until it arrives the row reads **"Working…"**,
  its metrics are listed under **"Still being checked"** with *"ChromIQ is
  laying this preset's page out to check it. The answer appears here in a
  moment."*, the figures line adds **"Still being checked: n"**, and the row is
  redrawn by itself when the answer arrives (a timer reads one integer; the
  thread touches no Qt object). The reader's own chart, the first line, is
  answered at once. No dialog is ever shown.
* **Cached by content.** The key is the patch set's bytes, the printtarg
  arguments and the printtarg binary, so a preset renamed or re-saved unchanged
  is not laid out again, and an Argyll upgrade lays everything out again. The
  cache lives for the session.
* **When the layout cannot be computed** the two evenness rows say why, as
  other unanswerable rows do: *"printtarg, which lays this preset's page out,
  was not found in the ArgyllCMS folder set in Preferences, so where its
  patches will sit on the page is not known."* (`evenness_layout_no_tool`), or
  *"… could not lay it out …"* (`evenness_layout_refused`) followed by
  *printtarg said: "…"* with printtarg's own line. Neither offers the metric's
  own lever (a larger chart does not make printtarg appear). Both are file and
  tool reasons: they never take the star.
* **What the behind-the-scenes layout does not reproduce:** ChromIQ's own
  post-processing of a printtarg page (the stamped notes; on an i1Pro with the
  ChromIQ clip style the band painted in after the patches are moved right).
  None of it changes a page's strips or rows, and the clip band moves the patch
  block sideways without changing its size. printtarg also shuffles the
  patches on each run, so the places differ from the sheet later printed; the
  page grid and the coverage do not.
* **Measured** (this host, 2026-09-25; `knut-k40/REPORT.md`): a printtarg
  layout costs 0.41 to 0.52 s per one-page preset (median 0.45 s: the 300 dpi
  page image and its measurement); the 31 demo verification presets 14.0 s in
  all, on the background thread. On screen, with the demo presets installed
  and nothing warmed (220 presets): before, the window took 6.3 s to open and
  opened fully answered; after, it opens in 1.4 s with 164 rows "Working…"
  and is fully answered about 19 s later, with no click. Built-ins: 154
  answer 15 of 18 (was 152), 14 answer 14, 17 answer 13; none reads "laid out
  later" (was 2).
* **Found by it** (B8-1122): the 31 demo verification presets could never have
  been printed. Their `.ti1` held only the colour table, and printtarg refuses
  that (*"Input file doesn't contain two or three tables"*); the window said so
  the first time it laid them out. The demo pack now writes printtarg's two
  other tables, and every demo is laid out: 3 i1Pro strips on A4, so both
  evenness rows read "fewer than 9 strips" on each (the pack's new constant).

**36.2 K40-2: the 30 to 70 % tone row on a FROM PROFILE GAMUT chart.**
On a chart that carries a colorimetric reference (the report's
`reference_source == "colorimetric"`; the chart's `-reference.ti3` in the
presets window), the tone row's GREY axis is the chart's neutral aims, as the
grey rows' steps are (§26.5):

* a step is a patch whose AIM is neutral, ``hypot(a*, b*) <
  NEUTRAL_AIM_CHROMA_MAX`` = 1.0; the eight cube corners never;
* **our construction, to confirm:** each is placed at the tone value
  **100 − its aim's L\***, so the band 30 % to 70 % is the aims from L\* 70 down
  to L\* 30, and the count (3 distinct steps), span (20) and spacing (rule A, 4)
  rules are asked of those levels unchanged. §26.5 left open *"by which tone
  value: an L\* is not a tone value"*; this is the grey rows' own reading
  (an aim placed by its L\* on a 0 to 100 scale), turned into a tone value the
  way a device grey's is (100 − level);
* its ΔL\* is each step's measured L\* against its own aim;
* device greys (R = G = B) do not count on such a chart, as for the grey rows;
  the R, G and B axes stay device axes, as on every chart;
* two reasons of their own, because "raise Single Channel Steps or Grey Axis
  Steps" is not a lever such a chart has: `ramp_too_few_neutral_aims` and
  `ramp_neutral_aims_bunched` (which names the LIGHTNESS no aim is near). The
  presets window files both as a patch shortfall, and the lever the help icon
  offers for them is a larger chart
  (`compliance_sets.remedy_for`, `_R_RAMPS_AIMS`);
* every other chart is unchanged.

Measured: on the K31 challenge A charts (100 and 400 patches) the row was
answered by device greys before and is answered by the neutral aims after; on
a 216-patch chart through the demo profile below, "no tone ramp" before and
answered after (3 of 10 aims picked at tone 32.4, 48.2 and 65.0).

The metric's help icon states the rule (EN, and German by hand), and so do its
lever, the report's help paragraph on what a chart must carry, the Dictionary's
"Grey ramp", the report's N-A sentences (which name no part of the app, §35) and
the presets window's lines.

**36.3 K40-3: Report-Limits-Every-Metric, one chart that answers every
metric.** Built by `scripts/make_every_metric_demo.py`, in the release package
beside the other projects (README and COVERAGE entries):

* run1's profile is built from an ordinary 210-patch chart on the baryta paper
  class; its verification chart is built FROM PROFILE GAMUT through that
  profile by ChromIQ's own module: 632 colours, **8 of them printed twice**,
  and the 8 cube corners, 648 patches, laid out by the layout engine with the
  built-in "A4-648p-1page-Portrait-w7.5mm" i1Pro preset (24 strips by 27 rows,
  69 % of the page covered);
* it answers **18 of 18** in the presets window, and the two repeatability
  metrics as well: it repeats 8 colours, and it is measured three times;
* judged against **Custom ISO 12647-8**, the one set that limits all twenty:
  2026-11-02 everything inside its limit (19 PASS, "the same chart measured
  again" N-A on a first measurement), 2026-11-09 the same chart measured again
  (20 PASS), 2026-11-16 everything over its limit (20 FAIL). The build stops
  when a date's report reads otherwise;
* the readings are synthetic (the report's own aims plus a designed residual);
  a solid and the black sit between their ideal value and the profile's
  prediction, the overprints on the prediction (§34);
* the printing is recorded **raw**: the Print tab forces Raw for a converted
  chart (§3.1a), and such a sheet is still graded.

* **Built:** `workflow/preset_layout.py`; `workflow/preset_eligibility.py`
  (`_evenness_grid_for`, `chart_row_values(lay_out=)`, `values_ready`,
  `request_values`, `is_being_laid_out`, `layout_is_ready`,
  `layout_failure_detail`, the three `REASON_EVENNESS_LAYOUT*` codes,
  `_perfect_print`); `workflow/chart_creator.py` (`printtarg_layout_argv`,
  `engine_build_kwargs`); `ui/tabs/tab_chart.py` (`builtin_preset_layout`,
  `fls_engine_recipe`, `verification_preset_rows`,
  `_open_preset_verification_window`); `ui/dialogs/preset_verification_dialog.py`
  (`reason_line`, `detail_lines`, `_columns`, `_watch_layouts`,
  `_poll_layouts`, `wait_for_layouts`, `background=`);
  `workflow/measurement_report.py` (`ramps_block(neutral_aims=, corner_ids=)`,
  the two `REASON_RAMP_*` codes, `build_report`); `workflow/compliance_sets.py`
  (`_D_RAMPS`, `_R_RAMPS_DEVICE`, `_R_RAMPS_AIMS`, `remedy_for`);
  `ui/dialogs/measurement_report_dialog.py` (`_reason_sentence`,
  `_CHART_HELP`); `ui/dialogs/welcome_dialog.py`;
  `scripts/make_verification_preset_demos.py`;
  `scripts/make_every_metric_demo.py`; `scripts/make_release_demo_package.py`;
  `data/i18n/*.json`.
* **Verified by:** `tests/test_k40_presets_laid_out_and_the_tone_row_on_aims.py`
  (each test red on the mutation in its docstring,
  `knut-k40/mutations.txt`), `tests/test_the_demo_presets_pair_on_every_requirement.py`,
  `tests/test_the_release_demo_package.py::test_one_project_answers_every_metric_passed_and_failed`
  (release tier).
* **Proof:** `~/Desktop/ChromIQ-beta43-proof/knut-k40/`.

**Status:** built for beta 43 (B8-1121 to B8-1125), NOT confirmed; the tone
value of a neutral aim (100 − L\*) is our construction and is put to Knut.


## 37. K42: the graph tab arrows, and where the one-page summary says what a PASS means (#182, 2026-09-25, beta 43)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Ruled by:** Knut, #182
[5832746557](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5832746557)
(2026-09-25, testing beta 42). His description is the ruling; what was BUILT
waits for his confirmation. Register: B8-1141 to B8-1143. Proof:
`~/Desktop/ChromIQ-beta43-proof/k42/` (on screen, EN and DE, before and
after).

**37.1 The graph tab arrows (amends §28's 27.6).** *"the arrow-buttons to the
right of the tabs do not have an outline like all other buttons controls.
Also, the arrow buttons are now much wider than they were. Reduce the width of
the arrow buttons to what they were before, approx. half the width they are in
beta 42."*

* Each arrow has the outline an ordinary button has in the same appearance
  (light, dark, neutral): the same edge colour, a disabled button's fainter
  edge on a greyed arrow. A greyed arrow keeps its greyed triangle (B8-1002).
* Each arrow is Qt's own scroll-button width (16 px), which is what the arrows
  were before the bar drew its own; beta 42 made each one as wide as the bar
  is tall less 4 px. Height as before. The row still runs from the left edge
  to the arrows with no gap (B8-1008).
* **Built:** `ui/peek_tab_bar.py` (`_arrow_width`, `ARROW_OBJECT_NAME`), the
  `QToolButton#peek_tab_arrow` rules in `ui/styles.py`, `ui/light_styles.py`,
  `ui/neutral_styles.py`.
* **Verified by:** `tests/test_k42_tab_arrows_outlined_and_narrow.py`,
  `tests/test_c2_a_greyed_tab_arrow_looks_greyed.py`,
  `tests/test_k32_peek_tab_bar.py`.

**37.2 What a PASS means ends the Result, not the page (amends §10's T1).**
*"This text should not be at the end, but as an explanation for the results in
the Results section. Move that text to the end of the Results section. IF this
also happens on other report types, do the same there."*

* On the Colour summary (one page), under a limit set named after a standard,
  "A PASS means that the measured values are inside these limits. It is not
  proof that the print meets the standard, and where these limits are wider
  than the standard's own it says nothing about the standard." is the last
  paragraph of the Result section (after the result line, its sentence and
  the evenness paragraph when there is one), in the window and the PDF. It no
  longer closes the page. The text is unchanged.
* Under a set named after no standard, the page still ends with "This page
  says what was measured and what it was compared against; it does not
  certify." (Knut asked only about the PASS sentence.)
* The other five types were checked, window and PDF: none ends with the
  sentence. The Full colour check, the Grey and tone check and the two ISO
  types print the whole caveat among the notes under the Report Results table,
  so it is inside the results section already, followed there by the numbered
  notes; the Printing record grades nothing and does not print it. They are
  unchanged.
* **Built:** `ui/dialogs/measurement_report_dialog.py` (`_one_page_html`).
* **Verified by:** `tests/test_the_one_page_summary_prints_on_one_page.py`
  (`test_the_pass_sentence_is_the_last_paragraph_of_the_result`, window and
  PDF; the page is still one page with it).


## 38. K44: the button Return presses is filled (#182, 2026-09-25, beta 43)

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

**Asked by:** Knut, #182
[5833776276](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5833776276)
(Create New is the default of the Update / Create New question, 27.1, *"but
there is no indication"*) and
[5833983335](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5833983335)
(*"all windows and pop-up windows then should follow the same standard"*).
**Rule set by:** Basti, 2026-09-25. What was BUILT waits for Knut's
confirmation. Register: B8-1151 to B8-1155. Proof:
`~/Desktop/ChromIQ-beta43-proof/k44-default-button/` (on screen, EN, Light,
Dark and Neutral, before and after).

**38.1 The standard, for every window and pop-up.**

* A window that already colours one or more buttons keeps them exactly as
  they are: no colour removed, nothing recoloured, and no second fill.
* A window with no coloured button has its default button, the one Return
  presses, drawn filled: the look of a tab's main action (`#primary`), in the
  window's accent. The accent is the window's masthead colour; for a window
  opened from a tab, the tab's colour; otherwise the application's (blue in
  Light, cyan in Dark). In Neutral it is ACTION. A greyed main action shows
  the greyed primary look and fills when it becomes available.
* A destructive question whose safe default is Cancel (or No, Keep, Go back)
  keeps Cancel as the default and draws it like any button.
* The default does not move with the keyboard focus: Return presses the
  filled button whatever has focus; Space presses the focused one.
* In the Update / Create New question (27.1), Create New is filled in the
  report window's green.
* The Measurement Report and Report limits windows have no default (C9) and
  fill nothing.

**38.2 Put to Knut (B8-1155):** windows where the coloured button is not the
one Return presses, destructive questions whose default is the action,
Neutral's Preferences (Restore Factory Defaults and OK both ACTION-filled),
and four windows that now have no default (Profile info, Measurement info,
Soft-proof, Translate).

* **Built:** `ui/default_button.py`, `ui/theme.py` (`default_button_qss`),
  the three style sheets, `ui/dialogs/tools_dialogs.py`
  (`neutral_controls_qss`), `ui/main_window.py` (per-tab sheet),
  `ui/widgets.py` (`DialogFocusFilter`).
* **Verified by:** `tests/test_the_default_button_is_filled_in_the_accent.py`,
  `tests/test_k44_default_button_audit.py`.

**38.3 A destructive action is never filled** (decision for beta 43,
2026-09-25, B8-1156): delete, overwrite, replace, clear, enable-at-your-own-risk
buttons are drawn like any button even when they are the default. Which button
Return presses in those questions is unchanged and remains with Knut (38.2).
