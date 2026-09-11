"""Hexagonal charts work with the scanner tools (they used to be refused).

The refusal said the CHT format "can only describe rectangular patch boxes — it
has no way to express a hexagon". True of the printed shape, and beside the
point: a CHT carries the SAMPLING RECTANGLE inside each patch, and
`cht_writer.boxes_from_patch_rects` takes those from the chart's recorded
per-patch geometry, which already carries the hexagons' row stagger.

Measured end to end before the refusal was removed, on a 150-hexagon 12 mm
chart: the target built, real `scanin` returned 0 with a standard deviation of
0.106, and real `colprof` produced a profile (peak error 0.59, average 0.20).

What genuinely fails is scanin's AUTO-recognition — a hexagon has no horizontal
edges for its YLIST.

**The sentence that used to follow was wrong, and it is worth saying how.** It
read "…and ChromIQ never uses it: the four corners are placed by hand on the
alignment mesh". ChromIQ does use it: the Auto align button's first step IS
scanin's recogniser (`workflow.scan_placement.place_grid`), and measured on a
honeycomb it returns nothing with zero candidates, so the button declined and
moved the corners 0.0 px while the same drive on a rectangular chart of the
same 648 colours landed 0.6 px from truth. The claim conflated "scanin's
recogniser is not the thing that reads the patches" — true — with "nothing in
ChromIQ asks it where the chart is" — false. Auto align now has a second step 1
for exactly this case (`workflow.hex_block_search`,
`tests/test_auto_align_finds_a_honeycomb.py`); hand placement is no longer the
only way to align a honeycomb.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _hex_chart(tmp_path, n=120, w_mm=12.0):
    from workflow.layout_engine import chart as le_chart
    ti1 = tmp_path / "p.ti1"
    lines = ["CTI1", "", 'DESCRIPTOR "x"', 'ORIGINATOR "x"', 'KEYWORD "SAMPLE_LOC"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    lines += [f"{i+1} {float((i*37) % 101)} {float((i*53) % 101)} "
              f"{float((i*71) % 101)} 40 45 50" for i in range(n)]
    lines += ["END_DATA", ""]
    ti1.write_text("\n".join(lines), encoding="utf-8")
    stem = tmp_path / "HexChart"
    le_chart.build_chart(ti1, stem, instrument="SS", hflag=True,
                         pscale=w_mm / 7.0, paper="A4", border=6.0, dpi=200,
                         randomize=False)
    strips = json.loads(stem.with_suffix(".strips.json").read_text(encoding="utf-8"))
    (tmp_path / "HexChart.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"],
        "layout": {"engine": "chromiq", "dpi": 200, "paper_mm": [210.0, 297.0],
                   "patches": strips["patches"],
                   "recipe": {"instrument": "SS", "hflag": True}}}), encoding="utf-8")
    return stem, [p for p in strips["patches"] if p["page"] == 0]


def test_a_hexagonal_chart_has_scanner_geometry(tmp_path):
    """The geometry layer never objected — only the dialogs did."""
    from workflow.scanin_target import has_scanner_geometry
    stem, _ = _hex_chart(tmp_path)
    assert has_scanner_geometry(tmp_path / "HexChart.channels.json") is True


def test_the_cht_boxes_are_the_recorded_patch_rects(tmp_path):
    """The sampling rectangles come from the chart's own geometry, so they carry
    the stagger and sit inside their hexagons — no shape assumption anywhere."""
    from workflow.layout_engine import cht_writer
    stem, patches = _hex_chart(tmp_path)
    boxes = cht_writer.boxes_from_patch_rects(patches, 297.0, 200, page=0)
    assert len(boxes) == len(patches)
    assert {b["loc"] for b in boxes} == {p["loc"] for p in patches}


def test_the_mesh_cells_take_the_patch_shape(qapp, tmp_path):
    """Only the DRAWING changes: the rects, and so the sampled area, are
    identical whether the chart is hexagonal or not."""
    from ui.scan_grid_marquee import GridSpec
    _stem, patches = _hex_chart(tmp_path)
    flat = GridSpec.from_patches(patches)
    hexy = GridSpec.from_patches(patches, hexagonal=True)
    assert flat.hexagonal is False and hexy.hexagonal is True
    assert flat.rects == hexy.rects, "the sampled geometry must not move"


def test_the_drawn_cell_is_a_hexagon(qapp, tmp_path):
    """A hexagonal cell must not cover its box's corners — they belong to the
    neighbours, which is the whole reason to draw the true shape.

    TWO WRONG VERSIONS BEFORE THIS ONE, and they failed in opposite directions.

    The first read `inspect.getsource(_cell_uv)` and counted the substring
    `"(cxu,"`. It passed for the right reason on the day it was written and went
    red the moment the six vertices MOVED into `layout_engine/hexagon.py` — the
    shape unchanged, the assertion broken, which is what every source-text
    assertion eventually does.

    The second asked `hexagon.vertices` directly and asserted nothing about the
    mesh at all. A review proved it vacuous: with `_cell_uv` made to emit
    rectangles for a hexagonal grid, the entire everyday tier passed, 12,322
    tests green. Testing the library the code calls is not testing the code.

    This one asks the real `ScanGridMarquee` for its real mesh and counts what
    comes back.
    """
    import numpy as np
    from ui.scan_grid_marquee import ScanGridMarquee
    from ui.scan_grid_marquee import GridSpec

    _stem, patches = _hex_chart(tmp_path)
    grid = GridSpec.from_patches(patches, hexagonal=True)
    flat = GridSpec.from_patches(patches, hexagonal=False)

    def mesh(g):
        m = ScanGridMarquee.__new__(ScanGridMarquee)
        m._grid = g
        m._cell_uv_cache = None
        m._sample_frac = 0.5
        return m._cell_uv()

    hu, hv, hstride = mesh(grid)
    fu, fv, fstride = mesh(flat)

    # A HEX CELL CARRIES TWO MORE POINTS THAN A SQUARE ONE. This is the
    # assertion the vacuous version did not make: it is about the mesh.
    assert fstride == 4 + 4, f"a rectangular cell should contribute 8, not {fstride}"
    assert hstride == 6 + 4, f"a hexagonal cell should contribute 10, not {hstride}"
    ncells = len(grid.rects)
    assert len(hu) == ncells * hstride, "the mesh is not one stride per cell"
    assert len(hu) > len(fu), (
        "the hexagonal mesh has no more points than the rectangular one, so "
        "_cell_uv is drawing boxes for a honeycomb"
    )

    # ...and the six are a hexagon, not four corners with two repeats: the two
    # apexes must lie OUTSIDE the cell, on its centre line.
    for c in range(min(6, ncells)):
        u, v, w, hh = grid.rects[c]
        cell = list(zip(hu[c * hstride:c * hstride + 6],
                        hv[c * hstride:c * hstride + 6]))
        ys = [pt[1] for pt in cell]
        assert min(ys) < v - 1e-12, f"cell {c}: no apex above the box"
        assert max(ys) > v + hh + 1e-12, f"cell {c}: no apex below the box"
        corners = [(u, v), (u + w, v), (u + w, v + hh), (u, v + hh)]
        for px, py in cell:
            assert not any(abs(px - cxx) < 1e-9 and abs(py - cyy) < 1e-9
                           for cxx, cyy in corners), (
                f"cell {c}: {(px, py)} is a box corner, which belongs to a "
                "neighbouring patch")


class _Store:
    def __init__(self, on):
        self._on = on

    def get(self, key, default=None):
        return self._on if key == "scanner_hex_charts" else default


def test_the_default_is_the_long_proven_behaviour():
    """Off: a hexagonal chart is turned away, exactly as it always has been.
    No existing user's scanner workflow changes."""
    from workflow.hex_support import hex_scanner_allowed
    assert hex_scanner_allowed(_Store(False)) is False


