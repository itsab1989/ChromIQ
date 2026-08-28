# CR30 registration surface map — [CR30-SURFACE]

STATUS: in-progress
Branch: `feature/cr30-instrument-159`
Started: 2026-08-28

Method: every claim below carries a `file:line` citation verified by reading the
surrounding code. Claims taken from ChromIQ#159 are marked as VERIFIED /
FALSE / NOT VERIFIED against the actual source.

---

## 0. Corrections to ChromIQ#159's own citations

| #159 says | Reality | Evidence |
|---|---|---|
| `ui/panels/layout_options_panel.py:74` / `:2350` | Path is `ui/dialogs/layout_options_panel.py` | (known, restated in the brief) |
| `workflow/ti2_writer.py:80` | Path is **`workflow/layout_engine/ti2_writer.py`**; `TARGET_INSTRUMENT` is written at **line 79** | `workflow/layout_engine/ti2_writer.py:79` |
| `ui/ti2_loader.py:33` (`KNOWN_INSTRUMENTS`) | It is at **line 35** | `ui/ti2_loader.py:35` |
| `instruments.py:30 / :139 / :461` | `TARGET_INSTRUMENT_NAME` is at **26**; `supported()` at **138**; the ColorMunki geometry block starts at **394** (the `_build_base` CM branch), not 461 | `workflow/layout_engine/instruments.py:26,138,394` |
| `chromiq_chartread.c:600` (`spot_ready`) | Correct — `cq_emit_spot_ready` is defined at **600**, emitted at **2789** | `native/chartread_helper/chromiq_chartread.c:600,2789` |
| `chromiq_chartread.c:887` (`rmode 0 = spot`) | Correct | `native/chartread_helper/chromiq_chartread.c:887` |
| `chromiq_chartread.c:3628` (the fatal `error()`) | It is at **3630**; the `find_kword` is at 3627 | `native/chartread_helper/chromiq_chartread.c:3626-3633` |
| `patch_db.py:180` | Correct — `INSTRUMENT_LABELS` at 180 | `data/patch_db.py:180` |
| `settings_dialog.py:1435` (`_MARGIN_INSTRUMENTS`) | **See §6 below** — verified separately |
| "Nine touch points, all one-liners bar the geometry block" | **FALSE — undercounts by roughly 5×** (48 code touch points across 17 files, plus 24 i18n files). See §12. | this document |

---

## 1. Layout engine — `workflow/layout_engine/`

### 1.1 `instruments.py` — the geometry table

