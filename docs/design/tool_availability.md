# Which Tools apply to which selection — and where they may write

> **These specifications are binding.** They must be consulted before changing
> code in the area they cover, and a fault that contradicts one is reported and
> approved before it is implemented — the specification may be the part that
> needs to change.

## ⏳ Awaiting confirmation — DRAFT, nothing here is settled

**Confirmed by:** *nobody yet.*

Every classification below is the assistant's reading of the code, not an agreed
rule. Knut's own caution applies exactly here:

> *"only the behavior that you confirm as correct, after bugs are confirmed
> fixed, should be written into the design specification. Otherwise the
> specification looses its value with lots of trash Claude thinks is correct
> behavior."*

So this document is a **proposal to argue with**, section by section. When a row
is agreed it stops being a proposal; until then no code greys anything out on
the strength of it.

## 1. Why this document exists, and why it comes first

Knut, 2026-08-08, as part of his handover:

> *"I also discovered that some of the tools are only needed or relevant for
> some of the profile run and run type selections, thus it might be good to ask
> to make a table with a full overview of which functions/tools can be used or
> should not be used for each combination of profile run and run type
> selection. Then gray out the tools in the pull-down list depending on profile
> run and run type selection, and give tool-tip on greyed out tools to tell
> user why it is not available and when it is available."*
>
> *"**That table would define and limit where the various tools should write its
> files, so important to do first.**"*

That last sentence sets the order, and it reverses an open question. "Where
should a tool write?" cannot be answered tool by tool; it follows from *what
that tool is for*. A tool that has no business in a calibration run has no
business writing into `cal/` either. **So the table is the input to the file
placement work, not a companion to it.**

## 2. The selection space

The bar (`ui/measurement_target_bar.py`) offers two things, and together they
make the selection every tool has to be judged against:

| | Values |
|---|---|
| **Run type** | Profiling · Verification · Calibration |
| **Profile run** | an existing run (`run1`, `run2`, …) · **New run** (nothing created yet) |

Calibration is a special case worth stating: there is **one** `cal/` per
project, shared by every run, so "New run" does not apply to it —
`store_for_target` returns `project.calibration` whatever the profile-run
dropdown says (`workflow/per_target_settings.py:228`).

That gives **five reachable states**, not six:

| # | Run type | Profile run | Shorthand |
|---|---|---|---|
| S1 | Profiling | an existing run | *profiling run* |
| S2 | Profiling | New run | *new profiling run* |
| S3 | Verification | an existing run | *verification* |
| S4 | Verification | New run | *new verification* |
| S5 | Calibration | — | *calibration* |

## 3. The three verdicts a tool can have

Deliberately three, not two. "Available / greyed" alone would hide the most
common case — a tool that works perfectly well but has nothing to do with the
current selection.

| Verdict | Meaning | In the pull-down |
|---|---|---|
| **●  Applies** | The tool acts on this selection's own files, and its output belongs to this selection | normal |
| **○  Independent** | The tool works on files the user picks, and has no relationship to the selection at all | normal — greying it would take away something that works |
| **✕  Not here** | The tool cannot do anything useful in this state, or would act on the wrong files | **greyed, with a tooltip saying why and when it returns** |

The distinction between ● and ○ is what decides file placement (§5), and it is
the reason this table has to exist before the placement work.

## 4. The table — DRAFT

Grouped as the Tools pull-down groups them (`ui/tools_popup.py:49`).

### Measurements

| Tool | S1 profiling run | S2 new profiling | S3 verification | S4 new verification | S5 calibration | Note |
|---|---|---|---|---|---|---|
| **Read single patches** `spot_read` | ○ | ○ | ○ | ○ | ○ | Writes nothing; a hand-held meter reading. Never selection-dependent. The FD-9 (Beta) is not one of its instruments and is not offered there |
| **Average measurements** `average` | ● | ✕ | ● | ✕ | ● | Combines repeated reads of *this* chart. A New run has no measurement to average |
| **Merge measurements** `merge` | ● | ✕ | ● | ✕ | ● | Same reasoning as averaging |
| **Inspect a measurement** `ti3_info` | ○ | ○ | ○ | ○ | ○ | Read-only on any file |
| **Measurement report** `measurement_report` | ● | ✕ | ● | ✕ | ● | Reports on a measurement this selection has; a New run has none. S5: the calibration's measurement, its reports in `cal/reports/` (beta 39, Knut 5794078008, `measurement_report_limits.md` §18.12, awaiting confirmation; replaces beta 38's empty, locked window of §18.1) |

