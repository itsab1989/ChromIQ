# Brief — Agent A: colour-science referee (the numbers)

You are a senior colour scientist and profiling engineer. Your job is to find
every way the ChromIQ profile engine's **Maximum accuracy** mode produces a
worse, wrong, or non-standard profile than it should — with measurements, not
opinions. Repo `/Users/Basti/develop/ChromIQ`, branch
`feature/engine-accuracy-challenge`, venv `.venv` (`.venv/bin/python`),
ArgyllCMS 3.5.0 at `/Applications/Argyll/bin`. Read `CLAUDE.md` first.

Read before anything else (in full):
* `~/Desktop/ChromIQ-engine-challenge/reports/orchestrator/01-plan-v1.md`
* `~/Desktop/ChromIQ-engine-challenge/reports/critic/01-critique.md` — the
  critic already MEASURED several things (§1 M1–M10) and refuted some of the
  plan; do not redo what is measured there, build on it.

## Rules that are not negotiable
1. **Do NOT edit any file under the repo** (`workflow/`, `ui/`, `tests/`,
   `benchmarks/` …). The tree is frozen while you and Agent B measure it; the
   orchestrator fixes afterwards. Your scripts go to
   `~/Desktop/ChromIQ-engine-challenge/work-A/`. If you must import the
   repo, run from the repo root with `.venv/bin/python`.
2. **Copies only.** `~/ChromIQ` is the owner's real project folder — never
   open, build into, or run a tool inside it. Copies of the real charts are in
   `~/Desktop/ChromIQ-engine-challenge/charts/` (note critic M10: the 18p and
   315p files are NOT measurements — stuck instrument / junk; use them only
   as robustness inputs; the 924p and 1168p are ColorMunki spectral charts).
3. Any process that launches the app or `AppSettings()` must have
   `CHROMIQ_SETTINGS_FILE=<your sandbox>/settings.ini` and
   `CHROMIQ_PRESETS_DIR=<your sandbox>/presets` exported first. You probably
   never need the app — Agent B owns the screen. If you do, use
   `scripts/engine_challenge/harness.py` (read its docstring) and do not edit it.
4. Never run `colprof -f` (or any refusing colprof) in a folder holding a
   profile you care about — it truncates the output `.icc` to 0 bytes
   (critic M9). Scratch copies only.
5. `benchmarks/README.md` rule: never tune anything against the owner's
   charts; the 924p/1168p are smoke inputs, the synthetic battery is the
   referee for "better".
6. No `pytest --runslow`, no `-n auto` gates. Single test files are fine
   (`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_x.py -q`).
7. **Staged report**: append to
   `~/Desktop/ChromIQ-engine-challenge/reports/agent-A/01-findings.md` after
   EVERY completed item — heading, verdict, the exact command(s), the numbers,
   file:line of the cause. A killed agent must lose at most one item. Number
   findings `A-01…`. Grade each **BUG / GAP / INCONSISTENCY / IMPROVEMENT /
   OK / NOT-MEASURABLE-HERE**, and say what was measured vs read.
8. Cite trusted sources with URLs where a standard is invoked (ICC.1:2022,
   colprof.html, CIE). No "probably". Every number: the command that made it.

## Your territory (from plan S-items + critic N-items, as re-split by the critic §4)

Work in this order; stop each item when you have the number.

**A1. Real-CMM leg (critic N18) — the foundation.** Build a tool
`work-A/cmm_probe.py` that, for a given `.icc`, produces per-intent
(perceptual 0, relative 1, absolute 3) transforms sRGB→profile and
profile→Lab with **littleCMS via `PIL.ImageCms`** and with Argyll `xicclu`,
on a 33³ device grid and a 1000-swatch Lab ring just inside/outside the
gamut, and additionally runs ColorSync via `sips --matchTo` on a TIFF.
Report agreement (ΔE2000 median/p95/max) between xicclu and littleCMS and
between littleCMS and ColorSync, for: engine fast, engine accurate (q=m, with
`-S ClayRGB1998.icm`), and the colprof reference of the same 924p chart. Any
intent where a real CMM disagrees with xicclu by > 0.5 ΔE at p95 is a finding.

