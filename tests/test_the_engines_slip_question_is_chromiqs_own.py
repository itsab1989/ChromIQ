"""The engine's whole-strip net (#50) asks ChromIQ's own question (4.3.11).

`cq_detect_misalign` in native/chartread_helper/chromiq_chartread.c sends
``strip_misaligned`` with the shift and two CIE76 means and nothing else. The
Measure tab used to word that itself: "the average colour error drops from
{base} to {best} ΔE" (CIE76, called ΔE beside ChromIQ's ΔE00 texts), and
"the last one reads the empty paper" for every slip, although a strip read
LATE (the reader started on the paper) has the paper in its FIRST patch.

Now `MeasureManager._engine_slip_finding` describes the finding the way the
part-of-a-strip check does, from the strip's own readings (the strip_read
event comes first): the patches named, ΔE00 averaged over exactly them, and
the right direction; the tab asks M-STRIP-WHOLE-SLIPPED-LATE / -EARLY, or
M-STRIP-WHOLE-SLIPPED-TWO-LATE / -EARLY for a shift of two.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_149786_part_of_a_strip_slipped import (  # noqa: E402
    _event, _manager, _paper, _strips, _tab_seeing)
from test_knut_5956210745_next_strip_after_a_read import _feed  # noqa: E402

from workflow import measurement_messages as M  # noqa: E402
from workflow.slipped_strip import (strip_read_labs,  # noqa: E402
                                    whole_strip_shift, _de00)

ROOT = Path(__file__).resolve().parents[1]


def _net(strip, offset, other=False):
    return {"event": "strip_misaligned", "strip": strip, "offset": offset,
            "base_de": 61.2, "best_de": 9.4,
            "other_direction": other}


def _engine_flagged(strip_label, strip, meas):
    ev = _event(strip_label, strip, meas)
    ev["misaligned"] = 1          # the engine's net flagged it in strip_read
    return ev


def _asked(m, *events):
    part, net = [], []
    m.strip_partly_misaligned.connect(lambda f: part.append(f))
    m.strip_misaligned.connect(lambda *a: net.append(a))
    _feed(m, *events)
    return part, net


def test_a_late_slip_names_the_first_patch_as_the_paper(qapp):
    """MUTATION: drop the `strip_partly_misaligned.emit` in the
    strip_misaligned branch of MeasureManager: nothing asks ChromIQ's
    question, and the old window is gone."""
    m = _manager()
    m._safenet_on = True
    strip = _strips()["K"]
    meas = [mx for _l, mx, _e in strip]
    late = [_paper()] + meas[:-1]
    part, _net_q = _asked(m, _engine_flagged("K", strip, late), _net("K", 1))
    assert len(part) == 1
    f = part[0]
    assert f["whole"] and f["engine"] and f["offset"] == 1
    assert (f["lead"], f["lead_paper"]) == (strip[0][0], True)
    assert (f["first"], f["last"]) == (strip[1][0], strip[-1][0])
    # ΔE00, averaged over exactly the named patches
    m_lab, e_lab = strip_read_labs(_event("K", strip, late)["patches"])
    own = [_de00(m_lab[i], e_lab[i]) for i in range(1, len(strip))]
    shifted = [_de00(m_lab[i], e_lab[i - 1]) for i in range(1, len(strip))]
    assert f["base"] == pytest.approx(sum(own) / len(own), abs=0.06)
    assert f["best"] == pytest.approx(sum(shifted) / len(shifted), abs=0.06)
    assert f["best"] <= 0.5 * f["base"]


def test_an_early_slip_names_the_last_patch(qapp):
    m = _manager()
    m._safenet_on = True
    strip = _strips()["K"]
    meas = [mx for _l, mx, _e in strip]
    early = meas[1:] + [_paper()]
    part, _n = _asked(m, _engine_flagged("K", strip, early), _net("K", -1))
    f = part[0]
    assert f["whole"] and f["offset"] == -1
    assert (f["lead"], f["lead_paper"]) == (strip[-1][0], True)
    assert (f["first"], f["last"]) == (strip[0][0], strip[-2][0])


def test_two_patches_late_is_measured_as_the_engine_found_it(qapp):
    m = _manager()
    m._safenet_on = True
    strip = _strips()["K"]
    meas = [mx for _l, mx, _e in strip]
    late2 = [_paper(), _paper()] + meas[:-2]
    part, _n = _asked(m, _engine_flagged("K", strip, late2), _net("K", 2))
    f = part[0]
    assert f["whole"] and f["offset"] == 2 and f["shift"] == 2
    assert (f["first"], f["last"]) == (strip[2][0], strip[-1][0])
    assert f["best"] <= 0.5 * f["base"]


def test_without_the_strips_readings_it_still_asks(qapp):
    m = _manager()
    m._safenet_on = True
    part, _n = _asked(m, _net("Q", 1))
    assert part and part[0]["whole"] and part[0]["base"] is None


def test_whole_strip_shift_reads_the_direction_from_the_offset():
    strip = _strips()["K"]
    meas = [mx for _l, mx, _e in strip]
    m_lab, e_lab = strip_read_labs(
        _event("K", strip, [_paper()] + meas[:-1])["patches"])
    run = whole_strip_shift(m_lab, e_lab, 1)
    assert (run.lead, run.lead_paper, run.kind) == (0, True, "start")
    assert run.covers(len(strip))
    m_lab, e_lab = strip_read_labs(
        _event("K", strip, meas[1:] + [_paper()])["patches"])
    run = whole_strip_shift(m_lab, e_lab, -1)
    assert (run.lead, run.lead_paper, run.kind) == (len(strip) - 1, True, "end")


@pytest.mark.parametrize("offset,message,lost", [
    (1, M.M_STRIP_WHOLE_SLIPPED_LATE, "the colour of its last patch was not read at all"),
    (-1, M.M_STRIP_WHOLE_SLIPPED_EARLY, "the colour of its first patch was not read at all"),
    (2, M.M_STRIP_WHOLE_SLIPPED_TWO_LATE, "the colours of its last two patches were not read at all"),
    (-2, M.M_STRIP_WHOLE_SLIPPED_TWO_EARLY, "the colours of its first two patches were not read at all"),
])
def test_the_tab_asks_the_question_for_the_direction(qapp, monkeypatch,
                                                     offset, message, lost):
    tab, seen = _tab_seeing(monkeypatch)
    tab._on_strip_partly_misaligned({
        "strip": "K", "offset": offset, "reversed": False, "whole": True,
        "engine": True, "shift": abs(offset), "first": "K2", "last": "K14",
        "lead": "K1", "lead_paper": True, "base": 40.04, "best": 1.46})
    text = " ".join(seen["labels"])
    title, _b = message.render(strip="K", first="", last="", lead_line="",
                               base="", best="", remeasure="", keep="",
                               stop="")
    assert title in text
    assert lost in text
    assert "40.0 ΔE00" in text and "1.5 ΔE00" in text
    assert "empty paper" not in text
    tab.deleteLater()


def test_the_old_window_is_gone():
    src = (ROOT / "ui" / "tabs" / "tab_measure.py").read_text(encoding="utf-8")
    assert "def _on_strip_misaligned" not in src
    assert "strip_misaligned.connect" not in src
    assert "may have been read slightly out of alignment" not in src


def test_the_engine_still_sends_only_numbers():
    """The engine's own text never reaches the user: it sends an event, and
    the words are ChromIQ's. If prose about the slip appears in the C file,
    this test asks for it to be worded in the GUI instead."""
    c = (ROOT / "native" / "chartread_helper" / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="replace")
    i = c.index('"{\\"event\\":\\"strip_misaligned\\"')
    block = c[i - 600:i + 400]
    assert "empty paper" not in block and "misaligned" in block
