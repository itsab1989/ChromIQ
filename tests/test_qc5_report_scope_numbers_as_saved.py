"""Q-C5: a saved report's Report Scope count is shown as it was saved.

Knut, #182 comment 5950006399 (2026-10-02), on the sentence "This report
covers {n} of the {total} measurements recorded for ...": *"Yes, Show numbers
as they were saved. An update will renew the numbers."*

Until this, the sentence was counted off the disk every time a report was
SHOWN, so a saved report changed its own numbers whenever a run was measured,
duplicated or deleted beside it. Now `workflow.measurement_report.scope_counts`
decides the sentence once, when a report is made, updated or written after a
measurement, and the report stores that decision in its document block
(`scope_count`, ids and whole numbers only). Showing a saved report (page and
PDF) uses the stored decision; `tr()` runs at display time. A report written
before the block existed is counted live, and opening it writes nothing.

Each test names the mutation that turns it red.
"""
import json
import re
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _flat(html_text: str) -> str:
    import html as _h
    return " ".join(_h.unescape(re.sub("<[^>]+>", " ", html_text)).split())


def _page(dlg) -> str:
    return _flat(dlg._view.toHtml())


def _measured(run, shift=0.0):
    from tests.test_import_measurement_module import _cgats, _PATCHES
    run.ensure_dir()
    run.measurement_ti3.write_text(
        _cgats("CTI3", [(min(100.0, r + shift), g, b) for r, g, b in _PATCHES]),
        encoding="utf-8")
    return run


def _project(tmp_path, runs=1):
    """A profiling project whose first *runs* runs are measured."""
    from tests.test_import_measurement_module import _verify_env
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    _measured(run1)
    out = [run1]
    for i in range(1, runs):
        out.append(_measured(fm.project().new_run(), shift=3.0 * i))
    return s, fm, out


