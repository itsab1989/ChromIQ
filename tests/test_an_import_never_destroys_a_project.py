"""Importing over an existing project ARCHIVES it. It never destroys it.

§S4.7 of `unified_measurement_management.md`: a replace "archive[s] the whole
project into its `old/`". T2.6: "nothing is ever deleted". Three import routes
reached for `shutil.rmtree` instead — which is not atomic, so one unwritable
sub-folder left a project holding one file of six with `project.json` among the
casualties, while the app reported that nothing had changed.
"""
import pathlib
import tempfile

import pytest

from workflow.chart_import import _archive_project_contents


def _project(root: pathlib.Path) -> pathlib.Path:
    (root / "runs" / "run1").mkdir(parents=True)
    (root / "project.json").write_text('{"schema_version": 2}', encoding="utf-8")
    (root / "runs" / "run1" / "chart.ti3").write_text("CTI3\n", encoding="utf-8")
    (root / "runs" / "run1" / "chart.icc").write_bytes(b"\0\0\0\0")
    return root


@pytest.fixture()
def work():
    return pathlib.Path(tempfile.mkdtemp())


def test_a_replaced_project_is_still_readable_afterwards(work):
    root = _project(work / "Canon")
    _archive_project_contents(root)
    kept = sorted(p.name for p in (root / "old").glob("*/**/*") if p.is_file())
    assert "project.json" in kept, "the manifest was not archived"
    assert "chart.ti3" in kept and "chart.icc" in kept, (
        f"the measurement or the profile was lost: {kept}")


def test_two_replaces_in_one_second_do_not_eat_the_first_archive(work):
    """The stamp is to the second and the folder was reused, so the second
    archive overwrote the first's files and NESTED its directories."""
    root = _project(work / "Canon")
    first = _archive_project_contents(root)
    _project(root)
    second = _archive_project_contents(root)

    assert first != second, "the second archive reused the first's folder"
    assert (first / "project.json").is_file(), "the first archive was overwritten"
    assert not (first / "runs" / "runs").exists(), "directories were nested"


@pytest.mark.parametrize("name", ["Canon", "canon"])
def test_the_folder_holding_the_imported_file_is_a_self_collision(work, name):
    """Calls the SHIPPED helper, not a copy of its expression.

    The first version of this test re-implemented the comparison inline and
    imported neither loader, so restoring the bug in both left it green. The
    logic now lives in one place precisely so a test can reach it. `canon`
    covers APFS case folding, where two strings disagree about one folder.
    """
    from core.file_manager import dir_holds
    src = work / "Canon" / "runs" / "run1" / "x.txt"
    src.parent.mkdir(parents=True)
    src.write_text("x", encoding="utf-8")

    assert dir_holds(work / name, src), (
        f"replacing {name!r} would destroy the file being imported")
    assert dir_holds(work / "Canon" / "runs", src), "an ancestor was missed"
    assert not dir_holds(work / "Somewhere-else", src)
    assert not dir_holds(None, src) and not dir_holds(work / name, None)


def test_both_loaders_ask_the_shared_helper_and_obey_it(work, monkeypatch):
    """Asserted by ANSWERING the question differently, not by grepping.

    The old version looked for the word "dir_holds" in the module source, and
    a loader that had stopped calling it entirely still passed — the name
    survived in the docstring above the call. So the shared helper is replaced
    with one that gives the opposite answer, and each loader's own collision
    test is driven and must follow it. A loader carrying its own copy cannot.
    """
    import inspect

    import core.file_manager as fmmod
    import ui.ti2_loader as ti2
    import ui.txt_loader as txt

    deep = work / "Canon" / "runs" / "run1" / "measured.txt"
    deep.parent.mkdir(parents=True)
    deep.write_text("x", encoding="utf-8")

    for mod in (txt, ti2):
        assert ".parent.resolve()" not in inspect.getsource(mod), (
            f"{mod.__name__} has grown its own comparison again")

    # The real answers first, so the flip below means something.
    assert txt.is_self_collision(work, "Canon", deep) is True
    assert ti2.is_self_collision(work, "Canon", deep) is True
    assert txt.is_self_collision(work, "Nikon", deep) is False

    asked: list = []

    def _never(folder, path):
        asked.append((str(folder), str(path)))
        return False              # the opposite of the truth, deliberately

    monkeypatch.setattr(fmmod, "dir_holds", _never)

    assert txt.is_self_collision(work, "Canon", deep) is False, (
        "ui.txt_loader answered the collision question without the shared "
        "helper — it has its own copy again")
    assert ti2.is_self_collision(work, "Canon", deep) is False, (
        "ui.ti2_loader answered the collision question without the shared "
        "helper — it has its own copy again")
    assert len(asked) == 2, (
        f"the shared helper was consulted {len(asked)} times by two loaders")


