# Reviewer — staged findings (appended per item)

Tree: `/Users/Basti/develop/ChromIQ` on `feature/engine-accuracy-challenge` @ ac4e2f61 (base 1b9cad54).
Scratch: `~/Desktop/ChromIQ-engine-challenge/work-R/`. Nothing in the repo was edited;
mutations for R18 are applied at runtime (monkeypatch plugin), never on disk.
All measurements offscreen / in-process unless a line says "ON SCREEN".

## R16 — i18n — OK
`python scripts/i18n_extract.py --missing <code>` for de es fr it ja nl no pl pt ru sv zh_CN:
"0 missing of 4859" for every one; `pytest tests/test_i18n.py` → 87 passed (32 s).
(German register and the timing sentences vs B-34: checked below under R16b once the
timings are re-measured from my own builds.)

## R1 — white pin — BUG (the local correction never reaches weight 1 at the white node)
`builder._pin_media_white` (workflow/profile_engine/builder.py:406-409) weights the correction
by `l_w = ((L−60)/40)²` and `c_w = 1 − C/40` evaluated at each node's OWN fitted Lab. The device-white
corner node is fitted at (L_w, a_w, b_w) ≠ (100,0,0), so its weight is `((L_w−60)/40)²·(1−C_w/40) < 1`
and the residual after the "pin" is `δ·(1−w)`. Small on a well-fitted chart, large as soon as the fitted
white error is large — which is exactly the case the pin exists for.
Repro `work-R/R1b.py` (battery S2 = matte, dot gain 0.70; bytes read through iccread AND xicclu):

| build | log: "model's white read L* … now …" | A2B1(device white) from the bytes | B2A1(100,0,0) |
|---|---|---|---|
| fast, -r 0.5 | 99.91 → 100.00 | 100.0004 / 0 / 0 | 1, .99999, .99999 |
| fast, -r 4 | 98.80 → **99.91** | **99.91 / 0.03 / 0.01** | .99999 .99999 .99998 |
| fast, -r 12 | 95.69 → **99.05** | **99.05 / 0.17 / 0.04** | .99995 .99986 .99983 |
| accurate, -r 4 | 93.28 → **97.71** | **97.71 / 0.63 / 0.21** | 1, .99999, .99998 |

`-r` is the Manual tab's Smoothing spin; the log line honestly prints "now 97.71" while the docstring,
the "Paper white anchored" wording and `tests/test_engine_pins_the_paper_white.py` (which builds only
well-fitted synthetic charts, L_w ≈ 99.9) all claim an exact pin. Because `b2a.pin_white_node` forces the
B2A side to device white regardless, the profile is then internally inconsistent: A2B(white)=97.7 but
B2A(100,0,0)=white. Fix: make the weight exactly 1 at the corner (evaluate the weight relative to the
fitted white, e.g. `l_w = clip((L − 60)/(L_w − 60))²`, or set the corner node to (100,0,0) after the
weighted correction). Real chart (924p, -r 0.5): fitted 99.756 → A2B1 99.9943 (fast 99.9958), inside
±0.02 — the bug is invisible there. S2 with a mis-measured white row (Y×0.94 on 1 of 9 whites): 99.9912
— averaging hides it. XYZ-PCS (`-a x`) and CMYK (S3) results: see the probe log `work-R/B/run.log`.

## R11 — child registry / timeouts — OK
`work-R/R11.py`: build (accurate, -S ClayRGB) in a thread; `terminate_argyll_children()` from the main
thread 2 s after colprof appeared → returned 1; the build ended 2.6 s later with the log line
"Using the engine's own rendering (colprof was stopped)." — no hang, the .icc was written, no leftover
`tmp*/…ti3` dir, `_LIVE_CHILDREN` empty afterwards.

## R14 — archive-on-rebuild — BUG (archives before the build is even allowed to start, never restores)
`ui/tabs/tab_profile.py:5134` calls `_archive_previous_build(params)` BEFORE the `engine == "blocked"`
check (5135) and with no restore on failure. `work-R/R14.py` (offscreen, real `TabProfile._on_build`):
* multi-ink chart, beta OFF → "Multi-ink measurement … colprof cannot build" dialog, and the run's
  `blocked.icc` is now `old/2026-09-05_031824/blocked.icc`; the run has NO profile.
