"""Forum post 149786: part of a strip read one patch out of place.

jctay's i1Pro 3 read strip 36 of a 585-patch verification chart (ChromIQ
4.3.8/4.3.9, From Profile Gamut, Windows) with patches 36A to 36H one patch
late: 36A read the paper, and the MEASURED colour of each of 36B to 36H is
the EXPECTED colour of the patch before it (sampled from his report's Worst
patches table). From 36I on the strip was in step again, so the engine's
safety net, which only tries shifting the WHOLE strip (`cq_detect_misalign`),
fitted badly at every offset and said nothing. The report then showed eight
patches with ΔE00 17 to 66 and did not say why; Knut read it as the report
pairing the wrong colours.

These tests hold four things to that:

1. `workflow.slipped_strip.find_slipped_run` finds such a run, on REAL
   readings (Basti's ET-8550 verification, `tests/data/...`), and stays quiet
   on the same strips read correctly;
2. the measuring session marks such a strip ``misaligned`` (so its readings
   confirm nothing, #210) and asks about it, but only with the warning on and
   only when the engine's own net did not already speak;
3. the Measure tab's question and the report's paragraph render the proposed
   catalogue texts with the strip and the patches named;
4. a stored measurement with a slipped strip names it in the report, and the
   same measurement as read names nothing.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M          # noqa: E402
from workflow.slipped_strip import (find_slipped_run,      # noqa: E402
                                    slipped_run_in_strip_read, xyz_to_lab)

ROOT = Path(__file__).resolve().parents[1]
ET = ROOT / "tests/data/g_basti_et8550_run1_verify"
STEM = "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify"


def _rows(path: Path) -> "dict[str, dict]":
    fmt: list = []
    rows: dict = {}
    st = 0
    for ln in path.read_text(encoding="latin-1").splitlines():
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            st = 1
            continue
        if s == "END_DATA_FORMAT":
            st = 0
            continue
        if st == 1:
            fmt += s.split()
            continue
        if s == "BEGIN_DATA":
            st = 2
            continue
        if s == "END_DATA":
            st = 0
            continue
        if st == 2 and s:
            d = dict(zip(fmt, s.split()))
            rows[d["SAMPLE_LOC"].strip('"')] = d
    return rows


def _xyz(d):
    return [float(d["XYZ_X"]), float(d["XYZ_Y"]), float(d["XYZ_Z"])]


def _strips():
    """{strip letter: [(loc, measured xyz, expected xyz)]} in strip order, of
    Basti's real ET-8550 verification read through its own chart."""
    t2, t3 = _rows(ET / f"{STEM}.ti2"), _rows(ET / f"{STEM}.ti3")
    out: dict = {}
    for loc in t3:
        m = re.fullmatch(r"([A-Z]+)(\d+)", loc)
        if m and loc in t2:
            out.setdefault(m.group(1), []).append(
                (int(m.group(2)), loc, _xyz(t3[loc]), _xyz(t2[loc])))
    return {k: [(loc, mx, ex) for _n, loc, mx, ex in sorted(v)]
            for k, v in out.items()}


def _paper():
    t3 = _rows(ET / f"{STEM}.ti3")
    return max((_xyz(d) for d in t3.values()), key=lambda x: x[1])


def _slip(strip, k):
    """jctay's slip: the paper read as patch 1, patches 1..k one late, the
    real patch k lost, and from k+1 on the strip in step again."""
    meas = [mx for _l, mx, _e in strip]
    return [_paper()] + meas[:k - 1] + meas[k:]


def _event(strip_label, strip, meas):
    return {"event": "strip_read", "strip": strip_label, "misaligned": 0,
            "patches": [{"loc": loc, "xyz": mx, "exyz": ex}
                        for (loc, _m, ex), mx in zip(strip, meas)]}


# ---- 1. the check ------------------------------------------------------------

