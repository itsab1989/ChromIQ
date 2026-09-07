# Critic report on plan v1 — staged, appended as sections finish

Critic: senior colour-science / software review, 2026-09-04.
Tree: `/Users/Basti/develop/ChromIQ` @ `feature/engine-accuracy-challenge` (no repo file edited by the critic).
Method: every verdict below cites file:line as read today; every "measured" line names the command. Nothing is "probably".

## 0. Read list (in full, not remembered)

`workflow/profile_engine/builder.py` (622 l), `accuracy.py`, `ti3_data.py`, `gp.py`, `spectral.py`, `fwa.py`, `icc_writer.py`, `gamut_map.py` (source_kind, oracle, cache key, fit_multiink_anchor, build_mapped_b2a), `b2a.py` (ink_priors, invert_to_device, refine_b2a_clut), `workflow/engine_builder.py`, `ui/tabs/tab_profile.py` 570–640 / 2790–2960 / 5055–5190, `ui/dialogs/scanin_dialog.py` 640–660 / 5330–5380, `ui/dialogs/settings_dialog.py` 583–700, the four named test files plus the inventories of `test_profile_engine*.py`, `test_engine_v2_candidates.py`, `test_engine_v2_harness.py`; `benchmarks/README.md`; `/Applications/Argyll/bin/colprof` usage text (3.5.0); the two baseline logs and three ICCs in `builds/`.

## 1. Measurements the critic ran (each ≤ 1 min; commands in `scratchpad/`)

| # | what | command / probe | result |
|---|---|---|---|
| M1 | A2B1(device white) and B2A1(L=100) on the plan's three ICCs and on a colprof reference of the same chart | `xicclu -ff -ir -pl <icc>` ← `1 1 1`; `xicclu -fb -ir -pl <icc>` ← `100 0 0`; reference: `colprof -ql -D ref924 ref924` (2.2 s) on a scratch copy of `charts/real-rgb-924p-spectral36.ti3` | engine **fast**: white → L 99.756 a 0.095 b −0.111; L=100 → RGB 0.9976/0.9956/0.9960. engine **accurate** (both ICCs): white → L 99.936; L=100 → RGB 0.9970/0.9954/0.9962; perceptual L=100 → 0.9949/0.9953/0.9955. **colprof**: white → L 100.00003 a −0.0004 b 0.0011; L=100 → RGB 0.99996/0.99995/0.99996 |
| M2 | Absolute white and the `wtpt` tag vs the chart's own four white rows (SAMPLE_LOC J9/AR2/N15/AC7: Y 83.605/83.334/83.407/82.981) | python parse of the XYZ tag; `xicclu -ff -ia` | `wtpt` fast = 80.444/83.604/72.563 = the brightest row to 3 decimals; accurate = 80.223/83.331/72.443 = the mean of the four to 3 decimals; **colprof = 79.546/82.611/72.005 — 0.37 Y below the darkest measured white**. Absolute L of device white: fast 93.05, accurate 93.10, colprof 92.84 |
| M3 | `gamt` content, engine vs colprof | python parse of the gamt CLUT (value/65535·128 = ΔE) | engine accurate (grid 17): 378 zeros, **26 nodes at 0<ΔE≤1, 49 at 1<ΔE≤3**; fast: 375 / 26 / 34; colprof (grid 9): 15 zeros, **0 nodes below 3 ΔE** — colprof's gamt is 0 or far, the engine's carries a ring of small non-zero values |
| M4 | In-process (warm oracle cache) vs fresh-process accurate build | tag-by-tag byte compare of the two `builds/*.icc` | A2B0/1/2, B2A0/1/2, gamt, wtpt, bkpt, arts, targ identical; only `desc` (different stem) and the date differ |
| M5 | Determinism | `det.py`: 219-patch synthetic RGB, `-q l`, no gamut source, `timestamp` fixed, two fresh processes per mode | **byte-identical** in fast and in accurate (36 044 bytes). The oracle path was not measured |
| M6 | `-u 0.9` through `builder.py:290-294` + `average_endpoints` on a chart with 4 duplicate whites | `probe_a.py` A | raw white Y 91.27; after the builder's one-row scale AND `_invalidate_bases` the recomputed `white_index` picks another (unscaled) duplicate → **fast/argyll media white Y 91.25 (scale ignored)**; accurate after averaging Y 89.32 → **effective scale 0.979, not 0.9** |
| M7 | NaN in one XYZ row | `probe_a.py` B | `read_ti3` accepts it; `build_profile` raises `ValueError: cannot convert float NaN to integer` after four numpy RuntimeWarnings — no profile written, message meaningless to a user |
| M8 | UI observer choices vs the engine | `probe_a.py` C | `engine_support(observer="2015_2")` → `(True, '')`; the build then raises `SpectralError: Unknown observer '2015_2' (the engine knows 1931_2 and 1964_10)` |
| M9 | FWA on the real spectral charts (both ColorMunki) | `probe_a.py` D; `colprof -ql -f ref924` | engine: "The measuring instrument (X-Rite ColorMunki) doesn't illuminate with UV…"; colprof: "Error - Instrument doesn't have an FWA illuminent" (and it truncates `ref924.icc` to 0 bytes) |
| M10 | What the four "real" charts contain | awk over the DATA blocks | 924p: ColorMunki (not i1Studio), 4 whites, 4 blacks. 1168p: ColorMunki, 9 whites, 8 blacks. **315p scanner chart: white rows Y 26.7 and 23.5, black rows Y 25.4/24.5, grey ramp non-monotone — not a measurement of colours.** **18p CR30 chart: every patch reads XYZ ≈ 48.4/37.4/5.8 (stuck instrument), no white patch.** |

