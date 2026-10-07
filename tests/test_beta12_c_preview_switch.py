"""Beta 12, build C (Basti, 2026-10-08): the preview's indicator is a switch.

* Clicking the indicator (or Space / Enter on it, or ⌘Y / Ctrl+Y in the main
  window) switches the chart preview of Create Chart, Print Chart and Measure
  between "as on paper" (soft-proofed through the run's profile) and "device
  values". The choice is one AppSettings key for the whole app.
* Collapsed the indicator is an icon; on hover (or keyboard focus) it slides
  open to a short line. Without a profile it shows the screen icon and a
  click does nothing.
* Switching is a pixmap swap: both renderings are kept in memory. The
  soft-proof itself is made in memory too, through a colour table filled by
  cctiff, and its pixels are the ones cctiff makes of the whole page.
"""
from __future__ import annotations

import inspect
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from workflow import print_preview as PP

DATA = Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
NAME = "ET8550_EpsPremSG_AdobeRGB_CM_Okt26"


def _page(path: Path, px: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(px, "RGB").save(path)
    return path


def _run(tmp_path, *, profile=True, px=None) -> Path:
    run = tmp_path / NAME / "runs" / "run1"
    run.mkdir(parents=True)
    (run / "meta.json").write_text("{}", encoding="utf-8")
    if profile:
        shutil.copy2(DATA / f"{NAME}.icc", run / f"{NAME}.icc")
    (run / f"{NAME}.ti2").write_text("CTI2\n", encoding="utf-8")
    if px is None:
        px = np.zeros((8, 24, 3), np.uint8)
        px[:, :8] = 255
        px[:, 8:16] = (200, 40, 40)
        px[:, 16:] = 30
    return _page(run / f"{NAME}.tif", px)


def _darkening_runner(cmd, **kw):
    """A stand-in cctiff: the "soft-proof" is the page at half brightness."""
    assert kw.get("timeout"), "every ArgyllCMS call needs a timeout"
    with Image.open(cmd[-2]) as im:
        a = np.asarray(im.convert("RGB")) // 2
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
    yield b
    PP.clear_cache()


@pytest.fixture()
def paper_view(qapp):
    """Every test starts from the default (as on paper) and leaves it so."""
    from ui import tiff_preview as TP
    TP.set_device_values_chosen(False)
    yield TP
    TP.set_device_values_chosen(False)


@pytest.fixture()
def preview(qapp, paper_view, fake_bin, monkeypatch):
    from ui.tiff_preview import TiffPreview
    monkeypatch.setattr(TiffPreview, "_argyll_bin_with",
                        staticmethod(lambda t: fake_bin))
    real = PP.softproof_page
    monkeypatch.setattr(PP, "softproof_page",
                        lambda *a, **k: real(*a, runner=_darkening_runner, **k))
    w = TiffPreview(None)
    w.resize(600, 500)
    w.set_print_preview(True)
    w.show()
    yield w
    w.deleteLater()


def _shown(w) -> np.ndarray:
    img = w._pixmap.toImage().convertToFormat(
        __import__("PyQt6.QtGui", fromlist=["QImage"]).QImage.Format.Format_RGB888)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    a = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine())
    return a[:, :img.width() * 3].reshape(img.height(), img.width(), 3).copy()


# ------------------------------------------------------------ the switch
def test_the_choice_is_one_app_setting_and_defaults_to_paper(paper_view):
    from core.settings import DEFAULTS, AppSettings
    assert DEFAULTS[paper_view.PREVIEW_DEVICE_VALUES_KEY] is False
    paper_view.set_device_values_chosen(True)
    assert AppSettings().get("preview_show_device_values") is True
    assert paper_view.device_values_chosen() is True