* RGB chart, Argyll path bogus → "Profile Build Failed", `colprof-fails.icc` moved to `old/…`, run
  has NO profile. Before this change a failed rebuild left the previous profile untouched in place.
The scanner tool's own path (`_restore_archived_profile(stash)`) shows the intended pattern. Also:
`calibrated.icc` (applycal output of the archived profile) is not archived and stays, now stale.
Other R14 cases: verification present → `_archive_superseded_profile` runs first, so the second archive
finds nothing (no double archive, by code at 5297-5304); same-timestamp clash → `archive_to_old`
suffixes `_1` (core/file_manager.py:1920-1923). Guided vs Manual take the same `_on_build` path.

## R1b — white pin with an XYZ PCS (`-a x`) — BUG (ink in the paper white, every table)
`work-R/probe_B.py` + `probe_D.py`, battery S3 (CMYK), `algorithm="x"`, -qm, bytes via iccread and xicclu:

| build | A2B1(device white) | B2A0/1/2 (100,0,0) → CMYK | xicclu B2A1 |
|---|---|---|---|
| fast, XYZ PCS | 100.00 | **C 4.7 % M 4.4 % Y 3.5 %** K 0 | 4.7/4.4/3.9 % |
| accurate, XYZ PCS (XyzPcsShaped) | 99.99 | **C 5.5 % M 9.7 % Y 6.3 %** K 0.2 | 4.9/7.9/6.1 % |
| accurate, Lab PCS (same chart) | 99.99 | 0.002 % | 0.002 % |

Cause: `b2a.pin_white_node` pins "the node(s) within 1 ΔE of (100,0,0)" (b2a.py:706-726) — the XYZ grids
(`XyzPcs.node_lab`, `XyzPcsShaped.node_lab`, pcs.py:51-90) have no node at D50 white, so nothing is
pinned, and `lab_b2a_in_tables`' top-row trick is Lab-only (pcs.py:63-66 keeps identity for XYZ). The
gamt tag at (100,0,0) also reads 0.07 (non-zero) in the XYZ build. `-a x` is offered by the Manual
algorithm combo (tab_profile.py, see grep below) and accurate mode always uses the shaped XYZ layout
for it.

## R1c — kink — OK
Real 924p, fast, with and without the pin (runtime mutation, `probe_D.py`): neutral-ramp second
differences near L*60 identical (0.0963 both); max |d2| 0.2108 → 0.2189 at L*≈96 (paper's own
curve; colprof 0.1863 at 96.3). a/b sweep at L*93 through the neutral axis: |d2 a| 0.0027 vs
colprof 0.0013 — the C=0 cusp of `1−C/40` is measurable but 40× below Lab16 quantisation.

## R2 — B2A L-axis scaling — GAP (littleCMS reads the engine's white one 8-bit step darker than colprof's)
xicclu: B2A1(99.5)=0.996/0.993/0.994, (100)=0.99999/0.99996/0.99996, (100.39)=1.0/0.99998; gamt 0 at all
three — the in-table clips as designed. littleCMS (PIL.ImageCms, 8-bit LAB → RGB, `probe_D.py`):

| L8 (L*) | colprof rel | engine accurate rel | engine fast rel | perceptual (all three) |
|---|---|---|---|---|
| 255 (100) | 254,254,254 | **253,253,253** | 253,253,254 | 254 |
| 254 (99.6) | 253 | **252** | 252/252/253 | 253 |

lcms itself does not reach 255 for colprof either (8-bit Lab path), but the engine's relative table is
one step darker than colprof's through lcms while identical through xicclu. Not diagnosed further
(table geometry: see the in-table sizes noted in the summary); ColorSync not tested.

## R3 — hue-gated clip — OK on continuity; gap-of-hue path returns the nearest clip
S3 (CMYK) accurate: B2A1 at L*=2, 5, 98 for hues 0/90/200°, chroma 4.0/4.9/5.1/6.0: the step across
the C=5 gate (0.005–0.009 device) is SMALLER than the neighbouring 1-unit steps (0.025–0.039) — the
smooth refit erases the gate (`probe_B.py`). No-candidate-within-25° → `found=False` → the node keeps
the plain nearest clip (b2a.py:522-524) — no crash, but also no hue guarantee for a printer with a hue
gap; not exercised on a real gap. Ink limit + `channel_max` reach `_device_cloud` and the polish GN
(b2a.py:120-134) — verified by R5.

