# Brief — Reviewer: attack the fixes

You are the adversarial reviewer for the ChromIQ profile-engine challenge. Two
agents measured the SHIPPED engine (reports/agent-A/, reports/agent-B/); the
orchestrator then fixed things on branch `feature/engine-accuracy-challenge`
(commits 18a7b264, c425e05e, 93182073, ec3839f8 and later). Your job: find what
is wrong INSIDE the fixes — the newest code is the least examined. Repo
`/Users/Basti/develop/ChromIQ`, venv `.venv`. Read `CLAUDE.md` first.

Read: `reports/orchestrator/04-fixes-in-progress.md` and `05-handover.md`,
then `git log -8 --stat` and `git diff d3d1bd43 -- workflow/profile_engine
workflow/engine_builder.py ui/tabs/tab_profile.py ui/dialogs/scanin_dialog.py
ui/main_window.py ui/dialogs/settings_dialog.py`.

## Rules
* Another Claude session works in this checkout on measurement-report files
  (docs/beta8_open_items.md, docs/design/unified_measurement_management.md,
  workflow/measurement_messages.py, workflow/measurement_report*.py,
  tests/test_message_catalogue.py, tests/test_a_failed_report_says_so.py,
  ui/dialogs/measurement_report_dialog.py) — never touch, stage or revert them.
* Do not edit repo source. Report; the orchestrator fixes. Your scratch:
  `~/Desktop/ChromIQ-engine-challenge/work-R/`. Staged report:
  `reports/reviewer/01-findings.md`, appended per item; final
  `reports/reviewer/02-summary.md`.
* `~/ChromIQ` is the owner's real folder: copies only. Every measurement on
  his drive is developer test data, some measured wrong on purpose — never a
  referee. Judge with the synthetic battery (`benchmarks/`), colprof parity
  (`xicclu`), littleCMS (`PIL.ImageCms`) and the ICC spec.
* Any app launch: `CHROMIQ_SETTINGS_FILE` + `CHROMIQ_PRESETS_DIR` in your
  sandbox, `custom_output_path` in the sandbox. You MAY drive the real app on
  screen (visible window, real clicks, screenshots via QWidget.grab, look at
  them) with `scripts/engine_challenge/harness.py`; say what was measured on
  screen vs offscreen. No `--runslow`; single test files are fine.

## Attack list (each: repro that was RUN, verdict, file:line)
R1  White pin: `_pin_media_white` now applies a LOCAL correction (weight
    ((L−60)/40)²·(1−C/40)). Find a chart where it fails: a paper whose fitted
    white error is large (matte, dot gain 0.7 = battery S2), a chart with the
    white patch mis-measured, an ink device, an XYZ-PCS build (`-a x`). Does
    A2B1(device white) still read 100.00 ±0.02 and B2A1(100,0,0) → device
    white on every one? Does the correction create a visible kink between
    L 60 and 100 (second differences of a neutral ramp through A2B)?
R2  B2A L-axis scaling (`lab_b2a_in_tables`): does littleCMS and ColorSync
    honour the mft2 input curve the same way xicclu does (compare B2A1 at
    L=99.5, 100, 100.39 through all three)? Does the `gamt` tag, which uses
    the same input table, still read 0 at (100,0,0)?
R3  Hue-gated clip (`_hue_gated_seeds`): construct targets where the gate
    finds NO candidate within 25° (a printer with a hue gap) and targets
    exactly on the neutral boundary (chroma 4.9 vs 5.1) — continuity across
    that boundary in the written B2A1. Ink devices: does the gated seed respect
    the ink limit and the black limit (`channel_max`)?
R4  CV margin (`accuracy.py`): 3 splits when grid**n ≤ 250k, else 1. On a
    CMY+N chart (single split) is the margin rule worse than before? Run S5
    with old vs new (`_CV_FOLDS`, `_CV_MARGIN_FRACTION` monkeypatched) and
    read `k_tv_excess` (the S5 neutral-K smoothness regression 0.10 → 0.38 was
    NOT the black pin — the orchestrator's bisect log is in
    `builds/battery-S5-bisect.log`; continue from it).