### Charts & patch sets

| Tool | S1 | S2 | S3 | S4 | S5 | Note |
|---|---|---|---|---|---|---|
| **Edit / create chart patch set** `ti2_relayout` | ● | ○ | ● | ○ | ● | Opens the selected target's chart (fixed in beta.203). With no chart yet it still creates one from scratch, so it is not blocked. **FD-9 chart (Beta, PR #213): the same as any chart** since 4.3.25 (the owner's second round of FD-9 feedback, F10, on Knut's finding): the editor opens the FD-9 chart, and its edited patch set goes back to Create Chart, which lays it out with the FD-9's own builder (`workflow/fd9/chart.py`: its marks, arrow, patch size and gaps, and the detector check of every page), so the 4.3.24 refusal ("cannot lay it out yet") was wrong and is gone. The protections for a run that holds a measurement are the editor's usual ones. With FD-9 support off nothing is read and it opens as in 4.3.21. *Awaiting confirmation; confirmed by nobody yet.* |
| **Show patch distribution (3D)** `patch_cube` | ● | ✕ | ● | ✕ | ● | Shows *the selected target's* chart — had the beta.203 fault too, fixed here. Nothing to show before a chart exists |

### Scanner & camera

| Tool | S1 | S2 | S3 | S4 | S5 | Note |
|---|---|---|---|---|---|---|
| **Create scanner or camera target** `scanner_target` | ○ | ○ | ○ | ○ | ○ | Turns a measured chart into `.cht`/`.cie`. Independent of the run |
| **Build profile with scanner or camera** `scanner_profile` | ○ | ○ | ○ | ○ | ○ | Builds a *scanner* profile — a different device from the printer this project profiles. **Proposed as independent**, and this is the row most worth arguing about |

### i1Profiler interchange

| Tool | S1 | S2 | S3 | S4 | S5 | Note |
|---|---|---|---|---|---|---|
| **Convert TI1 → i1Profiler** `ti1_to_i1p` | ○ | ○ | ○ | ○ | ○ | Format conversion. Note every chart already writes these sidecars into the run's `exports/` automatically |
| **Convert i1Profiler → TI3** `i1p_to_ti3` | ● | ✕ | ● | ✕ | ● | Brings a measurement *in*. Its natural destination is this selection's measurement — see §5 |
| **Convert i1Profiler → TI1** `i1p_to_ti1` | ○ | ○ | ○ | ○ | ○ | Produces a chart definition, not a measurement |

### Profiles

