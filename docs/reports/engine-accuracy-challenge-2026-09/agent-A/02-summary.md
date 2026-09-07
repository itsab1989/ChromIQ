# Agent A — summary (colour-science referee)

Full evidence: `reports/agent-A/01-findings.md` (every number with its command); scripts and every built profile in `~/Desktop/ChromIQ-engine-challenge/work-A/`. No repo file edited. Measurement window 2026-09-04 23:40 → 2026-09-05 00:30 (~110 builds).

## Findings

| # | item | grade | one-line repro |
|---|---|---|---|
| A-01 | Determinism on the colprof-oracle path | OK | two fresh `build.py --mode accurate --q m` → md5-identical (`builds/det/`) |
| A-02 | Real-CMM leg (xicclu vs littleCMS vs ColorSync) | OK for perceptual/relative (≤ 0.01 ΔE); absolute differs 0.2/0.8 ΔE *identically* for colprof (CMM-level) | `cmm_probe.py builds/e924-acc-qm.icc` |
| A-03 | White pinning: A2B1(white) = L 99.94 (acc) / 99.76 (fast); B2A1(100,0,0) → 254.2/253.8/254.0; littleCMS sends sRGB white to 254,254,254 | **BUG** both modes | `a2_pinning.py`; colprof 99.9995 / 254.995 |
| A-04 | Black pinning: B2A1(0,0,0) → RGB 3/4/18 (fast, prints L 6.2, 2.5 ΔE00 above the printer's black) / 3/0/4 (acc, 1.0 ΔE00) | **BUG** relative intent | same; colprof 0/0.16/0.17 (0.09) |
| A-05 | Far out-of-gamut relative clip returns the *complementary* hue: sRGB magenta → device green, green → magenta; > 90° hue error on 7 % of OOG targets (acc), 21 % at q=l, 0 % colprof | **BUG** both modes, worst in accurate | `oog_hue.py`; `builds/oog-hue.txt` |
| A-06 | Round trip 600 random: acc 0.68/1.99/**7.26** vs colprof 0.61/1.73/2.47 ΔE00; neutral ramp 2–5× rougher than colprof at both ends | INCONSISTENCY | `a4_accuracy.py` |
| A-07 | CV smoothing ladder is a coin toss (criterion flat within 0.01–0.1 ΔE across 16× λ; winner flips ×0.25 ↔ ×4 with the split seed); on the 924p chart accurate generalises *worse* than fast (0.826 vs 0.659 held-out) | **BUG** | `a4d_heldout.py`; `builds/ho924/` |
| A-08 | `gamt` ≠ 0 for 68 % of printable interior colours (colprof 28 %) — ICC.1:2022 §9.2.29 says 0 = in gamut | INCONSISTENCY | `builds/a5-gamut2.txt` |
| A-09 | `-L 50` caps *total* ink at 51 % (colprof: black 49 %, total 261 %); `-l 200` fine and better than colprof's on ground truth; `-k` rules OK | **BUG** (S01) | `builds/m/S3-l50.icc`, `scratch/cref/s3-klim50.icc` |
| A-10 | `-u 0.9`: colprof refuses on output data; engine accepts and applies ×0.975 (acc) / ×1.001 (fast) | INCONSISTENCY | `builds/m/u09*.icc` |
| A-11 | Observer 2015_2 → `SpectralError`, no file | BUG (known) | `builds/m/obs2015.out` |
| A-12 | `-nP -nS` → oracle gets `-s` → B2A2 = B2A0; `-s` vs `-S` indistinguishable to the parser | BUG (translation) | `builds/m/nPnS.icc` tag table |
| A-13 | `spectral_physics` on RGB: bit-identical, **no log line** | GAP | `builds/m/spectral.log` |
| A-14 | `noise_model` engages on every real chart ("5.3× healthy": the four whites' spatial scatter, σ 0.26 XYZ) and changes every LUT; held-out: +0.18 better on 924p, −0.05 on 1168p | INCONSISTENCY (the "stands aside on clean charts" contract) | `builds/m/noise.log`, `builds/ho924n/` |
| A-15 | Plain accurate on a 3×-noisy chart flags **61** patches as misreads, 1 real (F1 0.03); with noise_model 6 | **BUG** | `builds/m/S4-base.out` |
| A-16 | NaN row → dead profile written (A2B1 = (0,−128,−128) everywhere), green log; stuck-instrument 18p chart → "profile" with fit 0.03 and no warning; junk 315p chart → fit 5.1/14.5 printed, no verdict; 60-patch chart → CV silently skipped; TAC stamped 400 on a 280 % chart → B2A asks 349 % | **BUG** (NaN) + GAPs | `builds/rob/` |
| A-17 | Rest of the option surface: `-ni -no -nc -Z -A/-M/-C/-D` (umlauts OK in v2 transliterated, v4 exact) `-R -c/-d -t/-T -nP -nI -f -V` all OK; `-no` leaves B2A0/B2A2 shaped; `-i D65` writes an unadapted `wtpt` in v2 *and v4* with no `chad` (§9.2.36/§9.2.15 — parity with colprof, not with the spec); bijective logs both renderers; v4 profile ID equals the §7.2.18 digest yet `sips --verify` rejects it (cause not found — for Agent B: what does ColorSync Utility show?); "both" twin has the same `desc` | mixed, see table | `builds/m/analysis.txt` |
| A-18 | Duplicate averaging: pre-averaged 3 reads beat stacked reads on every battery metric; stacked reads flag 205 "misreads" | IMPROVEMENT | `builds/dupavg/result.json` |
| A-19 | Q2 ranking + designs: 1 black ink limit, 2 duplicate averaging, 3 CIE 2015 observers (+`.sp`) | — | findings §A-19 |
| A-20 | CMYKcm light inks: highlights (L > 75) print **6.0 ΔE00 median / 14.1 p95** off (whole gamut 0.95); `c`/`m` zero on neutrals then jumping 0 → 17.5 % in the highlights; light cyan used only inside its hue gate | **BUG** for light-ink devices | `a6_lightink.py`; `builds/lightink/` |
| A-21 | CMYKOG at `-q h`/`-q u`: 24 / 25 min, both A2B grid 11 (stepped from 17/23, no log line), identical A2B fit, only the B2A grid differs (33/45); ETA said "~121 min left"; no cancel in the UI | GAP | `builds/m/S5-*.out` |
| A6 (d) | `FINAL_TOTAL_INK_LIMIT` ignored by `read_ti3` (280 read, 230 stamped); colprof uses it only with a CAL table | GAP, low | findings A-17 tail |

Verdict on the user's Q1: **"Maximum accuracy" is more accurate at the chart patches only** (self-fit 0.05 vs colprof 0.34 ΔE00). On unseen patches it ties (1168p) or loses (924p) against *fast*; on the print-relevant tables — white/black pinning, out-of-gamut clipping, neutral smoothness, round-trip tail — it is not better than fast and worse than colprof. None of the option translations is wrong in a way that changes the colorimetric core except `-L`, `-u`, `-nP -nS`, and the two engine-only rows that do nothing visible (`spectral_physics`) or the opposite of their contract (`noise_model`).

## Recommended fix order

1. **A-05** hue inversion of far-OOG relative clips (both modes; every saturated photo colour under relative colorimetric). Acceptance: > 30° hue error on ≤ 1 % of OOG nodes (colprof 0.4 %).
2. **A-03 + A-04** white and black pinning (already in a worktree per the coordinator): A2B1(white) = (100,0,0) ± 0.01; B2A1(100,0,0) ≥ 0.99995; B2A1(0,0,0) ≤ 0.002; lcms sRGB white → 255,255,255.
3. **A-16** NaN gate before any fit (name row + SAMPLE_LOC) and a flat-chart refusal; the scanner tool's sanitiser must stay in front if the tool is routed to the engine (Q3).
4. **A-07** CV ladder: require a margin above the criterion's own noise, fall back to ×1, say so; flag boundary picks. Then re-measure A-06/A-07 on the battery, not on the owner's charts.
5. **A-20** light-ink separation (hue gate must not zero light inks on neutrals; a lightness-gated prior instead) — before any CMY+N release.
6. **A-15 / A-14 / A-18** the noise family together: Huber scale from the chart's real scatter (or the noise model always on), duplicate averaging before the fit, and an honest log line.
7. **A-09** `-L` → black limit (Q2 #1), **A-10** refuse `-u` like colprof, **A-12** `-nP -nS`/`-s` translation, **A-11** observers (Q2 #3).
8. **A-08** gamt; **A-21** grid-reduction line / refuse `-q u` on ≥ 6 inks = 0 inside; **A-13** one log line; **A-17** v4: `chad` for `-i` ≠ D50, twin `desc` suffix, and the `sips --verify` question to Agent B.
