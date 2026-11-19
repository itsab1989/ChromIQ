"""The i1Pro 2 dual scan by hand: four gaps closed for 4.3.49
(analysis ~/Desktop/ChromIQ-work/2026-11-19_dual_gaps/DUAL_GAPS.md).

Each test below was written first and failed on v4.3.48 (6174bb4d8), except
the ones marked CHARACTERISATION, which pin what already held:

1. While the second pass (UV light) of a strip is due, nothing may silently end
   M1 and M2. A jump (a click on the preview, a navigation key, "I read strip
   B", turn round) is HELD, not sent, and the Measure tab says why
   (M-DUAL-PASS-HELD); the helper holds such a command too (belt and braces)
   and keeps waiting for the UV pass, and its calibration gate is closed during
   the wait, so a requested calibration runs at the next strip prompt. The open
   first pass cannot be discarded cleanly: its ruler stream is closed only by
   the UV pass's trigger ("ruler end", 0x0209), the only recorded form.
2. A dual calibration that cannot give M1 / M2 no longer ends them at the first
   strip: that strip is read as a plain lamp scan (no ruler stream, so no
   second pass), refused ONCE per calibration with "calibrate again"
   (M-DUAL-CAL-AGAIN); read again without a new calibration, it is kept as M0
   and M1 / M2 end as before (the way out).
3. A Continue Measurement whose resume the engine refuses keeps the dual-scan
   header in the main file, with CHROMIQ_DUAL_ENDED "resume" (gap 3b).
4. "High resolution spectral mode (-H)" with the dual scan by hand is refused
   before START (M-DUAL-HIGHRES-REFUSED), as the i1iO table refuses it.

With the Beta off, nothing of this runs (the last tests).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M          # noqa: E402
from workflow.dual_scan import session as D             # noqa: E402
from workflow.dual_scan import storage                  # noqa: E402
from workflow.dual_scan.reasons import REASONS          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "native" / "chartread_helper"
SIM = ROOT / "tests" / "helpers" / "dual_sim_helper.py"
CAPS = frozenset({storage.CAPABILITY, storage.DEVICE_CAPABILITY,
                  "i1pro3_conditions"})


class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def _on(**kw):
    return _S({"i1pro3_conditions_beta": True, D.SETTING: True, **kw})


def _code(text: str) -> str:
    """C source without its comments."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# ------------------------------------------------------------ the manager

class _Runner:
    def __init__(self):
        self.sent, self.is_running = [], True

    def write_stdin(self, text):
        self.sent.append(text)


def _manager(qapp):
    from workflow.measure_manager import MeasureManager
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._guided_state = "disabled"
    return m


def _line(m, text):
    m._handle_engine_line(text, lambda _l: None)


def _sent(m) -> "list[str]":
    return [s for s in m._runner.sent]


def _to_the_second_pass(m, strip="A"):
    _line(m, '{"event":"strip_ready","strip":"%s"}' % strip)
    _line(m, '{"event":"scan_started"}')
    _line(m, '{"event":"dual_pass","strip":"%s","pass":"uv","of":2,'
             '"lamp_ok":true}' % strip)


def test_1_a_jump_while_the_second_pass_is_due_is_held_not_sent(qapp):
    m = _manager(qapp)
    held = []
    m.dual_pass_held.connect(held.append)
    _to_the_second_pass(m, "A")
    m._runner.sent.clear()
    m.user_goto_strip("C")                 # a click on the preview
    m.goto_patch("C3")
    for key in ("f", "b", "n", "F"):       # navigation keys
        m.send_key(key)
    m.file_strip_as("A", "B") if hasattr(m, "file_strip_as") else None
    assert not any('"goto"' in s or '"forward"' in s or '"back"' in s
                   or '"next_unread"' in s or '"file_as"' in s
                   for s in _sent(m)), _sent(m)
    assert held and set(held) == {"A"}


def test_1_stop_and_finishing_still_reach_the_engine_during_the_wait(qapp):
    m = _manager(qapp)
    _to_the_second_pass(m, "A")
    m._runner.sent.clear()
    m.send_key("d")
    m.send_key("\x1b")
    out = "".join(_sent(m))
    assert '"done"' in out and '"quit"' in out


