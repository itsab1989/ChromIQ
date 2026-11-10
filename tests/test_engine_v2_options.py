"""#123 user-facing pieces: ETA progress, ICC v4, spectral option + UI."""
import numpy as np
import pytest
from PyQt6.QtCore import QSettings

from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from ui.tabs.tab_profile import TabProfile
from workflow.profile_engine.builder import (BuildSettings, _PercentProgress,
                                             build_profile)


def _tab(tmp_path, **prefs):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    for k, v in prefs.items():
        s.set(k, v)
    return TabProfile(ArgyllRunner(s), s)


# ---------------------------------------------------------------------------
# Progress: percentage + estimated remaining time
# ---------------------------------------------------------------------------

def test_percent_progress_reports_remaining_time():
    lines = []
    t = [0.0]
    p = _PercentProgress(lines.append, clock=lambda: t[0])
    p("Reading the measurement…")                       # 2 %
    assert lines[-1].startswith("2% · Reading")         # too early for ETA
    t[0] = 30.0
    p("Anchoring the rendering…")                       # 18 %
    assert "left · Anchoring" in lines[-1]
    t[0] = 60.0
    p("Gamut mapping: smoothing…")                      # 54 %
    assert "% · ~" in lines[-1] and "left" in lines[-1]
    # ETA shrinks as the build gets closer to done at constant pace.
    import re
    def eta_secs(line):
        m = re.search(r"~(\d+)(s| min) left", line)
        return int(m.group(1)) * (60 if m.group(2) == " min" else 1)
    t[0] = 90.0
    p("Saturation table: fitting…")                     # 92 %
    assert eta_secs(lines[-1]) < eta_secs(lines[-2])


def test_percent_progress_stays_monotonic_with_eta():
    lines = []
    t = [0.0]
    p = _PercentProgress(lines.append, clock=lambda: t[0])
    for i, msg in enumerate(["Fitting the printer model x…",
                             "Inverting the model: converging 1/6…",
                             "Inverting the model: converging 5/6…",
                             "Writing the profile…"]):
        t[0] = 5.0 * (i + 1)
        p(msg)
    pcts = [float(ln.split("%")[0]) for ln in lines]
    assert pcts == sorted(pcts)


# ---------------------------------------------------------------------------
# ICC v4 container (W6)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _s1_ti3(tmp_path_factory):
    td = tmp_path_factory.mktemp("v4")
    p = PRINTERS["S1"]
    chart = make_chart(p, 450)
    xyz, refl, _ = measure(p, chart)
    return write_ti3(td / "c.ti3", p, chart, xyz, refl)


def test_v4_profile_header_id_and_metadata(_s1_ti3, tmp_path):
    icc = tmp_path / "v4.icc"
    build_profile(_s1_ti3, icc, BuildSettings(quality="l",
                                              gammap_mode="accurate",
                                              icc_version="4",
                                              description="Vier"))
    data = icc.read_bytes()
    assert data[8] == 4 and data[9] >> 4 == 4          # version 4.4
    assert any(data[84:100])                            # profile ID (MD5)
    # v4 metadata: desc and cprt are multiLocalizedUnicodeType.
    from benchmarks.iccread import IccProfile
    prof = IccProfile(icc)
    assert prof.tags["desc"][:4] == b"mluc"
    assert prof.tags["cprt"][:4] == b"mluc"
    assert "Vier".encode("utf-16-be") in prof.tags["desc"]
    # littleCMS accepts the file and reads the description back.
    from PIL import ImageCms
    p = ImageCms.getOpenProfile(str(icc))
    assert "Vier" in ImageCms.getProfileDescription(p)


@pytest.mark.slow
def test_v4_luts_identical_to_v2(_s1_ti3, tmp_path):
    from datetime import datetime, timezone
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = tmp_path / "v2.icc"
    b = tmp_path / "v4.icc"
    for path, ver in ((a, "2"), (b, "4")):
        build_profile(_s1_ti3, path, BuildSettings(
            quality="l", gammap_mode="accurate", icc_version=ver,
            timestamp=ts, description="same"))
    from benchmarks.iccread import IccProfile
    p2, p4 = IccProfile(a), IccProfile(b)
    for tag in ("A2B1", "B2A1", "gamt"):
        # The spec keeps the legacy PCS encoding for lut16Type in v4 —
        # the colour tables must be byte-identical.
        assert p2.tags[tag] == p4.tags[tag]
    assert p2.tags["desc"][:4] == b"desc"
    assert p4.tags["desc"][:4] == b"mluc"


