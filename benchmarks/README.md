# Engine evaluation harness (issue #123, W0)

Dev-only tooling — never imported by the app, never shipped.

## What it is

Candidate improvements to the **Maximum accuracy** engine mode land dark
behind tokens (`CHROMIQ_ENGINE_NEXT="ucs,joint-sep"` /
`BuildSettings.engine_candidates`). Nothing replaces the shipped accurate
mode until it provably wins here.

- `synthetic.py` — seven analytic spectral printers (S1–S7) where
  `f_true(device) → XYZ` is exact; instrument-noise + misread models.
  S7 is CMYKcm: light cyan/magenta are the parent dye at 40 % of the
  absorbance (`SyntheticPrinter.light_inks`) — a diluted primary, not a
  spot colour. S1–S6 are byte-identical to the six-printer battery.
- `battery.py` — builds a profile per printer and scores the **written
  bytes** against `f_true` on dense quasi-random points (ΔE2000):
  A2B accuracy, B2A end-to-end (profile ink printed on the true printer),
  round-trip, neutral-K smoothness, OOG hue keeping, outlier-flag F1,
  build time. Also evaluates the promotion gates.
  Two referees added with S7 (every printer reports them):
  `highlight.a2b/b2a` score the two legs on a dedicated light sample
  (`highlight_points`: Halton with every channel ≤ 40 % coverage, kept
  where the true printer renders L* > 70) — the main evaluation grid is
  TAC-projected over the whole cube and on six inks holds 3 points in
  6,000 above L* 70, so a highlight median from it means nothing.
  `light_ink` (light-ink printers only): `fraction` = the share of
  neutral-ramp (L* 5…95 at 0.5 steps, a = b = 0) + highlight targets the
  profile prints within 1 ΔE00 AND separates light-first — for every
  light/parent pair the pair is unused (< 2 % together), or the dark ink
  is ≥ 40 %, or the light ink carries at least as much as the dark one;
  `colour_ok` / `light_first` are the two halves on their own;
  `ramp_max_step` is the largest move of any channel between consecutive
  0.5 L* ramp steps (the "0 → 17.5 %" jump of A-20 reads ≈ 0.17).
- `iccread.py` — minimal mft2 CMM replay so the referee judges the file,
  not the in-memory model.
- `heldout.py` — the real-measurement secondary leg (90/10 held-out
  protocol, endpoints protected).

## Usage

```bash
python -m benchmarks.battery --candidates "" --out baseline.json
python -m benchmarks.battery --candidates ucs --out ucs.json
python -m benchmarks.battery --compare baseline.json ucs.json

python -m benchmarks.heldout ~/charts/*.ti3 --candidates ucs
```

## Promotion gates

A candidate set is promoted into the shipped accurate mode only when:

1. Synthetic battery: aggregate median ΔE00 improves **≥ 5 %**, no device
   class regresses **> 2 %** on median or p95, p99 / round-trip p99 not
   worse (beyond jitter; max is reported but not gated — the max of tens
   of thousands of noisy evaluations is a fragile order statistic).
2. Robustness: S4 misread F1 not worse; clean-chart false flags not up.
3. Smoothness: neutral K TV-vs-net not worse on S3/S5/S6.
4. Build time ≤ 2× the current accurate mode; full test suite green.
5. Real-measurement leg: no consistent regression across the corpus.
6. Light-ink printer (S7): the highlight A2B and B2A medians improve
   ≥ 25 %, `light_ink.fraction` rises, and `ramp_max_step` ≤ 0.08 (no
   jumps along the neutral ramp). A change to the separation alone can
   never move the A2B half — A2B is the model — which is the point: a
   light-ink win has to come with a model that is accurate where the
   light inks print (agent E, 2026-09-05).

## Interpretation rule (data-integrity policy)

Real-data ΔE00 median differences **below ~0.05 are noise** — never argue
from them. The synthetic battery decides ties. The owner's own
measurements are benchmark smoke tests only; **no constant, threshold or
curve may ever be tuned against them.** The battery definitions in
`synthetic.py` are fixed referees — do not tune them against a candidate.
