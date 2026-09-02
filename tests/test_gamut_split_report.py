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
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
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
    whole = Path(T.__file__).read_text(encoding="utf-8")
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
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")

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


# ---- item 6: the raw-sheet drift figure (Knut, 2026-08-11) ----------------
def _drift_run(dir_: Path, name: str, ti3_text: str, created: str,
               colour="raw") -> dict:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(ti3_text, encoding="utf-8")
    return {"is_verification": True, "reference_source": "design",
            "printing": {"colour": colour}, "created": created,
            "_origin_dir": str(dir_), "ti3": name}


def test_raw_drift_baseline_pair_and_incomparable(tmp_path):
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import annotate_raw_drift
    base = _cgats("CTI3", _PATCHES)
    # a second sheet: same chart (same locs + device values), moved colours
    moved = (base
             .replace("65.0000 73.0000 52.0000", "60.0000 68.0000 47.0000")
             .replace("5.0000 73.0000 2.0000", "8.0000 70.0000 4.0000"))
    assert moved != base
    shrunk = "\n".join(base.splitlines()[:-2]) + "\nEND_DATA\n"  # fewer rows

    r1 = _drift_run(tmp_path / "d1", "v.ti3", base, "2026-05-01T10:00:00")
    r2 = _drift_run(tmp_path / "d2", "v.ti3", moved, "2026-06-01T10:00:00")
    r3 = _drift_run(tmp_path / "d3", "v.ti3", base, "2026-06-10T10:00:00",
                    colour="through-profile")      # not a raw sheet
    runs = [r1, r2, r3]
    annotate_raw_drift(runs)
    assert r1["raw_drift"] == {"baseline": True}
    rd = r2["raw_drift"]
    assert rd["prev"] == "2026-05-01T10:00:00" and rd["n"] > 0
    assert rd["avg"] > 0.0 and rd["max"] >= rd["avg"]
    assert "raw_drift" not in r3                   # through sheets untouched

    # a raw check with a DIFFERENT chart refuses the comparison
    r4 = _drift_run(tmp_path / "d4", "v.ti3", shrunk, "2026-07-01T10:00:00")
    runs = [r1, r4]
    annotate_raw_drift(runs)
    assert r4["raw_drift"].get("incomparable") is True


def test_raw_drift_identical_prints_measure_zero(tmp_path):
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import annotate_raw_drift
    base = _cgats("CTI3", _PATCHES)
    r1 = _drift_run(tmp_path / "a", "v.ti3", base, "2026-05-01T10:00:00")
    r2 = _drift_run(tmp_path / "b", "v.ti3", base, "2026-06-01T10:00:00")
    annotate_raw_drift([r1, r2])
    assert r2["raw_drift"]["avg"] == 0.0 and r2["raw_drift"]["max"] == 0.0


def test_raw_sheets_show_drift_not_pass_fail(qapp, tmp_path, monkeypatch):
    """Report Results: a raw sheet's cells say “drift”; its detail table has
    no Pass/Fail; the drift paragraph appears. Gamut and through sheets keep
    their grading."""
    import html as _html
    from workflow.measurement_report import build_report
    s, run, ti3 = _measured(tmp_path, monkeypatch,
                            lambda labs, *a, **kw: [True] * len(labs))
    from workflow.verification_print import write_print_record
    cdir = ti3.parent / "chart"
    cdir.mkdir(exist_ok=True)
    import shutil as _sh
    for ext in (".ti1", ".ti2"):
        src = run.verify_chart_ti2.with_suffix(ext)
        if src.is_file():
            _sh.copy2(src, cdir / src.name)
    write_print_record(cdir / (ti3.stem + ".ti2"),
                       colour="raw", intent="", profile=None, route="chromiq")
    from workflow.ti3_analysis import mark_verification_ti3
    mark_verification_ti3(ti3)
    rep = build_report(ti3, argyll_bin="/x/bin")
    assert rep.get("is_verification")
    assert (rep.get("printing") or {}).get("colour") == "raw"
    rep["raw_drift"] = {"baseline": True}

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    try:
        results = _html.unescape(dlg._report_results_html([rep]))
        assert ">drift<" in results.replace("</td>", "<")
        assert "not expected to match the design closely" in results
        detail = _html.unescape(dlg._run_detail_html(rep))
        assert "it becomes the baseline" in detail
        assert ">Pass<" not in detail and ">Fail<" not in detail
    finally:
        dlg.deleteLater()


def test_the_audit_batch_texts_are_in_the_report(qapp, tmp_path, monkeypatch):
    """The 2026-08-13 external-audit batch (wording approved by Sebastian):
    the split note carries the within-gamut share as a percentage, and the
    how-to section explains what the one ΔE number bundles — with the
    profcheck pointer — and that filtered averages do not rank papers or
    printers against each other."""
    from workflow.measurement_report import build_report
    s, run, ti3 = _measured(tmp_path, monkeypatch,
                            lambda labs, *a, **kw:
                            [i % 2 == 0 for i in range(len(labs))])
    rep = build_report(ti3, argyll_bin="/x/bin")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    try:
        import html as _html
        detail = _html.unescape(dlg._run_detail_html(rep))
        gs = rep["gamut_split"]
        pct = round(100 * gs["n_in"] / (gs["n_in"] + gs["n_out"]))
        assert f"({pct} %)" in detail
        how = _html.unescape(dlg._how_to_read_html())
        assert "Analyse Profile Quality" in how
        assert "not a fair way to rank papers or printers" in how
        assert "whole chain in one number" in how
    finally:
        dlg.deleteLater()
