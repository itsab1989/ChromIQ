"""B8-250 / B8-251 — the Measurement Report's "Saved reports" row.

The project's design authority, 2026-09-16, asking for this before a non-beta
release of the report feature::

    I suggest that we release a non-beta with the measurement report, even
    though the 'reference file' feature is not yet implemented, as the reports
    feature is still very good. Though, the selection and deletion of reports
    with a selector input box is needed and should be made first

A run may hold several reports of one measurement on purpose (Knut,
2026-09-11), and until now the line above the table counted them and nothing
could open one: `_one_row_per_measurement` keeps the newest and the rest were
unreachable. The row adds a selector that shows any of them and a Delete that
removes exactly one, saying what goes first (M-REPORT-DELETE, §M-PROPOSED).

**THE ONE REFUSAL.** The only saved report of a DATED VERIFICATION is kept.
§5 of `docs/design/measurement_report_limits.md` exists so that every dated
verification of a run is judged the same way and the dates stay comparable,
and that comparability IS the recorded verdict; a date whose last report is
gone has none, and the window would grade it live against today's numbers,
which is the thing the lock is there to prevent.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


def _env(tmp_path, dates=2, per_date=2):
    """A run with *dates* dated verifications, each carrying *per_date* saved
    reports of its measurement."""
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import bind_run, run_limits
    s, fm, _ctl, run = _verify_env(tmp_path)
    bind_run(run, "chromiq_default", None)
    lim = run_limits(run, None)
    vs = []
    for _d in range(dates):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
        for _n in range(per_date):
            rep = build_report(v.measurement_ti3)
            stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                          set_label=lim.label_en, edited=lim.edited)
            save_report(rep, v.dir)
        vs.append(v)
    return s, fm, run, vs


def _dialog(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def _reports(v):
    return sorted(p.name for p in (v.dir / "reports").glob("report_*.json"))


# --------------------------------------------------------------------------
# B8-380/B8-383: the pulldown is a LIST BOX and every entry is a DOCUMENT.
#
# The fixture here saves reports through `save_report` directly, exactly as an
# earlier ChromIQ did and as every report already on a user's disk was written,
# so none of them carries a document block and each is its own one-file
# document. That is deliberate: these tests are the record that such a file is
# still listed, still named as it was and still opens.
# --------------------------------------------------------------------------
def _count(dlg) -> int:
    return dlg._saved_combo.count()


def _key(dlg, i: int) -> str:
    return str(dlg._saved_combo.itemData(i) or "")


def _text(dlg, i: int) -> str:
    return dlg._saved_combo.itemText(i)


def _file_of(key: str) -> str:
    """The report file a one-file document's key names."""
    return Path(key.split("file:", 1)[1]).name if key.startswith("file:") else ""


def _current_file(dlg) -> str:
    return _file_of(str(dlg._saved_combo.currentData() or ""))


def _pick(dlg, i: int, qapp) -> None:
    dlg._saved_combo.setCurrentIndex(i)
    qapp.processEvents()


