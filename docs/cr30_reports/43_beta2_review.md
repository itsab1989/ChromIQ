# Report 43 — Review of v4.1.5-beta.2 candidate (master @ 378ec745)

**Reviewer:** Claude (reviewing agent), 2026-08-30.
**Status: COMPLETE. Verdict at the end: NO — three proven faults in the new keyboard-trigger / tile-learning work, each small to fix.**

Scope: the 16 commits in `v4.1.5-beta.1..HEAD` (8c4eaa94..378ec745), every diff read.
Constraints honoured: no app launch, no serial/BLE device opened, no `--runslow` gate,
no writes to `~/ChromIQ/CR30-Test`, no plist touched, no source edits. Evidence is
targeted offscreen pytest plus code reading; every finding is labelled PROVEN
(something I ran) or INFERENCE.

Proving tests are in **`tests/test_cr30_review43_stale_trigger.py`** — run
`QT_QPA_PLATFORM=offscreen pytest tests/test_cr30_review43_stale_trigger.py --runxfail`
to see all three faults fail live (3 failed, 0.73 s). With their
`xfail(strict=True)` markers the file is green (3 xfailed), so the everyday tier
stays green, and the markers start FAILING the moment each fault is fixed, so
they cannot outlive the fixes.

What I ran, all green before my additions: `test_message_catalogue.py` +
`test_i18n.py` + `test_design_specs_are_binding.py` (123 passed), and all 14
new/changed CR30 test files from the diff (108 passed).

---

## 1. The learned magnet guard (0f03b34a) — sound core, two edges to know about

**Can a real patch be refused? No — PROVEN by arithmetic on the shipped constants,
INFERENCE that the constants describe the hardware (they come from your measured
facts).** The learned comparison is 0.001 %R per band across all 31 bands; genuine
repeat noise is 0.05 %R (50x), so a real patch can only match a *correctly* learned
signature by being the tile constant itself — which is the detection working. The
built-in `TILE_SIGNATURE` fallback still runs beside a learned value
(`looks_like_calibration_tile` falls through), unchanged at 0.05, same as beta.1.
The 4-vs-6-decimal point is a non-issue: the built-in constant is compared at 0.05
where the 5th decimal cannot matter, and learned values are captured from the
parsers' own `round(x, 6)` and stored via JSON at full precision, consistent with
the 0.001 tolerance.

**Learning provenance — USB is airtight, BLE has an unproven ordering assumption.
INFERENCE.** USB: `TileLearner.offer` accepts `gate_flag is True`, and
`button_header_is_gated` refuses solicited frames (byte 58 must be 0x00), so the
proof really is the device's own unsolicited header. BLE: the bit-identical rule is
correct *given* that the stored slot is updated before the `bb 01 00` event frame is
pushed. That ordering has never been measured, and the codebase itself believes
stale slot reads happen (the `identical_to(previous)` guard exists for exactly
that). If the event can outrun the slot update, press 2's read returns press 1's
bytes — bit-identical — and two *uncapped* presses on a patch (a user ignoring the
dialog) would arm the guard with a patch colour. Consequence of a wrongly armed
guard is not "a patch refused" (0.001 corridor, unreachable by real readings); it is
that `trigger_allowed()` turns True on a unit whose real tile the guard no longer
recognises — the exact state the trigger gate exists to prevent. Cheap hardening
for beta 3: refuse to `remember_signature` a value that does not look like a white
tile (say mean 60–100 %R and shaped near the built-in constant within a few %R);
the true tile always passes, a coloured patch never does.

**Can a second instrument inherit the first's signature? YES — through the
"exactly one signature arms an unidentified unit" rule. PROVEN by code path,
INFERENCE on likelihood.** Over BLE `unit_id` is *never* populated:

- fast path: `identify()` runs but takes the id from `transport.name`, which is
  None (the path never scans) — `device.py:227`;
- discovery path: `BleTransport.open` stores `self.address = target` but never
  sets `self.name` from the candidate it chose (`ble.py:242`), and `_open_ble`'s
  discovery branch never calls `identify()` at all.

So every BLE session arms through `learned_signature(None)`. Owner of one unit:
correct and intended. Owner of two units, one learned: unit B inherits A's
signature, `guard_is_armed` goes True, the keyboard trigger unlocks — and a
magnet-gated trigger on B returns B's constant, which matches neither A's learned
value (0.001) nor the built-in (4.69 %R away), so a gated reading is **accepted as
a patch**. The stated invariant "failure direction is always unarmed" is violated
precisely here. Button presses on B are no worse than beta.1 (BLE never had a
flag); what is new is the trigger being *enabled* where its guard cannot see.
Two-CR30 owners are rare; this can wait for beta 3, but it needs Basti's ruling:
either store the advertised name with the remembered address (discovery has it in
hand) and key on it, or require the arming key to match before allowing the
trigger on an unidentified unit.

