"""The i1Pro 2 dual scan, fix round after the independent UI review
(2026-11-18, ~/Desktop/ChromIQ-work/2026-11-18_dual_scan/ui_review).

One test (or a few) per finding, each written to fail on the reviewed head
044a9bbcf and to pass after the fix:

* M-1 Continue Measurement after M1 / M2 ended: nothing promises them back;
* M-2 a new measurement into the same file starts a fresh pass record
  (``test_i1pro2_dual_scan_ui_review.py``);
* M-3 every sentence says what really happens;
* S-1 / the owner's decision 2: which instrument is connected is known
  before START (USB, then remembered, then one question), and the
  instrument's own report at the start wins;
* S-2 a kept failure belongs to its own strip (review test file);
* S-3 the two planted faults that survived;
* S-4 no reason id is ever shown as text;
* S-5 "Skip initial calibration (-N)" with the dual scan is refused;
* the NOTEs: an honest pass prompt after a refused calibration, a readable
  pass line, and a simulated helper that ends as the real one does.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M          # noqa: E402
from workflow.dual_scan import instrument_model as IM   # noqa: E402
from workflow.dual_scan import session as D             # noqa: E402
from workflow.dual_scan import storage                  # noqa: E402
from workflow.dual_scan.reasons import REASONS          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CAPS = frozenset({storage.CAPABILITY, storage.DEVICE_CAPABILITY,
                  "i1pro3_conditions"})


class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def _on(**kw):
    return _S({"i1pro3_conditions_beta": True, D.SETTING: True, **kw})


def _fake(tmp_path, strips=("A", "B"), **kw):
    from ui.tabs.tab_measure import TabMeasure
    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    logged, notices, flashes = [], [], []
    fake = SimpleNamespace(
        _settings=_on(), _ti1_path=run_dir / "P.ti1",
        _log=SimpleNamespace(appendPlainText=logged.append,
                             ensureCursorVisible=lambda: None),
        _manager=SimpleNamespace(_session_strips=[{"strip": s}
                                                  for s in strips]),
        _preview=SimpleNamespace(
            set_notice=lambda *a, **k: notices.append(a[0] if a else None)),
        _strip_name=lambda s: s,
        _hide_status_flash=lambda: flashes.append("hide"),
        _flash_status=lambda t, ms=0: flashes.append(t),
        _set_autosave_banner=lambda *a: notices.append("autosave"),
        **kw)
    fake._dual_strip_labels = lambda: TabMeasure._dual_strip_labels(fake)
    fake._dual_status = lambda t, d="": None
    fake._dual_prompt = lambda t, b: fake.__dict__.setdefault(
        "prompts", []).append((t, b))
    fake._dual_tile_released = lambda: TabMeasure._dual_tile_released(fake)
    fake._dual_calibration_parts = (
        lambda: TabMeasure._dual_calibration_parts(fake))
    fake._dual_calibration_log = (
        lambda parts=None: TabMeasure._dual_calibration_log(fake, parts))
    return fake, logged, notices, flashes


def _dual_main(tmp_path, *, readings=True):
    p = tmp_path / "chart.ti3"
    head = ['CTI3', 'TARGET_INSTRUMENT "X-Rite i1Pro 2"',
            'CHROMIQ_DUAL_SCAN "i1pro2"', 'CHROMIQ_DUAL_SCALE "1.1560"',
            'CHROMIQ_DUAL_SCALE_SOURCE "standard"',
            'CHROMIQ_DUAL_WHITE "instrument"', 'CHROMIQ_DUAL_CHOSEN "M2"']
    rows = ['1 "A1"'] if readings else []
    p.write_text("\n".join(head + [
        "NUMBER_OF_FIELDS 2", "BEGIN_DATA_FORMAT", "SAMPLE_ID SAMPLE_LOC",
        "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA",
        *rows, "END_DATA", ""]), encoding="latin-1")
    return p


# ------------------------------------------------------------ S-3 (planted)

def test_a_refused_second_pass_is_never_recorded_as_good(qapp, tmp_path):
    """Planted fault 3 of the review: the refused pass recorded as good."""
    from core.file_manager import Run
    from ui.tabs.tab_measure import TabMeasure
    from workflow.dual_scan.record import PassRecord
    fake, *_ = _fake(tmp_path)
    TabMeasure._dual_reset(fake)
    TabMeasure._on_dual_session(fake, {"active": True, "dual": True,
                                       "scale": 1.156, "chosen": "M1"})
    TabMeasure._on_dual_pass_result(fake, {"what": "strip", "strip": "A",
                                           "ok": False,
                                           "why": "uv_pass_wrong_strip"})
    main = fake._ti1_path.with_suffix(".ti3")
    main.write_text("CTI3\n", encoding="latin-1")
    TabMeasure._dual_flush(fake, str(main), 1)
    rec = PassRecord.load(Run.dual_pass_record(main))
    assert rec.uv["A"].state != "ok"
    assert rec.uv["A"].reason == "uv_pass_wrong_strip"
    assert ("A", "uv") in rec.missing()
    assert rec.strips_with_both() == []


def test_keep_it_on_the_tile_stays_until_calibration_complete(qapp, tmp_path):
    """Planted fault 4 of the review: "keep it on the tile" released at
    once, before the engine's cal_done (safety review S5)."""
    from ui.tabs.tab_measure import TabMeasure
    fake, logged, notices, flashes = _fake(tmp_path)
    TabMeasure._dual_reset(fake)
    fake._dual_live = True
    TabMeasure._dual_calibrating(fake)
    tile = M.M_DUAL_CAL_TILE.render()
    assert fake._dual_tile_wait is True
    assert notices[-1] == tile[1]
    assert flashes[-1] == tile[0]
    # the autosave line may not take its place while the tile is read
    assert TabMeasure._dual_notice_shown(fake) is True
    # the tile's UV reading came back; still nothing released
    TabMeasure._on_dual_calibration(fake, {"ok": True, "lamp_clocks": 139,
                                           "uv_clocks": 139})
    assert fake._dual_tile_wait is True
    # Calibration Complete releases it
    from PyQt6.QtWidgets import QDialog, QVBoxLayout
    dlg = QDialog()
    TabMeasure._dual_calibration_done(fake, QVBoxLayout(dlg), dlg)
    assert fake._dual_tile_wait is False
    assert notices[-1] == "autosave"
    dlg.deleteLater()


