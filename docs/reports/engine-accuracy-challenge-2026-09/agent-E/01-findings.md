# Agent E — light inks (A-20): findings, staged as measured

Branch `feature/engine-accuracy-challenge`, baseline HEAD `4d1b714a`.
Referee: the synthetic battery (`benchmarks/README.md`) with the new S7
printer. Every number below has a script under `work-E/` (copied from the
session scratchpad at the end) or a battery JSON under `builds/`.

## E-01 — S7, a CMYKcm printer, is in the battery (landed, additive)

`benchmarks/synthetic.py`: `SyntheticPrinter.light_inks` — a lowercase
COLOR_REP letter is its uppercase parent's dye at a fraction of the
absorbance (`("c", 0.40), ("m", 0.40)` for S7; `1k`/`2k` dilute K).
Nothing else about the printer model changes: S1–S6's chart, measurement,
misread rows, evaluation points and ground-truth Lab hash identically
under HEAD's `synthetic.py` and the new one (sha256 of the arrays,
`work-E/identity_synthetic.py`). The light-cyan solid prints at
L* 82.0 a* −22.8 b* −29.4; 40 % dark cyan at 81.8 / −19.9 / −29.7 — a
diluted primary, the same hue, 3 ΔE apart in the halftone (a solid light
dye is not exactly a 40 % dark halftone; that is real).

## E-02 — the battery's highlight set was empty (fixed in the referee)

The main evaluation grid is a TAC-projected Halton set over the whole
device cube: on six inks it is almost entirely dark. Measured: **3 of
6,000** evaluation points on S7 have true L* > 70, so any "highlight
median" taken from it — A-20's "L* > 75 median 6.03" on a 20,000-point
set included — rests on a handful of points. `battery.highlight_points`
now draws a dedicated sample (Halton with every channel ≤ 40 % coverage,
kept where the true printer renders L* > 70; 1,768 points for S7 at the
default budget) and every printer reports `highlight.a2b/b2a`. The
light-ink metric `light_ink.fraction` (README) is the share of neutral-
ramp (L* 5…95 at 0.5) + highlight targets printed within 1 ΔE00 *and*
separated light-first (dark ink ≥ 40 %, or light ≥ dark, or the pair
unused). `ramp_max_step` is the largest channel move between ramp steps.

## E-03 — baseline on HEAD (builds/agentE-before.json, re-scored with the final referee)

| | A2B med/p95 | B2A med/p95 | highlight A2B | highlight B2A | light-first | colour_ok | ramp step | s |
|---|---|---|---|---|---|---|---|---|
| S7 CMYKcm | 0.753 / 2.333 | 1.023 / 2.588 | 2.542 | 2.200 | **0.010** | 0.113 | 0.019 | 323 |

S1–S6 reproduce agent D's `agentD-tacface.json` to the digit. On S7's
neutral ramp HEAD prints c and m at 0 from L* 5 to 75 and then 4.9 → 8.3
→ 8.3 → 4.9 % (c) / 9.4 → 17 → 17 → 9.4 % (m) at L* 80–95 while C runs
57 → 7 % — the A-20 picture, now on the battery.

## E-04 — the light channel mapping (landed, `ti3_data.light_ink_parents`)

`c/m/y/k` → the uppercase parent; `2c/2m/2y/2k` → the parent; `c` → `2c`
when the printer has one; `1k` → `k`, else `K`. Spot inks untouched:
`CMYKOGcm` → {6: 0, 7: 1}. `extra_ink_hues` skips light channels — the
light-cyan solid no longer becomes "a 232° cyan hue" for the hue gate.

## E-05 — the light/dark policy (`b2a.LightInkPolicy`): correct on the ramp, loses at the print

Design: per (light, parent) pair the model's own ramps give the dark
equivalent `t_eq(a)` of light coverage `a` (nearest Lab on the parent's
ramp; `t_eq(1) ≈ 0.4` on S7). Demand `t = d_parent + t_eq(d_light)`; the
curve puts the light ink alone up to its peak (`t_eq(a) = t`), then fades
it quadratically to 0 at `t = 1`, dark `D = t − t_eq(a)` — a soft minimum
joins the branches, demand is conserved, so the prior only pulls along
the metameric direction. Applied inside every Gauss–Newton iteration
(`prior_update`), because the demand is a property of the solution; a
light black splits the K locus statically. Inert for RGB/CMYK/CMYKOG/
CMYKV: `from_model` returns None and the code path is HEAD's.