# --------------------------------------------------------------------------
# the selector
# --------------------------------------------------------------------------
def test_every_saved_report_of_the_run_is_offered(tmp_path, qapp):
    """Four files across two dates, four entries, one per FILE.

    MUTATION: list `self._history` rows instead of their `_all_report_files`
    and this goes red (two entries instead of four).
    """
    s, _fm, run, vs = _env(tmp_path, dates=2, per_date=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        on_disk = sum(len(_reports(v)) for v in vs)
        assert on_disk == 4, on_disk
        assert _count(dlg) == 4, (
            f"{_count(dlg)} entries for {on_disk} saved reports")
    finally:
        dlg.close()


def test_the_selector_never_offers_another_run_s_reports(tmp_path, qapp):
    """Everything this window WRITES is its own run's, for the reason
    `_recalculate_run` gives at length. A window gathers the whole project's
    history to draw the trend (#40); offering to delete out of that list would
    be the widest reach in the window.

    MUTATION: drop the `mine` filter from `_saved_report_choices` and this goes
    red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import build_report, save_report
    s, fm, run, _vs = _env(tmp_path, dates=1, per_date=1)
    # THE WINDOW HAS TO BE ON THE SHAPE THAT GATHERS ACROSS RUNS, which is a
    # run's own profiling measurement: `list_project_reports` globs
    # `runs/*/reports` there and `runs/*/verifications/*/reports` for a dated
    # one. A first cut of this test opened on a verification, where the other
    # run's report is not in the history at all, and passed with the filter
    # deleted.
    own = run.dir / "P.ti3"
    own.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    save_report(build_report(own), run.dir)
    run2 = fm.project().new_run()
    run2.ensure_dir()
    other = run2.dir / "P.ti3"
    other.write_text(_cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
                     encoding="utf-8")
    p2 = save_report(build_report(other), run2.dir)
    dlg = _dialog(s, own, qapp)
    try:
        assert any(str(r.get("_origin_dir")) == str(run2.dir)
                   for r in dlg._history), (
            "the history does not span both runs, so this proves nothing")
        # BY FOLDER, NOT BY FILE NAME. `save_report` names by the second, so
        # two runs' first reports of the same second are the same NAME in
        # different folders, and a first cut of this test compared the names
        # and failed on a window that was filtering correctly.
        keys = [_key(dlg, i) for i in range(_count(dlg))]
        assert keys, "the selector is empty, so this proves nothing"
        assert not any(str(run2.dir) in k for k in keys), (
            f"the selector offers another run's report: {keys}")
        assert p2.is_file()
    finally:
        dlg.close()


def test_two_reports_of_one_second_are_told_apart_in_the_list(tmp_path, qapp):
    """Driven on screen before this was added: a run holding fifty reports of
    one measurement drew forty-eight identical lines. A list where a reader
    cannot tell which entry they are about to delete is not a selector.

    MUTATION: drop the "saved {when}" clause from `_saved_report_label` and
    this goes red.
    """
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=3)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        labels = [_text(dlg, i) for i in range(_count(dlg))]
        assert len(labels) == 3
        assert len(set(labels)) == 3, labels
    finally:
        dlg.close()


def test_choosing_an_entry_that_is_not_the_first_one_sticks(tmp_path, qapp):
    """`combo.findData` cannot compare a PyQt-wrapped tuple: the item is there,
    `itemData(i) == want` is True in Python, and it answers -1 all the same.
    Driven on screen, the selector snapped back to the first entry on every
    pick, so choosing any report but the top one was impossible.

    MUTATION: restore `combo.findData(want)` in `_sync_saved_reports` and this
    goes red.
    """
    s, _fm, _run, vs = _env(tmp_path, dates=2, per_date=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        # A REPORT OF ANOTHER MEASUREMENT, which is the shape it was driven on.
        # Picking a second report of the SAME measurement did not reproduce it:
        # `findData` answered correctly there and only failed once the pick
        # moved the window's row, so a test on the easy shape passed with the
        # scan replaced by `findData` again.
        here = str(vs[-1].dir)
        i = next(n for n in range(_count(dlg)) if here not in _key(dlg, n))
        want = _key(dlg, i)
        _pick(dlg, i, qapp)
        assert str(dlg._saved_combo.currentData() or "") == want, (
            f"the selector went back to index "
            f"{dlg._saved_combo.currentIndex()}")
    finally:
        dlg.close()


def test_the_document_follows_the_report_that_was_chosen(tmp_path, qapp):
    """The selector's job. The three reports of one measurement are identical
    here except for their files, so the check is on WHICH FILE the window's row
    came from, which is what the document is built out of.

    MUTATION: drop the `_chosen_reports` lookup from `_one_row_per_measurement`
    and this goes red.
    """
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=3)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        was = str(dlg._report.get("_report_file"))
        i = next(n for n in range(_count(dlg))
                 if _file_of(_key(dlg, n)) != was)
        other = _file_of(_key(dlg, i))
        _pick(dlg, i, qapp)
        assert str(dlg._report.get("_report_file")) == other, (
            f"the window still shows {dlg._report.get('_report_file')}")
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# the delete
# --------------------------------------------------------------------------
def test_delete_moves_exactly_the_chosen_report_and_destroys_nothing(tmp_path,
                                                                     qapp):
    """One report, named in the question, MOVED into `old/` (L.7).

    Knut, 2026-09-18: *"Having this list, also requires a 'Delete Selected
    Report' button … which then creates a dated report folder in the old/
    folder where the files for that report is moved to."* This button used to
    `unlink`, under a question that ended *"ChromIQ cannot undo this"*.

    MUTATION: unlink the file instead of moving it, or move a file the list is
    not on, and this goes red.
    """
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=3)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    asked: list = []
    dlg._confirm = lambda t, b: (asked.append((t, b)), True)[1]
    try:
        before = _reports(vs[0])
        target = _current_file(dlg)
        label = _text(dlg, dlg._saved_combo.currentIndex())
        dlg._on_delete_report()
        qapp.processEvents()
        after = _reports(vs[0])
        assert sorted(set(before) - set(after)) == [target]
        assert len(after) == len(before) - 1
        # ONE DATED VERIFICATION, so it lands in that date's own reports/old/.
        moved = list(vs[0].dir.glob("reports/old/*/" + target))
        assert moved, (
            f"{target} was destroyed instead of moved into old/: "
            f"{sorted((vs[0].dir / 'reports').rglob('*'))}")
        assert vs[0].measurement_ti3.is_file(), "the MEASUREMENT was deleted"
        assert asked and label in asked[0][1], (
            "the question does not name the report it is about to move")
        assert asked and "old" in asked[0][1], (
            "the question does not say where the files go")
    finally:
        dlg.close()


def test_saying_no_removes_nothing(tmp_path, qapp):
    """MUTATION: ignore `_confirm`'s answer and this goes red."""
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=3)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    dlg._confirm = lambda t, b: False
    try:
        before = _reports(vs[0])
        dlg._on_delete_report()
        qapp.processEvents()
        assert _reports(vs[0]) == before
    finally:
        dlg.close()


