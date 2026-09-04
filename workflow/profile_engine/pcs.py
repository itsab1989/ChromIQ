"""PCS codecs — Lab16 (legacy v2) and XYZ16 (u1.15) table encodings.

The engine fits and inverts in Lab (the validated basis); a codec maps
between the profile's PCS-native CLUT coordinates and Lab, so ``-a l`` and
``-a x`` share one pipeline. colprof's own output profiles are restricted to
exactly these two cLUT types (``colprof.c``: "Output profile can only be a
cLUT algorithm").
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.ti3_data import lab_to_xyz, xyz_to_lab


class LabPcs:
    signature = b"Lab "

    @staticmethod
    def node_lab(grid: int) -> np.ndarray:
        """CLUT node targets (B2A/gamt input grid), expressed in Lab."""
        ls, ab = icw.lab_grid_axes(grid)
        return np.stack(np.meshgrid(ls, ab, ab, indexing="ij"),
                        -1).reshape(-1, 3)

    @staticmethod
    def lab_to01(lab: np.ndarray) -> np.ndarray:
        """Lab → CLUT grid coordinate 0..1 per axis."""
        ls, ab = icw.lab_grid_axes(2)
        lo = np.array([ls[0], ab[0], ab[0]])
        hi = np.array([ls[-1], ab[-1], ab[-1]])
        return np.clip((lab - lo[None, :]) / (hi - lo)[None, :], 0.0, 1.0)

    @staticmethod
    def encode(lab: np.ndarray) -> np.ndarray:
        """A2B CLUT output encoding from Lab values."""
        return icw.lab_to_u16(lab)

    @staticmethod
    def b2a_in_tables(entries: int) -> np.ndarray:
        """B2A/gamt input shaper tables (PCS value → grid coordinate):
        colprof's L*-axis scaling, so L*=100 is the top grid row."""
        return icw.lab_b2a_in_tables(entries)


class XyzPcs:
    signature = b"XYZ "

    @staticmethod
    def node_lab(grid: int) -> np.ndarray:
        ax = icw.xyz_grid_axes(grid)
        xyz1 = np.stack(np.meshgrid(ax, ax, ax, indexing="ij"),
                        -1).reshape(-1, 3)
        return xyz_to_lab(xyz1 * 100.0)

    @staticmethod
    def lab_to01(lab: np.ndarray) -> np.ndarray:
        xyz1 = lab_to_xyz(lab) / 100.0
        return np.clip(xyz1 / icw.XYZ16_MAX, 0.0, 1.0)

    @staticmethod
    def encode(lab: np.ndarray) -> np.ndarray:
        return icw.xyz_to_u16(lab_to_xyz(lab) / 100.0)

    @staticmethod
    def b2a_in_tables(entries: int) -> np.ndarray:
        return np.tile(icw._identity_table(entries), (3, 1))


class XyzPcsShaped(XyzPcs):
    """XYZ PCS with cube-root-shaped B2A/gamt input curves (accurate mode).

    A CLUT grid laid out uniformly in XYZ starves the shadows: L* goes with
    the cube root of Y, so the bottom *sixth* of the L* axis is squeezed
    into the first grid cell (measured on a real chart: B2A round-trip
    median ≈ 4 ΔE, p95 ≈ 17). Shaping the B2A input tables by the cube
    root places the very same grid uniformly in L*-like coordinates —
    CIE-lightness maths, not a tuning constant — which is exactly what the
    mft2 input curves exist for. The A2B side is untouched (its output
    *encoding* must stay u1.15 XYZ per the spec).
    """

    @staticmethod
    def node_lab(grid: int) -> np.ndarray:
        u = np.linspace(0.0, 1.0, grid)
        ax = icw.XYZ16_MAX * u ** 3          # grid coord u ↦ PCS value u³
        xyz1 = np.stack(np.meshgrid(ax, ax, ax, indexing="ij"),
                        -1).reshape(-1, 3)
        return xyz_to_lab(xyz1 * 100.0)

    @staticmethod
    def lab_to01(lab: np.ndarray) -> np.ndarray:
        xyz1 = lab_to_xyz(lab) / 100.0
        return np.clip(np.cbrt(xyz1 / icw.XYZ16_MAX), 0.0, 1.0)

    @staticmethod
    def b2a_in_tables(entries: int) -> np.ndarray:
        u = np.cbrt(np.linspace(0.0, 1.0, entries))
        table = np.clip(u * 0xFFFF, 0, 0xFFFF).round().astype(">u2")
        return np.tile(table, (3, 1))


def codec_for(algorithm: str, accurate: bool = False):
    if algorithm == "x":
        return XyzPcsShaped if accurate else XyzPcs
    return LabPcs
