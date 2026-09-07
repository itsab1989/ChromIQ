# Agent E — summary (2026-09-05): light inks — the separation is right, the model under it is not

Branch `feature/engine-accuracy-challenge`, baseline `4d1b714a`. Referee =
the synthetic battery with the new S7 printer (`benchmarks/README.md`).
Every number has a script in `work-E/`; the argument is in `01-findings.md`.

## What landed (commit `7204dbce`)

* `benchmarks/synthetic.py` — **S7**, CMYKcm: light cyan/magenta = the
  parent dye at 40 % absorbance (`SyntheticPrinter.light_inks`). S1–S6
  chart, measurement, evaluation points and truth hash identically
  against HEAD's file (`work-E/identity_synthetic.py`).
* `benchmarks/battery.py` — two referees on every printer: `highlight`
  (a dedicated ≤ 40 %-coverage sample above L* 70 — the main grid holds
  **3 points in 6,000** above L* 70 on six inks, so every highlight median
  taken from it so far, A-20's included, stood on a handful) and, for
  light-ink printers, `light_ink` (`fraction` = printed within 1 ΔE00 AND
  light-first; `ramp_max_step`); gate 6 in the README.
* `workflow/profile_engine/ti3_data.py` — `light_ink_parents`: `c/m/y/k`
  → the uppercase parent, `2c…` → the parent, `c` → `2c` when present,
  `1k` → `k` else `K`; spot inks untouched. Pure function + property; no
  engine behaviour changes in this commit.
* `tests/test_engine_light_inks_are_diluted_primaries.py` — 16 tests:
  the mapping, S7 is a diluted primary, the highlight sample, the metric's
  definition, and the Fast `-ql` bytes of S3/S5 pinned by sha256. Each
  proven to fail under one runtime mutation (`work-E/mutate.py`: 5/5
  red).
* `docs/dev_profile_engine_accuracy_challenge.md` — one section;
  `benchmarks/README.md` — S7, the referees, gate 6.

## What did NOT land — `light-ink-policy.patch` (b2a.py + ti3_data.py, 310 lines) and its tests

`b2a.LightInkPolicy`: per (light, parent) pair the model's own ramps give
the dark equivalent `t_eq(a)`; demand `t = d_parent + t_eq(d_light)`; the
curve puts the light ink alone up to its peak, fades it quadratically to
0 at full demand, dark = the rest — a soft minimum rounds the peak,
demand is conserved, so the prior pulls only along the metameric
direction. Applied inside every Gauss–Newton iteration (`prior_update`);
light blacks split the K locus statically; `from_model` returns None for
every rep without light inks, and S1/S3/S5/S6 Fast `-ql` bytes at a fixed
timestamp are identical between a `git archive HEAD` tree and the tree
with the patch (`work-E/identity_build.py`).

### S7 before / after (accurate, `-qm`, 900 patches, the same chart)

| | A2B med / p95 | B2A med / p95 | rt p99 | highlight A2B | highlight B2A med / p95 | light-first | colour_ok | ramp step | k_tv_excess |
|---|---|---|---|---|---|---|---|---|---|
| HEAD | 0.753 / 2.333 | **1.023** / 2.588 | 2.20 | 2.542 | **2.200** / 7.10 | 0.010 (lf 0.16) | 0.113 | 0.019 | 0.124 |
| policy | 0.754 / 2.331 | 1.422 / 3.439 (+39 %) | 3.42 | 2.553 | 4.470 / 8.47 (+103 %) | 0.010 (lf **0.976**) | 0.010 | 0.066 | 0.163 |
| gate | — | ≤ +2 % ✗ | ✗ | ≥ −25 % ✗ (cannot move) | ≥ −25 % ✗ | rises ✗ (the AND) | | ≤ 0.08 ✓ | ≤ +0.05 ✓ |

Neutral ramp (B2A1, L* 5…95 by 5): HEAD c = 0 up to L* 75 then 4.9/8.3/
8.3/4.9 %, m 9.4/17/17/9.4 %, C 57 → 7 %; policy c 74/86/83/69/53/52/53/
55/65/83/84/82/72/59/43/30/22/19/14 %, C 0 from L* 45 up, M 0 from L* 50
up — light-first, smooth, exactly the A-20 ask. And every one of those
neutrals prints 5–9 ΔE00 off.

### Why (measured on the builder's own `-qm` model, no B2A table in the way)

| device region | model vs truth, ΔE00 median |
|---|---|
| the chart's patches / its c and m ramps / its CMYK-only patches | 0.43 / 0.09, 0.07 / 0.14 |
| between patches: c+m only · c+Y only · c+C only · C+M only | 5.4 · 6.5 · 6.1 · 4.2 |
| the light corner C=M=K≈0, c,m < 1, Y < 0.5 | **8.25** (p95 11.4) |
| CMYK-only highlights (c=m=0, CMYK < 0.5) | 1.97 |

Direct inversion of the highlight referee: policy OFF lands at (C .23 M
.21 Y .24 c .01 m .01), end-to-end **1.45**; policy ON at (C .01 M .01 Y
.23 c .38 m .35), end-to-end **7.77** — model-space residual 0.000 in
both. A 900-patch uniform fill puts ≈ 1 patch where C, M and K are all
under 10 %, `make_chart` (and targen) span corners over four channels,
and the multilinear grid extrapolates additively onto halftone faces.
HEAD's CMYK-face separation happens to sit where the chart's corners,
ramps and composite grey support the model.

A chart spanning all 2⁶ corners plus a c/m/Y light-grey ramp (`work-E/
lightchart_probe.py`, `-qm`): policy highlight B2A 3.57, HEAD on that
chart 2.11 — the corners do not close it; the six-channel model at grid 9
cannot represent the light faces from 900 patches either way. The A2B
half of gate 6 cannot be moved by any separation change at all.

Secondary, in the patch: the raw per-node inversion is ragged at the cyan
handover (fixture model L* 47 → 44: c 0.96 → 0.30, residual 0 → 0.5 —
the moving prior unsettled in 10 iterations); the refit smooths the
written table. Worth a damped prior update when the model is fixed.

## S1–S6

No engine behaviour changed in what landed, so the battery on S1–S6 is
the baseline itself: `builds/agentE-before.json` (S1 0.088/0.288, S2
0.221/0.678, S3 0.239/0.392, S4 0.431/0.530, S5 0.651/1.349, S6
0.446/0.843 — agent D's `agentD-tacface.json` to the digit). With the
patch applied, S1/S3/S5/S6 Fast bytes are identical (sha256) and the
policy's code path is HEAD's for every rep without light inks.

## Tests and tiers

Engine set + the new file: 120 passed, 5 skipped (slow tier). Everyday
tier (`builds/agentE-everyday-1.log`): 10558 passed, 278 skipped, 3 xfailed, 5:52, exit 0.

## Next idea

The model, not the separation: fit a light channel as its parent's dye at
a lower density — two monotone dilution curves `t_eq_c(a)`, `t_eq_m(a)`
feeding a **four**-ink grid (`C' = C ⊕ t_eq(c)` with the halftone's
overlap term), so the light faces are supported by the parent's data
instead of extrapolated. That is one forward-model change, it removes the
6-D grid's 531k unknowns for a CMYKcm chart, and the patch here is the
B2A half already written and gated. Measure it with the same referee
first on S7's chart, then with a light-grey ramp added by Create Chart
for light-ink reps (targen has no light-pair patches either).

## Commits (feature/engine-accuracy-challenge, on 4d1b714a)

* `7204dbce` — S7, the two referees + gate 6, `light_ink_parents`, the 16 tests, the doc section. Everyday tier `builds/agentE-everyday-1.log`: 10558 passed, 278 skipped, 3 xfailed, exit 0.
