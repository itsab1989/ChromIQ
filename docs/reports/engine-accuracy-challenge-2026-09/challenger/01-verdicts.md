# Challenger verdicts — appended per item (independent run, 2026-09-05, ~04:53–05:33)

Repo HEAD 0e86b2f6 on feature/engine-accuracy-challenge, master 1b9cad54. Scratch: ~/Desktop/ChromIQ-engine-challenge/work-X/.
No repo file was edited. Master worktree for C1(b): work-X/master (git worktree, detached at 1b9cad54).

## C1(a) — colprof path untouched: CONFIRMED (partly, see C1(c))
`git diff 1b9cad54 0e86b2f6 --stat -- workflow/profile_builder.py core/` → empty. Also empty against the working tree.
(The working tree carries another session's uncommitted edits to ui/tabs/tab_measure.py, ui/widgets.py, ui/dialogs/scanin_dialog.py etc. — not this branch's.)

## C2 — "net improvement except S4 B2A +8.8 %": CONFIRMED, S4 B2A regression is real (+8.4 % at 20k eval)
Repro: `python -m benchmarks.battery --candidates "" --printers S1,S2,S3,S4 --eval 20000 --out work-X/final-q.json` (36 s total, ~10 s/printer).
Median ΔE2000 (before = builds/battery-before.json, 50k eval; X = my run, 20k eval; orch = builds/battery-final2.json):

| | metric | before | orch-final2 | X-acc | X vs before |
|---|---|---|---|---|---|
| S1 | a2b med / p95 | 0.089 / 0.452 | 0.088 / 0.452 | 0.088 / 0.451 | −0.4 % / −0.3 % |
| S1 | b2a med / p95 | 0.288 / 1.233 | 0.288 / 1.234 | 0.289 / 1.234 | +0.6 % / +0.1 % |
| S2 | a2b med / p95 | 0.223 / 1.775 | 0.221 / 1.777 | 0.220 / 1.792 | −1.5 % / +0.9 % |
| S2 | b2a med / p95 | 0.676 / 1.970 | 0.678 / 1.971 | 0.680 / 1.968 | +0.7 % / −0.1 % |
| S3 | a2b med / p95 | 0.242 / 0.857 | 0.239 / 0.861 | 0.239 / 0.852 | −1.3 % / −0.6 % |
| S3 | b2a med / p95 | 0.390 / 1.388 | 0.388 / 1.391 | 0.385 / 1.394 | −1.4 % / +0.4 % |
| S4 | a2b med / p95 | 0.449 / 1.508 | 0.431 / 1.265 | 0.435 / 1.254 | **−3.1 % / −16.8 %** |
| S4 | b2a med / p95 | 0.485 / 1.568 | 0.528 / 1.604 | 0.526 / 1.604 | **+8.4 % / +2.2 %** |

Reading: S1–S3 are unchanged to within ±1.5 % (that is eval-size noise: 20k vs 50k). The only printer that moved at all is S4 (the noisy CMYK one): A2B p95 −17 %, B2A median +8.4 %. "Net improvement" is therefore ONE printer's A2B improving while its B2A got worse; on three of four printers the last change-set did nothing measurable. The three last changes (gamt knee, ink-limit rule, XYZ top) cannot be isolated from the artefacts on disk: builds/battery-bisect.log bisects an EARLIER pair (white pin / CV smoothing on S2,S3,S6), not those three. Their combined effect on S1–S3 is ≤ 1.5 %, i.e. nothing outside noise.

## C5 — "the remaining-time estimate never grows between lines": CONFIRMED literally, but the estimate is NOT useful
Repro: work-X/c5_build.py — 924p chart (charts/real-rgb-924p-spectral36.ti3), -qm, accurate, -S ClayRGB1998, timestamped every progress line → work-X/c5-progress.log (56.55 s total).
Shown seconds sequence: ~20s (4.45 s) → ~20s → ~20s → ~20s (9.30 s) → [colprof stage, no number] → "taking longer than estimated" (53.31 s) → ~20s (56.27 s) → ~10s → ~10s → ~10s → almost done → "taking longer than estimated" ×27 lines. It never grew except right after a "taking longer" line. Literal claim holds.
Usefulness — shown vs actual remaining: at 18 % (4.45 s) "~20s", actual 52 s; at 26 % (9.30 s) "~20s", actual 47 s; at 40 % no number ("colprof is running, its time is not counted") — yet colprof's 44 s DID run down the deadline, so the very next line said "taking longer than estimated"; at 70 % "taking longer"; at 78 % (56.27 s) "~20s left", actual 0.3 s; at 96 % "almost done"; then **"100 % · taking longer than estimated" for the last 0.23 s over 27 lines** — the percentage hit 100 % on "converging 6/6" of the final stage while three more sub-passes (retry, hue clip, converging again) were still to come. The estimate was never within a factor 2 of the truth at any anchor, and the log ends with a line that says 100 % and "taking longer" at once.

