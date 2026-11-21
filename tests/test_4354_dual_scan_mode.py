"""4.3.54: WHEN the i1Pro 2 dual scan runs (the owner, 2026-11-20).

"for the dual scan i think this could be nice to leave it always on but then at least
selectable in a combobox as part of this option one should be able to choose whether to only
use the dual scan when choosing another measurement condition then m0. so choosing m0 would
only do the regular scan and m1 or m2 would do the 2 pass dual scan and save all conditions."

Pinned here (docs/design/i1pro2_dual_scan.md section 16):

* "always": every strip twice, as 4.3.53 (the plan is 4.3.53's, argument for argument);
* "m1_m2": M0 chosen = the ordinary single scan (no --dual-*, no -F n), M1 / M2 chosen =
  the dual scan with every condition saved, exactly as "always";
* Guided offers no condition choice: there the dual scan runs as with "always";
* a continued measurement keeps the kind it was STARTED with (its own record), whatever
  is chosen now;
* the default: "m1_m2" for a new store, "always" written ONCE for a store whose dual scan
  was already on when 4.3.54 first ran.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.dual_scan import session as D          # noqa: E402
from workflow.dual_scan import storage                # noqa: E402

CAPS = frozenset({storage.CAPABILITY, storage.DEVICE_CAPABILITY, "i1pro3_conditions"})


class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def _on(mode=None, **kw):
    s = _S({"i1pro3_conditions_beta": True, D.SETTING: True, **kw})
    if mode is not None:
        s[D.MODE_SETTING] = mode
    return s


def _main(tmp_path, *, dual):
    p = tmp_path / "chart.ti3"
    head = ['CTI3', 'TARGET_INSTRUMENT "X-Rite i1Pro 2"']
    if dual:
        head += ['CHROMIQ_DUAL_SCAN "i1pro2"', 'CHROMIQ_DUAL_SCALE "1.1560"',
                 'CHROMIQ_DUAL_SCALE_SOURCE "standard"',
                 'CHROMIQ_DUAL_WHITE "instrument"', 'CHROMIQ_DUAL_CHOSEN "M0"']
    p.write_text("\n".join(head + [
        "NUMBER_OF_FIELDS 2", "BEGIN_DATA_FORMAT", "SAMPLE_ID SAMPLE_LOC",
        "END_DATA_FORMAT", "NUMBER_OF_SETS 1", "BEGIN_DATA", '1 "A1"',
        "END_DATA", ""]), encoding="latin-1")
    return p


# ------------------------------------------------------------------ the mode itself

def test_the_mode_reads_only_its_two_words_and_defaults_to_m1_m2():
    assert D.mode(_S()) == D.MODE_M1_M2
    assert D.mode(_S({D.MODE_SETTING: "always"})) == D.MODE_ALWAYS
    assert D.mode(_S({D.MODE_SETTING: " ALWAYS "})) == D.MODE_ALWAYS
    assert D.mode(_S({D.MODE_SETTING: "sometimes"})) == D.MODE_M1_M2
    assert [k for k, _ in D.mode_labels()] == [D.MODE_ALWAYS, D.MODE_M1_M2]


def test_the_default_in_the_store_is_m1_m2():
    from core.settings import DEFAULTS
    assert DEFAULTS[D.MODE_SETTING] == D.MODE_M1_M2


# ------------------------------------------------------------------ mode x condition x module

@pytest.mark.parametrize("code", [None, "", "n", "5", "u"])
def test_always_is_4353_argument_for_argument(code):
    """"always" plans what 4.3.53 planned for every condition (no mode key existed)."""
    plan = D.plan_for(_on(D.MODE_ALWAYS), CAPS, None, code)
    assert plan.dual is True and not plan.single_i1pro2
    assert plan.chosen == D.FILTER_CHOICE[code]
    assert plan.args() == storage.helper_args(plan.choice, "instrument", plan.chosen)


@pytest.mark.parametrize("code", [None, "", "n"])
def test_m1_m2_with_m0_chosen_is_the_ordinary_single_scan(code):
    plan = D.plan_for(_on(D.MODE_M1_M2), CAPS, None, code)
    assert plan.dual is False and plan.refusal == ""
    assert plan.why_not == "m0_chosen" and plan.single_i1pro2
    assert plan.args() == []


@pytest.mark.parametrize("code,chosen", [("5", "M1"), ("u", "M2")])
def test_m1_m2_with_m1_or_m2_chosen_is_the_dual_scan_of_always(code, chosen):
    b = D.plan_for(_on(D.MODE_M1_M2), CAPS, None, code)
    a = D.plan_for(_on(D.MODE_ALWAYS), CAPS, None, code)
    assert b.dual and b.chosen == chosen
    assert b.args() == a.args()


@pytest.mark.parametrize("mode", D.MODES)
@pytest.mark.parametrize("code", [None, "n", "5", "u"])
def test_guided_has_no_choice_so_the_dual_scan_runs_as_always(mode, code):
    plan = D.plan_for(_on(mode), CAPS, None, code, condition_offered=False)
    assert plan.dual is True


@pytest.mark.parametrize("mode", D.MODES)
def test_off_other_instrument_and_refusals_come_first_in_both_modes(mode):
    assert D.plan_for(_S({D.MODE_SETTING: mode}), CAPS, None, "5").why_not == "off"
    assert D.plan_for(_on(mode), frozenset(), None, "5").why_not == "helper"
    assert D.plan_for(_on(mode), CAPS, "i1Pro3", "n").why_not == "other_instrument"
    assert not D.plan_for(_on(mode), CAPS, "i1Pro3", "n").single_i1pro2
    for code in ("p", "6"):
        assert D.plan_for(_on(mode), CAPS, None, code).refusal == "filter_not_dual"


# ------------------------------------------------------------------ Continue: the record decides

def test_started_as_reads_the_measurements_own_record(tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "s").mkdir()
    assert D.started_as(None) == ""
    assert D.started_as(tmp_path / "missing.ti3") == ""
    assert D.started_as(_main(tmp_path / "d", dual=True)) == "dual"
    assert D.started_as(_main(tmp_path / "s", dual=False)) == "single"


@pytest.mark.parametrize("code", [None, "n", "5", "u"])
def test_m1_m2_a_dual_measurement_continues_as_a_dual_scan(tmp_path, code):
    """Started as a dual scan: continued as one, also with M0 chosen now."""
    main = _main(tmp_path, dual=True)
    plan = D.plan_for(_on(D.MODE_M1_M2), CAPS, None, code, main)
    assert plan.dual is True and plan.refusal == ""
    assert plan.chosen == D.FILTER_CHOICE[code]


@pytest.mark.parametrize("code", [None, "n", "5", "u"])
def test_m1_m2_a_single_scan_measurement_continues_as_a_single_scan(tmp_path, code):
    """Started as a single scan: continued as one, also with M1 or M2 chosen now; never
    refused and never mixed."""
    main = _main(tmp_path, dual=False)
    plan = D.plan_for(_on(D.MODE_M1_M2), CAPS, None, code, main)
    assert plan.dual is False and plan.refusal == ""
    assert plan.why_not == "single_record" and plan.single_i1pro2


def test_m1_m2_a_dual_measurement_whose_header_lost_the_record_is_still_dual(tmp_path):
    """4.3.48 rewrote such a header without the record; the pass record still says dual."""
    main = _main(tmp_path, dual=False)
    from core.file_manager import Run
    from workflow.dual_scan.record import PassRecord
    PassRecord(strips=["A"]).save(Run.dual_pass_record(main))
    assert D.started_as(main) == "dual"
    plan = D.plan_for(_on(D.MODE_M1_M2), CAPS, None, "n", main)
    assert plan.dual and plan.ended_before


def test_always_keeps_refusing_a_single_scan_measurement_as_in_4353(tmp_path):
    main = _main(tmp_path, dual=False)
    assert D.plan_for(_on(D.MODE_ALWAYS), CAPS, None, "5", main).refusal == "mixed_scan_kind"


def test_guided_continues_by_the_record_too(tmp_path):
    main = _main(tmp_path, dual=False)
    plan = D.plan_for(_on(D.MODE_M1_M2), CAPS, None, None, main, condition_offered=False)
    assert plan.why_not == "single_record"


# ------------------------------------------------------------------ the tab: what START passes

def _tab_fake(tmp_path, plan):
    from ui.tabs.tab_measure import TabMeasure
    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    fake = SimpleNamespace(
        _settings=_on(), _ti1_path=run_dir / "P.ti1", _is_verification_run=lambda: False,
        _log=SimpleNamespace(appendPlainText=lambda *_: None, ensureCursorVisible=lambda: None),
        _dual_plan_now=lambda: plan)
    fake._condition_dir_for = lambda p: TabMeasure._condition_dir_for(fake, p)
    return fake


def _params(fake, extra):
    return SimpleNamespace(extra_args=extra, ti1_path=fake._ti1_path,
                           engine_condition_dir="KEPT", engine_dual_args=None)


@pytest.mark.parametrize("extra", ["", "-T 0.7", "-T 0.7 -l"])
def test_m0_chosen_without_minus_f_is_the_read_with_the_dual_scan_off(tmp_path, extra):
    """No -F in the row: START passes exactly what it passes with the dual scan off."""
    from ui.tabs.tab_measure import TabMeasure
    b = _tab_fake(tmp_path, D.plan_for(_on(D.MODE_M1_M2), CAPS, None, None))
    off = _tab_fake(tmp_path, D.Plan(False, why_not="off"))
    pb, poff = _params(b, extra), _params(off, extra)
    TabMeasure._apply_dual_scan(b, pb)
    TabMeasure._apply_dual_scan(off, poff)
    assert vars(pb) == vars(poff)
    assert b._dual_assumed == off._dual_assumed == ""


def test_m0_chosen_with_minus_f_n_drops_it_and_assumes_an_i1pro2(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    from workflow.dual_scan import instrument_model as IM
    fake = _tab_fake(tmp_path, D.plan_for(_on(D.MODE_M1_M2), CAPS, None, "n"))
    p = _params(fake, "-F n -T 0.7")
    TabMeasure._apply_dual_scan(fake, p)
    assert p.extra_args == "-T 0.7" and p.engine_dual_args is None
    assert p.engine_condition_dir == "KEPT"
    # an instrument that reports itself as another model is started again with -F n
    assert fake._dual_assumed == IM.I1PRO2
    assert fake._dual_master == ("-F n -T 0.7", "KEPT")


@pytest.mark.parametrize("code", ["5", "u"])
def test_m1_or_m2_chosen_passes_what_always_passes(tmp_path, code):
    from ui.tabs.tab_measure import TabMeasure
    b = _tab_fake(tmp_path, D.plan_for(_on(D.MODE_M1_M2), CAPS, None, code))
    a = _tab_fake(tmp_path, D.plan_for(_on(D.MODE_ALWAYS), CAPS, None, code))
    pb, pa = _params(b, f"-F {code} -T 0.7"), _params(a, f"-F {code} -T 0.7")
    TabMeasure._apply_dual_scan(b, pb)
    TabMeasure._apply_dual_scan(a, pa)
    assert vars(pb) == vars(pa)
    assert pb.extra_args == "-T 0.7" and "--dual-scale" in pb.engine_dual_args


# ------------------------------------------------------------------ default and migration

def _store(tmp_path, monkeypatch, values: dict, schema: int = 34):
    """An AppSettings on a file of its own (the suite's sandbox is shared per worker);
    the returned factory opens the same file again, as a restart does."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    path = str(tmp_path / "s.ini")

    def AS():
        s = AppSettings()
        s._qs = QSettings(path, QSettings.Format.IniFormat)
        return s
    s = AS()
    s._qs.setValue("settings_schema", schema)
    for k, v in values.items():
        s._qs.setValue(k, v)
    s._qs.sync()
    return AS


@pytest.mark.parametrize("stored", [True, "true"])
def test_a_store_with_the_dual_scan_already_on_keeps_always(tmp_path, monkeypatch, stored):
    AS = _store(tmp_path, monkeypatch, {D.SETTING: stored})
    s = AS()
    s.migrate()
    assert D.mode(s) == D.MODE_ALWAYS
    assert s.is_stored(D.MODE_SETTING)


@pytest.mark.parametrize("values", [{}, {D.SETTING: False}, {D.SETTING: "false"}])
def test_a_store_with_the_dual_scan_off_or_absent_gets_m1_m2(tmp_path, monkeypatch, values):
    AS = _store(tmp_path, monkeypatch, values)
    s = AS()
    s.migrate()
    assert D.mode(s) == D.MODE_M1_M2


def test_it_is_decided_once_and_never_again(tmp_path, monkeypatch):
    """Switching the dual scan on AFTER the first start of 4.3.54 does not move the mode:
    the decision is the schema step's, made once."""
    AS = _store(tmp_path, monkeypatch, {})
    s = AS()
    s.migrate()
    s.set(D.SETTING, True)
    s2 = AS()
    s2.migrate()
    assert D.mode(s2) == D.MODE_M1_M2
    # and a person's own choice is never overwritten by a later start
    s2.set(D.MODE_SETTING, D.MODE_ALWAYS)
    AS().migrate()
    assert D.mode(AS()) == D.MODE_ALWAYS


def test_a_mode_already_stored_is_never_overwritten_by_the_step(tmp_path, monkeypatch):
    AS = _store(tmp_path, monkeypatch, {D.SETTING: True, D.MODE_SETTING: "m1_m2"})
    s = AS()
    s.migrate()
    assert D.mode(s) == D.MODE_M1_M2


# ------------------------------------------------------------------ the helper's command line

def _argv(tmp_path, monkeypatch, plan, extra):
    """The whole command line the chart-reading engine is started with, from START's
    parameters after `_apply_dual_scan` (the real MeasureManager builds it)."""
    from tests.test_i1pro3_conditions_beta_option import _Runner
    from ui.tabs.tab_measure import TabMeasure
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps", lambda helper=None: frozenset(CAPS))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port", lambda self, *a, **k: False)
    fake = _tab_fake(tmp_path, plan)
    p = MeasureParams(ti1_path=fake._ti1_path, engine_helper=tmp_path / "chromiq-chartread",
                      engine_condition_dir=fake._ti1_path.parent / "conditions",
                      extra_args=extra)
    TabMeasure._apply_dual_scan(fake, p)
    runner = _Runner()
    MeasureManager(runner).start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1]


