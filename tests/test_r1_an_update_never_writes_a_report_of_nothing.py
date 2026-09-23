"""Re-challenge R1 of beta 39, #4: an Update never writes a report that
covers nothing.

Measured on screen (``~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-
behaviour/c/TI3``, T3): the one-date report of 2026-12-08, whose only
``.ti3`` had been removed, Updated with "Update without them": the file was
rewritten with ``measurements: []``, still scoped ``one_date`` and carrying
its old verdict, and the list and the page went on showing it.

Every test names its mutation; each was run red (REPORT.md in
``~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-fixes/``).
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_calibration_reports import _settings, _window    # noqa: E402
from tests.test_challenge_c_report_files import (                # noqa: E402
    _update_from, qapp, said)
from tests.test_g7_reports_across_places import (               # noqa: E402
    _date, _press, _project, _snapshot)

assert qapp and said


def _one_date_report_of(tmp_path, qapp):
    """P with two dated verifications; a one-date report of the SECOND one
    written by the window. Returns (first, second)."""
    _p, run, first = _project(tmp_path, "P")
    second = _date(run, scale=0.98)
    dlg = _window(_settings(), second.measurement_ti3, qapp, "verification")
    try:
        dlg._ask_update_or_create_new = lambda: "new"
        dlg._saved_combo.setCurrentIndex(0)             # "New report…"
        qapp.processEvents()
        _tick_only_the_windows_own(dlg, qapp)
        _press(dlg, qapp)
    finally:
        dlg.close()
    return first, second


def _tick_only_the_windows_own(dlg, qapp):
    from PyQt6.QtCore import Qt
    here = dlg._run_key(dlg._report)
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind == "run" and key is not None:
            dlg._profile_list.item(i).setCheckState(
                Qt.CheckState.Checked if key == here
                else Qt.CheckState.Unchecked)
    qapp.processEvents()
    assert [dlg._run_key(r) for r in dlg._runs_for_report()] == [here]


def _documents(tmp_path):
    out = []
    for f in tmp_path.rglob("report_*.json"):
        if "old" in f.parts:
            continue
        d = json.loads(f.read_text(encoding="utf-8")).get("document")
        if d:
            out.append((f, d))
    return out


def test_an_update_whose_every_measurement_is_gone_is_refused(tmp_path, qapp,
                                                              said):
    """The tester's T3: the only measurement of the loaded report deleted.
    The press writes and archives nothing, and says so
    (M-REPORT-UPDATE-NOTHING-LEFT) instead of offering "Update without them".

    MUTATION, proven red: drop the nothing-left test in
    `MeasurementReportDialog._update_leaves_out` (the question is asked, and
    "Update without them" writes ``measurements: []``)."""
    from workflow import measurement_messages as M
    first, second = _one_date_report_of(tmp_path, qapp)
    docs = _documents(tmp_path)
    assert any(len(d["measurements"]) == 1
               and second.dir.name in d["measurements"][0]["dir"]
               for _f, d in docs), docs
    second.measurement_ti3.unlink()
    before = _snapshot(tmp_path)
    dlg = _update_from(first.measurement_ti3, qapp, leave_out_answer=True)
    assert dlg._loaded_doc_id
    assert not dlg.__dict__.get("_asked"), "it offered Update without them"
    assert _snapshot(tmp_path) == before, "the refused Update wrote something"
    title = M.CATALOGUE["M-REPORT-UPDATE-NOTHING-LEFT"].render(missing="")[0]
    hits = [x for _k, t, x in said if t == title]
    assert hits, said
    assert "its measurement file is no longer in its folder" in hits[0]
    assert not any(d.get("measurements") == [] for _f, d in _documents(
        tmp_path)), "a report of nothing is on disk"


def test_the_writer_refuses_an_update_of_nothing_by_any_door(tmp_path, qapp,
                                                             said):
    """The same rule where the file is written: `_write_the_document` asked
    to update a document with no measurement left writes nothing.

    MUTATION, proven red: drop the ``updating is not None and not members``
    refusal in `_write_the_document`."""
    first, second = _one_date_report_of(tmp_path, qapp)
    dlg = _window(_settings(), second.measurement_ti3, qapp, "verification")
    try:
        assert dlg._loaded_doc_id
        updating = dlg._document_being_updated()
        assert updating is not None
        keys = {dlg._run_key(r) for r in dlg._runs_for_document()}
        before = _snapshot(tmp_path)
        dlg._write_the_document(None, dlg._reports_to_generate(), updating,
                                leave_out=keys)
    finally:
        dlg.close()
    assert _snapshot(tmp_path) == before


def test_a_document_of_nothing_says_so_in_its_name(tmp_path, qapp):
    """A report of nothing written by the build before this one is named for
    what it is, never as the report it had been.

    MUTATION, proven red: drop the "covers no measurement" bit in
    `_document_label`."""
    first, second = _one_date_report_of(tmp_path, qapp)
    (f, d), = [(f, d) for f, d in _documents(tmp_path)
               if second.dir.name in json.dumps(d["measurements"])]
    data = json.loads(f.read_text(encoding="utf-8"))
    data["document"]["measurements"] = []
    f.write_text(json.dumps(data), encoding="utf-8")
    dlg = _window(_settings(), first.measurement_ti3, qapp, "verification")
    try:
        names = [dlg._saved_combo.itemText(i)
                 for i in range(dlg._saved_combo.count())]
    finally:
        dlg.close()
    assert any("covers no measurement" in n for n in names), names
