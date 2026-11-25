"""Item 70: the dual row's lamp pass has its own assumed motion start.

Around the single strip's 0.372 s the real dual lamp passes lie 0 to 3.25 readings early, so good
rows were refused for their timing at the early limit (2.5). Their own start, 0.365 s (scan.
DUAL_LAMP_MOTION_START_S), puts them -1.75 to +1.25 from it; the limits are unchanged. The
recordings are private: what they measured is built in here (placement_synth, SHAPED LIKE THEM).
"""
from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tests.i1io_table import placement_synth as S
from tests.i1io_table.test_dual_lamp_timing import _passes
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp
from workflow.i1io.table import strip as stp

ROOT = Path(__file__).resolve().parents[2]
R = sc.READING_S


def _cut(dt_s, pitch=10.0, seed=0, dx=0.0):
    lamp = S.plan(pitch, 132)
    uv = sp.uv_pass_of(lamp)
    row = S.Row(lamp, dt_s=dt_s, dx_mm=dx, seed=seed)
    rows = row.readings.tolist()
    cut = dl.cut_dual(lamp, uv, rows, [[0.01] * 36] * uv.N)
    err = float(np.max(S.de00_spectra(np.array(cut.lamp), row.truth))) if cut.lamp else None
    return cut, dl.lamp_timing(lamp, rows), err


# ---- what is accepted: where the real passes lie -----------------------------------------------

@pytest.mark.parametrize("readings", [0.0, -0.5, -1.0, -1.5, -2.0, -2.5])
@pytest.mark.parametrize("seed", range(4))
def test_a_lamp_pass_where_the_real_ones_start_is_accepted_and_right(readings, seed):
    """*readings* from 0.372 (the true start; the fit counts half a reading earlier)."""
    cut, t, err = _cut(readings * R, seed=seed)
    assert cut.ok, (cut.reason, cut.info.get("placement"))
    assert t["lamp_refuse"] is False, t
    assert err < 0.5


def test_the_early_rows_the_old_start_refused_are_accepted():
    """2.75 readings early of 0.372 in the fit's count: refused around the old start."""
    lamp, uv, lr, ur = _passes(0.0)
    fit = {"best_readings": -2.75, "r2_best": 0.9999, "r2_assumed": 0.99, "spread": 0.5}
    assert dl._judge_lamp(fit)["lamp_refuse"] is True          # the verdict itself is unchanged
    moved = -2.75 - (sc.DUAL_LAMP_MOTION_START_S - sc.MOTION_START_AFTER_LAMP_S) / R
    assert dl._judge_lamp(dict(fit, best_readings=moved))["lamp_refuse"] is False


def test_the_real_passes_lie_inside_both_limits():
    """The recorded extremes (0 and 3.25 readings before 0.372) with at least half a reading."""
    off = (sc.DUAL_LAMP_MOTION_START_S - sc.MOTION_START_AFTER_LAMP_S) / R
    for seen in (0.0, -3.25):
        b = seen - off
        assert -dl.LAMP_FIT_REFUSE_EARLY + 0.5 <= b <= dl.LAMP_FIT_REFUSE_LATE - 0.25, b


# ---- what is refused -------------------------------------------------------------------------

@pytest.mark.parametrize("k", [2.5, 3.0, 4.0, -3.5, -4.0, -6.0])
def test_a_lamp_pass_that_far_from_its_own_start_is_never_accepted(k):
    for seed in range(3):
        cut, t, err = _cut(sc.DUAL_LAMP_MOTION_START_S - sc.MOTION_START_AFTER_LAMP_S + k * R,
                           seed=seed)
        assert not cut.ok or t["lamp_refuse"] or err < 0.5, (k, seed, err)
        if abs(k) >= 4:
            assert not cut.ok or t["lamp_refuse"], (k, seed)


@pytest.mark.parametrize("k", [3.0, 4.0, 6.0, -4.0, -5.0, -6.0])
def test_the_timing_verdict_refuses_it_by_itself(k):
    """Not only the placement check: the streams of the verdict's own tests."""
    lamp, uv, lr, ur = _passes(k)
    assert dl.uv_timing_fit(lamp, uv, lr, ur)["lamp_refuse"] is True


def test_the_limits_are_the_old_ones():
    assert (dl.LAMP_FIT_REFUSE_LATE, dl.LAMP_FIT_REFUSE_EARLY) == (1.75, 2.5)
    assert dl.LAMP_FIT_MIN_GAIN == dl.UV_FIT_MIN_GAIN == 0.005
    assert (dl.UV_FIT_REFUSE_READINGS, sc.UV_MOTION_START_AFTER_TRIGGER_S) == (1.0, 0.236)


def test_a_dark_stream_is_refused():
    lamp = S.plan(10.0, 132)
    uv = sp.uv_pass_of(lamp)
    dark = [[0.0005 + 0.0002 * ((a * 7 + j) % 5) for j in range(36)] for a in range(lamp.N)]
    assert dl.cut_dual(lamp, uv, dark, [[0.01] * 36] * uv.N).ok is False


# ---- nothing else moves --------------------------------------------------------------------------

def test_only_the_dual_lamp_pass_uses_it():
    assert sc.DUAL_LAMP_MOTION_START_S == 0.365 and sc.MOTION_START_AFTER_LAMP_S == 0.372
    src = inspect.getsource(dl)
    assert "sc.MOTION_START_AFTER_LAMP_S" not in src
    for fn in (sc.cut_by_position, sc.windows, sp.strip_windows_ok, stp.cut_row, sc.run_row):
        assert "DUAL_LAMP_MOTION_START_S" not in inspect.getsource(fn), fn
    users = subprocess.run(["grep", "-rl", "DUAL_LAMP_MOTION_START_S", "--include=*.py", "core",
                            "ui", "workflow"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8").stdout.split()
    assert sorted(users) == ["workflow/i1io/table/dual_rows.py", "workflow/i1io/table/job.py",
                             "workflow/i1io/table/scan.py", "workflow/i1io/table/spot.py"]


def test_the_hand_dual_scan_knows_nothing_of_it():
    """The hand scan's timing is the helper's and workflow/dual_scan's: no table constant there."""
    for f in (ROOT / "workflow" / "dual_scan").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "i1io.table" not in text and "MOTION_START" not in text, f.name


def test_no_row_is_read_as_a_dual_row_that_was_not_before(monkeypatch):
    """Every patch length from 7.5 to 13 mm, and rows that start anywhere within a reading."""
    n_new = 0
    for tenths in range(75, 131):
        for run_in in (9.0, 9.2, 9.4):
            lamp = S.plan(tenths / 10.0, 132, run_in=run_in)
            uv = sp.uv_pass_of(lamp)

            def ok():
                few = sp.dual_windows_ok(lamp, uv)
                return few is not None and few >= sc.DUAL_MIN_READINGS
            now = ok()
            with monkeypatch.context() as m:
                m.setattr(sc, "DUAL_LAMP_MOTION_START_S", sc.MOTION_START_AFTER_LAMP_S)
                before = ok()
            with monkeypatch.context() as m:
                # what planning on the new start alone would allow
                m.setattr(sc, "MOTION_START_AFTER_LAMP_S", sc.DUAL_LAMP_MOTION_START_S)
                n_new += ok() and not before
            assert before or not now, (tenths, run_in)
    assert n_new > 0                  # the second start is not there for nothing