def test_v2_default_untouched(_s1_ti3, tmp_path):
    icc = tmp_path / "v2.icc"
    build_profile(_s1_ti3, icc, BuildSettings(quality="l",
                                              gammap_mode="accurate"))
    data = icc.read_bytes()
    assert data[8] == 2
    assert not any(data[84:100])                        # no profile ID in v2


# ---------------------------------------------------------------------------
# Spectral-physics option (opt-in flag)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_spectral_physics_flag_runs_challenge(tmp_path):
    p = PRINTERS["S5"]
    chart = make_chart(p, 700)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "s5.ti3", p, chart, xyz, refl)
    lines = []
    s = BuildSettings(quality="l", gammap_mode="accurate",
                      spectral_physics=True, ink_limit=p.tac,
                      progress=lines.append)
    build_profile(ti3, tmp_path / "s5.icc", s)
    assert any("spectral physics" in ln for ln in lines)


@pytest.mark.slow
def test_spectral_physics_off_is_bit_identical(tmp_path):
    p = PRINTERS["S1"]
    chart = make_chart(p, 400)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "c.ti3", p, chart, xyz, refl)
    from datetime import datetime, timezone
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a, b = tmp_path / "a.icc", tmp_path / "b.icc"
    build_profile(ti3, a, BuildSettings(quality="l", gammap_mode="accurate",
                                        timestamp=ts, description="x"))
    build_profile(ti3, b, BuildSettings(quality="l", gammap_mode="accurate",
                                        timestamp=ts, description="x",
                                        spectral_physics=False))
    assert a.read_bytes() == b.read_bytes()


# ---------------------------------------------------------------------------
# Manual-module UI: visibility + persistence
# ---------------------------------------------------------------------------

def test_engine_rows_hidden_without_accurate_mode(tmp_path, qtbot):
    tab = _tab(tmp_path)                          # engine beta off
    qtbot.addWidget(tab)
    assert tab._m_engine_rows_widget.isHidden()
    tab2 = _tab(tmp_path, profile_engine_beta=True, gammap_mode="fast")
    qtbot.addWidget(tab2)
    tab2._refresh_engine_rows()
    assert tab2._m_engine_rows_widget.isHidden()


def test_engine_rows_visible_in_accurate_mode(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="accurate")
    qtbot.addWidget(tab)
    tab._refresh_engine_rows()
    # Not explicitly hidden — actual visibility follows the (currently
    # unshown) manual page, so isHidden is the right probe here.
    assert not tab._m_engine_rows_widget.isHidden()


def test_engine_options_reach_params_only_when_active(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="accurate")
    qtbot.addWidget(tab)
    tab._m_spectral_cb.setChecked(True)
    tab._m_iccver_combo.setCurrentIndex(
        tab._m_iccver_combo.findData("4"))
    params = tab._collect_manual_profile()
    assert params.spectral_physics is True
    assert params.icc_version == "4"
    # Same widget state, but accurate mode off → engine-only options muted.
    tab._settings.set("gammap_mode", "fast")
    params = tab._collect_manual_profile()
    assert params.spectral_physics is False
    assert params.icc_version == "2"


