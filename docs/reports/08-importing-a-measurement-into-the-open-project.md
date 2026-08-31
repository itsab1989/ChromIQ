# Loading a measurement while a project is open

STATUS: challenged-2 — see the two Challenge sections at the end (2026-08-31). No code written.

**RELEASE GATE (Basti, 2026-08-31): beta 6 is NOT tagged until this feature is
built.** The round-4 fixes (the prebuilt routes' missing name validation, the
stranded "you already have a project with this name" line, the Windows-reserved
names, the folder-name preview and the collision notice in the name dialog) are
finished and gate-green on master, uncommitted — they ship WITH this, not
before it.

Basti, 2026-08-31: when a project is open and the user loads a measurement in
Build Profile (and maybe Check & Refine, and maybe an ICC there too), should
ChromIQ ask whether to **build from the loaded measurement alone** or **import
it into the open project**?

---

## 1. What happens TODAY (verified, cited)

**Nothing ever consults the open project.** Every route decides from WHERE THE
FILE IS.

| Route | Code | Today |
|---|---|---|
| Build Profile → `.ti3` | `ui/tabs/tab_profile.py:4210` → `ui/ti2_loader.py:919 resolve_ti3` | inside a project → used in place; outside → **a new project is created** |
| Build Profile → `.txt` (i1Profiler) | `tab_profile.py:4289` → `ui/txt_loader.py:42` | outside → asks for a name, writes `working_dir/<name>/` (`txt_loader.py:281`) — **a new project** |
| Build Profile → `.mxf` / `.cxf` | `tab_profile.py:4251 _import_i1profiler_cxf` | converted to `.ti3` in a **temp folder**, then loaded like an external `.ti3` → same as row 1 |
| Check & Refine → `.ti3` | `ui/tabs/tab_check_refine.py:1210` | **the same `resolve_ti3`** — Basti's guess was right |
| Check & Refine → `.icc` | `tab_check_refine.py:1222 _on_browse_icc` | **referenced in place. Never copied, never imported, the project never learns of it** |

`resolve_ti3`'s own docstring says it plainly: *"either the original (when the
file is already inside a structured project) or a newly copied path inside a
freshly-created project"*. And `tab_profile.py:4237`: *"An external .ti3 … gets
imported into a fresh project."* So the behaviour is deliberate and documented
— it simply predates the question being asked.

### The asymmetry nobody asked for
A `.ti3` loaded from the Desktop is **copied into a project**. An `.icc` loaded
from the Desktop in the same tab is **only referenced**. So a verification
report can be built against a profile that lives outside every project, and
which can move or be deleted with the project keeping no record. Principle 11
(consistency) says these two should not differ; principle 5 (files land in
obvious places) says the report's inputs should be findable later.

### The destructive path already found (report 04/05, H)
`txt_loader.py:331`'s "Overwrite existing folder" is `shutil.rmtree` on a whole
project, while `ti2_loader`'s "Replace" archives to `old/`. Same word, opposite
consequence, and it is what the user is offered if they try to import a
measurement under a name that already exists. Principle 4 says user work is
archived, never deleted. **Any new import flow must not inherit this button.**

---

## 2. The proposal, as I would build it (TO BE CHALLENGED)

When a measurement is loaded **from outside any project** and **a project is
open**, ask once:

- **Add it to “<open project>”** — the measurement is COPIED in (never moved:
  the file the user chose stays where they put it), converted to `.ti3` if it
  came from i1Profiler, and the profile is built inside that project.
- **Make a new project for it** — today's behaviour, unchanged.
- **Cancel.**

With an info text saying, in plain words, what each choice means for where the
files end up.

### Numbered open questions (nobody may answer these silently)
1. **Which run does an imported measurement join?** A project holds runs
   (`runs/run1/…`). Does importing create a NEW run, or land in the current
   one? A measurement is the defining artefact of a run, so "new run" looks
   right — but that must be confirmed against `docs/design/per_target_settings.md`
   and the #130 run model.
2. **What is it called inside the project?** CLAUDE.md: the chart's files carry
   the sanitised project name as their stem, and derived files are role-named.
   An imported measurement has neither a chart nor a stem of its own.
3. **Does it apply to Check & Refine as well?** Same loader, so the same
   question arises — but the tab's purpose differs (checking a profile, not
   building one). Should the answer be the same?
4. **The `.icc` in Check & Refine** — copy it in too, or keep referencing it?
   Copying makes the report self-contained; referencing avoids duplicating a
   profile the user installed system-wide.
5. **Should "import" ever MOVE?** I say never — copy only. Confirm.
6. **What if the open project already has a measurement in the run?** The
   §S4.7 / displacing-results machinery exists for exactly this; reuse it,
   never a new question.
7. **Is a converted i1Profiler measurement stored as `.ti3` only, or is the
   original `.txt` / `.mxf` kept beside it?** Keeping the original is friendlier
   and costs little; it also makes the conversion auditable.

---

## 3. Basti's steer on question 1 (2026-08-31) — WHICH RUN

> *"it should let me choose between the currently open one or any other. maybe
> a combobox for this? but in theory there might be very many different runs and
> run types and various verifications — but it would mostly only make sense if a
> run does not yet have a measurement. otherwise would it replace the
> measurement already there or offer to duplicate the run but with the new
> measurement? — should be part of the challenge."*

So the user picks the run. The hard part is what a run that ALREADY HOLDS a
measurement should offer, and that is for the challenge to settle.

