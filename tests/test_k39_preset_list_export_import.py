"""Export list and Import list in the gear window (Knut, #182 5831246553,
beta 43, B8-1101 to B8-1104).

*"one "Export list" and one "Import list". The export button saves a csv file
of the table with the current settings. The import button imports the same
type of file back into the app and updates the checked settings. file dialogs
open in the ChromIQ default folder. The saved filename should have a
pre-defined name that explains what this list is. The import file dialog is
filtered to only accept csv file type, as was exported."*

What these tests hold:

* Export writes the ticks AS SHOWN, unsaved changes included, in exactly the
  table ``scripts/make_preset_defaults.py --table`` writes (same columns, same
  rows, same names), and ``--from-table`` reads it back to the same ticks;
* Import sets the ticks by key; a key ChromIQ does not have, a row without a
  key and an empty or unreadable yes/no are reported and change nothing; a
  preset the file does not name keeps its tick; a file that is not a table
  changes nothing;
* Import changes only the window: OK stores it, Close discards it (B8-1097);
* both file windows open in the ChromIQ folder, the save window offers
  "ChromIQ built-in presets shown.csv", and both are filtered to .csv;
* the two buttons sit at the bottom LEFT, and OK and Close stay at the right.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPoint, QRect, QSettings, QTimer        # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402

import core.curated_presets as cp                                # noqa: E402
from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.file_manager import FileManager                        # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.dialogs.builtin_presets_shown_dialog import (            # noqa: E402
    BuiltinPresetsShownDialog,
)
from ui.tabs.tab_chart import (                                  # noqa: E402
    BUILTIN_PRESET_KEYS, TabChart, builtin_preset_facts,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    (tmp_path / "out").mkdir()
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


@pytest.fixture()
def make_tab(qapp, settings):
    made = []

    def build():
        t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
        made.append(t)
        return t
    yield build
    for t in made:
        t.hide()
        t.deleteLater()
    qapp.processEvents()


@pytest.fixture()
def dlg(make_tab):
    """The window exactly as the gear builds it, without its exec."""
    tab = make_tab()
    d = BuiltinPresetsShownDialog(
        tab._curated_dialog_groups(),
        cp.shown_keys(tab._settings, BUILTIN_PRESET_KEYS), tab,
        facts=builtin_preset_facts(), folder=tab._file_mgr.root_dir())
    d._exec_box = lambda box: setattr(d, "_last_box", box)
    yield d
    d.deleteLater()


def _script():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import make_preset_defaults
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    return make_preset_defaults


def _rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.reader(fh))


def _write(path: Path, rows: list[list[str]], delim: str = ",") -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, delimiter=delim).writerows(rows)
    return path


def _some(dlg, n=3):
    shown = sorted(dlg.ticked())
    hidden = sorted(set(BUILTIN_PRESET_KEYS) - set(shown))
    return shown[:n], hidden[:n]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export_writes_the_ticks_as_shown_including_unsaved_changes(
        dlg, tmp_path):
    """MUTATION, proved to land: ``export_to`` writing the shipped list
    instead of ``self.ticked()`` (red: the two changed rows read as
    before)."""
    on, off = _some(dlg)
    dlg.set_ticked(off[0], True)
    dlg.set_ticked(on[0], False)
    out = tmp_path / "x.csv"
    dlg.export_to(out)
    rows = _rows(out)
    assert rows[0] == cp.TABLE_HEADER
    answer = {r[4]: r[2] for r in rows[1:]}
    assert answer[off[0]] == "yes"
    assert answer[on[0]] == "no"
    assert set(answer.values()) == {"yes", "no"}
    assert {k for k, v in answer.items() if v == "yes"} == dlg.ticked()


def test_the_export_is_the_scripts_table_with_the_answers_filled_in(
        make_tab, tmp_path):
    """Same columns, same rows in the same order, same names and groups as
    ``make_preset_defaults.py --table``; only the answer column is filled.
    Exported from the window the GEAR opens, through its own button.

    MUTATION, proved to land: the gear building the window without
    ``facts=`` (the names then come from the overlay labels, red)."""
    mpd = _script()
    blank = tmp_path / "blank.csv"
    mpd.write_table(blank)
    ours = tmp_path / "ours.csv"
    tab = make_tab()
    done = {}

    def act():
        d = tab._builtin_presets_shown_dialog
        if d is None or not d.isVisible():
            QTimer.singleShot(10, act)
            return
        d._ask_save_path = lambda: str(ours)
        d._export_btn.click()
        done["ok"] = True
        d._close_btn.click()

    QTimer.singleShot(0, act)
    tab._open_builtin_presets_shown()
    assert done.get("ok")
    a, b = _rows(blank), _rows(ours)
    assert a[0] == b[0] == cp.TABLE_HEADER
    assert len(a) == len(b) == len(BUILTIN_PRESET_KEYS) + 1
    for ra, rb in zip(a[1:], b[1:]):
        assert (ra[0], ra[1], ra[3], ra[4]) == (rb[0], rb[1], rb[3], rb[4])
        assert ra[2] == ""
        assert rb[2] in ("yes", "no")


def test_the_export_goes_through_from_table_to_the_same_ticks(dlg, tmp_path):
    """MUTATION, proved to land: ``--from-table`` taking every answered row,
    "no" included, as ticked (red)."""
    mpd = _script()
    on, off = _some(dlg)
    dlg.set_ticked(off[1], True)
    out = tmp_path / "round.csv"
    dlg.export_to(out)
    doc = mpd.from_table(out)
    assert set(doc["shown"]) == dlg.ticked()
    assert doc["source"] == mpd.TABLE_SOURCE


def test_the_shipped_beta42_table_reads_the_same_in_the_window_and_the_script(
        dlg):
    """The table on #182 goes through both readers to the same 62."""
    mpd = _script()
    path = ROOT / "docs" / "presets" / \
        "builtin-presets-shown-by-default_beta42.csv"
    doc = mpd.from_table(path)
    for k in BUILTIN_PRESET_KEYS:
        dlg.set_ticked(k, False)
    reading = dlg.import_from(path)
    assert reading.skipped == 0
    assert dlg.ticked() == set(doc["shown"])
    assert len(doc["shown"]) == 62


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def test_export_then_import_restores_the_ticks(dlg, tmp_path):
    """MUTATION, proved to land: ``import_from`` not setting the boxes (red)."""
    on, off = _some(dlg)
    dlg.set_ticked(off[0], True)
    dlg.set_ticked(on[1], False)
    wanted = dlg.ticked()
    out = tmp_path / "t.csv"
    dlg.export_to(out)
    for k in BUILTIN_PRESET_KEYS:
        dlg.set_ticked(k, k not in wanted)       # every box the other way
    assert dlg.ticked() != wanted
    reading = dlg.import_from(out)
    assert dlg.ticked() == wanted
    assert reading.skipped == 0
    assert len(reading.answers) == len(BUILTIN_PRESET_KEYS)