def test_engine_options_save_defaults_and_preset_roundtrip(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="accurate")
    qtbot.addWidget(tab)
    tab._m_spectral_cb.setChecked(True)
    tab._m_iccver_combo.setCurrentIndex(tab._m_iccver_combo.findData("4"))
    data = tab._m_collect_preset_data()
    assert data["spectral_physics"] is True and data["icc_version"] == "4"
    tab._m_spectral_cb.setChecked(False)
    tab._m_iccver_combo.setCurrentIndex(tab._m_iccver_combo.findData("2"))
    tab._m_apply_preset_data(data)
    assert tab._m_spectral_cb.isChecked()
    assert tab._m_iccver_combo.currentData() == "4"
    # Save-as-defaults writes the settings keys; the defaults entry
    # (index 0) restores them.
    tab._stack.setCurrentIndex(1)                 # manual mode
    tab._on_save_defaults()
    assert bool(tab._settings.get("manual2_colprof_spectral")) is True
    assert tab._settings.get("manual2_colprof_iccver") == "4"
    tab._m_spectral_cb.setChecked(False)
    tab._m_iccver_combo.setCurrentIndex(tab._m_iccver_combo.findData("2"))
    tab._on_m_preset_selected(0)
    assert tab._m_spectral_cb.isChecked()
    assert tab._m_iccver_combo.currentData() == "4"


def test_settings_from_params_maps_new_fields():
    from workflow.engine_builder import settings_from_params
    from workflow.profile_builder import ProfileParams
    from pathlib import Path
    p = ProfileParams(ti3_path=Path("x.ti3"), spectral_physics=True,
                      icc_version="4")
    s = settings_from_params(p)
    assert s.spectral_physics is True and s.icc_version == "4"


@pytest.mark.slow
def test_both_versions_writes_v2_and_v4_twin(_s1_ti3, tmp_path):
    icc = tmp_path / "twin.icc"
    lines = []
    res = build_profile(_s1_ti3, icc, BuildSettings(
        quality="l", gammap_mode="accurate", icc_version="both",
        progress=lines.append))
    twin = tmp_path / "twin-v4.icc"
    assert res.icc_path == icc and icc.exists() and twin.exists()
    assert icc.read_bytes()[8] == 2
    d4 = twin.read_bytes()
    assert d4[8] == 4 and any(d4[84:100])
    from benchmarks.iccread import IccProfile
    assert IccProfile(icc).tags["A2B1"] == IccProfile(twin).tags["A2B1"]
    assert any("v4 twin" in ln for ln in lines)


def test_both_option_in_ui_and_persistence(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="accurate")
    qtbot.addWidget(tab)
    idx = tab._m_iccver_combo.findData("both")
    assert idx >= 0
    tab._m_iccver_combo.setCurrentIndex(idx)
    assert tab._collect_manual_profile().icc_version == "both"
    data = tab._m_collect_preset_data()
    assert data["icc_version"] == "both"
    tab._m_iccver_combo.setCurrentIndex(tab._m_iccver_combo.findData("2"))
    tab._m_apply_preset_data(data)
    assert tab._m_iccver_combo.currentData() == "both"


def test_inv_gamut_row_tooltip_right_aligned(tmp_path, qtbot):
    # Regression (Basti report): the ⓘ must sit at the row's right edge —
    # a stretch BEFORE the button and none after it.
    tab = _tab(tmp_path)
    qtbot.addWidget(tab)
    row = tab._m_inv_gamut_cb.parentWidget().layout()
    # find the QHBoxLayout holding the checkbox
    from PyQt6.QtWidgets import QHBoxLayout
    def find_row(layout):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            lay = item.layout()
            if lay is not None:
                if any(lay.itemAt(j).widget() is tab._m_inv_gamut_cb
                       for j in range(lay.count())):
                    return lay
                sub = find_row(lay)
                if sub is not None:
                    return sub
        return None
    lay = find_row(row)
    assert lay is not None
    kinds = ["stretch" if lay.itemAt(i).spacerItem() else
             type(lay.itemAt(i).widget()).__name__
             for i in range(lay.count())]
    assert kinds[0] == "QCheckBox"
    assert "stretch" in kinds[1:-1]            # spacer between…
    assert kinds[-1] == "TooltipButton"        # …and the ⓘ last (right edge)


def test_settings_close_refreshes_engine_rows():
    # The Build Profile tab stays visible while the Settings dialog is
    # open — MainWindow must refresh the engine-only rows on dialog close.
    import inspect
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._open_settings)
    assert "_refresh_engine_rows" in src


