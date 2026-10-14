"""A fresh read of a measured verification date, stopped part way (Knut, #182
6154440320, 4.3.5 beta 3).

    *"I then started a measurement ("refine / resume..." set to OFF) ... I
    noticed that previous measurements were still showing as overlay ...
    Next I stopped the measurement ... It seems the app thinks I finished
    measurements, even though I stopped at strip E. Previous measurements are
    still showing split view of expected and measured, although I started a
    new measurement without refine / resume."*

Reproduced on screen with his run 2 and the real engine (beta 4 report, M2):
the read itself painted only A to E; the END painted the earlier measurement
of the date over it, and the completion window "Verification Measurement
Saved" came for a sheet 41.7 % read.

THE CAUSE. A verification's readings stay beside the chart until
``_finalize_verification`` files them on their date. ``_on_measure_done``
repainted the overlay before that filing, and outside a session the
selection reads the DATED folder, which still held the measurement being
replaced: all 324 of its patches were painted on top of the session's 135.

THE RULES (UMM §5 and M-REPLACE-COMPLETE: a fresh read replaces the
measurement, the old one goes to ``old/``): the painting after the read is
the filed measurement alone; a read stopped with patches unread is a partial
measurement, handled as a profiling run's is (the log says so, Refine /
resume is ticked so Start carries on, no completion window); a finished read
still gets M-VERIFY-SAVED.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_import_measurement_module import (_PATCHES, _cgats,  # noqa: E402
                                                  _tab, _verify_env)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _setup(tmp_path, qapp, monkeypatch):
    s, fm, ctl, run = _verify_env(tmp_path)
    s.set("chartread_engine", "chromiq")      # the overlay is the engine's
    tab = _tab(s, fm, ctl)
    # A measured date, selected in the bar: the measurement being replaced.
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    ctl.set_verification_id(v.id)
    qapp.processEvents()
    monkeypatch.setattr(tab, "_ask_how_printed", lambda ti3: None)
    saved: list = []
    monkeypatch.setattr(tab, "_show_verification_saved",
                        lambda dst: saved.append(dst))
    events: list = []
    monkeypatch.setattr(tab, "_clear_overlay", lambda: events.append("clear"))

    def paint():
        ti3 = tab._existing_ti3_for_chart()
        events.append(("paint", ti3.read_text(encoding="utf-8")
                       if ti3 is not None else None))
        return True
    monkeypatch.setattr(tab, "_show_overlay_from_existing_ti3", paint)
    # "Show overlay from existing measurement" ticked, as on Knut's screen
    # (set quietly: the box's own handler paints, and is not under test)
    qapp.processEvents()
    for cb in (tab._overlay_cb, tab._m_overlay_cb):
        cb.blockSignals(True)
        cb.setChecked(True)
        cb.blockSignals(False)
    events.clear()
    return tab, run, v, saved, events


def _end_a_fresh_read(tab, run, patches) -> str:
    """What a fresh read leaves beside the verify chart, then the real
    chartread-exit handler."""
    new = _cgats("CTI3", patches)
    run.verify_chart_ti2.with_suffix(".ti3").write_text(new, encoding="utf-8")
    tab._ti1_path = run.verify_chart_ti2
    tab._verify_run = True
    tab._ti3_mtime_before = None
    tab._all_done_shown = len(patches) == len(_PATCHES)
    tab._measure_failed = False
    tab._on_measure_done(0)
    return new


def test_a_stopped_fresh_read_paints_only_its_own_readings(tmp_path, qapp,
                                                         monkeypatch):
    tab, run, v, saved, events = _setup(tmp_path, qapp, monkeypatch)
    old = v.measurement_ti3.read_text(encoding="utf-8")
    try:
        new = _end_a_fresh_read(tab, run, _PATCHES[:4])
    finally:
        tab.deleteLater()
    paints = [e[1] for e in events if isinstance(e, tuple)]
    assert old not in paints, (
        "the end of the read painted the measurement it replaced")
    filed = v.measurement_ti3.read_text(encoding="utf-8")
    assert paints and paints[-1] == filed
    assert "CHROMIQ_VERIFICATION" in filed and new.splitlines()[-2] in filed
    # …and on a cleared preview, not over an earlier painting
    last_paint = max(i for i, e in enumerate(events) if isinstance(e, tuple))
    assert "clear" in events[:last_paint]
    # the earlier measurement of the date is kept
    assert any(p.read_text(encoding="utf-8") == old
               for p in (v.dir / "old").rglob("*.ti3"))


def test_a_stopped_fresh_read_is_partial_not_finished(tmp_path, qapp,
                                                     monkeypatch):
    tab, run, v, saved, events = _setup(tmp_path, qapp, monkeypatch)
    try:
        _end_a_fresh_read(tab, run, _PATCHES[:4])
        log = tab._log.toPlainText()
    finally:
        tab.deleteLater()
    assert saved == [], (
        "a verification stopped with patches unread got the completion window")
    assert "partial readings saved" in log


def test_a_finished_fresh_read_still_says_saved(tmp_path, qapp, monkeypatch):
    tab, run, v, saved, events = _setup(tmp_path, qapp, monkeypatch)
    try:
        new = _end_a_fresh_read(tab, run, _PATCHES)
    finally:
        tab.deleteLater()
    assert saved == [v.measurement_ti3]
    paints = [e[1] for e in events if isinstance(e, tuple)]
    assert paints and paints[-1] == v.measurement_ti3.read_text(encoding="utf-8")
