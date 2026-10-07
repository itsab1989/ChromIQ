"""Beta 12, review C: the preview switch's memory and disk footprint.

Measured on screen (review notes, 2026-10-08): a 10-page 4000-patch A4
300 dpi chart viewed in Create Chart, Print Chart and Measure took the app
from 539 MB to 2.1 GB, because each of the three previews kept up to 400 MB
of pixmaps and every chain a 64 MB colour table. Now ONE bounded pixmap store
serves the whole app and the colour table is sparse: the same walk peaks at
1.16 GB (the beta before the switch: about 0.8 GB), with the same toggle
times. And a ChromIQ killed in the middle of a cctiff call no longer leaves
its temporary folder behind for good.
"""
from __future__ import annotations

import os
import subprocess

import numpy as np
import pytest

from workflow import print_preview as PP


# ------------------------------------------------------------ pixmaps
@pytest.fixture()
def frames(qapp, monkeypatch):
    from ui import tiff_preview as TP
    store = TP._FrameCache()
    monkeypatch.setattr(TP, "_FRAMES", store)
    return store


def _pm(w=100, h=100):
    from PyQt6.QtGui import QPixmap
    pm = QPixmap(w, h)
    pm.fill()
    return pm


def test_the_three_previews_share_one_store(frames, qapp):
    from ui.tiff_preview import TiffPreview
    a, b = TiffPreview(None), TiffPreview(None)
    try:
        assert a._frame_cache is b._frame_cache is frames
    finally:
        a.deleteLater()
        b.deleteLater()


