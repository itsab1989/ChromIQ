# 12 — SKEPTIC 2

Round 2 review, `feature/cr30-instrument-159`, HEAD `6295c91a`.
S-numbers below refer to `11_skeptic.md`; new findings are **T-numbers**.

> **⚠ THE WORKING TREE IS LIVE WHILE I READ IT.** At 23:16 `git status` was
> clean but for my own report file. At 23:18:33 it was
> `M ui/tabs/tab_measure.py` (+37 −13), and `git blame` on the Save-and-stop
> window returned *"Not Committed Yet, 2026-08-28 23:18:27"*. The implementer is
> editing the same checkout I am auditing. **Every line number in this report is
> a moving target**; I cite function names as well as lines wherever it matters.
> It also means CLAUDE.md's *"do not edit source files while a gate is running"*
> applies to anyone who starts a gate tonight.
>
> **And this file was swept into commit `8223020c` at 600 of its 959 lines** by
> someone's `git add` while I was still writing it. Nothing was lost — the rest
> is in the working tree — but that is the hazard MEMORY records as *"never
> `git add -A` while an agent is writing"*, and it happened again tonight.

---

## STATUS

- [x] Read 11_skeptic.md, 11_EVIDENCE.md, git log
- [x] Verified what the six fix commits did and did not close
- [x] Section C — re-verified every open S-number
- [x] Section A — the calibration-first plan, challenged
- [x] Section B — S28/S31, challenged
- [ ] Section D — F2 on screen
- [ ] On-screen run + screenshots to ~/Desktop

---

# PART 0 — regression check on the six fixes

I verified each commit did what it claims and looked for what it broke.

## Verified GOOD, no regression found

| commit | what I checked | verdict |
|---|---|---|
| `c8122ecb` | `Cr30MeasureBridge.stop` (`measure_bridge.py:240-253`) now calls `reader.cancel()`; `DeviceReader.close` (`:398-425`) cancels first then `acquire(timeout=2.0)` and closes the device either way; `_on_read_failed` (`:277-288`) returns early when `_stopped` | correct, and the `getattr` duck-typing keeps every test double working |
| `243cee7c` | `device.py:181-192` separates `TransportTimeout`/`ShortFrameError` (keep waiting) from everything else (`DeviceLost`); same distinction added to both BLE loops (`:219-226`, `:241-248`) | detection is right — **but see T1, nothing consumes it** |
| `8bc26338` | `device.py:195-258`: `accepted = self._previous` captured **before** the loop, `check_usable(accepted)` at `:255`, `self._previous = m` only on acceptance at `:256`; `read_measurement` now assigns `_previous` only under `enforce` (`:288`, `:347`) | S30 genuinely fixed, and the first-read baseline probe (`:207-226`) is the real fix report 11 asked for, not `prev = None` |
| `6295c91a` | `device.py:97-108` `identify()` on BLE now sends `ble.READ_MEASUREMENT`; the frame is renamed `TRIGGER_UNSAFE` | correct |
| `a7516de1`+ follow-ups | S22 site is now `_blocked_by_unusable_target_instrument` and resolves `self._chart_file_for(self._ti1_path)`; S23 `_overlay_failure_reason:11484` likewise | **S22 and S23 are CLOSED** |

## T-1 [MAJOR] `243cee7c` fixed the *detection* and left the *reporting* — `DeviceLost` is thrown away one frame later

`workflow/cr30/device.py:21` — `class DeviceLost(MeasurementError)`. It is raised
at `:191`, `:224`, `:246`. Nothing anywhere catches it:

```
$ grep -rn "DeviceLost" --include="*.py" .   # minus .venv
workflow/cr30/device.py:21,191,224,246
tests/test_cr30_notices_the_device_is_gone.py:19,39,52,66,80
```

The only consumer is `_ReadWorker.run` (`measure_bridge.py:129-134`):

```python
except Exception as e:            # noqa: BLE001 — a device error is news
    self.failed.emit(self._loc, str(e) or e.__class__.__name__)
```

`failed` is `pyqtSignal(str, str)` — **the type is flattened to a string.** So an
unplugged CR30 reaches the user through the same handler as a refused reading,
`_on_cr30_read_failed`, and says:

> *"The CR30 could not be read for patch A16: the instrument stopped answering
> (…). **Press the button on the instrument again.**"*

That is still the wrong advice, in a log line and an 8-second status flash, for
an instrument that is not plugged in. The 180-second delay is gone; the wrong
message is not. **S28 is half-fixed, and the visible half is the half that is
still broken.** Fix: give `_ReadWorker` a `lost = pyqtSignal(str, str)` (or pass
`type(e).__name__`), and route it as in Section B.

## T-2 [MINOR] `DeviceLost` subclasses `MeasurementError`, and one loop catches the parent first

`device.py:215-226`, the BLE baseline probe:

```python
try:
    prev = self.read_measurement(enforce=False).values
except MeasurementError:
    time.sleep(poll)      # not answering yet; keep trying
except Exception as exc:
    raise DeviceLost(...)
```

`DeviceLost` **is** a `MeasurementError` (`:21`), so if anything below ever
raises one, it lands in the `sleep-and-retry` arm and the "instrument is gone"
fact is swallowed until the timeout — exactly the bug `243cee7c` set out to
kill. Latent today (nothing under `read_measurement` raises `DeviceLost`) but it
is a trap that reads as safe. Either make `DeviceLost` inherit `Exception`
directly, or put `except DeviceLost: raise` above the `MeasurementError` arm in
both loops.

---
# PART A — the calibration-first flow

I agree with the *shape* of the plan. Five of its details are wrong or missing,
and two of them destroy user data or poison the session.

## A-1 [BLOCKER] "Before the helper" is not one place — put it in the wrong one and a Cancel DESTROYS the previous measurement

There is exactly **one** start path: `TabMeasure._on_start`
(`ui/tabs/tab_measure.py:5465`). Guided and Manual differ only in
`_collect_params()` (`:5531` → `_collect_guided` / `_collect_manual`), and resume
is a checkbox inside those, not a second entry point. `self._manager.start(...)`
— the helper launch — is at **`:5661`**, and `_open_cr30_bridge()` +
`_show_cr30_measuring_window()` are at `:5671-5672`, i.e. **after** it. So
"before the helper" is reachable in Guided, Manual and resume alike. Good so far.

**But `_on_start` does eight irreversible things between `:5490` and `:5661`,
and two of them are destructive.** In order:

| line | what it does | reversible? |
|---|---|---|
| 5490 | `self._sound.arm(...)` | only by an explicit `disarm()` |
| 5531 | `_collect_params()` | yes |
| 5535 | `_confirm_replacing_measurement()` | yes (asks) |
| **5546** | **`_archive_measurement_before_replacing()`** | **NO — moves the run's `.ti3` to `old/`** |
| 5575 | `_show_overlay_from_existing_ti3()` / `_clear_overlay()` | cosmetic |
| **5603** | **`_begin_session_guard(_ti3_pre)`** | **NO — `MeasurementSession.begin()` copies aside and records C₀** |
| 5605-5615 | `killall chartread` | harmless |
| 5637 | `save_target_settings()` (**W8**, `per_target_settings.md`) | writes meta.json |
| 5639-5645 | `_set_settings_enabled(False)`, Start off / Stop on, `_session_live = True`, `installEventFilter` | must be undone by hand |

