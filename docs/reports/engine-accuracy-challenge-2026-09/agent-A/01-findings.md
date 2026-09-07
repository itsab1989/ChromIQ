# Agent A — colour-science referee: staged findings

Agent A, 2026-09-04/05. Tree `/Users/Basti/develop/ChromIQ` @ `feature/engine-accuracy-challenge`, **no repo file edited**. All scripts in `~/Desktop/ChromIQ-engine-challenge/work-A/`, all builds in `work-A/builds/`. Every engine build is a fresh process via `work-A/build.py` (fixed timestamp 2026-01-01T00:00Z, `argyll_bin=/Applications/Argyll/bin`, `-S /Applications/Argyll/ref/ClayRGB1998.icm` unless "no source"). Chart = `charts/real-rgb-924p-spectral36.ti3` (924 p, ColorMunki, 4 white + 4 black duplicates) unless stated. Grades: BUG / GAP / INCONSISTENCY / IMPROVEMENT / OK / NOT-MEASURABLE-HERE. "Measured" = a command run today; "read" = code read.

CMM legs used (A1): Argyll `xicclu` 3.5.0; littleCMS 2.19 via Homebrew `transicc` 5.1 (double precision, `-o '*Lab2'` — the **v4** `*Lab` profile makes lcms apply black-point compensation on perceptual: A2B0(black) came back L 0.000 instead of the table's 2.83, identically on colprof's file, so it was switched off); ColorSync via `sips -M <icc> <intent>` (8-bit on every destination it accepts; refuses Lab and XYZ destinations: "Unable to render destination image").

Foundation profiles (`work-A/run_foundation.sh`):

| file | how | wall |
|---|---|---|
| `builds/e924-fast-qm.icc` | `build.py … --mode fast --q m` | 107.2 s |
| `builds/e924-acc-qm.icc` | `build.py … --mode accurate --q m` | 56.1 s |
| `builds/c924-qm.icc` | `colprof -v -qm -S ClayRGB1998.icm -D ref924 ref924` on a scratch copy | 44.2 s |

---

## A-01 — Determinism on the oracle path (A8) — **OK**

**Measured.** Two fresh processes, identical settings (accurate, q=m, `-S ClayRGB1998.icm`, fixed timestamp), output stems identical (`e924-acc-qm`):

```
.venv/bin/python work-A/build.py charts/real-rgb-924p-spectral36.ti3 work-A/builds/e924-acc-qm.icc --mode accurate --q m
.venv/bin/python work-A/build.py charts/real-rgb-924p-spectral36.ti3 work-A/builds/det/e924-acc-qm.icc --mode accurate --q m
.venv/bin/python work-A/tagcmp.py builds/e924-acc-qm.icc builds/det/e924-acc-qm.icc   → byte-identical files: True
md5: 040819bd89a449c90109e32e04341653 both
```

Both logs contain exactly one "Saturation table: matching colprof's rendering" line (cold oracle both times). Critic N15 closed: the colprof-oracle path is byte-reproducible with a fixed timestamp. (The UI never fixes `timestamp`, `engine_builder.py:288-303`, so real builds differ in header bytes 24–35 only — expected.)

---

## A-02 — Real-CMM leg (A1) — engine vs xicclu **OK for perceptual/relative; absolute is CMM-level; the sRGB→printer relative leg exposes A-05**

Tool: `work-A/cmm_probe.py <icc> --n 33 --ring 1000 --json …` (device 33³ grid → Lab; Lab ring at ±2 ΔE76 around the gamut surface → device; sRGB 33³ → device; ColorSync legs). JSON in `builds/cmm-<name>.json`.

**Measured, xicclu vs littleCMS (transicc), ΔE2000 median / p95 / max:**