## R5 — black ink limit reaches every B2A table on a 6-ink chart — OK
`work-R/R5.py`: CMYKOG synthetic chart, `-L 40`, -ql, with the colprof CMYK proxy anchor AND -S mapped
tables, fast and accurate: K max over a neutral ramp + 3000 dark/saturated targets = 0.3996 / 0.3996 /
0.3996 (fast B2A0/1/2) and 0.3949 / 0.3994 / 0.3747 (accurate); no sample above 0.401. The path the
brief suspected (the `_seed_nearest` 5-point mesh for n>4, the proxy anchor) is covered by the final
`np.minimum(d, channel_max)` + GN clip. Not covered by construction: `joint_sep` (dark candidate, not
shipped) — `grep channel_max workflow/profile_engine/joint_sep.py` → nothing.

## R4/R6 — the S5 regression IS the duplicate averaging — BUG (mis-attributed in the handover)
`work-R/s5_avg.py` (S5 = CMYKOG, -qm accurate, ink_limit 320, scored by `benchmarks.battery.score_profile`):

| | A2B median | B2A median | k_tv_excess |
|---|---|---|---|
| `average_duplicates=True` (shipped) | 0.637 | **1.652** | **0.377** |
| `average_duplicates=False` | 0.651 | 1.335 | 0.127 |
| shipped baseline (battery-before) | — | — | 0.101 |

The orchestrator's own `builds/battery-S5-bisect.log` line "B no-avg: … k_tv_excess 0.127" already
said this; the handover blamed the CV margin / black pin. Mechanism: `collapse_duplicates`
(ti3_data.py:158-202) turns k identical readings into ONE row of weight 1 — the chart's repeats sit at
the cube's extreme points (12× white, 6× solid K, doubled corners in `make_chart`), which lose their
k-fold pull on the fit exactly where the model extrapolates; the docstring's "unbiased, noise/√k" is
true of the value and false of the weight. Fix: keep the averaged row but weight it by k in the fit
(the robust loop already carries per-row weights). Re-measured against the NEW uncommitted
`accuracy.py` (group-aware splits, best-mean rule): `work-R/S5b/run.log` (pending at the time of
writing; see summary).
Other R6 checks (code): kept row = `min(g)` so its SAMPLE_ID/LOC is the first occurrence (ok);
spectra averaged (ok); noise-model path skips (builder.py:392); `targ` embeds `meas.text`, untouched
(ok). Side effect not mentioned anywhere: `BuildResult.outlier_rows` and `fit_max_de/fit_mean_de`
are indexed/computed on the COLLAPSED rows — the scanner tool's "Profile check complete" now
describes fewer patches than colprof's on the same file.

## R17 — progress lines — OK (monotone), one stale anchor
Real 924p builds, raw lines replayed (`probe_B.py`): accurate 72 lines monotone 2→100, fast 53 lines
monotone. Accurate order: … Inverting → Writing → **Saturation table: matching colprof (40 %, ETA text
"colprof is running, its time is not counted")** → fitting (70) → building the final colour table (74).
Fast order: Gamut mapping 46/54/62 → final table 74 → "Saturation table: reusing" (anchored 40 but
printed at 74 — the monotone guard hides it) → final table again. No `tr()` slipped into a
`_STAGE_PCT` prefix (all f-strings, builder.py:236-263). "fine-tuning k/n" sub-steps do not occur in
these logs, so the backwards interpolation (next anchor 40 < 62) never fired.

## R7 — sanity gates — OK on the flat gate; the poor-fit WARNING wording is wrong for scanner charts (GAP)
`_sanity_gates` measures `lab_relative[white] − lab_relative[black]`; the relative white is 100 by
construction, so the gate is "darkest patch above L*rel 90". Newsprint (white ≈ 82 abs, black ≈ 25 abs →
span ≈ 60–70 relative) is nowhere near it; a single-ink/linearisation chart is the only thing that
trips it, and that is not a printer profile. Repro in `test_flat_measurement_is_refused` + mutation
(R18). The WARNING: on the real scanner-measured 315-patch chart (`work-R/probe_C.py`) the FAST build's
median is 3.29 ΔE2000 → "WARNING: the model fits this measurement poorly … damaged, mis-aligned or
from an instrument that did not read colour" fires on a legitimately aligned scan (accurate: 1.85, no
warning; colprof's own avg err 3.9 ΔE76 on the same file). That window now routes through the engine
(R13), so every Fast-mode scanner profile gets this line. The wording needs a scanner branch.

