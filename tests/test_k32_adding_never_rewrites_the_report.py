"""K32, Knut on beta 41 (#182 5815133233): adding measurements never rewrites
the report on screen.

*"When adding new measurement sets, they should by default not be checked,
and even if they were checked, the currently selected report should get a
warning that the settings for the report has been modified (the normal
warning when changes are made), and the report never automatically updated
without first clicking generate report."*

Driven on screen on Report-Limits-Profile-Gamut (run 1, Verification, run 2's
measurements added): `scripts/drive_k32_report_rows_and_switch.py`, scene
"add".
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _ticks(dlg):
    from PyQt6.QtCore import Qt
    out = {}
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind == "run" and key:
            out[key] = (dlg._profile_list.item(i).checkState()
                        == Qt.CheckState.Checked)
    return out


def test_added_measurements_come_in_unticked_and_the_page_stays(
        tmp_path, qapp, monkeypatch):
    """A window on a saved report; another project's measurements added.

    MUTATION, proved to land: the old path for every add
    (`if added and had_sources:` -> `if False:`): the new rows come in
    ticked, the page is drawn again with them, and no red line says so."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path / "a", dates=2)
    _s2, _fm2, _run2, vs2 = _messy_project(tmp_path / "b", dates=2)
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        page = dlg._view.toPlainText()
        before = _ticks(dlg)
        assert before and not dlg._stale_label.isVisible()
        monkeypatch.setattr(mrd, "open_files_dialog",
                            lambda *a, **k: [str(vs2[-1].measurement_ti3)])
        dlg._on_add_project()
        qapp.processEvents()
        after = _ticks(dlg)
        new = set(after) - set(before)
        assert new, "nothing was added"
        assert not any(after[k] for k in new), (
            "an added measurement came in ticked")
        assert {k: after[k] for k in before} == before, (
            "adding moved a tick the user had set")
        assert dlg._view.toPlainText() == page, (
            "the report text changed without Generate")
        assert not dlg._stale_label.isVisible(), (
            "nothing the report covers has changed, so no red line")
        # ticking one is a change like any other: red line, same page
        from PyQt6.QtCore import Qt
        k = sorted(new)[0]
        i = next(i for i, (kind, _si, key) in enumerate(dlg._list_rows)
                 if key == k)
        dlg._profile_list.item(i).setCheckState(Qt.CheckState.Checked)
        qapp.processEvents()
        assert dlg._stale_label.isVisible(), "no warning for a ticked set"
        assert dlg._view.toPlainText() == page, (
            "ticking an added set rewrote the report without Generate")
    finally:
        dlg.close()
