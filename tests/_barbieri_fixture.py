"""Shared helpers for the Barbieri Spectro 100xy chart tests (a Beta)."""
from __future__ import annotations

import random
from pathlib import Path


def srgb_xyz(r: float, g: float, b: float) -> "tuple[float, float, float]":
    def lin(c):
        c = c / 100.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    R, G, B = lin(r), lin(g), lin(b)
    return (100 * (0.4124 * R + 0.3576 * G + 0.1805 * B),
            100 * (0.2126 * R + 0.7152 * G + 0.0722 * B),
            100 * (0.0193 * R + 0.1192 * G + 0.9505 * B))


def write_ti1(path: Path, n: int, seed: int = 7) -> Path:
    """An RGB .ti1 of *n* patches: white, black, then random colours."""
    rnd = random.Random(seed)
    rows = [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)]
    while len(rows) < n:
        rows.append(tuple(round(rnd.uniform(0, 100), 3) for _ in range(3)))
    lines = ["CTI1   ", "", 'DESCRIPTOR "Argyll Calibration Target chart '
             'information 1"', 'ORIGINATOR "Argyll targen"',
             'CREATED "Sat Oct  3 01:27:48 2026"',
             'APPROX_WHITE_POINT "95.106486 100.000000 108.844025"',
             'COLOR_REP "RGB"', "", "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z ",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(rows[:n], start=1):
        x, y, z = srgb_xyz(r, g, b)
        lines.append(f"{i} {r:.4f} {g:.4f} {b:.4f} {x:.5f} {y:.5f} {z:.5f} ")
    lines.append("END_DATA")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def barbieri_on():
    """A context: the Beta on for this process, restored afterwards."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        from workflow.barbieri import support
        before = support._latched
        support.set_enabled_for_this_process(True)
        try:
            yield
        finally:
            support._latched = before
    return _ctx()
