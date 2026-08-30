# 55 — Verifying d8ceaca8, and the Windows question

**Status:** COMPLETE — §A–I reviewed `d8ceaca8`; **§J is the final check for `v4.1.5-beta.4`** (`d926b358`, `f11b9bc6`) and ends in the verdict.
**Date:** 2026-08-30
**Reviews:** `d8ceaca8` "ChromIQ now says which way it connected, and can prove
it afterwards", against report 54.
**Constraint:** the CR30 was never touched. No serial port was opened and no
Bluetooth connection was made. The app was driven on screen with the settings
plist backed up and restored.

## Sections

- [x] A. Verdict on the three changes, one at a time
- [x] B. The gaps — where the transport line does NOT appear (incl. **B.4, found on screen**)
- [x] C. ⚠ **The two halves were shipped un-wired**
- [x] D. Was leaving the preference out the right call?
- [x] F. The recipe a user can run TONIGHT, on all three platforms
- [x] G. The Windows question, ranked by likelihood × cost
- [x] H. What beta 4 should contain, and what must not
- [x] I. What blocks beta 4

## The three things to read if you read nothing else

1. **The warning and the summary were shipped un-wired.** The line added to be
   found is silently dropped by report 54's own parser (§C). The user recipe in
   §F is written to be independent of it, which is why it is a grep and not a
   feature.
2. **On screen, at the log height this machine is set to, the transport note is
   invisible** — written first, then scrolled off (§B.4). Five-line fix.
   Headless tests pass; only looking found it.
3. **The two likeliest Windows explanations both cost nothing to settle** (§G.1),
   and the smallest useful change is a text change to a diagnostic (§G.3 rank 1).
   Everything else would be four stacked inferences shipped to every user.

---

## A. The three changes, one at a time

**All three are correct. Two have gaps; one of the gaps is serious.**

Everything below was proved by RUNNING, not by reading — and every claim is
checked against the parent commit `262b49af` in a throwaway git worktree, so the
mutation is proven to land rather than assumed. Two new test files were added
(`tests/` only, per the constraint):

* `tests/test_the_measure_log_names_the_transport.py` — 5 tests
* `tests/test_a_failed_bluetooth_open_leaves_a_trace.py` — 5 tests

Against `d8ceaca8`: **10 passed.** Against `262b49af`: **8 failed, 2 passed.**
The two that pass on the parent are the two written as future guards (an unknown
`kind` says nothing; the success path still names the transport), and they pass
there trivially because nothing is said at all. Stated so nobody reads "2 passed"
as coverage.

### A.1 The Bluetooth-failure WARNING — correct, and better placed than I proposed

`measure_bridge.py:855-863`. Verified by driving the real `_open()` with both
transports faked to raise:

```
2026-08-30 19:33:13,912 [INFO]    workflow.cr30.measure_bridge: CR30: no USB device (no CH34x serial device found); trying Bluetooth
2026-08-30 19:33:13,912 [WARNING] workflow.cr30.measure_bridge: CR30: Bluetooth failed too (nothing advertising); no instrument could be opened
```

* **Level:** WARNING. `core/logger.py:47` sets the root to DEBUG and `:57` the
  rotating file handler to DEBUG, so it is kept. Proven end to end by
  `test_the_line_really_reaches_a_file_on_disk`, which builds a real
  `RotatingFileHandler` into a temp directory (the user's own log is never
  written to) and asserts the line is in the file, with its logger name and
  level, in the exact form the grep in §F looks for.
* **The reason travels with it** — `(%s)` carries `ble_err`, so the line says
  *why*, not merely *that*. `test_the_reason_travels_with_it` pins it.
* WARNING rather than INFO is the better choice and worth saying why: it is the
  last level that survives if this logger is ever quieted the way
  `core/logger.py::_NOISY_LIBRARIES` quiets Pillow, and `[WARNING]` makes the
  line findable by level alone on a user's machine.

**No gap.** This one is simply right.

### A.2 The transport line — correct where it runs, and it does not run everywhere

`ui/tabs/tab_measure.py:7365-7379`. Both branches verified by driving the real
`_run_cr30_calibration()` on a real `TabMeasure` with only the device faked:

```
[NOTE] Connected to your CR30 over the USB cable.      (kind == "usb")
[NOTE] Connected to your CR30 over Bluetooth.          (kind == "ble")
```

* **A remembered address still names Bluetooth.** The fast path skips discovery
  but still builds `CR30(t, "ble")`, so `kind` is unchanged. Pinned by
  `test_a_remembered_address_still_names_bluetooth`, because the whole repair
  feature routes users onto that path and it is the one that could silently lose
  the note.
* **An unknown `kind` says nothing rather than guessing.** `if kind:` guards it.
  Correct: `kind` is empty only when no device opened, and inventing a transport
  there would destroy the one property this note has.
* **It cannot break a measurement.** Wrapped in `try/except` with a debug log.
  Right call for a note.

Gaps in B and C below.

### A.3 The tooltip DEBUG line — clean removal, nothing depended on it

* `grep -rn "TooltipButton created"` across the tree (code, tests, docs,
  scripts): **zero hits** outside my own report 54. Nothing read it.
* The module's `log` is **still used** — `ui/tooltip_button.py:192` logs when a
  tooltip dialog is actually *opened*, which is a real user action at a sane
  volume. So no unused import and no dead `get_logger`.
* The comment left in its place explains why, with the measurement. Good: the
  next person to "add a bit of debug logging here" will read it first.
* `tests/test_help_cards_untranslated_are_tracked.py` budgets went 110 → 112 for
  the eleven non-German languages. That is a **translation** budget, unrelated to
  the deleted line; it is the cost of the two new strings. See C.3 — it is the
  one edit in this commit I would question.

**Predicted effect, restated as a prediction and not a result:** report 54
measured 99,751 of 170,000 retained lines (58.7 %) as this one call. Removing it
should roughly triple how far back a user's log reaches. **That cannot be
confirmed until a machine has run the new build long enough to rotate.** It is
not confirmed here and should not be written up as if it were.

---

## B. The gap — where the transport line does NOT appear

### B.1 Manual + "Skip initial calibration (-N)": no line at all

The note lives inside `_calibrate_and_confirm`, which is reached only through
`_run_cr30_calibration`, which `_on_start` guards at `tab_measure.py:5834`:

```python
if params.external_values and not params.disable_initial_cal:
```

So:

| mode | Skip initial calibration | transport line? |
|---|---|---|
| **Guided** | hard-coded False (`tab_measure.py:5836-5843`) | **yes, always** |
| **Manual**, box unticked | False | **yes** |
| **Manual**, box ticked | True | **NO — nothing is said** |

