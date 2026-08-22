# ChromIQ 4.1.2 on Windows — verification results, and the macOS handover

Companion to `windows_verification_4.1.2.txt` (the kick-off prompt). That
document says what to do; this one says what happened, what was fixed as a
result, and what macOS still has to answer before 4.1.2 can be tagged stable.

Verified at `v4.1.2-beta.10` (`75764688`). The fix that followed is commit
`6cfb71f5` on `perf/startup-snappiness`.

---

## Verdict

**Do not tag stable yet** — not because anything is known-broken, but because of
what is unverified. Everything betas 8–10 changed is correct on Windows. The
blocker was a first-launch fault older than this branch, now fixed; that fix has
never run on macOS.

A **beta.11** is the honest vehicle: it buys a real macOS gate and the five
human checks in §11 of the kick-off document.

---

## Environment

| | |
|---|---|
| OS | Windows 11 Home 10.0.26200, German locale, local console (not RDP) |
| Arch | **ARM64** — Git Bash reports `x86_64` under emulation; PowerShell reports the truth |
| Display | 3456×2160 at **200 %** (1728×1080 logical), VMware SVGA 3D |
| CPU / RAM | 2 cores, 4 GB |
| Python | **3.12.10 ARM64** (not the 3.13 the release builds with) |
| Git | `core.autocrlf=true` |

Two deviations from the shipping configuration, neither of which changed a
result: Python 3.12 rather than 3.13, and two cores — which is why the gate takes
22 minutes here rather than four.

**Two environment traps the kick-off document does not mention:**

* **`PYTHONUTF8=1` is required.** On a German-locale Windows box, reading app
  strings raises a real `cp1252 UnicodeEncodeError`. The gate was run with it set.
* **The startup update-check is a modal.** `ui/main_window.py:1516` schedules a
  check 3 s after the window opens and `_on_startup_update_available` calls
  `dlg.exec()`. It did *not* fire during this verification (GitHub's newest tag
  equalled the local `4.1.2-beta.10`), but it returns the moment beta.11 is
  tagged, and a modal inside an offscreen gate has no visible window.
* Minor: the document's own sanity check (`import freetype`) fails on ARM64
  because it omits `ensure_freetype_library()`. The app is fine — FreeType 2.14.3
  loads via the vendored ARM64 DLL.

---

## Gate

```
1 failed, 6620 passed, 238 skipped, 2 xfailed in 1313.94s   (Windows, beta.10)
6758 passed,  101 skipped, 2 xfailed in  257.72s            (macOS baseline)
```

Collection matched exactly — 6861 items both sides. The 138-test difference is
137 extra skips plus the single failure; no test went missing. Zero errors, no
long-path `WinError 3`, demo projects built against real Argyll.

**The single failure was not a Windows regression.**
`tests/test_no_chart_preview_guidance.py:85::test_profile_run_combo_is_readable_width`
asserted `minimumWidth() >= 120` and measured 117. Re-run with real fonts it
**passes** — it is an absolute-pixel assertion with no font guard, and Windows'
offscreen font database is empty, so the width was computed from a null font.
Same class as the document's E6. It wants `skip_without_fonts()`.

All 238 skips reconcile against Appendix B. Two appear that are not in the
catalogue, both harmless: `test_temp_cleanup.py:185` *"symlinks unavailable
(Windows without developer mode)"* and `test_scanin_dialog.py:252` *"ISO 12641-2
3-page set not in this Argyll ref/"*.

### Real fonts (§7)

```
8 failed, 97 passed in 6.71s     QT_QPA_PLATFORM=windows
```

**Six of the eight are one test bug, not a product fault.**
`tests/test_disabled_controls_look_disabled.py`'s `_brightest()` indexes
`img.pixelColor(x, y)` with `widget.geometry()` — logical coordinates — but
`QWidget.grab()` at `devicePixelRatio=2.0` returns a device-pixel image. Every
sample lands at half the intended position and reads a different row. Rendering
the widgets and looking at them shows the app is correct: disabled labels are
visibly grey, and the disabled checked checkbox correctly loses its accent.
Re-sampling with the DPR applied gives **drop = 124** in all four cases against a
threshold of 60 — exactly the "230 vs 106" the test's own docstring cites.

