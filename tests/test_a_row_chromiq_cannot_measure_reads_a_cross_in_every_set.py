"""A row ChromIQ cannot measure reads ✕ in EVERY limit set (B8-979).

Knut, #182 5815435713 (2026-09-24), on Preferences > Reports > Report limits:
*"Opening help text for 'Maximum deltaE00, spot colours'. The help text says
'... and the cell shows a cross in every limit set.'. This is not true. The
three ChromIQ limit sets show '-'. There are many other rows/metrics that
ChromIQ does not evaluate, but still shows '-' and not 'x' for a limit set. I
guess they should show x on all limit sets, when ChromIQ does not evaluate
that metric at all."*

Measured on screen before the change: 42 of the 84 cells of the twelve such
rows read "–" (every row in the three ChromIQ columns, and each row a standard
does not limit in its ISO and Custom columns).

The rule is one function, `compliance_sets.mark_unmeasurable`, applied to a
set's factory column and, for display, to a report's stored copy. It moves no
verdict and no count: these rows never carry a value, so a "–" and a ✕ both
give no word.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel          # noqa: E402

from workflow import compliance_sets as cs                # noqa: E402

UNMEASURABLE = [r.id for r in cs.ROWS if r.status == "unmeasurable"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _old_rule(set_id: str) -> "dict[str, cs.Limit]":
    """The column as every build before 2026-09-24 gave it: "–" on a row
    ChromIQ cannot measure unless the set's standard limits it."""
    s = cs.SET_BY_ID[set_id]
    touched = set(cs._ISO_ROWS.get(s.parent or s.id, ()))
    out = dict(cs.factory_limits(set_id))
    for rid in UNMEASURABLE:
        if rid not in touched:
            out[rid] = cs.Limit.none()
    return out


def test_there_are_rows_to_mark():
    # the premise: twelve on the day of the ruling; none would make this vacuous
    assert len(UNMEASURABLE) >= 10, UNMEASURABLE


@pytest.mark.parametrize("set_id", [s.id for s in cs.SETS])
def test_every_set_reads_a_cross_on_every_row_chromiq_cannot_measure(set_id):
    """MUTATION: return `out` instead of `mark_unmeasurable(out)` at the end
    of `factory_limits` and this goes red for the three ChromIQ sets (and
    for the rows a standard does not limit in the other four)."""
    f = cs.factory_limits(set_id)
    # an override on such a row is ignored, as it always was, and cannot
    # turn the cross back into a number or a dash
    ov = {set_id: {rid: 1.0 for rid in UNMEASURABLE}}
    ov[set_id].update({UNMEASURABLE[0]: None})
    e = cs.effective_limits(set_id, ov)
    for rid in UNMEASURABLE:
        assert f[rid].kind == "unmeasurable", (set_id, rid, f[rid])
        assert e[rid].kind == "unmeasurable", (set_id, rid, e[rid])
        assert cs.limit_text(f[rid]) == "✕"


def test_every_other_row_is_exactly_what_it_was():
    """The mark touches the unmeasurable rows and nothing else.

    MUTATION: mark every row whose status is not "now" in
    `mark_unmeasurable` and this goes red."""
    for s in cs.SETS:
        new, old = cs.factory_limits(s.id), _old_rule(s.id)
        for r in cs.ROWS:
            if r.status != "unmeasurable":
                assert new[r.id] == old[r.id], (s.id, r.id)
                # `_old_rule` is derived from `factory_limits`, so the line
                # above cannot see a mark that spreads; this one can
                assert new[r.id].kind != "unmeasurable", (s.id, r.id)
    # and a set with a number on a row ChromIQ computes keeps it
    assert cs.factory_limits("chromiq_default")["all_de00_avg"].is_numeric


def test_the_cross_moves_no_count_and_no_limit_bearing_row():
    for s in cs.SETS:
        assert cs.limit_bearing(cs.factory_limits(s.id)) == \
            cs.limit_bearing(_old_rule(s.id)), s.id
    # the sets the report window may offer are the same seven
    assert cs.selectable_set_ids({}) == [
        s.id for s in cs.SETS if cs.limit_bearing(_old_rule(s.id))]