def test_the_only_report_of_a_dated_verification_cannot_be_deleted(tmp_path,
                                                                   qapp):
    """The one refusal, and it says why on screen rather than only greying out.

    MUTATION: return "" from `_saved_delete_refusal` and this goes red.
    """
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=1)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    dlg._confirm = lambda t, b: True
    try:
        assert _count(dlg) == 1
        assert not dlg._delete_report_btn.isEnabled()
        assert dlg._saved_note.toolTip(), "the refusal gives no reason"
        assert dlg._saved_note.text(), "the reason is not on screen"
        before = _reports(vs[0])
        dlg._on_delete_report()          # the keyboard, or a driver, can reach it
        qapp.processEvents()
        assert _reports(vs[0]) == before, "the last report was deleted anyway"
    finally:
        dlg.close()


def test_the_second_to_last_report_of_a_date_may_go(tmp_path, qapp):
    """The refusal is about the LAST one, not about dated verifications."""
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=2)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    dlg._confirm = lambda t, b: True
    try:
        assert dlg._delete_report_btn.isEnabled()
        dlg._on_delete_report()
        qapp.processEvents()
        assert len(_reports(vs[0])) == 1
        assert not dlg._delete_report_btn.isEnabled(), (
            "the last one is now deletable")
    finally:
        dlg.close()


def test_delete_is_dead_when_the_selector_is_empty(tmp_path, qapp):
    """Driven on screen: the last report of a profiling measurement deleted,
    the pulldown empty, and Delete still live over a list with nothing in it.

    MUTATION: drop the `r is not None` term and this goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import build_report, save_report
    s, fm, run, _vs = _env(tmp_path, dates=1, per_date=1)
    own = run.dir / "P.ti3"
    own.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    p = save_report(build_report(own), run.dir)
    dlg = _dialog(s, own, qapp)
    dlg._confirm = lambda t, b: True
    try:
        assert dlg._delete_report_btn.isEnabled(), (
            "a profiling measurement's only report is refused, and should not "
            "be: it is not a dated verification")
        dlg._on_delete_report()
        qapp.processEvents()
        assert not p.exists(), "the file is still in the reports folder"
        moved = list(run.dir.glob("reports/old/*/" + p.name))
        assert moved, "the file was destroyed instead of moved to old/"
        assert _count(dlg) == 0
        assert not dlg._delete_report_btn.isEnabled()
    finally:
        dlg.close()


def test_the_window_survives_losing_the_report_it_was_showing(tmp_path, qapp):
    """A delete changes what is ON DISK, so the window re-reads it.

    MUTATION: call `_rebuild_from_sources` instead of `_reload_sources` after
    the unlink and this goes red: the window redraws from the file that has
    just been removed.
    """
    s, _fm, run, _vs = _env(tmp_path, dates=1, per_date=1)
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import build_report, save_report
    own = run.dir / "P.ti3"
    own.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    save_report(build_report(own), run.dir)
    save_report(build_report(own), run.dir)
    dlg = _dialog(s, own, qapp)
    dlg._confirm = lambda t, b: True
    try:
        gone = _current_file(dlg)
        dlg._on_delete_report()
        qapp.processEvents()
        names = [_file_of(_key(dlg, i)) for i in range(_count(dlg))]
        assert gone not in names, "the window still offers a file that is gone"
        assert str(dlg._report.get("_report_file")) != gone, (
            "the window is still showing the report it deleted")
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# B8-251: the faint labels were invisible in the dark theme
# --------------------------------------------------------------------------
def _luminance(h: str) -> float:
    """WCAG relative luminance of a #rrggbb colour."""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


@pytest.mark.parametrize("mode,dark_ground", [("dark", True), ("light", False),
                                              ("neutral", False)])