def test_unknown_keys_blank_and_bad_answers_are_reported_and_change_nothing(
        dlg, tmp_path):
    """MUTATIONS, proved to land: an empty answer read as "no" (red: the
    blank row's box is cleared); an unreadable answer read as "no" (red);
    a key ChromIQ does not have raising instead of being skipped (red)."""
    on, off = _some(dlg, 4)
    before = dlg.ticked()
    rows = [cp.TABLE_HEADER,
            ["G", "ticks", "YES", "", off[0]],               # line 2: ticks
            ["G", "clears", "no", "keep me", on[0]],         # line 3: clears
            ["G", "Gone", "yes", "", "__no_such_preset__"],  # line 4: unknown
            ["G", "Blank", "", "", on[1]],                   # line 5: blank
            ["G", "Maybe", "maybe", "", on[2]],              # line 6: invalid
            ["G", "Keyless", "yes", "", ""]]                 # line 7: no key
    reading = dlg.import_from(_write(tmp_path / "e.csv", rows))
    assert dlg.ticked() == (before | {off[0]}) - {on[0]}
    assert on[1] in dlg.ticked() and on[2] in dlg.ticked()
    assert [r[0] for r in reading.unknown] == [4]
    assert [r[0] for r in reading.blank] == [5]
    assert [(r[0], r[3]) for r in reading.invalid] == [(6, "maybe")]
    assert [r[0] for r in reading.no_key] == [7]
    assert reading.skipped == 4
    counts, problems = dlg.import_summary(reading)
    assert "Ticked: 1" in counts and "Unticked: 1" in counts
    assert "Skipped: 4" in counts
    # 185 built-ins, 4 of them named: the rest keep their tick, and say so.
    assert f"left as they were: {len(BUILTIN_PRESET_KEYS) - 4}" in counts
    assert [p.split(":")[0] for p in problems] == [
        "Line 4", "Line 5", "Line 6", "Line 7"]
    assert "__no_such_preset__" in problems[0]
    assert "maybe" in problems[2]
    # The comment rides along to the next export.
    out = tmp_path / "again.csv"
    dlg.export_to(out)
    assert {r[4]: r[3] for r in _rows(out)[1:]}[on[0]] == "keep me"


