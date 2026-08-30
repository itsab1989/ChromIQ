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

---

# Re-check after 0945855b (staged — if this section ends without a verdict, the re-check was killed mid-way)

Scope: commit 0945855b only (5 files: the three fixes, the rewritten proving
tests, this report). Tree clean at re-check time. Sections appended as
completed:

- R1. Fix 1 — request needs a read to belong to — PENDING
- R2. Fix 2 — routing on `armed_for` — PENDING
- R3. Fix 3 — no event drop on a learning read — PENDING
- R4. Audit of the rewritten tests — PENDING
- R5. Re-verdict — PENDING

## R1. Fix 1 — a request needs a read to belong to. HOLDS, one microsecond-class residual

**PROVEN green:** the reworked test plus my two new ones (below) pass;
`test_cr30_the_keyboard_trigger_is_prompt.py` still passes (the prompt-latency
behaviour is intact).

**Every-path audit of `_reading_in_flight` (code-read, PROVEN by test for the
paths that matter):** it is set and cleared at exactly one site, the
try/finally around the read in `DeviceReader.__call__` — so a normal return, a
refusal, a cancel, an abandoned generation, and the DeviceLost re-raise all
pass through the same `finally`, which also kills any unconsumed request.
`learn_tile` and `calibrate` never set it, which is correct: no keyboard
trigger belongs in either. `trigger_and_read` (still unused by the UI) neither
sets nor consults it and does not need to — it takes its reading synchronously
under the lock; a concurrent `request_trigger` during it returns False, which
is sensible. Its pre-existing BLE first-read staleness note from the original
review stands, unreachable today.

**The plain bool: I agree, with one stated residual.** Each field has a single
writer per transition and no read-modify-write on the GUI side except the
check-then-set in `request_trigger` — and that pair is the residual: if the
read completes in the microseconds between the GUI evaluating
`_reading_in_flight` (True) and storing `_trigger_requested = True`, the store
lands after the finally cleared it, and the next read fires it. That is the
original fault reduced from two wide-open states to a true race requiring
Space in the same instant a reading completes — vanishing probability, same
consequence class. A generation-scoped request token would close it airtight;
beta 3, not a blocker. The lost-update direction (a refused or overwritten
keystroke) costs one press, as claimed.

**Wrong-patch consumption: closed.** A request accepted for patch A either
fires while A's read is in flight (right patch; if the user then navigates,
the bridge drops the value as DROPPED_NAVIGATING), or the abandoned read exits
via its cancelled check — which runs BEFORE the trigger check — and the
finally clears the flag, so nothing crosses into B's read. PROVEN for the
crossing case by `test_a_request_pending_when_its_read_dies_is_cleared_by_that_read`.

## R2. Fix 2 — routing on `armed_for`. HOLDS; the bridge should NOT change; one wrong-message wart

**Coverage of the press window (code-read):** `_reading_loc` is set
synchronously inside `_start_read`, which runs inside the same GUI-thread slot
as `on_patch_ready` and as the re-arm tail of `_on_read_failed` — no event-loop
turn happens between clearing and re-setting, so there is no instant in which
a keystroke can land during a re-arm gap. A genuine instrument press is never
governed by this filter at all. The give-up, device-lost and magnet states all
leave `armed_for` False, which is exactly when nothing is listening.

**On the bridge question: keep it as you have it.** `awaiting_loc` means "the
helper's outstanding prompt", which a give-up does not retract — and
`resume_after_magnet`/`rearm` genuinely need it afterwards. My original test's
demand (awaiting_loc alone must mean "listening") was the wrong altitude; the
tab asking `armed_for` is the right fix. No change requested.

**Wart (minor, beta 3):** between `armed_for` going True and the worker thread
actually setting `_reading_in_flight` (milliseconds, since the calibration flow
has already opened the device), and again in the window between a worker-side
failure and its queued GUI delivery, Space passes the filter but
`request_trigger` returns False — and `_cr30_reading_from_the_keyboard` then
shows M-CR30-TRIGGER-NOT-ARMED, whose text claims the tile is not learned,
on an instrument whose tile IS learned. Once per session (it latches to a
status flash afterwards). No data hazard, self-corrects on the next press.
Cheap fix: ask `reader.guard_is_armed` before choosing the message, and say
"not ready for that patch yet — press again" when the guard is armed.

## R3. Fix 3 — no event drop on a learning read. RIGHT FIX; it hardens one abuse path into a deterministic one — beta-3 item upgraded

