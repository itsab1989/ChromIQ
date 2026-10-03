""""Replace the stored chart" (Measure tab, a measured verification date and a
DIFFERENT chart loaded) lost the date's stored chart.

`snapshot_chart` copied the new chart over ``<date>/chart/`` and kept nothing:
the chart the date's measurement was made with was gone, and whatever the new
chart did not have stayed behind. A gamut chart's ``-verify-reference.ti3``
then sat beside a regular chart, so Restore Used Chart brought back a
colorimetric reference and Print forced Raw (challenge of 2026-10-03, §4).

Now the old ``chart/`` is moved to ``<date>/old/<stamp>/chart/`` first, in the
same ``<stamp>`` folder the date's old measurement is kept in when the new one
is filed, and the snapshot starts clean. When the attempt ends WITHOUT filing
(any refusal after the snapshot, a read that measured nothing, an import the
date refuses), the old chart is put back, because the date still holds the
measurement made with it.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from tests.test_a_dated_verification_offers_its_own_measurement import (  # noqa: E402
    TI3, _env, _pump)

NEW = TI3.replace("90.0 93.0", "91.5 94.5")
OLD_TI2 = "CTI2\nGAMUT-CHART\n"
NEW_TI2 = "CTI2\nREGULAR-CHART\n"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def quiet(monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    monkeypatch.setattr(TabMeasure, "_maybe_offer_existing_overlay",
                        lambda self: None)
    monkeypatch.setattr(TabMeasure, "_ask_how_printed", lambda self, t: None)
    monkeypatch.setattr(TabMeasure, "_show_verification_saved",
                        lambda self, d: None)
    monkeypatch.setattr(TabMeasure, "_maybe_save_measurement_report",
                        lambda self, d: None)
    # "Replace the stored chart" pressed.
    monkeypatch.setattr(TabMeasure, "_chart_overwrite_choice",
                        lambda self, v: "go")


def _gamut_date_then_regular_chart(tmp_path):
    """A date measured with a gamut chart (its snapshot holds the reference
    .ti3), and a regular chart loaded now."""
    from workflow.verify_chart_snapshot import snapshot_chart
    run, ctl, tab, measured, empty = _env(tmp_path)
    ref = run.verifications_dir / f"{run.verify_stem}-reference.ti3"
    run.verify_chart_ti2.write_text(OLD_TI2, encoding="utf-8")
    ref.write_text(TI3, encoding="utf-8")
    snapshot_chart(measured)
    ref.unlink()                                   # the new chart is regular
    run.verify_chart_ti2.write_text(NEW_TI2, encoding="utf-8")
    ctl.set_verification_id(measured.id)
    _pump()
    return run, ctl, tab, measured, ref.name


def _stored(measured) -> dict:
    d = measured.dir / "chart"
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted(d.iterdir())} if d.is_dir() else {}


def _old_charts(measured):
    return sorted((measured.dir / "old").glob("*/chart"))


# ---------------------------------------------------------------------------
# the file helpers
# ---------------------------------------------------------------------------
def test_set_aside_then_snapshot_leaves_one_clean_chart_and_keeps_the_old(
        tmp_path):
    from workflow.verify_chart_snapshot import (put_back_stored_chart,
                                                set_aside_stored_chart,
                                                snapshot_chart)
    run, ctl, tab, measured, ref_name = _gamut_date_then_regular_chart(tmp_path)
    before = _stored(measured)
    assert ref_name in before
    kept = set_aside_stored_chart(measured, "2026-10-03_120000")
    assert kept == measured.dir / "old" / "2026-10-03_120000" / "chart"
    snapshot_chart(measured)
    now = _stored(measured)
    assert ref_name not in now, (
        "the gamut chart's reference stayed in the regular chart's snapshot")
    assert now[run.verify_chart_ti2.name] == NEW_TI2
    assert {p.name: p.read_text(encoding="utf-8")
            for p in kept.iterdir()} == before, "the old chart was not kept"
    # …and put back exactly, with nothing left in old/.
    assert put_back_stored_chart(measured, kept)
    assert _stored(measured) == before
    assert not (measured.dir / "old").exists()


def test_set_aside_with_nothing_stored_does_nothing(tmp_path):
    from workflow.verify_chart_snapshot import set_aside_stored_chart
    run, ctl, tab, measured, empty = _env(tmp_path)
    assert set_aside_stored_chart(empty, "2026-10-03_120000") is None
    assert not (empty.dir / "old").exists()


# ---------------------------------------------------------------------------
# through the Measure tab
# ---------------------------------------------------------------------------
def test_a_filed_read_keeps_the_old_chart_beside_the_old_measurement(
        qapp, tmp_path, quiet):
    run, ctl, tab, measured, ref_name = _gamut_date_then_regular_chart(tmp_path)
    before = _stored(measured)
    assert tab._snapshot_verification_chart()
    assert ref_name not in _stored(measured)
    # What chartread leaves beside the chart, then the real ending.
    beside = run.verify_chart_ti2.with_suffix(".ti3")
    tab._session_live = True
    tab._ti3_mtime_before = None
    beside.write_text(NEW, encoding="utf-8")
    tab._ti1_path = run.verify_chart_ti2
    tab._verify_run = True
    tab._all_done_shown = True
    tab._measure_failed = False
    tab._on_measure_done(0)
    assert "91.5" in measured.measurement_ti3.read_text(encoding="utf-8")
    assert _stored(measured)[run.verify_chart_ti2.name] == NEW_TI2, \
        "the filed measurement must sit beside the chart it was made with"
    charts = _old_charts(measured)
    assert len(charts) == 1, "the replaced chart was not kept in old/"
    assert {p.name: p.read_text(encoding="utf-8")
            for p in charts[0].iterdir()} == before
    old_ti3 = sorted(charts[0].parent.glob("*.ti3"))
    assert [p.read_text(encoding="utf-8") for p in old_ti3] == [TI3], (
        "the old measurement and the old chart belong in ONE old/<stamp>/")
    assert getattr(tab, "_replaced_chart", None) is None


def test_a_refusal_after_the_snapshot_puts_the_old_chart_back(
        qapp, tmp_path, quiet, monkeypatch):
    """Start, "Replace the stored chart", then a question after the snapshot
    is answered with Cancel (here the bidirectional one): nothing is filed, so
    the date's measurement must keep its own chart."""
    from ui.tabs.tab_measure import TabMeasure
    run, ctl, tab, measured, ref_name = _gamut_date_then_regular_chart(tmp_path)
    before = _stored(measured)
    for guard in ("_blocked_by_new_run", "_blocked_by_missing_chart_file",
                  "_blocked_by_stock_chartread_for_cr30",
                  "_blocked_by_the_instrument_being_in_use",
                  "_blocked_by_unusable_target_instrument"):
        monkeypatch.setattr(TabMeasure, guard, lambda self: False)
    monkeypatch.setattr(TabMeasure, "_verification_guard", lambda self: None)
    seen: list = []
    real = TabMeasure._snapshot_verification_chart

    def spy(self):
        ok = real(self)
        seen.append(_stored(measured))
        return ok
    monkeypatch.setattr(TabMeasure, "_snapshot_verification_chart", spy)
    monkeypatch.setattr(TabMeasure, "_confirm_nonrandom_bidir",
                        lambda self, params: False)
    tab._on_start()
    assert seen and ref_name not in seen[0], \
        "the start never reached the snapshot, so this proves nothing"
    assert _stored(measured) == before, (
        "a start that filed nothing left the date's measurement beside a "
        "chart it was not made with")
    assert not _old_charts(measured)
    assert getattr(tab, "_replaced_chart", None) is None


def test_a_read_that_files_nothing_puts_the_old_chart_back(
        qapp, tmp_path, quiet):
    run, ctl, tab, measured, ref_name = _gamut_date_then_regular_chart(tmp_path)
    before = _stored(measured)
    assert tab._snapshot_verification_chart()
    tab._session_live = True
    tab._ti3_mtime_before = None
    tab._ti1_path = run.verify_chart_ti2
    tab._verify_run = True
    tab._all_done_shown = False
    tab._measure_failed = False
    tab._on_measure_done(1)               # no instrument, nothing read
    assert _stored(measured) == before
    assert not _old_charts(measured)
    assert measured.measurement_ti3.read_text(encoding="utf-8") == TI3


def test_every_ending_settles_the_replaced_chart():
    """The three methods an attempt ends in are wrapped, so a return added to
    any of them later is covered too."""
    from ui.tabs.tab_measure import TabMeasure
    for name in ("_on_start", "_on_measure_done", "_import_into_verification"):
        fn = getattr(TabMeasure, name)
        assert getattr(fn, "__wrapped__", None) is not None, name
        assert fn.__qualname__.endswith(name)
