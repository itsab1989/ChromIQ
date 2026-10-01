"""#182 (c): a saved report keeps the run number it was saved in.

Knut, 2026-10-01: he deleted runs 1 to 4, and every report saved in run 5 then
said "run 1": on the page, in the PDF, and in the file itself, because the run
delete renumbers the references (§13.14) and the page read the run number off
the folder the report sits in now. §53.1 (CONFIRMED, Knut 2026-09-27): a saved
report selected in "Report shown" shows *"the exact data that was saved at the
time it was saved"*.

What is frozen is the RUN NUMBER only (the challenge's minimal design):
``saved_as: {"run": N}`` at the top of the file and in each measurement entry,
written when the report is saved and, by a run delete, before anything moves
for every report that lacks it (a report with no document block included).
The first value is never changed. References keep following the runs. Project
name, list label, title and PDF name are untouched (they need Knut).

Driven through the real writers: the Measure tab's automatic report, the bar's
run delete (`core.run_delete.delete_run`, the Trash sandboxed by conftest),
`Project.rename`, and the report window's page and PDF.

MUTATIONS, each proved red (MUTATIONS.md of H_impl_182):
* drop the `stamp_saved_as` call in `save_report`;
* drop the `_in_a_moved_run` stamp in `run_references_plan` (the legacy
  report test red);
* drop the `saved_as` stamp in `_renumber_entry`;
* `_run_number_for` without the `SAVED_RUN_KEY` read (the page tests red);
* `_judged_by_the_document` stamping the live branch too (the New report test
  red);
* drop the `SAVED_AS_KEY` skip in `_rename_stems` (the stems unit test red);
* `rewrite_report` without `prior` (the Update test red).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_import_measurement_module import (_PATCHES, _cgats,  # noqa: E402
                                                  _verify_env)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Target:
    def __init__(self, profile_run):
        self.profile_run = profile_run
        self.run_type = "profiling"
        self.verification_id = ""

    def is_verification(self):
        return False


def _read(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _five_runs(tmp_path, qapp):
    """Knut's shape: runs 1 to 5, run 5 with a dated verification whose
    automatic report the Measure tab wrote, and a report from before the
    document block (B8-388) in the same date."""
    from core.file_manager import RunMeta
    from tests.test_the_measurement_report_defaults_are_knuts import \
        _measure_tab
    s, fm, ctl, run1 = _verify_env(tmp_path)
    proj = fm.project()
    for _ in range(4):
        proj.new_run()
    proj = fm.project()
    for run in proj.all_runs():
        run.ensure_dir()
        if not run.meta_path.exists():
            run.save_meta(RunMeta.fresh(run.id))
    run5 = proj.run("run5")
    run5.profile_icc.write_bytes(b"icc")
    run5.verifications_dir.mkdir(parents=True, exist_ok=True)
    run5.verify_chart_ti2.write_text(_cgats("CTI2", _PATCHES), encoding="utf-8")
    v = run5.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
    finally:
        tab.deleteLater()
    auto = sorted((v.dir / "reports").glob("report_*.json"))
    assert len(auto) == 1
    # a report as ChromIQ wrote it before the document block and this fix
    legacy = _read(auto[0])
    legacy.pop("document", None)
    legacy.pop("saved_as", None)
    legacy["created"] = "2026-09-01T10:00:00"
    old = v.dir / "reports" / "report_2026-09-01_10-00-00.json"
    old.write_text(json.dumps(legacy, indent=2), encoding="utf-8")
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    return s, proj, v, auto[0], old


def _delete_runs_1_to_4(proj):
    """The bar's Delete of run 1, four times, as Knut did. Each deleted
    folder goes to a sandboxed Trash of its own (the suite's sandbox names a
    folder by its path, and run 1 is deleted from one path four times)."""
    import shutil

    import core.run_delete as rd
    import core.trash as ct
    from core.file_manager import Project
    trash = Path(proj.root).parent / "trash-182c"
    trash.mkdir(exist_ok=True)
    count = [0]

    def _to_trash(path):
        count[0] += 1
        dest = trash / f"{Path(path).name}-{count[0]}"
        shutil.move(str(path), str(dest))
        return ct.TrashResult(True, dest)
    real = rd.move_to_trash
    rd.move_to_trash = _to_trash
    try:
        for _ in range(4):
            proj = Project.load(proj.root)
            plan = rd.plan_for(proj, _Target("run1"))
            assert plan.kind == rd.KIND_RUN, plan
            rd.delete_run(proj, plan)
    finally:
        rd.move_to_trash = real
    return Project.load(proj.root)


def _now_in_run1(proj, v):
    d = proj.root / "runs" / "run1" / "verifications" / v.dir.name
    assert d.is_dir(), list((proj.root / "runs").iterdir())
    return d


# --------------------------------------------------------------------------
# what is written
# --------------------------------------------------------------------------
def test_the_automatic_report_records_the_run_it_was_saved_in(tmp_path, qapp):
    _s, _proj, _v, auto, _old = _five_runs(tmp_path, qapp)
    rep = _read(auto)
    assert rep.get("saved_as") == {"run": 5}, rep.get("saved_as")
    ms = rep["document"]["measurements"]
    assert [m.get("saved_as") for m in ms] == [{"run": 5}]


def test_a_run_delete_stamps_every_report_before_it_moves(tmp_path, qapp):
    """Including the report with no document block, which no reference
    rewrite ever touched; its modification time is kept."""
    _s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    mtime = old.stat().st_mtime
    proj = _delete_runs_1_to_4(proj)
    d = _now_in_run1(proj, v)
    moved_old = d / "reports" / old.name
    rep = _read(moved_old)
    assert rep.get("saved_as") == {"run": 5}, (
        "a report from before the document block was not stamped before "
        "its run was renumbered")
    assert abs(moved_old.stat().st_mtime - mtime) < 0.01
    new = _read(d / "reports" / auto.name)
    assert new["saved_as"] == {"run": 5}
    m = new["document"]["measurements"][0]
    assert m["saved_as"] == {"run": 5}
    # references still follow the run (§13.14)
    assert "/runs/run1/" in m["dir"].replace("\\", "/"), m["dir"]


def test_a_reference_renumbered_records_its_run_first(tmp_path):
    """`_renumber_entry` on an entry with no saved_as: the number it had
    is recorded before the reference moves, and a value already there is
    never changed."""
    from core.report_refs import _renumber_entry
    m = {"dir": "/x/P/runs/run5/verifications/2026-10-01_184318",
         "created": "c", "ti3": "P-verify.ti3",
         "key": "/x/P/runs/run5/verifications/2026-10-01_184318|c|P-verify.ti3"}
    assert _renumber_entry(m, frozenset({"P"}), {"run5": "run4"}, "run1")
    assert m["saved_as"] == {"run": 5}
    assert "/runs/run4/" in m["dir"]
    assert _renumber_entry(m, frozenset({"P"}), {"run4": "run3"}, "run1")
    assert m["saved_as"] == {"run": 5}, "the first value was changed"


def test_a_rename_never_rewrites_saved_as(tmp_path, qapp):
    _s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    before = _read(auto)["saved_as"], _read(auto)["document"]["measurements"][0]["saved_as"]
    from core.file_manager import Project
    p = Project.load(proj.root)
    p.rename("Renamed")
    p = Project.load(proj.root if proj.root.exists() else p.root)
    hits = list(Path(p.root).rglob(auto.name))
    assert len(hits) == 1, hits
    rep = _read(hits[0])
    assert (rep["saved_as"], rep["document"]["measurements"][0]["saved_as"]) \
        == before


def test_rename_stems_skips_saved_as(tmp_path):
    from core.report_refs import _rename_stems
    rep = {"chart": "P-verify", "saved_as": {"run": 5, "chart": "P-verify"}}
    assert _rename_stems(rep, "P", "Q")
    assert rep["chart"] == "Q-verify"
    assert rep["saved_as"] == {"run": 5, "chart": "P-verify"}


# --------------------------------------------------------------------------
# what is shown
# --------------------------------------------------------------------------
def _window(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    qapp.processEvents()
    return dlg


def _pick(dlg, qapp, name: str) -> None:
    combo = dlg._saved_combo
    ctx = dlg._run_ctx
    key = next(d["key"] for d in dlg._saved_documents(ctx.run if ctx else None)
               if any(n == name for _r, n in d["members"]))
    combo.setCurrentIndex(combo.findData(key))
    qapp.processEvents()
    assert dlg._loaded_doc_id == key


def test_after_runs_1_to_4_are_deleted_the_saved_page_still_says_run_5(
        tmp_path, qapp):
    s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    proj = _delete_runs_1_to_4(proj)
    d = _now_in_run1(proj, v)
    dlg = _window(s, d / v.measurement_ti3.name, qapp)
    try:
        for name in (auto.name, old.name):
            _pick(dlg, qapp, name)
            text = dlg._view.toPlainText()
            assert ", run 5" in text, (name, text[:600])
            assert ", run 1" not in text, (name, text[:600])
    finally:
        dlg.close()


def test_a_new_report_names_the_run_the_measurement_is_in_now(tmp_path,
                                                              qapp):
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    proj = _delete_runs_1_to_4(proj)
    d = _now_in_run1(proj, v)
    dlg = _window(s, d / v.measurement_ti3.name, qapp)
    try:
        combo = dlg._saved_combo
        combo.setCurrentIndex(combo.findData(NEW_REPORT_KEY))
        qapp.processEvents()
        before = set((d / "reports").glob("report_*.json"))
        dlg._on_generate_report()            # "New report…" asks nothing
        qapp.processEvents()
        text = dlg._view.toPlainText()
        assert ", run 1" in text, text[:600]
        assert ", run 5" not in text
    finally:
        dlg.close()
    new = set((d / "reports").glob("report_*.json")) - before
    assert len(new) == 1, new
    assert _read(new.pop())["saved_as"] == {"run": 1}


def test_the_german_page_says_lauf_5(tmp_path, qapp):
    import core.i18n as i18n
    previous = getattr(i18n, "_language", "en")
    s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    proj = _delete_runs_1_to_4(proj)
    d = _now_in_run1(proj, v)
    try:
        i18n.set_language("de")
        dlg = _window(s, d / v.measurement_ti3.name, qapp)
        try:
            _pick(dlg, qapp, auto.name)
            text = dlg._view.toPlainText()
            assert ", Lauf 5" in text, text[:600]
        finally:
            dlg.close()
    finally:
        i18n.set_language(previous)


def test_the_pdf_of_the_saved_report_says_run_5(tmp_path, qapp,
                                                monkeypatch):
    import pymupdf
    from PyQt6.QtGui import QDesktopServices
    import ui.widgets as W
    s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    proj = _delete_runs_1_to_4(proj)
    d = _now_in_run1(proj, v)
    out = tmp_path / "saved.pdf"
    monkeypatch.setattr(W, "save_file_dialog", lambda *a, **k: str(out))
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)
    dlg = _window(s, d / v.measurement_ti3.name, qapp)
    try:
        _pick(dlg, qapp, auto.name)
        dlg._export_pdf()
    finally:
        dlg.close()
    assert out.is_file()
    text = " ".join(pg.get_text() for pg in pymupdf.open(str(out)))
    text = " ".join(text.split())
    assert ", run 5" in text, text[:600]
    assert ", run 1" not in text


def test_an_update_keeps_the_run_it_was_first_saved_in(tmp_path, qapp):
    """The first value is never changed: an Update rewrites the report with
    this version, and its saved_as stays the one it was first saved with."""
    s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    proj = _delete_runs_1_to_4(proj)
    d = _now_in_run1(proj, v)
    dlg = _window(s, d / v.measurement_ti3.name, qapp)
    try:
        _pick(dlg, qapp, auto.name)
        dlg._ask_update_or_create_new = lambda: "update"
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
    finally:
        dlg.close()
    rep = _read(d / "reports" / auto.name)
    assert rep.get("document", {}).get("updated"), "no Update happened"
    assert rep["saved_as"] == {"run": 5}, rep.get("saved_as")
    assert rep["document"]["measurements"][0]["saved_as"] == {"run": 5}