def test_the_beta_switch_opens_it():
    from workflow.hex_support import hex_scanner_allowed
    assert hex_scanner_allowed(_Store(True)) is True


def test_anything_that_cannot_read_the_setting_gets_the_proven_path():
    """A missing or broken settings store must not open the door — the failure
    mode has to fall towards what is known to work."""
    from workflow.hex_support import hex_scanner_allowed

    class Broken:
        def get(self, *_a, **_k):
            raise RuntimeError("no store")

    assert hex_scanner_allowed(None) is False
    assert hex_scanner_allowed(Broken()) is False
    assert hex_scanner_allowed(object()) is False


def test_the_refusal_no_longer_claims_it_is_impossible(tmp_path):
    """The old text said every CHT feature was unavailable for these charts.
    That was wrong, and it told users to rebuild the chart for no reason.

    It then went one worse: it asked the user to "keep the Sample area at or
    below 60 %" — advice that only appears in the message the people who are
    NOT using the feature get, and that is now a computed cap the app applies
    itself. A refusal may state what is unproven; it may not hand out a manual
    workaround for something the code already handles."""
    from workflow.hex_support import hex_scanner_message
    msg = hex_scanner_message()
    low = msg.lower()
    assert "impossible" not in low and "cht format" not in low
    assert "cannot" not in low.replace("cannot work", "").replace(
        "cannot reach", ""), "no capability claim beyond the two known ones"
    # The user is told where the switch is, and nothing else is asked of them.
    assert "beta" in low and "preferences" in low
    for workaround in ("60 %", "60%", "at or below", "keep the sample area"):
        assert workaround not in low, (
            f"{workaround!r}: the sample-area cap is computed and applied "
            "(scanin_runner.hex_max_sample_fraction) — it must not be advice, "
            "least of all advice shown only to users who cannot get here")
    # And it says what genuinely is not proven: finding the chart unaided.
    assert "corners" in low
    assert len(msg) > 400, "a refusal this surprising needs explaining properly"