Pinned by `test_skipping_the_calibration_leaves_the_transport_unnamed`, which is
written to **fail loudly and tell you to delete it** the day the note also runs
on the skip path.

Why it matters more than the row count suggests: **skipping the calibration is
what you do on the second and third attempt.** The user debugging a connection
is disproportionately the user who has already calibrated once this session and
ticks the box to get on with it — and that is exactly the user this note was
written for. In that state ChromIQ opens the instrument at the first patch read
(`measure_bridge.py:877`, via `__call__`) and says nothing about how.

**Cost to close: small.** The `kind` is known the moment `_open()` returns; the
tab already has a handler for the lazy-open path. The natural home is a signal
from the reader on first open, which would cover every route at once — including
the two below.

### B.2 A transport CHANGE mid-session is invisible

`_on_cr30_device_lost` → "Carry on measuring" → `_carry_on_after_the_instrument_went`
→ `bridge.rearm()`, and `DeviceReader.__call__` reopens with `self._dev = None`
(`measure_bridge.py:903-908`). If the cable was pulled and Bluetooth then answers
— or the reverse — **the instrument is now on a different transport and nothing
says so.** This is the one moment in a session when the transport genuinely
changes, and it is the only moment currently unreported.

Not a regression; the line simply does not reach there. Same fix as B.1.

### B.3 A failed calibration says nothing about how it connected

`tab_measure.py:7344-7363` returns False before the note. So a user whose device
opened fine but whose calibration command failed sees "The calibration did not go
through" and still cannot tell which transport was in use — which is precisely
the pairing of symptoms most worth knowing. Cheap to fix by moving the note above
the `if "error" in result:` block; but the device handle exists by then either
way, so this is a nicety, not a fault.

### B.4 ⚠ On screen: at the log height THIS MACHINE IS SET TO, the note is invisible

**Found by looking, and no headless test could have found it.** The text is in
the widget — my tests assert on `toPlainText()` and pass — it simply cannot be
seen.

Driven in the real app (`scripts/drive_55_transport_note.py`; the real
`MainWindow`, the real Measure tab, the real method, only the device and the
modals faked):

| `log_visible_lines` | window | note visible? |
|---|---|---|
| **9** (the shipped default, `core/settings.py:112`) | 1900×1400 | **YES** — reads clearly, directly above the calibration note |
| **2** (what this machine is actually set to) | 1900×1400 | **NO** — scrolled out of sight |
| 9 | 1280×900 | **NO** — `_max_lines_for` caps the pane to the room in the column (`ui/widgets.py:525-563`) |

At nine lines it looks like this, and it is good:

```
[NOTE] Connected to your CR30 over Bluetooth.

[NOTE] ChromIQ asked the CR30 to take its white calibration. It cannot check
the result — the instrument reports the same value whatever is under the cap.
```

At two lines the user sees only *"…the instrument reports the same value whatever
is under the cap."* The note is written FIRST, a longer note follows it, and
`ensureCursorVisible()` then scrolls to the bottom.

This is not unique to this note — every note in that pane has it — but this
note's entire value is being *seen*, and the pane height is a user setting we do
not control. **The owner's own machine is set to 2.**

**The fix is a five-line move and it is free:** `ensureCursorVisible()` always
leaves the LAST line showing, so writing the transport note *after* the
white-calibration note makes it visible at any pane height, in any window. It
also reads better in that order — "here is what I did, and here is how I was
connected".

Screenshots: `scratchpad/drive55/measure-log-{bluetooth,cable}-{2,9}-1900x1400.png`.

**The settings plist was backed up before the run and restored byte-identically
afterwards** (sha1 `33fd96c8…` before and after; `log_visible_lines` back to 2,
`custom_output_path` back to empty). `CHROMIQ_PRESETS_DIR` and the output path
were sandboxed under the scratch directory throughout, and nothing was written
to `~/ChromIQ/CR30-Test`.

---

## C. ⚠ THE ONE THAT MATTERS — the two halves were shipped un-wired

**The warning is written. The summary that was supposed to read it does not
look for it.**

Report 54's prototype (§D.7 and its appendix) matches on a fixed needle list:

```python
_WANTED = (
    ("attempt",   "no USB device"),
    ("opened",    "CR30: opened over "),
    ("timing",    "CR30 BLE: found in "),
    ("staleaddr", "the device at the remembered Bluetooth address"),
    ("usbrefuse", "did not answer as a CR30"),
)
```

`"Bluetooth failed too"` is not in it. Run end to end just now — the real
`_open()` failing both ways into a real temp log, then report 54's parser over
that file:

```
--- what the log now contains ---
[INFO]    CR30: no USB device (no CH34x serial device found); trying Bluetooth
[WARNING] CR30: Bluetooth failed too (nothing advertising); no instrument could be opened

--- what the report-54 prototype extracts ---
   ('attempt', 'no USB device (no CH34x serial device found); trying Bluetooth')

failure captured? -> False
lines in file: 2   events extracted: 1
```

**The line added specifically to be found is silently dropped by the thing that
was going to find it.** The failure is still only inferable by absence — exactly
the fault the commit set out to remove — for anyone using that summary.

This is my fault as much as anyone's: report 54 shipped the needle list in an
appendix and the warning in a recommendation, and nothing tied them together.

**Two consequences, and the second is the one to act on:**

1. Whenever the summary is implemented, `("failed", "Bluetooth failed too")`
   must be in `_WANTED`, and the counts must report it
   (`Bluetooth failed: N, last on …`). One tuple entry.
2. **The user-facing recipe in §F must not depend on that list at all.** It is
   built from a grep whose pattern is written out in full, so it can be checked
   by eye. That is why §F looks the way it does.

### C.2 A second, smaller wiring gap: `_no_device_help` is still `auto`-only

Unchanged by this commit and correctly so — report 54 §E.1(ii) — but worth
restating because it is now the ONLY thing standing between a future transport
preference and a raw library error. If the preference is ever built, this is
gate one.

### C.3 The translation-budget bump is the one edit I would question

`tests/test_help_cards_untranslated_are_tracked.py` moved eleven languages from
110 to 112 to admit the two new strings as untranslated. German was translated
(`data/i18n/de.json`), the other eleven got the keys with English values.

That matches the project's own rule — *"Translation only before final, not during
beta"* — so it is defensible for a beta. But raising a budget is how a budget
stops meaning anything, and this one has now been raised for a reason unrelated
to help cards. **Ask the owner whether beta 4 should carry the eleven
translations of two short sentences instead.** It is fifteen minutes of work and
it puts the budget back.

Not a blocker either way.

---

## D. Was leaving the preference out the right call?

