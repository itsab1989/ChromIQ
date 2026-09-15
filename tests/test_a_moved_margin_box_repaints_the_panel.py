"""Moving a layout box has to change the sentence on the panel.

`_engine_text_notes` states its own contract in its docstring: the collision
"is predicted here from the recipe, because the user has to be told **while
they are still moving the spin boxes**, and the only raster that could report
it is one they have already committed to building".

It was not. Nothing refreshed the "Measured from Preview" frame on a LAYOUT
change. `_refresh_manual_command_preview` is the single hook every targen row,
every printtarg row and the whole layout panel routes through, and it called
`_maybe_schedule_auto_preview` (which does nothing at all unless the user has
opted into the live preview, and `auto_update_preview` ships **False**) and
`_refresh_unapplied_warning` (which repaints a different label). The panel's
own notices stood frozen at the last build.

`_on_chart_settings_touched` was given the missing call on 2026-09-13 for
exactly this reason, for the chart-notes box and the stamp tick. Its docstring
says what was measured then: *"toggling the tick, 0 refreshes, six times out of
six; typing a 336-character note, 0 refreshes. So the warning arrived a rebuild
late, and clearing the notes left the red message standing until something else
happened to repaint."* The other twenty controls were left behind.

MEASURED ON SCREEN, 2026-09-15, in the real window, with a real Generate and
then eleven real keyboard and mouse gestures
(`scripts/adv23e_the_notice_after_every_gesture.py`): i1Pro, A4, one 24 pt
line of sheet text, bottom margin 8 mm. In **8 of the 11** the sentence the
frame was really showing was not the sentence the state had earned. Holding Up
until "Bottom" read 14.0 mm, which is past the 5.5 mm rise the message itself
names, left the red warning standing word for word; typing 60 into Size left it
saying the text needs 10.3 mm where the state needs 25.7. The same driver run
in a worktree at v4.3.0-beta.16 gives the same 8 of 11, so this is older than
the bottom-text work and not part of it.

The cost was measured BEFORE the call was added, because this hook fires on
every keystroke of every Manual row (`scripts/adv23f_what_a_panel_refresh_
costs.py`): one refresh is 8.5 to 20.3 ms median across both layout modes, with
and without sheet text, at 24 and 72 pt; worst single pass 63.7 ms. The sibling
call was accepted at 17.2 ms.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    s.set("auto_update_preview", False)      # the shipped default
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    t.deleteLater()


def test_a_layout_change_repaints_the_measured_from_preview_frame(tab,
                                                                  monkeypatch):
    """A margin box moves, and the frame is asked for a fresh report.

    MUTATION: delete the `_update_margin_inspector()` call from
    `_refresh_manual_command_preview` and this goes red with 0 refreshes,
    which is the state v4.3.0-beta.16 shipped in.
    """
    calls: list[int] = []
    monkeypatch.setattr(type(tab), "_update_margin_inspector",
                        lambda self: calls.append(1), raising=True)
    # A chart in the preview is the guard: the frame shows a placeholder and
    # returns without one, so a keystroke before anything is built must cost
    # nothing.
    tab._margin_tiffs = []
    tab._refresh_manual_command_preview()
    assert calls == [], (
        "the panel was refreshed with no chart in the preview, which is the "
        "one case the guard exists for")

    tab._margin_tiffs = ["a-chart.tif"]
    tab._refresh_manual_command_preview()
    assert calls == [1], (
        "moving a layout box did not refresh the 'Measured from Preview' "
        "frame, so its notices describe the last build and not the boxes "
        "being moved")


def test_the_layout_panel_really_routes_through_that_hook(tab):
    """The hook only helps if the layout panel is wired to it.

    Belt and braces: the fix above is worth nothing if a later change moves
    the layout panel's signal somewhere else.
    """
    src = inspect.getsource(type(tab)._build_manual_page) \
        if hasattr(type(tab), "_build_manual_page") else \
        inspect.getsource(inspect.getmodule(type(tab)))
    assert "_manual_layout_panel.changed.connect(" \
           "self._refresh_manual_command_preview)" in src.replace("\n", ""), (
        "the layout panel no longer routes its changes through "
        "_refresh_manual_command_preview, so the panel refresh added there "
        "cannot fire")


def test_the_refresh_is_guarded_on_there_being_a_chart():
    """The call must stay behind the `_margin_tiffs` guard.

    Unguarded it runs on every keystroke of a freshly started app, before any
    chart exists, and `_update_margin_inspector` would do its whole placeholder
    pass each time.
    """
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._refresh_manual_command_preview)
    body = src[src.index("_refresh_unapplied_warning()"):]
    i = body.index("self._update_margin_inspector()")
    assert "_margin_tiffs" in body[:i], (
        "the panel refresh in _refresh_manual_command_preview is not guarded "
        "on there being a chart to measure")
