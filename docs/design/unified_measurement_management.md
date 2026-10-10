# Unified Measurement Management — Design Specification

> **Revision 2026-08-09 (e) — two approved messages carry a revised print step.**
> **Awaiting review:** M-VERIFY-NO-PROFILE and M-VERIFY-NO-CHART (revised wording only), M-CM-NO-CCTIFF, M-CM-CONVERT-FAILED and M-CM-PROFCHECK-CONVERTED (new, feature A), M-VERIFY-CREATE-NO-PROFILE and M-GAMUT-NO-PROFILE (feature B — wording agreed verbatim with Sebastian on #133, 2026-08-02, listed for the formal record), M-IMPORT-MISMATCH and M-IMPORT-DATE-TAKEN (the Measure tab's IMPORT module; its import-done window was approved by Sebastian 2026-08-10), plus the revised M-CHART-VERIFY (W5, reworked after the 2026-08-10 hardware session) and M-HOW-PRINTED (pairing 3 — the measure-time question for sheets ChromIQ did not print), plus M-ALL-STRIPS-PATCHES-LEFT (new, 2026-08-14 — every strip read while patches inside them are not, #156; both are wording only, their bug fixes are already in the code and speak through the log until these are approved), plus M-NO-INSTRUMENT-FAST (new, 2026-08-13 — Knut's ColorMunki was invisible on older hardware until "Faster instrument connection" was switched off, so that variant of the no-instrument window names the shortcut and carries its switch), plus M-ENGINE-FELL-BACK (new, 2026-08-14 — asked for by Knut on #148: ChromIQ's own measuring engine could not use the instrument, so stock chartread took over, which also silences ChromIQ's measurement sounds without saying so) — all defined in the awaiting-review section below, plus M-PATCHSET-MISSING (new, 2026-08-25 — a loaded patch set that had gone from disk wrote one line to the log and built a different chart, in silence), plus M-PATCHSET-KEPT-UNCHECKED (new, beta 45, B8-1460: a chart made before its record said whether its patch set was given, and whose patches targen could not be asked about, keeps them rather than Generate replacing them in silence), plus M-PROJECT-EXISTS (new, 2026-08-27 — a typed project name that already names a project on disk adopted it in silence; Knut reported it and Basti ruled on when it may appear and what it may offer, but the WORDING is new and waits here), plus M-PROJECT-REPLACE-CONFIRM and M-PROJECT-REPLACE-FAILED (new, 2026-08-27 — the second look before §S4.7's "Replace it" clears a whole project, and the window for the case where its promise cannot be kept), plus M-CR30-STOCK-READER (new, 2026-08-28, #159 — a CR30 chart carries the honest name the device reports for itself, which stock ArgyllCMS chartread refuses outright, so the window names the Preferences control that fixes it) and M-CR30-READ-ENDED (new, 2026-08-28, #159 — the same refusal seen from the other end: an engine run that fails on a CR30 chart has no second reader to fall back to, so the two existing fallback messages, one of which promises that every measured strip will be kept, must not be shown) and M-CR30-MAGNET (new, 2026-08-30, #159 — a magnet recalibrated the instrument mid-chart, which happened to Basti with a MacBook under his paper; the session now stops and offers to retake the white calibration instead of inviting another press) and M-CR30-CALIBRATE-BLACK (new, 2026-08-29, #159 — the dark reference, taken against open air with the instrument's own command, offered by an unticked per-use checkbox so it never becomes a second window on every Start) and M-CR30-CALIBRATE (new, 2026-08-28, #159 — Basti ruled that ChromIQ triggers the CR30's white calibration itself on both transports, which deliberately reverses a documented safety rule; the window's warning is about which face of the cap meets the aperture, not about magnets) and M-CR30-INSTRUMENT-GONE (new, 2026-08-28, #159 — the instrument unplugged mid-measurement and ChromIQ said nothing at all) and M-CR30-PATCH-GAVE-UP (new, 2026-08-28, #159 — one refused reading used to end a CR30 session for ever in silence; refusals are now re-armed and this is the window for when re-arming keeps failing) and M-CR30-HOW-TO-MEASURE (new, 2026-08-28, #159 — every other instrument reaches its "how to measure" window through `calibration_done`, which cannot fire when ChromIQ supplies the values itself, so a CR30 user was given a spot session with no on-screen instruction at all) and M-CR30-READ-FAILED (new, 2026-08-30, #159 — a refused reading was announced only in the log, where Basti did not see it; the behaviour was already right and only the place it was said was wrong, so this is a modeless window that closes itself when the reading arrives) and M-CR30-LEARN-TILE (new, 2026-08-30, #159 — the magnet guard recognised one unit's stored white-tile value because it was hard-coded from that unit; every other owner had no protection at all, so ChromIQ now learns it from a single capped press) and M-CR30-TRIGGER-NOT-ARMED (new, 2026-08-30, #159 — taking the reading from the keyboard is measurably steadier than pressing the instrument's button, but a reading ChromIQ asks for cannot report the magnet gate, so it is refused until that instrument's tile is known), plus M-IMPORT-REPLACE-CONFIRM, M-IMPORT-REPLACE-PROJECT-CONFIRM and M-IMPORT-REPLACED-KEPT (new, 2026-08-31 — importing a measurement or a chart under a name that is already a project asked the question in each loader's own words AND with its own consequence: one said “Overwrite existing folder” and destroyed the project outright, the other said “Replace” and archived it. Basti ruled that the consequence and the vocabulary are shared with §S4.7 while the window stays the loaders' own, because theirs carries a name box and a live “this name is taken” line that §S4.7's has no room for; the third message exists because nothing anywhere told the person where their replaced project had gone) and M-INSTRUMENT-BUSY (new, 2026-09-02, #159 — Tools ▸ Read single patches now reads a CR30 with ChromIQ's own driver, which is the first time two windows can reach for one instrument; every existing guard answers from process state and cannot see a reader that spawns no process, and the instrument hands its last reading to whoever asks, so the fault it prevents is a plausible wrong colour rather than an error), (the window for a CR30 that stopped answering during a spot session, new in beta 17, was APPROVED by Basti on 2026-10-10 and left this list), (the log line for a CR30 press made before the spot window said Ready, new in the review of beta 17, was APPROVED by Basti on 2026-10-10 and left this list), plus M-SPOT-CLEAR and M-SPOT-UNSAVED (new, 2026-09-03 — Tools ▸ Read single patches could throw a whole measuring session away in silence by two separate routes: Clear had no question and no undo, and Close, the red window button and Escape all discarded the readings without a word. Knut found the first of them by pressing the spacebar, which the Measure tab uses as the reading trigger), plus M-SCAN-REF-SHORT, M-SCAN-REF-DISAGREES, M-SCAN-CLIPPED and M-SCAN-PROFILE-ARCHIVED (new, 2026-09-03 — review 5 of Tools ▸ Build profile with scanner or camera found the app building a profile from data that is not the chart it thinks it is, with every indicator on screen green: a reference file holding a correct SUBSET of the target builds from a sixth of the sheet and scores BETTER on colprof's own self-check than the correct build, an upside-down scan passes every pre-build check, and a scan with two of every five patches clipped to white builds clean and silent. The mechanisms are in the code and can ship ahead of these words; the fourth message says where a rebuilt profile's predecessor went, now that it is archived instead of overwritten), plus M-SCAN-DARK, M-SCAN-FIT-UNSUPPORTED and M-SCAN-SELFCHECK-UNUSABLE (new, 2026-09-04 — beta 8 items B8-01 and B8-03, the two places where the same window tells the user a bad profile is a good one. Every guard in it is scale-invariant and an exposure slip is pure scale, so an under-exposed scan passes all of them in silence and builds a profile 21.7 ΔE out; and colprof's self-check is measured against the rows it was fitted to, so it is smallest exactly when there is least to fit — a one-colour reference scores a perfect 0.007 and a profile whose white point is nan is not checked at all, both ending "Install it as your scanner's input profile"), plus M-SCAN-LOADED and M-SCAN-DIAGNOSTIC (new, 2026-09-03, beta 8 items B8-16 and B8-15 — the same window said nothing at all when a scan was loaded, so a 24-patch photograph loaded under a 288-patch target left an empty log and a live Run button; and it accepted one of ArgyllCMS's own diagnostic images as a scan, which Knut did in his beta.7 log, and then reported a misplacement that was not real about a read that had been fine), plus M-SCAN-ALIGN-NO-BETTER (revised wording only, 2026-09-04, beta 8 item B8-42 — the headline is unchanged and approved; the body used to describe the recogniser alone, and the merged placement button reaches this ending only when the search AND the reshaping have both declined, so it now says both and names “Check alignment”, the one check in the window that can tell a grid one whole patch out from the right answer), plus M-SCAN-CONVERTED and M-SCAN-FIT-TOO-FAR (new, 2026-09-04, beta 8 — the photograph path, revised the same day for B8-42's merged placement button. The window offers “a scan or photo” and Argyll reads TIFF only, so a camera JPEG aligned perfectly on screen and then failed inside scanin; and a sheet that is bowed AND photographed at an angle is read wrongly at its own corners — measured over 48 bow × lens × tilt conditions, each distortion alone costs nothing and two together put 102 patches over 1 ΔE00, which is why the four corners can now be reshaped onto the patches under a bound of three quarters of a patch pitch. Four further messages written for that button on the same day are WITHDRAWN, never having been approved — they are named and accounted for in the awaiting-review section below, and they went with the button itself, which B8-42 merged into Auto align), plus M-SCAN-ALIGN-NOT-SEATED (revised wording, 2026-09-04, beta 8 items B8-02 and B8-42 — Auto align's seventh refusal, and the first one about geometry rather than colour. The quad it is able to return is always a rotated rectangle, so a sheet photographed off square gets a grid that is systematically wrong — and every check it had looks at the chart's COLOURS, which a shear does not disturb because the patches keep their brightness order while sliding onto their neighbours. Measured at 8 degrees of compound tilt: 20 of 23 targets accepted, ten of them more than half a patch out, while the window printed “agrees … to 0.98” beside its own sentence “anything below 0.80 is refused”. Its body is reworded for B8-42 because the placement it refuses may now have come from reshaping the user's own corners rather than from the recogniser, so “it found the chart, but …” would not always be true), plus M-SCAN-SHOT-EMPTY and M-SCAN-TARGET-CHANGED (new, 2026-09-04, beta 8 item B8-32 — two silences in the same window found by the regression sweep: an averaging slot left empty is dropped without a word, so the window shows “Scan 2 of 2” while the build reads one scan and averages nothing; and changing the Target type discards the loaded scan, its placement and every other shot on the page, into a log that is cleared in the same block), plus M-SCAN-WP-DEFAULT (new, 2026-09-05 — the white-point handling a scanner or camera profile is built with moved from “Map chart white to white” to “Scale white to a perfect white surface” (`colprof -u -R`), because the old default clipped every original brighter than the test chart's own white board — 84 % reflectance on the scan it was measured from — irreversibly onto white, at no gain in accuracy. Basti ruled that existing remembered settings adopt the new default rather than being pinned to the old one: “our user base is not very big at the moment so i want the better default”. The RULING is his; this message is the announcement that goes with it, and its wording is new and waits here), plus M-REPORT-CHART-MISMATCH-NO-GREY (new, 2026-09-24, beta 40 challenge B: the strip named “Neutral grey ramp” with 16 steps under a list with no grey row, and on a FROM PROFILE GAMUT chart, whose grey steps are its neutral aims; this closing names no grey lever), plus M-THRESHOLDS-NOT-CERTIFICATION (new, 2026-09-08, #182: the note at the foot of the Report limits window saying that ChromIQ measures against a standard's published values and never certifies anything, and naming the requirements it cannot measure; revised twice after Knut approved section C of 5802027116, and the revision of 2026-09-24 about “–” was accepted by him in 5816616607, but the sentence about where a Custom column starts from (B8-978) has not been put to him, so it still waits here), plus M-SCAN-ALIGN-NOT-FOUND-HEX (new, 2026-09-11 — Auto align cannot find a hexagonal chart and never could: measured on Knut's own CR30 honeycomb against a rectangular chart of the same 648 colours, the honeycomb moves 0.0 px from every starting placement while the rectangle lands 0.6 px from the true corners, and only the SEARCH stage declines, with zero candidates, because it borrows scanin's recogniser and that hunts the straight horizontal patch edges a grid of rectangles has. The refusal was already safe; what was wrong is that it told the user to drag the corners roughly round the chart and press again, which narrows a search that will find nothing however narrow it is. Behaviour unchanged, wording new, so it waits here), plus M-SCAN-ALIGN-PLACED-UNCHECKED and M-SCAN-ALIGN-PLACED-NOT-SEATED (new, 2026-09-11, #182 — Knut ruled that Auto align, when it cannot place the grid well enough to trust, must “place its best attempt and tell user to check it” rather than leave the corners alone. Two of the nine endings had a candidate and discarded it, so the user never saw what ChromIQ had found; both now apply it with the one-press undo armed, and these are what is said instead of the shared “Auto align left your corners exactly where they are”. The checks themselves are unchanged), plus M-IMPORT-DONE-PROFILING (new, 2026-09-15 — the Measure tab's IMPORT module now files into a profiling run as well as a verification, asked for by a tester and ruled on by Sebastian; the approved import-done window speaks only of verifications and of a dated folder a profiling run does not have, so its twin is new wording and waits here), plus M-IMPORT-DEVICE-FROM-CHART (new, 2026-09-12 — i1Profiler's measure tool reads a chart it did not generate, so it has no colour space to express device values in and exports none at all. ChromIQ refused such a file with "No device RGB columns", about a user's complete measurement of her own verification chart, taken on an i1iO. The pairing never needed those values: the chart printed a NAME beside every patch, the export carries those names, and the chart knows what was printed at each of them, so the chart supplies the device values exactly as it does for a measurement made here. What it cannot then do is check the file against the chart, because that check compares device values, so this window says so and leaves the judgement with the person who printed the sheet) , plus M-VERIFY-UNCHECKED-METRICS (new, 2026-09-22, #182: what the report does with a metric the chart cannot answer; its last paragraph was reworded for K31 after Knut approved section C of 5802027116, and not in the words that post proposed, so the revision waits here), plus M-REPORT-DELETE-FAILED and M-REPORT-NOT-WRITABLE (new, 2026-09-23, challenge C of beta 39, both revised by re-challenge R2 after Knut had been shown them in 5802027116, for a remedy that names the right folder and a plural that follows the folders; the revisions wait here) plus M-RUN-DELETE-REPORTS-LOCKED (new, 2026-09-23, re-challenge R2 of beta 39: a run delete refused because the reports naming the later runs cannot be renumbered said it had tried to remove the reports folder, and had no headline; the behaviour is unchanged, the wording is ours and waits here) plus M-REPORT-UPDATE-NOTHING-LEFT (new, 2026-09-23, re-challenge R1 of beta 39: “Update without them” on a report whose every measurement was gone wrote a report covering nothing under its old verdict and scope; the press is now refused, the wording is ours and waits here) (the two K49 notes on the paper row and the two solid rows, which say that they compare a measurement with its profile's own description while the cube-corner table keeps the ideal values, were APPROVED by Knut in 5845588201 and left this list) (the four K37 notes about the paper white and the strip corners were APPROVED by Knut in 5824834975 once "sheet" was reworded, and left this list), (the Report Scope line saying that an earlier version worked a report out was APPROVED by Knut in 5831246553 once its last sentence, which named the Update button, was reworded, K39-1, and left this list) (the variant of the unchanged question and the red line after "New report…", K39-2 and K39-3, were APPROVED by Knut in 5832385126 and left this list) (the note for a date whose measurement is no longer on disk, B8-1500, was APPROVED by Knut in 5858874320 and left this list) (the line for a calibration found while the ChromIQ layout engine lays the chart out, B8-1655, was APPROVED by Knut in 5865088296 and left this list) (the fourteen K59 texts of option C and of "change" for "drift", about a sheet printed raw and the opening of a report of sheets printed both ways, were APPROVED by Knut in 5850164956 and left this list) plus M-CM-K-CHART-THROUGH, M-CM-RAW-UNCALIBRATED, M-CAL-APPLIED-TWICE and M-CAL-CALIBRATED-TWICE (new, 2026-10-02, #182 5959070209: Sebastian approved the behaviour, a warning before the printer calibration is applied twice to a profile from an older layout-engine -K chart, and verification prints of a -K run that carry the calibration; the wording is ours and waits here) plus M-PATCH-COLOUR-RANGE (new, 2026-10-02, #182 k10: the colour-range rule for yellow outlines was approved by Knut in 5961180259 and by Sebastian; its post gave one line of card text, and the lines the cards now carry, the range on its own line, a count of three, the confirmed patches it learned from, are ours; revised for beta 9, Knut 5979886227: no "spaced", and two lines for a patch confirmed by similar patches; and, for Knut 5980576263, a "read it again" line on a red card and a "no need to read it again" line on a yellow one, which Knut approved in 5982038838 together with the two similar-patches lines; and, for beta 10, Knut 5982206917, the lines that name the failed test and its numbers on a red card in a learned range; and, for Knut 5982600086, the lines saying whether the reading landed where its confirmed patches' readings did) (the six lines of a verification card whose profile was made after the sheet was printed, Knut's own sentence, were APPROVED by Knut in 5983480953 and left this list; the four lines beside them are ours and wait) (the ten lines of a verification card that speak of the profile's accuracy instead of what the printer cannot reach, #203 5982702169, were APPROVED by Knut in 5982788316 and left this list) (the hover-card line saying a verification patch's expected colour is the profile's prediction was APPROVED by Knut in 5965408335 and left this list) (the two "Continue to next / Jump to unread" questions of 5958921500 Q2 were APPROVED by Knut in 5962907586 and left this list) plus M-STRIP-READ-TWICE, M-CR-STRIPS, M-CR-START-OVER and M-CR-PRECONDITIONING (new, 2026-10-03, #182: Knut approved the Check & Refine redesign and the live "strip read twice" check on the pictures in 5963737221, in 5963903650; the words the pictures and the question showed are kept verbatim, the few they did not show are ours, and none of it has had his word on the wording yet; beta 9 removed M-CR-STRIPS' two "Not offered again" lines, Knut 5980560281) plus M-CAL-TABLE-REPAIRED and M-CAL-TABLE-DAMAGED (new, 2026-10-03, beta 7: a measurement whose copy of the printer calibration an earlier engine wrote damaged is repaired in place from its chart before any ArgyllCMS tool loads it, the original kept in old/, as Basti ruled; the first says so, the second replaces the build-failed text that blamed the user when no chart could be found to repair from; the wording is ours and waits here) plus M-CHART-PATTERN-REFUSED, M-CHART-LOCATIONS-UNREADABLE, M-CHART-LEGACY-STOCK and M-CHART-LEGACY-ENDED (new, 2026-10-03, forum report and Knut's ruling #182 5965589190: the strip pattern "0-9" made a 14-strip chart neither ArgyllCMS chartread nor ChromIQ's engine could read, because ChromIQ printed "10" where Argyll's pattern stops at 9; ChromIQ now labels every new chart exactly as ArgyllCMS does and refuses a pattern the readers could not read back, the Measure tab says so before starting any reader on a sheet no reader can measure, and a sheet printed with ChromIQ's old labels is read by ChromIQ's engine as printed while a user of ArgyllCMS chartread is told plainly that chartread cannot read it; the wording is ours and waits here) plus M-PROFILE-VERIFY (revised, 2026-10-03, #182: Knut ruled in 5964384250 Q1 that a rebuild archives the profile only, so “Build here anyway” no longer moves the dated verifications, and in 5964076758 Q4 that “Each was printed through the profile” must be reworded, because it is untrue for raw and FROM PROFILE GAMUT sheets) and M-VERIFY-EARLIER-PROFILE, M-VERIFY-EARLIER-PROFILE-KEEP-CHART, M-VERIFY-EARLIER-PROFILE-NO-CHART, M-VERIFY-CHART-EARLIER-PROFILE and M-VERIFY-EARLIER-ARCHIVED-HERE (new, 2026-10-03, #182 §6f: the one window Knut asked for when Verification is chosen after the profile was replaced, 5964384250 and 5965626117; the behaviour is his, the wording is ours) plus M-CAL-REQUESTED, M-CAL-REQUESTED-DONE and M-CAL-REQUESTED-FAILED (new, 2026-10-03, #182: Knut 5965478577 and 5965735823 and Basti 5965500670 approved calibrating between strips or patches with K or an optional Calibrate button, on ChromIQ's engine only; the placement window keeps the session on Cancel, the short completion window says to carry on, and a failure locks reading until a calibration succeeds; the wording is ours and waits here) plus M-PATCHSET-CAL-INKS and M-VIEW-RGB-ONLY (new, 2026-10-03, beta 7, the CMYK/CR30 forum report: the first refuses a preset's or loaded patch set the printer calibration does not fit and names “Edit patch recipe (override preset)”, the second is the one line every RGB-only view shows for a CMYK or multi-ink measurement; Basti approved the behaviour, the wording is ours and waits here) (the no-instrument window for when nothing is connected at all, new in beta 8, was APPROVED by Knut in 5979780372, "all are ok", and left this list) plus M-PATCH-CORRECTED-VARIANTS (new, 2026-10-04, beta 11: the two lines of the green outline Knut's approved example did not cover; the green outline itself and its words were approved by Knut in 5984277558), plus M-PATCH-NEIGHBOUR-VARIANTS and M-MEASURED-SUSPECTS (new, 2026-10-04, beta 11, #182: Knut approved the neighbour check in 5983470377, answer 5, and its threshold box in 5983725218; the rule is confirmed in 10.9, the card lines and the closing window's summary of suspected misreads are ours and wait here), plus M-PATCH-UNSETTLED (new, 2026-10-07, beta 12, #182: Knut ruled in 6045500910 that a re-read past the limit that agrees with no earlier reading stays red and its card says so, 10.10a; the words are ours and wait here), plus M-REPORT-THROUGH-PROFILE (new, 2026-10-07, beta 12, #182: Knut ruled in 6045500910 that a verification printed through its profile is judged against its source colours on in-gamut patches and against the profile's own prediction; the words are ours and wait here), plus M-PREVIEW-AS-PRINTED (new, 2026-10-07, beta 12, #182: Knut ruled in 6045500910 answer 4 that the chart preview looks as the paper will look printed, and Basti in 6045468325 asked for a small indicator saying what the preview shows; the words are ours and wait here; extended 2026-10-08 for Basti's switch between "as on paper" and "device values", lines 10 to 16), (the Simulate paper white button inside the indicator, beta 14, was APPROVED by Sebastian on 2026-10-08 and left this list), plus M-CHART-SLOW-NO-PROFILE (new, 2026-10-08, beta 12: the "taking longer than usual" window of a chart built without a pre-conditioning profile no longer speaks of pre-conditioning profiles and refinement charts), plus M-PRINT-JOB-NOT-AS-SENT (new, 2026-10-08, beta 15: the job read back from the printing system is not what ChromIQ sent; Sebastian did not approve it as worded, its opening sentence is wrong when the paper profile is the only problem), M-PRINT-JOB-UNTAGGED (new, 2026-10-08, beta 15: that case's own window) and M-PRINT-PAPER-PROFILE-UNKNOWN (new, 2026-10-08, beta 15: the direct route does not know which paper profile the driver of this model chooses, so it asks instead of guessing), plus M-PRINT-VERIFY-ROUTE and M-PRINT-JOB-TAGGED-INTENT (new, 2026-10-10, Knut 6095262115: the Print Chart tab says nothing about what a verification print needs, and on a printer without paper profiles the status line did not say that the chart went with the job's own profile; measured on capture queues set up like Knut's HP; shown nowhere until approved), (the note and marks of the Print Chart tab's quality row, beta 16, were APPROVED by Sebastian on 2026-10-09 and left this list), (the confirmation window's colour rows and the status line after sending, beta 15, were APPROVED by Sebastian on 2026-10-08 and left this list) — all defined in the awaiting-review section below.
> **Withdrawn, never approved:** the patch-set sibling of the message above was removed on 2026-08-26 without reaching the catalogue. Ticking “Edit patch recipe (override preset)” already opens a window saying the loaded patches will be replaced, and that box is shown for a patch set the user loaded themselves, not only for a built-in preset — so a second window at Generate time would have interrupted a decision the user had already made and acknowledged. Knut, 4.1.3-beta.17: *“there is already a message when clicking the ‘Edit patch recipe’ warning of consequences … that warning should be sufficient for a user.”* Checked against the existing text before removal.

> Both were approved by Knut on 2026-08-04, but one step in each instructed *"(with colour management on)"* — a setting ChromIQ deliberately locks **off** on every print path, so the approved text told the user to do something the app prevents (established in `verification_printing_and_target.md` §1, and A0.1 of its plan). With feature A the instruction has a real control to name — the Print Chart tab's **Colour** row — so that one step is revised and the revision waits in §M-PROPOSED. Every other message in §M remains approved as before: the last, **M-BUILD-ELSEWHERE**, was accepted on 2026-08-04 — *"Message M-BUILD-ELSEWHERE accepted"* — and M-CHART-CORRUPT, M-REPLACE-UNCOUNTABLE and M-PREVIEW-PAUSED the day before. A new message goes to §M-PROPOSED first, and `tests/test_message_catalogue.py` fails if one is added to the code without it.

> **Status:** specification, agreed on [issue #130](https://github.com/itsab1989/ChromIQ/issues/130).
> Written by the ChromIQ assistant, reviewed and directed by Knut (soul-traveller)
> and Sebastian, 2026-08-02/03.
>
> This is the first chapter of what is meant to become ChromIQ's design
> documentation. It covers **the life of a measurement** — how one ends, what is
> written, what is archived, and every warning shown along the way. Later
> chapters can cover the other areas of the app in the same shape: the tables
> here are the contract, and §T says how each row is proved.

> **These specifications are binding.** Knut, 2026-08-06: *"These must always be
> consulted on changing code so that behaviour defined is not violated. And if
> faults are found that do not match with the specification [it] must be
> reviewed and approved."* So: read the relevant document before changing code
> in the area it covers, and if you find behaviour that contradicts it, **report
> it and get the change approved** rather than quietly correcting one side to
> match the other.

## The companion specifications

This chapter covers the life of a measurement. Three further specifications
came out of the same issue and are part of the same contract; Knut asked
(2026-08-06) that each posted analysis and table set be written down as a
specification rather than left in the thread, *"strictly described from what has
been agreed, including fixes that has risen from tests and bugfixes."*

| Document | What it specifies | Thread post |
|---|---|---|
| [`per_run_description.md`](per_run_description.md) | the four description / notes fields: which file a keystroke reaches, what Restore Used Chart puts back, `-D`, and the run lifecycle. §9b and §9c record what the beta.148 and beta.150–157 rounds found | [5190506691](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5190506691) |
| [`measurement_exit_strategy.md`](measurement_exit_strategy.md) | every window that can end a measurement, for stock chartread and the ChromIQ engine, in strip and patch-by-patch mode: the key each button sends, what it does, and whether it follows §1/§1a's single exit | [5206885923](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5206885923) |
| [`per_target_settings.md`](per_target_settings.md) | which settings belong to a target rather than to the installation, and exactly when they are loaded and written | [5206901110](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5206901110) |

## How to read this

- **§0–§3** are the model: what actually happens to a `.ti3`, and how ChromIQ
  can tell one state from another.
- **§4–§6** are the three places a matching set of files can be broken.
- **§7** maps every event ChromIQ detects to the exact line of ArgyllCMS or of
  ChromIQ's own reader that emits it.
- **§M** is the complete message catalogue: every window, with its ID and text.
- **§S** is the sequence: what happens in what order, one window at a time.
- **§T** is the test plan. Nothing here is implemented until its row is green.

**The rule the whole document serves:** a run holds one matching set — chart,
measurement, profile, and the verification measurements of that profile. Every
warning exists because some action would break that set, and every one of them
archives rather than deletes.

## 0. The one fact everything follows from

**ArgyllCMS `chartread` keeps its readings in memory and writes the `.ti3` only when it exits cleanly.** Kill it and the readings are gone — there is no partial file on disk to recover.

| | What is sent | What chartread does | `.ti3` |
|---|---|---|---|
| `d` then `y` | keystrokes | writes the file, exits 0 | **saved** |
| Stop (before beta.123) | SIGKILL | dies where it stands | **lost** |

Your own log carries both, minutes apart: every `d` ends `finished with code 0`, every Stop ends `finished with code -9`.

**The ChromIQ engine is different.** `chromiq_chartread.c` calls `cq_write_ti3_atomic()` *before* it gives up — a ChromIQ extension marked *"never lose readings"*. Stock chartread has no equivalent: `chartread.c:1654` treats `q` at a misread prompt as give-up and `return -1`, writing nothing.

---

## 1. Every way a measurement can end

| # | Route | Engine | Mode | What is sent today | Message today | `.ti3` today | Proposed |
|---|---|---|---|---|---|---|---|
| 1 | **Stop** | ChromIQ | strip | two `q` | "Keep what you have measured so far?" | saved | unchanged |
| 2 | **Stop** | ChromIQ | patch | two `q` | same | saved | unchanged |
| 3 | **Stop** | stock | strip | `d`→`y`, or `r`→`d`→`y` | same | saved | unchanged |
| 4 | **Stop** | stock | patch | **nothing — killed** | **none** | **LOST** | fixed in beta.123 (§6) |
| 5 | **Stop** | any | nothing read | kill | none | nothing to lose | say "nothing was measured, so nothing was saved" **on screen** |
| 6 | **`d`** | both | strip | `d` → chartread asks | "Patches Still Unread" | saved | replace with the one window (§2) |
| 7 | **`d`** | both | patch | as above | as above | saved | replace with the one window (§2) |
| 8 | **`Esc`/`q`** | both | strip | passthrough | none | **discarded silently** | the one window |
| 9 | **`Esc` `Esc`** | both | patch | passthrough | none | **discarded silently** | the one window |
| 10 | **any failure window offering a save** | both | any | see §1a | its own text | saved | all use the same wording |
| 11 | **any failure window offering only "Give Up"** | both | any | `Esc` | *"stop the measurement without saving"* | **discarded** | must offer to save — see §1a |
| 12 | **`Esc`** (single patch) | spotread | single | passthrough | inline | n/a — spotread appends per patch | §9 |
| 13 | Chart finished | any | any | — | "All patches read" | saved | unchanged |
| 14 | Instrument init fails | any | any | — | **none** — exits **0** | none | fixed in beta.123 (§6) |

### 1a. Every window that can end a measurement

You asked me to generalise rows 10 and 11 to all failure windows. Doing that turned up **five more doors that discard without offering to save** — the same fault as rows 8 and 9, wearing a button instead of a key:

| Window | Buttons today | Offers to save? |
|---|---|---|
| Patch Read Failed / Strip Read Failed | Retry · **Save Partial & Quit** | ✅ |
| Strip Read Interrupted | … · **Save Partial** | ✅ |
| Patches Still Unread | **Save Partial** · Keep Measuring | ✅ |
| Strip may be misaligned | Use Anyway · Re-measure · Retry · **Give Up** / **Stop** | ❌ |
| Wrong Strip Read | Use Anyway · Retry · **Give Up** | ❌ |
| Unexpected Colour Response | Use Anyway · Retry · Resume · **Give Up** | ❌ |
| Instrument Error | Retry · **Give Up** | ❌ |
| Confirm Abort | **Yes — Abort** · No — Keep Measuring | ❌ |

"Give Up" sends `Esc`, which for stock chartread means quit-without-saving. The windows say so honestly — but the user is being asked to choose between retrying and losing the session, when saving was available all along.

**Proposal: every one of these gets the same three choices as §2**, so "Give Up" stops meaning "throw away the last twenty minutes".

**BUILT — beta.140/141.** Every window in this table offers Save · Discard · Keep
Measuring. Two things had to be settled while building it, and both are rules
now rather than accidents:

- **A window that is already open is never covered by another one.** Every
  during-a-read window signs into one register, so "is one already open?" is a
  question the app can answer — Knut: *"I can also click the instrument button
  more times, and this window comes on top of previous windows, all at the same
  time. This should not be allowed."* Same rule as the instrument-mismatch
  window in beta.136, now applied to all of them.
- **One failure is one window, however many times it is reported.** See §7c.

---

## 1b. The exact sequence each ending sends

Knut, beta.133: *"The save partial and quit and stop buttons worked before. Even
the q and d keys worked before. What is different now? … Update the … document
with the sequences to use to exit windows and measurement session."*

Here is every one, because they are not the same and the difference is not
visible on screen. **Two things decide the sequence: which engine is reading,
and whether a prompt is open.**

### Save Partial & Quit

| Engine | Mode | Where it starts | What ChromIQ sends | What ends it |
|---|---|---|---|---|
| ChromIQ | strip | any | `{"cmd":"quit"}` → the helper answers with the **event** `{"event":"strip_interrupted"}` (and prints the give-up prompt) → `{"cmd":"quit"}` | the helper writes the `.ti3` (`cq_write_ti3_atomic`) and exits |
| ChromIQ | patch | any | the same two commands; the printed line reads *"**Spot** read stopped at user request!"* | as above |
| stock | strip | a failure prompt | `r` → *"Ready to read strip pass X"* → `d` → *"Are you sure [y/n]"* → `y` | chartread writes the `.ti3` and exits |
| stock | patch | a failure prompt | `r` → *"Ready to read patch 'N' at 'LOC'"* → `d` → *"Done ? — At least one unread patch (…) Are you sure [y/n]"* → `y` | as above |
| stock | either | the menu | `d` → *"Are you sure [y/n]"* → `y` | as above |

**Why the first key differs.** A failure prompt reads **any key that is not Esc
or `q` as "retry"** (chartread.c:1652-1654), so a `d` sent there is swallowed
and the reader simply carries on. The retry key has to be spent first, and only
then does `d` reach the menu that raises the saving question.

**In engine mode the second command hangs off the EVENT, not the printed line.**
Prose never reaches the stock parser there — it goes straight to the log — so a
chain waiting for *"Strip read stopped at user request"* waits for ever. Knut,
beta.135, pressing Stop → "Save and stop": *"The session still did not exit."*
The test that covered it called the stock parser directly, which the app never
does in engine mode, so it proved the chain against a path that does not run.

### Skipping the unit that just failed

Two steps, always: the retry prompt has to be answered before anything can
move, because it reads any key but Esc/`q` as *retry*.

| Engine | Mode | What Skip sends | Where the move is flushed |
|---|---|---|---|
| ChromIQ | strip | `{"cmd":"ok"}` → then `f` | on the `strip_ready` event |
| ChromIQ | patch | `{"cmd":"retry"}` → then `f` | on the `spot_ready` event |
| stock | strip | `\r` → then `f` | on *"Ready to read strip pass X"* |
| stock | patch | `\r` → then `f` | on *"Ready to read patch 'N' at 'LOC'"* — **added in beta.137**; the flush hung off the strip line alone, so this was the one combination of the four where Skip acknowledged the prompt and then never moved (Knut, beta.136) |

### Moving about while reading

| Key | stock chartread | ChromIQ engine |
|---|---|---|
| `f` / `b` | one unit forward / back | `{"cmd":"forward"}` / `{"cmd":"back"}` |
| `F` / `B` | ten units (chartread.c:2319-2327) | the helper has no ten-step command, so **ten single steps** are sent |
| `n` | next unread | `{"cmd":"next_unread"}` |
| `g` | go to a patch | `{"cmd":"goto", …}` |
| ← / → | `b` / `f` — **not** the raw arrow sequence | `{"cmd":"back"}` / `{"cmd":"forward"}` |

An arrow key is three characters and the first one is Escape. chartread reads
**one character at a time**, and Escape there is *give up without saving*
(chartread.c:1611, :1654, :1857) — so sending `\x1b[D` for a Left arrow
abandoned the session, and on the engine it matched no command and did nothing.
Both arrows send the keys chartread prints in its own menu (beta.139).

*(The stray semicolon in chartread's own help line — `'B; to move back 10` — is
Argyll's, at chartread.c:2122.)*

### After the ending window, nothing else asks

"Save and stop" is an answer, not a question. Once it has been given, the
session ends and **no further window may open about the same ending** — the old
"Strip Read Interrupted" window appearing behind it was pre-model and is gone
(Knut, beta.137: *"I have already decided to save and stop, so this is what must
happen"*). The helper both prints and reports the give-up prompt; the printed
copy now only completes the chain, never raises a window.

### What the user's own keys do

| Key | ChromIQ engine | stock chartread |
|---|---|---|
| `d` at the menu | asks *"Are you sure"*, then writes | the same |
| `d` at a failure prompt | read as "retry" | read as "retry" |
| space, `r` at a failure or warning prompt | `{"cmd":"retry"}` | *any key that is not Return/Esc/`q`* means retry (chartread.c:1855) |
| `q` / Esc at a failure prompt | the helper **writes the `.ti3` first**, then gives up | **gives up without writing** — `chartread.c:1654` returns −1 and the readings die with the process |
| Stop | §2's window: *Save and stop* runs the sequence above; *Discard and stop* ends the session and keeps nothing | the same |
| `K` / `k`, and the physical K key under a Cyrillic layout (#182, Knut 5965478577 and 5965735823, Basti 5965500670; ⏳ awaiting confirmation as rows) | `{"cmd":"calibrate"}`: a new calibration before the next strip or patch, **M-CAL-REQUESTED**; held and sent at the next prompt when pressed during a swipe or at a question; never for the CR30 or a whole-sheet reader | **nothing**: a log line, nothing forwarded, in both modes. Stock patch mode's own `k` used to reach chartread, and any non-ok answer there, a Cancel included, ended the program without writing the `.ti3` (`chartread.c` 2305) |

That last row is the whole reason ChromIQ never sends `q` on stock chartread,
and why the two engines cannot share one sequence.

### After a read: where the reader goes next

Only on ChromIQ's engine, in strip mode and patch by patch. Stock chartread
keeps its own behaviour (Knut, #182 5958921500, Q3: *"No, the stock chartread
only follows its own behaviour as designed in ArgyllCMS provided code."*), and
the whole-sheet modes report no per-strip read.

**What the engine does by itself.** After a good strip read it searches for
the next unread strip (`incflag = 2`), and "unread" there means only that the
strip's FIRST patch has no reading; on a chart with nothing unread the search
comes back to the strip just read. After a good patch read it steps to the
next patch in order and wraps at the end (`incflag = 1`).

**The beta-4 rule, nothing unread.** Knut, #182 5956210745: *"When measurement
of a strip is completed, the focus should jump to the next strip after the one
I completed … This should be default behaviour, unless warning messages pop up
where I am asked if I want to retry."* ChromIQ sends the goto. On the last
strip it stays: Knut, 5958921500, Q1: *"Stay at the last strip, as at this
point the measurement completed message will arrive. If user chooses to re-read
more patches, then the user can choose where to start and if he presses f key,
which then would wrap round to A."*

**Strips or patches still unread.** Knut, 5958921500, Q2:

> *"If strips still unread, then re-reading a read strip should not jump to
> next unread, but instead ask with a popup that appears only one time per
> started measurement (resume / re-measurement), then, the behaviour chosen by
> the user is continued until the measurement is stopped (exited) … This window
> function must look at patches not yet measured, not strips, as patch-by-patch
> measurements may have been performed, and this feature should work for both
> patch-by-patch mode and strip mode, and when resume measurement is started,
> by any instrument and on any chart, and any run or verification run
> measurement. This function only applies to ChromIQ measurement engine, not
> ArgyllCMS stock chartread."*

#### Confirmed behaviour — our choices inside Knut's rule

**Confirmed by:** Knut, 2026-10-03, #182 [5962907586](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5962907586) ("All questions in post 5961673878 are accepted": closest = forward with wrap, asks on a fresh session too, last strip stays, X/Esc answers nothing, Continue to next is the default).

**How ChromIQ carries his rule out.** After each read ChromIQ compares two places: **N**, the strip after the one
just read (none on the last strip) or the patch after it (wrapping), and **U**,
the first strip after it holding at least one unread patch, or the first unread
patch after it, both going forward and wrapping. If N and U are the same place
the reader goes there and nobody is asked. If they differ, the window
M-UNREAD-NEXT-OR-JUMP-STRIP / -PATCH asks, and the answer is kept until the
measurement ends: **Continue to next** goes to N (on the last strip it stays on
that strip), **Jump to unread** goes to U. A failure, pace or wrong-strip
window that is open holds the decision until it closes, and a "read it again"
answer from that window cancels it. The user's own f, b, n, a click on the
preview, or a swipe already started cancel that read's move too, and the
stored answer stays. (`MeasureManager._after_a_read`.)

* **"Closest" is "the next one going forward, wrapping round"**, not the
  nearest in either direction. That is the order the reader itself moves in,
  and the one f and n use.
* **It asks also on a fresh session** whenever N and U differ, for example when
  strips were read out of order and the next one is already read, not only on
  a resume or a re-measurement.
* **Continue to next on the last strip stays on that strip** (his Q1), even
  though patches elsewhere are unread; the engine has already jumped to an
  unread strip, so ChromIQ sends it back.
* **Closing the window with the X or Escape answers nothing.** The engine's own
  move stands and the question comes back at the next read where N and U
  differ. It never asks twice for the same read.
* **The two modes behave differently when nobody has answered**, because the
  engines do: in strip mode the engine has already jumped to an unread strip,
  in patch mode it has already stepped to the next patch. Continue to next is
  the default button.
* **The window plays the "Instrument error" sound** as it opens. Knut,
  [5963044182](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963044182):
  *"When the window appears it is supposed to get the attention of the user,
  so the "Instrument error" sound can be also used as a "attention" sound.
  Use this sound."*
* **It asks on any read, first reads included.** Knut, 5963044182: *"for all
  reads is ok, not only re-reads."*

#### ⏳ Awaiting confirmation — points put to Knut in 5962715315

**Confirmed by:** *nobody yet.*

* **Unread is counted per patch, from the file the engine resumes from**
  (`<chart>.ti3`, which a resumed verification is copied to first), and the
  fill-up squares that complete the last strip are never counted as unread.
* **The progress counts each design patch once** (fixed 2026-10-03 at Knut's
  request, #182 5963044182: *"Re-reads shall not increase the Progress"*). It
  used to start a resumed session from the file's row count and add every
  patch read, so a re-read counted twice and the header said 100 % beside
  "21 patches on this chart have no reading yet" (review AR). The file's
  patches are now kept by location and joined with the session's, fill-up
  squares left out (`TabMeasure._progress_measured`).

### What changed, and when

- **beta.139** gave the retry key a command. Every failure and warning window
  spells chartread's *"any other key to retry"* as a **space**; stock chartread
  takes it, but the engine's key→command table had no entry for it, so Retry
  sent nothing and the helper sat at its prompt for ever — Knut, beta.138:
  *"The instrument now stopped responding (no button press reacting and no
  sound), so I cannot measure strips anymore."* It also gave the arrow keys the
  row above, and closed the last door on the duplicate ending window: the
  give-up prompt arrives both as an event and as a printed line, beta.138 
  silenced only the printed one, so whichever arrived **second** still opened a
  window. One per-session flag — *this ending has been answered* — is now set by
  whichever arrives first and checked by both.
- **beta.130** taught the stock path that a failed *strip* read leaves a retry
  prompt open. Before that, Save Partial sent `d` straight into that prompt,
  which ate it — Knut's beta.128 report.
- **beta.138** removed the second window after "Save and stop", let the
  wrong-dial warning be raised again in engine mode (its one-per-prompt flag was
  cleared only on chartread's printed menu line, which the engine never emits),
  and fixed the completion window for a chart with **one** patch left: whether
  the chart was already complete was read from the strip flags, and in
  patch-by-patch a strip whose last patch is unread still reports itself read.
- **beta.137** finished the same story in the two places it still ran out: the
  helper answers the first quit with an **event** in strip mode and with a
  **printed line** in patch-by-patch, and only the event was handled — so
  reading patch by patch, Save Partial & Quit sent one `quit`, which is Esc, and
  the session ended without writing. Both are handled now. It also stopped the
  wrong-dial window opening twice (chartread prints the fault and its reason on
  two lines, and both matched), and gave Skip its missing flush above.
- **beta.136** made the engine's own ending work at all: its give-up prompt
  arrives as an event, and nothing was listening for it, so the second `quit`
  was never sent. It also gave `F` / `B` a meaning in engine mode, and made the
  wrong-dial-position message raise a window in **both** engines and **both**
  modes — chartread prints it as *"Spot read failed due to the sensor being in
  the wrong position"* (chartread.c:1644) even in strip mode, with no
  parenthesised reason, so no other pattern saw it.
- **beta.134** does the same for **patch-by-patch**: its menu line is *"Ready to
  read patch 'N' at 'LOC'"*, which the chain did not recognise, so it walked
  back to the menu and then waited for a line that never came. And the ChromIQ
  engine's patch mode never matched *"Spot read stopped at user request"* at
  all, so its second `quit` was never sent — that one had never worked.

---

## 2. The proposed unified ending

**One window, one set of words, every route** — Stop, `d`, `Esc`/`q`, and every failure window in §1a:

> **Keep what you have measured so far?**
>
> You have read **{n} patches** in this session. They are not in your measurement file yet — ChromIQ can write them now, or end the session without them.
>
> **What each button does:**
> • **Save and stop** — writes what you have read so far to this run's measurement file and ends the session. You can carry on later with "Refine / resume existing measurement (-r)", reading only the strips or patches that are still missing.
> • **Discard and stop** — ends the session and keeps nothing from it. *(added only when a measurement was already there: "Your previous measurement of {n} patches is put back exactly as it was.")*
> • **Keep measuring** — closes this window and carries on where you were.

**On the first sentence.** You were right that the old wording fought itself — *"stopping now would throw them away"* immediately before a button that saves them reads as a threat, and an alarming one. It now states the position plainly and lets the buttons offer the way out.

**On the third sentence.** It assumed a previous measurement existed. It is now added only when one did, and says what will happen to it rather than merely that it is "untouched".

### 2a. Protecting the measurement that was already there

Your assumption is the right design, and it is only partly true today: ChromIQ archives a measurement to `old/` when *replacing* one, and archives an empty `.ti3` after a session — but a session that starts, reads nothing and dies has no guard of its own.

Proposed, and it makes §3 possible:

1. **At the start of every measurement**, if a `.ti3` exists, copy it to `old/<date_time>/` — `runs/runN/old/` for Profiling, `runs/runN/verifications/<date>/old/` for Verification — and record its reading count.
2. **At the end**, compare (§3).
3. **Put it back** when the session ended without saving, when the new file is empty, or when a resume ended with *fewer* readings than it started with.
4. **Never delete the archived copy.** It costs a few kB and it is the only insurance against a bad ending.

---

## 3. The `.ti3` reading-count check

**Where the counts come from.** A CGATS file states `NUMBER_OF_SETS` and then lists that many rows between `BEGIN_DATA` and `END_DATA`. `workflow/ti3_analysis.py` already parses this, so nothing new is needed:

| | Where | Meaning |
|---|---|---|
| **A** | `.ti2` `NUMBER_OF_SETS` | how many patches the chart HAS |
| **B** | `.ti3` `NUMBER_OF_SETS` | how many the file CLAIMS |
| **C** | rows between `BEGIN_DATA`/`END_DATA` | how many it actually HOLDS |
| **C₀** | C, measured **before** the session starts | the baseline |

**You are right, and my "not possible" was wrong.** With C₀ recorded at the start, `C − C₀` is exactly how many patches this session added — so the session's own result is measurable after all. I had only considered the file at the end.

### 3a. Every state a `.ti3` can be in

| State | B | C | Reading | Action | Message when Start Measurement is pressed |
|---|---|---|---|---|---|
| No `.ti3` at all | — | — | nothing measured yet | normal for a fresh run; C₀ = 0 | none |
| Header only, **no `BEGIN_DATA`/`END_DATA`** | any | — | **no measurements** — treat as empty | delete, restore the archived copy, say so | **M-REPLACE-UNCOUNTABLE** ✅ |
| Empty (`C = 0`), or `NUMBER_OF_SETS` absent or 0 | 0 | 0 | nothing was saved | delete, restore, say so | **M-REPLACE-UNCOUNTABLE** ✅ |
| `B ≠ C` | ✓ | ✓ | **corrupt or truncated** | never offer for resume; keep the file, restore the archived copy, explain | **M-TI3-MISMATCH** (with its `{extra}` sentence) |
| Partial (`0 < C < A`) | ✓ | ✓ | expected after a partial session | offer resume, name the count | **M-REPLACE-PARTIAL** |
| Complete (`C = A`) | ✓ | ✓ | fully measured | §6 warning before re-measuring | **M-REPLACE-COMPLETE** |
| `C > A` | ✓ | ✓ | **does not belong to this chart** | refuse, explain | **M-TI3-MISMATCH** |

✅ = approved by Knut, 2026-08-04 — full text in **§M**, with the rest of the approved catalogue. 🆕 = **PROPOSED**, awaiting review — full text in **§M-PROPOSED**. Every message not marked here was approved earlier.

**Who answers a file with nothing readable in it — settled 2026-08-04.** Two rules met on the same file. Beta.110: a session that measured nothing archives what it left behind, *"right after measurement session was exited/stopped/completed"*. That had been extended to files merely **found when the Measure tab opens**, which archived them before Start Measurement could mention them — and §3a's two rows above say Start is exactly where they are answered.

Knut's ruling: **"leave as is, use §3a."** So the archive happens at the end of a session, never on tab-open, and a header-only or empty `.ti3` already on disk is met by **M-REPLACE-UNCOUNTABLE** when Start Measurement is pressed. That message is also why the older complaint does not return: it never claims a measurement exists — it says ChromIQ cannot tell how many readings the file contains.

**Why M-REPLACE-UNCOUNTABLE exists.** The first three rows all describe a file with nothing readable in it, and the model gave them no message of their own — so they fell through to M-REPLACE-PARTIAL, which states a fraction and produced **"0 of the chart's ? patches have been read"**. That reads as a fault in ChromIQ rather than a fact about the file, and it points at Refine / resume, which cannot work when there is nothing to resume from.

**Removed 2026-08-04: the "no `.ti2` beside it" row, and its message M-REPLACE-NO-CHART.** Knut asked whether that condition can arise at all: *"Can a chart read at all be initiated if a ti2 file does not exist? I thought it could not. Thus the Start Measurement button should not be available at all."*

He was right about what *should* happen, and — measured, not assumed — wrong about what *did*: **Start Measurement was offered without a `.ti2`.** The Measure tab can be loaded from the `.ti1` when a project is opened, and the button was enabled from that alone; chartread would then have failed with the chart file missing. That is a bug, not a case needing a message. Fixed in beta.128: Start is available only when the `.ti2` exists, and its tooltip says why when it is not. With the condition prevented, the message is gone from the model and from the code.

**C₀ and a corrupt file.** When the `.ti3` present *at the start of a measurement* is corrupt or empty, `C₀ = 0` — there is nothing in it to resume from and nothing to lose by measuring again, and it is treated exactly as "no measurement" for §3b's purposes. The file itself is still archived rather than deleted, because ChromIQ cannot judge whether it holds something the user would want.

### 3b. Judging the session by C₀ → C

| C₀ | C at end | Resume? | Verdict | What ChromIQ does |
|---|---|---|---|---|
| 0 | 0 | — | nothing read, nothing saved | delete the empty file; say so on screen |
| 0 | > 0 | no | normal first measurement | keep |
| > 0 | 0 | **yes** | **the resume destroyed the earlier work** | restore from `old/`, warn loudly |
| > 0 | < C₀ | **yes** | **readings went backwards** — cannot be right | restore from `old/`, warn loudly |
| > 0 | = C₀ | yes | resumed but read nothing new | keep; say nothing was added |
| > 0 | > C₀ | yes | normal resume | keep; say how many were added |
| > 0 | any | **no** | a fresh measurement replaced it | the replace warning already covers this; the archived copy stays |

The two "restore" rows are the case you described — *"if saved ti3 at stop was empty and the ti3 before start was 10 patches, and the session was a Refine/Resume, then we know something went wrong"*. Without C₀ this is undetectable.

**On reporting**: agreed — every one of these is told **on screen**, not only in the log. A log line is hidden information.

---

## 4. Chart integrity — when the chart changes under a measurement

You are right that this is the same problem from the other end: a `.ti3` describes *one* chart, and a profile describes *one* `.ti3`. Change the chart and the set stops belonging together.

**Triggers:** Generate Chart · loading a `.ti1` · applying a patch set from the editor · auto-update · any preset change that regenerates.

**Every one of them asks** (Knut, 2026-08-03, after beta.125 shipped with only two of them wired): *"the warning messages defined for section 4 … should then arrive for all these cases: Generate Chart, loading a .ti1, applying a patch set from the editor, any preset change that regenerates."*

**The auto-update preview is the one exception, and it is an exception about *how often*, not about *whether*.** A window on every turn of a layout knob would make the option unusable, so Knut set the rule:

> *"the popup window saying 'The live preview is not being re-drawn...' should come once only, then again the next time 'auto-update preview ...' is enabled. At the same time it can come in the log window until 'auto-update preview ...' is disabled."*

So the live preview **declines to re-draw** a run that holds work, writes the note to the log every time, and shows the window once per switch-on of the option. See **M-PREVIEW-PAUSED**.

| What the run holds | Run type | Warning | Message |
|---|---|---|---|
| Nothing | either | none — nothing to break | none |
| Chart only | either | none | none |
| Chart + partial `.ti3` | Profiling | "This run holds a partial measurement of {n} patches. A new chart cannot be measured with it — the patches would no longer match. The measurement is moved to `old/` and kept." | **M-CHART-PROFILING** |
| Chart + complete `.ti3` | Profiling | as above, plus: "…and you would have to measure the whole chart again." | **M-CHART-PROFILING** |
| Chart + `.ti3` + profile | Profiling | as above, plus: "The profile built from it is moved to `old/` too, because it describes a chart this run will no longer have." | **M-CHART-PROFILING** |
| **Chart + `.ti3` + profile, AND the run has verifications with readings** | **Profiling** | **W4 — the widest blast radius of the three; see below** | **M-CHART-W4** |
| Chart + `.ti3` (+ profile) | Verification | **W5** — the same shape as W4, one level down | **M-CHART-VERIFY** |
| Chart + a `.ti3` that is **corrupt or empty**, no profile | Profiling | a window of its own, naming the file as corrupt or empty | **M-CHART-CORRUPT** ✅ (not M-CHART-PROFILING) |
| Chart + a `.ti3` that is **corrupt or empty**, **and a profile** | Profiling | as above, **plus** what it costs the profile | **M-CHART-CORRUPT** ✅ with its profile paragraph |
| Any of the above, **and the trigger is the auto-update preview** | either | the preview declines to re-draw instead of asking | **M-PREVIEW-PAUSED** ✅ |
| Any of the above, **and the chart has no `.channels.json`** | either | the §4 message, **plus** a paragraph about the pages | **M-CHART-NOPAGES**, appended |
| Any of the above, **and the run cannot be duplicated** | either | the §4 message, **plus** a paragraph about Duplicate | **M-DUPLICATE-BLOCKED**, appended |

✅ = approved by Knut, 2026-08-04 — full text in **§M**, with the rest of the approved catalogue. 🆕 = **PROPOSED**, awaiting review — full text in **§M-PROPOSED**. Every message not marked here was approved earlier.

**What "`.ti3` exists" means in this table**, since Knut asked for it plainly: the rows above distinguish three things, and they are not the same.

| In the table | On disk | How ChromIQ decides |
|---|---|---|
| no `.ti3` | the file is not there | `Path.exists()` |
| a `.ti3` that is **corrupt or empty** | the file is there, but holds no readable readings — no `BEGIN_DATA`/`END_DATA`, no rows between them, or `NUMBER_OF_SETS` absent or 0 | §3a's *header only* and *empty* states |
| a `.ti3` with `{c}` readings | the file is there and `{c}` rows can be read | §3a's *partial*, *complete* and `B ≠ C` states |

**At this point no measurement is running**, so every count here is the state *before* anything is measured — `C₀` in §3b's terms.

**Messages combine.** A single window can be one base message with one or two paragraphs appended: M-CHART-PROFILING is the window, and M-CHART-NOPAGES and M-DUPLICATE-BLOCKED are paragraphs added to it when they apply. Nothing else in this specification stacks; these two do, because both describe the *same* replacement from a different angle.

**W4 — regenerating the profiling chart of a run that has a verification history**

> **This would undo the whole run, not just its chart**
>
> Replacing this run's chart breaks the chain three links deep:
>
> • the measurement of {n} patches no longer describes the chart in this run;
> • the profile built from that measurement no longer describes anything on disk;
> • and the {v} dated verification{s} under this run were printed **through** that profile, so they stop describing a profile that exists.
>
> Everything is kept in `old/` and nothing is deleted — but the run would no longer hold a set of files that belong together, and its verification history could not be continued.
>
> **Duplicate the run and change the chart in the copy** if you want a different chart while keeping this one's work and its history.

**W5 — replacing the verification chart**

> **The verification measurements already made in this run used the chart you are about to replace**
>
> The {v} dated verification measurement{s} in this run were all made with this verification chart. Replacing it does not make them wrong, and the report can still compare their figures — but those measurements would no longer have the chart they were made with, so nothing on disk would say what they were readings *of*.
>
> A trend across the change also compares two different charts, which is not the same measurement twice. See §6b for what that costs in practice.
>
> The chart is kept in `old/` and no measurement is touched. Duplicate the run instead if you want a different verification chart while keeping this run's verification measurements intact.

**Why W4 is worse than the row above it.** Without verifications, regenerating the chart costs a measurement and a profile — both rebuildable from a reprint. With verifications it also costs a **history**, and a history cannot be rebuilt at all: those sheets were printed on days that will not come back. That is why it gets its own row and its own message rather than another sentence on the end of the previous one.

The Verification row is the one worth arguing about: the damage is not to one file but to a **trend**, and a trend cannot be archived back into meaning. That is why "Duplicate the run" belongs in the message rather than in a footnote.

### 4a. What counts as "a chart" — one definition, taken from Restore Used Chart

You are right that this must not get a second opinion. The definition already exists in `workflow/chart_slot.py`, which is what Restore Used Chart compares and copies, and everything below uses it unchanged:

| Part | Rule | Where |
|---|---|---|
| Stem | the sanitised project name; `<stem>-verify` for a verification chart | `Run.stem` / `Run.verify_stem` |
| Profiling chart files | `.ti1` · `.ti2` · `.channels.json` · `.strips.json` · `.control-strip.json` | `PROFILING_CHART_SUFFIXES` |
| Never part of a profiling chart | the run's `<stem>.cht` / `<stem>_NN.cht`: made from the measurement by the scanner target, so never copied to `chart/` (Knut, #182 5958921500). A `.cht` an older `chart/` still holds stays on disk and is ignored | `ChartSlot.scanner_cht_files`, `_not_kept_in_a_snapshot` |
| Page images | any `.tif` / `.tiff` | `_IMAGE_SUFFIXES` |
| Travels with the chart | `meta.json` | `CHART_SIDE_FILES` |
| Verification chart files | **every file** at the root of `verifications/` — folders are never included, so the dated runs, `old/` and `reports/` are safe | `suffixes=None` in `slot_for_verification` |
| Never part of a chart | dot-files (`.DS_Store`, `._name`) | `live_files()` |
| Can the pages be redrawn? | only if a `.channels.json` is present | `has_layout_recipe()` |

#### ⏳ Awaiting confirmation — what Restore Used Chart does with the run's `.cht` (4.3.3-beta.3)

**Confirmed by:** *nobody yet.*

Knut ruled (#182 5958921500) that a run's `.cht` is kept on restore when it is
"in agreement with the chart in the chart/ folder", otherwise archived to
`old/` and removed, and that the Restore window says which. What "agreement"
means was not defined in the ruling; this is how it is implemented, and it
waits for his confirmation:

* A run's `.cht` is kept when it is, line for line, a page the scanner target
  would write for the RESTORED chart: the page is rebuilt from the stored
  copy's `.channels.json` by the writer itself
  (`workflow.scanin_target.scanner_cht_pages`), under the name it would get
  (`<stem>.cht`, or `<stem>_NN.cht` for page NN), and everything but the
  `EXPECTED` rows is compared (they are the measurement's XYZ, not the chart).
* Decided per file. A page the restored chart does not have, different patch
  boxes, or a stored chart with no scanner geometry → archived into the run's
  `old/<date>/` (the same folder as the replaced `meta.json`) and removed.
* Not applicable to a verification date: its chart folder is copied whole, as
  before. The calibration follows the run rule.
* The Restore window adds one sentence naming the file(s) and saying "kept in
  the run" or "moved to the run's “old” folder and removed from the run". The
  window is not in the §M catalogue, so the sentence was written into it
  directly. It is also shown when only a `.cht` would be removed.

Knut answered the three questions on 2026-10-02 (#182 5959825756), quoted:
*"1. Agreed, archive olde chart files to old, except the tif files, they are
deleted and gan be regenerated if the other files are restored. They take too
much space on the drive. 2. Yes, the cht and cie file are always a pair that
belongs together and must always match for the chart used. 3. agreement rule
approved."* Built for 4.3.3-beta.5, awaiting his confirmation of the result:

* The chart a restore replaces is moved into the same `old/<date>/` folder as
  the replaced `meta.json` (the run's `old/`, or `verifications/old/` for a
  verification date), except its page images, which are deleted
  (`_archive_replaced_chart`). The four Restore windows say so instead of
  "The chart that is there now is not kept".
* A `.cht` that is removed takes its `.cie` (same name) with it; a kept `.cht`
  keeps its `.cie` (`restore_cht_plan`).

**The two chart kinds are deliberately not defined the same way**, and it is worth knowing why before reusing this: a profiling chart shares its folder with the measurement, the profile and the run's own files, so it must be identified by suffix. A verification chart has a folder to itself, so everything in it *is* the chart.

#### When a chart is valid for this feature

| # | On disk | Is there a chart? | Can pages be redrawn? | Effect on §4 |
|---|---|---|---|---|
| 1 | nothing | no | — | no warning — nothing to break |
| 2 | `.ti1` only | **no** | — | no warning; a patch list is not a chart |
| 3 | `.ti1` + `.ti2` | **yes**, incomplete | **no** | warn; say the pages cannot be redrawn |
| 4 | `.ti1` + `.ti2` + `.channels.json` | **yes** | **yes** | warn |
| 5 | `.ti1` + `.ti2` + `.tif` | **yes** | **no** | warn; the pages would be lost |
| 6 | `.ti1` + `.ti2` + `.channels.json` + `.tif` | **yes**, complete | **yes** | warn — the ordinary case |
| 7 | `.tif` only | **no** | — | no warning; images with no chart are not measurable |
| 8 | dot-files only | **no** | — | no warning |

Rows 3 and 5 are the ones worth naming in the message, because losing pages that cannot be redrawn is a different loss from losing pages that can.

**Same rule as Duplicate, deliberately.** Duplicate requires `.ti1` + `.ti2` + `.channels.json` + at least one `.tif` — row 6. This feature warns from row 3 upward, because the question is different: Duplicate asks *"can this be copied into a working run?"*, while §4 asks *"is there something here to lose?"*, and rows 3 and 5 answer yes to the second and no to the first.

## 5. Starting a measurement over an existing one

The mirror image, and it needs `C = A` from §3a:

| State of the `.ti3` | Resume ticked | Warning before starting |
|---|---|---|
| None | — | none |
| Partial (`C < A`) | yes | none — this is what resume is for |
| Partial (`C < A`) | no | "This run already holds {n} of {A} patches. Starting without “Refine / resume” replaces them. Tick it to keep them and read only what is missing." |
| Complete (`C = A`) | no | "This chart is **fully measured** — all {A} patches. Starting a new measurement replaces the finished measurement this run's profile was built from. The old one is kept in `old/`, but the profile will no longer match until you build it again." |
| Complete (`C = A`) | yes | "All {A} patches are already read. Resuming will only re-read the ones you scan again." |
| Corrupt (`B ≠ C`, or `C` ≠ the chart's `A`) | either | **W6 — see below** |

**W6 — the measurement and the chart disagree**

> **This run's measurement and its chart do not match**
>
> The measurement file holds {C} readings, and the chart ({stem}.ti2) describes {A} patches. {extra}
>
> ChromIQ cannot tell which of the two is the wrong one. A measurement can be truncated by an interrupted session, and a chart can be replaced or edited outside ChromIQ — both look exactly like this from here.
>
> **What you can do:**
> • **Start a fresh measurement** — the safe choice if this chart is the one you printed. The existing measurement is kept in `old/` and nothing is lost.
> • **Cancel** — stops here so you can look at the files first. The run is at {path}. This run's `chart/` folder holds the copy of the chart that was stored when it was last measured, and Restore Used Chart puts that copy back. There is exactly one; ChromIQ does not keep earlier versions of a chart.
>
> Resuming is not offered, because resuming into a mismatch would write readings against patch positions that may not be the ones on your paper.

where `{extra}` is the second-order detail when the file also disagrees with itself: *"The file's own header claims {B} readings, which does not match the {C} it contains — so this file may be damaged as well as mismatched."*

The wording is deliberately cautious throughout. ChromIQ can see that two numbers disagree; it cannot see **why**, and an interrupted session, a hand-edited file and a file dropped into the wrong folder all look identical from here. Saying "damaged" would be naming a cause the evidence does not support.

## 6. Rebuilding the profile when the run already has verifications

### 6a. What actually changes, and what does not

**Correcting what I wrote before.** I said a trend across a profile change "no longer means anything". That is wrong, and the report is better than that: its metrics were built to be compared across different charts and runs of the same printer. What a rebuild costs is narrower and more precise:

| | Effect of building a new profile under existing verifications |
|---|---|
| The **dated measurements** | untouched — still valid readings of what was on paper that day |
| Their **origin** | lost: each was printed *through* a profile that no longer exists, and nothing on disk records which |
| **Comparability of the numbers** | preserved in kind, but the reference has moved — later dates answer a different question from earlier ones |

The measurements do not become wrong. They become **undocumented**, which is the real damage: a year later nothing says which profile a given date was measured against.

### 6b. What comparing across charts actually costs, in statistics

Knut asked for this to be researched rather than asserted. Two of the report's metric families behave differently when the charts differ in size, and the difference matters:

**Averages are comparable; their precision is not equal.** The standard error of a mean is `SD / √n`, so a 400-patch chart's average ΔE carries **twice** the uncertainty of a 1 600-patch one. The average itself stays an unbiased estimate — it is not "wrong" — but a difference between two dates that is smaller than their combined standard error is not evidence of anything. A trend across charts of different sizes is readable; it is simply noisier on the smaller ones.

**The maximum is not comparable at all, and this one is a bias rather than noise.** The maximum of a sample can only rise as the sample grows: more patches mean more chances to draw from the tail. A 1 600-patch chart will report a higher maximum ΔE than a 400-patch chart *of the same printer, on the same day, with nothing wrong*. So `Maximum ΔE, all patches` must not be compared across charts of different sizes — and it is one of the five metrics carrying a Pass/Fail verdict.

**The percentile metrics sit in between.** `Worst 10%` and `lowest 95%` are order statistics over a fixed *fraction*, so they are far steadier than the raw maximum, but they still drift a little with n because the tail is sampled more finely.

**Which is exactly why a verification history is meant to use one chart** — and why the recommendation is to duplicate the profile run rather than re-base an existing one. Same chart, same size, same reference: the numbers then differ only because the printer did.

### 6c. The other verification tools, across differing charts

| Tool | Compares | Across differing charts |
|---|---|---|
| **Measurement Report** | measured vs the chart's design values, or vs stored reference | comparable, with the caveats above |
| **`profcheck`** (Check & Refine) | a profile against **the data it was built from** | not applicable — it never looks at a verification measurement |
| **Tools ▸ Verify against reference** (`colverify`) | two CIE datasets, patch by patch | **requires matching patch sets**: it pairs by `SAMPLE_ID`, or by `SAMPLE_LOC` with `-l`. Two different charts do not pair, so this tool cannot compare across a chart change at all |
| **Cube corners** (§9a) | nearest patch to eight ideal corners | comparable *only if both charts contain the corners* — which is why §9a makes them mandatory |

So one tool degrades gracefully, one is unaffected, and one stops working outright. That is worth knowing before someone changes a chart mid-history.

### 6d. The warning, and the checkbox

**The build signature idea is dropped.** Knut: *"The main intention is to make user aware, then the user is given authority to act responsibly on an informed basis."* Rebuilding with identical settings is neither dangerous nor the likely case — someone rebuilding has usually changed something, or is testing. Trying to detect "harmless" rebuilds bought precision nobody needed at the cost of machinery and a new file format.

So: **warn whenever a run holds a profile, a verification chart and at least one dated measurement.** Explain, recommend, allow. And add the same escape the "This chart already has a measurement" window has — *"Don't show this again for this run"*, per run and per session, so a testing session is not nagged and a fresh launch warns again.

**W1 — building a new profile under an existing verification history**

> **The verification measurements in this run were made against the profile you are about to replace**
>
> This run holds **{n} dated verification measurement{s}**, going back to {date}. Each was printed **through** the profile in this run and measured against it, so it records how that profile behaved on that day.
>
> Building a new profile here does not make those measurements wrong, and it deletes nothing — but they will no longer say which profile they belong to, and comparing them with verification measurements made afterwards means comparing against two different profiles.
>
> **What each button does:**
> • **Duplicate the run and build there** *(recommended)* — copies this run's chart, measurement and profile into a new run and builds there. This run keeps its profile and its verification measurements exactly as they are, and the copy starts fresh. This is the clean way to try a different profile from the same readings.
> • **Build here anyway** — replaces this run's profile. The current profile is moved to `old/`, and the {n} dated verification measurement{s} are moved to `verifications/old/{date}/` with it, because they describe the profile that is being replaced. Nothing is deleted.
> • **Cancel** — changes nothing.
>
> ☐ Don't show this again for this run

**Why the dated verifications move to `old/` too** — Knut's question, and the answer follows the folder model rather than being invented for this case: a run is meant to hold **one matching set**, chart → measurement → profile → the verifications of that profile. Leaving the old dates in place would break that rule and leave the report to explain a discontinuity for ever. Archiving them keeps the rule intact, keeps every file, and starts the new profile with a clean history — which is what "build here anyway" means.

That also retires the divider idea entirely: with the old dates archived there is no discontinuity left for the report to draw a line through.

#### Confirmed behaviour: a rebuild archives the profile only (supersedes the W1 text and the two paragraphs above)

**Confirmed by:** Knut, 2026-10-03 (#182 [5964384250](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5964384250) Q1, and [5964076758](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5964076758) Q4).

The W1 text above, and "Why the dated verifications move to old/ too", were Knut's own earlier rule and are kept as history. He replaced it:

> *"verification runs shall not be automatically archived when the profile is re-built from new measurements. Only after selecting run type =verification and this window pops up, 'Make a new chart from current profile' shall also include 'and archive old verification runs into old/ folder'. The wording can be improved. The user shall also be given the option to cancel and keep the old verification runs, leaving the user the chance to modify or delete verifications manually."* (5964384250 Q1)

> *"Yes reword it."* (5964076758 Q4, on "Each was printed through the profile", which is untrue for raw and FROM PROFILE GAMUT sheets.)

* **"Build here anyway" moves the profile only**, into `runs/runN/old/<timestamp>/`. The dated verification measurements, their reports and the verification chart stay where they are. Nothing under `verifications/` is touched by any build.
* **A silenced warning behaves the same.** The profile still moves (every build archives the profile it replaces); nothing under `verifications/` moves. 5964076758 Q4's "still move them" is superseded by 5964384250 Q1.
* **The warning is reworded**: M-PROFILE-VERIFY's revision waits in §M-PROPOSED. When it is shown, and its "Don't show this again for this run" checkbox, are unchanged.
* What happens to the verifications afterwards is §6f.

### 6e. All the combinations

| # | Profile | Verify chart | Dated verifications | Warning | What the build moves (Knut, 5964384250 Q1) |
|---|---|---|---|---|---|
| 1 | no | — | — | none — first build | nothing |
| 2 | yes | no | — | none — no history to document | the profile, to `runs/runN/old/<ts>/` |
| 3 | yes | yes | 0 | none — a chart with no readings is just a chart | the profile |
| 4 | yes | yes | ≥ 1, "don't show again" set this session | none | the profile; nothing under `verifications/` |
| 5 | yes | yes | 1 | **W1** (singular) | on "Build here anyway": the profile; nothing under `verifications/` |
| 6 | yes | yes | ≥ 2 | **W1** (plural) | on "Build here anyway": the profile; nothing under `verifications/` |
| 7 | target is a loaded file, not a run | — | — | none | the profile it replaces |

No row now depends on knowing whether the profile would differ, which is what the signature was for.

### 6f. Choosing Verification after the profile was replaced

#### Confirmed behaviour: one window, three texts

**Confirmed by:** Knut, 2026-10-03 (#182 [5964076758](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5964076758), [5964384250](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5964384250) and [5965626117](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5965626117), answering the plan in [5965550986](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5965550986)).

* **When.** The user chooses Verification (run type, run or project) for a run whose dated measurements or FROM PROFILE GAMUT chart belong to an earlier profile: *"a user entering run type= verification after the profile was replaced should be informed that the dated verifications that exist no longer match with the new profile, and then offer to archive the old dated verifications into old/ folder and then start fresh"* (5964076758).
* **One window, no sound** (5964076758 Q5: *"OK"*). The default button makes a new chart from the current profile (Q3: *"Yes"*).

| Dated measurements from an earlier profile | Live verification chart | Text | Default button does |
|---|---|---|---|
| ≥ 1 | FROM PROFILE GAMUT, made from an earlier profile | **A** M-VERIFY-EARLIER-PROFILE | moves the measurements and their reports to `verifications/old/<ts>/`, then opens Create Chart on FROM PROFILE GAMUT with this run's last settings |
| ≥ 1 | ordinary, or a gamut chart from the current profile | **B** M-VERIFY-EARLIER-PROFILE-KEEP-CHART | moves the same, keeps the chart, and opens Create Chart showing that chart so the user can confirm it and go on to printing (5965626117: *"opening Create Chart should be done anyway, so that the user can confirm if this is the chart he wants to use, and then move to printing the chart if desired"*) |
| 0 | FROM PROFILE GAMUT, made from an earlier profile | **C** M-VERIFY-CHART-EARLIER-PROFILE | opens Create Chart on FROM PROFILE GAMUT with this run's last settings |
| 0 | anything else | none | no window |

* **The chart moves at Generate Chart, as today**, never from the window (5964384250 Q1 *"Yes"* to the plan's point 2), so a run is never left without a chart.
* **An ordinary chart is kept** and usable as it is (5964384250 Q2).
* **"Keep them" changes nothing**, so the user can change or delete the verifications by hand (5964384250 Q1), and it is **asked again after ChromIQ is restarted**, the way "Don't show this again" on the rebuild warning lasts only until ChromIQ is closed (5965626117).
* **The earlier profile's reports go with its measurements** (5964076758 Q6: *"Earlier reports belonging to old profile is archived with other files"*). **Quality_Check reports stay** (5964384250 Q3: *"yes"*).

#### ⏳ Awaiting confirmation: how ChromIQ decides what belongs to an earlier profile, and when it asks

**Confirmed by:** *nobody yet.*

Our implementation of the rulings above (`workflow/verification_profile_match.py`, `ui/earlier_profile_offer.py`), driven on screen on 2026-10-03; the wording of all five texts waits in §M-PROPOSED.

* **The anchor P** is the creation time in the ICC header of the run's current profile (`merged.icc` when a refinement merge made one, else the run's own `.icc`). ArgyllCMS writes it in UTC; it is converted with the offset valid on that date. No profile, or no date in its header: nothing is flagged. **No file modification times are used anywhere**: they are reset by a copy, a zip or a sync.
* **A dated folder** counts only when it holds a measurement. It is from an earlier profile when any of these is earlier than P: (a) its folder name; (b) the `CREATED` of the colorimetric reference in its own `chart/` snapshot; (c) the `printed_at` of its OWN print record (beside the `.ti3` or in its `chart/` snapshot, never the shared one beside the live chart, which describes the chart's last print).
* **The live chart** is from an earlier profile when it carries a colorimetric reference (a FROM PROFILE GAMUT chart) whose `CREATED` is earlier than P. An ordinary chart is never flagged.
* **Which reports move:** each dated folder moves whole (its `reports/`, `chart/`, `reads/`, `old/` and `.confirmed.json` inside it), and a document in `verifications/reports/` moves when it covers a moving date and none of the dates it covers stays at the top level of `verifications/`. Project-level reports and the run's own `reports/` stay. One timestamped folder holds everything moved by one answer; the folder is named in the Create Chart log (M-VERIFY-EARLIER-ARCHIVED-HERE).
* **The one trigger** is a change of the bar's (project, run type, profile run) to Verification. The verification date is not part of it, so Start Measurement, which selects a date, can never raise the window. A profile cannot change while Verification is selected (the Build Profile tab is locked there and the bar is locked during a build), so no second trigger is needed.
* **One check at a time.** It waits while another window is open and asks when that window closes; it is dropped while a measurement or a build is running. The Measure tab's own arrival windows (the verification pre-flight and "This chart already has a measurement") now also wait while any other window is open and are asked again when it closes, so no two of them are ever stacked.
* **"Keep" is remembered** per run, profile file and profile time, in memory only.
* **Text B shows the kept chart in its own module.** After "Archive them", Create Chart opens on Manual when the kept chart is an ordinary one (no colorimetric reference; its recipe is restored there), so it is not shown under FROM PROFILE GAMUT, whose Generate Chart would replace it. A FROM PROFILE GAMUT chart made from the current profile stays on that module, and Guided or Manual, when the run's own settings put Create Chart there, is left as it is. The 2026-08-10 default for every other way into Create Chart is unchanged.
* **Text B without a chart.** When the run has dated measurements from an earlier profile and no verification chart at all, the window uses M-VERIFY-EARLIER-PROFILE-NO-CHART: text B without "the verification chart itself can still be used" and without "the chart stays. Create Chart then opens on this chart".
* **Accepted limits.** A project moved between time zones is off by the zone difference, only for dates within hours of a build. A measurement imported after the build from a sheet with no print record of its own is not flagged; neither is a profile copied back by hand.

## 7. Every event detected during a read, and where it comes from

Line numbers are from **ArgyllCMS 3.5.0** source (`spectro/`) and from ChromIQ's own helper, found by searching each source for the string the detector keys on. "Detected by" is the pattern in `workflow/measure_manager.py`.

**Reading the "where it is printed" columns:** a dash means that program does not print it at all, which is a fact about the event rather than a gap.

| Event | Detected by | stock `chartread.c` | ChromIQ `chromiq_chartread.c` | `spotread.c` | Correct? |
|---|---|---|---|---|---|
| Strip read OK | `(?:strip\|patch)\s+read\s+ok` | 1909 | 2478 | — | ✅ fixed in beta.123 — it matched only "strip" before |
| Patch read OK | same pattern | 2422 | 3079 | — | ✅ |
| Strip read failed | `Strip read failed[^(]*\(([^)]+)\)` | 1652, 1671, 2222 | 2181, 2205, 2869 | — | ✅ three call sites, one wording |
| Wrong strip read | `Seem to have read strip pass (\w+) rather than (\w+)` | 1854 | 2412 | — | ✅ |
| Unexpected colour response | `unexpected response.*\(DeltaE\s*([\d.]+)\)` | 1887, 2445 | 2451, 3104 | — | ✅ both strip and patch paths |
| Strip read interrupted | `Strip read stopped at user request` | 1608 | 2127 | — | ✅ |
| Patches still unread | `Done\s*\?\s*-\s*At least one unread patch \(([^)]+)\)` | 1593, 2345 | 2108, 2998 | — | ✅ strip and patch paths |
| Ready to read strip | `Ready\s+to\s+read\s+strip` | 1539 | 2010 | — | ✅ |
| Ready to read patch | `Ready to read patch\s+'([^']+)'` | 2115, 2146 | 2753, 2784 | — | ✅ |
| All rows read | `ALL\s+ROWS\s+READ` | 1539 | 2010 | — | ✅ |
| Are you sure | `Are\s+you\s+sure\s+\[y/n\]` | 1593, 2295, 2345 | 2108, 2945, 2998 | — | ✅ |
| Sensor in wrong position | `sensor.*wrong\s+position\|sensor should be in surface` | 1644 | — | — | ✅ second alternative comes from the driver — `munki.c:490` |
| Comms establish failed | `Establishing communications with instrument failed with message\s+'([^']+)'` | 488 | 914 | — | ✅ |
| Instrument init failed | `Initialising instrument failed with message\s+'([^']+)'` | 498 | 924 | — | ✅ **exits 0** — see §7 |
| Instrument mode rejected | `Setting instrument mode failed with error\s*:?\s*'([^']+)'` | 975 | 1409 | 1603, 1618, 2040 | ✅ |
| Capability missing | `Need (reflection\|transmission\|emissive)\s.*?reading capability` | 536, 549, 559 | 970, 983, 993 | 1492 | ✅ |
| Correction file failed | `Setting Colorimeter Correction Matrix failed\|…` | 629 | 1063 | 1696 | ✅ |
| No instrument found | `no instrument detected\|no suitable instruments\|no instruments connected` | 476 | 901 | 1199 | ✅ |
| Chart / instrument mismatch | `Warning:\s*chart is for\s+(\S+),\s*using instrument\s+(\S+)` | 526 | 952 | — | ✅ |
| Generic instrument error | `Got\s+'([^']+)'\s*\(([^)]+)\)\s+error\.` | 391, 396, 1710 | 796, 808, 2251 | 391, 396 | ✅ |
| XY: place sheet | `Please place sheet\s+(\d+)\s+of\s+(\d+)\s+on table` | 1123 | 1576 | — | ✅ |
| XY: sheet read OK | `Sheet\s+(\d+)\s+of\s+(\d+)\s+read OK` | 1325 | 1782 | — | ✅ |

### 7a. Events that do NOT come from these three programs

Three of the windows are driven by strings printed elsewhere, and that is worth recording because it explains why they behave the same in every mode:

| Event | Printed by | Note |
|---|---|---|
| Calibration prompt | `spectro/instappsup.c:289` | shared application-support code — identical in chartread, spotread and the ChromIQ helper, which links the same library |
| Calibration complete | `spectro/instappsup.c:199` | as above |
| Device being used | `spectro/usbio_ox.c:380, 387` (macOS), `usbio_dk.c:544` (Windows) | the USB backend, **per platform**. Line 380 is `a1logd` — a *debug*-level message that may not reach the terminal at normal verbosity, so this one is the least reliable detector in the table |
| Strip may be misaligned | — | **not an Argyll string at all.** It is ChromIQ's own reading of a failed strip plus its reason. `"Bad strip"` exists in Argyll only for the DTP41/DTP20 (`dtp41.c:1026`, `dtp20.c:1251`) and never reaches a ColorMunki or i1 user |

### 7c. One failure, reported twice — the helper prints it AND sends it (beta.141)

Knut's beta.140 log has it exactly:

```
Patch read failed due unexpected error :'Wrong Sensor Position' (Sensor should be in surface position)
send_key '{"cmd": "ok"}'                                   <- Retry was pressed
{"event":"error","kind":"misread","detail":"Sensor should be in surface position"}
```

The helper **prints** the failure in the same prose stock chartread uses, and
then — once the window it raised has been answered — reports the same failure
again as a **JSON event**. Both parsers were reading independently, so each
raised a window: Instrument Error -> Retry -> Patch Read Failed -> Retry ->
Instrument Error, with no way out but Stop.

**The rule:** while a sensor-position window is open, an event describing that
same sensor position is the failure already on screen, not a new one, and is
dropped. Anything else — a different misread, or the dial being wrong *again*
after the reader has moved on — still opens its own window, because silencing
those was the opposite bug in beta.136. Both directions have tests
(`tests/test_knut_beta140_no_window_loop.py`).

This is the general shape of every engine-parity problem in §7: **the two
parsers see one event, and whichever notices first owns it.**

### 7b. What this table changes

1. **`Device being used` is detected in both of its forms**, per Knut: either one raises the "Instrument Not Available" window. The error-level form (`usbio_ox.c:387`) reaches the terminal reliably; the debug-level one (`usbio_ox.c:380`) may not, so the pattern must match both rather than assuming which arrives, and the same window stays reachable from the generic error path as a third route.
2. **`Strip may be misaligned` is ChromIQ's own inference**, so it belongs in ChromIQ's documentation as an interpretation, not as an instrument message.
3. **Everything else is confirmed** against the exact line that emits it, in all three programs.

## M. The message catalogue

*Correcting myself: I referred to texts "marked (to define)", and no table carried such a marker. There was no such marking — the messages simply had not all been written. They are all written below, each with an ID, and every table in this document now names the ID it uses.*

Every window this specification can raise, in one place. **ID → where it is used → the text.**

**Bold in the quoted texts below is this document's typography, not the window's.** The windows show the headline in bold — it is the one line the user must read first — and everything under it at normal weight, because a screen of bold is a wall nobody reads. Emphasis inside a message is therefore carried by the words, and a test fails if a `**bold**` span ever reaches a message string, where it would show on screen as asterisks.

### M-END · ending a measurement — §1, §1a, §2

> **Keep what you have measured so far?**
>
> You have read **{n} patches** in this session. They are not in your measurement file yet — ChromIQ can write them now, or end the session without them.
>
> **What each button does:**
> • **Save and stop** — writes what you have read so far to this run's measurement file and ends the session. You can carry on later with "Refine / resume existing measurement (-r)", reading only the strips or patches that are still missing.
> • **Discard and stop** — ends the session and keeps nothing from it. *(when a measurement was already there: "Your previous measurement of {m} patches is put back exactly as it was.")*
> • **Keep measuring** — closes this window and carries on where you were.

### M-END-EMPTY · ending with nothing read — §1 row 5

> **Nothing was measured, so nothing was saved**
>
> This session ended before any patch was read. Your run is exactly as it was: {state}.
>
> *{state} is one of:* "the measurement it already held is untouched" · "it still has no measurement".

### M-TI3-EMPTY · the saved file holds no readings — §3a

> **The measurement file was empty, so it has been put aside**
>
> The file this session wrote contains no readings. It has been moved to `old/{date}/`, and {restored}.
>
> *{restored}:* "your previous measurement of {m} patches has been put back" · "this run has no measurement, as before".

### M-TI3-SHRANK · a resume ended with fewer readings — §3b

> **This session ended with fewer readings than it started with**
>
> The measurement held **{c0} patches** when this session began and **{c}** when it ended. A resume should only ever add readings, so something has gone wrong.
>
> Your earlier measurement has been put back from `old/{date}/`, and the file this session wrote is kept beside it so nothing is lost. Nothing needs doing right now — measure again when you are ready.

> **Amended 2026-08-08 (Sebastian).** The two bullets used to read *“Start a
> fresh measurement”* and *“Cancel and look at the files first”* — names the
> window has never had. Its buttons are **Measure anyway** and **Cancel**, which
> are Knut's own beta.132 ruling: *“Measurement has not yet started, so it is
> wrong name for the ‘MEASURE AGAIN’ button. Call button instead ‘MEASURE
> ANYWAY’.”* The buttons were right and the message was stale, so the message
> follows the buttons. Nothing else about the message changed. Found by the
> Japanese translator, who looked up every control name the text quotes.

### M-TI3-MISMATCH · the measurement and the chart disagree — §5

> **This run's measurement and its chart do not match**
>
> The measurement file holds **{c} readings**, and the chart ({stem}.ti2) describes **{a} patches**. {extra}
>
> ChromIQ cannot tell which of the two is the wrong one. A measurement can be cut short by an interrupted session, and a chart can be replaced or edited outside ChromIQ — both look the same from here.
>
> **What each button does:**
> • **Measure anyway** — starts a fresh measurement. The safe choice if this chart is the one you printed: the existing measurement is moved to `old/{date}/` and nothing is lost.
> • **Cancel** — stops here so you can look at the files first. The run is at {path}. This run's `chart/` folder holds the copy of the chart that was stored when it was last measured, and **Restore Used Chart** puts that copy back. There is exactly one; ChromIQ does not keep earlier versions of a chart.
>
> Resuming is not offered here, because resuming into a mismatch would write readings against patch positions that may not be the ones on your paper.
>
> *{extra}, only when the file also disagrees with itself:* "The file's own header claims {b} readings, which does not match the {c} it contains — so this file may be damaged as well as mismatched."

### M-REPLACE-PARTIAL · starting over a partial measurement — §5

> **This run already holds part of a measurement**
>
> {c} of the chart's {a} patches have been read. Starting now without **Refine / resume existing measurement (-r)** replaces them.
>
> Tick that option to keep what you have and read only the patches that are still missing. The existing measurement is moved to `old/{date}/` either way, so nothing is lost.

### M-REPLACE-COMPLETE · starting over a finished measurement — §5

> **This chart is fully measured**
>
> All **{a} patches** have been read, and this run's profile was built from that measurement.
>
> Starting a new measurement replaces it. The finished measurement is moved to `old/{date}/` and nothing is deleted — but the profile in this run will no longer match the measurement beside it until you build it again.
>
> *Refine / resume is left exactly as you set it before pressing Start; this window does not change your choice.*

### M-REPLACE-UNCOUNTABLE · a measurement file with nothing readable in it — §3a

*Approved by Knut, 2026-08-04 ("Accepted message"). Why it exists: with §5's partial message this case printed "**0 of the chart's ? patches have been read**", which reads as a fault in ChromIQ rather than a fact about the file. It must also not point at Refine / resume, because there is nothing in the file to resume from.*

> **This run already holds a measurement file**
>
> ChromIQ cannot tell how many readings it contains — the file is there, but it holds no readable measurement data. That usually means a session ended before the first patch was read, or the file was changed outside ChromIQ.
>
> Starting now writes a new measurement in its place. The file you have is moved to the run's "old" folder and nothing is deleted, so you can always look at it afterwards.
>
> Refine / resume is not offered for this file, because there is nothing in it to resume from.
>
> The measurement file is: {path}

### M-CHART-PROFILING · regenerating a chart with work under it — §4

> **This run already holds work made with the chart you are about to replace**
>
> Replacing the chart in this run means what is here no longer describes it:
> {items}
>
> Everything is moved to `old/{date}/` and nothing is deleted — but this run would no longer hold a matching set of files.
>
> **Duplicate the run and make the new chart in the copy** if you want a different chart while keeping this run's work.
>
> *{items} lists only what is actually present:*
> • "a measurement of {c} patches"
> • "the profile built from it"

### M-CHART-W4 · regenerating the chart of a run that has a verification history — §4 (W4)

*The text is §4's W4 block, unchanged; the ID was assigned when the catalogue was moved into `workflow/measurement_messages.py` so that every window could be checked against it.*

> **This would undo the whole run, not just its chart**
>
> Replacing this run's chart breaks the chain three links deep:
>
> • the measurement of {c} patches no longer describes the chart in this run;
> • the profile built from that measurement no longer describes anything on disk;
> • and the {v} dated verification runs under this run were printed through that profile, so they stop describing a profile that exists.
>
> Everything is kept in the run's `old/` folder and nothing is deleted — but the run would no longer hold a set of files that belong together, and its verification history could not be continued.
>
> Duplicate the run and change the chart in the copy if you want a different chart while keeping this one's work and its history.
>
> The `old/` folder is here: {folder}

### M-CHART-NOPAGES · the pages cannot be redrawn — §4a rows 3 and 5

> **This chart's printed pages cannot be recreated**
>
> This chart has no layout recipe (`.channels.json`), so ChromIQ cannot redraw its pages. {pages}
>
> If you have the printed sheets, keep them — they are the only copy. Everything is moved to `old/{date}/` rather than deleted.
>
> *{pages}:* "The {n} page images in this run are the only ones there will be." · "This run has no page images to lose."

### M-OVERLAY-NO-MEASUREMENT · the overlay is asked for on a chart that has never been measured — Measure tab

> **This chart has not been measured yet**
>
> There is no measurement file beside this chart, so there is nothing to draw on the patches.
>
> Read the chart with your instrument and the overlay will fill in as you go, showing what you measured against the colour each patch was meant to be.

*Approved by Knut, 2026-08-14: "Text approved. Make Sure to use the guideline
used for other messages, if relevant." Switching to a run that had never been
measured showed **M-TI3-MISMATCH**'s claim — that the measurement was made for a
different chart — about a file that does not exist (#155). Stopping that false
claim was the bug fix; this is the window that replaces it. It is a **window**
and not a log line, per his ruling in the same review: "all events shall have
windows, and not hidden in a log where user will not see it."*

### M-CHART-CORRUPT · the run's measurement file cannot be read — §4

*Approved by Knut, 2026-08-04. **It is the window**, not a paragraph inside another one — his ruling on beta.133: "M-CHART-CORRUPT (ONLY THIS MESSAGE …)". It replaces M-CHART-PROFILING whenever the run holds a `.ti3` that is corrupt or empty, because M-CHART-PROFILING's `{items}` list cannot describe a file whose readings will not count — "a measurement of 0 patches" would be false, and naming it in a list under a headline about matching files says less than the message below says on its own. M-CHART-NOPAGES and M-DUPLICATE-BLOCKED still append to it when they apply; they are about other things.*

> **The measurement file in this run cannot be read**
>
> It has no readable measurement data in it — no readings, or a structure ChromIQ cannot make sense of. That can happen when a session ended before the first patch was read, or when the file was changed outside ChromIQ.
>
> It is moved to the run's "old" folder rather than deleted. **Look at it there before you measure again** — ChromIQ cannot tell whether it holds anything you would want to keep, and only you can judge that.

*Appended to that when the run also holds a profile:*

> The profile in this run moves to the "old" folder with it. That profile was built from a measurement, and the measurement file that should describe it can no longer be read — so nothing on disk now connects the profile to the chart it came from. ChromIQ cannot tell whether the file was always like this or became so later, and it cannot repair it. Measuring the chart again is the way to get a run whose chart, measurement and profile describe each other once more.

*(The `{items}` entry that once went with it is gone: with the message standing on its own there is no list to fill.)*

### M-PREVIEW-PAUSED · the auto-update preview declines to re-draw — §4

*Approved by Knut, 2026-08-04 ("Accepted message"). The auto-update preview re-lays out the chart in the run, so it is a §4 trigger — but a window on every turn of a layout knob would be unusable. Knut accepted the exception on 2026-08-03 and set the rule: "the popup window … should come once only, then again the next time 'auto-update preview …' is enabled. At the same time it can come in the log window until 'auto-update preview …' is disabled."*

> **The live preview is not being re-drawn**
>
> This run already holds work made with the chart the preview would replace, so the preview is left as it is rather than re-drawn over it.
>
> Press "Generate Chart" when you want the new layout. You will be told exactly what moves to the run's "old" folder first, and nothing is deleted.
>
> This window appears once each time you switch "Auto-update preview" on. While it stays on, the same note goes to the log instead, so your layout work is not interrupted.

### M-DUPLICATE-BLOCKED · Duplicate is recommended but unavailable — §4a, §6

*A paragraph appended to whichever message recommends Duplicate, when the run cannot be duplicated.*

> **Duplicate is not available for this run.** It needs all four of these: the patch list (.ti1), the laid-out chart (.ti2), the layout recipe (.channels.json) and at least one printed page (.tif). This run is missing {missing}.

### M-CHART-VERIFY — definition moved to §M-PROPOSED

*The wording was revised after the 2026-08-10 hardware session (Sebastian
saw the old text live and it earned a "needs rework": it ignored the
per-date chart snapshots and its Duplicate advice contradicted its own
"no measurement is touched"). The revision awaits review in the
awaiting-review section below; once approved it returns here. The archive
it promises is now real: ``verifications/old/<date>/``.*

### M-IMPORT-DONE · the import succeeded — Measure ▸ IMPORT

*Approved by Sebastian, 2026-08-10 — seen live in the hardware session
("import worked and the messages were good").*

> **The measurement was imported**
>
> It is filed as this run's verification from {when}, in its own dated folder:
> {folder}
>
> A copy of the chart it was measured against is stored with it, so the result stays interpretable even if the chart is replaced later.
>
> To see the colour-accuracy figures, open Tools ▸ "Measurement report" — the imported measurement is already in place there.

---

### M-VERIFY-SAVED · a verification measurement was saved — Measure

*Approved by Sebastian, 2026-08-10 (delegated: "if you think the text
... is correct, friendly, extensive and easy to understand then use
it"), after using it live in the hardware session.*

*Replaces the completion window's inline text. It promised "colour accuracy"
but only offered the measurement inspector — the accuracy analysis lives in
the measurement report, so the window now offers both doors and says what
each is for (Sebastian, 2026-08-10 hardware session). Buttons: Close · Open
in measurement inspector · Open measurement report (default).*

> **Verification Measurement Saved**
>
> Your verification measurement has been saved as {name}, in its own dated folder.
>
> This file checks a print against a profile — do not build a profile from it. Two ways to look at it:
>
> Measurement report — the colour-accuracy analysis: how close each printed colour landed to what the profile expected, the worst patches, your printer's reach at the cube corners, and — once you have several dated verifications — how the profile holds up over time.
>
> Measurement inspector — the physical portrait of this one print: paper white, contrast, grey cast, and how it behaves under different light.

### M-BUILD-ELSEWHERE · the measurement belongs to another run — §6

*Approved by Knut, 2026-08-04. Raised when Build Profile is pressed while the measurement loaded in the tab sits in a different run's folder from the one the bar shows — his Demo-08 step 10: "I created a profile for run 6 via standing in run 5."*

> **This measurement is not in the run you have selected**
>
> The bar shows {run}, but the measurement loaded here comes from:
> {folder}
>
> A profile is always built beside the measurement it is built from, so pressing Build Profile now writes the profile into that folder — not into {run}. The run you have selected would be left exactly as it is.
>
> **What each button does:**
> • **Build anyway** — builds from this measurement and puts the profile beside it. Choose this when you meant to work on that run.
> • **Cancel** — changes nothing. To build into {run}, load that run's own measurement first: switching "Profile run" in the bar loads it for you when the run has one.

### M-PROFILE-VERIFY — definition moved to §M-PROPOSED

*Revised 2026-10-03 on Knut's rulings (#182 5964384250 Q1: a rebuild archives the profile only; 5964076758 Q4: "Each was printed through the profile" is to be reworded). The revision awaits review in the awaiting-review section below; once approved it returns here. The text it replaces said "Build here anyway" moves the dated verification measurements to `verifications/old/{date}/`, which it no longer does.*

---

### M-NO-INSTRUMENT · the instrument is not there — §S2

*Knut's own words, written by him in his beta.150 report and used unedited, so
this one is approved by authorship. It replaces the original "No Instrument
Found" bullet list, and it replaces the ten-second window I had proposed as
**M-INSTRUMENT-SILENT** — which is withdrawn:* "I prefer your more detailed
message, but the original 'No Instrument Found' had a few bullets to add."

*Two things about it are his instruction rather than the text. It arrives **5
seconds** after the no-instrument condition is detected — the detection is
unchanged, only the moment it reaches the user, which used to be whenever
chartread happened to exit (about twenty seconds). And its **OK button ends the
session through the one ending every route shares**, so nothing read is lost
and nothing is discarded without being offered:* "All messages that can arrive
during measurement must exit in that safe manner, as a single exit strategy for
all cases."

> **No Instrument Found**
>
> ChromIQ has started the measurement and asked your instrument to wake up, and it has not replied for {n} seconds. A working instrument answers almost at once, so something is in the way.
>
> This is nearly always the connection rather than anything you did. Try these in order:
>
> •  Unplug the instrument's USB cable and plug it back in.
> •  Use a different USB port, and plug straight into the computer rather than through a hub.
> •  Close anything else that may be holding the instrument — another profiling program, or a virtual machine.
>
> Nothing has been lost. The measurement you already had is put back exactly as it was if this session ends without reading anything, and you can keep waiting instead if you would rather.

---

### M-NO-INSTRUMENT-NONE · APPROVED · no instrument is connected at all — §S2

**Approved by:** Knut, 2026-10-04, #182 [5979780372](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979780372): *"all are ok"*, answering question 1 of [5979436912](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979436912) (*"Is this wording OK?"*), in full.

*Knut, #182 5969949735 (beta 7). When ChromIQ refuses to start a reader
because no instrument is attached (the only serial port is the computer's own,
`core/instrument_port.py`), M-NO-INSTRUMENT came after about one second and
still said the instrument "has not replied for 5 seconds" and suggested
turning off "Faster instrument connection". Asked whether that case should be
reworded, he answered "yes". This variant is shown only for that refused
start; M-NO-INSTRUMENT and M-NO-INSTRUMENT-FAST are unchanged for a reader
that really waited. The window keeps its single OK, which ends the session
the standard way.*

> **No Instrument Connected**
>
> ChromIQ cannot find a measuring instrument connected to this computer, so the measurement has not started.
>
> Connect your instrument with its USB cable, give the computer a moment to recognise it, and press Start again.
>
> Nothing has been lost: any measurement you already had is kept exactly as it was.

### M-CAL-REPLACE-CHART · replacing a calibration chart nobody measured — Create Chart, Run type = Calibration

**Approved by:** Basti, 2026-09-02, together with M-CAL-REPLACE-MEASURED and
M-CAL-ARCHIVED-HERE, as one approval.

**Why it was rewritten.** It used to say *"Nothing is deleted: the chart you
have now moves to the project's “cal/old” folder … and you can go back to it at
any time."* On 2026-09-02 Basti was given three options for what should happen
to a replaced calibration chart and chose **option 3** — *"Keep it only if it
was measured; experiments leave nothing"* — against a recommendation to keep the
last one. That made the old sentence false, so the behaviour and this text
landed together. Two strict `xfail`s held the branch shut in between, rather
than let the window promise something the code no longer did.

Shown when `cal/` holds a chart and `Calibration.exists()` is false — no `.ti3`
and no `.cal`. That is narrower than what the code keeps
(`Calibration.result_files()`, which also counts an `.icc` and a
`.ti3.engine-partial`), and the direction is deliberate: this window can say
"not kept" over a calibration that is in fact kept, and can never say "kept"
over one that is dropped.

> **Replace this project's calibration chart?**
>
> *(bold first line)* You already made a calibration chart for this project, but it has not been measured yet.
>
> Generating a new one replaces it, and the chart you have now is not kept. Nothing has been measured from it, so ChromIQ treats it as an attempt rather than as work to go back to. This is what a profile run does with a chart you have not measured.
>
> Once a calibration has been measured it is never replaced this way: the measurement, the calibration file made from it and the chart that produced them all move to the project's “cal/old” folder, and nothing is deleted.
>
> If you want to keep this chart, press Cancel and copy the “cal” folder somewhere else first.
>
> **Buttons:** *Replace the chart* · *Cancel*

### M-CAL-REPLACE-MEASURED · replacing a finished calibration — Create Chart, Run type = Calibration

**Approved by:** Basti, 2026-09-02. **The wording is unchanged** — it was
drafted at `docs/design/calibration_run_type_plan.md:240` and option 3 did not
touch the measured branch. What changed is where it lives: the window is
governed in one place now instead of half of it, so a future edit to one branch
cannot quietly leave the other saying something else.

Shown when `Calibration.exists()` — a `.ti3` or a `.cal` is there.

> **Replace this project's calibration?**
>
> *(bold first line)* This project already has a finished calibration, and generating a new chart starts that work again from the beginning.
>
> You would need to print the new chart and measure it before this project has a calibration once more.
>
> These move to the project's “cal/old” folder, in a folder named with today's date — nothing is deleted, and you can go back to them at any time:
>   •  the calibration chart
>   •  its measurement
>   •  the calibration file (.cal) made from it
> {runs_line}
>
> **Buttons:** *Replace the calibration* · *Cancel*

`{runs_line}` — real singular and plural, never "(s)"; omitted entirely when no
run recorded this calibration, because absent means unknown:

> • one run → "Run 3 was built using this calibration. It is not changed, and its profile keeps working, but it was made with the calibration you are about to replace."
> • more → "Runs 3, 5 and 6 were built using this calibration. They are not changed, and their profiles keep working, but they were made with the calibration you are about to replace."

### M-CAL-ARCHIVED-HERE · where a replaced calibration went — the Create Chart log

**Approved by:** Basti, 2026-09-02.

Not a window: two lines written into the log the build is already streaming
into, because that is where a person is looking when it happens.
`Calibration.reset()` returned the archive folder and every caller discarded it,
so M-CAL-REPLACE-MEASURED promised "a folder named with today's date" and the
app then named it nowhere — true and unfindable. Found by the adversarial round
of 2026-09-02.

Shown only when an archive was really made. An unmeasured chart is dropped, so
there is no folder to name and nothing is said.

> **The calibration that was here has moved to this folder, and nothing in it was deleted:**
>
> {folder}

### M-IMPORT-NOT-OPENED · the copy is filed and ChromIQ is not in the project — the import door

*Approved by Basti, 2026-09-02. New for 4.1.5, round 2 of the import-door review (2026-09-02, findings T1-A,
T1-B and T1-C). The new-project door has three ways to end with the measurement
copied to disk and the app still standing outside the project it was copied
into: no `project.json` above the copy, an open that was attempted and failed
(a truncated manifest, which `save_manifest` writes non-atomically, so it is an
ordinary accident), and no Create Chart tab to perform the open with. All three
ended in a `log.warning`, no window, and a bar that said "Load a profile
project" about a project ChromIQ had just made — the exact fault the door was
rewritten to remove. The person is told the one thing they cannot work out for
themselves: where the file is.*

> **The measurement is filed, but the project could not be opened**
>
> Nothing has been lost. Your own file is untouched where it is, and the copy ChromIQ made is here:
>
> {folder}
>
> ChromIQ could not open that project afterwards, so it is not the project you are working in, and the bar at the top still shows the one you were on.
>
> The reason: {reason}.
>
> That folder is an ordinary folder. Everything ChromIQ put in it, including the measurement you have just imported, is there and can be opened like any other folder on your computer. Once the reason above is dealt with, use “Open Project” at the top left of the window to go there.

`{reason}` is one of three, and each is written out here because the reviewer
sees the sentence, not the code:

* *there is no project.json in that folder or above it, so ChromIQ has nothing to open*
* *the project could not be read ({error})*
* *the Create Chart tab, which performs the Open Project step, is not open*

### M-IMPORT-FOLDER-EXISTS · the typed name is a folder and not a project — the import door

*Approved by Basti, 2026-09-02. New for 4.1.5, round 2 (finding T1-D). The window decided "already a project"
from the folder merely existing, so the one window the door still opens for a
plain folder arrived asserting, in red, that the folder is a project — about
the folder whose NOT being one is the only reason that window opens at all.
The consequence and the vocabulary follow M-IMPORT-REPLACE-CONFIRM, which Basti
ruled on for the project case on 2026-08-31; only the claim about what is there
differs, because what is there is different.*

> **There is already a folder called “{name}”**
>
> ChromIQ found it here:
>
> {folder}
>
> It is not a ChromIQ project: there is no project.json in it. Nothing has been changed yet.
>
> •  Type a different name, and ChromIQ starts a new project under that name instead. Nothing in the folder above is touched.
>
> •  Replace it: everything in that folder is moved into its own “old” folder, with today’s date on it, and a new and empty project of the same name is started in its place, with what you are importing in its first run. Nothing is deleted, and ChromIQ asks you to confirm before it does it.
>
> •  Cancel: stops here and changes nothing.

The form this takes on screen today is the live line under the name box, which
is a fragment of the message above and the twin of the sentence shown when the
name really is a project:

* *“{name}” is a folder you already have, and it is not a ChromIQ project. Choose a different name, or click “Replace it”.*

### M-IMPORT-REPLACE-FOLDER-CONFIRM · the second look before a plain folder is moved aside — the import door

*Approved by Basti, 2026-09-02. New for 4.1.5, round 2 (finding T1-D). The twin of M-IMPORT-REPLACE-CONFIRM
for a folder that is not a project: the same act, the same promise, and no
claim that what is being moved aside is a project.*

> **Move everything in “{name}” aside?**
>
> That folder is not a ChromIQ project, and everything in it is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays where the files were, so you can open it at any time and take anything back out of it.
>
> After that, a new and completely empty ChromIQ project of the same name is started in the same place, and {subject} you are importing is put into its first run.

### M-IMPORT-REPLACE-FOLDER-FAILED · that move could not be made — the import door

*Approved by Basti, 2026-09-02. New for 4.1.5, round 2 (finding T1-D). The twin of M-PROJECT-REPLACE-FAILED,
which said “The existing project could not be moved aside” about a plain
folder — driven against a read-only folder that held one text file.*

> **That folder could not be moved aside**
>
> ChromIQ was going to move everything in this folder into its own “old” folder before starting a project of the same name in its place, and it could not:
>
> {folder}
>
> Nothing has been changed. Anything that had already been moved has been put back, and nothing has been imported.
>
> The reason given was:
> {reason}
>
> This usually means the folder is read-only, is on a disk or a share that is no longer available, or holds a file another program still has open. Close anything that might be using it and try again, or type a different name and leave that folder alone.

### M-SCAN-ALIGN-AMBIGUOUS · Auto align cannot tell which way up the sheet is — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. Auto align hands the scan to
ArgyllCMS's own chart recogniser, scores the answer against this chart's
reference, and either places the grid on it or changes nothing. It refuses for
six distinct reasons, and the module names them the way a program wants them
named — `ambiguous-orientation`, `below-floor`, `not-recognised`,
`no-usable-candidate`, `no-chart-geometry`, `no-better`. Those names belong in
the log file and in the tests. The first implementation printed them in
brackets in the middle of the sentence the user reads, which is what these six
messages replace.*

*All six open with the same line, because after a refusal the first thing the
user needs to know is that they have lost nothing: the four corners they placed
by hand are exactly where they left them, and the button was safe to press.*

*This one: a rectangle of patches maps onto itself when it is turned, so more
than one orientation scores the same and picking one of them at random would
read every patch as another patch and build a confidently wrong profile.*

> **Auto align left your corners exactly where they are**
>
> This chart's patches look the same whichever way round it is turned, so ChromIQ cannot work out which way your scan was made. If you know it needs turning, use the “⟳ Rotate 90°” button below the preview. Otherwise drag the four corners onto the chart yourself, which always works.

### M-SCAN-ALIGN-NO-MATCH · what Auto align found does not agree with the reference — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. The recogniser found a chart and
the placement scored below the agreement floor of 0.80, which is the same
question M-SCAN-REF-DISAGREES asks of a finished read, asked before anything is
moved.*

*`{ref_row}` is the row on screen that holds this chart's known colours, and
there are three of them: “Target reference data” for a standard target, and the
chart picker for a ChromIQ chart — “Measured chart (.ti3)”, or “Chart you
printed (.ti2)” in printer mode. The window fills it in from the label it is
actually showing, so the message never names a row that is hidden.*

> **Auto align left your corners exactly where they are**
>
> It found the chart, but what your scan shows does not match the reference closely enough to rely on. That usually means the reference file belongs to a different target, or the scan is of a different chart. Check the file in the “{ref_row}” row above and try again.

### M-SCAN-ALIGN-NOT-FOUND · Auto align found nothing chart-like at all — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. The recogniser returned no
candidate placement of any kind. The advice is not a formality: when the user's
own quad covers less than 70 % of the image, Auto align re-runs the same
recogniser inside it, so drawing the corners roughly round the chart really is
what makes a cluttered photograph work.*

> **Auto align left your corners exactly where they are**
>
> ChromIQ could not find this chart anywhere in the picture. That usually happens when the picture shows a lot more than the chart, or when one edge of the chart is missing. Drag the four corners roughly around the chart and press Auto align again: it will then search only inside them.

### M-SCAN-ALIGN-NO-FIT · something was found, and this chart does not fit it — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. The distinction from the message
above is a real one and not a shade of the same thing: there, nothing
chart-shaped was found; here, candidates came back and every one of them was
rejected — the quad was not a plausible sheet, its values could not be
measured, or its outer edges are not this chart's edges. The usual cause is a
target chosen that is not the one on the glass.*

*`{chart_row}` is “Target type” for a standard target, and the chart picker for
a ChromIQ chart, filled in the same way as `{ref_row}` above.*

> **Auto align left your corners exactly where they are**
>
> ChromIQ found something chart-shaped in the picture, but no way of fitting this target's patches onto it. Check that the chart chosen in the “{chart_row}” row above is the one you actually scanned.

### M-SCAN-ALIGN-NO-GEOMETRY · the chart definition records no patch positions — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. Auto align works from the patch
boxes in the `.cht`; without them there is nothing to fit. Nothing else in the
window depends on it, and the message says so, because a user who has just been
told a feature cannot work needs to know how far the trouble reaches.*

> **Auto align left your corners exactly where they are**
>
> The chart definition for this target does not record where its patches sit, and that is what Auto align needs to work. Place the four corners yourself; everything else in this window works normally.

### M-SCAN-ALIGN-DONE · Auto align moved the corners — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. `{rho}` is the agreement between
what the placed grid reads and this chart's reference, to two decimals, on the
same scale as M-SCAN-REF-DISAGREES. The number is given a scale in the sentence
rather than left bare, and the message points at the pre-build check rather than
inviting a build.*

> **Auto align put the grid on the patches**
>
> What the grid reads now agrees with this chart's own reference to {rho}, on a scale where 1.00 is a perfect match and anything below 0.80 is refused. Press “Check alignment” below to look at the read before you build anything. Nothing else has changed, and you can still drag any corner by hand.

### M-SCAN-ALIGN-NO-INPUT · Auto align pressed before there is anything to align — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5.*

> **Auto align has nothing to look at yet**
>
> Load a scan for this page and choose the chart it was made from, then press Auto align again.

### M-REPORT-NOT-SAVED · the dated report after a measurement could not be written — Measure

*New message (#182 spin-off, 2026-09-04). "Save measurement report" is on by
default, and after every measurement ChromIQ builds a dated accuracy report and
writes it into the run's `reports/` folder, so a printer's reports accrue and
can be trended. When that failed, `_maybe_save_measurement_report` sent the
exception to `log.warning` and appended NOTHING to the screen.*

*The silence was worse than an omission, because the SUCCESS is announced: a
good run prints "[Report] Measurement report saved: …" into the measurement log.
So a failure did not merely fail to inform — the window that had just written no
report was indistinguishable from the window that had, and the only evidence
lived in a log file the user never opens.*

*It is the log and the status line, not a window.* This is the shape
`_on_cr30_dropped_reading` already uses in the same tab, and the reason Basti
gave for wanting a pop-up on M-CR30-READ-FAILED — *"instead of ruining a whole
measurement session when this is unnoticed"* — does not reach here. There the
session stalls with the instrument waiting. Here the measurement is over and
safe: the `.ti3` is the record, the report is derived from it, and the
**Measurement report** button rebuilds it on demand. Nothing is interrupted,
nothing is lost, and there is nothing to do at that instant — so a modal after
every failed report would cost more than it says.

*The message carries NO placeholder and no exception text, and that is
deliberate.* Basti's standing rule for user-facing text is *"friendly,
extensive, easy to understand and correct"*, and an errno with a path in it
fails three of those four: it blames, it is not plain language, and — because
the same `except` catches a failure to BUILD the report and a failure to WRITE
it — a sentence built around it would state a cause nobody has established. So
the message says what happened, what it costs and what to do, names the usual
reasons as things to check rather than as a diagnosis, and points at the
technical line that follows it in the log. That line is
`[Report] Technical detail: <class>: <message>`, and it is not part of §M — it
is a log line, not an explanation.

*The first paragraph is the most valuable one in the message.* A user who reads
"the report failed" and concludes their measurement is gone has been badly
served by a technically accurate sentence, so the message opens by saying what
was NOT lost, before it says what was.

> **The measurement report could not be created**
>
> Your measurement is safe. It was read, checked and written to disk exactly as it always is, and nothing about it has changed. This is only the dated accuracy report ChromIQ normally saves beside it, and nothing in your chart, your measurement or your profile depends on that report.
>
> What did not happen: ChromIQ was not able to work out and save this measurement's report just now, so there is no new dated entry for it in the run's reports folder.
>
> You do not need to measure anything again. The report is worked out from the measurement file itself, so you can open it whenever you like with the Measurement report button, and save it from there.
>
> If you would like to look into it, the technical detail is on the line below this message and in ChromIQ's log file. The usual reasons are a run folder that has been moved, renamed or deleted since the measurement began, a disk with no room left on it, or a folder ChromIQ is not allowed to write into. If this keeps happening and you would rather not be asked about it, you can switch the automatic report off in Preferences, under Reports.

**Confirmed by:** Basti, 2026-09-04 — *"i approve it"*, on the wording as
written, after reading it in full.

### M-VERIFY-NO-CONTROL-STRIP · APPROVED · the verification chart cannot carry a control strip — Create Chart

**Approved by:** Knut, 2026-09-19, asked directly and answered *"Yes, message
text approved."*

*New for 4.3.0-beta.22 (#182). ChromIQ now writes a control-strip declaration
beside every verification chart it creates, which is what makes the three
control-strip rows of the Measurement Report computable at all; a chart whose
patches cannot fill eight rungs of the ladder gets none. Knut asked for that to
be said out loud: "notify the user if a selected/loaded/created chart (from
loading a preset or otherwise, in the verifications/ folder for a run) does not
fulfil the requirements to be able to create the control-strip declaration
(either when pressing Generate Chart, or when loading a preset, or the other
usual paths to create a chart while 'run type' = Verification). The warning must
specify what is required when selecting a chart for the control-strip
declaration to be created, and also refer to the button function in Create Chart
mentioned above for help in selecting a compatible chart." Modal, one button,
shown after the chart has been built and filed; the chart is untouched and
printable. `{n}` is how many of the 29 rungs the chart filled. `{button}` is the
Create Chart control that lists which patch sets can carry a strip; it is a
placeholder rather than a literal because that control is being built alongside
this message, and its name is settled in one place
(`workflow/control_strip.ELIGIBILITY_CONTROL`).*

> **This chart cannot carry a control strip**
>
> ChromIQ has saved it as this run's verification chart and it is ready to print. What it cannot do is carry a control strip, so the three control-strip rows of the Measurement Report will read “this chart declares no control strip” for every measurement made on it.
>
> A control strip is the short run of patches a print is checked on, and ChromIQ builds one out of the chart's own patches: the bare paper, the composite black, the cyan, magenta and yellow solids, the red, green and blue overprints, a 25 %, 50 % and 75 % step of each of those six colours, and a 25 %, 50 % and 75 % neutral grey. That is 29 patches in all, and a patch of your chart counts for one of them when its red, green and blue values are each within 12 units of it.
>
> This chart supplied {n} of the 29. At least 8 are needed before the average and the largest patch can be reported, and 20 before the 95th percentile can.
>
> What to do: build the verification chart from a patch set with more patches, or one spread more evenly over the colour cube. “{button}” on this tab lists every chart preset against the rows a Measurement Report judges, so you can choose a patch set that answers more of them.
>
> Nothing is wrong with the chart itself and nothing has been changed. Every other row of the Measurement Report is unaffected.

### M-REPORT-DELETE · APPROVED · one generated report is about to leave the list — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C3 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New for #182, 2026-09-16. The design authority asked for it before a non-beta
release: "the selection and deletion of reports with a selector input box is
needed and should be made first". Nothing in this model governs removing a
report, and §5 of `measurement_report_limits.md` governs only the
archive-then-recalculate rule, which is about rewriting one. Shown by the
Measurement Report window's "Delete Selected Report" button, before anything is
moved; Cancel is the default.*

*REVISED 2026-09-18, and the revision is what the button does. Knut's L.7
(§13 of `measurement_report_limits.md`) says the files are MOVED: "which then
creates a dated report folder in the old/ folder where the files for that
report is moved to." The wording it replaces described deleting one file and
ended "ChromIQ cannot undo this", which was true of the old button and is false
of this one. An entry in the list is also one DOCUMENT now (B8-383), which may
be one file per measurement it covers, so the count is of files rather than of
what is left behind. Neither wording has been approved. `{what}` names the
report the way the list names it; `{n}` is how many files it is made of;
`{where}` is the folder they are moved to, which L.7 decides from what the
report spans.*

*The one refusal is not a window: the only saved report of a DATED
VERIFICATION cannot be deleted, because that verdict is the record §5 keeps
comparable across dates, so the button is disabled and a line beside it says
so. That rule waits for approval with the wording.*

*REVISED 2026-09-23 for Knut's K25 answer (#182 comment 5789263863, Q5). Since
K23 a report of several measurements is ONE document file, so the one-file
body said "the measurement it describes" about a report of several dates.
`{n}` counts files, not measurements, and cannot choose the word, so both
bodies now use his own: "You could say 'the measurement(s) it describes', to
make it simple." The one-file body is the same text with "Its file is moved
here" and "The file stays". Still unapproved as a whole.*

> **Delete this report from the list?**
>
> This report is taken out of the list of generated reports:
>
> {what}
>
> Its {n} files are moved here:
>
> {where}
>
> Nothing is destroyed. The files stay on your disk in that folder, and the measurement(s) it describes are not touched.

### M-REPORT-UPDATE-NOT-FOUND · APPROVED · Update of a report that covers a measurement nobody can find — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C6 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New 2026-09-23, challenge C of beta 39 (#1). Update rewrites a report about
every measurement it covers (`measurement_report_limits.md` §13.13). Opened
from the side that could not find one of them (the other project renamed or
moved away), it archived the whole report into `old/` and rewrote it about the
one date it had found; the renamed side then listed nothing. No rule lets an
Update drop a covered measurement it cannot find, so the press is refused
before anything is written, and the window says which and why. Button:
**OK**. `{missing}` is one line per measurement, in the form below.*

> **This report cannot be updated from here**
>
> The selected report covers measurements that ChromIQ cannot find:
>
> {missing}
>
> Updating it now would rewrite the report without them, so nothing was changed. Put the project back in the folder beside this one, or open the report from a project that can reach them, and try again. “Create New” writes a new report of what is ticked and leaves this one as it is.

Each line of `{missing}` (`measurement_messages.report_gone_line`) is one of

> •  {project}, run {run}, {when}: {why}

> •  {project}, calibration, {when}: {why}

and `{why}` is one of

> ChromIQ cannot find this project

> its profile run was deleted

> its folder is no longer in the project

> its measurement file is no longer in its folder

### M-REPORT-UPDATE-LEAVES-OUT · APPROVED · Update of a report some of whose measurements are no longer on disk — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C7 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New 2026-09-23, challenge C of beta 39 (#11). §13.11 of
`measurement_report_limits.md` leaves out a folder that no longer holds its
measurement. The Update did that in silence, and a date whose `.ti3` had been
deleted was enough to retire a report across projects into a one-date report.
Shown instead of writing, when every measurement the Update would lose is in a
project it can see (its run deleted, its dated folder gone, or its
measurement file gone). Buttons: **Update without them** and **Cancel**
(default). `{missing}` as for M-REPORT-UPDATE-NOT-FOUND.*

> **Some measurements of this report are no longer on disk**
>
> The selected report covers measurements that are no longer on disk:
>
> {missing}
>
> Updating it now leaves them out, and the report then covers only what is still there. The report as it is now is kept in the old folder first.
>
> What do you want to do?

### M-REPORT-ONE-PAGE-ONE-DATE · APPROVED · Generate report, with several measurements ticked on a one-page type — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C8 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New for #182, 2026-09-20 (B8-591). Shown by "Generate report" when the report
type is "Colour summary (one page)" and MORE THAN ONE measurement is ticked in
"Included Measurements in report". The press is abandoned: nothing is written,
and **no tick is moved**. `{count}` is how many are ticked.*

*This message exists because of what it replaces. Knut reported the silent
correction from both ends in his beta 29 review:*

> *"Selecting report type 'Grey and tone check' with 'Show all...' OFF and many
> measurements included (ticked), the generate report. This unselected all but
> the last measurement without a warning."*

*and, a paragraph later:*

> *"If I try this again, but now only with one measurement ticked, the
> measurement I had ticked was unticked and the last measurement in the list
> was automatically ticked (I did not ask for that). This is also wrong."*

*He gave the rule for what should happen instead, and it is the shape of this
window:*

> *"Upon generate report clicked, the user should be informed that several
> measurements have been ticked as to be included … Then the user must be
> instructed to select which measurement to include in the report (since
> several are ticked) … Then the user can close that message and do the
> changes, and then click generate report again."*

*Most of that paragraph was about the conflict between the ticks and "Show all
measurement runs", and that checkbox is gone with the feature behind it
(B8-590), so those conflicts are gone with it. **One survives the removal**,
because it is a property of the report type and not of the box, and he named
it separately in the same comment: "color summary only allows one measurement
date ticked, and if several is selected, user must be informed as mentioned
above, and make a choice which to include."*

*It informs; it does not choose. One button, and the user goes back to a list
that still holds exactly the ticks they put there. The alternative shape, a
question offering to keep the newest, was not built: correcting the ticks is
the thing he objected to, and offering to do it for him is the same act with a
button on it.*

> **A colour summary is one page about one measurement**
>
> {count} measurements are ticked in “Included Measurements in report”, and this report type has room for one.
>
> Close this, untick the measurements you do not want on the page, and click “Generate report” again. “Deselect all” clears them all if that is quicker. To keep every measurement you have ticked, choose another report type instead.

### M-REPORT-CHART-MISMATCH · APPROVED · the chart cannot supply a row the limit set limits — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C9 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New for #182 (Knut, D25, 2026-09-06: "a strip inside the report window, below
the selection of the Compliance set chosen, and in the report text"). Shown in
the Measurement Report window under the "Judged against" row whenever the
measured chart cannot supply one or more rows the run's limit set puts a limit
on, and repeated as a note under Report Results. Hidden, not blank, when there
is nothing to say. `{set}` is the limit set's label; `{rows}` is one line per
row, "• <row>: <reason>", the reasons being the row's own N-A sentence (too few
grey steps, no tone ramp, needs a reference file, fewer than 20 patches).*

> **Some limits cannot be checked on this chart**
>
> The limit set {set} puts a limit on values this chart cannot supply, so these rows read N-A (not applicable):
> {rows}
>
> A row that was not computed says nothing about the printer. Each reason above names what that row needs: most want patches added to the chart in Create Chart (for the grey balance: “Neutral grey ramp” with 16 steps), and the control strip wants the chart to declare one. Make the change, print the chart again and measure it.

*REVISED 2026-09-18, B8-397. The closing sentence named ONE remedy for every
reason, which was true while every reason meant "the chart is missing patches".
The three control-strip rows are missing a DECLARATION, not patches: Knut
approved S2w that day and a chart now says for itself which of its patches make
up a strip. Photographed on screen, the window listed "Control-strip patches,
average (… Declare a longer strip, or add its patches to the chart)" and then
closed with "add the missing patches to the chart in Create Chart to have it
checked", contradicting the line above it. Each reason carries its own lever
now, so the closing sentence points at them.*

*REVISED 2026-09-23 (challenge rounds A and B before beta 37, A-F3, B-H2 and
B-M7). The strip no longer names a row withheld for the MEASUREMENT's noise
(the two evenness rows' noise rule): the sheet's readings scattered, and nothing
added to the chart answers that. The row still reads N-A with its own note. When
every row the strip lists is an evenness row, the closing sentence above is
replaced by M-REPORT-CHART-MISMATCH-LAYOUT's.*

### M-REPORT-CHART-MISMATCH-LAYOUT · APPROVED · only the evenness rows cannot be checked on this chart — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C10 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New 2026-09-23, round B before beta 37, M7. The strip above, when every row it
lists is one of the two evenness rows. Under a list holding only those, the
general closing sent the reader to add patches in Create Chart "(for the grey
balance: “Neutral grey ramp” with 16 steps)". Evenness is judged over nine areas
of one page, so what those rows lack is strips and rows on a page. Same headline,
same `{set}` and `{rows}`.*

*Revised 2026-09-23 for beta 38 (#182 E2): a page whose patches cover less than
75 % of the paper is now left out as well (Knut, 5789263863, approved in
5789539407), so the closing names that too. Still PROPOSED.*

> **Some limits cannot be checked on this chart**
>
> The limit set {set} puts a limit on values this chart cannot supply, so these rows read N-A (not applicable):
> {rows}
>
> A row that was not computed says nothing about the printer. Evenness is judged over nine areas of one page, so these rows want a chart laid out with more strips and more rows on a page, and with patches that cover most of the page. Make the change, print the chart again and measure it.

### M-REPORT-PATCH-COUNTS-DIFFER · APPROVED · one report, sheets holding different numbers of readings — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C11 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New for 4.3.0-beta.35 (#182). Knut, 2026-09-22: where the selected
measurements come from charts with different patch counts, the report carries a
plain warning that judged metrics may differ slightly for that reason, and that
it shows in the trend graphs. **Not an error**, and it must not be painted as
one: it is printed in the report's own note style and not in the red Report
Scope warning block.*

*It says **readings**, not "charts", because readings are what is counted.
`report_scope` reads `r["patches"]`, which is `data.n_patches`: the number of
readings in the `.ti3`. An adversary round drove the difference on one
variable, twelve measurements of ONE chart: read in full, the note stayed
silent; the same read ended early at 168 of 210 patches, and the report printed
"taken from charts with different numbers of patches (210, 167)" directly under
a Report Scope block naming one chart and twelve runs. Ending a measurement
early is a supported ending, so that is not an exotic state. Saying "readings"
makes the sentence true in both cases, and the second paragraph names both
causes, so the note stays useful exactly where it was lying.*

*`{counts}` is filled with the distinct reading counts of the sheets in the
report, in the order the columns appear.*

> **These measurements do not all hold the same number of readings**
>
> The sheets in this report do not all carry the same number of measured patches ({counts}). Every metric is worked out over the patches a sheet actually holds, so a figure taken over more of them is not measured over quite the same set of colours as the same figure taken over fewer, and the two can differ a little for that reason alone. It shows in the trend graphs as well as in the table.
>
> That can be because the charts differ, or because a measurement was ended before its last strip. Either way it is not a fault and nothing here is wrong, but a small change between such sheets is not necessarily a change in the printer.

*REVISED 2026-09-23 (round B before beta 37, H4): the closing sentence spoke to the reader ("before you read"), and Knut's K18 rule is that report text may go to a customer and gives no user tips. It now states what the difference means.*

### M-VERIFY-PREFLIGHT · APPROVED · what this chart can verify, before anything is measured — Measure tab

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C12 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New for 4.3.0-beta.30 (#182). Knut, 2026-09-21: "I see that there is one
popup-message that is missing, that would help a user in the process of
verification." Shown on entering the Measure tab when four conditions hold
together, and on no other occasion: Run type is Verification; a chart with a
patch set exists, by any route at all ("Either made manually, or imported as ti2
file, or loaded a preset etc. Whatever method that was used is not relevant");
no measurement has been taken (no `.ti3`, or one that is empty or invalid, by
the same test Start Measurement applies); and no measurement has been started.
Entering the tab means EITHER clicking it OR switching "Profile run" to such a
run while already standing on it. One OK button, Escape closes it, and a tick
that silences it for that profile run until ChromIQ is restarted, held in memory
only and never written to the project.*

*⏳ **A fifth condition, awaiting confirmation (2026-09-22, B8-776).** Knut, on
beta 32: "It does not have value to show this when measurements have been
performed, and especially when many dated verification runs already exist". So
the window is also withheld once ANY dated verification of the selected profile
run carries readings (by the same empty-or-invalid test), even when the date
now selected is new and empty. Beta 34 shipped this rule and it never took
effect (B8-776); it does from beta 36. Two edges are his to rule on: a dated
folder holding only `reads/readN.ti3` (averaging stopped after one read) does
not count as measured, and neither does a measurement Replace has moved to
`verifications/old/`, so in both cases the window opens again.*
**Confirmed by:** *nobody yet.*

*The metric list is not in this text. It is built for the chart in front of the
reader by the same code the "Which presets can be used for verification" window
puts in its right-hand pane, in the short form Knut asked for: "A summary of
that info shall be shown in the pop-up message, so that the text does not become
too long." The FROM PROFILE GAMUT paragraph below is appended only when a metric
is missing that nothing else can supply.*

*He asked for this wording to be drafted and shipped so that he can review it as
a working example, so it appears in the window while it waits for approval, under
the log-rule amendment at the end of this section.*

> **Before you measure this verification chart**
>
> This run is a verification, so what you read here will be judged by the Measurement Report: a table of metrics, each with a limit, saying whether the print is inside it.
>
> Not every chart can answer every metric. Which ones this chart can is listed below, worked out from its patch set before anything is printed, so you can still change the chart. A metric the chart cannot supply is not judged and nothing else is affected, so falling short does not make the chart wrong.
>
> To compare patch sets before you settle on one, open “Which presets can be used for verification” under the preset pulldown in Create Chart. It judges every preset ChromIQ ships and every one of your own against these same metrics, and its first line is the chart you have now.
>
> For the verification workflow end to end, see the help card “Check a finished profile (verification run)” behind the question mark at the top right of the window.

And, when and only when a metric is missing that nothing but FROM PROFILE GAMUT
can supply:

> Some of the metrics listed above can be answered by a verification in only one way: its solid patches must be printed as they are, and a chart printed through its profile converts them. A chart built with FROM PROFILE GAMUT in the Create Chart tab prints them as they are.
>
> That button sits beside GUIDED and MANUAL whenever Run type is Verification. Before it can choose any colours the run must already hold a built profile, and it lays the sheet out again from scratch.

**Revision accepted by:** Knut, 2026-09-26, #182 [5848287278](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5848287278), on the first paragraph above, proposed to him as B8-1374: *"The paragraph in the check before measuring that says the solid metrics are "judged against a colorimetric reference". Suggested: [the paragraph above] Answer: Accepted."* It read *"Some of the metrics listed above can be met in only one way: they are judged against a colorimetric reference, and ChromIQ writes one only beside a chart built with FROM PROFILE GAMUT in the Create Chart tab."*, which K49 and K51 made untrue: the two solid rows are compared with the profile's prediction, and a raw print answers them. The second paragraph is the one approved in 5816565326, as the code has carried it since beta 32 (770908d6 dropped the clause "so a preset that arrives as finished page images cannot be converted", which this document still quoted).

*Knut wrote of that feature's own conditions: "not sure about all the required
conditions for 'From Profile Gamut' feature to be visible?". They were measured
for B8-613 and the paragraph above says what they are; the measurement is
recorded in the register and awaits his confirmation, like everything else here.*

### M-LIMIT-RECOMMENDED · APPROVED · the note a bracketed limit points at — Report limits window and report text

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C14 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New message (2026-09-21), and the second half of Knut's ruling that retired
COND as a row word. He asked for the note in the same message as the retirement:
"there should be a note associated with the metric its self, like a reference
number at the end of the metric label-name, pointing to a note below the table
in the Report Limits window (and in the report text also a number on the metric
name, pointing to a note in the report text)."*

*One text, rendered in both places. In the Report limits window the marker sits
at the end of the metric label and the note is listed below the table; in a
report the marker sits on the verdict cell and the note joins the existing
numbered note list under the results table, which is the machinery Knut asked
for on 2026-09-13 and is reused here rather than duplicated.*

*The body is deliberately silent about the Overall word.* His first version of
this note ended *"but does not affect the overall result of the ISO 12647
verification"*, and he withdrew it nine minutes later: *"I recommend that all
thresholds tested against are treated the same, so there is no need to have
special handling of the results of a metric with 'should' … If the test is
applied the report shall show the result as is, and the overall result follows
as normal."* A sentence excusing a recommended row from the Overall would now
be false of the code as well as against the ruling.

*After the same ruling's point 5, no ChromIQ set marks any row a recommendation,
so this note appears only where a licence holder has written `[number,
"should"]` into their own ISO values file, or where a user has marked a row that
way in one of the two editable Custom columns.*

> **The standard recommends this metric rather than requiring it**
>
> The standard calls this metric recommended rather than required, so it may be applied optionally. Its limit is shown in brackets. It was applied here, and the result is reported the same way as every other row.

### M-PROJECT-FOLDER-RENAMED · APPROVED · a project opened from a folder not named what its files carry — Create Chart

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C16 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New 2026-09-23, #182 K26. Knut, 5792484060 (Q5): "If a project is opened where
the root project folder is different than the defined name in 'Printer profile
project name' field, then the user should be given the option, with a popup
window, to rename the project. This interface and function should already
exist and just has to be modified a tiny bit to allow this case." The window is
the rename chooser Create Chart already shows when the name field is changed
(`TargetChangeDialog`), in a second mode; this is its heading and introduction.
Shown by Open (the masthead's Load, and every door that opens a project the same
way) when `project.json`'s name is not the folder's name, before anything of the
project is displayed. `{folder}` is the folder as it is on disk, `{name}` the
name the files carry, `{new}` what the project becomes: the name the "Printer
profile project name" field shows.*

*Revised 2026-09-23, Knut 5794078008: the window must NOT offer "Leave it as
it is". It offers exactly three choices, each explained in a bullet in the
window text, as is customary for popups: rename the project to the project
folder's name; define a new name (the existing project-name window, then the
same rename); Cancel, which closes the project. A project with a built profile
is still offered the rename ("Yes", same comment). `{built}` is empty, or a
space and the sentence given below it when a run of the project has a built
profile.*

> **This project's folder is called “{folder}”, but its files are named “{name}”**
>
> ChromIQ finds a project's charts, measurements, profiles and reports by the name of its folder, so until the two match it finds none of them. This happens when a project folder is copied, duplicated or renamed outside ChromIQ.
>
> •  Rename the project to “{new}”: every file that carries the name “{name}” is renamed to carry “{new}”, and the folder too when its name has a space or a character a file name cannot carry. Nothing is deleted.{built}
>
> •  Choose another name: you type the name the project is to have, and its folder and files are renamed to it in the same way.
>
> •  Cancel: nothing is changed, and the project is closed.

`{built}`:

> A profile already built keeps the name written inside it, “{name}”, which is what ColorSync Utility and other programs show.

Buttons, in one row: **Cancel** · **Choose another name…** · **Rename the
project to “{new}”** (default). Cancel, Escape and the window's close button
close the project: the app goes back to the state Close Project leaves.
Keep both and Delete are not offered: there is one folder, and it is the
project.

"Choose another name…" opens the existing project-name window (“Give this
project a name”), prefilled with “{new}”, with this line in place of its usual
one; cancelling it returns to the three choices:

> Type the name this project is to have. Its folder, and every file that carries the name “{name}”, are renamed to it.

### M-PROJECT-FOLDER-RENAME-FAILED · APPROVED · the rename of such a project could not be done — Create Chart

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C17 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*New 2026-09-23, #182 K26, with the message above. Shown when the rename the
user chose fails (the new folder name is already taken, the folder cannot be
written). Nothing further runs; the project stays open as it was.*

*Revised 2026-09-23, the beta 38 challenge round (F1, F6). The first wording
named the rename "{folder}" to "{new}", which for a folder renamed only in
case printed one name twice, and `{error}` was the exception's text, which for
the commonest cause (the name is taken) was a bare path. It now names the
project by the name its files carry, and `{error}` is one of the sentences
below. "Nothing was changed" is now also true in every case: a rename is
refused before anything moves when it cannot finish, and a step that fails
anyway is undone (`Project.rename`, `FileManager.rename_existing_project`).*

> **The project could not be renamed**
>
> ChromIQ could not rename the project “{name}” to “{new}”.
>
> What went wrong: {error}
>
> Nothing was changed, and the project is open as it was. Its files still carry the name “{name}”, so ChromIQ does not find them in the folder “{folder}”.

Button: **OK**.

`{error}` is exactly one of (`measurement_messages.rename_failure_reason`,
`core.file_manager.ProjectRenameRefused`):

> A folder called “{name}” is already there, beside this one.

> ChromIQ is not allowed to change this folder or the files in it.

> A file of the project was no longer where ChromIQ expected it.

> The system refused it ({reason}).

> Two of its files would both be called “{name}” after the rename.

> ChromIQ is not allowed to change the files in the folder “{folder}”.

> A file called “{name}” is already there and could not be moved out of the way.

### M-IMPORT-NOT-A-CHART · APPROVED · the file picked as a chart has no chart in it

**Approved by:** Knut, 2026-09-24, #182 [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326): *"All messages under 'C. Message texts waiting for your approval' are approved."* This message was C18 of that list ([5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116)), and the words he approved are the words below, unchanged since that post.

*Raised 2026-09-11 while reproducing Knut's #182 import route. "Open chart
file" filters on `*.ti2` and its file list hides everything else, but a file
dialog also has a NAME BOX, and a name typed, pasted or dragged into it is
accepted whatever it ends in. `resolve_ti2` then handed the file to
`_copy_files`, which copies it into a brand-new project as that project's
chart: a page bitmap became `<project>.ti2` with `II` as its first two bytes,
in a project that cannot be printed, measured or built from, and the app said
the files had been copied. The guard is
`workflow.chart_import.holds_a_chart`, and it refuses before the project is
made, so nothing exists to clean up. `{name}` is the file the person picked.*

> **That file holds no chart**
>
> “{name}” was opened as a chart file, and there is no patch list inside it. A chart file, “.ti2”, holds the colours ChromIQ prints and measures. A page image, “.tif”, is a picture of the printed sheet and holds none of them.
>
> Nothing has been created and nothing has been copied. Your file is where it was, unchanged.
>
> Open the “.ti2” file that sits beside the page images instead. It carries the same name as they do, without the page number.

### M-REPORT-UPDATE-OR-NEW · APPROVED · Generate report, with a selected report whose settings were changed — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5818037438](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5818037438): *"Yes, I approve those two messages."*, on this text as it reads now, with its numbered list in the buttons' order (Create New first, his K32). It was C1 of [5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116); his approval of section C in [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326) did not cover the reordered list ([5817922257](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817922257)), this one does.


*New for #182, 2026-09-19. **Knut wrote the text himself** and ended it "(or
similar)", and it still goes through this section, because §M is where a
message waits until he says the words are the words. It is shown by the
Measurement Report window's "Generate report" button, and only when both halves
of his sentence hold: a report from "Report shown" is selected AND one of the
five settings has moved since the page was drawn, which is exactly the state
the red line names.*

> *"When a report from 'Report shown' is selected, as we know, all settings are
> updated reflecting the selected reports settings when it was created/saved.
> If any of the settings are changed, a red text message will show user that he
> must click Generate Report to apply settings. When Generate Report is then
> clicked, the user must be shown a popup message with following text (or
> similar) … The window must then have three buttons: Update, Create New and
> Cancel."*

*The headline is his sentence without its full stop: a headline is not a
sentence in this catalogue, and nothing else about the text moved. The numbered
lines stay in the body even though the three buttons carry the same three
words: the list is what says which button does what, and "Update"
on its own does not say that the SELECTED report is what gets updated.*

*This message is the visible half of a ruling that also supersedes K.1 of
`measurement_report_limits.md` ("Generate report always writes a NEW report").
§13.8 of that document carries the ruling, his words and his date.*

*K32, 2026-09-24 (Knut on beta 41, #182 5813851807), his words and so his
approval of the change: "Move Create New button to be the first button on the
left and Update button to be the middle button. Make sure bullet list
description also has same sequence, Create New button in first bullet etc. The
Create New button should be default selected, so than an enter would Create New
by default (Safest)." The buttons now read **Create New**, **Update**,
**Cancel** from the left, Create New is the default button (Enter creates a new
report, Escape cancels), and the numbered list follows the buttons. The same
applies to M-REPORT-UNCHANGED-UPDATE-OR-NEW below.*

> **Settings were modified for the selected report**
>
> What do you want to do?
>
> 1. Create new report with selected settings.
> 2. Update selected report with selected settings.
> 3. Cancel

### M-REPORT-UNCHANGED-UPDATE-OR-NEW · APPROVED · Generate report, with a selected report and nothing changed — Measurement Report

**Approved by:** Knut, 2026-09-24, #182 [5818037438](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5818037438): *"Yes, I approve those two messages."*, on this text as it reads now, with its numbered list in the buttons' order (Create New first, his K32). It was C2 of [5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116); his approval of section C in [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326) did not cover the reordered list ([5817922257](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817922257)), this one does.


*New for #182, 2026-09-22 (B8-778 K4). Knut on beta 34: "I clicked Generate
Report button (without any settings having been changed.). This resulted in a
new report being created, without user being asked if I want to create a new or
update the selected". M-REPORT-UPDATE-OR-NEW above was asked only when a
setting had moved, and Generate otherwise created in silence; his log holds
four such presses in nine seconds and 44 files. So a selected report is now
always asked about. The three buttons and what they do are M-REPORT-UPDATE-OR-
NEW's; only the headline and the first two lines differ, because "Settings were
modified" is false here. Update then works the report out again with this
version of ChromIQ, which is what he wanted ("The report had some old text,
which I wanted to update"), and the previous content is kept under
`reports/old/` first (B8-782, D23). Whether an unchanged Update may re-judge a
dated record by today's rules is put to him.*

> **Nothing was changed for the selected report**
>
> What do you want to do?
>
> 1. Create new report with the same settings.
> 2. Update selected report, worked out again by this version of ChromIQ.
> 3. Cancel

*K32, 2026-09-24: the list and the buttons in M-REPORT-UPDATE-OR-NEW's new
order, Create New first and the default (Knut, #182 5813851807).*

### M-REPORT-SCOPE-RUN-DELETED · APPROVED · Report Scope of a saved report that covered a profile run since deleted — Measurement Report (window and PDF)

**Approved by:** Knut, 2026-09-24, #182 [5820871320](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5820871320): *"when saying "profile run" do you mean the report was for measurements when run type is profiling? Maybe a the terms to differentiate between the different reports' scope could be (suggest something better if you want) "profile run", "verification run" and "calibration run"? Maybe the message should take this into account too, and that the wording used is recorded in the help card Dictionary, so it is clearly defined. [...] Given the above, the message is accepted."* The words below are the words he was shown in [5820168457](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5820168457), unchanged: "profile run" is the term the Dictionary help card now defines (K36-3, `measurement_report_limits.md` §32.3), the numbered run of a project (run 1, run 2, …) with everything in it, so a report that covered its profiling measurement or its verification runs names it the same way.

*New 2026-09-24, #182 A6. Knut, 5817809396, accepted the recommendation "add
the Scope line". The profile bar's Delete renumbers the later runs and turns a
saved report's reference to the deleted run into `runs/runN.deleted`
(`core/report_refs.py`), which no folder answers, so the report shows fewer
measurements than it was written about and only an Update said why
(M-REPORT-UPDATE-LEAVES-OUT). Report text, for the reader of the document: in
the dim note style at the foot of Report Scope, in the window and the PDF,
only while a saved report that names such a run is shown. `{runs}` names each
deleted run by the number it had when the report was written ("run 2", "run 2
and run 4"; with the project's name, "P, run 2", when the report covers
several projects). `{count}` decides singular and plural.*

> **Part of this report has since been deleted**
>
> This report also covered {count} profile runs that have since been deleted ({runs} when the report was written). Their measurements are no longer in the report.

*With one run:*

> This report also covered a profile run that has since been deleted ({runs} when the report was written). Its measurements are no longer in the report.

### M-REPORT-NO-PAPER-PATCH · APPROVED · the numbered note of a sheet whose chart has no paper patch — Measurement Report (window and PDF)

**Approved by:** Knut, 2026-09-24, #182 [5820871320](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5820871320): *"When you say "..., and nothing on this sheet is judged relative to the paper." do you mean the "chart sheet" or do you mean "nothing in this report"? Make sure the text cannot be misunderstood. Then this message is accepted."* So the approval is of the reworded body below (K36-4, `measurement_report_limits.md` §32.4), not of the words he was shown.

*Reworded 2026-09-24 (K36-4). What the code does was read first: it is PER MEASURED SHEET. `build_report` finds the paper patch and chooses the yardstick for each measurement on its own, and the note is attached to that sheet's "Paper white" line; the numbered note is shared by every sheet that carries it (one numbering for the document). A report can hold sheets of several charts, so the body names the measured sheet and says the rest of the report is not affected. The first body read: "This chart has no patch printed with no ink, so the paper white could not be measured, and nothing on this sheet is judged relative to the paper."*

*New 2026-09-24, #182 A10. Knut, 5817809396, accepted recommendation (a):
"Paper white" is the chart's own white patch (device value 100, 100, 100 for
RGB; every channel at 0 in a subtractive space), and when there is none,
"Paper white" reads N-A with a numbered note, it is not drawn in the Paper
white (L\*) graph, and nothing is judged relative to the paper. Until beta 42
it was the lightest measured patch, which on such a chart is a light colour or
grey (an L\* 82 grey on one demo chart). The note is the one numbering every
other note uses: the "Paper white" line of the detailed section and the
Overview table read N-A, and the list under Report Results names it "Paper
white". Report text, for the reader of the document.*

> **This chart has no paper patch**
>
> The chart of this measurement has no patch printed with no ink, so this measurement has no paper white of its own. Every colour of this measurement is therefore judged as measured, in absolute Lab, and none relative to the paper. Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual.

*(Only the body is printed, as a numbered note; the headline names the message
in this catalogue.)*

*Reworded 2026-09-25 (Knut, #182 [5824834975](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5824834975), on the four K37 notes that share its words): "sheet" was unclear to him (the measured chart, a metric, or the report?), so this body names the measurement, as the report does ("Detailed data per measurement"), and ends as the four K37 notes now do. Its approval (5820871320) is kept; the rewording is here for Knut to see. The body before read: "The chart of this measured sheet has no patch printed with no ink, so the paper white of this sheet could not be measured. Every colour on this sheet is therefore judged as measured, in absolute Lab, and none relative to the paper. Only the sheets that carry this note are affected, not the rest of the report."*

*Where it is shown since K37 (2026-09-24, Knut 5822758830; words unchanged):
on a sheet with no paper patch that is judged in absolute Lab, which is every
such sheet EXCEPT one printed with a white-mapping intent whose profile's
paper white could be read. That sheet is judged relative to the profile's
paper white, so the second sentence above would be false on it, and its
"Paper white" line carries M-REPORT-PAPER-WHITE-FROM-PROFILE (§M-PROPOSED)
instead. So the message stays true wherever it is printed.*

### M-REPORT-PAPER-WHITE-FROM-PROFILE · APPROVED · the numbered note of a sheet judged relative to its profile's paper white, because its chart has no paper patch · Measurement Report (window and PDF)

**Approved by:** Knut, 2026-09-25, #182 [5824834975](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5824834975), on the condition that the word "sheet" is made clear: he could not tell whether it meant the measured chart, a metric or the report (*"Only the sheets that carry this note are affected, not the rest of the report"* confused him). The words below are the reworded body, in the report's own vocabulary: one dated measurement of the chart, as "Detailed data per measurement" names it, which is what the code decides it for (per measurement). They end *"Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual."* The words he was shown said "sheet" throughout.

*New 2026-09-24, #182 K37. Knut, [5822758830](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5822758830),
answer 1: *"Recommendation: (e), with a numbered note on the sheet, and (b)
only when no profile can be read."* (`measurement_report_limits.md` §32.6 and
§33.) A sheet printed through its profile with an intent that maps white to
the paper (relative colorimetric, perceptual, saturation, or the external
colour-managed route), against the chart's design or device reference, whose
chart has no patch printed with no ink, is judged media-relative with the
paper white its profile records (`wtpt`): the profile the print record names,
else the run's own built profile. The note is on that sheet's "Paper white"
line (which still reads N-A: the paper was not measured), in the document's
one numbering, listed under "Paper white". It REPLACES M-REPORT-NO-PAPER-PATCH
on such a sheet, because that approved body says "Every colour on this sheet
is therefore judged as measured, in absolute Lab", which is not true of it;
M-REPORT-NO-PAPER-PATCH stays on every other sheet with no paper patch, where
its words are true. `{profile}` is the profile's file name, `{L}`, `{a}`,
`{b}` its paper white to one decimal. Report text, for the reader of the
document.*

> **Paper white taken from the profile**
>
> The chart of this measurement has no patch printed with no ink, so this measurement has no paper white of its own. The chart was printed with an intent that maps white to the paper, so the colours of this measurement are judged relative to the paper white recorded in the profile {profile} (L* {L}, a* {a}, b* {b}), which is the paper that profile was made for. If the measured paper differs from it (another batch, or paper that has aged), the results can be off by a little. Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual.

*(Only the body is printed, as a numbered note; the headline names the message
in this catalogue.)*

### M-REPORT-STRIP-CORNERS-PREDICTED · APPROVED · the numbered note on the control-strip rows of a FROM PROFILE GAMUT sheet · Measurement Report (window and PDF)

**Approved by:** Knut, 2026-09-25, #182 [5824834975](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5824834975), on the condition that the word "sheet" is made clear: he could not tell whether it meant the measured chart, a metric or the report (*"Only the sheets that carry this note are affected, not the rest of the report"* confused him). The words below are the reworded body, in the report's own vocabulary: one dated measurement of the chart, as "Detailed data per measurement" names it, which is what the code decides it for (per measurement). They end *"Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual."* The words he was shown said "sheet" throughout.

*New 2026-09-24, #182 K37 (i). Knut, [5823088098](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5823088098),
*"Yes do so"*, on our [5823015844](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5823015844)
(i): on a FROM PROFILE GAMUT chart the seven ink and black corner rungs of the
control strip are compared with the profile's predicted Lab for their device
value; the cube-corner table and its graph keep the ideal values. Our post
said *"A short note would say so."* The note is on the three control-strip
rows wherever they carry a verdict on such a sheet, one number for all of them
(`measurement_report_limits.md` §34). Report text, for the reader of the
document.*

> **A corner patch is compared two ways**
>
> In this measurement the chart's solid ink, overprint and black patches are compared two ways. In the cube-corner table each is compared with its ideal value, which shows how far this printer's colour is from the ideal one. In the control-strip rows each is compared with the colour the profile predicts for it, like every other patch of this chart, which shows how accurately it was printed. Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual.

### M-REPORT-STRIP-CORNERS-IDEAL · APPROVED · the same rows when no profile could be read to predict the corners · Measurement Report (window and PDF)

**Approved by:** Knut, 2026-09-25, #182 [5824834975](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5824834975), on the condition that the word "sheet" is made clear: he could not tell whether it meant the measured chart, a metric or the report (*"Only the sheets that carry this note are affected, not the rest of the report"* confused him). The words below are the reworded body, in the report's own vocabulary: one dated measurement of the chart, as "Detailed data per measurement" names it, which is what the code decides it for (per measurement). They end *"Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual."* The words he was shown said "sheet" throughout.

*New 2026-09-24, #182 K37 (i), for charts where the run's profile cannot be
read (or ArgyllCMS cannot be asked): today's comparison with the ideal values
stays, and the strip rows say so.*

> **Corner patches compared with their ideal values**
>
> No profile could be read to predict the colours of this measurement's solid ink, overprint and black patches, so in the control-strip rows they are compared with their ideal values, as in the cube-corner table. That difference is mostly how far this printer's colours are from the ideal ones, not a printing error, so these rows can read worse than the print is. Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual.

*(Only the body is printed, as a numbered note; the headline names the message
in this catalogue.)*

### M-REPORT-JUDGED-ABSOLUTE-NO-PAPER-WHITE · APPROVED · the numbered note on each row of a sheet that should have been judged relative to its paper white and could not be · Measurement Report (window and PDF)

**Approved by:** Knut, 2026-09-25, #182 [5824834975](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5824834975), on the condition that the word "sheet" is made clear: he could not tell whether it meant the measured chart, a metric or the report (*"Only the sheets that carry this note are affected, not the rest of the report"* confused him). The words below are the reworded body, in the report's own vocabulary: one dated measurement of the chart, as "Detailed data per measurement" names it, which is what the code decides it for (per measurement). They end *"Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual."* The words he was shown said "sheet" throughout.

*New 2026-09-24, #182 K37, the (b) of Knut's answer above: the same kind of
sheet when NO profile can be read (the print record names none on disk and
the run has no built profile). The sheet is judged in absolute Lab as before
beta 42's K37; the note is attached to every row of that sheet whose number
the paper's own tone moves and that carries a verdict (the five
colour-difference rows, the three control-strip rows, the two gamut rows, both
grey-balance rows, the 30 to 70 % tone ramps and the two evenness rows), one
number for all of them. M-REPORT-NO-PAPER-PATCH stays on the sheet's "Paper
white" line: on this sheet its words are true. The figure "about 1.5 to 3
ΔE00 on the averages" is measured (§32.6 and §33: 12 demo sheets on six
papers of L\* 94 to 96). Report text, for the reader of the document.*

> **Judged without a paper white**
>
> The chart of this measurement was printed with an intent that maps white to the paper, so its colours should be judged relative to its paper white. The chart has no patch printed with no ink, and no profile could be read to take the paper white from, so these rows of this measurement are judged as measured, in absolute Lab. The paper's own lightness and tint then count against every colour, so these results can read worse than the print is (on typical papers by about 1.5 to 3 ΔE00 on the averages), and a limit can fail for that reason alone. Only the measurements that carry this note are judged this way; the report's other measurements are judged as usual.

*(Only the body is printed, as a numbered note; the headline names the message
in this catalogue.)*

### M-REPORT-WORKED-OUT-EARLIER · APPROVED · a saved report shown as an earlier version worked it out · Measurement Report, Report Scope (window and PDF)

**Approved by:** Knut, 2026-09-25, #182 [5831246553](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5831246553), except its last sentence: *"This part "Update works the report out again." is not according to rules for report text and notifications in the report. It refers to features, actions or buttons in the app interface, which shall never be part of the notes or the report text. [...] Besides this, the message is approved."* So the approval is of the body below, whose last sentence speaks of the topic in general terms (K39-1, `measurement_report_limits.md` §19.1a). The body he was shown ended *"This version works some of its rows out differently; Update works the report out again."*

*New 2026-09-25, challenge 5 of beta 42, M1 (B8-1091). A saved report is a
record (`measurement_report_limits.md` §6): its verdict words are kept when
it is read again. A report saved before a rule that changed how its rows are
worked out (K34's paper patch, K37's paper white taken from the profile, K37
(i)'s strip corners against the profile's prediction) was shown with its
kept words beside notes written by the new rule, which contradicted them. The
page now shows the report as it was saved, notes included, and says so once,
at the foot of Report Scope, only when this version would work it out
differently. Our words; the behaviour follows §6. Report text, for the
reader of the document.*

> **Worked out by an earlier version**
>
> This report was worked out by an earlier version of ChromIQ and is shown as it was saved. This version works some of its rows out differently. A newer report of the same measurements would be worked out the current way.

### M-REPORT-WORKED-OUT-DIFFERENTLY-UPDATE-OR-NEW · APPROVED · Generate report, with a selected report, nothing changed, and this version working it out differently — Measurement Report

**Approved by:** Knut, 2026-09-25, #182 [5832385126](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5832385126): *"the two messages are approved."*

*New 2026-09-25, #182 K39-2. We asked (B8-1093): "After Update on such an
older report, its verdicts can change right after the approved question
"Nothing was changed for the selected report". Should that question have its
own wording for this case, for example "This version works the selected report
out differently"?" Knut, [5831246553](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5831246553):
*"Yes."* So M-REPORT-UNCHANGED-UPDATE-OR-NEW (approved) is unchanged, and this
variant is shown in its place when nothing in the settings changed but an
Update would change the report: the window works each measurement the Update
would write out again from disk, exactly as the Update does, judges it against
the report's own limit set, and compares the rows, their words, their numbers
and the Overall word with the page; a change in how the rows are explained
(the test behind M-REPORT-WORKED-OUT-EARLIER) counts too. The three buttons and
their order are M-REPORT-UPDATE-OR-NEW's: Create New, Update, Cancel from the
left, Create New the default (Enter), Escape Cancel. Our words; the numbered
list is M-REPORT-UNCHANGED-UPDATE-OR-NEW's, word for word.*

> **This version works the selected report out differently**
>
> Nothing was changed in the settings of the selected report, but this version of ChromIQ works it out differently from the version that saved it: an update changes some of its results, or the notes that explain them.
>
> What do you want to do?
>
> 1. Create new report with the same settings.
> 2. Update selected report, worked out again by this version of ChromIQ.
> 3. Cancel

### M-REPORT-NEW-REPORT-SETTINGS · APPROVED · the red line after "New report…" is chosen in "Report shown" — Measurement Report

**Approved by:** Knut, 2026-09-25, #182 [5832385126](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5832385126): *"the two messages are approved."*

*New 2026-09-25, #182 K39-3. Knut, [5831246553](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5831246553):
*"Selecting "New report…" will not change whatever report is currently
visible, but loads the default settings for "New report…", and should then
also show a red text message telling user to modify settings as desired and
then press Generate Report to apply and make a new report."* Window text, in
the red line under the settings, where "Settings changed" is shown otherwise
(`measurement_report_limits.md` §28.11). Only the body is shown, after a
warning sign; the headline names the message in this catalogue. It stays up
until a report is drawn: Generate report, a report chosen in "Report shown", a
delete. Our words.*

> **Settings loaded for a new report**
>
> New report: change the settings as wanted, then press “Generate report” to make it. The report shown stays as it is until then.

### M-REPORT-SOLIDS-PREDICTED · APPROVED · the numbered note on the two solid-colour rows, wherever they are compared with the profile's prediction · Measurement Report (window and PDF)

**Approved by:** Knut, 2026-09-26, #182 [5845588201](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5845588201): *"Messages "M-REPORT-SOLIDS-PREDICTED" and "M-REPORT-PAPER-AGAINST-PROFILE" accepted."*

*New 2026-09-26, #182 K49. Knut, [5841092535](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5841092535),
answer 1, *"Should (b2) be built? Answer: Yes."*: "Maximum ΔE00, solid
colours" and "Maximum ΔH\*ab, cyan, magenta and yellow solids" are compared
with the colours the profile predicts for the solids, wherever they were
printed raw (a FROM PROFILE GAMUT chart always, else a raw print). The
cube-corner table keeps the ideal values (`measurement_report_limits.md`
§41.7), so on a real printer the row reads near 0 while the table reads 10 to
40 for the same patch. Report text, for the reader of the document; only the
body is printed, as a numbered note.*

> **Solid colours compared with the profile's prediction**
>
> In this measurement the solid cyan, magenta, yellow and black patches are compared with the colours the profile predicts for them, which shows how accurately they were printed. The cube-corner table compares the same patches with their ideal values, which shows how far this printer's colours are from the ideal ones, so the two can differ a lot.

### M-REPORT-PAPER-AGAINST-PROFILE · APPROVED · the numbered note on the paper row of a chart that is not FROM PROFILE GAMUT · Measurement Report (window and PDF)

**Approved by:** Knut, 2026-09-26, #182 [5845588201](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5845588201): *"Messages "M-REPORT-SOLIDS-PREDICTED" and "M-REPORT-PAPER-AGAINST-PROFILE" accepted."*

*New 2026-09-26, #182 K49, the same answer: "ΔE00, paper white against the
reference paper" compares the chart's paper patch with the media white of the
profile the chart was printed through, or else of its run's own profile, on
every chart with a paper patch (the lookup of §33). On a FROM PROFILE GAMUT
chart the cube-corner table's white already aims at that paper (§31.5), so no
note is needed there; on any other chart the table's white is the chart's own
aim, and this note says why the two differ.*

> **Paper compared with the profile's paper**
>
> In this measurement the paper is compared with the paper white recorded in the profile (the one the chart was printed through, or else the profile of its run), which is the paper that profile was made for. The cube-corner table compares the same patch with the chart's own aim for white, an ideal white, so the two can differ.

### M-VERIFY-SOLIDS-REASON · APPROVED · why a chart cannot answer the two solid colour metrics — the presets window, and the Measure tab pre-flight's metric list

**Approved by:** Knut, 2026-09-26, #182 [5848287278](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5848287278): *"Regarding "For your approval (M-VERIFY-SOLIDS-REASON)" Answer: Approved."*, on the words below, unchanged since they were proposed (B8-1373).

*New 2026-09-26, beta 44 challenge 8, C5 (B8-1373). The reason line under
"Maximum ΔE00, solid colours" and "Maximum ΔH\*ab, cyan, magenta and yellow
solids" in the "Which presets can be used for verification?" window, and in
the metric list M-VERIFY-PREFLIGHT carries. Only the body is shown; the
headline is its name in the catalogue. It replaced "This chart carries no
colorimetric reference.", which K49 and K51 made untrue as a reason: those
two rows are compared with the colours the profile predicts, not with a
reference file, and on a sheet printed raw they are judged (Knut, #182
5846167083, K50-1). What withholds them is how a verification is printed:
through its profile, which converts the solid patches. Neither window can know
yet how the sheet will be printed, so the line says both cases.*

> **Why this chart cannot answer the solid colour metrics**
>
> Printed through its profile, as a verification normally is, the chart's solid patches become other ink amounts, not the printer's own solids, so the report cannot judge them. Printed without a profile, its solids are judged against the profile and its other metrics are shown for information only.

### K59 · the texts of option C, and of "change" for "drift" (#182, Knut 5849392788, APPROVED in 5850164956, 2026-09-26)

*Knut's answer to K56 question 1 (`~/Desktop/ChromIQ-beta44-proof/k56/ANALYSIS-drift.txt`):
*"use recommended option C, but with some comments: 1. The word drift is not
used at all ... Use the word "Change" instead of "Drift"."*; on the cell word,
*"can we use the INFO but also have a numbered reference to a note that
explains the issue, where that is relevant?"*; and to "I will propose the
reworded sentence under the results, the guide entry and the "Judged against"
text for your approval before they ship": *"Ok"*. Each text below replaced one
that was false under his ruling and was shown while it waited; all fourteen
were APPROVED by Knut in 5850164956 and left §M-PROPOSED. German is in
`data/i18n/de.json`, by hand, no "du".*

### M-REPORT-RAW-PRINT-INFO · APPROVED · the numbered note on a value of a sheet printed raw shown for information — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*On every row of a raw sheet that compares the print with the chart's design colours and reads INFO (`ROWS_COMPARED_WITH_THE_DESIGN`); not on the paper and solid rows, and not on the two repeatability rows. Knut asked for it: *"can we use the INFO but also have a numbered reference to a note that explains the issue, where that is relevant?"**

> **A value of a sheet printed raw, shown for information**
>
> This sheet was printed raw, without the profile, so this value is shown for information only and is not judged: it compares the print with the chart's design colours, which a sheet printed without the profile is not expected to match closely.

### M-REPORT-RAW-JUDGED-AGAINST · APPROVED · "Judged against" of a raw sheet's column that judged a row (its paper or solid rows, or since D3 its repeatability rows) — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*`{set}` is the limit set's name as every other column shows it. Replaces "—".*

> **Judged against, a sheet printed raw**
>
> {set} (printed raw)

### M-REPORT-RAW-NOT-JUDGED · APPROVED · "Judged against" of a raw sheet's column that judged nothing — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*Replaces "—".*

> **Judged against, a sheet printed raw that judged nothing**
>
> not judged (printed raw)

### M-REPORT-RAW-OVERALL · APPROVED · the Overall word's sentence of a raw sheet that judged nothing (tooltip, one-page summary) — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*Replaces the profiling sheet's "It was measured to build a profile rather than to check one", false of a verification. Also shown for a report saved before K59 that stored that sentence for a raw sheet (a saved sentence is a rendering, `recorded_reason`).*

> **Overall, a sheet printed raw that judged nothing**
>
> This sheet was printed raw, without the profile, so its values are shown for information only and nothing on it was judged.

### M-REPORT-RAW-RESULTS-JUDGED · APPROVED · the sentence under Report Results where every raw column judged its paper and all its solid rows — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*Knut's K51 clause is kept verbatim; only the opening sentence, which named the "drift" cells, is new.*

> **Under the results, sheets printed raw that judged their paper and solids**
>
> Columns marked “printed raw” under “Judged against” are sheets printed without the profile. On them the paper and the solid colours are judged against the profile; the other colours are compared with the chart's design colours for information, because a sheet printed raw is not expected to match the design closely, and PASS or FAIL there would be unfair to a perfectly healthy printer. For those sheets the detailed chapter shows how far the printer has moved since the previous raw check.

### M-REPORT-RAW-RESULTS-SOME · APPROVED · the sentence under Report Results where a raw column judged some of its paper and solid rows — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*Challenge 9 of beta 44: the clause must be true of exactly the rows judged (ISO 12647-8 limits the paper only; a row can read N-A).*

> **Under the results, sheets printed raw that judged some of their paper and solid rows**
>
> Columns marked “printed raw” under “Judged against” are sheets printed without the profile. On them the paper and the solid colours are judged against the profile where the limit set has a limit for them and the measurement can answer them; the other colours are compared with the chart's design colours for information, because a sheet printed raw is not expected to match the design closely, and PASS or FAIL there would be unfair to a perfectly healthy printer. For those sheets the detailed chapter shows how far the printer has moved since the previous raw check.

### M-REPORT-RAW-RESULTS · APPROVED · the sentence under Report Results where no raw column judged anything — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

> **Under the results, sheets printed raw that judged nothing**
>
> Columns marked “printed raw” under “Judged against” are sheets printed without the profile. They are not expected to match the design closely, and PASS or FAIL would be unfair to a perfectly healthy printer, so their values are shown for information. For those sheets the detailed chapter shows how far the printer has moved since the previous raw check.

### M-REPORT-RAW-GUIDE-JUDGED · APPROVED · "How to read this report", the paragraph on a raw column — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*The last sentence, on the Overall word, is the guide's own and unchanged.*

> **How to read this report, a sheet printed raw**
>
> A column marked “printed raw” under “Judged against” is a sheet printed without the profile. Its paper and solid colour rows are judged against the profile where the limit set has a limit for them; its values that compare the print with the chart's design colours read INFO, with a numbered note that says so. A column's Overall word is PASS when every row that could be checked passed; a row the test chart used could not answer is not counted as a failure, and the sentence under the word says how many there were.

### M-REPORT-RAW-GUIDE · APPROVED · "How to read this report", the paragraph on a raw column, where no raw column judged anything — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

> **How to read this report, a sheet printed raw that judged nothing**
>
> A column marked “printed raw” under “Judged against” is a sheet printed without the profile. Its values that compare the print with the chart's design colours read INFO, with a numbered note that says so. A column's Overall word is PASS when every row that could be checked passed; a row the test chart used could not answer is not counted as a failure, and the sentence under the word says how many there were.

### M-REPORT-RAW-BASELINE · APPROVED · the detailed chapter under the first raw sheet of a chart — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

> **The first raw check of a chart**
>
> This sheet was printed raw, without the profile, and it is the first raw check of this chart: it is the baseline that later raw checks of this chart are compared with.

### M-REPORT-RAW-INCOMPARABLE · APPROVED · the detailed chapter under a raw sheet whose previous raw check used another chart — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

> **A raw check after one of a different chart**
>
> This sheet was printed raw, without the profile. The previous raw check used a different chart, so the change from print to print cannot be measured for this pair; the next raw check of THIS chart will start a fresh comparison.

### M-REPORT-RAW-CHANGE · APPROVED · the detailed chapter: the print-to-print change since the previous raw check — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*Knut: *"Use the word "Change" instead of "Drift". ... It is better that a person looks at the trend to diagnose this."* The sentence pointing at the trend graphs is new.*

> **Change since the previous raw check**
>
> Change since the previous raw check ({prev}): average {avg} ΔE00, maximum {max}: this print measured against that print, patch by patch, {n} patches. Small numbers mean the printer still behaves as it did then; larger numbers mean it has changed since. Whether it keeps changing in one direction can be read from the trend graphs, across all the dated checks. (PASS and FAIL against the report's limit set are not shown here: a raw sheet is not expected to match the design closely, so it would fail even a perfectly healthy printer.)

### M-REPORT-RAW-SHEET · APPROVED · the detailed chapter under a raw sheet with no comparison record — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

> **A sheet printed raw**
>
> This sheet was printed raw, without the profile. Its figures compared with the chart's design colours describe the distance from the design, and what matters is how they change between dated checks, not their size.

### M-REPORT-MIXED-OPENING · APPROVED · the opening of a report whose sheets were printed both ways (one project and run) — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956): *"All messages under "B. PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are approved."*

*B8-1380. Knut: *"When that is resolved and the message reworded, the rest of the message is ok."* Only "marked “drift”" is reworded, to "marked “printed raw”".*

> **The opening of a report of sheets printed both ways**
>
> This report judges the profile built in {where}. Some of its sheets were printed through that profile and compared with the chart's own aim values; the others, marked “printed raw”, were printed without it. The measurements it covers are listed under Report Scope.

### M-REPORT-MIXED-OPENING-RUNS · APPROVED · the opening of a report across runs whose sheets were printed both ways — Measurement Report

**Approved by:** Knut, 2026-09-26, #182 [5850164956](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5850164956), D2 (B8-1397): *"Accepted."*, to the words below, verbatim.

*A document across several profile runs with sheets printed both ways kept the approved plural sentence "Each was verified by printing a chart through its profile", false of its raw sheets.*

> **The opening of a report across runs of sheets printed both ways**
>
> This report judges the profiles built in {where}. Some of their sheets were printed through their profiles and compared with the charts' own aim values; the others, marked “printed raw”, were printed without them. The measurements it covers, and the profile run each comes from, are listed under Report Scope.

### M-REPORT-NOT-WORKED-OUT · APPROVED · a new report with a date whose measurement is no longer on disk · Measurement Report, Report Scope (window and PDF)

**Approved by:** Knut, 2026-09-27, #182 [5858874320](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5858874320): *"Regarding your 'Two new texts for your approval:' Answer: Approved."* The words he approved are the words below, unchanged since they were put to him in [5857991890](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5857991890).

*New 2026-09-27, B8-1500. Knut, #182 [5857473253](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5857473253): a saved report is shown exactly as it was saved, and a new or updated report is made entirely by the current version, every date worked out again from its measurement. Where a date's measurement is no longer on disk as it was measured, nothing can be worked out again, and that date's figures are the ones an earlier report saved. The report says so at the foot of Report Scope instead of mixing them silently with this version's figures, and a report saved that way keeps saying so. Our words, for Knut's approval. Report text, for the reader of the document; it names no button. {dates} is the dates, comma-separated; the singular form is used for one date.*

> **Figures an earlier report saved**
>
> The measurements of {dates} are no longer on disk as they were measured, so they could not be worked out again. Their figures are the ones an earlier report saved, worked out by the version of ChromIQ that saved it.

*For one date:* "The measurement of {dates} is no longer on disk as it was measured, so it could not be worked out again. Its figures are the ones an earlier report saved, worked out by the version of ChromIQ that saved it."

### M-CAL-FOUND-ENGINE · APPROVED · a calibration file found while the ChromIQ layout engine lays the chart out · Create Chart, Manual, the status line under the calibration fields

**Approved by:** Knut, 2026-09-28, #182 [5865088296](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5865088296): *"Message 1 is ok"*. The words he approved are the words below, unchanged since they were put to him in [5863200239](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5863200239).

*New 2026-09-28, B8-1655. Decision 7 of `calibration_run_type.md` (2026-08-05) fills the found `.cal` into the printtarg -K and -I fields, switches neither on, and says so. An engine build does not read those fields: it takes its calibration from the engine panel's own "Printer calibration" group. With the engine the default, the offer went where the build ignores it, and the line told the user to switch on a field that does nothing. The engine panel's path is now offered the same way (filled only when it is empty, Mode left on "None"), and this is the line for that case; with printtarg laying the chart out, the old line stays. Our words, for approval. `{name}` is the file name.*

> **Calibration file found**
>
> Calibration file found: {name}. It is filled into “Printer calibration” in the ChromIQ layout section below, with Mode still on “None”: choose the mode you want there. “Apply & embed (-K)” reprints every patch through the calibration; “Embed only (-I)” only records it in the chart file.

### M-UNREAD-NEXT-OR-JUMP-STRIP · APPROVED · after a strip read, the next strip is not the nearest unread one — Measure tab, ChromIQ engine, strip mode

**Approved by:** Knut, 2026-10-03, #182 [5962907586](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5962907586): *"All questions in post https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5961673878 are accepted. The messages are also accepted."*

*New for #182, 2026-10-02. **Knut wrote the text himself**
([5958921500](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5958921500),
Q2), and it still goes through this section, because §M is where a message
waits until he says the words are the words (the precedent is
M-REPORT-UPDATE-OR-NEW). His ruling, verbatim:*

> *"The window should follow the same framework as other popup messages during
> measurement and should say something like this: 'Some patches / strips are
> still not read. What do you want to do? 1. Continue to next: position to read
> jumps to next patch / strip from current position, even if previously
> measured. 2. Jump to unread: position to read jumps to closest unread patch /
> strip to complete the measurement.' Where the following buttons are available
> 'Continue to next' and 'Jump to unread'."*

*What changed from his text, and why: "patches / strips" is one of the two in
each window (this one names strips, the twin below names patches), the
headline counts, with a real singular; each bullet says what the reader does in
full sentences; "closest" became "forward to the next … (after the last strip
it carries on from the first)", which is what the reader does (see §1b, "After
a read"); and a last paragraph says the question comes once and that the usual
keys still work. Shown when it is needed even before approval: Sebastian,
2026-10-02, ruled that a proposed window protecting the measurement may show.
The buttons are **Continue to next** (default) and **Jump to unread**.*

> **Some patches are still not read**
>
> {n} patches on this chart have no reading yet. What would you like to do next?
>
> •  Continue to next: the reader moves to the strip after the one you have just read, even if that strip was measured before.
>
> •  Jump to unread: the reader moves forward to the next strip that still has patches without a reading (after the last strip it carries on from the first), so you can complete the measurement.
>
> ChromIQ asks once. Your choice stays for the rest of this measurement, and f, b, n or a click on the preview still take you anywhere.

*With one patch left:*

> **One patch is still not read**
>
> One patch on this chart has no reading yet. What would you like to do next?
>
> •  Continue to next: the reader moves to the strip after the one you have just read, even if that strip was measured before.
>
> •  Jump to unread: the reader moves forward to the strip that still has a patch without a reading (after the last strip it carries on from the first), so you can complete the measurement.
>
> ChromIQ asks once. Your choice stays for the rest of this measurement, and f, b, n or a click on the preview still take you anywhere.

### M-UNREAD-NEXT-OR-JUMP-PATCH · APPROVED · after a patch read, the next patch is not the nearest unread one — Measure tab, ChromIQ engine, patch by patch

**Approved by:** Knut, 2026-10-03, #182 [5962907586](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5962907586): *"All questions in post https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5961673878 are accepted. The messages are also accepted."*

*The twin of M-UNREAD-NEXT-OR-JUMP-STRIP above, for patch-by-patch reading,
from the same ruling. Only the unit differs.*

> **Some patches are still not read**
>
> {n} patches on this chart have no reading yet. What would you like to do next?
>
> •  Continue to next: the reader moves to the patch after the one you have just read, even if that patch was measured before.
>
> •  Jump to unread: the reader moves forward to the next patch that has no reading yet (after the last patch it carries on from the first), so you can complete the measurement.
>
> ChromIQ asks once. Your choice stays for the rest of this measurement, and f, b, n or a click on the preview still take you anywhere.

*With one patch left:*

> **One patch is still not read**
>
> One patch on this chart has no reading yet. What would you like to do next?
>
> •  Continue to next: the reader moves to the patch after the one you have just read, even if that patch was measured before.
>
> •  Jump to unread: the reader moves forward to the patch that has no reading yet (after the last patch it carries on from the first), so you can complete the measurement.
>
> ChromIQ asks once. Your choice stays for the rest of this measurement, and f, b, n or a click on the preview still take you anywhere.

### M-PATCH-EXPECTED-PREDICTED · APPROVED · the expected colour on a verification patch's hover card is the profile's prediction — Measure tab preview, #182

**Approved by:** Knut, 2026-10-03, #182 [5965408335](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5965408335): *"1. \"Expected: profile prediction\", ok. 2. ok"* (2 is the card's limit line on these charts, "(limit for a chart judged against its profile)").

*New 2026-10-03. Knut approved the idea in [5964173774](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5964173774) (answer 4 to question 4 of [5963902307](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963902307): Show "expected: profile prediction" on the patch hover card for these charts? "Yes."); these exact words wait for approval. On a verification chart judged against the run profile's prediction (10.8), this line replaces the card's "Expected" label above the expected swatch, its RGB and its L\*a\*b\*. One line, so the message's body is its headline. Every other chart keeps "Expected".*

> **Expected: profile prediction**

### M-PATCH-CORRECTED · APPROVED · the green outline of a misread a re-read corrected — Measure tab preview and the closing window, #182 beta 11

**Approved by:** Knut, 2026-10-04, #182 [5984277558](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5984277558): *"Ok"*, to [5984237879](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5984237879)'s *"Green outline: corrected by a re-read. The first reading (ΔE 58 off) did not fit; the new one does. It replaces the misread."* and *"2 misreads corrected by a re-read: patches Y6, AE8."*, approved line by line as below.

*The card breaks its lines by hand; the headline stands under the card's separator. `{de}` is the first reading's ΔE\*ab from its expected colour, a whole number. Line 2 is the middle line when the neighbour check flagged the first reading (alone or with the limit); when only the limit did, M-PATCH-CORRECTED-VARIANTS line 1 stands in its place. Line 4 is the closing window's, under the neighbour check's lines, for two or more patches (one: M-PATCH-CORRECTED-VARIANTS line 2); `{locs}` the first ten in chart order, then "…".*

> **Green outline: corrected by a re-read**
>
> The first reading (ΔE {de} off)
> did not fit; the new one does.
> It replaces the misread.
> {n} misreads corrected by a re-read: patches {locs}.

### M-PATCH-NEIGHBOUR · APPROVED · the neighbour check on a patch's hover card — Measure tab preview, #182 beta 17

**Approved by:** Knut, 2026-10-09, #182 [6078174421](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6078174421) (*"Every card: 'This patch is ΔE 6.2 further from its expected colour than the 4 patches nearest in colour (median).' ('further from' is replaced with 'closer to' when below 0. When ΔE 0.0 then the value should not be shown, and the text should be 'This patch has equal distance from its expected colour as the 4 patches nearest in colour (median)') - A red card: 'Red outline: ΔE 13.2 further from its expected colour than the 4 patches nearest in colour (median), passing the neighbour limit (10). Probably a misread: read it again.' ... This should be clear enough."*), and [6084176226](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6084176226) (*"Question 5: Are these the cards you want?" "Yes, good."*, to the k56 mock-ups of [6083412660](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6083412660), which carry lines 5 to 10: every card ends with "Checked again after each strip is read: …" or, patch by patch, "… after each patch is read", then "See Preferences ▸ Measurement for threshold values.", an empty line between topics, and no "buffer" anywhere ([6082015002](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6082015002))).

*Replaces beta 15's proposed lines ("Its reading does not fit the {n} patches / nearest in colour, read in other strips: / it is ΔE {excess} further from their readings / than the expected colours are (your buffer {buffer}).", and "Against the {n} patches nearest in colour: / ΔE {d} further from its expected colour / than they are from theirs (median)."). Whole sentences: the card wraps them to its width (`ui.tiff_preview.card_wrap`, about 40 characters), so each language translates a sentence. `{d}`: Knut's four steps' number, the patch's own error minus the median of its neighbours' errors (ΔE\*ab, one decimal, its size: the sign is the word); `{n}`: 2 to 4; `{limit}`: the Neighbour limit of the chart type, one decimal. Line 1 then line 2 under the card's separator on a red card of a patch only the neighbour check flagged, then lines 6 and 7, then "Same value after a re-read:" with the profiling or the verification line. Line 3, 4 or 5 on EVERY card of a patch with at least 2 neighbours, under "Measured" (5 when the number rounds to 0.0). Line 6 replaces "ΔE\*ab … reached the patch error limit …" on the yellow card of a suspect its own re-read confirmed. Lines 9 or 10, then 11, end EVERY card.*

> **Neighbour check on the patch card**
>
> Red outline: ΔE {d} further from its expected colour than the {n} patches nearest in colour (median), passing the neighbour limit ({limit}).
> Probably a misread: read it again.
> This patch is ΔE {d} further from its expected colour than the {n} patches nearest in colour (median).
> This patch is ΔE {d} closer to its expected colour than the {n} patches nearest in colour (median).
> This patch has equal distance from its expected colour as the {n} patches nearest in colour (median).
> Red before: ΔE {d} further from its expected colour than the {n} patches nearest in colour (median), passing the neighbour limit ({limit}).
> Only its own re-read can turn it yellow,
> not similar patches or its colour range.
> Checked again after each strip is read: a patch can turn red later, when patches near it in colour are read.
> Checked again after each patch is read: a patch can turn red later, when patches near it in colour are read.
> See Preferences ▸ Measurement for threshold values.

### M-PATCH-LIMIT · APPROVED · the patch error limit on a patch's hover card — Measure tab preview, #182 beta 17

**Approved by:** Knut, 2026-10-09, #182 [6084176226](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6084176226) (*"Question 5: Are these the cards you want?" "Yes, good."*), to the k56 mock-ups `card_red_patch_error_limit` ("Red outline: a large difference / ΔE\*ab 23.4 reached the patch error / limit (20.0, profiling charts made / with a pre-conditioning profile), / and it stands out from its strip / (strip test).") and `card_red_verification_limit` ("… reached the patch error / limit (5.0, verification charts).") of [6083412660](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6083412660). The fourth chart-type phrase, "calibration charts", is the column name Knut approved in 6082015002.

*Replaces "ΔE\*ab {de} reached your limit {limit}", the "(limit for a chart …)" line, "and stands out from its strip" and "(Preferences ▸ Measurement, “Flag a patch…”)": the limit is named by its proper name, with its value and its chart type, and the strip test by its name (Knut 6082015002). The headline is the red card's first line under the separator, then line 1, or line 2 when the strip test also flagged the patch. Line 1 alone stands on a yellow card (a re-read, similar patches, a learned range) in place of the old "reached your limit" line. `{de}` the patch's ΔE\*ab and `{limit}` the Patch error limit, one decimal each; `{kind}` one of lines 3 to 6, the chart type of the measurement.*

> **Red outline: a large difference**
>
> ΔE\*ab {de} reached the patch error limit ({limit}, {kind}).
> ΔE\*ab {de} reached the patch error limit ({limit}, {kind}), and it stands out from its strip (strip test).
> profiling charts with estimated colours
> profiling charts made with a pre-conditioning profile
> verification charts
> calibration charts

### M-PREVIEW-PAPER-WHITE · APPROVED · Simulate paper white, a small button inside the chart preview's indicator: Create Chart, Print Chart and Measure, beta 14

**Approved by:** Sebastian, 2026-10-08, in the session that built it ("yes the wording is approved").

*New 2026-10-08 (beta 14). Basti: "when the user hovers the label icon and it extends and the proof view is active could then there be also a button inside that activates and deactivates simulate paper white? ... the choice should also be remembered." The behaviour is his, and so is the approval of the words. While a page is shown as on paper (M-PREVIEW-AS-PRINTED, headline or line 1) and the indicator is open (hover, or keyboard focus), a small button at the open indicator's left end carries the headline and a box that is ticked while the paper white is simulated; it is not there over a page shown as device values, by choice or for want of a profile. A click on it, or Space once Tab has moved to it from the indicator, switches the simulation and never the view; the choice is one setting for the whole app, off by default. Line 1 is the button's name for a screen reader. Line 2 is the indicator's own name while the paper white is simulated (its short line stays "As on paper"). Lines 3 and 4 are the button's tooltip when off and when on. Lines 5 and 6 take the place of M-PREVIEW-AS-PRINTED lines 5 and 6 in the indicator's tooltip while the paper white is simulated; the rest of that tooltip is unchanged. Placeholders as in M-PREVIEW-AS-PRINTED.*

> **Paper white**
>
> Simulate paper white
> As on paper, paper white simulated
> Simulate paper white is off: the paper is shown as the screen's white. Click, or press Space, to show the paper in its own tone, as the run's profile describes it. ChromIQ remembers your choice.
> Simulate paper white is on: the paper is shown in its own tone, as the run's profile describes it (absolute colorimetric), and every colour sits on it as on the sheet. Click, or press Space, to show the paper as white again.
> The preview shows this chart as it prints: the ink amounts in the file, as the run's profile {profile} predicts them on paper, with the paper in its own tone (paper white simulated). What is printed does not change.
> The preview shows this chart as it prints through the profile: its colours converted from {source} to {profile} ({intent}), as ChromIQ converts them when printing, then as the profile predicts them on paper, with the paper in its own tone (paper white simulated). What is printed does not change.

### M-PRINT-COLOUR-CONFIRM · APPROVED · the colour rows of the Print Chart tab's confirmation window ("Confirm Print Settings"), beta 15

**Approved by:** Sebastian, 2026-10-08 (DECISIONS_print_fix_beta15.md, A1: "Sounds ok.").

*New 2026-10-08 (beta 15). Basti: the chart must print in exactly the state his later image prints get, and those come from Photoshop with "Photoshop manages colours". For a printer whose own print dialog picks a paper profile for the medium (Canon IJ and Epson, `workflow/ppd_color.py` PAPER_PROFILE_RULES) the direct route now sends that job: application colour matching and the medium's paper profile, the chart tagged with that same profile. The window said "Colour management: Off (forced)", which was not true of a Canon on photo paper (the printer ran its own colour processing). The behaviour is Basti's; the words are ours. Headline: the first row's name. Line 1: its value. Line 2: the second row's name, its value is the profile's name as the printer's driver gives it. Lines 3 to 5: the third row's name and its two values, shown for a Canon only, whose own colour processing is off for a paper profile and on for the generic one (plain paper, cards, discs). For any other printer the window is unchanged.*

> **Colour management**
>
> By ChromIQ, as when Photoshop manages colours
> Paper profile
> Printer's own colour processing
> Off for this paper
> On for this paper type, as for prints from Photoshop

### M-PRINT-JOB-CONFIRMED · APPROVED · the Print Chart tab's status line after a job was sent, both routes, beta 15

**Approved by:** Sebastian, 2026-10-08 (DECISIONS_print_fix_beta15.md, A2: "Sounds ok.").

*New 2026-10-08 (beta 15). After every print ChromIQ reads the job back from the printing system (CUPS, Get-Job-Attributes, no password) instead of reading back its own settings, which is what the macOS dialog route did until beta 14 and which could not fail. Line 1 when the job names a paper profile ({profile} is its name as the driver gives it), line 2 when it does not, line 3 is added after either on the macOS dialog route when the chart was tagged with the job's own paper profile, line 4 when the job could not be read back, or the read-back did not answer within ten seconds (it runs on a background thread since the beta 15 builder round). {job} is the printing system's job number.*

> **Print job sent**
>
> Sent as job {job}. The printing system confirms it carries application colour matching and the paper profile {profile}.
> Sent as job {job}. The printing system confirms it carries application colour matching.
> The chart went with that same profile attached, so macOS leaves its colours unchanged.
> Sent. ChromIQ could not read the job back from the printing system, so its colour settings are not confirmed.

### M-PRINT-QUALITY · APPROVED · the quality row of the Print Chart tab, Canon and Epson, beta 16

**Approved by:** Sebastian, 2026-10-09 (DECISIONS_beta16_quality.md, rows 1 to 4: "6 confirmed").

*New 2026-10-09 (beta 16). Basti: he prints his photos at the highest quality the Canon print dialog allows for the paper (its Custom slider at the top; on a PRO-300 with Semi-gloss that is CNIJPrintQuality 5, “Fine”). The direct route sent the dialog's standard quality (10) and the tab had no Canon quality row, so a chart could not be printed in the state his photos get. The row now lists the qualities the driver's own dialog allows for the chosen paper (Canon: the model's media database, XML or binary; Epson: the `Resolution` table of PDEData.dat), and preselects the quality of his last print on that paper through the macOS dialog (the learning store, `workflow/printer_memory.py`), otherwise the dialog's standard. Under the row: the headline in bold, then line 1 on the next line; line 2 is added when the preselected quality came from that last dialog print. Lines 3 and 4 mark two entries of the list; {quality} is the driver's own name for the quality (“Fine”, “Normal(Fine)”, “High Quality”). A printer whose driver ChromIQ cannot read keeps its generic row, without these lines. The behaviour is Basti's; the words are ours.*

> **Print your photos at this quality too**
>
> The profile fits only prints made at the quality its chart was printed with.
> Chosen as in your last print on this paper through the macOS print dialog.
> {quality} (highest)
> {quality} (standard)

### M-SPOT-CR30-GONE · APPROVED · the CR30 stopped answering during a spot session — Tools ▸ Read single patches

**Approved by:** Basti, 2026-10-10, in the session after the review of beta 17: the wording as it stands, and his confirmation that one short press of the button switches a CR30 on, which line 3 tells the user to do.

*New message (beta 17, 2026-10-09). Basti, on beta 16: the CR30 switched itself off during a session, Stop did nothing, and once it was switched on again nothing happened until the window was closed. Nothing in the session watched the Bluetooth link, so a gone instrument looked exactly like one nobody had pressed yet. The link is now watched, Stop ends the session at once, and when the instrument goes away the session pauses and asks.*

*Every reading already in the list is kept on both answers. "Reconnect" looks for the instrument again (the remembered Bluetooth address first, then a search) and the session carries on; if it is still not there, this window comes back. The instrument's own error text goes to the window's notes and the log, not into the window.*

> **Your CR30 is not answering**
>
> ChromIQ has lost the connection to your CR30. Usually it has switched itself off to save its battery, its USB cable has come out, or it is out of Bluetooth range.
>
> Every reading in this window is kept.
>
> Switch the instrument on again (press its button once) or plug it back in, then choose “Reconnect”. ChromIQ looks for it and you carry on reading. If it is still not there, this window comes back.
>
> To finish instead, choose “Stop session”. Your readings stay in the list either way.

*Buttons: **Reconnect** (default) and **Stop session**.*

### M-SPOT-CR30-EARLY-PRESS · APPROVED · a press from before Ready was not used — Tools ▸ Read single patches, CR30

**Approved by:** Basti, 2026-10-10: both lines, the one-press and the {n}-press variant, in the English as written; the place, the window's log, unchanged.

*New 2026-10-10 (review of beta 17). The review found that a press of the CR30's button made right after the spot window said Ready was thrown away: over Bluetooth the session's read began by dropping every press the instrument had announced so far, and it began up to about a second after Ready was shown. The log said "discarded 1 reading taken before this patch was armed"; the window said nothing. Fixed: the stale presses are dropped once, BEFORE the window says Ready, and never again while the session runs, so every press made once Ready is shown is taken (over USB nothing was dropped). A press the instrument announced before Ready, typically while the calibration's last window, which itself says to press the button, was still open, is still not used, because it belongs to no reading anybody asked for; this is what the window's log then says, so nobody waits for a row that will not come. Line 1 for one press, line 2 for more. The headline names the case in the model and is not shown. It speaks through the window's log, which is visible for the whole of a CR30 session.*

> **A reading taken before Ready was not used**
>
> One reading was taken before this window was ready for it, so it was not used. Take the reading again.
> {n} readings were taken before this window was ready for them, so they were not used. Take the reading again.

## M-PROPOSED. Messages awaiting review

*This section is where a new or revised message goes: add it to
`workflow/measurement_messages.py` with `approved=False`, write it here, and
list it on the issue. `tests/test_message_catalogue.py` holds the two in step —
it fails if a proposed message is missing from this section, and equally if an
approved one is left sitting in it.*

### M-PRINT-JOB-NOT-AS-SENT · PROPOSED · a window when the job read back from the printing system does not carry what ChromIQ sent, beta 15

*New 2026-10-08 (beta 15). Replaces the beta 14 window "Colour Management Lock Not Verified". {details} is one line per key, "{key}: {got} (ChromIQ sent {want})"; the line "The chart could not be given the job's own profile, so macOS may convert its colours." is added when, besides, the chart on the macOS dialog route could not be given the job's paper profile. When that is the only problem, M-PRINT-JOB-UNTAGGED is shown instead. Sebastian, 2026-10-08, did not approve this wording: "the reviewer said it is wrong. so i probably can't approve this" (the opening sentence was wrong for the untagged case, which now has its own window).*

> **The print job is not what ChromIQ sent**
>
> The job was sent, but the printing system shows other colour settings on it than ChromIQ asked for:
>
> {details}
>
> The sheet may not carry the chart's own colours, and a measurement of it would not describe your printer. If it has not printed yet, cancel it in the printer's queue and print again.

### M-PRINT-JOB-UNTAGGED · PROPOSED · a window when the chart could not be given the paper profile its job prints with, macOS dialog route, beta 15

*New 2026-10-08 (beta 15 builder round). The macOS dialog route tags the chart with the paper profile the job prints with (the output intent macOS gives it), so the conversion macOS applies is the identity. When that profile could not be read, or the job read back from CUPS prints with another one (compared byte for byte), and nothing else on the job differs, this window says so. Asked for by Sebastian on 2026-10-08: M-PRINT-JOB-NOT-AS-SENT's opening sentence ("other colour settings than ChromIQ asked for") was wrong for this case. The advice names the other route, which tags the chart itself.*

> **The chart may not print with its own colours**
>
> The job was sent, but ChromIQ could not give the chart the profile this job prints with. macOS may therefore change the chart’s colours on the way to the printer, and a measurement of that sheet would not describe your printer.
>
> If it has not printed yet, cancel it in the printer’s queue and print again. If this message comes back, turn off “Use default macOS printer dialog” in Preferences and print from the Print Chart tab directly.

### M-PRINT-PAPER-PROFILE-UNKNOWN · PROPOSED · the direct route does not know which paper profile the driver of this model chooses, Print Chart tab, beta 15

*New 2026-10-08 (beta 15 builder round). Basti: the direct route sends the paper profile the vendor's own print dialog would choose for the medium. ChromIQ knows it from the installed driver's own table (Canon IJ media database, Epson PDEData.dat), from the tables measured and shipped with it (`data/printer_paper_profiles.json`: PRO-300/310/200S/1000/1100/100, ET-8550/18100, SC-P700/900/5300/800, Stylus Photo R2000/R3000), or from the user's own earlier prints through the macOS dialog (`workflow/printer_memory.py`). For any other Canon IJ or Epson model it must not guess silently: this window comes before the confirmation window. {printer} is the queue, {medium} the paper type as the driver names it, {profile} the driver's standard setting for the paper profile (the PPD's default, which Epson labels "None"), which a job sent anyway carries. Review 2, 2026-10-08: "standard profile (None)" was untrue for an Epson, so the sentence names the setting. The buttons: "Use the macOS Print Dialog" (the default: prints this chart through the dialog, with the printer already chosen), "Print Anyway", "Cancel". A printer with no paper profiles at all (generic, driverless, Xerox, Gutenprint) never sees it: it prints exactly as in beta 14.*

> **ChromIQ does not know this printer’s paper profiles yet**
>
> ChromIQ does not know which paper profile the driver of {printer} chooses for the paper type “{medium}”. A print from Photoshop gets that paper profile from the printer’s own print dialog, and the chart has to print in the same state.
>
> Print this chart through the macOS print dialog and pick the same paper type there. The driver then chooses the paper profile itself, and ChromIQ remembers its choice, so later charts for this printer and paper type can go straight to the printer.
>
> If you print straight to the printer anyway, the chart goes with the driver’s standard setting for the paper profile ({profile}), which may not be what your prints from Photoshop get on this paper.

### M-PRINT-VERIFY-ROUTE · PROPOSED · what a verification print needs, the Print Chart tab, macOS, B3 (4.3.4 beta 1)

*New 2026-10-10. Knut, #182 [6095262115](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6095262115): with Run type Verification and the macOS print dialog on, the notice on the Print Chart tab "seems to describe a profiling run, not a verification run". It is the one notice of the macOS dialog route, the same for every run type; neither §M nor `verification_printing_and_target.md` has a text for a verification print. Measured for this proposal (report folder `2026-10-10_434b1_B3`, capture queues with a generic PostScript PPD and a profile assigned in ColorSync, as on Knut's HP CLJ5550): the chart's numbers reach the printer unchanged on both routes, 1,372,807 of 1,372,807 chart pixels identical, with the dialog's Color Matching panel left alone and with another profile chosen in it, because ChromIQ gives the chart whichever profile the job prints with; but the dialog route hands a PostScript printer the chart as calibrated RGB (CIEBasedABC) and the direct route as device RGB, which a PostScript interpreter renders differently (Ghostscript: 2.3 levels mean, 26 max, on the patches). Proposed to be shown under the Print Chart tab's notice for a verification run on macOS, both routes; the second paragraph only on the dialog route. Not shown anywhere until approved.*

*Review R3, 2026-10-10 (report folder `2026-10-10_434b1_R3`): Sebastian approved this text on condition that every statement in it is true. Two were not. Choices made in the dialog's own Color Matching sheet (driven on screen, not injected into the settings) left the chart unchanged on a PostScript queue with a ColorSync profile, a Canon PRO-300 and an Epson ET-8550 (another profile picked; the vendor's matching chosen on the PostScript queue and the Canon), but the Epson's "EPSON colour matching" reaches the job as EPIJ_OSColMat=1, which ChromIQ neither sets back nor checks, so "Choosing another profile there does not apply it to the chart either" could not be kept as a promise about the panel. And on a generic CMYK raster queue (the CUPS sample HP DeskJet driver) with a ColorSync profile, macOS ignores the output intent and converts from the chart's tag, so the re-tag changes the raster: "If its Color Matching panel names a profile, ChromIQ gives the chart that same profile … so macOS does not change the chart's colours" is untrue there. The second paragraph now names only the printers where it was measured, and the third says what the PostScript stream carries (a CIEBasedABC colour space with sRGB's D65 white point and Rec. 709 matrix) instead of "calibrated RGB". Not approved: back to Sebastian in these words.*

> **Printing a verification chart**
>
> Print this chart on the same printer, paper, media type and quality as the profiling chart this profile was made from, and by the same route (the macOS print dialog, or straight to the printer). The profile describes the printer only in that state.
>
> Leave the colour settings in the macOS print dialog as they are, including its Color Matching panel. When macOS prints the job with a Canon or Epson paper profile, or with a profile set for a PostScript printer in ColorSync Utility, ChromIQ gives the chart that same profile after you close the dialog, so macOS does not change the chart’s colours.
>
> On a PostScript printer the two routes do not reach the printer in the same form: the dialog sends the chart’s colour values marked as sRGB, which the printer converts with its own colour rendering, and the direct route sends them as the printer’s own RGB. Print the profiling chart and its verification charts the same way.

### M-PRINT-JOB-TAGGED-INTENT · PROPOSED · the status line when the chart went with the job's own profile and the job names no paper profile, macOS dialog route, B3 (4.3.4 beta 1)

*New 2026-10-10. M-PRINT-JOB-CONFIRMED line 3 ("The chart went with that same profile attached…") follows only its line 1, which names a paper profile. On a printer without paper profiles, such as Knut's HP CLJ5550 on a generic PostScript queue with his own profile assigned in ColorSync, ChromIQ did give the chart the job's profile, and the status line said only "Sent as job 50. The printing system confirms it carries application colour matching." while the dialog he had just closed showed ColorSync and his profile. Proposed to follow M-PRINT-JOB-CONFIRMED line 2 in that case. The headline names the case and is not shown; {profile} is the profile's name as ColorSync gives it. Not shown anywhere until approved.*

*Review R3, 2026-10-10: Sebastian approved this text on condition that every statement in it is true. It is true on a PostScript queue with a ColorSync profile (1,372,807 of 1,372,807 chart pixels unchanged in the PostScript the printer receives, the Color Matching sheet untouched, another profile picked, or "In printer" chosen) and untrue on a generic CMYK raster queue with a ColorSync profile, where the chart's tag changes the raster (its md5 differs from the untagged job's, which equals a job with no profile at all). The words stay; where it may be shown is restricted to PostScript queues (a PPD with no CUPS raster filter). Not approved and not shown: back to Sebastian with that restriction.*

> **The chart went with the profile its job prints with**
>
> The chart went with the profile macOS prints this job with ({profile}) attached, so macOS leaves its colours unchanged.

### M-VERIFY-UNCHECKED-METRICS · PROPOSED · what the report does with a metric the chart cannot answer — the presets window, with one line in the Measure tab pre-flight

*New for 4.3.0-beta.35 (#182). Knut, 2026-09-22: a report that judges metrics
which cannot be calculated carries a warning for each of them, and the reader
should be told, before anything is printed, that those metrics can be switched
off in Report limits by setting the threshold to "-", so that what is handed to
a customer holds only the metrics that were actually checked.*

**⚠ HIS PREMISE WAS MEASURED AND IT HOLDS IN A MINORITY OF STATES. Two
questions are put back to him below; nothing here is settled.** An adversary
round drove every combination in the real app:

* **the limit SET decides whether such a row appears at all.** Only the two
  ISO-derived sets put a real limit on the rows a ChromIQ verification chart
  cannot answer; the five ChromIQ sets put none, so on them the row is simply
  left out. "A report judging metrics that cannot be calculated carries a
  warning for each" describes 2 of the 7 selectable sets. On the other five the
  remedy is also a no-op, because the threshold is already "no limit".
* **the report TYPE decides too.** One run, four buildable types: the numbered
  note exists on T2 alone. T4 is ungraded, so `_note_the_absences` returns
  early and no row carries one; T3 does not carry those rows at all; T1 carries
  no metric rows. The pre-flight cannot know the type (it asks `assess_any`,
  which unions every combination), so anything it says about notes is wrong on
  three of the four.
* **"-" cannot be typed.** One row, both states: typing "-" into the threshold
  box leaves `hasAcceptableInput()` False and the cell silently reverts on
  focus-out, with the old value still stored. The gesture is setting the spin
  box to ZERO, which it displays as "–" through `setSpecialValueText`. The mark
  is an en dash everywhere in the app and his message spelled it as a hyphen.
* **the lever is often absent.** On a locked run every column is read-only,
  photographed on his own demo project with zero spin boxes in the whole table,
  and the two ISO columns are read-only in every state.

*So the text below says what is invariant, names what decides the rest, and
qualifies the instruction instead of promising it works everywhere.*

**⚠ TWO QUESTIONS FOR KNUT, neither answered:** (1) he asked for this in the
pre-flight popup AND in the presets window, and in the same specification he
asked that the popup not *"become too long"*. Measured on screen, appending the
full paragraph took the popup's `minimumHeight()` from 798 px to 958 in English
and 974 in German, on a window with no scroll area, against about 918 px of
usable height on a 13-inch MacBook Air: the OK button and his own "do not show
this again" tick would be off the bottom of the screen. So the popup carries
one line and the window carries the paragraph. (2) Since most sets already
leave these rows out, is the behaviour he wants actually the ISO sets' one, and
should the ISO-derived sets stop showing rows nothing can answer?

**Question (1) ANSWERED, 2026-09-23** ([5795087247](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5795087247),
*"Leave the window wider as previously specified"*, R2 of 5781645939). From
beta 39 the pre-flight carries the FULL paragraph below, heading and body, in a
box widened to 968 px; measured on screen it is 827 px tall in English and 875
in German. The one line stays, used only where the shown box would not fit the
screen's work area (a 13-inch Air with the Dock at the bottom, about 860 px).
`docs/design/measurement_report_limits.md` §21.3. The WORDING of both is
unchanged and still waits here. Question (2) was answered in the same comment
(the general rule for unanswerable rows) and is not built by this change.

*The pre-flight's one line, appended under its metric list only when the chart
really falls short of something AND the wide box would not fit the screen:*

> A metric this chart cannot answer is never judged and can never make the report fail. Whether it is shown at all is decided by the limit set, and the window named above says how to change that.

*The paragraph, in the right-hand pane of "Which presets can be used for
verification", under the list of what the chart cannot answer:*

> **What the report does with a metric this chart cannot answer**
>
> It is never judged, and it can never make the report fail.
>
> Whether it appears at all is decided by the limit set the report is judged against. Where the set puts a real limit on the metric, the metric is shown reading N-A, and on a report type that carries notes it also carries one saying what it needed. Where the set puts no limit on it, the metric is left out; that is what ChromIQ's own sets do with the metrics above.
>
> To leave a metric out yourself, set its threshold to zero in the report's own limits, the first column of Edit limits… in the Measurement Report window. The box shows zero as “–”.

*Revised 2026-09-23 for beta 38: the paragraph said "row" four times in the one window Knut's beta 25 item 4 cleared of the word; it says "metric" now. Still PROPOSED.*

*Revised for beta 40 (K31, Knut [5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743)): the last paragraph said "in the run's limits, where those limits can still be edited". A run holds no limits of its own any more and nothing is locked, so the lever is the report's own column. Still PROPOSED.*

*Neither window is report text, which is why they may name a control: his other
ruling of the same day is that no report text explains how to use ChromIQ, and
both of these exist to help somebody decide what to print.*

### ⏳ Awaiting confirmation — the log rule no longer describes what CR30 does

**Confirmed by:** *nobody yet.* This is a discrepancy report and a proposed
amendment, not a change to the rule. Nothing here is in force.

§M says that a message whose wording is not yet approved says its piece **in the
log** until it is. For the CR30 messages that is no longer true of any of them:

| message | where its text appears | wording |
|---|---|---|
| M-CR30-CALIBRATE | window | `approved=False` |
| M-CR30-CALIBRATE-BLACK | window | `approved=False` |
| M-CR30-MAGNET | window | `approved=False` |
| M-CR30-INSTRUMENT-GONE | window | `approved=False` |
| M-CR30-READ-FAILED | window | `approved=False` |

Each window exists because **Basti asked for that window**, in his own words,
after meeting the fault himself — the magnet one after a MacBook recalibrated
his instrument mid-chart, the read-failure one after missing a grey line under
the buttons, the instrument-gone one on 2026-08-30: *"if this is an important
message this should be in a pop up windows with benefitial options for this
case"*.

So this is not four exceptions accumulating. It is the rule having stopped
describing practice, which is worse, because the next message will break it
without anyone noticing.

**Proposed amendment, for Basti or Knut to accept or reject:**

> Proposed wording may be shown in a window when the window itself has been
> asked for. The WORDING remains §M-PROPOSED and unapproved either way, and
> still needs review before it can move to §M.

The distinction that matters is preserved: a ruling that a *window* should exist
is not an approval of the *text* inside it. What the log rule was protecting —
that nobody's unreviewed prose quietly becomes the specification — is untouched,
because none of these five is marked approved.

**If this is rejected**, the honest alternative is to put all five back to
log-only, which reverses four decisions Basti made deliberately. Recording it
that way so the choice is visible rather than drifted into.

*Raised by the round-3 review, 2026-08-30.*


### RETIRED for beta 40 (K31), never approved: the unlock question, after the door changed (B8-391)

*Retired 2026-09-23 with the control it belonged to. Knut, #182
[5801677743](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5801677743):
"I agree that the 'Unlock this run's limits' is no longer needed, and it causes
confusion in the functionality." The checkbox, this question window, its
re-lock twin ("Lock this run's limits again?") and the Preferences option that
allowed unlocking are gone from the code and the language files
(`measurement_report_limits.md` §25). Neither the text in force nor the proposed
replacement below is shown anywhere; both are kept only as the record of what
was asked.*

**Confirmed by:** *nobody.* It was a proposed replacement sentence, never a
message in force.

Knut, 2026-09-18, reading the window that appears when **"Unlock this run's
limits"** is ticked:

> *"This run (run3) has 2 dated verifications. Unlocking lets you change the
> run's limit set and its numbers. Every dated report of this run will then be
> recalculated with the numbers you set, and the previous reports are kept
> first, in a reports/old folder beside each date. Nothing is deleted.
> Continue?"*
>
> *"The description is wrong. All dated reports shall NOT be recalculated, only
> the selected report will be recalculated and report text recreated according
> to new values."*

**The behaviour changed first, and the sentence follows it.** Unlocking now
recalculates nothing at all: it lets the user change the run's limit set and
its numbers, and what a change then does belongs to the ONE report named in
"Report shown" (N.2/N.3 of §5 of `measurement_report_limits.md`). So the clause
that promised a recalculation of *"every dated report of this run"* described
something that cannot happen and **was removed the moment it became false** —
the same course B8-384 took at the "Judged against" door an hour earlier. What
is on screen today is the words that were already there:

> **Unlock this run's limits?**
>
> This run (run3) has 2 dated verifications. Unlocking lets you change the
> run's limit set and its numbers.
>
> Nothing is deleted. Continue?

**Proposed replacement, for Knut to accept, reject or reword.** It says what
the door now does rather than only dropping what it no longer does:

> **Unlock this run's limits?**
>
> This run (run3) has 2 dated verifications. Unlocking lets you change the
> run's limit set and its numbers.
>
> Nothing already saved is recalculated. The report you have open is rebuilt
> when you press Generate report, and every other report of this run stays
> exactly as it is. Continue?

*Raised by the B8-391 round, 2026-09-18.*


*The two below are **revisions**, not new messages. Both were approved by Knut
on 2026-08-04, but one step in each instructed "(with colour management on)" —
a setting ChromIQ deliberately locks off on every print path
(`postscript_generator.py`, `cups_printer.py`, `workflow/native_print_macos.py`;
established in `verification_printing_and_target.md` §1). Feature A gives the
instruction a real control to name: the Print Chart tab's **Colour** row. Only
that one step changed in each; every other sentence is the approved text.*

### M-VERIFY-NO-PROFILE · PROPOSED revision · a verification with no profile to check — §S1.2

*Revision of the message approved 2026-08-04: step 6 now names the Print Chart
tab's "Colour" row instead of instructing colour management on. Raised when Run
type = Verification and the selected run has no built profile; also what the
greyed Start button's tooltip says. The numbers below are escaped so both
halves of the list line up exactly as they do on screen — Knut, beta.132: "the
numbered list from 4 to 7 does not have the same indent as points 1 to 3".*

> **This run has no profile to verify yet**
>
> A verification checks a finished profile — but this profile run doesn't have a built profile yet.
>
> To build the profile first:
> &nbsp;&nbsp;1\. Set "Run type" to "Profiling".
> &nbsp;&nbsp;2\. Create, print and measure the profiling chart as normal — its measurement is stored in the run folder.
> &nbsp;&nbsp;3\. Build the profile on the Build Profile tab (this makes the profile's .icc / .icm file).
>
> Once the profile exists, you can verify it:
> &nbsp;&nbsp;4\. Set "Run type" back to "Verification".
> &nbsp;&nbsp;5\. Create a verification chart in the Create Chart tab.
> &nbsp;&nbsp;6\. Print that chart from the Print Chart tab with "Colour" set to "Through the profile" — ChromIQ applies the profile for you and keeps the printer's own colour management off.
> &nbsp;&nbsp;7\. Measure it here with "Run type" = "Verification" — the result is kept in a dated folder under this run's "verifications" folder.

### M-VERIFY-NO-CHART · PROPOSED revision · a verification with no chart to measure — §S1.3

*Revision of the message approved 2026-08-04: step 2 now names the Print Chart
tab's "Colour" row instead of instructing colour management on. Since beta.128
Start Measurement needs a `.ti2`, so a run without its verification chart meets
this as the greyed button's tooltip; the window remains for the case where a
chart exists but the profile does not.*

> **No verification chart for this run yet**
>
> This run has a finished profile, but you haven't created its verification chart.
>
> &nbsp;&nbsp;1\. Go to the Create Chart tab and, with "Run type" = "Verification", create the verification chart (a smaller chart is fine).
> &nbsp;&nbsp;2\. Print it from the Print Chart tab with "Colour" set to "Through the profile" — ChromIQ applies the profile for you and keeps the printer's own colour management off.
> &nbsp;&nbsp;3\. Come back here with "Run type" = "Verification" and measure it — the result is stored in a dated folder under this run's "verifications" folder.

### M-CR30-STOCK-READER · PROPOSED · a CR30 chart while Preferences selects stock chartread — Measure

*New message (#159, 2026-08-28). A CR30 chart carries `TARGET_INSTRUMENT
"CR30"` — the honest name the device reports for itself, by ruling. Stock
ArgyllCMS `chartread` matches that keyword against its own instrument table and
refuses the chart before reading a patch, so a CR30 chart is readable only by
ChromIQ's own chartread fork. Raised BEFORE anything is armed, when the loaded
chart is a CR30 and Preferences → Measurement → "ChromIQ chart-reading engine"
is switched off (B8-1643: the control became a checkbox; the wording followed on
2026-09-28, still awaiting approval). The window offers to change that setting; declining
cancels the measurement rather than starting one that cannot succeed. This is
the guard that keeps `_blocked_by_unusable_target_instrument`'s claim true:
"CR30" is in `KNOWN_INSTRUMENTS`, so that window no longer fires for a CR30
chart — and this one asks the question that is still open.*

> **This chart can only be read by ChromIQ**
>
> This chart was made for the CR30, and ChromIQ reads that instrument itself. Standard ArgyllCMS chartread does not know the CR30 at all: it would refuse the chart before reading a single patch, whichever instrument you have connected.
>
> Right now, "ChromIQ chart-reading engine" in Preferences → Measurement is switched off, so ArgyllCMS chartread reads your charts. Switch it on and this chart measures normally. The setting applies to every chart, and every other chart reads the same either way.
>
> Nothing is wrong with the chart, and nothing you have already measured is affected.

### M-CR30-READ-ENDED · PROPOSED · an engine run failed on a CR30 chart, and there is no second reader — Measure

*New message (#159, 2026-08-28). The mirror of M-CR30-STOCK-READER, seen from
the other end of the run. When ChromIQ's own chart-reading engine fails,
`MeasureManager` restarts the measurement on stock ArgyllCMS chartread and says
so (M-ENGINE-FELL-BACK); when it fails partway through a chart it does the same
with `-r` and promises that "every strip you have already measured has been
saved and will be kept". **Neither promise can be kept for a CR30 chart** —
stock chartread matches `TARGET_INSTRUMENT "CR30"` against its own instrument
table, finds nothing, and errors with "Unrecognised chart target instrument"
before the first patch. So all three fallback sites are gated off for such a
chart and the run ends on the helper's own exit. This is what the user is told
instead: one honest ending rather than a rescue that fails a second time.
`{reason}` is the helper's own sentence, captured from its stderr prose — the
same failure used to render as "unknown error".*

> **The measurement stopped**
>
> Reading this chart has stopped before it finished.
>
> This chart was made for the CR30, and ChromIQ reads that instrument itself. There is no second reader to try: standard ArgyllCMS chartread does not know the CR30 and would refuse the chart before reading a single patch, so ChromIQ has not started it and has ended the measurement here rather than showing you a second failure.
>
> Nothing you have already measured is lost — every patch that was read is on disk, and you can carry on from it by ticking "Refine / resume existing measurement (-r)" before you press Start again.
>
> What went wrong: {reason}

### M-CR30-CALIBRATE · PROPOSED · calibrate the instrument before the measurement — Measure

*New message (#159, 2026-08-28). **Ruled by Basti**: the window offers a
Calibrate button and ChromIQ triggers the calibration itself rather than asking
for a button press — on **both** transports. EXP-MEAS-004 established the host
trigger over USB; EXP-BLE-012 established it over Bluetooth on 2026-08-28,
after he pushed back on a "no BLE host trigger is known" that turned out never
to have been tested (host trigger 3.9222 %R against his own button press
3.9416 %R on the same surface, 0.0347 %R apart).*

*This **deliberately reverses** the documented rule that a ChromIQ backend never
sends the trigger command. That rule existed because the host cannot see a
magnet and so cannot tell a measurement from a calibration; here the calibration
is the whole intention. His ruling, his instrument.*

*The warning is **not** about magnets. The magnet is what makes the command a
calibration at all — telling the user to keep magnets away would tell them to
remove the thing the operation requires. The hazard is **which face of the cap**
is at the aperture: calibrating against the cap's green side is what corrupted
the research unit (81.10 → 149.10 %R), and the error is one-sided and invisible
in every reading afterwards.*

*It must not claim success. When the magnet gate engages the device reports the
firmware's nominal tile constant whatever is under the aperture — white tile and
green face come back bit-identical, max absolute difference across all 31 bands
0.0 — so there is nothing to check, no number worth showing, and no tick or
green mark may appear. The window is shown on every Start unless the run's
`disable_initial_cal` is set, which is hard-coded False in Guided and is the
existing "Skip initial calibration" box in Manual, exactly as he ruled.*

*The calibration reading is **not** counted as a measurement, and that needs no
enforcing: the window runs before the helper is started, so no prompt is
outstanding and there is nowhere for a value to go.*

> **Calibrate your CR30 before measuring**
>
> Your instrument takes a white calibration before it measures a chart. It takes a couple of seconds and ChromIQ does it for you — there is no button to press on the instrument.
>
> Put the magnetic cap on the measuring end, with the WHITE TILE facing the opening. The cap is reversible and the other side is green, so it is worth a glance: white towards the instrument.
>
> Then press "Calibrate now".
>
> ChromIQ cannot check the result for you. The instrument reports the same value whatever is under the cap, so a calibration against the green side looks exactly like a good one and would quietly shift every reading that follows. Your eyes are the only check there is.
>
> If you would rather not calibrate now, press Cancel — nothing has been changed and any measurement this run already has is untouched.

### M-CR30-READ-FAILED · PROPOSED · a reading did not arrive complete — Measure

*New message (#159, 2026-08-30). The behaviour already existed and was correct:
a reading that does not arrive complete is refused, the patch is armed again,
and the operator presses the instrument's button once more. What was wrong was
where ChromIQ said so. Basti, with a screenshot of it as a line of grey text
under the buttons:* **"a message like this would be better in a pop up so the
user is aware of it instead of ruining a whole measurement session when this is
unnoticed"**.

*He has the cost right. The failure itself is one button press. NOT NOTICING is
what ruins the session: the instrument sits waiting, the operator believes they
have already pressed it, and nothing moves — and there is no other cue, because
a refused reading makes no sound and leaves the preview unchanged.*

*The window is MODELESS, and that is not a detail. The remedy is to press the
button on the instrument, so a window that had to be dismissed first would stand
between the user and the only thing that puts it right — and a press made while
it was up would arrive behind a window still asking for it. It closes itself
when the chart moves on, which is the same event as the reading having arrived,
and the text promises exactly that so the user is not left wondering whether to
close it.*

*ONE WINDOW PER PATCH, not one per refusal. A flaky link can refuse the same
patch five times before the retry limit gives up (M-CR30-PATCH-GAVE-UP takes
over there). Five windows for one stuck patch is a worse interface than none.
The second and later refusals of the same patch keep the log line and the status
flash they always had.*

*{reason} is the instrument's own words and they are technical — "no usable
reply among the only candidate in 200 bytes" and the like. They stay: the
sentence above them says what to do without needing them, and the detail is what
makes a report worth reading when somebody sends one in. The same screenshot
also showed "1 candidate(s)", which is fixed at source — this project writes
singular and plural out.*

> **That reading did not come through**
>
> The reading for patch {loc} did not arrive complete, so ChromIQ has not used it — nothing wrong has gone into your measurement file.
>
> Press the button on the instrument again, with it resting on patch {loc}. This window will close by itself when the reading comes through.
>
> What the instrument reported: {reason}

### M-INSTRUMENT-BUSY · PROPOSED · two windows reaching for one instrument — Measure and Tools

*New message (#159, 2026-09-02). Tools ▸ "Read single patches" can now read a
CR30, and it reads it the way the Measure tab does: with ChromIQ's own driver,
in this process, over USB or Bluetooth. That is the first time two windows in
ChromIQ can reach for one instrument.*

*Nothing already in the app could see it happening.* `ArgyllRunner.is_running`
*is the question every guard asks, and it answers purely from PROCESS state. The
Measure tab's CR30 session is visible to those guards only by accident, because
`chromiq-chartread -xx` is a real process even though it opens no instrument. A
window driving the reader directly spawns nothing at all.*

*The failure this prevents is not an error. Over Bluetooth a CR30 accepts one
connection and stops advertising once it is taken; over USB two openers
interleave their bytes on the same port. And the instrument holds its last
reading indefinitely and hands it back to whoever asks, so what the second
window gets is a plausible colour belonging to somebody else's patch. That is
the same class of fault the whole CR30 bridge exists to prevent, and it is worse
here because neither window has any reason to doubt what it was given.*

*So the claim on the instrument is explicit and process-wide, taken by whichever
window opens the device. It is refused in BOTH directions and the message is the
same either way, with {where} naming the window that has it: "the Measure tab"
or "Tools ▸ Read single patches". Refusing costs nothing at the moment it
happens, because it is refused BEFORE anything is opened, measured or written.*

*Only ChromIQ's own reader takes the claim. Two ArgyllCMS sessions already
exclude each other through the process guard, and a ColorMunki chart read
alongside a CR30 spot read is two different instruments doing two different
jobs, which is allowed and should be.*

> **Your instrument is already in use**
>
> ChromIQ is measuring in {where}, and your instrument can only answer one window at a time.
>
> Finish or stop that measurement, then start this one again.
>
> Nothing has been changed and nothing has been measured.

### M-CR30-LEARN-TILE · PROPOSED · teaching one unit its own white-tile value — Measure

*New message (#159, 2026-08-30). The magnet guard works by recognising the
value the instrument returns when something magnetic is at the opening — it
stops measuring and hands back its stored white tile. That value was HARD-CODED
from one particular unit. The only other CR30 anyone has measured reads up to
4.69 %R lower, which is 94 times the tolerance, so on that instrument the guard
matched nothing and its owner had no protection at all: a gated reading looks
exactly like an ordinary patch colour and goes straight into the profile.*

*The value cannot be taken from the calibration itself. After a white
calibration the instrument's stored slot is ZERO-FILLED — the code already
measures this and passes `allow_dark=True` because of it — so learning there
would store a spectrum of zeros and arm a guard that matches nothing.*

*It has to come from a capped press, and that is safe to ask for. Measured
across EXP-TILE-002/003/004 on 2026-08-30: a capped press does not damage the
white reference. The paper readings afterwards moved -3.43 %R in one run and
+4.72 %R in the next, and a damaged reference is monotonic; repositioning alone
accounts for 2.36 %R with no cap involved at all. The window says so, because a
user who has read the calibration window's warnings has every reason to be
nervous about pressing the button with the cap on.*

*Offered once per session, only while the guard is unarmed for that instrument,
and always refusable. Skipping costs nothing that is not already lost today.*

*The press count is now asked of the OPEN TRANSPORT and shown as the
instruction, with a pictogram of the capped instrument carrying a downward
arrow and “1×” or “2×”. The window used to be titled "One press teaches…" and
buried the two-press Bluetooth rule four paragraphs down: Basti pressed once
over Bluetooth on 2026-08-30, confirmed, and the window sat there until he
force-quit the app; pressing twice worked immediately. Two is the default when
the transport cannot be read — being told twice and having it accept after one
costs nothing, while being told once when two are needed is a dead end.*

*A tile is learned PER TRANSPORT, and this is by design, not a defect. Over USB
the key is the unit's serial; over Bluetooth there is no serial, so the key is
the address the OS hands back. Basti's own store holds the same 31 values twice
— once under `PT694D01E7` and once under a `ble:` key — because he learned it
over each. The cost is one extra learning press per connection type; the
alternative, arming one unit's constant on an instrument that has not been
learned, is the exact fault this feature exists to remove.*

**Two bodies, chosen by the OPEN TRANSPORT** (`count_key="presses"`,
rendered `M_CR30_LEARN_TILE.render(presses=1|2)`). Each states its own
press count first and then explains it, and each names what the OTHER
transport needs. One shared body with a sentence injected into it left both
windows saying *"Why the difference"* about a difference neither of them
had mentioned, and the one-press window never said that Bluetooth needs two
(Basti, 2026-08-31). No em dashes, by the same ruling.

**Over USB (one press):**

> **Teach ChromIQ your instrument's white tile**
>
> This is a one-off, and it makes every measurement afterwards safer.
>
> If anything magnetic touches the measuring opening, such as a laptop lid under your paper, a magnetic desk mat, or the instrument's own cap, the CR30 stops measuring and hands back the value of its white tile instead. That value looks like a perfectly ordinary patch colour, so without knowing what it is, ChromIQ cannot tell it from a real reading.
>
> Every instrument's tile value is slightly different, so ChromIQ has to learn yours from your own device.
>
> LEAVE THE CAP ON, exactly as it is now, and press the button on the instrument ONCE. This window closes as soon as ChromIQ has the reading.
>
> One press is enough over USB, because the instrument itself tells ChromIQ that the opening was covered, so a single reading proves what it is looking at. Over Bluetooth the instrument does not say, and ChromIQ has to ask for two.
>
> The reading is not part of your measurement and nothing is written to your chart.
>
> This does not change your calibration. A press with the cap on reads the tile that is already the instrument's reference, so there is nothing for it to spoil.
>
> You can press “Not now” and carry on measuring as usual. Everything works exactly as before, and ChromIQ will offer this again next time.

**Over Bluetooth (two presses):**

> **Teach ChromIQ your instrument's white tile**
>
> This is a one-off, and it makes every measurement afterwards safer.
>
> If anything magnetic touches the measuring opening, such as a laptop lid under your paper, a magnetic desk mat, or the instrument's own cap, the CR30 stops measuring and hands back the value of its white tile instead. That value looks like a perfectly ordinary patch colour, so without knowing what it is, ChromIQ cannot tell it from a real reading.
>
> Every instrument's tile value is slightly different, so ChromIQ has to learn yours from your own device.
>
> LEAVE THE CAP ON, exactly as it is now, and press the button on the instrument TWICE. This window closes as soon as ChromIQ has both readings.
>
> Two presses are needed over Bluetooth, because the instrument does not tell ChromIQ that the opening was covered. ChromIQ accepts the value only when two readings come back identical, which real measurements never do. Over USB the instrument does say, and one press is enough there.
>
> The reading is not part of your measurement and nothing is written to your chart.
>
> This does not change your calibration. A press with the cap on reads the tile that is already the instrument's reference, so there is nothing for it to spoil.
>
> You can press “Not now” and carry on measuring as usual. Everything works exactly as before, and ChromIQ will offer this again next time.

### M-CR30-TRIGGER-NOT-ARMED · PROPOSED · the keyboard trigger, on an instrument that has not been learned — Measure

*New message (#159, 2026-08-30). Pressing the instrument's own button moves
it: measured at ~0.5 %R against its own repeat noise of 0.05 %R when nothing
touches it (EXP-TILE-003/004). Taking the reading from the keyboard removes that
error, which is worth roughly a factor of ten in steadiness — Basti asked for it
for exactly this reason: "this would help to keep the device more stable because
pressing its button introduces shake".*

*But a reading ChromIQ asks for cannot report the magnet gate. Byte 58 marks a
solicited reply and the flag at offset 24 is meaningful only in the unsolicited
header a button press produces, so `button_header_is_gated` correctly answers
"cannot tell". The learned tile signature is what replaces the flag — and it is
an exact replacement, because a gated host trigger returns the constant
bit-for-bit (EXP-MEAS-004, 2026-08-30: worst-band delta 0.0000 %R).*

*So the trigger is refused on an instrument whose tile is not yet known, rather
than offered in a state where a magnet would go unnoticed. The window explains
the one-off step that unlocks it and makes clear that nothing is broken
meanwhile.*

> **Measuring from the keyboard needs one quick setup step**
>
> ChromIQ can take each reading for you when you press the space bar, so the instrument never moves between patches — that makes readings about ten times steadier than pressing its own button.
>
> To do that safely, ChromIQ first needs to know what your instrument's white tile looks like, so it can tell a real patch from a covered opening. That takes one press: after calibrating, leave the cap on and press the instrument's button once when ChromIQ asks.
>
> Until then, keep using the button on the instrument — every reading still works exactly as before.

### M-CR30-MAGNET · PROPOSED · a magnet recalibrated the instrument mid-chart — Measure

*New message (#159, 2026-08-30), and it comes from a real incident rather than a
hazard analysis. Basti rested his chart on a MacBook while measuring, and the
laptop's magnets reached straight through the sheet. The instrument did what it
always does with a magnet at the aperture: it took a WHITE CALIBRATION from
whatever it was sitting on — in this case the patch he was trying to read.*

*ChromIQ's guard fired and refused the reading, which was right. Then it re-armed
the patch, told him to press the button again, and let the session carry on — so
every patch after that was measured against a reference that had just been
overwritten. He noticed only because the numbers looked wrong.*

*So the refused reading is the least of it, and this window says so. The session
STOPS. The window offers to retake the white calibration on the spot — with the
instrument's own command, which is a remedy the app can actually perform, unlike
the old advice to seat the cap and press the button, which mid-session simply
produces another gated reading and another refusal.*

*Nothing measured BEFORE the moment is affected, and the window says that too:
the refusal happens before any reading is accepted, so the suspect set is empty
and there is nothing to mark or discard. "Your calibration is wrong" without
that sentence invites someone to bin work that is perfectly sound.*

*⚠ Prevention is impossible, and the text does not pretend otherwise. The only
signal that a magnet is present arrives INSIDE the reading it has already
ruined, and a probe reading would itself be the calibration. Detection before
acceptance is the most that can be done — and it is enough, because it keeps the
suspect set empty.*

*⚠ Known limit: over Bluetooth on a unit other than this one, the first gated
press is not yet detectable — there is no gate flag on that transport and the
tile signature is one unit's constant. USB catches it on every unit.*

> **Your CR30 has just recalibrated itself**
>
> Something magnetic was against the measuring opening, and that changes what the instrument does: instead of measuring your patch, it takes a white calibration from whatever it is resting on.
>
> The usual culprit is not obvious. A laptop has magnets in its lid and body, and they reach straight through a sheet of paper; so do fridge doors, magnetic desk mats, tool trays and the instrument's own cap.
>
> EVERYTHING YOU MEASURED BEFORE THIS IS SAFE, and is already saved. ChromIQ refused this reading before using it, so nothing wrong has gone into your measurement file.
>
> But nothing more can be measured until the white calibration is taken again — until then every reading would be wrong by an amount nothing afterwards could detect.
>
> Move your chart onto something non-magnetic — a book, a pad of paper, a wooden desk — then press “Recalibrate now” and ChromIQ will take the white calibration for you and carry on from the patch you were on.
>
> What ChromIQ detected: {reason}

### M-CR30-CALIBRATE-BLACK · PROPOSED · the dark reference, taken against air — Measure

*⚠ REVISED 2026-09-07, wording only, and it is still PROPOSED — nothing here
has been approved. The act had two names. `black calibration` names it in seven
places and all twelve catalogues have committed to it (`svartkalibrering`,
`kalibracja czerni`, `калибровка по чёрному`, `黑校准`); `dark calibration`
named the same act in three, one of which was this body, one a window title
sitting directly over the sentence "That dark reference does not look dark."
`dark reference` is kept, because it names the RESULT the instrument now holds
and that distinction is worth having. So the body now says "A black calibration
DEFINES what zero means". Three em dashes went with it, under the em-dash rule:
the string was modified, so it stops matching the frozen baseline.*

*New message (#159, 2026-08-29). The second calibration step, offered by an
unticked checkbox in M-CR30-CALIBRATE — per use, deliberately not remembered, so
a second window only ever appears for the user who has just asked for it. That
is the honest answer to the owner's worry about two pop-ups on every Start.*

*The command is the instrument's own. Captured from the vendor's USB frames
(PRIORART-001) and from a Bluetooth trace of the vendor app on his unit
(EXP-BLE-016), and verified on that unit in EXP-022 after he lifted the standing
instruction never to send it: both calibrations were accepted and answered in
~250 ms, and a properly seated white calibration moved his paper reading from
83.95 to 88.37 %R — back into the band every other reading that evening sat in.
So the command really does set the reference, and setting it against the wrong
surface really does shift everything afterwards.*

*⚠ **There is no black tile.** This unit has none, and the vendor calibrates
black against open air with the port downward. The wording says "pointing at
nothing" and never "put something in front of it", and the picture shows no
black tile — because the nearest dark thing to hand is the cap's GREEN face, the
surface that silently corrupted this instrument's white reference during the
research. A drawing of a black tile would teach the one mistake this window
exists to prevent.*

*⚠ **No success is claimed, because none can be.** The reply's bytes fit a
result code and fit equally well the high byte of a device clock that was never
set — over Bluetooth the same field carried a real timestamp. What the dark
reference DOES have, and the white one does not, is an honest test: afterwards, a
reading of nothing should come back at nothing. ChromIQ asks, and reports what
it saw. The threshold is a starting point, not a measured limit, and the check
is one-sided — a reference set too high clamps to a healthy-looking zero.*

*The lamp-and-window clause is PRUDENCE, not measurement. It follows from the
arithmetic of a dark reference and from the vendor's own instruction; the one
experiment that tried to measure it was compromised and is filed as such.*

*Both calibration windows carry the same pair-of-steps picture with the current
step marked — the owner's own choice from eight variants. It is drawn at runtime
from the live palette, so one drawing is correct in light and dark by
construction: a black swatch on a dark window is invisible, and the dark step is
where being unmistakable matters most.*

> **Now the dark reference**
>
> This second step is the opposite of the first one, so it is worth a glance at the picture above.
>
> TAKE THE CAP OFF and put it aside. Hold the instrument with the opening pointing DOWNWARD into open space, about a metre above the floor, with nothing in front of it, and not aimed at a lamp or a window.
>
> There is nothing to place it on. Your CR30 has no black tile: it takes its dark reading from empty air, which is why the picture shows it pointing at nothing.
>
> Then press "Calibrate now". Afterwards ChromIQ reads once more and shows you the number that came back, so there is a record of it.
>
> ⚠ It cannot check that you pointed it at the right thing. A black calibration DEFINES what zero means, so whatever the instrument was looking at becomes the new zero and reads as nothing a moment later. Measured on a real unit: calibrated against white paper, it read back 0.004 %. Getting this step right is your eyes, not ours.
>
> If you would rather not, press "Skip this step". Your white calibration still stands and the measurement goes ahead with the dark reference the instrument already had.
>
> If you have changed your mind about measuring at all, press "Cancel the measurement". Nothing has been measured yet and nothing on disk changes, so the only thing you lose is the white calibration you have just taken, and you can take that again in a few seconds whenever you like.

*⚠ REVISED 2026-08-30, and this one is a retraction. The window claimed the
read-back was "the one check it can honestly make". **It is not a check of what
the user did.** Basti tested it on hardware — black-calibrated deliberately
against white paper — and the read-back came back at **0.004 %R**, comfortably
inside the 0.05 threshold, reported as a healthy dark reference.*

*The reason is structural, not a bug: a black calibration DEFINES zero. Whatever
the instrument is looking at becomes the new zero, so reading that same surface
a moment later can only return ~0. The check is circular for the one mistake it
appeared to guard — pointing it at the wrong thing — and could only fire if
something moved in front of the aperture in the fraction of a second between
the calibration and the read-back.*

*What it still gives is the NUMBER — recorded on screen and now in
`chromiq.log` too. Not "the instrument answered sanely": `allow_dark=True` is
what makes the read-back possible at all, and it necessarily disables the
zero-run guard, so a truncated zero-filled frame passes this exactly as a real
dark reading does. Claiming sanity would have been the same overselling one
sentence further down. The text now promises the number and nothing else.* Under the project's own
rule about colour science — no fake or circular checks — a check that cannot
see its own failure mode must not be described as one.*

*A real check is possible and is NOT implemented: read the WHITE TILE after the
black calibration, where a dark reference taken against paper would show up. It
costs the user another step with the cap, and it needs measuring before it is
promised. Recorded as a possible improvement, not a plan.*

*⚠ ALSO FOUND BY THAT TEST, AND WORSE: every calibration message was being
erased. `_on_start` cleared the measurement log fifty-one lines AFTER calling
the calibration, so the read-back verdict, the note that a white calibration
cannot be verified at all, and the skip note were all written and then wiped
milliseconds later. The check had been firing correctly for its whole life and
nobody had ever seen its answer — which is how the overselling survived this
long. The log is now cleared before the calibration, and the reading also goes
to `chromiq.log`.*

*⚠ REVISED 2026-08-30: a third button, because closing this window used to mean
"skip". Basti found it:* **"none of the calibration pop ups allow to cancel and
if i close them via the red traffic light button chromiq gives me the next
window anyway and allows me to go into the measurement"**.

*The window offered "Calibrate now" and "Skip this step", and the code asked
"is it not Calibrate now?" — which is also true of the red traffic light, the
Windows X and Esc, since `clickedButton()` is None for all three (measured).
So dismissing the window was read as a decision to skip the dark reference, and
the measurement went ahead.*

*Skipping a calibration step is a positive decision and keeps its own button.
Dismissing a window is a withdrawal and now cancels — which costs nothing at
all, because the calibration runs BEFORE the helper starts and there is no
session yet to lose. The same rule is applied at the white window, where it was
already correct, and at M-CR30-INSTRUMENT-GONE, where the safe option is the
opposite one (there, ending is the consequential act, so a dismissal carries
on).*

### M-CR30-INSTRUMENT-GONE · PROPOSED · the instrument stopped answering mid-measurement — Measure

*New message (#159, 2026-08-28). Basti unplugged the CR30 mid-session and
**ChromIQ said nothing at all**, then froze for three minutes when he tried to
stop. The spot workflow spends nearly all its time with nothing arriving,
because it is waiting for a human to press a button — so "no frame yet" is the
normal state, and a bare catch-all treated a transport that had GONE as that
same normal state. The two are now told apart (`DeviceLost`), and this is what
the user is told about the second. It deliberately does **not** say "press the
button again": that is the advice for a refused reading and it is the wrong
advice for an instrument that is not there. The promise about nothing being
lost is real and checked — the helper writes the measurement file after every
single patch (`chromiq_chartread.c`, `cq_write_ti3_atomic` in the external-value
branch). `{loc}` is the patch being read; `{reason}` is the underlying failure.*

> **The instrument stopped answering**
>
> ChromIQ has lost contact with your CR30 while measuring patch {loc}.
>
> This is not something you did wrong, and nothing you have measured is lost — every patch you have already read is written to your measurement file as it is read, so all of it is safe on disk.
>
> The usual causes, in the order worth checking:
>
> •  The USB cable came out, or the instrument was switched off.
> •  Over Bluetooth, the instrument moved out of range or its battery ran down.
> •  Something else took the instrument — the phone app holds it exclusively while it is connected.
>
> Plug it back in or switch it on, then press "Carry on measuring" and ChromIQ will pick up from the patch you were on. If it is still not there, you will simply land back here.
>
> If you would rather stop, press "Stop the measurement". Everything you have read is saved either way, and you can come back to the rest later by starting the measurement again with "Refine / resume existing measurement (-r)" ticked — ChromIQ will then offer you only the patches that are still missing.
>
> What went wrong: {reason}

*⚠ REVISED 2026-08-30, twice over, and the second revision is a ruling.*

*The advice was WRONG for the code it belonged to. It offered restarting with
"Refine / resume" as the only way forward, while the handler had already been
changed to offer carrying on from the patch you were on — so the text sent the
user the long way round past a door the app was holding open. Carrying on is
now named first, because it is what the user wants and what the app does;
restarting is kept as the fallback for someone who would rather stop.*

*And it is shown in a WINDOW now, not only in the log. Basti ruled on that
directly:* **"i don't know what m-cr30-instrument-gone is for but if this is an
important message this should be in a pop up windows with benefitial options
for this case"**. *It had been log-only under §M's own rule — that unapproved
wording speaks through the log until it is approved — with the consequence that
the user got the shared ending window and no statement of why it had appeared.
An instrument that has vanished mid-chart is not something to discover by
scrolling.*

*The two buttons are the two real options and both are safe: "Carry on
measuring" re-arms the outstanding patch (nothing ends), "Stop the measurement"
goes through `_confirm_end_of_session` like every other ending
(`measurement_exit_strategy.md` §1). **Closing the window does not end the
session** — `clickedButton()` is None for the red traffic light, the Windows X
and Esc alike, and ending is the consequential act, so a dismissal takes the
option that changes nothing.*

### M-CR30-PATCH-GAVE-UP · PROPOSED · one patch was refused again and again — Measure

*New message (#159, 2026-08-28). A reading can be refused for good reasons: the
magnetic cap left on, the instrument lifted too early, a reading identical to
the last one. Until now a single refusal **ended the session for ever, in
silence** — `_start_read` is reached only from a new `spot_ready`, which the
helper sends only when it receives a command, so a failure that re-armed nothing
left no reader running and no prompt ever coming again, while the screen still
said "press the button on the instrument again". The likeliest first-run mistake
there is — starting a chart with the cap still on, which is where the cap lives
when the instrument is idle — reached it every time. Refusals are now re-armed,
so pressing again genuinely works; this window is for when that has been tried
several times and is still failing, so the user is not left pressing a button
with nothing changing. `{loc}` is the patch; `{reason}` is what the instrument
reported.*

> **That patch could not be read**
>
> ChromIQ has tried several times to read patch {loc} and each attempt was refused, so it has stopped asking rather than leave you pressing the button with nothing changing on screen.
>
> Everything you have already measured is safe on disk.
>
> The two things that cause this, and both are quick to check:
>
> •  The magnetic cap is still on the instrument. That is where the cap lives when the CR30 is not in use, so it is an easy one to miss — and with a magnet at the opening the instrument stops measuring and hands back its own white-tile value instead, which ChromIQ refuses. Take the cap right off and put it aside.
> •  The instrument was lifted before it had finished. Hold it flat on the patch until it has beeped.
>
> When you have checked those, end this session with "Save and stop" and start it again with "Refine / resume existing measurement (-r)" ticked — you will be offered only the patches that are still missing.
>
> What the instrument reported: {reason}

### M-CR30-HOW-TO-MEASURE · PROPOSED · the spot session's instructions, when ChromIQ supplies the values — Measure

*New message (#159, 2026-08-28). Every other instrument reaches its "how to
measure" window through `MeasureManager.calibration_done`, which
`tab_measure._on_calibration_done` answers — and that handler is the **only**
route to `ui.ti2_loader.patch_measurement_instructions_html`. When ChromIQ
supplies the readings itself the helper is run with `-x`, opens no instrument,
and `cq_handle_calibrate` sits inside `if (xtern == 0)`, so `calibration_done`
can never fire. A CR30 user therefore got a spot session with **no on-screen
instruction at all**. This window is shown once when such a measurement starts,
in place of that one. It carries the two things a CR30 user needs that no other
instrument's user does — take the magnetic cap OFF, and nothing on screen has
to be pressed — plus `{how}`, the instrument's own steps from
`patch_measurement_instructions_html`, which gained its `cr30` branch in the
same change (it previously fell through to the generic "as described in its
manual").*

> **Ready to measure, patch by patch**
>
> ChromIQ reads your CR30 itself, so the measurement is driven from here rather than by ArgyllCMS.
>
> {how}
>
> The patch to read is highlighted in the preview, and the highlight moves on by itself as each reading arrives. You can click any patch in the preview to jump to it, and ChromIQ keeps every reading as it is taken, so you can stop and continue later without losing anything.
>
> You can also press the SPACE BAR, or Enter, to take the reading from here without touching the instrument. That keeps it perfectly still, and a reading taken that way is steadier than one taken by pressing the instrument's own button — pressing it moves the instrument slightly, by about ten times its own measurement noise. ChromIQ offers this once it has learned what your instrument's white tile looks like, which it asks about after calibrating.

### M-REPORT-CHART-MISMATCH-NO-GREY · PROPOSED · the strip when no grey row a device grey ramp answers is listed — Measurement Report

*New 2026-09-24, beta 40 challenge B (B8-942). M-REPORT-CHART-MISMATCH's
closing names one lever for the grey balance, “Neutral grey ramp” with 16
steps, and it was printed whatever the list held: on a FROM PROFILE GAMUT
verification the strip listed three control-strip and evenness rows and still
named the grey ramp, a row not in its list and a lever §26.5 of
`measurement_report_limits.md` rules out on such a chart (its grey steps are
its neutral aims; its lever is a larger chart). This variant is shown when no
listed row is a grey row, or when the sheet the grey row is listed for is a
FROM PROFILE GAMUT chart; each row's own reason still names what that row
needs. Same headline, same `{set}` and `{rows}`.*

> **Some limits cannot be checked on this chart**
>
> The limit set {set} puts a limit on values this chart cannot supply, so these rows read N-A (not applicable):
> {rows}
>
> A row that was not computed says nothing about the printer. Each reason above names what that row needs: most want patches added to the chart in Create Chart, and the control strip wants the chart to declare one. Make the change, print the chart again and measure it.

### WITHDRAWN 2026-09-23, never approved: M-REPORT-NOT-FOR-CALIBRATION

*Proposed the same day for #182 K26 (Knut, 5792484060, Q1: "Run type=
Calibration should not allow any reports"): a red line where "Already
generated…" stands, headed "Measurement reports can only be made with Run type
Profiling or Verification". Knut retracted the ruling it spoke for in
5794078008: "The run type set to calibration should be able to make a report
after all. I retract my statement that the measurement report window should not
allow making reports in this run type." From beta 39 a Calibration window lists,
counts and generates reports (`measurement_report_limits.md` §18.12), so there
is no state left for the line to describe. It was never approved, and its text
is gone from the code and the language files.*

### M-REPORT-UPDATE-NOTHING-LEFT · PROPOSED · Update of a report none of whose measurements is left on disk — Measurement Report

*New 2026-09-23, re-challenge R1 of beta 39 (#4). M-REPORT-UPDATE-LEAVES-OUT
offered “Update without them” even when the report's EVERY measurement was
gone, and the press then wrote the report with `measurements: []` under its
old verdict and its old scope, and the list and the page went on showing it as
the report it had been. A report that covers nothing is not a report, so the
press is refused before anything is written, and the window names the two
buttons that do something. Button: **OK**. `{missing}` as for
M-REPORT-UPDATE-NOT-FOUND.*

> **Nothing of this report is left to update**
>
> None of the measurements the selected report covers is on disk any more:
>
> {missing}
>
> Updating it would leave a report that covers nothing, so nothing was changed and the report stays as it was written. “Delete Selected Report” moves it to the old folder, and “Create New” writes a new report of what is ticked.

### M-REPORT-DELETE-FAILED · PROPOSED · Delete Selected Report could not move the report — Measurement Report

*New 2026-09-23, challenge C of beta 39 (#7). In a read-only folder the move
copied the report into `old/` and left the original, so it was on disk twice
and still in the list, and the window showed Python's own
"[Errno 13] Permission denied: '/Users/…'". The move is now all or nothing
(`core.file_manager.move_report_files`) and this says what could not be done
and what to do. Button: **OK**. `{folder}` is the folder that stopped it.*

> **The report could not be moved to the old folder**
>
> ChromIQ could not change this folder:
>
> {folder}
>
> Nothing was moved, and the report is still in the list. The usual reason is that the folder is read-only. {remedy}

*Revised 2026-09-23, re-challenge R2 of beta 39 (#8): "copy the project" was
the remedy for every report, and a report across projects is not in a project
at all. `{remedy}` (`measurement_messages.report_delete_remedy`) is, for a
report inside a project,*

> Give yourself permission to change it, or copy the project somewhere you may write, and try again.

*and, for a report kept beside the projects it covers (`<ChromIQ folder>/reports/`
or a `reports/` folder beside the projects), with `{place}` the folder that
holds them,*

> This report is not kept in a project but beside the projects it covers. Give yourself permission to change it, or copy {place}, the folder that holds those projects, somewhere you may write, and try again.

### M-REPORT-NOT-WRITABLE · PROPOSED · Generate report or Update could not write in a folder — Measurement Report

*New 2026-09-23, challenge C of beta 39 (#8). The press was already all or
nothing; the window said only "Nothing could be written. The log says why."
It now names the folders that stopped it and the remedy. Button: **OK**.
`{folders}` is one folder per line. The older sentence stays for a failure
that is not a folder ChromIQ may not write in.*

> **The report was not written**
>
> ChromIQ is not allowed to write in:
>
> {folders}
>
> A report is written whole or not at all, so nothing was changed. Give yourself permission to change those folders, or copy the project somewhere you may write, and try again.

*Revised 2026-09-23, re-challenge R2 of beta 39 (#7): the body said "that
folder" under a list of several. With ONE folder the last paragraph reads
"Give yourself permission to change that folder, …"; with several, "those
folders", as above.*

### M-RUN-DELETE-REPORTS-LOCKED · PROPOSED · deleting a profile run is refused because the reports that name the later runs cannot be renumbered — Measurement target bar

*New 2026-09-23, re-challenge R2 of beta 39 (#1). Since challenge C, deleting
a profile run renumbers the saved reports that name the runs after it, and a
report ChromIQ may not change stops the delete before anything moves. The
refusal was a paragraph followed by "This is what ChromIQ tried to remove:"
and the reports folder, which ChromIQ never tried to remove: it is where the
reports it would have had to CHANGE live. The window had no headline either.
Button: **OK**. `{n}` is the run's number, `{folders}` one folder per line.
With one folder the last two sentences read "… in this folder:" and "Make it
writable, …".*

> **Profile run {n} was not deleted**
>
> Nothing was deleted. Deleting this run renumbers the runs after it, and the saved reports that name those runs by number must be renumbered with them. ChromIQ is not allowed to change the reports in these folders:
>
> {folders}
>
> Make them writable, or move the project somewhere you may write, and try again.

### M-THRESHOLDS-NOT-CERTIFICATION · PROPOSED · what ChromIQ measures and what it does not claim — Report limits window

*New for #182 (Knut, D11 and D24, 2026-09-04/05: criteria ChromIQ cannot reach
are a note at the bottom of the thresholds window and in the report, and
"ChromIQ is not offering certification"). The note at the foot of the Report
limits window, under the legend and the footnotes. `{rows}` is the
comma-separated list of the rows marked ✕.*

**Where its review stands (2026-09-24).** Knut approved section C of
[5802027116](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5802027116) in [5816565326](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816565326), and this message
was C15 there, but it has been revised twice since that post, so the approval
does not reach the text below as a whole. Of the two revisions:

* **Accepted by Knut, 2026-09-24, #182 [5816616607](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5816616607)**
  (*"both accepted"*): the "–" sentence as it now reads, *"Such a column reads
  “–” for a row ChromIQ can measure that the standard puts no limit on, and ?
  where it limits the row but no number has been supplied for it"* (B8-979),
  and the last sentence, *"Rows marked ✕ are requirements ChromIQ cannot
  measure at all; they stay in the table so you can see what the standard
  asks"*, left as it is although ✕ now also appears in columns whose standard
  does not ask for the row.
* **Not yet put to him:** the Custom-column sentence of B8-978, *"A Custom
  column starts from limits researched from industry practice and ChromIQ's
  own numbers, neither of which is that standard's, and no values file changes
  that."* (it replaced *"starts from a licence holder's figures where there
  are any, and otherwise from …"*). That is why the message stays here.

> **ChromIQ measures against published values; it does not certify**
>
> A read-only column named after a standard is judged against that standard's published tolerance values, where ChromIQ ships them or a licence holder has supplied them. Such a column reads “–” for a row ChromIQ can measure that the standard puts no limit on, and ? where it limits the row but no number has been supplied for it. A Custom column starts from limits researched from industry practice and ChromIQ's own numbers, neither of which is that standard's, and no values file changes that. Either way the values are applied to the chart you printed and not to that standard's own control strip and chart, so a report can never say that a print conforms to a standard. What ChromIQ does is measure as many of the standard's values as your chart allows, say which it checked and which it did not, and let you follow them over time.
>
> *(Corrected 2026-09-12. The first wording said the columns HOLD that standard's published values, which is false in both of ChromIQ's states: the two editable columns start from ChromIQ's own numbers where nobody has supplied a standard's, and the two read-only ones are empty as ChromIQ ships, because the data file is empty by design. The report's guide was corrected for each half in turn and this copy was reached by neither, while `_notes_text` printed it two lines below its own correct sentence.)*
>
> *(Revised 2026-09-24, awaiting review, B8-979 (Knut, #182 5815435713): a row ChromIQ cannot measure now reads ✕ in every set, so "–" is said only of a row ChromIQ can measure.)*
>
> *(Revised 2026-09-24, awaiting review. Knut, #182 5815346140: the Custom columns are "alternative limit sets to the standards", never copies, so a licence holder's own values file no longer fills them; it fills the read-only column. "starts from a licence holder's figures where there are any" was removed.)*
>
> *(Revised 2026-09-23, awaiting review, for #182 S-2 (`measurement_report_limits.md` §23). DIN's legal department answered that a standard's values alone are not reproduction, so the ISO 12647 values are prepared to ship in the read-only columns once the owner gives the go-ahead. From then on "where nobody has supplied them" no longer divides the columns correctly: a shipped set judges its read-only column while the Custom column beside it keeps the researched figures. Each column is now described by what it starts from, as a condition, so the one sentence is true whether a set ships, is supplied, or holds nothing.)*
>
> *(Revised 2026-09-23, awaiting review, re-challenge R2 of beta 39: "reads ? where neither is so" stopped being true with §23. A shipped set shows “–” for a row the standard does not limit, and ? only where the set limits the row but no number has been supplied, which is how the Report limits legend puts it.)*
>
> *(Corrected again 2026-09-21. Knut's researched industry figures became the two Custom columns' starting values on that day, so "ChromIQ's own numbers" described nineteen of their thirty-six limits and not the other seventeen. Both sources are named, and the sentence says of both that they are not the standard's.)*
>
> Rows marked ✕ are requirements ChromIQ cannot measure at all; they stay in the table so you can see what the standard asks: {rows}

### M-PATCHSET-MISSING · PROPOSED · the loaded patch set is no longer on disk — Create Chart

*New for 4.1.3-beta.16. Shown when "Generate Chart" is about to lay out a patch
set the user opened earlier and that file can no longer be found. Until now this
path wrote one line to the log and built a completely different chart. Modal,
one button; the build does not start. `{path}` is the file ChromIQ was looking
for.*

> **The patch set you loaded is no longer there**
>
> ChromIQ was going to lay out the patch set you opened earlier, but that file cannot be found any more — it may have been moved, renamed or deleted since you loaded it:
>
> {path}
>
> Nothing has been changed. The chart already in this run is untouched, and no new chart has been made.
>
> To carry on, choose one of these:
> • Open the patch set again with the patch-grid icon at the top right of this tab, and pick the file from wherever it is now.
> • Choose a ready-made patch set from the "Presets" list.
> • Or let ChromIQ work out a fresh set of colour patches for you: tick "Edit patch recipe (override preset)" and click "Generate Chart".

### M-PATCHSET-KEPT-UNCHECKED · PROPOSED · an older chart keeps its own patch set, unchecked — Create Chart

*New for beta 45 (B8-1460). A chart made before its sidecar recorded whether
its patch set was given (beta 44 and every release before it) is judged from
its files when it is shown again: targen is asked whether the settings on
screen, with the arguments Generate would give it, write exactly the chart's
patches. If they do, Generate builds the chart again as before; if they do not
(a patch set loaded with "Load patch set", say), the chart keeps its own
patches, as a chart that records a given set always did, and nothing is said.
This message is for the third case only: targen could not be asked (it is not
installed, it failed, or a file it needs is gone), so nothing can tell, and
rather than let Generate replace the patches in silence the chart keeps them.
Written into Create Chart's log, not a window; the chart has just been shown
and nothing is being built.*

> **This chart keeps its own patch set**
>
> This chart was made by an earlier version of ChromIQ, which did not record where its patches came from, and ChromIQ could not check whether the settings on screen make the same patches. So that a sheet you have already printed still matches, “Generate Chart” lays out this chart’s own patches again.
>
> To make a new set of patches from your settings instead, tick “Edit patch recipe (override preset)” and change a setting of the patch recipe. The next “Generate Chart” then makes a new set.

### M-PROJECT-EXISTS · PROPOSED · the typed project name is already a project — Create Chart

*New for 4.1.3. **Nothing in this model governed it.** §4 governs what a RUN
holds; nothing governed which PROJECT a typed name lands on. So typing the name
of a project you already have adopted that project in silence and built into its
current run — Knut, 2026-08-27: "there is no warning message that this project
already exists, with choice to overwrite or cancel, and message to change to a
different name … Nothing shall ever be lost and user shall always be notified if
there is a risk of overwriting a project."*

*Raised at build time — Generate Chart, a preset, a loaded patch set, an applied
editor chart, a from-profile-gamut build — when the name in "Printer profile
project name" resolves to a project that exists on disk, is not the project
already open, **and holds something**. An existing project that is empty raises
nothing: there is nothing to lose, and a window there would be a nag. In every
case, empty included, a line appears under the name box saying which project the
name now points at; that line is hidden whenever the name does not match one, so
its appearing is itself the signal (Basti's ruling, 2026-08-27).*

*It is **never** raised from the live auto-update preview, which may not open a
window (§4) and no longer adopts an uncommitted name at all.*

*This window ALSO carries §4's answer for the run it names, so one action still
opens one window — see §S4.6.*

*`{name}` is the sanitised project name (the folder that will really be used),
`{folder}` its path, `{runs}` how many runs it has, `{cal}` the one extra
sentence when the project has a calibration of its own, `{chosen}` the run the
picker is on, and `{holds}` what that run holds.*

> **There is already a project called “{name}”**
>
> ChromIQ found it here:
> {folder}
>
> That name is already taken, so building now would carry on inside that project rather than start a new one. A project keeps its work in runs, and each run holds one finished profile. This one has {runs}.{cal}
>
> You can choose below which run the new chart goes into. {chosen} holds:
>
> {holds}
>
> Nothing has been changed yet. Choose what you would like to do:
>
> •  Continue this project: the new chart is made in the run named in the box below. Anything that chart replaces is moved to that run’s “old” folder first, with today’s date on it, so you can always get it back. Choosing a new run adds a fresh, empty one and leaves everything already in the project exactly as it is.
>
> •  Replace it: everything the project holds now is moved into its own “old” folder, with today’s date, and a new, empty project of the same name is started. Nothing is deleted, and ChromIQ asks you to confirm before it does it.
>
> •  Use a different name: nothing is touched, and ChromIQ takes you back to the name box so you can type another one.
>
> •  Cancel: stops here and changes nothing.

Buttons: **Continue this project** · **Replace it** · **Use a different name** ·
**Cancel**. The default is **Cancel** — a Return keypress must never be an
overwrite.

The picker below the text is labelled **"Make the new chart in:"** and offers
**"A new run (nothing already there is touched)"** first — the default, because
it is the one answer that cannot cost anything — followed by every run the
project has, oldest first. `{chosen}` and `{holds}` follow the picker as it
moves. `{runs}` is *"one run"*, *"{n} runs"*, *"{n} runs, one of them with work
in it"* or *"{n} runs, {f} of them with work in them"*.

`{holds}` is a LIST, not a sentence — joining the parts with commas and a final
"and" would need the comma and the conjunction to be translatable too, and word
order differs enough across the thirteen languages that the result would be
wrong somewhere. It is built from these lines and from nothing else (house rule:
real singular and plural, never "(s)"):

> •  a chart
> •  a measurement
> •  a built profile
> •  one dated verification check          ← when there is exactly one
> •  {n} dated verification checks         ← when there is more than one

Only the lines that apply are shown. When none of them do:

> •  nothing yet: no chart, no measurement and no profile

That is the line the window shows by default, because the picker starts on
**a new run** — a run that does not exist yet holds nothing. It is also what a
project shows when every one of its runs is empty, and THAT case raises no
window at all: only the line under the name box.

`{cal}` is empty, or this one sentence — a calibration belongs to the PROJECT,
not to a run, so it is stated with the project rather than listed under
"A new run holds:", where it said something plainly untrue:

> It also has a calibration of its own, shared by every run.

### M-PROJECT-REPLACE-CONFIRM · PROPOSED · the second look before a project is cleared — Create Chart

*New for 4.1.3, with §S4.7. Basti, 2026-08-27: "Keep it but require a second
confirmation". "Replace it" is the only control in the app that clears a whole
project from the Create Chart tab, and three of the six data-loss faults found in
the first implementation were about it — so it is never one click away from a
window somebody opened by accident. Default button: **Go back**.*

> **Start “{name}” again from empty?**
>
> Everything this project holds is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays inside the project, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.
>
> After that, a new and completely empty project of the same name is started in the same place, and your new chart is made in its first run.
>
> If what you wanted was to ADD to this project rather than start it again, go back and choose “Continue this project” instead. That leaves everything where it is.

Buttons: **Replace it** · **Go back**, default **Go back**.

### M-PROJECT-REPLACE-FAILED · PROPOSED · the Replace could not be carried out — Create Chart

*New for 4.1.3, with §S4.7. "Replace it" promises that everything is moved into
the project's own "old" folder and that nothing is deleted. When the move cannot
be made — a read-only folder, a share that has gone away, a file another program
holds open — the promise is not kept, and this says so. The archive is
all-or-nothing: anything already moved is put back before this window appears,
and the build does not go ahead. `{folder}` is the project, `{reason}` the error
the operating system gave.*

> **The existing project could not be moved aside**
>
> ChromIQ was going to move everything in this project into its own “old” folder before starting a fresh one of the same name, and it could not:
>
> {folder}
>
> Nothing has been changed. Anything that had already been moved has been put back, and no new chart has been made.
>
> The reason given was:
> {reason}
>
> This usually means the folder is read-only, is on a disk or a share that is no longer available, or holds a file another program still has open. Close anything that might be using it and try again, or choose “Use a different name” and leave this project alone.

### M-IMPORT-REPLACE-CONFIRM · PROPOSED · the second look before an import clears a project — the loaders

*`M-PROJECT-REPLACE-CONFIRM` with one clause changed, because on this route
what lands in the new project is an imported file rather than a new chart.*

> **Start “{name}” again from empty?**
>
> Everything this project holds is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays inside the project, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.
>
> After that, a new and completely empty project of the same name is started in the same place, and {subject} you are importing is put into its first run.

Buttons: **Replace it** · **Go back**; default **Go back**.

### M-IMPORT-REPLACE-PROJECT-CONFIRM · PROPOSED · the second look before "Copy the whole project in" replaces — Print ▸ Load chart

*New for 4.1.5. This route archived a whole project on ONE CLICK with no
confirmation of any kind, while its own error line named a button ("Replace
it") that was not on the window ("Replace existing"). Its own wording, because
what arrives is a whole project with its own runs — not a single file landing
in run 1, which is what M-IMPORT-REPLACE-CONFIRM describes.*

> **Start “{name}” again from empty?**
>
> Everything the project here holds is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays in place, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.
>
> The project you are copying in then takes its place, with everything it brings of its own.

Buttons: **Replace it** · **Go back**; default **Go back**.

### M-IMPORT-REPLACED-KEPT · PROPOSED · where the replaced project went — the loaders

*New for 4.1.5. Nothing anywhere recorded it: no window, no log line, not even
a line in the tab's log. "Nothing is deleted" is only true if the person can
find it again.*

> **The earlier “{name}” has been kept**
>
> It has been moved into its own “old” folder:
>
> {folder}
>
> Nothing was deleted. You can open that folder at any time and take anything back out of it.

### M-CM-NO-CCTIFF · PROPOSED · the profile-applying tool is missing — feature A, §3.2 A10

*New with feature A (`verification_printing_and_target.md` §6 S9). Shown when
"Through the profile" is chosen but `cctiff` is not in the configured
ArgyllCMS folder. Nothing is printed.*

> **ChromIQ cannot find the tool that applies your profile**
>
> To print this chart through your profile, ChromIQ uses a program called cctiff, which comes with ArgyllCMS. It is not in the ArgyllCMS folder ChromIQ is set to use.
>
> You can still print this sheet raw — choose "Raw — no profile" above — but measuring it will tell you about your printer rather than about your profile.
>
> To fix it: open Preferences and check that the ArgyllCMS folder is the one you installed, then come back to this tab.

### M-CM-CONVERT-FAILED · PROPOSED · a page could not be converted — feature A, §3.2 A11/A12

*New with feature A (`verification_printing_and_target.md` §6 S10). Shown when
a page's conversion fails or times out; the whole job stops and nothing is
printed. `{reason}` carries cctiff's parsed error, so an unreadable or non-RGB
profile (A12) names itself.*

> **This sheet could not be prepared**
>
> ChromIQ was working out the ink amounts your profile predicts for page {n} of {total}, and that did not finish. Nothing has been printed and nothing has been changed.
>
> The most common reason is that the profile file is damaged or is not a printer profile. Rebuilding the profile on the Build Profile tab usually fixes it.
>
> Details: {reason}

### M-CM-PROFCHECK-CONVERTED · PROPOSED · Check & Refine on a print-time-converted sheet — feature A, §2b

*New with feature A (`verification_printing_and_target.md` §2b, test T13).
`profcheck` pushes the chart's device values through the profile, so those
values must be what was printed. A sheet converted at print time still has the
unconverted values in its chart file — the check would produce confident,
meaningless figures, and nothing downstream could tell. Shown before the check
runs; Cancel is the default button.*

> **This measurement came from a sheet printed through the profile**
>
> This check pushes the chart's own numbers through the profile and compares the answer with what you measured. That only means something when the chart's numbers are what was actually sent to the printer.
>
> This sheet was printed with "Colour" = "Through the profile", so ChromIQ converted the numbers before printing — the chart file still holds the unconverted ones. The check would run without complaint and produce confident figures, but they would not describe your profile or your printer.
>
> To judge this measurement, use the Measurement Report instead — it compares against the right reference. To use this check, print the verification chart raw and measure that sheet.
>
> **What each button does:**
> • **Run the check anyway** — runs the check on these files unchanged.
> • **Cancel** — changes nothing.

### M-CM-K-CHART-THROUGH · PROPOSED · the verification chart was built with -K — B7, #182 5959070209

*New 2026-10-02. Print Chart, Run type = Verification, Colour = Through the profile, when the VERIFICATION chart was itself built with the printer calibration applied (-K): its pixels are calibrated device values, and the conversion reads them as sRGB design values. Nothing is printed. Detection: `workflow.printer_calibration.calibration_mode_of` (apply or old_engine_apply). Behaviour approved by Sebastian (5959070209); the wording is ours.*

> **This chart cannot be printed through the profile**
>
> This verification chart was made with the printer calibration applied (-K), so its pages already hold calibrated ink amounts instead of the colours the chart describes. Printing it through the profile would read those ink amounts as colours and calibrate them a second time, and the measurement would not describe your profile. Nothing has been printed.
>
> To check the profile: make the verification chart again with the printer calibration set to None or to embed only (-I), and print it through the profile. When the run's own chart was printed with the calibration applied, ChromIQ applies that calibration itself as it prints through the profile.
>
> To check the printer instead: choose “Raw” in the Colour row above and print this chart as it is.
>
> **What each button does:**
> • **OK** — prints nothing.

### M-CM-RAW-UNCALIBRATED · PROPOSED · a -K run's verification printed raw without the calibration — B7, #182 5959070209

*New 2026-10-02. Print Chart, Run type = Verification, Colour = Raw, when the run's PROFILING chart was printed with the calibration applied (-K) and the verification chart was not. Cancel is the default. The wording is ours.*

> **This sheet will print without the printer calibration**
>
> This run's chart was printed with the printer calibration applied (-K), so its profile describes your printer with that calibration in front of it. Printed raw, this verification chart goes to the printer without the calibration, and its measurement describes a printer the profile was not made for.
>
> To check the profile, choose “Through the profile” in the Colour row above: ChromIQ then applies the profile and the run's calibration. To check the printer exactly as the run's chart was printed, make the verification chart again with the calibration applied (-K) and print that raw.
>
> **What each button does:**
> • **Print Raw Anyway** — prints the sheet raw, as before.
> • **Cancel** — prints nothing.

### M-CAL-APPLIED-TWICE · PROPOSED · Apply Calibration on an older layout-engine -K profile — C1, #182 5959070209

*New 2026-10-02. Build Profile ▸ Apply Calibration (mode Apply), when the input profile's run is an older engine -K run: its .ti2 says ORIGINATOR "ChromIQ layout engine", a CAL is embedded, and a device value of its .ti3 for a SAMPLE_ID the .ti1 has differs from the .ti1 by more than 0.05 (fields matched by name). Sebastian approved the warning in 5959070209; the wording is ours. Cancel is the default.*

> **The calibration would be applied twice**
>
> This profile was built from a chart that an earlier version of ChromIQ's layout engine made with the printer calibration applied (-K). That version also wrote the calibrated values into the chart file, so the profile already describes your printer without the calibration. Applying the calibration to it now would apply it a second time, and prints made with the result would be wrong. Nothing has been changed yet.
>
> Use this profile as it is, without the calibration. To work with the calibration, build the chart again with this version of ChromIQ, then print and measure it again.
>
> **What each button does:**
> • **Apply Anyway** — runs applycal as before.
> • **Cancel** — changes nothing.

### M-CAL-CALIBRATED-TWICE · PROPOSED · Check & Refine on such a run's calibrated.icc — C1, #182 5959070209

*New 2026-10-02. Check & Refine, when the profile to check is the calibrated.icc of an older engine -K run (the same rule as M-CAL-APPLIED-TWICE). Cancel is the default. The wording is ours.*

> **This calibrated profile applies the calibration twice**
>
> This calibrated profile was made from a profile whose chart an earlier version of ChromIQ's layout engine built with the printer calibration applied (-K). That profile already describes your printer without the calibration, so this file applies the calibration a second time, and checking it measures that mistake rather than your profile.
>
> Check the run's own profile instead, without the calibration. To work with the calibration, build the chart again with this version of ChromIQ, then print and measure it again.
>
> **What each button does:**
> • **Run the check anyway** — runs the check on these files unchanged.
> • **Cancel** — changes nothing.

### M-CAL-TABLE-REPAIRED · PROPOSED · a measurement's damaged copy of the printer calibration was put back from its chart, before an ArgyllCMS tool loads it — Build Profile, Check & Refine, averaging and merging, resuming a measurement, Tools

*New 2026-10-03, beta 7 (the CMYK/CR30 forum report). Before 4.3.3-beta.7 ChromIQ's measuring engine wrote the printer calibration of every `-K`/`-I` chart into the `.ti3` as `nan` (on other compilers possibly as wrong numbers), so colprof, profcheck, average, colverify and a resumed chartread refused the file. Basti ruled on 2026-10-03: repair the measurement in place, keep the original in `old/`, keep the yellow confirmed marks. `workflow/cal_repair.py` does so only when the `.ti3`'s table differs from the chart's AND is not a plausible calibration (a channel not finite, outside 0..1 beyond 0.001, constant, or not monotonic; a plausible table that merely differs, for example a measurement printed with another calibration, is left untouched and only logged, Basti's data-safety ruling after the review of aad896d8) AND the `.ti2` is provably the chart that was measured (same table shape and input column, same device columns, same device values for every SAMPLE_ID); it copies the original and its `.confirmed.json` to the run's `old/<date-time>/` first (a verification's to its date's `verifications/<date>/old/`, as §2a keeps it), replaces only the calibration table, keeps the file's date, and re-stamps `<stem>.confirmed.json` (`-verify.confirmed.json`). One window per action, however many files it repaired (three averaged reads give one). It is never shown while a measurement is starting or running, nor over another window: a resumed measurement's repair is held and shown once the measurement has ended. When the session guard has just archived the same bytes (a resume), that copy is the original and no second one is kept; a file outside any project is repaired only if an `old/` folder can be written beside it. Information only, one OK button, no sound. `{file}` and `{folder}` are shown from the project folder down; `{files}` is one line per file, `•  {file}  (as it was: {folder})`. The behaviour is Basti's; the wording is ours.*

> **ChromIQ repaired a measurement file**
>
> The measurement {file} carries a copy of the printer calibration its chart was made with. An earlier version of ChromIQ wrote that copy damaged, so ArgyllCMS could not read the file.
>
> ChromIQ has put the calibration back from the chart, which holds it intact. The readings themselves were not changed, and patches you confirmed stay confirmed. You do not need to measure again.
>
> The file as it was is kept in:
> {folder}

With more than one file, the headline is **ChromIQ repaired these measurement files** and the body:

> These measurements carry a copy of the printer calibration their chart was made with. An earlier version of ChromIQ wrote that copy damaged, so ArgyllCMS could not read them:
>
> {files}
>
> ChromIQ has put the calibration back from the chart, which holds it intact. The readings themselves were not changed, and patches you confirmed stay confirmed. You do not need to measure again.

### M-CAL-TABLE-DAMAGED · PROPOSED · the profile build failed on that table, and no chart could be proved to be the one measured — Build Profile

*New 2026-10-03, beta 7. The body of the "Profile Build Failed" window when colprof's error is a CGATS read error AND the measurement's calibration table is not all numbers, which after M-CAL-TABLE-REPAIRED's repair can only mean that no chart was found to repair it from. It replaces, for this one cause, "Make sure the file isn't open in another app, hasn't been edited by hand, and was generated by ChromIQ's Measure step", which blamed the user for a file ChromIQ wrote; every other read error keeps that text. What can be checked against the chart is the patches with their device values and the calibration table's size, not the calibration itself (the measurement's copy is the damaged part), and the body says only that. The wording is ours.*

> **The measurement's copy of the calibration is damaged**
>
> ArgyllCMS could not read {file}: the copy of the printer calibration inside it is damaged. An earlier version of ChromIQ's measuring engine wrote it that way. Nothing you did caused it, and the readings in the file are fine.
>
> ChromIQ puts that copy back from the chart before it builds, but it could not find the chart this measurement was made with: a .ti2 with the same patches and the same device values, and a calibration table of the same size, in the run folder. Put that chart back into the run folder and build again, or print and measure the chart again with this version of ChromIQ.

### M-PATCHSET-CAL-INKS · PROPOSED · a preset's or loaded patch set does not fit the printer calibration — Create Chart, before the chart is built

*New 2026-10-03, beta 7 (the CMYK/CR30 forum report). Every built-in preset carries an RGB patch set; a loaded or attached one carries whatever inks it was made for. A printer calibration for other inks cannot be applied to (-K) or embedded in (-I) it, and printtarg and the layout engine both refuse. Their refusal (the "calibration_mismatch_message" text) said "set Device Type to CMYK", which the preset's locked targen panel does not allow, so the user followed it, saw CMYK on screen and met the same refusal again. This window is asked BEFORE anything is built, in `TabChart._refuse_cal_inks_for_patch_set`, from every route that lays out a bound patch set (`_generate_from_ti1`, and the TC9.18 and CR30/ColorMunki/i1/Pharmacist/Knut preset picks, where the preset then stays applied so the box it names is on screen). The live preview stops without a window. `{source}` is the preset's name, or the patch-set file's name when it was loaded; `{chart_space}` and `{cal_space}` are the inks ("RGB", "CMYK", "grey", …). Shown before approval, as the brief for this fix (2026-10-03) allows; the behaviour was approved by Basti, the wording is ours.*

> **This patch set does not fit the printer calibration**
>
> The patch set of “{source}” is {chart_space}, but the printer calibration was made for a {cal_space} chart. A calibration can only be applied to (-K) or embedded in (-I) a chart with the same inks, so the chart was not built.
>
> To build a {cal_space} chart with this layout, tick “Edit patch recipe (override preset)”, set “Device Type” to {cal_space} and press Generate Chart. ChromIQ then makes a new {cal_space} patch set with targen.
>
> To use the {chart_space} patch set of “{source}” as it is, set the printer calibration to “None”.

### M-VIEW-RGB-ONLY · PROPOSED · a view that reads RGB measurements only, shown a CMYK or multi-ink one — Measurement Report, its patch-identity line, the auto-saved report, the measurement details

*New 2026-10-03, beta 7. CMYK and multi-ink charts are built, measured, imported (§I.13) and profiled, but the Measurement Report, its patch-identity check and the measurement details read RGB device values only (`parse_ti3`). They said "No device RGB columns — only RGB charts are supported.", "the measurement carries no device values", or nothing at all. Every such view now asks `workflow.ti3_analysis.non_rgb_note` first and shows this one text in place of its content; the auto-saved report writes it to the log and saves nothing. `{space}` is the measurement's inks ("CMYK", "CMYKOG", …). Information only. The wording is ours.*

> **This view supports RGB charts only for now**
>
> This is a {space} measurement. ChromIQ measures, imports and builds profiles from {space} and other multi-ink charts, but this view supports RGB charts only for now. Nothing is wrong with the measurement.

### M-PATCH-COLOUR-RANGE · PROPOSED · the colour range on a flagged patch's hover card — Measure tab preview, #182 k10

*New 2026-10-02. The rule was approved (Knut [5961180259](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5961180259), Sebastian, on [5961078418](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5961078418)); the post's one line of card text, "Blue: 2 of 3 spaced confirmations so far", is split so the range's name stands alone on a line of its own (a nominative every language can say), and the sentences below are ours. Nothing counts but the fixed 3, so no language needs plural forms. The card breaks its lines by hand, so each line below is one line on the card; the headline is the range line. `{range}` is one of: dark grey, mid grey, light grey, pink/rose, red, orange/brown, yellow, yellow-green, green, cyan/turquoise, blue, magenta (purple/violet was merged into blue in beta 11, Knut [5983470377](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983470377), answer 4). `{locs}` is the range's confirmed patches in reading order, the first three and then "…". Which lines a card shows: a red card, the headline and, with one or two confirmations, lines 1 and 2, or with three, lines 7 and 8; a confirmed (yellow) card, the headline and lines 1 and 2, or with three, line 9; a learned (yellow) card, the headline, line 2 and lines 3 to 6; a card confirmed by similar patches opens with lines 10 and 11 instead of "Yellow outline: confirmed by a re-read" and its two ΔE values.*

> **Colour range: {range}**
>
> {k} of 3 confirmations so far
> Confirmed: {locs}
> Its range has learned: three patches
> of it were confirmed.
> This one is off in the same way,
> so it is taken as real too.
> This range has learned, but this
> one is off in a different way.
> This range has learned.
> Yellow outline: confirmed by similar patches
> Read alike in other strips: {locs}
> Read it again to find out.
> No need to read it again.
> one's error is smaller: ΔE {own} here,
> Its error is also smaller: ΔE {own} here,
> (at most ΔE {tol} smaller allowed),
> one's error points another way:
> Its error also points another way:
> ΔE {own} sideways
> (at most ΔE {tol} allowed).
> one stands out from its strip more:
> It also stands out from its strip more:
> ΔE {own} above its strip,
> (at most ΔE {tol} more allowed).
> ΔE {ref} on its confirmed patches
> ΔE {ref} on some of its confirmed patches
> {lo} to {hi}
> and its reading did not land near theirs
> (ΔE {own} away, at most ΔE {tol}).
> Its reading landed where its
> confirmed patches' readings did.
> Far from what the profile predicts.
> Either a misread, or a place where
> the profile is inaccurate.
> it is real, and counts against
> the profile's accuracy.
> A real difference, not a misread:
> the profile does not predict this
> colour well here (or the printer has
> changed since the profile was made).
> The profile is off in the same way here,
> Far from the chart's estimate.
> The profile was made after this
> sheet was printed, so its
> prediction is not used.
> Either a misread, or a real difference:
> read it again to find out.
> it is real: the print differs from
> the chart's estimate here.
> A real difference from the chart's
> estimate, not a misread.

*Beta 11, lines 42 to 51 (2026-10-04, #182): a VERIFICATION whose run profile was made, or changed, after the sheet was printed is compared with the chart's own estimate, not the profile's prediction (10.8), and its card used the profiling wording, which ends "keep it for the profile". On such a card (only), a red card says lines 42 to 47 instead of "Either a misread, or a colour / this printer and paper cannot reach." and "Read it again to find out.", and lines 48 and 49 after "Same value after a re-read:" instead of "it is real, keep it for the profile."; a yellow card confirmed by a re-read or by similar patches says lines 50 and 51 instead of "A real difference this printer and / paper cannot reach, not a misread." and "Keep it for the profile.". A learned card keeps line 5.*

*Approved lines (Knut, 2026-10-04, [5983480953](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983480953): "OK", to the sentence "Far from the chart's estimate. The profile was made after this sheet was printed, so its prediction is not used. Either a misread, or a real difference: read it again to find out."): lines 42 to 47, that sentence broken for the card. **Confirmed by:** Knut, 2026-10-04, 5983480953. Only these six lines; lines 48 to 51 are ours, worded in the same spirit, and wait here.*

*Approved lines (Knut, 2026-10-04, [5982038838](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982038838), answers 1 and 2 to the questions of beta 9): "Yellow outline: confirmed by similar patches" and "Read alike in other strips: {locs}" (lines 10 and 11), and "Read it again to find out." and "No need to read it again." (lines 12 and 13). **Confirmed by:** Knut, 2026-10-04, 5982038838. Only these four lines; the message as a whole stays PROPOSED for its other lines.*

*Beta 10, lines 14 to 27 (2026-10-04, Knut [5982206917](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982206917), answer 1 of [5982058944](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982058944): the card of a red patch in a LEARNED range names the test that failed and its numbers). They replace line 8, "one is off in a different way.", which is kept only for a card with no numbers to show. Line 7 "This range has learned, but this" is finished by the first reason (line 14, 17 or 21); a further reason starts its own sentence (line 15, 18 or 22). The reasons are the tests of 10.4 that ruled the patch out against its range's confirmed patches: the fewest that between them rule out every one of them, the one ruling out most first, a tie going to a test the closest confirmed patch (by expected colour) failed. The numbers: "smaller", this patch's error measured along theirs ({own}) and their errors ({ref}), then line 16; "another way", how far this patch's error strays sideways from theirs, then line 20; "stands out", this patch's ΔE above its strip's median and theirs, then line 24. A span is line 27 ("75 to 92"); line 26 replaces line 25 when that test ruled out only some of the confirmed patches. Whole numbers, one decimal when the test failed by less than ΔE 1 somewhere. Example (Knut's O7 at limit 60): "This range has learned, but this / one's error is smaller: ΔE 63.8 to 64.3 here, / ΔE 74.8 to 92.4 on its confirmed patches / (at most ΔE 10 smaller allowed)." Knut kept the "smaller" test with a waiver (see lines 28 to 31). The request is approved; the words are ours and wait here.*

*Beta 10, lines 28 to 31 (2026-10-04, Knut [5982600086](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982600086) approving [5982339631](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982339631): the size test is waived when the patch's measured colour lands within ΔE 15 of a confirmed patch's measured colour; the rule is CONFIRMED in §10, the words are ours and wait here). A "smaller" reason can only be given when the reading also did not land there, so it now says so: line 16 ends with a comma instead of a full stop and is followed by lines 28 and 29, `{own}` how far this patch's reading is from those confirmed patches' readings (a span by line 27), `{tol}` 15. Example: "one's error is smaller: ΔE 64 here, / ΔE 75 to 92 on its confirmed patches / (at most ΔE 10 smaller allowed), / and its reading did not land near theirs / (ΔE 18 to 31 away, at most ΔE 15)." A learned (yellow) card whose patch is like its confirmed patch only by that waiver shows lines 30 and 31 between line 4 and line 5.*

*Beta 10, lines 32 to 41 (2026-10-04, Knut [#203 5982702169](https://github.com/itsab1989/ChromIQ/issues/203#issuecomment-5982702169): on a verification whose colours come from the profile's gamut, a highlighted patch is a check of the profile's accuracy, "not a highlighting of patches that the printer cannot reach"; proposed in [5982715730](https://github.com/itsab1989/ChromIQ/issues/203#issuecomment-5982715730)). Only on a card of a VERIFICATION judged against the run profile's prediction (10.8); the profiling cards are unchanged. A red card says lines 32 to 34 instead of "Either a misread, or a colour / this printer and paper cannot reach.", and lines 35 and 36 after "Same value after a re-read:" instead of "it is real, keep it for the profile."; a yellow card confirmed by a re-read or by similar patches says lines 37 to 40 instead of "A real difference this printer and / paper cannot reach, not a misread." and "Keep it for the profile."; a learned card says line 41 instead of line 5.*

*Approved lines (Knut, 2026-10-04, [#203 5982788316](https://github.com/itsab1989/ChromIQ/issues/203#issuecomment-5982788316): *"your rewording is OK."*, to the wording of [5982715730](https://github.com/itsab1989/ChromIQ/issues/203#issuecomment-5982715730)): lines 32 to 41, the verification card's lines, exactly as shown above. **Confirmed by:** Knut, 2026-10-04, 5982788316. Only these ten lines; the message as a whole stays PROPOSED for its other lines.*

*Beta 9, the last two lines (2026-10-04, Knut [5980576263](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980576263): the user must understand the difference between red and yellow). "Read it again to find out." stands on a red card under "Either a misread, or a colour / this printer and paper cannot reach."; "No need to read it again." on every yellow card, under "Keep it for the profile." (re-read and similar patches) or under line 6 (learned). New, ours, waits here.*

*Beta 8 (2026-10-04, Knut [5969949735](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5969949735) and [5973177088](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5973177088)): three yellow blue patches said "2 of 3" and four magenta ones "1 of 3", correctly by the rule, because confirmed patches of nearly the same colour count once. A confirmed or red card whose range has not learned now also shows line 2 (the confirmed patches), and, when more patches are confirmed than are counted, lines 10 to 12. Those three lines are new and wait here.*

*Beta 9 (2026-10-04, Knut [5979886227](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979886227), awaiting confirmation; the behaviour is 10.3a and 10.4a). The three beta-8 lines "Patches closer than ΔE 6 in colour / count as one confirmation, so the / range needs more different colours." were **approved by Knut on 2026-10-04** ([5979780372](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979780372), *"all are ok"*, question 4 of [5979436912](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979436912)) and are **removed by this change**: in the same thread Knut ruled that close patches counting as one was the wrong behaviour, so the ΔE 6 spacing they explain is gone. "spaced" is dropped from lines 1 and 4 ("{k} of 3 spaced confirmations so far", "of it, spaced apart, were confirmed."), line 2 "Re-read and the same: {locs}" becomes "Confirmed: {locs}" because the list now holds patches confirmed by similar patches too, and lines 10 and 11 are new. A card confirmed by similar patches then shows "ΔE*ab {de} reached your limit {limit}" and "A real difference this printer and / paper cannot reach, not a misread. / Keep it for the profile.", the existing lines of the other yellow cards. All of this waits here.*

### M-STRIP-READ-TWICE · PROPOSED · a strip's readings match a strip already measured — Measure tab, ChromIQ engine, strip mode

*New 2026-10-03. The check and its question were approved by Knut, #182 [5963903650](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963903650) Q5 ("Yes."), on the wording shown in [5963737221](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963737221): "Strip D looks very like strip C, which you already measured. Did you read strip C again?" with the buttons **Re-read strip D** (default) and **Keep, it is strip D**. Those words are kept verbatim; the two lines saying what each button does are ours, which is why the message waits here. Shown before approval on Sebastian's ruling of 2026-10-02 that a proposed window protecting the measurement may show. `{strip}` is the strip the engine filed the reading under, `{like}` the already-measured strip it matches. When it is asked, and when it is not: §11b.*

*Beta 8 (2026-10-04, Knut [5969949735](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5969949735): he read strip B on purpose with the reader on A, and the window offered no way to say so). A third button, **I read strip {like}**, between the two, and the line above that explains it, are new. **The button's name, "I read strip {like}", was approved by Knut on 2026-10-04**, #182 [5979780372](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979780372) (*"all are ok"*, question 3 of [5979436912](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979436912)); the line explaining it, and the rest of the window's own words, still wait here. The engine cannot move a reading to another strip, so that answer sends the reader to {like} to be read again there; "Re-read" and "I read strip {like}" both set the reading filed under {strip} aside: it is never compared with again, and {strip} counts as unread until it is read.*

> **Was a strip read twice?**
>
> Strip {strip} looks very like strip {like}, which you already measured. Did you read strip {like} again?
>
> •  Re-read strip {strip}: the reader goes back to strip {strip}. Read it again and the new reading replaces this one.
>
> •  I read strip {like}: the reader goes to strip {like}. Read it there again, then read strip {strip}, which still has to be measured.
>
> •  Keep, it is strip {strip}: this reading stays as strip {strip}, and measuring goes on.

### M-CR-STRIPS · PROPOSED · which strips to re-measure, and why — Check & Refine, the result window and its saved report

*New 2026-10-03. The design was approved by Knut, #182 [5963903650](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963903650) Q1 and Q3, on the pictures in [5963737221](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963737221). **Every line the pictures showed is kept word for word**; the lines marked (not shown) are the singulars and the cases the pictures had no example of. The window composes its text from these lines, one per line below, and the saved Quality_Check report carries the same lines as plain text. `{de}` is the name of the formula the check used (ΔE00, ΔE94 or ΔE76). The rules that decide what is listed: §11a.*

*Beta 9 (2026-10-04): the two "Not offered again, because ... already confirmed ..." lines are **removed**, with the rule they reported: Knut ruled in [5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281) that confirmed or unconfirmed patches have no influence on Check & Refine (§11, the purpose). The rest is unchanged and still waits here.*

> **Re-measure these strips first**
>
> Average {de} {avg} | Largest {de} {peak}
> 1 of {total} patches is above your limit of {de} {limit}. (not shown)
> {n} of {total} patches ({pct}%) are above your limit of {de} {limit}.
> No patch is above your limit of {de} {limit}. Nothing needs re-measuring. (not shown)
> Re-measure these strips first (worst first). Each has a patch that may have been misread, and a re-read shows whether it was:
> Strip {strip}
> Patch {patch} ({de} {value}) stands out clearly from the rest of this check.
> Patch {patch} ({de} {value}) looks partly like its neighbour {neighbour}, as if the instrument was moved unevenly. Move it steadily over strip {strip}.
> {n} patches in this strip are above your limit.
> 1 more strip has at least one patch above {de} {limit} (worst patch, and how many are above): (not shown)
> {n} more strips have patches above {de} {limit} (worst first; worst patch, and how many are above):
> 1 strip has at least one patch above {de} {limit} (worst patch, and how many are above): (not shown)
> {n} strips have patches above {de} {limit} (worst first; worst patch, and how many are above): (not shown)
> Re-measure the strip listed first
> Re-measure the {n} strips listed first
> Re-measure all {n} strips above your limit
> The guide takes you through the chosen strips in chart order (A, B, C ...), the order the instrument reads them in.

### M-CR-START-OVER · PROPOSED · more than half of all patches are above the limit — Check & Refine, the result window and its saved report

*New 2026-10-03. The rule was approved by Knut, #182 [5963903650](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963903650) Q2; this text is the framed note the picture of run2 at 0.5 showed, word for word. Refinement stays offered below it.*

> **More than half of your patches are above your limit**
>
> More than half of your patches are above your limit ({n} of {total}, {pct}%). Re-measuring strips is unlikely to fix all of this: printing and measuring a fresh chart is recommended. You can still re-measure the strips below first, to rule out reading mistakes. If your limit is very strict, a higher one may suit this printer better.

### M-CR-PRECONDITIONING · PROPOSED · what "Use as pre-conditioning profile" does — Check & Refine and Profile Built

*New 2026-10-03. Knut, #182 [5963903650](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963903650) Q6, "OK" to this text as the pictures showed it; it waits here only because §M is where a text is approved as text. It replaces, in both windows, a description that said the next chart "will sample more in the colour regions your printer reproduces least accurately", which is not what ArgyllCMS `targen -c` does, and that recommended the button. In Check & Refine the button is no longer the highlighted one when refinement is offered.*

> **Use as pre-conditioning profile**
>
> Use as pre-conditioning profile: start a new chart whose patches are spread evenly by how colours look on this printer and paper, using this profile as a guide, instead of evenly by RGB numbers. This often gives a better second profile. It does not aim the new patches at the colours that measured badly here, so it does not replace re-measuring. This profile and its measurements stay in their own run folder.

### M-PROFILE-VERIFY · PROPOSED revision · rebuilding under existing verification measurements — §6

*Revised 2026-10-03. Knut, #182 5964384250 Q1: a rebuild archives the profile only, so "Build here anyway" no longer moves the dated verifications. 5964076758 Q4: "Each was printed through the profile" was untrue for raw and FROM PROFILE GAMUT sheets; "Each was checked against the profile this run had at the time" is true for all three, and after a "Keep them" (§6f). The behaviour is his; the wording is ours. When it is shown, its buttons and its checkbox are unchanged (§6d, §6e).*

> **This run already has verification measurements**
>
> This run holds {n} dated verification measurements, going back to {date}. Each was checked against the profile this run had at the time.
>
> Building a new profile here deletes nothing, and the measurements stay correct readings of their sheets. But they would then belong to an earlier profile, and comparing them with verification measurements made afterwards would mean comparing two different profiles.
>
> What each button does:
>
> •  Duplicate the run and build there (recommended): copies this run's chart, measurement and profile into a new run and builds there. This run keeps its profile, its verification measurements and their reports exactly as they are.
>
> •  Build here anyway: replaces this run's profile. The current profile is moved to the run's “old” folder. The verification measurements, their reports and the verification chart stay where they are. When you next choose Verification, ChromIQ offers to move the measurements to the “old” folder inside “verifications”. Nothing is deleted.
>
> •  Cancel: changes nothing.{blocked}
>
> ☐ Don't show this again for this run

Singular form: title "This run already has a verification measurement"; "This run holds one dated verification measurement, made on {date}. It was checked against the profile this run had at the time." / "… the measurement stays a correct reading of its sheet. But it would then belong to an earlier profile, and comparing it with …" / "… its verification measurement and its reports …" / "The verification measurement, its reports and the verification chart stay … offers to move the measurement …".

### M-VERIFY-EARLIER-PROFILE · PROPOSED · Verification chosen; old measurements and a FROM PROFILE GAMUT chart from the earlier profile — §6f, text A

*New 2026-10-03. The window and its buttons are Knut's (#182 5964384250 Q1, 5965626117); the wording is ours. No sound. The first button is the default; Escape and the close button mean Keep. Shown before the wording is approved on the same footing as M-STRIP-READ-TWICE: Knut asked for the window itself. {profile_when} is the current profile's header time (YYYY-MM-DD HH:MM), {date} the oldest measurement named.*

> **The verification measurements in this run were made with an earlier profile**
>
> This run's profile was replaced on {profile_when}. The {n} dated verification measurements going back to {date} were made with the earlier profile, and so was the FROM PROFILE GAMUT verification chart. A sheet printed from that chart would test the earlier profile, not the current one.
>
> What each button does:
>
> •  Archive them and make a new chart from the current profile (recommended): moves the {n} measurements and their reports to the “old” folder inside “verifications”. Nothing is deleted. Create Chart then opens on FROM PROFILE GAMUT with this run's last settings. When you press Generate Chart, the old chart is moved to “old” too. Then print the new chart and measure it.
>
> •  Keep them: changes nothing. You can look at them, move them or delete them yourself. ChromIQ asks again the next time you start it.

Singular form: title "The verification measurement in this run was made with an earlier profile"; "The dated verification measurement from {date} was made with the earlier profile, and so was …" / "Archive it and make a new chart from the current profile (recommended): moves the measurement and its reports …" / "Keep it: changes nothing. You can look at it, move it or delete it yourself. …". Buttons: **Archive them and make a new chart from the current profile** (singular: **Archive it and make a new chart from the current profile**), **Keep them** (**Keep it**).

### M-VERIFY-EARLIER-PROFILE-KEEP-CHART · PROPOSED · Verification chosen; old measurements, and a chart that can be used as it is — §6f, text B

*New 2026-10-03. Knut, 5964384250 Q2: an ordinary chart is kept; 5965626117: Create Chart opens anyway, so the user can confirm the chart and go on to printing. The wording is ours. The title is text A's, in both forms.*

> **The verification measurements in this run were made with an earlier profile**
>
> This run's profile was replaced on {profile_when}. The {n} dated verification measurements going back to {date} were made with the earlier profile. The verification chart itself can still be used: print it again and measure the new sheet.
>
> What each button does:
>
> •  Archive them (recommended): moves the {n} measurements and their reports to the “old” folder inside “verifications”. Nothing is deleted, and the chart stays. Create Chart then opens on this chart, so you can check that it is the one you want before you print it.
>
> •  Keep them: changes nothing. You can look at them, move them or delete them yourself. ChromIQ asks again the next time you start it.

Singular form follows text A ("The dated verification measurement from {date} was made with the earlier profile." / "Archive it (recommended): moves the measurement and its reports …" / "Keep it: …"). Buttons: **Archive them** (**Archive it**), **Keep them** (**Keep it**).

### M-VERIFY-EARLIER-PROFILE-NO-CHART · PROPOSED · Verification chosen; old measurements, and no verification chart at all — §6f, text B without a chart

*New 2026-10-03 (review of the §6f build). Text B, less the two sentences about a chart the run does not have. The wording is ours.*

> **The verification measurements in this run were made with an earlier profile**
>
> This run's profile was replaced on {profile_when}. The {n} dated verification measurements going back to {date} were made with the earlier profile.
>
> What each button does:
>
> •  Archive them (recommended): moves the {n} measurements and their reports to the “old” folder inside “verifications”. Nothing is deleted. Create Chart then opens.
>
> •  Keep them: changes nothing. You can look at them, move them or delete them yourself. ChromIQ asks again the next time you start it.

Singular form follows text B. Buttons: **Archive them** (**Archive it**), **Keep them** (**Keep it**).

### M-VERIFY-CHART-EARLIER-PROFILE · PROPOSED · Verification chosen; only the FROM PROFILE GAMUT chart is from the earlier profile — §6f, text C

*New 2026-10-03. Knut, 5964384250 Q1 and Q3. The wording is ours.*

> **The verification chart in this run was made from an earlier profile**
>
> This run's profile was replaced on {profile_when}, after this FROM PROFILE GAMUT chart was made from the earlier profile. A sheet printed from it would test the earlier profile, not the current one.
>
> What each button does:
>
> •  Make a new chart from the current profile (recommended): Create Chart opens on FROM PROFILE GAMUT with this run's last settings. Nothing changes until you press Generate Chart, which moves the old chart to the “old” folder inside “verifications”.
>
> •  Keep it: changes nothing. ChromIQ asks again the next time you start it.

Buttons: **Make a new chart from the current profile**, **Keep it**.

### M-VERIFY-EARLIER-ARCHIVED-HERE · PROPOSED · where the measurements of the earlier profile went — the Create Chart log, after text A or B

*New 2026-10-03, in the manner of M-CAL-ARCHIVED-HERE: two lines in the log of the tab the window opens. If not everything could be moved, the log says instead "[WARNING] Not everything made with the earlier profile could be moved: {error}. What did move is in: {folder}"; nothing that moved is moved back.*

> **The verification measurements made with the earlier profile have moved to this folder, and nothing in them was deleted:**
>
> {folder}

Singular form: "The verification measurement made with the earlier profile has moved to this folder, and nothing in it was deleted:".

### M-VERIFY-CREATE-NO-PROFILE · PROPOSED · Create Chart, verification with no profile — #133 §10

*Feature B. The wording was agreed VERBATIM with Sebastian on #133
(2026-08-02), before this review queue existed; it is defined here so the
formal record is complete. Shown as the non-blocking info box at the foot of
Guided / Manual while Run type = Verification and the run has no built
profile — those modules stay fully usable.*

> **There's no finished profile in this run yet**
>
> You can go ahead and create the chart — the files will be ready and waiting for you. Printing and measuring it will have to wait for the profile, though: a verification chart is printed through your finished profile, and that's the whole point of it. Measuring one without a profile is turned off for the same reason.
>
> To get there: set Run type to Profiling, then create, print and measure the profiling chart as usual and build the profile on the Build Profile tab. Come back here afterwards and everything will be ready for you.

### M-GAMUT-NO-PROFILE · PROPOSED · the From-profile-gamut module with no profile — #133 §10

*Feature B, same provenance as the message above. Shown INSTEAD of the
module's options, with Generate disabled — the profile's gamut is this
module's input, so without one there is nothing to ask.*

> **This run needs a finished profile first**
>
> This way of making a chart asks your profile which colours it believes your printer can produce, and then tests exactly those. {run} doesn't have a profile yet, so there's nothing to ask.
>
> How to get one:
> &nbsp;&nbsp;1\. Set Run type to Profiling.
> &nbsp;&nbsp;2\. Create, print and measure the profiling chart as usual.
> &nbsp;&nbsp;3\. Build the profile on the Build Profile tab.
> &nbsp;&nbsp;4\. Come back here and set Run type to Verification again.
>
> GUIDED and MANUAL can still build you a chart in the meantime, so the files are ready. Printing and measuring any verification chart waits for the profile either way.

### M-IMPORT-MISMATCH · PROPOSED · an imported file fails validation — Measure ▸ IMPORT

*The IMPORT module (verification runs) files a measurement made in i1Profiler
through the same doors a native measurement uses — but only after checking,
patch by patch, that the file belongs to this run's verification chart.
`{reason}` names the failed check in plain words (patch counts, or the
patch-identity comparison).*

> **This file does not match the verification chart**
>
> Before filing anything, ChromIQ checks that the measurement really belongs to this run's verification chart — and this one does not:
>
> {reason}
>
> Nothing has been imported and nothing has been changed.
>
> The two usual causes: the file belongs to a different chart, or the patches came back in a different order than they were sent — that can happen when the shuffled i1Profiler export was used for measuring. Use the chart's normal export (the file without "shuffled" in its name), measure again, and import that.

### M-IMPORT-DEVICE-FROM-CHART · PROPOSED · the measurement carries no device values — Measure ▸ IMPORT

*i1Profiler's measure tool reads a chart it did not generate, so it has no
colour space to express device values in and exports none: `SAMPLE_ID`,
`SAMPLE_NAME` and the spectral curve. ChromIQ pairs such a file with the chart
by the patch NAME each reading carries and takes the device values from the
chart, exactly as chartread does. The patch-identity check compares device
values, so on this file it has nothing to compare, and the person is told so
before anything is filed. `{count}` is the number of readings and `{chart}` the
chart's file name. Two buttons: **Import it** and **Cancel**.*

> **Only you can confirm this is a measurement of this chart**
>
> This file holds the colour of every patch and no record of the ink that made it. i1Profiler writes it that way when it measures a chart it did not generate itself: there is no colour space for it to put device values in, so it puts none.
>
> ChromIQ can still file it. All {count} readings name a patch of {chart}, and the chart knows what was printed at each of those names, so the chart supplies the device values, exactly as it does for a measurement made here.
>
> What ChromIQ cannot do is check the file against the chart. That check compares the device values in the measurement with the chart's, and this file has none. The names all belong to this chart, which is as far as names can go: another chart laid out the same way carries the same names.
>
> Import it only if this is the measurement of the sheet printed from {chart}. Cancel changes nothing.

*Singular ({count} = 1):*

> This file holds the colour of its patch and no record of the ink that made it. i1Profiler writes it that way when it measures a chart it did not generate itself: there is no colour space for it to put device values in, so it puts none.
>
> ChromIQ can still file it. Its one reading names a patch of {chart}, and the chart knows what was printed at that name, so the chart supplies the device values, exactly as it does for a measurement made here.
>
> What ChromIQ cannot do is check the file against the chart. That check compares the device values in the measurement with the chart's, and this file has none. The name belongs to this chart, which is as far as a name can go: another chart laid out the same way carries the same names.
>
> Import it only if this is the measurement of the sheet printed from {chart}. Cancel changes nothing.

### M-IMPORT-DATE-TAKEN · PROPOSED · importing over an existing dated result — Measure ▸ IMPORT

*The import never replaces an existing dated measurement; the way to a fresh
check is the same field a native measurement uses.*

> **This verification already holds a measurement**
>
> The verification from {when} already has its measurement, and importing over it would replace a result you may still need.
>
> Nothing has been imported and nothing has been changed.
>
> To file this measurement as a new check, set the "Verification" field in the bar above to "New verification" and press Import Measurement again — it gets its own dated folder, and the earlier result stays exactly as it is.

### M-IMPORT-DONE-PROFILING · PROPOSED · the import succeeded, into a profiling run — Measure ▸ IMPORT

*New 2026-09-15. The twin of the approved import-done window, for the run type
that door could not reach until now. A tester looked for the import on the
Measurement tab in a profiling run and found it only on Build ICC profile;
Sebastian ruled that the module is offered on the Measure tab for a profiling
run as well, and that the Build ICC profile tab's own import stays where it is.
The approved wording cannot be reused: every sentence of it is about a
verification, and its dated folder does not exist for a profiling run. The two
buttons are §I.9's I.8 ("offers Open measurement report and Build the
profile"); `{run}` is the run the file actually went into, which is not always
the run that was on the bar when the button was pressed — a run that already
held a measurement is duplicated rather than written over (§I.9).*

> **The measurement was imported**
>
> It is filed as the measurement of {run}, in:
> {folder}
>
> A copy of the chart it was measured against is stored with the run, so the result stays interpretable even if the chart is replaced later.
>
> You can build a profile from it now on the Build ICC profile tab, or open Tools ▸ “Measurement report” first to see the colour-accuracy figures.

### M-CHART-VERIFY · PROPOSED · replacing the verification chart — §4 (W5), revised wording

*Revised after the 2026-08-10 hardware session; the previous approved text
claimed the displaced measurements would "no longer have the chart they
were made with" (untrue — every measured date snapshots its chart) and its
Duplicate advice contradicted its own "no measurement is touched". The
M-DUPLICATE-BLOCKED note was stripped of its four-file jargon at the same
time.*

> **The verification measurements already made in this run used the chart you are about to replace**
>
> The {v} dated verification measurement{s} in this run were made with this verification chart. Replacing it does not make them wrong — each date keeps its own stored copy of the chart it was measured with, so every result stays readable, and "Restore Used Chart" can bring a date's chart back on screen.
>
> One thing to keep in mind: a trend across the change compares two different charts, which is not the same measurement made twice.
>
> The chart itself moves to the "old" folder inside "verifications"; no measurement is touched and nothing is deleted. If you would rather keep measuring the current chart, duplicate the run first — it lives on in the copy.

### M-HOW-PRINTED · PROPOSED · asking how an unrecorded verification sheet was printed — Measure tab, at save time

*New with pairing 3 (the media-relative yardstick, agreed with Knut and
Sebastian 2026-08-10). Shown once, just before the saved/imported window,
only when a verification measurement is being filed and its sheet has no
print record — ChromIQ's own prints and answered sheets are never asked
again. Buttons: **Raw — no profile** · **With colour management** ·
**Not sure** (default). The answer is written into the dated folder's
print record with `recorded: "asked-at-measure"`; Not sure leaves the
sheet unrecorded, exactly as today.*

> **How was this sheet printed?**
>
> ChromIQ did not print this sheet itself, so it does not know whether a profile took part — and the measurement report needs to know, because the two kinds of sheet are judged differently.
>
> Raw — no profile: the chart's own numbers went straight to the printer, with every colour setting off. Measuring it checks the printer, not a profile.
>
> With colour management: the sheet was printed from another application (for example Photoshop) with this run's profile applied. Measuring it checks your whole everyday printing chain, and the report judges it relative to the sheet's own paper white — so the paper is not counted against the profile.
>
> Not sure is always safe: the report simply notes that the printing method is not recorded, and judges the colours as they are. Your answer is stored with this measurement only — it changes nothing else.

### M-ALL-STRIPS-PATCHES-LEFT · PROPOSED (revised 2026-08-14) · every strip read, but patches inside them are not — Measure tab

> **Some patches are still unread**
>
> Every strip has been read, but {n} patches still have no reading. Everything you have read so far is safe.
>
> This usually happens when some patches were read one at a time in **Patch-by-patch mode** and a few were stepped over.
>
> To finish them, start measuring again with **Patch-by-patch mode** ticked and **Refine / resume existing measurement (-r)** ticked. ChromIQ picks up where the readings stop, so you only measure the patches that are still missing rather than the whole chart again.
>
> • **Re-read Individual Strips** — stay in this session and read a strip again now. Use **f** and **b** to move between strips, **n** to jump to the next unread one, and **d** when you are done.
>
> • **Close** — finish here. ChromIQ asks whether to keep what you have measured so far, so nothing is decided behind your back.

*Revised after Knut's review of the first draft (2026-08-14), which he corrected
on three counts.*

**1. The cause was wrong.** The first draft said *"a slight wobble as the
instrument passes over them is enough"*. His answer: *"is not likely. if not
enough patches are registered it is caught. The likely reason is that a user has
used patch-by-patch mode to read some patches and missed some."* The message now
says that instead. Nothing here asserts a mechanism that has not been observed.

**2. The button was invented.** The first draft told the user to press
**"Stop & Save"**, which is not a button this app has. His answer: *"The button
'Stop & Save' is not the wording used for other windows … like the All Patches
Read (for patch-by-patch mode) and All Strips Read (for strip mode) [which] have
one button to Close, which calls the window where user decides to stop and save,
or stop and discard. This is the unified exit method defined in the design spec,
which you would have known."* He is right that it is defined, and right that I
should have read it: `measurement_exit_strategy.md` §"The single exit".

**3. Every button needs its own explanation** — *"the rules used in the design
specification is that all windows have an explanation for each button in a
window"* — so both now carry one.

**It must exist in all four cases.** Strip mode and patch-by-patch, on ChromIQ's
engine and on stock ArgyllCMS chartread, are four separate windows with different
exit keys behind the same buttons (`measurement_exit_strategy.md`, Tables 1 and
2). A window raised from one parser only reaches half the users, and the stock
half working is what has hidden that four times already. So this window is to be
raised from code both `_handle_line` and `_handle_engine_line` reach, and its
Close must delegate to `_confirm_end_of_session`, which already knows which mode
and which reader it is in rather than sending a key of its own.

**4. It is a STRIP-MODE window, so its button re-reads strips.** The first
revision offered "Re-read Patches", which he corrected: *"this message is for a
strip mode session (and this message only happens during strip mode), not a
patch-by-patch session. Here one would 'Re-read strips'."* The button now matches
the completion window it stands in for, and the guidance in the body still points
at patch-by-patch + resume, because that is how the missing patches get finished
in a later session — which he approved separately.

**Close — ruled 2026-08-14.** He answered **(A)**: *"Close should raise the 'Keep
what you have measured so far?' window. However, the description 'keeps the
measurement, goes nowhere' is still correct, because it is referring to the other
button that says to jump to build profile tab."* So the row in
`measurement_exit_strategy.md` is not stale — it was read against the wrong
button. Close raises the ending; the Go-to-tab button is the one that keeps the
measurement and moves on.

**Both readers, per his instruction:** *"If this check is possible to implement
for the stock argyllcms chartread engine also, then the button commands should be
made to use the correct command for the specific chartread engine, according to
the measurement exit strategy in the design specification. Use the All Strips
Read window for each engine as basis for the correct action to use to re-read or
to Close / exit."* So both buttons take their keys from the All Strips Read row
of Table 1 (engine) and Table 2 (stock) rather than sending anything of their
own.

### M-ENGINE-FELL-BACK · PROPOSED · ChromIQ's own measuring engine could not use the instrument — Measure tab

> **Measuring with ArgyllCMS instead**
>
> ChromIQ's own measuring engine could not use your instrument this time, so the measurement has been started again using ArgyllCMS's chartread. Carry on measuring exactly as you would normally — nothing you have already read is lost.
>
> One thing changes while this is running: **ChromIQ's measurement sounds are silent.** ArgyllCMS makes its own beeps as it reads, and playing ChromIQ's sounds on top would double every one of them. The beeps you hear are coming from ArgyllCMS.
>
> Reason: {reason}

*Why it is proposed rather than in use.* Knut asked for it directly (#148,
2026-08-14): *"there should be a defined and approved instrument error message in
the design specification for this error, is there not? I think there should be a
warning message so the user knows."* He is right that there is none — the
fallback is announced only in the measurement log
(`workflow/measure_manager.py`, `engine_fell_back_resumed`), which is easy to
miss mid-measurement.

*Why the second paragraph matters as much as the first.* The fallback silently
changes a second thing: `SoundManager.play` deliberately suppresses every
per-patch and per-strip sound while stock chartread is driving, because chartread
beeps for itself and cannot be silenced (Knut's own ruling, #131 2026-07-27). So
a user whose engine falls back loses ChromIQ's sounds for the rest of that
measurement, is told nothing about it, and has every reason to report it as the
sound feature being broken — which is one of the two things being untangled in
#148. The suppression itself is correct and stays; what is missing is saying so.

Until this is approved, the fallback continues to write its line into the
measurement log, and `core.sound` now logs each suppressed sound with the reason,
so a log can at least distinguish "deliberately quiet" from "audio broken".

### M-NO-INSTRUMENT-FAST · PROPOSED · the instrument is not there, and the connection shortcut is on — §S2

*The same moment as M-NO-INSTRUMENT, and the same text, plus one paragraph.
Knut, 2026-08-13: his ColorMunki was found on a 2023 MacBook Pro and not on a
2019 one — in strip mode, patch-by-patch and Read Single Patches alike — and
switching off "Faster instrument connection" was the whole fix:* "That did it…
Now it works. Maybe the No Instrument detected message could warn about this
setting?" … "warning about this setting not working on all computers,
especially some older hardware, might be good. And suggesting to also test
connecting without that setting."

*Two things about it are instruction rather than text. The window carries the
switch itself —* "Maybe the pop-up should have this option linked already so
the user does not have to go to preferences to find it" *(Sebastian; Knut:*
"Sounds ok"*) — as a **Turn off faster connection** button beside OK, which
sets the preference and leaves the session ending exactly as before. And the
paragraph names where the option lives for later (Sebastian: Preferences ▸
Measurement), so someone who wants the shortcut back can find it. Which of the
two messages is shown follows the preference: with the shortcut off, Knut's
original text is unchanged.*

> **No Instrument Found**
>
> ChromIQ has started the measurement and asked your instrument to wake up, and it has not replied for {n} seconds. A working instrument answers almost at once, so something is in the way.
>
> This is nearly always the connection rather than anything you did. Try these in order:
>
> •  Unplug the instrument's USB cable and plug it back in.
> •  Use a different USB port, and plug straight into the computer rather than through a hub.
> •  Close anything else that may be holding the instrument — another profiling program, or a virtual machine.
>
> One more thing is worth trying, and it is the likeliest cause on an older computer. ChromIQ is using a shortcut called “Faster instrument connection”: it skips the ports an instrument is never plugged into, so the calibration prompt appears sooner. On some computers that shortcut is what stops the instrument being found at all. The button below turns it off straight away — then start the measurement again, and your instrument will very likely be found. Nothing else about your measurements changes, and you can switch it back on whenever you like in Preferences ▸ Measurement, where it is called “Faster instrument connection”.
>
> Nothing has been lost. The measurement you already had is put back exactly as it was if this session ends without reading anything, and you can keep waiting instead if you would rather.

### M-SPOT-CLEAR · PROPOSED · the second look before the spot list is emptied — Tools ▸ Read single patches

*New message (2026-09-03). Knut reported the spacebar as an annoyance:
"pressing spacebar there which is a trigger in measure tab closes the read
single patches window even in an active session." Driving the real window shows
it is worse than that. `setEnabled(false)` on the focused **Take reading**
button makes Qt walk the focus on to the next ENABLED button, and once there
are readings in the table that button is **Clear** — which had no question,
no undo, and left the window open, so nothing on screen said a whole session
had just been thrown away.*

*Two independent guards, because they cover different mistakes. This one stops
the click that was never meant. The Clear button then turns into "Undo clear"
until the next reading arrives, which covers the click that was meant and
regretted. Nothing the user made is destroyed without a way back.*

*Shown only when the list is not empty, and it states the count, so the person
can see whether it is the reading they just took or an afternoon of them.*

> **Clear every reading in this list?**
>
> This window holds {n} readings, and none of them are saved to a file yet.
>
> Clearing empties the list. Nothing is written to disk and nothing is asked of the instrument, so if you clear by mistake press “Undo clear” and every reading comes straight back. The next reading you take replaces what Undo would restore.
>
> To keep them, choose Cancel and use Save first.

*Singular, when the list holds one:*

> This window holds one reading, and it is not saved to a file yet.
>
> Clearing empties the list. Nothing is written to disk and nothing is asked of the instrument, so if you clear by mistake press “Undo clear” and the reading comes straight back. The next reading you take replaces what Undo would restore.
>
> To keep it, choose Cancel and use Save first.

*Buttons: **Clear** (destructive) and **Cancel** (default).*

### M-SPOT-UNSAVED · PROPOSED · closing a spot window that holds readings nobody saved — Tools ▸ Read single patches

*New message (2026-09-03), found while fixing the one above and independent of
it. The readings live in `self._readings` and nowhere else; the only thing that
writes them out is Save. `reject()`, `closeEvent()` and therefore **Escape**
all went straight to releasing the instrument and out, so Close, the red window
button and a stray Escape each discarded an entire measuring session without a
word.*

*Three ways out, and each says what it does, because the difference matters
here: the readings cannot be recovered afterwards by any route. Save is the
default, and if the file dialog is cancelled the window stays open rather than
closing on work it did not write.*

*Not shown when everything in the list has already been saved, so the ordinary
end of a session is still one click.*

> **These readings are not saved yet**
>
> This window holds {n} readings that are not written to any file. They live in this window only, so closing it lets them go.
>
> Save writes them as a CSV and an ArgyllCMS .ti3 beside the run you are working on, and then the window closes. Discard closes the window and loses the readings. Cancel leaves the window open exactly as it is, with every reading still in the list.

*Singular, when the list holds one:*

> This window holds one reading that is not written to any file. It lives in this window only, so closing it lets it go.
>
> Save writes it as a CSV and an ArgyllCMS .ti3 beside the run you are working on, and then the window closes. Discard closes the window and loses the reading. Cancel leaves the window open exactly as it is, with the reading still in the list.

*Buttons: **Save** (default), **Discard** (destructive) and **Cancel**.*

### M-SCAN-WP-DEFAULT · PROPOSED · the scanner white-point default moved, and existing settings moved with it — Tools ▸ Build profile with scanner or camera

*New for 4.1.5-beta.9, 2026-09-05. The white-point handling a scanner or camera profile is built with moved from "Map chart white to white" (no colprof flag) to "Scale white to a perfect white surface" (`colprof -u -R`). **Basti ruled the migration**: existing remembered settings adopt the new default rather than being pinned to the old one — "our user base is not very big at the moment so i want the better default". This message is the other half of that ruling. CLAUDE.md's principle 10 is "migrate schemas in place, ANNOUNCE it, keep the old files", and this is exactly that case: somebody who re-profiles a scanner they have profiled before gets a visibly different profile, and nothing else in the app would tell them why.*

*Shown once, in the window's LOG, the first time the window opens after the migration has actually changed something — never for a user who had no stored settings, and never twice. It is in the log rather than a window because §M's rule is that unapproved wording speaks through the log, and because nobody has asked for a window here; if Basti would rather it were a window, the mechanism is the same and only the presentation changes.*

*The measured case behind the change (re-measured independently 2026-09-05 on the 864-patch IT8 scan in `beta 9/knut-whitepoint/`, `colprof -ax -qh`): the old default put the chart's own white board at PCS white, and that board is 84.286 % reflectance, so four physically different whites — the board at 84 %, a brighter paper at 89 %, a very bright paper at 95 % and a perfect diffuse reflector at 100 % — all reached L\* 101.1 / 103.5 / 106.1 / 108.1 and every one of them landed on sRGB 255/255/255. Under `-u -R` the same four land at L\* 93.50 / 95.69 / 98.12 / 99.98 and none of them clips. Accuracy is unchanged: profcheck avg ΔE00 0.336709 against 0.336727. Neutrality is unchanged too — the board reads a\* −0.83 / b\* −0.50 against the old default's −0.89 / −0.53 — which is what separates this from `-ua`, whose board carries the chart's real cast at a\* +1.49.*

> **The white point setting for new scanner profiles has changed**
>
> ChromIQ used to build scanner and camera profiles so that the white patch of your test chart became pure white. It now scales white to a perfect white surface instead — the entry "Scale white to a perfect white surface (-u -R)" under Advanced… ▸ White Point ▸ White point handling. Your remembered settings for this window have been moved to it, which is why you are reading this.
>
> Why it moved. Under the old setting, anything you scanned that was lighter than your chart's own white board came out as flat white with no detail left in it, and no amount of editing afterwards could bring that detail back. A test chart's white board is not very white: on the scan this was measured from it is 84 % as bright as a perfect white surface, so that board, a brighter paper, a very bright paper and a perfect white surface all came out as exactly the same white. The new setting keeps them apart. It is just as accurate as the old one, and it keeps whites just as neutral.
>
> What this does not change. Every profile you have already built is a file on disk and is untouched. So is every measurement, every chart and every project. Nothing has been rebuilt, converted, moved or deleted, and no profile changes unless you build it again.
>
> What you will notice. A profile you build from now on makes scans open a little darker — a white board lands at about 93 out of 100 in lightness rather than at 100 — so a scan wants one levels or curves step to finish. Nothing has been lost by that: the highlight detail that used to be flattened is now there for you to work with.
>
> If you preferred the old behaviour, it has not gone anywhere. Open Advanced…, and under White Point set "White point handling" back to "Map chart white to white". That is exactly what ChromIQ did before. Press "Save as Defaults" and it will stay that way.

*No buttons: it is a log entry, not a window.*

### M-SCAN-REF-SHORT · PROPOSED · the reference file covers only part of the target — Tools ▸ Build profile with scanner or camera

*New for 4.1.4, review 5 (2026-09-03), finding D. **The most serious thing this
window does.** A reference file holding the first 48 rows of the target's own
correct 288-row reference — a truncated download, a partial export, a maker's
"short" file — builds a profile from a sixth of the sheet while every indicator
on screen is green: "✓ Ready — 288 patches, reference loaded", the alignment
tick at "worst 99.84 %, average 99.96 %", and colprof's own self-check at
0.185 / 0.076, which is **better** than the correct 288-patch build's
0.620 / 0.098 because forty-eight points fit a matrix beautifully. The `.ti3`
records `NUMBER_OF_SETS 48`: 240 patches were read off the scan and thrown away
in silence. The 288 on screen is the `.cht`'s count and nothing ever compared it
with the reference's own rows.*

*Shown the moment the reference is picked, in the status line under the
"Target reference data" row, where the user can still fix it by choosing another
file — and again as a line in the pre-build warning window, so it cannot be
scrolled past. `{covered}` is how many of the chart's patches the reference
names, `{total}` how many the chart has, `{missing}` the difference.*

*The opposite case says nothing: a reference with MORE rows than the chart has
patches builds a perfect profile, because the extra rows simply go unused
(measured: peak 0.62, average 0.098 from a 400-row reference for a 288-patch
target).*

> **This reference file covers only part of the target**
>
> The reference file you picked gives colours for {covered} of the {total} patches on this target. ChromIQ can only use the patches the reference names, so the other {missing} would be read from your scan and then thrown away, and the profile would describe your scanner from a fraction of the sheet.
>
> Nothing later would show it. A profile built from fewer patches passes its own quality check more easily, not less.
>
> In the “Target reference data” row, pick the full reference file that came with this target. That file lists every patch, so it has about as many rows as the target has patches.

*Singular, when exactly one patch is missing:*

> The reference file you picked gives colours for {covered} of the {total} patches on this target. ChromIQ can only use the patches the reference names, so the remaining one would be read from your scan and then thrown away.
>
> In the “Target reference data” row, pick the full reference file that came with this target. That file lists every patch, so it has about as many rows as the target has patches.

### M-SCAN-REF-DISAGREES · PROPOSED · what was read does not match the reference — Tools ▸ Build profile with scanner or camera

*New for 4.1.4, review 5, findings B2 and B4. ChromIQ already computes the one
number that names a wrong reference or an upside-down scan —
`scan_reference_correlation`, the rank agreement between how light each patch
read and how light the reference says it is — and used it only to decide whether
to run a further check. Measured: **+0.94 to +0.97 on every good read, and −0.60
to +0.14 on every broken one**. When it collapsed, the window quietly declined
to judge and then printed a green tick from the geometric ladder, which never
looks at the reference at all.*

*An upside-down scan is the ordinary flatbed mistake and the clearest case: the
patch block maps onto itself, so every geometric check passes, every patch reads
its opposite number's colour, and only colprof's fit noticed, at the very end.*

*Shown as a line in the pre-build warning window, which already offers Stop and
Build anyway. `{rho}` is the measured agreement, to two decimals.*

*The floor is **0.25**, not the 0.8 the existing `ref_usable` gate uses for a
different purpose. A strongly saturated target (LaserSoft) ranks at ρ≈0.5 even
on a perfect read, which is why that gate exists; this one must sit well below
it. Measured against 30 legitimate reads on two targets across an exposure and
cast sweep, the lowest was **+0.940**.*

> **What was read does not match this reference**
>
> ChromIQ compared how light each patch came out of your scan with how light the reference says that patch is. On a good scan the two run together closely. Here they hardly agree at all: {rho}, where a good read is above 0.9.
>
> That is what happens when the scan is upside down or a quarter turn out, or when the reference belongs to a different target from the one you scanned. A profile built from this read would be wrong, and nothing later would tell you.
>
> Check that the scan is the right way up, and that the file in the “Target reference data” row is the one that came with this target.

### M-SCAN-CLIPPED · PROPOSED · the scan has run out of scale — Tools ▸ Build profile with scanner or camera

*New for 4.1.4, review 5, finding B3. A scan with every value lifted 55 % built
a clean profile in silence: 39.2 % of its patches read at the top of the device
scale, rank agreement +0.943 (so the check above cannot see it), and colprof's
self-check passed without a word. Clipping is the one scan fault that cannot be
profiled around — the values are gone, not merely shifted, and the profile
treats "as bright as this scanner goes" as a measurement.*

*Shown as a line in the pre-build warning window. `{pct}` is the share of
patches at either end of the scale.*

*The floor is **15 %**, and it is deliberately late rather than eager. Measured
across an exposure ladder, `profcheck` against the read's own data goes 0.098 →
0.286 → 0.740 → 1.097 → 5.967 average ΔE as the clipped share goes 0 % → 6 % →
11 % → 16 % → 39 %, so the damage becomes real between 10 % and 16 %. Against
that, the highest reading from any legitimate scan measured — including an
extreme warm cast, a low-contrast scan, a second target, and exposures from
×0.12 to ×1.10 — was **9.7 %**. A floor of 15 % keeps a 1.55× margin over the
worst legitimate case and still catches the scan that is ruined.*

> **Part of this scan has no colour left in it**
>
> {pct} of the patches were read at the very end of the scan's brightness range, where there is nothing left to record. Their real colours are gone, not merely shifted, so ChromIQ cannot tell those patches apart and the profile would treat “as far as this scanner goes” as a measurement.
>
> Scan the target again with the automatic brightness and contrast turned off in your scanner software, so that no patch reaches either end of the scale.

### M-SCAN-PROFILE-ARCHIVED · PROPOSED · where the profile this build replaced went — the scanner window's log

*New for 4.1.4, review 5, finding B5. Building twice in the same folder wrote
over the first profile in place: no copy, no question, and not a word in the log
— and it may be one the user has already installed and been working against. The
measurement beside it went the same way. The app's habit everywhere else is to
archive (`runs/run1, run2, …`, `old/<timestamp>/`, "Deleting moves to the
Trash"), and this window was the exception.*

*The archiving itself needs no new wording and is fixed outright. Saying WHERE
does — and the adversarial round of 2026-09-02 established that moving something
and then naming the folder nowhere is a fault of its own, which is why
M-CAL-ARCHIVED-HERE exists. This follows its shape and its sentence deliberately,
with one word changed.*

*Not a window: two lines written into the log the build is already streaming
into. Shown only when an archive was really made — a first build in a clean
folder moves nothing and says nothing.*

> **The profile that was here has moved to this folder, and nothing in it was deleted:**
>
> {folder}

### M-SCAN-DARK · PROPOSED · the scan never reached the top of the scale — Tools ▸ Build profile with scanner or camera

*New for 4.1.5, beta 8, item B8-01. The opposite twin of M-SCAN-CLIPPED, and the
one nothing in the window could see. Every other guard here is
**scale-invariant** and an exposure slip is **pure scale**: darkening Knut's own
Wolf Faust sheet by 30 % leaves the reference coverage unchanged, the rank
agreement unchanged to three decimals (+0.9839 → +0.9838) and the clipped share
unmoved by a single patch. The build is silent from end to end, and the profile
it produces is **21.7 ΔE** out against a correctly exposed read of the same
sheet. At ×0.18 it is **177.9 ΔE** out, peak 335.7, and still silent.*

*colprof's own self-check cannot see it either, because it is computed against
the same dark data: across the whole ladder it moves only 1.93 → 2.59, against
limits of 30 and 12.*

*Shown as a line in the pre-build warning window, beside the clipping line it
mirrors. `{pct}` is where the chart's own white patches landed on the device
scale.*

*The measure is the median of the **largest device channel** over the patches
the reference calls near-white (Y within 5 % of the reference's own brightest).
A properly exposed scan puts the chart's brightest patch near the top of the
scale, because that is what setting the exposure means, and it is the one
statement about level that survives a change of scanner — every encoding curve
fixes white. Three cheaper measures were built and thrown away, each killed by a
legitimate scan beating an under-exposed one: the **mean** device level (a
transparency's tone scale 28.04 against ×0.70's 27.27), the **black patch above
zero** (matte paper 14.52 against ×0.70's 5.04 — upside down), and the white
patch's **luminance** rather than its max channel (a cool cast 66.28 against
×0.85's 66.88).*

*The floor is **60**, and it comes from 74 reads: Knut's ten real IT8 sheets on
two targets read **72.92 – 79.82**; this session's own re-reads of his two
full-resolution scans, 74.84 and 79.77; the app's own demo scan for all 25
bundled and ArgyllCMS targets, **80.96 – 94.34**; nine legitimate variations
built from his scans — a gamma-1.8 scanner, a gamma-2.6 scanner, matte paper, a
transparency tone scale anchored at the medium's Dmin, a warm cast, a cool cast,
a scanner running 12 % hot, 16-bit and JPEG q12 — **69.57 – 83.86**. Against
that, ×0.85 reads 67.84, ×0.70 reads 55.85 and 52.43 on the two targets, ×0.45
reads 35.87 and 33.71, ×0.18 reads 14.47. A floor of 60 is 9.6 points under the
worst legitimate case measured and 12.9 under the worst that came off real
hardware.*

*It says nothing at all when the reference names no near-white patch — a low-key
target has no exposure to judge against. Measured on a deliberately dark chart
(every reference value scaled to 0.28 and the scan darkened to match) the level
reads 44.1, which would be an accusation; the reference's own brightest patch
reads Y = 22.97, and the check declines instead.*

*And it deliberately lets a half-stop slip through. ×0.85 at 67.84 sits 1.7
points under the harshest legitimate case and cannot be separated from it. That
profile is 9.5 ΔE out, which is not free — but a window that fires on a
legitimate scan is worse, because the same user then clicks past the ×0.70 one.*

> **This scan came out darker than it should be**
>
> The white patches on this target came out at {pct} of your scanner’s brightness range. On a scan exposed for this target they sit just under the top of that range, and getting them there is what the brightness or exposure setting in your scanning software is for.

Nothing later in ChromIQ would tell you. A dark scan is not harder to describe than a bright one: it passes every other check in this window, and the quality number you are shown at the end of the build is worked out from this same dark reading, so it comes out looking just as good. What changes is the profile itself — it would describe your scanner in a state you are unlikely to set up again, so it would not match your everyday scans.

Scan the target again with the brightness or exposure turned back up in your scanner’s own software — not in ChromIQ, which never changes your scan — so that the white patches sit just below the top of the scale without touching it.

One exception: if you are scanning a transparency or a negative, a low reading here can be normal for that medium. Check the exposure before you go on, but you may find nothing is wrong.

### M-SCAN-FIT-UNSUPPORTED · PROPOSED · the reference gives too few colours to fit a profile to — Tools ▸ Build profile with scanner or camera

*New for 4.1.5, beta 8, item B8-03, the half that can be caught before the
build. colprof's self-check is measured against the very rows it was fitted to,
so it is **smallest exactly when there is least to fit**. A reference whose every
`SAMPLE_ID` reads `A1` leaves one row and scores `peak err = 0.007339, avg err =
0.007339` — a better mark than any correct build in this document — and the log
ends "Install it as your scanner's input profile". A reference whose every value
reads `0.00` leaves 288 rows of ONE colour, sends colprof's Powell fit to
`residual error = nan`, and lands a 26 KB profile whose white point is `nan nan
nan`, with the same closing line.*

*An error FLOOR cannot separate these, and the number that proves it is the
app's own: the bundled ColorChecker demo builds at `avg err = 0.059311` — a
legitimate, shipped case only eight times above the degenerate one, with a cLUT
build on real data at 0.462 in between. Counting the **distinct** colours can:
**1** for both degenerate references, against **21** for the smallest target
ChromIQ or ArgyllCMS ships (`MLG`), 24 for a ColorChecker, 288 for Wolf Faust
and 864 for the ISO 12641-2. The floor is **10** — under half the smallest
legitimate case and ten times the degenerate one.*

*Shown as a line in the pre-build warning window. It catches the all-zero
reference squarely, where the existing agreement check caught it only by a
whisker (ρ = 0.246 against a floor of 0.25), and it catches it **before** colprof
spends two minutes converging on nan. `{support}` is the number of distinct
colours.*

> **This reference file describes too few colours to build a profile from**
>
> The reference file names only {support} different colours for this target. A profile describes how your scanner answers to colour, and that cannot be worked out from so few.

ChromIQ can still build one, and it would pass its own quality check easily — when there is almost nothing to match against, almost any answer matches. The quality number you are shown at the end of the build would look better than a correct profile’s, and it would mean nothing at all.

In the “{ref_row}” row, choose the reference file that came with your target. It lists a different colour for every patch on the sheet.

*Singular, when the whole reference holds ONE colour — which is what both of
beta 8's degenerate references reduce to:*

> The reference file names the same colour for every patch it lists. A profile describes how your scanner answers to colour, and that cannot be worked out from a single one.

ChromIQ can still build one, and it would pass its own quality check perfectly — when there is nothing to match against, any answer matches. The quality number you are shown at the end of the build would look better than a correct profile’s, and it would mean nothing at all.

In the “{ref_row}” row, choose the reference file that came with your target. It lists a different colour for every patch on the sheet.

### M-SCAN-SELFCHECK-UNUSABLE · PROPOSED · colprof's own quality check produced no number — the scanner window's log

*New for 4.1.5, beta 8, item B8-03, the half that can only be caught after the
build. `_PROFCHECK_RE` matched only digits and dots, so colprof's `avg err = nan`
line did not match at all: `found` came back empty and the verdict returned on
its `if not found` line. **The one case where the check had the most to say was
the one case it could not read.** Even parsed, `0.0 <= 30.0` would have
short-circuited the `or`. The build then wrote "[OK] Scanner profile saved" and
"Install it as your scanner's input profile" over a profile whose white point is
`nan nan nan`.*

*Two lines in the log the build is already streaming into, in the same place as
the existing self-check warning, and it grades the Install button the same way —
"Install Profile Anyway", which is existing wording. `{raw}` is what colprof
actually printed, so the log names its own evidence.*

*No false-positive cost worth stating: a finite fit never reads `nan`.*

> **This profile could not be checked**
>
> After building a profile, ChromIQ asks how closely it matches the colours it was built from, and shows you the answer as a quality number. This time no number came back at all — the answer was “{raw}”, which is what happens when the measurements handed over had nothing in them to match against.

So the file on disk is a profile in name only, and nothing has confirmed that it describes your scanner. Treat it as unchecked: read the warnings above, put right what they name, and build again before you use it for anything.

### M-SCAN-LOADED · PROPOSED · what has just been loaded, and that nothing has been checked yet — the scanner window's log

*New for beta 8, item B8-16. Loading a scan under the wrong Target type produced
an **empty log**, a live Run button and a 288-cell mesh drawn confidently across
a 24-patch photograph. Pressing Run does fire two automatic guards before
colprof — the reference-agreement test at −0.22 and the placement check at
0.00 % — so this is **not** a silent wrong profile, and it must not be reported
as one. What it is: for as long as the user cares to look, the window is
authoritative about a placement that cannot be right, and it invites them
straight past it.*

*A load-time mismatch DETECTOR is not proposed, because at load time the app has
read nothing and cannot honestly know. What it can do is stop being silent: say
what was loaded, say what it is about to be read as, and say that nothing has
been checked yet. The check that can answer the question is named, because it is
the button beside it.*

*Not a window: two lines in the log the window already writes into, on every
successful load — the matching case as well as the mismatched one, because a
line that appears only when something is wrong teaches the user nothing about
what right looks like.*

> **Scan loaded**
>
> {file} — {w} × {h} pixels. It will be read as “{target}”, which has {n} patches.
> Nothing has been checked yet. Place the grid over the patch area, then press Check alignment — that reads the scan and says whether the grid is really on the patches.

### M-SCAN-ALIGN-NOT-SEATED · PROPOSED · Auto align found the chart and the grid does not sit on the patches — Tools ▸ Build profile with scanner or camera

*New for 4.1.5, beta 8, item B8-02. The seventh Auto align refusal, and the
first one about GEOMETRY rather than about colour. Every other check in
`workflow/scan_auto_align.py` scores the placement against the chart's known
colours, and the quad Auto align is able to return is always a rotated
rectangle — `corners_from_candidate` builds it from a rotation and two scales,
so its two edge vectors are orthogonal by construction. A sheet photographed
even slightly off square is a keystone, which a rectangle cannot be, so the grid
comes out systematically wrong: right in the middle of the sheet and worst at
one corner. **A rank correlation cannot see that**, because the patches keep
their brightness ORDER while they slide onto their neighbours.*

*Measured with a pinhole camera at three sheet-widths and a compound pitch+yaw
tilt — what a hand holding a phone actually does. At **8 degrees**, 20 of 23
bundled targets accepted the answer and **ten of them were more than half a
patch pitch out**, which is the point at which a sample box reads the
neighbouring patch; the window printed “agrees … to 0.98” beside its own
sentence “anything below 0.80 is refused”. Knut's LaserSoft target was 0.921
pitch out at 0.98; LaserSoftDCPro 0.426 out at **1.00**. Costed end to end on
Knut's real Wolf Faust scan at 10 degrees: 33 of 288 patches move by more than
3 ΔE00, six by more than 10, and the resulting scanner profile differs from the
correct one by a median **2.23 ΔE00** with 320 of 343 device grid points over
1 ΔE00, against a harness floor of 0.78.*

*The gate is `seating_drift`: for every patch box, the offset that would seat it
on flat colour, shrunk by how much moving it actually helped, averaged over a
4×4 grid of chart regions, in patch pitches. Noise cancels inside a region; a
keystone does not.*

*Measured over three populations: 600 camera views of 25 targets; 216 CROSSED
views carrying a paper bow, a lens distortion and a tilt at once; and the
38-case challenge set at its own ground truth plus Knut's two real scans and
nine legitimate degradations of his sheet. **328 correct placements read 0.0631
or less** — the single worst a 24-patch half Passport at 15 degrees, with Knut's
own scan plus heavy noise next at 0.0583 and his untouched scans at 0.0175 and
0.0139 — while **106 placements more than half a pitch out read 0.0989 or
more**. Every value from **0.065 to 0.095** gives the same two counts: **0 false
refusals in 328, and 106 of 106 wrong answers refused**. The limit is **0.075**,
1.19× above the worst correct placement and 1.32× below the worst wrong one.*

*The false-refusal cost is stated rather than implied: this refuses nothing that
Auto align places correctly today, and it refuses the barrel- and
pincushion-distorted photographs where **no** four corners can seat the patches
(Agent G's lens measurements: an ordinary phone lens already costs 6 patches
over 3 ΔE at the best possible quad, a pincushion 39). Those were being accepted
at rho 0.98 and are now refused, which is the right answer for them.*

*What it does NOT catch, said plainly: about half of the placements between a
quarter and half a patch pitch out — where the sample box overhangs its patch
border but does not reach the neighbouring patch. 126 of 252 of those are
refused. Nearly all the survivors are lens-distorted photographs at low tilt.*

*A refusal, not a warning, and this is the one place in the scanner window where
that is the right shape: the harm is a confidently wrong profile, the user loses
nothing (their own corners are untouched), and dragging four corners by hand
always works.*

> **Auto align left your corners exactly where they are**
>
> It found the chart, but the patches in the picture do not sit where that grid would put them: towards one edge of the sheet the grid would read part of the neighbouring patch, and a profile built from that is wrong without looking wrong.

This is what a photograph taken at a slight angle does — the sheet further from the camera comes out smaller, and no rectangle fits both ends of it. A flatbed scan does not have the problem at all.

Scan the sheet, or photograph it square-on with the camera above the middle of it — or drag the four corners onto the chart yourself, which always works and is what the grid is for.

### M-SCAN-ALIGN-PLACED-UNCHECKED · PROPOSED · Auto align placed the grid and its reading does not agree with the chart — Tools ▸ Build profile with scanner or camera

*New for #182, 2026-09-11. Knut was asked what Auto align should do when it
cannot place the grid well enough to trust: leave the corners alone and say so,
or place its best attempt and tell the user to check it. He ruled:* **"place its
best attempt and tell user to check it."**

*That changes what two of the nine endings DO, and therefore what they say. Both
`below-floor` (the placement does not agree with the chart's own reference) and
`not-seated` (the picture says the patches are not where the placement puts
them) are reached only AFTER a candidate exists, so both had a real answer to
show and threw it away. The other seven endings are unchanged and keep their
refusals, because in every one of them there is nothing to place: the search
found nothing, or the chart file records no patch positions, or the only
"candidate" is the user's own corners put back where they already are.*

*Nothing about the CHECKS changed. `border_agreement`, `seating_drift` and the
reference agreement all still run, on the same corners, and still say the same
thing; `PlacementResult.trusted` is the flag that carries their verdict, and it
is the only thing in the app that may be read as "this grid is right". What
changed is that the user now gets to see the answer they are being asked to
correct, and that the one-press undo puts their own corners back.*

*This is the `below-floor` wording. The headline is shared with
M-SCAN-ALIGN-PLACED-NOT-SEATED because from the user's side there is one state:
the grid moved, and nobody is vouching for it. It deliberately avoids the word
the approved M-SCAN-ALIGN-DONE opens with, so the two cannot be told apart at a
glance by their first word alone.*

> **Auto align placed the grid and could not confirm it**
>
> ChromIQ found the chart and has put the grid on its best reading of it, so you can see what it found. What the grid reads there does not agree with this chart's own reference closely enough to rely on, which usually means the reference file belongs to a different target, or the scan is of a different chart.
>
> Check it before you build anything. Look at the file in the “{ref_row}” row above, press “Check alignment” below to read the scan and see which patches it is really taking, and drag any corner by hand. “Undo auto align” puts your own corners back.

### M-SCAN-ALIGN-PLACED-NOT-SEATED · PROPOSED · Auto align placed the grid and the picture says the patches are elsewhere — Tools ▸ Build profile with scanner or camera

*New for #182, 2026-09-11, from the same ruling. The `not-seated` half: the
seating check refused the candidate, and under the old behaviour that discarded
it. The evidence behind the check itself is unchanged and is set out under
M-SCAN-ALIGN-NOT-SEATED above, which stays in the catalogue for the case where
the SEARCH ended on that reason with no candidate to place.*

*The paragraph naming the camera angle is kept from that message, because it is
the single most likely cause and it tells the user what to do differently next
time rather than only what is wrong now.*

> **Auto align placed the grid and could not confirm it**
>
> ChromIQ worked out where the grid would have to go and has put it there, then looked at the picture once more to check it, and the patches are not where that placement puts them. Towards one edge of the sheet the grid reads part of the neighbouring patch, and a profile built from that is wrong without looking wrong.
>
> This is what a photograph taken at a slight angle does: the end of the sheet further from the camera comes out smaller, so no single shape fits both ends of it. A flatbed scan does not have the problem at all.
>
> Check it before you build anything. Press “Check alignment” below, and drag the corners that are off onto the patches by hand. “Undo auto align” puts your own corners back.

### M-SCAN-DIAGNOSTIC · PROPOSED · a scanin diagnostic image offered as a scan — the scanner window's log

*New for beta 8, item B8-15. Knut did this in his own beta.7 session
(`chromiq.log`, 15:30): he picked `diagnosticReadLSTarget01.tif` — an output of
`scanin -dipn`, a picture OF a read — as the scan. The app took it without a
word, and the alignment check then reported a misplacement that was not real
("sample boxes sit on patch edges, worst 73.80 %") about a read that had been
fine. ChromIQ writes one of these into `cache/` beside every scan it reads, so
it is an easy file to pick again by mistake.*

*Recognised from the pixels, not from the file name: his was written by his own
`scanin` command and is called nothing ChromIQ would write. Measured at full
resolution over three diagnostics and twenty real scans and photographs
(`workflow/scan_diagnostic_image.py` carries the table): a diagnostic is 60–66 %
exactly neutral and 0.7–3.4 % Argyll's annotation colour, while no real scan in
the set had a single pixel of that colour. Both signatures must hold, because
the neutral fraction alone reached 45 % on a JPEG at quality 12.*

*A WARNING, not a refusal. The harm is a false verdict, not a bad profile, and a
detector measured on three files should not be able to lock a user out of their
own scan. Written into the log at load time, so the user meets it before the
false verdict rather than after it.*

> **This looks like a diagnostic image, not a scan**
>
> ChromIQ writes one of these after every read: your scan turned grey, with the colour painted back only where ArgyllCMS sampled it, and the patch names drawn on top. It is a picture of a read, not something that can be read again.
>
> The grid cannot line up on it, and the alignment check will report a misplacement that is not real. Load the original scan of your target instead — diagnostic images live in the “cache” folder beside it and are safe to delete.

### M-SCAN-CONVERTED · PROPOSED · a photograph converted so ArgyllCMS can read it — the scanner window's log

*New for beta 8, agent L. The window's own subtitle offers “a scan **or photo**
of the target”, and the file picker's “All files” entry lets a camera JPEG be
chosen. Qt decodes it happily into the preview, the marquee aligns on it, the
Run button goes live — and `scanin` then exits with* `Not a TIFF or MDI file,
bad magic number` *at the very end of the job, worded as an Argyll file error.
Measured here on a real camera JPEG.*

*ChromIQ now writes a TIFF copy and reads that. Said out loud rather than
silently, because a file the app has substituted for the one the user chose is
not the user's file any more, and the two questions they will have — “was
anything done to my colours?” and “was my original changed?” — are both answered
here. A file that is already a TIFF is not copied, not re-encoded and not
opened: that is the flatbed path and it stays exactly what it was.*

> **This photograph was converted for reading**
>
> ArgyllCMS reads TIFF images only, and {file} is not one. ChromIQ made a TIFF copy of it and will read that; your own file is not changed. The copy holds the same pixels — nothing has been sharpened, resized or colour-managed.

### WITHDRAWN on 2026-09-04, never approved — the separate “Fit to the patches” button's own four messages

*B8-42 merged “Auto align” and “Fit to the patches” into one button, on the
measurement that neither was useless and neither was a subset of the other: over
290 starting placements there are 139 cases only the search recovers and 30 only
the reshaping does, and one button that searches, then reshapes, then checks
lands 244 of the 290 on the patches where pressing both landed 226. With the
second button gone, four of the messages written for it describe states the user
can no longer reach, and every ending the merged button HAS is told in Auto
align's own approved words:*

* **M-SCAN-FIT-DONE** — “The grid was fitted to the patches”. There is one
  success now, M-SCAN-ALIGN-DONE, and it is approved. This one also quoted a
  number that was true only of the reshaping step: on screen, on Knut's own Wolf
  Faust scan, it said “moved your corners by up to 0.54 of a patch” while the
  grid was 1.54 patches out.
* **M-SCAN-FIT-NO-BETTER** — “The grid was left exactly where you put it”.
  The approved M-SCAN-ALIGN-NO-BETTER says the same thing, and now covers it.
* **M-SCAN-FIT-NOTHING** — the button pressed before there was anything to look
  at. The approved M-SCAN-ALIGN-NO-INPUT is that state.
* **M-SCAN-FIT-NOT-SEATED** — the reshaped answer failing the picture check.
  There is one picture check now, at the end, on whatever placement is about to
  be applied, and M-SCAN-ALIGN-NOT-SEATED is its refusal.

### M-SCAN-ALIGN-NO-BETTER · PROPOSED (revised wording) · nothing could be improved on the corners the user placed — Tools ▸ Build profile with scanner or camera

*The headline was approved by Basti on 2026-09-03 and is unchanged. The BODY is
rewritten for B8-42 and is back in the queue for that reason.*

*What changed under it: this used to be the recogniser's own ending, reached
when its answer did not beat the placement on screen by a margin. The merged
placement button reaches it only when BOTH halves of the operation have
declined — the search found nothing better, and the reshaping then found
nothing worth moving the corners for — so a body that describes only the search
would describe half of what happened.*

*The second half of the body is the part that matters, and it is new. This
ending is a statement about what was searched and is NOT a statement that the
placement is right: a grid exactly one patch out reads every patch as its
neighbour and is, to everything measured inside the sample boxes, identical to
the right answer. The wording therefore says what happened, refuses the claim it
cannot make, and names the one check in this window that can tell the two apart
— which the approved version did not do.*

> **Auto align left your corners exactly where they are**
>
> ChromIQ searched the picture for the chart, and then looked around the four corners you placed for a better place to put the grid. Neither found one worth moving them for — what you have is already the closest match it can see.
> That is not the same as saying the grid is on the right patches: a grid a whole patch out reads every patch as its neighbour and looks just as even. Press “Check alignment” below — that reads the scan and can tell the difference.

### M-SCAN-ALIGN-NOT-FOUND-HEX · PROPOSED · Auto align cannot find a honeycomb chart, and the advice it gave could not help — the scanner window's log

*New for 4.2.4, 2026-09-11. Knut asked whether Auto align works on a hexagonal
chart. It does not, it never did, and that is not what was wrong with it.*

*Measured on screen on his own CR30 honeycomb, against a rectangular chart of
the same 648 colours built by the same engine so that every number has a
control beside it. The honeycomb: the corners move **0.0 px**, `is_placed()`
stays False, and the window says so. The rectangle, same drive: the corners land
**0.6 px** from the true block corners. Repeated from a deliberately rough hand
placement 166 px out, the honeycomb gives the same answer and again moves
nothing. So the worst case a placement button has — a silent move that leaves a
careful placement somewhere wrong — does not happen here, and the user is told.*

*Asked stage by stage, `place_grid` is search, then refine, then check. Only the
SEARCH declines: it returns "not recognised" with **zero** candidates from every
starting placement, because it borrows scanin's own recogniser and that hunts
the straight horizontal patch edges a grid of rectangles has. A hexagon has
none. The two stages after it are shape-agnostic in practice as well as in
principle: on the same honeycomb the refine step moves a rough placement onto
the patches and the check step separates a right placement from a wrong one by
**0.969 against 0.514**, with the floor at 0.80.*

*What was wrong is the sentence. The generic "not recognised" wording sends the
user to drag the four corners roughly around the chart and press Auto align
again, which narrows the search to inside them — and a narrower search of a
honeycomb finds nothing either, so the instruction cannot work however carefully
it is followed. Nothing about the behaviour changes with this message: the same
ending, the same refusal, the same untouched corners, and an instruction the
user can act on. Whether the search itself should be replaced for honeycombs is
a separate question, sized and costed but not decided.*

> **Auto align left your corners exactly where they are**
>
> Auto align cannot find a hexagonal chart. The search looks for the straight edges of a grid of rectangles, and a honeycomb has none, so pressing the button again will not help however the corners are placed. Drag the four corners onto the chart yourself: put each one on the outermost patch of its corner. Everything else in this window works normally on a honeycomb, including “Check alignment”, which will tell you whether what you placed is reading the right patches.

### M-SCAN-FIT-TOO-FAR · PROPOSED · nothing was found, and the corners cannot be improved from where they are — the scanner window's log

*Beta 8. Written for agent L's separate “Fit to the patches” button and REWRITTEN
for the merged one (B8-42): from beta 8 the scanner window has ONE placement
button, which searches the picture for the chart, reshapes what it finds — or,
when nothing is found, the four corners the user placed — onto the patches, and
checks the result before anything moves. This is the ending where the search had
no diagnosis of its own and the reshaping then found its best placement further
away than it is allowed to move. Measured over 290 starting placements, 2 end
here.*

*The refusal carries the safety rule, so it says what the rule is: past three
quarters of a patch pitch the “same patch, better centred” reading of the answer
stops being the only one, and the wrong reading looks exactly as convincing.
Measured: from a placement 0.35 of a patch out on a sheet bowed 5.5 % and tilted
15 degrees the reshaping wants 0.85 of a pitch, and is refused; the user moves
the corners closer and it lands.*

*The arithmetic in the first version was wrong twice over — it said “more than
half a patch” of a limit that is three quarters, and “half a patch further and
the grid would be reading the neighbouring patch” of a distance that is a
quarter. The headline is now the one every other refusal from this button
carries, because after a refusal the first thing the user needs to know is that
they have lost nothing.*

> **Auto align left your corners exactly where they are**
>
> ChromIQ looked around the four corners you placed for a better place to put the grid, and the best one it found is further than three quarters of a patch away from them. That is as far as it will move your corners by itself: one whole patch and the grid would be reading the neighbouring squares, which looks just as convincing and is completely wrong.
> Drag the four corners onto the chart’s patch area, as close to the real patches as you can get them, and press Auto align again.

### M-SCAN-SHOT-EMPTY · PROPOSED · an averaging slot left empty — the scanner window's log

*New for beta 8, item B8-32 (regression-sweep finding F-7). Press
**＋ Add another scan to average** and stop there. The shot bar reads
"Scan 1 / Scan 2", `_page_ready` asks only `any(s["path"] …)` so the Run button
stays live, and the build runs **one** `scanin`, no averaging step, and ends
`[OK] Scanner profile saved` exactly as if one scan had been asked for. Driven
end to end in the real window (sweep check J32): two slots, one file, one
scanin call, and nothing said on screen or in the log.*

*A sentence, not a refusal. What happens is a legitimate build from fewer scans
— not a wrong profile — and this window's rule for that case is already set
(B8-15: warn, never lock the user out of their own file). A Run button that
greys out with no reason attached would be a new silence rather than the end of
one.*

*One message, not a singular and a plural: every count in it is a bare number in
a clause that does not inflect around it.*

> **An empty scan slot was skipped**
>
> This page has {slots} scan slots, and a file has been picked for {filled} of them. An empty slot is not read and nothing is averaged with it, so this build uses only the scans that are there.
> If you meant to average repeated scans of this page, pick a file for each empty slot and build again. If a slot was added by mistake, “Remove this scan” takes it away.

### M-SCAN-TARGET-CHANGED · PROPOSED · the scan a target-type change throws away — the scanner window's log

*New for beta 8, item B8-32 (regression-sweep finding F-9). Load a scan, place
the grid, change **Target type**: the scan, its four corners and every other
shot on that page are dropped (`_set_std_targets` → `_reset_shots`), the preview
goes empty, and the log — cleared in the same block, which is B8-16's fix — said
nothing about any of it.*

*The discard is correct and is not being changed. A different target has a
different grid, so a placement made on the old one is meaningless on the new
one, and a demo scan belongs to the target that generated it. What was missing
was the sentence saying it happened, and where to start again.*

> **Target type changed — the loaded scan was cleared**
>
> A scan is read through the target’s own recognition file, and a different target has a different grid, so a placement made on the old one would not mean anything on this one. The scan that was loaded, its four corners and any further scans on this page have been dropped.
> Nothing on disk was touched. Pick the scan again — or press “Try with a demo scan” — for the target now selected.

### WITHDRAWN 2026-09-18 — the update-or-create question (B8-375, B8-384)

*Proposed on 2026-09-18 from Knut's own specification of that morning, which
said that on changing a setting "it is checked if this report type and judged
against combination already exists. If it exists the user will be asked if he
wants to update the existing report (overwrite) or create a new report." Two
readings of it were written out here rather than chosen, and the wording went to
review before anything was built.*

*He answered the same day and the question is not wanted:*

> *"It is better that existing reports are not overwritten. A user could instead
> select and delete old reports they do not want."*

*So **Generate report always writes a new report and nothing is ever
overwritten**, and the user prunes the list with "Delete Selected Report", which
moves the files into an `old/` folder and destroys nothing (M-REPORT-DELETE
above). The question is withdrawn rather than left waiting: it was never given an
`M-` identifier and nothing in the code refers to it. What his defect objected to
was that ONE press of Generate wrote TWO files and put two lines in the list; one
press now writes one document and one line, which is the behaviour he asked for.*

### Frame titles awaiting a ruling — Create Chart ▸ Manual ▸ Expert (B8-21 §4)

**Confirmed by:** *nobody yet.* Proposed 2026-09-04 by AGENT-R. Not approved,
and Basti rules on it.

*Deliberately NOT given an `M-` identifier. §M is a catalogue of MESSAGES —
each one a window or a log line with a headline and a body, rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading in this document to exist there. A group-box title
is not a message and must not be given a fake one to satisfy a parser. It is
recorded here because it is new user-facing wording and this is where new
user-facing wording is proposed and ruled on.*

The frame **"Strip && row labels"** used to explain which of its controls
reaches which set of labels in a paragraph. Basti, 2026-09-03: *"keep the first
note, drop the second, and rule on sub-frames… the paragraph is the option I'd
argue against — it's correct, and correct is not the same as clear."* So the
frame is split in two along the line the ink drew, and the two titles ARE the
explanation:

| proposed title | what it holds | German |
|---|---|---|
| **Strip letters and row numbers** | Font, Size, Bold — measured at 11 086 to 126 162 pixels of row-label ink each, and Font and Size re-lay the page | Streifenbuchstaben und Zeilennummern |
| **Strip letters only** | Underline, line thickness, line distance, rotation, Label offset — 0 row-label pixels, every time | Nur Streifenbuchstaben |

*Written for somebody who has never met the words "indicator" or "band": they
name what the reader can see on the printed sheet — the letters across the top
and the numbers down the left — and the second says "only", which is the whole
point of the split. Italic is in neither title: it is greyed out because
neither bundled font has an italic face, and it drew nothing on either side.*

*The other eleven catalogues carry the English source until this is ruled on,
because translating a draft translates it twice. German is translated, as the
beta convention has it.*

### Button labels — Tools ▸ Build profile with scanner or camera (AGENT-S) — Confirmed behaviour

**Confirmed by:** Basti, 2026-09-04 — *"it is ok"*, put to him as the label
and its tooltip together and approved as proposed. Drafted the same day by
AGENT-S.

*The eleven non-German catalogues still carry the English source, and that is
now the BETA TRANSLATION CONVENTION doing it, not a pending ruling: translation
happens before a final, not during a beta, so that nothing is translated twice.
Do not "finish" them here — the language sweep before the final is where they
land.*

*Deliberately NOT given an `M-` identifier, for the reason the section above
gives: §M is a catalogue of MESSAGES, each one rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading here to exist there. A button label is not a
message and must not be given a fake identifier to satisfy a parser. It is
recorded here because it is new user-facing wording and this is where new
user-facing wording is proposed and ruled on.*

Basti, 2026-09-04, looking at the running window: *"could you task an agent to
rearrange the buttons under the preview in a way it makes sense and takes up
less space?"* The block was four rows for six buttons, and the last row held
one button because its label was a sentence.

| proposed label | replaces | German |
|---|---|---|
| **⤢ Pop out** | ⤢ Pop out for a bigger view | ⤢ Ablösen |

*Measured at these buttons' own metrics: the old label is the longest in the
window — 202 px in Italian, 191 in German, against 78 for this one — and it is
what forced a fourth row. What the four dropped words said is now said twice
over: by the new tooltip below, and by the hint line printed under the block,
which already ends "Rotate handles a sideways scan; Pop out gives a bigger
view".*

| proposed tooltip (the button has none today) |
|---|
| Open the preview in its own resizable window, much bigger, so the corners are easier to place. The placement, the zoom and the rotation all come back with it when you dock it again. |

*German: "Öffnet die Vorschau in einem eigenen, frei skalierbaren Fenster – viel
größer, damit sich die Ecken leichter setzen lassen. Platzierung, Zoom und
Drehung kommen beim Andocken unverändert zurück."*

*The other eleven catalogues carry the English source until this is ruled on,
because translating a draft translates it twice. German is translated, as the
beta convention has it. "⤢ Dock back", the label the button carries while the
preview is popped out, is unchanged.*

### Profile type help text, Tools ▸ Build profile with scanner or camera (AGENT-AD, AGENT-AF) — Confirmed behaviour

**Confirmed by:** Basti, 2026-09-04 — *"i approve it"*, given after he read the
text in full and asked whether it was "friendly, extensive, easy to understand".
Approved as written: the help itself, the "(recommended cLUT)" marker in scanner
mode, and the patch-count hint. Drafted 2026-09-04 by AGENT-AD, revised the same
day by AGENT-AF when Basti ruled that the measurement must be reflected in the
app rather than only in a reply to Knut. Knut asked for it: *"Maybe the help text for the profile type should give
recommendations for when to use the LUT types, such as when one has large
targets with many patches… or whatever…."*

#### ⏳ Awaiting confirmation — three paragraphs of the scanner-side ⓘ, 2026-09-06

**Confirmed by:** *nobody yet.*

Basti approved the words above on 2026-09-04. Three paragraphs of the
scanner-side text have changed since, and neither change has been put to him,
so they are flagged here rather than left inside a "Confirmed" heading as if
they had been:

1. **The Lab-table bullet was already out of date in this document before
   today**, and that is a pre-existing divergence, not something this change
   introduced. B8-75 moved the white-point default to "Scale white to a perfect
   white surface (-u -R)" on 2026-09-05, which moves a Lab cLUT's ceiling from
   about 94 % reflectance to about 114 %, and the bullet was rewritten in the
   code to say so. This document kept the older wording, which still ends
   *"set Advanced… ▸ White point handling to 'Auto-scale to avoid clipping
   (-u)', which lifts the ceiling"* — advice the new default has already taken.
   The paragraph above is now the code's, so the two agree again.
2. **"the default here" is gone from the Shaper + matrix bullet, and "on the
   default there" from the Lab one.** Knut asked in beta 10 for the profile
   type, the quality and the white point to be chosen from the patch count, and
   for the white-point dropdown to stop calling one entry the default (it is
   wrong for the two matrix types, which this window's own help says). With
   both built, "the default" names nothing on either control, so the two
   sentences that leaned on it had to say something else.
3. **The third paragraph now says the window acts on the patch count**, because
   it does. That is the change B8-19 considered and deliberately did not make;
   Knut asked for it and Basti authorised it, and the guard that keeps it safe
   is that it never touches a bucket whose settings somebody saved. B8-78 has
   the whole of it.

4. **The printer side lost two of its four profile types, and this
   document said they worked.** It read *"All four choices build a working
   profile"* for the printer mode and listed Shaper + matrix and Matrix only in
   the dropdown table, and ArgyllCMS makes that impossible: `colprof.c:1244`
   answers any non-cLUT algorithm for a `DEVICE_CLASS "OUTPUT"` measurement
   with *"Output profile can only be a cLUT algorithm"* and writes nothing.
   MEASURED on Knut's own `Knut-Scanner-printer.ti3`, the printer-mode
   measurement this very window produced: `-as` and `-am` exit 1 with no
   profile. So this is a fault in the DOCUMENT as much as in the code, and by
   CLAUDE.md's rule that is Knut's and Basti's call rather than ours: the
   wording below is what the app now shows, and it is flagged here for a ruling
   rather than presented as settled. B8-93 and B8-94 carry the whole
   measurement. The same note applies to the Quality paragraph on BOTH sides:
   it said `-q` "applies only to the two cLUT types and is greyed out for the
   other two", and ArgyllCMS's own `colprof.html` says the opposite ("For
   matrix profiles it sets the per channel curve detail level and fitting
   'effort'"), which is measured: `-q l/m/h/u` gives four different profiles
   for every algorithm tested. The greyed value was being sent regardless.
   B8-95.

The patch-count *hint* Basti approved is still there and still changes nothing.
It now fires only where ChromIQ may not choose for the user: a bucket with
saved settings, or one edited by hand this session.

**The wording below is what the app now shows.** It is written into
`ui/dialogs/scanner_colprof.py` (`ptype_help`, `ptype_advice`) and reproduced
here verbatim so a ruling can be made on the exact words. If a word changes
there it changes here in the same commit —
`tests/test_the_profile_type_says_which_clut.py` pins the claims and
`tests/test_i18n.py` pins the catalogues.

*Deliberately NOT given an `M-` identifier, for the reason the sections above
give: §M is a catalogue of MESSAGES rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading here to exist there. A tooltip is not a message and
must not be given a fake identifier to satisfy a parser.*

**Every recommendation is a measurement, not colour-management lore.** The
numbers come from cross-validated builds on two REAL scans — a Wolf Faust IT8
(288 patches) and a LaserSoft DCPro (864) — fitted on part of the patch set and
scored, in CIEDE2000, only on patches the fit never saw. The evidence is in
`beta 8/24-scanner-profile-default/`, the harness is `cv_profile_type.py`, and
the register entries are B8-19 and B8-56.

**It differs by MODE, because the advice does.** The same row builds a scanner /
camera INPUT profile and, with "Profile my printer from this scan" ticked, a
printer OUTPUT profile — and the window already marks a different "(default)"
for each. The XYZ recommendation is about capturing something lighter than the
chart's white; ArgyllCMS's `colprof.html` makes that claim of INPUT devices
specifically, AGENT-AD measured input profiles only, and nothing a printer
prints is lighter than the paper it prints on. So it is made on the scanner side
and NOT on the printer side. One text covering both would have to contradict one
of the two "(default)" markers.

#### 1 · The ⓘ beside "Profile type (-a):" — scanner or camera mode

> How the scanner or camera profile models colour.
>
> Profile type (-a) — the shape of the maths inside the profile, and how it describes what your device does with colour. All four choices build a working profile. What separates them is how many measured patches they need before they are any good, and how they behave on colours your target did not contain.
>
> That makes the size of your target the first thing to look at, and you do not have to count anything or set anything up. The patch count is printed beside each target's name in the list above, and again in the green “✓ … patches” line once a target or a chart is loaded; and the moment ChromIQ knows that number it sets this control, the Quality below it and Advanced… ▸ White point handling to suit it. Below about a hundred patches that is “Shaper + matrix” at Medium; at a hundred or more it is the XYZ look-up table at High. Change any of the three and ChromIQ leaves all three alone from then on.
>
> • Shaper + matrix, and what ChromIQ chooses for a target under about a hundred patches: a small, sturdy profile made of one gentle tone curve for each of red, green and blue plus a 3×3 matrix, which is a fixed recipe for mixing those three into a finished colour. It is a formula rather than a stored table, so it needs very little data to work well, and it carries on sensibly beyond the lightest and darkest patch your target contains. Take it for a ColorChecker (24 patches), a SpyderChecker (48) or a QPcard (49), and whenever a scan is noisy or you would rather not think about it. On real scanned targets it was the most accurate of the four at 24 and at 48 patches.
>
> • cLUT — XYZ table — “cLUT” means a look-up table. Instead of a formula, the profile stores your measurements and interpolates between them, so it can follow a device that does not behave like tidy maths. That freedom has to be paid for in patches: with too few of them there is nothing much to interpolate between, and the table will happily fit the noise in a scan rather than the colour. Take it when your target has roughly two hundred patches or more — a full IT8 has 288, a three-page ISO 12641-2 set has 864 — and the scan is clean and correctly exposed. At that size it measured about a third more accurate than Shaper + matrix on a real IT8 scan. “XYZ” is simply the internal form the table keeps colour in, and it is the one to use here — the next entry says why.
>
> • The Lab look-up table, the other of the two cLUT entries: the same kind of table, keeping colour in a different internal form. On the colours your target actually contains, the two tables measured close together, with neither of them consistently ahead of the other. The difference is at the top end: a Lab table has a hard ceiling and stops dead at it, flattening every tone above onto one value, where Shaper + matrix and the XYZ table both carry on. How high that ceiling sits is decided by Advanced… ▸ White point handling. On “Scale white to a perfect white surface” it sits at about 114 % reflectance, brighter than a perfect white surface, so nothing you can put on the glass will reach it. On “Map chart white to white” the ceiling drops to about 94 % reflectance, which ordinary bright paper does reach, and everything above it arrives flattened. (Both figures measured on a real IT8 scan, so your own will differ a little.) The XYZ table has no ceiling at all under any of those settings, which is why it is the safer of the two and why it costs nothing to take.
>
> • Matrix only — the 3×3 mix and nothing else, with no tone curves in front of it. It suits a device that is already perfectly linear, such as a camera shooting RAW. On an ordinary scanner it measured several times less accurate than any of the other three at every size tested, so it is not the one to reach for here.
>
> Right around a hundred patches the first three land within a whisker of one another and the choice barely matters; it is above and below that the difference shows. And whichever you pick, changing the paper or the target you scan moves the result a great deal further than the profile type does.
>
> ArgyllCMS has two more variants that this list leaves out, and it is worth knowing they exist. They fit one tone curve shared by all three colour channels instead of a separate curve for each. That is not an accuracy choice: their stated purpose is compatibility with applications that refuse a profile carrying a different curve per channel. If an application will not accept a profile this window built, that is the first thing to mention when you report it.
>
> Quality (-q): how much detail and fitting effort goes into the profile. For the two look-up-table types it sets the table's grid resolution; for the shaper and matrix types it sets how finely the tone curves are fitted. Higher is finer but slower, and needs better data to be worth it. It applies to every profile type. Medium is a good default, Low is a quick test, and High and Ultra are for large, clean charts.
>
> If you tick “Profile my printer from this scan”, this same control builds the printer profile instead — a different kind of device, with different advice. The type then defaults to “cLUT — Lab table”; open this ⓘ again with the box ticked and it will explain why. Either way you won't find a working space (like sRGB) or a rendering intent here; a rendering intent is something you choose when you print, not when you build a profile from measurements.
>
> None of the recommendations above is received wisdom. Profiles were built from part of two real scanned targets and then scored only on the patches the fit had never seen, which is the only way the numbers mean anything — a profile marked against its own measurements flatters a look-up table badly.

*German:*

> Wie das Scanner- oder Kameraprofil Farbe modelliert.
>
> Profiltyp (-a) – die Form der Mathematik im Inneren des Profils, also wie es beschreibt, was dein Gerät mit Farbe macht. Alle vier Möglichkeiten erzeugen ein funktionierendes Profil. Sie unterscheiden sich darin, wie viele gemessene Felder sie brauchen, bevor sie wirklich gut sind, und wie sie sich bei Farben verhalten, die dein Target gar nicht enthielt.
>
> Damit ist die Größe deines Targets das Erste, worauf du schauen solltest, und zählen oder einstellen musst du nichts: Die Feldanzahl steht in der Liste oben neben dem Namen jedes Targets und noch einmal in der grünen Bereitschaftszeile mit dem Häkchen, sobald ein Target oder eine Testkarte geladen ist. Und sobald ChromIQ diese Zahl kennt, setzt es dieses Bedienelement, die Qualität darunter und Erweitert… ▸ Weißpunkt-Behandlung passend dazu. Unter etwa hundert Feldern ist das „Shaper + Matrix“ mit Mittel, ab hundert die XYZ-Nachschlagetabelle mit Hoch. Änderst du eine der drei, lässt ChromIQ von da an alle drei in Ruhe.
>
> • Shaper + Matrix, und das, was ChromIQ für ein Target unter etwa hundert Feldern wählt: ein kleines, robustes Profil aus je einer sanften Tonwertkurve für Rot, Grün und Blau und einer 3×3-Matrix, also einem festen Rezept, das diese drei zu einer fertigen Farbe mischt. Es ist eine Formel und keine gespeicherte Tabelle, braucht deshalb sehr wenig Daten, um gut zu arbeiten, und verhält sich auch jenseits des hellsten und des dunkelsten Feldes deines Targets noch vernünftig. Nimm es für einen ColorChecker (24 Felder), einen SpyderChecker (48) oder eine QPcard (49) und immer dann, wenn ein Scan verrauscht ist oder du dir darüber lieber keine Gedanken machen möchtest. Bei echten gescannten Targets war es bei 24 und bei 48 Feldern das genaueste der vier.
>
> • cLUT — XYZ-Tabelle – „cLUT“ heißt Nachschlagetabelle. Statt einer Formel speichert das Profil deine Messwerte und interpoliert dazwischen, kann also einem Gerät folgen, das sich nicht wie saubere Mathematik verhält. Diese Freiheit muss in Feldern bezahlt werden: Sind es zu wenige, gibt es kaum etwas, wozwischen sich interpolieren ließe, und die Tabelle bildet bereitwillig das Rauschen im Scan ab statt der Farbe. Nimm sie, wenn dein Target ungefähr zweihundert Felder oder mehr hat – ein volles IT8 hat 288, ein dreiseitiges ISO-12641-2-Set 864 – und der Scan sauber und richtig belichtet ist. In dieser Größe war sie bei einem echten IT8-Scan rund ein Drittel genauer als Shaper + Matrix. „XYZ“ ist einfach die interne Form, in der die Tabelle Farbe hält, und sie ist hier die richtige – warum, sagt der nächste Punkt.
>
> • Die Lab-Nachschlagetabelle, der andere der beiden cLUT-Einträge: dieselbe Art Tabelle, die Farbe nur in einer anderen internen Form hält. Auf den Farben, die dein Target tatsächlich enthält, lagen die beiden Tabellen dicht beieinander, keine von beiden durchgehend vorn. Der Unterschied liegt am oberen Ende: Eine Lab-Tabelle hat eine harte Obergrenze und bleibt dort stehen; jeder Ton darüber wird auf einen einzigen Wert eingeebnet, während Shaper + Matrix und die XYZ-Tabelle beide weiterlaufen. Wie hoch diese Grenze liegt, entscheidet Erweitert… ▸ Weißpunkt-Behandlung. Mit „Weiß auf eine perfekt weiße Fläche skalieren“ liegt sie bei rund 114 % Reflexionsgrad, heller als eine perfekt weiße Fläche, nichts, was du auf das Glas legen kannst, erreicht sie also. Mit „Chart-Weiß auf Weiß abbilden“ fällt die Grenze auf etwa 94 % Reflexionsgrad, was gewöhnliches helles Papier durchaus erreicht, und alles darüber kommt eingeebnet an. (Beide Werte an einem echten IT8-Scan gemessen, deine eigenen werden also etwas abweichen.) Die XYZ-Tabelle hat unter keiner dieser Einstellungen eine Obergrenze, und deshalb ist sie die sicherere der beiden und deshalb kostet es nichts, sie zu nehmen.
>
> • Nur Matrix – die 3×3-Mischung und sonst nichts, ohne jede Tonwertkurve davor. Sie passt zu einem Gerät, das bereits perfekt linear ist, etwa einer Kamera im RAW-Modus. Bei einem gewöhnlichen Scanner war sie in jeder getesteten Größe um ein Vielfaches ungenauer als alle drei anderen und ist hier deshalb nicht die richtige Wahl.
>
> Genau um die hundert Felder herum liegen die ersten drei so dicht beieinander, dass die Wahl kaum eine Rolle spielt; erst darüber und darunter zeigt sich der Unterschied. Und was du auch nimmst: Ein anderes Papier oder ein anderes Target zu scannen verschiebt das Ergebnis weit stärker als der Profiltyp.
>
> ArgyllCMS hat zwei weitere Varianten, die diese Liste weglässt, und es lohnt sich zu wissen, dass es sie gibt. Sie legen eine einzige Tonwertkurve für alle drei Farbkanäle an statt einer eigenen Kurve je Kanal. Das ist keine Frage der Genauigkeit: Ihr erklärter Zweck ist die Kompatibilität mit Anwendungen, die ein Profil mit unterschiedlichen Kurven je Kanal ablehnen. Wenn eine Anwendung ein hier gebautes Profil nicht annimmt, erwähne das bitte als Erstes, wenn du es meldest.
>
> Qualität (-q): wie viel Detail und Anpassungsaufwand in das Profil geht. Bei den beiden Tabellentypen legt sie die Gitterauflösung der Tabelle fest, bei den Shaper- und Matrixtypen, wie fein die Tonwertkurven angepasst werden. Höher heißt feiner, aber langsamer, und lohnt sich nur mit besseren Daten. Sie gilt für jeden Profiltyp. Mittel ist ein guter Standard, Niedrig ein schneller Test, Hoch und Ultra sind für große, saubere Charts.
>
> Wenn du „Meinen Drucker aus diesem Scan profilieren“ ankreuzt, baut genau dieses Bedienelement stattdessen das Druckerprofil – ein anderes Gerät, eine andere Empfehlung. Der Typ ist dann auf „cLUT — Lab-Tabelle“ voreingestellt; öffne dieses ⓘ mit gesetztem Haken noch einmal, dann erklärt es dir warum. So oder so findest du hier keinen Arbeitsfarbraum (etwa sRGB) und kein Rendering-Intent; ein Rendering-Intent wählst du beim Drucken, nicht beim Erstellen eines Profils aus Messwerten.
>
> Nichts von alledem ist überliefertes Halbwissen. Die Profile wurden aus einem Teil zweier echter gescannter Targets gebaut und danach nur an den Feldern bewertet, die die Anpassung nie gesehen hatte – nur so bedeuten die Zahlen überhaupt etwas: Ein Profil, das an seinen eigenen Messwerten gemessen wird, schmeichelt einer Nachschlagetabelle erheblich.

#### 2 · The same ⓘ with "Profile my printer from this scan" ticked

> How the printer profile models colour.
>
> “Profile my printer from this scan” is ticked, so this window is building a PRINTER profile: your scanner is the measuring instrument, and the chart it reads is the one you printed. That changes what to choose here, so this is not the same advice you get for a scanner or camera profile.
>
> Profile type (-a): the shape of the maths inside the profile, and how it describes what your printer does with colour. There are two here, not the four you get with the tick off, and both build a working profile.
>
> • cLUT — Lab table — the default here, and what a printer profile should normally be. “cLUT” means a look-up table: instead of reducing your printer to a formula, the profile stores your measurements and interpolates between them. It also carries something the formula types cannot — the perceptual and saturation rendering intents, which are what decide how colours your printer cannot reach are eased inwards when you print a photograph. Everything under Advanced… ▸ Gamut Mapping describes those two intents, so it has nothing to act on unless the profile is a table. “Lab” is simply the internal form the table keeps colour in; it is ArgyllCMS's own default for this job, and it is what ChromIQ's Build Profile tab builds as well.
>
> • cLUT — XYZ table — the same kind of table, keeping colour in the other internal form. It is worth knowing why this window points at the XYZ table on the scanner side and not here. A Lab table cannot describe anything lighter than the white patch of the chart it was built from, and a scanner meets paper brighter than a scanning target's white board all the time. A printer never does — nothing it prints is lighter than the paper it prints on — so that reason does not apply here, and the Lab default stands.
>
> “Shaper + matrix” and “Matrix only”, which this list offers with the tick off, are not here. That is ArgyllCMS's rule and not a ChromIQ choice: colprof refuses to build a printer profile from a formula, and refuses it before it has read a single patch. The rule is not arbitrary either. By the way the ICC format works, a matrix-based profile cannot carry a perceptual or a saturation intent at all, so it would have nothing to fall back on when a colour is out of the printer's reach.
>
> Quality (-q): how much detail and fitting effort goes into the profile. For the two look-up-table types it sets the table's grid resolution; for the shaper and matrix types it sets how finely the tone curves are fitted. Higher is finer but slower, and needs better data to be worth it. It applies to every profile type. Medium is a good default, Low is a quick test, and High and Ultra are for large, clean charts.
>
> Untick “Profile my printer from this scan” and this control goes back to building a scanner or camera profile, where the default is “Shaper + matrix” and the advice is different — open this ⓘ again and it will tell you that story instead. Either way you won't find a working space (like sRGB) or a rendering intent in this row: the working space the gamut mapping uses is under Advanced… ▸ Gamut Mapping, and a rendering intent is something you choose when you print, not when you build a profile from measurements.

*German:*

> Wie das Druckerprofil Farbe modelliert.
>
> „Meinen Drucker aus diesem Scan profilieren“ ist angehakt, dieses Fenster baut also ein DRUCKERPROFIL: Dein Scanner ist das Messgerät, und die Testkarte, die er liest, ist die, die du gedruckt hast. Das ändert, was du hier wählen solltest – es ist deshalb nicht dieselbe Empfehlung wie für ein Scanner- oder Kameraprofil.
>
> Profiltyp (-a): die Form der Mathematik im Profil und damit, wie es beschreibt, was dein Drucker mit Farbe macht. Hier gibt es zwei davon, nicht die vier, die du ohne Haken bekommst, und beide bauen ein funktionierendes Profil.
>
> • cLUT — Lab-Tabelle – hier die Voreinstellung und normalerweise das, was ein Druckerprofil sein sollte. „cLUT“ heißt Nachschlagetabelle: Statt deinen Drucker auf eine Formel zu reduzieren, speichert das Profil deine Messwerte und interpoliert dazwischen. Es trägt außerdem etwas, das die Formel-Typen nicht können – die Rendering-Intents Perzeptiv und Sättigung, die darüber entscheiden, wie Farben, die dein Drucker nicht erreicht, beim Druck eines Fotos sanft nach innen geführt werden. Alles unter Erweitert… ▸ Gamut-Mapping beschreibt genau diese beiden Intents und hat deshalb nichts, worauf es wirken könnte, wenn das Profil keine Tabelle ist. „Lab“ ist einfach die interne Form, in der die Tabelle Farbe hält; es ist die eigene Voreinstellung von ArgyllCMS für diese Aufgabe und auch das, was der Reiter „Profil erstellen“ von ChromIQ baut.
>
> • cLUT — XYZ-Tabelle – dieselbe Art Tabelle, die Farbe nur in der anderen internen Form hält. Es lohnt sich zu wissen, warum dieses Fenster auf der Scanner-Seite zur XYZ-Tabelle rät und hier nicht. Eine Lab-Tabelle kann nichts beschreiben, was heller ist als das Weißfeld der Testkarte, aus der sie gebaut wurde, und ein Scanner bekommt ständig Papier zu sehen, das heller ist als das Weiß eines Scan-Targets. Ein Drucker nie – nichts, was er druckt, ist heller als das Papier, auf das er druckt –, deshalb greift dieser Grund hier nicht und die Lab-Voreinstellung bleibt richtig.
>
> „Shaper + Matrix“ und „Nur Matrix“, die diese Liste ohne Haken anbietet, gibt es hier nicht. Das ist die Regel von ArgyllCMS und keine Entscheidung von ChromIQ: colprof weigert sich, ein Druckerprofil aus einer Formel zu bauen, und weigert sich schon, bevor es ein einziges Feld gelesen hat. Willkürlich ist die Regel auch nicht. So wie das ICC-Format funktioniert, kann ein matrixbasiertes Profil überhaupt keinen perzeptiven und keinen Sättigungs-Rendering-Intent tragen, es hätte also nichts, worauf es zurückfallen könnte, wenn eine Farbe außerhalb der Reichweite des Druckers liegt.
>
> Qualität (-q): wie viel Detail und Anpassungsaufwand in das Profil geht. Bei den beiden Tabellentypen legt sie die Gitterauflösung der Tabelle fest, bei den Shaper- und Matrixtypen, wie fein die Tonwertkurven angepasst werden. Höher heißt feiner, aber langsamer, und lohnt sich nur mit besseren Daten. Sie gilt für jeden Profiltyp. Mittel ist ein guter Standard, Niedrig ein schneller Test, Hoch und Ultra sind für große, saubere Charts.
>
> Nimm den Haken bei „Meinen Drucker aus diesem Scan profilieren“ heraus, dann baut dieses Bedienelement wieder ein Scanner- oder Kameraprofil, wo die Voreinstellung „Shaper + Matrix“ heißt und die Empfehlung eine andere ist – öffne dieses ⓘ dann noch einmal, es erzählt dir stattdessen jene Geschichte. So oder so findest du in dieser Zeile keinen Arbeitsfarbraum (etwa sRGB) und kein Rendering-Intent: Der Arbeitsfarbraum, den das Gamut-Mapping benutzt, steht unter Erweitert… ▸ Gamut-Mapping, und ein Rendering-Intent wählst du beim Drucken, nicht beim Erstellen eines Profils aus Messwerten.

#### 3 · The dropdown's second marker

The factory default already carries "(default)", and that is unchanged. A
SECOND marker names which of the two cLUTs to take if you want one — **in
scanner / camera mode only** (`PTYPE_RECOMMENDED_CLUT = {False: "x", True:
None}`). The Lab option is NOT removed, NOT disabled and NOT relabelled: Knut
likes its results, it stays a legitimate choice, and picking it still emits
`-al` unchanged. The two markers can never land on the same item, and a
recommendation identical to that mode's default is refused by a test.

| mode | what the dropdown reads |
|---|---|
| scanner / camera | Shaper + matrix **(default)** · Matrix only · cLUT — XYZ table **(recommended cLUT)** · cLUT — Lab table |
| printer | cLUT — XYZ table · cLUT — Lab table **(default)** |

| proposed marker | German |
|---|---|
| **{option} (recommended cLUT)** | {option} (empfohlene cLUT) |

#### 4 · Three live notes, carried inside that same ⓘ

Not a new control, and nothing new on the face of the window:
`TooltipButton.set_live_note`, the mechanism Basti asked for on 2026-09-04
(*"a tooltip will be enough"*), which puts a note in FRONT of the standing help
and lifts only its first line into the hover tooltip. It changes no setting, and
it disappears on its own when it stops being true.

**An automatic switch was considered and REJECTED** (B8-19): the window learns
the patch count only after a chart or target is loaded, while the type is set
before it, so an automatic default would move the user's control under them —
and the crossover is shallow. A note is the proportionate form of the same
information.

> **⏳ Superseded, and awaiting confirmation, 2026-09-06.** *Knut asked for that
> automatic switch in beta 10 and Basti authorised it, so the paragraph above
> is no longer what the app does: the profile type, the quality and the white
> point ARE chosen from the patch count, by the rule in B8-78. The objection it
> records was answered rather than overruled. The window learning the count
> late is why the rule fires on `_refresh` and not at construction; the control
> being moved under the user is why it is refused for any bucket whose settings
> were saved or hand-edited (`_may_auto_setup`); and the crossover being
> shallow is why the note below still exists, for exactly the cases where
> ChromIQ may not choose. Read this paragraph as the reasoning that shaped the
> rule, not as the behaviour. **Confirmed by:** *nobody yet.*

Each one requires a KNOWN patch count, and none of them fires in printer mode,
where nothing was measured.

| when | note |
|---|---|
| Shaper + matrix chosen, and the target has 200 patches or more | (a) |
| either cLUT chosen, and the target has fewer than 100 patches | (b) |
| cLUT — Lab chosen, and (b) did not already fire | (c) |
| anywhere between, or the count not yet known, or printer mode | *nothing* |


**(a)** — shown here with a 288-patch target:

> A note on the profile type: your target has 288 patches, which is big enough for a look-up table to be worth it.
>
> Above about a hundred patches, a cLUT measured about a third more accurate than “Shaper + matrix” on real scanned targets, and “cLUT — XYZ table” is the one to take. “Shaper + matrix” is still a perfectly good, safe profile and it will not clip your highlights — this is a suggestion, not a warning, and nothing has been changed for you.

*German:*

> Ein Hinweis zum Profiltyp: Dein Target hat 288 Felder – groß genug, dass sich eine Nachschlagetabelle lohnt.
>
> Oberhalb von etwa hundert Feldern war eine cLUT bei echten gescannten Targets rund ein Drittel genauer als „Shaper + Matrix“, und die richtige davon ist „cLUT — XYZ-Tabelle“. „Shaper + Matrix“ bleibt trotzdem ein völlig brauchbares, sicheres Profil und beschneidet deine Lichter nicht – das hier ist ein Vorschlag, keine Warnung, und es wurde nichts für dich geändert.

**(b)** — shown here with a 48-patch target:

> A note on the profile type: your target has 48 patches, which is on the small side for a look-up table.
>
> Below about a hundred patches, “Shaper + matrix” measured more accurate than either cLUT on real scanned targets — a table needs plenty of well-spread patches before it has anything to interpolate between, and with fewer it starts fitting the noise in the scan. Your choice stands; this is only a suggestion, and nothing here has been changed for you.

*German:*

> Ein Hinweis zum Profiltyp: Dein Target hat 48 Felder, das ist für eine Nachschlagetabelle eher wenig.
>
> Unterhalb von etwa hundert Feldern war „Shaper + Matrix“ bei echten gescannten Targets genauer als beide cLUTs – eine Tabelle braucht reichlich gut verteilte Felder, bevor sie überhaupt etwas zum Interpolieren hat, und mit weniger bildet sie das Rauschen im Scan ab. Deine Wahl bleibt bestehen; das hier ist nur ein Vorschlag, und es wurde nichts für dich geändert.

**(c)** — shown here with a 288-patch target:

> A note on the profile type: “cLUT — Lab table” has a ceiling, and how high it sits depends on Advanced… ▸ White point handling.
>
> A Lab table cannot describe anything above that ceiling: every tone over it comes out at one lightness, with the differences flattened away. On “Scale white to a perfect white surface” the ceiling is at about 114 % reflectance, brighter than a perfect white surface, so nothing you can put on the glass reaches it and there is nothing to worry about. On “Map chart white to white” it drops to about 94 %, which ordinary bright photo paper does reach. “cLUT — XYZ table” has no ceiling under any of those settings and measured just as accurate on the colours your target does contain, so it is the safer of the two. Your choice stands either way, and nothing here has been changed for you.

*German:*

> Ein Hinweis zum Profiltyp: „cLUT — Lab-Tabelle“ hat eine Obergrenze, und wie hoch sie liegt, entscheidet Erweitert… ▸ Weißpunkt-Behandlung.
>
> Eine Lab-Tabelle kann nichts oberhalb dieser Grenze beschreiben: Jeder Ton darüber kommt mit einer einzigen Helligkeit heraus, die Unterschiede sind eingeebnet. Mit „Weiß auf eine perfekt weiße Fläche skalieren“ liegt die Grenze bei rund 114 % Reflexionsgrad, heller als eine perfekt weiße Fläche, nichts, was du auf das Glas legen kannst, erreicht sie also, und es gibt nichts zu befürchten. Mit „Chart-Weiß auf Weiß abbilden“ fällt sie auf etwa 94 %, was gewöhnliches helles Fotopapier durchaus erreicht. „cLUT — XYZ-Tabelle“ hat unter keiner dieser Einstellungen eine Obergrenze und war auf den Farben, die dein Target tatsächlich enthält, genauso genau, sie ist also die sicherere der beiden. Deine Wahl bleibt so oder so bestehen, und hier wurde nichts für dich geändert.

> **⏳ Awaiting confirmation, 2026-09-06 (CL-6).** *Note (c) above is not the
> wording Basti approved on 2026-09-04, and the wording he approved had stopped
> being true the day after: B8-75 moved the white-point default on 2026-09-05,
> and from then on this note told a user on the shipped default that their
> bright paper was being flattened and sent them to "Auto-scale to avoid
> clipping" to lift a ceiling that already sat at about 114 % reflectance,
> above anything that can physically be put on the glass. The same ⓘ gave two
> answers, 130 lines apart. It now names the ceiling and says what decides how
> high it is. **Confirmed by:** *nobody yet.*

*The other eleven catalogues carry the English source until this is ruled on,
because translating a draft translates it twice. German is translated, as the
beta convention has it. 22 keys arrive and 1 is retired — the retired one is the
sentence this item exists to remove, "XYZ and Lab are just how the table stores
colour inside; both are accurate, and Lab sometimes gives slightly smoother
neutrals", which nothing measured either way.*

*The dropdown's "(default)" markers are unchanged in BOTH modes: the
measurements support keeping **Shaper + matrix** as the scanner default (B8-19)
and say nothing against **cLUT — Lab** as the printer one, which is also
ArgyllCMS's own default and ChromIQ's own in tab 4
(`workflow/profile_builder.py`, `data/parameters.yaml`). If either default were
ever moved, the marker, the help and the recommendation would have to move in
the same commit or the window would contradict itself.*

### Button label — the driver consent window's decline button (AGENT-BD) — ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Proposed 2026-09-05 by AGENT-BD. Basti approved
the CHANGE — *"fix the ok button and the grammar, then land it"* — but not a
particular phrase, so the phrase is here for him to correct.

*Deliberately NOT given an `M-` identifier, for the reason the two sections above
give: §M is a catalogue of MESSAGES, each one rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading in this document to exist there. A button label is
not a message and must not be given a fake identifier to satisfy a parser. It is
recorded here because it is user-facing wording and this is where user-facing
wording is proposed and ruled on.*

`ui/dialogs/settings_dialog.py::_driver_notice` shows two kinds of window. With
no second button it is a NOTICE — it asks nothing, and **OK** is exactly the
right word for acknowledging one. With a second button it is an OFFER, and then
the plain button is the **DECLINE**: `ok.clicked.connect(dlg.reject)`,
deliberately, because `box.accepted` fires for OK too and that is how OK once
came to start an elevated driver install (`f7a565ad`).

The behaviour has been right since that commit and a mutation kills seven tests
if it is undone. **The WORD was still wrong.** On "Before ChromIQ starts" —
the one window in ChromIQ whose entire purpose is informed consent — the row
read `Herunterladen und installieren` and `OK`, and OK is the word most people
read as "yes". Somebody skimming clicks it meaning to agree and gets the
opposite of what they intended, which is the single mistake that window exists
to prevent.

| proposed label | replaces | German | where it appears |
|---|---|---|---|
| **Not now** | OK | Jetzt nicht | the dismissing button of any driver window that OFFERS something |

*It is not new vocabulary. `ui/cr30_calibration.py` already builds a button
labelled **Not now** for exactly this meaning — declining an offered action in a
window that can be opened again — so this reuses that key rather than adding a
thirteenth way to say no, and German is already translated. **Zero new
translation keys.***

*It is correct on all five offers this window makes — `Download and install`,
`Check and install`, `I already have the folder…`, `Choose a different folder…`
and `Try Zadig` — and nothing is lost by pressing it: every one of these windows
is reachable again from Preferences ▸ Instrument drivers…. A label naming the
action ("Don't install") would be correct on two of the five and wrong on three.*

*The alternative considered and not chosen was Qt's **Cancel** / `Abbrechen`,
which is equally unmistakable and also costs no new keys. It was rejected
because there is nothing in flight to cancel on three of the five windows — the
user is declining an offer, not aborting an operation — and because "Not now" is
already the house word for that.*

*Only the button's TEXT changes. It stays a `StandardButton.Ok`, so its role,
its place in the row and its identity to everything that looks it up are
unchanged, and it remains the dialog's default — the key most people press to
get rid of a window still declines. Measured in all thirteen languages, in the
dark appearance's wider button font, on a screen tall enough that the window is
not at its cap: the row fits, nothing is clipped, nothing runs past the edge
(`tests/test_usb_driver_dialog.py::test_the_consent_buttons_fit_the_row_in_every_language`).*

### The driver window's fifth ending — an install that has not finished (A9) — ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Proposed 2026-09-06 by A9. Nobody has ruled on
this wording; it is recorded here because it is user-facing wording on the
driver helper, and this is where user-facing wording on that window is proposed
and ruled on.

*Deliberately NOT given an `M-` identifier, for the reason the driver consent
button's section above gives: §M is a catalogue of MESSAGES rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading in this document to exist there. The driver helper
is a Preferences window, not a measurement window, and must not be given a fake
identifier to satisfy a parser.*

**What was wrong.** `core/usb_driver_installer.py::install_winusb` waited 60 s
for the elevated installer, threw away what `WaitForSingleObject` returned, then
read `GetExitCodeProcess` — which answers `STILL_ACTIVE` (259) for a process
that has not finished. `259 != 0`, so the window said the install had **failed**
and offered **Try Zadig**. Measured on the bench 2026-09-06 against a real
driverless X-Rite i1Studio on an idle 2-core ARM64 VM, a *successful* install
took **48.6 s** (`00:41:24.501` → `00:42:13.129`) — 11.4 s inside that budget,
most of it Windows making a system restore point. On a machine that is actually
busy the window would have called a succeeding install a failure and sent the
user to replace a driver that was being installed as they read it.

**The window now has a fifth ending**, alongside *It worked* / *cannot tell you
whether that changed anything* / *did not take* / *failed or was cancelled*. It
is reached when ChromIQ stops WATCHING — because its five-minute budget ran out,
or because the user pressed the button that says so. It never says "failed", it
names no instrument, and it offers no Zadig button.

> **ChromIQ stopped waiting, and cannot tell you whether that worked.**
>
> The installer had not finished when ChromIQ stopped watching it. Nothing was
> cancelled and nothing was undone. Windows is very likely still installing the
> driver, and it may well finish on its own.
>
> Give it a moment, then open **Instrument drivers** in Preferences again and
> use **Check again**. That looks your instrument up afresh and says whether the
> driver is attached now.

*No instrument is named because there is nothing to point at:
`unbound_targets()` is deliberately not asked while an install is in flight — it
samples the same device stack wdi-simple is re-enumerating and can be wrong in
either direction. No Zadig button, because nudging somebody to replace a driver
while an elevated installer is still putting one in is the one action here that
could leave the machine worse than it started. Both onward controls are named
from the controls' own `tr()` keys via `_in_prose`, the same way the reboot
window and the "cannot tell" ending are, so they cannot drift from the buttons
in any of the twelve languages.*

**And the window that is on screen while it waits.** The install used to hold
the GUI thread: `Get-Process ChromIQ` reported `Responding = False` for ~50 s
with no spinner, no message and no cursor change, and the owner read it as a
hang (*"after confirming the uac nothing seems to happen"*, then *"it seems to
be hanging"*).

| what it says | when |
|---|---|
| **Installing the driver for {name}. Windows makes a restore point before it touches a driver, and that is most of the wait.** | from the first moment there is anything to wait for |
| button: **Stop waiting** | on that window |

*The window appears only once there is a wait — an install that ends at the
permission prompt takes 2-5 s and gets nothing flashed at it. It is
application-modal, which is what stops a second install, a closed Preferences
window or a quit while an elevated installer is running.*

*The button is **Stop waiting** and not Qt's **Cancel**. The section above
rejects `Cancel` on this window's other five offers because "there is nothing in
flight to cancel … the user is declining an offer, not aborting an operation".
Here something IS in flight — and it still cannot be cancelled: an elevated
driver install cannot be safely killed, and ChromIQ does not try. The button
stops ChromIQ watching, which is what it says, and the ending above says the
same thing again in a sentence. **Not now** was considered and is wrong for the
same reason: nothing is being offered.*

**And a sixth sentence, for an instrument ChromIQ never got to.** `Reinstall
Driver` runs over every detected instrument, one permission prompt each, and the
run stops after five of the endings — the user said No, Windows would not ask, or
an elevated installer may still be running and starting a second one while it
holds Windows' PnP install lock is a way to make a good install fail. Whatever
the instruments that WERE tried have earned, this is appended:

> ChromIQ stopped before it reached {names}. Nothing was tried there, and
> nothing was changed.

*It exists because the shipped code did the skipping SILENTLY and then blamed
the skipped instrument: `all(install_winusb(d) for d in targets)` is a
generator, so the first falsy answer ended the iteration, and the untried
instrument came back from `unbound_targets()` to be named in "the driver still
isn't bound to {names}" — a sentence about an install that never happened. It is
one sentence with no count and no pronoun, so it reads for one instrument and for
four without a singular/plural pair, the same way the "isn't bound to" sentence
beside it already does.*

*The permission prompt itself is still frozen time — `SEE_MASK_NOASYNC` makes
`ShellExecuteExW` block until the shell operation completes, so ChromIQ does not
pump events while Windows asks for consent. That is deliberate: consent must
stay a modal, deliberate act. It is a second or two, not fifty.*

### The measurement guard's "{where}" — a preposition glued to a translated noun (AGENT-BD) — ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Recorded 2026-09-05 by AGENT-BD. **No wording is
being proposed here** — every sentence below is the wording that already
shipped, re-cut so that each language can inflect it. It is recorded because
part of it is a §M concern and because the sibling defect named at the end is
one somebody has to rule on.

ChromIQ's driver helper refuses to open during a measurement and says why. That
paragraph used to be built by formatting `core.instrument_lease.where_label()`'s
noun phrase into `"…is being read right now, from {where}."` English survives
that, and German survives it only because both labels were hand-inflected into
the dative to fit. Rendered from the shipped catalogues, four languages did not:

| | what it produced | what the language needs |
|---|---|---|
| it | da la scheda Misura | **dalla** scheda Misura |
| pt | a partir de o separador Medir | a partir **do** separador Medir |
| pl | z karcie Pomiar | z **karty** Pomiar (genitive) |
| ru | из вкладке «Измерение» | из **вкладки** «Измерение» (genitive) |

*Nothing in the project could see it. `tests/test_i18n.py` sees a key that is
present, translated, and whose placeholder matches. `scripts/i18n_extract.py`
sees nothing at all — the broken sentences exist nowhere as literals, they are
assembled at run time, so no translator was ever shown one.*

*Hand-inflecting the label was the German fix (`8d5b8430`) and it cannot
generalise: two different sentences interpolate the same label with two
different prepositions, and a language with cases needs a different form of the
noun in each. So the WHOLE SENTENCE is the translatable unit now — one complete
sentence per holder, with nothing formatted into it — and each language writes
its own preposition, article and case. It is also its own paragraph rather than
glued to the next with a space, because ja and zh join sentences with 。and no
space: even joining two translated sentences is a decision the code must not
make on a translator's behalf.*

**The sibling, which is NOT fixed and needs a ruling.** `M-INSTRUMENT-BUSY`
("ChromIQ is measuring in {where}") is fed by the same `where_label()` and has
the identical fault — "in la scheda Misura", "in o separador Medir", "in karcie
Pomiar", "in вкладке «Измерение»" — and it is worse, because that sentence is
still the English source in eleven of the twelve catalogues. It is a §M message,
so its wording is not an implementer's to change; it is raised here and left
alone.

### M-CAL-REQUESTED · PROPOSED · the placement window of a calibration the user asked for during a measurement — Measure, ChromIQ engine, strip and patch by patch

*New 2026-10-03. Knut, #182 5965478577 and 5965735823, and Basti, 5965500670, approved the behaviour: K, or the optional Calibrate button (Preferences ▸ Measurement, off by default), takes a new instrument calibration between strips or patches, on ChromIQ's own engine only, without ending the measurement. The window is NOT "Calibration required": readings exist, so its Cancel is "Cancel calibration" and keeps measuring (it sends `{"cmd":"cal_cancel"}`, never Esc, so it never marks the session as ended by the user), and it plays no sound (Knut). The instruction for the instrument itself, `calibration_instructions_html`, is shown under this text, as in "Calibration required". The wording is ours.*

> **Calibrate the Instrument**
>
> You asked for a new calibration. Everything you have measured so far is already saved.
>
> Place the instrument as described below, then press “Start Calibration”. When it is done, you carry on with the strip or patch you were on.
>
> If you change your mind, press “Cancel calibration”: nothing is measured, and you keep measuring with the calibration the instrument already has.

### M-CAL-REQUESTED-DONE · PROPOSED · the short "carry on" Calibration complete, after a calibration the user asked for — Measure

*New 2026-10-03, with M-CAL-REQUESTED. The four existing "Calibration complete" windows explain how to start measuring, which the user is already doing; this one says only that the measurement goes on, with the same key list (K included). Shown only when the instrument asked to be placed; a calibration that needed no step from the user says so in the log and the status line.*

> **Calibration Complete**
>
> The instrument has a new calibration. Carry on measuring from where you were: the reader is waiting for the same strip or patch as before.

### M-CAL-REQUESTED-FAILED · PROPOSED · a calibration the user asked for did not succeed, and reading is locked — Measure

*New 2026-10-03, with M-CAL-REQUESTED. Reading is LOCKED until a calibration succeeds: an i1Pro measures its white straight into its calibration and checks it only afterwards (`i1pro_imp.c:2230`, `2429-2433`), so after a failure it would read on without an error against a wrong reference (challenge, 2026-10-03, 1c). Try again sends another calibrate; Save and stop runs the save chain directly, as Patch Read Failed's Save Partial & Quit does (`measurement_exit_strategy.md` note 1). Closing the window leaves the lock in place, and the status line says that K, Calibrate or Stop are the ways on. `{reason}` is the instrument's own sentence, or "the calibration was cancelled" when a second attempt was cancelled at its placement prompt. The sound is Instrument error (`measurement_window_sounds.md`, awaiting confirmation).*

> **The Calibration Did Not Succeed**
>
> The instrument could not be calibrated.
>
> Everything you measured before this is saved. Nothing more is read until a calibration succeeds, because a calibration that went wrong part of the way through can leave the instrument holding values that would make every following reading wrong, without any error to show for it.
>
> •  Try again: place the instrument as asked and calibrate once more.
>
> •  Save and stop: end the measurement with what you have measured. You can carry on later with “Refine / resume existing measurement (-r)”.
>
> What the instrument reported: {reason}

### M-CHART-PATTERN-REFUSED · PROPOSED · a strip or patch pattern the readers cannot use — Create Chart, under the preview

*New 2026-10-03, forum report (strip pattern "0-9", 14 strips, "Bad location field value '(null)' on patch 266"). ChromIQ prints its labels with its own rule (letters when the pattern contains "A-Z", otherwise 1, 2, 3 ...) while ArgyllCMS chartread and ChromIQ's engine read them with ArgyllCMS's pattern grammar, so any pattern whose labels differ from the printed ones makes a chart that cannot be measured. A NEW layout (Generate Chart, the live preview, a patch set loaded or applied from the Editor) is now refused for such a pattern: the box turns red, this sentence stands under the preview, and Generate Chart is unavailable. Not a window, and nothing in the log while typing: it follows every keystroke. Restore Used Chart still redraws a chart already printed. `{reason}` is one sentence naming the pattern and what is wrong with it (too few labels for the chart's strips or patches, a label ArgyllCMS names differently from the one printed, a location whose strip and patch cannot be told apart, or a pattern ArgyllCMS cannot read at all). Shown before approval, like the other texts of this list, because it protects a chart from being printed unreadable.*

> **This strip or patch pattern cannot be used**
>
> {reason} Generate Chart stays unavailable until the pattern is changed.

### M-CHART-LOCATIONS-UNREADABLE · PROPOSED · a printed chart whose locations its patterns cannot read — Measure tab, before any reader starts

*New 2026-10-03, the same forum report seen from the Measure tab, on a sheet already printed with such a pattern. Before Start launches any reader, the chart's own SAMPLE_LOC values are checked against its STRIP_INDEX_PATTERN and PATCH_INDEX_PATTERN exactly as chartread checks them, and a chart ChromIQ laid out must also carry, at every patch, the label its patterns give that strip and patch. When it does not, no reader is started, so there is no fallback to stock chartread either (it reads the chart the same way and would fail a second time, or file the readings under the wrong patches without an error). `{detail}` names the first location that does not fit.*

> **This chart cannot be measured**
>
> This chart's patch locations do not fit its strip and patch patterns: {detail}.
>
> ArgyllCMS chartread would refuse the chart before the first patch, or file the readings under the wrong patches, and ChromIQ's own measuring engine reads it the same way. So ChromIQ has not started a measurement, and nothing has been changed.
>
> The chart was laid out with a strip or patch pattern that ArgyllCMS reads differently from the labels printed on the sheet. To measure, generate the chart again with the default patterns (A-Z, A-Z for strips and 0-9,@-9,@-9;1-999 for patches) and print it again.

### M-CHART-LEGACY-STOCK · PROPOSED · a sheet only ChromIQ's engine can read, with ArgyllCMS chartread selected — Measure tab, before any reader starts

*New 2026-10-03. Knut, #182 5965589190 Q2: a sheet printed with ChromIQ's labels from before 4.3.3-beta.7 is read by ChromIQ's own engine as printed, without changing the chart file, while a user of stock chartread is told plainly that chartread cannot read it. Nothing is started. `{detail}` names the first location that does not fit.*

> **ArgyllCMS chartread cannot read this chart**
>
> This chart's patch locations do not fit its strip and patch patterns: {detail}.
>
> The labels were printed by an earlier version of ChromIQ, and ArgyllCMS chartread reads them differently from the sheet, so it would refuse the chart or file the readings under the wrong patches. ChromIQ's own measuring engine reads the labels as they are printed.
>
> Right now, “ChromIQ chart-reading engine” in Preferences → Measurement is switched off, so ArgyllCMS chartread reads your charts. Switch it on and this chart measures normally. Nothing has been started or changed.

### M-CHART-LEGACY-ENDED · PROPOSED · the engine run on such a sheet ended, and there is no second reader — Measure, the log and the status line

*New 2026-10-03, the same ruling. When the engine stops on a sheet only it can read, none of the three fallbacks to stock chartread is made (immediate, whole-sheet mode, the mid-run resume), so the two fallback messages, one of which promises that every measured strip will be kept, are not shown. The words follow M-CR30-READ-ENDED. `{reason}` is the engine's own sentence.*

> **The measurement stopped**
>
> Reading this chart has stopped before it finished.
>
> This chart's labels were printed by an earlier version of ChromIQ in a way ArgyllCMS chartread cannot read, so there is no second reader to try, and ChromIQ has not started it.
>
> Nothing you have already measured is lost: every patch that was read is on disk, and you can carry on from it by ticking “Refine / resume existing measurement (-r)” before you press Start again.
>
> What went wrong: {reason}

### M-PATCH-CORRECTED-VARIANTS · PROPOSED · the green outline's two lines Knut's example did not cover — Measure tab preview and the closing window, #182 beta 11

*New 2026-10-04. Knut approved the green outline and its words in 5984277558 (M-PATCH-CORRECTED); his example was a neighbour-check misread of two patches. These two are ours and wait here: line 1 is the card's middle line when only the LIMIT flagged the first reading, in place of "did not fit; the new one does."; line 2 is the closing window's line for one patch.*

> **Green outline: corrected by a re-read**
>
> reached the patch error limit; the new one is below it.
> 1 misread corrected by a re-read: patch {locs}.

### M-PATCH-UNSETTLED · PROPOSED · a re-read past the limit that agrees with no earlier reading — Measure tab preview, #182 beta 12

*New 2026-10-07. Knut, [6045500910](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6045500910) answer 2: a patch red by the limit, read again past the limit and not the same as before, stays red, "and message should say that the two measurements were not similar and both above error threshold, and needs another measurement to confirm what is the reoccurring and correct value for the patch." The rule is CONFIRMED in 10.10a; the words are ours and wait here. The card breaks its lines by hand; the headline stands under the card's separator. `{de}`: this reading's ΔE\*ab; `{prevs}`: the earlier readings past the limit, in the order read, one decimal each, joined by ", "; `{limit}`: the limit, one decimal; `{n}`: how many readings, 3 or more (lines 2 and 3 cover two). Which lines: the headline, line 1, (for a patch the neighbour check also suspects, M-PATCH-NEIGHBOUR's lines 2 to 5 with "It also does not fit"), a blank line, lines 2 and 3 for two readings or lines 4 and 5 for more, a blank line, lines 6 and 7, a blank line, and "(Preferences ▸ Measurement, “Flag a patch…”)". Example: "Red outline: the readings do not agree / ΔE\*ab 150.4 now; before: 120.3 / / The two readings are not similar, / and both are past your limit 95.0. / / Read it again: a reading that matches / one of them shows which value is real."*

> **Red outline: the readings do not agree**
>
> ΔE*ab {de} now; before: {prevs}
> The two readings are not similar,
> and both are past the patch error limit ({limit}).
> The {n} readings are not similar,
> and all are past the patch error limit ({limit}).
> Read it again: a reading that matches
> one of them shows which value is real.

### M-REPORT-THROUGH-PROFILE · PROPOSED · a verification printed through its profile, judged against its source colours and its profile's prediction — Measurement Report (window and PDF), #182 beta 12

*New 2026-10-07. Knut, [6045500910](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6045500910) answer 1, "OK" to question 1 of [6044584365](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6044584365): judge the profile's accuracy against its own prediction, and colour fidelity against the true source colour on in-gamut patches only. The ruling is CONFIRMED (`verification_printing_and_target.md` B3, `measurement_report_limits.md` §58); the words are ours and wait here. The headline heads the new table of the detailed section and the new block of the Overview. Line 1 heads the colour-accuracy table of such a sheet, in place of "Colour accuracy (ΔE00 against the chart's design)"; line 2 is the "Reference for the ΔE figures" row of "How this verification was produced" (`{profile}`: the source profile's file name, `{intent}`: the intent as that block names it, "relative colorimetric"); line 3 its "What this measured" row; line 4 stands under the Profile accuracy table; line 5 replaces the table when the profile's prediction cannot be worked out (the profile changed since the print, another light, a calibration that cannot be read again).* *Beta 15: line 4 revised for k40 (Knut 6059912998, answer 1: a failed Profile accuracy table fails the sheet; it said "these words do not change the sheet's verdict"). Lines 6 to 9 are new for k41 (answer 2), a sheet printed through the perceptual or saturation intent: line 6 replaces line 2 and line 7 replaces line 3 there, and lines 8 and 9 are the note on its five colour-accuracy rows, which are shown for information (`measurement_report_limits.md` 58.8 and 58.9).*

> **Profile accuracy (ΔE00 against the profile's own prediction)**
>
> Colour accuracy (ΔE00 against the colours the sheet was converted from)
> the colours the sheet was converted from: the chart's colours in {profile}, {intent}. Only the colours inside the profile's gamut ({intent}) are judged; the others are shown beyond the gamut, for information.
> two things: how faithfully the colours inside the profile's gamut were reproduced, and how accurate the profile is against its own prediction
> Every patch, inside the gamut or not, compared with what the profile predicts for the ink amounts that were really printed. Judged with the same limits, and a value over its limit here also fails the sheet's overall verdict.
> The profile's prediction of this sheet could not be worked out, so the profile's accuracy is not shown.
> the colours the sheet was converted from: the chart's colours in {profile}, {intent}. The sheet was printed with a rendering intent that changes colours on purpose, so this comparison is shown for information only and is not judged.
> how accurate the profile is against its own prediction. The rendering intent changed the colours on purpose, so how closely they match the original colours is shown for information only
> This sheet was printed with the perceptual rendering intent, which changes colours on purpose so that all of them fit inside the printer's gamut. So this value compares the print with the original colours for information only and is not judged against a limit. The sheet is judged on its profile accuracy instead: every patch against what the profile predicts for the ink amounts that were really printed.
> This sheet was printed with the saturation rendering intent, which changes colours on purpose to make them as vivid as the printer allows. So this value compares the print with the original colours for information only and is not judged against a limit. The sheet is judged on its profile accuracy instead: every patch against what the profile predicts for the ink amounts that were really printed.

### M-PREVIEW-AS-PRINTED · PROPOSED · the chart preview's indicator: shown as it will print, or as device values — Create Chart, Print Chart and Measure, #182 beta 12

*New 2026-10-07. Knut, [6045500910](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6045500910) answer 4: "preview should always look as paper would look printed, assuming normal printing path, as Sebastian said." Basti, [6045468325](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6045468325): "as soon as those settings are locked in for a verification run I think showing the softproofed version makes sense. Maybe the tiff preview could show a little indicator that gives this information without being a distraction." The behaviour is CONFIRMED (`verification_printing_and_target.md` §3.7); the words are ours and wait here. The indicator is a small label in the top right corner of the chart preview of the three tabs. The headline is shown over a page printed raw and shown through the run's profile (a profiling chart once the run has a profile, a FROM PROFILE GAMUT verification chart, a verification chart printed raw); line 1 over a verification chart printed through the profile; lines 2 to 4 over a page shown as its device values (the run has no profile yet; the pages carry the printer calibration; ArgyllCMS could not convert the page). Lines 5 to 9 are the label's tooltip, in the same order (5 for the headline, 6 for line 1, 7 to 9 for lines 2 to 4). `{profile}`: the run profile's file name, `{source}`: the source profile's file name (sRGB.icm), `{intent}`: the print's intent as the report names it ("relative colorimetric").*

*Extended 2026-10-08 (beta 12, build C). Basti asked for the indicator to be the switch between the two views, and to stay small: collapsed it is only an icon (a paper sheet with a folded corner while the preview shows the page as on paper, a small screen while it shows the device values); on hover it slides open to a short line, and the full explanation stays in the tooltip. Lines 10 and 11 are that line's view, lines 12 and 13 what a click switches to, shown beside it in a lighter tone ("As on paper  click: device values"). The tooltip of a page shown as on paper is its headline (or line 1), its explanation (5 or 6) and line 14; the tooltip of a page shown as device values by choice is line 11 and line 15; the tooltip of a page that has no view on paper is its line (2 to 4), its explanation (7 to 9) and line 16, and that indicator shows lines 2 to 4 as its short line with no click hint. The first line of the tooltips that offer a switch ends in the shortcut in brackets, added after translation as every tooltip shortcut is. `{keys}`: the platform's spelling of the shortcut (⌘Y on macOS, Ctrl+Y on Windows and Linux).*

> **As on paper, via the run's profile**
>
> As on paper, printed through the profile
> Device values, no profile yet
> Device values, calibrated pages
> Device values, profile not applied
> The preview shows this chart as it prints: the ink amounts in the file, as the run's profile {profile} predicts them on paper, with the paper shown as white. What is printed does not change.
> The preview shows this chart as it prints through the profile: its colours converted from {source} to {profile} ({intent}), as ChromIQ converts them when printing, then as the profile predicts them on paper, with the paper shown as white. What is printed does not change.
> The preview shows the ink amounts in the file as screen colours, so it can look lighter or more colourful than the print. Once this run has a profile, the preview shows the chart as it prints.
> The pages of this chart carry the printer calibration, which the profile does not describe, so the preview shows the ink amounts in the file as screen colours.
> ArgyllCMS could not convert this page through {profile}, so the preview shows the ink amounts in the file as screen colours.
> As on paper
> Device values
> click: device values
> click: as on paper
> Click here, or press {keys}, to see the ink amounts in the file as screen colours instead. ChromIQ remembers your choice in Create Chart, Print Chart and Measure.
> You chose to see the ink amounts in the file as screen colours, so the preview can look lighter or more colourful than the print. Click here, or press {keys}, to see the chart as it prints through {profile} again. What is printed does not change.
> This page cannot be shown as on paper, so a click changes nothing here.

### M-PATCH-NEIGHBOUR-VARIANTS · PROPOSED · the neighbour check's two card lines the mock-ups did not show — Measure tab preview, #182 beta 17

**Text approved by:** Basti, 2026-10-10 (both lines, as listed by the review of beta 17). **Knut has not confirmed them yet**, so they stay here until he does.

*New 2026-10-09 (beta 17). The rest of the card's neighbour lines were approved by Knut (M-PATCH-NEIGHBOUR); these two follow the same wording and wait here. Line 1 stands on the red card of a patch past the patch error limit that ALSO fails the neighbour check, after the limit's lines, in place of its colour range's lines. Line 2 stands under "Measured" instead of M-PATCH-NEIGHBOUR lines 3 to 5 while fewer than 2 read patches lie within the colour-neighbour radius (the patch is then not judged). Placeholders as in M-PATCH-NEIGHBOUR. Both are whole sentences: the card wraps them to its width.*

> **Neighbour check on the patch card, two more lines**
>
> It is also ΔE {d} further from its expected colour than the {n} patches nearest in colour (median), passing the neighbour limit ({limit}).
> Not compared with the patches nearest in colour yet: fewer than 2 within the colour-neighbour radius are read.

### M-MEASURED-SUSPECTS · PROPOSED · the suspected misreads in the window that closes a measurement — Measure tab, #182 beta 11

*New 2026-10-04, revised in the review of beta 11. Knut, [5983470377](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983470377) answer 5: "The Measurement Completed window, which today has a summary of some things (like the reading speeds) should also hold a short summary of the detected suspected misreads from the neighbour-test method and (if active) the strip misreading test." The behaviour is his, the words are ours and wait here. The headline names the block in the model and is not shown: the lines stand under the reading-time summary of the closing window (All Strips Read, All Patches Read, Re-measurement Complete, Calibration Measurement Complete, and the averaging window), and **never on a verification's closing window**. Lines 1 to 7 only where the neighbour check applies (10.9): line 7 alone when no patch could be checked; otherwise line 1, or line 2 or 3, then line 4 or 5 when suspects its re-reads confirmed were kept as real (only a re-read can, 5984174575), and line 6 when not every patch could be checked. Lines 8 to 10 only when "Was a strip read twice?" watched the measurement (strips read with ChromIQ's engine, outside guided refinement): line 8 when it asked nothing, otherwise line 9 or 10 with each strip it asked about as line 11, 12 or 13 by its answer (Re-read, the other strip read on purpose, Keep or closed). `{locs}`: the patches still red, in chart order, the first ten and then "…".*

> **Suspected misreads**
>
> Neighbour check: no suspected misreads.
> Neighbour check: 1 suspected misread, patch {locs}. Read it again before you build the profile.
> Neighbour check: {n} suspected misreads, patches {locs}. Read them again before you build the profile.
> 1 patch it flagged was read again with the same result, so it is taken as real.
> {n} patches it flagged were read again with the same result, so they are taken as real.
> {checked} of {total} patches had enough patches near in colour to be checked.
> Neighbour check: none of the {total} patches had enough patches near in colour to be checked.
> Strip read twice: none found.
> Strip read twice: 1 strip looked like another, {list}.
> Strip read twice: {n} strips looked like another, {list}.
> {strip} (like {like}, read again)
> {strip} (like {like}, set aside)
> {strip} (like {like}, kept)

### M-CHART-SLOW-NO-PROFILE · PROPOSED · the "taking longer than usual" window of a chart built WITHOUT a pre-conditioning profile — Create Chart, while targen runs

*New 2026-10-08, beta 12. The window that offers the faster patch layout when targen runs long (`ui/dialogs/slow_chart_dialog.py`) had one text, written for a refinement chart: it said the slowdown happens "with certain pre-conditioning profiles", promised "the same profile", and judged the quality "for a refinement chart". It also appears for a plain CMYK chart with no profile at all (beta-11 targen review, -d4 with an ink limit), where all three are wrong. A build that passes targen a profile (-c) keeps the existing text unchanged; a build without one shows this text instead, which names only what applies. The headline and the three buttons are the existing ones.*

> **This chart is taking longer than usual**
>
> ChromIQ hasn't frozen: your chart is still being built in the background. On larger (multi-page) charts, Argyll's standard way of arranging the colour patches can slow down dramatically, and that's what's happening here.
>
> You have three choices:
>
> • Keep waiting: let it finish with the highest-quality patch layout. Be aware this may take a very long time, and there's no reliable way to predict how long.
>
> • Rebuild with the faster layout (recommended): ChromIQ stops this attempt and immediately rebuilds the same chart, with the same number of patches, using a different patch-arrangement method that doesn't suffer from this slowdown. The patches are still spread evenly through the colour space, and it usually finishes in under a second.
>
> • Cancel: stop building the chart. Nothing is saved.

### M-x. Which table uses which message

**Calibration replacement** (`docs/design/calibration_run_type_plan.md` Table C,
and `docs/design/calibration_run_type.md` §4.4). Which of the two appears is
`Calibration.exists()`; what the code then does is `Calibration.result_files()`,
which is wider — see M-CAL-REPLACE-CHART.

| condition | message |
|---|---|
| `cal/` empty | none |
| `cal/` has a chart, nothing measured | **M-CAL-REPLACE-CHART** — and the chart is NOT kept |
| `cal/` has a `.ti3` and/or a `.cal` | **M-CAL-REPLACE-MEASURED** — everything moves to `cal/old/<date>/` |
| …and runs were built on that `.cal` | **M-CAL-REPLACE-MEASURED** + its `{runs_line}` |
| an archive was really made | **M-CAL-ARCHIVED-HERE**, in the log |

| Table | Rows | Message |
|---|---|---|
| §1 Every way a measurement can end | 1–4, 6–12 | **M-END** |
| §1 | 5 | **M-END-EMPTY** |
| §3a Every state a `.ti3` can be in | empty, header-only | **M-TI3-EMPTY** |
| §3a | `B ≠ C`, `C > A` | **M-TI3-MISMATCH** |
| §3b Judging by C₀ → C | `C = 0` after resume, `C < C₀` | **M-TI3-SHRANK** |
| §4 Chart integrity | chart + `.ti3` (+ profile), Profiling | **M-CHART-PROFILING** |
| §4 | + verifications, Profiling | **M-CHART-PROFILING** then **M-PROFILE-VERIFY** wording folded in — see §8 sequence |
| §4 | Verification run | **M-CHART-VERIFY** |
| §4a validity | rows 3 and 5 | **M-CHART-NOPAGES**, in addition to the §4 message |
| §4a | rows 1, 2, 7, 8 | none |
| §5 Starting over | partial, no resume | **M-REPLACE-PARTIAL** |
| §5 | complete | **M-REPLACE-COMPLETE** |
| §5 | corrupt | **M-TI3-MISMATCH** |
| §6e Rebuilding | rows 5, 6 | **M-PROFILE-VERIFY** |
| §6e | rows 1–4, 7 | none |
| any recommending Duplicate while it is unavailable | — | **M-DUPLICATE-BLOCKED** appended |
| §3a header-only, empty | Start Measurement | **M-REPLACE-UNCOUNTABLE** ✅ |
| §4, trigger = auto-update preview | — | **M-PREVIEW-PAUSED** ✅ |
| §4, run holds a corrupt or empty `.ti3` | Profiling | **M-CHART-CORRUPT** ✅ — the window itself, replacing M-CHART-PROFILING |
| §S1.2, Verification with no built profile | Start Measurement | **M-VERIFY-NO-PROFILE** ✅ |
| §S1.3, Verification with a profile but no verification chart | the greyed Start button's tooltip | **M-VERIFY-NO-CHART** ✅ |
| §6, the measurement is not in the selected run | Build Profile | **M-BUILD-ELSEWHERE** ✅ |
| §4, chart with no `.channels.json` | — | **M-CHART-NOPAGES** appended |
| §4, run with a verification history | Profiling | **M-CHART-W4** |

✅ = approved by Knut, 2026-08-04. 🆕 = **PROPOSED**, awaiting review — see **§M-PROPOSED**.

**Singular and plural.** Every message that states a count carries two bodies, and the one that reads correctly is chosen — "one dated verification measurement" against "4 dated verification measurements". Knut, 2026-08-03: *"Yes, use house rule with real singular and plural. You do not need to ask about this."* The bracketed "(s)" appears nowhere, and a test fails on it.


## I. The IMPORT module — a measurement made in i1Profiler — Confirmed behaviour

**Confirmed by:** Sebastian, 2026-08-10 — hardware session: a real ColorMunki
measurement imported via the module ("done, import worked and the messages
were good"); filing, chart snapshot, marker keyword and untouched original
verified on disk. M-IMPORT-DONE approved the same day; M-IMPORT-MISMATCH and
M-IMPORT-DATE-TAKEN remain in §M-PROPOSED (their windows were verified in the
on-screen drive but not yet read by a human).

*Built 2026-08-09 (#133). A third mode on the Measure tab — GUIDED · MANUAL ·
IMPORT — shown only while the shared Run type is **Verification**. It files a
measurement made outside ChromIQ (typically i1Profiler with an i1iO table)
through the same doors a native verification read uses.*

The sequence, in the order the code performs it (`TabMeasure._on_import_measurement`):

| # | Step | On failure |
|---|---|---|
| I.1 | "New run" guard (same window as Start) | stop, nothing written |
| I.2 | Verification guard — **M-VERIFY-NO-PROFILE** / **M-VERIFY-NO-CHART** | stop, nothing written |
| I.3 | A chosen dated verification that already holds its measurement → **M-IMPORT-DATE-TAKEN** | stop, nothing written — an import never replaces a result |
| I.4 | Convert to `.ti3` into `runs/runN/cache/import/` (`.mxf`/`.cxf` read directly; `.txt` via txt2ti3; a `.ti3` passes through). The user's original is never touched. | one window with the converter's reason |
| I.5 | Validate: patch count against the run's verification chart, then the patch-identity comparison the report itself uses → **M-IMPORT-MISMATCH** | stop, nothing written |
| I.6 | The same dated-folder + chart-snapshot front door as a native read (`_snapshot_verification_chart`): creates the folder on "New verification", moves the bar to it, asks before replacing a differing stored chart | user cancel stops the import |
| I.7 | Copy to `verifications/<date>/<name>-verify.ti3`, stamp `CHROMIQ_VERIFICATION "true"` | log line, nothing half-written |
| I.8 | **M-IMPORT-DONE**, with a button straight into the measurement report | — |

Deliberate limits (v1): an import never replaces an existing dated result
(the road to a fresh check is the bar's "New verification", exactly as for a
native read); a partial measurement (fewer patches than the chart) is refused,
not filed; profiling and calibration runs cannot import at all — a profile is
built only from a measurement made here.

> **Two of those three limits are WITHDRAWN by §I.9 / §I.10 below, and so is
> "shown only while the shared Run type is Verification".** They are left
> standing here because this section records what shipped; read them with the
> amendment. Since 2026-09-15 the module is shown for a **profiling** run too
> (a tester's report, Sebastian's ruling — §I.9, "Where the door is"); it is
> still hidden for a calibration run, which is the one limit that survives.

### ⏳ Awaiting confirmation — §I.9 / §I.10, importing into a profiling run

**Confirmed by:** *nobody yet.*

**Amendment approved by:** Sebastian, 2026-08-31 — the RULE is his ruling; the
BEHAVIOUR is not built yet, which is why the line above still says nobody. It
is promoted only once he has seen it work.

Two findings drove it, both from shipped code rather than opinion:

* ChromIQ **already** builds a profile from a partial measurement made here,
  deliberately: `ui/tabs/tab_profile.py:4026` — *"A partial measurement is
  legitimate… this does not forbid it — it says how partial it is, and leaves
  the choice with the user."* Refusing the same data on import contradicts it.
* ChromIQ **already advertises** the banned capability. `ui/dialogs/tools_dialogs.py:1324`
  tells the user: *"Measured your chart in X-Rite's i1Profiler? This brings
  those readings back into ChromIQ so you can build a profile from them."*

**I.9 · A profiling run may be an import destination.** The IMPORT module is
offered while the shared Run type is **Profiling** as well as **Verification**.
Its sequence is §I.1–§I.8 unchanged, with three substitutions:

* **I.5** validates against the run's own chart, `Run.chart_ti2`, in place of
  the verification chart.
* **I.6** keeps its chart snapshot — for a profiling run that is the run's own
  chart, not the verification chart. Dropping it (an earlier draft of this
  clause did) would leave the filed measurement with no record of what it was a
  measurement OF.
* **I.7**: the measurement is copied to `Run.measurement_ti3` — the run's
  canonical stem, never the source file's name, because the report finds its
  chart by that stem (`measurement_report._find_reference_ti2`) and a
  measurement filed under any other name falls back to
  `reference_source: device` without saying so.
* **I.8** offers *Open measurement report* and *Build the profile*.

**Where the door is. TWO DOORS, AND THIS CLAUSE WAS AMENDED ON 2026-09-15.**

As first written, this clause said the profiling import lived **only** in the
Build Profile tab: *"that tab is disabled for verification runs
(`ui/main_window.py:1590`), so the tab a person is on already says which act
they are performing, and they are never sent to another tab to perform it"* —
Basti, 2026-08-31: *"clicking the button should allow me to do the import there
instead of skipping around"*. That reasoning stands and the door it describes
stays exactly as it is.

What it did not anticipate is where a person LOOKS. A tester, 2026-09-15: *"an
odd thing: when doing an icc profile, importing from another program is on the
Build ICC Profile tab, and when doing a verification, importing is on the
Measurement tab. Probably makes sense for it to be on the Measurement tab on
both?"* Sebastian's ruling, the same day:

> *"For profiling I thought that when you have a measurement from i1Profiler you
> would want to build a profile out of it. That's why I made the import happen
> in the build profile tab. For verification however you don't build a profile
> so I needed another path for it. It is probably the easiest option to add the
> import module in the measurement tab in a profiling run as well."*

**ADD IT, DO NOT MOVE IT.** The IMPORT module is offered on the **Measure tab**
for a profiling run as well as a verification, and the Build ICC profile tab's
own import is untouched. Removing a working door to make a point about symmetry
would be a regression for the people already using it.

The two doors must not be able to say different things about the same file, so
they share the code that decides and the code that speaks: `measurement_import.assess`
judges it, `measurement_filing.refuse_it_does_not_belong` refuses it,
`measurement_filing.ask_to_make_a_new_run` asks §I.9's duplicate question, and
`measurement_filing.finish_the_import` ends it (the bar, the partial sentence of
§I.10, the hand-back). Only the ENTRY differs: the Build Profile door has to ask
which project and which run, because a file loaded there may come from anywhere;
the Measure tab door asks neither, because the bar above it has already said.

**What the Measure tab's door does NOT do, and why.**

* It does not ask **M-HOW-PRINTED**. That question offers "with colour
  management … with this run's profile applied", which cannot be true of a
  profiling chart: the profile is what the measurement is FOR. A profiling sheet
  is printed raw by construction, so there is nothing to ask.
* It does not write into `reads/readN.ti3`. An import is a standalone read, and
  the tab already treats one that way: `_promote_completed_read` files into the
  reads slot only while an averaging set is active, and otherwise *"ignores any
  reads/ left over from an earlier session"*. An imported file has no place in a
  sequence of reads taken here — its instrument and its date are its own — so it
  lands where a standalone read lands, at `Run.measurement_ti3`, and opting into
  averaging afterwards starts a clean set exactly as it does after any read.
* It does not show **M-IMPORT-DATE-TAKEN** or **M-IMPORT-MISMATCH**. Both speak
  of the verification chart, and a profiling reader must not be told about
  verifications. The mismatch is the shared
  `refuse_it_does_not_belong`; the date-taken case does not arise, because a
  profiling run's answer to "it already holds a measurement" is the duplicate
  question above, not a refusal.
* It DOES hand the measurement over with `measure_finished`, exactly as a read
  made here does, so the Build ICC profile tab is holding the import before its
  own window offers to take you there — and so an import accrues a dated
  measurement report beside the others, when the person has that option on.

**A chart is not a measurement of one.** Added 2026-09-15 after the refusal
doors were driven: the run's chart and its measurement sit in the same folder
under the same stem and are both CGATS tables, and printtarg writes the chart's
AIM values into the `.ti2`, so a chart picked by mistake parsed as a complete
set of readings, matched its own patch count exactly, and passed the identity
check against itself. Both doors now refuse a file whose CGATS table says
`CTI1` or `CTI2`, and the Measure tab asks it of the file the person picked,
before conversion can destroy the evidence.

**Choosing where it goes.** The load control asks: import into the open project,
or start a new one. With nothing open it offers to import into an existing
project, and performs ChromIQ's own Open Project act in place before carrying
straight on — one way to open a project, and no window that explains a fix and
then leaves the person to repeat what they just did.

**THE PATCH ORDER IS CHECKED, NEVER REPAIRED.** A measurement whose patches do
not line up with the chart is refused with an explanation. ChromIQ does **not**
re-pair it by matching device values, and this is deliberate (Basti,
2026-08-31, on measured evidence):

* `measurement_report.verify_patch_identity` cannot validate such a repair. It
  compares the chart's device values with the measurement's for each pairing —
  and a repair assigns the pairings by minimising exactly that difference, so
  it reports "verified" afterwards whether the repair was right or wrong.
  Measured: `mismatch, worst=100.0` before, `verified, worst=0.0001` after.
* A tolerant match — which a real implementation needs, because 23 of 240
  device values in ChromIQ's OWN demo chart differ from its measurement in the
  fourth decimal — can hand a reading to a patch **16.24 ΔE00 away** in design
  colour on real charts.
* The interchangeability rule ("patches asked to be the same colour may be
  swapped freely") holds for EXACT duplicates, measured on 22 of 24 real
  charts. It does not extend to tolerant neighbours.

A profiling run that **already holds a measurement** is not displaced. As for a
verification, the road to a second result is a new place to put it: ChromIQ
duplicates the run through `duplicate_run_plan` / `duplicate_run` and files the
import into the copy — **copying the CHART only**
(`groups=("chart",)`). Copying the whole run was driven on a real project and
made a run that contradicted itself: the copy carried the measurement, the
profile, `reads/`, `reports/` and a 153 KB export, every one of them orphaned
the moment the import overwrote the `.ti3` — while the confirmation window said
it was copying them for the person. Where `duplicate_source()` is `None` — the run has no
complete chart — the import is refused with the reason
`_duplicate_missing_phrase()` already writes.

**A calibration run still cannot import.** There is one `cal/` per project,
shared by every run, and `Calibration.reset()` has no `old/` archive
(`calibration_run_type.md` §3 D1), so an import there has no safe way to
displace what is present. This stays out until that defect is fixed — a
data-safety reason, not a preference.

**I.10 · A partial measurement is filed, not refused.** Withdrawn for both run
types. A measurement holding **fewer** readings than the chart has patches is
filed and the user is told **both counts** — M-IMPORT-PARTIAL-PROFILING or
M-IMPORT-PARTIAL-VERIFICATION. A measurement holding **more** readings than the
chart has patches is still refused (M-IMPORT-TOO-MANY): that is not a partial
measurement, it is a different chart.

**A file ChromIQ wrote must be a file ChromIQ will take back.** Its own real
verification read of 15 patches from a 105-patch chart could not be re-imported
by it.

**No threshold is set, and none may be added later without a measurement to
justify it.** Charts in use run from 64 to 2064 patches and quality falls off
with the absolute count, not the fraction, so any line drawn across it would be
arbitrary. ChromIQ states the counts and leaves the judgement with the person,
exactly as Build Profile already does.

**One measured caution for whoever implements this:** `colprof` builds silently
from as few as **4 patches** (exit 0, no warning), and its own self-check then
reports **0.016** — the best number in the table — for a profile **41.5 ΔE**
wrong against 924 real readings. The self-check is anti-correlated with quality
and must never be shown as reassurance. A missing **white** patch is a hard
failure (`rc=1`); a missing black one is not, so ChromIQ must not invent a
black-patch rule.

### ⏳ Awaiting confirmation — §I.11 / §I.12, a measurement with no device values

**Confirmed by:** *nobody yet.*

**Proposed 2026-09-12**, from a report by a user verifying a profile on beta 4.
The BEHAVIOUR is built and driven on screen; the RULES below contradict §I.5 and
§I.10 as they stand, so they are Knut's and Sebastian's to approve or reject
before any of this is treated as settled.

She printed a verification chart through her profile, read all 420 squares of it
on an i1iO in i1Profiler, exported CGATS, and met **M-IMPORT-MISMATCH** saying
*"the file could not be read as a measurement (No device RGB columns, only RGB
charts are supported.)"*. Her file is `SAMPLE_ID`, `SAMPLE_NAME` and 36 spectral
columns, and she is right about the tool: i1Profiler's measure tool reads a chart
it did not generate, so it has no colour space to express device values in and
*"won't let you select RGB data to be included in the export"*. `txt2ti3`
converts it without complaint, `spec2cie` gives it XYZ, and `colprof` would build
from it.

**I.11 · The pairing is keyed on the patch NAME when the file carries no device
values.** §I.5's patch-identity comparison pairs a measurement with its chart by
`SAMPLE_ID` and uses the DEVICE VALUES as the witness that the pairing is right.
For a file like hers `SAMPLE_ID` is only i1Profiler's reading order, and the
chart's is the design order, so pairing those two would hand every reading to the
wrong patch. Her NAMES are `A1 … T21`, which are exactly the chart's own
`SAMPLE_LOC` labels, because that is what the chart printed beside each square
and what she aimed the instrument at.

So where the measurement carries no device columns at all:

* every measured name must be one of the chart's, no name may be used twice, and
  a name the chart does not have is **refused** as a measurement of a different
  chart. Fewer names than the chart has is a partial, per §I.10, not a refusal;
* the chart then supplies the device values and its own row order, on the
  CONVERTED COPY and never on the user's file, so the filed `.ti3` is an
  ordinary ChromIQ measurement. It carries `CHROMIQ_DEVICE_FROM_CHART "<chart>"`
  so nothing later mistakes a value the chart supplied for one the instrument
  measured;
* the name check runs **before** the device values are written. Afterwards
  `verify_patch_identity` compares the chart's device values with a copy of
  themselves and answers "verified" whatever happened, which is exactly the
  self-validating trap §I rejected for the device-value repair;
* **this is not that repair.** Nothing here looks at a colour, so nothing here
  can be validated by the quantity it minimised. A name is exact: the chart
  issued it and printed it.

**What a name CANNOT settle, and who settles it instead.** Another chart laid out
the same way carries the same names, so a device-less measurement of a different
chart of identical shape would pass the name check. Measured on real files,
2026-09-12: the median ΔE00 of the true pairing against a shuffled one is 3.18
for a correct measurement of a chart and 1.04 for another chart's readings under
the same labels, which separates them cleanly on two samples, but a survey of the
16 measurement/chart pairs on this machine gives RIGHT ratios from 0.99 to 6.12
and WRONG ratios from 0.76 to 3.45. **The two distributions overlap, so no
colour-margin threshold is justified by the evidence, and none is set** (§I.10's
own rule). ChromIQ states what it can and cannot check and leaves the judgement
with the person who printed the sheet: **M-IMPORT-DEVICE-FROM-CHART**, Import it
or Cancel, shown only for a device-less file.

A measurement whose device columns are present but are NOT RGB (a CMYK or
n-colour file) was refused here until beta 7; §I.13 below now imports it into a
run whose chart has the same inks. "No device columns" and "the wrong device
columns" are still different files and different faults: a CMYK file never
takes the §I.11 name pairing.

**I.12 · The count is judged against the SHEET, not the design.** §I.10 says a
measurement holding more readings than the chart has patches is refused as a
different chart. A chart's last strip is filled out with rows that are not part
of the design, and the person reading the sheet reads them too, so her 408-patch
design printed as 420 squares gives a complete measurement of 420. Judged against
408 it was refused; the chart preview two inches away said 420.

So a chart now answers two questions with two numbers:

| number | what it is | what it decides |
|---|---|---|
| designed patches (`expected_patches`) | what the `.ti1` asked for | below it, the measurement is PARTIAL |
| sheet squares (`sheet_patches`) | what the `.ti2` prints, fill-up included | above it, it is a DIFFERENT CHART |

Between the two the measurement covers the whole design and is complete. The same
rule is applied by `measurement_state.classify`, so the state machine and both
import doors cannot disagree, and the import panel now names both numbers where
they differ instead of only the design.

**The verification door and the profiling door judge through one function.** The
Measure tab had its own copy of §I.5's rule; the profiling door learned to read a
spectral-only export on 2026-09-11 and this one still refused it the next
morning. Both now call `workflow.measurement_import.assess`. The one thing the
verification door still decides for itself is what to do with a SHORT
measurement: §I.10 files it on the profiling door, and §I as shipped refuses it
here, which is unchanged and still awaits its own §I.10 work.

### ⏳ Awaiting confirmation — §I.13, a CMYK or multi-ink measurement

**Confirmed by:** *nobody yet.*

**Approved in scope by Basti, 2026-10-03** (the CMYK/CR30 forum report):
*"yes, allow importing cmyk into a cmyk run"*, on every import path. The
behaviour below is built and driven on screen; the rules are written here for
Knut's and Sebastian's confirmation.

**I.13 · A measurement for other inks than RGB is judged with the N-channel
readers, by the same rules.** `parse_ti3` still refuses every non-RGB file and
`Ti3Data.has_device` still means RGB device values: thirty readers rely on the
refusal, and a CMYK file returned with `rgb` empty would read as device-less
and be sent down §I.11's name pairing, which writes the chart's device values
over the file's own. So `measurement_import.assess` asks first, with
`ti3_analysis.device_space_of`, and a non-RGB file goes to its own branch:

* it must carry XYZ or L*a*b* columns, or it is no measurement;
* its inks must be the chart's, compared colorant by colorant as
  `calibration.check_matches` compares a calibration with a chart. A CMYK file
  into an RGB run, an RGB file into a CMYK run and a CMYK+OG file into a CMYK
  run are refused: *"this measurement is {measured}, but the chart is
  {chart}, so it is a measurement of a different chart"*;
* the count rules are §I.10 and §I.12 unchanged: more readings than the sheet
  carries is a different chart, fewer than the design is a partial;
* identity is per `SAMPLE_ID`: every device value the chart has must equal the
  file's within `PATCH_IDENTITY_TOL` (`printer_calibration.device_values_differ`),
  or *"the measured device values do not agree with the chart's patches, so the
  readings do not line up with this chart"*. Nothing is re-paired (§I.9);
* it never takes the chart's device values (`device_from_chart` stays False).

Nothing in it is CMYK-specific, so every ink set targen writes is judged alike.
Every door goes through it: the Measure tab's IMPORT module for profiling and
verification runs, Build Profile's "Load measurement data" (`file_into_project`,
`make_new_project_and_file`) and Check & Refine's import. The i1Profiler CxF
converter (`cxf_measurement_to_ti3`) now writes `ColorCMYK` as `CMYK_*` columns
(percent, already Argyll's scale) beside `ColorRGB`; the `.txt` route has gone
through `txt2ti3`, which writes CMYK, all along. **A calibration run still
cannot import** (§I.9's data-safety reason is unchanged).

What a CMYK measurement is NOT yet: reported on. The Measurement Report, its
patch-identity line, the automatic report and the measurement details window
read RGB device values only, and each now shows **M-VIEW-RGB-ONLY** in place of
a parse error (§M-PROPOSED).

## S. Sequences — what happens, in what order, for every entry condition

**The rule this chapter exists to state: one window at a time.** Where a condition raises two, the second is not built until the first has returned. No window is ever opened from inside another's handler, and none is opened from a `showEvent` — a window raised while its parent is still being painted comes up behind it or over the wrong tab, which is how #134 and #130 both started.

Read each row top to bottom: that is the order the code must perform it in.

### S1 · Start Measurement

| # | Condition | Sequence |
|---|---|---|
| S1.1 | no chart loaded | 1 refuse, inline hint. No window. |
| S1.2 | Verification run type, run has no profile | 1 **M-VERIFY-NO-PROFILE** ✅ → 2 return. Nothing is written. Reachable when the run has a verification chart but no profile; otherwise met as the greyed Start button's tooltip. |
| S1.3 | Verification, profile exists, no verification chart | **M-VERIFY-NO-CHART** ✅, as the greyed Start button's tooltip — since beta.128 Start needs a `.ti2`, so this is met before a window can open. Knut, beta.128: *"Start Measurement button is not available, so test cannot be performed."* |
| S1.4 | no `.ti3` | 1 archive step (§2a) is a no-op → 2 record C₀ = 0 → 3 launch |
| S1.5 | `.ti3` partial, Resume ticked | 1 **archive `.ti3` → `old/{date}/`** → 2 record C₀ → 3 launch. No window. |
| S1.6 | `.ti3` partial, Resume **not** ticked | 1 **M-REPLACE-PARTIAL** → 2 *if cancelled, stop here* → 3 archive → 4 record C₀ → 5 launch |
| S1.7 | `.ti3` complete | 1 **M-REPLACE-COMPLETE** → 2 *if cancelled, stop* → 3 archive → 4 record C₀ → 5 launch. Resume is left exactly as the user set it. |
| S1.8 | `.ti3` corrupt (`B ≠ C`) or `C > A` | 1 **M-TI3-MISMATCH** → 2 *Cancel stops here* → 3 on "Start fresh": archive → 4 C₀ = 0 → 5 launch with Resume forced off |
| S1.9 | instrument cannot be opened | 1 launch → 2 detect init failure (§7) → 3 **Instrument Failed to Initialize** → 4 mark failed → 5 no `.ti3` written, archive untouched |

### S2 · During a measurement

| # | Condition | Sequence |
|---|---|---|
| S2.1 | patch/strip read OK | 1 record reading → 2 sound → 3 update preview. No window. |
| S2.2 | any failure window (§1a) | 1 **one** window → 2 its choice is sent to the reader → 3 nothing else opens until it returns |
| S2.3 | two failures in quick succession | 1 first window → 2 *closed* → 3 second window. Queued, never stacked. |
| S2.4 | user presses Stop, nothing read | 1 **M-END-EMPTY** → 2 end. No save prompt — there is nothing to save. |
| S2.5 | user presses Stop, readings exist | 1 **M-END** → 2 Save → graceful protocol per engine · Discard → abort · Keep → return, nothing changes |
| S2.6 | user presses `d` | identical to S2.5 — same window, same three buttons |
| S2.7 | user presses `Esc`/`q` | identical to S2.5 |
| S2.8 | bar / Tools / Preferences clicked | disabled for the duration; tooltip explains. No window. |
| S2.9 (beta.141) | the same failure arrives twice — once printed, once as an event (§7c) | 1 first arrival opens the window → 2 the second is recognised as the failure already reported and is **dropped**. A genuinely different failure still opens its own window |
| S2.10 (beta.141) | a second failure arrives while a window is open | 1 nothing stacks on top → 2 it waits, per S2.3. Enforced by the register, not by each window remembering to check |

### S3 · After a measurement ends

Always in this order, whatever ended it:

| # | Step | Then |
|---|---|---|
| S3.1 | read the resulting `.ti3` → B, C | — |
| S3.2 | C = 0 or no `BEGIN_DATA` | **M-TI3-EMPTY** → move to `old/`, restore the archived copy |
| S3.3 | C₀ > 0 and C < C₀ after a resume | **M-TI3-SHRANK** → restore the archived copy, keep both |
| S3.4 | `B ≠ C` | keep the file, never offer resume, report it |
| S3.5 | otherwise | keep; log "{C − C₀} patches added, {C} in the file" **on screen** |
| S3.6 | verification run | tag `CHROMIQ_VERIFICATION`, file under the dated folder |
| S3.7 | report | offer / refresh the measurement report |

Only **one** of S3.2, S3.3, S3.4, S3.5 can apply, so at most one window follows a measurement.

### S4 · Generate Chart / load a `.ti1` / auto-update

| # | Condition | Sequence |
|---|---|---|
| S4.1 | run empty | 1 generate. No window. |
| S4.2 | chart only | 1 generate, replacing it. No window. |
| S4.3 | chart + `.ti3` (+ profile), Profiling | 1 **M-CHART-PROFILING** → 2 *Cancel stops* → 3 if the chart has no recipe: **M-CHART-NOPAGES** → 4 *Cancel stops* → 5 archive → 6 generate |
| S4.4 | as S4.3 **and** dated verifications exist | 1 **M-CHART-PROFILING**, its `{items}` naming the verification measurements too → 2 *Cancel stops* → 3 M-CHART-NOPAGES if applicable → 4 archive run work **and** `verifications/` → 5 generate |
| S4.5 | Verification run type | 1 **M-CHART-VERIFY** → 2 *Cancel stops* → 3 archive the verification chart → 4 generate |
| S4.6 | any of the above, Duplicate unavailable | the recommendation carries **M-DUPLICATE-BLOCKED** — one window still, not two |
| S4.7 · **PROPOSED** | the typed project name resolves to a **different** project that exists on disk **and holds something** — in ANY of its runs (not only the current one), or its shared calibration | 1 **M-PROJECT-EXISTS**, listing every run and defaulting its picker to **a new run** → 2 *Cancel / Use a different name stops* → 3 Replace it → **M-PROJECT-REPLACE-CONFIRM** → *Go back stops* → archive the whole project into its `old/` and start a fresh one · Continue this project → adopt it, point the Profile-run bar at the run the picker names → 4 generate. For **Profiling**, S4.1–S4.4 do not also fire: M-PROJECT-EXISTS carries §4's answer for the run it names. For **Verification** and **Calibration** they DO — see below. When the project is EMPTY in every run, no window at all: only the line under the name box. |

S4.3 and S4.4 are the only place two windows can follow one action, and they are strictly sequential: the second is built after the first returns, and only if the first was accepted.

**S4.7 replaces S4.1–S4.4, and only those.** It describes the run's *profiling*
artefacts — a chart, a measurement, a profile — which is what M-CHART-PROFILING
would have said, so for a Profiling build one action still opens one window. It
knows nothing about the verification charts under `verifications/` or about the
calibration in `cal/`, so for **Run type = Verification** it does NOT stand in
for S4.5, and for **Run type = Calibration** it does not stand in for the
calibration question: the specific one follows it. That is a second window for
one action, and it is recorded here rather than left to be discovered.

**⏳ Awaiting confirmation.** Whether two windows are right for those two run
types, or whether M-PROJECT-EXISTS should instead grow a verification and a
calibration variant, is a decision about the model.
**Confirmed by:** *nobody yet.*

**Why S4.1–S4.5 could not answer this on their own.** They are all evaluated against *the run*, and until 4.1.3 they were evaluated **before** the typed name was applied — so when a name adopted a different project, the question was answered about the run the app happened to be on, not the one about to be written. S4.7 resolves the name first and asks about the project the build will really touch.

### S5 · Build Profile

| # | Condition | Sequence |
|---|---|---|
| S5.1 | target is a loaded file, not a run | 1 build. No window. |
| S5.2 | run has no profile, or no verification chart, or no dated measurements | 1 build. No window. |
| S5.3 | run has profile + verify chart + ≥ 1 dated measurement | 1 **M-PROFILE-VERIFY** → 2 Duplicate → duplicate, switch, build there · Build anyway → archive profile **and** `verifications/` → build · Cancel → nothing |
| S5.4 | as S5.3, "don't show again" set this session | 1 build. No window. |
| S5.5 | as S5.3, Duplicate unavailable | **M-DUPLICATE-BLOCKED** appended; the Duplicate button is not offered |


## T. Test plan

**Principle: every row of every table above is a test, and every button in every message is a test.** A specification that is not executable is a wish. The tables give the cases; this chapter says how each is proved.

### T1 · Unit — the decisions, with no UI

Pure functions, no Qt, milliseconds each.

| Group | Cases | Asserts |
|---|---|---|
| T1.1 `.ti3` state | every row of §3a: absent · header-only · `C=0` · `B≠C` · `0<C<A` · `C=A` · `C>A` | the classifier returns the right state for each |
| T1.2 session verdict | every row of §3b: the six C₀→C combinations × resume on/off | the right action: keep · restore · delete-and-restore |
| T1.3 chart validity | all eight rows of §4a | "is there a chart", "can pages be redrawn", "warn or not" |
| T1.4 which message | every row of §M-x | the case maps to the expected message ID |
| T1.5 counting | `.ti2` vs `.ti3` parsing: `NUMBER_OF_SETS` vs actual rows, missing `BEGIN_DATA`, trailing blank lines, CRLF | A, B, C read correctly from real files |
| T1.6 event detection | every row of §7, fed the **exact line from the Argyll source** | the right event fires, and *only* that one |
| T1.7 no false positives | near-miss lines: "Ready to read strip" must not match "strip read ok"; "Strip read failed" must not match either | nothing fires |

### T2 · Integration — the sequences

Driven through the real handlers with a stubbed reader, asserting the **order** of what happens.

| Group | Cases | Asserts |
|---|---|---|
| T2.1 start | every row of §S1 | the exact sequence, in order; nothing written when a guard stops it |
| T2.2 during | every row of §S2 | one window at a time; a second failure queues behind the first |
| T2.3 end | every row of §S3 | at most one window; the right file is on disk afterwards |
| T2.4 chart change | every row of §S4 | S4.3/S4.4 raise two windows **strictly sequentially**, second only if first accepted |
| T2.5 build | every row of §S5 | duplicate-and-build leaves the original untouched |
| T2.6 archive | every path that archives | the original is in `old/{date}/` and readable; **nothing is ever deleted** |
| T2.7 restore | S3.2 and S3.3 | the restored `.ti3` is byte-identical to the archived one |

### T3 · Windows — every message, every button

| Group | Cases | Asserts |
|---|---|---|
| T3.1 appearance | each message ID × each condition that raises it | it appears exactly when the tables say, and not otherwise |
| T3.2 text | each message | the placeholders are filled; no `{name}` reaches the screen; singular and plural both correct |
| T3.3 buttons | each button of each message | it performs the action the text promises — the text is the specification |
| T3.4 default button | each message | the **safe** choice is the default; nothing destructive is triggered by Return |
| T3.5 cancel | each message with a Cancel | disk is byte-identical before and after |
| T3.6 don't-show-again | M-PROFILE-VERIFY | suppressed for that run in that session; a new session shows it again |
| T3.7 never stacked | S2.3, S4.3, S4.4 | at no point are two of these windows open at once |

### T4 · Engine parity

| Group | Cases | Asserts |
|---|---|---|
| T4.1 both engines | every §S2 and §S3 row × {stock, ChromIQ} | the same windows, the same wording, the same `.ti3` outcome |
| T4.2 protocol | Save-and-stop on each engine | the right keys are sent — two `q` · `r`/`d`/`y` · `d`/`y` |
| T4.3 spotread | §9 | appends per patch; no ending window; the count is reported |
| T4.4 modes | strip · patch-by-patch · refine · single patch | each ending route behaves identically within a mode |

### T5 · What cannot be automated

Stated so it is not mistaken for coverage:

- **A real instrument.** Every test above uses recorded output. That the strings still match a live ColorMunki or i1 is checked by Knut's testing, which is why §7 cites the source lines — a wording change in a future Argyll shows up as a failing T1.6, not as a silent regression in the field.
- **Whether a warning reads well.** T3.2 proves the text is complete and correct; only a person can say whether it is understood.
- **Optical judgements** — the bar-icon alignment kind.

### T6 · Order of building

1. **T1** first: the decisions must be right before the sequences can be.
2. **T1.6** before any code changes to detection, using the exact source lines from §7 as fixtures.
3. **T2 and T3** alongside the implementation of each section, section by section.
4. **T4** last, once both engines follow the same path.

No section of this specification is implemented until its row in T1 and T3 is green.


## 8. Fixed in beta.123

| Your report | Cause | Fix |
|---|---|---|
| patch-by-patch Stop loses everything, no warning (row 4) | `_STRIP_OK_RE` matched only "Strip read OK"; stock prints "**Patch** read OK" in patch mode, so nothing was recorded as read and Stop went straight to the kill | the pattern matches both |
| "the instrument no longer responds" (row 14) | chartread exits **0** when it cannot open the device, so this read as success and the error window was never reached | init failure is a failure regardless of exit code; the window leads with "try again first", which your log shows working 16 s later |
| profile bar live mid-measurement | the bar consulted only its *tab* lock | bar, Duplicate, Tools, Preferences all lock; Help stays live |
| "Show the location being edited" OFF did nothing | closing Preferences refreshed a list of widgets the bar was not on | it is now |
| overlay / sounds / click-to-jump under stock chartread | keyed on "a `.ti3` exists" rather than the engine | hidden **and** switched off |
| messages naming Print and Measure for Open .ti2 | the button moved to the masthead | every message names the button and where it is |
| "Loaded chart…" after opening a file already in the project | no distinction between imported and opened-in-place | skipped when nothing was imported |
| Duplicate greyed with no reason | — | tooltip lists all four required files and names which are missing |
| log window too short | fixed 100 px | measured from the font: exactly 9 lines |

**Your two questions on this section, both checked in the code:**

- **"Is the '.ti3 exists' condition still there when the engine is ON?"** Yes — the rule is `show_overlay = has_ti3 and engine_selected`. The engine is a second condition, not a replacement.
- **"The strip label arrows must keep working for stock chartread."** They do, and they were never touched. The arrow follows `stripe_changed`, which stock emits from chartread's own "Ready to read strip pass B" line (`measure_manager.py:1009`) — a different path from the overlay, with no engine test anywhere in it.

## 9. Does any of this transfer to Read single patches (spotread)?

**Partly, and the difference is worth stating: `spotread` does not hold readings in memory.** ChromIQ appends each patch as it is read, so there is no cliff — pulling the plug loses at most the patch in progress. Rows 8/9 do not apply.

What *does* transfer:

| Idea | Transfers? | Why |
|---|---|---|
| One ending window | ➖ | nothing is at risk, so a confirmation would be noise |
| Say what happened, on screen | ✅ | "12 patches saved to …" — the same rule as §3 |
| Archive before starting (§2a) | ✅ | a spot session appends to an existing file, so the pre-session copy is exactly as valuable |
| C₀ → C (§3b) | ✅ | "12 patches added, 47 in the file now" is a true and useful sentence |
| Corrupt-file check (§3a) | ✅ | the file can be damaged by anything, not only by chartread |
| Complete-chart warning (§5) | ➖ | spot reading is not tied to a chart's patch count |

---


## 10. The patch outline in the live preview: red, and yellow (#182)

### Confirmed behaviour — three limits: a verification's own row, and 20 for a chart made with a pre-conditioning profile (beta 11)

*Amended by 10.11 (beta 17): the verification limit's default is 5 (Knut 6070058549), calibration charts have their own limit (default 95), and the strip test has its own box per chart type, off by default on verification charts (6084176226).*

**Confirmed by:** Knut, 2026-10-04, #182 [5983470377](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983470377), answers 1 and 2 to the questions of [5983075893](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983075893), for points 1 and 2, which amend 10.1 and point 1 of 10.8; Knut, 2026-10-04, [5983733592](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983733592), for point 3, whose RULING (what the help must explain) is his and whose WORDS are ours and have not been put to him.

1. **A verification judged against its profile has its own limit** (answer 1:
   *"yes, 10, and own threshold row for this in Preferences --> Measurements
   "Flag a patch when..."*). A third row under *"Flag a patch when its colour
   error reaches:"*, *on a verification judged against its profile*, default
   **ΔE 10**. It applies exactly when the expected colours are the run
   profile's prediction (10.8), whatever the chart file says; the strip
   outlier test stays off for it (10.8 point 3). A new key
   (`patch_read_warn_de_prediction`): nobody's earlier limit is carried into
   it. A verification that falls back to the chart's estimate takes the limit
   its chart file names, as before.
2. **The limit for a chart made with a pre-conditioning profile is ΔE 20** (answer 2: *"If your
   tests indicate 20, then use it."*), no longer ArgyllCMS's 30. Settings
   schema 26: a stored 30 is an echo of the old default (Preferences ▸ Save
   writes every key) and falls through to 20; any other value is the user's
   and is kept. Which charts this limit covers: those whose `.ti2` or `.ti1`
   carries `ACCURATE_EXPECTED_VALUES "true"`, which only ArgyllCMS targen
   writes, and only when it is given a pre-conditioning profile (`-c`):
   a chart made after "Use as pre-conditioning profile", or with Manual
   targen `-c`. A FROM PROFILE GAMUT chart (written by ChromIQ, not targen)
   never carries it.
   **The term** (Knut, 2026-10-04, #182
   [5984174575](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5984174575),
   *"do you mean charts where a pre-conditioning profile is specified? you
   should use proper terms for us to understand what you mean"*):
   these charts are called charts *made with a pre-conditioning profile*,
   in every user-facing text and in this document, never "made from a
   profile", which reads like FROM PROFILE GAMUT. Beta 11 corrected the
   Preferences row, its tooltip, the limits help and the hover card; the
   corrected words have not yet been put to Knut.
3. **The help says what the limits are for** (Knut, 2026-10-04, #182
   [5983733592](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983733592),
   after 5983725218: *"The help text must explain the purpose properly"*):
   the red outline catches misreads and asks for a re-read; it does not mark
   colours the printer cannot reproduce (yellow answers that). 95 stays for
   estimated charts because their expected colours are far from any print,
   with the strip check and the neighbour check (10.9) doing most of the
   misread hunting there; 20 and 10 are low
   because the expected colours are close to what the printer should print.
   One paragraph (`LIMITS_PURPOSE_HELP`), the same in Preferences ▸
   Measurement and the Measure tab's hover help. The ruling is Knut's; the
   words are ours. It names the strip check and the neighbour check by
   their boxes' own words ("Only flag a patch that stands out from its own
   strip", "Flag a patch that does not fit the patches nearest in colour by
   more than").

### ⏳ Awaiting confirmation — two limits, and the yellow outline

**Confirmed by:** *nobody yet.*

**Rulings it is built from:**

* Sebastian, #182 [5956560815](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5956560815):
  *"I confirm the proposals."* (proposals A and B of
  [5956305908](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5956305908)).
* Knut, #182 [5956552085](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5956552085),
  on A: *"the preferences --> measurement should have two values, one for each
  of the two cases, so a user may change them both, each default wired to the
  correct circumstance and chart when measuring."*
* Knut, #182 [5956831467](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5956831467),
  on B: *"if later strip reads come across similar colors ... then if those
  patches have larger error than those previously flagged for the same color
  range, then one should assume that these errors are not a misread and
  automatically flag these patches with yellow highlighting."*
* Knut, #182 [5961180259](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5961180259),
  and Sebastian, on the colour-range rule of
  [5961078418](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5961078418)
  (k10): *"Sounds ok... Confirm with Sebastian too."* (10.4).

**What was built** (`workflow/patch_flags.py`, `TabMeasure._patch_warn_limit`
/ `_judge_patch`, `ui/tiff_preview.py`):

**10.1 · Two limits.** Preferences ▸ Measurement, under *"Flag a patch when its
colour error reaches:"*, holds two numbers: *on a chart with estimated colours
(most charts)*, default **ΔE 95**, and *on a chart made with a pre-conditioning profile*,
default **ΔE 30** (ArgyllCMS chartread's `WERR_TH` and `ACC_WERR_TH`). The
chart decides: a `.ti2` with `ACCURATE_EXPECTED_VALUES "true"` uses the second.
ChromIQ's layout engine does not copy that keyword from the `.ti1` into the
`.ti2` (printtarg does), so when the `.ti2` is silent the chart's `.ti1` is
asked too. The keyword is read once per chart (path and modification time).
The strip-outlier option is unchanged and applies to both, except on a
verification chart judged against the run profile's prediction, which takes
the second limit and ignores the strip-outlier option (10.8, confirmed by
Knut).

**10.2 · Migration** (settings schema 25). A user who had moved the old single
limit away from 50 keeps that number as the estimated-chart limit; a stored
50, the old default 20, or nothing at all gives both new defaults. The old
schema-8 rule that reset any value above 50 is retired, because with a default
of 95 a raised value is a choice, not a mistake.

**10.3 · Yellow, confirmed.** A red patch read again (its strip re-read, or the
patch) whose new MEASURED colour lies within ΔE*ab 3 of the previous reading,
and which is still past the limit, is outlined in yellow. The hover card says,
set apart at the bottom: *"Yellow outline: confirmed by a re-read"*, the two
ΔE values, *"A real difference this printer and paper cannot reach, not a
misread. Keep it for the profile."* A reading repainted from the file is
remembered as the previous reading but cannot confirm (a file read twice is
not a second reading), so re-reading a strip measured in an earlier session
still confirms. The repaint judges each patch exactly as it was judged live
(10.6), so a patch that was red is remembered as red.

**10.4 · Yellow, learned, within a colour range (#182 k10).** Built from
the rule posted in
[5961078418](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5961078418)
and confirmed by Knut
([5961180259](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5961180259):
*"Sounds ok... Confirm with Sebastian too."*) and by Sebastian. The behaviour
below is the build of that rule and awaits confirmation as built.

* **Thirteen colour ranges.** On an RGB chart (every chart whose `.ti2`
  device columns are RGB, charts made with a pre-conditioning profile included) from each
  patch's RGB numbers read as sRGB, as the confirmed block below states. On
  any other chart (CMYK, grey, N-channel, or a `.ti2` without RGB columns)
  from each patch's EXPECTED colour classified against the chart's own white
  (`APPROX_WHITE_POINT` of the `.ti2`, read once per chart with the accurate
  flag; D50 when it is missing, unparsable or has no positive Y). Then: a grey
  when its chroma C\* is under 8 (dark under L\* 35, mid from 35 to under 70,
  light from 70); otherwise by hue angle: red 15° to 50°, orange/brown 50° to
  75°, yellow 75° to 110°, yellow-green 110° to 130°, green 130° to 165°,
  cyan/turquoise 165° to 240°, blue 240° to 315°, purple/violet 315° to 325°,
  magenta 325° to 345°, and pink/rose everything else (345° to 15°). Each
  lower edge belongs to its range.
* **A range learns** once it holds three CONFIRMED patches (10.3) whose
  expected colours lie pairwise at least ΔE\*ab 6 apart (D50 L\*a\*b\*; the
  largest such set is counted exactly). Learned patches never count; a
  confirmed patch read again clean, or to a clearly different colour, drops
  out of the count.
* **Then** a red patch of that range turns yellow when, against a confirmed
  patch of the same range, its measured-minus-expected shift strays at most
  ΔE 10 sideways and is no more than ΔE 10 shorter along it, and, reading
  strips, it stands above its strip's median by no more than ΔE 10 more than
  the confirmed patch did (patch by patch there is no strip, and this last
  condition is not applied). The card names the closest such patch by
  expected colour, ties by location.
  **There is no upper bound:** a patch much further off than the confirmed
  one still turns yellow. Knut ruled this on 2026-10-03, #182
  [5963044182](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963044182):
  *"Use "(a) Any error at least as large as the confirmed patch turns
  yellow""* (the rest of 10.4 still awaits confirmation).
* **Both directions, after every batch** (a strip, a patch, a repaint from
  the file): every flagged patch is judged again, so a range that has just
  learned turns EARLIER red patches of it yellow, and a range that loses a
  confirmation turns its learned patches red again. A confirmed patch stays
  yellow whether or not its range has learned.
* **The card** shows the range on a line of its own; a red card in a range
  with one or two spaced confirmations says *"{k} of 3 spaced confirmations
  so far"*; a learned card lists the range's confirmed patches. The wording
  is M-PATCH-COLOUR-RANGE, in §M-PROPOSED.

A completely new read starts with no references; a read that resumes or
refines a measurement, and the preview of a measurement on disk, take that
measurement's stored references back (10.7). Loading another chart starts
from that chart's own.

#### Confirmed behaviour — purple merged into blue (beta 11)

**Confirmed by:** Knut, 2026-10-04, #182 [5983470377](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983470377), answer 4 (*"Merge purple into blue?: Answer: Yes"*). Only this point; it amends point 2 of the block below.

* **There is no purple/violet range any more: blue runs from 240° to 325°.**
  Magenta (325° to 345°) stays. Twelve ranges, not thirteen. Built:
  `workflow/patch_flags.HUE_SECTORS`; the name "purple/violet" is gone from
  the card and the catalogues. A stored confirmed patch is classified again
  when it is loaded (10.7), so a former purple one counts for blue.
  Re-measured on Knut's charts (copies; every red patch re-read in reading
  order): 24 of 648, 82 of 1944 and 7 of 324 patches change range; at limit
  50 the re-reads fall 16 → 14, 20 → 15 and 12 → 10, and no patch is left
  red either way (`workflow/patch_flags.py` docstring).

#### Confirmed behaviour — the colour ranges of an RGB chart, and the blue/purple edge (k10)

**Confirmed by:** Knut, 2026-10-03, #182 [5963411325](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963411325) (*"do the recommended for all three"*, answering the three questions of [5963152271](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963152271)). Only these three points; the rest of 10.4 still awaits confirmation.

1. **An RGB chart's ranges come from its RGB numbers read as sRGB**, for every
   RGB chart including charts made with a pre-conditioning profile; CMYK and other charts keep
   the expected-colour rule. As built: the device RGB of the `.ti2` goes
   through ArgyllCMS targen's own no-profile estimate (3.5.0,
   `xicc/xcolorants.c`: sRGB curve and primaries, normalised to Y = 1, a flat
   flare of 0.01 added to X, Y and Z), and the L\*a\*b\* is taken against
   that estimate's own white (95.106 / 100 / 108.844); then the grey and hue
   rules above. The choice is made per chart, never per patch. Values on a
   0..255 scale are brought to 0..100. A chart carrying a printer calibration
   takes its device values from its `.ti1` (a layout-engine chart printed
   with `-K` before 4.3.3-beta.5 holds calibrated values in its `.ti2`).
   Stored confirmed patches are classified again when they are loaded.
2. **The blue/purple edge moves from 310° to 315°**: blue 240° to 315°,
   purple/violet 315° to 325°.
3. **The yellow-green/green edge stays at 130°.**

Unchanged, as Knut's question stated: three confirmations ΔE 6 apart and the
"closest" patch are measured on the EXPECTED colours (D50), the shift and
stand-out conditions, the 13 range names, and the greys.

> **Superseded (beta 9, confirmed 2026-10-04):** the words *"three
> confirmations ΔE 6 apart"* above no longer describe the build. Knut
> [5979886227](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979886227) asked whether the ΔE 6 distance "is at all necessary or has value";
> the analysis (10.4a) found it has none, and the spacing is removed. Knut
> CONFIRMED dropping it in [5982038838](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982038838) (answer 3), see *Confirmed behaviour: no ΔE 6
> spacing* below. The rest of the confirmed block stands.

**10.5 · No longer suggested for re-reading.** The only place the app itself
suggests re-reading a flagged patch is the per-patch "Patch reading looks off"
sound (patch-by-patch mode); a yellow patch plays the ordinary patch sound.
Check & Refine's strips come from the profile check, not from these outlines,
and the outlines have no influence on them at all (§11, *the purpose of Check
& Refine*, confirmed by Knut on 2026-10-04, [5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281)).

**Measured on Knut's beta-3 run1** (648 patches, estimated colours, chart
white D65; scripts in the session reports `AF_impl_flag_limits/`,
`AP_colour_ranges/knut_colour_ranges_measure.py` and
`2026-10-03_srgb_ranges/knut_srgb_ranges_replay.py`): ΔE ≥ 50 flags 72
patches, ΔE ≥ 95 flags 10. Re-reading every red patch in reading order:

| rule | at ΔE 95 | at ΔE 50 (61 red) |
|---|---|---|
| expected colour, edge 310° (before 5963411325) | 10 re-read, 0 learned: O9 (RGB 50 0 100, hue 311°) is purple | 19 re-read, 42 learned |
| RGB numbers as sRGB, edge 315° (as built) | 9 re-read, 1 learned: all ten are blue, the triple A23, O9, U4 teaches the range and U16 is learned | 18 re-read, 43 learned |

18 of the chart's 648 patches change range between the two rules: 8 purple
to blue at the moved edge, and the rest near-greys and edges where targen's
flat flare differs slightly from the 1 % D65 flare ChromIQ's own `.ti2`
writer uses.

**Open questions for Knut:** whether the layout engine should write
`ACCURATE_EXPECTED_VALUES` into the `.ti2` as printtarg does (that would also
move the engine's own "Unexpected Colour Response" window to ΔE 30 for such
charts); the question whether a learned range should also turn EARLIER red patches
of it yellow is answered by 10.4: it does, and back again.


### ⏳ Awaiting confirmation — similar patches confirm each other (beta 9)

**Confirmed by:** *nobody yet.*

**Ruling it is built from:** Knut, #182 [5979886227](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5979886227): *"When separate similar
patches get the same reading, then that should count as a confirmation too
... three of these confirmations of separate patches with similar colors is
enough to learn that the color group has trouble with being reproduced by the
printer."*, *"re-categorise all highlighted patches on the fly"*, *"lowering
the thresholds in the preferences --> measurements would change which patches
are highlighted red or yellow"*, and *"advise if the 6 dE distance is at all
necessary or has value ... Make the change."* Built as variant B of the k22
challenge (`2026-10-04_beta9/k22_challenge/CHALLENGE.md` of that session's
report). Two choices in it were ours and were put to Knut in [5980331169](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980331169):
**"different strips"** (not in his words), CONFIRMED by him and moved to the
confirmed block below, and **Check & Refine leaving these patches out**
(10.5a), which he answered NO. The rule itself, 10.3a, was CONFIRMED by
Knut in [5983752160](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983752160) and is in the confirmed block below; the rest of
this block (10.4a apart from the spacing, 10.4b, 10.3b, 10.7a) still waits.

**10.3a · Yellow, confirmed by similar patches** (adds to 10.3): CONFIRMED
by Knut on 2026-10-04 (5983752160) and moved to the confirmed block *"similar
patches confirm each other (10.3a)"* below.

**10.4a · Learning without spacing** (replaces the spacing in 10.4). A range
learns once **three** of its patches are confirmed, by a re-read or by
similar patches, in any mix. There is **no ΔE 6 spacing** between them any
more: similar patches lie closer than ΔE 6 by definition, so a spacing would
count every group of them as one, which is what Knut called wrong (the four
magenta corner patches of his 1944-patch chart, all within ΔE 4.7). The
protection the spacing was meant to give is the shift and stand-out test of
10.4, unchanged. Learned patches are judged by it against every confirmed
patch of the range (re-read and similar). **A learned patch never confirms
anything**: similar patches are found from the raw flagged readings only,
never from a verdict.

**10.4b · On the fly.** Similar patches are worked out again from the readings
on hand and the CURRENT limit every time the outlines are judged: after every
strip and patch during a measurement, at its end, whenever the measurement is
painted from disk, when Preferences closes with OK, and when the Measure tab is
shown (the last two while the overlay box is ticked and no measurement runs).
Lowering a limit can therefore add a partner and turn a pair yellow; raising
it turns them back.

**10.3b · A re-read confirmation is not lost by raising the limit** (a defect
found with this change). A repaint at a higher limit used to judge a
re-read-confirmed patch clean and drop its confirmation; at the start of a
resumed read that loss was then written into the memory file. Now only a LIVE
reading (clean, or a clearly different colour) drops it. While the limit hides
it, it teaches its range nothing; lowering the limit shows it again.

**10.7a · The memory file** (adds to 10.7). Patches confirmed by similar
patches are written as `peer`, with the patches they agree with
(`{"kind": "peer", "with": [..]}`), as the session judged them. They are
never loaded back as references; they are worked out again from the readings.
Re-read confirmations are written whether the limit shows them or not. When
the outlines are judged again from disk on Preferences OK or on showing the
Measure tab (10.4b), the file is rewritten if it changed, so its `peer`
entries follow the CURRENT limit, never the limit of the session that wrote
them (k22 review). Check & Refine does not read the file ([5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281)).

**10.5a · Check & Refine: answered NO, and withdrawn.** Beta 9 as first built
left out patches confirmed by similar patches as well as those a re-read
confirmed. Knut answered question 2 of [5980331169](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980331169) in [5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281): *"No, for Check & Refine
we already agreed that confirmed or non-confirmed high-error patches has no
influence"*. Check & Refine now reads no confirmations at all, neither kind,
and the switch `CHECK_REFINE_LEAVES_OUT_PEERS` is gone: see §11, *the purpose
of Check & Refine*, and the reversal of CR-9.

**Measured** (k22 challenge, Knut's beta-8 data, no re-reads unless stated;
red / yellow confirmed / yellow learned):

| chart, limit | before, with Knut's re-reads | before, none | built |
|---|---|---|---|
| 1944 patches, ΔE 95 (18 flagged) | 0 / 10 / 8 | 18 / 0 / 0 | 0 / 18 / 0 |
| 1944 patches, ΔE 50 (129) | 61 / 27 / 41 | 129 / 0 / 0 | 10 / 87 / 32 |
| run 4, 324 patches, ΔE 50 (31) | 28 / 3 / 0 | 31 / 0 / 0 | 23 / 4 / 4 |

Simulated misreads (40 trials per fault): out of step, wrong strip and smudge
were never confirmed by similar patches; the few that ended yellow were
LEARNED through 10.4's existing test, at its measured rate.

#### Confirmed behaviour — similar patches confirm each other (10.3a)

**Confirmed by:** Knut, 2026-10-04, 5983752160 (#182 [5983752160](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983752160): *"Yes. Beta 10 seems to work nicely with that."*, answering our question after [5983725218](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983725218)). Only the rule below, as built; 10.4a (apart from the spacing, confirmed separately), 10.4b, 10.3b and 10.7a still await confirmation above.

**10.3a · Yellow, confirmed by similar patches** (adds to 10.3). Two FLAGGED
patches (past the limit and, reading strips with the strip test on, outliers
of their strip) confirm each other when:

* they were read in **different strips** (confirmed by Knut, see the block
  below);
* their **expected colours** are less than ΔE\*ab 6 apart (D50, Knut's own
  "<6 dE");
* their **errors** (measured minus expected) are within ΔE\*ab 10 of each
  other (the "off in the same way" tolerance of 10.4).

Both are drawn in the same yellow as a re-read. The card says *"Yellow
outline: confirmed by similar patches"* and *"Read alike in other strips:
{locs}"* (M-PATCH-COLOUR-RANGE; these two lines CONFIRMED, see below). A re-read confirmation still exists beside
it and is named first; it is the only route for a colour with no similar
patch.

#### Confirmed behaviour: no ΔE 6 spacing between a range's confirmations (10.4a)

**Confirmed by:** Knut, 2026-10-04, 5982038838 (#182 [5982038838](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982038838), answer 3: *"confirmed."*). Only the spacing; the rest of 10.4a still awaits confirmation above.

* A range learns once three of its patches are confirmed, with **no ΔE 6
  spacing** between them: confirmed patches of nearly the same colour each
  count.

#### Confirmed behaviour: the card lines of similar patches and of what to do (10.3a, help)

**Confirmed by:** Knut, 2026-10-04, 5982038838 (#182 [5982038838](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982038838), answers 1 and 2: *"OK"*, *"Ok"*). Only these lines.

* A card confirmed by similar patches says *"Yellow outline: confirmed by
  similar patches"* and *"Read alike in other strips: {locs}"*.
* A red card says *"Read it again to find out."*, every yellow card (re-read,
  similar patches, learned) *"No need to read it again."*

#### Confirmed behaviour — similar patches confirm each other only across different strips (10.3a)

**Confirmed by:** Knut, 2026-10-04, #182 [5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281) (question 1 of [5980331169](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980331169): *"Ok"*). Only this condition; the rest of 10.3a, 10.4a, 10.4b, 10.3b and 10.7a still await confirmation above.

* Two flagged patches confirm each other only when they were read in
  **different strips**. One strip is one pass of the reader, and a smudge or a
  slipped strip can make several patches of ONE strip wrong in the same way
  (in the k22 test, without this condition 4 of 24 smudged patches turned
  yellow, with it none did). Patch by patch and a whole chart read at once use
  the same strip labels. On Knut's run 4 it leaves F11 and F14 red.

### ⏳ Awaiting confirmation — the help tells red and yellow apart (beta 9)

**Confirmed by:** *nobody yet.*

**Ruling it is built from:** Knut, #182 [5980576263](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980576263): *"make sure all help text and
the hover-over text during measurements is written so the user understands the
difference between the red and yellow highlighting."* The request is his; the
words are ours.

* **Red** is said everywhere as: the reading is far from the colour the chart
  expects, it may be a misread, read it again. **Yellow** as: the difference
  is real (a re-read gave the same colour, similar patches in other strips are
  off in the same way, or the colour range has learned that the printer
  struggles there), keep it, there is no need to read it again.
* Where: the help of "Show overlay from existing measurement" (Guided and
  Manual), of "Each patch shows", of "Show patch values on hover" (its yellow
  paragraph rewritten: the retired "at least ΔE 6 apart" is gone and similar
  patches are named), Preferences ▸ Measurement's "Patch-reading error limits"
  (its YELLOW OUTLINE section, which still described the ΔE 6 spacing, is now
  RED AND YELLOW), the Getting started card "3. Measure", the threshold help of
  Check & Refine (Guided and Manual), and the file guide's line for
  `<stem>.confirmed.json`.
* The help says what the limits do, that the outlines are worked out again
  after every strip or patch, at the end of a measurement, on coming back to
  the Measure tab and on Preferences OK (10.4b), that a re-read confirmation is
  never lost by raising the limit (10.3b), and that **Check & Refine judges on
  its own** (§11).
* **The hover cards** get one line each: a red card *"Read it again to find
  out."*, every yellow card (re-read, similar patches, learned) *"No need to
  read it again."* (M-PATCH-COLOUR-RANGE; CONFIRMED by Knut in 5982038838,
  see the confirmed block above).

### ⏳ Awaiting confirmation — a red card in a learned range says why (beta 10)

**Confirmed by:** *nobody yet.*

**Ruling it is built from:** Knut, #182 [5982206917](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982206917), answer 1 (*"Ok"*) to question 1 of [5982058944](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982058944), which answered his O7 question in [5982038838](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982038838) (*"What does it mean 'but this one is off in a different way'? How different?"*).

* **10.4c · The card names the failed test.** A red patch whose range has
  learned is compared with every confirmed patch of its range by the three
  tests of 10.4. Its card names the test that ruled it out and the numbers,
  instead of *"one is off in a different way."*: its error is **smaller**
  (along the confirmed patch's error, more than ΔE 10 short), it **points
  another way** (more than ΔE 10 sideways), or it **stands out from its
  strip more** (more than ΔE 10 above the confirmed patch's own standing-out).
  When no single test rules out every confirmed patch, the fewest tests that
  together do are named, the one ruling out most first. Wording:
  M-PATCH-COLOUR-RANGE lines 14 to 27 (§M-PROPOSED).
* Reporting only: no outline changes. The judge (`FlagJudge._misfit`) works
  the reasons out only for a patch it has already judged red.
* **The size test stays, with a waiver** (question 2 of 5982058944,
  consequences in [5982217410](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982217410); Knut kept it and approved the waiver in
  [5982600086](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982600086), see *Confirmed behaviour: the size test is waived when the
  reading lands with its confirmed patches' readings* below). A "smaller"
  reason is now only given when the reading also did not land within ΔE 15
  of the confirmed patches' readings, and the card says so with those
  distances: M-PATCH-COLOUR-RANGE lines 16, 28 and 29 (§M-PROPOSED).
* Measured on Knut's 1944-patch run1 with his re-reads: at limit 60 the four
  red patches of learned ranges (J25, O7, BG5 purple, Y27 magenta) all say
  "smaller" (O7: ΔE 63.8 to 64.3 here, ΔE 74.8 to 92.4 on its confirmed
  patches: one decimal, because it misses one of them by less than ΔE 1); at
  limit 50, eight of the ten red patches are in learned ranges, seven say
  "smaller" and AW21 (green) says "another way: ΔE 15 to 27 sideways"; at
  limit 40, fourteen of nineteen, six of them with two reasons (BC13:
  "smaller" on some, "another way" on the rest). Re-measured in the beta-10
  review by replaying the run through `FlagJudge` at 95, 60, 50 and 40: not
  one outline differs from beta 9. (These are the numbers BEFORE the waiver
  below, which turns O7, J25, BG5 and Y27 yellow.)

#### Confirmed behaviour: the size test is waived when the reading lands with its confirmed patches' readings (10.4d)

**Confirmed by:** Knut, 2026-10-04, 5982600086 (#182 [5982600086](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982600086): *"Ok"* to the question of [5982339631](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5982339631), "use this variant (keep the size test, waived when the reading lands within ΔE 15 of a confirmed patch's reading) instead of dropping the size test?"). Only this rule; the card's words for it stay in §M-PROPOSED.

* In a learned range, the "as large or larger" test of 10.4 (no more than
  ΔE 10 shorter along a confirmed patch's error) **stays**, and is **waived**
  for a confirmed patch when this patch's **measured** L\*a\*b\* is within
  **ΔE\*ab 15** of that confirmed patch's **measured** L\*a\*b\*
  (`LANDING_DE`, `workflow/patch_flags.py`). A printer that cannot reach a
  colour lands its readings at the same place, its limit, so a less vivid
  colour asked for has a shorter error and the same reading; a misread lands
  somewhere else.
* The other two tests, **the same direction** (at most ΔE 10 sideways) and
  **not standing out from its strip** more than ΔE 10 more than the
  confirmed patch did, are unchanged and still apply.
* Measured on Knut's 1944-patch run1 with his re-reads, replayed through the
  built `FlagJudge` (`2026-10-04_beta10/landing/replay/` of that session's
  notes): red **4 → 0** at limit 60 (O7, J25, BG5, Y27 turn yellow),
  **10 → 3** at 50, **19 → 6** at 40; nothing changes at 95. Injected misreads
  (out of step, wrong strip, smudge over 5 patches; 40 trials each, no
  re-reads, limits 60 and 50): **not one more** turns yellow than without the
  waiver in any of the six cases.

#### Confirmed behaviour: a verification card speaks of the profile, not of what the printer cannot reach (10.8a, beta 10)

**Confirmed by:** Knut, 2026-10-04, 5982788316 (#203 [5982788316](https://github.com/itsab1989/ChromIQ/issues/203#issuecomment-5982788316): *"your rewording is OK."*, to the wording proposed in [5982715730](https://github.com/itsab1989/ChromIQ/issues/203#issuecomment-5982715730)). Only the card's wording on such a verification; his second point in that comment (the default limit for a verification judged against its profile) is a separate question and changes nothing here.

**Ruling it is built from:** Knut, #203 [5982702169](https://github.com/itsab1989/ChromIQ/issues/203#issuecomment-5982702169): *"for a verification chart where the colors have been selected from profile's gamut, all the colors are within gamut ... the measurement is a check of the profiles accuracy, is it not? ... not a highlighting of patches that the printer cannot reach"*.

* **10.8a · The card of a verification judged against the profile's
  prediction** (10.8) never says "a colour this printer and paper cannot
  reach" or "keep it for the profile": a real difference there means the
  profile is inaccurate at that colour (or the printer has changed since the
  profile was made), and a verification never goes into a profile. Red: *"Far
  from what the profile predicts. Either a misread, or a place where the
  profile is inaccurate. Read it again to find out."*, and after "Same value
  after a re-read:" *"it is real, and counts against the profile's
  accuracy."* Yellow (re-read or similar patches): *"A real difference, not a
  misread: the profile does not predict this colour well here (or the printer
  has changed since the profile was made). No need to read it again."* A
  learned card: *"The profile is off in the same way here, so it is taken as
  real too."* Wording: M-PATCH-COLOUR-RANGE lines 32 to 41 (§M-PROPOSED).
* The outlines themselves do not change, and a profiling card is unchanged.

### ⏳ Awaiting confirmation — the preview after a measurement shows what it showed during it (K3)

**Confirmed by:** *nobody yet.*

**Ruling it is built from:** Knut, #182
[5959352118](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5959352118):
*"the highlighted large errors shown during a measurement is no longer visible
[after it is stopped]. ... If no good reason, maybe this should be
implemented?"*; answered as a bug in
[5959399054](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5959399054).

**10.6 · The same numbers and the same outlines.** When the preview is painted
from a measurement on disk (after a session, on reopening a project, on
switching run, run type or tab and back, and at the start of a resumed read),
each patch is compared exactly as it was compared during the read: the
chart's expected XYZ as the `.ti2` holds it (no rescaling, no white-point
adaptation), or, on a verification chart judged against the run profile's
prediction (10.8), that prediction, worked out the same way and replaced by
the same function as during the read (`workflow/verify_expected.py::apply_expected`);
the measured XYZ from the `.ti3`; both turned into L\*a\*b\* against
ArgyllCMS's D50 after dividing by 100, and their ΔE\*ab (CIE76)
(`workflow/measurement_report.py::per_patch_overlay`, `engine_patch_de`). It used to use the Measurement Report's figures (D65 to D50
adapted expected values and ΔE2000): Knut's A23 read ΔE\*ab 103.2 live and
16.1 afterwards, so every red outline vanished at the end of a measurement.
The Measurement Report itself is unchanged. For a measurement read in strips,
each patch is also judged against its own strip as during the read (the strip
test when it is switched on, and the stand-out figure of 10.4); patch by patch,
and for a whole chart or sheet read at once (XY / chart instruments), there is
no strip test, as before. The `.ti3` does not record how it was read:
the stored memory (10.7) does, and without one the patch-by-patch setting on
the panel decides.

### ⏳ Awaiting confirmation — the confirmed patches are kept with the measurement (K4)

**Confirmed by:** *nobody yet.*

**Rulings it is built from:** Knut, #182
[5959352118](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5959352118):
*"the information on which patches were re-measured and confirmed as not to be
misreadings are remembered after a measurement is stopped, which must anyway
be remembered for the Check & Refine function"*; approved by Sebastian
([5959447807](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5959447807)).

**10.7 · `<stem>.confirmed.json`.** Beside the `.ti3` it describes
(`runs/runN/<stem>.confirmed.json`, and
`verifications/<date>/<stem>-verify.confirmed.json`), written atomically after
every change during a session and once more at its end, when the `.ti3` is
final (`workflow/confirmed_patches.py`). It holds the `.ti3`'s SHA-256, how it
was read (`strip` or `patch`) and, per patch, either `confirmed` (with the
readings that confirmed it) or `learned` (and which confirmed patch it was
judged like). It is believed only while the `.ti3` is byte for byte the one it
names; otherwise it is ignored. Only `confirmed` patches are loaded back as
references; learned ones are judged again from them. A file written before
the colour ranges (4.3.3 beta 5) may name, as a learned patch's `like`, a
confirmed patch of another range; it is never read back, so it changes
nothing.

* A completely new read moves it to `old/` with the measurement it described,
  and starts with none; a session that read nothing puts both back.
* A resumed or refined read starts with it (a resumed verification, with its
  dated file's).
* "Measure again to average": the averaged measurement, and a read kept with
  "Use last read only", get the memory of the last session. `merged.ti3` and
  `reads/readN.ti3` get none.
* A verification carries it when ChromIQ marks and files the reading
  (`<stem>-verify.ti3`), re-stamped for the marked file.
* Duplicating a run copies it with the measurement; renaming the project
  renames it; Restore Used Chart leaves it alone. Older projects have none,
  and nothing is migrated.
* `confirmed_locations(ti3)` gives the patches the memory records as
  confirmed (a re-read, or similar patches, `peer`). **Check & Refine never
  reads it** (Knut, [5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281)); the file is the Measure tab's memory only.

The help text of the patch outline says so instead of *"A new measurement
session starts without yellow patches"*.

**Open questions for Knut:** (a) the engine's own ΔE during a read uses the
`.ti2` XYZ as written; on a chart whose `.ti2` holds XYZ on a 0..1 scale (some
printtarg charts) the expected colours are then 100 times too dark and every
patch is far off, live and now afterwards alike. Should the engine scale such
a chart as the Measurement Report does? (b) *Answered* by Knut on 2026-10-04
([5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281)): Check & Refine leaves out none of them, confirmed, peer or learned.

### 10.8 · The expected colour of a verification chart: the profile's prediction (#182)

#### Confirmed behaviour — what is compared with what, on a verification chart ChromIQ printed

**Confirmed by:** Knut, 2026-10-03, #182 [5964173774](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5964173774) / [5964384250](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5964384250), answering the five questions of [5963902307](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963902307). Only these points:

1. **The rule** (question 1, *"Yes."*). While a verification chart printed by
   ChromIQ is measured, each patch is compared with the run profile's
   prediction of the ink values that were really printed (raw or through the
   profile, any intent), at ΔE 30, the limit for a chart made with a pre-conditioning profile.
   Today's sRGB estimate at ΔE 95 is the fallback. Charts printed outside
   ChromIQ, and runs without a profile, keep today's rule.
2. **Another light** (question 2, *"Yes."*). The fallback is also taken when
   the profile was built with an illuminant other than D50, another observer,
   or FWA compensation.
3. **The strip outlier test** (question 3, *"yes"*, 5964384250: *"should
   ChromIQ ignore this setting and outline every patch above 30, even if the
   whole strip is off? yes."*). On these charts the setting is ignored and
   every patch at or above the limit is outlined. It stays the user's setting
   for every other chart.
4. **The hover card** (question 4, *"Yes."*) shows that the expected colour
   is the profile's prediction. The words are M-PATCH-EXPECTED-PREDICTED, in
   §M-PROPOSED.
5. **The measuring engine's own warning window** (question 5) is left for
   later: *"yes leave for later. Sebastian to decide later."*

The Measurement Report is not part of this: it keeps its own references.

#### Confirmed behaviour — the card when the profile is newer than the print

**Confirmed by:** Knut, 2026-10-04, #182 [5983480953](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983480953) (*"OK"*). Only this point:

6. **A verification whose profile was made, or changed, after the sheet was
   printed** falls back to the chart's estimate (below), and its red card
   says so instead of the profiling wording that ends "keep it for the
   profile": *"Far from the chart's estimate. The profile was made after this
   sheet was printed, so its prediction is not used. Either a misread, or a
   real difference: read it again to find out."* (M-PATCH-COLOUR-RANGE lines
   42 to 47). Its other lines (48 to 51) are ours and wait in §M-PROPOSED.
   Built: `verify_expected.LiveExpected.profile_newer`, set by the two
   "the profile changed since printing" fallbacks; the card's
   `expected_source` is then `"estimate_profile_newer"`.

#### ⏳ Awaiting confirmation — how 10.8 was built (phase 1)

**Confirmed by:** *nobody yet.*

Python only: no engine change, no change to the `.ti2`, nothing new written at
print time (the challenge of 2026-10-03). The engine still compares with the
`.ti2`; ChromIQ replaces the expected colour of every patch event and works
out the ΔE again with `engine_patch_de` (`workflow/verify_expected.py`).

* **When.** At the start of a verification read (before the overlay of a
  resumed read is painted), and whenever a verification measurement is
  painted from disk (10.6), for that measurement's own print record
  (`verification_print.read_print_record`: a dated verification's `chart/`
  snapshot first; a resumed read uses the dated folder it resumes). Worked
  out once per chart, profile and record, and kept for the session.
* **What was sent**, from the print record (A15 to A18, B7):

  | Record | Values predicted |
  |---|---|
  | raw | the `.ti2` RGB (0..255 charts brought to 0..100) |
  | through the profile | `cctiff -p -f T -i <intent> <recorded source profile> -i <intent> <run profile>` (`cctiff_apply.convert_args`) on one row of the chart's RGB at the page images' bit depth; never the `.ti2` RGB |
  | through, `-K` profiling chart, calibration applied with the SHA-1 of the run's own | the cctiff output BEFORE the calibration (the profile describes the printer behind it) |
  | through, a calibration applied that the profile was not built with, still readable at its recorded source with the recorded SHA-1 | the cctiff output with that calibration (the values sent) |
  | raw, verification chart printed with `-K` and the profiling chart with the same calibration | the `.ti2` RGB (before the calibration) |

  The prediction is `xicclu -ff -ia -pX <run profile>` (absolute, XYZ with
  white Y = 100, the `.ti3` scale). Each tool runs with a two-minute timeout.
* **The fallback** (the estimate at the estimated-chart limit, with the strip
  test as set) when: there is no print record, or it does not say ChromIQ
  printed the sheet (`route`, `printed_at`, `colour`); the run has no profile;
  **the profile changed since printing**: through the profile, the recorded
  profile name or modification time differs from the run's profile now; raw,
  the profile is newer than the print; the run's Build Profile settings
  (Manual or Guided) name an illuminant other than D50, an observer other than
  1931 2°, or FWA; the chart is not RGB; cctiff or xicclu is missing, refuses
  or does not finish; and the calibration cases the table above does not
  cover (a raw sheet printed without the calibration the profile describes or
  with one it does not describe, an older layout-engine `-K` chart, a through
  print of a `-K` profile with no record that the calibration was applied).
  The question in 5963902307 said that ChromIQ asks first when the profile has
  changed (Knut's earlier Q4 ruling); that window is not built in phase 1, and
  such a sheet falls back.
* **The log** (chromiq.log) says once per chart which source was used and why.
* **The same in every place**: the live strip, the live patch, a whole chart
  read at once, the patch-by-patch sound, and the repaint of 10.6, all through
  `verify_expected.apply_expected`.
* **Unchanged:** the colour ranges of 10.4 (device RGB read as sRGB); the
  confirmed-patch memory of 10.7 and its file. The three spaced confirmations,
  the "closest" patch and the shift test of 10.4 work on the expected colours,
  so on these charts they work on the prediction. The engine's own log line
  "worst patch ΔE" is the engine's figure against the `.ti2`.

**Measured** (copies, no file written; `~/Desktop/ChromIQ-work/2026-10-03_verification_expected/build/probe_prediction.py`):

| Sheet | Source | Median ΔE before → after | Largest | Red |
|---|---|---|---|---|
| printer-test, raw (2026-08-10_120247) | prediction | 28.3 → 4.2 | 105.8 → 10.6 | 0 at 30 |
| printer-test, through, relative (2026-08-10_121639) | prediction | 27.0 → 4.3 | 106.3 → 11.7 | 0 at 30 |
| Knut's run 3, gamut chart, raw | prediction | 13.8 → 3.1 | 105.2 (B1, pure blue) → 2.2 | 0 at 30 |
| Knut's run 2, gamut chart, raw | estimate: the profile was rebuilt at 00:39, after the 21:27 print | unchanged | 106.9 | 1 at 95 |

Worked out in 0.1 to 0.15 s per sheet.

### 10.9 · The neighbour check: a reading that does not fit the patches nearest in colour (#182, beta 11)

#### Confirmed behaviour: the neighbour check on profiling charts

*Superseded in part by 10.11 (beta 17, Knut 6078174421, 6082015002, 6085694445): the check now runs on every chart type, its neighbours come from any strip, and the rule is Knut's four steps against the Neighbour limit; the "buffer" and the excess test are gone.*

**Confirmed by:** Knut, 2026-10-04, 5983470377, 5983725218 and 5984174575 (#182 [5983470377](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983470377), answer 5: *"Build the neighbour check for profiling charts?"* "Answer: Yes", approving section C of the beta 10 analysis, `~/Desktop/ChromIQ-work/2026-10-04_beta10/knut_analysis/ANALYSIS.md`; [5983725218](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5983725218): *"The Neighbour-check method should have a defined input box in preferences --> measurement so that the threshold for when this check triggers a red highlighted patch can be modified by user. Rereading those misread to confirm their value, turning them to yellow, as usual."*; [5984174575](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5984174575): on charts made with a pre-conditioning profile *"If so, yes"*, and *"No learned colour range can turn it (that only applies to the other limit check, the 95 or 20) ... The neighbour check needs a re-read to confirm."*). Only the rule below; the card's and the closing window's words are M-PATCH-NEIGHBOUR and M-MEASURED-SUSPECTS in §M-PROPOSED, and the details Knut was not asked about wait in the section after this one.

* **Where.** Profiling charts: those whose expected colours are ArgyllCMS's estimate, **and** those made with a **pre-conditioning profile** (`targen -c`; the chart file carries `ACCURATE_EXPECTED_VALUES`), Knut 5984174575. **Not** on a verification measurement (its own limit, 10, does this work: the analysis' verdict) and **not** on a calibration chart.
* **The rule** (the robust form of the analysis, `workflow/neighbour_check.py`). For each patch with a reading: its comparison patches are up to **4** other patches with a reading, read in a **different strip**, whose **expected** colours lie within **ΔE\*ab 15** of its own, the nearest first. With fewer than **3** it is **not judged**: a patch is never flagged for lack of comparisons. For each pair the excess is `|measured_a − measured_b| − |expected_a − expected_b|` (ΔE\*ab, L\*a\*b\* as the engine computes it, D50). When the **median** excess is **more than the buffer** the patch is a suspected misread and is drawn **red, even below the limit**.
* **The buffer** is a box in Preferences ▸ Measurement, default **ΔE 10** (5983725218).
* **Only its own re-read clears it** (5984174575). Read again with the same colour (within ΔE 3, 10.2) it turns **yellow**, and the confirmation is kept with the measurement (10.7). Similar patches of other strips (10.3a) and a learned colour range (10.4) do **not** turn a neighbour suspect yellow: those rules belong to the limit (95 / 20 / 10). A suspect is not a similar patch for another patch either. A patch red for **both** reasons (over the limit and a neighbour suspect) also needs its own re-read.
* **When.** Judged again after **every strip** (the analysis: "re-judge after each strip, never flag for lack of comparisons"), so a patch read early can turn red, or back, when later strips bring its comparisons; and when a measurement is opened.
* **The closing window** of a measurement carries a short summary of the suspected misreads the neighbour check found and, when it ran, of "Was a strip read twice?"; a verification's closing window carries none of it (5983470377).

**Measured** (the analysis, replayed through the module on the same six real profiling sheets, `tests/test_neighbour_check.py`, numbers identical): suspects at buffer 5 / 8 / 10 / 15: HP laser 1944, 43 / 9 / 4 / 0; Knut run1 648, 8 / 1 / 1 / 0 (P27); run4 324, 0; Epson P300 924, 10 / 2 / 2 / 0; Canon Pro300 1168, 259 / 81 / 28 / 0; Knut's scanner chart 315, 14 / 4 / 0 / 0; **35 of 5,323 patches (0.7 %) at buffer 10**, 28 of them on the wide-gamut Canon. Share of patches with 3 comparisons by the end: 1.0, 0.78, 0.44, 0.98, 0.99, 0.47. Against injected misreads (the analysis): smudges 43 %, single glitches 77 %, out of step and another strip's readings 100 %; with the limit 95 and the strip test, 45 / 81 / 100 / 100. The analysis measured estimated charts only; on charts made with a pre-conditioning profile the check runs on Knut's ruling, not on a measurement.

#### ⏳ Awaiting confirmation — the neighbour check's details

**Confirmed by:** *nobody yet.*

How beta 11 builds what Knut approved; none of it was asked of him.

* **Modes.** Every way of reading: strips, patch by patch (CR30 spot included), a whole chart at once, a resumed or refined measurement, and a measurement painted from disk. A patch read patch by patch is judged with the strip its location names. Judged again after every patch as well as every strip.
* **The box.** "Flag a patch that does not fit the patches nearest in colour by more than:", ΔE 1 to 50, one decimal, an application setting like the limits above it (`patch_neighbour_buffer_de`), not a per-target one. Pressing OK judges the outlines again, as the limits do.
* **The card** (M-PATCH-NEIGHBOUR): the patches compared (3 or 4), the median excess itself and the buffer ("it is ΔE 12.4 further from their readings / than the expected colours are (your limit 10.0)"), and that only its own re-read turns it yellow. A patch red for both reasons shows the limit's red card with these lines added, in place of its colour range's lines. The figures follow the comparisons as later strips arrive.
* **The closing window** (M-MEASURED-SUSPECTS), under the reading times: the suspects still red (the first ten, in chart order), those a re-read kept as real, how many patches could be checked when not all could (and, when none could, that instead of "no suspected misreads"), and, when "Was a strip read twice?" ran, each strip it asked about with the answer. Profiling and calibration measurements; on a calibration chart only the strip lines.
* **A reading set aside** by "Was a strip read twice?" leaves the check at the answer: it is neither a suspect nor a comparison until the strip is read again.
* **A resumed measurement** is judged with the earlier sessions' readings only when the overlay is shown (the readings are taken from the file by the overlay's repaint at the start of the session, as the yellow memory's are).
* **Cost.** Each patch's comparisons are kept between strips and only what a strip changes is worked out again: about 40 ms a strip more at the end of a 4,096-patch chart.

#### ⏳ Awaiting confirmation: B2+, two buffers, the approved line and the check's own switch (beta 15, k43 and k44)

**Confirmed by:** *nobody yet.* (The requests are Knut's: #182 [6059912998](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6059912998), "Questions, one at a time", answers 1 to 6, on `~/Desktop/ChromIQ-work/2026-10-08_neighbour_methods/ANALYSIS.md`; and [6060201176](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6060201176). What was built from them waits here.)

* **B2+ (answers 1 and 2: "Use the suggested B2+ method").** A patch is judged once **2** patches near it in colour have been read in other strips (up to 4, the nearest first, within ΔE\*ab 15 as before; it was 3), and it is red only when, besides the median excess over the buffer, it is **the one that is off**: the median of ΔE(patch) − ΔE(neighbour), each reading's distance from its own expected colour, is above 0. Knut, answer 2: *"The patch that is currently being read is the patch that is judged, and if that is the one that is further off, then that is the one turning red."* Built in `workflow/neighbour_check.py` (`MIN_COMPARED` 2, `NeighbourFinding.further`). The sphere idea is dropped (answer 3).
* **Re-checked after each strip, as before;** a green (corrected) patch may still turn red again when a later reading of it is a misread (answer 4, Knut wants that kept). Nothing changed there.
* **The approved line** (answer 5, "Yes"): "Checked again after each strip: a patch can turn red later, when patches near it in colour are read". On the card it is broken in three at the colon and the comma (lines 10 to 12 of M-PATCH-NEIGHBOUR; beta 15 follow-up, before it only at the comma), after the figures; the Preferences help carries it whole. Its wording is Knut's; the rest of the card stays proposed.
* **Two buffers (answer 6).** Preferences ▸ Measurement: "Buffer on a chart made with a pre-conditioning profile:", default **5** (`patch_neighbour_buffer_de_accurate`), and "Buffer on a chart with estimated colours (most charts):", default **10** (`patch_neighbour_buffer_de`, the beta-11 box, values kept). The chart's file decides which one applies (`ACCURATE_EXPECTED_VALUES`, the same test as the limits'), so the user never chooses.
* **The neighbour check's own switch (k44).** Knut read the checkbox "When reading strips, only flag a patch that also stands out from its own strip" as the neighbour check; it switches the **strip test** (a patch past the limit is flagged only when it also stands out from its own strip; `patch_warn_outlier_fence`). It never controlled the neighbour check, and switching it off can only add red outlines, which is what Knut saw. Both are now named after their function: the checkbox "Strip test: flag a patch past the limit only if it also stands out from its own strip" with the help card "Strip test", and a **new** checkbox "Neighbour check: flag a patch that does not fit the patches nearest to it in colour" (`patch_neighbour_check`, default on) with the help card "Neighbour check" and the two buffers under it (greyed while it is off). The limits' help quotes both labels word for word.
* **Live.** Pressing OK with the neighbour check switched off removes every red outline it caused at once, during a measurement too, and its line in the closing window; switched on again, they come back. Nothing is read again: each patch it had suspected is judged again from its last reading (`TabMeasure.refresh_neighbour_switch`, called from `refresh_patch_flags`), so what a re-read confirmed (yellow) or corrected (green) is kept across the toggles. While it is off the check still takes the readings, so switching it on needs no new reading.
* **Measured again** on the six real sheets (`tests/test_neighbour_check.py`), suspects at buffer 5 / 8 / 10 / 15: HP laser 29 / 7 / 3 / 0; Knut run1 5 / 1 / 1 / 0 (P27); run4 0; Epson P300 8 / 2 / 2 / 0 (AK19, AM5); Canon Pro300 115 / 44 / 18 / 0; scanner chart 9 / 3 / 0 / 0; **24 of 5,323 at buffer 10** (beta 11: 35). Patches with enough comparisons: run1 85 % (78 %), run4 60 % (44 %), scanner chart 71 % (47 %).
* **The help** (Preferences ▸ Measurement, "Neighbour check") says what it does, what it needs, when it runs, its limits, the patch colours and states, the two buffers and what switching it off does, naming each control by its label (Knut: "always use the proper name of a function or parameter"). Its words, and the strip test's, are ours and wait for approval with the labels.

#### ⏳ Awaiting confirmation: the neighbour comparison on every card, and the Verification box's default (beta 15, items 9 and 10)

**Confirmed by:** *nobody yet.* (Both requests are Knut's, #182 [6065640028](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6065640028), approved by Basti for beta 15.)

* **Item 10, the comparison on every card.** Knut: *"it could really be useful if the hover-over-text, under the "Measured" info, also shows how far or close the measured patch value is compared to its closest colour-neighbours in the patch set ... "Average" would here also mean to ignore large outliers ... I think this actually should be present in the hover-text for a patch always, either an error is triggered or not."* Built: every card of a patch the neighbour check judges carries lines 12 to 17 of M-PATCH-NEIGHBOUR under "Measured": the B2+ neighbour set (2 to 4 read patches of other strips within ΔE\*ab 15) and the MEDIAN of ΔE(patch) − ΔE(neighbour), each reading's distance from its own expected colour, which ignores one outlier among the neighbours; "further" above 0, "closer" below; too few neighbours read says so. The figure is asked of the check when the card is drawn (`TabMeasure._neighbour_compare`), so it follows every later strip. On a verification or a calibration chart, where the neighbour check does not run, the same figures are worked out on that measurement's own readings and expected colours for the card ONLY (`TabMeasure._neighbour_card_feed`, review of beta 15): nothing is outlined there, no closing-window line, no verdict; outlines on a verification are a separate analysis Knut asked to see first. Tests: `tests/test_b15_card_compares_with_the_neighbours.py`.
* **Item 9, the Verification box opens on the latest dated verification.** Knut: *"Should the dropdown always default to the last dated verification, and only default to 'New Verification...' if there are no verifications?"* Built: with Run type Verification, choosing a run, changing the run type to Verification, and reopening a project (which selects its run) put the Verification box on the run's latest dated verification; on "New verification" only when the run has none (`MeasurementTargetController.default_verification_id`). A user's own pick of "New verification" is kept until the run or the run type changes again. The warnings before changing a chart that has a measurement, and before measuring into a date that already holds one, are unchanged. **Selecting asks nothing (review of beta 15):** with the latest date chosen by default, switching Run type to Verification opened "This chart already has a measurement" at once. Now a selection change that lands on a dated verification (the run type, the run, or another date) opens no window: the overlay follows the options panel's tick and "Refine / resume" is offered there. Arriving at the Measure tab still asks, as Knut ruled for every chart (#130, 2026-07-29), and a profiling run's selection still asks (#131 scenario 4); the question at Start Measurement on a date that holds readings and the warning before changing a measured chart are untouched. Until now picking another date asked too: that was our own extension of scenario 4 (f53874ca1), never Knut's ruling. Tests: `tests/test_b15_selecting_a_verification_asks_nothing.py`. No specification stated the old default; `core/measurement_target.chart_overwrite_message` still sends a user who wants a fresh check to "New verification". **A date reads as the date (beta 15 follow-up):** every dated entry of the box read "Overwrite <date>" (since #130 phase 4, when the box opened on "New verification" and picking a date was the step towards measuring over it). With the latest date chosen by default, merely looking at a verification read like a destructive act, and the entry was cut to "Overwrite 2027-01-07 11:0" in the bar. Each date now reads as the date alone ("2027-01-07 11:00"); "<date> — no measurement yet" is unchanged, and measuring over a date that holds readings is still asked about at Start Measurement. When the bar is too tight, each box now first gives up what it holds beyond the entry it shows, and the last cut takes the end of "Run N (overwrite)" before the date. No specification stated the "Overwrite" wording. Tests: `tests/test_b15_a_selected_verification_reads_as_its_date.py`. Tests: `tests/test_b15_verification_box_opens_on_the_latest.py`.

### 10.11 · Beta 17: Knut's four steps, and every parameter per chart type (#182)

#### Confirmed behaviour: the neighbour check is Knut's four steps

**Confirmed by:** Knut, 2026-10-09, #182 [6071673457](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6071673457) (the four steps), [6078174421](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6078174421) (*"I think the 4 steps should be used"*; *"I say neighbours should come from any strip"*), [6082015002](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6082015002) (*"No, add neighbour check for calibration charts"*), [6085694445](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6085694445) (*"I revert back to previous solution with the 'colour-neighbour radius' parameter ... I do not want a solution that has hidden thresholds that change behaviour."*), and [6070058549](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6070058549) answer 3 (*"Should the neighbour check run on verification charts ...?" "Yes"*).

1. **The rule.** For each neighbour, its error: ΔE\*ab between its reading and its expected colour. The median of the neighbours' errors. The patch's own error, the same way. The patch is red when its own error minus that median is **more than the Neighbour limit**. Nothing else: beta 15's first test (the readings further apart than the expected colours, by more than a "buffer") is removed, and there is no hidden threshold, no "twice the limit" and no "always 4" ([6085694445](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6085694445)).
2. **The neighbours** are the **2 to 4** read patches nearest to it in expected colour **within the Colour-neighbour radius**, from **any strip**, its own included. With fewer than 2 the patch is not judged.
3. **When.** Judged again after each completed strip read, or after each patch read in patch-by-patch mode, and when a measurement is opened.
4. **Yellow** only by the patch's own re-read (within the Same-reading tolerance); similar patches and a learned colour range do not turn a neighbour suspect yellow ([5984174575](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5984174575), unchanged). A green patch turns red again when a later reading of it is a misread ([6059912998](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6059912998) answer 4, unchanged).
5. **Every chart type:** profiling charts with estimated colours, profiling charts made with a pre-conditioning profile, verification charts (through the profile and From Profile Gamut) and calibration charts, each with outlines.

#### Confirmed behaviour: the parameters, their names and their defaults

**Confirmed by:** Knut, 2026-10-09, #182 [6082015002](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6082015002) (*"All the parameters in the shown table should be configurable, for all chart types and 2 test types"*, the same-reading tolerance *"common for all and configurable"*, the colour-neighbour radius *"visible and configurable"*, *"Names for the tests, limits, chart types are all good"*, neighbour limit 10 on calibration charts), [6078174421](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6078174421) (the defaults 10 / 5 / 3 and the chart-type names with "Profiling"), [6070058549](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6070058549) (verification patch error limit 5: *"Yes, I agree"*), [6084176226](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6084176226) (the strip test's *"own box for verification charts, off by default"*), [6082015002](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6082015002) and [6085694445](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6085694445) (radius 15 / 30 / 30 / 30, *"setting that threshold to 30 for calibration charts"*).

All values ΔE\*ab (CIE76, L\*a\*b\* D50), every one in Preferences ▸ Measurement:

| | Profiling charts with estimated colours | Profiling charts made with a pre-conditioning profile | Verification charts | Calibration charts |
|---|---|---|---|---|
| **Patch error limit** | 95 | 20 | 5 | 95 |
| **Strip test** | on | on | off (its own box) | on |
| **Neighbour check** (one switch) | on | on | on | on |
| Neighbour limit | 10 | 5 | 3 | 10 |
| Colour-neighbour radius | 15 | 30 | 30 | 30 |
| **Same-reading tolerance** | 3, one value for every chart type | | | |

#### Confirmed behaviour: Preferences ▸ Measurement is one table

**Confirmed by:** Knut, 2026-10-09, #182 [6082015002](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6082015002) (the table: chart types as column headers, a test with more than one threshold on its own bold row across the columns with its parameters below, the ON / OFF box left of the test's name, the same-reading tolerance one merged box, help icons in a last column; *"All separate checks should begin its name with bold"*), [6084176226](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6084176226) (*"The mockup table version looks good. The One-sentence description you made for each parameter or test can be shown as tool-tip hovering the name"*; the k56 mock-up `prefs_measurement_A_table_en/de`), and [6085694445](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6085694445) (the tooltips *"are fine, except the Neighbour check returns to using 2 to 4 nearest patches and the 'colour-neighbour radius' parameter"*).

The tooltips on the names, as Knut approved them in [6085694445](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6085694445) (*"This are fine"*): Patch error limit "The largest ΔE\*ab a patch may be from its expected colour before it is outlined red."; Strip test "A patch past the patch error limit is outlined red only if it also stands out from the other patches of its own strip."; Same-reading tolerance "The largest ΔE\*ab between two readings of one patch for a re-read to count as the same colour." The neighbour check's and the neighbour limit's he approved *"except the Neighbour check returns to using 2 to 4 nearest patches and the 'colour-neighbour radius' parameter"*; their reworded sentences, and the colour-neighbour radius's, are confirmed in the section after the hover cards (Knut, 2026-10-10).

The strip test's help carries the paragraph Knut approved in [6085694445](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6085694445) (*"Yes"*, to question 3 of [6085123026](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6085123026)), "Strip test on verification charts (off by default)", without its internal reference line *"(Numbers: k56 …)"*, which he asked to go.

#### Confirmed behaviour: the hover cards

**Confirmed by:** Knut, 2026-10-09, #182 [6078174421](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6078174421) and [6084176226](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6084176226) (*"Yes, good."*). The words are M-PATCH-NEIGHBOUR and M-PATCH-LIMIT (§M). No "buffer" anywhere, an empty line between topics, "read in other strips" gone, and every card ends with "Checked again after each strip is read: …" (patch by patch "… after each patch is read") and "See Preferences ▸ Measurement for threshold values." ([6071004702](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6071004702), [6082015002](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6082015002)).

#### Confirmed behaviour: the three remaining tooltips, and two rulings on what the check is for

**Confirmed by:** Knut, 2026-10-10 (#182 6092540253), [6092540253](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6092540253), answering questions 1 to 3 of [6092038699](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6092038699). Their English text had already been approved by Basti on 2026-10-10; that approval stands.

* **The three tooltips** (question 3, *"accepted"*), verbatim:
  * Neighbour check: "Each patch is compared with the 2 to 4 read patches nearest to it in expected colour within the colour-neighbour radius, and outlined red if it is clearly further from its expected colour than they are."
  * Neighbour limit: "How many ΔE\*ab further from its expected colour than the median of its 2 to 4 nearest patches a patch may be."
  * Colour-neighbour radius: "The largest ΔE\*ab between two expected colours for the two patches to be compared."
* **Faulty whole or half strips** (question 1, *"Keep the neighbour check as it is for this?"*, *"yes keep"*): the neighbour check stays as built in beta 17, neighbours from any strip, also when a whole or half strip was read with stray light or a tipped instrument. Neighbours are not restricted to other strips.
* **Scanner-read sheets** (question 2, *"Is a scanner-read sheet outside what the neighbour check is designed for, so these 16 are acceptable?"*, *"leave as is"*): a sheet read with a scanner is outside what the neighbour check is designed for. The red outlines it gets there are accepted, and there is no separate, higher neighbour limit for scanner-read measurements; the limits stay as in the table above.

#### ⏳ Awaiting confirmation: how beta 17 builds it

**Confirmed by:** *nobody yet.*

* **Which chart type a measurement is** (`workflow/misread_settings.chart_kind`, decided by the chart, never chosen): a chart in the project's `cal` folder is a calibration chart; a verification judged against its profile's prediction (10.8) is a verification chart, through the profile or From Profile Gamut; a chart whose file carries `ACCURATE_EXPECTED_VALUES` is a profiling chart made with a pre-conditioning profile; every other chart has estimated colours. A verification sheet that falls back to the chart's own estimate (10.8 point 2, or a profile made after the sheet was printed) takes the column of the profiling chart its file describes, as the fallback always did.
* **The three tooltips** that waited here (Neighbour check, Neighbour limit, Colour-neighbour radius) were confirmed by Knut on 2026-10-10 and moved to the section above.
* **The keys.** `patch_read_warn_de_estimated` / `_accurate` / `_prediction` (beta 11's, values kept) and the new `patch_read_warn_de_calibration`; `patch_strip_test_<type>`, `patch_neighbour_limit_<type>`, `patch_neighbour_radius_<type>`, `patch_same_reading_de`; `patch_neighbour_check` unchanged. Ranges: patch error limit 1 to 200, neighbour limit 0.5 to 50, radius 1 to 100, tolerance 0.5 to 20, one decimal each. Application settings, not per target.
* **Migration (settings schema 29; like every step since beta 16 it runs only for settings stored before it).** A stored verification limit of 10 is the old default's echo and becomes 5; any other value is kept. "Strip test" switched off (`patch_warn_outlier_fence`) stays off on profiling charts (both kinds) and calibration charts, which it ruled; the new verification box starts at its default, off. A changed neighbour "buffer" becomes the neighbour limit of the same chart type (estimated, pre-conditioning): it measured something else, but it was the one number a user turned to make the check stricter or looser. A changed limit of charts with estimated colours is also given to calibration charts, which used it until now. The old keys are removed.
* **The Same-reading tolerance** decides every "same colour" of a re-read: yellow (10.2, 10.10a), and green (a re-read more than the tolerance away from the red reading, 10.10).
* **The closing window** of a calibration measurement now carries the neighbour check's lines (M-MEASURED-SUSPECTS), since the check runs there; a verification's still carries none (5983470377).
* **The help texts** of the four rows (what the test does, its values by chart type, what it needs, when it runs, the patch colours, Knut's tip for laser printers: a neighbour limit of 7 to 15 on verification charts, [6078174421](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6078174421)) and the limits' purpose paragraph are ours, except the approved strip-test paragraph.
* **The card** shows the comparison line under "Measured" on every chart type; on a yellow card it names why the patch was red (the patch error limit or the neighbour check). A patch past the patch error limit that also fails the neighbour check carries M-PATCH-NEIGHBOUR-VARIANTS line 1 (§M-PROPOSED).
* **Tested as Knut asked** (6084756743): `scripts/make_misread_demo.py` builds a project with a real chart of each type and readings that trip every kind of misread; `scripts/drive_b17_misread_protocol.py` measures them in the real app on screen (strips and patch by patch), changes every threshold of each chart type up and down in Preferences ▸ Measurement, and takes each test through red, yellow and green, against an implementation of the rules of its own. What it showed about strips read off together (review of beta 17, corrected: the first wording generalised from the ONE probe patch per strip the driver looked at). On the demo's measurement with every misread at once, at the default thresholds, the neighbour check outlines 14 of the 21 patches of the strip read off together and 6 of the 10 of the half strip on the profiling chart with estimated colours (beta 16: 16 and 4), 21 and 10 on the chart made with a pre-conditioning profile (beta 16: 16 and 4), 16 and 8 on the calibration chart (beta 16 did not judge calibration charts), and 18-19 and 10 on the verification charts; a strip reader re-reads the whole strip, so one outline is enough. The patch the driver looked at happened to be one of those left unoutlined. Injected into the real profiling sheets of `tests/test_neighbour_check.py` (HP laser, Knut's run1 and run4, Epson P300; 32 strips each), a whole strip with stray light is noticed 29 times in 32 (beta 16: 28), half a strip 24 (22), a whole strip read with the instrument tipped 12 (3), half a strip 8 (2). The strip test still hides such strips from the patch error limit, as before. A strip read out of step or another strip's readings are caught.

#### Confirmed behaviour: a value on a threshold is not over it, compared at one decimal (4.3.4 beta 1)

**Confirmed by:** Knut, 2026-10-10, #182 [6094941512](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6094941512) (his own rule: *"patch B3 turned red with 3.0 dE error from its neighbours. This is ON the error threshold of 3.0, which should not be red, because errors shall happen if ABOVE the threshold. I suggest that an error only is flagged if the threshold is passed by one decimal ... the values being compared with the threshold is rounded to the closest value with one decimal (0.1 steps). This principle should apply for all measurement thresholds and tests (as defined in preferences -> measurement tab) during measurement, so that one never get this situation again."*).

* A value is flagged only when, rounded to one decimal, it is **above** the threshold: at a threshold of 3.0, ΔE 3.0 is not flagged and 3.1 is.
* This holds for every threshold and test of Preferences ▸ Measurement while measuring.

#### ⏳ Awaiting confirmation: how 4.3.4 beta 1 applies the one-decimal rule

**Confirmed by:** *nobody yet.*

* **One helper** (`workflow/misread_settings.py`: `one_decimal`, `above`, `within`, `within_array`) for every comparison, so all round the same way.
* **The rounding is the cards' own** (`f"{value:.1f}"`, which every card line naming a limit uses): the nearest tenth of the float's exact value; an exact half the float holds exactly (0.25) goes to the even tenth (0.2). So the figure a card prints is, character for character, the figure compared, and a red card always prints a value above the limit it prints. The card's colour section keeps its precise "ΔE\*ab 5.04" line (two decimals); the sentences that name a limit print one decimal.
* **Each threshold, and the direction chosen:**
  * **Patch error limit:** red when the patch's ΔE\*ab is *above* the limit (it was "reaches": at or above). Strips, patch by patch, a whole sheet, a measurement painted from disk, the re-read rules (10.10a: "past the limit", and "under the limit" is now "not above it", so a re-read ON the limit after one past it is green) and the out-of-tolerance sound.
  * **Strip test:** its threshold is worked out, not typed (the strip's fence); a patch past the limit is red only when its ΔE\*ab is also *above* the fence at one decimal (it was at or above).
  * **Neighbour limit:** red when the patch's own error minus its neighbours' median is *above* the limit (it was already strictly above, on the unrounded figure: Knut's B3 printed 3.0 and was above by a few thousandths).
  * **Colour-neighbour radius:** "within the radius" is *not above it*: a patch whose expected colour is 15.0 away is a neighbour at radius 15.0, 15.1 is not (it was at or below, unrounded). Chosen so that a value ON a threshold counts as inside it, the same rule seen from the other side.
  * **Same-reading tolerance:** "the same reading" is *not above it*: a re-read 3.0 away is the same colour at 3.0, 3.1 away is not, which also decides green (a re-read more than the tolerance away).
* **Not touched:** the reading-speed check of Preferences ▸ Measurement compares times, not colour differences, under its own rulings (Knut, #131: "strictly according to the calculations", and Basti's 2 % allowance, beta 12); the Measurement Report's limit sets (Preferences ▸ Reports) and Check & Refine's threshold are not tests of Preferences ▸ Measurement during measurement.
* **The help** of the Patch error limit says "is above the limit" (it said "reaches"), and the help of the Patch error limit, the Strip test, the Neighbour check and the Same-reading tolerance carry one new paragraph, "ONE DECIMAL" (`ONE_DECIMAL_HELP`, our words). The approved card sentence "ΔE\*ab {de} reached the patch error limit ({limit}, {kind})" is unchanged: it now only stands beside a value above the limit.
* **Open, for §M (review R1, not applied):** "reached" reads as "at or above", and a value ON the limit is no longer red, so the wording is proposed as "ΔE\*ab {de} is above the patch error limit ({limit}, {kind})." and "ΔE\*ab {de} is above the patch error limit ({limit}, {kind}), and it stands out from its strip (strip test)."; and M-PATCH-CORRECTED-VARIANTS' proposed middle line "reached the patch error limit; the new one is below it." as "was above the patch error limit; the new one is not." (a re-read ON the limit is now green, and is not below it). The approved texts stay until Knut answers.
* **Open, for Knut (review R1):** the card's colour section prints ΔE\*ab with two decimals and the rule rounds to one, so a card can show "ΔE\*ab 5.05" beside no outline at a limit of 5.0 (measured on screen: the true value was just under 5.05, which rounds to 5.0). The limit sentence of a red card is always consistent; the two-decimal line is what can surprise.
* **Measured** on the six real sheets of `tests/test_neighbour_check.py`, suspects at neighbour limit 5 / 8 / 10 / 15 (beta 17 in brackets): HP laser 56 / 3 / 0 / 0 (59 / 3), Knut run1 18 / 2 / 0 / 0 (22 / 2), run4 9 / 1 / 0 / 0, Epson P300 17 / 5 / 2 / 1 (17 / 6), Canon Pro300 79 / 22 / 14 / 0 (81), scanner chart 56 / 27 / 15 / 3 (58 / 29 / 16); 31 of 5,323 at the default 10 (32). Tests: `tests/test_434b1_a_value_on_the_limit_is_not_over_it.py`.

### 10.10 · Green: a misread a re-read corrected (#182, beta 11)

#### Confirmed behaviour: the green outline

**Confirmed by:** Knut, 2026-10-04, 5984277558 (#182 [5984277558](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5984277558): *"Ok"* to [5984237879](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5984237879), *"green for corrected misreads from both checks (neighbour check and limit), with that wording?"*). The words are M-PATCH-CORRECTED.

* **When.** A patch that was **red**, by the limit (10.1) or by the neighbour check (10.9), whose **re-read** is no longer flagged by either, is outlined **green**: the misread was corrected and the new reading replaces it.
* **The card** says so, with the first reading's ΔE (M-PATCH-CORRECTED).
* **The closing window** names the corrected patches ("2 misreads corrected by a re-read: patches Y6, AE8.").
* **Remembered.** Green stays while the measurement is open and when it is opened again later, kept with the measurement like yellow (10.7).

#### ⏳ Awaiting confirmation — how green is built

**Confirmed by:** *nobody yet.*

* **Only a live re-read makes green.** The previous reading of the patch (this session's, or the file's when a measurement is resumed) was flagged, and the new one, read now, is not, and reads a different colour (more than ΔE 3 from the red reading, the re-read rule's own margin, 10.2). A patch that stops being red because the limit was raised, or because later strips changed its neighbour check, is not green: nothing was read again; nor is one read again with the same colour after the limit was raised, since its reading was right.
* **A re-read that is still suspected turns green later (beta 12, #182 B1, Basti's AA5 of 2026-10-05).** When the live re-read reads a clearly different colour (more than ΔE 3 from the flagged reading) but something still flags it, typically the neighbour check because the strips around it are not read yet, the correction is remembered, and the patch turns green the moment it is no longer flagged, also when that happens on a later strip's repaint. Reading the misread colour again (within ΔE 3) cancels it; a new session forgets it. This carries out the confirmed rule above (the re-read did fit); it is not a new rule. A re-read that matches the patch's FIRST reading rather than the misread straight before it (Basti's J28) was a question to Knut; he answered it in 6045500910 (10.10a): it is yellow.
* **It ends** when the patch is read once more and the new reading is flagged again (red or yellow); a repaint never ends it.
* **The memory file** (`<stem>.confirmed.json`, 10.7) holds it as `{"kind": "corrected", "de": <first ΔE>, "by": "neighbour" | "limit"}`, read back when the measurement is opened and never used as a reference, so green teaches no colour range and confirms no similar patch.
* **On a verification too.** The limit check runs there and a verification can be misread, so a corrected misread on a verification is green with the same card. Its closing window carries no misread summary (5983470377), so the "corrected" line is not shown there.
* **The colour** is a clear green (`#1fd65f`) on the yellow outline's dark halo, so it reads on light and dark patches; the overlay is drawn on the chart, the same in light and dark mode. The overlay's help, the hover help and Preferences ▸ Measurement's help each add one paragraph on green.
* **Where the line stands.** In the closing window under the neighbour check's lines and above "Was a strip read twice?", on profiling and calibration measurements.

### 10.10a · A re-read is compared with every earlier reading (#182, beta 12)

#### Confirmed behaviour: the re-read rules for a patch red by the limit

**Confirmed by:** Knut, 2026-10-07, 6045500910 (#182 [6045500910](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6045500910), answer 2, to question 2 of [6044584365](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6044584365), Basti's J28). The card's words are M-PATCH-UNSETTLED in §M-PROPOSED.

Knut's own summary: *"1st measurement above threshold=red. (a) 2nd measurement higher error than 1st measurement=red. (b) 2nd measurement "same" as 1st = yellow. (c) 2nd measurement lower than 1st (not same) but still above error limit = red (same as "(a)"). (d) 2nd measurement lower than 1st and below error limit = green. If first measurement error, then (a), then third measurement same as first measurement=yellow."*

* **The first reading past the limit** is red, as before (10.1).
* **(b) A re-read the same** as an earlier reading (within ΔE\*ab 3 between the two measured colours, 10.3) is **yellow**, with the normal confirmation (10.3).
* **(a) and (c) A re-read past the limit again, not the same** as any earlier reading, higher or lower, stays **red**. Its card says that the readings are not similar and all are past the limit, and that another reading is needed to find the real value.
* **A third (or later) reading the same as ANY earlier reading** of the patch, not only the one straight before it, is **yellow** with the normal confirmation. This is Basti's J28: its third reading matched the first, not the misread in between.
* **(d) A re-read under the limit**, after one or more readings past it, is **green** (10.10).

#### ⏳ Awaiting confirmation — how 10.10a is built, and how it sits with the earlier rules

**Confirmed by:** *nobody yet.*

How beta 12 builds Knut's rule (`workflow/patch_flags.py`, `FlagJudge.judge`); none of it was asked of him.

* **Every reading of the session is kept** per patch (a measurement resumed starts from the reading in the file). A repaint is not a reading: it only brings the flag of the last reading up to date. A new session forgets them, except for a patch still unsettled: the memory file (10.7) keeps it as `{"kind": "unsettled", "prevs": [ΔE past the limit, …], "readings": [{"de", "meas_lab"}, …]}`, so it is red again when the measurement is opened (similar patches cannot vouch for it there either), and a re-read in a resumed session is compared with those earlier readings too. Never a reference.
* **"Earlier reading" means an earlier reading that was flagged** (red or yellow) when it was last judged: a re-read the same as a clean reading confirms nothing, as before.
* **(a)/(c) needs the limit on both sides**: this reading past the limit, and one or more earlier flagged readings past it too. Its card lists those earlier readings. A reading past the limit after a reading that only the neighbour check flagged (below the limit, J28's first) is the plain red card.
* **An unsettled patch is red whatever its colour range or similar patches say.** One of its readings is a misread, so neither a learned range (10.4) nor similar patches of other strips (10.3a) turn it yellow, and it is never a similar patch for another patch. Once a reading settles it (the same as an earlier one), it is a confirmed patch like any other.
* **(d) uses the current limit.** A re-read under the limit is green when an earlier flagged reading was past THAT limit, even when its colour is within ΔE 3 of it (96, then 94, at 95). A re-read with the same colour after the limit was RAISED is still not green (10.10): the earlier reading is not past the new limit.
* **With the neighbour check (10.9).** A re-read under the limit that the neighbour check still suspects is not green yet: it turns green the moment nothing flags it (beta 12's B1, 10.10), naming the reading past the limit. A neighbour suspect is still cleared only by its own re-read (5984174575); the same colour as any earlier flagged reading counts as that re-read. J28 (69.5 suspected, 150.4 past the limit, 69.7 suspected): yellow after the third reading, confirmed by the first; green once the neighbour check stops suspecting it, because the misread past the limit was corrected.
* **A third reading the same as an earlier one is not a correction.** When a re-read repeats an earlier reading, the reading straight before it is not "corrected" by it unless that one was past the limit and this one is under it ((d)).
* **The card of the third-reading yellow** is the normal one (Knut: "with the normal confirmation message"); "the reading before" shows the ΔE of the earlier reading it matched.
* **Measured on Basti's 43 strip events of 2026-10-05** (`tests/data/b1_basti_et8550_1005`, the Measure tab's own loop): at limit 95 two patches change, J21 and J28 (red to yellow, each matching its first reading); at his former limit 50 with the strip test off, six re-reads past the limit that agreed with nothing (X27, AA9, AA10, AA21, AA22, AA26, each from ΔE 65 to 147 down to 51 to 64) are now red and ask for one more reading, where similar patches or a learned range had made them yellow.

## 11. Check & Refine: what is offered for re-measuring, and a strip read twice (#182)

Check & Refine compares every patch of a measurement with what the profile
built from it predicts (ArgyllCMS `profcheck`), and offers the strips worth
reading again. Until 4.3.3 beta 6 any strip with a patch above the user's
limit was "to re-measure", and when more than three quarters of the strips
were, the window advised starting over **and offered no way to re-measure**.
On a 648-patch chart one patch in six above 2.0 marks nearly every strip:
Knut's run1 and run2 (beta 5) were both told "24 of 24 strips, start over"
about Good and Acceptable profiles. Knut ruled that on a first check nobody
knows whether re-measuring helps, so refinement must be offered
([5963360295](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963360295)),
asked to see the redesign, and approved it on the pictures
([5963737221](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963737221)).

### 11p. Confirmed behaviour — the purpose of Check & Refine

**Confirmed by:** Knut, 2026-10-04, #182 [5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281)

In Knut's words: *"for Check & Refine we already agreed that confirmed or
non-confirmed high-error patches has no influence, as this feature checks on
the measurements through the built profile, and the resulting high errors from
the Check feature will all be used as part of the recommendations for the
Refining. ... make sure this is remembered as a purpose for the Check & Refine
feature."*

* **Check & Refine checks the measurement through the built profile**, and
  **every high error it finds feeds the refinement recommendations**, whatever
  the Measure tab's red or yellow outlines say. A patch a re-read confirmed, a
  patch similar patches confirmed and a learned patch are offered exactly like
  any other patch above the limit.
* It never reads the confirmed-patches memory (`<stem>.confirmed.json`, 10.7):
  `ui/tabs/tab_check_refine.py::_plan_for` says so at the decision point, and
  `tests/test_check_refine_ignores_the_confirmed_patches_memory.py` fails if
  any Check & Refine source reaches for it again.

*Where the earlier rule came from, honestly.* Knut's K4 request
([5959352118](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5959352118))
said the confirmations must be remembered *"for the Check & Refine function
... to know what to recommend and which patches to ignore"*. Our redesign
pictures ([5963737221](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963737221),
item 7) listed *"Patches a re-read already confirmed (yellow) are not offered
again"*, and his *"Yes. Good."* to the window as a whole
([5963903650](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963903650) Q1)
was recorded as confirming CR-9, although no question asked about that item
alone. Beta 9 then extended it to similar patches and asked him; his answer
reverses CR-9 entirely. Built in 4.3.3 beta 9.

### 11a. Confirmed behaviour — the result window and its report

**Confirmed by:** Knut, 2026-10-03 (#182 [5963903650](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963903650), Q1 to Q4 and Q6, on the pictures in 5963737221; Q4 answered in [5963916503](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963916503); 5963360295 for CR-3 and CR-6)

* **CR-1 · Two lists, worst first.** *"Re-measure these strips first"*: the
  strips with a patch that **stands out clearly** from the rest of this check,
  or a patch that **looks partly read as its neighbour** (an unsteady swipe),
  each with one plain sentence saying why. Then the **remaining strips above
  the user's limit**: the strip, its worst patch's error, and how many of its
  patches are above. *"Yes. Good."*
* **CR-2 · "Stands out clearly" is statistical and relative to each check**,
  never a fixed number: above the median of that check's patch errors plus six
  times their median absolute deviation scaled by 1.4826. On Knut's laser run2
  the bar falls at about ΔE00 5.3, on his run3 at about 2.4, and on a clean
  inkjet much lower.
* **CR-3 · Refinement is always offered** when at least one patch is above the
  limit. The strip-count rule ("more than three quarters of the strips") is
  gone.
* **CR-4 · Starting over is advised only when more than half of all patches
  are above the limit**, in a framed note, and refinement stays available
  below it. *"Yes."*
* **CR-5 · The choice, and its default.** *"Re-measure the strips listed
  first"* (the default) or *"Re-measure all N strips above your limit"*. With
  only one list there is nothing to choose. The guide then goes through the
  chosen strips **in chart order** and the window says so.
* **CR-6 · "Re-measuring the flagged strips can help" stays** in the grade's
  sentence (5963360295).
* **CR-7 · One ΔE formula, named on every number** (ΔE00 by default; ΔE94 or
  ΔE76 when the check used those). No strip averages: everything is per
  patch.
* **CR-8 · Pre-conditioning described as what it does** (`targen -c` spreads
  the new chart's patches evenly by how colours look on this printer and
  paper); it is never "recommended" as a fix, in Check & Refine and in
  Profile Built. *"OK"*. **The "Use as Pre-conditioning" button keeps the
  violet accent whenever it is shown**, beside "Guide Me Through Refinement"
  too, as in beta 5 and 6; only its colour, not which button Return presses
  (ruling: Sebastian, 2026-10-03, reversing the redesign's removal of it).
* ~~**CR-9 · Patches a re-read already confirmed (yellow) are not offered
  again**, and the window names them.~~ **Reversed by Knut on 2026-10-04**
  ([5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281)): confirmed patches are offered like any other, and the window no
  longer has a "Not offered again" line. See *the purpose of Check & Refine*
  above.
* **CR-10 · Re-reads are not judged against the previous profile**
  (5963360295 Q2): the profile is rebuilt after a re-read anyway, and reports
  can be compared.
* **CR-11 · The saved Quality_Check report says what the window says**: the
  same lines, start-over note and strip lists both.

The words are M-CR-STRIPS, M-CR-START-OVER and M-CR-PRECONDITIONING in
§M-PROPOSED: the lines the pictures showed are kept word for word, and the
wording as a whole still waits for Knut's approval as text.

### ⏳ Awaiting confirmation — the details the approval did not cover

**Confirmed by:** *nobody yet.*

What 4.3.3 beta 7 does where the pictures and the questions said nothing.
Built in `workflow/refine_plan.py`; proved by
`tests/test_182_check_refine_redesign.py` and on screen in
`~/Desktop/ChromIQ-work/2026-10-03_check_refine_build/`.

* **When the MAD is 0** (more than half of the errors identical), the spread is
  the mean absolute deviation scaled by 1.2533; when that is 0 too, every error
  is the same and nothing stands out.
* **"Partly read as its neighbour"**: the measured colour lies on the line from
  what the profile predicts for the patch towards what its neighbour in the
  same strip measured, between 15 % and 92 % of the way, no further off that
  line than a quarter of the patch's error, and the neighbour at least 8 apart
  (L\*a\*b\*). No real patch of Knut's run2 or run3 is flagged this way; a
  looser first version flagged run2's L5, which his re-read showed was read
  right.
* **Which reason a strip gets**: a blend found on any of its patches above the
  limit, unless its worst patch stands out clearly, which then is the reason
  given. The first list is sorted by that patch's error, worst first.
* ~~**Confirmed patches leave the lists entirely**~~: withdrawn with CR-9
  (Knut, [5980560281](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5980560281)); every patch above the limit is listed.
* **The formula's name** is read from profcheck's own summary line
  (*"errors(CIEDE2000)"*, *"errors (CIE94)"*, *"errors:"*), falling back to the
  option the check was run with.
* **The strips file** (`Refine_Strips_N`) holds the default choice; picking
  "all strips" rewrites that same file when the guide starts. Both lists are
  written, start over advised or not.
* **A profcheck line cut in two** by the app's output capture is put back
  together before anything is read from it. Knut's run2 report Quality_Check_6
  holds one (B26), and the B26 patch had been left out of every figure.
* **Manual mode's own limit** is used when the check runs from the Manual
  panel; the window used to read the Guided panel's limit there.
* **The window fits its screen** (Basti, 2026-10-04, beta 9): never taller
  than the screen's available geometry (menu bar, a visible Dock, the taskbar
  left out) less 48 px; the grade line and numbers stay above, the button row
  below, and everything between scrolls when it does not fit. With room to
  spare there is no scroll bar.
* **The help of Create Chart's "Refinement profile"** now says what
  `targen -c` does and does not do, in the same terms as CR-8.

### 11b. Confirmed behaviour — asking whether a strip was read twice

**Confirmed by:** Knut, 2026-10-03 (#182 [5963903650](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963903650) Q5, *"Yes."*, to the check as proposed in 5960926048 and 5963737221; sound: [5963044182](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963044182))

* While measuring with ChromIQ's engine, each newly read strip is compared
  with the strips already measured. When it looks like one of them, the
  measurement's own window framework asks *"Strip D looks very like strip C,
  which you already measured. Did you read strip C again?"* with
  **Re-read strip D** and **Keep, it is strip D** (M-STRIP-READ-TWICE).
* `-S` stays on: the comparison is with what was measured on the same sheet,
  never with the chart's expected colours.
* A window that interrupts the read to get the user's attention plays
  **Instrument error** (5963044182; `measurement_window_sounds.md` row
  "Strip read twice").

### ⏳ Awaiting confirmation — how the read-twice check decides

**Confirmed by:** *nobody yet.*

Built in `workflow/strip_read_twice.py` and `MeasureManager._check_read_twice`;
proved by `tests/test_182_strip_read_twice.py` (including the real engine on its
replay instrument) and on screen.

* **The figure**: the median ΔE76 between the new strip and an already
  measured one, trying the strip one patch out either way and in either
  direction, over at least 4 patch pairs, is below **1**, and below **a tenth
  of the new strip's own patch-to-patch variation** (the median ΔE76 between
  neighbouring patches of the strip as read). Measured: different strips at
  least 26 apart on Knut's run2 and run3 (median, with the shift) and the same
  strip read twice under 0.5 (Knut's re-reads); Basti's real misread of
  2026-08-08 (`~/ChromIQ/printer-test`, strip D holding strip C's readings) at
  0.08 to 0.18 in all eight archived copies, which is 0.002 to 0.004 of that
  strip's variation.
* **Comparing with what was measured does not make it immune to the paper.**
  Beta 7's first build used a bar of 3 and no variation test. Simulated on the
  bundled charts (printtarg, ArgyllCMS fakeread through a real profile, a gloss
  and a very-low-chroma matte response, instrument noise): randomised charts
  never asked (0 of 70), but FIXED-ORDER charts (`printtarg -r`, "Preserve
  Patch Order") asked about correctly read strips in 27 of 70 cases, 4 of them
  on gloss, because neighbouring strips of an ordered chart can measure 0.7 to
  3 apart. A bar of 1 alone left 2; with the variation test 0 of 140, while all
  eight real misreads are still caught (review of 6de015eb, 2026-10-03). The
  price: on a smooth fixed-order strip (neighbours about 3.5 apart) a real
  misread is asked about only below 0.35.
* **Never compared with itself.** A strip read again where the reader is (C
  read again with the reader on C) is a legitimate re-read and never asks; only
  a reading the engine filed as D that matches C does.
* **Strips the chart designed alike are never compared** (their device values
  differ by less than 2 on the 0 to 100 scale, with the same shift).
* **What counts as already measured**: the strips the file being resumed holds
  and every strip read in this session, each as last read.
* **When it does not run**: stock ArgyllCMS chartread, patch by patch, and the
  whole-sheet modes (no strip is read); guided refinement (its own navigation
  decides what is read next); and a read chartread's own wrong-strip window
  already asked about (only when `-S` is off).
* **The order of the windows**: the question opens after any measurement window
  already open (for example Strip Read Quickly) has closed, and before
  "Continue to next / Jump to unread"; the move after the read waits for its
  answer. **Re-read strip D** is the default and sends the reader back to D,
  whose new reading replaces this one; **Keep** (or closing the window) keeps
  the reading and lets the move go on. A measurement that ends first takes the
  question with it.
* **One question at a time, about the pair it shows.** A strip read while the
  window is open (the instrument does not wait for it) never changes that
  window's question: a second alarm waits and is asked when the first is
  answered, and a waiting one is replaced only by a newer alarm about the same
  strip.

### ⏳ Awaiting confirmation — a reading asked about is judged only after the answer (4.3.4 beta 1)

**Confirmed by:** *nobody yet.*

**The ruling it is built from:** Knut, 2026-10-10, #182 [6094941512](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-6094941512), on beta 17: strips A and B read, the reader on C, strip B read again without clicking B; behind "Was a strip read twice?" all of strip C turned red (a second try: yellow), and after "I read strip B" C stayed red. *"the neighbour check did not take consideration of the warning message "Was a strip read twice?", and should have judged the patches AFTER I answered that window, not before, so that the neighbour check would judge the right strip depending on my answer (the message window gives four button options, where the outcome should be correctly done depending on what is chosen). The test of the neighbour check must be constructed to verify all these choices every time this function is verified."*

**The fault:** the engine files a reading under the strip it is positioned on, and the Measure tab judged it (patch error limit, strip test, neighbour check, the yellow memory, the cards, the progress count) as that strip the moment it arrived, before the question was asked; the answer only moved the reader and told the neighbour check to forget.

How 4.3.4 beta 1 builds it (`TabMeasure._hold_for_read_twice`, `_release_read_twice_hold`, `MeasureManager.read_twice_waiting_strips`):

* **Held until the answer.** A strip reading the question is about (on screen or waiting behind another window) is not judged, drawn or counted while it waits: the preview, the cards, the neighbour check, the yellow and green memory and the progress figure stay exactly as they were before the swipe, so no outline appears behind the window. A newer reading of the same strip, read while it waits, replaces the held one; the answer is about the strip's latest reading, as before.
* **The four ways the window ends.**
  * **Keep, it is strip {strip}**: the reading is judged as strip {strip}, exactly as the same reading with no question would be.
  * **Closing the window** (the X, Escape): the same as Keep, as before.
  * **Re-read strip {strip}**: the reading is never judged. Strip {strip} counts as unread (as before), so its patches show no reading and no outline until it is read again; the engine's reading of {strip} is now the set-aside one, which never reaches the saved file, so an earlier reading of {strip} shown before the swipe is not shown either.
  * **I read strip {like}**: the same as Re-read for the reading: never judged, neither as {strip} nor as {like}. The reader goes to {like}, whose next reading is judged as {like}; the set-aside reading is not given to {like}, because the engine cannot move a reading to another strip and it would not be the one saved.
* **A measurement that ends with the question open** takes the held reading with it: nothing is drawn, and the overlay is painted from the saved file.
* **The window on the last strip** (review R1 of 4.3.4 beta 1). When the engine says every strip is read while the last strip's reading is still held, whether the chart is finished is decided after the answer: Keep (or closing the window) counts the strip and the "all strips read" window follows; Re-read and I read strip {like} leave the strip unread, and the engine's next "all done" brings it. Before this review the held strip was counted as missing: "Every strip has been read, but 8 patches still have no reading" was written to the log and, after Keep, the finished window never came.
* **A newer reading while the window is open** (review R1). If the strip is read again before the answer and the check finds nothing wrong with the new reading, that reading is the engine's and the one the file keeps, so it is judged at once and is not held; the answer about the older reading then never takes it off the screen. Before this review it was held too, and Re-read or I read strip {like} cleared a strip the saved file still held.
* **The next reading of the strip** after Re-read or I read strip {like} is judged on its own: the set-aside reading was never one of its earlier readings, so it can neither confirm it (yellow) nor be corrected by it (green).
* **Where the window can appear:** only ChromIQ's engine reading strips (§11b, "When it does not run"), fresh or resumed. Proved for every button, with the patch error limit and with the neighbour check doing the flagging, on each of the four chart types (each with its own column of Preferences ▸ Measurement), on a fresh measurement and on one whose strip already had a reading, with the window on the last strip and with a newer reading arriving while it is open: `tests/test_434b1_read_twice_is_judged_after_the_answer.py`.

## 12. The computer stays awake while a measurement runs (Basti, #182 6015495063, beta 12)

#### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

* **When.** From the moment a measurement session starts (Start Measurement, any reading mode, the engine or stock chartread) until it ends, however it ends: all read, failed, stopped, refused before the instrument was asked anything, or the app quitting. Neither the display nor the system goes to sleep in between; the lid closing still sleeps a laptop.
* **How.** macOS: `caffeinate -d -i -w <ChromIQ's pid>`, which ends by itself with ChromIQ, so no assertion is ever left behind (`pmset -g assertions` shows it while it is held). Windows: `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)`, cleared with `ES_CONTINUOUS`. Linux: `systemd-inhibit --what=idle:sleep` where it exists, otherwise nothing. A failure is logged and never stops a measurement. `core/keep_awake.py`, held by `MeasureManager.start`.
* **No window, no setting.** Nothing is shown; it is not optional. Reading a single patch (spotread) does not hold it.
