"""Feature A on the Print Chart tab (#130) — tests T1–T13 of
docs/design/verification_printing_and_target.md §9.

T3 (intent letters) and the failure rows A10–A12 are pinned at engine level in
test_verification_print.py; here the tab itself is driven: row visibility per
run type (T1), the cache destination (T2), both print buttons converting (T4),
the §M failure windows (T5/T6), the colour-management locks (T7), the report
block (T8), old projects opening unchanged (T9), the §3.1a force-Raw lock
(T11), the deliberate §3.1b asymmetry (T12) and the Check & Refine guard (T13).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox     # noqa: E402

from core.file_manager import FileManager, Project, RunMeta        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import verification_print as vp             # noqa: E402
from workflow import measurement_messages as M            # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    # The lp path is the deterministic one for tests; the native dialog would
    # open a real window (and its failure path a real modal) offscreen.
    s.set("use_native_print_dialog", False)
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    return s, fm, MeasurementTargetController(fm)


def _verify_env(tmp_path, *, with_profile: bool = True, n_pages: int = 2):
    """A project whose run1 has a verify chart with pages, and (optionally) a
    built profile — the §3.1 A3 row."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.verify_chart_ti2
    ti2.write_text("CTI2\n")
    pages = []
    for i in range(1, n_pages + 1):
        p = run.verifications_dir / f"{run.verify_stem}_{i:02d}.tif"
        p.write_bytes(b"II*\x00")
        pages.append((p, 0))
    if with_profile:
        run.profile_icc.write_bytes(b"icc")
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    return s, fm, ctl, run, ti2, pages


def _tab(s, ctl, ti2, pages):
    from ui.tabs.tab_print import TabPrint
    tab = TabPrint(s)
    tab.set_target_controller(ctl)
    tab._current_ti2 = ti2
    tab.load_tiffs([p for p, _f in pages])
    tab._preview._pages = list(pages)
    tab._preview._current = 0
    return tab


def _fake_converter(calls: list):
    def fake(pages, profile, intent, out_dir, **kw):
        calls.append({"pages": list(pages), "profile": Path(profile),
                      "intent": intent, "out_dir": Path(out_dir)})
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        mapping = {}
        for p in pages:
            dst = out / p.name
            dst.write_bytes(b"converted")
            mapping[p] = dst
        return mapping
    return fake


# ------------------------------------------------------------------- T1
def test_rows_appear_for_exactly_the_table_31_rows(qapp, tmp_path):
    """Colour + intent only for a verification; Route for every chart; the
    whole section hidden with no pages (A6)."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)
    assert tab._cm_grp.isVisibleTo(tab)
    assert tab._cm_colour_row.isVisibleTo(tab._cm_grp)
    assert tab._cm_intent_row.isVisibleTo(tab._cm_grp)
    assert tab._cm_route_row.isVisibleTo(tab._cm_grp)

    ctl.set_run_type(RUN_TYPE_PROFILING)                        # A1
    assert tab._cm_grp.isVisibleTo(tab)
    assert not tab._cm_colour_row.isVisibleTo(tab._cm_grp)
    assert not tab._cm_intent_row.isVisibleTo(tab._cm_grp)
    assert tab._cm_route_row.isVisibleTo(tab._cm_grp)

    ctl.set_calibration_allowed(True)                           # A2
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert not tab._cm_colour_row.isVisibleTo(tab._cm_grp)

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab.load_tiffs([])                                          # A6
    assert not tab._cm_grp.isVisibleTo(tab)


def test_no_profile_disables_through_and_keeps_raw(qapp, tmp_path):
    """§3.1 A4 — "through" disabled, raw selected, S7 notice shown."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path, with_profile=False)
    tab = _tab(s, ctl, ti2, pages)
    assert not tab._cm_through_rb.isEnabled()
    assert tab._cm_raw_rb.isChecked()
    assert not tab._cm_intent_combo.isEnabled()
    assert "no finished profile" in tab._cm_notice.text()
    assert tab._cm_selected_colour() == vp.COLOUR_RAW


