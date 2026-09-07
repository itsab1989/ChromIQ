# Agent C — a smoothing choice that sees the print (findings, staged as I go)

Branch feature/engine-accuracy-challenge @ ec1bf103. Baseline battery:
builds/agentC-before.json (run from a HEAD snapshot in the scratchpad so my
edits cannot leak into it).

## Step 1 — the λ oracle (benchmarks/lambda_sweep.py, new, additive)

Force the maximum-accuracy fit to each factor of ×0.125…×16 and score the
fitted model against f_true (A2B ΔE00 at 8000 quasi-random points; B2A
end-to-end by inverting 300 in-gamut true targets and printing them on the
true printer). Chart-only statistics next to it: chart residual, whitened
residual (fit residual / duplicate-patch noise σ).

RGB printers (work-C/sweep-S1S2.json):

| | ×0.125 | ×0.25 | ×0.5 | ×1 | ×2 | ×4 | ×8 | shipped pick |
|---|---|---|---|---|---|---|---|---|
| S1 A2B med/p95 | .092/.457 | .088/.448 | **.085**/.450 | .086/.483 | .093/.553 | .105/.560 | .124/.825 | ×0.25 |
| S1 B2A med/p95 | .090/.536 | .089/.423 | .084/**.401** | .084/.452 | .089/.573 | .099/.624 | .120/.998 | |
| S2 A2B med/p95 | .252/**1.374** | .240/1.389 | .233/1.521 | .221/1.755 | **.204**/2.232 | .252/2.934 | .286/3.552 | ×1 |
| S2 B2A med/p95 | .259/**1.391** | .242/1.409 | .213/1.703 | .213/2.140 | **.197**/2.980 | .221/4.571 | .270/5.593 | |
| S2 whitened RMS | 2.9 | 4.5 | 6.6 | 7.7 | 10.9 | 12.2 | 17.7 | |

