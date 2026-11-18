"""THE X-RITE i1Pro 2 DUAL SCAN: M0, M1 AND M2 FROM A LAMP PASS AND A UV PASS
(step 1 of the feature, 2026-11-18: the calculation only, no user interface).

An i1Pro 2 has two light sources for reflective readings: its tungsten lamp
and an ultraviolet LED. X-Rite's i1Profiler offers a "dual scan": every strip
(or patch) is read twice, once under the lamp and once under the UV LED,
after a calibration that also reads the white tile under the UV LED. From the
two readings it reports all three ISO 13655 conditions (M0, M1, M2).

This package does that calculation for ChromIQ:

* :mod:`workflow.dual_scan.model`: the formula (inputs validated, a refusal
  with a reason id instead of a guess), see its docstring for the derivation;
* :mod:`workflow.dual_scan.cut`: the UV pass of a strip cut into the lamp
  pass's patches by the instrument's ruler;
* :mod:`workflow.dual_scan.scale`: the one number the formula needs that the
  instrument does not store (the glow scale ``s``): the built-in standard
  value, and the optional refinement from one i1Profiler measurement;
* :mod:`workflow.dual_scan.reasons`: every refusal's id and the English
  sentence the later user interface step will translate.

Where the three conditions are kept afterwards is the i1Pro 3 Beta's
mechanism ("X-Rite i1Pro 3: keep M0, M1 and M2 from every scan",
:mod:`workflow.i1pro3_conditions`), extended to the i1Pro 2, never a second
one: see :mod:`workflow.dual_scan.storage`.

Specification: ``docs/design/i1pro2_dual_scan.md`` (awaiting confirmation).
"""
