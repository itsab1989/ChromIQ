# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The waiting times around an i1Pro / i1Pro 2 reading, as ONE table (4.3.53).

The owner, 2026-11-20: "for the waiting times just make it so it does not take
a day to change them again if the times then are too short", and then: "cant
you repurpose the one waiting time option to all of the waiting times ... so
they can be changed by the users directly".

Each wait used to be a number compiled into the chart-reading helper or its
copy of ArgyllCMS's driver. Now the app passes each one at Start (the helper's
argument, in ms), so changing one is:

* for a developer: the ``default_s`` below (one number, nothing native);
* for a user: Preferences > Beta (the fields under the i1Pro 2 lights, and the
  two lamp waits, i1Pro and i1Pro 2, after 4.3.54);
* for a tester without the window: one line in the settings file, the key
  below in seconds (``i1pro_lamp_off_s=1.06``).

Without the argument the helper keeps its compiled value, which is 4.3.52's
(``native/instlib/i1pro_imp.c`` LAMP_OFF_TIME 1500 and CQ_LIGHTS_BLUE_QUIET_MS
370, ``native/chartread_helper/chromiq_chartread.c`` CQ_LIGHTS_BLUE_AFTER_MS
550, CQ_LIGHTS_QUIET_MS 2100). The defaults here equal those in 4.3.53, so
nothing changes for anybody. See docs/dev_instrument_waits.md.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Wait:
    name: str          #: the app log's name
    key: str           #: the settings key, in seconds (the Preferences field)
    flag: str          #: the helper's argument, in whole milliseconds
    default_s: float   #: THE default: change it here and only here
    max_s: float       #: the largest value taken (the helper takes the same)


#: the lights' quiet time before every reading and calibration (4.3.37, RULE B)
LIGHTS_QUIET = Wait("lights_quiet", "i1pro2_lights_quiet_s", "--lights-quiet-ms", 2.1, 10.0)
#: after the dual scan's blue light, before the second pass (4.3.52 fix round)
BLUE_QUIET = Wait("blue_quiet", "i1pro2_blue_quiet_s", "--lights-blue-quiet-ms", 0.37, 10.0)
#: from the end of a dual scan's first pass to the blue light (4.3.52)
BLUE_AFTER = Wait("blue_after", "i1pro2_blue_after_s", "--lights-blue-after-ms", 0.55, 5.0)
#: ArgyllCMS's lamp wait before every dark reading of an ORIGINAL i1Pro (rev A
#: to D and rebadged ones); until 4.3.54 also of the i1Pro 2. ArgyllCMS's value:
#: no vendor recording of this instrument has been evaluated for it
LAMP_OFF = Wait("lamp_off", "i1pro_lamp_off_s", "--lamp-off-ms", 1.5, 5.0)
#: the same for an i1Pro 2 (also the ES-2000 and the i1Basic Pro 2), after 4.3.54
#: (the owner's decision of 2026-11-21): i1Profiler was recorded at 1.059 s from
#: lamp off to the next dark reading of an i1Pro 2 (RECORDED_LAMP_OFF_S), rounded
#: UP on the fields' 0.05 s grid. A tester's i1Pro 2 dual scans with real gaps of
#: 1.03 to 2.24 s showed no effect (work folder 2026-11-21_nelson_bluelight_confirm,
#: analysis sections 7 to 9). The helper's compiled fallback is the same number
#: (i1pro_imp.c CQ_LAMP_OFF_TIME_I1PRO2 1100; tests/test_lamp_wait_per_model.py)
I1PRO2_LAMP_OFF = Wait("lamp_off_i1pro2", "i1pro2_lamp_off_s", "--lamp-off-ms-i1pro2", 1.10, 5.0)

WAITS: "tuple[Wait, ...]" = (LIGHTS_QUIET, BLUE_QUIET, BLUE_AFTER, LAMP_OFF, I1PRO2_LAMP_OFF)

#: the helper's caps word for --lamp-off-ms-i1pro2 (helper 2026-11-21d). A helper
#: without it gets --lamp-off-ms alone, which then applies to the i1Pro 2 too (4.3.54)
CAP_I1PRO2 = "lamp_off_i1pro2"

MIN_S = 0.0
#: the Preferences fields: two decimals, steps of 0.05 s (as 4.3.52's)
DECIMALS = 2
STEP_S = 0.05

