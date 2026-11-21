# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""THE i1Pro 2 DUAL SCAN ON THE i1iO 2 TABLE (2026-11-18): A FIRST TRY, not yet tried on a real
table.

The owner's ruling (18 Nov 2026): "you have the commands so you will do patch by patch and strip
mode so it can be tried. as long as there is no chance for physical harm of the table this is ok
so we can collect data". Both modes use only what the volunteer recorded from i1Profiler 3.8.6
doing a dual scan on his table (private analysis of 18 Nov 2026):

* PATCH BY PATCH: no new table line at all. Per patch the helper's own dual spot reading (the
  hand dual scan's, ``chromiq_dualdev.c`` (b)): the lamp reading, then on the same spot the UV
  half (dark + UV-LED readings, the volts). Each row's reader takes up the dual tile the
  calibration kept for this white (``--dual-table``), because the arm stands over the sheet.
* ROWS: each row twice on the same line, as recorded: the lamp pass forward at 132, then
  straight back with the UV LED at 132 (``scan.run_row(uv_pass=True)``; the ONE path to the
  fire is the same code for both passes). The table's position log (y1-y5) is NOT asked for:
  ChromIQ cuts both passes by position (:func:`cut_dual`), which the recordings show to work
  (M2 0.012-0.022 dE00 against i1Profiler's own with a 1.5 mm clean edge). Every reading of
  both passes is kept in the session folder, so the cut can be made again.

THE MATHS STAY IN THE HELPER. The instrument's factory tables (kA, kD) never leave it: the app
cuts both passes into patches and hands the lamp and UV values per patch to the helper
(``tscan_dual_compute``), which proves the UV pass belongs to this row (the hand dual scan's
pairing check) and writes M1 / M2 per patch.

Nothing here runs unless the Measure tab's dual scan applies (both Beta switches on, a helper
with ``i1io_table_dual``): :class:`DualSetup` is None otherwise, and the table job is the
released one, line for line.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

from . import placement as pl
from . import scan as sc
from . import spot as sp
from . import strip as stp

#: the helper's capability word (helper 2026-11-18e)
CAPABILITY = "i1io_table_dual"
#: what every dual measurement file of the table says it was cut by, besides strip.CUT_BY
DUAL_CUT_BY = "position, dual row (first try)"
CONDITIONS = ("M1", "M2")


@dataclass(frozen=True)
class DualSetup:
    """What START decided about the dual scan on the table (``workflow.dual_scan.session``'s
    plan, reused): the helper's --dual-* arguments, the factor, the person's choice."""
    args: "tuple[str, ...]"
    scale: float
    source: str = "standard"
    chosen: str = "M0"
    white: str = "table"

    def spot_args(self, condition_dir: str, table_white: str) -> "list[str]":
        """The patch-by-patch reader's arguments: the hand dual scan's own, the white of the
        tile the dual calibration was made on, and the table's --dual-table."""
        out = []
        it = iter(self.args)
        for a in it:
            if a == "--dual-white":
                next(it, None)
                continue
            out.append(a)
        return out + ["--dual-white", table_white, "--dual-table", "--condition-dir",
                      str(condition_dir)]

    @property
    def scan_args(self) -> "list[str]":
        return ["--i1io-table-dual"]


def white_for_place(place: "str | None") -> str:
    """The dual scan's white record for the tile the calibration was made on."""
    return "instrument" if place == "own tile" else "table"


class DualPass:
    """The table-scan reader as one PASS of a dual row sees it (scan.run_row's ``inst``): it
    arms and fires exactly that pass; the lamp pass also makes the recorded lights-off."""

    def __init__(self, scan, which: str):
        if which not in ("lamp", "uv"):
            raise ValueError(which)
        self.scan, self.which = scan, which

    def alive(self) -> bool:
        return self.scan.alive()

    def lights_off(self) -> dict:
        if self.which != "lamp":
            # never recorded before the UV pass: run_row(uv_pass=True) never asks for it
            return {"event": "refused", "why": "no lights-off before the UV pass"}
        return self.scan.lights_off()

    def arm(self, n: int, wait_ms: int = 3000) -> dict:
        return self.scan.arm(n, wait_ms, pass_=self.which)

    def fire(self, n: int, patches: int, name: str) -> bool:
        return self.scan.fire(n, patches if self.which == "lamp" else 0, name)

    def poll(self, name):
        return self.scan.poll(name)

    def wait(self, names, timeout):
        return self.scan.wait(names, timeout)