**Failure scenario, concrete.** Run1 holds a good 390-patch measurement. The user
presses Start on a CR30 chart, is offered the calibration window, and clicks
Cancel because the white tile is in the other room. If the window sits anywhere
after `:5546`, the old `.ti3` is already in `old/` and the run now shows *no
measurement* — for a measurement that never began. If it sits after `:5639`, the
settings panel is greyed out, Start is disabled, Stop is enabled and the
app-wide event filter is installed, on a session that does not exist.

**Recommendation:** the calibration window goes **between `:5535` and `:5546`** —
after `_confirm_replacing_measurement()` (so we do not ask a user to calibrate
for a measurement they then decline to replace) and before
`_archive_measurement_before_replacing()`. At that point a Cancel is a bare
`return` and costs nothing *except* the armed sound at `:5490`, which the Cancel
path must undo with `self._sound.disarm()` — #131's rule is that per-patch sounds
must not be live outside a read.

## A-2 [BLOCKER] The plan says "so nothing is armed" — but the transport must be OWNED at that moment, and on BLE there is only one connection to be had

The plan's stated reason for going first is that "nothing is armed and S11's
deadlock cannot happen". That is true but it is not the whole ownership question,
and the plan does not answer the one I asked.

Today `_open_cr30_bridge` (`:5671`) constructs a `DeviceReader` but **does not
open anything** — `DeviceReader._open` is called lazily inside `__call__`, under
`self._lock` (`measure_bridge.py:382-385`). So at calibration time nothing is
open, and the calibration is the thing that will open it.

Two ways to do that, and only one is safe:

* **Wrong:** the calibration window builds its own `CR30.open_*()` handle, uses
  it, closes it, and the session then reopens in `DeviceReader._open`. Over USB
  that costs seconds. Over **BLE it is a full disconnect/reconnect**, and the
  device advertises as a single-connection peripheral — `ble.py:1-14` and the
  `_no_device_help` text itself (`measure_bridge.py:92-94`): *"A CR30 stops
  being visible over Bluetooth while another device holds it"*. A reconnect that
  races the OS's own cached link is exactly the class of failure that produced
  incident 4. It also throws away the `Measurement` we just took — which is the
  only baseline the BLE change-detection has (`device.py:198-207`).
* **Right:** `_open_cr30_bridge()` is moved to **before** the calibration
  window, the calibration runs through **that same `DeviceReader`**, and the
  helper start stays where it is. The bridge is inert until `on_patch_ready` is
  called, and nothing calls it until the helper prints its first `spot_ready` —
  so moving the bridge earlier arms nothing. Only `self._manager.start()` must
  stay after.

**And there is a bonus for free.** If the calibration goes through the same
`DeviceReader`, the reading it takes becomes `self._previous` on the `CR30`
object, so the BLE baseline probe at `device.py:207-226` is already satisfied
when patch A1 is armed — the first patch no longer spends a poll cycle
establishing a baseline, and the stale-cache hazard the docstring documents in
capitals is closed by construction rather than by a probe.

## A-3 [BLOCKER] The cancel latch WILL poison the session — you asked, and the answer is yes

`DeviceReader._cancel` is documented as a one-way latch
(`measure_bridge.py:352-356`):

> *"Set once, by `stop()`/`close()`, and **never cleared**: a cancelled reader is
> a FINISHED one. Safe because the tab builds a fresh `DeviceReader` for every
> session … if one is ever reused, every read would cancel the instant it
> started."*

`_cancelled()` (`:395-396`) is the predicate every wait loop in
`device.py` checks (`:169`, `:209`, `:229`). So if the calibration window's
Cancel — or its timeout — calls `reader.cancel()`, then **every patch read for
the rest of the session raises `"cancelled while waiting for the instrument's
button"` instantly**, and `_on_cr30_read_failed` tells the user to press a button
that can never help. That is S30's dead-session shape, re-created by the new
feature. The docstring predicted it in as many words; the plan walks into it.

**Recommendation:** do not reach for `cancel()`. Give the calibration its own
one-shot `threading.Event` and pass it as the `cancelled=` callable for that call
only. Concretely:

```python
def calibrate(self, *, timeout: float = 30.0, cancelled=None):
    """User-initiated white calibration. Its own cancel, never self._cancel."""
```

and leave `_cancel` meaning exactly what it means today: this reader is finished.

## A-4 [MAJOR] The calibration must not run on the GUI thread — and the plan does not say which thread it runs on

`DeviceReader.__call__` takes `self._lock` and holds it for the whole read
(`measure_bridge.py:382-387`). A `Calibrate` button whose `clicked` slot calls
into the reader synchronously blocks the Qt main thread for the duration — the
same primitive S1/S27 proved, only for a shorter interval. It is also
unresponsive: no Cancel, no repaint, and on macOS a spinning cursor within
~2 s.

Reuse what exists: `_ReadWorker` (`measure_bridge.py:119-140`) is a
one-shot `QObject` + `QThread` + `done`/`failed` pair that already solves this,
including the "keep the QThread referenced or the process dies" rule
(`:266-269`). A `_CalibrateWorker` on the same pattern — or `_ReadWorker` with the
callable injected — is ~15 lines. **Do not invent a second threading pattern.**

**Named deadlock risk:** if the calibration worker holds `_lock` and the user then
closes the modal, `_close_cr30_bridge` → `reader.close()` (`:398`) acquires with
`timeout=2.0` and logs *"reader did not stop within 2 s; closing the instrument
anyway"* — it will not hang, but it will close the transport under a running
calibration. The modal's close/Esc must therefore be routed to the calibration's
own cancel, and the window must not be dismissible while the calibration frame is
in flight.

## A-5 [MAJOR] There is no second confirmation window to write — M-CR30-HOW-TO-MEASURE **is** it, and it already says "take the cap off"

The plan implies two new windows. Only one is new.

Basti's ruling: *"then the calibration confirmation window should appear and
explain to take the cap off again and how to navigate"*. That text already
exists, word for word, in `ui/ti2_loader.py`
`patch_measurement_instructions_html("cr30")`:

> *"Take the **magnetic cap off** the measuring end first — with the cap on, the
> CR30 reads its own white tile instead of your print. … press the button on the
> instrument. ChromIQ collects the reading by itself and moves on to the next
> patch — there is nothing to press on screen…"*

and it is rendered into `M_CR30_HOW_TO_MEASURE`
(`workflow/measurement_messages.py:123-137`, `approved=False`), which
`_show_cr30_measuring_window` (`tab_measure.py:6904`) already shows once per
measurement. So:

* **The confirmation window = M-CR30-HOW-TO-MEASURE**, moved to fire immediately
  after the calibration and before the helper. Ruling 2's sentence
  ("ChromIQ cannot check the calibration") is **one added sentence to a message
  that is still `approved=False`** — no new ID, no second §M round for it.
* **Only ONE new message is genuinely new:** the calibrate-first window itself.
  Call it `M-CR30-CALIBRATE`, `approved=False`, plus at most one refusal variant.
* **Do not show it twice.** `_cr30_how_shown` is reset at `:5660`, *after* where
  the calibration window belongs. If the calibration flow shows the window and
  `:5660` then clears the flag, `:5672` shows it a **second** time. Whichever way
  it is wired, the flag must be set by whoever shows it, and `:5660`'s reset must
  move above the calibration window.

**Modality.** `_show_cr30_measuring_window` sets `dlg.setModal(False)` at
`:6935` with a reason: *"the reading is driven by the instrument's own button, so
a modal would sit between the user and the preview they are meant to be
watching."* That reason **evaporates** once the window is shown before the helper
exists: there is nothing to watch yet, and nothing can be read while it is up. So
it may become modal — but that is a behaviour change to a window Knut's
`measurement_exit_strategy.md` regime governs, and it must be stated in the §M
entry, not slipped in.

## A-6 [MAJOR] `-N` already does exactly what the owner ruled — reuse `params.disable_initial_cal`, do NOT read the checkbox

The plan says "Guided mandatory, Manual honours `-N`". That is **already the
value of one field**, and it was made so after a real incident.

`_collect_guided` (`tab_measure.py:11699`) hard-codes
`disable_initial_cal = False` behind a comment headed *"NEVER FROM A CONTROL THE
USER CANNOT SEE"*: `self._nocal_cb.setVisible(False)` at `:2056`, and a stored
`measure_no_cal` once ran **every** guided measurement uncalibrated — Knut's
beta.148, every patch rejected as *"Reading is inconsistent"*.
`_collect_manual` (`:11717`) reads `self._m_nocal_cb.isChecked()`.

So the rule is one line:

```python
if not params.disable_initial_cal:
    ...show the calibration window...
```

**Reading `self._m_nocal_cb` directly would re-open the beta.148 hole**, because
in Guided that widget still holds whatever Manual last set. Read the params
object, which is also the value W8 writes into `meta.json`
(`save_target_settings()`, `:5637`) and the value the log NOTE at `:5681` quotes.

Three consequences the plan has not accounted for:

1. **`-N` is inert under `-xx`.** `MeasureManager._build_args` says so in its own
   comment: *"`-c`, `-N`, `-B`/`-b` and `-T` all become inert under it — …
   calibration lives inside `if (xtern == 0)`"*. On a CR30 chart `-N` currently
   means **nothing at all**. Giving it a second, ChromIQ-specific meaning on this
   one path is the owner's call and he has made it — but it must be written down,
   because a reader of `_build_args` will conclude the opposite.
2. **The `-N` log NOTE at `:5681-5690` becomes wrong for a CR30.** It says *"your
   instrument will not be calibrated before this measurement … switch the option
   off in the measurement options and start again"* — true in spirit, but it is
   about chartread's calibration prompt, which does not exist here. It needs a
   CR30 variant, and that variant is user-facing text → §M.
3. **The tooltip at `:2048-2054` lies for a CR30**: *"Skips the automatic
   white-tile calibration at chartread startup. Normally chartread prompts
   you…"*. chartread prompts nobody under `-xx`.

## A-7 [MAJOR] What `trigger_unsafe` must become — and the warning is the OPPOSITE of the one you would write

`workflow/cr30/device.py:114-137`. Two separate problems.

**(a) The BLE branch now states a falsehood, and the commit that disproved it did
not fix it.** `:132-135`:

```python
if self.kind != "usb":
    raise NotImplementedError(
        "no host trigger is known on BLE; the operator presses the "
        "instrument's own button (TRANSPORT_BLE.md)")
```

`6295c91a` rewrote `ble.py:57-73` to say the exact opposite — *"EXP-BLE-012
proved on 2026-08-28 that it triggers over Bluetooth too"* — and defined
`ble.TRIGGER_UNSAFE`. **Two files in the same package now contradict each other,
and the wrong one is the one that raises.** This needs correcting whether or not
the Calibrate button ships.

**(b) The docstring's rule is being reversed, so it must be rewritten, not
edited around.** Today it reads *"Deliberately not called `trigger`, and
deliberately not part of the recommended integration surface"* and *"⚠ Not to be
used near a magnet"*. If ChromIQ ships a button that calls it **with a magnet
deliberately present**, leaving that text in place makes the codebase say "never
do this" beside the code that does it. What it must become:

* keep `trigger_unsafe` as the **raw command** and keep the name — nothing should
  reach for it casually;
* add `CR30.calibrate_white()` as the single **deliberate, user-initiated** entry
  point, whose docstring records: the owner's ruling and its date; that
  EXP-BLE-012 (BLE) and EXP-MEAS-004 (USB) are the evidence; that the magnet gate
  is what turns a trigger into a calibration; and that
  **ChromIQ cannot verify the result** (`INTEGRATION.md:495-499`);
* make it work on **both** transports — `usb_measure.trigger` on USB,
  `ble.TRIGGER_UNSAFE` on BLE — per ruling 1.

**On your question "must a magnet WARNING gate it": no, and a magnet warning
would be actively wrong here.** The hazard is not the magnet — the magnet is the
*point*, it is what makes the command a calibration instead of a measurement.
The hazard is **which face of the cap is at the aperture**: EXP-MEAS-004
corrupted this unit by calibrating against the cap's **green** face, 81.10 → 149.10 %R,
and `src/cr30/measurement.py:75-87` records that the error is one-sided and
invisible afterwards. A window that says *"do not press this near a magnet"*
tells the user to remove the very thing the operation requires. The correct
warning is about the **white tile facing the aperture**, and it is the same
sentence in both windows. Cap ON, white tile facing, is what makes it safe;
cap ON, green face, is the accident; cap OFF is merely a wasted measurement.

## A-8 [MAJOR] A resumed / continued run — my answer, and it is *not* "recalibrate because patches exist"

You asked whether a run that is being continued must recalibrate. The
calibration lives **in the instrument**, not in the run: nothing in the `.ti3`,
the run folder or `meta.json` records it, and the CR30 keeps its white reference
across power cycles. So "some patches are already read" is the wrong variable.

The right variable is *"is this a new instrument session"*, and every press of
Start is one — the `DeviceReader` is rebuilt each time (`_open_cr30_bridge` →
`_close_cr30_bridge` first). So:

* **Same rule for a fresh run and a resumed one**: the window appears on every
  Start unless `params.disable_initial_cal`. Manual users resuming a long chart
  are exactly the people the `-N` tick exists for, and ruling 3 says to respect
  it.
