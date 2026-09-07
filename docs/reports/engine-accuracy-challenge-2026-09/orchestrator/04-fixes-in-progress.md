# Orchestrator — fixes in progress (staged; appended as each lands)

Worktree: `/Users/Basti/develop/ChromIQ-fix` on branch `wip/engine-fixes`
(from d3d1bd43). The agents measure the FROZEN main tree; these fixes are merged
into `feature/engine-accuracy-challenge` only after both agents have reported.

## F1 — the paper white is pinned (critic N01/N07, plan S08) — DONE, measured
`builder._pin_media_white` (Argyll xfit.c "White point fine tune" method): look
the device white up through the fitted model, Bradford-adapt every grid node so
that lands on D50 exactly, take the fitted white (in the measured basis) as
`wtpt`. Real 924p chart, fresh processes (`builds/FIX-white-pin-924p.log`):

| | before | after |
|---|---|---|
| A2B1(device white), fast | L 99.756 | **100.0004 / 0.00003 / 0.00003** |
| A2B1(device white), accurate | L 99.936 | **100.0004** |
| wtpt Y, fast / accurate / colprof | 83.604 (brightest row) / 83.331 (mean) / 82.611 | **83.08 / 83.19** (fitted) |

## F2 — B2A L axis ends at L*=100 like colprof's (same finding, B2A half) — DONE, measured
colprof's B2A input curve scales L by 0xFFFF/0xFF00 (ratio 1.0039 measured on
its profile) so L*=100 is the top grid row; the engine's grid ended at 100.39
and interpolated white with the row below. `icc_writer.lab_b2a_in_tables` +
`lab_grid_axes` L axis 0..100. `builds/FIX2-white-pin-924p.log`:

| B2A(100,0,0) → RGB | before | after |
|---|---|---|
| relative, fast | 0.9976/0.9956/0.9960 | **0.99999/0.99996/0.99997** (colprof 0.99996) |
| relative, accurate | 0.9970/0.9954/0.9962 | **0.99999/0.99997/0.99997** |
| perceptual, accurate | 0.9949/… | **0.99995/0.99996/0.99995** |

## F3 — the B2A white NODE is pinned to device white — DONE (test), CMYK measured on synthetic
`refine_b2a_clut` refits the colorimetric table as a smooth field and the mapped
tables invert a mapped target: the white node came out C 0.6 % M 1.3 % Y 3.5 %
on a synthetic CMYK chart with F1+F2 in place. `b2a.pin_white_node` sets the
node(s) within 1 ΔE of (100,0,0) to device white, in the colorimetric path
(builder) and the mapped path (gamut_map).

## F4 — `-u` scales the FITTED white (critic N02) — DONE (test)
Was: one measured row scaled, then out-voted by its duplicates (fast: ×1.0;
accurate: ×0.979). Now: the grid is scaled by 1/scale and `wtpt` by scale, as
xfit.c does.

## F5 — every Argyll subprocess has a timeout (critic N20) — DONE
`gamut_map._run_argyll`: colprof 1800 s, xicclu 600 s; a timeout becomes
`OracleUnavailable("colprof did not finish within 30 minutes")`, which the
mapped-table path already turns into "Using the engine's own rendering (…)".

## F6 — outliers named by SAMPLE_LOC (plan S07) — DONE (test)
`Ti3Measurement.sample_ids/sample_locs/patch_label()`; the accurate-mode line
now reads "… — F20 (ID 757), W1 (ID 811). Consider remeasuring them."

## F7 — nan/inf readings refused with the patch names (critic N13) — DONE (test)
`read_ti3` raises `Ti3Error("…: 2 patch(es) have no usable reading (nan/inf) —
A8 (ID 8), A13 (ID 13). Re-measure them, or remove those rows, before building
a profile.")` instead of `ValueError: cannot convert float NaN to integer`.

Tests added: `tests/test_engine_pins_the_paper_white.py` (bytes through the
benchmark CMM replay + xicclu referee, fast and accurate, RGB and CMYK, `-u`),
`tests/test_engine_names_patches_the_way_the_sheet_does.py`. Existing pin
changed: `test_lab_grid_axes_span_legacy_range` → `…_end_at_white…` (it guarded
the bug). Engine test set round 3 running.

## Queued (waiting for the agents' numbers before deciding scope)
S01 `-L` = black ink limit (and BLACK_INK_LIMIT from the .ti3) · N03 observers
2015_2/2015_10 (route to colprof on ≤4 inks / clear error) · N05 `-s` vs `-S` ·
N12 twin `desc` · N04 oracle ink limit · scanner tool routing (A-Q3) · tooltip
timing text (S04/B-03) · Guided "which mode built this" (B-06) · engine rows'
home/visibility (B-02/B-05).