**A same-unit wart, safe direction (INFERENCE, code-read):** a unit learned over
BLE is stored under `""`; the same unit over USB (keyed by `Identity.device_id`)
finds nothing, is offered learning again, and the second entry makes the store
size 2 — after which the "exactly one" rule leaves the BLE fast path unarmed
forever, taking the keyboard trigger with it. Degradation only, beta 3.

**`_previous` and `for_learning` discipline: correct. PROVEN by code read +
the shipped suite.** Both transports' learning paths call `validate()` but not
`check_usable`, and neither writes `_previous` (USB: `enforce=False`; BLE:
`_read_when_ready` uses `enforce=False` and the learning return skips the
`_previous = m` line). `check_usable`'s order is right: `gate_flag` first, tile
second, zero-run and bit-identical last — so a gated repeat is classified
MagnetGated (stop, recalibrate) rather than "no new measurement" (re-arm, invite
another press).

## 2. The keyboard trigger (98b9179d + 3bdb1045) — one real fault, the rest holds

**FAULT 1 (PROVEN): a stale trigger request auto-fires the next patch's read.**
`tests/test_cr30_review43_stale_trigger.py::test_a_stale_trigger_request_does_not_fire_on_the_next_patch`
drives the real `CR30.read_next_measurement` and the real
`DeviceReader.request_trigger`/`_take_trigger_request` over a silent fake port:
with the flag set and nobody pressing anything, the trigger frame goes out on the
**first loop iteration** of the next read (the test's fake port records the
`transact` of the trigger frame; expected outcome was the button-press timeout).
`_trigger_requested` has no owner and is cleared only by consumption — never on
abandonment, failure, give-up, or `stop()`. Two real entries:

- **Wide:** after `read_gave_up` (5 failed reads, e.g. repeated early lifts) the
  session deliberately survives, `_dev` stays open, `awaiting_loc` stays set, and
  nothing is listening (`_on_cr30_gave_up` is non-modal, tab_measure.py:8148). Space
  is accepted (see fault 2), flashes "Taking the reading — keep the instrument
  still." — a lie — and plants the flag. The user then clicks the patch to carry
  on; the new read consumes the stale flag and fires the instrument at whatever it
  is sitting on, possibly mid-air or the previous patch. If the values are
  plausible and differ from `_previous`, the reading is **sent as the patch value,
  silently** — the exact mislabelling this module's own docstring exists to
  prevent.
- **Narrow (~20 ms):** Space immediately followed by click-to-jump — the abandoned
  read exits via the `cancelled` check *before* the `trigger_wanted` check, so the
  flag survives into the jump target's read and fires while the operator is still
  moving the instrument.

Fix is small: clear the flag whenever a read ends without consuming it (a
`finally` in `read_next_measurement`, or clear in `abandon_current`/`cancel`),
and/or make the request generation-scoped.

**FAULT 2 (PROVEN): the give-up state still invites Space.**
`::test_after_giving_up_the_key_routing_predicate_stops_inviting_space` drives the
real `Cr30MeasureBridge` through five genuine worker-thread failures to
`read_gave_up` and shows `awaiting_loc` still set while `armed_for()` is False —
the tab's routing predicate (`awaiting_loc is not None`, tab_measure.py:11127)
accepts Space with nothing listening. This is the arming half of fault 1; fix
together (route on `armed_for(awaiting_loc)`, or clear `awaiting_loc` on give-up).

**The rest of the attack list, cleared:**

- *Plain-bool flag soundness:* under the GIL the swap in `_take_trigger_request`
  is safe against tearing and double-fire; the worst race is a keypress landing
  between the tuple's load and store being overwritten — one lost keystroke, user
  presses again. Acceptable. (INFERENCE, code-read.)
- *`bytes_waiting()` losing a frame between check and read:* no. The probe only
  gates *entry* into `receive`; once entered, `receive` blocks up to
  `min(left, 1.0) s`, and a 60-byte frame at the CR30's rate arrives in
  milliseconds, so a frame that begins between probe and read is collected whole.
  A frame straddling the very end of the 180 s budget is lost — inherent and
  harmless. The `-1 = cannot say` convention and the AttributeError-vs-raise
  distinction are covered by the shipped
  `test_cr30_the_keyboard_trigger_is_prompt.py` (runs green here). (PROVEN for the
  shipped behaviour, INFERENCE for the straddle analysis.)