## 2. Verdicts on S01–S24, A-Q1, A-Q3

Grades: **W** = worthless as specified (already proven by a named test, or not user-visible); **V** = valid; **V*** = valid but mis-specified — the test must measure something else. Confirmed/refuted cheaply where possible.

**S01 — V, CONFIRMED by code.** `workflow/engine_builder.py:80-81` folds `-l` and `-L` into `s.ink_limit`; colprof's usage (run today) says `-L klimit = override black ink limit, 0–100%`. No `BuildSettings` field for a black limit (`builder.py:98-141`), and the engine never reads `BLACK_INK_LIMIT` from the `.ti3` either (colprof does: `colprof.c:1160-1172`). User-visible only through Manual's extra-options box (no widget produces `-L`; `ProfileParams` has no black-limit field, `profile_builder.py:110-174`). Grade BUG, low frequency. Plan's repro is right.

**S02 — V*.** `gamut_map.py:67-79` sniffs the stem; `tests/test_profile_engine_mapping.py:28-34` **pins** that behaviour (`"AdobeRGB1998.icc"` → `"adobe"`), so a test guards the bug. But in the mode under test (accurate, ≤4 inks) the perceptual/saturation node targets come from the **colprof oracle reading the real file** (`gamut_map.py:504-566`, `_ExactNodeMapper` at 644-660); the sniff only feeds the WarpMapper's training interior (`_source_interior_lab`, 662-668) and the two paths that never see the oracle: `render_style="bijective"` (883) and CMY+N (887). The plan's repro on an RGB chart in accurate mode measures nothing. Run it on S5 (CMYKOG) or with the bijective renderer.

**S03 — V*, premise wrong.** colprof's `-s`/`-S` take an ICC; the image gamut is `-g src.gam` (usage text; colprof.html: "-g flag … source image gamut … created using tiffgamut"). `-g` and `-p` are unknown to `_apply_extra_args` → `ExtraArgsError` (`engine_builder.py:158`). ≤4 inks: `engine_support` routes to colprof with a log line (`tab_profile.py:608-613`) — fine. **Multi-ink:** `_resolve_engine` returns `"engine"` before consulting `engine_support` (`tab_profile.py:585-590`), `EngineProfileBuilder.build` catches the error and emits `"[ERROR] -g"` then `on_finish(1)` (`engine_builder.py:315-319`) → the failure dialog's whole text is `-g`. That is the test. A `.gam` in the source picker passes `_validate_gamut_source` (only `is_file`, `tab_profile.py:4199-4203`).

**S04 — V, CONFIRMED from the plan's own logs.** `builds/baseline-accurate-924p.log`: fast = 101.4 s; fresh accurate = 53.2 s. The fast log shows why: the Python port does the perceptual mapping (40–74 %) and then **the colprof oracle is still run for the saturation table** ("Saturation table: matching colprof's rendering (this runs Argyll colprof once…)") — `gamut_map.py:857-873` (port) then 874-885 (oracle fills whatever the port did not return). So "Fast" = port + colprof, "Maximum accuracy" on ≤4 inks = oracle only. The Accuracy tooltip (`settings_dialog.py:641-646`, 665-667) is wrong both ways. Measure fresh processes, q=m and q=h, **with and without a gamut source** (without one there is no mapping at all).