| Symbol | Line | What a CR30 needs |
|---|---|---|
| `TARGET_INSTRUMENT_NAME: dict[str, str]` | `instruments.py:26-33` | one entry `"CR30": "<the CGATS string>"` — **but see §3, the string is constrained by `inst_enum`** |
| `DELEGATED = {"isis"}` | `:36` | leave alone *unless* the CR30 ships as an import-only device, in which case it belongs here (`_build_base` raises `ValueError` for a DELEGATED key, `:356-357`) |
| `Geom.extra_keywords` | `:73` (declared), consumed at `layout_engine/ti2_writer.py:87-88` | the ready-made hook for a private `CHROMIQ_INSTRUMENT "CR30"` keyword. Today only `SS` hex (`:466`) and `DTP41` lengths (`:485-489`) use it. **Verified: it is emitted verbatim as `KEYWORD "value"` into the `.ti2`.** |
| `supported() -> list[str]` | `:138-139` | add `"CR30"` — hard-coded list, does **not** derive from `TARGET_INSTRUMENT_NAME` |
| `default_ruler_mm(key)` | `:142-155` | works automatically once a `Geom` exists; returns `0.0` for a device with `ruler_mm=0` (ColorMunki/SpectroScan). **A CR30 wants `ruler_mm=0.0`** — no jig. |
| `_MARGIN_LABEL_TO_KEY` | `:159-161` | add `"CR30": "CR30"` (or whatever the friendly Settings label is) — this is what maps the Settings-dialog label back to a device key |
| `build(...)` CM-specific branch | `:245-247` (`if key == "CM" and cm_stagger`) | decide whether CR30 inherits the stagger option; a spot device has no reason to stagger, so probably **not** |
| `_build_base(...)` dispatch | `:354-509` | **the real work**: a new `if key == "CR30":` block returning a `Geom`. Needs aperture-derived `plen`/`pwid`/`rrsp`, `lcar`/`tspa`/`lspa` (a spot grid needs **no** strip lead-in or trailer — see §11), `mxrowl=MAXROWLEN`, `ruler_mm=0.0`, `has_clip_border=_band > 0` (clip band OFF by default, as #159 §8 argues and the CM branch at `:449-450` demonstrates) |
| `geom_from_build_kwargs` CM/SS notes-band special case | `:311-315` | the `("CM", "SS")` tuple gates the optional notes band — a CR30 must be added or it silently cannot have one |
| `GEOM_BUILD_KEYS` | `:293-299` | no change needed (instrument-agnostic) — but if a CR30-only option is added it MUST be listed here or capacity estimates silently diverge from the render (the file says so at `:288-292`) |

**#159 §8 claim — "the ColorMunki branch is already written for exactly this shape": VERIFIED.**
- "no ruler cap" — `instruments.py:441-443` comment and `mxrowl=MAXROWLEN` at `:451`, `ruler_mm` left at its `0.0` default (`:135`).
- "density levels 1/2/3, the third being 10.4 × 13.0 mm" — `:394-453`; level 3 at `:414-436`, `plen = pscale * 13.0`, `pwid = rrsp = pscale * 10.4` (`:424-425`).
- "clip border optional" — `_band = max(0.0, clip_band - border) if clip_band > 0 else 0.0` at `:391`, `has_clip_border=_band > 0` at `:452`; i1/p3 return `has_clip_border=True` unconditionally at `:385`. VERIFIED.

### 1.2 `presets.py`

| Symbol | Line | Need |
|---|---|---|
| `SUPPORTED_INSTRUMENTS = ("i1","p3","CM","41","51","SS")` | `presets.py:24` | add `"CR30"` |
| `LayoutRecipe.mode()` | `:167-176` | the preset **key** is `f"{instrument}\|{paper}\|{mode()}"` (`:176`). `mode()` branches per instrument: i1/p3 → clip/noclip, CM → freehand/high/extrahigh, SS → flat/hex, everything else → the fallthrough at `:172-175`. A CR30 needs its own mode vocabulary decided (probably a single `"spot"`). |
| `LayoutRecipe.from_dict` | `:198` (`inst = d.get("instrument", "i1")`) | no change |
| `build_kwargs()` edge-spacer default | `:319-324` — `self.instrument in ("i1","p3","CM")` | a CR30 grid wants **no** edge spacers; leaving it out of the tuple is the correct default, but must be a deliberate decision |
| `build_kwargs()` `nolpcbord` | `:378` — `if self.instrument in ("i1","p3")` | no change |
| `default_recipe(instrument, paper, mode=None)` | `:397-436` — branches at `:408` (SS), `:413` (CM/SS), `:416/418/428` | a CR30 branch is needed, or it silently gets i1-shaped defaults |
| `built_in()` shipped presets | `:496-503` — `modes = [...] if inst in (...) else ...` | must list the CR30 modes or the device ships with no built-in preset |

### 1.3 `chart.py`

| Symbol | Line | Need |
|---|---|---|
| `_instr_friendly` display map | `chart.py:277-278` | add `"CR30": "CR30"` — used for the `{instrument}` placeholder in sheet text and the engine stamp (`:282`, `:290`) |
| `layout()` / `render()` signatures default `instrument="i1"` | `:41`, `:94` | no change |

### 1.4 `papers.py`

| Symbol | Line | Need |
|---|---|---|
| `ENGINE_EXCLUDED_PAPERS` | `workflow/layout_engine/papers.py:19` | decide whether a CR30 hides any paper. Probably **no exclusions** (like CM), i.e. no entry — but that must be a decision, not an omission. |

STATUS: in-progress

---

## 2. Chart creation — `workflow/chart_creator.py`

| Symbol | Line | Need |
|---|---|---|
| `ENGINE_INSTRUMENTS = {"i1","p3","CM","SS"}` | `chart_creator.py:130` | **must contain `"CR30"`** or `_should_use_engine` returns False for every CR30 chart |
| `_should_use_engine(params)` | `:1068-1101` | first line is `if params.instrument not in ENGINE_INSTRUMENTS: return False` (`:1069-1070`) |
| `_engine_kwargs` / `_engine_build_kwargs` per-instrument branches | `:1123-1160` — `("i1","p3","CM")` edge-spacers at `:1125`, then `:1127` i1/p3, `:1140` CM, `:1158` SS | a CR30 branch is needed for its defaults |
| `_engine_total_patches` | `:1162-1179` | returns `None` when `_should_use_engine` is False → falls through to `query_patches` |
| `estimate_patches` | `:751-792` | **the trap**: with the engine off, `query_patches("CR30", …)` returns `None` (no DB rows) → `_binary_search` → runs **printtarg with `-iCR30`**, which printtarg does not know |
| `_printtarg_args` | `:1775-1795` — `pt_instr` resolution | a CR30 must be routed like `isis` (`:1786-1792`, `EXTERNAL_INSTRUMENTS`) or excluded from the printtarg path entirely |
| `_patch_ti2_instrument` | `:1442-1462` | precedent for post-hoc rewriting of `TARGET_INSTRUMENT` in a printtarg-produced `.ti2` (used today for CM triple density). **Reusable** if the CR30 is stamped with an Argyll-known name. |
| error-pattern table entry "Unsupported instrument type" | `:96-99` | the message printtarg emits if a CR30 code ever reaches it |

### VERIFIED: #159 §8's "no patch-capacity data is involved" — **TRUE ONLY ON THE ENGINE PATH**
`chart_creator.py:753-761` short-circuits on `_engine_total_patches`, and the
comment at `:753-754` says exactly what #159 quotes. But the engine path is
conditional:
- **Guided** always uses the engine for an `ENGINE_INSTRUMENTS` key (`:1078-1079`, `if not params.is_manual: return True`).
- **Manual** uses it only when `use_chromiq_layout_engine` is on (`:1101`) and neither legacy clip flag is set (`:1096-1099`).

So a **Manual CR30 chart with the engine setting off** falls to `query_patches`
and then to a printtarg binary search. That is a real, reachable path and a
**blocker for a naive registration**. Two candidate fixes, both a decision:
(a) add `"CR30"` to `EXTERNAL_INSTRUMENTS`-style handling so the printtarg path
is never taken; or (b) force `_should_use_engine` True for CR30 unconditionally.
Neither is written yet — **open question 4**.

### `data/patch_db.py`

| Symbol | Line | Need |
|---|---|---|
| `INSTRUMENT_LABELS` | `data/patch_db.py:180-186` | the single source of the friendly name; `ui/tabs/tab_chart.py:3406` builds the **Guided instrument combobox** straight from it |
| `EXTERNAL_INSTRUMENTS` | `:190` | see above — the existing "device Argyll cannot lay out" seam |
| `EXCLUDED_PAPERS` | `:209-213` | optional; no entry = every paper offered (the CM behaviour, stated at `:207-208`) |
| `INSTRUMENT_MODEL_WORDS` | `:1108-1116` | **needed**: `"CR30": ("cr30", "chnspec")` or the connected-device check is blind |
| `instrument_family_of(model)` | `:1119-1136` — the `for code in ("p3","CM","SS","isis","i1")` tuple at `:1133` | **a hard-coded tuple** — a CR30 key added to the dict but not to this tuple is silently never matched |
| `instrument_mismatch(chart_code, model)` | `:1139-1155` | works automatically once the two above are done |
| `PAPER_LABELS` / `PAPER_SIZES` | `:225`, `:192` | no change |

---

## 3. The `.ti2` / `.ti3` identity chain — **the hard constraint**

### 3.1 Where the name is written
`workflow/layout_engine/ti2_writer.py:79`
```
add(f'TARGET_INSTRUMENT "{geom.target_name}"')
```
`geom.target_name` comes from `instruments.TARGET_INSTRUMENT_NAME[key]`
(`instruments.py:361`). `extra_keywords` are emitted immediately after, at
`ti2_writer.py:87-88`, as `KEYWORD "value"` — so a private
`CHROMIQ_INSTRUMENT "CR30"` costs one tuple in the `Geom`.

### 3.2 The gate — VERIFIED BY RUNNING IT
`native/chartread_helper/chromiq_chartread.c:3626-3633`:
```c
if (itype == instUnknown) {
    if ((ti = icg->find_kword(icg, 0, "TARGET_INSTRUMENT")) >= 0) {
            if ((itype = inst_enum(icg->t[0].kdata[ti])) == instUnknown)
                error ("Unrecognised chart target instrument '%s'", …);
    } else {
        itype = instI1Pro;      /* Default chart target instrument */
    }
}
```
`tests/test_target_instrument_gate.py` already pins this against the **real**
binaries. I ran it: **6 passed in 0.25 s**, including
`test_stock_chartread_behaves_identically`, so the stock-`chartread` half is
confirmed on this machine.

**#159 §7's three claims are all VERIFIED**: unknown name → fatal in our fork
*and* in stock chartread; a known name passes; **omitting the keyword is more
permissive** (falls back to `instI1Pro`).

### 3.3 What `itype` is actually used for — the cheap way through
Grep of every use of `itype` in `chromiq_chartread.c`: `:900` (`instDTP51`
special case), `:968-970` (a `-v` warning when the connected device differs),
`:978` (the `instrument` JSON event's `chart_model` field), `:1874`
(`instDTP20` exclusion), `:3740-3741` (DTP20/41 extra keywords), `:4148`
(passed to `read_strips`). **Nothing else.** So mapping a CR30 name onto an
existing `instType` inside our own file is behaviourally inert apart from one
`-v` warning line and one JSON field — this is a genuinely small change, and it
does **not** require touching vendored Argyll or adding an enum value.

### 3.4 The unavoidable trade-off
Three options, and the choice is a **decision, not a discovery**:

| Option | Our fork | Stock chartread (`chartread_engine: "argyll"`, `core/settings.py`) | Honesty |
|---|---|---|---|
| **A.** `TARGET_INSTRUMENT "X-Rite ColorMunki"` + `CHROMIQ_INSTRUMENT "CR30"` via `extra_keywords` | works today, zero C change | **works** | the chart lies about its instrument; `ui/ti2_loader.is_colormunki()` (`:60-66`) will return True and the app will show ColorMunki swipe instructions |
| **B.** a new honest name, taught to our fork only | one `strcmp` before the `inst_enum` call at `:3629` | **FATAL** — user must never fall back | honest, but the fallback path breaks |
| **C.** omit the keyword | works (`instI1Pro`) | works | worst: silently claims i1Pro downstream, and the `.ti3` gets `TARGET_INSTRUMENT` written from `inst_name(atype)` at `:317-318` |

**Option A is the only one that keeps both readers working today**, but it
poisons every `is_colormunki` / `instrument_family` consumer listed in §5. A
hybrid — option A's name plus a `CHROMIQ_INSTRUMENT` keyword that
`ui/ti2_loader.py` checks **first** — is the smallest correct design, and needs
`read_target_instrument` to grow a companion `read_chromiq_instrument`.
**Open question 1.**

### 3.5 `.ti3` write-back
`chromiq_chartread.c:317-318`: the output `.ti3` gets
`TARGET_INSTRUMENT` = `inst_name(atype)` — **the connected instrument**, not the
chart's — and only when the keyword is not already present. In `-x` (external
values) mode no instrument is opened at all (`:4097`), so what lands in the
`.ti3` there is NOT VERIFIED and must be checked before relying on it.

### 3.6 `workflow/ti2_relayout.py` and `ui/dialogs/ti2_relayout_dialog.py`
`ti2_relayout_dialog.py:5326-5329` filters relayout targets by
`spec.instrument_flag in ENGINE_INSTRUMENTS` — so a CR30 automatically appears
there once §2's entry is made. Not separately verified beyond the grep + read
of those four lines.


---

## 4. Measure tab / chart-reading engine

### 4.1 #159 §4's protocol claim — **VERIFIED**
- **stdout, engine → app**: `workflow/chartread_engine.py:70-83` `parse_engine_line` — any line starting with `{` at column 0 is `json.loads`'d and must carry an `"event"` key.
- **stdin, app → engine**: `workflow/measure_manager.py:709` — `self._runner.write_stdin(_json.dumps(cmd) + "\n")`, translated from keystrokes by `chartread_engine.KEY_TO_COMMAND` (`:88-113`) and `KEY_TO_REPEATED_COMMAND` (`:123-126`).

So the boundary really is a **line-based JSON event/command protocol over
stdout/stdin**, and a non-Argyll backend can sit behind it.

### 4.2 The complete event vocabulary a backend must speak
Emitted by `chromiq_chartread.c` (grep of every `"event\":\"` literal), consumed
by `measure_manager._on_engine_event` (`:1052-1395`):

`session_start` (`c:4125`) · `instrument` (`c:977`) · `strip_ready` (`c:2032`) ·
`scan_started` (`c:780`) · `strip_read` (`c:568`) · **`spot_ready` (`c:600`,
emitted `c:2789`)** · **`patch_read` (`c:622`)** · `saved` (`c:494`) ·
`unread_confirm` (`c:2129`, `c:3040`) · `strip_warning` (`c:2432`, `c:2471`) ·
`strip_misaligned` (`c:2563`) · `mode_fallback` (`c:1444`) · `xy_place_sheet`
(`c:1598`) · `xy_locate` (`c:1670`) · `chart_reading` · `abort_confirm` ·
`cal_required` / `cal_done` · `error` (with `kind` ∈ misread / coms /
read_error / needs_cal / no_instrument / cal_failed / autosave_rename /
patch_not_found) · `aborted` · `done`.

**A spot-only backend needs a strict subset**: `session_start`, `instrument`,
`spot_ready`, `patch_read`, `saved`, `error`, `done` — plus the commands
`ok / forward / back / next_unread / retry / done / yes / skip / quit`.
Everything strip-shaped can be omitted.

`spot_ready` payload (`c:602-606`): `{event, id, loc, read, all_done, exyz[3]}`.
`patch_read` payload (`c:622-625`): `{event, id, loc, xyz[3], exyz[3], de}` —
XYZ scaled ×100, ΔE computed against the chart's expected value in D50 Lab.

### 4.3 EXISTING SEAMS FOR A DEVICE ARGYLL CANNOT DRIVE — three, not one
1. **`EXTERNAL_INSTRUMENTS`** (`data/patch_db.py:190`, used at
   `chart_creator.py:1786` and `ui/tabs/tab_chart.py:3407`) — the i1iSis
   pattern: ChromIQ lays out/prints, an external tool measures.
2. **chartread's `-x` external-values mode** — `chromiq_chartread.c:3186`,
   `:3250`, `:3489-3497`, and the spot loop's `if (xtern != 0)` branch at
   `:2791-2810`. In this mode **no instrument is opened at all**
   (`:4097` — `if (!xtern && !cq_replay_active())`), values are typed on stdin
   as `L*a*b*` (`-xl`) or `XYZ` (`-xx`), and — critically —
   **`cq_emit_spot_ready` at `:2789` fires *before* the branch**, so the JSON
   event stream works in `-x` mode too.
   **This is not exposed anywhere in ChromIQ's Python** (grep of `workflow/`,
   `ui/`, `core/` for `-x`/`xtern`: no hits). It is the cheapest possible live
   backend: a CR30 driver process writes `X Y Z\n` to the helper's stdin and the
   entire Measure tab, per-patch autosave, `.ti3` writing and profile chain work
   unchanged.
   ⚠ **Cost, NOT VERIFIED in detail**: `-x` carries no spectral data, so the
   `.ti3` would have XYZ only and `colprof -f` (FWA) plus every spectral Tool
   would be unavailable. Whether `-x` also changes what `TARGET_INSTRUMENT` is
   written into the `.ti3` (`c:317-318` uses `inst_name(atype)`, and `atype`
   is never set without an instrument) **must be checked before relying on it**.