#: what X-Rite's i1Profiler was recorded doing (for the help texts; each
#: number checked at its source, see docs/dev_instrument_waits.md)
#: blue light -> the second pass's trigger, from the END of the light command
#: (as ChromIQ counts): shortest 0.308 s (re-review decode, 23 blues)
RECORDED_BLUE_QUIET_END_S = 0.31
#: ...and from its START (the study's count): 0.372 to 1.389 s, 15 of 15
RECORDED_BLUE_QUIET_LOW_S = 0.37
RECORDED_BLUE_QUIET_HIGH_S = 1.39
#: first pass's last data -> the blue light: 0.531-0.679 s at normal speed
RECORDED_BLUE_AFTER_LOW_S = 0.53
RECORDED_BLUE_AFTER_HIGH_S = 0.68
#: lamp off -> the next dark reading, i1iO table spot readings (R12): 1.059 s
RECORDED_LAMP_OFF_S = 1.06
#: 4.3.53 fix round (waits review S1): lamp data -> the dark trigger in i1Profiler's DUAL
#: readings: 0.13-0.18 s on table dual rows, 0.11-0.18 s on dual spots (RE_REVIEW_BRIEF of
#: 2026-11-18, cq_i1pro2_dual.h); whether it uses that dark as ArgyllCMS does is not known
RECORDED_LAMP_DUAL_LOW_S = 0.11
RECORDED_LAMP_DUAL_HIGH_S = 0.18
#: the table's own scan waits, which this field does not reach (native/instlib/cq_tscan.h
#: CQ_TSCAN_LAMPOFF_MS, cq_i1pro2_dual.h CQ_TDUAL_DARK_AFTER_LAMP_MS)
TABLE_SCAN_LAMP_OFF_S = 1.07
TABLE_DUAL_DARK_AFTER_LAMP_S = 0.17


def seconds(wait: Wait, value) -> float:
    """A stored or typed value on the fields' grid; anything that is not a
    number from 0 to ``wait.max_s`` gives the default."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return wait.default_s
    if not (MIN_S <= v <= wait.max_s):      # also refuses nan
        return wait.default_s
    return round(v, DECIMALS)


def to_ms(wait: Wait, value) -> int:
    """The helper's whole milliseconds (the default for anything unusable)."""
    if not is_usable(wait, value):
        return int(round(wait.default_s * 1000.0))
    return int(round(float(value) * 1000.0))


def is_usable(wait: Wait, value) -> bool:
    """True when *value* is a number in range (a stored value that is not is
    replaced by the default, and the log says so)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return MIN_S <= v <= wait.max_s


def from_settings(get) -> "dict[str, int]":
    """Every wait in ms from a settings ``get`` (AppSettings.get or a dict's
    get); a missing key or an unusable value gives the default."""
    return {w.name: to_ms(w, get(w.key, w.default_s)) for w in WAITS}


def helper_args(ms: "dict[str, int]", *, lights: bool, i1pro2: bool = False) -> "list[str]":
    """The helper's arguments for a helper whose caps name
    "instrument_waits": every wait that applies, ALWAYS, also at its
    default, so that the number in this file is the one in use (a wait left
    out would fall back to the helper's compiled one). ArgyllCMS's lamp wait
    applies to every reading; the three lights waits only with the lights
    option. *i1pro2*: the helper takes the i1Pro 2's own lamp wait
    (CAP_I1PRO2); without it the i1Pro 2 waits ``--lamp-off-ms`` as before."""
    out = ["--lamp-off-ms", str(ms[LAMP_OFF.name])]
    if i1pro2:
        out += ["--lamp-off-ms-i1pro2", str(ms[I1PRO2_LAMP_OFF.name])]
    if lights:
        out += ["--lights-quiet-ms", str(ms[LIGHTS_QUIET.name]),
                "--lights-blue-quiet-ms", str(ms[BLUE_QUIET.name]),
                "--lights-blue-after-ms", str(ms[BLUE_AFTER.name])]
    return out


def log_fields(ms: "dict[str, int]") -> "dict[str, str]":
    """The app log's fields: every wait in seconds, marked when not the
    default (``lamp_off_s=1.06(changed)``)."""
    out = {}
    for w in WAITS:
        s = ms[w.name] / 1000.0
        text = f"{s:g}"
        if ms[w.name] != int(round(w.default_s * 1000.0)):
            text += "(changed)"
        out[f"{w.name}_s"] = text
    return out


def lamp_wait_for(model: str, ms: "dict[str, int]", *, i1pro2_taken: bool) -> "tuple[str, int] | None":
    """Which lamp wait applies to the instrument the helper reported (its
    ``instrument`` event's model), for the app log: ("i1pro2" | "i1pro",
    ms), or None for any other instrument (it has no such wait). An i1Pro 2
    with a helper that did not take the i1Pro 2's own value waits the
    i1Pro value, as up to 4.3.54."""
    m = str(model or "").lower().replace(" ", "")
    if not m.startswith("i1pro") or m.startswith("i1pro3"):
        return None
    if m.startswith("i1pro2"):
        if i1pro2_taken:
            return "i1pro2", ms.get(I1PRO2_LAMP_OFF.name, int(round(I1PRO2_LAMP_OFF.default_s * 1000)))
        return "i1pro2(i1pro_value)", ms.get(LAMP_OFF.name, int(round(LAMP_OFF.default_s * 1000)))
    return "i1pro", ms.get(LAMP_OFF.name, int(round(LAMP_OFF.default_s * 1000)))