@pytest.mark.parametrize("closing", [
    '{"event":"dual_pass_result","what":"strip","strip":"A","ok":true,'
    '"why":"","uv_readings":96,"fewest_per_patch":4,"uv_triggers":1,'
    '"volts":[1,1],"pairing":"checked","calibrate":false}',
    '{"event":"strip_ready","strip":"A"}',
    '{"event":"error","kind":"misread","detail":"x"}'])
def test_1_after_the_second_pass_a_jump_goes_out_again(qapp, closing):
    m = _manager(qapp)
    _to_the_second_pass(m, "A")
    _line(m, closing)
    m._runner.sent.clear()
    m.user_goto_strip("C")
    assert any('"goto"' in s for s in _sent(m))


def test_1_characterisation_a_calibration_asked_for_during_the_wait_is_held(qapp):
    """CHARACTERISATION (held already on v4.3.48, app side): a calibration asked
    for during the UV wait is held by the manager (a swipe is in progress) and
    goes out at the next strip prompt. The analysis's worry was the helper's
    gate, which the helper now closes during the wait (test below)."""
    m = _manager(qapp)
    m._saw_reader_prompt = True
    _to_the_second_pass(m, "A")
    m._runner.sent.clear()
    assert m.request_calibration() == "held"
    assert not any('"calibrate"' in s for s in _sent(m))


def test_1_the_engines_own_hold_reaches_the_tab(qapp):
    m = _manager(qapp)
    held = []
    m.dual_pass_held.connect(held.append)
    _to_the_second_pass(m, "B")
    _line(m, '{"event":"dual_pass_held","strip":"B","cmd":"goto"}')
    assert held == ["B"]


def test_1_without_the_dual_scan_a_jump_during_a_swipe_goes_out_as_before(qapp):
    m = _manager(qapp)
    _line(m, '{"event":"strip_ready","strip":"A"}')
    _line(m, '{"event":"scan_started"}')
    m._runner.sent.clear()
    m.user_goto_strip("C")
    assert any('"goto"' in s for s in _sent(m))


def test_1_the_tab_says_why_the_jump_was_not_made(qapp):
    from ui.tabs.tab_measure import TabMeasure
    logged, flashes = [], []
    fake = SimpleNamespace(
        _log=SimpleNamespace(appendPlainText=logged.append,
                             ensureCursorVisible=lambda: None),
        _strip_name=lambda s: s,
        _flash_status=lambda t, ms=0: flashes.append(t))
    TabMeasure._on_dual_pass_held(fake, "A")
    title, body = M.M_DUAL_PASS_HELD.render(strip="A")
    assert flashes == [title]
    assert logged == [f"[{title}]\n{body}"]
    TabMeasure._on_dual_pass_held(fake, "A")       # once per wait in the log
    assert len(logged) == 1


def test_1_the_helper_holds_a_command_and_keeps_waiting_for_the_uv_pass():
    """chromiq_dualdev.c: the UV pass's read_strip runs in a loop that a held
    command (cq_dd_held_command: goto, forward, back, next unread, file as,
    turn) does not leave; Esc, quit, done and hold leave it as before. The
    calibration gate is closed BEFORE the UV wait, so a calibration asked for
    then runs at the next strip prompt, never over an open ruler stream."""
    src = _code((HELPER / "chromiq_dualdev.c").read_text(encoding="utf-8"))
    i = src.index("static void cq_dd_strip(")
    body = src[i:src.index("\n}\n", i)]
    gate = body.index("cq_cal_gate_set(0);")
    loop = body.index("rv2 = it->read_strip(")
    assert body.index('\\"event\\":\\"dual_pass\\"') < gate < loop
    tail = body[loop:body.index("(void)i1pro2_cq_dual_take_uv(", loop)]
    assert "cq_dd_held_command()" in tail and "dual_pass_held" in tail
    c = _code((HELPER / "chromiq_chartread.c").read_text(encoding="utf-8",
                                                         errors="replace"))
    j = c.index("static int cq_dd_held_command(void) {")
    held = c[j:c.index("\n}\n", j)]
    for k in ("'f'", "'b'", "'n'", "'g'", "'m'", "'u'"):
        assert k in held, k
    for k in ("'d'", "'q'", "'h'", "'k'", "0x1b"):
        assert k not in held, k


