"""`chartread -r` is sent only when specification §3a says there is something
to resume from (#148, Knut).

His log, 19:09, on a run whose measurement was not on disk:

    chromiq-chartread: Error - Unable to read chart being resumed
      '.../Demo-02-Partial-Measurement.ti3' : Unable to open file ... for reading

and then, seconds later, **the same error again** from stock chartread — because
the fallback re-launched with the arguments it had been handed, `-r` included.
Two readers, one missing file, no measurement.

ChromIQ was sending `-r` on the strength of the checkbox alone. Knut's ruling:

    *"The action when a ti3 file is not existing or is corrupt or empty is
    defined by the design specification and the unified measurement management
    model. Make sure this is handled accordingly. I assume the issue happens with
    fallback to chartread only because the event is not handled according to the
    specification."*

He is right that the model already answers it, and it answers it twice:

* **§3a**, first row — *"No `.ti3` at all … nothing measured yet | normal for a
  fresh run; C₀ = 0 | (no message)"*.
* **§5**, first row — state "None", any resume tick, **no warning**. The
  measurement simply starts.
* **§3a** on the unreadable states — a header-only or empty file *"holds no
  measurements — treat as empty"*, a corrupt one (`B ≠ C`) is *"never offer[ed]
  for resume"*, and all of them give `C₀ = 0`: *"there is nothing in it to
  resume from and nothing to lose by measuring again, and it is treated exactly
  as 'no measurement'."*

So the tick is honoured whenever it can be and ignored when nothing is behind
it — no window, because §5 asks for none. Nothing is lost either way: resuming
from nothing and starting fresh are the same measurement.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_state import can_resume          # noqa: E402

A = 4          # patches the chart describes


def _ti2(tmp_path):
    p = tmp_path / "c.ti2"
    rows = "\n".join(f"{i+1} 0 0 0" for i in range(A))
    p.write_text('CTI2\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
                 'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n'
                 f'NUMBER_OF_SETS {A}\nBEGIN_DATA\n{rows}\nEND_DATA\n')
    return p


def _ti3(tmp_path, held, claimed=None):
    """A `.ti3` holding *held* readings, claiming *claimed* in its header."""
    p = tmp_path / "c.ti3"
    rows = "\n".join(f"{i+1} 0 0 0 50 50 50" for i in range(held))
    p.write_text('CTI3\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n'
                 'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
                 'END_DATA_FORMAT\n'
                 f'NUMBER_OF_SETS {claimed if claimed is not None else held}\n'
                 f'BEGIN_DATA\n{rows}\nEND_DATA\n')
    return p


# --- every row of §3a --------------------------------------------------------

def test_no_ti3_at_all_cannot_be_resumed(tmp_path):
    """§3a row 1, and §5 row 1: nothing measured yet, no warning, just start."""
    assert can_resume(tmp_path / "c.ti3", _ti2(tmp_path)) is False


def test_a_header_only_file_cannot_be_resumed(tmp_path):
    """Several hundred bytes, and not one reading. The old test was "size > 0",
    which this file passes and `-r` does not survive."""
    p = tmp_path / "c.ti3"
    p.write_text('CTI3\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n'
                 'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
                 'END_DATA_FORMAT\n')
    assert p.stat().st_size > 0, "the point of this test is a non-empty file"
    assert can_resume(p, _ti2(tmp_path)) is False


def test_an_empty_file_cannot_be_resumed(tmp_path):
    assert can_resume(_ti3(tmp_path, 0), _ti2(tmp_path)) is False


def test_a_corrupt_file_is_never_offered_for_resume(tmp_path):
    """§3a: `B ≠ C` — *"never offer for resume"*, in as many words."""
    assert can_resume(_ti3(tmp_path, 2, claimed=9), _ti2(tmp_path)) is False


def test_a_file_holding_more_than_the_chart_cannot_be_resumed(tmp_path):
    """`C > A` — *"does not belong to this chart"*."""
    assert can_resume(_ti3(tmp_path, A + 3), _ti2(tmp_path)) is False


def test_a_partial_measurement_can_be_resumed(tmp_path):
    """The case resume exists for."""
    assert can_resume(_ti3(tmp_path, 2), _ti2(tmp_path)) is True


def test_a_complete_measurement_can_be_resumed(tmp_path):
    """§5: *"All {A} patches are already read. Resuming will only re-read the
    ones you scan again."* — allowed, with its own warning."""
    assert can_resume(_ti3(tmp_path, A), _ti2(tmp_path)) is True


