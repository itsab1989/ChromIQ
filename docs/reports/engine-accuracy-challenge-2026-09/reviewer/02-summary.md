# Reviewer summary — attack on the engine-challenge fixes (2026-09-05, ~04:15)

Tree `feature/engine-accuracy-challenge` @ ac4e2f61 (+ the uncommitted `accuracy.py` best-mean/group-split
change, measured separately). Nothing edited in the repo; mutations applied at runtime. Details, tables and
repro pointers: `reports/reviewer/01-findings.md`; scratch `~/Desktop/ChromIQ-engine-challenge/work-R/`.
Two stray folders my R14 script created in the repo root (`blocked/`, `colprof-fails/`) were removed.

| item | grade | one line | repro |
|---|---|---|---|
| R1 white pin | **BUG** | weight `((L−60)/40)²·(1−C/40)` is <1 at the white node itself → residual δ·(1−w): fitted 98.80→99.91, 95.69→99.05, accurate -r4 93.28→**97.71**; B2A pinned separately → A2B/B2A inconsistent | `work-R/R1b.py` |
| R1b XYZ PCS | **BUG** | `-a x` (fast and accurate): B2A(100,0,0) = **4–10 % CMY ink**, every table; no grid node at D50 so `pin_white_node` pins nothing, L-scaling is Lab-only | `probe_B.py`, `probe_D.py` |
| R1c kink | OK | pin vs no-pin: identical d² near L60; +0.008 at L96 | `probe_D.py` |
| R2 L-axis | GAP | xicclu: 100→0.99999, 100.39 clipped, gamt 0; littleCMS 8-bit Lab: engine rel 253 vs colprof 254 at L*=100 (one step darker); ColorSync untested | `probe_D.py` |
| R3 hue gate | OK | step across C=5 (0.005–0.009) < neighbour steps (0.025–0.039); no-candidate → nearest clip, no crash | `probe_B.py` |
| R4 CV margin | GAP | S5 regression is NOT the margin (see R6); new rule: fallback row-cut taken in 6/9 splits (0 straddles measured) | `straddle.py` |
| R5 -L on 6 inks | OK | K max 0.3996/0.3949/0.3994/0.3747 across B2A0/1/2, fast+accurate, with proxy anchor and -S tables | `R5.py` |
| R6 dup averaging | **BUG** | THE S5 regression: avg on/off = k_tv 0.377/0.127 (committed rule), 0.178/0.101 (new rule); k readings collapse to weight 1 at the cube corners; outlier_rows/fit_max now index collapsed rows | `s5_avg.py`, `S5b/` |
| R7 gates | GAP | flat gate fine (relative span); poor-fit WARNING fires on a real ALIGNED scanner chart (fast median 3.29) with "instrument did not read colour" | `probe_C.py` |
| R8 ink cap | GAP | colprof = stamp−10 (colprof.c:1147-1157), honours a user −l with a warning; engine = printed max, overrides a user −l silently | source |
| R9 -s/-S | OK | Guided/Manual/extra-args/old presets all land in `sat_gamut`; mutation lands and fails the test | `mutate2.py` |
| R10 gamt | **BUG** | tag non-zero for printable colours: median 1.56 at 2 ΔE inside the TRUE surface, 0.91 at 5 inside (colprof 0 / 86–93 % zeros); flags EARLY, ~5–10 ΔE band | `probe_D.py` |
| R11 kill child | OK | "Using the engine's own rendering (colprof was stopped)", 2.6 s, no temp dir, icc written | `R11.py` |
| R12 quit guard | OK | ON SCREEN: question appears on close during colprof, Keep→build finishes (icc 03:57), Quit→no orphan colprof, no oracle dir; box has no title (macOS) and no icon; scanner-tool builds not guarded | `R12.py`, `quit-question-keep.png` |
| R13 scanner routing | GAP | accurate peak 21.1 vs colprof 10.2 on the same aligned scan (avg 3.3 vs 3.9): thresholds calibrated on colprof; `test_scanner_tool…` is source-text only | `probe_C.py` |
| R14 archive | **BUG** | `_archive_previous_build` runs before the "blocked" check and never restores: blocked multi-ink build and failed colprof build both leave the run with NO profile (moved to old/) | `R14.py` |
| R15 defaults | OK | preset loader defaults every new key; 6 UI tests pass | tests |
| R16 i18n | OK | 0 missing ×12, test_i18n 87 passed, Du, timings match B-34 | script |
| R17 progress | OK | monotone in both modes; "Saturation table: reusing" anchor (40) prints at 74 in fast mode, harmless | `probe_B.py` |
| R18 mutations | GAP | 12 mutations fail their test ✓; 4 cannot fail: hue-gate removed (nearest clip passes), `_CV_MARGIN_FRACTION=0`, `_NAME_SCALE_FACTOR=0` (16 vs 14 flags), scanner-tool source-text test; 3 literals unmutable | `mutations*.log` |

## The three most dangerous things
1. **R6 — duplicate averaging is the S5 regression the handover blamed on the CV margin/black pin**, and it is still a K-smoothness regression under the new `accuracy.py` (0.178 vs the 0.151 gate). Averaging k identical corner readings into one weight-1 row lets the extremes go; keep the average and weight it by k.
2. **R1/R1b — the white pin is not a pin.** The local weight is <1 at the very node it exists for (up to 2.3 L* short with heavy smoothing, and the B2A side is forced to white anyway → inconsistent profile), and with the XYZ PCS nothing is pinned at all: 4–10 % ink in the paper white in every table. The tests only build well-fitted Lab-PCS charts.
3. **R14 — a rebuild that cannot start or fails now removes the run's working profile.** Blocked multi-ink (beta off) and a colprof failure both archive first and restore nothing; before the change the old profile survived a failed rebuild.

Honourable mention: R10 — the gamut tag reports printable colours out of gamut up to ~10 ΔE inside the edge (colprof: 2), so a soft-proof gamut warning paints a wide false band; the 3 ΔE node tolerance only fixed the interior statistic the test looks at.
