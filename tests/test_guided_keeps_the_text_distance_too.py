"""The distance from the paper edge must reach GUIDED, which is where it was
reported.

Knut's report of 2026-09-10 was a **Guided** CR30 chart with hexagon patches:
*"Right says 5.8 mm but text goes to the edge almost."* The fix that followed
read the setting off `params.layout_recipe`, and only `_collect_manual` ever
attaches one (`ui/tabs/tab_chart.py:19991`). `_collect_guided` never has. So the
fix closed the Manual half of his report and left the half he actually sent,
which a challenge round caught by driving four Guided builds and recording
`text_edge_mm: 0.0` every time while Manual passed 7.5 correctly.

Guided has no control for this, so it gets the DEFAULT of the setting, which is
what he asked for:

> the text needs to stay within the default "Text distance from edge" settings
> in preferences chart layout. **For all sides, for Guided mode. Not a hardwired
> margin.**

A printtarg chart still passes zero, deliberately: nothing in that path ever had
the setting, and changing it would move text on charts that print correctly
today.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

from workflow import tiff_metadata as tm
from workflow.chart_creator import ChartParams
from workflow.layout_engine.presets import LayoutRecipe

from tests.test_chart_creator import _make_creator


def _sheet(tmp_path: Path):
    creator, _ = _make_creator(tmp_path)
    run = creator._file_mgr.project().current_run()
    run.ensure_dir()
    (run.dir / f"{run.stem}.ti1").write_text("NUMBER_OF_SETS 484\n", encoding="utf-8")
    tiff = run.dir / f"{run.stem}_01.tif"
    tifffile.imwrite(str(tiff), np.zeros((100, 100, 3), np.uint8),
                     resolution=(200, 200), resolutionunit="INCH")
    return creator, run, tiff


def _edge_passed(creator, tiff, params, monkeypatch) -> float:
    seen: list[float] = []
    monkeypatch.setattr(
        tm, "stamp_chart_metadata",
        lambda tiffs, lines, edge=0.0, band=0.0: seen.append(float(edge)))
    creator._stamp_tiff_metadata([tiff], params)
    assert seen, "the stamper was never called"
    return seen[0]


def test_a_guided_engine_chart_gets_the_default_distance(tmp_path, monkeypatch):
    creator, run, tiff = _sheet(tmp_path)
    got = _edge_passed(
        creator, tiff,
        # Guided: is_manual False, and no layout_recipe, exactly as
        # `_collect_guided` builds it.
        ChartParams(target_name=run.stem, device_type="2", is_manual=False,
                    instrument="CR30", stamp_commands=True),
        monkeypatch)
    assert got == LayoutRecipe().text_edge_clip_mm, got
    assert got > 0.0, "Guided is back to letting the note run to the paper edge"


def test_manual_still_uses_the_users_own_number(tmp_path, monkeypatch):
    creator, run, tiff = _sheet(tmp_path)
    got = _edge_passed(
        creator, tiff,
        ChartParams(target_name=run.stem, device_type="2", is_manual=True,
                    instrument="CR30", stamp_commands=True,
                    layout_recipe=LayoutRecipe(text_edge_clip_mm=7.5)),
        monkeypatch)
    assert got == 7.5, got


def test_a_printtarg_chart_still_passes_zero(tmp_path, monkeypatch):
    """Deliberate. Nothing in that path ever had the setting, and giving it one
    would move text on charts that print correctly today."""
    creator, run, tiff = _sheet(tmp_path)
    got = _edge_passed(
        creator, tiff,
        ChartParams(target_name=run.stem, device_type="2", is_manual=True,
                    instrument="i1", stamp_commands=True),
        monkeypatch)
    assert got == 0.0, got