**Yes — and this round produced a third reason that did not exist when the
decision was made.**

The two reasons given in the commit message are both correct and both were
proven in report 54: `transport="ble"` is Bluetooth-only with no fallback
(§E.1 i, proven by running `_open()`), and neither non-`auto` branch builds
`_no_device_help` (§E.1 ii, proven by reading `_open()`). Shipping the
preference on top of those would hand the user who is already stuck a slower
failure and a worse message.

**The new reason is B.4.** Report 54 §G.3 argued that "Bluetooth first, then the
cable" fails safely *because* the fallback would not be silent — the user would
see *"ChromIQ looked over Bluetooth first, as you asked, and did not find it, so
it is using the cable"*. That argument rests entirely on the transport line being
seen. On screen, at the log height this machine is set to, it is not. So the
preference's safety story is not yet true, and **B.4 is now a prerequisite for
the preference, not a cosmetic tidy.**

Order of work, unchanged in substance and now with one more step:

1. B.4 — make the transport line reliably visible (five-line move).
2. B.1 — make it appear on every route, not only the calibrated one.
3. `_no_device_help` for the non-`auto` branches.
4. an additive `"ble-first"` branch in `_open()`.
5. only then the Preferences control.

None of 3–5 belongs in beta 4.

---

## F. The recipe — what a user can do TONIGHT, with no new build

**This is the deliverable.** It works on the log a user already has, because
`"trying Bluetooth"` and `"opened over …"` have been written for as long as the
CR30 code has existed. On a beta-4 build it additionally catches
`"Bluetooth failed too"`.

### F.0 The rule it obeys: never ask for the whole log

Report 54 §D.4 measured `chromiq.log` naming **16 distinct nearby Bluetooth
devices across 7,597 lines**, including a television by make and model — while
`bluetooth_report.py:27-30` redacts exactly that, with a comment saying the file
is "written to be sent to a stranger". Asking for the whole log would undo our
own redaction.

So the command below **filters first and writes a small file**. Verified on this
machine's real six-file log: **77 matching lines, and zero of them contain a
third-party device name** (`grep -ci "Discovered device\|webOS\|RSSI\|kCBAdv"` on
the filtered output returns 0). What it does contain is the user's own port path,
their own instrument's Bluetooth address, and timings — their own hardware, which
is the thing we are being asked to look at.

### F.1 The pattern, written out so it can be checked by eye

```
trying Bluetooth|opened over|Bluetooth failed too|BLE: found in|did not answer as a CR30|remembered Bluetooth address
```

Six phrases. Every one is a sentence ChromIQ writes about its own instrument.
None of them can match a bleak advertisement line.

### F.2 ⚠ Sort the output — the file glob is NOT chronological

`chromiq.log*` expands as `chromiq.log, chromiq.log.1 … .5` — the **newest file
first and the oldest last**, because the rotation numbers count backwards. Read
without sorting, the story runs in the wrong order. The ISO timestamps sort
lexicographically, so `| sort` is the whole fix. Confirmed on the real log: the
last line before sorting was 29 Aug; after sorting it is 30 Aug.

### F.3 macOS — RUN AND VERIFIED on this machine

```bash
grep -hE "trying Bluetooth|opened over|Bluetooth failed too|BLE: found in|did not answer as a CR30|remembered Bluetooth address" \
  ~/Library/Logs/ChromIQ/chromiq.log* | sort > ~/Desktop/cr30-transport.txt
wc -l < ~/Desktop/cr30-transport.txt
```

Log location: `~/Library/Logs/ChromIQ/chromiq.log` (`core/platform_paths.py:122`).

### F.4 Linux — same shape, UNVERIFIED path (no Linux machine here)

```bash
grep -hE "trying Bluetooth|opened over|Bluetooth failed too|BLE: found in|did not answer as a CR30|remembered Bluetooth address" \
  "${XDG_STATE_HOME:-$HOME/.local/state}"/ChromIQ/logs/chromiq.log* | sort > ~/Desktop/cr30-transport.txt
```

The path is read from `core/platform_paths.py:126-130`; the grep is the same
tested one.

### F.5 Windows — ⚠ NOT RUN. No Windows machine and no PowerShell here.

```powershell
$p = "trying Bluetooth|opened over|Bluetooth failed too|BLE: found in|did not answer as a CR30|remembered Bluetooth address"
Select-String -Path "$env:LOCALAPPDATA\ChromIQ\Logs\chromiq.log*" -Pattern $p -ErrorAction SilentlyContinue |
  ForEach-Object { $_.Line } | Sort-Object |
  Set-Content "$env:USERPROFILE\Desktop\cr30-transport.txt"
Get-Content "$env:USERPROFILE\Desktop\cr30-transport.txt" | Measure-Object -Line
```

Log location: `%LOCALAPPDATA%\ChromIQ\Logs\chromiq.log` (`platform_paths.py:123`).

**Say this to whoever sends it**, because an untested command that fails silently
is worse than none: *if the last line reports 0, tell us that — an empty result
is itself one of the three answers, and we would rather know it came back empty
than assume the command worked.*

### F.6 What the three answers look like

Each block below is real output, produced by running the tested macOS command
against a synthetic log for that case.

**(a) ChromIQ never tried Bluetooth** — cable opens only, no `trying Bluetooth`:

```
2026-08-20 10:00:01,000 [INFO] workflow.cr30.measure_bridge: CR30: opened over usb
2026-08-21 09:15:44,000 [INFO] workflow.cr30.measure_bridge: CR30: opened over usb
```

> ChromIQ was using the cable and never looked at Bluetooth. Whatever happened,
> it did not happen inside ChromIQ. **This is the case report 54 §A.3 proved is
> possible and nobody could confirm.**

**(b) It tried and failed** — the beta-4 shape, both lines present:

```
2026-08-25 21:03:11,000 [INFO]    …: CR30: no USB device (no CH34x serial device found); trying Bluetooth
2026-08-25 21:03:47,000 [WARNING] …: CR30: Bluetooth failed too (No CR30 found over Bluetooth. The device
                                     stops advertising while another central holds it); no instrument could be opened
```

> ChromIQ tried, and the reason is on the line. Thirty-six seconds between them
> is a full scan that found nothing. **This is the case that makes every
> Bluetooth hypothesis in §G live.**
>
> On a build older than beta 4 the same case shows as a `trying Bluetooth` line
> with **no** `opened over ble` after it. That is still an answer, just a
> quieter one — and it is why the recipe is worth sending even from an old build.

**(c) It tried and it worked:**