| profile | intent | A2B 33³ | B2A ring inside (−2) | B2A ring outside (+2) | max Δdevice (8-bit) |
|---|---|---|---|---|---|
| engine fast | p | 0.001/0.002/0.006 | 0.001/0.002/0.005 | 0.001/0.002/0.004 | 0.02 |
| engine fast | r | 0.001/0.002/0.006 | 0.001/0.002/0.005 | 0.001/0.002/0.016 | 0.04 |
| engine fast | a | 0.198/0.788/1.125 | 0.183/0.880/1.727 | 0.199/0.953/2.463 | 14.5 |
| engine accurate | p | 0.001/0.002/0.007 | 0.001/0.002/0.006 | 0.001/0.002/0.005 | 0.01 |
| engine accurate | r | 0.001/0.002/0.007 | 0.001/0.003/0.004 | 0.001/0.002/0.004 | 0.03 |
| engine accurate | a | 0.199/0.804/1.149 | 0.194/0.928/2.071 | 0.222/1.116/**5.312** | 10.0 |
| colprof | p | 0.001/0.003/0.009 | 0.001/0.003/0.006 | 0.001/0.003/0.006 | 0.01 |
| colprof | r | 0.001/0.003/0.009 | 0.001/0.003/0.005 | 0.001/0.003/0.004 | 0.03 |
| colprof | a | 0.199/0.807/1.149 | 0.164/0.778/1.499 | 0.166/0.795/1.561 | 9.3 |

* Perceptual and relative: the two CMMs read the engine's mft2 tables identically (≤ 0.01 ΔE), same as colprof's. The cube-root `mft2` input curves of accurate mode (`pcs.py:XyzPcsShaped`) are not exercised here — this chart builds `-a l` (Lab PCS); an `-a x` accurate build is in the A3 matrix.
* Absolute: 0.20 median / 0.80 p95 between xicclu and lcms **for all three files with identical numbers** (colprof included) → a difference in how the two CMMs realise absolute colorimetry from `wtpt`, not an engine property. Both agree at device white to 0.001 (xicclu 93.0521/−0.2297/−3.3291 vs lcms 93.0526/−0.2288/−3.3306 on colprof's file). Not a finding against the engine.
* The accurate profile's absolute **outside** ring has a 5.3 ΔE tail (colprof 1.56, fast 2.46) — the same OOG behaviour A-05 measures in full.

**Measured, ColorSync (sips, 8-bit):**

| profile | intent | device→Lab via ROMM-8bit, ColorSync vs xicclu (ΔE00 med/p95/max, max Δcode) | sRGB-8bit→device, ColorSync vs lcms (ΔE00 med/p95/max, max Δcode, frac > 1 code) |
|---|---|---|---|
| engine fast | p | 0.31/0.71/4.1, 7 | 0.23/0.46/1.9, 4, 8.3 % |
| engine fast | r | (sips ignores intent here, same numbers) | **2.44/13.5/48.1, 158, 97 %** |
| engine accurate | p | 0.31/0.71/4.0, 8 | 0.23/0.46/1.4, 3, 6.9 % |
| engine accurate | r | (same) | **2.44/10.9/81.0, 218, 99.5 %** |
| colprof | p | 0.39/0.93/5.2, 5 | 0.00/0.36/1.6, 2, 0.25 % |
| colprof | r | (same) | 1.92/4.57/6.6, 119, 99 % |

* The device→Lab ColorSync leg is at the 8-bit ROMM floor for all three (one ROMM code ≈ 0.3–0.5 ΔE); `sips -M` did **not** honour the intent in that direction (colprof's file read L 100.001 for device white under "absolute" where xicclu says 93.05), so that leg cannot judge absolute. Limitation of the tool, recorded.
* sRGB→printer, perceptual: ColorSync and lcms agree to ≤ 4 codes on all three files. Fine.
* sRGB→printer, **relative**: ColorSync differs from lcms's B2A1 lookup by ~2 ΔE median on **every** file including colprof's (BPC explains only ~0.15 of it: lcms `-b` → 1.77 median on colprof, 2.31 on accurate — `work-A` inline probe, output in this session). That part is ColorSync's own relative rendering and not an engine matter. The **excess on the engine files — p95 11–13.5, max 48–81 ΔE, vs colprof's 4.6/6.6 —** is the engine's B2A1 table itself: for far out-of-gamut sRGB colours it returns the complementary hue (A-05). ColorSync evidently does not take the engine's B2A1 verbatim there (it printed a plausible magenta where the table says green), littleCMS does — and so does Photoshop's ACE by all public accounts, which I cannot run here.
* Brief threshold "> 0.5 ΔE p95 between a real CMM and xicclu": perceptual/relative pass on both CMMs; absolute fails **identically for colprof** (CMM-level); the relative sRGB leg fails through ColorSync for colprof too (1.9 median) — so the only engine-attributable failure is A-05.

Repro pointers: `builds/cmm-e924-acc-qm.json`, `builds/cmm-c924-qm.json`; `.venv/bin/python work-A/cmm_probe.py work-A/builds/e924-acc-qm.icc --n 33 --ring 1000`.

---

## A-03 — White pinning (A2, white end) — **BUG (both engine modes), acceptance numbers below**

Tool: `work-A/a2_pinning.py <icc>…` (xicclu + lcms `*Lab2`; JSON `builds/a2-924.json`). **Measured:**

| profile | A2B1(device white) Lab | B2A1(100,0,0) → RGB 8-bit | what that RGB prints (A2B1), ΔE00 to the profile's own white | B2A0(100,0,0) → RGB | wtpt (XYZ·100) |
|---|---|---|---|---|---|
| engine fast | 99.756 / 0.095 / −0.111 | 254.38 / 253.89 / 253.99 | L 99.48 a 0.26 b −0.08, **0.29** | 253.65/253.80/253.85 (0.19) | 80.444 / 83.604 / 72.563 |
| engine accurate | 99.936 / 0.008 / −0.004 | 254.24 / 253.83 / 254.03 | L 99.64 a 0.16 b −0.03, **0.28** | 253.70/253.80/253.86 (0.18) | 80.223 / 83.331 / 72.443 |
| colprof -qm | 99.9995 / −0.0004 / 0.0011 | 254.994 / 254.994 / 254.995 | L 99.998, **0.0008** | 254.995 ×3 (0.0008) | 79.996 / 83.087 / 72.246 |

Through the real CMMs (A-02 tables): lcms sends sRGB white (255,255,255) to **254,254,254** on both engine files (255,255,255 on colprof's); ColorSync sends it to 255,255,255 on all three. So in littleCMS/ACE-class workflows an image's paper-white areas receive ~0.4 % less than full device white through the engine's profile — that is ink in the paper white on an inkjet driven with RGB. Absolute intent clips (255/254/251) on all three — expected, L 100 lies above the paper.

Cause (read): the engine normalises the *measurement* to its media white (`ti3_data.py:xyz_relative`, Bradford from `media_white_xyz`) but never forces the *fitted model* through (100,0,0) at device white; the smoothed fit lands 0.06 L* (accurate) / 0.24 L* (fast) short, and the B2A1 inversion of (100,0,0) therefore lands off the white corner. colprof fits, then evaluates the fitted surface at device white and re-normalises the whole output to it: `profout.c:2135` `flags |= ICX_SET_WHITE | ICX_SET_BLACK`, honoured in `xicc/xlut.c:3333-3345` (`XFIT_OUT_WP_REL`) and `xicc/xfit.c:1855-1873` / `2681-2746` (white point found on the fitted surface, output made relative to it), tag written at `xlut.c:3686-3700`.

**Acceptance spec for the fix (numbers the fix must reproduce, xicclu):**
* `xicclu -ff -ir -pl` ← `1 1 1` → L 100.00 ± 0.01, |a|,|b| ≤ 0.01 (colprof: 99.9995/−0.0004/0.0011).
* `xicclu -fb -ir -pl` ← `100 0 0` → each channel ≥ 0.99995 (65532/65535; colprof 0.99998).
* `xicclu -fb -ip -pl` ← `100 0 0` → same bound (colprof 0.99998).
* littleCMS sRGB(255,255,255) → device (255,255,255) at intents 0 and 1 (`transicc -n -t1 -i "sRGB Profile.icc" -o <icc>` ← `255 255 255`).

---

## A-04 — Black pinning (A2, black end) — **BUG (relative intent), worse in fast than accurate**

**Measured** (same tool):

| profile | A2B1(device black) Lab | B2A1(0,0,0) → RGB 8-bit | prints (A2B1) | ΔE00 to the profile's own black |
|---|---|---|---|---|
| engine fast | 2.824 / 0.583 / 0.533 | **3.18 / 3.91 / 17.75** | L 6.24 a 0.19 b −0.90 | **2.54** |
| engine accurate | 2.862 / 0.576 / 0.513 | **3.05 / 0.00 / 3.82** | L 3.30 a 1.20 b 0.02 | **1.04** |
| colprof | 2.831 / 0.517 / 0.515 | 0.00 / 0.16 / 0.17 | L 2.88 a 0.46 b 0.52 | 0.09 |

Perceptual B2A0(0,0,0) is fine on all three (≤ 0.05 ΔE00 from device black — the perceptual table comes from the colprof oracle). B2A2 likewise. The defect is in the engine's **own** colorimetric inversion: L*=0 — the value every "pure black" pixel carries — prints as L 6.2 with a blue cast (fast: B = 17.75/255) or L 3.3 with a magenta cast (accurate) instead of the printer's deepest black. The neutral ramp below L 6 (A-07) shows the same: fast's B channel runs 17.8 → 8.4 while R,G sit at 3–4.

Cause (read, not yet bisected): `b2a.py:refine_b2a_clut` anchors nodes with residual > `deep_oog=5.0` firmly and everything else at weight 0.05; the black corner of the Lab16 grid is only ~2.96 ΔE76 outside the gamut, so its node is a *weak* anchor and the smooth-field refit extrapolates it; accurate's hue-weighted re-clip (`_hue_weight_matrices`, `_CLIP_HUE_FACTOR = 3`) then trades L* for a*/b* on a target that has no hue. colprof pins black via `ICX_SET_BLACK` (`profout.c:2135`). The three profiles all fail to return device black for their **own** A2B1(black) Lab (fast 5.2/4.0/13.5, acc 5.6/2.6/6.2, colprof 5.2/4.1/6.9) — so that is not the test; L*=0 is.

**Acceptance spec:** `xicclu -fb -ir -pl` ← `0 0 0` → every channel ≤ 0.002 (colprof ≤ 0.0017); A2B1 of that device value within 0.1 ΔE00 of A2B1(0,0,0).

---

## A-05 — Far out-of-gamut relative clip returns the complementary hue — **BUG (both engine modes, worst in accurate)**

Found through the ColorSync/lcms sRGB leg (A-02). **Measured** with `xicclu -fb -ir` then `-ff -ir` on the same profile (`work-A` inline probe; targets are sRGB primaries/secondaries converted to Lab by lcms):

| sRGB | target Lab (hue) | engine accurate B2A1 → RGB 8-bit, printed hue | engine fast | colprof |
|---|---|---|---|---|
| 255,64,239 | 62.6/82.9/−47.7 (330°) | **71,186,66 → 133° (err 163°)** | see survey | correct hue |
| 0,239,16 | 82.9/−75.3/75.8 (135°) | **250,50,204 → 338° (err −156°)** | | correct |
| 48,16,191 | 24.3/52.7/−84.1 (302°) | 73,0,171 → 302° (ok) | | |
| 255,0,0 / 0,0,255 / 255,255,0 / 0,255,255 | | ok (≤ 2°) | | |

Perceptual B2A0 of the same targets on the accurate profile: hue errors ≤ 15°, all plausible (216,59,193 for the magenta; 100,205,49 for the green).

