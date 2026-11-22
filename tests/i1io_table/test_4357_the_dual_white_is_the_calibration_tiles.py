"""4.3.57 (item 34, second part): the dual scan's white names the tile the calibration is made on.

The table owner's patch-by-patch dual try of 22 Nov 2026 (22:17): his calibration place is the
instrument's own tile (Preferences > Beta). The calibration reader was started BEFORE the place
was decided, so it got ``--dual-white table`` (``white_for_place(None)``) while the instrument
lay on its own tile; row 1's reader then asked for the dual tile of ``--dual-white
instrument``, the helper had none, and the row failed (dual_calibration_not_kept) before any
patch move. The simulated helper kept one dual tile whatever the white, so no test saw it; it
now keeps it per white, as the real helper does.

Tested here through the REAL default reader factory (``job._default_reader`` and the app's
``reader.SpotReader``; only the helper process behind it is the simulated one), for both
calibration places, patch by patch and in strips.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_dual_table import STRIP, _job, _ready
from workflow.i1io.table import job as J
from workflow.i1io.table import reader as rd

SPOT = ["-v", "-c", "1", "-p", "chart"]
WHITE = {"own tile": "instrument", "table tile": "table"}


def _real_factory(job, helper, monkeypatch):
    monkeypatch.setattr(rd, "_Proc", helper.proc_class())
    monkeypatch.setattr(rd, "helper_path", lambda pkg=None: Path("/sim/bin/chromiq-chartread"))
    job._reader_factory = J._default_reader


def _whites(helper) -> "list[tuple[str, str]]":
    out = []
    for argv in helper.started:
        if "-p" in argv and "--dual-white" in argv:
            out.append((Path(argv[argv.index("-p") + 1]).name,
                        argv[argv.index("--dual-white") + 1]))
    return out


@pytest.mark.parametrize("args", [SPOT, STRIP], ids=["patch_by_patch", "strips"])
@pytest.mark.parametrize("place", ["own tile", "table tile"])
def test_the_rows_find_the_dual_tile_of_the_calibration(tmp_path, monkeypatch, place, args):
    job, sim, helper, run, p = _job(tmp_path, args=args)
    _real_factory(job, helper, monkeypatch)
    job.calibration_place_preference = place
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok, (r.kind, r.reason, r.detail)
    whites = _whites(helper)
    assert whites, helper.started
    # the calibration reader and every row reader name the same white: the calibration's tile
    assert {w for _n, w in whites} == {WHITE[place]}, whites
    assert whites[0][0] == "c1_spot"
    assert job.cal_place == place


def test_the_place_question_comes_before_the_dual_calibration_reader(tmp_path, monkeypatch):
    job, sim, helper, run, p = _job(tmp_path, args=SPOT)
    _real_factory(job, helper, monkeypatch)
    job.calibration_place_preference = None
    p.script[J.Confirm.CAL_PLACE] = "own tile"
    seen = []

    def on_ask(person, res):
        if res.confirm == J.Confirm.CAL_PLACE:
            seen.append(len(helper.started))
    p.on_ask = on_ask
    _ready(job, p)
    assert seen and all(not ("c1_spot" in " ".join(a)) for a in helper.started[:seen[0]])
    assert _whites(helper)[0] == ("c1_spot", "instrument")
