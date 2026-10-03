"""A calibration chart is laid out in order, never shuffled (#182).

calibration_run_type §4.2: the calibration knobs switch printtarg's ``-r``
(do not randomise) on. With the ChromIQ layout engine and a layout recipe,
the engine took ``randomize`` from the RECIPE, not from ``-r``, so the
diagnosis drive of 2026-10-03 found the calibration ramps scattered over the
sheet (patch 77 at D8, 78 at C2, 79 at B8) with ``RANDOM_START`` in the .ti2,
and the help card's "a plain ramp of one ink channel at a time" was false.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_creator import ChartCreator, ChartParams  # noqa: E402


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


class _FM:
    def __init__(self, root: Path):
        self.root = root


def _ramps_ti1(path: Path, steps: int = 8) -> int:
    """What targen -d2 -f0 -e0 -B0 -s N writes: one shared white, then the
    R, G and B ramps of N-1 steps each (3N-2 patches)."""
    rows = [(100.0, 100.0, 100.0)]
    for ch in range(3):
        for k in range(1, steps):
            v = 100.0 - 100.0 * k / (steps - 1)
            rgb = [100.0, 100.0, 100.0]
            rgb[ch] = v
            rows.append(tuple(rgb))
    data = "\n".join(f"{i} {r:.4f} {g:.4f} {b:.4f} {r:.4f} {g:.4f} {b:.4f}"
                     for i, (r, g, b) in enumerate(rows, 1))
    path.write_text(
        'CTI1\n\nORIGINATOR "Argyll targen"\nCOLOR_REP "iRGB"\n\n'
        "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n{data}\nEND_DATA\n",
        encoding="utf-8")
    return len(rows)


def _recipe():
    from workflow.layout_engine.presets import LayoutRecipe
    # The layout panel's own default: randomise ON.
    return LayoutRecipe(instrument="i1", paper="A4", randomize=True)


def test_a_calibration_build_is_never_randomised(tmp_path):
    creator = ChartCreator(object(), _FM(tmp_path), _Settings())
    for recipe in (_recipe(), None):
        kw = creator._engine_kwargs(ChartParams(
            instrument="i1", paper="A4", layout_recipe=recipe,
            no_randomise=False, cal_target=True))
        assert kw["randomize"] is False, f"shuffled with recipe={recipe!r}"


def test_a_profiling_build_still_follows_the_recipe(tmp_path):
    creator = ChartCreator(object(), _FM(tmp_path), _Settings())
    kw = creator._engine_kwargs(ChartParams(
        instrument="i1", paper="A4", layout_recipe=_recipe(),
        cal_target=False))
    assert kw["randomize"] is True


def test_the_calibration_ti2_runs_in_order(tmp_path):
    from workflow.layout_engine import chart as le_chart

    ti1 = tmp_path / "Test-cal.ti1"
    n = _ramps_ti1(ti1)
    creator = ChartCreator(object(), _FM(tmp_path), _Settings())
    kw = creator._engine_kwargs(ChartParams(
        instrument="i1", paper="A4", layout_recipe=_recipe(), cal_target=True))
    kw["dpi"] = 72
    le_chart.build_chart(ti1, tmp_path / "Test-cal", **kw)
    text = (tmp_path / "Test-cal.ti2").read_text(encoding="latin-1")
    assert "RANDOM_START" not in text and "CHART_ID" in text
    body = text.split("BEGIN_DATA\n", 1)[1].split("END_DATA", 1)[0]
    locs = [m.group(1) for m in re.finditer(r'^\d+ "([^"]+)"', body, re.M)]
    assert len(locs) >= n
    # SAMPLE_ID order is location order: strip by strip, patch by patch.
    steps = int(re.search(r'STEPS_IN_PASS "(\d+)"', text).group(1))
    m = re.search(r'STRIP_INDEX_PATTERN "([^"]*)"', text)
    p = re.search(r'PATCH_INDEX_PATTERN "([^"]*)"', text)
    from workflow.layout_engine import permutation as perm
    expected = [perm.location_label(i, steps, m.group(1), p.group(1))
                for i in range(len(locs))]
    assert locs == expected, "the calibration patches are not in order"