R5  Black ink limit: `channel_max` reaches seeds, both GN passes, the retry
    cloud, the refit samples, the mapped tables and the final clip — find the
    path it does NOT reach (joint-sep candidate? `_seed_nearest` mesh for
    n>4? the multi-ink proxy anchor?). A 6-ink chart with `-L 40`: K ≤ 40 % in
    every B2A table?
R6  Duplicate averaging (`collapse_duplicates`): SAMPLE_LOC of the kept row;
    spectral rows averaged; the noise model path must NOT average; the
    `targ` tag still embeds the ORIGINAL text; a chart where every patch is
    duplicated (i1Profiler 2× charts).
R7  Sanity gates: `_sanity_gates` refuses white−black < 10 L*. A legitimate
    chart that trips it (a very low-contrast media, e.g. newsprint with L
    span 12 passes; find a real-world case under 10) — and the poor-fit
    WARNING at median > 2 ΔE00: a legitimate scanner-measured chart may sit
    at 2–3; is the wording right for that case?
R8  Ink limit capped at the chart's printed maximum: a CMYK chart whose
    darkest patch is 280 % but whose stamped limit is 300 % now builds at
    280 % — colprof builds at 290 % (stamp − 10). Which is right, and is the
    log line honest about the difference?
R9  `-s` vs `-S` and `-nP -nS`: the oracle now gets `-S` unless `sat_gamut`
    is False; the tab's Guided "Perceptual only" path → `gamut_src` → engine
    `sat_gamut=False` → B2A2 aliases B2A0. Verify the tab's plumbing
    end-to-end (Guided and Manual gamut-mode combos) and that a preset saved
    before this change still loads.
R10 gamt tolerance 3 ΔE: a soft-proof gamut warning in Photoshop/littleCMS
    (proofing transform with GAMUTCHECK) — does it now flag near-surface
    colours late? Quantify on a synthetic chart with known truth.
R11 Timeouts + child registry (`_run_argyll`): kill the child while it runs
    (`terminate_argyll_children()` from another thread) → the build must end
    with a clear "Using the engine's own rendering (colprof was stopped)" or
    an error, never a hang; the temp dir is removed.
R12 Quit guard (`main_window._ask_before_quitting_on_a_build`): on screen —
    start an accurate build, Cmd-Q, expect the question; "Keep building"
    keeps the window and the build finishes; "Quit anyway" quits without an
    orphan colprof (`pgrep colprof`) and no temp dir. Also `test_the_warning_
    sign_is_ours_everywhere.py` and the button-fitting rules.
R13 Scanner tool routing (`_printer_profile_builder`): on screen with the
    engine on: the preview line, the log's first line, the "Profile check
    complete" line from the engine, the self-check verdict on a misaligned
    chart (does the engine's max/mean fit error trip the same thresholds as
    colprof's peak/avg? compare numbers on the same file), the stash/restore
    on failure (observer refusal no longer applies — find another failure).
R14 Archive-on-rebuild (`_archive_previous_build`): rebuild in Guided,
    rebuild in Manual, rebuild when a verification exists (must not archive
    twice), rebuild with the measurement of ANOTHER run selected, rebuild when
    `old/` already has a folder with the same timestamp.
R15 `_restore_defaults` now resets the kgen spins and four engine rows —
    does loading a preset that lacks those keys, then switching run, behave?
R16 i18n: every new/changed tr() string has 12 catalogue entries (run
    `python scripts/i18n_extract.py --missing <code>` for all 12 and
    `pytest tests/test_i18n.py`); German uses Du; the Accuracy tooltip's new
    timing sentences agree with `reports/agent-B/01-findings.md` B-34.
R17 The engine's log lines (`builder.py`) are f-strings, untranslated by
    design (progress prefixes) — did any of the new lines slip a `tr()` into
    `_STAGE_PCT` matching, or break the percentage monotonicity? Feed a real
    build's lines through `_PercentProgress` and check monotone.
R18 Anything the orchestrator wrote a test for: mutate the code (revert one
    line) and prove each new test actually fails — a test that cannot fail is
    not a test (`feedback_a_mutation_must_be_proven_to_land`).

Return a ≤ 50-line summary: findings table (R-NN, grade BUG/GAP/OK, one
line, repro pointer) and the three most dangerous things you found.
