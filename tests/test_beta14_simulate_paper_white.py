"""Beta 14 (Basti, 2026-10-08): Simulate paper white inside the preview chip.

"when the user hovers the label icon and it extends and the proof view is
active could then there be also a button inside that activates and
deactivates simulate paper white? ... the choice should also be remembered."

* While a page is shown as on paper, the OPEN indicator carries a small
  "Paper white" button. It is its own button: it switches the paper white and
  never the view. Not offered over device values nor without a profile.
* On, the run's profile is read absolute colorimetric on the way to the
  screen (only that last step: a chart printed through the profile is still
  converted for the print as before), and the frame the preview draws round
  the page takes the blank paper's colour. Off is the beta-12 look.
* One AppSettings key for the whole app, default off; the three tabs follow
  it; the kept renderings are keyed by it, so switching back is a swap.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from workflow import print_preview as PP

DATA = Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
NAME = "ET8550_EpsPremSG_AdobeRGB_CM_Okt26"


def _run(tmp_path, *, profile=True, sub="a") -> Path:
    run = tmp_path / sub / NAME / "runs" / "run1"
    run.mkdir(parents=True)
    (run / "meta.json").write_text("{}", encoding="utf-8")
    if profile:
        shutil.copy2(DATA / f"{NAME}.icc", run / f"{NAME}.icc")
    (run / f"{NAME}.ti2").write_text("CTI2\n", encoding="utf-8")
    px = np.zeros((8, 24, 3), np.uint8)
    px[:, :8] = 255                      # the page's own blank margin
    px[:, 8:16] = (200, 40, 40)
    px[:, 16:] = 30
    tif = run / f"{NAME}.tif"
    Image.fromarray(px, "RGB").save(tif)
    return tif


def _is_absolute(cmd) -> bool:
    """Whether a cctiff call reads the run's profile absolute colorimetric."""
    return any(cmd[i] == "-i" and cmd[i + 1] == "a" for i in range(len(cmd) - 1))


CALLS: list = []


def _intent_runner(cmd, **kw):
    """A stand-in cctiff: relative halves the page; absolute takes 10 % off
    and tints it, so the paper (device white) comes out (229, 229, 214)."""
    assert kw.get("timeout"), "every ArgyllCMS call needs a timeout"
    CALLS.append(list(cmd))
    with Image.open(cmd[-2]) as im:
        a = np.asarray(im.convert("RGB")).astype(np.float64)
    if _is_absolute(cmd):
        a = a * np.array([0.9, 0.9, 0.84])
    else:
        a = a // 2
    Image.fromarray(a.astype(np.uint8), "RGB").save(cmd[-1])
    return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture()
def fake_bin(tmp_path):
    from core.resource_path import argyll_binary
    b = tmp_path / "argyll" / "bin"
    b.mkdir(parents=True)
    (b / argyll_binary("cctiff")).write_text("", encoding="utf-8")
    (tmp_path / "argyll" / "ref").mkdir()
    (tmp_path / "argyll" / "ref" / "sRGB.icm").write_bytes(b"icc")
    PP.clear_cache()
    CALLS.clear()
    yield b
    PP.clear_cache()


@pytest.fixture()
def views(qapp):
    """Every test starts from the defaults (as on paper, paper white off)
    and leaves them so."""
    from ui import tiff_preview as TP
    TP.set_device_values_chosen(False)
    TP.set_paper_white_chosen(False)
    yield TP
    TP.set_device_values_chosen(False)
    TP.set_paper_white_chosen(False)


@pytest.fixture()
def make_preview(qapp, views, fake_bin, monkeypatch):
    from ui.tiff_preview import TiffPreview
    monkeypatch.setattr(TiffPreview, "_argyll_bin_with",
                        staticmethod(lambda t: fake_bin))
    real_page, real_paper = PP.softproof_page, PP.paper_colour
    monkeypatch.setattr(PP, "softproof_page",
                        lambda *a, **k: real_page(*a, runner=_intent_runner, **k))
    monkeypatch.setattr(PP, "paper_colour",
                        lambda *a, **k: real_paper(*a, runner=_intent_runner, **k))
    made = []

    def make(show=True):
        w = TiffPreview(None)
        w.resize(600, 500)
        w.set_print_preview(True)
        if show:
            w.show()
        made.append(w)
        return w
    yield make
    for w in made:
        w.deleteLater()