def test_jctays_slip_is_found_on_a_real_strip():
    strip = _strips()["K"]
    run = slipped_run_in_strip_read(_event("K", strip, _slip(strip, 8))
                                    ["patches"])
    assert run is not None
    assert run.offset == 1                   # each reading is the patch BEFORE
    assert (strip[run.first][0], strip[run.last][0]) == ("K1", "K8")
    assert run.shifted_de <= 0.5 * run.base_de


def test_no_real_strip_read_correctly_is_named():
    """The other half, on every strip of a real verification: as read,
    nothing may look shifted."""
    for label, strip in _strips().items():
        assert slipped_run_in_strip_read(
            _event(label, strip, [mx for _l, mx, _e in strip])["patches"]) \
            is None, label


def test_the_whole_strip_rule_alone_misses_it():
    """WHY this exists: the engine's net asks only whether the whole strip
    fits better shifted, and a strip half slipped and half in step does not.
    Its rule, transcribed from cq_detect_misalign, on the same strip."""
    strip = _strips()["K"]
    val = [xyz_to_lab(x) for x in _slip(strip, 8)]
    exp = [xyz_to_lab(e) for _l, _m, e in strip]
    import math
    n = len(val)

    def mean_at(off, rev):
        d = []
        for i in range(n):
            ix = i + off
            if rev:
                ix = n - 1 - ix
            if 0 <= ix < n:
                d.append(math.dist(val[ix], exp[i]))
        return sum(d) / len(d), len(d)
    base, _ = mean_at(0, False)
    best = min((mean_at(o, r)[0] for r in (False, True)
                for o in (-2, -1, 1, 2) if mean_at(o, r)[1] >= n - 3))
    assert not (base >= 12 and best <= 35 and best <= 0.5 * base)


def test_a_run_needs_four_patches_and_distinct_neighbours():
    exp = [(50.0 + 30 * (i % 2), 40.0 * ((i * 7) % 3 - 1), 0.0)
           for i in range(10)]
    three = [exp[0]] + [exp[0], exp[1], exp[2]] + exp[4:]     # 3 late, healed
    assert find_slipped_run(three, exp) is None
    ramp = [(10.0 + i, 0.0, 0.0) for i in range(10)]          # 1 dE steps
    assert find_slipped_run([ramp[0]] + ramp[:-1], ramp) is None


# ---- 2. the measuring session ---------------------------------------------------

def _manager():
    from workflow.measure_manager import MeasureManager
    sys.path.insert(0, str(Path(__file__).parent))
    from test_knut_5956210745_next_strip_after_a_read import _Runner
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._guided_state = "disabled"
    return m


def test_the_session_flags_the_strip_and_asks(qapp):
    from test_knut_5956210745_next_strip_after_a_read import _feed
    m = _manager()
    m._safenet_on = True
    strip = _strips()["K"]
    asked, judged = [], []
    m.strip_partly_misaligned.connect(lambda *a: asked.append(a))
    m.strip_measured.connect(lambda ev: judged.append(int(ev["misaligned"])))
    _feed(m, _event("K", strip, _slip(strip, 8)))
    assert judged == [1], "the judge must see the strip as slipped (#210)"
    assert len(asked) == 1
    s, off, first, last, base, best = asked[0]
    assert (s, off, first, last) == ("K", 1, "K1", "K8")
    assert float(best) < float(base)


def test_off_when_the_warning_is_off(qapp):
    m = _manager()
    m._safenet_on = False
    strip = _strips()["K"]
    ev = _event("K", strip, _slip(strip, 8))
    assert m._check_part_of_strip_slipped(ev, ev["patches"]) is None
    assert ev["misaligned"] == 0


def test_the_engines_own_finding_is_not_asked_twice(qapp):
    m = _manager()
    m._safenet_on = True
    strip = _strips()["K"]
    ev = _event("K", strip, _slip(strip, 8))
    ev["misaligned"] = -1
    assert m._check_part_of_strip_slipped(ev, ev["patches"]) is None
    assert ev["misaligned"] == -1


def test_the_safenet_switch_reaches_the_manager():
    src = (ROOT / "workflow/measure_manager.py").read_text(encoding="utf-8")
    assert 'self._safenet_on     = bool(getattr(params, "engine_safenet"' in src


