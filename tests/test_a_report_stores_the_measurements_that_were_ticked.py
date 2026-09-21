"""What is ticked when Generate is pressed is what the report holds, and the
date tag in its name says so.

**KNUT, 2026-09-20, ON BETA 26, TWICE AND IN OPPOSITE DIRECTIONS (B8-521,
B8-522).**

> *"I tried selecting New report, then selecting 3 measurements included, of
> the 11 in the list, then Generate report. The resulting report now says 'All
> dates' and the 'Included Measurements in report' box has ticked all
> measurements. This is wrong. Only the measurements ticked at the time I press
> Generate Report shall be stored as part of the report, and then re-selected
> when selecting the report in Report shown pulldown."*

> *"the report name ended with 'One date', while it was supposed to have All
> dates. When selecting another report and then going back to the one I newly
> created the 'Included Measurements in report' box only had one (the last
> one) ticked. … The 'One date' tag also needs to be updated if I update the
> report to contain other measurements included."*

Two mechanisms, and both were measured in a real window on his own demo project
before a line was changed (`scripts/drive_k26_included_measurements.py`,
`~/Desktop/ChromIQ-beta28-proof/knut-beta26-review/before/`):

1. **The tick marks and `_hidden_runs` could disagree.** Only
   `_rebuild_from_sources` drew a tick; every other door that assigned the set
   repainted through `_refresh`, which never touches the list. Measured: after
   Generate the list showed 11 ticks over a `_hidden_runs` of 10, and choosing
   "New report…" showed 1 tick over a `_hidden_runs` of none. Because
   `setCheckState` to a value a row already holds emits nothing, every later
   tick was then read against the wrong baseline: three rows ticked produced a
   document of ten.
2. **The date flag asked the tick box, not the document.** `all_runs and not
   self._hidden_runs` is a second answer to a question the member list already
   answers, and it disagreed with it in both directions.

**AND THE BOX ITSELF WENT, TWO DAYS LATER (B8-590, B8-591).** Knut, 2026-09-20,
on the same window: *"I realise now this checkbox is not a reasonable feature
to have … Remove the feature 'Show all measurement runs' totally from the
design, and any feature that belongs to that button … only the selected/ticked
measurements shall be part of the report when created/updated (always)."*

That is this file's sentence made unconditional, so nothing below it changed
its subject: what is ticked at the press is what the report holds. Two things
did change, and both are marked where they are checked. The fixture reaches
"everything ticked" through the "Select all" button he asked for. And the
one-page summary no longer DRAWS a narrowing the set behind it does not hold:
that was the second half of B8-591, *"the 'included measurements in report'
became unticked for all measurements and it froze"* — the rows had not been
unticked, they had been drawn that way over a live set, so the list and the
report disagreed and a click on such a row was painted straight back.

His log of the session confirms the first and rules out a third theory: the
eleven files a press wrote went to eleven DIFFERENT dated folders, one each
(`report_2026-09-20_02-28-56.json` in each of `2026-01-05_100000` …
`2026-05-25_100000`), so nothing was overwritten.
"""
from __future__ import annotations

import json

import pytest

import workflow.measurement_report as mr

pytestmark = pytest.mark.usefixtures("qapp")

DATES = ("2026-09-01_100000", "2026-09-08_100000", "2026-09-15_100000")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _run_keys(dlg) -> list:
    return [k for kind, _si, k in dlg._list_rows if kind == "run" and k]


def _ticked(dlg) -> list:
    """The keys the LIST shows ticked — what a person sees, not what the set
    behind it holds."""
    from PyQt6.QtCore import Qt
    out = []
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind != "run" or key is None:
            continue
        if dlg._profile_list.item(i).checkState() == Qt.CheckState.Checked:
            out.append(key)
    return out


def _tick(dlg, key: str, on: bool) -> None:
    """Tick a row the way a click does: through the item, so `itemChanged`
    fires and the window learns about it."""
    from PyQt6.QtCore import Qt
    for i, (kind, _si, k) in enumerate(dlg._list_rows):
        if kind == "run" and k == key:
            dlg._profile_list.item(i).setCheckState(
                Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            return
    raise AssertionError(f"no row for {key}")


def _keep_only(dlg, keys) -> None:
    for k in _run_keys(dlg):
        _tick(dlg, k, k in set(keys))


def _generate_new(dlg) -> None:
    """Press Generate on "New report…", which asks nothing."""
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(NEW_REPORT_KEY))