3. **`--replay` / `cq_replay_*`** (`c:3320-3333`, `:2842-2843`,
   `tests/helpers/replay_tools.py`) — a scripted fake instrument that drives the
   real code path with no hardware. It is a **test** facility, but it proves the
   spot loop can be fed from outside and is the right harness for CR30 tests
   written before the device is on the bench.

### 4.4 Patch-by-patch is ALREADY a first-class, specified mode
- `MeasureParams.patch_by_patch` → `-p` (`measure_manager.py:169`, `:901-902`).
- It is a **user checkbox**, in both Guided and Manual
  (`ui/tabs/tab_measure.py:11157`, `:11175`), stored **per target** as
  `patch_by_patch` / `patch_by_patch_guided` (`workflow/measure_settings.py:48`,
  `:71`).
- `spot_ready` → `patch_ready` → highlight + page flip
  (`measure_manager.py:1141-1178`, `ui/tabs/tab_measure.py:10131`).
- `patch_read` → `patch_measured` → progress + tile
  (`measure_manager.py:1183-1187`, `tab_measure.py:4185`).
- The exit/abort behaviour is **specified**:
  `docs/design/measurement_exit_strategy.md:132-140` has a "Strip mode vs
  patch-by-patch — where they genuinely differ" table.

**Consequence: a CR30 beta does not have to build a spot workflow. It exists,
is specified, and is shipping.**