def test_1_the_simulation_holds_as_the_helper_does(tmp_path, monkeypatch):
    from tests.test_i1pro2_dual_scan_ui import _c_fields, _sim_events

    def script(s):
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=i)
        j = s.event_index()
        s.send(cmd="goto", strip="C")
        s.wait_event("dual_pass_held", after=j)
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=j)
        s.wait_event("strip_ready", after=j)
        k = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=k)
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=k)
        s.wait_event("strip_ready", after=k)
        s.send(cmd="done")
        s.wait_event("done", timeout=10)
        s.finish()

    s, *_ = _sim_events(tmp_path, monkeypatch, script)
    held = [e for e in s.events if e.get("event") == "dual_pass_held"]
    assert held and set(held[0]) - {"event"} == _c_fields("dual_pass_held")
    assert not [e for e in s.events if e.get("event") == "conditions"
                and not e.get("active")], "M1 / M2 go on"
    results = [e for e in s.events if e.get("event") == "dual_pass_result"]
    assert [r["ok"] for r in results] == [True, True]
    # the reader stayed on strip A: the first strip read is the first strip
    reads = [e.get("strip") for e in s.events if e.get("event") == "strip_read"]
    readies = [e.get("strip") for e in s.events if e.get("event") == "strip_ready"]
    assert reads[0] == readies[0]


# ---------------------------------------------------- 2. an unusable calibration

def test_2_the_helper_reads_a_strip_after_an_unusable_calibration_as_a_plain_scan():
    """No ruler stream is opened for a strip the last calibration cannot give
    M1 / M2 for (so no second pass is asked for); the strip loop asks
    cq_dd_fits before it arms the lamp pass."""
    c = _code((HELPER / "chromiq_chartread.c").read_text(encoding="utf-8",
                                                         errors="replace"))
    i = c.index("if ((cq_dd_this_strip = cq_dd.on && cq_cond_active))")
    arm = c[i:c.index("rv = it->read_strip(it, \"STRIP\"", i)]
    assert "cq_dd.uncal = cq_dd_fits(1, 0)" in arm
    assert arm.index("cq_dd.uncal = cq_dd_fits(1, 0)") < arm.index(
        "i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_LAMP);")
    src = _code((HELPER / "chromiq_dualdev.c").read_text(encoding="utf-8"))
    j = src.index("static void cq_dd_strip(")
    body = src[j:src.index("\n}\n", j)]
    unc = body.index("if (cq_dd.uncal != NULL) {")
    assert unc < body.index("if (!i1pro2_cq_dual_uv_pass_ready(it)) {")
    block = body[unc:body.index("\n\t}\n", unc)]
    assert "cq_dd_ask_calibration()" in block and "inst_misread" in block
    k = src.index("static int cq_dd_ask_calibration(void) {")
    assert "cq_dd.cal_asked = 1;" in src[k:src.index("\n}\n", k)]
    assert "read_strip" not in block, "no second pass after an unusable calibration"
    # once per calibration
    k = src.index("static void cq_dd_after_cal(")
    assert "cq_dd.cal_asked = 0;" in src[k:src.index("\n}\n", k)]


def test_2_the_tab_asks_for_a_new_calibration_and_records_the_strip(qapp, tmp_path):
    from core.file_manager import Run
    from ui.tabs.tab_measure import TabMeasure
    from workflow.dual_scan.record import PassRecord
    from tests.test_i1pro2_dual_scan_ui_fix import _fake
    fake, *_ = _fake(tmp_path)
    TabMeasure._dual_reset(fake)
    TabMeasure._on_dual_session(fake, {"active": True, "dual": True,
                                       "scale": 1.156, "chosen": "M2"})
    TabMeasure._on_dual_calibration(fake, {"ok": False, "why": "uv_tile_dark"})
    TabMeasure._on_dual_pass_result(fake, {
        "what": "strip", "strip": "A", "ok": False, "why": "uv_tile_dark",
        "calibrate": True})
    html = TabMeasure._dual_failure_html(fake)
    title, body = M.M_DUAL_CAL_AGAIN.render(
        reason=D.reason_sentence("uv_tile_dark"), retry="Retry")
    assert title in html and "Calibrate button" in html
    main = fake._ti1_path.with_suffix(".ti3")
    main.write_text("CTI3\n", encoding="latin-1")
    TabMeasure._dual_flush(fake, str(main), 1)
    rec = PassRecord.load(Run.dual_pass_record(main))
    assert rec.uv["A"].reason == "uv_tile_dark"
    assert ("A", "uv") in rec.missing()


