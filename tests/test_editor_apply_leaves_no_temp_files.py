"""The editor's Apply staged a whole chart into $TMPDIR and never removed it.

`_save_and_apply` does `tempfile.mkdtemp(prefix="chromiq_apply_")`, lays the
FULL deliverable into it — .ti1, .ti2 and every page TIFF — and hands the folder
to the host, which takes only the .ti1 out. Nothing deleted it, on any of the
five exits. Every press of Apply leaked a multi-page chart's worth of TIFFs.

Driven through the real method with the collaborators stubbed, so each exit
path is actually executed rather than read.
"""
import pathlib
import tempfile

import pytest


def _dirs_now():
    root = pathlib.Path(tempfile.gettempdir())
    return {p for p in root.glob("chromiq_apply_*")}


class _Spec:
    pass


@pytest.fixture
def dlg(qapp, monkeypatch):
    """A real Ti2RelayoutDialog with only the collaborators Apply touches."""
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog

    d = Ti2RelayoutDialog.__new__(Ti2RelayoutDialog)      # no __init__ chrome
    d._spec = _Spec()
    d._basename = "chart"

    class _Grid:
        def count(self):
            return 3

    d._grid = _Grid()

    class _Status:
        def setText(self, _t):
            pass

    d._status = _Status()
    # The three-choice window is not what is under test, and building a real
    # QDialog parented to this bare instance needs the Qt base __init__.
    d._prompt_apply_action = lambda: "overwrite"
    d._default_apply_name = lambda: "edited"
    d._mark_saved = lambda: None
    d._clear_undo_history = lambda: None
    d.accept = lambda: None
    return d


def _run(d, *, write_raises=False, apply_result=True, apply_raises=False,
         monkeypatch=None):
    from PyQt6.QtWidgets import QMessageBox

    def _write(staging, name):
        if write_raises:
            raise RuntimeError("boom")
        (pathlib.Path(staging) / f"{name}.ti1").write_text("x", encoding="utf-8")

    def _apply(staging, name):
        if apply_raises:
            raise RuntimeError("boom")
        return apply_result

    d._write_chart_into = _write
    d._on_apply = _apply
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))
    d._save_and_apply()


@pytest.mark.parametrize("kwargs,label", [
    ({}, "success"),
    ({"apply_result": False}, "host cancelled"),
    ({"write_raises": True}, "layout failed"),
    ({"apply_raises": True}, "apply callback raised"),
])
def test_no_staging_folder_survives_any_exit(dlg, monkeypatch, kwargs, label):
    before = _dirs_now()
    _run(dlg, monkeypatch=monkeypatch, **kwargs)
    leaked = _dirs_now() - before
    assert not leaked, f"{label}: leaked {[p.name for p in leaked]}"


def test_the_host_still_receives_a_usable_chart(dlg, monkeypatch):
    """The cleanup must not run BEFORE the host has read the staged .ti1."""
    from PyQt6.QtWidgets import QMessageBox

    seen = {}

    def _write(staging, name):
        (pathlib.Path(staging) / f"{name}.ti1").write_text("patches", encoding="utf-8")

    def _apply(staging, name):
        ti1 = pathlib.Path(staging) / f"{name}.ti1"
        seen["existed"] = ti1.is_file()
        seen["content"] = ti1.read_text(encoding="utf-8") if ti1.is_file() else None
        return True

    dlg._write_chart_into = _write
    dlg._on_apply = _apply
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    dlg._save_and_apply()

    assert seen["existed"] is True, "the staged chart was deleted before the host read it"
    assert seen["content"] == "patches"