It has never been caught because the test is font-guarded and skips in every
offscreen gate; a 200 %-scale display is the first place it has actually run. It
would fail the same way on a Retina Mac run with real fonts.

The remaining two are genuine but cosmetic: hand-wrapped help text fills 86 % and
88 % of its card instead of >90 %, leaving a strip of empty frame. Windows font
metrics differ from macOS. Notably in the **safe** direction — text narrower than
its card, never clipped.

**This is the step that was supposed to find button-label clipping on Windows.
It found none.**

---

## The four things betas 8–10 changed

**Splash — correct, including the regression that was feared.**

| Check | Result |
|---|---|
| First visible, warm | 0.271 s |
| First visible, cold | 1.0–1.5 s |
| Size @ 200 % | 1280×800 device = **640×400 logical** |
| Size @ effective 300 % | 1920×1200 device = **640×400 logical** |
| Size @ effective 400 % | 2560×1600 device = **640×400 logical** |
| Centring | centre (1726,1078) vs screen (1728,1080) |

The double-size-with-art-in-a-quarter bug did not recur, on the machine most
likely to expose it. Never the "flash just before the main window" failure
either. **Classic splash** appears at 1.338 s against 0.279 s — **1.06 s later**,
reproducing on Windows the ~1 s `QSplashScreen.show()` cost this branch removed.
No performance claim in betas 8–10 was gate-backed, so that is worth recording.

**Composite event filter — indistinguishable from the four separate filters.**
Run with and without `CHROMIQ_SEPARATE_FILTERS=1` and diffed: tooltips at the
right, bottom, bottom-right and centre of the screen were byte-identical in both
modes and all stayed on screen; the group-box surface matched. An independent
source audit confirmed all four sub-filters act only on
`Polish`/`Show`/`StyleChange` (all in `_INTERESTING`), all four end in
unconditional `return False`, and the tuple order matches Qt's reverse-install
order. One real delta: the dispatch loop at `ui/widgets.py:1562-1567` has no
`try`, so an exception in an earlier filter now aborts the later ones — and the
Windows-specific #70 tooltip wrapper is the unguarded one doing the most
arithmetic. Latent; not observed.

**Tab pane — the feared regression does not appear.** Measured across all five
tabs in both themes, the two device rows directly under the tab bar are identical
on every tab (`#eeece8` light, `#181818` dark). Rows below differ because each
tab's content panel carries its own accent tint, by design. The only coloured
line is the selected tab's own underline.

**Log font — fixed, and the fix holds.** Widget and viewport move in lockstep:
light → bold/800, dark → normal/400, and back. No stale bold after switching.

