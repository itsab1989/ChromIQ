"""An engine resume asks "was the chart already complete" by location (4.3.5 beta 8).

Found on screen by the beta-7 regression review: ChromIQ's layout engine gives
the fill-up squares that complete the last strip real ids, so chartread and
ChromIQ's own engine both write readings for them. A file two design patches
short (C5 and D3) then held 398 rows for a 390-patch design on a 400-square
sheet, and `measurement_state.classify` counted it COMPLETE. The engine's
session_start took that as "the chart was already finished", so reading C and
D took the progress to 100 % and no completion window came. The same on a
calibration chart (62 rows, A3 and B2 missing). Stock chartread had been fixed
for the same blind spot in 4aad735ec by asking by location; the question now
lives in `classify` itself (`unread_design_locations`), so the engine, stock
chartread, the Start Measurement message, the Profile tab and the progress all
get one answer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication

from workflow.measure_manager import MeasureManager
from workflow.measurement_state import Ti3State, classify, progress_from_files


def unread_design_locations(ti3, ti2):
    from workflow.measurement_state import unread_design_locations as f
    return f(ti3, ti2)


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QCoreApplication.instance() or QCoreApplication(sys.argv)


STRIPS = "ABC"
PER = 4
DESIGN = 10          # C3 and C4 are the engine's fill-up squares
SHEET = [f"{s}{p}" for s in STRIPS for p in range(1, PER + 1)]
FILL = {"C3", "C4"}


def _engine_chart(folder: Path) -> Path:
    """A ChromIQ-layout-engine .ti2: 12 squares, the last two fill-up."""
    rows = [f'{i + 1} "{loc}" 50.0 50.0 50.0 20.0 21.0 22.0'
            for i, loc in enumerate(SHEET)]
    p = folder / "chart.ti2"
    p.write_text(
        'CTI2\n\nDESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        'ORIGINATOR "ChromIQ layout engine"\nCOLOR_REP "iRGB"\n'
        f'STEPS_IN_PASS "{PER}"\nPASSES_IN_STRIPS2 "{len(STRIPS)}"\n'
        'NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        f'END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n'
        + "\n".join(rows) + "\nEND_DATA\n", encoding="latin-1")
    (folder / "chart.ti1").write_text(
        f"CTI1\n\nNUMBER_OF_SETS {DESIGN}\nBEGIN_DATA\nEND_DATA\n",
        encoding="latin-1")
    return p


def _ti3(folder: Path, locs) -> Path:
    rows = [f'{i + 1} "{loc}" 50.0 50.0 50.0 20.0 21.0 22.0'
            for i, loc in enumerate(locs)]
    p = folder / "chart.ti3"
    p.write_text(
        'CTI3\n\nDESCRIPTOR "Argyll Calibration Target chart information 3"\n'
        'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        'NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        f'END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n'
        + "\n".join(rows) + "\nEND_DATA\n", encoding="latin-1")
    return p


def _fill_gap(folder: Path) -> Path:
    """The reviewer's 398-of-390 file in small: two design patches missing,
    the fill-up squares read, as many rows as the design has patches."""
    return _ti3(folder, [x for x in SHEET if x not in {"A3", "B2"}])


# ---- the definition ----------------------------------------------------------

def test_a_file_with_fill_up_readings_and_a_design_gap_is_partial(tmp_path):
    ti2 = _engine_chart(tmp_path)
    ti3 = _fill_gap(tmp_path)
    facts = classify(ti3, ti2)
    assert facts.held == DESIGN, "as many rows as the design has patches"
    assert facts.state is Ti3State.PARTIAL
    assert facts.design_read == DESIGN - 2
    assert facts.patches_read == DESIGN - 2
    assert unread_design_locations(ti3, ti2) == {"A3", "B2"}
    assert progress_from_files(ti3, ti2) == pytest.approx(80.0)


def test_every_design_patch_read_is_complete_with_or_without_fill_up(tmp_path):
    ti2 = _engine_chart(tmp_path)
    assert classify(_ti3(tmp_path, SHEET), ti2).state is Ti3State.COMPLETE
    design = [x for x in SHEET if x not in FILL]
    assert classify(_ti3(tmp_path, design), ti2).state is Ti3State.COMPLETE


def test_the_control_without_fill_up_rows_stays_partial(tmp_path):
    ti2 = _engine_chart(tmp_path)
    ti3 = _ti3(tmp_path, [x for x in SHEET if x not in FILL | {"A3", "B2"}])
    facts = classify(ti3, ti2)
    assert facts.state is Ti3State.PARTIAL
    assert facts.patches_read == DESIGN - 2


def test_names_the_chart_does_not_have_keep_the_count(tmp_path):
    """A file that cannot be compared by name must never be made partial by
    the comparison: the count's answer stands."""
    ti2 = _engine_chart(tmp_path)
    ti3 = _ti3(tmp_path, [f"Z{i}" for i in range(1, DESIGN + 1)])
    assert unread_design_locations(ti3, ti2) is None
    assert classify(ti3, ti2).state is Ti3State.COMPLETE


