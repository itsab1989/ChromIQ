"""#43: the engine/colprof combobox is gone — the beta setting alone
drives which engine builds a profile (ON = engine, no per-build
selector), and enabling the setting pops a consent dialog."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_profile import TabProfile  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, **prefs):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    for k, v in prefs.items():
        s.set(k, v)
    return TabProfile(ArgyllRunner(s), s)


def test_no_engine_combobox_exists(qapp, tmp_path):
    tab = _tab(tmp_path, profile_engine_beta=True)
    assert not hasattr(tab, "_engine_combo")
    assert not hasattr(tab, "_engine_row_widget")
    assert not hasattr(tab, "refresh_profile_engine_option")


def test_resolve_engine_follows_setting(qapp, tmp_path, monkeypatch):
    # a plain RGB build the engine fully supports
    import ui.tabs.tab_profile as tp

    class _Params:
        ti3_path = tmp_path / "x.ti3"
    import workflow.engine_builder as eb
    monkeypatch.setattr(eb, "is_multi_ink", lambda _p: False)
    monkeypatch.setattr(eb, "engine_support", lambda _p: (True, ""))

    off = _tab(tmp_path, profile_engine_beta=False)
    assert off._resolve_engine(_Params()) == "colprof"

    on = _tab(tmp_path, profile_engine_beta=True)
    assert on._resolve_engine(_Params()) == "engine"


def test_resolve_engine_falls_back_when_unsupported(qapp, tmp_path,
                                                    monkeypatch):
    import ui.tabs.tab_profile as tp

    class _Params:
        ti3_path = tmp_path / "x.ti3"
    import workflow.engine_builder as eb
    monkeypatch.setattr(eb, "is_multi_ink", lambda _p: False)
    monkeypatch.setattr(eb, "engine_support",
                        lambda _p: (False, "an extra flag"))
    on = _tab(tmp_path, profile_engine_beta=True)
    assert on._resolve_engine(_Params()) == "colprof"
