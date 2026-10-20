"""4.3.8: a verification chart goes to a PostScript printer the way its
profiling chart went (Knut's run 6, 2026-10-19).

Knut's run 6 verification (a FROM PROFILE GAMUT chart, printed raw on
2026-10-14 with 4.3.5 beta 5) measured mean dE00 8.7 against its profile,
pure green dE76 39 from the same RGB on the profiling sheet. The profiling
chart had been printed on 2026-10-01 through the macOS print dialog (4.3.2),
where macOS marked the chart as sRGB or with the queue's ColorSync profile and
his HP Color LaserJet 5550 converted it; the verification chart went by
ChromIQ's direct route as the printer's own RGB. Against a profile his printer
made from a direct-route sheet (2026-10-10) the same sheet measures mean dE00
2.0: the printer was fine, the two sheets went two different ways, and
nothing in ChromIQ could tell, because a print record said only
``route: chromiq`` for both.

So (report folder 2026-10-19_knut_highverif):

* every print record says which way the sheet went (``path``: dialog or
  direct), to which queue, and on a PostScript printer the form its colours
  reached it in (``postscript``), and which ChromIQ wrote it;
* a verification chart takes the form its run's profiling chart was recorded
  printed in, after the run's own row choice and before the parent's and the
  project's, so the dialog sends that form and the direct route asks
  M-PRINT-DIRECT-LIKE-PREVIEW where it cannot;
* a profiling chart printed by 4.3.4 or earlier, whose record cannot say,
  gets the approved M-PRINT-VERIFY-PS-EARLIER as a window before a
  verification chart goes by the direct route to a PostScript printer
  (Cancel the default; "Print anyway").
"""
from __future__ import annotations

import inspect
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox     # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import measurement_messages as MM           # noqa: E402
from workflow import native_print_macos as npm            # noqa: E402
from workflow import ppd_color                            # noqa: E402
from workflow import verification_print as vp             # noqa: E402

DEVICE, MACOS = ppd_color.POSTSCRIPT_DEVICE_RGB, ppd_color.POSTSCRIPT_AS_MACOS

#: Knut's run 2 profiling chart's record, as it is on his disk
KNUTS_PROFILING_RECORD = {"printed_at": "2026-10-01T17:25:00", "colour": "raw",
                          "intent": "", "route": "chromiq", "source_profile": ""}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def mac(monkeypatch):
    from ui.tabs import tab_print as tp
    monkeypatch.setattr(tp, "is_macos", lambda: True)
    monkeypatch.setattr("sys.platform", "darwin")
    return tp


@pytest.fixture
def ps_queue(monkeypatch, tmp_path):
    ppd = tmp_path / "q.ppd"
    ppd.write_text('*PPD-Adobe: "4.3"\n', encoding="utf-8")   # no filter: PostScript
    monkeypatch.setattr(ppd_color, "ppd_path_for_queue", lambda q: str(ppd))
    return ppd


def _env(tmp_path, run_type=RUN_TYPE_VERIFICATION, dialog=False):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("use_native_print_dialog", dialog)
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(run_type)
    return s, fm, ctl


def _profiling_record(fm, rec):
    run = fm.project().run("run1")
    path = vp.print_record_path(run.chart_ti2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec), encoding="utf-8")
    return run


def _tab(s, ctl):
    from ui.tabs.tab_print import TabPrint
    tab = TabPrint(s)
    tab.set_target_controller(ctl)
    return tab


# ---- the record ---------------------------------------------------------------
def test_a_print_record_says_which_way_the_sheet_went(tmp_path):
    ti2 = tmp_path / "c.ti2"
    vp.write_print_record(ti2, colour="raw", intent="", profile=None,
                          route=vp.ROUTE_CHROMIQ, path=vp.PATH_DIRECT,
                          printer="HP_CLJ5550", postscript=DEVICE)
    rec = json.loads(vp.print_record_path(ti2).read_text(encoding="utf-8"))
    assert (rec["path"], rec["printer"], rec["postscript"]) == ("direct", "HP_CLJ5550", DEVICE)
    from core.version import APP_VERSION
    assert rec["app_version"] == APP_VERSION
    assert vp.recorded_postscript_form(rec) == DEVICE
    assert not vp.record_may_be_from_the_old_dialog(rec)


