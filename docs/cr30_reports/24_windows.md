# CR30 on Windows — first test

STATUS: complete

**Machine:** Windows 11 Home 10.0.26200, **ARM64** VM under VMware, 2 cores, 200 % display scale
**Python:** 3.12.10 (`.venv\Scripts\python.exe`)
**Branch:** `feature/cr30-instrument-159` @ `6ddae691` ("a Bluetooth calibration waited seconds for a reply sent somewhere else") — the required head or later ✅
**Date:** 2026-08-30
**Operator:** Basti (owns the instrument), driving with Claude Code

Written as the work happened. Sections appear in the order of the hand-off
brief. `⛔` marks a finding, `✅` a step that passed, `⏸` a step not yet run.

---

## The short version

**The CR30 works on Windows ARM64.** The instrument was identified, calibrated
(white and black), and read patches — both from a source checkout and from a
PyInstaller bundle built with the release spec. Not one line of
`workflow/cr30/` had to change, and not one of its 283 tests fails here.

Everything that went wrong sat either **below** ChromIQ (a Windows driver),
**beside** it (build artefacts, tests that assume macOS), or **around** it (how
faults are reported to the user). Two blockers were hit and both were cleared
during the session:

| # | Finding | Severity | Where it lives |
|---|---|---|---|
| 1 | `pip install -r requirements.txt` fails on Windows (`pycups`) | annoyance | pre-existing, known |
| **2** | **No working CH34x driver on Windows ARM64 — instrument never becomes a COM port** | **blocker** | Windows / WCH |
| 3 | Two tests hard-code the macOS word "Trash" | test bug | this branch |
| 4 | A US Letter help-card page carries only a repeated table header | cosmetic | Windows fonts |
| **5** | **Nothing tells the user a driver is missing — three faults give one message** | **UX, highest reach** | ChromIQ |
| **6** | **Chart-reading engine on Windows predated CR30 support; no freshness check** | **blocker** | dev/build |
| 7 | "How to measure" window is never closed when a session ends | UI fault | ChromIQ, likely all platforms |
| ~~8~~ | ~~Packaged build cannot see the CR30~~ — **WITHDRAWN, my test was wrong** | — | — |
| 9 | Windows paths break the engine's JSON; `session_start` is lost every run | real, silent | vendored engine |
| 10 | A refused reading is only logged, where the operator will not see it | possibly data-corrupting | ChromIQ |

### The two blockers, and what cleared them

**Finding 2 — the driver.** Windows Update supplied WCH's `ch341ser.inf`
**3.5.2019.1**, whose `[Manufacturer]` line targets `NT, NTamd64, NTia64` — no
ARM64 — and whose driver-store folder contains an `.INF` and a `.CAT` and **no
`.sys` at all**. The device sat at Code 28, so no COM port existed and
`candidates()` correctly returned `[]`. The current package (**4.0.2026.02**)
declares `NTARM64`, is signed by Microsoft's Windows Hardware Compatibility
Publisher, and installs with `pnputil` in about a second — no reboot, no
test-signing. One download covers x86, x64 and ARM64.

**Finding 6 — the engine.** `native/chartread_helper/build/chromiq-chartread.exe`
was dated **5 August**, built by an earlier session whose toolchain had since
been deleted, and contained **zero occurrences of the string `CR30`** while the
source and the committed macOS binary both had it. It refused the chart,
ChromIQ correctly declined to fall back to stock chartread, and the session died
before the first patch — looking exactly like a protocol or hardware fault.
Rebuilding from the current source fixed it outright. `helper_path()` accepts
any existing dev build on existence alone and never compares it to the source.

### The one finding that matters most

**Finding 5.** Three unrelated faults in this session — a missing driver, a
stale engine, and (as I wrongly believed) a missing library — all end with the
user being told the instrument is not there, while it is plugged in and working.
A user cannot tell them apart, and the natural conclusion in each case is "the
cable or the instrument is broken", which is the one thing that is not true.
Basti's suggestion is the answer: ChromIQ already has an **"Install USB Driver…"**
button in Preferences on Windows, and it can grow to cover instrument drivers —
with the caveat that the CR30 needs a *vendor serial* driver, and installing
WinUSB on it (what that button does today) would **destroy** the COM port
pyserial needs. Until that exists, the **stopgap section** in this report is
ready to lift into the changelog.

### Where I was wrong

Twice, and both are recorded in place rather than quietly edited out:

* **Finding 8 is withdrawn.** I checked for `dist/ChromIQ/_internal/serial/` on
  disk, found nothing, and concluded four of six release bundles could not
  reach a CR30. PyInstaller embeds pure-Python packages in the **PYZ inside the
  executable**; `ls` was never a test of this. The bundle contains 14 `serial`
  modules and 41 `bleak` modules, and Basti disproved the claim by measuring
  patches through the packaged app.
* **Finding 6's first draft** said the Windows engine binary "is not committed,
  and cannot be", implying releases were broken. CI builds it for both Windows
  architectures. The real problem is narrower: a Windows *source checkout* has
  no helper and no freshness check.

### The test suite

```
everyday   pytest -n auto              70 failed, 7782 passed, 400 skipped, 3 xfailed   8:42
GATE       pytest --runslow -n auto    72 failed, 7876 passed, 304 skipped, 3 xfailed  14:28
CR30 only  pytest -k cr30 -n auto     264 passed, 19 skipped, 0 failed                 0:08
```

**69 of the 72 gate failures are pre-existing Windows problems**, proved by
re-running the same files on the branch's merge-base (`master`, `3fd11afd`),
where they fail identically. They are overwhelmingly font-metric and pagination
tests — Windows renders text wider than macOS and these assert on measured
geometry. **Three fail only on the branch**, all Windows-only: two are
Finding 3 (the "Trash" literal, where the app is right and the tests are wrong)
and one is Finding 4.

**Zero CR30 tests fail, in any tier.** `PYTHONUTF8=1` is required on Windows or
~55 content tests fail on cp1252 decoding before anything real is measured.

The gate is **not green**, so by `CLAUDE.md`'s rule this is not a release-ready
state on Windows — but none of the redness is CR30's, and 69/72 of it predates
this branch.

### What was NOT tested — none of this should be read as passing

* **Bluetooth** — out of scope; VMware exposes none to this VM.
* **Windows x64** — only ARM64 was available. Also **Linux, entirely.**
* **Dark mode** (8b), **patch re-arming** (8f), and the black-calibration
  window's wording and pictogram (8d, only observed in passing).
* **All of step 9** — 100 %/125 %/150 % display scaling, high-DPI pictogram
  sizing, recovery after VM sleep/wake, and unplugging the cable
  mid-measurement. Only **200 %** scaling was seen, and at that setting the
  Measure tab and calibration window were clean.
* Whether the `CH341SER.EXE` GUI installer puts down a **3.6-or-newer** driver
  — it has no version metadata and was not run.

### Nothing was fixed, and nothing of Basti's was harmed

Per the brief, no ChromIQ code was changed to make anything pass. The two
changes made to this machine were a **driver install** and a **rebuild of a
gitignored build artefact**, both with Basti's explicit approval, and the stale
binary was preserved as evidence. His `cr30-test` project was **copied** to
`~/ChromIQ/CR30-Test`; the Desktop original was never opened for writing and is
byte-identical. His earlier partial measurement was archived to `old/` by the
app's own mechanism, not overwritten.

---

## 1. Checkout ✅

`git fetch` / `checkout feature/cr30-instrument-159` / `pull` clean. Head is
`6ddae691`, exactly the commit the brief asked for. `git pull` reported
"Already up to date".

---

## 2. Dependency install

### ⛔ FINDING 1 — `pip install -r requirements.txt` cannot succeed on Windows (pre-existing, not CR30)

The brief's step 2 fails. `requirements.txt` line 7 pins `pycups`, which is a C
extension against the CUPS headers and has no Windows wheel:

```
Building wheel for pycups (pyproject.toml): finished with status 'error'
error: Microsoft Visual C++ 14.0 or greater is required. Get it with
"Microsoft C++ Build Tools": https://visualstudio.microsoft.com/visual-cpp-build-tools/
ERROR: Failed building wheel for pycups
error: failed-wheel-build-for-install
```

pip exits 1 and installs **nothing** — including `pyserial` and `bleak`, which
it had already downloaded. So a Windows developer following the documented
setup ends up with no CR30 support at all and an error that names CUPS, not the
instrument.

**Classification: Windows problem, pre-existing, and already known to the
project** — `requirements-dev.txt`'s own header says *"requirements.txt pins
pycups, which only builds on macOS/Linux. On Windows install the runtime deps
with pycups filtered out (as the build-windows workflow does)"*, and
`.github/workflows/build-windows.yml:54` does exactly that:

```yaml
grep -v 'pycups' requirements.txt > requirements-win.txt
pip install -r requirements-win.txt
```

Not a CR30 bug and it would not happen on macOS. But it is worth saying that
the knowledge lives in a comment in a dev-only file and in a CI workflow, not
in `CLAUDE.md`'s Setup section, which still says plainly
`pip install -r requirements.txt`. Anyone starting on Windows hits this first.