# --------------------------------------------------------------- T2 + T4
def test_both_print_buttons_convert_and_cache_gets_the_sheets(
        qapp, tmp_path, monkeypatch):
    """T4 — the A2.2 risk: BOTH buttons funnel through the conversion.
    T2 — converted sheets land in the chart's cache/, never the run root."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)
    calls: list = []
    monkeypatch.setattr(
        "workflow.verification_print.convert_pages_through_profile",
        _fake_converter(calls))
    sent: list = []
    monkeypatch.setattr(tab, "_print_pages",
                        lambda pages: sent.append(("lp", list(pages))))
    monkeypatch.setattr(tab, "_print_native",
                        lambda pages: sent.append(("native", list(pages))))

    tab._on_print_current()
    tab._on_print_all()
    assert len(calls) == 2 and len(sent) == 2
    # T2: the destination is the chart folder's cache/, and the pages the
    # print path receives are the converted ones.
    cache = run.verifications_dir / "cache"
    assert calls[0]["out_dir"] == cache
    assert calls[0]["profile"] == run.profile_icc
    for _route, got in sent:
        for p, _f in got:
            assert p.parent == cache
            assert p.exists()
    assert not list(run.dir.glob("cache/*"))     # never the run root's cache

    # The native path converts too (the second half of T4).
    s.set("use_native_print_dialog", True)
    tab._on_print_current()
    assert sent[-1][0] == "native"
    assert sent[-1][1][0][0].parent == cache


def test_the_chosen_intent_reaches_the_converter_and_the_record(
        qapp, tmp_path, monkeypatch):
    """T3 at tab level, and A15–A18: the record beside the chart says how the
    sheet was produced."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)
    calls: list = []
    monkeypatch.setattr(
        "workflow.verification_print.convert_pages_through_profile",
        _fake_converter(calls))
    monkeypatch.setattr(tab, "_print_pages", lambda pages: None)
    idx = tab._cm_intent_combo.findData("absolute")
    tab._cm_intent_combo.setCurrentIndex(idx)

    tab._on_print_current()
    assert calls[0]["intent"] == "absolute"
    rec = json.loads(vp.print_record_path(ti2).read_text())
    assert rec["colour"] == vp.COLOUR_THROUGH
    assert rec["intent"] == "absolute"
    assert rec["route"] == vp.ROUTE_CHROMIQ
    assert rec["profile"] == run.profile_icc.name
    assert rec["profile_mtime"]


def test_raw_choice_is_recorded_and_prints_unconverted(
        qapp, tmp_path, monkeypatch):
    """§3.1 A5 — raw stays a legitimate choice, and the record says so."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)
    monkeypatch.setattr(
        "workflow.verification_print.convert_pages_through_profile",
        lambda *a, **k: pytest.fail("raw must not convert"))
    sent: list = []
    monkeypatch.setattr(tab, "_print_pages",
                        lambda pages: sent.append(list(pages)))
    # Windows forces use_native_print_dialog True (no lp), so _on_print_current
    # dispatches through _print_native there; capture both so the assertion
    # holds on whichever path the platform takes.
    monkeypatch.setattr(tab, "_print_native",
                        lambda pages: sent.append(list(pages)))
    tab._cm_raw_rb.setChecked(True)

    tab._on_print_current()
    assert sent and sent[0][0][0] == pages[0][0]      # untouched pages
    rec = json.loads(vp.print_record_path(ti2).read_text())
    assert rec["colour"] == vp.COLOUR_RAW
    assert rec["intent"] == ""


def test_external_route_hands_over_files_and_prints_nothing(
        qapp, tmp_path, monkeypatch):
    """§4 — Route = another application: convert, reveal, print nothing."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)
    monkeypatch.setattr(
        "workflow.verification_print.convert_pages_through_profile",
        _fake_converter([]))
    revealed: list = []
    monkeypatch.setattr("core.preset_store.reveal_in_file_manager",
                        lambda p: revealed.append(Path(p)))
    monkeypatch.setattr(tab, "_print_pages",
                        lambda pages: pytest.fail("external route must not print"))
    monkeypatch.setattr(tab, "_print_native",
                        lambda pages: pytest.fail("external route must not print"))
    tab._cm_route_ext_rb.setChecked(True)

    tab._on_print_all()
    assert revealed == [run.verifications_dir / "cache"]
    rec = json.loads(vp.print_record_path(ti2).read_text())
    assert rec["route"] == vp.ROUTE_EXTERNAL


