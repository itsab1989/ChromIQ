"""The in/out-of-gamut split of the measurement report (Knut, 2026-08-10) and
the FROM PROFILE GAMUT default for verification runs.

The split's real-data numbers were validated against the 2026-08-10 hardware
sheets (105-patch design chart on plain paper: 9 within / 96 beyond; raw
within-avg 6.37, through within-avg 3.77 vs totals 11.76 / 9.04). These tests
pin the mechanics without Argyll: the round-trip flags are stubbed."""
from pathlib import Path

import pytest

from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env


@pytest.fixture()
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _measured(tmp_path, monkeypatch, flags_fn):
    """A dated verification measurement + stubbed gamut round trip."""
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
    # the referee profile only has to EXIST — the round trip is stubbed
    run.built_profile_icc().parent.mkdir(parents=True, exist_ok=True)
    run.built_profile_icc().write_bytes(b"icc")
    import workflow.gamut_target as G
    monkeypatch.setattr(G, "flags_in_gamut", flags_fn)
    return s, run, v.measurement_ti3


def test_split_counts_every_patch_and_degrades_without_argyll(
        qapp, tmp_path, monkeypatch):
    from workflow.measurement_report import build_report
    seen = {}

    def fake_flags(labs, profile, bin_dir, **kw):
        seen["n"] = len(labs)
        seen["profile"] = Path(profile).name
        return [i % 3 == 0 for i in range(len(labs))]   # every 3rd within

    s, run, ti3 = _measured(tmp_path, monkeypatch, fake_flags)
    rep = build_report(ti3, argyll_bin="/x/bin")
    gs = rep["gamut_split"]
    assert gs["n_in"] + gs["n_out"] == seen["n"] > 0    # nothing dropped
    assert gs["profile"] == run.built_profile_icc().name == seen["profile"]
    assert (gs["de00_in"] or {}).get("avg_all") is not None
    assert (gs["de00_out"] or {}).get("avg_all") is not None

    # No Argyll path → the report is exactly its old self, never an error.
    rep2 = build_report(ti3)
    assert "gamut_split" not in rep2
    assert rep2["de00"]["avg_all"] == rep["de00"]["avg_all"]


def test_split_failure_never_breaks_the_report(qapp, tmp_path, monkeypatch):
    from workflow.measurement_report import build_report

    def boom(*a, **kw):
        raise RuntimeError("xicclu missing")

    s, run, ti3 = _measured(tmp_path, monkeypatch, boom)
    rep = build_report(ti3, argyll_bin="/x/bin")
    assert "gamut_split" not in rep
    assert rep["de00"]["avg_all"] is not None


def test_dialog_grades_within_gamut_and_shows_the_blocks(
        qapp, tmp_path, monkeypatch):
    from workflow.measurement_report import build_report

    s, run, ti3 = _measured(tmp_path, monkeypatch,
                            lambda labs, *a, **kw:
                            [i % 2 == 0 for i in range(len(labs))])
    rep = build_report(ti3, argyll_bin="/x/bin")

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    try:
        detail = dlg._run_detail_html(rep)
        assert "Within gamut" in detail and "Beyond it" in detail
        assert "not a mistake of the profile" in detail
        import html as _html
        overview = _html.unescape(dlg._comparison_table_html([rep, rep]))
        for block in ("Within the profile's gamut",
                      "Beyond the profile's gamut", "All patches together"):
            assert block in overview
        # the split blocks list the five accuracy metrics three times over
        assert overview.count("Average ΔE, all patches") == 3
        results = _html.unescape(dlg._report_results_html([rep]))
        assert "within-gamut" in results
    finally:
        dlg.deleteLater()


def test_verification_default_guard_is_wired(qapp):
    """Proposal 2, pinned at the source level (a full TabChart needs the whole
    app; the on-screen driver exercises the behaviour for real): the default
    lives in _refresh_gamut_visibility, is gated on a built profile AND on the
    user not having chosen a module by hand, and every mode button routes
    through _user_switch_mode so a hand-picked module wins."""
    import inspect
    from ui.tabs import tab_chart as T
    src = inspect.getsource(T.TabChart._refresh_gamut_visibility)
    assert 'self._switch_mode("gamut")' in src
    assert "_user_chose_module" in src and "profile is not None" in src
    whole = Path(T.__file__).read_text()
    assert whole.count("_user_switch_mode(") >= 4      # def + three buttons
    assert 'clicked.connect(lambda: self._switch_mode(' not in whole


def test_user_switch_mode_marks_the_choice(qapp):
    from types import SimpleNamespace
    from ui.tabs.tab_chart import TabChart
    seen = []
    dummy = SimpleNamespace(_switch_mode=lambda m: seen.append(m))
    TabChart._user_switch_mode(dummy, "manual")
    assert seen == ["manual"] and dummy._user_chose_module is True


def test_report_options_are_remembered(qapp, tmp_path):
    """The dialog's options survive closing it: detail + all-runs checkboxes
    and the Pass thresholds come back as last set (Sebastian, 2026-08-10)."""
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    try:
        assert dlg._all_runs_check.isChecked()          # the default
        assert not dlg._detail_check.isChecked()
        dlg._detail_check.setChecked(True)
        dlg._all_runs_check.setChecked(False)
        dlg._avg_thr_spin.setValue(1.5)
        dlg._max_thr_spin.setValue(4.0)
    finally:
        dlg.deleteLater()

    dlg2 = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    try:
        assert dlg2._detail_check.isChecked()
        assert not dlg2._all_runs_check.isChecked()
        assert dlg2._avg_thr_spin.value() == 1.5
        assert dlg2._max_thr_spin.value() == 4.0
    finally:
        dlg2.deleteLater()
