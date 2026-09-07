# Agent D — findings (2026-09-05): the black depth of Maximum accuracy

Branch `feature/engine-accuracy-challenge`, baseline HEAD b94dd538. Referee
= the synthetic battery (`benchmarks/README.md`); every number below has
its script in `work-D/`. Nothing on the owner's drive was a tuning input.

## 1. Reproduce (work-D/black_diag.py S3 → diag/S3-m.json, HEAD)

Battery printer S3 (CMYK, 280 % limit), quality m, 900 patches, read
through the referee's CMM (`benchmarks.iccread`) and printed on the true
printer:

| | B2A1(0,0,0) device | Σ | true L* a* b* |
|---|---|---|---|
| fast | 0.829 0.409 0.733 0.829 | 2.80 | 13.54 −5.5 1.1 |
| accurate (HEAD) | 0.747 0.559 0.747 0.747 | 2.80 | 14.75 −1.9 1.9 |

Confirms C3 (1.2 L* here at -qm; the challenger's 1.5 was at -ql). Both
sit exactly on the ink limit. The neutral ramp in accurate mode was not
monotone either: requested L* 0/2/4/6/8/10 printed 14.75 / 13.5 / 12.2 /
11.1 / 11.3 / 11.8 — L*=0 printed LIGHTER than L*=6.

## 2. What is reachable (work-D/black_diag.py, black_oracle.py)

* Deepest black under the limit, true physics: (0.90, 0.90, 0.00, 1.00),
  L* 8.14; the chart's own black patch L* 8.39. Both modes were 5–6 L*
  above it — but that point is blue (b* −14), and the inversion's job is
  the NEAREST printable colour, not the darkest.
* **The optimum of the objective the solver claims to minimise**
  (|Lab − 0|² + the accurate K prior, under Σ ≤ 2.8), by dense search on
  the accurate model: **(0.661, 0.589, 0.550, K 1.000), model L* 9.47,
  true L* 9.94, a* 0.3, b* −1.4** — neutral, and 5.3 L* deeper than what
  the solver delivered. Same answer for targets L* 0, 4 and 8, with or
  without the prior. So the fault is the SOLVER, not the objective or the
  policy.

## 3. Which suspect (work-D/black_diag.py, lever isolation on the model)

Re-inverting the black corner through `invert_to_device` with one lever
changed at a time (true L* of the result):

| levers | K | true L* |
|---|---|---|
| parity path (accurate=False: prior 0.05, proportional scaling) | 0.782 | 13.31 |
| accurate as shipped | 0.747 | 14.75 |
| accurate, proportional scaling instead of Euclidean projection | 0.728 | 14.73 |
| accurate, black_l = None | 0.747 | 14.75 |
| accurate, K prior weight 0 | 0.891 | 12.60 |
| accurate, K prior 0 + proportional | 0.814 | 13.37 |

So: the projection's *shape* (Euclidean vs proportional) is worth 0.02 L*
— suspect 1 as named is not it; `black_l`/the locus (suspect 3) nothing;
the pin (suspect 2) faithfully copies the inversion's value. The 2.0
neutral firming of the K prior is what turns 13.3 into 14.75, and it does
so **through** the projection: the device values say why. Before the
projection C, Y and K all sit on the 1.0 face (the target is darker than
anything printable, every channel wants more); the Euclidean projection
subtracts one common θ = 0.253 from all of them → (0.747, 0.559, 0.747,
0.747). The prior pulls K to 1.0 in the solve, the projection takes it
back, every iteration. The TAC was never *inside* the solve.

## 4. The fix (workflow/profile_engine/b2a.py, accurate only)

`_tac_face_step`: for the rows whose clipped Gauss–Newton step would
cross the limit, re-solve the same damped least-squares step with the
equality constraint Σ(free, non-pinned channels) = limit − Σ(others)
(KKT: s = A⁻¹(b + μc), μ = (e − cᵀA⁻¹b)/(cᵀA⁻¹c), two solves per row
batch). Pinned columns from the boundary active set stay out of the
constraint with a zero step. `project_tac` still runs afterwards and now
only tidies clip rounding. Gated on `tac_projection`, which only accurate
mode sets — the parity/fast path does not execute a new line.

Prototype (work-D/gn_proto.py, proto_check.py S3 17 — invert the whole
grid-17 Lab grid on the same model):

| | in-gamut residual med / p95 / max | nodes > 0.1 | secs | black true L* |
|---|---|---|---|---|
| shipped | 0.000 / 0.076 / 0.803 | 14 | 2.6 | 14.75 |
| face step | 0.000 / 0.072 / 0.803 | 14 | 2.8 | 9.78 |

Nodes in gamut under both: 0 worse by > 0.05, 0 better. OOG clip distance
median 57.32 → 57.31. Through the real builder (diag/S3-m.json, after):

| | B2A1(0,0,0) | true L* a* b* | ramp L*0/2/4/6/8/10/12/14 printed | k_tv_excess |
|---|---|---|---|---|
| fast | 0.829 0.409 0.733 0.829 | 13.54 −5.5 1.1 | 13.5 12.6 11.4 10.7 11.5 12.5 13.4 14.7 | 0.0095 |
| accurate HEAD | 0.747 0.559 0.747 0.747 | 14.75 −1.9 1.9 | 14.8 13.5 12.2 11.1 11.3 11.8 12.3 13.8 | 0.0051 |
| accurate + fix | 0.683 0.602 0.514 **1.000** | **9.78** 0.4 −2.3 | 9.8 9.9 10.1 10.3 10.9 11.6 12.4 14.0 | 0.0051 |

3.8 L* deeper than Fast, 5.0 deeper than before, neutral (C* 2.3 vs Fast's
5.6), monotone, and the neutral-K smoothness metric unchanged.

## 5. The referee (builds/agentD-before.json → agentD-tacface.json)

| | A2B med | A2B p95 | B2A med | B2A p95 | rt p99 | k_tv_excess | s |
|---|---|---|---|---|---|---|---|
| S1 | 0.088 → 0.088 | 0.452 → 0.452 | 0.288 → 0.288 | 1.234 → 1.234 | = | – | 8 → 9 |
| S2 | 0.221 → 0.221 | 1.777 → 1.777 | 0.678 → 0.678 | 1.971 → 1.971 | = | – | 12 → 12 |
| S3 | 0.239 → 0.239 | 0.861 → 0.861 | 0.388 → 0.392 (+1.0 %) | 1.391 → 1.356 (−2.5 %) | | 0.005 → 0.005 | 9 → 10 |
| S4 | 0.431 → 0.431 | 1.265 → 1.265 | 0.528 → 0.530 (+0.4 %) | 1.604 → 1.543 (−3.8 %) | | 0.009 → 0.009 | 9 → 10 |
| S5 | 0.651 → 0.651 | 1.918 → 1.918 | 1.337 → 1.349 (+0.9 %) | 2.545 → 2.486 (−2.3 %) | | 0.102 → 0.102 | 310 → 333 |
| S6 | 0.446 → 0.446 | 1.606 → 1.606 | 0.852 → 0.843 (−1.1 %) | 2.118 → 2.038 (−3.8 %) | | 0.083 → 0.083 | 49 → 43 |

`--compare`: no class regresses > 2 % on any median or p95; p99s and
round-trip within jitter; k_tv_excess unchanged on S3/S5/S6; build time
≤ 1.1×. The verdict line reads "DO NOT PROMOTE: aggregate median
improvement −0.1 % < 5 %" — that is the gate for promoting a *candidate
set* into the mode; this change is a solver fault fix judged on the
task's own acceptance (medians/p95 not worse by the 2 % rule, k_tv_excess
≤ baseline + 0.05), which it meets. Where the +1 % on S3's median lives
(work-D/bin_compare.py, 20 k eval points): L* < 15 improves 0.971 → 0.927
(p95 1.777 → 1.695), the eval points on the ink limit improve 0.677 →
0.639 (p95 1.606 → 1.444), L* 15–25 +0.007 and neutrals C* < 10 +0.005
— the tail is what moved, the median shift is inside the scatter.