# --------------------------------------------------------------- T5 + T6
def test_missing_cctiff_shows_s9_and_prints_nothing(qapp, tmp_path, monkeypatch):
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    s.set("argyll_bin_path", str(tmp_path / "no-argyll-here"))
    tab = _tab(s, ctl, ti2, pages)
    shown: list = []
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(
        lambda parent, title, body, *a, **k: shown.append((title, body))))
    monkeypatch.setattr(tab, "_print_pages",
                        lambda pages: pytest.fail("a failed conversion must print nothing"))

    tab._on_print_current()
    assert shown and shown[0][0] == M.M_CM_NO_CCTIFF.title


def test_a_failed_page_shows_s10_names_the_page_and_prints_nothing(
        qapp, tmp_path, monkeypatch):
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)

    def boom(*a, **k):
        raise vp.VerificationPrintError("M-CM-CONVERT-FAILED",
                                        "cctiff: broken", page=2, total=3)
    monkeypatch.setattr(
        "workflow.verification_print.convert_pages_through_profile", boom)
    shown: list = []
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(
        lambda parent, title, body, *a, **k: shown.append((title, body))))
    monkeypatch.setattr(tab, "_print_pages",
                        lambda pages: pytest.fail("a failed conversion must print nothing"))

    tab._on_print_all()
    assert shown and shown[0][0] == M.M_CM_CONVERT_FAILED.title
    assert "page 2 of 3" in shown[0][1]
    assert "cctiff: broken" in shown[0][1]


# ------------------------------------------------------------------- T7
def test_the_colour_management_locks_still_guard_both_print_paths():
    """Regression pin for A14: the conversion feeds INTO the existing raw
    paths — it must not have grown a third way to a printer."""
    import inspect
    from ui.tabs.tab_print import TabPrint
    send = inspect.getsource(TabPrint._send_page)
    assert "print_job_ps" in send            # the CUPS raw path, CM forced off
    native = inspect.getsource(TabPrint._print_native)
    assert "native_print_macos" in native    # the locked native path
    preflight = inspect.getsource(TabPrint._show_preflight)
    assert "Colour management" in preflight and "Off (forced)" in preflight
    funnel = inspect.getsource(TabPrint._apply_verification_colour)
    for forbidden in ("print_job_ps", "lp ", "subprocess"):
        assert forbidden not in funnel


# ------------------------------------------------------------------- T8
_TI2_TEXT = """CTI1

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100 100 100 96.42 100.0 82.53
2 "A2" 0 0 0 0.96 1.0 0.83
3 "A3" 100 0 0 41.0 21.0 2.0
END_DATA
"""

_TI3_TEXT = _TI2_TEXT.replace("CTI1", "CTI3").replace(
    "41.0 21.0 2.0", "36.0 18.0 3.0")