# ---------------------------------------------------------------------------
# Noise handling behind the held-out exam (only-win-or-do-nothing)
# ---------------------------------------------------------------------------

def _noisy_chart(tmp_path, noise_scale):
    from benchmarks.synthetic import SyntheticPrinter
    p = SyntheticPrinter("SX", "CMYK", tac=280.0, noise_scale=noise_scale)
    chart = make_chart(p, 600)
    xyz, refl, _ = measure(p, chart, seed=41)
    return write_ti3(tmp_path / f"n{noise_scale:g}.ti3", p, chart, xyz, refl), p


@pytest.mark.slow
def test_noise_option_stands_aside_on_clean_chart(tmp_path):
    ti3, p = _noisy_chart(tmp_path, 1.0)
    lines = []
    from datetime import datetime, timezone
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a, b = tmp_path / "a.icc", tmp_path / "b.icc"
    build_profile(ti3, a, BuildSettings(quality="l", gammap_mode="accurate",
                                        ink_limit=280.0, timestamp=ts,
                                        description="x"))
    build_profile(ti3, b, BuildSettings(quality="l", gammap_mode="accurate",
                                        ink_limit=280.0, timestamp=ts,
                                        description="x", noise_model=True,
                                        progress=lines.append))
    assert any("stands aside" in ln for ln in lines)
    # Only-win-or-do-nothing: on a clean chart the profile is IDENTICAL.
    assert a.read_bytes() == b.read_bytes()
    # …but the confidence map still arrives (reporting-only extra).
    assert any("Confidence map" in ln for ln in lines)


@pytest.mark.slow
def test_noise_option_wins_on_noisy_chart(tmp_path):
    ti3, p = _noisy_chart(tmp_path, 4.0)
    lines = []
    build_profile(ti3, tmp_path / "n.icc",
                  BuildSettings(quality="l", gammap_mode="accurate",
                                ink_limit=280.0, noise_model=True,
                                progress=lines.append))
    assert any("weighted by their reliability" in ln for ln in lines)


@pytest.mark.slow
def test_render_style_option_uses_bijective_mapper(tmp_path):
    p = PRINTERS["S1"]
    chart = make_chart(p, 450)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "c.ti3", p, chart, xyz, refl)
    lines = []
    res = build_profile(ti3, tmp_path / "c.icc", BuildSettings(
        quality="l", gammap_mode="accurate", render_style="bijective",
        source_gamut="assets/profiles/ClayRGB1998.icm",
        progress=lines.append))
    assert res.perceptual_distinct
    assert any("ChromIQ bijective rendering" in ln for ln in lines)


def test_new_rows_persistence_roundtrip(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="accurate")
    qtbot.addWidget(tab)
    tab._m_noise_cb.setChecked(True)
    tab._m_render_combo.setCurrentIndex(
        tab._m_render_combo.findData("bijective"))
    params = tab._collect_manual_profile()
    assert params.noise_model is True
    assert params.render_style == "bijective"
    data = tab._m_collect_preset_data()
    assert data["noise_model"] is True
    assert data["render_style"] == "bijective"
    tab._m_noise_cb.setChecked(False)
    tab._m_render_combo.setCurrentIndex(tab._m_render_combo.findData("argyll"))
    tab._m_apply_preset_data(data)
    assert tab._m_noise_cb.isChecked()
    assert tab._m_render_combo.currentData() == "bijective"
    tab._stack.setCurrentIndex(1)
    tab._on_save_defaults()
    assert bool(tab._settings.get("manual2_colprof_noise")) is True
    assert tab._settings.get("manual2_colprof_render") == "bijective"
    # Muted outside accurate mode.
    tab._settings.set("gammap_mode", "fast")
    params = tab._collect_manual_profile()
    assert params.noise_model is False and params.render_style == "argyll"


def test_settings_from_params_maps_noise_and_render():
    from workflow.engine_builder import settings_from_params
    from workflow.profile_builder import ProfileParams
    from pathlib import Path
    p = ProfileParams(ti3_path=Path("x.ti3"), noise_model=True,
                      render_style="bijective")
    s = settings_from_params(p)
    assert s.noise_model is True and s.render_style == "bijective"
