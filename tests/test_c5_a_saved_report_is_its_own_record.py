"""A saved report is its own record, its PDF is the page, and Generate reads
the disk again (challenge 5 of beta 42; register B8-1091 to B8-1095; spec
§6, §28.10, §33.6, §34.1).

M1 (B8-1091). A report saved before a rule that changes how its rows are
worked out (K34's paper patch, K37's paper white from the profile, K37 (i)'s
strip corners) is rebuilt when it is read, and its saved verdict is kept. The
page took every explanation from the rebuild, so the kept FAIL of a
Border-Conditions sheet (absolute Lab) stood under a note saying it was judged
relative to the profile's paper white. Beside a kept verdict the page now
shows what the saved report recorded, and says once that an earlier version
worked it out.

M2 (B8-1092). With one setting touched, "Save report as PDF" judged every row
again: `_doc_settings_moved` silenced the loaded document, so the PDF said
PASS where the page said FAIL. The PDF now prints the rows the page was drawn
from.

M4 (B8-1094). Generate wrote the report from the rows the window had read,
so a print record written since, or a profile renamed away since, did not
reach a new report. Generate now works each measurement out again from disk.

Minor (B8-1095). An empty trend graph gives the reason that is true.
"""
from __future__ import annotations

import json
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


_WORDS = re.compile(r"\b(PASS|FAIL|COND|INFO|N-A)\b")


def _results_words(text: str) -> list:
    """The verdict words of Report Results, in order."""
    a = text.find("Report Results")
    b = text.find("Notes on the verdicts above", a)
    if a < 0:
        return []
    return _WORDS.findall(text[a:b if b > a else None])


def _flip_saved_words(folder):
    """Every PASS a saved report of *folder* recorded becomes FAIL, so the
    saved words differ from any judgement worked out now."""
    n = 0
    for p in (folder / "reports").glob("report_*.json"):
        rep = json.loads(p.read_text(encoding="utf-8"))
        v = rep.get("verdict")
        if not isinstance(v, dict) or "compliance" not in rep:
            p.unlink()          # one saved report of this date, not two
            continue
        for row in v.get("rows") or []:
            if row.get("word") == "PASS":
                row["word"], row["pass"] = "FAIL", False
                n += 1
        v["overall"] = "FAIL"
        p.write_text(json.dumps(rep), encoding="utf-8")
    return n


def _window(tmp_path, qapp, *, flip=True):
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_import_measurement_module import _cgats, _PATCHES
    s, _fm, run, vs = _messy_project(tmp_path / "p", dates=2)
    run.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    if flip:
        assert _flip_saved_words(vs[-1].dir), "nothing to flip"
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    assert dlg._loaded_doc_id != mrd.NEW_REPORT_KEY
    return dlg, run, vs


def _pdf_text(dlg, qapp, tmp_path, name) -> str:
    """Save report as PDF… through the real door, and read the file back."""
    import ui.widgets as _w
    from PyQt6.QtGui import QDesktopServices
    from pypdf import PdfReader
    out = tmp_path / f"{name}.pdf"
    real_save, real_open = _w.save_file_dialog, QDesktopServices.openUrl
    _w.save_file_dialog = lambda *a, **k: str(out)
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    try:
        dlg._export_pdf()
        qapp.processEvents()
    finally:
        _w.save_file_dialog = real_save
        QDesktopServices.openUrl = real_open
    assert out.is_file(), "no PDF was written"
    text = "\n".join(pg.extract_text() or ""
                     for pg in PdfReader(str(out)).pages)
    # pypdf separates the words of a line by tabs
    return re.sub(r"[ \t\xa0]+", " ", text)


def _touch(dlg, qapp, monkeypatch, run):
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())


def _untick(dlg, qapp, monkeypatch, run):
    from PyQt6.QtCore import Qt
    i = next(i for i, (kind, _si, _k) in enumerate(dlg._list_rows)
             if kind == "run")
    dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)


def _add(dlg, qapp, monkeypatch, run):
    import ui.dialogs.measurement_report_dialog as mrd
    monkeypatch.setattr(mrd, "open_files_dialog",
                        lambda *a, **k: [str(run.measurement_ti3)])
    dlg._on_add_project()


