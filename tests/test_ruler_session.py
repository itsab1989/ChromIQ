"""The ruler check between the engine and the Measure tab
(workflow/ruler_session.py, the manager's wiring, Preferences > Beta).

* OFF: the setting is off by default and the helper's command line is exactly
  the base branch's (no --ruler), whatever the lights options are;
* ON: --ruler only for a helper whose caps name "ruler_check";
* the per-strip line, "no ruler seen" once, an incomplete record one short
  line, a given-up ruler one friendly line, the end line with the file;
* the question: only for an accepted strip, never when another question is
  asked, on an i1Pro 2 only after the session worked out its step size;
* the diagnostics file after every strip, with "stream_did_not_end".
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_ruler_check import stream                      # noqa: E402
from workflow.ruler_session import RulerSession               # noqa: E402

CHART = Path(__file__).parent / "data" / "b8_1570_beta44_chart" / "chart.channels.json"


def _cut(rec, n=16, start=0.15, end=0.85):
    readings = rec["readings"]
    cut = []
    for k in range(n):
        s0 = int(readings * (start + (end - start) * k / n))
        s1 = int(readings * (start + (end - start) * (k + 1) / n))
        no = (s1 - s0) * 2 // 3
        cut += [s0 + (s1 - s0 - no) // 2, no]
    rec["cut"] = cut
    return rec


def _rec(strip, steps, gen="i1pro2", result="read", **kw):
    r = stream(steps, 600, gen=gen, ended="short" if gen == "i1pro2" else "argyll",
               start_frac=0.1, end_frac=0.9, **kw)
    r.update({"strip": strip, "result": result, "argyll_used": True})
    return _cut(r)


def _strip_read(strip, n=16, **kw):
    ev = {"event": "strip_read", "strip": strip,
          "patches": [{"loc": f"{strip}{i + 1}"} for i in range(n)]}
    ev.update(kw)
    return ev


def _session(tmp_path, gen="i1pro2", chart=False):
    ti1 = tmp_path / "runs" / "run1" / "chart.ti1"
    ti1.parent.mkdir(parents=True)
    if chart:
        (ti1.parent / "chart.channels.json").write_text(
            CHART.read_text(encoding="utf-8"), encoding="utf-8")
    rs = RulerSession(ti1_path=ti1)
    lines = rs.on_session({"event": "ruler", "active": True,
                           "instrument": gen, "firmware": 634})
    return rs, lines


def test_the_setting_is_off_by_default():
    from core.settings import DEFAULTS
    assert DEFAULTS["ruler_check_beta"] is False


def test_opening_lines_name_the_file(tmp_path):
    rs, lines = _session(tmp_path)
    assert "firmware 634" in lines[0] and "i1Pro 2" in lines[0]
    assert str(rs.diagnostics_path()) in lines[1]
    assert rs.diagnostics_path().parent.name == "reports"


def test_inactive_says_why_once(tmp_path):
    rs = RulerSession(ti1_path=tmp_path / "c.ti1")
    assert "does not report a ruler sensor" in rs.on_session(
        {"active": False, "why": "sensor", "instrument": "i1pro2"})[0]
    assert "i1Pro 2 and i1Pro 3 only" in rs.on_session(
        {"active": False, "why": "instrument"})[0]


def test_a_strip_line_and_no_question_on_a_full_strip(tmp_path):
    rs, _ = _session(tmp_path)
    lines = rs.on_strip(_rec("A", 340))
    assert lines and "strip A" in lines[0] and "ruler steps" in lines[0]
    summ = rs.on_strip_read(_strip_read("A"), other_question=False)
    assert summ["usable"] and not summ["ask"]
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    assert doc["strips"][0]["verdict"] == "accepted"
    assert doc["strips"][0]["stream_did_not_end"] is False


def test_i1pro2_asks_only_after_the_session_knows_its_step(tmp_path):
    rs, _ = _session(tmp_path)
    # first strip partial: no step size yet (printtarg chart, no geometry)
    rs.on_strip(_rec("A", 60))
    assert not rs.on_strip_read(_strip_read("A"), other_question=False)["ask"]
    for s in "BCD":                    # three good strips teach the pitch
        rs.on_strip(_rec(s, 340))
        assert not rs.on_strip_read(_strip_read(s), other_question=False)["ask"]
    rs.on_strip(_rec("E", 60))
    assert rs.on_strip_read(_strip_read("E"), other_question=False)["ask"]


def test_i1pro3_with_chart_geometry_asks_on_a_clearly_short_strip(tmp_path):
    rs, _ = _session(tmp_path, gen="i1pro3", chart=True)
    geo = rs.geometry["A"]
    n = geo["patches"]
    full = int(geo["span_mm"] / 0.5 * 1.3)
    rs.on_strip(_cut(_rec("A", full, gen="i1pro3"), n=n))
    assert not rs.on_strip_read(_strip_read("A", n=n), other_question=False)["ask"]
    rs.on_strip(_cut(_rec("B", full // 4, gen="i1pro3"), n=n))
    summ = rs.on_strip_read(_strip_read("B", n=n), other_question=False)
    assert summ["ask"] is (n >= 8)
    # never when another question is asked about the same strip
    rs.on_strip(_cut(_rec("C", full // 4, gen="i1pro3"), n=n))
    assert not rs.on_strip_read(_strip_read("C", n=n), other_question=True)["ask"]


def test_no_ruler_is_said_once(tmp_path):
    rs, _ = _session(tmp_path)
    a = rs.on_strip(_rec("A", 0))
    b = rs.on_strip(_rec("B", 0))
    assert len(a) == 1 and "no ruler was seen" in a[0] and b == []


def test_an_incomplete_record_is_one_short_line(tmp_path):
    rs, _ = _session(tmp_path)
    r = _rec("A", 340, extra=-900)
    assert "incomplete" in rs.on_strip(r)[0]
    assert not rs.on_strip_read(_strip_read("A"), other_question=False)["ask"]


def test_a_given_up_ruler_is_said_once_and_filed(tmp_path):
    rs, _ = _session(tmp_path)
    r = {"strip": "A", "instrument": "i1pro2", "result": "read",
         "ended": "running", "given_up": True, "giveup": "stream_did_not_end",
         "stream_did_not_end": True, "changes": [], "samples": 0,
         "readings": 600, "clocks": 136, "clock_s": 36e-6}
    lines = rs.on_strip(r)
    assert len(lines) == 1 and "stopped using" in lines[0]
    assert "did not end by itself" in lines[0]
    rs.on_strip_read(_strip_read("A"), other_question=False)
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    assert doc["strips"][0]["stream_did_not_end"] is True


def test_a_refused_strip_is_filed_without_a_question(tmp_path):
    rs, _ = _session(tmp_path)
    rs.on_strip(_rec("A", 60, result="misread"))
    assert rs.on_strip_read(_strip_read("A"), other_question=False) is None
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    assert doc["strips"][0]["verdict"] == "refused"


def test_the_end_line_names_the_file_and_how_to_send_it(tmp_path):
    rs, _ = _session(tmp_path)
    rs.on_strip(_rec("A", 340))
    rs.on_strip_read(_strip_read("A"), other_question=False)
    end = rs.on_end()
    assert end and str(rs.diagnostics_path()) in end[0]
    assert "no serial number" in end[0]


# ---- the manager's command line ------------------------------------------
from tests.test_i1pro2_lights_beta_option import _Runner  # noqa: E402


def _args(qapp, tmp_path, monkeypatch, *, ruler, caps, lights=False):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps",
                        lambda helper=None: frozenset(caps))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port",
                        lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      engine_i1pro2_lights=lights, engine_lights_signals=lights,
                      engine_ruler_check=ruler)
    m.start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1]


@pytest.mark.parametrize("lights", [False, True])
def test_off_adds_nothing_to_the_command_line(qapp, tmp_path, monkeypatch, lights):
    caps = {"ruler_check", "i1pro2_lights", "lights_signals"}
    off = _args(qapp, tmp_path, monkeypatch, ruler=False, caps=caps, lights=lights)
    assert "--ruler" not in off


@pytest.mark.parametrize("lights", [False, True])
def test_on_adds_ruler_only_for_a_helper_that_knows_it(qapp, tmp_path,
                                                         monkeypatch, lights):
    caps = {"ruler_check", "i1pro2_lights", "lights_signals"}
    on = _args(qapp, tmp_path, monkeypatch, ruler=True, caps=caps, lights=lights)
    off = _args(qapp, tmp_path, monkeypatch, ruler=False, caps=caps, lights=lights)
    assert [a for a in on if a != "--ruler"] == off and on.count("--ruler") == 1
    assert ("--i1pro2-lights" in on) is lights
    old = _args(qapp, tmp_path, monkeypatch, ruler=True, caps={"i1pro2_lights"})
    assert "--ruler" not in old


def test_the_tab_passes_the_setting(qapp):
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert 'p.engine_ruler_check = bool(\n            self._settings.get("ruler_check_beta", False))' in src


# ---- Preferences > Beta ---------------------------------------------------
def test_the_preferences_row_its_help_and_its_confirmation(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from core.settings import AppSettings
    from ui.dialogs import settings_dialog as sd
    dlg = sd.SettingsDialog(AppSettings())
    try:
        box = dlg._ruler_check_check
        assert not box.isChecked()
        assert "(beta)" in box.text()
        help_text = sd.ruler_check_help()
        for must in ("never changed", "nothing new is sent", "diagnostics",
                     "serial number", "**Default:** off"):
            assert must in help_text, must
        assert "—" not in help_text + sd.ruler_check_confirmation()
        monkeypatch.setattr(QMessageBox, "exec",
                            lambda self: QMessageBox.StandardButton.Cancel)
        box.click()
        assert not box.isChecked()
        monkeypatch.setattr(QMessageBox, "exec",
                            lambda self: QMessageBox.StandardButton.Ok)
        box.click()
        assert box.isChecked()
    finally:
        dlg.reject()
        dlg.deleteLater()


# ---- review round 1 (2026-11-14): items 6 and 9 --------------------------
def test_i1pro2_with_chart_geometry_needs_three_strips_before_asking(tmp_path):
    rs, _ = _session(tmp_path, chart=True)
    n = rs.geometry["A"]["patches"]
    for i, s in enumerate("ABC"):
        rs.on_strip(_cut(_rec(s, 340), n=n))
        assert rs.derived_step() is None or i == 2
        rs.on_strip_read(_strip_read(s, n=n), other_question=False)
    assert rs.derived_step() is not None
    # after one or two strips a short strip was only reported
    rs2, _ = _session(tmp_path / "two", chart=True)
    rs2.on_strip(_cut(_rec("A", 340), n=n))
    rs2.on_strip_read(_strip_read("A", n=n), other_question=False)
    rs2.on_strip(_cut(_rec("B", 60), n=n))
    assert not rs2.on_strip_read(_strip_read("B", n=n), other_question=False)["ask"]


def test_units_switch_once_with_a_line_that_says_so(tmp_path):
    rs, _ = _session(tmp_path, chart=True)
    n = rs.geometry["A"]["patches"]
    seen = []
    for s in "ABCDE":
        seen += rs.on_strip(_cut(_rec(s, 340), n=n))
        rs.on_strip_read(_strip_read(s, n=n), other_question=False)
    steps = [ln for ln in seen if "ruler steps" in ln]
    mm = [ln for ln in seen if " mm along the ruler" in ln]
    switch = [ln for ln in seen if "from now on the distances are shown in mm" in ln]
    assert len(steps) == 3 and len(mm) == 2 and len(switch) == 1
    assert seen.index(switch[0]) < seen.index(mm[0])


def test_the_file_takes_argyll_s_version_from_the_engine(tmp_path):
    ti1 = tmp_path / "c.ti1"
    rs = RulerSession(ti1_path=ti1)
    rs.on_session({"active": True, "instrument": "i1pro2", "firmware": 634,
                   "argyll": "3.5.0"})
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    assert doc["argyllcms"] == "3.5.0"
    import inspect
    from workflow import ruler_diagnostics
    assert '"3.5.0"' not in inspect.getsource(ruler_diagnostics)


def test_strip_read_ok_waits_for_the_answer(qapp, tmp_path, monkeypatch):
    """Review item 9: "Strip read OK" is not shown for a strip the person
    chose to read again after the ruler question."""
    from workflow.measure_manager import MeasureManager
    m = MeasureManager(_Runner())
    lines = []
    rs, _ = _session(tmp_path)
    m._ruler = rs
    for s in "BCD":
        rs.on_strip(_rec(s, 340))
        m._handle_engine_line(json.dumps(_strip_read(s)), lines.append)
    rs.on_strip(_rec("E", 60))
    m.strip_measured.connect(
        lambda ev: m.ruler_answer(ev["strip"], "reread")
        if (ev.get("ruler") or {}).get("ask") else None)
    m._handle_engine_line(json.dumps(_strip_read("E")), lines.append)
    assert not any("Strip read OK — E " in ln for ln in lines)
    assert any("Strip E: you chose to read it again" in ln for ln in lines)
    assert any("Strip read OK — D" in ln for ln in lines)


# ---- combined review of 4.3.35: the log line and the question agree -------
def test_the_strip_line_names_the_part_over_the_patches_the_question_uses(tmp_path):
    """The per-strip line said "moved 105 mm ... It went from the first patch
    to the last." and the question right after it "moved only about 90 mm ...
    cannot have passed over all of them". The line now gives the whole stroke
    AND the part over the patches, the very number the question shows, and
    the direction sentence says only which way the instrument moved."""
    rs, _ = _session(tmp_path, gen="i1pro3", chart=True)
    geo = rs.geometry["A"]
    n = geo["patches"]
    full = int(geo["span_mm"] / 0.5 * 1.3)
    rs.on_strip(_cut(_rec("A", full, gen="i1pro3"), n=n))
    rs.on_strip_read(_strip_read("A", n=n), other_question=False)
    lines = rs.on_strip(_cut(_rec("B", full // 4, gen="i1pro3"), n=n))
    summ = rs.on_strip_read(_strip_read("B", n=n), other_question=False)
    line = lines[-1]
    # the question's own figure (TabMeasure._prompt_ruler_not_covered)
    moved = int(round((summ["coverage_steps"] or summ["travel_steps"])
                      * summ["mm_per_step"]))
    whole = int(round(summ["travel_steps"] * summ["mm_per_step"]))
    assert f"moved {whole} mm along the ruler in all" in line, line
    assert f"about {moved} mm of it over the patches" in line, line
    assert "It went from" not in line
    assert ("It moved in the reading direction, from the first patch towards "
            "the last." in line) or ("It moved against the reading direction"
                                     in line), line


def test_the_steps_line_names_the_part_over_the_patches_too(tmp_path):
    rs, _ = _session(tmp_path)
    line = rs.on_strip(_rec("A", 340))[0]
    assert "ruler steps in all, about " in line and "of them over the patches" in line


def test_a_refused_strip_keeps_why_it_was_refused(tmp_path):
    """4.3.37: the driver's reason for a strip it could not read goes into
    the diagnostics file with the strip (the most useful case)."""
    rs, _lines = _session(tmp_path)
    rec = _rec("A", 60, result="misread")
    rec["reason"] = "Not enough patches"
    rs.on_strip(rec)
    rs.flush()
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    st = doc["strips"][0]
    assert st["verdict"] == "refused"
    assert "Not enough patches" in json.dumps(st)


# ---------------------------------------------------------------------------
# 4.3.37: the ruler and the filing disagree about the direction (i1Pro 3)
# ---------------------------------------------------------------------------
def _strip(rs, name, sign, reversed_=False, gen="i1pro3"):
    rs.on_strip(_rec(name, 300, gen=gen, sign=sign))
    return rs.on_strip_read(_strip_read(name, reversed=reversed_),
                            other_question=False)


def test_a_strip_saved_back_to_front_is_asked_about(tmp_path):
    """The tester's file in miniature: every strip scanned the same way and
    filed in order, then one scanned the same way but FILED back to front."""
    rs, _ = _session(tmp_path, gen="i1pro3")
    for s in "ABCD":
        assert not _strip(rs, s, -1)["ask_direction"]
    summ = _strip(rs, "E", -1, reversed_=True)
    assert summ["ask_direction"] and not summ["ask"]
    rs.flush()
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    assert doc["strips"][-1]["verdict"] == "asked"


def test_a_strip_scanned_the_other_way_and_filed_so_is_not_asked(tmp_path):
    """Reading some strips from the far end is allowed (bidirectional
    recognition): scanned the other way AND filed reversed agrees."""
    rs, _ = _session(tmp_path, gen="i1pro3")
    for s in "ABC":
        _strip(rs, s, -1)
    assert not _strip(rs, "D", +1, reversed_=True)["ask_direction"]
    assert not _strip(rs, "E", -1)["ask_direction"]


def test_forward_is_the_majority_not_strip_one(tmp_path):
    """A first strip that is itself the odd one out cannot set "forward"."""
    rs, _ = _session(tmp_path, gen="i1pro3")
    first = _strip(rs, "A", -1, reversed_=True)   # the odd one, first
    assert not first["ask_direction"]              # nothing to compare yet
    for s in "BCDE":
        assert not _strip(rs, s, -1)["ask_direction"]
    assert rs._majority_direction() == -1
    assert _strip(rs, "F", -1, reversed_=True)["ask_direction"]


def test_no_majority_no_question(tmp_path):
    rs, _ = _session(tmp_path, gen="i1pro3")
    for s, sign, rev in (("A", -1, False), ("B", -1, True), ("C", -1, False),
                         ("D", -1, True)):
        _strip(rs, s, sign, reversed_=rev)
    assert rs._majority_direction() == 0
    assert not _strip(rs, "E", -1, reversed_=True)["ask_direction"]


def test_the_i1pro2_is_never_asked_about_the_direction(tmp_path):
    rs, _ = _session(tmp_path, gen="i1pro2")
    for s in "ABCD":
        _strip(rs, s, -1, gen="i1pro2")
    assert not _strip(rs, "E", -1, reversed_=True, gen="i1pro2")["ask_direction"]


def test_the_direction_message_is_proposed():
    from workflow import measurement_messages as M
    m = M.CATALOGUE["M-STRIP-RULER-DIRECTION"]
    assert m.id in M.PROPOSED
    title, body = m.render(strip="9")
    assert "saved back to front" in title and "Re-read Strip" in body
    assert "ChromIQ never changes a reading by itself" in body
    assert "—" not in title + body
