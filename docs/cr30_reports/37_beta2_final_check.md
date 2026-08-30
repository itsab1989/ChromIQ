# 37 — Beta 2 final check ([CR30-B5])

**Status: IN PROGRESS — sections are appended as they are confirmed.**
Started 2026-08-30. Scope: everything in `v4.1.5-beta.1..HEAD` plus the
uncommitted tree, with four named attack targets:

1. DTR/RTS at port open (`workflow/cr30/transport.py::open`) — highest risk
2. `CR30.open_usb()` identify-before-trust + `DeviceReader._open_usb` memory
3. The tile analysis (backlog B2-10) — can a patch impersonate the tile?
4. The shutdown fix (`core/argyll_runner.py::cleanup`)

Also: chart-names-no-instrument note, magnet-test segfault rule,
B2-7/8/9 blocking ranking, CHANGELOG truth, one gate run at the end.

Verdict placeholder: **NOT YET GIVEN.**

---
## 1 · The DTR/RTS change (`SerialTransport.open`) — SOUND, one claim overstated

**Method note:** the pyserial actually installed in `.venv` (all three platform
backends ship in the package) was read directly — not remembered, not the docs.

**Does setting `dtr`/`rts` before `open()` take effect on win32/posix? YES, on
both — verified from the installed source:**
- `serialutil.py`: the `dtr`/`rts` setters on a CLOSED port store
  `_dtr_state`/`_rts_state` and touch nothing else — so the pattern is legal
  and the state survives into `open()`.
- **posix** (`serialposix.py:311`): `os.open()` → `_reconfigure_port` → then
  `if not self._dsrdtr: self._update_dtr_state()` (and the same for RTS), which
  issues `TIOCMBIC` when the state is False. So the lines are actively
  **cleared** right after the OS open. The old code (defaults True) actively
  **raised** them at the same point — the fix genuinely changes the wire.
- **win32** (`serialwin32.py`): `CreateFile` → `_reconfigure_port()` sets
  `comDCB.fDtrControl = DTR_CONTROL_DISABLE` / `fRtsControl =
  RTS_CONTROL_DISABLE` when the states are False. Takes effect there too.

**What is overstated:** the docstring's "Holding both LOW before the port is
opened is the form that CANNOT reset a board." Not quite:
- On **Linux**, pyserial's clear happens *after* `os.open()`. The kernel's
  tty open path (`tty_port_block_til_ready`, O_NONBLOCK branch) raises
  DTR/RTS itself when the termios baud is nonzero, before userspace can act,
  and the ch341 driver implements `dtr_rts`. So a **brief DTR pulse at open
  remains possible** on Linux (and plausibly macOS; on Windows it depends on
  what the CH341SER driver does between CreateFile and SetCommState). A pulse
  through a 100 nF auto-reset cap can still reset an Arduino-style board.
- The fix is therefore **strictly better, not absolute**: before, DTR/RTS were
  raised AND HELD for the whole session on every platform; now at worst a
  millisecond-scale driver-side pulse remains on some stacks. The commit's
  framing ("cannot reset") should be softened to "no longer asserts", or the
  residual named the way the AA-0A residual already is.
- Also: `ser.dtr` READS BACK pyserial's cached `_dtr_state`, not the wire —
  so "ChromIQ's own open reported dtr True, rts True" measured pyserial's
  bookkeeping, not the hardware. The conclusion was still right (posix
  `_update_dtr_state` provably drove TIOCMBIS with the old defaults), but the
  sentence claims a wire measurement that was not made.

**Can the CR30 fail to answer with the lines low on another stack?** The risk
is real but bounded, and I could not fault the change with it:
- The device's own transport facts argue the lines are unused: baud, parity
  and stop bits are all ignored and replies outrun the nominal line rate
  (EXP-USB-005) — there is no UART in the path; the "CH340" is a CH554
  emulation whose handling of modem-line requests is firmware-defined and was
  measured indifferent (identify OK, lines low, V11.3).