### 4.5 What a live CR30 backend must additionally provide
Beyond the JSON vocabulary in §4.2: the reference implementation already in
`/Users/Basti/develop/chromiq-cr30-research/src/cr30/device.py`
(`CR30.open_usb()`, `open_ble()`, `identify()`, `read_measurement()`),
plus — from that repo's own STATUS.md — **the magnet-near-the-aperture hazard**:
a measurement silently becomes a white calibration returning a stored constant.
Nothing in ChromIQ can detect that; a guard has to live in the backend or in a
plausibility check on the reading. **Open question 8.**

---

## 5. UI menus and pickers — every place an instrument name appears

| # | File:line | What it is | Work |
|---|---|---|---|
| 5.1 | `ui/tabs/tab_chart.py:3406-3409` | **Guided** "Measurement Instrument" combobox — built by iterating `INSTRUMENT_LABELS`, skipping `EXTERNAL_INSTRUMENTS` | free once `INSTRUMENT_LABELS` has a row |
| 5.2 | `data/parameters.yaml:623-636` | **Manual** printtarg `-i` `ParameterWidget` — `choices` + `labels` + `tooltip_body` | one-liner in the YAML, **but see §9 — it breaks all 12 i18n overlays** |
| 5.3 | `ui/dialogs/layout_options_panel.py:76-79` | `LayoutOptionsPanel.INSTRUMENTS` — the **engine panel's** instrument combobox | one line |
| 5.4 | `ui/dialogs/layout_options_panel.py:81-91` | `mode_label_for` — "Clip border:" / "Density:" / "Patch shape:" | new branch or accept the `"Mode:"` fallback |
| 5.5 | `ui/dialogs/layout_options_panel.py:93-126` | `mode_tooltip_for` | new branch or accept the generic fallback (`:124-126`) |
| 5.6 | `ui/dialogs/layout_options_panel.py:128-138` | `modes_for` | new branch or accept `[("default", "Default")]` (`:138`) |
| 5.7 | `ui/dialogs/layout_options_panel.py:1857`, `:1946`, `:2289` | three `("CM","SS")` tuples gating the optional notes/clip band UI | three one-liners, or the CR30 can never carry a notes band |
| 5.8 | `ui/dialogs/layout_options_panel.py:1864-1865` | `cm_stagger_cb` visibility — `inst == "CM"` | no change (CR30 should not stagger) |
| 5.9 | `ui/dialogs/layout_options_panel.py:2898` | `_instr_friendly` for the `{instrument}` sheet-text placeholder | one line |
| 5.10 | `ui/dialogs/settings_dialog.py:3126-3131` | `_LAYOUT_INSTRUMENTS` — **Preferences → Chart Layout** picker (its comment at `:1855-1861` explains why DTP41/51 were dropped) | one line |
| 5.11 | `ui/dialogs/settings_dialog.py:1517` | `_MARGIN_INSTRUMENTS` — **Preferences → Instrument Limits** picker | one line |
| 5.12 | `ui/tabs/tab_chart.py:1474-1477` | `_MARGIN_INSTR_LABEL` | ⚠ **silent-wrongness trap**: `tab_chart.py:16174` does `.get(instr_flag, "i1Pro")` — an unregistered CR30 chart is judged against the **i1Pro's 38 mm top margin** |
| 5.13 | `core/settings.py:668-671` | `THRESHOLD_INSTR_LABEL` | safer: an unknown flag returns `None` from `thresholds_for_combo` (`:698-710`) → no thresholds checked |
| 5.14 | `ui/tabs/tab_chart.py:8543-8544` | `_suggest_target_name`'s instrument label map | one line, cosmetic |
| 5.15 | `ui/dialogs/ti2_relayout_dialog.py:7726` | same map in the relayout dialog | one line, cosmetic |
| 5.16 | `ui/dialogs/ti2_relayout_dialog.py:5326-5329` | relayout targets filtered by `ENGINE_INSTRUMENTS` | free once §2 is done |
| 5.17 | `workflow/layout_engine/chart.py:277-278` | `_instr_friendly` for the engine stamp | one line |
| 5.18 | `ui/tabs/tab_chart.py:1084-1086`, `:2138`, `:2154` | `INSTRUMENT_GROUP_LABELS` + the built-in-preset group order | only if CR30 presets ship |
| 5.19 | `ui/ti2_loader.py:35-39` | `KNOWN_INSTRUMENTS` | one line — **and `tests/test_knut_beta106_target_instrument.py:73` asserts the app reads names from this constant** |
| 5.20 | `ui/ti2_loader.py:60-66 / 69-76 / 78-93 / 96-107 / 110-122` | `is_colormunki`, `is_spectroscan`, `instrument_label`, `is_i1pro`, `instrument_family` | **needs a `is_cr30` / `"cr30"` family**, or every wording branch falls to the generic text |
| 5.21 | `ui/ti2_loader.py:125-155`, `:157-175`, `:178-200`, `:202-232` | four per-family instruction texts (calibration / strip / spot-tool / **patch**) | `patch_measurement_instructions_html` (`:202`) is the one a CR30 user reads — a CR30 branch is **new user-facing text** → §M-PROPOSED (see §10) |
| 5.22 | `ui/ti2_loader.py:234-265` | `disable_bidir_for_instrument` / `force_bidir_for_instrument` | must return "no bidirectional" for a spot device |
| 5.23 | `data/patch_db.py:1108-1136` | `INSTRUMENT_MODEL_WORDS` **and** the hard-coded tuple at `:1133` | both, or the connected-device mismatch check is blind |
| 5.24 | `ui/tabs/tab_measure.py:4470` | `if "colormunki" in low or "i1studio" in low or "ccstudio" in low` | verify what it gates before deciding |
| 5.25 | `ui/tabs/tab_check_refine.py:248`, `ui/tabs/tab_profile.py:4095` | `is_colormunki(self._detected_instrument)` gates UV/FWA options | a CR30 is **also** UV-cut-equivalent (LED, no OBA excitation) — it must land on the same side, or `colprof -f` is offered when it must not be |
| 5.26 | `ui/dialogs/welcome_dialog.py` (two hits) | prose listing supported instruments | translated strings |

---

## 6. Settings / Preferences

