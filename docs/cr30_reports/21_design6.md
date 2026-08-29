# 21_design6 — [CR30-DESIGN-6] Black-cal in the flow, the tile picture, the phone thief

## In progress
Started 2026-08-29. Read: 20_blackcal.md, 19_design5.md, 17_verify4.md, git log
(967917a6 head). Plan: V1 verify the BLE calibration frames + byte[3] analysis;
V2 challenge the EXP-021 reading; V3 the bb1a/bb1b sync blobs; then the design
(no-Tools black cal, tile picture incl. dark mode, phone-warning placement),
on-screen both themes, ranked backlog. Nothing verified yet.

## V1 — N1 verified, and byte[3] is DECODED: it is a clock, not a result.
Re-parsed ~/Desktop/test.pklg myself with tools/parse_pklg.py (109 ATT PDUs).
The quoted frames are exact. New decodings, all from arithmetic on the trace:

**V1.1 `bb 14` is SET-CLOCK.** The phone writes `bb 14 <u32 LE unix> 01 00 ff ck`
before/after work: values 1788034235/300/316/361 = 2026-08-29 22:10:35..22:12:41
local — and the value deltas match the wall-clock deltas between the writes to
the second (65.412 s wall vs 65 s value; 15.810 vs 16; 44.815 vs 45). The reply
echoes value>>8.

**V1.2 The calibration reply's bytes [3..6] are a u32 LE DEVICE-CLOCK
timestamp** — byte[3] is merely its LOW BYTE. Test: predict
(last bb14 value & ~0xff) + seconds-elapsed-since-that-set:
  white1 reply 0x6a933c11, predicted 0x6a933c11 — exact
  black1 reply 0x6a933c1c, predicted 0x6a933c1d — off by 1 (integer rounding)
  white2 reply 0x6a933d0a, predicted 0x6a933d0a — exact
  black2 reply 0x6a933d0f, predicted 0x6a933d0f — exact
So the "varying byte[3]" (0x11/0x1c/0x0a/0x0f) is seconds ticking, nothing
else. (Why `& ~0xff`: the device evidently applies the set at 256-s
granularity — its bb14 reply echoes only value>>8. Detail HYPOTHESIS; the
fit above is the fact.)

**V1.3 This puts the USB "0x01 success marker" itself in doubt.** The USB
reply (PRIORART-001, all four occurrences, both sequences — re-dumped) is
`bb 11 00 | 00 00 00 01 | 0…0 ff cc`. Same field position [3..6], read as the
same u32 LE = 0x01000000 = 2^24 EXACTLY, identical across two capture days.
And the Windows vendor app NEVER sends bb 14 (cmd census over the whole
PRIORART file: bb01 592, bb10 4, bb11 4, bb13 30, bb17 3, bb21 1, bb28 3 —
no 0x14), so that unit's clock was plausibly never set and sits at a frozen
default. Two rival readings of USB offset 6, and no capture distinguishes
them: (a) status byte 0x01 = success (PROTOCOL.md:161-165, already labelled
HYPOTHESIS there); (b) high byte of an unset RTC reading 2^24 — in which case
NO success indicator exists anywhere. 20_blackcal's "0x01 success marker"
should not be leaned on even for USB.

