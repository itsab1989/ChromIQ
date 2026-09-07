# ChromIQ profile engine — "Maximum accuracy" challenge: plan v1

Orchestrator plan, written 2026-09-04 before any agent was spawned. This is the
document the critic agent is asked to tear apart. Nothing in §4 is a finding
yet — they are suspects from reading the code, each needs a run that was
actually executed before it is called a finding.

Branch: `feature/engine-accuracy-challenge` (from master @ d3d1bd43, 4.1.5-beta.8).
Proof folder: `~/Desktop/ChromIQ-engine-challenge/` (this folder).
Staged reports: `reports/<role>/NN-*.md`, appended as work progresses, never
rewritten — a killed agent loses at most its current step.

## 1. What the user asked (verbatim intent, restated as testable questions)

Q1. Are the options the Build Profile tab offers **while the engine's Maximum
    accuracy mode is active** working as intended, or could they be improved?
Q2. Could **more options** further improve profile quality — for RGB, CMY and
    CMY+N devices?
Q3. When the engine is active, is it **also used by "Build profile with scanner
    or camera"**, and could that tool benefit from options only visible with
    the engine + Maximum accuracy?
Q4. Everything must be proven **end to end on screen**, in the real app, real
    styling, real settings (sandboxed), with proof on the Desktop, on a branch.

## 2. What exists (read, not remembered)

| Piece | Where | What it does |
|---|---|---|
| Beta switch | `ui/dialogs/settings_dialog.py:583` `profile_engine_beta`, consent QMessageBox at `:1536` | engine on/off; consent dialog on first tick |
| Accuracy picker | `settings_dialog.py:632` `gammap_mode` ∈ fast / argyll ("Bit-exact") / accurate ("Maximum accuracy") | only visible while the beta switch is on |
| Routing | `ui/tabs/tab_profile.py:581 _resolve_engine` | multi-ink → engine (or "blocked" without beta); beta+argyll on ≤4 inks → **colprof**; beta+fast/accurate → engine unless `engine_support` says no (unknown extra flag, unreadable gamut source) |
| Engine-only rows | `tab_profile.py:2792` `_m_engine_rows_widget` — **Manual module only** | Spectral physics model · ICC profile version (2/4/both) · Measurement noise handling · Out-of-gamut rendering (Argyll-matched / ChromIQ bijective) |
| Param → settings | `workflow/engine_builder.py:settings_from_params` + `_apply_extra_args` | full colprof option surface mapped onto `BuildSettings` |
| Builder | `workflow/profile_engine/builder.py` | `build_profile()`; accurate = `average_endpoints`, `extra_ink_hues`, `fit_forward_model_accurate` (CV λ ladder ×0.25…×4, Huber IRLS, outlier report), shaped-XYZ codec, hue-preserving clip, Euclidean TAC projection, dense shell; candidates via env `CHROMIQ_ENGINE_NEXT` (ucs, joint-sep, gp, spectral, render2) |
| Accuracy fit | `workflow/profile_engine/accuracy.py` | `_HOLDOUT_MIN_PATCHES = 120`; ΔE2000 criterion; `fit_forward_model_accurate_challenged` = noise detector (≥2× healthy scatter) |
| Noise model | `profile_engine/gp.py` | heteroscedastic σ from duplicate patches; uncertainty map lines |
| Spectral physics | `profile_engine/spectral_model.py` | YNSN hybrid, held-out challenge, ink devices with SPEC_* only |
| Gamut mapping | `profile_engine/gamut_map.py` | Python port (fast) / `native/chromiq-gammap` helper (bit-exact; **present and runnable here**) / colprof oracle for ≤4 inks with an **in-process cache** `_ORACLE_CACHE` keyed by `_oracle_cache_key` |
| ti3 reader | `profile_engine/ti3_data.py` | any COLOR_REP; XYZ or Lab-only; SPEC_* when `SPECTRAL_BANDS == len(cols)` |
| Writer | `profile_engine/icc_writer.py` | v2 mft2; v4 header/Unicode/profile-ID when `icc_version="4"`; "both" writes `<stem>-v4.icc` twin via `out.with_name` |
| Scanner/camera tool | `ui/dialogs/scanin_dialog.py:652` `self._profiler = ProfileBuilder(runner)`; printer mode `_printer_mode()`; build at `:5378` | **always colprof**, never consults `profile_engine_beta` / `gammap_mode`; command preview says `colprof …` |
| Benchmarks | `benchmarks/` (S1–S6 synthetic printers, ICC-byte referee, promotion gates) | dev-only; the objective yardstick agents should reuse, not rebuild |
| Tests | `tests/test_engine_accurate_mode.py`, `test_engine_v2_options.py`, `test_engine_gp.py`, `test_engine_v2_harness.py`, `test_engine_builder.py`, `test_profile_engine*.py` | synthetic only; **no test builds an accurate profile from a real instrument measurement** |
| Real data on this machine (copied to `charts/`, originals untouched) | 924 p RGB, 36-band spectral (i1Studio) · 1168 p iRGB, 106-band spectral (ColorMunki) · 315 p scanner-measured printer chart · 18 p CR30 chart · plus `tests/golden/…/Golden-Printer.ti3` | the first two are the only real spectral charts; nothing CMYK/CMY+N real exists (memory: CMY+N "built, never really tested") |