def _latest_document(dlg) -> dict:
    """The document block of the newest report file in the project."""
    root = dlg._run_ctx.run.dir
    files = sorted(root.rglob("report_*.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(files[-1].read_text(encoding="utf-8"))["document"]


def _entry_name(dlg) -> str:
    return dlg._saved_combo.currentText()


def _choose_type(dlg, type_id: str) -> None:
    """Change the report type THROUGH THE PULLDOWN, which is the door.

    Calling `_sync_limit_controls` by hand is not the door: the pulldown's own
    handler is what marks the settings touched and repaints, and a guard that
    skips it measures a state no user can reach.
    """
    i = dlg._type_combo.findData(type_id)
    assert i >= 0, type_id
    dlg._type_combo.setCurrentIndex(i)


# --------------------------------------------------------------------------
# the ticks the list DRAWS follow the set behind them, at every door
# --------------------------------------------------------------------------
def test_new_report_redraws_the_ticks_it_just_cleared(three_dated):
    """Door 1, and the one Knut walked through: "New report…" forgets the
    narrowing, so every row must come back ticked.

    Before the fix this left the previous document's ticks on screen over an
    empty `_hidden_runs`, which is the baseline every later tick was read
    against.

    MUTATION PROVEN: remove the one `_draw_the_row_ticks()` call, at the end
    of `_sync_limit_controls`, and this goes red with 1 tick of 3.
    """
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY

    dlg = three_dated
    keys = _run_keys(dlg)
    _keep_only(dlg, keys[:1])
    assert dlg._hidden_runs == set(keys[1:]), "the premise"
    dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(NEW_REPORT_KEY))
    assert dlg._hidden_runs == set(), "the set really was cleared"
    assert set(_ticked(dlg)) == set(keys), (
        "the list still shows the last document's narrowing over a set that "
        "holds nothing")


def test_the_page_that_adopts_a_new_document_redraws_the_ticks(three_dated):
    """Door 2: Generate, then the page moves to the document it just wrote.

    MUTATION PROVEN: remove the one `_draw_the_row_ticks()` call and this goes
    red with 3 ticks over a set of one hidden.
    """
    dlg = three_dated
    keys = _run_keys(dlg)
    _generate_new(dlg)
    _keep_only(dlg, keys[:2])
    dlg._on_generate_report()
    assert set(_ticked(dlg)) == set(keys[:2]), (
        "after Generate the list disagrees with the document it is showing")
    assert dlg._hidden_runs == {keys[2]}


# --------------------------------------------------------------------------
# what is stored, and what comes back
# --------------------------------------------------------------------------
def test_only_the_ticked_measurements_are_stored(three_dated):
    """His sentence, word for word.

    MUTATION PROVEN: `return [r for r in self._history]` in
    `_runs_for_report`, ignoring `_hidden_runs`, and this goes red with 3
    measurements recorded where 2 were ticked.
    """
    dlg = three_dated
    keys = _run_keys(dlg)
    _generate_new(dlg)
    _keep_only(dlg, keys[:2])
    dlg._on_generate_report()
    doc = _latest_document(dlg)
    stored = {str(m.get("key") or "") for m in doc["measurements"]}
    assert stored == set(keys[:2]), sorted(stored)


def test_and_they_are_re_ticked_when_the_report_is_selected_again(three_dated):
    """*"…and then re-selected when selecting the report in Report shown
    pulldown."*

    MUTATION PROVEN: drop the one `_draw_the_row_ticks()` call and this goes
    red -- two of three ticked, all three drawn ticked afterwards.
    """
    dlg = three_dated
    keys = _run_keys(dlg)
    _generate_new(dlg)
    _keep_only(dlg, keys[:2])
    dlg._on_generate_report()
    mine = str(dlg._saved_combo.currentData() or "")
    # …away to another entry, and back, which is what he did.
    other = next(str(dlg._saved_combo.itemData(i))
                 for i in range(dlg._saved_combo.count())
                 if str(dlg._saved_combo.itemData(i)) not in (mine, "new:"))
    dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(other))
    dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(mine))
    assert set(_ticked(dlg)) == set(keys[:2]), sorted(_ticked(dlg))


# --------------------------------------------------------------------------
# the date flag says what the document covers
# --------------------------------------------------------------------------
@pytest.mark.parametrize("n,flag", [(3, "All dates"), (2, "Multiple dates"),
                                    (1, "One date")])