def test_the_summary_is_shown_and_names_the_problems(dlg, tmp_path):
    """The Import list button: file window, then the summary.

    MUTATION, proved to land: ``_on_import`` skipping
    ``_show_import_summary`` (red: no box)."""
    on, _off = _some(dlg)
    path = _write(tmp_path / "s.csv", [
        cp.TABLE_HEADER, ["G", "x", "yes", "", "__nope__"],
        ["G", "y", "no", "", on[0]]])
    dlg._ask_open_path = lambda: str(path)
    dlg._import_btn.click()
    box = dlg._last_box
    assert box is not None
    info = box.informativeText()
    assert "Ticked: 0" in info and "Unticked: 1" in info
    assert "Skipped: 1" in info
    assert "Line 2: “__nope__”" in info
    assert "OK keeps these ticks" in info
    assert on[0] not in dlg.ticked()
    assert str(path) in dlg._status.text()


def test_a_file_that_is_not_a_table_changes_nothing(dlg, tmp_path):
    """MUTATION, proved to land: ``read_table`` not refusing a header without
    Key (red: no error, the box never shows)."""
    before = dlg.ticked()
    path = _write(tmp_path / "n.csv", [["a", "b"], ["1", "2"]])
    dlg._ask_open_path = lambda: str(path)
    dlg._import_btn.click()
    assert dlg.ticked() == before
    assert dlg._last_box is not None
    assert "not a list of built-in presets" in dlg._last_box.text()


def test_a_spreadsheet_saved_with_semicolons_and_cp1252_is_read(dlg, tmp_path):
    """A spreadsheet in a decimal-comma language saves "CSV" with semicolons,
    and its plain CSV in the Windows code page."""
    on, off = _some(dlg)
    path = tmp_path / "semi.csv"
    with path.open("w", newline="", encoding="cp1252") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(cp.TABLE_HEADER)
        w.writerow(["G", "Größe · x", "Ja", "", off[0]])
        w.writerow(["G", "n", "Nein", "", on[0]])
    reading = dlg.import_from(path)
    assert reading.skipped == 0
    assert off[0] in dlg.ticked() and on[0] not in dlg.ticked()


def test_the_scripts_blank_table_imports_as_all_blank_and_changes_nothing(
        dlg, tmp_path):
    mpd = _script()
    path = tmp_path / "blank.csv"
    mpd.write_table(path)
    before = dlg.ticked()
    reading = dlg.import_from(path)
    assert dlg.ticked() == before
    assert len(reading.blank) == len(BUILTIN_PRESET_KEYS)


# ---------------------------------------------------------------------------
# Import changes only the window: OK applies, Close discards
# ---------------------------------------------------------------------------

def _import_then(tab, path: Path, end: str) -> None:
    done = {}

    def act():
        d = tab._builtin_presets_shown_dialog
        if d is None or not d.isVisible():
            QTimer.singleShot(10, act)
            return
        d._ask_open_path = lambda: str(path)
        d._exec_box = lambda box: done.__setitem__("box", box)
        d._import_btn.click()
        done["ticked"] = d.ticked()
        dog = done["dog"] = QTimer(d)
        dog.setSingleShot(True)
        dog.timeout.connect(lambda: (done.__setitem__("hung", True),
                                     d.done(99)))
        dog.start(3000)
        (d._ok_btn if end == "ok" else d._close_btn).click()

    QTimer.singleShot(0, act)
    tab._open_builtin_presets_shown()
    if "dog" in done:
        done["dog"].stop()
    assert "box" in done and not done.get("hung")
    return done


