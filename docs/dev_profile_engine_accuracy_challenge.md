# The profile engine's "Maximum accuracy" mode — the 2026-09 challenge

What was measured, what was wrong, what changed, and how to re-run every
check. The full evidence (plan, critic, two agents' findings, reviewer,
builds, screenshots) lives outside the repo in the owner's
`~/Desktop/ChromIQ-engine-challenge/`; this page keeps what a developer
needs in the tree.

## What "Maximum accuracy" is

Preferences → Beta → *ChromIQ profile engine (beta)* → Accuracy = *Maximum
accuracy* (`gammap_mode == "accurate"`). The engine (`workflow/profile_engine/`)
then fits the printer model with a cross-validated, outlier-robust loop
(`accuracy.py`), pins the paper white and the black corner, clips out-of-gamut
colours by hue, and renders the perceptual/saturation tables through Argyll
colprof (≤ 4 inks) or the bundled `chromiq-gammap` helper (CMY+N). Four
engine-only rows appear in Build Profile → Manual under the heading
*Maximum accuracy (ChromIQ engine only)*: spectral physics model, ICC profile
version, measurement noise handling, out-of-gamut rendering.

## Referees — never the owner's measurements

* **The synthetic battery** (`python -m benchmarks.battery --candidates "" --out x.json`,
  then `--compare before.json after.json`): six analytic printers with exact
  ground truth; the promotion gates in `benchmarks/README.md` are binding.
  Two runs on this Mac take about 25 minutes in total.