* **No mid-session Calibrate button in this cut.** I stand by S14: the only drift
  measurement in the research repo is a warm-up of −0.32 % relative over a few
  minutes (`MEASUREMENT.md:800-801`), hours-scale drift is unmeasured, and
  `CALIBRATION.md:93-117` carries a standing *"do not recalibrate this unit"*.
  A mid-run calibration also has to stop the bridge, release the reader,
  calibrate, and re-arm — and the reader's `_cancel` latch (A-3) makes "re-arm"
  impossible without new code.
* **Do not recalibrate silently on a resume.** Nothing may claim it happened.

## A-9 [MINOR but it is the ruling] What the calibration window may and may not say

Ruling 2 is satisfied by one true sentence and no more. `INTEGRATION.md:495-499`:
*"ChromIQ cannot tell a well-calibrated CR30 from a badly-calibrated one, and
neither can we."* — because the device returns the firmware's canned tile
constant whenever the gate engages (`MEASUREMENT.md:381-397`: white tile vs green
face, **max absolute difference across all 31 bands = 0.0**).

So the window must **not** say "calibration successful", must not show a number,
and must not have a tick or a green mark. The honest form is *"ChromIQ has asked
your CR30 to calibrate. It cannot check the result — the instrument reports the
same value whatever is under the cap, so make sure the white tile is facing the
aperture."* All of it goes to §M-PROPOSED with `approved=False`
(`measurement_messages.py:67`, `_m(..., approved=False)`), and
`measurement_exit_strategy.md` must be **extended** for the new window rather
than contradicted — its existing "Calibration required" row is the *Argyll*
prompt, and its Cancel key mapping does not apply to a window that gates a helper
which has not started.

**On (v) "all new strings go to §M-PROPOSED with approved=False": agreed, and it
is already the branch's habit** — M-CR30-STOCK-READER, M-CR30-READ-ENDED and
M-CR30-HOW-TO-MEASURE are all `approved=False` and listed in
`unified_measurement_management.md`'s awaiting-review header.

---
# PART B — surfacing the disconnect (S28) and the missing watchdog (S31)

Your plan is *"emit `instrument_disconnected` when `DeviceLost` reaches the
bridge, and reuse `_on_instrument_disconnected`."* The reuse instinct is right.
Three things are wrong with it, and one of them is bigger than the disconnect.

## B-1 [BLOCKER] The bigger bug: **one failed read kills the CR30 session for ever, in silence — and the commonest first-time mistake triggers it**

This is the "I pressed a few times and nothing happened" case, and it is **not**
a disconnect, not `reading_dropped`, and not `DROPPED_NO_PROMPT`.

Trace it in the code:

* `Cr30MeasureBridge._start_read` has **exactly one caller**:
  `on_patch_ready` (`measure_bridge.py:214`). Verified by grep — no other site
  in the repo calls it.
* `on_patch_ready` only runs on a **new `spot_ready`** from the helper, and the
  helper only re-prompts when it **receives a command**
  (`chromiq_chartread.c`, the `xtern` spot loop).
* `_on_read_failed` (`:277-288`) sets `self._reading_loc = None`, emits
  `read_failed`, **and does nothing else**. It sends no command, starts no
  retry, re-arms nothing.
* `_on_cr30_read_failed` in the tab (`tab_measure.py:6875-6881`) writes a log
  line and flashes the status bar. It sends nothing either.

**So after any single failed read, no reader is running and no prompt will ever
arrive again. The session is dead and every part of the UI still says it is
alive**: the preview keeps its patch highlighted, the helper still shows *"Ready
to read patch …"*, and the message on screen says:

> *"The CR30 could not be read for patch A1: … **Press the button on the
> instrument again.**"*

Pressing it cannot help. Nothing is listening. On BLE the presses land in
`BleTransport._buf` and are cleared by the next `ask()`; on USB they sit in the
serial buffer.

**The reproducible failure scenario is the ordinary one, not an exotic one.**
The user starts a CR30 chart with the cap still on — the instrument's resting
state, and the mistake the how-to-measure window exists to pre-empt. Patch A1 is
read, `Measurement.check_usable` raises the magnet-gate message, `read_failed`
fires, and the session is over. The user takes the cap off, presses the button
as instructed, and nothing happens for ever. **This is a 100 % dead end on the
most likely first-run mistake**, and it needs no unplugging, no Bluetooth and no
timeout to reach. The 180 s button timeout is merely *one* of the doors into it.

**Recommendation.** `read_failed` must be recoverable. Two routes, both already
anticipated by the code:

1. **Re-arm in the bridge.** In `_on_read_failed`, if the session is live and
   `self._awaiting_loc == loc`, call `_start_read(loc)` again after telling the
   user why. A retry counter is needed so a permanently broken device does not
   spin; a `DeviceLost` (once B-2 gives it a type) must *not* re-arm.
2. **Or re-prompt the helper.** The module docstring at `measure_bridge.py:20-27`
   already records that `{"cmd":"ok"}` / `{"cmd":"retry"}` are inert to the
   external-value parser and **loop the prompt, producing a duplicate
   `spot_ready` for the same loc** — which is precisely a re-arm. The
   `_reading_loc == loc` guard at `:209` does not block it after a failure,
   because `_on_read_failed` has already cleared `_reading_loc`.

Route 1 is smaller and does not touch the protocol. Either way the user must be
told which happened. **Whatever else is done for S28, do this first: it costs a
user their whole session on the first mistake they are most likely to make.**

## B-2 [BLOCKER] `instrument_disconnected` cannot be emitted from a `DeviceLost` today, because the type is gone by then

See **T-1**. `_ReadWorker.run` catches `Exception` and emits
`failed = pyqtSignal(str, str)` with `str(e)`. By the time anything in the tab
can act, all that is left is a sentence. Emitting `instrument_disconnected` on
a substring match would be exactly the "adjacent in the log is not causal" trap.

**Minimum change:** `_ReadWorker` gains a second signal, or a third string
argument carrying `type(e).__name__`; `Cr30MeasureBridge` gains
`device_lost = pyqtSignal(str, str)`; `_open_cr30_bridge` connects it. Only then
can the tab distinguish "that reading was refused" from "the instrument is gone",
which is the whole point of `243cee7c`.

## B-3 [BLOCKER] `_on_instrument_disconnected`'s `abort()` is a **second exit**, and the design spec forbids it — your instinct is right, but not for the reason you gave

You asked: *"is `abort()` right, or must it be save-and-stop?"*

**Data-wise, for a CR30, `abort()` loses nothing.** I confirmed the per-patch
autosave in the C source: `native/chartread_helper/chromiq_chartread.c:3178`,
`cq_write_ti3_atomic(); /* CHROMIQ_EXT: autosave per patch */`, inside the
`xtern` external-value branch. And `MeasurementSession.finish` →
`judge_session` (`workflow/measurement_state.py:241-256`) keeps a file with
`after > 0` (verdict `KEEP`), or on a resume that went backwards keeps **both**
(`RESTORE_AND_KEEP_BOTH`). So the 15 patches survive a kill.

