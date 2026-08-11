# Per-target settings — specification

Issue #130. Source posts, in the order Knut listed them:

- [#issuecomment-5206901110](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5206901110) — the consequence analysis
- [#issuecomment-5207570325](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5207570325) — Knut's rulings on it (beta.157)

> **These specifications are binding.** Knut, 2026-08-06: *"These must always be
> consulted on changing code so that behaviour defined is not violated. And if
> faults are found that do not match with the specification [it] must be
> reviewed and approved."* So: read the relevant document before changing code
> in the area it covers, and if you find behaviour that contradicts it, **report
> it and get the change approved** rather than quietly correcting one side to
> match the other.

**Status: specification COMPLETE. Create Chart is IMPLEMENTED (beta.171); Measure, Build Profile and Calibration & Profiling are not yet.** Everything
below is either Knut's ruling quoted, or a consequence of one. The last two
open questions were answered on 2026-08-06 (§9); the next step is the test plan
in §8, then the build.

---

## 0. The problem, in his words

> *"It is important that all parameters that are not global … are stored when
> creating a chart. If some settings are saved and other not, then it is very
> confusing for a user when settings he never set for a run … suddenly change,
> and when the user wants to reproduce a chart or a profile build, he will not
> get the same result … having fields change randomly because some other
> run-specification changed something is similar to a global parameter in a
> programming code where several actors can change that parameter, but not know
> when or where."*

That last sentence is the specification. A per-target setting must have exactly
one writer — the target it belongs to — and it must never be written by the act
of looking at a different target.

**One third of it already exists.** A chart writes its own settings into
`<stem>.channels.json` and reads them back; that is what Restore Used Chart and
a re-opened project rely on. What is missing is that the tab does not consult it
when the *selection* changes — it keeps whatever is on screen. So the mechanism
is built. What changes is **when it is read and written**, and **which fields it
covers**. Build Profile, Calibration & Profiling and Measure have no such store
at all, and that is new work.

---

## 1. Global or per target — the dividing line

Knut's rule: *"everything that describes this chart or this measurement becomes
per run; everything that describes your setup stays global"* — with his
correction that it must be **all** of them, not a selection.

### 1.1 Stays global

| Setting | Why |
|---|---|
| Printer profile project name | it names the project, not one run |
| the preset selector itself | it is a way of *loading* settings, not a setting |
| ArgyllCMS binary path, language, appearance, sounds | your installation |
| Preferences → everything | your setup |
| the instrument and paper **defaults** in Preferences | the seed for a new target, not the target's own value |

### 1.2 Becomes per target

| Group | Where it lives today |
|---|---|
| every targen control (`-f`, `-B`, `-g`, `-s`, `-m`, …) | partly in `.channels.json` |
| every printtarg control (`-i`, `-p`, `-h`, `-P`, `-L`, …) | partly in `.channels.json` |
| the ChromIQ engine on/off, and its whole layout recipe | in `.channels.json` |
| **sheet text, its inserts, the clip border and its text** | in the recipe — Knut's own example |
| bit depth, compression, PDF export, stamp checkbox | partly |
| Auto patch count on/off, page count | partly |
| Build Profile: quality, algorithm, gamut settings, `-D`, manufacturer/model/copyright | **nowhere** |
| Calibration & Profiling: the printcal and applycal panels | **nowhere** |
| **Measure: patch-by-patch, `-T`, resume, skip calibration, and the rest of the Measure panel** | **nowhere** |

That last row is Knut's ruling on §4 below: *"measure tab must be included."*

**S1.1** The list of per-target widgets is generated from `_manual_widgets` and
the equivalent registry on each in-scope tab, never hand-written, so a parameter
added to `parameters.yaml` cannot be forgotten.

---

## 2. When settings are loaded

Knut asked for this to be pinned down and checked:

> *"Exact definition of when stored parameter settings are loaded, such as Open
> Project, open Chart file (ti2)?, activating any tab loads that tabs setup,
> changing 'Preset run' an 'Run Type' and 'Verification' fields etc… Verify what
> is correct to do."*

and gave the general rule:

> *"Load settings when activating tab, Save / write settings when leaving tab,
> and when main button for tab is pressed."*

Every load event below is that rule applied to one situation. The right-hand
column is the "verify what is correct to do" answer, with the reason.

| # | Event | What loads | Why this is correct |
|---|---|---|---|
| **L1** | **A tab is activated** | that tab's settings for the currently selected target | the general rule. It is also the only moment at which the tab is about to be *seen*, so it is the last moment the values can be made true |
| **L2** | **Open Project** | nothing immediately; every tab is marked stale, and the **visible** tab loads at once | a project change replaces the target. The visible tab is already "activated", so L1 applies to it now; the others apply theirs when the user gets to them |
| **L3** | **Profile run changes** (the bar) | as L2 | same reason — the target changed |
| **L4** | **Run type changes** (the bar) | as L2 | same reason |
| **L5** | **A chart file is opened / Restore Used Chart** | Create Chart loads the settings recorded in that chart's sidecar | the chart carries the recipe that produced it; restoring the sheet without its recipe is the bug this whole feature exists to remove |
| **L6** | **A preset is loaded** | the preset's values into the panels | unchanged behaviour. The preset is a *loader*, not a target |
| **L7** | **A `.ti1` or `.ti2` is loaded** | whatever that file carries | unchanged behaviour |
| **L8** | **App start** | the restored project's selection, then L2 | app start is Open Project with a remembered name |

**The Verification field is not a separate event.** Verification is a value of
Run type, so it is L4. Listing it separately would invite a second code path,
and a second code path is how the two sets of Chart Notes came to overwrite each
other in beta.150.

### 2.0 The scope of every load and every write

Knut, tightening the general rule (edit of 2026-08-06):

> *"Loading or saving parameters only applies for the run type and profile run
> selected."*

**One target is live at a time, and it is the one the bar names.** Every event
in §2 and §3 reads from, or writes to, that target and no other. There is no
event that touches a target the user is not looking at — not a sweep on Open
Project, not a flush on quit, not a fan-out that "keeps the other runs in step".

This is what makes the store safe. A per-target setting has exactly one writer,
and that writer only runs while its target is selected, so the failure Knut named
at the top — *"several actors can change that parameter, but not know when or
where"* — has nowhere to happen.

It also decides §2.1: the write that precedes a target change belongs to the
**outgoing** target, because that is the one still selected at the moment the
write is made. The load that follows belongs to the incoming one, because by
then it is.

### 2.1 The hazard the load rule creates

**A target change must write the outgoing target before it loads the incoming
one.** If it does not, the on-screen values still belong to the old target when
the user later leaves the tab — and §3's write-on-leave would then record the
old target's edits **onto the new target**. That is exactly the "several actors
can change that parameter" failure Knut described, reintroduced by the fix for
it.

So L2/L3/L4 are each a write (W6) followed by a load, in that order, in one
guarded step — the write against the outgoing target, the load against the
incoming one, each while it is the selected one (§2.0).

---

## 3. When settings are written

Knut's general rule, in full:

> *"Load settings when activating tab, Save / write settings when leaving tab,
> and when main button for tab is pressed (Build Profile for Build Profile Tab
> and Calibration and Profiling tab; Start Measurement / Continue Measurement
> for Measure tab, Generate Chart for Create Chart Tab)"*

| # | Event | Writes |
|---|---|---|
| W1 | **Generate Chart** | Create Chart's settings for that target |
| W2 | a preset is loaded | same — the preset has just decided them |
| W3 | a `.ti1` is loaded | same |
| W4 | a `.ti2` is loaded | same |
| W5 | auto-update preview redraws | same (the same code path as W1) |
| W6 | **leaving a tab** — including a target change (§2.1) and app quit | that tab's settings for the target being left |
| W7 | **Build Profile** pressed | tab 4's settings — the Build Profile module and the Calibration & Profiling module alike |
| W8 | **Start Measurement / Continue Measurement** pressed | the Measure tab's settings |

**Not on every keystroke.** W6 is the widest of these and it is still an event,
not a timer: what is stored is the state of the tab at a moment the user
finished with it, never what someone was in the middle of typing.

### 3a. How a write is triggered, and what it costs

Knut's queue design (2026-08-06), and the ordering is the substance of it:

> *"Writing queue request trigger could be when pulldown list of 'Profile run'
> or 'Run type' is clicked to see the pulldown menu, and reading queue request
> trigger could be when an option in the pulldown list is clicked/selected."*

| # | Rule |
|---|---|
| **Q-1** | The **write** fires when a target-changing pulldown **opens**. At that moment the outgoing target is still selected, so the values on screen are filed against the target they belong to. `currentIndexChanged` is already too late — the selection has moved |
| **Q-2** | The **read** fires when an option is **selected** |
| **Q-3** | A read never overtakes its write: the write is complete before the selection changes, because opening the list precedes choosing from it |
| **Q-4** | *"A write trigger should also have a check if any settings have changed since last write, preventing multiple writes in a row if user is going back and forth."* The last snapshot written is remembered per target, so a repeated trigger costs nothing — not even a read of `meta.json` |
| **Q-5** | Every write is **atomic**: written to a temporary file in the same directory, `fsync`-ed, then renamed over the original. A crash mid-write cannot truncate it, and a failed write leaves the previous contents intact |

**Threads.** Knut suggested `ThreadPoolExecutor` and OS file locking. Neither is
used, and the reasoning is recorded here because it is a deliberate departure:
every read ends in touching widgets, which Qt permits only on the GUI thread, so
a worker would have to hand back anyway; the write is a small JSON file well
under a millisecond; and this project has twice lost a full test run to
`QThread` lifetime bugs. Locking guards against a second **process**, which does
not exist while ChromIQ owns one project. Ordering, serialisation and atomicity
are what make this safe, and none of the three needs a thread.

**App quit counts as leaving the visible tab.** Qt does not raise a tab-change
for it, so it is wired explicitly; otherwise the last tab the user worked in is
the one tab that never records anything. It writes **that tab, for the selected
target** — §2.0 — never a sweep across the other tabs or the other runs.

---

## 4. What a target with nothing stored opens on

Knut's ruling: **factory settings, or the saved defaults if the user has any** —
never the last run's.

| # | Case | Opens on |
|---|---|---|
| S1 | run N, Profiling, settings stored | **its own** |
| S2 | run N, **Verification**, settings stored | **its own** |
| S3 | **Calibration**, settings stored | **its own** |
| S4 | run N, Profiling, **nothing stored** | saved defaults, else factory |
| S5 | run N, **Verification**, nothing stored | saved defaults, else factory |
| S6 | New run, Profiling | **seeded from the loaded run** — see §4a |
| S7 | New run, Verification | **seeded from the loaded run** — see §4a |
| S8 | Calibration, nothing stored | saved defaults, else factory |
| S9 | a run made before this feature | saved defaults, else factory, and it records its own the first time it is used |

S2–S5 are the rows Knut added: *"Missing cases (some cases can occur if user
deletes a file)."* His parenthesis is the important part — **a target with a
store is not the same as a target whose store is readable.** A deleted or
truncated `meta.json` must land on S4/S5/S8, not on an error and not on the
previous target's values.

**This reverses §5 T5.1 of the description spec**, which said a New run inherits
what is on screen. His reason overrules that one: *"the situation is chaotic and
unrecognisable for a user if settings change arbitrarily for a run, seen from
his view point."* Save as Defaults is the answer to the case the old rule was
protecting.

### 4a. "New run" is seeded from the run you were on

Knut, 2026-08-06:

> *"When profile run = New run, I suggest the currenly loaded run … is copied at
> the same time to a temporary set of settings … Then, if a user happens to
> select 'New run' that block of settings is read on selection, displayed on
> screen (no visible change for the user), which then can be modified by user to
> what is desired for the new run. Then when Generate Chart is pressed, all
> these settings are copied into the new runs parameter slot."*

This sharpens S6/S7 rather than overturning them. His earlier reason for
defaults — *"the situation is chaotic … if settings change arbitrarily for a
run"* — was about an **existing** run changing behind the user. That stays
impossible. A New run is not a run; it is the specification for one, and
seeding it from what is already on screen is continuity, not arbitrariness.
Making a new run is nearly always *"like the last one, with one change"*.

| # | Rule | Why |
|---|---|---|
| **N-1** | The block is seeded **only when it is empty** | Re-seeding on every click would overwrite the user's own New-run setup the moment they flicked to another run and back — silently |
| **N-2** | The six rows in `_CAL_VALUES` are **stripped** from the seed | Seeding while Run type = Calibration would copy a calibration sheet's patch set into a profiling run |
| **N-3** | **Generate Chart** copies it into the new run and **clears** it | Otherwise the run after next inherits a stale copy instead of the run actually loaded |
| **N-4** | It lives in **`<target>/cache/new_run.json`** | Knut, 2026-08-07: *"always … in the cache/ folder for the runN/ runN/verifications/ or cal/ folders"*. The layout already documents `cache/` as "always safe to delete", which is exactly this file's nature — an orphaned block after a restart costs nothing, because the New run simply seeds fresh |
| **N-5** | A New run under Run type = **Verification** seeds from the **verification** | Knut, 2026-08-07: *"Answer: Yes"* |
| **N-6** | **A calibration never seeds the block at all** — no `new_run.json` is written into `cal/` | Knut, 2026-08-08: the seeding *"should only work for profiling and verification runs"*. N-2 alone did not achieve this: stripping the six `_CAL_VALUES` rows still left **34** others — paper, instrument, margins, the whole layout recipe — which a later New run would have started from. **The rule is Knut's; that the code now obeys it is ⏳ awaiting confirmation — see below** |

**Status:** built and wired (v3.14.8-beta.204); ⏳ awaiting confirmation that the
behaviour is right.

### ⏳ Awaiting confirmation — observed on screen 2026-08-08, not yet confirmed by a human

**Confirmed by:** *nobody yet.* This section is a **candidate** for the
specification and must not be read as settled.

Knut asked for correct behaviour to be written into the specification — and then
qualified it the same day, which is why this section is marked the way it is:

> *"Be careful though, only the behavior that you confirm as correct, after bugs
> are confirmed fixed, should be written into the design specification.
> Otherwise the specification looses its value with lots of trash Claude thinks
> is correct behavior."*
>
> *"This means you have to respond to say if a bug is fixed and behavior is now
> correct."*

So the gate is **a human's confirmation, not the assistant's own verification**.
An on-screen run proves what the app *does*; only Knut or Sebastian can say that
what it does is what it *should* do. This section was first written as "✅
Confirmed behaviour" on the assistant's own authority, which is exactly the
failure mode Knut names, and was demoted on the same day.

**Promotion rule:** when Knut or Sebastian replies that the behaviour is right,
this section is renamed to `## Confirmed behaviour`, gains a
`**Confirmed by:** <name>, <date>` line, and only then becomes binding.
`tests/test_design_specs_are_binding.py` fails on a confirmed section that names
nobody.

Driven through the real app against the Argyll-built `Demo-Full-RGB`
(`scripts/drive_new_run_seeding.py`, 11 checks):

| Observed | Result |
|---|---|
| Select a run, then **New run** | The New run opens on that run's settings — the "copy a chart without saving a preset" route Knut describes. **Works.** |
| Select run A, then run B, then **New run** | It follows **B**, the last selected run — not A, and not the project's `current_run`. **Works.** |
| Visit Run type = **Calibration**, then **New run** | No block is written into `cal/`, so the New run keeps the last *run's* settings. **N-6.** |

**Two traps this cost, both worth keeping written down.**

*Comparing a value proves nothing here.* The block is written once and then left
alone (N-1), so whether a calibration value leaked depended on **when** the
block happened to be written, not on whether calibration was excluded. A
value-comparison check reported a false pass. The question that means something
is structural: *is a block written into `cal/` at all?*

*The guard must come from the store, not the selection.* Seeding runs for the
**outgoing** target while the bar already points at the incoming one, so
`_target_ctl.target.is_calibration()` answers about the wrong target. The first
version of the guard did exactly that, passed its unit test, and still wrote the
file on screen. `isinstance(store, Calibration)` is the reliable question —
the same lesson as beta.165 and the three per-target-settings faults before it.

---

## 5. Scope

**In scope: Create Chart, Measure, Build Profile, Calibration & Profiling.**
Print Chart and Check & Refine *"can be kept as is for now"*.

Measure was out of scope in the analysis and Knut put it in — *"Add measure tab
too"*, and, on the §1 list, *"Looks ok, but measure tab must be included."* The
analysis had already flagged it as the next candidate, because two of his own
reports came from exactly this: the `-N` that survived from an earlier session,
and the resume tick that disagreed with itself.

| Tab | In scope | Store |
|---|---|---|
| 1. Create Chart | ✅ | `<stem>.channels.json` (extended) |
| 2. Print Chart | ❌ for now | — |
| 3. Measure | ✅ | `runs/runN/meta.json` / `cal/meta.json` |
| 4. Build Profile / Calibration & Profiling | ✅ | `runs/runN/meta.json` / `cal/meta.json` |
| 5. Check & Refine | ❌ for now | — |

---

## 6. What this touches

| # | Feature | Impact |
|---|---|---|
| 1 | `.channels.json` | gains the fields it does not yet carry. Old charts load with what they have; the rest come from defaults |
| 2 | Restore Used Chart | **improves** — restoring a chart restores the settings that made it |
| 3 | Duplicate run | the copy takes the source's settings, since it takes the source's chart |
| 4 | Delete + renumber | settings follow their run, like `meta.json` |
| 5 | Presets | unchanged. A preset still loads into the panels; W2 then records it for the target |
| 6 | Save as Defaults | unchanged, and more useful: it is now the answer to "start every new run like this" |
| 7 | Restore Factory Defaults | unchanged; resets the defaults, never a target's stored settings |
| 8 | Build Profile | needs a store of its own — `runs/runN/meta.json` |
| 9 | Calibration & Profiling | the same, in `cal/meta.json` |
| 10 | Measure | the same store as 8/9, a separate key |
| 11 | project.json | untouched |

---

## 7. The two risks, stated plainly

**A. A stored setting that no longer exists.** A chart made today, opened after
a parameter is renamed or removed. The loader ignores what it does not
recognise rather than failing — the rule `RunMeta.from_dict` already follows.
Knut's *"some cases can occur if user deletes a file"* is the same risk from the
other end, and gets the same answer: fall through to S4/S5/S8.

**B. Loading settings must not trigger a rebuild.** Filling twenty widgets fires
twenty `changed` signals, and with auto-update on that would redraw the chart —
possibly over a measured one. The fill is guarded the way
`_set_target_text_fields` already guards the two text fields. This is the one
that would actually hurt, so it gets its own test.

**C. (added by §2.1) A load that runs before its write.** Covered by making the
target change one guarded write-then-load step.

---

## 8. The test requirement

Knut's, verbatim, and it is stricter than a normal feature's:

> *"The testing of the implementation must verify by on-screen control of app
> that changing every parameter (non-global) in every tab included in this
> specification is recorded in the log correctly (with set value) in reference
> to set value on-screen and that each parameter has the correct stored tag and
> value in the relevant json file. Both empty/disabled and filled/enabled values
> shall be tested. The test plan and actual tests shall also verify updating of
> every single parameter before and after writing to json file, and that loading
> of settings file happen at the exact correct events and times, such as on
> enabling any of the tabs etc."*
>
> *"Expand demo project package with tests to verify loading and saving of
> parameters from all input sources / activation events."*

Read as requirements:

| # | Requirement |
|---|---|
| **R1** | **On-screen**, driving the real window — not a fixture. Every non-global parameter on every in-scope tab. |
| **R2** | For each parameter: the **on-screen value**, the **logged value**, and the **JSON tag and value** must agree. Three-way, not two. |
| **R3** | Each parameter tested **empty/disabled and filled/enabled**. A control that stores nothing when it is off must be shown to store nothing, and to come back off. |
| **R4** | Each parameter checked **before and after** the write, so a value that only appears to be stored is caught. |
| **R5** | Loading is verified to happen **at exactly the events in §2 and at no others** — including that activating a tab loads, and that typing does not. |
| **R6** | The demo project package gains steps that exercise **every input source and activation event** in §2 and §3. |

**R1 is the reason this is not a unit-test task.** The parameter list is
generated (S1.1), so the test is generated from the same list: every widget the
registry yields is driven, and a parameter added later is tested automatically
or the test fails for not knowing what to do with it.

**R3 has a trap worth naming now.** "Empty" and "absent" are different in JSON,
and `-D ""` is not the same as no `-D`. The store records which of the two it
is, and R3 checks both directions.

---

## 9. What is settled and what is not

**Settled** (Knut, beta.157):

1. §1 list is right, **with Measure added**.
2. Write on **leaving a tab** and on the tab's **main button** — Generate Chart,
   Build Profile, Start/Continue Measurement.
3. Measure is **in** scope.
4. The four missing rows in §4 (S2–S5).

**Answered 2026-08-06 — nothing is open:**

| # | Question | Knut's answer |
|---|---|---|
| **Q1** | Are **page count** and **instrument/paper** per target, or per project? | *"yes, per target"* — §1.2 stands as written |
| **Q2** | On **app quit** (§3, W6): write silently? | *"yes, write silently"* — no prompt, no notice |

**The specification is therefore complete and the next step is the test plan**
(§8, R1–R6), then the implementation, in that order — Knut's own sequencing.

---

## 10. The 2026-08-11 rulings — run-type store split, visible-tab reload, sidecar precedence

The on-screen switching drive (`scripts/drive_per_target_settings.py`, the
driver §8/R1 called for) found two faults on 2026-08-11; both were reported
and Knut ruled on them the same day. **His rulings are binding design.**

**F1 — a verification's settings are its own.** Knut:

> *"I think the verification chart shall have its own settings, separate from
> the profile run's settings, and when a verification chart is stored in the
> verifications/<date_time>/chart/ folder when a measurement starts, the
> settings are also backed up with the chart, thus can be restored."*

So the §5 store column reads, per run type: Profiling → `runs/runN/meta.json`;
**Verification → `runs/runN/verifications/meta.json`** (one set per run's
verification tree, shared by its dated checks the same way the chart is);
Calibration → `cal/meta.json`. The two description/notes TEXT fields are not
part of this ruling — they stay on the per-run description design (§9 Q4).

**F2 — every tab saves and reloads the same way.** Knut:

> *"All tabs must save-on-change-from/reload-on-change-to a tab, and each tab
> must also save and reload in the same manner that Create Chart does, using
> same method and trigger mechanism (click on any of the profile run or run
> type input boxes is saving settings of current tab open and visible, and
> selecting an actual value in the pull down lists loads the settings of the
> tab selected to be loaded.) Same principle, same method."*

This is §2 L3/L4's "the visible tab loads at once", now wired centrally in
MainWindow (`changed` → `_load_settings_of_visible_tab`) beside the existing
write trigger (Q-1). Before the fix, Measure and Build Profile kept the OLD
target's values while visible and then filed them onto the new target — the
§2.1 corruption from the load side.

**Sidecar precedence (the L5/L4 question).** Knut:

> *"The charts sidecar is the correct value to use. When a chart is restored,
> the chart sidecar will overrule the settings for the chart for that
> specific run type."*

### ⏳ Awaiting confirmation — implemented 2026-08-11, not yet confirmed by a human

**Confirmed by:** *nobody yet.*

- The store split is implemented in `workflow.per_target_settings
  .store_for_target`; the settings file at the root of `verifications/` is a
  chart **side file** (`CHART_SIDE_FILES`), so the measurement-start snapshot
  backs it up into `<date_time>/chart/` and Restore Used Chart restores it,
  archiving the replaced live file into `old/` first. A snapshot from before
  this feature (no settings backup) leaves the live settings untouched. A
  verification chart Replace archives the chart and keeps the settings live.
  A settings edit never makes a dated check look like "a different chart".
- The visible-tab reload is central and covers every storing tab; verified on
  screen by standing on Build Profile through run1→run2→run1→run2.
- Existing projects: settings written before the split (under either run
  type) stay in `runs/runN/meta.json` and now belong to Profiling; a
  verification target starts on defaults (§4 S5) and records its own from
  first use. No files are moved by migration.

## 10a. Related documents

- [`per_run_description.md`](per_run_description.md) — the description field; §5 T5.1 of it is reversed by §4 here
- [`measurement_exit_strategy.md`](measurement_exit_strategy.md) — every window that can end a measurement
- [`unified_measurement_management.md`](unified_measurement_management.md) — the model these all sit inside
- [`per_target_settings_test_plan.md`](per_target_settings_test_plan.md) — **the test plan for this document** (R1–R6 worked out)
- [`dev_folder_layout.md`](../dev_folder_layout.md) — where `meta.json` and the chart sidecars live
