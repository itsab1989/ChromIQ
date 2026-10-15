"""Review of 4.3.5 beta 8: "Re-measurement Complete" patch by patch.

Guided refinement patch by patch (#211) counted patches in the window's first
line ("All 3 patches have been re-measured successfully.") while the
"Continue Measuring Manually" bullet under it still said "scan additional
strips" and "move between strips". In patch mode the bullet now talks about
patches; strip by strip it is unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


@pytest.fixture
def tab(tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication, QDialog, QLabel
    QApplication.instance() or QApplication([])
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    t = TabMeasure(ArgyllRunner(s), s)
    t._ti1_path = Path(tmp_path / "P" / "runs" / "run1" / "P.ti1")
    t._play_measurement_finished_once = lambda: None
    t._refine_rebuild_texts = lambda: ("Rebuild", "Build it again.")
    texts: list = []

    def fake_exec(dlg):
        texts.extend(l.text() for l in dlg.findChildren(QLabel))
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    monkeypatch.setattr(t._manager, "set_guided_strips", lambda *_: None)
    yield t, texts
    QApplication.instance().removeEventFilter(t)
    t.deleteLater()


def _open(t, texts, patches, strips):
    texts.clear()
    t._guided_refinement_active = True
    t._guided_patch_list = list(patches)
    t._strip_list = list(strips)
    t._show_all_stripes_done()
    return "\n".join(texts)


def test_patch_by_patch_the_next_steps_say_patches(tab):
    t, texts = tab
    body = _open(t, texts, ["A1", "B4", "C9"], ["A", "B", "C"])
    assert "All 3 patches have been re-measured successfully." in body
    assert "read more patches yourself" in body
    assert "move between patches" in body
    assert "click a patch in the preview to jump to it" in body
    assert "automatic patch navigation" in body
    assert "strip" not in body.lower()
    assert "—" not in body.split("What would you like")[1]


def test_one_patch(tab):
    t, texts = tab
    body = _open(t, texts, ["A1"], ["A"])
    assert "The patch has been re-measured successfully." in body
    assert "move between patches" in body


def test_strip_by_strip_keeps_the_strip_text(tab):
    t, texts = tab
    body = _open(t, texts, [], ["A", "B"])
    assert "All 2 chart strips have been re-measured successfully." in body
    assert "scan additional strips yourself" in body
    assert "move between patches" not in body