# ---- the cut ---------------------------------------------------------------------------------

@dataclass
class DualCut:
    ok: bool
    reason: str = ""
    lamp: list = field(default_factory=list)       # per patch, 0..1
    uv: list = field(default_factory=list)         # per patch, lamp-white units
    wavelengths: list = field(default_factory=list)
    info: dict = field(default_factory=dict)


def _mean(rows):
    n = len(rows)
    return [sum(r[j] for r in rows) / n for j in range(len(rows[0]))]


def _uv_patch_order(lamp, uv):
    """The UV pass's patches in the lamp pass's order (both plans hold the same patches)."""
    by = {q.loc: i for i, q in enumerate(uv.patches)}
    return [by[q.loc] for q in lamp.patches]


def _dual_windows(lamp, uv, nl, nu, edge):
    wl_ = sc.windows(lamp, sc.MOTION_START_AFTER_LAMP_S, nl, edge_mm=edge)
    wu_ = sc.windows(uv, sc.UV_MOTION_START_AFTER_TRIGGER_S, nu, edge_mm=edge,
                     first_reading_s=sc.UV_FIRST_READING_AFTER_TRIGGER_S)
    order = _uv_patch_order(lamp, uv)
    return wl_, [wu_[k] for k in order]


def cut_dual(lamp, uv, lamp_rows, uv_rows, edges=None, wavelengths=None,
             uniform_row: bool = False) -> DualCut:
    """Both passes of a dual row cut into the row's patches BY POSITION (the move's own profile,
    each pass's recorded first-reading delay and motion start, the dual row's clean edge: the
    widest of ``scan.DUAL_EDGES_MM`` that leaves every patch ``scan.DUAL_MIN_READINGS`` in both
    passes). Refused (nothing guessed) when a window lies outside a pass's readings, holds fewer
    than that at the narrowest edge, or the lamp pass's window is not on one colour. The UV pass
    is judged later by the helper (whether it belongs to this row)."""
    if len(lamp_rows) < lamp.N or len(uv_rows) < uv.N:
        return DualCut(False, "strip_fewer_readings_than_planned",
                       info={"lamp": len(lamp_rows), "uv": len(uv_rows), "planned": lamp.N})
    for edge in (edges or sc.DUAL_EDGES_MM):
        wl_, wu = _dual_windows(lamp, uv, len(lamp_rows), len(uv_rows), edge)
        counts_l = [i1 - i0 for i0, i1 in wl_]
        counts_u = [i1 - i0 for i0, i1 in wu]
        if min(counts_l + counts_u, default=0) >= sc.DUAL_MIN_READINGS:
            break
    info = {"lamp_windows": wl_, "uv_windows": wu, "lamp_readings_per_patch": counts_l,
            "uv_readings_per_patch": counts_u, "edge_mm": edge,
            "lamp_motion_start_s": sc.MOTION_START_AFTER_LAMP_S,
            "uv_motion_start_s": sc.UV_MOTION_START_AFTER_TRIGGER_S,
            "uv_first_reading_s": sc.UV_FIRST_READING_AFTER_TRIGGER_S}
    if min(counts_l + counts_u, default=0) < sc.DUAL_MIN_READINGS:
        return DualCut(False, "strip_patch_too_few_readings", info=info)
    L = [_mean(lamp_rows[i0:i1]) for i0, i1 in wl_]
    U = [_mean(uv_rows[i0:i1]) for i0, i1 in wu]
    uni = [max((abs(a - b) for r in lamp_rows[i0:i1] for a, b in zip(r, v)), default=0.0)
           for (i0, i1), v in zip(wl_, L)]
    info["uniformity"] = [round(u, 5) for u in uni]
    if max(uni, default=0.0) > sp.STRIP_UNIFORMITY_MAX:
        bad = [q.loc for q, u in zip(lamp.patches, uni) if u > sp.STRIP_UNIFORMITY_MAX]
        return DualCut(False, "strip_patch_not_on_one_colour", info=dict(info, patches=bad))
    if not all(math.isfinite(v) for row in L + U for v in row):
        return DualCut(False, "strip_patch_implausible", info=info)
    # 4.3.54: the row placement check on the LAMP pass (a veto only; see _placement)
    why = _placement(lamp, lamp_rows, wl_, wavelengths, info, uniform_row)
    if why:
        return DualCut(False, why, info=info)
    return DualCut(True, "", L, U, info=info)


