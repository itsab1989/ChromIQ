"""TI2 editor 'randomised tag' redesign: auto-tag when safe, force-override
otherwise.

On save the editor tags a well-mixed chart as randomised automatically; a
structured one is left untagged unless the user ticks 'Force randomised tag',
which then shows a (suppressible) risk warning. The force checkbox is enabled
only while the current preview layout is judged unsafe. These tests drive that
glue without ArgyllCMS by feeding the analyzer synthetic .ti2 files.
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import DEFAULTS  # noqa: E402
import workflow.ti2_relayout as R  # noqa: E402
from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication(sys.argv)


class _StubSettings:
    def __init__(self, **overrides):
        self._d = dict(DEFAULTS)
        self._d.update(overrides)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


@pytest.fixture
def dlg():
    s = _StubSettings()
    return Ti2RelayoutDialog(ArgyllRunner(s), s)


_HEAD = (
    'CTI2\n\nORIGINATOR "t"\nTARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n'
    'COLOR_REP "iRGB"\nCHART_ID "2"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
    "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
)


def _ti2(tmp_path: Path, strips: dict, name="chart.ti2") -> Path:
    rows, sid = [], 0
    for letter, seq in strips.items():
        for i, (r, g, b) in enumerate(seq, start=1):
            sid += 1
            rows.append(f'{sid} "{letter}{i}" {r:.1f} {g:.1f} {b:.1f} 0 0 0')
    p = tmp_path / name
    p.write_text(_HEAD + f"NUMBER_OF_SETS {sid}\nBEGIN_DATA\n"
                 + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    return p


_SAFE = {
    "A": [(100, 0, 0), (0, 100, 0), (0, 0, 100)],
    "B": [(100, 100, 0), (0, 100, 100), (100, 0, 100)],
    "C": [(50, 50, 50), (90, 10, 10), (10, 90, 90)],
}
_UNSAFE = {  # two identical strips -> confusable
    "A": [(100, 0, 0), (0, 100, 0), (0, 0, 100)],
    "B": [(100, 0, 0), (0, 100, 0), (0, 0, 100)],
}


def _set_preview(dlg, ti2: Path) -> None:
    dlg._regen = types.SimpleNamespace(ti2=ti2)
    dlg._update_force_tag_state()


# --- enabled-state follows the preview's safety ----------------------------

def test_force_checkbox_disabled_when_safe(dlg, tmp_path):
    _set_preview(dlg, _ti2(tmp_path, _SAFE))
    assert dlg._pt_force_tag.isEnabled() is False


def test_force_checkbox_enabled_when_unsafe(dlg, tmp_path):
    _set_preview(dlg, _ti2(tmp_path, _UNSAFE))
    assert dlg._pt_force_tag.isEnabled() is True


# --- save-time tagging decisions -------------------------------------------

def test_safe_layout_auto_tagged(dlg, tmp_path):
    ti2 = _ti2(tmp_path, _SAFE)
    note = dlg._maybe_tag_randomised(ti2)
    assert "RANDOM_START" in ti2.read_text(encoding="utf-8")
    assert "automatically" in note.lower() or "bidirectional" in note.lower()


def test_unsafe_unforced_left_untagged(dlg, tmp_path):
    dlg._pt_force_tag.setChecked(False)
    ti2 = _ti2(tmp_path, _UNSAFE)
    note = dlg._maybe_tag_randomised(ti2)
    assert "RANDOM_START" not in ti2.read_text(encoding="utf-8")
    assert "untagged" in note.lower()


def test_unsafe_forced_suppressed_tags_silently(dlg, tmp_path):
    dlg._pt_force_tag.setChecked(True)
    dlg._settings.set("ti2_editor_force_tag_hide_warning", True)
    ti2 = _ti2(tmp_path, _UNSAFE)
    note = dlg._maybe_tag_randomised(ti2)
    assert "RANDOM_START" in ti2.read_text(encoding="utf-8")
    assert "forced" in note.lower()


def test_unsafe_forced_warning_accept_tags(dlg, tmp_path, monkeypatch):
    dlg._pt_force_tag.setChecked(True)
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    ti2 = _ti2(tmp_path, _UNSAFE)
    dlg._maybe_tag_randomised(ti2)
    assert "RANDOM_START" in ti2.read_text(encoding="utf-8")


def test_unsafe_forced_warning_reject_leaves_untagged(dlg, tmp_path, monkeypatch):
    dlg._pt_force_tag.setChecked(True)
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    ti2 = _ti2(tmp_path, _UNSAFE)
    dlg._maybe_tag_randomised(ti2)
    assert "RANDOM_START" not in ti2.read_text(encoding="utf-8")


def test_force_warning_hide_checkbox_persists(dlg, tmp_path, monkeypatch):
    # Accepting with 'Don't show again' ticked sets the suppression flag.
    dlg._pt_force_tag.setChecked(True)
    from PyQt6.QtWidgets import QCheckBox

    def _exec(self):
        for cb in self.findChildren(QCheckBox):
            cb.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", _exec)
    dlg._maybe_tag_randomised(_ti2(tmp_path, _UNSAFE))
    assert dlg._settings.get("ti2_editor_force_tag_hide_warning") is True
