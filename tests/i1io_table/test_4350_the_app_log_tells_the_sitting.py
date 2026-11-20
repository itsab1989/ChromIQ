"""A6 + A4 (4.3.50): a table sitting leaves a few lines in the app log (the session folder,
every job call's result with the arm's position, each page shown and the answer given, one
line per row, the ending), from the window's GUI thread after each result; the wire
traffic stays in the session folder."""
from __future__ import annotations

import logging

from tests.i1io_table.test_window import open_window, settings  # noqa: F401


def _msgs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "chromiq.events"]


def test_a_table_page_in_the_app_log(qtbot, monkeypatch, tmp_path, settings, caplog):  # noqa: F811
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                        asking=False)
        p.drive_until("end_of_session")
        p.press("Save and stop")
        p.press("Bring the arm home, my hands are away")
    m = _msgs(caplog)
    tags = {x.split(":", 1)[0] for x in m}
    assert {"table session", "table page", "table result", "question answer", "strip",
            "table session end"} <= tags, tags
    (opened,) = [x for x in m if x.startswith("table session:")]
    assert "job_version=" in opened and "folder=" in opened and "i1io-table" in opened
    results = [x for x in m if x.startswith("table result:")]
    assert any("step=align" in x and "aims=" in x for x in results), results
    assert any("step=home" in x and "at_rest=on" in x for x in results)
    rows = [x for x in m if x.startswith("strip:")]
    assert rows and all("path=table" in x for x in rows)
    assert any("result=kept" in x and "took_s=" in x for x in rows), rows
    answers = [x for x in m if x.startswith("question answer:")]
    assert any('id=table:' in x and 'answer="Save and stop"' in x for x in answers), answers
    # no wire traffic in the app log
    assert not any("SEND" in x or "RECV" in x for x in m)
    lines = len(m)
    import os
    if os.environ.get("CQ_DUMP"):
        open(os.environ["CQ_DUMP"], "w", encoding="utf-8").write("\n".join(m))
    assert lines < 400, lines