## 3. Answers that are already visible from the code (to be confirmed on screen)

A-Q3. **No.** The scanner/camera tool's printer-profile path is hard-wired to
colprof (`scanin_dialog.py:652/5378`). With the beta engine on and Maximum
accuracy chosen, the Build Profile tab uses the engine and the scanner tool
does not; the user sees two different builders for the same measurement
depending on which window they build from. The tool's *scanner input profile*
path is a different problem (input-class profile) and outside what the engine
implements (`builder.py` docstring: output-class only) — so the honest scope
for Q3 is the **printer-from-scan** path, which is exactly a ≤4-ink output
build the engine already handles.

A-Q1 (partial). The four engine-only options are shown in **Manual only**.
Guided mode with Maximum accuracy active still builds through the engine, with
those four silently at their defaults, and Guided has no way to see or change
them. Whether that is a gap or by design is a product call (Guided is meant to
be simple) — record it, don't fix it unasked.

## 4. Suspects from code reading (each becomes a numbered test)

S01 **`-L` is mapped to the TOTAL ink limit.** `engine_builder.py:_apply_extra_args`
    treats `-l` and `-L` identically (`s.ink_limit = …`). colprof: `-l tlimit`
    = total ink limit, `-L klimit` = **black** ink limit (colprof usage text,
    verified locally). Hand-typing `-L 90` in Manual's extra options would cap
    total ink at 90 % on a CMYK build. The engine has no black-ink-limit at
    all (`BuildSettings` has no `k_limit`). → repro: CMYK synthetic, extra
    `-L 50`, compare max C+M+Y+K in B2A vs `-l 50`.
S02 **Gamut-source sniffed by file NAME.** `gamut_map.source_kind`: any path
    whose stem contains "clay", "adobe" or "srgb" is replaced by an analytic
    surface, whatever the file contains (`sRGB-linear.icc`, `AdobeRGB-ish.icm`,
    a `.gam` named `adobe-photo.gam`). → repro: rename a ProPhoto profile to
    `adobe.icc`, confirm the mapping ignores its contents.
S03 **`.gam` source gamuts** (colprof `-s` accepts `.gam` from tiffgamut; ChromIQ
    ships `workflow/tiffgamut_runner.py`). Does `source_surface_from_profile`
    read `.gam`? If not, ≤4-ink builds route to colprof (fine) but CMY+N
    builds cannot use an image gamut at all. → repro.
