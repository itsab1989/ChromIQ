"""The X-Rite i1Pro 2 dual scan in the Measure tab: the UI step (2026-11-18).

Pinned here, in the owner's and the coordinator's words
(docs/design/i1pro2_dual_scan.md section 8, workflow/dual_scan/session.py):

* a Beta under "X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan"; with
  either off, nothing of it runs and the helper's command line is today's;
* with it on, the filter row's M0 / M1 / M2 is NOT sent as -F: it is recorded
  with --dual-chosen, and the main file stays M0; the polariser and D65 are
  refused before START; an instrument seen as another model measures as
  before; a dual measurement is never continued as a single scan;
* the engine's events (dual_calibration, dual_pass, dual_pass_result, the
  conditions event that ends M1 / M2) reach the tab as signals, never as the
  i1Pro 3 Beta's lines, and an engine refusal is never a fallback to stock
  chartread;
* the simulated helper the on-screen proof uses speaks the REAL helper's
  events, field for field (checked against the C sources), and with the real
  helper's replay instrument writes the real M0 / M1 / M2 files;
* the pass record is written from the events, and Build Profile is pre-set
  to the chosen condition ONCE, when every strip has both passes.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.dual_scan import session as D          # noqa: E402
from workflow.dual_scan import storage                # noqa: E402
from workflow.dual_scan.reasons import NOTES, REASONS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "tests" / "helpers" / "dual_sim_helper.py"
CAPS = frozenset({storage.CAPABILITY, storage.DEVICE_CAPABILITY,
                  "i1pro3_conditions"})


class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def _on(**kw):
    # 4.3.54: these rules are the dual scan's "always" (4.3.53's behaviour); the
    # "only for M1 or M2" mode is pinned in tests/test_4354_dual_scan_mode.py
    return _S({"i1pro3_conditions_beta": True, D.SETTING: True,
               D.MODE_SETTING: D.MODE_ALWAYS, **kw})


# ------------------------------------------------------------------ the rules

@pytest.mark.parametrize("settings", [
    _S(), _S({"i1pro3_conditions_beta": True}), _S({D.SETTING: True})])
def test_off_or_without_the_i1pro3_beta_there_is_no_dual_scan(settings):
    plan = D.plan_for(settings, CAPS, None, "5")
    assert plan.dual is False and plan.refusal == "" and plan.args() == []


def test_it_needs_a_helper_that_names_both_words():
    for caps in (frozenset(), {storage.CAPABILITY}, {storage.DEVICE_CAPABILITY}):
        assert D.plan_for(_on(), caps, None, None).dual is False
    assert D.plan_for(_on(), CAPS, None, None).dual is True


@pytest.mark.parametrize("model,dual", [
    (None, True), ("X-Rite i1 Pro 2", True), ("i1Pro 2", True),
    ("X-Rite i1 Pro 3", False), ("ColorMunki", False), ("i1 Pro", False)])
def test_an_instrument_seen_as_another_model_measures_as_before(model, dual):
    assert D.plan_for(_on(), CAPS, model, "5").dual is dual


@pytest.mark.parametrize("code,chosen", [
    (None, "M0"), ("n", "M0"), ("5", "M1"), ("u", "M2"), ("U", "M2")])
def test_the_filter_row_chooses_the_main_condition(code, chosen):
    plan = D.plan_for(_on(), CAPS, None, code)
    assert plan.dual and plan.chosen == chosen
    assert plan.args() == ["--dual-scale", "1.1560", "--dual-scale-source",
                           "standard", "--dual-white", "instrument",
                           "--dual-chosen", chosen]


@pytest.mark.parametrize("code", ["p", "6"])
def test_the_polariser_and_d65_are_refused_before_start(code):
    plan = D.plan_for(_on(), CAPS, None, code)
    assert plan.dual is False and plan.refusal == "filter_not_dual"


@pytest.mark.parametrize("args,left", [
    ("-F 5", ""), ("-F5", ""), ("-T 0.7 -F u -H", "-T 0.7 -H"),
    ("-T 0.7", "-T 0.7"), ("", "")])
def test_no_minus_f_goes_to_the_instrument(args, left):
    out = D.without_filter(args)
    assert out == left
    from workflow.measurement_condition import filter_code_from_args
    assert filter_code_from_args(out) is None


@pytest.mark.parametrize("why,rid", [
    ("dual_uv_tile_dark", "uv_tile_dark"), ("uv_tile_dark", "uv_tile_dark"),
    ("dual_dual_needs_ruler", "dual_needs_ruler"),
    ("dual_high_resolution", "dual_high_resolution"),
    ("dual_no_uv_tables", "no_uv_tables"), ("mixed", "mixed_scan_kind"),
    ("uv_pass_wrong_strip", "uv_pass_wrong_strip"),
    # review of 2026-11-18, S-4: these had no sentence and showed their id
    ("dual_record", "record"), ("dual_not_available", "not_available"),
    ("resume", "resume"), ("", "")])
def test_every_engine_reason_finds_its_sentence(why, rid):
    assert D.reason_id(why) == rid
    text = D.reason_sentence(why)
    assert text and "—" not in text
    if rid:
        assert text == REASONS[rid]


def test_every_reason_the_tab_can_show_is_translated_and_says_both_passes():
    import scripts.i18n_extract as x
    keys = x.extract_keys()
    for rid in D.SHOWN_REASONS:
        assert REASONS[rid] in keys, rid
    for n in D.SHOWN_NOTES:
        assert NOTES[n] in keys, n
    for rid in D.SHOWN_REASONS:
        if rid.startswith("uv_pass_") and rid != "uv_pass_count":
            assert "both passes" in REASONS[rid], rid


def _dual_main(tmp_path, *, dual=True, scale="1.1560", source="standard"):
    p = tmp_path / "chart.ti3"
    head = ['CTI3', 'TARGET_INSTRUMENT "X-Rite i1Pro 2"']
    if dual:
        head += ['CHROMIQ_DUAL_SCAN "i1pro2"', f'CHROMIQ_DUAL_SCALE "{scale}"',
                 f'CHROMIQ_DUAL_SCALE_SOURCE "{source}"',
                 'CHROMIQ_DUAL_WHITE "instrument"', 'CHROMIQ_DUAL_CHOSEN "M2"']
    p.write_text("\n".join(head + [
        "NUMBER_OF_FIELDS 2", "BEGIN_DATA_FORMAT", "SAMPLE_ID SAMPLE_LOC",
        "END_DATA_FORMAT", "NUMBER_OF_SETS 1", "BEGIN_DATA", '1 "A1"',
        "END_DATA", ""]), encoding="latin-1")
    return p


def test_a_measurement_is_never_continued_the_other_way(tmp_path):
    (tmp_path / "s").mkdir()
    single = _dual_main(tmp_path / "s", dual=False)
    plan = D.plan_for(_on(), CAPS, None, None, single)
    # 4.3.54 (review S1, "a run continues the way it was started"): a one-pass run is
    # continued with one pass per strip, in both modes; never with the dual scan
    assert plan.dual is False and plan.refusal == "" and plan.why_not == "single_record"
    (tmp_path / "d").mkdir()
    dual = _dual_main(tmp_path / "d")
    # a single scan on a dual measurement: refused, where the engine can tell
    assert D.single_scan_refusal(_S(), CAPS, None, dual) == "mixed_scan_kind"
    assert D.single_scan_refusal(_S(), frozenset(), None, dual) == ""
    assert D.single_scan_refusal(_S(), CAPS, None, single) == ""


def test_a_measurement_continues_with_its_own_factor(tmp_path):
    from workflow.dual_scan.scale import ScaleChoice
    main = _dual_main(tmp_path, scale="1.2000", source="refined")
    plan = D.plan_for(_on(), CAPS, None, "u", main, ScaleChoice.standard())
    assert plan.dual and plan.choice.value == pytest.approx(1.2)
    assert plan.choice.source == "refined"
    assert "--dual-scale" in plan.args() and "1.2000" in plan.args()


# ------------------------------------------- the simulation is the real helper

def _c_fields(event: str) -> "set[str]":
    """The field names of *event* as chromiq_dualdev.c / chromiq_chartread.c
    emit it."""
    for src in ("chromiq_dualdev.c", "chromiq_chartread.c"):
        text = (ROOT / "native" / "chartread_helper" / src).read_text(
            encoding="utf-8", errors="replace")
        for m in re.finditer(r'cq_emit_raw\(((?:\s*"(?:[^"\\]|\\.)*")+)', text):
            fmt = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
            if f'\\"event\\":\\"{event}\\"' in fmt:
                return set(re.findall(r'\\"(\w+)\\":', fmt)) - {"event"}
    raise AssertionError(f"{event} is not emitted by the C sources")


def _sim_events(tmp_path, monkeypatch, script):
    """Run the simulated helper on a real chart; *script(s)* drives it."""
    import tests.helpers.replay_tools as rt
    from tests.test_i1pro2_dual_scan_engine import _chart, _dual_args
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_TILE_S", "0.2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_PASS_S", "0.05")
    monkeypatch.setattr(rt, "HELPER", SIM)
    base, rp, truth, steps = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with rt.ReplaySession(base, rp, extra_args=_dual_args(cdir) + [
            "--dual-chosen", "M2"]) as s:
        script(s)
    return s, base, cdir


needs_helper = pytest.mark.skipif(
    not (ROOT / "native" / "chromiq-chartread").exists(),
    reason="engine not built")


@needs_helper
def test_the_simulation_speaks_the_real_helpers_events(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_NEEDCAL", "1")

    def script(s):
        s.wait_event("cal_required", timeout=10)
        i = s.event_index()
        s.send(cmd="accept")
        s.wait_event("cal_done", after=i, timeout=10)
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe")                       # pass 1 of 2
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe", uv_fault="uv_pass_wrong_strip")   # refused
        s.wait_event("error", after=i, kind="misread")
        i = s.event_index()
        s.send(cmd="retry")                       # both passes again
        s.wait_event("strip_ready", after=i)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        s.wait_event("strip_ready", after=i)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe", pairing="pairing_not_checked")
        s.wait_event("strip_read", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("done", timeout=10, after=i)
        s.finish()

    s, base, cdir = _sim_events(tmp_path, monkeypatch, script)
    names = [e.get("event") for e in s.events]
    # the order the real helper keeps: the tile's UV reading before cal_done
    assert names.index("dual_calibration") < names.index("cal_done")
    for ev in ("dual_calibration", "dual_pass", "dual_pass_result"):
        got = [e for e in s.events if e.get("event") == ev]
        assert got, ev
        for e in got:
            assert set(e) - {"event"} == _c_fields(ev), (ev, e)
    res = [e for e in s.events if e.get("event") == "dual_pass_result"]
    assert [(r["ok"], r["why"]) for r in res] == [
        (False, "uv_pass_wrong_strip"), (True, ""), (True, "")]
    assert res[-1]["pairing"] == "pairing_not_checked"
    # each result comes right before its strip's verdict
    for r in res:
        k = s.events.index(r)
        assert s.events[k + 1].get("event") in ("strip_read", "error")
    # ...and the files are the real helper's, with the person's choice
    main = base.with_suffix(".ti3")
    rec = storage.read_dual_record(main)
    assert rec.dual and rec.chosen == "M2"
    assert sorted(p.name.split("-")[-1] for p in cdir.glob("*.ti3")) == [
        "M1.ti3", "M2.ti3"]


@needs_helper
def test_a_lost_ruler_ends_m1_and_m2_as_the_real_helper_says_it(
        tmp_path, monkeypatch):
    def script(s):
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe", needs_ruler=True)
        s.wait_event("strip_read", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("unread_confirm", after=i)
        s.send(cmd="yes")
        s.wait_event("done", timeout=10, after=i)
        s.finish()

    s, _base, _cdir = _sim_events(tmp_path, monkeypatch, script)
    ends = [e for e in s.events if e.get("event") == "conditions"
            and not e.get("active")]
    assert ends == [{"event": "conditions", "active": False,
                     "why": "dual_dual_needs_ruler", "kept": True}]   # 4.3.49
    assert "dual_pass" not in [e.get("event") for e in s.events]
    # the reason the C code gives for it is the one the tab maps
    text = (ROOT / "native/chartread_helper/chromiq_dualdev.c").read_text(
        encoding="utf-8")
    assert 'cq_cond_lose("dual_dual_needs_ruler")' in text
    assert D.reason_id("dual_dual_needs_ruler") == "dual_needs_ruler"


# ------------------------------------------------------------------ the manager

def _manager(qapp):
    from workflow.measure_manager import MeasureManager

    class _R:
        is_running = True

        def write_stdin(self, _d):
            pass
    m = MeasureManager(_R())
    m._engine_active = True
    m._guided_state = "disabled"
    return m


def test_the_engine_events_reach_the_tab_as_signals(qapp):
    m = _manager(qapp)
    got = []
    for sig in ("dual_session", "dual_ended", "dual_calibration", "dual_pass",
                "dual_pass_result", "dual_start_refused"):
        getattr(m, sig).connect(lambda *a, n=sig: got.append((n, a)))
    lines = []
    feed = [
        {"event": "conditions", "active": True, "instrument": "i1pro2",
         "dual": True, "scale": 1.156, "scale_source": "standard",
         "white": "instrument", "main": "M0", "extra": ["M1", "M2"],
         "chosen": "M1"},
        {"event": "dual_calibration", "ok": True, "why": "", "mode": "scan",
         "lamp_clocks": 139, "uv_clocks": 139, "volts": [1, 2], "driver": 0},
        {"event": "dual_pass", "strip": "A", "pass": "uv", "of": 2,
         "lamp_ok": True},
        {"event": "dual_pass_result", "what": "strip", "strip": "A",
         "ok": True, "why": "", "uv_readings": 90, "fewest_per_patch": 4,
         "uv_triggers": 1, "volts": [1, 2], "pairing": "checked"},
        {"event": "conditions", "active": False, "why": "dual_dual_needs_ruler"},
        {"event": "error", "kind": "mixed_scan_kind", "detail": ""},
    ]
    for ev in feed:
        m._handle_engine_line(json.dumps(ev), lines.append)
    assert [n for n, _ in got] == ["dual_session", "dual_calibration",
                                   "dual_pass", "dual_pass_result",
                                   "dual_ended", "dual_start_refused"]
    assert got[4][1] == ("dual_dual_needs_ruler",)
    # never the i1Pro 3 Beta's own line about "one scan"
    assert not [ln for ln in lines if "from one scan" in ln]
    # an engine refusal is never a fallback to stock chartread
    m._engine_progress = False
    m._user_quit = False
    m._engine_fallback_used = False
    m._cal_request_used = False
    m._chart_unreadable = None
    m._stock_cannot_read_chart = ""
    m._engine_saw_event = False
    assert m._dual_refused == "mixed_scan_kind"
    assert m._engine_should_fall_back(1) is False


def test_the_i1pro3_betas_own_events_are_untouched(qapp):
    m = _manager(qapp)
    got = []
    m.dual_session.connect(lambda *a: got.append(a))
    m.dual_ended.connect(lambda *a: got.append(a))
    lines = []
    m._handle_engine_line(json.dumps(
        {"event": "conditions", "active": True, "instrument": "i1pro3",
         "main": "M0", "extra": ["M1", "M2"]}), lines.append)
    m._handle_engine_line(json.dumps(
        {"event": "conditions", "active": False, "why": "record"}),
        lines.append)
    assert got == []
    assert len(lines) == 2


def _args(tmp_path, monkeypatch, dual_args, caps=CAPS, cdir="conditions"):
    from tests.test_i1pro3_conditions_beta_option import _Runner
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
                      engine_condition_dir=(tmp_path / cdir) if cdir else None,
                      engine_dual_args=dual_args)
    m.start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1]


def test_the_helper_gets_the_dual_arguments_only_beside_the_conditions_folder(
        qapp, tmp_path, monkeypatch):
    dual = D.plan_for(_on(), CAPS, None, "u").args()
    on = _args(tmp_path, monkeypatch, dual)
    off = _args(tmp_path, monkeypatch, None)
    k = on.index("--dual-scale")
    assert on[k:k + len(dual)] == dual
    assert on[:k] + on[k + len(dual):] == off
    assert "-F" not in on
    # no conditions folder, or a helper without both words: nothing
    assert "--dual-scale" not in _args(tmp_path, monkeypatch, dual, cdir=None)
    assert "--dual-scale" not in _args(
        tmp_path, monkeypatch, dual, caps={"i1pro3_conditions",
                                           storage.CAPABILITY})


# ------------------------------------------------------------------ the tab

def _tab_fake(tmp_path, plan, **kw):
    from ui.tabs.tab_measure import TabMeasure
    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    logged = []
    fake = SimpleNamespace(
        _settings=_on(), _ti1_path=run_dir / "P.ti1",
        _is_verification_run=lambda: False,
        _log=SimpleNamespace(appendPlainText=logged.append,
                             ensureCursorVisible=lambda: None),
        _dual_plan_now=lambda: plan, **kw)
    fake._condition_dir_for = lambda p: TabMeasure._condition_dir_for(fake, p)
    return fake, logged


def test_at_start_the_row_is_recorded_and_not_sent(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    plan = D.plan_for(_on(), CAPS, None, "5")
    fake, _ = _tab_fake(tmp_path, plan)
    p = SimpleNamespace(extra_args="-F 5 -T 0.7", ti1_path=fake._ti1_path,
                        engine_condition_dir=None, engine_dual_args=None)
    TabMeasure._apply_dual_scan(fake, p)
    assert p.extra_args == "-T 0.7"
    assert p.engine_dual_args[-2:] == ["--dual-chosen", "M1"]
    assert p.engine_condition_dir == fake._ti1_path.parent / "conditions"
    # the Beta off: nothing changes at all
    off = D.Plan(False, why_not="off")
    fake2, _ = _tab_fake(tmp_path, off)
    p2 = SimpleNamespace(extra_args="-F 5", ti1_path=fake._ti1_path,
                         engine_condition_dir=None, engine_dual_args=None)
    TabMeasure._apply_dual_scan(fake2, p2)
    assert p2.extra_args == "-F 5" and p2.engine_dual_args is None


def test_the_pass_record_follows_the_events_and_build_from_is_preset_once(
        qapp, tmp_path):
    from core.file_manager import Run
    from ui.tabs.tab_measure import TabMeasure
    from workflow.dual_scan.record import PassRecord
    plan = D.plan_for(_on(), CAPS, None, "u")
    fake, _ = _tab_fake(tmp_path, plan)
    fake._manager = SimpleNamespace(_session_strips=[{"strip": "A"},
                                                     {"strip": "B"}])
    fake._preview = SimpleNamespace(set_banner=lambda *_a: None,
                                    set_notice=lambda *a, **k: None)
    fake._strip_name = lambda s: s
    fake._hide_status_flash = lambda: None
    fake._dual_strip_labels = lambda: TabMeasure._dual_strip_labels(fake)
    fake._dual_status = lambda t: TabMeasure._dual_status(fake, t)
    TabMeasure._dual_reset(fake)
    TabMeasure._on_dual_session(fake, {"active": True, "dual": True,
                                       "scale": 1.156, "chosen": "M2",
                                       "scale_source": "standard"})
    TabMeasure._on_dual_calibration(fake, {"ok": True, "lamp_clocks": 139,
                                           "uv_clocks": 139})
    TabMeasure._on_dual_pass_result(fake, {"what": "strip", "strip": "A",
                                           "ok": False,
                                           "why": "uv_pass_short"})
    html = TabMeasure._dual_failure_html(fake)
    assert "The second pass of strip A failed" in html
    assert "both passes" in html
    assert TabMeasure._dual_failure_html(fake) == "", "said once"
    TabMeasure._on_dual_pass_result(fake, {"what": "strip", "strip": "A",
                                           "ok": True, "why": "",
                                           "pairing": "checked"})
    main = fake._ti1_path.with_suffix(".ti3")
    main.write_text("CTI3\n", encoding="latin-1")
    TabMeasure._dual_flush(fake, str(main), 1)
    rec = PassRecord.load(Run.dual_pass_record(main))
    assert rec.chosen == "M2"
    assert rec.missing() == [("B", "lamp"), ("B", "uv")]
    assert rec.strips_with_both() == ["A"]
    assert len(rec.calibrations) == 1 and not rec.preset_done
    # B read after the ruler was lost: M0 only, its second pass due
    TabMeasure._on_dual_ended(fake, "dual_dual_needs_ruler")
    TabMeasure._dual_strip_measured(fake, {"strip": "B"})
    TabMeasure._dual_flush(fake, str(main), 2)
    rec = PassRecord.load(Run.dual_pass_record(main))
    assert rec.missing() == [("B", "uv")]
    assert rec.uv["B"].reason == "dual_needs_ruler"
    assert storage.strips_without_second_pass(main) == ["B"]


def test_build_from_is_set_to_the_choice_once(qapp, tmp_path, monkeypatch):
    from core.file_manager import Run
    from ui.tabs.tab_profile import TabProfile
    from workflow.dual_scan.record import PassRecord
    main = _dual_main(tmp_path)
    rec = PassRecord(["A"], chosen="M2")
    rec.helper_strip("A", True, "", "c1")
    rec.save(Run.dual_pass_record(main))
    from workflow import i1pro3_conditions as ic
    monkeypatch.setattr(ic, "condition_file", lambda m, c: Path(m))
    saved = []
    fake = SimpleNamespace(_ti3_path=main, _build_from="",
                           _dual_note_lbl=None,
                           save_target_settings=lambda: saved.append(1) or True,
                           _refresh_build_from=lambda: None)
    fake._dual_preset_commit = lambda m, c: TabProfile._dual_preset_commit(
        fake, m, c)
    fake._dual_preset_commit_pending = lambda: None
    TabProfile._dual_preset_once(fake, True)
    assert fake._build_from == "M2"
    # a load of the target's settings before it is stored: set again
    fake._build_from = ""
    TabProfile._dual_preset_once(fake, True)
    assert fake._build_from == "M2"
    TabProfile._dual_preset_commit(fake, main, "M2")
    assert saved and PassRecord.load(Run.dual_pass_record(main)).preset_done
    fake._build_from = "M1"                 # the person's later choice
    TabProfile._dual_preset_once(fake, True)
    assert fake._build_from == "M1", "never a second time"


def test_until_every_strip_has_both_passes_it_says_why(qapp, tmp_path):
    from core.file_manager import Run
    from ui.tabs.tab_profile import TabProfile
    from workflow.dual_scan.record import PassRecord
    main = _dual_main(tmp_path)
    rec = PassRecord(["A", "B"], chosen="M2")
    rec.helper_strip("A", True, "", "c1")
    rec.helper_lamp_only("B", "dual_needs_ruler")
    rec.save(Run.dual_pass_record(main))
    shown = {}
    lbl = SimpleNamespace(setText=lambda t: shown.__setitem__("t", t),
                          setVisible=lambda v: shown.__setitem__("v", v))
    fake = SimpleNamespace(_ti3_path=main, _build_from="",
                           _dual_note_lbl=lbl,
                           save_target_settings=lambda: None,
                           _dual_preset_commit=lambda m, c: None,
                           _dual_preset_commit_pending=lambda: None)
    TabProfile._dual_preset_once(fake, True)
    assert fake._build_from == ""
    # 4.3.49 (Basti, 2026-11-19): the engine keeps the record, so a strip
    # with M0 only is completed by Continue Measurement, and the line says so
    assert shown["v"] is True and "M2" in shown["t"]
    # (no condition files at all here: the review's SHOULD-1 sentence)
    assert "back to strip A" in shown["t"] and "keep their" not in shown["t"]
    assert "Continue Measurement" in shown["t"]
    assert "measure the chart again" not in shown["t"]


def test_the_filter_refused_variant_points_to_the_dual_scan(qapp):
    from ui.tabs.tab_measure import TabMeasure
    fake = SimpleNamespace(
        _settings=_S({"i1pro3_conditions_beta": True}),
        _reported_instrument="X-Rite i1 Pro 2", _dual_caps=lambda: CAPS,
        _measure_filter_code=lambda: "5",
        _start_button_name=lambda: "Start Measurement")
    t, b = TabMeasure._dual_filter_refused_variant(fake, "M1")
    assert t == "The i1Pro 2 gives M1 and M2 only with a dual scan"
    assert D.switch_label() in b and "Preferences > Beta" in b
    # today's text: another instrument, M0, an old helper, or the Beta on
    for change in ({"_reported_instrument": "X-Rite i1 Pro 3"},
                   {"_measure_filter_code": lambda: "n"},
                   {"_dual_caps": lambda: frozenset()},
                   {"_settings": _on()}):
        f2 = SimpleNamespace(**{**vars(fake), **change})
        assert TabMeasure._dual_filter_refused_variant(f2, "M1") is None


def test_preferences_the_switch_lives_under_the_i1pro3_beta(qapp, tmp_path):
    from ui.dialogs.settings_dialog import SettingsDialog
    from core.settings import AppSettings
    s = AppSettings()
    s.set("i1pro3_conditions_beta", False)
    s.set(D.SETTING, False)
    d = SettingsDialog(s)
    try:
        assert d._i1pro2_dual_check.text() == D.switch_label()
        assert not d._i1pro2_dual_check.isEnabled()
        d._i1pro3_conditions_check.setChecked(True)
        assert d._i1pro2_dual_check.isEnabled()
        d._i1pro2_dual_check.setChecked(True)
        d._save_and_close()
        assert s.get(D.SETTING) is True
    finally:
        d.reject()
        s.set("i1pro3_conditions_beta", False)
        s.set(D.SETTING, False)


# ------------------------------------- where the pass prompt lives (Basti)

@pytest.mark.parametrize("size", [(1500, 1000), (900, 620)])
def test_the_pass_prompt_is_the_tabs_own_status_line_and_covers_nothing(
        qapp, tmp_path, size):
    """Basti, watching the drive (2026-11-18): "the yellow box for the uv
    pass info looks out of place and seems to cover other infos". The pass
    information is a variant of the tab's own strip prompt line (the status
    line under the log), never the preview's amber banner; it lies beside
    the log, the buttons and the chart preview, never over them."""
    from PyQt6.QtCore import QRect
    from tests.test_b202_the_i1pro_generation_is_read_right import _tab
    tab = _tab(tmp_path)
    tab.resize(*size)
    tab.show()
    qapp.processEvents()
    tab._dual_reset()
    tab._dual_live = True
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": True})
    tab._flash_status("an unrelated line", 1)
    for _ in range(20):
        qapp.processEvents()
    import time
    time.sleep(0.05)
    qapp.processEvents()
    tab._hide_status_flash()
    lbl = tab._status_bar_lbl
    assert lbl.isVisible()
    assert lbl.text() == "Strip A, pass 2 of 2 (UV light)", "one line"
    assert lbl.toolTip().startswith("Now read strip A once more")
    assert not tab._preview._banner_lbl.isVisible(), "no box over the chart"

    def rect(w):
        return QRect(w.mapTo(tab, w.rect().topLeft()), w.size())
    mine = rect(lbl)
    for other in (tab._log, tab._start_btn, tab._stop_btn, tab._preview):
        if other.isVisible():
            assert not mine.intersects(rect(other)), other.objectName() or other
    # the pass ends: the line goes, and nothing else of the tab's is hidden
    tab._on_dual_pass_result({"what": "strip", "strip": "A", "ok": True,
                              "why": "", "pairing": "checked"})
    assert not lbl.isVisible()
    tab.close()


def test_with_the_beta_off_the_status_line_is_never_touched(qapp, tmp_path):
    from tests.test_b202_the_i1pro_generation_is_read_right import _tab
    tab = _tab(tmp_path)
    tab._flash_status("something else", 60000)
    tab._refresh_dual_note()
    tab._dual_session_over()
    qapp.processEvents()
    assert tab._status_bar_lbl.text() == "something else"
    assert not tab._status_bar_lbl.isHidden()
    tab.close()