def _window(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    dlg._ask_update_or_create_new = lambda: "new"
    return dlg


def _generate(s, ti3, qapp) -> Path:
    """Generate a report on *ti3*'s window; returns the file it wrote."""
    dlg = _window(s, ti3, qapp)
    try:
        before = set(Path(ti3).parent.glob("reports/report_*.json"))
        dlg._on_generate_report()
        qapp.processEvents()
        new = set(Path(ti3).parent.glob("reports/report_*.json")) - before
        assert len(new) == 1, new
        return new.pop()
    finally:
        dlg.close()


def _block(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["document"]


def _pdf(dlg, tmp_path, monkeypatch) -> str:
    """The PDF the window exports, through `_export_pdf` itself."""
    import ui.widgets as W
    from PyQt6.QtGui import QDesktopServices
    out = tmp_path / f"report_{len(list(tmp_path.glob('report_*.pdf')))}.pdf"
    monkeypatch.setattr(W, "save_file_dialog", lambda *a, **k: str(out))
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda *a: True)
    seen: list = []
    real = dlg._pdf_html

    def _keep(runs, charts_html):
        seen.append(real(runs, charts_html))
        return seen[-1]

    dlg._pdf_html = _keep
    try:
        dlg._export_pdf()
    finally:
        del dlg._pdf_html
    assert out.exists() and seen, "no PDF was written"
    return _flat(seen[-1])


def _on_a_saved_report(dlg):
    assert str(dlg._loaded_doc_id or "").startswith("id:"), (
        f"the window is not on a saved report: {dlg._loaded_doc_id!r}")


COVERS = re.compile(r"covers (\d+) of the (\d+) measurements")


# --------------------------------------------------------------------------
# 1. "1 of 1" stays silent after another run is measured
# --------------------------------------------------------------------------
def test_a_complete_report_stays_silent_when_a_run_is_measured_later(
        tmp_path, qapp, monkeypatch):
    """Saved with the project's only measurement: no sentence. Another run
    is measured afterwards; the saved report, opened again, still has no
    sentence, on the page and in the PDF.

    MUTATION: make `_scope_count_for` ignore the stored block (always
    `scope_counts(...)`), and the reopened report says "covers 1 of the 2",
    red."""
    s, fm, (run1,) = _project(tmp_path, runs=1)
    path = _generate(s, run1.measurement_ti3, qapp)
    sc = _block(path)["scope_count"]
    assert sc["variant"] == "none" and (sc["n"], sc["total"]) == (1, 1), sc
    _measured(fm.project().new_run(), shift=5.0)
    dlg = _window(s, run1.measurement_ti3, qapp)
    try:
        _on_a_saved_report(dlg)
        # The disk really did change: counted now, it would say so.
        from workflow.measurement_report import scope_counts
        live = scope_counts(dlg._runs_for_document(), dlg._history)
        assert (live["variant"], live["total"]) == ("covers", 2), live
        assert not COVERS.search(_page(dlg)), _page(dlg)
        assert not COVERS.search(_pdf(dlg, tmp_path, monkeypatch))
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 2. "1 of the 2" survives a run delete; Update renews it
# --------------------------------------------------------------------------
def test_a_run_delete_leaves_the_numbers_and_update_renews_them(
        tmp_path, qapp, monkeypatch):
    """Saved "covers 1 of the 2"; the other run is deleted through the real
    run-delete path. On the page, in the PDF and when the entry is chosen
    again from "Report shown" it still says "1 of the 2". Update counts the
    disk again, and the sentence goes.

    MUTATION: drop `scope_count=scope_count` from the one-measurement
    `stamp_document` in `_write_the_document`, and the reopened report is
    counted live ("no sentence"), red; drop the count at write time
    (store the page's saved decision instead) and Update keeps "1 of the 2",
    red."""
    import core.run_delete as rd
    from tests.test_run_delete import _Target
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, fm, (run1, _run2) = _project(tmp_path, runs=2)
    path = _generate(s, run1.measurement_ti3, qapp)
    assert _block(path)["scope_count"]["variant"] == "covers"
    proj = fm.project()
    rd.delete_run(proj, rd.plan_for(proj, _Target("run2")))
    assert not (Path(str(proj.root)) / "runs" / "run2").exists()
    dlg = _window(s, run1.measurement_ti3, qapp)
    try:
        _on_a_saved_report(dlg)
        m = COVERS.search(_page(dlg))
        assert m and m.groups() == ("1", "2"), _page(dlg)
        m = COVERS.search(_pdf(dlg, tmp_path, monkeypatch))
        assert m and m.groups() == ("1", "2")
        # …and through "Report shown": away to "New report…" and back.
        combo = dlg._saved_combo
        saved_key = dlg._loaded_doc_id
        combo.setCurrentIndex(combo.findData(NEW_REPORT_KEY))
        qapp.processEvents()
        assert dlg._loaded_doc_id == NEW_REPORT_KEY
        combo.setCurrentIndex(combo.findData(saved_key))
        qapp.processEvents()
        _on_a_saved_report(dlg)
        m = COVERS.search(_page(dlg))
        assert m and m.groups() == ("1", "2"), _page(dlg)
        # UPDATE RENEWS THE NUMBERS, with nothing else changed (K4: a
        # selected report is asked about whatever moved), so the page is
        # still showing the saved "1 of the 2" when the press counts again.
        dlg._ask_update_or_create_new = lambda: "update"
        assert dlg._document_settings() is not None
        dlg._on_generate_report()
        qapp.processEvents()
        assert path.exists(), "the Update did not rewrite the report in place"
        sc = _block(path)["scope_count"]
        assert sc["variant"] == "none" and (sc["n"], sc["total"]) == (1, 1), sc
        assert _block(path).get("updated"), "this was not an Update"
        _on_a_saved_report(dlg)
        assert not COVERS.search(_page(dlg)), _page(dlg)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 3. the automatic report carries the block
# --------------------------------------------------------------------------
def test_the_automatic_report_after_measuring_carries_the_count(tmp_path,
                                                               qapp):
    """The report written after a profiling measurement and after a
    verification each store the decision.

    MUTATION: drop `scope_count=scope_count` from
    `TabMeasure._stamp_the_automatic_document`, red."""
    from tests.test_the_measurement_report_defaults_are_knuts import (
        _measure_tab)
    s, _fm, (run1, _run2) = _project(tmp_path, runs=2)
    v1 = run1.new_verification()
    v1.ensure_dir()
    from tests.test_import_measurement_module import _cgats, _PATCHES
    v1.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(run1.measurement_ti3)
        tab._maybe_save_measurement_report(v1.measurement_ti3)
    finally:
        tab.deleteLater()
    (prof,) = list((run1.dir / "reports").glob("report_*.json"))
    (ver,) = list((v1.dir / "reports").glob("report_*.json"))
    assert _block(prof)["scope_count"] == {
        "variant": "covers", "n": 1, "total": 2, "kind": "profiling",
        "projects": 1, "runs": 0}
    sc = _block(ver)["scope_count"]
    assert (sc["variant"], sc["kind"], sc["n"], sc["total"]) == (
        "none", "verification", 1, 1), sc


# --------------------------------------------------------------------------
# 4. saved in English, shown in German
# --------------------------------------------------------------------------
def test_saved_in_english_shown_in_german_with_the_saved_numbers(
        tmp_path, qapp):
    """The block holds ids and whole numbers only, and the sentence is
    translated when it is shown: German words, the saved numbers.

    MUTATION: as in test 1 (ignore the stored block), and the German page
    says "1 der 3", red."""
    from core import i18n
    s, fm, (run1, _run2) = _project(tmp_path, runs=2)
    path = _generate(s, run1.measurement_ti3, qapp)
    sc = _block(path)["scope_count"]
    assert set(sc) == {"variant", "n", "total", "kind", "projects", "runs"}
    for k in ("n", "total", "projects", "runs"):
        assert type(sc[k]) is int, (k, sc[k])
    assert sc["variant"] in ("none", "covers", "unknown")
    assert sc["kind"] in ("profiling", "verification", "")
    assert "report" not in json.dumps(sc).lower(), "text was stored"
    _measured(fm.project().new_run(), shift=6.0)
    before = i18n.current_language()
    i18n.set_language("de")
    try:
        dlg = _window(s, run1.measurement_ti3, qapp)
        try:
            _on_a_saved_report(dlg)
            text = _page(dlg)
            assert ("Dieser Bericht umfasst 1 der 2 Messungen, die für die "
                    "Profilläufe dieses Projekts aufgezeichnet sind.") in text, \
                text[:1500]
        finally:
            dlg.close()
    finally:
        i18n.set_language(before or "en")


# --------------------------------------------------------------------------
# 5. "unknown" stays as saved after the folder becomes readable
# --------------------------------------------------------------------------
def test_the_unknown_variant_stays_as_saved(tmp_path, qapp, monkeypatch):
    """Saved while the project's folder could not be counted ("does not cover
    every measurement"); the folder answers again later, and the saved report
    still says what it said, without numbers.

    The unreadable folder is simulated by making the disk count answer 0 for
    the length of the press, which is exactly what
    `measurements_recorded_in` returns for a folder it cannot read.

    MUTATION: as in test 1, and the reopened report says "covers 1 of the
    2", red."""
    import workflow.measurement_report as MR
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from tests.test_import_measurement_module import _verify_env
    s, _fm, _ctl, run = _verify_env(tmp_path)
    dates = []
    for i in range(2):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES),
                                     encoding="utf-8")
        dates.append(v)
    dlg = _window(s, dates[0].measurement_ti3, qapp)
    try:
        rows = [i for i, (k, _s, _key) in enumerate(dlg._list_rows)
                if k == "run"]
        assert len(rows) == 2
        from PyQt6.QtCore import Qt
        for i in rows:
            it = dlg._profile_list.item(i)
            want = (Qt.CheckState.Checked
                    if dlg._list_rows[i][2] == dlg._run_key(dlg._report)
                    else Qt.CheckState.Unchecked)
            it.setCheckState(want)
        qapp.processEvents()
        assert len(dlg._runs_for_document()) == 1
        with monkeypatch.context() as mp:
            mp.setattr(MR, "measurements_recorded_in", lambda *a, **k: 0)
            dlg._on_generate_report()
            qapp.processEvents()
    finally:
        dlg.close()
    files = [p for v in dates for p in (v.dir / "reports").glob("*.json")]
    assert len(files) == 1, files
    sc = _block(files[0])["scope_count"]
    assert sc["variant"] == "unknown", sc
    dlg = _window(s, dates[0].measurement_ti3, qapp)
    try:
        _on_a_saved_report(dlg)
        from workflow.measurement_report import scope_counts
        live = scope_counts(dlg._runs_for_document(), dlg._history)
        assert live["variant"] == "covers", live   # the folder answers now
        text = _page(dlg)
        assert "does not cover every measurement recorded" in text, text[:1500]
        assert not COVERS.search(text), text[:1500]
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 6. guard: a report without the block counts live and is not written
# --------------------------------------------------------------------------
def test_a_report_without_the_count_is_counted_live_and_left_alone(
        tmp_path, qapp, monkeypatch):
    """A report saved by an earlier version has no `scope_count`: it is
    counted now, as it always was, and opening it (page and PDF) changes no
    byte of it.

    MUTATION: treat a missing block as "no sentence" in `_scope_count_for`
    (return the saved-or-none answer), red; write the block back on open,
    red on the bytes."""
    s, fm, (run1,) = _project(tmp_path, runs=1)
    path = _generate(s, run1.measurement_ti3, qapp)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["document"].pop("scope_count")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    before = path.read_bytes()
    _measured(fm.project().new_run(), shift=5.0)
    dlg = _window(s, run1.measurement_ti3, qapp)
    try:
        _on_a_saved_report(dlg)
        m = COVERS.search(_page(dlg))
        assert m and m.groups() == ("1", "2"), _page(dlg)
        m = COVERS.search(_pdf(dlg, tmp_path, monkeypatch))
        assert m and m.groups() == ("1", "2")
    finally:
        dlg.close()
    assert path.read_bytes() == before, "opening an older report wrote to it"


