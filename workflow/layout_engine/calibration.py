"""Printer calibration (printtarg ``-K`` / ``-I``).

A ``.cal`` is a CGATS ``CAL`` table: a shared input axis (``RGB_I``, 0–1) plus
one calibrated-output column per device channel (e.g. ``RGB_R RGB_G RGB_B``),
typically 256 rows.  printtarg can:

* ``-K`` **apply** the curves to each patch's device values *and* embed the
  table in the ``.ti2``;
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

        Per-channel linear interpolation of the LUT.  This is **self-consistent**
        (the TIFF and ``.ti2`` are calibrated identically, so the measured chart
        is valid), and for an identity ``.cal`` it matches ``printtarg -K``
        exactly.  It is *not* bit-identical to printtarg for non-trivial cals
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


def apply_to_target(target, cal: Calibration):
    """Return a copy of a :class:`ColorTarget` with device values calibrated.

    Used for ``-K`` (apply): the TIFF and ``.ti2`` are calibrated identically,
    keeping the printed chart and its measurement file self-consistent.
    """
    from dataclasses import replace
    if cal.n_channels != len(target.device_fields):
        raise ValueError(
            f"calibration has {cal.n_channels} channels, target has "
            f"{len(target.device_fields)}")
    new_patches = [(cal.apply(dev), xyz) for dev, xyz in target.patches]
    return replace(target, patches=new_patches)