@pytest.mark.parametrize("extra", ["", "-T 0.7", "-F n -T 0.7"])
def test_on_the_wire_m0_chosen_is_the_measurement_with_the_dual_scan_off(
        tmp_path, monkeypatch, extra):
    """The helper is the only thing that talks to the instrument, and what it sends follows
    from its command line alone (the driver's dual hooks are no-ops without --dual-*:
    tests/test_i1pro2_dual_scan_device.py, 'a single scan sends exactly what it sent before').
    "-F n" with the dual scan OFF goes to ArgyllCMS, which refuses it for an i1Pro 2 before a
    reading: there the only difference is that the measurement now starts."""
    b = _argv(tmp_path, monkeypatch, D.plan_for(_on(D.MODE_M1_M2), CAPS, None, "n" if "-F" in extra
                                                else None), extra)
    off = _argv(tmp_path, monkeypatch, D.Plan(False, why_not="off"), extra.replace("-F n ", ""))
    assert b == off
    assert not any(a.startswith("--dual") for a in b) and "-F" not in b


@pytest.mark.parametrize("code", ["5", "u"])
def test_on_the_wire_m1_or_m2_chosen_is_todays_dual_scan(tmp_path, monkeypatch, code):
    b = _argv(tmp_path, monkeypatch, D.plan_for(_on(D.MODE_M1_M2), CAPS, None, code),
              f"-F {code} -T 0.7")
    a = _argv(tmp_path, monkeypatch, D.plan_for(_on(D.MODE_ALWAYS), CAPS, None, code),
              f"-F {code} -T 0.7")
    # 4.3.53 had no mode: its plan is "always"'s (test_always_is_4353_argument_for_argument)
    assert b == a and "--dual-scale" in b and "-F" not in b
