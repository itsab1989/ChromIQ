# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""A strip row's readings into patches, and its row file (build step 10, round B: A FIRST TRY,
not confirmed on a real table yet; off by default).

The reading stream is the helper's table-scan mode's (``<name>.spec.csv``: every reading's
calibrated spectrum, the i1Pro 2's own conversion, ``native/instlib/cq_i1pro2_tscan.h``). It is
cut into patches BY POSITION with tester 0.6.0's own rule (``scan.cut_by_position``: the move's
profile, the recorded first-reading delay and the measured motion start; no refinement), exactly
what the tester's E2/E3 did. Nothing is guessed:

* a row FAILS (``strip_*`` ids, nothing of it is kept) when the instrument did not deliver its
  readings, delivered fewer than the plan's, when a patch's window holds fewer than
  ``spot.STRIP_MIN_READINGS`` readings or lies outside the stream, when a window is not on one
  colour (``spot.STRIP_UNIFORMITY_MAX``), or when a patch's value is implausible
  (``spot.plausible``, the spot rows' own rule);
* ArgyllCMS's own recogniser result (``<name>.rec.csv``, the helper's cross-check) is recorded
  beside, never used for a value.

The row file has the fields a spot row's file has for the same options (so a session may mix
strip rows and rows read patch by patch): SAMPLE_ID, SAMPLE_LOC, XYZ (unless -l), L*a*b* (with
-l or -L), the spectrum in percent (unless -n). XYZ is computed from the spectrum the way
ArgyllCMS's chartread does (D50, the 1931 2 degree observer, ``workflow.argyll_colorimetry``,
the app's own ArgyllCMS method). It carries ``CUT_BY "position (first try)"``.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field

from . import scan as sc
from . import spot as sp

CUT_BY = "position (first try)"
ROW_FILE_SUFFIX = ".ti3"


@dataclass
class Cut:
    ok: bool
    reason: str = ""
    #: [(sample_id, loc, spectrum 0..1, xyz)] in the plan's patch order, only when ok
    patches: list = field(default_factory=list)
    wavelengths: list = field(default_factory=list)
    info: dict = field(default_factory=dict)


def _xyz(spectra, wl):
    from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll
    out = spectra_to_xyz_like_argyll(spectra, wl, illuminant="D50", observer="1931_2")
    return [[float(v) for v in row] for row in out]


def lab_d50(xyz):
    """CIE L*a*b* of an XYZ on the Y = 100 scale, against the D50 white ArgyllCMS uses."""
    wx, wy, wz = 96.42, 100.0, 82.49

    def f(t):
        return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (24389.0 / 27.0 * t + 16.0) / 116.0
    fx, fy, fz = f(xyz[0] / wx), f(xyz[1] / wy), f(xyz[2] / wz)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def cut_row(plan, outdir: str, fired: "dict | None") -> Cut:
    """The patches of one scanned row, or the reason it cannot be cut (nothing guessed)."""
    if not fired or not fired.get("ok"):
        return Cut(False, "strip_instrument_delivered_nothing")
    spec = os.path.join(outdir, plan.name + ".spec.csv")
    if not os.path.exists(spec):
        return Cut(False, "strip_instrument_delivered_nothing")
    try:
        wl, rows = sc.read_spec_csv(spec)
    except (OSError, ValueError):
        return Cut(False, "strip_readings_unreadable")
    got = fired.get("got")
    if len(rows) < plan.N or (isinstance(got, int) and got < plan.N):
        return Cut(False, "strip_fewer_readings_than_planned",
                   info={"readings": len(rows), "planned": plan.N})
    try:
        vals, info = sc.cut_by_position(plan, rows)
    except ValueError:
        return Cut(False, "strip_patches_outside_the_readings")
    if len(vals) != len(plan.patches):
        return Cut(False, "strip_patch_count_differs", info=info)
    if min(info["readings_per_patch"], default=0) < sp.STRIP_MIN_READINGS:
        return Cut(False, "strip_patch_too_few_readings", info=info)
    if max(info["uniformity"], default=0.0) > sp.STRIP_UNIFORMITY_MAX:
        bad = [q.loc for q, u in zip(plan.patches, info["uniformity"])
               if u > sp.STRIP_UNIFORMITY_MAX]
        return Cut(False, "strip_patch_not_on_one_colour", info=dict(info, patches=bad))
    xyzs = _xyz(vals, wl)
    for q, xyz in zip(plan.patches, xyzs):
        why = sp.plausible(xyz)
        if why or not all(math.isfinite(v) for v in xyz):
            return Cut(False, "strip_patch_implausible", info=dict(info, loc=q.loc))
    info = dict(info, recogniser=_recogniser(plan, outdir, fired))
    return Cut(True, "", [(q.sample_id, q.loc, v, x)
                          for q, v, x in zip(plan.patches, vals, xyzs)], list(wl), info)


