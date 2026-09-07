# Agent D — summary (2026-09-05): black depth landed; B2A geometry measured

Branch `feature/engine-accuracy-challenge`, baseline b94dd538. Referee =
the synthetic battery (`benchmarks/README.md`); Fast mode bit-identity
checked on S1/S3/S5 bytes; real charts smoke only. Details, every number
with its script: `01-findings.md`, `work-D/`.

## Target 1 — black depth in Maximum accuracy: LANDED

**Cause (not the suspect as named).** The Euclidean-vs-proportional shape
of the ink-limit projection is worth 0.02 L*; `black_l` and the K locus
nothing; the black-corner pin faithfully copies the inversion's value. The
fault is that the total ink limit was never *inside* the solve: every
Gauss–Newton step was projected onto Σ ≤ limit afterwards, which subtracts
a common amount from every channel — a dark target drives C, M, Y and K
all onto the 1.0 face, the projection hands back equal parts of each, and
the accurate mode's firm K prior (2.0 on neutrals) is undone each
iteration. The objective's own optimum at L*=0 on S3 is (0.66, 0.59, 0.55,
K 1.0), true L* 9.9; the solver delivered L* 14.8.

**Fix** (`workflow/profile_engine/b2a.py`, `_tac_face_step`, accurate
only): rows whose clipped step would cross the limit re-solve the same
damped least-squares step with the equality constraint Σ = limit (KKT,
two batched solves); pinned columns stay out. `project_tac` afterwards only
tidies clip rounding.

### Black L* (B2A1(0,0,0) → true printer physics, quality m, 900 patches)

| printer | Fast | accurate before | accurate after | Δ vs Fast | Σ ink (limit) | k_tv_excess before → after |
|---|---|---|---|---|---|---|
| S3 CMYK | 13.54 | 14.75 | **9.78** (K 1.00, a* 0.4 b* −2.3) | −3.8 | 2.80 (2.80) | 0.0051 → 0.0051 |
| S5 CMYKOG | 11.17 | (not measured at HEAD) | **8.73** (K 1.00, O 0.91) | −2.4 | 3.12 (3.20) | 0.102 → 0.102 (battery) |

Neutral ramp, requested L* 0/2/4/6/8/10/12 → printed (S3 accurate):
before 14.8 / 13.5 / 12.2 / 11.1 / 11.3 / 11.8 / 12.3 (L*=0 lighter than
L*=6); after 9.8 / 9.9 / 10.1 / 10.3 / 10.9 / 11.6 / 12.4, monotone.

### Battery (builds/agentD-before.json → agentD-tacface.json)

| | A2B med | A2B p95 | B2A med | B2A p95 | k_tv_excess | build s |
|---|---|---|---|---|---|---|
| S1 | 0.088 = | 0.452 = | 0.288 = | 1.234 = | – | 8 → 9 |
| S2 | 0.221 = | 1.777 = | 0.678 = | 1.971 = | – | 12 → 12 |
| S3 | 0.239 = | 0.861 = | 0.388 → 0.392 (+1.0 %) | 1.391 → 1.356 (−2.5 %) | 0.005 = | 9 → 10 |
| S4 | 0.431 = | 1.265 = | 0.528 → 0.530 (+0.4 %) | 1.604 → 1.543 (−3.8 %) | 0.009 = | 9 → 10 |
| S5 | 0.651 = | 1.918 = | 1.337 → 1.349 (+0.9 %) | 2.545 → 2.486 (−2.3 %) | 0.102 = | 310 → 333 |
| S6 | 0.446 = | 1.606 = | 0.852 → 0.843 (−1.1 %) | 2.118 → 2.038 (−3.8 %) | 0.083 = | 49 → 43 |

Acceptance: no B2A median or p95 worse by > 2 %, k_tv_excess ≤ baseline
+ 0.05, round-trip p99 within jitter — met. (`--compare` prints "DO NOT
PROMOTE: aggregate median −0.1 % < 5 %", the candidate-set promotion gate;
this is a solver fix, not a candidate set.) The +1 % medians on S3/S4/S5
are inside the scatter: binned on S3, L* < 15 improves 0.971 → 0.927
(p95 1.777 → 1.695) and the points on the ink limit 0.677 → 0.639, the
rest moves ≤ 0.007.

