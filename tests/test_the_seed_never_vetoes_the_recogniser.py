"""Auto align must not treat its OWN opening rectangle as the user's answer.

`workflow.scan_auto_align.auto_align` takes `current_corners` and refuses any
candidate that is not `IMPROVEMENT_MARGIN` better than the agreement there
("no-better"). That rule exists to protect a placement somebody worked at.

`ScanGridMarquee._seed_corners` draws a rectangle at 90 % of the image the
moment a scan is loaded, and as four numbers it is indistinguishable from a
placement. Measured in the running window on Knut Georg Larsson's own
4157x2939 Wolf Faust scan (beta 8, B8-22):

    the seed              rank agreement 0.9799   Check alignment: worst 0.00 %
    the recogniser's own  rank agreement 0.9839   Check alignment: worst 96.63 %

0.004 apart — inside the 0.02 margin — so Auto align kept the seed and told him
"your own placement is already the closer match, so there was nothing to
improve". He had not made a placement. A Spearman rank correlation over 288
patch luminances cannot resolve half a patch pitch; the placement probe can.
The fix is therefore not a different threshold but not offering the app's own
guess as a rival in the first place.

These guard both halves: the marquee knows whether it has been placed, and the
dialog only hands `auto_align` a quad that has been.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPointF, Qt          # noqa: E402
from PyQt6.QtGui import QImage, QMouseEvent           # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

from core.settings import DEFAULTS                    # noqa: E402
from ui.scan_grid_marquee import GridSpec, ScanGridMarquee   # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self, **overrides):
        import tempfile
        self._store = {**DEFAULTS, **overrides}
        if not self._store.get("custom_output_path"):
            self._store["custom_output_path"] = tempfile.mkdtemp(
                prefix="chromiq-seedveto-")

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


def _marquee_with_a_scan(_app):
    m = ScanGridMarquee()
    m.resize(400, 300)
    m.set_grid(GridSpec([(0.0, 0.0, 0.25, 0.25), (0.25, 0.0, 0.25, 0.25),
                         (0.0, 0.25, 0.25, 0.25), (0.25, 0.25, 0.25, 0.25)],
                        aspect=1.0))
    img = QImage(200, 200, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFF)
    m.set_image(img)
    return m


def test_a_freshly_loaded_scan_is_not_a_placement(_app):
    """Loading a scan seeds a quad. Nobody placed it."""
    m = _marquee_with_a_scan(_app)
    assert len(m.corners_image_px()) == 4        # there IS a quad
    assert m.has_placement()                     # …and it can be read
    assert m.is_placed() is False                # …but it is the app's guess


def test_setting_the_corners_is_a_placement(_app):
    """Restored from settings, carried over from another shot, or written by
    Auto align — all of them arrive through `set_corners`."""
    m = _marquee_with_a_scan(_app)
    m.set_corners([(10.0, 10.0), (190.0, 10.0), (190.0, 190.0), (10.0, 190.0)])
    assert m.is_placed() is True


def test_dragging_a_corner_is_a_placement(_app):
    """The hand on the mouse is the whole point of the rule being protected."""
    m = _marquee_with_a_scan(_app)
    assert m.is_placed() is False
    pos = m._handle_pos(0)
    m.mousePressEvent(QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(pos), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    m.mouseMoveEvent(QMouseEvent(
        QEvent.Type.MouseMove, QPointF(pos.x() + 12, pos.y() + 9),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier))
    m.mouseReleaseEvent(QMouseEvent(
        QEvent.Type.MouseButtonRelease, QPointF(pos.x() + 12, pos.y() + 9),
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier))
    assert m.is_placed() is True


def test_a_new_scan_and_reset_grid_both_take_the_placement_back(_app):
    """Re-seeding is the app guessing again, so the flag must fall back."""
    m = _marquee_with_a_scan(_app)
    m.set_corners([(10.0, 10.0), (190.0, 10.0), (190.0, 190.0), (10.0, 190.0)])
    assert m.is_placed() is True
    m.reset_selection_grid()
    assert m.is_placed() is False
    m.set_corners([(10.0, 10.0), (190.0, 10.0), (190.0, 190.0), (10.0, 190.0)])
    img = QImage(300, 300, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFF)
    m.set_image(img)
    assert m.is_placed() is False


# --------------------------------------------------------------------------
# The dialog half: what actually reaches `auto_align`.
# --------------------------------------------------------------------------
def _drive_auto_align(_app, tmp_path, place_the_grid: bool):
    """Run the real `_on_auto_align` with the recogniser stubbed, and return the
    `current_corners` it was given."""
    import ui.dialogs.scanin_dialog as sd
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    from workflow.standard_targets import bundled_targets_dir, make_test_scan

    d = bundled_targets_dir()
    if d is None or not (d / "SpyderChecker24.cht").is_file():
        pytest.skip("no bundled targets")
    cht = d / "SpyderChecker24.cht"
    tif, cie = make_test_scan(cht, tmp_path)

    dlg = ScannerProfileDialog(
        object(), _FakeSettings(custom_output_path=str(tmp_path)))
    try:
        dlg._mode_standard.setChecked(True)
        i = dlg._target_combo.findData("SpyderChecker24")
        assert i >= 0
        dlg._target_combo.setCurrentIndex(i)
        dlg._std_ref = cie
        dlg._cur_shot()["path"] = tif
        dlg._marquee.set_image(sd._load_scan_qimage(str(tif)))
        assert dlg._marquee.image_size()[0] > 0
        if place_the_grid:
            q = dlg._marquee.corners_image_px()
            dlg._marquee.set_corners([(x + 7.0, y + 3.0) for x, y in q])

        seen = {}

        def fake_auto_align(exe, scan, cht_, cie_, boxes, expected, size,
                            current_corners=None, sample_frac=0.6,
                            search_region=None, **kw):
            seen["current_corners"] = current_corners
            return None                       # refused: nothing else runs

        import workflow.scan_auto_align as saa
        real = saa.auto_align
        saa.auto_align = fake_auto_align
        try:
            dlg._on_auto_align()
            thread = dlg._align_thread
            if thread is not None:
                thread[0].quit()
                thread[0].wait(10000)
            for _ in range(200):
                QApplication.processEvents()
                if "current_corners" in seen:
                    break
        finally:
            saa.auto_align = real
        return seen
    finally:
        dlg.deleteLater()


def test_the_seed_is_never_offered_to_the_recogniser_as_a_rival(_app, tmp_path):
    seen = _drive_auto_align(_app, tmp_path, place_the_grid=False)
    assert "current_corners" in seen, "auto_align was never called"
    assert seen["current_corners"] is None, (
        "Auto align was handed the marquee's own seed as `current_corners`, so "
        "`no-better` can refuse a correct answer in favour of a rectangle "
        "nobody placed — the fault measured on Knut's Wolf Faust scan")


def test_a_placement_the_user_made_still_vetoes(_app, tmp_path):
    """The protection this rule was written for must survive the fix."""
    seen = _drive_auto_align(_app, tmp_path, place_the_grid=True)
    assert "current_corners" in seen, "auto_align was never called"
    assert seen["current_corners"] is not None and len(seen["current_corners"]) == 4