* **colprof parity** through `xicclu` on the same `.ti3` (build both, look the
  chart's device values up through both A2B1, ΔE2000 median at the patches).
* **A real CMM**: littleCMS via `PIL.ImageCms`, ColorSync via `sips --matchTo`.
* **The ICC specification** (ICC.1:2022) for tag semantics.

Every `.ti3` under `~/ChromIQ` is developer test data — some measured wrong on
purpose. They are smoke inputs and robustness cases only, never a referee.

## What the challenge found and what changed (branch `feature/engine-accuracy-challenge`)

| finding | before | after |
|---|---|---|
| Paper white not pinned (both modes): A2B1(device white) L* 99.76/99.94, B2A1(L*=100) → RGB 0.996 — ink in every paper-white area | | A2B white 100.00 ±0.001, B2A 0.99999 (colprof 0.99996); local correction, B2A L axis ends at L*=100 like colprof's input curve, white node pinned |
| L*=0 printed RGB 3/4/18 (blue cast) | | black node pinned (device black for RGB, the inversion's own policy value for inks); the white corner node is set exactly (reviewer R1: the weighted correction fell short at heavy smoothing) and the XYZ-PCS grids now end at D50 so `-a x` profiles pin white too (reviewer R1b: 5 % CMY in paper white before) |
| Far out-of-gamut relative clip printed the COMPLEMENTARY hue on 5.7 % of nodes (colprof 0 %) | | hue-angle-gated seeds: 0.000 above 30° in every distance bin (colprof 0.014 in the far bin) |
| The cross-validated smoothing was a coin toss (×0.25 on the chart, ×4 on 90 % of it) and reported as a decision | | the SELECTION is unchanged — three alternatives (three splits, a keep-×1 margin, duplicate-aware splits) each helped one battery printer and cost another by 8–21 %, so none met the gate; the log now calls a win inside the test's scatter a near tie and names a pick at the ladder's end. A criterion that sees the print is open work |
| `-L` capped the TOTAL ink (colprof: black limit); no black limit at all | | `BuildSettings.black_ink_limit`, `BLACK_INK_LIMIT` from the chart, plumbed through every inversion pass and the written nodes |
| Observers 2015 2°/10° offered by the tab, refused by the engine | | CIE 170-2:2015 tables (CVRL); parity vs `colprof -o 2015_2` ΔE00 median 0.18 |
| `-u <scale>` half-applied what colprof refuses | | refused with colprof's own message |
| Outliers named by data row; nan/inf rows crashed with a numpy error; a stuck-instrument chart built a "successful" profile; a junk chart drew no verdict | | SAMPLE_LOC names; nan/inf refused naming the patches; white−black < 10 L* refused; fit median > 2 ΔE00 warns |
| `-s` mapped both tables; `-nP -nS` copied the perceptual table into saturation | | `sat_gamut`: with `-s` B2A2 aliases B2A0 (colprof.html) |
| gamut tag flagged two thirds of printable colours, and a 5–10 ΔE band inside the surface | | the tag subtracts a 6 ΔE margin like colprof's behaves (interior exactly 0: 32 % → 86 %; every point 5 ΔE inside under 1 ΔE); the distance far outside is understated by the margin |
| Every Argyll subprocess without a timeout; a quit mid-build orphaned colprof | | `_run_argyll` (timeouts, child registry, `terminate_argyll_children`), a quit question while a build runs |
| The scanner/camera tool always ran colprof, whatever Preferences said | | `engine_builder.choose_builder` shared by the tab and the tool; the engine prints colprof's "Profile check complete" line so the tool's misalignment verdict keeps working |
| The four engine rows leaked into a fresh run; Guided never named the mode; rebuilds overwrote the profile and its v4 twin in place | | `_restore_defaults` resets them; the bar says "ChromIQ engine · Maximum accuracy"; every rebuild archives to `old/` after the refusal checks and a failed build puts the previous profile back (reviewer R14) |
| Tooltip timings were inverted (fast "seconds", accurate "minutes longer") | | measured sentences (fast ~2 min, bit-exact ~1 min, accurate ~1 min at Medium on a 900-patch chart) |

Tried and withdrawn: averaging repeated patches before the fit
(`BuildSettings.average_duplicates`, now opt-in, default off) — it won on a
three-read chart but lost on the battery, whose charts repeat only white and
black.

## The smoothing choice, second round (agent C, 2026-09-05) — measured, nothing landed

The λ search in `accuracy.py` is still the shipped one. A candidate that
scored the fit it will actually use (the fold fits carrying the robust
weights), held every patch out once (5/3/1 folds by grid size), ran the
final fit's shaper rounds in the folds and judged by the root-mean-square
instead of the median was measured on the battery and failed the gate:
S4 −4 % on both medians but +4 % on A2B p95, S3 +3 % on the A2B median, S5
B2A +28 % with A2B flat, S3/S4 build time over 2×. The reason, in numbers
(`benchmarks/lambda_sweep.py` and `lambda_criteria.py`, new, and the proof
folder `reports/agent-C/`): on S4 the held-out mean square is 5.90 at ×2
and 5.95 at ×1 and ×4 — the bias the search looks for is 0.03 of it, the
rest is the reading noise's λ-independent constant, whose standard error
over 900 patches is ≈ 0.28. Adjacent ladder rungs differ by 1–5 % in the
truth on S3/S4, below what any statistic of 900 noisy patches resolves;
every criterion measured (median, RMS, p90, GCV, discrepancy, 1/5/10
folds) calls them near ties and settles them by its own noise, which the
2 % gate then reads as a loss on one printer and a win on another. Three
further facts for the next attempt: the ladder itself is nearly flat on
S1/S2/S3/S5 (A2B), so S2's loss to colprof (0.22 vs 0.14) is model
capacity, not λ; the RGB printers' B2A rows are owned by the B2A table's
interpolation (written profile 0.29/0.68 vs the inverted model 0.08/0.21);
and S5's B2A moves 28 % across factors its A2B cannot tell apart, so a
criterion for it has to look at the inversion, not the A2B residual.

## The black depth (agent D, 2026-09-05) — landed

The challenger's C3: Maximum accuracy's CMYK black was 1.5 L* lighter than
Fast's on the same chart, both exactly on the total ink limit. Measured on
the battery's CMYK printer (`reports/agent-D/`): the inversion's own
objective at L*=0 has its optimum at (0.66, 0.59, 0.55, K 1.0), true L*
9.9, and the solver delivered (0.75, 0.56, 0.75, 0.75), L* 14.8 — neither
the Euclidean-vs-proportional shape of the limit, `black_l` nor the K locus
(each worth ≤ 0.02 L*), but the limit being enforced by a projection AFTER
every Gauss–Newton step: a dark target drives every channel onto the 1.0
face, the projection subtracts a common amount from all of them, and the K
prior's pull is undone each iteration. `b2a._tac_face_step` now solves the
step ON the limit's face for the rows that would cross it (an equality-
constrained least-squares step; pinned columns stay out). Accurate mode
only (`tac_projection`); Fast is bit-identical (S1/S3/S5 hashes). Result:
S3 B2A1(0,0,0) L* 14.8 → 9.8 (Fast 13.5), S5 8.7 (Fast 11.2), the neutral
ramp below L* 20 monotone (it printed L*=0 lighter than L*=6), neutral-K
smoothness unchanged; battery B2A medians within ±1.1 %, every ink
printer's p95 2–4 % better, RGB printers untouched.
`tests/test_engine_accurate_black_reaches_its_ink_limit_depth.py`.

## Light inks (agent E, 2026-09-05) — measured, the separation NOT landed

S7 (CMYKcm, light cyan/magenta at 40 % of the parent dye) joined the
battery, with two referees every printer now reports: `highlight` (a
dedicated ≤ 40 %-coverage sample above L* 70 — the main grid holds 3
points in 6,000 up there on six inks, so A-20's "L* > 75 median" stood on
a handful) and `light_ink` (light-first fraction, ramp step; README).
`ti3_data.light_ink_parents` maps every light letter to the ink it
dilutes. The light/dark curve itself (`LightInkPolicy`, a per-iteration
prior that splits each pair's demand — light alone up to its peak, a
rounded handover, demand conserved — inert for every rep without light
inks, S1/S3/S5/S6 Fast bytes identical) does exactly what A-20 asked on
the ramp: light-first 0.01 → 0.98, C = M = 0 from L* 95 to ≈ 45, step
0.066, and it loses at the print: S7 B2A 1.02 → 1.42, highlight B2A
2.20 → 4.47 (`reports/agent-E/`, `light-ink-policy.patch`). The reason,
measured on the builder's own `-qm` model: it is 0.1 ΔE00 off at the
chart's c and m ramps and 0.14 on the CMYK face, and **5–8 ΔE00 between
them** — c+m alone 5.4, c+Y 6.5, the light corner C=M=K≈0 8.3 — because a
900-patch uniform fill puts ≈ 1 patch where C, M and K are all under
10 % and the multilinear grid extrapolates additively onto a halftone
face. HEAD's separation happens to live on the CMYK face the chart's
corners, ramps and grey support. A chart spanning all 2⁶ corners plus a
light-grey ramp does not close it (policy 3.57, HEAD on that chart
2.11), and no separation change can move the A2B half of the gate. The
next step is the model: fit a light channel as its parent's dye at a
lower density (two dilution curves on a four-ink grid), so the light
faces are supported by the parent's data — then re-apply the patch.

## Verdict on the mode itself (Agent A, A-06/A-07, unchanged by the fixes)

Maximum accuracy fits the chart patches tighter than colprof (median 0.05 vs
0.34 ΔE00) but on unseen patches it ties or loses to the Fast mode and to
colprof, and its B2A round-trip tail and neutral-ramp smoothness are not
better than Fast. It is the mode with the best hue-preserving clip and the
most honest log now; it is not yet a proven accuracy gain at the print. The
battery is the place to prove one.

## Still open (recorded, not fixed)

* A-20 light inks (CMYKcm): the hue gate zeroes light cyan/magenta on
  neutrals and highlights. The battery printer exists now (S7) and the
  design was built and measured — see the section below; the wall is the
  forward model, not the separation.
* B-32: the engine's build log is English in every UI language (the
  progress-prefix matching in `builder._STAGE_PCT` is on the English text).
* B-08: the remaining-time estimate cannot see inside colprof; it now says so.
* B-19: no way to make a second run from a measurement-only project.
* B-16: the per-target store overrides "Save as Defaults" after a restart —
  by the per-target rule, but nothing tells the user.
* A-14: the noise detector engages on every real chart (paper unevenness
  across the sheet counts as scatter); the wording now says so, the threshold
  is unchanged.

## Re-running the on-screen checks

`scripts/engine_challenge/harness.py` boots the real app against a sandboxed
settings store and working folder; `smoke_harness.py` builds the 924-patch
chart in Maximum accuracy on screen; `drive_B*.py` are the challenge's
journeys. Every launch sandboxes `CHROMIQ_SETTINGS_FILE`, `CHROMIQ_PRESETS_DIR`
and `custom_output_path`; nothing under `~/ChromIQ` is opened in place.
