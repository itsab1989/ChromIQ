# Per-run description — Test Plan Specification

> **These specifications are binding.** Knut, 2026-08-06: *"These must always be
> consulted on changing code so that behaviour defined is not violated. And if
> faults are found that do not match with the specification [it] must be
> reviewed and approved."* So: read the relevant document before changing code
> in the area it covers, and if you find behaviour that contradicts it, **report
> it and get the change approved** rather than quietly correcting one side to
> match the other.

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

🆕 **The labels were rewritten after Knut's beta.144 report.** Three kinds of
chart can be under the notes field — the run's chart, the verification chart,
the calibration chart — and the label has to say which:

> *"each time the 'Profile run' and 'Run type' changes, the correct text field
> shall be shown, which is specific for the run's chart, the verification run's
> chart and the calibration's chart. The 'Run N Description' is specific only
> for Profiling run and for Calibration."*

| # | Profile run | Run type | Label | Working value | Authoritative copy | Shown in |
|---|---|---|---|---|---|---|
| F1 | run N | Profiling | **Run N Description:** | `runs/runN/meta.json` | the run | Guided + Manual |
| F2 | run N | Profiling | **Run N Chart Notes:** | `runs/runN/meta.json` | the chart's `.channels.json` | Manual only |
| F3 | run N | Verification | **Run N Description:** | `runs/runN/meta.json` of the run being verified | the run | Guided + Manual |
| F4 | run N | Verification | 🆕 **Verification Chart Notes:** — no run number | `runs/runN/meta.json` | the **verification** chart's sidecar | Manual only |
| F5 | — | Calibration | **Calibration Description:** | `cal/meta.json` | the calibration | Manual only¹ |
| F6 | — | Calibration | 🆕 **Calibration Chart Notes:** — no run number | `cal/meta.json` | the calibration chart's sidecar | Manual only¹ |
| F7 | 🆕 New run | Profiling | 🆕 **Run N+1 Description:** / **Run N+1 Chart Notes:** | held until the run exists | — | Guided + Manual |
| F8 | 🆕 New run | Verification | 🆕 **Run N+1 Description:** / **Verification Chart Notes:** | held until the run exists | — | Guided + Manual |

¹ Calibration is manual-only by #137, so "Manual only" is the whole of it.

🆕 **N+1, not "New run".** The earlier agreement was that a run which does not
exist yet says "New run Description:". Knut superseded it, and gave the reason:

> *"when i look at 'Location being edited' that updates to /run N+1/ in the
> path, to signify the expected new run number. This could be done also for the
> labels so that they become 'Run N+1 Description' or 'Run N+1 Chart Notes'."*

So the number comes from `Project._next_run_index()` — **the same call the
folder line uses** — and the two cannot disagree.

🆕 **Why the verification notes carry no number**: *"only one verification chart
and we know it is for the run it belongs to"*. The run is already named by the
description row directly above.

🆕 **The description is SHARED between Profiling and Verification.** Knut spelled
this out when asked (2026-08-05 23:43):

> *"The 'Run N Description' is specific for Profiling run (Run type = Profiling
> and any numbered run selected in "Profile run"), and 'Run N Description' is
> specific for Calibration (Run type = Calibration, at which "Profile run" is
> not relevant). When a specific run is selected for Profile run, then 'Run N
> Description' is shared with (common with) any verification run (Run type =
> Verification)."*

There is therefore no separate verification description: switching to
Verification leaves the description row reading **"Run N Description:"** and
editing the run's own text. Only the notes row follows the chart. Rows F3 and
F8 are that rule.

**T1.1 (U)** `RunMeta` gains `description: str = ""` and `chart_notes: str = ""`.
A `meta.json` written before this feature loads with both empty and is not
rewritten until something changes.
**T1.2 (U)** `Calibration` meta gains the same two keys, same defaults.
**T1.3 (I/S)** The label text follows Run type on the same signal the rest of
the bar follows, with no tab switch needed to see it change. Profiling →
Verification → Profiling on one run changes the notes label each time.
**T1.4 (I/S)** 🆕 With the run not yet created, both labels read **N+1**, and
the number equals the one in "Location being edited".
**T1.5 (I)** 🆕 The rows are labelled for the selection the app OPENS on, not
only after the first change — they are built before the bar exists, so the tab
re-labels them when the controller is attached.
**T1.6 (I)** 🆕 The fixed-width label column fits every label in the table; a
column measured for one of them clips the rest.

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

