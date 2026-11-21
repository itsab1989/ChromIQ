"""4.3.54, the review's M2: a measurement any row of which the i1iO table read at a row speed
factor other than 1.00 carries CHROMIQ_ROW_SPEED in its header ("factor F: N of M rows faster than
the safe border"), beside CHROMIQ_VERSION / CHROMIQ_HELPER_BUILD; the mark is never dropped by a
Continue, a merge or an average (any contributing file with it gives the result it); the
measurement report names it; and one line says it at the end of a table measurement.

Why "a factor other than 1.00" and not only "faster than the safe border": every row read at a
factor not 1.00 was read at a speed ChromIQ did not choose (above 1.00 the border may be shrunk,
below it the speed was never ChromIQ's own for that patch length); the mark says how many rows
were also read faster than the safe border, which is where the risk is."""
from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import ti3_provenance as tp  # noqa: E402

TI3 = """CTI3
DESCRIPTOR "x"
ORIGINATOR "Argyll chartread"
NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
SAMPLE_ID XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 1
BEGIN_DATA
1 10 10 10
END_DATA
"""


def _file(tmp_path, name, mark=None):
    p = tmp_path / name
    p.write_text(TI3, encoding="ascii")
    if mark:
        assert tp.stamp_row_speed(p, mark)
    return p


def _job(marks):
    from workflow.i1io.table import job as J
    j = SimpleNamespace(row_speed_marks=dict(marks))
    return J.TableJob.row_speed_mark(j)


def test_the_mark_of_a_sitting():
    assert _job({}) is None
    assert _job({(0, 0): (1.0, False), (0, 1): (1.0, False)}) is None
    assert _job({(0, 0): (1.95, True), (0, 1): (1.95, True)}) == (
        "factor 1.95: 2 of 2 rows faster than the safe border")
    assert _job({(0, 0): (0.75, False), (0, 1): (1.0, False)}) == (
        "factor 0.75: 0 of 2 rows faster than the safe border")


def test_written_beside_the_version_and_never_dropped(tmp_path):
    p = _file(tmp_path, "a.ti3", "factor 1.95: 22 of 22 rows faster than the safe border")
    text = p.read_text(encoding="ascii")
    assert 'KEYWORD "CHROMIQ_ROW_SPEED"' in text
    assert tp.read_row_speed(p) == "factor 1.95: 22 of 22 rows faster than the safe border"
    # a later sitting at 1.00 (no mark of its own) keeps it
    tp.stamp_row_speed(p, None)
    assert tp.read_row_speed(p).startswith("factor 1.95")
    # nothing at all is written into a file that never had one
    q = _file(tmp_path, "b.ti3")
    assert not tp.stamp_row_speed(q, None) and tp.read_row_speed(q) is None
    # the readings are untouched
    assert p.read_text(encoding="ascii").split("BEGIN_DATA\n")[1] == TI3.split("BEGIN_DATA\n")[1]


def test_continue_merge_and_average_keep_every_mark(tmp_path):
    from workflow import ti3_merge
    fast = _file(tmp_path, "fast.ti3", "factor 1.95: 3 of 4 rows faster than the safe border")
    plain = _file(tmp_path, "plain.ti3")
    result = _file(tmp_path, "result.ti3")
    ti3_merge.settle_combined_xyz_method(result, [plain, fast])
    assert tp.read_row_speed(result) == "factor 1.95: 3 of 4 rows faster than the safe border"
    slow = _file(tmp_path, "slow.ti3", "factor 0.75: 0 of 4 rows faster than the safe border")
    tp.stamp_row_speed(result, None, [slow])
    assert tp.read_row_speed(result) == ("factor 1.95: 3 of 4 rows faster than the safe border"
                                         " + factor 0.75: 0 of 4 rows faster than the safe "
                                         "border")
    # the hand path's Continue carries the guard's copy; the table's carries its base
    from ui.tabs.tab_measure import TabMeasure
    assert "tp.stamp_row_speed(ti3, sources=[guard.archive])" in inspect.getsource(
        TabMeasure._stamp_provenance_at_end)
    from workflow.i1io.table import job as J
    src = inspect.getsource(J.TableJob)
    assert "stamp_row_speed(path, self.row_speed_mark(), [base] if base else [])" in src
    assert src.count("self._stamp_row_speed(") >= 2
    import workflow.ti3_average as av
    assert "stamp_row_speed(out, sources=[Path(p) for p in inputs])" in inspect.getsource(av)


def test_the_report_names_it(tmp_path):
    from workflow import measurement_report as mr
    src = inspect.getsource(mr)
    assert 'report["row_speed"] = _rs' in src
    from ui.dialogs import measurement_report_dialog as d
    assert "Read by the i1iO table at a row speed other than 1.00" in inspect.getsource(d)


def test_one_line_at_the_end_of_a_table_measurement(qapp, tmp_path):
    from workflow import measurement_messages as M
    from ui.tabs.tab_measure import TabMeasure
    got, notice = [], []
    fake = SimpleNamespace(_log=SimpleNamespace(appendPlainText=got.append,
                                                ensureCursorVisible=lambda: None),
                           _preview=SimpleNamespace(set_notice=lambda b, warn: notice.append(b)))
    p = _file(tmp_path, "m.ti3", "factor 1.95: 22 of 22 rows faster than the safe border")
    TabMeasure._say_row_speed_at_end(fake, p)
    title, body = M.M_I1IO_ROW_SPEED_END.render(mark=tp.read_row_speed(p))
    assert got == [f"[{title}]\n{body}"] and notice == [body]
    assert "1.00" in body and "without any warning" in body and "factor 1.95" in body
    got.clear()
    TabMeasure._say_row_speed_at_end(fake, _file(tmp_path, "n.ti3"))
    assert got == []