## C7 — "Maximum accuracy is not yet a proven accuracy gain at the print over Fast or colprof": PARTLY — on the synthetic battery it IS a gain over Fast on every printer's median and over colprof on 3 of 4 printers, but it LOSES to colprof on S2
Repro: work-X/battery_mode.py fast … (the CLI hard-codes gammap_mode="accurate"; the wrapper subclasses BuildSettings) → work-X/fast-q.json; work-X/colprof_score.py runs `colprof -qm -l <tac>` on the SAME .bench/S*.ti3 and scores with benchmarks.battery.score_profile at 20k → work-X/colprof/colprof-q.json. All three at -qm, 900 patches, 20k eval, no -S.

Median / p95 ΔE2000:

| | table | colprof | Fast | Maximum accuracy |
|---|---|---|---|---|
| S1 | A2B | 0.117 / 0.396 | 0.119 / 0.565 | **0.088** / 0.451 |
| S1 | B2A | 0.597 / 1.223 | 0.356 / 1.275 | **0.289** / 1.234 |
| S2 | A2B | **0.136 / 0.611** | 0.277 / 1.418 | 0.220 / 1.792 |
| S2 | B2A | **0.661 / 1.606** | 0.714 / 1.837 | 0.680 / 1.968 |
| S3 | A2B | 0.292 / 1.019 | 0.280 / 1.085 | **0.239 / 0.852** |
| S3 | B2A | 0.822 / 1.892 | 0.493 / 1.664 | **0.385 / 1.394** |
| S4 | A2B | 0.508 / 2.681 | 0.635 / 2.536 | **0.435 / 1.254** |
| S4 | B2A | 0.799 / 2.794 | 0.649 / 1.894 | **0.526 / 1.604** |
| OOG hue err med/p95 | | S1 1.10/5.57, S2 1.19/4.81, S3 1.11/3.93, S4 0.95/4.06 | S1 2.60/11.4, S2 3.20/10.9, S3 3.63/17.5, S4 3.26/16.5 | S1 0.98/3.83, S2 2.03/7.20, S3 1.54/4.08, S4 1.51/4.79 |

Reading: accurate vs Fast — better median on all 8 table/printer cells, worse p95 only on S2 (A2B 1.79 vs 1.42, B2A 1.97 vs 1.84). accurate vs colprof — better on S1/S3/S4 (A2B medians −25/−18/−14 %, B2A medians −52/−53/−34 %), but on S2 (matte, dot gain 0.70) colprof's A2B is 1.6× better at the median and 2.9× better at p95, and colprof's B2A p95 is better too. colprof's OOG hue error is also lower than Fast's everywhere and close to accurate's. So: the orchestrator's caution is right for the print (no referee measurement exists — ~/ChromIQ data is developer test data), and on the synthetic referee the gain is real but NOT uniform: one of the four printers is a loss against colprof, and it is the A2B table (the one profcheck-style users look at).

## C1(b) — colprof ARGS identical on master and branch: CONFIRMED
Repro: work-X/c1b_args.py <root> <tag> — offscreen MainWindow with sandboxed settings (CHROMIQ_SETTINGS_FILE, CHROMIQ_PRESETS_DIR, custom_output_path in work-X/c1b/<tag>), beta OFF, the 924p chart copied into a run folder, `set_ti3_path`, then `_collect_params()` → `_builder._build_args()` in Guided and Manual. Master worktree at work-X/master (1b9cad54).
Both trees, both modes, byte-identical:
`-D c1b -al -qm -A ChromIQ -M c1b -S /Applications/Argyll/ref/ClayRGB1998.icm <run>/c1b`
and `_resolve_engine` says "colprof" in both modes on the branch. (`ProfileBuilder` itself is byte-identical, see C1(a); this proves the tab feeds it the same ProfileParams too.)

## C1(c) — what changed for a beta-OFF user: PARTLY — the orchestrator's two are real, and there are four more, all small
From `git diff 1b9cad54 0e86b2f6 -- ui/` (227 lines in 5 files), every hunk not gated on `profile_engine_beta`/`gammap_mode`/`_accurate_engine_active()`:

1. **`_archive_previous_build` on every build** (tab_profile.py:5183, both Guided and Manual, colprof included). Admitted. Before: a rebuild into the same run overwrote `<name>.icc` in place. Now: `<name>.icc`, `<name>-v4.icc` AND `calibrated.icc` move to `runs/runN/old/<timestamp>/`, one log line, and a failed build moves them back. Judgement: a FIX in spirit (never destroy a built profile silently), with two side effects the orchestrator does not mention: (a) every rebuild now leaves an `old/<timestamp>/` folder in the run; (b) `calibrated.icc` is swept too and the build does NOT recreate it — it comes from the Calibration tab's applycal step (tab_profile.py:1618) — so a calibrated user who rebuilds must re-run applycal. Before the branch a STALE calibrated.icc (from the old profile) stayed behind and could be installed, which was arguably worse, but the user is not told to re-apply. `Run.archive_to_old` (core/file_manager.py:1900) already existed on master, core/ is unchanged.
2. **`_restore_defaults` resets the -k rows and the four engine rows on a run switch** (tab_profile.py:5898+). Admitted. The Black-generation (-k) rows are NOT engine-only: they exist on master and feed colprof's `-k` for CMYK charts (tab_profile.py:5691). So a colprof CMYK user who switches to a run with nothing stored now gets the saved default `-k` instead of the previous run's leaked value. Judgement: a FIX (the §4 S4–S7 leak in per_target_settings.md), and it changes colprof's args after a run switch — the only case where C1(b) would differ between trees.
3. **The post-build "Use as pre-conditioning profile" text** (tab_profile.py:5459) no longer claims files are renamed with a `pre_` prefix (false since #127). Text only; a fix. It is why 12 i18n catalogues changed.
4. **The scanner/camera tool's command preview** (scanin_dialog.py:2619) now calls `choose_builder()` on every refresh, which calls `is_multi_ink(Path("<measurements>.ti3"))` — a lenient read of a file that does not exist, returning "" → not multi-ink. With beta OFF the text is unchanged: verified offscreen, `preview OFF: colprof -v -D <chart name> scanner -al -qm …` (work-X/c6.log). Harmless.
5. **Quit path** (main_window.py:2936, 3024): `_ask_before_quitting_on_a_build` asks only when `EngineProfileBuilder.any_running()`, which is never true with beta OFF; `terminate_argyll_children()` kills only children the engine registered in `_LIVE_CHILDREN` (gamut_map.py:465), never the ArgyllRunner's QProcess. Harmless.
6. A "Maximum accuracy (ChromIQ engine only):" heading inside `_m_engine_rows_widget`, which is hidden unless the accurate engine is active. Harmless. `ui/file_guide.py` and `settings_dialog.py` are text only.

Nothing else. No regression for a colprof user found; items 1(b) is the one to tell users about.

## C3 — paper white and black exact in both modes, Lab and XYZ PCS: CONFIRMED under xicclu (max 4.2e-5), PARTLY under littleCMS (8-bit: 1–2/255 at white, up to 5/255 at black — colprof's own profiles show the same through that CMM)
Repro: work-X/c3_whiteblack.py — battery S1 (RGB) and S3 (CMYK, TAC 280) charts from .bench/, 8 builds at -ql: {fast, accurate} × {-al, -ax}; xicclu -ff/-fb -ir/-ip/-is -pl; PIL.ImageCms (8-bit only: PIL has no 16-bit multichannel modes, so the CMM leg is 8-bit). Full numbers in work-X/c3.json, work-X/c3.log.

xicclu (device units 0..1):

| build | A2B1(dev white) Lab | B2A0/1/2(100,0,0) max dev err | B2A1(0,0,0) → device | A2B1 of that black |
|---|---|---|---|---|
| S1 fast -al | 100.0008, 0.00001, 0.00001 | 2.5e-5 | 0,0,0 | L 26.78 |
| S1 fast -ax | 100.0000, −0.0012, 0.0022 | 0 | 0,0,0 | L 26.77 |
| S1 accurate -al | 100.0008, 0.00001, 0.00001 | 2.6e-5 | 3e-6, 8e-6, 1e-5 | L 26.77 |
| S1 accurate -ax | 100.0000, −0.0012, 0.0022 | 0 | 0,0,0 | L 26.76 |
| S3 fast -al | same white | 4.2e-5 | 0.726, 0.578, 0.687, 0.810 (sum 2.80 = TAC) | L 13.36 |
| S3 fast -ax | same | 0 | 0.726, 0.578, 0.687, 0.810 | L 13.82 |
| S3 accurate -al | same | 3.7e-5 | 0.707, 0.656, 0.715, 0.723 (sum 2.80) | **L 14.90** |
| S3 accurate -ax | (log) | — | — | — |

White: ≤ 4.2e-5 device error in every case, all three intents, both PCS → the ≤ 2e-3 claim holds by a factor 50. Black on RGB: exact (≤ 1e-5). Black on CMYK: both modes land exactly on the TAC, but on DIFFERENT ink mixes — accurate's black is 1.5 L* LIGHTER than fast's (14.90 vs 13.36) at -ql on S3. "Exact" is not defined for a CMYK black; the two modes disagree, and that is a number the orchestrator did not report.

littleCMS 8-bit (PIL.ImageCms, LAB8 in, intent 0/1/2): white → S1 -al (254,254,254) = 1/255 both modes; S1 -ax (255,255,255) fast, (255,255,254) accurate; S3 -al (2,1,2,0)/255 fast, (1,1,1,0)/255 accurate; S3 -ax (0,0,1,0)/255. Black (L=0) → S1 -al (0,0,1) fast / (0,2,3) accurate; S1 -ax (0,0,1) / (0,0,5). Control through the same path: colprof -qm S1 gives white (255,255,254) and black (0,3,5); colprof S3 gives white (0,0,1,0). So through littleCMS the engine sits within 1/255 of colprof's own profiles at white and black; the residual is the CMM's 8-bit Lab leg (v2 Lab16 0xFF00 white, grid interpolation), not the tables. Strictly, "≤ 2e-3 device error" is NOT met through littleCMS (1/255 = 3.9e-3 is the floor there) — for the engine or for colprof.

## C4 — the hue-preserving clip cannot flip hue: CONFIRMED on S1, and it did not flip on a hue-gap printer either — but it drifts up to 20° with chroma collapse
Repro: work-X/c4_hue.py — ring of 24 hues at L 55, C 110 (h = 0..345 step 15) + sRGB (255,64,239) → Lab(62.6, 82.9, −47.7) and (0,239,16) → Lab(82.9, −75.3, 75.8) via xicclu on Argyll's sRGB.icm; each through B2A1 then A2B1 of the profile; hue error = |Δh°|.
S1 accurate -qm (.bench/S1.icc from the C2 run): **max 7.57°** at Lab(55,110,0) → dev (1.0, 0.0001, 0.986) → Lab(64, 65, −9); 0 of 26 above 10°; the two historic flip colours: 2.88° and 3.79°. No flip.
Hue-gap printer: battery S2 chart with the B channel clamped to ≤ 0.3 (900 patches, measured through the real S2 model, accurate -qm, TAC): **max 19.97°** at Lab(55,−110,0) → dev (0.851, 0.984, 0.101) → Lab(78.4, −11.3, −4.1); 5 of 26 above 10°; historic colours 5.57° and 2.35°. Nothing crossed into another hue family (a flip would be ≥ 60°); but the worst case collapsed chroma from 110 to 12 and lifted L from 55 to 78 — a "hue-preserving" clip that lands on a near-neutral, where hue is nearly meaningless. The build log carried only "hue-preserving clip k/4" lines; no line said a nearest-clip fallback ran, so whether the fallback path executed cannot be told from the log (work-X/c4.log).

## C6 — the scanner/camera tool follows Preferences: CONFIRMED
Repro: work-X/c6_scanner.py (offscreen, sandboxed settings, `ScannerProfileDialog(ArgyllRunner(s), s)`, "Profile my printer" ticked, params via `scanner_colprof.make_profile_params` on a copy of the 924p chart) → work-X/c6.log.
- beta ON + Maximum accuracy: `_printer_profile_builder(params)` → **EngineProfileBuilder**. beta OFF → ProfileBuilder. beta ON + Bit-exact → ProfileBuilder (colprof itself, as `choose_builder` documents).
- Command preview: ON → "ChromIQ profile engine · Maximum accuracy — instead of: colprof -v -D <chart name> scanner -al -qm …"; OFF → "colprof -v -D <chart name> scanner -al -qm …" (unchanged text).
- The build through that builder ran to rc 0 in 54.1 s, 75 log lines, wrote c6-printer.icc, and the log contained `Profile check complete, peak err = 2.062908, avg err = 0.188830`; the tool's `_watch_profile_check` captured `[(2.062908, 0.18883)]` — so `_selfcheck_verdict` has the numbers it needs.
- Side note, not a defect: with params collected BEFORE ticking printer mode (scanner defaults, `-as`), `choose_builder` still says "engine" and the engine then refuses with "Output profile can only be a cLUT algorithm" — the same refusal colprof gives; a user cannot reach that state through the UI because printer mode sets `-al`.

### C3 addendum — the CMYK black against ground truth
Synthetic S3 (`lab_relative_true`): fast's black (0.726,0.578,0.687,0.810) truly reads L 13.34, a −0.93, b 0.47; accurate's (0.707,0.656,0.715,0.723) reads L 14.84, a 0.83, b 1.23 — the A2B1 tables reproduce these to 0.05 L. The darkest device value under TAC 280 (26^4 grid search) is (0.80,1,0,1) at L 8.1 but b −14.5, i.e. a blue-tinted black; a neutral black is necessarily lighter, and the request was Lab(0,0,0). By ΔE76 from that request fast's black (13.4) is 1.5 closer than accurate's (14.9). So on CMYK "black exact in both modes" is PARTLY: white is exact, black is a defensible neutral in both modes, but Maximum accuracy's black is 1.5 L* lighter than Fast's at -ql — the opposite of what "maximum accuracy" promises for the shadows.
