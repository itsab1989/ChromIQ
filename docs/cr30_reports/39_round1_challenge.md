# 39 — Round-1 challenge of the beta-2 plan ([CR30-R1])

**Status: COMPLETE.**
Started 2026-08-30. Target: the plan ranking B2-8 > B2-9 > B2-7 > B2-3,
the "none blocks beta 2" judgement, and the already-committed
`v4.1.5-beta.1..HEAD` work (especially the DTR change and `408f25d7`).

Verdict: **one blocker found (F1, not on the plan's list); ranking confirmed; see VERDICT.**

---
## F1 · BLOCKER — the quit fix in `408f25d7` is INERT: `closeEvent` never finds the manager

`ui/main_window.py:2460-2467` looks the manager up as

```python
for _mgr in (getattr(getattr(self, "tab_measure", None), "_manager", None),
             getattr(self, "_measure_manager", None)):
```

but MainWindow's attribute is **`self._tab_measure`** (`ui/main_window.py:239`);
`self.tab_measure` is assigned NOWHERE (`grep -c "self\.tab_measure\b"` = 0) and
`_measure_manager` occurs exactly once in the file — inside this getattr itself.
Both candidates are therefore `None`, `note` is never callable, and
**`note_app_quitting()` is never called**.

**Proven dynamically, not just by grep** — a real `MainWindow` built offscreen
under the test suite's own settings sandbox
(`scratchpad/prove_quit_fix_inert.py`):

```
candidate 1 (tab_measure._manager): None
candidate 2 (_measure_manager):     None
note_app_quitting would be called: False
real manager at w._tab_measure._manager: MeasureManager   (has note_app_quitting)
```

Consequences at HEAD:
- The owner's warning — the very report that opened B2-1 — **still prints on
  every quit** with a CR30 session live. He will see it in his terminal the
  first evening.
- The **latent orphan-relaunch is still live too**: with `_user_quit` False at
  quit, `_engine_should_fall_back(9)` (`measure_manager.py:639-642`) returns
  True for a session quit before its first event (`_engine_saw_event` False),
  so stock chartread is still relaunched into the closing app — the exact
  hazard `c508fec5`/`408f25d7` claim fixed.

**Why the gate is green anyway:** `tests/test_quitting_does_not_run_the_session_finish.py`
checks only `inspect.getsource` — that the string `note_app_quitting` appears in
`closeEvent` before `_runner.cleanup()`. It never RUNS the lookup against a real
window. The dropped condition is the real MainWindow's attribute namespace, and
the dropped condition is the thing under test — the same shape as the four
probes this week, and as `is_cr30()`-with-zero-callers one commit earlier.

**Fix (one line):** `getattr(getattr(self, "_tab_measure", None), "_manager", None)`
— plus a test that constructs the real window (any of the existing
`MainWindow(s)` fixtures) and asserts `_user_quit` flips when the closeEvent
loop runs. A source-text assertion cannot hold this door.

## F2 · B2-8 — the plan is RIGHT to rank it first, and it is WORSE than the backlog says

All read from code at `408f25d7`; nothing sent to any device.

**Three compounding facts the backlog entry does not carry:**

1. **A fallback misfire is PERSISTED.** `BleTransport._open` sets
   `self.address = target` before connecting (`ble.py:205`), and
   `DeviceReader._open_ble` calls `_remember_address(dev)` on ANY successful
   open (`measure_bridge.py:668-670`) — including one that fell back to an
   unconfirmed `ffe0` gadget. Every later session then takes the
   remembered-address branch, which performs **no confirmation of any kind**,
   straight to the gadget. One bad scan becomes a sticky misidentification
   that survives restarts, until the gadget stops answering.
2. **The connection is not the harm — what follows it is.** The first BLE open
   of a session happens when the user presses Calibrate
   (`measure_bridge.py:836-838`: `_open()` then `self._dev.calibrate(...)`),
   so the very next frames written to the unconfirmed device are the white/
   black **calibration commands** (`device.py:335`, `ble.frame(cmd, 0x01)`),
   then poll bytes. An HM-10-class module pipes every byte into whatever MCU
   sits behind it. This is the CH340 harm — writing commands into a stranger's
   device — not a mere wrong label.
3. **BLE has no second gate behind `open()`.** USB re-identifies its remembered
   port before accepting it (`measure_bridge.py:719-723`); the BLE
   remembered-address branch never identifies, and nothing in the session ever
   calls `CR30.identify()` on a BLE device (zero callers). `open()`'s
   confirmation is the ONLY identity check the Bluetooth path has, and the
   `or cands` fallback waives it.

**Does the fallback protect a REAL case? Mostly no — one narrow yes.**
- A CR30 held by a phone app **stops advertising** (the error text at
  `ble.py:195-199` says so from measurement), so it never reaches the
  shortlist; the fallback cannot help it. Same for a sleeping unit: nothing
  advertises, `cands` is empty, the fallback is moot.
- A **freshly-calibrated CR30 (zero-filled slot) still confirms**: the
  zero-filled reply carries a valid header and axis — that is how
  `measure_bridge.calibrate`'s read-back parses it (`_parse_reply` builds the
  wavelengths from the SAME reply's axis, `device.py:47-52`), so
  `discover`'s axis check (`ble.py:131-135`) still sees 400/10/31.
- The one real case: a **transient connect/notify failure during the confirm
  pass** (`ble.py:136-137` stores `entry["error"]` and leaves
  `confirmed=False`). BLE connects do fail sporadically; today the fallback
  quietly retries by connecting anyway. Deleting `or cands` without replacing
  that would turn a one-off radio hiccup into "no CR30 found".

**The middle course, grounded in the code rather than a dialog:** prefer
confirmed candidates; for candidates that FAILED WITH AN ERROR (as opposed to
answering with a wrong axis), retry confirmation once; if still nothing
confirmed, refuse with a message that separates "N ffe0 devices seen, none
answered as a CR30" from "nothing seen at all" (the existing text). Do NOT add
a user chooser: `discover_ble` has zero UI callers today, and a user's answer
about an unlabelled BLE gadget is the seeded-widget trap again.

**Adjacent latent hole, same family:** `CR30.identify()`'s BLE branch
(`device.py:195-206`) never compares the parsed axis to `EXPECTED_AXIS` — it
sets `model = "CR30"` for any reply containing `MEASUREMENT_HDR`. Since
`MEASUREMENT_HDR` is the first four bytes of our OWN command
(`bb 02 10 00`), a BLE-UART gadget that ECHOES its input passes `identify()`.
It has no callers today; it is exactly the building block the next fix will
reach for, so wire the axis check in when touching this file. (`discover`
itself survives an echo: the echoed frame's bytes 4..7 parse as axis (0,0,0),
which fails `EXPECTED_AXIS`.)

## F3 · B2-9 — "say it" is NOT all that is available; the plan skips its own report's mitigation

`38_learning_the_tile.md` §6 alternative 3 already names a **unit-independent,
learn-free behavioural mitigation**: a rolling bit-identity window — refuse a
reading bit-identical to any recent one, because genuine CR30 readings are
never bit-identical (0 identical pairs in the corpus; gated ones always are).
It misses only the first gated reading of a run, needs no other units, and the
same report calls it "cheap, safe, and worth doing regardless". The plan's
"not fixable without other units" is true only of the FULL fix. Also cheap:
the once-per-session disclosure for a unit with no signature (38 §4), and a
"prefer USB for chart reads" line where the Bluetooth path is documented. The
changelog sentence beta 1 already ships ("Use USB if you have the cable") is
the right disclosure and stays true. Verdict: documentation for beta 2 is
fine; alternative 3 + the disclosure belong on the beta-3 list by name, not
"said" and stopped.

## F4 · B2-7 — half of the plan's premise is now stale, in the good direction

At HEAD the USB path DOES tell a CR30 from a sibling: `Identity.is_cr30()`
(`identity.py:78`, `model.upper() == "CR30"`) is wired at both call sites
(`device.py:155-158`, `measure_bridge.py:720-723`). So "the axis cannot tell
a CR30 from a CR10/CR20" is now a **BLE-only** statement. Two consequences the
plan should carry: (1) a CR10/CR20 that speaks the protocol would be accepted
over Bluetooth and refused over USB — an asymmetry users could actually hit,
worth one sentence wherever B2-7 is documented; (2) if the manufacturer
answers that siblings identify as e.g. "CR20", USB support for them is a
string away — but a hypothetical CR30 VARIANT whose model string is not
exactly "CR30" (a "CR30S") would now be refused on USB; nobody has seen one,
and the all-refused error names what answered, so this is acceptable and
diagnosable. Documentation-only for beta 2: agreed.

## F5 · B2-3 — verified, and the deferral is right

Both quotes lack the `(-r)`: `ui/tabs/tab_profile.py:4045-4050` and
`ui/tabs/tab_chart.py:10699-10704` (read at HEAD). The widget reads
"…existing measurement (-r)". Outside CR30 files; the owner asked to be told
before other areas are edited — deferring with his sign-off is correct.

## F6 · Already-committed beta-2 work — the rest of the audit

- **DTR/RTS (`7aeb9776`)**: report 37 §1's analysis holds; nothing new found.
  But its required wording change did NOT land: `transport.py::open` still
  says "Holding both LOW before the port is opened is the form that cannot
  reset a board" and still cites the `dtr True, rts True` read-back as a
  measurement (it read pyserial's cached `_dtr_state`, not the wire — 37 §1).
  `408f25d7` said the review was "right on all four counts" yet shipped this
  count unchanged. Fix the docstring before it is quoted into a spec.
- **`c508fec5` USB port memory**: the two defects report 37 found are
  genuinely fixed at HEAD — `is_cr30` checked and the refused port closed in
  the remembered branch (`measure_bridge.py:711-737`). Report 37's Defect B
  (an explicitly-chosen port that fails identify is reopened anyway after a
  "looking at the other serial devices" log line, `measure_bridge.py:736-738`)
  is still present; cosmetic, carry it on the list.
- **`1bfaffec` chart note**: report 37 §6's wrong-moment firing is still at
  HEAD — `_refresh_bidir_autodetect`'s `else` (`tab_measure.py:3918-3939`)
  logs "this chart does not name one" when NO chart is loaded
  (`_ti1_path is None`; the caller at :3859 is the clear-chart path) and when
  the `.ti2` sibling is missing (unreadable ≠ absent). Cosmetic; already on
  the beta-3 pile; saying so here so it is not lost between reports.

---
## F7 · The tile-learning idea (B2-9's real fix) — BLOCKED ON ONE BUTTON-PRESS EXPERIMENT, and the failed probe changes less than it seems

### What EXP-TILE-001's negative result actually means

The probe (`captures/raw/EXP-TILE-001.json`) ran `bb 11` → read → cap-on HOST
trigger → read, over USB, and got exact zeros instead of `TILE_SIGNATURE`.
Three reasons it cannot carry the weight of "the design fails", and one thing
it DOES establish:

1. **The gate flag was never obtainable on that path — by protocol, not by
   accident.** The flag lives at offset 24 of an UNSOLICITED `BB 01 09` button
   header only; `button_header_is_gated` returns None for solicited frames
   (marker `0xFF` at byte 58, `usb_measure.py:67-68`), and the corpus shows
   0x00 on 20+ of 20+ host-triggered frames (`usb_measure.py:44-52`). So
   **`wait_for_button_header` does not "fit after a host trigger" at all** — a
   host trigger's reply is solicited and flagless. A gated read that PROVES
   its gatedness requires the operator's button, full stop.
2. **The read was `read_stored` with no `button_header`** (its own metadata:
   `path='read_stored (no trigger sent)'`, `axis_source='ASSUMED…'`,
   `gate_flag=None`) and **no raw frames were kept**. An echo/empty frame
   (the device echoes commands it will not serve — EXPERIMENTS corpus) parses
   through `assemble()` as exact 0.0 on every band, indistinguishable in the
   stored record from a genuinely zero slot. "Exact zeros, stable across three
   reads" fits both stories.
3. **Even the "bb 11 did not zero-fill on USB" sub-finding is suspect**: the
   `before` and `after_calibrate` spectra are bit-identical, and bit-identical
   repeats are the corpus's own signature of a stale cache (MEASUREMENT.md,
   unit-2 note; EXP-020).

What it DOES establish: the composed sequence of report 38 decision 1
(`bb 11` → zeros → capped host trigger → read), **transplanted to USB and read
via a bare `read_stored`, does not return the constant** — while
EXP-MEAS-004, same transport and same read call but with NO preceding
`bb 11`, did (`host_trigger_capped` = `TILE_SIGNATURE` to the digit). The one
variable between the two records is the preceding `bb 11`. So the composed
sequence is demoted: **failed as composed on USB; never yet run over BLE**,
where its three constituent proofs were measured. Label: inference from two
records, raw bytes absent from one.

### Why the DESIGN survives

Report 38's narrow design never depended on the composed sequence for its
primary path: **over USB, a gate-flagged button frame confirms a learn in one
step** (38 §3, corroborated 2/2 vs 0/20+), and the constant is
transport-independent (bit-identical over USB and BLE on the owner's unit —
EXP-BLE-010/015), so **a USB button-learn protects that unit's BLE sessions**.
The BLE-only composed learn was the fallback for cable-less owners; it is the
part now in doubt.

### The exact frame sequence a PROVEN gated read requires (from code)

```
open USB (DTR/RTS low)                      transport.py:138
[operator presses the button, cap on]
hdr = wait_for_button_header(t)             usb_measure.py:74  — unsolicited BB 01 09, marker byte58==0x00
gated = button_header_is_gated(hdr)         usb_measure.py:59  — offset 24 == 0x01
m = read_stored(t, button_header=hdr)       usb_measure.py:127 — chunks BB 01 10/11/12, axis from hdr
                                            → m.gate_flag is True, m.metadata['axis_source']='device header'
```

`CR30.read_next_measurement` (`device.py:337`) is the app-level wrapper of the
same sequence. Anything without the unsolicited header can never carry
`gate_flag`.

### The minimal experiment (owner present, ~3 minutes, 4 button presses)

One sentence for approval: *"Cap on, press the instrument's button once — plus
one uncapped press on plain paper before and after — while a script records the
raw frames, and we learn whether the device itself flags the press as gated and
hands back the tile constant."*

Steps, expectations, and what each outcome proves:

| # | action | record | expected | if not |
|---|---|---|---|---|
| 1 | cap OFF, button press on paper | raw hdr + chunks | gate 0x00, ~85–90 %R | harness broken — stop (positive control) |
| 2 | cap ON (white face seated), press | raw hdr + chunks | **gate 0x01, spectrum = TILE_SIGNATURE (≤0.05 %R every band; record full precision)** | gate 0x01 + zeros → the gated write empties the slot first; press again (step 3) answers whether the SECOND read has it. gate 0x00 → the flag does not replicate even on this unit; the USB one-step learn is dead |
| 3 | cap ON, press again | raw hdr + chunks | gate 0x01, **bit-identical to step 2** | not bit-identical → the "gated reads are bit-exact" pillar fails; the whole learned-guard tolerance argument must be redone |
| 4 | cap OFF, press on the same paper | raw hdr + chunks | gate 0x00, within noise of step 1 | white reference damaged — recalibrate properly; and the "capped press is harmless" claim is wrong and must be withdrawn |

Safety: each capped press may perform a white calibration **against the
correctly-seated tile**, which the corpus shows is harmless (EXP-BLE-015:
paper 88.33 %R before, 87.68 after); step 4 verifies it anyway. Raw bytes of
every frame go into the capture — the absence of raw bytes is what crippled
EXP-TILE-001. (Note EXP-MEAS-004 proved the HOST trigger calibrates; it did
not prove the button press does or does not — hence step 4, not an assumption.)

### Verdict on the feature

**Buildable in report 38's narrow form, blocked on the experiment above** —
which now also doubles as the missing prerequisite run. If step 2 returns
flag+constant: build the USB button-learn (bit-equality match, warn-only until
two independent learns agree, keyed to device-id), ship the rolling
bit-identity window regardless, and leave the BLE-only composed learn OUT
until someone re-runs it over BLE. If step 2 returns flag+zeros twice, the
stored-slot route is wrong on USB and the learn must be taken from the BLE
read-back instead — a separate, BLE-side experiment. Do not let the feature be
parked: it is the only full fix B2-9 has.

---
## F8 · The YouTube D50/D65 answer — the draft is RIGHT in substance, two figures must change, one claim must be cut

### 1 · The pipeline claim — VERIFIED, both transports

There is exactly ONE producer of a CR30 reading for the `.ti3` and exactly ONE
converter, and it defaults to D50 / CIE 1931 2°:

- `measure_bridge.py:803` — `spectrum_to_xyz(m.values)` with **no overrides**;
  `colour.py:130` — `def spectrum_to_xyz(refl, illum=D50, observer=PROFILING_OBSERVER)`;
  `colour.py:117` — `PROFILING_OBSERVER = "2"`.
- `measure_bridge.py:550` is the ONLY place `{"cmd":"value","xyz":…}` is built
  (grep over `workflow/ ui/ core/`), fed from that converter.
- Both transports land in the same `Measurement.values` (31 × %R): USB via
  `usb_measure.read_stored` / BLE via `device.read_measurement`; the reader
  path is transport-agnostic above that point.
- The device's own Lab is stored on the `Measurement` and **consumed by
  nothing** (grep: zero readers), so the CR30's D65/10 display mode cannot
  reach a profile. The display mode changes what the DEVICE shows, not the
  reflectance curve ChromIQ reads — reflectance carries no illuminant.

### 2 · The Argyll side — VERIFIED at source

- The helper takes the values in XYZ mode (`chromiq_chartread.c:3330`
  `xtern … 2 = XYZ`; ChromIQ's external-values `-x` path,
  `measure_manager.py:396-399`) and writes them into the `.ti3` verbatim with
  **no spectral columns** (`:3159-3178` stores `XYZ`, never touches `sp`, and
  the `SPECTRAL_BANDS` block at `:373` is gated on `spec_n > 0`).
- `colprof` defaults, from the shipped source: `colprof.c:1075-1079` —
  `illum = icxIT_D50; obType = icxOT_CIE_1931_2;` — and with CIE data present
  it uses the XYZ as-is. chartread's own spectral default is the same
  (`chartread.c:2512` "1931_2 (def)"). So ChromIQ's D50/2° is exactly the
  condition the `.ti3`/`colprof` convention expects; nothing converts twice.
- Writing XYZ-only is also the honest choice for THIS device:
  EXP-SPEC-001b (VERIFIED) shows the 31 bands carry **8 degrees of freedom**
  — 31 `SPEC_*` columns would over-claim information the sensor does not have
  (MEASUREMENT.md "Consequences").

### 3 · The tables — VERIFIED as claimed

`colour.py:38-52`: D50/D65 sampled from ArgyllCMS 3.5.0's own `il_D50`/`il_D65`
(`xspect.c:244`); the file records that the earlier hand-typed D65 was wrong by
13.4 units at 670 nm and that `validate_illuminants()` originally PASSED it —
the tolerance is now 1e-3 with a mutation test proving the control sees that
error class, and `tests/test_colour_tables.py` re-derives the tables from the
Argyll source when present. The `ref/D50_*.sp` warning (UV-content variants,
not colorimetric D50) is in the module comment. This part of the draft is
solid and has its own guard-rails.

### 4 · M-conditions — DO NOT claim one

The CR30's illuminant's UV content is **UNKNOWN** (MEASUREMENT.md:633,
EXPERIMENTS.md:801-810 — the FWA question is explicitly open), and the sensor
is an unidentified 8-channel part. So the public answer must NOT say M0, M1 or
M2, and must NOT say "UV-cut like a ColorMunki" — nothing in the corpus
establishes that. Honest form: the device does not specify a measurement
condition; on optically-brightened papers it may differ from an M1 instrument.

### 5 · The coverage figure — the upstream number does NOT reproduce; use ≥99.8 %

Recomputed from Argyll's own full-range tables (`il_D50` 300–830 nm and
`ob_CIE_1931_2` 360–830 nm, `native/instlib/xspect.c`), share of each
tristimulus integral inside 400–700 nm:

```
X 99.82 %   Y 99.95 %   Z 99.78 %
```

The draft's "X 99.95, Y 100.00, Z 100.00" is not what these tables give; do
not repeat it publicly. "More than 99.8 % of the D50/2° tristimulus weight"
is safe and still makes the point.

### The corrected reply for Basti to post

> Good question — the answer is that ChromIQ never uses the CR30's own Lab
> numbers, so the device's D65 display mode doesn't matter. Over both USB and
> Bluetooth, ChromIQ reads the raw 31-point reflectance curve (400–700 nm) and
> computes XYZ itself on the computer, under D50 with the CIE 1931 2° observer
> — the standard condition ArgyllCMS expects for printer profiles. Reflectance
> itself is illuminant-independent, so nothing of D65 sticks to the data; the
> D65/10° you see on the instrument's screen is only how it displays its own
> readout. The 400–700 nm range covers more than 99.8 % of the D50/2°
> tristimulus weight. One honest caveat: the CR30 doesn't specify an M
> measurement condition (M0/M1/M2), so on heavily optically-brightened papers
> its readings may differ from an M1 instrument.

Every sentence above is backed by a file:line in this section; the two claims
the draft wanted that are NOT in the reply (the 99.95/100/100 figures, the
UV-cut comparison) are out because they did not survive verification.

