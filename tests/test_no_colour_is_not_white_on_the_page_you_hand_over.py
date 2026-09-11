"""A patch with no expected colour must not draw a white block.

`_swatch` fell back to `#ffffff` for an empty hex. On the full report that was
hidden, because the cube-corner table checked `expected_hex` itself and printed
a dash instead. The one-page colour summary — the document Knut asked for so a
user has something to hand to a customer — built its two swatch columns without
that check, so every patch of a chart with no reference drew a white block under
"Asked for". The page then said the chart asked for white and the printer made
something else.

That state is not exotic. §9.1 of the design refuses to invent a reference for a
converted chart whose colorimetric reference file is missing: the report gets no
ΔE at all rather than a plausible number from the wrong yardstick. Those are
exactly the patches whose expected colour is absent.

The rule now lives in `_swatch` itself, so a third table cannot be written
without it, and it renders the same nothing the ΔE column renders.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ui.dialogs.measurement_report_dialog import _fmt, _swatch


def test_an_absent_colour_renders_as_nothing_not_as_white():
    assert _swatch("") == _fmt(None)
    assert _swatch(None) == _fmt(None)          # type: ignore[arg-type]
    assert "#ffffff" not in _swatch("")


def test_a_real_colour_still_draws_a_block():
    out = _swatch("#ff0000")
    assert "background-color:#ff0000" in out
    assert out.startswith("<span")


def test_white_is_still_drawn_when_it_is_the_answer():
    """The fallback is gone, not the colour: a patch that really is white must
    still show a white block, or the paper-white row would read as unmeasured."""
    assert "background-color:#ffffff" in _swatch("#ffffff")


def _page(dlg, corner: dict, tmp: Path) -> str:
    rep = {"schema": 7, "report_type": "t1_colour_summary",
           "corners": [corner], "summary_patches": [], "de": {},
           "created": "2026-09-11T10:00:00", "_origin_dir": str(tmp)}
    return dlg._one_page_html([rep])


def test_the_one_page_summary_draws_no_white_block_for_a_missing_reference(
        tmp_path, qapp, report_dialog):
    """THE PAGE, not the helper: the regression was in the table, and a helper
    test alone would have passed while the page was wrong."""
    html = _page(report_dialog, {"name": "W", "present": True,
                                 "hex": "#f8f8f4"}, tmp_path)
    assert "#f8f8f4" in html, "the measured colour is still shown"
    assert "#ffffff" not in html, \
        "a patch with no expected colour drew white under 'Asked for'"


def test_and_draws_both_when_the_reference_is_there(tmp_path, qapp, report_dialog):
    html = _page(report_dialog, {"name": "R", "present": True,
                                 "hex": "#c81e1e", "expected_hex": "#e02020",
                                 "de": 3.4}, tmp_path)
    assert "background-color:#e02020" in html
    assert "background-color:#c81e1e" in html


@pytest.fixture
def report_dialog(qapp):
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    d = Path(tempfile.mkdtemp())
    st = AppSettings()
    st._qs = QSettings(str(d / "s.ini"), QSettings.Format.IniFormat)
    dlg = MeasurementReportDialog(st, None)
    yield dlg
    dlg.close()