def cut_lamp_only(lamp, lamp_rows, edges=None, wavelengths=None,
                  uniform_row: bool = False) -> DualCut:
    """4.3.50 (Basti's rule of 19 Nov 2026, as by hand): the LAMP pass of a dual row alone, cut
    into the row's patches by position, for a row whose second pass (UV) failed or was refused:
    the row then keeps M0 only. The same windows, edges and checks as :func:`cut_dual`'s lamp
    half (the widest clean edge that leaves every patch ``scan.DUAL_MIN_READINGS``, one colour
    per window, finite values); refused (nothing guessed) otherwise. ``uv`` stays empty."""
    if len(lamp_rows) < lamp.N:
        return DualCut(False, "strip_fewer_readings_than_planned",
                       info={"lamp": len(lamp_rows), "planned": lamp.N})
    counts: "list[int]" = []
    wl_: list = []
    edge = None
    for edge in (edges or sc.DUAL_EDGES_MM):
        wl_ = sc.windows(lamp, sc.MOTION_START_AFTER_LAMP_S, len(lamp_rows), edge_mm=edge)
        counts = [i1 - i0 for i0, i1 in wl_]
        if min(counts, default=0) >= sc.DUAL_MIN_READINGS:
            break
    info = {"lamp_windows": wl_, "lamp_readings_per_patch": counts, "edge_mm": edge,
            "lamp_motion_start_s": sc.MOTION_START_AFTER_LAMP_S, "lamp_only": True}
    if min(counts, default=0) < sc.DUAL_MIN_READINGS:
        return DualCut(False, "strip_patch_too_few_readings", info=info)
    L = [_mean(lamp_rows[i0:i1]) for i0, i1 in wl_]
    uni = [max((abs(a - b) for r in lamp_rows[i0:i1] for a, b in zip(r, v)), default=0.0)
           for (i0, i1), v in zip(wl_, L)]
    info["uniformity"] = [round(u, 5) for u in uni]
    if max(uni, default=0.0) > sp.STRIP_UNIFORMITY_MAX:
        bad = [q.loc for q, u in zip(lamp.patches, uni) if u > sp.STRIP_UNIFORMITY_MAX]
        return DualCut(False, "strip_patch_not_on_one_colour", info=dict(info, patches=bad))
    if not all(math.isfinite(v) for row in L for v in row):
        return DualCut(False, "strip_patch_implausible", info=info)
    why = _placement(lamp, lamp_rows, wl_, wavelengths, info, uniform_row)
    if why:
        return DualCut(False, why, info=info)
    return DualCut(True, "", L, [], info=info)


def _placement(lamp, lamp_rows, windows, wavelengths, info, uniform_row=False) -> str:
    """4.3.54: THE ROW PLACEMENT CHECK (placement.py) on a dual row's LAMP pass, the same veto
    as a strip row's: the values stay the cut's own; the row is refused (the strip row's
    reason) when the lamp readings do not confirm every patch's window. The lamp pass is the
    pass the study measured (its 132 mm/s rows ARE the recorded dual rows' lamp passes; at the
    dual row's 1.5 mm edge it caught a recorded lamp pass whose cut took in an edge reading,
    1.23 dE00). The UV pass is NOT checked by it: its readings are the LED light the patch
    reflects, for which the study measured no stable-run threshold; it keeps its own timing
    check against the chart (uv_timing_fit). Returns the reason, or "" when confirmed."""
    check = pl.check_row(lamp, lamp_rows, windows, wavelengths, uniform_reference=uniform_row)
    info["placement"] = check
    if check.get("confirmed"):
        return ""
    info["loc"] = check.get("patch") or ""
    return stp.PLACEMENT_REASON