def test_a_copy_stored_before_the_ruling_is_not_called_edited():
    """Every report saved before 2026-09-24 stored "–" (null) on these rows in
    ChromIQ's own sets. It is the same yardstick, and "(edited)" beside it
    would be a false claim on screen and in the PDF.

    MUTATION: in `is_edited`, compare `kind` instead of `is_numeric` and
    this goes red."""
    for s in cs.SETS:
        old = _old_rule(s.id)
        assert not cs.is_edited(old, s.id, {}), s.id
        assert cs.same_limits(old, cs.factory_limits(s.id)), s.id


def _a_report():
    """A real report of a real (synthetic) .ti3, 125 patches."""
    import workflow.measurement_report as mr
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from drive_one_page_report import _GRID, _srgb_to_xyz_d50
    import tempfile
    rows, n = [], 0
    for r in _GRID:
        for g in _GRID:
            for b in _GRID:
                n += 1
                x, y, z = _srgb_to_xyz_d50(r, g, b)
                x, y, z = x * 0.97 + 0.3, y * 0.97 + 0.2, z * 0.97 + 0.15
                rows.append(f"{n} {r:.4f} {g:.4f} {b:.4f} "
                            f"{x / 100:.6f} {y / 100:.6f} {z / 100:.6f}")
    with tempfile.TemporaryDirectory(prefix="chromiq-b8979-") as d:
        p = Path(d) / "chart.ti3"
        p.write_text(
            'CTI3\n\nDESCRIPTOR "x"\nKEYWORD "DEVICE_CLASS"\n'
            'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
            "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows)
            + "\nEND_DATA\n", encoding="utf-8")
        return mr.build_report(p)


def test_the_report_judges_and_counts_exactly_as_before():
    """The Measurement Report's rows, words and overall verdict (with its
    "n of N" counts) are the same under the new column as under the old one,
    in every set.

    MUTATION: make `row_verdict` return INFO for an ``unmeasurable`` limit and
    this goes red (a word would appear on twelve rows nobody can judge)."""
    import workflow.measurement_report as mr
    rep = _a_report()
    assert mr.judge(rep, cs.factory_limits("chromiq_default")), \
        "the premise failed: the report judges nothing"
    for s in cs.SETS:
        new, old = cs.factory_limits(s.id), _old_rule(s.id)
        rows_new, rows_old = mr.judge(rep, new), mr.judge(rep, old)
        assert rows_new == rows_old, s.id
        assert not {r["row_id"] for r in rows_new} & set(UNMEASURABLE), s.id
        assert mr.summarise(rep, new, rows_new, s.id) == \
            mr.summarise(rep, old, rows_old, s.id), s.id


def test_the_help_text_of_such_a_row_is_now_true(qapp, tmp_path):
    """The sentence Knut found false, read off the window, beside the cells
    it describes: every column the window has reads ✕ on that row."""
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(st, None)
    try:
        cols = sorted({c for (c, _r) in dlg._cells})
        assert len(cols) == len(cs.SETS), cols
        for rid in UNMEASURABLE:
            help_text = dlg._row_help(cs.ROW_BY_ID[rid])
            assert "cross in every limit set" in help_text, rid
            for c in cols:
                w = dlg._cells[(c, rid)]
                assert isinstance(w, QLabel) and w.text() == "✕", (c, rid)
    finally:
        dlg.deleteLater()


def test_a_reports_own_column_reads_the_cross_too(qapp, tmp_path):
    """"This report" shows a copy stored with the report. One stored before
    the ruling carries null on these rows; it is shown as ✕ beside the sets,
    and the copy on disk is not rewritten by looking at it.

    MUTATION: return `self._run_limits` unmarked from `_limits_of` and this
    goes red."""
    from core.file_manager import Project
    from core.settings import AppSettings
    from tests.helpers import legacy_run_meta
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    legacy_run_meta.bind_run(run, "chromiq_default", {})
    meta = run.load_meta()
    for rid in UNMEASURABLE:
        meta.compliance_thresholds[rid] = None      # as stored before
    run.save_meta(meta)
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(st, None, run=run, run_editable=True)
    try:
        for rid in UNMEASURABLE:
            w = dlg._cells[("__run__", rid)]
            assert isinstance(w, QLabel) and w.text() == "✕", rid
        dlg.accept()
        assert not dlg.run_limits_changed, "looking at the column wrote it"
        stored = run.load_meta().compliance_thresholds
        assert all(stored[rid] is None for rid in UNMEASURABLE)
    finally:
        dlg.deleteLater()