# ---- the engine's session_start -------------------------------------------

class _Runner:
    def __init__(self):
        self.sent = []

    def write_stdin(self, text):
        self.sent.append(text)

    def abort(self):
        pass


def _engine_resume(ti2: Path):
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._spot_mode = False
    m._is_resume = True
    fired = []
    m.all_stripes_done.connect(lambda: fired.append(1))
    return m, fired


def _feed(m, *events):
    for ev in events:
        m._handle_engine_line(json.dumps(ev), lambda _s: None)


def _start(ti2):
    # Every strip's first patch has a reading, so the engine says read: true
    # for all of them: the gap is per patch.
    return {"event": "session_start", "chart": str(ti2),
            "strips": [{"strip": s, "read": True} for s in STRIPS]}


def _read(strip):
    return {"event": "strip_read", "strip": strip,
            "patches": [{"loc": f"{strip}{p}"} for p in range(1, PER + 1)]}


def _ready(strip, all_done=True):
    return {"event": "strip_ready", "strip": strip, "read": True,
            "all_done": all_done}


def test_an_engine_resume_of_a_file_with_a_design_gap_was_not_complete(
        tmp_path):
    ti2 = _engine_chart(tmp_path)
    _fill_gap(tmp_path)
    m, _fired = _engine_resume(ti2)
    _feed(m, _start(ti2))
    assert m._chart_was_complete is False


def test_reading_the_gap_on_the_engine_announces_the_completion(tmp_path):
    """The reviewer's case: read A and B (the strips with the gaps); the
    chart is now complete and that is news. The engine says all_done after
    every read here (each strip's first patch has a reading), and the
    manager passes each one on; the Measure tab picks the window by its own
    unread count (M-ALL-STRIPS-PATCHES-LEFT waits, "All Strips Read" once
    nothing is unread). Before the fix nothing was passed on at all."""
    ti2 = _engine_chart(tmp_path)
    _fill_gap(tmp_path)
    m, fired = _engine_resume(ti2)
    _feed(m, _start(ti2), _ready("A"))
    assert fired == [], "nothing is completed before a read"
    _feed(m, _read("A"), _ready("B"))
    after_a = len(fired)
    _feed(m, _read("B"), _ready("C"))
    assert len(fired) == after_a + 1, "reading the last gap is announced"


def test_re_reading_a_strip_of_a_finished_chart_stays_silent(tmp_path):
    """Knut, #131: the rule the suppression exists for still holds."""
    ti2 = _engine_chart(tmp_path)
    _ti3(tmp_path, SHEET)
    m, fired = _engine_resume(ti2)
    _feed(m, _start(ti2))
    assert m._chart_was_complete is True
    _feed(m, _ready("A"), _read("A"), _ready("B"))
    assert fired == []


def test_stock_and_engine_share_the_one_definition():
    """One question, one place: both paths ask `_measurement_was_complete`,
    which asks `classify`."""
    import inspect

    src = inspect.getsource(MeasureManager._prepare_stock_count)
    assert "_measurement_was_complete(" in src
    assert "chart_locations(ti3)" in src, "the strip-read rule stays"
    from workflow import measurement_state
    assert "unread_design_locations(" in inspect.getsource(
        measurement_state.classify)


# ---- the import door asks the same question --------------------------------

def test_an_import_with_a_design_gap_is_filed_as_partial(tmp_path):
    from workflow.measurement_import import _design_patches_unread
    ti2 = _engine_chart(tmp_path)
    assert _design_patches_unread(_fill_gap(tmp_path), ti2) is True
    assert _design_patches_unread(_ti3(tmp_path, SHEET), ti2) is False


def test_an_import_partial_by_location_states_the_patches_read(tmp_path):
    """Review of beta 8: the import door's partial windows state the chart's
    count beside the file's. For a file partial by location the row count
    equals the chart's (or passes it), and "the chart has 10 patches and
    this file holds 10 readings, so part of the chart was not measured"
    contradicts itself; the verification door even said "holds only". They
    state the design patches read instead, the same number as the Start
    message and the Profile tab."""
    from workflow.measurement_import import assess
    ti2 = _engine_chart(tmp_path)
    v = assess(_fill_gap(tmp_path), ti2)
    assert v.ok and v.partial
    assert v.n_measured == DESIGN, "the rows are still the rows"
    assert v.patches_read == DESIGN - 2
    short = assess(_ti3(tmp_path, SHEET[:5]), ti2)
    assert short.partial and short.patches_read == 5
    whole = assess(_ti3(tmp_path, SHEET), ti2)
    assert not whole.partial and whole.patches_read == len(SHEET)
    import inspect
    from ui import measurement_filing
    from ui.tabs.tab_measure import TabMeasure
    for src in (inspect.getsource(measurement_filing),
                inspect.getsource(TabMeasure._import_mismatch_reason)):
        assert "got=verdict.n_measured" not in src