**S05 — V*.** Key at `gamut_map.py:478-501`: path, mtime_ns, size, source path string, quality, `-t/-T/-c/-d`, `-nP/-nS`, `-i/-o/-f`, k-rule, node signature. It omits `ink_limit`, `smoothing`, `algorithm`, `b2a_quality`, `wp_scale`, `clip_primaries`, `argyll_bin` — **but the oracle colprof run omits the same flags** (`gamut_map.py:540-566` passes only `-q`, `-s/-S`, `-t/-T/-c/-d`, `-nP/-nS`, `-i/-o/-f`, `-k`), so the cache is consistent with what it caches. The real defect is upstream and is listed as **N04** below. A source-gamut file edited in place at the same path is not in the key (string only) → stale hit. Thread safety: one `_EngineThread` at a time (`tab_profile.py:5060`), so no race. M4 shows a warm hit reproduces the fresh tables byte-for-byte.

**S06 — V, but under-specified.** `accuracy.py:100-113`: five factors, no boundary flag, no extension. What matters more: the CV criterion is A2B held-out ΔE2000 only (`accuracy.py:117-125`), while `builder.py:51-56` records that fitting tighter than the noise "sharpens the inverse and blows up B2A round-trip errors (max 11.8 → 2.3)". The baseline chose ×0.25 — the stiffest end. So the test is not "add a log note": measure B2A round-trip (as `tests/test_profile_engine_parity.py:57-70` does) and neutral-ramp smoothness accurate vs fast vs colprof on the 924p chart. See **N14**.

**S07 — V.** `builder.py:341-347` prints 1-based data-row numbers; `read_ti3` discards `SAMPLE_ID`/`SAMPLE_LOC` (`ti3_data.py:236-247` keeps only device/XYZ/SPEC columns). Both real charts carry `SAMPLE_LOC`. `BuildResult.outlier_rows` is 0-based (`builder.py:212`) — the plan's fresh-process harness already printed `756, 810` for the log's `757, 811`. GAP. Cheap add-on: print the two patches' device values and residuals.

**S08 — V and MEASURED (M1/M2) — this is a BUG in both modes, not an accurate-mode question.** The engine's relative-colorimetric B2A1 sends L*=100 to RGB ≈ 0.995–0.997 (253.7–254.3 of 255) and its A2B1 returns L* 99.76 (fast) / 99.94 (accurate) for device white; colprof pins both to white (`ICX_SET_WHITE|ICX_SET_BLACK`, `profout.c:2135`; `xicc.h:301`). In a real CMM that is ink laid down in paper-white image areas under relative colorimetric — the classic printmaker complaint. The perceptual table inherits it (0.9949). Separately, three profiles carry three different `wtpt` values for one paper (M2): fast = brightest duplicate (the max-selection bias `ti3_data.py:97-106` describes), accurate = mean (defensible), colprof = below every measured white. Agent A should judge against the measured rows, not against colprof.

**S09 — half W, half V.** The NaN/division fear is refuted by code: `gp.py:44-56` needs ≥ 3 exact repeats for a group, `estimate_xyz_noise` returns the defaults with none (60-84) and floors σ at 1e-4 (69). The silent CV skip below 120 patches (`accuracy.py:99`) is real. **The 18p and 315p files are not measurements** (M10) — run them once as robustness cases ("does a stuck-instrument chart build a profile without a word?"), not as small-chart accuracy cases; make a real small chart by subsampling the 924p.

**S10 — V.** Lab-only path `ti3_data.py:262-265`; 106 bands accepted when `SPECTRAL_BANDS == len(SPEC_*)` (268-278) with a `linspace` axis. Parity method is right. Note the 924p header says `X-Rite ColorMunki`, not i1Studio.

**S11 — V*, cannot be run on this data.** Both spectral charts are ColorMunki: the engine refuses (`fwa.py:53-66`, M9) and colprof refuses (M9). Only refusal parity is measurable here; a synthetic with `TARGET_INSTRUMENT "i1 Pro"` is needed for the numbers. Watch one trap: `txt2ti3` stamps every imported file `Spectrolino` (memory `ref_argyll_source.md`), so an i1Profiler-imported M2 measurement passes the UV gate in both tools.

