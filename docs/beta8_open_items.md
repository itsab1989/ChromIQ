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
- because: researched and answered from ArgyllCMS's own Scenarios.html, which
  names the IT8.7/2 explicitly as the case where shaper+matrix is best — so the
  current default is right. What is open is a FEATURE, not a defect: measure the
  fit after a build (Argyll's yardstick is average dE <= 5, max <= 15, and
  profcheck already runs) and advise cLUT XYZ when shaper+matrix fits poorly.
  Written up in `03-scanner-naming-defaults/PROFILE-TYPE-DEFAULT.md`.
- evidence: —

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
  test_the_window_leaves_the_corners_alone_when_the_check_refuses,
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
- evidence: test_three_rows_of_two_grouped_by_what_each_button_acts_on,
  test_the_block_is_one_row_shorter_than_it_was,
  test_tab_follows_the_visual_order,
  test_the_pop_out_label_is_a_label_and_not_a_sentence,
  test_the_preview_takes_the_height_the_fourth_row_gave_back,
  test_the_button_block_never_decides_how_narrow_the_window_can_be,
  test_the_button_is_reachable_in_the_block_under_the_preview

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
- evidence: test_no_section_of_the_layout_panel_prints_a_paragraph,
  test_no_section_of_the_margin_inspector_prints_a_paragraph,
  test_where_a_label_style_setting_lives_is_on_every_icon_in_that_frame,
  test_the_clip_override_note_rides_on_the_row_it_is_about,
  test_the_clip_note_comes_off_the_icon_when_the_typed_value_is_in_force,
  test_the_marker_notice_no_longer_points_above_itself,
  test_the_marker_help_no_longer_sends_the_reader_under_the_boxes,
  test_the_text_distance_help_no_longer_promises_a_warning_is_shown,
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