Fast mode: S1/S3/S5 built from a `git archive HEAD` tree and from the
working tree at a fixed timestamp — identical sha256, `cmp` clean.
Held-out real charts (924p / 1168p, RGB): 0.819/1.796/2.55 and
0.358/0.980/1.82, unchanged from agent C's baseline.

Tests: `tests/test_engine_accurate_black_reaches_its_ink_limit_depth.py`
(3 tests; proven red with `_tac_face_step` replaced at runtime by the
unconstrained step: accurate 15.02 vs Fast 12.95). Engine set 88 passed,
5 skipped. Everyday tier: see below.

**Landed:** commit `37357e92` (b2a.py, the test, one doc paragraph).
Everyday tier 10542 passed / 278 skipped / 3 xfailed, exit 0.

## Target 2 — the RGB B2A table's interpolation error: measured, NOT landed

Where it arises (S1, quality m → the B2A grid is 17, not 33): the written
profile's 0.289 vs the model inverted directly 0.088 is trilinear
interpolation error in the *interior* of the grid — not the output
tables or 16 bits (a float replay of the refit grid gives 0.290), not
the refit's λ or sample count (≤ 0.02 either way, median and tail moving
in opposite directions), and the shaper curves are the identity on S1,
so nothing is linearised. The refit is already worth 0.06 over raw nodes.

The lever at the same grid size is the a/b **geometry**: the legacy Lab
grid spends 2.4 of 16 cells per side on |a|,|b| > 90 where nothing
prints. Spending one cell per side beyond a gamut-derived edge (fitted
model's max |a|,|b| + 4; the mft2 input tables carry the mapping, table
sizes unchanged, the mapped tables read the same codec):

| written bytes | B2A med | B2A p95 | round-trip med | outer band vs exact clip |
|---|---|---|---|---|
| S1 | 0.289 → 0.217 (**−25 %**) | 1.234 → 1.024 (−17 %) | −25 % | med 0.41 → 0.79, p95 8.6 → 10.2 |
| S2 | 0.680 → 0.652 (**−4.2 %**) | +0.4 % | −4.9 % | 0.47 → 0.53 |
| S1 with 2 / 3 outer cells | −3 % / +31 % | | | (interior cells 14.4 / 17.0 vs legacy 16) |

A2B, k_tv_excess and hue keeping unchanged in every row. Not landed: S2
misses the ≥ 5 % gate (its gamut is wider, |a|,|b| 104, so the same cell
budget buys less), the one-cell outer band reproduces the exact clip of
unprintable colours worse, and the budget had no second battery cycle in
it. `benchmarks/b2a_geometry_probe.py` (additive) reproduces every row:
`python -m benchmarks.b2a_geometry_probe S1 --outer 1`.

## Next idea

Per-axis-sign edges (a print gamut is asymmetric) with the outer cell
kept at the legacy width and the interior taking the rest — S1 ≈ 13
units/cell, S2 ≈ 15 — scored on all six printers AND on the perceptual
table's outer band with a source gamut, before the battery. Separately,
S5's B2A median moved +0.9 % with the face step while its p95 fell 2.3 %:
the 6-ink separation's metameric freedom is now settled by the priors on
the ink-limit face too, which is where a criterion for S5 (agent C's
note 4) should look.

## Commits (feature/engine-accuracy-challenge, on b94dd538)

* `37357e92` — the face step in `b2a.py`, `tests/test_engine_accurate_black_reaches_its_ink_limit_depth.py`, the doc paragraph.
* `4d1b714a` — `benchmarks/b2a_geometry_probe.py` (additive; engine set 88 passed, tier 10542 passed before it).

Logs: builds/agentD-before.json/.log, agentD-tacface.json/.log,
agentD-engine-tests{,-2}.log, agentD-everyday-{1,2}.log,
agentD-heldout-after.log, agentD-geometry-probe-S1.log.