def test_a_record_that_does_not_say_keeps_its_old_shape(tmp_path):
    ti2 = tmp_path / "c.ti2"
    vp.write_print_record(ti2, colour="raw", intent="", profile=None, route=vp.ROUTE_CHROMIQ)
    rec = json.loads(vp.print_record_path(ti2).read_text(encoding="utf-8"))
    assert "path" not in rec and "postscript" not in rec and "printer" not in rec
    assert vp.recorded_postscript_form(rec) == ""


@pytest.mark.parametrize("rec, old", [
    (KNUTS_PROFILING_RECORD, True),
    ({**KNUTS_PROFILING_RECORD, "printed_at": "2026-10-11T04:41:59"}, True),
    ({**KNUTS_PROFILING_RECORD, "printed_at": "2026-10-11T04:42:00"}, False),
    ({**KNUTS_PROFILING_RECORD, "path": "dialog"}, False),
    ({**KNUTS_PROFILING_RECORD, "route": "external"}, False),
    ({**KNUTS_PROFILING_RECORD, "printed_at": ""}, False),
    (None, False), ({}, False),
])
def test_only_a_record_older_than_4_3_5_that_does_not_say_may_be_from_the_old_dialog(rec, old):
    assert vp.record_may_be_from_the_old_dialog(rec) is old


def _icc_dated(path, y, mo, d, h=12, mi=0):
    """A file with an ICC header dated (UTC) as given; nothing else in it."""
    import struct
    head = bytearray(128)
    head[24:36] = struct.pack(">6H", y, mo, d, h, mi, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(head))
    return path


def test_with_no_record_the_profiles_date_decides(tmp_path):
    """Knut's run 6 is a duplicated run: its profiling chart's record did not
    come along, and its profile (test.icc) is dated 2026-10-02 22:39 UTC."""
    old = _icc_dated(tmp_path / "old.icc", 2026, 10, 2, 22, 39)
    new = _icc_dated(tmp_path / "new.icc", 2026, 10, 11, 2, 42)
    assert vp.icc_created_utc(old) == "2026-10-02T22:39:00"
    assert vp.profiling_chart_may_be_from_the_old_dialog(None, old) is True
    assert vp.profiling_chart_may_be_from_the_old_dialog(None, new) is False
    assert vp.profiling_chart_may_be_from_the_old_dialog(None, tmp_path / "none.icc") is False
    assert vp.profiling_chart_may_be_from_the_old_dialog(None, None) is False
    # a record decides on its own, whatever the profile's date
    assert vp.profiling_chart_may_be_from_the_old_dialog(
        {**KNUTS_PROFILING_RECORD, "path": "direct"}, old) is False


# ---- the form a verification chart takes ---------------------------------------
def test_a_verification_chart_takes_the_form_its_profiling_chart_went_in(
        qapp, tmp_path, mac, ps_queue):
    """MUTATION: drop the record from ``_ps_form_stored`` and the project's
    "unchanged colours" sends a chart whose profiling chart the printer
    adjusted as the printer's own RGB."""
    s, fm, ctl = _env(tmp_path)
    fm.project().set_print_setting("postscript", DEVICE)
    _profiling_record(fm, {**KNUTS_PROFILING_RECORD, "printed_at": "2026-10-20T10:00:00",
                           "path": "dialog", "postscript": MACOS})
    tab = _tab(s, ctl)
    assert tab._ps_form_stored() == MACOS
    # so the direct route asks before it sends the printer's own RGB
    assert tab._direct_print_needs_like_preview_question("Q") is True
    # the profiling chart itself still follows the project
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert tab._ps_form_stored() == DEVICE


def test_the_runs_own_row_choice_still_wins(qapp, tmp_path, mac, ps_queue):
    s, fm, ctl = _env(tmp_path)
    run = _profiling_record(fm, {**KNUTS_PROFILING_RECORD, "printed_at": "2026-10-20T10:00:00",
                                 "path": "direct", "postscript": DEVICE})
    meta = run.load_meta()
    meta.print_settings = {**(meta.print_settings or {}), "postscript": MACOS}
    run.save_meta(meta)
    assert _tab(s, ctl)._ps_form_stored() == MACOS


def test_a_record_that_does_not_say_changes_nothing(qapp, tmp_path, mac, ps_queue):
    s, fm, ctl = _env(tmp_path)
    fm.project().set_print_setting("postscript", DEVICE)
    _profiling_record(fm, KNUTS_PROFILING_RECORD)
    assert _tab(s, ctl)._ps_form_stored() == DEVICE


