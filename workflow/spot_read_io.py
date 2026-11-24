"""Colour conversion and file output for the single-patch (spot) read tool.

spotread reports each reading as XYZ plus D50 L*a*b*. This module turns those
values into:

  * an on-screen sRGB swatch colour  (``lab_d50_to_srgb``)
  * a human-readable CSV             (``write_csv``)
  * an Argyll CGATS ``.ti3``         (``write_ti3`` — delegates to the existing
                                      ``colverify_runner.write_reference_ti3``)

The ``.ti3`` is written from the measured XYZ (Argyll derives Lab from XYZ), so
it opens cleanly in other Argyll tools; the CSV carries the user-given patch
names and the sRGB hex for quick reference in a spreadsheet.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from workflow.colverify_runner import write_reference_ti3


@dataclass
class SpotReading:
    """One spot reading: a name plus its measured XYZ and D50 Lab.

    *condition* (item 43) is the ISO 13655 measurement condition the reading
    was taken under ("M0", "M1", "M2"), recorded only where ChromIQ knows it:
    an i1Pro 3, whose spotread session was started with or without ``-F``.
    None for every other instrument, which is what every reading was before,
    and then nothing about the saved files changes."""
    name: str
    xyz: tuple[float, float, float]
    lab: tuple[float, float, float]
    condition: "str | None" = None
    #: item 43 steps 2-3: EVERY condition this reading has, {"M0": (xyz,
    #: lab), "M1": ..., "M2": ...}, when ChromIQ's own spot session read it
    #: (an i1Pro 3, or an i1Pro 2's dual spot). *xyz*, *lab* and *condition*
    #: are then the ones the list shows (:meth:`show`). None for every other
    #: reading, which is what every reading was before.
    conditions: "dict | None" = None

    def show(self, condition: str) -> bool:
        """Show this reading in *condition* when it has it (the list's view
        switch); True when it changed what it shows. A reading without that
        condition keeps showing its own."""
        alts = self.conditions or {}
        if condition not in alts or condition == self.condition:
            return False
        xyz, lab = alts[condition]
        self.xyz, self.lab, self.condition = tuple(xyz), tuple(lab), condition
        return True

    def has(self, condition: "str | None") -> bool:
        """The reading has a value in *condition* (its own, or one kept)."""
        return condition in (self.conditions or {}) or condition == self.condition

    def as_condition(self, condition: "str | None") -> "SpotReading":
        """A copy showing *condition* (for the file of that condition)."""
        r = SpotReading(name=self.name, xyz=self.xyz, lab=self.lab,
                        condition=self.condition,
                        conditions=dict(self.conditions) if self.conditions else None)
        if condition is not None:
            r.show(condition)
        return r

    @property
    def keeps_several(self) -> bool:
        """The reading keeps more than one condition (steps 2-3)."""
        return len(self.conditions or {}) > 1

    @property
    def hex(self) -> str:
        r, g, b = lab_d50_to_srgb(*self.lab)
        return f"#{r:02x}{g:02x}{b:02x}"


# --- Lab (D50) -> sRGB ------------------------------------------------------
#
# spotread prints D50 Lab. To show a swatch we go Lab(D50) -> XYZ(D50), adapt
# D50 -> D65 (Bradford), then the standard XYZ(D65) -> linear sRGB -> gamma.
# This is the inverse of the sRGB -> XYZ path in workflow/i1profiler_import.py.

# D50 reference white (Y = 1).
_D50 = (0.96422, 1.0, 0.82521)

# Bradford chromatic adaptation, D50 -> D65 (standard matrix).
_BRADFORD_D50_TO_D65 = (
    ( 0.9555766, -0.0230393,  0.0631636),
    (-0.0282895,  1.0099416,  0.0210077),
    ( 0.0122982, -0.0204830,  1.3299098),
)

# XYZ(D65) -> linear sRGB.
_XYZ_TO_RGB = (
    ( 3.2404542, -1.5371385, -0.4985314),
    (-0.9692660,  1.8760108,  0.0415560),
    ( 0.0556434, -0.2040259,  1.0572252),
)


def _lab_to_xyz_d50(L: float, a: float, b: float) -> tuple[float, float, float]:
    """D50 L*a*b* -> XYZ with Y on a 0..1 scale (white = _D50)."""
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def _f_inv(t: float) -> float:
        t3 = t ** 3
        return t3 if t3 > 0.008856 else (t - 16.0 / 116.0) / 7.787

    xr, yr, zr = _f_inv(fx), _f_inv(fy), _f_inv(fz)
    return xr * _D50[0], yr * _D50[1], zr * _D50[2]


def average_readings(readings: list["SpotReading"], name: str) -> "SpotReading":
    """Average several readings into one. Both XYZ (used for the .ti3/CSV) and
    Lab (used for the on-screen swatch) are averaged component-wise — spotread
    reports both for every reading, so the mean Lab is taken straight from the
    measured Labs rather than reconstructed from XYZ (whose scale we don't pin).
    Raises ``ValueError`` if ``readings`` is empty.

    ONLY WITHIN ONE MEASUREMENT CONDITION (item 43): the same patch read in
    M0 and in M1 gives two different colours on purpose (the brighteners'
    glow), and their mean is a colour no light shows. Readings of different
    conditions raise :class:`MixedConditions`; the average carries the
    condition of its readings."""
    if not readings:
        raise ValueError("no readings to average")
    conditions = conditions_of(readings)
    if len(conditions) > 1:
        raise MixedConditions(conditions)
    n = len(readings)
    xyz = tuple(sum(r.xyz[i] for r in readings) / n for i in range(3))
    lab = tuple(sum(r.lab[i] for r in readings) / n for i in range(3))
    # item 43 steps 2-3: the conditions EVERY selected reading keeps are
    # averaged too, each within itself, so the average can be shown in them
    common = None
    for r in readings:
        keys = set((r.conditions or {}).keys())
        common = keys if common is None else common & keys
    alts = None
    if common and len(common) > 1:
        alts = {}
        for c in sorted(common):
            alts[c] = (tuple(sum(r.conditions[c][0][i] for r in readings) / n
                             for i in range(3)),
                       tuple(sum(r.conditions[c][1][i] for r in readings) / n
                             for i in range(3)))
    return SpotReading(name=name, xyz=xyz, lab=lab,
                       condition=readings[0].condition, conditions=alts)


class MixedConditions(ValueError):
    """Readings of more than one measurement condition were to be averaged."""

    def __init__(self, conditions: "list[str | None]") -> None:
        super().__init__("readings of different measurement conditions: "
                         + ", ".join(c or "none" for c in conditions))
        self.conditions = conditions


def conditions_of(readings: "list[SpotReading]") -> "list[str | None]":
    """The distinct conditions of *readings*, in first-seen order (None for
    readings without one)."""
    out: "list[str | None]" = []
    for r in readings:
        c = getattr(r, "condition", None)
        if c not in out:
            out.append(c)
    return out


def _mul(m: tuple, v: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(row[0] * v[0] + row[1] * v[1] + row[2] * v[2] for row in m)  # type: ignore[return-value]


def _gamma(c: float) -> float:
    """Linear-light 0..1 -> sRGB-encoded 0..1."""
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def lab_d50_to_srgb(L: float, a: float, b: float) -> tuple[int, int, int]:
    """D50 L*a*b* -> 8-bit sRGB ``(r, g, b)``, clamped to gamut.

    Out-of-gamut measurements (vivid inks, fluorescents) clamp per channel — the
    swatch is an *approximation* for orientation, never a colour-managed proof.
    """
    return xyz_d50_to_srgb(*_lab_to_xyz_d50(L, a, b))


def xyz_d50_to_srgb(X: float, Y: float, Z: float) -> tuple[int, int, int]:
    """D50 XYZ -> 8-bit sRGB ``(r, g, b)``, clamped to gamut. Expects Y on a
    0..1 scale (reference white ≈ 1.0); scale 0..100 input down before calling.

    Like :func:`lab_d50_to_srgb` this is an approximation for orientation /
    analysis (loading a CIE reference chart), not a colour-managed proof."""
    xyz_d65 = _mul(_BRADFORD_D50_TO_D65, (X, Y, Z))
    rgb_lin = _mul(_XYZ_TO_RGB, xyz_d65)
    return tuple(round(_gamma(c) * 255.0) for c in rgb_lin)  # type: ignore[return-value]


# --- File output ------------------------------------------------------------


def csv_needs_condition(readings: "list[SpotReading]") -> bool:
    """Whether the CSV carries a ``condition`` column (item 43): only when a
    reading is shown in M1 or M2, or keeps several conditions (steps 2-3). A
    list read in the instrument's own light (M0, or no condition known) is
    written exactly as before."""
    return any(getattr(r, "condition", None) not in (None, "M0")
               or getattr(r, "keeps_several", False) for r in readings)


def write_csv(path: Path, readings: list[SpotReading]) -> Path:
    """Write readings to a CSV: ``name,L,a,b,X,Y,Z,sRGB_hex`` (one row each),
    plus a last ``condition`` column when :func:`csv_needs_condition`."""
    with_condition = csv_needs_condition(readings)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        head = ["name", "L", "a", "b", "X", "Y", "Z", "sRGB_hex"]
        if with_condition:
            head.append("condition")
        w.writerow(head)
        for r in readings:
            row = [
                r.name,
                f"{r.lab[0]:.4f}", f"{r.lab[1]:.4f}", f"{r.lab[2]:.4f}",
                f"{r.xyz[0]:.4f}", f"{r.xyz[1]:.4f}", f"{r.xyz[2]:.4f}",
                r.hex,
            ]
            if with_condition:
                row.append(r.condition or "")
            w.writerow(row)
    return path


def write_ti3(path: Path, readings: list[SpotReading]) -> Path:
    """Write readings to an Argyll CGATS ``.ti3`` (XYZ measurement set).

    When the readings share one known condition (item 43) the header names it
    (``MEASUREMENT_CONDITION``, as a chart measurement does; M0 from an i1Pro
    3 without ``-F`` is marked as the instrument's normal mode), so the FWA
    gate treats the file like any other. Readings without a condition are
    written exactly as before. Raises :class:`MixedConditions` for a mixed
    list: use :func:`write_ti3_files`."""
    conditions = conditions_of(readings)
    if len(conditions) > 1:
        raise MixedConditions(conditions)
    out = write_reference_ti3(path, [r.xyz for r in readings], space="XYZ")
    cond = conditions[0] if conditions else None
    if cond:
        from workflow.measurement_condition import (
            SOURCE_INSTRUMENT_DEFAULT, record_condition)
        record_condition(out, cond, source=(SOURCE_INSTRUMENT_DEFAULT
                                            if cond == "M0" else None))
    return out


def ti3_groups(base: "str | Path", readings: "list[SpotReading]"
               ) -> "list[tuple[Path, list[SpotReading]]]":
    """Where each condition's readings go: ONE CONDITION PER ``.ti3``.

    A list of one condition (or of none) is one file, ``<base>.ti3``, as
    always. A mixed list is split: ``<base>-M1.ti3`` and so on, each reading
    in the file of its own condition, in list order; readings without a
    condition keep ``<base>.ti3``."""
    from core.stem_paths import artefact
    if any(getattr(r, "keeps_several", False) for r in readings):
        return _groups_of_kept(base, readings)
    conditions = conditions_of(readings)
    if len(conditions) <= 1:
        return [(artefact(base, ".ti3"), list(readings))]
    groups = []
    for cond in conditions:
        stem = f"{base}-{cond}" if cond else str(base)
        groups.append((artefact(stem, ".ti3"),
                       [r for r in readings
                        if getattr(r, "condition", None) == cond]))
    return groups


def _groups_of_kept(base, readings):
    """Item 43 steps 2-3: some readings keep M0, M1 and M2. ONE FILE PER
    CONDITION, ``<base>-M0.ti3``, ``<base>-M1.ti3``, ``<base>-M2.ti3``, each
    with every reading that has that condition (whatever the list shows), in
    list order; a reading without any condition keeps ``<base>.ti3``. So the
    files are the same whichever condition the list shows."""
    from core.stem_paths import artefact
    present = [c for c in ("M0", "M1", "M2")
               if any(r.has(c) for r in readings)]
    groups = []
    for c in present:
        groups.append((artefact(f"{base}-{c}", ".ti3"),
                       [r.as_condition(c) for r in readings if r.has(c)]))
    rest = [r for r in readings if r.condition is None and not r.conditions]
    if rest:
        groups.insert(0, (artefact(base, ".ti3"), rest))
    return groups


def write_ti3_files(base: "str | Path", readings: "list[SpotReading]"
                    ) -> "list[Path]":
    """Write the readings as one ``.ti3`` per condition (:func:`ti3_groups`)."""
    return [write_ti3(path, group) for path, group in ti3_groups(base, readings)]
