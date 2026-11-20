# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The i1Pro 2's quiet time before a reading (Preferences > Beta, under the
lights option; ChromIQ 4.3.52).

The owner, 2026-11-20: "could we allow the user to set the timing himself
with recommendations of what was measured inside i1profiler and leave more
room than that to the bottom end?". The driver keeps every measurement back
until this long after the instrument's light last changed (RULE B of 4.3.37,
native/instlib/i1pro_imp.c ``cq_lights_quiet``). 2.1 s is 4.3.37's own value
and stays the default: the study of 2026-11-20 (ChromIQ-work
2026-11-20_pulse452b/quiet_study.txt) found i1Profiler waiting far less
(0.37 s by hand, 0.01 s before a calibration) but nothing measured with
ChromIQ's own driver between 25 ms (two readings in three lost) and 2.1 s.
The range goes down to 0, below everything recorded, so a user can try.
"""
from __future__ import annotations

#: 4.3.37's quiet time, the default (``CQ_LIGHTS_QUIET_MS``)
DEFAULT_S = 2.1
DEFAULT_MS = 2100
#: the range offered (the helper takes 0 to 10000 ms, CQ_LIGHTS_QUIET_MAX_MS)
MIN_S = 0.0
MAX_S = 10.0

#: what i1Profiler 3.8.6 was recorded doing on a tester's i1Pro 2 (the study):
#: light change -> the next measurement, by hand (before the return pass of a
#: dual scan, 15 cases) and before a calibration (5 cases); every reading came
RECORDED_HAND_MIN_S = 0.37
RECORDED_HAND_TYPICAL_S = 0.46
RECORDED_CALIBRATION_S = 0.01


def to_ms(value) -> int:
    """The setting as the helper's whole milliseconds; anything that is not a
    number from 0 to 10 s gives the default."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return DEFAULT_MS
    if not (MIN_S <= v <= MAX_S):
        return DEFAULT_MS
    return int(round(v * 1000.0))