**V1.4 Is ANY success check available? No. Plainly: we are exactly as blind
as with white calibration.** Over BLE the reply carries [2]=0x00 + the clock;
0x00 has never been contrasted with a failure (none ever captured, either
framing). The only honest observables: a reply arrived at all, ~310-340 ms
after the command (white 326/336 ms, black 308/303 ms — consistent with one
~300 ms acquisition per command, which independently corroborates "each
command performs its own acquisition"); and ChromIQ's own after-the-fact
readings (the zero check for black — 20_blackcal D5 — and nothing for white).
Design consequence: the black flow's self-check (air read) is not optional
decoration; it is the ONLY verification that exists.

**V1.5 The sub-byte 01-vs-00.** Byte[2] is command-specific payload, not
framing (bb 14 uses it as the time's low byte; bb 02 uses 0x10; the phone's
bb 01 trigger uses 00 with 4 random-looking bytes after it — a nonce the
device ignores, since ChromIQ's zero-filled triggers work). For bb 10/11 the
phone sends [2]=01 where the Windows USB app sent [2]=00. Meaning of 01:
UNKNOWN (HYPOTHESIS: app-version or transport difference; we have exactly one
app per framing, so it cannot be attributed). Consequence: if ChromIQ ever
sends these, copy the byte observed on the SAME transport, and treat "does
[2]=00 work over BLE" as untested.

**V1.6 Order and acquisition confirmed as briefed.** WHITE then BLACK, twice,
both runs (22:10:52/22:11:04 and 22:12:50/22:12:55); no trigger frame between
or after either cal command. CALIBRATION.md:340's "black first, per
Pharmacist" is now contradicted by the vendor's own BLE app on this unit AND
matches 20_blackcal F2's finding that the Windows app used both orders —
order is free; the corpus line should say so (correction owed, research repo).

**V1.7 Bonus decode (helps the protocol doc): the BLE trigger reply/press
announcement `bb 01 00 00 01 90 0a 1f` carries the spectral axis** — u16 BE
0x0190 = 400 (start nm), 0x0a = 10 (step), 0x1f = 31 (bands) — the same
declaration the USB `bb 01 09` header carries as `28 1f 0a` (0x28=40 i.e.
400/10, 31 bands, 10 nm). The unsolicited BLE press frame is byte-identical
to a host-trigger reply — over BLE there is NO distinguishing a button press
from a trigger ack by content.

## V2 — N2 challenged: the brief's "proves the listener was not merely
mis-set" is BACKWARDS, and the two artefacts do not even overlap in time.
Facts from disk:
- captures/raw/EXP-021-cross-link.json (the ONLY saved run — the probe
  overwrites its output file, so "two runs" left one artefact): quiet=0,
  phone=0, own_button=0, and the probe's own recorded verdict is
  "LISTENER PROVEN DEAF — … the silence in phase 2 means nothing at all.
  Re-run; do not read anything into this." A positive control that fails
  INVALIDATES the run; it cannot "prove the listener was not mis-set".
  That sentence in the brief inverts the probe's own control logic.
- Timeline (pklg record clock vs the JSON's utc field): the pklg's one
  unsolicited press is at 22:15:34; the saved EXP-021 run STARTED 22:19:12
  and its phase-3 press was ~22:22-23 (file written 22:23). The trace and
  the saved run DO NOT overlap. The pklg is the parallel record of the
  OVERWRITTEN first run (its phone-phase content matches the probe's a-f
  script exactly, twice — the operator did the list twice, hence 2 connects,
  2 cal pairs, 2 measurements, 4 syncs; press at 22:15:34 = run 1 phase 3).
  Run 1's USB-side silence therefore rests on terminal memory, not on any
  artefact.
What SURVIVES, and it is still substantial:
- CORROBORATED: with a phone attached, a button press IS announced over BLE
  and the phone immediately consumes the stored reading (pklg 22:15:34 →
  bb 02 10 → 200-byte spectrum).
- The saved run's identify SUCCEEDED over USB at 22:19 (the JSON exists at
  all only because CR30.open_usb completed) — the cable answered SOLICITED
  traffic minutes before hearing nothing unsolicited. "Port dead/mis-opened"
  is largely excluded.
- The listener DESIGN is proven able to hear a press with no phone attached:
  EXP-CAL-001 (28 Aug, no phone), phase "button press": one unsolicited
  60-byte BB 01 09 frame on the same open+identify+passive-read path.
REMAINING RIVAL the brief did not consider: in BOTH EXP-021 runs the cable
had been idle 3-6 minutes when the press came, while the 28-Aug positive
control had continuous solicited traffic just before its press. "The device
stops announcing on an idle/unpolled USB link" fits every observation with no
phone involvement at all — and would matter to ChromIQ on its own (a long
pause mid-session = deaf cable). So:
- VERDICT: "a connected phone app takes the press exclusively" is the BEST
  reading but is HYPOTHESIS, one rival standing (idle-cable), one artefact
  short (run 1 overwritten). Do not write "steals" as fact anywhere
  user-facing or in the corpus.
- No third run needed TONIGHT; but the consolidated owner session's passive
  listen (20_blackcal step 1) must be upgraded to distinguish the rivals:
  (a) press with phone connected AND cable idle; (b) press with phone
  connected and cable freshly active (send one identify just before);
  (c) press with phone disconnected and cable idle ≥5 min. Three presses,
  ~4 minutes, sends nothing but identify. And the probe must STOP overwriting
  EXP-021-cross-link.json (timestamp the filename) — that is how run 1's
  evidence died.

## V3 — N3 confirmed: the Average setting is NOT in the trace.
Reassembled all four `bb 1a 04` + `bb 1b` sync exchanges (22:11:40, 22:11:56,
22:13:23, 22:13:33 — the a-f list run twice, steps e+f each time): the four
100-byte bb 1b blobs are BYTE-IDENTICAL (same sha256). No other frame type
varies with the toggle either — the only bytes that change anywhere in the
whole trace are bb 14's clock values and the trigger nonces. So either the
toggle never took (operator/app), or Average does not travel over "Sync to
Instrument" at all (app-side, or a different command on a screen not synced).
Blob content, decoded: 8-byte header `bb 1b 01 00 00 00 00 00`, then TEN u32
values of 16384 (0x4000 — as the app's fixed-point/half-float 2.0), then
zeros, `ff 56`. Ten slots of 2.0 = the app's default dE TOLERANCE table
(HYPOTHESIS) — which would make bb 1b the tolerance sync, nothing to do with
Average. Worth another attempt? Only as a passenger in the next owner
session, and only with (i) an on-screen confirmation the toggle actually
changed in the app before each sync, and (ii) one measurement taken under
each state — if Average is device-side, the trigger-to-reply cycle
(~380 ms in this trace, both measurements same setting) should visibly grow.
Not worth a dedicated session; the M1 conclusion (19_design5) that nothing
else in the app touches acquisition still stands.

# D — THE DESIGN, inside the owner's no-Tools-menu ruling

## D1. Black calibration = an OPT-IN inside the calibration window itself —
not a per-target option, and not a second modal on every Start.
The ruling ("part of the measurement process", no Tools entry) kills
20_blackcal D3's placement but not its grounds (F6: zero observed dark
drift; the exposure is slow and rare). The shapes considered:
- (a) Second modal every Start: double friction for a correction with no
  observed need — the owner's own two-popup worry, and 20_blackcal risk 6.
- (b) A per-target measurement option (the instinct in the brief): REJECTED,
  and it is not just a dodge, it is the WRONG CADENCE. A remembered tick
  converts "rarely needed" into "on every Start of this target, forever" —
  users set options once; the target that got the tick pays a blind
  calibration WRITE plus a second modal on every measurement from then on.
  It also adds vocabulary to per_target_settings.md (spec change, owner
  approval, migration questions) for a thing that should not be sticky.
- (c) RECOMMENDED: a checkbox INSIDE the existing M-CR30-CALIBRATE modal —
  "Also take the black calibration afterwards" — unticked on every Start,
  deliberately NOT remembered. House precedent for a checkbox in exactly
  this window family: tab_measure.py:11310 (the replace-warning box,
  `box.setCheckBox(ask)`). Flow when ticked:
    modal 1 (cap ON, white tile) → white cal runs →
    modal 2 M-CR30-CALIBRATE-BLACK (cap OFF, point at nothing) → bb 10 →
    automatic zero check (one air read, port already open, cap already off) →
    how-to window (its cap-off first line becomes a confirmation).
  Cap state changes exactly twice, monotonically (20_blackcal D1 preserved);
  the user who never ticks sees today's flow to the pixel; the second popup
  exists only for the user who asked for it, which answers the two-popup
  worry honestly instead of hiding the step.
  Is the checkbox "part of the measurement process" or a dodge? It is the
  calibration step of the measurement process, where the white calibration
  already lives; the vendor's own app treats black the same way (a wizard
  the user invokes — never per measurement). An option is the honest answer
  BECAUSE the honest frequency is "rarely, deliberately"; the dodge would be
  hiding it behind Tools (overruled) or silently automating a device WRITE
  on a schedule ChromIQ cannot justify (it cannot see the device's dark
  state — 20_blackcal D3's grounds, still true).
- Checkbox label must stay <60 chars (test_message_catalogue.py:347's
  no-own-prose rule — button-length literals pass, sentences do not); the
  EXPLANATION of what black calibration is lives in the §M bodies, where it
  is reviewed. One short body line in M-CR30-CALIBRATE (revision, it is
  PROPOSED so revision is the normal path) mentions the checkbox exists.
- The zero check rides inside the black step and is not offered separately
  (its Tools home is gone; a standalone check can return if the owner ever
  asks). Bonus over the Tools design: the trigger-with-cap-on hazard
  (20_blackcal risk 3) shrinks — the zero check now always runs seconds
  after the window made the user take the cap off, instead of cold from a
  menu; the bit-identical-tile heuristic stays as the guard.
- Guided/Manual: the checkbox lives in the window, so both modes get it with
  zero new panel rows; Manual's "Skip initial calibration" (-N) skips the
  whole window and therefore black too — consistent, nothing new to rule.
- BUILD GATE unchanged: bb 10 has never been sent on this unit and the
  standing never-send rule stands. This design is ready for the owner's
  approval and for the ~15-min session 20_blackcal already scripted; V1.4
  adds one line to that session: record the calibration reply's bytes [3..6]
  and compare to the wall clock (settles the USB 0x01 rival for free).

## D2. The picture: verdict and design
**The owner's specific picture — a white tile then a BLACK tile — must not
be built, because the black tile does not exist.** The CR30's black
reference is AIR (19_design5 R1: the vendor's own wizard says measuring
port downward, 1 m from the ground; no black tile ships with the unit). A
black-tile drawing would teach the user to hunt for a tile, or to present
something dark — the cap's green side being the nearest dark thing to hand,
which is precisely the uncheckable disaster M-CR30-CALIBRATE's text warns
about. The picture worth having teaches the ACTION, not a swatch:
- Window 1 (white): the cap's two faces — white disc ticked, green disc
  crossed. This attacks the one documented spatial hazard ("the cap is
  reversible … a calibration against the green side looks exactly like a
  good one"). Words already say it; a glance shows it.
- Window 2 (black): the instrument nose-down over emptiness — open
  aperture, downward arrow, nothing beneath. That is the whole instruction.
**Dark mode:** his frame idea is right in spirit; the better form is an
outline in the THEME'S FOREGROUND colour, drawn at runtime from the live
palette (house pattern: ui/widgets.py:_is_light_palette and the
palette-driven recolouring in load_tinted_folder_icon). A drawn pictogram
asks the palette at paint time, so both themes are correct by construction
— no *_light.svg sibling pair to keep in step (the assets/ pairs are for
static monochrome glyphs; this picture has semantic colours: literal white,
literal green, near-black, which only the outline needs to adapt around).
**Mechanism — REUSE, nothing invented:** the black window is a QMessageBox
in the house style, and QMessageBox has a designed slot for a picture:
`setIconPixmap`. No custom layout, no HTML <img>, no new window class. The
§M catalogue carries title+body text only; the pictogram is presentation
supplied by the window code, same as the buttons — test_message_catalogue's
rules are untouched. Size derives from fontMetrics().height() (follows the
system font size) with devicePixelRatio applied (crisp on retina); it is a
plain widget child, so window grabs and the screenshot tooling capture it.
**Is a picture the best cue for "the two steps are DIFFERENT"?** No — the
differentiator the house style already uses is the ONE bold/CAPS action
line per window with opposite actions (20_blackcal F8), and that must stay
the primary cue. The pictogram earns its place for the two things words do
badly (cap orientation; "nothing under it") and as a glanceable second
channel. Recommendation: wording first, pictograms as the enhancement — and
this round puts BOTH on screen in BOTH themes so the owner can rule on the
real thing (shots below).

## D3. The phone warning: ONE place — a no-reading WATCHDOG banner, and the
mechanism-agnostic wording is the point.
The four candidates, judged:
- The how-to window (every Start): WORST. The owner's own judgement is that
  the case is rare; the window is already long; and per-Start §M inflation
  is what the catalogue exists to prevent (20_blackcal F10.3 said the line
  earns a place there only if mirroring is PROVEN — V2 shows it is not).
- The no-device help (`measure_bridge.py:_no_device_help`): WRONG TRIGGER.
  In the failure that matters the device OPENED fine and the session runs —
  presses just never arrive. The no-device help never fires there. (Its
  existing BLE hold-hint stays correct and stays put.)
- A troubleshooting entry: honest but unreachable — a user inside a silent
  session does not go reading documentation; nothing tells them anything is
  wrong. That is the definition of this failure.
- RECOMMENDED: the watchdog — when a session has an armed patch and NOTHING
  has arrived for N seconds (propose N=120 s, and only while the device is
  believed present), put a line in the log and a banner on the preview
  (`TiffPreview.set_banner`, ui/tiff_preview.py:1089 — the channel
  17_verify4 F2 already chose for mid-measurement facts), cleared on the
  next reading and re-armed per quiet spell. Not a popup — no §M window, no
  exit-table row; a banner is not a window. Wording names the SYMPTOM and
  the checks, not an unproven mechanism: "Nothing has arrived from the
  instrument for two minutes. If you have been pressing the button: check
  the instrument is still on, and close any phone app connected to it —
  a connected phone can take the readings instead." (§M-PROPOSED as a
  catalogued banner text, since it is user-facing prose.)
  Why it wins: it is the only placement that reaches the user AT the moment
  of failure; it catches the whole symptom CLASS (phone thief, flat
  battery, instrument gone to sleep, the idle-cable rival from V2) without
  asserting which mechanism fired; and it costs nothing on every healthy
  Start. Precedent: the tab already runs a no-response watchdog for
  keystrokes (tab_measure.py:1095, 12 s) — this is the same idea at patch
  cadence. Legitimate long pauses (user makes tea) see one quiet banner,
  not a modal — acceptable, and the banner text's first clause ("if you
  have been pressing") excuses the tea-break reader.
  The troubleshooting/help text can ALSO carry a sentence later for free,
  but the ONE place that answers the brief is the watchdog banner.

## D4. Remaining leftovers — ranked build order (I built nothing; ChromIQ is
read-only for this round)
1. **The agreed window work** (19_design5 D1): how-to window OK rename +
   "Stop the measurement" button + calibration-led first line + close in
   `_close_measurement_windows` — owner-agreed, daily-visible, small, and
   the §M revisions for M-CR30-INSTRUMENT-GONE (drop "start again with
   Refine/resume" for the Keep-measuring path) and V-17's
   M-CR30-PATCH-GAVE-UP (add click-to-re-arm) travel in the same approval
   batch.
2. **Keep-measuring patient reconnect** (19_design5 D2): the quiet 3 s
   retry + visible waiting line, AND the transport-changed announcement
   (banner+log naming transport and device) — one cluster, same code path.
   V2 raises its stakes: a third party in the same space (the phone) makes
   a silent transport switch even less acceptable.
3. **The no-reading watchdog banner** (D3 above) — new this round.
4. **The hygiene batch that must not survive to release**: the two FALSE
   docstrings (calibrate()'s `_previous` claim, device.py:227's
   change-polling claim), ble.py's poll-doctrine overstatement, `_retries`
   not popped on the click-re-arm path, the "1 patch … They are not"
   grammar, the CR30 "using Argyll's default strip recognition" log line.
5. **§M entries for the four flash texts** — ride along with batch 1's §M
   approval round.
6. **Research-repo corrections** (no ChromIQ risk, do any time):
   EXPERIMENTS.md entries for EXP-BLE-012..018, EXP-020, EXP-021 (BOTH
   runs, the overwrite included); the EXP-021 probe must timestamp its
   output filename (V2 — the overwrite is how run 1's evidence died);
   CALIBRATION.md:340 order correction (order is free — V1.6);
   PROTOCOL.md: the 0x01-at-offset-6 rival reading (V1.3), the BLE
   vocabulary from tonight's trace (bb 14 set-clock, bb 02 10 read,
   bb 1a/bb 1b sync, 10/100/200-byte BLE framing, the trigger-reply axis
   decode V1.7), and the calibration-reply timestamp decode (V1.2).
7. **Black calibration build** (D1) — design ready, §M texts ready for the
   approval queue, but the BUILD stays gated on the owner session (bb 10
   never sent here; standing rule not lifted). Nothing above waits on it.
Q-A remembered address/port stays on the list after these (17 s/session +
wrong-device risk), unchanged from 19_design5's ranking.

## C — coordinator's mid-round corpus update (commit 29da1e5), answered
1. **The lamp/window caveat (EXP-020 COMPROMISED): I am keeping it as
   PRUDENCE, labelled as such — option 1.** Grounds that owe nothing to
   EXP-020: a dark reference is by definition a reading of "no light", so
   any light entering the open aperture while it is taken contaminates it —
   that is arithmetic on (S−D)/(W−D), not a measurement claim; the vendor's
   own instruction (port downward, 1 m up) is the same prudence; and the
   clause costs one line. What changes: the §M-PROPOSED note for
   M-CR30-CALIBRATE-BLACK must carry "the bright-light clause is prudence,
   not a measured threshold — EXP-020 is compromised and no light-entry
   threshold has been measured on this unit", so the sentence can never be
   promoted into a spec as measured behaviour. The window sentence itself
   stays imperative ("Do it away from bright light…") — an instruction to a
   user carries no provenance claim; the provenance lives in the catalogue
   note and the report. NO redo asked of the owner for this alone: the
   instruction is identical whichever way a redo came out. If the
   freshness-enforced redo happens anyway (it is already step 3 of the
   consolidated session, and it also answers whether the firmware subtracts
   lamp-off per reading), the 0.05 %R zero-check threshold stops being
   provisional — that is its real payoff, not the window text.
2. **bb 10/bb 11 now permitted in a designed session.** D1's build gate
   softens from "blocked on a standing rule" to "waiting for the designed
   session to be RUN, backlog first per the owner". Ranking unchanged —
   black-cal build stays behind the window work, the reconnect cluster, the
   watchdog and the hygiene batch, exactly as he asked. The session script
   is 20_blackcal's, plus V1.4's one addition: record the calibration
   replies byte-for-byte and compare bytes [3..6] to the wall clock — his
   unit's clock was SET tonight (bb 14, 22:10), so a USB cal reply carrying
   current time would settle V1.3's frozen-RTC rival at zero extra cost.
3. **EXP-BLE-016's "byte 3 … meaning NOT DETERMINED" is now superseded by
   V1.2**: it is the low byte of a u32 LE device-clock timestamp at reply
   bytes [3..6] (arithmetic fit exact on 3 of 4, ±1 s on the fourth).
   The entry's conclusion stands — no success check may be built on it —
   but the corpus should take the decode (and V1.3's consequence for the
   USB 0x01 reading) rather than leave the byte mysterious. Handed up, not
   edited in place: corpus edits are the coordinator's to commit.

## ON-SCREEN — done, real app, real styling, BOTH themes
Driver: scratchpad/onscreen/drive_design6.py (sandbox mirroring
tests/conftest 322c3d20: QSettings→ini, CHROMIQ_PRESETS_DIR, custom output
path, trash no-op; project is a COPY of CR30-Test; real ~/ChromIQ untouched;
120 s hard watchdog; QMessageBox.exec patched to shoot-and-return so no
button is clicked and no device I/O occurs — the CR30 on the cable was never
spoken to). Run twice, CHROMIQ_DRIVER_THEME=dark then =light.
Shots in ~/Desktop/CR30-test-shots/ (looked at, not just saved):
- cr30_design6_01_calibrate_real_{dark,light}.png (+ _fullscreen variants):
  the REAL M-CR30-CALIBRATE window from `_run_cr30_calibration`, both
  themes — the light variant had never been captured before; legible in
  both.
- cr30_design6_02_white_mock_checkbox_{dark,light}.png: MOCKUP of D1's
  checkbox ("Also take the black calibration afterwards", 44 chars, under
  the body per the house checkbox precedent) plus D2's cap pictogram
  (white face ticked, green face crossed). Verified by eye: in dark mode
  the white disc carries itself against the dark ground; in light mode the
  foreground-colour ring carries it — one drawing, no theme conditionals,
  legible both ways. (Mockup nit: the tick clips the white disc's edge by a
  pixel or two — final art is the implementer's.)
- cr30_design6_03_black_mock_{dark,light}.png: MOCKUP of
  M-CR30-CALIBRATE-BLACK (20_blackcal D6 text, last line adjusted to "the
  white calibration you just took is kept either way" for the new in-flow
  position) with the nose-down/open-aperture/arrow pictogram via
  QMessageBox.setIconPixmap. The near-black aperture — the owner's exact
  dark-mode worry — reads in dark mode because of its foreground ring, and
  as a solid dark ellipse in light mode. Both verified by eye.
Mockup texts live ONLY in the driver; nothing was added to the app or the
catalogue (§M rule intact; ChromIQ repo untouched — `git status` shows only the
untracked report files 20_blackcal.md and 21_design6.md).

## STATUS: COMPLETE — verdicts and ranked backlog in the final message.

## OWNER DELIVERABLE — the eight-variant choice set (requested mid-round)
Folder: ~/Desktop/CR30-calibration-graphics/ — 64 PNGs + README.txt.
Renderer: scratchpad/onscreen/render_cal_graphics2.py (ChromIQ untouched).
- 8 white-step variants (all on the "cap ON, WHITE face, never green" cue)
  and 8 black-step variants (all on the "cap OFF, nose-down over nothing"
  cue) — NO black-tile drawing, per D2's ruling, and the README says why.
- Each variant × 4 renders: `_swatch_light/_dark` on the app's REAL
  message-window ground (sampled from the themed app: light #eeece8 /
  #22211f fg, dark #181818 / #e6e6e6 fg — not guessed), and
  `_inwindow_light/_dark` seated in the REAL QMessageBox (real palette,
  fonts, M-CR30-CALIBRATE text + proposed checkbox for white; the
  D6-draft text for black; grabbed with WA_DontShowOnScreen, verified by
  eye — the dark in-window renders carry full dark styling).
- Variants span: theme-fg outline, the owner's fixed-frame idea, true
  drop-shadow (fixed mid-round: it originally still drew the outline, so
  it wasn't the shadow-only comparison the README claimed — now it is,
  and the dark row honestly shows the shadow vanishing), seated-in-cap,
  on-instrument, captioned, minimal, floor-line, crossed-cap,
  nothing-marks, and a numbered both-steps pair with the active step
  dashed.
- README notes scaling (all font-metric derived, all survive the
  screenshot/help tooling), the caption-is-a-label-in-the-app caveat, and
  repeats the recommendation (white_01_two-faces + black_01_outline)
  beside the alternatives so his choice is informed, not steered.