Byte identity, Fast mode, `-ql`, fixed timestamp, `git archive HEAD` tree
vs working tree: S1 `dec82909…`, S3 `44a051ab…`, S5 `8fa70ddf…`, S6
`b2a45357…` — identical (`work-E/identity_build.py`).

**On the ramp it does what A-20 asked** (direct inversion of the builder's
model, `-ql`): light-first fraction 0.62 → 0.99, c/m carry the neutrals
from L* 95 down to ≈ 45 with C = M = 0, the written profile's ramp step
0.048 (gate 0.08), k_tv_excess 0.14 → 0.04.

**At the print it loses, and the reason is not the separation.** The
builder's own model (accurate, 900 patches), scored against the truth by
device region (`work-E/model_support.py`, `dissect.py`):

| device region | model error ΔE00 med (p95) |
|---|---|
| the chart's own patches | 0.43 (1.31) |
| the c ramp / m ramp patches | 0.09 / 0.07 |
| CMYK-only patches (c = m = 0) | 0.14 |
| **between patches**: c+m only, nothing else | **5.4** |
| c+Y only | 6.5 |
| c+C only (the pair itself) | 6.1 |
| C+M only (for comparison — also a two-ink face) | 4.2 |
| the light-ink corner C=M=K=0, c,m < 1, Y < 0.5 (`-qm` model) | **8.25 (11.4)** |
| CMYK-only highlights c=m=0, CMYK < 0.5 (`-qm`) | 1.97 (3.5) |

A 900-patch uniform fill puts ≈ 1 patch where C, M and K are all under
10 %, and `make_chart` (like targen) spans corners over the first four
channels only, so the multilinear model *extrapolates* onto every face
the light inks live on — additively, and a halftone is not additive.
HEAD's separation happens to live on the CMYK face, which the chart's
corners, ramps and composite grey support. Inverting the highlight
referee through the `-qm` model directly (no B2A table in the way):

| policy | mean device (C M Y K c m) | model-space residual | end-to-end ΔE00 med (p95) |
|---|---|---|---|
| OFF (HEAD) | .23 .21 .24 .00 .01 .01 | 0.000 | **1.45** (4.3) |
| ON, peak 1.0 | .01 .01 .23 .00 .38 .35 | 0.000 | 7.77 (9.7) |
| ON, peak 0.6 | .04 .03 .23 .00 .33 .30 | 0.000 | 7.21 (8.8) |
| ON, weight 2 / 0.1 (`-ql` model) | | | 2.11 / 1.62 whole-gamut vs OFF 1.11 |

The solver reaches the target colour *in the model* in every row; the
printer disagrees by 5–9 ΔE00 wherever the light inks are used. No
separation policy can pass a B2A gate on this chart, and no separation
change can move the A2B half of the gate at all (A2B is the model).

Secondary: the per-node inversion is ragged at the cyan handover
(fixture model, L* 47 → 44: c 0.96 → 0.30, C 0.02 → 0.45, residual 0 →
0.5 ΔE76 — the moving prior has not settled in 10 iterations there); the
refit smooths the written table (ramp step 0.048) but the raw field is
not smooth. Would need more iterations or a damped prior update; not
pursued once the model wall was measured.

## E-06 — does a chart that spans the light corners close it? (`-ql`, not landed)

`work-E/lightchart_probe.py`: the same 900 patches with all 2⁶ corners
and a c/m/Y light-grey ramp instead of 60 fill points. At `-ql` (model
grid 5, which cannot represent much either way): highlight B2A 3.75 →
3.13 with the policy (HEAD on the generic chart 3.14). The `-qm` builds
(policy + light chart, HEAD + light chart, policy + generic chart) are
recorded in `02-summary.md`.