## R8 — ink limit capped at the chart's printed maximum — GAP (documented difference to colprof)
colprof.c:1147-1157 (Argyll 3.5.0 source): with a file limit and no `-l`, colprof uses **stamp − 10**
(when the stamp > 80 %), never looking at what the chart printed; with `-l` above the stamp it WARNS
and keeps the user's value. The engine now uses the chart's printed maximum when the stamp exceeds it
(builder.py:462-473) and, with a hand-typed `-l 350` on a 280 %-printed chart, silently overrides the
user (one log line). For a 300 % stamp / 280 % printed chart: colprof 290 %, engine 280 %; for a
280 % stamp: colprof 270 %, engine 280 % (no −10 rule at all). The log line is honest about what it
uses but does not say colprof would differ.

## R9 — -s / -S plumbing — OK
Guided (`_collect_guided_profile`, tab_profile.py ~5586/5598): `gamut_src` only when the combo data is
"s", `gamut_sat_src` only for "S"; Manual (5620-5621) identical; `settings_from_params` →
`sat_gamut = bool(params.gamut_sat_src)` (engine_builder.py:229). Extra options `-s`/`-S` set it too
(engine_builder.py:172). Old presets: `_m_apply_preset_data` reads `gamut_mode` with default "S"
(tab_profile.py:2267) — a preset saved before this change loads as before. Mutation (R18): forcing
`sat_gamut=True` inside `build_mapped_b2a` fails `test_lowercase_s_aliases…` (mutation proven landed,
wrapped 2×).

## R10 — gamt tolerance 3 ΔE — BUG (the tag flags printable colours up to ~10 ΔE INSIDE the gamut)
Battery S1 (RGB), true gamut surface = f_true(device-cube faces), points moved along chroma by k ΔE;
engine accurate -qm vs colprof -qm on the same chart (`probe_B.py`, `probe_D.py`):

| chroma offset from the TRUE surface | engine: gamt==0 / <1 / median | colprof: gamt==0 / median |
|---|---|---|
| −10 (inside) | 0.32 / 0.85 / 0.21 | 0.97 / 0.00 |
| −5 | 0.12 / 0.54 / **0.91** | 0.93 / 0.00 |
| −2 | 0.04 / 0.29 / **1.56** | 0.86 / 0.00 |
| 0 (on the surface) | 0.03 / 0.16 / 2.06 | 0.74 / 0.00 |
| +2 | 0.01 / 0.08 / 2.68 | 0.59 / 0.00 |
| +5 | 0.00 / 0.04 / 3.77 | 0.21 / 10.8 |
| random interior dev∈[.05,.95] | 0.65 / 0.96 / 0.00 | 0.99 / 0.00 |

The 3 ΔE node tolerance fixed the random-interior figure the test measures (65 %) but a soft-proof
gamut warning (lcms GAMUTCHECK, Photoshop) paints a band ~5–10 ΔE wide inside the gamut edge with the
engine's profile, where colprof's tag stays 0 down to 2 ΔE inside. It does NOT flag late (the brief's
worry) — it flags early. Cause: the tag interpolates the per-node inversion residual, and near the
surface the residual is non-zero on nodes that are in gamut (A2B on S1 is 0.09 ΔE median, so the
fitted gamut is not the reason). `test_gamut_tag_is_zero_for_printable_colours` cannot see this: it
samples the interior only.