S04 **Timing claims are inverted on this machine.** Baseline run
    (`builds/baseline-accurate-924p.log`): fast = **101 s**, accurate = 8.5 s
    in the same process (oracle cache warm). Fresh-process accurate run in
    progress. The Accuracy tooltip says fast "finishes in a few seconds" and
    accurate "takes several minutes longer". → measure all three modes in
    fresh processes, q=m and q=h, RGB 924 p and CMYK synthetic; fix the text
    to the truth.
S05 **The in-process oracle cache.** `_ORACLE_CACHE` lives for the app's
    lifetime. If `_oracle_cache_key` omits anything the oracle build depends
    on (k-rule, ink limit, a `.ti3` edited in place at the same path, source
    gamut edited in place) a later build silently reuses a stale colprof
    result. → read the key; mutate each ingredient; check hit/miss.
S06 **CV ladder ends at its boundary and does not say so.** Baseline chose
    ×0.25 — the smallest factor. When the optimum is at an end of the ladder
    the search is truncated; the log reports it as a choice. → add a boundary
    note or extend (gp already hill-climbs; plain accurate does not).
S07 **Outliers are named by DATA ROW, not by patch.** Log: "rows 757, 811";
    the chart calls them `SAMPLE_ID 757 / SAMPLE_LOC F20` and `811 / W1`. It
    matches here only because targen numbers rows 1..N. On an imported or
    merged `.ti3` the row number is meaningless to a person holding the sheet.
    → name SAMPLE_LOC (and ID) in the message. Also: are the two flagged
    patches (RGB 12/6/6 and 6/6/12, near-black) misreads or the dark-noise
    tail the noise model exists to explain? Compare with `noise_model` on.
S08 **Media white after `average_endpoints`.** Only `media_white_xyz` is
    replaced; the duplicate white ROWS keep their own XYZ, so the brightest
    duplicate now has relative L* > 100. What does A2B1(device white) return
    from the written profile — exactly L*=100/a=0/b=0 as ICC relative
    colorimetry requires? Argyll forces the fitted white to the PCS white
    (`icxLuLut` white-point set). → `xicclu -ff -ir` on device white for
    fast/argyll/accurate; also B2A1(L=100,0,0) → device white?
S09 **Small charts in accurate mode.** `_HOLDOUT_MIN_PATCHES = 120` skips CV
    silently; robust scale on 15–18 residuals; `noise_model` with **no
    duplicate patches** (i1Profiler-imported charts have none) →
    `estimate_xyz_noise` division/NaN? → run the 18 p CR30 chart, the 15 p
    chart, and a synthetic chart with zero duplicates, all four options on.
S10 **Lab-only `.ti3`** (no XYZ columns — i1Profiler CxF/TXT imports, some
    scanner paths) and `.ti3` with **XYZ + spectral of 106 bands at 3.33 nm**
    (the real ColorMunki file). Does `apply_spectral` resample correctly, and
    does `-i D65` / `-i F8` / FWA agree with colprof on the same file?
    → objective parity: build with colprof and the engine, look up the chart
    patches through both A2B1 (`xicclu`), report ΔE2000 median/p95.
S11 **FWA compensation** (`fwa.py`, 115 lines) vs Argyll's — paper white and
    light tints under `-f` with the real spectral chart. Same parity method.
S12 **ICC v4 correctness** (needs the spec, not memory): `wtpt` in v4 must be
    the D50-adapted media white with a `chad` tag; `desc`/`dmnd`/`dmdd` must be
    multiLocalizedUnicodeType; profile ID = MD5 with header bytes 44–47,
    64–67, 84–99 zeroed; lut16Type legacy Lab encoding is legal. Verify the
    bytes against ICC.1:2010 (color.org) and with Argyll `iccdump` + littleCMS
    if available. Also: non-ASCII descriptions (beta 8 fixed colprof's
    `Müller-Prüfdruck`; does the engine writer handle it in v2 AND v4?).