**Worked around** (for this test only, not committed as a source change) by
running the same two lines the CI workflow runs.

### ✅ With `pycups` filtered, everything installs — including on ARM64

```
Successfully installed bleak-3.0.2 pyserial-3.5 winrt-runtime-3.2.1
  winrt-windows-devices-bluetooth-3.2.1
  winrt-windows-devices-bluetooth-advertisement-3.2.1
  winrt-windows-devices-bluetooth-genericattributeprofile-3.2.1
  winrt-windows-devices-enumeration-3.2.1 winrt-windows-devices-radios-3.2.1
  winrt-windows-foundation-3.2.1 winrt-windows-foundation-collections-3.2.1
  winrt-windows-storage-streams-3.2.1
```

Exit 0, no warnings. This is the part the brief flagged as "the first genuinely
new ground", and it is **clean**: every `winrt-*` wheel resolved as
`cp312-cp312-win_arm64`, so bleak's WinRT bindings ship prebuilt for ARM64
Windows and nothing had to be compiled. `requirements-dev.txt` installed with
no errors (only `pymupdf` was new; the rest were already present).

Both import:

```
pyserial 3.5
bleak import OK, version 3.0.2      # bleak 3.x has no __init__.__version__ —
                                    # read via importlib.metadata, not a fault
```

---

## 3. Discovery — `candidates()`

### ✅ With the instrument NOT passed through

```
>>> from workflow.cr30.discovery import candidates; candidates()
[]
```

Correct — and the stronger check agrees: `serial.tools.list_ports.comports()`
returns **0 ports of any kind** on this VM, so the empty list is a true
negative, not a filter that silently drops everything.

### On the brief's worry about product-string matching

The brief warned that discovery "filters on the CH34x USB-serial chip family …
on macOS that works through pyserial's product strings; on Windows the same
information arrives differently."

Reading `workflow/cr30/discovery.py`, **that worry does not apply to this
code.** The filter is `Candidate.is_ch34x`, which is a numeric comparison:

```python
CH34X_VID = 0x1A86
CH34X_PID = 0x7523
...
return self.vid == CH34X_VID and self.pid == CH34X_PID
```

`product` is carried on the Candidate but never used to decide. pyserial fills
`vid`/`pid` on Windows by parsing the `USB\VID_1A86&PID_7523` hardware ID out
of SetupAPI, which is the same integer pair macOS gets from IOKit. So the
platform difference the brief anticipated is one the module was already written
around. **Pending confirmation with the instrument actually attached** — that
is step 3's second half and is not yet run.

⛔ **With the instrument passed through: the port never appears.** See Finding 2.

---

## ⛔ FINDING 2 — THE BLOCKER: no CH34x driver exists for Windows **ARM64**, so the CR30 never becomes a COM port

Basti attached the CR30 and passed it through in VMware. **The passthrough
worked.** Windows sees the device:

```
FriendlyName : CH554_CDC
InstanceId   : USB\VID_1A86&PID_7523\7&3B74C78&0&2
Status       : Error
Problem      : CM_PROB_FAILED_INSTALL
ProblemDescription : The drivers for this device are not installed. (Code 28).
```

That is the exact VID:PID `discovery.py` looks for (`0x1A86:0x7523`) and the
exact product string the module's docstring documents (`CH554_CDC`). But with
no driver bound there is no serial port, so:

```
Get-PnpDevice -Class Ports   →  (empty)
serial.tools.list_ports.comports()  →  0 ports
candidates()                 →  []
CR30.open_usb()              →  ConnectionError: no CH34x serial device found
```

### Root cause — nailed down, and it is not ChromIQ

A WCH driver **is** already in the Windows driver store, published as
`oem9.inf`, and Windows even filed it in an `arm64`-decorated folder:

```
C:\Windows\System32\DriverStore\FileRepository\ch341ser.inf_arm64_89e3544a870a2366
  CH341SER.CAT   10935
  CH341SER.INF    7405
```

Two things are wrong with it, and either alone is fatal:

1. **The INF declares no ARM64 target.** Its `[Manufacturer]` line is
   `%WinChipHead% = WinChipHead,NT,NTamd64,NTia64` — x86, AMD64 and Itanium.
   All six hardware-ID matches, `USB\VID_1A86&PID_7523` included, live in
   `[WinChipHead.NTamd64]`. On an ARM64 machine there is no section that
   matches, so the driver cannot bind however the device is enumerated.
2. **The package has no driver binary at all.** The store folder contains only
   `.INF` and `.CAT`. The `CH341S64.SYS` that the INF's `.Services` section
   installs is simply not there.

The driver is WCH's, version **3.5.2019.1, dated 2019-01-30**, and `pnputil`
flags it `Attribute: Legacy`. It is a seven-year-old amd64-only package that
Windows Update matched on hardware ID and could not install.

### The Microsoft inbox driver cannot substitute, and the reason is not obvious

`usbser.sys` (10.0.26100.8521) **is** present on this machine, and the device is
called `CH554_CDC`, so the natural guess is that Windows should just bind the
inbox CDC-ACM driver. It will not, and the device's own compatible IDs say why:

```
USB\COMPAT_VID_1A86&Class_FF&SubClass_01&Prot_02
USB\Class_FF&SubClass_01&Prot_02
```

**Class FF — vendor-specific**, not USB CDC (Class 02). Despite the `_CDC` in
the product string, the CH554 bridge does not present itself as a standard
communications device, so `usbser.inf` never matches it. A vendor driver is
mandatory. This is the same reason macOS needs `AppleUSBCHCOM` rather than the
generic Apple CDC driver — the difference is that Apple ships theirs and WCH's
Windows ARM64 one is not on this machine.

### Classification

**A Windows-ARM64 platform/driver problem. Not a ChromIQ bug, not a packaging
bug, and it would not happen on macOS.** No change to ChromIQ's code could make
the instrument appear, because the operating system never creates the serial
port that pyserial enumerates. On x64 Windows the ordinary WCH `CH341SER.EXE`
installer would almost certainly resolve it; the question is only whether WCH
ships an ARM64 build.

### What it blocks

Steps 5, 6, 7, most of 8 and all of 9 need a live instrument, and none of them
can run until a driver binds. Step 10's packaging check can still be done in
part (are `pyserial` and `bleak` in the bundle?) but its 8a–8c re-run cannot.

### Secondary observation — the message ChromIQ gives is accurate but misleading here

`CR30.open_usb()` raises `ConnectionError: no CH34x serial device found`. On
this machine that reads as "your instrument is not plugged in" when the
instrument *is* plugged in, correctly passed through, and visible to Windows by
the very VID:PID being searched for — it is the driver that is missing. A
Windows user would reasonably go hunting for a cable fault.

Worth weighing, **not** proposed as a fix here: `discovery.py` is deliberately
"the ONLY OS-aware module" and deliberately does not do platform PnP
enumeration, so telling the two states apart would mean new Windows-specific
code and a wider remit than the module was given. Flagging it as a UX finding
for whoever owns #159 to decide.


---

## 4. The test suite

### Everyday tier — `pytest -n auto`

```
70 failed, 7782 passed, 400 skipped, 3 xfailed in 522.77s (0:08:42)
```

macOS reference for comparison: **8111 passed, 141 skipped, 3 xfailed, ~3 min**.
Two environment notes that are not results: this VM has 2 cores, so 8:42 against
macOS's 3 min is the hardware, not a regression; and `PYTHONUTF8=1` is required
on Windows or roughly 55 content tests fail with cp1252 `UnicodeDecodeError`
before anything real is measured. The 259 extra skips are macOS-only tests
(CUPS, `pyobjc`, Finder) correctly skipping themselves.

### ✅ The CR30 code itself is clean on Windows ARM64

Run alone:

```
$ pytest -k cr30 -n auto
264 passed, 19 skipped in 7.71s
```

**283 CR30 tests collected, 264 passed, 19 skipped, ZERO failed.** Not one of
the 70 failures is a CR30 test. Everything in `workflow/cr30/` that can be
exercised without the physical instrument — frame decoding, identity, session,
colour, the measure bridge, the replay fixtures — behaves identically on Windows
ARM64 and macOS.

### Classifying the 70 — measured, not guessed

The brief asked which failures are pre-existing Windows issues rather than CR30
ones. Rather than judge by eye: the merge-base of this branch is exactly local
`master` (`3fd11afd`), so the same 15 failing files were re-run there.

```
master  (3fd11afd):  67 failed, 203 passed, 6 skipped
branch  (6ddae691):  70 failed
```

**67 of the 70 fail identically on master and are pre-existing Windows
problems that have nothing to do with the CR30.** They are almost entirely
font-metric and pagination sensitivity — Windows renders text at different
widths than macOS, and these tests assert on measured geometry:

| Count | File | Nature |
|---|---|---|
| 22 | `test_the_manual_panel_does_not_scroll_sideways` | panel width vs. font metrics, all 11 languages |
| 11 | `test_the_layout_panel_fits_the_pane_in_every_language` | same |
| 9 | `test_a_long_label_is_not_clipped_by_its_indent` | same |
| ~15 | `test_pdf_page_rules`, `test_helpcard_blank_letter_sheet`, `test_cmyk_n_numbered_list`, `test_knut_row_page_skip`, `test_164_fixes_stay_fixed` | help-card / PDF pagination |
| 3 | `test_native_file_dialogs` | Windows native dialog behaviour |
| 4 | `test_knut_newbatch` (g3, g4) | dialog start directory |
| rest | `test_redriver_presets_are_knuts`, `test_calibration_before_a_project`, `test_keyboard_shortcuts`, `test_a_failed_start_never_locks_the_app` | assorted |

**Three fail only on the branch.** All three are Windows-only — they pass on
macOS, which is why the macOS reference run is green. Details below.

---

## ⛔ FINDING 3 — two tests hard-code the macOS word "Trash" and can only pass on macOS

```
FAILED tests/test_run_delete.py::test_p1_names_the_measurement_and_the_profile
FAILED tests/test_run_delete.py::test_every_window_says_where_the_files_go
```

Both fail on `assert "Trash" in body`.

**The application is correct here and the tests are wrong** — and the branch is
the thing that made the application correct. `core/trash.py` on master says
"Trash" unconditionally. This branch adds `trash_name()`:

```python
if sys.platform == "darwin":  return tr("Trash")
if os.name == "nt":           return tr("Recycle Bin")
return tr("Wastebasket")
```

Verified live on this machine: `trash_name()` → `'Recycle Bin'`. Its own
docstring records why the fix was needed — *"verified on German Windows 11,
where the app said 'Trash' eight times in one window"*.

So the delete windows now say "Recycle Bin" on Windows, exactly as they should,
and two older assertions in `tests/test_run_delete.py` — which the branch did
**not** touch, they predate it — still demand the macOS noun. They pass on
macOS and cannot pass on Windows or Linux.

**Classification: a test bug, introduced by this branch's own (correct)
platform fix, invisible on macOS.** The product behaviour is right; the tests
need `trash_name()` instead of the literal. **Not fixed here**, per the brief's
rule that the finding is the deliverable.

---

## ⛔ FINDING 4 — a help-card page on US Letter carries a repeated table header and nothing else

```
FAILED tests/test_knut_row_page_skip.py::test_no_sheet_carries_only_a_repeated_table_header
E  main_actions/Letter page 8: the repeated table header and nothing else
```

This is the wasted-sheet fault the test exists to catch — *"the one Knut printed
twice"* — reproduced on Windows, on US Letter, in the `main_actions` card.

It is a Windows font-metrics fault that the branch tipped over the edge rather
than a clean regression. `ui/main_actions.py` is one of the files the branch
edits, and the edit makes two rows **longer**, for the same good reason as
Finding 3:

```diff
-tr("A Delete is permanent by design, and every Delete window says so before
-   you confirm. What a Replace displaced is still in “old”.")
+tr("Open your {trash} and put the folder back where it was. A Delete moves
+   the files there rather than destroying them, and every Delete window
+   says so before you confirm. What a Replace displaced is still in
+   “old”.").format(trash=trash_name())
```

Longer text, and "Recycle Bin" is a longer word than "Trash", against Windows
font metrics that are already wider than macOS's — and the file's sibling test
`test_no_empty_band_is_left_under_a_repeated_header` **already fails on master**
on this same platform. So the ground was soft before the branch pushed it.

**Classification: Windows-only, aggravated by the branch.** Would not reproduce
on macOS. Cosmetic — a wasted sheet in a printed help card, not a data or
measurement fault — but it is real output on real paper.

### The release gate — `pytest --runslow -n auto`

```
72 failed, 7876 passed, 304 skipped, 3 xfailed in 868.05s (0:14:28)
```

Two cores, so 14:28 against macOS's ~3 min is the hardware. **Zero CR30
failures.**

The gate adds exactly **two** failures over the everyday tier, both from the
slow tier and both in the same font-metric family as the other 67:

```
tests/test_helpcard_sheets_in_every_language.py::test_the_orphan_rule_is_what_keeps_that_true_in_other_languages
tests/test_margin_inspector_help_icons.py::test_the_frame_did_not_get_wider
```

Both were re-run on the merge-base (`master`, `3fd11afd`) with `--runslow`, and
**both fail there too**:

```
master:  2 failed, 17 passed in 176.87s
```

So they are pre-existing, not regressions.

### Final classification of the 72

| | count | |
|---|---|---|
| **Pre-existing Windows failures** | **69** | fail identically on the merge-base |
| **Branch-only** | **3** | 2 × Finding 3 (the "Trash" literal), 1 × Finding 4 |
| **CR30 failures** | **0** | out of 283 CR30 tests |

**The gate is not green, so by `CLAUDE.md`'s rule this is not a release-ready
state on Windows.** But none of the redness belongs to the CR30, and 69 of the
72 predate this branch — they are the standing cost of Windows font metrics
against tests that assert on measured geometry, and they deserve their own
piece of work, separate from #159.


---

## ⛔→✅ FINDING 2, RESOLVED: the current WCH driver has ARM64 and fixes it outright

Basti authorised updating the driver on this VM. The fix needs **no** test-signing,
no Secure Boot change and no reboot.

WCH's current package — `CH341SER.ZIP`, obtained from `wch-ic.com`,
**version 4.0.2026.02 dated 11 Feb 2026** — declares ARM64 where the 2019 one did
not:

```ini
[Manufacturer]
%WinChipHead% = WinChipHead,NT,NTamd64,NTARM64        ; ← NTARM64

[WinChipHead.NTARM64]
%CH340SER.DeviceDesc% = CH341SER_Inst.NTARM64, USB\VID_1A86&PID_7523
```

and the package actually ships ARM64 binaries (`CH341PORTSA64.DLL`,
`CH341PTA64.DLL`, plus the `.sys` files). All four signed files verify:

```
CH341M64.sys   Valid   CN=Microsoft Windows Hardware Compatibility Publisher
CH341S64.sys   Valid   CN=Microsoft Windows Hardware Compatibility Publisher
CH341SER.CAT   Valid   CN=Microsoft Windows Hardware Compatibility Publisher
CH341SER.sys   Valid   CN=Microsoft Windows Hardware Compatibility Publisher
```

Installed non-interactively (no GUI wizard, so no modal window left waiting):

```
pnputil /add-driver "...\WIN 1X\CH341SER.INF" /install     → exit 0
```

Immediately afterwards:

```
USB-SERIAL CH340 (COM3)   Status: OK   CM_PROB_NONE   "This device is working properly."
```

### ✅ Step 3, second half — discovery with the instrument attached

```
>>> candidates()
[Candidate(device='COM3', vid=6790, pid=29987, product=None)]
```

`vid=6790, pid=29987` is `0x1A86, 0x7523`. **Discovery works unchanged on
Windows.**

**And it confirms the brief's worry was a real risk that this code happens to be
immune to.** Note `product=None`. pyserial on Windows does **not** populate the
product string — macOS reports `CH554_CDC`, Windows reports nothing, putting the
name in `description` (`'USB-SERIAL CH340 (COM3)'`) instead. Had
`discovery.py` matched on `product` as the brief anticipated, it would have
found **nothing** here even with the driver correctly installed. It matches on
numeric VID/PID, so it is unaffected. Worth keeping that way — a future
"improvement" that reads `product` would silently break Windows.

---

## FINDING 5 — the Windows driver problem needs a place in the app, and there is already a button to grow

**This is Basti's finding, made during the session, and it is the one with the
longest reach.** In his words:

> *"i did not have influence on the driver installation so this might be
> something we have to make the users aware of so they have access to the latest
> driver for the system they use. the app already offers help to install argyll
> drivers on windows. so maybe we can make something similar for drivers of
> other devices."*

and, refining it:

> *"in preferences (only on windows) there is a button to install usb driver.
> this is currently only for the argyll drivers. maybe this can be expanded to
> support other devices. but must find the correct driver for the os version the
> app is running on."*

### The button he means

`ui/dialogs/settings_dialog.py:143` — **"Install USB Driver…"**, Windows-only,
wired to `_show_usb_installer()` and backed by `core/usb_driver_installer.py`,
whose docstring is:

> *"Windows-only: enumerate connected ArgyllCMS-compatible USB devices and
> install WinUSB drivers via wdi-simple (libwdi)."*

It carries a `KNOWN_COLORIMETERS` table of ~30 VID/PID pairs — the i1 Pro
family, ColorMunki, Spyder, DTP and so on — deliberately mirroring the active
device lines in ArgyllCMS 3.5.0's own `usb/ArgyllCMS.inf`. So the shape Basti
is describing already exists: **detect what is plugged in, tell the user the
driver is missing, offer to install it.** That is exactly the interaction the
CR30 needed today and did not have.

### Why the CR30 cannot simply be added to that table

This matters, and the existing code already contains the warning that explains
it. `usb_driver_installer.py` lists what is **deliberately excluded**:

> *"HID colorimeters Argyll reads without libusb (i1 Display Pro, ColorMunki
> Display, etc.) — they must stay on their HID driver, so prompting to install
> WinUSB for them would break them."*

The CR30 is in that same category, for the same reason and more sharply:

- The existing button installs **WinUSB**, a generic Microsoft driver that
  *replaces* a device's driver so libusb can claim the raw USB interface. That
  is what Argyll's instruments need.
- The CR30 needs the **opposite**: a vendor CDC/serial driver (WCH CH34x) that
  creates a **COM port**, because ChromIQ reaches it through `pyserial`.
- **Installing WinUSB on `1A86:7523` would destroy the COM port** and make the
  CR30 permanently invisible to `discovery.candidates()`. Adding it to
  `KNOWN_COLORIMETERS` would not be an improvement; it would be a regression
  that is hard to undo.

So the button can grow, but it needs a **second mechanism** beside the WinUSB
one: install a signed vendor driver package (`pnputil /add-driver … /install`),
not swap the device onto WinUSB. Two device classes, two actions, one entry
point.

### "Must find the correct driver for the OS version" — and it is worse than the OS version

Basti's caveat is the crux, and this session is the proof of it. The machine
already **had** a WCH driver, supplied by Windows Update, correctly matched on
hardware ID — and it was useless:

| | on this machine (ARM64 Win 11) |
|---|---|
| driver Windows Update installed | WCH `ch341ser.inf`, **3.5.2019.1**, 30 Jan 2019 |
| its `[Manufacturer]` targets | `NT, NTamd64, NTia64` — **no ARM64 section** |
| files actually in the driver store | `.INF` + `.CAT` only — **no `.sys` at all** |
| device state | `CM_PROB_FAILED_INSTALL` (Code 28) |
| driver that works | WCH **4.0.2026.02**, declares `NTARM64`, ships `*A64.DLL` |

So the selection rule is not "which OS version" but **"which OS version *and*
which CPU architecture, and does this particular package actually contain a
binary for it"**. A driver can be present, signed, matched by hardware ID, and
still be incapable of loading. Any in-app helper must check that the device
reached a *working* state afterwards, not merely that an install command
returned success.

Worth noting for whoever builds this: WCH publishes the package at a stable
endpoint (`wch-ic.com/download/file?id=5` serves `CH341SER.ZIP`), the binaries
are signed by *Microsoft Windows Hardware Compatibility Publisher*, and
`pnputil /add-driver <inf> /install` installs it non-interactively in about a
second with **no reboot and no test-signing**. This session did exactly that,
with Basti's approval, and the device went from Code 28 to
`USB-SERIAL CH340 (COM3) — working properly` immediately.

### Why it matters more than a convenience

Three separate faults in this session produced **the same message to the user**:

| cause | what the user is told |
|---|---|
| no CH34x driver (Finding 2) | "no CH34x serial device found" |
| stale chart-reading engine (Finding 6) | a session that ends having measured nothing |
| `pyserial` missing from the bundle (Finding 8) | "no USB device (No module named 'serial')" |

In all three the instrument is plugged in and working. A user cannot tell these
apart, and the natural conclusion in each case is "the cable or the instrument
is broken" — the one thing that is not true. **Finding 5 is the only one of the
nine findings that addresses the user's experience of the other eight.**

### Suggested shape, not a change

1. When `candidates()` returns empty on Windows, check whether a `1A86:7523`
   device is present in PnP with a problem code before saying no device was
   found. Note this would put OS-specific code near `discovery.py`, which is
   deliberately *"the ONLY OS-aware module in the package"* — so it belongs
   beside that module, not inside it.
2. Say what is actually wrong: *the instrument is connected but Windows has no
   working driver for it*.
3. Offer the existing **Install USB Driver…** button as the route, extended
   with the vendor-driver mechanism described above.
4. Verify afterwards that a COM port appeared, and say so.

**Reported, not implemented.** It is a design change to a Windows-only feature
and touches the user-facing message catalogue, so under `CLAUDE.md`'s
binding-spec rule it is Knut's and Basti's call, not ours.

---

## 5. Identify the instrument — ✅ PASS

```
open_usb()   took 0.033 s
identify()   took 0.052 s
```

```
Identity(model='CR30',
         device_id='PT…[redacted]',      # serial redacted, per commit decdc872
         second_id='CM…[redacted]',
         version_a='V11.3.', version_b='V10.0.0.0', build='0.0.20231219',
         status_byte=2, suspect_fields=[])
```

**Model reads `CR30`, exactly as on macOS.** All four `AA 0A nn` response frames
decoded, `suspect_fields` empty, and `close()` returned cleanly. The vendored
driver's framing, checksums and identity parsing all work unmodified over the
Windows CH340 COM port.

---

## 6. A reading — ✅ PASS

Basti put the instrument on plain paper on a non-magnetic surface and pressed
its own button. `read_next_measurement(timeout=300)` returned after 54 s of
waiting (all of it human time — the read itself is instant):

```
bands      : 31
mean %R    : 80.24
min / max  : 62.39 / 88.65
values     : 62.39 69.42 74.36 78.70 83.70 87.58 88.65 87.78 85.84 83.56 81.67
             80.86 81.15 81.73 81.81 80.60 78.63 77.18 77.02 77.82 78.16 78.38
             78.94 79.61 80.41 81.82 82.57 82.72 82.07 81.46 80.95
```

**31 bands, which is the CR30's 400–700 nm at 10 nm.** The values decode,
`Measurement`'s own finite/length validation passed, and `close()` was clean.

### On the number being 80.24 and not the briefed 85–90 %R

The brief predicted "somewhere around 85–90 %R" for plain paper. The **peak is
88.65**, squarely in that band; the *mean* is dragged down by the three lowest
bands at the violet end (62.39, 69.42, 74.36 at 400/410/420 nm).

That shape is not a fault — it is what brightened office paper looks like. An
optical brightener absorbs in the near-UV and re-emits around 440–460 nm, so the
spectrum dips at 400 nm and peaks just where this one does. The curve is smooth,
structured and monotonic through the rise; a spoiled white reference — the
failure mode the hardware warning exists for — produces a flat or wildly scaled
curve, not this.

**Reported as a pass, with the caveat that only Basti can confirm the paper
stock.** Nothing here needs a macOS comparison to interpret, but a same-paper
reading on the Mac would settle it beyond argument and is worth doing.

---

## 7. White calibration — ✅ PASS

Cap seated with the white tile facing the opening.

```
calibrate() returned OK after 0.253 s (253 ms)
closed cleanly
```

**253 ms against macOS's ~250 ms.** No error, no retry, no timing difference
worth naming. The command/ack round trip over the Windows CH340 port behaves as
it does over macOS's `AppleUSBCHCOM`.

Taken together, steps 5–7 say the same thing: **once the OS gives ChromIQ a COM
port, the entire vendored CR30 driver works on Windows ARM64 with no change.**
Every Windows-specific problem found so far sits below ChromIQ — in the driver —
or beside it, in tests that assume macOS wording.

---

## 8. The real app

The app launched with no stderr beyond one expected warning, loaded a
**macOS-made CR30 project copied to Windows** (`schema_version 3`), and migrated
it without complaint. Basti's own `cr30-test` was copied to
`~/ChromIQ/CR30-Test`; his Desktop original was never opened for writing and is
byte-identical at the end of this session.

### ✅ What worked

* **The chart's instrument is read correctly on Windows.** The Measure tab
  reports `Chart instrument: CR30 → using Argyll's default strip recognition`,
  read out of a `.ti2` written by macOS.
* **`Location being edited: ChromIQ/CR30-Test/runs/run1/`** — path handling is
  right across the OS boundary.
* **The partial measurement survived the copy** — 4 of 390 patches, shown as
  `Progress: 1.0%`, with the preview rendering expected-vs-measured split
  colours from it.
* **Layout at 200 % scaling on a 3456×2160 display is clean.** Nothing clipped,
  no cut-off buttons, no squashed pictures in the Measure panel.

### ⛔ FINDING 6 — THE CR30 CANNOT MEASURE ON WINDOWS: the chart-reading helper has no Windows binary, and the one on this machine predates CR30 support

Basti pressed **Start Measurement**, took the white calibration, ticked the
black calibration and took that too — and then the session ended immediately
without reading a patch.

The log said:

```
[WARNING] workflow.measure_manager: the chart's instrument is one stock
chartread cannot read (Unrecognised chart target instrument 'CR30')
— not falling back
```

**ChromIQ's own behaviour here is correct** — it must not fall back to stock
chartread for a CR30 chart. The fault is that the thing which was supposed to
read it could not.

#### The chain, proven not assumed

`workflow/chartread_engine.py::helper_path()` searches, in order:
`$CHROMIQ_CHARTREAD`, then the CMake dev build
`native/chartread_helper/build/chromiq-chartread.exe`, then the bundled
`native/chromiq-chartread.exe`.