**But `abort()` is still wrong, and the reason is binding spec, not data loss.**
`docs/design/measurement_exit_strategy.md:27-40`:

> *"**Every way out of a session goes through `_confirm_end_of_session`** …
> A window that ends a session any other way is a second exit, and that is the
> thing this document exists to catch."*

and Knut on M-NO-INSTRUMENT (`unified_measurement_management.md:906-911`):

> *"its **OK button ends the session through the one ending every route
> shares**, so nothing read is lost and nothing is discarded without being
> offered … **All messages that can arrive during measurement must exit in that
> safe manner, as a single exit strategy for all cases.**"*

`_on_instrument_disconnected` (`tab_measure.py:7129-7147`) calls
`self._manager.abort()` **directly**. It never asks. And the handler is shared
with every other instrument, where `abort()` **does** destroy the session —
CLAUDE.md's own note: *"chartread writes .ti3 ONLY on clean exit — kill = data
loss."* So the moment this dead signal is brought to life, a CR30 unplug is
survivable and an i1Pro unplug on the same code path is not.

The helper is still alive after a disconnect — the instrument went away, not the
process — so `send_save_partial_and_quit()` (`d` → `unread_confirm` → `y`) works
perfectly well from here.

**Recommendation:** `_on_instrument_disconnected` shows its window, and the
window's OK routes into `self._end_session(self._confirm_end_of_session(...))`,
exactly as M-NO-INSTRUMENT does. Keep `abort()` only where the user chose
"Discard and stop".

## B-4 [MAJOR] The handler's strings are **ad-hoc, not §M**, and one of them is not translated at all — report 11 got this wrong

Report 11 (S28, S31) says reusing this machinery *"would light up an existing,
already-§M-approved user journey"*. **It is not §M-approved. It is not in §M at
all.**

* `grep -n "isconnect" workflow/measurement_messages.py` → **nothing**. There is
  no `M-INSTRUMENT-DISCONNECTED`.
* `grep -in "disconnect" docs/design/*.md` → **one hit**,
  `measurement_window_sounds.md:38`, a *sound* row. It is absent from
  `measurement_exit_strategy.md`, a document whose title is *"Every window that
  can end a measurement"* — so an ending window is missing from the register of
  ending windows.
* `tab_measure.py:7144-7146` is **not `tr()`-wrapped**:
  ```python
  self._log.appendPlainText(
      "\n[ERROR] Instrument disconnected — stopping measurement."
  )
  ```
  (the `[WARN]` line four lines above it *is* wrapped, so this is an oversight,
  not a convention).
* The window body (`_show_instrument_disconnected_window`, `:7186-7190`) is
  `tr()`-wrapped but invented in place, and says **"Please check the USB
  connection"** — wrong for a CR30 that dropped its **Bluetooth** link, which is
  one of the two cases this work is about.

So the §M obligation lands on Section B too, not only on Section A: the window
must be added to `measurement_exit_strategy.md`'s table and its text moved into
`measurement_messages.py` as `approved=False`, with a transport-neutral body.

## B-5 [MAJOR] Yes, a watchdog is still needed — `DeviceLost` covers **one** of the three silences

Your question: *"is a watchdog actually needed on top, or does `DeviceLost` cover
every case now?"* It covers one.

| silence | covered by `DeviceLost`? | why |
|---|---|---|
| cable pulled / BLE link dropped | **yes**, once B-2 routes the type | `device.py:191,224,246` |
| a read failed and nothing re-armed (B-1) | **no** | the transport is healthy; there is simply no reader |
| instrument switched off *before* Start | **no** | `_open` raises `ConnectionError`, `_on_read_failed` fires once, session runs on with no reader (S29 state 4) |

Two of the three are the **same shape**: *the session believes it is measuring
and no read is in flight.* That is a state the bridge can answer exactly, with no
timing guesswork at all:

```python
@property
def is_reading(self) -> bool:
    return self._reading_loc is not None
```

A 20-30 s `QTimer` in the tab that fires only while `self._session_live` and
`bridge.awaiting_loc is not None and not bridge.is_reading` catches both, and
**cannot false-positive on a user taking their time** — which is exactly why
report 11's S31 warned that the watchdog interval cannot be
`button_timeout_s`. It is a state check with a debounce, not a timeout.

## B-6 [ANSWER] Does a dropped reading reach the user? Yes — but it is not the symptom you are chasing

`reading_dropped` → `_on_cr30_dropped` (`tab_measure.py:6855-6873`): a `tr()`-ed
line in the in-app log **and** a 6-second status flash. So it is visible (though
not a window, which is arguably against Knut's *"all events shall have windows"*
— a design call, not a bug).

But `DROPPED_NO_PROMPT` is close to unreachable in practice: `_why_not` returns
it only when `_awaiting_loc is None` while a reading arrives, and the only paths
that clear `_awaiting_loc` are `_on_reading`'s own success (`:302`),
`note_goto` (`:236` — which sets `_nav_target`, so `DROPPED_NAVIGATING` wins) and
`stop()` (`:243` — which sets `_stopped`, so `_on_reading` returns first at
`:294`). **`DROPPED_NO_PROMPT` is not the mechanism behind "I pressed and
nothing happened".** B-1 is. Do not fix the wrong one.

---
# PART C — every open finding from report 11, re-verified

Verified against the tree as of `6295c91a` plus the implementer's uncommitted
edits. **CLOSED** = I found the fix and read it; **OPEN** = I found the fault
still there.

| # | verdict | evidence |
|---|---|---|
| **S6** | **CLOSED** | `_try_load_tiffs`'s no-TIFF branch (`tab_measure.py:4324-4335`) now sets `self._patch_boxes = []` and `self._preview.set_page_patch_boxes({})`, with a comment naming exactly S6's failure. |
| **S17** | **CLOSED** (uncommitted) | `tab_measure.py:6015-6032` now has real singular/plural for both sentences. `git blame` says *"Not Committed Yet"* — it is in the working tree, not in a commit. |
| **S22** | **CLOSED** | the function is now `_blocked_by_unusable_target_instrument` and resolves `self._chart_file_for(self._ti1_path)`, with the reopened-project reason in the comment. |
| **S23** | **CLOSED** | `_overlay_failure_reason:11484` calls `per_patch_overlay(ti3, self._chart_file_for(self._ti1_path))`. |
| **S24** | **CLOSED, and better than my proposal** | `_show_overlay_from_existing_ti3:11104-11121` now counts `drawable` **before** painting, from the patches themselves, and returns False when none will land. The comment states the accumulation problem explicitly. |
| **S16** | **OPEN** | `tab_profile.py:4012-4017` `set_ti3_path` still does `self._build_btn.setEnabled(True)` unconditionally. |
| **S18** | **PARTLY MOOT — see C-1** | |
| **S19** | **OPEN** | `measure_manager.py:943` sets `_save_partial_state = "wait_are_you_sure"` before `send_key("d")`; the only clears are the two prompt handlers at `:1667` and `:1672`. A complete chart raises neither. |
| **S20** | **OPEN** | `measure_bridge.py:63-116` `_no_device_help` — still ~15 user-facing sentences with no `tr()`. It is the `{message}` in `_on_cr30_read_failed`'s window text, so it is definitely shown. |
| **S3** | **OPEN, and I can now name the cause** — see C-2 | |
| **S7** | **OPEN** | `_on_chart_measured` (`tab_measure.py:11744-11750`) still `continue`s silently on `page < 0 or box is None`. S24's `drawable` guard is all-or-nothing: 389 of 390 landing is still silent. Note `_on_patch_measured` (the LIVE path) **does** say so once per session (`:10673-10687`) — so the two paths disagree, and the static one is the quiet one. |
| **S29 (1)** zero patches | **MOOT** — see C-1 |
| **S29 (2)** all read | **OPEN** = S19 |
| **S29 (3)** mid-goto | **OPEN** — `save_partial_and_quit` still sends `d` regardless of `bridge.navigating`; no test covers it |
| **S29 (4)** device absent | **OPEN, and it is B-1** — `_open` raises, one `read_failed`, no reader, session runs on |