---
## VERDICT

**1 · Is the ranking right? Is anything a BLOCKER?**
The ranking of the four backlog items (B2-8 > B2-9 > B2-7 > B2-3) is right,
and B2-8 is stronger than the plan states (F2: the misfire is persisted, the
next frames written are calibrations, and BLE has no second identity gate).
None of the four blocks beta 2 — all predate beta 1 and beta 2 worsens none.
**But there IS a blocker, and it is not on the plan's list: the quit fix the
beta exists to ship does not run (F1).** `closeEvent` looks the manager up
under two names MainWindow has never had; proven inert on a real window. The
owner will see the very warning that opened B2-1 on his first quit. One-line
fix, plus a test that runs the lookup instead of reading its source. Since
that forces a new commit and a fresh gate anyway, the B2-8 fix (delete
`or cands`, split the two refusal messages, one confirm retry on errored
candidates — F2) is cheap to take on the same train; recommended, not
formally blocking.

**2 · What was missed entirely?** Three things: F1 (the inert flagship fix —
the round's predicted "fault inside a fix I had just written"); the
`identify()` BLE echo hole adjacent to B2-8 (F2, latent, zero callers today);
and B2-9's own report already contains a unit-independent partial mitigation
(rolling bit-identity window) that the plan's "not fixable, say it" framing
skips (F3). Also stale-but-committed: the DTR "cannot reset" docstring and
the §6 no-chart log line both survived a review that was accepted "on all
four counts" (F6).

**3 · Should anything committed since beta.1 not ship?** No revert needed.
The DTR change is sound and strictly safer (37 §1 re-verified path); the USB
identify+remember work is fixed properly at HEAD; the chart-instrument note
is right in substance. Ship them — after F1's one-liner, with the DTR
docstring softened (F6) in the same commit.

**Plainly said, where the plan is right:** the harm ranking is correct;
refusing unconfirmed BLE devices IS the right call (the fallback protects
almost nothing real — a held or sleeping CR30 never advertises, and a
freshly-calibrated one still confirms; the one real case, a transient confirm
error, is better served by one retry than by trusting strangers); B2-7 as
documentation-plus-email is right; B2-3's deferral is right; and "beta 2
ships the fixes already made" is the right release theory — it just has to
actually ship them working.

**Status: COMPLETE.**
