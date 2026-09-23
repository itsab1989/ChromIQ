"""Round 3-A adversary findings on d68d7026 (2026-09-23), each reproduced ON
SCREEN first (~/Desktop/ChromIQ-beta36-proof/round3-A-features/REPORT.md).

Every test is xfail(strict=True): it describes the behaviour the finding asks
for, fails today for the finding's reason, and turns the suite red the moment
the fault is fixed without the marker being removed.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from tests.test_generate_report_asks_what_to_do import (       # noqa: E402
    _a_real_document, _pick_key, _press, _window, two_dates)   # noqa: F401


def _old_dirs(run):
    out = set()
    for d in [run.dir] + [v.dir for v in run.verifications()]:
        old = d / "reports" / "old"
        if old.is_dir():
            out |= {p for p in old.iterdir() if p.is_dir()}
    return out


@pytest.mark.xfail(strict=True, reason="R3A-2: a moved document ticks its "
                   "leftover member, so 'Nothing was changed' + Update widens it")
def test_a_moved_document_does_not_tick_the_date_an_update_took_out(
        two_dates, qapp, tmp_path, monkeypatch):
    import shutil
    from PyQt6.QtWidgets import QMessageBox
    from core.file_manager import Project
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=False)
        _pick_key(dlg, key, qapp)
        dropped = dlg._run_key(dlg._history[0])
        dlg._hidden_runs.add(dropped)
        dlg._settings_touched()
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        _pick_key(dlg, key, qapp)
        in_place = sorted(r.get("created") for r in dlg._runs_for_report())
        project_dir = run.dir.parent.parent
    finally:
        dlg.close()
    assert len(in_place) == 1, in_place

    moved_root = tmp_path / "moved-r3a2"
    moved_root.mkdir()
    shutil.copytree(project_dir, moved_root / project_dir.name)
    s.set("custom_output_path", str(moved_root))
    moved = Project.load(moved_root / project_dir.name)
    r2 = moved.all_runs()[0]
    dlg2 = _window(s, r2.verifications()[-1].measurement_ti3, qapp)
    try:
        _pick_key(dlg2, key, qapp)
        ticked = sorted(r.get("created") for r in dlg2._runs_for_report())
        assert ticked == in_place, (
            f"the moved copy ticks {ticked!r}; the document covers {in_place!r}")
    finally:
        dlg2.close()


# R3A-3: FIXED 2026-09-23; this was a strict xfail and is now the guard.
def test_already_generated_counts_an_untyped_report_as_its_label_says(
        two_dates, qapp):
    from workflow.measurement_report import (REPORT_TYPE_SUMMARY,
                                             generated_report_types)
    from workflow.run_compliance import set_run_report_type
    s, _fm, run, vs = two_dates
    set_run_report_type(run, REPORT_TYPE_SUMMARY)
    for v in vs:
        for p in (v.dir / "reports").glob("report_*.json"):
            rep = json.loads(p.read_text(encoding="utf-8"))
            rep.pop("report_type", None)
            rep.pop("document", None)
            p.write_text(json.dumps(rep), encoding="utf-8")
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        labelled = set()
        for r in dlg._history:
            for name in (r.get("_all_report_files") or []):
                p = Path(str(r.get("_origin_dir"))) / "reports" / name
                labelled.add(dlg._type_a_file_renders_as(
                    json.loads(p.read_text(encoding="utf-8")), r))
        counted = set(generated_report_types(run))
        assert counted == labelled, (
            f"the list labels these files {labelled}, the 'Already generated' "
            f"line counts them as {counted}")
    finally:
        dlg.close()


# R3A-4: FIXED 2026-09-23; this was a strict xfail and is now the guard.
def test_adding_a_measurement_is_a_change_to_the_selected_report(
        two_dates, qapp, monkeypatch):
    """R3A-4: when the loaded measurements differ from the ones the selected
    document was drawn from, the question says the settings were modified.

    Since the final round before beta 36, every way Add can change the list
    under a selected report is refused before this question (another run is
    several places, the run's profiling sheet is both kinds), so the state is
    set directly: the document's recorded sources against today's.

    MUTATION: drop `sources_moved` from `modified` and the box says "Nothing
    was changed": red."""
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=False, detail=False)
        _pick_key(dlg, key, qapp)
        dlg._doc_sources = ("/somewhere/else.ti3",)
        asked = []

        def _cancel(box):
            asked.append(box.text())
            for b in box.buttons():
                if b.text().replace("&", "") == "Cancel":
                    b.click()
            return 0
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _cancel)
        dlg._on_generate_report()
        qapp.processEvents()
        assert asked, "no question was asked"
        assert not asked[0].startswith("Nothing was changed"), asked[0]
    finally:
        dlg.close()


def test_a_refused_update_leaves_no_archive_even_when_the_archive_fails(
        two_dates, qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    locked = None
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=False)
        _pick_key(dlg, key, qapp)
        locked = vs[0].dir / "reports" / "old"
        locked.mkdir(exist_ok=True)
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        if os.access(locked, os.W_OK):
            pytest.skip("this user can write a read-only folder (root?)")
        before = _old_dirs(run)
        dlg._detail_check.setChecked(True)
        qapp.processEvents()
        said = {}
        dlg._say_generated = lambda saved, failed: said.update(
            saved=list(saved), failed=list(failed))
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        assert not said.get("saved"), said
        made = _old_dirs(run) - before
        assert not made, f"a refused update archived into {sorted(map(str, made))}"
    finally:
        if locked is not None:
            os.chmod(locked, stat.S_IRWXU)
        dlg.close()
