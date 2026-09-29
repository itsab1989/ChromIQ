# Challenge of "Create Chart: Final Assessment and Decisions" and IMPLEMENTATION-READINESS.md

Challenger: a third agent, read-only, 2026-09-07, against master 80975e65 (clean tree).
Sources read: both documents under challenge, AGENT2-review-report.md, AGENT1-final-assessment.md,
all 29 F-files, the R-files cited below, both briefs, CLAUDE.md, per_target_settings.md (4a, 10),
dev_margin_inspector.md, dev_builtin_presets.md, and the memory files behind the five rulings.
Every line number and count below was re-checked with grep in the repository.

Verdict key: DROPPED / WRONG / OVERSTATED / UNCLEAR / MISSING DECISION / OK.
Totals: 4 DROPPED, 8 WRONG, 9 OVERSTATED, 8 UNCLEAR, 3 MISSING DECISION, 8 OK.

## a. Completeness

1. OK. All 29 Agent 1 findings and all 10 distinct Agent 2 items (N-1, 2, 3, 4, 6, 7, 8, 9, 10, 11)
   appear in Part 2; the three folded items (N-5, N-12, N-13) appear inside P5, P8 and P11c. All 16
   of Agent 1's questions and all 10 of Agent 2's map to a Part 3 decision or an explicit "no decision".
2. DROPPED. N-9 (R-103, "Show strip indicators" off frees no space) survives only as half a sentence
   in P10a. It has no fix, no decision and no line in any Part 4 list or in the recommended order.
   Fix: one line in P12 and in the Improvements list ("free the band, or say in the help it stays").
3. DROPPED. Agent 2 observations that vanished entirely: the (i) help buttons are not reachable by
   keyboard (checkpoint 03; the memory says the tab-order audit is still pending); the Pages control
   stops at 20 while the engine builds 22 and 36 pages (R-021 note); "-f 0" is accepted and builds a
   22-patch chart of neutrals without a word; Save as Defaults gives no visible feedback with the log
   hidden; the expert-row preview shows "-f0 ... -g28" while the command that ran was "-f550 ... -g31".
   Fix: five one-line entries under P12 or a "noted, not filed" list, so nobody counts them as unseen.
4. DROPPED. P1 is the item the brief and the memory already call "the deeper ordering cause, open and
   awaiting the owner" (project_build_in_flight_clobber: `_adopt_new_run_settings` ... "awaiting
   Basti's ruling"); R-003 says so in plain words. The document never tells the owner that P1 is that
   known item, and Part 1's list of known items leaves it out. Fix: one sentence in P1 and in Part 1.
5. DROPPED. dev_margin_inspector.md records Basti's own ruling of 2026-08-26 (#171: "known,
   deliberately not fixed ... do not fix it without asking"), and its example is a red Guided sheet
   with Top 27.2 < 38, which is one of the "four new red defaults" (i1Pro Letter landscape). R-018
   cites #171; P2 and Decision 1 do not. The same document also describes an option it considered
   ("colour against whichever minimum is stricter and name which one failed") that is absent from
   Decision 1. Fix: cite #171 in P2, say one red default was already on record, add that option.

## b. Fidelity

6. OVERSTATED. P3 "Cause (INFERRED, reproduced offline by both)": Agent 1 reproduced it offline;
   R-001 records a code check only. Fix: "reproduced offline by Agent 1, confirmed in code by Agent 2".
7. OVERSTATED. P12 and Part 4 say a foreign 304-patch set "was laid out into another project".
   R-104 qualifies this: it happens only through the session-restore path, "not one a user takes
   between projects in one session ... a driver-only reproduction today"; the real Open Project route
   leaves only a stale row. Keep the qualifier, or the owner reads a user-facing data bug where the
   reviewer found a latent one. Part 4 also lists F-028 as confirmed although nobody re-tested it.
8. WRONG. "Five help texts" (P12, Part 4): F-022 lists six, the sixth being the Instrument Limits
   introduction. Agent 1's summary said five; the finding file says six. Fix: six.
9. OVERSTATED. Part 4 "zero CRITICAL log records in about 200 builds": the CRITICAL count is Agent 1's,
   for 150 builds; Agent 2's report never states one. Fix: "in Agent 1's 150; no crash in Agent 2's 45".