# ---- 3. the texts ----------------------------------------------------------------

def test_the_measure_tab_asks_with_the_proposed_text(qapp, monkeypatch):
    from PyQt6.QtWidgets import QLabel, QPushButton
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    seen = {}

    def grab(dlg):
        seen["labels"] = [lb.text() for lb in dlg.findChildren(QLabel)]
        seen["buttons"] = [b.text() for b in dlg.findChildren(QPushButton)]
        return 0
    monkeypatch.setattr(tab, "_exec_measurement_window", grab)
    went = []
    monkeypatch.setattr(tab._manager, "goto_strip", went.append)
    tab._on_strip_partly_misaligned("36", 1, "36A", "36H", "48.9", "2.1")
    text = " ".join(seen["labels"])
    title, _body = M.M_STRIP_PART_SLIPPED_LATE.render(
        strip="36", first="36A", last="36H", base="48.9", best="2.1",
        remeasure="x", keep="y", stop="z")
    assert title in text
    assert "Patches 36A to 36H of strip 36" in text
    assert "before them" in text
    assert seen["buttons"][:2] == ["Re-measure this strip", "Keep it"]
    assert went == []                          # "Keep it" is the default
    tab.deleteLater()


def test_the_early_case_has_its_own_words():
    _t, late = M.M_STRIP_PART_SLIPPED_LATE.render(
        strip="1", first="1A", last="1D", base="1", best="1",
        remeasure="r", keep="k", stop="s")
    _t, early = M.M_STRIP_PART_SLIPPED_EARLY.render(
        strip="1", first="1A", last="1D", base="1", best="1",
        remeasure="r", keep="k", stop="s")
    assert "before them" in late and "after them" in early


# ---- 4. the report ---------------------------------------------------------------

def _copy(tmp_path) -> Path:
    d = tmp_path / "et"
    shutil.copytree(ET, d)
    return d / f"{STEM}.ti3"


def _slip_ti3(ti3: Path, strip_letter: str, k: int) -> None:
    text = ti3.read_text(encoding="latin-1").split("\n")
    strip = _strips()[strip_letter]
    new = _slip(strip, k)
    by_loc = {loc: xyz for (loc, _m, _e), xyz in zip(strip, new)}
    fmt: list = []
    st = 0
    for n, ln in enumerate(text):
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            st = 1
            continue
        if s == "END_DATA_FORMAT":
            st = 0
            continue
        if st == 1:
            fmt += s.split()
            continue
        if s == "BEGIN_DATA":
            st = 2
            continue
        if s == "END_DATA":
            st = 0
            continue
        if st == 2 and s:
            parts = s.split()
            loc = parts[fmt.index("SAMPLE_LOC")].strip('"')
            if loc in by_loc and by_loc[loc] is not None:
                i = fmt.index("XYZ_X")
                parts[i:i + 3] = [f"{v:.6f}" for v in by_loc[loc]]
                # the spectrum would disagree with the XYZ; the report reads XYZ
                text[n] = " ".join(parts)
    ti3.write_text("\n".join(text), encoding="latin-1")


def test_the_report_names_nothing_on_a_good_measurement(tmp_path):
    from workflow.measurement_report import build_report
    r = build_report(_copy(tmp_path))
    assert r.get("worst_patches")
    assert "shifted_strips" not in r


def test_the_report_names_the_slipped_strip(tmp_path):
    from workflow.measurement_report import build_report
    ti3 = _copy(tmp_path)
    _slip_ti3(ti3, "K", 8)
    r = build_report(ti3)
    found = r.get("shifted_strips")
    assert found and len(found) == 1
    f = found[0]
    assert (f["strip"], f["first"], f["last"], f["offset"]) == \
        ("K", "K1", "K8", 1)
    # ...and those are the worst patches the reader sees
    top = {w["loc"] for w in r["worst_patches"][:8]}
    assert top == {f"K{i}" for i in range(1, 9)}


