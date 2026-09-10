# What a chart's patch set must contain, per metric — and the feature that checks it
Round 4, issue #182. Answers Knut's instruction of 2026-09-05 to *"create this definition of
parameters and boundaries for each metric and design how this feature can be implemented"*, with the
requirement that the definitions be *"clear and measurable and understandable so that a user knows
how to add patches … using the 'Edit / Create Chart Patch Set' editor and its patch generators."*

Everything below is stated in **device RGB on ChromIQ's 0–100 scale**, because that is what a
`.ti1` holds and it is what the editor's generators emit. Nothing here needs a measurement, a
profile or a reference file: **a criterion is a property of the chart, and it can be checked before
the sheet is ever printed.**

---

## 1. The criteria

Each one is a sentence a user can act on, a rule a function can evaluate, and the checkbox in the
editor that produces it.

| id | the rule, in words | the test, exactly | the generator that makes it |
|---|---|---|---|
| **C1** | The chart has enough patches for a "worst 5 %" to mean anything. | `n ≥ 20` | any |
| **C2** | The chart contains **bare paper** — one patch with no ink at all. | at least one patch within **0,5** device units of RGB 100/100/100 | **Pure white & black** |
| **C3** | The chart contains the **darkest the printer can go**. | at least one patch within **0,5** of RGB 0/0/0 | **Pure white & black** |
| **C4** | The chart contains the **six solid colours** — red, green, blue, cyan, magenta, yellow. | for each of the six cube corners, a patch within **12** device units on every channel (ChromIQ's own `CORNER_PRESENT_TOL`, `measurement_report.py:50`) | **3D RGB cube** (steps ≥ 2) *or* **Saturated edges** |
| **C5** | All **eight** cube corners are present. | C2 ∧ C3 ∧ C4 | as above |
| **C6** | The chart contains a **grey ramp**: at least 8 different grey levels from near-white to near-black. | patches with all three channels within **1,0** of each other; **≥ 8** distinct levels; the lightest **≥ 90** and the darkest **≤ 10** | **Neutral grey ramp**, steps ≥ 8 |
| **C6+** | *(for a grey-balance report)* the ramp is **dense and complete**. | **≥ 16** levels, spanning **0 … 100**, and **no gap larger than 10** device units between consecutive levels | **Neutral grey ramp**, steps ≥ 16 |
| **C7** | The chart contains a **near-neutral ring** — greys with a small deliberate colour cast, so the report can see *which way* the balance leans. | ≥ **12** patches whose channel spread (max − min) is **> 0 and ≤ 12** | **Near-neutral greys**, steps ≥ 2, rings ≥ 1, offset 1 to 12 |
| **C8** | The chart contains **tone ramps with steps in the 30 %–70 % band**, for each of the three inks. | for each axis: patches whose *other two* channels are within 1,0 of 100; tone value = 100 − the varying channel; **≥ 3 distinct tone values inside 30 ≤ TV ≤ 70**, and the outermost two at least **20 TV** apart | **no generator aims at this today — see §5, to-do 1** |
| **C9** | A **black-only ramp**. | — | **impossible on an RGB printer.** There is no way to ask for "K only": R=G=B=x is a composite the driver builds however it likes. Recorded so the report can say so, never as a failure the user can fix |
| **C10** | The **ISO 12647-7 / -8 control-strip patches** of clause 5.2. | **cannot be stated.** Clause 5.2 is past the end of both free previews | — |
| **C11** | The **outer-gamut patch selection**. | **cannot be stated.** `[P7]` Annex C / `[P8]` Annex C | — |

**C10 and C11 must report "cannot be checked", never "fails".** A user cannot fix a clause we have
not bought, and a red mark that means "we don't know" is the same lie as calling our limitation the
standard's.

## 2. Which metric needs which criterion

Metric ids are those of `METRICS-ONE-BY-ONE.md`.

| metric | needs | if the chart lacks it, the report must say |
|---|---|---|
| A1–A5 ChromIQ's five ΔE00 statistics | C1 | *"fewer than 20 patches — the 95 % split is not meaningful"* |
| B1 Substrate ΔE00 | C2 | *"no bare-paper patch"* |
| B2 Process-colour solids ΔE00 | C4 | *"the chart has no solid <colour> patch"* |
| B3 CMY solids ΔH\*ab | C4 (C, M, Y only) | same |
| B4 / B5 Near-neutral ΔCh average / maximum | C6 **and** C7 | *"no near-neutral scale"* |
| B6 Ramps 30–70 % ΔL\* | C8 | *"the chart has no tone ramp with steps between 30 % and 70 %"* |
| B7 Grey balance, substrate-relative | C2 **and** C6+ | *"the grey ramp is too short or has a gap"* |
| C1 / C2 all patches of ISO 12642-2 | the chart **is** that target | *"this is not an ISO 12642-2 chart"* — permanent for an RGB chart |
| D1–D3 control strip | C10 | *"which patches the control strip contains is in ISO 12647-7 clause 5.2, which ChromIQ does not hold"* |
| D4 outer gamut | C11 | same, naming the Annex |
| F1 / F2 nine-location uniformity | a **uniformity form**, not a patch set — §5, to-do 3 | *"no uniformity test form was printed"* |

## 3. The approved list — what the function produces

One row per preset. Knut asked for *"an approved list of chart presets that fulfil the criteria (or
what is missing for those not approved) and which then also states which standard and verification
action (report type) the specific chart may be used for."* Proposed shape:

```
preset                                        patches   report types it can serve      tolerance sets it can feed        what is missing
------------------------------------------------------------------------------------------------------------------------------------
i1Pro · A4-1160p TC9.18 extended greys           1160   Profiling · Verification       ChromIQ Profile Check (5 of 5)    –
                                                                                        ISO 12647-8:2021 (4 of 9)         tone ramps 30–70 %; and see the notes
Fogra RGB · i1Pro · Verification · A4-128p         128   Verification                   ChromIQ Profile Check (5 of 5)    –
my-quick-check                                     46   Verification                   ChromIQ Profile Check (5 of 5)    no grey ramp — add "Neutral grey ramp",
                                                                                                                          16 steps, in Add… ; no tone ramps
```

Three rules the wording must follow, all of them consequences of things already agreed in this
thread:

1. **"Can be used for" is never "conforms to".** The column says which *tolerance values* can be
   applied and how many of that set's metrics the chart can feed — `4 of 9` — never that the chart
   satisfies the standard. `[P7] 4.3.3` and `[P8] 4.2.2.2` mean no ChromIQ chart ever can.
2. **"What is missing" names the generator and the setting**, because that is the whole point:
   *"add 'Neutral grey ramp', 16 steps"*, not *"insufficient neutral coverage"*.
3. **A criterion that cannot be checked is its own state**, distinct from pass and from fail —
   the same `–` / `✕` / `?` distinction already agreed for the thresholds table.

## 4. The cost — measured, not estimated

Knut asked for the check *"possibly also on opening the measurement report window, if this is not
too cpu intensive and slow"*. Measured on this machine, script `measure_preset_check_cost.py` in
this folder, over **all 125 chart `.ti1` files bundled in `assets/`** — 187 758 patches, 84 to
10 290 patches each — using ChromIQ's own CGATS reader:

| | total | median per chart | worst chart |
|---|---:|---:|---:|
| read the `.ti1` | 210 ms | **1,34 ms** | 11,6 ms |
| evaluate all criteria | 47 ms | **0,30 ms** | 3,0 ms |
| **both, all 125 presets** | **257 ms** | | |

Four consecutive runs: 256,4 / 256,6 / 258,6 / 260,6 ms. So:

* **On opening the Measurement Report window — yes, do it, always.** The only chart that matters
  there is the one belonging to the run being reported, and it is already a file on disk. **≈ 1,6 ms**
  median, **≈ 15 ms** worst case. That is below anything a person can perceive.
* **The whole preset list — on demand, and cache it.** 0,26 s is fine for a button; those are warm-cache
  figures on a local disk, and a hundred and twenty-five file reads will be slower on a network
  home folder or a cold cache. Not on every report-window open.
* **And one kind of preset cannot be checked cheaply at all.** A user preset that is only *targen
  parameters* has no patch set until targen runs. Measured, `targen -d2 -G -f<n>`:
  **0,55 s at 300 patches, 1,82 s at 918, 3,41 s at 1 617.** Never on window open. On demand, with
  progress, and cached — which is safe, because targen is **deterministic**: two runs with identical
  parameters produce byte-identical patch *data*, verified both with `-G` and without. The *file* is not
  byte-identical, because of its `CREATED` timestamp line, so the cache must key on the parameters
  and never on a file hash.

**Where each preset's patch set comes from**, which is what decides the cost:

| preset kind | the patch set is | cost |
|---|---|---|
| built-in *prebuilt-files* (10 "by Pharmacist") | a bundled `<stem>.ti1` | read |
| built-in *ti1 → printtarg* (17 TC9.18+Spyderprint) | one shared bundled `.ti1` | read |
| built-in *ti1 → layout engine* (2 Scanner) | `assets/charts/knut/rgb/scanner/<paper>/chart.ti1` | read |
| user preset with `attached_ti1: true` | the `.ti1` sidecar beside its `.json` (`core/preset_store.sidecar_path`) | read |
| user preset that is targen parameters | **does not exist until targen runs** | 0,55–3,4 s |
| a Chart Layout preset | a *layout*; it holds no patch set at all | not a patch-set preset |
| the chart already in a run | its own `.ti1` / `.ti2` | read |

