"""A CHART OF AN EARLIER ChromIQ, HALF READ, GOES ON WITH ITS OWN DATA (the new i1iO chart layout,
25 Nov 2026): its side file as 4.3.65 wrote it (schema 1, the facts block with its sources), its
recipe without the new marker and asking for sizes the old ChromIQ did not print (6 x 6 mm, printed
8.9 x 7). Continue reads only what is missing, at the places the old side file names, to a complete
measurement; nothing of the chart's files is written again."""
from __future__ import annotations

import json

import pytest

from tests.i1io_table import bed_sim as B
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_job_ending import SECOND, _end
from tests.i1io_table.test_job_reading import read_page, ready_to_read
from tests.i1io_table.test_window_in_the_measure_tab import beta, start, tab  # noqa: F401
from tests.i1io_table.window_person import WindowPerson
from workflow.measurement_state import Ti3State, classify, unread_locations

SPOT = ["-v", "-c", "1", "-p", "chart"]
STRIP = ["-v", "-c", "1", "chart"]


def old_chart(tmp_path):
    """A chart as the old ChromIQ left it on disk: patches of 8.9 x 7 mm printed, 6 x 6 asked."""
    ch = B.with_preview(B.build_chart(tmp_path, count=3 * 25, patch_h=8.9, patch_w=7.0))
    n = len(ch.sheet["pages"][0]["strips"][0]["patches"])
    side = ch.run.i1io_side_file
    doc = json.loads(side.read_text(encoding="utf-8"))
    doc["table_facts"] = {k: {"value": v, "source": "as an old file names it",
                              "confidence": "OURS"} for k, v in doc["table_facts"].items()}
    side.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    stem = ch.run.chart_ti2.name[:-4]
    cj = ch.run.dir / f"{stem}.channels.json"
    d = json.loads(cj.read_text(encoding="utf-8"))
    from workflow.layout_engine.presets import default_recipe
    r = default_recipe("IO2", "A4").to_dict()
    r.pop("i1io_limits", None)
    r.update(patch_w_mm=6.0, patch_h_mm=6.0)
    d["layout"]["recipe"] = r
    cj.write_text(json.dumps(d), encoding="utf-8")
    ch.sheet = json.loads(side.read_text(encoding="utf-8"))
    return ch, n


def _files(ch):
    return {p.name: p.read_bytes() for p in ch.run.dir.iterdir() if p.is_file()
            and p.suffix in (".ti1", ".ti2", ".json", ".tif") and p.name != "meta.json"}


def _half_read(tmp_path, ch, n, opts):
    job, sim, helper, run = B.bed_job(tmp_path, ch, B.Bed(ch.laid()), ask_after_each_step=False)
    assert job.set_options(opts).ok
    p = H.Person(job, sim)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    end, st = _end(job, p, "save")
    assert end.ok and st["read"] == n and end.detail["measurement"]["state"] == "partial"
    job.close()


@pytest.mark.parametrize("opts", (STRIP, SPOT), ids=("strips", "patch by patch"))
def test_the_job_goes_on_where_the_old_sheet_has_its_patches(tmp_path, opts):
    ch, n = old_chart(tmp_path)
    before = _files(ch)
    _half_read(tmp_path, ch, n, opts)
    job, sim, helper, run = B.bed_job(tmp_path, ch, B.Bed(ch.laid()), stamp=SECOND,
                                      ask_after_each_step=False)
    assert job.set_options(opts[:-1] + ["-r"] + opts[-1:]).ok
    p = H.Person(job, sim)
    ready_to_read(job, p)
    # the plan is the old side file's own millimetres
    from workflow.i1io.table import spot as sp
    st = ch.sheet["pages"][0]["strips"][1]
    plan = sp.plan_row(job.sheet, 0, 1, job.alignment, job._table.front_y, kind="spot")
    bed = B.Bed(ch.laid())
    for t in plan.patches:
        want = bed.table_of(next(q["centre_mm"] for q in st["patches"] if q["loc"] == t.loc))
        assert abs(t.target[0] - want[0]) <= 2 and abs(t.target[1] - want[1]) <= 2, t.loc
    res = read_page(job, p)
    assert [r.detail["status"] for r in res] == ["nothing_to_read", "read", "read"]
    end, _st = _end(job, p, "save")
    assert end.ok and classify(ch.run.measurement_ti3, ch.run.chart_ti2).state \
        is Ti3State.COMPLETE
    assert _files(ch) == before
    job.close()


def test_continue_measurement_on_the_measure_tab(tab, beta, tmp_path, monkeypatch,  # noqa: F811
                                                 qtbot):
    ch, n = old_chart(tmp_path)
    _half_read(tmp_path, ch, n, SPOT)
    before = _files(ch)
    sim = B.bed_window_sim(ch, B.Bed(ch.laid()))
    monkeypatch.setattr(tab, "_current_mode", lambda: "manual")
    real = tab._manager._build_args
    monkeypatch.setattr(tab._manager, "_build_args",
                        lambda params: ["-r", "-p"] + [a for a in real(params)
                                                       if a not in ("-r", "-p")])
    monkeypatch.setattr(tab, "_read_builds_on_existing", lambda *a, **k: True)
    monkeypatch.setattr(tab, "_confirm_replacing_measurement", lambda: True)
    # the first half was read with the instrument's own white
    tab._settings.set("i1io_table_stored_tile_white", False)
    start(tab, ch.run, monkeypatch, sim)
    win = tab._table_window
    assert win is not None and win._sheet == ch.sheet
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=20000))
    page = p.drive_until(("end_of_session", "done"))
    if page == "end_of_session":
        p.press("Save and stop")
    assert unread_locations(ch.run.measurement_ti3, ch.run.chart_ti2) in ((), set(), [], None)
    assert classify(ch.run.measurement_ti3, ch.run.chart_ti2).state is Ti3State.COMPLETE
    assert len([loc for _at, loc in sim.helper.readings_at if loc[0] == "A"
                and len(loc) > 1 and loc != "A1"]) == 0          # row A was not read again
    assert _files(ch) == before
