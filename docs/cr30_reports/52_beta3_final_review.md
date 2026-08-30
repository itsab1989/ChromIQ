# 52 — Final review before v4.1.5-beta.3

**Reviewer:** Claude (final-gate critic) · **Date:** 2026-08-30
**Range:** `v4.1.5-beta.2..HEAD` (20 commits, `6428fd2c..fccb5b89`)
**Verdict:** **NO — three small fixes first (§6). Everything else is green,
including a live end-to-end run of the Bluetooth tool on this Mac.**

## 1. Priority 1 — CR30 Bluetooth report + repair
### 1.1 The worker-thread fix (bleak WinRT vs Qt STA)

**The threading model itself is sound — verified against the shipped bleak
3.0.2 source, not the docs.** `bleak/backends/winrt/util.py::assert_mta()`
(called by `scanner.py:242` before every WinRT scan) does this, in order:

1. `CoGetApartmentType`. On a **fresh thread that has never touched COM** this
   fails with `CO_E_NOTINITIALIZED`, and `assert_mta` returns success with the
   comment *"All is OK if not initialized yet. WinRT will initialize it."* —
   WinRT then initialises that thread MTA itself. A bare
   `threading.Thread(target=...)` running
   `asyncio.new_event_loop().run_until_complete(collect())` is **exactly** this
   sanctioned configuration.
