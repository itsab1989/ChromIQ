# 18 — Strip-reading design review [CR30-STRIP]

## In progress

Research started 2026-08-28. Nothing below is final until the "In progress"
marker is removed.

### Progress log (working notes, superseded by final sections)

- 2026-08-29: Read PROTOCOL.md (full), MEASUREMENT.md §1-2, 17_verify4 -T
  section, helper spot/external path.
- FACT (helper): the `-x` external path is patch-at-a-time BY CONSTRUCTION —
  `chromiq_chartread.c:2812` (one prompt, one value line, one patch), value
  parse at :3135-3183 writes exactly `scols[pix]->XYZ`, no spectral, then
  `rr=1`, `cq_emit_patch_read`, `cq_write_ti3_atomic` (autosave per patch),
  then advance. There is NO strip concept anywhere on the xtern branch —
  `xtern` forces spot mode at :2600.
- FACT (helper): the cursor is steerable — 'f'/'F'/'b'/'B'/'n'/'g' commands;
  'g' goto takes a patch LOC label (:2770-2797 label lookup over scols).
  So ChromIQ CAN feed an aligned strip: for each patch, goto loc, feed value.
  Randomised chart order is irrelevant because goto is by loc, not index.
- FACT (helper): the dE-vs-expected challenge (:3211-3227) runs AFTER the
  value is already written+autosaved, and thresholds are WERR_TH=95 /
  ACC_WERR_TH=30 (:70-71). Adjacent-patch misalignment is typically dE<30,
  so the helper CANNOT be the alignment safety net. Re-feeding a patch (goto
  + value) overwrites and re-autosaves — recovery from a bad feed exists.
- FACT (helper): -T / scan_tol is consumed only at :1209-1214 via
  `inst_opt_scan_toll` → instrument option, inside the `xtern==0` block
  (:918). It operates on NOTHING we can feed. Any consistency tolerance for
  CR30 strips must be implemented in ChromIQ, full stop.
- FACT (helper JSON): `spot_ready` carries id, loc, read, all_done AND
  `exyz` (chromiq_chartread.c:600-608). `goto_patch(loc)` exists
  (measure_manager.py:801-804), value feed is
  `{"cmd":"value","xyz":"X Y Z"}` (measure_bridge.py:504,
  chromiq_json.c:191-199). `patch_read` echoes loc, so the bridge already
  VERIFIES pairing (measure_bridge.py docstring). The feed loop a strip
  needs — goto loc, wait spot_ready(loc), send value, verify patch_read(loc)
  — is composed entirely of protocol that is live today.
- FACT (device, USB): button press pushes an unsolicited BB 01 09 header
  (device.py:225-235 doc, usb_measure.wait_for_button_header, VERIFIED
  3/3 EXP-MEAS-001/002/003) and that header is the ONLY carrier of the
  magnet-gate flag (offset 24; host-triggered headers show 0x00 gated or
  not — usb_measure.py:50-58). Consequence for the design: the press that
  starts a swipe is not just UX, it is the SAFETY GATE — host-trigger
  streaming with a capped device silently REWRITES the white calibration
  (trigger_unsafe warning, device.py:149-176, EXP-MEAS-004), and only a
  button header can prove the cap is off before streaming begins.
- FACT (EXP-018 raw, re-read): phase A 39 cycles 3.18/s, step dE median
  0.0037 max 0.0155, min step 0.0006 (never bit-identical); phase B in
  motion median 0.2747 max 6.8123, 15/38 > 1. Verdict text matches the
  brief. CAVEAT the brief omits: phase B proves readings TRACK the surface
  in motion; it does NOT prove a reading taken in motion equals the settled
  reading of the same patch (no ground truth was under it), and the
  smear arithmetic assumes integration spans the whole 315 ms cycle —
  the actual optical integration window is UNMEASURED (HYPOTHESIS).
- FACT (ChromIQ): the layout engine has full physical geometry —
  Placement.x_of/y_of, patch_rects_px, strip_rects_px, spacer_rects_px
  (workflow/layout_engine/geometry.py:168-560) — everything an alignment
  needs for engine charts. check_usable (measurement.py:178-201) refuses
  tile constants, zero runs, bit-identical repeats; usable per stream
  sample with previous=last sample.