On this machine it resolves to the dev build, which exists and runs — it is a
correct **ARM64** PE (`machine 0xAA64`), Argyll 3.5.0, and it starts fine. But
its timestamp is **2026-08-05 12:34**, and the branch changed the helper source
in three CR30 commits (`7711b16c`, `5f1354b5`, `f8cdaf75`). The decisive test:

| | `CR30` string present? |
|---|---|
| `native/chartread_helper/chromiq_chartread.c` (current source) | **yes** |
| `native/chromiq-chartread` (macOS, Mach-O, tracked in git) | **yes** |
| `native/chartread_helper/build/chromiq-chartread.exe` (Windows, Aug 5) | **NO — zero occurrences** |

The stale binary has the whole JSON event protocol (`abort_confirm`,
`needs_cal`, `strip_interrupted`, `patch_not_found`, `xy_sheet_read`, …) and it
has the sentence `Unrecognised chart target instrument`. What it does not have
is any knowledge of `CR30`. So it hits its own refusal path, says exactly that,
and stops — which is precisely the warning above.

#### Why this is not just one stale file on one VM

**Correcting my own first reading of this:** the release pipeline is fine.
`.github/workflows/build-windows.yml` builds `chromiq-chartread.exe` for
**both** Windows architectures — x64 with mingw-w64 gcc, and arm64 with
LLVM-mingw (`aarch64-w64-mingw32-clang`) — and copies each to
`native/chromiq-chartread.exe` before packaging. So a **released** Windows
ChromIQ ships a freshly compiled, CR30-aware helper. My first draft said the
Windows binary "is not committed, and cannot be", which was wrong about what
reaches users.

What is true, and still matters:

1. **A Windows source checkout has no helper and no freshness check.**
   `native/chromiq-chartread` (Mach-O) is tracked in git, so a macOS developer
   always has a current binary. There is no tracked `.exe`, and `.gitignore:15`
   excludes `build/` — so on Windows the only binary is whatever the developer
   last built locally. `helper_path()` accepts it on existence alone; it never
   compares it against the source it was built from. A three-week-old build is
   used silently.

2. **This VM's binary was built by an earlier session whose toolchain is gone.**
   `native/chartread_helper/build/CMakeCache.txt` records the compiler as
   `…/3c33e5fa-…/scratchpad/tools/llvm-mingw-20250430-ucrt-aarch64/bin/aarch64-w64-mingw32-clang.exe`
   — a scratchpad belonging to a different Claude Code session, long since
   cleaned up. The build is reproducible (`native/gammap_helper/build_windows_arm64.ps1`
   downloads exactly that toolchain), but nothing prompts anyone to redo it.

3. **A locally packaged build inherits the gap.** `native/chromiq-chartread.exe`
   does not exist in this checkout, so a developer running
   `pyinstaller ChromIQ.spec` here bundles no engine at all, and the packaged
   app raises `EngineUnavailable`. That is step 10's business and is examined
   there.

**Classification: a Windows developer-experience and local-packaging problem —
not a defect in what users receive.** It is a blocker for testing the CR30 on
Windows from source, which is what this exercise is. It would not happen on
macOS, where the current binary is checked in. It is **not** a bug in
`workflow/cr30/` — everything there is correct, as steps 5–7 and the 264
passing CR30 tests show.

**The cheap guard, for whoever owns this:** `helper_path()` could compare the
dev build's mtime against `chromiq_chartread.c` and refuse (or warn loudly) when
the source is newer. A silent stale binary cost this session an hour and
produced a failure that looked like a hardware or protocol fault.

### ⛔ FINDING 7 — the "how to measure" window is left on screen when the session ends, and its button then does nothing

Independent of *why* the session ended, what Basti saw was two windows:

> *"after the black calibration I get a pop up 'nothing was measured' 'the
> session ended…'. I confirmed this while the other pop up was still under it
> (the ready to measure — patch by patch one). I could press start measurement
> then in the other pop up but I could not measure and would have to start the
> process again."*

That is M-END-EMPTY (`unified_measurement_management.md` §M) arriving on top of
the CR30 instructions window.

The instructions window is **deliberately modeless** and that is right —
`_show_cr30_measuring_window` documents it: *"the reading is driven by the
instrument's own button, so a modal would sit between the user and the preview
they are meant to be watching."* The fault is the **lifecycle**, not the
modelessness:

* `self._cr30_how_dlg = dlg` keeps the window alive, and **nothing ever closes
  it when the session ends.** `_cr30_how_shown` is reset at the start of the
  next measurement (`tab_measure.py:5637`), but the dialog object itself is
  never `close()`d or `reject()`ed on an ending.
* Its button is wired `box.accepted.connect(dlg.accept)` and nothing else. It
  **only closes the window** — it cannot start a measurement. Labelled
  **"Start measuring"**, sitting on screen after the session is already dead, it
  reads as the way to try again. It is not. That is exactly the dead end Basti
  described.

**Classification: a genuine UI fault that is not Windows-specific in mechanism.**
It needs a session that ends before the first patch; on Windows that happens
every time because of Finding 6, but on macOS any engine refusal, unplugged
instrument or immediate stop should reproduce it. Worth checking there.

**Not fixed here**, per the brief. It also touches
`unified_measurement_management.md` §M and `measurement_exit_strategy.md`
("every window that can end a measurement"), so under `CLAUDE.md`'s binding-spec
rule this is reported for review rather than corrected: the exit strategy
document should say what happens to a modeless instructions window when a
session ends, and as far as this reading goes, it does not.

### ✅ No data was lost

Worth stating plainly, because the screen suggested otherwise. After the failed
session the tab showed **`Progress: 0.0%`** where it had shown 1.0 %, and the
button changed to **CONTINUE MEASUREMENT** with *Refine / resume existing
measurement (-r)* newly ticked. On disk, nothing had happened:

```
CR30-Test.ti3          NUMBER_OF_SETS 4, 4 data rows, mtime = the copy time
Desktop original       NUMBER_OF_SETS 4, 4 data rows   → identical
old/                   no new snapshot created
```

So the 4 existing readings were untouched. **The 1.0 % → 0.0 % reset is a
display fault only** — the progress figure follows the dead session rather than
the file that still holds four patches — but on a screen that has just said
"nothing was measured", a progress bar dropping to zero reads as *"and your
earlier work is gone too"*. Minor next to Findings 6 and 7, and worth a line.

---

## ✅ FINDING 8 — **WITHDRAWN.** The packaged Windows build *can* see the CR30. My test was wrong.

**This finding was raised, and it was wrong. Basti disproved it by running the
packaged app.** The correction is kept in full rather than deleted, because the
mistake is instructive and because an earlier draft of this report stated the
opposite in strong terms.

### What I claimed

That `ChromIQWin.spec` declares no `serial` / `bleak` / `winrt` hidden imports
(true), and that the resulting bundle therefore contains neither, so all four
Windows and Linux artifacts could not reach a CR30 (**false**).

### The bad test

I looked for directories:

```
ls dist/ChromIQ/_internal/serial   -> absent
ls dist/ChromIQ/_internal/bleak    -> absent
```

and concluded the modules were missing. **That is not how PyInstaller stores
pure-Python packages.** They go into the **PYZ archive embedded in the
executable**; only packages carrying binary extensions or data files also get a
directory under `_internal/`. Looking on disk for a pure-Python package and
finding nothing proves nothing at all.

### What the bundle actually contains

`build/ChromIQWin/PYZ-00.toc` — the authoritative list:

```
'serial'                            'bleak'
'serial.serialutil'                 'bleak.backends'
'serial.serialwin32'                'bleak.args.winrt'
'serial.tools'                      … 41 bleak modules in total
'serial.tools.list_ports'
'serial.tools.list_ports_windows'   ← the runtime-dispatched one
'serial.tools.list_ports_linux'
'serial.tools.list_ports_osx'
'serial.win32'
  14 serial modules in total
```

plus **nine `winrt` `.pyd` files** in `dist/ChromIQ/_internal/winrt/`, which is
bleak's Windows Bluetooth backend.

### Why PyInstaller found them unaided

My reasoning was that lazy, in-function imports and runtime platform dispatch
would defeat static analysis. Both premises were wrong in this case:

* **PyInstaller's modulegraph follows `import` statements inside function
  bodies.** `from serial.tools import list_ports` in `discovery.py` is still a
  static import in the compiled bytecode, lazy or not.
* **The platform dispatch is a static branch, not a dynamic lookup.**
  `serial/tools/list_ports.py:28` reads
  `if os.name == 'nt': from serial.tools.list_ports_windows import comports`.
  modulegraph walks **every** branch, which is exactly why the bundle contains
  the Linux and macOS variants too.

Nothing here relies on the spec. It would only have broken had the import been
genuinely dynamic — `importlib.import_module("serial")` or similar.

### The proof that settles it

Basti ran the packaged app — the one built from `ChromIQWin.spec`, with the dev
app closed so there was no ambiguity about which was which — and measured
patches with the CR30 through it:

> *"it worked in the open app as well"*

### What survives, much weaker

Not a blocker, and not a bug — a robustness gap worth a sentence:

**The macOS spec declares these dependencies; the Windows and Linux specs get
them by inference.** `ChromIQ.spec` names `serial`, `serial.tools`,
`serial.tools.list_ports` and `bleak` explicitly, with a comment explaining
why. The other two specs work because modulegraph happens to reach the same
place. Should `workflow/cr30` ever move to a genuinely dynamic import, macOS
would keep working and Windows and Linux would break silently — and the symptom
would be `no USB device (No module named 'serial')`, indistinguishable from a
hardware fault. Declaring them in all three specs costs four lines and removes
the coupling.

**Linux remains UNVERIFIED.** The same inference should apply, and `dbus_fast`
is imported statically by bleak's BlueZ backend, so it will probably behave like
Windows. No Linux machine was available in this session. It should not be
recorded as working on the strength of the Windows result.

### The lesson worth keeping

Three faults in this session produced the same user-visible symptom, and I added
a fourth phantom one by testing the wrong thing. **`ls` on `_internal/` is not a
test of whether a frozen app can import a module.** The tests that mean
something are the PYZ TOC, and running the packaged app against real hardware —
which is what caught this.

---

## FINDING 6, CONFIRMED BY REBUILD

With Basti's approval the helper was rebuilt from the current source, using the
toolchain the project's own `native/gammap_helper/build_windows_arm64.ps1`
downloads (LLVM-mingw 20250430, `aarch64-w64-mingw32-clang` 20.1.4), which was
already present in `.tools/`. Nothing in ChromIQ was edited; only the build
artefact was regenerated, and the stale one was preserved as evidence.

```
cmake -S native/chartread_helper -B native/chartread_helper/build       -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release       -DCMAKE_C_COMPILER=aarch64-w64-mingw32-clang
cmake --build …                                   → exit 0
```

| | stale (Aug 5) | rebuilt (Aug 30) |
|---|---|---|
| PE machine | ARM64 | ARM64 |
| runs | yes | yes |
| knows `CR30` | **no** | **yes** |

**The binary was the only difference.** This closes the diagnosis in Finding 6:
the CR30 code, the driver, the instrument and the app were all correct, and a
build artefact three weeks older than the feature was producing a failure that
looked like a protocol or hardware fault.

---

## 8 (retest, with the rebuilt engine) — ✅ WORKS

With the current helper in place, Basti repeated the whole flow:

> *"it worked, the calibration window looked good, i took a few measurements
> afterwards."*

Confirmed on disk — the measurement really was written, and the earlier readings
were archived rather than destroyed:

```
CR30-Test.ti3        NUMBER_OF_SETS 7   (was 4 before this session)
old/2026-08-30_022149/                  <- the previous 4-patch file, kept
reports/report_2026-08-30_02-22-30.json <- this session's report
```

So **8a (calibration window appears), 8c ("Calibrate now" works and the app says
so) and 8e (reading patches works) all pass on Windows.** The white and black
calibrations, the CR30 instruction window, patch reads and the save path all
behave.

### What is NOT confirmed, and should not be read as passing

Being exact about the limits of this run:

* **8b — legibility in Windows light *and* dark mode: NOT tested.** Basti saw
  the calibration window in the current (light) theme and said it looked good.
  Dark mode was never switched on. **Unverified.**
* **8d — the second window for the black calibration asking for the cap OFF:**
  the black calibration was taken and the flow completed, but the window's
  wording and pictogram were not captured or checked against the spec.
  **Partially observed, not verified.**
* **8f — clicking a measured patch to re-arm it:** not exercised.
* **9 — 100 %/125 %/150 % scaling, high-DPI pictogram sizing, sleep/wake
  recovery, and unplugging mid-measurement:** none of these were run. Only
  **200 %** scaling was seen, and at that setting the Measure tab and the
  calibration window were clean.

These are results too, in the brief's sense: they are steps this session did not
reach, not steps that passed.

---

## ⛔ FINDING 9 — Windows paths break the engine's JSON: `session_start` is silently lost on every Windows measurement

Even in the successful run, one warning appears every time:

```
[WARNING] workflow.chartread_engine: engine: undecodable event line:
{"event":"session_start","chart":"C:\Users\sebas\ChromIQ\CR30-Test\runs\run1\CR30-Test.ti2",...
```

**The chart path is interpolated into a JSON string without escaping.**
`chromiq_chartread.c:4246`:

```c
fprintf(stdout,
        "\n{\"event\":\"session_start\",\"chart\":\"%s\",\"randomised\":%s,"
        "\"patches\":%d,\"steps_per_pass\":%d,\"strips\":[",
        inname, rand ? "true" : "false", npat, stipa);
```

`inname` goes in raw. On Windows that is `C:\Users\...`, and `\U`, `\C` and
`\r` are not valid JSON escapes, so **the entire event fails to parse and is
discarded.**

The helper already has the right tool and uses it elsewhere —
`cq_json_escape()` (`chromiq_json.c:51`) escapes `"` and `\` correctly, and
line 493 calls it for exactly this purpose. This one call site was missed.

**Why it is invisible on macOS and Linux:** their paths contain no backslashes,
so the unescaped string happens to be valid JSON. The bug has been latent since
the event was written and can only appear on Windows.

### What is actually lost

`session_start` is not cosmetic. `measure_manager.py:1189` uses it to:

* reset `_saw_spot_ready`, `_ending_already_answered` and `_stop_requested` for
  the new session;
* set `_chart_was_complete`, which decides via `_all_done_is_news` whether the
  **"All Strips Read" window and the completion sound** can fire at all;
* populate `_session_strips` / `_engine_strips`, the strip map the UI reads
  (`tab_measure.py:10616`, `:12188`).

With the event dropped, those flags keep values from the previous session and
the strip map stays empty. The measurement still works — Basti's seven patches
prove that — but the completion announcement and the stop/ending bookkeeping are
running on stale state on **every Windows measurement**. This is precisely the
class of fault the beta.150 comment at that call site was written to prevent.

**Classification: a real Windows-only bug in the vendored engine, latent on
macOS.** Low blast radius, silent, and a one-line class of fix (`cq_json_escape`
the path, as line 493 does). **Not fixed here**, per the brief.

---

## ⛔ FINDING 10 — a refused reading is announced only in the log pane, where an operator reading 390 patches will not see it

**Basti's finding, hit live while measuring.** He lifted the instrument slightly
too early and got, in the log output window:

> *"The CR30 could not be read for patch A3: 6 consecutive bands are exactly
> 0.0 %R. That is a truncated or zero-filled reply, not a dark sample — a real
> dark patch still reads a few percent.. Press the button on the instrument
> again."*

His conclusion:

> *"messages like this should be placed in a pop up window for the user to
> confirm so it can't pass unnoticed by the user making a lot of measurements
> then useless because the user would simply continue"*

### What the code does

`ui/tabs/tab_measure.py:7364` — `_on_cr30_read_failed`:

```python
def _on_cr30_read_failed(self, loc: str, message: str) -> None:
    text = tr("The CR30 could not be read for patch {loc}: {message}. "
              "Press the button on the instrument again.").format(...)
    self._log.appendPlainText(text)
    self._log.ensureCursorVisible()
    self._flash_status(text, duration_ms=8000)
```

A log line and an **8-second** status flash. No window, no sound, nothing to
confirm.

The detection itself is good work — `Measurement.check_usable()` in
`workflow/cr30/measurement.py:198` gates on a zero-run of 3+ bands precisely
because *"a truncated, zero-filled reply looks structurally perfect: right
header, right length, valid checksum"*. The reading is caught. **The problem is
purely that the person is not told in a way they can miss nothing.**

### Why the operator is exactly the person who will not see it

The CR30 is read patch-by-patch by pressing a button on the instrument. During a
390-patch chart the operator's eyes are on **the paper and the instrument**, not
on a log pane in the corner of a window that may not even be in front. Eight
seconds of status text is not addressed to someone whose head is down.

### The consequence, and it may be worse than wasted work

Basti's framing was "measurements then useless". Reading the code, there is a
sharper risk worth checking. The message says *"Press the button on the
instrument again"*, so **patch A3 stays armed**. An operator who did not notice
has already moved the instrument on to the next patch on the paper. Their next
button press then reads the *next patch's colour* and files it under **A3** —
a wrong colour on a correctly-named patch.

That is the exact failure the neighbouring code is written to prevent.
`_on_cr30_dropped`, ten lines above, says so in its own docstring:

> *"Dropping costs the operator one button press; sending it would put a colour
> on the wrong patch, **which nothing downstream can detect**."*

**Flagged as an inference from reading the code, not as an observed event.** It
was not reproduced in this session and should be confirmed before being treated
as fact. If it holds, this is not a UX nicety — it is a silent data-corruption
path guarded only by whether the operator happened to be looking at the log.

### Where it belongs

The message is user-facing and concerns the ending/interruption of a
measurement, so under `CLAUDE.md`'s binding-spec rule it is governed by §M of
`unified_measurement_management.md` and by `measurement_exit_strategy.md`. A new
or promoted window needs to go to **§M-PROPOSED** and be approved before it is
written into a tab — `tests/test_message_catalogue.py` enforces exactly that.

**Reported, not implemented**, per the brief and per the spec rule. Worth
deciding at the same time:

* whether every `_on_cr30_read_failed` deserves a modal, or only the ones
  indicating a bad *reading* (zero-run, bit-identical) as opposed to routine
  mistiming (`_on_cr30_dropped`, `_on_cr30_readings_discarded`, which cost only
  a button press and are self-correcting);
* whether a sound is the lighter answer for the routine cases, given #131
  already has per-patch sounds and `measurement_window_sounds.md` governs them;
* and whether the still-armed patch should be **visibly** re-highlighted, so
  the screen shows what the log says.

---

# STOPGAP FOR THE FIRST BETA — installing the CR30's Windows driver by hand

*Asked for by Basti: a manual route users can follow now, so the first beta is
not blocked on building the in-app driver helper (Finding 5). Written to be
lifted straight into the changelog or release notes.*

**Windows only.** macOS ships the driver (`AppleUSBCHCOM`) and needs nothing.
Linux has `ch341` in the kernel and needs nothing.

## ONE download covers x86, x64 and ARM64 — only one link is needed

Asked during the session: *"is it one driver for x64 and arm or do we need two
links?"* — **one.** The WCH package is architecture-universal. A single
`CH341SER.INF` declares all three targets and ships a driver binary for each,
and Windows picks the right one by itself:

```ini
[Manufacturer]
%WinChipHead% = WinChipHead,NT,NTamd64,NTARM64      ; x86, x64, ARM64

