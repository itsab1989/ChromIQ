"""Was a strip read twice? The live check while measuring (#182).

Knut, #182 5963903650 Q5, *"Yes."* to: *"the optional live check while
measuring, which compares each new strip with the strips already measured and
asks 'Strip D looks very like strip C, which you already measured. Did you
read strip C again?' with Re-read strip D / Keep, it is strip D"*. ``-S`` stays
on: chartread's own test compares with the chart's expected colours, which is
what misfires on low-quality paper; this one compares with what was measured.

What has to hold, and where it is proved here:

* no false alarm on real charts read correctly: Knut's run2 (648 patches) and
  run3 (324), read in order, and each of their strips read a second time where
  the reader was (a legitimate re-read never asks);
* it does fire on the real misread on file: Basti's printer-test chart of
  2026-08-08, where strip D holds strip C's readings, and not once D was read
  again;
* a strip may be one patch out or reversed, and strips the chart designed
  alike are never compared;
* only the ChromIQ engine in strip mode, never patch by patch, never under
  guided refinement, never twice for a read chartread's own wrong-strip test
  already asked about;
* the order of the windows: the question waits for any window already open,
  comes before "Continue to next / Jump to unread", and holds the move after
  the read until it is answered. "Re-read" sends the reader back to the strip.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import strip_read_twice as rt                 # noqa: E402

DATA = Path(__file__).parent / "data" / "check_refine"
sys.path.insert(0, str(Path(__file__).parent))


def _strips(name, value="xyz"):
    """{strip: [value, ...]} in place order from a fixture."""
    import re
    patches = json.loads((DATA / name).read_text(encoding="utf-8"))["patches"]
    out: dict = {}
    for loc, v in patches.items():
        m = re.match(r"^([A-Z]+)(\d+)$", loc)
        out.setdefault(m.group(1), []).append(
            (int(m.group(2)), rt.xyz_to_lab(v["xyz"]) if value == "xyz"
             else tuple(v["rgb"])))
    return {k: [x for _p, x in sorted(v)] for k, v in out.items()}


def _read_in_order(strips, design=None):
    """Read every strip in turn; return the first alarm, or None."""
    measured: dict = {}
    for s in sorted(strips, key=lambda k: (len(k), k)):
        hit = rt.looks_read_twice(s, strips[s], measured,
                                  design.get if design else None)
        if hit is not None:
            return hit
        measured[s] = strips[s]
    return None


# ---- the comparison on real data -------------------------------------------

@pytest.mark.parametrize("name", ["knut_run2.json", "knut_run2_earlier_read.json",
                                  "knut_run3.json", "knut_run3_earlier_read.json",
                                  "basti_2026-08-08_after_reread.json"])
def test_a_chart_read_correctly_never_asks(name):
    assert _read_in_order(_strips(name), _strips(name, "rgb")) is None


@pytest.mark.parametrize("now, before", [
    ("knut_run2.json", "knut_run2_earlier_read.json"),
    ("knut_run3.json", "knut_run3_earlier_read.json"),
])
def test_reading_a_strip_again_where_the_reader_is_never_asks(now, before):
    """Knut re-read whole charts: every strip, read a second time on itself,
    against the complete first measurement."""
    measured, again = _strips(before), _strips(now)
    for s, labs in again.items():
        assert rt.looks_read_twice(s, labs, measured) is None, s


def test_different_strips_are_far_apart_and_the_same_strip_is_close():
    """The numbers the threshold of 3 rests on, measured on Knut's charts."""
    for name in ("knut_run2.json", "knut_run3.json"):
        s = _strips(name)
        keys = sorted(s)
        closest = min(rt.strip_distance(s[a], s[b])
                      for i, a in enumerate(keys) for b in keys[i + 1:])
        assert closest > 25, (name, closest)
    a, b = _strips("knut_run2.json"), _strips("knut_run2_earlier_read.json")
    assert max(rt.strip_distance(a[k], b[k]) for k in a) < 1.0


