"""Every square of the chart counts, fill-up included (Knut, #182 6191934889).

Knut's ruling of 2026-10-15, confirmed: *"All fill-up patches are patches that
are randomly redistributed on the layout and are read as real patches. ALL
patches in the chart, fill-up or not, shall be counted to get a complete
chart. If two patches are missing and not read, then the chart is not
completed."* It replaces the beta-8 proposal ("complete = every designed patch
read, fill-up squares do not count").

So a chart from ChromIQ's layout engine with 10 designed patches and 2
fill-up squares has 12 patches: a file holding the 10 designed ones is
2 short, a file holding all 12 is complete, and the question is asked by
location in `classify` (`unread_locations`), so the engine, stock chartread,
the Start Measurement message, the Profile tab, the progress and the import
doors all get one answer. Only printtarg's ``SAMPLE_ID`` 0 padding stays out,
because no reader ever records it.

(Was ``test_b8_engine_resume_judges_completeness_by_location.py``, which
pinned the rejected design-only rule.)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication

from workflow.measure_manager import MeasureManager
from workflow.measurement_state import Ti3State, classify, progress_from_files


def unread_locations(ti3, ti2):
    from workflow.measurement_state import unread_locations as f
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

def test_the_chart_has_every_square_as_a_patch(tmp_path):
    from workflow.measurement_state import expected_patches, sheet_patches
    ti2 = _engine_chart(tmp_path)
    assert expected_patches(ti2) == len(SHEET) == sheet_patches(ti2)


def test_a_file_with_a_gap_is_partial_and_counts_every_square(tmp_path):
    ti2 = _engine_chart(tmp_path)
    ti3 = _fill_gap(tmp_path)
    facts = classify(ti3, ti2)
    assert facts.state is Ti3State.PARTIAL
    assert facts.expected == len(SHEET)
    assert facts.located_read == facts.patches_read == len(SHEET) - 2
    assert unread_locations(ti3, ti2) == {"A3", "B2"}
    assert progress_from_files(ti3, ti2) == pytest.approx(
        100.0 * (len(SHEET) - 2) / len(SHEET))


def test_the_designed_patches_alone_are_not_a_complete_chart(tmp_path):
    """The rejected rule called this complete. Two squares are unread."""
    ti2 = _engine_chart(tmp_path)
    ti3 = _ti3(tmp_path, [x for x in SHEET if x not in FILL])
    facts = classify(ti3, ti2)
    assert facts.state is Ti3State.PARTIAL
    assert facts.patches_read == DESIGN
    assert unread_locations(ti3, ti2) == FILL


def test_every_square_read_is_complete(tmp_path):
    ti2 = _engine_chart(tmp_path)
    facts = classify(_ti3(tmp_path, SHEET), ti2)
    assert facts.state is Ti3State.COMPLETE
    assert facts.patches_read == len(SHEET)


def test_printtargs_padding_is_still_left_out(tmp_path):
    """printtarg's SAMPLE_ID 0 rows are never recorded by any reader, so a
    file holding every other square is complete."""
    rows = [f'{"0" if loc in FILL else i + 1} "{loc}" 50.0 50.0 50.0 '
            f'20.0 21.0 22.0' for i, loc in enumerate(SHEET)]
    ti2 = tmp_path / "pt.ti2"
    ti2.write_text(
        'CTI2\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        f'END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n'
        + "\n".join(rows) + "\nEND_DATA\n", encoding="latin-1")
    ti3 = _ti3(tmp_path, [x for x in SHEET if x not in FILL])
    facts = classify(ti3, ti2)
    assert facts.expected == DESIGN
    assert facts.state is Ti3State.COMPLETE


def test_names_the_chart_does_not_have_keep_the_count(tmp_path):
    """A file that cannot be compared by name must never be judged by the
    comparison: the count's answer stands."""
    ti2 = _engine_chart(tmp_path)
    ti3 = _ti3(tmp_path, [f"Z{i}" for i in range(1, len(SHEET) + 1)])
    assert unread_locations(ti3, ti2) is None
    assert classify(ti3, ti2).state is Ti3State.COMPLETE
    short = _ti3(tmp_path, [f"Z{i}" for i in range(1, DESIGN + 1)])
    assert classify(short, ti2).state is Ti3State.PARTIAL


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


def test_an_engine_resume_of_a_file_with_a_gap_was_not_complete(
        tmp_path):
    ti2 = _engine_chart(tmp_path)
    _fill_gap(tmp_path)
    m, _fired = _engine_resume(ti2)
    _feed(m, _start(ti2))
    assert m._chart_was_complete is False


def test_an_engine_resume_of_the_design_alone_was_not_complete(tmp_path):
    """The fill-up squares unread: reading strip C completes the chart, and
    that is news."""
    ti2 = _engine_chart(tmp_path)
    _ti3(tmp_path, [x for x in SHEET if x not in FILL])
    m, fired = _engine_resume(ti2)
    _feed(m, _start(ti2))
    assert m._chart_was_complete is False
    _feed(m, _ready("C"), _read("C"), _ready("C"))
    assert fired, "reading the fill-up squares completes the chart"


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
    assert "unread_locations(" in inspect.getsource(
        measurement_state.classify)


# ---- the import door asks the same question --------------------------------

def test_an_import_with_a_gap_is_filed_as_partial(tmp_path):
    from workflow.measurement_import import assess
    ti2 = _engine_chart(tmp_path)
    assert assess(_fill_gap(tmp_path), ti2).partial
    assert assess(_ti3(tmp_path, [x for x in SHEET if x not in FILL]),
                  ti2).partial, "the fill-up squares are part of the chart"
    assert not assess(_ti3(tmp_path, SHEET), ti2).partial


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
    # 12 rows, one location twice and A3 missing: partial by location only.
    v = assess(_ti3(tmp_path, [x if x != "A3" else "A1" for x in SHEET]), ti2)
    assert v.ok and v.partial
    assert v.n_measured == len(SHEET), "the rows are still the rows"
    assert v.patches_read == len(SHEET) - 1
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
