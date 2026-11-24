"""The owner, during the 4.3.39 integration: "the cr30 does not need spacers
either". Three notes depend on an instrument finding its patches by the
colour change between neighbours along a strip: the no-spacer note, "Keep very
dark patches away from very light ones" (R7) and the short-patch note (R6).
One registry answers it (`instruments.FINDS_PATCHES_BY_EDGES`); this test lists
EVERY registered instrument, so a new one fails here until it is classified,
and proves on the CR30 that none of the three can appear or act.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from workflow.layout_engine import instruments as I

EXPECTED = {
    # found by colour edges along a strip
    "i1": True, "p3": True, "CM": True, "41": True, "51": True,
    # read by position or patch by patch
    "SS": False, "CR30": False, "FD9": False, "IO2": False, "XRISIS": False,
    # the Barbieri Spectro 100xy (a Beta): the table moves to each patch
    "B100XY": False,
}


def _every_registered_instrument() -> set:
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel as LP
    from workflow.chart_creator import ENGINE_INSTRUMENTS
    keys = set(I.TARGET_INSTRUMENT_NAME) | set(I.supported())
    keys |= set(ENGINE_INSTRUMENTS)
    keys |= {k for k, _ in LP.INSTRUMENTS}
    keys |= {LP.FD9_INSTRUMENT[0], LP.I1IO_INSTRUMENT[0],
             LP.ISIS_INSTRUMENT[0], LP.BARBIERI_INSTRUMENT[0]}
    return keys


def test_every_registered_instrument_is_classified():
    keys = _every_registered_instrument()
    missing = keys - set(I.FINDS_PATCHES_BY_EDGES)
    assert not missing, f"classify in instruments.FINDS_PATCHES_BY_EDGES: {missing}"
    assert set(I.FINDS_PATCHES_BY_EDGES) == keys


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_each_instrument_is_on_its_side(key):
    assert I.finds_patches_by_edges(key) is EXPECTED[key]
    assert I.FINDS_PATCHES_BY_EDGES == EXPECTED


def test_an_unknown_instrument_gets_no_note():
    assert I.finds_patches_by_edges("nonsense") is False
    assert I.finds_patches_by_edges(None) is False


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_the_short_patch_minimum_is_only_its_own(key):
    from workflow import patch_size_check as P
    lo = P.min_patch_length_mm(key)
    if not EXPECTED[key]:
        assert lo is None
    assert P.judge(key, [3.0]) is None or EXPECTED[key]


TARGEN = shutil.which("targen") or "/Applications/Argyll/bin/targen"


@pytest.mark.parametrize("spacers", [True, False])
def test_the_cr30_gets_none_of_the_three(tmp_path, spacers):
    """The CR30's chart, in fixed order, with R7 asked for and spacers on
    or off: R7 moves nothing, and neither note is made."""
    if not Path(TARGEN).exists():
        pytest.skip("ArgyllCMS targen not available")
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.chart import build_chart
    subprocess.run([TARGEN, "-v0", "-d2", "-f120", str(tmp_path / "t")],
                   check=True, capture_output=True, timeout=120)
    r = build_chart(tmp_path / "t.ti1", tmp_path / "c", instrument="CR30",
                    paper="A4", seed=1, dpi=72, randomize=False,
                    spacer_on=spacers,
                    spacer_mode="colored" if spacers else "none",
                    avoid_dark_light_neighbours=True)
    assert not r.neighbour_moves and not r.neighbour_patches_moved
    assert r.slots is None
    (tmp_path / "c.channels.json").write_text(json.dumps({"layout": {
        "engine": "chromiq", "dpi": 72, "margins_chosen_by_user": False,
        "recipe": {"instrument": "CR30", "spacer_on": spacers,
                   "spacer_mode": "colored" if spacers else "none"},
        "patches": [{"loc": "A1", "h": 10}]}}), encoding="utf-8")
    lines = []
    fake = SimpleNamespace(_margin_ti2=r.ti2_path,
                           _log=SimpleNamespace(appendPlainText=lines.append))
    assert TabChart._alike_neighbours_note(fake) is None
    assert TabChart._short_patch_note(fake) is None
    assert lines == []


def test_the_spectroscan_reads_by_position_and_gets_no_spacer():
    """The owner: "spectroscan also needs no spacers i think". Confirmed: the
    layout engine's SpectroScan geometry, read from printtarg.c, has no patch
    spacer and no strip spacer (pspa = tspa = 0), because its XY table moves
    the head to each patch from the chart's reference points; it is on the
    "reads by position" side, so none of the three notes applies."""
    g = I.build("SS")
    assert g.pspa == 0.0 and g.tspa == 0.0
    assert I.finds_patches_by_edges("SS") is False
    assert "SS" in I.READ_PATCH_BY_PATCH