@pytest.mark.parametrize("allowed,expect_rejected", [(False, True), (True, False)])
def test_the_target_dialog_obeys_the_setting(qapp, tmp_path, monkeypatch,
                                             allowed, expect_rejected):
    """Called for real, not grepped for. A source check that only looks for the
    helper's NAME passes even when the call is replaced by `if True:` — which is
    exactly the mutation that would silently ship the ungated behaviour."""
    import types

    import ui.dialogs.scanin_target_dialog as std
    from ui.dialogs.scanin_target_dialog import ScaninTargetDialog

    stem, _ = _hex_chart(tmp_path, n=30)
    shown = []
    # STUB THE FUNCTION THE CODE CALLS, not `QMessageBox.warning`.
    # Every warning in this app now goes through `ui.warning_sign.warn` so it
    # can carry ChromIQ's own sign, and each module imports that name into its
    # own globals — so `<module>.warn` is the thing to replace. Stubbing the
    # static instead lets a REAL modal open in the headless suite; the
    # conftest watchdog catches it after 4 s and fails the test, which is how
    # this was found.
    monkeypatch.setattr(std, "warn", lambda *a, **k: shown.append(a) or 0)
    fake = types.SimpleNamespace(_settings=_Store(allowed))
    rejected = ScaninTargetDialog._reject_if_hexagonal(fake, stem)
    assert rejected is expect_rejected
    assert bool(shown) is expect_rejected, (
        "a refusal must explain itself, and an acceptance must stay quiet")


def test_the_dialogs_ask_the_setting_before_refusing(tmp_path):
    """Gated, not deleted and not hard-wired: both dialogs must consult the
    beta switch, and the Create Chart heads-up must fall silent when it is on."""
    import inspect
    import ui.dialogs.scanin_dialog as sd
    import ui.dialogs.scanin_target_dialog as std
    import ui.tabs.tab_chart as tc
    for mod in (sd, std, tc):
        src = inspect.getsource(mod)
        assert "hex_scanner_allowed" in src, (
            f"{mod.__name__} does not consult the beta setting")
        assert "hex_unsupported_message" not in src, (
            f"{mod.__name__} still uses the old, false message")
