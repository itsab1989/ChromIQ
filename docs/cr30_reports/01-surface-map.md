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