def test_readings_with_no_chart_to_compare_against_can_still_be_resumed(tmp_path):
    """Readings exist and that is all we know — refusing would throw away work
    over a missing `.ti2`."""
    assert can_resume(_ti3(tmp_path, 2), None) is True


# --- both modules ask, from one place ---------------------------------------

def test_both_modules_resolve_resume_through_the_same_helper():
    """Guided and Manual have separate resume checkboxes. The last time a flag
    was resolved twice they drifted, and every Guided measurement ran
    uncalibrated because a hidden control was still being read (beta.148). One
    rule, both callers."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    for fn in (TabMeasure._collect_guided, TabMeasure._collect_manual):
        src = inspect.getsource(fn)
        assert "_resume_has_anything_to_resume" in src, fn.__name__
        assert "resume              = self._resume_cb.isChecked()" not in src
        assert "resume              = self._m_resume_cb.isChecked()" not in src


# --- and a fallback re-checks instead of trusting its arguments -------------

class _Stub:
    """Enough of a manager to exercise the argument filter, without a QObject —
    the method only needs `_resumable_partial_ti3` and the module logger."""

    def __init__(self, resumable):
        self._resumable_partial_ti3 = lambda _p: resumable


def _call(stub, args, ti1):
    from workflow.measure_manager import MeasureManager
    return MeasureManager._without_resume_when_nothing_to_resume(stub, args, ti1)


def test_the_fallback_drops_r_when_nothing_can_be_resumed(tmp_path):
    """Knut's log shows both readers failing on the same missing file, one after
    the other, because the second inherited the first's flag."""
    out = _call(_Stub(None), ["-r", "-v", "chart"], tmp_path / "c.ti1")
    assert "-r" not in out
    assert out == ["-v", "chart"], "it must drop only the resume flag"


def test_the_fallback_keeps_r_when_there_is_something_to_resume(tmp_path):
    args = ["-r", "-v", "chart"]
    assert _call(_Stub(tmp_path / "c.ti3"), args, tmp_path / "c.ti1") == args


def test_arguments_without_r_are_untouched(tmp_path):
    args = ["-v", "chart"]
    assert _call(_Stub(None), args, tmp_path / "c.ti1") == args


def test_a_broken_check_never_blocks_a_fallback(tmp_path):
    """The fallback exists to rescue a measurement; it must not be the thing
    that kills one."""
    class _Boom:
        @staticmethod
        def _resumable_partial_ti3(_p):
            raise RuntimeError("disk gone")
    args = ["-r", "chart"]
    assert _call(_Boom(), args, tmp_path / "c.ti1") == args


def test_both_fallback_launches_recheck():
    """There are two places a failed engine re-launches stock chartread. The one
    Knut hit was the second."""
    import inspect
    from workflow.measure_manager import MeasureManager
    src = inspect.getsource(MeasureManager.start)
    assert src.count("_without_resume_when_nothing_to_resume") >= 2, (
        "a re-launch that trusts its arguments is how this happened")


def test_the_mid_chart_resume_uses_the_spec_test(tmp_path):
    """`_resumable_partial_ti3` used "size > 0", which a header-only file passes
    and `-r` does not survive."""
    import inspect
    from workflow.measure_manager import MeasureManager
    src = inspect.getsource(MeasureManager._resumable_partial_ti3)
    assert "can_resume" in src
    assert "st_size" not in src