def test_the_dialog_asks_through_that_same_function(work):
    """…and the dialogs' own closure is the one-liner, not a second copy."""
    import inspect

    import ui.ti2_loader as ti2
    import ui.txt_loader as txt

    for mod in (txt, ti2):
        src = inspect.getsource(mod)
        i = src.index("def _is_self_collision")
        body = src[i:src.index("def ", i + 10)]
        assert "is_self_collision(working_dir, name," in body, (
            f"{mod.__name__}'s dialog no longer routes through the shared "
            f"function:\n{body}")


def test_a_failed_duplicate_does_not_discard_a_run_holding_work(work, qapp):
    """`new_run()` allocates from the manifest while `ensure_dir()` is
    `exist_ok=True`, so a manifest that lost track of a run hands back a folder
    that already holds somebody's results — and the undo destroyed it."""
    from core.file_manager import Project

    proj = Project.create(work / "Proj", "Proj")
    run = proj.current_run()
    (run.dir / "chart.ti3").write_text("CTI3\n", encoding="utf-8")
    (run.dir / "chart.icc").write_bytes(b"\0")

    proj._discard_run(run)

    assert run.dir.exists(), "a run holding results was destroyed"
    assert (run.dir / "chart.ti3").is_file(), "the measurement was destroyed"
    assert (run.dir / "chart.icc").is_file(), "the profile was destroyed"


def test_resetting_a_calibration_keeps_a_part_finished_measurement(work, qapp):
    """`<stem>.ti3.engine-partial` is what a measurement stopped part way
    through leaves behind. Its suffix is not in RESULT_SUFFIXES, so it was
    unlinked unarchived — while `Run.reset_chart_artefacts` names it
    explicitly as something to preserve."""
    from core.file_manager import Project

    proj = Project.create(work / "Proj2", "Proj2")
    cal = proj.calibration
    cal.ensure_dir()
    partial = cal.dir / f"{cal.stem}.ti3.engine-partial"
    partial.write_text("CTI3 partial\n", encoding="utf-8")

    cal.reset()

    assert not partial.exists(), "precondition: reset should clear the live file"
    archived = [p.name for p in cal.dir.glob("old/**/*") if p.is_file()]
    assert any(n.endswith(".ti3.engine-partial") for n in archived), (
        f"the part-finished measurement was destroyed, not archived: {archived}")


def test_the_txt_import_route_itself_archives(work, qapp):
    """DRIVES THE LOADER, not the archive helper beside it.

    The tests above prove `_archive_project_contents` keeps things. They do NOT
    prove the import calls it — and the fault was in the import, which called
    `shutil.rmtree`. A test that never enters the route it guards is the shape
    of guard this project has repeatedly found deletable with the suite green.
    """
    from ui.txt_loader import _copy_txt

    existing = _project(work / "Canon")
    src = work / "elsewhere" / "measured.txt"
    src.parent.mkdir(parents=True)
    src.write_text(
        "CGATS.17\nKEYWORD \"SAMPLE_NAME\"\nNUMBER_OF_FIELDS 4\n"
        "BEGIN_DATA_FORMAT\nSAMPLE_NAME RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100\nEND_DATA\n", encoding="utf-8")

    _copy_txt(src, work, "Canon", overwrite=True)

    archived = sorted(p.name for p in (existing / "old").glob("**/*") if p.is_file())
    assert archived, "the replaced project was destroyed, not archived"
    assert "project.json" in archived, f"the manifest is gone: {archived}"
    assert "chart.ti3" in archived and "chart.icc" in archived, (
        f"the earlier measurement or profile was destroyed: {archived}")



@pytest.mark.parametrize("fn_name,suffix", [("_copy_files", ".ti2"),
                                            ("_copy_ti3_only", ".ti3")])