def test_2_the_simulation_asks_for_a_calibration_once_then_keeps_m0(
        tmp_path, monkeypatch):
    from tests.test_i1pro2_dual_scan_ui import _sim_events
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_CAL", "dark")

    def script(s):
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("error", after=i)          # refused: calibrate again
        s.send(cmd="retry")
        s.wait_event("strip_ready", after=i)
        j = s.event_index()
        s.send(cmd="swipe")                     # again, without calibrating
        s.wait_event("strip_read", after=j)
        s.wait_event("strip_ready", after=j)
        k = s.event_index()
        s.send(cmd="done")
        s.wait_event("unread_confirm", after=k)
        s.send(cmd="yes")
        s.wait_event("done", timeout=10)
        s.finish()

    s, *_ = _sim_events(tmp_path, monkeypatch, script)
    assert not [e for e in s.events if e.get("event") == "dual_pass"], \
        "no second pass after an unusable calibration"
    results = [e for e in s.events if e.get("event") == "dual_pass_result"]
    assert [(r["ok"], r["why"], r["calibrate"]) for r in results] == [
        (False, "uv_tile_dark", True), (False, "uv_tile_dark", False)]
    ends = [e for e in s.events if e.get("event") == "conditions"
            and not e.get("active")]
    assert [e["why"] for e in ends] == ["dual_uv_tile_dark"]


def test_2_every_text_says_what_now_happens():
    one = M.M_DUAL_PASS_ONE_NO_CAL.render(strip="A")[1]
    assert "still asks for its second pass" not in one
    assert "M_DUAL_PASS_TWO_NO_CAL" not in dir(M), "no strip asks for a pass that cannot count"
    again = " ".join(M.M_DUAL_CAL_AGAIN.render(reason="R", retry="Retry")).lower()
    assert "calibrate" in again and "m0 only" in again
    refused = M.M_DUAL_CAL_REFUSED.render(reason="R")[1]
    assert "M0 is measured as always" not in refused


# ------------------------------------------------- 3. the header after a refused resume