## 4b. The Profile Description is per run 🆕 **beta.148**

Knut, beta.148, after typing his own `-D` for run 3 and finding it on every run:

> *"Every run has its own values. When I change to run 1, then the Profile
> Description … is still the default value … because I did not change the
> Profile Description … for that run. Emptying the Profile Description … will
> re-enable the automatic generation … for that specific run."*

| # | State of `runN/meta.json` `profile_description` | What the field shows |
|---|---|---|
| D1 | empty | the automatic `<project>-<run description>`, recomposed each time |
| D2 | set | that text, verbatim |
| D3 | emptied by the user | back to D1, for that run only |

**T4b.1 (U)** Typing stores the text on the selected run — and on **no other**.
**T4b.2 (I/S)** Switching Profile run replaces the field with that run's own
value; an override typed for run 3 is not visible on run 1.
**T4b.3 (U)** Typing the automatic value is **not** an override: it is stored as
empty, so the run's description still drives the name afterwards.
**T4b.4 (I/S)** Run type = Calibration composes `<project>-<Calibration
Description>` and follows it as it changes, and takes its own override.
**T4b.5 (I)** The store is the same one §2a names: the run, or the calibration,
never both.

---

## 5. Run lifecycle

| # | Action | Description | Chart Notes |
|---|---|---|---|
| T5.1 | **New run** | ~~keeps the previous run's text~~ → **empty** | ~~keeps it~~ → **empty** |
| T5.2 | **Duplicate run** | copied, **prefixed** `(copy) ` | copied as-is |
| T5.3 | **Delete run** | goes with the run | goes with the run |
| T5.4 | Delete run 6 of 10 (renumbering) | run 7's text follows run 7 as it becomes run 6 | same |
| T5.5 | **Open project** | both fields fill from the current run | same |
| T5.6 | Project with no `meta.json` for a run | both empty, nothing written until edited | same |

**T5.1 is superseded.** It said a New run inherits what is on screen, on the
grounds that settings carry over. Knut reversed that in the per-target settings
ruling — *"the situation is chaotic and unrecognisable for a user if settings
change arbitrarily for a run, seen from his view point"* — and a description is
a per-target field like any other. A text field has no factory value other than
empty, so **a New run opens on empty in both boxes**, and the text typed there
is still saved to the run Generate Chart creates (K1, which is unaffected).
See [`per_target_settings.md`](per_target_settings.md) §4.

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
| S15 | 🆕 set Profile run = New run and read both labels | F7, T1.4 |
| S16 | 🆕 with New run selected, switch Run type to Verification | F8 |
| S17 | 🆕 compare the label's number with "Location being edited" | T1.4 |
| S18 | 🆕 open the app cold and read the labels before touching the bar | T1.5 |
| S19 | 🆕 New run + type in both boxes + **Generate Chart** | T5.9 |
| S20 | 🆕 New run + type in both boxes, then look at every existing run | T5.10 |
| S21 | 🆕 Calibration + type in both boxes + **Generate Chart** | T5.11 |
| S22 | 🆕 **Duplicate** a run, then press Generate Chart | T5.12 |
| S23 | 🆕 Run type = Calibration, read "Location being edited" | T1.7 |

**T1.7 (I/S)** 🆕 With Run type = Calibration the folder line reads
`…/<project>/cal/`. A calibration is not in a run, so naming one pointed at a
folder nothing was being written to (Knut, beta.147).

**T5.9 (I/S)** 🆕 Text typed while "New run" is selected is written into the run
**Generate Chart creates**, and stays on screen afterwards. There is nowhere to
save it until that moment, so it is held in the fields and flushed by
`_align_current_run_to_target` **before** the bar moves to the new run —
otherwise the re-read that follows finds an empty file and blanks both boxes.
**T5.10 (U/I)** 🆕 …and it is never written into an existing run in the
meantime. `resolve_run` answers "the current run" when the selection names
none, which made every keystroke land on somebody else's description.
**T5.11 (U/I)** 🆕 Generating a calibration chart archives the previous
calibration; `cal/meta.json` is **copied** into the archive and the live one
stays, so the two fields survive the rebuild.
**T5.12 (I)** 🆕 A chart inside the open project is never "loaded from
elsewhere". Duplicate shows the copy through the same call the Print/Measure
"Open Chart File" path uses, and that state makes Generate Chart refuse to run.

