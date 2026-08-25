"""Close Project must record the outgoing target's settings from EVERY tab.

`close_current_project` flushed a hand-written triple — Create Chart, Measure,
Build Profile — and silently omitted Print Chart. So a Rendering-intent change
made on the Print tab was lost by Close Project, while the same change made
anywhere else survived. The tab switch inside `_reset_after_project_gone`
cannot rescue it: `close_project()` has already run by then, so
`store_for_target` returns None.

Contradicts per_target_settings.md §3 W6 ("leaving a tab — including a target
change"), which `close_current_project`'s own docstring cites.
"""
import pytest


@pytest.fixture
def win(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    w = MainWindow(s)
    qapp.processEvents()
    w._file_mgr.set_target_name("Flush Test")
    w._file_mgr.project().current_run().ensure_dir()
    w._target_ctl.changed.emit()
    qapp.processEvents()
    yield w
    w.close()


def test_every_tab_that_can_save_is_asked_to(win, qapp):
    """Driven, not read: each tab's real saver is counted as Close runs."""
    asked = []
    for i in range(win._tabs.count()):
        tab = win._tabs.widget(i)
        saver = getattr(tab, "save_target_settings", None)
        if not callable(saver):
            continue
        name = type(tab).__name__

        def _spy(*a, _n=name, _real=saver, **k):
            asked.append(_n)
            return _real(*a, **k)

        tab.save_target_settings = _spy

    win.close_current_project()
    qapp.processEvents()

    assert "TabPrint" in asked, (
        f"the Print Chart tab was never asked to save; only {asked} were")
    # …and it is not just Print — every saver must be reached.
    for expected in ("TabChart", "TabMeasure", "TabProfile", "TabPrint"):
        assert expected in asked, f"{expected} was not flushed (got {asked})"