@pytest.mark.parametrize("end", ["ok", "close"])
def test_import_then_ok_applies_and_import_then_close_discards(
        make_tab, settings, tmp_path, end):
    """MUTATIONS, proved to land: ``import_from`` also calling
    ``store_choices`` (red for "close"); ``import_from`` not setting the
    boxes (red for "ok")."""
    tab = make_tab()
    shown = cp.shown_keys(settings, BUILTIN_PRESET_KEYS)
    hidden = sorted(set(BUILTIN_PRESET_KEYS) - shown)[0]
    visible = sorted(shown)[0]
    path = _write(tmp_path / "k.csv", [
        cp.TABLE_HEADER, ["G", "a", "yes", "", hidden],
        ["G", "b", "no", "", visible]])
    done = _import_then(tab, path, end)
    assert hidden in done["ticked"] and visible not in done["ticked"]
    cb = tab._preset_combo
    if end == "ok":
        assert cp.user_choices(settings) == {hidden: True, visible: False}
        assert not cb.view().isRowHidden(cb.findData(hidden))
        assert cb.view().isRowHidden(cb.findData(visible))
    else:
        assert cp.user_choices(settings) == {}
        assert cp.shown_keys(settings, BUILTIN_PRESET_KEYS) == shown
        assert cb.view().isRowHidden(cb.findData(hidden))


# ---------------------------------------------------------------------------
# The file windows, the name, the buttons
# ---------------------------------------------------------------------------

def test_both_file_windows_open_in_the_chromiq_folder_filtered_to_csv(
        dlg, settings, monkeypatch):
    """MUTATIONS, proved to land: the save window started in the Documents
    folder (red); the open filter "All files (*)" (red)."""
    import ui.widgets as w
    seen = {}
    monkeypatch.setattr(w, "save_file_dialog", lambda *a, **k: (
        seen.__setitem__("save", (a, k)), "")[1])
    monkeypatch.setattr(w, "open_file_dialog", lambda *a, **k: (
        seen.__setitem__("open", (a, k)), "")[1])
    dlg._export_btn.click()
    dlg._import_btn.click()
    root = Path(settings.get("custom_output_path"))
    a, _k = seen["save"]
    assert Path(a[3]) == root / "ChromIQ built-in presets shown.csv"
    assert a[2] == "CSV files (*.csv)"
    a, k = seen["open"]
    assert a[2] == "CSV files (*.csv)"
    assert Path(k["start_dir"]) == root


def test_export_through_the_button_adds_csv_and_says_where(dlg, tmp_path):
    target = tmp_path / "named"
    dlg._ask_save_path = lambda: str(target)
    dlg._export_btn.click()
    written = tmp_path / "named.csv"
    assert written.is_file()
    assert _rows(written)[0] == cp.TABLE_HEADER
    assert str(written) in dlg._status.text()
    assert dlg._status.isVisibleTo(dlg)


def test_export_and_import_sit_bottom_left_and_ok_close_stay_right(
        dlg, qapp):
    """MUTATION, proved to land: the two buttons added after the stretch
    (red: they sit at the right beside OK)."""
    dlg.show()
    qapp.processEvents()

    def rect(b):
        return QRect(b.mapTo(dlg, QPoint(0, 0)), b.size())
    ex, im = rect(dlg._export_btn), rect(dlg._import_btn)
    ok, close = rect(dlg._ok_btn), rect(dlg._close_btn)
    left = dlg.layout().contentsMargins().left()
    assert ex.left() <= left + 2
    assert ex.right() < im.left() < ok.left() < close.left()
    assert im.right() < dlg.width() // 2 < ok.left()
    assert abs(ex.top() - ok.top()) <= 2
    assert not dlg._export_btn.isDefault() and not dlg._import_btn.isDefault()
    assert dlg._ok_btn.isDefault()
    dlg.close()


def test_the_window_says_ok_keeps_an_import_and_close_discards_it(dlg):
    text = dlg._intro.text()
    assert "Export list saves this table as a CSV file" in text
    assert "an imported list is kept only by OK; Close discards it" in text
