"""Create Chart: a strip or patch pattern the readers cannot read back turns
the box red, says why under the preview and holds Generate Chart off, and
nothing else happens.

Forum report, 2026-10-03 (strip pattern "0-9", 14 strips, a chart nobody
could measure), and Knut's ruling the same day (#182 5965589190): ChromIQ
labels as ArgyllCMS does, letters or numbers on either side, so what is
refused is what ArgyllCMS itself cannot read back: too few labels for the
chart, or a strip and a patch label that run together.

The fields fire on every keystroke, so the way to "0-9,@-9;1-99" passes
through "0", "0-" and "0-9," and each of those must not open a window, write a
log line or start a build.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QMessageBox
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    def _no_window(*_a, **_k):
        raise AssertionError("a window opened while a pattern was typed")
    monkeypatch.setattr(QMessageBox, "exec", _no_window)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    s.set("auto_update_preview", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    for name in ("_auto_preview_timer", "_cmd_preview_timer"):
        timer = getattr(t, name, None)
        if timer is not None:
            timer.stop()
    t.deleteLater()


def _type(tab, box, text):
    """Type *text* into *box* one character at a time, as a person does,
    letting the tab react after every keystroke."""
    box.setText("")
    for ch in text:
        box.insert(ch)
        tab._refresh_manual_command_preview()
        yield box.text()


def _red(box) -> bool:
    return "#d9534f" in box.styleSheet() or "border: 2px" in box.styleSheet()


def test_typing_through_the_half_patterns_opens_nothing_and_builds_nothing(
        tab, monkeypatch):
    builds: list = []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda *a, **k: builds.append(a) or True,
                        raising=False)
    panel = tab._manual_layout_panel
    log_before = tab._log.toPlainText()
    seen = []
    for text in _type(tab, panel.strip_pat, "0-9,@-9;1-99"):
        seen.append((text, tab._pattern_problem is not None,
                     tab._auto_preview_timer.isActive()))
    # every state on the way was judged, none of them scheduled a re-layout
    # while it was refused, and nothing was written to the log
    assert all(not active for _t, bad, active in seen if bad), seen
    assert builds == []
    assert tab._log.toPlainText() == log_before
    # the half-typed "0-" is a pattern ArgyllCMS reads as the symbols 0 and -,
    # which cannot number a chart: red on the way
    assert any(bad for t, bad, _a in seen if t in ("0", "0-", "0-9"))


def test_a_refused_pattern_is_red_says_why_and_holds_generate_off(tab):
    panel = tab._manual_layout_panel
    panel.strip_pat.setText("A-Z;1-999")         # ArgyllCMS refuses it outright
    tab._refresh_manual_command_preview()
    assert _red(panel.strip_pat)
    assert not tab._pattern_problem_lbl.isHidden()
    assert "A-Z;1-999" in tab._pattern_problem_lbl.text()
    assert "—" not in tab._pattern_problem_lbl.text()
    btn = tab._generate_btn
    assert not btn.isEnabled(), "Generate must be held off"
    assert btn.wanted_enabled(), "…by the gate, not by a build"
    assert not tab._chart_build_in_flight(), \
        "a refused pattern is not a build in flight"


def test_a_build_finishing_does_not_release_the_gate(tab):
    panel = tab._manual_layout_panel
    panel.strip_pat.setText("A-Z;1-999")
    tab._refresh_manual_command_preview()
    tab._generate_btn.setEnabled(False)          # a build starts...
    tab._generate_btn.setEnabled(True)           # ...and finishes
    assert not tab._generate_btn.isEnabled()


def test_a_good_pattern_releases_it(tab):
    panel = tab._manual_layout_panel
    panel.strip_pat.setText("A-Z;1-999")
    tab._refresh_manual_command_preview()
    panel.strip_pat.setText("A-Z, A-Z")
    tab._refresh_manual_command_preview()
    assert not _red(panel.strip_pat)
    assert tab._pattern_problem_lbl.isHidden()
    assert tab._generate_btn.isEnabled()


@pytest.mark.parametrize("strip,patch", [
    ("0-9,@-9;1-99", "A-Z"),       # numbered strips, lettered patches (Knut)
    ("A-Z, A-Z", "0-9,@-9,@-9;1-999"),
    ("A-Z", "0-9,@-9;1-99"),
])
def test_patterns_argyll_reads_back_are_not_refused(tab, strip, patch):
    panel = tab._manual_layout_panel
    panel.strip_pat.setText(strip)
    panel.patch_pat.setText(patch)
    tab._refresh_manual_command_preview()
    assert tab._pattern_problem is None, tab._pattern_problem
    assert tab._generate_btn.isEnabled()


def test_a_stored_pattern_that_cannot_be_used_loads_unchanged_and_red(tab):
    from workflow.layout_engine.presets import LayoutRecipe
    panel = tab._manual_layout_panel
    r = panel.get_recipe()
    r.strip_pattern = "A-Z;1-999"
    panel.set_recipe(r)
    tab._refresh_manual_command_preview()
    assert panel.strip_pat.text() == "A-Z;1-999", "never rewritten"
    assert panel.get_recipe().strip_pattern == "A-Z;1-999"
    assert _red(panel.strip_pat)
    assert not tab._generate_btn.isEnabled()
    assert isinstance(r, LayoutRecipe)


def test_the_keyboard_shortcut_is_refused_too(tab, monkeypatch):
    panel = tab._manual_layout_panel
    panel.strip_pat.setText("A-Z;1-999")
    tab._refresh_manual_command_preview()
    started: list = []
    monkeypatch.setattr(tab, "_log_chart_build",
                        lambda *a, **k: started.append(a), raising=False)
    tab._on_generate()
    assert started == [], "Generate must not start a build"
    assert "A-Z;1-999" in tab._log.toPlainText()


def test_guided_is_not_held_off_by_a_manual_pattern(tab):
    panel = tab._manual_layout_panel
    panel.strip_pat.setText("A-Z;1-999")
    tab._refresh_manual_command_preview()
    tab._switch_mode("guided")
    assert tab._generate_btn.isEnabled()
