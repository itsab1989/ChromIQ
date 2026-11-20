"""4.3.52: a dual scan's first pass that did not read is said at once.

pharmacist (thread 17593, posts 150398 / 150400) asked for the i1Pro 2 to
blink red as soon as the first pass of a dual scan was bad. i1Profiler does
not do that (red only after the return pass, recording of 2026-11-17) and the
return pass is needed (it closes the ruler stream), so nothing is sent to the
instrument for it. The Measure tab says it at once instead: its own status
line headline (M-DUAL-PASS-TWO-UNREAD) and the "Strip read failed" sound,
once, when the engine asks for pass 2 with lamp_ok false. A first pass that
read plays nothing at that moment.

The blue "scan back" pulse itself was not built: analysis_pulse.txt of the
2026-11-20_pulse452 work folder.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _Sound:
    def __init__(self):
        self.played = []

    def play(self, event):
        self.played.append(event)

    def play_window(self, event):
        self.played.append(event)


def _live_tab(tmp_path):
    from tests.test_b202_the_i1pro_generation_is_read_right import _tab
    tab = _tab(tmp_path)
    tab._dual_reset()
    tab._dual_live = True
    tab._sound = _Sound()
    return tab


def test_a_bad_first_pass_has_its_own_headline_and_the_failure_sound(qapp, tmp_path):
    import core.sound as snd
    tab = _live_tab(tmp_path)
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": False})
    assert tab._sound.played == [snd.STRIP_FAIL]
    assert tab._status_bar_lbl.text() == (
        "Strip A: pass 1 did not read. Read pass 2 anyway")
    assert "The first pass of this strip did not read" in tab._log.toPlainText()
    tab.close()


def test_a_good_first_pass_plays_nothing_and_keeps_its_headline(qapp, tmp_path):
    tab = _live_tab(tmp_path)
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": True})
    assert tab._sound.played == []
    assert tab._status_bar_lbl.text() == "Strip A, pass 2 of 2 (UV light)"
    tab.close()


def test_without_the_sound_object_nothing_fails(qapp, tmp_path):
    tab = _live_tab(tmp_path)
    tab._sound = None
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": False})
    assert "did not read" in tab._status_bar_lbl.text()
    tab.close()


def test_the_two_headlines_differ_and_carry_no_em_dash():
    from workflow import measurement_messages as M
    good = M.M_DUAL_PASS_TWO.render(strip="A")[0]
    bad = M.M_DUAL_PASS_TWO_UNREAD.render(strip="A")[0]
    assert good != bad
    assert "pass 1 did not read" in bad
    assert "—" not in bad
    assert not M.M_DUAL_PASS_TWO_UNREAD.approved, "stays PROPOSED (§M)"


def test_the_sound_is_in_the_help_table_and_the_specification():
    from pathlib import Path
    from core.measure_windows import EVENT_ROWS
    row = [r for r in EVENT_ROWS if "first pass of a dual scan" in r[0]]
    assert row and row[0][2] == "Strip read failed"
    doc = (Path(__file__).resolve().parent.parent / "docs" / "design"
           / "measurement_window_sounds.md").read_text(encoding="utf-8")
    sec = doc.split("## 4l.")[1].split("\n## ")[0]
    assert "Awaiting confirmation" in sec and "nobody yet" in sec
    # review S6: the plain table of section 2 does not read as confirmed
    line = next(ln for ln in doc.splitlines() if ln.startswith("| " + row[0][0]))
    assert "*(awaiting confirmation, 4l)*" in line


@pytest.mark.parametrize("code", ["de", "es", "fr", "it", "ja", "nl", "no",
                                  "pl", "pt", "ru", "sv", "uk", "zh_CN"])
def test_both_new_texts_are_translated(code):
    import json
    from pathlib import Path
    d = json.loads((Path(__file__).resolve().parent.parent / "data" / "i18n"
                    / f"{code}.json").read_text(encoding="utf-8"))
    head = d["Strip {strip}: pass 1 did not read. Read pass 2 anyway"]
    assert "{strip}" in head
    assert d["The first pass of a dual scan strip did not read (i1Pro 2, Beta)"]