**Every S row is walked in the real app**, with the app's own fonts and style
applied as `main.py` applies them — a run without them measures a different
widget, which has already produced one wrong fix in this issue.

---

## 9b. What beta.148 found, written down so it cannot be missed again 🆕

Every one of these came out of one report, and five of the six are the same
shape: **something the user typed or chose was thrown away.**

| # | Rule | Test |
|---|---|---|
| K1 | Text typed while "New run" is selected is saved to the run **Generate Chart creates**, and stays on screen | T5.9 |
| K2 | …and is never written into an existing run in the meantime | T5.10 |
| K3 | A calibration keeps its Description and Chart Notes across a chart rebuild — `cal/meta.json` is copied into the archive, never moved | T5.11 |
| K4 | A chart inside the open project is never "loaded from elsewhere", so Generate Chart is never blocked by it | T5.12 |
| K5 | Duplicate copies the description with **`(copy) `** at the start, and the chart notes verbatim | T5.2 |
| K6 | `cal/old/<date>/` holds only what cannot be regenerated — the measurement, the `.cal`, any profile. The chart is replaced, as a run's is | T5.13 |
| K7 | Starting a calibration measurement copies its chart into `cal/chart/`, as a run copies into `runN/chart/` | T5.14 |
| K8 | Restore Used Chart puts the **Chart Notes** back, for a run, a verification and a calibration alike — and writes them to that target's own meta | T4.7 |
| K9 | A chart with no notes leaves the notes field alone | T4.2 |
| K10 | The Profile Description is per run | §4b |
| K11 | "Location being edited" names `cal/` under Run type = Calibration | T1.7 |

**T5.13 (U)** After a calibration rebuild, `cal/old/<date>/` holds the `.ti3`
and the `.cal` and **not** the `.ti1`/`.ti2`; `cal/chart/` is untouched.
*(K6's second sentence — "The chart is replaced, as a run's is" — is now true of
an UNMEASURED calibration chart as well, following the owner's ruling of
2026-09-02: it is set aside for the length of the build and then dropped,
exactly as a run's is, and no dated folder is made for it. A MEASURED
calibration still keeps its chart, one level down in
`cal/old/<date>/chart/`, which is the compromise `fe92ed1f` reached so that the
dated folder's own listing stays as K6 asked. T5.13 is unchanged and still
passes.)*
**T5.14 (I)** Starting a calibration measurement writes `cal/chart/`.
**T4.7 (I)** Restore writes the notes into the run/verification/calibration meta
as well as into the field, so the refresh that follows cannot undo it.

---

## 9c. What beta.150–157 found 🆕

The second round of Knut's reports. Same shape as 9b — text or a name going
missing — plus two that were mine, introduced by the beta.149 fixes themselves.

| # | Rule | Fixed in |
|---|---|---|
| K12 | **A run and its verification keep separate Chart Notes.** They are two different sheets of paper; editing one changed the other. Stored as `verify_chart_notes`. The **description stays shared**, by Knut's earlier ruling | beta.153 |
| K13 | **Text typed for a "New run" survives a detour to another tab.** It has nowhere on disk to live yet, so it is held in memory until the run exists | beta.153 |
| K14 | **Emptying Profile Description hands the composed name back immediately**, not at the next change of Profile run — and the name is recomposed on arrival at tab 4, because both halves of it live on other tabs | beta.153 |
| K15 | **The Create Calibration File module's own "Description (-D)"** is composed from the project name and the Calibration Description, and kept in step with the other two. It is printcal's `-D` — a different field from the Build Profile module's, and they had been confused once | beta.153 |
| K16 | **Restore Used Chart acts on the calibration** when that is what is selected. `restore_state` knew about calibration; `restore_target` did not, so the button could be offered for the calibration chart and put a **run's** chart back | beta.153 |
| K17 | **Every dialog that names tab 4 takes the name from one call.** Qt reads `&` in button text as the mnemonic marker and ate it — "GO TO CALIBRATION _PROFILING TAB" — and the rename had been made in one dialog of three | beta.153 |
| K18 | **Stopping a calibration measurement no longer changes tab.** `main_window` navigated for *every* calibration `.ti3`, however the session ended | beta.153 |
| K19 | **Tab 4's Run type bar is live, and "Verification" is greyed inside the list** with a tooltip saying which tab to use, rather than the user being moved off the tab | beta.158 |

K17 is worth keeping visible: the test file for popup buttons already documented
the `&&` convention on "Save Partial && Quit", and the fix walked past it.

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
