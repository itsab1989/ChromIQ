"""Owner's question (2026-11-15): on a chart WITHOUT spacers, whites stood
next to whites and blacks next to blacks; how can that be read? Nothing marks
the edge between two such patches. ChromIQ now says so (M-CHART-ALIKE-NO-
SPACER in the Create Chart log and the frame's info, its panel line on the
Measured from Preview surface), never refuses, greys or moves anything, and
says nothing while spacers are drawn (a spacer between two patches always
differs from both: two whites get a black one, two blacks a white one)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from workflow.layout_engine import contrast
from workflow.layout_engine.neighbour_order import alike_pairs_in_ti2

TARGEN = shutil.which("targen") or "/Applications/Argyll/bin/targen"


def _chart(tmp, spacer_mode, randomize=False):
    if not Path(TARGEN).exists():
        pytest.skip("ArgyllCMS targen not available")
    from workflow.chart_creator import ChartCreator  # noqa: F401 (import check)
    from workflow.layout_engine.chart import build_chart
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.run([TARGEN, "-v0", "-d2", "-f120", str(tmp / "t")], check=True,
                   capture_output=True, timeout=120)
    r = build_chart(tmp / "t.ti1", tmp / "c", instrument="i1", paper="A4",
                    seed=1, dpi=72, randomize=randomize,
                    spacer_on=spacer_mode != "none", spacer_mode=spacer_mode)
    import json
    (tmp / "c.channels.json").write_text(json.dumps({"layout": {
        "engine": "chromiq", "dpi": 72, "recipe": {
            "instrument": "i1", "spacer_on": spacer_mode != "none",
            "spacer_mode": spacer_mode}}}), encoding="utf-8")
    return r.ti2_path


def test_targens_whites_and_blacks_are_counted(tmp_path):
    ti2 = _chart(tmp_path, "none")
    # targen: 4 whites then 4 blacks, so at least 3 + 3 identical pairs
    assert alike_pairs_in_ti2(ti2) >= 6


def _note(ti2):
    from ui.tabs.tab_chart import TabChart
    lines = []
    fake = SimpleNamespace(_margin_ti2=ti2,
                           _log=SimpleNamespace(appendPlainText=lines.append))
    out = TabChart._alike_neighbours_note(fake)
    return out, lines, fake


def test_said_without_spacers_and_once_in_the_log(tmp_path):
    out, lines, fake = _note(_chart(tmp_path, "none"))
    assert out is not None
    full, panel = out
    assert "cannot tell where one ends" in full and "switch the spacers on" in full
    assert panel.startswith("⚠ No spacers") and "Pairs the instrument cannot tell apart:" in panel
    assert len(lines) == 1
    from ui.tabs.tab_chart import TabChart
    TabChart._alike_neighbours_note(fake)
    assert len(lines) == 1                      # once per chart


def test_silent_with_spacers(tmp_path):
    out, lines, _f = _note(_chart(tmp_path, "colored"))
    assert out is None and lines == []


def test_a_spacer_between_two_identical_patches_differs_from_both():
    for mode in ("colored", "bw"):
        assert contrast.spacer_for_mode(mode, (255, 255, 255),
                                        (255, 255, 255)) == (0, 0, 0)
        assert contrast.spacer_for_mode(mode, (0, 0, 0),
                                        (0, 0, 0)) == (255, 255, 255)
        g = (128, 128, 128)
        assert contrast.spacer_for_mode(mode, g, g) != g


def test_nothing_is_moved_or_greyed():
    src = (Path(__file__).resolve().parents[1] / "ui/tabs/tab_chart.py"
           ).read_text(encoding="utf-8")
    i = src.index("def _alike_neighbours_note")
    blk = src[i:src.index("def _short_patch_note", i)]
    assert "setEnabled" not in blk and "slots" not in blk
