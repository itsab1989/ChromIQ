"""#155 (Knut): a chart with no measurement is not a foreign measurement.

    *"when I now change from run 1 to run 2, the message 'This measurement was
    made for a different chart' comes. This is strange, as the chart is what I
    printed and started measurements on."*

He was right to find it strange, and his own project shows why: **run 1 has no
``.ti3`` at all.** ChromIQ was making a claim about a file that does not exist.

``_existing_ti3_for_chart`` answers ``None`` for three different situations — no
chart loaded, no measurement file, and a measurement file holding no readings —
and only the last two were told apart. The absent case fell through to the
foreign-chart branch.

This is the same shape as the fault he found in #130, where an EMPTY file was
reported as a mismatch. That fix taught the code to recognise empty; absent was
left standing behind it. Hence a test per state, so the next one cannot hide.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs import tab_measure                          # noqa: E402

TI3_WITH_READINGS = """CTI3

NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS 2
BEGIN_DATA
1 0 0 0
2 100 100 100
END_DATA
"""

TI3_EMPTY = """CTI3

NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS 0
BEGIN_DATA
END_DATA
"""


class _Tab:
    """The few attributes the reason logic touches."""

    def __init__(self, ti1=None):
        self._ti1_path = ti1

    _overlay_failure_reason = tab_measure.TabMeasure._overlay_failure_reason
    _measurement_is_empty = tab_measure.TabMeasure._measurement_is_empty
    _existing_ti3_for_chart = tab_measure.TabMeasure._existing_ti3_for_chart


def _chart(tmp_path, ti3_body=None):
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("CTI1\n")
    if ti3_body is not None:
        (tmp_path / "chart.ti3").write_text(ti3_body)
    return _Tab(ti1)


# --- the reported bug -------------------------------------------------------

def test_no_measurement_file_is_not_a_foreign_measurement(tmp_path):
    """The heart of #155. Knut's run 1 is exactly this state."""
    tab = _chart(tmp_path, ti3_body=None)
    assert tab._overlay_failure_reason() == "absent", (
        "a chart that has never been measured was reported as belonging to a "
        "different chart — this is #155")


def test_no_chart_at_all_is_also_absent(tmp_path):
    assert _Tab(None)._overlay_failure_reason() == "absent"


# --- the states it must still tell apart ------------------------------------

def test_an_empty_measurement_is_still_reported_as_empty(tmp_path):
    """#130's fix must survive #155's."""
    tab = _chart(tmp_path, ti3_body=TI3_EMPTY)
    assert tab._overlay_failure_reason() == "empty"


def test_a_measurement_that_cannot_be_paired_is_still_a_mismatch(tmp_path,
                                                                 monkeypatch):
    tab = _chart(tmp_path, ti3_body=TI3_WITH_READINGS)
    monkeypatch.setattr("workflow.measurement_report.per_patch_overlay",
                        lambda *_a, **_k: [])
    assert tab._overlay_failure_reason() == "mismatch"


def test_a_measurement_that_pairs_but_cannot_be_drawn_is_no_geometry(tmp_path,
                                                                     monkeypatch):
    tab = _chart(tmp_path, ti3_body=TI3_WITH_READINGS)
    monkeypatch.setattr("workflow.measurement_report.per_patch_overlay",
                        lambda *_a, **_k: [{"loc": "A1"}])
    assert tab._overlay_failure_reason() == "no_geometry"


def test_the_four_states_are_all_distinct():
    """Each cause needs a different answer from the user, so each needs its own
    name — that was the whole point of #130 and it now holds for four."""
    src = inspect.getsource(tab_measure.TabMeasure._on_overlay_toggled)
    for reason in ("absent", "empty", "no_geometry"):
        assert f'"{reason}"' in src, reason


# --- the message says what it compared (his second question) ----------------

def test_the_mismatch_message_shows_its_evidence():
    """Knut: *"Should maybe this message also inform the user what the basis for
    this message coming is, as the text today is not very specific?"*"""
    src = inspect.getsource(tab_measure.TabMeasure._on_overlay_toggled)
    assert "_overlay_mismatch_detail" in src


def test_the_evidence_names_both_counts(tmp_path):
    tab = _chart(tmp_path, ti3_body=TI3_WITH_READINGS)
    (tmp_path / "chart.ti2").write_text(TI3_WITH_READINGS.replace("CTI3", "CTI2"))
    detail = tab_measure.TabMeasure._overlay_mismatch_detail(tab)
    assert "2" in detail, detail


def test_the_evidence_never_raises_on_missing_files(tmp_path):
    """It sits inside a message box; it must never be the thing that fails."""
    tab = _chart(tmp_path, ti3_body=None)
    assert tab_measure.TabMeasure._overlay_mismatch_detail(tab)


def test_the_absent_message_does_not_mention_a_different_chart():
    src = inspect.getsource(tab_measure.TabMeasure._on_overlay_toggled)
    start = src.index('if reason == "absent"')
    block = src[start:src.index('elif reason == "empty"')]
    assert "different chart" not in block
    assert "not been measured yet" in block