def test_the_date_flag_counts_the_document_not_the_tick_box(three_dated, n,
                                                            flag):
    """F.1 to F.4 of §13.7, derived from the member list alone.

    MUTATION PROVEN: `return SCOPE_MULTIPLE_DATES` unconditionally after the
    one-member branch and the three-of-three case goes red.

    **AND THE OLD PREDICATE PASSES THIS ONE**, which is worth saying rather
    than hiding: with the ticks and `_hidden_runs` back in step (B8-521),
    `all_runs and not self._hidden_runs` agrees with the member list in every
    state reachable from a window that has only ever had one project in it.
    `test_a_stale_untick_no_longer_mislabels_every_later_report` below is the
    state where the two part company, and it is the one that justifies the
    change.
    """
    dlg = three_dated
    keys = _run_keys(dlg)
    _generate_new(dlg)
    _keep_only(dlg, keys[:n])
    dlg._on_generate_report()
    assert flag in _entry_name(dlg), _entry_name(dlg)


def test_an_update_that_changes_the_membership_changes_the_flag(three_dated,
                                                                monkeypatch):
    """*"The 'One date' tag also needs to be updated if I update the report to
    contain other measurements included."*

    The popup is answered by patching the ONE method that asks it, never
    `QDialog.exec`.

    MUTATION PROVEN: store the flag from the FIRST press (pass
    `scope=document_scope_of(doc)` in the update branch) and this goes red,
    the name still saying "All dates" over a document of two.
    """
    dlg = three_dated
    keys = _run_keys(dlg)
    _generate_new(dlg)
    _keep_only(dlg, keys)
    dlg._on_generate_report()
    assert "All dates" in _entry_name(dlg), _entry_name(dlg)

    asked: list = []
    monkeypatch.setattr(type(dlg), "_ask_update_or_create_new",
                        lambda self: asked.append("asked") or "update")
    _tick(dlg, keys[0], False)
    dlg._on_generate_report()
    assert asked, "the three-button question was never put"
    name = _entry_name(dlg)
    assert "Multiple dates" in name, name
    assert "All dates" not in name, name
    assert "updated" in name, name
    doc = _latest_document(dlg)
    assert len(doc["measurements"]) == 2


def test_a_stale_untick_no_longer_mislabels_every_later_report(three_dated,
                                                               second_run,
                                                               monkeypatch):
    """THE STATE THE TWO ANSWERS PART COMPANY IN, and the reason the flag is
    derived from the members rather than from the tick box.

    `_hidden_runs` is keyed by the measurement's absolute folder, and nothing
    prunes it when a profile is removed from the list. So: add a second
    profile, untick one of ITS rows, remove that profile again, and the set
    keeps a key that matches nothing on screen. Every row that is left is
    covered, and the old predicate -- `all_runs and not self._hidden_runs` --
    reads the leftover as "something is hidden" and names every later report
    "Multiple dates" for the rest of the session.

    MUTATION PROVEN: restore `all_runs and not self._hidden_runs` in
    `_document_scope` and this goes red, the name reading "Multiple dates"
    over a document that covers every measurement in the list.
    """
    dlg = three_dated
    dlg._add_source(second_run)
    dlg._rebuild_from_sources()
    theirs = [k for k in _run_keys(dlg) if "Other" in k]
    assert theirs, "the premise: the second profile really is in the list"
    _tick(dlg, theirs[0], False)
    # …and now the profile goes away, taking its rows with it and leaving the
    # key behind.
    dlg._sources = [s for s in dlg._sources if "Other" not in str(s["dir"])]
    dlg._rebuild_from_sources()
    assert theirs[0] in dlg._hidden_runs, "the stale key is the premise"
    assert not any("Other" in k for k in _run_keys(dlg)), "it really is gone"

    # NOT through "New report…": that clears `_hidden_runs`, stale key and
    # all, so the state under test would be gone before Generate is pressed.
    # The press is answered with Create New, which is the door a user takes
    # from a loaded document.
    monkeypatch.setattr(type(dlg), "_ask_update_or_create_new",
                        lambda self: "new")
    _keep_only(dlg, _run_keys(dlg))
    assert theirs[0] in dlg._hidden_runs, "the stale key survived to the press"
    dlg._on_generate_report()
    name = _entry_name(dlg)
    assert "All dates" in name, name