Survey (`work-A/oog_hue.py`, Lab grid L 5…95 step 5 × a,b −110…110 step 10, chroma > 20, 9 804 targets; gamut distance = colprof's nearest-clip ΔE76): see the addendum below this item once the re-binned run has finished — the first pass (binned by `xicclu -fg`, which saturates at 1.0) already gave, over the 8 894 OOG targets: hue error > 90° for **5.7 % (accurate q=m), 9.1 % (accurate q=l), 1.1 % (fast), 0.0 % (colprof)**; > 30° for 16.6 % / 22.0 % / 18.2 % / **0.4 %**; median printed ΔE00 vs target 14.9 / 15.4 / 19.9 / 13.0.

Why it matters: relative colorimetric is the proofing/printing default in Photoshop and in every RIP; a saturated green or magenta that the printer cannot reach must clip to the nearest printable colour of the same hue family. Here it prints the *opposite* hue. The tooltip's promise for accurate mode ("lose saturation instead of drifting", critic N19) is inverted for these nodes.

Cause (read): far-OOG nodes in `b2a.py:invert_to_device` are seeded from `_seed_nearest` / the 40 000-point cloud in *Lab distance*; for a target far outside, the nearest cloud point in ΔE76 can lie on the opposite side of the gamut only if the seed cloud is sparse there — but the survey shows it is systematic, not random, in accurate mode, so the hue-weighted Gauss–Newton (`_hue_weight_matrices`) is the prime suspect: it minimises a*/b* *direction* error with weight 3 on hue and lets the lightness/chroma residual run, and for targets whose chroma exceeds anything printable the solver walks around the hue circle. Needs the orchestrator's bisect; the numbers above are the acceptance test (no OOG target with > 30° hue error above 1 % of nodes, matching colprof's 0.4 %).

---

## A-06 — Accuracy that reaches the print, A4 (a)–(c): round trip and neutral banding — **INCONSISTENCY (accurate is not better than colprof where it matters; its round-trip tail is 3× worse)**

Tool: `work-A/a4_accuracy.py <icc>… --ti3 <chart>` (JSON `builds/a4-924.json`, text `builds/a4-924.txt`). All q=m, `-S ClayRGB1998.icm`. **Measured:**

(a) xicclu round trip device → A2B1 → B2A1 → A2B1, 600 random device values (`rng(3).uniform`), same as `tests/test_profile_engine_parity.py:57-70`:

| profile | ΔE2000 med / p95 / max | ΔE76 med / p95 / max | max Δdevice 8-bit |
|---|---|---|---|
| engine fast | 0.712 / 2.016 / 6.56 | 1.385 / 4.056 / 16.9 | 39.6 |
| engine accurate | 0.678 / 1.985 / **7.26** | 1.363 / 4.223 / **18.4** | 44.4 |
| colprof -qm | 0.612 / 1.731 / **2.47** | 1.305 / 3.296 / 6.29 | 54.9 |

