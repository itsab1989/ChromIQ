# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.54: "Row speed" (Preferences > Beta, under the i1iO option): the factor's own grid and
range, in core, so Preferences and the window read it without loading any of the i1iO
code (the factor's effect: workflow/i1io/table/spot.apply_speed_factor)."""
from __future__ import annotations

import math

#: the settings key (core/settings.py)
SETTING = "i1io_table_row_speed_factor"
#: the field: 0.50 to 2.00 in steps of 0.05, default 1.00 (= ChromIQ's own choice)
DEFAULT = 1.0
RANGE = (0.5, 2.0)
STEP = 0.05


def is_one(f) -> bool:
    try:
        return abs(float(f) - 1.0) < 1e-9
    except (TypeError, ValueError):
        return True


def clean(raw) -> float:
    """The stored factor on its grid, inside its range; anything unusable is 1.00."""
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return DEFAULT
    if not math.isfinite(f):
        return DEFAULT
    f = min(RANGE[1], max(RANGE[0], f))
    return round(round(f / STEP) * STEP, 2)