**A2. White and black pinning (plan S08 / critic N01, N07) — quantify fully.**
Critic M1/M2 proved B2A1(L=100)→RGB≈0.996 and A2B1(white)=L 99.76/99.94.
Extend: (a) all three intents, A2B and B2A, white AND black corners, engine
fast/accurate vs colprof; (b) through littleCMS and ColorSync (A1);
(c) what it means in ink: convert a 100 % white TIFF through the engine's
profile with `sips --matchTo` and read the max RGB deviation from 255;
(d) which `wtpt` is right by the chart's own duplicate rows (mean vs
brightest vs colprof's) — with the ICC.1:2022 §9.2.36 text and Argyll's
`profout.c` `ICX_SET_WHITE` as references. Output: the numbers the fix must
reproduce (an acceptance test spec: "A2B1(device white) = (100,0,0) within
0.01; B2A1(100,0,0) = device white within 1/65535").

**A3. Option matrix (plan S17 + critic S17 a–e, N02, N03, N04, N05).** For
every `BuildSettings` field reachable from the UI in accurate mode build the
924p chart (or the S3 CMYK synthetic where the option is ink-only: `-k/-K/-l/
-L`) default vs changed, **fresh process each**, `timestamp` fixed, and prove
by tag-level byte comparison which tags changed and that nothing else did.
Specifically nail: `-s` vs `-S` (does the engine build a mapped B2A2 for `-s`
where colprof aliases it? — N05); `-u 0.9` (N02, expect ×0.9 on wtpt Y);
observer 2015_2 (N03, expect a clean colprof fallback or a clear message, get
"Unknown observer"); `-l 200` on S3 accurate — is the colprof oracle built
without it (N04) and do mapped targets get clipped twice?; `-L 50` (S01 —
expect black limit, get total limit); `-r` (does it move the CV ladder centre
and the chosen λ?); `-V` (no-op, matches colprof); `-ni/-no/-np/-nc`;
`-Z m t n b p r s a`; `-A/-M/-C/-D` incl. an umlaut description in v2 AND v4;
`-R`; `-c/-d` viewing conditions (do they reach the CAM02 mapping? compare
B2A0 bytes `-c pp` vs `-c mt`); `-t/-T` intents; `-nP/-nS/-nI`; `-i D65` in
v2 and v4 (v4: is `chad` written? critic S12 — expect no); `-f` (refusal
parity only on ColorMunki data; synthesise an `i1 Pro`-stamped copy to get
numbers); spectral_physics on RGB (no-op — does the LOG say so?); noise_model
on a clean chart (bit-identical?) and on a synthetic 3× noisy chart (better on
held-out?); render_style bijective (N11 log line; and A1 through a real CMM);
icc_version 2/4/both (N12: twin `desc` identical).

**A4. Accuracy that reaches the print (critic N14, plan S06).** 924p chart,
fast vs accurate vs colprof `-qm`: (a) `xicclu` round trip on 600 random
device values (median/p95/max, like `tests/test_profile_engine_parity.py:57-70`);
(b) neutral ramp L 0→100 through B2A1 → RGB, first and second differences
(banding); (c) the same on a*=b*=±20 slices; (d) held-out A2B accuracy with
`benchmarks/heldout.py` (90/10, endpoints protected) on 924p and 1168p —
does accurate beat fast and colprof on unseen patches, and by how much
(ΔE2000)? (e) the CV ladder: which factor was chosen, was it at the boundary,
and what does λ×0.25 vs ×1 do to (a)–(c)? Verdict: is "Maximum accuracy"
more accurate where it matters, or only at the chart patches?

**A5. Gamut tag semantics (critic N06).** `xicclu -fg` on a ring of Lab
values 0.5/1/2/3 ΔE inside the gamut, engine vs colprof; and a littleCMS
gamut-check (proofing transform with `cmsFLAGS_GAMUTCHECK`) on the same
swatches. ICC.1:2022 §9.2.29 is the reference.

**A6. Ink devices on the battery (plan S18, S19, S23; critic N04, N09, N21).**
Using `benchmarks/synthetic.py` + `benchmarks/battery.py` (read them; reuse,
do not rebuild): (a) add a CMYKcm light-ink printer **in your work folder**
(subclass/param the existing SyntheticPrinter; do not edit `benchmarks/`)
and measure the B2A neutral ramp's c/m columns in accurate mode — are light
inks used in highlights or zeroed by the hue gate (`b2a.py:301-318`)?;
(b) `-q h` and `-q u` on S5 (CMYKOG): real grid used, build time, and does
the log say the grid was reduced?; (c) duplicate-patch averaging as an
IMPROVEMENT candidate: on S4 (noisy CMYK) with a chart carrying 3× repeats,
compare accurate as-is vs the same chart pre-averaged — battery score;
(d) a calibrated CMYK `.ti3` with `FINAL_TOTAL_INK_LIMIT` — which limit does
the engine take?

**A7. Robustness inputs (critic N13, plan S09/S10).** Through `build_profile`
in accurate mode, all four options on: NaN row; the stuck-instrument 18p
chart; the junk 315p scanner chart; a Lab-only `.ti3` (strip XYZ columns from
the 924p); a 60-patch subsample of the 924p (below `_HOLDOUT_MIN_PATCHES`);
a chart with zero duplicate whites; duplicate SAMPLE_IDs; `TOTAL_INK_LIMIT`
above what was printed. For each: exception text vs a profile written
silently; and whether the fit line would tell a user something is wrong.

**A8. Determinism on the oracle path (critic N15)** — two fresh processes,
fixed timestamp, `-S ClayRGB1998.icm`, accurate: byte-identical?

**A9. Q2 — more options.** From the critic §5 table, rank the unmapped real
options (black ink limit, `.sp` illuminant, 2015 observers, `-g`, `-p`,
`-s/-S` percentage forms, per-channel dot limits, duplicate averaging) by
(i) how often a printmaker needs it, (ii) evidence from A3/A6, (iii) cost.
Recommend the top 3 with a one-paragraph design each (where in the Manual
group, what the tooltip must say, which `BuildSettings` field, which test).

## Deliverable
`reports/agent-A/01-findings.md` (staged) + `reports/agent-A/02-summary.md`
at the end: a table of A-NN findings with grade, one-line repro pointer, and
your recommended fix order. Return a ≤ 50-line summary to the orchestrator.
Time budget: about 3 hours of measurement; if an item will take longer than
20 minutes of compute, downscale it (q=l, fewer swatches) and say so.