- That measurement is ONE unit, ONE firmware, macOS. A CDC-style firmware that
  gates TX on DTR (common in Arduino-CDC land) would go dark with DTR low —
  on such a unit ChromIQ would report "none of them answered as a CR30". The
  mitigating design already exists: the error names every port tried. A cheap
  belt-and-braces for beta 3 (not beta 2): if NO candidate answers, retry the
  remembered/only port once with DTR asserted — reintroducing the pulse only
  on a path that would otherwise end in "no instrument".
- Windows CH341SER / Linux ch341 remain untested on hardware, as the batch
  owner already says. Nothing I can read makes them *worse* than beta 1: under
  beta 1 the lines were raised on every open; a unit that NEEDED them raised
  would have worked then and could fail now — but no evidence anywhere in the
  corpus suggests such a unit exists, and the sibling harm (resetting real
  users' printers, proven mechanism) outweighs the hypothetical.

**Verdict: does not block.** Change the "cannot reset" wording (docstring +
report 36/backlog phrasing) before it hardens into a spec claim.

## 2 · `open_usb` identify-before-trust + the remembered port — one REAL gap, two defects

**The real gap — `is_cr30()` is called by NOBODY.** `CR30.identify()` (USB
branch) runs `Session.identify()`, stores `ident.model`, returns. It raises on
silence, framing, checksum and sub-command mismatch — but **not on a wrong
model string**. `grep is_cr30()` over `workflow/` and `ui/`: zero callers (the
`ti2_loader` hits are the chart keyword). So the comment in `open_usb` —
"`identify()` raises unless this really is a CR30" — and the docstring's "a
port that does not say `CR30` is closed and left alone" are **not what the code
does**: any device that answers the four identity frames well-formed is
accepted, whatever it calls itself. Realistically that is a CR10/CR20 sibling
(B2-7's USB half) or the vendor's other instruments; an Arduino stays silent
and is refused, so the headline hazard IS fixed. But report 36's line "On USB
the model-string check would refuse a CR10/CR20" is **wrong for the shipped
code** — the check exists and is wired to nothing, which is the exact
Exception-1 shape report 36 itself diagnosed, one level up.
Fix is two lines in `open_usb`'s loop (`if not ident.is_cr30(): raise`), plus
the same in the bridge's remembered-port branch. The new test file cannot see
this: its fake `identify` *raises* for the impostor — a silent device — and
never simulates a protocol-speaking one with the wrong name.

**Defect A — the remembered-port branch leaks an open port.** In
`DeviceReader._open_usb`, when `CR30.open_usb(remembered)` succeeds but
`dev.identify()` raises, nothing closes `dev`: the local stays bound through
the `except` and the fallback `CR30.open_usb(...)` search runs **while the
stale port is still open**. On POSIX a second open of the same tty succeeds, so
it self-heals; on **Windows** `CreateFile` is exclusive (share mode 0), so the
full search gets `PermissionError` on that port. If the remembered port was a
transient-failing real CR30, the user loses the instrument for that attempt
with a misleading error. One-line fix: close `dev` in the except.

**Defect B — an explicitly chosen port that fails identify is used anyway,
after a lying log line.** With `self._port` set, `_open_usb` treats it as
"remembered", identifies it, and on failure logs "did not answer as a CR30;
looking at the other serial devices" — then calls `CR30.open_usb(self._port)`,
which (explicit-port contract) opens THE SAME port with no question and returns
it. Honouring the caller's port is the documented design; the wasted probe and
the false "looking at the other serial devices" are not. Cosmetic-to-minor.

**What I could NOT fault:**
- **Hang/timeout:** a candidate that opens and never replies costs ~1 s
  (DEFAULT_TIMEOUT_S per first identity frame, `_read` deadline loop) and is
  then closed — no hang, bounded per candidate.
- **Ports closed on refusal:** `open_usb`'s loop closes `t` in its except; the
  all-refused error names every port and the likely cause. Good.
- **Ordering / two CH340s:** enumeration order, remembered port first via the
  bridge — the common case (one CR30, one other board, CR30 remembered) sends
  the identify frame to exactly one device, which is the promised mitigation
  working. First run (nothing remembered) probes in enumeration order and may
  identify the stranger first; that is the accepted residual, stated honestly.
- **No CH340:** immediate `ConnectionError("no CH34x serial device found")`.
- **Is `identify()` safe to send blind?** Four 60-byte `AA 0A` frames. The
  Marlin/GRBL inertness analysis (report 36) covers the same frame class, and
  the vendor's own software sends the identical frame — this is as safe as
  serial probing gets, and the alternative (ask the user per port) trades a
  silent hazard for a nagging dialog on every measurement. With the
  remembered-port mitigation the steady state is one probe to the right
  device. **Asking first is not warranted; the residual is correctly stated.**
- The settings read/write for the remembered port is wrapped and non-fatal;
  the key is app-wide like `cr30_ble_address`, consistent with beta 1.

**Verdict: does not block**, but wire `is_cr30()` in (2 lines) and close the
leaked port (1 line) BEFORE tagging if any code change is still allowed —
both are exactly the kind of thing beta 2 claims to have fixed, half-fixed.

## 3 · The magnet-test settle rule — INCOMPLETE, one instance remains

The harness docstring now says "ANY TEST THAT RESUMES THIS BRIDGE MUST CALL
`h.settle()` BEFORE IT ENDS". Audit of every resume site in `tests/`:
- `test_cr30_magnet_stops_the_session.py:100` — resumes, settles at :102. ✔
- remedy file: the three fixed tests settle; the `_calibrate_and_confirm`
  pair start no reader (no resume, `_cr30_reader is None`); the stop/keep
  tests end with `_stopped True`. ✔
- **`test_a_real_resume_still_reports_success` (same file, bottom) calls
  `h.bridge.resume_after_magnet()` → `rearm()` → `_start_read` — a real
  reader thread — and never settles.** The rule is broken two screens below
  the warning that states it. Same intermittent-segfault class the commit
  says it fixed; "five consecutive clean runs" is exactly the evidence the
  commit itself calls the worst way to fail.

One-line fix (`h.settle()` before the asserts end). **Should be fixed before
tagging** — not because the product is wrong, but because the gate's
reliability is the release instrument and this is a known, named defect class
left half-closed.
## 4 · The shutdown fix (`argyll_runner.py::cleanup`, UNCOMMITTED) — mechanism right, **"nothing is lost" is WRONG**

**What I could not fault:**
- The mechanism analysis is correct and I re-verified every link: `cleanup()`
  has exactly ONE caller, `MainWindow.closeEvent:2455`, and `closeEvent` never
  ignores/cancels the event — so the callback-drop can only ever run on a real
  quit. `_on_finished` calls `_run_on_finish` directly (argyll_runner.py:977),
  so disconnecting the public `finished` signal never was the path; the fix
  disconnects `self._process.finished → _on_finished` and drops the callbacks
  BEFORE `kill()`, which is the only order that works (`waitForFinished`
  delivers synchronously). Chained runs are untouched (`_on_finished` still
  captures-then-calls). The PTY path was already covered by `_pty_done`.
- **The autosave claim is TRUE, verified in source, not accepted:**
  `native/chartread_helper/chromiq_chartread.c` calls `cq_write_ti3_atomic()`
  immediately after every accepted value on the external-values path
  (line ~3178, "autosave per patch") and at six other accept sites. SIGKILL at
  quit loses at most the in-flight patch.
- The latent orphan-relaunch (`_engine_should_fall_back(9)` → `_launch_stock`
  during shutdown) is real in the code and the fix removes it.

**What the fix's own comment gets wrong — "Nothing is lost by dropping them."**
Readings, no. **File reconciliation, yes.** The per-run callback chain at quit
was: manager `_on_finish(9)` → (CR30 branch) → `TabMeasure._on_measure_done`
→ `_finish_session_guard()` (§3b/M-TI3-EMPTY: set an empty `.ti3` aside,
restore the pre-session copy) and `_archive_empty_measurement()` /
`_restore_displaced_measurement()` (Knut's #130 remedy: an old measurement
MOVED to `old/` at Start comes back when the session read nothing). B2-1's own
log analysis records this running at quit — "the session ending cleanly and
his measurement being restored" — and calls the outcome CORRECT ("Nothing is
broken"). The uncommitted fix silences the warning by also silencing the
remedy.

**Concrete regression** (vs beta 1): replace an existing measurement, read
zero patches, quit the app. Before: empty file set aside, previous measurement
restored, run state honest. After: the empty `.ti3` stays in place claiming
the run is measured (resume acts on it, the overlay warns — the exact
symptoms Knut's rule exists to prevent), and the real measurement sits
un-restored in `old/<timestamp>/`. **Nothing is deleted** — Start MOVED it
there with a log line saying so, and the §2a guard COPIES too — so this is
confusion, not data loss. But it removes spec'd behaviour (§3b, M-TI3-EMPTY)
on one ending path, and Knut's wording was "right after measurement session
was exited/stopped/completed" — quitting is an exit.

**Also lost at quit, previously present:** the same handler's modal windows
("Nothing was measured…") used to `exec()` DURING shutdown — which was itself
wrong. The right shape is the fix as written PLUS a silent, headless
reconcile from `closeEvent` after `cleanup()`: run `guard.finish()` and the
displaced-restore with every dialog suppressed. File truth preserved, no
shutdown modals, warning and orphan both still gone.

**Verdict: NOT tag-ready as it stands.** Either (a) add the silent quit-time
reconcile, or (b) leave this change OUT of beta 2 (it is uncommitted; the
warning it removes is documented noise — B2-1: "Nothing is broken") and land
the complete version in beta 3. Shipping it as-is trades a cosmetic warning
for a real, spec-relevant behaviour regression, and that trade is the wrong
direction for a "final check" beta.
## 5 · The tile analysis (B2-10) — conclusion SAFE, one supporting claim WRONG, one overstated

**Recomputed independently** (scratchpad/tile_check.py — my own extractor over
`captures/public`, 155 spectra found where B2-10 counted 103; different dedup,
same corpus):
- `looks_like_calibration_tile` compares exactly as B2-10 assumed: length-
  checked 31 bands, absolute per-band difference, tol 0.05, `all()`. ✔
- Everything inside the guard is worst-band delta **0.0000** — the bit-exact
  stored signature — and every one comes from the magnet/trigger-calibration
  experiments (EXP-MEAS-002/003, EXP-BLE-015, EXP-MEAS-004). ✔
- Closest genuine reading: **4.6857 %R** worst-band — reproduces B2-10's 4.686
  to the digit, and it IS the other unit's white reference (PRIORART-002),
  exactly as the ⚠ footnote says. On the owner's OWN unit the closest genuine
  reading is **11.33 %R** away — stronger than reported. ✔

**The WRONG claim — the noise argument.** B2-10: "Two readings of the same
real surface on his own unit differ by 1.41–6.38 %R on their worst band — his
own measurement noise is 28x to 128x the tolerance. So even measuring the
actual white tile WITHOUT a magnet cannot match: noise alone pushes it out."
The corpus says otherwise: adjacent same-surface repeat pairs on his unit span
**0.035–2.71 %R** worst-band — including pairs BELOW the 0.05 tolerance — and
the code's own `identical_to` docstring records **0.056 %R worst-band SD**
(EXP-MEAS-001). Noise alone does NOT push a reading out of a 0.05 window.
The 1.41–6.38 figure was presumably computed across recalibrations or between
different surfaces (drift, not repeat noise). This is the round's "another
wrong claim".

**Why the conclusion still holds — the argument that should replace it:**
a genuine reading is RATIOED against the white reference; measuring the tile
itself after calibration reads ~100 %R, not the stored ~79 %R curve. To match
the signature a printed patch would need the ceramic tile's absolute spectral
curve within 0.05 %R on all 31 bands simultaneously — with per-band SD
~0.056 the all-31 probability is ~1e-6 per reading even for a physically
perfect spectral twin, and no printed patch is one. So: **no false positive in
practice** — but "At 0.05 it cannot be reached" is an overstatement;
"astronomically unlikely, and never observed in 155 corpus readings" is the
honest sentence.

**Safe to write into a specification?** The margin facts (closest genuine
4.69 %R = other unit's white ref; own unit ≥11 %R; only gated frames match)
— yes, with `Confirmed by` rules observed. The noise sentence — no, it is
wrong as written and must not be the spec's justification.
## ⚠ Mid-review event

The work reviewed in §4 as "uncommitted" was committed as **`c508fec5`**
("quitting ran the measurement's finish handler, and USB now remembers")
while this review ran. Every §2 and §4 finding therefore applies to **HEAD**,
and §4's option (b) ("leave it out of beta 2") now means a partial revert or —
better — the amendment in §4.

## 6 · The chart-names-no-instrument note (`1bfaffec`) — claim TRUE, one wrong-moment firing

- **The Argyll claim is verified at source**, not from the log line:
  `Argyll_V3.5.0_orig/spectro/chartread.c:2898` — `itype = instI1Pro;
  /* Default chart target instrument */` when `TARGET_INSTRUMENT` is absent,
  printed by the "chart is for %s" warning at :526. The note's wording ("its
  own assumption when a chart is silent, not something written in your file")
  is exactly right.
- **Right moments, mostly:** the note lives in `_refresh_bidir_autodetect`'s
  announcement block, called on chart load, chart clear, and after an
  instrument-name repair — same place the positive "Chart instrument: X"
  line always lived, replacing the previous line each time. B2-2a and B2-2b
  both closed in one message. ✔
- **The wrong moment:** `instr` stays `None` not only for a chart that names
  nobody but also when **no chart is loaded at all** (`_ti1_path is None` —
  and the caller at tab_measure.py:3859 is precisely the clear-chart path,
  which nulls the session and clears the preview) and when a `.ti1` has **no
  `.ti2` sibling** (the chart's instrument is unreadable, not absent). In both
  cases the log now claims "this chart does not name one" about a chart that
  is not there / was never read. Found by reading, not driven. Fix: make the
  `else` an `elif self._ti1_path is not None and chart.exists():`. Cosmetic —
  a log line — and exactly the fault class the commit itself fixes, so it
  should not survive into beta 3.

## 7 · B2-7 / B2-8 / B2-9 — does any of them block beta 2?

**None strictly blocks — all three predate beta 1 and beta 2 makes none of
them worse. Ranked:**

1. **B2-8** (BLE `open()` falls back to unconfirmed `ffe0` devices) — the
   strongest case for inclusion anyway: beta 2's entire theme is "do not
   greenlight unidentified devices", and this is the same fault left standing
   on the other transport, fixable by deleting the `or cands` fallback and
   saying "N ffe0 devices seen, none answered as a CR30". Shipping the theme
   half-done is coherent only if the backlog says so out loud (it does, B2-8).
   Not blocking; first in line for beta 3.
2. **B2-7** (axis cannot tell a CR30 from a CR10/CR20) — DOWNGRADED as an
   asymmetry claim by §2's finding: USB does not check the model string
   either, so today NEITHER transport distinguishes the siblings. Wiring
   `is_cr30()` (§2) restores the USB half cheaply. The BLE half genuinely
   cannot be fixed without vendor input — the manufacturer email already asks.
   Not blocking: a sibling either speaks the protocol (and likely works) or
   fails the axis check safely.
3. **B2-9** (no BLE magnet protection on any other unit) — the "it must be
   SAID" duty is already met where it matters most: the beta-1 changelog
   states it plainly ("Over Bluetooth … the first such reading may not be
   caught. Use USB if you have the cable."), and the code comments carry it.
   Nothing to do for beta 2 beyond keeping that sentence.

## 8 · CHANGELOG and version — outstanding tag work, nothing untrue

- `core/version.py` still reads `4.1.5-beta.1` and CHANGELOG.md has **no
  beta-2 entry**. Both precede the gate per the release process.
- The beta-1 entry stays true after these changes — checked line by line. In
  particular "we would like ChromIQ to tell those two apart itself, and it
  does not yet" (driver-missing vs not-found) remains true; the new
  all-refused error only helps the case where a CH340 answers.
- The beta-2 entry should carry: the quit-warning fix (with whatever §4
  resolution is chosen), the CH340 identify + DTR/RTS safety (worded per §1 —
  "no longer asserts", not "cannot reset"), the remembered USB port, and the
  no-instrument chart note.
## 9 · The gate

Run once, alone, at the end, nothing else touching the tree:
`QT_QPA_PLATFORM=offscreen pytest --runslow -n auto` →
**8238 passed, 141 skipped, 3 xfailed, 1 warning in 170.61 s (2:50)**.
The warning is a `PytestUnraisableExceptionWarning` for a `BrokenPipeError`
inside `_pytest/fixtures.py::finish` at teardown — xdist worker-pipe noise,
no test failed. Note the green gate includes the §3 settle-hole test: it
usually wins its race, which is why "five consecutive clean runs" proves
nothing there.

## VERDICT

**1 · Does anything block tagging 4.1.5-beta.2? YES — one thing, and it is
cheap to clear.**

1. **BLOCKS: the quit-time reconciliation regression in `c508fec5`** (§4).
   Dropping the per-run callbacks at quit also drops §3b / M-TI3-EMPTY:
   an empty `.ti3` left claiming to be a measurement, the replaced
   measurement left un-restored in `old/` — behaviour B2-1 itself documented
   as correct at quit, and behaviour Knut specified ("right after measurement
   session was exited/stopped/completed"). Under the binding-specs rule this
   is a spec-contradicting change that has had no review or approval. Clear
   it by ANY of: (a) a silent, dialog-free reconcile from `closeEvent` after
   `cleanup()`; (b) reverting the `argyll_runner.py` half of `c508fec5` and
   landing the complete fix in beta 3 (the warning it removes is documented
   noise); (c) the owner explicitly accepting the corner-case regression in
   writing, recorded in the backlog and the spec discrepancy list. Any of the
   three lifts my no.
2. **Fix-before-tag, not formally blocking (all three are one-to-two lines,
   in the areas beta 2 claims to have fixed):** the `h.settle()` hole in
   `test_a_real_resume_still_reports_success` (§3 — gate reliability);
   wiring `Identity.is_cr30()` into `open_usb` and the bridge (§2 — makes
   the shipped docstrings true); closing the leaked port in
   `DeviceReader._open_usb`'s remembered branch (§2 — Windows-only failure).
3. **Not blocking:** the no-chart wrong-moment log line (§6); the "cannot
   reset" wording (§1); B2-8 → first for beta 3, B2-7 downgraded, B2-9
   already stated where it matters (§7).
4. **Mechanical anyway:** version bump + beta-2 CHANGELOG entry, then the
   gate re-run per the release process (the numbers above were measured at
   version beta.1).

**2 · Overstated or wrong claims in the backlog/batch — four found:**
- B2-10's noise argument: "repeat readings differ by 1.41–6.38 %R (28x–128x
  the tolerance); noise alone pushes even the tile out". Corpus says
  0.035–2.71 %R adjacent-repeat worst-band, including BELOW the 0.05
  tolerance; the code's own recorded SD is 0.056 %R. The conclusion survives
  on the margin argument only (§5).
- "`identify()` raises unless this really is a CR30" (code comment), "a port
  that does not say CR30 is closed and left alone" (docstring), and report
  36's "on USB the model-string check would refuse a CR10/CR20" — all wrong:
  `is_cr30()` has zero callers; the USB gate is "speaks the protocol", not
  "says CR30" (§2).
- "Holding both LOW before the port is opened … cannot reset a board" — on
  posix the kernel can pulse DTR between `os.open()` and pyserial's clear;
  and the "measured dtr True, rts True" read pyserial's cached state, not
  the wire (§1). The change is still strictly better than beta 1.
- `cleanup()`'s "Nothing is lost by dropping them" — readings no,
  reconciliation yes (§4).

**3 · What I could NOT fault** — said plainly, because a review that only
finds problems is not a review: the DTR/RTS pattern is legal and effective on
all three pyserial backends (read from the installed source, §1); the
per-patch autosave claim is true in the helper's C source (§4); the cleanup
mechanism analysis — the direct-callback path, the synchronous
`waitForFinished` delivery, the single caller, the orphan-relaunch hazard —
is exactly right (§4); B2-10's margin numbers reproduce to the digit from an
independent extractor, and only gated frames sit inside the guard (§5); the
Argyll i1 Pro default is real at `chartread.c:2898` (§6); `open_usb`'s
probing is bounded, closes refused ports, and its all-refused error is the
most helpful text in the batch (§2); and the gate is green at full strength.

**Status: COMPLETE.**