| Tool | S1 | S2 | S3 | S4 | S5 | Note |
|---|---|---|---|---|---|---|
| **Inspect a profile** `profile_info` | ○ | ○ | ○ | ○ | ○ | Read-only on any `.icc` |
| **Verify a profile (independent check)** `verify_profile` | ● | ✕ | ● | ✕ | ✕ | Already takes the project's runs and verification history. A calibration has no profile to check |
| **Verify against reference** `verify` | ○ | ○ | ○ | ○ | ○ | Explicitly the "files from elsewhere" tool (#133 §15.4) |
| **Create device-link profile** `device_link` | ○ | ○ | ○ | ○ | ✕ | Needs a finished printer profile; a calibration never produces one |
| **Apply a device-link to an image** `devicelink_apply` | ○ | ○ | ○ | ○ | ○ | Acts on the user's images, not on the project |
| **Soft-proof / check an image** `softproof` | ○ | ○ | ○ | ○ | ✕ | Needs a printer profile to proof through |

### Language

| Tool | S1 | S2 | S3 | S4 | S5 | Note |
|---|---|---|---|---|---|---|
| **Translate / edit language** `translate` | ○ | ○ | ○ | ○ | ○ | Edits the app's own catalogues |

**Totals in this draft:** 7 tools are ● somewhere, 12 are ○ everywhere or
almost, and **12 cells are ✕** — the ones that would grey out.

## 5. What the table then decides about file placement

This is the part Knut said the table exists for, and it falls out of §3 with no
further argument:

| Verdict | Where its output belongs |
|---|---|
| **● Applies** | Inside the selected target — `runs/runN/`, `runs/runN/verifications/<date>/` or `cal/`, resolved through `Project` / `Run` / `Calibration`, never a hand-built path. Tool output that is not itself a chart or a measurement goes in that target's `exports/` |
| **○ Independent** | Wherever the user says. The *offered* folder is still a decision: the last folder used for that tool, falling back to the project root |
| **✕ Not here** | Nowhere — it cannot be opened in this state |

**Measured against that rule, the current behaviour is wrong for the ● tools.**
`_initial_dir(settings, tool_key)` (`ui/dialogs/tools_dialogs.py:201`) offers
the last folder used for that tool, and failing that `_working_dir()` —
`custom_output_path`, or `~/ChromIQ`. That is the **projects root**: not the
open project, not the selected run, not the run type. Five tools take their
destination from it through the shared `_OutputRow`: `average`, `merge`,
`ti1_to_i1p`, `i1p_to_ti3`, `i1p_to_ti1`.

Of those five, the table marks **`average`, `merge` and `i1p_to_ti3` as ●** —
so they are the ones whose default is wrong. `ti1_to_i1p` and `i1p_to_ti1` are
○, and their current behaviour is right. **Fixing `_initial_dir` alone would
therefore be wrong**; the default has to follow the verdict, not the mechanism.

`tests/test_tool_file_placement_audit.py` keeps the writer list complete, and
`scripts/audit_tool_file_placement.py` reproduces it on demand.

## 6. The greying-out, and what the tooltip says

Knut asked for the greyed entries to explain themselves — *"tell user why it is
not available and when it is available"*. Two sentences, always in that order:
**what is missing now**, then **what makes it come back**, naming the exact
control.

Proposed wording, one per reason rather than one per tool, so twelve cells need
four strings:

> **There is no measurement here yet.**
> This tool works on a measurement belonging to the run you have selected, and
> "New run" hasn't been created yet. Generate and measure its chart first, or
> pick an existing run in "Profile run" above.

> **This run hasn't been measured yet.**
> This tool works on the measurement of the chart in this run. Measure the
> chart on the Measure tab, and this tool becomes available.

> **A calibration doesn't have a profile.**
> This tool needs a finished printer profile to work with. Set "Run type" to
> "Profiling" and pick a run that has one built.

> **There is no chart here yet.**
> This tool shows the chart belonging to the selection you have made, and
> nothing has been generated yet. Create the chart on the Create Chart tab.

These are **§M-PROPOSED candidates** if any of them becomes a message window;
as pull-down tooltips they are ordinary help text, but they should be reviewed
in the same pass so the two never disagree.

## 6a. An option offered that the rest of the app cannot honour

Found 2026-08-08 while answering a question about device types, and recorded
here because it is exactly the shape this document exists for.

**Create Chart offers `targen -d` with choices 0–15** — grey, RGB, CMY, CMYK and
the N-colour ink combinations (`data/parameters.yaml`; wired at
`ui/tabs/tab_chart.py:2736` as `_manual_devtype_pw`). Nothing restricts it to
RGB.

**But `parse_ti3` refuses anything that is not RGB**, outright
(`workflow/ti3_analysis.py:158`):

```
raise Ti3ParseError("No device RGB columns — only RGB charts are supported.")
```

That parser is what the measurement report, the cube corners and the
patch-identity check all read through. So a user can choose CMYK, generate a
chart and print it, and then find the result cannot be reported on.

**Established 2026-09-04: the wall is at REPORTING only.** `chartread` accepts a
CMYK chart. It reads the chart's declared `COLOR_REP`, turns it into an ink mask
with `icx_char2inkmask` and then loops over `icx_noofinks(nmask)` device
channels, naming each field from the mask itself. There is no RGB branch
anywhere in it (`spectro/chartread.c:3052-3082` in the 3.5.0 source, through
`xicc/xcolorants.c`). `colprof`, `profcheck` and `colverify` were run live
against a CMYK measurement built from a real FOGRA51 dataset and all three
worked: the profile built in 14 s at peak err 0.67, and ChromIQ's own "Verify
against reference" tool matched 72 of 72 Media Wedge patches, peak 1.91,
average 1.20 ΔE, with no code change.

So nothing between the chart and the measurement file cares what colour space it
is, and of the three options below only the third touches measuring at all.
The gap is one reader, `parse_ti3`, and everything shaped around RGB device
values.

*Worked out in `ChromIQ-research/issue-182/07-cmyk-verification/AB-FINDINGS.md`
§5 and reported on issue #182 on 2026-09-04 (comment 5545838349); the Argyll
source was re-read on 2026-09-11 before this paragraph was written.*
**Confirmed by:** *nobody yet.* It is a fact about Argyll rather than a decision
about ChromIQ, but the `chartread` half has still never been run against an
instrument, so it stays here rather than in a Confirmed section.

**Beta 7 (2026-10-03, the CMYK/CR30 forum report).** Two of the gaps above are
closed, neither by changing `parse_ti3`: a CMYK or multi-ink measurement is
IMPORTED into a run whose chart has the same inks (Basti's approval;
`unified_measurement_management.md` §I.13, awaiting confirmation), and every
reader that still needs RGB (the Measurement Report, its patch-identity line,
the automatic report, the measurement details) says so in one line,
M-VIEW-RGB-ONLY, instead of a parse error. Reporting on a CMYK chart remains
the open item. **Confirmed by:** *nobody yet.*

**Options**, none of them taken here:

1. **Restrict the choice** to what the app can carry through, and say why in the
   tooltip. Smallest, and honest.
2. **Warn at the point of choosing** — the option stays, with a notice that
   measuring and reporting are RGB-only today.
3. **Lift the limit** in `parse_ti3` and everything shaped around RGB device
   values. A real piece of work, and its own design.

This is independent of both verification features
(`verification_printing_and_target.md` §2a) — it is a pre-existing gap that
neither introduces.

## 7. Open questions — these are what confirmation means

1. **Is the three-verdict model right**, or should "independent" simply be
   "available" with no distinction? The distinction is what drives §5, so
   collapsing it changes the placement answer too.
2. **`scanner_profile` and `scanner_target`** — proposed ○ (independent),
   because they profile a *scanner*, a different device from the printer this
   project is about. But a scanner profile built from a chart printed in this
   run arguably belongs to that run. This is the row most likely to be wrong.
3. **`measurement_report`** — marked ● because it reports on this selection's
   measurement, but it can also be pointed at any file. Should it be ● or ○?
4. **Do ● tools that find nothing get greyed, or do they open and explain?**
   Greying is what Knut asked for. Opening-and-explaining is what the Measure
   tab does for the same situation (`M-VERIFY-NO-PROFILE`), and is friendlier
   to someone who wants to read the tool's help before having the files.
   Consistency with the existing model argues for the second.
5. **Should `exports/` be the home for ● tool output**, as §5 proposes, or
   should each tool's output sit beside the files it is derived from?
6. **Does greying a tool need a matching change to the help card** (the
   overview of main actions), so the two accounts agree?

## 8. What has been built already

- **`patch_cube` fixed** — it showed the profile run's chart whatever the bar
  said, the same fault the patch set editor had in beta.203. Found while
  writing this table, which is a point in the table's favour.
- **The audit and its completeness tests** — see §5.
- **Nothing greys out yet.** No cell of §4 is implemented, because no cell of
  §4 is confirmed.

### ⏳ Awaiting confirmation — Inspect a measurement compares two readings of one chart (4.3.32)

**Confirmed by:** *nobody yet.* Asked for by jctay (forum, 2026-11-10);
Basti ordered it built on 2026-11-11 (*"do both, established workflow"*).
Still ○ in every state: it reads files and writes none.

* Measurement info has a row **Other readings:** under the mode row, in
  both modes: a list of files (each with its name and, where the file says,
  the date measured, the instrument and the measurement condition), Add…
  (several files at once), Remove (the selected entries), Clear all and a
  help button; up to nine other readings, ten in all; a file already in the
  list is not added twice, and files past the ninth are not added; the
  window names each file not added and why (see the notice below). Each is a reading of the same chart: a `.ti3`, a CGATS text file with XYZ or
  L\*a\*b\* values, or an i1Profiler `.mxf`/`.cxf`, converted by the
  import's converter in a temporary folder that is removed again, in the
  measurement's own condition when the file holds it.
* **Same chart first** (`workflow/reading_compare.py`): the patch count,
  the patch numbers and the device values of every pair within
  `PATCH_IDENTITY_TOL`, the rule of Verify against reference (4.3.30).
  Files whose patch numbers do not pair (another grid, another order) are
  paired by their device values when each names exactly one patch in each
  file; patches whose device value repeats in the chart are left out and
  counted (more than 10 % left out: refused). Anything else is refused with
  M-READINGS-NOT-SAME-CHART; an unreadable or colourless file with
  M-READINGS-UNUSABLE. Nothing is compared then.
* **Results**, section "Another reading of this chart": the file, how the
  patches were paired, the count, average, median, 95th percentile and
  largest ΔE₀₀, the tolerance (0.5, 1.0 default, 2.0, or Custom 0.1 to 10)
  and how many patches lie above it (above = strictly greater), the ten
  largest differences with their strip and place as printed and both
  L\*a\*b\* values, per printed strip the five worst and every strip of
  which at least three quarters are above the tolerance ("nearly the whole
  strip disagrees"), and a paragraph on what two readings can and cannot
  tell. Save inspection… saves it with the rest, plus every patch above the
  tolerance.
* Nothing is written: not the measurement, not the second reading, no
  profile (`tests/test_4332_compare_two_readings.py`).
* **One other reading** gives the view above, row for row (also when it is
  what is left after removing others). Where the files name different
  measurement conditions or instruments, a row "Measured differently" says
  so, in both views; nothing is refused for it (a file that names none is
  left out of that check). Where a file names no condition (a chartread
  .ti3 never does), a row "Measurement condition" names those readings
  by their place ("This measurement", "The second reading", "Neither of
  the two readings"; with three readings or more by number: "Reading 3",
  "Readings 1, 3 and 4", "None of the readings", 4.3.32 review: file names
  made a ten-line block) and says that ChromIQ cannot know their condition
  (M0, M1, M2) or always their instrument, and that readings taken
  differently differ for that reason alone. The "Second reading" row shows
  the file with its date, instrument and condition where the file says
  them. Every date the window reads from a file ("Measured on", the reading
  lines) is shown one way: `2026-11-11 09:30`, or `2026-11-11` without a
  time, and as the file has it when it does not read as a date
  (`reading_compare.display_date`). Every added reading
  is read by the same loader as the one other reading (review pass 1:
  i1Profiler CGATS text converted as the import converts it; a reading
  without device values beside a turned measurement refused).
* **Two or more other readings** (Basti, 2026-11-11: several readings, not
  only two), section "Other readings of this chart"
  (`workflow/reading_compare.compare_several`). Every file is paired with
  the measurement on its own; one that fails is refused with the messages
  above, marked "not compared" in the list and shown as a "Not compared"
  row, and the others are compared exactly as without it. Patches are those
  every compared reading pairs (others left out and counted).
  * The **centre** of a patch is the median of its L\*, of its a\* and of its
    b\* over all readings, each separately: with three readings the middle
    value (two that agree hold it, the third shows its whole difference),
    with an even number the mean of the two middle values. Every reading's
    ΔE₀₀ to the centre is its distance.
  * The **spread** of a patch is the largest ΔE₀₀ between any two readings
    (with two readings, their difference). **Repeatability**: the median and
    95th percentile of the spread. "Above the tolerance" counts patches
    whose spread is above it.
  * **By reading**: per reading average, median, 95th percentile and largest
    distance, and patches farther than the tolerance (count and share), with
    a verdict: agrees with the others (none above); differs overall (median
    distance above the tolerance); differs on nearly the whole strip X (at
    least three quarters of a strip of three or more patches above); else
    differs on N patches.
  * **Groups** (4.3.32 review: two against two read as four readings that
    each differ overall): two readings agree when their typical difference
    (the median ΔE₀₀ between them over all compared patches) is within the
    tolerance. When the readings split CLEANLY into groups (inside each
    group every reading agrees with every other, none with a reading
    outside it) and at least two groups hold two readings or more, a row
    "Groups" names them by number ("readings 1 and 2; readings 3 and 4"),
    any reading that agrees with no group, and says that ChromIQ cannot tell
    which group is right. A reading of such a group that is not within the
    tolerance of the centre says instead which readings it agrees with, and
    its strips are not called slipped (the centre lies between the groups,
    so that distance is the gap between them). A single reading
    apart (three against one), a chain (1 agrees with 2, 2 with 3, 1 not
    with 3) or no split at all names no groups
    (`SeveralComparison.groups`).
  * **Largest differences**: the ten largest spreads, each with its strip
    and place, every reading's distance from the centre, and, above the
    tolerance, "Reading N stands apart" when every pair of the OTHER
    readings is within the tolerance and N is the only reading for which
    that holds, else "the readings disagree with each other".
  * **By strip**: the five strips where a reading (not one that differs
    overall) is farthest from the centre on average, with every reading's
    average, plus every strip that is nearly whole off in one such reading.
  * **What this tells you**: standing apart is strong evidence, not proof;
    two readings can share an error and make the good one stand apart.
  * Save inspection… saves it all, plus every patch whose spread is above
    the tolerance with its place, its spread and every reading's distance
    from the centre. No CSV export: the window has none to extend.
  * Read on the GUI thread as before; each file is read once and kept, so a
    change of tolerance only recounts (`tests/test_4332_compare_several_
    readings.py`, nine others of 2000 patches well under a second).
* **Files dropped from the file manager** (jctay, forum 150152, 2026-11-12:
  *"would it be possible to add drag-and-drop for selecting files?"*; Basti:
  if possible, do it). `ui/file_drop.py`, `tests/test_4332_drop_files_on_
  measurement_info.py`.
  * On the **Other readings** row (the list, its buttons, its label, also
    while the list is still empty): one file or several, of the kinds Add…
    offers (`.ti3`, `.txt`, `.mxf`, `.cxf`, any case), are added exactly as
    Add… adds the files chosen in its window: in the order dropped, the same
    loader and same-chart check, the same refusals in the same words, a file
    already listed not added twice, and past nine others the rest not added,
    all named in the same notice.
  * On the **Measurement** row: exactly one `.ti3` opens as Browse opens it.
    Two files or a file of another kind there are not accepted.
  * Folders, web links, missing files and files of other kinds are left out;
    a drag that holds nothing usable is not accepted at all (no highlight,
    the system shows its "not allowed" pointer, nothing changes). The row's
    help says which kinds are taken and that folders and other kinds are
    left out.
    It names the file manager as each platform calls it (the Finder, File
    Explorer, "your file manager" on Linux; #130).
  * **One notice, for Add… and for a drop alike** (the owner, 2026-11-12):
    when a file was not added, the banner under the rows names EVERY such
    file with its reason, one line each: already in the list, the list is
    full (nine others), a folder, a kind ChromIQ cannot read as a reading,
    not found on this computer. A newly added file that cannot be compared
    is named in a second part ("Added to the list, but not compared"), and
    its row says "not compared" as before. When every file was added and
    compared there is no notice, and an earlier one goes. This replaces
    4.3.31's single line "… so N of the files you chose were not added",
    which named no file and said nothing about duplicates.
  * **The notice wears the app's warning colours**: the cream warning box's
    ink in Light, amber in Dark, Neutral's own grey box with one equal 1 px
    edge all round (a multi-line box, as the Print Chart warning box; the
    2 px underline stays on one-line banners). Until 4.3.31 this window drew
    it, and its "RGB only" note, in a blue (`#3b82f6`) that is in no
    appearance's palette.
  * While a usable drag is over a row, a dashed frame with a light wash in
    the window's accent (Neutral: the ACTION ink) is drawn over it; it goes
    when the drag leaves or drops. Nothing under it moves.
  * The files are loaded on the next turn of the event loop after the drop,
    not inside it, and on the GUI thread as Add… loads them.
  * `file:` URLs only, decoded (spaces, umlauts); `file:///C:/…` is read as
    the drive path `C:/…` on every platform, `file://server/share/…` as
    `//server/share/…`.