def test_a_malformed_count_is_not_trusted():
    """A block of any other shape is dropped on reading (R27-F2) and the
    report is counted live."""
    from workflow.measurement_report import (recorded_document,
                                             scope_count_of)
    good = {"variant": "covers", "n": 1, "total": 2, "kind": "profiling",
            "projects": 1, "runs": 0}
    assert scope_count_of(good) == good
    for bad in ("covers", [1], {"variant": "covers", "n": "1"},
                {**good, "variant": "all"}, {**good, "total": True},
                {**good, "kind": "calibrated"}, {**good, "n": -1}):
        assert scope_count_of(bad) is None, bad
        doc = recorded_document({"document": {"id": "x",
                                              "scope_count": bad}})
        assert "scope_count" not in doc


# --------------------------------------------------------------------------
# 2b. a report of several dates (the document file) carries it too
# --------------------------------------------------------------------------
def test_a_report_of_several_dates_stores_the_count_in_its_document_file(
        tmp_path, qapp):
    """Two of three dated verifications ticked: the document file says
    "covers 2 of the 3", and keeps saying it when a fourth date is measured.

    MUTATION: drop `scope_count=scope_count` from the `document_file` call in
    `_write_the_document`, red."""
    from PyQt6.QtCore import Qt
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from tests.test_import_measurement_module import _verify_env
    s, _fm, _ctl, run = _verify_env(tmp_path)

    def _date():
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES),
                                     encoding="utf-8")
        return v

    dates = [_date() for _ in range(3)]
    dlg = _window(s, dates[0].measurement_ti3, qapp)
    try:
        rows = [i for i, (k, _s, _key) in enumerate(dlg._list_rows)
                if k == "run"]
        assert len(rows) == 3
        dlg._profile_list.item(rows[-1]).setCheckState(
            Qt.CheckState.Unchecked)
        qapp.processEvents()
        assert len(dlg._runs_for_document()) == 2
        dlg._on_generate_report()
        qapp.processEvents()
    finally:
        dlg.close()
    docs = [p for p in run.dir.rglob("report_*.json")
            if _block(p).get("role") == "document"]
    assert len(docs) == 1, list(run.dir.rglob("report_*.json"))
    sc = _block(docs[0])["scope_count"]
    assert (sc["variant"], sc["n"], sc["total"], sc["kind"]) == (
        "covers", 2, 3, "verification"), sc
    _date()
    dlg = _window(s, dates[0].measurement_ti3, qapp)
    try:
        _on_a_saved_report(dlg)
        m = COVERS.search(_page(dlg))
        assert m and m.groups() == ("2", "3"), _page(dlg)[:1500]
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# a duplicate's copies keep the count (the default, a question for Knut)
# --------------------------------------------------------------------------
def test_a_duplicated_run_s_reports_keep_the_count_they_were_saved_with(
        tmp_path, qapp):
    """A duplicate is not an Update: the original's report and the copy in
    the new run both keep the stored count, and the original, opened again,
    still says what it said (no sentence) though the project now holds two
    measured runs. Whether a copy should count again for its new run is
    asked of Knut (spec §57.3).

    MUTATION: as in test 1 (ignore the stored block), red."""
    s, fm, (run1,) = _project(tmp_path, runs=1)
    path = _generate(s, run1.measurement_ti3, qapp)
    saved = _block(path)["scope_count"]
    new = fm.project().duplicate_run(run1)
    copies = list((new.dir / "reports").glob("report_*.json"))
    assert copies, "the duplicate copied no report"
    for c in copies:
        assert _block(c)["scope_count"] == saved
    assert _block(path)["scope_count"] == saved
    dlg = _window(s, run1.measurement_ti3, qapp)
    try:
        _on_a_saved_report(dlg)
        assert not COVERS.search(_page(dlg)), _page(dlg)[:1500]
    finally:
        dlg.close()
