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


def cut_dual(lamp, uv, lamp_rows, uv_rows, edges=None) -> DualCut:
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
    return DualCut(True, "", L, U, info=info)


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