### What already exists for this — reuse it, do not invent it
* **A run picker already exists**, in the Profile-run bar
  (`ui/measurement_target_bar.py`; `ui/main_window.py:1151` builds "Delete,
  Duplicate, the run picker and Restore Used Chart" together). A fresh combobox
  in an import dialog would be a second way to say the same thing, with its own
  vocabulary — the mistake §S4.7 collision-ownership was ruled on to avoid.
* **Duplicating a run already exists**: `core/file_manager.py:2048
  duplicate_run` and `:2021 duplicate_run_plan`, the latter written so the
  confirmation window lists *what is actually on disk* rather than a wish list
  (Knut, 2026-08-01). That is precisely the machinery Basti's third option
  needs.
* **Creating a run already exists**: `core/file_manager.py:1954 new_run`, which
  can seed `preconditioning.icc` / `preconditioning.ti3` from a parent run.
* Replacing anything must ARCHIVE, never delete (principle 4) — and the
  §S4.7 / displacing-results machinery already asks that question properly.

### The sub-questions the challenge must answer
1a. Which runs may even be offered? A project holds profiling, verification and
    calibration runs. A calibration run has its own measurement flow, and
    `docs/design/calibration_run_type.md` plus `tool_availability.md` may
    forbid it outright. Is a verification run a legitimate destination for an
    imported measurement?
1b. A run with NO measurement is the easy case. Should runs that already have
    one be shown at all — greyed with a reason, or hidden? Hiding them makes
    the list short but leaves the user hunting for a run they can see in the
    bar and not in this dialog.
1c. For a run that HAS a measurement: replace-with-archive, or duplicate the
    run and put the new measurement in the copy? Duplicating keeps both results
    comparable, which is the whole point of runs — but it also silently doubles
    the files on disk, so the confirmation must say so (`duplicate_run_plan`
    already can).
1d. Is "create a new run for it" the sane DEFAULT, given a measurement is what
    defines a run in the #130 model?
1e. How long can this list get in practice, and does it stay usable? Report on
    a real project with many runs and verifications rather than guessing.

---

## 4. Basti, 2026-08-31 — a VERIFICATION chart measured in i1Profiler

> *"i could very well create a patch set for verification inside ChromIQ and
> print and measure it inside of i1Profiler. the question would be whether the
> measurement from there can then be used for our report when we import it
> back (and it should i think)."*

**It can, and the hazard in it is already guarded** —
`workflow/measurement_report.py:236 verify_patch_identity`, written for this
exact round trip:

* ChromIQ's report pairs a measurement with its chart **by `SAMPLE_ID`**.
* For a measurement that came back through i1Profiler that ID is **only the row
  number**: CxF objects are labelled `M0_Measurement1`, `c1` … and carry no
  trace of the original patch, so `reference_convert` numbers them 1..N by
  their order in the file.
* So if anything reordered the patches on the way — i1Profiler's own
  **`ScramblePatches`** setting is named in the docstring — every patch is
  compared against the wrong one, **and the report looks entirely normal**,
  because each comparison is against a real patch, just not the right one.
* The check walks the pairing the report itself uses and asks whether the chart
  and the measurement agree about the colour. A real 550-patch round trip
  through i1Profiler (2026-08-08) preserved the order exactly.

### What this means for the import design — possibly the most useful finding here
The same check answers a question the import flow must ask anyway: **is this
measurement actually of THIS run's chart?** Importing into the wrong run is the
easiest mistake to make in the whole feature, and it is silent — the report
still renders. `verify_patch_identity` compares device values against the
chart's asked-for colours, so running it AT IMPORT TIME, against the chosen
run's `.ti2`, would catch:

* the wrong run picked from the list,
* a measurement of a completely different chart,
* a genuine `ScramblePatches` reorder,

before anything is copied, rather than after a report has been believed.

### Questions this adds
4a. Should the import refuse a mismatch, or warn and let the user proceed?
    (It cannot be a hard refusal without care: a PARTIAL measurement is a
    normal supported state — the docstring is explicit that fewer patches is
    not a fault.)
4b. A verification run's reference is its own chart. Confirm the run's `.ti2`
    is what the check should be given, on every run type.
4c. Does the verification report path accept an imported `.ti3` unchanged, or
    does it expect fields only ChromIQ's own chartread writes? Prove it end to
    end with a real i1Profiler-shaped file, not a hand-made one.


---

# Challenge

**STATUS: challenged.**  2026-08-31. No source file was changed.
Proof: `~/Desktop/knut-import-design/` (see its `INDEX.md`).
Everything below was either read from the tree at `bd463b94` or measured —
by driving the real app, or by running the real functions on real files.

## C0 · Verdict up front

Report 08 is honest and its five current-behaviour rows are all true. But it
misses one thing that changes the whole design, gets one thing backwards, and
under-counts the destructive surface by two.

1. **ChromIQ already has this feature.** The Measure tab's **IMPORT module**
   files a measurement made in i1Profiler into the **open project**, into a run
   the **bar** selects, converting `.mxf`/`.cxf`/`.txt`/`.ti3`, validating it
   against that run's chart, never touching the original
   (`ui/tabs/tab_measure.py:10246 _on_import_measurement`). It is specified in
   **§I of `docs/design/unified_measurement_management.md`**, under
   `Confirmed behaviour` — *"Confirmed by: Sebastian, 2026-08-10"*. Report 08's
   whole §4 re-derives a shipped, confirmed feature, and §2's proposed
   "add it to the open project" dialog is a second front door to it.
   I drove it: **C6** below is the round trip working end to end.

2. **What is actually being asked for is the half §I forbids.** Its
   `Deliberate limits (v1)` paragraph says, verbatim:
   *"profiling and calibration runs cannot import at all — a profile is built
   only from a measurement made here."* That is a rule in a **Confirmed**
   section of a binding document. Per CLAUDE.md this is **reported, not
   fixed**: building this feature requires Sebastian to amend §I in writing,
   in the same commit. He is the person who confirmed it, so it is his to
   change — but it must be changed, not stepped over. **Open question 1.**

3. **The combobox should not be built.** The bar's controller already answers
   every question the proposed dialog would ask, for every run and every
   verification date (`ui/measurement_target_bar.py:160 run_ids`,
   `:164 verification_ids`, `:483 selection_has_measurement`,
   `:556 duplicate_state`, `:612 duplicate_run`,
   `:218 location_being_edited`). Report 03 §D5 already ruled that a second,
   weaker version of an owned question is a defect. **C2.**

4. **The pairing can be reconstructed, exactly.** Not "detected" — *repaired*.
   Measured on three real charts: **100.0 % of patches recovered
   colour-equivalently, 96.7–99.4 % on their exact original position**, from a
   fully shuffled measurement, with a stable device-value match. Basti's ruling
   about duplicate colours holds, and I checked its one caveat against the code
   rather than assuming it. **C5** — this is the most useful part of this
   document.

5. **Two more `shutil.rmtree` project-deleters than report 08 names**, and one
   of them is on the exact route this feature is about. **C8.**

**Recommended shape, in one sentence:** do not build a new dialog — lift §I's
profiling ban (with Sebastian's word), let the **bar** choose the run exactly
as it does today, add a device-value **re-pair** step to the existing
validation, and make Build Profile's own loader offer the IMPORT module instead
of silently making a new project.

---

## C1 · Citation audit — every claim in report 08, checked

| Report 08 says | Verdict |
|---|---|
| `tab_profile.py:4210` `_on_load_ti3` | ✅ exact |
| `ti2_loader.py:919 resolve_ti3` | ✅ exact; docstring quoted correctly |
| `tab_profile.py:4289` → `txt_loader.py:42` | ⚠️ `_import_i1profiler_txt` is at **:4286**; `resolve_txt`'s body starts at :42 but its `def` is at **:28** |
| `tab_profile.py:4251 _import_i1profiler_cxf` | ✅ exact |
| `tab_check_refine.py:1210` for the `.ti3` browse | ⚠️ `_on_browse_ti3` is at **:1199**; :1210 is inside it |
| `tab_check_refine.py:1222 _on_browse_icc` | ✅ exact — and the claim is right: the ICC is stored as a path and never copied |
| `txt_loader.py:281` writes `working_dir/<name>/` | ✅ `_copy_txt` at :309; the dialog's `dest` is built at :283 |
| `txt_loader.py:331` is `shutil.rmtree` | ⚠️ **:333**, and it is **one of three** — see C8 |
| `file_manager.py:1954 new_run`, `:2021 duplicate_run_plan`, `:2048 duplicate_run` | ✅ all three exact, and all three do what the report says |
| `measurement_report.py:236 verify_patch_identity` | ✅ exact |
| `reference_convert.py:331` writes `SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z` | ✅ exact, and `SAMPLE_LOC` is the row number: `f'{i} "{i}" …'` |
| `chart_exports.py:64` writes the shuffled sidecar | ⚠️ `write_sidecars` is at **:55**; `also_shuffled` is honoured at :83–:92 via `i1profiler_export.export_from_ti1` |
| `main_window.py:1151` builds the bar's buttons | ⚠️ that line is inside `_apply_calibration_mode` (`:1138-1149` per `calibration_run_type.md`); the bar itself is `ui/measurement_target_bar.py` |
| "A real 550-patch round trip preserved the order exactly" | ✅ quoted from the docstring at `measurement_report.py:224-232` |
| **"Principle 4", "Principle 5", "Principle 11"** | ❌ **no such document exists.** `grep -rn "rinciple" docs/ CLAUDE.md ui/ core/ workflow/` finds only prose uses and one earlier report citing "principle 5" the same way. Three numbered rules are being cited as binding with nowhere for a reader to look them up. Either write them down or stop numbering them. |

**Nothing in report 08 §1 is wrong.** I re-ran its central claim on screen. With
`ZZ-import-1` open, loading an external `.ti3` from the Desktop shows this —
`proof/drive/D1-external-ti3-dialog.png`:

> The following files from **Desktop/** will be copied into your working folder
> as a new profile set:  •  ZZ-import-external.ti3
> They will be placed in: `/Users/Basti/ChromIQ/<name>/`
> Enter a name for the new profile:

The open project is not named, not offered, not mentioned. A new project
(`ZZ-import-3`) was created. Confirmed, on screen.

**A side finding from that screenshot.** This is `ti2_loader._ask_project_name`
/ `_ask_profile_name` — the **old** dialog. The round-4 work (`ui/dialogs/
name_prompt.py`: validation, folder-name preview, collision notice,
Windows-reserved names) is imported **only by `ui/tabs/tab_chart.py`** (:12201,
:12222). Every measurement-loading route still runs its own copy. So the
release note at the top of this report — "they ship WITH this" — is truer than
intended: the loaders did not get the fix.

---

## C2 · Where the run is chosen: the bar, not a new combobox

Basti asked for *"a combobox … but in theory there might be very many different
runs and run types and various verifications"*. His own caveat is the argument
against a new one: the thing that already handles many runs, run types and
dated verifications is the bar.

### What the bar's controller already answers

| Question the import dialog would ask | Already answered by | 
|---|---|
| which runs exist | `MeasurementTargetController.run_ids()` — `ui/measurement_target_bar.py:160` |
| which dated verifications this run has | `verification_ids(run_id)` — `:164` |
| does that dated verification hold a result | `verification_has_measurement()` — `:170` |
| does the selected target hold a measurement | `selection_has_measurement()` — `:483` |
| can this run be duplicated, and if not, why | `duplicate_state()` → `(enabled, reason)` — `:556` |
| duplicate it and select the copy | `duplicate_run()` — `:612` |
| **where exactly will this write** | `location_being_edited()` — `:218`, written from the ChromIQ folder down |

Measured on `ZZ-import-2`, a real five-run project
(`proof/drive/drive-log.txt`):

```
controller.run_ids() -> ['run1', 'run2', 'run3', 'run4', 'run5']
  run1: measurement=True  chart_ti2=True  profile=True  duplicate_state=True
  run2: measurement=True  chart_ti2=True  profile=True  duplicate_state=True
        verifications=['2026-05-20_090500', '2026-06-24_164000']
  run3: measurement=False chart_ti2=True  profile=False duplicate_state=True
  run4: measurement=False chart_ti2=False profile=False duplicate_state=False
  run5: measurement=False chart_ti2=False profile=False duplicate_state=False
```

### The IMPORT module already reads it

`_on_import_measurement` takes its destination from `ctl.target.profile_run`
and `ctl.target.verification_id` (`tab_measure.py:10275`, `:10286`), and the
green info box above the button says, live, where the file will land. Driven,
verbatim from the running app (`proof/drive/D2-log.txt`):

> Before anything is filed, the measurement is checked patch for patch against
> this run's verification chart (ZZ-import-1-verify.ti2, 105 patches). A file
> that does not match is refused, and nothing changes.
>
> A new dated folder is created for it (named after today's date and time),
> under: `/Users/Basti/ChromIQ/ZZ-import-1/runs/run1/verifications`
>
> Your original file is not moved or changed — ChromIQ files a copy.

That is report 08 §2's proposed dialog, already written, already approved
(M-IMPORT-DONE, Sebastian, 2026-08-10), already saying the consequence in plain
words.

### The ruling

**A new combobox is a defect, not a feature.** Report 03 §D5:

> *"A second collision UI inside the name dialog would ask the same question
> with a different and weaker vocabulary … Anything else lets the user answer
> the same question two ways."*

Same shape here. **Recommendation: the run is chosen in the bar.** The import
control follows the bar, exactly as Start Measurement does, and the info box
states the destination. This also disposes of report 08's sub-question 1b —
"listed-but-greyed, or hidden?" — because the bar always lists every run, and
the greying moves to the **button**, which is where the house pattern already
puts it (`duplicate_state`, `delete_state`, `restore_state` each return
`(enabled, a reason naming what to do about it)`).

**A user hunting for a run they can see in the bar and not in a dialog is a
problem this design never creates.**

---

## C3 · Which run types may be a destination

### The rule, cited

`docs/design/unified_measurement_management.md` **§I, `Confirmed behaviour`**,
last paragraph:

> *"Deliberate limits (v1): an import never replaces an existing dated result
> (the road to a fresh check is the bar's "New verification", exactly as for a
> native read); a partial measurement (fewer patches than the chart) is
> refused, not filed; **profiling and calibration runs cannot import at all —
> a profile is built only from a measurement made here.**"*

So the answer today is: **verification only**, and it is confirmed behaviour,
not an oversight.

### The specification that disagrees with it

`docs/design/tool_availability.md` §4, "i1Profiler interchange", marks
**`i1p_to_ti3` as ● Applies** in S1 (profiling run), S3 (verification) **and
S5 (calibration)** — *"Brings a measurement in. Its natural destination is this
selection's measurement"* — and §5 then rules that a ● tool's output belongs
*"inside the selected target … resolved through `Project` / `Run` /
`Calibration`, never a hand-built path."*

**These two documents contradict each other, and the challenge must say so
rather than pick.** `tool_availability.md` is `⏳ Awaiting confirmation —
DRAFT, nothing here is settled`, `Confirmed by: nobody yet.` §I is confirmed.
**Confirmed beats draft**, so today's behaviour is right and the draft is the
one that is out of step. But the draft is also the document that anticipated
exactly this feature, which is a point in its favour once Sebastian rules.

### Recommendation per run type

| Run type | v1 | Why |
|---|---|---|
| **Verification** | **allowed — already is** | §I, confirmed, driven working in C6 |
| **Profiling** | **allowed, once §I is amended** | this is the feature. §5 of `tool_availability.md` already says where it lands. Needs **open question 1** |
| **Calibration** | **not in v1** | three reasons, below |

**Why calibration is a bad idea in v1, beyond the ban.**

* A calibration is not a profile attempt. `calibration_run_type.md` §2:
  *"A calibration belongs to the printer, paper and ink — not to a profile
  attempt."* There is **one** `cal/` per project, shared by every run
  (`core/file_manager.py:318-384`). An imported calibration measurement
  changes every run at once.
* **The archive machinery does not exist there.** `calibration_run_type.md`
  §3 D1: `Calibration.reset()` is `shutil.rmtree(cal/)` with **no `old/`
  archive at all** — *"Calibration has old_dir: False, Calibration has
  archive_to_old: False"*. So there is no safe way to displace an existing
  `cal/<project>-cal.ti3`, and the whole point of C4 below is that displacing
  must archive.
* `printcal -r` / `-e` need the *previous* `.cal` as an input. An import that
  landed on top of one would silently remove the input of the two modes that
  need it.

**Report it, do not fix it.** D1 is a known, unfixed defect in a DRAFT
document. This challenge does not touch it; it only says that calibration
import must wait for it.

---

## C4 · A run that already holds a measurement

Report 08 offers three options and asks which. The answer is already written
down for the verification half, and the profiling half should match it.

### The rule §I sets, and its profiling analogue

§I: *"an import never replaces an existing dated result (the road to a fresh
check is the bar's 'New verification', exactly as for a native read)."*
`M-IMPORT-DATE-TAKEN` says it to the user, and I saw the code refuse **twice**
before writing anything — once before converting (`tab_measure.py:10285`) and
once after the snapshot step (`:10327`).

For a verification, "somewhere new" is a **new dated folder**. For a profiling
run, the exact analogue is a **new run** — and `duplicate_run` is what makes it
one that is comparable rather than empty.

### Recommendation

| State of the selected run | Import does |
|---|---|
| no `.ti3` | files it into that run. Nothing is displaced, nothing is asked |
| has a `.ti3`, and the run has a complete chart | **duplicates the run** and files the measurement into the copy. The confirmation is `duplicate_run_plan`'s — it lists what is actually on disk, group by group, with byte counts (`file_manager.py:2021`) |
| has a `.ti3`, and the chart is incomplete | **refused**, with the reason named. See the trap below |

**Never replace-with-archive.** It is available (`Run.archive_to_old`,
`file_manager.py:1062`) and it is what a native re-measure does (§S1.5–S1.8) —
but that is a person deliberately re-reading *this* chart with *this*
instrument. An import is a file arriving from outside; the run it lands in is a
guess until the pairing check has passed. Duplicating costs disk and destroys
nothing; archiving-in-place moves a result the user may be looking at. §S4.7's
"Replace it" needed a second confirmation window
(`M-PROJECT-REPLACE-CONFIRM`, added for 4.1.3) precisely because replacing is
the dangerous verb.

### The trap in "just duplicate the run"

`duplicate_source()` (`measurement_target_bar.py:505`) returns `None` unless
the run has **all four** of `.ti1`, `.ti2`, `.channels.json` and at least one
`.tif`. On `ZZ-import-2` that is true of run1–run3 and false of run4/run5. So
"duplicate the run and put the new measurement in the copy" is **unavailable
for exactly the runs most likely to be an import target** — a run someone made
to hold a measurement from elsewhere.

Falling back to `new_run()` produces a run with **no chart**, and a run with no
chart cannot give the report a reference (C6). So the honest answer for that
state is a refusal that names the missing files — and `_duplicate_missing_phrase`
(`:530`) already writes that sentence.

---

## C5 · The pairing problem — it can be REPAIRED, not merely detected

This is the part worth building.

### (a) Can the pairing be reconstructed from device values? **Yes, exactly.**

`reference_convert.py:331` writes `RGB_R RGB_G RGB_B` for every converted
i1Profiler measurement, so a returning file carries the colour it was asked to
be. The chart carries the same. So the pairing does not have to be trusted —
it can be recomputed.

**The experiment Basti asked for**, on three real charts with their real
measurements. Full output: `proof/EXPERIMENT-shuffle-and-repair.txt`.
Method: take the real `.ti3`, shuffle its data rows, renumber `SAMPLE_ID` 1..N
in file order (**exactly** what `reference_convert` does and what
`ScramblePatches` produces), then match device values back to the chart with a
**stable** assignment — unambiguous patches first, duplicates handed out in the
chart's own order.

```
Pro300 940-patch chart, real i1Studio read (itself partial, 924/940)
  duplicates in the chart: 9 groups, 38 patches (4.0 %), largest group 20
  B SHUFFLED            exact position 910/924 (98.5 %)   colour-equivalent 924/924 (100.0 %)
  D PARTIAL+SHUFFLED    exact position 457/462 (98.9 %)   colour-equivalent 462/462 (100.0 %)
  after re-pairing, worst device disagreement = 0.0000 (tolerance 1.0) → verified

Demo-Switching 240-patch
  duplicates: 2 groups, 8 patches (3.3 %), largest group 4
  B SHUFFLED            exact position 233/240 (97.1 %)   colour-equivalent 240/240 (100.0 %)
  D PARTIAL+SHUFFLED    exact position 116/120 (96.7 %)   colour-equivalent 120/120 (100.0 %)

Knut-Scanner 315-patch
  duplicates: 2 groups, 4 patches (1.3 %), largest group 2
  B SHUFFLED            exact position 313/315 (99.4 %)   colour-equivalent 315/315 (100.0 %)
  D PARTIAL+SHUFFLED    exact position 157/157 (100.0 %)  colour-equivalent 157/157 (100.0 %)
```

**Colour-equivalent recovery is 100.0 % in every case.** Exact-position recovery
is 96.7–99.4 % for free, because the stable assignment hands the duplicates out
in chart order and a real read usually returns them in that order too.

### (b) How many duplicates does a real chart have? **Every one has some.**

Census over every `.ti2` in `~/ChromIQ` and in the owner's i1Profiler folder —
`proof/duplicate-device-values-in-real-charts.txt`. 51 charts. **Exactly one
had no duplicate device value at all.** The worst cases:

| chart | patches | unique | duplicate groups | patches in a duplicate | largest group |
|---|---|---|---|---|---|
| `knut.ti2` (TC9.18-class) | 1176 | 1035 | 110 | **251 (21.3 %)** | 17 |
| `tc918eg-cm-a3.ti2` | 1173 | 1039 | 110 | 244 (20.8 %) | 16 |
| `Pro300…Jun26.ti2` | 940 | 911 | 9 | 38 (4.0 %) | 20 |
| `Red-River…Letter-2052p.ti2` | 2064 | 2042 | 2 | 24 (1.2 %) | 19 |
| `Demo-Full-RGB-cal.ti2` | 64 | 54 | 2 | 12 (18.8 %) | 8 |

So a fifth of a TC9.18 chart is not uniquely identifiable by device value.
**That does not prevent reconstruction** — see (b′).

### (b′) Basti's ruling, checked rather than assumed

> *"if there is a chart with multiple patches of the same color i think it will
> not matter where which one is placed on which exact position as long as each
> position represents one patch of the correct color at least"*

**The colour maths: he is right, and it is provable rather than plausible.**
Every member of a duplicate group carries the *same design XYZ*, so the
expected value the report compares against is identical. Measured on the same
files: `design-XYZ spread within each duplicate group = [0. 0. 0.]`
(`proof/pairing-reconstruction.txt`). Two groups showed a spread above `1e-9` —
both are the paper-white group and the difference is text-rounding in the file,
not a real disagreement (`proof/ambiguity-by-chart.txt`).

**The caveat, checked in three places:**

1. **Does anything name a patch's location when reporting a problem?**
   **Yes.** `build_report` returns `worst_patches[…]["loc"]`, and
   `ui/dialogs/measurement_report_dialog.py:2468-2508` prints it — paper white,
   max black, the cube corners and every worst-offender row.
   **But for an imported measurement that location is already meaningless
   today.** `reference_convert.py:331` writes `SAMPLE_LOC` as the row number,
   so a report on the owner's real `RGB_default-i1Pro.mxf` says
   `paper_white.loc = 1872` and `worst patch loc = '1081'` — row numbers, not
   squares (`proof/real-mxf-roundtrip.txt`). **Re-pairing cannot destroy
   location information for an import, because there is none. It is the only
   thing that can supply it**, by carrying the chart's own `SAMPLE_LOC` onto
   the matched patch. After a real import through the existing module, the
   report says `worst patch loc: B6` (C6) — a real square, because the chart
   snapshot supplied it.
2. **Is `SAMPLE_LOC` used downstream?** Yes — `per_patch_overlay`
   (`measurement_report.py:337`) places each patch on the page by it, the
   Measure tab's per-patch hover keys on it (`tab_measure.py:12074`,
   `:12202`), and `ti2_relayout` sorts strips by it (`:278`). All of those read
   the **chart's** `SAMPLE_LOC`, which re-pairing preserves by construction; the
   measurement's own copy is discarded either way.
3. **Does anything compare readings of the same colour against each other?**
   Yes — `_duplicate_scatter` (`ti3_analysis.py:404`): *"Max ΔEab between
   patches that share the same device RGB (repeat patches), a direct read on
   measurement repeatability."* **It is immune.** It groups by device value
   inside the measurement itself and compares members pairwise; permuting
   members within a group changes neither the grouping nor the set of Lab
   values in it.

**So the ruling stands unconditionally on all three counts.** One refinement is
still worth building, and it is free: **assign duplicates stably, in chart
order**, so original positions are preserved wherever they can be. That is what
bought the 96.7–99.4 % exact-position figures above.

### (c) Re-pair automatically, or detect and warn? **Re-pair, and say so.**

The multiset test Basti proposed is exactly right, and it separates the three
cases on real data. Measured (`proof/EXPERIMENT-shuffle-and-repair.txt`):

| case | multiset of device values | unmatched | advice |
|---|---|---|---|
| in order / shuffled, full read | **identical** | 0 | re-pair silently, note it in the log |
| partial read (half, prefix or scattered) | **strict subset** | 0 | re-pair, and say *how many* patches were read |
| a different chart entirely | **neither** — 129/300, 281/300, 286/300 of its device values are absent from the chart | 129–286 | refuse: `M-IMPORT-MISMATCH` |

**One residual risk, stated rather than hidden.** In the Pro300 case, a
different chart still matched **171 of 300** patches by device value, because
both are RGB grids sampling the same cube. The multiset test catches it
(`neither`), but a chart whose device values are a genuine **subset** of the
run's chart — a small survey set inside a big one — would read as "partial".
Mitigation, cheap: **also require the read to be plausible in size**, and say
the count in the message. A 300-patch file offered against a 1176-patch chart
should tell the user 300 of 1176 came back and let them decide; it should not
be filed as if that were normal.

### (d) `verify_patch_identity` fires on the case it exists for — proven

Driven on screen (C6, case 2) and mutation-checked
(`proof/mutation-check.txt`):

```
BASELINE  tolerance = 1.0
  in order : verified
  shuffled : mismatch          <- the guard FIRES

MUTATION: PATCH_IDENTITY_TOL 1.0 -> 1e9
  mutation landed? module value is now 1e+09 and the function reads it
    at call time: True
  shuffled under the mutation : verified   <- the verdict flipped
RESTORED tolerance = 1.0 | shuffled again -> mismatch
```

The mutation is proven to land (the returned `tolerance` field changes with
it), and the verdict follows it. The check is real.

One thing to know about it: `out["paired_by"]` reports `"SAMPLE_ID"` for an
i1Profiler import, which reads as reassuring and **is numerically identical to
pairing by position** — because `reference_convert` set those IDs to 1..N by
file order and the chart's are 1..N too. The docstring is straight about this;
the field name is not.

### The shuffled export makes re-pairing mandatory, not optional

`chart_exports.write_sidecars(also_shuffled=True)` writes
`<name>-i1profiler-shuffled.pxf/.txt`, and `_shuffled_target`
(`i1profiler_export.py:493`) says why: *"a plain export can place near-identical
patches side by side on the strip — a little harder to read and slightly worse
for the instrument."* It is offered from three places (`tab_chart.py:13171`,
`:16105`, `ti2_relayout_dialog.py:6195`, `:7527`) behind the
`export_shuffled_pxf` preference.

**So ChromIQ itself ships a chart whose measurement comes back in a different
order from the `.ti1`, for a good instrument reason, and then refuses that
measurement.** Today's answer is the last line of `M-IMPORT-MISMATCH`:

> *"Use the chart's normal export (the file without "shuffled" in its name),
> measure again, and import that."*

**That sentence asks a person to reprint and re-measure a chart because of a
file-ordering detail a computer can undo in a millisecond.** With re-pairing it
becomes unnecessary, and the shuffled export becomes what it was meant to be
rather than a trap. This alone justifies the work.

---

## C6 · Does a verification report accept an imported `.ti3`? **Yes — driven end to end**

Real app, real files, sandboxed settings. Log: `proof/drive/D2b-log.txt`;
windows: `proof/drive/D2b-window-*.png`.

**Files used, by name:**

* `~/Desktop/i1Profiler/ColorSpaceRGB/Measurements/RGB_default-i1Pro.mxf` —
  the owner's real X-Rite CxF3 measurement, 2033 patches, `i1Pro 2`,
  `CHROMIQ_MEASURED "2014-08-05"`. Read only; SHA-256 verified identical
  before and after every run.
* `~/ChromIQ/ZZ-import-1/runs/run1/verifications/2026-08-10_120247/ZZ-import-1-verify.ti3`
  — a real 105-patch ColorMunki verification read (a copy of the owner's
  `printer-test` project, renamed; his own project was never touched).
* `~/ChromIQ/ZZ-import-1/runs/run1/verifications/2026-08-13_185140/ZZ-import-1-verify.ti3`
  — a real **15-patch partial** verification read, see the finding below.

### The converter, on the owner's real `.mxf`

```
source untouched: True
converted -> RGB_default-i1Pro.ti3   (118 210 bytes)
TARGET_INSTRUMENT "i1Pro 2"   CHROMIQ_MEASURED "2014-08-05"
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
parsed: 2033 patches; sample_ids[:5] ['1','2','3','4','5']
```

`build_report` on it produced a complete report — `reference_source: device`,
`patch_identity: unchecked ("there is no chart file to compare against")`,
ΔE00 mean 11.99. That is `verification_printing_and_target.md` §3.4 **row B5**
behaving exactly as specified.

### The whole import, in the running app

**Accepted (a real, matching, complete measurement):**

> **The measurement was imported**
> It is filed as this run's verification from 2026-08-31 07:54, in its own
> dated folder: `…/runs/run1/verifications/2026-08-31_075443`
> A copy of the chart it was measured against is stored with it, so the result
> stays interpretable even if the chart is replaced later.
> To see the colour-accuracy figures, open Tools ▸ "Measurement report" — the
> imported measurement is already in place there.

On disk afterwards: `ZZ-import-1-verify.ti3`, `…ti1`, `…ti2`,
`…channels.json`, `chart/`, `meta.json`. `CHROMIQ_VERIFICATION` stamped: True.
And the report on it:

```
reference .ti2 found: …/2026-08-31_075443/chart/ZZ-import-1-verify.ti2
patches 105 · instrument X-Rite ColorMunki · is_verification True
reference_source: design
patch_identity: {checked: True, verdict: 'verified', compared: 105,
                 mismatched: 0, worst: 0.0, paired_by: 'SAMPLE_ID'}
de00: {n: 105, avg_all: 11.758, max_all: 26.317}
worst patch loc: B6
```

**Report 08 question 4c is answered: yes, unchanged, and with a real chart
reference — not the `device` fallback.**

**Refused (the same file, rows shuffled, `SAMPLE_ID` renumbered 1..N):**

> **This file does not match the verification chart**
> … 105 of 105 patches do not hold the colour the chart asked for, so the
> readings may not line up with the chart
> Nothing has been imported and nothing has been changed.

Nothing was written. **The guard fires, on screen, on the exact case.**

**Refused (the owner's real 2033-patch `.mxf` against a 105-patch chart):**

> the verification chart has 105 patches, but this file holds 2033 measurements

Correct, and the source file's SHA-256 was unchanged afterwards.

### The finding I did not expect, and it matters

My first attempt used
`verifications/2026-08-13_185140/ZZ-import-1-verify.ti3` — a real measurement
ChromIQ itself wrote. It was **refused**:

> the verification chart has 105 patches, but this file holds 15 measurements

**A partial read that ChromIQ made cannot be re-imported by ChromIQ.** §I calls
that a deliberate limit; on the owner's own data it fires immediately. And the
Pro300 profiling measurement is partial too — 924 of 940. **Partial
measurements are not an edge case in this project; they are most of the
corpus.** Report 08 §4a is right that a hard refusal is wrong, and it is right
for a stronger reason than it gives: it is not a supported-state argument, it is
what the real files look like.

Note also that `verify_patch_identity`'s docstring says *"A shorter measurement
is not a fault"* while `_import_mismatch_reason` (`tab_measure.py:10201`)
refuses on patch count **before** ever calling it. The check and its caller
disagree. **Open question 5.**

---

## C7 · The `.icc` asymmetry in Check & Refine

`tab_check_refine.py:1222 _on_browse_icc` stores a path and nothing else. The
`.ti3` beside it, at `:1199`, is copied into a project. Report 08 is right that
this is inconsistent.

**The case for copying it in.** The run's report is then self-contained; the
profile cannot move or be deleted out from under a stored result; the file
guide's promise that a run holds the work that describes it stays true; and it
matches what `duplicate_run` already assumes — `DUPLICATE_GROUPS`
(`file_manager.py:1990`) lists `{stem}.icc` under `profile`, i.e. the model
already treats "the profile" as a file that lives in the run.

**The case against.** A printer profile is routinely installed system-wide;
copying it duplicates 0.5–8 MB per check and creates two files that will
diverge the day the user rebuilds one. And Check & Refine's ICC is often
*someone else's* profile being checked, which is `tool_availability.md`'s
**○ Independent** verdict — *"the tool works on files the user picks, and has
no relationship to the selection at all."*

**Recommendation, and it is a third option.** Copy nothing in v1; **record
identity**. When a check or a report is written, store the profile's path, byte
size, SHA-256 and its ICC `desc` tag in the run's report JSON. That makes the
result reproducible and auditable, says honestly which profile produced it, and
lets a later reader be told "the profile this was checked against has changed
since" — which is the actual risk, and which copying does *not* solve either
(a copy just hides the divergence). If Sebastian wants the copy as well, it
should land as `Run.checked_profile_icc`, role-named, never under the chart
stem — because `_auto_fill_icc` (`tab_check_refine.py:1231`) and
`_find_reference_ti2` both key on stems and would start finding it. **Open
question 6.**

---

## C8 · The destructive button — there are three, not one

Report 08 names `txt_loader.py:331`. The real count:

| where | what | reached from |
|---|---|---|
| `ui/txt_loader.py:333` | `shutil.rmtree(dest)` on a whole project | Build Profile → i1Profiler `.txt` |
| `ui/ti2_loader.py:1324` | `shutil.rmtree(dest)` on a whole project | `.ti2` chart import |
| **`ui/ti2_loader.py:1395`** | `shutil.rmtree(dest)` on a whole project, in **`_copy_ti3_only`** | **Build Profile / Check & Refine → an external `.ti3`** — the exact route this feature is about |

Both loaders carry their own "Overwrite existing folder" button
(`txt_loader.py:197`, `ti2_loader.py:1184`) and their own second confirmation
(`txt_loader.py:289`, `ti2_loader.py:1278`), whose text promises *"This will
permanently delete: {dest}"*. `ti2_loader.py:870` meanwhile offers **"Replace
existing"**, which *archives*. Three deleters, two vocabularies, one word.

**What the import flow should offer instead: nothing.** The whole hazard comes
from the import needing a project *name*, and the name colliding. **An import
into the open project needs no name at all** — the destination is a run the bar
already names, the file lands as `Run.measurement_ti3`, and the displacing
question is C4's (duplicate the run), which archives nothing because it copies
forward. The correct fix is to make the collision unreachable, not to write a
gentler version of the same button.

The three `rmtree` sites stay reachable from the *make a new project* branch,
and they are a separate defect that this feature should not inherit and should
not be blocked on. **Open question 7.**

---

## C9 · Edge cases, and what should happen

| # | Case | Behaviour |
|---|---|---|
| 1 | **No project open** | today's flow, unchanged: the name dialog and a new project. The import offer simply does not appear — there is nothing to import into. `location_being_edited()` returns `""` for exactly this state |
| 2 | **Project open, no runs** | the bar shows "New run". Import creates run1 through `new_run()` (`file_manager.py:1954`) and files into it. Nothing to displace. But it has **no chart**, so warn that the report will have no reference — see 4 |
| 3 | **The `.ti3` is already inside ANOTHER project** | `_project_root_for` (`ti2_loader.py:961`) already recognises it and `resolve_ti3` returns it unchanged, so today it is *used in place inside the other project*. That is the silent cross-project write this feature must not keep: **offer the import** (copy into the open project) or **open that project instead**. Never write into a project the bar is not pointing at |
| 4 | **Patch count differs from the run's chart** | the multiset test decides. Subset → a partial read; say *"{n} of {m} patches came back"* and file it. Neither → refuse. Never file a longer measurement than the chart |
| 5 | **schema_version 1 project** | nothing special. `Project.load` migrates in place before anything else (`file_manager.py:1616-1625`, `_migrate_v1_to_v2` at `:1750`), and all paths come from `Run`. Note the current schema is **3**, not 2 as CLAUDE.md says — worth a one-line doc fix |
| 6 | **Custom output path** | `_resolve_working_dir` honours `custom_output_path` and `_project_root_for` resolves under it, so this works — **but see the preferences finding in `proof/PREFS-DRIFT.md`**: a stale value pointing at a swept temp folder makes every project invisible, and it was live on this machine today |
| 7 | **The run's chart files were deleted** | import still allowed (the measurement is the valuable thing), but the validation cannot run. Say so in the log the way `_import_mismatch_reason` already does — *"[INFO] The patch-identity check could not run ({reason}) — the import continues"* — and warn that the report will fall back to `reference_source: device`. Do **not** offer the duplicate route here: `duplicate_source()` returns `None` (C4) |
| 8 | **The same file imported twice** | for a verification, §I already handles it: a second import needs "New verification" and gets its own dated folder. For a profiling run the analogue is C4's duplicate. Neither silently overwrites. Do **not** try to detect "same file" — two reads of the same sheet are a legitimate thing to hold twice |
| 9 | **Read-only source file** | fine — every path is `shutil.copy2` from it and never to it. Proven: the owner's `.mxf` is `-rwxr-xr-x` and its SHA-256 was unchanged after three import attempts. `copy2` preserves the mode, so the *copy* lands read-only; the copy is only ever read, so that is harmless, but strip the write-protection on the copy if a later feature ever edits it |
| 10 | **A `.ti3` whose chart is a different colour space** | `parse_ti3` raises *"No device RGB columns — only RGB charts are supported"* (`ti3_analysis.py:158`). Two of the owner's own `.ti2` files are CMYK and hit it. Refuse with that reason, not a traceback — `tool_availability.md` §6a is the standing analysis |

---

## C10 · The design — the journey, click by click, and where every file lands

### Journey A — a verification measured in i1Profiler (already works; one change)

1. Bar: **Run type = Verification**, **Profile run = run2**, **Verification = New verification**.
2. Measure tab: the **IMPORT** module button appears (`_import_available()`,
   `tab_measure.py:10033`). Press it.
3. The green box says what will happen and **where**, before anything is chosen.
4. Green folder button → choose `MyChart-measured.mxf` on the Desktop.
5. The box updates: *"…is an i1Profiler measurement (CxF3) — ChromIQ reads it
   directly, no export step needed."*
6. **Import Measurement**.
   * converted → `runs/run2/cache/import/MyChart-measured.ti3` (safe to delete)
   * validated against `runs/run2/verifications/<name>-verify.ti2`
   * **NEW: if the order does not line up, it is re-paired rather than refused**
   * dated folder created → `runs/run2/verifications/2026-08-31_1204/`
   * chart snapshot → `…/2026-08-31_1204/chart/<name>-verify.ti2` (+ `.ti1`, `.channels.json`)
   * measurement → `…/2026-08-31_1204/<name>-verify.ti3`, stamped `CHROMIQ_VERIFICATION "true"`
   * the original on the Desktop: **untouched**
7. "How was this sheet printed?" (`M-HOW-PRINTED`) — Raw / With colour management / Not sure.
8. **The measurement was imported**, with **Open measurement report**.

### Journey B — a profiling measurement, the new half

1. Bar: **Run type = Profiling**, **Profile run = run3** (a run with a chart and no measurement).
2. Measure tab: the **IMPORT** module button now appears for Profiling too.
   The box reads:
   *"It will be filed as this run's measurement, in: `ChromIQ/My-Printer/runs/run3/`."*
3. Choose the file. Press **Import Measurement**.
   * converted → `runs/run3/cache/import/<source>.ti3`
   * validated against `runs/run3/<stem>.ti2`, re-paired if needed
   * measurement → **`runs/run3/<stem>.ti3`** — `Run.measurement_ti3`, the
     project's own stem, **not the source file's name**
   * the original: untouched
4. **The measurement was imported.** Two buttons: *Open measurement report* and
   *Build the profile* (Build Profile tab, run3 already selected).

**Why the stem is not cosmetic.** `_find_reference_ti2`
(`measurement_report.py:168-197`) starts at `ti3_path.with_suffix(".ti2")`.
A measurement filed under the source file's name finds no chart, and the report
falls back to `reference_source: device` **without saying anything is wrong** —
measured, on the real `.mxf` (C6). Report 08's open question 2 has a hard
answer: `Run.measurement_ti3`, always.

### Journey C — Build Profile's own loader, redirected

Today: load an external `.ti3` while a project is open → a new project, no
mention of the open one (C1, screenshot).

Proposed: **one question, three answers**, and one of them is a hand-off.

* **Add it to "My-Printer"** → goes to the Measure tab's IMPORT module with
  the file already chosen and the bar pointing at the current run. The user
  then sees the destination, the validation and the confirmation the import
  module already provides. *One flow, not two.*
* **Make a new project for it** → today's path, unchanged.
* **Cancel.**

This is the only new UI in the whole design, and it is a routing question, not
a destination question.

### Where files land, in one table

| what | where | why |
|---|---|---|
| the user's original | **exactly where it was** | never moved, never modified. Proven by hash |
| the converted `.ti3` | `runs/runN/cache/import/<source-stem>.ti3` | §I.4; `cache/` is documented as always safe to delete |
| the filed measurement, profiling | `runs/runN/<stem>.ti3` (`Run.measurement_ti3`) | the stem is what lets the report find the chart |
| the filed measurement, verification | `runs/runN/verifications/<date>/<stem>-verify.ti3` | §I.7, unchanged |
| the chart it was judged against | `…/verifications/<date>/chart/` | §I.6, unchanged |
| a re-pair record | the run's `reports/report_*.json`, alongside `patch_identity` | so a reader can see the order was repaired and by how much |

---

## C11 · The exact dialog wording

New text goes to **§M-PROPOSED** of `unified_measurement_management.md` first —
`tests/test_message_catalogue.py` enforces it. Nothing here may be written into
a tab before Sebastian reads it.

### M-LOAD-INTO-PROJECT · the Build Profile / Check & Refine fork (new)

*Shown only when a project is open and the chosen measurement is outside every
project.*

> **Where should this measurement go?**
>
> "{file}" is not inside any of your projects yet, and you have "{project}" open.
>
> **Add it to "{project}"** files it with that project's work, so the report can compare it against the chart it was measured from and everything about this printer stays in one folder. You choose which run it joins on the next screen.
>
> **Make a new project for it** puts it in a folder of its own, named by you. Pick this when the measurement has nothing to do with "{project}" — a different printer, or a different paper.
>
> Either way your original file stays exactly where it is. ChromIQ works on a copy.

Buttons: **Add it to "{project}"** · **Make a new project for it** · **Cancel**

### M-IMPORT-REPAIRED · the order was reconstructed (new)

Two bodies, count-aware, no "(s)".

> **The patches came back in a different order, and ChromIQ put them right**
>
> All {n} patches in this measurement match a patch on your chart, but they arrived in a different order from the one they were sent in. That happens when the chart was measured from the shuffled i1Profiler export, or when i1Profiler's own "Scramble patches" was switched on.
>
> ChromIQ matched every reading back to the patch it belongs to by its colour, so the measurement is filed correctly and the report will be right. Nothing was thrown away.

Singular variant of the first sentence, for `{n} == 1`:
*"The one patch in this measurement matches a patch on your chart, but it arrived…"*

### M-IMPORT-PARTIAL · fewer patches than the chart (new — replaces today's refusal)

> **Part of the chart was measured**
>
> Your chart has {chart} patches and this file holds {got} of them. That is a normal thing to have: a measurement can be stopped part-way and finished later.
>
> ChromIQ matched every reading to the patch it belongs to. The measurement is filed, and the report will cover the {got} patches that were read. Build a profile only when you are happy that is enough of the chart.

### M-IMPORT-MISMATCH · revised last paragraph

The approved wording ends by telling the user to reprint and re-measure. With
re-pairing that sentence is wrong. Proposed replacement for the last paragraph
only:

> This does not look like a different order — the colours in this file are not the ones your chart asks for at all. Check that you picked the measurement of **this** run's chart. If you measured a different chart, select the run that chart belongs to in the bar above and import it there.

### The IMPORT module's info box, profiling variant

> It will be filed as this run's measurement, in:
> {folder}
>
> Before anything is filed, the measurement is checked patch for patch against this run's chart ({chart}, {n} patches). If the patches come back in a different order, ChromIQ puts them back in the right order for you. A file that belongs to a different chart is refused, and nothing changes.
>
> Your original file is not moved or changed — ChromIQ files a copy.

### And when the run already holds a measurement

> ⚠ This run already has a measurement, and an import never replaces one. Press Import Measurement and ChromIQ will make a copy of this run — chart, measurement, profile and reports — and put the new measurement in the copy. Everything you have here stays exactly as it is.

---

## C12 · Implementation plan

1. **Get §I amended.** Sebastian rewrites the `Deliberate limits (v1)`
   paragraph: profiling runs may import; partial reads are filed with
   `M-IMPORT-PARTIAL` instead of refused; a reordered measurement is re-paired
   instead of refused. **No code before this.** Add the three new messages to
   §M-PROPOSED in the same commit.
2. **`workflow/patch_repair.py` — new, pure, no Qt.** One function:
   `repair_pairing(measured, ti2_path) -> RepairResult` with
   `(pairs, verdict, n_chart, n_read, n_unmatched, n_reordered, n_ambiguous)`.
   Verdict from the multiset test: `aligned` / `reordered` / `partial` /
   `foreign`. Stable assignment: unambiguous first, duplicates handed out in
   chart order. Reuses `_rgb_to_0_100` and `PATCH_IDENTITY_TOL` so it and
   `verify_patch_identity` can never disagree about what "the same colour"
   means.
3. **Tests for step 2 before any UI**, including the three real charts of C5
   and a mutation that is proven to land. `tests/` only; the fixtures are
   small `.ti2`/`.ti3` pairs, no Argyll, no `@pytest.mark.slow`.
4. **Rewrite the measurement on re-pair.** When the verdict is `reordered` or
   `partial`, write the filed `.ti3` with the chart's `SAMPLE_ID` and
   `SAMPLE_LOC` carried onto each matched row, in chart order. This is the step
   that turns row numbers into real squares (C5 caveat 1). Record the repair in
   the run's report JSON beside `patch_identity`.
5. **`_import_mismatch_reason` → `_import_verdict`.** Call `repair_pairing`;
   refuse only on `foreign`; return the repaired rows otherwise.
   `verify_patch_identity` stays exactly as it is and is run **after** the
   repair as the final gate — a repair that does not produce a `verified`
   result is a bug, and should refuse.
6. **Lift the run-type gate.** `_import_available()` returns True for Profiling
   and Verification; keep it False for Calibration with a tooltip naming why
   (`tool_availability.md` §6's second string is close enough to reuse).
   `_on_import_measurement` branches on `ctl.target.is_verification()`:
   verification keeps §I.6/I.7 exactly; profiling files to
   `run.measurement_ti3` and applies C4's rule.
7. **C4's displacement rule.** If `run.measurement_ti3.exists()`, route through
   `duplicate_run_plan` → its existing confirmation → `duplicate_run` →
   `set_profile_run(new.id)` → file into the copy. If `duplicate_source()` is
   `None`, refuse using `_duplicate_missing_phrase()`.
8. **Build Profile / Check & Refine fork.** In `_on_load_ti3` /
   `_import_i1profiler_cxf` / `_import_i1profiler_txt` /
   `tab_check_refine._on_browse_ti3`, before calling `resolve_ti3` /
   `resolve_txt`: if a project is open **and** `_project_root_for(path)` is
   `None`, show `M-LOAD-INTO-PROJECT`. "Add it" hands the path to the Measure
   tab's IMPORT module and switches to it. "Make a new project" calls today's
   code unchanged.
9. **Record the ICC identity** (C7): path, size, SHA-256, ICC `desc`, into the
   report JSON. No copying in v1.
10. **Do not touch the three `rmtree` sites in this change.** File them as their
    own defect. Mixing a destructive-path fix into a feature is how a green
    gate hides a regression.
11. **Gate:** `QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`, green,
    before any beta. Bump `core/version.py` **before** the gate, per
    `project_release_process`.

**Sequencing note:** steps 2–5 are worth shipping *on their own*, for the
verification import that already exists. They turn today's "reprint and
re-measure" into "ChromIQ put them right", with no spec change beyond the
partial/reorder rules. Step 6 onward is the part that needs §I amended.

---

## C13 · i18n

* Every new string through `tr()`; runtime values as
  `tr("… {n} …").format(n=…)`, placeholders part of the key.
* `M-IMPORT-PARTIAL` and `M-IMPORT-REPAIRED` are **count-bearing**: explicit
  singular and plural bodies, never "(s)". `tests/test_message_catalogue.py`
  and `tests/test_i18n.py` both fail on the bracketed form.
* `{project}`, `{file}`, `{chart}`, `{folder}` are placeholders; folder paths
  and file names are never translated.
* After the strings land: `python scripts/i18n_extract.py --missing de` and add
  the German (Du-Form), then the other twelve. Per
  `feedback_translation_only_before_final`, the other twelve wait for the final,
  not the beta.
* `M-LOAD-INTO-PROJECT`'s buttons carry a project name inside the label —
  `tr('Add it to “{project}”')`. Check the German and the CJK catalogues for
  button width; `_fit_box` / `fit_message_box_buttons` exist for this.

---

## C14 · Open questions — only Sebastian can answer these

1. **§I's `Deliberate limits (v1)` says profiling and calibration runs cannot
   import at all, and it is in a Confirmed section.** This feature reverses
   half of it. Do you amend §I, and with what wording? *Nothing may be built
   until this is answered.*
2. **`tool_availability.md` §4 marks `i1p_to_ti3` as ● for profiling,
   verification AND calibration**, which contradicts §I. Which document is
   right? (My reading: §I is right today, the draft is right about where this
   is going, and calibration should stay out of both until
   `calibration_run_type.md` D1 — `cal/` is `rmtree`d with no archive — is
   fixed.)
3. **A partial measurement is refused today.** Your own real files are
   overwhelmingly partial: the verification I tried is 15 of 105, the Pro300
   profiling read is 924 of 940. Should partial imports be **filed with a
   count-bearing notice** (my recommendation), or stay refused?
4. **Should a re-paired measurement be filed silently, or with a window?** My
   recommendation is a window the first time (`M-IMPORT-REPAIRED`) and a log
   line thereafter — a person who used the shuffled export deserves to know
   why it worked.
5. **`verify_patch_identity`'s docstring says a shorter measurement is not a
   fault; `_import_mismatch_reason` refuses on count before ever calling it.**
   Which is the intended rule?
6. **The Check & Refine `.icc`** — record its identity (my recommendation), copy
   it into the run, or leave it as it is?
7. **The three `shutil.rmtree` project-deleters** (`txt_loader.py:333`,
   `ti2_loader.py:1324`, `ti2_loader.py:1395`) and the two loader name dialogs
   that never got the round-4 `name_prompt` work. Separate defect, or part of
   this change? (My recommendation: separate, and soon.)
8. **Journey C's fork** — is "Add it to {project}" handing off to the Measure
   tab's IMPORT module acceptable, or do you want the import to complete
   without leaving Build Profile? The hand-off gives one flow and one
   vocabulary; staying put is fewer clicks.
9. **A measurement whose device values are a genuine subset of a bigger
   chart's** reads as "partial" and cannot be told from a real partial. Should
   ChromIQ also warn on the *proportion* (300 of 1176 came back), and at what
   threshold?
10. **CLAUDE.md says `schema_version (2)`; the code and every project on this
    machine are at 3** (`file_manager.py:1624 _migrate_v2_to_v3`). Fix the doc
    in this change or separately?

---

## C15 · Rating

**Correctness — 8/10.** The core mechanism is measured, not argued: 100 %
colour-equivalent reconstruction on three real charts, the multiset test
separating all three failure modes on real data, and the existing guard
mutation-checked with the mutation proven to land. The whole import path was
driven end to end in the real app, accepted and refused, with the report read
back. Two points off: the subset-of-a-bigger-chart case (open question 9) has
no clean discriminator, and the design depends on a specification change that
has not been granted.

**Robustness — 8/10.** Every destructive verb is avoided rather than made
safer: no name, so no collision, so no `rmtree`; no replacement, so no archive
needed; the original is never touched, proven by hash across three imports. The
repair is validated by the app's own `verify_patch_identity` after the fact, so
a bad repair cannot file. Two points off: a run without a complete chart is a
real dead end (`duplicate_source()` returns `None`) and the design's answer
there is a refusal rather than a route; and the repair rewrites `SAMPLE_ID`,
which is a write to the user's data that has no undo beyond "the original is
still on your Desktop".

**Maintainability — 9/10.** The design adds **one** new pure module and **one**
new dialog. Everything else is a change of condition inside code that already
exists: `_import_available`, `_import_mismatch_reason`, the bar's controller
untouched, `duplicate_run` untouched, `resolve_ti3` untouched. The repair
function shares `PATCH_IDENTITY_TOL` with the existing check so the two cannot
drift. One point off: `_on_import_measurement` grows a run-type branch, and it
is already 90 lines.

**Efficiency — 9/10.** The repair is one pass over the measurement against a
dict of the chart — 2064 patches is microseconds, against a conversion that
already runs `txt2ti3` as a subprocess. No new Argyll call, no new file
written that is not already written, no `qapp.setStyleSheet`, and the new tests
are `.ti2`/`.ti3` text fixtures with no chart build, so they stay in the
everyday tier. One point off: re-writing the filed `.ti3` with repaired IDs is
a second write of a file that could have been written once.

**Overall: 8.5/10** — and the single largest risk is not technical. It is that
this feature is a second front door onto a module that already exists and was
confirmed three weeks ago. Built as a new dialog with its own combobox, it
becomes the thing report 03 §D5 was written to prevent. Built as an extension
of §I, it is a small change with a large payoff.

---

# Challenge 2 — the entry point and partial measurements

**STATUS: challenged-2.** 2026-08-31. No source file was changed.
Proof: `~/Desktop/knut-import-rulings/` (see its `INDEX.md`).
Every number below was measured — by driving the real app against the owner's
own projects in a sandbox, or by running the real ArgyllCMS 3.5.0 binaries on
the owner's own measurements.

Skeleton (filled in below as each part was measured):

* **D0** — verdict on both rulings, up front
* **D1** — Ruling 1, attacked: what `main_window.py:1590` really does, in every state
* **D2** — Ruling 1, attacked: the doors that already exist, and how many are open at once
* **D3** — Ruling 1: Check & Refine — a third door or a different act?
* **D4** — Ruling 1: what `tool_availability.md` contradicts
* **D5** — Ruling 2, attacked: what colprof really does with a sparse set
* **D6** — Ruling 2: where the line is, measured
* **D7** — Ruling 2: is refusing even consistent? (it is not)
* **D8** — Ruling 2: what the user should see — exact wording
* **D9** — Ruling 2: does a partial verification break anything downstream?
* **D10** — the three `rmtree` sites, confirmed and counted
* **D11** — `name_prompt`, confirmed
* **D12** — the proposed §I amendment, as the specification would read
* **D13** — numbered open questions

---

## D0 · Verdict up front

**Ruling 1 — the entry point: DISAGREE with the reasoning, AGREE WITH CHANGES
on the conclusion.** The citation is sound but it does not carry the argument.
`main_window.py:1590` does exactly what was claimed, in every state I could
reach — but it is *not* what makes the two imports mutually exclusive, and the
"a user can never see both" premise is **already false today**. Four doors onto
the same act exist right now, **three of them are open to a profiling user at
the same moment**, and one of them — Tools ▸ *Convert i1Profiler → TI3* — tells
the user in its own help text to *"build a profile from them"*, which is the
sentence §I forbids. Nothing greys by run type; `tool_availability.md` §8 says
so in terms: *"Nothing greys out yet."*

The rule that survives is not "one door per run type". It is **one destination
decision, wherever the door is**. Keep the single IMPORT module in the Measure
tab, and make Build Profile's and Check & Refine's loaders route into it.
Do not build a second import module in Build Profile.

**Ruling 2 — partial measurements: DISAGREE.** Allow partials on **both**
verification and profiling imports, with a count-bearing statement. Three
findings kill the "refuse for profiling" half:

1. **ChromIQ already builds profiles from partial measurements, on purpose,
   with approved wording.** The owner's own `printer-test` run1 measurement is
   **15 of 90 patches** and the Build button arms on it, labelled
   *"15 of 90 patches measured"* (measured on screen — D7).
   `tab_profile.py:4026` states the policy outright: *"A partial measurement is
   legitimate … this does not forbid it — it says how partial it is, and leaves
   the choice with the user."* §I refuses on import precisely what the tab
   deliberately allows natively.
2. **Refusing is inconsistent in the WRONG DIRECTION.** An imported measurement
   lands beside the run's `.ti2`, so its count *can* be shown. The file a user
   gets from today's permitted route — Tools ▸ Convert, then Build Profile —
   has no chart beside it, so `classify()` returns `expected=None`, the label
   shows nothing, the tooltip is empty and the Build button arms in silence
   (measured — D7). **Today's allowed path is the silent one; the forbidden
   path is the one that could speak.**
3. **colprof gives no protection to lean on.** rc=0 and not one warning from a
   4-patch set, while its own self-check reports the *best* numbers in the whole
   table (D5).

**Ruling 2's premise (c) is true, and worse than stated** — it is not
"silently worse", it is *silently worse while scoring better*. But that argues
for not showing colprof's self-check as a quality figure, not for refusing the
file.

**Where the line is: there is no defensible threshold, and there does not need
to be one** (D6). What is defensible is the one precondition colprof genuinely
has — **a patch at full white** — because it is a fact about the tool rather
than an opinion about "enough". Measured: no white → rc=1 and a 0-byte `.icc`;
no black → rc=0, builds fine. Black is *not* required, and ChromIQ must not
invent a rule the tool does not have.

---

## D1 · `main_window.py:1590`, checked in every state

`_apply_profile_tab_gate` (`ui/main_window.py:1556-1601`) is exactly as
described: `self._tabs.setTabEnabled(idx, not is_verification)` at **:1590**,
with the tooltip *"Not for a verification run…"* at :1591-1598, and a
`setCurrentWidget(self._tab_measure)` escape at :1600 if the user is standing on
it when it closes. It is re-applied from three places — `:256` (the bar's
`changed` signal), `:1047` (a measurement ending) and `:1619` (a build ending) —
and it deliberately stands aside while `_profile_building` or `_measuring` is
set (:1583-1589), because `_lock_other_tabs` owns the tabs then.

**Driven, on the owner's own five-run `Demo-Switching` project, sandboxed**
(`proof/doors/doors-log.txt`; the driver is `proof/doors/drive_doors.py`):

| state | Build Profile | Measure | Check & Refine | `_import_available()` |
|---|---|---|---|---|
| idle · Profiling | **enabled** | enabled | enabled | False |
| idle · **Verification** | **disabled**, with the tooltip | enabled | enabled | **True** |
| idle · **Calibration** | **enabled**, no tooltip | enabled | enabled | False |
| **no project open** | **enabled** | enabled | enabled | False |
| measuring | disabled | enabled | disabled | — |
| building a profile | enabled (the working tab) | disabled | disabled | — |
| run type → Profiling *while measuring* | disabled | enabled | disabled | — |
| …and after it ends | enabled | enabled | enabled | — |

**The claim about :1590 holds.** The gate re-asserts itself correctly after a
measurement and after a build; switching the run type mid-measurement does not
leave a stale enabled tab. Nothing here is broken.

**But three things it was used to prove are false.**

1. **The Measure tab is never disabled by run type — only by a build.** So the
   verification-side exclusivity does not come from the tab gate at all. It
   comes from `TabMeasure._import_available()` (`ui/tabs/tab_measure.py:10033`),
   which returns `self._is_verification_run()`, and from
   `_refresh_import_visibility` (`:10039-10050`), which calls
   `self._import_btn.setVisible(avail)`. Two different mechanisms, and the
   ruling cited the one that is not doing the work.

2. **Calibration runs keep the Build Profile tab.** Measured above, and
   `_apply_profile_tab_gate`'s own docstring says so — *"Calibration · shown —
   printcal (calibration options only)"*. A Build-Profile import door would
   therefore be **visible to a calibration user**, whom §I forbids from
   importing at all. The run-type separation is **not** free: an explicit second
   gate would still have to be written inside Build Profile, which is precisely
   the duplication the ruling claimed to avoid.

3. **With no project open the Build Profile tab is enabled and the run type
   reads Profiling.** A door there would be offered with nothing to import
   into.

### What a profiling user sees today: nothing at all

Question 3 of the brief — hidden, greyed with a reason, or a late failure?
**Hidden.** `setVisible(False)`; no tooltip, no reason, no trace. Grabbed from
the running app (`proof/doors/mode-row-*.png`):

| run type | the Measure tab's mode row |
|---|---|
| Profiling | `GUIDED` · `MANUAL` |
| **Verification** | `GUIDED` · `MANUAL` · **`IMPORT`** |
| Calibration | `GUIDED` · `MANUAL` |

So there is no confusing refusal message to worry about — and no
discoverability either. A profiling user has no way to learn from the screen
that ChromIQ can file an i1Profiler measurement at all. That is the *opposite*
failure from the one the ruling was defending against, and it is the one the
owner actually reported.

---

## D2 · The doors that already exist — the "mutually exclusive" claim is false today

`resolve_ti3` / `resolve_txt` have **four** call sites, all of which create a
new project from a measurement chosen outside one:

| # | door | code |
|---|---|---|
| 1 | Build Profile → `.ti3` | `ui/tabs/tab_profile.py:4240` |
| 2 | Build Profile → `.mxf` / `.cxf` (converted, then loaded as a `.ti3`) | `ui/tabs/tab_profile.py:4279` |
| 3 | Build Profile → `.txt` | `ui/tabs/tab_profile.py:4298` → `ui/txt_loader.py:29 resolve_txt` |
| 4 | Check & Refine → `.ti3` | `ui/tabs/tab_check_refine.py:1210` |

Plus a fifth that does not go through them at all:

| 5 | Tools ▸ **Convert i1Profiler → TI3** | `ui/tools_popup.py:67` → `ui/dialogs/tools_dialogs.py:1318 I1ProfilerToTi3Dialog` |

**Nothing greys any of these by run type.** `ui/tools_popup.py` builds its rows
from a static `_GROUPS` tuple (:48-84) with no availability filter of any kind,
and `docs/design/tool_availability.md` §8 confirms it: *"**Nothing greys out
yet.** No cell of §4 is implemented, because no cell of §4 is confirmed."*

So for a **profiling** run today, doors 1, 2, 3, 4 and 5 are all live at once.
For a **verification** run, 1–3 close with the Build Profile tab but **4 and 5
stay open** — and door 4 is the identical `resolve_ti3` that creates a project.
The premise "a user can never see both, so there is nothing to choose wrongly"
does not describe this app.

### The sentence that settles it

`I1ProfilerToTi3Dialog.HELP` (`ui/dialogs/tools_dialogs.py:1324-1348`), shipped,
translated, in the app today:

> *"Measured your chart in X-Rite's i1Profiler? This brings those readings back
> into ChromIQ **so you can build a profile from them**. … You'll get a ChromIQ
> measurement file (.ti3) you can take **straight to the Build Profile tab** —
> which neatly closes the loop after measuring in i1Profiler."*

and `DESCRIPTION` (:1349-1363):

> *"The resulting .ti3 **loads into Build Profile** and into the Measurement
> Report."*

**§I's `Deliberate limits (v1)` — *"profiling and calibration runs cannot import
at all — a profile is built only from a measurement made here"* — is already
contradicted by shipped user-facing text and by a working three-click route.**
The specification is not describing a capability the app withholds; it is
describing a button one module does not show. Per CLAUDE.md this is **reported,
not fixed**: it is Sebastian's rule and Sebastian's to amend.

This reframes the owner's request. He is not asking for a new capability. He is
asking for the capability the app already advertises to **land in the right
place** instead of manufacturing a stray project (report 08 §1, and C1's
screenshot).

### The corrected rule

> **One destination decision, wherever the door is.** Every route that brings a
> measurement in asks the same question, in the same words, and files through
> the same code. Which tab hosts a button is then a discoverability choice, not
> a correctness one.

Under that rule the answer to the owner's question is: **the module stays in
Measure** (that is where a measurement is filed, and §I already specifies the
sequence), and Build Profile and Check & Refine get a **fork question** that
routes into it — Challenge 1's Journey C. Not a second module. Not a second
combobox. Not a run-type gate that has to be maintained in two places.

---

## D3 · Check & Refine — a third door, and it needs the same question

`_on_browse_ti3` (`ui/tabs/tab_check_refine.py:1199-1219`) calls the **same**
`resolve_ti3`, with the same comment — *"External / old-flat-layout .ti3s get
imported into a fresh project"* — and therefore the same `_copy_ti3_only`, the
same name dialog and the same `shutil.rmtree` (D10). Measured above, the tab is
**enabled in every run type**, verification included.

**Is it a different act?** The subsequent action is different — it runs
profcheck and can feed a refinement, and it never builds a profile. **The
destination question is identical.** A `.ti3` arriving from outside has to land
somewhere either way, and today both tabs answer it by inventing a project the
open one knows nothing about.

**Verdict: same door, same question, different verb.** It gets the fork
(D2's rule), not its own import module. Its `.icc` asymmetry
(`tab_check_refine.py:1222`, referenced and never copied) is unchanged by this
and stays as Challenge 1 C7 left it — open question 6 there.

---

## D4 · What `tool_availability.md` contradicts — reported, not resolved

`docs/design/tool_availability.md` is `⏳ Awaiting confirmation — DRAFT, nothing
here is settled`, `Confirmed by: nobody yet.` §I is `Confirmed behaviour`,
Sebastian, 2026-08-10. **Confirmed beats draft** — so this is a contradiction to
report, not to act on.

§4, "i1Profiler interchange" (`tool_availability.md:118`):

> `| **Convert i1Profiler → TI3** `i1p_to_ti3` | ● | ✕ | ● | ✕ | ● | Brings a
> measurement *in*. Its natural destination is this selection's measurement —
> see §5 |`

Against §2's selection space (`:60-68`), that reads: **● Applies** in
**S1 (an existing profiling run)**, **S3 (verification)** and **S5
(calibration)**; **✕** only for S2 / S4, the *New run* states.

§5 (`:148`) then rules that a ● tool's output belongs *"inside the selected
target — `runs/runN/`, `runs/runN/verifications/<date>/` or `cal/`, resolved
through `Project` / `Run` / `Calibration`, never a hand-built path."*
And `:160` names `i1p_to_ti3` among the three tools *"whose default is wrong"*
today because it writes to the projects root instead.

**The contradiction, stated precisely:**

| | profiling run | verification | calibration |
|---|---|---|---|
| §I (**confirmed**) | cannot import | may import | cannot import |
| `tool_availability.md` §4 (**draft**) | ● applies, lands in `runs/runN/` | ● applies | ● applies, lands in `cal/` |

Both cells that this feature touches disagree, and the calibration cell
disagrees hardest. **I do not resolve it.** Two notes for whoever does:

* The draft is the document that anticipated this feature, which is a point in
  its favour on the profiling cell.
* On the **calibration** cell the draft is the more dangerous of the two.
  `docs/design/calibration_run_type.md` §3 D1 records that `Calibration.reset()`
  is `shutil.rmtree(cal/)` with **no `old/` archive** — *"Calibration has
  old_dir: False … archive_to_old: False"* — so there is no safe way to displace
  an existing `cal/<project>-cal.ti3`, and there is one `cal/` shared by every
  run (`core/file_manager.py:318-384`). Calibration should stay out of both
  documents until D1 is fixed. **Open question 3.**

---

## D5 · What colprof really does with a sparse set — measured, not assumed

Source: the owner's own **924-reading** i1Studio measurement,
`~/ChromIQ/Pro300_EpsonPremSG_i1Studio_Jun26/runs/run1/…ti3` (itself already a
partial — the chart has 940 patches). Tool: the real
`/Applications/Argyll/bin/colprof` 3.5.0, `-v -qm -aX`. Every subprocess carries
a `timeout=`. Raw output: `proof/colprof/A-prefix.txt`,
`proof/colprof/B-random-and-profcheck.txt`; the scripts are beside them.

### (a) The source says there is no "too few patches" guard

`profile/profout.c` in `/Users/Basti/Downloads/Argyll_V3.5.0_orig` carries
exactly one count guard — `error("No sets of data")` at **:1596**, which fires
only at zero. `grep -n "npat" profile/colprof.c` returns nothing. There is no
minimum, no advisory, no warning tied to patch count anywhere in the profile
builder.

### (b) A PREFIX truncation — what a stopped chartread leaves — fails HARD

A `.ti3` cut to its first *N* rows, which is the shape a session ended early
produces on a chart read in order:

```
N=3, 8, 15, 30, 60, 120, 240, 462, 700  ->  rc=1, in 0.0-0.1 s
  colprof: Error - 65539, set_icxLuLut: can't handle test points without a white patch
N=924                                   ->  rc=0
```

**700 of 924 still fails.** The reason is not sparseness — it is that the chart
is randomised and **RGB 100/100/100 first appears at row 729 of 924**
(`loc "J9"`; there are four whites, at rows 729, 920, 922 and 924). So on this
real chart *any* read stopped before 78.9 % has no white patch and colprof
refuses outright.

Two things follow. First, **the most common real partial already gets a loud,
immediate failure for free** — premise (c) does not hold for it. Second, that
failure reaches the user as Argyll's raw string: `_COLPROF_ERROR_PATTERNS`
(`workflow/profile_builder.py:20-56`) has no entry for it, so there is no
plain-English explanation. **A small, real defect on exactly this path.**

Noted in passing: colprof creates the output file and *then* errors, leaving a
**0-byte `.icc`** behind. `ProfileBuilder.sanity_check` catches it
(`profile_builder.py:264-266`, *"Profile is suspiciously small (0 bytes)"*), so
it is guarded — but the file is written.

### (c) A SCATTERED subset that does contain white and black succeeds SILENTLY

Random subsets of the same 924 readings, seeded, always including one white and
one black. This is the shape of a real ChromIQ patch-by-patch partial — the
owner's own 15-of-105 verification read has `SAMPLE_ID`s 5, 9, 18, 25, 33, …,
scattered, not a prefix.

| patches in | colprof | its own self-check, avg ΔE | **true avg ΔE, profcheck against all 924 readings** | true max ΔE |
|---:|---|---:|---:|---:|
| 4 | rc=0, no warning | **0.016** | **41.50** | 164.19 |
| 8 | rc=0, one convergence warning | 0.796 | 31.83 | 204.15 |
| 16 | rc=0, no warning | 1.664 | 22.81 | 249.65 |
| 32 | rc=0, no warning | 2.071 | 8.02 | 92.36 |
| 64 | rc=0, no warning | 1.729 | 5.64 | 33.55 |
| 128 | rc=0, no warning | 1.005 | 3.59 | 20.86 |
| 256 | rc=0, no warning | 0.283 | 2.08 | 44.34 |
| 512 | rc=0, no warning | 0.560 | 1.13 | 11.46 |
| 924 | rc=0, no warning | 0.459 | 0.46 | 2.13 |

**Premise (c) is confirmed and is worse than it was stated.** colprof does not
error, does not warn, and builds a valid ICC from four patches — and its own
self-check reports **0.016**, the *best* figure in the whole table, 29× "better"
than the full 924-patch profile, for a profile that is in truth **90× worse**.
The self-check measures how well the fit reproduces its own input; a 4-point fit
reproduces 4 points perfectly. **It is anti-correlated with quality at the
sparse end.**

ChromIQ does not surface that number for printer profiles — the only consumers
are the scanner path (`ui/dialogs/scanin_dialog.py:234`, threshold
`scanner_selfcheck_peak` at `core/settings.py:354`) and the layout preflight
(`workflow/layout_engine/preflight.py:147`) — and the Preferences help already
describes it correctly as *"how well a profile fits its own measurements"*
(`ui/dialogs/settings_dialog.py:2445`). **So this is a warning, not a live
defect on the printer path: whatever else is built, "peak err" must never become
the quality figure for a partial build.** It should be checked whether the
scanner path's threshold is exposed to the same inversion. **Open question 8.**

### What this does to Ruling 2's argument (c)

The premise is true. **The conclusion does not follow.** "colprof will not
protect you" is an argument for ChromIQ saying something, and ChromIQ already
has an approved sentence for saying it (D7, D8). It is not an argument for
refusing a file — and refusing it, as D7 shows, closes the *only* route on which
the count can be stated at all.

---

## D6 · Where is the line? There is no defensible threshold, and none is needed

**A fixed count is indefensible.** The owner's own charts run from 64 patches
(`Demo-Full-RGB-cal.ti2`) to 2064 (`Red-River…Letter-2052p.ti2`). Any number
that is a sensible floor for one is either the whole of the other or a rounding
error in it.

**A percentage is indefensible too, and the measurement says why.** The curve in
D5(c) is monotone in **absolute count**, not in fraction: 512 of 924 (55 %)
gives avg ΔE 1.13, while a complete 64-patch calibration chart cannot do better
than a 64-patch fit. A percentage gate would pass the second and fail the first,
which is backwards.

**What IS defensible is not a threshold at all — it is colprof's own
precondition, and there turns out to be exactly one.** It is a fact about the
tool, not an opinion about "enough".

`xicc/xlut.c:3206-3218` (case `icSigRgbData`) counts a patch as white only when
**all three device channels exceed 0.999** — i.e. RGB 100/100/100 on Argyll's
0..100 scale. A 99/99/99 patch does not count. With `nw == 0` it returns
`ICX_ERR_NO_WP` at `:3272-3275`. There is **no** matching requirement for black.

Proven rather than read, on four 64-patch subsets of the owner's own
measurement with one variable each (`proof/colprof/D-white-and-black.txt`):

```
wb_both      n=64 rc=0 icc=121768
wb_nowhite   n=64 rc=1 icc=0   set_icxLuLut: can't handle test points without a white patch
wb_noblack   n=64 rc=0 icc=121768      <- black is NOT required
wb_neither   n=64 rc=1 icc=0
```

So the one check ChromIQ can make that is a fact rather than a judgement is:
**does this measurement contain a patch at full white?** It can answer that from
the device values it already parses, before the build, and say so in words. That
is better than a threshold because it is checkable, explicable and cannot be
argued with.

**What to tell a beginner** is therefore not a number but the shape of the
curve, and only where they are about to act on it. From D5(c), against the same
printer and paper:

| patches read | avg ΔE of the resulting profile |
|---:|---|
| tens | 8–40 — a sketch, not a profile |
| ~128 | 3.6 |
| ~256 | 2.1 |
| ~512 | 1.1 |
| the whole chart | 0.46 |

There is no cliff in that curve, which is itself the answer: **any line drawn
across it would be arbitrary, so ChromIQ should not draw one.** State the count,
state the chart's count, arm the button. That is what `tab_profile.py:4026-4048`
already decided, and this measurement supports it.

---

## D7 · Is refusing a profiling import even consistent? **No — and it is backwards**

### A user can already build a profile from a sparse ChromIQ measurement

`TabProfile.set_ti3_path` (`ui/tabs/tab_profile.py:4013-4066`) says so in the
code, in a comment written after this very fault was found once already:

> *"Build Profile used to arm on the mere existence of a .ti3. In this session
> that meant it was offered on a measurement of 3 patches out of 390 — a profile
> built from that is not a bad profile, it is not a profile at all, and nothing
> on screen said so. **A partial measurement is legitimate, though**: the whole
> point of "Refine / resume" is that you stop and come back. **So this does not
> forbid it — it says how partial it is, and leaves the choice with the user.**"*

`usable` excludes only `ABSENT`, `EMPTY`, `NO_DATA_BLOCK` and `UNREADABLE`
(`:4032-4035`). `PARTIAL` is armed, deliberately.

And the specification agrees for the native case: §S1.5 and §S1.6 of
`unified_measurement_management.md` both treat a partial `.ti3` as an ordinary
state to resume or replace, not as a fault.

### Driven, on the owner's own files

Real `MainWindow`, sandboxed settings, a copy of the owner's `printer-test`
project (`proof/partial/partial-log.txt`; driver `proof/partial/drive_partial.py`):

```
--- the run's own COMPLETE profiling measurement ---
    label on screen : …/runs/run1/printer-test.ti3  —  15 of 90 patches measured
    Build button     : enabled = True
    Build tooltip    : "This measurement holds 15 of the chart's 90 patches. You can
                        build a profile from it, but a profile made from part of a
                        chart describes your printer only where it was measured.
                        To fill in the rest, go back to Measure and tick
                        “Refine / resume existing measurement (-r)”."
    classify()       : state=Ti3State.PARTIAL claimed=15 held=15 expected=90
```

**The owner's own profiling run holds 15 of 90 patches, and ChromIQ offers to
build a profile from it, with a plain-English count and an approved sentence.**
The same 15 readings arriving as a file would be refused by
`_import_mismatch_reason` (`ui/tabs/tab_measure.py:10200-10214`), whose test is
strict equality — `measured.n_patches != n_chart` — so it refuses fewer *and*
more, before `verify_patch_identity` is ever called. That check's own docstring
says *"A shorter measurement is not a fault"*. **The check and its caller
disagree; the caller wins.** (Challenge 1's open question 5, still open.)

### The inconsistency runs the wrong way, and this is the part that decides it

The same drive, two more cases:

```
--- a real 15-of-105 PARTIAL verification read ---
    label on screen : …/verifications/2026-08-13_185140/printer-test-verify.ti3
    Build button     : enabled = True
    Build tooltip    : (none)
    classify()       : state=Ti3State.PARTIAL claimed=15 held=15 expected=None

--- a real 105-of-105 COMPLETE verification read ---
    label on screen : …/verifications/2026-08-10_120247/printer-test-verify.ti3
    Build button     : enabled = True
    Build tooltip    : (none)
    classify()       : state=Ti3State.PARTIAL claimed=105 held=105 expected=None
```

`classify()` returns `expected=None` whenever it cannot find a chart beside the
measurement — *"No chart to compare against: readings exist, and that is all we
know"* (`workflow/measurement_state.py:195-196`) — and `set_ti3_path`'s
count-bearing branch requires `facts.expected` to be truthy (`:4047`,
`:4058-4066`). So **when there is no `.ti2` next to the `.ti3`, Build Profile
arms in complete silence**: no count on the label, no tooltip, nothing.

That is exactly the file today's *permitted* route produces. Tools ▸ Convert
i1Profiler → TI3 writes the `.ti3` wherever the user says
(`_OutputRow` / `_initial_dir`, `tool_availability.md:155-160` calls this out as
wrong), with no chart beside it. Take it to Build Profile — which the tool's own
help tells you to do — and a 15-patch measurement arms the Build button without
a word.

**An import into a run is the one route on which the count can be shown**,
because the measurement lands beside `Run.chart_ti2` and `classify()` can then
find it. Refusing the import while permitting the Tools route means **refusing
the safe path and keeping the silent one**. That is the whole case, and it is
measured rather than argued.

*(Two smaller findings from the same run, for the record: `set_ti3_path` looks
for the chart at `path.with_suffix(".ti2")` (`:4079`) while
`measurement_report._find_reference_ti2` (`:168-197`) searches harder and does
find a verification's chart under `chart/` — two chart-finders in one app that
disagree. And `Ti3State.PARTIAL` is returned for a file that is complete but
uncomparable, so the state name overstates what is known.)*

---

## D8 · What the user should see — exact wording

All of this is **new user-facing text**, so under CLAUDE.md and §M it goes to
**§M-PROPOSED** first and is not written into a tab until Sebastian has read it.
`tests/test_message_catalogue.py` enforces that. Every string is count-bearing
and therefore carries explicit singular and plural bodies — never "(s)"
(`tests/test_i18n.py` fails on the bracketed form).

The vocabulary deliberately reuses the sentence Build Profile already shows for
a native partial (`tab_profile.py:4051-4057`), so the two accounts of the same
situation cannot drift apart.

### M-IMPORT-PARTIAL-PROFILING · a partial measurement filed into a profiling run

*Replaces today's refusal. Shown after validation, before anything is copied.*

> **Part of the chart was measured**
>
> Your chart has {chart} patches. This file holds {got} of them.
>
> That is a normal thing to have — a measurement can be stopped part-way and
> carried on later. ChromIQ has matched every reading to the patch it belongs
> to, and nothing has been thrown away.
>
> A profile made from part of a chart describes your printer only where it was
> measured. Build one from this when you are happy that {got} patches is enough
> of your chart; otherwise measure the rest first and import again.

Buttons: **File it in {run}** · **Cancel**

Singular bodies, for `{got} == 1`:
*"This file holds one of them."* … *"Build one from this when you are happy that
one patch is enough of your chart"*.
For `{chart} == 1`: *"Your chart has one patch."*

### M-IMPORT-PARTIAL-VERIFICATION · a partial measurement filed as a verification

> **Part of the chart was measured**
>
> Your verification chart has {chart} patches. This file holds {got} of them.
>
> ChromIQ has matched every reading to the patch it belongs to. The measurement
> is filed, and the report will cover the {got} patches that were read — the
> rest are not counted for or against your profile.

Singular body, for `{got} == 1`: *"…the report will cover the one patch that was
read — the rest are not counted for or against your profile."*

### M-IMPORT-NO-WHITE · the set cannot build a profile, and this is a fact not an opinion

*Profiling imports only. Shown when the measurement holds no patch with all
three device channels at full — the one thing colprof genuinely requires
(D6). The measurement is still filed: it is real data, and the report can use
it. What is refused is the promise that a profile can be built from it.*

> **This measurement has no white patch**
>
> ChromIQ filed your {got} readings, but the profile builder needs a reading of
> the paper itself — a patch printed at full white — before it can work out what
> white looks like on your printer. This file does not have one, so Build
> Profile will not work from it yet.
>
> That usually means the measurement stopped before it reached the white patch.
> On a chart whose patches are shuffled, white is rarely near the beginning. Go
> back to Measure, tick "Refine / resume existing measurement (-r)" and read the
> rest of the chart.

Singular body, for `{got} == 1`: *"ChromIQ filed your one reading, but…"*

**There is deliberately no matching black message.** Measured: colprof builds
without a black patch (`proof/colprof/D-white-and-black.txt`). Inventing a
second requirement the tool does not have would be exactly the kind of
Claude-authored rule the specification policy exists to keep out.

### M-IMPORT-TOO-MANY · more readings than the chart has patches

*Kept as a refusal. This is not a partial measurement, it is a different chart.*

> **This file holds more readings than your chart has patches**
>
> Your chart has {chart} patches and this file holds {got} readings, so it
> cannot be a measurement of this chart.
>
> Nothing has been imported and nothing has been changed. Check that you picked
> the measurement of **this** run's chart — and if you measured a different
> chart, select the run that chart belongs to in the bar above and import it
> there.

### The IMPORT module's info box, profiling variant

> It will be filed as this run's measurement, in:
> {folder}
>
> Before anything is filed, the measurement is checked patch for patch against
> this run's chart ({chart}, {n} patches). A file that belongs to a different
> chart is refused, and nothing changes. If it holds fewer readings than the
> chart, ChromIQ will tell you how many came back and let you decide.
>
> Your original file is not moved or changed — ChromIQ files a copy.

### And on the Build Profile label afterwards

**No new string.** The measurement lands beside the run's `.ti2`, so
`classify()` finds `expected`, and the label the app already writes appears by
itself:

> `…/runs/run3/My-Printer.ti3  —  {got} of {chart} patches measured`

That is the point of filing it into the run rather than leaving it on the
Desktop, and it is the strongest single argument for allowing the import.

---

## D9 · Does a partial verification break anything downstream? **No — proven on real files**

Run on the owner's own `printer-test` verification folders, copied into a
sandbox (originals read-only, never modified). Full output:
`proof/report/partial-vs-complete-report.txt`; script beside it.

| | 105 of 105 | **15 of 105** |
|---|---|---|
| `_find_reference_ti2` | found, under `chart/` | **found, under `chart/`** |
| `parse_ti3` | 105 | **15** |
| `verify_patch_identity` | `verified`, compared 105, mismatched 0 | **`verified`, compared 15, mismatched 0** |
| `build_report` | complete | **complete, no exception** |
| `reference_source` | `design` | **`design`** — the real chart, not the device fallback |
| `de00` | n 105, avg 11.758, max 26.317 | **n 15, avg 9.759, max 22.893** |
| `accuracy_verdict` | computed, pass=False | **computed, pass=False** |
| `worst_patches` | B6, G1, F8, A1 | **A1, A7, A14, A10** — real squares |
| `per_patch_overlay` | `[]` | `[]` |

**Nothing breaks.** The ΔE statistics carry their own `n`, the pass/fail summary
is computed the same way, the identity check passes, and the worst-patch rows
name real chart locations. The overlay returns `[]` for the **complete** file
too, so that is not a partial-specific failure — it wants page images that these
folders do not hold.

### One real hazard, found on the way — reported, not fixed

`build_report` picks paper white and max black **by measured L\*** —
`wi = int(np.argmax(Ls))`, `bi = int(np.argmin(Ls))`
(`workflow/measurement_report.py:467-479`). On a partial read that means the
lightest and darkest patches *present*, whatever they are. On the owner's real
15-patch file:

```
paper_white -> loc "A2",  device RGB 85.714 85.714 85.714   (a light grey)
max_black   -> loc "A11", device RGB 28.571 28.571 28.571   (a mid grey)
```

The report labels them "paper white" and "max black" regardless. This is
**pre-existing** — it is reachable today from every native partial read and from
every already-permitted verification import — and it contradicts principle 8 as
the owner states it, so under CLAUDE.md it is **reported for review, not
corrected here**. Allowing partial imports would make it easier to reach, which
is a reason to fix it, not a reason to keep the refusal. **Open question 6.**

*(A second, smaller note: the 15 readings' `SAMPLE_ID`s are 5, 9, 18, 25, 33, …
— a scattered subset, not a prefix. Any reasoning that assumes a partial read is
the first N patches is wrong about ChromIQ's own files.)*

---

## D10 · The `rmtree`-a-whole-project sites — the count is confirmed at three

Challenge 1's count is **right**, and the exact paths at `HEAD` (`bd463b94`) are:

| # | site | what it destroys | reached from |
|---|---|---|---|
| 1 | `ui/txt_loader.py:333` | `shutil.rmtree(dest)` — a whole project folder | Build Profile → i1Profiler `.txt` (`tab_profile.py:4298 → txt_loader.py:29 resolve_txt`) |
| 2 | `ui/ti2_loader.py:1324` | the same, in `_copy_files` | `.ti2` chart import |
| 3 | **`ui/ti2_loader.py:1395`** | the same, in **`_copy_ti3_only`** | **Build Profile → `.ti3` / `.mxf` / `.cxf` (`tab_profile.py:4240`, `:4279`) and Check & Refine → `.ti3` (`tab_check_refine.py:1210`)** — the exact route this feature is about |

**All three are reachable from the UI.** Each is gated on `overwrite=True`,
which is set only by the "Overwrite existing folder" button
(`ti2_loader.py:1184`, `txt_loader.py:197`), which appears only when the typed
name collides (`ti2_loader.py:1232`), and which is confirmed by a second window
promising *"This will permanently delete: {dest}"* (`ti2_loader.py:1277-1288`,
`txt_loader.py:289`). Driven path: `_ask_profile_name` → `(name, overwrite)` →
`_copy_ti3_only(…, overwrite=True)` → `rmtree`.

**No fourth site.** I checked the other candidates rather than assuming:

* `core/file_manager.py:2121 _discard_run` — `rmtree(run.dir)`, but its docstring
  says *"Only for undoing a failed `duplicate_run` … one that existed for a
  fraction of a second"*. Not UI-reachable as a delete.
* `core/file_manager.py:2524` and `:625` — both are comments recording that this
  *used to be* `rmtree` and no longer is.
* `ui/tabs/tab_chart.py:15271`, and everything under `workflow/` and
  `ui/dialogs/` — temp folders and staging directories, not projects.

### The part worth stating plainly

The project **already has the safer primitive, and these three sites do not use
it.** `core/trash.py` exists precisely for this, and its own docstring records
the measured failure that motivated it:

> *"`shutil.rmtree` is not atomic … Measured on 2026-08-28 through the real
> Delete button, on a project with a single read-only `reports/` folder:
> `rmtree RAISED -> the app said "Nothing was changed." files before 6, files
> now 1  project.json still there: False`"*

The Delete button, `run_delete.py` and `FileManager` all route through
`move_to_trash` (`core/run_delete.py:629`, `:649`, `:743`;
`core/file_manager.py:2563`; `ui/measurement_target_bar.py:2007`). The three
loader sites are the only project-destroying calls left that do not.

**This is a separate defect and this feature must not inherit it.** The right
answer for the import remains the one Challenge 1 gave: **an import into the
open project needs no name**, so the collision that raises the button is
unreachable, so the button never appears. **Open question 9.**

---

## D11 · `name_prompt` — the claim is confirmed

`grep -rn "name_prompt" ui core workflow tests scripts` returns, outside tests,
**two lines, both in one file**:

```
ui/tabs/tab_chart.py:12201  from ui.dialogs.name_prompt import validate
ui/tabs/tab_chart.py:12222  from ui.dialogs.name_prompt import ask_for_project_name
```

**No loader uses it.** Every measurement-loading route asks for a name its own
way — `ti2_loader._ask_profile_name` (`:1111` onward) and
`txt_loader`'s equivalent — so none of them has the round-4 work: the live
validation, the folder-name preview, the collision notice or the
Windows-reserved-name check. Challenge 1 saw the old dialog on screen
(its `proof/drive/D1-external-ti3-dialog.png`); the grep is the reason.

**It is a real consistency gap and worth stating**, but it is a gap in the
*make a new project* branch, which the import branch does not use. It should be
closed — and it is the same defect as D10, since both live in the same two
dialogs. **Open question 9.**

---

## D12 · The §I amendment, as the specification would read

**I have not written Sebastian's name on it, and the project's own rules are why.**
CLAUDE.md: *"only the behavior that you confirm as correct, after bugs are
confirmed fixed, should be written into the design specification"*, and
`tests/test_design_specs_are_binding.py::test_an_awaiting_section_does_not_claim_to_be_confirmed`
fails on any `Awaiting confirmation` block that does not carry the exact words
`**Confirmed by:** *nobody yet.*`. §I is *his* confirmed section, so until he
says the words this is a proposal, not a specification. **The signature line
below is the line he fills in.**

### How it lands

1. Add the block below to `docs/design/unified_measurement_management.md`
   immediately after §I's existing `Deliberate limits (v1)` paragraph, as an
   `⏳ Awaiting confirmation` block, carrying `**Confirmed by:** *nobody yet.*`
   — that keeps the gate test green and keeps §I's confirmed half honest.
2. Add **M-IMPORT-PARTIAL-PROFILING**, **M-IMPORT-PARTIAL-VERIFICATION**,
   **M-IMPORT-NO-WHITE** and **M-IMPORT-TOO-MANY** (D8) to **§M-PROPOSED** in
   the same commit — `tests/test_message_catalogue.py` requires it.
3. When Sebastian confirms, the block's heading and its `Confirmed by:` line
   change together, the paragraph is folded into `Deliberate limits`, and the
   old sentence is struck. **Not before.**

### The text

> ### ⏳ Awaiting confirmation — §I.9, importing into a profiling run
>
> **Confirmed by:** *nobody yet.*
>
> **This replaces the third clause of `Deliberate limits (v1)`** — *"profiling
> and calibration runs cannot import at all — a profile is built only from a
> measurement made here"* — which is withdrawn.
>
> **I.9 · A profiling run may be an import destination.** The IMPORT module is
> shown while the shared Run type is **Profiling** as well as **Verification**.
> Its sequence is §I.1–§I.8 unchanged, with three substitutions:
>
> * **I.5** validates against the run's own chart, `Run.chart_ti2`, in place of
>   the verification chart.
> * **I.6** and **I.7** are replaced by a single step: the measurement is copied
>   to `Run.measurement_ti3` — the run's canonical stem, never the source
>   file's name, because the report finds its chart by that stem
>   (`measurement_report._find_reference_ti2`) and a measurement filed under any
>   other name falls back to `reference_source: device` without saying so.
> * **I.8** offers *Open measurement report* and *Build the profile*.
>
> A profiling run that **already holds a measurement** is not displaced. As for
> a verification, the road to a second result is a new place to put it: ChromIQ
> duplicates the run through `duplicate_run_plan` / `duplicate_run` and files
> the import into the copy. Where `duplicate_source()` is `None` — the run has
> no complete chart — the import is refused with the reason
> `_duplicate_missing_phrase()` already writes.
>
> **A calibration run still cannot import.** There is one `cal/` per project,
> shared by every run, and `Calibration.reset()` has no `old/` archive
> (`calibration_run_type.md` §3 D1), so an import there has no safe way to
> displace what is present. This stays out until that defect is fixed.
>
> **I.10 · A partial measurement is filed, not refused.** The rule *"a partial
> measurement (fewer patches than the chart) is refused, not filed"* is
> withdrawn for both run types. A measurement holding **fewer** readings than
> the chart has patches is filed, and the user is told the two counts —
> **M-IMPORT-PARTIAL-PROFILING** or **M-IMPORT-PARTIAL-VERIFICATION**. A
> measurement holding **more** readings than the chart has patches is still
> refused (**M-IMPORT-TOO-MANY**): it is not a partial measurement, it is a
> different chart.
>
> This aligns the import with what ChromIQ already does for a measurement made
> here. `TabProfile.set_ti3_path` arms Build Profile on a partial measurement
> deliberately and states the count on the label; §S1.5 and §S1.6 treat a
> partial `.ti3` as an ordinary state to resume or replace. **A file ChromIQ
> wrote must be a file ChromIQ will take back.**
>
> **No threshold is set, and none may be added later without a measurement to
> justify it.** Charts in use run from 64 to 2064 patches, and profile quality
> falls off smoothly with the absolute count rather than with the fraction of
> the chart, so any line drawn across it would be arbitrary. ChromIQ states the
> counts and leaves the judgement with the person, exactly as Build Profile
> already does.
>
> **I.11 · The one thing that is checked is white.** ArgyllCMS `colprof`
> requires at least one patch whose three device channels are all at full
> (`xicc/xlut.c`, case `icSigRgbData`); without one it refuses and writes an
> empty profile. A profiling import whose measurement has no such patch is
> still filed — the readings are real and the report can use them — and
> **M-IMPORT-NO-WHITE** says that a profile cannot yet be built from it and how
> to finish the chart. Black is **not** required by `colprof`, and ChromIQ does
> not invent a requirement the tool does not have.
>
> **I.12 · The IMPORT module is the only implementation.** Build Profile's and
> Check & Refine's own measurement loaders do not gain an import of their own.
> When a project is open and the chosen file lies outside every project, they
> ask one routing question (**M-LOAD-INTO-PROJECT**) and hand the file to this
> module. One destination decision, one vocabulary, one place where it is
> written.
>
> ---
>
> *On confirmation this heading becomes* `### I.9-I.12 — Confirmed behaviour`
> *and this line becomes* `**Confirmed by:** Sebastian, <date>`.

---

## D13 · Open questions — numbered

1. **§I's `Deliberate limits (v1)` forbids profiling imports, and it is
   confirmed behaviour.** Do you amend it, in the words of D12, or in others?
   *Nothing may be built until this is answered.*
2. **A partial measurement is refused on import and allowed natively.** Do you
   accept D12's I.10 — file it and state both counts — or keep the refusal and
   instead *remove* the native partial build to match? (I recommend the first:
   `tab_profile.py:4026` already argues the case, and your own `printer-test`
   run1 is 15 of 90.)
3. **`tool_availability.md` §4 marks `i1p_to_ti3` as ● for profiling,
   verification and calibration**, contradicting §I on two of the three. Which
   document is right, and does calibration stay out of both until
   `calibration_run_type.md` D1 (`cal/` is `rmtree`d with no archive) is fixed?
4. **The Tools ▸ Convert i1Profiler → TI3 help says in the shipped app that you
   can "build a profile from them" and take the result "straight to the Build
   Profile tab".** That is the sentence §I forbids. Does the help text change,
   or does the specification?
5. **The entry point.** Do you accept D12's I.12 — the module stays in Measure,
   and Build Profile / Check & Refine route into it — or do you want the import
   to complete without leaving Build Profile? (I recommend routing: it is one
   flow and one vocabulary, and a second module would need its own run-type gate
   because the Build Profile tab is live for calibration runs and with no
   project open.)
6. **`build_report` names paper white and max black by measured L\***, so a
   partial read labels a light grey "paper white" and a mid grey "max black"
   — measured on your own 15-of-105 file. Pre-existing, reachable today.
   Report only: do you want it changed, and to what? (A patch should probably
   only be called paper white when it *is* the chart's white.)
7. **`verify_patch_identity`'s docstring says a shorter measurement is not a
   fault; `_import_mismatch_reason` refuses on count before ever calling it.**
   Which is the intended rule? (Carried over from Challenge 1 open question 5,
   still unanswered, and D12's I.10 depends on it.)
8. **colprof's self-check ("peak err") is anti-correlated with real quality at
   the sparse end** — 0.016 for a 4-patch profile that is 41.5 ΔE wrong. The
   printer path does not show it, but the scanner path thresholds on it
   (`scanner_selfcheck_peak`). Should that threshold be re-examined?
9. **The three `shutil.rmtree` project-deleters** (`txt_loader.py:333`,
   `ti2_loader.py:1324`, `ti2_loader.py:1395`) still bypass `core/trash.py`,
   and the two loader name dialogs still bypass `ui/dialogs/name_prompt.py`.
   Separate defect, or part of this change? (I recommend separate, and soon:
   both live in the same two dialogs, and this feature makes them unreachable
   rather than fixing them.)
10. **`_import_available()` hides the IMPORT button rather than greying it with
    a reason.** After I.9 that stops mattering for profiling, but it will still
    be hidden for calibration. Hidden, or greyed with the reason?

---

**STATUS: challenged-2**