def test_bastis_real_misread_is_caught():
    """2026-08-08: strip D was filed with strip C's readings."""
    hit = _read_in_order(_strips("basti_2026-08-08_strip_C_read_as_D.json"),
                         _strips("basti_2026-08-08_strip_C_read_as_D.json",
                                 "rgb"))
    assert hit is not None
    assert (hit.strip, hit.like) == ("D", "C")
    assert hit.median_de76 < 0.5


def _synthetic(n=8):
    import random
    rnd = random.Random(7)
    return {s: [(rnd.uniform(20, 90), rnd.uniform(-60, 60), rnd.uniform(-60, 60))
                for _ in range(n)] for s in "ABCDE"}


@pytest.mark.parametrize("shift, reverse", [(0, False), (1, False), (-1, False),
                                            (0, True), (1, True)])
def test_one_patch_out_or_reversed_still_matches(shift, reverse):
    s = _synthetic()
    c = list(s["C"])
    if reverse:
        c = c[::-1]
    if shift > 0:
        c = c[1:] + [(95.0, 0.0, 0.0)]
    elif shift < 0:
        c = [(95.0, 0.0, 0.0)] + c[:-1]
    measured = {k: v for k, v in s.items() if k != "D"}
    hit = rt.looks_read_twice("D", c, measured)
    assert hit is not None and hit.like == "C"


def test_a_strip_is_never_compared_with_itself():
    s = _synthetic()
    assert rt.looks_read_twice("C", s["C"], s) is None


def test_strips_designed_alike_are_left_alone():
    s = _synthetic()
    s["D"] = list(s["C"])
    design = {k: [(10.0 * i, 0.0, 0.0) for i in range(8)] for k in s}
    assert rt.looks_read_twice("D", s["D"], {"C": s["C"]}, design.get) is None
    design["D"] = [(50.0, 50.0, 50.0)] * 8
    assert rt.looks_read_twice("D", s["D"], {"C": s["C"]}, design.get) \
        is not None


def test_too_few_patches_say_nothing():
    s = _synthetic(n=3)
    assert rt.looks_read_twice("D", s["C"], {"C": s["C"]}) is None


def test_the_threshold_is_a_median_so_one_odd_patch_cannot_hide_it():
    s = _synthetic()
    c = list(s["C"])
    c[2] = (5.0, 70.0, -70.0)                    # one patch wildly off
    assert rt.looks_read_twice("D", c, {"C": s["C"]}) is not None


# ---- the manager -------------------------------------------------------------

from workflow.measure_manager import MeasureManager                # noqa: E402
from test_knut_5956210745_next_strip_after_a_read import (         # noqa: E402
    _Runner, _feed, _gotos)

STRIPS = ["A", "B", "C", "D"]
PER = 6


def _chart(tmp: Path, read=()):
    """A .ti2 of 4 strips x 6 patches with distinct design values; a .ti3
    holding *read* (strips) with readings equal to `_xyz`."""
    rows, sid = [], 1
    for s in STRIPS:
        for k in range(1, PER + 1):
            rows.append((sid, f"{s}{k}", _rgb(s, k)))
            sid += 1
    body = "\n".join(f'{i} "{loc}" {r:.1f} {g:.1f} {b:.1f}'
                     for i, loc, (r, g, b) in rows)
    ti2 = tmp / "chart.ti2"
    ti2.write_text(
        'CTI2\n\nORIGINATOR "test"\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n{body}\nEND_DATA\n",
        encoding="utf-8")
    got = [(i, loc, rgb) for i, loc, rgb in rows if loc[0] in set(read)]
    if got:
        tbody = "\n".join(
            f'{i} "{loc}" {r:.1f} {g:.1f} {b:.1f} '
            + " ".join(f"{v:.4f}" for v in _xyz(loc[0], int(loc[1:])))
            for i, loc, (r, g, b) in got)
        ti2.with_suffix(".ti3").write_text(
            'CTI3\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
            "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
            f"END_DATA_FORMAT\nNUMBER_OF_SETS {len(got)}\nBEGIN_DATA\n"
            f"{tbody}\nEND_DATA\n", encoding="utf-8")
    return ti2