## 5. The generators that do not exist — the to-do list for the patch-set tool

**To-do 1 — a tone-ramp generator with an aimable band.** C8 has no generator today. The only route
to a single-channel ramp in the RGB panel is **Saturated edges**, and its step positions are locked
to the 3D cube's step count (`_edges_cube_n`, `ti2_relayout_dialog.py:2827`), so it lands inside
30 %–70 % only by luck. **Measured: 32 of the 125 built-in charts fail C8** — the gap is real, not
hypothetical. What is wanted: *"Tone ramps"*, with **from %**, **to %** and **steps**, emitting the
three white→cyan / →magenta / →yellow device-axis ramps, and optionally the grey axis as the
K analogue. The N-channel panel already has the equivalent (`per_ink_ramps`,
`workflow/patch_generators_nd.py:40`); the RGB panel does not.

**To-do 2 — a "Verification set" composite.** One checkbox emitting the minimum a verification
report needs: bare paper, composite black, the six solids, a 16-step grey ramp, a near-neutral ring
and the three tone ramps. Today a user must tick five separate generators and get five counts right,
which is exactly the step where a chart quietly ends up unusable for the report type it was made for.

**To-do 3 — a uniformity test form.** `[P8] 4.2.2.1` (quoted in full in `METRICS-ONE-BY-ONE.md`
Part F) wants three full-format single-tint sheets read at nine positions, in a 3 × 3 grid at the
centres of the ninths. Nothing in ChromIQ makes such a sheet. The tint values are in clause 5.4,
which is past the end of the free preview — so build it with user-chosen tints, and label it
honestly.

**Not to-dos.** A K-only ramp (C9) is impossible on an RGB printer. A clause-5.2 control strip
(C10) and an outer-gamut set (C11) cannot be specified without the documents. Spot colours have no
workflow at all.

## 6. How it is built — files and functions

**New module `workflow/patch_set_criteria.py`** — pure Python, numpy, no Qt, no Argyll, so it is
testable without a display and cheap to call from anywhere:

```python
CRITERIA_VERSION = 1                       # bumped when a rule changes; part of the cache key

@dataclass(frozen=True)
class Criterion:
    id: str                                # "C6"
    title: str                             # tr("A grey ramp")
    how_to_add: str                        # tr("Add 'Neutral grey ramp', at least {n} steps")
    check: Callable[[np.ndarray], CriterionResult]

def evaluate_patch_set(rgb100) -> PatchSetVerdict      # every criterion, one pass
def metrics_supported(verdict) -> set[str]             # which metric ids the chart can feed
def missing_for(metric_id, verdict) -> list[str]       # the user-facing "what is missing" lines
```

**New module `workflow/preset_audit.py`** — knows where patch sets live, nothing else:

```python
def patch_set_for_preset(kind, name) -> np.ndarray | NeedsTargen
def audit_presets(*, run_targen=False, progress=None) -> list[PresetVerdict]
def cached_audit() -> list[PresetVerdict]              # keyed on (path, mtime, size,
                                                       #           param fingerprint,
                                                       #           CRITERIA_VERSION)
```

**Three places it is used.**

1. **`ui/dialogs/ti2_relayout_dialog.py`** — a *Standards check* panel in the New Patch Set / Add…
   window, ticking criteria live as generators are switched on. The counts panel already refreshes
   live (`_update_gen_counts`); at 0,30 ms this is free. This is what turns the criteria from a
   document into something a user can *use*.
2. **`ui/dialogs/settings_dialog.py`**, Reports tab — a button next to the thresholds table opening
   the **approved list** of §3, with a *Re-check now* button that offers to run targen for the
   parameter-only presets.
3. **`ui/dialogs/measurement_report_dialog.py`** — `_refresh` (`:1286`) checks the run's own chart
   against the selected compliance set, and `_render` (`:1292`) writes the *"not computed, and why"*
   section into the report.

## 7. The warning before the report is generated

Knut asked for *"feedback to the user (warning message) as part of the setup of the measurement
report, before the report is actually executed/generated"*.

**Proposed: a warning strip inside the report window, not a modal.** `_refresh` runs on every list
change and every threshold edit; a modal there would fire many times per session and would be
trained away within a day. The strip states the mismatch in one line and stays while it stands. At
**PDF export** — `_export_pdf`, `:1411`, one deliberate action — a modal confirmation is
proportionate, because that is the artefact that leaves the machine.

Both texts are **§M-PROPOSED** and are drafted in the reply, not written into any tab.

**Whether he wants the modal at report time instead of at export is his call, and it is asked.**