def test_the_report_window_says_it_above_the_worst_patches(qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    r = {"created": "2026-10-22T18:51:24",
         "shifted_strips": [{"strip": "36", "first": "36A", "last": "36H",
                             "offset": 1, "patches": 8, "base_de": 48.93,
                             "shifted_de": 2.05}]}
    # it reads nothing of the window, so it is called without one
    html_ = MeasurementReportDialog._shifted_strips_html(None, r)
    title, _b = M.M_REPORT_STRIP_SHIFTED_LATE.render(
        strip="36", first="36A", last="36H", base="48.93", best="2.05")
    assert title in html_ and "36A to 36H" in html_
    assert MeasurementReportDialog._shifted_strips_html(None, {}) == ""
    src = (ROOT / "ui/dialogs/measurement_report_dialog.py").read_text(
        encoding="utf-8")
    i = src.index("parts.append(self._shifted_strips_html(r))")
    assert i < src.index('html.escape(tr("Worst patches"))'), \
        "the paragraph goes above the Worst patches table"


# ---- 5. Knut's question: is it ChromIQ's counting? ---------------------------

def _jctay_chart(tmp: Path, randomize: bool) -> Path:
    """jctay's chart as his log describes it (forum logs, 2026-10-17): i1Pro,
    4x6 in, patch first, margins T5.5 R4 B1 L5, numbered strips; the engine
    said 585 patches, 13 a strip, 9 strips a sheet. 576 colours, so the
    engine pads the last strip with 9 paper squares (45E..45M)."""
    import random
    from workflow.i1profiler_import import RgbPatch, write_ti1
    from workflow.layout_engine.chart import build_chart
    rnd = random.Random(576)
    write_ti1([RgbPatch(rnd.uniform(0, 100), rnd.uniform(0, 100),
                        rnd.uniform(0, 100)) for _ in range(576)],
              tmp / "jc.ti1")
    build_chart(tmp / "jc.ti1", tmp / "jc", instrument="i1", paper="4x6",
                layout_mode="patch_first", margins=(5.5, 4.0, 1.0, 5.0),
                clip_border_width=20.0, patch_w=8.0, patch_h=8.2,
                strip_pattern="0-9,@-9,@-9;1-999", patch_pattern="A-Z, A-Z",
                randomize=randomize, seed=149786)
    return tmp / "jc.ti2"


@pytest.mark.parametrize("randomize", [False, True])
def test_a_perfect_read_of_jctays_chart_files_every_reading_under_its_own_patch(
        tmp_path, randomize):
    """Knut (149787) read the one-patch chain as a counting error in ChromIQ,
    with the 9 padding squares of a 576-patch chart as the suspect. A PERFECT
    read through the real engine (every reading is its patch's own expected
    value) must store every reading under its own patch, padding included,
    and flag nothing. It does; so the chain on strip 36 came from the swipe."""
    sys.path.insert(0, str(Path(__file__).parent / "helpers"))
    from replay_tools import HELPER, ReplaySession
    if not Path(HELPER).exists():
        pytest.skip("the ChromIQ engine helper is unavailable")
    import time
    from workflow.layout_engine.labels import labels_for_chart, location_key
    ti2 = _jctay_chart(tmp_path, randomize)
    text = ti2.read_text(encoding="latin-1")
    assert 'STEPS_IN_PASS "13"' in text and 'PASSES_IN_STRIPS2 "9,9,9,9,9"' in text
    rows2 = _rows(ti2)
    assert len(rows2) == 585
    cl = labels_for_chart(ti2)
    strips: dict = {}
    for loc, d in rows2.items():
        s, p = location_key(cl, loc)
        strips.setdefault(s, {})[p] = _xyz(d)
    rp = tmp_path / "replay.txt"
    with rp.open("w", encoding="utf-8") as f:
        f.write("PATCHES 13\n")
        for s in sorted(strips):
            f.write(f"STRIP {cl.strip(s)}\n")
            for p in range(13):
                f.write("%.5f %.5f %.5f\n" % tuple(strips[s][p]))
    with ReplaySession(ti2.with_suffix(""), rp, extra_args=["--safenet"]) as sess:
        sess.wait_event("session_start", timeout=20)
        for _ in strips:
            idx = sess.event_index()
            sess.send(cmd="swipe")
            end = time.time() + 20
            while time.time() < end and not any(
                    e.get("event") == "strip_read" for e in sess.events[idx:]):
                if any(e.get("event") == "strip_warning"
                       for e in sess.events[idx:]):
                    sess.send(cmd="ok")
                time.sleep(0.02)
            sess.wait_event("saved", after=idx, timeout=20)
        sess.send(cmd="done")
        sess.wait_event("done", timeout=20)
        events = list(sess.events)
    assert not [e for e in events if e.get("event") == "strip_misaligned"]
    got = _rows(ti2.with_suffix(".ti3"))
    assert set(got) == set(rows2)
    worst = max(max(abs(a - b) for a, b in zip(_xyz(got[loc]), _xyz(rows2[loc])))
                for loc in rows2)
    assert worst < 1e-3, worst
    for ev in events:
        if ev.get("event") == "strip_read":
            for p in ev["patches"]:
                assert max(abs(a - b) for a, b in zip(p["xyz"], p["exyz"])) < 1e-3


def test_the_session_judges_with_the_tabs_expected_colours(qapp):
    """On screen, jctay's chart rebuilt: against the chart's DESIGN colours
    his strip-36 slip fitted its neighbours at 37 ΔE (the bar is 35) and went
    unseen; against the profile's prediction, which the Measure tab judges a
    verification with, it fits at 0.2. So the check asks the tab."""
    m = _manager()
    m._safenet_on = True
    strip = _strips()["K"]
    ev = _event("K", strip, _slip(strip, 8))
    real = {p["loc"]: list(p["exyz"]) for p in ev["patches"]}
    for p in ev["patches"]:               # the engine's own: useless here
        p["exyz"] = [40.0, 42.0, 35.0]
    assert m._check_part_of_strip_slipped(dict(ev), ev["patches"]) is None

    def tab_expected(patches):
        return [dict(p, exyz=real[p["loc"]]) for p in patches]
    m.set_expected_for_slip_check(tab_expected)
    got = m._check_part_of_strip_slipped(ev, ev["patches"])
    assert got is not None and got[:4] == ("K", 1, "K1", "K8")


def test_the_measure_tab_hands_its_expected_colours_over():
    src = (ROOT / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    assert "self._manager.set_expected_for_slip_check(self._with_expected)" in src


def test_a_run_that_is_the_whole_strip_asks_the_whole_strip_question(qapp):
    """Agent 14 review: when the engine's net misses a WHOLE-strip slip (it
    judges with the design colours; a verification is judged against the
    profile's prediction), the run check finds every patch of the strip. The
    part-of-a-strip question would then say "The rest of the strip was read
    correctly", which is untrue: there is no rest. Such a finding asks the
    whole-strip question (`strip_misaligned`) instead, and still marks the
    strip as slipped for #210."""
    from test_knut_5956210745_next_strip_after_a_read import _feed
    m = _manager()
    m._safenet_on = True
    strip = _strips()["K"]
    meas = [mx for _l, mx, _e in strip]
    whole = [_paper()] + meas[:-1]          # every reading one patch late
    part, whole_q, judged = [], [], []
    m.strip_partly_misaligned.connect(lambda *a: part.append(a))
    m.strip_misaligned.connect(lambda *a: whole_q.append(a))
    m.strip_measured.connect(lambda ev: judged.append(int(ev["misaligned"])))
    _feed(m, _event("K", strip, whole))
    assert part == [], "a whole-strip slip must not claim the rest was right"
    assert len(whole_q) == 1 and whole_q[0][:2] == ("K", 1)
    assert float(whole_q[0][3]) < float(whole_q[0][2])
    assert judged == [1]
    # ...and a slip that heals half way still asks the part-of-a-strip one
    part.clear(), whole_q.clear()
    _feed(m, _event("K", strip, _slip(strip, 8)))
    assert len(part) == 1 and whole_q == []