def test_a_faint_label_is_a_colour_and_not_an_absence(mode, dark_ground):
    """`color: palette(mid)` resolved to #161616 on this window's near-black
    ground: a contrast ratio of 1.02, measured on screen, which is not a colour
    but an absence. It was the style on the "Already generated for this run:"
    line Knut asked for as well as on the Delete refusal, and a driver
    photographed a greyed-out Delete with no reason beside it at all.

    **THIS DOES NOT RE-STYLE THE APPLICATION.** `apply_appearance` calls
    `qapp.setStyleSheet`, which CLAUDE.md forbids in a test because it
    re-polishes every widget the suite has alive; a first cut of this test did
    exactly that and left the next two files in the run with a taller window
    and two red screen-fit assertions. The function under test is pure, so it
    is asked directly.

    MUTATION: return "color: palette(mid); padding-left: 4px" for any mode and
    this goes red.
    """
    from ui.dialogs.measurement_report_dialog import _faint_label_css
    css = _faint_label_css(mode)
    assert "palette(" not in css, css
    m = re.search(r"color:\s*(#[0-9a-fA-F]{6})", css)
    assert m, f"{mode}: no explicit colour in {css!r}"
    lum = _luminance(m.group(1))
    if dark_ground:
        assert lum >= 0.25, (
            f"{mode}: {m.group(1)} has luminance {lum:.3f} and is drawn on a "
            f"dark ground")
    else:
        assert lum <= 0.25, (
            f"{mode}: {m.group(1)} has luminance {lum:.3f} and is drawn on a "
            f"light ground")


def test_the_faint_labels_carry_that_colour_and_not_the_palette(tmp_path, qapp):
    """…and the window uses it, in whatever appearance this session is in.

    MUTATION: put `color: palette(mid)` back on either label and this goes red.
    """
    from PyQt6.QtGui import QPalette
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=2)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        for name in ("_saved_note", "_type_blurb"):
            w = getattr(dlg, name)
            fg = w.palette().color(QPalette.ColorRole.WindowText).name()
            mid = w.palette().color(QPalette.ColorRole.Mid).name()
            assert fg != mid, (
                f"{name} is styled with the palette's Mid role ({mid}), which "
                f"is a 3-D frame shade and not a text colour")
    finally:
        dlg.close()


def test_no_label_in_this_window_is_styled_with_palette_mid():
    """The role Qt uses for a 3-D frame shade is not a text colour, and this
    window had it on both of its secondary labels.

    MUTATION: put the string back and this goes red.
    """
    src = Path(__file__).resolve().parent.parent / "ui" / "dialogs" / \
        "measurement_report_dialog.py"
    text = src.read_text(encoding="utf-8")
    body = text.split('def _faint_label_css', 1)[1].split("\n    \"\"\"", 1)
    # the docstring of the helper explains the fault and may quote the string;
    # nothing OUTSIDE it may use it
    rest = body[1].split('"""', 1)[1] if len(body) > 1 else text
    assert "palette(mid)" not in rest, (
        "a label is styled with palette(mid) again")


def test_an_empty_list_says_to_press_generate_report(tmp_path, qapp):
    """**AND THE ROW NO LONGER HIDES ITSELF.** It used to, to save 42 px on an
    800 px screen, which left a user with no way of knowing the list was there.
    Knut, 2026-09-18 (L.9): *"The window needs to show clearly that a user
    should select a report in the list to show/load a previously generated
    report. IF the list is empty, then the user could also be informed to Click
    Generate Report to create the first report."*

    The height it costs is still the thing that was right about the old
    behaviour, so `_fits` is asserted in the same breath.

    MUTATION: drop the `_set_saved_hint` call from the empty branch of
    `_sync_saved_reports` and this goes red.
    """
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        assert _count(dlg) == 0, "this run has a saved report"
        assert dlg._saved_combo.isVisible(), (
            "the selector hides itself when empty")
        assert not dlg._delete_report_btn.isEnabled()
        assert "Generate report" in dlg._saved_hint.toolTip(), (
            f"the empty list says {dlg._saved_hint.toolTip()!r}")
        assert dlg._saved_hint.text(), "the sentence is not on screen"
        assert _fits(dlg)
    finally:
        dlg.close()


