# CR30 beta 1 — FINAL check before tagging ([CR30-B4])

**Scope:** commits `e7eb81f9..eaa6147b` (`30d65ed2` changelog rewrite,
`eaa6147b` R1/R2/E1/E2 fixes + button ordering) on
`feature/cr30-instrument-159`, hostile review before 4.1.5 beta 1.
**Status: COMPLETE**, including PART TWO (the uncommitted work of ~05:50–06:40
that postdates the snapshot, reviewed at the coordinator's request).

## Checklist
- [x] 1. R1 fix — `_on_cr30_device_lost` / `_carry_on_after_the_instrument_went`, both routes; round-3 proof test re-run
- [x] 2. `order_message_box_buttons` — code attack + four windows ON SCREEN, both themes
- [x] 3. E1 fix — `_refresh_calm_subtext` staleness
- [x] 4. E2 fix — `_start_button_name` in every state
- [x] 5. §M note vs binding-spec tests
- [x] 6. Unfixed items from rounds 2–3; truth of `31_round4_fixes.md`
- [x] 7. Fresh-eyes on-screen end-to-end (no hardware commands — instrument asleep on desk)
- [x] 8. Release readiness: version, CHANGELOG factual claims
- [x] 9. `--runslow` gate, once, alone, at the end

## Findings

### 1. R1 fix — VERIFIED FIXED (both routes), with two nits

* `_on_cr30_device_lost` (tab_measure.py:7743-7810): "Carry on" → `_carry_on_after_the_instrument_went(loc)`;
  Stop/dismissal → shared ending window; a real choice returns after `_end_session(choice)`;
  choice None (Keep measuring) falls through to the same carry-on. `_end_session(None)` is a
  no-op (tab_measure.py:6268-6269) — confirmed, so the fall-through is the only continuation.
* Bridge level: on `DeviceLost`, `_on_read_failed` clears `_reading_loc`, leaves `_stopped`
  False and `_awaiting_loc` set (measure_bridge.py:498-505), so `rearm()`
  (measure_bridge.py:373-390) genuinely restarts the read. It cannot resume a stopped
  session (`_stopped` guard) and returns True-without-restarting only when already reading.
* **Round 3's own proof test re-run: 2/2 PASS at head** (it failed 2/2 at `e7eb81f9`).
  Its stub needed the new split-out method bound
  (`_carry_on_after_the_instrument_went`) — bound in the scratchpad copy, not deleted.
* The shipped tests now cover the None answer on both routes, the failed-rearm message,
  and that a real ending still ends (test_cr30_a_gone_instrument_gets_a_window.py).
* Nit 1 (doc): the handler docstring still says the message "says its piece in the log
  for now (§M)" — it now also opens a window; the comment 15 lines below says so. Stale sentence.
* Nit 2 (narrow edge, not blocking): if DeviceLost lands during a pending goto
  (`note_goto` sets `_awaiting_loc=None`), carry-on's `rearm()` returns False and the log
  claims "there is no patch waiting to be read" while the goto's new prompt may still
  arrive and arm itself. Requires instrument loss in the same instant as a navigation
  click; self-heals when the prompt arrives; recoverable via resume either way.

### 2. `order_message_box_buttons` — the helper itself HOLDS; the escape-button semantics around it do NOT

**The helper survives every structural attack** (probe run under the app's real
`WinButtonLayoutStyle("Fusion")` — main.py:147, ui/styles.py:9-14 — offscreen
AND under cocoa; also under bare macos style):

* one button, standard buttons, three buttons: ordered correctly, no raise
* repeated calls: idempotent, exactly one stretch remains (no accumulation)
* show → hide → show: order stays
* buttons still parented to the QDialogButtonBox, `bb.buttons()` intact — no leak, no re-parent
* a button added AFTER ordering lands mid-row — not done anywhere in the app; noted only
* default button unaffected (`Calibrate now` stays default)
* **StyleChange DOES revert the order to the style's own** (measured under macos
  style: Cancel jumped back to x=0 after `setStyleSheet` on the box). Unreachable
  in the app — the four windows are modal and nothing restyles while they stand —
  but a latent trap the docstring does not mention.
* Left-alignment from the trailing stretch is CONSISTENT with the app's other
  message boxes (Fusion+WinLayout renders them left-aligned too — see Basti's
  own proof sheet `~/Desktop/CR30-button-order/REAL-button-order.png`).