[CH341SER_Inst.NTamd64.Services]
AddService = CH341SER_A64, 2, CH341SER.ServiceA64   ; -> CH341S64.SYS   (x64)

[CH341SER_Inst.NTARM64.Services]
AddService = CH341SER_M64, 2, CH341SER.ServiceM64   ; -> CH341M64.SYS   (ARM64)
```

Both `.sys` files are inside the one download. So the release notes need **one
link and one instruction**, not a per-architecture table — the only thing that
differs by architecture is the **minimum version**: ARM64 needs 3.6 or newer,
while x64 has been supported since long before that.

## Draft text for the changelog / release notes

> **Windows: the CR30 needs a USB driver, and Windows may not supply a working one**
>
> The CR30 talks to your PC through a CH340 USB-to-serial chip. Windows must
> have a driver for it before ChromIQ can see the instrument at all — and
> Windows Update sometimes installs a version that cannot run on your PC,
> particularly on **ARM64** machines (Surface, Snapdragon laptops, Windows on
> Arm in a VM). When that happens ChromIQ reports *"no CH34x serial device
> found"* even though the instrument is plugged in and switched on.
>
> **How to tell whether you need this.** Plug the CR30 in, open **Device
> Manager**, and look:
>
> * Under **Ports (COM & LPT)** you see **USB-SERIAL CH340 (COM*n*)** —
>   nothing to do, the driver is fine.
> * You see a device with a warning triangle, named **CH554_CDC** or **USB2.0-Serial**,
>   often under **Other devices**, with *"The drivers for this device are not
>   installed. (Code 28)"* — you need the driver below.
>
> **Installing it.** Download the CH341SER package from the manufacturer, WCH:
>
> * https://www.wch-ic.com/downloads/CH341SER_EXE.html — the installer
>   (`CH341SER.EXE`); run it and press **Install**.
> * https://www.wch-ic.com/downloads/CH341SER_ZIP.html — the same driver as a
>   ZIP, if you would rather install it from Device Manager or `pnputil`.
>
> **On ARM64 you must have version 3.6 or newer.** Versions before that contain
> no ARM64 driver at all, which is exactly what makes Windows Update's copy
> fail. The current release (**4.0.2026.02**) is fine. After installing, unplug
> the CR30 and plug it in again, and check Device Manager shows
> **USB-SERIAL CH340 (COM*n*)** working properly.
>
> No reboot is needed, and nothing about Secure Boot or driver signing has to be
> changed — the driver files are signed by Microsoft's Windows Hardware
> Compatibility Publisher.
>
> *A future ChromIQ will offer to do this from Preferences, alongside the
> existing "Install USB Driver…" button for ArgyllCMS instruments.*

## What was actually verified in this session, and what was not

Being precise, so nobody ships a claim that was not tested:

| | verified? |
|---|---|
| ZIP package `CH341SER.ZIP`, driver **4.0.2026.02** (11 Feb 2026) declares `NTARM64` and matches `USB\VID_1A86&PID_7523` | **yes** — read from the INF |
| its four binaries signed *CN=Microsoft Windows Hardware Compatibility Publisher*, all `Valid` | **yes** — `Get-AuthenticodeSignature` |
| `pnputil /add-driver "<...>\WIN 1X\CH341SER.INF" /install` -> exit 0, device becomes `USB-SERIAL CH340 (COM3)`, working properly | **yes** — on this ARM64 VM |
| no reboot, no test-signing, no Secure Boot change needed | **yes** — nothing was changed here |
| `CH341SER.EXE` installer downloads and is validly signed by *Nanjing Qinheng Microelectronics* (WCH) | **yes** |
| which driver **version** that `.EXE` installs | **NO — not verified.** It carries no version metadata and was not run. |
| behaviour on **Windows x64** | **NO — not tested.** Only ARM64 was available. x64 is the case that mostly already works, since WCH has shipped amd64 since 2019. |

**So the changelog text should keep the "check Device Manager afterwards" step.**
It is the only part that proves the install worked, and it is cheap. If the
`.EXE` route turns out to install a pre-3.6 driver on an ARM64 machine, the
symptom is unchanged (Code 28) and the ZIP route is the fallback.

## The exact commands, for a support reply or a bug report

For anyone technical enough to prefer a terminal — this is what was run here,
verbatim:

```powershell
# what state is the device in?
Get-PnpDevice | Where-Object { $_.InstanceId -match 'VID_1A86' } |
    Format-List FriendlyName, Status, Problem, ProblemDescription

# install (elevated), after extracting CH341SER.ZIP
pnputil /add-driver "<extracted>\CH341SER\WIN 1X\CH341SER.INF" /install