def _remove(dlg, qapp, monkeypatch, run):
    _add(dlg, qapp, monkeypatch, run)
    qapp.processEvents()
    row = next(i for i, (kind, si, _k) in enumerate(dlg._list_rows)
               if kind == "source" and si == 0)
    dlg._profile_list.setCurrentRow(row)
    dlg._on_remove_profile()


def _clear(dlg, qapp, monkeypatch, run):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k:
                                     QMessageBox.StandardButton.Yes))
    dlg._on_clear_list()


@pytest.mark.parametrize("step", [_touch, _untick, _add, _remove, _clear],
                         ids=["touch a setting", "untick", "add",
                              "remove", "clear list"])
def test_the_pdf_says_what_the_page_says(tmp_path, qapp, monkeypatch, step):
    """M2 (B8-1092): after each of the five steps the page is kept, and the
    PDF's verdict words are the page's, read out of the written PDF.

    MUTATION, proved to land: `_runs_for_report` ignores `_runs_forced` AND
    `_as_the_document_was_built` does not restore `_doc_settings_moved`
    (red on "touch a setting" and "clear list": the PDF re-judges and prints
    PASS under a page of FAIL). The rows alone (`_runs_forced`) turn "clear
    list" red; the second lock is
    `test_the_pdf_prints_the_rows_the_page_was_drawn_from`."""
    dlg, run, _vs = _window(tmp_path, qapp)
    try:
        page = dlg._view.toPlainText()
        words = _results_words(page)
        assert "FAIL" in words and "PASS" not in words, (
            "the page does not show the saved words", words)
        step(dlg, qapp, monkeypatch, run)
        qapp.processEvents()
        assert dlg._view.toPlainText() == page, "the page was redrawn"
        pdf = _results_words(_pdf_text(dlg, qapp, tmp_path, "after"))
        assert pdf == words, (
            "the PDF is not the page", {"page": words, "pdf": pdf})
    finally:
        dlg.close()


def test_the_pdf_prints_the_rows_the_page_was_drawn_from(tmp_path, qapp):
    """The rows themselves are the lock: inside the export the window hands
    back the page's own rows, whatever state the controls are in.

    MUTATION, proved to land: drop the `_runs_forced` return from
    `_runs_for_report` (red: the rows are judged again)."""
    dlg, _run, _vs = _window(tmp_path, qapp)
    try:
        drawn = list(dlg._runs_as_drawn)
        dlg._doc_settings_moved = True          # what a touched control does
        dlg._judged_cache = {}
        with dlg._as_the_document_was_built():
            dlg._doc_settings_moved = True      # and even so
            inside = dlg._runs_for_report()
        assert [id(r) for r in inside] == [id(r) for r in drawn]
    finally:
        dlg.close()


# ---- M1 ------------------------------------------------------------------
def _pre_k37(rep: dict) -> dict:
    """*rep* as a ChromIQ before K37 saved it for a white-mapped sheet with no
    paper patch: absolute Lab, no `paper_white_used`."""
    out = dict(rep)
    out.pop("paper_white_used", None)
    out.pop("strip_corner_aims", None)
    out.pop("paper_white", None)
    out.update(paper_patch=False, yardstick="absolute",
               yardstick_no_paper=True)
    return out


def _as_k37_rebuilds_it(rep: dict) -> dict:
    """What this version's rebuild says of the same sheet: (e), relative to
    the profile's paper white, and the strip against the prediction."""
    out = dict(rep)
    out.pop("paper_white", None)
    out.update(paper_patch=False, yardstick="media-relative",
               paper_white_used={"from": "profile", "source": "run_profile",
                                 "profile": "P.icc", "lab": [95.5, 0.2, 1.4]},
               strip_corner_aims={"from": "profile", "profile": "P.icc"})
    return out