| Symbol | Line | Need | Size |
|---|---|---|---|
| `_MARGIN_INSTRUMENTS` | `ui/dialogs/settings_dialog.py:1517` | add `"CR30"` — feeds the picker at `:2746` | one line |
| `_MARGIN_SEED` | `core/settings.py:511-524` | **optional.** SpectroScan is in `_MARGIN_INSTRUMENTS` and `THRESHOLD_INSTR_LABEL` and has **no seed rows at all** — `margin_inspector.check_violations` returns `[]` for a combo with no thresholds (`workflow/margin_inspector.py:100-113`). So no seeds = no checking, which is honest until the aperture/positioning data exists | zero, deliberately |
| `THRESHOLD_INSTR_LABEL` | `core/settings.py:668-671` | add `"CR30": "CR30"` | one line |
| `MODEL_DEFAULTS` | `core/measure_pace.py:320-331` | add `"cr30": (0.0, None)` or `(1.0, None)` | one line |
| `ESTIMATE_PATCHES` | `core/measure_pace.py:345-352` | add `"cr30": None` | one line |
| `_ARGYLL_MODEL_KEYS` | `core/measure_pace.py:376-388` | add `("cr30", "cr30")` so a reported model resolves | one line |
| pace `labels` dict | `ui/dialogs/settings_dialog.py:1700-1707` | add `"cr30"` — the rows themselves are **generated from `MODEL_DEFAULTS`** at `:1713-1714`, so the row appears automatically | one translated line |
| `_pace_example` key tuple | `ui/dialogs/settings_dialog.py:3121` and name map `:1865-1867` | hard-coded `("colormunki","i1pro2","i1pro","i1pro3","i1pro3plus")` — a CR30 with no rate contributes nothing anyway | none |
| `AppSettings` defaults `pace_sample_hz_*` | `core/settings.py:268-269` | only if a rate is wanted; **not wanted** for a spot device | none |
| `SETTINGS_SCHEMA = 22` | `core/settings.py:718` | **not** a bump — adding a NEW key is not changing an existing default. Only bump if an existing default moves | none |

### VERIFIED: #159 §8b's pace warning is right in principle and **moot in practice**
Two independent findings:
1. **The precedent already exists.** `MODEL_DEFAULTS["spectroscan"] = (250.0, None)`
   (`core/measure_pace.py:330`) with `ESTIMATE_PATCHES["spectroscan"] = None`
   (`:351`), and the file's own comment at `:317-319` says why: *"a motorised
   table … there is no swipe to be too quick and no threshold worth setting."*
   The UI renders that as **"Off"** and **"N/A"**
   (`settings_dialog.py:1741-1743`, `:1767-1770`). A CR30 row is the same
   shape. So this is **a one-line table entry, not "a small design job of its
   own"** as #159 §8b claims.
2. **The pace model never runs in spot mode at all.** `_report_strip_pace` is
   connected only to `strip_measured` (`ui/tabs/tab_measure.py:1022`), and
   `strip_measured` is emitted only from the `strip_read` event
   (`workflow/measure_manager.py:1135`). Patch-by-patch emits `patch_measured`
   instead, and the code says so outright at `tab_measure.py:1016-1019`:
   *"reading pace is judged per STRIP, not per patch … nothing subscribes to
   patch events for pace any more."*

⚠ **The one real trap**: `_pace_config` (`tab_measure.py:4322-4370`) falls back
to `defaults_for(None)` = the **i1Pro's `(100.0, 20)`** for an unrecognised
instrument (`measure_pace.py:680-687`). Harmless in spot mode (nothing reads
it), but it would bite immediately if a CR30 chart were ever read in strip mode.
A `"cr30"` row closes it.

---

## 7. Per-target settings

**`docs/design/per_target_settings.md` is BINDING and it already answers this.**

- **The CHART instrument is per target.** `per_target_settings.md:495`, Q1:
  *"Are page count and instrument/paper per target, or per project?"* → Knut:
  *"yes, per target"*. It reaches the store as an ordinary `ParameterWidget`
  row, discovered generically by `ui/tabs/tab_chart.py:13570-13583`
  (`per_target_widgets`) — **so a new `-i` choice needs no per-target code at
  all.** Guided's copy rides in `create_chart_ui["guided"]`
  (`tab_chart.py:13598`).
- **The MEASURING instrument is explicitly NOT per target.**
  `workflow/measure_settings.py:31`:
  `"instrument": "which instrument is plugged in, not a property of the run"`.
  And it is not a device name — `measure_manager.py:891` passes it as
  `-c <p.instrument>`, chartread's **communication port**. `spot_read_manager.py:51-55`
  records the same correction for spotread. This confirms the research repo's
  `INTEGRATION.md §1` finding that #159's framing of instrument selection is wrong.
- `per_target_settings.md:293` (N-6) matters if a CR30 calibration run type is
  ever added: a calibration must not seed the block.
- **Drift guard**: `tests/test_measure_settings.py` fails if a `MeasureParams`
  field is neither in `MEASURE_CONTROLS` nor in `NOT_A_SETTING`
  (`measure_settings.py:14-18`). Any new CR30 measure field must be filed in one
  of the two.

---

## 8. Margin inspector and other instrument-keyed code