**Timings** (`starting` → `Event loop starting`, from the app's own log):
light 3.664 / 3.572 / 3.684 s; dark 3.622 / 3.250 / 3.326 s. macOS reference
~3.0 s. No theme-dependent penalty.

**Betas 1–7 spot checks.** Clip-border branding passes: `%WINDIR%\Fonts` yields
61 families, Arial/Segoe UI/Times resolve with bold and italic, the bundled
`Inter` resolves, and rendered clip text is legible including the `·` separator.
`scanin.exe` resolves through the app's own detection, runs, and `ref/` yields 25
`.cht` templates. ArgyllCMS's x64 binaries run correctly on ARM64 under emulation.

---

## What was fixed — commit `6cfb71f5`

### The finding

On a first launch with no ArgyllCMS, the "not found" modal was **unreachable**.
The splash is `WindowStaysOnTopHint` (`WS_EX_TOPMOST`) and a modal dialog is not,
so on Windows the modal opened *under* it — measured at ~83 % covered, buttons
swallowed by the topmost splash. Clicking the splash away could not rescue it:
Qt discards mouse events to windows a modal has blocked, so `ui/splash.py`'s
click-to-dismiss — whose docstring named this exact scenario — was inert
precisely when needed. Only Alt+Tab reached it.

Root cause: `ui/main_window.py:300` → `:1610` calls `dlg.exec()` inside
`MainWindow.__init__`, i.e. `main.py:238` — before `win.show()` and before
`splash.finish(win)`, the splash's only dismissal.

And the dialog's text told **every** user, on every platform, to *"move the
folder to `/Applications`"* — a folder Windows does not have.

### The fix, in two independent halves

* **`main.py` / `ui/main_window.py`** — the modal leaves the constructor. Only
  the *dialog* is deferred; the auto-detect, the settings write and the
  status-bar warning stay exactly where they were. A `singleShot(0)` from
  `__init__` would **not** have been late enough — `_pump()` calls
  `processEvents()` and dispatches zero-timers.
* **`ui/splash.py`** — both splashes step aside for any modal via
  `WindowBlocked`/`WindowUnblocked`. Not redundant with the deferral: `_pump()`
  can dispatch `__init__`'s `_restore_last_session`, which raises a `QMessageBox`
  while the splash is still up. Qt's own `QSplashScreen` ignores `WindowBlocked`,
  so `ClassicSplash` exists to stop the "Classic splash screen" setting being the
  one place the bug survived.

The message is now per-platform, the download link is the per-OS page, and no
ArgyllCMS version is named — that would pin `3.5.0` inside a translated key and
cost 12 retranslations per release. All 12 catalogues updated.

**Measured after the fix:** splash 0.45 s → main window 3.9 s → dialog 4.1 s,
dialog frontmost and clickable, splash gone, main window behind it and disabled.

### What review caught in my own work

Three adversarial review passes found three real defects before this shipped:

1. An accidental regression: the app stopped taking the foreground on launch.
   `WA_ShowWithoutActivating` was set in the constructor rather than only on the
   re-show. Measured: `activeWindow` `PlainSplash` → `None`. Fixed.
2. A guard tested *after* its flag was cleared, so a refused re-show would have
   left the splash hidden **and** disarmed for the rest of startup. Fixed.
3. **The first draft of the new text told macOS users to use `~/Applications`
   and Linux users to unpack to `/opt/argyll`. Neither is searched** — only
   `/Applications` gets the versioned scan, and Linux has no versioned scan at
   all. That was the same bug the message exists to fix, in the two arms that
   could not be tested here. Fixed, with a test that rejects the old wording.

### Tests, and what they are worth

* `test_the_splash_steps_aside_for_a_modal_dialog` drives a **real** `exec()`.
  The pre-existing click-away test calls `mousePressEvent` directly and therefore
  stayed green for the entire life of this bug. Verified by stashing the source
  fix and keeping the tests: exactly the new ones fail.
* `test_main_actually_calls_show_startup_warnings` pins the wiring — without it,
  deleting one line leaves every splash test green while first-launch users get
  no dialog at all.
* `tests/test_argyll_not_found_dialog.py` asserts every path the message names is
  one `argyll_candidate_dirs()` actually searches. Verified it rejects the old
  wording. It cannot catch a wrong *verb* (the old Linux text named a real
  candidate but told the user to create a nested folder inside it).
* `tests/test_splash.py` now removes its application fonts on teardown — see
  below.

---

## Pre-existing problems found, not caused by this work

**The Windows gate hangs, roughly half the time.** Two of four full runs froze
near the end (98–99 %) with every worker at zero CPU and had to be killed after
20 and 39 minutes. **One of those was on completely unmodified code.** Stack
dumps point at the demo-project build shelling out to Argyll
(`tests/conftest.py:510` → `scripts/make_demo_projects.py:185`). All three
subprocess calls there *do* carry `timeout=`, so the likely cause is subtler: on
Windows, `subprocess.run(capture_output=True, timeout=…)` kills the direct child
when the timeout fires, but a **grandchild that inherited the output pipe** leaves
the reader thread blocked for ever. Run with
`--timeout=600 --timeout-method=thread` so a hang names its test.

**A font leak between test files.** `tests/test_splash.py` added six bundled
fonts to the process-global `QFontDatabase` and never removed them. An xdist
worker runs many files per process, so those fonts stayed visible to every file
that followed and silently switched off `tests/_fontcheck.py`'s
`skip_without_fonts()` guard — making text-metric tests *run* on Windows and fail
against three bundled faces instead of the system's. Which files were affected
depended on `--dist loadfile` packing, so the failures moved between runs. Fixed
in `6cfb71f5` by removing the fonts on teardown. **The causal link to the three
text-width failures seen in one run was never proven**, because the control run
that would have proven it hung.

**Three tests monkeypatch `_show_argyll_not_found_dialog` to a no-op**
(`tests/test_keyboard_shortcuts.py:33`,
`tests/test_knut_beta102_delete_project_reset.py:233`,
`tests/test_tab_styling_cache.py:25`) — module-level class mutations, not
`monkeypatch` fixtures, so they leak to every later test in the same worker.
Now dead weight, since the constructor no longer opens the dialog. Safe to delete.

---

## `windows_verification_4.1.2.txt` §4c is now stale

Step 4c describes the *old* behaviour and asks a tester whether clicking the
splash dismisses it and whether the dialog is reachable. After `6cfb71f5` the
dialog opens **after** the main window with the splash already gone, so the
question no longer applies. Left unedited deliberately — that document is Knut's
and Sebastian's, and rewriting a test procedure under its authors is their call,
not the verifier's.

---

## macOS: what has to happen before stable

1. **Run the gate.** `QT_QPA_PLATFORM=offscreen pytest --runslow -n 4`. Baseline
   for this branch was `6758 passed, 101 skipped, 2 xfailed`; expect **6763**,
   since the fix adds five tests.
2. **Confirm the load-bearing assumption.** The splash fix rests on Qt delivering
   `WindowBlocked` to the splash when a modal blocks it. Verified on Windows;
   **unverified on macOS**, where Cocoa handles modal sessions differently. Move
   Argyll aside, clear preferences, launch, and check the main window appears
   first and the dialog is in front and clickable. If the assumption fails there,
   the splash simply will not hide — the same as before the fix, not worse.
3. **Re-run §4 and §8b of the kick-off document.** They measured startup
   behaviour that this fix has since changed, so those numbers no longer describe
   the shipping code on any platform.
4. **Do §11's five human checks** — particularly item 3 (a long tooltip near the
   right screen edge, which could not be triggered reliably by automation) and
   item 4 (German button labels).
