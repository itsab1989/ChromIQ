"""R4 (4.3.39): the measurement condition actually used is written into the
.ti3 (``MEASUREMENT_CONDITION``, the keyword the i1Profiler import already
writes), not only when one was chosen with -F.

* the explicit -F choice, as before;
* else the instrument's normal mode where it IS known: M0 for the i1Pro 3
  family, and for the original i1Pro / i1Pro 2 when the engine's driver says
  no physical UV-cut filter is fitted (the helper's "filter" event, read from
  the instrument's calibration data at open; no request to the instrument);
* nothing where it cannot be known: an i1Pro with a UV-cut filter, a driver
  that did not say, any other instrument, and a resume onto a measurement
  that records none;
* a measurement that records M0 can still be continued without -F, as one
  that recorded nothing could (else 4.3.39 would refuse every resume);
* the ruler diagnostics file carries it, with where it came from;
* colprof, ArgyllCMS's average and the app's own readers take the keyword.

tester: jctay (forum 150236), whose i1Pro 3 measurement named no condition
and turned out to be M0 against his i1Profiler references.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
sys.path.insert(0, str(Path(__file__).parent))
import strip_nine_fixture as nine  # noqa: E402
from replay_tools import HELPER, ReplaySession, helper_env  # noqa: E402
from workflow.measurement_condition import (  # noqa: E402
    condition_fits_normal_mode, default_condition, read_condition,
    record_condition)

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("model,flt,want", [
    ("X-Rite i1 Pro 3", None, "M0"),            # stock chartread: no event
    ("X-Rite i1 Pro 3", "none", "M0"),
    ("X-Rite i1 Pro 3 Plus", "none", "M0"),
    ("X-Rite i1 Pro 3", "d50", None),           # never without -F, but safe
    ("GretagMacbeth i1 Pro 2", "none", "M0"),
    ("GretagMacbeth i1 Pro", "none", "M0"),
    ("GretagMacbeth i1 Pro", "uvcut", None),    # the brief's example
    ("GretagMacbeth i1 Pro 2", None, None),     # stock: cannot be known
    ("GretagMacbeth i1 Pro 2", "unknown", None),
    ("X-Rite ColorMunki", "none", None),
    ("", "none", None),
])
def test_the_normal_mode_is_known_only_where_it_is(model, flt, want):
    assert default_condition(model, flt) == want


def _ti3(path):
    path.write_text('CTI3\n\nORIGINATOR "x"\nNUMBER_OF_FIELDS 4\n'
                    "BEGIN_DATA_FORMAT\nSAMPLE_ID XYZ_X XYZ_Y XYZ_Z\n"
                    "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
                    "1 1 1 1\nEND_DATA\n", encoding="latin-1")
    return path


def test_only_a_default_m0_resumes_without_minus_f(tmp_path):
    from workflow.measurement_condition import SOURCE_INSTRUMENT_DEFAULT
    d = _ti3(tmp_path / "d.ti3")
    record_condition(d, "M0", SOURCE_INSTRUMENT_DEFAULT)
    assert condition_fits_normal_mode(d)
    e = _ti3(tmp_path / "e.ti3")
    record_condition(e, "M0")                  # an explicit -F n
    assert not condition_fits_normal_mode(e)
    # an explicit choice over a default takes the source line out
    record_condition(d, "M0")
    assert not condition_fits_normal_mode(d)
    assert "MEASUREMENT_CONDITION_SOURCE" not in d.read_text(encoding="utf-8")
    assert not condition_fits_normal_mode(tmp_path / "missing.ti3")


@pytest.mark.parametrize("source,code,refused", [
    ("INSTRUMENT_DEFAULT", None, False),       # R4: the same setting
    ("INSTRUMENT_DEFAULT", "n", False),
    ("INSTRUMENT_DEFAULT", "5", True),         # M1 on top of M0: refused
    (None, None, True),                        # S-A1 as before
])
def test_s_a1_with_a_default_m0(tmp_path, source, code, refused):
    from test_4323_review_r2a import _resume_tab
    from ui.tabs.tab_measure import TabMeasure
    ti3 = _ti3(tmp_path / "chart.ti3")
    record_condition(ti3, "M0", source)
    t = _resume_tab(ti3, code)
    assert TabMeasure._blocked_by_a_differing_condition(t) is refused


def test_the_tab_records_it_and_resumes_it():
    src = (REPO / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    end = src[src.index("def _record_measurement_condition_at_end"):]
    end = end[:end.index("\n    def ", 10)]
    assert "default_condition(" in end
    assert '"_reported_instrument"' in end      # never the chart's instrument
    assert "records_default" in end
    blk = src[src.index("def _blocked_by_a_differing_condition"):]
    blk = blk[:blk.index("\n    def ", 10)]
    assert "condition_fits_normal_mode(ti3)" in blk
    start = src.index("self._session_records_default = not (")
    assert "_resumes_unrecorded_condition(_ti3_pre)" in src[start:start + 200]


# ---- the helper's filter event ------------------------------------------------

@pytest.fixture
def chart(tmp_path):
    base = tmp_path / "nine"
    nine.write_chart(base)
    return base, nine.write_replay(tmp_path / "replay.txt")


@pytest.mark.skipif(not HELPER.exists(), reason="chromiq-chartread helper not built")
@pytest.mark.parametrize("env,want", [(None, "none"), ("uvcut", "uvcut"),
                                      ("unset", "unknown")])
def test_the_helper_says_which_filter(chart, monkeypatch, env, want):
    base, replay = chart
    if env is None:
        monkeypatch.delenv("CHROMIQ_REPLAY_FILTER", raising=False)
    else:
        monkeypatch.setenv("CHROMIQ_REPLAY_FILTER", env)
    s = ReplaySession(base, replay, extra_args=["-S"])
    try:
        ev = s.wait_event("filter", timeout=10)
        assert ev["filter"] == want
    finally:
        s.proc.kill()
        s.finish()


# ---- the manager and the diagnostics file ------------------------------------

def test_the_manager_learns_it_and_tells_the_diagnostics(qapp, tmp_path):
    from workflow.measure_manager import MeasureManager
    from workflow.ruler_session import RulerSession
    from test_knut_5956210745_next_strip_after_a_read import _Runner, _feed
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._ruler = RulerSession(ti1_path=None)
    _feed(m, {"event": "instrument", "model": "X-Rite i1 Pro 3"},
          {"event": "filter", "filter": "none"})
    assert m.engine_filter == "none"
    assert (m._ruler.condition, m._ruler.condition_source) == (
        "M0", "instrument default")
    # a choice made with -F stands
    m._ruler = RulerSession(ti1_path=None, condition="M1")
    _feed(m, {"event": "filter", "filter": "none"})
    assert (m._ruler.condition, m._ruler.condition_source) == ("M1", "chosen")


def test_the_diagnostics_file_carries_condition_and_source(tmp_path):
    from workflow.ruler_diagnostics import Diagnostics
    d = Diagnostics(tmp_path / "d.json", instrument="i1pro3", firmware=1)
    d.write()
    assert json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))[
        "measurement_condition"] is None
    d.set_condition("M0", "instrument default")
    doc = json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))
    assert doc["measurement_condition"] == "M0"
    assert doc["measurement_condition_source"] == "instrument default"
    d2 = Diagnostics(tmp_path / "e.json", instrument="i1pro3", firmware=1,
                     condition="M2")
    assert d2.doc["measurement_condition_source"] == "chosen"


# ---- every reader takes the keyword -------------------------------------------

@pytest.fixture
def measured(chart, monkeypatch):
    """A real engine .ti3 of the synthetic chart, every strip read."""
    if not HELPER.exists():
        pytest.skip("chromiq-chartread helper not built")
    monkeypatch.delenv("CHROMIQ_REPLAY_FILTER", raising=False)
    base, replay = chart
    with ReplaySession(base, replay, extra_args=["-S"]) as s:
        s.wait_event("strip_ready")
        for k in range(1, nine.STRIPS + 1):
            i = s.event_index()
            s.send(cmd="goto", strip=str(k))
            s.wait_event("strip_ready", after=i, strip=str(k))
            i = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("saved", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("done", after=i)
    plain = base.with_suffix(".ti3")
    keyed = base.parent / "keyed.ti3"
    shutil.copy(plain, keyed)
    assert record_condition(keyed, "M0")
    assert read_condition(keyed) == "M0" and read_condition(plain) is None
    return plain, keyed


def test_the_apps_readers_read_the_same_data(measured):
    plain, keyed = measured
    from workflow.ti3_analysis import parse_ti3
    from workflow.colverify_runner import read_cgats_table
    from workflow.profile_engine.ti3_data import read_ti3
    a, b = parse_ti3(plain), parse_ti3(keyed)
    assert a.n_patches == b.n_patches == 192
    ta, tb = read_cgats_table(plain), read_cgats_table(keyed)
    assert ta.rows == tb.rows
    ra, rb = read_ti3(plain), read_ti3(keyed)
    assert (ra.xyz == rb.xyz).all()


def _argyll(tool):
    return shutil.which(tool) or (
        str(Path("/Applications/Argyll/bin") / tool)
        if (Path("/Applications/Argyll/bin") / tool).exists() else None)


@pytest.mark.skipif(not _argyll("colprof"), reason="ArgyllCMS not installed")
def test_colprof_and_average_take_the_keyword(measured, tmp_path):
    _plain, keyed = measured
    work = tmp_path / "p"
    work.mkdir()
    shutil.copy(keyed, work / "K.ti3")
    r = subprocess.run([_argyll("colprof"), "-v0", "-ql", "K"],
                       cwd=work, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600,
                       env=helper_env())
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    assert (work / "K.icc").exists() or (work / "K.icm").exists()
    if _argyll("average"):
        r = subprocess.run([_argyll("average"), str(work / "K.ti3"),
                            str(work / "K.ti3"), str(work / "A.ti3")],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120,
                           env=helper_env())
        assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def test_a_filter_event_before_any_session_breaks_nothing(qapp):
    """The everyday tier found it: a manager that never started a session
    (no `_ruler` yet) took the new "filter" event and raised."""
    from workflow.measure_manager import MeasureManager
    from test_knut_5956210745_next_strip_after_a_read import _Runner, _feed
    m = MeasureManager(_Runner())
    if hasattr(m, "_ruler"):
        del m._ruler
    _feed(m, {"event": "filter", "filter": "none"})
    assert m.engine_filter == "none"