2. Only a thread already STA (Qt's GUI thread after `OleInitialize`) reaches
   the SetTimer probe and the "Thread is configured for Windows GUI but
   callbacks are not working" BleakError — the pre-fix crash.

Does bleak need a *running* asyncio loop on that thread? Yes, and it has one:
the whole of `collect()` — both `BleakScanner.discover` calls and
`ble.discover(verify=True)` — executes inside the single
`run_until_complete`, so `asyncio.get_running_loop()` and
`call_soon_threadsafe` (which bleak uses to deliver notifications) always have
the worker's loop. On macOS the CoreBluetooth backend dispatches from its own
queue via the same mechanism and is thread-agnostic; verified live on this Mac
(§1.6).

**Three real faults remain around the spin loop** (`ui/main_window.py`,
`_run_cr30_bluetooth_report`):

**F-3 (should fix before tag): the GUI is fully re-entrant during the scan,
and the dialog text claims the opposite.**
`QApplication.processEvents(ProcessEventsFlag.AllEvents, 50)` **delivers user
input**. While the ~35 s scan runs the user can: click Tools and start a
*second* concurrent report (two concurrent BLE scans, two `ble.discover`
connects — nothing guards it, and the nested spin loop means the outer run
finishes only after the inner); start a *measurement* (DeviceReader will try
to open BLE while the diagnostic holds a connection); or **close the main
window** — `closeEvent` then runs the full quit teardown (WebEngine shutdown,
`self._runner.cleanup()`, `_settings.sync()`) and, when the worker finishes,
the save dialog, the "Saved" box and the repair offer all pop up over an app
the user has already quit. A repair accepted at that point is written *after*
`_settings.sync()` and `main._hard_exit` (`os._exit`) skips the QSettings
destructor flush — the accepted repair can be silently lost. Meanwhile the
intro dialog still says *"The window will be unresponsive while it looks"* —
stale from the pre-worker version, and now false (proven live, §1.6: the
window repaints, moves, and takes clicks throughout).
**One-flag fix**: `ProcessEventsFlag.ExcludeUserInputEvents` keeps the window
painting, blocks clicks/keys/close, kills the whole re-entrancy class — and
makes the existing sentence true again.

**F-4 (minor):** the worker's event loop is never closed
(`asyncio.new_event_loop().run_until_complete(...)` with no `close()`), so
each run leaks a loop and its selector/self-pipe fds. Harmless at this
frequency; worth a `finally: loop.close()`.

**F-5 (note):** quit-mid-scan leaves a daemon thread mid-BLE-connection to be
killed by `os._exit`. The OS tears the link down; acceptable — and moot once
F-3 blocks input.
### 1.2 The repair path — can an unconfirmed device reach `cr30_ble_address`?

**No path found, and I looked for one.** The chain, each link read in code:

* `Report.confirmed` is set only from `[c for c in accepted if
  c.get("confirmed")]`, and `ble.discover` sets `confirmed` solely on
  `entry["axis"] == EXPECTED_AXIS` (400, 10, 31) after a real protocol
  exchange (`ble.py:135`). On any exception in `collect()` the list stays
  empty; on a worker crash `result` has no `"confirmed"` key and
  `_offer_cr30_bluetooth_repair` receives `[]` and returns at once.
* A device that *fakes* the axis reaches the setting — but such a device also
  passes `identify()` and the whole protocol, and `_open_ble` **re-identifies
  at every open** before anything is written to the link
  (`measure_bridge.py:685`, and BLE `identify()` genuinely raises on a wrong
  axis, `device.py:219`). The remembered address is a hint, never a trust.
* **"Search normally" is a complete undo at the persistence layer**: it writes
  `""`, and `_remembered_address()` returns `str(value) or None` — empty means
  scan. Nothing else persists the address; the next *successful* open
  re-remembers it, which is the designed fast path, not a repair leftover.
* Two confirmed instruments → it takes `confirmed[0]`, scan order. The dialog
  names the device, so the user sees which one; with two CR30s he cannot pick
  the other. Rare enough to note, not to fix.
* Verified live (§1.6): with the instrument off, the repair was never offered
  across three runs and the sandboxed `cr30_ble_address` was byte-identical
  before and after.

**F-2 (fix before tag): the repair dialog tells the user to do something that
does not exist.** *"You can undo it at any time: run this report again and
choose “Search normally”, or clear it in Preferences."* — there is **no
control in Preferences** that clears `cr30_ble_address` (grepped the whole
settings dialog; the only thing that touches the key is `reset_to_defaults`,
which wipes *every* setting). This is the exact class the owner fixed twice
today (`2c29945d`: "Stop telling the reader not to do something he cannot
do"; the Bluetooth on/off advice before it). And the first half is
conditional too: "run this report again and choose Search normally" only
works while an instrument still *confirms* — the offer never appears
otherwise. Fix is one string (drop the Preferences clause) or one small
control; the stale-address cost is soft either way, because `_open_ble`
falls back to a scan when the address fails.
### 1.3 Does the repair hide the bug?

**Judged adequate.** The report is written to disk *before* the offer, so a
repaired user always has the file; the dialog's last paragraph asks for it
in so many words ("Please still send the report either way… ChromIQ's search
has a fault that we would rather fix than leave you working around"), and
`test_the_offer_still_asks_for_the_report` pins the phrase. Beyond asking,
software can do nothing — there is no telemetry, so a user who never sends
was invisible before the repair existed too. Residual worth knowing: after a
repair the fast path bypasses discovery on that machine, so the discovery
fault will never resurface *locally*; but the log records "remembered
Bluetooth address set from the report", so a later log request identifies a
repaired install.
### 1.4 The report's honesty — one branch still tells the fixed lie

**F-1 (fix before tag): the empty-rescan branch says "ChromIQ REFUSED every
candidate", and that is the inversion `f3bb9b98` says it removed — alive in
one branch, with a regression test enforcing it.**

`bluetooth_report.py`, stage 3: when the report's own scan found a candidate
but ChromIQ's `ble.discover` comes back **empty** (`elif not accepted:`), the
text printed is:

> ChromIQ REFUSED every candidate.
> So a device is advertising the right service but did not answer as a CR30…

Both sentences are false for that branch. An empty shortlist means ChromIQ's
own 15-second scan **no longer saw anything advertising** — nothing was asked
anything, nothing was refused, and the device demonstrably is *not*
"advertising the right service" any more. The real causes are the ones
`f3bb9b98`'s own commit message names: the instrument fell asleep or was
claimed **between the two scans** (they are ~20 s apart — for a real Windows
user this is a plausible, even likely, sequence). The fixed inversion moved
the correct wording into the *unconfirmed* branch and left the old "REFUSED"
headline in the empty branch. Reproduced with the real `collect()` (scanner
faked to show one CR30-looking candidate, `ble.discover` returning `[]`) —
output attached above in my session log, the wrong text verbatim.

Worse, the test guarding it is self-contradictory:
`test_an_empty_rescan_is_not_reported_as_a_refusal` — whose docstring says
"That is not ChromIQ refusing it" — **asserts `"REFUSED every candidate" in
text`**, and its second assertion (`"did not answer as a CR30" not in text`)
passes only because the module wraps the phrase across a line break
(`"…did not answer as\na CR30"` — verified by running it). A green test
guarding the bug, in the newest code, in the diagnostic built for the one
user we know is waiting.

Fix: rewrite that branch to say the candidate vanished between the scans —
press the button and run it again; and rewrite the test to assert *that*
(and drop the line-wrap-defeated phrase check). Text-only; §M does not govern
this file (it is a report body, not a tab message), but the same care applies.

**Other branch texts, read as the recipient (live output in §1.6):**

* Stage-1-failure branch: correct and useful (exception type + message first,
  then macOS-permission / Windows-privacy pointers).
* No-candidates branch: read live with 36 devices listed above it. Tone good,
  the no-Bluetooth-switch and watch-the-screen advice both true and helpful —
  **except the third bullet** (minor, F-6): "this computer's Bluetooth is
  off, or ChromIQ is not permitted to use it" printed directly beneath a
  listing of 36 devices this Bluetooth just saw. Both impossible given
  stage 1 succeeded with hits; print that bullet only when stage 1 saw zero.
* Confirmed branch: accurate ("reachable… if measuring still fails, the
  problem is later than the connection").
* Intro dialog: **"The window will be unresponsive while it looks"** is
  false since the worker-thread fix — see F-3, proven live.
* The changelog's and module's "Nothing here can disturb your instrument" is
  fair: `test_it_opens_no_connection_of_its_own` proves the module constructs
  no `BleakClient`, and stage 3's one frame is `ble.discover`'s status read.
### 1.5 Privacy

**Verified on real scans, not on the code's word** (§1.6): three in-app runs
and one script run, 34–36 devices each, in a real neighbourhood. Every named
non-candidate appears as `(named device, hidden)` — zero plaintext names in
any of the four files. Addresses truncated to the last 6 characters (on
macOS these are random per-host UUIDs, worthless to a third party; on
Windows they are the tail 3 bytes of a real MAC — half-redaction, acceptable
but worth knowing). RSSI and service *counts* only. Candidates are named in
full, which the report needs to be actionable.

* **Desktop default**: `~/Desktop/cr30-bluetooth-report.txt`, and the script's
  old drop-into-the-repo default is gone (`_default_report_path()` → Desktop,
  falling back to home); `.gitignore` carries `cr30-bluetooth-report*.txt`;
  no such file exists in the repo after my runs.
* **Cancelled save**: the report is still written to the Desktop default and
  the "Saved" box names the path — verified live (run 3). Writing after an
  explicit cancel is a judgement call, but the user is told exactly where it
  went and why it is kept; I side with the current behaviour.
* **Send-privately guidance** present in the saved-box text and the script
  header, matching `604a7ef9`.
* Minor (F-7): the script's own docstring still says "The report is written
  next to this script" — stale since the Desktop fix in the same file, and
  it contradicts the final `Report written to:` line. One line.

### 1.6 Live run on this Mac (owner-requested scope)

Driven through the real app on the real screen — `scripts/drive_52_bt_report_verify.py`,
sandboxed exactly like `drive_50` (plist backed up + sha-compared,
`core.settings.QSettings` → sandbox .ini, `CHROMIQ_PRESETS_DIR` +
`custom_output_path` sandboxed, `~/ChromIQ` untouched). The scan, the worker
thread, the message boxes and the report are all real; the only driven parts
are the box buttons (clicked by role on the real widgets) and
`QFileDialog.getSaveFileName`, which is replaced because a native save sheet
cannot be scripted and must never be left waiting. The CR30 was **off**
throughout — the transport was never faked because it was never reached: no
`ffe0` advertiser existed, so stage 3 skipped itself by circumstance, which
is precisely the branch the Windows user is in. Evidence in
`~/Desktop/cr30-bluetooth-tool-verify/` (4 reports, 5 screenshots, driver log).

1. **Completes**: 21.4 s / 21.5 s / 21.0 s per run (20 s scan + overhead;
   with candidates it would be ~36 s — the dialog's "about half a minute" is
   fair).
2. **Responsiveness**: a 100 ms GUI-thread heartbeat kept ticking (206 ticks,
   max gap 539/555 ms); mid-scan the window was moved and a tab switch
   **landed and repainted** (screenshot `mid_scan_window.png` shows the
   Measure tab active, Start Measurement enabled). So the window is fully
   alive — which *disproves* the dialog's "unresponsive" line and *proves*
   the re-entrancy in F-3, including that a measurement could be started
   mid-diagnostic.
3. **Accuracy**: Darwin 24.6.0 arm64 / Python 3.14.6 / bleak 3.0.2 /
   ChromIQ 4.1.5-beta.3 — all correct; 36, 35, 34 devices across runs,
   consistent with the standalone script's own scan minutes later.
4. **The no-candidates branch, read as its recipient**: honest and calm; the
   strongest lines ("NOTHING. That is the most useful line", the sleep and
   held-by-the-phone causes, watch-the-instrument's-screen) are the right
   advice for an instrument that is simply off. Two blemishes: the
   self-contradicting third bullet (F-6) and — worth one added clause —
   nothing says "or it is switched off / battery flat"; "press its button
   once" covers it functionally, but only by luck of phrasing.
5. **The repair was never offered** (no destructive-role box appeared in any
   run) and `cr30_ble_address` in the sandbox was byte-identical before and
   after all three runs; the real plist's sha unchanged.
6. **Save flow**: accepted saves landed where pointed; the cancelled save
   (run 3) still wrote the report to the Desktop default and said so — the
   mis-click no longer loses the scan.
7. **Twice in a row**: identical duration, zero leftover
   `cr30-bluetooth-report` threads after each run, no accumulation. (The
   never-closed asyncio loop, F-4, leaks quietly and invisibly at this
   scale.)
8. The standalone `scripts/cr30_bluetooth_report.py` also ran end-to-end
   (exit 0, report to Desktop, same redaction). One oddity: its no-candidate
   advice says "is Bluetooth switched on **in Windows**" on a Mac — it is a
   Windows-user script, but the line reads odd elsewhere. Minor.

Method note for honesty: my first driver attempt deadlocked *itself* on run 2
(an `id()`-reuse bug in my modal clicker — my bug, not the app's), was
interrupted cleanly, plist verified restored, fixed, re-run. Run-1 numbers
come from the first attempt, runs 2–3 from the second.

**The judgement call the owner left to me — stage 3 connecting to bystander
`ffe0` devices during a diagnostic.** I did not skip the stage (it never
fired here: no candidates). My ruling: **keep it** — it is the entire reason
the report can tell "Windows cannot see it" from "ChromIQ refuses it", it
sends the same single status frame the shipped Measure tab already sends to
any `ffe0` advertiser on every Bluetooth open, and the recipient set is
identical. But two things are different in kind and one sentence should
close the gap: the *standalone script* asks separate consent before
connecting ("Try that now?") while the in-app intro describes only
"looking"; and a diagnostic runs precisely when the user's own instrument is
likely absent, so the odds that the contacted device is a stranger's are
higher than during a measurement. Add one sentence to the intro dialog —
"If something nearby advertises the same service as a CR30, ChromIQ will
briefly connect to it and ask one harmless identifying question." — and the
in-app tool is as honest as its script. Not tag-blocking.

## 2. Legend fault F1 — a regression test IS possible, and now exists ✅

**Delivered:** `tests/test_legend_hover_hide.py::test_a_countermanding_hide_stops_the_running_show_fade`.

**Proven both ways, mutation verified to land** (the early return moved back
above the `anim.stop()`, diff inspected, `.pyc` cleared, `-p no:randomly`):

* fault applied → **FAILS**, on the intended assertion
  (`assert not (anim.state() == Running and endValue == 1.0)`);
* fix restored → **PASSES**, five consecutive runs (randomisation on),
  and the file's other 16 tests still pass.

**Why the two deleted attempts could not work, confirmed empirically:** with
the fault re-applied, all 16 existing tests in the file still pass — including
the F1-labelled scenario test `test_flicking_off_and_straight_back_on_still_hides_it`,
which therefore never discriminated. Both deleted attempts judged the END
state or the animation's state *after pumping events*, and by then the loop
has settled both builds to the same place. The discriminating moment is
**synchronous**: the instant `_start_legend_fade(0.0)` returns, the
countermanded show fade must already be stopped — under the fault it is still
`Running` with `endValue == 1.0`, and no event has yet had the chance to hide
the difference. Two review rules did the rest: the setup self-verifies (the
test asserts a show fade is genuinely running towards 1.0 before the flick
back, so an off-point that never actually left the chip fails loudly instead
of passing vacuously — the shipped scenario test has exactly that silent
hole), and the assertion runs before a single `processEvents`.

The gap note in the test file is kept (its diagnosis of end-state assertions
is correct) with an UPDATE paragraph pointing at the new test.

## 3. Release mechanics — the site/version guard test ✅

`tests/test_the_site_offers_the_current_beta.py`, both directions proven by
mutation (mutations applied to `core/version.py`, verified landed, reverted,
tree confirmed clean after):

* `APP_VERSION` mutated to `4.1.5-beta.99` while the site says `beta.3` →
  **FAILED** with the intended message ("the site offers v4.1.5-beta.3 while
  this build is v4.1.5-beta.99"). The guard fires.
* `APP_VERSION` mutated to plain `4.1.5` → **both tests PASS**: the beta-link
  test returns early on a stable version even though the page still names a
  beta tag, and the download-buttons test still holds `releases/latest`.
* As committed (`beta.3` everywhere): passes. `core/version.py` at HEAD is
  `4.1.5-beta.3`; `CHANGELOG.md` leads with `## v4.1.5-beta.3`;
  `docs/index.html:361` links `releases/tag/v4.1.5-beta.3`. All three agree.

One deployment-order note, not a blocker: the site link goes live when master
is pushed, the tag exists only once pushed — push and tag in the same breath
or the live page 404s for the minutes between.

## 4. Priority 2 — spot checks of the rest of the range

Reports 49/50 verified this ground (including byte-identical guided layout);
I did not redo it. Spot checks only:

* **Changelog `4.1.5-beta.3`**: every item maps to a commit in the range —
  **except one**: *"A CR30 chart no longer prints spacers by default"* under
  "Changed" **shipped in beta.2** (commit `2bd8d2e8`, tagged
  `v4.1.5-beta.2`, and beta.2's own changelog already announces it in nearly
  the same words). A beta-2 user reading beta-3's notes is told an existing
  behaviour is new. Delete the paragraph from the beta.3 entry. Minor.
* **`core/version.py`** = `4.1.5-beta.3`, committed; changelog heading and
  site tag agree (§3).
* **Site copy (`docs/index.html`, live and public)**: the CR30 section is
  accurate about USB/BLE, the 33 mm body (constant confirmed in
  `ui/tiff_preview.py`), and links the beta tag. One phrasing wart, added in
  `b46ab0cc`: *"a CR30 stops measuring altogether if anything magnetic
  touches its opening"* — beta.2's own Fixed list calls that exact claim
  "the opposite of the danger. It answers — with a plausible number". The
  sentence then contradicts itself ("…so ChromIQ learns what your instrument
  reports in that state"). Suggest "a CR30 quietly stops **really**
  measuring — it answers with a stored value instead". Minor, not blocking.
* **Aiming overlay / layout moves / margin changes**: covered by reports
  49/50 and by the green everyday tier (which contains their tests); the
  known-issues section honestly carries the two open Bluetooth items. The
  aperture (4 mm) and body (33 mm) constants match the code.
* **Nothing in the range is unshippable in a beta.** The Bluetooth report is
  the right thing to ship this week — with the three fixes below.

## 5. Everyday test tier ✅

`QT_QPA_PLATFORM=offscreen pytest -n auto`, run 2026-08-30 on this Mac:
**8228 passed, 262 skipped, 3 xfailed in 1:24**. Green, and inside the
expected wall-clock band.

## 6. Verdict

**NO — three small fixes first, all in the newest code, all text-or-one-flag.
Nothing touches the layout or chart paths that reports 49/50 verified, so
nothing else needs re-proving afterwards beyond the gate.**

The shortest list that makes it YES:

1. **F-1** — rewrite the empty-rescan branch of
   `workflow/cr30/bluetooth_report.py` (the `elif not accepted:` arm): the
   candidate *vanished between the two scans* (asleep / claimed); it was not
   "REFUSED" and is not "advertising". Rewrite
   `test_an_empty_rescan_is_not_reported_as_a_refusal` to assert the new
   wording and to stop relying on a line-wrap to miss the old one. This is
   the report's core promise — tell the two cases apart — broken in one of
   its four endings, for a plausible real sequence.
2. **F-2** — the repair dialog's undo sentence: drop "or clear it in
   Preferences" (no such control exists), or add the control. The exact
   mistake class fixed twice today by name.
3. **F-3** — `_run_cr30_bluetooth_report`: change the spin loop to
   `processEvents(ProcessEventsFlag.ExcludeUserInputEvents, 50)`. One flag:
   it blocks the second-report/measurement/close re-entrancy proven live in
   §1.6, and makes the dialog's existing "unresponsive while it looks"
   sentence true instead of false.

(1) and (2) change user-facing strings → German per the i18n rules, and the
gate re-run. My contribution is already in the tree: the F1 legend
regression test (`test_a_countermanding_hide_stops_the_running_show_fade`),
proven to fail on the fault and pass on the fix.

Worth fixing, not blocking: F-4 close the worker's asyncio loop; F-6 the
self-contradicting "Bluetooth is off" bullet; F-7 the script's stale
"next to this script" docstring line; the beta-2 spacers paragraph
duplicated into beta-3's changelog; the site's "stops measuring altogether";
one consent sentence in the intro dialog for stage 3 (§1.6); the script's
"in Windows" phrasing on other platforms; the Windows MAC last-6
half-redaction; `confirmed[0]` when two instruments confirm.