def _shown(w) -> np.ndarray:
    from PyQt6.QtGui import QImage
    img = w._pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    a = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine())
    return a[:, :img.width() * 3].reshape(img.height(), img.width(), 3).copy()


def _loaded(make, tif, show=True):
    w = make(show)
    w.load_tiff([tif])
    w._update_display()
    return w


# ------------------------------------------------------------ the setting
def test_the_setting_defaults_to_off_and_is_remembered(views):
    from core.settings import DEFAULTS, AppSettings
    assert views.PREVIEW_PAPER_WHITE_KEY == "preview_simulate_paper_white"
    assert DEFAULTS["preview_simulate_paper_white"] is False
    assert views.paper_white_chosen() is False
    views.set_paper_white_chosen(True)
    assert AppSettings().get("preview_simulate_paper_white") is True
    assert views.paper_white_chosen() is True
    # read back from the store, not only from the module's memory
    views._PAPER_WHITE_CHOSEN = None
    assert views.paper_white_chosen() is True


# ------------------------------------------------------------ the chain
def test_the_chain_and_its_cache_key_carry_the_flag(tmp_path, fake_bin):
    from dataclasses import replace
    prof = tmp_path / "p.icc"
    prof.write_bytes(b"icc")
    plan = PP.PreviewPlan(PP.KIND_RAW, profile=prof)
    off = PP.chain_key(plan, fake_bin)
    on = PP.chain_key(replace(plan, paper_white=True), fake_bin)
    assert off != on and on[:len(off)] == off
    # plan_for_page decides how the page PRINTS: it never sets the flag
    assert PP.PreviewPlan(PP.KIND_RAW).paper_white is False


def test_only_the_print_to_screen_step_becomes_absolute(tmp_path, fake_bin):
    """A verification chart printed through the profile: the print's own
    conversion is unchanged, the last step reads the profile absolute."""
    from dataclasses import replace
    src = tmp_path / "sRGB-source.icc"
    src.write_bytes(b"icc")
    tif = _run(tmp_path)
    plan = PP.PreviewPlan(PP.KIND_THROUGH, profile=tif.with_suffix(".icc"),
                          intent="relative", source_profile=str(src))
    calls = {}
    for pw in (False, True):
        CALLS.clear()
        PP._cctiff_colours(np.array([0xFFFFFF, 0x102030], np.uint32),
                           replace(plan, paper_white=pw), fake_bin,
                           _intent_runner)
        calls[pw] = list(CALLS)
    assert len(calls[False]) == len(calls[True]) == 2
    first_off, first_on = calls[False][0], calls[True][0]
    # the print's conversion: the same arguments either way (temp names aside)
    assert first_off[:-2] == first_on[:-2] and not _is_absolute(first_on)
    assert not _is_absolute(calls[False][1]) and _is_absolute(calls[True][1])
    last = calls[True][1]
    i = last.index(str(plan.profile))
    assert last[i - 2:i] == ["-i", "a"]                 # the run's profile
    assert last[i + 1:i + 3] == ["-i", "r"]             # the screen, relative


def test_the_paper_colour_is_the_printers_blank_white(tmp_path, fake_bin):
    tif = _run(tmp_path)
    plan = PP.PreviewPlan(PP.KIND_THROUGH, profile=tif.with_suffix(".icc"),
                          intent="perceptual", source_profile="/nowhere.icc")
    rgb = PP.paper_colour(plan, fake_bin, runner=_intent_runner)
    # the printer's device white straight through the profile, absolute:
    # no source conversion, even for a chart printed through the profile
    assert rgb == (229, 229, 214)
    assert len(CALLS) == 1 and _is_absolute(CALLS[0])
    assert PP.paper_colour(plan, fake_bin, runner=_intent_runner) == rgb
    assert len(CALLS) == 1, "asked again: the paper colour is kept in memory"