# ---- Knut's case: a profiling chart from 4.3.4 or earlier ----------------------
def _answer(monkeypatch, tp, button_text):
    seen = []

    def clicked(box):
        seen.append((box.text(), box.informativeText(), [b.text() for b in box.buttons()],
                     box.defaultButton().text() if box.defaultButton() else None))
        if button_text == "cancel":
            return box.button(QMessageBox.StandardButton.Cancel)
        return next(b for b in box.buttons() if b.text() == button_text)
    monkeypatch.setattr(tp.QMessageBox, "exec", lambda box: 0)
    monkeypatch.setattr(tp.QMessageBox, "clickedButton", clicked)
    return seen


def test_knuts_run_is_warned_before_the_direct_route_sends_his_verification_chart(
        qapp, tmp_path, mac, ps_queue, monkeypatch):
    """MUTATION: remove the window and Knut's run 6 sheet is printed again
    the other way, unsaid."""
    s, fm, ctl = _env(tmp_path)
    _profiling_record(fm, KNUTS_PROFILING_RECORD)
    tab = _tab(s, ctl)
    assert tab._verify_after_an_old_dialog_profile("HP") is True
    seen = _answer(monkeypatch, mac, "cancel")
    assert tab._ask_verify_after_an_old_dialog_profile("HP") == ""
    # Basti, 2026-10-20: the window has its own wording, covering both ways
    # the profiling chart may have gone (ChromIQ cannot tell them apart);
    # the tab's note keeps the approved M-PRINT-VERIFY-PS-EARLIER
    title, body = MM.M_PRINT_VERIFY_PS_EARLIER_ASK.render()
    assert seen[0][0] == title and seen[0][1] == body
    assert "4.3.4" in body and "Print anyway" in body and "Use the print dialog" in body
    assert sorted(seen[0][2]) == ["Cancel", "Print anyway", "Use the print dialog"]
    assert seen[0][3] == "Cancel", "nothing is sent unless the user says so"
    _answer(monkeypatch, mac, "Print anyway")
    assert tab._ask_verify_after_an_old_dialog_profile("HP") == "anyway"
    _answer(monkeypatch, mac, "Use the print dialog")
    assert tab._ask_verify_after_an_old_dialog_profile("HP") == "dialog"


def test_use_the_print_dialog_sends_it_like_preview(qapp, tmp_path, mac, ps_queue,
                                                     monkeypatch):
    """(c) of Basti's decision: through the macOS print dialog, letting the
    printer adjust the colours, the way the old profiling chart went; for this
    print only, nothing stored."""
    from workflow import native_print_macos as npm
    s, fm, ctl = _env(tmp_path)
    _profiling_record(fm, KNUTS_PROFILING_RECORD)
    tab = _tab(s, ctl)
    got = []
    monkeypatch.setattr(tab, "_print_native",
                        lambda pages, printer=None: got.append(
                            (printer, tab._ps_form_for_dialog())))
    monkeypatch.setattr(tab, "_ask_verify_after_an_old_dialog_profile",
                        lambda printer: "dialog")
    monkeypatch.setattr(tab, "_ask_direct_like_preview", lambda printer: None)
    monkeypatch.setattr(tab, "_unknown_paper_profile", lambda *a: None)
    monkeypatch.setattr(tab._printer, "is_printer_reachable", lambda q: True)
    monkeypatch.setattr(tab, "_handle_stuck_jobs", lambda q: True)
    monkeypatch.setattr(tab, "_compute_geometry", lambda *a: ("portrait", (595.0, 842.0), None))
    tab._printer_combo.addItem("HP", "HP")
    tab._printer_combo.setCurrentIndex(0)
    tab._print_pages([(tmp_path / "p.tif", 0)])
    assert got == [("HP", MACOS)]
    assert tab._ps_form_for_dialog() != MACOS or tab._ps_form_stored() == MACOS