## 6. Fast mode bit-identity (work-D/fast_bytes2.py)

S1, S3, S5 built in `gammap_mode="fast"` at quality m with a fixed
timestamp from a `git archive HEAD` tree and from the working tree:
identical sha256 on all three (`cmp` clean). First attempt differed at
byte 144 — the `desc` tag carries the output file's stem; same file name
in two folders settles it.

## 7. The test (tests/test_engine_accurate_black_reaches_its_ink_limit_depth.py)

S3 chart, 400 patches, quality l, both modes: accurate black L* ≤ fast +
0.2, both on the ink limit; accurate K ≥ 0.97 at L*=0; the printed
neutral ramp L* 0…20 never gets lighter as the request gets darker.
Proven able to fail: with `_tac_face_step` replaced at runtime by the
unconstrained step (work-D/prove_test_fails.py) the first test fails
(see the run log in 02-summary).

## 8. Landed

Commit 37357e92 on `feature/engine-accuracy-challenge`: `b2a._tac_face_step`
+ the face-constrained branch in `_gauss_newton`, the test file, one
paragraph in `docs/dev_profile_engine_accuracy_challenge.md`. Everyday
tier 10542 passed / 278 skipped / 3 xfailed, exit 0 (builds/agentD-
everyday-1.log); engine set 88 passed, 5 skipped.