Reading:
* S1 is flat: every factor ×0.25…×1 is within 3 % at the median. Nothing to win.
* **S2 cannot reach colprof's 0.136 by any λ.** The best median on the whole
  ladder is 0.204 (×2) and that costs +27 % on p95 (the gate forbids it); the
  best p95 is at ×0.125 where the median is 0.252. The median and the tail
  pull λ in opposite directions, and the shipped ×1 sits at their compromise.
  The whitened residual is 7.7 at ×1 and still 2.9 at ×0.125 — the fit is
  MODEL-limited (grid 17 with per-channel shapers cannot follow the matte
  printer's dark-end curvature), not noise-limited, so the discrepancy
  principle has no root to find here: it would drive λ to the ladder floor
  and lose 14 % at the median. The S2 gap to colprof is a model-capacity
  question (colprof's grid/shaper for -qm RGB, see step 2), not a λ one.

## Baseline battery on HEAD ec1bf103 (builds/agentC-before.json, 6 printers, 50k eval points)

| | A2B med | A2B p95 | B2A med | B2A p95 | build |
|---|---|---|---|---|---|
| S1 | 0.088 | 0.452 | 0.288 | 1.234 | 9 s |
| S2 | 0.221 | 1.777 | 0.678 | 1.971 | 13 s |
| S3 | 0.239 | 0.861 | 0.388 | 1.391 | 9 s |
| S4 | 0.431 | 1.265 | 0.528 | 1.604 | 10 s |
| S5 | 0.651 | 1.918 | 1.337 | 2.545 | 329 s |
| S6 | 0.446 | 1.606 | 0.852 | 2.118 | 44 s |

Side finding: the WRITTEN profile's B2A on the RGB printers (S1 0.288, S2
0.678) is 3× the model-level inversion's (0.084, 0.213 in the sweep) — the
B2A table's own interpolation error, not the fit, owns the RGB B2A rows.
Not λ; recorded for the next person.

## Step 2 — which chart-only criterion predicts the oracle? (benchmarks/lambda_criteria.py, new)

Plain fit (no robust weights), per factor: the shipped single-split
held-out median, the mean over 5 splits, GCV (Hutchinson trace of the hat
matrix, no split), whitened GCV, and the discrepancy ratio
(work-C/criteria-S1S2.json). S1: oracle ×0.125 (0.097); the held-out
criteria and plain GCV pick ×0.25 (+17 %); whitened GCV and the discrepancy
principle pick the oracle. S2: oracle ×0.125 (0.274) — every criterion
picks it or lands within 1.5 %.

BUT the plain fit is not what ships, and the difference is the headline
of this step: the Huber robust weighting in `fit_forward_model_accurate`
moves the TRUE A2B error at ×1 from 0.120 → 0.086 on S1 and 0.278 → 0.221
on S2 (−28 %, −21 %). With this printer noise (dark patches 3–5× noisier
than light ones) the robust step acts as a crude heteroscedastic
weighting — it is the weighting, not the λ, that carries the accuracy on
the RGB printers. The gp (GLS-whitened) path, forced on, does NOT beat it
(S1 0.088 = 0.088; S2 0.231 vs 0.221) because its model-error floor and
the [0.2, 5] clip on the variance ratios pull it back toward equal
weights.

Consequence for the ladder: once the robust weights are in, the whole
×0.25…×2 span is worth ≤ 3 % at the median on S1/S2, and the S2 tail
forbids the one factor (×2) that would buy 8 % at the median.

## Step 3 — the robust pipeline's oracle (work-C/sweep-*.json; the fit the app ships, forced to each factor)

A2B median/p95 at 8000 true points; B2A = 300 true in-gamut targets inverted through the model and printed on the true printer.

| | ×0.125 | ×0.25 | ×0.5 | ×1 | ×2 | ×4 | shipped pick | oracle |
|---|---|---|---|---|---|---|---|---|
| S3 A2B | .286/1.03 | .262/.93 | .243/.86 | **.240**/.86 | .249/.92 | .303/1.20 | ×1 | ×1 |
| S3 B2A | .275/1.22 | .242/1.14 | .225/1.06 | **.214/.96** | .232/1.07 | .258/1.30 | | |
| S4 A2B | .631/2.55 | .571/2.16 | .507/1.83 | .446/1.51 | **.412**/1.32 | .432/**1.28** | ×4 | ×2 (median) |
| S4 B2A | .576/2.53 | .529/2.26 | .474/1.90 | .424/1.50 | **.396**/1.35 | .417/**1.21** | | |
| S5 A2B | .638/1.92 | .649/1.92 | .645/1.93 | .648/1.99 | **.627**/1.99 | .640/2.09 | ×0.25 | flat (±2 %) |
| S6 A2B | **.444**/1.55 | .443/1.59 | .477/1.70 | .539/1.94 | .617/2.27 | .685/2.58 | ×0.25 | ×0.125–0.25 |
| S6 B2A | **.846/1.88** | .985/1.96 | 1.127/2.12 | 1.285/2.39 | 1.466/2.94 | 1.576/3.34 | | (below the ladder) |

So the ladder has real money on exactly one printer, S4 (×4 → ×2: −5 %
median on both legs, but +4 % / +12 % on the p95s), and S6 wants a factor
BELOW the ladder for its B2A. S1/S2/S3/S5 are flat or gate-locked.

Two structural faults in the shipped criterion, both measured (work-C/
criteria-*.json and the scratch runs recorded in 02-summary):

1. **It scores the wrong fit.** The training-split fits were UNWEIGHTED
   and the winner was handed to the Huber-weighted fit; the two want
   different λ (unweighted oracle ×2/×8/×1 on S3/S4/S6 vs ×1/×2/×0.25
   weighted).
2. **The median is blind while noise exceeds bias.** A held-out residual
   is bias + reading noise. The mean square is the one statistic where
   the noise adds a λ-independent constant; the median of |bias+noise|
   barely moves (S4, 5 folds: 1.01–1.07 across the ladder against a
   truth that moved 0.63 → 0.41) and picked ×0.25 where the truth wanted
   ×2. Pooled 5-fold RMS picked ×2 on S4, ×0.5–×1 on S3, ×1 on S2, ×0.25
   on S1, ×0.125 on S6 — every one at or within 2 % of the oracle.
   A third, smaller effect: the fold fits used ONE shaper round where the
   final fit uses two; the under-fitted shapers at ×1 were blamed on λ
   (S2: ×0.25 for +9 % true error with one round, ×1 with two).

Tested and rejected on the way: excluding the chart's structured rows
(ramps, greys, corners, duplicates) from the held-out pool — S3's pick
did not move (the fill-only median still said ×0.25); GCV (Hutchinson
trace) — no better than the split on the plain fit (S1 +17 %, S3 +15 %);
whitened GCV and the plain discrepancy principle — both drive λ to the
ladder floor wherever the fit is model-limited (S2, S3: the whitened
residual never reaches 1).

## Candidate "kfold-rms" (accuracy.py): weighted fold fits, every patch held out once (5/3/1 folds by grid size), RMS ΔE2000 over the non-rejected held-out patches, fold fits at the final fit's curve rounds. Ladder, log lines, determinism unchanged; no new option.

Model-level check (pipe_check): S1 ×0.25 (=), S2 ×1 (=), S3 ×0.5 (A2B
.243/.860 vs .240/.864, a named near tie), S4 ×2 (A2B .412/1.323 vs
.432/1.276; B2A .396/1.350 vs .417/1.208), S6 ×0.25 (=). Battery running
as builds/agentC-kfold-rms.json.

## Step 4 — the referee's verdict on "kfold-rms" (builds/agentC-kfold-rms.json vs agentC-before.json)

| | A2B med | A2B p95 | B2A med | B2A p95 | build |
|---|---|---|---|---|---|
| S1 | 0.088 (=) | 0.452 (=) | 0.288 (=) | 1.234 (=) | 14 s |
| S2 | 0.221 (=) | 1.777 (=) | 0.678 (=) | 1.971 (=) | 18 s |
| S3 | 0.245 (+2.9 %) | 0.862 (=) | 0.382 (−1.5 %) | 1.381 (−0.7 %) | 25 s (was 9) |
| S4 | 0.412 (−4.4 %) | 1.315 (+3.9 %) | 0.500 (−5.3 %) | 1.528 (−4.7 %) | 28 s (was 10) |
| S5 | 0.650 (=) | 1.925 (=) | **1.709 (+27.9 %)** | **3.396 (+33 %)** | 360 s |
| S6 | 0.446 (=) | 1.606 (=) | 0.852 (=) | 2.118 (=) | 90 s (was 44) |

`--compare`: REGRESS S3 a2b median +2.9 %, S3 roundtrip p99, S4 a2b p95
+3.9 %, S4 a2b/roundtrip p99, S5 b2a median +27.9 % and p95 +33 %, S3/S4
build time > 2×; aggregate median −5.3 %. **DO NOT PROMOTE.** The
selection change is NOT committed (rule: no candidate passed the gate).

Why no chart-only criterion can pass this gate, in numbers: on S4 the
held-out mean square is 5.90 at ×2, 5.95 at ×1 and ×4 — the bias part
the search is looking for is 0.02–0.03 of it, the rest is the reading
noise's λ-independent constant, and the standard error of that mean
square over 900 held-out patches is ≈ 0.28. The truth differences between
adjacent ladder rungs on S3 and S4 (1–5 %) are below what any statistic of
900 noisy patches can resolve; every criterion I measured (median, RMS,
p90, GCV, discrepancy, 1/5/10 folds) calls S3 and S4 near ties and
resolves them by its own noise, which the referee then reads as a
+3 % loss on one printer and a −5 % win on another. That is the same
"helped one printer, cost another" pattern the three earlier attempts hit,
now with the reason. S5's B2A is the exception: its A2B is flat across the
whole ladder (0.63–0.65) while its B2A moved 28 % — a factor the fit
cannot see from A2B residuals at all, so a criterion for S5 must look at
the inversion. The candidate picked ×0.5 on S5 (work-C/s5-pick.log: held-out RMS 1.45 vs
1.49 at ×1, a named near tie) where the shipped rule picked ×0.25 — one
rung, A2B 0.645 vs 0.649 in the sweep, and the written profile's B2A
moved 1.34 → 1.71.

## What is committed (b94dd538)
Only the additive benchmark tools (`benchmarks/lambda_sweep.py`,
`benchmarks/lambda_criteria.py`) and a paragraph on the developer page;
`accuracy.py` and the smoothing tests are back at HEAD. The full candidate
diff is kept as work-C/kfold-rms.diff for the next attempt.

## Exact next step
A criterion that sees the inversion, judged on S5 first: for each ladder
factor invert a fixed in-gamut target set through the fold model and
score the round trip THROUGH THE HELD-OUT PATCHES' measured colours
(print the inverted device value with the *other* folds' model, compare
to the target) — the only chart-only quantity that moves when B2A moves
and A2B does not. Budget: S5's B2A is the metric to watch, A2B will not
tell. Also open: the ladder floor for S6 (its B2A wants ×0.125, below the
ladder) and the RGB B2A rows, which are the B2A table's interpolation, not
the fit.