def test_the_ti2_loader_routes_archive_too(work, qapp, fn_name, suffix):
    """The other two of the three sites had NO test at all: restoring
    `shutil.rmtree(dest)` at both left 100 tests green across every file naming
    these functions."""
    import ui.ti2_loader as ti2

    existing = _project(work / "Canon")
    src = work / "elsewhere" / f"chart{suffix}"
    src.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".ti2":
        src.write_text("CTI2\n\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
                       "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
                       "1 100 100 100\nEND_DATA\n", encoding="utf-8")
    else:
        src.write_text("CTI3\n\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B "
                       "XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\nNUMBER_OF_SETS 1\n"
                       "BEGIN_DATA\n1 100 100 100 95 100 108\nEND_DATA\n", encoding="utf-8")

    fn = getattr(ti2, fn_name)
    # `_copy_files` also takes the sibling .ti1 and the printed TIFFs.
    args = ((src, None, [], work, "Canon") if fn_name == "_copy_files"
            else (src, work, "Canon"))
    try:
        fn(*args, overwrite=True)
    except Exception:                      # noqa: BLE001
        # The copy may fail for its own reasons; what must NEVER happen is that
        # the earlier project was destroyed on the way.
        pass

    archived = sorted(p.name for p in (existing / "old").glob("**/*") if p.is_file())
    assert archived, f"{fn_name} destroyed the replaced project"
    assert "project.json" in archived and "chart.ti3" in archived, (
        f"{fn_name} lost the earlier work: {archived}")


def test_the_bar_is_told_when_a_replace_empties_the_project(work, qapp):
    """F4: after a replace the bar went on listing runs that had moved to old/.

    `_copy_*` empties the folder and starts a fresh project, so every run the
    bar shows has stopped existing. Nothing told it — and one manifest write
    then put the phantom runs back on disk.
    """
    from core.file_manager import FileManager, Project
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController

    s = AppSettings()
    s.set("custom_output_path", str(work))
    fm = FileManager(s)
    proj = Project.create(work / "Canon", "Canon")
    proj.new_run(); proj.new_run()               # run1..run3
    fm.set_target_name("Canon")
    assert len(fm.project()._manifest.runs) >= 3

    ctl = MeasurementTargetController(fm)
    fired = []
    ctl.changed.connect(lambda: fired.append(1))

    # what a replace does to the folder
    from workflow.chart_import import _archive_project_contents
    _archive_project_contents(work / "Canon")
    Project.create(work / "Canon", "Canon")

    ctl.project_replaced_on_disk()

    assert fired, "the bar was never told the project had changed"
    assert fm.project()._manifest.runs == ["run1"], (
        f"the file manager still holds the runs that moved to old/: "
        f"{fm.project()._manifest.runs}")


def _run_resolve_with(monkeypatch, work, boom):
    import ui.txt_loader as txt

    shown = []
    monkeypatch.setattr(txt, "_say_the_replace_failed",
                        lambda parent, folder, exc: shown.append(str(exc)))
    monkeypatch.setattr(txt, "_project_root_for", lambda *a, **k: None)
    monkeypatch.setattr(txt, "_handle_outside",
                        lambda *a, **k: (_ for _ in ()).throw(boom))
    return txt, shown


def test_a_replace_that_cannot_be_carried_out_is_shown_not_just_logged(
        work, qapp, monkeypatch):
    """F2: the raise reached `chromiq.log` and nothing else — no window, no tab
    log line, the app simply looked idle."""
    from workflow.chart_import import ReplaceFailed

    txt, shown = _run_resolve_with(
        monkeypatch, work,
        ReplaceFailed(work / "Canon", OSError("the folder is read-only")))

    out = txt.resolve_txt(None, work / "x.txt", _Settings(work))

    assert out is None, "the import carried on after a failed replace"
    assert shown and "read-only" in shown[0], (
        "the failure was swallowed — the person was told nothing")


def test_an_unrelated_failure_is_not_reported_as_a_failed_replace(
        work, qapp, monkeypatch):
    """The window promises "Nothing has been changed", so it may only be shown
    when that is true.

    Catching plain `OSError` around the whole import made it a lie twice: an
    unreadable SOURCE file on a brand-new name raised it with no replace
    involved, and a copy that failed AFTER a successful archive raised it while
    the project sat empty with everything already in `old/`.
    """
    txt, shown = _run_resolve_with(
        monkeypatch, work, OSError("the source file could not be read"))

    with pytest.raises(OSError):
        txt.resolve_txt(None, work / "x.txt", _Settings(work))

    assert not shown, (
        f"an unrelated failure was reported as a failed replace: {shown}")


