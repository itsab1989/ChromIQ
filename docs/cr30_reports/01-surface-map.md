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
| "Nine touch points, all one-liners bar the geometry block" | **FALSE — undercounts by roughly 3×.** See the table in §12. | this document |

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

