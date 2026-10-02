"""#182 (b): "Inspect a measurement" saves into the reports folder of what the
measurement belongs to.

Knut, 2026-10-01: the inspection of a verification landed loose in
``verifications/<date>/`` beside the ``.ti3`` (his ``test-verify-report.txt``),
not in that date's ``reports/``. The folder is now the OWNER's, resolved through
the run / dated verification / calibration (``workflow.run_compliance.
reports_dir_for``), never ``<the file's folder>/reports``: a ``.ti3`` in
``reads/``, ``cache/`` or ``old/<stamp>/`` would otherwise make a
``reads/reports/`` nothing in ChromIQ lists (challenge B2). A file in no project
gets ``<its folder>/reports``. The folder is left behind only when the file is
saved into it, and a same-named file there is kept in ``reports/old/<stamp>/``
first, never overwritten.

Every save test goes through the dialog's own ``_on_save_report``; only the
OS save dialog is answered.

MUTATIONS, each proved red (MUTATIONS.md of H_impl_182):
* ``reports = reports_dir_for(src)`` -> ``src.parent`` (the old folder): the
  dated-verification and every owner test red;
  -> ``reports_subdir(src.parent)`` (the plain wrong fix): reads/cache/old red;
* drop the ``reports.rmdir()`` after a cancel: the cancel test red;
* drop the archive before the write: the second-save test red.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

_TI3 = ("CTI3\n\nCOLOR_REP \"iRGB_XYZ\"\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 3\nBEGIN_DATA\n"
        "1 100 100 100 86 90 75 \n2 50 50 50 18 19 16 \n3 0 0 0 0.9 1.0 1.1 \n"
        "END_DATA\n")


#: "<kind> - <name> - YYYY-MM-DD_HH-MM-SS.txt", the Measurement Report's scheme.
_NAME = __import__("re").compile(
    r"Measurement inspection - .+ - \d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.txt")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _project(tmp_path):
    from core.file_manager import Calibration, Project
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    v = run.new_verification()
    v.ensure_dir()
    cal = Calibration(proj.root)
    cal.dir.mkdir(parents=True, exist_ok=True)
    return proj, run, v, cal


def _put(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TI3, encoding="utf-8")
    return path


def _places(tmp_path):
    """{label: (the .ti3, the reports folder it belongs to)}."""
    proj, run, v, cal = _project(tmp_path)
    outside = tmp_path / "Downloads"
    return {
        "run root": (_put(run.dir / "P.ti3"), run.dir / "reports"),
        "reads": (_put(run.dir / "reads" / "read1.ti3"), run.dir / "reports"),
        "cache": (_put(run.dir / "cache" / "scan.ti3"), run.dir / "reports"),
        "run old": (_put(run.dir / "old" / "2026-09-30_101010" / "P.ti3"),
                    run.dir / "reports"),
        "dated verification": (_put(v.dir / "P-verify.ti3"),
                               v.dir / "reports"),
        "dated old": (_put(v.dir / "old" / "2026-09-30_101010" / "P-verify.ti3"),
                      v.dir / "reports"),
        "calibration": (_put(cal.dir / "P-cal.ti3"), cal.dir / "reports"),
        "calibration old": (_put(cal.dir / "old" / "2026-09-30" / "P-cal.ti3"),
                            cal.dir / "reports"),
        "project, no run": (_put(Path(proj.root) / "exports" / "x.ti3"),
                            Path(proj.root) / "reports"),
        "outside any project": (_put(outside / "m.ti3"), outside / "reports"),
    }


@pytest.mark.parametrize("label", [
    "run root", "reads", "cache", "run old", "dated verification",
    "dated old", "calibration", "calibration old", "project, no run",
    "outside any project"])
def test_the_reports_folder_is_the_owners(tmp_path, label):
    from workflow.run_compliance import reports_dir_for
    ti3, want = _places(tmp_path)[label]
    assert reports_dir_for(ti3) == want
    assert not want.exists(), "asking made the folder"


def _inspector(qapp, ti3):
    from tests.test_profile_tools import _runner, _Settings
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    dlg = Ti3InfoDialog(_runner(), _Settings())
    dlg.load_measurement(ti3)
    qapp.processEvents()
    assert dlg._analysis is not None
    return dlg


def _answer(monkeypatch, answer):
    """Answer the OS save dialog: *answer(start_path) -> chosen path*."""
    import ui.dialogs.ti3_info_dialog as mod
    seen = {}

    def _dialog(parent, title, name_filter="", start_path="", **kw):
        seen["start"] = Path(start_path)
        seen["start_dir_existed"] = Path(start_path).parent.is_dir()
        return answer(Path(start_path))
    monkeypatch.setattr(mod, "save_file_dialog", _dialog)
    return seen


@pytest.mark.parametrize("label", ["dated verification", "reads", "cache",
                                   "run old", "calibration",
                                   "outside any project"])
def test_save_offers_and_writes_into_the_owners_reports(tmp_path, qapp,
                                                        monkeypatch, label):
    ti3, want = _places(tmp_path)[label]
    seen = _answer(monkeypatch, lambda start: str(start))
    dlg = _inspector(qapp, ti3)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    assert seen["start"].parent == want, (seen["start"], want)
    assert seen["start_dir_existed"], "the chooser was offered a folder that " \
        "does not exist, so it opens somewhere else"
    # Knut's B1 (#182 5943085974): the Measurement Report's naming
    # structure, this tool's own word, the time stamp at the end.
    assert _NAME.fullmatch(seen["start"].name), seen["start"].name
    assert seen["start"].name.startswith(f"Measurement inspection - {ti3.stem} - ")
    assert (want / seen["start"].name).is_file()
    # never a reports/ folder beside a file the run merely keeps
    for wrong in ("reads", "cache", "old"):
        assert not list(Path(tmp_path).rglob(f"{wrong}/reports")), wrong
        assert not list(Path(tmp_path).rglob(f"{wrong}/*/reports")), wrong


def test_a_cancelled_save_leaves_no_reports_folder(tmp_path, qapp,
                                                   monkeypatch):
    ti3, want = _places(tmp_path)["dated verification"]
    _answer(monkeypatch, lambda start: "")
    dlg = _inspector(qapp, ti3)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    assert not want.exists(), "a cancelled save left an empty reports/"


def test_a_save_elsewhere_leaves_no_reports_folder(tmp_path, qapp,
                                                   monkeypatch):
    ti3, want = _places(tmp_path)["dated verification"]
    elsewhere = tmp_path / "Desktop"
    elsewhere.mkdir()
    _answer(monkeypatch, lambda start: str(elsewhere / "mine"))
    dlg = _inspector(qapp, ti3)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    assert (elsewhere / "mine.txt").is_file()
    assert not want.exists()


def test_a_second_save_keeps_the_first_in_old(tmp_path, qapp, monkeypatch):
    ti3, want = _places(tmp_path)["dated verification"]
    want.mkdir()
    first = want / "mine.txt"
    first.write_text("the first inspection\n", encoding="utf-8")
    _answer(monkeypatch, lambda start: str(first))
    dlg = _inspector(qapp, ti3)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    kept = list((want / "old").glob(f"*/{first.name}"))
    assert len(kept) == 1, "the earlier file was overwritten, not kept"
    assert kept[0].read_text(encoding="utf-8") == "the first inspection\n"
    assert first.read_text(encoding="utf-8") != "the first inspection\n"
    assert ti3.name in first.read_text(encoding="utf-8")


def test_reports_as_a_file_falls_back_to_the_measurements_folder(
        tmp_path, qapp, monkeypatch):
    """Error case: a FILE named ``reports`` where the folder should be. The
    chooser opens in the measurement's folder, nothing raises, and the file
    called reports is untouched."""
    ti3, want = _places(tmp_path)["dated verification"]
    want.write_text("not a folder", encoding="utf-8")
    seen = _answer(monkeypatch, lambda start: str(start))
    dlg = _inspector(qapp, ti3)
    try:
        dlg._on_save_report()
    finally:
        dlg.close()
    assert seen["start"].parent == ti3.parent
    assert want.read_text(encoding="utf-8") == "not a folder"
    assert (ti3.parent / seen["start"].name).is_file()