# did it work?
Get-PnpDevice -Class Ports | Format-Table Status, FriendlyName, InstanceId
```

And from ChromIQ's own code, which is the definitive test:

```
python -c "from workflow.cr30.discovery import candidates; print(candidates())"
# working:  [Candidate(device='COM3', vid=6790, pid=29987, product=None)]
# not yet:  []
```

## Why this is worth doing even after Finding 5 is implemented

An in-app installer still has to be *told* what went wrong, and this section is
the knowledge it would encode: the fault is a **version and architecture**
mismatch, not a missing download, and the only reliable confirmation is that a
COM port appeared afterwards. Shipping the manual note first also means the
beta can go out, and the in-app helper becomes an improvement rather than a
blocker.

---

# THE PACKAGING AUDIT — what the downloadable bundles need on macOS, Windows and Linux

*Requested by Basti during this session: "please write down your findings for the
github app bundles so they will work under all supported macos windows and linux
versions."*

This section is about the **six artifacts users actually download from GitHub**,
not about developer checkouts.

> **This section was rewritten after its first version was proved wrong.** It
> originally said four of the six bundles could not reach a CR30. They can. See
> Finding 8 (withdrawn) for the bad test and the correction.

## The state of it today

| Release artifact | Built by | Spec used | CR30 over USB | CR30 over Bluetooth |
|---|---|---|---|---|
| `ChromIQ-macOS-arm64.dmg` | `build-release.yml` | `ChromIQ.spec` | yes (declared) | yes (declared) |
| `ChromIQ-macOS-universal.dmg` | `build-release.yml` | `ChromIQ.spec` | yes (declared) | yes (declared) |
| `ChromIQ-Windows-x64.zip` | `build-windows.yml` | `ChromIQWin.spec` | **yes (by inference)** | likely (by inference) |
| `ChromIQ-Windows-arm64.zip` | `build-windows.yml` | `ChromIQWin.spec` | **yes — PROVEN on hardware** | likely (by inference) |
| `ChromIQ-Linux-x86_64.tar.gz` | `build-linux.yml` | `ChromIQLinux.spec` | probably (by inference) | probably (by inference) |
| `ChromIQ-Linux-aarch64.tar.gz` | `build-linux.yml` | `ChromIQLinux.spec` | probably (by inference) | probably (by inference) |

**"Proven"** means the packaged app read patches from a real CR30 in this
session. **"By inference"** means PyInstaller's module graph pulls the
dependency in without the spec asking, which was verified in the Windows ARM64
bundle's `PYZ-00.toc` (14 `serial` modules, 41 `bleak` modules, 9 `winrt`
`.pyd`s). **Linux was never built or run here and must not be recorded as
working on the strength of the Windows result.**

## The real gap: declared on one platform, inferred on two

All three CI workflows install `pyserial` and `bleak`, so the dependency lists
are correct everywhere. The difference is whether the spec *says so*:

| pattern | `ChromIQ.spec` | `ChromIQWin.spec` | `ChromIQLinux.spec` |
|---|---|---|---|
| `serial` | 5 | 0 | 0 |
| `bleak` | 6 | 0 | 0 |
| `winrt` | 12 | 0 | 0 |
| `dbus_fast` | 1 | 0 | 0 |

`ChromIQ.spec` names them and explains why:

> *"CR30 instrument support (#159) … They are imported lazily (workflow/cr30
> degrades without them), which is exactly why PyInstaller cannot find them on
> its own — and why their absence shows up as `no USB device (No module named
> 'serial')` rather than a build error."*

**That comment turns out to be over-cautious rather than wrong.** PyInstaller's
modulegraph does follow imports inside function bodies, and `pyserial`'s
platform dispatch is a static `if os.name == 'nt': from
serial.tools.list_ports_windows import comports` — a branch modulegraph walks,
along with the Linux and macOS ones. So the Windows bundle contains all of it
without being told.

The gap that remains is a **coupling nobody declared**: two of the three
platforms depend on an implementation detail of PyInstaller's static analysis.
If `workflow/cr30` ever switched to a genuinely dynamic import
(`importlib.import_module`), or if a future PyInstaller narrowed its branch
walking, macOS would keep working and Windows and Linux would fail — silently,
with a message that reads as a hardware fault.

Also note the *placement* oddity, which is real regardless: the nine `winrt.*`
collections exist **only** to serve Windows and the `dbus_fast` collection
**only** Linux, and both sit in the macOS spec, inside `sys.platform` branches
that can never run there.

## Recommendation

Cheap, and it removes the coupling:

1. Declare the four imports — `serial`, `serial.tools`,
   `serial.tools.list_ports`, `bleak` — in **all three** specs.
2. Move the platform-branching Bluetooth block out of `ChromIQ.spec` into
   something like `packaging/cr30_deps.py` exporting
   `(datas, binaries, hiddenimports)`, imported by all three. The block already
   branches on `sys.platform` internally, so it needs no per-platform editing —
   only one home instead of one file and two absences.
3. **Add a post-freeze CI assertion on all three platforms.** This needs no
   hardware and is the check that actually matters:

   ```
   grep -q "'serial.tools.list_ports_windows'" build/<name>/PYZ-00.toc   # or the platform's variant
   grep -q "'bleak'"                            build/<name>/PYZ-00.toc
   ```

   Note the test must read the **PYZ table of contents**, not the `_internal/`
   directory listing — pure-Python packages are embedded in the executable and
   never appear on disk. Getting that wrong is what produced the withdrawn
   Finding 8.

**Recommendations, not changes.** Nothing here was modified, per the brief.

## Per-platform notes that still stand

- **Windows (x64 + arm64)** — the `winrt` wheels exist for ARM64 and install
  cleanly: this session got `winrt-runtime-3.2.1` and all eight namespace
  packages as `cp312-cp312-win_arm64` with nothing compiled. USB needs only
  `pyserial`. The real Windows obstacle is not packaging at all — it is the
  **CH34x driver** (Finding 2), which no bundle can fix.
- **Linux (x86_64 + aarch64)** — `dbus_fast` is a compiled extension reached
  through bleak's BlueZ backend. Untested here. Worth documenting that the
  CH34x appears as `/dev/ttyUSB*` and the user must be in `dialout` / `uucp`;
  that is documentation, not packaging.
- **macOS (arm64 + universal2)** — correct and explicit already, and Apple
  ships the CH34x driver (`AppleUSBCHCOM`), so there is no driver step at all.

---

## 10. The packaged build — ✅ PASS, including on hardware

The brief expected this to be the part most likely to be broken. It was not.

### Building it

One step had to be done by hand, and it is the same step CI does for itself:
`native/chromiq-chartread.exe` is not in the repository (see Finding 6), so the
freshly rebuilt engine was copied into place exactly as
`build-windows.yml` does before packaging:

```
cp native/chartread_helper/build/chromiq-chartread.exe native/chromiq-chartread.exe
python -m PyInstaller ChromIQWin.spec --noconfirm      → exit 0
```

`ChromIQWin.spec` is the spec CI uses for both `ChromIQ-Windows-x64.zip` and
`ChromIQ-Windows-arm64.zip`, so this is a faithful local reproduction of the
released artifact apart from that one staging step.

### What is in the bundle

Both native helpers are bundled:

```
dist/ChromIQ/_internal/native/chromiq-chartread.exe   1471488
dist/ChromIQ/_internal/native/chromiq-gammap.exe      1953280
```

And — the point the brief asked to check explicitly, *"Check explicitly that
both are present in the build, and say how you checked"*:

**`pyserial` and `bleak` ARE both present.** How I checked, and how I checked
wrongly first:

* **Wrong way (do not use):** `ls dist/ChromIQ/_internal/serial` — absent. This
  proves nothing; PyInstaller embeds pure-Python packages in the PYZ inside the
  executable, and only packages with binary extensions or data files also get a
  directory. Acting on this produced the withdrawn Finding 8.
* **Right way:** `build/ChromIQWin/PYZ-00.toc`, the archive's table of contents
  — **14 `serial` modules** including `serial.tools.list_ports_windows`, and
  **41 `bleak` modules** including `bleak.args.winrt`.
* **Also present on disk**, because they are binary extensions: nine
  `winrt/*.pyd` files in `dist/ChromIQ/_internal/winrt/` — bleak's Windows
  Bluetooth backend.
* **The only test that really settles it:** running the packaged app against
  the instrument (below).

### Running it — steps 8a-8c repeated in the packaged app

With the development app closed so there was no ambiguity about which window
was which, Basti drove the packaged `dist\ChromIQ\ChromIQ.exe` with the CR30
attached:

> *"it worked in the open app as well"*

So in the **packaged** build: the instrument is found, the calibration window
appears, the calibration is taken and confirmed, and patches are read. **8a, 8b
(light theme only) and 8c all pass in the frozen app**, on Windows ARM64.

### Caveats on what this does and does not prove

* It proves the **spec** is sufficient — `ChromIQWin.spec` produces a bundle
  that reaches a CR30 over USB.
* It does **not** exercise the CI pipeline end to end. CI builds the engine
  itself with LLVM-mingw and copies it into `native/` in the same job; here that
  copy was done by hand from a locally rebuilt binary. The mechanism is
  identical, but a genuine release artifact was never downloaded and run.
* **Bluetooth was not tested at all** — out of scope for this session
  (VMware exposes no Bluetooth to this VM), so `bleak` being in the bundle is
  evidence about packaging, not about a working BLE connection.
* Only **ARM64** was built and run. The x64 artifact was not exercised.



---

# Appendix — what this session changed on the machine

Nothing was committed. `HEAD` is still `6ddae691`, and
`docs/cr30_reports/24_windows.md` (this file) is the only file intended to be
kept.

### Changed, with Basti's explicit approval

| what | where | reversible? |
|---|---|---|
| **WCH CH341SER driver 4.0.2026.02 installed** | Windows driver store | yes — Device Manager, or `pnputil /delete-driver` |
| **`chromiq-chartread.exe` rebuilt** from current source | `native/chartread_helper/build/` | gitignored build output |

The **stale 5 August binary was preserved** as evidence at
`…/scratchpad/chromiq-chartread-STALE-aug5.exe` — it is the proof for Finding 6
and will vanish when the session scratchpad is cleaned, so copy it somewhere
durable if it is wanted.

### Created, untracked, safe to delete

* `native/chromiq-chartread.exe` — the rebuilt engine, staged where CI puts it
  (step 10). **Not gitignored**, so it will show up in `git status`; it must not
  be committed.
* `dist/` and `build/` — the PyInstaller output and its TOCs. `build/ChromIQWin/PYZ-00.toc`
  is the evidence for the withdrawn Finding 8.
* `.tools/llvm-mingw-20250430-ucrt-aarch64/` — the toolchain, already present
  from an earlier session. Gitignored. **Worth keeping**: without it the engine
  cannot be rebuilt on this machine, and its absence is what caused Finding 6.
* `requirements-win.txt` — regenerated by `grep -v pycups requirements.txt`,
  exactly as `build-windows.yml` does. Was already present and stale (it
  predated the CR30 branch and so lacked `pyserial` and `bleak`).
* Logs and screenshots: `pytest_win_everyday.log`, `pytest_win_gate.log`,
  `pyinstaller_win.log`, `cr30_step6.log`, `app_*.log`, `pkg_*.log`,
  `win_measure_01.png`, `win_bug_nothing_measured.png`, `win_step8_01.png`.

### Projects

`~/ChromIQ/CR30-Test` is a **copy** of Basti's `Desktop/cr30-test`, made for
this session. His Desktop original was never opened for writing and is
byte-identical to how it started. The copy now holds **7 measured patches**
(it started with 4); the original 4 were archived by the app itself to
`runs/run1/old/2026-08-30_022149/`. Nothing of his was deleted or overwritten,
and no other project was touched.

### Still running when this was written

The packaged app `dist\ChromIQ\ChromIQ.exe` may still be open. It is safe to
close.
