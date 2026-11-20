"""4.3.52 fix round, S-5 of the independent safety review: with "Keep the table's detailed log"
off, the table's model answers (a1, k2) existed only as RECV lines, so a clean sitting lost them
(and a late stop's 300-line ring no longer reached back to them). They are one DATA line now,
written in both cases: they identify the model, not the person (both are the one recorded form)."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_4352_guidance_off import _session_log, _to_done, _unguided
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from ui import i1io_table_window as W
from workflow.i1io.table import session_table as tbl


@pytest.mark.parametrize("detailed", [True, False])
def test_s5_the_model_answers_are_kept_with_the_detailed_log_on_and_off(qtbot, monkeypatch,
                                                                       tmp_path, settings,
                                                                       detailed):
    settings.set(W.EXTRA_LOG_KEY, detailed)
    try:
        win, sim, run, p, *_ = _unguided(qtbot, monkeypatch, tmp_path, settings)
        _to_done(p)
        p.press("Close")
        text = _session_log(run)
    finally:
        settings.set(W.EXTRA_LOG_KEY, True)
    want = (f"the table's model answers: a1 = {tbl.EXACT_DATA['identity']}, "
            f"k2 = {tbl.EXACT_DATA['k2']}")
    lines = [ln for ln in text.splitlines() if want in ln]
    assert len(lines) == 1 and lines[0].startswith("DATA"), lines
    # nothing else of the wire came back with it
    if not detailed:
        assert not [ln for ln in text.splitlines() if ln.startswith(("SEND", "RECV"))]