# --------------------------------------------------------------------------
# the one-page summary DRAWS what it will store, and narrows nothing
# --------------------------------------------------------------------------
def test_the_one_page_summary_draws_the_ticks_it_really_holds(three_dated):
    """**THE DRAWING RULE WAS THE NEXT FAULT, AND IT IS GONE (B8-591).**

    This used to pin the opposite: picking T1 was expected to DRAW one tick of
    three over an untouched `_hidden_runs`, so that a user who had ticked
    eleven could see, before pressing anything, that the page covers one sheet.
    The idea was to say the true thing without throwing the ticks away.

    What it did instead is what Knut reported on 2026-09-20: *"Then the
    'included measurements in report' became unticked for all measurements and
    it froze, so I cannot scroll or select."* They had not been unticked; they
    had been DRAWN unticked over a set that still held them, so the list showed
    1 where `_runs_for_report` returned 3 -- the visible ticks were not the
    ticks the report would use -- and a real click on such a row toggled the
    item and was immediately painted back, which from the outside is a dead
    list. The list was disabled as well, which is the freeze itself.

    So the list now tells the truth about itself under every type, and the
    one-page limit is said at Generate instead
    (`test_a_one_page_summary_refuses_a_press_that_covers_several`).

    MUTATION PROVEN: any `_rows_drawn_unticked` that answers something other
    than `_hidden_runs`, or an `lst.setEnabled(False)` under T1, and this goes
    red.
    """
    dlg = three_dated
    keys = _run_keys(dlg)
    # On "New report…", so the RUN's type governs: a loaded document carries
    # the type it was made with and would keep the pulldown on it.
    _generate_new(dlg)
    _keep_only(dlg, keys)
    _choose_type(dlg, mr.REPORT_TYPE_SUMMARY)
    assert set(_ticked(dlg)) == set(keys), (
        "the list draws a narrowing the set behind it does not hold: "
        f"drawn={_ticked(dlg)!r} hidden={dlg._hidden_runs!r}")
    assert dlg._profile_list.isEnabled(), "the list is frozen under T1"
    assert dlg._hidden_runs == set(), (
        "the ticks the user set were thrown away, so the trend charts and the "
        "next report type lost the history")
    assert {dlg._run_key(r) for r in dlg._runs_for_report()} == set(keys), (
        "what is drawn and what the report would cover disagree")

    _choose_type(dlg, mr.REPORT_TYPE_FULL)
    assert set(_ticked(dlg)) == set(keys), "the ticks did not come back"


def test_a_one_page_summary_refuses_a_press_that_covers_several(three_dated,
                                                                monkeypatch):
    """The limit is now SAID, at the press, and no tick moves (B8-591).

    Knut asked for exactly this in place of the silent narrowing: *"the user
    should be informed … Then the user can close that message and do the
    changes, and then click generate report again."*

    MUTATION PROVEN: delete the `_one_page_wants_one_measurement()` guard from
    `_on_generate_report` and a document of one is written out of three ticks,
    which is the report named "One date" he photographed.
    """
    import ui.warning_sign as WS
    from workflow import measurement_messages as M
    dlg = three_dated
    keys = _run_keys(dlg)
    _generate_new(dlg)
    _keep_only(dlg, keys)
    _choose_type(dlg, mr.REPORT_TYPE_SUMMARY)
    said: list = []
    monkeypatch.setattr(WS, "inform",
                        lambda parent, title, text, *a, **k: said.append(
                            (title, text)))
    root = dlg._run_ctx.run.dir
    before = sorted(q.name for q in root.rglob("report_*.json"))
    dlg._on_generate_report()
    assert said == [M.CATALOGUE["M-REPORT-ONE-PAGE-ONE-DATE"].render(count=3)]
    assert sorted(q.name for q in root.rglob("report_*.json")) == before, (
        "a refused press still wrote a report")
    assert set(_ticked(dlg)) == set(keys), "the refusal moved a tick"
    assert dlg._hidden_runs == set()


def test_a_one_page_summary_is_named_one_date_and_stores_one(three_dated):
    """The other half: with ONE measurement ticked, what the list shows is what
    the document holds, so the name agrees with what the user was looking at.

    It used to reach the one-measurement state by letting the window draw it
    (`_rows_drawn_unticked`); the user ticks it now, which is the whole of
    B8-591. The assertion is unchanged, because the rule it guards is.

    MUTATION PROVEN: make `_runs_for_document` ignore `_runs_for_report` and
    the stored members stop matching the ticks on screen.
    """
    dlg = three_dated
    keys = _run_keys(dlg)
    _generate_new(dlg)
    _keep_only(dlg, keys[-1:])
    _choose_type(dlg, mr.REPORT_TYPE_SUMMARY)
    drawn = _ticked(dlg)
    assert drawn == [dlg._run_key(dlg._report)], drawn
    dlg._on_generate_report()
    doc = _latest_document(dlg)
    assert {str(m["key"]) for m in doc["measurements"]} == set(drawn)
    assert "One date" in _entry_name(dlg), _entry_name(dlg)