The skip is correctly scoped (`for_learning` only; normal patch reads still
drop), the false "discarded a press" report is gone with it, and the shipped
test proves the asked-for press is now collected. PROVEN.

**Stale-inheritance analysis (INFERENCE, code-read against the hardware facts):**
events carry no values — every read fetches the CURRENT stored slot — so
nothing historical can be "replayed"; a genuine earlier gated pair cannot be
re-presented as proof. The learning call site sits immediately after the white
calibration, which zero-fills the slot, so stale queued events from before the
flow resolve to zero-filled reads that the learner never sees (the read-back
retries, then the learn aborts to the safe "could not learn this time" path).
A press made during the dialog with the cap ON — the instructed flow — reads
the tile, and even several such reads agree because a gated slot is
bit-identical by nature. All safe.

**But you asked about TWO stale identical events, and the honest answer is
yes, with double user error:** two uncapped presses made during the dialog
leave two queued events and ONE final acquisition in the slot; the two learning
reads then both fetch that single acquisition, so they are bit-identical **by
construction** — the pair rule's premise (two independent acquisitions never
match) is bypassed, and whatever the slot holds (paper, a patch) is learned as
the tile. Before this fix that path needed an unproven slot-update race; it is
now deterministic. It still requires ignoring "LEAVE THE CAP ON … press once"
twice over, inside the dialog's lifetime, after the calibration zeroed the
slot. Consequence if hit is the bad direction (guard armed wrong, trigger
enabled, a real magnet invisible). Two cheap closures for beta 3, either
sufficient: (a) the tile-plausibility band on `remember_signature` from the
original review (kills every non-white surface); (b) in a learning read,
treat pre-queued events as at most ONE press — the second half of a pair must
arrive after the first read, restoring the two-acquisitions premise. I
recommend both before GA; for a beta whose testers know the flow, not a
blocker.

## R4. Audit of the rewritten tests — not softened in intent, but finding 1's rewrite had lost half its teeth; closed with two new mutation-proven tests

- **Finding 1 rewrite:** the True→False precondition flip is correct under the
  new contract and is itself the stronger assertion. **But** the behavioural
  tail (`not port.triggered`) became vacuous for the `finally`-clear half of
  the fix — nothing sets the flag any more, so nothing could fire regardless —
  and no test anywhere else leaves a request pending when a read exits, nor
  proves `request_trigger` ever says YES at the reader level (the tab-level
  accept guard uses a plain-function reader, not `DeviceReader`). Two
  mutations would have passed the entire suite: delete the finally's
  `_trigger_requested = False`, or never set `_reading_in_flight = True`
  (feature dead). **Closed:**
  `tests/test_cr30_trigger_request_dies_with_its_read.py` (new, 2 tests, both
  green on master). Both mutations were APPLIED in a scratchpad copy of the
  repo (never the working tree) and each was caught by exactly its intended
  assertion — the mutation-must-land rule satisfied by execution, with the
  mutated line visible in the failing traceback.
- **Finding 2 rewrite:** stronger than mine, and the right altitude — it
  drives the real `TabMeasure.eventFilter` unbound over a stand-in carrying
  the real bridge in a genuinely given-up state, asserts the key is refused
  AND still forwarded to the manager (not swallowed), pre-asserts that
  `awaiting_loc` survives (so the test cannot go vacuous if the bridge ever
  changes), and the accept-direction mutation guard releases and joins its
  reader thread. Nothing softened.
- **Finding 3:** unchanged apart from the marker. Not softened.
- **Marker removal after each XPASS:** correct protocol; the strict markers
  did their job.

## R5. Re-verdict

Everything else in the 16 commits was re-confirmed unaffected by 0945855b
(it touched only the three fix sites, the test file, and this report):
catalogue/§M, quit-fix, and the full CR30 targeted suite re-run green here —
83 + 59 tests across the two sweeps, plus the 123 catalogue/i18n/spec tests
from the first pass, all passing.

**One pre-tag mechanical note:** `core/version.py` still reads `4.1.5-beta.1`.
The release process bumps it BEFORE the gate — do that with the tag.

### GREEN LIGHT for v4.1.5-beta.2

All three review-43 faults are genuinely fixed — each fix verified against the
real objects, each fix's mutation proven to land and be caught — and no fix
introduced a regression I could find. Bump the version, run your gate, tag.