5. **Test §9a** — Create Chart settings surviving a build and the load that
   follows. **There is no automated test for this anywhere in the repo**, which is
   why it was on the manual list. Build in Guided against a target holding
   *different* stored settings and check the module, instrument, paper size,
   layout, engine switch, its calibration, gamut count and stamp flag all survive.
6. **Skim the translations.** All 48 new strings are the verifier's work. A
   reviewer checked placeholders, HTML tag counts and button labels mechanically
   across all 12, but no native speaker has read them.

## What could not be tested here

* macOS, at all, for the changes made.
* Tooltip word-wrap on a real mouse hover — programmatic `QToolTip.showText`
  wrapped inconsistently, *identically in both filter modes*, and a plain
  `QPushButton` with a plain `setToolTip` in a throwaway window showed no tooltip
  either, so the instrument was unreliable rather than the app.
* Multi-monitor and mixed DPI. One virtual screen only.
* Real Windows display-scale changes — `QT_SCALE_FACTOR` was the proxy.
* Python 3.13.
* Any hardware path: no instrument, printer or scanner attached.
* A genuinely pristine machine — ArgyllCMS and a populated settings store were
  already present, so the first-run state was reconstructed by renaming
  `%LOCALAPPDATA%\ArgyllCMS` aside and clearing the settings key (both restored
  afterwards). Faithful, but reconstructed.