Worst accurate point: device (148,101,177) → Lab 56.6/29.3/−31.9 → back to (134,112,155), 7.26 ΔE00 — a saturated in-gamut violet, the same colour is fast's worst (6.56); colprof's worst is 2.47. By L band (median/max): accurate 0–10: 1.14/1.71, 10–30: 0.59/2.05, 30–70: 0.68/**7.26**, 70–100: 0.69/3.46; colprof 1.23/1.48, 0.59/2.21, 0.69/2.33, 0.54/2.47. The parity test's band (median ≤ 0.2, p95 ≤ 1.5, max ≤ 4 — ΔE76, ET8550 fixture at `-qh`) is not met by any of the three at `-qm` on this chart; what separates the engine from colprof is the tail.

(b) neutral ramp L 0→100 step 0.5 through B2A1 → RGB, first/second differences in 8-bit units per step, in-gamut part (L 3.5–100), by L band (`work-A` inline probe, printed in this session):

| profile | d2 RMS R/G/B, L 0–10 | 10–30 | 30–70 | 70–100 | d2 max (whole ramp) | monotonicity violations |
|---|---|---|---|---|---|---|
| engine fast | 0.22/0.34/0.48 | 0.06/0.17/0.07 | 0.08/0.04/0.05 | 0.33/0.21/0.19 | 1.62 | 3 |
| engine accurate | 0.30/0.19/0.35 | 0.09/0.09/0.12 | 0.08/0.03/0.05 | 0.31/0.23/0.21 | 1.44 | 0 |
| colprof | 0.13/0.13/0.05 | 0.09/0.09/0.04 | 0.04/0.04/0.04 | 0.04/0.09/0.07 | 0.52 | 0 |

The engine's neutral ramp is 2–5× rougher (second differences) than colprof's at both ends — shadows (L < 10, where A-04 lives) and highlights (L > 70, where A-03 lives); the mid-tones are equal. Max second difference 1.4–1.6 codes/step vs 0.52. A second difference of 1.4 codes in a 0.5 L* step is a visible step in a smooth gradient on an 8-bit driver. Perceptual ramps (B2A0) are colprof-matched at the nodes and come out at colprof's smoothness (d2 RMS ≤ 0.03 on the accurate file's neutral).

(c) chroma slices a*=b*=+20 (in gamut L 25–81.5): accurate d2 RMS 0.029/0.026/0.034 vs colprof 0.041/0.054/0.056 — engine smoother; a*=b*=−20 (L 48.5–77.5): accurate 0.104/0.045/0.041 vs colprof 0.057/0.029/0.047 (colprof's in-gamut range there is only L 45.5–55.5, so its numbers cover a shorter span).

Chart self-fit through the written A2B1 (ΔE2000 med/p95/max): fast 0.145/0.453/1.63, **accurate 0.103/0.397/5.5**, colprof 0.344/0.929/3.11 — the accurate profile fits the patches 3× tighter than colprof (the 5.5 max is one of the two down-weighted patches). See A-07 for whether that is accuracy or over-fit.

---

## A-07 — Held-out accuracy and the CV ladder, A4 (d)–(e) — **BUG (the "smoothing chosen by cross-validation" is a coin toss; on the 924p chart accurate generalises WORSE than fast and colprof)**

Tool: `work-A/a4d_heldout.py <chart> <outdir>` — `benchmarks.heldout.split_ti3` (90/10, seed 4242, white/black duplicates protected), engine fast + accurate (q=m, no source: A2B1 is source-independent) and `colprof -qm` on the *same* training split, held-out patches scored through the written profiles with xicclu, ΔE2000 in the absolute basis (`-ia` vs the raw-XYZ Lab — independent of which white each builder chose) and in the media-relative basis against the mean-of-duplicates white. Results `builds/ho924/result.json`, `builds/ho1168/result.json`. **Measured:**

| chart | builder | held-out ΔE00 abs med / p95 / max | held-out rel (mean white) med | training-set med | CV choice (log) |
|---|---|---|---|---|---|
| 924p (92 held out) | fast | **0.659** / 1.758 / 2.31 | 0.690 | 0.140 | — |
| 924p | accurate | **0.826** / 1.801 / 2.63 | 0.847 | 0.343 | **×4** (held-out median 0.69) |
| 924p | colprof | 0.700 / 1.789 / 2.60 | 0.719 | 0.306 | — |
| 1168p (116 held out) | fast | 0.339 / 0.989 / 1.79 | 0.370 | 0.098 | — |
| 1168p | accurate | 0.347 / 1.004 / 1.79 | 0.356 | 0.034 | ×0.25 (0.41) |
| 1168p | colprof | 0.383 / 0.951 / 1.81 | 0.396 | 0.190 | — |

On the full 924p chart the CV chose **×0.25** (log: "held-out median 0.65"); on 90 % of the same chart it chose **×4** — the two ends of a 16× ladder — and the resulting profile fits its own training patches at 0.34 instead of 0.05 and flags 5 outliers instead of 2 (rows 11, 262, 679, 731, 779 vs 757, 811). On the held-out patches that profile is 25 % worse than fast (0.826 vs 0.659) and worse than colprof. On the 1168p chart the three tie within the ±0.05 noise floor `benchmarks/README.md` names.

Why: the CV criterion is flat. Replicating `accuracy.py:cv_err` (`fit_forward_model`, grid 17, `curve_rounds=1`, `cg_iters=350`, median ΔE2000 on the 10 % hold-out) for the five ladder factors and three permutation seeds (`work-A` inline probe, printed in this session; relative Lab here uses the brightest white, so absolute values differ from the log — the *shape* is the point):

| chart | seed | ×0.25 | ×0.5 | ×1 | ×2 | ×4 | winner |
|---|---|---|---|---|---|---|---|
| 924p full | 4242 (engine's) | 0.652 | 0.669 | 0.701 | 0.713 | 0.747 | ×0.25 |
| 924p full | 1 | 0.628 | 0.631 | 0.643 | 0.671 | 0.715 | ×0.25 |
| 924p full | 2 | 0.737 | 0.723 | 0.721 | 0.726 | 0.751 | ×1 |
| 924p 90 % | 4242 | 0.714 | 0.716 | 0.737 | 0.730 | 0.695 | ×4 |
| 924p 90 % | 1 | 0.801 | 0.798 | 0.786 | 0.822 | 0.785 | ×4 |
| 924p 90 % | 2 | 0.709 | 0.702 | 0.711 | 0.752 | 0.782 | ×0.5 |
| 1168p full | 4242 | 0.372 | 0.364 | 0.362 | 0.362 | 0.372 | ×2 |
| 1168p full | 1 | 0.369 | 0.359 | 0.350 | 0.352 | 0.372 | ×1 |

The spread across the whole ladder is 0.01–0.1 ΔE00, the spread across seeds at a fixed factor is 0.1 — the criterion cannot tell ×0.25 from ×4 on this instrument's noise, and the log reports the noise as a decision ("Smoothing chosen by cross-validation: ×0.25 … (held-out median 0.65 ΔE2000)"). The boundary is also never flagged (plan S06): both real choices sat at an end of the ladder.

What λ×0.25 vs ×1 does to (a)–(c): the accurate q=m profile (×0.25) has the tighter self-fit (0.05 vs fast's 0.15) but the *same* round-trip median (0.68 vs 0.71), a worse round-trip tail (7.26 vs 6.56), and the same neutral-ramp roughness as fast (A-06) — the extra stiffness buys chart-patch fit and nothing at the print. Verdict for A4: **"Maximum accuracy" is more accurate at the chart patches only.** On unseen patches it is a tie (1168p) or a loss (924p); on B2A smoothness and round trip it is not better than fast and worse than colprof.

Fix direction (for the orchestrator, not implemented): (1) make the CV decision require a margin above the criterion's own noise (bootstrap the hold-out or use ≥ 3 folds) and fall back to ×1 when nothing wins by more than that; (2) say so in the log ("no factor beat the standard smoothing — keeping ×1"); (3) name a boundary pick as such. Battery gate: `benchmarks/README.md` rules apply; nothing here was tuned against the owner's charts.

---

## A-08 — `gamt` tag semantics (A5) — **INCONSISTENCY (engine marks 68 % of printable colours out-of-gamut; colprof 28 %)**

Reference: ICC.1:2022 §9.2.29 gamutTag (text extracted from https://archive.color.org/specification/ICC.1-2022-05.pdf, `work-A/scratch/icc-spec-crude.txt` @ 141536): *"This tag provides a table in which PCS values are the input and a single output value for each input value is the output. If the output value is 0, the PCS colour is in-gamut. If the output is non-zero, the PCS colour is out-of-gamut."*

The plan's ring test was unusable as an in-gamut set (a ±d ring around a 21²-face surface round-trips > 1 ΔE76 for 65–74 % of its points on every profile — `builds/a5-gamut.txt`), so the in-gamut set is *device* colours, printable by definition. `xicclu -fg -ir` prints the tag value / 128 (unit check against `benchmarks/iccread.py:gamut_distance`: colprof 1.0 ↔ 128.0, engine 0.995 ↔ 127.4). **Measured** (`builds/a5-gamut2.txt`):

| profile | 5 000 random interior device colours (0.05–0.95): gamt ≠ 0 | > 0.01 (≈1.3 ΔE) | median | max | 17³ device grid: ≠ 0 | far-OOG set (8 067 Lab points > 10 ΔE from colprof's gamut): ≠ 0, median |
|---|---|---|---|---|---|---|
| engine accurate | **68.3 %** | 34.8 % | 0.0039 (0.5 ΔE) | 0.278 (36 ΔE) | 81.7 % | 100 %, 0.385 (49 ΔE) |
| engine fast | 68.4 % | 39.0 % | 0.0046 | 0.318 | 81.9 % | 100 %, 0.433 |
| colprof -qm | 28.0 % | 27.1 % | 0.0000 | 1.000 | 44.4 % | 100 %, 1.000 |

Both violate the letter of §9.2.29 for interior colours — colprof through coarse 0/128 interpolation near the surface (its nonzero values are almost all the saturated 1.0), the engine through a *continuous* small residual (the GN clamp distance, `b2a.py:456-459` → `builder.py:415-417` /128) that leaks 0.5 ΔE onto two thirds of the printable interior and up to 36 ΔE onto a printable device-grid colour. A soft-proof gamut warning that tests `≠ 0` lights up two thirds of every image through the engine's profile; one that thresholds at ~1 ΔE behaves like colprof's. The littleCMS `GAMUTCHECK` leg is **NOT-MEASURABLE-HERE**: PIL's proofing transform flagged L 50 neutral as out of gamut on colprof's profile too and did not flag a*=b*=+120, so the harness, not the profiles, was wrong; not pursued.

Acceptance for a fix: interior device colours → gamt = 0 for ≥ 99 % (colprof's own figure is 72 %, so matching colprof is not the bar; the spec is), far-OOG → nonzero for 100 % (already true).

---

## A-09 — Option matrix (A3), part 1: the ink-limit flags on CMYK — **BUG: `-L` is a total limit in the engine; `-l` itself is fine**

Inputs: S3 synthetic CMYK (`benchmarks.synthetic.PRINTERS["S3"]`, TAC 280, 900 patches, `work-A/scratch/syn/S3.ti3`), engine accurate q=l `-S ClayRGB1998.icm` (`builds/m/S3-*.icc`), colprof `-ql -S ClayRGB1998.icm` on scratch copies (`scratch/cref/`). Ink sums = `xicclu -fb` on a 20×17×17 Lab grid, C+M+Y+K in % (`work-A/a3_analyse.py:ink_sums`). **Measured:**

| build | B2A1 max total ink | B2A1 max K | B2A0 max total | B2A0 max K |
|---|---|---|---|---|
| engine, no flag (ti3 says 280) | 278.7 % | 99.9 % | 268.9 % | 97.5 % |
| engine `ink_limit=200` (`-l 200`) | 200.8 % | 99.2 % | 200.8 % | 75.3 % |
| **engine `-L 50`** → `_apply_extra_args` sets `ink_limit = 50.0` (`engine_builder.py:80-81`; `BuildSettings` has no black-limit field) | **51.4 %** | 49.0 % | 51.4 % | 49.1 % |
| colprof, no flag | 263.0 % | 99.6 % | 247.8 % | 99.8 % |
| colprof `-l 200` | 209.0 % | 100 % | 202.7 % | 98.1 % |
| **colprof `-L 50`** | **260.9 %** | **49.4 %** | 251.6 % | 49.4 % |
| colprof `-L 30` | 261.9 % | 29.7 % | 261.9 % | 29.7 % |

colprof's usage text (run today): `-l tlimit override total ink limit, 0 - 400%`, `-L klimit override black ink limit, 0 - 100%`. A user typing `-L 50` in Manual's extra options gets a profile that never puts more than 51 % of ink *in total* on the paper — a print with no shadows. Plan S01 / critic S01 confirmed numerically. (colprof `-l 50` itself fails: "calc_ocent failed to return in-gamut focal point!" — a 50 % total limit is not a real request; the `-L 50` result above is the real one.)

`-l 200` (critic N04): honoured in both engine tables (200.8 % max, both). Ground truth on 20 000 targets printable at 200 % (`eval_points` projected to TAC 2.0, `benchmarks.iccread` replay of the written bytes; inline probe in this session): engine `-l 200` B2A1 printed-vs-target ΔE00 med 1.59 / p95 4.15 / max 7.9 vs colprof `-l 200` 2.67 / 7.99 / 21.8; perceptual B2A0 engine 3.50 / 6.61 vs colprof 3.60 / 6.53. The oracle-without-`-l` mechanism the critic described exists (`gamut_map.py:540-566` passes no `-l`), but its effect is not a loss against colprof's own `-l 200` perceptual table — **OK** as measured. Note the engine's perceptual rendering on S3 differs from colprof's by 0.74 median / 2.0 p95 at base and 1.14 / 9.6 at `-l 200` (printed Lab through each profile's A2B1), i.e. "matched to ArgyllCMS colprof" holds at base and loosens under an ink limit.

`-k p 0 0.1 0.9 1 1` / `-k z` (S3, accurate): K along the neutral axis L 8→97: default 87/77/52/35/20/8/3/0/0/0/0/0 %; `-kp` 86/99/98/85/71/59/47/36/26/14/3/1 %; `-kz` 61/63/6/0/1/3/2/0/0/0/0/0 % — the rules move K as their names say. **OK** (no colprof parity number taken; the curve shapes are as `colprof.html` describes).

---

## A-10 — `-u <scale>` — **INCONSISTENCY (engine accepts and half-applies what colprof refuses)**

colprof 3.5.0 on the 924p chart: `colprof -ql -u 0.9 u` → `Error - Input auto WP scale mode isn't applicable to an output device`, exit 1, no `.icc` (`work-A/scratch/u/`; the orchestrator measured the same). The engine (`engine_builder.py:169-171` maps `-u <scale>` to `wp_scale`; `builder.py:290-294` scales one row): accurate q=l `wp_scale=0.9` → `wtpt` Y 81.241 vs 83.331 = **×0.975** (critic M6's mechanism, now on the real chart: one of four white rows scaled, then averaged); fast → Y 83.406 = ×1.001 (scale lost to the re-selected brightest duplicate). Both write a profile. The right behaviour is colprof's: refuse with the same message, as `_WP_MODE_ERRORS` already does for `-u`/`-ua`/`-uc` (`engine_builder.py:176-182`). Critic N02's premise that colprof honours the scale on output data is wrong.

---

## A-11 — Observer 2015_2 — **BUG (confirmed; exact text)**

`build.py … --set observer='"2015_2"'` → `SpectralError: Unknown observer '2015_2' (the engine knows 1931_2 and 1964_10).`, no `.icc` written. colprof accepts `-o 2015_2` (usage text). Critic M8/N03 confirmed on the real chart; nothing new except the record.

---

## A-12 — `-nP -nS` builds the saturation table from the perceptual mapping — **BUG (flag translation)**

`gamut_map.py:548-552` passes `-s` to the oracle when both `perc_src_colorimetric` and `sat_src_colorimetric` are set. colprof `-s` = "perceptual only, saturation aliases perceptual" (colprof.html). **Measured** (`builds/m/nPnS.icc`, tag table): B2A2 md5 `91f5ab…` = B2A0 md5 `91f5ab…` — the saturation table *is* the perceptual table; in the baseline B2A2 is distinct (`69e779…`). With `-nP` alone only `desc` changed (a matrix source's colorimetric and perceptual gamuts coincide, so that is expected). Separately, plain `-s <icc>` and `-S <icc>` are indistinguishable to the engine's parser (`engine_builder.py:164-165` → one `source_gamut`), so a colprof user's `-s` gets a distinct saturation table (`build_mapped_b2a` always fills B2A2, `gamut_map.py:875-913`) where colprof aliases it: colprof `-ql -s ClayRGB` → B2A2 offset = B2A0 offset (381444, verified in `scratch/cref/s.icc`); the engine has no way to express that. Critic N05 confirmed. Low user impact, but a translation error either way.

---

## A-13 — `spectral_physics` on RGB is a silent no-op — **GAP**

`builds/m/spectral.icc` vs `base-ql.icc`: only `desc` differs (tag bytes identical). The log (`builds/m/spectral.log`) contains **no line** mentioning the option — `builder.py:365-375` calls `fit_spectral_hybrid` and prints only when it returns a verdict; on RGB it returns `None` (docstring: "silently a no-op"). The user ticked a Manual row and cannot see from the log that it did nothing. One log line is the fix.

---

## A-14 — Noise handling on a *clean* real chart engages and changes the fit — **INCONSISTENCY (the "only-win-or-do-nothing" contract is not what happens)**

`builds/m/noise.icc` vs base (924p, accurate q=l): log `Repeated patches scatter 5.3× the healthy-instrument level — noise handling engaged.` / `Measurement-noise model from duplicate patches: σ = 0.265 + 0.000·exp(−Y/10).` / `Smoothing chosen by cross-validation: ×0.707107 …`; every LUT tag differs from the baseline; self-fit 0.218 vs 0.124 ΔE00; 0 outliers flagged instead of 2. The 5.3× comes from the four white rows' scatter, std Y 0.26 (`work-A` probe: rows J9/AR2/N15/AC7 Y 83.605/83.334/83.407/82.981) — spatial paper/print non-uniformity across the sheet, which `gp.py:_DEFAULT_FLOOR + _DEFAULT_DARK = 0.05` (an instrument-repeatability constant) cannot tell from instrument noise. On the 1168p chart (9 whites) the same detector reports (see the held-out line appended below). Whether the engaged fit is better or worse on unseen patches is measured in the A-07 addendum below; either way the tooltip's "stands aside on a clean measurement" is not true for real charts with spatially separated duplicates.

---

## A-15 — Outlier report on a noisy chart flags 61 patches, 1 real — **BUG**

S4 (synthetic CMYK, 3× instrument noise, one true misread row 854), accurate q=m, no source (`builds/m/S4-base.icc`): log `61 patch(es) disagree strongly with the model and were down-weighted … Consider remeasuring them.` — flagged rows `[51, 76, 97, …, 896]`, true `[854]`: precision 1/61, recall 1, F1 0.03. With `noise_model=true` (`S4-noise.icc`): 6 flagged (`[51, 588, 656, 671, 818, 854]`), F1 0.29, and the ground-truth battery score improves (A2B med 0.435 → 0.406, B2A med 0.542 → 0.434, `benchmarks.battery.score_profile`, n_eval 20 000). The plain accurate mode's Huber scale (`accuracy.py:195-202`, floor 0.35 ΔE) is far below the chart's real scatter, so ordinary noise is reported as misreads and the user is told to remeasure 61 patches. The `benchmarks/README.md` gate "S4 misread F1 not worse" is measured against a baseline that is already 0.03.

---

### A-07 addendum — held-out with `noise_model=true` (measured after A-14)

Same split, same referee (`builds/ho924n/`): 924p accurate+noise **0.647** ΔE00 median (fast 0.659, colprof 0.700, plain accurate 0.826; CV under whitening chose ×0.354); 1168p accurate+noise **0.394** (fast 0.339, plain accurate 0.347, colprof 0.383; CV chose ×4, "held-out median 0.25 × the instrument noise"). Both charts report "scatter 5.3× / 5.1× the healthy-instrument level" (σ floor 0.265 / 0.257 XYZ units). So on 924p the whitened CV rescued the plain mode's ×4 pick; on 1168p it lost 0.05 (noise floor). Neither variant of "Maximum accuracy" beats "fast" on unseen patches by more than the ±0.05 noise floor on either real chart; the plain mode loses by 0.17 on one of them.

---

## A-16 — Robustness inputs (A7) — **BUG (NaN → garbage profile written silently) + GAPs (stuck instrument, junk scanner chart, small chart all build without a word)**

All builds: accurate, q=l, **all four options on** (`spectral_physics`, `noise_model`, `icc_version="both"`, `render_style="bijective"`), no source gamut (`work-A/rob.sh`, inputs made by the python block in this session under `work-A/scratch/rob/`, outputs `builds/rob/`). **Measured:**

| input | outcome | what the log / profile says |
|---|---|---|
| 924p with one XYZ_X = `nan` (row 101) | **profile written (384 108 B, plus a v4 twin), exit ok, 33 s** | log: `Model-error floor … (shadows ±nan ΔE, highlights ±nan ΔE)`, `Smoothing chosen … (held-out median inf × the instrument noise)`, `Model fit (perceptual ΔE2000): median nan, 95% nan`; `oog_fraction 1.0`. The written A2B1 returns **Lab (0, −128, −128) for white, black, mid grey and red** (the Lab16 encoding floor); B2A1(50,0,0) → RGB (0, 0, 0). A dead profile with a green log (xicclu, `builds/rob/nan.icc`). (Critic M7 got a `ValueError` on the *default* accurate path; with `noise_model` on the NaN survives to the file.) |
| 18p CR30 chart (every patch ≈ XYZ 48.4/37.4/5.8, no white) | profile written, 1.4 s, "Model fit … median 0.03, 95% 0.06", noise "low … standard fit" | A2B1: white → L 100.08, black → L 99.74, grey → 100.29, red → L 100.39 a 0.05 b −2.54 (every device value is paper white, because every patch *is* the media white); B2A1(50,0,0) → RGB (6, 0, 3); `oog_fraction 0.999`. Nothing in the log says the chart is flat. |
| 315p scanner-measured chart (white Y 26.7, black Y 25.4) | profile written, 2.8 s | "Smoothing chosen … ×4 … (held-out median **9.08** ΔE2000)", "Model fit … median **5.08**, 95% **14.52**" — the numbers are printed, no verdict is drawn; the profile installs like any other. |
| Lab-only `.ti3` (LAB_L/A/B, no XYZ, no SPEC; `COLOR_REP "RGB_LAB"`) | ok, 8.3 s, fit 0.218 | works (`ti3_data.py:262-265`); `spectral_physics` silently inapplicable (no line, A-13). **OK** |
| 60-patch subsample (1 white, 1 black) | ok, 6.5 s, fit 0.33 / p95 2.04, 1 outlier | **no "Smoothing chosen" line at all** (`_HOLDOUT_MIN_PATCHES = 120`, `accuracy.py:99`) — the tooltip's "tuned against held-back patches" silently did not happen. GAP (plan S09). |
| zero duplicate whites (1 white, 1 black) | ok, 8.0 s, fit 0.19, CV ×0.5 | `average_endpoints` no-op, `estimate_xyz_noise` → defaults ("noise is low"), CV picked ×0.5 where the 4-white chart picked ×0.25 (A-07 again). **OK** |
| duplicate SAMPLE_IDs (all "1") | ok, 8.2 s, identical statistics to the normal build | `read_ti3` never reads SAMPLE_ID. **OK** (and the reason outlier rows are reported by row number, S07). |
| S3 with `TOTAL_INK_LIMIT "400"` while the chart was printed at 280 % | ok, 6.1 s | engine `ink_limit` = 400 → B2A1 asks for up to **348.9 % total ink (p99 293 %)** measured (`ink_sums`) on a printer whose chart never exceeded 280 % — the inversion extrapolates the model 69 % beyond the measured ink range; no warning that the stamped limit exceeds every patch on the chart. colprof on the same file would use 390 % (its −10 % rule), so parity is not the defence; the chart's own maximum is. |

Acceptance for the NaN case: `read_ti3` (or `build_profile`) must refuse a non-finite XYZ/Lab/SPEC value with the row *and SAMPLE_LOC* named, before any fit — colprof's behaviour is `_sanitize_scanner_ti3` territory (`scanin_dialog.py:5380-5395`) only on the scanner path. For the flat chart: a one-line sanity gate (white L* − black L* < 10, or gamut volume ≈ 0) that refuses to write.

---

## A-17 — Option matrix (A3), part 2: the rest of the surface — mostly **OK**, with four items to fix

All: 924p, accurate, q=l, `-S ClayRGB1998.icm`, fresh process, fixed timestamp; baseline `builds/m/base-ql.icc`; comparison `work-A/a3_analyse.py` (tag-level md5 + header fields; text in `builds/m/analysis.txt`, JSON `builds/m/analysis.json`). "Only desc" = every other tag byte-identical to the baseline (the description carries the file stem).

| option | changed vs baseline | verdict |
|---|---|---|
| `-ni` (`no_input_shaper`) | in-process check (the matrix file `ni.icc` was overwritten by the `nI` job — APFS folds case, so `ni.icc` = `nI.icc`; recorded, redone in-process): `model.curves` max deviation from identity **0.0000** vs 0.0499 without; fit 0.128 vs 0.124 | **OK** |
| `-no` | B2A1 output tables identity ✓, only B2A1 changed — **B2A0/B2A2 keep their shaper output tables** (`gamut_map.py:build_mapped_b2a` always uses `inv_curves`) where colprof's `-no` applies to every B2A table | INCONSISTENCY, minor |
| `-nc` | `targ`/`DevD`/`CIED` absent, 46 336 B vs 406 184 B, nothing else changed | **OK** |
| `-Z mtnb` | header attributes `0x0f`, only desc otherwise | **OK** |
| `-Z s` | header default intent 2, only desc otherwise | **OK** |
| `-A "Ärger GmbH" -M "Größe A3" -C "© Müller" -D "Müller-Prüfdruck"`, v2 | lcms reads `Mueller-Pruefdruck` / `Aerger GmbH` / `Groesse A3` / `(c) Mueller` (ASCII transliteration, `icc_text.ascii_fallback`); iccdump shows the ASCII part plus a Unicode part holding `M\303\274ller…` (UTF-8 bytes); `sips -g description` prints `<nil>` for **every** profile incl. colprof's (not a signal) | **OK** for v2 (v2 `desc` is 7-bit ASCII by spec; transliteration is the honest choice) |
| same, v4 | lcms reads `Müller-Prüfdruck` / `Ärger GmbH` / `Größe A3` / `© Müller` from the `mluc` tags | **OK** |
| `-R` | only desc (white Y 83 < 100, nothing to clip) | **OK** |
| `-c pp` / `-c mt` | B2A0 and B2A2 differ from baseline and from each other; the oracle passes `-c` (`gamut_map.py:554-557`) | **OK** — viewing conditions reach the CAM02 mapping |
| `-t s -T p` | B2A0, B2A2 changed | **OK** |
| `-t r` | B2A0 tag entry = B2A1 entry (offset 370860, alias) | **OK** (colorimetric intent aliases, as colprof) |
| `-nP` | only desc (matrix source: colorimetric = perceptual gamut) | **OK** |
| `-nP -nS` | B2A2 = B2A0 (A-12) | BUG (A-12) |
| `-nI` | A2B0/A2B2 distinct from A2B1; perceptual-pair round trip (300 in-gamut device colours, A2B0∘B2A0) 0.62 ΔE00 median vs 1.83 without `-nI` | **OK** |
| `-i D65`, v2 | `wtpt` 79.239/83.455/**95.345** (the D65-relative XYZ written raw); colprof `-ql -i D65` writes 78.577/82.712/94.791, likewise raw; no `chad`, only Argyll's private `arts`; `xicclu -ia` white → L 93.0 a −2.4 **b −21.5** in both tools | INCONSISTENCY with the spec, parity with colprof (colprof.html warns "will not be standard"). ICC.1:2022 §9.2.36: *"When the measurement data used to create the profile were specified relative to an adopted white with a chromaticity different from that of the PCS adopted white, the media white point nCIEXYZ values shall be adapted to be relative to the PCS adopted white chromaticity using the chromaticAdaptationTag matrix, before recording in the tag."* (`scratch/icc-spec-crude.txt` @ 143798) |
| `-i D65`, **v4** | identical `wtpt`, still no `chad` (§9.2.15), header 4.4.0 | **GAP** — a v4 profile with a non-D50 `wtpt` and no `chad` is outside the spec; the engine's v4 writer must either adapt+write `chad` or refuse `-i` ≠ D50 for v4 |
| `-f` on ColorMunki data | `SpectralError: The measuring instrument (X-Rite ColorMunki) doesn't illuminate with UV…` — refusal parity with colprof (critic M9), no file written (colprof truncates its `.icc` to 0 bytes; the engine writes nothing — better) | **OK** |
| `-f` on an `i1 Pro`-stamped copy (`scratch/syn/real924-i1pro.ti3`) | engine builds (fit 0.124), `wtpt` 80.415/83.388/**73.700** (Z +1.26 vs 72.443 without FWA); colprof `-ql -f` → 79.756/82.863/73.233 (Z +1.23 vs its own no-FWA 72.005 at -ql). Absolute Lab at the 924 chart patches, engine-FWA vs colprof-FWA: ΔE00 med 0.343 / p95 0.844 / max 3.08; engine-no-FWA vs colprof-FWA 0.442. White: engine 92.99/0.02/−4.32, colprof 92.95/−0.27/−4.37 (both ≈1.0 b* bluer than without FWA) | **OK** — same direction, same size; the residual 0.34 is the generic engine-vs-colprof A2B difference |
| `spectral_physics` | only desc, no log line | GAP (A-13) |
| `noise_model` | engages on the clean chart, every LUT changes | INCONSISTENCY (A-14) |
| `render_style=bijective` | B2A0/B2A2 changed; log prints **both** `Gamut mapping (maximum accuracy): bijective CAM16-UCS rendering intents (candidate).` and `Gamut mapping (maximum accuracy): rendering intents matched to ArgyllCMS colprof.` (critic N11 confirmed, `gamut_map.py:864-873`); the word "(candidate)" is in a shipped option's log; build 6.7 s vs 22 s (no oracle) | INCONSISTENCY, cosmetic |
| `icc_version=4` | header 4.4.0, `desc`/`cprt` `mluc`, LUT tags byte-identical to v2, `bkpt` still written (not a v4 tag, harmless), no `chad`; lcms reads it (transicc white → 99.79/0.00/0.05); profile ID = the ICC.1:2022 §7.2.18 digest (recomputed here: `f87cbccd…` = stored; the same recomputation reproduces Apple's own `Display P3.icc` ID `ecfda38e…`) — **but `sips --verify` says `Header message digest (MD5) is not correct.`** Ten alternative digests (size/date/platform/creator/cmm/attributes zeroed, header-only, body-only, id-only, flags-only) were written into copies and every one is rejected too; a version byte change (4.0.0 / 4.3.0) does not help; with the ID zeroed sips says "missing" instead. lcms's own v4 sRGB writes no ID (sips: "missing"). File size and every tag offset are 4-byte aligned. | **NOT-MEASURABLE-HERE beyond the fact**: Apple's verifier rejects the engine's v4 ID for a reason none of the spec-derived variants explains; Agent B should look at what ColorSync Utility shows the user for `builds/m/v4.icc` |
| `icc_version=both` | twin `both-v4.icc` written; v2 and twin `desc` both read `both` (lcms) — identical names (critic N12 confirmed); LUTs identical, only header/desc/cprt differ | GAP (N12) |
| `-V 1.6` | `_apply_extra_args("-V 1.6")` leaves `BuildSettings` equal to the default (no field) — no-op by construction; colprof `-ql -V 1.6` vs plain: every tag byte-identical, header date only (`scratch/cref/v.icc` vs `v16.icc`) | **OK** (parity) |
| `-s 20` / `-S 20` (percentage forms) | parser stores `"20"` as `source_gamut`; `engine_support` → `Gamut source profile not found: 20` → routed to colprof on ≤4 inks (critic §5 confirmed by running the parser) | GAP for CMY+N only |
| `-g x.gam` / `-p abs.icc` | `ExtraArgsError` → colprof on ≤4 inks | as documented |
| `-a x` (XYZ PCS, cube-root B2A curves) | not built in this matrix (time); the codec's tables are exercised by the parity tests in the repo, not by a real CMM here | NOT-MEASURED |

### A6(d) — calibrated chart, `FINAL_TOTAL_INK_LIMIT`

`read_ti3` on S3 with `TOTAL_INK_LIMIT "280"` + `FINAL_TOTAL_INK_LIMIT "230"`: `meas.ink_limit` = **280.0** (keywords seen: both). colprof on the same file (no CAL table) printed `Total ink limit being used is 270%` — colprof's `FINAL_TOTAL_INK_LIMIT` path (`colprof.c`, see the grep in this session) applies to charts carrying calibration; without a CAL table it also ignores the keyword. So for a genuinely calibrated CMYK `.ti3` the engine will use the pre-calibration limit where colprof uses the post-calibration one (critic N09, read, the CAL-table build not done here); on RGB calibration runs there is no ink limit and no difference. GAP, low.

---

## A-18 — Duplicate-patch averaging (A6 c, plan S23) — **IMPROVEMENT (measured on the battery: pre-averaging beats fitting through repeats, and fitting through repeats floods the outlier report)**

`work-A/a6c_dupavg.py`: S4 (noisy CMYK, 3× instrument noise) chart of 900 patches measured three times with independent noise (seeds 23/24/25); three accurate q=m builds (no source, `ink_limit=280`) scored against `f_true` with `benchmarks.battery.score_profile` (n_eval 20 000). Results `builds/dupavg/result.json`. **Measured:**

| chart | rows | A2B ΔE00 med / p95 | B2A end-to-end med / p95 | round-trip p95 | patches flagged as misreads | CV pick | build |
|---|---|---|---|---|---|---|---|
| single read | 900 | 0.435 / 1.254 | 0.542 / 1.661 | 1.41 | 61 | ×4 | 11.4 s |
| **3 reads stacked** (what a merged/averaged `.ti3` with repeats looks like to the engine) | 2 700 | 0.319 / 1.162 | 0.500 / **1.986** | 1.99 | **205** | ×4 | 22.0 s |
| **3 reads pre-averaged** | 900 | **0.300 / 1.032** | **0.463 / 1.547** | 1.43 | 62 | ×2 | 10.9 s |

Averaging before the fit wins on every metric over stacking the repeats (B2A p95 1.55 vs 1.99, round-trip p95 1.43 vs 1.99, half the time) and both beat a single read. Stacked repeats also make the robust loop name 205 patches "misreads" (the between-read scatter of identical device values). `average_endpoints` (`ti3_data.py:85-106`) does this for white/black only; extending it to every exact duplicate group (`gp.py:duplicate_groups` already finds them) is the Q2 candidate with the best evidence on this battery — basICColor "Measurement Correction" and i1Profiler average repeats by default (critic §5 sources). Chart-noise caveat: the 924p/1168p real charts carry only endpoint duplicates, so this is battery-only evidence.

---

## A-19 — Q2: more options, ranked (A9)

Ranking = (i) how often a printmaker needs it (colprof.html / basICColor manual / i1Profiler practice as cited by the critic §5), (ii) evidence from A3/A6 today, (iii) cost in this codebase.

| rank | option | need | evidence today | cost |
|---|---|---|---|---|
| 1 | **Black ink limit** (`-L`, `BLACK_INK_LIMIT`) | every CMYK/CMY+N profile with a K channel; i1Profiler "Max Black", basICColor "Black Definition" | A-09: `-L 50` currently caps *total* ink at 51 % (BUG) — the option exists in the UI vocabulary through extra args and does the wrong thing | small: one `BuildSettings.k_limit`, a K-column clamp in `invert_to_device`/`refine_b2a_clut` beside the TAC projection, `_apply_extra_args` split, read `BLACK_INK_LIMIT` in `ti3_data` |
| 2 | **Duplicate-patch averaging** | every chart with repeats (targen `-e`, i1Profiler, averaged/merged reads, ChromIQ's own averaging feature) | A-18: better on every battery metric, 205 → 62 false misread flags | small: generalise `average_endpoints` over `duplicate_groups`, keep endpoint semantics; battery gate already exists |
| 3 | **2015 observers (+ `.cmf`) and `.sp` illuminant files** | anyone following CIE 170-2 / ISO 13655 M-series work; the UI already *offers* 2015_2/2015_10 | A-11: the offered option fails at build time | small for the observers (tables into `spectral_data.py`; CIE 170-2 at https://cie.co.at/datatable/cie-2015-2-degree-cone-fundamentals-based-cmfs-... — verify the URL when implementing), medium for `.sp` parsing (Argyll's CGATS `.sp` is `spec2cie`-readable; `/Applications/Argyll/ref/*.sp` for tests) |
| 4 | `-s`/`-S` percentage forms (compression/expansion amount) | perceptual taste control (basICColor sliders, i1Profiler Contrast/Saturation) | A-17: parser treats `20` as a path → colprof fallback | medium (only the oracle path can honour it: pass through to colprof) |
| 5 | `-g` image gamut, `-p` abstract profile | occasional (`tiffgamut` users) | routed to colprof on ≤4 inks; CMY+N cannot use them | medium/large |
| 6 | per-channel dot limits | basICColor CMYK only | none today | large; not in colprof either |

Designs for the top 3:

**1 — Black ink limit.** Manual group, Build-profile "Ink limits" row beside the total-ink field (the total field itself is `-l`, extra-args only today): a spinbox "Black ink limit %" (0–100, blank = from the `.ti3`'s `BLACK_INK_LIMIT`, else none). Tooltip: "Caps the black channel on its own — the total ink limit still applies on top. colprof's `-L`. Leave blank to take the value from the measurement." `BuildSettings.k_limit: float | None`; `_apply_extra_args`: `-L` → `k_limit`, `-l` → `ink_limit` (stop folding); `ti3_data.Ti3Measurement.black_ink_limit` from the keyword; `b2a.py`: clamp column 3 to `k_limit/100` inside `_gauss_newton`'s projection and after `refine_b2a_clut`, and pass `-L` to the colprof oracle so the mapped tables see the same gamut. Test: S3 accurate `k_limit=50` → `xicclu -fb` Lab grid: max K ≤ 50.5 %, max total ≥ 250 % (colprof `-L 50` today: 49.4 % / 260.9 %, A-09 table); `-L 50` through the parser must produce the same file as `k_limit=50`; the everyday-tier test lives beside `tests/test_engine_builder.py`.

**2 — Duplicate averaging.** Manual group, "Measurement noise handling" row gets a sibling checkbox "Average repeated patches (recommended)" default on in accurate mode; tooltip: "Patches printed more than once are averaged before the fit — an unbiased estimate that cuts instrument noise by √k. Off = fit through every reading (colprof's behaviour)." `BuildSettings.average_duplicates: bool = True`; `Ti3Measurement.collapse_duplicates()` → new device/xyz/spectral arrays with the group mean, keeping SAMPLE_LOC of the first row for the outlier report; `noise_model` keeps estimating σ from the *uncollapsed* groups (it needs the scatter) — so the collapse runs after `estimate_xyz_noise`. Test: the A-18 script as a battery gate (pre-averaged ≤ stacked on B2A p95, misread flags ≤ single-read count); a unit test that a 3×-repeated synthetic chart collapses to N unique rows with the mean XYZ.

**3 — 2015 observers.** No new widget — the observer combo already lists them (`tab_profile.py:2628-2636`); `spectral_data.py` gains `OBS_2015_2`/`OBS_2015_10` (CIE 170-2:2015 tables, 390–830 nm at 1 nm, resampled like the 1931 set); `spectral.py:_OBSERVERS` gains the keys; `engine_support` validates the observer against `_OBSERVERS` and hands unknown ones (`shaw`, `1955_2`, `1978_2`, `file.cmf`) to colprof with the log line the beta tooltip promises. Test: parity — build the 924p spectral chart with `-o 2015_2` through colprof and the engine, `xicclu -ff -ir` at the chart patches, ΔE00 median ≤ 0.35 (today's engine-vs-colprof floor, A-17 FWA row); and `engine_support(observer="shaw")` → `(False, "…observer shaw…")`.

---

## A-20 — Light inks (A6 a, plan S18): CMYKcm on the battery machinery — **BUG (highlights print 6 ΔE00 off; light inks erratic on neutrals)**

`work-A/a6_lightink.py`: `SyntheticPrinter("S7", "CMYKcm", tac=300, yn_nu=4.0)` with `c`/`m` = 40 % of the C/M absorbance (same hue), registered only in the work folder (`benchmarks/` untouched); 1 200-patch chart, accurate q=m, no source, `ink_limit=300`; built in **438 s**; measured extra-ink hues `c` 232.2°, `m` 345.6° (the cyan/magenta hues — `extra_ink_hues` reads a light ink as a spot ink of that hue, `ti3_data.py:135-160`). Referee `benchmarks.battery.score_profile` (n_eval 20 000) + `xicclu -fb -ir` ramps. Results `builds/lightink/`. **Measured:**

* Battery: A2B ΔE00 med 0.69 / p95 2.16 (fit at the patches 0.39 / 1.66); B2A end-to-end med 0.95 / p95 2.59 / **max 18.7**.
* **B2A end-to-end restricted to targets with L* > 75: ΔE00 median 6.03, p95 14.1** — the highlights, exactly where a light-ink printer is bought for. There the profile uses c 13.3 % / m 3.9 % on average against C 13.1 % / M 24.2 %.
* Neutral ramp L 20→97 (B2A1), light channels: `c` = 0.1/0.4/0.1/0/0/0.1/0/0/**3.3/4.6/0.5/7.3** %, `m` = 0.8/0/0.1/0.1/0/0/**2.7**/0/0.2/**5.8/17.5/16.6** % — zero through the mid-tones (the `chroma − 15` gate in `b2a.py:extra_ink_amount` zeroes the prior on neutrals) and then non-monotone jumps in the highlights where the solver is free to use them; C/M/Y meanwhile run 6–13 % at L 90–97.
* A cyan tint ramp at L 80 (chroma 4 → 21): `c` 9.8 → 21.5 % alongside `C` 18 → 29 % — inside its hue gate the light ink *is* used, next to the full ink instead of instead of it.

So the critic's S18 diagnosis is measured: the hue gate treats light cyan/magenta as spot colours, the neutral/highlight region gets no light-ink prior and an under-determined inversion, and the printed result in the highlights is off by 6 ΔE00 median. Acceptance for a fix: on S7, B2A end-to-end for L* > 75 ≤ the whole-gamut median (≈ 1 ΔE00), light-channel neutral ramp monotone (TV-vs-net excess < 5 %), and CMYK-only S3 numbers unchanged.

---

## A-21 — CMYKOG at `-q h` / `-q u` (A6 b, plan S19) — **GAP (25 minutes for the same A2B, no grid-reduction line, ETA off by 5×)**

`builds/m/S5-qh.*`, `S5-qu.*` (S5 synthetic CMYKOG, 900 patches, accurate, no source). **Measured:** `-q h` → 1 453.6 s, `-q u` → 1 505.4 s, both `a2b_grid 11` (17 and 23 stepped down by `builder.py` `while a2b_grid ** n > 2_000_000: a2b_grid -= 2`), B2A grid 33 / 45; **A2B fit identical** (0.32 / 1.64 ΔE00 in both) — the extra 52 s of `-q u` buys a bigger B2A grid only. The log names the grid ("Fitting the printer model (900 patches, grid 11)…") and never says it was reduced from 17/23; at 14 % it announced "~121 min left" for a build that took 24 min. Nothing in the app can cancel it (critic S15/N16). One line ("grid reduced from 17 to 11 to stay inside memory") and an ETA that ignores the first stage would make this honest; a cap that refuses `-q u` on ≥ 6 inks (same A2B as `-q h`) is the cheaper product answer.

---

## Closing note

Not measured (time): `-a x` through a real CMM (A-02 note), the refinement-merge journey (N08, Agent B), a genuinely calibrated CMYK `.ti3` with a CAL table (A6 d, read only), Photoshop/ACE. Everything else in the brief has a number above. Total wall time of measurement ≈ 2 h 50 min; ~110 profile builds under `work-A/builds/`.