S13 **"Both (v2 + v4)" writes an untracked twin.** `builder.py` creates
    `<stem>-v4.icc` with `out.with_name` — outside the `Run` file model
    (CLAUDE.md: all path construction through Project/Run). Consequences to
    prove on screen: not archived on rebuild (§4 never-destroy rule), not in
    the File guide, not deleted with the run, Install installs only v2, the
    engine's `_on_engine_done` never mentions it.
S14 **Archive-before-overwrite on the engine path.** `_archive_superseded_profile`
    is called from the rebuild-over-verifications question; confirm the engine
    path archives an existing `.icc` (and twin) exactly like the colprof path.
S15 **No cancel, and quitting mid-build.** `_EngineThread` has no stop; the
    Build button is disabled and tabs locked. Close the window / quit during
    an accurate build: hang, crash, or a half-written `.icc`? (`icw.write_profile`
    — atomic or in place?)
S16 **Per-target settings.** The four engine rows round-trip through presets
    (`_m_collect_preset_data`) — are they in the per-target store
    (`per_target_widgets`)? On screen: set them in run1, switch to run2, back.
S17 **Option-by-option effect test (Q1 core).** For every `BuildSettings`
    field reachable from the UI in accurate mode, build default vs changed and
    prove (a) the expected tag/table changed and (b) nothing else did:
    quality/b2a_quality grids; `-r` smoothing shifts the CV ladder centre;
    `-V` no-op (matches colprof); `-ni/-no/-np`; `-nc` targ tag absent;
    `-Z` bits + default intent; `-A/-M/-C/-D` tags; `-u scale`; `-R`;
    `-k/-K` rules on CMYK (incl. `p` with 5 params); `-t/-T` intents;
    `-c/-d` viewing conditions actually reach the CAM02 mapping; `-nP/-nS/-nI`;
    `-i/-o/-f`; spectral_physics on RGB (must be a no-op, and SAY so);
    noise_model on clean (bit-identical) and noisy charts; render_style
    bijective; icc_version 2/4/both.
S18 **Light inks (CMYKcm, CMYKcmk).** `extra_ink_hues` and `ink_priors` treat
    channels ≥ 4 as spot hues (orange/green/violet). Light cyan is not a spot
    hue; it is a lighter cyan and should be used for smoothness in highlights,
    not gated by hue. Does the accurate separation use light inks sensibly?
    → synthetic CMYKcm printer through the battery machinery.
S19 **Ultra quality on 6–7 inks.** `a2b_grid` is stepped down while
    `grid**n > 2e6` without telling the user; `-q u` on CMYKOG → 11³…? Check
    the log says what grid was really used and the profile is valid.
S20 **Log lines are untranslated f-strings** in `builder.py` (the progress
    prefix matching depends on the English text). `tests/test_i18n.py` does
    not see them. Record; the "Consider remeasuring them" advice is user text.
S21 **Guided + accurate**: Guided has no engine rows (A-Q1). Also the Guided
    log never says which accuracy mode built the profile; the progress-bar
    label says "ChromIQ engine" only.
S22 **Scanner-measured printer chart in accurate mode.** 315 p, no spectral,
    no duplicates? Scanner noise is far above spectro noise — the noise
    detector (≥2× *spectro* healthy level) will engage; is that right for a
    scanner, and does the CV/robust machinery help or hurt vs colprof on this
    file? Objective: hold-out protocol (`benchmarks/heldout.py`).
S23 **Duplicate patches beyond white/black.** Accurate averages only the
    endpoints; charts carry many duplicates (targen `-e`, i1Profiler). Should
    duplicates be averaged (unbiased, √k) before fitting? colprof fits through
    all of them (equivalent to averaging under least squares only when
    weights are equal). Candidate improvement for Q2, measurable on the
    battery.
S24 **What the tooltip promises vs what happens**: "patches that look like
    misreads are … reported so you can remeasure them" (see S07);
    "the model's smoothing is tuned by testing it against held-back patches"
    (silent below 120 patches, S09); "expect several minutes" (S04).

## 5. Team and territories