- *CPU burn:* USB waits at 50 Hz on `in_waiting` (20 ms sleeps); the BLE branch's
  `min(left, 0.1)` slices run the asyncio loop with 50 ms `asyncio.sleep`s — no
  busy loop, no starvation. (INFERENCE, code-read.)
- *`trigger_and_read` (unused by the UI):* lock held correctly across trigger +
  read. Note for whenever it grows a caller: on BLE it reads immediately after the
  0x01 acknowledgement without `_read_when_ready`'s busy-retry, so a slow slot
  update on the *first* read of a session (`_previous is None`) could return the
  stale stored value. Not reachable today. (INFERENCE.)
- *Solicited trigger cannot fake the gate flag:* PROVEN by code —
  `button_header_is_gated` returns None unless byte 58 is 0x00, so the
  trigger path's reply can never set `gate_flag` and the learned tile is,
  as designed, the only guard on a triggered read. Refusal when unarmed is
  enforced in both `request_trigger` and `trigger_and_read`.

## 3. Key routing (378ec745) — the predicate is right for warnings, wrong for give-up

The narrowing to `awaiting_loc is not None` does fix the defect it chased: in a
CR30 `-xx` session a questioned reading blocks the helper at its retry prompt
*before* the next `spot_ready` can be sent, so while a Space/Enter warning is
answerable, `awaiting_loc` is None and the keys fall through to
`self._manager.send_key` as before. Instrument-position warnings cannot occur in
`-xx` (no instrument is opened), and ChromIQ's own refusal windows are modal, so
the tab never sees those keys. The fix was a genuine fix, not a move. (INFERENCE
from the helper protocol as implemented in `measure_manager.py` — the helper
cannot emit `spot_ready` while blocked at a prompt; I found no path that has both
a live prompt and an answerable warning.)

The predicate's remaining gap is fault 2 above: `awaiting_loc` also survives
states where nothing is listening. It should be `awaiting_loc is not None and
bridge.armed_for(bridge.awaiting_loc)`.

## 4. Remembered BLE address identified (1de3f3af) — matches report 41's spec. PROVEN

All four of report 41's Q5/Q6 requirements are in `DeviceReader._open_ble`:
identify before trust, remember only *after* identify, close on failure so the
scan can find the device again, and the fallback never hands the failed
`self._address` straight back (`address=None if self._address == remembered else
self._address` — with `remembered = self._address or …` this is always None when
an explicit address failed, which is the specified behaviour). The discovery
branch's remember-without-second-identify is now sound because 2c21d329 removed
the unconfirmed-candidates fallback (confirmed-only, one retry, and an honest
error naming what was seen). The shipped test
`test_ble_remembered_address_is_identified.py` is the one report 41 staged: fakes
`bleak` in `sys.modules`, identity reply as a hex literal from a capture, asserts
no `bb 11`/`bb 10` calibration frame ever reaches a stranger — 196 lines, runs
green here.

## 5. Message text and catalogs (a55a28de, 4a8876f2) — held, with one doc drift

**PROVEN green:** `test_message_catalogue.py`, `test_i18n.py`,
`test_design_specs_are_binding.py` — 123 passed. Both new messages
(`M-CR30-LEARN-TILE`, `M-CR30-TRIGGER-NOT-ARMED`) are `approved=False` in code,
in the catalogue dict, in the design document's awaiting-review header and full
§M-PROPOSED sections, and in the test's `AWAITING_APPROVAL` set. The i18n test's
missing/stale/placeholder checks pass on all 12 catalogs, the resume checkbox
widgets really are labelled "(-r)" (tab_measure.py:2199/2664), and the help-card
untranslated budget change is tested.

**Drift (report, do not just fix — §M discipline):** the "(-r)" migration updated
the *code* text of seven messages but the design document's quoted texts in only
one of them. `unified_measurement_management.md` lines 262, 640, 697, 1073, 1483,
1828 still quote the checkbox without "(-r)" while the code (and the on-screen
windows) now say "(-r)" — and line 697 is **M-REPLACE-PARTIAL, an approved
message whose on-screen wording was changed without the spec moving with it**.
The change is obviously right in substance (it makes the quote match the widget),
but the binding-specs rule says this needs Basti's nod and the document updated in
the same breath. One-line-each doc edit; do it with the tag.

## 6. Everything else in the diff

- **Quit fix (c508fec5 + 80966c4a):** `MainWindow._tab_measure` and
  `TabMeasure._manager` both resolve (verified by grep at main_window.py:239 and
  tab_measure.py:899), `note_app_quitting` exists, and
  `test_quitting_does_not_run_the_session_finish.py` drives the real lookup on a
  real window — green here. The cleanup comment correctly keeps the finish
  handler running (the §3b reconciliation Knut specified). PROVEN.
