"""Challenge 1 of beta 43, m1 to m3: the gear window's Import list.

* m1 (B8-1162): a file with a cell over 128 KB, or any binary file with no
  line break, raised an uncaught ``_csv.Error`` from `read_table`: no message,
  and the app's excepthook logged it CRITICAL. It is now refused like a file
  without the two columns, with its own reason.
* m2 (B8-1163): a key listed twice (yes, then no) was settled by the last
  row without a word. The summary now names the key, its lines and the answer
  that counts (the last).
* m3 (B8-1164): after a failed import, the status line still read the last
  export's "Saved the list to …". Every outcome now writes it.

Each test names the mutation it was proved red on.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                               # noqa: E402
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


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def dlg(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    (tmp_path / "out").mkdir()
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    d = BuiltinPresetsShownDialog(
        tab._curated_dialog_groups(),
        cp.shown_keys(tab._settings, BUILTIN_PRESET_KEYS), tab,
        facts=builtin_preset_facts(), folder=tab._file_mgr.root_dir())
    d._exec_box = lambda box: setattr(d, "_last_box", box)
    yield d
    d.deleteLater()
    tab.hide()
    tab.deleteLater()
    qapp.processEvents()


def _import(dlg, path: Path) -> None:
    dlg._last_box = None
    dlg._ask_open_path = lambda: str(path)
    dlg._import_btn.click()


def _export_first(dlg, tmp_path) -> Path:
    exp = tmp_path / "exported.csv"
    dlg._ask_save_path = lambda: str(exp)
    dlg._export_btn.click()
    assert "Saved the list to" in dlg._status.text()
    return exp


# ---------------------------------------------------------------------------
# m1
# ---------------------------------------------------------------------------
#: A binary file with no line break and no comma: one "cell" of 300 KB.
BINARY = bytes(b for b in range(256) if b not in b"\n\r,;\"") * 1200


@pytest.mark.parametrize("content", [
    b"\"" + b"x" * 200_000 + b"\n", BINARY,
], ids=["a-cell-over-128-KB", "a-binary-file"])
def test_a_file_that_cannot_be_read_as_a_table_is_refused(content, tmp_path):
    """MUTATION, proved red: `read_table` catching something other than
    ``csv.Error`` (the ``_csv.Error`` escapes)."""
    with pytest.raises(cp.TableError) as err:
        cp.read_table(content, BUILTIN_PRESET_KEYS)
    assert err.value.unreadable


def test_any_binary_file_is_refused_one_way_or_the_other():
    """A binary file with line breaks and commas in it reads as rows of short
    cells, and is refused for having no Key column."""
    with pytest.raises(cp.TableError):
        cp.read_table(bytes(range(256)) * 1200, BUILTIN_PRESET_KEYS)


def test_the_window_says_so_and_changes_nothing(dlg, tmp_path):
    """On the Import list button: the refusal is shown with its own reason,
    no tick moves, and the status line no longer says "Saved the list to".

    MUTATION, proved red: as above (nothing is shown; the error escapes)."""
    _export_first(dlg, tmp_path)
    before = dlg.ticked()
    path = tmp_path / "huge.csv"
    path.write_bytes(b"\"" + b"x" * 200_000 + b"\n")
    _import(dlg, path)
    assert dlg.ticked() == before
    box = dlg._last_box
    assert box is not None
    assert "not a list of built-in presets" in box.text()
    assert "a cell is too long, or it is not a text file" in \
        box.informativeText()


# ---------------------------------------------------------------------------
# m2
# ---------------------------------------------------------------------------
def _rows_with_duplicate(dlg, answers=("yes", "no")) -> "tuple[list, str]":
    key = sorted(BUILTIN_PRESET_KEYS)[0]
    other = sorted(BUILTIN_PRESET_KEYS)[1]
    rows = [cp.TABLE_HEADER,
            ["G", "The name", answers[0], "", key],
            ["G", "Other", "yes", "", other],
            ["G", "The name", answers[1], "", key]]
    return rows, key


def test_a_key_listed_twice_is_reported_with_its_lines_and_the_answer_that_counts(
        dlg, tmp_path):
    """MUTATION, proved red: `read_table` not recording ``duplicates`` (the
    summary says nothing about line 2 and line 4)."""
    rows, key = _rows_with_duplicate(dlg)
    path = tmp_path / "dup.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    reading = cp.read_table(path.read_bytes(), BUILTIN_PRESET_KEYS)
    assert reading.duplicates == [([2, 4], key, "The name", False)]
    assert reading.answers[key] is False           # the last line counts
    _import(dlg, path)
    info = dlg._last_box.informativeText()
    assert ("Lines 2, 4: The name is listed more than once. The last of them "
            "counts, so it is unticked.") in info
    assert key not in dlg.ticked()


def test_the_same_key_twice_ticked_last_says_ticked(dlg, tmp_path):
    rows, key = _rows_with_duplicate(dlg, ("no", "yes"))
    path = tmp_path / "dup2.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, delimiter=";").writerows(rows)
    _import(dlg, path)
    assert ("Lines 2, 4: The name is listed more than once. The last of them "
            "counts, so it is ticked.") in dlg._last_box.informativeText()
    assert key in dlg.ticked()


def test_a_key_listed_once_is_no_duplicate(tmp_path):
    key = sorted(BUILTIN_PRESET_KEYS)[0]
    reading = cp.read_table(
        "\n".join([",".join(cp.TABLE_HEADER), f"G,N,yes,,{key}"]),
        BUILTIN_PRESET_KEYS)
    assert reading.duplicates == []


# ---------------------------------------------------------------------------
# m3
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("content", [
    b"",                                    # empty: "not a table"
    b"a,b\n1,2\n",                          # no Key column
    b"\"" + b"x" * 200_000 + b"\n",         # unreadable
], ids=["empty", "no-key-column", "unreadable"])
def test_a_failed_import_rewrites_the_status_line(dlg, tmp_path, content):
    """MUTATION, proved red: the ``_set_status`` in `_on_import`'s TableError
    branch removed (the export's "Saved the list to …" stays)."""
    _export_first(dlg, tmp_path)
    path = tmp_path / "bad.csv"
    path.write_bytes(content)
    _import(dlg, path)
    status = dlg._status.text()
    assert "Saved the list to" not in status
    assert status == f"{path} was not imported. Nothing was changed."


def test_an_unreadable_file_rewrites_the_status_line(dlg, tmp_path):
    _export_first(dlg, tmp_path)
    _import(dlg, tmp_path / "does-not-exist.csv")
    assert dlg._status.text().endswith("was not imported. Nothing was changed.")


def test_a_failed_export_rewrites_the_status_line(dlg, tmp_path):
    """MUTATION, proved red: the ``_set_status`` in `_on_export`'s OSError
    branch removed."""
    _export_first(dlg, tmp_path)
    target = tmp_path / "no-such-folder" / "list.csv"
    dlg._ask_save_path = lambda: str(target)
    dlg._export_btn.click()
    assert dlg._status.text() == f"The list was not saved to {target}."
