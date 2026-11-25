"""The i1Pro 2 dual scan on the i1iO 2 table in the Measure tab's table window (2026-11-18, a
first try): the window passes START's decision to the job, says what will happen on its first
page (M-I1IO-DRIVE-DUAL-ROWS / -SPOT, proposed texts), and a whole dual measurement is read,
saved with M1 / M2 beside it and Build Profile pre-set, in both modes, on the simulated table
and helper. With the dual scan off the window is unchanged (its own tests)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.i1io_table.test_dual_table import dual_setup, long_sheet
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (fixture)
from ui import i1io_table_window as W
from workflow import measurement_messages as M
from workflow.dual_scan import storage as S

STRIP = ["-v", "-c", "1", "-S", "chart"]
SPOT = ["-v", "-c", "1", "-S", "-p", "chart"]


def _open(qtbot, monkeypatch, tmp_path, settings, args, chosen="M1", asking=False):
    orig = W.TableMeasureWindow.__init__

    def init(self, *a, **k):
        k.setdefault("dual", dual_setup(chosen))
        orig(self, *a, **k)
    monkeypatch.setattr(W.TableMeasureWindow, "__init__", init)
    return open_window(qtbot, monkeypatch, tmp_path, settings, asking=asking,
                       sheet=long_sheet(), args=args)


@pytest.mark.parametrize("args,mode", [(STRIP, "rows"), (SPOT, "spot")])
def test_a_whole_dual_measurement_in_the_window(qtbot, monkeypatch, tmp_path, settings, args,
                                                mode):
    win, sim, run, p, saved, finished = _open(qtbot, monkeypatch, tmp_path, settings, args)
    assert p.page() == "prepare"
    msg = M.M_I1IO_DRIVE_DUAL_ROWS if mode == "rows" else M.M_I1IO_DRIVE_DUAL_SPOT
    other = M.M_I1IO_DRIVE_DUAL_SPOT if mode == "rows" else M.M_I1IO_DRIVE_DUAL_ROWS
    assert msg.render(chosen="M1")[1] in win._text.text()
    assert other.render(chosen="M1")[1] not in win._text.text()
    assert p.drive_until("end_of_session") == "end_of_session"
    job = sim.jobs[0]
    assert job.dual is not None and job.dual.chosen == "M1"
    p.press("Save and stop")
    assert saved and saved[0][0] == run.measurement_ti3
    import workflow.i1pro3_conditions as ic
    assert ic.condition_file(run.measurement_ti3, "M1") is not None
    assert ic.condition_file(run.measurement_ti3, "M2") is not None
    assert S.build_from_preset(run.measurement_ti3) == ("M1", "")
    m2 = [ln for ln in sim.sim.received if ln.startswith(";m2")]
    if mode == "rows":
        assert m2 and all(int(ln[11:15], 16) == 132 for ln in m2) and len(m2) % 2 == 0
    else:
        assert m2 == []
    assert sim.sim.violations == []


def test_every_dual_reason_has_a_sentence_of_its_own():
    for rid in ("uv_pass_failed_clean", "uv_pass_wrong_strip", "uv_spot_failed",
                "uv_pass_timing_off", "arrived_beside_the_target",
                "dual_calibration_not_kept", "dual_calibration_failed", "dual_not_available",
                "dual_no_uv_tables", "dual_high_resolution", "dual_needs_a_calibration",
                "dual_conditions_missing", "dual_conditions_not_written",
                "dual_row_patches_too_short",
                "stopped_before_the_uv_pass", "mixed_scan_kind", "mixed_factor",
                "uv_pass_no_uv_light", "no_dual_calibration", "record", "bad_scale"):
        t = W.reason_text(rid)
        assert "diagnostics file of this measurement has the details" not in t, rid
        assert rid not in t and "—" not in t, rid


# ---- the Measure tab's START decision ------------------------------------------------------

class _Tab(SimpleNamespace):
    pass


def _tab(settings, caps, code=None, main=None):
    from ui.tabs.tab_measure import TabMeasure as MeasureTab
    shown = []
    t = _Tab(_settings=settings, _dual_caps=lambda: frozenset(caps),
             _measurement_to_continue=lambda: main, _measure_filter_code=lambda: code,
             _log=SimpleNamespace(appendPlainText=shown.append),
             _show_dual_refusal=lambda r: shown.append(("refused", r)))
    return (lambda: MeasureTab._table_dual_setup(t)), shown


CAPS = {"i1pro2_dual_conditions", "i1pro2_dual_scan", "i1io_table_dual"}


def _on(settings, on=True):
    from workflow import i1pro3_conditions as ic
    from workflow.dual_scan import session as D
    settings.set(ic.SETTING, on)
    settings.set(D.SETTING, on)
    settings.set(D.MODE_SETTING, D.MODE_ALWAYS)   # 4.3.54: 4.3.53's behaviour


def test_start_on_the_table_with_the_dual_scan_off_is_unchanged(settings):
    _on(settings, False)
    f, shown = _tab(settings, CAPS)
    assert f() is None and shown == []


def test_start_on_the_table_with_the_dual_scan_on(settings):
    _on(settings)
    f, shown = _tab(settings, CAPS, code="5")
    setup = f()
    assert setup is not None and setup.chosen == "M1" and setup.scale == pytest.approx(1.156)
    assert "--dual-scale" in setup.args and "-F" not in setup.args
    _on(settings, False)


def test_a_filter_the_dual_scan_has_nothing_for_is_refused_before_anything(settings):
    _on(settings)
    f, shown = _tab(settings, CAPS, code="p")
    assert f() is False and shown == [("refused", "filter_not_dual")]
    _on(settings, False)


def test_an_older_helper_measures_m0_and_says_so(settings):
    _on(settings)
    f, shown = _tab(settings, CAPS - {"i1io_table_dual"})
    assert f() is None and shown and "M0 only" in shown[0]
    _on(settings, False)


def test_the_filter_is_taken_out_of_the_table_args():
    from ui.tabs.tab_measure import TabMeasure as MeasureTab
    assert MeasureTab._args_without_filter(["-v", "-F", "u", "-c", "1", "-Fn", "chart"]) == \
        ["-v", "-c", "1", "chart"]