def _rgb(s, k):
    i = STRIPS.index(s)
    return ((37 * i + 11 * k) % 100, (53 * i + 29 * k) % 100,
            (71 * i + 7 * k) % 100)


def _xyz(s, k):
    r, g, b = _rgb(s, k)
    return (0.4 * r + 0.35 * g + 0.2 * b + 2, 0.2 * r + 0.7 * g + 0.1 * b + 2,
            0.02 * r + 0.1 * g + 0.9 * b + 2)


def _sread(strip, like=None):
    src = like or strip
    return {"event": "strip_read", "strip": strip,
            "patches": [{"loc": f"{strip}{k}", "xyz": list(_xyz(src, k))}
                        for k in range(1, PER + 1)]}


def _sready(strip, all_done=False):
    return {"event": "strip_ready", "strip": strip, "read": True,
            "all_done": all_done}


def _mgr(tmp, *, read=(), spot=False, guided=None, question=None):
    r = _Runner()
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = spot
    m._is_resume = True
    m._chart_was_complete = False
    m._guided_state = "disabled"
    if guided:
        m._guided_strips = list(guided)
        m._guided_state = "waiting"
    if question is not None:
        m.set_question_probe(question)
    asked, unread = [], []
    m.strip_read_twice.connect(lambda s, like: asked.append((s, like)))
    m.unread_choice_wanted.connect(lambda n, mode: unread.append((n, mode)))
    ti2 = _chart(tmp, read=read)
    _feed(m, {"event": "session_start", "chart": str(ti2),
              "strips": [{"strip": s, "read": s in read} for s in STRIPS]})
    return m, r, asked, unread


def test_the_manager_asks_when_d_reads_like_c(tmp_path):
    m, r, asked, _u = _mgr(tmp_path)
    _feed(m, _sread("A"), _sready("B"), _sread("B"), _sready("C"),
          _sread("C"), _sready("D"), _sread("D", like="C"))
    assert asked == [("D", "C")]
    assert m.read_twice_pending() == ("D", "C")


def test_a_correct_read_in_order_never_asks(tmp_path):
    m, _r, asked, _u = _mgr(tmp_path)
    for s, nxt in zip(STRIPS, STRIPS[1:] + ["A"]):
        _feed(m, _sread(s), _sready(nxt))
    assert asked == []


def test_strips_already_in_the_file_count(tmp_path):
    """A resume: C is in the .ti3 being resumed, read in an earlier session."""
    m, _r, asked, _u = _mgr(tmp_path, read=("A", "B", "C"))
    _feed(m, _sread("D", like="C"))
    assert asked == [("D", "C")]


def test_reading_c_again_on_c_never_asks(tmp_path):
    m, _r, asked, _u = _mgr(tmp_path, read=("A", "B", "C"))
    _feed(m, _sread("C"), _sready("D"), _sread("C"))
    assert asked == []


def test_not_in_patch_by_patch_and_not_under_guided_refinement(tmp_path):
    m, _r, asked, _u = _mgr(tmp_path, read=("A", "B", "C"), spot=True)
    _feed(m, _sread("D", like="C"))
    assert asked == []
    m, _r, asked, _u = _mgr(tmp_path, read=("A", "B", "C"), guided=["D"])
    _feed(m, _sread("D", like="C"))
    assert asked == []


def test_not_when_chartreads_own_wrong_strip_test_already_asked(tmp_path):
    m, _r, asked, _u = _mgr(tmp_path, read=("A", "B", "C"))
    _feed(m, {"event": "strip_warning", "kind": "wrong_strip", "read": "C",
              "expected": "D"}, _sread("D", like="C"))
    assert asked == []
    _feed(m, _sready("D"), _sread("D", like="B"))      # the next read asks
    assert asked == [("D", "B")]


