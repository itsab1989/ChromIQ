"""M-I1IO-NOT-YET TELLS THE TRUTH SINCE THE TABLE MEASURES (4.3.47).

Since 4.3.45 START drives the i1iO table for every i1iO 2 + i1Pro 2 chart that
has its ChromIQ side file ``<stem>.i1io.json`` (the positions of the patches
and marks). The chart that still gets M-I1IO-NOT-YET is one without that file,
and the window kept saying the table "cannot measure with it yet ... being
prepared for a later version". Now it says what is missing, how to make a
chart the table can measure, and the way by hand; and it no longer appends the
paragraph on where to aim the table on this sheet, which the table cannot
measure.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_beta_option import _chart, i1io_on, measure_tab  # noqa: E402,F401
from workflow import measurement_messages as M  # noqa: E402

_STALE = ("cannot measure with it yet", "later version", "not available")


@pytest.mark.parametrize("msg", [M.M_I1IO_NOT_YET, M.M_I1IO_NOT_YET_BY_HAND])
def test_the_text_no_longer_says_the_table_cannot_measure_yet(msg):
    title, body = msg.render()
    for stale in _STALE:
        assert stale not in (title + body), stale
    # what is missing, and why the table needs it
    assert ".i1io.json" in body
    assert "where every patch and every aiming mark lies" in body
    # how to make a chart the table measures, with the names the app shows
    assert "Create Chart tab" in body and "“i1iO 2 + i1Pro 2”" in body
    assert "Start Measurement" in body
    # and the way by hand
    assert "“i1Pro / i1Pro 2 / i1Pro 3”" in body and "by hand" in body
    assert "—" not in title + body
    assert msg.approved is False


def test_a_profiling_chart_names_load_patch_set_for_its_own_patches():
    body = M.M_I1IO_NOT_YET.render()[1]
    assert "“Load patch set”" in body and "“.ti1”" in body
    assert "Generate Chart" in body


def _shown(tab, monkeypatch):
    shown = []
    monkeypatch.setattr(type(tab), "_i1io_window",
                        lambda self, t, b: shown.append((t, b)))
    tab._i1io_not_yet_window()
    assert len(shown) == 1
    return shown[0]


def test_without_a_side_file_the_window_has_no_aiming_paragraph(
        measure_tab, tmp_path, monkeypatch):
    ti2 = _chart(tmp_path)
    measure_tab.set_ti1_path(ti2.with_suffix(".ti1"))
    title, body = _shown(measure_tab, monkeypatch)
    want_title, want_body = M.M_I1IO_NOT_YET.render()
    assert (title, body) == (want_title, want_body)
    assert "Good to know for later" not in body


def test_with_a_readable_side_file_the_aiming_paragraph_stays(
        measure_tab, tmp_path, monkeypatch):
    ti2 = _chart(tmp_path)
    ti2.with_name("iochart.i1io.json").write_text(json.dumps({}),
                                                 encoding="utf-8")
    measure_tab.set_ti1_path(ti2.with_suffix(".ti1"))
    title, body = _shown(measure_tab, monkeypatch)
    # 4.3.50: the file IS there, so the window says so (never "has no such file")
    assert body.startswith(M.M_I1IO_NOT_YET_SIDE_FILE.render()[1] + "\n\n")
    assert "Good to know for later" in body