## F4 (revised) — `-u <scale>` is REFUSED like colprof, not scaled
Measured 2026-09-05: `colprof -ql -u 1.1` and `-u1.1` on printer data → "Input
auto WP scale mode isn't applicable to an output device", no .icc. The critic's
N02 premise (colprof honours -u for output profiles) was wrong. The engine's
extra-options parser now raises the identical error; `BuildSettings.wp_scale`
keeps xfit semantics (grid ×1/scale, white ×scale) but nothing in the tab can
reach it. Test: `test_hand_typed_u_scale_is_refused_exactly_like_colprof`.

## F8 — black ink limit (plan S01) — DONE (tests)
`BuildSettings.black_ink_limit`, `Ti3Measurement.black_ink_limit`
(BLACK_INK_LIMIT keyword, as colprof reads it), `-L` → black limit, `-l` →
total. Plumbed as a per-channel ceiling (`channel_max`) through seeding, both
Gauss–Newton passes, the retry cloud, the smooth refit's samples, the mapped
tables, and finally the written nodes (the refit overshot: K 0.65 for a 60 %
limit until the nodes were capped in curve space). Log line "Black ink limited
to 60%." Tests: `test_engine_black_ink_limit_and_2015_observers.py`.

## F9 — CIE 2015 observers (critic N03) — DONE (tests + parity)
`OBS_2015_2` / `OBS_2015_10` from the CVRL database (CIE 170-2:2015, 5 nm,
390–830). Parity on the real 924p chart vs `colprof -o 2015_2` / `2015_10` /
`-i D65 -o 2015_2`: ΔE2000 median 0.18–0.19 at 80 patches (the trusted
1964_10 path measures 0.19). Effect of the option: median 1.1 (2°) / 2.4 (10°)
ΔE00 vs 1931_2. `builds/FIX-observer-parity.log`.

## F10 — black corner pinned (A-04) — DONE (code), measurement running
`b2a.pin_black_node`: the L*=0 node(s) → the chart's deepest measured black
(device black for RGB), in the colorimetric table.

## F11 — hue-preserving clip that cannot flip hue (A-05) — DONE (code), measurement running
The first-order hue metric could not tell a colour from its complement (both
on one line through the neutral axis). Out-of-gamut nodes are now seeded from
a printable colour of the SAME HUE ANGLE (gate 6°, then 12°, 25°; score
(2·ΔL)² + ΔC² — lightness worth more than chroma), polished 4 GN iterations
under the hue-weighted norm, and the polish is dropped if it drifts > 10° or
gains > 3 chroma. Neutral targets keep the nearest clip. `gamt` unchanged.

## F12 — cross-validated smoothing needs a margin (A-07) — DONE (code)
Three hold-out splits (≤ 4 inks; one for CMY+N), mean criterion per factor;
a factor is chosen only if it beats the standard smoothing by more than
max(5 %, the across-split scatter); otherwise ×1 with the line "Smoothing: no
candidate beat the standard value by more than the test's own scatter (±x)
— keeping the standard smoothing." A pick at either end of the ladder says
"the end of the search range." The gp hill-climb uses the same splits and
margin.

## F13 — log lines (B-11, B-13, N12)
Spectral physics on an RGB chart now says "not applicable — this is an
RGB-driver chart (the inks are hidden). Standard model kept."; the bijective
renderer no longer also prints "matched to ArgyllCMS colprof" and drops the
"(candidate)" vocabulary; the v4 twin's description ends in " (v4)".

## 2026-09-05 (resumed) — landed on `feature/engine-accuracy-challenge`, rebased onto master 1b9cad54
Commits: 25120feb (batch 1), 3d7b90b8 (batch 2), 059632a0 (local white
correction, CV folds by grid size, colprof-shaped fit-check line, scanner-tool
chooser, grid-reduction line), ff7798c9 (UI: B-18 leak incl. kgen rows, B-06
mode label, B-05 heading, B-02 scroll-into-view, B-20 archive-on-rebuild +
twin, B-21 File guide row, B-03/B-04/B-01 tooltip and consent text, B-10 stale
sentence, B-25 quit guard + terminate_argyll_children), ac4e2f61 (B-26 scanner
routing through `choose_builder`; 17 i18n keys ×12, 5 stale removed).

**Battery (referee) after the local white correction** (`builds/battery-after2.log`
vs shipped): S1 0.088/0.089, S2 0.241/0.223 (+8 %), S3 0.238/0.242, S4 0.447/0.449,
S5 0.636/0.653 (better), S6 0.447/0.447. Two flags: S2 A2B +0.018 and S5 neutral-K
TV excess 0.10 → 0.38. Probes: the white-correction reach is NOT the S2 cause
(L60/C40, L80/C25, L90/C15 all 0.241; no-pin 0.241 too); the ink black pin is NOT
the S5 cause (identical 0.377 with the inversion's own value). Bisect of the CV
rule and duplicate averaging on S2/S5 running (`builds/battery-S5-bisect.log`).

Tests: engine set round 6 = 197 passed; UI tests 6/6; `tests/test_i18n.py` 87/87.
Reviewer agent launched on the fixes (brief `06-brief-reviewer.md`).