def test_the_move_after_the_read_waits_for_the_answer(tmp_path):
    m, r, asked, unread = _mgr(tmp_path, read=("A", "B", "C"))
    _feed(m, _sread("D", like="C"), _sready("A"))
    assert _gotos(r) == [] and unread == [], "moved or asked before the answer"
    m.release_held_strip_move()
    assert _gotos(r) == [] and unread == [], "released while still asking"


def test_reread_sends_the_reader_back_and_drops_the_held_move(tmp_path):
    m, r, _a, unread = _mgr(tmp_path, read=("A", "B", "C"))
    _feed(m, _sread("D", like="C"), _sready("A"))
    m.answer_read_twice("reread")
    m.release_held_strip_move()
    assert _gotos(r) == ["D"] and unread == []
    assert m.read_twice_pending() is None


def test_a_later_read_never_replaces_the_question_on_screen(tmp_path):
    """Review of 6de015eb: the instrument reads while the window is open. A
    second alarm used to overwrite the pending pair, so "Re-read strip D"
    pressed in the window about D sent the reader to the NEWER strip. Now the
    answer applies to the pair shown, and the newer one is asked after it."""
    m, r, asked, _u = _mgr(tmp_path, read=("A", "B", "C"))
    _feed(m, _sread("D", like="C"))                  # the window: D like C
    assert m.read_twice_pending() == ("D", "C")
    _feed(m, _sready("A"), _sread("A", like="B"))    # read while it is open
    assert asked == [("D", "C"), ("A", "B")]
    assert m.read_twice_pending() == ("D", "C"), "the shown pair was replaced"
    m.answer_read_twice("reread")
    assert _gotos(r) == ["D"], "the answer went to another strip"
    assert m.read_twice_pending() == ("A", "B"), "the newer one is asked next"
    m.answer_read_twice("keep")
    assert m.read_twice_pending() is None and _gotos(r) == ["D"]


def test_a_waiting_question_about_the_same_strip_is_not_asked_twice(tmp_path):
    m, _r, _a, _u = _mgr(tmp_path, read=("A", "B", "C"))
    _feed(m, _sread("D", like="C"), _sready("A"), _sread("A", like="B"),
          _sready("A"), _sread("A", like="C"))
    assert m._read_twice_pending == [("D", "C"), ("A", "C")]


def test_keep_lets_the_held_move_go_on(tmp_path):
    """Keep on a chart now complete: the beta-4 rule moves on after D."""
    m, r, _a, unread = _mgr(tmp_path, read=("A", "B", "C"))
    m._chart_was_complete = True
    _feed(m, _sread("D", like="C"), _sready("D"))
    m.answer_read_twice("keep")
    m.release_held_strip_move()
    assert m.read_twice_pending() is None
    assert unread == []


def test_the_unread_question_comes_after_the_read_twice_question(tmp_path):
    """C re-read as B's swipe while D is still unread: read twice first, and
    only after Keep the "Continue to next / Jump to unread" question."""
    m, r, asked, unread = _mgr(tmp_path, read=("A", "B", "C"))
    _feed(m, _sread("A", like="B"), _sready("D"))
    assert asked == [("A", "B")] and unread == []
    m.answer_read_twice("keep")
    m.release_held_strip_move()
    assert unread == [(PER, "strip")]


# ---- the tab: the window and its order ----------------------------------------

class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark", "chartread_engine": "chromiq"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    t = TabMeasure(ArgyllRunner(s), s)
    mgr = t._manager
    sent: list[str] = []
    mgr._runner.write_stdin = sent.append
    monkeypatch.setattr(type(t._runner), "is_running",
                        property(lambda self: True))
    mgr._engine_active = True
    mgr._spot_mode = False
    mgr._is_resume = True
    mgr._chart_was_complete = False
    mgr._guided_state = "disabled"
    ti2 = _chart(tmp_path, read=("A", "B", "C"))
    _feed(mgr, {"event": "session_start", "chart": str(ti2),
                "strips": [{"strip": x, "read": True} for x in STRIPS]})
    t._sent = sent
    t._session_live = True
    yield t
    t.deleteLater()


def _sent_gotos(sent):
    class _R:
        pass
    r = _R()
    r.sent = sent
    return _gotos(r)


