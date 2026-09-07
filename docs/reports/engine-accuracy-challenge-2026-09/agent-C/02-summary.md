# Agent C — summary (2026-09-05): a smoothing choice that sees the print

Branch feature/engine-accuracy-challenge @ ec1bf103 (baseline). Task: replace
the held-out-median λ selection in `accuracy.py` with a criterion that
predicts what reaches the print; referee = the synthetic battery, gate =
benchmarks/README.md. Everything measured is in 01-findings.md and
work-C/ (sweep-*.json, criteria-*.json, kfold-rms.diff, s5-pick.log).

## Verdict: no candidate passed the gate — the selection is NOT changed

Battery, before (builds/agentC-before.json) → candidate "kfold-rms"
(builds/agentC-kfold-rms.json):

| | A2B med | A2B p95 | B2A med | B2A p95 | build s |
|---|---|---|---|---|---|
| S1 | 0.088 → 0.088 | 0.452 → 0.452 | 0.288 → 0.288 | 1.234 → 1.234 | 9 → 14 |
| S2 | 0.221 → 0.221 | 1.777 → 1.777 | 0.678 → 0.678 | 1.971 → 1.971 | 13 → 18 |
| S3 | 0.239 → 0.245 (+2.9 %) | 0.861 → 0.862 | 0.388 → 0.382 | 1.391 → 1.381 | 9 → 25 |
| S4 | 0.431 → 0.412 (−4.4 %) | 1.265 → 1.315 (+3.9 %) | 0.528 → 0.500 (−5.3 %) | 1.604 → 1.528 | 10 → 28 |
| S5 | 0.651 → 0.650 | 1.918 → 1.925 | 1.337 → 1.709 (+27.9 %) | 2.545 → 3.396 (+33 %) | 329 → 360 |
| S6 | 0.446 → 0.446 | 1.606 → 1.606 | 0.852 → 0.852 | 2.118 → 2.118 | 44 → 90 |

`--compare`: DO NOT PROMOTE (S3 a2b median, S4 a2b p95, S5 b2a median+p95,
p99s, S3/S4 build time > 2×; aggregate median −5.3 %, i.e. worse).

The candidate: fold fits carrying the robust (Huber) weights the final fit
uses; every patch held out once (5/3/1 folds by grid size); fold fits at
the final fit's shaper rounds; statistic = RMS of held-out ΔE2000 over
non-rejected patches instead of the median. Each piece was motivated by a
measured fault (01-findings step 3), the tests for it were written and
proven to fail under one-line reverts (4/4), and the referee still said no.

Real-chart smoke (HEAD, builds/agentC-heldout-before.log): 924p held-out 92
patches median 0.819 / p95 1.796 / max 2.55; 1168p 116 patches median
0.358 / p95 0.980 / max 1.82. "After" = the same numbers: the shipped code
is unchanged (the candidate was not run on the real charts — they are not a
tuning target and the battery had already refused it).

## What the measurements say (the part worth keeping)

1. **The ladder has almost nothing to give.** Forced to each factor
   ×0.125…×16 through the real pipeline (work-C/sweep-*.json): S1, S3, S5
   are flat within 3 % at the A2B median; S2's best median (×2, −8 %) costs
   +27 % on the tail, so the gate pins it at ×1; only S4 (×4 → ×2, −5 % on
   both medians, +4 % / +12 % on the p95s) and S6's B2A (wants ×0.125,
   below the ladder) move. **S2 cannot reach colprof's 0.136 by any λ** —
   the best on the whole ladder is 0.204; that gap is model capacity (grid
   17 + per-channel shapers on a matte, dense, dot-gain-0.70 printer),
   with the error concentrated in L* > 60 (median 1–2 ΔE there).
2. **The weighting carries the accuracy, not λ.** The Huber step moves
   S1's true A2B from 0.120 → 0.086 and S2's from 0.278 → 0.221 at ×1;
   the plain fit and the weighted fit want different λ (×2/×8/×1 vs
   ×1/×2/×0.25 on S3/S4/S6), and the shipped search scores the plain fit.
3. **No chart-only criterion resolves the gate's 2 %.** On S4 the
   held-out mean square is 5.90 at ×2 and 5.95 at ×1 and ×4 — the bias the
   search is after is 0.03 of it, the reading noise's constant is the
   rest, and that constant's standard error over 900 patches is ≈ 0.28.
   Median, RMS, p90, GCV, whitened GCV, discrepancy, 1/5/10 folds
   (work-C/criteria-*.json, 01-findings) all call S3/S4 near ties and
   settle them by their own noise. That is the mechanism behind "helped
   one printer, cost another" in all four attempts so far.
4. **S5's B2A moved 28 % between factors its A2B cannot tell apart**
   (A2B 0.63–0.65 across the whole ladder): the candidate picked ×0.5
   (a named near tie, 1.45 vs 1.49) where the shipped rule picked ×0.25,
   and that one rung took the written B2A from 1.34 to 1.71. A criterion
   for the 6-ink printer has to look at the inversion; A2B residuals are
   blind to it.
5. **The RGB printers' B2A rows are the B2A table's, not the fit's**: the
   written profile's B2A is 0.288 / 0.678 (S1/S2) where the model inverted
   directly gives 0.084 / 0.213.

## What landed
Commit b94dd538 on feature/engine-accuracy-challenge: `benchmarks/lambda_sweep.py` (the λ oracle: force
each factor through the real pipeline, score against f_true, A2B + a
model-level B2A), `benchmarks/lambda_criteria.py` (every chart-only
criterion next to the oracle), and the paragraph on
`docs/dev_profile_engine_accuracy_challenge.md`. `accuracy.py` and the
smoothing tests are at HEAD; the full candidate diff is
work-C/kfold-rms.diff.

## Next idea (not started)
A criterion that sees the inversion, judged on S5 first: per factor,
invert a fixed in-gamut target set through the fold model and print it
through the OTHER folds' model (the only chart-only round trip that moves
when B2A moves and A2B does not); accept only if S5's B2A comes back to
≤ 1.34 without S4's tail moving. Independently: extend the ladder floor
to ×0.125 for S6's B2A, and look at the B2A table interpolation on the
RGB printers (bigger than any λ effect).