10. OK. Agent 2's corrections are all kept: F-018 has no clamp (P2, Decision 1); F-003's mechanism
    and the §4a reading (P1); F-025's frames were placeholders and exports/ is the real loss (P6);
    F-014's preflight runs in Preferences (P9); F-011's OK acts as No (P12). The UNKNOWN sub-claim of
    F-003 is named in Part 1.
11. UNCLEAR. P1 and Decision 2 say the specification "already says the screen wins" and that only a
    confirmation is needed. Section 4a says two things: Knut's prose ("can be modified by user ...
    then all these settings are copied") and its own rule table, whose N-3 reads "Generate Chart
    copies IT [the block] into the new run and clears it", which is exactly what the code does. The
    spec disagrees with itself, and the whole of 4a carries "Status: awaiting confirmation". Fix: say
    so, and say Option A also rewrites N-3. That is more than a confirmation.
12. WRONG. P2 and Decision 1 A give the cost as "every Guided landscape sheet" changing. i1Pro 3 Plus
    A4 PORTRAIT is also red (Left 26 < 28, Right 8 < 9, R-018), so portrait geometry changes too.
13. MISSING DECISION (a trade-off the options hide). Guided today equals printtarg to the patch for
    i1Pro A4 and for i1Pro 3 Plus A4 landscape (parity table, "exact"). Decision 1 A must end that
    parity for the red combos, yet Part 4 lists "Guided parity with printtarg (4 combos)" as a thing
    to protect. Fix: state in Option A's cons "Guided will no longer match printtarg for these sheets".
