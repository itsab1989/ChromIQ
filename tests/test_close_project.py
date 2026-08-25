"""Closing a project changes nothing on disk (#164, Basti).

*"add that button … when one is opened ask for confirmation in a pop up window
- info friendly extensive, easy to understand"*

The whole point of this button is that it is SAFE: every run, chart,
measurement and profile stays exactly where it is, and "Open Project" brings it
all back. So the thing to prove is not that it works — it is that it destroys
nothing, and that a half-close cannot happen.
"""
import hashlib
import os
import pathlib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


def _snapshot(root: pathlib.Path) -> dict:
    return {str(f): hashlib.sha1(f.read_bytes()).hexdigest()
            for f in sorted(root.rglob("*")) if f.is_file()}


@pytest.fixture
def win_with_project(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))
    settings.set("session_project", "")
    w = MainWindow(settings)
    qapp.processEvents()
    w._file_mgr.set_target_name("Close Test")
    w._file_mgr.project().current_run().ensure_dir()
    w._refresh_masthead_availability()
    yield w, tmp_path
    w.close()


def test_closing_deletes_nothing(win_with_project):
    """Not one byte moves. This is the promise the confirmation makes."""
    win, root = win_with_project
    before = _snapshot(root)
    win.close_current_project()
    after = _snapshot(root)
    assert after == before, (
        f"closing changed the disk: {len(set(after) - set(before))} added, "
        f"{len(set(before) - set(after))} removed")


def test_closing_leaves_no_project_named(win_with_project):
    """And nothing may invent one afterwards — `get_target_name()` would."""
    win, _root = win_with_project
    win.close_current_project()
    assert win._file_mgr._target_name == ""
    assert win._file_mgr.has_project() is False
    assert win._file_mgr.is_named() is False


def test_the_button_greys_itself_once_there_is_nothing_left_to_close(
        win_with_project):
    win, _root = win_with_project
    assert win._masthead._close_project_btn.isEnabled() is True
    win.close_current_project()
    assert win._masthead._close_project_btn.isEnabled() is False


def test_cancelling_the_confirmation_changes_nothing(win_with_project,
                                                     monkeypatch):
    """The dialog defaults to Cancel, so this is the likeliest path of all."""
    from PyQt6.QtWidgets import QMessageBox

    win, root = win_with_project
    before = _snapshot(root)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: None)
    win._on_masthead_close_project()
    assert win._file_mgr.is_named() is True, "Cancel closed the project anyway"
    assert _snapshot(root) == before


def _observable_state(w):
    """Everything a user could tell the two journeys apart by."""
    return {
        "guided_name": w._tab_chart._target_name_edit.text(),
        "manual_name": w._tab_chart._manual_target_name_edit.text(),
        "tab": w._tabs.currentIndex(),
        "location": w._target_ctl.location_being_edited(),
        "close_enabled": w._masthead._close_project_btn.isEnabled(),
        "is_named": w._file_mgr.is_named(),
        "has_project": w._file_mgr.has_project(),
    }


def test_delete_and_close_land_in_the_same_place(qapp, tmp_path):
    """An app with two different "no project" states is one the user cannot
    predict.

    COMPARED BY OBSERVATION, not by source text. The previous version asserted
    that both methods mention `_reset_after_project_gone` — which would pass on
    a comment, and says nothing about whether the two actually agree.
    """
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    def _fresh(name):
        s = AppSettings()
        s.set("custom_output_path", str(tmp_path / name))
        s.set("session_project", "")
        s.set("restore_last_session", False)
        w = MainWindow(s)
        qapp.processEvents()
        w._file_mgr.set_target_name("Same Place")
        w._file_mgr.project().current_run().ensure_dir()
        w._target_ctl.changed.emit()
        qapp.processEvents()
        return w

    a = _fresh("close_side")
    b = _fresh("delete_side")
    try:
        a.close_current_project()
        qapp.processEvents()
        b._on_project_deleted()
        qapp.processEvents()

        after_close, after_delete = _observable_state(a), _observable_state(b)
        assert after_close == after_delete, (
            "closing and deleting leave the app in different states:\n"
            f"  close : {after_close}\n  delete: {after_delete}")
    finally:
        a.close()
        b.close()