**S12 — V, spec quotes obtained (ICC.1:2022 text, extracted from color.org's PDF).** 8.2: `chromaticAdaptationTag` is required only "when the measurement data … was specified for an adopted white with a chromaticity different from that of the PCS adopted white"; 9.2.36: `wtpt` "shall be adapted … using the chromaticAdaptationTag matrix" in that case; 7.2.18: profile ID zeroes bytes 44–47, 64–67, 84–99 — `icc_writer.py:339-345` does exactly that; `mediaBlackPointTag` has **0 hits** in the v4.4 text — the engine writes `bkpt` into v4 (`icc_writer.py:246`), harmless but not a v4 tag; 10.15 mluc record size 12 — `make_mluc` matches. The one concrete v4 test the plan lacks: **v4 + `-i D65`** — the engine writes the raw D65-relative media white as `wtpt` (`builder.py:485`, `ti3_data.py:102`) and only Argyll's private `arts` (`icc_writer.py:262`), never `chad`.

**S13 — V, CONFIRMED.** Only `builder.py:513-517` and the tooltip know the twin (grep of `ui/ core/ workflow/`); `_archive_superseded_profile` archives `run.built_profile_icc()` only (`tab_profile.py:5043`, `file_manager.py:1717-1723`). Add: the twin gets the **same `desc`** (`replace(spec, version=(4,4))`) → two profiles with one name in Photoshop/ColorSync lists.

**S14 — V.** `_confirm_rebuild_over_verifications` runs before `_resolve_engine` (`tab_profile.py:5069-5080`), so both paths archive. Add the failure case: after archiving, an engine failure leaves the run with no profile (the scanner tool restores its stash on failure, `scanin_dialog.py:5354-5358`; `_on_engine_done` does not).

**S15 — V, sharpened.** No stop in `_EngineThread` (`engine_builder.py:256-283`); `closeEvent` never consults `_engine_builder.is_running` (`main_window.py:2936-2994`), `_runner.cleanup()` kills QProcess tools only; the oracle colprof is a `subprocess.run` child **without a timeout** (`gamut_map.py:567`, CLAUDE.md rule), so quit → `_hard_exit` → orphan `colprof` + leaked `TemporaryDirectory`. `write_profile` is a single in-place `write_bytes` at the end (`icc_writer.py:363-367`): a half file needs a kill inside that call.

**S16 — V.** Store is `workflow/per_target_settings.store_for_target` (`tab_profile.py:2167, 2205`); whether its vocabulary has the four keys must be read, then driven on screen.

**S17 — V, add five items:** (a) **`-s` vs `-S`**: colprof.html — "If only a perceptual intent is needed, then the -s flag can be used, and the saturation intent will use the same table as the perceptual intent"; the engine collapses both into one `source_gamut` (`engine_builder.py:220`) and `build_mapped_b2a` always builds a mapped `B2A2` (`gamut_map.py:875-913`), the oracle passing `-S` unless both `-nP` and `-nS` (548-552). (b) `-u scale` (M6). (c) observer 2015_2/2015_10/shaw (M8). (d) the bijective log line (N11). (e) `-a x` in accurate mode uses `XyzPcsShaped` (`pcs.py:113`) — the B2A input tables are cube-root curves: verify littleCMS/ColorSync honour `mft2` input curves on an XYZ-PCS profile (they should; measure).

**S18 — V, failure mode named.** `b2a.py:301-318`: an extra ink participates only inside its hue gate **and only when chroma > 15** (`sat = clip((chroma−15)/60)`), so light cyan/magenta are pulled to zero on neutrals and highlights — exactly where a printer uses them. `extra_ink_hues` (`ti3_data.py:135-160`) reads the 'c' solid as a cyan hue and feeds the same gate. The battery has no light-ink printer (`benchmarks/synthetic.py:172-179`), so a CMYKcm synthetic must be added; the measurement is the B2A neutral ramp's c/m columns.

**S19 — V.** `builder.py:305-307`: 6 inks → grid 11 at **both** `-q h` (17→11) and `-q u` (23→11); 7 inks → 7. The log names the grid (309-310) but not the reduction. The real question is time: the CV ladder is 8 forward fits of an 11⁶-node grid.

**S20 — V, record only.** Translating the lines needs `_STAGE_PCT` (`builder.py:226-253`) to match translated prefixes.

**S21 — V, CONFIRMED by code.** Guided's `ProfileParams` (`tab_profile.py:5536-5553`) has no engine fields → dataclass defaults (`profile_builder.py:170-174`).

**S22 — W as specified.** The file is junk (M10) and has 2 whites/2 blacks, below the ≥3 repeats `duplicate_groups` needs (`gp.py:44-56`) → defaults → "Measurement noise is low … keeping the standard fit". The plan's prediction ("the detector will engage") cannot happen on this file. A real scanner-measured chart is needed.

**S23 — V** (Q2 candidate, battery-measurable).

**S24 — V** (S04/S07/S09).

**A-Q1 — confirmed** (S21). **A-Q3 — confirmed** (`scanin_dialog.py:652`, `5346-5377`); add: the tool sanitises nan/inf for colprof (`_sanitize_scanner_ti3`, 5380-5395) — the engine has no equivalent (M7), so routing the tool to the engine must keep the sanitiser in front.

Addendum to S16: `workflow/per_target_settings.py` (259 lines) contains no occurrence of `spectral_physics`, `icc_version`, `noise_model`, `render_style`, `iccver`, or the `manual2_colprof_*` keys the rows persist under (`tab_profile.py:2341-2347`). Expected on-screen outcome: the four rows are **not** per-target. The illuminant list (`tab_profile.py:104-114`) matches the engine's `_ILLUMS` + M2 variants exactly (`spectral.py:38-42, 58-64`); only the observer list is out of step (M8).

## 3. What the plan missed — NEW suspects, each with a repro

Graded by what a printmaker would see. "Measured" = done by the critic today.

**N01 — Ink in the paper white (relative AND perceptual), both modes. BUG, measured (M1).** Repro: `xicclu -fb -ir -pl <engine.icc>` ← `100 0 0` → RGB 0.995–0.997; colprof → 0.99996. Fix direction: pin the fitted white the way Argyll does (`profout.c:2135` `ICX_SET_WHITE|ICX_SET_BLACK`): scale the model so A2B1(device white) = (100,0,0) exactly and force the B2A1/B2A0/B2A2 node at the white corner to device white; check the black end the same way (A2B1(black) engine 2.86 vs colprof 2.85 — fine).

**N02 — `-u scale` diluted / ignored. BUG, measured (M6).** `builder.py:290-294` scales one row then `_invalidate_bases` recomputes `white_index`, which selects another duplicate; accurate then averages the scaled row with k−1 unscaled ones. colprof honours the scale for output profiles (`profout.c:823` "media white point scale factor", used at 2155/3218; colprof.html: "use a scale factor slightly less than 1.0 … try 1.1"). Repro on the 924p chart (4 whites): `-u 0.9`, read `wtpt`; expect Y ×0.9, get ×1.0 (fast) / ×0.975 (accurate).

**N03 — Observer 2015_2 / 2015_10 offered, engine refuses at build time. BUG, measured (M8).** UI list `tab_profile.py:2628-2636` (Guided at 3670) and `data/parameters.yaml:1507` (adds `shaw`); engine `spectral.py:33-37`; `engine_support` returns True (`engine_builder.py:230-250` never validates it). The user sees "[ERROR] Unknown observer '2015_2'" and a failure dialog instead of the colprof fallback the beta tooltip promises ("quietly handed to colprof and the log tells you why", `settings_dialog.py:616-619`). Repro: Manual, accurate, observer 2015 2°, Build.

**N04 — The colprof oracle is built with the .ti3's ink limit and colprof's defaults, not the user's `-l`, `-r`, `-u`, `-R`, `-a`, `-b`.** `gamut_map.py:540-566`. For CMYK ≤4 inks in accurate/argyll mode the perceptual/saturation node targets are colprof's realised mapping into a gamut limited by `TOTAL_INK_LIMIT − 10` (colprof's own rule, `colprof.c:1153-1156`), then inverted through the engine's model limited by `-l`. Repro: S3 (CMYK, tac 280) accurate, `-l 200` vs none; compare B2A0 node targets and the OOG fraction; expect the mapped targets to sit outside the 200 % gamut and get clipped a second time. (Also removes S05's "stale cache" worry for these fields — they never reach the oracle.)

**N05 — `-s` (perceptual only) maps the saturation table too.** See S17(a). Repro: build with `-s ClayRGB.icm` through the engine and through colprof; colprof's B2A2 aliases B2A0; the engine's B2A2 is colprof's `-S` saturation. On screen: Guided "Perceptual only" vs "Perceptual + Saturation" should differ in the file; in the engine they may not.

**N06 — `gamt` flags in-gamut nodes as out of gamut. Measured (M3).** ICC.1:2022 9.2.29: "If the output value is 0, the PCS colour is in-gamut. If the output is non-zero, the PCS colour is out-of-gamut." Engine: 75 nodes with 0 < ΔE ≤ 3 (the GN residual of near-boundary nodes, `b2a.py:456-459` + `builder.py:415-417` scale /128); colprof: none. Repro: `xicclu -fg -pl` on a ring of just-inside-gamut Lab values, engine vs colprof; and ColorSync gamut check via `sips`/ImageCms proofing on a 1 000-swatch image.

**N07 — Three whites for one paper (M2).** Which `wtpt` is right is a colour-science ruling, not a parity question: the measured rows are the referee (mean 83.33; brightest 83.60; colprof 82.61). Repro is M2. Adds to S12: v4 + `-i D65` must adapt `wtpt` and write `chad`.

**N08 — Refinement merge + accurate.** `merged.ti3` (`tab_profile.py:4561-4591`) stacks two prints' rows; `average_endpoints` (`ti3_data.py:85-106`) and `duplicate_groups` (`gp.py:44`) then treat print-to-print differences as instrument repeats: the noise detector's ratio (`accuracy.py:295-297`) sees paper/print drift and may engage; the outlier line names merged-row numbers (S07). Repro on screen: a refinement run in accurate mode with noise handling on; compare the "scatter ×" line with the fresh chart alone.

**N09 — Calibrated chart (CAL table in the .ti3).** colprof reads it (`profout.c:1183-1215`) and uses `FINAL_TOTAL_INK_LIMIT` (`colprof.c:1140`); the engine reads only `TOTAL_INK_LIMIT` (`ti3_data.py:59-66`) and embeds the whole file text (CAL included) as `targ`. RGB calibration runs carry no ink limit → harmless there; CMYK calibrated charts get the wrong limit. Low.

**N10 — Multi-ink + unknown extra flag → dialog text is the bare flag** (`engine_builder.py:315-319`: `"[ERROR] {msg}"` with `msg = "-g"`). Low.

**N11 — Bijective renderer logs "rendering intents matched to ArgyllCMS colprof".** `gamut_map.py:864-873`: with `render2` true and ≤4 inks the `elif _bitexact_le4` branch still prints the Argyll line after the bijective line. Cosmetic; one build with the bijective option shows both lines.

**N12 — The v4 twin has the same `desc` as the v2 file** (`builder.py:513-517`, `replace(spec, version=(4,4))`). Two entries with one name in Photoshop's profile menu; install one and you cannot tell which. Medium.

**N13 — NaN/inf and a stuck instrument.** M7: `ValueError: cannot convert float NaN to integer`. The scanner tool sanitises before colprof (`scanin_dialog.py:5380-5395`); the engine has no gate. The 18p CR30 chart (every patch ≈ 48.4/37.4/5.8) is the second repro: does the engine write a "profile" from a flat measurement, and what does the fit line say? Run it through fast and accurate.

**N14 — The CV picks the stiffest fit and nobody measures what that costs the B2A.** See S06. Repro: 924p chart, fast vs accurate vs colprof: (a) `xicclu` round trip on 600 random device values (median/p95/max, as `test_profile_engine_parity.py:57-70`), (b) neutral ramp L 0→100 through B2A1 → RGB, first and second differences (banding), (c) the same on a 3-D slice at a*=b*=±20. If accurate loses (b) while winning A2B, the mode is mis-tuned for printing.

**N15 — Determinism.** Measured byte-identical with a fixed timestamp on the no-source path (M5). The UI never sets `timestamp` (`engine_builder.py:288-303`), so two identical builds differ in bytes 24–35 and, in v4, the profile ID — expected and fine. The oracle path (colprof subprocess) is unmeasured: repeat M5 with `-S ClayRGB.icm`.

**N16 — Quit mid-build leaves an orphan colprof and a temp dir** (S15 sharpened): `pgrep colprof` after quitting during "Saturation table: matching colprof's rendering"; `ls $TMPDIR` for `tmp*/oracle.ti3`.

**N17 — The plan's data table is wrong (M10).** Two of the four charts are not measurements; the 924p is ColorMunki. Every conclusion planned on the 18p and 315p files must be re-scoped to robustness.

**N18 — No real-CMM leg at all.** Everything in the plan is judged through Argyll's `xicclu`. Add: littleCMS via `PIL.ImageCms` (already a dependency, `gamut_map.py:97`) — build transforms sRGB→profile for intents 0/1/3 and profile→Lab, on a 32³ swatch image, and compare with `xicclu` per intent; ColorSync via `sips --matchTo <icc>` on the same TIFF. This is where N01, N06, N12, the v4 `mluc`, the cube-root `mft2` input curves of `-a x` (S17e) and absolute-colorimetric (`wtpt` scaling) actually reach the user.

**N19 — Relative colorimetric in accurate mode is hue-preserving clipping, not nearest-colour clipping** (`b2a.py:486-506`, `_CLIP_HUE_FACTOR = 3`). Documented in the tooltip ("lose saturation instead of drifting"), so design, not a bug — but a proofing workflow expects minimum-ΔE clipping and Agent A should quantify the ΔE2000 between the two clips on the 924p chart's OOG shell so the tooltip's promise has a number.

**N20 — The oracle/proxy subprocess calls have no `timeout=`** (`gamut_map.py:567, 573, 577, 745`; CLAUDE.md: "Anything that shells out to Argyll … needs a `timeout=`"). A wedged colprof = a build that never ends and cannot be cancelled (S15).

**N21 — K-prior column is hard-wired to index 3** (`b2a.py:349-377`). ChromIQ's own reps (`grep`: CMY, CMYK, CMYKOG, CMYKOGV, CMYKPLUSN) all put K there; a foreign 5-ink rep without K (e.g. `CMYRGB`-style) would receive a black-generation prior on its fourth colour ink. Low; note only.

## 4. The A/B split

Right in principle; four moves:

* **S08 → BUG for the orchestrator now**, not a research item: M1 already proves it, and it needs a fix + test before anything else is judged (every B2A measurement downstream inherits it).
* **S04 stays with B for the felt time, but A must supply the fresh-process numbers** (M1's colprof reference took 2.2 s at `-q l`; the plan's 101 s fast build is the port + oracle). The tooltip text is B's to check on screen.
* **S07, S09 (the small-chart half) and S22 belong to A** — they are numbers (row vs SAMPLE_LOC mapping, held-out on subsampled real charts); B only checks that the log line is readable and that the "remeasure them" advice can be followed on the sheet.
* **S13, S14, S15, S16, S21, A-Q1, A-Q3 must be on screen** — `isVisible()`/`isHidden()` of `_m_engine_rows_widget` offscreen means nothing (the tests already assert `isHidden`, `test_engine_v2_options.py:164-181`, which is exactly what the plan wants to go beyond); archive-then-build, the twin in the File guide and Install, the disabled Build button and tab lock during a build, the quit path (N16), per-target switching, the consent dialog, the failure dialog text of N03/N10 — all painting/geometry/modal behaviour.
* **N18 (real CMM) is A's**; N08 (refinement merge) is a B journey with A reading the numbers.

Items that are worthless offscreen and must NOT be reported from a `QT_QPA_PLATFORM=offscreen` run: any `isVisible()`, the engine rows' geometry inside the Manual group (they are `QVBoxLayout` children, `tab_profile.py:2795-2798`), the progress bar label "ChromIQ engine" (5104-5106), the busy headline HTML (5091-5097), the failure dialog, the consent QMessageBox (`settings_dialog.py:1536`).

## 5. Q2 — "more options": real practice vs invented (trusted sources)

Sources: colprof.html (fetched today, quoted), ICC.1:2022 text (extracted from color.org's PDF), basICColor print manual (PDF extracted: §3.1.1 Gamut Mapping – perceptual, §3.1.2 Correction of Optical Brighteners, §3.1.3 Measurement Correction, §3.1.4 Dot Limits (CMYK only), §3.1.5 Spectral Profiling, §3.2.1 Total Ink Limit, §3.2.2–3.2.6 Black Definition/Black Start/Black Width/GCR-UCR — https://www.basiccolor.de/assets/Manuals/Manual-print5.pdf), i1Profiler as publicly described by users (Total Ink, Black Start, Max Black, Black Curve, Black Width, Contrast, Saturation, Smoothness, Granularity, Intelligent Black — https://www.signs101.com/threads/how-to-get-a-better-profile-epson-s80600-onyx-thrive-19-and-xrite-i1-profiler.166088/ ; X-Rite's own page on PM5→i1Profiler GCR settings returned 404 today).

| candidate | real practice? | colprof today | engine today (engine_builder.py / builder.py) |
|---|---|---|---|
| Black ink limit | **Real** — colprof `-L klimit`; basICColor "Black Definition"; i1Profiler "Max Black" | `-L`, plus `BLACK_INK_LIMIT` from the .ti3 (`colprof.c:1160`) | **mapped wrongly to the total limit** (S01); no field |
| Black start / width / shape (GCR) | **Real** — colprof `-k p stle stpo enpo enle shape`; basICColor §3.2.4/3.2.5/3.2.6; i1Profiler Black Start/Width/Curve | `-k/-K` | mapped (`engine_builder.py:102-116`, `b2a.py:265-299` port of `icxKcurveNF`) |
| Total ink limit | **Real** everywhere | `-l`, .ti3 default −10 % rule | mapped from the .ti3 exactly; user `-l` via extra args only (no widget in either path, `profile_builder.py:486-489`) |
| Per-channel ink / dot limits | **Real** (basICColor §3.1.4 "Dot Limits (CMYK only) for highlights and shadows") | **not in colprof** | not in engine — a genuine addition candidate for ink devices only |
| Duplicate-patch averaging (S23) | **Real** (basICColor §3.1.3 "Measurement Correction"; i1Profiler averages repeated patches by default) | fits through all rows | endpoints only (`ti3_data.py:85-106`) |
| Custom illuminant spectrum file | **Real** — colprof `-i file.sp` ("Argyll specific .sp custom spectrum file") | yes | **no** (`spectral.py:38-64`) and no UI |
| Observer 2015_2 / 2015_10 | **Real** — colprof `-o 2015_2, 2015_10, 1955_2, 1978_2, shaw, file.cmf` | yes | **no** — and the UI offers it (N03) |
| Image-specific `.gam` source gamut | **Real** — colprof `-g src.gam` from tiffgamut | yes | no (S03) |
| Abstract profile in the output tables | **Real** — colprof `-p absprof` | yes | no |
| Gamut-mapping intent per table | **Real** — colprof `-t`/`-T` | yes | mapped; bijective renderer only when both unset |
| Perceptual compression amount / chroma vs lightness trade | **Real** — colprof `-s cperc` / `-S experc` (percentage forms); basICColor §3.1.1 "Compression … Standard method" + lightness/saturation sliders; i1Profiler Contrast/Saturation | percentage forms exist | the engine's parser sends `-s 20` into `source_gamut` as a path (`engine_builder.py:150-151`) → `engine_support` fails "not found" → colprof (≤4) / error (CMY+N) — test it |
| Optical brightener correction | **Real** — colprof `-f`; basICColor §3.1.2 | yes (UV instruments only) | mapped, same gate (S11) |
| Smoothing per region / "Smoothness" slider | i1Profiler "Smoothness", colprof `-r avgdev` global only | global | global (`-r` scales λ, `builder.py:314`) — a regional version is invented by the plan, no vendor documents it |
| Dark-region grid emphasis | **Real** — colprof `-V demphasis` (doc: "1.3–1.6 are a good place to start") — **but colprof itself passes 1.0 for output profiles** (`colprof.c:1258` literal `1.0`; `builder.py:15-17`) | no-op for printers | no-op — the plan's S17 "-V no-op" is correct |
| ICC v4 with `chad` / D50-adapted `wtpt` | **Required by the spec** when `-i` ≠ D50 (8.2, 9.2.36) | colprof writes v2 only; doc warns `-i` ≠ D50 "will not be standard" | v4 header + mluc + ID (S12), no `chad` |
| "Noise handling", "spectral physics", "bijective" | ChromIQ inventions — no vendor equivalent; judged only by the battery | — | shipped behind the Manual rows |

So: the black ink limit, `.sp` illuminant, the 2015 observers, `-g`, `-p`, the `-s`/`-S` percentage forms and per-channel dot limits are real and unmapped; "smoothing per region" is not documented by any vendor; duplicate averaging is real and worth the battery run.

## 6. Damage risks in the plan as written

1. **Any on-screen run without `CHROMIQ_SETTINGS_FILE` writes the real preferences** (CLAUDE.md "Driving the app on screen"; the beta switch, `gammap_mode`, Save-as-defaults `manual2_colprof_*` keys at `tab_profile.py:2341-2347`, `custom_output_path`). The plan says each agent gets its own file — make it a hard precondition in the brief and print `defaults read com.chromiq.ChromIQ custom_output_path` after each run.
2. **The real `~/ChromIQ` must only be copied.** `_archive_superseded_profile` moves files inside the run (`run.archive_to_old`), the engine writes `<ti3>.icc` and `-v4.icc` beside the measurement (`engine_builder.py:238-240`, `builder.py:514`), `merged.ti3` lands in the run folder (`tab_profile.py:4580`). Point `custom_output_path` at a sandbox copy before opening any project.
3. **`colprof -f` truncates the output `.icc` to 0 bytes when it refuses** (M9, observed on my scratch copy). An agent running the FWA refusal repro **in the user's run folder** deletes the profile that was there. Run it on copies only.
4. **The oracle cache is process-global** (`gamut_map.py:474`): an agent that edits a source profile in place between builds and expects a change will report a phantom "no effect". Restart the app between S05 mutations.
5. **The tree has 26 uncommitted files**; `tests/test_i18n.py` and friends assert on `inspect.getsource` — an agent editing `builder.py` log text while the other runs the gate produces phantom reds (CLAUDE.md). Sequence fixes after both agents finish, and commit only challenge files by name.
6. **No agent should run `--runslow` twice in parallel on this host** (12 workers each → 24 processes on 12 performance cores, and the demo-project cache is shared).
7. `benchmarks/README.md`'s rule: **no constant may be tuned against the owner's measurements**; the 924p/1168p charts are smoke tests only. A fix for N01/N14 must be proven on the battery, not by making the 924p numbers look better.