def test_report_carries_the_printing_block_when_a_record_exists(tmp_path):
    from workflow.measurement_report import build_report
    (tmp_path / "c.ti2").write_text(_TI2_TEXT)
    (tmp_path / "c.ti3").write_text(_TI3_TEXT)
    profile = tmp_path / "c.icc"
    profile.write_bytes(b"icc")
    vp.write_print_record(tmp_path / "c.ti2", colour=vp.COLOUR_THROUGH,
                          intent="relative", profile=profile,
                          route=vp.ROUTE_CHROMIQ)
    r = build_report(tmp_path / "c.ti3")
    p = r["printing"]
    assert p["colour"] == vp.COLOUR_THROUGH
    assert p["intent"] == "relative"
    assert p["route"] == vp.ROUTE_CHROMIQ
    assert p["profile_changed_since_print"] is False

    # A17: rebuild the profile after printing → the report flags it.
    os.utime(profile, (0, 0))
    assert build_report(tmp_path / "c.ti3")["printing"][
        "profile_changed_since_print"] is True


def test_report_has_no_printing_block_without_a_record(tmp_path):
    from workflow.measurement_report import build_report
    (tmp_path / "c.ti2").write_text(_TI2_TEXT)
    (tmp_path / "c.ti3").write_text(_TI3_TEXT)
    assert "printing" not in build_report(tmp_path / "c.ti3")


def test_dialog_block_names_the_question_each_way(qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    block = MeasurementReportDialog._printing_block_html
    through = block(object(), {
        "is_verification": True,
        "printing": {"colour": "through-profile", "intent": "relative",
                     "route": "chromiq", "profile": "P.icc",
                     "printed_at": "2026-08-09T10:00:00"}})
    assert "how accurate this profile is" in through
    assert "relative colorimetric" in through
    raw = block(object(), {"is_verification": True,
                           "printing": {"colour": "raw", "route": "external"}})
    assert "whether this printer has changed" in raw
    unrecorded = block(object(), {"is_verification": True})
    assert "not recorded" in unrecorded
    # A profiling run with no record has nothing to account for.
    assert block(object(), {"is_verification": False}) == ""


def test_scope_warns_when_verifications_mix_printing_methods():
    """Phase A3: the report marks where the method changed (Q3)."""
    from workflow.measurement_report import report_scope
    runs = [
        {"chart": "P", "created": "2026-07-01T10:00:00",
         "is_verification": True},                       # pre-A → unrecorded
        {"chart": "P", "created": "2026-08-09T10:00:00",
         "is_verification": True,
         "printing": {"colour": "through-profile"}},
    ]
    warnings = report_scope(runs)["warnings"]
    printing = [w for w in warnings if w["kind"] == "printing"]
    assert printing and len(printing[0]["runs"]) == 2
    methods = {o["method"] for o in printing[0]["runs"]}
    assert methods == {"unrecorded", "through-profile"}

    # Uniform methods stay quiet.
    uniform = [dict(r, printing={"colour": "raw"}) for r in runs]
    assert not [w for w in report_scope(uniform)["warnings"]
                if w["kind"] == "printing"]


def test_trend_points_carry_the_printing_method():
    from workflow.measurement_report import report_trend
    series = report_trend([
        {"created": "2026-08-09", "chart": "P",
         "de00": {"mean": 1.0, "max": 2.0},
         "printing": {"colour": "raw"}}])
    assert series[0]["printing_colour"] == "raw"


# ------------------------------------------------------------------- T9
def test_an_existing_project_opens_unchanged(qapp, tmp_path):
    """Old meta.json (no print_settings) loads; nothing stored → defaults."""
    meta = RunMeta.from_dict({"run_id": "run1", "instrument": "i1"})
    assert meta.print_settings == {}

    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)
    assert tab.load_target_settings() is False       # nothing stored
    assert tab._cm_intent_combo.currentData() == "relative"
    assert tab._cm_route_here_rb.isChecked()
    # No verification history → the honest default, through the profile (Q3).
    assert tab._cm_through_rb.isChecked()


