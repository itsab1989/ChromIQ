"""Triple-density presets round-trip their patch scale (#89).

A user preset (or built-in) that uses triple density with a customised patch
scale must reload with that scale, not snap back to the triple-density default
(1.3 / 5). Save now stores the effective TD layout; restore re-enables the TD
checkbox in a suppressed mode that doesn't clobber the restored values.
"""
import tempfile

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402

#: Files made here go into ONE folder the suite's sweep takes by name
#: (`chromiq-test-*`), not loose into $TMPDIR: 42,523 settings .ini files
#: and 4,024 .ti2 files had piled up there by 2026-09-24.
_TMP_DIR = tempfile.mkdtemp(prefix="chromiq-test-files-")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(qapp):
    s = AppSettings()
    s._qs = QSettings(tempfile.mktemp(suffix=".ini", dir=_TMP_DIR), QSettings.Format.IniFormat)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def _mval(t, flag):
    for pw in t._manual_widgets.get("printtarg", []):
        if pw.flag == flag:
            return pw.get_raw_value()
    return None


def test_td_preset_keeps_custom_scale_on_reload(qapp):
    t = _tab(qapp)
    # The effective TD layout the save path now stores (custom scale 1.08).
    pdata = {"printtarg_-i": "CM", "printtarg_-p": "A4", "printtarg_-a": 1.08,
             "printtarg_-m": 5, "printtarg_-P": True, "printtarg_-L": True,
             "triple_density": True, "pages": 1, "auto_patches": False}
    t._restore_user_preset(pdata)
    assert t._manual_td_check.isChecked() is True
    assert _mval(t, "-a") == pytest.approx(1.08)   # NOT clobbered to 1.3
    assert _mval(t, "-m") == 5


def test_td_untick_after_reload_reverts_cleanly(qapp):
    t = _tab(qapp)
    t._restore_user_preset({"printtarg_-i": "CM", "printtarg_-p": "A4",
                            "printtarg_-a": 1.14, "printtarg_-m": 5,
                            "printtarg_-P": True, "triple_density": True,
                            "pages": 1, "auto_patches": False})
    assert _mval(t, "-a") == pytest.approx(1.14)
    t._manual_td_check.setChecked(False)           # untick TD
    assert _mval(t, "-a") == pytest.approx(1.0)     # clean non-TD default
    assert _mval(t, "-m") == 6


def test_manual_td_toggle_still_applies_defaults_normally(qapp):
    """Ticking TD by hand (not a restore) still seeds the 1.3 / 5 defaults."""
    t = _tab(qapp)
    t._set_manual_value("printtarg", "-i", "CM")
    t._manual_td_check.setChecked(True)
    assert _mval(t, "-a") == pytest.approx(1.3)
    assert _mval(t, "-m") == 5
