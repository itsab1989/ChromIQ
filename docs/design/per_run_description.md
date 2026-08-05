# Per-run description — Test Plan Specification

Issue #130. Knut, 2026-08-05, after agreeing the last open question:

> *"With all that settled, create a complete Test Plan Specification for all
> functions, cases of events, combinations of input variables and output
> actions. Assure that all cases are tested with on-screen control of the app."*

The design this tests is the consequence analysis in
[#130 comment 5190506691](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5190506691),
as it stands with the 🆕 R2 changes. Where this document and that post
disagree, the post is the specification and this is the bug.

---

## How to read this

Every table is **condition × outcome**: the left columns are the inputs a
person can vary, the right column is what must be observed. No row says
"works correctly" — each says what is on screen or on disk, because a row that
cannot be checked is not a test.

| Mark | Meaning |
|---|---|
| **U** | unit test — the decision, with no widgets |
| **I** | integration test — the real widget, driven through its own handler |
| **S** | **on-screen** — the real app, real window, judged by what is rendered |

Every row carries at least one mark. Rows marked **S** are in the demo package
(§9) and are walked in the real app; that is Knut's requirement, not a
nice-to-have — three of the faults in this feature's neighbours were invisible
to green tests and appeared only on screen.

---

## 1. The four fields

Two fields, each of which changes its label and its home according to Run type.

| # | Run type | Label | Working value | Authoritative copy | Shown in |
|---|---|---|---|---|---|
| F1 | Profiling | **Run N Description:** | `runs/runN/meta.json` | the run | Guided + Manual |
| F2 | Profiling | **Run N Chart Notes:** | `runs/runN/meta.json` | the chart's `.channels.json` | Manual only |
| F3 | Verification | **Run N Description:** | `runs/runN/meta.json` of the run being verified | the run | Guided + Manual |
| F4 | Verification | **Run N Chart Notes:** | `runs/runN/meta.json` | the **verification** chart's sidecar | Manual only |
| F5 | Calibration | **Calibration Description:** | `cal/meta.json` | the calibration | Manual only¹ |
| F6 | Calibration | **Chart Notes:** — no run number | `cal/meta.json` | the calibration chart's sidecar | Manual only¹ |

¹ Calibration is manual-only by #137, so "Manual only" is the whole of it.

**T1.1 (U)** `RunMeta` gains `description: str = ""` and `chart_notes: str = ""`.
A `meta.json` written before this feature loads with both empty and is not
rewritten until something changes.
**T1.2 (U)** `Calibration` meta gains the same two keys, same defaults.
**T1.3 (I/S)** The label text follows Run type on the same signal the rest of
the bar follows, with no tab switch needed to see it change.
**T1.4 (I)** With the run not yet created, the labels read **"New run
Description:"** / **"New run Chart Notes:"**, and both show the real number the
moment the run exists (§7 Q1 of the spec).

---

## 2. Typing — which file a keystroke reaches

The spec's §9 Q4. **Exactly one file per keystroke; never both.**

| # | Profile run | Run type | Field | Written to | Not written to |
|---|---|---|---|---|---|
| T2.1 | run 1 | Profiling | Description | `runs/run1/meta.json` | `cal/meta.json`, any sidecar |
| T2.2 | run 3 | Profiling | Chart Notes | `runs/run3/meta.json` | the chart's `.channels.json` |
| T2.3 | run 3 | Verification | Description | `runs/run3/meta.json` | — |
| T2.4 | run 3 | Verification | Chart Notes | `runs/run3/meta.json` | the verification sidecar |
| T2.5 | (fixed) | Calibration | Description | `cal/meta.json` | any `runs/*/meta.json` |
| T2.6 | (fixed) | Calibration | Chart Notes | `cal/meta.json` | the calibration sidecar |
| T2.7 | New run | Profiling | either | nothing yet — held until the run exists | any existing run's `meta.json` |

**T2.8 (U)** Read the table as: *the Profile run picks the folder, the Run type
picks the file.* A test enumerates all 6 live combinations and asserts the set
of files whose mtime changed is exactly one.
**T2.9 (I)** Switching either dropdown re-reads both fields from the new
location. Nothing is carried across.
**T2.10 (S)** Type in run 1, switch to run 2, switch back: run 1's text is
there and run 2's is its own.

---

## 3. The chart's sidecar — when it is written

| # | Event | `.channels.json` written? | With what |
|---|---|---|---|
| T3.1 | typing in either field | **no** | — |
| T3.2 | Generate Chart | yes | both fields as they are at that moment |
| T3.3 | auto-update preview redraws | **yes** | same — it is the same code path (`_generate_from_ti1(ti1, ask=False)`) |
| T3.4 | auto-update preview **declines** (run holds a measurement) | no | nothing is redrawn, so nothing is rewritten |
| T3.5 | measurement starts | copied into `chart/` with the rest of the chart | unchanged |

**T3.6 (U)** After T3.2 and after T3.3 the sidecar's two keys are identical for
identical field contents — the two paths cannot drift.
**T3.7 (S)** With auto-update on, change a layout knob, then read the sidecar:
the notes are in it.

---

## 4. Restore Used Chart — the rules, exactly as specified

| # | Restored chart's notes | Chart Notes field | Description field |
|---|---|---|---|
| T4.1 | non-empty | **replaced** by the chart's | **untouched** |
| T4.2 | empty | **kept as it is** | **untouched** |
| T4.3 | sidecar missing entirely | kept as it is | untouched |
| T4.4 | sidecar present but unreadable | kept as it is, and the log says so | untouched |

**T4.5 (U)** The description is never read back from a sidecar, in any path.
A test greps the code for a read of `description` from `.channels.json` and
fails if one appears — the two-sources-of-truth failure this rule exists to
prevent is not visible in behaviour until it bites.
**T4.6 (S)** Restore a chart whose notes differ from what is typed; the field
changes and the description does not.

---

## 5. Run lifecycle

| # | Action | Description | Chart Notes |
|---|---|---|---|
| T5.1 | **New run** | keeps the previous run's text (settings carry over) | keeps it |
| T5.2 | **Duplicate run** | copied, **prefixed** `(copy) ` | copied as-is |
| T5.3 | **Delete run** | goes with the run | goes with the run |
| T5.4 | Delete run 6 of 10 (renumbering) | run 7's text follows run 7 as it becomes run 6 | same |
| T5.5 | **Open project** | both fields fill from the current run | same |
| T5.6 | Project with no `meta.json` for a run | both empty, nothing written until edited | same |

**T5.7 (U)** T5.4 is the one that can silently mis-assign user text. A test
builds 10 runs with distinct descriptions, deletes run 6, and asserts every
surviving description is still on its own run.
**T5.8 (S)** Duplicate on screen and read the field: `(copy) ` is at the
**start**, where it can be seen without scrolling the field.

---

## 6. `-D`, the profile description

The spec's §4 and §4a.

### 6a. When the default is recomputed

| # | Event | `-D` empty | `-D` = ChromIQ's last default | `-D` = the user's own text |
|---|---|---|---|---|
| T6.1 | project name edited | recomputed | recomputed | **untouched** |
| T6.2 | run description edited | recomputed | recomputed | **untouched** |
| T6.3 | **Run type changed** | recomputed | recomputed | **untouched** |
| T6.4 | **calibration description edited** | recomputed | recomputed | **untouched** |
| T6.5 | **the build's calibration changed** | recomputed | recomputed | **untouched** |
| T6.6 | Profile run changed | recomputed | recomputed | **untouched** |
| T6.7 | project opened | recomputed | recomputed | **untouched** |
| T6.8 | Generate Chart | recomputed | recomputed | **untouched** |
| T6.9 | user clears the field by hand | recomputed on the next event above | — | — |

**T6.10 (U)** "The user's own text" is decided by comparison with the last
default ChromIQ itself wrote, remembered as a string. A test types a value that
happens to equal the current default, then changes the project name: the field
is recomputed, because it was indistinguishable from a default. **This is the
known, accepted limit of the rule** and is written down so it is not later
reported as a bug.

**T6.18 (U/I) — the guard does not exist yet, and this is where it is added.**
The consequence analysis said the "only when empty" rule was already in use at
`tab_profile.py:1278`. That line is `_pc_desc_edit`, the **printcal**
description; the field §4 is about is colprof's "Profile Description (-D)",
and there are two of them (`_desc_edit`, `_m_desc_edit`). `set_ti3_path`
overwrites **both, unconditionally**, so a description the user typed is lost
the moment a measurement is loaded or handed over from Measure. Pre-existing,
and corrected as part of this work — building §4 on a field that overwrites
the user would be building on sand.

| # | Field holds | A `.ti3` is loaded | Result |
|---|---|---|---|
| T6.19 | empty | any | filled with the new default |
| T6.20 | ChromIQ's last default | any | replaced by the new default |
| T6.21 | **the user's own text** | any | **untouched** |
| T6.22 | user's text, then cleared by hand | any | filled again — clearing gives it back |

### 6b. What it is built from

| # | Calibration feature | Build uses a calibration | Default `-D` |
|---|---|---|---|
| T6.11 | **off** | — | `<project>-<run description>` — **as today** |
| T6.12 | on | no | `<project>-<run description>` |
| T6.13 | on | yes | `<project>-<run description>-<calibration description>` |
| T6.14 | on | yes, calibration description empty | `<project>-<run description>` — no trailing hyphen |
| T6.15 | on | yes, run description empty | `<project>-<calibration description>` |
| T6.16 | any | both empty | `<project>` alone |

**T6.17 (U)** Every empty part drops out **with its separator**. Parametrised
over all 8 combinations of the three parts being empty or not.

---

## 7. `{rundescription}`

| # | Run type | Renders |
|---|---|---|
| T7.1 | Profiling | the run's description |
| T7.2 | Verification | the run's description — a verification shares its run's |
| T7.3 | Calibration | **the calibration's description** (spec R2 — not empty) |
| T7.4 | any, description empty | nothing, the way `{seed}` does on a chart with no seed |

**T7.5 (U)** A recipe saved before this feature, containing no such token, is
unaffected.
**T7.6 (S)** The token is in the Insert ▾ menu, and a chart generated with it
in the sheet text has the description **printed on the page** — read off the
rendered TIFF, not from the recipe.

---

## 8. Everything that must NOT change

The half of a test plan that catches regressions rather than proving features.

| # | With the calibration feature OFF | Must be |
|---|---|---|
| T8.1 | the Run type list | Profiling, Verification — no third item |
| T8.2 | `-D` | `<project>-<run description>`, no calibration part |
| T8.3 | `cal/meta.json` | never created, never read |
| T8.4 | the fields' labels | never say "Calibration" |

| # | Everything | Must be |
|---|---|---|
| T8.5 | `project.json` | unchanged — no per-run text in the manifest |
| T8.6 | schema version | **not bumped**; no migration runs |
| T8.7 | an older project | opens, both fields empty, nothing rewritten on open |
| T8.8 | a preset made before this | loads; chart notes still restore; no description in it |
| T8.9 | Restore Factory Defaults | resets the two defaults keys; **never** touches any run's stored text |
| T8.10 | file names | unchanged — the description is not in any stem |

**T8.11 (U)** T8.10 is asserted by generating a chart with a long description
full of punctuation and comparing every produced filename against the same
build with an empty description.

---

## 9. On-screen walk — the demo package

Each step is one row of the package's `README.md`, performable by hand with no
knowledge of the code. A step names: the starting state, the exact control, the
value to type, and what must then be visible.

| # | Step | Proves |
|---|---|---|
| S1 | open the demo project, read Run 1's description | T5.5 |
| S2 | switch to Run 2 and back | T2.10 |
| S3 | type into Run 2's description, switch away, return | T2.1, T2.9 |
| S4 | Build Profile: watch `-D` follow what was typed | T6.2 |
| S5 | type your own `-D`, change the run description again | T6.2's third column |
| S6 | Generate Chart, then read `.channels.json` | T3.2 |
| S7 | turn on auto-update, move a layout knob, read it again | T3.3 |
| S8 | Restore Used Chart on a run whose notes differ | T4.1, T4.6 |
| S9 | Duplicate the run | T5.2, T5.8 |
| S10 | switch Run type to Verification | T2.3, T2.4 |
| S11 | switch to Calibration (feature on) | T2.5, T2.6, F5, F6 |
| S12 | put `{rundescription}` in the sheet text and generate | T7.6 |
| S13 | delete run 6 of 10 | T5.4, T5.7 |
| S14 | turn the calibration feature off, check `-D` | T6.11, T8.1–T8.4 |

**Every S row is walked in the real app**, with the app's own fonts and style
applied as `main.py` applies them — a run without them measures a different
widget, which has already produced one wrong fix in this issue.

---

## 10. Method for anything that fails

Knut's instruction, kept where the tests are:

> *"For all bugs and failures found, study context of whole function to see the
> bigger picture on how things are affected. Make several theories for most
> probable cause of bugs and test them with above methodology, and retest,
> until functionality is as specified from specification."*

So, for each failure: read the whole function and its callers before proposing
anything; write down **more than one** theory; test each against the real app
rather than against a unit stub; fix; then re-run the whole affected table —
not just the row that failed. A fix that makes one row pass and is not re-run
against its table is how the sibling faults in §3 were introduced.
