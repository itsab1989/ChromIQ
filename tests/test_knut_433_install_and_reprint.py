"""Two faults Knut found on 4.3.3 (beta 17), run5, issue comments 6095262115
and 6095687746.

A. **Install Profile on Build Profile did nothing.** He built run5's profile,
   generated a verification chart, came back to Build Profile and pressed
   Install Profile: no copy, no log line, no window. Generating a chart fires
   ``target_started``, which runs ``TabProfile.clear_files``; that emptied the
   tab's profile path but left the button enabled, and ``_on_install``
   returned without a word on an empty path. Coming back to run5 put the
   measurement back (``measurement follows the bar`` in his log, 09:24:09) but
   never the profile.

B. **"Stored chart differs" after printing the same chart again.** His dated
   verification ``2026-10-10_095840/chart/`` matched the live verification
   chart byte for byte in every chart file. Only ``test-verify.print.json``
   differed: ``printed_at`` 09:43:30 in the stored copy, 10:13:55 live, because
   he had printed the chart again. The print record says how a sheet was
   printed, never which chart it is, and it was being compared as chart.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project, RunMeta          # noqa: E402
from workflow import profile_builder as PB              # noqa: E402


# ===========================================================================
# A. Install Profile follows the profile, and is never silent
# ===========================================================================
@pytest.fixture
def build_tab(qapp, tmp_path, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_profile import TabProfile

    class _Settings(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path / "projects")
            return super().get(key, default)

    installed = tmp_path / "ColorSync-sandbox"
    monkeypatch.setattr(PB, "_profile_dir", lambda: installed)
    st = _Settings()
    fm = FileManager(st)
    fm.set_target_name("test")
    project = fm.project()
    run1 = project.current_run()
    run2 = project.new_run()
    for r in (run1, run2):
        r.ensure_dir()
        if not r.meta_path.exists():
            r.save_meta(RunMeta.fresh(r.id))
    run1.measurement_ti3.write_text("CTI3\n", encoding="utf-8")
    run1.profile_icc.write_bytes(b"pretend this is run1's profile")
    ctl = MeasurementTargetController(fm)
    tab = TabProfile(ArgyllRunner(st), st, None)
    tab.set_target_controller(ctl)
    return tab, ctl, run1, run2, installed


def test_knuts_sequence_build_make_a_chart_come_back_install(build_tab):
    """His run5, step by step: a built profile, a chart generated (which
    clears the tab), back to the run, Install Profile. It must install."""
    tab, ctl, run1, run2, installed = build_tab
    ctl.set_profile_run(run1.id)
    assert tab.icc_path == run1.profile_icc
    assert tab._install_btn.isEnabled()

    tab.clear_files()                     # Generate Chart → target_started
    assert not tab._install_btn.isEnabled(), (
        "the button stayed enabled with nothing behind it: pressing it did "
        "nothing at all, which is what Knut saw")

    ctl.set_profile_run(run2.id)
    ctl.set_profile_run(run1.id)          # back to his run
    assert tab.icc_path == run1.profile_icc, "the profile did not follow the bar"
    assert tab._install_btn.isEnabled()

    tab._install_btn.click()
    dest = installed / run1.profile_icc.name
    assert dest.is_file(), "Install Profile installed nothing"
    assert f"[OK] Profile installed to {dest}" in tab._log.toPlainText()


def test_a_run_without_a_profile_offers_no_install(build_tab):
    tab, ctl, run1, run2, installed = build_tab
    ctl.set_profile_run(run1.id)
    assert tab._install_btn.isEnabled()
    ctl.set_profile_run(run2.id)          # run2 has no profile
    assert tab.icc_path is None, "run1's profile was offered under run2"
    assert not tab._install_btn.isEnabled()


def test_install_with_no_profile_says_so_in_the_log(build_tab, caplog):
    tab, ctl, run1, run2, installed = build_tab
    tab.set_icc_path(None)
    with caplog.at_level("WARNING"):
        tab._on_install()
    assert "nothing was installed" in caplog.text
    assert not installed.exists()


def test_a_restored_session_profile_arms_the_button(build_tab):
    """Session restore hands the profile over with ``set_icc_path``; the
    button used to stay disabled until the next build."""
    tab, ctl, run1, run2, installed = build_tab
    tab.clear_files()
    tab.set_icc_path(run1.profile_icc)
    assert tab._install_btn.isEnabled()


def test_both_buttons_say_the_same_thing_after_installing():
    """Knut: "Both buttons must behave the same way." Both write the same
    confirmation, naming where the copy went, into their tab's log."""
    import inspect
    from ui.tabs import tab_check_refine, tab_profile
    line = 'f"[OK] Profile installed to {dest}"'
    assert line in inspect.getsource(tab_profile.TabProfile._on_install)
    assert line in inspect.getsource(tab_check_refine)
    # …and both through the one door, which writes the chromiq.log line.
    assert 'log.info("Profile installed: %s", dest)' in \
        inspect.getsource(PB.install_profile_file)


