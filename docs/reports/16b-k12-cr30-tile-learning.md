# K12 · CR30 over Bluetooth — "I have pressed it" leads nowhere

STATUS: for challenge — evidence only, no code written

Kept in its OWN file: an agent is appending to
`16-knut-beta5-findings.md`, and an edit of mine to that file destroyed this
section once already. Two writers, one file.

Basti's own hardware, 2026-08-31. Live log `~/Library/Logs/ChromIQ/chromiq.log`
— the copy on his Desktop stops at 18:04 and does not contain these sessions.

**He ran it twice, and the difference between the runs IS the finding:**

> *"in the second session i have clicked the remind me later button for this.
> in the session before i tried it when it failed. i then force closed the app"*

## The session that FAILED — 22:11, he CONFIRMED the press

```
22:11:06,834  tile_learning: no tile signature learned for unit ble:FFB32AD2-…
22:11:06,834  measure_bridge: CR30: opened over ble
22:11:07,641  device: CR30 BLE: calibration white answered in 0.81 s
              ←—— 34 SECONDS, NOT ONE LOG LINE ——→
              (the tile window is up; he presses the instrument's button and
               clicks "I have pressed it")
22:11:41,954  ArgyllRunner: cleanup complete        ← he force-quit the app
```

* **No black calibration ever ran** — the sequence stopped dead after white.
* **Confirming produced no log line of any kind.** It never reached
  `workflow/cr30/tile_learning.py`.
* He had to kill the app to get out.

## The session that WORKED — 22:12, he chose "Remind me later"

```
22:12:27,776  tile_learning: no tile signature learned for unit ble:FFB32AD2-…
22:12:28,583  calibration white answered in 0.81 s
22:12:38,325  calibration black answered in 0.81 s      ← the flow CONTINUES
22:12:40,620  chromiq-chartread started (390 patches)
22:12:52 … 22:13:34   read_patches 1,2,3,4,5            ← presses arrive normally
```

**So: "Remind me later" continues the sequence correctly. "I have pressed it"
stops it, silently, with no way out but killing the app.** That is a hang on
the happy path of a feature shipped for CR30 owners.

## NOT a fault — the A6 wait
The 180 s wait at A6 in the second session, and the cancel at 22:19, are
correct behaviour. Basti: *"the a6 thing is simply because i forgot to stop the
measurement and did not click anything anymore i think"*. He walked away; the
instrument waited, said so, re-armed, and stopped cleanly when cancelled.
**Do not spend time on it.**

## What to establish
1. What does "I have pressed it" DO on the BLE path? The learner's contract is
   that USB proves a tile by the magnet gate flag while **BLE proves it by two
   bit-identical presses**. Can that path complete at all, and what does it do
   while waiting? A window silently waiting for a SECOND press would look
   exactly like this.
2. Why did the sequence not continue to the black calibration — is the learn
   awaited in a way that blocks the rest of the calibration?
3. Is the learn keyed to the same unit id the guard reads back
   (`ble:<address>`)? Known trap: the id came from `device_id` on USB and the
   advertised name on BLE, so a tile learned on one transport did not arm the
   guard on the other.
4. Does anything time out, or would it wait for ever? He force-quit, which
   suggests the latter.

## Hardware
Basti has granted use of his CR30 (*"you can use my instrument… it is for
testing and developing only"*). An agent still **cannot press the physical
button**, and a host trigger is NOT the same event as a press — that is exactly
why `M-CR30-TRIGGER-NOT-ARMED` exists. Press-dependent steps must be written
out for him to run. A capped trigger performs a real white calibration: never
speculatively, never in a loop, close whatever you open, log every frame sent,
and stop on anything unexpected rather than attempting recovery.
