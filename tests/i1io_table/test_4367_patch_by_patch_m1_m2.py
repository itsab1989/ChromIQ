"""Patch by patch with the dual scan: the row's M1 / M2 are written where the job says.

On a real table (4.3.66) the reading program said {"event": "conditions", "active": false,
"why": "write"} after the first patch of every row: the job named a folder nobody had made.
The other patches of the row were then read for M0 only, about 40 s a row, and the page offered
the same row again. These tests use a helper that writes exactly where the job says (the real
one with its replay instrument; the simulated one no longer makes the folder itself).
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from tests import test_i1pro2_dual_scan_engine as DE
from tests.i1io_table.test_4350_dual_m1_m2_per_row import (
    SPOT, _job, _read_all, _ready, _row_locs)
from tests.i1io_table.test_job_reading import read_page
from tests.i1io_table.test_window import settings  # noqa: F401 (fixture)
from workflow import i1pro3_conditions as ic
from workflow.dual_scan.scale import ScaleChoice
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import job as J
from workflow.i1io.table import spot as sp

pytestmark = pytest.mark.timeout(120)


def _asked(p):
    return [d for _s, c, d, _n, _m in p.asked if c == J.Confirm.ROW_FAILED]


def _moves(sim, n0=0):
    return [ln for ln in sim.received[n0:] if ln.startswith((";m", ";i"))]


# ---- the real helper, started with the job's own arguments ------------------------------------
# (its replay instrument makes dual readings in strips only; patch by patch writes M1 / M2 through
# the same function, cq_cond_write)

def ns_job(setup=None):
    return types.SimpleNamespace(dual=setup, _events=J.TableJob._events,
                                 diag=types.SimpleNamespace(log=lambda *a: None))


def _real_run(tmp_path, monkeypatch, cdir_made_by_the_job: bool):
    if not DE.HELPER.exists():
        pytest.skip("chromiq-chartread not built")
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, truth, _ = DE._chart(tmp_path)
    ch = ScaleChoice.standard()
    setup = dl.DualSetup(tuple(DE.storage.helper_args(ch, "table", "M2")), ch.value, ch.source,
                         "M2", "table")
    folder = tmp_path / "row-1"
    args = (J.TableJob._dual_spot_args(ns_job(setup), folder, "table tile")
            if cdir_made_by_the_job else setup.spot_args(folder / "conditions", "table"))
    with DE.ReplaySession(base, rp, extra_args=["-S", *args]) as s:
        DE._swipe(s)
        first = [e for e in s.events if e.get("event") == "conditions"]
        DE._swipe(s, reversed=True)
        DE._done(s)
    reader = types.SimpleNamespace(proc=types.SimpleNamespace(events=s.events))
    return base.with_suffix(".ti3"), folder, first, reader


def test_the_real_helper_writes_m1_and_m2_where_the_job_says(tmp_path, monkeypatch):
    ti3, folder, first, reader = _real_run(tmp_path, monkeypatch, True)
    assert [e["active"] for e in first] == [True], first
    key = ic.data_block_hash(ti3)
    assert sorted(f.name for f in (folder / "conditions").iterdir()) == [
        f"{key}-M1.ti3", f"{key}-M2.ti3"]
    assert J.TableJob._dual_not_written(ns_job(), reader) is False


def test_without_the_folder_the_real_helper_says_write_after_its_first_save(tmp_path,
                                                                            monkeypatch):
    """What the old arguments did; the job hears exactly this event."""
    ti3, folder, first, reader = _real_run(tmp_path, monkeypatch, False)
    assert first[-1] == {"event": "conditions", "active": False, "why": "write"}
    assert not (folder / "conditions").exists()
    assert J.TableJob._dual_not_written(ns_job(), reader) is True


# ---- the job --------------------------------------------------------------------------------

def test_every_row_patch_by_patch_has_m1_and_m2(tmp_path):
    """Fails with the old folder behaviour: the helper writes only where a folder is."""
    job, sim, helper, run, p, _rep = _job(tmp_path, args=SPOT)
    _ready(job, p)
    rows = read_page(job, p)
    assert all(r.ok and r.detail["row_kind"] == "spot" for r in rows), [r.reason for r in rows]
    assert _asked(p) == []
    recs = [json.loads(f.read_text("utf-8")) for f in job.diag.folder.glob("row-*/*.row.json")]
    assert len(recs) == len(rows) and all(set(r["conditions"]) == {"M1", "M2"} for r in recs)
    assert job.save().ok
    assert ic.m0_only_locs(Path(run.measurement_ti3)) == []


def test_the_calibrations_reader_gets_a_folder_as_well(tmp_path):
    job, sim, helper, run, p, _rep = _job(tmp_path, args=SPOT)
    _ready(job, p)
    cal = [a for a in helper.started if "--dual-table" in a and "-N" not in a]
    assert cal and all(Path(a[a.index("--condition-dir") + 1]).is_dir() for a in cal)


@pytest.mark.parametrize("after", [1, 3])
def test_a_row_whose_m1_m2_cannot_be_written_ends_at_once(tmp_path, after):
    job, sim, helper, run, p, _rep = _job(
        tmp_path, args=SPOT, faults={"no_write_at": (2,), "no_write_after": after},
        script={J.Confirm.ROW_FAILED: "skip"})
    _ready(job, p)
    n0 = len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "skipped"
    asked = _asked(p)
    assert len(asked) == 1 and asked[0]["why"] == J.NOT_WRITTEN and not asked[0]["m0_kept"]
    # exactly as many patches as were read before it was said: no movement more
    assert len(_moves(sim, n0)) == after
    rec = json.loads(next(job.diag.folder.glob("row-*/p1_row1.row.json")).read_text("utf-8"))
    assert rec["why"] == J.NOT_WRITTEN and rec["conditions"] is None
    # today's rule of a row that ended early: the readings made keep their M0
    assert [a["loc"] for a in rec["accepted"]] == _row_locs(job, 1)[::-1][:after]
    assert len(rec["dual_spot_results"]) <= after


def test_it_is_not_read_again_by_itself():
    assert J.NOT_WRITTEN not in sp.READ_AGAIN_BY_ITSELF


def test_the_next_row_is_read_as_always(tmp_path):
    job, sim, helper, run, p, _rep = _job(tmp_path, args=SPOT, faults={"no_write_at": (2,)},
                                          script={J.Confirm.ROW_FAILED: "skip"})
    _ready(job, p)
    rows = _read_all(job, p)
    assert [r.detail["status"] for r in rows] == ["skipped", "read"]
    assert job.save().ok
    main = Path(run.measurement_ti3)
    assert ic.m0_only_locs(main) == _row_locs(job, 1)[-1:]


def test_a_write_that_fails_on_the_last_patch_keeps_the_whole_rows_m0(tmp_path):
    job, sim, helper, run, p, _rep = _job(
        tmp_path, args=SPOT, faults={"no_write_at": (2,), "no_write_after": 10 ** 6},
        script={J.Confirm.ROW_FAILED: "skip"})
    helper.faults["no_write_after"] = len(_row_locs(job, 1))
    _ready(job, p)
    assert p.drive(job.read_row()).ok
    d = _asked(p)[0]
    assert d["why"] == J.NOT_WRITTEN and d["read"] == d["patches"] == len(_row_locs(job, 1))


def test_a_folder_that_cannot_be_made_moves_nothing(tmp_path, monkeypatch):
    job, sim, helper, run, p, _rep = _job(tmp_path, args=SPOT,
                                          script={J.Confirm.ROW_FAILED: "stop"})
    _ready(job, p)
    real = Path.mkdir

    def mkdir(self, *a, **k):
        if self.name == "conditions":
            raise PermissionError("no")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    n0, readers = len(sim.received), len(helper.started)
    r = p.drive(job.read_row())
    assert r.reason == "stopped_after_a_failed_row"
    assert _asked(p)[0]["why"] == J.NOT_WRITTEN
    assert _moves(sim, n0) == [] and len(helper.started) == readers


def test_other_endings_of_the_record_change_nothing(tmp_path):
    """Only why "write" stops the row: a record kept as M0 only goes on as before."""
    ev = [{"event": "conditions", "active": True}, {"event": "conditions", "active": False,
                                                    "why": "record", "kept": True}]
    r = types.SimpleNamespace(proc=types.SimpleNamespace(events=ev))
    assert J.TableJob._dual_not_written(ns_job(), r) is False
    ev.append({"event": "conditions", "active": False, "why": "write"})
    assert J.TableJob._dual_not_written(ns_job(), r) is True


# ---- the window: no "Read it again" where it cannot help --------------------------------------

def _window(qtbot, monkeypatch, tmp_path, settings, faults, args):  # noqa: F811
    from tests.i1io_table.test_dual_table import dual_setup, long_sheet
    from tests.i1io_table.test_window import open_window
    from tests.i1io_table.window_sim import WindowSim
    from ui import i1io_table_window as W
    orig = W.TableMeasureWindow.__init__

    def init(self, *a, **k):
        k.setdefault("dual", dual_setup("M1"))
        orig(self, *a, **k)
    monkeypatch.setattr(W.TableMeasureWindow, "__init__", init)
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sheet=long_sheet(), args=args,
        sim=WindowSim(faults=faults))
    return W, win, sim, run, p, saved


def _labels(win):
    return [b.text().replace("&", "") for b in win._buttons]


def test_the_page_of_a_row_that_cannot_be_written_offers_skip_and_end(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    from workflow import measurement_messages as M
    W, win, sim, run, p, saved = _window(
        qtbot, monkeypatch, tmp_path, settings, {"no_write_at": (3,)},
        ["-v", "-c", "1", "-p", "chart"])
    assert p.drive_until("row_failed") == "row_failed"
    title, body = M.M_I1IO_DRIVE_ROW_M1_M2_NOT_WRITTEN.render(row=1, page=1, why="x")
    assert win._title.text() == title
    assert _labels(win) == ["Skip it", "End this step"]
    assert all(b.isEnabled() for b in win._buttons)
    assert "Read it again" not in body and "as often as" not in body
    p.press("Skip it")
    assert p.drive_until("end_of_session") == "end_of_session"
    p.press("Save and stop")
    main = Path(run.measurement_ti3)
    assert saved and ic.sibling_in_step(main, ic.partial_sibling_path(main, "M1"))


def test_a_row_without_a_known_reason_still_offers_reading_it_again(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    from workflow import measurement_messages as M
    W, win, sim, run, p, saved = _window(
        qtbot, monkeypatch, tmp_path, settings, {"no_conditions_at": (3,)},
        ["-v", "-c", "1", "-p", "chart"])
    assert p.drive_until("row_failed") == "row_failed"
    assert win._title.text() == M.M_I1IO_DRIVE_ROW_M0_ONLY.render(row=1, page=1, why="x")[0]
    assert _labels(win) == ["Read it again", "Skip it", "End this step"]
    assert "as often as" not in M.M_I1IO_DRIVE_ROW_M0_ONLY.body


def test_the_window_shows_the_not_moved_page_for_a_refusal_before_any_move(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    from tests.i1io_table.test_window import open_window
    from tests.i1io_table.window_sim import WindowSim
    from workflow import measurement_messages as M
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False,
        args=["-v", "-c", "1", "chart"], sim=WindowSim())
    sim.sim.c_faults["c4_byte"] = 0xFF
    assert p.drive_until("row_failed_strip") == "row_failed_strip"
    first = M.M_I1IO_DRIVE_ROW_FAILED_STRIP_NOT_MOVED.body.split(".")[0]
    assert first in win._text.text()
    assert "where the strip move ended" not in win._text.text()


def test_the_window_says_the_arm_is_held_after_a_real_move(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    """The direction that matters (safety review S1): the arm moved to the row start and is held."""
    from tests.i1io_table.test_window import open_window
    from tests.i1io_table.window_sim import WindowSim
    from workflow import measurement_messages as M
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False,
        args=["-v", "-c", "1", "chart"], sim=WindowSim(faults={"scan": {"not_ready": True}}))
    assert p.drive_until("row_failed_strip") == "row_failed_strip"
    assert sim.sim.moving is False and sim.jobs[-1]._table.arm_free is False
    body = win._text.text()
    assert M.M_I1IO_DRIVE_ROW_FAILED_STRIP.body.split(".")[0] in body
    assert "did not move the arm" not in body