* All four windows rendered on screen with the app's real theme pipeline, dark
  and light, real §M body text for the gone window: order correct, legible,
  Cancel/Stop rightmost every time. Shots in scratchpad `b4/shots/` (looked at).

**F-B4-1 — MUST FIX (or consciously ship): closing the dark-reference window
still lets the measurement go ahead — the owner's own complaint, unfixed on the
real Qt path.** Measured with real Qt (offscreen AND cocoa, app's real style,
identical construction to tab_measure.py:7358-7374):

```
Esc      -> clickedButton() == Skip this step
close()  -> clickedButton() == Skip this step   (the red traffic light path)
```

Qt auto-detects the ONLY RejectRole button ("Skip this step") as the escape
button, so Esc and the traffic light CLICK SKIP — `clickedButton()` is never
None for this window, the "CLOSING A WINDOW IS A WITHDRAWAL" branch
(tab_measure.py:7391-7414) is unreachable by any user gesture, and closing the
window proceeds into the measurement ("[NOTE] The black calibration was
skipped… will go ahead"). That is exactly the owner's 2026-08-30 report the
branch claims fixed: *"if i close them via the red traffic light button chromiq
gives me the next window anyway and allows me to go into the measurement"*.
The comment's "measured, not assumed" is wrong for THIS button set, and the
shipped test's premise (test_cr30_black_calibration_flow.py:60: None "is what
Qt reports for the red traffic light / X / Esc") is false — its stubbed box
manufactures the None. A green test guarding the bug. One-line fix:
`box.setEscapeButton(cancel)` (then Esc/X click "Cancel the measurement" and
land in the withdrawal branch). Not verified in the running app because
reaching the black window requires "Calibrate now", which would command the
owner's sleeping instrument — construction-identical synthetic proof only.

**F-B4-2 — the gone and magnet windows cannot be dismissed at all.** With
AcceptRole + DestructiveRole and no RejectRole, Qt finds no escape button: Esc
is ignored and close() is ignored (measured; window stays open). So the whole
dismissal arm of `_on_cr30_device_lost` (clickedButton None) and the magnet
loop's None handling are dead code, the comments "clickedButton() is None for
the red traffic light, the Windows X and Esc alike" describe gestures that do
nothing, and the spec sentence about a dismissal at the gone window describes
an impossible event. Harmless to the user (a modal that must be answered is
defensible), but three comments + one spec line + R2's whole story rest on a
dismissal that cannot happen. Downgrades R2 to moot-in-practice, as round 3
suspected — but for the OPPOSITE reason round 4 recorded.

### 3. E1 fix (`_refresh_calm_subtext`) — could not fault the wiring

Called from `_apply_cr30_dead_options` (tab_measure.py:1461), which runs from
`set_ti1_path` (3379 — "where the chart changes: project open, Profile-run and
Run-type changes, and every cross-tab load all arrive here") and from both
per-target settings-load paths (1305, 1316). CR30-ness is a property of the
chart file (`_chart_is_cr30` → TARGET_INSTRUMENT in the resolved .ti2,
tab_measure.py:5498), so there is no separate "instrument changed" event to
miss; replacing a CR30 chart with a non-CR30 one arrives via the same
`set_ti1_path`. Widget-not-yet-built and widget-destroyed are both handled
(None getattr, RuntimeError catch). On-screen check under item 7.

### 4. E2 fix (`_start_button_name`) — correct in every state I could construct

Reads the live button (`_start_btn.text()`), which
`_refresh_start_button_label` keeps at Start/Continue per the mode's resume
checkbox; falls back to tr("Start Measurement") before the button exists and
after destruction (RuntimeError catch). Only theoretical nit: it does not strip
"&" mnemonics the way `_update_start_tooltip` does — today the button text
never carries one.

### 5. The §M note — form correct, tests green; but TWO §M passages state false measured claims

`tests/test_design_specs_are_binding.py` + `tests/test_message_catalogue.py`:
52 passed, run here. The note sits under "⏳ Awaiting confirmation" with
"Confirmed by: nobody yet", proposes without adopting, and names the honest
alternative — the right form, and "nobody yet" is correct there.

But the spec carries two *(measured)* claims my probes disprove:
* unified_measurement_management.md:1276-1287 (black window): "`clickedButton()`
  is None for all three (measured) … Dismissing a window … now cancels" —
  false; dismissal clicks Skip (F-B4-1). Even the historical account is wrong:
  the OLD two-button window's close also escape-clicked Skip rather than
  returning None; the user-visible fault was the same, the mechanism is not.
* unified_measurement_management.md:1344-1347 (gone window): "Closing the
  window does not end the session — `clickedButton()` is None … a dismissal
  takes the option that changes nothing" — the window cannot be closed at all
  (F-B4-2), so the sentence describes an impossible gesture as measured fact.
Both sections are PROPOSED, not Confirmed, so no binding-spec violation — but
per Knut's rule the discrepancy is REPORTED here, not corrected by me.

### 6. Round 4's own claims, audited

* R1 "both routes now re-arm" — TRUE (verified, §1 above).
* R2 "The code is now what the documentation always claimed" — OVERSOLD. The
  code still routes a dismissal into the ending offer (only a None answer there
  carries on); the doc says a dismissal directly "takes the option that changes
  nothing"; and the measured truth is that no dismissal is possible (F-B4-2).
  Three stories, none quite right — harmless only because the gesture cannot
  happen.
* E1/E2 fixed as claimed — TRUE.
* "applied to all four CR30 windows" — TRUE: exactly 4 call sites
  (tab_measure.py:7129, 7373, 7696, 7786), none elsewhere.
* "The four app-wide OK/Cancel windows are NOT changed" — TRUE (no other call
  sites; Basti's Desktop proof folder since updated by the implementer with a
  third-answer README; an UNEXPLAINED user-side screenshot showing Cancel LEFT
  in the already-measured window is still open there — owner's eyes needed,
  not mine).
* "Three NameErrors in one night" — the new helper uses `_log` correctly, and
  ble.py:27 defines `log`. **But the same class survives one function up:
  `widen_message_box`'s except branch uses bare `log` (ui/widgets.py:922),
  which does not exist in that module (`_log` at 463)** — from 37bfe6aa
  (2026-08-28), pre-dating this review's commits. If its try body ever raises,
  the NameError propagates and the delete windows
  (ui/measurement_target_bar.py:1655 etc.) fail to open. Latent, one-word fix.
* Cosmetic: ~20 call sites now import `order_message_box_buttons` alongside
  `fit_message_box_buttons` and never use it (only the 4 windows do).

### 7. On-screen end-to-end (sandboxed copy of CR30-Test, real MainWindow, dark theme)

Settings ini-sandboxed via conftest's own mechanism (`core.settings.QSettings`
name replaced BEFORE any ui import; `CHROMIQ_PRESETS_DIR` set; working folder
seeded) — so no `cr30_ble_address` existed and only Cancel-family buttons were
ever clicked; the sleeping instrument was never contacted. Project rsync-copied;
`~/ChromIQ/CR30-Test` untouched.

Verified live, screenshots looked at (`scratchpad/b4/shots/`):
* **E1 on screen:** the Keep-calm banner reads "Rest the instrument on the
  highlighted patch and press its button." on the CR30 chart. ✔
* **E2 on screen:** resume ticked → button "Continue Measurement", and after
  cancelling the white window the log's [STOPPED] line names "Continue
  Measurement" — the real path, not a stub. ✔
* **The real white-calibration window**: pictogram (side-bar marker, tile line,
  dashed air step), the black-cal checkbox, and Calibrate now → Cancel with
  Cancel rightmost (x 541 < 690). ✔
* The #134 already-measured dialog renders [OK][Cancel], Cancel rightmost —
  agreeing with the implementer's measurement and NOT with Basti's unexplained
  screenshot (that stays open for his eyes; nothing I ran reproduces Cancel-left).
* Residual round 3 already named, still present and not claimed fixed: the two
  stacked stopped lines ("[STOPPED] You cancelled…" + "Measurement not started:
  the instrument was not calibrated…") say the same thing twice; and Strip
  recognition + Auto render enabled beside the greyed CR30-dead options.
* The no-device/"reader fails to open" path stays code+test-verified only: with
  the owner's live instrument in BLE range, ANY Calibrate-now click (even from a
  sandbox with no remembered address — the scan would find his unit) is a
  hardware command, which this review was forbidden. Same conclusion round 3 drew.

### 8. Release readiness — version, CHANGELOG claims

* `core/version.py` = "4.1.5-beta.1", committed; working tree clean but for this report.
* Platform claims: "macOS over USB and over Bluetooth, and Windows on ARM over
  USB, each with a real instrument and a real chart" — supported
  (24_windows.md: real output on real paper, partial measurement read on the
  ARM64 VM; owner's own macOS BLE sessions in his log). The narrowed honesty
  ("Bluetooth on Windows and everything on Linux … have not been tried") matches
  30d65ed2's stated intent and the evidence.
* Driver section (CH341SER, ARM64 needs 4.0.2026.02+) matches
  docs/cr30_platform_support.md:18-30.
* Magnet section matches the shipped behaviour (refuse + stop + offer recal);
  the BLE per-unit hedge matches the known limitation.
* Dark-reference "one-sided" and "cannot check a white calibration" match code
  and window text seen on screen. (The dark check's WARNING branch has still
  never fired on hardware — the changelog's "it can warn you" is a capability
  claim no hardware has exercised; round 3's 5-second test remains open.)
* **F-B4-3 (wording, worth softening): "A Bluetooth calibration takes about
  three seconds."** Owner's log: best post-fix session 04:51 — found 0.04 s +
  connected 1.08 s + white answered 0.81 s ≈ 2 s, no read-back failure (round
  3's read-back-works claim re-confirmed). But the 04:47 session with the SAME
  remembered address took connected 4.08 s (≈5-6 s click-to-done), and a
  first-ever use scans ~13-15 s. Report 26 warned verbatim that "a beta note
  claiming Bluetooth calibration is now fast would be false". "About three
  seconds" describes the best measured case as the typical one, and the
  Known-limits list omits report 26's UI residual (window closes on Calibrate;
  nothing indicates connecting is in progress). One sentence each would fix both.

**F-B4-4 (doc, in the very function the owner asked to have reviewed): the
helper's docstring tells the story backwards.** ui/widgets.py:929-933 says the
platform rule "puts the confirming action LAST, on the right — … the same as
every OK/Cancel window in ChromIQ (measured 2026-08-30 …)" and that overriding
it "makes one window disagree with the platform and with its siblings". The
implementer's own later measurement (Desktop README, third answer) proves the
opposite: ChromIQ runs `WinButtonLayoutStyle` app-wide (main.py:147), every
OK/Cancel window renders [OK][Cancel] — confirming FIRST, Cancel last — and the
helper therefore does not reverse the app's convention, it enforces it where
three-button roles could not express it. The commit message repeats the same
wrong story ("on macOS that puts the confirming button RIGHTMOST … measured").
Behaviour is right; the recorded reasoning is the first-answer measurement that
the README has since retracted.

### 9. The gate — first run contaminated by a MOVING TREE, then re-run frozen

* **Run 1** (this working tree, no app on screen, no source edits by me):
  `2 failed, 8208 passed, 141 skipped, 3 xfailed in 2:56` — both failures in
  `tests/test_cr30_calibrates_before_measuring.py`
  (`test_cancelling_disarms_the_sound_it_armed`,
  `test_the_skip_rule_is_read_from_the_run_not_the_widget`), both
  `inspect.getsource(TabMeasure._on_start)` tests. The file alone: 9/9 pass;
  both assertions hold against the real source when probed directly.
* **Cause found, not guessed:** during my runs the IMPLEMENTER SESSION was live
  and editing the tree — `ui/tabs/tab_measure.py` mtime moved under me
  (06:19:38), and the working tree acquired an uncommitted WIP of 18 files
  (+496/−78: new `_is_lost_link` / `_warn_dark_reference_looks_wrong` /
  `_plain_instrument_error` work in tab_measure.py, +20 lines in the very test
  file that failed, i18n keys removed/added, spec + messages edits). This is
  CLAUDE.md's documented failure mode verbatim: "Do not edit source files while
  a gate is running… an edit mid-run shifts line offsets and produces failures
  that look like real regressions and are not." The failures indict the moving
  tree, not `eaa6147b`. Also explains the count drift vs the commit message
  (8201 → 8208: tests were being added live).
* A second run against the (still-moving) working tree was killed as
  meaningless. **The authoritative run** was made instead from a frozen
  `git archive eaa6147b` export in the scratchpad (plus the git-ignored helper
  binary and demo TIFFs copied in), with nothing on screen: result recorded
  below.
* Consequence for the release process: the gate that counts must be run at the
  tag commit AFTER the implementer session stops writing — the WIP in flight
  (dark-reference warning work, lost-link classification) is not part of
  `eaa6147b` and was not reviewed here.

### 9b. The authoritative eaa6147b gate numbers (frozen export)

`git archive eaa6147b` into the scratchpad + the git-ignored helper binary and
demo TIFFs, run alone, offscreen:

**8188 passed, 0 failed, 154 skipped, 3 xfailed, 12 errors, 2:56.**

All 12 errors are ONE assertion: the suite's own tripwire "THIS RUN WROTE INTO
THE REAL ~/ChromIQ FOLDER", naming `CR30-Test/runs/run1/CR30-Test.ti3` and
`reports/report_2026-08-30_06-22-12.json` — and those are the OWNER'S OWN LIVE
HARDWARE SESSION writing into his real project at 06:22 while the gate ran (his
reports at 06:09, 06:12, 06:22 and a fresh app session at 06:24:06 are in
~/ChromIQ and chromiq.log; the tripwire watches that folder and cannot tell a
concurrent app from a leaking test). No test failed. The 13-skip delta vs the
tree run (154 vs 141) is unattributed — most plausibly untracked fixtures the
export lacks — and is recorded rather than chased. The gate that counts remains
the implementer's run at the tag commit, alone, which was starting as this was
written.

## PART TWO — the uncommitted work (owner-requested extension)

Scope: the working tree's uncommitted delta over `eaa6147b` (18 modified files
+ `tests/test_the_calibration_notes_survive_the_start.py` +
`docs/cr30_reports/33_the_dark_reference_check.md`), reviewed in place, nothing
edited.

### W1. The moved log clear — CORRECT, one behavioural note

* Exactly ONE `self._log.clear()` remains in tab_measure.py (line 5695, before
  the calibration gate); the old site is a comment. The new test file pins
  clear-before-calibrate AND clear-exactly-once — both good assertions.
* Between the two positions nothing else writes to `self._log` except the
  calibration flow itself (checked the span) — nothing that "should not
  survive" now survives.
* Every route into a start passes `_on_start` once, so one clear covers
  guided/manual/verification/resume alike.
* Behavioural note, not a fault: a CANCELLED start now clears the previous
  session's on-screen log too (before, an early return skipped the old clear
  and the prior log survived a cancel). The [STOPPED] note stands alone on a
  fresh panel — arguably better, but it is a change nobody ruled on.

### W2. The circularity retraction — true, and INCOMPLETE in three places

The new texts (M_CR30_CALIBRATE_BLACK, the healthy [NOTE], the spec retraction)
are accurate: a dark calibration defines zero, the hardware test proves the
check passes the wrong-surface case, and the 0.004 % figure is REAL — owner's
log, 06:18:28: `CR30 dark reference read back at 0.00410 %R (warn above 0.05)`.
But the retraction has not reached everything:

* **F-B4-5 — CHANGELOG.md:52-53 still asserts the retracted claim in the same
  entry that retracts it.** "reads once to check that nothing really does come
  back as nothing … can warn you the dark reference looks too high" stands
  unmodified in "How measuring with a CR30 works", while the new bench section
  below says the check cannot do that. Zero deletions in the CHANGELOG diff —
  the old bullet must be rewritten.
* **F-B4-6 — tests/test_cr30_black_calibration_flow.py::test_nothing_claims_the_calibration_succeeded
  FAILS at the WIP tree** (run here, alone: 1 failed): it still requires the
  removed sentence "not the same as verified" in `_do_black_calibration`'s
  on-screen text. Test and text must move together — the implementer's own gate
  will be red on this.
* **F-B4-7 — tab_measure.py:199-202** (the `_CR30_ZERO_WARN` comment) still
  quotes the removed sentence and calls it "the honest claim". Stale comment.

On the threshold: 0.05 is now a sanity bound, not a surface check, and the
texts say so — defensible, not decoration, provided nothing claims more. The
warn branch has STILL never fired on hardware (the 06:18 test was the pass-when-
it-should-warn proof, which is the finding, not the branch).

**"Answered sensibly" — the coordinator asked directly: it IS a shade too
strong.** What a passing read-back proves: the link was alive, a well-formed
reply frame came back, and its values were ≤0.05 %. What it cannot exclude: the
device's known zero-filled "not finished yet" frame — `read_zero` runs with
`allow_dark=True`, which disables the zero-run truncation guard on exactly this
path (it must, or a real dark reading would be rejected). The event-gated
trigger makes a premature zero-fill unlikely, not impossible. So "the
instrument answered" is provable; "answered sensibly" claims value-level sanity
that a zero-filled frame also satisfies. Suggested wording: "…prove is that the
instrument answered — a complete reply came back with nothing high in it."
Keep the check; soften the adverb.

### W3. The dark-reference warning window — could not fault the mechanics

* Return threading verified end-to-end: `_do_black_calibration` →
  `_run_cr30_black_calibration` (returns the callee's bool, line 7515) →
  `_calibrate_and_confirm` (`if want_black and not …: return False`, 7233) →
  `_on_start` stops. "Carry on anyway" returns True the whole way up and the
  flow reaches the sound/flash/measuring-window. ✔
* Recursion: "Take it again" recurses into `_do_black_calibration`; each level
  costs a click, thread refs are cleared before the window shows so the retry
  starts a fresh worker — no re-entrancy, no unattended loop. Stack depth grows
  one frame per human click; not a hazard. ✔
* The window is Accept+Destructive, so per F-B4-2 it cannot be dismissed at all
  (Esc/X ignored) — a modal that must be answered; consistent with its
  siblings, and this one's docstring makes no dismissal claim. ✔
* Nit: `order_message_box_buttons(box, box.buttons())` re-asserts whatever
  order Qt already chose instead of naming the wanted order like every other
  call site — a no-op that would preserve a wrong order rather than fix it.
  Works today under WinLayout; fragile pattern.

### W4. `_is_lost_link` / `_plain_instrument_error` — the dangerous direction is CLOSED, the safe one leaks

* **False positive (a refusal mis-read as a lost link, stopping a survivable
  measurement): could not construct one.** Checked every raise in
  workflow/cr30/device.py — the refusal vocabulary ("no status reply (N
  bytes)", "cancelled while waiting…", "no button press within Ns…",
  "measurement header not found…", "candidate at i has N zero bands (truncated
  reply)", "the instrument did not return a complete reading (…)") contains
  none of the four `_LOST_LINK_SIGNS` fragments. The signs only appear via
  bleak/pyserial texts wrapped into DeviceLost messages. ✔
* **False negative is real and acknowledged-by-design:** a loss surfacing as a
  timeout ("no button press within 180 s") or an unlisted bleak sentence
  ("failed to connect", "timed out") is still classified as a refusal → the
  black window says "the measurement can go ahead" over a dead link — the
  owner's original complaint, alive for those message shapes. The status quo
  ante, not a regression; the CHANGELOG's flat "no longer tells you the
  measurement can go ahead over a connection that is gone" is therefore a
  little wider than the code — true only when the link's own error names the
  loss. One hedging clause would make it exact.
* `_plain_instrument_error` keeps instrument evidence verbatim and translates
  only the two bleak internals — right rule, correctly scoped.

### W5. The reading now reaches chromiq.log — verified

`log.info("CR30 dark reference read back at …")` at _do_black_calibration;
`_CR30_ZERO_WARN` exists at module scope (line 203) — no NameError this time;
the None case prints "unreadable". And the owner's own 06:18 line proves it
works in the field. The new test pins the logger call. ✔

### W6. The two rewritten brittle tests — equal or stronger

* disarm: asserts inside the actual `if not self._run_cr30_calibration():`
  block up to its `return` — same behaviour pinned, immune to comment growth;
  a stray "return" in a comment inside the block would fail it safe, not pass
  it. ✔
* skip-rule: asserts on the guard line itself. One theoretical soft spot: the
  line-picker takes the FIRST line matching either needle, so a future comment
  above the guard containing "params.disable_initial_cal" could satisfy it —
  fail-open only in a contrived edit; today it grabs the real guard. ✔
* These rewrites also EXPLAIN my gate-1 failures exactly: the old ±600/2000
  character windows were shifted by the WIP's new comment block, so gate 1
  (taken while the tree carried the half-written WIP) failed those two tests
  and nothing else.

### W7. The second delta: the (-r) quotes — PARTIAL, one CR30 place missed

Fixed as claimed: measurement_messages.py:298 (M_CR30_INSTRUMENT_GONE) and
tab_measure.py:7968 (`_carry_on_after_the_instrument_went`) now quote
"Refine / resume existing measurement (-r)". **Missed:
measurement_messages.py:327 — M_CR30_PATCH_GAVE_UP, a CR30 message in the same
feature, still quotes the checkbox without "(-r)".** ("Both places" was three.)
On the two non-CR30 outliers (tab_profile.py:4049, tab_chart.py:10703, plus
measurement_messages.py:991/1007): leaving them was right — they are outside
the feature and the owner asked to be told first. My view: they should follow
the widget text eventually, as one owner-announced consistency sweep, not now.

### The pattern in the three wrong confident answers, named

All three shared one shape: **the proof was run on a cheaper stand-in for the
real thing, and the stand-in's answer was reported with the real thing's
confidence.** Bare Qt stood in for ChromIQ-with-`WinButtonLayoutStyle`; a
dialog never shown stood in for the shown dialog; the code path already
understood stood in for a wall-clock profile of the user's whole interval. Each
time, the condition the stand-in dropped was precisely the thing under test —
and each time the correction came from evidence CLOSER to the user (hardware, a
screenshot, the owner's log). The transferable rule: **a proof must name the
condition that distinguishes the real system from the harness, and show that
condition present in the proof** — and any result obtained under conditions
more convenient than the user's is a hypothesis until measured once under
theirs. (This review was caught by the same shape once tonight: my first
window probes ran under the macos style until the Desktop README revealed the
app's proxy style — the conclusion survived, but only because the probe was
re-run under the real style before being written down.)

## VERDICT — what must be fixed before tagging 4.1.5 beta 1, ranked

Covering BOTH the committed range (`30d65ed2`, `eaa6147b`) and the uncommitted
WIP. Items 1–3 are small and should go in with the WIP commit; nothing here is
data-losing.

1. **F-B4-6 (the WIP breaks its own gate):**
   `test_nothing_claims_the_calibration_succeeded` fails at the WIP tree — the
   retracted sentence is still required by the test. Must be green before any
   tag; the implementer's own solo gate will show it.
2. **F-B4-1 (committed; owner-reported fault still reachable):** Esc/X on the
   dark-reference window CLICK "Skip this step" (Qt escape-button
   auto-detection; measured under the app's real style, offscreen and cocoa) —
   closing the window proceeds into the measurement, the exact behaviour the
   owner reported and the branch believes fixed. The withdrawal branch is
   unreachable; the shipped test manufactures the None it relies on. One line:
   `box.setEscapeButton(cancel)` — plus the same decision made consciously for
   the new W3 warning window and the gone/magnet windows (currently simply
   un-dismissable, F-B4-2, which also falsifies two spec sentences and R2's
   story).
3. **F-B4-5 (WIP, one paragraph): CHANGELOG contradicts itself** — the line
   52-53 bullet still promises the dark check the bench section below retracts;
   and "about three seconds" (F-B4-3) + the unhedged lost-link claim (W4)
   would each take one clause to make exactly true. Soften "answered sensibly"
   (W2) while in there.
4. **F-B4-8 (WIP, tiny): the missed third (-r) quote** in M_CR30_PATCH_GAVE_UP
   (measurement_messages.py:327), and the stale comment at tab_measure.py:199-202
   (F-B4-7).
5. **Not blocking, decide consciously:** widen_message_box's bare `log`
   NameError (ui/widgets.py:922, pre-existing); the helper docstring's
   backwards platform story (F-B4-4); the two stacked [STOPPED] lines; strip
   recognition rendered live on a CR30 chart; the cancelled-start log clear
   (W1 note); ~20 unused `order_message_box_buttons` imports; `_draw_tick`
   corpse.

**Nothing in the committed range eaa6147b blocks beta 1 by itself** — R1/E1/E2
are genuinely fixed (proof test 2/2, live on screen), the button order is real
in the app, and the frozen gate shows 0 failures. The blockers above are one
test/text mismatch inside the WIP, one line of escape-button truth at the black
window, and honesty paragraphs. With 1-4 done and a green solo gate at the tag
commit, tag it.

## Gate numbers (mine)

* Working tree, run 1: 2 failed / 8208 passed / 141 skipped / 3 xfailed, 2:56 —
  INVALID: taken while the implementer session edited the tree (the two
  failures are the old brittle char-window tests against the WIP's grown
  source; see W6).
* Frozen `eaa6147b` export, alone: **8188 passed / 0 failed / 154 skipped /
  3 xfailed / 12 errors (all one tripwire tripped by the owner's concurrent
  live hardware session writing ~/ChromIQ — not a test leak), 2:56.**
* The tree-at-tag gate is the implementer's solo run, in progress as this
  review closed; per his instruction no further gate was started here.
