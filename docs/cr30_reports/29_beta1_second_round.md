# Second round of fixes — everything [CR30-B2] found, and Basti's asks

2026-08-30, after `28_beta1_challenge2.md`. The challenge found **no hard
blocker**: it could not fault the `saw_reply` fix, the `keep_bridge` core, W9,
W3 or W7. What follows is its two should-fixes, the edge it suspected, and the
things Basti asked for while it ran. Every fix below has a test proved to fail
against the fault.

## The root cause under both magnet dead ends

`resume_after_magnet` answered **True when there was nothing to resume**
(`if not self._stopped: return True`). That single line is why both faults could
exist: "not stopped" is exactly the state a *rebuilt* bridge is in, so the tab
took the True at face value and printed "Carrying on. Read the highlighted patch
again" over a session with no reader in it.

It now answers honestly in both directions — True only when a patch is genuinely
being read. That closes the challenge's suspected edge (the helper dying while
the magnet window is up) at its source rather than by guarding each caller.

## B2-a — "Keep measuring" after a magnet

`_end_session(None)` is deliberately a no-op, so declining to end left the
session stopped with nothing armed and nothing on screen: the same dead end,
through the other door.

**Resuming would have been the wrong fix.** The white reference is still
overwritten — that is why the session stopped, and it stays true however the
user answers a window about *ending*. So "keep measuring" is taken at its word:
the session is not ended, the log says plainly that nothing can be read until
the calibration is retaken, and the remedy comes back on screen. The handler is
now a loop with exactly two ways out — recalibrate, or really end it — because
there are only two, and offering a third door would mean pretending otherwise.

## B2-b — the window that outlived the app's own patience

After the last retry, `read_gave_up` fires and nothing is armed, but the
read-failure window stood there saying "press the button on the instrument
again" — beside a log line saying ChromIQ had given up. Closed now.

## The suspected edge, confirmed and fixed

The window promises "This window will close by itself when the reading comes
through", and that promise is why it asks nothing of the user. It rode on the
next prompt naming a *different* patch — but on the chart's LAST patch the
helper re-offers the same loc with `all_done`. The decision is now its own
method (`_close_read_failed_window_if_moved_on`), which also made it testable
for what it is; a separate test asserts `_on_patch_ready` still drives it, so
the two cannot drift apart.

## Windows driver safety — the part that could not wait

The challenge found two hazards that are **live the moment CR30 support ships**,
neither needing a code change to reach:

1. **The Zadig guidance tells the user to find their instrument and give it
   WinUSB.** That is right for every colorimeter ChromIQ lists and catastrophic
   for a CR30: it is reached through a COM port, and WinUSB removes it. A CR30
   owner with driver trouble is precisely the person who follows those steps.
   All three places that steer someone to Zadig now carry the warning, and a
   test counts the steers against the warnings so a fourth cannot be added
   silently.
2. **`install_winusb` now refuses a vendor-serial device outright**, from a
   structurally separate `VENDOR_SERIAL_DEVICES` table that no existing code
   path can feed to the installer. This matters because the dialog's "Reinstall"
   runs it over *every* detected device — one wrong table entry would brick a
   CR30 while its owner repaired a different instrument.

⚠ On a non-Windows host the direct refusal test passes for the wrong reason
(wdi-simple is absent, so it returns False anyway). Proved by removing the
guard: only the *ordering* test went red. That test is the load-bearing one and
its docstring says so.

The rest of the challenge's design — a "connected but no working driver" state
and a Get-the-driver action — is not implemented. It is Windows-only, touches
§M, and the changelog and `docs/cr30_platform_support.md` tell the user what to
install in the meantime, which is what Basti said would keep it off the blocker
list.

## Asked for directly, while the challenge ran

* **The tick beside step 1 is gone.** *"i would read it as done although it is
  not yet done in the first window"* — and he is right: in the white window that
  step is the one he is about to take.
* **The current-step bar is the Measure tab's own green** (`#56d6a5`, and
  `#0f7a5a` on a pale ground, the darker green that theme already uses for
  measure text). These windows belong to that tab.
* **The bar itself** replaced an underline, because the challenge confirmed on
  screen what was only suspected: under the dashed "pointing at nothing" line, a
  solid marker reads as *a floor beneath the emptiness*. The solid line is now
  drawn only where the instrument is genuinely resting on something.
* **Bluetooth calibration speed**, now that he has asked for it. The earlier fix
  stopped us waiting *past* the answer; it did nothing about not *looking* for
  it until ~1.1 s had passed (0.4 s drain + 0.35 s settle + 0.35 s to the first
  poll) for a device measured at ~250 ms. The calibration now polls twenty times
  at 0.10 s instead of six at 0.35 s — the ceiling is deliberately unchanged, so
  a slow link has no less time than before.

  **The 0.4 s drain in front of it is untouched**: it flushes stragglers that
  would otherwise shift every offset in the next reply, which once produced
  fifteen garbage readings, and a calibration can happen mid-session. Shortening
  it needs a measurement on hardware, not a guess.

  **His other gap is still open and is not this.** The first Bluetooth
  connection of a session is made when he presses Calibrate, and nothing on
  screen says anything is happening. That is a design change — connect earlier,
  off the critical path — and it cannot be measured from here while the unit is
  on USB. It needs his approval and a measured plan, not another guess.

## Still open, deliberately

W4 (Letter help card), W6 (helper freshness in a source checkout), the standing
backlog, the 69 pre-existing Windows failures, and the §M question in `27`:
three CR30 messages are shown in windows while their wording is unapproved, two
of them because Basti asked for those windows. That inconsistency should be
settled deliberately rather than by accumulation.
