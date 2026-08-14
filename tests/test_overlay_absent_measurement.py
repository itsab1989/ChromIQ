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


# --- no invented wording ---------------------------------------------------

def test_the_absent_case_now_opens_its_approved_window():
    """The wording went to §M-PROPOSED first, and came back approved.

    Knut, #155: *"You are inventing new messages and new functions at your own
    initiative, which is NOT allowed for an app that is released for users."* So
    the tab said its piece in the log while the text waited. On 2026-08-14 he
    approved it — *"Text approved"* — and ruled on where such things belong in
    the same review: *"all events shall have windows, and not hidden in a log
    where user will not see it."*

    Both halves matter, and this test holds both: the window exists **and** its
    text comes from the catalogue rather than being written here.
    """
    src = inspect.getsource(tab_measure.TabMeasure._on_overlay_toggled)
    start = src.index('if reason == "absent"')
    block = src[start:src.index('elif reason == "empty"')]
    assert "M_OVERLAY_NO_MEASUREMENT" in block, (
        "the window must take its text from the approved catalogue")
    assert "box.exec()" in block, "an approved event must not hide in the log"
    assert "_log.appendPlainText" not in block


def test_that_message_is_approved_in_the_catalogue():
    """A window whose text is still flagged PROPOSED would be the original
    breach wearing a catalogue entry."""
    import workflow.measurement_messages as M
    assert M.M_OVERLAY_NO_MEASUREMENT.approved is True
    assert "M-OVERLAY-NO-MEASUREMENT" not in M.PROPOSED


def test_the_approved_mismatch_wording_is_untouched():
    """§M's M-TI3-MISMATCH already states the counts and names Restore Used
    Chart. Rewriting this window's text to say the same things differently was
    the breach; the original wording stands."""
    src = inspect.getsource(tab_measure.TabMeasure._on_overlay_toggled)
    assert "Open it in Tools ▸ Inspect a measurement" in src
    assert not hasattr(tab_measure.TabMeasure, "_overlay_mismatch_detail")
