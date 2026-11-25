"""Item 74, P5: the computer is kept awake while a table session is open, and never after it."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_4367_every_ending_offers_the_homing import (
    PRESSES, _open, _press, _to_the_ending)
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (fixture)
from ui import i1io_table_window as W


@pytest.fixture
def awake(monkeypatch):
    from core import keep_awake as ka

    class Fake:
        held, log = False, []

        def hold(self):
            self.held = True
            self.log.append("hold")
            return True

        def release(self):
            self.held = False
            self.log.append("release")
    f = Fake()
    f.log = []
    monkeypatch.setattr(ka, "keep_awake", f)
    return f


def test_nothing_is_held_before_start_and_everything_during_it(
        qtbot, monkeypatch, tmp_path, settings, awake):  # noqa: F811
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    assert p.page() == "prepare" and awake.log == []
    p.drive_until("aimed")
    assert awake.held and awake.log == ["hold"]


@pytest.mark.parametrize("how", list(PRESSES))
@pytest.mark.parametrize("home", [True, False])
def test_every_ending_releases_it(qtbot, monkeypatch, tmp_path, settings, awake,  # noqa: F811
                                  how, home):
    win, sim, run, p, saved, finished = _open(qtbot, monkeypatch, tmp_path, settings, "row_failed")
    assert awake.held
    _to_the_ending(win, p, (how, how))
    p.press("Discard and stop")
    assert awake.held                         # the arm is out: the homing is still to come
    if home:
        p.press("Bring the arm home, my hands are away")
    else:
        p.press("Not now")
        assert awake.held
        p.press("Close")
    p.idle()
    assert not awake.held and awake.log.count("release") >= 1


def test_not_started_and_never_held_is_not_released(qtbot, monkeypatch, tmp_path, settings,  # noqa: F811
                                                    awake):
    """A hand measurement's own hold is not the table's to release."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    win._on_close_pressed()
    p.idle()
    assert finished and awake.log == []


def test_a_deleted_panel_releases_it(qtbot, monkeypatch, tmp_path, settings, awake):  # noqa: F811
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("aimed")
    W.retire_window(win)
    assert not awake.held


def test_a_failure_of_it_is_never_in_the_way(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    from core import keep_awake as ka

    class Broken:
        def hold(self):
            raise OSError("no")
        release = hold
    monkeypatch.setattr(ka, "keep_awake", Broken())
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    assert p.drive_until("aimed") == "aimed"