def lamp_timing(lamp, lamp_rows, wavelengths=None) -> dict:
    """4.3.50: the lamp pass's own timing verdict (:func:`uv_timing_fit`'s lamp half), for a
    lamp pass kept without its UV pass."""
    if not lamp.patches or not lamp_rows:
        return {"lamp": None, "lamp_checked": False, "lamp_refuse": False,
                "lamp_why": "no readings"}
    sl = _band_means(lamp_rows, wavelengths, (380.0, 730.0))
    lf = _layout_fit(lamp, sl, sc.FIRST_READING_AFTER_LAMP_S, sc.MOTION_START_AFTER_LAMP_S)
    return dict({"lamp": lf}, **_judge_lamp(lf))


# ---- the UV pass's timing (safety review of 2026-11-19, SHOULD-2) --------------------------------
#
# A UV pass whose motion started 2 to 4 readings (1.3 to 2.6 mm) away from where the cut assumes
# passes the helper's pairing check: the shift stays inside the 1.0-1.5 mm clean edge, so the
# per-patch MEANS barely move (median |ratio - 1| 0.007 against 0.008) while the windows' edges
# already take in the neighbouring patch, and M2 is off by up to 2.7 dE00 (review, recorded rows).
# No check on the cut values can see that; the stream of readings can.
#
# THE CHECK: the UV pass's readings at 380-400 nm (where nothing glows: the LED light the patch
# reflects) are laid over the chart's own patches for every UV motion start within +-UV_FIT_SPAN
# readings of the assumed one, and the start is taken whose readings are flattest inside the
# patches (the share of the readings' variance the patches explain, R squared, over each patch's
# middle: its half length less half the aperture). A pass whose best start lies
# UV_FIT_REFUSE_READINGS or more away from the assumed one is refused (``uv_pass_timing_off``)
# when the fit is sure of it: R squared at the best start beats the assumed start's by at least
# UV_FIT_MIN_GAIN (a patch edge really lies where the assumed windows are). A row whose patches
# hardly differ at 380-400 nm, or whose edges do not move R squared, cannot show its timing (and
# a shift could then hardly change its M2): not judged, said in the row's record.
#
# WHY AGAINST THE CHART AND NOT AGAINST THE LAMP PASS: fitted against the lamp pass's readings,
# every recorded row came out 1.5 to 2.75 readings "off", because the LAMP pass's own constant
# (scan.MOTION_START_AFTER_LAMP_S) sits 1.25 to 3.25 readings early against the chart on the
# same rows (the review saw the same from the lamp side: +1.3 mm improves M0). Against the chart
# each pass is judged on its own; the lamp pass's best start is logged, and since 4.3.48 judged
# too, in the dual row only (see the next section; the released strip rows share its constant
# and are not changed).
#
# Both best starts are written into the row's record (``dual_cut.json``, the row record), so the
# first real rows tell the true values. TUNED on the volunteer's recorded rows (private,
# 2026-11-19, work folder table_fix/proof/tune_uv_timing*.txt; RE_REVIEW_BRIEF.md has the table):
# every recorded UV pass's best start lies within 0.5 readings of the assumed one (R squared gain
# at most 0.0041); shifted by 2 or more readings, every one is refused (gain at least 0.0133).