```
2026-08-26 08:41:02,000 [INFO] …: CR30: no USB device (no CH34x serial device found); trying Bluetooth
2026-08-26 08:41:04,000 [INFO] …: CR30 BLE: found in 15.42 s, connected in 2.33 s, notifications in 0.06 s
2026-08-26 08:41:06,000 [INFO] …: CR30: opened over ble
```

> Bluetooth works on that computer, and the timings say where the time went.

### F.7 The one thing to say alongside it

An empty file is **not** proof that nothing happened — it may only mean the log
has rotated past it. The rotation is six files of 5 MB (`core/logger.py:54-55`),
which on this (heavy) machine was under three days before the tooltip line was
removed. **State that distinction when asking, or a "no record" will be read as
a "no".**

---

## G. The Windows question

### G.0 What we are allowed to claim

Report 53 §2.1 states the evidence base and it is thin in one specific way:

> *"we know one unit advertises `ffe0` on one operating system. We know nothing
> about all units, and nothing about Windows."*

One BLE scan capture exists, from one Mac, on 2026-08-28. `PLATFORM_SUPPORT.md`
in the research repo: *"Windows Bluetooth is still tested by nobody, and remains
the largest untested area in this repository."* There is no second CR30, no
Windows machine, no HCI capture separating ADV_IND from SCAN_RSP, and no
PowerShell on this machine either.

So the ranking below separates **PROVEN** from **INFERENCE**, and the
recommendation turns on which is which.

### G.1 The ranking — likelihood × cost to settle

| # | Hypothesis | Status | Likelihood | Cost to SETTLE |
|---|---|---|---|---|
| **1** | **H0 — ChromIQ never attempted Bluetooth at all.** `auto` tries USB first and reaches BLE only in the `except`; nothing in the UI can ask for Bluetooth. | **PROVEN mechanism** (report 54 §A.3, run) | **highest** | **ZERO** — §F, tonight, no build |
| **2** | **H2 — the `ffe0` filter drops his instrument.** Service UUIDs are optional; the one measured advertisement does not fit 31 octets; Windows is the one platform where bleak merges ADV and SCAN_RSP by hand. | mechanism **PROVEN**, applicability **INFERENCE** | **highest of the technical ones** | **ZERO** — the shipped report's stage 1 already prints every device with its service list |
| 3 | H1 — instrument asleep, or held by the phone app. | PROVEN as a mechanism, everywhere | high, and boring | zero — the report says so already |
| 4 | H4 — Windows adapter, driver or privacy setting. | plausible | medium | zero — report stage 1 fails loudly |
| 5 | H3 — his unit's firmware does not advertise `ffe0`, or has no radio. | unfalsified, unsupported | medium | needs his report |
| 6 | H6 — a rotating (RPA) Bluetooth address on Windows. | address type **NOT ESTABLISHED** | low for a first connection | needs a Windows scan |
| 7 | H5 — STA/MTA apartment threading. | **AUDITED and it holds** — all three bleak entry points are off the GUI thread | ruled out | done |
| 8 | H7 — a stale `cr30_ble_address`. | **ruled out** — the fast path re-identifies and falls back | ruled out | done |

**The two most likely explanations both cost nothing to settle, and neither
needs a code change.** That is the finding.

### G.2 ⚠ A new one: the report's ONE Windows safety net may be comparing the wrong string

`bluetooth_report.py:131` is the only thing in the whole app that can catch an
instrument advertising a **name but no service UUID** — precisely H2's signature:

```python
elif serial and _looks_like(name, serial):
```

`_looks_like` (`:63-77`) is a containment match on alphanumerics between the
advertised name and **whatever the user typed** when the report asked for their
serial number.

But report 53 §4.1 established, measured on the one unit, in one process, with
ChromIQ's own parser:

| comparison | result |
|---|---|
| advertised `local_name` == `Identity.second_id` (`AA 0A 01`) | **True** |
| advertised `local_name` == `Identity.device_id` (`AA 0A 00`) | **False** |
| `device_id` == `second_id` | **False** |

Two different 10-character strings, and only the second is the Bluetooth name.
**Which one the vendor's software prints under "Instrument settings" is not
established anywhere** — I read `LOCAL_DEVICE_IDS.md` in the research repo and
grepped both repos; the question is never answered. And `_looks_like` requires
one string to contain the other, which two different 10-character strings never
will.

