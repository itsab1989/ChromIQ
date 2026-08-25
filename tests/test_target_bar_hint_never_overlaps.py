"""The help sentence must not sit on top of the run buttons.

Basti, on signing off the sentence moving below the row: *"just make sure it
does not overlap with the buttons to restore, duplicate and delete in the app
styling the user would see"*.

IT ALREADY DID, and had been shipping that way. Measured across window widths
900-1675 px on v4.1.3-beta.15: 60 overlaps with those six widgets and 8 widths
where the sentence itself was clipped. The row reported a height of 16 px while
holding 34 px children, so the sentence was placed at y=18 — inside the band
the buttons occupy.
"""
import pathlib
import tempfile

import pytest

_BUTTONS = ("_restore_btn", "_duplicate_btn", "_delete_btn",
            "_restore_tip", "_duplicate_tip", "_delete_tip")


@pytest.fixture
def bar_and_window(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    from ui.measurement_target_bar import MeasurementTargetBar

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    w = MainWindow(s)
    w.show()
    qapp.processEvents()
    bar = getattr(w, "_target_ctl_bar", None) or w.findChild(MeasurementTargetBar)
    assert bar is not None, "no target bar found"
    yield bar, w, qapp
    w.close()


def _sweep(bar, w, qapp, lo=900, hi=1700, step=25):
    overlaps, clipped, seen = [], [], 0
    for width in range(lo, hi, step):
        w.resize(width, 900)
        qapp.processEvents()
        hint = bar._hint
        if not hint.isVisible():
            continue
        seen += 1
        hr = hint.geometry()
        for name in _BUTTONS:
            b = getattr(bar, name, None)
            if b is None or not b.isVisible():
                continue
            if hr.intersects(b.geometry()):
                overlaps.append((width, name))
        if hint.heightForWidth(hr.width()) > hr.height() + 1:
            clipped.append(width)
    return overlaps, clipped, seen


def test_the_hint_never_covers_the_run_buttons(bar_and_window):
    bar, w, qapp = bar_and_window
    overlaps, _clipped, seen = _sweep(bar, w, qapp)
    assert seen > 20, f"the sentence was visible at only {seen} widths — the "\
                      "sweep proves nothing"
    assert not overlaps, (
        f"the help sentence covers a run button at {len(overlaps)} width/widget "
        f"combinations, e.g. {overlaps[:4]}")


def test_the_hint_is_never_clipped(bar_and_window):
    """It asks for the height its wrapped text needs, and gets it."""
    bar, w, qapp = bar_and_window
    _overlaps, clipped, seen = _sweep(bar, w, qapp)
    assert seen > 20
    assert not clipped, (
        f"the sentence is cut off at {len(clipped)} widths: {clipped[:6]}")


def test_the_sweep_can_actually_see_an_overlap(bar_and_window):
    """Guard the guard.

    A sweep that never finds the sentence, or compares geometries in different
    coordinate systems, would report zero for ever. Move the sentence onto the
    buttons on purpose and the sweep must notice.
    """
    bar, w, qapp = bar_and_window
    w.resize(1400, 900)
    qapp.processEvents()
    if not bar._hint.isVisible():
        pytest.skip("the sentence is not shown in this state")
    victim = next((getattr(bar, n) for n in _BUTTONS
                   if getattr(bar, n, None) is not None
                   and getattr(bar, n).isVisible()), None)
    assert victim is not None, "no run button visible to test against"
    bar._hint.setGeometry(victim.geometry())
    assert bar._hint.geometry().intersects(victim.geometry()), (
        "the comparison cannot detect an overlap even when one is forced")
