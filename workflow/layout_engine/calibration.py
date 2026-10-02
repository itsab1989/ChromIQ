"""Printer calibration (printtarg ``-K`` / ``-I``).

A ``.cal`` is a CGATS ``CAL`` table: a shared input axis (``RGB_I``, 0–1) plus
one calibrated-output column per device channel (e.g. ``RGB_R RGB_G RGB_B``),
typically 256 rows.  printtarg can:

* ``-K`` **apply** the curves to the colour each patch is PRINTED with (the
  page TIFF / PostScript) *and* embed the table in the ``.ti2``. The ``.ti2``'s
  own device values stay uncalibrated: printtarg writes them from
  ``cols[i].dev`` and calibrates only a local ``cdev`` in ``tiff_setcolor`` /
  ``ps_setcolor``. chartread copies them into the ``.ti3``, so the profile is
  of the calibrated device and ``applycal`` folds the curves in exactly once;
* ``-I`` **embed** the table without applying it.

This module reads the table, applies it (per-channel linear interpolation,
device values in 0–100), and returns the raw table text for embedding.  The
apply path is validated to match ``printtarg -K`` exactly (see tests).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from core.text_io import read_text


@dataclass(frozen=True)
class Calibration:
    color_rep: str
    out_fields: list[str]        # e.g. ["RGB_R", "RGB_G", "RGB_B"]
    input_axis: np.ndarray       # shape (N,), 0..1
    curves: np.ndarray           # shape (N, nchan), 0..1
    raw_text: str                # the original .cal file text (for embedding)

    @property
    def n_channels(self) -> int:
        return len(self.out_fields)

    def apply(self, device: tuple[float, ...]) -> tuple[float, ...]:
        """Map device values (0–100) through the per-channel curves (0–100).

        Per-channel linear interpolation of the LUT, used for the printed
        pixels only (never the ``.ti2``). For an identity ``.cal`` it matches
        ``printtarg -K`` exactly.  It is *not* bit-identical to printtarg for non-trivial cals
        across every colorspace (Argyll applies cals in the native device space
        with its own interpolation); for printtarg-exact ``-K`` output, delegate
        to ArgyllCMS.  Used for additive-RGB printers (ChromIQ's target).
        """
        if len(device) != self.n_channels:
            raise ValueError(
                f"calibration has {self.n_channels} channels, value has {len(device)}")
        out = []
        for i, v in enumerate(device):
            u = min(1.0, max(0.0, v / 100.0))
            out.append(float(np.interp(u, self.input_axis, self.curves[:, i]) * 100.0))
        return tuple(out)


def read_cal(path: str | Path) -> Calibration:
    """Parse an ArgyllCMS ``.cal`` file."""
    text = read_text(Path(path), lenient=True)

    rep_m = re.search(r'^COLOR_REP\s+"([^"]+)"', text, re.MULTILINE)
    color_rep = rep_m.group(1) if rep_m else "RGB"

    fmt_m = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\nEND_DATA_FORMAT", text, re.DOTALL)
    data_m = re.search(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", text, re.DOTALL)
    if not (fmt_m and data_m):
        raise ValueError("not a CAL file (missing DATA tables)")

    fields = fmt_m.group(1).split()
    # First field is the shared input axis (e.g. RGB_I); the rest are channels.
    in_idx = 0
    out_idx = list(range(1, len(fields)))
    out_fields = [fields[i] for i in out_idx]

    rows = [ln.split() for ln in data_m.group(1).splitlines() if ln.strip()]
    arr = np.array([[float(t) for t in r] for r in rows], dtype=float)
    input_axis = arr[:, in_idx]
    curves = arr[:, out_idx]
    return Calibration(color_rep=color_rep, out_fields=out_fields,
                       input_axis=input_axis, curves=curves, raw_text=text)


def cal_table_text(cal: Calibration) -> str:
    """The CAL table text to append to a ``.ti2`` for embedding (``-K``/``-I``)."""
    return cal.raw_text.strip() + "\n"


def colour_space_name(color_rep: str) -> str:
    """A person's name for a CGATS ``COLOR_REP``: ``iRGB`` and ``RGB`` are
    both "RGB" (the ``i`` is Argyll's print-RGB flag, not another set of
    inks), a one-channel grey is "grey", everything else is its own letters
    (``CMYK``, ``CMY``, ``CMYKOG`` …)."""
    rep = (color_rep or "").split("_")[0].strip()
    if rep.startswith("i") and len(rep) > 1:
        rep = rep[1:]
    if rep.upper() in ("W", "K", "GRAY", "GREY"):
        from core.i18n import tr
        return tr("grey")
    return rep or "?"


class CalibrationMismatch(ValueError):
    """The calibration is for other inks than the chart (#182 5956560815).

    ``printtarg`` refuses this for ``-K`` AND ``-I`` alike ("Calibration
    colorspace CMYK doesn't match .ti1 iRGB", measured against 3.5.0), and
    the engine does the same, so a CMYK calibration can never be printed
    into, or recorded in, an RGB chart. ``str()`` stays the short technical
    line for the log; :meth:`friendly` is what a person is shown.
    """

    def __init__(self, cal_rep: str, chart_rep: str,
                 cal_fields: list[str], chart_fields: list[str]):
        self.cal_rep, self.chart_rep = cal_rep, chart_rep
        self.cal_fields, self.chart_fields = list(cal_fields), list(chart_fields)
        super().__init__(
            f"the calibration is {cal_rep} ({' '.join(cal_fields)}), the "
            f"chart is {chart_rep} ({' '.join(chart_fields)})")

    def friendly(self) -> str:
        return calibration_mismatch_message(self.cal_rep, self.chart_rep)


def calibration_mismatch_message(cal_rep: str, chart_rep: str) -> str:
    """What the window says when a calibration and a chart do not match.

    One text for both layout routes: the engine raises
    :class:`CalibrationMismatch`, and printtarg's own refusal is recognised
    in ``chart_creator`` and reworded with this.
    """
    from core.i18n import tr
    return tr(
        "The calibration file was made for a {cal_space} chart, but the patch "
        "set you are building is {chart_space}. A calibration can only be "
        "applied to (-K) or embedded in (-I) a chart with the same inks, so "
        "the chart was not built.\n\n"
        "To use this calibration, set “Device Type” in the targen settings to "
        "{cal_space} and press Generate Chart again. A new profiling run starts "
        "on the default Device Type, not on the one the calibration chart was "
        "made with, so check it there.\n\n"
        "To build this {chart_space} chart without the calibration, set the "
        "printer calibration to “None”."
    ).format(cal_space=colour_space_name(cal_rep),
             chart_space=colour_space_name(chart_rep))


def check_matches(target, cal: Calibration) -> None:
    """Raise :class:`CalibrationMismatch` unless *cal* is for *target*'s inks.

    The test is the device columns themselves (``CMYK_C CMYK_M CMYK_Y
    CMYK_K`` against the ``.ti1``'s), in order: they are what
    :meth:`Calibration.apply` pairs up, and they are named the same way in
    both files by Argyll. Argyll's own test is the ``COLOR_REP``, which also
    tells print RGB (``iRGB``) from video RGB (``RGB``); the engine has always
    accepted an RGB calibration on either, and keeps doing so, because the
    numbers mean the same channels.

    Only the colorant after the ``_`` is compared. The prefix is the file's
    own colour-space word and Argyll does not spell it the same way in both
    files for every device: a grey ``.ti1`` names its channel ``GRAY_K``
    (``GRAY_W`` for video grey) while the ``.cal`` printcal / synthcal write
    for it names the same channel ``K_K`` (``W_W``). printtarg accepts that
    pair; comparing whole field names refused every grey calibration.
    """
    def _inks(fields) -> list[str]:
        return [str(f).rsplit("_", 1)[-1] for f in fields]

    if _inks(cal.out_fields) != _inks(target.device_fields):
        raise CalibrationMismatch(cal.color_rep, target.color_rep,
                                  cal.out_fields, target.device_fields)


def apply_to_target(target, cal: Calibration):
    """Return a copy of a :class:`ColorTarget` with device values calibrated.

    Used for ``-K`` (apply), for what is PRINTED only: the page raster. The
    ``.ti2`` is written from the uncalibrated target, as printtarg does, or
    the profile describes the raw printer and ``applycal`` calibrates twice.
    """
    from dataclasses import replace
    check_matches(target, cal)
    new_patches = [(cal.apply(dev), xyz) for dev, xyz in target.patches]
    return replace(target, patches=new_patches)