def _fits(dlg) -> bool:
    """Whether this window's layout can be made to fit the screen.

    **NOT `dlg.geometry()`.** The offscreen platform prints *"This plugin does
    not support propagateSizeHints()"* and ignores `resize` and `move` outright,
    so the rectangle it reports is its own choice and not the window's: measured
    here, `showEvent` brought the layout's minimum from 957 px to 729 px against
    a 760 px cap, asked for 729, and the plugin handed back 819. What
    `showEvent` actually controls, and what decides whether a real window's
    bottom lands off a real screen, is the layout's own minimum against that
    cap, so that is what is measured. The two geometry assertions in
    `tests/test_install_rename_and_run_filter.py` are left exactly as they are:
    they are the record of the bug that was reported.
    """
    lay = dlg.layout()
    lay.activate()
    cap = max(1, dlg.screen().availableGeometry().height() - 40)
    assert lay.minimumSize().height() <= cap, (
        f"the layout cannot go below {lay.minimumSize().height()} px on a "
        f"screen that allows {cap}")
    return True


def test_the_window_still_fits_the_screen_with_the_row_on_it(tmp_path, qapp):
    """And with something to choose, which is when the row costs its 42 px.

    The ladder in `showEvent` trades the report view and then the charts when
    the layout's own minimum will not fit; this is the check that it still has
    enough to trade. Measured on this fixture: 957 px before the ladder,
    729 px after, against a 760 px cap.
    """
    s, _fm, _run, vs = _env(tmp_path, dates=2, per_date=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._saved_combo.isVisible() and _count(dlg) == 4
        assert _fits(dlg)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# B8-252: the newest report is the one written last
# --------------------------------------------------------------------------
def test_the_file_written_last_wins_even_when_its_name_is_older(tmp_path, qapp):
    """A project made elsewhere can carry a report whose NAME is a date in the
    future: the demo packs seed each report with the date they want it to read.
    A report generated today then sorted below it, and the window went on
    describing the seeded one.

    MUTATION: drop the mtime from `_report_order` and this goes red.
    """
    import os as _os
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=1)
    d = vs[0].dir / "reports"
    old_name = d / "report_2099-01-01_00-00-00.json"
    (next(d.glob("report_*.json"))).rename(old_name)
    from workflow.measurement_report import build_report, save_report
    fresh = save_report(build_report(vs[0].measurement_ti3), vs[0].dir)
    # the seeded file's NAME is later and its TIME is earlier, which is the
    # shape measured on the pack
    _os.utime(old_name, (1, 1))
    assert old_name.name > fresh.name, "this test needs the name order reversed"
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        assert str(dlg._report.get("_report_file")) == fresh.name, (
            f"the window shows {dlg._report.get('_report_file')}, which is not "
            f"the file written last")
    finally:
        dlg.close()


def test_generate_shows_the_report_it_just_wrote(tmp_path, qapp):
    """A button that writes a file and changes nothing on screen.

    Driven in a real window: an older report of the date chosen in the
    pulldown, Generate pressed, one new file on disk, the selector still at
    four entries and the document unchanged.

    MUTATION: drop the `_chosen_reports.pop` loop, or the `_reload_sources`
    call, from `_on_generate_report` and this goes red.
    """
    s, _fm, _run, vs = _env(tmp_path, dates=1, per_date=3)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        # point the window at the OLDEST of the three
        oldest = sorted(_reports(vs[0]))[0]
        i = next(n for n in range(_count(dlg))
                 if _file_of(_key(dlg, n)) == oldest)
        _pick(dlg, i, qapp)
        assert str(dlg._report.get("_report_file")) == oldest
        before = set(_reports(vs[0]))
        dlg._on_generate_report()
        qapp.processEvents()
        after = set(_reports(vs[0]))
        written = sorted(after - before)
        assert len(written) == 1, written
        # …AND THE LIST GAINED EXACTLY ONE ENTRY, because one press of Generate
        # is one DOCUMENT (B8-383). The three files already there carry no
        # document block, so they are three one-file documents; the new one is
        # the fourth entry.
        assert _count(dlg) == len(after), (
            "the report it just wrote is not in the list")
        assert str(dlg._report.get("_report_file")) == written[0], (
            f"Generate wrote {written[0]} and the page still describes "
            f"{dlg._report.get('_report_file')}")
        # AND THE SELECTOR, WHICH THIS TEST NEVER ASKED. B8-308, Knut, beta 20:
        # *"Now there are two reports in the 'Saved reports' pulldown, but the
        # selected option did not change to the new report I generated last."*
        # The page moved and the pulldown did not, so the window's header named
        # one report and its selector named another, in front of him. The
        # missing line below is why that shipped.
        row = dlg._saved_combo.currentIndex()
        names = [m[1] for m in dlg._saved_documents(
            dlg._run_ctx.run if dlg._run_ctx else None)[row]["members"]]
        assert names == [written[0]], (
            f"Generate wrote {written[0]} and the selector names {names}")
    finally:
        dlg.close()
