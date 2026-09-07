# Handover — paused 2026-09-05 ~01:45 CEST at Basti's request (usage limits)

Resume by reading this file, then `04-fixes-in-progress.md`, then the agents'
`02-summary.md` files. Nothing here is committed to `feature/engine-accuracy-challenge`
yet — the engine work lives on the worktree branch `wip/engine-fixes`.

## Where things are

| what | where | state |
|---|---|---|
| Main checkout | `/Users/Basti/develop/ChromIQ` on `feature/engine-accuracy-challenge` @ d3d1bd43 | FROZEN tree the agents measured; carries ~34 uncommitted paths of ANOTHER Claude session's measurement-report work (its territory; do not stage). Untracked from this job: `scripts/engine_challenge/` (harness + Agent B's drivers). |
| Fix worktree | `/Users/Basti/develop/ChromIQ-fix` on `wip/engine-fixes` | commit 18a7b264 (first batch) + UNCOMMITTED second batch (see below). Run tests from there with `/Users/Basti/develop/ChromIQ/.venv/bin/python`. |
| Proof folder | `~/Desktop/ChromIQ-engine-challenge/` | plan, critic, agent-A (21 findings + summary), agent-B (33 findings; B10 + summary were still being written when paused), orchestrator notes, builds/, screenshots/, charts/ (copies) |
| Peer Claude session | uds socket `/tmp/cc-socks/37369.sock` ("chromiq-ed") | agreed territories; will not switch branches without asking. Its files: beta8_open_items.md, unified_measurement_management.md, measurement_messages.py, test_message_catalogue.py, test_a_failed_report_says_so.py, measurement_report*.py, measurement_report_dialog.py; it has uncommitted edits in `ui/dialogs/scanin_dialog.py` (preview-button block, Profile-type help) — RE-READ that file before the scanner-routing edit. |

## Engine fixes on `wip/engine-fixes`

Committed (18a7b264): white pin (A2B + B2A L-axis + white node), black node pin,
hue-gated OOG clip, CV margin over 3 splits, `-L` black ink limit + BLACK_INK_LIMIT,
CIE 2015 observers, `-u` refused like colprof, SAMPLE_LOC outlier names, nan/inf gate,
subprocess timeouts, v4 twin " (v4)" description, spectral/bijective log lines.
Tests: 184 passed in the engine set (round 5), plus 4 new behaviour tests.

UNCOMMITTED second batch (all edits done, tests written, test run was in flight):
`-s`/`-S` semantics (B2A2 aliases B2A0 with `-s`; `-nP -nS` no longer collapses
the saturation table), gamt tolerance 3 ΔE (interior zeros 32 % → 66 % at -qm),
outlier naming threshold 6× robust scale, flat-chart refusal (white−black < 10 L*),
poor-fit WARNING line (median > 2 ΔE00), ink limit capped at the chart's printed
maximum with a line, duplicate-patch averaging in accurate mode (off with the
noise model), `-no` on mapped tables, v4 `chad` + adapted wtpt under a non-D50
illuminant, plain-language noise lines, `_run_argyll` Popen registry +
`terminate_argyll_children()` (engine half of the quit fix), progress anchors in
time order and "colprof is running, its time is not counted".
Tests: `tests/test_engine_second_batch_from_the_accuracy_challenge.py` (result of
the last run in the task output / rerun it), `tests/test_engine_accurate_mode_keeps_hue_black_and_honest_smoothing.py`.

## OPEN DECISION — the battery says NO (benchmarks/README promotion gates)

`builds/battery-before-after.log`: with the first batch, A2B median on the synthetic
printers REGRESSES (S2 +42 %, S3 +32 %, S6 +32 %), "DO NOT PROMOTE". The real-chart
held-out numbers (Agent A A-07 + my FIX3) IMPROVED. A bisect (`builds/battery-bisect.log`,
V0 fixed / V1 no white pin / V2 old single-split CV / V3 both) was running when
paused — read it first. Hypotheses: (1) the global Bradford re-adaptation of the
grid to pin white shifts the interior by the white-fit error (S2 +0.094 abs ≈ its
white error); a lightness-weighted correction (full at white, decaying below
L* 70) would keep the interior; (2) the CV margin keeps ×1 where the noise-free
synthetics genuinely prefer ×0.25. Decide with the bisect numbers; the rules say a
candidate must not regress > 2 % on any device class.

## Still to do (in order)

1. Read bisect → adjust the white pin (local correction) and/or CV margin → rerun
   `python -m benchmarks.battery --candidates "" --out …` and `--compare` (25 min).
2. Commit batch 2 on `wip/engine-fixes` by name; rerun the engine test set.
3. UI phase in the MAIN tree (after Agent B is fully done — check its summary):
   B-18 `_restore_defaults` four rows · B-06 first log line + bar label say
   "Maximum accuracy" · B-10 stale "pre_ prefix" sentence in Profile Built ·
   B-03/B-04 Accuracy + engine tooltips (timings: fast 101 s, bit-exact = colprof
   direct on ≤4 inks, accurate 53–67 s on the 924p at -qm; "handed to colprof"
   sentence) · B-01 consent grammar · B-02/B-05 engine rows: heading + scroll into
   view · B-26 scanner tool printer mode → EngineProfileBuilder when the beta is
   on (keep `_sanitize_scanner_ti3` in front; preview text; RE-READ scanin_dialog.py)
   · B-25 main_window quit guard while `_engine_builder.is_running` +
   `terminate_argyll_children()` on quit · B-20 archive-before-rebuild on the
   engine path incl. the twin (product rule "never destroy") · A-21 log the grid
   reduction on 6+ inks · A-20 light inks (CMYKcm) — needs its own design.
4. Merge `wip/engine-fixes` into `feature/engine-accuracy-challenge`
   (`git merge` from the main checkout; name-only staging for the UI edits).
5. Reviewer agent (attack the fixes; rerun A's and B's repros on the fixed tree).
6. Everyday tier, then `--runslow` (never in parallel with another gate), then
   the final report to Basti + memory update.

## Bisect result (read at pause time; V2/V3 may have finished since — check the log)
V0 fixed: S2 a2b 0.318 / S3 0.319 / S6 0.588. V1 (no white pin): S2 0.241 / S3 0.238 /
S6 0.543 (shipped baseline 0.223 / 0.242 / 0.447). → The GLOBAL Bradford
re-adaptation in `_pin_media_white` is the main A2B cost; the CV margin explains the
rest on S6. Next code step: replace the global adaptation by a correction that is
full at white and fades with lightness/chroma (e.g. δ = D50-relative fitted-white error
applied to nodes with weight ((L−60)/40)² clipped to 0..1 and chroma < 30 → 1 −
chroma/30), keep the B2A L-axis scaling and the node pins, re-run the battery.
Second batch WIP committed on `wip/engine-fixes` (see git log there).
9 passed in 232.41s (0:03:52)
