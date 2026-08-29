# CR30 Verify Round 3 — [CR30-VERIFY-3]

## In progress
Started 2026-08-28. Reading 14_protocol.md, 15_verify2.md, git log, 63831d67.

Read: 14_protocol.md, 15_verify2.md, full diff of 63831d67. Desk-trace of the
owner's log scenario matches the implementer's reading so far (A19 re-armed via
asked_for; A24's in-flight worker consumed press 1 → stale_loc; A19 read on
press 2; helper auto-advanced to A20; spot_ready A20 read:true all_done:false →
`on_patch_ready` sets `_awaiting_loc` then returns at the read-and-not-asked_for
gate, measure_bridge.py:256-260 — nothing armed, tab still highlights). To
verify against code: helper's advance-by-index + `n` command, tab highlight
site, worker/lock interleaving.

## FINDING 1 — BLOCKER CONFIRMED (mechanism verified, plus a second way in)
The implementer's reading of the A20 stall is CORRECT, and reproduced against
the real bridge (scratchpad/proof_a20_stall.py):
- click A19 (read) -> asked_for re-arm works (read_calls 1, rearmed [A19], value sent);
- helper records the value and advances BY INDEX (`incflag = 1`,
  chromiq_chartread.c:3181/3199 — spot value + instrument branches), NOT
  next-unread;
- spot_ready A20 read:true all_done:false -> measure_bridge.py:247 sets
  `_awaiting_loc="A20"`, :256-260 returns — 0 new read_calls, 0 signals,
  awaiting_loc='A20', 0 threads. Nothing armed, nothing said, and with no
  worker no wait_for_event pumps the loop so the press notification is not
  even DELIVERED (ble.py wait_for_event is the only pump).
- tab_measure.py:10948-10972 `_on_patch_ready` highlights loc UNCONDITIONALLY
  after bridge.on_patch_ready — the highlight lies.
- Not `_nav_target` (cleared at :246), not `_retries`, not zombie-worker state:
  the A24 drop at log 38781 is A24's still-running worker (holding
  DeviceReader._lock, measure_bridge.py:474/514) consuming press 1 ->
  `_why_not` stale_loc (:441-442), `_reading_loc` untouched ("A19" != "A24",
  :420). It leaves NO state behind; press 2 was accepted normally. The stall
  is purely the traversal-skip.
SECOND WAY IN (new): the helper's dE-sanity branch (chromiq_chartread.c:3211-
3222, werror >= WERR_TH 95, or ACC_WERR_TH 30 with accurate ref) sets
incflag=0 and re-offers the SAME patch — now rr=1 -> read:true, not asked_for
-> same silent stall on a FRESH chart (scratchpad/proof_werror_stall.py:
VERDICT SAME STALL). 14_protocol.md caveat 2 claimed the `_reading_loc == loc`
latch covers this; it does not — `_reading_loc` is cleared in `_on_reading`
(:420-421) before the helper re-offers.
Also: tests/test_cr30_can_re_read_a_patch.py::test_merely_passing_over_a_read_
patch_still_skips_it is a green test guarding exactly this bug's shape.
Helper `n`/next_unread verified: {"cmd":"next_unread"} -> 'n'
(chromiq_json.c:211-212), mirrored onto the -x line queue (:247-268), xtern
parser 'n' -> incflag=3 (chromiq_chartread.c:3097-3099) -> search starts AFTER
current pix, wraps, stops at opix (:2716-2750). all_done=false guarantees an
unread non-padding patch exists (:2802-2806) so next_unread always lands on
one — no loop. ChromIQ already sends it from the keyboard engine map
(workflow/chartread_engine.py:97) but nowhere on the CR30 path.