S5 (CMYKOG) through the real builder after the fix (diag/S5-after.log):
Fast B2A1(0,0,0) = (0.54, 0.88, 0.86, 0.88, 0.00, 0.04), Σ 3.20, true L*
11.17; accurate = (0.82, 0.18, 0.21, K 1.00, O 0.91, 0.00), Σ 3.12, true
L* 8.73, a* 0.3 b* 2.8; ramp 0…12 → 8.7 / 9.1 / 9.3 / 9.5 / 10.1 / 11.1 /
12.1, monotone.

## 9. Target 2 — the RGB B2A table's interpolation error: MEASURED, NOT LANDED

Anatomy on S1 (work-D/b2a_anatomy.py; quality m → **B2A grid 17**, not
33), B2A end-to-end median / p95 on 20 k eval points, interior = gamut
distance ≤ 0.5 (95 % of the points):

| stage | med | p95 | interior med |
|---|---|---|---|
| V0 written profile (referee) | 0.289 | 1.234 | 0.275 |
| V1 model inverted directly at the targets | 0.088 | 0.493 | 0.085 |
| V2 float replay of the shipped refit grid (no u16, exact out curves) | 0.290 | 1.234 | 0.275 |
| V3 per-node inversion grid, curve space (no refit) | 0.347 | 1.275 | 0.335 |
| V4 the same in device space | 0.347 | 1.275 | 0.335 |
| V5 refit λ 0.003 / 0.0003 / 0.3 | 0.291 / 0.291 / 0.286 | 1.244 / 1.244 / 1.190 | |
| V5 refit 90 k samples (3×) | 0.269 | 1.260 | 0.254 |

So: the output tables and 16-bit cost nothing (V0 = V2); the refit is
already worth 0.06 over raw nodes and λ/samples move it ≤ 0.02 (and the
median and the tail in opposite directions); V3 = V4 because the model's
shaper curves are the identity on S1 (`model.curves` linear), so all the
device non-linearity sits as curvature inside the cells. The 0.20 between
V1 and V2 is trilinear interpolation error in the INTERIOR of a 17-grid.

Two levers at the same grid size (work-D/b2a_geometry.py, in memory):

* Output curves d^p (grid stores g(device), out tables g⁻¹): p 1.2 →
  median 0.266 but p95 1.412 (+14 %); p < 1 worse on both. A wash.
* Input geometry: the a/b axes span −128…128 and S1's gamut reaches
  |a|,|b| 89.5 — 2.4 of the 16 cells per side hold nothing printable.
  Spending one cell per side beyond a gamut-derived edge (max |a|,|b| of
  the fitted model over the device cube + 4) → **median 0.204 (−30 %),
  p95 0.985 (−20 %)**; an L floor adds nothing worth its risk to the
  perceptual table's shadow resolution.

Through the WRITTEN bytes (work-D/geom_proto.py → benchmarks/
b2a_geometry_probe.py; mft2 input tables carry the mapping, so the
table sizes are colprof's):

| printer, outer cells | interior cell width (legacy 16) | B2A med | B2A p95 | round-trip med | outer band vs exact clip med / p95 |
|---|---|---|---|---|---|
| S1, 1 | 12.5 | 0.289 → 0.217 (**−25 %**) | 1.234 → 1.024 (−17 %) | −25 % | 0.41 / 8.6 → 0.79 / 10.2 |
| S1, 2 | 14.4 | −3.2 % | −3.6 % | −3.3 % | 0.43 / 8.7 |
| S1, 3 | 17.0 | +31 % | +19 % | +34 % | 0.36 / 8.1 |
| S2, 1 | 14.4 | 0.680 → 0.652 (**−4.2 %**) | +0.4 % | −4.9 % | 0.47 / 10.7 → 0.53 / 11.1 |
| S2, 2 | 16.6 | +14 % | +6.5 % | | |
| S3, 2 | 14.4 | −3.9 % | −4.2 % | −5.7 % | 0.34 / 5.0 → 0.34 / 5.2 |

A2B, k_tv_excess and hue keeping unchanged in every row (the codec is
B2A/gamt-side only; the mapped tables read it too, `gamut_map.py:905`).

Why not landed: the gate asks S1 AND S2 ≥ 5 % — S2's gamut is wider
(|a|,|b| 104), so the same cell budget buys it 4.2 %; and the far
out-of-gamut band, one cell wide, reproduces the exact hue-preserving
clip worse (S1 median 0.41 → 0.79, p95 8.6 → 10.2 — unprintable colours,
but a regression the battery's `oog_hue` at ×1.6 chroma does not see;
it improved, 0.98 → 0.85). No time left in the budget for a second
battery cycle on a variant. Not tried, next: an edge per axis SIGN (a
print gamut is asymmetric: −a reaches further than +a on S1), a mapping
whose outer cell keeps the legacy width and gives the interior the rest
(S1 would get ~13 units/cell, S2 ~15), and scoring the perceptual table
(B2A0 with a source gamut) on the outer band before promoting.