So: if the vendor prints `device_id`, the report's prompt
(`ui/main_window.py:1789`, *"the manufacturer's own software shows it under
Instrument settings"*) collects the wrong id, the containment test fails, and
**the safety net for the most likely technical hypothesis silently does not
fire.** The user is told nothing and the instrument stays hidden behind the
redaction — which is the exact scenario `bluetooth_report.py:132-136`'s own
comment describes.

`bluetooth_report.py` has no knowledge of `second_id` at all
(`grep second_id` → no hits).

### G.3 The smallest changes, ranked

**Rank 1 — flag devices that advertise NO services at all. Cost: one text
change. Blast radius: zero.**

Today those appear in stage 1 as `(named device, hidden) …addr rssi=-72
services=0`, indistinguishable from a neighbour's earbuds. But the CSS says an
omitted Service UUID list means *"there may be more services; I have told you
about none of them"* — so **an empty list is the exact signature of the failure
mode**, and the report is silently redacting the answer.

Adding a stage-2 line — *"N device(s) advertised no services at all. ChromIQ
cannot rule any of them out: a device is allowed to reveal its services only
after you connect, and an instrument doing that is invisible to ChromIQ's
search"* — connects to nothing, writes nothing, changes no behaviour, and turns
his report into one that answers H2 by itself. **This is the one I would ship.**

It also covers G.2 without depending on him typing anything.

**Rank 2 — say both ids when asking for the serial.** The prompt should not
assume which string the vendor prints. Cheap, but it still relies on his typing,
and rank 1 makes it unnecessary. Ship only if rank 1 is refused.

**Rank 3 — probe the empty-service devices in the report's stage 3. Cost:
moderate. Blast radius: real.** This turns "cannot rule out" into "is / is not".
But it means connecting to strangers' devices and writing a status frame — the
fault class closed in `1de3f3af`. Defensible **only** inside the report (a
deliberate diagnostic the user opted into), **only** when the `ffe0` shortlist
found nothing, and with a hard cap. **Not for beta 4.**

**Rank 4 — DO NOT widen the filter in `ble.discover` itself.** That is the
measure path, on every Start, for every user, on every platform, to fix a problem
we have not confirmed exists — and report 53's own conclusion is that this code
works for the one Bluetooth user we have. **No.**

**Rank 5 — name-based discovery from a remembered `cr30_ble_name`** (report 53's
Tier-2 proposal, unimplemented). Helps only users who have used the cable, and
fails identically if the *name* is the element riding in the SCAN_RSP — which is
the more common HM-10 layout and which we have never observed either way.
Unproven benefit, real cost. **Not for beta 4.**

### G.4 What we would be shipping blind, stated plainly

Rank 1 changes **text in a diagnostic report**. Nothing about the instrument
path, nothing about discovery, nothing that runs during a measurement. If the
inference behind H2 is wrong, the cost is one extra paragraph in a report. That
is the only change in this whole area whose worst case is harmless.

Everything at rank 3 and below would be shipping a behaviour change to every
user, on evidence that is:

* **PROVEN:** service UUIDs are optional (CSS, primary source); bleak on WinRT
  merges ADV and SCAN_RSP by hand and its union is incomplete until both halves
  arrive (bleak 3.0.2's own docstring); the advertised name is `second_id`.
* **INFERENCE, and the reports say so themselves:** that the CR30's
  advertisement is 33 octets (computed from CoreBluetooth-level fields, never
  read off the wire — and 30 octets *does* fit if Flags is absent); that it
  therefore uses SCAN_RSP; that a Windows controller fails to complete the
  exchange; that `service_uuids` comes back empty on Windows. **Nobody has ever
  run a BLE scan for a CR30 on Windows.**

Four inferences stacked, none observed, to justify a change to the path that
opens every user's instrument. **That is not a trade to make blind when the two
top hypotheses can both be settled for free.**

### G.5 So the Bluetooth answer for Windows users, concretely

Not a code change. Two asks, and the second one works because of a fix that has
already shipped:

1. **Run the §F command** and send `cr30-transport.txt`. Settles H0 — did
   ChromIQ ever try — for attempts already made, from a log he already has.
2. **Run Tools ▸ Instruments ▸ "CR30 Bluetooth report"** and send the file.
   Stage 1 lists every device with its service count, which settles H2, H3 and
   H4 between them.

Ask 2 is worth making *now* specifically because report 51 §1.1 found the tool
would have died on Windows within half a second — Qt's Windows plugin puts the
GUI thread in a single-threaded apartment and bleak's scanner raises rather than
scanning. `main_window.py:1813-1834` moved it to a worker thread, and report 53
§5.6 audited all three bleak entry points as off the GUI thread. **The tool built
for the one untested platform should now actually run there.** That is unverified
on real Windows and should be said when asking.

One residual, from report 53 §5.6 and worth carrying forward as a rule rather
than a fix: `assert_mta` guards the **scanner** only. A `BleakClient.connect` on
a blocked STA thread would **hang, not raise**. Anything new that touches bleak
must stay on a worker thread.

### G.6 One tidy found on the way

`workflow/cr30/ble.py:84-86` carries an orphaned fragment left by `262b49af`'s
comment rewrite — a dangling clause with an unmatched parenthesis:

```
# `device.py::identify`), and the tile-learning key then differed by transport.
# (the value
# AA 0A 01 returns off USB) and is therefore UNIT-SPECIFIC. Hard-coding one
```

Comment only, no behaviour. But this is the exact comment whose self-contradiction
caused the `device_id`/`second_id` bug in the first place, so leaving it
half-rewritten is asking for the same fault twice. Three lines to delete.

---

## H. What beta 4 should contain

Beta 4's job is **one thing**: make the Windows user's Bluetooth question
answerable. Everything is judged against that.

### H.1 Already in, and it earns its place

| | Change | Verified |
|---|---|---|
| ✅ | the `Bluetooth failed too` WARNING | A.1 — run, into a real file |
| ✅ | the Measure tab's transport note | A.2 — run, both transports, on screen |
| ✅ | the tooltip DEBUG line removed | A.3 — nothing depended on it |

### H.2 Should go in — cheap, clearly right, all verified above

| | Change | Size | Why for beta 4 |
|---|---|---|---|
| 1 | **Move the transport note to AFTER the white-calibration note** (B.4) | 5 lines | `ensureCursorVisible()` always leaves the last line showing, so this makes it visible at any pane height. Without it the release note claims something a user with a short log pane will not see. |
| 2 | **Flag "advertises no services at all" in the Bluetooth report** (G.3 rank 1) | text only | Turns his report into one that answers the most likely technical hypothesis by itself. Connects to nothing, writes nothing. |
| 3 | **Delete the orphaned comment fragment** in `ble.py:84-86` (G.6) | 3 lines | It is the descendant of the comment that caused the `device_id`/`second_id` bug. |

None of the three changes behaviour during a measurement.

### H.3 Should NOT go in

| Change | Why not |
|---|---|
| the transport **preference** | D — blocked on three prerequisites, one of them new (B.4) |
| widening the filter in **`ble.discover`** | G.3 rank 4 — the measure path, every user, every platform, four stacked inferences |
| **probing** empty-service devices (report stage 3) | G.3 rank 3 — connects to strangers; the `1de3f3af` fault class. After his report, not before |
| the **log-summary feature** in the app | §F's recipe does the job tonight with no build. Build it once we know what the answer was |
| a `cr30_ble_name` remembered from USB | G.3 rank 5 — unproven benefit |
| **translating** the two new strings now | C.3 — the project's own rule is translation before final, not during beta. Ask, do not assume |

### H.4 The outstanding questions from report 54 §J.4

| | Question | Call |
|---|---|---|
| 1 | `bleak` into `_NOISY_LIBRARIES`? | **OWNER'S — it is a privacy decision, not a technical one.** Both sides, fairly: *for* — it is the part of the log that names the user's neighbours in the clear, 7,597 lines and 16 devices on this machine (report 54 §D.4). *Against* — it is the only running record of what a Bluetooth scan actually saw, and we are about to ask a Windows user for exactly that kind of evidence. Neither artefact we are asking for in §G.5 contains it, so quieting costs us nothing **today**. I am not deciding it. |
| 2 | May the report attempt a real BLE open? | Defer. Not needed for beta 4; §G.5 ask 2 covers it |
| 3 | A "Bluetooth only" option? | Defer with the preference |
| 4 | May a measurement message name a Preferences control? | **Moot** until the preference exists |
| 5 | Reword *"nothing to hunt for in Preferences"* (`main_window.py:1927`) | **Moot, and this is good news** — the sentence is still TRUE, because the preference is not shipping. Nothing to do for beta 4 |
| 6 | The two one-line source edits | **Done** — both are in `d8ceaca8` |

### H.5 The release note for beta 4, in one paragraph

> ChromIQ now tells you which way it reached your CR30 — the USB cable or
> Bluetooth — in the measurement log, and writes both that and any failed
> Bluetooth attempt into its own log file. Until now a Bluetooth attempt that
> did not work left no trace at all, so nobody could tell afterwards whether it
> had even been tried. It also stops filling that log file with a line every
> time a help icon is drawn, which was using up well over half the space and
> pushing the entries that actually diagnose problems out of it.

Nothing in that paragraph promises a fix to Bluetooth. It shouldn't: beta 4
does not fix Bluetooth, it makes Bluetooth diagnosable, and saying otherwise
would be the fourth time today that shipped text described something that does
not exist.

---

## I. What blocks beta 4

**Nothing hard blocks it. Three things must happen first, and one of them is
mandatory by CLAUDE.md.**

| | Item | Status |
|---|---|---|
| 🔴 | **A green `pytest --runslow` run.** CLAUDE.md: *"Any merge/release decision requires a green `--runslow` run — the everyday tier alone is not a gate."* I am forbidden from running it this round, so **this is unverified and it is the one true gate.** | **MUST RUN** |
| 🔴 | **Bump `core/version.py`** to `4.1.5-beta.4` **before** the gate, per the release process | not done — still `4.1.5-beta.3` |
| 🟡 | **H.2 item 1** — move the transport note below the calibration note | recommended before tagging; see below |
| 🟢 | Everyday tier | **green: 8250 passed, 262 skipped, 3 xfailed** — your 8240 plus the 10 tests added here. No regressions |
| 🟢 | The three shipped changes | all verified by running, all proven to fail against the parent |

**On the yellow one, precisely.** B.4 does **not** block the Windows diagnosis:
the file log records the transport on every route regardless
(`measure_bridge.py:891`), and §F's recipe — the actual ask — never reads the
on-screen note. What B.4 blocks is **claiming item 2 in the changelog**. A user
with a two-line log pane, told "ChromIQ now says which way it connected", will
look and see nothing. Ship the five-line move, or soften the release note.

### I.1 Left in the tree for you

* `docs/cr30_reports/55_transport_verify.md` — this report
* `tests/test_the_measure_log_names_the_transport.py` — 5 tests, run not read
* `tests/test_a_failed_bluetooth_open_leaves_a_trace.py` — 5 tests, run not read
* `scripts/drive_55_transport_note.py` — the on-screen driver, sandboxed, with
  its own modal-clicking timer so it never leaves a window waiting

No source outside `tests/` and `scripts/` was touched. The settings plist was
backed up and restored byte-identically (sha1 `33fd96c8…` before and after).
Nothing was written to `~/ChromIQ/CR30-Test`. The CR30 was never touched: no
serial port was opened and no Bluetooth connection was made at any point.

---

# J. Final check for `v4.1.5-beta.4`

Reviewing `d926b358` and `f11b9bc6`. Same constraints: no CR30, no serial port,
no Bluetooth connection. Plist backed up before the on-screen runs and restored
byte-identically after.

## J.1 B.4 — FIXED, re-verified on screen, four combinations

`tab_measure.py:7365-7389`: the white-calibration note is written first, the
transport note last, then `ensureCursorVisible()`. Since that call always leaves
the **last** line showing, the note survives any pane height.

Driven in the real app (`scripts/drive_55_transport_note.py`) at 1900×1400:

| `log_visible_lines` | transport | what the pane shows |
|---|---|---|
| **2** (the owner's own setting) | USB | `[NOTE] Connected to your CR30 over the USB cable.` ✅ |
| **2** | Bluetooth | `[NOTE] Connected to your CR30 over Bluetooth.` ✅ |
| **9** (shipped default) | USB | both notes, transport note last ✅ |
| **9** | Bluetooth | both notes, transport note last ✅ |

At two lines the pane now shows **only** the transport note — the single most
useful line, alone, in the smallest pane anyone runs. That is a better outcome
than the nine-line case.

### J.1.1 Residual — the tile-learning offer still writes after it

I removed the stub for `_offer_cr30_tile_learning` from the driver, because
stubbing it would have hidden exactly this. It appends up to six lines
(`tab_measure.py`, six `appendPlainText` calls) and it runs whenever
`reader.guard_is_armed` is False — which is **every session** until the user
teaches that unit its tile constant.

Driven with `guard_is_armed = False`, two-line pane:

```
magnet check stays on its built-in one. Nothing else is affected, and it will offer again.
```

The transport note is pushed off again.

**Not a blocker, and much smaller than what it replaced.** Before B.4 the note
was invisible on a short pane in **100 %** of sessions; now only when the guard
is unarmed *and* the pane is short. The file log records the transport on every
route regardless (`measure_bridge.py:891`), and the §F recipe — the actual
Windows ask — never reads the pane. Worth one line in a follow-up, not a reason
to hold a tag.

## J.2 The no-services line — correct, and placed where it matters

`bluetooth_report.py:118,145-168`. Run with a faked `BleakScanner.discover`
(no Bluetooth touched) against the case that matters — nothing offers `ffe0`,
two devices advertise nothing:

```
  (named device, hidden)     …:EE:00  rssi=-70  services=1
  (named device, hidden)     …:EE:01  rssi=-70  services=0
  (no name)                  …:EE:02  rssi=-70  services=0

⚠ 2 of those advertise NO services at all.
```

It appears **before** stage 2's early return, so it survives the
"NOTHING was advertising" path — which is the one a stuck user actually hits.
Your first placement would have missed it; the fix is right. The counter is
incremented only in the `else` branch, which is correct: an `ffe0` candidate has
services by definition.

## J.3 The serial caveat — correct, and it exposes one wording collision

`bluetooth_report.py:213-218` now says a silent match does not rule the
instrument out. That is exactly right and it closes G.2.

⚠ **One contradiction to fix, cheap.** In the same report the new ⚠ block says

> *"If your instrument is one of them, ChromIQ will not have looked at it —
> please send this report, because that is **a fault of ours**"*

and eight lines later stage 2 still says

> *"Your computer never saw a device offering the service ChromIQ looks for, so
> **the problem is before ChromIQ rather than inside it**."*

Both cannot be true, and the reader meets them in that order. The second
sentence predates the new finding. Suggested repair, no new claim:

> *"Your computer never saw a device offering the service ChromIQ looks for. If
> the note above says some devices advertised no services at all, one of them
> could still be your instrument — otherwise the problem is before ChromIQ
> rather than inside it."*

**Not a blocker.** It is a report a human reads and sends, not a decision the
app makes. But it should go in before it is pasted to a real person.

## J.4 The `ble.py` comment — repaired

`ble.py:81-87`. The dangling clause and unmatched parenthesis are gone and the
sentence reads through. Comment only, no behaviour.

## J.5 ⚠ THE RULING I WAS ASKED TO CHECK — `bleak` quietened. **It is safe.**

Three ways, all run.

**(a) The suppression actually reaches the logger that named the television.**
The tests added (`test_the_log_does_not_name_the_neighbours.py`) assert on the
parent logger `bleak`. The names came from a **child**,
`bleak.backends.corebluetooth.CentralManagerDelegate`, and a child only inherits
if it has no level of its own — so this had to be checked, not assumed:

```
child explicit level : 0 (NOTSET, inherits)
child effective level: WARNING
DEBUG enabled?   False
WARNING enabled? True
bleak loggers with an EXPLICIT level after importing bleak: {'bleak': 30}
after importing bleak, DEBUG still suppressed? True
```

The only explicit level is the WARNING we set. Importing bleak does not reset
it, and no backend module sets its own. **Inheritance holds.** Worth adding that
child logger name to the test so a future bleak release cannot break it quietly.

**(b) Nothing the diagnosis reads goes through a bleak logger.** All six phrases
in the §F pattern are written by `workflow.cr30.*` loggers
(`measure_bridge.py:851,863,891,697,774`; `ble.py:261`). None can come from
bleak.

**(c) End to end, with the ruling applied, on a real file.** A real
`RotatingFileHandler` at DEBUG in a temp directory, `_quiet_third_party()`
applied, a verbatim-shaped television line and a real bleak failure emitted, then
the real `_open()` failing both transports:

```
[WARNING] bleak.backends.corebluetooth.CentralManagerDelegate: Failed to connect to device: timeout
[INFO]    workflow.cr30.measure_bridge: CR30: no USB device (no CH34x serial device found); trying Bluetooth
[WARNING] workflow.cr30.measure_bridge: CR30: Bluetooth failed too (No CR30 found over Bluetooth); no instrument could be opened

neighbour named?      False   ✅
bleak FAILURE kept?   True    ✅
```

Then the §F grep over that file returned both ChromIQ lines. **The recipe still
answers the question.**

**Nothing needed was lost.** The Bluetooth report runs its own
`BleakScanner.discover` and formats the results itself
(`bluetooth_report.py:108-146`) — logger levels do not touch it. And the one
thing bleak says that a diagnosis would want, a connection failure, is at
WARNING and survives. The ruling improves the position: it removes the reason we
could never ask for the log at all.

## J.6 Translations — complete, budget restored

All twelve languages carry both new strings, and none is an English copy
(checked by comparing each value against its key). The untranslated budget is
back from 112 to 110, so C.3 is closed rather than papered over.

## J.7 Version, changelog, site

`core/version.py` → `4.1.5-beta.4`; `CHANGELOG.md` has the beta.4 section;
`docs/index.html:363` points at the beta.4 tag. The changelog does not claim
Bluetooth is fixed, which is right (J.9).

---

## J.8 THE RECIPE, FINAL FORM — paste-ready

Everything below is meant to be copied to a real person as-is. It works on a log
they already have; a beta-4 build only makes the failure case louder.

### J.8.1 Windows — ⚠ NOT RUN. There is no Windows machine and no PowerShell here.

Rewritten since §F.5 to be defensive about the two things I cannot test: a log
that does not exist, and an empty result. `@( … )` forces an array so `.Count`
is right for zero, one or many.

> Open **Windows PowerShell** from the Start menu, paste all of this in at once,
> and press Enter.
>
> ```powershell
> $logs = "$env:LOCALAPPDATA\ChromIQ\Logs\chromiq.log*"
> $out  = "$env:USERPROFILE\Desktop\cr30-transport.txt"
> $p = "trying Bluetooth|opened over|Bluetooth failed too|BLE: found in|did not answer as a CR30|remembered Bluetooth address"
> if (-not (Test-Path $logs)) {
>   "No ChromIQ log found at $logs"
> } else {
>   $hits = @(Select-String -Path $logs -Pattern $p -ErrorAction SilentlyContinue |
>             ForEach-Object { $_.Line } | Sort-Object)
>   Set-Content -Path $out -Value $hits
>   "Wrote $($hits.Count) line(s) to $out"
> }
> ```
>
> It writes **cr30-transport.txt** to your Desktop. Send us that file.
>
> **Please tell us the number it prints, even if it is 0** — and tell us if it
> says it found no log at all. Those are two different answers and both are
> useful. It is a short file and you can open it first; it contains only
> ChromIQ's own notes about your instrument. It deliberately does **not**
> include the rest of the log, because that would list the Bluetooth devices
> around you.

### J.8.2 macOS — RUN AND VERIFIED on this machine

```bash
grep -hE "trying Bluetooth|opened over|Bluetooth failed too|BLE: found in|did not answer as a CR30|remembered Bluetooth address" \
  ~/Library/Logs/ChromIQ/chromiq.log* | sort > ~/Desktop/cr30-transport.txt
wc -l < ~/Desktop/cr30-transport.txt
```

### J.8.3 Linux — same tested grep, path read from the source (no Linux machine here)

```bash
grep -hE "trying Bluetooth|opened over|Bluetooth failed too|BLE: found in|did not answer as a CR30|remembered Bluetooth address" \
  "${XDG_STATE_HOME:-$HOME/.local/state}"/ChromIQ/logs/chromiq.log* | sort > ~/Desktop/cr30-transport.txt
```

### J.8.4 Where the log lives (`core/platform_paths.py:122-131`)

| | |
|---|---|
| Windows | `%LOCALAPPDATA%\ChromIQ\Logs\chromiq.log` |
| macOS | `~/Library/Logs/ChromIQ/chromiq.log` |
| Linux | `$XDG_STATE_HOME/ChromIQ/logs/chromiq.log`, else `~/.local/state/ChromIQ/logs/` |

Six files, 5 MB each (`core/logger.py:54`). `chromiq.log` is the newest and
`chromiq.log.5` the oldest — which is why every command above ends in a sort.

### J.8.5 ⚠ Two things that must be said when asking

1. **Sort, or the story runs backwards.** `chromiq.log*` expands newest-file
   first. Verified: unsorted, the last line was 29 Aug; sorted, it is 30 Aug.
2. **An empty result is not proof that nothing happened.** It may only mean the
   log has rotated past it. Say so, or "no record" gets read as "no".

### J.8.6 The three outcomes

**(a) ChromIQ never tried Bluetooth** — cable opens, and no `trying Bluetooth`:

```
2026-08-20 10:00:01,000 [INFO] …: CR30: opened over usb
2026-08-21 09:15:44,000 [INFO] …: CR30: opened over usb
```

> ChromIQ was using the cable and never looked at Bluetooth. Whatever went
> wrong did not happen inside ChromIQ.

**(b) It tried and failed** — the beta-4 shape:

```
2026-08-25 21:03:11,000 [INFO]    …: CR30: no USB device (no CH34x serial device found); trying Bluetooth
2026-08-25 21:03:47,000 [WARNING] …: CR30: Bluetooth failed too (No CR30 found over Bluetooth …); no instrument could be opened
```

> It tried, and the reason is on the line. On a build older than beta 4 this
> shows as a `trying Bluetooth` line with **no** `opened over ble` after it —
> still an answer, just a quieter one.

**(c) It tried and it worked:**

```
2026-08-26 08:41:02,000 [INFO] …: CR30: no USB device …; trying Bluetooth
2026-08-26 08:41:04,000 [INFO] …: CR30 BLE: found in 15.42 s, connected in 2.33 s, notifications in 0.06 s
2026-08-26 08:41:06,000 [INFO] …: CR30: opened over ble
```

> Bluetooth works on that computer, and the timings say where the time went.

### J.8.7 The second ask, worth making at the same time

**Tools ▸ Instruments ▸ "CR30 Bluetooth report (for when it will not connect)"**,
then send the file it saves.

It answers what the log cannot: what his computer can *see* right now. Stage 1
lists every device with its service count, and beta 4 adds the ⚠ line that names
the most likely fault outright. Worth making **now** specifically because report
51 §1.1 found the tool would have died on Windows within half a second, and
`main_window.py:1813-1834` moved it off the GUI thread — so it should now
actually run there. **That is unverified on real Windows and should be said when
asking.**

---

## J.9 What beta 4 does and does NOT do for the Windows user

**Your reading is correct. Beta 4 is the instrument, not the fix.** Confirmed,
and here is the line to hold.

### It DOES

* record every Bluetooth **attempt** and its **outcome**, dated, in a file he
  already has — including for attempts made **before** beta 4 existed, because
  `trying Bluetooth` and `opened over …` have always been written;
* make a **failed** attempt say so, instead of existing only as a missing line;
* say **on screen** which way it connected, visibly, at any log-pane height;
* stop the log evicting its own evidence — 58.7 % of it was one help-icon line;
* stop the log listing his neighbours, which is what made asking for it
  impossible;
* in the Bluetooth report, **name the most likely fault outright** — devices
  advertising no services at all — and admit the serial match can silently miss.

### It does NOT

* fix Bluetooth on Windows. **No line of the discovery or connection path has
  been changed.** `ble.discover`, `_open_ble` and `_open` behave exactly as they
  did in beta 3;
* make ChromIQ attempt Bluetooth when the cable works. `auto` is unchanged:
  USB first, Bluetooth only in the `except`. If his cable works, ChromIQ still
  never tries Bluetooth, and **there is still no setting to ask it to**;
* find an instrument that advertises no service UUID. It now *tells* him that is
  possible; it does not act on it;
* prove the log-reach improvement. That is a prediction from a measurement, not
  a result — no machine has yet run beta 4 long enough to rotate.

### The sentence to send him

> This build does not fix Bluetooth — nothing about how ChromIQ connects has
> changed. What it does is let us find out what actually happened, which nobody
> can currently say. Would you run the two things below and send what they
> produce? Then we will know whether ChromIQ ever tried Bluetooth on your
> machine at all, and if it did, where it stopped.

Anything stronger would be the fifth time today that shipped text described
something that does not exist.

---

## J.10 Everyday tier — run here

```
8256 passed, 262 skipped, 3 xfailed in 92.39s
```

**Identical to your number.** That includes the 10 tests I added last round and
the 4 you added this round.

## J.11 Constraints — accounted for

* **The CR30 was never touched.** No serial port opened, no Bluetooth connection
  made, at any point in either round. Every device in every run was a stub;
  `BleakScanner.discover` was replaced with a fake for the report check.
* **Plist backed up and restored byte-identically** — sha1
  `33fd96c8864ffcea3945c9de589739a276846541` before and after. `log_visible_lines`
  back to 2, `custom_output_path` back to empty, verified by reading them through
  `AppSettings` after the restore.
* **Paths sandboxed** — `CHROMIQ_PRESETS_DIR` and the output path under the
  scratch directory for every on-screen run.
* **`~/ChromIQ/CR30-Test` untouched** — mtime 28 Aug 20:14, two days before this
  session.
* **No `--runslow`.** It remains the one gate I have not run and cannot.
* **No source edited outside `tests/` and `scripts/`.**

## J.12 Follow-ups — none of them blocking

| | Item | Size |
|---|---|---|
| 1 | **J.3** — stage 2 still says *"the problem is before ChromIQ"* eight lines after the new ⚠ block says *"that is a fault of ours"*. Suggested repair in J.3. Worth doing before it is pasted to a real person | one sentence |
| 2 | **J.1.1** — the tile-learning offer writes after the transport note, so a short pane loses it again while the magnet guard is unarmed | one line moved |
| 3 | **J.5** — add `bleak.backends.corebluetooth.CentralManagerDelegate` to `test_the_log_does_not_name_the_neighbours.py`, so a future bleak release cannot break inheritance quietly | one assert |
| 4 | **§C** — when the in-app log summary is eventually built, `("failed", "Bluetooth failed too")` must be in its needle list. The §F recipe does not depend on it | one tuple entry |

---

# VERDICT: 🟢 GREEN LIGHT to tag `v4.1.5-beta.4`

Subject to the two things only you can do: **bump is already done** (`4.1.5-beta.4`
is in `core/version.py`), and **`--runslow` must be green at the tag commit** —
CLAUDE.md makes that the gate and I am not permitted to run it. If it is red, this
verdict does not apply.

Everything asked for this round is in, and every claim in it was checked by
running rather than reading:

* **B.4 is fixed**, re-verified on screen on both transports at both pane
  heights. At two lines the pane now shows the transport note *alone*, which is
  the best outcome available.
* **The no-services line** is correct and, after your fix, appears in the
  early-return case that matters.
* **The serial caveat** closes G.2.
* **The `bleak` ruling is safe** — proven three ways, including that the
  suppression reaches the *child* logger that actually named the television, and
  that the §F recipe still returns both ChromIQ lines end to end on a real file
  with the ruling applied. Nothing needed was lost; bleak's connection failures
  survive at WARNING, and the report does its own scanning.
* **Translations complete**, budget back to 110, so C.3 is closed rather than
  deferred.
* **8256 / 262 / 3**, matching your run.

The four follow-ups in J.12 are all one-liners and none of them affects what
beta 4 is for.

**One thing to hold to when you write to him** (J.9): beta 4 does not fix
Bluetooth and changes no line of the discovery or connection path. It is the
instrument that will find the fault. Say that, send the two asks in J.8, and the
next round starts from evidence instead of from two people's memory.