# ------------------------------------------------------------ the preview
def test_switching_changes_the_page_and_the_frame_and_not_the_view(
        tmp_path, make_preview, views):
    from PyQt6.QtGui import QColor
    w = _loaded(make_preview, _run(tmp_path))
    v = w.print_view()
    assert not v["device"] and v["paper_white"] is False
    assert _shown(w)[0, 0].tolist() == [127, 127, 127]          # relative
    assert w._frame_color == QColor(255, 255, 255)
    assert w.set_paper_white(True)
    assert views.paper_white_chosen() and not views.device_values_chosen()
    v = w.print_view()
    assert not v["device"] and v["paper_white"] is True
    # the page's own blank margin and the frame are the same paper colour
    assert _shown(w)[0, 0].tolist() == [229, 229, 214]
    assert w._frame_color == QColor(229, 229, 214)
    assert w.set_paper_white(False)
    assert _shown(w)[0, 0].tolist() == [127, 127, 127]
    assert w._frame_color == QColor(255, 255, 255)
    assert not views.device_values_chosen()


def test_the_frame_keeps_its_width_so_the_page_does_not_move(
        tmp_path, make_preview):
    w = _loaded(make_preview, _run(tmp_path))
    before = w._border_px(300.0)
    w.set_paper_white(True)
    assert w._frame_is_paper is False                   # no pinned border
    assert w._border_px(300.0) == before


def test_the_kept_renderings_are_keyed_by_it_and_switching_back_is_a_swap(
        tmp_path, make_preview, monkeypatch):
    from ui.tiff_preview import frame_cache
    frame_cache().clear()
    w = _loaded(make_preview, _run(tmp_path))
    off_px = w._pixmap.cacheKey()
    w.set_paper_white(True)
    on_px = w._pixmap.cacheKey()
    keys = [k for k in frame_cache()._d if k and k[0] == "proof"]
    assert len(keys) == 2 and keys[0] != keys[1]
    assert sum("paper-white" in k[-1] for k in keys) == 1
    calls = []
    monkeypatch.setattr(PP, "softproof_page",
                        lambda *a, **k: calls.append(a) or None)
    w.set_paper_white(False)
    assert w._pixmap.cacheKey() == off_px
    w.set_paper_white(True)
    assert w._pixmap.cacheKey() == on_px
    assert calls == [], "a kept rendering was made again"
    assert frame_cache().nbytes <= frame_cache().BUDGET


def test_not_offered_over_device_values(tmp_path, make_preview, views):
    w = _loaded(make_preview, _run(tmp_path))
    w.toggle_print_view()                                # device values
    v = w.print_view()
    assert v["device"] and v["paper_white"] is None
    assert w.set_paper_white(True) is False
    assert views.paper_white_chosen() is False
    chip = w._print_chip
    assert chip.paper_white() is None
    chip._hovered = True
    chip._reconsider()
    assert not chip.paper_white_button().isVisibleTo(chip)


def test_not_offered_without_a_profile(tmp_path, make_preview, views):
    views.set_paper_white_chosen(True)                   # even when chosen
    w = _loaded(make_preview, _run(tmp_path, profile=False))
    v = w.print_view()
    assert v["device"] and not v["switchable"] and v["paper_white"] is None
    assert w._print_chip.paper_white() is None
    assert w._frame_color.name() == "#ffffff"
    assert w.set_paper_white(False) is False


def test_device_values_while_it_is_on_show_the_plain_page(
        tmp_path, make_preview, views):
    from PyQt6.QtGui import QColor
    views.set_paper_white_chosen(True)
    w = _loaded(make_preview, _run(tmp_path))
    assert w._frame_color == QColor(229, 229, 214)
    w.toggle_print_view()
    assert _shown(w)[0, 0].tolist() == [255, 255, 255]
    assert w._frame_color == QColor(255, 255, 255)
    assert views.paper_white_chosen()                    # still remembered