UV_FIT_SPAN = 6.0                  # readings either side of the assumed start
UV_FIT_STEP = 0.25                 # readings
UV_FIT_REFUSE_READINGS = 1.0       # |best - assumed| at or beyond this: refused ...
UV_FIT_MIN_GAIN = 0.005            # ... when R squared at the best start is this much better
UV_FIT_MIN_SPREAD = 0.05           # std / mean of the readings inside the patches
UV_FIT_BANDS_NM = (380.0, 400.0)

# ---- the lamp pass's timing (4.3.48 re-review, SHOULD-A) ------------------------------------------
#
# The same fit, over the lamp pass's readings at 380-730 nm, judged too: in the reviewer's stress
# run a lamp pass 2 readings late gave M0 off by up to 2.65 dE00, 3 readings 10 dE00, and the
# lamp's uniformity check refused only 2 of 12. Only the DUAL ROW is judged; the released
# single-scan strip rows are not changed (the review found no fault in them).
#
# TUNED on the volunteer's recorded dual rows (private, 2026-11-19, work folder
# 2026-11-19_release_4348/proof/lamp_tune*_private.txt): the five recorded lamp passes (driven
# by the vendor's software) fit best 0.25 to 2.25 readings EARLY of ChromIQ's assumed start (the
# re-review's M0 comparison found the same, -1 to -1.5), and the fit is sharp (R squared 0.998
# at the best start). Against the vendor's M0, moving a recorded pass costs little while its
# best start stays within -2.75 and +1.75 readings of the assumed one (M0 max 0.40 dE00), and
# a lot beyond: +2.25 to +2.75 gave max 1.5 to 1.95 dE00, -3.25 gave 1.37, -3.5 gave 2.9 to
# 8.4. So a lamp pass is refused (``lamp_pass_timing_off``) when its best start lies
# LAMP_FIT_REFUSE_LATE readings or more late (1.75: the fit's 0.25-reading steps put a pass
# truly 2 readings late at 1.75 or 2.0), or LAMP_FIT_REFUSE_EARLY or more early (the recorded
# passes reach 2.25 early and read well), with the same gain gate as the UV pass. A
# row whose patches hardly differ, or whose edges do not move R squared, is not judged.
LAMP_FIT_REFUSE_LATE = 1.75        # readings late of the assumed start: refused ...
LAMP_FIT_REFUSE_EARLY = 2.5        # ... or this many early ...
LAMP_FIT_MIN_GAIN = UV_FIT_MIN_GAIN   # ... when R squared at the best start is this much better


def _position_at(plan, t: float) -> float:
    """The arm's place along *plan* (mm from its start) *t* seconds after its motion started
    (the inverse of :func:`scan.time_at`)."""
    V = float(plan.speed)
    ta = plan.A / 1000.0
    L = plan.dist / 10.0
    a = V / ta
    if t <= 0:
        return 0.0
    if t >= plan.move_s:
        return L
    d_acc = 0.5 * a * ta * ta
    if L < 2 * d_acc:
        th = math.sqrt(L / a)
        if t <= th:
            return 0.5 * a * t * t
        r = 2 * th - t
        return L - 0.5 * a * r * r
    if t <= ta:
        return 0.5 * a * t * t
    if t <= plan.move_s - ta:
        return d_acc + (t - ta) * V
    r = plan.move_s - t
    return L - 0.5 * a * r * r


def _band_means(rows, wavelengths=None, bands=UV_FIT_BANDS_NM) -> "list[float]":
    if wavelengths:
        idx = [j for j, w in enumerate(wavelengths)
               if bands[0] - 1e-6 <= float(w) <= bands[1] + 1e-6]
    else:
        n = len(rows[0]) if rows else 36
        idx = [j for j in range(n) if bands[0] - 1e-6 <= 380.0 + 10.0 * j <= bands[1] + 1e-6]
    if not idx:
        return []
    return [sum(r[j] for j in idx) / len(idx) for r in rows]


