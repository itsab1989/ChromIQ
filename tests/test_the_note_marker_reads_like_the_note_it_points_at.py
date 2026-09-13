"""The raised marker and the note list use ONE notation, and it is Knut's.

Knut, 2026-09-13::

    The notes should also be numbered in the report, and the verdict line in a
    table which applies to a note should snow a number as a reference to the
    note that applies to it, f.ex. a note as a raised number, ex. "1)" "2)" or
    "a)" "b)"

The first build printed a bare superscript `1` beside the verdict and a bold
`1.` at the head of the list item. Two notations for one cross-reference, and
neither the one he named: a reader has to work out that the floating digit and
the numbered item are the same thing.

`measurement_report.note_label` is the single formatter. This file pins that
both renderers ask it, so a change of notation cannot reach one and miss the
other — which is the fault shape this project keeps finding, a guard on one
door and not the identical door beside it.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_report import note_label            # noqa: E402


def test_a_note_is_written_the_way_he_asked_for_it():
    assert note_label(1) == "1)"
    assert note_label(2) == "2)"
    assert note_label(11) == "11)"


def _dialog_with_a_noted_verdict(tmp_path, qapp):
    """A run whose grey rows carry the `printing_unrecorded` note: a sheet with
    no print record, which is the one case that produces a note today."""
    from tests.test_import_measurement_module import _verify_env
    from tests.test_a_saved_report_does_not_leak_its_verdict_into_another_type \
        import _grey_ramp_ti3
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import ensure_bound
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_grey_ramp_ti3(), encoding="utf-8")
    lim = ensure_bound(run, None, "chromiq_default")
    rep = build_report(str(v.measurement_ti3))
    stamp_verdict(rep, lim.limits, set_id=lim.set_id, set_label=lim.set_label)
    save_report(rep, v.dir)
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def test_the_marker_and_the_list_item_carry_the_same_string(tmp_path, qapp):
    """MUTATION: put the marker back to a bare digit and this goes red."""
    dlg = _dialog_with_a_noted_verdict(tmp_path, qapp)
    try:
        reps = dlg._runs_for_report()
        numbered = dlg._numbered_notes(reps)
        if not numbered:
            import pytest
            pytest.skip("this fixture produced no note, so there is no marker")
        body = dlg._report_body_html(reps, for_pdf=True)
        # SPELLED OUT, NOT ASKED OF `note_label`. Written as
        # `f"...{note_label(n)}..."` this test passed under a mutation that put
        # the notation back to a bare digit, because it put the same question
        # to the same function the renderer does and both moved together. A
        # test that re-derives the value it is checking checks nothing; the
        # notation Knut named is a literal here, and `note_label` is pinned to
        # the same literals in the test above.
        for (n, _where, _sentence) in numbered:
            want = f"{n})"
            assert f"<sup style='font-weight:normal'>&nbsp;{want}</sup>" in body, (
                f"no verdict carries the marker {want!r}; the note list names "
                f"a number nothing on the page points at")
            assert f"<b>{want}</b>" in body, (
                f"the note list does not head its item with {want!r}")
            # …and the renderers must agree with the formatter, which is the
            # other half: one notation, from one place.
            assert note_label(n) == want
        assert "<b>1.</b>" not in body, (
            "the old '1.' item label is still printed beside the new marker")
    finally:
        dlg.close()