def test_the_toggle_switches_the_rendered_preview_and_persists(tmp_path, preview,
                                                               paper_view):
    tif = _run(tmp_path)
    preview.load_tiff([tif])
    preview._update_display()
    v = preview.print_view()
    assert v["switchable"] and not v["device"] and v["icon"] == "paper"
    paper = _shown(preview)
    assert paper[0, 0].tolist() == [127, 127, 127]       # the soft-proof
    assert preview.toggle_print_view()
    assert paper_view.device_values_chosen()              # remembered
    v = preview.print_view()
    assert v["device"] and v["icon"] == "screen" and v["switchable"]
    assert _shown(preview)[0, 0].tolist() == [255, 255, 255]   # device values
    assert preview.toggle_print_view()
    assert not paper_view.device_values_chosen()
    assert np.array_equal(_shown(preview), paper)


def test_switching_back_is_a_swap_not_a_render(tmp_path, preview, monkeypatch):
    tif = _run(tmp_path)
    preview.load_tiff([tif])
    preview._update_display()
    first = preview._pixmap.cacheKey()
    preview.toggle_print_view()
    calls = []
    monkeypatch.setattr(PP, "softproof_page",
                        lambda *a, **k: calls.append(a) or None)
    monkeypatch.setattr(type(preview), "_load_frame",
                        staticmethod(lambda *a, **k: calls.append(a)))
    preview.toggle_print_view()
    assert calls == [], "the kept rendering was made again"
    assert preview._pixmap.cacheKey() == first
    preview.toggle_print_view()                 # and the device values too
    assert calls == []


def test_every_preview_follows_the_choice(tmp_path, preview, paper_view):
    """Create Chart, Print Chart and Measure each have a preview; switching in
    one switches all three."""
    from ui.tiff_preview import TiffPreview
    other = TiffPreview(None)
    other.set_print_preview(True)
    tif = _run(tmp_path)
    for w in (preview, other):
        w.load_tiff([tif])
        w._update_display()
    other.show()
    preview.toggle_print_view()
    assert other.print_view()["device"]
    other.deleteLater()


def test_a_preview_not_on_screen_catches_up_when_shown(tmp_path, preview, qapp):
    """A switch costs the preview on screen, not all three tabs' previews."""
    from ui.tiff_preview import TiffPreview
    hidden = TiffPreview(None)
    hidden.set_print_preview(True)
    tif = _run(tmp_path)
    for w in (preview, hidden):
        w.load_tiff([tif])
        w._update_display()
    preview.toggle_print_view()
    assert not hidden.print_view()["device"]          # not redrawn yet
    hidden.show()
    qapp.processEvents()
    assert hidden.print_view()["device"]
    hidden.deleteLater()


def test_without_a_profile_the_screen_icon_shows_and_a_click_does_nothing(
        tmp_path, preview, paper_view):
    tif = _run(tmp_path, profile=False)
    preview.load_tiff([tif])
    preview._update_display()
    v = preview.print_view()
    assert v["icon"] == "screen" and not v["switchable"]
    assert v["title"] == "Device values, no profile yet"
    assert "a click changes nothing" in v["tooltip"]
    assert preview.toggle_print_view() is False
    assert paper_view.device_values_chosen() is False
    chip = preview._print_chip
    assert chip is not None and chip.isVisibleTo(preview)
    fired = []
    chip.activated.connect(lambda: fired.append(1))   # noqa: test-only slot
    chip._activate()
    assert fired == []


def test_the_tooltip_names_the_shortcut(tmp_path, preview):
    from ui.keyboard_help import keys_for
    tif = _run(tmp_path)
    preview.load_tiff([tif])
    preview._update_display()
    k = keys_for("preview_view")
    tip = preview.print_view()["tooltip"]
    assert f"({k})" in tip.splitlines()[0] and f"press {k}" in tip