# --------------------------------------------------------------------- S-4

def _engine_reason_ids() -> "set[str]":
    """Every reason the helper's dual paths can give (C sources)."""
    src = ROOT / "native" / "chartread_helper"
    ids: "set[str]" = set()
    # the calculation's own ids also reach the tab as "dual_<id>"
    # (chromiq_chartread.c: snprintf(buf, ..., "dual_%s", r))
    calc = (src / "chromiq_dualscan.c").read_text(encoding="utf-8",
                                                  errors="replace")
    ids |= {"dual_" + i for i in re.findall(r'return "([a-z_]+)";', calc)}
    for name in ("chromiq_dualscan.c", "chromiq_dualdev.c"):
        text = (src / name).read_text(encoding="utf-8", errors="replace")
        ids |= set(re.findall(r'return "([a-z_]+)";', text))
        ids |= set(re.findall(r'why = "([a-z_]+)";', text))
        ids |= set(re.findall(r'cal_why = "([a-z_]+)";', text))
    cr = (src / "chromiq_chartread.c").read_text(encoding="utf-8",
                                                 errors="replace")
    ids |= set(re.findall(r'cq_cond_lose\("([a-z_]+)"\)', cr))
    # cq_cond_for_session's reasons, and the formed "dual_<id>" ones
    body = cr[cr.index("static void cq_cond_for_session"):]
    body = body[:body.index("\n}\n")]
    ids |= set(re.findall(r'why = "([a-z_]+)";', body))
    ids |= set(re.findall(r'why = "(dual_[a-z_]+)";', cr))
    return ids - {"lamp"}      # "lamp": ArgyllCMS's own misread window


def test_no_reason_id_is_ever_shown_as_text():
    ids = _engine_reason_ids()
    assert len(ids) > 40
    fallback = D.reason_sentence("a_brand_new_id_nobody_wrote_a_sentence_for")
    assert "a_brand_new_id" not in fallback
    plain = []
    for rid in sorted(ids):
        text = D.reason_sentence(rid)
        if "_" in rid:          # (an id like "files" is also a plain word)
            assert rid not in text, (rid, text)
        if text == fallback:
            plain.append(rid)
    assert plain == [], f"no sentence of their own: {plain}"
    # every id the tab can show is extracted for translation
    assert set(D.SHOWN_REASONS) >= {D.reason_id(i) for i in ids} - {""}


# --------------------------------------------------------------------- M-3

SESSION_LEVEL = ("no_dual_calibration", "uv_tile_dark", "calibration_mismatch",
                 "calibration_mode_changed", "bad_values", "dual_needs_ruler",
                 "no_uv_tables", "bad_uv_tables", "not_available", "record",
                 "memory", "conversion", "write", "resume", "mode", "files")


@pytest.mark.parametrize("rid", SESSION_LEVEL)
def test_a_session_level_reason_carries_no_action_the_ending_contradicts(rid):
    text = REASONS[rid]
    for wrong in ("Calibrate again", "Read it again", "M0 goes on",
                  "Read the strip again"):
        assert wrong not in text, (rid, wrong)
    title, body = M.M_DUAL_ENDED.render(reason=D.reason_sentence(rid))
    assert body.count("M0") >= 1
    assert "carry on measuring" in body
    assert "Continue Measurement cannot add M1 and M2" in body
    assert "measure the chart again" in body


def test_the_ending_after_a_lost_ruler_says_m0_goes_on_once():
    _t, body = M.M_DUAL_ENDED.render(
        reason=D.reason_sentence("dual_dual_needs_ruler"))
    assert "M0 goes on as always" not in body
    assert body.count("carry on measuring") == 1


def test_a_failed_uv_tile_reading_is_not_called_a_single_scan_calibration():
    text = REASONS["no_dual_calibration"]
    assert "made for single scans" not in text
    assert "did not succeed" in text


def test_no_ruler_says_both_passes_again_like_every_pass_reason():
    assert "both passes" in REASONS["no_ruler"]