def test_the_store_is_bounded_and_keeps_the_page_on_screen(frames, monkeypatch):
    one = _pm().width() * _pm().height() * (_pm().depth() // 8)
    monkeypatch.setattr(frames, "BUDGET", 3 * one)
    for i in range(10):
        frames.put(("p", i), _pm(), 0.0, "")
    assert frames.nbytes <= 3 * one and len(frames) == 3
    assert ("p", 9) in frames and ("p", 0) not in frames
    # a page larger than the whole budget still keeps both its views
    big = _pm(400, 400)
    frames.put(("big", 0), big, 0.0, "")
    frames.put(("big", 1), big, 0.0, "")
    assert ("big", 0) in frames and ("big", 1) in frames and len(frames) == 2


def test_a_hit_is_the_most_recent(frames, monkeypatch):
    one = _pm().width() * _pm().height() * (_pm().depth() // 8)
    monkeypatch.setattr(frames, "BUDGET", 2 * one)
    frames.put("a", _pm(), 0.0, "")
    frames.put("b", _pm(), 0.0, "")
    assert frames.get("a") is not None
    frames.put("c", _pm(), 0.0, "")
    assert "a" in frames and "b" not in frames


def test_the_budget_is_both_views_of_two_a4_pages_not_hundreds_of_mb():
    from ui.tiff_preview import _FrameCache
    a4_300dpi = 2339 * 3366 * 4
    assert 4 * a4_300dpi <= _FrameCache.BUDGET <= 160 * 2**20


# ------------------------------------------------------------ colour table
def test_the_colour_table_is_sparse_and_exact():
    t = PP._ColourTable()
    rng = np.random.default_rng(3)
    colours = np.unique(rng.integers(0, 1 << 24, 20000, dtype=np.uint32))
    values = (colours * 7 + 3) & 0xFFFFFF
    t.insert(colours[: colours.size // 2], values[: colours.size // 2])
    t.insert(colours[colours.size // 2:], values[colours.size // 2:])
    assert np.array_equal(t.lookup(colours), values)
    others = np.setdiff1d(np.arange(0, 1 << 24, 4099, dtype=np.uint32), colours)
    assert (t.lookup(others) == PP._UNKNOWN).all()
    # 20,000 scattered colours: a few MB, not the flat table's 64 MB
    assert t.nbytes() < 12 * 2**20


def test_a_colour_table_never_outgrows_the_flat_one():
    t = PP._ColourTable()
    every = np.arange(1 << 24, dtype=np.uint32)
    t.insert(every, every)
    assert np.array_equal(t.lookup(every[::997]), every[::997])
    assert t.nbytes() <= (1 << 24) * 4 * 2 + (1 << 18) * 4


def _copy_runner(cmd, **kw):
    from PIL import Image
    assert kw.get("timeout")
    with Image.open(cmd[-2]) as im:
        im.convert("RGB").save(cmd[-1])
    return subprocess.CompletedProcess(cmd, 0, "", "")


def test_prefetch_fills_the_table_and_makes_no_picture(tmp_path, monkeypatch):
    from tests.test_beta12_c_preview_switch import _run
    from core.resource_path import argyll_binary
    b = tmp_path / "argyll" / "bin"
    b.mkdir(parents=True)
    (b / argyll_binary("cctiff")).write_text("", encoding="utf-8")
    (tmp_path / "argyll" / "ref").mkdir()
    (tmp_path / "argyll" / "ref" / "sRGB.icm").write_bytes(b"icc")
    PP.clear_cache()
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        return _copy_runner(cmd, **kw)

    tif = _run(tmp_path)
    plan = PP.plan_for_page(tif)
    assert PP.softproof_page(tif, plan, b, runner=runner, fill_only=True) is None
    assert len(calls) == 1
    out = PP.softproof_page(tif, plan, b, runner=runner)
    assert out is not None and len(calls) == 1      # nothing asked again
    PP.clear_cache()


# ------------------------------------------------------------ disk
def test_a_killed_chromiqs_temp_folder_is_swept(tmp_path):
    dead = subprocess.Popen(["true"])
    dead.wait(timeout=30)
    orphan = tmp_path / f"{PP._TMP_PREFIX}{dead.pid}-abc"
    orphan.mkdir()
    (orphan / "colours.tif").write_bytes(b"x")
    alive = tmp_path / f"{PP._TMP_PREFIX}{os.getpid()}-def"
    alive.mkdir()
    other = tmp_path / "chromiq-something-else-1"
    other.mkdir()
    unnamed = tmp_path / f"{PP._TMP_PREFIX}notapid"
    unnamed.mkdir()
    PP._sweep_orphans(tmp_path)
    assert not orphan.exists()
    assert alive.exists() and other.exists() and unnamed.exists()


def test_the_call_folder_names_its_process(tmp_path, monkeypatch):
    import tempfile
    made = []
    real = tempfile.TemporaryDirectory

    def spy(*a, **k):
        made.append(k.get("prefix", ""))
        return real(*a, **k)

    monkeypatch.setattr(tempfile, "TemporaryDirectory", spy)
    monkeypatch.setattr(PP, "_swept", True)
    from tests.test_beta12_c_preview_switch import _run
    from core.resource_path import argyll_binary
    b = tmp_path / "argyll" / "bin"
    b.mkdir(parents=True)
    (b / argyll_binary("cctiff")).write_text("", encoding="utf-8")
    (tmp_path / "argyll" / "ref").mkdir()
    (tmp_path / "argyll" / "ref" / "sRGB.icm").write_bytes(b"icc")
    PP.clear_cache()
    tif = _run(tmp_path)
    PP.softproof_page(tif, PP.plan_for_page(tif), b, runner=_copy_runner)
    PP.clear_cache()
    assert made == [f"{PP._TMP_PREFIX}{os.getpid()}-"]


# ------------------------------------------------------------ accessibility
def test_the_indicator_is_a_button_a_screen_reader_can_press(qapp):
    """Qt gives every QAbstractButton its accessible Button role and a press
    action that calls click() (PyQt6 does not wrap QAccessible, so the class
    and click() are what a test can hold)."""
    from PyQt6.QtWidgets import QAbstractButton
    from ui.print_view_chip import ICON_PAPER, PrintViewChip
    chip = PrintViewChip(None)
    assert isinstance(chip, QAbstractButton)
    chip.set_state(icon=ICON_PAPER, title="As on paper",
                   hint="click: device values", tooltip="tip", switchable=True)
    assert chip.accessibleName() == "As on paper"
    hits = []
    chip.activated.connect(lambda: hits.append(1))
    chip.click()                     # what the accessible press action does
    assert hits == [1]
    chip.set_state(icon=ICON_PAPER, title="Device values, no profile yet",
                   hint="", tooltip="tip", switchable=False)
    chip.click()
    assert hits == [1]                       # nothing to switch to
    chip.deleteLater()


def test_the_open_chip_never_runs_past_the_image_area(qapp):
    """The French line is 300 px; the image area is 316 px at the window's
    minimum size and narrower when the splitter is dragged. The hint goes
    first, then the title is elided; the icon stays."""
    from ui.print_view_chip import ICON_PAPER, PrintViewChip
    chip = PrintViewChip(None)
    chip.set_state(icon=ICON_PAPER, title="Comme sur papier",
                   hint="clic : valeurs du périphérique", tooltip="t",
                   switchable=True)
    natural = chip.expanded_width()
    chip.set_max_width(natural)
    assert chip.expanded_width() == natural and chip._shown_text()[1]
    chip.set_max_width(natural - 20)
    title, hint = chip._shown_text()
    assert hint == "" and title == "Comme sur papier"
    assert chip.expanded_width() <= natural - 20
    chip.set_max_width(80)
    title, hint = chip._shown_text()
    assert hint == "" and title.endswith("…") and chip.expanded_width() <= 80
    chip.set_max_width(0)                    # no limit
    assert chip.expanded_width() == natural
    chip.deleteLater()


def test_the_preview_tells_the_chip_how_much_room_there_is(qapp):
    import inspect
    from ui.tiff_preview import TiffPreview
    assert "set_max_width" in inspect.getsource(TiffPreview._place_print_chip)


# ------------------------------------------------------------ the key
def test_a_text_field_keeps_ctrl_y_where_it_means_redo(qapp):
    """Where the platform's Redo includes Ctrl+Y (Windows; the offscreen
    platform uses the same table), a focused line edit or text box takes the
    key and the preview switch does not fire. Built the way MainWindow's
    ``sc()`` builds it: a plain QShortcut on the window."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeySequence, QShortcut
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import (QLineEdit, QMainWindow, QPlainTextEdit,
                                 QVBoxLayout, QWidget)
    from ui.keyboard_help import BINDINGS
    redo = [k.toString() for k in QKeySequence.keyBindings(
        QKeySequence.StandardKey.Redo)]
    if BINDINGS["preview_view"] not in redo:
        pytest.skip("Ctrl+Y is not Redo on this platform's key table")
    win = QMainWindow()
    box = QWidget()
    lay = QVBoxLayout(box)
    le, te = QLineEdit(), QPlainTextEdit()
    lay.addWidget(le)
    lay.addWidget(te)
    win.setCentralWidget(box)
    hits = []
    QShortcut(QKeySequence(BINDINGS["preview_view"]), win,
              activated=lambda: hits.append(1))
    win.show()
    win.activateWindow()
    qapp.processEvents()
    try:
        for w in (le, te):
            w.setFocus()
            QTest.keyClick(w, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        assert hits == []
        box.setFocus()
        QTest.keyClick(box, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        assert hits == [1]
    finally:
        win.close()
        win.deleteLater()



def test_reduce_motion_is_asked_again_while_chromiq_runs(monkeypatch):
    from ui import print_view_chip as C
    answers = iter([False, True])
    monkeypatch.setattr(C, "_ask_reduce_motion", lambda: next(answers))
    monkeypatch.setattr(C, "_motion_asked", None)
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    assert C.reduce_motion() is False
    clock[0] += 1
    assert C.reduce_motion() is False          # cached, not asked again
    clock[0] += C._MOTION_TTL_S
    assert C.reduce_motion() is True           # the user turned it on
