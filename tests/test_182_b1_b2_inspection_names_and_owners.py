"""#182, Knut's rulings B1 and B2 (#182 5943085974, 2026-10-02).

B1: *"the file name should be as you suggest, with the same naming structure
as the measurement report file name with time-stamp at the end (but not with
the special configurable title that the measurement report has). There shall
not be any PDF support."*

B2: *"'Inspect a profile' should also have a distinguishing file name ... in
the same style with time stamp and unique for the 'Inspect a profile' tool. It
shall also use the reports folder, with the same logic relative to the
location of the file that were opened for inspection. 'Check & Refine' shall
also use the reports folder, unless the checked file is outside the project."*

Everything here goes through the real dialogs and the real tab handlers; only
the OS save chooser and the Argyll processes are answered by the test.

Plus R182-1 (K_review_beta1): a failed save no longer replaces the inspection
with "Could not read this measurement".

MUTATIONS, each proved red (N_impl_inspect/MUTATIONS.md).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_182_b_inspect_saves_into_the_owners_reports import (  # noqa: E402
    _TI3,
)
from tests.test_profile_tools import _make_icc, _runner, _Settings  # noqa: E402

_STAMP = r"\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _put(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def _places(tmp_path, suffix: str, data) -> dict:
    """{label: (the file, the reports folder it belongs to)}."""
    from core.file_manager import Calibration, Project
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    v = run.new_verification()
    v.ensure_dir()
    cal = Calibration(proj.root)
    cal.dir.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "Downloads"
    return {
        "run root": (_put(run.dir / f"P{suffix}", data), run.dir / "reports"),
        "reads": (_put(run.dir / "reads" / f"read1{suffix}", data),
                  run.dir / "reports"),
        "cache": (_put(run.dir / "cache" / f"scan{suffix}", data),
                  run.dir / "reports"),
        "run old": (_put(run.dir / "old" / "2026-09-30_101010" / f"P{suffix}",
                         data), run.dir / "reports"),
        "dated verification": (_put(v.dir / f"P-verify{suffix}", data),
                               v.dir / "reports"),
        "calibration": (_put(cal.dir / f"P-cal{suffix}", data),
                        cal.dir / "reports"),
        "project, no run": (_put(Path(proj.root) / "exports" / f"x{suffix}",
                                 data), Path(proj.root) / "reports"),
        # beside the file, no reports/ (Knut, #182 5944210498)
        "outside any project": (_put(out / f"m{suffix}", data), out),
    }


def _answer(monkeypatch, module, answer):
    seen = {}

    def _dialog(parent, title, name_filter="", start_path="", **kw):
        seen["title"] = title
        seen["start"] = Path(start_path)
        return answer(Path(start_path))
    monkeypatch.setattr(module, "save_file_dialog", _dialog)
    return seen


# ---------------------------------------------------------------------------
# One naming scheme
# ---------------------------------------------------------------------------
def test_the_report_and_the_inspections_share_one_scheme():
    from datetime import datetime

    from workflow.measurement_report import (inspection_file_name,
                                             report_file_name,
                                             report_name_stamp)
    when = datetime(2026, 10, 2, 14, 30, 5)
    assert report_name_stamp("2026-10-02T14:30:05") == "2026-10-02_14-30-05"
    assert report_name_stamp(when) == "2026-10-02_14-30-05"
    # the Measurement Report's PDF, as it always was
    assert (report_file_name("Measurement Report - Profiling of Printer - K",
                             "2026-10-02_14-30-05", ".pdf")
            == "Measurement Report - Profiling of Printer - K - "
               "2026-10-02_14-30-05.pdf")
    assert (inspection_file_name("Measurement inspection", "Knut-Canson", when)
            == "Measurement inspection - Knut-Canson - 2026-10-02_14-30-05.txt")
    # the same sanitising: nothing a file system refuses
    assert (inspection_file_name("Profile inspection", 'a:b/c?"', when)
            == "Profile inspection - a_b_c__ - 2026-10-02_14-30-05.txt")


def test_the_report_window_builds_its_pdf_name_through_the_shared_scheme():
    import inspect

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._report_filename)
    assert "report_file_name(" in src and "report_name_stamp(" in src
    # and no second copy of the stamp or the sanitising beside it
    assert '.replace(":", "-")' not in src and "re.sub(" not in src


# ---------------------------------------------------------------------------
# Inspect a measurement (B1)
# ---------------------------------------------------------------------------
def _ti3_dialog(qapp, ti3):
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    dlg = Ti3InfoDialog(_runner(), _Settings())
    dlg.load_measurement(ti3)
    qapp.processEvents()
    assert dlg._analysis is not None
    return dlg


def test_measurement_inspection_is_named_and_titled_as_itself(
        tmp_path, qapp, monkeypatch):
    import ui.dialogs.ti3_info_dialog as mod
    ti3, want = _places(tmp_path, ".ti3", _TI3)["dated verification"]
    seen = _answer(monkeypatch, mod, lambda start: str(start))
    dlg = _ti3_dialog(qapp, ti3)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    name = seen["start"].name
    assert re.fullmatch(rf"Measurement inspection - P-verify - {_STAMP}\.txt",
                        name), name
    assert seen["start"].parent == want
    assert seen["title"] == "Save measurement inspection"
    text = (want / name).read_text(encoding="utf-8")
    first = text.splitlines()[0]
    assert first == "Measurement inspection"
    assert "Measurement report" not in text and "—" not in first
    # the time in the name is the time in the text
    stamp = re.search(_STAMP, name).group(0)
    day, hm = stamp.split("_")
    assert f"on {day} {hm[:5].replace('-', ':')}" in text
    # no PDF next to it, ever (B1)
    assert not list(want.glob("*.pdf"))


@pytest.mark.parametrize("unwritable", [
    pytest.param("reports folder", marks=pytest.mark.skipif(
        os.name == "nt", reason="a folder cannot be made unwritable with chmod on Windows (it only sets the read-only attribute, which folders ignore)")),
    "file itself"])
def test_a_failed_save_keeps_the_inspection_on_screen(tmp_path, qapp,
                                                      monkeypatch, unwritable):
    """R182-1: the save error is shown; the inspection is not thrown away and
    the measurement is not blamed."""
    import ui.dialogs.ti3_info_dialog as mod
    ti3, want = _places(tmp_path, ".ti3", _TI3)["run root"]
    want.mkdir()
    if unwritable == "reports folder":
        want.chmod(0o500)
        # The chooser no longer OFFERS a folder nobody may write to (beta 2,
        # review T_review_beta2), so the user picks it by hand here.
        answer = lambda start: str(want / start.name)  # noqa: E731
    else:
        (want / "taken").mkdir()          # a FOLDER where the file would go
        answer = lambda start: str(want / "taken.txt")  # noqa: E731
        (want / "taken.txt").mkdir()
    _answer(monkeypatch, mod, answer)
    dlg = _ti3_dialog(qapp, ti3)
    rows_before = dlg._grid.count()
    report_before = list(dlg._report)
    try:
        dlg.show()
        dlg._on_save_report()
        qapp.processEvents()
        banner = dlg._banner.text()
        assert dlg._banner.isVisible()
        assert banner.startswith("Could not save the report:"), banner
        assert "Could not read" not in banner
        assert dlg._grid.count() == rows_before > 0
        assert dlg._report == report_before
        assert dlg._analysis is not None and dlg._save_btn.isEnabled()
    finally:
        dlg.close()
        want.chmod(0o700)


# ---------------------------------------------------------------------------
# Inspect a profile (B2)
# ---------------------------------------------------------------------------
_ICC = _make_icc(device_class=b"scnr")


def _icc_dialog(qapp, icc):
    from ui.dialogs.profile_info_dialog import ProfileInfoDialog
    dlg = ProfileInfoDialog(_runner(), _Settings())
    dlg.load_profile(icc)
    qapp.processEvents()
    assert dlg._info is not None
    return dlg


@pytest.mark.parametrize("label", [
    "run root", "reads", "cache", "run old", "dated verification",
    "calibration", "project, no run", "outside any project"])
def test_profile_inspection_goes_to_the_owners_reports(tmp_path, qapp,
                                                       monkeypatch, label):
    import ui.dialogs.profile_info_dialog as mod
    monkeypatch.setattr(mod, "icc_system_dirs", lambda: [])
    icc, want = _places(tmp_path, ".icc", _ICC)[label]
    seen = _answer(monkeypatch, mod, lambda start: str(start))
    dlg = _icc_dialog(qapp, icc)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    name = seen["start"].name
    assert seen["start"].parent == want, (seen["start"], want)
    assert re.fullmatch(rf"Profile inspection - {re.escape(icc.stem)} - "
                        rf"{_STAMP}\.txt", name), name
    assert seen["title"] == "Save profile inspection"
    text = (want / name).read_text(encoding="utf-8")
    assert text.splitlines()[0] == "Profile inspection"
    assert f"Profile: {icc.name}" in text
    assert "Profile report" not in text
    for wrong in ("reads", "cache", "old"):
        assert not list(Path(tmp_path).rglob(f"{wrong}/reports")), wrong
        assert not list(Path(tmp_path).rglob(f"{wrong}/*/reports")), wrong


def test_profile_inspection_cancelled_leaves_no_folder(tmp_path, qapp,
                                                       monkeypatch):
    import ui.dialogs.profile_info_dialog as mod
    monkeypatch.setattr(mod, "icc_system_dirs", lambda: [])
    icc, want = _places(tmp_path, ".icc", _ICC)["run root"]
    _answer(monkeypatch, mod, lambda start: "")
    dlg = _icc_dialog(qapp, icc)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    assert not want.exists()


def test_profile_inspection_keeps_a_same_named_file(tmp_path, qapp,
                                                    monkeypatch):
    import ui.dialogs.profile_info_dialog as mod
    monkeypatch.setattr(mod, "icc_system_dirs", lambda: [])
    icc, want = _places(tmp_path, ".icc", _ICC)["calibration"]
    want.mkdir()
    first = want / "mine.txt"
    first.write_text("the first inspection\n", encoding="utf-8")
    _answer(monkeypatch, mod, lambda start: str(first))
    dlg = _icc_dialog(qapp, icc)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    kept = list((want / "old").glob("*/mine.txt"))
    assert len(kept) == 1, "the earlier file was overwritten, not kept"
    assert kept[0].read_text(encoding="utf-8") == "the first inspection\n"
    assert first.read_text(encoding="utf-8").startswith("Profile inspection")


@pytest.mark.skipif(os.name == "nt", reason="a folder cannot be made unwritable with chmod on Windows (it only sets the read-only attribute, which folders ignore)")
def test_profile_inspection_save_error_is_not_a_read_error(tmp_path, qapp,
                                                           monkeypatch):
    import ui.dialogs.profile_info_dialog as mod
    monkeypatch.setattr(mod, "icc_system_dirs", lambda: [])
    icc, want = _places(tmp_path, ".icc", _ICC)["run root"]
    want.mkdir()
    want.chmod(0o500)
    # picked by hand: an unwritable folder is no longer offered (beta 2)
    _answer(monkeypatch, mod, lambda start: str(want / start.name))
    dlg = _icc_dialog(qapp, icc)
    rows = dlg._grid.count()
    try:
        dlg.show()
        dlg._on_save_report()
        banner = dlg._banner.text()
        assert banner.startswith("Could not save the report:"), banner
        assert "Could not read" not in banner
        assert dlg._grid.count() == rows > 0
    finally:
        dlg.close()
        want.chmod(0o700)


def test_a_system_profile_never_gets_a_reports_folder(tmp_path, qapp,
                                                      monkeypatch):
    """Inspect a profile browses the system's ColorSync folders first; the
    rule for a file in no project would make ``.../Profiles/reports``. The
    chooser opens in the ChromIQ folder instead and nothing is made."""
    import core.platform_paths as pp
    import ui.dialogs.profile_info_dialog as mod
    from ui.dialogs.profile_info_dialog import ProfileInfoDialog
    system = tmp_path / "Library" / "ColorSync" / "Profiles"
    icc = _put(system / "Vendor" / "paper.icc", _ICC)
    root = tmp_path / "MyChromIQ"          # Preferences > Paths
    root.mkdir()
    default = tmp_path / "ChromIQ"         # ~/ChromIQ, NOT what the user set
    default.mkdir()
    monkeypatch.setattr(mod, "icc_system_dirs", lambda: [system])
    monkeypatch.setattr(pp, "default_output_root", lambda: default)
    seen = _answer(monkeypatch, mod, lambda start: "")
    settings = _Settings()
    settings._d["custom_output_path"] = str(root)
    dlg = ProfileInfoDialog(_runner(), settings)
    dlg.load_profile(icc)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    assert seen["start"].parent == root
    assert not list(system.rglob("reports"))


# ---------------------------------------------------------------------------
# Check & Refine (B2)
# ---------------------------------------------------------------------------
def _check_tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = AppSettings()
    return TabCheckRefine(ArgyllRunner(s), s)


def _checked(tab, ti3, *, in_place=False):
    from workflow.profcheck_runner import ProfcheckResult
    result = ProfcheckResult(
        avg_de=1.2, peak_de=9.0, raw_log="profcheck output",
        patch_errors=[("A1", 0.5), ("A2", 0.4), ("B1", 9.0), ("C1", 0.3),
                      ("D1", 0.2), ("E1", 0.3), ("F1", 0.2), ("G1", 0.1)])
    tab._checker = SimpleNamespace(parse_results=lambda: result,
                                   primary_failure=lambda: None)
    tab._show_result_dialog = lambda *a, **k: None
    tab._ti3_path = ti3
    tab._checking_in_place = in_place
    tab._on_done(1)


@pytest.mark.parametrize("label", [
    "run root", "reads", "cache", "run old", "dated verification",
    "calibration", "outside any project"])
def test_check_and_refine_writes_into_the_owners_reports(tmp_path, qapp,
                                                         label):
    ti3, want = _places(tmp_path, ".ti3", _TI3)[label]
    tab = _check_tab(qapp)
    try:
        _checked(tab, ti3)
    finally:
        tab.deleteLater()
    assert (want / f"Quality_Check_1_{ti3.stem}.txt").is_file(), \
        sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.txt"))
    assert (want / f"Refine_Strips_1_{ti3.stem}.txt").is_file()
    for wrong in ("reads", "cache", "old"):
        assert not list(Path(tmp_path).rglob(f"{wrong}/reports")), wrong
        assert not list(Path(tmp_path).rglob(f"{wrong}/*/reports")), wrong


def test_check_and_refine_in_place_still_writes_beside_the_file(tmp_path,
                                                                qapp):
    """Outside the project, checked where it lies: beside the file, no
    ``reports/`` built around it (Basti 2026-09-01, Knut's exception)."""
    ti3, want = _places(tmp_path, ".ti3", _TI3)["outside any project"]
    tab = _check_tab(qapp)
    try:
        _checked(tab, ti3, in_place=True)
    finally:
        tab.deleteLater()
    assert (ti3.parent / f"Quality_Check_1_{ti3.stem}.txt").is_file()
    assert not (want / "reports").exists()


# ---------------------------------------------------------------------------
# The two Verify tools, which leave a report for a run too
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("label", ["reads", "dated verification",
                                   "outside any project"])
def test_verify_a_profile_reports_into_the_owners_reports(tmp_path, qapp,
                                                          label):
    from ui.dialogs.tools_dialogs import VerifyProfileDialog
    from workflow.profcheck_runner import ProfcheckRunner
    ti3, want = _places(tmp_path, ".ti3", _TI3)[label]
    log = ("Profile check complete, errors(CIEDE2000): max. = 3.50, "
           "avg. = 1.20\n  [1.20] 1 @ A1: ...\n")
    dlg = VerifyProfileDialog(runner=SimpleNamespace(is_running=False),
                              settings=_Settings())
    dlg._profile = tmp_path / "p.icc"
    dlg._measured = ti3
    dlg._checker = SimpleNamespace(
        run=lambda params, on_line, on_finish: on_finish(1),
        parse_results=lambda: ProfcheckRunner(None).parse_results(log),
        captured_warnings=lambda: [], primary_failure=lambda: None)
    try:
        dlg._execute()
    finally:
        dlg.close()
    assert (want / f"Verify_Profile_1_{ti3.stem}.txt").is_file()
    assert not list(Path(tmp_path).rglob("reads/reports"))


@pytest.mark.parametrize("label", ["reads", "calibration",
                                   "outside any project"])
def test_verify_against_reference_reports_into_the_owners_reports(
        tmp_path, qapp, label):
    from ui.dialogs.tools_dialogs import VerifyAgainstReferenceDialog
    from workflow.colverify_runner import ColverifyRunner
    ti3, want = _places(tmp_path, ".ti3", _TI3)[label]
    log = "  Total errors (CIEDE2000):     peak = 3.000000, avg = 1.000000\n"
    dlg = VerifyAgainstReferenceDialog(
        SimpleNamespace(is_running=False), _Settings())
    dlg._measured = ti3
    dlg._chart = None
    dlg._ref_edit.setPlainText("1 90 0 0\n2 50 0 0\n3 5 0 0\n")
    dlg._vrml_cb.setChecked(False)
    dlg._cv = SimpleNamespace(
        run=lambda params, on_line, on_finish: on_finish(0),
        parse_results=lambda: ColverifyRunner(None).parse_results(log))
    try:
        dlg._execute()
    finally:
        dlg.close()
    assert (want / f"Verify_Reference_1_{ti3.stem}.txt").is_file(), \
        sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.txt"))
    assert not list(Path(tmp_path).rglob("reads/reports"))


def test_outside_a_project_the_inspection_goes_beside_the_file_and_makes_nothing(
        tmp_path, qapp, monkeypatch):
    """Knut, #182 5944210498: outside a ChromIQ project, directly beside the
    inspected file, and no reports/ (nor an old/ archive) is made there."""
    import ui.dialogs.ti3_info_dialog as mod
    ti3, folder = _places(tmp_path, ".ti3", _TI3)["outside any project"]
    clash = folder / "taken.txt"
    clash.write_text("the user's own file", encoding="utf-8")
    seen = _answer(monkeypatch, mod, lambda start: str(clash))
    from ui.inspection_save import save_inspection
    res = save_inspection(None, ti3, "Measurement inspection", "Measurement inspection",
                          ["line"], dialog_title="t", subject_line="s",
                          ask=lambda *a, **k: (seen.update(start=Path(k["start_path"]))
                                               or str(clash)))
    assert seen["start"].parent == folder
    assert res.path == clash
    assert not (folder / "reports").exists() and not (folder / "old").exists()