- **DTR/RTS held low before open (7aeb9776):** correct pyserial idiom
  (`ser.dtr = False` before `open()`); the CR30 was shown not to need the lines.
  No regression risk seen. PROVEN by the shipped `test_usb_does_not_greenlight_any_ch340.py`
  (green) plus code read.
- **BLE confirmed-only (2c21d329):** removes the accept-anything fallback,
  retries once, refuses with a named list. Good, and it is what makes item 4's
  discovery branch sound.
- **"Chart names no instrument" log correction (1bfaffec/0ac6cbf5):** wording
  only, wrapped in `tr()`, tested. Fine.
- **No guard was weakened:** `check_usable`'s order is unchanged apart from the
  added `learned_tile` pass-through; `enforce=False` paths still never write
  `_previous`; the USB `enforce` branch now mirrors BLE's accepted-only baseline
  rule (an improvement).

**FAULT 3 (PROVEN): over Bluetooth, the learning flow throws away the press it
just asked for.**
`::test_ble_learning_collects_the_press_made_before_the_dialog_was_answered`:
the dialog says "press the button on the instrument once … [I have pressed it]".
The press happens while the dialog is up; bleak has queued it; `learn_tile` →
`read_next_measurement(for_learning=True)` → the BLE branch's unconditional
`drop_events()` pumps the loop and **discards that press** (the test run's own
log shows `CR30: discarded 1 reading taken before this patch was armed`), then
waits up to 90 s for presses nobody told the user to make — with no progress UI,
no `on_press` wired, and `on_dropped` unset on this path, so it is silent. Two
further capped presses would still succeed (bit-identical rule), but nothing says
so. USB is unaffected (the buffered header is collected). Failure direction is
safe — the learn fails, the guard stays as it was — but the headline flow of this
beta cannot succeed over BLE as instructed. Fix: skip the drop (or harvest the
queued events) when `for_learning`, and wire `on_press` feedback.

**Beta-polish notes (no faults):** `_offer_cr30_tile_learning` waits in a
`processEvents` loop with no progress dialog and no cancel for up to 90 s
(`learn_tile` is called with `cancelled=None`; only closing the reader breaks it
out, and `close()`'s 2 s lock timeout covers that). Livable for a beta whose
tester knows the feature; should grow a small progress/cancel affordance before
GA.

---

## VERDICT: NO — do not tag v4.1.5-beta.2 yet

Three proven faults sit inside the exact features this beta exists to test, and
two of them can write a wrong colour into a `.ti3` silently or make the new
feature fail its own instructions:

**Must fix before tagging (all small):**
1. **Stale trigger request auto-fires** (finding 1, `measure_bridge.py` /
   `device.py`): clear `_trigger_requested` whenever a read ends without
   consuming it (and on `abandon_current`/`cancel`). This is a silent
   wrong-surface reading recorded as a patch — the one failure class this whole
   module was built to prevent.
2. **Give-up state accepts Space** (finding 2, `tab_measure.py:11127` /
   bridge): route on `armed_for` (or clear `awaiting_loc` on give-up) so the
   "Taking the reading" flash cannot lie and cannot plant fault 1's flag.
3. **BLE learning drops the asked-for press** (finding 3, `device.py` BLE
   branch): do not `drop_events()` on a `for_learning` read — the queued press
   is the datum. Without this, the beta's headline feature stalls silently over
   Bluetooth for anyone who follows the dialog's own instructions.

With those three fixed (flip my xfail markers off and the proving tests must
pass), plus the one-line doc-quote updates from section 5, I would give beta.2 a
green light — everything else in the diff held up under attack, and the shipped
test coverage for this round is genuinely good (real objects, transport-edge
fakes, mutation-aware).

**Can wait for beta 3 (rank order):**
1. The "exactly one signature" rule can enable the keyboard trigger on a second,
   unlearned unit (section 1) — needs Basti's ruling; store/key the advertised
   BLE name, or gate the trigger on a matching key.
2. Learned-value plausibility band in `remember_signature`, closing the
   uncapped-presses + stale-slot mis-arm (section 1, INFERENCE-level risk).
3. BLE/USB dual learning of one unit leaves a `""` store entry that permanently
   disarms the BLE fast path (section 1) — degradation only.
4. Progress/cancel UI for the learning wait; wire `on_press`.
5. Design-doc "(-r)" quote updates if not done with the tag (section 5).

**Not blocking, for the record:** EXP-MEAS-004's completion (host trigger and
button bit-identical when gated) is correctly reflected in the code comments and
in `trigger_allowed`'s reasoning; report 42's "specified, not run" note is
superseded. `TILE_SIGNATURE`'s 4 decimals are harmless at its 0.05 tolerance.
