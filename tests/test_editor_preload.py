"""Layout editor pre-loads the Create Chart tab's current chart (#45)."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import ui.dialogs.ti2_relayout_dialog as M  # noqa: E402
from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from workflow import ti2_relayout as R  # noqa: E402

_TI2 = """CTI2

ORIGINATOR "test"
TARGET_INSTRUMENT "GretagMacbeth i1 Pro"
COLOR_REP "iRGB"
PAPER_SIZE "210.0x297.0"
APPROX_WHITE_POINT "95.1 100.0 108.8"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100.0 100.0 100.0 95.1 100.0 108.8
2 "A2" 0.0 0.0 0.0 0.0 0.0 0.0
3 "A3" 100.0 0.0 0.0 41.2 21.3 1.9
END_DATA
"""


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings():
    s = AppSettings()
    # IniFormat (not the native Windows registry) so clear() never hits
    # "key marked for deletion" registry warnings on Windows.
    s._qs = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      "chromiq-test", "editor-preload")
    s._qs.clear()
    return s


def _stage(tmp_path, opts):
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(_TI2, encoding="utf-8")
    R.save_editor_meta(ti2, R.ChartSpec.from_ti2(ti2), opts, "chart")
    return ti2


def test_load_chart_from_restores_layout_options(qapp, monkeypatch, tmp_path):
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings())
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    ti2 = _stage(tmp_path, R.LayoutOptions(margin_mm=12, patch_scale=0.85,
                                           tiff_16bit=True))
    assert ed._load_chart_from(ti2) is True
    assert ed._spec is not None
    assert ed._options.margin_mm == 12
    assert abs(ed._options.patch_scale - 0.85) < 1e-9
    assert ed._options.tiff_16bit is True
    assert ed._basename == "chart"
    # A pre-loaded chart is clean — closing it without edits won't warn (#49).
    assert ed._is_dirty() is False


def test_initial_chart_preloads_on_open(qapp, monkeypatch, tmp_path):
    ti2 = _stage(tmp_path, R.LayoutOptions(margin_mm=9))
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings(),
                             initial_chart=ti2)
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    assert ed._spec is None              # deferred — not loaded during __init__
    qapp.processEvents()                 # fire the QTimer.singleShot(0)
    assert ed._spec is not None
    assert ed._options.margin_mm == 9


def test_no_initial_chart_opens_empty(qapp, monkeypatch):
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings())
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    qapp.processEvents()
    assert ed._spec is None


def test_needs_twin_gating(qapp, monkeypatch):
    """#44: the B&W twin (second printtarg run) is skipped for the common
    Patches-mode preview, and rendered for Spacers mode or a painted chart."""
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings())
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    monkeypatch.setattr(ed, "_refresh_preview", lambda *a, **k: None)

    ed._options = R.LayoutOptions(spacer_mode="colored")
    ed._mode_patches.setChecked(True)
    ed._hl_patches.setChecked(False)
    assert ed._needs_twin() is False              # patches, unpainted → skip

    # Highlight on needs patch geometry (= the twin), even in Patches mode (#44).
    ed._hl_patches.setChecked(True)
    assert ed._needs_twin() is True
    ed._hl_patches.setChecked(False)

    ed._mode_spacers.setChecked(True)
    assert ed._needs_twin() is True               # spacers mode → twin

    ed._mode_patches.setChecked(True)
    ed._paint = {(0, 0): (50.0, 50.0, 50.0)}
    assert ed._needs_twin() is True               # painted → twin even in patches

    ed._paint = {}
    ed._options = R.LayoutOptions(spacer_mode="none")
    ed._mode_spacers.setChecked(True)
    assert ed._needs_twin() is False              # no spacers at all


def test_patch_geometry_is_lazy_and_cached(qapp, monkeypatch):
    """Geometry is computed per visited page on demand, then cached (#44)."""
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings())
    assert ed._patch_geom_cache == {}
    assert ed._patch_geom_for_page(0) == {}       # no render yet → empty, no crash

    calls = []
    monkeypatch.setattr(R, "patch_geometry_for_page",
                        lambda *a, **k: calls.append(1) or {1: (0, 0, 5, 5)})

    class _Regen:
        ti2 = None
        tiffs = ["p0", "p1"]
        bw_tiffs = [None, None]
    ed._regen = _Regen()
    assert ed._patch_geom_for_page(0) == {1: (0, 0, 5, 5)}
    ed._patch_geom_for_page(0)                     # cached — no recompute
    assert calls == [1]