| Place | Line | Behaviour with an unregistered CR30 |
|---|---|---|
| `workflow/margin_inspector.check_violations` | `:100-126` | `thresholds is None` → `[]`. **Safe** |
| `workflow/margin_inspector` ruler lookup | `:300-306` | `instruments.build(inst)` raises `ValueError` for an unknown key, swallowed by `except Exception` at `:305` → `ruler_mm = None`. **Safe, and correct for a rulerless device** |
| `core/settings.thresholds_for_combo` | `:698-710` | `THRESHOLD_INSTR_LABEL.get(flag)` → `None` → no thresholds. **Safe** |
| `ui/tabs/tab_chart.py:16174` | | `_MARGIN_INSTR_LABEL.get(flag, "i1Pro")` → **judged against the i1Pro's 38/26/9/9 mm. NOT SAFE.** |
| `workflow/layout_engine/instruments.default_ruler_mm` | `:142-155` | `build()` raises → caught → `0.0`. **Safe and correct** |
| `core/usb_driver_installer.py` | (WinUSB, Argyll's own devices) | does **not** cover a CH340/CP210x serial bridge. Per the research repo, macOS 15.7.9 needs **no** driver for VID `0x1A86` PID `0x7523` — so this file is out of scope for macOS; Windows is NOT VERIFIED |


---

## 9. i18n — the real cost

**13 languages: English source + 12 catalogues** (`data/i18n/*.json`: de, es, fr,
it, ja, nl, no, pl, pt, ru, sv, zh_CN) **and 12 parameter overlays**
(`data/i18n/parameters.<code>.yaml`) — counted on disk.

### 9.1 Hard gates in `tests/test_i18n.py`
| Test | Line | What it demands |
|---|---|---|
| `test_catalog_is_complete` | `:78` | every `tr()` key extracted by `scripts/i18n_extract.py` exists in **all 12** JSON catalogues |
| `test_catalog_has_no_stale_keys` | `:84` | **no catalogue may hold a key that is no longer in the code** |
| `test_placeholders_match_source` | `:90` | `{name}` placeholders must survive translation |
| `test_short_labels_stay_compact` | `:96` | a ≤24-char English string may not translate to >1.6× + 6 chars |
| `test_parameters_overlay_covers_every_parameter` | `:124` | for every `parameters.yaml` entry, each overlay must have `name`, `tooltip_title`, `tooltip_body` and **`len(labels)` equal to the source's** (`:139-140`) |

**English placeholders satisfy all five** (the key must exist; its value is not
checked against English), so the beta policy is workable.

### 9.2 The costed list
1. **`data/parameters.yaml:626-632`** — one new `choices` entry + one new
   `labels` entry ⇒ **12 mandatory overlay edits**, one label each, or
   `test_parameters_overlay_covers_every_parameter` fails **12 times**.
2. **`ui/tabs/tab_chart.py:3416-3434`** — the Guided instrument tooltip is a
   **single ~1,200-character `tr()` key**. Adding a CR30 bullet **changes the
   key**, so the old key goes stale in all 12 catalogues
   (`test_catalog_has_no_stale_keys` fails ×12) and the new one is missing
   (`test_catalog_is_complete` fails ×12). **24 test failures from one bullet.**
   Same shape, smaller, for `data/parameters.yaml:639-663`'s `tooltip_body`
   (presence-checked only, so it fails nothing — but ships stale text).
3. **New per-instrument branches**, each one or two new `tr()` keys:
   `layout_options_panel.mode_label_for` / `mode_tooltip_for` / `modes_for`
   (`:81-138`), `settings_dialog` pace `labels` (`:1700-1707`), and the four
   `ui/ti2_loader.py` instruction texts (`:125`, `:157`, `:178`, `:202`).
4. **Every §M message** (see §10) is a `tr()` string in
   `workflow/measurement_messages.py` and reaches the catalogues via
   `tests/test_i18n.py:191` (`test_the_message_catalogue_reaches_the_translations`).

**Rough total for a minimal registration: ~8-14 new `tr()` keys + 1 changed key
+ 12 overlay label lines** ⇒ 12 × (~9-15) JSON entries. `python
scripts/i18n_extract.py --missing <code>` lists them per language.

---

## 10. Design specifications — which ones bind this work

`CLAUDE.md` makes `docs/design/` binding, with two obligations: read before
changing, and **report** (do not silently fix) a fault that contradicts a spec.

| Spec | Binds because | What it forces |
|---|---|---|
| `unified_measurement_management.md` | §M is the message catalogue for **every** measurement window | any new CR30 wording goes to **§M-PROPOSED first** (heading at `:928`) |
| `measurement_exit_strategy.md` | `:132-140` already tabulates strip vs **patch-by-patch** differences | a CR30 read is a patch-by-patch read — the exits are already specified and must not be re-invented |
| `per_target_settings.md` | `:495` (Q1) rules chart instrument/paper **per target**; `:293` (N-6) rules calibration seeding | §7 above |
| `measurement_window_sounds.md` | which sound each measurement window plays | a spot read's cue is already defined by patch-by-patch mode |
| `tool_availability.md` (**DRAFT**) | `:93` lists `spot_read` as always available | a CR30 entry in the Tools matrix would need Knut/Basti sign-off; the doc is not confirmed |
| `calibration_run_type.md` | only if a CR30 calibration run type is proposed | out of scope for a beta |
| `verification_printing_and_target.md` (**DRAFT**) | only if CR30 verification charts are in scope | out of scope for a beta |

### 10.1 How `tests/test_message_catalogue.py` enforces §M-PROPOSED — VERIFIED
Reading the test end to end:
- `_spec_messages()` (`:38-52`) parses `## M. The message catalogue` out of
  `docs/design/unified_measurement_management.md` up to `### M-x.`
- `test_every_message_in_the_document_exists_in_the_code` (`:60`) — every §M ID
  must exist in `measurement_messages.CATALOGUE`
- `test_every_headline_is_the_documents_headline` (`:70`) — **word for word**
  for any message marked `approved`
- `test_proposed_messages_are_marked_as_such_in_the_document` (`:81`) — every ID
  in `M.PROPOSED` must have a `### <ID> ·` heading whose first 300 chars contain
  `PROPOSED`
- `test_nothing_is_quietly_proposed` (`:171`) —
  `assert set(M.PROPOSED) == AWAITING_APPROVAL`, the hand-maintained set at
  `:97-167`
- `test_an_approved_message_is_not_still_headed_proposed` (`:187`) — the reverse

**So the exact procedure for one new CR30 window, in ONE commit:** write the
message under `## M-PROPOSED.` (`unified_measurement_management.md:928`) with
`### M-CR30-… · PROPOSED ·` and a `> **headline**` line; add it to
`workflow/measurement_messages.CATALOGUE` with `approved=False`; add its ID to
`AWAITING_APPROVAL` in `tests/test_message_catalogue.py`. Miss any one and the
suite fails.

### 10.2 What must NOT go into a spec
`CLAUDE.md`, quoting Knut 2026-08-08: only **human-confirmed** behaviour is
written into a specification. Anything CR30 that this branch verifies goes into
an `⏳ Awaiting confirmation` section with `**Confirmed by:** *nobody yet.*`;
`tests/test_design_specs_are_binding.py` fails a "Confirmed" section that names
nobody. **#159's own header says it too**: *"Nobody here has the device.
Nothing about the CR30 is hardware-verified."*

---

## 11. Where a spot-only device breaks a strip assumption

| Assumption | Where | What breaks | Severity |
|---|---|---|---|
| **A strip has a length cap (ruler/jig)** | `instruments.py:135` `ruler_mm`, `:386`, `:492`, `:507` | none — `ColorMunki`/`SpectroScan` already set `0.0` and the code handles it (`default_ruler_mm` `:142-155`, `margin_inspector:300-306`) | **none** |
| **A strip needs a white lead-in and trailer** | `instruments.py` `lcar`/`lspa`/`tspa` on every branch | wasted paper: the CM branch reserves `lcar=20`, `tspa=25` (`:447-451`) for a swipe that never happens. Fewer patches per sheet than the device could take | **cosmetic/efficiency** |
| **A strip needs a clip border** | `instruments.py:385` (i1/p3 `has_clip_border=True` unconditionally) vs `:452` (CM, conditional) | none if the CR30 copies the **CM** branch | **none** |
| **Reading is a swipe with a pace** | `core/measure_pace.py`, `ui/tabs/tab_measure.py:9862` | **inert in spot mode** — `_report_strip_pace` is wired only to `strip_measured` (`tab_measure.py:1022`). The i1Pro fallback in `_pace_config` (`:4340`) would bite only in strip mode | **latent** |
| **Reading is bidirectional** | `ui/ti2_loader.py:234-265` `disable_bidir_for_instrument` / `force_bidir_for_instrument`; `measure_manager.py:892-896` `-B`/`-b` | a CR30 must land on "disable" like the SpectroScan (`is_spectroscan` `:69-76`, its docstring says the bidi concept does not apply) | **must be handled** |
| **A swipe arrow is drawn on the preview** | `ui/tabs/tab_measure.py:535-586`, `ui/tiff_preview.py:1672-1691` | cosmetic; the SpectroScan already hides it (`tab_measure.py:4186-4190`) | **cosmetic** |
| **Strips are the unit of progress** | `measure_manager.py` `strip_ready`/`strip_read`/`all_stripes_done` | already solved: `spot_ready`/`patch_read` and the `_saw_spot_ready` completion logic (`measure_manager.py:1147-1160`) | **none** |
| **Per-strip autosave** | `saved` event (`c:494`), `read_patches` count | spot mode reuses the same autosave; **verify the cadence is per patch, not per strip** — a 300-patch, 10-minute session must not risk 299 readings. NOT VERIFIED | **must check** |
| **Instruments come from Argyll** | `measure_manager._build_args:891` `-c <port>` | a CR30 is not an Argyll device at all → §4.3's three seams | **the central design question** |
| **A chart is read once, in strip order** | `spot_ready` navigation (`forward`/`back`/`next_unread`/`goto`) | already right for spot | **none** |
| **Spectral data is 380-730 nm / 36 bands** | `ui/ti2_loader.has_spectral_data:287`, `SPECTRAL_BANDS` regex `:27`; `chromiq_chartread.c:372-394` writes `SPECTRAL_BANDS`/`_START_NM`/`_END_NM` from the instrument | a 31-band 400-700 `.ti3` is legal CGATS, but every Tool that assumes a band count is a risk (#159 §10) — **NOT VERIFIED, needs its own sweep** | **unknown** |
| **`colprof -f` (FWA) needs a non-UV-filtered instrument** | `ui/tabs/tab_check_refine.py:248`, `ui/tabs/tab_profile.py:4095` — gated on `is_colormunki` | a blue-pump white LED does not excite OBAs either; a CR30 must be gated the **same way as a ColorMunki** or FWA is offered when it cannot work | **must be handled** |


---

## 12. The verified touch-point count

**48 code touch points across 17 files, plus 24 i18n files.** Only ONE is real
work; the rest are table rows and branch arms.

| File | Touch points | Lines |
|---|---|---|
| `workflow/layout_engine/instruments.py` | 5 | 26, 138, 159, 311, **354-509 (new `_build_base` branch — THE ONLY REAL WORK)** |
| `workflow/layout_engine/presets.py` | 4 | 24, 167, 397, 496 |
| `workflow/layout_engine/chart.py` | 1 | 277 |
| `workflow/layout_engine/papers.py` | 1 (decision) | 19 |
| `workflow/chart_creator.py` | 3 | 130, 1123-1160, 1786 |
| `data/patch_db.py` | 4 | 180, 190, 1108, 1133 |
| `ui/ti2_loader.py` | 6 | 35, new `is_cr30`, 110, 125, 202, 234/252 |
| `native/chartread_helper/chromiq_chartread.c` | 1 | 3629 |
| `data/parameters.yaml` | 1 | 623-632 |
| `ui/dialogs/layout_options_panel.py` | 8 | 76, 81, 93, 128, 1857, 1946, 2289, 2898 |
| `ui/dialogs/settings_dialog.py` | 3 | 1517, 1700, 3126 |
| `core/settings.py` | 1 (+1 optional seed) | 668 (511) |
| `core/measure_pace.py` | 3 | 320, 345, 376 |
| `ui/tabs/tab_chart.py` | 3 | 1474, 3416, 8543 |
| `ui/dialogs/ti2_relayout_dialog.py` | 1 | 7726 |
| `ui/tabs/tab_profile.py` | 1 | 4095 |
| `ui/tabs/tab_check_refine.py` | 1 | 248 |
| `ui/tabs/tab_measure.py` | 1 | 4470 |
| `data/i18n/parameters.*.yaml` | 12 files | one `labels` entry each |
| `data/i18n/*.json` | 12 files | ~9-15 keys each |

`ui/tabs/tab_chart.py:3406` (the Guided combobox), `workflow/layout_engine/ti2_writer.py:79`
(the `TARGET_INSTRUMENT` write) and `ui/dialogs/ti2_relayout_dialog.py:5326`
(relayout filter) are **free** — they derive from the tables above.

---

## 13. What ALREADY EXISTS and must be reused, not reinvented

1. **The whole patch-by-patch (spot) measurement mode.** A user checkbox in
   Guided and Manual (`tab_measure.py:11157`, `:11175`), stored per target
   (`measure_settings.py:48`, `:71`), driving `-p` (`measure_manager.py:901`),
   with `spot_ready`/`patch_read` events, per-patch highlight and page flip
   (`tab_measure.py:10131`), a specified exit strategy
   (`measurement_exit_strategy.md:132-140`), and its own completion window.
2. **Per-patch autosave — VERIFIED, already built.**
   `chromiq_chartread.c:3098` and `:3120` call `cq_write_ti3_atomic()` with the
   comment *"autosave per patch"*. #159 §9's P4 asks for this "from day one";
   it exists.
3. **The JSON engine protocol** — `chartread_engine.py:70-126`,
   `measure_manager.py:678-712`. A backend boundary that needs no C.
4. **chartread's `-x` external-values mode** (`chromiq_chartread.c:2791-2810`,
   `:3489-3497`, `:4097`) — a hardware-free path through the real reader that
   still emits `spot_ready`. Not exposed in Python. **The single cheapest live
   backend.**
5. **The `--replay` fake instrument** (`c:3320-3333`, `tests/helpers/replay_tools.py`)
   — hardware-free tests of the real code path.
6. **`EXTERNAL_INSTRUMENTS`** (`patch_db.py:190`) — the i1iSis precedent for a
   device Argyll cannot drive.
7. **`Geom.extra_keywords`** (`instruments.py:73` → `ti2_writer.py:87-88`) — a
   private `.ti2` keyword for one tuple.
8. **`_patch_ti2_instrument`** (`chart_creator.py:1442-1462`) — post-hoc
   `TARGET_INSTRUMENT` rewriting, already shipping for CM triple density.
9. **The ColorMunki geometry branch** (`instruments.py:394-453`) — no ruler cap,
   optional clip band, three density levels. The right template, as #159 says.
10. **The SpectroScan's "no pace" pattern** (`measure_pace.py:330`, `:351`) —
    the answer to #159 §8b, already written.
11. **`tests/test_target_instrument_gate.py`** — the constraint is already pinned
    against the real binaries. Its own docstring says *"When the CR30 … is
    implemented, the first test here is the one that must change, deliberately."*
12. **`data/patch_db.instrument_mismatch`** (`:1139-1155`) — the wrong-device
    warning, needs only two table rows.
13. **`workflow/margin_inspector`** — degrades safely for an unknown instrument.
14. **The reverse-engineered driver** in
    `/Users/Basti/develop/chromiq-cr30-research/src/cr30/device.py`.

---

## 14. The smallest viable beta slice

**Goal: a user can create a CR30 chart in ChromIQ and read it patch by patch.**

### REQUIRED
| # | Work | Size |
|---|---|---|
| B1 | Decide `TARGET_INSTRUMENT` (§3.4). The zero-C-change answer is `"X-Rite ColorMunki"` + `CHROMIQ_INSTRUMENT "CR30"` via `extra_keywords`; the honest answer costs one `strcmp` at `chromiq_chartread.c:3629` **and breaks stock chartread** | a decision |
| B2 | `instruments.py` CR30 `Geom` — the only real code | ~40 lines, copy of the CM branch |
| B3 | The 47 remaining table/branch registrations (§12) | mechanical |
| B4 | Route CR30 away from printtarg (§2 — `ENGINE_INSTRUMENTS` + the `estimate_patches` Manual-engine-off path) | small, but **must not be skipped** |
| B5 | `is_cr30` + `instrument_family` + the patch-by-patch instruction text | small + §M-PROPOSED |
| B6 | Bidirectional off (`ti2_loader.py:234-265`) and FWA gated like a ColorMunki (`tab_profile.py:4095`, `tab_check_refine.py:248`) | 4 lines |
| B7 | 12 overlay labels + 12 catalogue stubs (English placeholders) | mechanical |
| B8 | Getting the readings in. **Cheapest: `-x` external values.** Next cheapest: a Python backend speaking §4.2's subset | see risks |

### CAN WAIT
Spectral `.ti3` (31 bands) · BLE transport · CR30 margin-threshold seeds ·
CR30 built-in chart presets · a CR30 pace/timing model · calibration-run type ·
verification charts · the Tools sweep for 31-band spectral data · Windows/Linux
enumeration · aperture-tuned geometry (needs the device on the bench).

### The honest question the slice turns on
**B8 is not a registration problem, and everything else is.** B1-B7 is one
day's mechanical work with one 40-line geometry block. B8 is either
(a) `-x` mode wired up — hours, but XYZ-only, no spectral, and the `.ti3`'s
`TARGET_INSTRUMENT` behaviour in `-x` is NOT VERIFIED; or
(b) a real backend process — days; or
(c) a ColorQC2 CSV import (#159 §5 option C) — needs no device driver at all
but is a separate feature with its own patch-identity guard.

---

## 15. Risks and blockers for a same-day beta

| # | Risk | Severity |
|---|---|---|
| R1 | **`TARGET_INSTRUMENT` has no free answer.** An honest name is fatal in stock chartread, which is a **supported setting** (`core/settings.py`, `chartread_engine: "argyll"`) and the fallback when the helper is missing. A borrowed ColorMunki name makes every `is_colormunki` consumer lie | **BLOCKER — needs a ruling** |
| R2 | **No aperture-derived geometry exists.** #159 §12 Q2/Q3 are answered from the manufacturer (4 mm, 45°/0°), but the minimum patch size a hand-placed 4 mm aperture needs is a *positioning-error* figure, and #159 §9c steps 4 and 6 (the measurements that set it) are still open. A guessed patch size ships charts that cannot be read | **HIGH — geometry is a guess** |
| R3 | **Manual + engine-off routes a CR30 to printtarg** (`chart_creator.py:753-792`, `:1794`), which does not know the flag. Silent until someone unticks a checkbox | **HIGH — easy to miss** |
| R4 | **`_MARGIN_INSTR_LABEL.get(flag, "i1Pro")`** (`tab_chart.py:16174`) judges an unregistered CR30 chart against the **i1Pro's 38 mm top margin** — a false "Margins: OK/violated" | **MEDIUM — silent wrongness** |
| R5 | **The i18n stale-key trap.** One bullet added to `tab_chart.py:3416` fails `test_i18n.py` 24 times | **MEDIUM — gate-breaking, easily fixed** |
| R6 | **New wording is spec-gated.** Every CR30 window/instruction sentence must go through §M-PROPOSED + `AWAITING_APPROVAL` in the same commit, or `tests/test_message_catalogue.py` fails | **MEDIUM — process, not code** |
| R7 | **31 bands vs 36.** No sweep has been done of what ChromIQ Tools assume about `SPECTRAL_BANDS` / `SPECTRAL_START_NM`. NOT VERIFIED | **MEDIUM — unknown scope** |
| R8 | **The magnet hazard** (research repo `STATUS.md`): a magnet near the aperture silently turns a measurement into a white calibration returning a stored constant, invisible to the host. Nothing in ChromIQ can see it | **HIGH for data integrity** |
| R9 | **Nobody has confirmed any CR30 behaviour.** #159's own header. Nothing may enter a design spec | **process** |
| R10 | `-x` mode's `.ti3` `TARGET_INSTRUMENT` and spectral behaviour is NOT VERIFIED — `chromiq_chartread.c:317-318` writes `inst_name(atype)` and `atype` is never set when no instrument opens | **MEDIUM — settle before choosing B8(a)** |

**Verdict on a same-day beta:** the *registration* half (B1-B7) is achievable in
a day. **B8 is not**, unless `-x` mode turns out to work as it reads — and that
has not been run once. A beta that ships CR30 chart creation without a reading
path would produce charts nobody can measure, which is worse than nothing.

---

## 16. Open questions — numbered, must be answered before code

1. **`TARGET_INSTRUMENT`**: borrowed `"X-Rite ColorMunki"` + `CHROMIQ_INSTRUMENT "CR30"`, or an honest new name that stock chartread refuses? (§3.4) — *Basti's call.*
2. If the borrowed name is chosen, does `ui/ti2_loader.read_target_instrument` grow a companion that reads `CHROMIQ_INSTRUMENT` **first**, so `is_colormunki` stops lying? (§3.4)
3. **Reading path for the beta**: `-x` external values, a JSON-protocol backend, or ColorQC2 CSV import? (§4.3, §14 B8)
4. **How is the printtarg path blocked?** Add `"CR30"` to `EXTERNAL_INSTRUMENTS`, or make `_should_use_engine` unconditional for CR30? (§2)
5. **What patch size?** #159 §9c steps 4 and 6 (aperture + positioning spread) are the inputs and neither is measured. What is the interim figure, and is it flagged as provisional on screen? (§15 R2)
6. **Clip band**: offerable-but-off (the CM shape), or not offered at all? Which of `layout_options_panel.py:1857/1946/2289` gain a CR30? (§5.7)
7. **Does the CR30 get built-in presets** and a group heading (`tab_chart.py:2138`), or ship with none? (§5.18)
8. **The magnet hazard** (§15 R8): is a plausibility guard in scope for the beta, and where — the backend, or a `.ti3` sanity check?
9. **Spectral or XYZ-only `.ti3`?** #159 §6's open decision. It changes whether `colprof -f` and the spectral Tools are reachable, and `-x` mode forces XYZ-only. (§4.3, §15 R7)
10. **Which `tr()` strings ship as English placeholders**, and is that recorded so the translation round is not lost? (§9)
11. **Is a `Geom` with no strip lead-in/trailer wanted** (a true spot grid, denser than any printtarg layout), or does the CR30 keep the CM furniture so the chart still looks familiar? (§11)
12. **Does the CR30 need margin-threshold seeds at all** for the beta, or does it ship like the SpectroScan — listed in the picker with no seeded rows? (§6)
13. **Which spec, if any, gains a CR30 section**, and does anything reach `⏳ Awaiting confirmation` before hardware confirmation? (§10.2)

STATUS: complete