14. OVERSTATED. P1 "Pressing Generate again would build a different chart": inferred from the
    mechanism, not observed (Agent 2's variant B re-unticked the box first). Mark it "would (inferred)".

## c. Rulings and specifications

15. OVERSTATED. Decision 13 recommends B, a confirmation window when a typed name switches projects.
    The deferral memory says "do not implement, do not re-analyse, do not raise it again unasked", the
    brief says "do not propose to overturn a ruling", and the standing rule for design rulings is
    "default = change nothing". Asking whether the deferral reaches across projects is fair;
    recommending a new window is not. Fix: recommendation A (leave as is), question kept.
16. WRONG by omission. Decision 8: the i1Pro "by Pharmacist" built-in fails bottom 19 mm and its
    strip is 248.9 mm. The 19 mm bottom is the DELIBERATE ruling (re-confirmed 2026-08-23) whose whole
    reason is the 240 mm jig pass (297 - 38 - 19 = 240). So by the owner's own arithmetic this chart
    exceeds the jig by 8.9 mm; the document softens that to "the chart may really be marginal", and
    Option C "adjust the seeds" would touch the 19 mm row without saying so. Fix: state 248.9 > 240
    plainly, exclude the 19 mm row from Option C, and say Decision 1 B touches landscape rows only.
17. MISSING DECISION (who decides). The document addresses "you" as Basti (it credits him with the
    2026-09-02 deferral), yet calls the seed rows "your jig numbers" (Decisions 1 B, 3). The i1Pro seeds
    use Knut's 11 mm run-up, the 19 mm was added at Knut's request, and §4a and §10 are Knut's words;
    the standing rule routes #130 design-spec rulings to Knut, with Basti deciding process and
    implementation. Nothing says which of the 16 decisions are Basti's alone. Fix: mark 1 B, 2, 3, 8
    and 14e "Knut's numbers or spec: ask him", keep the rest with Basti.
18. OK. Helper markers, the page-label reclaim and Guided-on-engine are untouched by every option;
    the i1Pro 19 mm survives as long as item 16 is fixed.

## d. Decisions

19. OVERSTATED (need for a decision). Decisions 15 and 16 are engineering approvals; P5 itself says
    "Your decision needed: no (approach is engineering)" and then files Decision 16. Decision 7 (stash
    exports) and 11 b (an Escape key) are the same kind. Fix: fold 7, 11 b, 15, 16 into one line,
    "engineering fixes, approve as a block", and keep Part 3 for design.
20. UNCLEAR. Decision 10 recommends B without its reason (the code comment says the coupling was meant
    as a first-time default, so B is the intent restored); Decision 12 recommends "refuse Generate"
    with no evidence over "ask" or "untick and say so". Fix: give the reason in 10; in 12 give one or
    offer none.
21. MISSING DECISION. Two small design questions nobody asks: raise the Pages control above 20 or show
    "more than 20" (R-021 note), and whether the indicator band is freed when indicators are off
    (R-103). Both fit Decision 14.
22. OK, with a note. Decision 6's "above about 5,000 patches" and the example floors (4.5 mm, 4 mm)
    are Agent 1's guesses; the document presents them as examples, which is fair, but should say they
    are unmeasured.
23. UNCLEAR. Decision 4 A "rare, default 0" for stored recipes with a non-zero cap is asserted, not
    counted; a grep over the owner's presets and chart sidecars would settle it in a minute.

## e. Plain language

24. UNCLEAR. Undefined shorthand: "i1", "p3", "CM" (P12 F-006 "on i1 A3 and p3 A4", P11c "the CM
    seeds"); "seed rows" and "seeds" are never defined (the built-in starting values of the Instrument
    Limits table); "targen" (P8, Decision 6); "spin" (P7); "the §M-PROPOSED list" (P8, P12, Part 4);
    "stack trace" (Part 1, P1); "hook" (Decision 1); "by-grid and patch-first" (P3); "schema-1
    migration", "session restore", "--runslow gate" (Part 4, Steps 0 and 5); "sidecar" (Decision 7).
    Fix: a six-line glossary after the evidence grades; spell out the instrument names per section.
25. OK. The decision document contains no em dash (checked by code point). The readiness document has
    one, line 8, inside the quoted filename; either drop the quoted name or note it is the owner's.
26. UNCLEAR. Sentences a non-programmer will not follow: P1 "the engine's 'convert printtarg settings'
    step faithfully carries them on"; P5 "'a build is in flight' is inferred from the button being
    disabled"; P3 "size for a capacity fill"; Decision 2 "fix at the cause in the adoption step";
    Decision 16 "the live preview reads the same flag". Rewrite each as what the user sees.

## f. The readiness plan

27. OK. Thirty cited definitions match master 80975e65 exactly: tab_chart.py `_on_generate` 12905,
    `_collect_params` 19062, `_align_current_run_to_target` 16747, `_adopt_new_run_settings` 14720,
    `_on_target_changed` 16828, `_on_generate_finished` 17040, `save_target_settings` 14295,
    `_engine_geom` 12236, `_partial_last_page_blank` 18401, `_estimate_patch_total` 17350,
    `_onscreen_patch_total` 17404, `_refresh_gamut_state` 15822, `_switch_mode` 6721,
    `_chart_build_in_flight` 18581, `eventFilter` 13405, `_show_restored_chart_after_a_stop` 17018,
    `area_target_count` 18133..18144, `run.meta` at 16446, `_on_guided_precond_toggled` 7160,
    `_on_manual_engine_toggled` 5027, `_make_guided_panel` 3629, `_on_preset_selected` 8655,
    `_revert_preset_combo` 8020, `_refresh_manual_command_preview` 5249; chart_creator.py
    `_apply_margin_thresholds` 1394 (no caller anywhere), `_engine_build_kwargs` 1246, `_finish` 787;
    test at test_chart_creator_engine.py:232; main_window `_open_settings` 2344; layout panel
    `_sync_instr_margins` 2914; file_manager `settle_chart_stash` 924/2187, `reset_chart_artefacts`
    2208, `meta_path` 2120; margin_inspector_panel `_update_status` 512; raster.py 1292/1295;
    chart.py 235. settings_dialog.py:5652 is the import line, the call is at 5659 (fine). One note:
    Agent 2's R-files carry different numbers (13250, 13183, 16892, 17302, 15840); they are call sites
    inside the same functions, not a stale commit. Say so, or a reader will distrust one set.
28. WRONG. `tests/test_engine_info_line*.py` does not exist; it is cited four times (regression-net
    table, P3, P7, P11). The info-line tests live in `tests/test_layout_options_panel.py`. The "220
    layout + creator tests" count is right (220 across tests/test_layout_*.py and
    test_chart_creator_engine.py).
29. WRONG. "13 translation catalogues" (both documents, several places): there are 12
    (`data/i18n/*.json` and 12 `parameters.<code>.yaml`). Thirteen is the language count with English.
30. WRONG. "thirteen places" for Generate's enabled state (P5, Part 4 regression risks, inherited from
    Agent 1): grep finds 12 `_generate_btn.setEnabled` sites, and the readiness plan says 12. Make
    the two documents agree.
