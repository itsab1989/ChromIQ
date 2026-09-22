"""Round 2-A adversary findings on K13 / K4 / round A (2026-09-22), each
reproduced ON SCREEN first (~/Desktop/ChromIQ-beta36-proof/round2-A-features/).

Every test here WAS xfail(strict=True) and passes since the fixes of 2026-09-22; it describes the behaviour the finding
asks for, and turns the suite red the moment the fault is fixed without the
marker being removed.
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


def _live_reports(run):
    out = list((run.dir / "reports").glob("report_*.json"))
    for v in run.verifications():
        out += list((v.dir / "reports").glob("report_*.json"))
    return {p: p.read_bytes() for p in out}


def test_a_stale_saved_report_is_shown_as_the_type_its_file_records(
        two_dates, qapp):
    """Every demo project: the file says t1/t2, the list says Full colour
    check, the pulldown and the page say what the run would default to.
    ui/dialogs/measurement_report_dialog.py:2311-2321 keeps only the verdict
    keys across the rebuild."""
    from workflow.measurement_report import REPORT_SCHEMA, REPORT_TYPE_GREY
    s, _fm, run, vs = two_dates
    v = vs[-1]
    for p in (v.dir / "reports").glob("report_*.json"):
        rep = json.loads(p.read_text(encoding="utf-8"))
        rep["report_type"] = REPORT_TYPE_GREY
        rep["schema"] = REPORT_SCHEMA - 1          # stale: the window rebuilds it
        p.write_text(json.dumps(rep), encoding="utf-8")
    dlg = _window(s, v.measurement_ti3, qapp)
    try:
        key = str(dlg._loaded_doc_id)
        assert key and key != "new:", key
        assert dlg._report_type_now() == REPORT_TYPE_GREY, (
            f"the file records {REPORT_TYPE_GREY}, the window shows "
            f"{dlg._report_type_now()}")
    finally:
        dlg.close()


def test_create_new_on_a_disallowed_saved_type_writes_the_kinds_type(
        two_dates, qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_RECORD)
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                           every_measurement=False, detail=False)
    dlg.close()
    # what beta 35 was allowed to write: a Printing record of a verification
    for p in _live_reports(run):
        rep = json.loads(p.read_text(encoding="utf-8"))
        if (rep.get("document") or {}).get("id") and \
                f"id:{rep['document']['id']}" == key:
            rep["report_type"] = REPORT_TYPE_RECORD
            rep["document"]["type"] = REPORT_TYPE_RECORD
            p.write_text(json.dumps(rep), encoding="utf-8")
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        _pick_key(dlg, key, qapp)
        before = _live_reports(run)
        dlg._say_generated = lambda saved, failed: None
        monkeypatch.setattr(QMessageBox, "exec", _press("Create New"))
        dlg._on_generate_report()
        qapp.processEvents()
        new = [p for p in _live_reports(run) if p not in before]
        assert new, "Create New wrote nothing"
        types = {json.loads(p.read_text(encoding="utf-8")).get("report_type") for p in new}
        assert REPORT_TYPE_RECORD not in types, (
            f"Create New wrote a Printing record of a verification: {types}")
    finally:
        dlg.close()


def test_an_update_that_adds_an_unwritable_date_writes_nothing(
        two_dates, qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    locked = None
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=False, detail=False)
        _pick_key(dlg, key, qapp)
        dlg._select_all_btn.click()            # brings the other date in
        qapp.processEvents()
        locked = vs[0].dir / "reports"
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        if os.access(locked, os.W_OK):
            pytest.skip("this user can write a read-only folder (root?)")
        before = _live_reports(run)
        said = {}
        dlg._say_generated = lambda saved, failed: said.update(
            saved=list(saved), failed=list(failed))
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        after = _live_reports(run)
        assert after == before, (
            "a refused update still wrote: "
            f"{[str(p) for p in after if before.get(p) != after[p]]}")
        assert not said.get("saved"), said
    finally:
        if locked is not None:
            os.chmod(locked, stat.S_IRWXU)
        dlg.close()


def test_a_refused_update_leaves_no_archive_behind(tmp_path, qapp, monkeypatch):
    """R2A-4: a refused Update still copied every date into old/ for a rewrite
    that never happened. The write check now comes BEFORE the archive.
    MUTATION: archive before checking again and old/ appears: red."""
    import os
    import stat
    from PyQt6.QtWidgets import QMessageBox
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _pick_key, _press, _window)
    from tests.test_a_generated_report_is_one_document import _messy_project
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    locked = None
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        dirs = sorted({(Path(str(r.get("_origin_dir"))) / "reports")
                       for r, _n in entry["members"]})
        assert len(dirs) >= 2
        locked = dirs[0]
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        if os.access(locked, os.W_OK):
            pytest.skip("this user can write a read-only folder")
        dlg._say_generated = lambda saved, failed: None
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        for d in dirs[1:]:
            assert not (d / "old").exists(), (
                f"{d}/old was made for an update that wrote nothing")
    finally:
        if locked is not None:
            os.chmod(locked, stat.S_IRWXU)
        dlg.close()


def test_clear_list_forgets_the_selected_report(tmp_path, qapp):
    """R2A-6: after Clear list the cleared report stayed selected, so Update
    could rewrite it. MUTATION: drop the reset in `_on_clear_list`: red."""
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _pick_key, _window)
    from tests.test_a_generated_report_is_one_document import _messy_project
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        dlg._on_clear_list()
        qapp.processEvents()
        assert dlg._loaded_doc_id in ("", NEW_REPORT_KEY), dlg._loaded_doc_id
        assert dlg._document_being_updated() is None
    finally:
        dlg.close()