def test_q3_default_follows_the_runs_history():
    """§5 A3.1 — the highest-risk decision in A, pinned at engine level."""
    class _Run:
        def __init__(self, tmp, hist):
            self._hist = hist
            self.verify_chart_ti2 = tmp / "P-verify.ti2"

        def verifications(self):
            return self._hist

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # A fresh run: ON (through) from the start.
        assert vp.default_colour_for_run(_Run(tmp, [])) == vp.COLOUR_THROUGH
        # History from before feature A (no record): the method stays raw, so
        # the existing trend keeps its meaning.
        assert vp.default_colour_for_run(_Run(tmp, ["v1"])) == vp.COLOUR_RAW
        # History made through the profile keeps that method.
        (tmp / "P-verify.ti2").write_text("CTI2\n")
        vp.write_print_record(tmp / "P-verify.ti2", colour=vp.COLOUR_THROUGH,
                              intent="relative", profile=None,
                              route=vp.ROUTE_CHROMIQ)
        assert vp.default_colour_for_run(_Run(tmp, ["v1"])) == vp.COLOUR_THROUGH


def test_print_settings_roundtrip_through_the_target_store(qapp, tmp_path):
    """§11 Q5 — the Print tab is a storing tab now: choices survive a reload,
    and a forced state never overwrites the user's stored Colour."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)
    tab._cm_raw_rb.setChecked(True)                      # a user choice
    idx = tab._cm_intent_combo.findData("perceptual")
    tab._cm_intent_combo.setCurrentIndex(idx)
    assert tab.save_target_settings(store=run) is True
    stored = run.load_meta().print_settings
    assert stored == {"colour": vp.COLOUR_RAW, "intent": "perceptual",
                      "route": vp.ROUTE_CHROMIQ}

    tab2 = _tab(s, ctl, ti2, pages)
    assert tab2.load_target_settings() is True
    assert tab2._cm_raw_rb.isChecked()
    assert tab2._cm_intent_combo.currentData() == "perceptual"

    # Remove the profile → forced raw (A4). Saving in that state must not
    # overwrite the stored Colour with the forced one.
    run.profile_icc.unlink()
    tab2._cm_user_colour = None                          # no user click
    tab2._update_colour_row_visible()
    tab2._print_written.clear()
    tab2.save_target_settings(store=run)
    assert run.load_meta().print_settings["colour"] == vp.COLOUR_RAW


# ------------------------------------------------------------------ T11
def test_a_colorimetric_chart_forces_raw_and_stays_forced(qapp, tmp_path):
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    vp.colorimetric_reference_for(ti2).write_text("CTI3\n")
    tab = _tab(s, ctl, ti2, pages)
    assert not tab._cm_through_rb.isEnabled()
    assert tab._cm_raw_rb.isChecked()
    assert not tab._cm_intent_combo.isEnabled()
    assert "already has your profile applied" in tab._cm_notice.text()
    assert tab._cm_selected_colour() == vp.COLOUR_RAW

    # T11's second half: toggling the run type back and forth cannot
    # re-enable the option.
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert not tab._cm_through_rb.isEnabled()
    assert tab._cm_selected_colour() == vp.COLOUR_RAW


def test_a_claimed_reference_that_is_missing_also_forces_raw(qapp, tmp_path):
    """A3c — refusing to convert is the safe direction, and the notice says
    what could not be established."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    run.verify_chart_channels_json.write_text(json.dumps(
        {"ink_channels": ["r", "g", "b"],
         "colorimetric_reference": "P-verify-reference.ti3"}))
    tab = _tab(s, ctl, ti2, pages)
    assert not tab._cm_through_rb.isEnabled()
    assert "reference file beside it is missing" in tab._cm_notice.text()


