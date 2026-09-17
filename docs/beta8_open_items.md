# beta 8 — the register of everything found, and what happened to it

**This file is enforced by `tests/test_beta8_nothing_is_forgotten.py`.** It is not
a summary anybody has to remember to update: the release tier
(`pytest --runslow`) goes RED while any release-blocking item is still `OPEN`,
and the everyday tier goes red if this file is internally dishonest — a `FIXED`
item naming a test that does not exist, or a `DEFERRED` item with nobody's name
against it.

Written because a checklist in someone's head is not a checklist. CLAUDE.md
already records what a stale document costs here: the "use `-n 4`, do not raise
it" note was wrong for sixteen days and cost five minutes a run, because nobody
came back to it.

## The rules

* **status** is one of `FIXED`, `DEFERRED`, `OPEN`.
* `FIXED` must name at least one test that exists and proves it. "I checked by
  hand" is not evidence — a fix with no guard is a fix that comes back.
* `DEFERRED` must name **who** decided and **why**. A deferral nobody owns is an
  item that has been forgotten with extra steps.
* `blocks release: yes` means beta 8 does not ship while this is `OPEN`.

---

### B8-01 · An under-exposed scan builds a profile with no warning at all, and the app rates it best
- blocks release: yes
- status: FIXED
- found by: Agent B, `05-stress-and-edge-cases/FINDINGS.md` (F-8); re-derived on
  Knut's own scanner files by Agent H, `09-silent-bad-profiles/`
- detail: every guard in the window is scale-invariant and an exposure slip is
  pure scale. Re-measured on Knut's own Wolf Faust sheet, read through the same
  `-F` corners so exposure was the only variable: at ×0.70 coverage is
  unchanged, agreement moves +0.9839 → +0.9838, the clipped share does not move
  by one patch, colprof's self-check reads 1.99 against limits of 30/12 — and
  the profile is **21.70 ΔE** out against a correct read. ×0.18: 177.91 ΔE,
  peak 335.70, still silent. One correction to the original report: on real
  material the self-check does not go DOWN as the scan darkens, it creeps up
  (1.93 → 2.59); it never approaches a limit either way.
- fix: `scan_read_check.highlight_level` — the median of the largest device
  channel over the patches the reference calls near-white, floored at 60
  (`scanner_min_highlight`). Chosen against 74 reads: Knut's ten real sheets
  72.92–79.82, the app's own demo for all 25 targets 80.96–94.34, nine
  legitimate variations 69.57–83.86, against ×0.70 at 55.85/52.43. Three
  cheaper measures were built and thrown away because a legitimate scan beat an
  under-exposed one on each; the numbers are in the module and in
  `tests/test_a_dark_scan_is_not_a_good_one.py`. Wording is §M-PROPOSED
  (M-SCAN-DARK) and unapproved.
- evidence: test_the_shipped_floor_matches_every_level_measured,
  test_the_three_older_guards_cannot_see_an_exposure_slip,
  test_the_window_names_a_dark_scan_and_says_nothing_about_a_good_one,
  test_a_low_key_target_is_declined_and_never_accused,
  test_a_cast_does_not_move_the_level_but_darkening_does,
  test_the_floor_keeps_a_real_margin_under_the_worst_legitimate_scan
  test_the_three_older_guards_cannot_see_an_exposure_slip,
  test_the_window_names_a_dark_scan_and_says_nothing_about_a_good_one,
  test_a_low_key_target_is_declined_and_never_accused,
  test_a_cast_does_not_move_the_level_but_darkening_does,
  test_the_floor_keeps_a_real_margin_under_the_worst_legitimate_scan

### B8-02 · A 10-degree hand-held tilt is accepted as a correct placement
- blocks release: yes
- status: FIXED
- found by: Agent E, `06-every-target-type/FINDINGS.md`
- detail: **WORSE THAN FIRST MEASURED — see the update below.**
  Originally: 8 of 207 hard cases accept a wrong quad, 0.57 to 1.27 patch pitches
  out. `corners_from_candidate` reconstructs an AFFINE, which cannot represent a
  keystone, and every gate passes it because a rank correlation is blind to
  shear. The window offers "a scan **or photo**". Agent C's lighting fix (F3)
  must not ship before this: measured, it adds +16 correct but +2 new wrong, and
  both new wrong ones are this case.
- evidence: test_the_quad_the_recogniser_can_return_is_always_a_rectangle,
  test_a_correct_placement_has_no_seating_drift,
  test_a_flat_chart_with_no_texture_is_not_refused_for_being_flat,
  test_a_half_pitch_shift_is_seen,
  test_a_keystone_is_seen_although_every_older_gate_passes_it,
  test_the_true_corners_of_the_same_photograph_are_not_refused,
  test_auto_align_refuses_the_keystone_and_names_the_reason,
  test_auto_align_still_applies_a_good_answer_and_records_its_drift,
  test_the_gate_does_not_move_when_the_user_changes_the_sample_area,
  test_a_chart_too_small_to_judge_says_nothing_rather_than_refusing,
  test_an_unreadable_image_is_no_evidence_and_no_crash,
  test_the_limit_sits_between_the_two_measured_populations,
  test_the_refusal_has_words_of_its_own_and_is_not_approved_yet,
  test_every_reason_the_module_can_return_is_the_set_we_have_words_for
- update (Agent G, adversarial round, 2026-09-04): measured with a proper
  pinhole camera model, so "tilt" has degrees on it, and with a COMPOUND
  pitch+yaw tilt — which is what a hand actually does, where Agent E tested one
  axis. Auto align starts accepting wrong placements at **4 degrees, not 10**.
  In the real window at 8 degrees, **20 of 23 targets accept and 10 are more
  than half a patch pitch out** — reading the neighbouring patch — while the
  window prints an agreement of 0.97-1.00 beside its own sentence "anything
  below 0.80 is refused". Knut's LaserSoft target is 0.921 pitch out at 0.98.
  Costed end to end on Knut's real Wolf Faust scan at 10 degrees: 33 of 288
  patches move by more than 3 dE00 (six by more than 10), and the resulting
  scanner profile differs from the correct one by a median **2.23 dE00** with
  **320 of 343 device grid points over 1 dE00**, against a measured harness
  floor of 0.78.
- also open, same root: **lens distortion was never tested by anyone.** It is
  different in kind — it bends straight lines, so NO homography fits at any
  placement. With the best possible quad, an ordinary phone-lens barrel already
  costs 6 patches over 3 dE, a wide one 29, pincushion 39; pincushion is
  ACCEPTED 0.423 pitch out at rho 0.98. Control at zero distortion: zero.
- and the honest limit on the "no machinery needed" conclusion (B8-27's
  neighbour): on both real ColorChecker photographs and both freely-licensed
  real IT8 photographs, Auto align REFUSES outright. The conclusion that one
  quad suffices rests on a quad fitted by numerical optimisation, which a user
  cannot obtain through the app.
- the fault, corrected: `corners_from_candidate` does not build an affine. Its
  own arithmetic (`t1=xscale·c, t2=yscale·s, t4=−xscale·s, t5=yscale·c`) gives
  the quad's two edge vectors a dot product of EXACTLY ZERO — the placement the
  recogniser can return is always a rotated RECTANGLE, five degrees of freedom
  where a placement needs eight, with no shear available at all. So no gate can
  find this in the quad's own shape; the evidence has to come from the image.
- the fix: `workflow.scan_auto_align.seating_drift` searches +/-0.5 pitch in
  CHART coordinates for the offset that minimises dispersion inside the sample
  box scanin actually reads, discounts each answer by how much moving helped,
  averages over a 4x4 grid of chart regions and reports the worst region.
  Noise cancels inside a region; a keystone does not. Limit 0.075 patch pitches,
  0.12-0.15 s on Knut's largest scans.
- the measured separation, over 328 correct and 106 wrong placements from three
  populations (600 tilt views of 25 targets, 216 CROSSED bow x lens x tilt
  views, 38 challenge cases plus Knut's two real scans and nine legitimate
  degradations): correct <= 0.0631 (Knut's own scans 0.0175 and 0.0139), wrong
  by more than half a pitch >= 0.0989. EVERY limit from 0.065 to 0.095 gives
  zero false refusals in 328 and catches 106 of 106.
- regression evidence: everyday tier 10293 passed / 0 failed (baseline 10280,
  +13 being the new test file); the scanner sweep run on both trees minutes
  apart gave an identical 27 PASS / 7 FAIL with ZERO PASS->FAIL flips; all 23
  targets still place at tilt 0, worst corner 0.004-0.075 both ways. At 8
  degrees compound tilt: 19 placed of which 10 were more than half a pitch out,
  becomes 6 placed and 0 wrong.
- `-p` was measured and NOT shipped: on it8Wolf it is worse at every tilt where
  both answer (0.020 -> 0.037 at 0 degrees, 1.469 -> 4.492 at 15). That
  contradicts Agent C's single case, which was one target at one angle.
- residual, said plainly: 126 of 252 placements in the 0.25-0.50 pitch band are
  still accepted — lens-distorted photographs at low tilt, where the sample box
  overhangs its patch but does not reach the neighbour. Dropping the limit to
  0.065 would catch 134 of them at still-zero false refusals. Basti's call, and
  Agent L's photograph work may make it moot.

### B8-03 · The profile self-check has no floor and no NaN guard
- blocks release: yes
- status: FIXED
- found by: Agent B, `05-stress-and-edge-cases/FINDINGS.md`; reproduced by
  Agent H, `09-silent-bad-profiles/`
- detail: reproduced exactly. Every `SAMPLE_ID` rewritten to `A1` leaves one row
  and scores `peak err = 0.007339, avg err = 0.007339`; every value rewritten to
  `0.00` sends colprof's Powell fit to `residual error = nan` and lands a 26 KB
  profile whose white point is `nan nan nan`, reported as
  `peak err = 0.000000, avg err = nan` — which `_PROFCHECK_RE` could not match,
  so `found` was empty and the verdict returned silently.
- fix: **not** an error floor — that was measured and rejected: the app's own
  bundled ColorChecker demo builds at `avg err = 0.059311`, only eight times the
  degenerate 0.007339, with a cLUT build on real data at 0.462 in between.
  Instead (a) `scan_read_check.fit_support` counts DISTINCT reference colours
  and warns under 10 (`scanner_min_fit_support`) — 1 for both degenerate
  references, 21 for the smallest target anybody ships — before colprof spends
  two minutes on it, and (b) `_PROFCHECK_RE` now matches `nan`/`inf` and
  `_selfcheck_verdict` warns and grades the Install button when the fit is not a
  finite number. Wording is §M-PROPOSED (M-SCAN-FIT-UNSUPPORTED,
  M-SCAN-SELFCHECK-UNUSABLE) and unapproved.
- evidence: test_a_reference_of_one_colour_cannot_support_a_profile,
  test_the_support_floor_clears_the_smallest_target_anybody_ships,
  test_an_error_floor_would_not_have_worked,
  test_the_fit_line_is_read_even_when_colprof_answers_nan,
  test_a_self_check_that_is_not_a_number_warns_and_grades_the_button,
  test_a_perfect_self_check_on_one_colour_is_still_caught_before_the_build
  test_the_support_floor_clears_the_smallest_target_anybody_ships,
  test_an_error_floor_would_not_have_worked,
  test_the_fit_line_is_read_even_when_colprof_answers_nan,
  test_a_self_check_that_is_not_a_number_warns_and_grades_the_button,
  test_a_perfect_self_check_on_one_colour_is_still_caught_before_the_build

### B8-04 · A project name ending in _<digits> silently loses its exports
- blocks release: yes
- status: FIXED
- found by: Agent B (`Moab_Satin_240`); reproduced and fixed by Agent I
- detail: loses `exports/`, loses the meta stamp, and hands a non-existent
  `.ti2` to `chart_finished`. The only symptom is three missing log lines.
  WIDER THAN REPORTED — driven in the real Create Chart window, one page each:
  `Paper_1`, `Paper_01`, `Canon_Pro1000_2026` and `IT8_2` fail too, and
  `_stamp_chart_meta` raises a FileNotFoundError the user never sees. `240` (no
  underscore) was always fine. `_on_generate_finished` stripped a trailing
  `_NN` off the page bitmap because printtarg numbers a MULTI-page chart
  `<stem>_01.tif` — a single-page chart has no number, so the name's own digits
  were eaten. `core.file_manager.chart_stem_from_pages` now asks the disk which
  candidate the chart's own tables are called instead of guessing from the
  name. SIBLING, same cause, also fixed: `margin_inspector._page_index_of` read
  `Moab_Satin_240.tif` as page 240 and silently dropped the patch width out of
  the margin report.
- evidence: test_a_single_page_chart_keeps_the_digits_the_user_typed,
  test_a_multi_page_chart_still_loses_its_page_number,
  test_a_multi_page_chart_whose_name_ends_in_digits_loses_only_the_page,
  test_the_generate_handler_no_longer_guesses_from_the_name,
  test_the_margin_inspector_does_not_read_a_name_as_a_page_number

### B8-05 · Auto align could never work on any bought target
- blocks release: yes
- status: FIXED
- detail: all eight `data/scanner_targets/*.cht` carried an absolute edge length
  in XLIST/YLIST column 2 where ArgyllCMS defines a strength relative to the
  strongest tick. scanin answered `r0 = nan ... 0 candidate rotations`. Knut's
  geometry is untouched; one column was normalised in place.
- evidence: test_every_bundled_edge_list_is_normalised_the_way_argyll_defines_it,
  test_the_recogniser_finds_every_bundled_standard_target

### B8-06 · Auto align refused every target whose .cht carries an EXPECTED block
- blocks release: yes
- status: FIXED
- detail: `expected_luminance` preferred the chart's generic EXPECTED block over
  the user's own reference, so the demo image was scored against the REAL
  target's colours (ColorCheckerSG agreement 0.049). The reference now wins on
  how much of the CHART it covers. Also reads SAMPLE_LOC, and LAB when there is
  no XYZ.
- evidence: test_the_reference_beats_the_chts_expected_block,
  test_a_reference_that_names_patches_in_sample_loc_is_read,
  test_the_chart_decides_which_reference_wins_not_the_expected_block,
  test_a_short_reference_never_loses_colours_the_chart_already_had

### B8-07 · The demo scan painted only the patches, not the sheet
- blocks release: yes
- status: FIXED
- detail: a `.cht`'s XLIST/YLIST describes edges on the physical sheet, and on
  most targets some are the paper border. The recogniser was matching edges
  nobody had drawn. 25 of 25 targets now place the grid.
- evidence: test_make_test_scan_reads_back,
  test_the_recogniser_finds_every_bundled_standard_target

### B8-08 · An accepted answer was extrapolated to the fiducials twice
- blocks release: yes
- status: FIXED
- detail: with "Use fiducial marks" ticked — what a standard target defaults to
  — the grid landed 53 px above the patches and the `-F` corners handed to
  scanin sat at y = -4.8, off the image.
- evidence: test_an_accepted_answer_is_not_pushed_out_to_the_fiducials

### B8-09 · The alignment diagnostic drew no outline, so a correct read looked misaligned
- blocks release: yes
- status: FIXED
- detail: `-dipn` asked for the image, the sampled pixels and the names, never
  for an outline (`o`). The only visible edge was a colour-vs-greyscale step and
  the patch edge was invisible on a third of edges. Knut read a correct
  placement as "clearly misaligned" from exactly that picture. Now `-dipon`, so
  Argyll draws the box it actually read and the diagnostic stays an independent
  witness.
- evidence: test_diag_adds_flag_and_trailing_path

### B8-10 · A refusal was undiagnosable from the log
- blocks release: no
- status: FIXED
- detail: `log_tail`, `rejected`, `candidates`, `rho` were captured and never
  written, and `_run_scanin` discarded scanin's return code and error line. A
  77 KB tester log could say only "not-recognised", nine times.
- evidence: test_a_refusal_records_what_it_found

### B8-11 · Zooming the diagnostic interpolated away the edges being judged
- blocks release: no
- status: FIXED
- detail: smoothing is now applied only when shrinking. Measured: edge rise 3.50
  device px smoothed against 2.49 hard at the fit Knut used, 4.86 against 0.00
  at 4x; below 1:1 the two are indistinguishable.
- evidence: test_the_diagnostic_is_only_smoothed_when_it_is_shrunk

### B8-12 · Dragging the mesh was laggy on a dense chart
- blocks release: no
- status: FIXED
- detail: 988 patches in Neutral went from 21 fps to 39 fps. Cell geometry is
  cached, and the +2 px under-stroke is drawn aliased while the button is down —
  the accent the eye aims with stays smooth. Basti chose this over aliasing both
  passes (64 fps) after looking at the three-way comparison.
- evidence: test_only_the_under_stroke_is_aliased_while_the_button_is_down,
  test_an_appearance_with_no_under_stroke_draws_a_drag_exactly_as_it_rests,
  test_moving_the_quad_does_not_rebuild_but_does_move

### B8-13 · The ICC filename and the embedded description disagree when -D is empty
- blocks release: no
- status: FIXED
- found by: Knut, beta.7; reproduced by Agent B and again by Agent I
- detail: file `ScannedIT8LSTarget01-p1s1-scanner.icc`, description
  `ScannedIT8LSTarget01 scanner`. With `-D` filled the `-p1s1-scanner` segment
  vanishes entirely — two different schemes. `-p1s1-` is explained nowhere.
  There is one scheme now, and it is the one the `-D` path already used: a
  single `_default_profile_name(base)` feeds the file name AND the embedded
  description, so they cannot drift. `-p{n}s{k}` stays on the per-shot reads of
  a multi-page or averaged set, where it disambiguates something, and is gone
  from the ordinary one-scan case where it was always literally `p1s1`.
  NOT the rule in `03-scanner-naming-defaults/README-naming.md` verbatim — that
  file proposed appending the suffix conditionally to a name built the old way;
  building both strings from one source removes the divergence by construction
  instead of keeping the two sites in step. Old profiles are untouched and old
  projects still open: nothing is renamed on disk, and a rebuild archives the
  profile it replaces into `old/<date>/` under the NEW stem.
- evidence: test_one_scan_of_one_page_writes_no_p1s1_anywhere,
  test_the_file_and_the_description_are_the_same_string,
  test_several_shots_keep_the_suffix_that_disambiguates_them,
  test_a_typed_name_still_wins,
  test_a_profile_about_to_be_replaced_is_still_archived_under_the_new_name

### B8-14 · The Strip & row labels frame does not say which controls reach which labels
- blocks release: no
- status: FIXED
- found by: Knut, beta.7; measured from the ink by Agent B
- detail: underline / thickness / distance / rotation / label-offset touch strip
  labels only; Font, Size and Bold touch both. One tooltip is actually wrong.
  Table in `04-chart-layout-ui/README.md`.
- fix: the untrue sentence is gone — the "Indicator font" tooltip said
  *"Typeface, size and style of the strip letter labels"* while Font, Size and
  Bold move 11 086 to 126 162 pixels of ROW-label ink and re-lay the page. It
  now names both sets, says Bold reaches both, and says Italic greys out for
  fonts with no italic face (which is both bundled ones — Agent B's F-4, not a
  bug). Alongside it, one grey sentence INSIDE the frame names every control's
  reach, in the frame's own words. **That paragraph was retired the next day and
  the frame now says the same thing by its SHAPE — see B8-21 §4.** Basti,
  2026-09-03: *"keep the first note, drop the second, and rule on sub-frames…
  the paragraph is the option I'd argue against — it's correct, and correct is
  not the same as clear."* What survives from B8-14 is the untrue tooltip,
  fixed and still guarded here.
- evidence: test_the_font_tooltip_no_longer_says_strip_only,
  test_the_font_tooltip_names_both_sets_of_labels,
  test_the_font_tooltip_says_bold_reaches_both,
  test_the_frame_groups_the_controls_by_what_they_reach,
  test_both_sub_frames_are_inside_the_strip_and_row_labels_frame,
  test_no_sub_frame_title_claims_italic_does_anything

### B8-15 · The app accepts a scanin diagnostic image as a scan
- blocks release: no
- status: FIXED
- found by: Agent D; Knut did it in his own log at 15:30; fixed by Agent I
- detail: produces a FALSE failure — "sample boxes sit on patch edges, worst
  73.80 %" — on a read that is fine. Recognised from the PIXELS, not the file
  name: Knut's file was written by his own scanin command and is called nothing
  ChromIQ would write. `workflow/scan_diagnostic_image.py`, measured at full
  resolution over 3 diagnostics and 20 real scans and photographs — a
  diagnostic is 60.2–66.2 % exactly neutral and 0.74–3.38 % Argyll's annotation
  colour, and no real scan in the set had one pixel of that colour. Both
  signatures must hold: the neutral fraction alone reached 45.25 % on a JPEG at
  quality 12. WARN, NOT REFUSE — the harm is a false verdict, not a bad
  profile, and a detector with a 3-file positive sample must not be able to
  lock a user out of their own scan. Said at LOAD time, so it is met before the
  false verdict rather than after it. WORDING IS §M-PROPOSED (M-SCAN-DIAGNOSTIC)
  and is not approved.
- evidence: test_a_diagnostic_image_is_recognised,
  test_a_diagnostic_scanin_really_wrote_is_recognised,
  test_a_grey_picture_with_no_annotation_is_not_a_diagnostic,
  test_a_colourful_picture_containing_the_marker_colour_is_not_a_diagnostic,
  test_it_is_a_warning_and_not_a_refusal

### B8-16 · Loading a scan that does not match the Target type says nothing
- blocks release: no
- status: FIXED
- found by: Agent B; confirmed and fixed by Agent I
- detail: silent at load, `can_run` True, mesh drawn confidently over the wrong
  patches. Pressing Run DOES fire two guards, so it is not a silent wrong
  profile — but the window looks authoritative in the meantime. Also: the log is
  not cleared on a target-type change, so a stale demo note lingers.
  NO LOAD-TIME MISMATCH DETECTOR IS PROPOSED, and that is deliberate: at load
  the app has read nothing and cannot honestly know, and a detector that
  guessed would be a new kind of untrue statement. What it does now is stop
  being silent — it names the file and its pixel size, names the target it is
  about to be read AS and how many patches that target has, says nothing has
  been checked yet, and names the button that can answer the question. On the
  matching case as well as the mismatched one, because a line that appears only
  when something is wrong teaches the user nothing about what right looks like.
  The stale log is cleared in the same block that already cleared the scan.
  WORDING IS §M-PROPOSED (M-SCAN-LOADED) and is not approved.
- evidence: test_the_window_reports_a_load_and_names_the_diagnostic,
  test_the_log_is_cleared_when_the_target_type_changes

### B8-17 · Unparseable references blame the wrong thing
- blocks release: no
- status: FIXED
- found by: Agent B; reproduced and fixed by Agent I
- detail: reports "check the folder is writable" when Argyll's real reason is
  two lines up in the log. Both of Agent B's cases reproduced in the real
  window and both now answered in their own terms: "Read 48 sets, expected 288
  sets" becomes "this reference file says it lists 288 colours and then gives
  only 48", and `cgats.add_kword(), keyword '"' is illegal` becomes an encoding
  answer. Any OTHER CGATS read failure now names the file and repeats
  ArgyllCMS's own sentence rather than guessing; only a WRITE failure still
  mentions the folder, which is the case that message was ever about.
  AND THE UTF-16 CASE IS RESCUED BEFORE IT FAILS: `core.text_io` was already
  logging "byte-order mark says UTF-16 or UTF-32, not UTF-8" while the window
  said "Ready — 288 patches, reference loaded" — the app knew and threw the
  knowledge away. `reference_convert.utf8_reference` rewrites such a file as
  UTF-8 at pick time, under a `-utf8` stem so the copy can never overwrite the
  user's own file, and reuses the existing approved "Converted … to a reference
  ChromIQ can read." sentence. A byte-order mark left anywhere INSIDE the text
  makes scanin answer "field XYZ_X is wrong type"; every U+FEFF is stripped and
  the guard hands the rescued file to the real scanin.
- evidence: test_an_incomplete_reference_says_so_with_both_numbers,
  test_a_reference_that_is_not_plain_text_says_so,
  test_any_other_read_failure_repeats_argylls_own_words,
  test_a_write_failure_is_still_the_one_that_mentions_the_folder,
  test_a_utf16_reference_is_rewritten_before_anything_reads_it,
  test_the_rewritten_copy_can_never_be_named_what_the_original_is,
  test_the_rewritten_reference_really_reads_in_argyll

### B8-18 · sample_frac means linear in one place and area everywhere else
- blocks release: no
- status: DEFERRED
- decided by: Basti
- because: correcting it moves the reported placement agreement for every
  existing user, in BOTH directions (measured: worst figure moves at most 5.5
  points, and on LaserSoft at 40 % it moves UP, 82.38 -> 87.92). That is a
  behaviour change, not a bug fix, and it is his call rather than mine. It is
  real: `placement_probe.py:251` reads it linearly, the marquee,
  `cht_with_sample_area` and the flank grid read it as area, and it makes two
  shipped sentences false (`scanin_dialog.py:1426` and `:1464`).
  `scan_auto_align._agreement` reads it linearly too and must move in the same
  commit.
- evidence: —

### B8-19 · Is shaper+matrix the right default profile type for a scanner?
- blocks release: no
- status: DEFERRED
- decided by: Basti
- found by: Knut — *"Did you ask claude to verify if the shaper + matrix is the
  best default for the scanner window?"*, then *"I get very nice profiles just by
  changing to cLUT - Lab table"*, *"I guess it is desired that the profile for a
  scanner is not limited to the colors it was profiled with"*, and *"Maybe the
  help text for the profile type should give recommendations for when to use the
  LUT types"*. Measured by AGENT-AD, 2026-09-04.
- because: the question is now MEASURED and the default is confirmed — see the
  detail below. What is left is a design ruling that is Basti's: the replacement
  help text, drafted from these numbers and awaiting confirmation in
  `docs/design/unified_measurement_management.md`. No behaviour is proposed for
  change, so nothing is blocked on this.
- detail: **MEASURED, on two REAL scans, and the answer is YES — keep it, but
  the help text is wrong and one sibling option has a hard defect.**
  Method: 80/20 seeded split of a Wolf Faust IT8 (288 patches, real Epson scan)
  and a LaserSoft DCPro (864, real scan); profile fitted on a sample of the
  80 %, every ΔE00 taken on the 20 % the fit never saw
  (`profcheck -k -I a`); the self-check on the fit data recorded beside it. The
  self-check is not evidence — B8-03's trap reproduced here on real material:
  at 24 patches `-al` reads **0.28** against itself and **2.59** on held-out
  data, nine times worse than it claims.
  Hold-out avg ΔE00, Wolf Faust IT8, mean of five seeded splits:

  | fit patches | -as shaper+matrix | -am matrix | -ax cLUT XYZ | -al cLUT Lab |
  |---|---|---|---|---|
  | 24  | **1.49** | 9.79 | 2.93 | 2.59 |
  | 48  | **1.25** | 8.97 | 1.68 | 1.68 |
  | 96  | 1.14 | 9.00 | **1.06** | 1.13 |
  | 192 | 1.07 | 8.83 | **0.69** | 0.79 |
  | 230 | 1.08 | 8.82 | **0.64** | 0.75 |

  and the same method on the 864-patch LaserSoft DCPro, also five seeded splits:

  | fit patches | -as shaper+matrix | -am matrix | -ax cLUT XYZ | -al cLUT Lab |
  |---|---|---|---|---|
  | 24  | **1.29** | 8.70 | 2.65 | 2.06 |
  | 48  | **1.07** | 8.09 | 1.71 | 1.24 |
  | 96  | 0.98 | 7.81 | 1.00 | **0.97** |
  | 192 | 0.96 | 7.81 | **0.65** | 0.75 |
  | 691 | 0.93 | 7.80 | **0.52** | **0.52** |

  So the crossover sits near **100 patches**: below it shaper+matrix wins, above
  it a cLUT wins by roughly a third, and at a genuinely large target it is
  **nearly twice as accurate** (0.52 against 0.93). **Knut is right** that a cLUT gives him
  better profiles on a full IT8 — that is a held-out result, not a self-check
  artefact. Matrix-only is never competitive and returns L* = −90.7 for device
  blue; it is not a safe option.
  **But his other requirement rules out the option he picked.** He wants the
  scanner's hardware to be the limit, not the profile. The IT8's own white is
  only device RGB ≈ 80/79/82 of 100, so the top ~18 % of the scanner's range is
  extrapolation. Measured through `xicclu -ff -ir -pl`, neutral device ramp:
  `-as` runs L* 101 → 119.6 and `-ax` 101 → 119.5, monotonic, while **`-al`
  clamps at L* 100.39 from device 82 upward** — every value brighter than the
  chart's white collapses to one lightness. ArgyllCMS documents exactly this
  (`colprof.html`, `-u`), and `-ax` is the type its own Scenarios page
  recommends for input devices. `-al -u` restores the range (85.9 → 100.0), and
  ChromIQ already exposes `-u` under Advanced ▸ white point, defaulting to none.
  Two more things worth keeping: on the grey scale held out as a block (GS00–23
  removed from the fit) the cLUTs are ~25 % better than shaper+matrix
  (0.78 / 0.82 against 1.07 avg ΔE00, worst patch GS23 for all three); and
  across a DIFFERENT target the three usable types are indistinguishable
  (3.76–4.11 avg ΔE00), so changing media costs four units where the profile
  type costs a few tenths.
  **Conclusion: the factory default stays Shaper + matrix.** It is the most
  accurate type below ~100 patches, within 0.4 ΔE00 of the best above it, never
  clips the highlights, and is the only type that is never badly wrong. What is
  actually wrong is the guidance: the shipped tooltip claims Lab "sometimes
  gives slightly smoother neutrals", and on neutrals the two cLUTs are inside
  each other's noise in both directions (0.67 Lab against 0.66 XYZ on the 192-
  patch hold-out, 0.89 against 0.71 on the maximin arm, 0.78 against 0.82 on the
  block-held-out grey scale) — so it is a claim the data does not carry either
  way. The tooltip also says nothing about the lightness ceiling, which is the
  one difference between the two that IS reliably measurable, and it gives the
  user no rule for when to switch away from the default at all.
- prepared: a replacement tooltip, written from these numbers and translated
  into German, is drafted in `docs/design/unified_measurement_management.md`,
  section "⏳ Awaiting confirmation — Profile type help text…".
  **Basti rules on the wording.** Nothing else is proposed: no default is
  changed, so no settings migration is needed.
- then: **Basti ruled that the answer must be reflected in the APP**, not only
  in a reply to Knut. That is B8-56, which builds it — the rewritten help, the
  "(recommended cLUT)" marker and the live patch-count note. The wording is in
  the app but is still **PROPOSED, not approved**; this item stays DEFERRED on
  exactly one thing, which is Basti's ruling on the words themselves.
- evidence: `beta 8/24-scanner-profile-default/` — `cv_profile_type.py`
  (the harness), `cv/results.json` (every run), `summarise.py`,
  `HOW-TO-RERUN.md` (the commands), and `beta 8/_progress/agentAD.md` §04–§09.

### B8-53 · Knut: the green colprof command frame does not change with profile type
- blocks release: no
- status: OPEN
- found by: Knut — *"Also, the green frame showing the colprof command does not
  change when I change settings like profile type."* Investigated by AGENT-AD,
  2026-09-04.
- detail: **NOT REPRODUCED on beta 8, and the frame is not lying about the
  run.** Drove the real `ScannerProfileDialog` on screen. Changing Profile type
  moves the frame through `-as → -am → -ax → -al` in scanner mode and again in
  printer mode; Quality moves `-qm → -ql/-qh/-qu`; the description moves
  `-D`/`-M`; and 6 of 6 inline Advanced controls that add a flag move it too
  (`-ni -no -np -nc -R` and the white-point `-u`). The three that did not are
  the metadata gates with their text fields empty, which legitimately add
  nothing. Preview and the real build share ONE argument builder
  (`scanner_colprof.make_profile_params` → `ProfileBuilder._build_args`,
  `scanin_dialog.py:2546` for the preview, `:5315` and `:5397` for the two build
  paths) — captured the argv the live dialog handed `ArgyllRunner` and it
  matches the frame letter for letter. That also explains why switching type
  really does change his profiles. The wiring is byte-identical in
  `v4.1.5-beta.7`, so it should not have failed there either.
- next: ask Knut which version and platform he saw it on and what the frame
  said, rather than closing this as fixed. Beta 8 rebuilt this window (Advanced
  became an inline section), so a beta.7 or earlier report cannot be dismissed
  from a beta 8 run alone.
- evidence: `beta 8/25-preview-does-not-change/` — `drive_preview.py`,
  `drive_run_vs_preview.py`, `drive.log`, `shots/`. Existing guard:
  test_profile_type_clut_lab_high_maps_and_previews.

### B8-20 · The diagnostic always renders into a fixed 920x560 view
- blocks release: no
- status: DEFERRED
- decided by: Basti
- because: on-screen patch size ends up set by patch COUNT rather than scan
  quality — the LaserSoft gets 18 logical px per patch and a 4.5 px illegible
  label, and scanning at 1200 dpi buys nothing. Whether to keep the fixed view
  or open zoomed on the named worst patch is a design choice, and any new
  wording needs §M-PROPOSED.
- evidence: —

### B8-21 · Knut's label requests the specification does not rule on
- blocks release: no
- status: DEFERRED
- decided by: Basti
- because: `docs/design/row_label_geometry.md` rules on position, limit, margins
  and the reported raise (all conformant) and is SILENT on row-letter rotation,
  top/centred/bottom alignment, renaming "Label offset" to "Strip label offset"
  plus a row-label offset, sub-frames, and moving Strip/Patch pattern into the
  frame. Silence means design decision, not defect — and CLAUDE.md says a
  spec-contradicting fault is reported and approved, never silently fixed.
- prepared: each of the six is costed for a ruling in
  `beta 8/15-knut-small-items/B8-21-FOR-BASTI.md` — what it touches, how big it
  is, what it would look like and what the risk is, with the code sites already
  located.
- **§4 (sub-frames) IS NOW RULED AND BUILT — the other five stay deferred.**
  Basti, 2026-09-03: *"keep the first note, drop the second, and rule on
  sub-frames… the paragraph is the option I'd argue against — it's correct, and
  correct is not the same as clear."* So B8-14's forty-word reach paragraph is
  gone (its key retired in all twelve catalogues, both untranslated-count tables
  re-noted with the arithmetic) and "Strip && row labels" holds two sub-frames
  along the line the ink drew: **"Strip letters and row numbers"** (Font, Size,
  Bold) and **"Strip letters only"** (Underline, line thickness, line distance,
  rotation, Label offset). `_label_style_note` stays exactly where it was — it
  says where the setting LIVES, which no arrangement of controls can show. The
  two titles are new user-facing wording and sit in §M-PROPOSED awaiting
  Basti's ruling.
- the risk the costing named as HEIGHT was real and it was WIDTH. Measured
  offscreen with the app's own stylesheet, the panel's minimum width was
  **already 514 px in Dutch against a 514 px pane**, German and Swedish at 508 —
  the pane-fit test's own note claiming "~60 px of room" was four months stale
  and is corrected in the same change. Built with ordinary sub-frame margins
  the split cost **+14 px** and turned de/nl/sv RED in both width tests; paid
  for out of the margins it replaces (outer column 0, each sub-grid 8, so
  0 + 1 border + 8 = the 9 px a plain grid took), the minimum width is
  **identical to baseline in all thirteen languages** and four of them got
  narrower. Height went the right way on its own: on screen the frame is
  **340 → 298 px** in English and **356 → 298 px** in German, and the whole
  panel's sizeHint height **2412 → 2370** / **2421 → 2379**.
- evidence: test_the_frame_groups_the_controls_by_what_they_reach,
  test_both_sub_frames_are_inside_the_strip_and_row_labels_frame,
  test_the_titles_say_the_reach_in_the_readers_words,
  test_the_style_note_moved_to_the_tooltips_and_the_reach_paragraph_stayed_gone,
  test_no_sub_frame_title_claims_italic_does_anything,
  test_the_engine_panel_fits_the_pane_it_is_given
  — four mutations, each proved to turn exactly one of them red: Bold demoted
  to the strip-only frame, "only" dropped from the second title, the paragraph
  put back alongside the frames, and a sub-frame floated out of its parent

### B8-22 · The regression sweep Knut actually asked for
- blocks release: yes
- status: FIXED
- found by: Knut, beta.7
- detail: "When you make such large changes, every single function needs to be
  retested" and "the Auto align goes right into the middle of the code for the
  grid, the check alignment and such". This session changed exactly that code.
  A sweep of the whole scanner window, driven on screen, is owed with beta 8 and
  is what he will judge it on.
- evidence: test_the_script_is_where_the_runner_looks_for_it,
  test_every_check_is_registered_and_callable,
  test_every_check_in_the_README_table_exists,
  test_a_check_can_actually_fail,
  test_the_progress_table_is_rewritten_after_every_single_check,
  test_the_cache_probe_can_see_a_stale_cache
  — the sweep itself now lives in `scripts/scanner_sweep/`, so it is
  re-runnable before every beta instead of being improvised. 34 checks
  driven on screen this round: 29 PASS / 5 FAIL / 0 UNTESTED, and the
  five failures are B8-28 to B8-32.

### B8-23 · The release evidence: a clean gate AND a clean sweep, on the final tree
- blocks release: yes
- status: VERIFIED
- detail: beta 8 does not ship on one of these. BOTH are required, and both
  must be run on the final tree with nothing else touching the machine —
  driving the app writes into the output root and trips the suite's own
  `_no_gate_run_may_rewrite_the_real_chromiq_folder` guard, which is what the
  twelve teardown errors were.

  **1. `QT_QPA_PLATFORM=offscreen pytest --runslow -n auto` fully green.**
  Recorded baseline for the EVERYDAY tier on 2026-09-04, after B8-01, B8-03,
  B8-04, B8-13, B8-15..17, B8-22, B8-25, B8-26, B8-28, B8-29 and B8-33:
  **10280 passed, 278 skipped, 3 xfailed, 0 failed.** A later run with fewer
  passing tests has lost something; find out what before shipping.

  **2. `scripts/scanner_sweep/run-sweep.sh` with no PASS that has become a
  FAIL.** Recorded baseline: **29 PASS / 5 FAIL / 0 UNTESTED** over 34 checks
  driven on screen, where the five failures were B8-28..B8-32. B8-28 and B8-29
  are now fixed, so a correct run shows MORE than 29 passing and never fewer.

  Basti, 2026-09-04: *"and we have to make sure that non of this causes any
  regressions"* — so this item is the place that requirement is discharged, and
  it stays OPEN until both numbers have actually been produced on the tree that
  is about to be tagged. Neither number may be quoted from an earlier run.
- evidence: BOTH numbers produced on this tree, 2026-09-04, with nothing else
  touching the machine:
  * `QT_QPA_PLATFORM=offscreen pytest --runslow -n auto` ->
    **10474 passed, 143 skipped, 3 xfailed** in 2:58. No worker crash, no
    teardown error, no `Timeout` dump — the conditions CLAUDE.md says that
    gate needs, met.
  * `scripts/scanner_sweep/run-sweep.sh` -> **33 PASS / 1 FAIL of 34**,
    against a 30/4 baseline. ZERO checks went PASS -> FAIL.
  The single FAIL is J28, and it is a STALE EXPECTATION rather than a defect:
  it asserts that Auto align ACCEPTS on the demo scan, but J25 measures the
  demo's seeded grid at **1 px = 0.02 patch pitches** from the patch block
  since the sheet-painting fix, Check alignment agrees ("keeps all sample
  boxes within their chart patches"), and Auto align now correctly declines
  to move a grid with nothing to gain. J30 proves the half that matters still
  works: on Knut's own scan the seed no longer vetoes the recogniser. The
  check needs its expectation updated — filed as B8-40 — and must not be
  updated by loosening it.
### B8-24 · Knut's "one 34 % fit"
- blocks release: no
- status: OPEN
- found by: Knut, beta.7
- detail: settled by elimination as the placement-agreement worst figure —
  `scan_reference_correlation` only prints below a 0.25 floor, so 0.34 can never
  reach the screen. Confirming it needs his screenshot. Do not answer him until
  it is settled: the two candidates have different fixes.
- evidence: —

### B8-25 · Every warning in the app wore the platform's sign, not ChromIQ's
- blocks release: no
- status: FIXED
- found by: Basti, watching an agent drive the app
- detail: `ui/warning_sign.py` draws a warning triangle for Light, Dark and
  Neutral, from the same tokens as every other accent — and was being used in
  exactly ONE dialog. The other 51 sites across 13 files showed
  `QMessageBox.Icon.Warning`: on macOS the system caution triangle with the
  application badged into its corner, at whatever size and hue the OS picks,
  carrying the hue Neutral exists to remove. Added `warning_sign.warn()` as a
  drop-in for the static call, in the shape of the existing
  `ui.widgets.confirm`, and converted all 51.
- evidence: test_no_dialog_uses_the_platform_warning_sign,
  test_the_replacement_exists_and_keeps_its_shape,
  test_the_check_can_actually_see_every_offence_it_bans

### B8-26 · Information and Question had no ChromIQ sign either
- blocks release: no
- status: FIXED
- found by: Basti, 2026-09-04, on being asked whether a question mark existed
- detail: it did not. The platform question mark had been REMOVED once already
  on his word (`ui.widgets.confirm` exists because of it), and removing a sign
  is not the same as having one — 19 sites still showed the macOS badges.
  Drawn now in the same family: a TRIANGLE means "be careful" and stays the only
  amber; information and a question are CIRCLES in the app's own ACCENT
  (SPEC_CYAN), differing by their mark, so neither competes with the warning.
  Neutral gives all three its one accent pairing, so there the shapes carry the
  whole meaning — which is that appearance's rule. 4 setIcon and 15 static calls
  converted across 11 files; `inform()` and `ask()` join `warn()` as drop-ins.
  `confirm()` deliberately keeps NO sign: it is the everyday Yes/No, and a badge
  on every routine confirmation is noise.
- evidence: test_every_sign_renders_in_every_appearance,
  test_neutral_says_it_with_shape_not_hue,
  test_no_dialog_uses_the_platform_warning_sign,
  test_a_clean_line_is_not_reported

### B8-27 · `ui/warning_sign.py` now draws three signs and is still called warning_sign
- blocks release: no
- status: DEFERRED
- decided by: orchestrator (a tidy-up, not a defect)
- because: the module now holds the warning, information and question signs, so
  its name is wrong and `warning_sign.ask` reads oddly. Renaming it to
  `ui/message_signs.py` touches the import line in ~17 UI files — which is
  exactly the set three agents are producing patches against right now, so a
  rename today guarantees conflicts for a purely cosmetic gain. Do it once they
  have landed. Nothing behaves differently either way.
- evidence: —

### B8-28 · Auto align finds the right answer and throws it away
- blocks release: yes
- status: FIXED
- found by: Agent J (regression sweep F-1)
- detail: **Knut's original fault, surviving in a new disguise.** On his own
  4157x2939 Wolf Faust scan the recogniser now finds a placement that Check
  alignment scores ✓ worst 96.63 %, while the marquee's untouched SEED scores
  ⚠ worst 0.00 %. The two rank agreements are 0.9839 and 0.9799 — 0.004 apart,
  inside `IMPROVEMENT_MARGIN` 0.02 — so the answer is discarded and the window
  says "your own placement is already the closer match" about a placement the
  user never made. Same class as "the app pre-filled the name, then believed
  itself". A patch with 6 tests and 6 mutation proofs is ready
  (`J-01-seed-must-not-veto-the-recogniser.patch`) and verified on screen, but
  it is a BEHAVIOUR CHANGE — Auto align will move a grid it used to decline —
  so it is Basti's call, not the orchestrator's.
- evidence: test_a_freshly_loaded_scan_is_not_a_placement,
  test_setting_the_corners_is_a_placement,
  test_dragging_a_corner_is_a_placement,
  test_a_new_scan_and_reset_grid_both_take_the_placement_back,
  test_the_seed_is_never_offered_to_the_recogniser_as_a_rival,
  test_a_placement_the_user_made_still_vetoes
- approved by: Basti, 2026-09-04 — "if this fixes the issue and causes no
  regressions that is ok". It does not move `IMPROVEMENT_MARGIN`: it stops
  the app offering its OWN opening rectangle as a rival to the recogniser.
  A placement the user actually made still vetoes, which is what the margin
  was written for and is pinned by its own test.

### B8-29 · "Build anyway" is drawn as "uild anywa"
- blocks release: yes
- status: FIXED
- found by: Agent J (F-3)
- detail: `ui/styles.py`'s `padding: 6px 18px` inflates the button's hint to 132
  where QMessageBox grants 118, so the label is clipped at both ends. Measured
  with AND without the new warning sign — identical, so it is not the sign's
  doing. It is on the modal that gates building a bad profile, which is the
  worst possible button to render unreadably.
- evidence: test_the_rule_makes_a_long_label_fit,
  test_without_the_rule_the_label_really_is_cut,
  test_every_window_that_offers_going_ahead_anyway_applies_it
- note: the fix was NOT new code. `ui.widgets.fit_message_box_buttons` has
  existed since Knut's #130 report ("Delete Run 4 Permanently has its text
  cut on both sides. Again, all windows created must follow the universal
  rules created to prevent this happening") — three of the windows that
  matter most simply were not calling it. Measured with the shipped
  stylesheet: "Install Profile Anyway" wants 210 px and was granted 110.
  The orchestrator wrote a second copy of the helper before noticing the
  first, which is the "check it does not exist before building it" lesson
  arriving again.

### B8-30 · "Correct perspective" is an inert control
- blocks release: no
- status: FIXED
- found by: Agent J (F-4)
- detail: `-p` is suppressed whenever corners are given, and all four call sites
  always give corners. The checkbox has done nothing, in any configuration, for
  as long as it has been there. It was on screen, enabled and **ticked by
  default**, and its help text said *"There's no downside to leaving it on"*
  about a switch with no effect at all.
- fix: **REMOVED**, not enabled and not disabled-with-a-reason, and the choice
  is made on what is measured. There is no configuration in which ticking it
  helps and two measured populations in which `-p` hurts:
  (a) `workflow/scanin_runner.py` — with corners given it is dead work that runs
  `calc_perspective` before the corners are read; **23.3 % of hexagonal reads
  FAILED with it and 0 % without**, and 42 conditions including keystone and
  lens distortion came out bit-identical (0.385 dE against 0.380 at the median);
  (b) Agent K on Auto align, the one path that could still pass `corners=None` —
  `-p` is **worse at every tilt** (it8Wolf 0.020 → 0.037 at 0°, 1.469 → 4.492 at
  15°). The earlier note here said Agent C had measured `-p` worth real accuracy
  on a tilted photo; that was one target at one angle and B8-02 already records
  it as contradicted. Removing the control is argv-neutral by construction and
  proved so: with corners, `scanin_args` returns the identical list either way.
  No new wording was needed, which is the other thing removal buys.
- evidence: test_the_window_offers_no_control_that_cannot_act,
  test_no_help_text_in_this_window_still_explains_it,
  test_removing_it_changed_no_command_line,
  test_the_build_never_asks_for_the_perspective_search
  — and sweep check J10, rewritten to prove both halves (the control is gone,
  and no scanin call this window makes carries `-p`).

### B8-31 · Four scanner settings survive nothing
- blocks release: no
- status: FIXED
- found by: Agent J (F-5)
- detail: sample area, fiducials, perspective and the diagnostic checkbox are
  not kept by "Save as defaults" and not kept across closing the window.
  `_save_defaults_clicked` wrote exactly one key, `scanner_colprof_configs`,
  and the window contained no `settings.set` for any of the four — while the
  button's own tooltip opened *"Store everything you've set here"*. Knut has
  "Use fiducial marks" ticked in both of his beta.7 screenshots and had to tick
  it again every session.
- fix: THREE of the four now join the saved bucket; the fourth is the inert
  "Correct perspective", which no longer exists (B8-30) — a control that cannot
  act is not worth remembering. One new key, `scanner_read_options`, not one per
  profile context: the colprof settings are bucketed per context because a
  printer profile and a scanner profile are different things (#121), but these
  three describe how the SCAN is read, and a sample area that moved when the
  printer box was ticked would be a new surprise rather than a fix. "Restore
  defaults" puts them back too, so the two buttons stay each other's inverse.
  **No settings migration is needed and none was added**
  (`project_settings_default_migration`): the stored defaults are the values the
  widgets were already built with (60 % / off / off), so a user who never
  presses the button sees no change at all — pinned by its own test.
- evidence: test_the_read_options_are_written_by_save_as_defaults,
  test_a_reopened_window_has_them_back,
  test_a_window_nobody_ever_saved_from_opens_exactly_as_it_used_to,
  test_restore_defaults_puts_the_read_options_back_too,
  test_the_saved_marquee_area_reaches_the_marquee,
  test_the_restored_fiducials_setting_reaches_the_picture,
  test_the_save_button_still_says_what_it_saves

### B8-32 · Small silences found by the sweep
- blocks release: no
- status: FIXED
- found by: Agent J (F-6, F-7, F-9, F-10)
- detail: an empty averaging slot is dropped with no word (2 slots, 1 scanin
  call); changing the target type discards the loaded scan silently; a demo
  scan's seeded grid now sits 1.1-6.6 patch pitches off, so demo → Check
  alignment WITHOUT pressing Auto align is a red ⚠ 0.00 % (after Auto align,
  8 of 8 targets are green within 3 px); and `warning_sign.py` claims a fourth
  appearance "fails loudly" when it silently gets Dark.
- fix: three of the four, and the fourth deliberately left alone.
  **F-7, the empty averaging slot** — said, not refused, which is this window's
  settled rule (B8-15): a build from fewer scans is legitimate, and a Run button
  that greys out with no reason attached would be a new silence. The build names
  it before it reads anything, and the slot's own entry in the "Scan 1 / Scan 2"
  box reads "Scan 2 (no file yet)" from the moment it is added, so the state is
  visible before Run is ever pressed. Wording is §M-PROPOSED
  (M-SCAN-SHOT-EMPTY) and unapproved.
  **F-9, the target-type change** — the discard is correct and unchanged; the
  silence is not. It is counted before it happens and reported into the log that
  B8-16 already clears in the same block, and it says nothing at all when
  nothing was loaded. Wording is §M-PROPOSED (M-SCAN-TARGET-CHANGED) and
  unapproved.
  **F-10, the false comment** — the claim is DELETED rather than made true, in
  `ui/warning_sign.py` and in `ui/theme.by_mode` where it was copied from. B8-33
  settled the rule for this module the hard way: `warn()` falls back to a
  parentless box instead of raising, because a warning that throws takes the
  message it was drawn for down with it — so a sign that raised on an
  unfamiliar appearance would be the one outcome worse than the wrong amber.
  Both docstrings now say what the code does, and a guard keeps them saying it.
  **F-6, the demo seed, is NOT changed**: Agent J's own finding says "nothing to
  fix in the code" — the demo is deliberately off-centre so Auto align has
  something to do, and after Auto align 8 of 8 targets are green within 3 px.
  The log line he suggested would be new wording for a state that is working as
  designed, so it stays with Basti alongside B8-20.
- evidence: test_an_empty_averaging_slot_is_named_before_the_read,
  test_a_page_whose_slots_are_all_filled_says_nothing,
  test_the_page_is_named_only_when_there_is_more_than_one,
  test_the_shot_box_says_which_slot_has_no_file,
  test_the_build_asks_before_it_reads_anything,
  test_changing_the_target_type_says_the_scan_was_dropped,
  test_a_target_change_with_nothing_loaded_stays_quiet,
  test_both_new_sentences_come_from_the_catalogue,
  test_no_docstring_here_claims_a_loud_failure,
  test_that_guard_could_see_the_sentence_it_bans

### B8-38 · The inspector advised reducing a setting that moves nothing
- blocks release: no
- status: FIXED
- found by: Agent B, `04-chart-layout-ui` (F-5), reproduced on screen
- detail: two of this app's own messages contradicted each other on one screen
  at one moment. The red warning under the preview ended *"To get that paper
  back, switch “Show row indicators” off, use a smaller label size, or reduce
  “Clip”."* while the black note under "Text distance from edge", four inches
  away, said *"“Clip” starts moving them again once you set it above 26.0 mm."*
  `floor = max(Clip, the clip border's width, the instrument's own left
  furniture)`, so below the floor's other terms Clip is inert — which
  `docs/design/row_label_geometry.md` §R2 states outright: *"Below the width of
  a clip border, Clip has no visible effect."* Measured while fixing it, and
  wider than reported: on the ColorMunki at A4 the floor is 26.0 mm from the
  instrument's own furniture **with no clip border at all**, so the invalid
  advice was the ordinary case rather than an edge one.
- fix: the advice is conditional on Clip having won the `max()`. When it has,
  the sentence is unchanged — same string, same twelve translations. When it has
  not, the message says so instead: it names Clip's value, says lowering it
  moves nothing, and points at the note that does name the reason. This is the
  code being brought back to the specification, not a change to it.
  In the same panel, the text notices moved out of the margin-violation label
  into their own framed, collapsible "Text and label notes" box, which is what
  Basti asked for (*"Maybe put a frame around it like other sections and make
  it a collapsible info section"*) and Knut agreed to. §R2 requires the raise to
  be REPORTED and §R5 correction 3 exists because a document once claimed a
  panel said so while nothing did — so the box **opens itself whenever it has
  something to say** and is hidden, not collapsed, when it has not. Collapsing
  is for tidying it away after reading, never the state a notice arrives in.
- **the collapsible box lasted one day.** B8-52 took it out again on Basti's
  ruling, and the notices moved to the panel's own ⓘ. The advice half of this
  item — which lever the message names — is untouched and still proved by the
  first five tests below.
- evidence: test_the_advice_does_not_name_clip_when_clip_cannot_move_anything,
  test_it_says_plainly_that_clip_is_not_the_lever,
  test_the_advice_still_names_clip_when_clip_is_what_holds_them,
  test_both_forms_still_carry_the_two_numbers_the_raise_is_made_of,
  test_the_advice_that_is_left_is_advice_that_works,
  test_a_live_notice_reaches_the_panels_own_icon,
  test_the_icon_carries_nothing_when_there_is_nothing_to_report,
  test_a_text_notice_never_appears_under_a_green_verdict,
  test_panel_shows_text_overflow_warning

### B8-33 · Converting away from a stubbed static silently killed five test stubs
- blocks release: no
- status: FIXED
- found by: Agent J (F-2), caused by the orchestrator's B8-25/B8-26 conversion
- detail: tests monkeypatched `QMessageBox.warning` / `.information`; once the
  app called `warn()` / `inform()` instead, those stubs intercepted NOTHING and
  a real modal opened in a headless test — caught only by the watchdog, four
  seconds later. `warn()` also constructs a QMessageBox, which is stricter about
  `parent` than the static it replaced, so three tests passing a stand-in `self`
  began raising FROM INSIDE THE WARNING. Both fixed: the constructor falls back
  to a parentless box (a warning must never be the thing that raises), and the
  stubs now patch the name where the module looks it up. The orchestrator ran
  only the files it believed were affected and reported the conversion clean;
  the full tier is what found it.
- evidence: test_a_warning_survives_a_parent_that_is_not_a_widget,
  test_a_warning_survives_a_widget_whose_init_never_ran,
  test_a_real_parent_still_parents_the_box,
  test_no_test_stubs_the_static_warning_any_more,
  test_that_guard_can_actually_see_an_offence

### B8-34 · A photograph can be read at all
- blocks release: no
- status: FIXED
- found by: Basti's original question, escalated by the adversarial round
- detail: ChromIQ's own window offers "a scan **or photo**" and could not in
  fact profile from a photograph — on both real ColorChecker photographs and
  both freely-licensed real IT8 photographs, Auto align refused outright.
  The cause is that the quad Auto align can return is always a rotated
  RECTANGLE, and a photograph is a keystone. `workflow/photo_fit.py` adds a
  separate "Fit to the patches" button that searches the marquee's full EIGHT
  degrees of freedom from the placement the user already made, clamped to 3/4
  of a patch pitch so it can never slide onto the neighbouring patch. numpy and
  Pillow only — no new dependency. Two real photographs were driven end to end
  in the real window and both profiles installed; the ColorChecker one came out
  clean, colprof peak 10.78 / avg 4.11 inside ChromIQ's own limit of 12.
  Across a 48-cell bow x lens x tilt matrix it takes 636 patches over 1 dE00
  down to 14 and makes no cell worse. Nothing in the ordinary read path calls
  it: a flatbed scan that never presses the button runs byte-identical code,
  proven on Knut's Wolf Faust and LaserSoft scans at two sample areas.
- also settled here: **Basti's compounding instinct, measured.** On Knut's own
  Wolf Faust scan a 5.5 % bow ALONE costs nothing and a 15-degree compound tilt
  ALONE costs nothing — **together they put 102 of 288 patches over 1 dE00 and
  44 over 3**. No single-variable test could have found it, which is his
  standing rule about crossing the options, confirmed on this feature.
- and a correction to the adversarial round: **Agent G's lens-distortion table
  measured a mis-registered read, not a lens.** Its fixture left the `.cht`'s
  own `F` line alone while passing patch-bbox corners, and on `it8Wolf.cht` the
  greyscale strip sits BELOW the fiducial frame (patches reach y 411.75, the
  frame ends at y 358) — verified here at source. Re-run with ChromIQ's real
  `F` handling the counts fall 74 -> 1, 26 -> 0, 94 -> 2, 187 -> 21 patches
  over 1 dE. Lens distortion is a real limit but a far smaller one than that
  table said.
- evidence: test_a_photograph_is_converted_and_keeps_its_pixels,
  test_the_clamp_cannot_reach_the_neighbouring_patch,
  test_no_corner_is_ever_moved_further_than_the_clamp,
  test_a_whole_patch_slip_is_neither_confirmed_NOR_corrected,
  test_the_read_path_never_calls_the_fit,
  test_a_placement_that_is_already_right_is_left_alone

### B8-35 · The "Fit to the patches" tooltip read like Auto align
- blocks release: no
- status: FIXED
- found by: Basti, 2026-09-04 — *"i don't really get what the fit to the patches
  button does differently to the auto align button"*
- detail: the two buttons ARE different — Auto align returns a rectangle (five
  degrees of freedom, orthogonal edges by construction) while this reshapes the
  user's own quad through all eight — but the tooltip described the outcome
  rather than the difference, so it read as a second Auto align. Rewritten to
  lead with what only this can do: let the grid lean the way a photograph does.
  German written, the other eleven carry the English source.
- open, and pointed at an agent: whether the sampling boxes should be placed
  and sized PER PATCH, which is the only thing that can follow a bow or a lens
  bend, since neither is a plane. Note that `seating_drift` already computes
  exactly those per-patch offsets and uses them only to refuse.
- evidence: test_the_tooltip_names_what_only_this_button_can_do

### B8-36 · Should the sampling boxes be placed and sized per patch?
- blocks release: no
- status: DEFERRED
- decided by: Basti — the measurements are done and the choice is his
- because: **per-patch POSITION is a bad idea and the numbers say so; per-patch
  SIZE is a good one.** Measured over 80 crossed cells (bow x lens x tilt) on
  Knut's own Wolf Faust scan, from a hand-like placement with "Fit to the
  patches" pressed once, read through real scanin, dE00 against the flatbed
  base:

  | shape | patches >1 dE00 | >3 dE00 | cells made WORSE |
  |---|---|---|---|
  | Fit to the patches alone | 28 | 10 | — |
  | smooth warp (poly2) | 15 | 10 | 4 |
  | neighbour agreement | 27 | 10 | 0 |
  | free per-patch movement, clamped 0.25 pitch | 26 | **17** | **9** |
  | **per-patch shrink only, never move** | **5** | **4** | **0** |

  Free movement did exactly what it was predicted to do — it made nine cells
  worse and nearly doubled the count over 3 dE00 — because a box that slides
  onto its neighbour scores BETTER on every within-patch measure. The smooth
  warp helps the worst cells and damages four, one of which was clean before.
  Shrinking about an unchanged centre can only ever sample less of what it
  already sampled, so its safety is the SHAPE of the operation rather than a
  tuned threshold.

  The gain is genuinely per-patch: removing the same area uniformly gets 20 not
  5, and turning the existing Sample-area spinbox from 60 % to 36 % gets 9 while
  costing median accuracy. Per-patch keeps 94.8 % of the area on average.
  A degree-0 warp (one offset for the whole chart) is WORSE than nothing (33) —
  the quad's eight corner degrees of freedom have already absorbed every
  translation there is.

  One correction to the premise: perspective foreshortening needs no per-patch
  size, because a projective quad already sizes each box by its distance. What
  per-patch size buys is the residual left by a bow and a lens bend, and it buys
  it only because MOVING a box is unsafe.
- what exists: `patch/B8-16-per-patch-box-trim.patch` in
  `beta 8/16-per-patch-sampling/`, `git apply --check` clean — `workflow/box_trim.py`,
  a bit-identical split of `seating_drift` into `seating_field()` +
  `_drift_from_field()` (9 of 9 repr matches on Knut's scan), and 13 tests with
  7 mutations proved to land. **NOT APPLIED**, deliberately: it is the mechanism
  with no UI, no message and no i18n, so it buys nothing today, while it does
  refactor the B8-02 safety gate — and that gate is the only thing standing
  between a photograph and a confidently wrong profile. It should go in when the
  control that uses it does, not before, and Basti's "separate option" rule
  applies to that control.
- not verified, and said so by its author: the scanner sweep was never run
  against the patch (`run-sweep.sh` drove the live tree instead — now fixed, see
  below), so its 30 PASS / 4 FAIL bar is unproven. Untested: a cockled sheet
  (`exp/cockle.py` written, never run — the case most likely to overturn the
  "no smooth warp" verdict, because a bow is developable and a cockle is not),
  any chart other than the 288-patch it8Wolf, and a sweep of the trim constants.
- evidence: —

### B8-37 · The regression sweep silently tested the wrong tree
- blocks release: no
- status: FIXED
- found by: Agent N, by being honest about what it had not verified
- detail: `scripts/scanner_sweep/run-sweep.sh` read
  `REPO=${CHROMIQ_TREE:-/Users/Basti/develop/ChromIQ}`. Copy the repo to test a
  patch, run the sweep from the copy, and it drove the ORIGINAL: 34 checks pass,
  the patch is never loaded, and the run reports a clean bill of health for code
  it never saw. In the one tool whose entire job is to prove no regressions.
  It now derives the tree from the script's own location, says which tree it is
  driving, and says so when it has to borrow the original's venv.
- evidence: test_the_script_is_where_the_runner_looks_for_it,
  test_every_check_is_registered_and_callable

### B8-39 · Clipped labels in the scanner window, including its primary button
- blocks release: no
- status: OPEN
- found by: Agent M, reported as seen on screen: the primary button rendering as
  "**ild profile with scanner or came**"
- detail: B8-29's fault class, but on controls `fit_message_box_buttons` cannot
  reach — a `QDialogButtonBox` and ordinary layout children rather than a
  QMessageBox. Measured here offscreen, 13 controls want more width than they
  are granted, including:

  | control | text | wants | granted |
  |---|---|---|---|
  | **Build profile with scanner or camera** (primary) | 281 | 320 | 286 |
  | Restore defaults | 125 | 163 | 110 |
  | Try with a demo scan | 132 | 159 | 100 |
  | Install profile / Reveal profile | 117 / 109 | 156 / 148 | 110 |
  | Don't embed measurement data (-nc) | 231 | 256 | 100 |

- **CAVEAT, and it must be resolved before anyone "fixes" this:** those numbers
  are OFFSCREEN, and `ButtonFontFilter` re-fits at POLISH, which does not happen
  offscreen. `ui/widgets.py::fit_message_box_buttons` says so in its own
  docstring — that is precisely why a window can look right in a rendered check
  and clip in the real application, and it cuts both ways: an offscreen render
  can also show clipping that polish would have removed. Agent M reports having
  seen the primary button clipped ON SCREEN, which is the evidence that counts;
  confirm that first, per control, before changing any width.
- the fix is a design choice once confirmed: widen the window (Agent L measured
  six buttons in one row needing 840 px in German, which already puts the floor
  near a 1080p laptop), shorten the labels, or apply the existing
  `ButtonFontFilter.fit` at construction the way the message-box helper does.
- evidence: —

### B8-40 · Sweep check J28 asserts behaviour that B8-28 deliberately changed
- blocks release: no
- status: VERIFIED
- found by: the final release sweep, 2026-09-04; fixed by Agent Q while merging
  the two placement buttons (B8-42), which is the same question asked twice
- detail: J28 ("Demo -> Auto align -> Check alignment") expected Auto align to
  ACCEPT on the app's own demo scan. Two of this round's fixes changed that on
  purpose: the demo now paints the sheet, so its seeded grid lands 1 px — 0.02
  of a patch pitch — from the patch block (J25), and B8-28 stopped Auto align
  treating the app's own seed as a rival while leaving it free to decline a
  placement it cannot improve. Refusing there is the CORRECT answer, and Check
  alignment confirms the placement is good.
- fix: the check now asks what its own docstring always said it asked — "a
  verdict of anything but 'the grid is on the patches' here is a fault in the
  tool" — so it asserts the OUTCOME (every demo ends within a quarter of a
  patch pitch of the truth AND Check alignment shows no warning) instead of
  which button moved the grid. `accepted` is still printed in the note, so
  nothing is hidden by not asserting it. Written this way the check would have
  passed before B8-28 and after it, which is what a regression check is for.
- and a second reason it had to go, found while fixing it: **`accepted` is not
  stable between runs.** In the full sweep on 2026-09-04 it8Wolf reported
  `accepted=False`; running J28 alone minutes later on the same tree reported
  `accepted=True`, because the window remembers the last accepted placement per
  target and J28, unlike J29, does not clear it. The old check was flaky as
  well as stale.
- evidence: `CHROMIQ_TREE=<tree> scripts/scanner_sweep/run-sweep.sh` on the
  patched tree, 2026-09-04 — **33 PASS / 1 FAIL** with the old check (the FAIL
  being this one), then `run-sweep.sh J28` with the new check: **PASS**, giving
  **34 PASS / 0 FAIL**. Per-check output in
  `19-one-align-button/out/sweep-patched.txt` and `out/sweep-J28.txt`.
- and it was worse than filed: `accepted` is **flaky, not merely stale** — it
  came back False in a full run and True alone minutes later. A check that
  disagrees with itself is the thing that teaches people to re-run until green,
  which is how a real regression gets waved through. Rewriting it to assert the
  outcome removes the flake as well as the staleness.

### B8-41 · "Fit to the patches" submitted its answer to no check at all
- blocks release: no
- status: FIXED
- found by: Agent O, while answering whether the two buttons overlap
- detail: Auto align submits every answer it finds to TWO picture checks before
  applying it. `_on_fit_patches` submitted its answer to none — it called
  `refine_corners` and applied the result. Proved on screen on Knut's own Wolf
  Faust scan with the grid one pitch out: the window said *"The grid was fitted
  to the patches… moved your corners by up to 0.54 of a patch"* while the grid
  was **1.54 patches out**. That is the silent-wrong-profile class, in the
  button added earlier the same day and merged by the orchestrator without
  noticing the asymmetry. The fit now faces the recogniser's own two checks,
  at the recogniser's own limit rather than a second number of its own.
- evidence: test_the_true_placement_survives_the_check,
  test_a_grid_walked_onto_the_neighbouring_patch_is_refused,
  test_both_of_the_recognisers_picture_checks_are_asked,
  test_the_limit_is_the_recognisers_own_and_not_a_second_number,
  test_a_check_that_cannot_run_is_not_evidence_of_a_fault,
  test_the_window_says_it_could_not_confirm_the_placement_it_made,
  test_the_window_still_applies_a_fit_that_survives_the_check,
  test_the_refusal_has_words_of_its_own_and_is_not_approved_yet,
  test_every_reason_the_fit_can_end_on_has_words_of_its_own

### B8-42 · Auto align and Fit to the patches should be ONE button
- blocks release: no
- status: FIXED
- found by: Basti — *"i don't want to have two options where one is useless"*;
  measured by Agent O, built and driven by Agent Q
- detail: **neither button was useless and neither was a subset of the other**,
  measured over 290 cells, 10 starting conditions, 5 targets, real scanin — 139
  cases only the search recovers and 30 only the reshaping does. They are a
  SEARCH and a REFINEMENT, and choosing between them was never the user's job.
  There is now one button, "Auto align", which searches the picture, reshapes
  the answer (or, when nothing is found, the four corners the user placed) onto
  the patches, and only then submits the result to both picture checks and the
  reference agreement. Re-measured by DRIVING the shipped
  `workflow/scan_placement.py` over the same 290 cells, not by composing the
  parts:

  | design | ends ON the patches | applied a placement still WRONG |
  |---|---|---|
  | Auto align alone | 196/290 (68 %) | 0 |
  | Fit alone | 87/290 (30 %) | 41 of 118 applied |
  | press both, as beta 7 shipped | 226/290 (78 %) | 11 |
  | **one button** | **244/290 (84 %)** | **0 of 233** |

  Better than pressing both in 28 cells, worse in 1 (a conservative refusal,
  not a wrong answer), and identical to Agent O's composed prediction in
  **290 of 290** cells.
- the three rulings, each decided from the data and not from taste:
  * **UNDO.** One press, one snapshot. The corners are read once before the
    operation starts and written once at the end, so the undo returns the
    placement the user was looking at when they pressed — never the search's
    raw answer from between the steps, which was never on screen.
  * **THE ENDINGS.** Nine, and not one of them names an internal step. Eight
    refusals plus the success, all told in Auto align's own words; the search's
    reason wins whenever it is a diagnosis the user can act on, and the
    reshaping's only when the search had none (`no-better`), because that is
    the one search reason that carries no information at all.
  * **SEARCH SUCCEEDS, RESHAPING DECLINES.** The search's answer is APPLIED.
    That branch is 175 of the 290 cells — the majority — and refusing there
    would throw away 155 correct placements; in the 20 where the gate refuses
    instead, the search's answer would have been wrong in 20 of 20. A fallback
    ladder ("if the reshaped answer is gated out, try the raw one") was measured
    too and fires in **0 of 290**, so it was not built.
- also fixed here, and measured: the agreement the window quotes is now taken
  AT THE CORNERS IT SETS, not at the search's answer from before the reshaping
  moved it, and it must clear the same 0.80 floor the window's own sentence
  claims. Over the 233 applied placements the lowest was 0.978, so the floor
  costs nothing, and it closes a real hole: 59 of those 233 came from the
  reshaping alone, which under the composed design faced no colour check at all.
- the window is 14 px NARROWER: measured over all thirteen languages, the worst
  line of the button block is 288 px (German) against 302 px for the
  seven-control block that shipped. No button moved.
- wording: four never-approved messages are WITHDRAWN with the button
  (M-SCAN-FIT-DONE, -NO-BETTER, -NOTHING, -NOT-SEATED), M-SCAN-FIT-TOO-FAR and
  M-SCAN-ALIGN-NOT-SEATED are rewritten, and the approved M-SCAN-ALIGN-NO-BETTER
  goes back to §M-PROPOSED with its headline unchanged — it now means "both
  halves looked and neither found anything better", and it names "Check
  alignment", the one check that can see a grid a whole patch out.
- evidence: test_the_reshaping_starts_from_the_users_corners_when_the_search_declines,
  test_the_search_answer_is_applied_when_the_reshaping_declines,
  test_nothing_is_applied_when_both_halves_decline,
  test_the_drift_gate_is_suspended_for_the_search_and_asked_once_at_the_end,
  test_the_gate_sees_the_placement_that_is_about_to_be_applied,
  test_a_placement_the_picture_refuses_is_not_applied,
  test_the_true_placement_is_applied,
  test_the_agreement_shown_is_measured_at_the_corners_that_are_set,
  test_a_placement_that_cannot_be_scored_against_the_reference_is_refused,
  test_every_ending_has_words_and_none_of_them_names_a_stage,
  test_every_refusal_says_what_to_do_next,
  test_no_ending_promises_the_grid_is_right,
  test_one_press_undoes_the_whole_operation_and_not_a_stage,
  test_the_window_has_one_placement_button_and_it_runs_the_whole_operation,
  test_the_button_block_never_decides_how_narrow_the_window_can_be,
  test_the_tooltip_names_what_only_this_button_can_do,
  test_the_read_path_never_calls_the_fit
- BUILT AND DRIVEN, not composed: `workflow/scan_placement.py::place_grid()` —
  search, then reshape, then BOTH picture checks on the placement about to be
  applied, then the 0.80 reference floor at those same corners. Over Agent O's
  290 cells with the shipped module: **244/290 (84 %), 233 applied, 0 wrong**,
  matching his composed prediction in 290 cells of 290. Better than pressing
  both buttons in 28 cells, worse in 1 (a conservative refusal).
- the three questions, answered with evidence:
  * **undo** — one snapshot taken before the operation, restored by one press.
    No intermediate placement ever reaches the screen, so there is nothing else
    to undo to. Proved on the real window to 1e-6 px.
  * **the refusals** — 13 internal reasons collapse to NINE endings, none of
    which names a step. **Zero new message ids**: four never-approved keys
    withdrawn, two rewritten. Nine of the nine driven on screen;
    `no-chart-geometry` was not reachable and the agent said so rather than
    staging it.
  * **search succeeds, reshaping declines -> apply the search's answer.** That
    branch is **175 of 290, the majority**; refusing there would lose 155
    correct placements (53 % of the sweep) and buy nothing, because the 20 that
    deserved refusing are refused by the gate, 20 of 20.
- and a defect found in the design it was handed: a reshaping-only placement was
  being applied with **no colour check at all** — 59 of the 233. The agreement
  is now measured **at the corners that are set** rather than at the search's
  own answer, which the reshaping has since moved, and must clear 0.80. That
  also makes the shipped sentence "anything below 0.80 is refused" true.
- the window is **14 px narrower** (288 vs 302 px worst line, German, measured
  across 13 languages) and no button moved. The press costs +0.39 s / +0.68 s
  on Knut's real scans, all in the worker thread.

### B8-43 · One test fails intermittently in the full run
- blocks release: no
- status: FIXED
- found by: the beta 8 gate runs; diagnosed and fixed by Agent U
- detail: `tests/test_a_cancel_downstream_keeps_what_was_filed.py::
  test_a_cross_tab_chart_load_takes_the_130_road` failed in about one full
  parallel run in seven and passed every time alone. **It was a settings leak
  between test FILES in one xdist worker, and nothing to do with the code under
  test.** `AppSettings` is one store per worker PROCESS.
  `tests/test_no_project_is_ever_invented.py` switches `restore_last_session`
  on and points `session_target_name` at a project that is not on disk — which
  is exactly what it is testing — and never puts them back. Which files land on
  a worker before which, under `--dist loadfile`, changes from run to run:
  **that is the whole of the intermittency.**
- the mechanism, traced rather than reasoned: in a poisoned worker
  `MainWindow.__init__` queues `QTimer.singleShot(0, self._restore_last_session)`.
  A fixture that then opens a project runs no event loop, so the restore is
  still pending when setup ends — and **pytest-qt's `pytest_runtest_setup` is a
  hook WRAPPER that calls `QApplication.processEvents()` after its `yield`**.
  The restore fires there, writes `set_target_name("Real-Project")` over the
  project the fixture had just opened, finds no such project on disk, and calls
  `close_project()`. The test body then runs against a file manager holding
  nothing: `resolve_ti2` sees no loaded project, takes the "this chart belongs
  to a profile project — open it?" road instead of the #130 one, and opens a
  modal that only the 4-second sweeper can close. Hence both report lines —
  `assert [] == ['#130']` **and** the teardown ERROR "a modal dialog was left
  open … QMessageBox".
- and it could not be read off the report, which is why it survived three days:
  that mutation happens in pytest-qt's POST-yield wrapper, outside the setup
  phase's log capture and before the call phase's, so `Target name set to`,
  `Session restore skipped` and `Project closed` land in **no** captured
  section. The red report showed a project being opened and never closed.
- the trail in the previous version of this entry is discarded, with evidence:
  `_loaded_project_root`'s bare `except` never fired (nothing raised),
  `_handle_inside` was never called (`took` was EMPTY, not `['pre-#130']`), and
  `custom_output_path` was correct in both red runs — `house` failing to restore
  it is shared by 140 call sites in 111 files and is not what this was.
- reproduction, deterministic, one process, **ten seconds**:
  `QT_QPA_PLATFORM=offscreen pytest tests/test_no_project_is_ever_invented.py
  tests/test_a_cancel_downstream_keeps_what_was_filed.py` → `1 failed, 1 error`.
  Either file alone, or the two in the other order, is green.
- fix: one autouse fixture in `tests/conftest.py`, beside
  `_repair_a_leaked_qmessagebox_exec` and following its rule — **repair in
  SETUP, never teardown**, because a teardown version races monkeypatch's undo.
  It removes `restore_last_session`, `session_target_name` and
  `session_project_root` before every test, and refuses to act unless
  `core.settings.QSettings` has been replaced by conftest's sandbox factory, so
  it can never reach the developer's own preferences. No product code and no
  existing test file is changed; the file that legitimately switches the key on
  still works, because it does so in its own body, after setup. It is not one
  careless file either: `MainWindow.closeEvent` writes `session_target_name` and
  `session_project_root` on every close, and 28 call sites close one.
- measured, same machine, same tree: **2 red in 14** full `-n auto` runs before
  (run15 and run19; the rest green), **0 red in 8** after, plus one
  `--runslow` release gate after the fix — **10528 passed, 143 skipped, 3
  xfailed, exit 0, 3:12**. No cost in wall time: 1:38-2:36 before (the spread is
  other agents' gates running alongside), 1:39-1:41 for all eight after.
  **Eight green runs cannot prove a 1-in-7 flake gone** — the chance of that by
  luck is about 1 in 3. What carries the weight is the ten-second reproduction:
  red on the unfixed tree, green with the fix, and red again the moment the
  fixture is disarmed.
- evidence: test_a_test_may_switch_the_session_restore_on,
  test_the_next_test_never_inherits_it,
  test_a_project_opened_in_a_fixture_survives_the_first_event_loop_turn,
  test_a_cross_tab_chart_load_takes_the_130_road

### B8-44 · Four instruction labels were painted in the one colour that cannot carry a word
- blocks release: no
- status: FIXED
- found by: Basti, in Neutral — *"in create chart manual expert in sheet text
  and trip and row labels section under the neutral colorscheme some text is not
  readable"*
- detail: four labels in `ui/dialogs/layout_options_panel.py` said
  `color: palette(mid)`. `QPalette.Mid` is what Fusion shades a FRAME with —
  every appearance sets it a hair from its own ground on purpose, so it is the
  one role that can never carry text. **It was broken in all three appearances,
  not only Neutral**, measured off the pixels of the real running window:
  **Light 1.25:1, Dark 1.02:1, Neutral 1.14:1** against a 4.5:1 requirement.
  Basti saw it in Neutral because that is his appearance, and because Neutral is
  where it is worst in MEANING too — rule 3 of `ui/neutral_styles.py` reserves
  low contrast for "disabled" and nothing else, so a live instruction was
  painted in the value that means dead. After, through `theme.by_mode` on each
  theme's own token and no new hex: **13.64:1 / 5.14:1 / 12.13:1**.
- two measurement traps recorded because they nearly hid it: `QWidget.grab()`
  returns a 2x pixmap on Retina, so the first on-screen pass reported 81 of 85
  elements as "no diff" until the rects were scaled — and offscreen (dpr 1)
  hides that entirely. And a transparent QLabel grabbed ON ITS OWN paints
  Fusion's #efefef rather than the theme's ground, which made the mutation run
  catch the fault in Light and Neutral and MISS it in Dark.
- evidence: test_an_expert_note_reads_in_every_appearance,
  test_a_note_never_asks_for_a_shading_role,
  test_the_ink_is_named_per_appearance_and_not_folded
  — 16 cases measuring the contrast ratio off grabbed pixels rather than
  asserting a colour constant, threshold 4.5:1 (WCAG 2.1 AA), two mutations
  proved to land

### B8-45 · Two spin boxes clip their own value on screen
- blocks release: no
- status: FIXED
- found by: Agent P, while measuring B8-44
- detail: in the same panel, "Size (pt)" gives its editor **7 px** for a 27 px
  value and shows a sliver that reads as ")", and "Line thickness" gives **1 px**
  for 19. Appearance-independent — all three. **Offscreen the same editors are
  38/32/39 px and fit**, because the QSS padding lands at polish, which is
  exactly why no rendered check has ever caught it.
- **RE-MEASURED ON SCREEN AND IT DOES NOT HAPPEN IN THE SHIPPED APP.** Driven
  in the app's own launch order — `main.py` calls
  `apply_appearance(app, None, …)` BEFORE it builds `MainWindow`, so the
  stylesheet is in place before any widget exists — **nothing clips**: editors
  39/31/39 px, `VISIBLE + CLIPPED: 0`, in all three appearances and after three
  runtime appearance switches. Reproduced in Agent P's order (window first,
  appearance switched afterwards) it is real and *worse* than filed:
  **seventeen** visible boxes clip, all four page margins among them. The filed
  numbers are a driver artefact — worth recording in itself, because two agents
  in a row measured this panel through a driver that does not launch the app
  the way the app launches.
- what IS real is the fragility underneath. `_fit_spin_widths` pins each box to
  `widest + chrome + 4` and asks the STYLE what the chrome is: measured, that
  query answers **20 px with no application stylesheet and 51 px with one**
  (all three appearances write `padding: 0 24px 0 6px` plus a 1 px border, so
  they agree exactly). It ran ONCE, from the panel's first `showEvent`, and a
  box fitted at 20 and painted at 51 is 31 px too narrow for ever.
- fix: the fit is made re-runnable. `LayoutOptionsPanel.changeEvent` restarts a
  panel-owned single-shot timer on `QEvent.StyleChange` (a timer and a bound
  method, never a self-capturing lambda — CLAUDE.md). No width changes in the
  shipped path, so both governing width tests are untouched and still green.
  Proved on screen: in Agent P's own launch order the patched tree gives
  39/31/39 px where the pristine one gives 7/1/8.
- evidence: test_the_chrome_really_does_change_when_the_stylesheet_lands,
  test_every_spin_box_still_shows_its_value_after_the_stylesheet_lands,
  test_the_two_boxes_that_were_reported_are_named_and_checked
  — the first is the guard-the-guard (the chrome must actually move, or the
  other two prove nothing); two mutations proved to land: with the refit
  removed, 16 boxes clip and 2 of the 3 go red while the guard stays green
- **CORRECTED: this does not happen in the shipped app.** The reported numbers
  are real but come from a driver that launches the app differently from the
  way the app launches. `main.py:201` calls `apply_appearance(...)` BEFORE it
  builds `MainWindow`; the driver built the window first and then switched
  appearance. Driven in the app's own order the editors are **39 / 31 / 39 px**
  and **nothing clips**, at launch in Neutral and after runtime switches to
  Light, Dark and back. Driven in the driver's order, **seventeen** spin boxes
  clip, not two. Two agents in a row measured this panel through that harness.
- **The fragility underneath it was real and is fixed.** `_fit_spin_widths`
  sizes each box to `widest + chrome + 4` and ASKS THE STYLE what the chrome is
  — the answer is **20 px with no application stylesheet and 51 px with one**.
  The fit ran once, from the first `showEvent`, and pinned a `maximumWidth`, so
  a style arriving afterwards left every fitted box 31 px too narrow for ever.
  `changeEvent` now restarts a panel-owned single-shot `QTimer` on
  `StyleChange` — a timer and a BOUND METHOD, never a closure over `self`
  (CLAUDE.md's scroll-bar SIGSEGV). No width changes in the shipped path, so
  both governing width tests are untouched and nothing was loosened.
- honesty note from its author: it claimed an inline refit would read the OLD
  chrome, measured that this is false (it reads 51), found the mutation making
  it inline passed all three tests, and reported that rather than quietly
  keeping the better-sounding reason. The timer stays for coalescing repeated
  events, and the comment now says so.

### B8-46 · Light's dim text token cannot carry body text at AA anywhere in the app
- blocks release: no
- status: DEFERRED
- decided by: Basti — it is an app-wide appearance decision, not a local fix
- because: `LM_TEXT_DIM` reaches only **3.86:1** on Light's own ground, under the
  4.5:1 AA requirement for normal text, and it also paints every group-box title
  at **2.1:1**. B8-44 sidestepped it by giving Light `LM_TEXT_MAIN` for the four
  notes rather than changing a token the whole app draws with. Changing it
  reaches every window; leaving it means "dim" text is not readable to the
  standard the rest of the app is held to. Reported, not changed.
- evidence: —

### B8-47 · The sweep could not be run as ./run-sweep.sh
- blocks release: no
- status: FIXED
- found by: Agent P
- detail: line 43 called `dirname "$0"` AFTER the script had already
  `cd "$REPO"`, so a relative invocation resolved to the repo root and the
  Python file was not there. The absolute script directory was computed at the
  top — for exactly this reason, when B8-37 was fixed — and then not used here.
  Half a fix is its own bug.
- evidence: test_the_script_is_where_the_runner_looks_for_it
- **and it was still broken after that fix, twice over.** The absolute script
  directory was computed with `${BASH_SOURCE[0]}` — a *bash* builtin — in a
  `#!/bin/zsh` script, so it was EMPTY, `dirname ""` gave "." and `_HERE`
  silently became the caller's working directory. It only ever worked when the
  caller happened to already be in that folder, which is how it was verified.
  Now taken from `$0` BEFORE any `cd`, which is the script path in both shells,
  and checked from three different invocations. Three half-fixes to one line:
  first it hard-coded the tree, then it resolved after the `cd`, then it used a
  builtin the interpreter does not have.

### B8-48 · Two sub-frames, and the risk was width rather than height
- blocks release: no
- status: FIXED
- ruled by: Basti, 2026-09-04 — "keep the first note, drop the second… the
  paragraph is the option I'd argue against — it's correct, and correct is not
  the same as clear"
- detail: the "Strip & row labels" frame now says which control reaches which
  label by its SHAPE. `_label_style_note` stays (it says where a setting LIVES,
  which no arrangement of controls can show, and it was added because a size set
  for one instrument once cost a real chart 49 patches). The forty-word reach
  paragraph is gone, its key retired in all twelve catalogues. Two sub-frames
  along the line the ink actually drew: **Strip letters and row numbers** holds
  Font, Size and Bold (97 987 / 126 162 / 11 086 px of row-label ink, and Font
  and Size re-lay the page); **Strip letters only** holds Underline, thickness,
  distance, rotation and Label offset (0 px of row-label ink, every time).
  Italic stays greyed and is named in neither title.
- **B8-21's costing named the wrong risk.** It said height. It is WIDTH, and the
  panel had no slack at all: Dutch was **already sitting exactly on the 514 px
  budget**. The first build cost +14 px and turned de/nl/sv RED in both
  governing width tests. Paid for out of the margins the sub-frames replace, the
  minimum width is now identical to baseline in all thirteen languages and
  narrower in four. Height improved on its own: the frame is 340 → 298 px in
  English, 356 → 298 in German.
- the sub-frame TITLES are §M-PROPOSED and unapproved, and deliberately carry no
  `M-` identifier: §M is a catalogue of MESSAGES, and a group-box title must not
  be given a fake message id to satisfy a parser.
- also carried out: the pane-fit test's slack note had been stale for months and
  said the OPPOSITE of the truth ("Norwegian sits at 452 … ~60 px of room").
  Replaced with the measured table and a standing instruction to re-measure it
  in the same commit. Worth asking what other measured notes under `tests/`
  carry numbers from a tree that has moved.
- evidence: test_the_font_tooltip_no_longer_says_strip_only,
  test_the_font_tooltip_names_both_sets_of_labels,
  test_the_font_tooltip_says_bold_reaches_both,
  test_the_frame_groups_the_controls_by_what_they_reach,
  test_both_sub_frames_are_inside_the_strip_and_row_labels_frame,
  test_the_titles_say_the_reach_in_the_readers_words,
  test_the_style_note_moved_to_the_tooltips_and_the_reach_paragraph_stayed_gone,
  test_no_sub_frame_title_claims_italic_does_anything
- **the style note has since moved** (B8-52): it is no longer printed across
  the top of the frame, it is on the ⓘ of every control in it. The test above
  was renamed with it — it used to be
  `test_the_style_note_stayed_and_the_reach_paragraph_went`.

### B8-49 · Four rows of buttons under the preview, for six buttons
- blocks release: no
- status: FIXED
- asked by: Basti, 2026-09-04, looking at the running window — "could you task
  an agent to rearrange the buttons under the preview in a way it makes sense
  and takes up less space?"
- detail: the block was four rows (2 + 2 + 1 + 1) grouped by WHEN you press
  each button, with the longest label in the window alone on the last row. It
  is now three rows of two, grouped by WHAT EACH BUTTON ACTS ON — the picture
  (Rotate 90°, Reset view), the grid (Auto align, Reset grid), and judging
  where the grid landed (Check alignment, Pop out). Rotate and Reset view share
  a row because `rotate_90` literally calls `_reset_view`. Every action, every
  enabled/disabled rule and every signal is unchanged; this is a layout change
  and a label.
- **the old note here measured the wrong thing, and so did the brief.** "The
  block's worst line over thirteen languages" is not what constrains this
  window. `showEvent` pins the right pane at
  `max(360, right_pane.minimumSizeHint().width()) + _PANE_GAP`, and that
  minimum is the pane's WIDEST ROW — the diagnostic/fiducial checkbox grid
  (370 px in German, 421 in Russian) or the marquee's own 360 px floor. Measured
  on the real window, the buttons had **72 to 165 px of headroom they were not
  using**, in all thirteen. Both numbers are reported below.
- **two rows is not available in thirteen languages.** Brute-forced: every
  partition of the six into two rows, against each language's own budget, with
  the label full, shortened and icon-only. Not one 3 + 3 fits — the honest
  grouping (grid | view) overruns in six languages, worst Spanish +51 px, which
  is the window's minimum width going 1071 → 1122. Only an icon-only Pop out
  fits at all, in exactly one partition, and that partition groups nothing.
  Three rows: 39 partitions fit, this one with 94 px to spare in the tightest.
- measured, before → after: block **288 → 269 px** worst line over thirteen
  languages (321 px popped out, still 94 px inside the tightest budget); block
  height **96 → 71 px**; window minimum width **identical in all thirteen**
  (1048 / 1058 / 1071 / 1049 / 1075 / 1048 / 1097 / 1048 / 1084 / 1105 / 1109 /
  1048 / 1048).
- **the preview never grew with the window, and would not have taken the row
  back either.** Measured: a 1500x1000 window left the marquee at exactly its
  `setMinimumHeight(460)` and gave the other 350 px to the stretch at the bottom
  of the column. The preview now carries that stretch: same window, **460 → 533
  px in English and 460 → 488 in German**, and the 25 px the fourth row gave up
  goes there rather than to a spacer.
- **the tab order was already wrong, and not because of this.** The focus chain
  is creation order unless somebody says otherwise, and "Check alignment" is
  built last because it arrived last (#108) — so tabbing reached "Pop out"
  before the button drawn above it. Measured on the shipped tree: rotate, auto
  align, reset view, reset grid, **popout, check**. `_order_the_preview_buttons`
  now sets it after the panes are built (a tab order set earlier is thrown away
  when adding a layout to a layout reparents its widgets).
- wording: **"⤢ Pop out for a bigger view" → "⤢ Pop out"**, with the four
  dropped words moved into a tooltip the button did not have. Both are
  **approved by Basti, 2026-09-04 — *"it is ok"*** (§M-PROPOSED, "Button
  labels … Confirmed behaviour"; deliberately no `M-` identifier — a button
  label is not a message, and must not be given a fake one to satisfy a parser). German is
  translated, the eleven carry the English source. The old key is retired in all
  twelve catalogues; "⤢ Dock back" is unchanged.
- **superseded by B8-58**, which is where this block lives now. The three fixed
  rows are gone; the guards below were renamed with them, and the ones that
  still guard something this item claimed are named here in their current form.
- evidence: test_the_pop_out_label_is_a_label_and_not_a_sentence,
  test_the_preview_takes_the_height_the_wrapped_rows_gave_back,
  test_the_button_block_never_decides_how_narrow_the_window_can_be,
  test_the_button_is_reachable_in_the_block_under_the_preview,
  test_tab_follows_the_visual_order_at_every_width

### B8-50 · A self-capturing lambda on the pop-out's `finished` signal
- blocks release: no
- status: FIXED
- found by: Agent S, in passing, while rearranging the buttons above it
- detail: `ScannerProfileDialog._toggle_popout` carried
  `self._popout.finished.connect(lambda _=0: self._dock_marquee())` — a Python
  closure holding `self`, parked inside a C++ object that `self` owns, on a
  signal that object emits. That is the **exact shape CLAUDE.md records as
  faulting PyQt6 6.11**: `ui/fade_scroll.py` crashed the process this way
  (SIGSEGV, a `Py_INCREF` on a pointer read from NULL+0x20), and the documented
  remedy — a bound method, so PyQt keeps a WEAK reference to the receiver and
  lets Qt sever the connection when it dies — is what is now there.
  `_dock_marquee` takes no arguments and `finished` carries an int, which PyQt
  handles. Nothing about docking behaviour changed.

  **This was never going to be caught by the existing guard.**
  `test_a_scrollbar_signal_never_takes_a_lambda.py` is scoped to scroll-bar
  signals, because a scroll bar is where the crash was first paid for. The
  hazard is not scroll bars; it is the ownership cycle. A survey of `ui/` finds
  **47 further self-capturing lambdas**, which matches the standing note that
  the lambda connects are unaudited — see B8-51.
- evidence: test_the_pop_out_signal_takes_a_bound_method_not_a_lambda

### B8-51 · The 47 remaining self-capturing lambdas in `ui/` are unaudited
- blocks release: no
- status: DEFERRED
- decided by: Basti, 2026-09-04 — *"it is ok"*, told plainly that beta 8
  would ship with this known, bounded, unmeasured risk still in it
- because: B8-50 fixed the one lambda that matches the documented crash shape
  most closely, but a grep finds 47 more `\.connect(lambda …self…)` in `ui/`.
  **Most are certainly harmless** — the hazard needs the signal's emitter to be
  an object the capturing widget itself owns, which closes a reference cycle
  across the language boundary; a lambda on a signal from an unrelated or
  parent object does not. Auditing all 47 properly means establishing ownership
  for each one, which is a day's careful work and would touch a great many
  files at a point where beta 8 is otherwise ready. Doing it badly — converting
  them mechanically — is worse than not doing it: this round already recorded
  four separate files broken by mechanical edits.

  The honest position is that beta 8 ships with a known, bounded, unmeasured
  risk that **it also shipped with in every previous build**, minus one
  instance. Whether that audit happens before or after beta 8 is yours.

### B8-52 · Explanation left the Create Chart sections for the ⓘ they belong to
- blocks release: no
- status: FIXED
- ruled by: Basti, 2026-09-04 — *"regarding the info text in create chart tab
  that is directly inside the sections (even that that you made collapsible) -
  i want that gone. You can fit it inside of a tooltip where it fits but not
  directly inside a section"*
- detail: four notices were printed inside sections of Create Chart ▸ Manual ▸
  Expert Options and the panel under the preview. Every one moved onto the ⓘ of
  the control it belongs to; **none was deleted**, and the readouts that look
  similar were classified and left alone (`text_preview`, `clip_dims_label`,
  the margin table, the status verdict and the two placeholders are values
  measured off the chart on screen, not explanation, and Basti did not ask for
  those).

  | was | is now |
  |---|---|
  | `_label_style_note`, a paragraph across the top of "Strip & row labels" | the ⓘ of all six controls in that frame — it is true of every one of the ten label-style fields |
  | `text_edge_clip_note`, up to 7 lines under the T / B / Clip boxes | the "Text distance from edge" ⓘ |
  | `helper_markers_edge_warning`, under the two edge tick boxes | the "Show markers for" ⓘ |
  | the collapsible **"Text and label notes"** box, B8-38, one day old | the "About the margin inspector" ⓘ |

  One mechanism carries all four: `TooltipButton.set_live_note()` puts the live,
  chart-specific note ahead of the standing help in the ⓘ dialog and puts its
  first line into the HOVER tooltip, so an icon carrying a notice says so before
  it is clicked. Nothing is appended to the stored body, so a note re-set on
  every keystroke cannot accumulate.
- **the fourth one needed permission, not obedience, and got it.**
  `docs/design/row_label_geometry.md` §R2 required the automatic left-margin
  raise to be *"reported under the preview"*, and §R5 correction 3 exists in
  that same document because an earlier version *"claimed 'The panel says so'
  about the raised left margin"* when no panel did. Removing the box silently
  would have put the same false claim back into the same document about the
  same feature, the second time. It was put to Basti as a specification
  question with the cost of each option stated — a notice under the preview is
  SEEN, a notice on an ⓘ is only READ IF ASKED FOR — and he ruled: *"a tooltip
  will be enough"*. **§R6** of that document now records the ruling, its date,
  his words, what it costs, and how a check can still verify the disclosure
  exists. §R1.5, §R2, §R3 and open point 3 were corrected in the same change so
  the document cannot claim the old home.
- **three sentences were rewritten, not relocated,** because the move made them
  false: *"…tick at least one edge ABOVE"* was true of a label under the two
  tick boxes and is false of an ⓘ on the row above them; the "Show markers for"
  help ended *"ChromIQ says so under the boxes"* when nothing is under the
  boxes any more; and the "Text distance from edge" help ended *"the text
  overflows toward this line and a margin warning is shown"* when nothing is
  shown — it names the ⓘ beside the measured margins now. All three keys
  retired and re-added, German translated, the eleven carrying the English
  source. `_IDENTICAL_TO_KEY` +2 and `_BUDGET` +3 in the eleven, both 0 in
  German, both with dated notes. (The two constants move by different amounts
  because the retired box title "Text and label notes" is 20 characters and the
  `_BUDGET` detector only counts 25 or more.)
- **measured, on screen, in the real window** (Knut's i1Pro A4 chart with a
  26 mm clip border, a notes box, row indicators on and Clip typed at 4 mm —
  the state in which all four notices fire at once): Expert Options **1730 →
  1580 px in English** and **1754 → 1588 in German**; the margin inspector
  **346 → 250** in both. **246 px of vertical space back in English, 262 in
  German.** Panel minimum width **unchanged in all thirteen languages** — Dutch
  still sits exactly on its 514 px budget — and the inspector's minimum width
  is unchanged too. A real chart generated from the real window is
  byte-identical, four builds across two trees:
  `85bd051d46fc95f1eb2b9e91315ff194f81445a4eb5b0678f2d12fe7e6230fad`.
- **what it costs, said plainly:** the margin-raise notice used to be on
  screen, expanded, in warning red, the moment a chart was generated. It is now
  one hover or one click away. That is a real reduction in how likely a user is
  to learn their typed margin was overruled, and it is the reduction Basti
  chose knowing what it was.
- **2026-09-10: half of that cost was paid back, and the evidence line flipped
  its name to say so.** Knut reported a chart note dropped from all four pages
  of a sheet with nothing on screen to explain it, and ruled that text is never
  dropped but drawn and warned about. An overlap is a VERDICT about the sheet in
  front of you, not explanatory prose, so it goes back on the panel in red,
  where `MarginInspectorPanel._status` already lives; the advisory notes stay on
  the ⓘ, which is what Basti removed. So the test that used to prove the help
  no longer promises a warning now proves it promises one again, and it is
  listed above under its new name. **Both rulings are intact.** What Basti took
  off the panel was prose inside a section; what came back is a verdict.
- evidence: test_no_section_of_the_layout_panel_prints_a_paragraph,
  test_no_section_of_the_margin_inspector_prints_a_paragraph,
  test_where_a_label_style_setting_lives_is_on_every_icon_in_that_frame,
  test_the_clip_override_note_rides_on_the_row_it_is_about,
  test_the_clip_note_comes_off_the_icon_when_the_typed_value_is_in_force,
  test_the_marker_notice_no_longer_points_above_itself,
  test_the_marker_help_no_longer_sends_the_reader_under_the_boxes,
  test_the_text_distance_help_promises_the_message_field_again,
  test_a_live_note_never_stacks_up_when_it_is_set_twice,
  test_the_standing_help_comes_back_when_the_note_goes,
  test_the_hover_tooltip_says_there_is_something_to_read,
  test_a_note_moved_into_a_tooltip_is_still_readable,
  test_the_specification_names_the_home_the_code_actually_uses,
  test_the_specification_still_requires_the_raise_to_be_disclosed,
  test_the_style_note_moved_to_the_tooltips_and_the_reach_paragraph_stayed_gone,
  test_a_live_notice_reaches_the_panels_own_icon,
  test_the_icon_carries_nothing_when_there_is_nothing_to_report
  — 13 mutations applied one at a time, every one proved to land and to turn
  exactly the guard it attacks red (`mutations.json` in the delivery folder)
- ruled by Basti, 2026-09-04, on the one question AGENT-T handed back rather
  than deciding: **the "From profile gamut" note stays exactly as it is.**
  *"from profile gamut stays as it is. no change from me ws requested for
  this"*. It is static explanation, so it fit the shape of the instruction, but
  it sits BELOW the group box rather than inside a section and already carries
  its own ⓘ on the same line — so it was never what the instruction was about.
  **Do not revisit this**: the request was "the info text directly inside the
  sections", and that text is not inside one. AGENT-T was right to hand it back
  instead of taking the tidier-looking option, and the same reasoning applies to
  any other note found sitting outside a section later.


### B8-58 · The buttons under the scanner preview wrap to the width available
- blocks release: no
- status: FIXED
- asked by: Knut, 2026-09-04, on B8-49's three fixed rows of two — *"All the
  buttons, including the Auto Align are clumped together though… They could be
  aligned better across the width available."* and, told the block used to be
  four rows: *"I mean, that much space is not needed. The buttons could wrap
  down to next line when no space in width. If you want consistency in
  position, I get it, but at least 3 buttons per line should be possible."*
- detail: the block is no longer a shape at all. It is **one wrapping row** —
  the six buttons in one fixed reading order, laid out in as few lines as the
  panel allows, every line justified to the panel's width. Same six buttons,
  same actions, same enable rules, same signals; a layout change and an order.
- **it dissolves the problem B8-49 was built around rather than arguing with
  it.** That item's brute force was right: NOT ONE fixed 3 + 3 fits all
  thirteen catalogues, and German, Spanish and Norwegian cannot do 3 + 3 at
  this window's own floor. A fixed grid has to be the worst language's grid at
  every width. A wrapping one does not — it is 2 + 2 + 2 exactly where 2 + 2 +
  2 is all that fits, and 3 + 3 everywhere else.
- **nothing was written from scratch.** `ui/widgets.py::WrappingButtonRow`
  already existed, for Create Chart ▸ Manual's preset bar. It gains one option,
  `balanced=True` (default off, so that bar is untouched): greedy packing fills
  each line to the brim and dumps the remainder on the last one, and since
  every line is justified that remainder is DRAWN AT THE FULL WIDTH OF THE
  PANEL. Measured over every block width from each language's real window
  floor and the next 1200 px, greedy strands **"Check alignment" alone on a
  full-width line in ALL THIRTEEN languages** — a band 103 px wide in Chinese,
  195 in Russian — and cuts a one-button line at the window's OWN FLOOR in
  eleven of the thirteen (3 + 2 + 1, and 2 + 3 + 1 in French). Balanced packing
  keeps greedy's line COUNT and re-cuts the lines so the fullest holds the
  fewest, which gives 3 + 3 and 2 + 2 + 2 in the same number of lines.
- **the order changed too, and it was Basti's suggestion**: *"maybe auto align
  should be next to check alignment"* — one action and its verification. Beta 8
  grouped in PAIRS because it had three rows of two to fill; a wrapping block's
  unit is a RUN, and its commonest shape is 3 + 3, so the same principle at the
  granularity the layout uses gives two runs of three:

  | line | buttons | what it acts on |
  |---|---|---|
  | 1 | ⟳ Rotate 90° · Reset view · ⤢ Pop out | what you LOOK at |
  | 2 | Reset grid · Auto align · Check alignment | where the GRID IS |

  Rotate stays beside Reset view (`rotate_90` calls `_reset_view` itself), Pop
  out joins the view controls instead of being the odd one out, and nothing is
  left over.
- **the pairing survives the wrap, and that was measured, not assumed.** A flow
  never reorders, so adjacency in the sequence always holds; a LINE BREAK can
  still fall between two neighbours. It never falls between Auto align and
  Check alignment: swept every block width from each language's real window
  floor over the next 1200 px — **thirteen languages, 15,600 widths, zero
  splits**. Structurally, balanced packing gives 6 → 3 + 3 → 2 + 2 + 2 (plus a
  10 px 4 + 2 band in Portuguese) and every one of those breaks after item 3 or
  item 4; only 5 + 1 and 3 + 2 + 1 break after item 5, and balancing exists to
  prevent those. Turning `balanced` off makes that guard go red.
- **nesting the pair as an unbreakable unit was considered and rejected**: it
  would make the block's minimum the SUM of the pair rather than its widest
  single button, putting the block back within reach of setting the window's
  floor, and at 3 + 3 it would justify a line of two items across a
  three-button width.
- **tab order.** One fixed chain, and it is right at every width — a flow lays
  its items out in order and chooses only where the lines break, so the reading
  order IS the item order however it wraps. Re-pointed at the new sequence.
- measured, before → after, **window minimum width UNCHANGED in all thirteen
  languages, to the pixel**: 1048 / 1104 / 1126 / 1154 / 1101 / 1135 / 1048 /
  1115 / 1133 / 1178 / 1057 / 1048 / 1048 (en de fr es it nl no pl pt ru sv ja
  zh). It could not have risen: a `QHBoxLayout`'s minimum is the SUM of a row
  (313 px at worst, Spanish) and a wrapping row's is its widest SINGLE button
  (190 px at worst, Russian) — both under the 360 px the marquee itself asks
  for, so the block does not reach the window at all. Confirmed a second time
  on screen: en 1048 → 1048, de 1104 → 1104, es 1154 → 1154 (dark 1100 → 1100,
  1142 → 1142).
- measured, block height **72 → 46 px at 3 + 3 and → 20 px on one line** (ja/zh
  76 → 50 → 22; dark 69 → 44 → 19). The preview takes the difference — the
  stretch factor B8-49 put on `_marquee_box` was already there.
- measured, ON SCREEN, the width at which each language reaches 3 + 3 and then
  one line of six (`23-buttons-flow/onscreen-thresholds.jsonl`): en 1048 /
  1338 · zh 1048 / 1298 · ja 1056 / 1374 · sv 1101 / 1427 · no 1128 / 1476 ·
  pl 1129 / 1473 · pt 1159 / 1473 · it 1173 / 1525 · de 1174 / 1562 · fr 1178 /
  1564 · nl 1189 / 1575 · ru 1216 / 1598 · **es 1250 / 1602**. The window opens
  at 1240, so twelve of the thirteen get 3 + 3 the moment it opens; **Spanish
  needs ten pixels more** and is 2 + 2 + 2 until the user touches the edge.
  Said plainly rather than rounded away.
- evidence: test_the_six_buttons_are_one_wrapping_block_in_one_reading_order,
  test_the_block_is_two_runs_of_three_and_they_are_in_that_order,
  test_auto_align_and_check_alignment_share_a_line_at_every_width,
  test_it_uses_the_width_it_is_given_and_wraps_when_it_is_not,
  test_three_to_a_line_as_soon_as_three_fit,
  test_it_never_leaves_a_button_alone_on_a_line_it_did_not_have_to,
  test_the_block_cannot_widen_the_window,
  test_tab_follows_the_visual_order_at_every_width,
  test_the_block_on_screen_is_the_block_the_packer_describes,
  test_the_preview_takes_the_height_the_wrapped_rows_gave_back,
  test_balanced_mode_is_what_stops_a_button_being_stranded,
  test_balanced_mode_is_off_unless_it_is_asked_for,
  test_a_plain_row_would_widen_this_window,
  test_the_button_block_never_decides_how_narrow_the_window_can_be,
  test_the_button_is_reachable_in_the_block_under_the_preview
  — 4 mutations applied one at a time, each printed as it landed and each shown
  to turn the guard it attacks red: `balanced=False` (4 red), a plain
  `QHBoxLayout` back (7 red), the tab chain not set (1 red), Auto align moved
  away from Check alignment (8 red).
- **still open, for Basti or Knut to judge on screen**: the buttons on a line
  share the slack EQUALLY, so a longer label stays a wider button and the
  columns do not line up exactly between one line and the next. Giving every
  button on a line the same width would align them, at the cost of a
  water-filling allocation (a short label must never squeeze a long one) and a
  change to a layout Create Chart also uses. Not done; nobody asked for it.

### B8-54 · A measurement report that could not be saved said nothing on screen, and looked like a success
- blocks release: no
- status: FIXED
- found by: AGENT-AE, from the #182 design work; authorised by Basti, 2026-09-04
- detail: `TabMeasure._maybe_save_measurement_report` ends every failure in
  `except Exception as exc: log.warning("measurement report failed: %s", exc)`
  and appends **nothing** to the screen. "Save measurement report" is ON by
  default, so this runs after every measurement — and the SUCCESS of the same
  operation announces itself in the measurement log ("[Report] Measurement
  report saved: …"). So the window that had just written no report was
  indistinguishable from the window that had. The silence was not a missing
  message; it was a wrong one. The only evidence lived in a log file the user
  never opens.
- fix: `TabMeasure._say_report_not_saved` — the measurement log, headline first,
  plus a ten-second status flash under the buttons. `log.warning` is untouched;
  the on-screen path is an ADDITION, and a test pins that the support log still
  records the exception.
- **the log and the status line, NOT a window, and that was a decision.** The
  shape is the one `_on_cr30_dropped_reading` already uses in this same tab.
  Basti asked for a pop-up on M-CR30-READ-FAILED for a stated reason — *"instead
  of ruining a whole measurement session when this is unnoticed"* — and that
  reason does not reach here: the measurement is over and safe, the `.ti3` is
  the record, the report is derived from it, and the **Measurement report…**
  button rebuilds it on demand. Nothing is interrupted and there is nothing to
  do at that instant. If Basti wants a window instead, it is one call.
- wording is **§M-PROPOSED and unapproved**: M-REPORT-NOT-SAVED, in
  `workflow/measurement_messages.py` with `approved=False`, defined in
  §M-PROPOSED of `unified_measurement_management.md`, named in that document's
  "Awaiting review" line, and listed in `AWAITING_APPROVAL` in
  `tests/test_message_catalogue.py`. The method is registered in that file's
  `WINDOW_SOURCES`, so it is held to the same two rules as every window: the
  text is the catalogue's, and the method writes no prose of its own.
  `_IDENTICAL_TO_KEY` and `_BUDGET` +6 in the eleven for this item and B8-54
  together, 0 in German, both with dated notes.
- **held to Basti's standing rule for user-facing text** — *"friendly,
  extensive, easy to understand and correct"* — which changed the message after
  it was first written, in four ways, each with a guard:
  - **the exception came OUT of the message.** The first draft ended
    *"ChromIQ could not write it: {reason}"*, with `str(exc)` — an errno and a
    path — and `type(exc).__name__` when the exception carried no message. That
    blames, it is not plain language, and it is not even correct: the same
    `except` catches a failure to BUILD the report and a failure to WRITE it,
    so a sentence built around it states a cause nobody has established. The
    message now carries **no placeholder at all**; the technical line follows
    it, named as such, as `[Report] Technical detail: <class>: <message>`, and
    the message points the reader at it.
  - **the headline says what is true of both endings**: "could not be
    **created**", not "could not be saved".
  - **the first paragraph is the reassurance**, before anything about the
    failure: *"Your measurement is safe. It was read, checked and written to
    disk exactly as it always is, and nothing about it has changed."* A user
    who reads "the report failed" and concludes their measurement is gone has
    been badly served by a technically accurate sentence.
  - **the usual reasons are offered as things to check, never as a diagnosis**
    — a moved folder, a full disk, a folder ChromIQ may not write into — and it
    says nothing needs measuring again, where the report can be opened from,
    and where the automatic report is switched off.
- **driven on screen, with a REAL failure, not a stub**: the run folder is made
  read-only, so `save_report`'s `reports/` mkdir raises the operating system's
  own `PermissionError` — `scripts/drive_report_defects_onscreen.py`, shots
  `01-measure-tab-report-failed.png` and `02-measure-tab-report-saved.png` in
  `~/Desktop/beta 8/25-report-defects/`. Settings sandboxed with
  `CHROMIQ_SETTINGS_FILE`; `defaults read com.chromiq.ChromIQ
  custom_output_path` unchanged (`""`) afterwards.
- one mutation, proved to land before it was run: `self._say_report_not_saved(exc)`
  replaced by `pass  # MUTATION` (grepped in the file at line 12886), five of the
  eight guards went red, and the three that did not are the good-path,
  option-off and support-log guards the mutation does not touch.
- evidence: test_a_report_that_cannot_be_built_is_reported_on_screen,
  test_a_report_that_cannot_be_written_is_reported_on_screen,
  test_the_status_line_says_it_too,
  test_the_whole_body_reaches_the_user_not_just_the_headline,
  test_an_exception_with_no_message_still_names_something,
  test_a_report_that_saves_says_only_that,
  test_the_option_being_off_is_still_silent,
  test_the_python_log_line_was_not_traded_away,
  test_the_message_says_first_what_was_not_lost,
  test_the_message_carries_no_exception_text_of_its_own,
  test_the_message_claims_no_cause_it_cannot_know,
  test_the_message_says_what_to_do_and_that_nothing_needs_redoing,
  test_the_message_is_approved_and_the_ruling_is_recorded

### B8-55 · Saved measurement reports were silently re-graded by whatever the thresholds say today
- blocks release: no
- status: FIXED
- found by: AGENT-AE, from the #182 design work
- ruled by: Knut, #182, 2026-09-04 — *"Verdict should be saved for each dated
  run."* Authorised by Basti, 2026-09-04.
- detail: the Pass thresholds are a GLOBAL setting
  (`report_pass_threshold_avg` / `_max`, `core/settings.py`), re-read on every
  construction of the report window, and a saved report stored **neither** the
  thresholds it was judged with **nor** the verdict it was given —
  `accuracy_verdict` ran at DISPLAY time. So nudging one spin box silently
  re-graded every historical report the user had ever made: a run recorded as
  Pass in March read Fail in September, with nothing on the page to say that
  anything had changed. A dated record that changes its own verdict after the
  fact is not a record.
- fix: two optional keys, written once, at the moment the report is saved —
  `pass_thresholds: {avg, max}` and `verdict: {rows, all_pass, source, graded}`,
  stamped by `workflow.measurement_report.stamp_verdict` from
  `TabMeasure._maybe_save_measurement_report` BEFORE `save_report`. The window
  reads them back through `recorded_verdict` / `recorded_thresholds` and shows
  those, in the Report Results grid and in each run's own accuracy table. The
  rows are stored as well as the thresholds because the two answer different
  questions: the thresholds say what the user asked of this print, the rows say
  what ChromIQ concluded — which stays true even if a later version changes
  `ACCURACY_METRICS` or the in-gamut rule under it.
- **scoped deliberately to the ruling.** The wider #182 design — a separate
  thresholds window, compliance presets, thresholds bound to a verification run
  — is still being designed and NONE of it is here.
- **nothing on disk is bumped, rewritten or destroyed.** `REPORT_SCHEMA` stays
  at **7**: the window treats an older schema as stale and rebuilds it from the
  run's `.ti3`, so a bump would silently re-derive every report on disk — the
  exact fault this fixes, done wholesale. Both keys are optional and a report
  that lacks them is detected by their ABSENCE. A test opens an old report, reads
  it and asserts the bytes on disk are unchanged.
- **what an OLD report shows, and why.** It has no recorded verdict, so it is
  still graded live by the window's thresholds — blanking it would delete a
  working feature from every report the user owns — but it **says so**: the
  Report Results grid grew a "Pass thresholds" row reading `2.0 / 3.0` for a
  recorded column and *"not recorded"* for an unrecorded one, with a footnote,
  and each run's accuracy table carries one sentence naming where its Pass and
  Fail came from. What it may never do is claim in silence to have been judged
  by numbers set years later.
- **the stale-rebuild hole was found and closed**: `_gather_runs` rebuilds a
  report whose schema predates the current one, keeping only its date. That
  rebuild recomputes today's STATISTICS, which is right, and must not recompute
  the JUDGEMENT — it now carries `pass_thresholds` and `verdict` across
  untouched, driven through the real gather rather than read off the source.
- **driven on screen**: two dated reports of one project, one saved WITH its
  verdict at 2.0/3.0 and one exactly as every report already on disk looks; the
  window opened, the thresholds loosened to 9.0/9.0. The unrecorded column
  flipped to five Passes, the recorded one did not move a single cell —
  `scripts/drive_report_defects_onscreen.py`, shots `03b-…`, `04-…`, `05-…` and
  `06-…` in `~/Desktop/beta 8/25-report-defects/`.
- **held to the same standing rule**, and it changed the wording twice. An old
  report reading *"not recorded"* must not look like an error, and must not
  look like a fresh verdict either — so the grid footnote now opens *"A column
  whose thresholds read “not recorded” is not a fault, and nothing is missing
  from it"*, and the run's own note opens *"Nothing is wrong with this
  report"*, says which version of ChromIQ saved it, and says plainly that the
  numbers above are today's and that moving the thresholds moves them.
- **a second, smaller fault was found while doing that and is fixed here**: the
  Report Results footnote block ASSIGNED where it should have appended, so a
  report holding a raw-drift sheet AND a column with no recorded verdict lost
  one of the two notes without a trace. Guarded by
  `test_both_footnotes_survive_each_other`.
- four mutations, each proved to land before it was run: `_verdict_rows`
  ignoring the recorded verdict (3 red), the `stamp_verdict` call removed from
  the Measure tab (2 red), `kept = {}` in the stale rebuild (1 red), and the
  footnote `+=` put back to `=` (1 red).
- evidence: test_stamping_records_the_thresholds_and_the_verdict,
  test_the_verdict_is_stamped_before_it_is_saved_not_after,
  test_the_limits_come_from_the_run_not_the_module_defaults,
  test_a_gamut_split_is_judged_on_its_within_gamut_figures,
  test_a_raw_drift_check_records_no_pass_or_fail,
  test_a_report_with_no_reference_records_no_verdict_either,
  test_a_stamped_report_survives_a_round_trip_through_json,
  test_the_schema_is_not_bumped,
  test_an_old_report_is_read_without_being_rewritten,
  test_a_damaged_verdict_block_reads_as_no_verdict_not_as_a_crash,
  test_the_window_shows_the_recorded_verdict_not_todays,
  test_changing_the_windows_limit_set_does_not_move_a_recorded_verdict,
  test_a_report_with_no_recorded_verdict_is_still_graded_and_says_so,
  test_an_old_report_is_re_graded_when_the_limit_set_changes,
  test_the_recorded_thresholds_are_the_ones_printed_in_the_detail_table,
  test_a_stale_rebuild_carries_the_recorded_verdict_across,
  test_the_window_and_the_record_share_one_drift_rule,
  test_an_unrecorded_verdict_does_not_read_as_a_fault,
  test_a_recorded_verdict_says_plainly_that_the_spin_boxes_cannot_move_it,
  test_both_footnotes_survive_each_other
- **found and NOT changed, reported instead** — three siblings of B8-54's shape
  in the same tab, each governed by a design specification, so CLAUDE.md's
  binding-specification rule says report before fixing:
  `tab_measure.py:1287` *"Could not save the target's Measure settings"* and
  `:1304` its read (governed by `per_target_settings.md`),
  `:5703` / `:5755` *"Could not snapshot the verification/profiling chart"*
  (governed by `unified_measurement_management.md` §4a — the snapshot is what
  ties a dated verification to the sheet it was measured with), and
  `:3664` *"Could not offer the existing measurement"* (§5 — the window that
  does not appear is the one asking before a measurement is replaced). All
  three are log-only today. The report window's trend-chart threshold guide
  lines are still drawn from the live spin boxes, deliberately: they are a
  guide on a chart of many dates, not a verdict on one.

### B8-56 · The Profile type control said something nothing measured, and treated the two cLUTs as equals
- blocks release: no
- status: FIXED
- found by: B8-19's measurement (AGENT-AD), implemented by AGENT-AF on Basti's
  ruling that *the answer must be reflected in the app*, not only in a reply.
- detail: three separate faults in one row of `Tools ▸ Build profile with
  scanner or camera`.
  **(1) The help asserted something unmeasured.** *"XYZ and Lab are just how the
  table stores colour inside; both are accurate, and Lab sometimes gives
  slightly smoother neutrals."* Nothing measured that, in either direction —
  B8-19's held-out neutrals are 0.78 Lab against 0.82 XYZ, inside each other's
  noise — and the sentence said nothing about the one difference that IS
  reliably measurable.
  **(2) The two cLUTs were offered as interchangeable.** They are not: a Lab
  cLUT cannot encode anything above its chart's white, so a neutral ramp through
  one reads L* 100.4 flat from device 82 upward where the XYZ table and
  shaper+matrix both run on to L* ~119.5 (deterministic — no seeds — and
  reproduced at `-qh`). An IT8's own white is only ~80 of 100 on a real scan, so
  that ceiling sits inside the range a scanner uses every day.
  **(3) The help gave no rule for when to leave the default at all**, which is
  what Knut asked for: *"Maybe the help text for the profile type should give
  recommendations for when to use the LUT types, such as when one has large
  targets with many patches…"*
- fix: `ui/dialogs/scanner_colprof.py` gains `ptype_help(printer)`,
  `ptype_advice(printer, ptype, n)` and `PTYPE_RECOMMENDED_CLUT`, beside the
  `PTYPE_DEFAULT` they have to agree with; `scanin_dialog.py` keeps the ⓘ as
  `_ptype_tip`, adds `_known_patch_count()` and `_sync_profile_type_advice()`,
  and calls the latter from `_on_colprof_changed` and a `_refresh` override.
  Three things reach the user:
  * **the help is rewritten and is MODE-AWARE.** It names the sizes at which
    each type is worth choosing (a ColorChecker's 24, a full IT8's 288, an ISO
    12641-2 set's 864), says where the user can read their own count (beside
    each target's name in the Target list, and in the green "✓ … patches"
    line), and states the lightness ceiling in what it MEANS — highlights above
    the target's white arrive at one lightness — never as "L* 100.4". It differs
    by mode because the advice does: `colprof.html` makes the XYZ claim of
    INPUT devices, AGENT-AD measured input profiles only, and nothing a printer
    prints is lighter than the paper it prints on, so **no recommendation is
    made on the printer side** and the Lab "(default)" there stands alone.
  * **the dropdown marks the cLUT to take**, in scanner/camera mode only:
    "cLUT — XYZ table (recommended cLUT)", written by the same method that
    already writes "(default)". **The Lab option is not removed, not disabled
    and not relabelled** — Knut likes its results, it stays a legitimate choice,
    and picking it still emits `-al` unchanged.
  * **a live note appears inside that ⓘ once the patch count is known**
    (`TooltipButton.set_live_note`, so no new widget and nothing on the face of
    the window): a big target with shaper+matrix chosen, a small target with a
    cLUT chosen, or Lab chosen at all. It changes no setting, never fires with
    the count unknown, never fires in printer mode, and clears itself. The
    AUTOMATIC switch B8-19 rejected is still rejected — this is the
    proportionate form of the same information.
  Wording is **PROPOSED, not approved**: it is reproduced verbatim, English and
  German, in `docs/design/unified_measurement_management.md` ▸ "⏳ Awaiting
  confirmation — Profile type help text", carrying `**Confirmed by:** *nobody
  yet.*` i18n: 22 keys added, 1 retired; German translated, the other eleven
  carry the English source per the beta convention, and `_IDENTICAL_TO_KEY` in
  `tests/test_i18n.py` is updated with its reason.
- evidence: test_no_user_facing_string_anywhere_still_makes_the_claim,
  test_the_help_the_window_actually_shows_does_not_make_the_claim,
  test_the_unsupported_neutrals_claim_is_gone_from_every_catalogue,
  test_the_recommended_clut_is_xyz_for_a_scanner_and_nothing_for_a_printer,
  test_the_dropdown_points_at_the_xyz_clut_in_scanner_mode,
  test_a_recommendation_is_never_the_default_and_is_never_swallowed,
  test_printer_mode_recommends_nothing_and_keeps_the_lab_default,
  test_the_help_is_mode_aware_and_each_mode_names_its_own_default,
  test_the_help_follows_the_printer_tick_in_the_real_window,
  test_the_live_note_fires_only_where_the_measurement_is_unambiguous,
  test_the_note_reaches_the_tooltip_and_leaves_again,
  test_the_note_never_changes_a_setting,
  test_a_multipage_target_is_counted_whole,
  test_profile_type_clut_lab_high_maps_and_previews,
  test_window_title_and_defaults_are_mode_aware,
  test_catalog_is_complete, test_catalog_has_no_stale_keys,
  test_untranslated_values_do_not_creep_in_unseen
  — 11 mutations applied one at a time, each proved to land (anchor asserted
  unique, presence re-read after writing) and each proved to turn a guard red;
  table in `beta 8/_progress/agentAF-mutations.txt`. One of them, M3, showed a
  test of my own was weaker than it read and it was rewritten: setting the
  printer recommendation EQUAL to the printer default is silently swallowed by
  `_mark_default_combos` rather than double-marking an item, so the invariant
  now pinned is the pair — a recommendation must differ from that mode's
  default AND be on screen exactly once.

### B8-57 · The same unmeasured "smoother neutrals" claim is also in tab 4's -a tooltip
- blocks release: no
- status: OPEN
- found by: AGENT-AF while removing it from the scanner window (B8-56).
- detail: `data/parameters.yaml`, the `colprof` `-a` entry, `tooltip_body`:
  *"XYZ cLUT (-ax): Similar to Lab but in XYZ space. **Sometimes produces
  smoother neutral gradients.**"* It is the same unmeasured sentence as the one
  B8-56 removed, with the two options swapped over, and it reaches tab 4 ▸ Build
  profile ▸ Manual.
- why it is not fixed here: B8-19 measured SCANNER input profiles. This claim is
  about a PRINTER output profile and nothing has been measured about those, so
  replacing it would swap one unmeasured sentence for another — the exact fault
  B8-56 exists to remove. Deleting the sentence outright needs no measurement
  and is a one-line edit, but it is new user-facing wording (a §M-PROPOSED
  matter, Basti's ruling) and the sentence is translated in all twelve
  `data/i18n/parameters.*.yaml` overlays, so it is a small change with a
  paperwork tail rather than a drive-by.
- suggested: delete the sentence and say nothing in its place; the rest of the
  entry ("Lab cLUT: best accuracy for printer profiles… Recommended") is
  ArgyllCMS's own position and is unaffected.
- evidence: —

### B8-59 · The file dialog's back / forward / up arrows are invisible in Neutral
- blocks release: no
- status: FIXED
- found by: Basti, on screen in Neutral (2026-09-05) — *"in file opening /
  saving dialogs in the neutral color scheme the back forward and up button
  icons are not really visible because of low contrast"*
- detail: `ui/widgets._style_file_dialog_toolbar` recolours the three nav
  buttons itself (`backButton` / `forwardButton` / `toParentButton`, from the
  Qt standard pixmaps, filled SourceIn by `_nav_icon`). It chose the colour
  with a two-answer fold — `QColor("#1C1B18" if mode == APPEARANCE_LIGHT else
  "#e0e0e0")` — so **Neutral, not being Light, took the DARK branch**:
  `#e0e0e0` arrows on Neutral's `#e2e2e2` toolbar. Measured on screen through
  the real `open_file_dialog` (Fusion, `dlg.grab()`), identical for all three
  buttons: normal **1.03:1**, hover **1.14:1**, pressed **1.18:1**, disabled
  **1.02:1**. There was no state in which they came back. It is the same shape
  `ui.theme.by_mode` exists to replace, and the same one CLAUDE.md records
  costing a third appearance its assets elsewhere. Worse than the fold alone:
  the mode came from the SETTINGS (`resolve_mode(AppSettings().get(...))`), not
  from the dialog, so a dialog wearing a palette that disagreed with the
  setting got the wrong ink too.
- fix: `ui/widgets.nav_arrow_ink(dlg)` — the ink is READ from the dialog's own
  palette (`Active` / `ButtonText`) and never chosen per appearance. Not a
  third literal and not a hard-coded black: Neutral's ButtonText *is*
  `NM_TEXT_MAIN` (`#101010`), hueless because the whole Neutral token table
  is; Light's is `LM_TEXT_MAIN`, Dark's is `TEXT_MAIN`. A fourth appearance is
  right the day its palette exists, with no edit here. All four dialog helpers
  (`open_file_dialog`, `open_files_dialog`, `save_file_dialog`,
  `open_dir_dialog`) already funnel through the one styling call, so the fix
  reaches every file dialog in the app; the native-dialog preference is
  untouched and out of reach either way (an OS dialog draws its own arrows).
  Measured after, same method: Neutral **14.69 / 15.82 / 12.21 / 4.24**
  (normal / hover / pressed / disabled) — 14.69:1 is exactly `neutral_styles`'
  own documented figure for `NM_TEXT_MAIN` on the panel. Light 13.64 / 15.94 /
  11.28 / 3.96 and Dark 14.23 / 12.44 / 13.80 / 10.40, both unchanged in
  character (Light moves ~1 point because the arrows now use Light's own
  declared text ink instead of a slightly darker one-off; still 3x AA).
  Disabled is exempt from WCAG AA as an inactive component, and the shape
  still reads in all three.
- evidence: test_every_file_dialog_helper_styles_its_toolbar,
  test_the_nav_arrow_ink_is_the_dialogs_own_button_text,
  test_the_nav_arrows_clear_wcag_aa_on_every_appearances_toolbar,
  test_the_nav_arrow_icon_is_actually_painted_in_that_ink,
  test_the_arrow_colour_is_not_chosen_by_a_two_answer_appearance_fold
  — 5 mutations applied one at a time, each anchor proved unique and each edit
  re-read from disk before running, each turning a guard red: the original fold
  restored (6 red, naming Neutral by name), one helper stopped styling its
  toolbar (1 red), the ink back to a literal (4 red), the ink never reaching
  the icon (4 red), the ink read from the Disabled colour group (6 red). Ledger
  in `beta 8/_progress/agentAG.md`; before/after screenshots and per-state
  numbers in `beta 8/27-file-dialog-arrows/`.

### B8-60 · Two more tests could destroy a running QThread, in a file the crash report marked clean
- blocks release: no
- found by: Agent BA, verifying PR #188 on macOS with a detector written for it
  (`scratchpad/qthread_detector.py` — it replaces `PyQt6.QtCore.QThread` with a
  registering subclass BEFORE conftest loads, keeps a strong reference so it
  reports rather than reproduces, and asks the registry twice: when the test
  FUNCTION returned, and after teardown finished). Grepping for `QThread` and
  running each file alone cannot find this — the destruction happens in a LATER
  test, which is the whole property of the bug. The Windows session's own
  challenge (`beta 9/staging/12_drift_challenge.md`) had named the class open
  and predicted seven sites.
- status: FIXED
- detail: PR #188 root-caused the gate's silent worker death to a test ending
  with a live QThread and fixed two sites. Over the whole everyday tier on the
  rebased branch (10,492 passed) the detector finds **eight** tests that return
  while a QThread they made is still running, and none survives to session end.
  Four are in the file the PR fixed and are joined by its new autouse fixture —
  which is the positive control that the detector can see what it is looking
  for. What matters is the OWNERSHIP of the other four, not the count:
    * `tests/test_cr30_spot_read.py` (2) — **safe, and deliberately so.**
      `workflow/cr30_spot_manager.py:_start_loop` creates its read thread
      UNPARENTED and `_keep_until_finished` holds it in the module global
      `_LIVE` until `isFinished()`, with a comment saying exactly why. Nothing
      can destroy those while they run.
    * `tests/test_cr30_measure_bridge.py::test_a_reading_for_a_patch_we_are_no_longer_on_is_dropped`
      and `tests/test_cr30_a_press_before_the_read_opens_is_kept.py::test_a_refused_read_does_not_hand_its_press_to_the_retry`
      — **real.** `workflow/cr30/measure_bridge.py:_start_read` was the one
      place in the CR30 stack that still wrote `QThread(self)`, so the bridge
      OWNED the thread; and the bridge, `_threads`, the thread, its `finished`
      connection and the lambda that closes back onto the bridge form a
      reference cycle, freed at an arbitrary later moment.
  Measured on this machine, one seven-line script run against the two versions
  of the module — bridge dropped while a read is held open, interpreter allowed
  to end: `QThread(self)` gives `QThread: Destroyed while thread '' is still
  running`, **Abort trap: 6, exit 134**; `QThread()` gives **exit 0**. Qt 6.11 /
  PyQt 6.11. On Windows that same `qFatal` is the fail-fast `0xC0000409` the PR
  describes, which is why the gate logs carry no traceback.
  Product risk is nil and was checked rather than assumed: the app's bridge is
  owned by the Measure tab, and `main.py` ends on `os._exit`, so the widget tree
  is never destroyed at quit. This is a test-run crash, which is precisely what
  makes it expensive — it reads as somebody's regression.
- fix: `workflow/cr30/measure_bridge.py` now does what its sibling module
  already did: the read thread is created UNPARENTED and the last reference is
  held in a module-level `_LIVE` until the thread reports itself finished
  (pruned in `_reap`, and defensively on each new read). Nothing else moves;
  `self._threads` still governs the bridge's own view of what is in flight.
- evidence: test_the_read_thread_is_not_the_bridge_s_to_destroy,
  test_the_worker_is_kept_referenced_until_it_finishes
  — 2 mutations applied one at a time, each anchor proved unique and each edit
  re-read from disk before running: re-parenting the thread (`QThread(self)`)
  turns it red on the parent assertion AND prints Qt's own "Destroyed while
  thread is still running"; dropping the `_LIVE.append` turns it red on the
  keep-alive assertion. Restored, green again. An abort cannot be asserted on —
  it takes the assertion with it — so the guard is the invariant, and the abort
  is the measurement quoted above.

### B8-61 · `Run.chart_ti2.exists()` is False on NTFS for a decomposed name, and three windows branch on it
- blocks release: no
- found by: the Windows ARM64 session's challenge of PR #188
  (`beta 9/staging/12_drift_challenge.md`), re-read here while landing that PR.
- status: FIXED
- detail: `tests/test_a_decomposed_name_finds_its_files.py` had never run on
  Windows at all — it called `os.uname()` inside a `skipif`, which is evaluated
  when the decorator is BUILT, so on Windows the whole file failed to collect
  with `AttributeError`. PR #188 fixed that with `sys.platform`, and collecting
  the file for the first time exposed a premise that is TRUE ONLY ON APFS/HFS+:
  a path spelled NFC finds a file written NFD. NTFS is normalisation-sensitive,
  so `run.chart_ti2.exists()` is False there for a project whose name carries an
  umlaut and travelled from a Mac. The PR guarded those two assertions behind
  `IS_MACOS`, which is right for the TEST — the thing each test is about,
  `files_matching` finding all four page TIFFs, is still asserted on every
  platform — but it leaves the PRODUCT question open and now unguarded:
  `ui/main_window.py:1577`, `:2238` and `:2866` all branch on
  `chart_ti2.exists()`, so on Windows the app can decide a chart is absent that
  is sitting in the folder. Related to, but not the same as, the deferred
  "umlauts go cryptic on Windows" zip finding: this one needs no zip, only a
  name that was ever normalised the Mac way.
- **priority raised by the beta 9 release check, though still not blocking**:
  the entry above understates `ui/main_window.py:2866`. That branch skips
  `note_generated_chart`, so for a verification target the Print tab leaves
  "Through the profile" live for a chart that has already been converted —
  §3.1a exists to force Raw precisely there — and the sheet is printed twice
  through the profile. It needs Windows AND a non-ASCII name AND a Mac-created
  folder AND session restore AND a verification run, which is why it does not
  hold a release; but it is a wrong print, not a cosmetic fallback. The other
  two branches are cosmetic: `:2238` falls back to a `.ti1` that shares the
  same defeated stem, so the user gets an honest "no chart".
- fix: **PR #189**, `core.file_manager.resolve_existing(path)` — at the
  ACCESSOR, not at the three call sites. It returns the spelling the volume
  really holds, so the path both answers `exists()` and OPENS; a call-site
  `.exists()` fix would have moved the failure to the `open()` two lines later
  (`load_rgb_program`, `shutil.copy2`, `note_generated_chart` all USE it).
  Every stem-named artefact of a `Run`, a `Calibration` and a `Verification`
  goes through it via the now-public `Run.artefact(ext)` /
  `Calibration.artefact(ext)`, because ~155 places ask a `Run` for a file and
  the next one is not written yet. The exact spelling is asked for FIRST, so
  nothing is ever swapped for a neighbour; an absent file comes back unchanged,
  so writers still create the composed name; case folds only where
  `_NAME_CASEFOLD` says the filesystem folds it, the same flag `files_matching`
  uses eighty lines above. Making the guard truthful then RAN code that had
  never run on such a project, and two of those paths still built names with
  f-strings — `adopt_run_chart_as_verify` orphaned a one-page chart's only
  TIFF in the run root, and `workflow.chart_import.archive_run_for_replace`
  archived half a chart so `run.chart_cht` handed the scanner the OLD chart's
  recognition file for the NEW `.ti2`. Both fixed, and the same shape swept for
  and fixed in six further places (`reset_chart_artefacts`,
  `settle_chart_stash`'s leftovers, the v3 verification migration,
  `TabChart._reflect_loaded_project`, the profiling-chart snapshot, and
  `run_delete`'s `.icm` probe).
- deliberately NOT fixed, and pinned rather than left unknown: a composed name
  TYPED into the Create Chart box still does not find a decomposed project
  FOLDER, so a second, empty, identically-drawn folder is created beside it.
  Fixing it means changing either the "a folder name is always NFC" invariant
  or `working_dir`'s re-clean-and-compare, both pinned behaviour with a
  documented reason — a decision to be taken and reviewed, not slipped into a
  bug fix. Every route that reaches a project through the FOLDER (the picker,
  `open_project_at`, session restore) is unaffected and works today.
- evidence: test_a_named_artefact_resolves_to_the_spelling_that_is_on_disk,
  test_the_mirror_shape_resolves_too,
  test_the_ti1_is_not_quietly_substituted_for_a_ti2_that_is_there,
  test_the_exact_spelling_always_wins_when_both_are_on_disk,
  test_an_absent_artefact_keeps_its_composed_name_so_a_writer_creates_that,
  test_a_rewrite_overwrites_the_chart_instead_of_laying_a_second_beside_it,
  test_case_is_never_folded_by_the_resolver,
  test_the_whole_chart_chain_and_the_verify_chart_resolve,
  test_a_calibration_finds_its_own_restored_chart,
  test_the_ui_resolves_the_restored_chart_and_not_its_ti1,
  test_a_single_page_verify_chart_takes_its_page_with_it,
  test_the_multi_page_case_still_works_and_is_not_double_moved,
  test_a_replace_archives_the_whole_restored_chart_chain,
  test_a_regenerate_does_not_leave_a_second_chart_under_one_name,
  test_the_accessor_finds_whatever_the_listing_finds,
  test_which_of_several_spellings_wins_is_not_the_listing_order,
  test_a_name_with_no_other_spelling_never_lists_the_directory,
  test_a_name_that_really_has_another_spelling_is_still_looked_for,
  test_a_typed_composed_name_does_not_yet_find_a_decomposed_project_folder,
  test_every_per_chart_sidecar_is_on_both_lists.
- **the NTFS half is Windows evidence and stays Windows evidence.** The fault,
  the before/after table (`:2238` resolving `.ti1` 180 patches -> `.ti2` 462
  patches) and the German on-screen run were produced on the Windows 11 ARM64
  VM. An independent macOS review (agent BK, 2026-09-05) could not reproduce
  any of it and did not try to claim otherwise: **macOS cannot hold two
  canonically equivalent file names in one folder at all** — measured on three
  disk images made for the purpose, APFS case-insensitive, "Case-sensitive
  APFS" and macOS's exFAT driver, every one of which folds the pair onto one
  file. What that review established instead is that the change is a **pure
  no-op on macOS**: `resolve_existing` was called **6,257 times across a whole
  `--runslow` gate and returned a path different from the one it was asked for
  exactly 0 times**, because `Path.exists()` on APFS answers True for the other
  spelling and the fast path returns before the directory is ever listed. The
  release gate went 11,213 passed (master) -> 11,246 passed, 0 new failures;
  the 34-check scanner sweep gave verdict-for-verdict identical results before
  and after; and driving the real window through chart creation, the Create
  Chart tab's current-chart panel and the Print tab on both trees produced two
  borrowed projects byte-identical in all 25 files, `.ti1` and both page TIFFs
  of a freshly built chart byte-identical, and a `.ti2` differing only in
  printtarg's `CREATED` timestamp and random `CHART_ID`.
- one defect was found and fixed IN the PR while landing it:
  `test_the_exact_spelling_always_wins_when_both_are_on_disk` asserted on the
  CONTENT of two files that macOS folds into one, so the release gate was red
  on macOS while green on the machine the branch was written on. The guarantee
  (the NAME that comes back is the one asked for) is now asserted on every
  volume and the content check is asked only where there are two files.

### B8-62 · The CR30 refused the most saturated patches on glossy paper, and called a real reading a truncated reply
- blocks release: yes
- status: FIXED
- found by: **nertog**, printerknowledge.com post #622 (2026-09-05), with the
  screenshot `1788581562184.png`. His own reading of it — *"I believe this is
  not a real error, and that the 0-bands might just be coming from a very
  saturated colorimetric value"* — was **correct**, and it is the clue that
  found this. Canon iP8770, OEM inks, latest beta, CR30 over Bluetooth.
- detail: the window said *"That reading did not come through … candidate at 0
  has **3** zero bands (truncated reply)"*. Three is exactly the threshold
  `Measurement.zero_run() >= 3` refused on, and every truncated reply this
  project has ever recorded had a run of **5, 16 or 31** — never 3. The
  threshold's premise, written into `zero_run`'s own docstring as *"a real dark
  patch reads a few percent, never exactly 0.0 across a run"*, is contradicted
  by this project's own captures: the firmware CLAMPS, so a signal at or below
  the stored dark reference comes back as exactly 0.00000 %R — EXP-022 on open
  air (`device.read_measurement` docstring), EXP-020 phase A *"0.00000 exactly,
  all 31 bands, ALL FIVE readings"* and phase C's `0.000` among real numbers
  (`docs/cr30_reports/20_blackcal.md:76-80`), and again on the owner's own unit
  2026-09-05 (31 bands, every one exactly 0.0). The paper dependence he reported
  is the mechanism speaking: ink on glossy sits on the surface and reaches
  roughly 0.2–0.4 %R where it absorbs, against 1.3–2.5 %R for the same ink soaked
  into matte, and the CR30 has no black tile — its dark reference is taken
  against open air and can sit high by ~0.15 %R (EXP-020 phase C;
  `20_blackcal.md` F5 works the arithmetic). So glossy crosses the floor and
  matte does not. **The cost was not one refused reading**:
  `measure_bridge.MAX_READ_RETRIES` re-arms the patch five times and then gives
  up on it (`M-CR30-PATCH-GAVE-UP`), and the cause is deterministic, so resuming
  with `-r` meets the same refusal — the chart could never be finished. Nothing
  measured was lost; nothing further could be measured.
- verified: reproduced verbatim through the real read path. A 200-byte BLE reply
  carrying an ordinary saturated-blue spectrum (24.1 %R at 400 nm falling to the
  floor from ~600 nm, three bands clamped at 640/650/660 nm) and a real device
  Lab, fed to `CR30.read_measurement()` on master `1b9cad54`, produced
  *"no usable reply among the only candidate in 200 bytes; last reason: candidate
  at 0 has 3 zero bands (truncated reply)"* — byte-for-byte the sentence in the
  screenshot. With the fix the same reply is accepted, spectrum and Lab intact.
  The new test file run against unfixed master: **8 failed, 4 passed**; with the
  fix, **12 passed**. Six mutations, each proved to land by a file hash before
  the run, each caught (`M1`–`M6`).
- fix: `Measurement.truncation_reason()` replaces the zero-run threshold in
  `check_usable`, and at both call sites in `device.py` (`_parse_reply`'s polling
  predicate and the candidate scan). It is exact rather than a threshold, and it
  covers every truncation on record: (1) **every band exactly 0.0** — no reading
  in the reply at all, which is the recorded 31- and 16-band not-ready buffers
  and is what `allow_dark` exists to permit for the black calibration; (2)
  **reflectance in the spectrum but a Lab of pure black** — those cannot both be
  true, and it is a proof rather than a guess, because `SPECTRUM_AT` (8–131)
  sits BEFORE `LAB_AT` (184–195), so a reply truncated anywhere inside the
  spectrum has necessarily lost its Lab as well. `zero_run()` is kept but demoted
  to a diagnostic and pinned as one; `clamped_bands()` is new, and an accepted
  reading with clamped bands now writes a `log.info` line saying so, because
  those bands are a floor rather than a measurement. **No user-facing catalogue
  text changed** — `M-CR30-READ-FAILED` is unaltered and only its technical
  `{reason}` slot reads differently, which the catalogue's own note reserves for
  the instrument's words.
- evidence: test_the_field_report_reading_is_accepted_not_refused,
  test_the_words_from_the_field_report_can_no_longer_be_produced,
  test_the_polling_predicate_stops_on_a_saturated_patch,
  test_a_clamped_reading_passes_the_full_gate_on_the_usb_path,
  test_a_run_of_zeros_is_no_longer_a_reason_on_its_own,
  test_the_number_of_clamped_bands_is_reported,
  test_a_wholly_zero_filled_reply_is_still_refused,
  test_a_half_written_reply_is_still_refused,
  test_the_truncated_half_of_a_double_reply_still_loses_to_the_complete_one,
  test_the_black_calibration_read_back_still_gets_its_answer,
  test_no_zero_run_threshold_decides_a_reading_any_more
  (all in `tests/test_the_field_report_reading_is_accepted_not_refused.py`), plus the
  older guards that must not move:
  test_the_truncated_half_of_a_double_reply_is_rejected,
  test_a_partial_reply_is_not_enough_to_stop_on,
  test_nothing_at_all_is_not_a_reply
  (`tests/test_the_polling_predicate_stops_on_a_saturated_patch.py`)
- still open, for Basti to decide, NOT fixed here: a reading whose bands are
  clamped is at the instrument's floor, so a profile built from it is slightly
  optimistic in that ink's darkest region. Today that is a log line only. Whether
  the user should be TOLD — and in what words — is a new §M message and therefore
  his call, not an agent's.

### B8-63 · The driver consent window's DECLINE button said "OK"
- blocks release: no
- status: FIXED
- found by: Agent BB's review of PR #187 (F20), `beta 9/_progress/agentBB.md`;
  ruled on by Basti — *"fix the ok button and the grammar, then land it"*.
- detail: `ui/dialogs/settings_dialog.py::_driver_notice` shows two kinds of
  window. With no second button it is a NOTICE and OK is the right word for
  acknowledging one. With a second button it is an OFFER, and the plain button
  is the DECLINE — `ok.clicked.connect(dlg.reject)`, deliberately, because
  `box.accepted` fires for OK too and that is how OK once came to start an
  elevated driver install (`f7a565ad`). That behaviour is right and a mutation
  against it kills seven tests. **The WORD was still wrong.** On "Before ChromIQ
  starts" — the one window in ChromIQ whose entire purpose is informed consent —
  the row read `Herunterladen und installieren` and `OK`, and OK is the word
  most people read as "yes". Somebody skimming clicks it meaning to agree and
  gets the opposite of what they intended.
- fix: (guards live in `tests/test_usb_driver_dialog.py`) the dismissing button says what dismissing does — **`Not now`** /
  **`Jetzt nicht`** — and only when there is something to decline; a plain
  notice still says OK. It is not new vocabulary and it is **zero new
  translation keys**: `ui/cr30_calibration.py` already builds a `Not now` button
  for exactly this meaning, so the two share one key and German is already
  translated. Only `setText` changes — the button stays a `StandardButton.Ok`,
  keeping its role, its place in the row, its identity to `_ok_button()` and its
  status as the dialog's default, so `Return` still declines. The WORDING is
  §M-PROPOSED and unapproved: see "Button label — the driver consent window's
  decline button" in `docs/design/unified_measurement_management.md`, ⏳ awaiting
  confirmation, with the rejected alternative (`Cancel`) recorded beside it.
- evidence: test_the_consent_window_does_not_call_its_decline_button_ok,
  test_the_decline_button_is_still_the_one_enter_presses,
  test_a_notice_with_nothing_to_decline_still_says_ok,
  test_the_decline_label_is_the_apps_own_word_for_declining,
  test_the_consent_buttons_fit_the_row_in_every_language
  — all in the driver-dialog file named under `fix` above. The last one runs in
  all THIRTEEN languages and in the dark appearance's wider button font, and it
  asserts `height < cap` FIRST — BB's vacuity trap: the offscreen screen is
  800x800, so the cap is 720 and the German window sits AT it, where a geometry
  assertion passes without asking anything.

### B8-64 · "da la scheda", "a partir de o separador", "z karcie", "из вкладке" — a preposition glued to a translated noun
- blocks release: no
- status: FIXED
- found by: Agent BB's review of PR #187 (F4), by RENDERING the sentence in all
  twelve languages; ruled on by Basti in the same instruction as B8-63.
- detail: the driver helper refuses to open during a measurement and says why.
  That paragraph formatted `core.instrument_lease.where_label()`'s noun phrase
  into "…is being read right now, from {where}." English survives it, and German
  survives it only because `8d5b8430` hand-inflected both labels into the
  dative. Four languages did not: it "da la scheda Misura" (needs *dalla*), pt
  "a partir de o separador Medir" (needs *do*), pl "z karcie Pomiar" (needs the
  genitive *karty*), ru "из вкладке «Измерение»" (needs the genitive *вкладки*).
  **Nothing in the project could see it.** `tests/test_i18n.py` sees a key that
  is present, translated, and whose placeholder matches;
  `scripts/i18n_extract.py` sees nothing at all, because the broken sentences
  exist nowhere as literals — they are assembled at run time, so no translator
  was ever shown one.
- fix: structural, not four string edits. Hand-inflecting one label cannot work
  when two sentences interpolate it with two different prepositions and the
  language has cases. So `measurement_in_progress()` now returns the lease's
  IDENTIFIER — which `core/instrument_lease.py` documents those constants as —
  and `measurement_block_text()` picks a COMPLETE SENTENCE per holder through
  the new `_read_right_now_sentence()`, with nothing formatted into it. Each
  language writes its own preposition, article and case. It is its own paragraph
  rather than glued to the next with a space, because ja and zh join sentences
  with 。and no space: even joining two translated sentences is a decision the
  code must not make for a translator. Every value is the old sentence split at
  its own full stop, except the four corrections — no approved wording was
  re-invented. i18n: -1 key, +4 x 12; `--missing` 0 of 4969 and `--stale` 0 in
  all twelve, and "0 missing" is NOT the evidence — the corrections were proved
  by rendering them.
- evidence: test_the_guard_is_a_sentence_in_the_four_that_inflect,
  test_the_guard_never_formats_a_label_into_a_sentence_again,
  test_the_guard_is_handed_an_identifier_not_a_label,
  test_the_german_guard_reads_as_a_sentence_for_either_holder,
  test_the_german_guard_window_names_the_spot_tool_grammatically
  — all in the same driver-dialog file. The first renders the four languages
  that were wrong, for both holders, and asserts both the correct form and the
  absence of the glued one; the second pins the STRUCTURE in all twelve, so no
  future wording can go back to formatting a label into a sentence.
- still open, for Basti to decide, NOT fixed here: **`M-INSTRUMENT-BUSY` has the
  identical fault** — "ChromIQ is measuring in {where}", fed by the same
  `where_label()`, from `ui/dialogs/spot_read_dialog.py` and
  `ui/tabs/tab_measure.py`, producing "in la scheda Misura", "in o separador
  Medir", "in karcie Pomiar", "in вкладке «Измерение»". It is worse, because
  that sentence is still the English source in eleven of the twelve catalogues.
  It is a §M message, so its wording is his call and not an implementer's; an
  AST sweep of `ui/`, `workflow/` and `core/` for a translated value formatted
  into a translated sentence found 93 sites and this is the ONLY other one with
  the glued-preposition shape — every other is a button or file name inside
  `<b>…</b>` or „…“, which inflects nothing around it.

### B8-65 · The CR30 truncation proof is one-sided on the USB path
- blocks release: no
- found by: the beta 9 release check (AGENT-BE), reading B8-62's fix rather
  than trusting it
- status: OPEN
- detail: `truncation_reason()`'s second rule — reflectance present while Lab is
  exactly (0,0,0), which cannot both be true — needs a Lab to reason about, and
  `workflow/cr30/usb_measure.py:166` builds its `Measurement` **without one**.
  Proved on shipped code: the recorded 16-zero-band truncation shape is refused
  when a Lab is present and **accepted when it is not**. This is deliberate and
  the tests say so, and it is strictly narrower than the fault it replaced — the
  old threshold refused real readings, this one lets one rare shape through on
  one transport — so it is not a blocker. But the docstring claims a coverage it
  only has on BLE, and a docstring that overstates its own guard is how the
  three-zero-band rule came to be trusted in the first place.
- next step: either give the USB path a Lab to check against, or state the
  limit in the docstring and name the transport. Do not widen the rule back
  into a threshold.

### B8-66 · The Seed box read 0 while the chart on screen had been shuffled with something else
- blocks release: no
- found by: Basti, 4.1.5-beta.9 — *"when creating a chart with the layout engine
  and in the randomisation section 'randomise patch order' is active (which is on
  by default) then there is no way to see which seed number was used it seems.
  when i click the new seed button then the seed number field gets a number that
  is reflecting the seed but on initial generation the seed number there is
  always 0 at first or stuck at any other number even when i generate again. i
  think that even when this field is greyed it should reflect the seed number of
  the chart on screen"*
- detail: reproduced on screen exactly as reported, twice
  (`scripts/drive_seed_field_shows_the_chart.py`, shots in
  `Desktop/beta 9/seed-field/`): two consecutive builds were shuffled with
  1004140342 and 1778456217 while the box read **0** both times, and only "New
  seed" ever moved it. With "Use a fixed seed" unticked
  `layout_options_panel.get_recipe()` sets `seed=None`
  (`ui/dialogs/layout_options_panel.py:4501`), `chart.build_chart` draws its own
  (`workflow/layout_engine/chart.py:247`), and nothing carried the drawn number
  back to the widget. **0 is not a blank** — it is a valid seed producing a real,
  different shuffle — so the box was not silent, it was wrong.
- what was NOT broken, established while in there: the seed is persisted twice
  over — `RANDOM_START "<seed>"` in the `.ti2`
  (`workflow/layout_engine/ti2_writer.py:70,88`) and `layout.seed` in the
  chart's `channels.json` (`workflow/chart_creator.py:1418`) — the two agreed on
  every build driven; the same seed reproduces the same patch order (driven,
  step 6); and reloading the chart brings its seed back into the box with "Use a
  fixed seed" ticked (driven, step 7). The defect was reporting, not
  reproducibility.
- fix: `LayoutOptionsPanel.show_built_seed`, called from
  `TabChart._on_generate_finished` via `TabChart._show_built_seed_in_panel`,
  which reads the seed out of the finished chart's own `channels.json` rather
  than from a variable carried down the call chain — so it is right for every
  route that ends there, including a verification chart that has just been moved
  into `verifications/` under a different stem. DISPLAY ONLY: it does not tick
  "Use a fixed seed", `get_recipe()` still answers `seed=None`, the next build
  still draws a fresh seed, and the write goes in with the spin box's signals
  blocked so the live preview and the helper-marker memory do not move because a
  build finished. Proved unchanged: the same `.ti1` + the same recipe builds a
  byte-identical `.ti1`, `.ti2`, `.strips.json` and page TIFF on this tree and on
  `635a4dd8`, with an identical patch order.
- text: the Randomisation ⓘ gained one sentence saying that the box reports the
  chart on screen even while greyed, translated into all twelve catalogues. It
  is a tooltip, not a message window, so it is outside the §M catalogue.
- evidence: test_zero_is_a_real_seed_and_not_a_placeholder,
  test_a_normal_build_asks_the_engine_for_no_seed_at_all,
  test_the_built_seed_reaches_the_box,
  test_it_shows_even_while_the_box_is_greyed,
  test_showing_a_seed_does_not_tick_use_a_fixed_seed,
  test_a_typed_seed_still_survives_the_display,
  test_the_display_fires_no_change_signal,
  test_a_fixed_order_chart_gets_no_seed_in_the_box,
  test_a_seed_it_cannot_show_leaves_the_box_alone,
  test_the_tab_reads_the_seed_out_of_the_finished_chart,
  test_a_fixed_order_chart_on_disk_is_not_reported_as_shuffled,
  test_a_printtarg_chart_leaves_the_box_alone,
  test_a_chart_with_no_sidecar_at_all_is_survivable,
  test_every_finished_build_goes_through_it,
  test_it_is_read_from_the_chart_and_not_from_a_carried_variable
  — all in the seed-box file under `tests/`, whose name is the first test's
  subject. Eight mutations were applied to disk, each verified present in the
  file before the run, and every one turned that file red.
- status: FIXED

### B8-67 · Check & Refine judges a profile against a measurement it was not built from
- blocks release: no
- status: DEFERRED
- decided by: Basti, 2026-09-05 — *"fix is defered for now. can you store it
  somewhere?"* The work is complete, gated and pushed; it is held, not dropped.
- because: the fix is ready but the *interesting* half of the finding is not a
  fix at all — it is three design questions that are his to rule on, and landing
  the mechanical part first would make them look answered when they are not.
  Deferring keeps the whole thing on one desk instead of half-shipping it.
- found by: a user report relayed on 2026-09-05 — a profile that got worse every
  refinement round and then advised him to reprint and start again. Three of his
  four observations turned out to be the app telling the truth.
- detail: the quality check compares a profile against the readings it was BUILT
  FROM (`unified_measurement_management.md` §6c says exactly that). A guided
  re-read rewrites the measurement in place; **nothing rebuilds the profile**
  (`tab_profile.py:531` is the only caller of `_on_build`); `measure_finished`
  clears Check & Refine (`main_window.py:388`) and the session-restore path
  re-arms it with the NEW `.ti3` and the OLD `.icc`
  (`main_window.py:2869-2876`). So the second check answers "how far has my
  measurement moved since the profile was made", under the heading "Profile
  Quality Assessment", in silence.

  Measured on screen on beta 9, a real 924-patch chart, the same re-reads
  throughout and only the rebuild differing:

  | | avg ΔE | peak | strips flagged |
  |---|---|---|---|
  | before | 0.363139 | 2.946109 | 2 |
  | re-read, not rebuilt | 0.364849 | 2.314044 | 1 |
  | re-read, rebuilt | 0.363479 | **1.924213** | **none** |

  Data corruption was ruled out, not assumed: five rounds of byte-identical
  re-reads moved the numbers by not one digit.

  **The half that is not a fix, and is why this is deferred:**
  * the strip list is computed from profile FIT RESIDUAL, not measurement error
    — with zero noise it still flags 13 of 47 strips, patches holding no reading
    error a re-read can remove, so the flow can send a user to re-measure strips
    that are fine and can never reach "nothing left";
  * the reprint advice fires on `n_flagged/n_strips > 0.75` and one bad patch
    condemns a 20-patch strip: 105 bad patches of 924 (11.4 %) produced "39 of
    47 strips (83 %) need re-measuring";
  * whether a WORSE re-read may silently overwrite a better one is unruled.
  * `(!! ALL ROWS READ !!)` is chartread's own `-r` banner, true from the first
    instant of every refinement and printed at every strip prompt. Technically
    true, reads as the opposite of what the app is asking for.
- where the work is: branch **`deferred/check-and-refine-stale-profile`**,
  pushed. `workflow/profile_provenance.py` (colprof embeds the whole `.ti3` in
  the ICC's `targ` tag, so the profile carries its own source data and the
  question needs no timestamps), one log line in `tab_check_refine.py::_on_run`,
  and 8 tests. Release gate on that tree 11203 passed / exit 0 against beta 9's
  11195; scanner sweep 32 PASS / 0 FAIL on both. A window for this is drafted as
  M-CHECK-STALE-PROFILE and deliberately NOT written into §M-PROPOSED — the
  wording is Basti's ruling and a proposed message costs a translation in
  thirteen languages.
- evidence: test_a_check_knows_the_profile_it_judges.py

### B8-68 · The white-point help told the user that a scale of 1.00 changes nothing, and it changes everything
- blocks release: no
- status: FIXED
- found by: Knut, beta 9, by following the instruction and building a profile he
  did not intend; root-caused by AGENT BG (`beta 9/knut-whitepoint/REPORT.md`)
- what was wrong: `ui/dialogs/scanner_colprof.py` said, of the manual
  white-point scale, *"1.00 makes no change."* ArgyllCMS sets `autowpsc = 1`
  **before** it reads the number (`colprof.c:494`) and defaults the scale to 1.0
  anyway (`xfit.c:2753`), so `-u 1` builds byte-for-byte the same profile as a
  bare `-u`. Built both from a real IT8 scan: `wtpt 1.591736 1.624054 1.343185`,
  identical. The worked example under it was inverted too — it offered 0.90 as
  the way to keep a slightly darker white white, and `-u 0.9` measures a white
  point of Y **1.461655**, a scan about **44 % darker**. And the list itself had
  **two entries labelled "(-u)"**: "Auto-scale to avoid clipping (-u)" and
  "Manual white-point scale (-u)", one flag with a number after it.
- fix: the corrected tooltip says what a scale of 1.00 really is (the automatic
  scaling, unaltered — i.e. "Auto-scale to avoid clipping"), names the option
  that really does leave white alone, and gives the measured 0.90 figure as a
  warning rather than a recipe. The second entry is now "(-u scale)".
- **shipped as its own commit, ahead of the wider rewrite**, because a knowingly
  false sentence should not wait behind a wording discussion.
- evidence: 8 tests in `the_white_point_help_states_a_true_fact.py` —
  `test_the_help_no_longer_says_a_scale_of_one_changes_nothing`,
  `test_the_help_says_what_a_scale_of_one_really_is`,
  `test_the_inverted_worked_example_is_gone`,
  `test_no_two_white_point_options_are_labelled_with_the_same_flag` and
  `test_the_manual_scale_option_says_it_takes_a_number`. Four mutations, each
  proved present on disk before the run: restoring the false sentence, the
  duplicate label, the false bullet, or dropping the i18n anchors each turns it
  red.

### B8-69 · Nothing anywhere said a scanner profile used as a measuring instrument has to be BUILT as one
- blocks release: no
- status: FIXED
- found by: Knut, beta 9 — *"the scanner profile help … does not mention that
  the profile to be selected must have been created using the -ua attribute
  before using it for profiling a printer. This also goes for the help cards"*,
  and then: *"I totally forgot all this, and had to relearn all of it now, so
  this is really an important detail that the workflow steps in help cards and
  help descriptions must be clear about"*
- why it matters: he wrote his own reference `colprof` command with `-ua` in it
  and annotated why. He still forgot. Nobody else has a chance.
- **measured before a word of it was written**, because `scanin` reads the
  scanner ICC with `icAbsoluteColorimetric`, hard-coded (`scanin.c:1029`), so
  "does `-ua` matter for ChromIQ's own path?" is an empirical question. Six
  profiles from Knut's 864-patch scan, each looked up the way scanin looks them
  up (`xicclu -ff -ia -px`), in `beta 9/printer-from-scan/measure/`:
  * **cLUT — Lab table, default white point: the table FLATTENS.** Device 0.76 /
    0.80 / 0.85 / 0.90 / 1.00 all read Y 0.833 — one colour. With `-ua`:
    0.915 / 0.973 / 1.009 / 1.009 / 1.009. Everything on a printed sheet
    brighter than the target's own white board is measured as the same colour.
  * **cLUT — XYZ table: no flattening** (0.917 → 1.624); `-ua` moves what
    ChromIQ measures by about 0.5 ΔE00 over a test grid.
  * accuracy: `-ax -qm` 0.484 ΔE00 vs `-as -qm` 0.913; `-ax -qh` 0.337. **Quality
    High is the biggest single lever**, and ChromIQ's scanner defaults are
    shaper+matrix at Medium — neither right for this job.
- fix: the three settings (type, quality, white point) are now named in the
  printer-mode ⓘ, in the ⓘ beside the scanner-profile field, in **both** help
  cards, and — unasked — in the log the moment the tick goes on. `_TIP_WP` and
  `_TIP_R` are rewritten on the same measurements, including that "Restrict
  white, black and primaries" cannot restrict primaries on a cLUT and does
  nothing at all beside `-ua` (identical transforms, measured).
- **all of this wording is PROPOSED, not approved.** Basti rules on it.
- one thing it is NOT: a label in the panel. The left column measurably has no
  room — on a 1079-px screen the window is capped at 934 and `_chromiq_box` gets
  696 px against a 709-px sizeHint, so a wrapping hint under the scanner-profile
  field was drawn through the field above and the label below (three overlapping
  widget pairs, against none without it). Worth a separate look; not a regression.
- evidence: `the_scanner_profile_must_be_built_for_measuring.py` —
  `test_the_three_settings_are_named_the_way_the_window_spells_them`,
  `test_the_printer_mode_help_names_all_three_settings`,
  `test_the_printer_mode_help_warns_about_the_lab_table`,
  `test_the_printer_mode_help_quotes_argylls_own_instruction`,
  `test_the_scanner_profile_help_repeats_the_requirement`,
  `test_ticking_the_box_says_the_requirement_without_being_asked`,
  `test_the_printer_from_scan_card_names_all_three_settings`,
  `test_the_scanner_profile_card_points_at_the_measuring_settings`.
  Twelve mutations, each proved on disk, each red.

### B8-70 · "Profile my printer from this scan" is gated on the chart's origin — the gate is right, its silence was not
- blocks release: no
- status: FIXED
- found by: Knut, beta 9 — *"the option 'Profile my printer from this scan' is
  only available when 'A chart I made in ChromIQ' is selected. This should be
  possible to do whatever target a user has"*
- **verdict: the gate is technically justified and stays.** Printer mode is
  `scanin -c <scan> <cht> <scanner.icc> <pbase>` and reads `<pbase>.ti2` — the
  table of device values that were sent to the printer. A bought standard target
  has no such table: it was printed and measured by its manufacturer, and its
  reference file (.cie/.txt/.ti3/.cxf) says what the target *is*, never what any
  printer was asked to make. The standard-target branch has no device-value input
  at all, by construction.
- what WAS wrong: switching to a standard target made the tick vanish with no
  word, in a window whose own subtitle — still on screen in that mode — promises
  *"…or, from a scan of a chart you printed, a profile for your printer"*.
  Verified on screen: 31 visible labels in standard mode, not one explaining it.
- and the thing Knut actually needs **already exists and is undiscoverable**: the
  radio says "A chart I made in ChromIQ", but #105's bring-your-own-`.cht` path
  accepts a chart made in **any** program, given its `.ti2` and printtarg's
  `.cht` pages. Standard mode now says both — why the option is not there, and
  that the other side is not ChromIQ-only.
- the redesign Knut proposed on top of this is B8-71.
- evidence: `the_printer_option_says_why_it_is_gone.py` —
  `test_the_gate_itself_is_unchanged`,
  `test_standard_mode_now_says_why_the_printer_option_is_not_there`,
  `test_the_explanation_and_the_tick_are_never_both_shown_or_both_hidden`,
  `test_the_source_help_says_a_chart_from_another_program_belongs_there`

### B8-71 · "Usage Scenario:" — let the user say what the profile is for and let the window set it up
- blocks release: no
- status: FIXED
- **BUILT on 2026-09-06 under B8-78**, which supersedes this entry. Everything
  below is why it waited and what it had to answer first; B8-78 is what was
  built, what changed on the way, and what is still somebody else's call.
- guarded by: `tests/test_the_window_says_what_the_profile_is_for.py` — see
  B8-78 for the full list.
- evidence: the two that answer THIS entry's own hard rule, that an existing
  target must not have settings applied to it on first open:
  test_a_bucket_with_stored_settings_is_never_set_up_on_first_open and
  test_the_stored_set_is_read_from_the_store_and_not_from_the_visits.
- proposed by: Knut, beta 9 — *"I think we could make the 'Profile my printer
  from this scan' option a part of several user cases, maybe called 'Usage
  Scenario:' as a heading … (this option pre-selects the -ua attribute … and
  user does not need to specifically remember to select it)"*
- why it is the stronger answer to B8-69: that fix makes the `-ua` requirement
  visible. This makes it unnecessary to remember. Knut, who wrote his own
  annotated `colprof` commands, forgot it anyway — a design that removes the
  need to remember beats a sentence explaining it.
- **designed, not built**: `beta 9/printer-from-scan/USAGE-SCENARIO-DESIGN.md`,
  with five mockups driven from the real window. It answers: the taxonomy holds
  with one correction (scenarios 2 and 3 are step one and step two of one job
  and must read that way, or a user picks 3 first and is stuck); scenario 1
  pre-selects **today's defaults unchanged** — deliberately, since moving
  everyday scanning to a cLUT is a separate decision with a migration behind it;
  scenario 2 pre-selects cLUT — XYZ / Quality High / `-ua`, all three measured,
  and NOT "Restrict white, black and primaries", which is a measured no-op
  beside `-ua`; scenario 3 changes no setting at all. Pre-select, never lock,
  and name the divergence when the user overrides it. The B8-70 gate becomes a
  greyed option with its reason beside it instead of a vanishing control.
- decided by: AGENT BJ referred it to Basti, 2026-09-05
- because: it is a new control carrying new user-facing wording, which is
  Basti's ruling and not an agent's; it costs about 15 i18n keys across thirteen
  catalogues and a rewrite of both help cards; it needs a stored-setting
  migration whose one hard rule is that an existing target must NOT have a
  scenario applied on first open, or its next profile silently changes; and it
  had a layout prerequisite, because the left pane of this window did not
  scroll when it ran out of room, it overlapped (measured under B8-69).
  Building it before any of that is settled would ship a control that moves
  people's settings without asking.
- **the layout prerequisite is closed**: B8-73. The pane's rows can no longer
  be stacked at any height, and the correction worth carrying over is that it
  was never the settings COLUMN — that scrolls correctly in all thirteen
  languages — but the pane the column sits in. What remains here is wording,
  i18n and the stored-setting migration, all of which are Basti's.

### B8-72 · The scanner/camera window opens below the usable area on Windows, hiding three controls
- blocks release: no
- status: FIXED
- found by: the Windows ARM64 VM, `Desktop/HANDOVER-to-macos-3.md` item W-07 —
  *"the scanner window opens 67 logical px below the usable area, hiding three
  controls completely: add scan for averaging, save diagnostic image, and use
  .cht registration marks. It is the POSITION, not the size — moved to y=0,
  everything fits."*
- detail: the report's hypothesis was right in substance and wrong in one
  detail. The placement maths does not ignore the work area — Qt's own
  `QDialog::adjustPosition` clamps against `availableGeometry` — but it runs
  from `QDialog::showEvent`, **with the size the window has at that moment**,
  and `_ToolDialogBase.showEvent` resizes the window a few lines later, once
  its rows are real and its wrapped labels have claimed their height. The
  clamp is stale before it matters. Traced on the live window (German, macOS
  with the Dock shown, work area 994 px tall):

      base.showEvent on entry     y = -28, h = 744
      base.showEvent on exit      y = 137, h = 860
      just after show()           y = 110, h = 894
      settled                     y = 110, h = 922

  — 178 px of growth after the position was chosen.
- **it reproduces on macOS, and macOS hides it.** Cocoa's
  `constrainFrameRect:toScreen:` shoves the window up again on every growth
  step, which is why the frame lands with its bottom EXACTLY on the work
  area's edge in all thirteen languages and nothing is visible. Windows has no
  such rescue. The state the Windows report describes is reproducible here
  under `QT_QPA_PLATFORM=offscreen`, which also has no window manager: before
  the fix the frame was `[0, 88, 1244, 724]` on an 800 px screen, **12 px
  below the work area**; after it, `[0, 76, ...]`, bottom exactly on the edge.
- one thing the Dock DID show on macOS: with the Dock visible the work area
  drops from 1079 to 994 px, the window's 90 % cap takes it from 964 to 922,
  and the same three controls — *＋ Add another scan to average*, *Save a
  diagnostic image of what was read*, *Use fiducial marks in the .cht as
  reference* — go below the fold of the RIGHT pane. There they are reachable
  by scrolling, which is the difference between the two platforms in one
  sentence.
- **AND THE POSITION IS ONLY HALF OF IT** — corrected by the Windows VM's
  round-4 handover (B8-39), and confirmed here rather than taken on trust. The
  earlier *"moved to y=0, everything fits"* is wrong: at the top of the work
  area the right pane's own content still runs past the bottom. Measured on
  macOS with the Dock shown (work area 994 px), how far the right pane's
  content falls below its viewport as the window opens, and how many of the
  three controls are past the work area:

  | | before | after |
  |---|---|---|
  | English | 49 px, 2 controls | **7 px, 0 controls** |
  | German | 95 px, 3 | **37 px, 1** |
  | Russian | 95 px, 3 | **53 px, 2** |
  | Spanish | 136 px, 3 | **78 px, 3** |

  Two of the VM's corrections check out here to the letter: **Russian** needs
  the widest window (1178 px against German's 1104) and **Spanish** is the
  worst vertical case, not German.
- the second cause is `cap_h`. `_ToolDialogBase` opened at
  `min(hint, 0.9 * available.height())`, and the missing tenth is not spare —
  it is the bottom of the right pane. On the VM's 1032 px work area that is
  **41 px (DE) / 25 px (EN) less than the window's own sizeHint with 75 px of
  screen unused**; here, with the Dock shown, it opened at 894 px against a
  952 px hint, i.e. 58 px. `MAX_FLOOR_H` in `scanin_dialog.py` already reasons
  the honest way — screen, minus taskbar, minus caption — and `_work_area_cap`
  is now that same arithmetic with the caption READ off the window.
- fix, both halves, in `_ToolDialogBase` so every tool dialog gets them:
  * `_keep_inside_the_work_area`, run after every `self.resize(...)` the class
    performs (`showEvent` and `_refit_height`). It clamps the FRAME — caption
    and border included — against `availableGeometry`, never against
    `geometry()`, and never pushes a window that is too tall off the TOP to
    make its bottom fit. It also brings a frame TALLER than the work area down
    to it, which is what lets the cap below be optimistic before the window is
    mapped and the caption's height is known.
  * `_work_area_cap`, replacing the nine-tenths rule.
- **what it does NOT close, stated plainly.** Spanish still has 78 px of right
  pane below the fold as the window opens, because the window's `sizeHint` does
  not include the right pane's content at all — `_scroll_right` is a
  QScrollArea and reports a generic hint (the same reason its minimum is 44 px,
  which `_fit_floor_to_the_smallest_screen` already documents). What HAS changed
  is that scrolling now works: **after scrolling the right pane to the bottom,
  none of the three controls is past the work area in any of the four languages
  measured**, where the VM found that on Windows scrolling to maximum still
  left both checkboxes inside the reserved taskbar strip. Making the window ask
  for its right pane's real height — `ContentHeightScrollArea` in
  `settings_dialog.py` is the existing mechanism — changes the opening size of
  this window in every language, which is a design decision and not a defect
  fix. Left for Basti, with the numbers above.
- evidence: `tests/`, file `a_tool_window_opens_inside_the_work_area.py` —
  test_the_window_opens_with_its_bottom_inside_the_work_area,
  test_the_clamp_brings_a_window_back_from_under_the_taskbar,
  test_the_clamp_never_pushes_the_title_bar_off_the_top,
  test_a_window_that_already_fits_is_left_where_the_user_put_it,
  test_every_resize_the_base_class_performs_is_followed_by_the_clamp,
  test_the_opening_height_is_capped_by_the_work_area_not_nine_tenths_of_it,
  test_a_frame_taller_than_the_work_area_is_brought_down_to_it,
  test_no_tool_dialog_still_sizes_itself_to_a_fraction_of_the_screen
- mutation, proved to land, four of them: removing the two clamp call sites
  turns test_the_window_opens_with_its_bottom_inside_the_work_area and
  test_every_resize_the_base_class_performs_is_followed_by_the_clamp red;
  emptying the clamp turns the first and
  test_the_clamp_brings_a_window_back_from_under_the_taskbar red; putting the
  nine-tenths rule back turns
  test_the_opening_height_is_capped_by_the_work_area_not_nine_tenths_of_it and
  test_no_tool_dialog_still_sizes_itself_to_a_fraction_of_the_screen red;
  removing the shrink step turns
  test_a_frame_taller_than_the_work_area_is_brought_down_to_it red.

### B8-73 · The left pane of the scanner/camera window stacks its rows instead of scrolling
- blocks release: no
- status: FIXED
- found by: B8-69's own note, and named as the layout prerequisite of B8-71
  ("Usage Scenario:") — *"the left pane of this window does not scroll when it
  runs out of room, it overlaps"*
- detail: **it is the PANE, not the column, and that correction matters** —
  the pane is where a new control has to go. The settings scroll area itself
  was measured clean: thirteen languages × three source modes × Advanced open
  and closed × five window heights, with a wrapped hint added under the
  scanner-profile field and again inside a row layout, and in every one of
  those the column was handed its full `heightForWidth`, no wrapped label was
  short of its own `heightForWidth`, and no two controls shared pixels.
  What stacks is the pane one level up. It holds four rows — the settings
  scroll area, the spectrum busy bar, the four big buttons, the log — and
  three of them cannot give: `fit_log_height` pins the log at min == max, the
  buttons are two rows of real buttons, the bar is a fixed strip. The fourth,
  the only one that scrolls, held a hard `minimumHeight` of 120–136 px and
  refused. A QVBoxLayout that is over-subscribed does not clip and does not
  scroll: it lays its rows on top of one another. Measured on the live window
  (German, the window forced under its own floor):

      pane 367 px (its minimum is 447)   the spectrum bar 12 px into the
                                         settings area
      pane 287 px                        40 px
      pane 207 px                        the bar 46 px in, and the button grid
                                         a further 13 px on top of that

  The pane is handed less than its minimum only when the WINDOW is, which is
  finding C of the Windows verification — a floor of 675 logical pixels on a
  laptop that has 672 — and it is what a new row in this column does the
  moment `MIN_LEFT_SCROLL_H` is already the binding constraint.
- fix: `ScannerProfileDialog._let_the_settings_pane_give`, called from a new
  `resizeEvent` and from `_fit_floor_to_the_smallest_screen`. The settings
  area keeps the comfortable height that function decides
  (`_settings_pane_floor`) whenever the pane has room for it, and gives up
  whatever it must below that. A version that also re-pinned the window's
  minimum was built and thrown away: it read the floor through a QSplitter
  that had not been settled and pinned 720 px where the floor is 640, so the
  window bounced UP by 80 px on a drag that should have been refused at 640.
  The ratchet it was guarding against cannot start from a drag, because a drag
  stops at the window's minimum, at which the pane is exactly at its own.
- **it costs the ordinary window nothing**, and that is measured rather than
  assumed: in all thirteen languages the minimum width (1048–1178), the
  minimum height (640) and the opening size (1240×922) are identical before
  and after, and the 34-check scanner sweep has the same result on both trees.
- evidence: `tests/`, file `the_scanner_left_pane_scrolls_instead_of_overlapping.py` —
  test_the_left_panes_rows_never_sit_on_top_of_each_other,
  test_the_settings_area_gives_only_what_the_pane_cannot_hold,
  test_a_second_pass_moves_nothing,
  test_the_window_floor_is_unchanged_by_any_of_this
- mutation, proved to land: making the area never give
  (`give = want`) turns the first two red; removing the `resizeEvent` hook
  turns three of the four red.

### B8-74 · An empty averaging slot elides to "Scan 2 (no…" instead of saying it is empty
- blocks release: no
- status: OPEN
- found by: the Windows ARM64 VM, `HANDOVER-to-macos-4.md` §3 — flagged as a
  conflict for judgement rather than a fault, and it is one.
- detail: `ElidingComboBox` shortens the averaging slot's label to
  `Scan 2 (no…` in German, by design, with the full text on a tooltip. B8-32's
  whole point is that a slot with no file in it must SAY it is empty — a
  tooltip is not saying it, because nothing tells the user to hover. The two
  behaviours are individually right and together wrong.
- **not resolved here on purpose.** It is a wording-and-behaviour decision
  about a control the owner has already ruled on once (B8-32), and the
  alternatives — a shorter phrase, a different order so the word that matters
  survives the elision, a separate marker beside the combo — are choices, not
  fixes. Basti's.
- decided by: AGENT BM referred it to Basti, 2026-09-05
- because: resolving a conflict between two of his own rulings by picking one
  is exactly the thing CLAUDE.md's binding-specification rule forbids.

### B8-75 · The scanner white-point default clipped every original brighter than the test chart's own white board
- blocks release: no
- status: FIXED
- reported by: measured under B8-69 / the `knut-whitepoint` investigation, and
  ruled on by Basti, 2026-09-05
- what was wrong: Tools ▸ Build profile with scanner or camera built every
  scanner and camera profile with "Map chart white to white", which puts the
  test chart's own white board at PCS white. A photographic IT8's board is
  **84.286 % reflectance** (colprof's own log on the scan behind this:
  `Approximate White point XYZ = 0.82462 0.84286 0.70454`), and most photo and
  office paper is brighter than that. Everything brighter therefore exceeded
  PCS white and was flattened, irreversibly, at the first conversion into any
  RGB working space. Re-measured on 2026-09-05 at `colprof -ax -qh`,
  media-relative: 84.1 % reflectance arrives at L\* 101.12, 89.3 % at 103.47,
  95.2 % at 106.08 and a perfect diffuse reflector at 108.06, and all four come
  out of an sRGB conversion as exactly **255 255 255**. Four physically
  different whites, one number, with nothing to recover afterwards.
- what it is now: the default is **"Scale white to a perfect white surface
  (-u -R)"**, a new single entry in the same dropdown that carries both flags.
  The same four originals land at L\* 93.50 / 95.69 / 98.12 / 99.98 and nothing
  physically possible clips. It costs no accuracy — `profcheck -k -Ia` gives
  avg ΔE00 **0.336709** against the old default's **0.336727** — and it keeps
  whites neutral: the board reads a\* −0.83 / b\* −0.50 against the old
  default's −0.89 / −0.53. `-ua` is fractionally more accurate again (0.332197)
  and was NOT chosen, because it reports the chart's real cast (a\* +1.49 on
  the board, +2.50 on a perfect diffuser) — right for an instrument, wrong as a
  global default for pictures.
- what was measured and where: `beta 9/wp-default/measure/` holds the five
  `-ax -qh` rebuilds, their logs and the lookups; the case they confirm is
  `beta 9/knut-whitepoint/REPORT.md`. Two facts worth keeping: `-u 1 -R` (what
  Knut built and what the report measured) is `-u -R`, proved by rebuilding
  both and comparing tags — identical A2B0, B2A0, wtpt and bkpt, only `desc`
  differing because that is the file name; and a Lab cLUT's ceiling moves with
  this setting, from about **94 %** reflectance under the old default to about
  **114 %** under the new one, which is why the profile-type help had to change
  with it.
- the migration, RULED BY BASTI: existing remembered settings adopt the new
  default. His words: *"our user base is not very big at the moment so i want
  the better default"*. So a stored `""` moves, and there is deliberately no
  per-target escape hatch pinning old settings to the old value. A schema stamp
  in the stored configuration separates a `""` that was written because it was
  the default from one chosen deliberately afterwards, so the migration fires
  once and never again.
- and it is announced, not silent: **M-SCAN-WP-DEFAULT**, said once in the
  window's log the first time it opens after the migration has actually moved
  something. It says what changed, that every existing profile, measurement and
  project is untouched, and that the old behaviour is still one entry in the
  same dropdown. **The WORDING is §M-PROPOSED and unapproved** — it is Basti's
  to approve, which is why it speaks through the log rather than a window.
- what did NOT change: the printer-mode default, which is a separate question;
  `ProfileParams.wp_mode`, which stays `""` because every other caller builds
  an output profile; and both consumers of a scanner profile inside ChromIQ —
  `scanin -c` reads one with `icAbsoluteColorimetric` hard-coded in Argyll and
  is indifferent to this setting, and `workflow/cctiff_apply.py` still converts
  with `-i r`, which is the intent this default is chosen for.
- guarded by: `tests/test_the_white_point_default_cannot_clip_a_real_original.py`
- evidence: test_the_default_is_the_one_that_cannot_clip,
  test_a_fresh_scanner_build_asks_colprof_for_u_and_R,
  test_the_R_switch_and_the_default_do_not_stack_into_two_flags,
  test_the_old_behaviour_is_still_one_entry_in_the_same_dropdown,
  test_a_printer_build_is_untouched_by_any_of_this,
  test_the_dataclass_default_did_not_move_with_it,
  test_the_window_marks_the_default_entry_and_only_that_one,
  test_restore_defaults_goes_to_the_new_default_and_leaves_R_alone,
  test_a_missing_key_takes_the_default_and_a_stored_one_does_not,
  test_what_the_window_writes_carries_the_schema_stamp,
  test_a_setting_saved_before_the_change_adopts_the_new_default,
  test_the_migration_happens_once_and_not_on_every_open,
  test_a_choice_made_after_the_change_is_never_re_defaulted,
  test_a_setting_somebody_actually_chose_is_left_where_it_is,
  test_a_printer_bucket_never_gains_an_input_profile_setting,
  test_a_bucket_nobody_ever_saved_is_not_reported_as_migrated,
  test_rubbish_in_the_store_does_not_take_the_window_down,
  test_the_change_has_a_message_and_it_is_not_approved_yet,
  test_the_window_says_it_once_and_only_when_something_moved,
  test_showing_the_window_is_what_says_it,
  test_the_two_consumers_of_a_scanner_profile_still_read_it_as_they_did,
  test_the_help_calls_the_new_default_the_default_and_the_old_one_not,
  test_the_help_says_the_R_switch_is_already_in_the_default,
  test_the_help_still_says_what_the_default_costs. Nineteen mutations of the
  shipped code were each proved to land on disk before the run; every one is
  caught, and the one that survived the first pass (deleting the single line in
  `showEvent` that announces the migration) is why
  test_showing_the_window_is_what_says_it drives the real window instead of
  calling the method.
- note for B8-71: the "Usage Scenario" design says scenario 1 pre-selects
  "today's defaults unchanged". That is still exactly what it should do — but
  "today's default" is now this entry, so the table in
  `beta 9/printer-from-scan/USAGE-SCENARIO-DESIGN.md` names the wrong one and
  should be read with this item beside it. Scenario 2 is unaffected: it presets
  `-ua`, which is untouched and still its own entry.

---

### B8-76 · A profile Adobe's licence forbade us to bundle shipped in every release since v2.3.0
- blocks release: yes
- status: FIXED
- found by: Agent BZ, on a standing question about `assets/USWebCoatedSWOP.icc`
- detail: 557,168 bytes, ICC `desc` *"U.S. Web Coated (SWOP) v2"*, ICC `cprt`
  *"Copyright 2000 Adobe Systems, Inc."*, md5 `79d7e984ea3ac74eed7cc92bf6b22a0d`.
  Added in one line of an eight-file commit — `a4c7c53f`, *"assets: bundle
  USWebCoatedSWOP.icc so ICC conversion works on all Macs"* — by an earlier
  session of this assistant, with no licence file, no attribution, and nothing
  anywhere recording that anyone had asked whether we were permitted to copy it.
  It then shipped in every release for four months. **This is our error, not the
  owner's.**

  Adobe's terms are ESTABLISHED, from Adobe, and quoted in full in
  `THIRD-PARTY-NOTICES.md`. There are two agreements over byte-identical files.
  The end-user one (`adobe.com/support/downloads/iccprofiles/icc_eula_win_end.html`,
  live, and unchanged in Wayback captures from 2008 and 2012) says at §2:
  *"No other distribution of the Software is allowed; including, without
  limitation, distribution of the Software when incorporated into or bundled
  with any application software."* The bundling agreement
  (`…/icc_eula_win_dist.html`) permits *"(d) as bundled with your own application
  software"* and names "U.S. Web Coated (SWOP) v2" in Exhibit A. Nothing in this
  repo or its history records the file being taken under the second one. **We
  were not compliant.**

  Two facts correct the way this was originally framed. First, the search order:
  `_get_cmyk_transform` built `candidates = [resource_path("assets/USWebCoatedSWOP.icc")] + _extra`
  — the **bundled** copy was tried FIRST on every platform, so it was not a rare
  last resort, it was what every user's CMYK preview went through. Second,
  nothing breaks without a profile: the preview falls back to a naive
  subtractive composite, measured at a mean 16.9 ΔE76 (p95 47.0) from a profiled
  conversion, painting 100 % cyan as `#00FFFF`.
- fix: replaced with `assets/profiles/cmyk.icm` — ArgyllCMS 3.5.0's `ref/cmyk.icm`,
  copied byte for byte (md5 `6de8c139e9c1a54afd513d03efb7501f`), whose own `cprt`
  tag reads *"Created by Graeme W. Gill. Released into the public domain. No
  Warranty, Use at your own risk."* Public domain removes the question instead of
  answering it, and it is already the house pattern: the four profiles already in
  `assets/profiles/` are byte-identical Argyll ref copies carrying the same
  dedication. The Adobe bundling agreement was considered and rejected — its §3
  requires *"first obtaining the agreement of the end user"* and its §7 makes the
  grant terminable, neither of which survives GPLv3's irrevocable grant to every
  downstream redistributor. Cost, measured over a 6⁴ CMYK grid: mean **5.2 ΔE76**
  (p95 11.0) against the Adobe profile, in a path the app already badges
  *"Approximate colours — the ink values in the file are exact"*.

  The same sweep added `assets/fonts/OFL.txt` — six OFL 1.1 fonts shipped with no
  copy of the licence anywhere in the tree, which OFL §2 requires — reproduced
  plotly.js's MIT permission notice, and wrote `THIRD-PARTY-NOTICES.md` stating
  the terms of every bundled third-party asset.
- evidence: test_the_adobe_profile_is_gone_and_nothing_points_at_a_bundled_copy,
  test_no_profile_we_ship_carries_a_bare_third_party_copyright,
  test_the_cmyk_preview_still_has_a_profile_to_use,
  test_the_notices_file_exists_and_states_the_rule,
  test_every_bundled_profile_and_font_is_named_in_the_notices,
  test_the_notices_file_names_nothing_that_has_been_deleted,
  test_every_licence_file_the_notices_promise_is_actually_present,
  test_the_ofl_fonts_ship_with_the_ofl,
  test_the_vendored_javascript_carries_its_permission_notice.
  Twelve mutations were each proved to land before the run: re-adding the Adobe
  file, restoring the old `resource_path` line, deleting `cmyk.icm`, pointing the
  preview at an RGB profile, deleting `OFL.txt`, truncating it, dropping one
  font's copyright line from it, dropping `cmyk.icm` from the notices, removing
  the MIT permission notice, naming a nonexistent file, and deleting the rule
  sentence — each turns the matching test red; the twelfth (a nonexistent file on
  a line that says it is absent) correctly stays green. On screen:
  `scripts/drive_bz_cmyk_preview_profile.py` drives the real `MainWindow` and its
  own preview on a real Argyll CMYK chart, run once on this tree and once on a
  38ed485d worktree that still has the Adobe file — 10.1 % of preview pixels move
  by more than 1 ΔE (mean 6.17 among those), and the two pictures are
  indistinguishable by eye.
- note: two things this sweep found are NOT fixed here because they are not this
  assistant's to decide, and both are written up in `THIRD-PARTY-NOTICES.md`
  under "Still open": `data/scanner_targets/` states GPLv3 for files its own
  README calls derived from **AGPLv3** ArgyllCMS (and, three lines later, "mere
  aggregation" — they cannot be both); and
  `assets/plotly-gl3d.min.js.LICENSE.txt`, which the bundle's own header points
  at, has never been in this repo.

---

### B8-77 · The bundled scanner targets are ArgyllCMS's geometry, and the sweep that asked could not tell
- blocks release: no
- status: FIXED
- found by: B8-76's licensing sweep left it under `THIRD-PARTY-NOTICES.md` →
  "Still open" as the owner's call; re-opened and measured by Agent CB,
  2026-09-06
- detail: `data/scanner_targets/` ships **eight** `.cht` files under a **GPLv3**
  `LICENSE`, and ArgyllCMS's `ref/` — which its own `ref/ReadMe.txt` names all
  eight of them in — is **AGPLv3**. B8-76 offered two honest ways out: establish
  that the geometry was *regenerated*, making the files original work whose
  licence is the author's to choose, or mark the folder AGPLv3. It could not
  choose, because the only measurement it had was that "every one of the eight
  differs byte-wise from Argyll's copy, which settles nothing either way".

  **That instrument was wrong, and the first resolution is now refuted.** Argyll
  writes a whole grid on one line (`Y 01 29 A V 24.689655 24.545454 99.5 25.5
  24.689655 24.545454`) where these files write one line per patch, so the two
  never match byte-wise even when they describe the identical grid; a "percent
  similar" taken from such a diff — an earlier agent reported 0.2–2.9 % — is not
  a measurement of anything. Expanding **both** sides to per-patch boxes first,
  through a Python transcription of ArgyllCMS 3.5.0's own reader
  (`scanin/scanrd.c`, `read_elist()` and `strinc()`), and comparing patch by
  patch: `BOX_SHRINK` is Argyll's in **8 of 8** (12, 3, 12, 1.6, 4, 3, 8, 3.5),
  the declared patch size is Argyll's in **8 of 8** (including 24.6897 ×
  24.5455 and 12.675 × 12.75), and `ISO12641_2_1` (864 patches), `it8Wolf` (288)
  and `Hutchcolor` (528) sit at Argyll's **absolute** coordinates with a maximum
  deviation of 0, 0 and 0.00053. The remaining four are that grid translated or
  uniformly rescaled. The repo's own history agrees: `1f9c534a` bundles
  rectarg's corrected copies "plus ISO 12641-2 **unchanged**".

  Two guards against over-reading: an exact affine fit on a *uniform* grid is
  trivial and proves nothing on its own (four of these are uniform), and it is
  **NOT ESTABLISHED** whether rectarg took the geometry from Argyll or both took
  it from a common third source — which does not change what ships here.

  A second, smaller fault fell out of it: `it8Wolf.cht` had shipped in this
  folder since its first commit and was named nowhere in its README, so B8-76
  described a seven-file folder and audited seven of eight.
- fix: the folder is now **AGPLv3**. Measured first, decided after: the
  measurement is
  written into `data/scanner_targets/README.md` under "Provenance — measured,
  not assumed" — method, per-file table, and an explicit note on which numbers
  are evidence and which are not — and `THIRD-PARTY-NOTICES.md` records that
  resolution (a) is closed and what the remaining options cost: **(b)** mark the
  folder AGPLv3 (a `LICENSE` swap plus two documents; the files are data, so it
  does not touch ChromIQ's own licence), **(c)** drop the bundled copies and read
  the user's `ref/` at run time (`workflow/standard_targets` already falls back,
  but this loses the corrected fiducials and the `XLIST`/`YLIST` normalisation
  that took auto-align from 8 of 25 targets to 25 of 25 — a real functional
  loss), or **(d)** ask Graeme W. Gill for permission to ship these eight under
  GPLv3.

  **Basti chose (b) on 2026-09-06**, after asking — and being shown — that it
  changes nothing about how the app works. `data/scanner_targets/LICENSE` now
  carries the same AGPLv3 text ArgyllCMS ships as `ref/License.txt`; the folder
  README's "Credit & licence" section states the AGPL and why; and
  `THIRD-PARTY-NOTICES.md` records the decision under the folder's own heading
  and no longer lists it under **Still open**. The README's "mere aggregation"
  sentence is gone for good — the folder does not need an aggregation argument,
  because it now simply adopts its upstream's licence instead of asserting a
  different one. **No `.cht` was touched**, no code reads the `LICENSE`, and
  ChromIQ's own licence remains GPLv3. `it8Wolf.cht` is now listed in the README
  and a test keeps it that way.
- what is owed: nothing. The one visible run-time effect is that
  `ensure_user_targets_dir` refreshes an unmodified copy of the `LICENSE` in the
  user's `scanner-test-targets` folder on next open — its `.provisioned.json`
  hash changed — which is the "updated files must reach users" behaviour Knut
  asked for in beta.5. A copy the user has edited is never overwritten.
- evidence: test_every_bundled_cht_is_named_in_the_folder_readme,
  test_the_readme_states_the_measured_provenance_for_every_file,
  test_the_folder_carries_the_licence_of_the_geometry_it_ships,
  test_the_geometry_still_matches_argylls_the_way_the_readme_says.
  Nine mutations were each proved to land before the run: adding a ninth
  undocumented `.cht`, renaming `it8Wolf.cht` out of the README, deleting the
  Provenance header, removing one file's row from the table, softening the
  conclusion sentence, cutting the whole open item out of the notices, stripping
  the word AGPL from it, and changing a bundled `BOX_SHRINK` and a declared
  patch size. Two of those first did NOT land and were strengthened rather than
  believed.

  The licence test changed shape when the decision landed. It was written to
  SKIP once the folder became AGPLv3 — a reminder that retires. That would have
  left the folder unwatched again, which is how it carried the wrong licence
  from its first commit, so it was rewritten to hold the decision instead: the
  `LICENSE`, the folder README and the notices must agree, and reverting any one
  of them alone now fails. Five mutations were run against the new form:
  swapping the `LICENSE` back to the GPL, dropping "Affero" from the README's
  licence section, cutting the licence statement out of the notices, removing
  the sentence that says ChromIQ itself stays GPLv3, and re-listing the folder
  under **Still open**. Four failed the test immediately. **The fifth did not
  land** — cutting the licence statement left the word "AGPLv3" elsewhere in the
  same section, and a bare `"AGPLv3" in section` check passed over the hole. The
  assertion was tightened to require the section to *state* the licence
  (`**Licence: AGPLv3 …**`) rather than merely mention it, and the mutation then
  failed as it should. A passing mutation run is worth nothing if the mutation
  never applied.

---

### B8-78 · "Usage scenario", the patch-count setup, and three help texts that said things that were not true
- blocks release: no
- status: FIXED
- supersedes: B8-71, which is now BUILT. Read that entry for why it was
  deferred; read this one for what was built and what changed on the way.
- asked for by: Knut, beta 10, five items in one message on Tools ▸ Build
  profile with scanner or camera; **authorised for 4.2.0 by Basti**, who had
  been referred the wording and the migration when B8-71 was deferred.
- **the danger in it, and it is the reason B8-71 was deferred**: three of the
  five items set the SAME three controls (profile type, quality, white point
  handling). Built as three mechanisms they would overwrite each other, and any
  one of them could move a setting on a target somebody had already configured
  — which changes what their next profile looks like, in silence. So there is
  one table and one predicate, and both are named below.

**1 · One rule, not three.** `scanner_colprof.SETUP_SMALL` / `SETUP_LARGE` is
Knut's own rule (under a hundred patches: shaper+matrix, Medium, "Map chart
white to white"; at a hundred or more: the XYZ cLUT, High, "Scale white to a
perfect white surface"). Everything else reads it:
  * the usage scenario's **everyday** case IS that rule — `scenario_setup` for
    it returns `setup_for_patch_count`, so the two can never disagree;
  * the two white-point dropdown markers are DERIVED from it
    (`WP_MODE_RECOMMENDED`), so item 4 and item 5 are one fact written once;
  * the **measuring** scenario is the separate, measured triple (XYZ cLUT,
    High, `-ua`), and deliberately NOT `-R`, which is a measured no-op beside
    `-ua` on a cLUT (B8-69);
  * the **printer** scenario sets no colprof value at all.

  It agrees with what was measured here, and not by luck: B8-19 put the type
  crossover at about a hundred fit patches, B8-69 measured Quality High as the
  biggest single lever a cLUT has (0.484 → 0.337 ΔE00), and B8-75 measured `-R`
  costing 7.877 → 9.028 ΔE00 on a matrix fit while doing the anti-clipping job
  a cLUT wants.

**2 · The hard rule, made mechanical.** `_may_auto_setup(ctx)` is the one
predicate every automatic path asks, and it says no when either is true:
  * **the bucket has stored settings.** `_ctx_stored` is computed ONCE, in
    `_load_ctx_configs`, from the settings store. It is deliberately not read
    off `_ctx_cfg`, which gains an entry for every bucket the window merely
    VISITS (`_snapshot_context`) — a user who ticked and unticked the printer
    box would otherwise look like a user who had saved settings, and that is
    the shape of bug this rule exists to prevent.
  * **the user has changed one of the three this session.** After that the
    window sets nothing for that bucket, whatever happens to the patch count.

  A bucket saved before this version has no `scenario` key, which is the whole
  migration: it comes back as the Custom state, no radio lit, nothing applied,
  no schema bump. An explicit click on a scenario is not the automatic path and
  applies to any bucket, because the user has just asked out loud.

**3 · What changed in the design document, and it needs saying.**
`beta 9/printer-from-scan/USAGE-SCENARIO-DESIGN.md` §3 rule 2 says *"the
scenario never re-applies itself. Not on reopening the window, not on switching
source, not on picking a file."* Item 5 requires the opposite: a rule keyed on
the patch count cannot act before a chart is picked. **The amendment, and it is
proposed rather than assumed:** the everyday scenario re-applies when the patch
count it depends on CHANGES, and only while the bucket is one `_may_auto_setup`
allows. Reopening the window still applies nothing, because a saved bucket is
off limits for ever and an unsaved one has no patch count until something is
picked. §2's table also names the wrong white-point value for scenario 1; it
predates B8-75 (see that entry's own closing note) and is now moot, because
scenario 1 has no fixed values at all.

**4 · The `-R` switch is visible when it is in force** (Knut: *"the -R checkbox
is invisible"*). An unticked box beside a command line reading `-u -R` is
false, so while "Scale white to a perfect white surface (-u -R)" is chosen the
switch is shown **ticked and disabled**, with a wrapping line beside it saying
where the tick came from. Three decisions inside that:
  * **disabled**, because it cannot be turned off from here:
    `profile_builder.py:487` emits `-R` for `wp_mode == "uR"` whatever the box
    says, so an editable control that cannot change the outcome is worse than a
    locked one;
  * **a label, not a tooltip**, because Qt sends no events to a disabled widget
    and a disabled checkbox's tooltip never appears;
  * **the stored value stays the user's own** (`_r_choice`, written by
    `values()`). Without that, opening the window and pressing "Save as
    Defaults" would store `-R: true` for ever, and a later switch to "Map chart
    white to white" would carry a clamp nobody asked for. The command line is
    byte-for-byte what it was, which `test_the_locked_tick_changes_no_command_line`
    proves by comparing the two argument lists.

**5 · The white-point "(default)" marker is gone**, replaced by "(best for cLUT
profiles)" and "(best for matrix profiles)" — Knut's first route, because his
second (change the selection when the profile type changes) is a control that
silently undoes an edit, which is what `USAGE-SCENARIO-DESIGN.md` §3 rule 2 and
this whole entry exist to prevent, and it would have to fight the other two
mechanisms over the same widget. His own wording "(recommended for cLUT
profiles)" could not be used, and the three characters are MEASURED: against
the app's own Fusion style it made the window **53 px wider the moment the
Advanced disclosure was opened**, "(recommended for cLUT)" 3 px wider, and
"(best for cLUT profiles)" fits with nothing to spare
(`test_the_worst_languages_fit_a_1280_screen`). A translation longer than the
English will be caught by that same test, which is where it belongs.

**6 · The three factual errors in the printer-mode help, in his words.**
  * *"the scanner profile must be built in this window's ordinary scanner mode,
    from a bought target — not true"*: the text now says either source works,
    a chart made in ChromIQ included, as long as somebody has measured it with
    a real spectrophotometer.
  * *"reads as if choosing cLUT XYZ automatically sets -ua — it does not"*: the
    text now says so outright, and then says what the old sentence was reaching
    for. It is `scanin` that reads the scanner profile with
    `icAbsoluteColorimetric` hard-coded, so ChromIQ's own measurement is
    already absolute whatever the profile was built with. That is why the flag
    looks small inside ChromIQ, and it has nothing to do with the profile type.
  * *"'With the Lab table it is the difference … It costs nothing. Set it.'
    reads as advice to choose the Lab table, and 'Set it' has no referent"*:
    the paragraph now leads with what the flag is worth outside ChromIQ, says
    the Lab table's rescue is beside the point because the answer there is the
    XYZ table, and ends by naming the control and the entry to set.

**7 · B8-70 is absorbed.** The greyed third scenario carries the reason a
bought target cannot profile a printer; `_mode_note` is the same widget, moved
under it, and the gate itself is unchanged.

- **§M does not govern any of this**, and that was checked rather than assumed:
  §M is the catalogue of measurement WINDOWS (`test_message_catalogue.py`
  parses §M and pins `WINDOW_SOURCES`), and nothing here is a window. The one
  new sentence that reaches a user unprompted is a LOG line, which is the same
  place B8-69 and B8-75 speak from and for the same reason.
- i18n: 26 keys in, 9 stale keys out, across all thirteen catalogues. German is
  translated for all 26; the other eleven carry the English source, per
  "translate before a final, not during a beta". Two long help bodies are in
  `tests/data/em_dash_allowed.json` with a reason that is checked before it is
  written: every em dash in them is inside a quotation of a dropdown entry
  whose own grandfathered label contains one ("cLUT — XYZ table"), and naming a
  control approximately is the fault this text was rewritten to remove. Rename
  those two labels and both entries go with them.
- guarded by: `tests/test_the_window_says_what_the_profile_is_for.py`, 40 tests.
- evidence: test_the_patch_count_rule_is_knuts_rule,
  test_the_everyday_scenario_is_that_same_rule_and_not_a_second_answer,
  test_the_white_point_markers_are_derived_from_the_same_table,
  test_the_two_matrix_types_and_the_two_clut_types_are_all_four,
  test_the_measuring_scenario_sets_the_three_measured_settings,
  test_the_measuring_scenario_does_not_set_restrict_white_black_primaries,
  test_the_printer_scenario_changes_no_colprof_setting,
  test_the_three_are_listed_in_the_order_you_would_do_them,
  test_the_second_and_third_say_they_are_two_steps_of_one_job,
  test_choosing_a_scenario_sets_the_three_controls,
  test_a_scenario_locks_nothing,
  test_the_window_names_the_divergence_when_the_user_overrides,
  test_a_setting_the_user_changed_is_never_chosen_for_them_again,
  test_the_custom_state_is_a_state_and_not_a_fourth_option,
  test_a_bucket_with_stored_settings_is_never_set_up_on_first_open,
  test_a_stored_bucket_from_before_this_feature_shows_no_scenario,
  test_the_stored_set_is_read_from_the_store_and_not_from_the_visits,
  test_a_bucket_nobody_ever_saved_is_set_up_from_the_patch_count,
  test_the_patch_count_rule_is_off_in_printer_mode,
  test_it_applies_to_a_bought_target_as_well_as_a_chart,
  test_the_scenario_is_stored_with_the_bucket,
  test_the_R_switch_is_shown_ticked_and_locked_when_the_white_point_carries_it,
  test_the_locked_tick_changes_no_command_line,
  test_the_R_switch_comes_back_with_whatever_the_user_had,
  test_saving_defaults_on_that_entry_never_stores_an_R_nobody_chose,
  test_a_printer_build_has_no_such_switch_to_lock,
  test_the_help_no_longer_says_the_profile_must_come_from_a_bought_target,
  test_the_help_says_outright_that_the_xyz_table_does_not_set_ua,
  test_the_help_does_not_end_by_pointing_at_the_lab_table,
  test_the_help_points_at_the_scenario_that_sets_all_three,
  test_the_printer_scenario_is_greyed_for_a_bought_target_with_its_reason,
  test_the_printer_scenario_and_the_tick_are_one_control,
  test_the_window_says_what_it_set_up_and_why,
  test_it_says_nothing_when_it_changed_nothing,
  test_switching_source_never_writes_the_new_modes_count_into_the_old_bucket,
  test_choosing_everyday_with_nothing_loaded_still_means_everyday,
  test_a_fresh_window_opens_on_the_everyday_row_and_says_so_once (replaces the
  explicit-click-only pin after Knut's 4.2.0 report: the fresh window now
  takes the same row automatically),
  test_the_explicit_everyday_click_with_nothing_loaded_never_says_0_patches,
  test_restore_defaults_restores_the_pair_a_fresh_window_shows,
  test_a_hand_edit_under_an_unknown_count_is_named_in_the_note,
  test_choosing_other_before_browsing_warns_about_nothing,
  test_the_printer_tick_round_trip_keeps_the_fresh_chart_row,
  test_a_hint_that_is_hidden_claims_no_height,
  test_the_standard_target_explanation_sits_against_the_rows_around_it,
  test_the_printer_guard_holds_in_the_window_where_it_is_reachable,
  test_saving_settings_means_the_same_thing_before_and_after_a_restart,
  test_a_saved_bucket_is_never_told_its_settings_are_a_divergence,
  test_a_saved_bucket_with_no_chart_yet_still_says_why_nothing_happens,
  test_a_hand_edit_is_still_named_as_a_divergence,
  test_the_divergence_line_carries_a_warning_mark,
  test_the_unknown_count_answer_is_the_rules_own_small_row,
  test_the_shipped_default_white_point_did_not_move_with_it,
  test_the_lab_note_does_not_contradict_the_profile_type_help.
  **EIGHT MORE MUTATIONS for the review's fixes, all eight caught**, each
  proved on disk first: both halves of CL-1a and CL-1b (including one that
  swallows the hand-edit case, which is the half that must survive), both
  halves of CL-4, CL-2's revert to the factory pair, and CL-6's return to
  lifting a lifted ceiling. Twenty-nine in total across the two rounds.
  **TWENTY-ONE MUTATIONS, every one caught, and every one proved present on
  disk before its run** (`scratchpad/mutate.py`, the harness refuses to believe
  a run whose replacement it cannot find in the file). Both halves of
  `_may_auto_setup`; `_ctx_stored` taken from the visits instead of the store;
  a pre-4.2.0 bucket given a scenario anyway; the mid-switch guard; the
  scenario dropped from the stored bucket; the divergence line silenced; the
  announcement silenced; the greyed printer scenario re-enabled; the everyday
  scenario given fixed settings of its own; the everyday click's fallback
  removed; `-R` added to the measuring scenario; the crossover moved off a
  hundred; the white-point markers un-derived from the setup table; the locked
  `-R` stored as a choice; the `-R` switch left editable; the `-R` switch not
  restoring the user's answer; the printer bucket no longer reporting the
  printer scenario; and the three help-text corrections each reverted.

  **THREE of them survived the first pass, and all three were real.**
  * dropping the stored-bucket half of the gate changed nothing, because the
    test used a bucket saved BEFORE this feature, which the scenario check
    already refuses. The case that rests on the gate alone is a bucket saved BY
    this version, on the everyday scenario. The test now covers both.
  * the printer clause of `_maybe_auto_setup` could not be told apart from
    `_scenario_for`'s answer by any test, so it was DELETED rather than left as
    a safety net nothing can measure. The invariant now lives in one place and
    the mutation of that place is caught.
  * one anchor did not match the file at all, and the run said so instead of
    reporting a pass.
**8 · Driven on screen, and the adversarial pass found two faults in this
change that no test of mine had.** `CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cj.ini`,
the real `AppSettings`, the real window, the real ArgyllCMS. Proof in
`Desktop/beta 9/scanner-usage-scenarios/` (shots, every Argyll argv, the
settings file, the profiles, PROVENANCE.md).
  * **the bought target's patch count was written into the CHART bucket.**
    `_on_mode_changed` calls `_on_target_changed` (which ends in `_refresh`,
    which is where the rule runs) BEFORE `_sync_colprof_context`, so for one
    call the source radio already says "a standard target" while `_active_ctx`
    is still the chart bucket. Measured: a chart bucket on the XYZ table at
    High with "Force Absolute Colorimetric" came back from one round trip
    through the standard-target side holding "Scale white to a perfect white
    surface". Nobody chose that. Fixed by refusing whenever `_active_ctx` and
    `_colprof_context()` disagree.
  * **choosing "everyday scanning" with nothing loaded left another scenario's
    settings under the lit radio.** With no patch count the rule has nothing to
    say and correctly said nothing, so `-ua` and the XYZ table at High sat
    under a radio labelled everyday scanning, and the divergence line could not
    catch it either (with no count there is no recipe to compare against). The
    explicit click now falls back to the window's factory settings, which is
    what `USAGE-SCENARIO-DESIGN.md` says scenario 1 pre-selects, and a chart
    still refines all three afterwards. The AUTOMATIC path is untouched:
    `setup_for_patch_count(None)` is still None.
  * **a hidden hint claimed about 700 px of the left column, and it is
    PRE-EXISTING.** `_WrapHint` reclaims its height in `resizeEvent`, and a
    hint created hidden gets one resize to Qt's default 100 px before anything
    lays it out: `heightForWidth(100)` for a paragraph is several hundred
    pixels, and that number was latched. Layouts skip a hidden widget, so
    nothing corrected it, and the moment the hint was shown it claimed that
    height with its text floating in the middle. Photographed on the real left
    column: two gaps of roughly 300 px, above and below the standard-target
    explanation, pushing everything after it off the visible pane. The widget
    is B8-70's, so **beta.10 has this too**, in standard-target mode; the usage
    scenario above it is what made it impossible to miss. A hidden label needs
    no height, so it now takes none, and the reclaim happens the first time it
    is shown and laid out.

    Worth keeping: **geometry alone did not find this.** Two probes read the
    live window and reported the hint at 75 px with nothing overlapping,
    because by the time they asked, those runs had settled. The picture of the
    column is what showed it, every time. A grab of the whole DIALOG does not
    show it either — `QWidget.grab()` does not composite everything inside the
    left pane's scroll viewport — so the proof shots photograph the settings
    column on its own as well.

**9 · The review (AGENT CL, 2026-09-06) found one thing worth not shipping,
and it was real.** No blockers otherwise: twelve routes at the stored-settings
rule and none defeated, item 3 proved to a byte (two real colprof runs
differing in one byte, the timestamp seconds), item 5's boundary exact at
99/100/101, and both gates re-run here (11,529 on master, 11,569 on the
branch, the +40 accounted for file by file).

  * **CL-1. Saving meant one thing before a restart and another after, and the
    window then blamed the user for ChromIQ's own choice.** Press "Save as
    Defaults" on a scanner bucket having changed nothing, saving exactly the
    three settings ChromIQ chose from a 288-patch target: `_save_defaults_
    clicked` wrote to the store but never added the bucket to `_ctx_stored`,
    which is read once at construction, so the rule went on managing the bucket
    until the window was reopened and then stopped for ever. And from then on
    every chart on the other side of the crossover was met with "your settings
    no longer match this scenario", listing three differences the user never
    made, under a lit radio whose own gloss promises ChromIQ sets those three
    from the size of the target. At 24 patches the settings it blamed them for
    kept the cLUT B8-19 measured as the WORSE one there (1.68 against 1.25
    ΔE00). Saving now means the same thing on both sides of a restart, and the
    everyday scenario says what is true instead: the settings are being left
    alone because they were saved, and here is what the rule would otherwise
    have chosen. A hand edit is still named as a divergence, which is the half
    that must not be swallowed.
  * **CL-2.** `SETUP_EVERYDAY_UNKNOWN` paired a MATRIX profile type with the
    white point this module labels "(best for cLUT profiles)", and gave the
    same scenario two answers at the same profile type. It is `SETUP_SMALL`
    now. `WP_MODE_DEFAULT` is deliberately untouched: a window nobody has
    configured still opens where B8-75 put it, and that pairing is Basti's.
  * **CL-4.** The divergence line had no mark, no indent and no gap, and read
    as a fourth gloss of the scenario above it. It carries "⚠", sits at the
    options' own indent and has air above it. The mark is added outside the
    translated string, so no catalogue can lose it, and the two informational
    lines deliberately do not carry one.
  * **CL-6, and it is PRE-EXISTING.** The Lab-table live note still described
    the world before B8-75: it told a user on the shipped default that their
    bright paper was being flattened and sent them to "Auto-scale to avoid
    clipping" to lift a ceiling that the profile-type help 130 lines above says
    already sits at about 114 % reflectance, above anything that can physically
    be put on the glass. One ⓘ, two answers, in all thirteen catalogues.
  * **CL-8 is a correction to the proof, not to the app.** The Build button
    does NOT ship clipped: `main.py` installs `CompositeAppFilter`, whose
    `ButtonFontFilter` gives every button Menlo and calls `fit_button_width`.
    A driver that builds a dialog directly skips the filter while the global
    QSS paints Menlo anyway, so the button is sized for the wrong font: 321 px
    with the filter against 286 px and a 110 px minimum without. Zero languages
    affected. The drivers now install the filter, and every shot in the proof
    folder was retaken through it. **The earlier note in this entry saying the
    clipping is pre-existing was wrong about WHY, and is corrected here.**

**10 · One thing the review floated that is NOT built, because it is Basti's.**
A bucket whose stored triple happens to equal the rule's own answer could keep
being managed: press "Save as Defaults" over what ChromIQ chose and nothing is
really claimed, so the rule could go on adjusting it as targets change, and
only a triple that DIFFERS from the rule's answer would stop it.

  It is attractive and it is a behaviour change, not a fix. Two things make it
  Basti's call and not an agent's. First, it decides what "Save as Defaults"
  MEANS: today it means "these settings, from now on", and under this it would
  mean "these settings, unless ChromIQ would have chosen them anyway", which is
  a different promise from the one the button's own tooltip makes. Second, it
  is not stable: the same save is claimed or unclaimed depending on which
  target happened to be loaded at the moment it was pressed, so two users who
  did the same thing get different behaviour later. The safe half of it is
  already built, which is that the window now SAYS what the rule would have
  chosen, so a user who wants it can take it in one glance.

- what is NOT done, and is somebody else's call:
  * the eleven catalogues other than German carry English and need the ordinary
    translation pass;
  * §10 above: whether a save that claims nothing should stop the rule;
  * the scenario glosses are three wrapped lines each, which is a lot of chrome
    above "pick your chart". `USAGE-SCENARIO-DESIGN.md` §7 raises it and offers
    a one-line form with the detail behind the ⓘ. That is Basti's to judge on
    screen, and it is a layout change, not a behaviour one.
### B8-79 · Two layout controls did nothing at all on a hexagonal chart, and stayed live and armed
- blocks release: no
- status: FIXED
- found by: Knut, 4.1.5-beta.10 — *"When I try to make hexagonal patches on a
  chart for CR30, and setting in the layout engine Calculation method 'By
  columns / rows…', then changing the patches per strip has no function or
  effect. When 15 strips the patch width is 10.9 mm, and there is 28 rows, no
  matter what I set on patches per strip. … I assume the same thinking also
  applies to … 'Minimum patch height (% of width)' is not really used. **This
  should be verified.**"*
- detail: verified, and BOTH of his assumptions are right. A honeycomb
  interlocks, so its cell height is fixed at `width * sqrt(3)/2`;
  `area_fit.derive_area_patch_size` sets that ratio before it solves and snaps
  the solved height back to it afterwards, precisely so hexagons cannot come out
  stretched (Basti's ruling, 2026-08-28). A hexagonal grid therefore has ONE
  free parameter, and the panel offered two.
  Swept against the real engine, CR30 + SpectroScan, A4 and A3:
  **(a)** by columns/rows, hexagons, 15 strips pinned: patches-per-strip
  0 / 5 / 10 / 20 / 28 / 40 / 60 / 100 all give patch 10.85 x 9.39 mm, 15 strips
  of 26, 390 patches. Eight values, one chart. Knut's own 10.9 mm / 15 / 28
  falls out of the same run on Letter with a 10 mm right margin (10.96 x 9.49,
  15 x 28, 420), and 28 margin/paper combinations reproduce his exact triple.
  **(b)** by patch width, hexagons, minimum width 8 mm: height 50 / 100 / 150 /
  200 / 300 % all give 8.29 x 7.18 mm, 20 strips of 33, 660 patches, where
  rectangular gives 1113 / 630 / 441 / 336 / 231.
  The row box is NOT inert when Strips (columns) is on auto, so the lock is
  conditional on the strips being pinned rather than on the shape alone.
  Reproduced in the running app (`scripts/drive_hex_locks_the_inert_controls.py`,
  screenshots on the Desktop under `beta 9/hex-layout-controls/`).
- fix: `LayoutOptionsPanel._update_area_hex_locks` greys the inert box and puts
  the reason on the row's ⓘ button, which `TooltipButton.changeEvent` keeps
  enabled inside a disabled parent. A DISABLED QWIDGET RECEIVES NO HOVER EVENTS,
  so a tooltip on the greyed spin box may never appear at all; the note's first
  line also goes into the ⓘ's own hover tip. No value, no geometry and no
  default was touched: eleven recorded (instrument, shape, method, grid) charts
  come out byte-identical.
- deferred out of this fix, reported for Knut and Basti: **(1)** in "By columns /
  rows" with Strips on auto, the HIDDEN "Minimum patch height (% of width)"
  genuinely drives the layout for rectangular patches (50/100/150/200 % gives
  120 / 240 / 380 / 520 patches on a CR30 A4), which is the same fault pointing
  the other way and the same shape as the ColorMunki density row already
  documented in `_sync_layout_mode`; **(2)** on a honeycomb with Strips on auto
  the requested patches-per-strip is delivered short by one or two (10 -> 8,
  15 -> 13, 20 -> 18, 30 -> 29; rectangular is exact). That is a control that
  SHOULD work and does not, so the arithmetic was left alone.
- evidence: test_patches_per_strip_is_inert_on_a_honeycomb_with_pinned_strips,
  test_patches_per_strip_is_still_live_when_the_strips_are_on_auto,
  test_minimum_patch_height_is_inert_on_a_honeycomb,
  test_minimum_patch_width_stays_live_on_a_honeycomb,
  test_the_lock_fires_exactly_where_the_control_is_inert,
  test_a_locked_row_always_says_why_on_a_button_that_still_works,
  test_clearing_the_lock_restores_the_row_and_drops_the_note,
  test_a_panel_with_no_selectors_locks_from_the_recipe,
  test_the_guard_would_catch_a_lock_that_stopped_firing,
  test_the_guard_would_catch_a_lock_that_fired_on_everything,
  test_the_chart_that_came_out_before_still_comes_out.
  Both mutations were proved to land: forcing `_area_is_hexagonal` False leaves
  the row live where the table demands it locked, and forcing it True locks a
  rectangular row that the table demands live. The eleven frozen charts were
  recorded from `origin/master` @ 848e6965 before the lock existed.
### B8-90 · The patch-set editor is unusable for any CR30 chart, and the error box is taller than the screen
- blocks release: yes
- status: FIXED
- found by: Knut, v4.1.5-beta.10, with a screenshot; analysed by Agent CK,
  `Desktop/beta 9/cr30-patch-editor/FINDINGS-agentCK.md` (CK-1); fixed by Agent CM
- detail: `workflow/ti2_relayout.py` builds its own printtarg argv and passed
  `spec.instrument_flag` to `-i` unvalidated. `instrument_to_flag` returns the
  ChromIQ-only sentinel `"CR30"` for a CR30 chart, and printtarg 3.5.0 has no
  such code: `printtarg.c:3345` answers `Argument to -i wasn't recognised` and
  prints 51 lines of usage. The rule against this EXISTED and lived in one
  module: `chart_creator._build_printtarg_args` refuses to build an argv for an
  ENGINE_ONLY instrument, and `ti2_relayout` does not import it. Reproduced end
  to end in the real app before any change: box 420 x 1433 px on a 1079 px work
  area, 354 px of overflow, OK button at global y 1451, on screen = False,
  window title discarded by macOS so the words "Render failed" were never
  visible. Both doors into the editor pre-load the selected target's chart, so a
  CR30 owner met this on every open with no way to get in front of it.
- fix: three layers. (1) `ti2_relayout.PRINTTARG_INSTRUMENTS` /
  `PRINTTARG_PAPER_MIN_MM` / `PRINTTARG_PAPER_MAX_MM` and
  `check_printtarg_can_lay_out()`, called from `regenerate()` before the process
  is spawned, so the message is ChromIQ's one sentence. The set is
  `printtarg.c:3323-3345` and the test parses it out of that parser rather than
  out of the usage text, which is the thing that is wrong (it prints `p3`;
  printtarg accepts `3p`). (2) `_regenerate` routes an ENGINE chart to the
  engine instead of running a printtarg pass whose result is discarded two lines
  later, which for a CR30 is a pass that cannot succeed. (3) B8-91, which is
  what makes (2) reachable at all. Re-driven in the real app afterwards: zero
  windows on open, `_regen is None`, the engine renders the chart's 299 patches.
  The report's recommended route (delete the load-time render entirely) was NOT
  taken: `_suggest_chart_name` consumes `self._regen.tiffs` for the Save-As
  default name, so the claim that every consumer is a hidden widget has one
  hole, and removing the render is a design question for Basti and Knut.
- evidence: test_the_instrument_set_is_printtargs_own_strcmp_chain,
  test_p3_is_not_one_of_them_and_3p_is,
  test_every_flag_instrument_to_flag_can_return_is_known,
  test_regenerate_refuses_a_cr30_chart_without_spawning_printtarg,
  test_the_refusal_says_something_a_person_can_read,
  test_opening_a_cr30_chart_never_spawns_printtarg,
  test_a_rejected_instrument_is_refused_at_the_boundary,
  test_an_accepted_instrument_passes_the_boundary

---

### B8-91 · "Save As" from the patch editor turned an engine chart into a printtarg chart
- blocks release: yes
- status: FIXED
- found by: Agent CK, same report (CK-4); fixed by Agent CM
- detail: `Ti2RelayoutDialog._engine_active()` decided which renderer draws the
  preview, which renderer writes a Save-As deliverable, and whether the
  printtarg pass runs at all, and it answered by asking a QGroupBox whether it
  was visible. Commit `72c54d1f` (2026-06-29, "#93: editor - hide the
  layout-editing panels") then hid that group unconditionally, believing the
  hidden widgets inert. Its message says the chart "renders and saves unchanged
  through the edit->apply round-trip", and Apply IS unchanged because that path
  hands back only the `.ti1`. What went dark with it, measured by CK in the real
  app on an i1Pro engine chart saved from this window: 525 patches became 528,
  a 21x25 strip grid became 24x22, and `channels.json` was gone. For a CR30 that
  sidecar is not decoration: `measure_manager.py:481` and `:1587` and the
  ChromIQ chartread fork read the chart's own recorded layout. A widget's
  visibility was load-bearing state for two months.
- fix: `_engine_active()` tests the thing it means. The expression is
  `_refresh_engine_panel_visible`'s own `use_engine` from before `72c54d1f`,
  restored verbatim (`self._engine_recipe is not None or (the engine setting and
  not a loaded printtarg chart)`), plus the unchanged non-RGB rule, so the
  function matches its own docstring again. Round trip re-driven in the real app
  with real Argyll: an i1Pro engine chart built through Create Chart and saved
  through the editor's own `_write_chart_into` came back 441 / 21 / 21 with
  `channels.json` present and a 441-patch `.ti1`, identical in every field, and
  the save message names the engine writer. `_suggest_chart_name` now takes its
  page count from the engine's pages so the Save-As default name does not lose
  its `2pages` token with the dropped printtarg pass. NOTE, because it is a
  behaviour change and not only a repair: with the layout-engine setting on, a
  from-scratch patch set saves through the engine again, which is what the code
  did before `72c54d1f`.
- evidence: test_engine_active_does_not_read_a_widgets_visibility,
  test_an_engine_chart_makes_the_engine_active,
  test_a_printtarg_chart_off_disk_keeps_printtarg,
  test_a_multi_ink_chart_is_engine_only_whatever_else_is_true,
  test_save_as_on_an_engine_chart_goes_to_the_engine_writer,
  test_the_suggested_name_still_counts_pages_for_an_engine_chart

---

### B8-80 · A message box could open taller than the screen and take its only button with it
- blocks release: yes
- status: FIXED
- found by: Agent CK, same report (CK-2); fixed by Agent CM
- detail: `ui/warning_sign.py::warn` builds a `QMessageBox`, calls
  `setText(...)` and `exec()`. `ui/widgets.py::fit_message_box_buttons` only
  ever WIDENS a box to fit its BUTTONS; nothing widened it to fit its TEXT and
  nothing capped its HEIGHT. B8-72's `_work_area_cap` /
  `_keep_inside_the_work_area` were METHODS OF `tools_dialogs._ToolDialogBase`,
  and a `QMessageBox` is Qt's class. Measured on the real screen with the
  3055-character printtarg dump of B8-90: frame 420 x 1433 px on a 1079 px work
  area, 354 px past the bottom, OK button at y 1451 and off screen. macOS could
  not rescue it, because there is no position at which a 1433 px window fits a
  1079 px work area. The box also took 420 px against its own 664 px sizeHint,
  so printtarg's 80-column lines wrapped to two and three each and roughly
  doubled the height. This is 51 shared call sites, not one window.
- fix: `ui.widgets.keep_message_box_inside_the_work_area`, called from `warn()`
  and `_boxed()` (so `inform` and `ask` too). It widens the box for its text up
  to a share of the work area, moves an overflowing body behind Qt's own "Show
  Details" (a scroll area, so it cannot overflow) with a purely mechanical
  split that invents no sentence, and clamps the frame on the next turn of the
  event loop once the caption is real. Re-measured on the real screen with the
  same body: 778 x 937 px, 117 px of headroom, OK button on screen at y 980, and
  the widening alone was enough that the detail pane was not needed there. Under
  the suite's 800 px offscreen screen the split does fire and all 3055
  characters stay recoverable.
- evidence: test_a_message_box_with_a_tool_dump_in_it_still_fits_the_work_area,
  test_every_button_of_that_box_is_on_the_screen,
  test_the_overflow_goes_behind_show_details_rather_than_being_lost,
  test_a_short_message_is_left_exactly_as_it_was,
  test_the_helper_is_what_does_it_and_warn_calls_it,
  test_the_cap_is_not_a_round_fraction_of_the_screen

---

### B8-81 · `Ti2RelayoutDialog` is outside B8-72's work-area fix, and so is its guard test
- blocks release: no
- status: FIXED
- found by: Agent CK, same report (CK-13); fixed by Agent CM
- detail: `class Ti2RelayoutDialog(QDialog)` sizes itself with a hard-coded
  `resize(1280, 820)` and `setMinimumSize(1000, 620)`, and the whole class
  contains no `showEvent`, no `availableGeometry` and no other `resize`. A
  1366x768 laptop's work area is about 728 px, so the window opens roughly 92 px
  taller than the screen, and Apply / Save... and Close sit at the very bottom of
  its right-hand column. B8-72 fixed exactly this class of fault and fixed it
  only for `_ToolDialogBase`'s subclasses, because the arithmetic was two
  methods of that class; `tests/test_a_tool_window_opens_inside_the_work_area.py`
  reads `inspect.getsource(tools_dialogs._ToolDialogBase)` and never mentions
  this window, so its name promised more than its scope. Not reproducible on
  this machine (work area 1079 px), which is why it is read off the source, and
  B8-72's own write-up records that macOS shoves a frame back up and Windows
  does not, so this would be reported from Windows first.
- fix: the arithmetic moved into `ui.widgets.WorkAreaClamped`, a mixin, with the
  same body; `_ToolDialogBase` and `Ti2RelayoutDialog` both inherit it, so the
  rule is inherited rather than remembered. `Ti2RelayoutDialog.showEvent` caps
  the opening height against the work area and clamps the frame, once, so a user
  who resizes afterwards is never overruled.
- evidence: test_the_patch_editor_opens_inside_the_work_area,
  test_the_editor_inherits_the_clamp_rather_than_restating_it,
  test_the_clamp_brings_the_editor_back_from_under_the_taskbar

---

### B8-82 · The patch editor was the only place in the app that showed an Argyll tool's raw stderr in a modal
- blocks release: no
- status: FIXED
- found by: Agent CK, same report (CK-3); fixed by Agent CM
- detail: `_on_regen_done` and `_save_as` did `warn(self, <title>, str(exc))`,
  and `ti2_relayout` wraps a whole `stderr` in its `RuntimeError`. Everywhere
  else in the app the same stderr goes to a scrollable log and, if a pattern
  matches, ChromIQ's own sentence goes to an `InfoDialog`. Measured: every
  printtarg argument-parse failure is 51 lines with exactly one useful line,
  always prefixed `Diagnostic:`; every runtime failure is one line prefixed
  `printtarg: Error - `. There is no case in which the usage text helps. A
  related fault in the same area: `_PRINTTARG_ERROR_PATTERNS`'s
  `unsupported_instrument` entry, and the comment above
  `ENGINE_ONLY_INSTRUMENTS` pointing at it, both claimed printtarg answers
  "Unsupported instrument type" to a bad `-i`. It does not; that message is a
  different error, raised for an itype that parsed. So the one pattern written
  for this case could never match it.
- fix: `Ti2RelayoutDialog._report_tool_failure`, used at all three sites that
  can receive a whole stderr (the render worker's result and both callers of
  `_write_chart_into`). It logs the full output, consults the shared
  `chart_creator` table through the new pure `match_printtarg_error()`, falls
  back to `printtarg_said()` quoting the tool's one useful line inside a
  sentence, and shows it in `InfoDialog`, which scrolls its body, caps itself at
  90 % of the screen and repeats its title as a heading inside the window so it
  survives macOS discarding a QMessageBox title. Three patterns added for the
  messages the argument parser really prints, and the false comment corrected.
  The wording is NOT in the measurement-model catalogue and does not belong
  there: that catalogue is enforced over an allow-list of measurement windows
  and this is not one, with `tab_chart`'s own unmatched-failure window as the
  precedent. One new string, reusing existing titles, translated into all twelve
  languages from each catalogue's own translation of the sibling string.
- evidence: test_every_call_that_can_receive_a_tool_dump_routes_it_through_the_window,
  test_the_failure_handler_quotes_one_line_and_logs_the_rest,
  test_the_table_now_matches_the_message_printtarg_actually_prints,
  test_the_one_useful_line_is_what_is_quoted,
  test_a_dump_with_nothing_useful_in_it_still_yields_a_line

---

### B8-83 · colprof "Matrix only (forced)" does not exist, and choosing it failed in silence
- blocks release: no
- status: FIXED
- found by: Agent CK, same report (CK-5); established and fixed by Agent CM
- detail: both algorithm dropdowns in `ui/tabs/tab_profile.py` and
  `data/parameters.yaml`'s colprof `-a` row offered `M`. colprof 3.5.0's switch
  (`profile/colprof.c:599-631`) has cases for `l L x X Y g G s S m` and a
  `default:` that calls `usage("Unknown argument '%c' to algorithm flag -a")`.
  Measured one probe per ASCII letter against the real binary: those ten parse
  and every other letter, `M` included, exits 1. CK's report gives the set as
  `l x X Y g G s S m` and misses `L`, which colprof accepts as a synonym for
  `l`; the constant added here is the source's set, not the report's.
  `profile_builder._build_args` passes the letter verbatim. CK marked the third
  link NOT ESTABLISHED; it is established here without a profile build:
  `Diagnostic: Unknown argument 'M' to algorithm flag -a` is matched by none of
  the fourteen entries in `_COLPROF_ERROR_PATTERNS`, and
  `tab_profile.py:5213-5232` opens a window only when `primary_failure()`
  returns something or the FWA case fires, so the silence is by construction.
- fix: `workflow.profile_builder.COLPROF_ALGORITHMS`, parsed out of colprof's
  own switch by the test. `M` removed from both combos, from
  `data/parameters.yaml` and from the label list in all twelve
  `parameters.<code>.yaml` overlays, which are keyed by flag rather than being
  lists, so a label list one entry too long puts the wrong words against the
  wrong letter instead of failing to load. colprof's real `Y` was NOT added:
  offering an algorithm the app has never offered is a feature decision.
- evidence: test_the_colprof_algorithm_set_is_colprofs_own_switch,
  test_every_algorithm_letter_the_ui_offers_is_one_colprof_has,
  test_the_labels_still_match_the_choices_in_every_language

---

### B8-84 · A paper size the widget offers and printtarg refuses, and a `meta.json` trusted by key name only
- blocks release: no
- status: FIXED
- found by: Agent CK, same report (CK-6, CK-8, CK-9); fixed by Agent CM
- detail: `paper_to_flag` falls through to an unbounded `f"{w:g}x{h:g}"` and
  nothing checked it, so a `.ti2` carrying `PAPER_SIZE "5000.0x5000.0"` loaded
  through "Load patch set..." produced the same unbounded box as B8-90.
  printtarg's custom `-p WWWxHHH` sanity-checks each axis against 1.0..4000.0
  (`printtarg.c:3311-3316`; measured, 4000x4000 parses and 4000.5x4000.5 does
  not), and all four custom-paper spin boxes in the editor were
  `setRange(10, 9999)` - a range the widget offers and the tool rejects, latent
  today because both groups are hidden but wrong the moment either is shown
  again. Separately, `_layout_from_dict` rebuilds `LayoutOptions` from a
  `meta.json` filtering on key NAME only and never on value, feeding `-a`, `-A`
  and `-m`; measured printtarg limits are `-a` 0.1-4.0, `-A` 0.1-8.0, `-m`
  accepted at 50 and refused at 60 on A4.
- fix: `check_printtarg_can_lay_out()` range-checks the custom `-p` at the same
  boundary as the instrument (B8-90). The four spin boxes take
  `_CUSTOM_PAPER_MAX_MM = int(R.PRINTTARG_PAPER_MAX_MM)` so the widget and the
  tool cannot disagree; the floor stays 10 rather than printtarg's own 1,
  because a 1 mm page parses and then fails at layout time.
  `LayoutOptions.__post_init__` clamps to the widgets' own ranges while leaving
  each value's int/float TYPE exactly as it arrived, so a saved `meta.json`
  still round-trips to the value it was written with.
- evidence: test_an_accepted_paper_passes_the_boundary,
  test_a_paper_outside_printtargs_range_is_refused,
  test_a_paper_NAME_is_left_for_printtarg_to_judge,
  test_the_paper_ceiling_is_printtargs_own_sanity_check,
  test_the_custom_paper_spin_boxes_cannot_ask_for_a_page_printtarg_refuses

---

### B8-85 · The Manual command preview showed a CR30 user a command line printtarg rejects
- blocks release: no
- status: FIXED
- found by: Agent CK, same report (CK-11); corrected and fixed by Agent CM
- detail: `tab_chart._refresh_manual_command_preview` decides whether to show
  the engine summary or a `printtarg ...` line with its own `use_engine`
  expression, and that expression lacks `_should_use_engine`'s first rule: an
  ENGINE_ONLY instrument takes the engine whatever else is set. So a CR30 user
  with the layout-engine setting off was shown `printtarg -iCR30 ...`, a command
  line that cannot be run, describing a build that always takes the engine. One
  correction to the report: it says this label applies `{"3p": "p3"}`. It does
  the opposite (`"3p" if p.instrument == "p3"`), which is correct; the two
  `{"3p": "p3"}` maps at `:5324` and `:17887` translate into ChromIQ's engine
  namespace and never reach a command line. The CR30 half of the finding stands.
- fix: `use_engine` now begins with `p.instrument in ENGINE_ONLY_INSTRUMENTS`,
  mirroring `_should_use_engine`. Covered by the same vocabulary test that pins
  every place in the app that turns an instrument key into a printtarg `-i`.
- evidence: test_no_path_in_the_app_can_hand_printtarg_the_string_p3

---

### B8-86 · chartread extra arguments are joined with a space and re-split with shlex
- blocks release: no
- status: FIXED
- found by: Agent CK, same report (CK-12, first half); fixed by Agent CM
- detail: `tab_measure._collect_guided` and `_collect_manual` join the option
  rows' arguments with `" ".join` and `measure_manager` re-splits them with
  `shlex.split`, so a value containing a space is torn in two. Latent, not live:
  no current option row carries one. `data/parameters.yaml:1213` already
  declares a `-X file.ccmx` row, and a path with a space is the normal case the
  day that is wired up. `tab_chart` does the same round trip correctly with
  `shlex.join`.
- fix: `shlex.join` in both collectors, matching `tab_chart`.
- evidence: test_chartread_extra_args_survive_a_path_with_a_space

---

### B8-87 · The patch editor's instrument combo holds a value the chart does not have, and the user cannot see it
- blocks release: no
- status: OPEN
- found by: Agent CK, same report (CK-7, corrected by his own Part 5.1)
- detail: `_pt_instr` offers only `i1` / `3p` / `CM`, so `findData("CR30")`
  returns -1 and the combo is silently left showing item 0 while
  `spec.instrument_flag` is `CR30`. The same is true of `SS`. His first reading
  of this - that a user could pick ColorMunki out of curiosity and silently
  convert a CR30 chart - he withdrew himself: the whole `_pt_box` group is
  hidden by the #93 decision, so the control is not reachable. What is left is a
  hidden control holding a value that does not match the chart. The HARM it
  caused is gone with B8-90 and B8-91: that chart no longer goes near printtarg,
  so the invisible value no longer decides whether the window works. What
  remains is Part 10's Q5, whether hiding rather than removing was the right
  mechanism for #93, which is a design question and not an agent's to answer.
- fix: not attempted. Left OPEN rather than DEFERRED because nobody has been
  asked yet.

---

### B8-88 · The instrument-port spinner is a bare 1-9 with nothing enumerating the ports
- blocks release: no
- status: OPEN
- found by: Agent CK, same report (CK-10), measured by his subagent and not
  re-run by him or by Agent CM
- detail: `ui/tabs/tab_measure.py:2206` and `:2745` set the instrument-port
  spinner to `setRange(1, 9)`, and `-c` on chartread and spotread is an INDEX
  into the ports ArgyllCMS enumerated. `core/argyll_instruments.py:124` already
  enumerates instruments and its result is not used to bound the spinner.
  Reported measurement: `spotread -c 9 -N` answers `Error - No instrument at
  port 9`.
- fix: not attempted on beta night. Bounding the spinner means wiring the
  enumeration into two Measure tabs and deciding what happens when enumeration
  is empty or the instrument is unplugged mid-session, which is a measure-path
  change for a fault whose symptom is one clear Argyll error line.

---

### B8-89 · The patch-capacity probe swallows a printtarg failure and shows a wrong number
- blocks release: no
- status: OPEN
- found by: Agent CK, same report (CK-12, second half), read and not driven
- detail: `chart_creator._probe` reuses `_build_printtarg_args(p)`, user extras
  included, and treats ANY non-zero exit as `pages = 0`. `_binary_search` then
  returns its estimate with only a `log.warning`. So a malformed extra printtarg
  argument does not raise: it collapses the patch-capacity search and the user
  is shown a wrong "fits per page" number with no message.
- fix: not attempted. What a capacity search should DO when the tool refuses the
  user's own extra flag - report it, fall back, or refuse to build - is a
  decision rather than a repair, and the wrong number is not a data loss.
### B8-92 · A hexagonal patch was reported as the row pitch, so the panel said it was smaller than it prints
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-06, on 4.1.5-beta.10 (`/tmp/knut2.log`); measured and
  fixed by Agent CO
- detail: Knut, verbatim:

  > *"In the Chart layout information frame, the 'Patch size (mm)' has the
  > correct width according to the Patch width measurement in the 'Measured
  > from Preview' frame, but the height part is wrong and too small. For a
  > hexagonal patch, the height top-tip to bottom-tip is always larger than the
  > patch width, but the 'Patch size (mm)' says 11.3 x 9.78."*

  He is right, and by exactly 4/3. `instruments._build_base` builds a honeycomb
  with `plen = pwid · √3/2` (SpectroScan `:588`, CR30 `:727`), which is the
  interlocking ROW PITCH, and `raster._hexagon_points` puts the apexes at
  `y0 − plen/6` and `y0 + plen + plen/6`, so the drawn patch spans `plen · 4/3`
  = `pwid · 2/√3`, tip to tip. 11.3 · √3/2 = 9.786, which is what he saw;
  11.3 · 2/√3 = 13.05, which is what he gets. The panel was reporting the
  spacing between patches under the label "Patch size".

  **Measured, not derived.** Rendered at 1200 dpi with every patch a different
  colour, so an interlocking neighbour could not be mistaken for the patch under
  test (a same-colour scan merges three rows and reports a height three times too
  big), the drawn hexagon came out 7.027 × 8.086 mm against a 7.006 × 6.075 mm
  slot for the SpectroScan and 12.002 × 13.843 mm against 12.002 × 10.393 mm for
  the CR30. Ratios 1.33101 and 1.33198 against an ideal 4/3; the residual is
  pixel snapping.

  **The width is honest, and that is the control.** Both frames read the same
  field: "Patch width (in strip reading direction)" is
  `rects[0]["w"] · px2mm` (`margin_inspector.py:294`) and the width half of
  "Patch size" is `r0["w"] · 25.4/dpi` (`tab_chart.py`). A hexagon has flat
  vertical sides, so it is exactly as wide as its slot: 12.002 against 12.002 mm
  in the raster. Only the height was ever wrong.

  **Nothing computational depended on it.** Capacity subtracts `2·hxeh` before
  fitting rows (`geometry.py:83`, `:90`, `area_fit.py:44`) and placement shifts
  the block down by `hxeh` (`geometry.py:278`), so the page fit already knows
  about the overhang and reserves it. The margin inspector already expands
  `y0`/`y1` by `h_px/6` for a hexagonal recipe (`margin_inspector.py:283-286`),
  so its margins and strip length were already the real ink extremes. This was a
  display fault only, and the sheet is unchanged.

  Two siblings were found by the same sweep and fixed with it: the Manual info
  line's "patch {w}×{h} mm" summary echoed the same slot height, and the Manual
  "Patch size (mm)" tooltip claimed the boxes were the patch when on a honeycomb
  the height box is the row pitch.
- fix: `workflow/hex_support.hex_patch_height_mm` / `HEX_HEIGHT_FACTOR`, a
  REPORTING helper the layout engine may not call, plus
  `ui/tabs/tab_chart._panel_patch_height_mm` shared by both feeds of the panel
  so the estimate and the on-screen column cannot drift apart. The panel gains a
  "Row pitch (mm)" row, shown only for a honeycomb: both numbers are real and
  both matter, so both are named rather than one being picked. The height
  tolerance that decides the amber "differs" flag is scaled by the same 4/3, or a
  honeycomb rendered at a low dpi would flag amber against itself.
- proved on screen: `scripts/drive_hex_patch_size_readout.py` drives the real
  window, builds a real CR30 honeycomb at Knut's own 11.3 × 9.78 and reads the
  labels back. Before: `Patch size (mm) 11.35×9.82`, no pitch row. After:
  `Patch size (mm) 11.35×13.1`, `Row pitch (mm) 9.82`, with "Patch width" in the
  other frame reading 11.3 in both. Screenshots on the Desktop under
  `beta 9/hex-patch-size/`.
- what is owed: three things, all Basti's or Knut's call, none of them fixed here
  because each changes behaviour rather than wording.
  1. **The Manual "Patch size (mm)" height box is a row pitch on a honeycomb.**
     What you type becomes `geom.plen`. Changing that would change every chart
     built from a stored recipe, so the number was left alone and the tooltip now
     says what it is. Whether the LABEL should change for a hexagonal instrument
     is a design decision.
  2. **`preflight.check` tests `min(geom.plen, geom.pwid)`** against the 6 mm
     reliability floor (`preflight.py:54`, shown live in Preferences → Layout via
     `settings_dialog.py:5652-5670`). For a hexagon `plen` is the row pitch, and
     the patch's own smallest dimension is its width across the flats, which is
     larger. The check is therefore conservative, and it can call a honeycomb
     "below the floor" that is not. It decides when an error text appears, so
     changing it is a behaviour change and needs a ruling.
  3. **A CR30 honeycomb with spacers turned ON loses its bottom point.** The
     spacer bar is drawn after the patch above it and across the un-staggered
     slot, so it paints over the next hexagon's lower apex: measured at 600 dpi,
     12.107 mm drawn against 13.829 mm expected, the whole 1.73 mm point gone,
     and the patches print as houses rather than hexagons. Not the default (the
     CR30's default recipe sets `spacer_mode="none"` and the SpectroScan's
     `pspa` is 0), so no shipped default is affected, and it is a rendering
     change rather than a reporting one. Evidence:
     `cr30-hexagon-spacers-colored.png` beside the screenshots above.
- evidence: all nine live in one new file, `tests/…is_taller_than_its_row_pitch.py`:
  test_the_drawn_hexagon_is_four_thirds_of_its_slot (measures a rendered raster,
  so a change to `_hexagon_points` that leaves the constant alone still fails),
  test_the_slot_is_the_row_pitch_and_is_smaller_than_the_patch,
  test_knuts_own_numbers, test_the_panel_feed_reports_the_patch_and_the_pitch,
  test_a_square_chart_has_no_second_number,
  test_the_panel_hides_the_pitch_row_for_a_square_chart,
  test_the_two_columns_of_a_honeycomb_agree,
  test_the_honeycomb_geometry_is_untouched,
  test_no_layout_code_reports_its_way_into_the_geometry.

  Five mutations, each proved to land before the run: setting
  `HEX_HEIGHT_FACTOR` to 1.0; making `_panel_patch_height_mm` ignore its
  `hexagonal` argument; changing `raster._hexagon_points` to `ph/8` at the apex
  (the raster test fails, the constant test does not, which is the point of
  having both); scaling `pwid` in `patch_rects_px` so the geometry moves; and
  importing the reporting helper into `workflow/layout_engine/geometry.py`.
### B8-95 · The layout panel's estimate column described the chart from before the last build, so its two columns showed two different charts
- blocks release: no
- status: FIXED
- found by: Basti, 2026-09-06, on 4.1.5-beta.11, with Knut's CR30 preset set;
  reproduced on screen and fixed by Agent CS
- detail: Basti, with `CR30-A4-360p-1page-Portrait-w11.0mm` loaded, read the
  Chart layout information panel as **on screen 360, estimate 192**; loading the
  192-patch preset next read **192 / 360**. Each column appeared to be showing
  the other preset's chart. His screenshot carried a second oddity: with the
  panel's own "Strips (columns)" control reading **15** and "Patches per strip"
  **24**, the estimate said **8** strips.

  **It is one number, not two faults.** `_predict_layout_info` derives the
  strips row from the patch total it is handed:
  `cols = ceil(min(total, page capacity) / patches_per_strip)`. Measured against
  the layout engine with this preset's own recipe: 192 patches give
  `steps=24, patches_per_page=360, cols=8`; 360 give `cols=15`. So 8 is not a
  column count solved from a patch width and the estimate is not ignoring the
  "By columns / rows" method - it honours the 15x24 grid in every case. Feed it
  the right total and 15 comes back.

  **The cause.** The estimate column was computed only from the SETTINGS-change
  path (`_refresh_manual_command_preview`). Nothing recomputed it when the chart
  in the preview changed: `_set_margin_chart` called `_update_layout_info`,
  which fills the "on screen" column ONLY. And the count the estimate lays out
  comes from `_onscreen_patch_total()`, read from that very chart's `.ti2`. So
  every Generate published a panel whose estimate described the chart that was
  on screen *before* the build. The estimate lagged exactly one chart, which a
  two-preset A/B makes look like a swap.

  Driven in the real window with his own presets, before the fix:

  | step | on screen | estimate |
  |---|---|---|
  | nothing generated | (dash) | 360 (the 15x24 capacity fill) |
  | pick the 192 preset | 192 | 360 |
  | pick the 360 preset | 360 | 192 |
  | pick the 192 preset | 192 | 360 |
  | press Generate, nothing changed | 192 | 360 |

  The fifth row is the part that made it permanent: an explicit Generate did not
  correct it either, and it stayed wrong until some control was nudged.

  **Ruled out, measured not assumed:** changing the instrument and seeing
  nothing move is CORRECT here. With an explicit grid in area-first mode the
  instrument does not change the geometry (CR30 / i1 / CM / SS all return
  pwid 11.26, plen 11.16, 24 steps, 360 per page for this recipe). And the
  0.04 mm gap in the "Patch size (mm)" row is render snapping, not a mismatch:
  11.26 mm at 200 dpi is 88.66 px, drawn as 89 px = 11.303 mm. The panel's own
  0.15 mm tolerance already declines to flag it.
- fix: the estimate block moves out of `_refresh_manual_command_preview` into
  `TabChart._refresh_layout_estimate`, which `_set_margin_chart` now calls too -
  so the one door every chart comes through refreshes BOTH columns. A second,
  quieter error is fixed with it: `_estimate_patch_total` now prefers the patch
  set that is already armed (`_pending_patch_set_total`: a preset's attached
  `.ti1`, or a built-in's bundled one, mirroring the branch `_on_generate`
  actually takes, override included) over the chart still on screen. Selecting a
  preset arms its `.ti1` long before the build finishes, and the estimate is
  "what Generate would give". The `.ti1` is also the DESIGNED count where the
  `.ti2` already carries the fill-up patches, so laying the `.ti2` total out
  again was padding a padded chart.

  **The chart is untouched.** Both presets were generated with the seed pinned,
  with and without the fix, and the page TIFF, the `.ti2` (only `CREATED`, a wall
  clock, removed), the `.ti1` and the engine's `channels.json` layout block are
  byte-identical across the pair:
  `scripts/drive_layout_estimate_chart_unchanged.py`.
- evidence: all six live in one new file,
  `tests/…layout_estimate_follows_the_chart_on_screen.py`:
  test_a_new_chart_on_screen_refreshes_the_estimate (Basti's journey in the
  order he walked it), test_the_estimate_strip_count_agrees_with_the_grid_control
  (the 8-against-15 symptom, and that a full page uses every strip the control
  asks for), test_an_armed_patch_set_beats_the_chart_still_on_screen,
  test_editing_the_targen_recipe_drops_the_armed_patch_set,
  test_refreshing_the_estimate_writes_nothing (a readout may not put a byte on
  disk), test_set_margin_chart_still_refreshes_the_estimate_in_source.

  Three mutations, each proved to land before the run: removing the
  `_refresh_layout_estimate()` call from `_set_margin_chart` (4 of the 6 fail);
  making `_estimate_patch_total` ignore the armed patch set (2 fail); and making
  the estimate report the grid's strip capacity instead of the strips the
  patches occupy (2 fail).

  On-screen proof for Basti, both columns and the controls in the same shot, in
  `~/Desktop/beta 9/layout-estimate-column/` (`before/` and `after/`, driven by
  `scripts/drive_layout_estimate_columns.py`).

### B8-93 · Both scanner help cards, and the window's own ⓘ, still taught the route the usage scenarios replaced
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-06, on 4.1.5-beta.11; mapped by Agent CP
  (`FINDINGS-agentCP.md`, H1-H4), built by Agent CR
- detail: Knut set the bar himself:

  > *"A user should be guided with simple steps, and given the more detailed
  > explanations as notes for a deeper understanding, if the user decides to
  > want that."*

  The three usage scenarios landed on 2026-09-06 (`97da3224f` /
  `af2d429234`). **Neither commit opens `ui/dialogs/welcome_dialog.py`**, and
  the window's own ⓘ had not been touched since 2026-07-13. So on the day the
  feature shipped, the help still taught the long way round:

  1. `ScannerProfileDialog.HELP` said *"There are two ways to provide the
     target — choose one at the top of the window"*. The top of the window is
     now **"Usage scenario: what is this profile for?"** and its three radios;
     the source choice is the second block.
  2. It said *"click Build profile with scanner or camera"*. In printer mode
     that button reads **"Build printer profile"** (`_apply_mode_title`), and
     so does the masthead and the window title.
  3. Its opening sentence promised *"a genuinely useful printer profile with
     no spectro at all"* and then the whole body was written for a scanner or
     camera profile. The printer route had no steps in it at all.
  4. **Found here, not in the mapping:** the contents list promised the
     sections "in order" and had them the wrong way round. They really run
     `SCANNING_TIPS_HELP` (averaging), then `SCAN_SETUP_HELP` (capture), then
     camera, then which target; the sentence listed capture first.
  5. `scanner_profile` step 6 was a 145-word instruction to set three controls
     by hand, and `printer_from_scan` step 2 was a 200-word one. That is
     verbatim what `SETUP_INSTRUMENT` now does from one radio button.
  6. `grep "usage scenario" tests/` returned **nothing**, which is why none of
     the above cost anything to leave broken.

  **Knut's bar could not be met by rewording, and that is the finding the work
  turns on** (CP, H3). A card had exactly four keys, and a step was
  `(tab, text[, optional])`. There was one register, the numbered step, so
  every explanation had to be written as an instruction.
- fix: a **note register**, then the content.
  * A step may now carry a fourth element, a sequence of `(heading, body)`
    notes. On screen each is a CLOSED disclosure (`welcome_dialog.StepNote`:
    a bold ▶ heading that is a real `QPushButton`, so Tab reaches it and Space
    opens it, with the body hidden under it and painted in the dimmed ink an
    optional step uses, in all three appearances). On paper every note prints,
    because a sheet has nothing to click, indented and at 12 px grey against
    the body's 14 px black (`help_card_print._notes_html`, `p.note`).
  * `scanner_profile` 6 steps → 5, `printer_from_scan` 9 → 7, both rewritten
    around the three scenarios: what each is for, when to choose it, what it
    sets. The reasoning, the measured numbers and the colour science are
    notes.
  * `ScannerProfileDialog.HELP`'s middle block is rewritten as three numbered
    steps (scenario, source, capture and build) and names both states of the
    build button. The unchanged "Using your profile" half was split into its
    own `tr()` so its reviewed German moved rather than being rewritten.
  * Three more bodies gained one sentence each: the "Which source?" ⓘ (it is
    the second question, after the scenario), the "Save as Defaults" tooltip
    (saving is what stops the scenarios setting anything, and nothing said
    so), and the printer-tick log line (it named the three settings and sent
    the reader to an ⓘ; it now names the scenario that sets them).
- what was checked and found NOT stale: the other nine ⓘ bodies in that window.
  "Which chart to read", "Chart geometry (.cht)", "Averaging several scans",
  "Averaging method", "Patch sample area", "Reading options", "Profile
  description (-D)" and "Command preview" say nothing the scenarios made
  false. `grep` for the two false claims across `ui/` finds them in this
  window only; every other occurrence of "Build profile with scanner or
  camera" is the TOOLS MENU entry, which is still its name.
- §M: does NOT govern this text. `tests/test_message_catalogue.py` guards an
  allow-list of measurement message WINDOWS (`WINDOW_SOURCES`, plus three
  module-level functions); a printable help card and an ⓘ body are in neither,
  and `ScannerProfileDialog.HELP` is a class constant no catalogue check
  reaches. Checked rather than assumed, because the driver helper turned out
  not to be governed either.
- proved on screen: `scripts/drive_cr_help_cards.py` drives the real app,
  opens both cards in English and German, opens every note, and prints each
  card to PDF. Screenshots and PDFs on the Desktop under
  `beta 9/colprof-and-help-cards/`. Settings sandboxed to
  `/tmp/chromiq-cr.ini`; `defaults read com.chromiq.ChromIQ
  custom_output_path` unchanged after the run.
- evidence: twenty-one checks in one new file,
  `tests/…_knows_about_the_usage_scenarios.py`. The scenario labels are read
  off the LIVE radio buttons and the three settings off `scanner_colprof`,
  never copied into the test, so a reworded control fails the help rather than
  drifting away from it:

  test_the_window_really_offers_three_usage_scenarios,
  test_the_card_names_the_usage_scenario_feature,
  test_the_scanner_card_names_the_everyday_and_the_instrument_scenario,
  test_the_printer_card_names_the_instrument_and_the_printer_scenario,
  test_a_card_that_lists_the_three_settings_must_also_name_the_scenario,
  test_the_printer_card_sends_the_user_to_the_scenario_not_the_tick_box,
  test_the_window_help_leads_with_the_usage_scenario,
  test_the_window_help_does_not_send_the_user_to_the_wrong_control,
  test_the_window_help_names_the_build_button_in_both_of_its_states,
  test_the_window_help_contents_list_is_in_the_real_order,
  test_every_note_is_a_heading_and_a_body,
  test_the_two_scanner_cards_use_the_note_register,
  test_no_step_of_these_cards_is_an_essay,
  test_a_note_is_never_the_only_place_a_warning_lives,
  test_a_note_starts_closed_and_its_heading_is_a_button,
  test_on_screen_a_note_is_dimmer_than_the_step_it_sits_under,
  test_a_note_prints_and_prints_as_a_note,
  test_a_card_with_no_notes_prints_exactly_as_it_did.

  The one that would have caught the whole thing is
  test_a_card_that_lists_the_three_settings_must_also_name_the_scenario: any
  card spelling out `SETUP_INSTRUMENT`'s three values is describing the manual
  route, and must name the feature that does it for you.

  The existing `tests/…must_be_built_for_measuring.py` gained
  test_the_step_itself_still_says_to_build_it_for_measuring, the other half of
  the rule: the three settings may live in a note, the INSTRUCTION may not, or
  "moved to a note" is indistinguishable from "deleted". Its four card checks
  now read the notes as well as the steps, through a `_card_text` helper that
  says in as many words why a note counts.

  **The schema change is inert for the other nineteen cards, proved rather
  than asserted.** Rendered before and after, from a clean `git archive`
  extraction of master: printed HTML sha256 identical 21/21, printed-PDF text
  (read back with pypdf, not from a preview) and page count identical 21/21,
  and on screen the grabbed pixels, the row geometry and every label and
  button identical 21/21.

  Fourteen mutations, each proved to land before the run: rendering a note
  open; dropping notes from the print path; printing a note at the body's own
  size; painting a note in the step's ink; never building a `StepNote`; a card
  that stops naming a scenario; the printer card back on the tick box; the
  first step no longer saying FOR MEASURING; an explanation put back into a
  numbered step; the false "top of the window" sentence restored; the help
  naming one build-button state; the help no longer naming the scenario row;
  the contents list back in the wrong order; and a card that lists the three
  settings without naming the scenario.

### B8-97 · The Build Profile Algorithm list: five entries could not build a profile, a sixth was a silent no-op, three named the wrong algorithm
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-06, on the published v4.1.5-beta.11 release note;
  surveyed by Agent CP, measured and fixed by Agent CQ
- detail: Knut objected to the beta 11 note, which said *"'Matrix only
  (forced)' in the profile Algorithm list could never build a profile.
  ArgyllCMS's colprof has no such setting."* He is right that the sentence is
  wrong: colprof has no *forced* matrix setting, but it does have plain matrix
  only, as lowercase `-am`, and ChromIQ offered that one too.

  The fault under the sentence is larger than the sentence. Beta 11 checked
  the offered letters against colprof's `-a` **parser** and removed the one
  letter (`M`) that never existed. But `-a` is parsed long before the
  measurement is opened, so all ten of the parser's letters parse, and what
  decides whether one can be USED is the `DEVICE_CLASS` in the `.ti3`:

  ```c
  /* colprof.c:1244-1246, the OUTPUT branch */
  else if (ptype != prof_clutLab && ptype != prof_clutXYZ) {
      error ("Output profile can only be a cLUT algorithm");
  }
  ```

  **MEASURED** against the ArgyllCMS 3.5.0 binary, `-ql`, one run per letter,
  on three real `DEVICE_CLASS "OUTPUT"` measurements (`Demo-Switching` run2,
  Knut's own `Knut-Scanner-printer.ti3` from the scanner window, and a
  synthetic 300-patch chart): of the eight entries the tab offered,
  **`g G s S m` all exit 1 and write no `.icc`**, and `X` exits 0 and writes a
  file bit-identical to `x` (three differing bytes, all of them the ICC
  header's creation-time seconds). Only `l` and `x` do anything at all.

  `X` is inert for a structural reason, not an incidental one: the OUTPUT call
  site is `make_output_icc(ptype, 0, …)` (`colprof.c:1256`) with `mtxtoo` a
  hard-coded literal `0`, while the DISPLAY branch passes `mtxtoo` through
  (`:1310`). The fallback matrix that `X` and `Y` exist to add is discarded
  before it is built, and colprof says nothing about it (the INPUT branch, by
  contrast, does warn: *"-aX not applicable to input profile, using -ax"*).
  ChromIQ's label for it, "XYZ cLUT + matrix", promised a matrix the file does
  not contain.

  **And it failed in the same silence beta 11's own note described.**
  `_COLPROF_ERROR_PATTERNS` had no entry matching
  `Output profile can only be a cLUT algorithm`, so picking one of the five
  gave no profile, no window and one line in a log. Beta 11 removed the entry
  that never existed and left the five that do.

  **Three labels named a different algorithm.** colprof's own usage text
  (`colprof.c:127-131`): `s = shaper+matrix`, `G = single gamma+matrix`,
  `S = single shaper+matrix`. ChromIQ said `s` was "Single gamma + matrix",
  `G` "Gamma + matrix (forced)" and `S` "Single gamma + matrix (forced)".
  `s` is the worst of the three: it is the algorithm ArgyllCMS calls *"superior
  to gamma curve profiles"*, labelled as the gamma one. "single" in colprof
  means ONE TONE CURVE SHARED BY ALL THREE CHANNELS, not "forced". The scanner
  window's four labels were correct all along.

  **A fourth list disagreed with both.** `data/parameters.yaml`'s colprof `-a`
  row offered the same eight letters, called `X` "(Absolute)" (a
  rendering-intent word, nothing to do with `-aX`), and its tooltip described
  `-ag`/`-as` as *"faster to compute"* for a printer, where they compute
  nothing at all. The wrong labels were carried into all twelve language
  overlays.
- fix: `workflow/profile_builder.COLPROF_ALGORITHMS_BY_DEVICE_CLASS` (the
  legal set per `DEVICE_CLASS`, from colprof's three branches),
  `OUTPUT_ALGORITHM_CHOICES` (`l`, `x`) and `output_algorithm()`. Both Build
  Profile combos, Guided and Manual, now offer those two; `parameters.yaml`
  and all twelve overlays are trimmed to match; the two Algorithm tooltips say
  why there is no third choice. `_COLPROF_ERROR_PATTERNS` gains the missing
  pattern, so this class of failure opens a window with a sentence in it
  instead of vanishing into the log.
- existing projects: nothing is lost and nothing changes in silence.
  `_set_algorithm_combo` coerces a stored letter and SAYS SO in the tab's log.
  `L`/`X`/`Y` map to the letter they are an alias of, and the note says the
  built profile is unchanged, which is measured, not assumed. `g G s S m` map
  to `l`, colprof's own default for an output profile, and the note says the
  stored letter could not build a printer profile at all. Every store is
  covered: the app defaults (`colprof_algorithm`,
  `manual2_colprof_algorithm`), a target's `meta.json`
  (`profile_settings["algorithm"]` and `["g_algorithm"]`) and a user's Manual
  preset all reach the same one method.
- proved on screen: `scripts/drive_colprof_algorithm_lists.py`, sandboxed to
  `/tmp/chromiq-cq.ini`; screenshots and log under
  `Desktop/beta 9/colprof-and-help-cards/CQ-*`.
- evidence: `tests/…colprof_algorithms_fit_the_device_class.py`:
  test_the_device_class_table_is_colprofs_own_three_branches,
  test_an_output_profile_is_a_clut_or_it_is_nothing,
  test_aX_and_aY_are_inert_in_an_output_profile,
  test_every_letter_a_window_offers_is_legal_for_what_that_window_builds,
  test_the_printer_windows_offer_exactly_the_letters_that_do_distinct_work,
  test_no_label_names_an_algorithm_the_letter_does_not_select,
  test_the_output_clut_error_has_a_pattern_and_a_message,
  test_the_pattern_matches_the_string_colprof_actually_prints,
  test_a_stored_algorithm_lands_on_one_that_works,
  test_the_build_profile_tab_says_when_it_moves_a_stored_algorithm,
  and in the slow tier, driven by the real binary rather than by a list:
  test_real_colprof_builds_a_profile_for_every_letter_we_still_offer,
  test_real_colprof_refuses_the_letters_this_app_stopped_offering,
  test_aX_really_does_make_the_same_printer_profile_as_ax.

  Seven mutations, each PROVED to land by reading the value back through a
  fresh interpreter before the run and again after the restore: re-adding
  `("m", "Matrix only")` to the printer combo; relabelling `s` "Single gamma +
  matrix"; breaking the new error pattern; making `output_algorithm` return the
  stored letter unchanged; putting `s` back in the printer mode list; adding
  `g` to the OUTPUT row of the device-class table; and adding `g` to
  `parameters.yaml`. All seven turned the file red. The first attempt at this
  produced a phantom and is worth recording: two of the replacements were
  written to keep the column alignment, so mutant and original were the same
  BYTE COUNT and the write-and-restore happened inside one second, and CPython
  reused the stale mutated `.pyc` of a file that had already been restored. A
  mutation appeared to be caught by a test it never touched. Every run now
  purges `__pycache__` and reads the value back.

### B8-94 · The scanner and camera window offered two profile types in printer mode that colprof refuses
- blocks release: no
- status: FIXED
- found by: Agent CP, 2026-09-06, on Knut's own measurement; fixed by Agent CQ
- detail: with "Profile my printer from this scan" ticked the window builds a
  `DEVICE_CLASS "OUTPUT"` profile, and `PTYPE_CHOICES` was populated into the
  combo once, at construction, and never filtered by mode. So "Shaper + matrix"
  and "Matrix only" were selectable in printer mode.

  MEASURED on `Knut-Scanner-printer.ti3`, the printer-mode measurement this
  very window produced (`ORIGINATOR "Argyll printread"`, OUTPUT, `iRGB_XYZ`,
  315 sets): `-as` and `-am` exit 1 with
  `Error - Output profile can only be a cLUT algorithm` and write nothing;
  `-ax` and `-al` build a profile. CP saw the window's own command preview read
  `colprof -v -D … -am -qm …` in printer mode, live, on screen.

  Mitigating, and worth crediting: the per-context settings buckets mean
  ticking "printer" loads the printer bucket, whose default is `l`, so nobody
  drifts into this; and unlike the Profile tab this window does print colprof's
  raw output to its log on failure. But the choice was offered, nothing warned,
  and "Save as Defaults" would have kept it in the printer bucket.
- fix: `scanner_colprof.PTYPE_CHOICES_BY_MODE` and `ptype_choices(printer)`;
  `scanin_dialog._rebuild_ptype_choices` refills the combo on every mode
  change, with signals blocked so the refill is not read as a user edit, and
  `_mark_default_combos` walks the mode's own list so the "(default)" marker
  cannot land on the wrong item. The scanner and camera side keeps all four:
  every algorithm colprof has is legal for an INPUT profile (MEASURED), and
  Shaper + matrix is the right answer for a small target.
- existing projects: `coerce_ptype` moves a printer bucket holding `s` or `m`
  onto the bucket's own default and `_say_the_profile_type_moved` says so in
  the window's log, in the same register `_announce_wp_default_migration`
  already uses next door.
- evidence: `tests/…colprof_algorithms_fit_the_device_class.py`:
  test_every_letter_a_window_offers_is_legal_for_what_that_window_builds,
  test_the_scanner_window_offers_all_four_types_off_the_printer_tick,
  test_a_stored_scanner_profile_type_lands_on_one_that_works,
  and the slow, binary-driven
  test_real_colprof_builds_a_profile_for_every_letter_we_still_offer, which
  runs the real colprof once per entry in each of the window's two modes.

### B8-98 · Quality was greyed out for the matrix profile types and put on the command line anyway
- blocks release: no
- status: FIXED
- found by: Agent CP, 2026-09-06; re-measured and fixed by Agent CQ
- detail: `scanner_colprof.CLUT_ALGOS` was commented *"the -a letters for which
  -q quality applies"* and `scanin_dialog._on_colprof_changed` disabled the
  Quality label and combo for anything else. Both halves were wrong at once:
  the claim is false, and `make_profile_params` passed
  `quality=main_vals.get("quality", "m")` unconditionally, so the greyed-out
  value went on the command line regardless. The user was told the control did
  not apply, could not change it, and it was used.

  ArgyllCMS says the opposite, in `colprof.html` under `-q`: *"For table based
  profiles ('cLUT' profiles), it sets the main lookup table size … **For matrix
  profiles it sets the per channel curve detail level and fitting 'effort'**."*

  MEASURED, controlled (one base filename in separate directories so the
  embedded description is constant, and the ICC header creation date-time
  zeroed before hashing, because an uncontrolled first run of this comparison
  is exactly how a confounded answer gets reported): `-q l/m/h/u` on a
  300-patch INPUT measurement gives **four different profiles for every one of
  `-as`, `-am`, `-ag`, `-aS` and `-aG`**. Sizes move for `s` and `S`
  (18620/18620/20156/23228 bytes) and stay constant for `m`, `g` and `G` while
  every hash still differs, which is the fitting effort changing the curve
  rather than its length.
- fix: the row is no longer disabled. Nothing about the command changes, only
  whether the user can see and set what is already being sent. `CLUT_ALGOS`
  keeps its name and its two members, which several other rules legitimately
  need, and its comment now says what it is (the two types that ARE a stored
  table) instead of what it is not. The Profile type ⓘ's Quality paragraph is
  rewritten to say `-q` applies to every type and what it means for each.
- evidence: tests/…scanner_colprof.py's test_ptype_choices_are_colprof_algo_letters
  keeps `CLUT_ALGOS` at its two members, and
  the new file's test_quality_is_never_greyed_out_again
  reads the enable rule off the window's own source, so putting the disabling
  back is red. The measurement is recorded here and reproducible from
  `Desktop/beta 9/colprof-and-help-cards/CQ-quality-probe.txt`.

### B8-96 · The published beta 11 release note said colprof has no matrix-only setting
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-06; corrected by Agent CQ
- detail: verbatim from `CHANGELOG.md` as published: *"'Matrix only (forced)'
  in the profile Algorithm list could never build a profile. ArgyllCMS's
  colprof has no such setting."* colprof has no *forced* matrix setting, which
  is what was removed and is true; but it does have plain matrix only, as
  lowercase `-am` (`colprof.c:628`), and ChromIQ offered that one as well. The
  sentence reads wider than the fact.
- fix: the sentence in `CHANGELOG.md` now says *no forced matrix setting*,
  carries the correction openly rather than rewriting history, and points at
  the next release for the rest of that list. The GitHub release page is
  regenerated from the changelog, so correcting the changelog is what corrects
  the page.
- evidence: tests/…release_notes.py's test_the_current_release_renders_every_section_it_actually_has
  still renders the beta 11 entry, and
  the new file's test_an_output_profile_is_a_clut_or_it_is_nothing
  holds the fact the corrected sentence rests on.

---

### B8-99 · Knut's twenty CR30 charts ship as built-in presets, in their own group before Scanner
- blocks release: no
- status: FIXED
- found by: Basti, 2026-09-06, handing over `New presets CR30/` (twenty
  `.ti1` + `.json` export pairs he had curated from Knut's set) with: *"i want
  them listed for the cr30 in both preset dropdowns / speechbubble overlay
  before the scanner section"*. Built by Agent CT.
- detail: a feature rather than a fault, filed here because the register is the
  checklist. Twenty charts: ten on A4 and ten on US Letter, portrait, one to
  three sheets, patches 11 mm to 24 mm wide, twelve rectangular and eight
  hexagonal.

  **No new mechanism was needed, and one was nearly invented.** The files are
  the same export pairs the ColorMunki, i1Pro 3 Plus and two i1Pro families
  were built from, so this is a `FAMILIES` entry in
  `scripts/import_knut_presets.py` plus a `_Ti1Preset` row per chart, which is
  what that script's own docstring says a new line-up should be. It is kind 3
  ("ti1 to layout engine") in `docs/dev_builtin_presets.md`, and for a CR30 it
  could not have been anything else: Argyll has no layout for the instrument,
  so `chart_creator._should_use_engine` forces the ChromIQ engine on and
  printtarg never sees one of these charts.

  **The first family with two SHAPES.** Every one of the eight hexagonal charts
  moves the same four fields with `hflag` (`margin_left` 13,
  `margin_top`/`margin_bottom` 13, `text_edge_top_mm` 4, against the
  rectangular 15/17/12/8). Rather than five keyword arguments on eight rows,
  the shape has a name: `_CR30_HEX`, and a row says `hexagonal=True`. Three
  Letter hex charts move their top and bottom margins further and still spell
  those out. The importer gained the same idea as `Family.overlay`, so a chart
  taking the cut is validated against `base | delta` and cannot hide a fifth
  change inside the flag.

  **Two names round differently, and they are Knut's, not ours.**
  `Letter-150p-1page-Portrait-w17.0mm` prints 17.53 mm patches and
  `Letter-170p-1page-Portrait-w16.0mm-Hexagonal` prints 16.64 mm. Both are
  wider than the name says. The shipped recipes are byte-for-byte his exports
  (proved: every one of the twenty reproduces its export exactly), so this is
  his naming against his layout and the fix is his call. Pinned at what they
  measure so a change to either end fails.

  **The clip note's own numbers disagree with the margins it is printed
  beside.** It says top 34 / bottom 18 / left 14 / right 24 mm; the recipe sets
  17 / 12 / 15 / 26. It is the ColorMunki note copied forward. Carried verbatim
  rather than corrected, because what a chart prints on paper is his call.

  **A user preset of the same name is untouched.** Basti has all twenty saved
  in his own presets folder. A built-in is matched by a sentinel KEY and listed
  under its own "★ ... · built-in" label, so his files collide with neither the
  key nor the label the dropdown filters on: they stay listed above the
  built-ins, stay editable and stay deletable. Nothing is removed, hidden or
  frozen.
- fix: `ui/tabs/tab_chart.py` gains `_CR30_BASE`, `_CR30_HEX`, `_CR30_CLIP_TEXT`,
  `_CR30_GROUP` / `_CR30_DIR`, the `_cr30_preset()` helper and twenty rows;
  `INSTRUMENT_GROUP_LABELS` gains CR30 so the heading is the Instrument field's
  own words ("CR30 (ChnSpec)"); `BUILTIN_PRESET_GROUPS` gains the group BEFORE
  Scanner, which orders the Presets dropdown, the ★ overlay, the #66 "Compare
  with profile" list and the New-chart "Load setup from preset" list together.
  `_knut_tooltip` gains a CR30 branch: the shared engine tooltip calls a wide
  clip band "the run-up your instrument needs before the first patch", and a
  CR30 has no run-up, being a round hand-held colorimeter set on one patch at a
  time. `scripts/import_knut_presets.py` gains the `cr30` family and the
  `Overlay` mechanism. Assets: 20 x (`chart.ti1` + `recipe.json`) under
  `assets/charts/knut/rgb/cr30/`, 676 KiB on disk (226 KB compressed).
- proved on screen: `scripts/drive_cr30_builtin_presets.py` drives the real
  window, reads all four preset lists back, and builds **all twenty from the
  real dropdown** (through `activated`, which is what a click emits, not
  `setCurrentIndex`, which applies nothing). Twenty out of twenty landed on the
  paper, patch count, page count and patch shape their names promise, zero
  mismatches. Screenshots and a contact sheet of all twenty sheets are on the
  Desktop under `beta 9/cr30-builtin-presets/`; `custom_output_path` was empty
  before the runs and is empty after them.
- what is owed: three things, all Knut's or Basti's call, none of them changed
  here.
  1. **The two names that round differently** (above). Rename the chart or
     re-cut the layout.
  2. **The clip note's stale margin numbers** (above).
  3. **The display name.** Each row reads
     "★ CR30 · A4-360p-1page-Portrait-w11.0mm · Full layout setup · built-in".
     The "Full layout setup" marker Knut asked for is not typed into the name:
     it is earned automatically by shipping a `recipe.json`, so all twenty
     carry it with no per-row text. Nothing is proposed beyond that, because
     the filename already carries paper, count, pages, orientation and width.
- evidence: all of them live in one new file, `tests/…cr30_builtin_presets.py`
  (93 tests, everyday tier, four seconds):
  test_twenty_six_charts_registered,
  test_the_cr30_group_comes_before_the_scanner_section,
  test_the_family_has_its_own_group_named_as_the_instrument_field_names_it,
  test_every_chart_reaches_the_dropdown_and_the_overlay_smallest_sheet_first,
  test_every_row_carries_the_full_layout_setup_marker,
  test_recipe_differs_from_the_base_only_where_allowed,
  test_the_hexagonal_cut_is_exactly_these_four_fields_and_no_others,
  test_only_the_three_letter_hex_charts_move_a_margin_of_their_own,
  test_the_measured_shape_of_the_family,
  test_name_matches_the_bundled_patch_set_and_the_grid,
  test_sidecar_recipe_matches_its_chart,
  test_a_user_preset_named_after_one_of_these_is_left_alone,
  test_tooltip_names_the_device_and_does_not_invent_a_run_up,
  test_seeding_a_preset_puts_its_layout_on_the_panel,
  test_selecting_one_greys_targen_and_leaves_the_layout_editable,
  test_chart_builds_with_the_pages_and_patches_its_name_promises.

  Nine mutations, each proved to land before the run: the base clip band 26 to
  24 mm (1 failure); the CR30 group moved after Scanner (1); one row's grid
  15x24 to 15x12 (2, the name test and the build test); the hex cut's
  `margin_left` 13 to 15 (2); the CR30 tooltip branch disabled so it falls back
  to "run-up" (1); one `recipe.json` removed from the asset tree (2); and the
  base `margin_right` 26 to 40 mm (all 20 build tests, the two width-exception
  ones included).

  **Two of those nine taught something the family's own numbers hide, and they
  are recorded because they nearly read as a sleeping guard.** Dropping
  `margin_right` 26 to 22, and separately the clip band 26 to 20, each failed
  only the shape test and moved no patch by a micron. The chart area's right
  edge is `max(margin_right, clip_border_width_mm)` and BOTH are 26 in this
  family, so either one alone is masked by the other. Lifting `margin_right` to
  40 does move it, and then every width assertion fires. The note is in the test
  file's docstring so the next person mutating this family does not conclude the
  width check is asleep.

---

### B8-100 · The English source faults the 4.2.0 translation pass turned up, and the Russian dash instruction that was wrong for one language
- blocks release: no
- status: FIXED
- found by: the four translation agents of the 4.2.0 pass (2026-09-06), 14
  reported items; verified against the code and on screen by Agent DA,
  `~/Desktop/beta 9/english-source-faults/FINDINGS-agentDA.md`, which threw
  three out and priced the rest; fixed by Agent DB, whose working is in
  `FIXES-agentDB.md` beside it.
- detail: a translator reads every string in the app one after another, which
  is a review nobody else performs, and it found things no test could see.
  Fourteen English keys were re-spelled, carrying 168 translations with
  them, and 353 more translated values were corrected in place. The ones that mattered:

  **A comma splice that changes what the sentence says at the instrument.**
  `ui/ti2_loader.py` told a CR30 user *"Take the magnetic cap off the measuring
  end first, with the cap on, the CR30 reads its own white tile instead of your
  print."* Read to the first comma it is an instruction; read past it, "with
  the cap on" attaches to taking the cap off. Three more splices in the same
  function and one in the new-chart tooltip went with it.

  **Ten of twelve catalogues sent their reader to a control that is not there.**
  `ui/file_guide.py` names printcal's “Re-calibrate” and “Verify” modes; only
  `ja` and `zh_CN` had translated those two words, so the GERMAN help card said
  „Re-calibrate“ while the combo on screen reads `Nachkalibrieren  (vorhandene
  .cal verfeinern)`. Nothing could catch it: the quotation sits inside a
  577-character help string, so `--missing` and `--stale` see a fully
  translated key.

  **221 values across all twelve languages translated a log tag** while 523 left
  it alone, with `[ERROR]` kept and `[WARNING]` translated in the same log
  widget. The rule that was supposed to catch that had existed all along and
  could not: its pattern was `^\[(?:INFO|OK|WARN|ERROR)\]`, so six of the ten
  tags in use were invisible to it.

  **Russian was told to use the en dash, and the Russian dash is the em dash.**
  All four translation agents were told German and Norwegian use the en dash
  where English uses the em dash, and to apply that everywhere. Right for those
  two, and right for Polish (the półpauza, and its new strings converge on the
  language). Wrong for Russian: measured on the untouched strings, **2,424 em
  dashes to 37 spaced en dashes**, and the pass added 179 more. The Russian
  dash IS the em dash (тире), and it is the copula dash as well, standing where
  English has no dash at all.

  Deliberately NOT done, per DA and re-checked here: the 95 case-only key pairs
  (a button / heading / tooltip-title convention), the 17 curly apostrophes
  (measured harm: zero pairs), the ~25 other prefix quotations that do resolve
  on screen, the six remaining US `color` strings no catalogue ever shows, and
  the French `calibration`/`étalonnage`/`calibrage` split, which is
  pre-existing, was not made by this pass, and is its own piece of work with its
  own reviewer.
- fix: 14 English keys re-spelled with all 12 translations carried across
  (`_IDENTICAL_TO_KEY` and `_BUDGET` re-measured on the merged tree and
  UNCHANGED, which is the proof none were dropped); 221 log-tag values, 24
  quoted control names, 77 Italian `campione`→`tassello` and 216 Russian
  dashes corrected as values only. `ru` joins `ja` and `zh_CN` in
  `_EM_DASH_IS_NATIVE`, with the measurement written above it.
  `docs/design/unified_measurement_management.md` gains a `⚠ REVISED` note on
  M-CR30-CALIBRATE-BLACK (still PROPOSED, still unapproved) and its
  window-sounds table row is corrected to `Unexpected Colour Response`, which
  is what §M already called it.
- evidence: test_no_translation_quotes_a_control_by_its_english_name,
  test_every_pinned_quotation_still_names_a_real_control,
  test_the_detector_can_actually_see_the_fault_it_was_written_for,
  test_russian_keeps_one_dash_and_it_is_the_em_dash,
  test_log_prefixes_are_handled_the_same_way_throughout,
  test_no_new_english_ui_text_uses_an_em_dash,
  test_no_translation_adds_an_em_dash_the_english_does_not_have,
  test_untranslated_values_do_not_creep_in_unseen,
  test_no_string_carries_the_punctuation_a_careless_dash_swap_leaves.

  Four mutations, each proved to land before the run: reverting `ru.json`
  names all 113 keys and replacing every ` — ` in it with a comma drops the
  count to 20 (the two halves of the Russian guard); putting one `[HINWEIS]`
  back turns the log-tag rule red where its old shape stayed GREEN; and
  restoring „Re-calibrate“ to the German catalogue makes both the new quoted-
  label test and the on-screen driver fail by name.

  Driven on the real `MainWindow` in German and in English, sandboxed to
  `/tmp/chromiq-db.ini`: the live Mode combo reads `Nachkalibrieren  (…)` /
  `Überprüfen  (…)` and the folder guide quotes exactly those; the live tick
  boxes read `Seiten (vertikal)` / `Oben/unten (horizontal)` and the ⓘ quotes
  both in full; the live checkbox reads `Auch Scanner-Profilierungsdateien für
  dieses Chart speichern` and the scanner card quotes it in full.
  `defaults read com.chromiq.ChromIQ custom_output_path` is the user's own
  empty value afterwards, as it was before, and `calibration_mode` is still 0
  in the real store while the driver set it in the sandbox.

### B8-101 · The two info frames under the Create Chart preview hugged the panel separator and the window edge
- blocks release: no
- found by: Basti, 4.2.0, on screen: *"In the Create Chart tab under the TIFF
  preview, the left side of the frame around the Measured from Preview section
  touches the panel separator, and the right side of the frame around the Chart
  layout information section touches the right side of the main window. There
  should be a gap."* Reproduced, measured and fixed by Agent DG,
  `~/Desktop/beta 9/create-chart-frame-gaps/FINDINGS-agentDG.md`.
- status: FIXED
- detail: `_info_row` in `ui/tabs/tab_chart.py` carried
  `setContentsMargins(0, 0, 0, 0)`. Both panels are plain `QGroupBox`es and
  `ui/styles.py` gives them `margin-top: 14px` with no left/right margin, so
  their 1 px border is drawn at the widget's own edge and 0 px of layout margin
  is 0 px of visible gap. Measured in the real app with `CompositeAppFilter`
  installed, at 1700x1050: "Measured from Preview" began at x=584 with the
  splitter handle ending at x=584, and "Chart layout information" ended at
  x=1700 in a 1700 px window. Both gaps 0, in en/de/nl, at 900, 1440 and 1700 px
  wide, and with the splitter driven to both extremes. It was the only frame in
  the tab standing off nothing: the left pane's own group boxes sit at x=16 and
  end at x=564, 16 short of the handle at 580..584.
- fix: `_info_row.setContentsMargins(16, 0, 16, 0)`. 16 because it is the tab's
  own inset, already used by `left_layout.setContentsMargins(16, 12, 16, 12)`
  against both the window edge and the separator; with `right_layout`'s existing
  bottom of 12 the two frames now sit 16/16/12, which is the left pane's own
  inset, so the tab is symmetric about the separator. The 8 px channel between
  the two frames (#93) is untouched.

  IT WENT ON THE ROW, NOT ON `right_layout`, and that is the decision worth
  recording. The TIFF preview above them is deliberately full bleed:
  `ui/tiff_preview.py` sets `border-left: none` on the image label and the 4 px
  splitter handle is painted in the very same border colour (`#d0ccc6`,
  confirmed by a pixel scan of the rendered window), so the handle IS the
  preview's left border. Insetting the preview would stand it off a border it
  is wearing. Basti did not report the preview and it has not moved.

  The guard lives in `tests/` as `..._info_frames_do_not_hug_the_pane_edges.py`,
  and the driver that measured all of the above on screen is
  `scripts/drive_dg_create_chart_frame_gaps.py`.

  Width cost, measured because the two earlier frame-gap fixes insisted on it:
  the info row's fit threshold moves by exactly the 32 px added, 1110 → 1142 in
  English, 1203 → 1235 in German, 1245 → 1277 in Dutch. `MainWindow` opens at
  `min(1440, screen.width())`, so all three still fit the default window with
  room. Below that the row was already over-constrained before the change (its
  two panels want 774 px and the right pane can be squeezed to 200), and the
  900 px floor is cramped either way.
- evidence: test_the_left_frame_stands_off_the_panel_separator,
  test_the_right_frame_stands_off_the_window_edge,
  test_the_channel_between_the_two_frames_is_untouched,
  test_the_preview_above_them_still_bleeds_to_both_edges,
  test_both_gaps_survive_the_narrow_window_and_a_splitter_drag.
  Four mutations, four caught, each proved to land on disk: margins back to 0 and margins
  halved to 8 each take the three gap tests; spacing 8 → 0 takes the channel
  test; and moving the margin up to `right_layout` (the plausible wrong fix)
  passes all four gap tests and is caught only by the preview test, which is
  what that test is for. Gate: 11860 passed, 180 skipped, 3 xfailed, exit 0,
  twice, against a baseline of 11855/180/3 — the difference is these five tests.
---

### B8-102 · The scanner and camera window resized itself and moved the radio under the pointer, and its usage-scenario help filled the column
- blocks release: no
- status: FIXED
- found by: Basti, beta 9, two reports on Tools ▸ Build profile with scanner or
  camera: *"when switching the radio for 'create profile using' the window's
  size changes sometimes a bit, things jump around a bit"* and *"the help text
  for the usage scenarios under the 3 radio options is very extensive (which is
  good) but it uses a lot of space there. I'd rather have the detailed info put
  inside the tooltip"*. Measured and fixed by Agent DF; the working, the
  on-screen before/after sheets and the driver's own logs are in
  `~/Desktop/beta 9/scanner-window-steadiness/`.
- detail: **the first report is two faults with different causes**, and neither
  is the one the second report is about.

  **The window resized itself.** `_sync_inline_advanced` rebuilds the Advanced
  section whenever the settings bucket changes, and re-applied the pane width
  for the rebuilt section by calling `_on_advanced_toggled` — the handler for
  the user pressing the disclosure — which ends in `_refit_height()`, which
  ends in `resize(width, max(floor, min(hint, cap)))`. Nobody had toggled
  anything and the window was dragged back to its sizeHint height, throwing
  away whatever height the user had chosen. On the real screen, English, with
  the window dragged to 700 px: one click on "A standard target I own" made it
  **936 px**. German 700 → **952**. "Sometimes" is exact: `_sync_inline_advanced`
  early-returns when the bucket has not changed, so clicking the radio that is
  already on does nothing. The source radio, the "Profile my printer from this
  scan" tick and the printer usage scenario all changed the bucket.

  **The radio moved out from under the pointer.** `_mode_note`, the five-line
  B8-70 explanation of why the printer scenario is not offered for a bought
  target, sat inside the usage-scenario block, ABOVE "Create profile using:",
  and it appears exactly when that question is answered "a standard target".
  Both source radios slid **+79 px** in English (y 280/300 → 359/379) and
  German, **+94 px** in Russian, where the paragraph is six lines.
  `_scenario_note` is the same defect with a different trigger: it is
  re-evaluated on every source switch and is 38 px in English, 53 in German and
  Russian, so it appears and vanishes on that click for anyone who has saved
  defaults for one bucket and not the other.

  **The glosses.** Three paragraphs under three radios: 45 + 60 + 45 = 150 px in
  English, on top of the radios themselves, in the column
  `USAGE-SCENARIO-DESIGN.md` §6 had already measured as full.
- fix: three parts, and one repair to something they uncovered.

  1. `_show_the_advanced_section` is split out of `_on_advanced_toggled` and
     does not refit the window's height; `_sync_inline_advanced` calls that
     instead. `_refit_height` stays on the disclosure the user really pressed.
     Nothing is lost: the left column is a scroll area, so a bucket whose
     Advanced set is taller scrolls.
  2. The two notes move to a strip below BOTH radio groups. **Reserving the
     space was considered and rejected**: held open permanently the pair costs
     113 px of blank in English and 143 in Russian, it would read as the gap
     B8-73 was about, and
     `test_the_standard_target_explanation_sits_against_the_rows_around_it`
     requires `_mode_note` to be exactly as tall as its own text anyway. Neither
     note's TEXT changed, so all twelve translations came across, and
     `_mode_note`'s closing *"Choose “A chart I made in ChromIQ” instead"* now
     points at the line directly above it.
  3. Each gloss is one line, levelled against the other two (`_LevelHint`) so a
     translation that wraps cannot move the block in one language alone. The
     full text is not rewritten for the ⓘ, it is MOVED: `_scenario_help`
     composes the tip body from the same `tr()` literals the glosses carried, so
     no key went stale and only 4 keys are new (three one-line glosses and the
     heading above them). §7 of the design named the cost of this
     (*"the reader learns why without asking"*), so both clauses that make the
     three read as a sequence survive into the one-liners.
  4. **And the fix uncovered a latent width fault.** "Opening Advanced never
     widens the window" was being held by accident: the gloss paragraphs were
     wide enough in all thirteen catalogues to absorb whatever the Advanced
     editor needed. One-line glosses stopped paying for it and five languages
     started widening on a disclosure (German 36 px, Italian 54, Dutch 42,
     French 5, Spanish 1). `_measure_advanced_width` now raises `_pane_w_closed`
     to match, which the old note there had rejected as costing every user
     width. Measured, it costs nothing: the pane is **narrower in every
     language than it is today** even so (de 709 → 662, it 707 → 663,
     nl 681 → 661, fr 706 → 668, es 697 → 679, the rest unchanged).

  On screen, English and German, before and after, at the height the window
  opens at and at 700 px: window +0 px, every radio in both groups +0 px.
- evidence: test_pressing_a_radio_moves_neither_the_window_nor_a_control,
  test_a_bucket_change_does_not_refit_the_windows_height,
  test_no_note_can_push_a_radio_because_none_is_above_one,
  test_the_glosses_are_one_line_with_the_detail_behind_the_info_button,
  test_the_worst_languages_fit_a_1280_screen,
  test_every_language_fits_a_1280_screen

### B8-103 · Knut's six straight-strip CR30 charts, and the test that held them for a day by measuring the wrong axis
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-12, attaching `New presets CR30-streight.zip` to
  issue #182: *"I made 6 new presets for CR30, to be added in the same way as
  the other built-in presets"*. Confirmed on beta 7 the next day: *"all 6
  profiles give no warnings at all... show top=12.3mm and bottom = 6.9mm in
  Measured from Preview. All ok. Ship the presets."*
- detail: three things, and the middle one is the reason this entry is long.

  1. **The charts.** The same 11 mm honeycomb as his hexagonal CR30 cut, turned
     30 degrees, so a strip runs straight down the sheet instead of zig-zagging
     under the hand. Six exports, three on A4 (450 / 900 / 1350 patches) and
     three on US Letter (396 / 792 / 1188), all on one 18-column grid. Against
     the hexagonal cut they move seven fields and nothing else, so they are a
     CUT (`_CR30_STRAIGHT`, `straight=True`) rather than six charts, and
     `scripts/import_knut_presets.py` learned a second overlay so the rows are
     still generated and validated rather than typed.

  2. **They were built on 2026-09-13 and commented straight back out**, because
     `test_no_builtin_preset_breaks_its_own_declared_margins` reported the three
     A4 charts at Top 10.499 / Bottom 5.112 against the 11.0 / 6.0 their own
     recipe declares. Knut, on the same charts on beta 7, read 12.3 and 6.9 with
     no warning. Both numbers were produced honestly and only one of them came
     from the app: the test file re-implemented
     `margin_inspector.measure_from_engine` in a local helper, and the copy had
     drifted. The shipped function asks `recipe_is_flat_top` which way the
     hexagons point; the copy always took the vertical apex. A turned
     honeycomb's apexes point sideways, so the copy moved 1.82 mm off the top
     and bottom and left 1.59 mm on the left and right that the ink does not
     have. Fed the engine's own geometry, the shipped function answers 12.319
     and 6.932 — Knut's reading to the tenth. The helper now CALLS it, so the
     copy cannot drift again.

  3. **And measuring them turned up a real one.** "Patch width (in strip
     reading direction)" came off the slot rect's `w`. On an upright honeycomb
     that is the patch: the flats are its left and right sides. On a turned one
     `w` is the COLUMN PITCH, and the patch is 4/3 of it across the points and
     `h` across the flats. The panel showed 9.4 mm for a 10.9 mm patch on charts
     whose own names say 11 mm — 14 % short, on the one readout that tells a
     CR30 owner whether its round head fits inside a patch. The report now
     carries the across-flats measure in both orientations, which is the
     inscribed circle and the only span worth one number. Nothing upright moves.
- evidence: test_twenty_six_charts_registered,
  test_the_straight_cut_is_the_hexagonal_one_turned_and_six_numbers,
  test_name_matches_the_bundled_patch_set_and_the_grid,
  test_chart_builds_with_the_pages_and_patches_its_name_promises,
  test_no_builtin_preset_breaks_its_own_declared_margins,
  test_a_turned_hexagon_reports_the_distance_between_its_flats,
  test_the_reported_width_is_the_biggest_circle_that_fits_the_drawn_patch,
  test_an_upright_honeycomb_still_reports_what_it_always_did,
  test_a_rectangular_chart_is_untouched.

  The patch-width fix was mutation-proved: with the flat-top branch deleted and
  `__pycache__` purged, the first two of those fail with "reported 9.398 mm; the
  patch measures 10.922 mm across its flats" and the other two stay green.

### B8-104 · The chart's PDF export lost the strip-label underline entirely at a thin setting
- blocks release: no
- status: FIXED
- found by: this session, 2026-09-13, while answering Knut's question *"Which
  PDF export is this? from the Measurement Report? or any other export? If the
  Measurement Report, I say we keep as is."* It is not the report: it is Create
  Chart's "Also export a PDF", the chart itself, so his keep-as-is does not
  apply and the sheet a RIP may print was missing a rule the TIFF has.
- detail: one display list feeds the TIFF and the vector PDF, so they are the
  same chart in two forms. A `vrect` row is HALF-OPEN, like a Python slice, and
  the PDF writer takes `x1 - x0` by `y1 - y0` as the size. The helper markers
  emit half-open rows; the three strip-label underlines wrote Pillow's
  INCLUSIVE box straight in, so every rule came out one pixel short in both
  dimensions. Two emitters, two conventions, one consumer that cannot be right
  for both.

  Measured on a real export at 200 dpi with the rule at 0.10 mm: **1**
  zero-height rectangle in `black` mode, **5** in `segments`, **18** in
  `cycle` — the rule is in the TIFF and absent from the PDF. At 0.50 mm nothing
  vanished and every rule was a quarter thin instead, 1.08 pt against the
  TIFF's 1.44. After the fix: 0 dead rectangles in all three modes, and
  0.36 pt / 1.44 pt, which is exactly 1 px and 4 px at that resolution.

  `raster._ul_geom_rect` is now the only place that converts, and a test reads
  `render_pages`'s source to keep a fourth emitter from picking the other
  convention.
- evidence: test_no_rule_in_the_pdf_has_no_size,
  test_the_pdf_rule_is_exactly_as_thick_as_the_ink_on_the_tiff,
  test_the_converter_is_the_only_place_that_knows_the_convention.

  Mutation-proved: with the converter returning the inclusive box again and
  `__pycache__` purged, six of the ten fail with the counts above.

### B8-105 · Knut's text-and-margin batch of 2026-09-13: four built, one measured and held
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, testing beta 7. Five faults in one post, plus two
  more in the two posts after it.
- detail: K1 the clip-text warning fired when nothing was hit; K2 the messages
  that name the 7 pt floor did not say it belongs to "auto"; K3 the note-length
  warning measured the notes box while the sheet printed the joined line; K4 a
  clip line too long for the page was cut at both ends in silence; K5 the gap
  between the note and the clip text is not one line's leading. K6 (the six
  scanner presets warning about their own margin) is in the same batch and is
  fixed; K7 (their sluggishness) is open.

  **K5 IS MEASURED AND NOT BUILT, and the reason is worth the paragraph.**
  Fixing its first part alone was tried and measured: the note is then sized
  correctly, 3.429 mm of ink instead of 2.286, which is 10 pt instead of 7, and
  the white gap becomes **0.254 mm**, worse than the 2.286 it replaced, because
  the packing path is wrong too. Half of it would make the gap he reported
  narrower, so it is held whole. Everything measured for it, and the three
  parts it needs, is in §2q of `docs/design/issue_182_answers.md`.
- evidence:
  K1: test_a_wider_margin_than_the_band_says_nothing_at_all,
  test_it_still_warns_when_the_text_really_does_reach_the_patches;
  K2: test_auto_gets_the_sentence_and_a_typed_size_does_not,
  test_the_floor_is_read_from_the_constant_and_never_typed_into_the_text,
  test_every_message_that_prints_the_floor_appends_the_sentence,
  test_no_shipped_message_still_says_it_is_already_at_its_smallest,
  test_the_two_tooltips_name_the_floor_that_is_actually_in_force;
  K3: test_the_stamper_and_the_panel_ask_the_same_function,
  test_the_stamp_turns_a_silent_truncation_into_a_warning,
  test_the_count_it_names_is_within_a_character_of_the_sheet,
  test_the_patch_count_reaches_the_targen_line,
  test_the_stamp_is_offered_as_a_lever_only_while_it_is_on;
  K4: test_a_long_line_at_the_auto_floor_is_reported,
  test_a_typed_size_never_shrinks_so_it_loses_more,
  test_a_line_that_fits_says_nothing,
  test_the_predicate_allows_exactly_what_the_renderer_allows;
  K6: test_no_builtin_preset_breaks_its_own_declared_margins.

  Every one mutation-proved, and each fix driven on screen in a real window
  before and after: the K1 matrix (five combinations, two flipped and three
  unchanged), Knut's own A3-900p at clip 18 now reading "Margins: OK" in green,
  the K2 message read off the panel, the K3 combinations (37 and 236 characters
  cut where the panel had said nothing and 128), and the K4 pair (331 mm needed
  against 288, and a line that fits saying nothing).

### B8-106 · Selecting a scanner preset took eleven and a half seconds, and it was arithmetic
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13: *"all the scanner presets are very very slow to
  load (probably due to the number of patches) and every single click of
  change, like altering a margin number, takes a long time. I think this was
  not a problem some time ago... The sluggishness does not happen to other
  large charts, like the red river charts or other charts with more than 3000
  patches."*
- detail: he is right that it is not the patch count. Profiled, seeding one
  built-in in a real tab:

        Scanner A4-3430p     11,723 ms    17,794 calls to `strips()`
        Red River A4-2052p      190 ms       369
        CR30 A4-1350p           262 ms       369

  The scanner family is the only one laid out `by_width` with no column count,
  so `area_fit.derive_area_patch_size` tries every column count a 4 mm minimum
  allows, about sixty-five of them, and each try binary-searches the patch width
  over a real provisional geometry. Three things were wrong with that, and none
  of them is the search:

  1. **the same answer eight times for one click.** Selecting a preset refreshes
     the command preview and the layout estimate several times over and each
     refresh asks again. The function is pure in its kwargs, so the repeats are
     free to remove. The key is the whole of the kwargs, and a kwargs dict that
     will not serialise is simply not cached rather than guessed at;
  2. **every column candidate started its own search on the same interval**, so
     the probes repeated. One memo now spans the derivation;
  3. **a fixed FORTY halvings**, which on a 300 mm interval resolves the patch
     width to 3e-10 mm. One pixel at 1200 dpi is 0.021 mm. It stops at
     `_FIT_RESOLUTION_MM` = 1e-4 mm instead, which is 0.005 px at 1200 dpi.

  **No arithmetic changed.** Checked over all 147 recipe-carrying built-ins: the
  derived `(patch_w, patch_h)` is IDENTICAL, and the sweep took 4.6 s instead of
  9.6.

  Measured after: the scanner preset seeds in **544 ms** against 11,723, the
  Red River one in 27 ms against 190, the CR30 one in 32 ms against 262. Driven
  on screen, all six scanner built-ins loaded and measured: **32 s against
  2 m 35 s**, all six still "Margins: OK". The everyday tier itself went from
  174 s to 119 s.
- evidence: test_the_resolution_is_far_finer_than_the_pixel_it_becomes,
  test_stopping_early_gives_the_same_answer_as_grinding_on,
  test_the_answer_is_remembered_and_is_the_same_answer,
  test_the_memory_cannot_hand_one_chart_another_chart_s_size,
  test_a_recipe_the_key_cannot_describe_is_simply_not_cached,
  test_the_search_does_not_grind_past_the_resolution,
  test_the_slow_family_is_no_longer_slow.

  Two mutations, each proved to land: deleting the memo fails the remembering
  test, and deleting the early stop fails the geometry census (2,235 builds
  against 4,309). The census exists because the wall-clock test was written
  first and the mutation walked straight through it: forty halvings is 1.66 s
  and the bound was 4 s.

### B8-107 · Something writes a 100 MB chart TIFF into a bare temp folder and nothing sweeps it
- blocks release: no
- status: OPEN
- found by: this session, 2026-09-13, checking the disk after a day of gates and
  drivers: **680 folders under the system temp directory, each holding exactly
  one file called `s.tif` and nothing else, 33.6 GB in total**, all written
  today.
- detail: one was opened before anything was deleted. It is a 4961 x 7016 RGB
  TIFF at exactly 600 dpi, written by `tifffile` with the default
  `ImageDescription` of `{"shape": [...]}`, which is an A4 ChromIQ chart render
  and nothing else. The 680 were removed by a rule that matched only that exact
  shape (one file, named `s.tif`, alone in the folder).

  **The sweeper cannot see them, and the reason is honest.**
  `tests/conftest.py::_is_chromiq_temp` recognises a folder by a file only this
  suite writes: a `.ti1`, `.ti2`, `.ti3`, `.cht`, `.cie`, `.icc`, `.cal`, a
  `project.json` or a `meta.json`, or a chart-probe folder NAME. A folder
  holding one `.tif` matches nothing, and `.tif` is far too common a suffix to
  add: a false positive deletes another application's data.

  **The writer was not found.** `tempfile.mkdtemp()` with no prefix appears in
  eight test files, and every one of them also writes a `.ti1` beside the TIFF,
  so the sweeper already sees those. The tests that do write an `s.tif`
  (`test_scanner_multidpi.py`, `test_scanner_synthetic_e2e.py`) use `tmp_path`,
  which pytest cleans, and write a `.cht` and a `.cie` beside it. So the source
  is something else, and looking for it is the next step rather than widening
  the sweeper's marker list.
- who: nobody yet. Basti or whoever picks up the next round.

### B8-108 · The IMAGE-detection margin path still reports a turned honeycomb's column pitch
- blocks release: no
- status: OPEN
- found by: the adversary round of 2026-09-13, checking that today's
  patch-width fix reached everything: same chart, same files,
  `measure_from_engine` **10.922 mm** and `measure_margins` **9.638 mm**, which
  is the column pitch.
- detail: `measure_from_engine` reports the across-flats measure in both
  orientations now. `measure_margins` is the fall-back for a chart with no
  `channels.json` (a chart reflected from a `.ti2` alone), so it has no recipe
  and cannot know which way the hexagons point: it divides the block width by
  the strip count, which IS the patch on every rectangular chart and on an
  upright honeycomb, and is the pitch on a turned one.

  Guessing an orientation from the bitmap is exactly the kind of inference this
  module was rewritten to stop doing (#93: the image detector read the patch
  width as the strip pitch and a large strip gap corrupted the margins, which
  is why the engine path exists). The limit is written into
  `_estimate_patch_width_mm`'s docstring instead; whether the fall-back should
  learn the orientation from the `.ti2`, or say "estimated" on that row, is a
  design question.
- who: nobody yet.

### B8-109 · The adversary round of 2026-09-13, and the two claims it corrected
- blocks release: no
- status: FIXED
- found by: the adversary round run against `9273a91d` before tagging beta 8.
  Eight drivers, sixty-nine photographs, every one on screen in a real window.
- detail: five findings, four fixed here and one registered as B8-108.

  **F1 — the new clip-line length check covered one of the two modes that draw
  a croppable line.** With "Clip-border content" set to *Imported image* and a
  298-character caption at a typed 9 pt, the renderer drew 434.79 mm of line
  into a 287.61 mm canvas and cut **147.18 mm, 73.59 at each end**, and the
  panel said "Margins: OK". The identical text under *Custom text* warned.
  `render_clip_strip` puts the same `clip_text` through the same `_vtext` in
  image mode, which is Knut's own #164 ruling. Fixed; "branding" is left out on
  purpose, because its extra lines go through `_vwordmark`, a different
  renderer with a different fit.

  **F2 — both "6 GREEN" claims held only on the owner's preferences, and my own
  commit messages said otherwise.** On a fresh sandbox the six straight presets
  are 6 RED and the six scanner ones 2 GREEN / 4 RED, every red one a notice
  about "chart notes" with an empty notes box. The app ships with "Stamp
  settings down the right edge" ON and no recipe can clear it. The line IS
  there and it DOES land on the patches, so the warning is right; it was wrong
  about whose text it was. The empty-box case now has its own message that says
  the line is the settings stamp and names the tick that removes it.

  Renaming the subject of the four existing messages was tried first and
  withdrawn: "the chart notes" is plural and carries the agreement of every
  verb after it, so a one-line substitution produced *"the text ... share that
  edge ... they are printed ... the notes are printed anyway"*, in thirteen
  languages at once. A separate branch has no grammar to break.

  **F3 — the two controls the right-edge warnings are about never refreshed the
  panel.** Counted: toggling the stamp tick, 0 refreshes out of six tries;
  typing a 336-character note, 0. So the warning arrived a rebuild late and
  clearing the notes left the red message standing. Both now refresh, guarded
  on there being a chart to measure.

  **F4 — three messages printed "7 pt" without saying the floor belongs to
  "auto"**, which is the thing Knut asked for that morning: the note-too-long
  pair and the clip-band pair. The shared sentence named "Sheet text", so the
  clip pair needed its own, naming "Clip-border content".

  **What it could NOT break**, re-measured its own way: the PDF rectangles
  (90 / 94 / 107, 0 dead, and 1 / 5 / 18 dead when it mutated the converter
  back), the turned hexagon (12.573 across the points, 10.880 across the flats,
  24 of 24), K3's character counts (0/0, 41/41, 134/134, 242/242 against the
  fitter wrapped during a real build), K1 on both bands with every lever
  exercised, all six straight presets built for real, and the scanner-margin
  fix.
- evidence:
  test_the_two_controls_leave_the_measured_frame_alone, test_an_imported_image_s_caption_is_checked_too,
  test_the_branding_mode_is_left_alone_on_purpose,
  test_an_empty_notes_box_is_never_blamed,
  test_a_typed_note_still_gets_the_per_lever_wording,
  test_the_stamp_is_on_by_default_and_no_recipe_can_clear_it,
  test_it_does_nothing_at_all_when_there_is_no_chart_to_measure,
  test_every_message_that_prints_the_floor_appends_the_sentence,
  test_the_stamp_settings_tick_box_is_enough_on_its_own.

  Four mutations, each proved to land: narrowing the length check back to
  "text" only, deleting the empty-notes branch, deleting the refresh, and
  sending the floor sentence to a typed size.

### B8-110 · The report window told a user their verdict had been lost, on a file that never had one
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, on the beta 8 demo pack.
- evidence:
  test_the_column_is_marked_fresh,
  test_the_page_does_not_say_an_old_version_lost_the_verdict,
  test_the_judged_against_cell_does_not_read_not_recorded;
  and the other half, which must stay green when the three above go red,
  test_a_report_that_really_is_old_is_still_named_as_one.
  Mutation: remove the `_fresh` marker from `_load_runs`'s last resort.
  Driven on screen with `scripts/drive_182_profiling_sheet_verdict.py`.
- evidence: `test_a_report_never_saved_is_not_blamed_on_an_older_chromiq.py`,
  four tests. `test_the_column_is_marked_fresh`,
  `test_the_page_does_not_say_an_old_version_lost_the_verdict` and
  `test_the_judged_against_cell_does_not_read_not_recorded` go red when the
  `_fresh` marker is removed;
  `test_a_report_that_really_is_old_is_still_named_as_one` stays green, which
  is what stops the fix silencing both cases. Driven on screen with
  `scripts/drive_182_profiling_sheet_verdict.py`.

Knut, 2026-09-13, on `Report-Limits-Custom-Columns` from the beta 8 demo pack:

> The statemend "It was saved by a version of ChromIQ that did not yet keep the
> verdict together with the measurements, so no PASS or FAIL of its own was
> stored for it." seems wrong.

It was. Reproduced on screen before anything was touched, in a real 1152x977
window: the column read `recorded=False`, "Judged against: not recorded", and
the sentence he quoted, on a measurement with **no saved report on disk at
all**.

**The sheet he opened is the run's own profiling chart**, not one of the pack's
dated verifications. His column header gave it away: 2026-09-13, the day he
unpacked the zip, where every verification in that project is dated 2027.
ChromIQ saves a report under a dated verification folder, and the demo pack
saved none beside the sheet a profile was built from, so `_load_runs` fell
through to its last resort, which builds the report there and then.

Of the three branches that can produce a column, only that one did not set
`_fresh`. And `_recorded(r) is None and not r.get("_fresh")` is precisely the
state the window reads as "an older ChromIQ saved this and stripped the
verdict". Nothing had been saved, so nothing could have been lost.

Both halves are pinned: a live-built column must be marked fresh, and a report
that really was saved without a verdict block, which is what a pre-#182
ChromIQ wrote, must still be named as one. A fix that silenced both would have
been a second fault wearing the first one's clothes.

`tests/test_a_report_never_saved_is_not_blamed_on_an_older_chromiq.py`, four
tests. Mutation: remove the `_fresh = True` and three of them go red while the
fourth, the old-report one, stays green.

### B8-111 · The demo package shipped 23 measurements with no verdict beside any of them
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, in the same comment as B8-110.
- evidence:
  test_the_exact_pack_that_shipped_is_caught,
  test_the_project_list_is_what_decides,
  test_a_pack_with_no_verdict_beside_a_measurement_is_incomplete,
  test_the_zip_and_the_folder_are_the_same_check;
  plus `python scripts/make_report_limit_demos.py --verify <pack>` run on the
  artefact itself, which names the shipped pack incomplete and the rebuilt one
  complete, as a folder and as a zip.
- evidence: `test_a_demo_pack_ships_every_project_it_declares.py`, plus
  `python scripts/make_report_limit_demos.py --verify <pack>` run on the
  artefact: the pack that shipped is named incomplete and the rebuilt one
  complete, as a folder and as a zip.

Knut, same comment:

> Make sure all verdicts exist in the demo package.
> Why is the verdict and measurements not kept as part of the demo data
> created, so that it is a real test?

`tab_measure._maybe_save_measurement_report` runs after EVERY measurement the
app makes, the profiling read included, so a project built with "Save a
measurement report after each measurement" ticked holds a report beside the
sheet the profile was built from. The generator saved one only under each
dated verification. Across six projects that is 23 runs with nothing beside
their own measurement, which is what put him on B8-110's path in the first
place.

The profiling measurement is now dated seven days before its first
verification, which is the order the two really happen in, and carries a
stamped verdict against the run's own limit set. Undated, its column was
headed with whatever day the package was unpacked.

**AND THE CHECK IS ON THE ARTEFACT, NOT ON THE GENERATOR.** `verify_pack`
gained `_verdicts_missing`, which walks the built pack (folder or `.zip`) and
requires a saved report carrying the block `recorded_verdict` reads beside
every measurement, skipping only the role-named intermediates that never go on
paper. Run against the pack that shipped, it named all 23 gaps by path; against
the rebuilt one it reports complete, folder and zip. A check that read the code
that built the pack would be the baseline-against-itself fault this project has
already paid for twice.

### B8-112 · The layout stamp is a bottom line and nothing measured its width
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, testing beta 8.
- evidence:
  test_the_bottom_lines_include_the_stamp,
  test_the_stamp_alone_is_given_a_width,
  test_the_overflowing_stamp_is_reported,
  test_it_does_not_matter_which_side_the_border_is_on,
  test_the_message_names_the_tick_and_not_the_empty_text_box,
  test_a_long_custom_line_is_still_blamed_on_the_text,
  test_nothing_is_said_when_both_lines_are_off;
  and for the placeholders, test_the_bottom_line_is_measured_resolved,
  test_every_clip_text_call_site_resolves_first,
  test_a_seed_of_zero_is_a_seed.
  Mutation: put the gate back to `if r.chart_text:`.
  Driven on screen with `scripts/drive_182_bottom_stamp_warning.py`, which
  renders the sheet and measures the stamp's own ink rather than trusting the
  panel's prediction.
- evidence: `test_the_bottom_stamp_is_measured_like_the_text_beside_it.py` and
  `test_a_placeholder_is_measured_as_it_prints.py`. Mutation: putting the
  gate back to `if r.chart_text:` turns the four warning tests red.
  Driven on screen with `scripts/drive_182_bottom_stamp_warning.py`, which
  renders the sheet and measures the stamp's own ink rather than trusting
  the panel's prediction.

Knut, 2026-09-13, testing beta 8:

> When using "Stamp layout information along the bottom" (and no custom text)
> with font size 13 or 14 makes text that cross into the right clip-border
> text, but no warning is given. This happens regardless of the clip-border is
> on left of right side.

The bottom of a sheet carries up to two lines: the custom "Sheet text" and the
layout summary. `raster.render_pages` builds them as one list and shrinks the
PAIR against the room between the two side bounds. The panel's HEIGHT check
counts both and always did. Its WIDTH check asked `if r.chart_text:` and
measured that string alone, so with the stamp on and the text box empty the
check never ran, and with both on it under-measured whenever the stamp was the
longer line.

**A guard on one door and not the identical door beside it, thirty lines
apart.**

The stamp's text is predicted from `chart.stamp_summary_line`, lifted out of
`build_chart` so the panel asks the shipped function rather than carrying a
second copy of the f-string. Two of its values are not known while the panel is
being typed into: the patch count, which `_estimate_patch_total` answers with
the same question Generate asks, and the seed, drawn at build time and stood in
for by the widest one `pick_seed` can return.

Measured on screen, on the ColorMunki `A4-84p-1page-Portrait-w26.0mm` engine
preset, clip border on each side:

| Size | line | room | overflow | panel |
|---|---|---|---|---|
| 12 pt | 166.9 mm | 179 mm | none | quiet |
| 13 pt | 182.1 mm | 179 mm | 3.13 mm | warns |
| 14 pt | 197.3 mm | 179 mm | 18.32 mm | warns |

His 13 and 14, his both-sides, and his 12 as the control. And the message names
the tick rather than offering to shorten text nobody typed: *"The widest line
down there is the layout summary, not text you typed. Switching “Stamp layout
summary along the bottom” off removes it."*

**THE DRIVER WAS WRONG FOUR TIMES BEFORE IT WAS RIGHT**, and each way of being
wrong measured something other than the case: it never set a project name, so
the preset asked for one and the blanket QMessageBox stub answered no; it
waited for the `.ti2` and not the TIFFs, so the patch count was unknown and the
stamp line was four characters short; it took the FIRST ColorMunki preset in
the dropdown, which is a printtarg one, where `_engine_text_notes` returns at
its first line and the panel is silent for a reason that has nothing to do with
this fault; and it pushed the recipe with `set_recipe`, which is the app
filling the panel and deliberately does not set off a keystroke's refresh, so
the numbers said the message was there and the photograph showed the panel on
the previous state.

### B8-113 · A question with one OK button
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, testing beta 8.
- evidence:
  test_ask_offers_yes_and_no_and_defaults_to_no,
  test_an_explicit_button_set_is_still_honoured,
  test_the_real_ask_returns_no_when_no_is_clicked,
  test_declining_keeps_the_text_the_user_typed,
  test_accepting_really_does_load_the_example,
  test_an_empty_box_is_not_asked_about.
  Mutation: drop `ask`'s button default.
- evidence: `test_a_question_offers_a_way_to_say_no.py`, five tests, including
  one that drives the real `ask` through the real `_boxed` rather than a
  stub. Mutation: dropping `ask`'s button default turns it red.

Knut, same comment:

> for Clip-border content frame, if I choose Custom text example option in
> Content input box, then a window appears saying "Replace the current
> clip-border text with the example table?", but the window has only OK button,
> so I am not given the choice to NOT replace the text.

`warning_sign.ask` took its button set from `_boxed`, which it shares with
`warn` and `inform`, and their default is a single OK. Worse than either
outcome: the caller compares the answer against `Yes`, and OK is not Yes, so
the only button on screen fell through to the branch that replaces the text.
The user's record went whichever way they answered a question with one answer.

Yes and No now, with **No as the default button**, so a stray Return keeps what
was typed. Both halves are tested, because a fix to either alone leaves the
fault reachable: `ask` must OFFER both, and the call site must ACT on No.

### B8-114 · The adversary round of 2026-09-13 evening, and the two false warnings it found in that afternoon's fix
- blocks release: no
- status: FIXED
- found by: the adversary round run against `e062df83` before tagging beta 9.
  Four drivers, all on screen in real windows, plus rendered sheets.
- evidence:
  test_a_seed_of_zero_is_a_seed,
  test_an_absent_seed_is_never_predicted_wider_than_it_can_be,
  test_the_bottom_line_is_measured_resolved,
  test_every_clip_text_call_site_resolves_first,
  test_the_remedy_is_only_offered_when_it_works,
  test_the_placeholder_context_can_never_silence_the_panel,
  test_a_verdict_with_no_rows_in_it_does_not_count,
  test_the_zip_and_the_folder_are_the_same_check,
  test_a_calibration_measurement_is_judged_like_any_other,
  test_the_real_ask_returns_no_when_no_is_clicked,
  test_the_build_stamps_that_exact_line_and_not_another.
- detail: ten findings. **Two of them were regressions introduced by B8-112
  the same afternoon**, which is the entire reason the round is run.

  **F1 — the register was red.** B8-110 to B8-113 carried no `blocks release`,
  no `status` and no `evidence`, so `test_beta8_nothing_is_forgotten` failed and
  the everyday tier with it. The checklist caught the checklist.

  **F2 — a fixed seed of 0 produced a FALSE WARNING.** `getattr(r, "seed",
  None) or _WIDEST_SEED` treats 0 as "no seed", so a recipe carrying seed 0 was
  predicted as ten digits where the sheet prints one. Reachable by ticking "Use
  a fixed seed" and never pressing "New seed". Rendered and measured: at 13 pt
  the panel said 3 mm ran off and the ink stopped 10.61 mm inside the bound; at
  14 pt it said 18 mm where the sheet had 4.14 mm to spare.

  **F3 — and the worst-case stand-in was the wrong bias.** `pick_seed` draws ten
  digits 53 % of the time and nine the rest, so predicting the widest possible
  seed is one character too wide almost half the time, and one character is
  2.71 mm at 13 pt on Inter. Nine digits is either exact or one short, never
  long. A warning that is wrong about the sheet in front of the user is worse
  than one that arrives a character late.

  **F4 — the panel measured `{tokens}` and the sheet prints the answer.** On
  Knut's own example line, 12.6 mm at 12 pt; `{seed}` alone is 23.3 mm wider
  resolved and a long chain of token names 11.3 mm narrower, so the check could
  miss a real overflow AND invent one. `chart.text_placeholder_context` and
  `raster.resolve_placeholders` are lifted out and the panel asks them. THREE
  `clip_text_lines` call sites, not one.

  **F5 — "0 patches" out of the box.** With "Auto patch count" ticked, which is
  how a fresh Manual panel opens, `_estimate_patch_total` answers None and the
  stamp was predicted as "0 patches" while the sheet stamps the real figure:
  4.6 mm of line on a 918-patch chart. The Chart-layout-information panel had
  already computed it for its own column.

  **F6 — a remedy that changed nothing.** The sentence naming the stamp tick was
  appended whenever the stamp was the WIDEST line, so with a long custom line as
  well it could be right about that and useless: rendering with the stamp off
  left the sheet 19.61 mm over at 13 pt and 23.93 at 14, unchanged. It now asks
  whether removing the stamp makes what is left fit.

  **F7 — `_verdicts_missing` passed a hollow pack.** `recorded_verdict` requires
  only that `rows` is a list, so `{"verdict": {"rows": []}}` counted as a
  verdict.

  **F8 — its folder branch and its zip branch were different checks.** The
  folder branch skipped the role-named intermediates and the zip branch skipped
  nothing, so a pack holding a run that used measurement averaging passed as a
  folder and failed as a zip; a `.ti3` at the root of a zip could never find its
  report. One listing serves both now, and `cal/` is deliberately not skipped.
  The count of missing verdicts is **23**, not the 25 written three times.

  **F9 — the driver did not do what its commit message said.** It fed the
  panel's own prediction into `text_edge_fit` and called that independent.
  Getting the replacement right took three attempts, all recorded in the
  driver's own docstring: differencing a stamp-on against a stamp-off render
  moves the whole chart because `nlines` takes the bottom reserve with it;
  cropping the clip-border columns away hides the overflow being measured; and
  the right bound is `room + clip` only with the border on the RIGHT.

  **F10 — two tests guarded nothing.** The stamp-wording test never called
  `build_chart` and re-derived its expected value from the functions the
  implementation calls. The `ask` tests stubbed either `_boxed` or `ask` in
  every case. The round's own mutation for the second could not have been
  caught either: `StandardButton` is an `IntFlag`, so `int(No) == No`. A
  mutation that does change behaviour turns it red now.

  **And a hazard the round exposed without naming it.** `_engine_text_notes`
  wraps its whole body in one `except Exception: pass`, so a lookup that throws
  loses EVERY warning on the panel, silently. It did: 37 tests reported "no
  clip-text warning at all" for a chart that has one, accusing correct code.
  The context builder cannot raise now, the stand-in tab borrows the real
  methods instead of re-implementing a subset, and a test feeds it a recipe
  that answers badly to everything.

### B8-115 · Knut's beta 9 batch: one warning, five things wrong in it
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, testing beta 9 with a ColorMunki preset, a 24 mm
  clip border and a 31.5 mm right margin.
- evidence:
  test_the_margin_binds_the_side_the_clip_border_is_on,
  test_it_applies_whichever_side_the_border_is_on,
  test_a_narrower_margin_changes_nothing,
  test_his_own_worked_example_still_gives_202_mm,
  test_the_room_and_the_overflow_both_take_the_margins,
  test_the_renderer_uses_the_same_bounds_and_the_same_anchor,
  test_a_typed_size_is_not_described_as_a_shrink_that_stopped,
  test_no_message_still_claims_a_typed_size_stopped_shrinking,
  test_the_auto_case_still_says_where_shrinking_stops,
  test_a_chart_layout_name_replaces_the_targen_line,
  test_the_prediction_sets_the_layout_name_the_build_sets.
  Three mutations, each proved to land. Driven on screen with
  `scripts/drive_182_knut_beta9_case.py`, and the notes' ink measured on a
  sheet stamped by the real stamper.
- detail: he read one warning and answered it in five parts, and every part
  was right.

  **F1 and F2 are one fault: the panel measured a line the sheet does not
  print.** Measured before anything was touched, by rendering his sheet and
  running `stamp_chart_metadata` on it: the notes' ink ran **24.51 mm to
  276.61 mm** on a 297.05 mm page, so 24.5 mm of clear paper above it and
  20.4 below (his 1), and all **127 characters** were drawn with no ellipsis
  at any strip width the stamper could have used (his 2).

  The cause is one missing line. `_generate_from_ti1` sets
  `params.chart_layout_name`; `_collect_manual()` does not. With a patch set
  armed targen is never run, so `stamp_lines` prints "Chart layout <name> |"
  and the panel predicted "targen -d2 -f612 -e1 -B1 -G test". On his preset
  that is 143 characters predicted against 187 built. The prediction asks
  `_active_layout_name()` now, the same method the build asks, and driven on
  screen the two lines came out identical.

  **F3 and F4 are one fault too: the bottom line was bounded by the border and
  not by the margin.** His words: *"When right margin is larger than
  clip-border width: the largest value of them should define the
  side-positions that are used for centring the bottom text."* Measured on his
  sheet: bounds of (7.0, 186.0) from the border alone, a right margin whose
  own text column starts at 178.5, and a 172.9 mm line centred between them
  running to 182.95, so 4.45 mm of it printed inside the column the right-edge
  notes live in. He read the warning as being about the notes, which is what
  it said, and it was the bottom line that had moved.

  **AND IT REGRESSES NO SHIPPED CHART.** The new bound only bites where a
  margin is wider than the clip border on the border's own side, which is a
  hand-edited state: checked over all **143 recipes shipped in `assets/charts`,
  zero** have their bottom-line room narrowed by one hundredth of a millimetre.
  So no built-in preset starts warning, and no built-in sheet moves its bottom
  line. Measured rather than assumed, because widening a bound is exactly the
  kind of change that quietly turns a fleet of charts red.

  **THE READING WAS THE CONSERVATIVE ONE AND HE HAS NOW CONFIRMED IT.**
  *"This should apply for both left or right side clip-border"* could mean "on
  both sides" or "whichever side the border is on". Applied to both sides it
  contradicts his own already-confirmed A4 example, *"210 - Clip x2 = 202mm"*,
  which has margins and ignores them: driven that way, six tests pinning 202
  went red. So the margin joined the border's side only and the question went
  back to him. **Confirmed by: Knut, 2026-09-13**, who restated the rule in
  full for both sides, both clauses opening "If clip-border ON": that is what
  beta 10 already shipped, checked afterwards against his prose over nine
  crossings of the four terms, zero mismatches.

  **F5: a typed size never shrank.** *"Shrinking stops at 7 pt, but only in
  size=auto. When size is manually set to 13, it is not a shrinking."*
  `text_floor_pt` answers "a typed size is its own floor", which is true, and
  the message printed it back as *"the text has stopped shrinking at 13 pt"*,
  his own number described as a limit the text ran into. The clause is out of
  both messages and the two cases carry their own sentence: `_auto_floor_note`
  as before, and a new `_typed_size_note` saying the size is printed exactly
  as typed and what "auto" would do instead.

  **AND ONE I WALKED INTO WHILE FIXING F5.** `_typed_size_note` reached for
  `text_edge_fit` as a global, and it is imported inside `_engine_text_notes`,
  which swallows every exception: two warnings became zero, silently, on his
  own case. That is the hazard B8-114 recorded two hours earlier, arriving by
  a new door. It imports locally now.

### B8-116 · The layout-name stamp prints a doubled separator
- blocks release: no
- status: FIXED
- found by: reading the stamped line while measuring B8-115; NOT reported by
  anyone, raised with Knut, and changed only once he approved it.
- evidence: test_stamp_uses_chart_layout_line_for_ti1_origin, which pinned the
  trailing bar and now refuses it, and refuses "|    |" in the joined line the
  reader actually sees.
- detail: `stamp_lines` appends `f"Chart layout {name} |"` with a trailing
  bar, and `tiff_metadata._JOIN` then adds `"    |    "`, so a preset chart
  stamps `... w10.0mm |    |    ChromIQ layout engine`. Cosmetic, visible on
  every chart built from an armed patch set, and pinned as-is by
  `test_chart_creator.py` (`"Chart layout TC9.18 |"`).

  Left alone at first, deliberately: it changes what is printed on every preset
  sheet, nobody had asked for it, and it landed in the middle of a release. It
  was raised with Knut instead, and he answered the same evening: *"Yes, make
  sure only one 'bar' is used to separate the layout-name and other text-fields
  coming after."* The trailing bar is gone, and the test that pinned it now
  pins the opposite, on the joined line the reader actually sees.

### B8-117 · Font sizes moved a whole point at a time, and one shrink moved a tenth
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, after beta 11.
- evidence:
  test_the_step_is_half_a_point,
  test_the_next_size_down_lands_on_the_grid,
  test_it_is_always_strictly_smaller,
  test_the_notes_shrink_walks_half_points,
  test_the_shrink_never_goes_under_its_floor,
  test_the_finer_shrinks_are_left_alone,
  test_a_size_prints_its_decimal_only_when_it_has_one,
  test_the_old_spec_rounded_a_half_away,
  test_no_message_rounds_a_size_any_more,
  test_no_catalogue_still_carries_the_old_spec.
  Driven on screen with `scripts/drive_182_half_point_sizes.py`.
- detail: *"All the places where font size is defined, the side pt number
  should have one decimal and jump half a point at a time … The 1 pt resolution
  is too course, so a 5,5 pt, of 7,5 pt might some times be needed."*

  **THE FOUR SIZE-CHOOSING PATHS WERE MEASURED BEFORE ANY WERE CHANGED**,
  because "make the shrink finer" is only right where it IS coarse. At 300 dpi
  they could land on:

  | path | before |
  |---|---|
  | bottom sheet text | 12, 11.76, 11.52, 11.28 … (one PIXEL, 0.24 pt) |
  | clip text | computed straight to the fit, continuous |
  | right-edge notes | **12, 10.8, 9.6, 8.64, 7.68, 6.96** |
  | the Size boxes | whole points only |

  So his example is `fit_rotated_line` and nothing else: a ten per cent
  geometric step that never offers 9.5 and whose last step lands BELOW its own
  7 pt floor. The two already finer than half a point are deliberately
  untouched, and `test_the_finer_shrinks_are_left_alone` says so, because
  coarsening them to a 0.5 grid would lose fit.

  **THE SHRINK COUNTS IN POINTS NOW.** The first fix stepped in pixels and the
  pixel rounding swallowed the grid: at 300 dpi it produced 12, 11.52, 11.28,
  11.04 instead of 12, 11.5, 11.0, because half a point rounds onto a
  neighbouring pixel and the pixel did the stepping.

  **AND THE WARNINGS ROUNDED.** `{size:.0f}` rounds half to even, so a 9.5 pt
  line was described as 10 pt and 8.5 as 8. `text_edge_fit.format_pt` prints
  "9.5" and plain "13"; twelve messages take a finished string and all twelve
  catalogues were migrated with their keys, 144 entries, nothing retyped.

  Four boxes, one helper for three of them plus Preferences. No hand-widening:
  `_fit_spin_widths` asks each box for its own longest string, now "72.0".

### B8-118 · Two fields that could be present but empty
- blocks release: no
- status: FIXED
- found by: Knut's follow-up on B8-116, 2026-09-13: *"Also make sure that the
  empty space between two bars is not due to a missing parameter, or a setting
  that is empty etc. If that would be the case, double bars would only be
  replaced by one bar IF they are empty in between."*
- evidence:
  test_no_missing_field_ever_leaves_a_doubled_bar,
  test_no_field_is_blank_before_it_is_joined,
  test_a_blank_layout_name_is_not_a_layout_name,
  test_a_padded_layout_name_is_trimmed,
  test_every_joiner_drops_its_empty_pieces.
  Mutation: restoring the trailing bar turns five red.
- detail: the right question, because collapsing "|    |" into "|" would HIDE a
  field that came out empty and the empty field would be the fault.

  **IT WAS NOT A MISSING VALUE.** All five `_JOIN` sites filter first (`if s and
  s.strip()`), the four columns of the left clip strip and the right-margin
  stamp, so an absent field removes itself and takes its separator with it.
  Driven over six ways a field can go missing: no doubled bar in any of them.

  **HIS SHAPE DID EXIST FROM THE OTHER SIDE, TWICE.** A layout name that was
  PRESENT but blank stamped the bare label "Chart layout" with nothing after
  it; chart notes of nothing but spaces were appended and dropped again by the
  stamper's filter, a safety net doing the design's job. Both are stripped at
  the source. The second was found by the test written for the first.

### B8-119 · The limits window never said which set the run was bound to
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, on `Report-Limits-Report-Types` run 5.
- evidence:
  test_the_row_shows_the_set_the_run_is_bound_to,
  test_it_is_a_different_row_from_the_default_for_new_runs,
  test_choosing_one_records_the_pick_and_writes_nothing,
  test_picking_the_set_it_already_has_records_nothing,
  test_a_locked_run_cannot_be_changed_from_here,
  test_a_click_on_a_locked_run_records_nothing,
  test_there_is_no_row_when_there_is_no_run,
  test_the_report_window_applies_the_pick_through_its_own_door.
  Three mutations, each proved to land. Driven on screen with
  `scripts/drive_182_limits_radio_case.py`, on his own run and on the pack's
  own locked run.
- detail: *"The Judged against is set to 'ChromIQ tight', but when opening
  'Edit Limits' window the 'ChromIQ default' was enabled. Manually clicking any
  of the 5 radio-buttons to select a limit set did nothing."*

  **BOTH HALVES WERE TRUE AND NEITHER WAS A BROKEN CONTROL.** Driven before
  anything was changed: run 5 really is bound to `chromiq_tight`, the only
  radio row on that window really is headed "Default for new runs", and
  clicking one really did move `compliance_default_set` and leave the run
  alone. Two different questions, one row of radios, and the window never
  stated the answer to the one he was looking for.

  So the row he expected sits BESIDE the one that was there. Repurposing the
  existing row would have deleted CH-1 / S-13 without anyone asking.

  It writes nothing: `_on_set_chosen` is the single writer and carries the lock
  re-check, the preferences-moved check and the recalculate question. The pick
  is recorded and applied through the pulldown on close, so there is one path
  and one set of guards.

### B8-120 · The generated-reports line was cut off by the type's description
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13.
- evidence:
  test_the_line_carries_the_list_and_not_the_type_description,
  test_a_short_list_needs_no_link,
  test_a_list_too_long_for_the_line_opens_in_full,
  test_the_link_opens_a_window_naming_every_type,
  test_the_tooltip_is_the_whole_list,
  test_a_run_with_nothing_generated_still_says_so,
  test_which_types_exist_is_the_half_that_survives_elision,
  test_the_line_beside_the_pulldown_describes_the_chosen_type.
  Two mutations, each proved to land.
- detail: *"the end of the text is cut off with a '...' at the end. All
  generated reports should be listed clearly and visible, even if it is a list
  of 6 report types. This might require a taller text area. If limited space,
  this could be handled with one-line text that opens for more detailed
  information."*

  The taller area is the one thing that cannot be done here, and the comment
  beside the widget says why: a word-wrapped label of its own pushed this
  window's bottom off an 800 px screen twice. So it is his second option.

  An earlier round had already moved the list in FRONT of the type's
  description, but the two still shared one elided line, so the description was
  still pushing the list out on any narrow window; a wide window merely hid it.
  The line is the list now. What a type is for keeps the two homes it already
  had, the pulldown's entries and its tooltip; what a run holds had none. When
  the list still will not fit, the line grows a "show all" link that opens the
  whole thing, one type per line.

### B8-121 · The save panel lost the folder between ChromIQ and macOS
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13: *"Clicking Save Report as PDF opens a file window
  that does not open in the currently open project, for the selected run, and
  for the correct level in the folder structure according to the rules set for
  where reports are saved."*
- evidence:
  test_the_save_panel_is_given_the_folder_not_just_the_name,
  test_a_missing_folder_still_falls_back_to_a_bare_name.
  Mutation: pass the bare name again and both go red.
- detail: measured first, and the caller was right all along.
  `_report_dir()` returned `<project>/runs/run5/verifications/reports`, the
  documented home for a report covering several checks of one run, and that
  reached `save_file_dialog` intact. What did not reach the panel was the
  FOLDER: `selectFile` was handed a bare file name, and a native macOS save
  panel keeps its own last-used directory when it is given only a name. It gets
  the absolute path now. The beta.16 fall-back for a folder that does not exist
  is unchanged and still tested.

### B8-122 · REPORTED, NOT REPRODUCED: the report text following the set and type
- blocks release: no
- status: OPEN
- found by: Knut, 2026-09-13: *"When I changed the Judged against option to
  another limit set, the report scope and report text did not update to specify
  correct limit set. The same happened if I changed the report type."*
- detail: driven twice and it followed both times, so nothing is claimed as
  fixed.

  With the type pinned to one that prints the row, changing the set moved the
  on-screen document's "Judged against" from "ChromIQ tight" to "ChromIQ
  default (recommended)"; changing the type re-rendered the document and named
  the new type in it. Both checked on the rendered VIEW, not only on a
  recomputed body, because the view is what he reads.

  A first probe reported "no change" and was wrong: run 5 was already on the
  type it was being switched to, so the document was identical for the right
  reason. That is recorded because it is the kind of measurement that looks
  like a finding.

  His sequence is asked for rather than guessed at.

### B8-123 · The challenge round on the 2026-09-14 batch: five faults, all two hours old
- blocks release: no
- status: FIXED
- found by: the adversary round run against `b3bbafbe` and `de04179d` before
  tagging beta 13, at Basti's explicit instruction to run the loop on Knut's
  latest request. Four drivers, real windows, real Generate, ink measured off
  the app's own TIFFs.
- evidence:
  test_the_two_rows_are_separate_exclusive_groups,
  test_changing_your_mind_back_records_nothing,
  test_the_pick_is_applied_outside_the_body_so_it_cannot_double,
  test_the_body_leaves_the_pick_for_the_wrapper,
  test_the_report_window_applies_the_pick_through_its_own_door,
  test_patch_first_warns_too,
  test_the_label_checks_stay_area_first_only.
  Mutating back to the shipped state reproduces F1 and F2 exactly.
- detail: five, every one written that night. Recorded in full because the
  shapes recur.

  **F1. QT'S AUTO-EXCLUSIVITY IS PER PARENT WIDGET.** Both radio rows were laid
  into `_head_grid`, so the ten buttons were ONE exclusive group: picking a set
  for the run unchecked "Default for new runs", and one row could show two
  filled buttons. The opening state looked right only by accident, because
  `setChecked` runs before `addWidget` reparents. **A row of radios needs its
  own `QButtonGroup` the moment a second row shares its parent.**

  **F2. AND IT REBOUND THE RUN TO THE SET THE USER CANCELLED.** The first click
  never unchecked the original, so clicking the original again was a no-op on
  an already-checked button: the handler did not fire and the abandoned pick
  stayed recorded. `test_picking_the_set_it_already_has_records_nothing` passed
  throughout, because it clicked the already-checked radio FIRST, where the
  no-op gives the right answer. **The order a test clicks in is part of what it
  proves.**

  **F3. A WINDOW MUST NOT SEE ITS OWN CHANGE AS SOMEBODY ELSE'S.** Applying the
  pick inside `_on_open_limits` put it before the body's own after-snapshot, so
  the "did what this run is judged by change?" test caught the window's own
  write: two identical recalculate questions, two archive folders, a silent
  revert of the preference just set, and a box blaming another window. The body
  records; a `finally` outside it applies, once, across a dozen early returns.

  **F4. WIDENING A GUARD LETS THROUGH WHAT IT WAS ALSO HOLDING.** Letting the
  bottom checks run in patch-first (B8-1xx's real fix) took the HEIGHT check
  with the width one. The height check asks about `r.margin_bottom`, the
  REQUESTED margin; patch-first reserves the band instead. Measured on a real
  Generate: patches ending 263.99 mm, text at 288.37, 24.38 mm of clear paper,
  under a red line claiming a collision. The width check is right in both modes
  and stays; the height check is area-first again.

  **F5. A COMPOSITION CHANGED IN ONE CALL SITE OF TWO.** `_sync_type_combo_to`
  still set the line to the type's description after the line became the
  generated list, leaving a description carrying a "show all" link to a list it
  does not name, over a contradicting tooltip.

  **AND IT CAUGHT AN UNSANDBOXED PROBE OF MINE** pinning `custom_output_path`
  in the real plist for the second time in one session. Unset, verified by
  value. Probe scripts now set `CHROMIQ_SETTINGS_FILE` and
  `CHROMIQ_PRESETS_DIR` as environment variables before `core` is imported at
  all, which is the only ordering that works.

### B8-124 · "Generate report" looked inert, because every setting redrew the document
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-13, testing beta 12: *"The generate report button
  seems not to do much, as the report auto-generates whenever report type or
  judged against is changed."* Put back to him with the cost of changing it,
  and he ruled on 2026-09-14: *"This change give the user more feeling of
  control and understanding of when something should change, or when a change
  will result in a changed report, and will see that it does change or not when
  clicking "Generate report". It will also give a user a chance to undo a
  changed field, if not wanting to regenerate the report. Make the change."*
- evidence:
  test_a_fresh_window_says_nothing,
  test_the_two_tick_boxes_wait_and_say_so,
  test_the_ticked_measurements_are_one_of_the_five,
  test_generate_builds_the_document_and_clears_the_warning,
  test_a_new_measurement_still_appears_at_once,
  test_every_one_of_the_five_goes_through_one_door,
  test_the_banner_is_a_comparison_and_not_a_flag,
  test_choosing_a_type_WAITS_FOR_GENERATE_and_says_so,
  test_putting_the_type_back_takes_the_warning_away.
- detail: five settings now move the CONTROL and leave the DOCUMENT standing,
  with a red line beside the button saying so: report type, judged against,
  show all measurement runs, show detailed data, and the measurements ticked in
  the list. Everything else still repaints at once, because it changes what
  there IS to report on rather than how it is presented.

  **THE BANNER IS A COMPARISON, NOT A FLAG.** His second sentence is the one
  that decides the implementation: *"a chance to undo a changed field."* A
  boolean set on every change cannot see an undo, so putting a control back
  would leave a red line over a document that already matches it, which is the
  same lie the other way round. `_doc_settings()` snapshots the five, `_render`
  records what the document was built from, and the banner is the two being
  different.

  **AND WHAT A SETTING DOES ON DISK IT STILL DOES AT ONCE.** Choosing a limit
  set still binds the run and still asks its recalculate question; choosing a
  type still stores it on the run. Deferring those would have turned a
  deliberate act into a pending one, which is not what he asked for.

### B8-125 · The bottom lines get an Alignment control, with three options
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-14, in two posts an hour apart. First: *"for the sake
  of beauty, I find it better that the two bottom text type (in Sheet text
  frame) should be left-aligned against the patch area left margin, instead of
  centred against available horizontal space. This means a long text only gets
  warning when hitting towards the right side limits. This is ok. Leave limit
  detection as is for the left side, as alignment of text may change again
  later."* Then, with the control he wanted instead: *"However, in some cases
  the centre adjustment is best, depending on the setup. I thus suggest a new
  input box to be added below the Size input box in the Sheet text frame … 1.
  Left margin (default) … 2. Centre of available space: This is the alignment
  type already in the design on beta 13. 3. Centre between left and right
  margin … Leave side-limit detection as it is designed. Depending on the set
  alignment of text, a long text may trigger a warning on either sides, or only
  one side. The new alignment parameter must be added in the list of parameters
  so that it is saved/remembered or loaded in all cases … Test it thoroughly,
  that all alignment options result in the correct behaviour on screen, tested
  on presets for each instrument type."*
- evidence:
  test_his_three_names_are_the_three_keys,
  test_the_patch_area_centre_is_between_the_margins_not_the_paper,
  test_the_room_is_what_that_alignment_leaves,
  test_the_bounds_are_the_same_two_whatever_the_alignment,
  test_a_line_never_starts_inside_the_left_bound,
  test_left_margin_starts_both_lines_at_the_margin,
  test_centre_of_available_space_is_the_beta_13_placement,
  test_centre_between_the_margins_is_a_different_centre,
  test_the_two_bottom_lines_follow_the_same_rule,
  test_the_renderer_and_the_panel_ask_the_same_function,
  test_the_alignment_travels_through_every_door,
  test_the_engine_actually_receives_it,
  test_every_cell_holds_at_most_one_widget.
  **Driven on screen** by `scripts/drive_182_bottom_text_alignment.py`: one
  engine preset from each of the six instrument groups in the built-in
  dropdown, all three alignments on each, the ink measured off the app's own
  TIFFs and checked against arithmetic written out longhand in the driver, with
  a photograph of the new pulldown per instrument. Six verdicts, all green.
  Nine mutations proved to land across this entry and B8-124.
- detail (the first half, left-alignment):
  test_the_bottom_line_starts_at_the_patch_area_left_margin,
  test_a_clip_border_bounds_the_bottom_line_on_its_own_side,
  test_a_longer_bottom_line_grows_only_to_the_right,
  test_a_left_aligned_line_cannot_use_the_paper_behind_it,
  test_his_own_worked_example_still_gives_202_mm,
  test_the_renderer_uses_the_same_bounds_and_the_same_anchor,
  test_the_long_line_really_does_not_fit_at_the_starting_size,
  test_a_long_bottom_line_on_auto_shrinks_until_it_fits.
  Measured on rendered A4 sheets, ink read off the raster.

  `text_edge_fit.bottom_text_anchor_mm` is the new anchor, and it is
  the left MARGIN held inside his existing bounds. His last sentence is why the
  bounds are untouched: the left bound is still `max(Clip, R, border, margin)`
  exactly as comment 5651269930 and his 2026-09-13 follow-up specify it, and it
  is the floor the anchor cannot cross, so a margin narrower than the reserve
  cannot start the line inside furniture.

  **ONE THING HIS "LEAVE LIMIT DETECTION AS IS" DID NOT COVER, AND IT IS
  REPORTED RATHER THAN ASSUMED.** The room the width check measures is now
  `right bound - anchor`, not `right bound - left bound`. Leaving the old
  figure would have let a typed size run off the right-hand side of the paper
  with nothing said whenever the left margin is wider than the left bound: on
  A4 with 12 mm margins that is an 8 mm blind gap, and a silent overflow is the
  exact fault he reported against beta 8. His own sentence, *"a long text only
  gets warning when hitting towards the right side limits"*, is what the new
  figure implements. His 202 mm example is unchanged where it lives, on the
  bounds. **Raised in the beta 14 reply for his ruling.**

  The warning's own wording changed with it: it used to say the sheet leaves so
  many mm *"between the distances you set for the two side edges"*, which named
  two controls of which only one is still in the arithmetic, and did not name
  the margin that now decides where the line starts.


### B8-126 · The new report warning ate the four buttons it was pointing at
- blocks release: no
- status: FIXED
- found by: LOOKING AT THE PHOTOGRAPH. The banner for B8-124 was first added
  inside the button row with a stretch, the everyday tier was green, and the
  first on-screen driver run showed why that meant nothing: on the real
  1500 px window "Generate report" read *"erate rep"*, "Save report as PDF…"
  read *"report as"*, "Reveal folder" read *"veal fold"*, and the warning
  itself was cut off at *"or put the s"*.
- evidence:
  test_the_warning_does_not_squash_the_buttons_it_names.
  Photographs before and after in the beta 14 proof folder.
- detail: it has its own row now, directly under the row it talks about, with
  word wrap on. A hidden widget claims no space in a Qt layout, so the row
  costs nothing until the warning speaks.

  **THE TEST THAT CATCHES IT IS NOT THE ONE THAT LOOKS OBVIOUS.** Asserting
  that the buttons keep their `sizeHint` width passed under the mutation:
  offscreen at 1200 px there was still room, so nothing was clipped and the
  check proved nothing. What Qt will answer honestly is the WINDOW'S OWN
  MINIMUM WIDTH: with the label back in the row it goes from 996 px to 1072 px
  the moment the warning appears, and with it on its own wrapped row it does
  not move. Measured both ways before the assertion was written.

### B8-127 · The adversary round on beta 14: four faults, all mine, all hours old
- blocks release: no
- status: FIXED
- found by: the adversarial round run against the beta 14 work before tagging,
  driving real windows with the ink measured off the app's own renders. Four
  drivers left in `scripts/adv14_*.py`; proof in
  `~/Desktop/ChromIQ-adversary-2026-09-14/`.
- evidence:
  test_the_room_is_what_that_alignment_leaves,
  test_a_centred_line_is_never_called_too_wide_while_it_fits,
  test_nothing_waits_for_a_button_that_cannot_be_pressed,
  test_the_last_measurement_unticked_leaves_nothing_to_generate,
  test_the_loose_type_pulldown_goes_through_the_same_door,
  test_an_at_once_door_never_leaves_the_window_saying_something_untrue.
  Nine mutations, every one proved to land and every one caught.
- detail: four, and the shapes are worth keeping.

  **F1. A CHECK AND A PLACEMENT THAT DISAGREE PRINT THE DISAGREEMENT AS A
  NUMBER.** `bottom_text_room_mm` answered "the widest line that stays
  CENTRED" for the new between-margins alignment, while `bottom_text_start_mm`
  anchors a line that will not centre at the left bound instead, exactly as the
  centred renderer always did. So a line too wide to centre was called too wide
  to print. Driven on the real i1Pro 100x150 preset: the panel said 26 mm of a
  77 mm line ran off, and the app's own render put the ink at 19.30 to
  95.63 mm inside a 96.0 mm bound. A 144-cell sweep found nine cells warning
  about ink that fits, every one this alignment, and zero cells where ink
  crossed a bound in silence. The fix is the closed form of "the widest line
  the clamp actually lets fit", checked against a brute-force search of the
  real placement over 20,000 random geometries with zero mismatches.

  **F2. NOTHING MAY WAIT FOR A BUTTON THAT CANNOT BE PRESSED.** "Generate
  report" is disabled when the window is on a measurement in no run, when
  SEVERAL profiles are loaded, and when every measurement is unticked; the two
  tick boxes and the run ticks stay live in all three. So with two profiles
  loaded, which is this window's main job, "Show detailed data" froze the
  document and a red line told the reader to press a greyed-out button. Those
  settings did nothing at all, ever. Found twice within the hour, by reading
  the enable condition and by driving it.

  **F3. THE DOOR THAT WAS NOT REWIRED WAS THE ONE NOBODY LOOKED AT.**
  `_on_type_chosen`'s no-run branch still called `_refresh` after the other
  four learned to wait, so on a loose measurement the type pulldown rebuilt the
  document on its own while the limit pulldown two rows below it did not.
  Knut's original complaint was still true in that corner.
  `test_every_one_of_the_five_goes_through_one_door` did not catch it: it
  asserted `_settings_touched()` is IN the method, and it was, on the other
  branch. **A check that a call exists somewhere in a method says nothing about
  the branch that runs.**

  **F4. A DOOR THAT REPAINTS AT ONCE ADOPTS A PENDING SETTING**, and that is
  accepted rather than fixed: adding a measurement rebuilds the document from
  the controls, which include the change nobody confirmed, and the banner then
  correctly goes quiet. No statement the window makes is untrue at any step;
  what is lost is the cheap undo, for one setting, at a moment that had to
  rebuild the report anyway. Building from the committed five instead means
  rendering from a snapshot rather than from the window, which is a different
  window. The invariant is pinned instead: the banner is up exactly when the
  document does not match the controls.

  **AND TWO OF THE ADVERSARY'S OWN PROBES WERE WRONG BEFORE THEY WERE RIGHT**,
  which is recorded because both shapes recur: a hand-copied "off" recipe made
  the diff measure a sheet that was not the same sheet, and
  `bottom_text_overflow`'s `needed_w_mm` is the THIRD positional, not the
  seventh, so a `*pos, need` call fed the width in as `markers_sides` and made
  every warning in the first sweep meaningless.

### B8-128 · Knut, 2026-09-14: a report never said which type it was
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-14, with two PDFs of the same run attached: *"there
  are texts that should state correct report type used and judged against, but
  is not changing this. The top of the Report scope also does not show the
  report type generated."*
- evidence:
  test_the_default_type_names_itself_too,
  test_every_built_type_names_itself,
  test_the_head_can_never_name_a_type_this_build_cannot_make,
  test_the_limit_set_is_named_at_the_top,
  test_two_runs_bound_to_different_sets_leave_one_in_the_document,
  test_the_run_description_is_labelled_as_one,
  test_and_keeps_room_for_a_description_of_ordinary_length.
  Measured on his own two files with pypdf before anything was changed.
- detail: three separate things, and only two of them were bugs.

  **THE DEFAULT TYPE NEVER NAMED ITSELF.** The line was guarded by
  `_tid != REPORT_TYPE_FULL`, so the type most reports are is the one type that
  produced a document saying nothing about what it was. His two PDFs prove it:
  the Grey-and-tone one carries `Report type: Grey and tone check` on page 1
  and the Full colour check one carries no such line. The code comment
  justifying the silence was OUR reasoning, not his ruling.

  **THE LIMIT SET WAS IN THE DOCUMENT BUT NOT AT THE TOP.** The "Judged
  against" row of Report Results says "Custom ISO 12647-7" in one of his files
  and "ChromIQ default" in the other, correctly, and each run's detail names it
  again, so the body does follow the pulldown. It is now named beside the type,
  where a reader opening a saved PDF looks first, and only when the loaded runs
  agree on one set: one name over a document covering two differently bound
  runs would be a claim about a column it does not describe.

  **AND THE PARAGRAPH HE QUOTED AS EVIDENCE IS THE RUN'S DESCRIPTION**, which
  no report can update. The demo package writes descriptions that name a report
  type and a limit set because he asked for that sentence on 2026-09-11, so
  once a run is rebound the description contradicts the live lines above it.
  Unlabelled, it reads as one of them. It carries a faint "Run description"
  label now, which is the same trap closed for any user who writes "judged with
  ChromIQ tight" in the box. **Raised in the beta 14 reply, because the label
  is an addition to text he specified.**

  The two new lines cost the one-page summary 30 px of its 60 px margin, so the
  type and the set share one line separated by the report's own middle dot.

### B8-129 · Two leads found while fixing the above, neither driven to a fault
- blocks release: no
- status: OPEN
- found by: writing tests for B8-127 and needing two measurements that the list
  could tell apart.
- detail: **a run's identity in the report list is `created|ti3 name`**
  (`_run_key`), and `created` falls back to the measurement file's own mtime.
  Two dated verifications written inside one second are therefore ONE key, and
  unticking either hides both. Real, reproducible in a test fixture, and not
  reachable by hand at ordinary speeds; it needs a tie-break, not a redesign.

  **And a verification created while the report window is open is never picked
  up**: `_append_source` answers False for a second verification of a run
  already loaded, so `_load` does nothing at all. Whether that is right
  (the window lists what it read when it opened) or wrong is a question for
  Knut, not a fix to make unasked.

  Also carried forward from the adversary round: after a real Generate Chart,
  the run's stored `create_chart_ui.engine_recipe.paper` read "A4" for a chart
  built at 100x150 mm, while `meta.json` and the TIFF both say 100x150.
  `_engine_text_notes` computes every bottom-text bound from `r.paper` under
  the comment *"The recipe always knows its paper"*. Not driven to a visibly
  wrong warning, so it is a lead; the new alignment arithmetic sits on top of
  it.

### B8-130 · Knut, 2026-09-14: a help icon on every metric row, and the five rows with no detection
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-14: *"Right aligned to the end of each metric name,
  add an info help icon, where each help icon describes the metric for that
  line and details the conditions used to detect if a chart contains the
  patches needed to assess and judge this metric. If any metric is missing a
  detection method ... then this detection method must be determined and
  specified."*
- evidence:
  test_every_row_says_what_it_measures,
  test_every_row_that_can_be_judged_says_how_it_is_detected,
  test_the_assertion_in_the_row_itself_is_still_there,
  test_the_grey_condition_quotes_the_real_thresholds,
  test_the_corner_condition_quotes_the_real_tolerance,
  test_the_ramp_condition_quotes_the_real_thresholds,
  test_the_worst_five_condition_quotes_the_real_population_size,
  test_the_reference_rows_say_where_the_reference_comes_from,
  test_the_five_rows_with_no_detection_say_so_plainly,
  test_no_row_promises_a_reason_code_that_does_not_exist,
  test_the_window_carries_one_icon_per_row,
  test_each_icon_carries_both_halves,
  test_the_icon_sits_at_the_right_edge_of_the_name_column.
  Driven on screen by `scripts/drive_182_metric_help_icons.py`: thirty icons,
  all at one x, five verdicts green, three of the info dialogs photographed.
- detail: the two halves live on the ROW, in `compliance_sets.ROWS`, and
  `Row.__post_init__` refuses a row without them, so the window cannot describe
  a table it does not have and a new row cannot arrive undocumented.

  **THE NUMBERS IN THE SENTENCES ARE READ BACK OUT OF THE CODE.** Eight grey
  steps, one unit of spread, twelve device units at a corner, three ramp steps
  over twenty tone points, twenty patches for a worst twentieth: each is
  asserted against `measurement_report`'s own constant, so changing a threshold
  without changing what the window promises turns the suite red. A document
  cannot keep itself true; this is how it is held.

  **FIVE ROWS HAVE NO DETECTION AND THE ICONS SAY SO.** Three control-strip
  rows and the two selected-patch rows. What each would need is written out in
  `docs/design/issue_182_answers.md` §2w; two of them change a specification
  and are Knut's to approve, so nothing was invented.

  **AND THE THREE REFERENCE ROWS ARE DEAD ON EVERY CHROMIQ CHART**, measured:
  `needs_reference_file` in 80 of 80 saved reports in the demo package. They are
  also the three rows both Custom columns put a number on. The icon now says
  which kind of chart supplies that reference.

### B8-131 · The worst-5 % row said the condition was met and withheld the verdict anyway
- blocks release: no
- status: FIXED
- found by: mapping the metric table for B8-130. **MEASURED** on a 20-patch
  chart: *"the chart has 20 patches; at least 20 are needed to split off the
  worst 5 %"*.
- evidence: test_the_worst_five_condition_quotes_the_real_population_size,
  and the sentence itself now names the population it counted.
- detail: the verdict is passed on the WITHIN-gamut subset (`graded_de00`),
  which was 18 on that sheet, and `{n}` was filled from `report["patches"]`,
  the sheet's own count. A reader was told a condition was satisfied and the
  row was withheld anyway. **The number in a message must be the number the
  code tested**, which is the same shape as the layout-name and patch-count
  faults in B8-115.

### B8-132 · The adversary round on the metric icons: four sentences promised more than the code does
- blocks release: no
- status: FIXED
- found by: the adversarial round on the beta 15 work, reading each of the
  thirty detection sentences against the function that does the detecting, and
  photographing the icons as a user reads them. Drivers in
  `scripts/adversary15_*.py`; proof in
  `~/Desktop/ChromIQ-adversary-15-2026-09-14/`.
- evidence:
  test_no_detection_sentence_promises_more_than_the_code_does,
  test_the_grey_sentence_tells_the_truth_about_bare_paper,
  test_the_solids_sentence_names_the_composite_black,
  test_the_worst_five_sentence_has_a_singular_form.
  Eight mutations, each proved to land and each caught.
- detail: **a help text is a promise, and four of thirty overstated the code.**

  **F1. "a patch at EACH of the four solid corners" and the code needs ONE.**
  `row_values` builds `solid = [...]` over the corners it found and takes
  `max(solid)` when the list is not empty. Measured: a report with cyan present
  and magenta 9.9 away grades *"Solid colours, largest difference"* from one
  ink while the icon says all four were found and checked. Both that row and
  the CMY hue row are the ones both Custom columns put a number on.

  **F2 and F3. Two sentences listed every geometric condition and omitted the
  one that is not geometric.** `grey_balance_block` and `ramps_block` both
  withhold the row when the patches carry no reference values, AFTER
  eligibility is granted. The ramp case is worse than a silence: the report
  then prints *"the chart has no tone ramp with at least three steps"* about a
  chart that has one. That sentence is pre-existing and unreachable on any
  chart ChromIQ builds; it is carried into B8-133 rather than fixed here.

  **F4. "any chart it built" is the chart it builds most often, and that one is
  never judged.** `is_graded_sheet` is False for a run's own profiling sheet:
  **23 of the 80 saved reports in the demo package**, 25 counting the drift
  checks. The sentence also said the only other way was a measurement with no
  references, which is the wrong "only".

  **AND THE TEST FILE PINNED THE NUMBERS AND NOT THE CLAIMS.** The round proved
  it: one detection sentence was rewritten to *"ChromIQ judges this row on
  absolutely every chart, always, with no conditions whatsoever"* and all
  fifteen tests passed. `_MUST_SAY` now holds, per row, the words the icon must
  and must not use, one entry per fault above.

  **A MUTATION NOTE THAT WAS NEVER EXECUTED.** The file claimed that removing
  `_h.addStretch(1)` would turn the alignment test red. It does not: a QLabel's
  Preferred policy absorbs the slack on its own. The claim is corrected in
  place and the stretch kept for intent.

  Two smaller ones: the icon's edge sat **one pixel** from the unit text on all
  thirty rows, in three languages, at two window sizes (`ⓘΔE00`), now a 10 px
  margin; and the new worst-5 % sentence had no singular form, so a twenty-patch
  sheet with nineteen colours out of gamut would read *"1 of them fall"*.

### B8-133 · The tone-ramp row can say something untrue about a chart
- blocks release: no
- status: OPEN
- found by: the adversary round on B8-130, by code reading plus a synthetic
  measurement; **not reproducible on any chart ChromIQ builds**, because all of
  them carry a design reference.
- detail: `ramps_block` sets `any_eligible` only when an axis is eligible AND
  its band carries reference values, and returns a single `REASON_NO_RAMP` for
  both. Measured on a synthetic grey axis with 5 distinct steps spanning 40
  tone points and no reference: `eligible=False, reason='no_ramp'`, and the
  report prints *"the chart has no tone ramp with at least three steps between
  30 % and 70 %"* about a chart that has one.

  The fix is to split the code into `no_ramp` and `ramp_has_no_reference` with
  a sentence each. It is not done here because the path cannot be exercised on
  real data, and a new code path nobody can drive is a worse trade than a
  message that cannot currently print. The metric's help icon already names the
  reference requirement, so the window does not repeat the claim.

  The same shape exists for the grey rows, where `REASON_NO_REFERENCE` is
  already a separate code and the sentence is therefore correct.

### B8-134 · The metric icons diagnosed and never said what to do
- blocks release: no
- status: FIXED
- found by: Basti, 2026-09-14, reading the beta 15 changelog: *"is the provided
  info friendly, extensive and easy to understand and correct as always?"*
  Measured before answering: the new help is **78 words at the median** against
  **76** for the app's other 256 tooltips, so it was not thin. Three real
  weaknesses were visible on reading it.
- evidence:
  test_every_judgeable_row_names_a_lever,
  test_the_lever_names_a_control_a_reader_can_find,
  test_the_help_shows_the_lever_under_its_own_heading,
  test_no_help_text_talks_about_the_project_instead_of_the_product,
  test_the_five_rows_with_no_detection_say_so_plainly.
  Driven on screen; seven verdicts green, four dialogs photographed.
- detail: three things, and the first is the one that mattered.

  **EVERY OTHER HELP TEXT IN THIS APP ENDS WITH A LEVER, AND THESE ENDED WITH A
  DIAGNOSIS.** *"Raise 'Left' under 'Margins (mm)' by about 3.1 mm"* is the
  house style; the thirty new icons said what the row measures and when it can
  be judged, and stopped. A reader whose chart had six grey steps was told the
  row needed eight and not that a chart with a longer grey ramp is the fix, nor
  where to get one. Eleven rows now carry a `remedy` naming the screen and the
  control; the nineteen that cannot be judged carry none, because advice about
  a gloss meter would be invention.

  **THREE ROWS TALKED ABOUT THE PROJECT, NOT THE PRODUCT.** They ended *"and
  that is a change still to be agreed"*, which is true between Knut and me and
  means nothing to anyone opening the panel. They now say what the reader can
  observe: the cell stays empty in every limit set, and why. A test bans the
  phrase and four others like it.

  **AND TWO CONDITION SENTENCES PACKED FOUR CLAUSES INTO ONE.** The grey-ramp
  and solid-corner conditions are three short paragraphs each now. Same facts,
  same numbers, still asserted against the code's own constants.


### B8-135 · The bottom-text height warning measured the margin, not the patches
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-14, on the CR30 Letter 792-patch straight preset:
  *"When bottom margin is 11.0mm there is a warning ... You can clearly see
  that there is ample space both on top and below the bottom text line, so the
  warning should not happen. Measurements are obviously calculated wrong.
  Bottom margin in Measured from Preview shows 12.8mm."*
- evidence:
  test_the_panel_measures_the_patch_bottom_rather_than_predicting_it,
  test_his_own_chart_is_warned_about_now_and_was_not_before,
  test_the_measured_bottom_on_his_own_chart_is_the_number_he_quoted,
  test_his_case_is_quiet_and_a_real_collision_is_not,
  test_the_old_question_gave_the_wrong_answer_on_his_sheet,
  test_the_notes_survive_a_tab_that_cannot_count_its_patches,
  test_auto_shrinks_on_the_height_as_well_as_the_width.
  Driven on screen with scripts/drive_182_knut_bottom_text_height.py: 6 of 6
  green on his own preset, sheets rendered and the ink measured rather than the
  prediction re-asked.
- detail: the check asked `margin_bottom - "B" < lines x line`, and neither of
  those numbers is the distance in question. The text is anchored on the PAPER
  EDGE and never moves with the margin; the patch area's bottom is held back by
  `raster._furniture_reserves_mm`, which already subtracts the text band, so on
  his sheet the patches end at 15.62 mm with the ink stopping at 10.41 mm, a
  clear gap of 5.21 mm, and the panel warned. Swept over 7.5, 9, 10, 11, 11.5,
  13 and 16 mm: the ink is at 7.37 to 10.41 mm at every one of them, and the
  old test flipped at 11.5 mm on a sheet that does not change.

  `text_edge_fit.bottom_text_block_overlap(patch_bottom, reserve, lines, line)`
  is the question worth asking, and `tab_chart.predicted_patch_bottom_mm`
  answers where the patches really end, through `geometry.compute` and
  `geometry.placement`, which is what the renderer uses. `_furniture_reserves_mm`
  also stopped guessing a literal 4.2 mm per line and asks `SHEET_TEXT_LINE_MM`.

  **AND THE FIRST FIX PUT THE LOOKUP ON `self`.** `_engine_text_notes` wraps its
  whole body in one `except Exception: pass`, so an AttributeError there loses
  EVERY warning on the panel rather than one sentence: four tests went quiet and
  the silence read like the fix working. It is a module function now, and the
  patch count is read with `getattr(self, "...", lambda: None)()`.

### B8-136 · The Report type and Judged against help did not answer the question
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-14: *"the help text for the report type and judged
  against must describe properly what each option are, when they are normally
  used, and which Judged against limit sets are normally matched with which
  report type. It should also be explained how report type and limit sets
  depend on selection of the right chart / preset to be used and how the colors
  in that chart is selected for verification."*
- evidence:
  test_the_help_lists_every_type_the_pulldown_offers,
  test_a_seventh_type_cannot_be_missing_from_the_help,
  test_both_icons_answer_the_pairing_and_the_chart_question,
  test_the_help_says_the_things_a_reader_came_for,
  test_every_language_names_the_controls_as_that_language_shows_them.
  Four mutations proved to land. Driven on screen with
  scripts/drive_182_report_type_help.py: ten verdicts green, both icons
  photographed, both documents rendered and diffed.
- detail: four questions, and the help now answers them in four pieces. The six
  types are listed from `REPORT_TYPE_MENU` with their own descriptions, so a
  seventh type cannot appear in the pulldown and be missing from the help; a
  paragraph says when a reader would reach for each; a second says which limit
  set suits which type and that the pairs are habits rather than rules; a third
  says what the printed chart has to carry before a row can be judged at all,
  and that a chart built with FROM PROFILE GAMUT is where the aim values come
  from. The last two ride on BOTH icons, because the question reads the same
  from either control.

  **ONE SENTENCE OF THE FIRST DRAFT WAS FALSE, AND THE DRIVER CAUGHT IT.** It
  said the Printing record judges nothing "so the set beside it changes nothing
  in the document". Rendered both types on one measurement and diffed them: the
  type turns every verdict into INFO, and the document still names the set at
  the top and in Report Scope. The sentence says so now.

  **AND ELEVEN OF THE TWELVE TRANSLATIONS POINTED AT NAMES NOBODY WOULD FIND.**
  The limit-set names are English in every catalogue but the German one, and
  "Report limits" is untranslated in eleven, while the Create Chart tab and the
  FROM PROFILE GAMUT button ARE translated, differently, in all twelve. The
  first draft invented local names in five places per language.
  `test_every_language_names_the_controls_as_that_language_shows_them` reads
  each name out of that language's own catalogue and looks for it in the
  paragraph, so the next such drift is red rather than shipped.

### B8-137 · The other three edges name a remedy of the same wrong size
- blocks release: no
- status: FIXED
- evidence:
  test_all_four_sides_can_be_wrong_at_once,
  test_the_panel_measures_the_patch_bottom_rather_than_predicting_it,
  test_the_strip_letters_are_judged_with_the_markers_the_engine_draws,
  test_the_right_edge_warns_when_the_notes_run_over_the_patches,
  test_a_left_band_that_reaches_the_labels_says_so,
  test_it_still_warns_when_the_text_really_does_reach_the_patches,
  test_the_bottom_check_is_silent_before_a_chart_is_generated.
  The stand-in tabs in every one of those files are handed a real
  `MarginReport` now (`tests/margin_reports.py`), so a check that goes back to
  reading `geom.margin_*` stops being exercised at all and the file goes red.
- CLOSED 2026-09-15 BY KNUT'S RULING, see B8-179. Both halves of this item are
  answered, and by the same change rather than by three separate predictions:

  **The room they measure is the patch area now, on all four sides.** The
  bottom reads `report.bottom_mm`, the top `report.top_mm`, the right
  `report.right_mm` for the notes and for the clip band, and the left
  `report.left_mm` for the clip band and its text. Nothing on this panel
  predicts a patch edge any more.

  **And no message names a remedy of any size.** The second half of this item
  asked for `margin_rise_that_clears_mm` on the other three edges; instead the
  bottom's own copy was deleted. Under the ruling the panel does not answer
  "how much more margin clears it" at all: it names what is short, names the
  controls, and asks for a Generate Chart.
- found by: this session, 2026-09-14, while fixing B8-135. Raised rather than
  changed: it is pre-existing, it is smaller than the bottom case, and the
  wording it would need has to go through twelve catalogues.
- evidence: measured on the CR30 Letter 792-patch straight preset through
  `geometry.placement`: the patch area starts at x 12.78 mm against an 11.0 mm
  left margin, its right edge lands at 188.28 mm against 189.9 mm of paper
  before the 26.0 mm right margin, and the first row starts at 18.56 mm against
  a margin plus leader of 18.0 mm. So there is 1.78, 1.62 and 0.56 mm of real
  paper the top, left and right checks do not know about, where the bottom's
  was 4.6 mm.
- detail: two halves, and the first is the milder one.

  **THE ROOM THEY MEASURE IS THE MARGIN, NOT THE PATCHES.** Same shape as
  B8-135, and the numbers above say it is worth between half a millimetre and
  two, so a warning can appear over a sheet with a little clear paper. The
  bottom edge is now measured against `predicted_patch_bottom_mm`; the other
  three would each need their own prediction.

  **AND "RAISE X BY ABOUT N MM" IS THE OVERLAP, WHICH IS NOT WHAT IT COSTS.**
  The patch grid is re-fitted when a margin moves, so the edge travels less
  than the margin does. `tab_chart.margin_rise_that_clears_mm` is the shape of
  the answer for the bottom; the other three want the same treatment.

### B8-138 · The height fix shrank every "Size auto" bottom line at 300 dpi
- blocks release: yes
- status: FIXED
- found by: the adversary round on 2026-09-14, hours after B8-135 introduced it.
- evidence:
  test_the_shrink_can_always_stop,
  test_the_reserve_is_the_band_this_dpi_can_draw,
  test_a_typed_size_above_the_reserve_is_what_can_collide (now at six
  resolutions, not one),
  test_auto_shrinks_on_the_height_as_well_as_the_width.
  Sheets rendered at 150, 200, 240, 300 and 360 dpi and the ink measured.
- detail: the new height term asked
  `sheet_text_line_mm(...) <= text_edge_fit.SHEET_TEXT_LINE_MM`.
  `sheet_text_line_mm` rounds through whole PIXELS, and its own floor is
  `round(4.2 x dpi / 25.4)` px read back as millimetres: **4.2333 mm at 150,
  240, 300 and 360 dpi**, which is larger than the 4.2 it was compared with. No
  size could satisfy it at those resolutions, not even the 7 pt floor the loop
  stops at, so every chart with Size auto had its bottom line shrunk all the way
  down however much paper was free. **300 dpi is `LayoutRecipe`'s default.**
  Measured on one sheet with 7.5 mm of clear paper under the patches: the ink
  came out 1.947 x 9.991 mm at 300 dpi where the same recipe at 200 dpi, and the
  same sheet before the change, draws 2.540 x 13.1 mm.

  `raster.sheet_text_reserve_mm(dpi)` is the band as that dpi can draw it, and
  the loop compares against it. **And the test that named this feature was green
  throughout**: it grepped `render_pages` for `_fits_h`. It now also requires
  the term to be off the bare constant.

### B8-139 · The bottom height check was silent in patch-first
- blocks release: no
- status: FIXED
- found by: the adversary round, 2026-09-14.
- evidence:
  test_the_panel_speaks_in_both_layout_modes.
  Driven on screen with scripts/adv17_bottom_text_quiet_and_colliding.py, 20 states on
  Knut's CR30 Letter preset with the ink read off the app's own sheets: before,
  three real collisions in patch-first (6.60, 9.28 and 25.02 mm of overlap)
  with no height warning at all; after, every collision in both modes is named
  and no sheet with a clear gap is warned about except the sub-millimetre case
  below.
- detail: `_labels_can_overflow` gated the whole bottom block on area_first,
  because the old check asked about the REQUESTED margin, which is not the room
  in patch-first. That reason died with B8-135: the check asks where the patches
  really are now, and that question is as well posed in one mode as the other.
  Patch-first is the default for SpectroScan and CR30.

  **ONE CONSERVATIVE CASE REMAINS, AND IT IS THE MODEL, NOT A BUG.** The check
  measures the line's BOX (ascent plus descent), and the ink sits about 2 mm
  inside it, so at 28 pt in patch-first it warns with 0.64 mm of clear paper.
  The engine reserves boxes too, so the box is the honest unit; the residue is
  named here rather than left to be re-found.

### B8-140 · "Lower B" was advice that did nothing on Knut's own preset
- blocks release: no
- status: FIXED
- found by: the adversary round, 2026-09-14.
- evidence: test_the_lever_is_only_offered_where_it_moves_the_text; driven on
  screen with the markers on and off, both sentences read off the panel.
- detail: the bottom text is anchored at the LARGER of "B" under "Text distance
  from edge (mm)" and the ruler helper markers' own reach. With the markers on,
  which is his preset (edge 4.0 + length 2.0 + 1.0 = 7.0 mm), B typed at 7, 5,
  4, 3, 2, 1 and 0 left the anchor at 7.00 mm and the overlap at 1.27 mm, with
  the warning up the whole time: seven values, zero movement. The message now
  offers the lever only where it moves the text, and where it does not it says
  what is holding it and which control hands the distance back.

### B8-141 · The "lower B" offer promised room it could not buy
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- found by: the second adversary round, 2026-09-14, on the sentence the FIRST
  round had just caused to be written. Then a second case found here while
  checking that fix.
- evidence:
  test_the_lever_is_only_offered_where_it_moves_the_text,
  test_the_lever_is_withheld_when_it_cannot_close_the_gap,
  test_a_b_of_zero_is_not_offered_as_a_lever,
  test_the_lever_sentence_cannot_take_the_panel_down_with_it.
  Driven on screen with scripts/adv17b_the_lever_that_stops_at_the_markers.py
  and adv17b_the_lever_offer_is_kept.py.
- detail: two ways to promise nothing, and the first is the interesting one.

  **THE SENTENCE WAS CHOSEN BY ARITHMETIC AND THE LEVER IS A LAYOUT.** It asked
  only whether the anchor already sat above "B", which detects the case where
  the markers hold the text and misses the case where "B" is ABOVE their reach:
  there the anchor follows "B", so the arithmetic said "lowering it buys the
  same room", and the lever then stops dead at the markers. Measured on screen
  on the CR30 Letter preset at 24 pt with a 7.0 mm marker reach, "B" swept 12
  down to 0: the offer was made at 12, 11, 10, 9, 8 and 7, and pulling it all
  the way to 0 bought 5 mm of a larger shortfall and left the warning up. That
  is the same shape as the "raise Bottom by the size of the overlap" fault this
  whole block was written to remove. `tab_chart.lowering_b_clears` rebuilds the
  geometry with "B" at the bottom of its range and asks the sheet; where the
  answer is no, no sentence is appended, because the "Raise Bottom" remedy
  beside it is measured to work and needs no companion that does not.

  **AND A "B" TYPED AS 0 IS NOT AT THE BOTTOM OF ITS RANGE.**
  `effective_text_edge_mm` is `text_edge_mm or 4.0`, so a box reading 0.0 draws
  the text at 4.0 mm, and the caller was handing the note that effective 4.0 as
  though it were the typed value. A reader at 0.0 was told to lower it. The
  typed value is passed now and the sentence is withheld there. The 0-means-4.0
  reading itself is B8-144.

### B8-142 · Two claims in the help were still not exact
- blocks release: no
- status: FIXED
- found by: the second adversary round, 2026-09-14.
- evidence: test_the_help_says_the_things_a_reader_came_for (both phrases are
  in the forbidden list now), test_the_numbers_in_the_help_are_the_numbers_in_the_sets.
- detail: **"the grey rows move with them, by less" was false in the direction
  it mattered.** Read out of `_CHROMIQ_FACTORY`: Quick check takes the grey
  maximum from 3.0 to 7.0 while the colour maximum goes 3.0 to 6.0, so that row
  moves MORE, by 4.0 against 3.0 and by 2.33x against 2.0. The qualifier is
  gone, in English and in all twelve catalogues.

  **And two sentences over-reached.** "An ordinary test chart carries no aim
  values" is true only of the colorimetric aims the paper and solid rows need,
  while the grey and tone rows on the same paragraph are judged from an
  ordinary chart's own design values; it says "no such aim values" now. "Each
  row's own info icon says what to change" promises a change for the three rows
  that carry no remedy at all, and says "what that row needs, and what to
  change where anything can be" instead.

### B8-143 · The rise the message names was a knife edge
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- found by: the second adversary round, 2026-09-14, brute-forcing the predicate
  on a 0.1 mm grid across 80 overlapping states.
- evidence: test_the_rise_survives_a_click_past_it.
- detail: the predicate is not monotone. Six of the eighty states the round
  swept, all area_first, clear, stop clearing and clear again as the margin
  rises, because a whole row of patches drops out and comes back.
  **Reproduced here**, on a plain i1 Letter sheet with two lines of 12 mm type
  over a 20 mm bottom margin: 9.7 mm clears, 9.8 does not, 9.9 clears again.
  The margin spin box steps in 0.5 mm, so a number that only works typed to the
  tenth is not advice. The search returns the first rise whose neighbourhood
  clears, itself and the two spin-box steps above it, and the number is still
  one that was tested rather than inferred.

  **WHAT COULD NOT BE REPRODUCED, AND IT IS WRITTEN DOWN RATHER THAN QUIETLY
  KEPT.** The round also reported a case where the NAMED rise was itself a
  knife edge (17.4 clearing, 17.5 and 17.6 not). Re-measured across about 240
  states here, two instruments, three papers, both layout modes, five bottom
  margins and four line configurations, plus Knut's own preset: the bisection's
  own answer survived its neighbours every time. So the walk is a guard for a
  property worth holding, not a fix for a failure on record here, and no
  mutation of it turns a test red. `test_the_rise_survives_a_click_past_it`
  says so in its own docstring.

### B8-144 · A "B" of 0 is read as 4.0 mm and nothing on screen says so
- blocks release: no
- status: OPEN
- found by: this session, 2026-09-14, while fixing B8-141.
- evidence: `LayoutRecipe.effective_text_edge_mm` is
  `float(self.text_edge_mm or TEXT_EDGE_DEFAULT_MM)`, and the same "0 means the
  default" reading is used for "T" and for "Clip". The spin box's own minimum
  is 0.
- detail: a user who types 0 to push the text as low as it goes gets it drawn
  at 4.0 mm, and the only way to move it lower is to RAISE the box to 0.1.
  Nothing in the window explains that. Three ways out, and the choice is not
  ours to make alone: treat 0 as 0 and give "unset" another spelling; raise the
  spin box's minimum to 0.1 so the state cannot be reached; or leave the
  reading and say so in the field's own help. Raised for Knut and Basti rather
  than changed mid-release. Nothing in the app now offers advice that depends
  on it.

### B8-145 · The remedy search made the panel sluggish while the warning was up
- blocks release: yes
- status: SUPERSEDED
- superseded by: B8-179
- found by: the second adversary round, in a correction it sent after its own
  report: its first latency probe called the panel fifteen times on an
  UNCHANGED recipe and measured a warm cache. Re-measured by stepping the real
  spin box, which is what a hand does.
- evidence: scripts/adv17b_what_a_spin_box_step_costs.py, driven on screen
  before and after; test_the_rise_is_a_number_the_spin_box_can_reach.
- detail: `margin_rise_that_clears_mm` was making about a dozen geometry
  rebuilds per call, and a rebuild is 16 ms cold. Measured stepping the bottom
  margin 0.5 mm at a time with the warning up: **117.7 ms median on his preset
  and 147.9 ms with the patch size on auto**, against 16 to 31 ms for a quiet
  step. An 8x regression on the panel's response, in exactly the state a reader
  is turning that box to get out of.

  Three changes, and the first is the one that mattered:

  * **the overlap is the starting point.** The caller already knows how much
    room is short, and a 775-state sweep found the answer landing within 0.1 mm
    of that number in most of them. The search takes it as a hint, walks up the
    grid from there, and settles the common case in three probes;
  * **candidates are memoised** inside a call, so the walk never re-probes what
    the bisection already asked;
  * **it works on the 0.5 mm grid the margin box steps in**, which is five
    times fewer candidates and, more to the point, a number a reader can reach
    with the arrows. A rise named to the tenth was advice nobody could click.

  After, on screen: **67.1 ms median on his preset, 70.1 ms on auto**, quiet
  steps 19 to 31 ms. A warning step is about twice a quiet one rather than six
  times. The bisection is still there for a sheet whose answer is nowhere near
  the overlap.

  **AND THE SWEEP CORRECTED A NUMBER OF ITS OWN.** The round first reported 6
  non-monotone states of 80, from a sample; the full run found **135 of 775**,
  and **none** where the named rise failed to clear. What it does show is
  overshoot, which the grid walk can only reduce.

### B8-146 · The markers sentence named a route nothing had tried
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- found by: the third adversary round, 2026-09-14.
- evidence: scripts/adv17c_the_route_gate_one_names.py, driven on screen on
  Knut's CR30 Letter preset, with the photographs
  `01-gate1-the-sentence.png` / `02-gate1-after-the-route.png` /
  `05-gate1-after-the-fix.png`; test_the_markers_sentence_names_a_route_that_has_to_finish.
- detail: B8-141 made *"lowering B buys the same room"* conditional on the
  sheet's own answer. **The sentence beside it, in the same message, was left
  deciding from one comparison.** When the ruler helper markers hold the text
  above "B" it says so and then names a way out of its own, *"switching
  'Print helper markers' off, or shortening them, hands that distance back to
  'B'"*, and nothing ever tried it.

  Driven on screen, both layout modes, bottom margins 8 / 11 / 14, one and two
  lines, 14 / 24 / 40 pt: **24 states offered the sentence and 16 of them left
  the warning exactly where it was** after the markers were switched off and
  "B" taken to 0.1 in the real window. Photographed at area_first / 8 mm /
  40 pt: the room went from 7.1 mm to 14.0 mm against 17.1 mm needed, and the
  ruler helper markers were gone for it.

  `markers_off_clears` asks the sheet the same way `lowering_b_clears` does,
  and where the route does not finish, the message's measured "Raise Bottom"
  remedy stands alone. Re-driven after the fix: 8 states still offer it and all
  8 clear.

### B8-147 · The overlap hint made the advice nearly four times too big
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- found by: the third adversary round, 2026-09-14, attacking B8-145's own fix.
- evidence: test_the_hint_is_a_ceiling_and_never_the_answer; a 380-state sweep
  comparing the hinted answer against the same function called with `hint_mm=0`.
- detail: B8-145 hands `margin_rise_that_clears_mm` the overlap as a starting
  point and walks UP the grid from it, which is where the speed came from. But
  the walk only ever goes up, so **on any sheet whose answer lies BELOW the
  overlap the bisection was never reached at all**. Of 380 overlapping states,
  **77 answered larger than the un-hinted search**. The worst: a plain i1
  Letter sheet in patch-first, 18 mm bottom margin, two lines at 28 pt, overlap
  9.02 mm. A 2.5 mm rise drops one whole strip off the page and takes the patch
  bottom from 21.4 mm to 32.4, which clears it; the hint path said **9.5 mm**.
  Seven millimetres of bottom margin given away on a chart that is already two
  pages, and the same function with `hint_mm=0` answers 2.5.

  The cure is one probe: the grid point below the hint's answer. If it does not
  clear, the hint's answer is the smallest and nothing more need be asked, which
  is the common case; if it does, the hint was loose and becomes the bracket
  the bisection runs inside. Over the same 380 states this agrees with the
  un-hinted bisection in **every one**, at 7.34 probes a call against 9.04 with
  no hint and 5.97 for the version that was wrong in 77. Measured in isolation,
  86 warning states: **2.69 ms to 3.27 ms per call**, under 1 % of a warning
  step. Re-measured on screen with `scripts/adv17b_what_a_spin_box_step_costs.py`,
  the warning step stays about twice a quiet one, which is where B8-145 left it.

### B8-148 · Typing 0.1 into a "B" that reads 0 clears the warning, unsaid
- blocks release: no
- status: OPEN
- found by: the third adversary round, 2026-09-14.
- evidence: scripts/adv17c_the_route_gate_one_names.py, gate 2, with
  `03-gate2-box-reads-zero.png`.
- detail: the consequence of B8-144 inside the message. With "B" reading 0 the
  text is drawn 4.0 mm up, and RAISING the box to 0.1 moves it 3.9 mm DOWN.
  Driven on screen on Knut's preset, **21 warning states had a box reading 0
  and in 5 of them typing 0.1 cleared the warning outright**, while the panel
  named only the bottom margin. Photographed at area_first / 8 mm / 24 pt: the
  message asks for 0.5 mm of bottom margin where one keystroke in the other box
  does it.

  Not fixed here, for two reasons. Saying it needs a new user-facing sentence,
  which is §M's to approve before it is written into a tab, and twelve
  catalogues after that; and the sentence would only exist because of the
  0-means-4.0 reading B8-144 asks Knut and Basti to settle. Fixing B8-144 in
  any of its three ways removes this with it.

### B8-149 · The advised rise could exceed what the margin box will hold
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- found by: the third adversary round, 2026-09-14, and fixed here rather than
  left open, because a number nobody can type is the same false promise as a
  number that does not work.
- evidence: test_no_margin_the_box_holds_is_said_rather_than_asked_for; the
  round's own sweep of 1,501 reachable warning states.
- detail: the search capped the RISE at 60 mm while "Bottom" holds an ABSOLUTE
  60 (`layout_options_panel.small_mm(top=60.0)`), so **160 of 1,501** states
  named a total above it, worst 72.9 mm: the box clamps and the warning stays
  up after the reader has done exactly what it said. Every one of them was at a
  typed sheet-text size of 64 or 72 pt.

  The search is capped at `60 - the margin now` and returns nothing when
  nothing inside that clears. The message then names the largest rise the box
  holds and appends a sentence that says plainly it will not be enough on its
  own, with the two levers that do work: a smaller sheet text, or a larger
  paper. One new string, translated into all twelve catalogues.


### B8-150 · "Or print the chart on a larger paper" was false
- blocks release: yes
- status: SUPERSEDED
- superseded by: B8-179
- found by: the fourth adversary round, 2026-09-14, on a sentence added here an
  hour earlier for B8-149.
- evidence: test_the_ceiling_sentence_is_really_printed_on_the_panel (now on
  both the one-line and the two-line wording, each with a proven mutation);
  the round's `run3.log` and `A2-largest-paper-still-warns.png`.
- detail: the sentence for a sheet no margin can rescue offered two levers and
  only one of them existed. Driven on screen on the CR30 Letter preset at two
  lines of 72 pt: switching to **each of the fourteen other papers in the
  pulldown, A2 Portrait and A2 Landscape included, left the warning exactly
  where it was**. In geometry the patch bottom moves from **21.00 mm on A4 to
  21.04 mm on A2**, four times the area for four hundredths of a millimetre,
  because the bottom text is anchored on the PAPER EDGE and the patch area is
  the margin plus the engine's reserve. Neither depends on the size of the
  sheet.

  The clause is gone, and in its place the sentence says why the obvious idea
  does not work, so a reader does not spend a sheet of A2 finding out. The
  other lever it names was measured sound: at a 20 mm margin with two lines,
  72 pt down to 18 pt clears.

### B8-151 · "Raise “Bottom” under “Margins (mm)” by about 0.0 mm"
- blocks release: yes
- status: SUPERSEDED
- superseded by: B8-179
- found by: the fourth adversary round, 2026-09-14. Verbatim from the window,
  and reachable by doing what the app itself had just said: at a 55 mm margin
  it asks for 5.0 mm, you type it, and at 60 it asks for 0.0.
- evidence: test_no_advice_ever_asks_for_a_rise_of_zero, over fifteen states at
  the top of the margin range; test_the_ceiling_sentence_is_really_printed_on_the_panel.
- detail: the "no margin can do it" case was built as the ordinary message plus
  an appended sentence, so it still carried "Raise “Bottom” by about {short}",
  with `short` falling back to `min(overlap, 60 - margin)`. At the ceiling that
  is zero. It also did not name the largest rise the box holds, as its own
  comment claimed: at patch-first with a 6 mm margin it named 49.0 where the
  box had 54.0 left.

  That case has its own message now, one line and two, and names no rise at
  all: it says the box stops at 60 mm, that even that leaves the text in the
  patches, and what to do instead. The appended note is gone.

  **AND WRITING THIS DELETED THE FIX BESIDE IT.** Replacing the note meant
  slicing the file between two function definitions, and B8-146's
  `_locked_margins_note` sat between them: it went with the slice, the blanket
  `except Exception: pass` in `_engine_text_notes` swallowed the NameError, and
  **every notice on the panel went silent**. Found by disabling the swallow
  deliberately and re-running one recipe, restored from the working-tree
  backup taken at 19:49. The same trap as 2026-09-13, one file away.

### B8-152 · "The line under the pulldown says why" said nothing of the kind
- blocks release: no
- status: FIXED
- found by: the fourth adversary round, 2026-09-14, first by reading the code
  and then on screen across all six demo projects.
- evidence: test_the_help_says_the_things_a_reader_came_for (the old clause is
  in its forbidden list now, the new one in its required list);
  scripts/adv17d_the_line_under_the_pulldown.py, run5c.log,
  P5b-no-report-generated-yet.png.
- detail: `_WHEN_HELP` said of the two ISO report types *"they are greyed
  today, and the line under the pulldown says why"*. Measured in both states:
  a run that HAS reports shows "Already generated for this run: Full colour
  check (3)", and a run with none shows "No report has been generated for this
  run yet." **Six of six projects, neither state mentions the ISO types.**

  The reason really is on screen, but somewhere else: it is the disabled row's
  own tooltip inside the open list, which is where `_not_built_line` is hung.
  The sentence points there now.

  **AND THE `blurb` HALF OF THAT LINE IS DEAD CODE.**
  `_set_type_blurb(already or blurb)` can never reach `blurb`, because
  `_generated_types_line` returns the "No report has been generated" sentence
  rather than "" when a run has none. So the chosen type's own description
  never appears under the pulldown either. Raised as B8-154 rather than changed
  here: the line is Knut's "show which type of reports have been generated" and
  what else may compete for it is his call.

### B8-153 · Two geometry rebuilds per keystroke, at most one of them read
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- found by: the fourth adversary round, 2026-09-14, on screen.
- evidence: test_a_gate_is_only_asked_where_its_answer_is_read,
  test_the_call_site_hands_the_gates_over_unrun (both mutations proved red);
  scripts/adv17d_two_rebuilds_where_one_is_read.py, run4.log.
- detail: `_bottom_lever_note` has three branches and each reads at most one of
  its two gates; a "B" typed as 0 returns before either. They were passed as
  VALUES, so both ran on every refresh. Measured on Knut's CR30 preset with "B"
  at 0, stepping the bottom margin over twenty different values so nothing is
  cached: **54.9 ms per step with the gates live against 25.1 ms with them
  stubbed**, so 29.8 ms, more than the rest of the notice pass together, spent
  on two answers nobody read. They are passed as callables now and asked after
  the branch is chosen. A plain bool still works, so no existing caller or test
  had to change.

  **Re-measured with the same driver after the fix:** 36.2 ms per step against
  23.8 stubbed, so **12.4 ms**, and the call counts over twenty steps are
  `lowering_b 0, markers_off 18`. The one that remains is the gate the chosen
  branch really reads, which is honest work; the wasted one is gone.

### B8-154 · The line under the Report type pulldown can never show a type's own description
- blocks release: no
- status: OPEN
- found by: the fourth adversary round, 2026-09-14, while proving B8-152.
- evidence: `_set_type_blurb(already or blurb)` in `_sync_type_combo`, and
  `_generated_types_line`, which returns "No report has been generated for this
  run yet." rather than "" for a run with none.
- detail: so `already` is always truthy and the `blurb` branch is unreachable.
  The description of the type you have chosen is in the combo's own tooltip and
  nowhere else. Two ways out and both are Knut's call, since the line is his
  request: let the line fall back to the description when a run has no reports,
  or drop the dead branch and leave the description in the tooltip.

### B8-155 · The custom paper boxes take tenths and the recipe drops them
- blocks release: no
- status: OPEN
- found by: the fourth adversary round, 2026-09-14, while clearing its own
  suspicion that `predicted_patch_bottom_mm` goes silent on a Custom paper. It
  does not: Custom is measured and warns exactly like a named paper.
- evidence: `LayoutOptionsPanel.selection()` builds the code with
  `int(self.custom_w.value())`; typing 215.9 x 279.4 reached the engine as
  216 x 279 and moved the predicted patch bottom by 0.3 mm.
- detail: pre-existing, unrelated to this change set, and not chased. Recorded
  so the next person measuring a custom sheet is not surprised by it.

### B8-156 · "A larger paper does not help" was false on a third of the sheets that said it
- blocks release: yes
- status: SUPERSEDED
- superseded by: B8-179
- found by: the fifth adversary round, 2026-09-14, on a sentence written here
  two hours earlier to replace a DIFFERENT false claim about paper (B8-150).
- evidence: test_a_larger_paper_is_asked_of_the_sheet_before_it_is_denied;
  the round's own sweep (7 papers x 2 modes x 7 margins x 1-2 lines x 9 sizes:
  the message fired in 84 states and the claim was false in 29);
  note-A4-area_first-mb59.5-72pt.png and CLEARED-...-A3.png, driven on screen.
  **Re-measured here independently**: four states where a larger sheet really
  clears the collision (patch-first, A4 at 72 pt, two lines: A3 and A2 both
  clear) and the panel denies none of them, against sixteen where nothing
  clears and it still says so.
- detail: B8-150 replaced a false lever with an explanation, and the
  explanation was **reasoned rather than measured**. It is true that the text
  does not move with the paper, because it is anchored on the paper edge. It is
  not true that the collision cannot be cleared by a larger sheet, because the
  PATCHES are re-fitted to every sheet and can end higher on a bigger one. The
  chart-notes warning directly above it has said "or use a taller paper" all
  along, so the panel contradicted itself in one frame.

  `_larger_paper_note` asks the sheet instead: it rebuilds the layout on every
  larger paper the instrument offers and stops at the first that clears, and
  where one does, it says nothing at all. The clause is its own appended
  sentence now, lifted out of the two message strings with its translation, and
  it runs only in the branch where no margin can help.

  **The lesson is the one this project keeps relearning**: a sentence about
  what a control cannot do is a claim about the layout, and the layout answers
  questions, it does not accept arguments.

### B8-157 · The rise was measured on a sheet the reader has to leave
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- residue: one state is not fixable from a recipe and is named in the detail
- found by: the fifth adversary round, 2026-09-14.
- evidence: test_the_rise_is_measured_on_the_sheet_the_reader_can_type_in;
  STILL-WARNS-patch_first-36pt.png.
- detail: "Use instrument margins" greys all four margin boxes AND is part of
  the geometry (`margins_are_law = area_first or use_instrument_margins`), so
  the rise was worked out on a sheet whose margins are law while the only way
  to type that rise is to take the tick off, which changes the law. Measured on
  the CR30 preset: of 57 locked states naming a rise, **12 did not clear once
  the tick came off**, all patch-first, the unticked sheet always needing more
  (4.5 named where 8.5 clears). On screen, from the state the preset ships in,
  2 of 10; from a state the reader ticked themselves, 7 of 10.

  The search answers for `use_instrument_margins=False` now, which is the sheet
  the reader can actually type into. On screen the ship-state case is 0 of 10,
  area_first answers are byte-identical, and over 94 locked overlapping states
  the number changes but never which of the four messages is chosen.

  **NOT FIXABLE FROM A RECIPE, AND NAMED AS SUCH:** unticking also restores the
  other three margins from the panel's `_saved_margins`, which the recipe does
  not carry, so in that state no number the message can print is right. The
  panel recomputes the moment the tick comes off, which is the mitigation.

### B8-158 · A marker box typed 0 is 2.0 mm on the sheet and was 0.0 in the warning
- blocks release: no
- status: FIXED
- residue: the bottom checks only; the top and side checks are reported, not swept
- found by: the fifth adversary round, 2026-09-14. **Inherited from HEAD, not
  introduced by this change set.**
- evidence: test_a_marker_box_typed_zero_is_read_as_the_engine_reads_it; P6 on
  screen, and the two sheets rendered through the kwargs `build_chart` itself
  passes.
- detail: `build_kwargs` sends `helper_marker_edge_mm or 2.0` and
  `helper_marker_len_mm or 2.0`, so a box typed 0 draws 2.0 mm, while every
  warning read the recipe field raw. The panel predicted a 1.00 mm reserve
  where the engine holds back 5.00, and the 0/0 sheet and the 2/2 sheet render
  identically, ink 6.48 to 13.46 mm in each. **91 reachable states where the
  bottom check is silent while the engine's own reserve says the block reaches
  the patches.** `_marker_reserve_args` is now used by the two gates and both
  bottom checks. The top and side checks still read the fields raw: reported,
  following the convention B8-146 set, rather than swept mid-release.

  The box that accepts 0 and draws 2 is a layout question rather than a warning
  question, and it is left for Basti and Knut, beside B8-144 and B8-155.

### B8-159 · "The greyed entry itself says why" was the second wrong place
- blocks release: no
- status: FIXED
- found by: the fifth adversary round, 2026-09-14, on the sentence written for
  B8-152 an hour earlier.
- evidence: test_the_help_says_the_things_a_reader_came_for (both earlier
  wordings are in its forbidden list now); the round's on-screen hover test.
- detail: B8-152 moved the claim off the line under the pulldown and onto the
  greyed row. Driven on screen, the greyed row's own TEXT is just the type's
  name, "Validation print check (ISO 12647-8)", and says nothing about why; the
  reason arrives as a TOOLTIP when the pointer rests on it. So the sentence now
  says that pointing at the greyed entry is what tells you. Third wording, and
  each one was measured rather than argued.

### B8-160 · The larger-paper loop filtered by area, and the collision is decided by height
- blocks release: yes
- status: SUPERSEDED
- superseded by: B8-179
- found by: the sixth adversary round, 2026-09-14, on the fix the FIFTH round
  wrote two hours earlier for B8-156.
- evidence: test_a_larger_paper_is_asked_about_by_size_not_by_area;
  scripts/adv17f_three_faults_on_screen.py, P1-A2-landscape-denies-*.png and
  P1-CLEARED-by-A2.png. **Re-measured here**: on A2 landscape the CR30 offers
  A3+ portrait, which is 36 % SMALLER by area and 63 mm TALLER, and it clears
  the collision; the panel no longer denies it.
- detail: `_larger_paper_note` skipped any candidate whose `w * h` was not
  greater than the current sheet's. Nothing in the pulldown is larger than A2
  landscape by area, so on that sheet the loop ran over an empty list and the
  sentence was exactly the unchecked assertion it had been written to remove.
  A headless sweep found **44 reachable states** falsified by a paper the area
  test skips, including A3+ portrait and Tabloid. The corroboration is that the
  branch cost 4.2 ms where a real pass costs 8.8 to 21.5: it was doing nothing.

  A candidate is skipped now only when it is no larger on **both** sides.

  **AND ROUND 5'S OWN TEST COULD NEVER HAVE CAUGHT IT**, because its helper
  re-implemented the same area filter: the fake re-implemented the code and
  validated it. That trap is in this project's memory under
  `feedback_a_fake_that_reimplements_validates_itself`, and it has now cost two
  rounds in one evening.

### B8-161 · The width warning's two remedies are ungated
- blocks release: no
- status: OPEN
- found by: the sixth adversary round, 2026-09-14.
- evidence: P2-width-warning-clip-4-0.png and
  P2-width-warning-clip-0-1-UNCHANGED.png, driven on screen; a sweep of
  reachable warning states.
- detail: the bottom-text WIDTH message offers "lower Clip under Text distance
  from edge (mm)" and "try another Alignment", and neither is asked of the
  sheet. The side reserve is the LARGER of "Clip", the ruler markers' reach,
  the clip border and the margin, so once another of those wins, winding Clip
  down changes nothing. Measured on i1/A4 with markers at 4 + 2: Clip at 4.0,
  2.0, 1.0, 0.5 and 0.1 all leave the reported room at **177 mm** and the
  warning up. **368 reachable states** where lowering Clip to 0.1 moves the room
  by exactly 0.00 mm, every one of them with the markers on, which is Knut's own
  #182 case; in **324** of those no alignment clears it either, so both remedies
  in that sentence are dead at once.

  Not fixed here on purpose: gating a clause inside a fully translated sentence
  means splitting the string across twelve catalogues, and new user-facing text
  is governed by §M-PROPOSED. It is the same fault the three sibling sentences
  were gated for, so it should be done, but it is Basti's and Knut's call.

### B8-162 · The strip-letter check read the marker boxes raw
- blocks release: no
- status: FIXED
- found by: the sixth adversary round, 2026-09-14, extending B8-158 to the
  call sites round 5 had deliberately left.
- evidence: test_no_notice_reads_a_marker_box_raw,
  test_the_strip_letters_are_judged_with_the_markers_the_engine_draws;
  P3b-BEFORE-the-fix.png and P3b-AFTER-the-fix.png.
- detail: with both marker boxes typed 0 the engine draws 2 mm and
  `geometry.strip_label_reserve_mm` puts the label band 5.0 mm down, while the
  panel asked for 0 + 0 + 1 = 1.0. Measured on i1/A4 with an 8.0 mm top margin:
  the band reaches 9.91 mm and the first patch row starts at 9.00, so **0.91 mm
  of every strip letter sits on the first row of patches** and the panel said
  nothing; 15 such states in a sweep. All four remaining raw reads now go
  through `_marker_reserve_args`, including the "lowering Clip would also do it"
  gate, which was misfiring for the same reason.

  Reported honestly by the round: with a live preview report the panel uses the
  measured patch-ink top, which on the honeycomb presets sits below the
  placement box, so the collision does not arise there. It is reachable through
  the info icon and on rectangular-patch sheets, which is where it was measured.

### B8-163 · The live preview drew no helper markers where the sheet carried 44
- blocks release: yes
- status: FIXED
- found by: the seventh adversary round, 2026-09-14. **Inherited from HEAD**,
  not from this change set, and it is the same `or 2.0` convention as B8-158
  and B8-162, on the one surface that claims to be the picture.
- evidence:
  test_no_raw_marker_read_survives_anywhere_in_the_panel (the source rule now
  covers both overlay branches, and the mutation that defeated the old guard
  was proved red here),.
  **Stated honestly: the overlay itself has no unit test.** The function needs a
  live panel and a .ti2 on disk, so what guards it is the source rule plus the
  on-screen driver below, which counts dashes on the overlay and on the sheet
  and compares them.
  Driven on screen with scripts/adv17g_the_overlay_and_the_note.py:
  F2-boxes-2-2-overlay-88-sheet-88.png,
  F2-after-Generate-overlay-empty-sheet-inked.png, and a crop of the app's own
  TIFF, F2-the-real-tiff-top-10mm-boxes-typed-0.png, with the tick row plainly
  above the strip letters. **Re-driven here after the fix: boxes at 0.0/0.0
  now give overlay 88 dashes against sheet 88, where they gave 0 against 88.**
- detail: `_helper_marker_lines_frac` read `helper_marker_edge_mm` and
  `helper_marker_len_mm` raw, in both the Manual and the Guided branch, while
  `build_kwargs` sends `... or 2.0`. So with both boxes typed 0 the overlay drew
  nothing at all and the sheet printed 2 mm dashes at 2 mm from the edge, and
  the caption did not say "press Generate Chart": the app was asserting that
  what you see IS the ink. Both branches read the engine's values now, through
  `_marker_reserve_args` and the named `_MARKER_DEFAULT_MM`.

  **This is the symptom shape of Knut's #152**, the overlay and the sheet
  disagreeing about dashes, and it is worth telling him it is fixed here.

### B8-164 · Three of the four marker call sites were guarded by a spelling
- blocks release: no
- status: FIXED
- found by: the seventh adversary round, 2026-09-14, attacking round 6's tests
  rather than round 6's code.
- evidence: (a
  behavioural guard) and the rewritten
  test_no_raw_marker_read_survives_anywhere_in_the_panel; both mutations proved
  red, including the exact spelling that defeated the old guard.
- detail: `test_no_notice_reads_a_marker_box_raw` matched `getattr(r,` on the
  line, so the same read written as a plain attribute passed it: the round
  rewrote three call sites that way and the file stayed green, 31 passed each
  time. Worse, the site inside `_bottom_clears_with` was guarded by **nothing**,
  and the raw read there flips `lowering_b_clears` in **5 of 140** reachable
  states, every one of them to True, which is the "lower B and it clears"
  promise this whole block exists to stop making. The `_eff_edge` site changed
  the panel's notices in **384 of 768** grid states and was caught only by the
  grep.

  There are two guards now: a behavioural one that asks the gates whether a box
  typed 0 answers as a box typed 2.0 does, and a source rule that bans a read of
  either field anywhere in the module unless the line also says what a 0 means.

### B8-165 · The stamper is handed a different marker reserve from the one the panel prints
- blocks release: no
- status: OPEN
- found by: the seventh adversary round, 2026-09-14.
- evidence: `workflow/chart_creator.py:1858-1867` and `:1968-1969` pass
  `getattr(_rec, "helper_marker_edge_mm", 0.0) or 0.0` into `side_text_edge_mm`
  and `edge_reserve_mm`; measured in the real app, the panel computes 5.00 mm
  for a recipe where `chart_creator` hands the stamper 1.00 mm, and the panel
  prints its number in the message ("printed 5.0 mm in from the paper edge").
  On the app's own sheet, feeding the stamper the two competing numbers moves
  real ink by **4.07 mm**.
- detail: left open on purpose. Aligning the stamper with the engine changes
  where ink lands on a printed sheet, which is not a change to slip into a beta
  overnight, and the round was honest about the limit of its own evidence: in
  the non-packing path the ink did not move across twenty states, and in the
  packing state it reached, the raw placement still cleared the dashes by
  0.33 mm. So: a proven divergence, proven ink movement, harm not yet
  demonstrated. Knut and Basti decide.

### B8-166 · The "press Generate Chart" caption could never be cleared on a sheet built with a marker box at 0
- blocks release: yes
- status: FIXED
- found by: the eighth adversary round, 2026-09-15, attacking B8-163's own fix.
  **Introduced by this change set**, not inherited: the `or 2.0` that B8-163
  added to the CONTROLS was not added to the SHEET's side of the same
  comparison.
- evidence: test_a_sheet_built_with_a_box_at_zero_is_not_a_proposal (mutation
  proved red: removing the coercion on the `printed` side puts the caption
  back). Driven on screen with
  scripts/adv18b_the_caption_that_cannot_be_cleared.py:
  F1-after-one-Generate-caption-still-on.png shows the dashes in the accent
  colour under "Not on this sheet yet" on a chart generated one second earlier
  with exactly those markers; F1-after-a-second-Generate-caption-still-on.png
  shows a second Generate not clearing it; and
  F1-control-generated-at-2-2-no-caption.png is the same 214 dashes in plain
  black with no caption.
- detail: `_helper_marker_lines_frac` compares `wanted`, read off the controls
  through `_MARKER_DEFAULT_MM`, against `printed`, read off the chart's own
  recipe raw. `LayoutRecipe.to_dict` is `asdict`, so `channels.json` stores the
  0.0 that was typed while the sheet was drawn with the 2.0 `build_kwargs`
  substituted. 0.0 != 2.0, so `pending` was true for ever: a second Generate
  writes 0.0 again, and no value the two boxes can hold clears it, because the
  left-hand side can never be 0.0. Measured over six box values and two
  Generates, all True; the control at 2.0/2.0, False. The `printed` side now
  reads the sheet through `_marker_reserve_args` as well.

### B8-167 · B8-163's fix was guarded by nothing at all
- blocks release: no
- status: FIXED
- found by: the eighth adversary round, 2026-09-15.
- evidence: test_a_box_typed_zero_draws_the_dashes_the_engine_draws (mutation
  proved red). Before it: reverting the two `or _MARKER_DEFAULT_MM` in the
  Manual branch left the everyday tier at **14,617 passed, exit 0**.
- detail: B8-163's own evidence line says so ("the overlay itself has no unit
  test") and named the source rule and a driver in its place. A source rule
  cannot see that branch: it reads `panel.helper_marker_edge.value()`, which
  carries neither field name, so the rule's FIELDS never match the line. The
  new test builds the same chart twice, once with both boxes at 0 and once at
  2.0, and requires the overlay to put the dashes in the same places -- which
  is what the engine does with them. It also pins `_MARKER_DEFAULT_MM` itself:
  moving the engine's default to 3.0 while leaving the constant at 2.0 turns it
  red, which nothing did before.

### B8-168 · The source rule's "dict key" exemption swallowed every getattr read
- blocks release: no
- status: FIXED
- found by: the eighth adversary round, 2026-09-15, attacking B8-164's
  replacement rule the way B8-164 attacked the one before it.
- evidence: test_no_raw_marker_read_survives_anywhere_in_the_panel (the
  exemption now wants a colon, or a line that says `_settings.`; the mutation
  below was proved red against the tightened rule and green against the old
  one). Driven on screen with
  scripts/adv18c_the_guided_branch_on_a_manual_sheet.py.
- detail: the exemption was `["']field["']\s*[:,)]`, which matches a dict key
  AND every `getattr(obj, "helper_marker_edge_mm", 0.0)` -- the exact spelling
  the original fault was written in. `test_no_notice_reads_a_marker_box_raw`
  cannot cover for it: it is scoped to `_engine_text_notes`, and it matches the
  literal `getattr(r,`, so `getattr(rec,` is invisible to it as well. Put
  `float(getattr(rec, "helper_marker_edge_mm", 0.0) or 0.0)` into the overlay's
  GUIDED branch -- which is live whenever a chart built in Manual is on screen
  and GUIDED is pressed -- and the preview went from the sheet's own **214
  dashes to none**, measured in the real window, while the everyday tier came
  back **14,619 passed, exit 0**.

### B8-169 · The new warning named a margin box that six languages do not have
- blocks release: no
- status: FIXED
- found by: the ninth adversary round, 2026-09-15, attacking the twelve
  catalogues the change set itself re-translated. **Introduced by this change
  set**: every one of the strings it replaced named the box correctly.
- evidence: test_every_language_names_the_margin_box_as_that_language_shows_it
  (12 cases, one per catalogue). Mutation proved to land: putting «Nederst»
  back into `no.json` turns it red for `no` alone, 11 others green. Re-measured
  here independently of the round: 12 languages x 4 messages, 0 problems after
  the fix. Driven in the real window in Norwegian and photographed in Chinese.
- detail: the two "raise the bottom margin" wordings were rewritten and
  re-translated, and in **it, no, pl, ru, sv** the translation named a word
  that is not on the box, while in **zh_CN** all four new wordings named 「下」,
  which is what that same window calls the **"B"** box under "Text distance
  from edge (mm)" -- and the next sentence of the same notice uses 「下」 in
  exactly that other sense. A reader following the advice would have hunted for
  a control that is not there, or turned the wrong one.

  | | the window labels the box | the message said | now |
  |---|---|---|---|
  | it | Basso | *Inferiore* | Basso |
  | no | Bunn | *Nederst* | Bunn |
  | pl | Dół | *Dolny* | Dół |
  | ru | Низ | *Снизу* | Низ |
  | sv | Nederkant | *Nederst* | Nederkant |
  | zh_CN | 底部 (B = 下) | *下*, all four | 底部 |

  This is the third time in one beta that a promise named a control by a word
  the reader's own window does not use (B8-142 for the German set names, B8-136
  for the help paragraphs). The guard written for those was scoped to the three
  report-help paragraphs, so it had nothing to say about the chart warnings
  edited in the same change set. The new guard reads each language's own
  `Bottom` label out of its own catalogue and looks for it in all four
  messages.

### B8-170 · The source rule was defeated by an ordinary line wrap
- blocks release: no
- status: FIXED
- found by: the ninth adversary round, 2026-09-15, attacking B8-168's
  replacement rule the way B8-168 attacked B8-164's, which attacked the one
  before that. Third generation of the same rule, third hole.
- evidence: test_no_raw_marker_read_survives_anywhere_in_the_panel, now walking
  STATEMENTS (`_logical_lines`) rather than physical lines. Three mutations
  proved to land here, each red with the fix and the tree restored byte for
  byte afterwards: the wrapped `getattr` spelling (**green before this fix**),
  the single-line plain attribute, and a subscript read through `to_dict()`.
  The four affected test files: 96 passed.
- detail: the rule exempted a line whose `.strip()` starts with a quote as
  "prose naming the field". Wrap the read the way a formatter would and the
  continuation line starts with the quoted field name::

      edge_mm = float(getattr(rec,
                              "helper_marker_edge_mm", 0.0) or 0.0)

  Round 9 put that spelling into the overlay's Guided branch: three test files
  came back **57 passed** and the Guided overlay drew **0 dashes on a sheet
  carrying 214**, which is B8-162 back with nothing said.

  Joining each statement onto one line closes it by construction, because the
  text a rule sees now starts where the statement starts, and a
  `_marker_reserve_args` two lines down still exempts the read it belongs to.
  Comments are stripped, so a SAFE word in a trailing comment can no longer
  exempt the code beside it. The dict-key and settings-key exemptions were
  replaced by the sentence they were both instances of: **a name is not a
  read**, so where the field appears only as a quoted string and the statement
  never reaches through an object for it, there is no box being read. A
  subscript is a read and stays in.

### B8-171 · "No bottom margin will clear it", and 36.5 mm clears it
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- found by: the tenth adversary round, 2026-09-15, sweeping the warning states
  round 9 had not reached. **Introduced by this change set**: neither
  `margin_rise_that_clears_mm` nor the two "no bottom margin" wordings exist in
  `git show HEAD:ui/tabs/tab_chart.py`.
- evidence: test_a_ceiling_that_cannot_be_built_does_not_deny_every_margin_below_it.
  Mutation proved to land here as well as by the round: putting `return None`
  back gives `assert None is not None`, and the tree restored byte for byte
  after. Driven on screen, i1Pro, Paper = Custom 62 x 88 mm, patch-first,
  markers on at 4.0 + 2.0 mm, two lines at 36 pt over a 6 mm bottom margin, the
  chart really built and the wording read back off the "Measured from Preview"
  field; photographed both ways, four warnings against three.
- detail: one line decided it,

      if _bracket >= cap_mm and not clears(cap_mm): return None

  which reads the largest rise the box holds as a verdict on every smaller one,
  on a predicate the same function documents twenty lines below as **not
  monotone** (B8-143: 9.7 clears, 9.8 does not, 9.9 clears again). On a small
  paper the ceiling is not merely worse than the answer, it cannot be laid out
  at all, so the single probe that failed denied everything under it. The
  reader was told to shrink their sheet text or throw a line away while typing
  36.5 into the box they were looking at fixed it, and so did every grid point
  to 47.0.

  The grid is walked before anything is denied now, with B8-143's own stability
  rule and through the existing memo, and only in the branch that was about to
  give up. Measured in the real window with a fresh margin every turn: the
  whole notice pass is **29.5 ms** where the walk finds an answer and **45.2 ms**
  where all 120 grid points are probed, against the 120 to 210 ms B8-145 was
  raised for.

  The round's own first sweep reported 14 of these and corrected itself to one:
  a candidate margin that raises `LayoutError` produces no notices at all,
  which a naive predicate reads as "cleared". Same shape as
  [[feedback_a_perfect_result_can_be_the_bug]].

### B8-172 · Round 9's rewritten marker rule still waved four spellings through
- blocks release: no
- status: FIXED
- found by: the tenth adversary round, 2026-09-15, attacking B8-170 the way
  B8-170 attacked B8-168, which attacked B8-164. Fourth generation.
- evidence: test_no_raw_marker_read_survives_a_rule_that_reads_the_code, with 8
  parametrised "must catch" cases (every spelling that has ever got through)
  and 6 "must not catch" ones. Proved end to end: `float(asdict(rec).get(
  "helper_marker_edge_mm", 0.0) or 0.0)` in the live Guided branch left **147
  marker tests and B8-170's own rule green**, and only the new rule red.
- detail: the four spellings were `r.__dict__.get(...)`, `asdict(r).get(...)`,
  `operator.attrgetter(...)(r)`, and the one that matters:

      replace(r, helper_marker_edge_mm=float(r.helper_marker_edge_mm or 0.0))

  exempted whole by the `helper_marker_edge_mm\s*=` rule that exists to let a
  recipe be BUILT. A statement can build one and read a box in the same breath.

  The new rule asks the code through its AST rather than its text: an attribute
  load of the field, a subscript by its name, or its name handed to something
  that looks a value up. Dict keys, key tuples, settings keys, recipe-building
  keywords and plain writes are exempt by construction rather than by a
  pattern. Both sibling rules are kept.

  **Reported, not fixed:** a local alias (`_F = "helper_marker_edge_mm"` then
  `getattr(r, _F)`) leaves no field name in the reading statement, and no
  source rule without dataflow can see it. The behavioural guard
  `test_the_gates_answer_with_the_markers_the_engine_draws` is the only thing
  that speaks for a read in another module.

### B8-173 · Three help claims were checked as phrases, never as facts
- blocks release: no
- status: FIXED
- found by: the tenth adversary round, 2026-09-15.
- evidence: test_the_three_claims_nothing_was_reading_out_of_the_code.
- detail: `test_the_help_says_the_things_a_reader_came_for` asked that the words
  "eight grey steps" appear in the paragraph; nothing tied the eight to
  `GREY_MIN_LEVELS`. Same for "the two ISO types are greyed today" and
  "Printing record grades nothing". All three are true on 2026-09-15, so this
  is a guard gap rather than a fault, but it is the kind that goes stale in
  silence, in twelve languages, the day a constant moves.

### B8-174 · FROM PROFILE GAMUT heard none of the panel's text warnings
- blocks release: no
- status: FIXED
- found by: the eleventh adversary round, 2026-09-15, driving the same chart
  through all three modules. **Inherited**, in the sense that the gate predates
  this change set; what this change set did is fill the method behind it with
  the four bottom wordings, the rise search, `_larger_paper_note` and
  `_locked_margins_note`, every one of which was silent there.
- evidence: test_manual_says_it, test_the_gamut_module_says_it_too,
  test_guided_still_says_nothing, test_the_gate_asks_the_mode_and_not_the_button
  (the Manual control, the gamut case, Guided must stay silent, and the
  spelling). Mutation proved to land here as well as by the round: restoring
  `self._manual_btn.isChecked()` turns 2 of the 4 red, and the tree came back
  byte for byte. Driven on screen and photographed three ways on one chart:
  MANUAL 3 notices, FROM PROFILE GAMUT 0, MANUAL again 3.
- detail: `_engine_text_notes` asked `self._manual_btn.isChecked()`, and
  `_switch_mode("gamut")` unchecks that button. The module's own margin, sheet
  text and marker boxes are on screen and editable, the chart is built from
  them and "Measured from Preview" reports the sheet, so a reader there had
  every reason to expect the warning and got silence. The gate asks
  `_current_mode() == "manual"` now, which is the question it was really
  asking; `_helper_marker_lines_frac`, eighty lines further down the same file,
  already spends twelve lines of comment on this exact trap.

  **Seven other sites in the file ask `_manual_btn.isChecked()`**
  (`current_layout_combo`, `_active_instrument_flag`, `_active_paper_code`,
  `_suggest_target_name` among them). Same latent shape, outside this change
  set, each needing its own judgement. Reported, not swept.

  Two hardenings came with it, neither a fault today. The AST marker rule was
  blind to a lookup whose name comes from a variable while the statement still
  spells the field out, which is not exotic: `tab_chart.py:22008` already
  writes `tuple(getattr(rec, k) for k in self._HM_KEYS)`, so it is the shape
  the next raw read arrives in. And "Grey and tone check keeps three rows" was
  asserted as a phrase; it is pinned to the three row ids now.

- and the round corrected itself twice, both times the same shape as
  [[feedback_a_perfect_result_can_be_the_bug]]: 11 false "no margin clears it"
  reports came from measuring the line box with PIL's fallback font where the
  panel uses the recipe's own (2 mm of difference at the same Size), and 1,292
  false "lever fails" reports came from holding the text block at its old
  anchor while lowering "B". Re-run correctly: 0 of 435 and 0 of 10,301.

### B8-175 · The stamp prediction named the layout, and the sheet stamped targen

- blocks release: no
- status: FIXED
- found by: adversary round 22, 2026-09-15, on screen in a real window, the
  rendered TIFF's own right-hand strip cropped and read
  (`~/Desktop/ChromIQ-adversary-22-2026-09-15/C-second-right-margin-tail.png`).
  Drivers `scripts/adv22c_press_generate_twice_and_the_warning_changes.py`
  (both stamped lines, both crops) and
  `scripts/adv22d_the_margin_where_the_panel_says_nothing.py` (49 right margins
  from 6.0 to 30.0 mm).
- evidence:
  test_an_ordinary_manual_build_predicts_the_targen_line,
  test_guided_predicts_the_targen_line,
  test_the_gamut_module_predicts_a_layout_name,
  test_a_bundled_patch_set_preset_predicts_its_layout_name,
  test_a_loaded_patch_set_predicts_its_layout_name,
  test_an_edited_recipe_falls_back_to_the_targen_line,
  test_a_loaded_patch_set_keeps_its_name_while_the_panel_is_locked,
  test_the_prediction_asks_the_predicate_not_the_label,
  test_the_predicate_never_answers_from_the_ti1_path_alone,
  test_the_prediction_sets_the_layout_name_the_build_sets.
  Restoring `self._active_layout_name()` at the call site turns 7 of them red.
- detail: WHAT A USER SEES. On i1Pro / A4, Sheet text Size 14 pt, right margin
  12 mm, "Stamp settings down the right edge" on and Chart Notes reading
  "Canon Pro-1000 / Photo Rag 308", the rendered sheet's right-hand line ends

      … | ChromIQ layout engine | ChromI…

  15 characters cut and replaced by an ellipsis, and the "Measured from
  Preview" panel says **nothing at all** about it. Swept at every right margin
  from 6.0 to 30.0 mm in half-millimetre steps: 49 of 49 silent, and 49 of 49
  cutting.

  THE CAUSE. `_engine_text_notes` predicts the stamped line by building it
  itself, and B8-153 (2026-09-13, Knut's ColorMunki report) added
  `_pm.chart_layout_name = self._active_layout_name()` so a chart laid out from
  an armed patch set would predict "Chart layout <name>" rather than a targen
  command the sheet never prints. That was right for the case it was written
  for and wrong everywhere else: `_active_layout_name()` falls back to
  `Path(self._current_ti1_path).stem`, and `_on_generate_finished` sets
  `_current_ti1_path` after EVERY build, an ordinary targen build included,
  while the build itself only carries a layout name down the
  `_generate_from_ti1` route. So from a user's first Manual build onwards the
  panel measured

      Canon Pro-1000 / Photo Rag 308 | Chart layout adv22c | …          122 ch

  for a sheet that stamps

      Canon Pro-1000 / Photo Rag 308 | targen -d2 -f609 -e4 -B4 -G -g35 adv22c | …   145 ch

  and the "Measured from Preview" frame only has something to measure once a
  chart exists, so this is the state the notice is nearly always read in.

  THE FIX. `_predicted_chart_layout_name` mirrors the branches `_on_generate`
  really takes, the way `_pending_patch_set_total` already mirrors them for the
  patch count: the gamut module and every from-.ti1 route answer with
  `_active_layout_name()`, and everything else answers None. Measured on screen
  afterwards on both sides: an ordinary targen build now says "the last 15
  characters are cut off", which is exactly what the photograph shows, and
  selecting a bundled Knut preset still answers
  "ColorMunki-A4-84p-1page-Portrait-Fast Reading Speed-Hand Held-w26.0mm", so
  B8-153 stays fixed.

- also driven and found clean in the same round, listed so nobody re-runs it:
  the FROM PROFILE GAMUT module's recipe against MANUAL's on one layout (every
  field identical, paper to clip border); the remedy named there typed in and
  the notice clearing, with 0.6 mm less still warning; Guided (silent, and its
  layout panel is not on screen at all, so there is no lever for a notice to
  name); the warning across a paper switch to A3 and back and across a run-type
  switch to Verification and back, the stated rise exact in every one; and the
  quoted control names in all twelve catalogues, 16 messages each, 0 naming a
  box by words its own UI does not use.

### B8-176 · Move a margin box and the warning under it does not move (INHERITED)
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-179
- found by: adversary round 23 (2026-09-15), on screen in the real window,
  `scripts/adv23e_the_notice_after_every_gesture.py`; cost measured before the
  fix by `scripts/adv23f_what_a_panel_refresh_costs.py`
- INHERITED, NOT THIS CHANGE SET. The same driver run in a worktree at
  v4.3.0-beta.16 gives the same count, 8 of 11, with beta 16's own wording. The
  bottom-text work of this round put new sentences on a frame that was already
  frozen; it did not freeze it.
- detail: WHAT A USER SEES. i1Pro, A4, one line of sheet text at 24 pt, bottom
  margin 8 mm, one real Generate, then eleven real keyboard and mouse gestures
  on the boxes. In **8 of them** the sentence the "Measured from Preview" frame
  was really showing was not the sentence the state had earned:
  * holding Up until "Bottom" reads 14.0 mm, which is past the 5.5 mm rise the
    message itself asks for, leaves the red warning standing word for word;
  * pasting 20 into the box, and tabbing out of it, likewise;
  * typing 60 into Size leaves it saying the text needs 10.3 mm of room where
    the state needs 25.7.
  The frame only comes back to life on the next Generate, so the app tells you
  to do something, you do it, and the app goes on saying it.
- cause: `_refresh_manual_command_preview` is the single hook every targen row,
  every printtarg row and the whole layout panel routes through, and it called
  `_maybe_schedule_auto_preview` (which does nothing unless the user has opted
  into the live preview, and `auto_update_preview` ships **False**) and
  `_refresh_unapplied_warning` (a different label). Nothing asked the panel for
  a fresh report. `_on_chart_settings_touched` was given exactly this call on
  2026-09-13 for the chart-notes box and the stamp tick, with its docstring
  recording the same measurement ("toggling the tick, 0 refreshes, six times
  out of six"); the other twenty controls were left behind.
- fix: the same two lines in `_refresh_manual_command_preview`, behind the same
  `_margin_tiffs` guard, so a keystroke before anything is built still costs
  nothing. Re-driven afterwards: **0 of 11**.
- cost, measured BEFORE it was added, because this hook fires on every
  keystroke: one refresh is 8.5 to 20.3 ms median over both layout modes, with
  and without sheet text, at 24 and 72 pt; worst single pass 63.7 ms. The
  sibling call was accepted at 17.2 ms.
- evidence: test_a_layout_change_repaints_the_measured_from_preview_frame,
  test_the_layout_panel_really_routes_through_that_hook,
  test_the_refresh_is_guarded_on_there_being_a_chart.
  Deleting the call turns 2 of the 3 red.

### B8-177 · The beta 17 release notes re-assert a claim the same entry says was wrong
- blocks release: no
- status: FIXED
- found by: adversary round 23 (2026-09-15), reading the changelog against the
  window, `scripts/adv23d_the_report_help_in_three_languages.py`
- INTRODUCED BY THIS CHANGE SET.
- detail: WHAT A USER SEES. `CHANGELOG.md`'s v4.3.0-beta.17 entry becomes the
  GitHub Release body verbatim (`build-release.yml`, `build-windows.yml`,
  `build-linux.yml` all `awk` it out by tag), so it is the first thing a tester
  reads. Its **Fixed** section says one of the help text's own claims was wrong
  and is now measured: *"an ordinary test chart does not simply read N-A on the
  paper and solid rows, because a ChromIQ set puts no limit on them and they
  are dropped from the table instead"*. Its **Changed** section, further down
  and therefore the last word, says *"An ordinary test chart has no aim values,
  and those rows read N-A."* The shipped help text (`_CHART_HELP`) says the
  corrected version, so the release notes also misdescribe the change they are
  announcing.
- measured, on screen, in the real Measurement Report window on a project with
  five dated verifications: Full colour check on ChromIQ default lists seven
  rows and `substrate_de00_max` and `solids_de00_max` are **not among them**,
  and the note under the results names only the two grey rows. They read N-A
  only under a Custom ISO set, which is not the default and not the set the
  same paragraph pairs those two report types with.
- fix: the Changed bullet now carries the measured sentence, the same one the
  help text carries.
- evidence: test_the_changelog_does_not_contradict_the_help_it_describes,
  test_the_help_says_a_chromiq_set_drops_those_rows_rather_than_n_a.

### B8-178 · 57 GB of temp folders the sweep was not allowed to recognise
- blocks release: no
- status: FIXED
- found by: Basti, 2026-09-15, after the beta 17 tag: *"there should be around
  80gb of files from this session still being around ... something is filling
  up my space during those sessions"*. Measured on his machine, not inferred.
- evidence: test_no_test_file_makes_a_temp_folder_the_sweep_cannot_see (826
  parametrised cases, one per test file),
  test_the_drivers_in_scripts_do_the_same. Mutation proved to land: a bare
  `tempfile.mkdtemp()` written into any test file turns it red, and the tree
  restored byte for byte afterwards.
- detail: `$TMPDIR` held **62 GB in 29,759 entries**, and 57 GB of it sat in
  27,600 folders named `tmpXXXXXXXX`. The two big groups: **1,150 folders
  holding one 143 MB `s.tif` each, 53 GB**, from
  `test_the_note_does_not_depend_on_the_resolution.py` building an A4 sheet at
  six resolutions, and **1,053 folders of help-card PDFs, 3.9 GB**.

  This is [[project_the_suite_leaked_198gb_of_temp]] again, through the door
  that fix deliberately left ajar. `_sweep_stale_temp_dirs` may not judge an
  unprefixed folder BY NAME, because `tmp*` is what every application's
  `mkdtemp` produces, so it judges by CONTENTS and fails closed. A folder
  holding one `.tif`, or forty-two `.pdf`s, carries none of the markers it
  knows (`.ti1 .ti2 .ti3 .cht .cie .icc .cal`, `project.json`, `meta.json`),
  so it was left where it was, for ever. Both halves of that were right; the
  half that was missing is that a test may not create a folder the sweep is
  not allowed to recognise.

  **38 call sites in 24 test files and 1 driver** now pass
  `prefix="chromiq-test-"`, which the sweep takes by name. The one file that
  must keep calling `mkdtemp()` bare is
  `test_the_sweep_sees_an_unprefixed_temp_folder.py`, whose whole subject is
  the contents rule; it is exempt by name.

  Measured after the fix: a full everyday tier leaves **244 prefixed folders**
  and the next run's sweep reports *"removed this run's temp files (1.94 GB)"*.
  Bounded at one run instead of unbounded. Freed on his disk: **61 GB**, from
  562 to 623 GB.

### B8-179 · The bottom text crashed into a hexagon row and the panel said nothing
- blocks release: no
- status: FIXED
- found by: Knut, 2026-09-15, testing v4.3.0-beta.17 (#182, comment
  5679470670), with his chart, his log and his rendered sheet attached:
  *"Attached image shows bottom text crashes into bottom margins without
  message ... Bottom margin is 13,0mmm but measured bottom in Measured from
  Preview is 15.8."*
- evidence:
  test_the_panel_measures_the_patch_bottom_rather_than_predicting_it,
  test_his_own_chart_is_warned_about_now_and_was_not_before,
  test_the_measured_bottom_on_his_own_chart_is_the_number_he_quoted,
  test_the_bottom_message_quotes_the_measured_patch_edge,
  test_the_bottom_check_is_silent_before_a_chart_is_generated,
  test_no_bottom_message_names_a_rise_or_a_paper_any_more,
  test_a_layout_change_does_not_remeasure_the_frame,
  test_the_notes_box_and_the_stamp_tick_leave_it_alone_too,
  test_the_red_press_generate_sentence_is_what_moves_instead,
  test_no_hook_on_a_keystroke_calls_the_margin_inspector.
  His own `channels.json` is in the tree as
  `tests/fixtures/charts/knut_cr30_a4_hex_bottom_text.channels.json`, so the
  15.822 mm is read from his chart and not quoted from a report.
- detail: WHAT A USER SEES. CR30, A4, area-first, **hexagonal** patches, layout
  engine on, bottom margin 13.0 mm, "B" 10.0 mm, ruler helper markers top and
  bottom at 4.0 + 2.0, Size auto, a ten-placeholder custom line with "Stamp
  layout summary along the bottom" on, so two lines, 200 dpi. The first line
  is printed straight through the lower apexes of the last hexagon row, and
  the "Measured from Preview" frame says nothing at all.

  **THE WHOLE FAULT IS ONE SUBTRACTION.** `predicted_patch_bottom_mm` ran
  `geometry.compute` and `geometry.placement` and answered **18.60 mm**, so the
  panel believed 8.60 mm of room for 8.38 mm of text.
  `margin_inspector.measure_from_engine` answers **15.822 mm**, which is the
  15.8 Knut read off the frame, and against that the block is 2.56 mm short.
  A flat-top honeycomb's last row hangs below the grid box `compute` returns,
  so a prediction built out of those two functions cannot see it. Measured off
  his own TIFF at 200 dpi: the bottom markers run 4.06 to 6.22 mm, and from
  10.16 mm (the "B" anchor) upward the ink is unbroken, so there is no clear
  paper anywhere between the text and the patches.
- Knut's ruling, which is what was built rather than a patch to the
  prediction: *"the calculations should use the Measured from Preview numbers
  in the calculations if text fit. This simplifies very much the calculation
  and it does not need to calculate across many page sizes or other searches,
  and does not need to do this every time a setting is changed ... Measured
  from Preview margin values are reliably calculated for all instrument types,
  all patch types and for all dpi and page sizes) and thus most reliable to use
  in the calculations of space in margins, and if text falls on the patch area
  edges or not (on all sides). However, they are only usable after the Measured
  from Preview margin values have been completed (after a Generate Chart has
  been performed)."*
- fix, in three parts:

  **1. ALL FOUR SIDES READ THE REPORT.** `_engine_text_notes` binds
  `_meas_l / _meas_r / _meas_t / _meas_b` off the frame's own report and every
  patch-area check measures from them: the bottom sheet text, the strip letters
  across the top, the chart notes and settings stamp down the right, and the
  clip border's band and its text on whichever edge it sits. The top and right
  already preferred the report; the bottom and the two clip checks read
  `geometry`'s margins, which is B8-137, now closed by this.

  **2. IT IS RECOMPUTED ON GENERATE, NOT ON A KEYSTROKE.** B8-176 put
  `_update_margin_inspector()` into `_refresh_manual_command_preview` hours
  earlier, and it comes out again: a frame headed "Measured from Preview"
  cannot repaint for a sheet nobody has drawn. The red "press Generate Chart"
  sentence `_refresh_unapplied_warning` paints is what says the boxes are ahead
  of the frame, and Knut names that behaviour as already correct.

  **3. NOTHING IS SEARCHED FOR ANY MORE.** `margin_rise_that_clears_mm`,
  `predicted_patch_bottom_mm`, `_larger_paper_note`, `_bottom_clears_with`,
  `lowering_b_clears` and `markers_off_clears` are deleted, with
  `_MARGIN_STEP_MM`, `_MARGIN_WALK_STEPS`, `_MIN_TEXT_EDGE_MM` and
  `_MARGIN_BOX_MAX_MM`. All six answered *"how much more margin clears it"*,
  which this rule cannot ask. Fourteen register entries are marked SUPERSEDED
  by this one because the code they guard is gone.
- the messages: four bottom wordings become two, one line and two lines. They
  name what is short, name the controls that move it ("Bottom" under "Margins
  (mm)", Size under "Sheet text", and the second line's own tick), and end by
  asking for a Generate Chart, which is the only thing that can measure the
  next state. No rise is named, and nothing is said about paper. Translated
  into all twelve catalogues, with each language's own name for every control.
- `_bottom_lever_note` survives, without its two gates: "the ruler helper
  markers hold the text {anchor} mm from the paper edge, which is further up
  than “B”" is arithmetic on two numbers the panel already holds, not a search,
  and it is the sentence that stops a reader winding down a box that moves no
  ink.

### B8-180 · The cost quoted for the per-keystroke refresh was wrong by 28x
- blocks release: no
- status: FIXED
- found by: this round, 2026-09-15, while carrying out B8-179. INTRODUCED BY
  B8-176 the same day, and shipped in v4.3.0-beta.17.
- evidence: test_no_hook_on_a_keystroke_calls_the_margin_inspector,
  test_a_layout_change_does_not_remeasure_the_frame,
  test_the_notes_box_and_the_stamp_tick_leave_it_alone_too.
- detail: B8-176's comment in `_refresh_manual_command_preview` justified
  calling `_update_margin_inspector()` on every layout keystroke with
  *"8.5 to 20.3 ms median ... worst single pass 63.7 ms"*, against a sibling
  call accepted at 17.2 ms. Measured on a real chart, ten consecutive calls,
  the method is **563 ms median (556 to 594)** on a 1.86 MB chart TIFF. The
  reason is the measurement source: `measure_from_engine` reads the engine's
  recorded patch rectangles out of `channels.json` and costs **0.7 ms** warm,
  while `measure_margins` re-reads and scans the rendered raster and costs
  **93 ms** on Knut's 0.58 MB sheet and far more on a large one. Only an
  engine chart has a `channels.json`; a printtarg chart, or one built with the
  layout engine off, takes the raster path every time.

  The number that was quoted appears to have been measured on
  `_engine_text_notes` alone, which is the arithmetic, and not on the method
  that re-measures the sheet around it.

  It is gone with B8-179 rather than fixed in place: the call is removed, so
  the frame is measured once per Generate, where a chart build already costs
  seconds. **The raster path itself is not made cheaper here and is reported,
  not swept**: paging through a multi-page non-engine chart still pays 93 ms or
  more per page, which is the one place the cost is still visible.

### B8-181 · With the layout engine OFF, the right-edge stamp is checked by nothing
- blocks release: no
- status: OPEN
- found by: this round, 2026-09-15, while carrying out Knut's ruling (B8-179),
  which names engine-off as one of the two cases the set margins and the
  measured ones disagree in. Raised rather than changed: it is a surface his
  ruling does not cover, and CLAUDE.md's rule is that behaviour a specification
  does not describe is reported and approved before it is built.
- evidence: measured on screen with
  `~/Desktop/ChromIQ-beta18-proof/knut-bottom-text/drivers/b18_engine_off_right_edge.py`,
  CR30 / A4 / 300 dpi, "Run 1 Chart Notes" typed and "Stamp settings down the
  right edge" on. The patch area's measured right edge is **17.53 mm**, the
  nearest black ink to the right paper edge is at **10.41 mm**, there are
  42,772 dark pixels in the rightmost 30 mm of the sheet, and
  `_engine_text_notes` returns `[]`. Photographed as
  `shots/D2-engine-off-right-edge.png`.
- detail: with "Use the ChromIQ layout engine instead of printtarg" off, the
  layout panel's Sheet text box, its Size, the "B" box, the clip-border
  controls and the ruler-marker boxes are all hidden, so three of the four
  checks have nothing to be about: printtarg lays the sheet out and none of
  that furniture exists.

  **The fourth does.** `ChartCreator._stamp_tiff_metadata` is called on the
  printtarg path (line 1674) as well as on the engine path (1535), so the chart
  notes and the settings stamp are printed down the right edge of an engine-off
  chart exactly as they are on an engine one. `_engine_text_notes` gates its
  whole body on `use_chromiq_layout_engine`, so nothing asks whether that line
  lands on the patches.

  **NOTHING IS WRONG ON THE SHEET MEASURED.** 7.1 mm of clear paper lie between
  the ink and the patch area, so this is a missing check rather than a visible
  fault, and that is why it is OPEN rather than a bug.
- what it would take: the right-edge block asked without the engine gate,
  against the same measured `report.right_mm` the engine path now uses. The
  reserve is `tiff_metadata._stamp_one`'s own, which is already the one the
  panel reads.

### B8-182 · One test can fail from another test's monkeypatch, once in three runs
- blocks release: no
- status: OPEN
- found by: this round, 2026-09-15, on the first of three full everyday-tier
  runs of the finished tree. The next two were green, 15,487 passed each.
- evidence: `/tmp/b18_full3.txt`, gw1. `test_settling_never_raises_out_of_its_caller`
  reported `CALL ERROR: Exceptions caught in Qt event loop`, and the traceback
  is `_auto_regenerate_preview` calling `_layout_signature`, which
  `tests/test_the_live_preview_only_follows_the_user.py:295` had monkeypatched
  to raise. The file passes alone, and passed in both later full runs.
- detail: the test deliberately makes `_layout_signature` throw and proves
  `_settle_live_preview` swallows it. A **queued auto-preview timer** then fires
  inside the same patch window and the exception reaches Qt's event loop, where
  `pytest-qt` turns it into a failure of whatever test is running.

  It is NOT this change set's: the patch, the timer and the pytest-qt hook are
  all older than today. What this change set did was make
  `_refresh_manual_command_preview` much cheaper (B8-179 removed a 563 ms call
  from it), which can move when a pending timer gets its turn. So the shape was
  always there and the timing is now more likely to expose it.
- what it would take: stop the auto-preview timer inside that test, or patch
  `_layout_signature` only for the duration of the one call it is about.

<!-- Merge note, 2026-09-15: the four entries below were written as
     B8-179 to B8-182 on a parallel branch, at the same time as the four
     above. They are renumbered B8-183 to B8-186 here; references inside
     them were renumbered with them. -->
---

### B8-183 · FROM PROFILE GAMUT freezes the window for seconds, with nothing on screen
- blocks release: no
- status: FIXED
- found by: a tester, on v4.3.0-beta.16: *"if there is a valid icc profile in the
  project, selecting this causes it to hang"*
- detail: it really did stop. The reach query behind the module
  (`_gamut_coverage` → `select_gamut_targets`) pushes all 5,960 master colours
  backward and forward through the profile on the GUI thread, and `xicclu` is
  single-threaded. Measured on screen with a 20 ms heartbeat on the main
  thread, on the profile the tester's figures match (3,838 of 5,960 in gamut):
  **the first click stalled the event loop 3.91 s, and a Margin change another
  3.97 s**. A photograph taken 1.2 s in shows the previous page still up and
  **no progress indicator of any kind**. The query alone costs 0.51 s to
  **7.41 s** depending on the profile, over four real ones.

  Two premises in the original report are **wrong** and are corrected here.
  (1) The tab's cache is not a single key: `_gamut_coverage_cache` is a plain
  dict that grows, so a combination asked once is free ever after (measured:
  0.03 s). What cost 3.97 s was a combination never asked before.
  (2) One click enters `_gamut_coverage` **eleven** times, not seven; ten are
  cache hits and one query goes out.

  The query itself is untouched. `-fif` stays: it sits 0.052 dE00 from the aim
  against 0.366 for the baked B2A table, the two disagree about the answer
  (2,896 in gamut against 3,838), and which one is right is Knut's call.
- fix: two changes, both outside the UI.
  * `workflow/xicclu_runner.py` splits a large batch across one xicclu process
    per core. **The same question, not a cheaper one**: xicclu answers one
    stdin line per output line and nothing carries between lines. Verified
    value by value on two real profiles across eight worker/chunk
    combinations, every one identical to the serial answer. The cost is
    per-ROW, measured (60 rows 0.10 s, 5,960 rows 3.31 s), which is why it
    works. An injected runner is never split, so every existing test still
    sees exactly one call.
  * `workflow/gamut_target.py` splits the round trip out of
    `select_gamut_targets` and memoises it. **The margin is a threshold, not a
    question** and neither is the patch count, so changing either cannot move
    the round trip. `flags_in_gamut` shares the same function, so the numeric
    inverse is now asked for in exactly one place.

  Measured in the real window, same project, before and after: first click
  **3.91 s → 1.66 s**, Margin change **3.97 s → 0.06 s**, Intent change
  2.92 s → 1.08 s. The query alone: 7.41 → 1.69 s on the slowest profile,
  3.64 → 1.09 s on the tester's. **Every in-gamut count is unchanged** (5896,
  1489, 3838, 4113), and the count line reads identically.
- not fixed here: the work still runs ON the GUI thread and there is still no
  progress indicator, so a slow profile on a slow machine still stalls the
  window for about a second. Both live in `ui/tabs/tab_chart.py`, which this
  round was scoped out of. See B8-184.
- evidence: test_splitting_the_batch_returns_exactly_the_serial_answer,
  test_the_split_keeps_the_rows_in_order,
  test_an_injected_runner_is_never_split,
  test_a_small_batch_is_not_worth_a_second_process,
  test_the_worker_count_is_bounded_by_the_rows_and_the_cores,
  test_changing_only_the_margin_does_not_ask_the_profile_again,
  test_a_different_intent_is_a_different_question,
  test_two_different_colour_sets_of_the_same_length_do_not_collide,
  test_a_rebuilt_profile_is_read_again, test_the_memo_is_bounded,
  test_an_injected_runner_is_never_remembered,
  test_the_one_round_trip_asks_for_the_numeric_inverse,
  test_neither_entry_point_inverts_behind_the_round_trips_back.
  All ten mutations proved to land and every one caught.

---

### B8-184 · The reach query still runs on the GUI thread, with nothing on screen while it does
- blocks release: no
- status: OPEN
- found by: this round, measuring B8-183
- detail: B8-183 took the first click from 3.91 s to 1.66 s and a Margin change
  to nothing, but it did not change WHERE the work runs. `_gamut_coverage` is
  still called synchronously from `_update_gamut_count_line`, so on a slow
  profile, a loaded machine, or an efficiency core (measured elsewhere at 5x a
  performance core) the window still stops, and while it does there is no busy
  cursor, no progress line and no greyed panel. The honest fix is the work off
  the thread with the "≈ N sheets" line arriving when it is ready.
- why it is not fixed here: every line of it is in `ui/tabs/tab_chart.py`,
  which another agent was editing at the same time and which this round was
  explicitly scoped out of. Reported rather than taken.
- owner: unassigned; needs a round that owns `ui/tabs/tab_chart.py`.

---

### B8-185 · ChromIQ has two Install buttons and they disagreed about the name
- blocks release: no
- status: FIXED
- found by: a tester, on the ICC profile's file name; measured on screen in
  `~/Desktop/ChromIQ-beta18-proof/katrina-icc-name/ASSESSMENT.md`
- detail: Build ICC profile's Install went through
  `ProfileBuilder.install_profile` and honoured "Name the installed copy after
  the description". Check and Refine's "Install Profile Anyway" was its own
  `shutil.copy2` to a name built from `Run.for_dir(icc.parent).stem`, and never
  read the setting at all. Same window, same run, same tick, same description
  `RR ColorJet Canon Pro-1100 v5`: the first installed
  `RR ColorJet Canon Pro-1100 v5.icc` and the second `Pro-1100-ColorJet3.icc`.
- fix: one door, `workflow.profile_builder.install_profile_file`, and one name
  decision, `installed_profile_name`. Check and Refine takes its description
  from the **profile's own `desc` tag** rather than a field on another tab: it
  is a fact about the file being installed, it is what colprof was given, and
  it is the name other applications list the profile under, which was the tester's
  point. `Run.stem` survives as the FALLBACK, so an unticked install of a
  role-named `merged.icc` still lands under the project name rather than as
  "merged".

  The deliberate half of the rule is kept and guarded: **the project's own file
  always keeps its stem, only the installed COPY is named after the
  description** (Knut). Forcing the file stem to follow the description is a
  different and much riskier change and was NOT made.

  Driven on screen against the fixed tree, with the first installed copy
  deleted before the second button was pressed so that "nothing new appeared"
  could not be read as agreement: both buttons independently wrote
  `RR ColorJet Canon Pro-1100 v5.icc` while the project file stayed
  `Pro-1100-ColorJet3.icc`. The ColorSync folder was restored to its exact
  42-profile listing afterwards.
- evidence: test_both_install_buttons_write_the_same_name,
  test_with_the_tick_off_both_keep_their_own_rule,
  test_an_empty_description_falls_back_rather_than_installing_nothing,
  test_the_source_profile_is_never_touched,
  test_check_and_refine_does_not_install_behind_the_doors_back,
  test_the_build_tab_really_goes_through_the_shared_sanitiser.
  All mutations proved to land and every one caught.

---

### B8-186 · The installed name kept `CON`, `nul` and a 240-character file name
- blocks release: no
- status: FIXED
- found by: this round, while fixing B8-185; flagged in the beta-18 assessment
- detail: `_install_name` sanitised with `re.sub(r'[\\/:*?"<>|]+', "_", ...)`
  and stripped spaces and dots. That is the character rule only, and it keeps
  three things Windows refuses outright, on a product that ships on Windows:
  a **reserved device name** (`CON`, `nul`, `COM1`, `LPT9` — invalid whatever
  extension follows, so `CON.icc` cannot be created), a name of any **length**,
  and **control characters**, which are invisible in the field and can arrive
  by paste.
- fix: `workflow.profile_builder.sanitise_install_stem`, shared by both Install
  buttons. A reserved stem is repaired with a trailing underscore rather than
  thrown away, so the user still sees what they typed; the stem is capped at
  `MAX_INSTALL_STEM` (100) and re-stripped afterwards because the cut can land
  on a space or a dot; control characters are dropped. **No valid name changes**
  — the existing `test_install_name_follows_checkbox_and_description` passes
  untouched, and only names that were already broken on Windows behave
  differently.
- evidence: test_a_windows_device_name_is_repaired_not_kept,
  test_a_reserved_name_with_more_words_is_left_alone,
  test_an_endless_description_is_cut_to_something_installable,
  test_a_control_character_never_reaches_the_file_name,
  test_the_old_behaviour_is_unchanged,
  test_the_name_decision_survives_a_settings_store_that_raises

<!-- Merge note, 2026-09-15: the entries below were written as B8-179 to
     B8-185 on the report-fix branch, in parallel with the two sets above,
     and are renumbered B8-187 to B8-193 here, references included. -->
### B8-187 · The report window opened on one run showed, and filed, another run's measurement
- blocks release: yes
- status: FIXED
- found by: a tester walking profile, then refinement, then physical
  verification, reported to Basti as *"it failed generating the report at the
  end"*; reproduced and narrowed by the journey round, 2026-09-15
  (`~/Desktop/ChromIQ-beta18-proof/katrina-journey/JOURNEY.md`), and re-measured
  here on screen before anything was changed.
- detail: WHAT A USER SAW. In a project with more than one profile run, the
  Measurement Report window opened on a run's own measurement stopped being
  about that run. `_gather_runs` built the window from
  `list_project_reports(ti3.parent)`, which deliberately globs
  `runs/*/reports/report_*.json` across EVERY run of the project, and the
  fall-back that uses the measurement the window was opened on was reached only
  when the project held **no** saved report at all. So the first report anybody
  generated in a project became the answer for every other run of it: asked
  from run 2 the report was written into `runs/run1/reports/`, asked from run 1
  into `runs/run2/`, and the run the user was standing in went on saying "No
  report has been generated for this run yet" for ever. No error, no traceback,
  no log line, which is why it reached the owner as a button that does nothing.
  Single-run projects were never affected, which is how it survived.

  Measured on screen, 2026-09-15, on a real two-run project built with real
  Argyll tools (`report-fix/drivers/two_runs_report.py`, three asks, before and
  after, with the pre-fix file restored from git for the "before"): opened on
  run 1, the window read **"Report type (run1)"** and **"Judged against (run1)"**
  over run 2's measurement (avg dE **0.669**, where run 1's own is **4.206**),
  wrote `runs/run2/reports/report_*.json`, and left the line under the pulldown
  reading "No report has been generated for this run yet". After the fix the
  same three asks each show and file their own run: run 1 gives 4.206 into
  `runs/run1/`, run 2 gives 0.669 into `runs/run2/`, and the line changes to
  "Already generated for this run: Full colour check (1)".
- fix: the two ideas that were one are separated, and BOTH are kept. What the
  window shows as HISTORY still spans the project's runs, because that trend is
  the feature (#40, Knut, in `list_project_reports`' own docstring); what
  Generate is about, and where it is filed, is the measurement the window was
  opened on. `_gather_runs` now always puts that measurement in its own history
  (`_report_is_about`), exactly as the dated-verification fall-back beside it
  already did for a date measured with the report switched off; `_subject_of`
  gives every source its own subject, so `_add_source`, `_on_add_project` and
  `_on_remove_profile` stop reaching for the history's newest entry; and
  `_reports_to_generate` keeps the button inside the run the window is on, asked
  of `ctx.run` rather than matched out of a path string. A side effect worth
  naming: a loose measurement in a folder that holds a report of a DIFFERENT
  file is now about the file the user opened, not about that report.
  Design rules relied on, both in `docs/design/measurement_report_limits.md`
  and both awaiting confirmation, neither contradicted: section 5 "the set
  belongs to the profile run" and section 10 "the type belongs to the profile
  run" / "Generate report writes a dated report of the type now chosen". No new
  user-facing text, so nothing for the M catalogue.
- evidence: test_the_window_shows_the_measurement_it_was_opened_on,
  test_a_report_generated_from_a_run_is_filed_in_that_run,
  test_the_filed_report_carries_that_runs_own_numbers,
  test_the_run_stops_saying_it_has_no_report,
  test_the_history_still_spans_every_run_of_the_project,
  test_the_run_the_window_is_on_is_in_the_history_even_unsaved,
  test_generate_never_crosses_a_run_boundary,
  test_every_date_of_one_run_still_gets_its_own_report,
  test_a_report_of_another_file_in_the_same_folder_is_not_about_this_one,
  test_a_measurement_that_cannot_be_read_says_so.
  Four mutations proved to land (the diff was printed each time) and each turns
  the file red: the `if not runs:` fall-back restored, the run filter dropped,
  the dedup dropped, and `list_project_reports` narrowed to `list_reports`.

### B8-188 · One press of Generate doubled the reports the run already had
- blocks release: yes
- status: FIXED
- found by: the same on-screen round, measured rather than reasoned:
  `report-fix/logs/two-runs-report-BEFORE.log`, ask C.
- detail: `_on_generate_report` iterated everything the document covered, and
  every report already saved of a measurement came back as a history entry of
  that same measurement. So one press wrote one file per entry: press one left
  one report, press two left two more, press three left four, and the line under
  the pulldown read "Already generated for this run: Full colour check (4)"
  after three presses. Photographed on screen going from 2 to 4.
- fix: `_reports_to_generate` writes one report per MEASUREMENT, deduplicated on
  `(origin folder, measurement file name)`. A run's several dated verifications
  are several measurements and still get one report each, which is what the
  multi-date window has always done.
- evidence: test_three_presses_leave_three_reports_not_eight,
  test_every_date_of_one_run_still_gets_its_own_report.

### B8-189 · Generate stayed live over an empty target list when its own row was unticked
- blocks release: no
- status: FIXED
- INTRODUCED BY THE B8-187 FIX, found by the adversary round on it the same
  hour (`report-fix/drivers/adversary_round2.py`, probe P4).
- detail: the run-row tick boxes leave a measurement out of the trend, the
  tables and the PDF. Unticking the row of the run you are standing in left the
  target list empty while the button stayed enabled, so pressing it wrote
  nothing and said nothing: `_say_generated` is deliberately quiet on success,
  and this was neither a success nor a failure. That is the same "a button that
  does nothing" shape as B8-187, one hour after fixing it.
- fix: the enable line asks the list it will actually write from
  (`_reports_to_generate`) instead of everything loaded. A disabled button is
  visibly refusing; a live one that writes nothing is not. The all-unticked case
  already disabled it, so this only makes the rule reach the row that matters.
  Re-measured on screen: unticked gives 0 targets and a disabled button, ticked
  back gives it again (`report-fix/drivers/adversary_round3.py`, P4b).
- evidence: test_the_button_refuses_when_its_own_run_is_unticked.

### B8-190 · Two profile runs of one project were ONE row key
- blocks release: no
- status: FIXED
- found by: the adversary pass over the B8-187 fix, reading `_run_key`.
- detail: `_run_key` was `created|ti3`, and every run of a project names its
  measurement after the project, so two runs measured in the same second were
  one key. Unticking one row would hide both, and the one-page summary picks its
  single sheet by that key. The same collision is already on record for two
  dated verifications built at load time
  (`test_the_one_page_summary_is_about_one_sheet.py` documents it in a fixture
  comment); the B8-187 fix puts two runs of one project in one window routinely,
  so the class was worth removing rather than the instance.
- fix: the origin folder is part of the key. Session-only: `_hidden_runs` is the
  only thing that keeps one.
- evidence: test_two_runs_measured_in_the_same_second_are_two_rows.

### B8-191 · A source-scanning test anchored on the first MENTION of a method
- blocks release: no
- status: FIXED
- found by: the everyday tier going red on work that had not touched the rule it
  guards.
- detail: `test_the_window_really_guards_it_this_way` read
  `src.index("stamp_report_type(rep, ctx.run)", src.index("_recalculate_run"))`
  over the whole class source. The anchor was therefore the first place the
  METHOD NAME appears anywhere, so a comment in another method naming
  `_recalculate_run` moved the anchor above `_on_generate_report`, and the test
  inspected that method's stamping instead. It failed on a comment.
- fix: `inspect.getsource(MeasurementReportDialog._recalculate_run)` — the
  method's own source cannot drift. Proved still to catch what it guards:
  deleting the `if not (rep or {}).get("report_type")` line turns it red.
- evidence: test_the_window_really_guards_it_this_way.

### B8-192 · Check and Refine writes a 63 KB quality report and its result window never names it
- blocks release: no
- status: OPEN
- found by: the journey round, 2026-09-15; re-read in the source here.
- detail: `ui/tabs/tab_check_refine.py` writes
  `reports/Quality_Check_N_<name>.txt` (62,995 bytes on the journey's run) and
  then shows the Profile Quality Assessment window, which gives the grade, the
  worst strips and the refinement offer and says nothing about the file. ONE
  CORRECTION to the report as it reached me: it is not silent everywhere. The
  line `[OK] Quality report saved: reports/Quality_Check_1_<name>.txt` is
  appended to the tab's own log pane (tab_check_refine.py:1548). What has no
  mention of it is the dialog the user is reading at that moment, which is the
  one place they are looking.
- owner: not this agent's area. `ui/tabs/tab_check_refine.py` was outside the
  brief (`ui/dialogs/measurement_report_dialog.py` and
  `workflow/measurement_report.py`), and the wording of any new sentence would
  go to M-PROPOSED first.

### B8-193 · The Measure tab's own "Measurement report" button is built inside the Manual panel
- blocks release: no
- status: OPEN
- found by: the journey round, 2026-09-15; confirmed in the source here.
- detail: `self._m_report_btn` is created at `ui/tabs/tab_measure.py:2931`, inside
  `_make_manual_panel` (2677 onwards), and is referenced nowhere else. The Guided
  panel (2202 to 2677) builds no such button, so a user who measures the guided
  way never sees the report offered where they are working. They are not cut off
  from it: Tools then Measurement report opens the same window seeded with the
  target's own measurement (`tools_dialogs._report_seed`), and two of the tab's
  own messages point at that route by name. It is a discoverability fault, not a
  dead end.
- owner: not this agent's area. `ui/tabs/tab_measure.py` is owned by another
  agent in another worktree, and moving a button between panels is a layout
  decision for that file's owner.

### B8-194 · Importing an i1Profiler measurement into a profiling run could only be done on the Build ICC profile tab
- blocks release: no
- status: FIXED
- found by: a tester, 2026-09-15: *"an odd thing: when doing an icc profile,
  importing from another program is on the Build ICC Profile tab, and when
  doing a verification, importing is on the Measurement tab. Probably makes
  sense for it to be on the Measurement tab on both?"*
- detail: the Measure tab's IMPORT module existed (#133) but was shown only
  while the shared Run type was **Verification** (`_import_available` returned
  `_is_verification_run()`), and every path inside it reached for
  `Run.verify_chart_ti2`: the panel named the verification chart, the
  validation compared against it, the copy went into a dated
  `verifications/<date>/` folder and was stamped `CHROMIQ_VERIFICATION "true"`.
  So the same act, "bring the readings I made in i1Profiler back in", lived on
  two different tabs depending on which kind of run you were doing, and the one
  a person looked for first was not there. §I.9 of
  `unified_measurement_management.md` had already withdrawn the reasoning
  ("profiling runs cannot import at all") on 2026-08-31, on two measured
  grounds: the app already builds a profile from a partial measurement made
  here, and Tools already advertises bringing i1Profiler readings back *"so you
  can build a profile from them"*.
- fix: Sebastian's ruling, 2026-09-15: *"It is probably the easiest option to
  add the import module in the measurement tab in a profiling run as well"* —
  **add it, do not move it**. The Build ICC profile tab's import is untouched.
  `_import_available` now answers "anything but a calibration" (§I.9's one
  surviving limit, for a data-safety reason: one `cal/` per project and no
  `old/` archive). `_on_import_measurement` became a router over two methods:
  `_import_into_verification`, lifted out unchanged because Sebastian confirmed
  that path on hardware on 2026-08-10, and `_import_into_profiling_run`, which
  is §I.1-§I.8 with §I.9's three substitutions — judged against
  `Run.chart_ti2`, the run's own chart snapshot kept, and copied to
  `Run.measurement_ti3`, the canonical stem the report finds a chart by.
  The two doors share the code that decides and the code that speaks —
  `measurement_import.assess`, `measurement_filing.refuse_it_does_not_belong`,
  the new shared `measurement_filing.ask_to_make_a_new_run` (lifted out of
  `file_into_project` with its wording unchanged) and
  `measurement_filing.finish_the_import` — so they cannot drift into saying
  different things about the same file, which is the fault round 2 of the
  import-door review (T1-G) was written after. Driven on screen end to end: the
  module appears in a profiling run, refuses a measurement of a different chart
  of the same size ("206 of 210 patches do not hold the colour the chart asked
  for"), files one that belongs at the run's own stem, and colprof then builds
  a real 192,296-byte profile from it, peak err 1.89 / avg 0.56 / RMS 0.65.
  New wording: **M-IMPORT-DONE-PROFILING**, in §M-PROPOSED and unapproved —
  the approved import-done window speaks only of verifications and of a dated
  folder a profiling run does not have.
- evidence: test_import_button_appears_for_profiling_and_verification,
  test_a_calibration_run_still_cannot_import,
  test_a_profiling_import_is_judged_against_the_runs_own_chart,
  test_a_measurement_of_the_verification_chart_is_refused_here,
  test_the_chart_the_panel_names_is_the_chart_it_is_judged_against,
  test_it_lands_on_the_runs_canonical_stem,
  test_it_never_lands_in_a_verification_folder,
  test_it_is_not_stamped_as_a_verification,
  test_it_does_not_write_into_the_reads_folder,
  test_an_existing_measurement_is_never_written_over,
  test_declining_the_new_run_writes_nothing,
  test_the_panel_says_so_before_the_button_is_pressed,
  test_a_profiling_reader_is_never_told_about_verifications,
  test_the_help_follows_the_run_type,
  test_the_how_printed_question_is_not_asked_for_a_profiling_sheet,
  test_a_partial_measurement_is_filed_and_both_counts_are_stated,
  test_more_readings_than_the_chart_has_patches_is_refused,
  test_a_run_with_no_chart_cannot_accept_anything,
  test_a_new_run_on_the_bar_is_explained_not_imported_into,
  test_switching_run_type_keeps_the_module_honest,
  test_every_write_in_the_filing_path_is_guarded

### B8-195 · After a profiling import the app asked whether to refine the measurement it had just filed
- blocks release: no
- status: FIXED
- found by: the challenge rounds on B8-194, rounds 1 and 2, 2026-09-15 — both
  on screen. Round 1 caught it because it BLOCKED the driver: a modal stood on
  the machine until the process was killed.
- detail: `_maybe_offer_existing_overlay` opens *"This chart already has a
  measurement"* with two checkboxes and the warning *"If you leave 'Refine /
  resume' unticked and start a new measurement, it will REPLACE this existing
  measurement"*. Every word of it is true and none of it is a question the
  person asked: one second earlier the import's own window had told them the
  measurement was filed. The window exists for ARRIVING at a run somebody
  measured earlier. Two different routes reached it, which is why it took two
  rounds: an import into a full run duplicates the run, so the chart on screen
  changes and `set_ti1_path` queues the offer; and after an ordinary import the
  chart does not change, so nothing queued it — until simply coming back to the
  Measure tab raised it through `showEvent` → `_queue_overlay_offer`.
- fix: the import adds its own run's scope to `_offer_silenced` after filing,
  through the per-run mechanism Knut already specified for this shape (#131,
  2026-07-28: stop asking about the run I am working through) rather than a new
  flag — so it is scoped to that run in that project, and every other run still
  asks. Round 1's first attempt put it inside the chart-changed branch and
  covered only one of the two routes; a remedy that depends on which branch the
  import took is not a remedy, and the parametrised guard below drives both.
  Two more silences the same rounds found: an import no longer joins a live
  averaging set (§I.9 — the next read would otherwise be averaged with a sheet
  measured on another instrument on another day), and a full run whose project
  cannot be opened now says so instead of returning from the button with
  nothing on screen.
- evidence: test_the_import_does_not_then_ask_about_the_file_it_just_filed,
  test_the_silence_is_scoped_to_the_run_the_import_went_into,
  test_an_import_does_not_join_a_live_averaging_set,
  test_a_full_run_with_no_reachable_project_says_so

### B8-196 · The import's own window said a profile could be built from it on a tab that was not holding it
- blocks release: no
- status: FIXED
- found by: the challenge round on B8-194, round 2, 2026-09-15, by reading what
  a native measurement does and what the import did not; confirmed on screen
  afterwards, with the driver only LOOKING at the tab rather than loading it.
- detail: M-IMPORT-DONE-PROFILING says *"You can build a profile from it now on
  the Build ICC profile tab"* and the window carries a **Build the profile**
  button. That button emitted `proceed_to_profile`, which changes tab and
  nothing else. A measurement made here reaches Build ICC profile through
  `measure_finished` → `MainWindow._on_measure_done` →
  `set_ti3_path(ti3, propagate=False)`, and a native session emits that line
  BEFORE it offers to go to tab 4. The import emitted neither, so the person
  pressed a button that promised a ready tab and arrived at one still holding
  whatever it held before. A message is a promise.
- fix: `_import_into_profiling_run` emits `measure_finished` with the filed
  copy immediately after the shared ending and BEFORE the done window, so the
  tab is armed whether or not the button is pressed, and by the same one line
  a read made here uses. Driven on screen: after the import the Build ICC
  profile tab holds the run's own `.ti3` with its Build Profile button enabled,
  and no window of its own is raised on the way.
- evidence: test_the_tab_that_builds_from_it_is_actually_holding_it

### B8-197 · The run's own chart could be imported as its own measurement, in silence
- blocks release: no
- status: FIXED
- found by: the challenge round on B8-194, round 6, 2026-09-15, on screen —
  the round that stopped driving the journeys that work and drove only the
  doors that are supposed to refuse.
- detail: the chart and the measurement sit in the same run folder under the
  same stem and are both CGATS tables, so picking the wrong one is an ordinary
  slip. Every check the import has was blind to it, and each one for a good
  reason. A `.ti2` is not a `.ti3`, so the file goes through txt2ti3 first, and
  what comes back is a well-formed CTI3 table of the chart's own AIM XYZ —
  printtarg writes those into every `.ti2` it lays out. So `parse_ti3` reads it
  as a complete set of 210 readings; the patch count matches EXACTLY, because
  it is the same file; and `verify_patch_identity` compares the chart with
  itself and reports a flawless match. It was copied to `Run.measurement_ti3`
  with nothing at all on screen, and the profile built from it would describe a
  printer that had never printed anything: a perfect result, which is exactly
  when to be suspicious. Reachable from the Measure tab by choosing "All files"
  in the file dialog, and from the Build ICC profile door under any name at
  all, since that one accepts a measurement wherever it comes from. The
  `.ti3`-named variant is reachable without changing the filter at all.
- fix: the file says what it is on its first line, so ask it.
  `measurement_import.looks_like_a_chart` reads the CGATS table keyword and
  `assess` refuses `CTI1`/`CTI2` before it tries to parse anything, which
  catches a chart carrying a `.ti3` name on BOTH doors. That alone is not
  enough for a `.ti2`, because conversion destroys the evidence before `assess`
  ever sees it, so the Measure tab's door asks the same question of the file
  the PERSON picked, before anything is converted. One sentence, in one
  constant, so the two places cannot drift. Driven on screen afterwards: the
  chart is refused with that sentence and nothing is written, while a text
  file, an empty file and a genuinely partial measurement all still end the way
  they did.
- evidence: test_the_runs_own_chart_cannot_be_imported_as_its_measurement,
  test_a_chart_is_refused_by_what_the_file_says_it_is

### B8-198 · An import saved a dated measurement report, by accident rather than by decision
- blocks release: no
- status: FIXED
- found by: the challenge round on B8-194, round 4, 2026-09-15 — read out of the
  Measure tab's own log in a photograph, not predicted.
- detail: B8-196's fix emits `measure_finished` so the Build ICC profile tab is
  armed, and that signal is ALSO wired to `_maybe_save_measurement_report`. So
  an import began accruing a dated accuracy report beside the measurement. The
  behaviour is right — it is what the feature wants, it obeys the person's own
  Settings switch, and an imported measurement already carries the date it was
  MEASURED rather than converted (`reference_convert` stamps
  `CHROMIQ_MEASURED`), so it trends beside the others correctly — but it was
  nobody's decision, and an undocumented side effect is a fault waiting for the
  next person who deletes the line that causes it.
- fix: written down at the line that causes it, and guarded, so it is a
  decision. Nothing about the behaviour changed. Re-checked after the
  Measurement Report window was changed to file under the run it was asked
  from: the report an import accrues lands under the run the measurement went
  into, including when that is a run the import created by duplicating.
- evidence: test_an_import_accrues_a_dated_report_like_a_read_made_here,
  test_the_report_lands_under_the_run_the_import_went_into

### B8-199 · The new profiling import door refused a measurement with no device values, which the verification door had just been taught to accept
- blocks release: no
- status: FIXED
- found by: the rebase of B8-194 onto the tip, 2026-09-15 — by B8's OWN test
  for the verification fix (`test_the_device_values_are_attached_before_the_copy_is_filed`)
  going red, because the split that gave each run type its own method left that
  assertion looking at a router.
- detail: i1Profiler's measure tool reads a chart it did not generate, so it
  has no colour space to express device values in and exports none at all. The
  verification door was taught on 2026-09-12 to key the pairing on the patch
  NAME and take the device values from the chart, after a user's complete i1iO
  reading of her own chart was refused with "No device RGB columns". The
  profiling door was written the same week, against a base that did not have
  that fix, and reached `assess` directly rather than through
  `_import_verdict` — so the identical file, imported one door along, met the
  identical refusal. Neither door had changed behaviour; the two were written
  days apart against different bases, which is exactly the drift the shared
  rule exists to prevent.
- fix: the profiling door goes through `_import_verdict` like its twin, and
  carries the same §2a block against `Run.chart_ti2`: the person is asked
  first (**M-IMPORT-DEVICE-FROM-CHART**, which names the chart and is run-type
  neutral), the values are completed on the CONVERTED COPY in the run's cache
  and never on the user's file, and a No writes nothing. The source assertion
  that caught it now names both doors and checks each completes from its own
  chart, so a third door could not inherit the gap.
- evidence: test_a_measurement_with_no_device_values_is_imported_here_too,
  test_saying_no_to_that_question_writes_nothing,
  test_the_device_values_are_attached_before_the_copy_is_filed


---

### B8-200 · One measurement was listed as several measurement runs, and unticking either row emptied the page
- blocks release: no
- status: FIXED
- found by: combined adversary round 1 on the merged tree, 2026-09-15, driving
  the real app in a real window
  (`~/Desktop/ChromIQ-beta18-proof/combined-round-1/`,
  `drive_two_reports_one_second.py`). It is a SEAM: the state is reached by an
  ordinary journey only because two streams meet at it.
- detail: WHAT A USER SEES, photographed in
  `D2-report-window-with-two-saved-reports.png`. A run whose single measurement
  has two saved reports of it opens the Measurement Report window on **"2
  runs"**, with two rows reading `2026-09-15 14:12 — printing method not
  recorded` word for word identical, **"No. of Measurements: 2"** for a chart
  measured once, and *Trend over time (this printer)* drawing flat lines from
  the measurement to itself between one date and the same date. Unticking
  EITHER row emptied the page: `build_report` stamps `created` from the
  MEASUREMENT and not from the moment Generate was pressed, so two reports of
  one measurement always carry the same `created` — measured, 2 rows under
  **1** distinct `_run_key`, and hiding one row left **0**.
- why now: the import door added to the Measurement tab saves a dated report by
  side effect (`measure_finished` is wired to
  `_maybe_save_measurement_report`), so the first press of **Generate report**
  after an import is the SECOND report of that measurement. Neither the import
  work nor the report work produces that state alone, which is why each was
  green in isolation. It is not a race: it needs no two clicks in one second.
- cause: `_gather_runs` yielded one row per report FILE. `_reports_to_generate`
  had already been given the correct rule for the writing side in the same
  batch — *"one report per MEASUREMENT rather than one per report already saved
  of it"*, keyed on `(origin, ti3 name)` — and the reading side kept the old
  one, so the count the writer had just stopped doubling was doubled again on
  the way back in. The same class is on record twice already in this window:
  the dated-verification `covered` set ("10 rows for 5 dates") and
  `_reports_to_generate` itself.
- fix: `MeasurementReportDialog._one_row_per_measurement`, applied in
  `_gather_runs`, keeps the NEWEST saved report of each measurement — newest by
  file name, because `save_report` names a second report of the same second
  `report_<stamp>_2.json`. The row then carries the type and the limits most
  recently asked for.
- what it deliberately does NOT change: several report types per run stay
  (Knut, 2026-09-11 — *"A user should be allowed to print several report types
  for a run … The Report window must thus show which type of reports have been
  generated"*). Every file stays on disk, and which types exist is said where
  it always was, by `_generated_types_line`: the after picture
  (`D4-FIXED-two-saved-reports-one-row.png`) shows **"1 run"**, one row, **"No.
  of Measurements: 1"**, the honest "a trend graph needs at least two
  measurement runs", and **"Already generated for this run: Full colour check
  (2)"** still counting both files. The cross-run history (#40) is untouched:
  the run folder is half the key.
- evidence: test_two_saved_reports_of_one_measurement_are_one_row,
  test_hiding_one_row_never_hides_another,
  test_the_row_kept_is_the_newest_report_of_that_measurement,
  test_several_runs_still_each_get_their_own_row,
  test_the_bookkeeping_this_needs_never_reaches_a_saved_file.
  Three mutations were proved to land in the file the run reads and each turns
  the right tests red: removing the call (4 red), flipping the newest-wins
  tie-break (1 red), and dropping the run folder from the key (1 red).

---

### B8-201 · The handler that exists to keep a window opening raised NameError out of itself
- blocks release: no
- status: FIXED
- latent: no caller reaches it in the shipped app today (see `reach` below)
- found by: combined adversary round 1, 2026-09-15, sweeping the merged tree
  for names bound nowhere before trusting the six functions one stream deleted.
  INHERITED, not this batch: the line has been there since 2026-08-28.
- detail: `ui/widgets.py::widen_message_box` ends
  `except Exception:  # noqa: BLE001 — a window must still open` followed by
  `log.debug(...)`. The module binds `_log`; `log` is bound nowhere at module
  level, and an `except Exception` cannot catch a `NameError` raised inside
  itself — so the one line written to KEEP the window opening threw the
  traceback to the caller instead. Reproduced directly: handing the function a
  widget whose layout is not a QGridLayout gives
  `NameError: name 'log' is not defined`.
- reach: all six callers are in `ui/measurement_target_bar.py` and all six pass
  a `QMessageBox`, whose layout IS the QGridLayout `addItem(item, r, c, rs, cs)`
  wants, so nothing meets it in the shipped app today. The seventh caller,
  with any other layout, would have — and that case is the entire reason the
  handler is written.
- fix: `_log.debug(...)`, the name the module has. It was the lone typo:
  every other swallowed error in `ui/widgets.py` already logs through
  `_log` (lines 511, 1179, 1431 and 1564), so nothing else in the file
  carries it, and a sweep of every `except` handler in `ui/`,
  `workflow/` and `core/` for a logger name the module never binds
  found no other.
- evidence: test_a_box_that_cannot_be_widened_still_opens. MUTATION PROVED:
  restoring `log.debug` in `ui/widgets.py` turns it red with the NameError,
  and nothing else in that file.

### B8-202 · A run measured eleven times listed one measurement, and lost ten points off its trend
- blocks release: no
- status: FIXED
- found by: combined adversary round 2 on the merged tree, 2026-09-15, attacking
  the round before it (B8-200) and driving the real app in a real window
  (`~/Desktop/ChromIQ-beta18-proof/combined-round-2/`,
  `drive_the_runs_a_run_remembers.py`).
- detail: WHAT A USER SEES, photographed in
  `E1-report-window-on-a-run-measured-many-times.png`. A real project off a real
  disk, `printer-test/runs/run1`: eleven dated reports of eleven distinct
  measurements, fifty-five archived measurements in `old/`. The Measurement
  Report window opened on it said **"printer-test · 1 run"**, one row reading
  `2026-08-08 13:36`, **"No. of Measurements: 1"**, a date range of
  `2026-08-08 – 2026-08-08` for a session that ran from 11:48 to 13:36, and
  *"A trend graph needs at least two measurement runs. Add another measurement,
  or, if the profile you have loaded already holds more than one run, tick
  'Show all measurement runs' above"* **with that box already ticked** — while
  the line above it read **"Already generated for this run: Full colour check
  (11)"**. The window knew about eleven and listed one. Ten measurements were
  gone from the list, the tables, the PDF and the trend.
- reach: four projects on one real disk were already in this state before the
  round began, with 11, 17, 8 and 4 distinct measurements in a single run
  folder. No unusual act is needed: measuring a run AGAIN archives the previous
  `.ti3` into `old/` and writes the new one under the same stem, and with
  *Save measurement report* on each measurement leaves its own dated report.
  That accrual IS the over-time trend the window's subtitle promises (#40).
- cause: B8-200's `_one_row_per_measurement` keyed on
  `(_origin_dir, ti3 file name)`. Every measurement of one run carries the same
  pair, because the stem is the sanitised project name. `_run_key`, three
  methods below it in the same class, answers the same question with
  `_origin_dir | created | ti3` and its docstring gives the reason for each of
  the three parts; the new rule was a coarser expression of it, written a
  commit earlier.
- fix: the row rule asks `_run_key`. Two reports OF ONE MEASUREMENT still merge
  under it — `build_report` stamps `created` from the measurement, so they share
  it, which is exactly what B8-200 measured — and two MEASUREMENTS never do.
  The writing side moved with it: with the history restored,
  `_reports_to_generate` saw several rows per folder again and kept the FIRST,
  which is the oldest, so Generate would have filed a report about a sheet
  measured hours earlier under this window's limits and this window's type. The
  row the window is ON wins now, and where the window is on neither, the later
  measurement does.
- evidence: test_every_measurement_of_a_run_is_its_own_row,
  test_the_trend_gets_a_point_for_every_measurement,
  test_two_reports_of_one_measurement_are_still_one_row,
  test_generate_files_a_report_about_the_measurement_in_hand,
  test_generate_still_writes_one_file_per_press,
  test_the_row_rule_and_the_run_identity_are_the_same_key. MUTATIONS PROVED,
  each checked to be in the file the run reads before the run: the coarse key
  turns 3 red, the first-row-wins rule in `_reports_to_generate` turns 1 red,
  and removing the dedup call altogether turns 5 red (B8-200's four and this
  file's one). After the fix the same window says **"printer-test · 11 runs"**,
  eleven rows, "No. of Measurements: 11" and a trend with eleven points
  (`E21-report-window-on-a-run-measured-many-times.png`).

### B8-203 · Switching on Preferences ▸ Calibration options removed the IMPORT door from every run type
- blocks release: no
- status: FIXED
- needs confirmation: the Measure tab now shows a `MANUAL | IMPORT` row where it
  showed none. `docs/design/calibration_run_type.md` promises only that *"the
  guided modes in all tabs are hidden"*, which is kept; that a row is visible at
  all in this state is a change a person should look at.
- found by: combined adversary round 2, 2026-09-15, walking the run types on
  screen (`drive_calibration_and_switching.py`,
  `/tmp/chromiq-comb2-work/probe_import_reachable.py`).
- detail: WHAT A USER SEES, photographed on a PROFILING run, the same project,
  the same run, the preference the only difference:
  `H-measure-tab-calibration-mode-OFF.png` shows the mode row
  `GUIDED | MANUAL | IMPORT`; `H-measure-tab-calibration-mode-ON.png` shows no
  row at all. With the preference on there is no way to reach the measurement
  import module from the Measure tab, on any run type, and nothing says why.
- cause: `TabMeasure.set_calibration_mode` hid the whole `_mode_row_widget`.
  When that line was written the row held two buttons, GUIDED and MANUAL, so
  hiding it said exactly what the preference promises. #133 then put IMPORT in
  the same row and this week widened that door from verification runs to
  profiling ones, so the rule built for it was inert underneath:
  `_import_available()` answered **True**, `_refresh_import_visibility` called
  `_import_btn.setVisible(True)`, and `isVisible()` was **False** with
  `isVisibleTo(parent)` **True** — the button's own parent was hidden over it.
- why no test caught it: every test the import work shipped with asks
  `_import_btn.isVisibleTo(tab)` and none of them calls `set_calibration_mode`,
  so the row they measure through was never hidden in them.
- fix: the GUIDED button is hidden, which is the sentence the preference
  promises; the row stays while it still offers a choice. A calibration run
  still has no row, because there is nothing to choose there. `_switch_mode`
  falls back to manual rather than guided when guided is not offered, or leaving
  the import module for a calibration would have stranded the person on a module
  whose button is hidden. `set_calibration_mode` also stopped forcing manual on
  somebody standing in the import module, since it runs on any Preferences save.
- evidence: test_the_import_button_is_reachable_with_calibration_options_on,
  test_pressing_it_reaches_the_import_module,
  test_the_guided_module_is_still_hidden,
  test_a_calibration_run_still_has_no_mode_row,
  test_leaving_the_import_module_never_lands_on_the_hidden_guided_one,
  test_the_preference_off_is_exactly_as_it_was. MUTATIONS PROVED: restoring
  `self._mode_row_widget.setVisible(not enabled)` turns 2 red, removing the
  guided-fallback clause from `_switch_mode` turns 1 red, and always showing the
  row turns 1 red. Driven again after the fix
  (`H2-FIXED-import-reachable-with-calibration-options-on.png`): the row reads
  `MANUAL | IMPORT`, pressing IMPORT opens the module, and a calibration run is
  unchanged.

### B8-204 · Paging to the last sheet of a chart made a red text-overlap warning disappear
- blocks release: no
- status: FIXED
- found by: combined adversary round 2, 2026-09-15, on the second and third
  page, which round 1 never reached
  (`drive_the_second_and_third_page.py`).
- detail: WHAT A USER SEES, photographed page by page on a real three-page A4
  chart with one set of settings and *Text distance from edge* ▸ Clip at 10 mm
  (`K41`/`K42`/`K43-create-chart-on-page-N-of-3.png`). The measured right margin
  is **7.985 mm** on pages 1 and 2 and **175.964 mm** on page 3, because the
  part-full last page's patches stop early and the paper beside them is the
  width of the empty half of the sheet. The panel said

  > ⚠ The chart notes down the right edge run over the patches. They are
  > printed 10.0 mm in from the paper edge, need 2.7 mm at 7 pt, and the right
  > margin leaves 0.0 mm … Raise "Right" under "Margins (mm)" by about 5.1 mm

  on pages 1 and 2, and **nothing at all** on page 3. Pressing *Next* made a red
  warning disappear with nothing saying why, and a reader who happened to be on
  the last page was told nothing about the two sheets that clip.
- cause: Knut's ruling of 2026-09-15 made all four text-fit checks read the
  MEASURED sheet rather than a prediction, and the measured sheet is the page
  the preview is showing — `_update_margin_inspector` says so itself, because
  the guides must land on the patches the reader can see (#83), and
  `_engine_text_notes` is called from inside that same method and re-runs on
  `page_changed`. A prediction was the same number on every page. A measurement
  is not. Two readers of that edge are affected: the chart note
  (`chart_note_overlap`) and the clip border's own content
  (`clip_content_overlap`). Top, bottom and left measured identically on all
  three pages to 0.001 mm, so the right edge is where it bites today.
- fix: `_worst_page_report` hands the notices a report whose four edges are the
  least room ANY page of the chart leaves, while the frame's own numbers and
  guides stay the page on screen. `_ensure_worst_page_cache` measures the whole
  chart once per chart, and BEFORE the page on screen is measured, because
  `test_inspector_follows_the_displayed_page` proves #83 by watching which TIFF
  `measure_margins` was asked for LAST; measuring the chart afterwards moved
  that, and the #83 guard caught it in the full run.
- evidence: test_the_verdict_is_the_worst_page_not_the_page_on_screen,
  test_the_frame_actually_hands_the_notes_the_worst_page,
  test_every_side_is_taken_from_its_own_worst_page,
  test_the_frame_still_shows_the_page_on_screen,
  test_a_one_page_chart_is_untouched,
  test_it_is_measured_once_per_chart_and_not_once_per_page_turn,
  test_a_new_chart_is_measured_again,
  test_the_pages_really_do_measure_differently. MUTATIONS PROVED: `max` for
  `min` turns 3 red, removing the cache's early return turns 1 red, and handing the notices the
  page on screen turns 1 red, and moving the whole-chart pass back to AFTER the
  shown page turns the #83 guard `test_inspector_follows_the_displayed_page`
  red — the first of those is why
  `test_the_frame_actually_hands_the_notes_the_worst_page` exists at all, since
  the first seven tests all called `_worst_page_report` themselves and every
  one of them stayed GREEN under it.

### B8-205 · Every dated row in the Measurement Report carried today's sheet's numbers
- blocks release: no
- status: FIXED
- found by: combined adversary round 3, 2026-09-15, attacking round 2's own
  fix on the real disks that fix was measured on
  (`drive_the_measurement_a_window_is_about.py`,
  `drive_one_sheet_under_every_date.py`).
- detail: WHAT A USER SEES, photographed on `CR30-Test/runs/run1` copied out of
  a real working folder (`B1-seventeen-dates-one-sheet.png`). That run holds
  seventeen distinct measurements and twenty-two archived copies in `old/`.
  Round 2 restored one row per measurement, so the window listed all seventeen
  dates across five weeks, "No. of Measurements: 17", "Date range 2026-08-28 –
  2026-09-08". **Every one of those rows read 8 patches, ΔE00 average 11.948,
  paper white L\* 66.97** — the sheet measured on 8 September. The row dated
  29 August had been saved with 20 patches, ΔE00 15.907 and white L\* 92.39.
  Sixteen of the seventeen rows had their saved numbers replaced, and the
  over-time trend (#40) — the thing the window's own subtitle promises — drew
  seventeen points in five perfectly flat lines. Surveyed over that whole disk:
  of 54 saved reports, **four** describe the measurement still live in their
  run folder, so 50 rows in that user's history were showing another sheet.
- cause: `_gather_runs` rebuilds a saved report whose schema or block set is out
  of date, and took the measurement to rebuild from as
  `p.parent.parent / ti3.name` — the run folder plus the name of the file the
  window was opened on. Every measurement of one run carries that same name:
  the stem is the sanitised project name, and measuring again copies the
  previous `.ti3` into `old/<when>/` and writes the new one over it. So for
  every report but the newest that path is a different measurement. The
  rebuild kept the saved date and the saved verdict and replaced every number,
  which is why the fault was invisible until round 2 stopped the rows being
  collapsed into one.
- fix: `workflow.measurement_report.created_stamp_for` is the rule
  `build_report` stamps `created` with, lifted out of it so there are two
  callers and one rule. `MeasurementReportDialog._measurement_for` answers with
  the run's measurement only while its own stamp is still this report's, and
  `None` otherwise; the rebuild is skipped for a `None`, so the row keeps the
  numbers it was saved with. The name comes from the report, not from the file
  the window was opened on. The archived copy in `old/<when>/` is deliberately
  NOT offered as a rebuild source, and the first reason written down for that
  was wrong and is corrected here: an archived measurement CAN find a design
  reference (`_find_reference_ti2` climbs three levels for a dated
  verification, and from `runs/runN/old/<when>/` those land on the run root),
  measured on three archives of `CR30-Test/runs/run1`. The real reasons are
  that the reference it finds is whatever chart is in the run TODAY, which is
  the failure `_find_reference_ti2`'s own docstring records (a trend point that
  jumped to delta-E 41 after the chart was swapped, against an honest 2.8, and
  an `old/` archive has no `chart/` snapshot to outrank it), and that
  `_sheet_kind` reads the folder, so a measurement rebuilt from `old/<when>/`
  comes back as `standalone` and stops being the profiling sheet it was. The
  numbers a saved report already holds were computed from the right measurement
  AND the chart of the day; nothing available now beats that.
- also: the reason printed beside such a row said *"this value was not computed
  for this report; the measurement file could not be read again"*. That names a
  cause `REASON_NOT_COMPUTED` never meant — it means the block is missing from
  the saved report — and the cause was untrue in both cases that reach it. The
  module's own docstring had said so since 2026-09-13. It now reads *"this
  value is not in this saved report; it was not one of the values ChromIQ kept
  when the report was saved"*, with the German translated and the stale key
  removed from all twelve catalogues.
- evidence: test_each_row_carries_its_own_measurements_numbers,
  test_the_trend_draws_a_different_point_for_each_measurement,
  test_the_measurement_still_in_the_run_folder_is_still_rebuilt,
  test_created_stamp_for_is_the_stamp_build_report_writes,
  test_a_date_only_measured_keyword_reads_the_same_both_ways,
  test_the_reports_own_name_wins_while_the_folder_has_that_file,
  test_a_measurement_whose_stamp_moved_is_not_claimed,
  test_an_archived_measurement_is_never_the_rebuild_source,
  test_no_row_is_told_its_measurement_could_not_be_read. MUTATIONS PROVED,
  each one grepped out of the file the run reads before the run that judged it:
  putting the rebuild's source back to `p.parent.parent / ti3.name` turns 2
  red, making `_measurement_for` always answer None turns 3 red, dropping the
  stamp condition turns 3 red, taking the name from the window instead of the
  report turns 1 red, making `created_stamp_for` fall back to `now()` turns 4
  red, removing its date-only branch turns 1 red, and restoring the old
  sentence turns 1 red.

### B8-206 · B8-205's first cut took the accuracy figures off every dated verification
- blocks release: no
- status: FIXED
- found by: combined adversary round 3 attacking its OWN fix, 2026-09-15, on
  the demo package the project rebuilds before every beta
  (`drive_a_demo_dated_verification.py`).
- detail: WHAT A USER SEES, photographed on `Demo-Switching/runs/run2` on
  screen, with the same drive run against the code before B8-205 and after it
  (`G0-BEFORE-result.json` beside `G-result.json`). Before B8-205 the two dated
  verification rows read 64 patches, ΔE00 average **20.146** and **20.042**,
  each with its grey block and its example colours. After B8-205's first cut
  both read **`avg_all: None`** — no ΔE block at all, nothing on the trend, and
  two rows saying "this value is not in this saved report". Those are the rows
  Knut reads out of the shared demo package, and it is the same complaint he
  made on 2026-09-11 about example colours, arriving again by a new route.
- cause: B8-205 said a saved report's measurement is the file whose
  `created_stamp_for` equals the report's `created`, and refused everything
  else. A dated verification's stamp moves for reasons that have nothing to do
  with measuring again: the demo package writes each report with the date it
  wants the history to show and leaves the file with the time it was generated,
  and renaming a target renames the measurement while the saved reports go on
  naming the old stem (`Demo-Full-RGB-verify.ti3` beside a folder holding
  `Demo-Switching-verify.ti3`). A `verifications/<date>/` folder holds exactly
  ONE measurement, so "the file in the folder" was right there all along. That
  is the shape B8-205 is not about.
- fix: the stamp settles it one way and the FOLDER settles it the other.
  `_measurement_for` refuses the file only where something on disk says the
  folder has held more than one measurement under that name: an archived copy
  in `old/<when>/`, which `MeasurementSession.begin` leaves every time a
  measurement is made over another, or another saved report in the same folder
  carrying a different `created`, which cannot exist without another
  measurement. Neither is true of a run measured once or of any dated
  verification; both are true many times over of `CR30-Test/runs/run1` (22
  archives, 17 distinct dates). The reports are now read once into a list and
  their dates counted per origin folder before anything is rebuilt, so no
  report is judged in ignorance of its neighbours. The name still comes from
  the report and falls back to the file the window is about only when the
  folder has no file of that name, which is the renamed-target state.
- also: two claims written down in B8-205 were wrong and are corrected in
  place. The archived copy CAN find a design reference (`_find_reference_ti2`
  climbs three levels for a dated verification, and from
  `runs/runN/old/<when>/` those land on the run root) — measured on three
  archives of `CR30-Test/runs/run1`. It is still not rebuilt from, for two
  reasons that are about being wrong rather than empty: the reference it finds
  is whatever chart is in the run today, which is the failure
  `_find_reference_ti2`'s own docstring records, and `_sheet_kind` reads the
  folder, so an archived profiling sheet comes back as `standalone`. And
  `_measured_keyword` now reads through `parse_ti3`'s own `_KW_RE` rather than
  splitting on a space: the two readers of the one rule agreed over 128 .ti3
  files on one real disk and **not one of them carried the keyword**, so that
  sample said nothing about the branch where a drift would live.
- evidence: test_a_renamed_target_still_finds_its_own_measurement,
  test_two_dates_in_one_folder_are_two_measurements,
  test_a_measurement_whose_stamp_moved_is_not_claimed,
  test_the_reports_own_name_wins_while_the_folder_has_that_file,
  test_an_archived_measurement_is_never_the_rebuild_source,
  test_the_keyword_is_read_through_parse_ti3s_own_regex, and B8-205's own
  test_each_row_carries_its_own_measurements_numbers and
  test_the_trend_draws_a_different_point_for_each_measurement, which must stay
  green through all of it. MUTATIONS PROVED, eleven, each read back out of the
  file before the run that judged it: not consulting the `old/` archive turns 2
  red, not consulting the folder's other report dates turns 3, removing the
  renamed-target fall-back turns 1, taking the name from the window turns 1,
  dropping the stamp check turns 5, making `_measurement_for` always answer
  None turns 6, putting the rebuild's source back to `p.parent.parent /
  ti3.name` turns 2, `created_stamp_for` falling back to `now()` turns 6,
  removing its date-only branch turns 1, splitting the keyword on a space turns
  1, and restoring the old sentence turns 1.

### B8-207 · "Location being edited" was drawn black on the near-black rail
- blocks release: no
- status: FIXED
- found by: combined adversary round 3, 2026-09-15, settling a suspicion the
  round's own pause note had written down as unproven
  (`drive_the_location_line_geometry.py`, `drive_the_rail_label_contrast.py`).
- detail: WHAT A USER SEES, in the DEFAULT appearance, on every screen of the
  app: the line under the Profile-run bar that answers "where are my files?"
  is unreadable. Measured **#000000 on the #070707 rail, 1.04:1**
  (`J-result.json`, `J1-dark-the-rail.png`). Light (17.65:1) and Neutral
  (14.17:1) were unaffected, because there near-black on a pale rail happens to
  be legible. Counted in the photograph rather than judged by eye: across the
  sixteen pixel rows of the label's own band, **zero** rows carry ink that
  differs from the rail by more than a hair, while the row above (the
  dropdowns) and the rows below (the tab strip) do.
- cause: `MastheadHeader._paint_center_widget_text` exists for exactly this —
  the bar's labels are plain `QLabel`s with no background of their own, so on
  the rail they take the application palette and vanish; its own docstring
  records fixing "Profile run:", "Run type:" and the first-run hint at 1.11:1.
  It sets a stylesheet naming `QLabel#target_bar_label` and
  `QLabel#target_bar_hint`. The bar has a THIRD object name:
  `QLabel#target_bar_location`, added for #130, never in the rule. An
  enumeration is how it was missed.
- fix: the location line takes `rail_hint_fg`, the colour the rail already uses
  for text meant to be READ rather than glanced at, which is what the first-run
  sentence uses: 4.56:1 dark, 8.71:1 light, 12.84:1 neutral. **The weight is
  Basti's call** — this is a legibility repair, not a design decision, and if
  he wants the line quieter `ver_fg` is 3.72:1 dark.
- and the guard no longer takes a list from anybody:
  `test_every_label_on_the_rail_is_readable_on_it` walks every `QLabel` on the
  hosted widget, in all three appearances, and measures the colour each one
  actually ends up with. A fourth label added tomorrow is covered without
  anyone remembering the file.
- also: three rounds of photographs showed this line looking half cut off, and
  two explanations were wrong. It is not clipped: the label is 127..143 px in a
  masthead whose bottom is at 146, and Qt's own `visibleRegion` for it equals
  its rect. It is not a capture artefact either. It was contrast all along.
- evidence: test_every_label_on_the_rail_is_readable_on_it (dark, light and
  neutral), test_the_labels_are_coloured_for_the_rail_not_the_app_palette.
  MUTATIONS PROVED, each read back out of the file before the run that judged
  it: removing the `target_bar_location` rule turns the dark case red at
  1.04:1, painting the hint in the rail's own background turns all three red,
  and removing the `_paint_center_widget_text()` call from `set_center_widget`
  turns 2 red.

### B8-208 · The report window described an older sheet than the one just measured
- blocks release: no
- status: FIXED
- found by: combined adversary round 3, 2026-09-15, proving a suspicion the
  round's own pause note had written down as unproven
  (`drive_the_three_remaining_suspicions.py`).
- detail: WHAT A USER SEES. Switch off *Preferences ▸ Save measurement report*,
  measure a run that already has reports, then open the Measurement Report
  window on it. The window opened on a measurement of **90 patches read
  2026-09-15** and described one of **15 patches read on 2026-08-08** — that
  older sheet's figures, its date and its verdict — with no row for the sheet
  just measured anywhere in the list or on the trend. Pressing *Generate
  report* would then have filed a report **about the older sheet**, stamped
  with this window's limits and this window's report type, while the page in
  front of the reader was supposed to be about the new one. Photographed on
  screen (`L1-the-window-on-a-measurement-with-no-report-of-its-own.png`) with
  the state built through the app's own `MeasurementSession` (the archive a
  real read leaves) and its own `_maybe_save_measurement_report` (which
  declined: 11 report files before and 11 after, read off disk rather than
  assumed).
- cause: `_gather_runs` decides whether to add the measurement in hand to its
  own history with `_report_is_about`, which matches on the run folder plus the
  bare file NAME. Every measurement of one run carries that pair, so eleven
  older reports answered "yes, it is already here". No row was added, and
  `_subject_of` then fell through to the newest SAVED report. It predates all
  three rounds; it was invisible while round 1 and round 2 were collapsing the
  rows, and it is the third face of the same wrong idea of what a measurement
  is.
- fix: `_is_this_measurement` asks `_measurement_for` — the identity B8-205 and
  B8-206 already built — from the other end, so the history, the rebuild and
  the subject cannot disagree about what a measurement is. ONE identity, three
  uses. `_report_is_about` is untouched and still right where it is used: it
  picks the subject out of a history that already holds the right row, and its
  deliberate looseness is what lets a report saved before the name was kept
  still belong to its folder.
- evidence: test_a_measurement_with_no_report_of_its_own_is_still_its_own_row,
  test_generate_files_a_report_about_the_measurement_in_hand,
  test_a_run_with_one_measurement_does_not_list_it_twice. MUTATIONS PROVED,
  each read back out of the file before the run that judged it: putting the
  guard back to `_report_is_about` turns 2 red, comparing `created` directly
  instead of asking `_measurement_for` turns 6 red (including four of the
  one-page-summary family, which is the duplicate-row failure this must not
  cause), and dropping the origin check turns
  `test_several_runs_still_each_get_their_own_row` red.

### B8-209 · Tools ▸ Measurement report opened on the profile run while the bar said Calibration
- blocks release: no
- status: FIXED
- found by: combined adversary round 3, 2026-09-15, walking the Tools menu
  door, which no round had reached (`drive_the_surfaces_no_round_reached.py`).
- detail: WHAT A USER SEES. Set Run type to Calibration, open Tools ▸
  Measurement report. The window describes the PROFILE run's measurement:
  driven on screen on `Demo-Switching`, `runs/run2/Demo-Switching.ti3` at **240
  patches**, with the calibration's own `cal/Demo-Switching-cal.ti3` — **64
  patches** — sitting unread beside it, and *Generate report* would have filed
  the report into `runs/run2/reports/`, which is another selection's folder.
  (`O-result.json`, `O1-tools-door-calibration.png`.)
- cause: `tools_dialogs._report_seed` reads "for a verification target the
  newest measured date; otherwise the run's own measurement". A calibration
  falls into "otherwise", and `resolve_run` hands back a RUN for a target that
  is not one. Same shape as `MainWindow._current_chart_ti2`'s "A CALIBRATION IS
  A THIRD TARGET, AND THIS KNEW ONLY ONE", and as beta.165's: two run types
  assumed where there are three.
- fix: the calibration is answered first, with `Calibration.ti3`, and a
  calibration that has nothing measured answers None rather than borrowing a
  run's measurement. `docs/design/tool_availability.md` §4 gives this tool ● in
  S5, noted *"Reports on a measurement this selection has"*; **that table is a
  DRAFT awaiting Knut's confirmation**, so what is fixed is only the part that
  needs no ruling — one selection's report must not be filed into another
  selection's folder. Whether a calibration with nothing measured should open
  empty or be greyed out is his call and is untouched.
- also: THE FIRST CUT OF THIS FIX WAS INERT and looked right on screen. It
  asked the Calibration for `measurement_ti3`, which is a Run's and a
  Verification's spelling and not a Calibration's; `_report_seed`'s
  `except Exception` swallowed the `AttributeError` and it answered None for
  every calibration, which is indistinguishable from "nothing measured yet". It
  was caught by driving the window again instead of trusting the edit, and
  `test_the_calibration_branch_is_not_swallowed_by_the_guard` asserts the file
  EXISTS as well as being returned so the inert version cannot come back.
- evidence: test_a_calibration_seeds_its_own_measurement,
  test_a_calibration_with_nothing_measured_borrows_no_run,
  test_the_calibration_branch_is_not_swallowed_by_the_guard,
  test_a_profiling_run_still_seeds_its_own_measurement,
  test_a_verification_still_seeds_its_newest_date. MUTATIONS PROVED, each read
  back out of the file before the run that judged it: removing the calibration
  branch turns 3 red, letting a calibration with nothing measured fall through
  to the run turns 1 red, and spelling it `measurement_ti3` again turns 2 red.

### B8-210 · The frame said 176.0 mm and the notice inside it said 0.0 mm
- blocks release: no
- status: FIXED
- found by: combined adversary round 3, 2026-09-15, attacking round 2's own
  fix (B8-204) with the question the coordinator asked of it: does the frame's
  own numbers still agree with the page the user is looking at
  (`drive_the_second_and_third_page.py`, re-run against this tree).
- detail: WHAT A USER SEES, photographed on a real three-page A4 chart at page
  3 of 3 (`P3-create-chart-on-page-3-of-3.png` and `P3-crop-the-frame.png`).
  The "Measured from Preview" frame printed **Right (to first patch) 176.0**
  and the red notice INSIDE THE SAME FRAME, an inch below it, said **"the right
  margin leaves 0.0 mm … Raise “Right” under “Margins (mm)” by about 5.1
  mm"**. Two numbers for one edge, 176 mm apart, on one screen, and the advice
  was wrong for the sheet in front of the reader: that page has 176 mm of room.
  The notices even name the frame while quoting their number ("the patch area
  in “Measured from Preview” comes down to …").
- cause: B8-204 made the notices judge the tightest page of the chart, which is
  right (paging forward used to make a red warning vanish), and deliberately
  left the frame showing the page on screen, which is also right (#83: the
  guides must land on the patches the reader can see). Nobody asked what the
  two say together. On a part-full last page they are different sheets.
- fix: neither half moves. One plain sentence is printed above the notices,
  naming the page the frame is measuring: *"The notices here are judged on the
  page of this chart where the edge is tightest, which is not the page on
  screen. The margins measured in this frame are page 3's own."* It appears
  only where the four edges actually differ, so pages 1 and 2 of the same chart
  are untouched (photographed: `P1-crop-the-frame.png`).
- and it goes on the panel's SURFACE, not onto its ⓘ. `text_warnings` reach
  the ⓘ only, and this panel's own comment says why that is not enough:
  *"an ⓘ is only read if it is asked for"*. The contradiction is between two
  numbers a reader sees at once. A new `notice_preamble` argument carries it,
  and it is deliberately NOT counted: a chart with one fault still says
  "1 warning".
- **for Basti's eye**: the sentence is painted in the same red as the notices,
  because the panel's status is one label with one ink. It is a qualifier and
  not a fault, so a quieter ink would read better if he wants one.
- evidence: test_the_reader_is_told_when_the_notice_is_about_another_page,
  test_the_two_sheets_are_compared_edge_by_edge,
  test_the_sentence_is_not_counted_as_a_warning,
  test_no_preamble_when_there_is_nothing_to_reconcile, alongside B8-204's
  eight, which stay green. MUTATIONS PROVED, each read back out of the file
  before the run that judged it: not passing `notice_preamble` turns 1 red,
  comparing the two reports by identity instead of edge by edge turns 1 red,
  counting the preamble as a warning turns 1 red, and not printing it turns 1
  red.
- also: the four sides were checked for the other half of the same question,
  whether the per-side worst can make up a sheet that does not exist. It
  cannot: every text-fit check reads exactly ONE measured edge
  (`_note_margin = _meas_r`, `_side_margin = _meas_r if _clip_on_right else
  _meas_l`, `_patch_top = _meas_t`, `_patch_bottom = _meas_b`), so no sentence
  mixes two pages' numbers into one arithmetic statement.

### B8-211 · "Measure again to average" left the report window describing the sheet before it
- blocks release: no
- status: FIXED
- found by: combined adversary round 4, 2026-09-15, attacking the
  measurement-identity rule the three rounds before it had re-keyed four times
  in one day (`drive_the_measurement_identity_from_both_ends.py`,
  `drive_averaging_replaces_the_measurement.py`).
- detail: WHAT A USER SEES. Measure a run, press *Generate report*, then press
  *Measure again to average* in the completion window, read the chart a second
  time and choose *Average*. The run now holds the AVERAGED sheet, which no
  saved report describes. Opened on it, the Measurement Report window:
  * with a report the current builder rebuilds, showed ONE row, dated with the
    saved report's own date, carrying the averaged sheet's numbers. The saved
    report holds **delta-E00 average 11.776, paper white A14 L\* 92.72**; the
    row read **13.513, C5 L\* 91.74** (`C-C-Averaged-Old-Report.png`).
  * with a report it does not rebuild, there was **no row for the averaged
    measurement at all**, no point for it on the trend, and *Generate report*
    would have filed a report about the older sheet
    (`C-C-Averaged-Today.png`).
  Both are the faults B8-205 and B8-208 record, reappearing through a door
  neither of them had.
- cause: B8-206 made the FOLDER settle the identity wherever the ``created``
  stamp has moved for an innocent reason, and its two tests are proxies for
  "this folder has held more than one measurement under that name": an archive
  in ``old/<when>/``, or a second saved report date. **Averaging leaves
  neither.** `Run.promote_measurement_to_read` MOVES ``<stem>.ti3`` into
  ``reads/readN.ti3``, so the next read's `MeasurementSession.begin` finds no
  file to archive, and `_run_average_and_proceed` then writes the averaged
  sheet straight over `Run.measurement_ti3`. Built with the app's own moves and
  ArgyllCMS `average` on two real reads of one chart: no `old/` folder existed
  at all.
- fix: the file is asked before the folder.
  `workflow.measurement_report.measurement_facts` is THE ONE RULE for the three
  facts a report records about its own measurement (``patches``,
  ``paper_white``, ``max_black``) — `build_report` now writes them through it
  and `facts_disagree` reads them back, so the writer and the reader cannot
  drift. `_measurement_for` refuses a file whose own facts contradict the
  report's. It is one-sided on purpose: agreement is not proof, so the folder
  tests still run underneath, and ``reads/`` joins them there.
- and NOT in a dated verification folder, which is B8-206's own sentence rather
  than a new exception: such a folder holds exactly one measurement (a replaced
  verification is archived into ``verifications/old/``, outside it). It matters
  because **the demo package writes a STUB report into each dated folder** to
  give the history its date: schema 5, no accuracy block at all,
  ``"patches": 240`` and a paper white of L\* 95.4 beside a real 64-patch sheet
  whose white is L\* 99.53. Measured on `Demo-Switching` and
  `Demo-Prefs-Speed`, both dates. Asking the file there took the accuracy
  figures off exactly the two rows B8-206 exists to keep, which is how this was
  caught: the first cut was driven against the demo package and both dated rows
  came back `avg_all: None` again.
- also measured and NOT changed: the three callers of the identity were driven
  rather than read, and they agree. A report written by a ChromIQ old enough to
  stamp ``created`` with the moment *Generate* was pressed (the rule changed in
  `05e1e92d`, 2026-07-21; 25 of the 58 saved reports on one real disk predate
  it) is handled correctly in all four shapes driven: one such report with the
  archive gone, two of them, one with the archives in place, and one after a
  rename. The app's own rename renames the ``old/`` archives along with
  everything else (driven through `FileManager.rename_existing_project` and
  read back off disk), so the archive test is not blinded by a rename.
- evidence: test_an_averaged_run_keeps_its_reports_own_numbers,
  test_the_averaged_measurement_gets_a_row_of_its_own,
  test_generate_would_file_about_the_averaged_sheet,
  test_a_reads_folder_says_the_run_has_held_another_measurement,
  test_the_file_itself_tells_two_sheets_apart,
  test_a_different_number_of_readings_is_a_different_measurement,
  test_facts_disagree_reads_a_report_of_every_schema_on_disk,
  test_measurement_facts_is_the_rule_build_report_writes,
  test_a_measurement_that_cannot_be_read_is_not_evidence,
  test_a_dated_verification_is_still_rebuilt_from_the_file_in_its_folder,
  alongside B8-205's and B8-206's fifteen, which stay green. MUTATIONS PROVED,
  nine, each read back out of the file before the run that judged it: removing
  BOTH the facts check and the ``reads/`` test turns 4 red (the three headline
  ones and the ``reads/`` one); removing only the ``reads/`` test turns 1 red;
  applying the facts check in a dated verification folder too turns 1 red;
  making `facts_disagree` compare nothing turns 4; letting it answer True when
  the file cannot be read turns 1; dropping `_point_L`'s schema-5 branch turns
  1; having `build_report` compute its own paper white a second way turns 2;
  dropping the patch-count comparison turns 1. Removing ONLY the facts check
  turns nothing red, on purpose and recorded in the tests: either guard catches
  the averaging state on its own, which is why there are two.

### B8-212 · A second import stopped at the stored-chart question kept the run it had just made
- blocks release: no
- status: FIXED
- found by: combined adversary round 4, 2026-09-15, settling the second
  question round 3 measured and deliberately did not report — import, then
  import again — by answering every window with a click on its own button
  (`drive_import_then_import_again.py`, `drive_the_import_that_is_stopped.py`).
- detail: WHAT A USER SEES. Import a measurement into Run 1. Later the run's
  stored chart stops matching the chart it holds (regenerate the chart, or
  answer *Keep stored chart* once, which ChromIQ records as
  `chart_snapshot_stale`). Import a second measurement, answer *Make a new
  run*, and then press **Cancel** on *Stored chart differs*. Driven on screen:
  **Run 2 stayed on disk and in `project.json` holding no measurement**, the
  bar was left standing on it (*Location being edited: runs/run2/*), the file
  was not imported, and **nothing at all was said** (`N-result.json`).
- cause: §I.9 step 3 duplicates the run and points the bar at the copy — that
  order is deliberate, because `_snapshot_profiling_chart` reads the bar to
  decide which run to copy a chart into. Step 4 then read
  `if not self._snapshot_verification_chart(): return`, with no rollback. Every
  other refusal on this door undoes the run it made and says so, and the
  sibling door has `_undo_the_run` for exactly this; only the one refusal that
  can happen AFTER the duplicate was missing it. It is the same shape round 2
  fixed on the new-project door ("Run 4 created by an import that was then
  refused") and the same silence this door's own comment records fixing on four
  other routes.
- fix: the run is undone through `_undo_the_run` — the sibling door's function,
  not a second copy of it — the bar is put back on the run the person was
  standing on, and they are told: *"The measurement was not imported / You
  stopped at the stored-chart question, so nothing has been imported and
  nothing has been changed. The new run ChromIQ had started making has been
  removed again, and your own file is untouched where it is."* German
  translated; the other eleven catalogues carry the English source, which is
  this project's beta practice. The wording follows this door's existing
  refusals; **it is Basti's to change.**
- and the question that was open is ANSWERED: import, then import again, with
  every window clicked rather than stubbed, is otherwise clean. Both runs end
  holding their own measurement, their own chart and their own chart snapshot,
  `project.json` agrees with the disk, and nothing is written outside the run
  the file went into (`M-result.json`).
- also: the first cut of this drive reported two faults that were its own.
  Renaming the source project's artefacts with `printer-test.*` misses
  `printer-test_01.tif`, so the duplicated run had a chart snapshot holding a
  TIFF its live folder did not — and *Stored chart differs* fired on a run that
  had just been copied from the one beside it. And a run left on "New run" is
  refused by `_blocked_by_new_run` before an import starts. Both were found by
  reading the disk rather than believing the window.
- evidence: test_stopping_at_the_stored_chart_question_undoes_the_run_it_made,
  test_stopping_there_puts_the_bar_back_on_the_run_the_person_was_on,
  test_stopping_there_says_so_rather_than_doing_nothing,
  test_the_measurement_is_not_filed_when_the_question_is_stopped,
  test_answering_the_chart_question_still_files_into_the_new_run. MUTATIONS
  PROVED, four, each read back out of the file before the run that judged it:
  putting step 4 back to a bare `return` turns 3 red, dropping the line that
  puts the bar back turns 1, removing the sentence turns 1, and rolling the run
  back even when the import goes on turns 13 red — which is the behaviour this
  must not eat.

### B8-213 · "Use last read only" left the run holding no measurement at all
- blocks release: no
- status: FIXED
- found by: combined adversary round 5, 2026-09-15, pointed at the averaging
  path round 4 had only reached at its very end
  (`drive_averaging_endings.py`, `drive_second_read_stopped.py`, driven in real
  windows in `~/Desktop/ChromIQ-beta18-proof/combined-round-5/`).
- detail: WHAT A USER SEES. Switch *Enable measurement averaging* on, measure a
  chart, press **Measure again to average**, read it a second time, then press
  **Use last read only**. The run folder is left holding **no `.ti3` at all**:
  the reading lives only in `reads/read2.ti3`. Measured on screen with two real
  90-patch reads of one chart (`A-result.json`, `A2-A2-the-report-window.png`):
  * the Measurement Report window, opened on that run, showed **zero rows**;
  * the report the *Save a measurement report* option writes automatically went
    to `runs/run1/reads/reports/` — a folder nothing in ChromIQ ever lists —
    carrying `"ti3": "read2.ti3"`, `"chart": "read2"`,
    `"sheet_kind": "standalone"` and no verdict set, judged against a **device**
    reference at delta-E00 16.346 instead of the chart's own at 16.379, because
    `_find_reference_ti2` cannot see a chart from inside `reads/`;
  * and the log said *"[Report] Measurement report saved"* about it.
  The same ending is what **closing the completion window** does: `use_last` is
  its default action whenever two or more reads exist.
- and the second door: **Measure again to average** followed by a second read
  that produces no file (Stop before the first patch, or any failure) left the
  run holding nothing while ChromIQ said *"no measurement (.ti3) file was
  created"* about a chart that had been measured perfectly well a minute
  earlier. Driven through the app's own `_on_measure_done`
  (`C-result.json`).
- cause: `Run.promote_measurement_to_read` MOVES `<stem>.ti3` into
  `reads/readN.ti3`. The *Average all reads & build* ending writes its result
  back to `Run.measurement_ti3`; none of the other endings of the same set put
  anything back.
- why it matters is the specification's own sentence. §I.7 of
  `docs/design/unified_measurement_management.md` requires a filed measurement
  to take the run's canonical stem, *"because the report finds its chart by
  that stem (`measurement_report._find_reference_ti2`) and a measurement filed
  under any other name falls back to `reference_source: device` without saying
  so"*. That clause is written for the IMPORT door; nothing in the
  specification covers the averaging endings, and the fix applies the clause's
  own stated reason rather than making a new ruling.
- fix: `_keep_the_read_as_the_runs_measurement` copies the read an ending
  builds from back to `Run.measurement_ti3` and hands THAT path on, so the
  report, the limit set, Build Profile, the window and a restart all see the
  sheet the run is about to be judged from; the per-read snapshots stay in
  `reads/` exactly as the averaging ending leaves them. A copy that fails is
  logged and the ending still happens.
  `_restore_a_read_when_the_set_lost_its_measurement` puts the most recent read
  back — a COPY, so the live set keeps every read — when a read produced no
  file at all, and says what was kept.
- measured after the fix, on screen (`B-result.json`,
  `B2-B2-the-report-window.png`): the run holds its own `.ti3`, the report is
  in `runs/run1/reports/` as `"sheet_kind": "profiling"` with delta-E00 16.379
  against the chart, and the window shows the row. In German and in the dark
  appearance as well (`H-result.json`, `H1-messung-abgeschlossen-dunkel.png`,
  `H3-messbericht-deutsch-dunkel.png`), with the catalogue proved loaded rather
  than assumed.
- also measured and NOT changed: a project a beta already left in that state is
  opened honestly. Four such folders were opened cold in a real window
  (`I-result.json`): reads with no measurement, one read with no measurement,
  the averaged run, and a saved report beside a file that is not there. None
  raised, none claimed a measurement it did not have, and none offered a build.
  Nothing offers the orphaned readings BACK, which is
  `docs/dev_averaging.md`'s own deferred Phase 5, not a new fault; after this
  fix the app can no longer create the state.
- evidence: test_use_last_read_only_leaves_the_run_holding_that_read,
  test_use_last_read_only_keeps_every_read_in_the_reads_folder,
  test_use_last_read_only_hands_build_profile_the_runs_own_file,
  test_use_last_read_only_files_its_report_where_the_run_can_see_it,
  test_the_report_is_judged_against_the_runs_own_chart,
  test_closing_the_completion_window_is_the_same_ending,
  test_a_stopped_second_read_keeps_the_reading_already_taken,
  test_the_restore_is_a_copy_so_the_set_keeps_every_read,
  test_the_restore_says_what_was_kept,
  test_the_ending_that_produced_a_file_is_left_alone,
  test_a_standalone_read_is_never_copied_anywhere,
  test_a_copy_that_fails_still_ends_the_measurement. MUTATIONS PROVED, two,
  each read back out of the file before the run that judged it: removing the
  `_keep_the_read_as_the_runs_measurement` call turns 4 red, and making
  `_restore_a_read_when_the_set_lost_its_measurement` return at once turns 1
  more.

### B8-214 · A refused copy said "nothing has been changed" over a run it had just made
- blocks release: no
- status: FIXED
- found by: combined adversary round 5, 2026-09-15, attacking round 4's own
  fix (`drive_import_copy_fails.py`).
- detail: WHAT A USER SEES. Import a measurement into a profiling run that
  already holds one, answer **Make a new run**, and let the copy that files the
  measurement fail — a full disk, a read-only folder, a share that has gone
  away. ChromIQ says *"The measurement has not been filed, and nothing has been
  changed."* Driven on screen with the copy refused once
  (`F-result.json`, `F1-after-the-refused-copy.png`): **run 2 was still on
  disk**, still in `project.json`, `current_run` still pointed at it and the
  bar still read *"Location being edited: runs/run2/"*. The sentence was false.
- cause: round 4 gave step 4's refusal (*Stored chart differs*) the rollback
  every other refusal on this door has. The copy at step 5, one line further
  along, was left with a bare `return`. The SIBLING door in
  `ui/measurement_filing.py` has always called `_undo_the_run` at exactly this
  failure and with the same words, so the two doors described the same accident
  differently.
- fix: the same rollback, and a sentence that is true. When the import made a
  run, it is undone, the bar is put back on the run the person was standing on,
  and the window says the new run has been removed again; when no run was made
  there is nothing to remove and the plain sentence is used.
- measured after the fix (`G-result.json`, `J-result.json`): the manifest is
  back to `["run1"]`, `current_run` is `run1`, the bar reads `runs/run1/`, and
  **nothing anywhere on disk names the run that was rolled back** — not in
  `project.json`, not in the sandboxed settings, not in the presets folder, and
  the folder itself is gone. That is the brief's own question about whether the
  rollback reaches outside the run folder, answered by reading the disk.
- evidence: test_a_refused_copy_undoes_the_run_the_import_made,
  test_a_refused_copy_puts_the_bar_back,
  test_a_refused_copy_says_what_it_actually_did,
  test_the_run_that_was_full_keeps_what_it_had,
  test_a_refused_copy_with_no_run_to_undo_still_says_the_plain_sentence.
  MUTATIONS PROVED, three, each read back out of the file before the run that
  judged it: dropping the `_undo_the_run` call turns 2 red, making the sentence
  unconditionally the "removed again" one turns 1, and making it unconditionally
  the plain one turns 1.

### B8-215 · An average that refused left the run holding no measurement at all
- blocks release: no
- status: FIXED
- found by: combined adversary round 6, 2026-09-15, attacking round 5's own
  fix from the side it does not reach (`drive_averaging_failed.py`).
- detail: WHAT A USER SEES. Switch averaging on, measure, press **Measure
  again to average**, read again, press **Average all reads & build**, and let
  `average` refuse. It refuses for ordinary reasons ArgyllCMS has its own
  messages for: reads with different field sets or different patch counts, a
  measurement file it cannot read, or simply a non-zero exit because the output
  could not be written. Driven on screen with a REAL Argyll refusal
  (`A-result.json`, `A1-the-averaging-failed-window.png`,
  `A2-the-build-profile-tab-it-sends-you-to.png`,
  `A3-the-report-window-after-the-refusal.png`): two promoted reads,
  `average: Error - File 'reads/read2.ti3' has 15 sets, file 'reads/read1.ti3
  has 90`, and afterwards the run folder held **no `.ti3` at all**, the
  Measurement Report window opened on that run with **zero rows**, and the
  Build Profile tab read **"No file selected"** — under a window whose last
  sentence promises that the individual reads are still saved and that the
  person can continue from the Build Profile tab using one of them.
- cause: `Run.promote_measurement_to_read` MOVES every read into
  `reads/readN.ti3`, and `AverageRunner` writes its output only on success. The
  failure branch of `_run_average_and_proceed` showed its window and returned.
  It is the THIRD ending of the shape round 5 fixed (B8-213) and the only one
  that can only ever be reached when something has already gone wrong, which is
  why five rounds walked past it.
- fix: the mechanism round 5 wrote is now shared rather than copied
  (`_put_the_last_read_back`) and this branch calls it: the newest read is
  COPIED back to `Run.measurement_ti3`, `reads/` keeps every read it has, the
  log names the read that was kept, and `measure_finished` arms the tab the
  window sends the person to. The failure window is unchanged and still shown.
- measured after the fix (`D-result.json`): the run folder holds its own
  `.ti3` again, `reads/` still holds `read1.ti3` and `read2.ti3`, the dated
  report lands in the run's own `reports/` rather than nowhere, the Measurement
  Report window shows its row instead of none, and the Build Profile tab holds
  the run's measurement — which is what makes the window's sentence true rather
  than merely hopeful.
- evidence: test_a_refused_average_leaves_the_run_holding_a_measurement,
  test_the_measurement_it_keeps_is_the_read_taken_last,
  test_every_read_is_still_in_the_reads_folder,
  test_the_tab_the_window_names_is_armed_with_it,
  test_the_log_says_which_read_it_kept,
  test_the_failure_window_is_still_shown,
  test_a_run_that_still_holds_a_measurement_is_not_written_over,
  test_a_refusal_with_nothing_in_reads_says_nothing_and_does_nothing,
  test_both_endings_put_a_read_back_through_the_same_helper,
  test_the_helper_copies_rather_than_moves. MUTATIONS PROVED, four, each read
  back out of the file before the run that judged it: dropping the
  `_put_the_last_read_back` call turns 5 red, dropping the
  `measure_finished.emit` turns 1, keeping `reads[0]` instead of `reads[-1]`
  turns 1, and removing the "the run already holds one" guard turns 1.

### B8-216 · A refused import moved the project to another run, under "nothing has been changed"
- blocks release: no
- status: FIXED
- found by: combined adversary round 6, 2026-09-15
  (`drive_duplicate_refused.py`, `probe_duplicate_run_drift.py`).
- detail: WHAT A USER SEES. A three-run project standing on Run 1. Import a
  measurement into Run 1, which already holds one; answer **Make a new run**;
  the copy is refused, as a full disk or a share that has gone away refuses it.
  ChromIQ says *"Nothing has been imported and nothing has been changed."*
  Driven on screen (`B-result.json`,
  `B2-the-refusal-that-moved-the-project.png`): afterwards `project.json` read
  `current_run: run3`, and a fresh open of that project stood on **Run 3**, not
  the run the person had been working in.
- cause: `Project.duplicate_run` makes the new run with `new_run()`, runs its
  OWN `_discard_run(just_created=True)` rollback when the copy fails — which
  points `current_run` at `runs[-1]` — and then RE-RAISES. `_undo_the_run` is
  the shared function written for exactly this accident, and its own docstring
  describes it in these words; but it began `if made_here is None: return`, and
  `made_here` is still None at this handler because it is assigned on the line
  AFTER the one that raised. So the restore was dead code at the one refusal it
  was written for, on BOTH import doors, and the Measure tab's door never
  called it there at all. Round 4 found the same restore dead for a different
  reason (a field name that does not exist); this is the second way it read as
  a fix and did nothing.
- fix: discarding a run is now conditional in `_undo_the_run` and putting the
  manifest back is not — every caller is on a refusal path, and on a refusal
  path the project belongs where the person left it. The Measure tab's two
  step-3 refusals call it through `_put_the_project_back`, with the MANIFEST's
  own value (`run_the_project_is_on`) rather than the bar's, because the bar
  can read "New run" while the manifest names a run.
- measured after the fix (`C-result.json`): the same journey, the same refusal,
  and afterwards `current_run` is `run1` and a fresh open stands on Run 1.
- evidence: test_a_refused_duplicate_really_does_move_the_manifest,
  test_undo_the_run_puts_the_project_back_with_no_run_to_discard,
  test_undo_the_run_still_discards_a_run_it_made,
  test_undo_the_run_with_nothing_to_go_back_to_changes_nothing,
  test_a_run_that_is_gone_is_not_restored_over,
  test_the_measure_tabs_import_puts_the_project_back,
  test_both_of_the_measure_tabs_refusals_call_it. MUTATIONS PROVED, two, each
  read back out of the file before the run that judged it: restoring
  `_undo_the_run`'s `if made_here is None: return` turns 2 red, and dropping
  the Measure tab's `_put_the_project_back` calls turns 1.

### B8-217 · Two Measure-tab options cannot be read in seven languages
- blocks release: no
- status: OPEN
- found by: combined adversary round 6, 2026-09-15, sweeping the merged set as
  a first-time user in German and in the dark appearance
  (`probe_clipped_everywhere.py`, `E5-messen-tab-dunkel-deutsch.png`).
- detail: WHAT A USER SEES. On the Measure tab, under **Live preview**, the two
  options "Show only measured patches" and "Show patch values on hover" share
  one row. In German they read *"Nur gemessene Messfelder anzeig"* and
  *"Messfeldwerte beim Überfahren a"*: hard-clipped mid-word, with no ellipsis.
  Measured rather than read off the photograph, as given-width against the
  width the control's own text needs: de 231 vs 241 and 231 vs 269, pt 231 vs
  244 and 231 vs 283, ru 231 vs 261 and 231 vs 292, es 240 vs 299, it 269 vs
  319, fr 231 vs 261, nl 238 vs 244. Ten controls across seven languages.
  English, Norwegian, Polish, Swedish, Japanese and Chinese all fit.
- and widening the window does not help: measured at 1480, 1800 and the full
  1728 px screen, the width given stays 231 px, because `tab_measure.py:1881`
  pins the left pane with `setFixedWidth(580)` while its own `sizeHint` there is
  636.
- the same sweep over every checkbox, radio button and push button on all five
  tabs in all thirteen languages found NOTHING else: the only other hit is the
  `✕` button on Check & Refine, 28 px against a `sizeHint` of 80, which is a
  one-glyph button at Qt's minimum button width and reads correctly in every
  language including English. A false positive of the probe, named here so
  nobody re-finds it.
- not a regression of the merged set: `setFixedWidth(580)` dates from
  `744f54c1`, 2026-04-29, *"fixed panel widths"*. The project's own guard for
  this (`test_i18n.py::test_short_labels_stay_compact`) skips any English source
  longer than 24 characters, and both of these are 26.
- why it is not fixed here: both remedies are a decision, not a repair. Either
  the two options stop sharing a row, which is the layout Basti asked for in as
  many words, or the translations are shortened, which the standing rule freezes
  during a beta. Reported with the numbers so the choice can be made rather than
  made for him.

---

### B8-218 · "Measure again to average" moved the reading away, then the read never started
- blocks release: yes
- status: FIXED
- found by: combined adversary round 7, 2026-09-16, pointed at the averaging
  door's one remaining branch. Rounds 5 and 6 closed every ending that happens
  AFTER chartread has run; this is the one where chartread never runs at all.
- detail: WHAT A USER SAW, driven on screen in a real window on a real
  240-patch measurement, with TWO DIFFERENT real refusals. Press **Measure
  again to average** at "Measurement Complete", then press **Cancel** on the
  next window ChromIQ shows:

  * "Stored chart differs" (`A-result.json`, `A2-stored-chart-differs.png`), whose own words are
    *"Cancel - nothing is written and no measurement starts"* and whose last
    paragraph reads *"You are averaging several readings of this run."*
  * the fixed-order bidirectional warning (`B-result.json`,
    `B3-Bidirectional-reading-on-a-fixed-order-chart.png`), where **Cancel is
    the DEFAULT button**, so a stray Return lands on it.

  Afterwards, in both, identically:
  * the run folder held **no `.ti3` at all**; the reading was in
    `reads/read1.ti3`,
  * **nothing whatever was said** - the log's last line was still
    "[INFO] First read saved as reads/read1.ti3",
  * the Build Profile tab still NAMED `runs/run1/<chart>.ti3`, a file that no
    longer existed (`B9-the-build-profile-tab.png`), and pressing **Build
    Profile** answered "[ERROR] No valid .ti3 file selected." about a chart
    that had been measured perfectly well a minute earlier.
- cause: `_apply_completion_action("again")` calls
  `Run.promote_measurement_to_read`, which MOVES the measurement into
  `reads/readN.ti3`, and only then fires `_start_averaging_read` through a
  zero-delay timer. `_on_start` has **12 early returns**, several of them
  windows with a Cancel button, and `_start_averaging_read` ended on a bare
  `self._on_start()`.
- fix: `_start_averaging_read` reads `_session_live` after `_on_start` returns.
  That is the marker `_on_start` sets at its own point of no return, one line
  before `self._manager.start(...)`, so every refusal above it leaves it False.
  The restore is round 5's own mechanism AND round 5's own sentence, so **no new
  user-facing string was added and no translation is missing**. Not assigned
  here, only read: writing it would be the one way this could switch off a
  session that really is live.
- proved after: `C-result.json` / `D-result.json`, the same two drives on the
  fixed tree - the run holds its `.ti3` again, `reads/read1.ti3` is still there
  (a COPY, never a move), the log carries the true sentence, and pressing Build
  Profile really runs the profiler.
- evidence: test_measure_again_really_does_empty_the_run_first,
  test_a_read_that_never_starts_leaves_the_run_holding_a_measurement,
  test_the_measurement_it_puts_back_is_the_reading_that_was_taken,
  test_the_read_is_still_in_the_reads_folder,
  test_the_log_says_what_was_kept,
  test_the_set_is_still_live_so_the_next_read_still_averages,
  test_a_read_that_really_starts_is_not_interfered_with,
  test_nothing_is_put_back_when_the_set_is_not_live,
  test_the_start_is_judged_by_the_marker_on_start_actually_sets,
  test_start_averaging_read_never_assigns_the_marker,
  test_on_start_still_sets_the_marker_at_its_point_of_no_return.
  Two mutations proved to land and both caught: removing the restore (4 tests
  red) and restoring UNCONDITIONALLY, over a read that really started (2 red).

---

### B8-219 · The only lines naming where a profile's history went were erased milliseconds later
- blocks release: no
- status: FIXED
- found by: combined adversary round 7, 2026-09-16, enumerating the same shape
  on doors no combined round had looked at.
- detail: "Build here anyway" on M-PROFILE-VERIFY runs
  `_archive_superseded_profile`, which MOVES the run's built profile into
  `runs/runN/old/<timestamp>/` and EVERY dated verification measurement into
  `verifications/old/<timestamp>/`, and writes the two lines naming those exact
  folders into the Build Profile tab's log. `_on_build` then called
  `self._log.clear()` seven lines further down.
- driven on screen on a real project holding a real profile and two real dated
  verifications (`E-result.json`, `E1-the-question-that-archives-them.png`): after "Build here anyway",
  `old/2026-09-16_000225/Demo-Switching.icc` and
  `verifications/old/2026-09-16_000225/` holding both dated folders - and a log
  showing the profiler's output and nothing else. The clear was WATCHED at the
  instant it fired and it held exactly those two lines.
- GRADED HONESTLY, because it is smaller than it looks: the window above
  already names `old/` and the `old` folder inside `verifications`, so nobody
  is stranded and nothing is lost. What is lost is the TIMESTAMPED folder, the
  one thing that says which archive is theirs when a run has several.
- fix: the clear moves ABOVE the questions, which is the same fix
  `ui/tabs/tab_measure.py::_on_start` records in its own words for the
  calibration messages - they were *"erased milliseconds after being written…
  None of it had ever been seen by anybody."* Safe because the one thing
  written before it, "No valid .ti3 file selected", returns immediately.
- proved after: `H-result.json` - both lines stand at the top of the on-screen
  log, above the profiler's output.
- evidence: test_the_archive_really_names_its_folders_in_the_tabs_log,
  test_the_archive_really_moves_the_profile_and_the_verifications,
  test_the_question_that_archives_is_asked_from_on_build,
  test_the_log_is_cleared_before_the_question_that_archives,
  test_the_log_is_cleared_before_every_step_that_writes_into_it,
  test_the_log_is_cleared_exactly_once_in_on_build,
  test_the_first_refusal_still_says_its_piece.
  Two mutations proved to land and both caught: the clear moved back below the
  archive (2 red), and "keeping" it by clearing TWICE (1 red).
- a note for the next reader, not a fault: these order tests read `_on_build`
  with its docstring and every `#` comment STRIPPED. The first version indexed
  raw source and went red on a correct tree, because the comment explaining the
  fix names `_confirm_rebuild_over_verifications` in prose above the clear. The
  same hazard is live in the existing
  `test_rebuild_warning_wiring.py::test_the_question_comes_before_the_build`,
  which indexes raw source for "colprof" and went red on this round's comment
  until the word was removed from it. It fails SAFE (a false alarm, never a
  false pass) and was left alone.

---

### B8-220 · A reader that could not be launched said nothing, and left the Measure tab stuck for ever
- blocks release: yes
- status: FIXED
- found by: combined adversary round 8, 2026-09-16, asking whether round 7's
  `_session_live` marker is true in every state. It is. The state it cannot
  reach is the one where `_on_start` never RETURNS at all.
- detail: `ArgyllRunner.run`'s QProcess path connects `errorOccurred` for
  exactly this, and says why in its own words: *"A PROCESS THAT NEVER STARTS
  MUST STILL REPORT BACK … every caller's `on_finish` was simply never
  called."* The three launchers underneath it had no such handler.
  `_run_pty` — the path stock chartread ALWAYS takes, because
  `MeasureManager._launch_stock` passes `use_pty=True` — calls
  `subprocess.Popen` bare, and a missing binary raises `FileNotFoundError`
  inside the Qt slot that pressed the button. `main.py` installs a
  `sys.excepthook`, so the process does not die: the exception is logged where
  no user looks and the call stops halfway, one line past
  `self._session_live = True`.
- reached the way a user reaches it, and the status line says so out loud:
  the ArgyllCMS folder in Preferences pointing somewhere wrong (moved, renamed,
  on a volume that went away, mistyped), with ArgyllCMS not on `PATH` —  which
  is the ordinary shape of a machine, because ChromIQ's default is
  `/Applications/Argyll/bin` and nothing puts Argyll on `PATH`.
  `_check_argyll_binaries(initial=False)` warns and leaves the path alone, by
  design; only the launch was unguarded.
- driven on screen, twice, in real windows (`H-result.json`, `I-result.json`,
  `H8-what-the-person-is-left-with.png`):
  - **Start Measurement**, answering *Measure anyway* to "This chart is fully
    measured": the Measure tab shows "Progress: 0.0%", **Start greyed, Stop
    live**, every option greyed and *"Keep calm! Scan each strip with a slow,
    steady motion."* Nothing is running. The finished measurement has already
    been moved into `runs/run1/old/<date>/`, so the run holds **no `.ti3` at
    all**, and the log's last line says only that it was moved. There is no way
    back but restarting the app, and `_session_live` stays True so the app-wide
    event filter goes on eating arrow keys everywhere in ChromIQ — measured,
    `eventFilter` returned True for a Left arrow.
  - **Measure again to average**: the run holds no `.ti3`, the reading is
    stranded in `reads/read1.ti3`, **the log is completely empty** and the
    Build Profile tab still names the file that has gone. That is B8-218's own
    damage, reached one line ABOVE the check round 7 added to undo it.
- a correction to this round's own first two drives, recorded because it was
  nearly reported as a finding: run WITHOUT `main.py`'s `sys.excepthook` the
  same press exits **134 (SIGABRT)**, because PyQt6 answers an unhandled slot
  exception with `qFatal()` only while the default hook is installed. Measured
  both ways (`probe-default.log`, `probe-mainpy.log`). **The shipped app does
  not crash.** A driver that does not install what `main.py` installs is
  measuring a different program.
- fix: `ArgyllRunner._the_tool_never_started` — the launch failure is reported
  exactly as the QProcess path reports it (`last_failed_to_start` set,
  `on_finish(-1)`), through a zero-delay timer so the caller still standing in
  `_on_start` is never re-entered, and with one line into the run's OWN output
  so the ending's *"see output above"* points at something. All three launchers
  are guarded, and the pty's two descriptors are closed on the failing path.
  Nothing else changed: every ending that already exists then gets its turn.
- proved after, on screen (`E-result.json`, `F-result.json`):
  - Start Measurement: §S3's own window, *"Because nothing was measured, your
    previous measurement has been put back exactly where it was — this read has
    changed nothing at all"*, and the run **holds its `.ti3` again**;
    `_session_live` False, Start live, Stop grey, the arrow key no longer eaten.
  - Measure again to average: round 5's own sentence, *"The reading you already
    took is kept: read1.ti3 is this run's measurement again"*, the run holding
    its `.ti3` and `reads/read1.ti3` still there.
- evidence: test_a_pty_reader_that_cannot_start_calls_on_finish,
  test_the_launch_failure_never_escapes_into_the_caller,
  test_nothing_is_left_running_after_a_failed_launch,
  test_the_failed_tool_is_named_for_the_tab_that_asked,
  test_the_run_output_says_why_before_the_ending_reads_it,
  test_the_reason_arrives_before_the_finish,
  test_the_pty_is_not_leaked_when_the_launch_fails,
  test_all_three_launchers_are_present_to_be_checked,
  test_every_launcher_guards_the_call_that_starts_the_process,
  test_the_reporter_does_not_re_enter_its_caller.
  Three mutations proved to land and all three caught: the `_run_pty` guard
  removed, back to a bare Popen (8 red); the guard kept but the pty left open
  (1 red, 25 descriptors to 49); the guard kept but the reason no longer said
  in the run's output (2 red).
- a note for the next reader: `workflow/spot_read_manager.py` is the other
  `use_pty=True` caller (Tools ▸ read single patches) and is covered by the
  same fix, because the guard is in the launcher rather than in either caller.
- the same shape swept for, across every door, from the AST: after this fix the
  only bare launch left in shipped code was the stray-chartread sweep in
  `_on_start` itself (`killall` / `taskkill`), which is now guarded too —
  UNDRIVEN, and recorded as such: they are system binaries and this round could
  not make either missing. `workflow/chart_creator._probe` (targen/printtarg,
  the patch-capacity binary search) is bare as well and is **not** a fault: its
  only caller, `tab_chart` at the Generate Chart door, already wraps it in
  `except Exception`, says "Auto patch estimation failed", re-enables the button
  and drops the shield. Examined and cleared.
  evidence: test_the_start_path_launches_nothing_without_a_guard,
  test_every_early_return_in_on_start_is_above_the_marker (which re-derives
  round 7's marker invariant rather than taking it on trust). Two further
  mutations proved to land and both caught: the sweep's guard removed (1 red),
  and an early return moved BELOW the marker (1 red).

---

### B8-221 · "Nothing was changed in your project", said after the profile and every verification had been moved
- blocks release: no
- status: FIXED
- found by: combined adversary round 8, 2026-09-16 — round 7's LEAD 1, forced.
- detail: `_on_build` → `_confirm_rebuild_over_verifications` →
  `_archive_superseded_profile` MOVES the run's built profile into
  `runs/runN/old/<date>/` and EVERY dated verification measurement into
  `verifications/old/<date>/`, and only THEN is colprof launched. With the
  ArgyllCMS folder wrong, colprof never starts and
  `_report_if_the_tool_could_not_start` shows a window ending with the words
  **"Nothing was changed in your project."**
- why round 7 could not force it, and it said so rather than guessing: its two
  probes pointed `argyll_bin_path` at nothing, and `ArgyllRunner._resolve`
  falls back to a bare `PATH` lookup which found a perfectly good colprof. The
  PATH has to go too, which is what a real machine looks like.
- driven on screen (`D-result.json`,
  `D2-ChromIQ-could-not-start-colprof.png`) on a real project holding a real
  profile and two real dated verification measurements: after *Build here
  anyway* the run held **no profile at all** — the `.icc` in
  `old/2026-09-16_003327/` and both verifications in
  `verifications/old/2026-09-16_003327/` — under that window, photographed,
  saying nothing had been changed.
- fix: ask BEFORE anything is moved.
  `_refuse_when_the_profiler_is_not_installed` sits above both questions, which
  is round 7's own fix for the archive's log lines in this very method: move
  the step above the question instead of undoing it below. Nothing is moved, so
  the sentence the window already says is TRUE, **no new message text was
  needed and no translation is missing**. It stands down for the profile engine
  (which may not need ArgyllCMS at all) and for a multi-ink measurement, which
  has its own window.
  `ArgyllRunner.tool_is_installed` asks the configured folder AND `PATH`, in
  that order, because `_resolve`'s bare-name answer would otherwise call a
  working `PATH` install missing and refuse a build that would have run.
- proved after (`G-result.json`): the archive question is never asked, the
  `.icc` is still in the run, both verifications are still in
  `verifications/`, there is no `old/` anywhere, and the window is the only
  thing that happens.
- evidence: test_the_refusal_is_asked_from_on_build,
  test_the_refusal_comes_before_the_question_that_archives,
  test_the_refusal_stops_the_build,
  test_the_window_still_claims_nothing_was_changed,
  test_a_path_install_is_not_called_missing,
  test_a_missing_tool_is_reported_missing,
  test_a_folder_holding_something_unrunnable_is_not_installed,
  test_the_question_that_archives_is_never_asked_when_the_builder_is_missing,
  test_a_build_that_cannot_start_leaves_the_profile_where_it_was,
  test_the_refusal_stands_down_when_the_engine_is_the_builder.
  Two mutations proved to land and both caught: the refusal moved BELOW the
  archive question (2 red) and the installed-check forced to always say yes
  (1 red).
- a fix to the fix, found by its own test and worth the line: the guard first
  asked `is_multi_ink`, which READS the measurement — so an unreadable `.ti3`
  raised, the broad `except` stood the guard down, and the history was archived
  anyway. The cheap, certain question goes first.
- and the same trap twice in one round: `MainWindow._check_argyll_binaries(
  initial=True)` AUTO-DETECTS a working ArgyllCMS and writes the path back, so
  a bad path set before the window is built is silently corrected. This round's
  first on-screen drive and its first version of this test both measured a
  machine that had ArgyllCMS. Set it after.

---

### B8-222 · The project manifest was the one written without the atomic write
- blocks release: no
- status: FIXED
- found by: combined adversary round 8, 2026-09-16 — round 7's LEAD 2, settled.
- detail: `Project.save_manifest` used a plain `write_text`, while
  `Run.save_meta` and the calibration's own meta have gone through
  `write_json_atomically` all along. `project.json` is the one that decides
  whether a project opens at all: it names `current_run` and every run, and a
  truncated one is not survived the way `meta.json` is — `Run.load_meta`
  treats "unreadable" as "absent" on purpose, and nothing does that here.
- Knut, #130 (2026-08-06), asking for exactly this: *"Write the updated JSON
  data to a temporary file in the same directory, then rename (replace) the
  original file with the temporary one. This prevents file corruption if the
  process crashes mid-write."*
- **GRADED HONESTLY: not a fault anybody has been shown.** A power loss inside
  one `write_text` is not something this round could drive, and it is recorded
  as a consistency fix against a rule already written down rather than as a
  third finding.
- the other half of round 7's lead is recorded as EXAMINED, not as a fault:
  `save_manifest` `mkdir(parents=True)`s a project root that has been deleted
  behind the app's back, so a folder deleted in Finder while ChromIQ holds it
  open comes back holding only a manifest. `write_json_atomically` does the
  same `mkdir`, so this fix does not change it — and refusing to write would
  lose state the app legitimately holds, silently, instead. Measured, judged,
  left alone.
- evidence: test_the_project_manifest_is_written_atomically,
  test_the_manifest_really_survives_a_write_that_fails.
  One mutation proved to land and caught by both (the plain `write_text` put
  back): a write that dies partway left `{"schema_version": 2, "name": "P",
  "cur` on disk as the whole manifest.

---

### B8-223 · Generate Chart died in silence and the button never came back
- blocks release: yes
- status: FIXED
- found by: combined adversary round 9, 2026-09-16.
- what a user does: put the ChromIQ projects folder somewhere ChromIQ cannot
  write — an external disk that is not plugged in, a network share that
  dropped, a folder locked in Finder — and press **Generate Chart**.
- what happened: **nothing at all.** No window. Not one line in the log
  (`"log tail": ""`). Generate Chart then stayed greyed out for the rest of the
  session, with Stop live beside it, and the only way back was to restart
  ChromIQ. Photographed: `A8-what-the-person-is-left-with.png`.
- driven two independent ways into the same state (`A-result.json`,
  `B-result.json`): the projects folder on a drive that is not mounted
  (`/Volumes` is root-owned `drwxr-xr-x`, so an ordinary `mkdir` under it is
  refused with EACCES), and the projects folder read-only, where
  `Project.load` raises rewriting "Where are my files.txt" on every load.
- the shape, which is round 8's lens one door further on: **a door can decline
  by RETURNING and it can stop by RAISING.** Both chart-build doors disable
  Generate Chart and raise `_layout_owned_by_build` BEFORE everything that
  touches the filesystem, and `_on_generate`'s own comment says *"Every path
  out of this build re-enables the button, including the failures"* — true of
  every `return` in it and of no exception at all. Its `try` had a `finally`
  that forgets the §S4.7 gate answer and no handler.
- the quieter half is worse: `_layout_owned_by_build` stayed True, and the
  comment beside every early return says what that costs — *"the next target
  the user selects never receives its own settings, and the next write files
  the previous run's values onto it (§4 S8)"*.
- the sibling door already had this guard, in these words:
  `tab_profile._on_build` wraps its launch in *"THE LOCK MUST COME BACK OFF IF
  THE BUILD NEVER STARTS … leaving the user locked out of their own app with no
  way back but a restart"*. This is that guard, for the tab a user meets first.
- fix: both doors catch. An `OSError` names the folder and says what to do; any
  other exception unlocks and re-raises, so nothing is swallowed. The
  slow-chart watchdog — armed one statement above the hand-over — is stopped on
  the way out, or the "this chart is taking a long time" window arrives for a
  build that never began.
- text: the title is the key the import door already uses
  (`ChromIQ could not write into that project`); the body is new and was
  translated into all twelve catalogues with it. No em dash.
- proved after (`E-result.json`,
  `E1-ChromIQ-could-not-write-into-that-project.png`): the window appears, the
  button comes back, the shield drops, and the excepthook catches nothing.
- evidence: test_each_build_door_handles_an_exception_that_escapes,
  test_each_build_door_puts_the_tab_back_for_anything_else,
  test_the_restore_puts_back_both_the_button_and_the_shield,
  test_the_restore_stops_the_slow_chart_watchdog,
  test_generate_says_so_and_comes_back,
  test_the_window_names_the_reason_and_ends_with_a_lever,
  test_the_live_preview_is_put_back_without_a_window,
  test_the_message_is_one_the_catalogues_carry.
  Three mutations proved to land and all caught: the `_on_generate` handler
  removed (4 red), the shield forgotten in the restore (3 red), the watchdog
  left running (1 red).

---

### B8-224 · The build refusal stood aside for a setting, and archived anyway
- blocks release: yes
- status: FIXED
- found by: combined adversary round 9, 2026-09-16 — attacking round 8's own
  B8-221 fix, which is what the round was asked to do.
- what a user does: tick **ChromIQ profile engine (beta)** in Preferences, have
  the ArgyllCMS folder pointing somewhere wrong, and press **Build** on an
  ordinary run that holds a profile and dated verification measurements.
- what happened (`D-result.json`,
  `D2-ChromIQ-could-not-start-colprof.png`): *Build here anyway* moved the
  run's `.icc` into `runs/run1/old/<date>/` and BOTH dated verifications into
  `verifications/old/<date>/`, and the window then said **"Nothing was changed
  in your project."** That is the exact sentence B8-221 was fixed to make true.
- why: `_refuse_when_the_profiler_is_not_installed` opened with
  `if profile_engine_beta: return False`, on the reasoning that "with the
  profile engine enabled the build may not need Argyll at all". `_resolve_engine`
  says otherwise, deliberately and in its own comment: with the beta ticked a
  standard (≤4-ink) measurement still builds on **colprof** when "Bit-exact
  gamut mapping" is chosen, and whenever `engine_support` declines. The guard
  was answering a question the app already answers elsewhere, and answering it
  wrong.
- the same shape a second time, fixed with it: `engine == "blocked"` refuses a
  multi-ink measurement built without the beta setting *outright* — and did so
  AFTER the archive, so the run's history was moved for a build refused in the
  next statement.
- fix: `_on_build` resolves the builder ONCE, above the archive, and hands the
  answer down. The guard has one question left and it is the cheap certain one:
  can that builder be launched at all? An unreadable `.ti3` raising out of
  `_resolve_engine` is answered "colprof", which is round 8's own reasoning in
  the one place it now lives.
- proved after (`F-result.json`): no `old/` anywhere, the `.icc` still in the
  run, both dated verifications still in `verifications/`, and the window is
  the only thing that happens.
- evidence: test_the_refusal_is_told_which_builder_will_run_rather_than_guessing,
  test_the_builder_is_decided_before_the_question_that_archives,
  test_the_multi_ink_refusal_is_also_above_the_archive,
  test_the_beta_engine_does_not_let_the_archive_happen,
  test_a_measurement_that_cannot_be_read_still_reaches_the_refusal,
  test_the_refusal_stands_down_when_the_engine_is_the_builder.
  Two mutations proved to land and both caught: the beta stand-aside put back
  (3 red) and the refusal removed from `_on_build` (7 red).
- and a test that read prose, caught by this round's own gate:
  `test_rebuild_warning_wiring.py::test_the_question_comes_before_the_build`
  indexed RAW source for the word "colprof", which the new comment says above
  the question. Round 7 wrote that hazard down; it now strips comments and
  looks for the two LAUNCHES instead of a word that is no longer a proxy for
  one.

---

### B8-225 · The atomic write ate a symlink and dropped the file's permissions
- blocks release: no
- status: FIXED
- found by: combined adversary round 9, 2026-09-16 — the brief asked what
  `project.json` actually IS on disk after B8-222 routed it through
  `write_json_atomically`.
- measured, on a real `project.json`: mode **0600 came back 0644**; a Finder
  tag on it was **destroyed**; a manifest made **read-only was silently
  overwritten** and left writable; and pointed at a **symlink** the helper
  deleted the link, left a regular file in its place, and every other reader of
  the real file went on seeing the old contents.
- this is the shape this project was bitten by once already and wrote down
  (the ICC accented-name fix, 2026-09-02): *"`os.replace` swaps the NAME"*. The
  helper never got that fix; B8-222 routed one more file through it.
- **GRADED HONESTLY: not a fault anybody has been shown.** Nothing in ChromIQ
  sets an xattr on a manifest and no user has been shown one missing. It is
  recorded as a property fix against a rule already written down, and the brief
  asked the question.
- two losses remain and are STATED rather than hidden: a hard link cannot
  survive a rename, and extended attributes are not carried on macOS, because
  `shutil.copystat` copies them only where `os.listxattr` exists — which is
  Linux, and is absent on this platform (measured).
- evidence: test_the_write_goes_through_a_symlink_rather_than_replacing_it,
  test_the_file_keeps_the_permissions_it_had,
  test_a_volume_that_refuses_the_properties_still_gets_the_write,
  test_the_project_manifest_gets_all_of_this_too.
  Two mutations proved to land and both caught: the symlink resolution removed
  (1 red) and `copystat` removed (2 red).
- and a fix to the fix, caught by this round's own gate: resolving with a bare
  `Path(...)` picks its flavour from `os.name`, which
  `test_run_delete.py` legitimately sets to `"nt"` on this host — so it built a
  `WindowsPath` and raised. It resolves only when there IS a symlink, and
  through `type(path)`.

---

### B8-226 · The trend told you to do what you had already done
- blocks release: no
- status: FIXED
- found by: combined adversary round 9, 2026-09-16 — the round's ONE HONEST
  PASS over the merged feature set, which is the item that was there in case
  nine rounds of narrow attacks had left something obvious unlooked-at.
- what a user sees (`J1-the-measurement-report.png`): two dated measurements
  listed, **both ticked**, "Show all measurement runs" already on, the Report
  Scope saying "No. of Measurements: 2" — and written across the Colour
  accuracy graph: *"A trend graph needs at least two measurement runs. Add
  another measurement — or, if the profile you have loaded already holds more
  than one run, tick 'Show all measurement runs' above."* Both instructions
  were already carried out. The sentence was false and its advice was inert.
- why: `_de00_block` writes every accuracy number TWICE, in today's
  five-metric spelling and in the old `mean`/`max`/`p95` one, and says why:
  *"aliases kept for the trend series (report_trend reads mean/max/p95)"*.
  `report_trend` does copy them into the point, with its own comment about
  *"the mean/max aliases older points used"*. **Nothing read them.** So a
  report written before the five-metric vocabulary (ChromIQ before 2026-07-20)
  carried no value for any of the five lines, `_TrendChart.set_data` dropped
  the whole point through `has_any`, and the chart fell into its empty state.
  That is dead code wearing a comment that claims a purpose, which is the same
  shape rounds 6 and 8 each found once.
- fix: the two metrics that are the SAME arithmetic are read in either
  spelling, and that is proved from `_de00_block`, where the new key and the
  alias are written from one expression. `max_low95` is deliberately NOT mapped
  from the old `p95`: today's is the nearest-rank maximum of the best 95 % and
  stamps `p95_rule` to say so, and a report old enough to lack the new key
  recorded no rule at all. A line that cannot be trusted is left with no point
  rather than given a wrong one. No new message text.
- proved after (`K1-the-measurement-report.png`): the graph draws, two lines
  across 2026-05-02 to 2026-08-11, and the empty-state sentence is gone.
- how common: on this machine all six alias-only reports are in the DEMO
  projects — which is where it was found, and which is what the demo package is
  driven through before every beta. A user upgrading from a ChromIQ older than
  2026-07-20 has the same reports on disk.
- evidence: test_the_alias_and_the_new_key_are_the_same_expression,
  test_only_the_two_safe_metrics_are_mapped,
  test_an_old_point_answers_for_what_it_carries,
  test_a_new_point_is_unchanged,
  test_the_chart_keeps_the_old_point_and_draws_a_trend,
  test_the_dialog_itself_uses_the_alias_reader.
  Two mutations proved to land and both caught: the alias map emptied (4 red)
  and the chart pointed back at the raw key (1 red).

---

### B8-227 · The atomic write left a scratch file nobody could delete
- blocks release: no
- status: FIXED
- found by: combined adversary round 10, 2026-09-16 — the round asked to
  CONFIRM round 9's three fixes before a tag, and this is a fault in one of
  them. It is the second round running to find one in the round before it.
- what a user sees: lock `project.json` in the Finder's Get Info panel (which
  sets `UF_IMMUTABLE`, and is a thing a person may reasonably do to a file they
  do not want changed), then use ChromIQ. Any manifest write fails — it always
  did, and the manifest is correctly left alone — but from combined round 9
  onwards it leaves a **`project.json.tmp` in the project folder that cannot be
  deleted**: not by the Finder, not by `unlink`, not by `rm -f`. The only way
  out is `chflags nouchg` or unticking Locked.
- why: round 9 added `shutil.copystat(path, tmp)` so a manifest's MODE survived
  the rename (B8-225), and on macOS `copystat` carries `st_flags` too. The
  scratch file therefore became immutable as well, so when `os.replace` failed
  on the locked target, the cleanup below it — under a comment reading *"Never
  leave the scratch file behind to be mistaken for real data"* — could no
  longer delete the file it had just made. `tmp.unlink()` raised
  `PermissionError`, the bare `except OSError: pass` swallowed it, and the file
  stayed.
- measured A/B, on the helper as it stood at `a60a5cde` and on this tree
  (`E2-locked-manifest.json`): **before** — raises, manifest untouched, no
  scratch file; **after** — raises, manifest untouched, `project.json.tmp`
  left, `st_flags 0o2`, a plain delete refused and `rm -f` refused.
- fix: the immutable and append-only bits are taken off the SCRATCH file (never
  off the user's own), once before the rename and again on the way into the
  cleanup. On a locked target they can only make the write fail in a worse way;
  on an unlocked one there is nothing to drop. A flag that does not block a
  rename still crosses, so what `copystat` is there for is untouched. No new
  message text.
- proved after: the same A/B, both sides now leaving nothing behind, and the
  other seven manifest shapes re-measured unchanged (`E-manifest-shapes.json`):
  fresh, mode 0600 kept, read-only 0444 kept, a live symlink written THROUGH,
  a dangling symlink, a Finder tag (the stated loss), and a separate exFAT
  volume. Driven on screen as well (`F-result.json`): a real chart build into a
  project whose manifest is a symlink at 0600 left it a symlink at 0600 with
  the new `current_run` in the real file, and the same build into a project
  whose manifest was Locked was refused by B8-223's own window, *"ChromIQ could
  not write into that project… The reason: Operation not permitted"*, with no
  scratch file and no uncaught exception.
- how common: rare — it needs a manifest the user has locked. It is recorded
  and fixed because the helper's own comment promises it cannot happen, and
  because a file a person cannot delete is a worse thing to leave behind than
  the failed write itself.
- NOT fixed, and stated rather than hidden: a manifest at mode 0444 is still
  silently overwritten (the mode is kept; the protection is not honoured), a
  hard link still cannot survive a rename, and extended attributes are still
  not carried on macOS. The first two are unchanged from before round 9; the
  third is round 9's own stated loss.
- evidence: test_a_locked_manifest_leaves_no_scratch_file,
  test_a_scratch_file_left_behind_would_be_undeletable,
  test_the_locked_manifest_itself_is_never_overwritten,
  test_the_mode_is_still_carried_across,
  test_a_symlinked_manifest_is_still_written_through,
  test_an_ordinary_write_keeps_the_flags_it_was_given.
  Two mutations proved to land and both caught: the unlock switched off (1
  red), and the unlock widened to clear every flag (1 red).

---

### B8-228 · Two import doors filed a measurement on the wrong colour scale in silence
- blocks release: no
- status: FIXED
- found by: combined adversary round 10, 2026-09-16, from a question the owner
  asked directly: do the i1Profiler import fixes made for a tester on the Build
  ICC profile tab also hold for the import door on the Measurement tab?
- graded INHERITED, NOT INTRODUCED. The verification import door has behaved
  this way since the reading was written on 2026-09-11; the profiling door was
  built the same week, the same way, and inherited the gap. Nothing about it is
  new in this batch.
- what a user sees: a `.ti3` that an older ChromIQ converted from an i1Profiler
  export carries XYZ on the 0-to-1 scale ArgyllCMS never uses, so its paper
  white reads about L* 8 instead of L* 95. Import it on the **Measurement**
  tab, either run type, and it is filed, the window says *"The measurement was
  imported"*, and on a profiling run **a dated measurement report is saved from
  it** — with nothing anywhere about the scale. The same file on the **Build
  ICC profile** tab is marked *"colour values on the wrong scale"* and
  explained on the button.
- driven on screen (`H-result.json`, `H1`–`H6`) with a real 240-patch
  measurement whose XYZ columns were divided by 100 — the exact shape the fault
  produces, so names, counts and device values all still match the run's own
  chart, and the verification twin built the same way from a real 64-patch
  verification measurement. Door 1 said it; doors 2 and 3 said nothing; the
  filed copy was still unscaled; `report_2026-09-16_02-55-55.json` was written
  from it.
- why: `repair_converted_cie` guards every path that CONVERTS an export, and a
  `.ti3` passes through `convert_i1profiler_measurement` untouched, so only a
  READING can catch one that was converted before the repair existed. That
  reading, `reference_convert.cie_columns_are_unscaled`, was referenced in
  exactly ONE place in the whole app: `tab_profile.set_ti3_path`.
- the honest half: the Build ICC profile tab DOES flag it afterwards, because
  the profiling import emits `measure_finished` and that reaches
  `set_ti3_path`. So a person who goes to that tab is told — after the file is
  filed and after the dated report has been written from it. The verification
  door has no such second chance.
- fix: ONE shared check, `measurement_filing.the_colour_scale_note`, holding
  the reading and the sentence; all three doors call it.
  `tab_profile.set_ti3_path` keeps exactly what it showed; the import panel's
  own label carries the same mark after the file name and the import info box
  carries the sentence, for both run types, filled by the one method that
  serves both; and `_convert_import_file` — the one call both import doors make
  — writes the sentence into the tab's log as a `[WARNING]`, because the log is
  what stays behind after the window is closed.
- NO NEW MESSAGE TEXT, deliberately. The sentence and the mark are the two
  strings the Build ICC profile tab has shown since 2026-09-11, already in all
  twelve catalogues; they were MOVED into the shared function and referenced,
  never copied. New text in this area goes to §M-PROPOSED first, and none was
  needed.
- said, not mended and not forbidden — `tab_profile`'s own rule for the same
  fact. Rewriting a measurement the user did not ask us to touch is a write,
  and refusing a file ArgyllCMS will read is not our decision.
- proved after (`H2.log`, `I-result.json`, `I` photographs): all three doors
  say it; both import panels carry the mark on the label and the sentence in
  the info box; an ordinary measurement is marked on neither door, so there is
  no false positive.
- evidence: test_the_note_fires_on_a_measurement_on_the_wrong_scale,
  test_the_note_is_silent_on_an_ordinary_measurement,
  test_the_note_is_silent_on_nothing_at_all,
  test_the_tag_is_the_mark_that_goes_after_the_name,
  test_the_door_asks_about_the_colour_scale (parametrised over all three
  doors), test_all_four_doors_are_still_listed,
  test_the_sentence_lives_in_exactly_one_module,
  test_the_sentence_is_not_new_text.
  Two mutations proved to land and both caught: one door's call removed (1
  red), and the shared reading made to accuse nothing (1 red).

---

### B8-229 · The scratch-file unlock reached through a link to the user's own manifest
- blocks release: no
- status: FIXED
- found by: combined adversary round 11, 2026-09-16 — the round asked to
  CONFIRM B8-227 and B8-228 before a tag, and this is a fault inside B8-227's
  own fix. Third round running to find one in the round before it.
- what a user sees: nothing, unless a `project.json.tmp` in a project folder is
  a symlink to `project.json` — which nothing in ChromIQ creates. Then a
  manifest the user has **Locked in the Finder** comes out of a failed write
  **unlocked**, and the lock they set is gone with no word said.
- why: B8-227 added `_unlock_scratch_file`, whose docstring promises *"Only
  ever the SCRATCH file: the user's own file is never touched."* It used
  `tmp.stat()` and `os.chflags`, and both FOLLOW a symlink, so with the scratch
  NAME standing as a link the unlock landed on the link's TARGET, which is the
  user's own file.
- measured on screen in a live session, combined round 11 (`A-result.json`,
  shape 20, one of 24 shapes driven): a `project.json` with `st_flags 0o2` came
  out of the failed write with `st_flags 0o0`, its content correctly untouched.
- fix: `os.lstat` and `os.lchflags` — ask about the NAME in hand. A scratch
  name that is a link carries no lock bits of its own, so nothing is touched at
  all, which is right: a link is not a file this helper created. One line each,
  no behaviour change on the shape B8-227 exists for.
- proved after: the same 24 shapes re-driven with the fix (`A-result.json`) —
  shape 20 now keeps `st_flags 0o2`, and every other shape is unchanged: 12
  writable shapes carry mode and non-blocking flags across and change the
  content, 8 locked or append-only shapes refuse and leave the manifest exactly
  as it was, and no shape leaves a scratch file the helper created. Driven
  through a REAL ACTION as well (`H-result.json`, `H-*.png`): laying a chart
  into run 2 of a project whose scratch name was a link to a Locked manifest
  was refused by B8-223's own window and left the Lock on.
- and the attempt the fix exists for: an undeletable scratch file could not be
  made by any route reachable from the app. Tried, all on screen: a locked
  manifest, a locked project FOLDER, both at once, a stale locked
  `project.json.tmp`, a read-only folder with a locked scratch file in it, a
  scratch name that is a directory, a scratch name that is a link, two separate
  volumes (HFS+ and FAT32) with and without the lock. The system-immutable bits
  cannot reach a scratch file at all: this user cannot set `SF_IMMUTABLE`
  (`A3-system-immutable.json`), so `copystat` can never copy one.
- NOT fixed, and stated rather than hidden: in a READ-ONLY folder that already
  holds a `project.json.tmp`, that file is written into and then cannot be
  removed, because the process may not delete anything in that folder. It is
  removable the moment the folder is writable, it is not the undeletable file
  B8-227 exists for, and no code inside the helper can fix it.
- evidence: test_the_unlock_never_reaches_through_the_scratch_name,
  test_the_scratch_file_is_still_unlocked_when_it_is_a_real_file.
  One mutation proved to land and caught: `tmp.stat()` and the following
  `chflags` put back (1 red, 7 green; restored, 8 green) — `mutations.txt`.

---

### B8-230 · A fourth door saved a dated report from a measurement on the wrong colour scale
- blocks release: no
- status: FIXED
- found by: combined adversary round 11, 2026-09-16, hunting for the fourth way
  in that B8-228's own brief asked about.
- graded INHERITED, NOT INTRODUCED, exactly like B8-228: Tools ▸ *"Measurement
  report"* has taken any `.ti3` since long before this batch.
- what a user sees: a `.ti3` whose XYZ is on the 0-to-1 scale opens in the
  Measurement Report window — either because the loaded project's run holds one
  (the window seeds itself from it) or through **Add Profile's Measurements…**,
  which the Tools ▸ *"Convert i1Profiler → TI3"* help text points people at by
  name. Every figure in the document is computed from it, and **Generate
  report** files a dated report whose own `paper_white` reads `L* 8.89`. The
  window said nothing.
- driven on screen before the fix (`D-result.json`, `D1`–`D3`): every word the
  live window showed was collected — buttons, help text, notices, list rows —
  and not one of them mentions the scale; `report_2026-09-16_03-44-13.json` was
  filed with `paper_white.lab [8.89, -3.28, 15.18]`.
- why: `_as_ti3` hands a `.ti3` straight through — no conversion, so
  `repair_converted_cie` never runs on it — and B8-228's shared reading was
  wired to three doors, not this one. This is the door where the harm B8-228
  named actually happens: it is the thing that writes the dated document.
- fix: the same shared check, asked once where a measurement joins the window
  (`_append_source`), with the answer kept on the source. The list row carries
  the same mark after the same name the other three doors put it after, and the
  sentence goes on its own hidden row under the buttons, the way the
  settings-changed notice already does.
- NO NEW MESSAGE TEXT. The two strings are B8-228's, already in all twelve
  catalogues, referenced and not copied — the test that refuses a second copy
  still passes.
- said, not mended and not forbidden: nothing is refused, nothing is rewritten,
  the report is still generated. The window simply stops being silent.
- proved after (`E-result.json`, `E1`–`E3`, `G1-the-report-window-with-the-
  sentence.png`): the row reads *"Demo-Switching · 2 runs · colour values on
  the wrong scale"* and the sentence is on screen in the window's warning
  colour, measured at 1406×32 px. The control matters as much (`F-result.json`,
  the same drive on the SAME project with the measurement left exactly as
  measured): the window says nothing, the row is clean, and the report is filed
  as before.
- evidence: test_the_report_window_says_it_on_a_measurement_on_the_wrong_scale,
  test_the_report_window_is_silent_on_an_ordinary_measurement,
  test_the_door_asks_about_the_colour_scale (now parametrised over four doors),
  test_all_four_doors_are_still_listed,
  test_the_sentence_lives_in_exactly_one_module.
  Three mutations proved to land and all caught: the refresh call removed (1
  red), the row's mark removed (1 red), and the reading made to answer nothing
  (1 red) — `mutations.txt`.

---

### B8-231 · A chart built on top of another was judged on the one it replaced
- blocks release: no
- status: FIXED
- found by: two testers driving beta 18 on screen, independently and from
  opposite directions, 2026-09-16.
- what a user sees, route one: a two-page chart built with Right = 6 mm warns
  *"the right margin leaves 1.7 mm … Raising “Right” … by about 2.8 mm"*. Set
  Right = 40 and press Generate Chart, and the frame reads **40.2 mm**, the
  engine 40.159 and the app's own raster 40.13 — while the red paragraph beside
  it repeats *"leaves 1.7 mm"* word for word. The reader did exactly what the
  message asked and got the identical message back.
  (`~/Desktop/ChromIQ-beta18-proof/knut-sweep-preview-truth/R12-B-right-40mm.png`)
- what a user sees, route two: two preset picks in one session. On page 1 of 3
  the frame reads `Right 23.9` and under it *"the right margin leaves 0.0 mm …
  Raising “Right” … by about 16.9 mm"* plus *"the right margin leaves 6.1 mm"*.
  Three numbers for one edge on screen at once, all three about a chart that no
  longer exists.
- and the same fault from the clip border's side: the frame read 34.994 while
  the judgement used 10.017, which is a tester's *"very different values that
  do not make sense"*; **raising the margin to 51 mm did not change one digit,
  and pressing Generate again did not clear it** — only a page-count change, a
  new project or a restart did.
- why: `TabChart._worst_page_key` was *(the page TIFF paths, the .ti2 path)*.
  A rebuild into the same run writes `<name>_01.tif … _NN.tif` again, so the
  key never moved and `_ensure_worst_page_cache` returned early. **The
  function's own docstring claimed the opposite** — *"A new chart is a new key,
  so the pages of the previous one can never judge this one's text"* — which is
  the third guard this week found asserting what it does not do.
- fix: the key is each file's SIZE plus `st_mtime_ns`, the `.channels.json`
  sidecar included. **Not mtime alone**: `shutil.copy2` preserves it, and this
  project lost a day to exactly that shape on another cache the week before.
- proved on screen, in the tester's own three-page sequence (`b19_f1m.json`,
  `P1`/`P2`/`P3`): band left with Right 10 (frame 10.017, silent), then band
  right with Right 35 in the SAME run (frame **34.994**, and the two false red
  notices are gone), then Generate pressed again with nothing changed (frame
  34.994, still silent). And on the plainest route (`b19_f1.json`): Right 6
  warns *"leaves 1.7 mm"*, Right 40 and Generate leaves the frame at 40.159
  with no notice at all (`window/F1-A-right-6.png`, `window/F1-B-right-40.png`).
- evidence: test_the_key_moves_when_the_same_filenames_are_rewritten,
  test_the_key_moves_even_when_the_mtime_is_preserved,
  test_the_sidecar_is_in_the_key_too,
  test_a_chart_that_did_not_change_keeps_its_measurement,
  test_the_docstring_describes_what_the_function_does.
  Mutation proved to land (the key back to the file names): 3 red.

### B8-232 · Four routes recomputed the notices from the live boxes against the old sheet
- blocks release: no
- status: FIXED
- found by: a tester driving beta 18 on screen, 2026-09-16.
- what a user sees: build a chart with the bottom line at 36 pt, type 6 pt into
  the Size box (correct: the red *"press Generate Chart"* line arms and the
  notice does not move), then tick a guide box **on the frame itself**. The
  notice is recomputed at 6 pt against the 36 pt sheet. Type 36 pt back and the
  red line correctly goes while the false notice stays. In that last state the
  boxes match the chart, the chart matches the disk, nothing on screen says
  anything is pending, and the red notice describes a sheet that was never
  generated. The TIFF's SHA-256 is identical at every step.
  (`~/Desktop/ChromIQ-beta18-proof/knut-sweep-preview-truth/R11-3-HEADLINE-size-36pt-no-red-line-notice-says-6pt.png`)
- the four routes: `_preview.page_changed`, `_on_margin_guides_toggled`,
  `_on_margin_measured_guides_toggled` and `refresh_margin_inspector_settings`
  (the Preferences round trip). `_refresh_manual_command_preview` was already
  excluded by the 2026-09-15 ruling; these four were not brought under it.
- why: `_engine_text_notes` re-read `_current_layout_recipe()` — the widgets —
  while `_update_margin_inspector` re-measured the OLD TIFFs.
- fix: `_notice_layout_recipe` takes the recipe from the chart's own
  `channels.json`, which every build writes and which `_restore_chart_settings`
  already trusts for exactly this reason. A printtarg chart, or no chart at
  all, still judges the live panel, so nothing goes silent.
- proved on screen (`b19_f2.json`, `window/F2-0…F2-3`): the four steps produce
  the IDENTICAL message field, and it is the 36 pt one throughout.
- evidence: test_the_notice_recipe_comes_from_the_chart_and_not_from_the_boxes,
  test_typing_a_box_and_typing_it_back_changes_nothing,
  test_the_recipe_is_re_read_when_the_chart_is_rebuilt,
  test_a_chart_with_no_sidecar_still_judges_the_boxes,
  test_the_notices_themselves_follow_the_built_recipe.
  Mutation proved to land (the live recipe back): 1 red.

### B8-233 · A tenth of a millimetre warned, and the residue is a pixel
- blocks release: no
- status: FIXED
- found by: a tester, testing beta 18 on the SHIPPED presets, untouched.
- what a user sees: load `i1Pro 3 Plus · A4-462p-3pages` or any A4 ColorMunki
  preset and the panel says *"The band is 24.0 mm wide and the left margin
  leaves 23.9 mm"*. Nothing is on the paper: twin sheets subtracted pixel by
  pixel put **3.3 mm of white paper** between the band's content and the first
  patch. He asked for a 0.2 mm threshold on all four sides.
- why, measured rather than guessed: the clip zone is an exact 28.000 mm and
  the MEASURED margin lands on a whole pixel. The same chart at five
  resolutions — 72: residue 0.131, 150 and 200: 0.060, 300: −0.025, 600: 0.018
  — against an `EPS_MM` of 0.05.
- **a flat 0.2 mm is not enough.** The dpi box accepts 72 to 1200 and the worst
  case at 72 is a whole pixel, 0.353 mm. The rule is `max(0.2 mm, one pixel at
  this chart's dpi)`.
- and it masks nothing that reaches paper: twin sheets again, the claimed
  shortfall exceeds the real ink overlap by a constant ~1.3 mm reserve, so at a
  claimed 0.2 mm there is **1.10 mm of clear paper and zero text pixels on the
  patches**.
- proved on screen (`b19_k2b.json`, `window/K2b-left-28.png`): the tester's own
  state at 200 dpi, band 28 mm on the left, frame reading **27.94** against a
  typed 28.0 — and the panel is silent. A real collision still warns
  (`b19_f1.json` F1-A, and `b19_bot2.json` B4 at 2.4 mm short).
- evidence: test_the_tolerance_is_the_larger_of_two_tenths_and_one_pixel,
  test_the_tenth_of_a_millimetre_on_the_shipped_preset_is_silent,
  test_a_collision_that_reaches_paper_still_warns,
  test_the_floor_reaches_all_four_of_the_patch_area_checks,
  test_the_default_is_still_float_noise_and_not_the_threshold.
  Mutation proved to land (the tolerance back to a constant): 1 red.

### B8-234 · The bottom block was budgeted by its box, and the box is not its ink
- blocks release: no
- status: FIXED
- found by: a tester driving 220 rendered sheets, 2026-09-16.
- **this is the SECOND cause of false warnings and B8-233's threshold does not
  touch it**, which is why both had to go in one pass: otherwise the threshold
  is blamed for the other's failures.
- what a user sees, measured off the sheet: bottom-left alignment, "B" 18,
  10 pt — the panel says *"0.2 mm short"* where the text's ink ends at 21.505
  and the patch block starts at 22.098, **0.593 mm of clear paper**. Top-left,
  "B" 4, 28 pt — *"1.3 mm short"* on **0.762 mm of clear paper**. A true
  collision at 28 pt was over-stated by 2.2 mm.
- why: `render_pages` draws each line with PIL's "la" anchor, so the ASCENDER
  lands on the top of the line box and the ink begins below it. The panel
  budgeted the box. The over-read is about 0.9 mm at 10 pt, rising to 2.2 mm at
  28.
- fix: `raster.sheet_text_ink_top_mm` measures the trim off the string that is
  really drawn, and `bottom_text_block_overlap` takes it off the need.
- proved on screen (`b19_bot.json`): B1, the 10 pt state, now silent with
  **4.064 mm** of clear paper on the sheet; B3, the 28 pt state, silent with
  **0.762 mm**; and B4 (`b19_bot2.json`), a collision that really reaches the
  patches, still reported at 2.4 mm short.
- evidence: test_the_trim_is_measured_off_the_string_that_is_drawn,
  test_the_false_warning_on_clear_paper_is_gone,
  test_a_real_collision_is_still_reported_and_is_not_over_stated,
  test_the_trim_can_never_make_the_need_negative.
  Mutation proved to land (the trim returning 0.0): 3 red.

### B8-235 · Six remedies named a control that does not move what the sentence says
- blocks release: no
- status: FIXED
- four of the six. The other two are reported, not implemented, in B8-239
  and B8-240: they are the design authority's to decide.
- found by: two testers, driving beta 18 and applying each named lever one at a
  time with the chart regenerated between them.
- this is the fault class the project's design authority has ruled against more
  than once: a remedy that changes nothing teaches the reader to stop reading.
- measured, one row per lever:
  - *"set a narrower Clip border width"* — **inert in the very branch that
    prints it.** The band displaces the patches, so the measured margin follows
    the band down; narrowing frees nothing until the band drops below the TYPED
    margin, and the box stops at 10 mm. Two of the three states that printed
    the message were in that branch.
  - *"put the clip border on the LEFT"* — removed the named message and
    immediately printed a different red one, *"the right margin leaves
    1.7 mm"*, with the note's ink still inside the patch rows.
  - *"set a smaller Size under Sheet text"* — 8, 7, 6 and 5 pt all produced the
    identical *"needs 4.2 mm of room … 0.5 mm short"*, because
    `raster.sheet_text_line_mm` floors at the 4.2 mm pitch. The message went on
    naming the lever at 5 pt.
  - *"Lowering “B” … buys the same room"* — **false in "Prioritise patch
    size"**, where the patch block follows "B" down the page: a 10 mm drop
    moved the text 10 mm, the block 10.2 mm and the overlap by 0.22 mm.
- fix: `_clip_width_lever_note` and `_size_lever_note` offer their clause where
  it works and say plainly why it will not help where it does not;
  `_bottom_lever_note` gains the patch-first case; the side swap is gone from
  both messages that carried it.
- evidence: test_the_width_lever_is_offered_where_the_typed_margin_survives_it,
  test_the_width_lever_is_withheld_where_it_cannot_work,
  test_no_message_in_the_panel_offers_the_other_side_of_the_sheet,
  test_the_size_lever_is_offered_while_the_type_is_above_the_floor,
  test_the_size_lever_is_withheld_below_the_prediction_floor,
  test_the_floor_really_is_where_the_prediction_stops,
  test_lowering_b_is_promised_only_where_the_block_stays_put,
  test_lowering_b_is_not_promised_in_patch_first,
  test_the_markers_branch_still_wins_over_both.
  Mutation proved to land (all three gates forced open): 4 red.

### B8-236 · In "Prioritise patch size" the top-edge notice could not fire at all
- blocks release: no
- status: FIXED
- found by: a tester, 24 states across four geometries, 2026-09-16.
- what a user sees: A B C D E printed in the middle of the second row of
  hexagons on a CR30 honeycomb, under a panel reading **"Margins: OK"** in
  green. Not one notice in 24 states, with the letters driven onto the patches
  by every lever that works. The same levers in "Prioritise chart area"
  produced a notice in 14 of 24.
  (`~/Desktop/ChromIQ-beta18-proof/knut-sweep-geometry/phase5/crops/ZOOM-CR30hexP-pf-off20.png`)
- why, two causes stacked: the whole check sat inside
  `_labels_can_overflow = r.layout_mode == "area_first"`, AND the arithmetic
  worked the letters' reserve out of "T" — which in that layout the renderer
  does not consult at all. `geometry.placement` anchors the band on the TOP
  MARGIN there, so lifting the gate alone would have produced a notice built on
  a number that describes nothing on the sheet.
- and a third, on both layouts: the reach was the em BOX while PIL anchors the
  letters by their ASCENDER. The ink begins about 1.33 mm below the anchor and
  ends below the box, so the warning arrived a millimetre late — at "T" 8 there
  was 0.93 mm of letter ink on the first row of patches and the panel said
  nothing, and at "T" 12 the message's own remedy left **1.1 mm of every letter
  still on the patches** while going silent.
- fix: `geometry.strip_label_leader_top_mm` mirrors the two lines of
  `placement` that set `leader_top`, and a test keeps the mirror honest;
  `raster._furniture_reserves_mm` measures the letters' real ink box off a
  probe into two new geom fields, and the LAYOUT reserve is deliberately
  untouched so no sheet moves; the message names the control that binds, with a
  third wording for the layout in which "T" moves nothing.
- proved on screen (`b19_top.json`, `window/T1-offset-8/14/20.png`): silent at
  Label offset 0, and at 8, 14 and 20 mm the panel says *"With “Prioritise
  patch size” they are held 12.0 mm from the paper edge by the top margin
  itself … 6.9 / 12.9 / 18.9 mm of every letter is on the first row of
  patches … “T” … does not move them in this layout."*
- evidence: test_the_helper_is_the_same_answer_as_placement,
  test_in_patch_first_the_anchor_is_the_top_margin_and_not_t,
  test_patch_first_can_report_a_top_overlap_at_all,
  test_the_message_does_not_offer_t_where_t_moves_nothing,
  test_the_two_older_bindings_are_untouched,
  test_the_geometry_carries_the_ink_box_and_it_is_not_the_em_box,
  test_the_reach_is_used_and_the_box_is_not,
  test_the_ink_offset_is_what_the_sheet_really_draws.
  Two mutations proved to land: the layout-mode branch dropped from the helper
  (3 red), the ink reach back to the em box (1 red).

### B8-237 · The Notes box showed a locked 12 pt, and the presets are where it came from
- blocks release: no
- status: FIXED
- found by: a tester, beta 18: *"the Size input box locked with 12 pt inside
  the input box. Is it locked because it has its own shrinking feature? If so,
  should it not show auto? if this comes from the json files of the presets and
  this is wrong, then correct this on all the preset files."*
- why: `_P3_BASE` carried `clip_text_size_mm: 4.23`, which is 12.0 pt, on all
  24 i1Pro 3 charts, and two more preset bases carried 3.53 mm beside "Notes
  box". The Size box is correctly disabled for that content mode, and a greyed
  number is a promise the sheet does not keep.
- fix: both halves. Every preset that pairs "Notes box" with a size now says
  auto, and `_sync_clip_content_enabled` shows the box's own `auto` special
  value whenever the content sizes itself, stashing the typed size so switching
  back to free text gives it straight back.
- proved on screen (`b19_k2.json`): loading the shipped
  `★ i1Pro 3 Plus · A4-462p-3pages` preset leaves the box reading `auto`,
  disabled, value 0.0.
- evidence: test_no_preset_pairs_a_notes_box_with_a_typed_size,
  test_the_shipped_i1pro3_family_really_carries_auto,
  test_the_size_box_reads_auto_whenever_its_content_sizes_itself.
  Mutation proved to land (4.23 back on `_P3_BASE`): 2 red.

### B8-238 · The sheet text was aligned on the margin box, and "Size auto" was 9 pt for ever
- blocks release: no
- status: FIXED
- found by: a tester, beta 18, in two separate paragraphs of one report.
- **the alignment.** *"when Alignment is left, any of the two bottom texts
  placed are aligned against the left margin setting, and not the left margin
  under Measured from Preview. This also applies for … "Centre between left and
  right margin" and "Centre of available space"."* The patch block is centred
  in the slack, moved by "Patch area alignment", and pushed in by a honeycomb's
  apex reserve and the row-label band, so it does not begin at `margin_l`.
  Fixed in `render_pages` (all three alignments) and predicted the same way by
  the panel's width check.
- proved on screen (`b19_bot2.json` B5): a CR30 honeycomb with the block pushed
  right, margin box **12.0**, `geom.margin_l` raised to **14.4**, the frame's
  measured left margin **23.961** — and the bottom line's ink measured off the
  TIFF starts at **24.215 mm**, one glyph bearing from the block it sits under.
- **and the ceiling.** *"When Size=auto for the sheet text, the bottom text is
  still not automatically sized … Set a reasonable upper limit … (such as 15 or
  16pt?) … This should apply to all the Size=Auto settings, except the Strip
  and Row labels."* The loop started at `SHEET_TEXT_DEFAULT_MM` (9.07 pt) and
  only ever decremented, so it could not grow however much paper was free.
  `AUTO_SIZE_CEILING_PT` is 16.0 and the search now steps in POINTS, which is
  the same answer at every resolution.
- the reserve had to follow it, and the first cut did not: the block was
  positioned for a 4.2 mm line and drawn at 16 pt, so the ink crossed the "B"
  reserve on its way to the paper edge. Caught by
  `test_the_bottom_sheet_text_keeps_its_reserve.py` and
  `test_the_top_and_bottom_edges_keep_off_the_helper_markers.py` on the first
  full run after the ceiling went in. A TYPED size still reserves the pitch and
  is still never shrunk, so no chart with one moves.
- proved on screen (`b19_bot.json` B1 against B2, same recipe): at a typed
  10 pt the line's ink ends 21.505 mm up the sheet; at Size auto it ends
  23.622 mm, so "auto" is visibly larger than the old default and still leaves
  1.947 mm of clear paper under the patches.
- evidence: test_the_block_bounds_are_the_block_and_not_the_margin_boxes,
  test_the_alignment_follows_the_block_across_the_nine_positions,
  test_the_renderer_asks_for_the_block_and_not_for_the_margins,
  test_the_ceiling_is_where_the_tester_asked_for_it,
  test_a_short_line_with_room_reaches_the_ceiling,
  test_a_long_line_still_shrinks_and_stops_at_the_floor,
  test_the_engine_reserves_the_band_the_resolved_size_needs,
  test_a_typed_size_still_reserves_the_pitch_and_is_never_shrunk,
  test_the_resolved_auto_size_is_the_same_at_every_resolution,
  test_a_line_that_fits_takes_the_room_it_has.
  Two mutations proved to land: the bounds filled from the margin boxes while
  keeping their names (1 red, and the guard was strengthened after it slipped
  the first version), the search started at the old default (3 red).

### B8-239 · ANSWERED · Is "T" meant to do nothing to the strip labels in "Prioritise patch size"?
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-270
- he ruled **No** on 2026-09-16: the geometry stays, and the help text
  now says so. What was implemented is B8-270. The measurement below is
  what the question was asked from and is kept as it was.
- reported, not implemented. The geometry was NOT changed.
- the measurement, on screen, i1Pro / A4 / "Prioritise patch size" / margins 12
  all round / Label offset 0, with **"T" under "Text distance from edge (mm)"
  swept 0, 2, 4, 8, 16 and 25 mm**, six builds, six sheets:

  | "T" (mm) | where the strip letters print, from the paper's top edge |
  |---|---|
  | 0 | 13.377 … 17.780 |
  | 2 | 13.377 … 17.780 |
  | 4 | 13.377 … 17.780 |
  | 8 | 13.377 … 17.780 |
  | 16 | 13.377 … 17.780 |
  | 25 | 13.377 … 17.780 |

  Identical to the thousandth. In the same window, "Prioritise chart area"
  moves them one millimetre per millimetre: "T" 4 puts them at 5.334, "T" 9 at
  10.329, "T" 12 at 13.334. What DOES move them in patch-first is the **top
  margin** (letters at top + 1.33 mm, exactly, at every value) and **Label
  offset** (−6 → 7.366, 0 → 13.377, +6 → 19.389, +12 → on the patches).
- what beta 19 did, and what it deliberately did not: the panel now describes
  where the letters really are and names the controls that move them (B8-236).
  The LAYOUT is untouched, because which of the two is right is not ours to
  decide.
- the question, as a tester can answer it: **"On a chart set to ‘Prioritise
  patch size’, should the ‘T’ box under ‘Text distance from edge’ move the
  strip letters up and down the page, the way it does on ‘Prioritise chart
  area’? Or is it correct that only the top margin and ‘Label offset’ move them
  there, in which case ‘T’’s help text should say so?"**

### B8-240 · ANSWERED · What should the bottom notice name, now that the rise search is retired?
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-271
- he answered on 2026-09-16, accepting option 3 *"as long as a search is
  done after a generate chart and margins have been measured"*. What was
  implemented is B8-271, and B8-269 then narrowed it so no value is named
  in "Prioritise patch size".
- reported, not implemented.
- the ruling this sits under: the search that answered *"how much more margin
  clears it"* was removed at the design authority's instruction, because it
  rebuilt a dozen geometries per keystroke and because the answer is a
  measurement of a sheet nobody has drawn. What the message names now is the
  OVERLAP, and the overlap undershoots by design.
- measured on screen: the notice said **8.3 mm short**. Raising "Bottom" by
  exactly 8.3 mm (6.0 → 14.3) left it red and now saying 0.5 mm short, because
  the patch grid re-fits and the measured bottom margin rose only 7.79 mm. It
  takes **15.0** to clear it, a raise of 9.0. And the walk is not monotonic,
  which a reader stepping the box will meet:

  | "Bottom" box | measured bottom | the notice |
  |---|---|---|
  | 14.3 | 15.568 | 0.5 mm short |
  | 14.5 | 15.568 | 0.5 mm short |
  | 14.6 | 15.907 | 0.2 mm short |
  | 14.7 | 16.499 | gone |
  | 14.8 | 16.499 | gone |
  | 14.9 | 16.161 | gone |
  | 15.0 | 16.161 | gone |

- a second measurement on the same lever: raising "Bottom" does nothing at all
  until the typed value passes the margin already realised. On a CR30 honeycomb
  in patch-first the frame read 23.654 mm at a typed 12, 14, 17 and 20, and the
  first change came at 24. A reader who is told "6.5 mm short" and raises
  Bottom from 12 to 18.5 changes not one pixel of the sheet.
- the honest options, none of them ours to pick: name no number; name the
  overlap and say in the sentence that it is a minimum; or bring back a search
  that was asked to be removed.
- the question, as a tester can answer it: **"When the sheet text runs into the
  patches, the message tells you how many millimetres short it is. Raising
  ‘Bottom’ by that many millimetres is not always enough, because the patches
  are re-laid out and take some of the room back. Would you rather the message
  (a) named no number at all and just said to raise ‘Bottom’ and press Generate
  Chart again, (b) kept the number but said it is the least it can be, or (c)
  went back to working out the exact figure, which makes the panel slower every
  time you type?"**

---

### B8-241 · The new top notice named a layout mode the reader is not in, and denied the only control that worked
- blocks release: no
- status: FIXED
- found by: the first adversary round against beta 19's own fixes, 2026-09-16,
  by driving the real window (`~/Desktop/ChromIQ-beta18-proof/beta19-round-1/`).
- what a user sees: on "Prioritise chart area" with a **Strip-indicator gap** of
  3 mm, or a **chart offset Y** of 3 mm, the strip-letter notice reads

  > *"⚠ The strip letters are printed over the patches. With “Prioritise patch
  > size” they are held 11.0 mm from the paper edge by the top margin itself …
  > Lower “Label offset” … “T” under “Text distance from edge (mm)” does not
  > move them in this layout."*

  The chart is not on "Prioritise patch size", the top margin is 10.0 mm and not
  11.0, and "T" is exactly what holds the letters there. Photographed:
  `window/P2-T8.png`.
- and its own numbers said so. The same state with "T" walked down, four builds
  (`p2.json`, `window/P2-T2.png`):

  | "T" (mm) | what the panel printed |
  |---|---|
  | 8 | held **11.0** mm, 5.2 mm of every letter on the patches, *"“T” … does not move them in this layout"* |
  | 6 | held **9.0** mm, 3.2 mm on the patches, the same sentence |
  | 4 | held **7.0** mm, 1.2 mm on the patches, the same sentence |
  | 2 | **no notice at all** |

  The sentence denied that "T" does anything while its own figures followed "T"
  three times running, and lowering "T" is what cleared it.
- why: B8-236 taught the notice to fire in "Prioritise patch size", and it chose
  between its three wordings by ARITHMETIC — `strip_label_overlap` compared the
  renderer's anchor with the reserve it works out of "T" and the ruler markers,
  and read any difference at all as "the top margin holds them". In "Prioritise
  chart area" the anchor is *reserve + the layout's strip-indicator gap + the
  chart offset Y*, so a non-zero value in either of two ordinary boxes is a
  difference. The same guess also forced `from_markers` False, so a
  marker-bound collision was sent to the "lower “T”" wording.
- fix: the question is asked of the LAYOUT, once, beside the `if` in
  `geometry.placement` that decides it —
  `geometry.strip_label_band_is_margin_anchored` — and passed to
  `text_edge_fit.strip_label_overlap` as `margin_anchored`. The numeric
  inference is gone. The anchor also carries the strip-indicator gap, so the gap
  is no longer added a second time in `LabelOverlap.reaches_mm`.
- re-driven on screen after the fix (`p1-AFTER-the-fix.json`,
  `window/P1-B-gap3-areafirst-AFTER.png`): the same two states now read *"They
  are held 11.0 mm from the paper edge by “T” under “Text distance from edge
  (mm)” … Raise “Top” … by about 5.2 mm, lower “T”, or use a smaller label
  size."* Patch-first (B8-236's own state) is unchanged and still names the top
  margin.
- no new user-facing string: the fix changes WHICH of three existing messages is
  chosen, so no catalogue moved.
- evidence: test_area_first_is_never_called_prioritise_patch_size,
  test_patch_first_still_names_the_top_margin,
  test_the_helper_mirrors_the_branch_placement_takes,
  test_the_markers_keep_their_own_wording_behind_an_anchor,
  test_an_anchor_does_not_count_the_gap_twice,
  test_the_panel_asks_the_layout_and_not_the_numbers.
  Four mutations proved to land by reading the file back: the arithmetic guess
  restored (5 red), the helper inverted (6 red), the gap passed through behind
  an anchor (1 red), `margin_anchored` dropped at the call site (1 red).

---

### B8-242 · ANSWERED · The new top notice fires on a honeycomb with clear paper under every letter
- blocks release: no
- status: SUPERSEDED
- superseded by: B8-272
- he ruled on 2026-09-16: *"use the 'Measured from Preview' top margin as
  an apex, which is the top margin line measured."* The behaviour below is
  therefore correct; it is now guarded rather than changed. See B8-272.
- reported, not implemented. Nothing was changed, because the rule it follows is
  the design authority's own ruling of 2026-09-15 (*"the calculations should use
  the Measured from Preview numbers"*) and this is that rule meeting a hexagon.
- found by: the first adversary round against beta 19, 2026-09-16, driving the
  real window and measuring the rendered TIFF
  (`~/Desktop/ChromIQ-beta18-proof/beta19-round-1/p10.json`, `p13.json`).
- what a user sees: CR30 pointy-top honeycomb, A4, "Prioritise patch size",
  margins 12 all round, **Label offset 0**, helper markers off. The panel prints

  > *"⚠ The strip letters are printed over the patches. With “Prioritise patch
  > size” they are held 12.0 mm from the paper edge by the top margin itself,
  > they reach 19.3 mm down the page, and the patch area starts at 19.0 mm, so
  > **0.3 mm of every letter is on the first row of patches**. Those patches
  > carry letter ink and will not measure correctly."*

  Measured off that sheet, column by column: **not one letter pixel is on a
  patch**, and the smallest clear paper under any letter is **0.762 mm**. The
  photograph is `window/P13-pointy-clear-paper.png` and the sheet at 4x is
  `crops/P13-ZOOM.png`, where B C D E F sit in the valleys between the apexes
  with white paper under every one.
- and it is not a one-off. The same measurement across the matrix:

  | state | the panel claims | measured clear paper under the lowest letter pixel | columns touching |
  |---|---|---|---|
  | pointy-top, patch-first, offset 0 | 0.3 mm on the patches | **+0.762 mm** | 0 |
  | pointy-top, area-first, offset 0 | 1.3 mm on the patches | **+0.085 mm** | 0 |
  | flat-top, area-first, offset 0 | 0.6 mm on the patches | −0.508 mm | 18 |

  The flat-top row is a true report, understated. Both pointy-top rows are
  false, over-stated by about 1.0 to 1.4 mm.
- why: "Measured from Preview" reports the topmost INK of the whole block, which
  on a pointy-top honeycomb is an APEX — a point at the top of each column. The
  strip letters are drawn beside the apex, over the valley, where the patch ink
  starts about a hexagon's apex overhang lower. The check compares one number
  against one number, so it cannot see that the two are not above each other.
- how far it reaches: **no shipped preset produces it.** Twelve of them were
  loaded and generated in this round, the two hexagonal CR30 ones included, and
  every one came back with an empty message field (`p12.json`). It takes a
  hand-typed margin on a hexagonal chart.
- what is new and what is not: in "Prioritise patch size" the notice could not
  fire at all before beta 19 (B8-236), so **that false warning is new**. In
  "Prioritise chart area" the same comparison shipped in beta 18; beta 19's
  ink-box correction made the letters' reach about 0.25 mm longer, which moves
  borderline states into it but did not create it.
- what a fix would cost, so the choice is informed: the honest comparison is the
  patch ink in the COLUMNS THE LETTERS OCCUPY, not the block's global top, and
  where a letter sits relative to its column's apex depends on the label
  alignment and the glyph. Widening the tolerance by the apex overhang instead
  would mask a real 1 mm collision on the same chart, so it is not the answer.
- the question, as a tester can answer it: **"On a hexagonal chart the very top
  of the patch area is the point of a hexagon, and the strip letters are printed
  beside those points, over the gaps between them. ChromIQ currently warns as
  soon as a letter reaches below the height of the points, even when the letter
  is over a gap and there is clear paper under it. Would you rather it (a) kept
  warning like that, so it never misses a real overlap, or (b) only warned when
  a letter really has ink on a patch, accepting that it then has to look at
  where each letter sits across the page?"**

---

### B8-243 · The "Prioritise patch size" top notice offered a remedy that cannot clear it at any typed size
- blocks release: no
- status: FIXED
- found by: the SECOND adversary round against beta 19, 2026-09-16, driving the
  real window and measuring every figure off the rendered TIFF
  (`~/Desktop/ChromIQ-beta18-proof/beta19-round-2/`).
- this is inside round 1's own fix. B8-241 made this sentence fire in the layout
  it describes; nobody had driven its second half there, and the second half was
  *"Lower “Label offset” under “Strip letters only” by about {over} mm, **or use
  a smaller label size**."*
- what a user sees: "Use instrument margins" off, "Prioritise patch size", top
  margin 10 mm, Label offset 12 mm, strip letters at 20 pt. The panel says
  2.9 mm of every letter is on the first row of patches and offers the two
  remedies above. The reader takes the second one and walks the Size box down:

  | strip-letter Size | what the panel says | measured on the sheet |
  |---|---|---|
  | 20 pt | 2.9 mm on the patches | 2.709 mm |
  | 14 pt | 2.4 | 2.202 |
  | 10 pt | 2.0 | 1.947 |
  | 8 pt | 1.8 | 1.693 |
  | 6 pt | 1.7 | 1.609 |
  | **1 pt**, the smallest the box takes before "auto" | **1.3** | still on the patches |

  The warning is red at every step. The reader has made the strip letters
  illegible and still has letter ink on the first row. Photographed:
  `window/Q10-1-size-floor-still-red.png`.
- and it is not one offset. The whole travel of the box is worth 1.6 mm wherever
  the notice can fire at all (`q7.json`):

  | Label offset | at 20 pt | at 1 pt | cleared? |
  |---|---|---|---|
  | 11, the smallest that warns at all | 1.9 mm | 0.3 mm | **no** |
  | 12 | 2.9 | 1.3 | **no** |
  | 16 | 6.9 | 5.3 | **no** |
  | 24 | 14.9 | 13.3 | **no** |
- why: this is the one layout where the PATCH BLOCK's own top reserve contains
  the label band (`geometry.placement`: `mints = margin_t + txhi + lcar`), so
  shrinking the type lifts the patch area by very nearly as much as it lifts the
  ink. What is left over is the "Label offset", which the band does not contain.
  In "Prioritise chart area" the margin is the law, the patch block does not
  move with the band at all, and the same offer is real: 8 pt clears a 4.3 mm
  collision there (`q5.json`). Only the one wording was wrong.
- fix: the sentence names the one lever that was measured to clear it, and says
  what the other two do instead. Driven after the change
  (`q10.json`, `window/Q10-1-patchfirst-offset12.png`): *"Lower “Label offset”
  under “Strip letters only” by about 2.9 mm. In this layout “T” under “Text
  distance from edge (mm)” does not move them, and a smaller label size lifts
  the patch area with the letters, so neither one clears this."* Applying that
  one lever exactly (Label offset 12 → 9.1) left **0.169 mm of clear paper**
  under the lowest letter and the panel reading "Margins: OK"
  (`window/Q10-1-remedy-applied.png`). The two area-first wordings keep the
  offer (`window/Q10-1-areafirst-keeps-the-offer.png`).
- string change: one key, renamed in all thirteen catalogues, with a new German
  translation; the twelve untranslated catalogues carry the new English.
- evidence: test_a_smaller_label_lifts_the_patch_area_with_the_letters,
  test_prioritise_chart_area_really_does_give_the_size_box_its_travel,
  test_the_patch_first_sentence_does_not_offer_the_size_box,
  test_it_still_says_which_two_controls_do_nothing_there,
  test_the_area_first_sentences_keep_the_offer.
  Two mutations proved to land by reading the file back: the dead offer put back
  into that one sentence (1 red), and `txhi` removed from `placement`'s
  patch-first `mints` so the patch block stops following the band (2 red).

---

### B8-244 · At 1200 dpi the chart has no preview at all, and the panel prints an internal error in its place
- blocks release: no
- status: FIXED
- found by: the second adversary round against beta 19, 2026-09-16. Round 1 saw
  it and recorded it without registering it; this round established that an
  ordinary route reaches it and that nothing tells the reader anything useful.
- what a user sees: A4 (the default paper), the dpi box set to 1200 (its own
  maximum), Generate Chart. The chart builds, "Measured from Preview" reports
  all four margins and "Chart layout information" reports 667 patches, and where
  the chart should be there is this, and no picture:

  > Preview error:
  > QPixmap.loadFromData failed for (9921, 14031) RGB image

  Photographed before the fix: `window/Q8-dpi1200.png`. 300 and 600 dpi were
  fine in the same run (`q8.json`).
- how ordinary the route is: two controls, both on the Create Chart page, both
  at values the app itself offers. Nothing warns beforehand and the sentence
  afterwards names no control.
- why: `TiffPreview._pil_to_pixmap` encoded the page as a PNG and handed the
  bytes to `QPixmap.loadFromData`, which reads through `QImageIOHandler` and
  refuses anything over `QImageReader`'s allocation limit. That limit is 256 MB
  and an A4 page at 1200 dpi is 9921 x 14031, which is 417 MB. Qt logs
  *"QImageIOHandler: Rejecting image as it exceeds the current allocation limit
  of 256 megabytes"* to the console, which no user sees.
- fix: a `QImage` built over the buffer the renderer already holds, then
  `QPixmap.fromImage`. Nothing is read through a handler, so no limit applies,
  and it is strictly less work than encoding and decoding a PNG of the whole
  page on every preview render.
- **the resolution is NOT reduced**, which was the other candidate fix and would
  have been wrong: `_refresh_image` hands this pixmap straight to
  `_measure_own_margin`, so scaling it would quietly coarsen every "Measured
  from Preview" number and every notice the 2026-09-15 ruling measures against
  them.
- driven after the fix (`q10.json`, `window/Q10-2-dpi1200.png`): the chart is
  drawn, the pixmap is 9921 x 14031, the error label is empty, and the frame
  reads Top 13.0 mm at 300, 600 and 1200 dpi alike.
- evidence: test_every_page_the_dpi_box_can_produce_becomes_a_pixmap,
  test_the_pixels_are_the_renderer_s_own,
  test_a_paletted_or_grey_page_still_converts,
  test_the_png_round_trip_is_gone.
  Mutation proved to land by reading the file back: the PNG round trip restored,
  and the 1200 dpi case raises the same `RuntimeError` the panel printed (2 red).

---

### B8-245 · "A narrower Clip border width also makes room" was offered where narrowing frees less room than the text needs
- blocks release: no
- status: FIXED
- found by: the second adversary round against beta 19, 2026-09-16, reaching the
  message from the app, which round 1 could not (`q9.json`).
- what a user sees: i1Pro, A4, clip border on the right, Run 1 Chart Notes
  filled in, the notes needing 2.7 mm at 7 pt. With a 12 mm border and "Right"
  at 12 mm the panel offers *"Setting a narrower “Clip border width” also makes
  room, down to 10 mm."* Narrowing it to 10.0, exactly as told, leaves the panel
  red with a different line: *"they are printed 10.0 mm in from the paper edge,
  need 2.7 mm at 7 pt and have 1.6 mm."*

  | border | "Right" | what was offered | after narrowing to 10.0 |
  |---|---|---|---|
  | 12 | 12 | *"also makes room, down to 10 mm"* | **still red** |
  | 24 | 12 | *"also makes room"* | **still red** |
  | 24 | 20 | *"also makes room"* | cleared |
  | 24 | 6 | *"will not help here"* | (not offered) |
- why: the gate was `typed margin >= CLIP_WIDTH_MIN_MM`, while narrowing frees
  exactly `typed - CLIP_WIDTH_MIN_MM` and the text still has to fit inside it.
  At a typed 12 that is 2 mm against the 2.7 mm the notes want. The function's
  own docstring already said the lever cannot help below about 13 mm, and its
  own measured table has the *"band 12, right margin 12 … still red"* row in it;
  the gate contradicted both.
- and the reason sentence for the other branch would have been wrong there too:
  it said the border *"would still be what decides where the patches start"*,
  which is false at a typed 12 against a 10 mm floor, where the MARGIN decides.
  One sentence now says the thing that is true on both sides of that line.
- fix: `_clip_width_lever_note` takes the caller's own `needed_mm` and offers
  the clause only when `typed >= CLIP_WIDTH_MIN_MM + needed`. All three call
  sites hand it over. Driven after the change (`q10.json`): band 12 / right 12
  says *"narrowing it frees less than the 2.7 mm the text needs"*, band 24 /
  right 20 still offers it, and narrowing there clears the panel.
- string change: two keys (the right and left variants), renamed in all thirteen
  catalogues, with new German translations.
- evidence: test_the_width_lever_is_withheld_when_the_room_it_frees_is_too_small,
  test_the_width_lever_is_still_offered_where_the_room_is_enough,
  test_the_reason_it_gives_is_true_on_both_sides_of_the_old_line,
  test_every_call_site_hands_over_the_room_the_text_needs.
  Two mutations proved to land by reading the file back: the old
  `typed >= CLIP_WIDTH_MIN_MM` gate (3 red), and one call site dropping
  `_o.needed_mm` (1 red).

---

### B8-246 · A report mixed measurements judged against three different limit sets, said so in red, and printed the table anyway
- blocks release: yes
- status: FIXED
- it is the fault the project's design authority reported on 2026-09-16, ahead
  of the non-beta he asked for.
- found by: a tester, 2026-09-16, on two projects of his own; reproduced here
  by driving the real window on both of them
  (`~/Desktop/ChromIQ-beta20-proof/report-sets/`).
- what a user sees: Tools ▸ Measurement report, on a project whose profile runs
  were judged against different limit sets. The Report Scope carries this, in
  red, above the results:

  > **Warning: these reports were not all judged against the same limit set.**
  > The words in one column are not comparable with the words in another where
  > the limit set differs:
  > * Report-Limits-Report-Types @ 2026-10-26T10:00:00: judged against ChromIQ default (recommended)
  > * Report-Limits-Report-Types @ 2026-10-27T10:00:00: judged against ChromIQ tight
  > * Report-Limits-Report-Types @ 2026-10-28T10:00:00: judged against Quick check
  > * … four more

  and then prints the seven columns side by side anyway, in one Report Results
  table, with one "Judged against" row naming the three sets under each other.
  Photographed before the fix:
  `report-sets/round0-profiling/A-opened.png`; the rendered document is
  `round0-profiling/document.txt`.
- **the exact act**: open the window on a run's own profiling measurement
  (which is what Tools ▸ Measurement report does for a Profile selection, and
  what `_report_seed` picks), in a project whose runs do not share a limit set.
  `list_project_reports` gathers every run of the project, which is the
  cross-run history #40 exists for, and nothing asked what each of them had
  been judged against. Seven runs, three set names, five distinct copies.
- **and the INFO beside it is a SECOND cause, not a consequence.** Every row of
  that screen read INFO because a profiling sheet is not graded (§4 of
  `docs/design/measurement_report_limits.md`, Knut's 12b, the one clause of
  that document he has confirmed: *"For now, leave it as is."*). Mixing limit
  sets does not make a verdict collapse; a graded column keeps the PASS or FAIL
  it was saved with whatever else is in the table. The two appear together
  because the same screen is a profiling sheet's report. Measured after the
  fix: the same window still reads INFO, correctly, with one column.
- the rule, in the reporter's words: *"only report data using the same judged
  against threshold sets as the judge against setting set in the report should
  be used when writing the report text. Not mix them together in the report
  output."*
- why: the red line was the whole of the mitigation. `report_scope` raised a
  `compliance` warning when two set NAMES appeared, and `_report_results_html`
  went on rendering every column. Telling a reader that the table they are
  reading cannot be read is not a report.
- **and the warning could not see a third of the mix.** It keyed on the set's
  LABEL. A run carries a COPY of the numbers it was bound to, so two runs can
  both say "ChromIQ default (recommended)" and be judged against different
  numbers; the window derives its own "(edited)" marker from exactly that
  difference and was showing it on one of the seven columns. The warning listed
  that column under the same name as the one it disagreed with.
- fix: `workflow.measurement_report.yardstick_key` makes a comparable key out
  of the set id **and its numbers**, and
  `MeasurementReportDialog._one_limit_set` splits the loaded history into the
  measurements judged against the report's own set and the rest. The document
  gets the first list, in `_report_body_html` and in `_runs_for_document`, so
  the page and the Generate button agree about which sheets the report is
  about. The Report Scope names every measurement left out and why.
- **the history is kept and the sets are separated, which is not deleting
  either.** Every measurement stays gathered, stays in the run list, stays
  tickable and stays a point on the trend over time, which plots measured
  values and carries no verdict. What narrows is the document.
- **the anchor is the sheet the window is on, never the pulldown.** A run's own
  profiling report is deliberately not recalculated when its limit set changes
  (`_recalculate_run` walks `run.verifications()`, which is what §5 of the
  design record specifies), so a run bound to one set can hold a report judged
  against another. Anchoring on the pulldown would throw the window's own
  subject out of its own report, and on the pack that reproduced this it would
  have emptied the document.
- after the fix, on the same window (`round1-after/`): the head line reads
  *"Report type: Full colour check · Judged against: ChromIQ default
  (recommended)"* where it had named nothing, one column is described, and the
  Scope reads *"6 measurements loaded in this window were judged against a
  different limit set, so they are not in the results below."* with all six
  named, the edited copy among them. The trend still draws its seven points.
- driven on the ordinary shape as well, to prove nothing narrowed that should
  not: `Report-Limits-Threshold-Series/run1`, eleven dated verifications all
  judged against one copy of ChromIQ tight, 11 columns in and 11 columns out,
  59 PASS and 40 FAIL unchanged (`round1-ts-run1-verif/`).
- string change: three keys, added to all thirteen catalogues with a new German
  translation; the two keys of the old warning are left in place as a backstop
  for a state nothing can now reach.
- evidence: test_two_copies_of_one_set_with_different_numbers_are_two_yardsticks,
  test_the_same_numbers_in_a_different_order_are_one_yardstick,
  test_a_recommendation_and_a_requirement_of_the_same_value_differ,
  test_a_report_with_no_record_of_what_judged_it_has_no_key,
  test_the_document_never_holds_two_limit_sets,
  test_the_left_out_measurement_is_named_in_the_report_scope,
  test_the_old_red_warning_can_no_longer_fire_on_a_rendered_document,
  test_two_copies_of_ONE_set_are_still_separated_in_the_window,
  test_one_limit_set_everywhere_keeps_the_history_loaded,
  test_the_button_files_a_report_only_for_what_the_page_describes,
  test_a_single_measurement_is_never_filtered_out_of_its_own_report,
  test_the_anchor_is_the_sheet_the_window_is_on,
  test_two_runs_bound_to_different_sets_leave_one_in_the_document.
  Four mutations proved to land by reading the file back: the filter removed
  from `_report_body_html` (3 red), `yardstick_key` reduced to the set id
  (3 red), `_other_limit_sets_html` silenced (2 red), and
  `_runs_for_document` left unfiltered (1 red).

---

### B8-247 · A report about one run offered to save its PDF into the whole project's reports folder
- blocks release: no
- status: FIXED
- found by: the challenge round against B8-246, 2026-09-16, in the first minute
  and inside B8-246's own fix
  (`~/Desktop/ChromIQ-beta20-proof/report-sets/round2-challenge/`).
- what a user sees: a seven-run project, the window opened on run1, the
  document now written against one limit set and describing run1's measurement
  alone. **Save report as PDF** opens with
  `Report-Limits-Report-Types/reports` as the folder, the whole project's, and
  not `runs/run1/reports`, the run the page is about. Measured both ways on
  screen by putting the one line back and driving it again: `C1 pdf folder:
  Report-Limits-Report-Types/reports` before, `…/runs/run1/reports` after.
- why: `_report_dir` takes the common ancestor of the folders the report
  covers, and the common ancestor of seven runs is the `runs` container, which
  it reads as "the whole profile". It asked `_runs_for_report`, "what is
  loaded". That was the same list as the document until B8-246 made the
  document narrower. Its own docstring already said *"The covered set is
  exactly what the report shows"*; the list it asked had stopped being it.
- fix: it asks `_runs_for_document`, the list the body and the Generate button
  already ask. Three callers, one answer.
- evidence: test_the_pdf_is_offered_in_the_folder_of_the_run_it_describes.
  Mutation proved to land by reading the file back: `_runs_for_report` put back
  in `_report_dir` (1 red).

---

### B8-248 · OPEN · Re-ticking a measurement puts it back in the list and not on the trend chart
- blocks release: no
- status: OPEN
- measured, not fixed. It predates B8-246 and is unchanged by it: the same
  three numbers come out of a checkout with that fix stashed.
- found by: the challenge round against B8-246, 2026-09-16, probing whether the
  filter had cost the trend a point. It had not; this had.
- what a user sees, driven on `Report-Limits-Report-Types/runs/run1` with seven
  measurements loaded and "Show all measurement runs" ticked:

  | act | measurements ticked | points on the trend |
  |---|---|---|
  | opened | 7 | 7 |
  | the window's own measurement unticked | 6 | 6 |
  | **ticked again** | **7** | **6** |

- why: `_settings_touched` defers the repaint while **Generate report** can be
  pressed, which is the ruling of 2026-09-14, and repaints at once when it
  cannot, which is the adversary-round fix beside it. Unticking the window's
  own run's only measurement leaves `_reports_to_generate` empty, so the button
  goes dead and that second branch repaints the trend without the point.
  Ticking it again brings the button back, so the repaint waits for it, and the
  chart stays one point short until it is pressed. Both branches are behaving
  as written; the asymmetry is between them.
- the red "the document waits" line IS on screen throughout, so the reader is
  told the page is out of date. What it does not say is that the CHART above it
  is, and the chart is not the document that ruling was about.
- **not fixed here, and deliberately.** Either answer changes what the 2026-09-14
  deferral covers: repainting the trend in both branches makes the chart
  disagree with the table under it, and deferring it in both leaves a dead
  button as the only way to bring a chart up to date. That is a ruling.
- **for the design authority:** when a measurement is ticked or unticked, should
  the trend chart follow at once, or wait for **Generate report** with the rest
  of the document?

---

### B8-249 · The ninth report of one second counted as the newest, and the sixteenth did not
- blocks release: no
- status: FIXED
- found by: the challenge round against B8-246, 2026-09-16, reading the pack a
  tester sent in rather than the code.
- what a user sees: nothing, on the data measured, and that is the whole
  report. One folder of that pack holds sixteen reports stamped
  `2026-09-15_13-35-33`, and the row the window draws for that measurement
  carried `_9`, not `_16`. All sixteen happen to carry the same report type and
  the same limit set there, so no figure and no word on screen was wrong. The
  promise was broken all the same, and the next Generate that changed either
  would have been the one to show it: press **Generate report** ten times with
  a different limit set on the tenth, and the window goes on describing the
  ninth.
- why: `_one_row_per_measurement` picked the greater FILE NAME as a string.
  `save_report` numbers a second report of the same second `_2`, `_3`, …, and
  `"report_…_9.json" > "report_…_16.json"`, so the comparison stops meaning
  "newer" at ten. Its own docstring said *"The newest report of a measurement
  wins, so the row carries the type and the limits the user most recently asked
  for."*
- fix: `_report_file_order` reads the name as what it is, the stamp as text
  (`%Y-%m-%d_%H-%M-%S` sorts correctly that way) and the suffix as a number. A
  name in no known shape sorts before every readable one rather than by
  alphabet, so a file called `odd.json` cannot take a row off a stamped report.
- **the other half of it is B8-252**, registered below: a report the pack
  seeded with a file name stamped in the future still beat one saved today.
  This entry said that was "a question, not a defect with an obvious answer",
  and the challenge round after it found the answer by driving the
  consequence: **Generate report** wrote a file and the page went on
  describing the seeded one. The order is the file's own time now, with the
  name as the tie-break.
- evidence: test_the_tenth_report_of_one_second_is_newer_than_the_ninth,
  test_the_first_report_of_a_second_is_the_oldest_of_it,
  test_a_later_second_wins_whatever_the_suffixes_are,
  test_a_name_in_no_known_shape_never_jumps_the_queue,
  test_the_merge_keeps_the_sixteenth_report_not_the_ninth.
  Mutation proved to land by reading the file back: the string comparison put
  back in `_one_row_per_measurement` (1 red).

---

### B8-250 · There was no way to see, or to remove, any saved report but the newest
- blocks release: yes
- status: FIXED
- it is the second half of what the project's design authority asked for on
  2026-09-16, before the non-beta he proposed: *"the selection and deletion of
  reports with a selector input box is needed and should be made first"*.
- what a user sees now that they did not: a **Saved reports (run1)** row under
  "Judged against", listing every report this run has saved, newest first, as
  *2026-11-02 10:00 · Printing record (not graded) · Custom ISO 12647-7 ·
  saved 2026-11-02 10:00:00 (3)*. Choosing one shows that report. **Delete…**
  removes the one chosen, after a window (M-REPORT-DELETE) naming it, its file
  and how many are left. Photographed in
  `~/Desktop/ChromIQ-beta20-proof/report-sets/round5-final-verification/` and
  `round5-german/`.
- what it replaces: nothing. A run may hold several reports of one measurement
  on purpose (Knut, 2026-09-11), the line above the table counts them, and
  `_one_row_per_measurement` keeps the newest, so the rest could not be opened
  and could not be removed except in Finder. On the pack a tester sent in, one
  run holds **fifty** reports of one measurement and the window could show one
  of them.
- **the one refusal, and it is a decision, not a fact.** The only saved report
  of a DATED VERIFICATION is kept: §5 of
  `docs/design/measurement_report_limits.md` exists so that every dated
  verification of a run is judged the same way and the dates stay comparable,
  and that comparability IS the recorded verdict; a date whose last report is
  gone has none, and the window would then grade it live against today's
  numbers, which is what the lock exists to prevent. The button greys and a
  line beside it says so. A profiling measurement's last report has no such
  record behind it and may go. **Nothing in the model governs deleting a
  report, so this rule waits for approval with the wording.**
- three faults found while driving it, all inside this work and all fixed:
  * **the list could not be read.** Forty-eight of the fifty entries drew the
    identical line, because the label carried the MEASUREMENT's date and not
    the file's own. It now carries when the report was saved and, where several
    share a second, the number `save_report` gave it.
  * **choosing anything but the top entry was impossible.** `combo.findData`
    answers -1 for a PyQt-wrapped tuple that `itemData(i) == want` says is
    there, so every pick snapped back to the first entry. The scan that
    replaced it is the window's own comparison. It reproduces only when the
    pick moves the window's ROW, which is why a test on the easy shape passed
    with `findData` restored.
  * **the row pushed the window's bottom off an 800 px screen.** A hidden
    widget claims no space and one left visible keeps the row: the help button
    was not in the visibility loop, so a measurement with no saved report at
    all paid 41 px for a row with nothing in it.
- string change: ten keys, added to all thirteen catalogues with new German
  translations. One of them is M-REPORT-DELETE, written into §M-PROPOSED of
  `unified_measurement_management.md` and listed in `AWAITING_APPROVAL`.
- evidence: test_every_saved_report_of_the_run_is_offered,
  test_the_selector_never_offers_another_run_s_reports,
  test_two_reports_of_one_second_are_told_apart_in_the_list,
  test_choosing_an_entry_that_is_not_the_first_one_sticks,
  test_the_document_follows_the_report_that_was_chosen,
  test_delete_removes_exactly_the_chosen_file, test_saying_no_removes_nothing,
  test_the_only_report_of_a_dated_verification_cannot_be_deleted,
  test_the_second_to_last_report_of_a_date_may_go,
  test_delete_is_dead_when_the_selector_is_empty,
  test_the_window_survives_losing_the_report_it_was_showing,
  test_the_row_costs_nothing_when_there_is_nothing_to_choose,
  test_the_window_still_fits_the_screen_with_the_row_on_it,
  test_the_merge_records_every_report_file_of_a_measurement,
  test_a_chosen_report_wins_over_the_newest,
  test_a_choice_that_names_no_file_falls_back_to_the_newest.
  Six mutations proved to land by reading the file back: the refusal made inert
  (2 red), `findData` restored (1 red), the `mine` filter removed (1 red), the
  "saved {when}" clause dropped (1 red), `_all_report_files` truncated (5 red),
  and the help button left out of the visibility loop (3 red, two of them the
  screen-fit tests that were already there).

---

### B8-251 · Two of this window's labels were drawn in a colour with no contrast at all
- blocks release: no
- status: FIXED
- found by: the challenge round against B8-250, 2026-09-16, photographing the
  new row and finding a greyed-out Delete with no reason beside it. The reason
  was in the label; the label was invisible.
- what a user sees, measured rather than judged by eye:

  | appearance | label colour | the ground it is on | contrast |
  |---|---|---|---|
  | dark | `#161616` | `#181818` | **1.02** |
  | light | `#d8d4ce` | `#eeece8` | **1.25** |
  | neutral | `#d4d4d4` | `#e2e2e2` | **1.14** |

- **and it was not only the new label.** The same style was on `_type_blurb`,
  which carries *"Already generated for this run: Colour summary (one page)
  (5), Full colour check (48), Printing record (not graded) (1)"*. That is the
  line Knut asked for on 2026-09-11 and reported as truncated on 2026-09-13.
  It was not being read short; in the dark theme it was not being read at all.
  Photographed before and after:
  `report-sets/round3b-saved-reports/S1-selector.png` against
  `report-sets/round4-readable/S1-selector.png`.
- why: `color: palette(mid)`. Qt's Mid role is a 3-D frame shade, not a text
  colour, and ChromIQ's palettes never set it for reading.
- fix: `_faint_label_css` chooses per appearance, the way the strip on the row
  above already chooses its own: `#9a9a9a` on dark, `#5b5b5b` on light, and the
  neutral theme's own named `NM_TEXT_DIM` (12.13:1 on its panel).
- **the test does not re-style the application.** `apply_appearance` calls
  `qapp.setStyleSheet`, which CLAUDE.md forbids in a test; a first cut of this
  one did, and left the next two files in the run with a taller window and two
  red screen-fit assertions. The function is pure, so it is asked directly.
- evidence: test_a_faint_label_is_a_colour_and_not_an_absence,
  test_the_faint_labels_carry_that_colour_and_not_the_palette,
  test_no_label_in_this_window_is_styled_with_palette_mid.
  Mutation proved to land by reading the file back: `palette(mid)` returned for
  every mode (5 red).

---

### B8-252 · Generate report wrote a file and the page went on describing another one
- blocks release: yes
- status: FIXED
- found by: the challenge round against B8-250, 2026-09-16, driving the real
  window on the pack a tester supplied
  (`~/Desktop/ChromIQ-beta20-proof/report-sets/round6-challenge/`).
- what a user sees: a dated verification holding three saved reports, one of
  them chosen in the new "Saved reports" pulldown, and **Generate report**
  pressed. Measured: one new file on disk
  (`report_2026-09-16_22-04-02.json`), the pulldown still at four entries, and
  the page still describing `report_2026-11-02_10-00-00.json`. Nothing on
  screen said a thing.
- **two causes, and the second is the one B8-249 declined to answer.**
  * `_on_generate_report` ended in `_refresh`, which redraws from
    `self._sources` — the list `_gather_runs` filled when the measurement was
    loaded. A report written a second ago is in neither, so it could not be in
    the pulldown and could not be what the merge keeps. It now drops the
    chosen-report override for each measurement it wrote for, because the user
    has just asked for a NEW document of it, and re-reads the sources.
  * and even then the merge kept the older file, because "the newest report of
    a measurement" was decided by the file NAME. `save_report` stamps the name
    with the second it saved, so on a disk where ChromIQ wrote everything the
    two agree; they part company on a project made elsewhere. The demo packs
    seed each report with the name they want its DATE to read, so every report
    this tester generated on 15 September sorted below one named
    `report_2026-11-02_10-00-00.json`.
- **the file times say plainly what the names do not.** Measured on that pack:
  the seeded `report_2026-11-02_10-00-00.json` files carry an mtime of
  2026-09-15 13:36:00 and the reports he generated carry 2026-09-15 13:36:11.
  `_report_order` is the file's own time, then `_report_file_order` as the
  tie-break, so a copy that loses the times gives every file the same one and
  the name decides exactly as it did before.
- **and it explains the rest of what he reported.** With the order fixed, his
  own run1 profiling window draws all seven runs against ONE limit set, Custom
  ISO 12647-7, which is the set he last chose: the mixture B8-246 is about was
  seven stale rows, each the pack's seeded report beating the one he had just
  made. B8-246's rule still stands and still fires where two runs genuinely
  disagree (`Report-Limits-Threshold-Series`, three runs, three sets, two left
  out and named), and it is now the second line of defence rather than the
  first.
- evidence: test_the_file_written_last_wins_even_when_its_name_is_older,
  test_generate_shows_the_report_it_just_wrote.
  Three mutations proved to land by reading the file back: the mtime dropped
  from `_report_order` (1 red), `_reload_sources` removed from
  `_on_generate_report` (1 red), and the chosen-report override left in place
  (1 red).
### B8-260 · A tooltip sent people to a button this tab has not had since #130
- blocks release: no
- status: FIXED

- reported by: a tester, on #182. *"On button 'Load Image (TIFF)' in Print Chart
  tab, the tool-tip text refers to a grid to load a ti2. This button does not
  exist, and is now equivalent to the 'Open Chart File (ti2)' in the upper left
  corner of the app."*
- measured: `ui/tabs/tab_print.py` carried the stale name in THREE places, not
  one. The tooltip on `_load_image_btn`, the status line `_on_load_image` sets
  after an image is loaded (*"load its .ti2 with the grid button — an image
  alone carries no patch geometry"*), and the handler's own docstring. The
  amber grid button left this tab in #130 when the app's whole-app actions
  moved into the masthead; the comment six lines above the tooltip records that
  move, and the tooltip under it was never touched.
- fix: all three name the masthead control, spelled the way the masthead spells
  it and the way eight other strings in the app already spell it,
  *"“Open Chart File (.ti2)” at the top left of the window"*. Both user-facing
  strings lost their em dashes on the way (`--prune` took the two baseline
  entries with them; the baseline only shrinks).
- DELIBERATELY NOT DONE, and pinned by a test so it is not "fixed" later: the
  reporter's second sentence, that a correct profile run should be selected
  before a chart is opened. It is right, and the app already says it at the
  moment it matters, in the design authority's own wording. Pressing Print with
  **Profile run** on "New run" raises
  `core.measurement_target.new_run_guard_message("print")`, which names the
  selection to change and every way to make a run. This tooltip is on a button
  that neither opens nor creates a chart, so repeating a four-paragraph guard
  on it would add reading and change no outcome.
- on screen: driven in a real window, both languages, photographed through
  `scripts/onscreen_capture.py`. `en-1-load-image-tooltip.png`,
  `de-1-load-image-tooltip.png`, `de-2-print-chart-tab.png` in
  `~/Desktop/ChromIQ-beta20-proof/text-fixes/`.
- evidence: test_the_load_image_help_does_not_send_anyone_to_the_grid_button,
  test_the_load_image_help_names_the_masthead_control,
  test_the_masthead_really_spells_it_that_way,
  test_the_tooltip_does_not_repeat_the_run_guard,
  test_both_load_image_strings_are_still_there.
  Two mutations proved to land by reading the file back: the tooltip and the
  status line each put back to "the grid button" (1 red each).

---

### B8-261 · The averaging-failed window was English in eleven of twelve languages
- blocks release: no
- status: FIXED

- measured: `TabMeasure._show_average_failed_dialog` put its TITLE through
  `tr()` and its body not at all, so every language but English showed the body
  in English. It also carried an em dash, against the house rule.
- the sentence was CHECKED BEFORE IT WAS TRANSLATED, because it is a promise.
  *"Your individual reads are still saved, you can continue from the Build
  Profile tab using one of them"* used to be false: every read had already been
  moved into `reads/` and `average` writes its output only on success, so this
  ending handed back a run holding no `.ti3` at all. Round 5 gave the ending a
  file back (the B8-213 mechanism): `_put_the_last_read_back` COPIES the newest
  read back as the run's measurement and leaves `reads/` intact, and
  `measure_finished` arms the tab the sentence names. The promise is kept now,
  so the wording stays and is translated.
- fix: the body goes through `tr()`, the runtime reason is a `{detail}`
  placeholder rather than a `+` concatenation (so a translator is handed the
  sentence whole and can put the reason where their language wants it), and the
  em dash is a comma. German written; the eleven carry the English under the
  beta rule.
- NOT DONE, registered instead: this window is a MEASUREMENT window whose text
  is in neither `WINDOW_SOURCES` nor `UNCATALOGUED_MEASUREMENT_WINDOWS` in
  `tests/test_message_catalogue.py`, so §M governs it in neither direction and
  it can word itself freely with both lists green. Proposing its text to
  §M-PROPOSED is a wording decision for the design authority, not a
  punctuation fix, so it is named here rather than started.
- on screen: `en-3-averaging-failed.png` and `de-3-averaging-failed.png`. The
  German window is German in title and body.
- evidence: test_the_averaging_failed_window_is_one_translatable_sentence,
  test_the_averaging_failed_window_carries_no_em_dash,
  test_the_averaging_failed_window_is_german_in_german,
  test_the_promise_the_window_makes_is_one_the_code_keeps.
  Four mutations proved to land by reading the file back: the body unwrapped
  and concatenated again, the em dash put back, the German value replaced by
  its English key, and the failure branch no longer putting a read back
  (1 red each).

---

### B8-262 · Three sentences of the Print Chart warning never reached `tr()`, and the sweep could not see them
- blocks release: no
- status: FIXED

- found by measuring for the rest of B8-261's shape rather than by a report.
- the MECHANISM, which is the part worth keeping: `i18n_extract`'s
  `unwrapped_literals` only ever inspected a bare `ast.Constant` argument. A
  text sink whose argument is a sum, `QLabel("…" + detail + "…")` or
  `setText("…" + fallback_sentence)`, is a `BinOp`, so the sweep skipped the
  argument and every literal inside it. Second rule, compounding it:
  `is_user_facing_text` rejected anything matching `^\s*<` as "markup", and
  this app's rich-text windows open with `<b>` as a matter of course.
- measured across the whole app: those two rules together hid exactly FOUR
  sentences and no others. `TabPrint._set_native_mode`'s lp-path warning (the
  body plus its two `fallback_sentence` variants) and B8-261's dialog body.
  The warning's sibling branch, for the native print dialog, has gone through
  `tr()` since it was written.
- reachability, stated honestly: `use_native_print_dialog` defaults to True on
  macOS and Windows, so this warning is what a Linux user sees and what a macOS
  user sees after turning the native dialog off in Preferences. It is the
  branch whose path the Printer tooltip documents.
- fix: all three wrapped, the fallback sentence a `{fallback}` placeholder
  rather than a concatenation, German written. And the sweep itself widened:
  `_literal_leaves` looks through `+`, and `is_user_facing_text` judges the
  words OUTSIDE the tags (`_prose`) instead of refusing anything that opens
  with one. The widened sweep finds nothing left; the one string it newly
  surfaced, `"colprof "` echoed as a command line for copying, joins its
  already-listed twin in `UNTRANSLATED_ON_PURPOSE` with the reason.
- on screen: `de-2-print-chart-tab.png` shows the warning in German in the real
  window, where it was English before.
- evidence: test_every_sentence_of_the_lp_print_warning_is_translatable,
  test_every_sentence_of_the_lp_print_warning_is_german_in_german,
  test_the_fallback_sentence_is_a_placeholder_not_a_concatenation,
  test_the_sweep_looks_through_concatenation,
  test_a_sentence_that_opens_with_a_tag_is_still_a_sentence,
  test_the_widened_sweep_finds_nothing_left,
  test_the_comment_stripper_actually_strips.
  Three mutations proved to land by reading the file back: the warning
  unwrapped, the sweep's call site narrowed back to a bare `Constant`, and
  `is_user_facing_text` given its `^\s*<` rule back (1 red each).
- a note on the guard's own guard: two of these tests passed on their first run
  against a COMMENT in the code they check, because the code explains itself by
  quoting the shapes being banned. `_code_only` strips comments first, and is
  itself checked.

<!-- Merge note, 2026-09-16: the entries below were written as B8-240, B8-242, B8-250, B8-251, B8-252, B8-253, B8-254, B8-255, B8-256, B8-257
     on the chart-panel branch while another branch used those numbers;
     they are renumbered B8-240, B8-242, B8-265, B8-266, B8-267, B8-268, B8-269, B8-270, B8-271, B8-272 here, references included. -->
### B8-270 · The ruling on B8-239 · "T" does not move the strip labels in "Prioritise patch size", and the help now says so
- blocks release: no
- status: FIXED
- the design authority ruled on B8-239 on 2026-09-16; this entry is what was
  implemented.
- the ruling, verbatim: *"The most logical ruling is that the T parameter works
  the same way, however, since 'Prioritise patch size' is based on working more
  closely as the original printtarg, I guess it is a risk to start changing
  that feature. I rule No, and the help text should mention this."*
- so **the geometry is unchanged**. `geometry.strip_label_leader_top_mm` still
  hangs the band on `margin_t + offset_y` when `margins_are_law` is false, and
  "T" is not consulted there.
- what changed is the help: the ⓘ on "Text distance from edge" gains a
  paragraph saying that in that layout the labels are placed automatically, the
  way printtarg does, and that the two controls which move them are "Top" under
  "Margins (mm)" and "Label offset" under "Strip letters only".
- the paragraph is its OWN `tr()` key rather than an edit to the existing
  tooltip. Folding it in changed that string's key, which turned all thirteen
  shipped translations of it stale in one edit (23 red tests) and would have
  forced twelve languages to lose a translated tooltip or carry an English tail
  inside one.
- evidence: in the two-layout-rulings file under `tests/`,
  `test_the_T_help_says_it_does_not_move_them_in_patch_first`,
  `test_the_geometry_still_ignores_T_in_patch_first`.

---

### B8-271 · The ruling on B8-240 · The bottom-notice rise search is allowed back, on his condition
- blocks release: no
- status: FIXED
- the design authority answered B8-240 on 2026-09-16; this entry is what was
  implemented.
- the ruling, verbatim: *"as long as a search is done after a generate chart and
  margins have been measured, then option 3 is acceptable for the bottom text
  warning."*
- `margin_rise_that_clears_mm` is therefore back in `ui/tabs/tab_chart.py`, and
  it is **not** the function that was deleted. Both halves of his condition are
  structural:
  - it is called only inside the branch that has a measured report, which means
    a chart has been generated and measured;
  - every candidate margin is laid out and then widened by
    `margin_inspector.engine_ink_bounds_px`, **the same function that measures a
    BUILT chart**, instead of being read off `geometry.compute`'s grid box. That
    box is what answered 18.60 mm on a flat-top honeycomb whose ink ends at
    15.82, which is why the old search was retired.
- and it is ANCHORED on the sheet in front of the reader: the model's answer for
  the current recipe is differenced against the measured bottom margin and every
  candidate carries that offset. Measured on a tester's own 648-patch chart, the
  model says 18.710 mm where his built sheet measures 18.964, so an uncalibrated
  search would have named a rise half a grid step optimistic.
- `engine_ink_bounds_px` was split out of `measure_from_engine` unchanged, so
  there is ONE implementation of "where does the ink really reach" and the
  search cannot walk a different sheet from the one the panel measures. Checked
  against a tester's own chart: 18.964 mm before and after the split.
- **AND IT MAY NOT NAME ITS NUMBER IN "Prioritise patch size"** — see B8-269,
  which arrived forty minutes later and narrows this one.
- **THE FIRST VERSION OF IT WAS A FREEZE, AND A CHALLENGE ROUND AGAINST MY OWN
  WORK FOUND IT.** The *when* was fixed by his condition; the *how much* was
  not. `margin_inspector.engine_patch_bottom_mm` costs **13.2 ms** a call on an
  i1Pro A4 sheet, two thirds of it `geometry.patch_rects_px` building a rect and
  a `SAMPLE_LOC` for all 1023 patches, and a plain 0.5 mm walk over the margin
  box's range took **36 probes (1.7 s)** to find an answer and **101 (3.6 s)**
  to decide there was none — on the panel, which is the cost that got the
  previous search deleted in the first place. A coarse 2.5 mm scan that hands
  over to the 0.5 mm grid inside the one interval that cleared brings it to
  **13 and 21 probes, about 450 ms**, with the candidates memoised. It names the
  same rise: compared against the plain walk over **48 states**, zero
  disagreements.
- evidence: in the bottom-sheet-text and bottom-text-measured files under
  `tests/`,
  `test_no_bottom_message_names_a_rise_or_a_paper_any_more`,
  `test_the_panel_measures_the_patch_bottom_rather_than_predicting_it`; and for
  the cost, in the rise-search-is-cheap file,
  `test_the_fast_scan_gives_the_fine_walks_own_answer`,
  `test_the_search_stays_inside_a_probe_budget`,
  `test_a_repeated_candidate_is_not_rebuilt`.

---

### B8-272 · The ruling on B8-242 · The pointy-top honeycomb notice is judged against the apex, and that is correct
- blocks release: no
- status: VERIFIED
- the design authority ruled on B8-242 on 2026-09-16: the behaviour is correct,
  so nothing changed and a guard was added instead.
- the ruling, verbatim: *"use the 'Measured from Preview' top margin as an apex,
  which is the top margin line measured."*
- so the behaviour reported in this entry is the intended one. `report.top_mm`
  is measured by `margin_inspector` to the block's TOPMOST ink, and on a
  pointy-top honeycomb that is an apex; the notice compares against it. A sheet
  can therefore carry clear paper directly under the lowest letter and still be
  reported, because the ink beside it reaches higher.
- nothing was changed. A guard was added instead, because "the warning fires on
  clear paper" is exactly the shape of report that invites a later round to
  soften it: the guard fails if a hexagon-shaped exception enters
  `strip_label_overlap`, or if the apex correction leaves `engine_ink_bounds_px`.
- evidence: `QT_QPA_PLATFORM=offscreen pytest -n auto` on this branch —
  **15902 passed, 334 skipped, 4 xfailed**, exit 0. The three guards that hold
  the ruling are `test_the_top_margin_the_check_uses_is_the_measured_apex`,
  `test_the_measured_top_is_the_blocks_topmost_ink_apex_included` and
  `test_a_valley_case_is_still_reported_rather_than_softened`.

---

### B8-265 · "Size = auto" chose a label size that fired its own left-margin warning · RULED AND SHIPPED
- blocks release: no
- status: FIXED
- **held for eleven days, then ruled on.** The design authority, 2026-09-16:
  *"It is more important that the feature is correct, so make the fix for the
  'Size = auto' choosing a label size that fits with the margins used."* So it
  ships, and the reason it was held is gone: the cost was three Letter presets
  needing a sheet more than their name promises, and **he removed that himself**
  by specifying the preset changes in B8-280 rather than accepting it.
- **who decided what, for the record:** the checking round built this, measured
  its cost and HELD it on its own judgement; the maintainer agreed and confirmed
  the hold; the ruling is the design authority's and is quoted above. Nothing
  here was decided by the round that implemented it.
- reported by a tester on beta 19, loading
  `CR30-A4-420p-1page-Portrait-w11.0mm-Hexagonal`: the panel said the left
  margin had to be widened from 13.0 mm to 14.0 mm to hold the row indicators,
  which "auto" had sized at 19 pt, *"but reducing the font size manually to 16pt
  would remove the warning. Since size is set to auto, I would expect the label
  text size to be found where there is no warning (as long as size does not go
  below 7pt, as usual)."*
- the cause: `raster.effective_indicator_size_mm` sizes the label to the PATCH
  WIDTH and knows nothing about any warning. Nothing anywhere fed the left
  margin back into the choice. `preflight.indicator_width_warning` calls the
  chooser, never the other way round.
- **the fix.** When the size is AUTO and the band would force `margin_l` above
  the typed value, `apply_row_label_geometry` walks the size down the
  half-point grid (`text_edge_fit.next_size_down_pt`, the grid the Size boxes
  themselves step by) to `AUTO_SHRINK_FLOOR_PT` (7 pt) and takes the first that
  fits. The answer is stored on `Geom.row_label_size_mm` and read back by
  `raster.effective_row_label_size_mm`, which is the single function every
  reader of the size comes through, so the renderer draws the size the band was
  reserved for.
- **driven on screen, on his own preset**, with the left margin and the size as
  he had them: "auto" settles at **16.0 pt**, the very size he named;
  `margin_l` stays at the 13.0 mm the recipe asks for; the measured patch-block
  edge moves 13.970 → 13.081 mm and the left-margin notice goes. All eight
  upright hexagonal CR30 presets were in that state and all eight clear.
  Proof in `~/Desktop/ChromIQ-beta20-proof/autosize-and-presets/`.
- **one fault of my own, found by the guard and not by the driver.** The first
  build left the settled size on the geometry, so a second application measured
  the band at that size, found it already fitted, walked nothing, and returned
  a geometry with the band reserved for 16 pt and the size back at "auto" --
  the renderer would then have drawn 19 pt into a 16 pt band. The settled size
  is now dropped before anything is measured. No on-screen run would have shown
  this, because the app applies the function once.
- **the cost that held it, and that it no longer has.** Releasing the left
  margin gives area-first a wider box, and area-first fills a wider box with
  BIGGER patches for the same count, so a chart that just fitted spills.
  Measured again on this branch with the fix in and the presets NOT yet
  changed: `Letter-390p` went to 2 pages, `Letter-780p` to 3, `Letter-1170p`
  to 4, every A4 chart unchanged. With B8-280's preset changes in the same
  batch, all eight print exactly the count and the page total their names
  state, measured off the rendered TIFFs.
- §R8 of `docs/design/row_label_geometry.md` is rewritten from a proposal to
  the built rule, and stays in ⏳ Awaiting confirmation: the RULE is his, but he
  has not yet seen a beta carrying the behaviour.
- **his other beta-19 finding on this same warning IS fixed**: see B8-269, where
  the check now reads the measured margin.
- **a false sentence this created, found by challenging my own work and not by
  anyone reading the app.** The "Indicator font" ⓘ promises *"Size 'auto' fits
  the strip letters to the strip width, and the row numbers follow the same
  size"*. Since this change they need not: measured on the reported chart, the
  strip letters print at **19.0 pt** and the row numbers at **16.0**. The
  sentence is still true of most charts, so it stays and a paragraph is added
  that says when it is not, naming the half-point step and the 7 pt floor so a
  reader can predict what they will get. Its own `tr()` key, translated into
  all thirteen catalogues.
- evidence: in the size-auto-fits-the-margin file under `tests/`,
  `test_auto_settles_at_sixteen_points_on_his_own_preset`,
  `test_the_two_label_sets_really_can_differ_in_size`,
  `test_the_font_help_no_longer_promises_one_size_for_both`,
  `test_the_left_margin_he_asked_for_is_the_one_he_gets`,
  `test_the_renderer_is_told_the_size_the_band_was_reserved_for`,
  `test_a_typed_size_is_left_exactly_where_it_was_typed`,
  `test_nothing_is_committed_when_no_size_down_to_the_floor_fits`,
  `test_applying_the_geometry_twice_does_not_ratchet_the_label_down`,
  `test_the_band_reserved_and_the_size_drawn_always_describe_one_chart`,
  `test_the_walk_never_goes_below_the_floor_he_named`,
  `test_every_size_it_settles_on_is_one_the_size_box_can_hold`,
  `test_a_shorter_margin_never_settles_on_a_larger_label`,
  `test_the_eight_hexagonal_presets_still_print_what_their_names_promise`; and
  in the clip-text-meets-the-row-labels file,
  `test_a_margin_that_a_smaller_label_would_clear_DOES_move_the_ink`,
  `test_a_typed_size_is_never_walked_down`,
  `test_a_wider_left_margin_does_not_move_the_label_ink`.


---

### B8-266 · The strip-label ink probe could not see the "Q", so the top notice arrived a millimetre late
- blocks release: no
- status: FIXED
- reported by a tester on beta 19, on his own
  `CR30-A4-450p-1page-Portrait-w11.0mm-Hexagonal-Straight`, labels at 11 pt, top
  margin 13.0 mm: *"the strip labels ... hit the patch area edge at T=9,0mm, but
  warning message came at 9,5mm. ... Thus, it is not the threshold that is at
  fault, but the measurement of the text height that is slightly off."*
- **he was right, and his own rendered sheets say by how much.** Measured off
  the two TIFFs he attached, reading each label column's black ink at 200 dpi
  (`~/Desktop/ChromIQ-beta20-proof/knut-beta19/fault2-tiff-measurement.txt`):

  | his sheet | a plain letter inks to | the **Q** inks to |
  |---|---|---|
  | `test-T9.0mm.tif` | 13.08 mm | **13.72 mm** |
  | `testT9.5mm.tif` | 13.59 mm | **14.22 mm** |

  The panel predicted 13.1 and 13.6, so it was exact to the hundredth about the
  letters with no descender and 0.64 mm short about the one with one. The patch
  area starts at 13.0 mm, so at "T" 9.0 there was 0.72 mm of Q on the first row
  of patches in silence.
- the cause: `raster._furniture_reserves_mm` measured the ink with a probe of
  the string **"W8"**. Neither glyph descends. **"Q" is the only letter in A-Z
  that does**, and `permutation`'s alphabetic labeller reaches it at the 17th
  strip; his chart has 18.
- the fix: the probe is the labeller's own first 26 labels, so it measures the
  letters the sheet will really print (`A-Z` for an alphabetic pattern, digits
  for a numeric one) rather than a hand-picked pair.
- **nothing lays a chart out from this number.** `label_ink_reach_mm` and
  `label_ink_top_mm` are predictions for the panel; the layout reserve
  (`label_ink_bottom_mm`, which `geometry._top_reserve_for_a_turned_hex` moves
  the patch block by) is deliberately untouched, so no sheet moves.
- what it costs, measured and bounded: the strip COUNT is not knowable where the
  reserve is computed, because the reserve feeds the capacity that decides it,
  so a chart with fewer than 17 strips never prints a Q and is predicted up to
  0.64 mm (at 11 pt) pessimistically. That is the safe direction for an overlap
  notice and the only one available without a second layout pass.
- driven on screen with "T" walked over the boundary on GENERATED, measured
  sheets (`onscreen/case2-T-walk.json`): at **T = 10.0 mm** the letters reach
  **14.657 mm** while the patches start at **13.97 mm**, the notice fires, and
  with the retired "W8" probe it would have been **silent** (13.979 mm against a
  14.17 mm threshold).
- evidence:
  `test_the_probe_text_is_the_labellers_own_output`,
  `test_the_probe_reaches_the_tail_that_a_W8_probe_misses`,
  `test_the_reach_a_geometry_reports_carries_the_tail`,
  `test_nothing_lays_a_chart_out_from_the_reach`.
  Mutation proved to land by reading the file back: probing "W8" again (1 red).

---

### B8-267 · The strip letters could be driven into the top helper markers with no warning at all
- blocks release: no
- status: FIXED
- reported by a tester on beta 19: *"When 'Prioritise patch size...' and helper
  markers are on (4mm distance and 2mm marker length), and then setting top
  margin (in Page geometry frame) to 5mm, the strip labels overlap with the
  'helper marker distance from page'+'marker length'+1.0mm rule. But there is no
  warning message. Same happens if Label offset is set to -5mm or -5.5mm, while
  top margin setting is 10.0mm."*
- the cause: every existing check compared the letters with the patch area
  BELOW them and **nothing compared them with the furniture ABOVE**. In
  "Prioritise chart area" that was survivable, because `edge_reserve_mm` places
  the band at `max("T", edge + len + 1.0)` and clears the dashes by
  construction. In "Prioritise patch size" the markers are not consulted at all:
  `geometry.placement` anchors the band on `margin_t + offset_y`.
- the fix: `text_edge_fit.strip_label_marker_overlap`, called from the panel.
  The test is on the INK and not on the anchor, because his second case moves
  the letters without moving the anchor; an anchor-based check would have caught
  one and missed the other.
- the wording obeys B8-268: the "Label offset" remedy carries a number, because
  that control was measured moving the letters one millimetre per millimetre in
  this layout, and "Top" is named without one.
- driven on screen, both of his cases, on generated and measured sheets
  (`onscreen/panel-notices.json`, cases 3a and 3b): top margin 5.0 mm reports
  **0.6 mm** of letter on the markers, Label offset -5.5 mm reports **1.1 mm**,
  and the control case at top margin 12.0 mm is silent.
- evidence:
  `test_his_first_case_the_top_margin_drives_them_in`,
  `test_his_second_case_a_negative_label_offset_drives_them_in`,
  `test_a_sheet_that_clears_them_stays_quiet`,
  `test_it_says_nothing_when_this_edge_carries_no_markers`,
  `test_the_panel_asks_the_question_and_offers_the_right_lever`,
  `test_the_reach_is_the_rule_he_quoted`.
  Mutation proved to land: returning None unconditionally from
  `strip_label_marker_overlap` (1 red).

---

### B8-268 · The bottom text's width was predicted at 7 pt while the renderer drew it at up to 16
- blocks release: no
- status: FIXED
- reported by a tester on beta 19: *"if I then enable 'Stamp layout summary...'
  the measured bottom margin changes from 11.3mm to 19,0mm, and there becomes
  much more space for the bottom text. However, the bottom text sometime is set
  to a larger size than there is room for, there the bottom text overlaps with
  the right side placed clip-border area, but there is no warning message."*
- his 19.0 mm reproduces exactly: `measure_from_engine` on the `channels.json`
  he attached answers **18.964 mm**.
- the cause: `TabChart._sheet_text_width_mm` resolved an auto Size to
  `AUTO_SHRINK_FLOOR_PT`, 7 pt. **That was right while "auto" could only
  shrink** -- the panel must not warn about a line the renderer is about to make
  fit. Since beta 17 `raster.auto_sheet_text_size_mm` starts at a 16 pt CEILING
  and returns the LARGEST size that fits, so the panel was measuring the
  narrowest line the renderer might draw while the renderer drew one up to
  16 pt wide, and the width warning could not fire for an auto-sized block at
  all.
- the fix: one resolver, `TabChart._bottom_text_size_mm`, shared by the block
  width and the per-line widths, which asks `auto_sheet_text_size_mm` against
  the room the overflow check itself uses -- built from the MEASURED margins, so
  the two cannot describe different sheets. The 7 pt floor survives as the
  fallback for callers with no room to offer.
- **AND THE FIRST FIX FOR IT WAS A FALSE WARNING WAITING TO HAPPEN, WHICH A
  CHALLENGE ROUND AGAINST MY OWN WORK CAUGHT.** `auto_sheet_text_size_mm` fits
  the WIDTH only; `render_pages` then walks the size down a second time until
  the line's box fits the band the engine reserved. Measured at a 200 mm room:
  the width rule alone says **14.50 pt** and the sheet carries **9.84**. Asking
  only the width chooser would therefore have swapped a missing warning for an
  invented one, on a roomy sheet. `_bottom_text_size_mm` applies both loops and
  now predicts 9.50 pt there, which is the safe side of what is drawn.
- evidence:
  `test_auto_is_resolved_by_the_renderers_own_chooser`,
  `test_a_typed_size_is_still_used_as_typed`,
  `test_a_wider_line_is_what_overflows_a_clip_border`,
  `test_the_panel_hands_the_measured_room_to_the_width_helper`.

---

### B8-269 · The left-margin warning read the setting instead of the sheet, and named a value that means nothing in patch-first
- blocks release: no
- status: FIXED
- the check is fixed; the wording half is a ruling, recorded below.
- reported by a tester on beta 19, on a "Prioritise patch size" chart he
  attached: *"The warning talks about the widening of the left area to 16.4mm,
  but the measured margin is already stating 26.0mm, while the left margin
  setting is 10.0mm. Thus, the check seems to use the left margin setting, and
  not the measured margin for controlling what is needed, so reporting wrong
  numbers."*
- **reproduced from his own `channels.json`** (staged at
  `~/Desktop/ChromIQ-beta20-proof/knut-beta19/chart-pps/`): typed left margin
  **10.00 mm**, the raise computes **16.31 mm**, the sheet measures
  **26.04 mm**.
- and measured off his rendered `test_01.tif` at 200 dpi
  (`fault5-tiff-measurement.txt`): the row indicators' ink ends at **14.99 mm**
  and the first patch ink begins at **26.04 mm**, so there was **11.05 mm of
  clear paper** where the panel printed a red warning. He saw it too: *"there is
  plenty of space between the row indicators and the measured left margin"*.
- the cause: `_raised_l` compared two numbers out of the GEOMETRY -- the margin
  asked for and the margin the raise computed -- and never looked at where the
  patches landed. In patch-first they do not land on `margin_l` at all.
- the fix: the warning is dropped when the sheet already gives the labels their
  room (`_got_l <= _meas_l + tol`). With no report the geometry's answer stands,
  because then it is the only fact there is.
- **the second half is a ruling that reaches the whole panel**: *"Changing left
  margin setting has no effect until the setting is brought above the measured
  left margin, so setting left margin to 26.0mm has no effect on the patch area
  left margin, but setting left margin to 27.0mm makes measured margin jump to
  35.9mm. ... Stating what to set the left margin, while in 'Prioritise patch
  size...' is selected, is not reliable. Only when 'Prioritise chart area...'
  this is reliable. Thus, the warning messages while in 'Prioritise patch
  size...' should not specifically mention what to set the margin settings to,
  but rather say which parameters can be altered to attempt removing a warning."*
- `margin_values_are_reliable(r)` implements it, and gates three places: both
  left-margin wordings, and B8-240's bottom-text rise, which is not even
  searched for in patch-first because its answer could not be used.
- **the narrower reading was implemented deliberately.** His acceptance of the
  rise search (B8-240) and this ruling arrived forty minutes apart and pull
  against each other. The rise is named in chart-first, where the margins are
  law and the number does what it says, and in patch-first the same message
  names the controls. It is a MARGIN-box rule: "Label offset" is not one, and it
  was measured moving the strip letters one millimetre per millimetre in
  patch-first, so its number is still given.
- driven on screen (`onscreen/panel-notices.json`, case 5): a generated
  patch-first sheet measuring **33.78 mm** on the left against a computed
  **33.79 mm** raise, and the panel is silent.
- evidence:
  `test_the_raise_is_dropped_when_the_sheet_already_gives_the_room`,
  `test_the_predicate_in_its_five_states`,
  `test_his_sheet_really_has_the_room_the_fix_assumes`,
  `test_a_margin_value_is_named_only_where_it_means_something`,
  `test_every_margin_remedy_is_gated_on_the_layout`,
  `test_the_patch_first_wordings_name_controls_and_no_margin_value`,
  `test_the_label_offset_keeps_its_number_in_patch_first`.
  Mutation proved to land by reading the file back: deleting the
  measured-margin guard (1 red).

---

### B8-273 · The merge renumbered ten entries and six pointers did not move, two of them onto the wrong entry
- blocks release: no
- status: FIXED
- found by: the combined adversary round over the merged tree, 2026-09-17,
  checking the briefing's own instruction that "nothing still points at a
  number that moved".
- **the merge is where this comes from, and neither branch could have seen
  it.** Three features were built in parallel and merged by hand. Two of them
  had numbered their register entries out of the same free block, so ten of the
  layout branch's entries were renumbered on the merge: `B8-250` … `B8-257`
  became `B8-265` … `B8-272`. The merge note in this file says the references
  moved with them. Six did not, and they are two different faults:
  - **Four point at nothing at all.** `B8-239` said *"what was implemented is
    B8-255"*, `B8-240` said *"implemented is B8-256, and B8-254 then narrowed
    it"*, and `B8-242` said *"See B8-257"*. None of `B8-253` … `B8-257` exists
    in the merged register, so the trail from each ANSWERED question to the
    entry that settled it simply stopped. All three of those entries have a
    correct `superseded by:` line, which is exactly why nobody noticed: the
    forward pointer was right and the sentence underneath it was not.
  - **Two point at the WRONG entry, which is worse, because they read as
    correct.** `workflow/layout_engine/raster.py` (twice) and §R8 of
    `docs/design/row_label_geometry.md` all said the held "Size = auto"
    decision is carried by `B8-250`. In the merged register `B8-250` is the
    Measurement Report's "Saved reports" row, and the auto-size decision is
    `B8-265` — the one entry the owner has deliberately left unshipped,
    because shipping it costs three Letter hexagonal presets an extra sheet.
    A pointer that leads somewhere else is how a held decision gets lost, and
    one of the two is in a **binding design document**, which a reader is
    obliged to consult before changing that area.
- **what was changed:** the six citations, and nothing else. `B8-265` is not
  shipped, not undone, and not touched; this entry only makes the three places
  that talk about it say its number.
  - `docs/beta8_open_items.md` — B8-255 → B8-270, B8-256 → B8-271,
    B8-254 → B8-269, B8-257 → B8-272, each checked against the heading of the
    entry it now names.
  - `workflow/layout_engine/raster.py` lines 976 and 1010 — B8-250 → B8-265.
  - `docs/design/row_label_geometry.md` §R8 — B8-250 → B8-265.
- the guard lives in
  `tests/`, in the file named for this rule (`..._every_register_citation_...`).
- evidence:
  `test_every_b8_citation_names_an_entry_that_exists` sweeps every `B8-NNN`
  written in `ui/`, `workflow/`, `core/`, `tests/`, `scripts/` and `docs/` and
  fails on one the register does not define;
  `test_the_held_auto_size_decision_points_at_its_own_entry` asks the register
  for the id of the entry whose HEADING says "Size = auto" and requires the two
  files that discuss it to cite that id, so the next renumber moves the
  expected answer instead of breaking the test;
  `test_a_superseded_entry_points_forward_to_a_real_settlement` requires every
  `superseded by:` to name a defined, later entry; and
  `test_the_sweep_is_not_vacuous` fails if the sweep stops finding citations at
  all. The register's own merge note, and this test file's own prose, are the
  two places allowed to write a retired number, and both exemptions are
  explicit.
- **mutation, proved to land, one at a time:** `B8-265` → `B8-250` in
  `raster.py` reds `test_the_held_auto_size_decision_points_at_its_own_entry`
  and names the entry it landed on; the same in `row_label_geometry.md` reds
  the same test; `B8-270` → `B8-255` in this file reds
  `test_every_b8_citation_names_an_entry_that_exists`. All three restored and
  green.
- **and what this round did NOT find**, measured rather than assumed, so the
  next round does not pay for it again: the twelve catalogues hold one
  identical key set with 0 missing and 0 stale against what the code asks for,
  and both untranslated budgets are the tree's own count with ZERO slack in all
  twelve languages; no hunk of either parent branch was lost in either merge;
  every `evidence:` line on B8-246 … B8-272 names test functions that exist;
  the bottom-text notice's named rise is a promise that keeps (16.5 mm named,
  applied, the notice cleared, the measured patch bottom moved 4.98 → 21.58 mm);
  the "only saved report of a dated verification" rule holds on every entry of
  the selector after a generate and a delete; Generate report shows what it
  wrote; the "Saved reports" pulldown really does re-anchor the document
  (1 row → 12 when the yardstick changes) and the Report Scope names all eleven
  measurements it leaves out and why; 1200 dpi has a preview and no error; and
  the restored rise search costs the panel 50/60/75/173 ms per frame repaint at
  200/300/600/1200 dpi, thirteen geometry rebuilds each, with no freeze. Driven
  on screen in real windows, photographed, in
  `~/Desktop/ChromIQ-beta20-proof/combined-round-1/`.

### B8-274 · The sweep that checks every register citation could not see three of them
- blocks release: no
- status: FIXED
- found by: the combined adversary round 2 over the merged tree, 2026-09-17,
  pointed at round 1's own fix first, on the briefing's grounds that on this
  feature three rounds running have each found a fault in the round before.
- **round 1's fix itself holds, and that was checked before anything else.**
  Every `B8-NNN` written outside the register in the collision range
  (`B8-250` … `B8-272`) was read against the heading of the entry it names:
  seventeen citations, in `ui/dialogs/measurement_report_dialog.py`,
  `workflow/layout_engine/raster.py`, `docs/design/row_label_geometry.md`,
  four test files and four drivers. Every one names the entry it is about.
  The nine numbers in that range that have no entry at all are, correctly,
  cited nowhere; they are not spelt out here, because this entry is swept like
  any other and a record of a renumber that writes the dead numbers down is
  exactly the exemption that lets a real one hide.
- **what the guard could not have said.** Its sweep walked six named
  directories and two file extensions, so three citations in the tree were
  outside it, in two different shapes:
  - a folder the list does not name: `.progress/hex-build/06-fourth.md` and
    `07-fifth.md`, two tracked build notes, both citing `B8-80`;
  - a file type the list does not read: `scripts/scanner_sweep/run-sweep.sh`
    cites `B8-22` in its header comment, INSIDE a directory the list DID name,
    and was skipped for its extension alone.
  All three name entries that exist, so nothing was wrong. The point is that a
  renumber moves numbers wherever they are written, and both of the records
  this project keeps of what a renumber costs are prose files nobody thinks of
  as code.
- **what was changed:** the sweep starts at the repository root and skips only
  what is not the tree (VCS, virtualenv, caches, build output, and
  `.claude/worktrees/`, which held six leftover CHECKOUTS of this repository,
  one still carrying the register from BEFORE the merge, with the eight
  numbers the merge retired alive in it, so a sweep that walked them would
  fail on another branch's history). File types are `.py`, `.md` and `.sh`, which is what
  carries a citation today: measured over the whole tree, 1287, 1666 and 7.
- **the other three ways the guard was probed, all sound:** a reworded
  "Size = auto" heading fails loudly with a count, two matching headings fail
  loudly with both ids, and an id inside a code string or a test name is caught
  like any other, because the sweep reads text and not comments.
- evidence:
  `test_the_sweep_is_not_vacuous` now also requires the sweep to be reading
  `.progress/` and `.sh` at all, by shape rather than by file name, so either
  coverage cannot be lost quietly;
  `test_every_b8_citation_names_an_entry_that_exists` is the sweep itself.
- **mutation, proved to land, one at a time and restored:** an id in the 900s,
  which the register does not define, appended to
  `scripts/scanner_sweep/run-sweep.sh`, reds the sweep and names that file; a
  second one appended to `.progress/hex-build/06-fourth.md` reds it and names
  that one. Both were checked against the OLD sweep in the same run: it would
  have read neither file. (The ids themselves are not written here for the
  reason given above.)

### B8-275 · The "only report of a dated verification is kept" rule was decided on a snapshot, and one window out of date could break it
- blocks release: no
- status: FIXED
- found by: the combined adversary round 2, driving the seams round 1 did not
  reach, on screen, photographed in
  `~/Desktop/ChromIQ-beta20-proof/combined-round-2/`.
- **the rule.** §5 of `docs/design/measurement_report_limits.md`: a dated
  verification's last saved report stays, because every date of a run is judged
  the same way and a date whose report is gone has no recorded verdict at all.
- **the fault.** `_saved_delete_refusal` asked `_all_report_files`, a list
  filled when the window GATHERED its sources and refreshed only by
  `_reload_sources`. Two `MeasurementReportDialog` windows were opened on one
  dated verification that really did hold two saved reports of one measurement.
  The second window deleted the spare. The first was then asked to delete the
  other WITHOUT touching its selector, because a re-pick is the one action that
  re-reads the folder and a person who has already chosen their report does not
  make it. The first window still believed there was a spare: Delete stayed
  live, the refusal never fired, and the date's `reports/` folder was left
  EMPTY, under a confirmation that said *"One saved report of it is left
  afterwards"*. Photographed in `before-the-fix/` of the round-2 proof folder
  (`W3-A-on-the-last-report.png`, `W4-after-A-tried.png`); `after-the-fix/`
  holds the same four frames of the same run against the fixed code, where the
  record survives, the button greys and the reason appears.
- **NOTHING SHIPPED THAT WAY, and the reason was written down nowhere.** All
  five doors that open this window open it with `exec()`, so a person cannot
  have two of them on screen. That modality is the only thing that made the
  snapshot safe. The one-window routes were checked and none of them shortens
  the list: `Verification.archive_reports` COPIES rather than moves, and the
  live file is rewritten under its own name, so a recalculate leaves every name
  in `_all_report_files` valid.
- **what was changed:** the count is taken from the directory the delete is
  about to write in, which is the same path `_on_delete_report` builds, with
  the session list kept as the fall-back for a folder that cannot be read. And
  because the refusal can now fire on a row whose Delete is still live, the
  refused branch re-reads instead of returning in silence, so the button greys
  and the row shows the reason in the words it already had. No new message
  text: `_saved_delete_refusal` owns the only sentence there is.
- evidence:
  `test_the_rule_is_decided_on_the_folder_and_not_on_a_stale_list` gives the
  row a list one delete out of date and requires the record to survive;
  `test_the_last_report_of_a_dated_verification_is_kept` and
  `test_a_spare_on_disk_still_lets_a_report_go` hold the two ends, so the rule
  cannot be satisfied by refusing everything;
  `test_a_refused_delete_re_reads_instead_of_doing_nothing` keeps the refusal
  visible; and `test_every_door_opens_the_report_window_modally` pins the
  assumption that used to carry the whole thing.
- **mutation, proved to land, one at a time and restored:** the stale count put
  back reds the stale-list test while the other two stay green, which is why
  they are not enough alone; a bare `return` in the refusal branch reds the
  visibility test; `dlg.exec()` → `dlg.show()` in `ui/dialogs/tools_dialogs.py`
  reds the modality test and names the line.
- re-driven after the fix on the same two windows: the record survives, the
  button greys, the reason appears.

### B8-276 · OPEN, for the design authority · Deleting the only saved report of a PROFILING measurement removes that measurement from the window and the trend, and the confirmation does not say so
- blocks release: no
- status: OPEN
- **nothing is changed. This is a question, asked with what it cost.** Round 1
  raised it; round 2 measured it end to end and is not fixing it, because the
  protection it would extend is §5 of a specification that is still a DRAFT,
  `M-REPORT-DELETE` is still unapproved, and CLAUDE.md is explicit that a fault
  which contradicts a specification is reported and reviewed, not corrected on
  our own judgement.
- **what was measured**, on screen in a real window, on a copy of a two-run
  project (`delete-findings.json`, `01`–`06` in the round-2 proof folder):
  the window opened on a profiling run listed TWO measurements, 2026-05-02 and
  2026-08-11, the older of them present only because of its one saved report.
  Delete was offered on it with no note, because `_saved_delete_refusal` covers
  a dated verification and nothing else. After the delete: the report was gone
  from disk, the run list fell from "2 runs" to "1 run", the 2026-05-02 row was
  gone, and the colour-accuracy trend fell from 2 points to 1. Reopening the
  window on the same measurement gave the same one row, so the date does not
  come back.
- **and the measurement really can be the only record.** The deleted report
  described a sheet named `Demo-Full-RGB.ti3`, which is in no folder of that
  project: both `.ti3` files on disk are the 2026-08-11 measurement. A run that
  has been measured again keeps its older sheet under `old/<stamp>/` when the
  re-measure went through ChromIQ, and does not when the report came from an
  import or another chart. Either way the row, the verdict it was saved with
  and its point on every trend go, and the window offers no route back to them.
- **what the user is told**, verbatim, in a box that also says "ChromIQ cannot
  undo this": *"The measurement it describes is not touched, and no other
  report of that measurement is touched. 0 saved reports of it are left
  afterwards."* The first sentence is true of the FILE and says nothing about
  the row, the verdict or the trend point; the second is the only hint, and it
  is a count rather than a consequence.
- **the same act on a dated verification behaves differently**, and correctly:
  Delete greys out and the row says *"The only saved report of a dated
  verification is kept: its verdict is this run's record of that date."*
  (`03-verification-report-selected.png`.)
- **the question, for a tester rather than for a reader of this file:** *"In
  the Measurement Report window, Saved reports, you can delete a report. For a
  dated verification check, ChromIQ refuses to delete the last one and says
  why. For a profile run's own measurement it does not refuse: when you delete
  the last report of one, that measurement's date disappears from the list of
  runs and from the trend charts, and it does not come back. Should ChromIQ
  keep the last report of a profile run's measurement too, the way it keeps a
  check's? Or should it let you delete it, and warn you first that the date
  will leave the list and the charts?"*
- until that is answered the behaviour stays exactly as it is.

### B8-277 · What combined round 2 drove and did NOT find
- blocks release: no
- status: VERIFIED
- **an honest empty round on everything but the two entries above**, recorded
  so the next round does not pay for it again. All of it driven on screen in
  real windows and photographed; proof in
  `~/Desktop/ChromIQ-beta20-proof/combined-round-2/`.
- **the 5.9-second repaint round 1 could not reproduce is REPRODUCED and
  explained.** Round 1 recorded it as not reproduced, which was right, and also
  called it "an early repaint", which its data could not say: the driver sorts
  the times before writing them. Kept in order and repeated, it is the FIRST
  margin repaint after the first 1200 dpi Generate in a process that has
  already built 200, 300 and 600 dpi: 6085.4 ms and 6056.5 ms on two separate
  runs, with the next eleven at 182 to 233 ms. It does not return on the second
  or third pass over the same four resolutions, and a fresh process taken
  straight to 1200 dpi never shows it (max 184.7 ms). The cause is the
  process's own memory and not the layout code: that one sample took **22,287
  minor page faults against about 5,100 for every other sample in the run**,
  zero major faults, no Python collection, while resident memory went from
  2.40 GB to 4.65 GB across the Generate. A user can meet it — build charts at
  a few resolutions, end at 1200 dpi, then touch a margin box — and it costs
  about six seconds, once per session, with nothing lost.
- **the "Saved reports" pulldown on a measurement with only ONE report**, which
  is the commonest shape. The row is shown, the pulldown offers one entry, and
  choosing it re-reads every source off disk and changes nothing: not the
  document, not the run list, not the trend. It costs **56.4 ms**, not the
  2.57 s a first cut of this round reported, which was its own `pump` and was
  re-measured. The row still earns its place, because Delete lives on it and
  works. Not a fault: the degenerate case of a control that is right in general.
- **two projects in one session**: adding a second project's measurement to an
  open window gave 2 sources, 4 measurements, 4 trend points and both named in
  the list by their chart. Correct.
- **a project reopened from disk after a delete** agrees with the window that
  did the deleting.
- **a report file landing in a run's `reports/` while the window sits open** is
  not noticed until the window re-reads — a re-pick in the pulldown, or
  reopening. No rule is broken by it and nothing is lost; it is recorded here
  because it is what led to B8-275.
- **the register's own trail**, re-checked past round 1: every citation in the
  collision range names the entry it is about (B8-274), and B8-273's own
  `evidence:` line names tests that exist.
- evidence: `QT_QPA_PLATFORM=offscreen pytest -n auto`, the everyday tier,
  after this round's change set: **16013 passed, 321 skipped, 4 xfailed,
  exit 0**, in 2:19. Round 1 left it at 16007 passed; the six new ones are the
  guards named in B8-274 and B8-275.

### B8-278 · The fix for B8-275 counted files the window cannot read, and reopened the hole it closed
- blocks release: no
- status: FIXED
- found by: the combined adversary round 3, driving the delete path seven ways
  on screen on a copy of a real project, photographed in
  `~/Desktop/ChromIQ-beta20-proof/combined-round-3/`.
- **the rule is still §5** of `docs/design/measurement_report_limits.md`: a
  dated verification's last saved report stays, because a date whose report is
  gone has no recorded verdict at all.
- **the fault.** B8-275 moved the "is there a spare?" question off the
  window's snapshot and onto the folder, which was right, and asked it with a
  bare `glob("report_*.json")`. `_gather_runs` reads every such file with
  `json.loads` and SKIPS the ones that raise, so a file that is not readable
  JSON is in no row, no selector and no trend, and the glob counted it as a
  spare all the same. A dated verification holding one good report and one
  truncated one therefore came up with **Delete… live and no reason beside
  it**, the confirmation said *"0 saved reports of it are left afterwards"*,
  and the press left the date with no verdict the window can read. The
  confirmation was honest and the rule was not: the two were counting
  different things, and that disagreement is the whole diagnostic.
  `save_report` writes with `write_text`, which is not atomic, so a process
  killed mid-write leaves exactly that file, and so does a full disk.
- **what was changed:** the count uses the same test `_gather_runs` uses, and
  stops at two, because two is all the question needs to know. The folder is
  still what is asked; only the files that are not verdicts stop being
  counted. No new message text, no change to the confirmation, nothing else in
  the delete path touched.
- **and the guard that carried B8-275's safety argument was a list.**
  `test_every_door_opens_the_report_window_modally` named two files in a tuple
  and asserted the tuple had two entries in it, which pins the two doors that
  exist and says nothing about a third. A sixth door, modeless, added in
  `ui/main_window.py`, passed that test; it now fails, because the doors are
  FOUND by walking the app's own packages rather than listed.
- **the same shape in B8-274's sweep, closed the same way.** Its skip set
  matches a directory NAME anywhere in a path, so a tracked `docs/build/…`
  would have been skipped in silence, which is the hole B8-274 was widened to
  close, written into the fix instead of left out of it. The skip now has to
  prove it costs nothing: git says what is in the tree, and nothing in the
  tree may be skipped. Measured: 0 tracked files under any skipped name.
- evidence: `test_a_file_the_window_cannot_read_is_not_a_spare` (a truncated
  report, then a zero-byte one, then a readable spare so the rule cannot be
  satisfied by refusing everything);
  `test_the_doors_are_found_and_not_merely_listed`;
  `test_the_skip_list_hides_nothing_that_is_IN_the_tree`.
- **mutations, proved to land, one at a time and restored:** the bare glob put
  back reds the unreadable-file test while every other test in the file stays
  green; the stale list put back reds the stale-list test; a bare `return` in
  the refusal branch reds the visibility test; `.exec()` → `.show()` on the
  Measure tab's fourth door reds the modality test and names the line; a sixth
  modeless door in `ui/main_window.py` reds two tests, and was PROVED to pass
  the old guard first; `"docs"` added to the skip set reds the tracked-file
  test and names the files it would have stopped reading.
- re-driven after the fix, same seven presses, same window: the truncated file
  is no longer a spare, Delete greys, the whole sentence shows beside it, and
  the date keeps its verdict. Everything else is byte-for-byte what it was.

### B8-279 · What combined round 3 drove on the delete path, and what it did NOT find
- blocks release: no
- status: VERIFIED
- **the brief was two fixes and nothing else**, so nothing outside the delete
  path and the citation sweep was opened. Seven presses, each on its own fresh
  copy of a real project, each followed by LISTING THE FOLDER ON DISK rather
  than asking the window what it thought had happened
  (`scripts/drive_182_combined_round3_delete.py`, `delete-round3.json` and the
  frames in `before-the-fix/` and `after-the-fix/`):
  - **A** the last saved report of a dated verification: refused, folder
    unchanged, no confirmation asked, the reason on the row.
  - **B** one of several on one date: the spare went and only the spare, and
    the last one was then refused.
  - **C** the chosen report's file removed under the app, window open,
    selector untouched: the press asked nothing, deleted nothing, and the
    window caught up with the disk. That is B8-275's other half working, and
    it is the case a person actually reaches without two windows.
  - **D** the folder made read-only between the confirmation and the press:
    the file survives and the failure is said out loud. See the note below.
  - **E** two dates, one holding no report at all: the date that still has one
    is protected, the empty one is not resurrected.
  - **F** a delete straight after a Generate with no re-pick: the new report
    is in the list, the confirmation names the old file and the count is
    right, and exactly that file goes.
  - **G** a `report_*.json` the window cannot read beside the only one it can:
    THE FAULT. B8-278.
- **notes for the next beta, not changed here, because they are outside the
  brief and neither is a loss:**
  - a delete that fails puts the raw OS error in the box, path and errno and
    all (*"[Errno 13] Permission denied: '/var/folders/…'"*), under the title
    *"Delete this saved report?"*, which is the question rather than the
    answer. Nothing is lost and the file survives; it is the wording.
  - the confirmation's *"N saved reports of it are left afterwards"* is
    counted from `_all_report_files`, which is the snapshot B8-275 moved the
    RULE off. On a profiling measurement, where no refusal applies, a file
    removed under the app leaves that number one too high. The rule itself is
    safe, because a profiling measurement has no rule.
  - `screencapture -x -R` refuses intermittently on this machine, so a frame
    whose window-id route happens to return an unpainted buffer three times is
    lost outright: one frame of twelve, in both runs, the same one. Measured
    in `capture-probe/`: four states, `region_route` false in two of them with
    the window visible, correctly sized and on screen. The fall-back is the
    unreliable half, not the window-id route, and `capture_window` recovered
    in every probe. The missing frame is the same state as
    `capture-probe/probe-03-after-delete-capture.png`, which is kept.
- evidence: `QT_QPA_PLATFORM=offscreen pytest -n auto`, twice, exit 0 both
  times: **16016 passed, 321 skipped, 4 xfailed**, 2:13 and 2:14. Every window
  in this round was real and photographed, `QT_QPA_PLATFORM` unset in every
  driver, settings and presets sandboxed to `/tmp/chromiq-b20r3*`, and the
  owner's `custom_output_path` absent from `com.chromiq.ChromIQ` before and
  after.
---

### B8-280 · The eight CR30 upright hexagonal presets: 14.0 mm left margin, a typed label size, and no helper markers
- blocks release: no
- status: FIXED
- **the design authority's own instruction, in the comment that ruled on
  B8-265**, and it is what makes that ruling free: with these three changes the
  eight upright hexagonal charts keep the patch count and page count their
  names promise.
- **THE UNIT WAS THE TRAP, AND IT IS POINTS.** He writes *"Set Size in 'Strip
  letters and row numbers' frame to value 11.0mm"* and, a paragraph earlier
  about the same control, *"which has 11.0pt font size"*. The control is a
  POINT box (`layout_options_panel.small_pt`, converted at the recipe boundary
  by `pt_to_mm`), the recipe stores millimetres, and the shipped
  `_CR30_STRAIGHT` has carried `indicator_size_mm: 3.88` since 2026-09-12 for
  the very chart he points at as already correct
  (`CR30-Letter-396p-1page-Portrait-w11.0mm-Hexagonal-Straight`).
  `pt_to_mm(11.0) = 3.88` and `pt_to_mm(18.0) = 6.35`.
- **and his own measurement was reproduced before any file was edited.**
  Driving `CR30-Letter-780p-2pages-Portrait-w11.0mm-Hexagonal` on screen and
  typing 11.0 into that box: the MEASURED left margin goes **14.224 to 13.081
  mm**, which is his *"goes down from 14.1mm to 13.1mm"*, and the left-margin
  warning disappears. His 14.0 mm then follows: at 13.0 with the smaller label
  the chart spilled to 3 pages at 375 patches per page, and at 14.0 it is back
  to 2 pages at 390.
- what changed, all of it in `_CR30_HEX` except the two exceptions:
  `margin_left` 13.0 to **14.0**, `indicator_size_mm` auto to **3.88** (11.0 pt),
  `helper_markers` True to **False**. `_CR30_STRAIGHT` now spells
  `helper_markers: True` out, because the straight cut is applied ON TOP of the
  hexagonal one and would otherwise have lost its dashes; he asked explicitly
  that the six `-Straight` charts keep them.
  `A4-153p` and `Letter-170p` take `indicator_size_pt=18.0` on their own rows.
- **why the markers go off, which is worth keeping.** A honeycomb carries a
  comb of dashes on ONE axis only, and which one follows the turn: an upright
  comb staggers every second ROW sideways so top and bottom would point at a
  seam, leaving Sides; a turned comb staggers every second COLUMN and keeps
  top/bottom. `_CR30_BASE` asks for `helper_markers_top_bottom` and NOT
  `helper_markers_sides`, so on these eight the only axis asked for was the
  greyed one and the only axis that could print was switched off. A ticked box,
  two dead sub-options, and no dashes on the sheet, which is exactly what he
  described. It was not cosmetic either: with the markers on, the strip letters
  are held 7.0 mm from the paper edge by the markers' own reserve rather than
  by the 4.0 mm "T", and that fired a strip-letter overlap notice on five of
  the eight. Both notices are gone.
- **every one of the fourteen was LOADED, GENERATED and MEASURED** through the
  real Manual presets dropdown, before and after, with the patch and page
  counts taken off the build and the margins off the rendered TIFF rather than
  off the panel's text (`scripts/drive_182_autosize_and_hex_presets.py`; proof
  in `~/Desktop/ChromIQ-beta20-proof/autosize-and-presets/`). The six
  `-Hexagonal-Straight` charts are the control group and did not move by a
  hundredth on any measure.

  | preset | measured left, before to after | pages | patches/page | warnings |
  |---|---|---|---|---|
  | `A4-153p-1page-w18.0mm-Hexagonal` | 14.478 to 14.097 | 1 | 153 | 2 to 1 |
  | `A4-420p-1page-w11.0mm-Hexagonal` | 13.970 to 14.097 | 1 | 420 | 2 to 1 |
  | `A4-840p-2pages-w11.0mm-Hexagonal` | 13.970 to 14.097 | 2 | 420 | 3 to 1 |
  | `A4-1260p-3pages-w11.0mm-Hexagonal` | 13.970 to 14.097 | 3 | 420 | 3 to 1 |
  | `Letter-170p-1page-w16.0mm-Hexagonal` | 14.478 to 13.970 | 1 | 170 | 2 to 1 |
  | `Letter-390p-1page-w11.0mm-Hexagonal` | 14.224 to 14.097 | 1 | 390 | 3 to 1 |
  | `Letter-780p-2pages-w11.0mm-Hexagonal` | 14.224 to 14.097 | 2 | 390 | 3 to 1 |
  | `Letter-1170p-3pages-w11.0mm-Hexagonal` | 14.224 to 14.097 | 3 | 390 | 3 to 1 |

  The one warning left on every row is *"The settings stamp down the right edge
  runs over the patches"*, which fires on all twenty-six charts of this family
  including the six that were not touched. It is pre-existing, it is not part
  of this batch, and it is not caused by anything here.
- **one printed patch moved, and it is pinned rather than absorbed.**
  `Letter-170p-1page-Portrait-w16.0mm-Hexagonal` prints 16.76 mm patches where
  it printed 16.64. That chart used to ask for 13.0 mm and be given 14.382 by
  the row-label band; it now asks for 14.0 and is given 14.0, so the patch area
  is 0.38 mm wider and each of its ten columns takes a tenth of it. Its name
  was already 0.64 mm out and is now 0.76 mm out. Both figures are the design
  authority's own; flagged for him, not corrected here.
- evidence: in the CR30-built-in-presets file under `tests/`,
  `test_the_hexagonal_cut_is_exactly_these_four_fields_and_no_others`,
  `test_the_straight_cut_is_the_hexagonal_one_turned_and_six_numbers`,
  `test_the_two_low_patch_hex_charts_carry_the_larger_label`,
  `test_recipe_differs_from_the_base_only_where_allowed`,
  `test_chart_builds_with_the_pages_and_patches_its_name_promises`; and in the
  size-auto-fits-the-margin file,
  `test_the_eight_hexagonal_presets_still_print_what_their_names_promise`.

---

### B8-281 · A ticked "Print helper markers" that prints nothing now says why, in the help and not only on the dead control
- blocks release: no
- status: FIXED
- reported by a tester, 2026-09-16, on the CR30 hexagonal presets: *"I notice
  that the helper markers are enabled, but the 'Show markers for' 'top/bottom'
  is greyed out and not selectable, but they should have been ON and showing on
  the preview (but are not showing on the preview). ... It is not clear why they
  are unavailable and help text does not say the conditions where they are not
  available."*
- the reason DID exist, on the tooltip of the greyed control, and that is the
  one place a reader in his position will not look: a control he cannot click
  is a control he has stopped asking about. He asks for it *"also in the help
  text"*, which is the ⓘ on "Print helper markers" itself.
- the ⓘ gains a paragraph saying that on hexagonal patches only one of the two
  pairs of edges can carry dashes, that **which pair depends on the way the
  honeycomb sits**, that every second row or column is shifted half a patch so
  dashes along the edges it is shifted against would point at a seam rather
  than a patch, that the unusable pair is greyed out, and that unticking the
  pair that is left leaves the box ticked and printing nothing.
- **it must not name one pair as the unavailable one.** Which pair survives
  follows the turn, and the panel itself got that wrong for nine rounds,
  greying the comb that prints and offering the one that does nothing. A help
  text that named a fixed pair would be false on half the honeycombs in the app.
- **its own `tr()` key, not an edit to the paragraph above it.** Folding it in
  changes that string's key and turns all thirteen shipped translations of it
  stale in one edit, which is the trap B8-270 records paying for.
- evidence: in the help-says-why-the-marker-edges-grey-out file under `tests/`,
  `test_the_help_on_the_master_box_explains_the_greying`,
  `test_the_help_says_which_pair_survives_rather_than_naming_one`,
  `test_the_help_warns_that_a_ticked_box_can_print_nothing`,
  `test_the_greyed_control_still_carries_its_own_reason`,
  `test_the_explanation_is_its_own_translatable_string`.

---

### B8-282 · The two label frames are renamed to the positions they cover, because the glyphs are a setting
- blocks release: no
- status: FIXED
- the design authority, 2026-09-16, and repeated in the comment of the same
  evening as *"which should be renamed, as stated in earlier posts"*: *"the
  'Strip letters and row numbers' Frame is named inaccurately, because a user
  may change the strip and patch pattern to be letters for rows and numbers for
  strip. Thus, a better name for the frame would be 'Strip and row indicators'
  and, the frame 'Strip letters only' could be named 'Strip indicators only'.
  Any reference to these frames in help text should also be renamed."*
- he is right and it is a correctness fault rather than a preference: the strip
  and patch patterns sit in the same panel, so a chart set to numbers across the
  top was described by a frame titled "Strip letters". The two POSITIONS cannot
  be swapped by any setting.
- **"any reference in help text" was four strings, and a grep found three.**
  The fourth is built by concatenation and splits the phrase mid-way across two
  source lines (`"“Strip "` then `"letters only” by about …"`), so it is
  invisible to a literal search and was caught only by running the AST
  extractor (`scripts/i18n_extract.py`) and asking which live keys still
  carried the old name. A rename of a user-facing phrase should be checked that
  way and not with grep.
- **seven keys moved in all thirteen catalogues**: the two titles, the new
  helper-marker paragraph from B8-281, and four messages whose text quotes a
  frame name. The four are RENAMES, so each language's shipped translation was
  carried across with the frame name swapped rather than retranslated, and the
  six retired keys were deleted. Every catalogue's identical-to-key count lands
  back exactly on its recorded budget in `tests/test_i18n.py` (de 124, es 372,
  fr 394, it 383, ja 358, nl 399, no 384, pl 376, pt 374, ru 347, sv 385,
  zh_CN 352). **No budget was raised**; a catalogue that shipped one of these
  four in English keeps it in English under the new key, which is the same
  state it was in.
- evidence: in the label-frame-says-which-control-reaches-which-label file
  under `tests/`, `test_the_titles_say_the_reach_in_the_readers_words`; and in
  the i18n file, `test_catalog_is_complete`, `test_catalog_has_no_stale_keys`,
  `test_untranslated_values_do_not_creep_in_unseen`,
  `test_short_labels_stay_compact`.

---

### B8-283 · Every built-in preset regenerated and measured · no preset warns about anything of its own
- blocks release: no
- status: VERIFIED
- asked for by the design authority, 2026-09-16: *"all Presets should be
  individually regenerated, (except those saying 'by Pharmacist'), so that
  changes made in features are incorporated. However, if any preset have
  warnings, these must be listed in a bullet-list with their exact names, so
  that I can report back what settings to modify to get rid of the warning
  messages in the presets."*
- **149 presets**, every built-in except the 11 whose names say "by
  Pharmacist", each selected from the real Presets dropdown and then
  GENERATED, with the panel read back afterwards
  (`scripts/drive_182_survey_every_builtin_preset.py`). **All 149 generated,
  none failed, no crashes.** Taken AFTER B8-265 and B8-280, so the numbers are
  the ones a beta-20 build shows.
- **THE ANSWER IS THAT NO PRESET NEEDS CHANGING.** With "Stamp settings down
  the right edge" off, **all 149 come up clean**: zero warnings, and a green
  "Margins: OK" on every one except the fifteen in B8-284.
- **With that box as the app ships it, 96 of the 149 warn, and it is the same
  sentence every time** -- *"The settings stamp down the right edge runs over
  the patches"*. There is no second warning anywhere in the set.
- the box is **not a preset field**. It is `chart_stamp_commands`, an
  application setting with no stored default, so `tab_chart` ticks it on a
  fresh install and no layout recipe can clear it: the recipe's own
  `stamp_command` is a different control, the summary along the BOTTOM. This
  was already known in the narrow (the note at `tab_chart.py`'s chart-note
  branch records the same fact, found by the adversary round of 2026-09-13, and
  records that two "6 GREEN" claims that morning held only because the owner's
  own preferences carry `chart_stamp_commands = 0`); what is new is the
  **scale**, which nobody had measured: it is 96 of 149, and it is the only
  warning the whole built-in set produces.
- **the warning is TRUE**, which is why this is a question about a default and
  not about a message: the line really is printed and it really does land on
  the patches.
- so what he can act on is **one decision about one default**, not 96 preset
  edits. The bullet list he asked for, in his format and with the exact names,
  is `~/Desktop/ChromIQ-beta20-proof/autosize-and-presets/survey/WARNINGS-BULLET-LIST.md`,
  with both passes and the per-preset JSON beside it.
- evidence: **what was run, and what came back.** Twice, once per stamp state:

  ```
  CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… python \
      scripts/drive_182_survey_every_builtin_preset.py <out>            # stamp ON
  CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… python \
      scripts/drive_182_survey_every_builtin_preset.py <out> --no-stamp # stamp OFF
  ```

  | | stamp ON (as shipped) | stamp OFF |
  |---|---|---|
  | generated | **149 PASS** / 149 | **149 PASS** / 149 |
  | showed a warning | 96 | 0 |
  | showed "Margins: OK" | 38 | 134 |
  | showed nothing at all | 15 | 15 |
  | crashes | 0 | 0 |

  and the suite after this round's change set:
  `QT_QPA_PLATFORM=offscreen pytest -n auto` -> **16032 passed**, 334 skipped,
  4 xfailed, in 2:34, with the one red being
  `test_the_sweep_is_not_vacuous`, an artefact of running inside
  `.claude/worktrees/` (its `_SKIP_DIRS` contains `.claude`, so the sweep skips
  the whole tree; with that one entry removed it finds 964 citations, all
  naming real entries).
  The survey itself is a driver, so its result is a measurement rather than an
  invariant; the invariant it rests on -- that a preset's warnings come from
  its own recipe and not from the app's defaults -- is pinned in the CR30 file
  by
  `test_chart_builds_with_the_pages_and_patches_its_name_promises` and in the
  says-nothing file by
  `test_an_overlap_warning_is_shown_and_explains_its_own_silence`.

---

### B8-284 · OPEN, for the design authority · Fifteen presets show no message at all, and the reason is a warning nobody can see
- blocks release: no
- status: OPEN
- **the behaviour is diagnosed and measured; what to do about it is a ruling,
  so nothing has been changed.** One question for the design authority, at the
  end.
- he asked, 2026-09-16: *"I mentioned before that some presets when loaded are
  missing the 'Margins: OK' message, and instead have no message at all. Why is
  that, for what kind of circumstances does this happen, and is that a bug? Can
  it be fixed, so that all presets loaded end up showing the 'Margins: OK'
  message?"*
- **WHICH FIFTEEN.** Driving all 149 built-in presets found exactly 15 in that
  state, in both survey passes, and they are not scattered: they are the **A4
  and A3 i1Pro 3 Plus** charts. Their nine **Letter** siblings, same author,
  same recipe shape, margins within a tenth of a millimetre, show the green
  line.
- **WHY.** `MarginInspectorPanel._update_status` blanks AND HIDES its status
  label whenever `text_warnings` is non-empty. `text_warnings` is the list that
  goes to the panel's ⓘ. So the three states are:

  | what is live | what the surface shows |
  |---|---|
  | a margin violation, or an overlap warning | a red paragraph naming it |
  | only an ⓘ note | **nothing whatever** |
  | neither | a green "Margins: OK" |

- **WHAT PUTS THESE FIFTEEN IN THE MIDDLE ROW**, measured on one silent chart
  and one talking one (`scripts/drive_182_why_some_presets_say_nothing.py`):

  | | `A4-84p-1page-Portrait-w25.0mm` | `Letter-84p-1page-Portrait-w25.0mm` |
  |---|---|---|
  | strip length | **236.98 mm** | 219.20 mm |
  | i1Pro 3 Plus ruler | 220 mm | 220 mm |
  | `_ruler_over_mm` | **220.0** | None |
  | text notes | 1 | 0 |
  | overlap warnings | 0 | 0 |
  | status line | **"" , hidden** | "Margins: OK" |

  The A4 sheet is 17.6 mm taller than Letter, so its strip runs past the ruler
  by 17 mm; Letter's clears it by 0.8. That single note is the whole difference.
- **AND THIS IS WORSE THAN A MISSING GREEN LINE.** The note that causes the
  silence says *"Strip length 237 mm exceeds the 220 mm instrument ruler, the
  strip may not fit your jig"* -- which is the most useful thing the panel
  could tell the owner of that chart, and it is reachable only by hovering an
  ⓘ that carries no mark of any kind (`TooltipButton.set_live_note` refreshes
  the hover tip and nothing else). Photographed: the frame lists all four
  margins and a strip length of 237.0 mm, and then there is no verdict at all.
- **IT IS A BUG, AND THE REASON IS IN ITS OWN COMMENT.** The suppression
  justifies itself with *"a green headline over a red notice reads as approval
  of the thing the notice is about"*. That describes an OVERLAP warning, which
  is red and on the surface, and overlap warnings are already handled by the
  branch above. It is keyed on `text_warnings`, which never reach the surface,
  so the rule is guarding against a contradiction that cannot occur and is
  paying for it with total silence. A reader cannot tell "checked and fine"
  from "not checked".
- **why it is still not simply fixed.** Restoring the green line alone would
  be true of the margins and would actively reassure the owner of a chart that
  does not fit his jig. That trade is a wording decision, and this file's rule
  is that a fault which contradicts an agreed behaviour is reported and
  approved, not corrected on our own judgement. There is also a THIRD, separate
  and deliberate route to silence: Preferences' "warn me about margin
  violations", off, hides the label before anything else is looked at. That one
  is the user asking for silence and is not part of this.
- **the question for him**, in what a user sees: *"On fifteen of the built-in
  charts the box under the preview lists the margins and then says nothing at
  all, where other charts say 'Margins: OK' in green. The margins on those
  fifteen are fine. The reason the line is missing is that the chart has a
  different problem, which is that its strip of patches is longer than your
  instrument's ruler and may not fit the jig, and that sentence is only visible
  if you hover the ⓘ. Would you rather (a) the green 'Margins: OK' appeared
  anyway, since the margins really are fine, (b) the strip-length sentence was
  printed in the box instead, where the red warnings go, or (c) both, with the
  green line and the sentence under it?"*
- our recommendation is **(c)**: the margins verdict is true and belongs on
  the surface, and a warning that changes whether the chart can be measured at
  all should not depend on a hover.
- evidence: in the preset-that-says-nothing file under `tests/`,
  `test_with_nothing_live_the_panel_says_margins_are_ok`,
  `test_an_i_note_alone_blanks_the_verdict_and_shows_nothing`,
  `test_an_overlap_warning_is_shown_and_explains_its_own_silence`,
  `test_turning_the_margin_notice_off_is_a_SECOND_way_to_get_silence`,
  `test_the_rule_is_keyed_on_a_list_that_never_reaches_the_surface`. They pin
  the FAULT, not a design: when he rules, that file is rewritten rather than
  deleted.

### B8-290 · FIXED · A cube corner the report calls missing borrowed a patch's colour, its number and its ΔE00

- blocks release: no
- status: FIXED
- fixed in this round, with a guard and seven proved mutations.
- reported by the design authority on a demo project, 2026-09-17, and
  reproduced from that project's own saved report before anything was changed.
  His words: *"The missing cube colors are marked as missing, but a color patch
  and a measurement deltaE is still provided. ... The red and blue marked with
  (missing) have gray color. the Cyan missing is green."*
- **WHAT THE READER SAW.** The Report Scope said, correctly, that both dated
  verifications are *missing Red, Blue, Cyan*. The Cube corners table in the
  same document then printed, for those three, a colour swatch under Expected,
  a colour swatch under Measured, a patch number and a ΔE00:

  | corner | patch it named | measured swatch | ΔE00 |
  |---|---|---|---|
  | Red **(missing)** | 14 | `#4f5b69`, a neutral grey | **2.46** |
  | Blue **(missing)** | **14, the same patch** | `#4f5b69`, the same grey | **2.46** |
  | Cyan **(missing)** | 20 | `#2ce387`, a green | 1.10 |

- **THE MECHANISM.** `measurement_report.build_report` finds each corner by
  taking the NEAREST patch in device RGB and then asks whether that patch is
  really at the corner (`CORNER_PRESENT_TOL`, 12 device units). When it is not,
  `present` is False and the Report Scope warns -- but `loc`, `rgb`, `lab`,
  `hex`, `expected_lab`, `expected_hex` and `de` on that entry all still
  describe the stand-in, and they are written into the saved report. Red's
  target is device (100, 0, 0) and Blue's (0, 0, 100); on a 20-patch
  verification chart the nearest patch to both is the same 33.3 % grey, which
  is why one patch answered for two inks with one number.
- **THREE SURFACES PRINTED IT, NOT ONE**, and only the first was reported:
  1. the per-run **Cube corners** table (`_run_detail_html`), his;
  2. the side-by-side **comparison** table (`_comparison_table_html`'s
     `corner_de`), which carries the same ΔE00 and has no "(missing)" mark
     anywhere to warn with, so the borrowed number is completely unmarked;
  3. the **trend** chart (`measurement_report.report_trend`), which plotted it
     as that ink's drift over time. On this project Red and Blue would have
     drawn the SAME line from the SAME patch.
- **WHAT WAS NEVER AFFECTED, AND IT DECIDED THE SIZE OF THE FIX.**
  `measurement_report.row_values` already gates every corner on `present`, so
  `substrate_de00_max`, `solids_de00_max` and `cmy_solids_dhab_max` never took
  a number from a stand-in, and no verdict word was ever wrong. Measured, not
  assumed: `test_no_judged_row_ever_took_a_number_from_a_stand_in`. That is
  what makes this a reporting fault fixable in the report window rather than a
  judging fault.
- **THE REMEDY IS HIS OWN**: *"When the colors are missing, the expected should
  still show the ideal cube colour, the measured and the DeltaE columns could
  show only a dash '-' to indicate it is not present or measured. The
  '(missing)' in first column is good as indication."* So a missing row now
  shows the corner's IDEAL ink under Expected (`_corner_ideal_hex`, derived
  from `CUBE_CORNERS` so the two tables cannot drift apart), and `_fmt(None)`'s
  dash for Measured and for ΔE00.
- **ONE STEP PAST HIS WORDS, AND IT IS SAID HERE SO HE CAN OVERRULE IT.** The
  patch NUMBER goes too. "Red (missing) (14)" is a claim about the chart, not
  only about a colour, and it is the claim that made one patch visibly answer
  for two corners. Leaving it would have left the row still naming a patch it
  does not have.
- **FIXED AT THE READING END, DELIBERATELY.** The stand-in's fields are already
  written into every report JSON on disk. Filtering in the builder would repair
  only reports written from now on; filtering in the three readers repairs
  every report a user already has. An entry with no `present` key at all is an
  older ChromIQ's and is still drawn in full, so nothing a user has goes blank.
- **NOT changed, and recorded as a separate observation:** the Customer report
  type's own corner block (`_swatch_table_html`, reached from `_one_page_html`)
  already filtered to `present` corners, so it silently OMITS the missing three
  rather than naming them. That is a different report for a different reader
  and the Report Scope warning still covers it, but whether a customer-facing
  page should say "three of the eight corners are not on this chart" is a
  wording decision and his, not ours.
- measured on screen: `scripts/adv_b20r4_cube_corners_on_screen.py`, driving
  his project (copied, never opened in place) through the real Measurement
  Report window with "Judged against" on Custom ISO 12647-7 and "Show detailed
  data for each run" ticked. Photograph and the rendered document in
  `~/Desktop/ChromIQ-beta20-proof/combined-round-4/cube-corners-after/`.
- **and the driver's own first answer was wrong twice, which is worth more than
  the fix.** Run 1 read a document that had no Cube corners table at all,
  because the table lives in the OPT-IN "Show detailed data for each run"
  section; run 2 read the right document with a parser written against the
  string the dialog builds rather than the markup `QTextBrowser.toHtml`
  returns, and `<td>` with no attributes matches nothing there. Both times the
  driver printed an empty table and every "still carries a number" check came
  back clean. **A probe that finds nothing looks exactly like a fault that is
  fixed**, so the parser now asserts it found eight rows by printing them.
- evidence: in the missing-cube-corner file under `tests/`,
  `test_a_missing_corner_shows_the_ideal_colour_and_no_measurement`,
  `test_a_missing_corner_names_no_patch_number`,
  `test_a_present_corner_keeps_its_swatches_and_its_delta_e`,
  `test_the_ideal_swatch_follows_the_cube_corner_table`,
  `test_the_comparison_table_dashes_a_missing_corner`,
  `test_the_comparison_table_keeps_a_present_corner`,
  `test_the_trend_never_plots_a_corner_the_chart_has_no_patch_at`,
  `test_the_trend_keeps_a_report_whose_corners_are_all_present`,
  `test_an_older_report_without_the_present_flag_is_not_silently_dropped`,
  `test_an_older_report_without_the_present_flag_still_draws_its_swatches`,
  `test_no_judged_row_ever_took_a_number_from_a_stand_in`.

### B8-291 · The automatic row-label size walk attacked across 11,088 geometries and twelve on-screen builds · nothing found

- blocks release: no
- status: VERIFIED
- nothing to fix. Recorded because an empty result is only worth anything if it
  says what was attacked and how big it was.
- the subject is B8-265's §R8 walk, shipped in this beta: when Size is "auto"
  and the row-label band would force the left margin above the typed one, the
  size is walked down the half-point grid to 7 pt and the first size that fits
  is recorded on `Geom.row_label_size_mm`. It changes a size the user did not
  type, inside a loop, and its own author found a stateful fault in it that
  only a guard could see, so it was attacked first and hardest.
- **THE INVARIANT SWEEP, 11,088 CASES.** Every combination of 7 paper/grid
  pairs x {square, pointy-top hexagon, flat-top hexagon} x 11 left margins from
  6.0 to 22.0 mm x {auto, 11.0 pt, 18.0 pt} x 4 patch-area alignments x
  {markers on, markers off} x {row indicators forced on, left untouched}, built
  through the real `_CR30_BASE` recipe. The walk fired in **1,592** of them.
  Six invariants on every case, all clean:
  - the band reserved (`rlwi`) equals the band the size actually drawn needs;
  - `floor + rlwi + 1.0` fits inside `margin_l`;
  - the margin is never LOWERED below the typed one;
  - the drawn size never exceeds the row-pitch cap `ROW_LABEL_PITCH_FRAC`;
  - applying the geometry a SECOND and a THIRD time changes neither the margin,
    the band nor the settled size;
  - no case raised.
- **THE SECOND BUILD, IN THE APP, TWELVE TIMES.** The guard proves
  `apply_row_label_geometry` is idempotent; it cannot prove the app is. So
  `scripts/adv_b20r4_autosize_on_screen.py` loads a preset in a real window,
  types a margin and a size, presses **Generate**, measures the rendered TIFF,
  presses **Generate again** and measures the second one. **All twelve cases
  produced a byte-identical sheet** (SHA-256 of the whole raster), across both
  hexagon cuts, square patches, one/two/three page charts, A4 and Letter.
- **WHAT THE WALK DOES, MEASURED OFF THE PAPER** rather than off the panel, on
  `CR30-A4-420p-1page-Portrait-w11.0mm-Hexagonal`:

  | Size box | left margin asked | margin realised | size drawn | row-label glyph ink |
  |---|---|---|---|---|
  | auto | 13.0 mm | **13.0 mm** | 16.0 pt | 4.191 mm |
  | auto | 11.0 mm | **11.0 mm** | 11.5 pt | 2.921 mm |
  | auto | 26.0 mm | 26.0 mm | 17.54 pt, no walk | 4.699 mm |
  | **19.0 typed** | 13.0 mm | **14.08 mm, raised** | 18.99 pt | 4.953 mm |
  | 7.0 typed | 13.0 mm | 13.0 mm | 7.00 pt | 1.778 mm |

  The typed row is §R1.5 behaving exactly as before, with its honest notice
  *"The left margin is below what the row indicators need, so it was widened
  from 13.0 mm to 14.1 mm to fit them"*. A typed size is never touched.
- **THE FLOOR HOLDS.** At a 9.0 mm left margin on two different charts the walk
  stops at 7.0 pt, which is `AUTO_SHRINK_FLOOR_PT`, and the margin stays where
  it was asked for.
- **AND NO BUILT-IN PRESET TAKES THE NEW BEHAVIOUR AT ALL.** All 149 built-ins
  were built twice, once with the walk live and once with its ladder stubbed to
  the pre-fix behaviour: **0 of 147 measurable presets differ**, because the
  eight the walk was reported on were given a typed size in the same change and
  a typed size does not walk. The walk's cost is bounded too: measured over all
  147, the worst extra time is **+22 ms** on the 10,290-patch scanner chart,
  the one previously reported as slow to load.
- **"OF 147 BUILT-IN PRESETS EXACTLY THESE EIGHT CHANGED GEOMETRY" IS TRUE**,
  and was tested rather than believed. Every preset's whole `LayoutRecipe` was
  dumped from this tree and from the tree before the change and compared field
  by field: **exactly 8 differ**, all of them the upright `-Hexagonal` ones,
  each by the same three fields (`margin_left` 13.0 to 14.0,
  `indicator_size_mm` 0.0 to 3.88 or 6.35, `helper_markers` True to False). The
  six `-Hexagonal-Straight` presets did not move, and neither did the other
  133. (The only other differences were `clip_image_path`, which is an absolute
  path and therefore names the checkout, not the recipe.)
- **ALL FOURTEEN HEXAGONAL PRESETS STILL DESCRIBE THEIR SHEET**, loaded through
  the real dropdown and generated in a real window: every one of the fourteen
  produced exactly the patch count and the page count its name promises
  (153/1, 420/1, 450/1, 840/2, 900/2, 1260/3, 1350/3, 170/1, 390/1, 396/1,
  780/2, 792/2, 1170/3, 1188/3), the eight at a realised left margin of 14.0 mm
  and the six straight ones unmoved at 11.0 mm. Zero crashes through the app's
  own `sys.excepthook`, fourteen photographs.
- proof: `~/Desktop/ChromIQ-beta20-proof/combined-round-4/` --
  `autosize-on-screen/`, `presets-asshipped/`.
- **the commands, so this can be re-run.** On screen, with
  `CHROMIQ_SETTINGS_FILE` and `CHROMIQ_PRESETS_DIR` both sandboxed and
  `QT_QPA_PLATFORM` unset:
  `python scripts/adv_b20r4_autosize_on_screen.py <out>` (12 cases, 24 builds,
  12 photographs, 0 crashes) and
  `python scripts/drive_182_autosize_and_hex_presets.py <out>` (14 presets, 14
  photographs, 0 crashes). Offscreen, as the suite:
  `QT_QPA_PLATFORM=offscreen pytest -n auto`, which came back **16062 passed**,
  321 skipped, 4 xfailed, exit 0, twice.
- evidence: the existing size-auto and CR30-built-in-preset files under
  `tests/` already pin what this round re-measured; nothing new was needed,
  which is the finding. `QT_QPA_PLATFORM=offscreen pytest -n auto` came back
  **16062 passed**, 321 skipped, 4 xfailed, exit 0, twice, with the two
  on-screen drivers named above contributing 0 crashes over 38 builds.

### B8-292 · OPEN, not swept · A translated help string can quote a control by a word that language does not use for it

- blocks release: no
- status: OPEN
- measured and left alone on purpose, twice over: it is not a beta-20
  regression, and this project's rule is that translation work happens before a
  final and not during a beta.
- **THE GUARD THAT EXISTS CHECKS ONE DIRECTION ONLY.**
  `tests/test_a_quoted_control_names_the_control_the_reader_has` catches a
  translation that kept the ENGLISH name of a control the language renames.
  It cannot see the other half: a translation that invents its OWN word for the
  control, different from the word on the control itself. The quotation is not
  English, so it passes.
- **AN EXAMPLE A USER COULD ACT ON.** The clip-border notice tells a Russian
  reader to turn off «Стороны» under «Вспомогательных метках линейки». The
  checkbox on screen reads **«Бока (вертикаль)»** and the frame
  «Вспомогательные метки линейки». German's limit-set help says
  „Grenzwerte dieses **Durchgangs** entsperren“ where the checkbox reads
  „Grenzwerte dieses **Durchlaufs** entsperren“. Italian's help quotes „Pinza“
  for the control that reads „Fermaglio“, Swedish „Klämma“ for „Klämkant“.
- **THE SIZE, SO NOBODY RE-MEASURES IT.** A sweep of every curly-quoted,
  capitalised phrase in an English catalogue key that resolves to a real
  control, checked in all twelve catalogues against that language's own label,
  raises **184** candidates: de 32, ru 29, nl 21, sv 19, pl 20, fr 17, it 14,
  pt 12, no 10, es 9, zh_CN 1, ja 0. A large share of those are false alarms of
  the detector rather than of the app -- a grammatical inflection (Polish
  „Zacisku“ for „Zacisk“ is correct), a string that quotes several controls
  where only one had to match, a quotation in the language's own marks that the
  curly-quote regex does not see (ja and zh_CN use 「」). **The real count is
  not 184 and is not known**; establishing it needs a reader of each language,
  which is exactly what the pre-final translation pass is for.
- what to do with it: fold it into the pre-release translation pass as a
  worklist, and at the same time widen
  `test_a_quoted_control_names_the_control_the_reader_has` to the second
  direction so the next rename cannot open it again.
- the beta-20 rename itself is clean. "Strip letters and row numbers" and
  "Strip letters only" became "Strip and row indicators" and "Strip indicators
  only"; all twelve catalogues carry **0** keys with the old phrase and 6 with
  the new one, no catalogue mentions the old names in a key or a value, the two
  frame titles are translated in all twelve, and the one affected string that
  falls back to English in eleven languages fell back in the same eleven
  BEFORE the rename, so nothing was lost. The only surviving mentions of the
  old words in the tree are source comments and a stale test docstring.

### B8-293 · The saved-report selector and the delete rule, re-driven on a project from outside this repo · nothing found

- blocks release: no
- status: VERIFIED
- the delete rule has been repaired three times in two rounds, so it was driven
  again, this time on a demo project that arrived as a zip rather than from a
  fixture: one run, two dated verifications, **two readable reports on each**,
  and an `old/` archive beside both. That last part is the shape the glob and
  the window's own snapshot each have to agree about.
- **THE SELECTOR.** Four entries for four saved reports, and each of the four
  picks stayed picked and landed on its own report: rows 0 and 1 on the
  2026-12-15 date's two files, rows 2 and 3 on the 2026-12-01 date's two. Four
  distinct answers, no snap back to the top, which is the QVariant-compare
  fault staying fixed.
- **THE RULE.** With two readable reports on the subject date, Delete was live
  and no reason was shown; it removed one, and the confirmation's *"One saved
  report of it is left afterwards"* matched what the folder then held. With one
  left, Delete went grey with the sentence beside it, and pressing the handler
  anyway removed nothing.
- **THE ARCHIVE DOES NOT COUNT AS A SPARE.** Both dates keep a copy under
  `reports/old/<timestamp>/`, and neither was read as the second report that
  would have let the last live one go. Both archives were untouched by every
  press.
- **and this driver was wrong twice before it was right**, which is the part
  worth keeping. It first watched ONE date's folder while the window's selector
  was on the OTHER, and reported `removed []` after a delete that had really
  taken a file out. It then read `self._report["_report_file"]`, a BARE
  FILENAME, and both dates hold a `report_2026-09-17_03-18-40.json` because
  both were regenerated in the same second: two different picks printed one
  name and looked like a selector that ignores the reader. The identity is the
  date folder AND the file, which is what `_run_key` uses, and a pick lands in
  `_chosen_reports` keyed by run, not on `self._report`, which stays the
  measurement the window was opened on.
- evidence: `scripts/adv_b20r4_saved_reports_and_delete.py`, photographs and
  `result.json` in
  `~/Desktop/ChromIQ-beta20-proof/combined-round-4/saved-reports-delete/`.
  The behaviour is pinned by the existing saved-report and delete-rule files
  under `tests/`; `QT_QPA_PLATFORM=offscreen pytest -n auto` came back
  **16062 passed**, 321 skipped, 4 xfailed, exit 0, and this driver added 0
  crashes through the app's own `sys.excepthook`.
### B8-285 · A project from before the folder redesign is really migrated · and Check & Refine shows the run it is on
- blocks release: yes
- status: VERIFIED
- the migration is what blocks; the other three items in here are smaller and
  would not have held a release on their own.
- reported by a tester, 2026-09-17, on three of his own projects from
  February 2026: *"Loading any of the two older projects does not convert them
  into new project folder structure, and files are not moved to correct place.
  I did try several times. First time I tried, I got the message that the
  project loaded was made with an older ChromIQ and that it would be converted
  to new folder structure. That did not happen. No folders were created. The
  second and third time I tried, then I no longer got a message ... and nothing
  was moved or reorganised."*

**THE SECOND HALF OF THAT SENTENCE IS THE DIAGNOSIS, AND IT IS ONE FAULT, NOT
TWO.** `_migrate_v1_to_v2` walks `runs/runN` and tidies what is inside each run
folder. A pre-redesign project has no `runs/` at all, so the loop found nothing
to do, stamped `schema_version` to current, rewrote the folder guide and logged
"Migration to v2 complete". The next load read that stamp, concluded correctly
that there was nothing to do, and said nothing. **The announcement and the
silence are the same bug seen twice.**

- **it passed every test because the fixture is not the layout.**
  `tests/golden/project_v1`, which the whole v1→v2 matrix runs against,
  ALREADY HAS `runs/` - a comment in `peek_project` even asserts that "v1 HAD
  `runs/`" and cites `test_legacy_migration.py` for it. That is true of the
  fixture and false of the app's own history: `runs/` arrived with the folder
  redesign (`c1fe7a0b`, 2026-05-27) and his projects are from February. **No
  test in the suite held an example of the layout that actually shipped.**
- **measured on his own files**, copied out of the zips, never opened in place:
  all three are flat, and one (the 900-patch project) carries a `project.json`
  written 2026-07-19 saying `schema_version: 2`, `runs: ["run1"]`, **with no
  `runs/` folder anywhere**. That is the state the broken migration leaves, and
  it is why gating the repair on the schema number could never have fixed it.
- **worse than reported, and nobody had seen it.** `peek_project` answered
  `holds_anything = False` for all three: a project holding a chart, a
  measurement and a profile read as EMPTY, so the "this project already exists"
  guard never fired and a build could have landed on top of them in silence.
- **the fix asks the DISK, never the manifest.** `migrate_flat_project` moves
  the chain (`<stem>` / `<stem>_NN`, the same predicate the old migration uses
  to decide what must never move) into `runs/<current_run>`, and runs on every
  load regardless of schema, so it also repairs projects the broken version has
  already stamped. Same-volume `os.replace`, so no file is ever half written;
  it refuses outright when the run holds a chart of its own or any destination
  exists, and rolls back what it moved if a move fails. **It returns 0 or it
  finishes: there is no third outcome, and 0 means the folder is exactly as it
  was found.** Files that are not the chain, including the user's own, are not
  touched; `<root>/reports/` is left where it is because a project-level
  reports folder is correct in v2 (`ui/file_guide.py` says so).
- **driven on screen**, real window, photographed with `capture_window`:
  `scripts/drive_pre_runs_migration.py`, proof in
  `~/Desktop/ChromIQ-beta20-proof/migration/`. Before: 14 files loose, no
  `runs/`. After: `runs/run1/` holding the `.ti1 .ti2 .ti3 .icc` and all five
  page TIFFs, and Check & Refine arriving with both fields already filled.
- evidence: the command, and what came back:
  `QT_QPA_PLATFORM=offscreen pytest -n auto` gave
  **16071 passed**, 334 skipped, 4 xfailed, against a baseline at `4b94058d`
  of 16036 passed. The single failure in BOTH is
  `test_every_register_citation_names_a_real_entry::test_the_sweep_is_not_vacuous`,
  which skips `.claude` and so counts zero citations from inside a worktree
  under `.claude/worktrees/`: environmental, identical before and after. Logs
  in `~/Desktop/ChromIQ-beta20-proof/migration/` as `suite-after.txt` and
  `suite-baseline-4b94058d.txt`. The migration's own guards are
  `test_a_pre_runs_project_moves_its_chain_into_run1`,
  `test_the_migration_keeps_every_byte`,
  `test_files_that_are_not_the_chain_are_left_alone`,
  `test_a_project_already_stamped_as_current_is_still_repaired`,
  `test_a_schema_1_project_is_migrated_through_load`,
  `test_a_refused_migration_changes_nothing_at_all`,
  `test_a_measurement_is_never_merged_into_a_run_with_a_DIFFERENT_chart`,
  `test_a_refusal_does_not_stamp_the_manifest`,
  `test_opening_twice_moves_nothing_the_second_time`,
  `test_a_laid_out_project_has_nothing_loose_to_find`,
  `test_a_pre_runs_project_does_not_read_as_empty`,
  `test_peeking_never_moves_anything`.

**THE STALE 3D PLOT.** *"the Check & Refine tab was showing the Gamut 3D plot
made on a previously loaded project."* `_reset_results` set all eight result
fields to None and never touched the web view, so the panel believed it held
nothing while displaying the last project's shape. It now returns the view to
its own placeholder, and a clear also drops the comparison profile B, which
belongs to the project A came from.
- evidence: `test_clearing_the_gamut_panel_blanks_the_shape_on_screen`,
  `test_clearing_the_panel_also_drops_the_comparison_profile`,
  `test_showing_a_profile_keeps_the_comparison_the_user_chose`.

**CHECK & REFINE NOW FOLLOWS THE BAR.** *"even though the profile run is set to
run1 and its folder has all files ... The ti3 and the icc file is not
automatically loaded."* The tab took the shared controller and deliberately did
not subscribe to it; the note said a `changed` connection "would be a new
behaviour nobody has asked for", resting on a challenge round that injected a
controller and saw zero `changed` signals. That was a fact about the harness.
It now mirrors `TabProfile._on_target_changed`: it only OFFERS what is on disk
for the selected run, never broadcasts (that is what can raise an import
window), and never pops the "Profile Not Found" modal at somebody who merely
opened a project.
- **a challenge round on this change found one more**: `resolve_run` answers
  with the RUN's profiling measurement for a Calibration or Verification target
  too, whose measurements live in `cal/` and in a dated folder. Build Profile's
  own follow guards only the second; this one guards both, because offering the
  wrong file is worse than offering none.
- evidence: `test_check_and_refine_loads_the_run_it_is_pointed_at`,
  `test_it_does_not_empty_itself_on_a_run_with_no_measurement`,
  `test_following_the_bar_never_asks_about_a_missing_profile`,
  `test_following_the_bar_tells_no_other_tab`,
  `test_it_offers_nothing_for_a_calibration_or_verification_target`.

**THE TOOLTIP, WRITTEN FROM THE APP THIS TIME.** The design authority's edited
specification makes three claims; two are about behaviour and were MEASURED
across all five tabs with `scripts/drive_the_bar_on_every_tab.py` before a word
was changed, because writing this sentence from another sentence is exactly how
it went wrong:

| tab | Profile run | Run type | Verification |
|---|---|---|---|
| 1. Create Chart | enabled | enabled | selectable |
| 2. Print Chart | enabled | enabled | selectable |
| 3. Measure | enabled | enabled | selectable |
| **4. Build Profile** | **enabled** | enabled | **NOT selectable** |
| 5. Check & Refine | GREYED | GREYED | selectable |

**Both of his behaviour claims hold, so there is no second fault**: the profile
run really is still changeable on Build Profile, and Build Profile really is
the only tab that narrows the run type to Profiling
(`set_verification_selectable(index != 3)`). The tooltip now says both, and no
longer claims the selection is unused on a tab whose bar is live. The old
wording also carried an em dash, cleaned per the rule; twelve translations
updated.
- **one observation, not changed, for whoever takes the next pass**: the
  DISABLED Verification entry's own tooltip reads *"Not while standing on Build
  Profile / Calibration and Profiling tab"*, which names a tab ("Calibration and
  Profiling") that no longer exists in the tab bar. It is a different string
  from the one he asked about, and correcting it means another twelve
  translations, so it is left as a note rather than swept in unasked.
- evidence: `test_the_locked_bar_tooltip_does_not_claim_build_profile_is_locked`,
  `test_the_tooltip_says_build_profile_is_where_you_can_change_it`,
  `test_the_tooltip_says_build_profile_is_profiling_only`,
  `test_build_profile_is_the_one_tab_that_forbids_a_verification_run`,
  `test_only_check_and_refine_locks_the_bar`.

**A THIRD CHALLENGE ROUND FOUND A TRAVERSAL IN THE FIX ITSELF.** `run_id`
reaches `migrate_flat_project` from `project.json`'s `current_run`, and
`ProjectManifest.from_dict` does not sanitise it: only `peek_project` does, in
its own `_safe_id`, and its comment says exactly why ("a manifest is a file
people can edit, and projects get mailed around"). Everything else that builds
a path from that field only READS. This MOVES somebody's measurements, so a
mailed project whose manifest said `"current_run": "../.."` would have had its
chart, measurement and profile carried out of the project folder entirely. Now
refused, which here means the folder is left exactly as it was found.
- evidence: `test_a_hand_edited_current_run_cannot_carry_the_files_out`
  (six ids), `test_the_manifest_route_refuses_the_same_way`.

- **rounds.** Round 1 found the fault and its cause. Round 2, against my own
  change, found two: a Calibration or Verification target was being offered the
  RUN's profiling measurement, and `peek_project` had grown an unconditional
  `iterdir` on a function called on every keystroke (now lazy). Round 3 found
  the traversal above. Round 4 found nothing a user could see.
- **every guard was mutation-checked**: twelve mutations, each proved to land by
  reading the file back, each turning its test red, each reverted and the revert
  verified. One (the refusal) was STILL GREEN on the first attempt because a
  second check covered the same case, which is what produced
  `test_a_measurement_is_never_merged_into_a_run_with_a_DIFFERENT_chart`.
- **not fixed, and deliberately**: a pre-redesign project that also had a
  CALIBRATION keeps its `<stem>-cal.*` files loose at the project root, because
  they do not match the chart chain and `cal/` is a different destination with
  its own rules. None of the tester's three projects has any, so this is
  untested against a real example and is left rather than guessed at.

---

### B8-294 · FIXED · The pre-runs mover picked up the project's own manifest, and its traversal guard did not know about drive letters

- blocks release: no
- status: FIXED
- combined round 5 over the merged beta 20 tree, pointed at the migration
  stream because it is the only work in this release that MOVES a user's own
  measurements. Two rules in `migrate_flat_project` / `flat_legacy_chain` were
  a shade too loose. Both are defects of this release: neither function existed
  before it.
- **`project.json` IS NOT A CHART FILE.** The chain is matched on the project
  FOLDER's name, so a project a person names `project` makes its own manifest
  spell `project(_NN)?.<ext>` exactly. Measured on disk: `flat_legacy_chain`
  returned `['project.json']`, and opening such a project moved the manifest
  into `runs/run1`. `save_manifest` wrote it back at the root a moment later,
  so nothing was lost; what was left was a stray copy of the manifest inside
  the run folder and, from the next open onward, a warning on **every single
  load** saying the run "already holds 1 chart file(s) of its own" and refusing
  to do anything.
- the whole collision surface is exactly two names and both are now excluded:
  `project.json` and `Where are my files.txt`. `_migrate_v1_to_v2` already
  protects that same pair from being swept into `cache/` from INSIDE a run; the
  same list now stops them being picked UP from the project folder. `Project`
  and `PROJECT` never collided, because the match is case sensitive and the
  manifest is written lowercase.
- **`:` IS A PATH SEPARATOR ON WINDOWS, and the guard round 3 added did not say
  so.** It listed `/`, `\` and NUL. `Path(root) / "runs" / "D:"` is `D:`,
  another drive, outside the project altogether, and `"C:"` collapses to the
  `runs` folder rather than a run inside it, so the files land one level above
  where the app looks and the project reads as empty. Measured here: `"C:"` was
  accepted and moved all seven files.
- that is the same threat model round 3 wrote the guard for (`current_run` is
  unsanitised on the load path and a project travels as a zip), on the platform
  ChromIQ also ships to. The reader and the mover now share one rule,
  `is_a_plain_folder_name`, instead of keeping a copy each of which only one
  was strict enough; leading and trailing blanks are refused too, because a run
  folder is named by ChromIQ and never by a person.
- evidence: `test_a_project_named_project_keeps_its_manifest_at_the_root`,
  `test_a_project_named_project_does_not_warn_on_every_open`,
  `test_the_readme_is_not_a_run_file_either`,
  `test_a_real_chart_chain_is_still_moved_whole`,
  `test_a_run_id_that_is_not_a_plain_folder_name_moves_nothing` (17 ids),
  `test_a_drive_letter_cannot_name_a_child_folder`,
  `test_the_reader_and_the_mover_share_one_rule`,
  `test_a_manifest_naming_a_drive_leaves_the_project_where_it_is`.
- four mutations, each proved to land by reading the file back, each turning
  its own guard red, each reverted and the revert verified against a copy of
  the good file. The first attempt at the drive-letter mutation did NOT land
  (shell escaping ate the backslashes) and was redone in Python only rather
  than counted.

### B8-295 · The migration attacked as data and on screen, and a project cannot be left half moved · nothing further found

- blocks release: no
- status: VERIFIED
- evidence: `QT_QPA_PLATFORM=offscreen pytest -n auto` came back
  **16123 passed**, 321 skipped, 4 xfailed, exit 0, twice. The round's own
  drivers are
  `python ~/Desktop/ChromIQ-beta20-proof/combined-round-5/scripts/attack_migration.py`
  (15 folder states, 15 of 15 behaved) and
  `python ~/Desktop/ChromIQ-beta20-proof/combined-round-5/scripts/drive_round5.py`
  (4 of 4 projects converted whole in a real window, 4 photographs captured,
  0 refused).
- the promise under test is `migrate_flat_project`'s own: **it moves nothing,
  or it finishes**. Every act listed the whole folder before and after and
  compared the two, file by file, with sizes.
- **the three reported projects plus a fourth**, unpacked fresh from the zips
  into a sandboxed working folder and opened in a REAL window, photographed
  with `capture_window`: a folder with no manifest and a legacy `reports/`; one
  already stamped `schema_version: 2` by the broken version with every file
  still loose; one with ten pages; and the bare four-file chain. All four came
  out `schema_version: 3` with the chart, measurement and profile in
  `runs/run1`, and the "this name is already a project" guard answered True for
  all four both before and after.
- **fifteen adversarial folder states**, built by hand: a destination holding
  its own chart, a single colliding destination file, a read-only project
  folder, an immutable file halfway through the plan, `runs` existing as a
  file, a chain-shaped directory, a symlink in the chain, a run holding only
  role-named work, and a project already stamped by the broken version. Every
  refusal left the disk byte-for-byte identical; the immutable-file case rolled
  all five completed moves back and returned 0.
- **concurrency, 65 trials**: 40 with four staggered processes, then 25 with
  five processes released together by a spin barrier over 604 files and three
  different `current_run` values. **0 scattered, 0 lost.** The reason is worth
  recording: the plan is `sorted()`, so every racer starts at the same file and
  the atomicity of that first `os.replace` serialises them; the loser fails on
  file one, has nothing to roll back and returns 0. ChromIQ is not
  single-instance, so this is reachable, and it holds.
- **the one way a folder CAN be left half moved is a kill, not a fault.**
  Simulated by moving three of ten files and reopening: the run then holds a
  chart of its own, the "already holds" guard fires, and the project stays half
  moved for good, with the remaining files loose at the root. No test can be
  written against SIGKILL and the rollback cannot cover it; it is recorded
  because the recovery is refused by a guard that is otherwise right, and
  because the window is the microseconds of a metadata-only `os.replace` loop.
  Not swept: making it recoverable means teaching the guard to tell its own
  half-finished work from a second job, which is a design question.
- **`peek_project`'s cost on a keystroke**, the thing round 2 made lazy:
  0.093 ms and **one** `is_file()` on a healthy project whose run holds work,
  0.114 ms and three when the run is empty, 13.3 ms and 2003 on a project root
  carrying 2000 loose files. The laziness works. The comment justifying it does
  not: it says the function is "asked ON EVERY KEYSTROKE while somebody types a
  project name", and driving the real window shows **ten characters typed into
  the name box call `peek_project` zero times** (the box uses
  `_name_is_a_project_on_disk`, one `is_file()`). The code is right and the
  reason written next to it is wrong. Left as a note.
- **observation, not a regression**: a pre-redesign project's legacy `reports/`
  folder at the project root stays there while the run's reports live in
  `runs/run1/reports/`, so an old measurement report is not listed after the
  conversion. It was not listed before it either, because the run did not
  exist, so nothing a user could see has changed. Same for
  `<stem>_sanity_check.txt` and `Argyll_*.log`, which are not part of the
  chain.

### B8-296 · The rest of beta 20, re-checked briefly after rounds 1 to 4 · nothing found

- blocks release: no
- status: VERIFIED
- evidence: `QT_QPA_PLATFORM=offscreen pytest -n auto` came back
  **16123 passed**, 321 skipped, 4 xfailed, exit 0, twice.
  `python scripts/em_dash_check.py --report` reports 5847 English strings, 1168
  carrying an em dash, 1161 grandfathered, **0 not grandfathered** and 0 stale
  baseline entries. `python scripts/i18n_extract.py --missing de` reports 0
  missing of 5566. The change in this round adds no user-facing text at all,
  only log lines.
- both surfaces that print a cube corner were read again. The detailed per-run
  table marks a missing corner "(missing)", shows the ideal colour under
  Expected and a dash for Measured and for the delta E00, and drops the patch
  number; the one-page colour summary filters a missing corner out entirely,
  which is **pre-existing** and not part of the round-4 change, whose hunks are
  at lines 56, 6848 and 7728 and none of them is that filter.

### B8-297 — combined round 6: round 5's two migration fixes CONFIRMED

The first round in this release to re-attack a previous round's fix. Both hold.

**Fix 1, driven on screen** (`scripts/adv_b20r6_drive_the_colliding_names.py`,
real window, `capture_window`, four photographs in
`~/Desktop/ChromIQ-beta20-proof/combined-round-6/shots/`): a pre-`runs/` project
in a folder named `project`, `project_1`, `Where are my files` and `runs`, each
copied, opened, listed, and then **opened a second time** because that is when
the symptom appeared. All four: no manifest and no README inside a run, no file
lost, the disk after open #2 byte-for-byte the disk after open #1, and the app
holding chart, measurement and profile in `runs/run1`.

**Fix 2, attacked directly** (`scripts/adv_b20r6_attack_the_shared_name_rule.py`,
22 values for `current_run`, each against a freshly built seven-file project,
listed before and after): `..`, `.`, `../..`, `...`, `C:`, `D:`, `D:\x`, a UNC
prefix in both spellings, `/etc`, a leading and a trailing blank, an embedded
NUL and the empty string are all refused with the disk untouched; 300 characters
is refused by the filesystem and rolled back by the `mkdir` guard; nothing
escaped the project folder in any of the 22. `run1` moved all seven.

**Two things the rule allows, both recorded as safe, neither a defect.** A
trailing dot (`run1.`) and an embedded newline are accepted, and both land
INSIDE `runs/`; the reader derives the same folder from the same string, so
reader and mover still agree and no file leaves the project. They are names a
manifest should not hold, not a traversal.

**And a case-insensitive filesystem makes `Project` and `project` one folder**,
so that pair cannot be tested apart on macOS: asked for `PROJECT` the chain
came back empty, because the stem regex is case-sensitive while the disk is
not. The mover then does nothing, which is the safe direction.

Task 3 (a second pass over the three reported projects) was NOT done: round 5
drove them and the deadline came first. No source file changed in this round.

### B8-298 · "The instrument lost communication" sent a user to the hardware shop
- blocks release: no
- status: OPEN
- found by: a reporter on issue #197, v4.2.7, Windows 11, i1Pro 2, and by reading
  his own two screenshots. **Not a fault in the detection, a fault in the
  advice.**
- detail: a strip read fails intermittently, every two or three strips, and the
  same strip usually reads fine on the next attempt. ChromIQ shows "Strip Read
  Failed", headed *"The instrument lost communication with the computer"*, and
  advises checking the cable, trying another USB port, and making sure no other
  application holds the device.

  Acting on that, the reporter tried **five USB ports, two cables, another PC
  and a powered hub**, and then wrote that he would have to replace the
  instrument. None of it helped, because none of it was the cause.

  **His own screenshots contain the evidence, in our own panel.** A strip that
  worked reads **4.0 s** in the strip-time panel; the failed one reads
  **32.8 s**. A dropped USB link does not take half a minute, and it has its
  own path here anyway: `_USB_ERROR_RE` on "ReadPipeAsync failed" raises
  `instrument_disconnected`. What he is hitting is `_STRIP_COMS_FAIL_RE`,
  chartread's "Strip read failed due to communication problem", which covers a
  read that never completes as well as a link that dies.

  So the wording names one cause of a message that has several, in the most
  expensive direction a wrong guess can point: at buying hardware. The chart is
  also worth noting, 1200 patches over ten 10 by 15 cm cards, about 120 per
  card, so the strips are short and the patches small.

  **What to change:** the headline should not assert the cause. Say the strip
  did not complete, offer the cable check as one possibility among others, and
  name the two that cost nothing: a slower or steadier sweep, and a chart with
  larger patches. The log line is what distinguishes them, so the message
  should also point at the log rather than at the cable.

### B8-299 · The expected/measured split showed the chart along a patch edge, and a screen capture could not have shown it
- blocks release: no
- status: FIXED
- held: **on branch `fix/split-overlay-gap`, out of every release until Basti
  has looked at the proof and says to merge it** (his instruction, 2026-09-17:
  *"this fix will not be part of a release until i have looked at the proof
  you leave for me and i tell you to implement it"*).
- evidence: `test_no_chart_pixel_survives_under_the_split`,
  `test_the_split_never_paints_over_the_spacers`,
  `test_every_box_is_the_size_of_the_patch_it_covers`,
  `test_the_same_patches_read_in_any_order_paint_the_same_pixels`,
  `test_a_honeycomb_reads_the_same_whatever_order_its_patches_arrive_in`,
  `test_both_paint_paths_hand_the_overlay_the_pages_own_vertical_scale`,
  `test_a_patch_box_is_never_smaller_than_the_chart_patch` (all seven live in
  the split-overlay file added by this round)
- proof: `~/Desktop/ChromIQ-beta21-proof/split-overlay-gap/`
- found by: a tester's screenshot of the Measure tab, forwarded by Basti:
  *"the 6th patch in the first strip has a tiny gap at the bottom from the
  split overlay (measured vs expected)"*, and then *"on some patches the
  diagonal line is perfect and on other it makes a step (patch 8 and 10 in the
  first strip)"*.

**Three findings, in the order they mattered.**

1. **The overlay was mapped with the page's HORIZONTAL scale on both axes.**
   `TiffPreview` scales the page with `QPixmap.scaled(..., KeepAspectRatio)`,
   which returns a whole number of device pixels on each axis, so the two
   ratios are not the same number. `_repaint_label` computed the scale from the
   width and `_draw_cq_overlay` applied it to y as well, sliding the overlay
   grid along the page. Measured on screen over six window sizes: the slide
   reaches **1.37 device pixels** at the foot of an A4 page. Where it crossed a
   rounding boundary the split stopped one screen pixel short and the printed
   patch showed through, full strength: a photograph of the fixed-page test at
   700x980 has row 1175 reading `(218, 0, 218)` right across the sheet.

2. **The page is drawn with `SmoothTransformation`, so a patch's colour
   reaches about a pixel past its own edge.** A box that covers the patch
   exactly still leaves a coloured hairline. Basti, on the photograph of the
   first fix: *"you can still see color from the patches bleeding through"*.

3. **`scripts/onscreen_capture.py` photographed a 2x window at 1x.**
   `kCGWindowImageNominalResolution` averages every device pixel with its
   neighbour before anyone can look at it, so this helper physically could not
   show a one-device-pixel fault, and every pixel-level proof taken with it
   since it was written was looking at a halved picture. Now
   `kCGWindowImageBestResolution`: same window, nominal 560x1028, best
   1120x2056, and the offending row exists only in the second.

**The fix.** Both paint paths hand `_draw_cq_overlay` the page's own vertical
scale, and so does the cursor-to-image mapping, which the first version left
behind on the old grid. Each box is then snapped to the patch it covers and
nothing more, and the boundary pixel the snap leaves uncovered is repainted at
the patch's own coverage of it (see "the fourth version" below). Items are
drawn in a canonical order, sorted by y then x, so a page cannot depend on the
order its patches were read in.

**THE FIRST VERSION OF THIS FIX WAS WRONG AND AN ADVERSARY ROUND PROVED IT.**
It decided "is this edge shared" by matching integer coordinates exactly, so a
gap of ONE image pixel read as free on both sides and the two boxes grew into
the same screen pixel. `Spacer size = 0.1 mm` is a real control in Create
Chart, and at 200 dpi ChromIQ's own layout engine then records 136 of 176
vertical neighbours exactly one image pixel apart, which is 0.50 screen pixels.
Driven on the real Measure tab at 1000x880: reading the same strips in a
different order changed **2,024 pixels** of the window, where the build before
the fix changed none. Re-driven with the gap rule on the same chart and window:
**0**. The round also caught two comments and a commit message claiming the
spacer bands were untouched, when every free edge costs one screen pixel, and
the hit-test drift above (66 of 924 probes landing on a different patch, or
none).

That case is now `test_the_same_patches_read_in_any_order_paint_the_same_pixels`,
which DRAWS the page twice and compares it, over five gap widths and three
window sizes. Asserting order-independence by reading the source, which is what
the first version did, cannot catch a box that grew a pixel into its
neighbour: put the old rule back and 16 cases go red.

**AND ROUND 2 BROKE THE SECOND VERSION, ON A LAYOUT WE SHIP.** The gap was
measured as one minimum over every patch on the page. A ColorMunki "Offset
every second strip" chart shifts the odd columns by half a patch, so column
N's y-spans OVERLAP column N+1's, that minimum reads 0, and the overlay
concluded it had no room to grow anywhere on the sheet. Every column has its
full 7 or 8 image pixel band. Measured on the real Measure tab at 1200x980:
**8,686 chart-coloured pixels** left showing with the stagger on, **0** with it
off, same chart, same patches, one checkbox apart.

`_axis_gaps` now measures the vertical gap down each COLUMN and the horizontal
one along each ROW, grouping lanes by OVERLAP rather than by equality, which is
the condition that actually lets two boxes meet. On a staggered chart that also
keeps the horizontal answer right: the columns touch across and their y-spans
do overlap, so they share a row group, the horizontal gap reads 0, and sideways
growth is correctly refused. Re-driven on the same chart and window: **8,686 to
440**, and the unstaggered control stays at 0.

**The remaining 440 are honest and will not go away by tuning.** They sit in
four short vertical lines, at the SIDE edges of the patches that the stagger
leaves facing a neighbouring column's gap rather than its patch. A per-edge
rule would not reach them either: the exposure is on part of an edge, and the
box is one rectangle. Covering them needs a clipped fill, which is a different
change and not worth it for a 95 per cent case.

**AND ROUND 3 BROKE THE THIRD VERSION, AT A CORNER.** Grouping lanes by
overlap answers two questions, and there are three. Two boxes that meet only
at a CORNER share no extent on either axis, so no grouping ever pairs them,
both single-axis answers come back large, both axes grew, and the corner
device pixel was painted twice with draw order deciding the winner. The layout
is real and reachable from three Create Chart controls: ColorMunki with
"Offset every second strip", "Spacers: None" and an inter-patch gap past twice
the patch length drops the odd columns into the even columns' gaps, so no
patch of one column shares any y with the next. Driven on the real Measure
tab: **6 to 48 device pixels changed with the read order** at every window
size tried, and at 28.2 mm **187 of 187 window sizes** scanned fire it, where
the build before this change set fired none.

`_growth_axes` asked the third question too: grow both axes only when no pair
was close on BOTH, which is the condition for two rectangles to stay disjoint.
When they cannot both grow, the vertical one wins, because a line along a
patch's bottom edge is the fault this all started from. Re-driven on round 3's
own two charts, four window sizes each, settled photographs: **0 differing
pixels between draw orders, and 0 overlapping pairs predicted**, with the
ordinary sweep still at 0 and the staggered chart still at 440.

Round 3 also found **three y coordinates still mapped with the HORIZONTAL
scale** inside the same function, after the rest had been fixed and the
docstring claimed they all were: the legend chip's anchor (twice) and the
hexagonal strip-hover outline, which drifts 1.012 device pixels from its
patches at the bottom of the sheet. Fixed, and `_strip_zigzag_path` now takes
the vertical scale.

And it measured the cost of the rule: **1.10 ms inside a 7.65 ms repaint** on
a 693-patch A3 page, on every hover. `_growth_for_page` cached the answer
against the page and the scale. The fourth version removed the cost entirely.

**THE FOURTH VERSION THREW THE GROWTH MACHINERY AWAY.** Every rule above
decided whether a box could take a whole screen pixel it did not own, and each
round found another layout where the answer was wrong. The requirement Basti
wrote makes that question unnecessary: the box is snapped to the patch, full
stop, and the one pixel the snap leaves uncovered is repainted at the coverage
the PATCH has in it, not opaquely. That pixel is part patch and part spacer,
exactly as the chart's own antialiased edge is; painting
`c * split + (1 - c) * spacer` over it replaces the patch's share and leaves
the spacer's. `c` comes from the edge's own fractional position and the spacer
colour is read from the rendered page just past the edge, so nothing is
assumed about what lies there.

`_MIN_GAP_TO_GROW_DEVICE_PX`, `_growth_axes`, `_growth_for_page`, `_min_gap`,
`_overlaps`, `_dfloor` and `_dceil` are gone with it, and so is the whole class
of draw-order faults: no box ever writes outside its own snapped rectangle, so
two boxes cannot contend for a pixel whatever order they arrive in. The sliver
is drawn only on the SEGMENTS of an edge that face no patch (`_exposed_edges`),
so an edge shared with a neighbour is never touched. The residue left on a
boundary pixel is `c * (1 - c)` of the patch colour, which peaks at a quarter
strength at c = 0.5 and is zero at either end.

**What was tried and rejected.** Snapping the position and rounding the SIZE
up gives every patch of a size exactly one size on screen, so every diagonal
gets the same stair pattern, which would have answered the second half of the
report as well. It also grows every box by up to a pixel on every side. Basti
saw it immediately in the photograph: *"now you just made the overlay bigger
and in turn some spacers got smaller and not all of them have the same size"*.
Rejected. The overlay follows the chart; it does not tidy it.

**The "step" is the chart's own grid, not a fault.** A corner-to-corner
diagonal's stair pattern follows the box's height, the box's height follows
the patch's height on screen, and a patch grid with a fractional pitch lands
on 52 screen pixels here and 53 there. The scaled chart does exactly the same.
An overlay that insisted on one height would stop matching the picture it sits
on, which is what the rejected variant did.

**Measured, on screen, six window sizes, 462 patches each.** A page whose only
colour is in the patches, the split drawn in two greys, so any coloured pixel
left is chart showing through (Basti's idea, and a better detector than the
one this round started with):

| | chart-coloured pixels left under the split | of which full strength |
|---|---|---|
| before | 151,383 | 37,305 |
| after | **0** | **0** |

and the residue after the gap rule is 0 pixels carrying half the patch's colour
or more (a faint tint of 6,954 pixels remained along the grid's outer edge
until the outermost edge was allowed to grow as well; 0 after that).

**AND THE SPACER BAND KEEPS ITS WIDTH.** The version before this one covered
the boundary pixel opaquely, which cost each band one screen pixel on each
side: over six window sizes the bands went from 4, 5, 6, 7 device pixels to
3, 4, 5. Basti saw it in the photograph, for the second time in this entry:
*"it seems that your fixes cause the spacers to become smaller when the split
overlay is active"*, and then set the requirement in one sentence: *"the split
overlay should only perfectly cover the patches and not the spacers but also
leave no gaps"*. With the coverage-weighted sliver the same six sizes measure
5, 6, 7 (mean 5.94) against 4, 5, 6, 7 (mean 5.93) before, which is the same
band, not a narrower one.

**Harness.** `scripts/drive_b21_split_overlay_gap.py` drives the real widget in
a real window and photographs it; `scripts/analyse_b21_mono_leak.py` counts.
The driver stamps a marker block into each corner of the page it loads, so
where the drawn page begins and ends is measured rather than derived through
three separate half-pixel roundings.

**One thing the round found in the harness, not the product:** a capture taken
straight after `set_patch_overlay` can land before the widget has repainted,
and `capture_window` correctly refuses the empty buffer as one flat colour.
The driver now waits and asks again, up to five times, and reports a refusal
that survives all five.

### B8-300 · A failed strip points a user at the cable, and the log is four steps away
- blocks release: no
- status: OPEN
- found by: checking a claim I had already made twice in public. On issue #197
  I told the reporter to open his log with *"Help menu, Open log folder"*.
  **There is no such item.** The log is reached through Preferences, the Paths
  tab, the "For reference" box, first row, behind a Reveal button; or by hand
  at `%LOCALAPPDATA%\ChromIQ\Logs\chromiq.log`,
  `~/Library/Logs/ChromIQ/chromiq.log`,
  `~/.local/state/ChromIQ/logs/chromiq.log`. Corrected on the issue
  (comment 5709770293).
- detail: this is the other half of B8-298. That entry says the "Strip Read
  Failed" dialog should stop naming the cable as the cause and should point at
  the log, because the log line is what tells a dropped link from a read that
  never finished. But a person who has just lost a strip cannot reasonably be
  sent on a four-step route through Preferences to find it, and nothing in the
  failure window mentions it at all.
- what to change: the dialog carries the button itself. Every window that ends
  a measurement badly should. The draft wording for B8-298 already leaves a
  place for it.

### B8-301 · FIXED · A saved measurement report could be left half written, and the atomic helper leaked a scratch file on Ctrl-C
- blocks release: no
- status: FIXED
- evidence: `test_both_report_writers_go_through_the_atomic_helper`,
  `test_a_failed_save_leaves_the_previous_report_untouched`,
  `test_a_write_that_dies_mid_payload_leaves_nothing_readable_behind`,
  `test_every_saved_report_parses`
- found by: closing the cause B8-278 left open. That entry hardened the delete
  rule so it counts only the report files the window can actually parse,
  after combined round 3 drove a dated verification holding one good report
  and one TRUNCATED file: Delete came up enabled with no reason beside it, the
  confirmation said *"0 saved reports of it are left afterwards"*, and the
  press left the date with no verdict the window could read. The truncated
  file is what `Path.write_text` leaves when the process is killed mid-write,
  and `save_report` and `rewrite_report` both used it.
- **the fix.** Both go through `core.file_manager.write_json_atomically`,
  which already pays for every trap `os.replace` has cost this project: it
  resolves a symlink first (the rename swaps the NAME, and pointed at a link
  it would delete the link and leave the real file stale), fsyncs before the
  rename, carries mode, times and flags across, and drops the immutable bits
  from the scratch file so a locked target cannot leave an undeletable `.tmp`.
  Nothing new had to be written.
- **AND WRITING THE GUARD FOUND A HOLE IN THAT HELPER.** Its cleanup hung off
  `except Exception`, which does not catch `KeyboardInterrupt` or
  `SystemExit`. A write interrupted by Ctrl-C is exactly the case the helper
  exists for, and it left `report_….json.tmp` in the reports folder. It is a
  `try/finally` with a flag now, so every exit path cleans up. The same helper
  writes `project.json` and `meta.json`, so this was not only about reports.
- **AND IT QUIETLY TOOK AWAY A REFUSAL, WHICH THE SUITE CAUGHT.**
  `write_text` on a file the user had made read-only raised, and the window
  told them so. `os.replace` needs write permission on the DIRECTORY, not on
  the target, so the rename succeeds and the content is replaced without a
  word, with `copystat` carrying the 0444 back so the file still looks
  protected afterwards. `test_a_set_change_asks_before_it_rewrites_history.py`
  marks one saved report read-only and expects the recalculation to report
  that it could not be written; both its cases went red the moment the write
  became atomic. `write_json_atomically` now refuses a target it cannot write,
  which closes the same hole for `project.json` and `meta.json`, where it was
  already open and nothing had noticed.
- mutation proof: put `write_text` back and two of the five go red.
- evidence (cont.): `test_a_read_only_report_still_refuses_the_write`

### B8-302 · FIXED · A test's 450 ms timer fired into a LATER test and turned a gate red
- blocks release: no
- status: FIXED
- evidence: `test_settling_never_raises_out_of_its_caller`,
  `test_resetting_manual_to_its_preset_arms_nothing`
- found by: one red `--runslow` gate on 2026-09-17, after five green ones on
  almost the same tree. `CALL ERROR: Exceptions caught in Qt event loop` with
  `RuntimeError("boom")`, and the traceback naming
  `tab_chart._auto_regenerate_preview` -- a TIMER slot, not the function the
  failing test calls.
- **the mechanism.** The `tab` fixture in
  `tests/test_the_live_preview_only_follows_the_user.py` builds a real
  `TabChart` and never disarmed its auto-preview timer. Several tests in the
  file END with that 450 ms timer deliberately running, because "the render the
  user queued is still queued" is the assertion. The tab is not collected when
  the test returns, so the timer can still fire during a LATER test -- and two
  tests in the same file patch `_layout_signature` ON THE CLASS to raise. The
  stray timer then threw into the Qt event loop and pytest-qt failed whichever
  test happened to be running.
- **the fix** is in the fixture: stop the timer at teardown. The product is
  unchanged; the leak was the test's.
- **honest limit:** the mechanism is read off the traceback and the fixture,
  not reproduced on demand. It needs 450 ms of event loop between the arming
  test and the patching one, which a loaded parallel gate provides and a
  two-test run does not. Three green `--runslow` gates since (16,302 passed,
  exit 0, three times) are the verification, and the leak itself is gone
  whether or not it was ever the cause.
- the same shape as the QApplication leak this project has already paid for:
  a fixture that leaves live Qt state behind fails a different test each run.

### B8-303 · FIXED · A test patched a method on the CLASS, and another file's leaked timer walked into it
- blocks release: no
- status: FIXED
- evidence: `test_settling_never_raises_out_of_its_caller`,
  `test_resetting_manual_to_its_preset_arms_nothing`
- found by: two red `--runslow` gates on 2026-09-17, hours apart, on trees
  that were otherwise green three times each. Both said `CALL ERROR:
  Exceptions caught in Qt event loop` with `RuntimeError("boom")`, and both
  tracebacks named `tab_chart._auto_regenerate_preview`, a TIMER slot, not the
  call under test.
- **the mechanism, and the first fix was not enough.**
  `_auto_regenerate_preview` calls `self._layout_signature()` as its FIRST
  statement, with no gate in front of it. So any TabChart anywhere in the
  process whose 450 ms auto-preview timer fires reaches that method
  immediately. `tests/test_the_live_preview_only_follows_the_user.py` patches
  it ON THE CLASS to raise, which means a leaked timer on ANY tab turns into a
  failure of whatever test is running. Disarming this file's own fixture
  (B8-302) was right and did not fix it, because the leaked tab belongs to
  another file.
- **the fix:** patch the INSTANCE. A class patch can be reached by every
  instance; an instance patch cannot be reached by any other. The same change
  is applied to `_renders`, whose class-level stubs would have recorded a
  render the test never asked for.
- **honest limit:** not reproduced on demand, twice attempted. The argument is
  structural rather than empirical, and it is the kind that does not need a
  reproduction: after the change there is no path from another tab's timer to
  this test's stub.

### B8-304 · FIXED · On a honeycomb the split overlay was decided by the order the strips were read in
- blocks release: no
- status: FIXED
- evidence: `test_a_honeycomb_reads_the_same_whatever_order_its_patches_arrive_in`
- proof: `~/Desktop/ChromIQ-beta21-proof/hex-overlay-shape/`
- found by: adversary round 4, and independently by Basti's eye: *"is it
  working for hexagonal patches as well (normal and rotated honeycomb)? …
  it seemed that there was something still wrong with hexagonal patches"*.
- **NOT introduced by the split-overlay change set.** The same measurement
  against `f7f1784e` gives the same numbers. It is an inherited fault that
  three adversary rounds had "cleared", and the clearances were worthless:
  every one of their draw-order drivers photographed a hexagonal chart with
  `set_hex_zigzag` OFF, so all three drew the RECTANGULAR branch on a
  honeycomb and reported it clean. The one path that depends on read order is
  the one path nobody had ever drawn.
- **the fault.** Hexagons interlock by design. The fill is antialiased and the
  seam is stroked ON the shared edge, so the lozenge where three apexes meet
  belongs to whichever patch was drawn last, and the patches arrive in the
  order the person swept. On the real Measure tab with a real SpectroScan
  honeycomb: **9,356 device pixels at 1200x980 and 4,859 at 900x1000** changed
  between two read orders, across 545 separate regions, the largest 145 pixels.
  Self-comparisons 0. With the honeycomb switched off, the same chart gives 0,
  and the growth rule granted no growth at all, so it is the hexagon branch and
  not the gap rule.
- **the fix.** `_draw_cq_overlay` sorts its items by position before drawing.
  It costs nothing, changes no pixel of a rectangular chart, and makes the
  picture the same whatever order the patches arrive in, which is what the rest
  of the function already promised. Re-driven on the real Measure tab:
  **0 and 0**. Mutation: take the sort out and four honeycomb cases go red,
  14,507 to 19,525 pixels each.
- **and the SHAPE question is answered, on screen, in all four cases.**
  `scripts/drive_b21_hex_overlay_shape.py` paints a page whose only colour lies
  INSIDE each patch's hexagon, with the slot corners a hexagon never reaches in
  a second colour, and draws the split in two greys. A pixel of the hexagon
  colour left showing means the split missed its own patch; a grey pixel on a
  corner means it drew a rectangle over a hexagon. SpectroScan honeycomb, CR30
  honeycomb, CR30 ROTATED honeycomb and CR30 square, three window sizes each:
  **0 hexagon pixels left**, and the only grey outside a hexagon is the
  one-pixel seam stroke the honeycomb is drawn with on purpose. The square CR30
  chart correctly gets rectangles.
- **the driver had the same blind spot first, and it is worth writing down.**
  `build_chart` does not write `channels.json`, and `chart_is_hexagonal` reads
  the RECIPE from that sidecar rather than the geometry, so a real honeycomb
  answers "not hexagonal" and every driver built on top quietly photographs the
  rectangular branch. Also: `hex_flat_top` is resolved the way `_build_base`
  resolves it, inside `key == "CR30" and hflag`, so **a SpectroScan honeycomb
  is always pointy-top** and asking for a rotated one there silently builds a
  pointy one. A rotated honeycomb is a CR30.

### B8-305 · FIXED · Two guards in the split-overlay file could not catch what they were written for
- blocks release: no
- status: FIXED
- evidence: `test_the_same_patches_read_in_any_order_paint_the_same_pixels`,
  `test_both_paint_paths_hand_the_overlay_the_pages_own_vertical_scale`
- found by: adversary round 4, reading the guards rather than the product.
- **the corner case did not build a corner.** The draw-order test's staggered
  variant dropped the odd columns by a whole pitch, which puts column c+1's row
  r exactly where column c's row r+1 is: the columns then share their whole
  height, which is an ordinary grid with an offset label, not a corner contact.
  Instrumented across all 30 drawn cases, the rule never once answered "grow
  sideways". The drop is half a gap plus the patch height now, which puts one
  column's patch bottom exactly at the next column's patch top.
- **the y-scale guard matched one spelling.** `assert "* s + oy" not in src`
  would have caught NONE of the three real cases that reached the shipped
  build: two were written `oy + (...) * s` and the third was `v * s + oy`
  inside a method the guard never read. It is an AST walk now, over every
  `something * s` added to `oy`: 3 hits on the build that had them, 0 on this
  one.

### B8-306 · FIXED · "Show only measured patches" blanked a honeycomb with a rectangle, wiped the strip labels, and left the edge spacers showing
- blocks release: no
- status: FIXED
- held: **on branch `fix/split-overlay-gap` with B8-299**, out of every release
  until Basti has looked at the proof and says to merge it.
- evidence: `test_a_blanked_honeycomb_does_not_reach_into_a_read_neighbour`,
  `test_the_blank_never_rises_into_the_strip_labels`,
  `test_an_unread_column_hides_its_edge_spacers` (all three in the
  show-only-measured file added by this round)
- proof: `~/.claude/jobs/c4ec4e71/tmp/b21-som/`, photographed on screen
- found by: an adversary round on the split-overlay work, then Basti on the
  photographs, then a mutation run on the guards written for the fix.

**All three faults were INHERITED.** None of them came from the split-overlay
change set; the round found them because it was driving the same widget.

1. **A honeycomb was blanked with a RECTANGLE spanning the unread strip's
   patch bounds.** Hexagonal columns interlock, so that rectangle reaches into
   the neighbouring column and paints white over a READ neighbour's lobes.
   Measured on screen on a real SpectroScan honeycomb at 900x1000: with the
   blanking off a read strip is drawn 68 to 90 device pixels wide down the
   column; with it on the same strip was 20 to 43, and it read as a straight
   band instead of a staggered honeycomb. Basti: *"the colorful patches go down
   in a straight line although they are staggered"*. A honeycomb is now blanked
   by filling its hexagons, grown by half the spacer ring so a blanked column
   really is blank and a read neighbour keeps its own half.
2. **The blank walked up into the strip labels.** Its clamp fired only
   `if band_top < min_py`, and every chart today's layout engine builds records
   the label band BELOW the first patch top, so the clamp was inert: 687 to
   1,415 device pixels of label ink turned white on six of the layouts tried.
   The clamp is unconditional now.
3. **The edge spacers were left showing**, which Basti asked about directly:
   *"are edge spacers also hidden by this? they should then be i think"*.

**AND THE FIRST FIX FOR (3) ONLY WORKED ON THE BOTTOM ONE.** Clamping the
blank's top flat to `rects[i].top()` takes the TOP edge spacer straight back
off, because on every chart today's engine builds that rect's top IS the first
patch top. Caught by a guard written for the fix, which measured **2,688 of
5,706 edge-spacer pixels still showing**, the top band whole. The rule now
separates the two things the old clamp confused: the edge spacer is a printed
bar of exactly `esp` pixels sitting directly on the first patch, so everything
from `min_py - esp` down belongs to the strip by construction and is always
safe to cover; the `vpad` above THAT is a guess at a hairline and is the part
that walked into the letters. The floor is the band bottom where the rect
carries one and the top of the edge spacer where it does not.

**AND THE FIRST GUARD FOR (1) WAS WORTHLESS, WHICH A MUTATION RUN PROVED.**
Its fixture pitched the honeycomb's columns a patch plus a gap apart, so the
columns did not interlock and no rectangle could ever reach a neighbour:
forcing the rectangular branch back on left the test GREEN. Rebuilt with the
three-quarter-patch pitch a honeycomb actually has, the same mutation fails it,
**13,593 coloured pixels left of about 24,753**, which is the same 45 per cent
loss the photographs showed.

**AND THE BLANK STOPPED ON A FRACTION.** Covering the edge spacer is not
enough on its own: the page is drawn with `SmoothTransformation`, so the
spacer's colour reaches about a device pixel past its own edge, and a fill that
stops mid-pixel leaves that row showing. Whether it does is decided by the
rounding phase, which is decided by the window. Basti, on the photographs:
*"still something at the top here. sometimes it seemed at the bottom as well"*.
Driven on a real label-free i1 chart, 8 strips, 160 patches, eight window
sizes, settled photographs:

| window | spacer pixels on the plain page | before any of this | with the spacer covered | with the fill snapped outward |
|---|---|---|---|---|
| 700x820 | 4,638 | 2,334 | 290 | **0** |
| 714x842 | 5,025 | 2,662 | 300 | **0** |
| 728x864 | 5,146 | 2,726 | 307 | **0** |
| 742x886 | 5,318 | 2,861 | 317 | **0** |
| 756x908 | 5,418 | 2,916 | 0 | **0** |
| 770x930 | 5,589 | 3,015 | 0 | **0** |
| 784x952 | 5,994 | 3,366 | 0 | **0** |
| 798x974 | 6,167 | 3,458 | 0 | **0** |

Only the VERTICAL edges are snapped. Sideways the fill already reaches the gap
midpoint to each neighbour and a neighbour may be READ, so growing there could
eat a measurement; above and below an unread column there is only paper. The
guard is parametrised over those eight sizes, because four of them cannot see
the fault: put the fraction back and it fails at 714x842 and 742x886 by 287 and
301 pixels, and passes everywhere else.

**TWO CLAIMS THIS ROUND INHERITED AND HAD TO CORRECT.**

* Round 5 wrote, in the code and in this register, that *"every chart today's
  layout engine builds records `label_band_bottom_px` BELOW the first patch
  top"*. Measured on six chart types built here, it is ABOVE on all of them:
  i1 85 against a first patch at 315, SpectroScan 81 against 123, ColorMunki
  102 against 319, rotated CR30 97 against 134. The clamp that claim called
  inert was firing the whole time and simply never binding. What DOES put the
  strip rect on the first patch is a chart with **no strip indicators**, which
  records no label band at all, and that is the class where the clamp binds and
  where there are no letters above to protect.
* The driver that measured all this wrote its sidecar recipe with
  `build_chart`'s keyword names. `LayoutRecipe(**recipe)` drops anything that
  is not one of its fields, so `spacer_width` (the kwarg) never became
  `spacer_width_mm` (the field), `edge_spacer_px_from_sidecar` answered with
  the instrument's default of 8 px where the chart had drawn 12, and the four
  rows in between showed as a black line in the photograph. **The app was
  right and the harness was wrong**, and it was one measurement away from being
  filed as a fault in `edge_spacer_px_from_sidecar`. The driver builds a real
  `LayoutRecipe` now and checks the drawn band against the reported number
  before it measures anything.

### B8-307 · FIXED · Loading a Create Chart preset measured the same text tens of thousands of times
- blocks release: no
- status: FIXED
- evidence: `test_the_three_label_probes_are_cached_at_all`,
  `test_the_engine_loads_a_font_once_however_often_it_asks`,
  `test_the_row_label_band_is_measured_once_per_question`,
  `test_a_cached_label_measurement_never_answers_a_different_question`,
  `test_every_argument_of_a_label_probe_really_changes_its_answer` (all five in
  the label-probe file added by this round)
- found by: Knut, beta 20: *"Loading any of the 6 Scanner presets takes 5 to 10
  seconds to load. Why? Patch sets are simple numbers for colors, so it should
  not take a lot of processing power. Can the loading be made more efficient?
  Also, the first preset I load after having loaded a scanner preset will also
  take a long time to load. It seems the time it takes to load a preset is
  dependent upon which profile I loaded last."*

**Both halves of that reproduce, in the real window on the real dropdown**, and
the second half is the more interesting one: the cost depends on the SIZE of
the chart the previous preset left in the panel, because the area fit searches
over candidate patch sizes and every candidate asked the font the same handful
of questions again.

`_furniture_reserves_mm` renders two glyph probes and `row_label_band_mm`
measures a row of labels. One preset load called them **3,845** and **45,227**
times, which came to **135,685 `Font.getlength` calls, 49,079 font loads and
7,706 rendered glyph images**. Profiled: 8.0 s of a 17.2 s load was PIL
measuring text and 1.9 s was rendering it.

All three are pure functions of their arguments, and all three are memoised
now. The font is built INSIDE each cached call rather than cached on its own,
so no `FreeTypeFont` is shared between the engine's worker threads; only
numbers cross.

| loaded | before | after |
|---|---|---|
| a ColorMunki preset, first | 1.25 s | **0.83 s** |
| a Scanner preset, 3,430 patches | 10.21 s | **1.66 s** |
| the ColorMunki one straight after it | 17.90 s | **1.29 s** |
| a Scanner preset, 6,860 patches | 10.15 s | **1.86 s** |
| the ColorMunki one straight after that | 5.09 s | **0.93 s** |

**AND IT ANSWERS THE SAME, BYTE FOR BYTE.** Twelve chart configurations built
on both trees (default, numeric labels, rotated labels, bold+italic, an
explicit 6 mm size, underlined, indicators off, ColorMunki, SpectroScan
honeycomb, rotated CR30 honeycomb, patch-first, A3): **46 files each,
identical**, once the `.ti2`'s CREATED timestamp and its random CHART_ID are
normalised. That check is what caught the one real fault the refactor
introduced: the rotated-label branch still used the font variable the extraction
had removed, and every `indicator_rotation=90` chart raised `NameError`. It
takes the band height the probe already returned now, which the comment beside
it always said was the same number.

**One claim NOT made:** the style does not change the BAND probe, at any size
tried. The band is the ink height of "W8" and a bold face is no taller, so
there is nothing to assert there and the guard says so rather than inventing a
weaker claim. It is observable in the ink probe at 40 px, and in the row label
on a face whose italic is a real second face, and both are asserted.

### B8-308 · OPEN · Generate report writes the new report and the selector keeps naming the old one
- blocks release: no
- status: OPEN
- found by: Knut, beta 20: *"Now there are two reports in the 'Saved reports'
  pulldown, but the selected option did not change to the new report I
  generated last."*
- proof: `~/.claude/jobs/c4ec4e71/tmp/knut-report/proof/C-after-generate-report.png`
- detail: worse than reported. The PAGE does follow the new file, so the
  selector and the document disagree: the header reads *"Judged against:
  ChromIQ default (recommended)"* while the pulldown reads *"… · Quick check ·
  saved 2026-06-01 09:00:00"*. `_sync_saved_reports`
  (`ui/dialogs/measurement_report_dialog.py:3399`) takes `want =
  combo.currentData()` as its primary source of truth, so the combo's own stale
  selection wins over `self._report`, which `_on_generate_report` has just
  moved to the file it wrote.
- what to change: compute the index from `self._report` first and use `want`
  only as the fallback for rows that are not the window's subject.
  `tests/test_saved_reports_can_be_chosen_and_deleted.py::test_generate_shows_the_report_it_just_wrote`
  asserts the document moved and never asserts the selector did; that missing
  line is why this shipped.

### B8-309 · OPEN · The report text is written to a reader who is sitting in front of the window
- blocks release: no
- status: OPEN
- found by: Knut, beta 20: *"the text must be written as if it is a separate
  document printed for a customer, and that customer knows nothing of the
  Measurement Report windows, buttons, selections that can be made or changed
  ... shall only contain data and results relating to that one reports
  settings, and not show information that other reports exist with other
  'judged against' threshold sets."*
- proof: `~/.claude/jobs/c4ec4e71/tmp/knut-report/proof/D-report-scope-names-other-reports.png`
- detail: `_other_limit_sets_html` (`:6206`, called unconditionally from
  `_scope_html:6203`) prints a red paragraph naming every measurement left out
  and the set each was judged against, twelve of them on the demo project.
  Fourteen further strings speak about the window or its controls: *"loaded in
  this window"*, *"in the list above"*, *"(unticked)"*, *"chosen in this
  window"*, *"ticked in Preferences → Reports"*, *"when you point at the cell"*
  (a printed PDF has no hover), *"use Check & Refine ▸ Analyse Profile
  Quality"*. Every one is listed with its line number in the investigation
  notes.
- **NOT in the §M catalogue.** `tests/test_message_catalogue.py`'s
  `WINDOW_SOURCES` does not list `measurement_report_dialog`, so removing them
  needs no approval; any NEW sentence written for the window does.
  `docs/design/measurement_report_limits.md` §11 must be revised in the same
  commit.
- detail: a second, near-identical block still exists at `:6302-6316`
  (`_scope_warnings_html`, `kind == "compliance"`). It is unreachable today
  only because `_one_limit_set` narrows the runs first, and it comes back the
  moment that narrowing changes.

### B8-310 · OPEN · Changing "Judged against" recalculates every saved report, and the SPEC says it must
- blocks release: no
- status: OPEN
- **IT CONTRADICTS A CONFIRMED SPECIFICATION**, see below
- found by: Knut, beta 20: *"This is wrong functionality. If a report has been
  generated, those reports shall not be recalculated if I want to create a new
  report with a different Judged Against threshold set."*
- proof: `~/.claude/jobs/c4ec4e71/tmp/knut-report/proof/B-recalculate-popup.png`
- **THIS IS A SPEC CONFLICT AND MAY NOT SIMPLY BE FIXED.**
  `docs/design/measurement_report_limits.md` §5 says, twice, that choosing a
  set *"recalculates that date's saved reports, archiving them first, exactly
  as the unlock path does"*, and attributes the archive-then-recalculate rule
  to **Knut D23**. His beta-20 ruling overturns his own D23. Per CLAUDE.md the
  specification must be revised, quoted and dated, in the same commit, and it
  needs more than one sentence: §5's whole "locked once a second dated
  verification exists" apparatus exists to keep dates comparable by binding one
  set to a run, and under B8-311 comparability becomes a property of the
  DOCUMENT instead.
- measured, so it need not be re-derived: `_recalculate_run` (`:5830`) copies
  every live `reports/report_*.json` into `reports/old/<stamp>/`
  (content-hash deduped, nothing deleted), re-stamps each with the run's new
  limits and rewrites it in place. On run3 the archived copy kept
  `chromiq_quick` / PASS and the live file became `chromiq_default` / FAIL.
  Nothing on disk goes inconsistent if it stops: `_yardstick_of` (`:4375`)
  already prefers a report's OWN recorded set over the run's, because the run's
  profiling report is deliberately never recalculated.
- open question for Knut: the unlock door (`_on_unlock_toggled:4940`) and the
  limits-window door (`:5745`) also recalculate. He named neither.

### B8-311 · OPEN · A saved report does not remember the settings it was made with
- blocks release: no
- status: OPEN
- found by: Knut, beta 20: *"All reports created must also [be] saved according
  to the selected measurements at the time of creation."*
- detail: a saved report already carries its report type (`report_type`) and
  its limit set (`compliance`). It carries neither checkbox and, crucially, not
  the list of measurements it covered. `_hidden_runs` is session-only by
  design (`:1127`, `:2182`) and the two ticks are read live at `:2439`.
- **AND THE STRUCTURAL PROBLEM CAME FIRST.** A "saved report" today is a
  per-measurement verdict record, not a document. Measured on screen: run1
  with "Show all measurement runs" ticked, ONE press of Generate report wrote
  **11 files**, one per dated verification, and took the pulldown from 11
  entries to 22. Knut's "Current Report Showing" is one entry per DOCUMENT, so
  a document-level record has to exist before the rest of his rework can be
  built. The fields are known (type, set id and label, the thresholds copy, the
  two ticks, and `included` keyed by the three parts of `_run_key`), and the
  block is additive, so `REPORT_SCHEMA` stays 7.

### B8-312 · OPEN · A recalculated report's label is stale for the rest of the session, because the file's mtime never moves
- blocks release: no
- status: OPEN
- found by: the same investigation, not reported by anyone
- detail: `write_json_atomically` calls `shutil.copystat(path, tmp)` when the
  target exists (`core/file_manager.py:797`), which carries `st_mtime` across,
  so a rewrite keeps the file's old timestamp. `_saved_report_label` caches by
  `path.stat().st_mtime_ns` (`:3279`) and therefore never invalidates after a
  recalculation: the entry goes on reading "Quick check" over a file that holds
  `chromiq_default`. A freshly opened window is correct, so it is invisible to
  any test that reopens the dialog. **This is a fault in a fix of my own**:
  the atomic-write helper is B8-301, from this same round.