def test_every_preview_follows_the_choice(tmp_path, make_preview):
    """Create Chart, Print Chart and Measure each have a preview."""
    from PyQt6.QtGui import QColor
    tif = _run(tmp_path)
    a, b = _loaded(make_preview, tif), _loaded(make_preview, tif)
    a.set_paper_white(True)
    assert b.print_view()["paper_white"] is True
    assert b._frame_color == QColor(229, 229, 214)
    assert b._print_chip.paper_white() is True
    b.set_paper_white(False)
    assert a.print_view()["paper_white"] is False
    assert a._print_chip.paper_white() is False


def test_a_preview_not_on_screen_catches_up_when_shown(tmp_path, make_preview,
                                                       qapp):
    tif = _run(tmp_path)
    shown = _loaded(make_preview, tif)
    hidden = _loaded(make_preview, tif, show=False)
    shown.set_paper_white(True)
    assert hidden.print_view()["paper_white"] is False   # not redrawn yet
    hidden.show()
    qapp.processEvents()
    assert hidden.print_view()["paper_white"] is True


def test_the_words_say_what_is_shown(tmp_path, make_preview):
    from workflow import measurement_messages as MM
    w = _loaded(make_preview, _run(tmp_path))
    chip = w._print_chip
    btn = chip.paper_white_button()
    assert btn.accessibleName() == MM._PREVIEW_PAPER_WHITE_NAME
    assert btn.toolTip() == MM._PREVIEW_PAPER_WHITE_TIP_OFF
    assert chip.accessibleName() == MM._PREVIEW_CHIP_PAPER
    assert "paper shown as white" in chip.toolTip()
    w.set_paper_white(True)
    assert btn.toolTip() == MM._PREVIEW_PAPER_WHITE_TIP_ON
    assert chip.accessibleName() == MM._PREVIEW_CHIP_PAPER_WHITE_ON
    assert "paper white simulated" in chip.toolTip()
    assert "paper shown as white" not in chip.toolTip()
    assert chip.title() == MM._PREVIEW_CHIP_PAPER       # the short line stays


# ------------------------------------------------------------ the chip
@pytest.fixture()
def chip(qapp, monkeypatch):
    from PyQt6.QtWidgets import QLineEdit, QWidget
    from ui import print_view_chip as C
    monkeypatch.setattr(C, "reduce_motion", lambda: True)
    host = QWidget()
    host.resize(500, 200)
    before = QLineEdit(host)
    c = C.PrintViewChip(host)
    after = QLineEdit(host)
    after.move(0, 120)
    c.set_state(icon=C.ICON_PAPER, title="As on paper",
                hint="click: device values", tooltip="tip", switchable=True,
                paper_white=False, paper_label="Paper white",
                paper_name="Simulate paper white", paper_tip="pw tip")
    c.place(480, 10)
    host.show()
    host.activateWindow()
    qapp.processEvents()
    c.host_before, c.host_after = before, after
    yield c
    host.deleteLater()


def test_the_button_shows_only_while_the_chip_is_open(chip):
    btn = chip.paper_white_button()
    assert not btn.isVisibleTo(chip)
    chip._hovered = True
    chip._reconsider()
    assert btn.isVisibleTo(chip)
    # it sits inside the open pill, left of the words
    assert 0 <= btn.x() and btn.geometry().right() < chip.width() - 28
    assert chip.expanded_width() > btn.width() + 100
    chip._hovered = False
    chip._reconsider()
    assert not btn.isVisibleTo(chip)


