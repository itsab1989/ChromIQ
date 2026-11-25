"""4.3.52 (the owner, 2026-11-20, about the yellow line under "Patch-by-patch mode (-p)" for an
i1iO table chart: "can it automatically go away after a measurement has been completed this
way?"): ticked, no line (the tooltip explains the box); not ticked, one short line that reading
in rows has not been tried on a real table yet; it goes away by itself once a measurement in rows
has been completed on that table (remembered by the table's salted key, as the reach record)."""
from __future__ import annotations

from core.i18n import tr
from tests.i1io_table.test_window_in_the_measure_tab import table_run
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.test_window_in_the_measure_tab import beta, tab  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W

LINE = ("Reading in rows has been tried on one real table so far. Please keep the table's "
        "power switch in reach.")


def _notes(tab):
    return [tab._pbp_table_note, tab._m_pbp_table_note]


def test_ticked_no_line_unticked_the_line_live_in_both_modules(tab, beta, tmp_path, qapp):
    tab._settings.set(W.ROWS_DONE_KEY, "")
    tab._settings.set(W.LAST_TABLE_KEY, "")
    run, _sheet = table_run(tmp_path)
    tab.set_ti1_path(run.artefact(".ti1"))
    assert tab._m_pbp_cb.isChecked(), "manual"
    assert tab._pbp_cb.isChecked(), "guided"
    assert all(n.isHidden() for n in _notes(tab)), [n.isHidden() for n in _notes(tab)]
    tab._m_pbp_cb.setChecked(False)
    qapp.processEvents()
    assert not tab._m_pbp_table_note.isHidden() and not tab._pbp_table_note.isHidden()
    assert tab._m_pbp_table_note.text() == tr(LINE)
    tab._m_pbp_cb.setChecked(True)
    qapp.processEvents()
    assert all(n.isHidden() for n in _notes(tab))
    # the tooltip keeps what the line said before: what the box means, Save as Defaults
    tip = tab._m_pbp_cb.toolTip()
    assert "Save as Defaults" in tip and "patch" in tip


def test_a_completed_rows_sitting_retires_the_line_for_that_table_only(
        qtbot, monkeypatch, tmp_path, settings, tab, beta):  # noqa: F811
    settings.set(W.ROWS_DONE_KEY, "")
    settings.set(W.LAST_TABLE_KEY, "")
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path / "w", settings, guided=False,
        args=["-v", "-c", "1", "-S", "chart"])            # no -p: rows read as strips
    p.script.update({"aimed": "Aimed", "done": "Close"})
    for _ in range(100):
        page = p.page()
        if page == "done":
            break
        assert page in ("aimed",), page
        p.answer_page(page)
    job = sim.jobs[0]
    assert job.row_kind == "strip" and job.rows_sitting_completed(), job.row_status
    p.press("Not now")            # (the strip default offer stands on this done page)
    key = job.reach.key
    assert key and W.rows_note_retired(settings, key) and W.rows_note_retired(settings)
    # the tab: unticked, this table known: no line
    run2, _s = table_run(tmp_path / "t")
    tab._settings.set(W.ROWS_DONE_KEY, settings.get(W.ROWS_DONE_KEY, ""))
    tab._settings.set(W.LAST_TABLE_KEY, key)
    tab.set_ti1_path(run2.artefact(".ti1"))
    tab._m_pbp_cb.setChecked(False)
    assert tab._m_pbp_table_note.isHidden()
    # another table: the line again
    tab._settings.set(W.LAST_TABLE_KEY, "0123456789abcdef")
    tab._pbp_table_note_follow()
    assert not tab._m_pbp_table_note.isHidden()


def test_a_sitting_with_a_stop_or_patch_by_patch_retires_nothing(qtbot, monkeypatch, tmp_path,
                                                                 settings):
    settings.set(W.ROWS_DONE_KEY, "")
    win, sim, run, p, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, guided=False)
    p.script.update({"aimed": "Aimed", "done": "Close"})
    for _ in range(100):
        if p.page() == "done":
            break
        p.answer_page(p.page())
    assert sim.jobs[0].row_kind == "spot" and not sim.jobs[0].rows_sitting_completed()
    p.press("Close")
    assert settings.get(W.ROWS_DONE_KEY, "") == ""