**Beta-3 list, re-stated and re-ranked (top two already with Basti):**
1. *(Basti's ruling)* The "exactly one signature ⇒ arm an unidentified unit"
   rule can enable the keyboard trigger on a second, unlearned unit over BLE —
   store/key the advertised BLE name, or gate the trigger on a matching key.
2. *(Basti's ruling)* Six design-doc quotes of the resume checkbox still lack
   "(-r)" while approved code strings carry it (`unified_measurement_management.md`
   262, 640, 697, 1073, 1483, 1828).
3. Learning mis-arm hardening, upgraded by R3: tile-plausibility band in
   `remember_signature` AND/OR at-most-one pre-queued event per learning read.
4. Generation-scoped trigger request (closes R1's microsecond residual).
5. Wrong-message wart: `_cr30_reading_from_the_keyboard` shows
   M-CR30-TRIGGER-NOT-ARMED on an armed instrument in the ms-wide
   not-yet-in-flight window — pick the message by `guard_is_armed`.
6. BLE `unit_id` never populated (fast path has no name; discovery never
   identifies) + the `""`-key dual-transport entry that permanently disarms
   the BLE fast path once a unit is learned over both transports.
7. Learning-wait progress/cancel UI; wire `on_press`.

---

# Second re-check: f1ea856e (address as signature key, doc quotes) and 1c67698a (changelog)

Staged; verdict at the end of this section. Tree at 1c67698a, clean,
`core/version.py` = 4.1.5-beta.2.

## S1. The Bluetooth address as the signature key — the mechanism HOLDS; verified, not accepted

**The platform claim checks out.** `docs/cr30_reports/23_live.md` (lines
253–257) says precisely what the commit cites: "the stored address is a
CoreBluetooth UUID on macOS and a MAC elsewhere — per-host". PROVEN by reading
the cited source.

**Address populated at arm time — verified in `ble.py` and then PROVEN on the
real stack.** Code-read first: `BleTransport.address` is set in `__init__`
(explicit/remembered paths) and in `open()` *before* connecting on the
discovery path (`self.address = target`, ble.py:242), and `_arm_tile_guard`
runs only after `_open_ble` returns an opened transport — so on every BLE path
the address exists when the key is computed. The remembered value is
`str(value) or None` and discovery addresses come from bleak non-empty, so no
empty-string key. Then proven end-to-end: **new file
`tests/test_cr30_ble_address_key_is_live_at_arm_time.py`** (4 tests, green)
drives the real `DeviceReader._open()` → `CR30.open_ble` → `BleTransport`
over the report-41 fake-bleak harness and shows: the guard arms from
`ble:<address>` on the fast path with the scan forbidden, and after discovery;
`learn_tile`'s key and `_arm_tile_guard`'s key are the same string for the
same session; and a signature stored for a *different* address arms nothing.

**Can the fallback silently reopen the hole?** Only where `_signature_key`
returns None, and on every production path it cannot: BLE always has the
address (above); both production USB paths (`remembered port`, and discovery
inside `open_usb`) call `identify()` before acceptance, so `unit_id` is the
serial. The one path with neither is an explicit `port=`/`address=`
constructor argument — no production caller passes one (same finding as
report 41). INFERENCE, code-read.

**Different keys for learn vs arm?** No. Both call the same static
`_signature_key(dev)` on the same device object, and `_arm_tile_guard` runs on
every open (including the one `learn_tile` performs), refreshing
`reader.unit_id`; the `or self.unit_id` fallbacks only fire when the key is
None (non-production paths). Pinned by the third new test so a future
asymmetry cannot file signatures nobody finds. PROVEN.

**`ble:` prefix vs USB serials:** `Identity.device_id` is the unit's own id
string (shape "CM454M0223"); a serial spelled `ble:<something>` is not a real
format, and even a collision would merely merge two keys, in the safe
direction. Non-issue.

**Failure direction:** holds. A key that stops matching (pairing reset changes
the CoreBluetooth UUID; another Mac; BLE privacy randomisation) lands on "no
signature, guard unarmed, learning offered again" — every owner's position
today. The only way to arm a unit with a foreign constant is now a genuine
address collision between two CR30s on one host (random UUIDs / distinct
MACs — vanishing), and even then the bad outcome is the pre-existing "trigger
enabled while the tile check is blind", never a refused patch: a real patch
matching a foreign constant across 31 bands at 0.001 %R cannot happen (units
in evidence 4.69 %R apart). One residual worth naming: a signature learned
during beta.2 testing BEFORE f1ea856e sits under the `""` key, is orphaned by
the new keys (arming looks it up by key, never by the "" entry), and the
session is simply offered learning again — safe, one extra learning step for
anyone who tested the un-keyed build. That is the owner and nobody else.

**The shipped tests, audited:** the `_Dev` stand-in mirrors exactly the two
attributes `_signature_key` reads, so it is a faithful mirror of that
function's surface — but it IS too thin to prove the integration claim (that
the real stack delivers those attributes at arm time), which is precisely the
claim the owner asked about. That gap is now closed by my end-to-end file
(above). The "fallback removed → tests fail" claim was re-verified by applying
the mutation in a scratchpad copy: `return None` in place of the `ble:` branch
is caught by **four** parametrised failures across the two test functions that
matter, including the second-instrument-stays-unarmed safety property. The
commit's "two of them fail" undercounts its own tests; the protection is real.

## S2. The design-document (-r) quotes — DONE, discipline followed

PROVEN: zero unmigrated quotes remain (`grep` finds no "resume existing
measurement" without "(-r)"; seven carry it), the catalogue/spec/i18n tests
pass (66 + 123 across the sweeps), and no message's *meaning* changed — every
edit is the quotation of the widget's own label, which the widgets have
carried since 4a8876f2. The ruling is recorded in the commit message; since
the reasoning must stay off GitHub, that is the right place, and this report
carries the cross-reference.

## S3. The changelog (1c67698a) — one promise is false over Bluetooth

`test_release_notes.py` passes; the entry renders. The numbers check out
against the measured record: 4.69 %R between units (PRIORART-001), 94x the
0.05 tolerance (4.69/0.05 = 93.8), 0.5 %R button press vs 0.05 %R untouched
noise (EXP-TILE-003/004), "three experiments" for the capped press
(EXP-TILE-002/003/004). "A capped press does not move the white reference" is
a shade stronger than the record (the record shows non-monotonic shifts
attributable to repositioning, i.e. *does not damage*), acceptable as written.

**But "One press with the cap on" promises behaviour that is not built over
Bluetooth.** BLE has no gate flag, so the learner needs TWO bit-identical
presses by design (`TileLearner.offer`); fix 3 collects the press made before
the dialog is answered, and then the loop waits — up to 90 s, silently, with
`on_press` unwired and no on-screen prompt — for a second press the user was
told would not be needed ("press the button on the instrument once. That is
all."). An instruction-following Bluetooth user gets "could not learn this
time" every session, forever: fail-SAFE, but the beta's headline feature is
effectively USB-only as instructed. The M-CR30-LEARN-TILE window body and the
changelog both carry the one-press promise; the Known issues section does not
mention it. Over USB one press is genuinely enough (gate flag) — the sentence
is true there.

## S4. Verdict on the tag

Everything else is ready: version bumped, release commits in, 113 tests green
across this re-check's sweep, both new-commit mechanisms verified and
mutation-proven.

### NO — one wording fix short of green

**The shortest list that makes it yes (one item):**

1. Make the one-press promise honest about Bluetooth in the release page:
   qualify the "New" bullet (e.g. "one press with the cap on — two over
   Bluetooth, where the instrument cannot flag the press as capped") and add a
   Known-issues line saying that over Bluetooth ChromIQ does not yet prompt
   for the second press, so press twice with the cap on. Changelog only; no
   source change, no re-review needed — say the word and this report's verdict
   is GREEN LIGHT.

The in-app M-CR30-LEARN-TILE body carries the same false promise; it is
§M-PROPOSED (unapproved), so the wording fix goes through the owner with the
document — recommended for beta 3 together with wiring `on_press` so the
second press is actually prompted on screen.

**Beta-3 list, updated:**
1. Learning over Bluetooth: wire `on_press`, prompt for the second press, and
   revise M-CR30-LEARN-TILE's body (owner's §M review) — supersedes the old
   "progress/cancel UI" item and subsumes S3's changelog qualifier.
2. Learning mis-arm hardening (upgraded in R3): tile-plausibility band in
   `remember_signature` AND/OR at-most-one pre-queued event per learning read.
3. Generation-scoped trigger request (closes R1's microsecond residual).
4. Wrong-message wart: M-CR30-TRIGGER-NOT-ARMED shown on an armed instrument
   in the ms-wide not-yet-in-flight window — pick the message by
   `guard_is_armed`.
5. Housekeeping: the orphaned `""` signature entry from pre-f1ea856e learning
   (harmless; clear it when a keyed signature is stored). The old item 6
   (dual-transport learning permanently disarming the BLE fast path) is
   RESOLVED by f1ea856e — each transport's key now finds its own entry.