def test_a_click_on_the_button_never_switches_the_view(chip, qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    got = []
    chip.activated.connect(lambda: got.append("view"))  # noqa: test-only slot
    chip.paperWhiteToggled.connect(lambda on: got.append(on))  # noqa: test-only
    chip._hovered = True
    chip._reconsider()
    QTest.mouseClick(chip.paper_white_button(), Qt.MouseButton.LeftButton)
    QTest.mouseClick(chip.paper_white_button(), Qt.MouseButton.LeftButton)
    assert got == [True, False]
    # and a click does not take the keyboard (it would hold the chip open)
    assert not chip.paper_white_button().hasFocus()


def test_tab_reaches_it_from_the_chip_and_space_switches_it(chip, qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    got = []
    chip.activated.connect(lambda: got.append("view"))  # noqa: test-only slot
    chip.paperWhiteToggled.connect(lambda on: got.append(on))  # noqa: test-only
    btn = chip.paper_white_button()
    assert btn.focusPolicy() == Qt.FocusPolicy.TabFocus
    chip.host_before.setFocus()
    qapp.processEvents()
    QTest.keyClick(chip.host_before, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert QApplication.focusWidget() is chip and chip.is_open()
    QTest.keyClick(chip, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert QApplication.focusWidget() is btn
    assert chip.is_open() and chip.width() == chip.expanded_width()
    QTest.keyClick(btn, Qt.Key.Key_Space)
    assert got == [True] and btn.isChecked()
    QTest.keyClick(btn, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert QApplication.focusWidget() is chip.host_after
    assert not chip.is_open() and not btn.isVisibleTo(chip)


def test_not_offered_on_a_chip_that_cannot_switch(chip):
    from ui import print_view_chip as C
    chip.set_state(icon=C.ICON_SCREEN, title="Device values, no profile yet",
                   hint="", tooltip="", switchable=False, paper_white=False,
                   paper_label="Paper white")
    assert chip.paper_white() is None
    chip._hovered = True
    chip._reconsider()
    assert not chip.paper_white_button().isVisibleTo(chip)


@pytest.mark.parametrize("room", [400, 316, 250, 180, 140, 110, 80])
def test_the_open_chip_never_leaves_the_image_area(chip, room):
    """Beta-14 review: the button made the open chip wider than the room it
    may open to (159 px in 110), the beta-12 review C fault again, and kept
    the button beside a title elided to one letter. The hint goes first, then
    the button, and only then is the title elided."""
    from PyQt6.QtGui import QFontMetrics
    btn = chip.paper_white_button()
    chip.set_state(icon="paper", title="Comme sur papier",
                   hint="clic : valeurs du périphérique", tooltip="",
                   switchable=True, paper_white=True,
                   paper_label="Blanc du papier")
    chip.set_max_width(room)
    chip._hovered = True
    chip._reconsider()
    title, _hint = chip._shown_text()
    assert chip.expanded_width() <= room
    if btn.isVisibleTo(chip):
        assert title == "Comme sur papier"           # never beside an elided title
        assert btn.x() >= 0
    else:
        fm = QFontMetrics(chip._font())
        assert (chip._paper_need() + fm.horizontalAdvance("Comme sur papier")
                + 4 + 22 + 6) > room
    if room >= 316:
        assert btn.isVisibleTo(chip)


def test_the_keyboard_on_the_button_keeps_the_chip_open_when_it_goes(chip,
                                                                     qapp):
    """⌘Y to device values while Tab is on the button: the button goes, the
    keyboard falls back to the chip, and the chip stays open (b14 review: a
    plain setFocus read as a click and closed it under the keyboard)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from ui import print_view_chip as C
    chip.host_before.setFocus()
    qapp.processEvents()
    QTest.keyClick(chip.host_before, Qt.Key.Key_Tab)
    QTest.keyClick(chip, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert QApplication.focusWidget() is chip.paper_white_button()
    chip.set_state(icon=C.ICON_SCREEN, title="Device values",
                   hint="click: as on paper", tooltip="", switchable=True,
                   paper_white=None)
    qapp.processEvents()
    assert QApplication.focusWidget() is chip
    assert chip.is_open()


# ------------------------------------------------------------ the help card
def test_the_help_card_says_how_to_reach_it():
    from ui.keyboard_help import _shortcuts
    rows = [d for _k, d in _shortcuts()]
    assert any("Simulate paper white" in d and "Space" in d for d in rows)