def test_3_a_refused_continue_keeps_the_dual_header(tmp_path, monkeypatch):
    import tests.helpers.replay_tools as rt
    from tests.test_i1pro2_dual_scan_engine import _chart, _dual_args, _vec
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_TILE_S", "0.2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_PASS_S", "0.05")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_M0_SUFFIX", "~M0")
    monkeypatch.setattr(rt, "HELPER", SIM)
    base, rp, truth, _steps = _chart(tmp_path)
    with rp.open("a", encoding="utf-8") as fp:
        for letter, (lamp, _m1, _m2) in sorted(truth.items()):
            fp.write(f"STRIP {letter}~M0\n")
            for row in lamp:
                fp.write(f"LAMP {_vec(row)}\n")
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    args = _dual_args(cdir) + ["--dual-chosen", "M2"]

    def first(s):
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        s.wait_event("strip_ready", after=i)
        i = s.event_index()
        s.send(cmd="swipe", needs_ruler=True)
        s.wait_event("strip_read", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("done", timeout=10, after=i)
        s.finish()

    with rt.ReplaySession(base, rp, extra_args=args) as s:
        first(s)

    def again(s):
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("done", timeout=10, after=i)
        s.finish()

    main = base.with_suffix(".ti3")
    for _ in range(2):                       # two Continues in a row
        with rt.ReplaySession(base, rp, extra_args=["-r"] + args) as s2:
            again(s2)
        cond = [e for e in s2.events if e.get("event") == "conditions"]
        assert cond and cond[0].get("why") == "resume", cond
        text = main.read_text(encoding="latin-1")
        assert storage.read_dual_record(main).dual, "the dual header is kept"
        assert re.search(r'^CHROMIQ_DUAL_ENDED "resume"', text, re.M)
        assert text.count('CHROMIQ_DUAL_SCAN "i1pro2"') == 1
        assert D.ended_before(main)
        plan = D.plan_for(_on(), CAPS, None, "u", main)
        assert plan.dual and plan.ended_before and not plan.refusal


def test_3_the_helper_writes_the_header_only_for_a_refused_dual_resume():
    c = _code((HELPER / "chromiq_chartread.c").read_text(encoding="utf-8",
                                                         errors="replace"))
    i = c.index("static void cq_cond_for_session(")
    body = c[i:c.index("\n}\n", i)]
    k = body.index('"CHROMIQ_DUAL_ENDED"')
    assert body.rindex('strcmp(why, "resume") == 0', 0, k) > 0
    assert body.rindex("was_dual", 0, k) > 0


# ------------------------------------------------------------ 4. high resolution

def _start_fake(plan, *, nocal=False, highres=False):
    from ui.tabs.tab_measure import TabMeasure
    said = []
    fake = SimpleNamespace(
        _settings=_on(), _dual_plan_now=lambda: plan,
        _dual_nocal_now=lambda: nocal, _dual_highres_now=lambda: highres,
        _engine_selected=lambda: True,
        _measurement_to_continue=lambda: None, _dual_caps=lambda: CAPS,
        _dual_model_for_plan=lambda: None,
        _filter_label=lambda c: str(c), _measure_filter_code=lambda: "u",
        _start_button_name=lambda: "Start Measurement",
        _log=SimpleNamespace(appendPlainText=lambda *_a: None,
                             ensureCursorVisible=lambda: None),
        _sound=None, _say_on_screen=lambda t, b: said.append((t, b)))
    return TabMeasure._blocked_by_dual_scan(fake), said


def test_4_high_resolution_with_the_dual_scan_is_refused_before_start():
    plan = D.plan_for(_on(), CAPS, None, "u")
    blocked, said = _start_fake(plan, highres=True)
    assert blocked
    title, body = said[0]
    assert title == M.M_DUAL_HIGHRES_REFUSED.render(
        highres="x", start="y", option="z", where="w")[0]
    assert "High resolution spectral mode (-H)" in body
    assert "Nothing has been measured or changed." in body
    blocked, said = _start_fake(plan, highres=False)
    assert not blocked and said == []


def test_4_the_tab_reads_minus_h_from_the_reader_arguments():
    from ui.tabs.tab_measure import TabMeasure
    for extra, want in (("-T 0.7 -H", True), ("-T 0.7", False), ("", False)):
        fake = SimpleNamespace(
            _current_mode=lambda: "manual",
            _collect_manual=lambda e=extra: SimpleNamespace(extra_args=e),
            _collect_guided=lambda e=extra: SimpleNamespace(extra_args=e))
        assert TabMeasure._dual_highres_now(fake) is want


# ------------------------------------------------------------ the Beta off

def test_off_high_resolution_is_as_always():
    off = D.Plan(False, why_not="off")
    blocked, said = _start_fake(off, highres=True)
    assert not blocked and said == []


def test_off_the_manager_never_holds(qapp):
    m = _manager(qapp)
    # no dual_pass event ever comes without --dual-scale
    _line(m, '{"event":"strip_ready","strip":"A"}')
    _line(m, '{"event":"scan_started"}')
    m._runner.sent.clear()
    m.send_key("f")
    assert any('"forward"' in s for s in _sent(m))


def test_1_the_tab_does_not_say_it_jumps_when_the_jump_was_held(qapp):
    """Found on screen (2026-11-19, en-held): the log said "[Engine] Jumping to strip C..."
    beside M-DUAL-PASS-HELD although nothing was sent."""
    from ui.tabs.tab_measure import TabMeasure
    logged = []
    for answer, want in ((False, 0), (True, 1), (None, 1)):
        logged.clear()
        fake = SimpleNamespace(
            _manager=SimpleNamespace(engine_active=True,
                                     user_goto_strip=lambda s, a=answer: a,
                                     goto_patch=lambda loc, a=answer: a),
            _letter_for_page_idx=lambda p, i: "C",
            _log=SimpleNamespace(appendPlainText=logged.append))
        TabMeasure._on_preview_strip_clicked(fake, 0, 2)
        TabMeasure._on_preview_patch_clicked(fake, 0, "C3")
        assert len(logged) == 2 * want, (answer, logged)


def test_2_the_failure_window_keeps_the_paragraphs(qapp, tmp_path):
    """Found on screen (2026-11-19, en-uncal): the window's rich text ran M-DUAL-CAL-AGAIN's
    paragraphs into one block."""
    from ui.tabs.tab_measure import TabMeasure
    from tests.test_i1pro2_dual_scan_ui_fix import _fake
    fake, *_ = _fake(tmp_path)
    fake._dual_failed = ("calibrate", "A", "uv_tile_dark")
    html_text = TabMeasure._dual_failure_html(fake)
    assert "\n" not in html_text and html_text.count("<br><br>") >= 4


# ------------------------------------------- 4.3.49 review round (REVIEW_DUALFIX.md)
#
# M1: once the engine has refused a reading with "calibrate again", it does not
# ask again for the same calibration (cq_dd_ask_calibration, once per
# calibration): the next strip read without calibrating is kept as M0 and M1 /
# M2 end. The strip prompt must say so, on the same strip (Retry) and on the
# next one (Skip Strip).

def _no_cal_session(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    from tests.test_i1pro2_dual_scan_ui_fix import _fake
    fake, logged, *_ = _fake(tmp_path, strips=("A", "B", "C"))
    fake._spot_session = False
    TabMeasure._dual_reset(fake)
    TabMeasure._on_dual_session(fake, {"active": True, "dual": True,
                                       "scale": 1.156, "chosen": "M2"})
    TabMeasure._on_dual_calibration(fake, {"ok": False, "why": "uv_tile_dark"})
    return fake


def _prompt(fake, strip):
    from ui.tabs.tab_measure import TabMeasure
    TabMeasure._dual_pass_one(fake, strip)
    return fake.prompts[-1]


def _refuse(fake, strip):
    from ui.tabs.tab_measure import TabMeasure
    TabMeasure._on_dual_pass_result(fake, {
        "what": "strip", "strip": strip, "ok": False, "why": "uv_tile_dark",
        "calibrate": True})
    return TabMeasure._dual_failure_html(fake)


@pytest.mark.parametrize("after", ["A", "B"], ids=["retry", "skip_strip"])
def test_r1_after_the_one_refusal_the_prompt_says_the_next_read_is_kept(
        qapp, tmp_path, after):
    fake = _no_cal_session(tmp_path)
    first = M.M_DUAL_PASS_ONE_NO_CAL.render(strip="A")
    assert _prompt(fake, "A") == first
    _refuse(fake, "A")
    kept = M.M_DUAL_PASS_ONE_NO_CAL_KEPT.render(strip=after)
    assert _prompt(fake, after) == kept, "Retry or Skip Strip: no second refusal comes"
    assert _prompt(fake, after) == kept, "it stays true until a calibration"


def test_r1_a_new_calibration_gives_the_refusal_back(qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    fake = _no_cal_session(tmp_path)
    _prompt(fake, "A")
    _refuse(fake, "A")
    # calibrated again, still dark: the engine refuses once more (cal_asked = 0)
    TabMeasure._on_dual_calibration(fake, {"ok": False, "why": "uv_tile_dark"})
    assert _prompt(fake, "A") == M.M_DUAL_PASS_ONE_NO_CAL.render(strip="A")
    # calibrated again, usable: the two passes as always
    TabMeasure._on_dual_calibration(fake, {"ok": True, "lamp_clocks": 41,
                                           "uv_clocks": 41})
    assert _prompt(fake, "A") == M.M_DUAL_PASS_ONE.render(strip="A")


def test_r1_the_kept_prompt_says_what_happens():
    title, body = M.M_DUAL_PASS_ONE_NO_CAL_KEPT.render(strip="B")
    assert "asks you once more" not in body and "does not keep" not in body
    assert "M0 only" in body and "end" in body and "strip B" in body
    assert "K or the Calibrate button" in body


# S1: the window says what to do with the buttons it has.

def test_r2_the_calibrate_again_window_names_its_own_button():
    from core.i18n import tr
    _t, body = M.M_DUAL_CAL_AGAIN.render(reason="R", retry=tr("Retry"))
    retry = body.index("“Retry”")
    assert retry < body.index("K or the Calibrate button"), \
        "Retry first: the Calibrate button is behind the window"
    assert "Please calibrate again now" not in body
    assert "M0 only" in body


def test_r2_the_window_fills_in_the_retry_button(qapp, tmp_path):
    from core.i18n import tr
    fake = _no_cal_session(tmp_path)
    html_text = _refuse(fake, "A")
    assert f"“{tr('Retry')}”" in html_text and "{retry}" not in html_text


# S2: the way out. A broken UV light must not refuse every strip for ever: the
# helper asks for a calibration once per calibration (compiled and run, not
# only read).

def test_r3_the_helper_asks_once_per_calibration_and_then_keeps_the_reading(
        tmp_path):
    import shutil
    import subprocess
    cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if cc is None:
        pytest.skip("no C compiler")
    src = _code((HELPER / "chromiq_dualdev.c").read_text(encoding="utf-8"))
    k = src.index("static int cq_dd_ask_calibration(void) {")
    fn = src[k:src.index("\n}\n", k) + 3]
    prog = tmp_path / "ask.c"
    prog.write_text(
        "#include <stdio.h>\nstatic struct { int cal_asked; } cq_dd;\n" + fn +
        "int main(void) {\n"
        "  int a = cq_dd_ask_calibration(), b = cq_dd_ask_calibration();\n"
        "  int c = cq_dd_ask_calibration();\n"
        "  cq_dd.cal_asked = 0;   /* cq_dd_after_cal: a new calibration */\n"
        "  int d = cq_dd_ask_calibration();\n"
        "  printf(\"%d%d%d%d\\n\", a, b, c, d);\n  return 0;\n}\n",
        encoding="utf-8")
    exe = tmp_path / "ask"
    subprocess.run([cc, "-o", str(exe), str(prog)], check=True, timeout=120,
                   capture_output=True)
    out = subprocess.run([str(exe)], capture_output=True, text=True,
                         encoding="utf-8", timeout=30)
    assert out.stdout.strip() == "1001", "refused once, then kept, until a new calibration"
    # ...and a 0 keeps the reading: the strip is made a misread only when asked
    j = src.index("static void cq_dd_strip(")
    body = src[j:src.index("\n}\n", j)]
    unc = body.index("if (cq_dd.uncal != NULL) {")
    block = body[unc:body.index("\n\t}\n", unc)]
    assert re.search(r"if \(again\)\s*\*rv = inst_misread;", block)
    s = src.index("static void cq_dd_spot(")
    spot = src[s:src.index("\n}\n", s)]
    assert "cq_dd_cal_reason(why) && cq_dd_ask_calibration()" in spot


# S3: the held jump, through the real manager and the real Measure tab.

def test_r3_a_held_jump_and_a_held_patch_say_nothing_went_out(qapp):
    m = _manager(qapp)
    _to_the_second_pass(m, "A")
    m._runner.sent.clear()
    assert m.user_goto_strip("C") is False
    assert m.goto_patch("C3") is False
    assert _sent(m) == []
    _line(m, '{"event":"strip_ready","strip":"B"}')
    assert m.user_goto_strip("C") is True
    assert m.goto_patch("C3") is True


def _real_tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _S({"chartread_engine": "chromiq", **_on()})
    tab = TabMeasure(ArgyllRunner(s), s)
    m = tab._manager
    m._engine_active = True
    m._guided_state = "disabled"
    m._runner = _Runner()
    tab._letter_for_page_idx = lambda page, idx: "C"
    return tab, m


def _dual_start(m, *, cal_ok=True):
    _line(m, '{"event":"conditions","active":true,"dual":true,"scale":1.156,'
             '"scale_source":"standard","chosen":"M2"}')
    _line(m, '{"event":"dual_calibration","ok":%s,"why":"%s","mode":"scan",'
             '"lamp_clocks":41,"uv_clocks":41,"volts":[1,1],"driver":0}'
          % (("true", "") if cal_ok else ("false", "uv_tile_dark")))


def test_r3_the_held_signal_reaches_the_measure_tab(qapp):
    tab, m = _real_tab(qapp)
    _dual_start(m)
    _to_the_second_pass(m, "A")
    tab._on_preview_strip_clicked(0, 2)
    title, body = M.M_DUAL_PASS_HELD.render(strip="A")
    log_text = tab._log.toPlainText()
    assert f"[{title}]\n{body}" in log_text
    assert "Jumping to strip" not in log_text
    assert not any('"goto"' in s for s in _sent(m))


# S4: a click during the FIRST pass (the instrument has fired) is held as well,
# and the tab says why once the UV wait begins, never "Jumping to strip C".

def test_r4_a_jump_during_the_first_pass_is_held_and_said_after_it(qapp):
    tab, m = _real_tab(qapp)
    _dual_start(m)
    _line(m, '{"event":"strip_ready","strip":"A"}')
    _line(m, '{"event":"scan_started"}')
    m._runner.sent.clear()
    held = []
    m.dual_pass_held.connect(held.append)
    tab._on_preview_strip_clicked(0, 2)
    assert m.user_goto_strip("C") is False and m.goto_patch("C3") is False
    m.send_key("f")
    assert _sent(m) == [], _sent(m)
    assert held == [], "said once the second pass is due, not during the first"
    _line(m, '{"event":"dual_pass","strip":"A","pass":"uv","of":2,"lamp_ok":true}')
    assert held == ["A"]
    log_text = tab._log.toPlainText()
    title = M.M_DUAL_PASS_HELD.render(strip="A")[0]
    two = M.M_DUAL_PASS_TWO.render(strip="A")[0]
    assert "Jumping to strip" not in log_text
    assert log_text.index(f"[{two}]") < log_text.index(f"[{title}]")


def test_r4_a_first_pass_that_ends_without_a_second_says_nothing(qapp):
    m = _manager(qapp)
    _dual_start(m)
    held = []
    m.dual_pass_held.connect(held.append)
    _line(m, '{"event":"strip_ready","strip":"A"}')
    _line(m, '{"event":"scan_started"}')
    assert m.user_goto_strip("C") is False
    _line(m, '{"event":"error","kind":"misread","detail":"x"}')
    _line(m, '{"event":"strip_ready","strip":"A"}')
    _line(m, '{"event":"dual_pass","strip":"A","pass":"uv","of":2,"lamp_ok":true}')
    assert held == [], "the early hold belonged to the misread pass"


@pytest.mark.parametrize("setup", ["no_dual", "unusable_calibration", "spot"])
def test_r4_otherwise_a_jump_during_a_swipe_goes_out_as_before(qapp, setup):
    m = _manager(qapp)
    if setup != "no_dual":
        _dual_start(m, cal_ok=setup != "unusable_calibration")
    ready = "spot_ready" if setup == "spot" else "strip_ready"
    _line(m, '{"event":"%s","strip":"A","patch":"A1"}' % ready)
    _line(m, '{"event":"scan_started"}')
    m._runner.sent.clear()
    assert m.user_goto_strip("C") is True
    assert any('"goto"' in s for s in _sent(m))


def test_r4_the_hold_ends_with_the_dual_scan(qapp):
    m = _manager(qapp)
    _dual_start(m)
    _line(m, '{"event":"conditions","active":false,"why":"dual_dual_needs_ruler"}')
    _line(m, '{"event":"strip_ready","strip":"A"}')
    _line(m, '{"event":"scan_started"}')
    m._runner.sent.clear()
    assert m.user_goto_strip("C") is True
