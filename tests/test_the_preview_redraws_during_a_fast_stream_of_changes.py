"""Review 2 of 4.3.52: THE CHART PREVIEW REDRAWS WHILE CHANGES KEEP COMING.

The project owner watched a table read on the Measure tab: the progress bar moved, the third
aim mark stayed highlighted and every green mark appeared at once at the end of the page. The
preview's STATE followed the read row by row; its REPAINT did not. ``_schedule_refresh``
restarted an 80 ms single-shot timer on every change (a trailing debounce), so while changes
came less than 80 ms apart the redraw was postponed again and again until the stream stopped.

Now a running timer is not restarted: the redraw comes at most 80 ms after the first change of
a burst. The preview is shared by EVERY instrument, so the second test pins that the last change
of a burst is still drawn (what is shown at rest is unchanged).

MUTATION, proven red: ``_schedule_refresh`` restarting the timer again -> 1 redraw in 2 s.
"""
from __future__ import annotations

import time

from PyQt6.QtWidgets import QApplication

from ui import tiff_preview as TP


def _preview(qtbot, tmp_path):
    from PIL import Image
    p = TP.TiffPreview()
    qtbot.addWidget(p)
    tif = tmp_path / "page.tif"
    Image.new("RGB", (400, 400), (230, 230, 230)).save(tif)
    p.resize(420, 420)
    p.load_tiff([tif])
    p.show()
    qtbot.waitExposed(p)
    qtbot.wait(200)
    return p


def _count_redraws(p, monkeypatch):
    calls = []
    real = p._update_display

    def counting():
        calls.append(time.monotonic())
        real()
    # the timer's connection is to the bound method made at construction: reconnect it
    p._refresh_timer.timeout.disconnect()
    p._refresh_timer.timeout.connect(counting)
    return calls


def test_changes_every_20_ms_for_2_s_are_drawn_many_times_not_once(qtbot, tmp_path,
                                                                    monkeypatch):
    p = _preview(qtbot, tmp_path)
    calls = _count_redraws(p, monkeypatch)
    start = time.monotonic()
    while time.monotonic() - start < 2.0:
        p._schedule_refresh()
        QApplication.processEvents()
        time.sleep(0.02)
    during = len(calls)
    qtbot.wait(300)
    # 2 s at one redraw per <= 80 ms (+ the loop's own 20 ms steps) is about 20; a loaded
    # machine gets fewer, never ONE. Before the fix: 0 during the stream, 1 after it.
    assert during >= 8, f"only {during} redraw(s) in 2 s of changes every 20 ms"
    assert len(calls) >= during


def test_the_last_change_of_a_burst_is_still_drawn(qtbot, tmp_path, monkeypatch):
    p = _preview(qtbot, tmp_path)
    calls = _count_redraws(p, monkeypatch)
    p._schedule_refresh()
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=2000)
    last = time.monotonic()
    p._schedule_refresh()                       # one more change after the redraw
    qtbot.waitUntil(lambda: len(calls) == 2, timeout=2000)
    assert calls[1] >= last
    qtbot.wait(TP._REFRESH_DELAY_MS * 3)
    assert len(calls) == 2, "a redraw with no change behind it"
