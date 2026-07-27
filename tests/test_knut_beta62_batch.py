"""#131 (Knut, 2026-07-27, testing beta.62): four fixes and one ruling.

His log settled two of them, and both were faults in my own earlier fixes:

* **Skip Strip still did not move.** `{"cmd": "next_unread"}` was sent and
  accepted — but he was re-reading a chart that is already complete, and there
  is no unread strip to go to. "Skip" can only mean *the next strip* there.
* **Retry still inflated the next strip's time.** Clearing the clock was not
  enough: the slot that reports the failed strip's time was connected AFTER the
  one that opens the failure window, and that window blocks inside its own slot
  — so the timing ran only once he had answered it.
"""
from __future__ import annotations

import inspect
import json

import pytest

from workflow.measure_manager import MeasureManager


class _Runner:
    def __init__(self):
        self.stdin = []

    def write_stdin(self, data):
        self.stdin.append(data)

    def __getattr__(self, _name):
        return lambda *a, **k: None


@pytest.fixture
def manager():
    m = MeasureManager(_Runner())
    m._engine_active = True
    return m


def _sent(manager):
    return [json.loads(s) for s in manager._runner.stdin]


# ---- Skip Strip -----------------------------------------------------------
def test_skip_goes_to_the_next_unread_while_anything_is_unread(manager):
    manager._strip_read_state = {"A": True, "B": False, "C": False}

    manager.skip_current_strip()

    assert _sent(manager) == [{"cmd": "next_unread"}]


def test_skip_goes_to_the_next_strip_on_a_complete_chart(manager):
    """His case: refining a finished measurement. "Next unread" has nowhere to
    go, so the engine stayed put and the arrow never moved."""
    manager._strip_read_state = {"A": True, "B": True, "C": True}

    manager.skip_current_strip()

    assert _sent(manager) == [{"cmd": "forward"}]


def test_an_unknown_read_state_still_moves(manager):
    """No session map yet — better to move on than to do nothing."""
    manager._strip_read_state = {}
    manager.skip_current_strip()
    assert _sent(manager) == [{"cmd": "forward"}]


def test_reading_a_strip_updates_what_skip_will_do(manager):
    manager._strip_read_state = {"A": False, "B": False}
    manager._handle_engine_line(
        json.dumps({"event": "strip_read", "strip": "A", "patches": []}),
        lambda _s: None)
    assert manager._strip_read_state["A"] is True


def test_the_session_map_seeds_the_read_state(manager):
    manager._handle_engine_line(json.dumps({
        "event": "session_start",
        "strips": [{"strip": "A", "read": True}, {"strip": "B", "read": False}],
    }), lambda _s: None)
    assert manager._strip_read_state == {"A": True, "B": False}


def test_stock_chartread_keeps_its_own_route(manager):
    manager._engine_active = False
    manager.skip_current_strip()
    assert manager._runner.stdin == ["\r"]


# ---- the failure timing ---------------------------------------------------
def test_the_timing_slot_runs_before_the_window_slot():
    """Connection order IS the behaviour: the window blocks inside its slot."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.__init__)
    pace = src.index("strip_error.connect(self._report_failed_strip_pace)")
    window = src.index("strip_error.connect(self._on_strip_error)")
    assert pace < window, (
        "the failed strip is timed after the window is answered, so the time "
        "includes however long the window was open")


# ---- the overlay after loading a project ----------------------------------
def test_a_remembered_overlay_is_painted_when_a_chart_is_loaded():
    """The box came up ticked and the preview stayed empty until it was
    toggled off and on again."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    marker = "ocb.setVisible(has_ti3); otip.setVisible(has_ti3)"
    assert marker in src
    after = src[src.index(marker):src.index(marker) + 700]
    assert "_restore_overlay_after_measurement()" in after


# ---- the outlier fence is a switch now (his option (c)) --------------------
def test_the_fence_is_a_setting_that_governs_both_modes():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._use_outlier_fence)
    assert '"patch_warn_outlier_fence"' in src
    assert "True" in src, "it must default to today's behaviour"


def test_the_setting_exists_with_the_right_default(tmp_path):
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    assert s.get("patch_warn_outlier_fence", None) is True


# ---- the hover tile names the standard ------------------------------------
def test_the_hover_tile_says_which_delta_e_it_is():
    """"ΔE" alone says neither the formula nor the white point, and there are
    several of each."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "ui" / "tiff_preview.py").read_text()
    assert "ΔE*ab" in src
    assert "CIE76" in src and "D50" in src


# ---- Calibration Required has a way out -----------------------------------
def test_the_calibration_window_offers_a_cancel():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_calibration_prompt)
    assert 'tr("Cancel Measurement")' in src
    assert "btn_box.rejected.connect(dlg.reject)" in src