def test_the_record_is_what_was_saved(tmp_path, qapp):
    """`_the_saved_record`: the saved numbers and yardstick win, a rule block
    the saved report lacks is not borrowed, and the page is told.

    MUTATIONS, each proved to land: `rec.update(saved)` removed (the numbers
    are the rebuild's); the RULE_BLOCKS pop removed (the (e) block comes
    back beside the kept words); `_worked_out_differently` answers False."""
    import ui.dialogs.measurement_report_dialog as mrd
    from workflow.measurement_report import build_report, stamp_verdict
    from workflow.compliance_sets import factory_limits
    from tests.test_import_measurement_module import _cgats, _PATCHES
    f = tmp_path / "m.ti3"
    f.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    base = build_report(f)
    stamp_verdict(base, factory_limits("chromiq_default"),
                  set_id="chromiq_default", set_label="ChromIQ default")
    saved = _pre_k37(base)
    saved["de00"] = dict(saved["de00"], max_all=3.533)
    rebuilt = _as_k37_rebuilds_it(build_report(f))
    rebuilt["de00"] = dict(rebuilt["de00"], max_all=2.258)
    rec = mrd._the_saved_record(saved, rebuilt)
    assert rec["de00"]["max_all"] == 3.533
    assert rec["yardstick"] == "absolute"
    assert "paper_white_used" not in rec and "strip_corner_aims" not in rec
    assert rec.get(mrd.WORKED_OUT_EARLIER_KEY) is True
    # the note on the Paper white line is then the approved one, true of it
    assert mrd._paper_white_note_code(rec) == mrd.NOTE_NO_PAPER_PATCH
    # a report saved by this version is its own record, and nothing is said
    same = dict(rebuilt, verdict=base["verdict"])
    assert mrd._the_saved_record(same, rebuilt).get(
        mrd.WORKED_OUT_EARLIER_KEY) is None
    # a report with no saved verdict is judged live, as before
    assert mrd._the_saved_record({k: v for k, v in saved.items()
                                  if k != "verdict"}, rebuilt) is None


def test_an_old_saved_report_explains_its_own_words(tmp_path, qapp,
                                                   monkeypatch):
    """M1 on the window: a report saved before K37 is rebuilt when read; the
    page keeps its words AND its notes, carries M-REPORT-NO-PAPER-PATCH
    (true of it), not M-REPORT-PAPER-WHITE-FROM-PROFILE (the rebuild's), and
    says once that an earlier version worked it out.

    MUTATION, proved to land: `_as_recorded` returns the row unchanged (the
    (e) note and no line)."""
    import workflow.measurement_report as wmr
    from workflow import measurement_messages as M
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path / "p", dates=1)
    for p in (vs[-1].dir / "reports").glob("report_*.json"):
        rep = json.loads(p.read_text(encoding="utf-8"))
        if "compliance" not in rep:
            p.unlink()          # one saved report of this date, not two
            continue
        p.write_text(json.dumps(_pre_k37(rep)), encoding="utf-8")
    real = wmr.build_report
    monkeypatch.setattr(wmr, "build_report",
                        lambda *a, **k: _as_k37_rebuilds_it(real(*a, **k)))
    import ui.dialogs.measurement_report_dialog as mrd
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        page = dlg._view.toPlainText()
        no_patch = M.M_REPORT_NO_PAPER_PATCH.render()[1]
        from_profile = M.M_REPORT_PAPER_WHITE_FROM_PROFILE.render(
            profile="P.icc", L="95.5", a="0.2", b="1.4")[1]
        earlier = M.M_REPORT_WORKED_OUT_EARLIER.render()[1]
        assert " ".join(no_patch.split()) in " ".join(page.split())
        assert from_profile not in page
        assert "relative to the paper white recorded in the profile" \
            not in page
        assert page.count(M.M_REPORT_WORKED_OUT_EARLIER.render()[0]) == 1
        assert " ".join(earlier.split()) in " ".join(page.split())
        # New report…: this version's working, and no line
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        assert earlier not in dlg._view.toPlainText()
    finally:
        dlg.close()