def test_the_filter_refused_window_names_the_option_the_dual_switch_is_under(
        qapp):
    from ui.tabs.tab_measure import TabMeasure
    fake = SimpleNamespace(
        _settings=_S({}), _reported_instrument="X-Rite i1 Pro 2",
        _dual_caps=lambda: CAPS, _measure_filter_code=lambda: "5",
        _start_button_name=lambda: "Start Measurement")
    t, b = TabMeasure._dual_filter_refused_variant(fake, "M1")
    assert D.parent_label() in b and D.switch_label() in b
    # with the option above on, only the dual switch is named
    fake._settings = _S({"i1pro3_conditions_beta": True})
    _t, b2 = TabMeasure._dual_filter_refused_variant(fake, "M1")
    assert D.switch_label() in b2 and D.parent_label() not in b2


# --------------------------------------------------------------------- M-1

def test_m1_and_m2_that_ended_are_completed_by_continue(qapp, tmp_path):
    """4.3.49 (Basti, 2026-11-19; was "never promised back"): the engine
    keeps the record of a dual measurement, so a strip with M0 only is read
    again with both passes by Continue Measurement, and every sentence says
    so. A dual main without any pair: every read strip has M0 only."""
    from core.file_manager import Run
    from workflow import i1pro3_conditions as ic
    from workflow.dual_scan.record import PassRecord
    main = _dual_main(tmp_path)               # no condition files at all
    plan = D.plan_for(_on(), CAPS, None, "u", main)
    assert plan.dual and not plan.ended_before and plan.m0_only == ("A",)
    assert "--dual-scale" in plan.args()
    rec = PassRecord(["A", "B"], chosen="M2")
    rec.helper_lamp_only("A", "dual_needs_ruler")
    rec.save(Run.dual_pass_record(main))
    why = ic.no_file_reason(main)
    assert "Continue Measurement" in why and "M0 only: A" in why
    assert "measure the chart again" not in why
    # the note before START
    from ui.tabs.tab_measure import TabMeasure
    fill = M.M_DUAL_CONTINUE_FILL.render(strips="A")
    fake = SimpleNamespace(_dual_plan_now=lambda: plan,
                           _fill_note_text=lambda: fill)
    assert TabMeasure._dual_before_start_text(fake) == fill


def test_after_a_continue_the_engine_rewrote_the_header_it_stays_ended(
        qapp, tmp_path):
    """Measured on screen (2026-11-18, en-ended): a Continue after M1 / M2
    ended makes the real helper write the main file again WITHOUT its dual
    record. A third START must not be refused as "started as a single
    scan", and no text may call it an i1Pro 3 matter."""
    from core.file_manager import Run
    from workflow import i1pro3_conditions as ic
    from workflow.dual_scan.record import PassRecord
    main = _dual_main(tmp_path)
    text = main.read_text(encoding="latin-1")
    main.write_text("\n".join(ln for ln in text.splitlines()
                              if "CHROMIQ_DUAL" not in ln) + "\n",
                    encoding="latin-1")
    assert not storage.read_dual_record(main).dual
    rec = PassRecord(["A", "B"], chosen="M2")
    rec.helper_strip("A", True, "", "c1")
    rec.helper_lamp_only("B", "dual_needs_ruler")
    rec.save(Run.dual_pass_record(main))
    plan = D.plan_for(_on(), CAPS, None, "u", main)
    assert plan.dual and plan.ended_before and plan.refusal == ""
    why = ic.no_file_reason(main)
    assert "Only an X-Rite i1Pro 3" not in why
    assert "measure the chart again" in why
    from ui.tabs.tab_measure import TabMeasure
    fake, logged, *_ = _fake(tmp_path)
    TabMeasure._dual_reset(fake)
    fake._dual_ended_before = True
    TabMeasure._on_dual_ended(fake, "mixed")
    assert REASONS["resume"].split(":")[0] in fake._dual_ended_text


def test_a_measurement_stopped_early_with_its_files_in_step_continues_dual(
        qapp, tmp_path, monkeypatch):
    from core.file_manager import Run
    from workflow import i1pro3_conditions as ic
    from workflow.dual_scan.record import PassRecord
    main = _dual_main(tmp_path)
    monkeypatch.setattr(ic, "condition_file", lambda m, c: Path(m))
    plan = D.plan_for(_on(), CAPS, None, "u", main)
    assert plan.dual and not plan.ended_before
    rec = PassRecord(["A", "B"], chosen="M2")
    rec.helper_strip("A", True, "", "c1")
    rec.save(Run.dual_pass_record(main))
    why = ic.no_file_reason(main)
    assert "not every strip has been read" in why and "(B)" in why
    assert "both passes" in why


def test_a_resume_refused_by_the_engine_reaches_the_tab_as_a_dual_end(qapp):
    from workflow.measure_manager import MeasureManager

    class _R:
        is_running = True

        def write_stdin(self, _d):
            pass
    m = MeasureManager(_R())
    m._engine_active = True
    m._guided_state = "disabled"
    got = []
    m.dual_ended.connect(got.append)
    m._dual_requested = True
    m._engine_model = "i1Pro2"
    m._handle_engine_line(
        '{"event":"conditions","active":false,"why":"resume"}', lambda _l: None)
    assert got == ["resume"]
    # an i1Pro 3 session without the dual arguments: the i1Pro 3 Beta's own
    m._dual_requested = False
    m._engine_model = "i1Pro3"
    m._handle_engine_line(
        '{"event":"conditions","active":false,"why":"resume"}', lambda _l: None)
    assert got == ["resume"]