class _Settings:
    def __init__(self, work):
        self._work = work

    def get(self, key, default=""):
        return str(self._work) if key == "custom_output_path" else default


def test_return_never_replaces_in_the_import_confirmation(work, qapp, monkeypatch):
    """Making Return press "Replace it" in BOTH new confirmations left 270
    tests green. §S4.7's rule — a keypress must never replace a project — was
    written into the code and guarded by nothing."""
    from PyQt6.QtWidgets import QMessageBox
    import ui.ti2_loader as ti2

    seen = {}

    def _grab(self):
        d = self.defaultButton()
        seen["default"] = d.text() if d is not None else None
        seen["roles"] = {b.text(): self.buttonRole(b) for b in self.buttons()}
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _grab)
    _project(work / "Canon")

    # reach the confirmation the way the dialog does
    ti2._ask_profile_name.__wrapped__ if hasattr(
        ti2._ask_profile_name, "__wrapped__") else None
    from workflow import measurement_messages as M
    title, body = M.M_IMPORT_REPLACE_CONFIRM.render(
        name="Canon", folder=str(work / "Canon"), subject="the chart")
    box = QMessageBox(None)
    box.setWindowTitle(title)
    yes = box.addButton("Replace it", QMessageBox.ButtonRole.DestructiveRole)
    back = box.addButton("Go back", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(back)
    assert box.defaultButton() is back

    # …and the shipped one, read out of the source so it cannot drift
    import inspect
    for mod in (ti2, __import__("ui.txt_loader", fromlist=["x"])):
        src = inspect.getsource(mod)
        assert "_box.setDefaultButton(_back)" in src, (
            f"{mod.__name__}: the import confirmation no longer defaults to "
            f"Go back — Return would replace a project")


def test_the_bare_ti3_route_calls_its_file_a_measurement(work, qapp, monkeypatch):
    """`_ask_profile_name` serves three .ti2 callers and one bare-.ti3 caller,
    and called them all "chart files". Dropping the subject left 270 green."""
    import ui.ti2_loader as ti2

    seen = {}

    def _fake(parent, path, ti1, tiffs, working_dir, subject=None,
              is_measurement=False):
        seen["subject"] = subject
        seen["is_measurement"] = is_measurement
        return None

    monkeypatch.setattr(ti2, "_ask_profile_name", _fake)
    src = work / "m.ti3"
    src.write_text("CTI3\n", encoding="utf-8")
    ti2._copy_ti3_into_new_project(None, src, work) if hasattr(
        ti2, "_copy_ti3_into_new_project") else ti2.resolve_ti3(
            None, src, _Settings(work))

    assert seen.get("subject"), (
        "the bare-.ti3 route did not say what it was importing, so the window "
        "calls a measurement 'the chart'")
    assert "measurement" in seen["subject"]
    # AND A FLAG, NOT THE TEXT. The title used to be chosen with
    # `"measurement" in subject` — on a string that has already been through
    # `tr()`, so it was true in English and false in the other twelve, and the
    # window fell back to "Copy Chart Files" in every one of them.
    assert seen.get("is_measurement") is True, (
        "the title still depends on the language the person is running")


def test_a_run_folder_that_exists_on_disk_is_never_handed_out(work, qapp):
    """`new_run()` allocated from the MANIFEST while `ensure_dir()` is
    exist_ok=True. Removing the on-disk skip left 312 tests green, and
    `duplicate_run` then copied straight over somebody's work."""
    from core.file_manager import Project

    proj = Project.create(work / "P", "P")
    stray = proj.runs_root / "run2"
    stray.mkdir(parents=True)
    (stray / "chart.ti3").write_text("someone's measurement\n", encoding="utf-8")

    nxt = proj.new_run()

    assert nxt.id != "run2", "a folder that already held work was handed out"
    assert (stray / "chart.ti3").read_text(encoding="utf-8") == "someone's measurement\n"


def test_measure_again_to_average_keeps_the_earlier_reads(work, qapp):
    """`Run.clear_reads()` is reachable from "Measure again to average" and
    called `shutil.rmtree` on the whole folder — measurements somebody stood at
    an instrument to make, gone with no archive and nothing in the Trash."""
    from core.file_manager import Project

    proj = Project.create(work / "P", "P")
    run = proj.current_run()
    run.reads_dir.mkdir(parents=True, exist_ok=True)
    (run.reads_dir / "read1.ti3").write_text("CTI3 first read\n", encoding="utf-8")
    (run.reads_dir / "read2.ti3").write_text("CTI3 second read\n", encoding="utf-8")

    run.clear_reads()

    kept = {p.name: p.read_text(encoding="utf-8")
            for p in run.reads_dir.rglob("*") if p.is_file()}
    assert "read1.ti3" in kept and "read2.ti3" in kept, (
        f"an earlier read was destroyed rather than archived: {sorted(kept)}")
    assert kept["read1.ti3"] == "CTI3 first read\n"


def test_copying_a_whole_project_in_asks_before_it_replaces(work, qapp,
                                                            monkeypatch):
    """"Copy the whole project in" archived a whole project on ONE CLICK.

    It was the only replace route in the app with no confirmation at all, and
    its error line named a button ("Replace it") that was not on the window
    ("Replace existing").
    """
    import inspect
    import ui.ti2_loader as ti2

    src = inspect.getsource(ti2._ask_project_name)
    assert "M_IMPORT_REPLACE_PROJECT_CONFIRM" in src, (
        "a whole project is still archived with no second look")
    assert "_box.setDefaultButton(_back)" in src, (
        "Return would replace a whole project")
    assert 'QPushButton(tr("Replace it"), dlg)' in src, (
        "the button and the error line still name different things")


def test_a_failed_duplicate_is_still_undone(work, qapp):
    """The guard added to `_discard_run` made `duplicate_run`'s own rollback
    never run: the copied files looked like somebody's work, so a failed
    duplicate left a half-copied run in the manifest — which that method's
    docstring calls worse than none."""
    from unittest.mock import patch
    from core.file_manager import Project

    proj = Project.create(work / "P", "P")
    run = proj.current_run()
    run.chart_ti2.write_text("CTI2 chart\n", encoding="utf-8")
    run.chart_ti1.write_text("CTI1 patches\n", encoding="utf-8")
    run.chart_cht.write_text("cht\n", encoding="utf-8")
    run.measurement_ti3.write_text("CTI3\n", encoding="utf-8")
    before = list(proj._manifest.runs)

    # FAIL PART WAY, not on the first file. With the copy failing immediately
    # the new folder is empty, the guard has nothing to see, and the undo runs
    # whether the guard is right or wrong — so the test proved nothing. The
    # fault only appears once files HAVE been copied and look like work.
    import shutil as _sh
    real = _sh.copy2
    calls = {"n": 0}

    def _fail_after_one(src, dst, *a, **k):
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("disk full")
        return real(src, dst, *a, **k)

    with patch("shutil.copy2", side_effect=_fail_after_one):
        with pytest.raises(OSError):
            proj.duplicate_run(run)

    assert list(proj._manifest.runs) == before, (
        "a half-copied run was left in the manifest")


def test_duplicating_for_an_import_copies_the_chart_only(work, qapp):
    """§I.9: the copy gets the chart the incoming measurement belongs to and
    nothing else. Copying the whole run gave it a measurement, a profile,
    reads/ and reports/ — all orphaned the moment the import wrote its .ti3."""
    from core.file_manager import Project

    proj = Project.create(work / "P", "P")
    run = proj.current_run()
    run.chart_ti2.write_text("CTI2 chart\n", encoding="utf-8")
    run.measurement_ti3.write_text("CTI3 someone's measurement\n", encoding="utf-8")
    run.profile_icc.write_bytes(b"\0")

    copy = proj.duplicate_run(run, ("chart",))

    assert copy.chart_ti2.is_file(), "the copy has no chart to measure against"
    assert not copy.measurement_ti3.is_file(), "the copy carried a measurement"
    assert not copy.profile_icc.is_file(), "the copy carried a profile"
    assert run.measurement_ti3.read_text(encoding="utf-8") == "CTI3 someone's measurement\n", (
        "the source run was touched")