def test_a_document_records_how_it_was_judged():
    """A report of several dates records the yardstick and the rule blocks
    beside each verdict (`judged_block`), so it can be shown as it was.

    MUTATION, proved to land: `JUDGED_EXPLANATION_KEYS` left out of
    `judged_block`."""
    from workflow.measurement_report import judged_block
    rep = {"verdict": {"rows": []}, "compliance": {}, "pass_thresholds": {},
           "yardstick": "absolute", "paper_patch": False,
           "paper_white_used": {"from": "unavailable"},
           "strip_corner_aims": {"from": "ideal"}, "de00": {"avg_all": 1}}
    j = judged_block(rep)
    for k in ("yardstick", "paper_patch", "paper_white_used",
              "strip_corner_aims"):
        assert j[k] == rep[k]
    assert "de00" not in j


# ---- M4 ------------------------------------------------------------------
def test_generate_works_the_measurement_out_again(tmp_path, qapp,
                                                  monkeypatch):
    """M4 (B8-1094): Create New writes a report worked out from disk at the
    press, not the row the window read when it opened.

    MUTATION, proved to land: `_write_the_document` stamps the window's row
    (`dict(one)`) instead of `_worked_out_again` (red: the probe is missing,
    the saved report's cached inputs were written)."""
    import workflow.measurement_report as wmr
    from tests.test_a_generated_report_is_one_document import (_dialog,
                                                               _messy_project)
    s, _fm, _run, vs = _messy_project(tmp_path / "p", dates=1)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        before = set((vs[-1].dir / "reports").glob("report_*.json"))
        real = wmr.build_report

        def _probe(*a, **k):
            out = real(*a, **k)
            out["strip_corner_aims"] = {"from": "ideal", "c5_probe": True}
            return out
        # what the disk says NOW, after the window has read its rows
        monkeypatch.setattr(wmr, "build_report", _probe)
        dlg._saved_combo.setCurrentIndex(0)             # New report…
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        new = set((vs[-1].dir / "reports").glob("report_*.json")) - before
        assert len(new) == 1, new
        rep = json.loads(next(iter(new)).read_text(encoding="utf-8"))
        assert (rep.get("strip_corner_aims") or {}).get("c5_probe"), (
            "Generate wrote the row the window had read, not the disk")
        assert rep.get("created") == json.loads(
            sorted(before)[0].read_text(encoding="utf-8")).get("created")
    finally:
        dlg.close()


# ---- the empty trend graph ------------------------------------------------
def test_an_empty_graph_gives_the_true_reason(qapp):
    """B8-1095 (and B8-1084): three dates and no judged row, three dates and
    no value, one date: three reasons.

    MUTATION, proved to land: `empty_reason` answers the generic sentence
    always (red on the first two)."""
    from ui.dialogs.measurement_report_dialog import _TrendChart
    from PyQt6.QtGui import QColor
    c = _TrendChart()
    pts = [{"created": f"2029-03-{d}"} for d in (12, 26, 29)]
    c.set_data(pts, [])
    assert "judges none of this graph's rows" in c.empty_reason()
    c.set_data(pts, [("x", QColor("red"), lambda pt: None)])
    assert "Fewer than two of the ticked measurements" in c.empty_reason()
    c.set_data(pts[:1], [("x", QColor("red"), lambda pt: 1.0)])
    assert "needs at least two measurements" in c.empty_reason()


def test_the_k37_notes_name_the_measurement_not_a_sheet():
    """Knut, #182 5824834975 (B8-1096): he could not tell what "sheet"
    meant. The four K37 notes and M-REPORT-NO-PAPER-PATCH name the
    measurement, end with what happens to the report's other measurements,
    and are approved.

    MUTATION, proved to land: any of the old bodies back (red)."""
    from workflow import measurement_messages as M
    tail = ("Only the measurements that carry this note are judged this way; "
            "the report's other measurements are judged as usual.")
    for m in (M.M_REPORT_NO_PAPER_PATCH, M.M_REPORT_PAPER_WHITE_FROM_PROFILE,
              M.M_REPORT_JUDGED_ABSOLUTE_NO_PAPER_WHITE,
              M.M_REPORT_STRIP_CORNERS_PREDICTED,
              M.M_REPORT_STRIP_CORNERS_IDEAL):
        body = m.body
        assert "sheet" not in body, m.id
        assert "measurement" in body.split(".")[0], m.id
        assert body.endswith(tail), m.id
        assert m.approved, m.id