# ------------------------------------------------------------ the chip
@pytest.fixture()
def chip(qapp, monkeypatch):
    from ui import print_view_chip as C
    monkeypatch.setattr(C, "reduce_motion", lambda: True)   # no waiting
    c = C.PrintViewChip(None)
    c.set_state(icon=C.ICON_PAPER, title="As on paper",
                hint="click: device values", tooltip="tip", switchable=True)
    c.place(300, 10)
    yield c
    c.deleteLater()


def test_collapsed_it_is_only_the_icon_and_opens_on_hover(chip):
    from PyQt6.QtCore import QEvent, QPointF
    from PyQt6.QtGui import QEnterEvent
    assert chip.width() == chip.height() == chip.collapsed_width()
    chip.enterEvent(QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    assert chip.width() == chip.expanded_width() > chip.collapsed_width() + 60
    assert chip.geometry().right() + 1 == 300           # opens to the left
    chip.leaveEvent(QEvent(QEvent.Type.Leave))
    assert chip.width() == chip.collapsed_width()
    assert chip.geometry().right() + 1 == 300


def test_it_animates_smoothly_unless_motion_is_reduced(qapp, monkeypatch):
    from PyQt6.QtCore import QEasingCurve
    from ui import print_view_chip as C
    monkeypatch.setattr(C, "reduce_motion", lambda: False)
    c = C.PrintViewChip(None)
    c.set_state(icon=C.ICON_PAPER, title="As on paper", hint="click",
                tooltip="", switchable=True)
    c._hovered = True
    c._reconsider()
    assert c._anim.duration() == C.ANIM_MS and 120 <= C.ANIM_MS <= 220
    assert c._anim.easingCurve().type() == QEasingCurve.Type.OutCubic
    assert c._anim.endValue() == c.expanded_width()
    c._anim.stop()
    c.deleteLater()


def test_keyboard_focus_space_and_enter(chip):
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QFocusEvent, QKeyEvent
    assert chip.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert chip.accessibleName() == "As on paper"
    assert chip.accessibleDescription() == "tip"
    fired = []
    chip.activated.connect(lambda: fired.append(1))   # noqa: test-only slot
    for key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
        chip.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key,
                                     Qt.KeyboardModifier.NoModifier))
    assert fired == [1, 1, 1]
    # Tab focus opens it and rings it; a click's focus does neither
    chip.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,
                                  Qt.FocusReason.TabFocusReason))
    assert chip._kb_focus and chip.width() == chip.expanded_width()
    chip.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut,
                                   Qt.FocusReason.TabFocusReason))
    chip.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,
                                  Qt.FocusReason.MouseFocusReason))
    assert not chip._kb_focus and chip.width() == chip.collapsed_width()