def _layout_fit(plan, signal, first_reading_s: float, motion_start_s: float) -> dict:
    """The motion start (readings from *motion_start_s*) at which *signal* (one value per
    reading of a pass along *plan*) is flattest inside the plan's patches."""
    def score(k):
        start = motion_start_s + k * sc.READING_S
        groups = []
        for q in plan.patches:
            hc = q.half_mm - plan.aperture_mm / 2
            if hc <= 0:
                continue
            g = []
            for j, v in enumerate(signal):
                t = first_reading_s + j * sc.READING_S - start
                if 0.0 < t < plan.move_s and abs(_position_at(plan, t) - q.along_mm) <= hc:
                    g.append(v)
            if len(g) >= 2:
                groups.append(g)
        vals = [v for g in groups for v in g]
        if len(groups) < 2 or len(vals) < 6:
            return float("nan"), 0.0
        m = sum(vals) / len(vals)
        tot = sum((v - m) ** 2 for v in vals)
        within = sum(sum((v - sum(g) / len(g)) ** 2 for v in g) for g in groups)
        spread = math.sqrt(tot / len(vals)) / m if m > 0 else 0.0
        return (1.0 - within / tot) if tot > 0 else float("nan"), spread
    n_steps = int(round(UV_FIT_SPAN / UV_FIT_STEP))
    scores = [(i * UV_FIT_STEP, *score(i * UV_FIT_STEP)) for i in range(-n_steps, n_steps + 1)]
    good = [(k, r2, sp_) for k, r2, sp_ in scores if r2 == r2]
    r0, spread0 = score(0.0)
    if not good or r0 != r0:
        return {"best_readings": None, "r2_best": None, "r2_assumed": None, "spread": spread0}
    kb, rb, _sp = max(good, key=lambda t: (t[1], -abs(t[0])))
    return {"best_readings": kb, "best_motion_start_s": round(motion_start_s + kb * sc.READING_S,
                                                               4),
            "r2_best": round(rb, 6), "r2_assumed": round(r0, 6), "spread": round(spread0, 4)}


def _judge_lamp(lf) -> dict:
    """The lamp pass's verdict from its fit (see LAMP_FIT_REFUSE_LATE)."""
    if lf is None or lf.get("best_readings") is None:
        return {"lamp_checked": False, "lamp_refuse": False,
                "lamp_why": "too few readings inside the patches"}
    if lf["spread"] < UV_FIT_MIN_SPREAD:
        return {"lamp_checked": False, "lamp_refuse": False,
                "lamp_why": "the row's patches hardly differ"}
    b = lf["best_readings"]
    off = b >= LAMP_FIT_REFUSE_LATE or b <= -LAMP_FIT_REFUSE_EARLY
    if off and (lf["r2_best"] - lf["r2_assumed"]) < LAMP_FIT_MIN_GAIN:
        return {"lamp_checked": False, "lamp_refuse": False,
                "lamp_why": "the patches' edges do not show the timing (R squared hardly changes)"}
    return {"lamp_checked": True, "lamp_refuse": off}


