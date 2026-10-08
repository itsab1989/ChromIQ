"""Beta 13, b13a (Basti, 2026-10-08, a 13" MacBook Air): on the Print Chart
tab the preview's chip sat about 12 px too high on first show, over the
"PRINT PREVIEW" / project-name header, and only a click moved it to where the
other tabs put it.

Root cause: the chip is anchored to the IMAGE AREA (`_img_label`), but it was
re-placed only from the preview's own resizeEvent. The Print Chart tab's chart
is loaded while the tab is hidden; on the first show the preview's resizeEvent
came BEFORE the header had grown by the file-name line and the 12 px gap under
it, and that growth moved the image area down 13 px without resizing the
preview again. Measured on screen at 1470x850 and 1728x1051: chip top 38,
rule 51, on Print only; 51 after a click. The preview now follows the image
area's own Move and Resize events: one rule, every tab.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from PyQt6.QtCore import QPoint

from workflow import print_preview as PP

DATA = Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
NAME = "ET8550_EpsPremSG_AdobeRGB_CM_Okt26"


def _run(tmp_path) -> Path:
    run = tmp_path / NAME / "runs" / "run1"
    run.mkdir(parents=True)
    (run / "meta.json").write_text("{}", encoding="utf-8")
    shutil.copy2(DATA / f"{NAME}.icc", run / f"{NAME}.icc")
    (run / f"{NAME}.ti2").write_text("CTI2\n", encoding="utf-8")
    px = np.full((40, 60, 3), 200, np.uint8)
    tif = run / f"{NAME}.tif"
    Image.fromarray(px, "RGB").save(tif)
    return tif


def _halving_runner(cmd, **kw):
    assert kw.get("timeout"), "every ArgyllCMS call needs a timeout"
    with Image.open(cmd[-2]) as im:
        a = np.asarray(im.convert("RGB")) // 2
    Image.fromarray(a.astype(np.uint8), "RGB").save(cmd[-1])
    return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture()
def softproof(qapp, tmp_path, monkeypatch):
    from core.resource_path import argyll_binary
    from ui import tiff_preview as TP
    b = tmp_path / "argyll" / "bin"
    b.mkdir(parents=True)
    (b / argyll_binary("cctiff")).write_text("", encoding="utf-8")
    (tmp_path / "argyll" / "ref").mkdir()
    (tmp_path / "argyll" / "ref" / "sRGB.icm").write_bytes(b"icc")
    PP.clear_cache()
    monkeypatch.setattr(TP.TiffPreview, "_argyll_bin_with",
                        staticmethod(lambda t: b))
    real = PP.softproof_page
    monkeypatch.setattr(PP, "softproof_page",
                        lambda *a, **k: real(*a, runner=_halving_runner, **k))
    TP.set_device_values_chosen(False)
    yield TP
    TP.set_device_values_chosen(False)
    PP.clear_cache()


def _pump(qapp, n=6):
    for _ in range(n):
        qapp.processEvents()


def _rule(pv) -> tuple[int, int]:
    """Where the chip belongs: its top RIGHT corner 10 px inside the image
    area's top right corner (less the focus ring), as _place_print_chip says."""
    from ui.print_view_chip import RING
    o = pv._img_label.mapTo(pv, QPoint(0, 0))
    return (o.x() + pv._img_label.width() - 10 + RING, o.y() + 10 - RING)


def _anchor(chip) -> tuple[int, int]:
    g = chip.geometry()
    return (g.right() + 1, g.y())


def test_the_chip_follows_the_image_area_when_the_header_grows(
        qapp, tmp_path, softproof):
    """The mechanism on its own: the image area moves, the preview does not
    resize, and the chip goes with the image area."""
    pv = softproof.TiffPreview(None)
    pv.resize(600, 500)
    pv.set_print_preview(True)
    pv.show()
    pv.load_tiff([_run(tmp_path)])
    pv._update_display()
    _pump(qapp)
    chip = pv._print_chip
    assert chip is not None and chip.isVisible()
    before = pv._img_label.mapTo(pv, QPoint(0, 0)).y()
    pv.set_banner("a second header line")       # the header grows
    _pump(qapp)
    assert pv._img_label.mapTo(pv, QPoint(0, 0)).y() > before
    assert _anchor(chip) == _rule(pv)
    pv.deleteLater()


@pytest.mark.parametrize("size", [(1470, 850), (1728, 1050)])
def test_print_tab_chip_is_right_on_first_show_and_unmoved_by_a_toggle(
        qapp, tmp_path, softproof, size):
    """The Print Chart tab as Basti saw it: the chart is loaded while the tab
    is hidden, then the tab is shown. Before any click the chip must sit where
    the rule puts it, and two toggles (back to the same view) must not move it."""
    from PyQt6.QtWidgets import QStackedWidget, QWidget
    from core.settings import AppSettings
    from ui.tabs.tab_print import TabPrint
    # as in the main window: the tab is a page of a stack, loaded while
    # another page is on screen, then switched to
    stack = QStackedWidget()
    stack.addWidget(QWidget())
    tab = TabPrint(AppSettings())
    stack.addWidget(tab)
    stack.resize(*size)
    stack.show()
    _pump(qapp)
    tab.load_tiffs([_run(tmp_path)])
    _pump(qapp, 12)
    stack.setCurrentWidget(tab)
    _pump(qapp, 12)
    pv = tab._preview
    chip = pv._print_chip
    assert chip is not None and chip.isVisible() and chip.switchable()
    first = chip.geometry()
    assert _anchor(chip) == _rule(pv), (first, _rule(pv))
    chip.click()
    _pump(qapp, 12)
    chip.click()
    _pump(qapp, 12)
    assert chip.geometry() == first
    stack.close()
    stack.deleteLater()


def test_one_placement_rule_for_every_tab():
    """Create Chart, Print Chart and Measure all show the same TiffPreview,
    and the chip is placed in exactly one method, from the image area."""
    import inspect
    from ui import tiff_preview as TP
    src = inspect.getsource(TP.TiffPreview.eventFilter)
    assert "_place_print_chip" in src and "Move" in src and "Resize" in src
    for mod in ("tab_chart", "tab_print", "tab_measure"):
        tab_src = Path(TP.__file__).parent.joinpath("tabs", f"{mod}.py") \
            .read_text(encoding="utf-8")
        assert ".place(" not in tab_src, mod
