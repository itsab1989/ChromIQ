"""The edge of the paper a printer does not print, and what of a chart falls
into it (Basti, 2026-10-25, from jctay's forum post 149836: the ruler helper
markers of his 100 x 150 mm chart were missing on the SELPHY's paper, and the
text at the bottom was cut). No real printer is ever asked: the driver query
is replaced by a fake one, and the PPD is a file written here."""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402
from PIL import Image                                          # noqa: E402

from workflow import measurement_messages as MM               # noqa: E402
from workflow import printer_edges as PE                      # noqa: E402

DPI = 100
PX = 25.4 / DPI

#: A SELPHY-like page: 100 x 148 mm postcard, 3 mm unprinted all round.
PPD = """*PPD-Adobe: "4.3"
*DefaultPageSize: Postcard
*PaperDimension Postcard/Postcard: "283.46 419.53"
*ImageableArea Postcard/Postcard: "8.50 8.50 274.96 411.03"
*PaperDimension A4/A4: "595 842"
*ImageableArea A4/A4: "12 12 583 830"
"""


class _Settings(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def _page(tmp_path: Path, markers=(2.0, 2.0), text_bottom=4.0) -> Path:
    """A 100 x 150 mm page: dashes along the top and bottom *markers[0]* mm in
    and *markers[1]* mm long, a block of 'text' *text_bottom* mm above the
    bottom edge, a patch block in the middle; with the sidecar overhang reads
    the markers' recipe from."""
    w, h = round(100 / PX), round(150 / PX)
    a = np.full((h, w, 3), 255, np.uint8)
    e, ln = markers
    for x_mm in range(10, 95, 4):
        x = round(x_mm / PX)
        a[round(e / PX):round((e + ln) / PX), x:x + 1] = 0
        a[h - round((e + ln) / PX):h - round(e / PX), x:x + 1] = 0
    a[h - round((text_bottom + 1.5) / PX):h - round(text_bottom / PX),
      round(20 / PX):round(60 / PX)] = 0
    a[round(20 / PX):round(130 / PX), round(15 / PX):round(90 / PX)] = 80
    p = tmp_path / "c_01.tif"
    Image.fromarray(a).save(p, dpi=(DPI, DPI))
    (tmp_path / "c.channels.json").write_text(json.dumps({"layout": {"recipe": {
        "helper_markers": True, "helper_marker_edge_mm": e,
        "helper_marker_len_mm": ln, "helper_markers_top_bottom": True,
        "helper_markers_sides": False}}}), encoding="utf-8")
    return p


def test_the_ppd_gives_the_edge_of_the_matching_paper():
    edges, paper = PE.ppd_edges_mm(PPD, (100.0, 150.0))
    assert paper == pytest.approx((100.0, 148.0), abs=0.1)
    assert edges.left == pytest.approx(3.0, abs=0.05)
    assert edges.top == pytest.approx(3.0, abs=0.05)
    assert edges.source == "ppd"


def test_the_preferences_value_wins_over_the_printer(monkeypatch):
    monkeypatch.setattr(PE, "_query_driver", lambda p, c: (
        PE.Edges(0, 0, 0, 0, "driver"), (100.0, 148.0)))
    s = _Settings()
    assert not PE.edges_for("Capture_A44", (100, 150), s)[0].any()
    PE.set_override(s, "Capture_A44", 3.5)
    e, paper = PE.edges_for("Capture_A44", (100, 150), s)
    assert (e.left, e.bottom, e.source) == (3.5, 3.5, "override")
    assert paper == (100.0, 148.0)
    PE.set_override(s, "Capture_A44", None)
    assert PE.edges_for("Capture_A44", (100, 150), s)[0].source == "driver"


def test_his_markers_and_bottom_text_are_named(tmp_path, monkeypatch):
    monkeypatch.setattr(PE, "_query_driver",
                        lambda p, c: PE.ppd_edges_mm(PPD, c))
    page = _page(tmp_path)
    edges, paper = PE.edges_for("Capture_A44", (100, 150), _Settings())
    loss = PE.losses_for_chart([(page, 0)], edges, paper)
    assert loss.markers.get("top") and loss.markers.get("bottom"), loss
    assert loss.text.get("bottom"), loss
    note = MM.edge_note("Capture_A44", edges, loss)
    assert "Capture_A44" in note and "ruler helper markers at the top" in note
    assert "Distance from page edge" in note and "Text distance from edge" in note
    assert "—" not in note


def test_markers_moved_in_far_enough_are_not_named(tmp_path, monkeypatch):
    monkeypatch.setattr(PE, "_query_driver",
                        lambda p, c: PE.ppd_edges_mm(PPD, c))
    page = _page(tmp_path, markers=(5.0, 3.0), text_bottom=8.0)
    edges, paper = PE.edges_for("Capture_A44", (100, 150), _Settings())
    loss = PE.losses_for_chart([(page, 0)], edges, paper)
    assert not loss.any(), loss
    assert MM.edge_note("Capture_A44", edges, loss) is None


def test_no_printer_and_no_edge_say_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(PE, "_query_driver", lambda p, c: None)
    e, _paper = PE.edges_for("", (100, 150), _Settings())
    assert not e.any()


def test_choosing_a_printer_refreshes_create_chart_at_once():
    import inspect
    from ui.tabs.tab_print import TabPrint
    src = inspect.getsource(TabPrint._on_printer_changed)
    assert "_update_margin_inspector()" in src


def test_patches_in_the_edge_are_named_and_never_called_safe(tmp_path,
                                                             monkeypatch):
    """Review of 4.3.14: with a margin narrower than the printer's edge the
    note called the patches "printed text" and said "Nothing your instrument
    measures is in it"."""
    monkeypatch.setattr(PE, "_query_driver",
                        lambda p, c: PE.ppd_edges_mm(PPD, c))
    w, h = round(100 / PX), round(150 / PX)
    a = np.full((h, w, 3), 255, np.uint8)
    # patches from 1 mm to 140 mm down, 15 to 90 mm across: the top 2 mm of
    # them are in the 3 mm edge (plus the 1 mm the 148 mm paper takes)
    a[round(1 / PX):round(140 / PX), round(15 / PX):round(90 / PX)] = 80
    page = tmp_path / "p_01.tif"
    Image.fromarray(a).save(page, dpi=(DPI, DPI))
    edges, paper = PE.edges_for("Capture_A44", (100, 150), _Settings())
    loss = PE.losses_for_chart([(page, 0)], edges, paper)
    assert loss.patches == ["top"], loss
    assert not loss.text, loss
    note = MM.edge_note("Capture_A44", edges, loss)
    assert "patches at the top" in note
    assert "Nothing your instrument measures" not in note
    assert "cannot read patches" in note and "Margins (mm)" in note


def test_each_fix_names_what_that_part_needs(tmp_path, monkeypatch):
    """Review of 4.3.14: the text fix said "by at least 5.0 mm" on a chart
    whose text was 1 mm into the edge, because every fix took the deepest
    amount of all."""
    monkeypatch.setattr(PE, "_query_driver",
                        lambda p, c: PE.ppd_edges_mm(PPD, c))
    page = _page(tmp_path, markers=(0.5, 2.0), text_bottom=2.5)
    edges, paper = PE.edges_for("Capture_A44", (100, 150), _Settings())
    loss = PE.losses_for_chart([(page, 0)], edges, paper)
    assert loss.need_markers > loss.need_text > 0, loss
    note = MM.edge_note("Capture_A44", edges, loss)
    import math
    want_m = math.ceil(loss.need_markers * 2 - 1e-9) / 2
    want_t = math.ceil(loss.need_text * 2 - 1e-9) / 2
    assert f"by at least {want_m:.1f} mm" in note.split("Move the text")[0]
    assert f"by at least {want_t:.1f} mm" in note.split("Move the text")[1]