def uv_timing_fit(lamp, uv, lamp_rows, uv_rows, wavelengths=None) -> dict:
    """Both passes' timing against the chart (see the sections' comments). Returns a dict for
    the row's record: ``checked`` (False: the patches hardly differ at 380-400 nm, or too few
    readings), ``refuse`` (True: the UV pass's best start is UV_FIT_REFUSE_READINGS or more from
    the assumed one, and R squared there is UV_FIT_MIN_GAIN better), ``lamp_checked`` and
    ``lamp_refuse`` (the same for the lamp pass, LAMP_FIT_REFUSE_LATE / _EARLY), ``uv`` and
    ``lamp`` (each pass's best start in readings and seconds, R squared at the best and at the
    assumed start)."""
    out = {"checked": False, "refuse": False, "assumed_uv_motion_start_s":
           sc.UV_MOTION_START_AFTER_TRIGGER_S, "assumed_lamp_motion_start_s":
           sc.MOTION_START_AFTER_LAMP_S, "refuse_at_readings": UV_FIT_REFUSE_READINGS,
           "lamp_refuse_at_readings": {"late": LAMP_FIT_REFUSE_LATE,
                                       "early": LAMP_FIT_REFUSE_EARLY},
           "span_readings": UV_FIT_SPAN, "uv": None, "lamp": None,
           "lamp_checked": False, "lamp_refuse": False}
    if not lamp.patches or not lamp_rows or not uv_rows:
        out["why"] = "no readings"
        out["lamp_why"] = "no readings"
        return out
    su = _band_means(uv_rows, wavelengths)
    sl = _band_means(lamp_rows, wavelengths, (380.0, 730.0))
    out["uv"] = _layout_fit(uv, su, sc.UV_FIRST_READING_AFTER_TRIGGER_S,
                            sc.UV_MOTION_START_AFTER_TRIGGER_S)
    out["lamp"] = _layout_fit(lamp, sl, sc.FIRST_READING_AFTER_LAMP_S,
                              sc.MOTION_START_AFTER_LAMP_S)
    out.update(_judge_lamp(out["lamp"]))
    u = out["uv"]
    if u["best_readings"] is None:
        out["why"] = "too few readings inside the patches"
        return out
    if u["spread"] < UV_FIT_MIN_SPREAD:
        out["why"] = "the row's patches hardly differ at 380-400 nm"
        return out
    off = abs(u["best_readings"]) >= UV_FIT_REFUSE_READINGS
    if off and (u["r2_best"] - u["r2_assumed"]) < UV_FIT_MIN_GAIN:
        out["why"] = "the patches' edges do not show the timing (R squared hardly changes)"
        return out
    out["checked"] = True
    out["refuse"] = off
    return out


def write_dual_in(path: str, cut: DualCut) -> None:
    """The helper's input: n, then per patch the lamp pass's 36 values and the UV pass's 36."""
    lines = [str(len(cut.lamp))]
    for l, u in zip(cut.lamp, cut.uv):
        lines.append(" ".join(f"{v:.8f}" for v in list(l) + list(u)))
    tmp = path + ".part"
    with open(tmp, "w", encoding="ascii") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, path)


def read_dual_out(path: str, n: int, nbands: int = 36) -> "tuple[list, list]":
    """M1 and M2 per patch from the helper's output (n lines of M1's and M2's values)."""
    m1, m2 = [], []
    with open(path, encoding="ascii") as fh:
        rows = [ln.split() for ln in fh if ln.strip()]
    if len(rows) != n:
        raise ValueError(f"{len(rows)} rows, not {n}")
    for r in rows:
        v = [float(x) for x in r]
        if len(v) != 2 * nbands or not all(math.isfinite(x) for x in v):
            raise ValueError("a row of the wrong shape")
        m1.append(v[:nbands])
        m2.append(v[nbands:])
    return m1, m2


def dual_keywords(setup: DualSetup, white: str) -> "list[tuple[str, str]]":
    """The header keywords every file of a dual measurement carries (storage's)."""
    import workflow.dual_scan.storage as S
    return [(S.DUAL_KEYWORD, "i1pro2"), (S.SCALE_KEYWORD, f"{setup.scale:.4f}"),
            (S.SOURCE_KEYWORD, setup.source), (S.WHITE_KEYWORD, white),
            (S.CHOSEN_KEYWORD, setup.chosen)]


def condition_cut(lamp_plan, cut: DualCut, values) -> "stp.Cut":
    """A strip.Cut of one condition (*values* per patch, 0..1) with the XYZ computed from it as
    the row file has it, so strip.write_row_file writes its file."""
    xyzs = stp._xyz(values, cut.wavelengths)
    return stp.Cut(True, "", [(q.sample_id, q.loc, v, x)
                              for q, v, x in zip(lamp_plan.patches, values, xyzs)],
                   list(cut.wavelengths), {})


def add_keywords(path: str, pairs) -> None:
    """Header keywords into a row file the job wrote (after its CUT_BY line)."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    extra = "".join(f'KEYWORD "{k}"\n{k} "{v}"\n' for k, v in pairs)
    at = text.index("\n\nNUMBER_OF_FIELDS")
    text = text[:at + 1] + extra + text[at + 1:]
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)