## C-1 [S18 is MOOT as filed — the empty `.ti3` cannot be reached from Stop]

I could not reproduce S18 and I think it was wrong. `send_save_partial_and_quit`
has exactly three call sites in the tab (`:5976`, `:6079`, `:7441`) and the
relevant one, `_end_session("save")`, is reachable only from
`_confirm_end_of_session`, which returns early at zero:

```python
if not self._manager.has_unsaved_readings:
    # M-END-EMPTY. Nothing to lose, so nothing to ask …
    return "discard"
```
(`tab_measure.py:6000-6007`; `has_unsaved_readings` is `bool(self._read_something)`,
`measure_manager.py:981`.)

So at zero patches the window is not shown, "Save and stop" is not offered, and
the path is `abort()`. **No empty `.ti3` is written by this route.** S18's
premise — *"the user presses Stop → Save and stop"* — cannot happen at n == 0.

What is left of it is real but smaller: **S16.** If an empty or 3-of-390 `.ti3`
gets into the run by any other route, Build Profile is still armed by it.

## C-2 [S16 + S18, the CORRECT rule — and it is not "forbid"]

You asked for the rule rather than the ban, and you are right that a partial
measurement is legitimate. Three things are being conflated and they need three
different answers:

1. **A partial measurement is valid work.** It must stay resumable, stay on
   disk, and keep its progress bar. Nothing may delete or refuse it.
2. **A partial measurement is not a finished one, and Build Profile must not
   present it as though it were.** Today `set_ti3_path` (`tab_profile.py:4017`)
   enables the button on the file's *existence*. The tab already has everything
   needed to know better: `workflow/measurement_state.py` gives
   `classify()` → `Ti3Facts.state` (`EMPTY` / `PARTIAL` / `COMPLETE`),
   `held`, `expected`, and `progress_percent`. **Reuse that; do not write a new
   counter.**
3. **Building from a partial measurement is sometimes exactly what the user
   wants** (a coarse look at 200 of 390). So the answer is a *warning with
   the numbers in it*, not a disabled button.

**Proposed behaviour** — and it belongs in `tab_profile.set_ti3_path`, because
that is the one place every route (bar hand-off, file chooser, main window)
passes through:

* `state is EMPTY` → **Build Profile stays disabled**, and the label says the
  measurement holds no readings. This is the only refusal, and it is not a
  judgement call: `colprof` cannot do anything with zero patches.
* `state is PARTIAL` → **the button stays enabled** and the file label carries
  the count: *"217 of 390 patches measured"*. Pressing Build raises a §M
  confirmation naming both numbers and saying the profile will describe only
  what was measured, with **Measure the rest** / **Build anyway** / **Cancel**.
* `state is COMPLETE` → unchanged.

**Failure scenario it fixes, from his own session:** 3 patches read, Stop, Save
and stop, switch to Build Profile, press the green button.
`22:14:19,882 [INFO] ui.tabs.tab_profile: Build Profile: measurement follows the
bar → …/CR30-Test.ti3` — 3 sets. `colprof` either dies with an Argyll message
the user cannot act on, or emits a profile that is garbage and is then installed.
Patch-by-patch on 390 patches makes "stopped after a handful" the **normal**
case, so #159 turns a latent fault into a routine one.

**The count must come from the FILE, not from the session.**
`_readings_count` is per-session and has no idea what a resume started from
(`measure_manager.py:1092` already reasons about this); `classify()` reads the
file, which is the only thing Build Profile is about to consume.

## C-3 [MINOR, new] S3's cause named: `abort()` never sets `_user_quit`

`MeasureManager.abort` is two lines (`measure_manager.py:983-984`):

```python
def abort(self) -> None:
    self._runner.abort()
```

`_user_quit` is set only by `send_key` on `q`/`Q`/`\x1b` (`:769-771`) and by the
engine's `aborted` event (`:1526`). A **kill** sets neither. So the guard at
`:470` — `if (was_engine and self._stock_reader_cannot_read and code != 0 and
not self._user_quit)` — passes on every abort, and the user gets:

* `WARNING … the chart's instrument is one stock chartread cannot read (unknown
  error) — not falling back` in the file log, and
* `engine_fallback_refused` → `_on_engine_fallback_refused` → **M-CR30-READ-ENDED
  in the in-app log and an 8-second status flash**: *"The measurement stopped …
  What went wrong: unknown error."*

Reached by **"Discard and stop"** and by **quitting the app mid-measurement** —
both deliberate user acts, both reported as an instrument failure. Fix:
`abort()` sets `self._user_quit = True`. It is a *user-initiated* abort by
definition — every call site (`_end_session("discard")`,
`_on_instrument_disconnected`, the close path) is either the user or a fault
that has already had its own message.

---

# PART D — F2, the live split-patch overlay: **SOLVED, and it is not a paint bug**

## D-0 [CORRECTION] The ground rule that was blocking this search is wrong

> *"no explanation is acceptable if it would ALSO have killed the patch
> highlighter, because the ring and the splits come from the same function, same
> page, same boxes."*

**They do not come from the same function, and they are not even on the same
signal.**

| | ring | split |
|---|---|---|
| helper event | `spot_ready` | `patch_read` |
| manager signal | `patch_ready` (`measure_manager.py:1298`) | `patch_measured` (`:1322`) |
| tab slot | `_on_patch_ready` (`tab_measure.py:10627`) | `_on_patch_measured` (`:10653`) |
| draws | `_preview.highlight_patch` | `_preview.set_patch_overlay` |

They share `_locate_patch` and `_patch_boxes` — that is all. So a cause that
kills only the `patch_measured` chain leaves the highlighter working, and the
rule as written excludes a whole class of correct answers. **It should be
retired.**

## D-1 [PROVEN ON SCREEN] The live overlay works — on his chart, his numbers, his settings