# ------------------------------------------------------------------ T12
def test_a_regular_chart_offers_both_and_the_notice_follows(qapp, tmp_path):
    """§3.1b — deliberately NOT symmetric with T11: nothing is disabled, and
    the notice names the question each choice answers."""
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    tab = _tab(s, ctl, ti2, pages)
    assert tab._cm_through_rb.isEnabled() and tab._cm_raw_rb.isEnabled()
    assert tab._cm_through_rb.isChecked()
    assert "profile" in tab._cm_notice.text()
    assert tab._cm_intent_combo.isEnabled()

    tab._cm_raw_rb.setChecked(True)
    assert "measures your printer, not your profile" in tab._cm_notice.text()
    assert not tab._cm_intent_combo.isEnabled()

    tab._cm_through_rb.setChecked(True)
    assert "prediction made real" in tab._cm_notice.text()
    assert tab._cm_intent_combo.isEnabled()


# ------------------------------------------------------------------ T13
def test_check_refine_warns_on_a_print_time_converted_measurement(
        qapp, tmp_path, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_check_refine import TabCheckRefine
    s, fm, ctl = _env(tmp_path)
    tab = TabCheckRefine(ArgyllRunner(s), s, None)
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\n")
    ti3 = tmp_path / "c.ti3"
    ti3.write_text(_TI3_TEXT)
    icc = tmp_path / "c.icc"
    icc.write_bytes(b"icc")
    tab._ti3_path = ti3
    tab._icc_path = icc

    execs: list = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self, *a, **k: execs.append(self) or 0)

    # A raw print (or no record) runs without a window.
    assert tab._warn_converted_measurement() is True
    vp.write_print_record(ti2, colour=vp.COLOUR_RAW, intent="",
                          profile=None, route=vp.ROUTE_CHROMIQ)
    assert tab._warn_converted_measurement() is True
    assert not execs

    # A print-time-converted sheet raises the §2b window, and with nothing
    # clicked (Cancel is the default) the check does not run.
    vp.write_print_record(ti2, colour=vp.COLOUR_THROUGH, intent="relative",
                          profile=icc, route=vp.ROUTE_CHROMIQ)
    assert tab._warn_converted_measurement() is False
    assert len(execs) == 1

    ran: list = []
    monkeypatch.setattr(tab._checker, "run",
                        lambda *a, **k: ran.append(1))
    tab._on_run()
    assert not ran, "the check must not start under the §2b warning"


def test_a_generated_gamut_chart_forces_raw_without_help(qapp, tmp_path):
    """Regression (Basti, 2026-08-10): generating a chart handed this tab only
    the page images, so a FROM PROFILE GAMUT chart — already converted — still
    offered "Through the profile" and defaulted to it. note_generated_chart is
    the missing link main_window now calls with the .ti2."""
    from workflow import verification_print as vp
    from workflow.gamut_target import (GamutSelection,
                                       write_colorimetric_reference)
    s, fm, ctl, run, ti2, pages = _verify_env(tmp_path)
    sel = GamutSelection(master_version="TEST-r0", master_total=10,
                         in_gamut_total=1, requested=1,
                         intent="absolute", margin="safe")
    sel.targets = [(0, (50.0, 0.0, 0.0), (10.0, 20.0, 30.0))]
    write_colorimetric_reference(sel, vp.colorimetric_reference_for(ti2))

    from ui.tabs.tab_print import TabPrint
    tab = TabPrint(s)
    tab.set_target_controller(ctl)
    # Exactly what main_window's generation handler used to do: pages only.
    tab.load_tiffs([p for p, _f in pages])
    # …and what it does now:
    tab.note_generated_chart(ti2)
    assert tab._cm_raw_rb.isChecked()
    assert not tab._cm_through_rb.isEnabled()
    assert tab._cm_selected_colour() == vp.COLOUR_RAW

    # A later regular (targen) chart replacing it frees the row again.
    vp.colorimetric_reference_for(ti2).unlink()
    tab.note_generated_chart(ti2)
    assert tab._cm_through_rb.isEnabled()

    # And a cleared chart (no-chart guidance state) drops the context.
    tab.note_generated_chart(None)
    assert tab._current_ti2 is None