31. OVERSTATED (the net's adequacy). P5: two tests simulate a build by disabling the button
    (`tests/test_a_build_can_be_stopped.py`, `tests/test_live_preview_does_not_replace_a_preset.py`)
    and three read `_chart_build_in_flight`. Once an explicit flag replaces the button read, those
    simulations go inert and pass while testing nothing; the memory already warns of exactly this.
    Also unstated: what the central rule does while a Tools-menu Argyll job holds the shared runner.
    Fix: name the three files and the runner case in P5's regression net.
32. OVERSTATED (P6 "Cons: none of note"). The plan says "include exports/ (and cache/)" in the stash.
    cache/ holds `new_run.json`, the §4a seed block (rule N-4), which today is deleted by every build;
    restoring cache/ on failure brings a consumed block back and interacts with N-1 and N-3. Fix:
    stash exports/ only, or explain why cache/ is safe.
33. WRONG. P2 "test first": an xfail asserting "every Guided default passes its table" encodes
    Decision 1 Option A before it is taken, opposite to the shipped test at line 232. Write that test
    after the decision. P1, P3 and P5 test-first entries are adequate (P1 should add "Overwrite run N
    unchanged" as a test, not only a driver).
34. OK, with a restriction. Branch step 1 (xfail tests, "ask first") is a repo change that enters the
    release gate; the owner said no app code changes and the plan rightly asks. The repo does use
    xfail markers to document open spec gaps, so the idea is in character, but only for correctness
    items (P3, P4, P6, P7, F-012, F-029), never for option-encoding ones (P2, Decisions 3, 4, 9, 10).
35. UNCLEAR. Step 1 "no-decision items" includes P8 and F-011, whose new sentences need §M-PROPOSED
    approval (a human gate), and F-022, which renames Guided's controls (user-facing text, and the
    names may be Knut's). Fix: split step 1 into "no new text" and "needs §M text".

## g. Anything else

36. WRONG (minor). Part 1 says Agent 2 wrote "11 drivers"; the review report says ten (r_lib.py is a
    library, not a driver). Ten scripts plus the library are on disk.
37. OVERSTATED (minor). Part 1 "Every dialog was answered by a script that first checked which dialog
    it was": Agent 1 logged eight unexpected dialogs closed through their own Cancel/OK, and two of
    Agent 2's drivers blocked and were killed. No human clicked, so the conclusion stands; the method
    sentence should say "expected dialogs by name; unexpected ones closed and logged".
38. UNCLEAR. Part 4 "REGRESSION RISKS" and the readiness plan disagree on the setEnabled count (item
    30) and on where the info-line tests live (item 28); a reader who checks one number and finds it
    wrong will doubt the rest.
39. OK. Numbers that agree with the sources: 150 + 45 builds ("about 200"), 261 + 60 screenshots
    ("about 320"), verdicts 20/5/0/4, 66 of 66 Auto-count builds, 4 parity combos (3 exact, CM by the
    accepted reclaim), 3 fresh runs for P1, 9 Guided defaults by the reviewer.

## Top 5 fixes the coordinator should make before handing this to the owner

1. Route the decisions to the right person: mark Decisions 1 B, 2, 3, 8 and 14e as Knut's numbers or
   Knut's spec, and fold the engineering approvals (7, 11 b, 15, 16) into one "approve as a block" line.
2. Reframe P1 / Decision 2: say the spec's prose and its rule N-3 disagree, that 4a is still
   awaiting confirmation, and that P1 is the already-known "deeper ordering cause" the owner was told
   was open.
3. Repair P2 / Decision 1: cite Basti's #171 ruling and its considered option, correct "landscape
   only" (p3 portrait is red too), and state that Option A ends Guided/printtarg parity for those sheets.
4. Respect the rulings in Decisions 8 and 13: write 248.9 > 240 plainly, keep the 19 mm row out of
   Option C, and change Decision 13's recommendation to "leave as is" per the deferral.
5. Fix the numbers and names in both documents: 12 catalogues not 13, 12 setEnabled sites not thirteen,
   six help texts not five, ten drivers not eleven, `tests/test_layout_options_panel.py` in place of
   the non-existent `test_engine_info_line*.py`, and add a six-line glossary for i1/p3/CM, seeds,
   targen, §M-PROPOSED, sidecar and the gate.