def _recogniser(plan, outdir, fired) -> dict:
    """ArgyllCMS's own recogniser on the same pass (the helper's cross-check): recorded only."""
    out = {"rec_ev": fired.get("rec_ev"), "patches": fired.get("patches")}
    path = os.path.join(outdir, plan.name + ".rec.csv")
    if os.path.exists(path):
        try:
            _wl, rows = sc.read_spec_csv(path)
            out["found"] = len(rows)
        except (OSError, ValueError):
            out["found"] = None
    return out


def write_row_file(path: str, cut: Cut, options: "sp.ReadOptions") -> None:
    """The row's file, with the fields a spot row's file has for these options."""
    fields = ["SAMPLE_ID", "SAMPLE_LOC"]
    xyz = not options.save_lab
    lab = options.save_lab or options.save_lab_and_xyz
    spec = not options.no_spectral
    if xyz:
        fields += ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    if lab:
        fields += ["LAB_L", "LAB_A", "LAB_B"]
    if spec:
        fields += [f"SPEC_{int(round(w))}" for w in cut.wavelengths]
    head = ["CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
            'ORIGINATOR "ChromIQ i1iO table, strip reading (first try)"',
            f'CREATED "{time.strftime("%a %b %d %H:%M:%S %Y")}"',
            'KEYWORD "DEVICE_CLASS"', 'DEVICE_CLASS "OUTPUT"',
            'KEYWORD "TARGET_INSTRUMENT"', 'TARGET_INSTRUMENT "X-Rite i1 Pro 2"',
            'KEYWORD "INSTRUMENT_TYPE_REFLECTIVE"', 'INSTRUMENT_TYPE_REFLECTIVE "YES"',
            'KEYWORD "CUT_BY"', f'CUT_BY "{CUT_BY}"']
    if spec and cut.wavelengths:
        head += ['KEYWORD "SPECTRAL_BANDS"', f'SPECTRAL_BANDS "{len(cut.wavelengths)}"',
                 'KEYWORD "SPECTRAL_START_NM"',
                 f'SPECTRAL_START_NM "{cut.wavelengths[0]:.6f}"',
                 'KEYWORD "SPECTRAL_END_NM"', f'SPECTRAL_END_NM "{cut.wavelengths[-1]:.6f}"',
                 'KEYWORD "SPECTRAL_NORM"', 'SPECTRAL_NORM "100.000000"']
    body = []
    for sid, loc, v, x in cut.patches:
        parts = [str(sid), f'"{loc}"']
        if xyz:
            parts += [f"{c:.6f}" for c in x]
        if lab:
            parts += [f"{c:.6f}" for c in lab_d50(x)]
        if spec:
            parts += [f"{100.0 * c:.6f}" for c in v]
        body.append(" ".join(parts))
    text = ("\n".join(head) + "\n\n" + f"NUMBER_OF_FIELDS {len(fields)}\nBEGIN_DATA_FORMAT\n"
            + " ".join(fields) + "\nEND_DATA_FORMAT\n\n" + f"NUMBER_OF_SETS {len(body)}\n"
            + "BEGIN_DATA\n" + "\n".join(body) + "\nEND_DATA\n")
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def accepted_entries(cut: Cut, path: str) -> "list[dict]":
    """The row record's accepted readings: the XYZ exactly as the row file holds it (the
    assembly's cross-check compares the two)."""
    out = []
    for sid, loc, _v, x in cut.patches:
        out.append({"sample_id": sid, "loc": loc,
                    "xyz": [round(float(c), 6) for c in x]})
    return out


def save_cut_info(outdir: str, name: str, cut: Cut) -> None:
    try:
        with open(os.path.join(outdir, name + ".strip_cut.json"), "w", encoding="utf-8") as fh:
            json.dump({"ok": cut.ok, "reason": cut.reason, "info": cut.info}, fh, default=str)
    except OSError:
        pass
