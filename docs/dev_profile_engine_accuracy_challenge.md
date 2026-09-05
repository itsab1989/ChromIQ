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
| L*=0 printed RGB 3/4/18 (blue cast) | | black node pinned (device black for RGB, the inversion's own policy value for inks) |
| Far out-of-gamut relative clip printed the COMPLEMENTARY hue on 5.7 % of nodes (colprof 0 %) | | hue-angle-gated seeds: 0.000 above 30° in every distance bin (colprof 0.014 in the far bin) |
| The cross-validated smoothing was a coin toss (×0.25 on the chart, ×4 on 90 % of it) and reported as a decision | | the SELECTION is unchanged — three alternatives (three splits, a keep-×1 margin, duplicate-aware splits) each helped one battery printer and cost another by 8–21 %, so none met the gate; the log now calls a win inside the test's scatter a near tie and names a pick at the ladder's end. A criterion that sees the print is open work |
| `-L` capped the TOTAL ink (colprof: black limit); no black limit at all | | `BuildSettings.black_ink_limit`, `BLACK_INK_LIMIT` from the chart, plumbed through every inversion pass and the written nodes |
| Observers 2015 2°/10° offered by the tab, refused by the engine | | CIE 170-2:2015 tables (CVRL); parity vs `colprof -o 2015_2` ΔE00 median 0.18 |
| `-u <scale>` half-applied what colprof refuses | | refused with colprof's own message |
| Outliers named by data row; nan/inf rows crashed with a numpy error; a stuck-instrument chart built a "successful" profile; a junk chart drew no verdict | | SAMPLE_LOC names; nan/inf refused naming the patches; white−black < 10 L* refused; fit median > 2 ΔE00 warns |
| `-s` mapped both tables; `-nP -nS` copied the perceptual table into saturation | | `sat_gamut`: with `-s` B2A2 aliases B2A0 (colprof.html) |
| gamut tag flagged two thirds of printable colours | | nodes within 3 ΔE of the surface write 0 (interior zeros 32 % → 66 % at -qm) |
| Every Argyll subprocess without a timeout; a quit mid-build orphaned colprof | | `_run_argyll` (timeouts, child registry, `terminate_argyll_children`), a quit question while a build runs |
| The scanner/camera tool always ran colprof, whatever Preferences said | | `engine_builder.choose_builder` shared by the tab and the tool; the engine prints colprof's "Profile check complete" line so the tool's misalignment verdict keeps working |
| The four engine rows leaked into a fresh run; Guided never named the mode; rebuilds overwrote the profile and its v4 twin in place | | `_restore_defaults` resets them; the bar says "ChromIQ engine · Maximum accuracy"; every rebuild archives to `old/` |
| Tooltip timings were inverted (fast "seconds", accurate "minutes longer") | | measured sentences (fast ~2 min, bit-exact ~1 min, accurate ~1 min at Medium on a 900-patch chart) |

Tried and withdrawn: averaging repeated patches before the fit
(`BuildSettings.average_duplicates`, now opt-in, default off) — it won on a
three-read chart but lost on the battery, whose charts repeat only white and
black.

## Verdict on the mode itself (Agent A, A-06/A-07, unchanged by the fixes)

Maximum accuracy fits the chart patches tighter than colprof (median 0.05 vs
0.34 ΔE00) but on unseen patches it ties or loses to the Fast mode and to
colprof, and its B2A round-trip tail and neutral-ramp smoothness are not
better than Fast. It is the mode with the best hue-preserving clip and the
most honest log now; it is not yet a proven accuracy gain at the print. The
battery is the place to prove one.

## Still open (recorded, not fixed)

* A-20 light inks (CMYKcm): the hue gate zeroes light cyan/magenta on
  neutrals and highlights — needs its own design and a light-ink battery printer.
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