def test_the_tab_records_strips_read_after_an_end_at_the_start(qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    fake, logged, *_ = _fake(tmp_path)
    TabMeasure._dual_reset(fake)
    TabMeasure._on_dual_ended(fake, "resume")
    assert fake._dual_started is True
    TabMeasure._dual_strip_measured(fake, {"strip": "B"})
    assert ("lamp_only", "B", "resume") in fake._dual_buffer
    assert any(M.M_DUAL_ENDED.render(
        reason=D.reason_sentence("resume"))[0] in ln for ln in logged)


# --------------------------------------------------------------------- S-5

def _start_fake(tmp_path, plan, nocal):
    from ui.tabs.tab_measure import TabMeasure
    said = []
    fake = SimpleNamespace(
        _settings=_on(), _dual_plan_now=lambda: plan,
        _dual_nocal_now=lambda: nocal, _engine_selected=lambda: True,
        _measurement_to_continue=lambda: None, _dual_caps=lambda: CAPS,
        _dual_model_for_plan=lambda: None,
        _filter_label=lambda c: str(c), _measure_filter_code=lambda: "u",
        _start_button_name=lambda: "Start Measurement",
        _log=SimpleNamespace(appendPlainText=lambda *_a: None,
                             ensureCursorVisible=lambda: None),
        _sound=None, _say_on_screen=lambda t, b: said.append((t, b)))
    return TabMeasure._blocked_by_dual_scan(fake), said


def test_skip_initial_calibration_with_the_dual_scan_is_refused(tmp_path):
    plan = D.plan_for(_on(), CAPS, None, "u")
    blocked, said = _start_fake(tmp_path, plan, nocal=True)
    assert blocked
    assert said[0][0] == M.M_DUAL_NOCAL_REFUSED.render(
        nocal="x", start="y", option="z", where="w")[0]
    assert "Skip initial calibration (-N)" in said[0][1]
    blocked, said = _start_fake(tmp_path, plan, nocal=False)
    assert not blocked and said == []
    # without the dual scan, -N is as always
    off = D.Plan(False, why_not="off")
    blocked, said = _start_fake(tmp_path, off, nocal=True)
    assert not blocked


# ------------------------------------------------------------------- NOTEs

def test_after_a_refused_calibration_the_pass_prompts_say_what_counts(
        qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    fake, *_ = _fake(tmp_path)
    TabMeasure._dual_reset(fake)
    fake._dual_live = True
    fake._spot_session = False
    TabMeasure._on_dual_calibration(fake, {"ok": False,
                                           "why": "uv_tile_dark"})
    TabMeasure._dual_pass_one(fake, "A")
    assert fake.prompts[-1] == M.M_DUAL_PASS_ONE_NO_CAL.render(strip="A")
    # 4.3.49: after such a calibration the engine asks for no second pass
    # (it reads the strip once and asks for a new calibration); a dual_pass
    # event can only be an ordinary one, M-DUAL-PASS-TWO-NO-CAL is withdrawn
    TabMeasure._on_dual_pass(fake, {"strip": "A", "lamp_ok": True})
    assert fake.prompts[-1] == M.M_DUAL_PASS_TWO.render(strip="A")
    # a good calibration again: the ordinary prompts
    TabMeasure._on_dual_calibration(fake, {"ok": True, "lamp_clocks": 139,
                                           "uv_clocks": 139})
    TabMeasure._dual_pass_one(fake, "B")
    assert fake.prompts[-1] == M.M_DUAL_PASS_ONE.render(strip="B")


def test_the_pass_line_is_as_readable_as_the_tabs_text(qapp, tmp_path):
    from tests.test_b202_the_i1pro_generation_is_read_right import _tab
    tab = _tab(tmp_path)
    # the main window's own style of the line (MainWindow._set_tab_status)
    base = "color: #909090; font-size: 11px; padding: 4px 16px 8px 16px;"
    tab._status_bar_lbl.setStyleSheet(base)
    tab._dual_reset()
    tab._dual_live = True
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": True})
    sheet = tab._status_bar_lbl.styleSheet()
    assert "font-weight: 600" in sheet and "palette(window-text)" in sheet
    assert sheet.startswith(base), "its padding stays"
    # a flashed line looks as always, and the pass line comes back bold
    tab._flash_status("an unrelated line", 60000)
    assert tab._status_bar_lbl.styleSheet() == base
    tab._hide_status_flash()
    assert "font-weight: 600" in tab._status_bar_lbl.styleSheet()
    tab._on_dual_pass_result({"what": "strip", "strip": "A", "ok": True,
                              "why": "", "pairing": "checked"})
    assert tab._status_bar_lbl.styleSheet() == base, "given back unchanged"
    tab.close()


# ------------------------------------------- which instrument (decision 2)

def _dev(*ids):
    from core.argyll_instruments import UsbDevice
    return tuple(UsbDevice(v, p) for v, p in ids)


@pytest.mark.parametrize("ids,family", [
    ((), None),
    (((0x0765, 0x6009),), IM.FAMILY_I1PRO3),
    (((0x0971, 0x2000),), IM.FAMILY_I1PRO),
    (((0x0971, 0x2007),), IM.FAMILY_OTHER),            # ColorMunki
    (((0x0971, 0x2000), (0x0765, 0x6009)), None),      # two: cannot tell
    (((0x1A86, 0x7523),), None),                       # not an instrument
])
def test_the_usb_connection_says_what_it_can(ids, family):
    assert IM.usb_family(_dev(*ids)) == family
    assert IM.usb_family(None) is None


def test_the_usb_ids_are_argylls_own():
    """ArgyllCMS 3.5.0 spectro/insttypes.c inst_usb_match: 0765:6009 is an
    i1Pro 3; 0971:2000 is an i1Pro or an i1Pro 2, told apart only by the
    pipe count, which the system list does not give."""
    text = (ROOT / "native/instlib/insttypes.c").read_text(
        encoding="utf-8", errors="replace")
    assert re.search(r"idProduct == 0x6009\)\s*/\* i1Pro 3 \*/\s*return "
                     r"instI1Pro3;", text)
    assert "if (idProduct == 0x2000) {\t/* i1Pro or i1Pro 2 */" in text
    assert "if (nep >= 5)\n\t\t\t\treturn instI1Pro2;" in text


@pytest.mark.parametrize("family,rem,kind,source", [
    (IM.FAMILY_I1PRO3, {}, IM.OTHER, "usb"),
    (IM.FAMILY_I1PRO3, {IM.SETTING: "i1pro2", IM.SETTING_SOURCE: "reported",
                        IM.SETTING_NAME: "i1Pro2"}, IM.OTHER, "usb"),
    (IM.FAMILY_OTHER, {}, IM.OTHER, "usb"),
    (IM.FAMILY_I1PRO, {IM.SETTING: "i1pro2", IM.SETTING_SOURCE: "reported",
                       IM.SETTING_NAME: "i1Pro2"}, IM.I1PRO2, "remembered"),
    (IM.FAMILY_I1PRO, {IM.SETTING: "other", IM.SETTING_SOURCE: "reported",
                       IM.SETTING_NAME: "i1Pro"}, IM.OTHER, "remembered"),
    (IM.FAMILY_I1PRO, {IM.SETTING: "other", IM.SETTING_SOURCE: "reported",
                       IM.SETTING_NAME: "i1Pro3"}, IM.ASK, ""),
    (IM.FAMILY_I1PRO, {IM.SETTING: "other", IM.SETTING_SOURCE: "chosen"},
     IM.OTHER, "remembered"),
    (IM.FAMILY_I1PRO, {}, IM.ASK, ""),
    (None, {IM.SETTING: "other", IM.SETTING_SOURCE: "reported",
            IM.SETTING_NAME: "i1Pro3"}, IM.OTHER, "remembered"),
    (None, {IM.SETTING: "i1pro2", IM.SETTING_SOURCE: "chosen"},
     IM.I1PRO2, "remembered"),
    (None, {}, IM.ASK, ""),
])
def test_the_order_of_knowing(family, rem, kind, source):
    dec = IM.resolve(_S(rem), family)
    assert (dec.kind, dec.source) == (kind, source)


def test_the_report_is_remembered_and_wins_over_a_choice():
    s = _S()
    IM.remember_choice(s, IM.I1PRO2)
    assert IM.remembered(s).source == "chosen"
    IM.remember_reported(s, "i1Pro3")
    assert IM.remembered(s) == IM.Remembered(IM.OTHER, "i1Pro3", "reported")
    assert IM.differs(IM.I1PRO2, "i1Pro3") and not IM.differs(
        IM.I1PRO2, "i1Pro2") and not IM.differs("", "i1Pro3")
    IM.forget(s)
    assert IM.remembered(s) == IM.Remembered()
    assert "asks" in IM.describe(s)


def _question_fake(settings, answer, plan=None):
    from ui.tabs.tab_measure import TabMeasure
    asked = []
    fake = SimpleNamespace(
        _settings=settings, _engine_selected=lambda: True,
        _dual_plan_now=lambda: plan or D.plan_for(_on(), CAPS, None, "u"),
        _dual_ask_model=lambda fam: asked.append(fam) or answer)
    fake._dual_model_decision = (
        lambda fresh=False: TabMeasure._dual_model_decision(fake, fresh))
    return TabMeasure._dual_question_cancelled(fake), asked, fake


@pytest.mark.parametrize("answer,cancelled,kept", [
    ("i1pro2", False, "i1pro2"), ("other", False, "other"),
    ("unsure", False, ""), (None, True, "")])
def test_one_question_when_nothing_tells(qapp, answer, cancelled, kept):
    s = _on()
    got, asked, fake = _question_fake(s, answer)
    assert asked == [None] and got is cancelled
    assert s.get(IM.SETTING, "") == kept
    if answer == "unsure":
        assert fake._dual_assume_once == IM.I1PRO2


def test_no_question_when_usb_tells_or_the_beta_is_off(qapp, monkeypatch):
    from core import argyll_instruments
    monkeypatch.setattr(argyll_instruments, "usb_devices",
                        lambda: _dev((0x0765, 0x6009)))
    got, asked, _ = _question_fake(_on(), "i1pro2")
    assert asked == [] and got is False
    # the Beta off: not even the USB list is read
    monkeypatch.setattr(argyll_instruments, "usb_devices",
                        lambda: (_ for _ in ()).throw(AssertionError("read")))
    got, asked, _ = _question_fake(_S(), "i1pro2")
    assert asked == [] and got is False


def test_the_question_names_how_to_tell_them_apart():
    title, body = M.M_DUAL_MODEL_ASK.render(usb="U.", where="Preferences > Beta")
    assert title == "Which instrument do you measure with?"
    for fact in ("Eye-One Pro Rev E", "Rev A, B or D", "ES-1000", "ES-2000",
                 "i1Pro 3 Plus", "Instrument Type:", "i1Pro2",
                 "could not check what is printed on the instrument's label",
                 "Not sure"):
        assert fact in body, fact


def test_argylls_documentation_says_what_the_question_says():
    """The identification text is verified, not remembered: ArgyllCMS
    3.5.0's own words (the vendored driver; its HTML documentation is not
    in the repository, see docs/design/i1pro2_dual_scan.md section 9)."""
    imp = (ROOT / "native/instlib/i1pro_imp.h").read_text(
        encoding="utf-8", errors="replace")
    assert "629 = Rev E (i1pro2)" in imp
    assert "502, 505, 631 = Rev D" in imp
    c = (ROOT / "native/instlib/i1pro_imp.c").read_text(
        encoding="utf-8", errors="replace")
    assert 'a1logv(p->log,1,"Instrument Type:   %s\\n",inst_name(p->dtype));' \
        in c
    t = (ROOT / "native/instlib/insttypes.c").read_text(
        encoding="utf-8", errors="replace")
    assert 'case instI1Pro2:\n\t\t\treturn "i1Pro2";' in t


def test_an_i1pro3_measures_exactly_as_on_master_with_the_switch_on(
        qapp, tmp_path, monkeypatch):
    """USB says i1Pro 3: no question, -F sent as before, no dual argument,
    and the filter-refused window is today's."""
    from core import argyll_instruments
    from ui.tabs.tab_measure import TabMeasure
    monkeypatch.setattr(argyll_instruments, "usb_devices",
                        lambda: _dev((0x0765, 0x6009)))
    fake = SimpleNamespace(_settings=_on())
    fake._dual_model_decision = (
        lambda fresh=False: TabMeasure._dual_model_decision(fake, fresh))
    model = TabMeasure._dual_model_for_plan(fake)
    assert model == D.NOT_I1PRO2
    plan = D.plan_for(_on(), CAPS, model, "u")
    assert not plan.dual and plan.why_not == "other_instrument"
    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True)
    f2 = SimpleNamespace(_settings=_on(), _ti1_path=run_dir / "P.ti1",
                         _dual_plan_now=lambda: plan)
    p = SimpleNamespace(extra_args="-F u -T 0.7", ti1_path=f2._ti1_path,
                        engine_condition_dir=run_dir / "conditions",
                        engine_dual_args=None, resume=False)
    TabMeasure._apply_dual_scan(f2, p)
    assert p.extra_args == "-F u -T 0.7" and p.engine_dual_args is None
    assert p.engine_condition_dir == run_dir / "conditions"
    f3 = SimpleNamespace(_settings=_on(), _reported_instrument="i1Pro3",
                         _dual_last_model="i1Pro3", _dual_caps=lambda: CAPS,
                         _measure_filter_code=lambda: "u",
                         _start_button_name=lambda: "Start Measurement")
    assert TabMeasure._dual_filter_refused_variant(f3, "M2") is None


@pytest.mark.parametrize("ids", [((0x0971, 0x2007),), ((0x0765, 0x5020),)])
def test_any_other_instrument_keeps_its_minus_f(ids, monkeypatch):
    from core import argyll_instruments
    from ui.tabs.tab_measure import TabMeasure
    monkeypatch.setattr(argyll_instruments, "usb_devices", lambda: _dev(*ids))
    fake = SimpleNamespace(_settings=_on())
    fake._dual_model_decision = (
        lambda fresh=False: TabMeasure._dual_model_decision(fake, fresh))
    assert not D.plan_for(_on(), CAPS, TabMeasure._dual_model_for_plan(fake),
                          "5").dual


def _report_fake(tmp_path, assumed, *, relaunch_ok=True, settings=None):
    from ui.tabs.tab_measure import TabMeasure
    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    relaunched, logged, notices = [], [], []
    started = SimpleNamespace(extra_args="-T 0.7", resume=False,
                              engine_condition_dir=run_dir / "conditions",
                              engine_dual_args=["--dual-scale", "1.1560"],
                              ti1_path=run_dir / "P.ti1", cal_auto_retries=3)
    fake = SimpleNamespace(
        _settings=_on() if settings is None else settings, _dual_assumed=assumed,
        _dual_model_checked=False, _dual_params=started,
        _dual_master=("-F u -T 0.7", run_dir / "conditions"),
        _manager=SimpleNamespace(
            relaunch_before_reading=lambda p: relaunched.append(p)
            or relaunch_ok),
        _log=SimpleNamespace(appendPlainText=logged.append,
                             ensureCursorVisible=lambda: None),
        _preview=SimpleNamespace(set_notice=lambda t, **k: notices.append(t)),
        _ti1_path=run_dir / "P.ti1", _dual_nocal_now=lambda: False)
    fake._dual_params_for = lambda k: TabMeasure._dual_params_for(fake, k)
    fake._dual_plan_now = lambda: D.plan_for(
        _on(), CAPS, TabMeasure._dual_model_for_plan(fake), "u")
    fake._dual_model_decision = lambda fresh=False: IM.Decision(IM.ASK)
    fake._condition_dir_for = lambda p: run_dir / "conditions"
    fake._apply_dual_scan = lambda p: TabMeasure._apply_dual_scan(fake, p)
    return fake, relaunched, logged, notices


def test_an_i1pro3_found_at_the_start_is_started_again_as_on_master(
        qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    fake, relaunched, logged, notices = _report_fake(tmp_path, IM.I1PRO2)
    TabMeasure._dual_check_reported(fake, "i1Pro3")
    assert len(relaunched) == 1
    p = relaunched[0]
    assert p.extra_args == "-F u -T 0.7", "the row's -F, as without the Beta"
    assert p.engine_dual_args is None
    assert fake._dual_assumed == IM.OTHER
    assert IM.remembered(fake._settings).kind == IM.OTHER
    title = M.M_DUAL_MODEL_CORRECTED.render(reported="i1Pro3", assumed="x")[0]
    assert any(title in ln for ln in logged) and notices
    # the second report of the same device (JSON after the prose): nothing
    TabMeasure._dual_check_reported(fake, "i1Pro3")
    assert len(relaunched) == 1
    # the sentence keeps its place under the chart until a strip is read
    assert TabMeasure._dual_notice_shown(fake) is True
    assert notices[-1] == fake._dual_model_notice
    fake._dual_started = False
    TabMeasure._dual_strip_measured(fake, {"strip": "A"})
    assert TabMeasure._dual_notice_shown(fake) is False


def test_an_i1pro2_found_after_a_start_without_it_is_started_as_dual(
        qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    fake, relaunched, logged, _ = _report_fake(tmp_path, IM.OTHER)
    fake._dual_params.extra_args = "-F u -T 0.7"
    fake._dual_params.engine_dual_args = None
    TabMeasure._dual_check_reported(fake, "i1Pro2")
    assert len(relaunched) == 1
    p = relaunched[0]
    assert "-F" not in p.extra_args
    assert p.engine_dual_args[-2:] == ["--dual-chosen", "M2"]


def test_after_a_reading_it_goes_on_as_started_and_says_so(qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    fake, relaunched, logged, _ = _report_fake(tmp_path, IM.I1PRO2,
                                               relaunch_ok=False)
    TabMeasure._dual_check_reported(fake, "i1Pro3")
    title = M.M_DUAL_MODEL_NOTED.render(reported="i1Pro3", assumed="x")[0]
    assert any(title in ln for ln in logged)


def test_with_the_beta_off_a_report_writes_nothing(qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    s = _S()
    fake, relaunched, logged, _ = _report_fake(tmp_path, IM.I1PRO2,
                                               settings=s)
    TabMeasure._dual_check_reported(fake, "i1Pro3")
    assert dict(s) == {} and relaunched == [] and logged == []


def test_the_manager_starts_again_before_the_first_reading_only(
        qapp, tmp_path, monkeypatch):
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(MeasureManager, "_refuse_system_port",
                        lambda self, *a, **k: False)

    class _Runner:
        def __init__(self):
            self.calls, self.aborted, self.is_running = [], 0, True

        def run(self, tool, args, cwd, on_line=None, on_finish=None,
                use_pty=False):
            self.calls.append((str(tool), list(args), on_finish))

        def abort(self):
            self.aborted += 1

        def set_kill_courtesy(self, line):
            pass

        def write_stdin(self, text):
            pass

    runner = _Runner()
    m = MeasureManager(runner)
    finished = []
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      extra_args="-T 0.7")
    m.start(p, lambda _l: None, finished.append)
    assert "-F" not in runner.calls[-1][1]
    q = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      extra_args="-F u -T 0.7")
    assert m.relaunch_before_reading(q) is True and runner.aborted == 1
    # the dying engine's lines are not read any more
    seen = []
    m._handle_engine_line('{"event":"strip_ready","strip":"A"}', seen.append)
    m._handle_engine_line("some prose", seen.append)
    assert seen == []
    runner.calls[-1][2](1)                   # the first engine ends
    assert len(runner.calls) == 2 and finished == [], "one session"
    args = runner.calls[-1][1]
    assert args[args.index("-F") + 1] == "u"
    # the new one ends: the tab hears that once
    runner.calls[-1][2](0)
    assert finished == [0]
    # once something was read: never
    m.start(p, lambda _l: None, finished.append)
    m._read_something = True
    assert m.relaunch_before_reading(q) is False and runner.aborted == 1


def test_preferences_shows_changes_and_forgets_the_instrument(qapp):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s.set("i1pro3_conditions_beta", True)
    s.set(D.SETTING, True)
    IM.remember_reported(s, "i1Pro2")
    d = SettingsDialog(s)
    try:
        assert d._dual_model_combo.currentData() == "i1pro2"
        assert "i1Pro2" in d._dual_model_note.text()
        assert d._dual_model_combo.isEnabled()
        # unchanged: the report stays as the instrument gave it
        d._save_and_close()
        assert IM.remembered(s).source == "reported"
    finally:
        d.reject()
    d = SettingsDialog(s)
    try:
        d._dual_model_combo.setCurrentIndex(d._dual_model_combo.findData(""))
        d._save_and_close()
        assert IM.remembered(s) == IM.Remembered()
    finally:
        d.reject()
    d = SettingsDialog(s)
    try:
        d._i1pro2_dual_check.setChecked(False)
        assert not d._dual_model_combo.isEnabled(), "follows the switch"
        d._i1pro2_dual_check.setChecked(True)
        d._dual_model_combo.setCurrentIndex(
            d._dual_model_combo.findData("other"))
        d._save_and_close()
        assert IM.remembered(s) == IM.Remembered(IM.OTHER, "", "chosen")
    finally:
        d.reject()
        for k in ("i1pro3_conditions_beta", D.SETTING):
            s.set(k, False)
        IM.forget(s)


def test_the_beta_option_names_the_i1pro2_too(qapp):
    """The owner's decision 1 (2026-11-18): the i1Pro 3 Beta is renamed so
    that its name names the i1Pro 2, whose dual-scan switch sits under it.
    The settings key is unchanged (no migration)."""
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    from workflow import i1pro3_conditions as ic
    s = AppSettings()
    d = SettingsDialog(s)
    try:
        text = d._i1pro3_conditions_check.text()
        assert text.startswith("X-Rite i1Pro 3 and i1Pro 2:")
        assert D.parent_label() in text
    finally:
        d.reject()
    assert ic.SETTING == "i1pro3_conditions_beta"
    # no user-facing text quotes the old name any more
    old = "X-Rite i1Pro 3: keep M0, M1 and M2"
    for path in list((ROOT / "ui").rglob("*.py")) + list(
            (ROOT / "workflow").rglob("*.py")):
        for lit in re.findall(r'tr\(\s*((?:"(?:[^"\\]|\\.)*"\s*)+)',
                              path.read_text(encoding="utf-8")):
            joined = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', lit))
            assert old not in joined, path
    import json
    for f in (ROOT / "data" / "i18n").glob("*.json"):
        keys = json.loads(f.read_text(encoding="utf-8"))
        assert not [k for k in keys if old in k], f.name


# ------------------------------------------- the simulation ends as the real

needs_helper = pytest.mark.skipif(
    not (ROOT / "native" / "chromiq-chartread").exists(),
    reason="engine not built")


@needs_helper
def test_after_m1_m2_ended_the_simulation_keeps_them_and_continue_completes(
        tmp_path, monkeypatch):
    import tests.helpers.replay_tools as rt
    from tests.test_i1pro2_dual_scan_engine import _chart, _dual_args, _vec
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_TILE_S", "0.2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_PASS_S", "0.05")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_M0_SUFFIX", "~M0")
    monkeypatch.setattr(rt, "HELPER",
                        ROOT / "tests" / "helpers" / "dual_sim_helper.py")
    base, rp, truth, _steps = _chart(tmp_path)
    # beside every strip, its lamp pass without a UV pass: the real helper's
    # record of that reading has no UV half, so it loses its conditions
    # record there (cq_cond_lose "dual_uv_pass_missing") and writes no more
    # condition files, as on the instrument after M1 / M2 ended
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
    ends = [e for e in s.events if e.get("event") == "conditions"
            and not e.get("active")]
    assert ends == [{"event": "conditions", "active": False,
                     "why": "dual_dual_needs_ruler", "kept": True}], \
        "one end, as in C"
    main = base.with_suffix(".ti3")
    assert storage.read_dual_record(main).dual
    # 4.3.49 (Basti, 2026-11-19): A keeps its M1 / M2, B has M0 only
    from workflow import i1pro3_conditions as ic
    assert not D.ended_before(main)
    assert D.m0_only_strips(main) == ["B"]
    assert ic.strips_of(ic._locs_of(ic.partial_sibling_path(main, "M1"))) == ["A"]

    def again(s):                      # Continue: B again, both passes
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="goto", strip="B")
        s.wait_event("strip_ready", after=i, strip="B")
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("done", timeout=10, after=i)
        s.finish()

    with rt.ReplaySession(base, rp, extra_args=["-r"] + args) as s2:
        again(s2)
    cond = [e for e in s2.events if e.get("event") == "conditions"]
    assert cond and cond[0].get("active") is True and cond[0].get("partial")
    assert D.m0_only_strips(main) == []
    assert ic.condition_file(main, "M2") is not None
