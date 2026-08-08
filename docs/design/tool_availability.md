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
| **Read single patches** `spot_read` | ○ | ○ | ○ | ○ | ○ | Writes nothing; a hand-held meter reading. Never selection-dependent |
| **Average measurements** `average` | ● | ✕ | ● | ✕ | ● | Combines repeated reads of *this* chart. A New run has no measurement to average |
| **Merge measurements** `merge` | ● | ✕ | ● | ✕ | ● | Same reasoning as averaging |
| **Inspect a measurement** `ti3_info` | ○ | ○ | ○ | ○ | ○ | Read-only on any file |
| **Measurement report** `measurement_report` | ● | ✕ | ● | ✕ | ● | Reports on a measurement this selection has; a New run has none |

### Charts & patch sets

| Tool | S1 | S2 | S3 | S4 | S5 | Note |
|---|---|---|---|---|---|---|
| **Edit / create chart patch set** `ti2_relayout` | ● | ○ | ● | ○ | ● | Opens the selected target's chart (fixed in beta.203). With no chart yet it still creates one from scratch, so it is not blocked |
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

**Not established, and worth knowing before deciding anything:** whether
`chartread` itself accepts a CMYK chart — i.e. whether the wall is at measuring
or only at reporting. The two call for different answers.

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