I drove the **real app** (real fonts, `WinButtonLayoutStyle("Fusion")`,
`CompositeAppFilter`, his real settings copied into a sandbox `.ini`, real
`MainWindow`, real `TabMeasure`, real preview) over **his own CR30-Test chart**,
and fired his own three readings from `11_EVIDENCE.md` through the same slots the
live session uses.

```
hex_zigzag=True no_swipe=True overlay_mode='both' boxes=390
overlay before anything: {}
overlay after 3 live patches: {0: 3}
preview pixels identical before/after 3 live patches: False
changed pixels: 45532 of 3486912
```

Screenshots on his Desktop:

* `cr30_skeptic2_2026-08-29_P2_1_window_virgin.png` — the whole window, chart
  loaded, nothing measured
* `cr30_skeptic2_2026-08-29_P2_3_window_after_3_patches.png` — **the same window
  after A1/A2/A3.** A1 carries a clean diagonal split, A2 carries the red
  ΔE-warning ring (its ΔE was 69.6), A3 carries the green current-patch ring.
* `cr30_skeptic2_2026-08-29_5_split_zoom.png` — zoomed, all 17 of his real
  readings, splits clipped to the hexagons
* `cr30_skeptic2_2026-08-29_1_chart_loaded.png`, `_4_split_all_live.png`,
  `_6_static_overlay.png`, and `_notes.txt` / `_P2_notes.txt`

The hexagon clipping is correct too — `ui/tiff_preview.py:2507-2534` has a
dedicated `if self._hex_zigzag:` branch that fills `hexp` with the measured
colour and then `hexp.intersected(tri)` with the expected one. His chart takes
that branch (`chart_is_hexagonal(CR30-Test.ti2) → True`, recipe `hflag: True`).

**And I ran it twice**, once with the `.ti2` and once with the **`.ti1`** — the
reopened-project route report 11 suspected. **Byte-identical results** (45,532
changed pixels both times). So the `.ti1` does not break the live overlay either;
`a7516de1`'s bug was confined to the *static* path, exactly as its commit
message claims.

## D-2 [VERDICT] Stop hunting for a paint fault. What is actually wrong is legibility

Every mechanism is proven good: the signal, the slot, `_locate_patch`, the
boxes, the hex clipping, the warn ring, the mode (`both`), `only_measured`
(`False`), and the reopened-project path. There is no remaining code candidate I
can find, and I looked with the widget in front of me.

What the screenshot shows instead is the honest answer: **three splits out of
390 hexagons, at fit-to-window zoom, are about 20 px each on a 390-patch A4
honeycomb.** A user who has seen the overlay on a rectangular chart would say it
did not appear. That is a legibility problem, not a bug, and the app already
owns the two controls that fix it — **"Show only measured patches"** (which was
OFF in his session, confirmed from `meta.json`) and the zoom.

**My recommendation, and I would put it to him as a question rather than ship
it:** when a patch-by-patch session is live and fewer than ~5 % of the chart has
been read, either default "Show only measured patches" ON for that session, or
say once in the log that it exists. Do **not** change the paint code — there is
nothing wrong with it, and changing it would be the "a perfect result can be the
bug" trap in reverse.

**Open, and only a human can close it:** whether what he saw is what these
screenshots show. Per CLAUDE.md an agent's on-screen run is not a confirmation.

---

# PART E — the on-screen run, and the hardware check

## E-1 Method (report 11's PART 8 failed; this is why this one did not)

Report 11 launched `python main.py` and tried to photograph the screen, and the
windows were not on the captured display. **That was the wrong instrument.** The
repo already has the right one, in ~40 `scripts/drive_*.py`: build the real
`QApplication` with the real fonts / style / app filter, build the real
`MainWindow`, and capture with **`widget.grab()`**. `grab()` renders the widget
through the same paint path the screen uses, after polish, so it sees exactly
what the user sees — and it does not care which Space or display the window is
on. (The known blind spot is combo *popups*, which are separate top-level
windows; nothing here needed one.)

**Safety, verified:** his real plist was copied into a sandbox `.ini` and
`AppSettings._qs` pointed at it (the pattern `scripts/drive_hex_overlay.py`
already uses), `custom_output_path` pointed at a temp folder, and his chart was
**copied** there. `~/ChromIQ/CR30-Test` was never opened by the app.

* `~/Library/Preferences/com.chromiq.ChromIQ.plist` md5 **`ad1496831bc929ba9acf01e21c68a8da`
  before and after** — byte-identical.
* `~/ChromIQ/CR30-Test/runs/run1/` mtimes unchanged (23:02 / 23:04, both before
  my first run at 23:28); the `.ti3` still holds `NUMBER_OF_SETS 17`.
* No modal was left waiting: `QDialog.exec` was stubbed to return 1 and the four
  `QMessageBox` statics to 0, so nothing could block on a click nobody is awake
  to give.

## E-2 [HARDWARE, tonight, on his unit] `6295c91a` HOLDS — discovery no longer moves the reading

Permitted by the brief, and nothing forbidden was sent. Script:
`…/scratchpad/ble_discovery_no_trigger.py`.

```
frames this script may send: {'READ_MEASUREMENT': 'bb 02 10 00 00 00 00 00 ff cc'}
TRIGGER_UNSAFE is bb 01 00 00 00 00 00 00 ff bb - NOT sent

A mean %R: 78.6904  first5=[70.0369, 74.4918, 77.0983, 78.0419, 77.5336]
discover -> [{"name": "CM454M0223", "address": "FFB32AD2-…", "rssi": -79,
              "confirmed": true, "axis": [400, 10, 31]}]
identify -> {'model': 'CR30', 'axis': BleAxis(start_nm=400, step_nm=10, bands=31),
             'transport': 'ble'}
B mean %R: 78.6904  first5=[70.0369, 74.4918, 77.0983, 78.0419, 77.5336]
IDENTICAL: True
```

**A full discovery *and* an `identify()` left all 31 bands bit-identical.** Before
`6295c91a` both sent `bb 01 00`, which EXP-BLE-012 has now proved is a real host
trigger over BLE — so this is the direct confirmation that the fix works on the
instrument it was written for.

Two side observations, offered as observations only:

* The advertised name is **`CM454M0223`** and `confirmed: true` came from the
  protocol check, not the name — the discovery design behaves as documented.
* **HYPOTHESIS, not a finding:** the value the unit is holding right now is
  **78.6904 %R mean**, which is within **0.24 %R** of the `TILE_SIGNATURE` mean
  the research repo records (78.93 %R, `MEASUREMENT.md:554`). The brief says the
  cap is OFF. If that number *is* the tile constant, the last thing the device
  did was a **gated** read — i.e. something was over the aperture. I cannot tell
  from here and I did not probe further; worth a glance when he is awake.

## E-3 [MINOR, seen on screen] The Measure tab tells a CR30 user to swipe

`cr30_skeptic2_2026-08-29_P2_3_window_after_3_patches.png`, bottom left of the
panel, on a chart whose `TARGET_INSTRUMENT` is `CR30` and whose patch-by-patch
box is forced on:

> **Keep calm!**
> *Scan each strip with a slow, steady motion.*

A CR30 cannot swipe — `set_no_swipe` exists in the preview for exactly this
reason (`tiff_preview.py:1490`, *"the arrow would be an instruction to do
something the device cannot do"*) and the arrow is correctly suppressed. The
pace panel's caption was not given the same treatment. Same class of fault, one
widget along.

---
# FINAL RANKED SUMMARY

## BLOCKER

| # | finding | file:line |
|---|---|---|
| **B-1** | **One failed read kills the CR30 session for ever, in silence.** `_start_read` has one caller (`on_patch_ready`); `_on_read_failed` re-arms nothing; the helper only re-prompts on a command. Reached by the commonest first-run mistake — starting with the cap on — and the message tells the user to press a button nothing is listening for. | `measure_bridge.py:214,277-288`, `tab_measure.py:6875` |
| **A-1** | The calibration window placed anywhere after `_on_start:5546` means **Cancel destroys the run's existing measurement** (`_archive_measurement_before_replacing`) or leaves the tab in a live-session state with no session. | `tab_measure.py:5465-5661` |
| **A-2** | The transport must be **owned** at calibration time. A separate `CR30` handle means a BLE disconnect/reconnect on a single-connection peripheral. `_open_cr30_bridge` must move before the window; only `_manager.start()` stays after. | `measure_bridge.py:373-389`, `ble.py:1-14` |
| **A-3** | `DeviceReader._cancel` is a **one-way latch**. A calibration Cancel or timeout that calls `reader.cancel()` makes every patch read for the rest of the session raise instantly. The docstring says so. | `measure_bridge.py:352-356,391-396` |
| **B-2** | `DeviceLost` cannot reach a handler: `_ReadWorker` flattened the type to `str(e)`. *(The implementer landed a fix for this mid-review — `failed` now carries `type(e).__name__`.)* | `device.py:21`, `measure_bridge.py:119-147` |
| **B-3** | `_on_instrument_disconnected` calls `abort()` directly — a **second exit**, forbidden by `measurement_exit_strategy.md:27-40` and by Knut's M-NO-INSTRUMENT ruling. Data-safe for a CR30 only; destroys the session on every other instrument. | `tab_measure.py:7129-7147` |

## MAJOR

| # | finding | file:line |
|---|---|---|
| A-4 | the calibration must not run on the GUI thread; reuse `_ReadWorker`, and route the modal's close to the calibration's own cancel | `measure_bridge.py:119-140,382` |
| A-5 | there is no second window to write — **M-CR30-HOW-TO-MEASURE is the confirmation window** and already says "take the cap off"; only the calibrate window is new. Watch `_cr30_how_shown`'s reset at `:5660` or it shows twice | `ti2_loader.py`, `measurement_messages.py:123`, `tab_measure.py:5660,6904` |
| A-6 | reuse `params.disable_initial_cal`, **never** `self._m_nocal_cb` — Guided hard-codes it False after the beta.148 incident. And `-N` is inert under `-xx`, so this gives the flag a second meaning that must be documented | `tab_measure.py:11699,11717,2056` |
| A-7 | `trigger_unsafe`'s BLE branch now **states a falsehood** that `6295c91a` disproved in the same package. And the safety warning must be about *which face of the cap*, not about magnets | `device.py:114-137` vs `ble.py:57-73` |
| A-8 | a resumed run needs the same rule as a fresh one; no mid-session Calibrate button in this cut | S13/S14 stand |
| B-4 | the disconnect window is **not in §M and not in `measurement_exit_strategy.md`**; one of its strings is not `tr()`-wrapped, and its body says "check the USB connection" to a Bluetooth user | `tab_measure.py:7144,7186` |
| B-5 | a watchdog IS still needed — `DeviceLost` covers one of three silences; `bridge.is_reading` answers it exactly, with no timing guesswork | design |
| **S16 / C-2** | Build Profile is armed by any `.ti3`, including 3-of-390. The rule is a warning with the numbers, not a ban — reuse `measurement_state.classify()` | `tab_profile.py:4017` |
| S20 | `_no_device_help`'s ~15 shown sentences are untranslated and invisible to the extractor | `measure_bridge.py:63-116` |
| T-1 | `243cee7c` fixed detection and left reporting *(being fixed as I write)* | see B-2 |

## MINOR

| # | finding |
|---|---|
| T-2 | `DeviceLost` subclasses `MeasurementError`, and `device.py:217` catches the parent first — a trap that reads as safe |
| C-3 / S3 | `abort()` never sets `_user_quit`, so "Discard and stop" and quitting the app are reported as an instrument failure |
| S19 | `_save_partial_state` latch has an unhandled exit (a complete chart raises no `unread_confirm`) |
| S7 | a partial geometry miss is silent on the **static** path while the live path says so — the two disagree |
| S29(3) | save-and-stop during an outstanding `goto` is untested and unguarded |
| E-3 | the pace panel tells a CR30 user to *"scan each strip with a slow, steady motion"* |
| D-0 | report 11's F2 ground rule is factually wrong and should be retired |

## MOOT / REFUTED

* **S18** — the empty-`.ti3`-from-Stop path does not exist; `_confirm_end_of_session`
  returns `"discard"` at zero readings before the window is built (C-1).
* **S6, S17, S22, S23, S24** — closed by the branch (S17 uncommitted).
* **F2** — no paint fault exists; proven on screen with his chart, his numbers,
  his settings, on both the `.ti2` and the `.ti1` route (D-1).

## WHERE I DISAGREE WITH THE IMPLEMENTER, BLUNTLY

1. **"The calibration window opens before the helper is started, so nothing is
   armed"** is necessary and not sufficient. It says nothing about *where*
   before (A-1 loses data), nothing about who owns the transport (A-2 breaks
   BLE), nothing about the thread (A-4), and it walks straight into the one-way
   cancel latch the code warns about in capitals (A-3).
2. **"Window says we cannot verify it"** — you are planning two new windows. One
   of them already exists, already says the sentence Basti asked for, and is
   already `approved=False`. Extend it; do not write a second (A-5).
3. **"Guided mandatory, Manual honours -N"** is `params.disable_initial_cal`
   and nothing else. If the implementation reads the checkbox, it re-opens
   beta.148 (A-6).
4. **"Reuse the existing `instrument_disconnected` machinery"** — do, but not
   because it is approved. It is **not** in §M, **not** in the exit-strategy
   table, and it ends the session with a bare `abort()` that the spec forbids
   (B-3, B-4). Report 11 said it was "already §M-approved"; that was wrong and I
   checked it twice.
5. **Fix B-1 before either of them.** A calibration flow that ends in a session
   which dies on the first refused reading has not helped anyone.

## STATUS

Complete. F2 answered and closed; on-screen run achieved with screenshots on
`~/Desktop`; the hardware check ran and `6295c91a` holds. Nothing of the user's
was written — plist md5 and project mtimes verified unchanged.