def test_the_warning_is_not_shown_where_it_does_not_apply(
        qapp, tmp_path, mac, ps_queue, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    run = _profiling_record(fm, KNUTS_PROFILING_RECORD)
    tab = _tab(s, ctl)
    # a printer that is not PostScript
    ps_queue.write_text('*cupsFilter: "application/vnd.cups-raster 0 rastertoqq"\n',
                        encoding="utf-8")
    assert tab._verify_after_an_old_dialog_profile("Q") is False
    ps_queue.write_text('*PPD-Adobe: "4.3"\n', encoding="utf-8")
    # the profiling chart itself
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert tab._verify_after_an_old_dialog_profile("Q") is False
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    # a record that says which way it went, and no record at all
    vp.print_record_path(run.chart_ti2).write_text(json.dumps(
        {**KNUTS_PROFILING_RECORD, "path": "direct", "postscript": DEVICE}), encoding="utf-8")
    assert tab._verify_after_an_old_dialog_profile("Q") is False
    vp.print_record_path(run.chart_ti2).unlink()
    assert tab._verify_after_an_old_dialog_profile("Q") is False, "no record, no profile"
    # no record, and a profile made before 4.3.5: Knut's duplicated run 6
    _icc_dated(run.built_profile_icc(), 2026, 10, 2, 22, 39)
    assert tab._verify_after_an_old_dialog_profile("Q") is True
    _icc_dated(run.built_profile_icc(), 2026, 10, 18, 9, 0)
    assert tab._verify_after_an_old_dialog_profile("Q") is False
    # nothing is asked, and True goes on printing
    asked = []
    monkeypatch.setattr(mac.QMessageBox, "exec", lambda box: asked.append(1) or 0)
    assert tab._ask_verify_after_an_old_dialog_profile("Q") is None
    assert asked == []


def test_the_direct_route_asks_and_notes_the_way_before_it_sends_anything():
    from ui.tabs import tab_print as tp
    src = inspect.getsource(tp.TabPrint._print_pages)
    asked = src.index("self._ask_verify_after_an_old_dialog_profile(printer)")
    noted = src.index("self._note_print_path(")
    assert src.index("self._ask_direct_like_preview(printer)") < asked
    assert asked < src.index("self._show_preflight(") < noted < src.index("self._send_page(")
    assert "_vp.PATH_DIRECT" in src[noted:noted + 200]


# ---- what the routes write ------------------------------------------------------
def test_the_dialog_route_records_the_form_the_job_went_in(qapp, tmp_path, mac, monkeypatch):
    s, fm, ctl = _env(tmp_path, dialog=True)
    tab = _tab(s, ctl)
    ti2 = tmp_path / "v.ti2"
    tab._pending_print_record = (ti2, dict(colour="raw", intent="", profile=None,
                                           route=vp.ROUTE_CHROMIQ))

    def fake(pages, printer=None, postscript_form=None, refuse_unlisted_paper=None,
             ask_postscript_form=None, **kw):
        sub = npm.Submission("HP Color LaserJet 5550", {}, 0.0, b"", None)
        sub.postscript_form = MACOS
        npm.last_submission = sub
        return True
    monkeypatch.setattr(npm, "print_frames", fake)
    # P16: `printer` is the QUEUE, not the name macOS shows (review of
    # fix/4.3.8, D5); the dialog only knows the display name
    monkeypatch.setattr(npm, "_queue_name", lambda shown: {
        "HP Color LaserJet 5550": "HP_CLJ5550_PostScript"}.get(shown, shown))
    monkeypatch.setattr(tab, "_start_read_back", lambda *a, **k: None)
    tab._print_native([(tmp_path / "p.tif", 0)])
    rec = json.loads(vp.print_record_path(ti2).read_text(encoding="utf-8"))
    assert (rec["path"], rec["printer"], rec["postscript"]) == (
        "dialog", "HP_CLJ5550_PostScript", MACOS)


def test_the_direct_route_records_the_printers_own_rgb_on_a_postscript_queue(
        qapp, tmp_path, mac, ps_queue):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    ti2 = tmp_path / "v.ti2"
    tab._pending_print_record = (ti2, dict(colour="raw", intent="", profile=None,
                                           route=vp.ROUTE_CHROMIQ))
    tab._note_print_path(vp.PATH_DIRECT, "HP",
                         DEVICE if tab._is_postscript_queue("HP") else "")
    tab._commit_print_record(True)
    rec = json.loads(vp.print_record_path(ti2).read_text(encoding="utf-8"))
    assert (rec["path"], rec["printer"], rec["postscript"]) == ("direct", "HP", DEVICE)