# ===========================================================================
# B. Printing the same chart again is not a different chart
# ===========================================================================
def _record(printed_at: str) -> str:
    return json.dumps({"printed_at": printed_at, "colour": "raw",
                       "intent": "", "route": "chromiq",
                       "source_profile": ""}, indent=2)


@pytest.fixture
def reprinted(tmp_path):
    """Knut's run5 verifications/: a dated check measured from a sheet printed
    at 09:43:30, and the same chart printed again at 10:13:55."""
    from workflow.verify_chart_snapshot import snapshot_chart
    proj = Project.create(tmp_path / "test", "test")
    run = proj.current_run()
    run.ensure_dir()
    run.save_meta(RunMeta.fresh(run.id))
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    stem = run.verify_stem
    (vdir / f"{stem}.ti1").write_text("TI1 verify", encoding="utf-8")
    (vdir / f"{stem}.ti2").write_text("TI2 verify", encoding="utf-8")
    (vdir / f"{stem}.channels.json").write_text("{}", encoding="utf-8")
    (vdir / f"{stem}.print.json").write_text(_record("2026-10-10T09:43:30"),
                                             encoding="utf-8")
    v = run.verification("2026-10-10_095840")
    v.ensure_dir()
    snapshot_chart(v)
    v.measurement_ti3.write_text("THE 09:58 MEASUREMENT", encoding="utf-8")
    # Print Chart, again, same chart:
    (vdir / f"{stem}.print.json").write_text(_record("2026-10-10T10:13:55"),
                                             encoding="utf-8")
    return run, v


def test_printing_again_is_not_a_different_chart(reprinted):
    from workflow.chart_slot import slot_for_verification
    from workflow.verify_chart_snapshot import (live_differs_from_snapshot,
                                                slot_live_differs,
                                                snapshot_matches_live)
    run, v = reprinted
    assert not live_differs_from_snapshot(v), (
        "Knut's \"Stored chart differs\": only printed_at had moved")
    slot = slot_for_verification(v)
    assert not slot_live_differs(slot)
    assert snapshot_matches_live(slot), (
        "Restore Used Chart would be offered for a chart that is the same")


def test_a_really_different_chart_still_differs(reprinted):
    """The window stays for real changes."""
    from workflow.verify_chart_snapshot import live_differs_from_snapshot
    run, v = reprinted
    (run.verifications_dir / f"{run.verify_stem}.ti2").write_text(
        "TI2 a different chart", encoding="utf-8")
    assert live_differs_from_snapshot(v)


def test_start_asks_nothing_and_keeps_the_earlier_sheets_record(
        reprinted, qapp, monkeypatch):
    """Start on the same chart printed again: no window, and the record of the
    sheet the date's earlier measurement was read from is kept (set aside to
    ``old/<stamp>/``) rather than overwritten by the new print's record."""
    from PyQt6.QtWidgets import QMessageBox, QWidget
    from ui.tabs.tab_measure import TabMeasure
    from workflow.verify_chart_snapshot import (print_record_differs,
                                                snapshot_chart, snapshot_dir)
    run, v = reprinted

    def _no_window(*_a, **_k):
        raise AssertionError("a window was shown for the same chart")
    monkeypatch.setattr(QMessageBox, "exec", _no_window)

    class _Stub(QWidget):
        pass
    stub = _Stub()
    assert TabMeasure._chart_overwrite_choice(stub, v) == "go"

    assert print_record_differs(v)
    assert TabMeasure._set_aside_the_replaced_chart(stub, v) is True
    rec = stub._replaced_chart
    assert rec is not None, "the earlier sheet's print record would be lost"
    kept = rec.set_aside / f"{run.verify_stem}.print.json"
    assert "09:43:30" in kept.read_text(encoding="utf-8")
    snapshot_chart(v)
    now = snapshot_dir(v) / f"{run.verify_stem}.print.json"
    assert "10:13:55" in now.read_text(encoding="utf-8")


def test_an_unchanged_record_sets_nothing_aside(reprinted, qapp):
    from PyQt6.QtWidgets import QWidget
    from ui.tabs.tab_measure import TabMeasure
    from workflow.verify_chart_snapshot import print_record_differs
    run, v = reprinted
    (run.verifications_dir / f"{run.verify_stem}.print.json").write_text(
        _record("2026-10-10T09:43:30"), encoding="utf-8")
    assert not print_record_differs(v)
    stub = QWidget()
    assert TabMeasure._set_aside_the_replaced_chart(stub, v) is True
    assert stub._replaced_chart is None
    assert not (v.dir / "old").exists()
