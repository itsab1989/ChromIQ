"""The printer edge note is about a paper the printer knows, for every
instrument (4.3.66 had it for the i1iO only).

When the printer's description has no paper of the chart's size, the note used
to take the default paper (A4) and measure its edge against the chart: an A2
chart on an A3+ printer was said to lose text and patches that lie well inside
the sheet. A paper the printer does not know has no known edge, so nothing is
said of it. The note stays where it is true: a paper the printer has, and the
edge a person typed in Preferences, on every paper.

No real printer is asked: the driver query is replaced.
"""
from __future__ import annotations

import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtCore import QSettings                             # noqa: E402
from PyQt6.QtWidgets import QWidget                            # noqa: E402

from tests._barbieri_fixture import write_ti1                  # noqa: E402
from workflow import measurement_messages as MM                # noqa: E402
from workflow import printer_edges as PE                       # noqa: E402

#: Every instrument the layout engine makes charts for, the Betas included.
INSTRUMENTS = ["i1", "p3", "CM", "41", "51", "SS", "CR30", "FD9", "IO2",
               "XRISIS", "B100XY"]
#: A printer that knows A4 alone and leaves 12 mm of it unprinted.
PPD = """*DefaultPageSize: A4
*PaperDimension A4/A4: "595 842"
*ImageableArea A4/A4: "34 34 561 808"
"""


class _Settings(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


@pytest.fixture(autouse=True)
def _every_beta_on(monkeypatch):
    for name in ("fd9", "i1io", "isis", "barbieri"):
        support = importlib.import_module(f"workflow.{name}.support")
        monkeypatch.setattr(support, "_latched", True)


@pytest.fixture
def printer(monkeypatch):
    monkeypatch.setattr(PE, "_query_driver",
                        lambda name, mm: PE.ppd_edges_mm(PPD, mm))


def _chart(tmp_path, instrument, paper):
    from workflow.layout_engine.chart import build_chart
    return list(build_chart(write_ti1(tmp_path / "c.ti1", 60), tmp_path / "c",
                            instrument=instrument, paper=paper,
                            dpi=100).tiff_paths)


@pytest.fixture
def both_tabs(qtbot, tmp_path, monkeypatch):
    """``(note of Print Chart, note of Create Chart)`` for a chart's pages."""
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_print import TabPrint
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_native_print_dialog", False)
    s.set("last_printer", "P")
    tp = TabPrint(s)
    monkeypatch.setattr(tp, "_refresh_printers", lambda *a, **k: None)
    qtbot.addWidget(tp)
    monkeypatch.setattr(tp, "_printer_combo", type(
        "C", (), {"currentData": lambda self: "P"})())

    class Create:
        _settings = s
        _margin_tiffs: list = []

        def window(self):
            return QWidget()

    def ask(tiffs):
        tp.load_tiffs(list(tiffs))
        create = Create()
        create._margin_tiffs = [str(t) for t in tiffs]
        return tp._edge_note_lbl.text(), TabChart._printer_edge_notice(create)
    return s, ask


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_a_paper_the_printer_does_not_know_is_not_judged_by_its_default(
        both_tabs, printer, tmp_path, instrument):
    s, ask = both_tabs
    tiffs = _chart(tmp_path, instrument, "230x320")
    print_note, create_note = ask(tiffs)
    assert not print_note, print_note
    assert create_note is None
    # the person's own edge is used on every paper, and true
    PE.set_override(s, "P", 40.0)
    print_note, create_note = ask(tiffs)
    assert print_note and print_note == create_note


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_a_paper_the_printer_knows_keeps_its_note(
        both_tabs, printer, tmp_path, instrument):
    _s, ask = both_tabs
    print_note, create_note = ask(_chart(tmp_path, instrument, "A4"))
    assert "12" in print_note and print_note == create_note
    assert MM._EDGE_SRC_PPD in print_note


@pytest.mark.parametrize("chart,knows", [
    ((210.0, 297.0), True), ((297.0, 210.0), True),      # either way round
    ((208.0, 300.0), True), ((216.0, 297.0), False),     # 5 mm, as before
    ((420.0, 594.0), False), ((100.0, 150.0), False)])
def test_only_the_charts_own_paper_says_anything(printer, chart, knows):
    edges, paper = PE.edges_for("P", chart, _Settings())
    assert edges.any() is knows
    if not knows:
        assert paper == chart


def test_a_driver_that_answers_about_another_paper_says_nothing(monkeypatch):
    """Windows: a driver that puts its own paper in place of the size asked
    for answers about that paper."""
    monkeypatch.setattr(PE, "_query_driver", lambda p, mm: (
        PE.Edges(5.0, 5.0, 5.0, 5.0, "driver"), (210.0, 297.0)))
    assert not PE.edges_for("P", (420.0, 594.0), _Settings())[0].any()
    assert PE.edges_for("P", (210.0, 297.0), _Settings())[0].any()


def test_the_persons_own_edge_is_on_the_charts_own_paper(printer):
    s = _Settings()
    PE.set_override(s, "P", 3.0)
    edges, paper = PE.edges_for("P", (420.0, 594.0), s)
    assert (edges.left, edges.source, paper) == (3.0, "override",
                                                 (420.0, 594.0))