def test_the_outgoing_settings_are_written_before_the_selection_clears(
        win_with_project, monkeypatch):
    """Moving the selection to nothing is still moving it, and per-target
    settings are recorded when a target is LEFT. A delete does not need this —
    the target is going away — but a close does, or the last edit before
    closing is silently lost."""
    win, _root = win_with_project
    order = []
    for tab in (win._tab_chart, win._tab_measure, win._tab_profile):
        if hasattr(tab, "save_target_settings"):
            monkeypatch.setattr(tab, "save_target_settings",
                                lambda *a, t=tab, **k: order.append(("save", t)))
    real = win._reset_after_project_gone
    monkeypatch.setattr(win, "_reset_after_project_gone",
                        lambda **k: (order.append(("reset", None)), real(**k)))
    win.close_current_project()
    assert order, "nothing happened at all"
    kinds = [k for k, _t in order]
    assert "reset" in kinds, "the reset never ran"
    assert "save" in kinds, "no tab was asked to record its settings"
    # Everything BEFORE the reset must be a save. (There may be saves after it
    # too — clearing a tab can trigger one — so checking the last entry would
    # measure the wrong end; the first version of this test did exactly that.)
    first_reset = kinds.index("reset")
    assert first_reset > 0, (
        "the reset ran before any settings were written — the last edit made "
        "before closing is silently lost")
    assert set(kinds[:first_reset]) == {"save"}


def test_the_confirmation_has_no_question_mark_icon(win_with_project, monkeypatch):
    """Basti, #164: *"i want this questionmark symbol removed from the pop
    up"*. The heading already asks the question; the glyph only squeezed the
    explanation into a narrow column."""
    from PyQt6.QtWidgets import QMessageBox

    seen = {}

    def _capture(self):
        seen["icon"] = self.icon()
        return 0

    win, _ = win_with_project
    monkeypatch.setattr(QMessageBox, "exec", _capture, raising=False)
    win._on_masthead_close_project()
    assert seen["icon"] is QMessageBox.Icon.NoIcon, (
        f"the confirmation still shows the {seen['icon']!r} glyph")


def test_close_project_button_carries_the_magenta_accent(win_with_project, monkeypatch):
    """Basti, #164: *"the close button should get the magenta accent color"*."""
    from PyQt6.QtWidgets import QMessageBox

    seen = {}

    def _capture(self):
        for b in self.buttons():
            if "close" in b.text().lower():
                seen["qss"] = b.styleSheet()
        return 0

    win, _ = win_with_project
    monkeypatch.setattr(QMessageBox, "exec", _capture, raising=False)
    win._on_masthead_close_project()
    qss = seen.get("qss", "").lower()
    assert "ff4573" in qss or "c2185b" in qss, (
        "the Close project button is not painted in the app's magenta accent; "
        f"its stylesheet is {seen.get('qss')!r}")


def test_the_accent_matches_the_generate_chart_button():
    """Basti, #164: *"styled like the generate chart button in create chart
    module (that punchy magenta and white text on it)"*.

    Consistency is the requirement, so this asserts the button is painted from
    the SAME tokens the Create Chart tab uses for `QPushButton#primary` — the
    tab's own accent and the app's per-theme label colour — rather than from a
    second set of magentas that could drift apart from it.

    On the contrast: white on this magenta measures 3.3:1, under WCAG AA's
    4.5:1 for normal text. That is the app's own shipped primary-action colour
    on every tab, chosen deliberately for consistency; dark mode flips the
    label to near-black and measures 6.0:1. Recorded here so nobody "fixes"
    the light-mode pair in isolation and leaves this button unlike every other
    primary button in ChromIQ.
    """
    from PyQt6.QtGui import QColor

    from ui.styles import TAB_COLORS

    accent = TAB_COLORS[0]

    def _lum(hexcode):
        c = QColor(hexcode)

        def _ch(v):
            v /= 255.0
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

        return (0.2126 * _ch(c.red()) + 0.7152 * _ch(c.green())
                + 0.0722 * _ch(c.blue()))

    def _ratio(a, b):
        la, lb = sorted((_lum(a), _lum(b)))
        return (lb + 0.05) / (la + 0.05)

    assert _ratio("#0a0a0a", accent) >= 4.5, (
        "dark mode's near-black label no longer clears AA on the accent")
    assert 3.0 <= _ratio("#ffffff", accent) < 4.5, (
        "light mode's contrast moved — if the accent changed, revisit this "
        "deliberate consistency-over-contrast choice with Basti")


def test_the_button_uses_the_theme_correct_label_colour(qapp, monkeypatch):
    """White on light, near-black on dark — the flip is what keeps it legible,
    and it is the app's rule, not a local invention.

    BOTH themes are exercised. An earlier version read only the theme the suite
    happened to run under, and a mutation that hard-coded the dark label sailed
    through it.
    """
    from PyQt6.QtWidgets import QPushButton

    from ui.widgets import accent_message_box_button

    for appearance, expected in (("light", "#ffffff"), ("dark", "#0a0a0a")):
        monkeypatch.setattr("ui.theme.resolve_mode", lambda _s, a=appearance: a)
        btn = QPushButton("Close project")
        accent_message_box_button(btn)
        qss = btn.styleSheet().lower()
        assert f"color: {expected}" in qss, (
            f"{appearance} mode should label the button {expected}; got {qss!r}")
