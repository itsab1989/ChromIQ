"""4.3.50 fix round (independent review of 20 Nov 2026, SHOULD-2): the dual scan's data guards on
the table that no test protected (the review planted each one away and every test stayed green).

* THE STALE-PAIR DELETION (``TableJob._file_dual_conditions``, both places): a filing removes
  the other kind of pair under the same readings' name, and with no pair filed, any pair under
  that name; but only a file whose own header says ChromIQ wrote it as that condition file
  (``i1pro3_conditions._written_by_us``). A same-named file without those keywords is never
  deleted.
* THE LAMP PASS KEPT ALONE (``TableJob._keep_lamp_pass``, ``dual_rows.cut_lamp_only``): a dual
  row whose UV pass failed keeps its lamp pass as M0 only, but only when its own timing is not
  refused, every window lies on one colour with finite values, and every patch is plausible.
  Each check, failing alone, keeps nothing (the row stays unread, as before 4.3.50).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from tests.i1io_table.test_4350_dual_m1_m2_per_row import _job, _ready, _read_all, \
    _row1_m0_only, UV_FAILS_ON_ROW_1
from workflow import i1pro3_conditions as ic
from workflow.i1io.table import job as J

FOREIGN = "CTI3\n\nDESCRIPTOR \"not ChromIQ's\"\n"


def _foreign_files_at(monkeypatch, dest, names):
    """Just when the filing works out the hash of the run's measurement *dest*, put a file that
    ChromIQ did NOT write (no CHROMIQ_CONDITION_OF, no MEASUREMENT_CONDITION) under each of
    *names(dest, cond)*."""
    real = ic.data_block_hash
    made: list = []
    busy = {"on": False}

    def wrapped(path, *a, **k):
        key = real(path, *a, **k)
        if not busy["on"] and key and Path(path) == Path(dest) and not made:
            busy["on"] = True
            try:
                for cond in ("M1", "M2"):
                    for f in names(Path(path), cond):
                        if f is not None and not f.exists():
                            f.parent.mkdir(parents=True, exist_ok=True)
                            f.write_text(FOREIGN, encoding="utf-8")
                            made.append(f)
            finally:
                busy["on"] = False
        return key
    monkeypatch.setattr(ic, "data_block_hash", wrapped)
    return made


def test_a_partial_filing_never_deletes_a_same_named_complete_pair_it_did_not_write(
        tmp_path, monkeypatch):
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    made = _foreign_files_at(monkeypatch, run.measurement_ti3,
                             lambda dest, c: [ic.sibling_path(dest, c)])
    assert job.save().ok
    assert len(made) == 2 and all(f.is_file() and f.read_text(encoding="utf-8") == FOREIGN for f in made)


def test_with_no_pair_filed_a_same_named_file_it_did_not_write_is_kept(tmp_path, monkeypatch):
    job, sim, helper, run, p, _rep = _job(
        tmp_path, faults={"scan": {"uv_not_ready": True}},
        script={J.Confirm.ROW_FAILED_STRIP: "skip"})
    _ready(job, p)
    assert all(r.ok for r in _read_all(job, p))
    made = _foreign_files_at(monkeypatch, run.measurement_ti3,
                             lambda dest, c: [ic.sibling_path(dest, c),
                                              ic.partial_sibling_path(dest, c)])
    assert job.save().ok
    assert len(made) == 4 and all(f.is_file() and f.read_text(encoding="utf-8") == FOREIGN
                                  for f in made)


# ---- the lamp pass kept alone --------------------------------------------------------------------

def _row1_question(p):
    return [d for _s, c, d, _n, _m in p.asked if c == J.Confirm.ROW_FAILED_STRIP][0]


def test_the_lamp_pass_alone_is_kept_when_every_check_passes(tmp_path):
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    assert _row1_question(p)["m0_kept"] is True


def test_a_lamp_pass_whose_own_timing_is_refused_is_not_kept(tmp_path, monkeypatch):
    real = J.dl.lamp_timing

    def refused(*a, **k):
        return dict(real(*a, **k), lamp_refuse=True)
    monkeypatch.setattr(J.dl, "lamp_timing", refused)
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    assert _row1_question(p)["m0_kept"] is False
    assert not (getattr(job, "_dual_m0_only", None) or [])


def test_a_lamp_pass_with_an_implausible_patch_is_not_kept(tmp_path, monkeypatch):
    real = J.sp.plausible

    def only_here(xyz):
        if sys._getframe(1).f_code.co_name == "_keep_lamp_pass":
            return "implausible (planted by the test)"
        return real(xyz)
    monkeypatch.setattr(J.sp, "plausible", only_here)
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    assert _row1_question(p)["m0_kept"] is False


def test_a_lamp_pass_not_on_one_colour_per_patch_is_not_kept(tmp_path, monkeypatch):
    """The one-colour check of the lamp-only cut: with the limit at zero every window fails."""
    real = J.dl.cut_lamp_only

    def strict(lamp, rows, *a, **k):
        old = J.dl.sp.STRIP_UNIFORMITY_MAX
        J.dl.sp.STRIP_UNIFORMITY_MAX = -1.0
        try:
            return real(lamp, rows, *a, **k)
        finally:
            J.dl.sp.STRIP_UNIFORMITY_MAX = old
    monkeypatch.setattr(J.dl, "cut_lamp_only", strict)
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    assert _row1_question(p)["m0_kept"] is False


def test_a_lamp_pass_with_a_value_that_is_not_a_number_is_not_kept(tmp_path, monkeypatch):
    real = J.sc.read_spec_csv

    def with_nan(path, *a, **k):
        wl, rows = real(path, *a, **k)
        if rows:
            rows = [list(r) for r in rows]
            for r in rows[::3]:                  # one reading in three, so every window has one
                r[3] = math.nan
        return wl, rows
    monkeypatch.setattr(J.sc, "read_spec_csv", with_nan)
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    assert _row1_question(p)["m0_kept"] is False


def test_the_cut_alone_refuses_two_colours_and_a_value_that_is_not_a_number():
    """dual_rows.cut_lamp_only on its own: a window over two colours, and a NaN."""
    from tests.i1io_table.test_dual_table import long_sheet  # noqa: F401 (the sheet's pitch)
    from workflow.i1io.table import dual_rows as dl
    from workflow.i1io.table import scan as sc
    pts = [sc.Patch(str(k + 1), f"A{k + 1}", (1000 - k * 106, 900), half_mm=5.3)
           for k in range(6)]
    lamp = sc.plan_row("t", (1100, 900), (300, 900), 132, pts, dual=True)
    n = lamp.N + 4
    flat = [[0.5] * 36 for _ in range(n)]
    # 4.3.54: a flat stream has no patch edges; the row placement check uses it only as a row of
    # identical patches (uniform_row), which this flat row is
    ok = dl.cut_lamp_only(lamp, flat, uniform_row=True)
    assert ok.ok, ok.reason
    striped = [[0.1 if i % 2 else 0.9] * 36 for i in range(n)]
    assert dl.cut_lamp_only(lamp, striped).reason == "strip_patch_not_on_one_colour"
    nan = [list(r) for r in flat]
    for r in nan:
        r[5] = math.nan
    assert not dl.cut_lamp_only(lamp, nan).ok