## R13 — scanner-tool routing — GAP (thresholds calibrated on colprof's numbers; accurate mode's peak is 2× colprof's)
Same 315-patch scanner chart, offscreen builds (`probe_C.py`): colprof "peak err = 10.20, avg err =
3.95"; engine fast peak 9.84 / avg 4.01 (equivalent); engine ACCURATE peak **21.13** / avg 3.34 — the
robust fit down-weights the patches it names, so the peak at the patches doubles by construction.
`_selfcheck_verdict` passes when `peak ≤ 30 OR avg ≤ 12` (scanin_dialog.py:5356-5358), calibrated on
colprof (Knut's aligned build: peak 32.8). An aligned scan whose colprof peak is ~30 will read ~60
through Maximum accuracy and can only be saved by the avg branch. (A cyclic XYZ row shift is not a
misalignment on this chart — its rows are sorted by colour — so no misaligned repro; not on screen.)
Routing itself: `_printer_profile_builder` (scanin_dialog.py:5436-5457) mirrors `_resolve_engine`;
`EngineProfileBuilder` has `build/expected_icc_path/primary_failure/last_output` (engine_builder.py:
341-529). NOT covered: the quit guard only looks at `_tab_profile._engine_builder`
(main_window.py:2942-2943) — a build started from the scanner tool (`self._engine_profiler`) gets no
question, and `terminate_argyll_children()` still kills its colprof on quit. Test
`test_scanner_tool_builds…` is a source-text assertion: with `choose_builder` forced to
`("colprof","")` it still passes (R18).

## R15 — _restore_defaults and presets lacking keys — OK
`_m_apply_preset_data` reads every engine/kgen key with a default (tab_profile.py:2289-2300), so a
preset from before the rows existed loads with defaults; a run with nothing stored goes through
`_restore_defaults` (2233) which now resets the same rows (5852-5867). `tests/test_engine_challenge_
ui_fixes.py` 6 passed. Not driven on screen.

## R12 — quit guard — see the on-screen section below (R12 ON SCREEN)

## R18 — mutations (runtime monkeypatch plugin `work-R/mutate.py`, `mutate2.py`; log `work-R/mutations.log`, `mutations2.log`)
| mutation (what was reverted at runtime) | test | result |
|---|---|---|
| `pin_black_node` → identity | test_l_zero_prints_the_deepest_black | FAILS ✓ |
| `_pin_media_white` → no-op | test_device_white_lands_exactly… | FAILS ✓ (CMYK fast) |
| `pin_white_node` → identity | same | FAILS ✓ |
| `lab_b2a_in_tables` → identity | same | FAILS ✓ |
| `_CV_FOLDS = 1` | test_cv_search_ran_more_than_one_split | FAILS ✓ |
| `_channel_ceilings` → None | test_black_ink_limit_caps_the_k_channel_only | FAILS ✓ |
| 2015 observers removed | test_build_with_a_2015_observer… | FAILS ✓ |
| `collapse_duplicates` → (0,0) | test_repeated_patches_are_averaged… | FAILS ✓ |
| `_sanity_gates` → no-op | test_flat_measurement_is_refused | FAILS ✓ |
| `_v4_adaptation` → no chad | test_v4_under_d65_carries_chad… | FAILS ✓ |
| `sat_gamut` forced True in `build_mapped_b2a` (landed 2×) | test_lowercase_s_aliases… | FAILS ✓ |
| `choose_builder` → always colprof | test_choose_builder_follows_the_beta_switch | FAILS ✓ |
| **`_hue_gated_seeds` → finds nothing (nearest clip kept)** | test_far_out_of_gamut_relative_clip_keeps_the_hue_family | **PASSES** — the synthetic 6³ printer never flips under the plain nearest clip; the test pins the symptom, not the mechanism |
| **`_CV_MARGIN_FRACTION = 0`** | test_cv_smoothing_keeps_the_standard_value… | **PASSES** (old and new versions accept both branches) |
| **`_NAME_SCALE_FACTOR = 0`** | test_outlier_report_does_not_flood… | **PASSES** — flagged 16 vs 14 with the factor (`work-R/name_scale.py`); the flood fix is the neighbour check, the constant is inert here |
| **`choose_builder` → always colprof** | test_scanner_tool_builds_the_printer_profile… | **PASSES** — `inspect.getsource` assertion, blind to behaviour |
| ink-limit cap, poor-fit WARNING, gamt 3 ΔE | (literals inside `_build_profile_impl`) | not mutable at runtime; not proven |

## R4 (new uncommitted rule) — group-aware splits: fallback path is the common one
`work-R/straddle.py` replicates accuracy.py:158-180 on S5, real 924p, S3: the group sampler yields fewer
than `nho` rows in 6 of 9 splits, so `ho = argsort(rows_by_group)[:nho]` is taken — a plain row cut that
CAN straddle a repeated group (argsort is unstable on equal keys); 0 straddles measured on these three
charts (the cut fell between groups). With the new best-mean rule the shipped S5 numbers move:
`average_duplicates=True` → A2B 0.652 / B2A 1.611 / k_tv_excess **0.178** (was 0.377 under the
committed rule; baseline 0.101). `avg=False` under the new rule: see `work-R/S5b/run.log`.

## R4/R6 addendum — the S5 pair under the NEW (uncommitted) accuracy.py — still a K-smoothness regression
`work-R/S5b/run.log` (group-aware splits, best-mean rule; same chart, same scorer):

| | A2B median | B2A median | k_tv_excess |
|---|---|---|---|
| `average_duplicates=True` (shipped) | 0.652 | 1.611 | **0.178** |
| `average_duplicates=False` | 0.652 | 1.855 | 0.101 |
| shipped baseline (battery-before) | — | — | 0.101 |

The new rule flips the B2A verdict in averaging's favour (1.61 vs 1.86) but the neutral-K
smoothness still regresses 0.101 → 0.178, and `benchmarks/battery.evaluate_gates` fails S5 above
0.151 ("k_tv_excess > b + 0.05", battery.py:183-188). Under the committed rule it was 0.377 vs 0.127.
So: averaging is a real cause of the S5 K regression under BOTH rules; the weight-by-k fix (above)
is still the recommendation. Note the run-to-run baseline: the two `avg=True` numbers (0.377 old rule,
0.178 new rule) show the CV rule and the averaging interact — the orchestrator's battery-final numbers
should be read with both changes in mind, not attributed to one.

## R16b — register and tooltip timings — OK
German strings use Du ("Wenn du jetzt beendest, geht der Build verloren …"); all eleven new keys
present in de.json (checked by script). Accuracy tooltip now says Fast ≈ 2 min at Medium, Bit-exact
≈ 1 min / 2 at High, Maximum accuracy ≈ 1 min / 2.5 at High — consistent with B-34's measured
2 min / 45 s–2 min / 1–2.5 min. B-34's other item, the Quality combo's colprof-era "(~2 min)", is not
in this diff.

## R12 ON SCREEN — quit guard — OK (with two notes)
Driver `work-R/R12.py` on the real MainWindow (Fusion, real fonts, visible window on the built-in
Retina display at (0,66,1700,1050) — the display could NOT be photographed with `screencapture`, it
captures a different Space, so the proof is `QWidget.grab` of the dialog + the run folder).
A real Cmd-Q was NOT sent (an osascript keystroke went to Terminal, the frontmost app); `win.close()`
delivers the same `closeEvent` that Qt's cocoa termination path delivers on Cmd-Q.
* Manual, accurate, -S ClayRGB; at the "Saturation table: matching colprof" stage with colprof pid
  alive and `tmp…/oracle.ti3` present → `close()` → the question appeared (`quit-question-keep.png`):
  text "ChromIQ is still building a profile. If you quit now, the build is thrown away — nothing is
  saved until it finishes. / Keep building, or quit anyway?", buttons QUIT ANYWAY · KEEP BUILDING,
  default KEEP BUILDING. "Keep building" → window still visible, engine still running, and
  `Real-924.icc` (539 768 B) written 03:57, 95 s after the answer — the build finished.
* NOTE 1: `windowTitle()` of the box is '' on macOS (Qt drops QMessageBox titles there) and the box
  carries no icon at all (no `setIcon`, unlike the four other question boxes in main_window.py at
  1452/1869/2003/2045 which set `NoIcon` explicitly and draw ChromIQ's own sign) — the quit question
  is the only bare one. `test_the_warning_sign_is_ours_everywhere.py`: 6 passed (it bans the
  platform sign; it does not require ours).
* NOTE 2: the guard reads `_tab_profile._engine_builder` only — a build started from the
  scanner/camera tool (`ScannerProfileDialog._engine_profiler`, R13) gets no question.
* "Quit anyway" half: see the line below (appended when the run finished).
* "Quit anyway" (`work-R/R12/quit.log`): window hidden at t+0, colprof child gone, no
  `/var/folders/…/tmp*/oracle.ti3` left, `pgrep -f Argyll/bin/colprof` → 0 afterwards. The engine
  QThread itself is NOT stopped: it fell back to "the engine's own rendering", wrote `Real-924.icc`
  (539 768 B, 04:07) and raised the "Profile Built" dialog on the hidden window ~1 s later — visible
  only because the driver has no `app.exec()`; in the real app `main._hard_exit` ends the process
  when the last window closes. Worth knowing if quit ever stops calling `os._exit`.