@pytest.mark.parametrize("dpr", [1.0, 2.0])
def test_both_icons_draw_at_1x_and_2x(qapp, dpr):
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QColor, QImage, QPainter
    from ui import print_view_chip as C
    for kind in (C.ICON_PAPER, C.ICON_SCREEN):
        img = QImage(int(14 * dpr), int(14 * dpr),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        C.draw_icon(p, kind, QRectF(0, 0, 14, 14), QColor("#f4f2ef"))
        p.end()
        inked = sum(1 for y in range(img.height()) for x in range(img.width())
                    if img.pixelColor(x, y).alpha() > 128)
        assert inked > 12 * dpr * dpr, (kind, dpr, inked)


# ------------------------------------------------------------ the shortcut
def test_cmd_or_ctrl_y_is_registered_and_installed_on_the_window():
    from ui.keyboard_help import BINDINGS, _shortcuts, keys_for
    from ui.main_window import MainWindow
    assert BINDINGS["preview_view"] == "Ctrl+Y"
    src = inspect.getsource(MainWindow._install_shortcuts)
    assert 'sc("preview_view", self._toggle_preview_view)' in src
    # sc() makes a plain QShortcut on the main window: Qt.WindowShortcut
    assert "QShortcut(QKeySequence(BINDINGS[action]), self, activated=slot)" in src
    assert any(k == keys_for("preview_view") for k, _ in _shortcuts())


def test_the_layout_editor_keeps_its_own_redo(qapp):
    """The chart layout editor is a separate window with its own Ctrl+Y."""
    from ui.dialogs import ti2_relayout_dialog as D
    src = inspect.getsource(D)
    assert 'QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._redo)' in src
    from ui.main_window import MainWindow
    assert "ApplicationShortcut" not in inspect.getsource(
        MainWindow._install_shortcuts)


def test_the_shortcut_toggles_the_current_tabs_preview(tmp_path, preview,
                                                       paper_view):
    from types import SimpleNamespace
    from ui.main_window import MainWindow
    tif = _run(tmp_path)
    preview.load_tiff([tif])
    preview._update_display()
    tab = SimpleNamespace(_preview=preview)
    fake = SimpleNamespace(_tabs=SimpleNamespace(currentWidget=lambda: tab))
    assert MainWindow._toggle_preview_view(fake) is True
    assert paper_view.device_values_chosen() and preview.print_view()["device"]
    assert MainWindow._toggle_preview_view(fake) is True
    assert not paper_view.device_values_chosen()
    # a tab without a chart preview: nothing happens
    none = SimpleNamespace(_tabs=SimpleNamespace(
        currentWidget=lambda: SimpleNamespace()))
    assert MainWindow._toggle_preview_view(none) is False


# ------------------------------------------------------------ in memory
def test_no_preview_file_is_left_on_disk(tmp_path, fake_bin, monkeypatch):
    import tempfile
    seen = tmp_path / "temp"
    seen.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(seen))
    tif = _run(tmp_path)
    plan = PP.plan_for_page(tif)
    out = PP.softproof_page(tif, plan, fake_bin, runner=_darkening_runner)
    assert out is not None and out.shape == (8, 24, 3)
    assert list(seen.iterdir()) == []


def _bin():
    from tests.argyll_env import argyll_bin_dir
    b = argyll_bin_dir()
    if b is None or not (b.parent / "ref" / "sRGB.icm").is_file():
        return None
    return b


@pytest.mark.skipif(_bin() is None, reason="needs ArgyllCMS with ref/sRGB.icm")
@pytest.mark.parametrize("through", [False, True])
def test_the_pixels_are_the_ones_cctiff_makes_of_the_whole_page(tmp_path,
                                                                through):
    """The full-quality path the preview used before build C (cctiff over the
    whole page file) and the in-memory path give IDENTICAL pixels."""
    from workflow.cctiff_apply import convert_args
    from workflow.verification_print import intent_letter
    PP.clear_cache()
    b = _bin()
    rng = np.random.default_rng(7)
    px = rng.integers(0, 256, (48, 64, 3), dtype=np.uint8)
    px[:, :8] = 255
    tif = _run(tmp_path, px=px)
    plan = PP.plan_for_page(tif, bin_dir=b)
    srgb = b.parent / "ref" / "sRGB.icm"
    if through:
        plan = PP.PreviewPlan(PP.KIND_THROUGH, profile=plan.profile,
                              intent="perceptual", source_profile=str(srgb))
    exe = str(b / "cctiff")
    src = tif
    if through:
        sent = tmp_path / "sent.tif"
        subprocess.run([exe, *[str(x) for x in convert_args(
            srgb, plan.profile, tif, sent, verbose=False,
            intent=intent_letter("perceptual"))]], check=True, timeout=120,
            capture_output=True)
        src = sent
    whole = tmp_path / "whole.tif"
    subprocess.run([exe, "-f", "T", "-i", "r", str(plan.profile), "-i", "r",
                    str(srgb), str(src), str(whole)], check=True, timeout=120,
                   capture_output=True)
    expected = np.asarray(Image.open(whole).convert("RGB"))
    got = PP.softproof_page(tif, plan, b)
    assert got is not None and np.array_equal(got, expected)
    PP.clear_cache()