# --------------------------------------------------------------------------
# fixture
# --------------------------------------------------------------------------
@pytest.fixture
def three_dated(tmp_path, qapp):
    """A SHOWN window on a run with three dated verifications.

    Three, not two: two cannot tell "all of them" from "more than one but not
    all", which is the pair of flags that disagreed.
    """
    import sys
    from pathlib import Path

    from PyQt6.QtCore import QSettings

    from core.file_manager import Project
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.run_compliance import ensure_bound, set_run_report_type
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from drive_one_page_report import _GRID, _srgb_to_xyz_d50

    work = tmp_path / "w"
    work.mkdir()
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    st.set("custom_output_path", str(work))
    proj = Project.create(work / "Three", "Three")
    run = proj.current_run()
    run.ensure_dir()

    def write(path, scale):
        rows, n = [], 0
        for r in _GRID:
            for g in _GRID:
                for b in _GRID:
                    n += 1
                    x, y, z = _srgb_to_xyz_d50(r, g, b)
                    x, y, z = x * scale + 0.25, y * scale + 0.2, z * scale + 0.15
                    rows.append(f"{n} {r:.4f} {g:.4f} {b:.4f} "
                                f"{x / 100:.6f} {y / 100:.6f} {z / 100:.6f}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            'CTI3\n\nDESCRIPTOR "x"\nKEYWORD "DEVICE_CLASS"\n'
            'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
            "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n",
            encoding="utf-8")

    paths = []
    for stamp, scale in zip(DATES, (0.985, 0.96, 0.93)):
        p = run.dir / "verifications" / stamp / "Chart.ti3"
        write(p, scale)
        rep = mr.build_report(p)
        rep["created"] = stamp[:10].replace("_", "") + "T10:00:00"
        rep["created"] = (f"{stamp[:4]}-{stamp[5:7]}-{stamp[8:10]}T10:00:00")
        mr.save_report(rep, p.parent)
        paths.append(p)
    ensure_bound(run, None, "chromiq_default")
    set_run_report_type(run, mr.REPORT_TYPE_FULL)

    dlg = MeasurementReportDialog(st, None, initial_ti3=paths[-1])
    dlg.resize(1400, 900)
    dlg.show()
    qapp.processEvents()
    # EVERY MEASUREMENT TICKED, which is the state these checks start from.
    # It used to be `dlg._all_runs_check.setChecked(True)`; the box and the
    # feature behind it were removed on Knut's 2026-09-20 ruling (B8-590) and
    # "Select all" is the button he asked for in its place.
    dlg._select_all_btn.click()
    dlg._refresh()
    yield dlg
    dlg.close()


@pytest.fixture
def second_run(tmp_path, qapp):
    """A measurement belonging to ANOTHER profile, to add and then remove."""
    import sys
    from pathlib import Path

    from core.file_manager import Project
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from drive_one_page_report import _GRID, _srgb_to_xyz_d50

    work = tmp_path / "w2"
    work.mkdir()
    proj = Project.create(work / "Other", "Other")
    run = proj.current_run()
    run.ensure_dir()
    p = run.dir / "verifications" / "2026-09-20_100000" / "Chart.ti3"
    rows, n = [], 0
    for r in _GRID:
        for g in _GRID:
            for b in _GRID:
                n += 1
                x, y, z = _srgb_to_xyz_d50(r, g, b)
                x, y, z = x * 0.9 + 0.25, y * 0.9 + 0.2, z * 0.9 + 0.15
                rows.append(f"{n} {r:.4f} {g:.4f} {b:.4f} "
                            f"{x / 100:.6f} {y / 100:.6f} {z / 100:.6f}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        'CTI3\n\nDESCRIPTOR "x"\nKEYWORD "DEVICE_CLASS"\n'
        'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n",
        encoding="utf-8")
    rep = mr.build_report(p)
    rep["created"] = "2026-09-20T10:00:00"
    mr.save_report(rep, p.parent)
    return p


def test_the_fixture_holds_three_measurements_that_can_be_told_apart(
        three_dated):
    """A GUARD ON THE TEST. `_run_key` is the created stamp plus the file name,
    so three reports built in the same second are one key three times and every
    test above would pass on a list of one."""
    dlg = three_dated
    keys = _run_keys(dlg)
    assert len(keys) == len(set(keys)) == 3, keys
    assert dlg._run_key(dlg._report) == keys[-1], "the window is on the newest"