Two agents run in parallel (the user asked for 2, explicitly superseding the
one-at-a-time rule for this job), then one reviewer at the end. Each gets its
own `CHROMIQ_SETTINGS_FILE`, its own `custom_output_path` sandbox, its own
report folder, and the standing permission to drive the real app on screen.

**Agent A — colour-science referee (numbers).** Owns S01, S02, S03, S05, S06,
S08, S10, S11, S12, S17 (the option matrix), S18, S19, S22, S23. Method:
objective parity and ground truth — colprof vs engine on the same real chart
through `xicclu`, the synthetic battery for CMY+N and light inks, ICC spec text
for v4, held-out ΔE2000 for "does accurate actually beat fast/colprof on real
data". Every number with the command that produced it.

**Agent B — user-journey breaker (screen).** Owns S04 (timing as the user
experiences it), S07, S09, S13, S14, S15, S16, S21, S24, A-Q1, A-Q3. Method:
the real app on screen: Preferences → Beta → engine + Maximum accuracy through
the consent dialog, Build Profile Guided and Manual, the scanner/camera tool in
printer mode with the same measurement, every engine-only row, presets, per-
target switching, rebuild-over-existing, quit mid-build, small charts, a Lab-
only chart, umlaut descriptions. Screenshots into `screenshots/`, looked at.

Both: staged reports every step; findings graded **BUG / GAP / INCONSISTENCY /
IMPROVEMENT / OK**, each with a repro that was run and what was measured on
screen vs offscreen.

**Reviewer (after fixes).** Attacks the fixes, re-runs the two agents' repros
against the fixed tree, checks regressions with the everyday tier and the
engine tests, and reads the diff for the beta 8 traps (mechanical edits,
colliding patches, guessed test names, duplicated helpers).

## 6. What the orchestrator will do with the findings

* BUGs with a repro → fix on the branch, with a test that fails before and
  passes after, then the everyday tier; `--runslow` before any beta.
* GAPs that are product decisions (Guided rows, scanner tool routing, black
  ink limit as a UI option, duplicate averaging) → implement the ones that are
  clearly inside the user's ask ("also used in the scanner tool", "more
  options"), report the rest with a recommendation. New user-facing message
  text goes through §M-PROPOSED (unified_measurement_management.md) where it
  is a measurement message; engine log lines are not §M territory.
* Never delete anything of the user's; archive-then-replace.
* Nothing touches the 26 uncommitted files of the unrelated report work on
  this tree; commits name only challenge files.

## 7. Explicit assumptions (no answer available, so stated)

1. "Maximum accuracy flavor" = `gammap_mode == "accurate"`; the env-only
   candidates (`CHROMIQ_ENGINE_NEXT`) are out of scope unless a shipped
   option depends on them.
2. Windows/Linux behaviour is out of reach here (macOS only).
3. No CMY+N hardware exists; CMY+N is judged on the synthetic battery and on
   structural checks (ICC validity via Argyll `iccdump`/`icclu`), which is
   the same evidence the engine shipped with.
4. The design specs in `docs/design/` do not cover the profile engine; the
   binding-spec rule applies only where a measurement message is touched.
5. Colour-science standard: D50, 2° observer unless an option says otherwise;
   ΔE2000 for judgement, ΔE76 reported where the code reports it.

## 8. Open questions for the critic

1. Which suspects are worthless (already covered by an existing test, or not a
   user-visible problem)? Name the test.
2. What did I miss? In particular: the B2A inversion in accurate mode, the
   dense shell, the K anchor via the colprof proxy (`fit_multiink_anchor`),
   the bijective renderer, and anything about how the profile behaves in a
   real CMM (ColorSync/littleCMS) rather than in Argyll.
3. Is the A/B split right, and is anything on B's list unmeasurable on screen
   (so it belongs to A)?
4. Which of the "more options" ideas are actually wanted by profiling
   practice (trusted sources: Argyll docs, ICC specs, X-Rite/basICColor
   manuals) and which are invented?