@pytest.mark.parametrize("button, expected", [(0, ["D"]), (1, [])])
def test_the_window_asks_in_knuts_words_and_acts_on_the_answer(
        tab, qapp, monkeypatch, button, expected):
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton
    seen = []

    def _exec(dlg):
        seen.append(dlg)
        dlg.findChildren(QPushButton)[button].click()
        return 1
    monkeypatch.setattr(QDialog, "exec", _exec)
    cues = []
    monkeypatch.setattr(tab, "_cue_window", cues.append)
    _feed(tab._manager, _sread("D", like="C"))
    for _ in range(5):
        qapp.processEvents()
    assert len(seen) == 1
    dlg = seen[0]
    text = "\n".join(lbl.text() for lbl in dlg.findChildren(QLabel))
    assert dlg.windowTitle() == "Was a strip read twice?"
    assert ("Strip D looks very like strip C, which you already measured. "
            "Did you read strip C again?") in text
    assert [b.text() for b in dlg.findChildren(QPushButton)] == \
        ["Re-read strip D", "Keep, it is strip D"]
    assert cues == ["INSTRUMENT_ERROR"]
    assert _sent_gotos(tab._sent) == expected
    assert tab._manager.read_twice_pending() is None


def test_it_waits_for_a_window_already_open(tab, qapp, monkeypatch):
    """Strip Read Quickly (or any window) is up when the read arrives: the
    question opens only after it closes."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QDialog, QPushButton
    order = []
    real_exec = QDialog.exec

    def _exec(dlg):
        order.append(dlg.objectName() or "other")
        if dlg.objectName() == "strip_read_twice_window":
            dlg.findChildren(QPushButton)[1].click()
            return 1
        return real_exec(dlg)
    monkeypatch.setattr(QDialog, "exec", _exec)
    monkeypatch.setattr(tab, "_cue_window", lambda *_a: None)
    other = QDialog(tab)

    def _inside():
        _feed(tab._manager, _sread("D", like="C"), _sready("A"))
        for _ in range(5):
            qapp.processEvents()
        order.append("still only the first window")
        other.accept()
    QTimer.singleShot(0, _inside)
    tab._exec_measurement_window(other)
    for _ in range(10):
        qapp.processEvents()
    assert order == ["other", "still only the first window",
                     "strip_read_twice_window"], order


def test_the_session_ending_first_drops_the_question(tab, qapp, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    opened = []
    monkeypatch.setattr(QDialog, "exec", lambda dlg: opened.append(dlg) or 0)
    _feed(tab._manager, _sread("D", like="C"))
    tab._session_live = False
    for _ in range(5):
        qapp.processEvents()
    assert opened == []
    assert tab._manager.read_twice_pending() is None


# ---- the real engine, on its replay instrument ------------------------------

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402


@pytest.mark.slow
@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_the_engine_files_c_as_d_and_the_check_sees_it(tmp_path):
    """The real helper, -S as ChromIQ runs it: C's readings swiped while the
    reader is on D are accepted and filed as D, and the strip_read event the
    app receives carries what the check needs to say so."""
    targen = shutil.which("targen") or "/Applications/Argyll/bin/targen"
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    base = tmp_path / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f60", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=True)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)
    r = _Runner()
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = False
    m._is_resume = False
    m._guided_state = "disabled"
    asked = []
    m.strip_read_twice.connect(lambda s, like: asked.append((s, like)))
    s = ReplaySession(base, replay, ["-S"])
    try:
        start = s.wait_event("session_start")
        _feed(m, start)
        labels = [x["strip"] for x in start["strips"]]
        assert len(labels) >= 3
        for k, lab in enumerate(labels[:3]):
            i = s.event_index()
            s.send(cmd="swipe", **({"as": labels[1]} if k == 2 else {}))
            ev = s.wait_event("strip_read", after=i)
            _feed(m, ev)
            s.wait_event("strip_ready", after=i)
    finally:
        s.proc.kill()
        s.finish()
    assert asked == [(labels[2], labels[1])]
