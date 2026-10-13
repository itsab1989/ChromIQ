"""4.3.5 beta 2: the PostScript choice is made AFTER the macOS print dialog.

Basti, 2026-10-13 ("go with 2"): on the macOS dialog route the Print Chart
tab decided BEFORE the dialog, from the printer the dialog opens on, whether
to show the PostScript row, its notices, the CMYK-driver hint and the
verification note's dialog paragraphs. The user picks the printer only IN the
dialog, so those could describe the wrong printer. Now:

* after the dialog closes with Print and before anything is sent, a
  PostScript printer on a target with no choice is asked (M-PRINT-PS-ASK);
  the answer is stored for the PROJECT (Basti, same day: the calibration is
  the first step), every run inherits it and may have its own; Cancel prints
  nothing;
* a stored choice is used without asking; any other printer is never asked;
* the row is shown only once the run has a stored choice;
* nothing printer-specific is shown before the dialog; a printer whose driver
  takes CMYK raster gets M-PRINT-CMYK-RASTER-ROUTE after the job, once per run.
"""
from __future__ import annotations

import inspect
import os
from dataclasses import replace

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

DEVICE, MACOS = ppd_color.POSTSCRIPT_DEVICE_RGB, ppd_color.POSTSCRIPT_AS_MACOS


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- print_frames: the decision after the dialog ----------------------------
class _Ask:
    def __init__(self, answer):
        self.answer, self.asked = answer, []

    def __call__(self, printer):
        self.asked.append(printer)
        return self.answer


def test_a_postscript_printer_with_no_choice_is_asked_after_the_dialog():
    ask = _Ask(MACOS)
    assert npm.form_after_dialog(True, None, ask, lambda: "HP 5550") == (True, MACOS)
    assert ask.asked == ["HP 5550"]


def test_cancel_sends_nothing():
    ask = _Ask(None)
    assert npm.form_after_dialog(True, None, ask, lambda: "PS") == (False, None)


@pytest.mark.parametrize("stored", [DEVICE, MACOS])
def test_a_stored_choice_is_used_without_asking(stored):
    ask = _Ask(DEVICE if stored == MACOS else MACOS)
    assert npm.form_after_dialog(True, stored, ask) == (True, stored)
    assert ask.asked == []


@pytest.mark.parametrize("stored", [None, DEVICE, MACOS])
def test_a_printer_that_is_not_postscript_is_never_asked(stored):
    ask = _Ask(MACOS)
    assert npm.form_after_dialog(False, stored, ask) == (True, stored)
    assert ask.asked == []


def test_without_a_way_to_ask_the_default_is_used():
    assert npm.form_after_dialog(True, None, None) == (True, ppd_color.DEFAULT_POSTSCRIPT_FORM)


def test_print_frames_asks_after_the_dialog_and_before_either_sender():
    """MUTATION: move the question before ``runModalWithPrintInfo_`` and the
    printer the user picks in the dialog is not the one asked about."""
    src = inspect.getsource(npm.print_frames)
    asked = src.index("form_after_dialog(")
    assert src.index("panel.runModalWithPrintInfo_(print_info)") < asked
    assert src.index("_is_ps = is_postscript_queue(_ppd_after)") < asked
    assert asked < src.index("_print_device_rgb_postscript(print_info")
    assert asked < src.index("printOperationWithView_printInfo_")
    assert "if not _go:" in src[asked:asked + 300]


# ---- the tab ------------------------------------------------------------------
def test_the_tab_never_asks_which_printer_the_dialog_opens_on():
    """MUTATION: put back a ``dialog_printer()`` call in the tab and this goes
    red: that printer is not the one the user picks in the dialog."""
    from ui.tabs import tab_print as tp
    src = inspect.getsource(tp)
    assert "dialog_printer" not in src
    assert "sharedPrintInfo" not in src


def _env(tmp_path, run_type=RUN_TYPE_PROFILING):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("use_native_print_dialog", True)
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(run_type)
    return s, fm, ctl


@pytest.fixture
def mac(monkeypatch):
    from ui.tabs import tab_print as tp
    monkeypatch.setattr(tp, "is_macos", lambda: True)
    monkeypatch.setattr("sys.platform", "darwin")
    return tp


@pytest.fixture
def approved(monkeypatch):
    for name in ("M_PRINT_PS_ASK", "M_PRINT_PS_FORM_CHOICE", "M_PRINT_PS_FORM_APPLIES"):
        monkeypatch.setattr(MM, name, replace(getattr(MM, name), approved=True))


def _tab(s, ctl):
    from ui.tabs.tab_print import TabPrint
    tab = TabPrint(s)
    tab.set_target_controller(ctl)
    tab._update_colour_row_visible()
    tab._commit_print_record = lambda submitted: tab.__dict__.setdefault(
        "_recorded", []).append(submitted)
    return tab


def _answer(monkeypatch, tp, which):
    """The asking window answers with the button whose choice is *which*
    (an index into M-PRINT-PS-FORM-CHOICE's lines), or Cancel."""
    seen = []

    def clicked(box):
        seen.append((box.text(), box.informativeText(),
                     [b.text() for b in box.buttons()]))
        if which == "cancel":
            return box.button(QMessageBox.StandardButton.Cancel)
        label, lines = MM.M_PRINT_PS_FORM_CHOICE.render()
        want = f"{label} {lines.split(chr(10))[which]}"
        return next(b for b in box.buttons() if b.text() == want)
    monkeypatch.setattr(tp.QMessageBox, "exec", lambda box: 0)
    monkeypatch.setattr(tp.QMessageBox, "clickedButton", clicked)
    return seen


def _fake_print_frames(monkeypatch, *, postscript: bool, printer="PS Printer"):
    """``print_frames`` with the dialog closed on Print on *printer*: it makes
    the real decision (``form_after_dialog``) and records what would be sent."""
    sent = []

    def fake(pages, printer_=None, postscript_form=None, refuse_unlisted_paper=None,
             ask_postscript_form=None, **kw):
        go, form = npm.form_after_dialog(postscript, postscript_form,
                                         ask_postscript_form, lambda: printer)
        if not go:
            return False
        sent.append(form if postscript else "raster")
        npm.last_submission = None
        return True
    monkeypatch.setattr(npm, "print_frames", fake)
    return sent


def test_the_run_is_asked_once_and_its_answer_is_kept(qapp, tmp_path, mac, approved, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    seen = _answer(monkeypatch, mac, 1)
    sent = _fake_print_frames(monkeypatch, postscript=True)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [MACOS]
    assert len(seen) == 1
    title, body = MM.M_PRINT_PS_ASK.render(printer="PS Printer")
    assert seen[0][0] == title and seen[0][1] == body
    # Basti, 2026-10-13: the answer is the PROJECT's (project.json), the
    # run inherits it and keeps nothing of its own
    run = fm.project().run("run1")
    assert "postscript" not in (run.load_meta().print_settings or {})
    assert Project.load(tmp_path / "P").print_setting("postscript") == MACOS
    # the second print of the run, and its verification chart: not asked
    tab._print_native([(tmp_path / "p.tif", 0)])
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    _tab(s, ctl)._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [MACOS, MACOS, MACOS]
    assert len(seen) == 1


def test_the_first_choice_is_the_default_button_and_prints_its_own_rgb(
        qapp, tmp_path, mac, approved, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    seen = _answer(monkeypatch, mac, 0)
    sent = _fake_print_frames(monkeypatch, postscript=True)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [DEVICE]
    label, lines = MM.M_PRINT_PS_FORM_CHOICE.render()
    a, b = lines.split("\n")
    assert seen[0][2][:2] == [f"{label} {a}", f"{label} {b}"]


def test_cancel_prints_nothing_and_keeps_nothing(qapp, tmp_path, mac, approved, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    _answer(monkeypatch, mac, "cancel")
    sent = _fake_print_frames(monkeypatch, postscript=True)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == []
    assert tab._recorded == [False]
    run = fm.project().run("run1")
    assert "postscript" not in (run.load_meta().print_settings or {})


def test_a_printer_that_is_not_postscript_is_never_asked_by_the_tab(
        qapp, tmp_path, mac, approved, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    seen = _answer(monkeypatch, mac, 1)
    sent = _fake_print_frames(monkeypatch, postscript=False, printer="Canon PRO-300")
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == ["raster"] and seen == []
    run = fm.project().run("run1")
    assert "postscript" not in (run.load_meta().print_settings or {})


def test_the_asking_texts_are_approved():
    """Basti, 2026-10-13: the option-2 texts approved; M-PRINT-PS-ASK worded
    for the project (the choice is the project's)."""
    assert MM.M_PRINT_PS_ASK.approved and MM.M_PRINT_PS_FORM_APPLIES.approved
    body = MM.M_PRINT_PS_ASK.body
    assert "this project\u2019s charts" in body
    assert "kept for the whole project: its calibration, its runs" in body


def test_until_approved_nobody_is_asked_and_the_default_goes(qapp, tmp_path, mac, monkeypatch):
    monkeypatch.setattr(MM, "M_PRINT_PS_ASK", replace(MM.M_PRINT_PS_ASK, approved=False))
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    seen = _answer(monkeypatch, mac, 1)
    sent = _fake_print_frames(monkeypatch, postscript=True)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [ppd_color.DEFAULT_POSTSCRIPT_FORM] and seen == []


def test_the_row_shows_only_once_the_run_has_a_choice(qapp, tmp_path, mac, approved, monkeypatch):
    """MUTATION: show the row before a choice exists and it is PostScript
    talk on a tab that does not know the printer yet."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab._tiff_pages = [tmp_path / "p.tif"]
    tab._update_ps_form_row()
    assert tab._ps_form_row.isHidden()
    _answer(monkeypatch, mac, 0)
    _fake_print_frames(monkeypatch, postscript=True)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert not tab._ps_form_row.isHidden()
    assert tab._ps_device_rb.isChecked()
    assert not tab._ps_applies_lbl.isHidden()
    assert tab._ps_applies_lbl.text() == MM.M_PRINT_PS_FORM_APPLIES.render()[1]


# ---- the CMYK raster hint, after the job --------------------------------------
def _cmyk_job(monkeypatch, cmyk="KCMY"):
    sub = npm.Submission("Sample DeskJet", {}, 0.0, b"", None)
    sub.cmyk_raster = cmyk

    def fake(pages, **kw):
        npm.last_submission = sub
        return True
    monkeypatch.setattr(npm, "print_frames", fake)


def test_a_cmyk_raster_printer_is_told_after_the_job_once_per_run(
        qapp, tmp_path, mac, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab._start_read_back = lambda rb: None
    told = []
    monkeypatch.setattr(mac.QMessageBox, "information",
                        lambda parent, t, b: told.append((t, b)))
    _cmyk_job(monkeypatch)
    tab._print_native([(tmp_path / "p.tif", 0)])
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert told == [MM.M_PRINT_CMYK_RASTER_ROUTE.render(printer="Sample DeskJet")]
    # a fresh tab (another session) remembers it for the run
    tab2 = _tab(s, ctl)
    tab2._start_read_back = lambda rb: None
    tab2._print_native([(tmp_path / "p.tif", 0)])
    assert len(told) == 1


def test_any_other_job_gets_no_cmyk_window(qapp, tmp_path, mac, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab._start_read_back = lambda rb: None
    told = []
    monkeypatch.setattr(mac.QMessageBox, "information",
                        lambda parent, t, b: told.append((t, b)))
    _cmyk_job(monkeypatch, cmyk=None)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert told == []


def test_the_notice_is_the_same_whatever_the_printer(qapp, tmp_path, mac, monkeypatch):
    """Nothing printer-specific before the dialog: the CMYK hint is not in the
    notice even for a CMYK raster queue."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    plain = tab._macos_dialog_notice()
    monkeypatch.setattr(mac, "_queue_cmyk_raster", lambda q: "KCMY")
    assert tab._macos_dialog_notice() == plain
    assert MM.M_PRINT_CMYK_RASTER_ROUTE.title not in plain


def test_the_asking_window_fits_its_long_buttons():
    """Measured on screen 2026-10-13: without the rule the second button read
    "RINT LIKE PREVIEW AND MOST OTHER APP" (Knut, #130 2026-07-28: every
    window follows the rule against clipped labels)."""
    from ui.tabs import tab_print as tp
    src = inspect.getsource(tp.TabPrint._ask_ps_form)
    assert "fit_message_box_buttons(box)" in src
    assert src.index("fit_message_box_buttons(box)") < src.index("box.exec()")


# ---- the choice belongs to the project (Basti, 2026-10-13) --------------------
def _cal_env(tmp_path):
    from core.measurement_target import RUN_TYPE_CALIBRATION
    s, fm, ctl = _env(tmp_path)
    ctl.set_calibration_allowed(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    return s, fm, ctl


def test_a_calibration_chart_is_asked_and_the_runs_follow_its_answer(
        qapp, tmp_path, mac, approved, monkeypatch):
    """MUTATION: keep the answer for the run only (or not ask on the
    calibration) and the profiling run after it is asked again, or prints in
    a form its calibration was not printed in."""
    s, fm, ctl = _cal_env(tmp_path)
    assert ctl.target.is_calibration()
    tab = _tab(s, ctl)
    seen = _answer(monkeypatch, mac, 1)
    sent = _fake_print_frames(monkeypatch, postscript=True)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [MACOS] and len(seen) == 1
    assert Project.load(tmp_path / "P").print_setting("postscript") == MACOS
    # the calibration has no row of its own: it follows the project
    tab._tiff_pages = [tmp_path / "p.tif"]
    tab._update_ps_form_row()
    assert tab._ps_form_row.isHidden()
    # the profiling run and its verification: not asked, the project's form
    ctl.set_run_type(RUN_TYPE_PROFILING)
    run_tab = _tab(s, ctl)
    run_tab._print_native([(tmp_path / "p.tif", 0)])
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    _tab(s, ctl)._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [MACOS, MACOS, MACOS] and len(seen) == 1


def test_a_run_may_override_the_project_and_the_project_keeps_its_choice(
        qapp, tmp_path, mac, approved, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    fm.project().set_print_setting("postscript", MACOS)
    tab = _tab(s, ctl)
    tab._tiff_pages = [tmp_path / "p.tif"]
    tab._update_ps_form_row()
    assert not tab._ps_form_row.isHidden()          # inherited: shown
    assert tab._ps_macos_rb.isChecked()
    tab._ps_device_rb.setChecked(True)              # the run's own
    assert fm.project().run("run1").load_meta().print_settings["postscript"] == DEVICE
    assert Project.load(tmp_path / "P").print_setting("postscript") == MACOS
    sent = _fake_print_frames(monkeypatch, postscript=True)
    seen = _answer(monkeypatch, mac, 1)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [DEVICE] and seen == []


def test_a_refined_run_keeps_its_parents_choice_before_the_projects(
        qapp, tmp_path, mac, approved, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    project = fm.project()
    project.set_print_setting("postscript", MACOS)
    r1 = project.run("run1")
    m1 = r1.load_meta()
    m1.print_settings = {"postscript": DEVICE}
    r1.save_meta(m1)
    r2 = project.new_run()
    m2 = r2.load_meta()
    m2.parent_run = "run1"
    r2.save_meta(m2)
    ctl.set_profile_run(r2.id)
    tab = _tab(s, ctl)
    assert tab._ps_form() == DEVICE
    m2.parent_run = None
    r2.save_meta(m2)
    assert tab._ps_form() == MACOS                   # no parent: the project's


def test_the_project_choice_survives_loading_and_an_older_project_has_none(tmp_path):
    p = Project.create(tmp_path / "Q", "Q")
    assert p.print_setting("postscript") is None     # project.json without it
    assert p.set_print_setting("postscript", MACOS) is True
    assert p.set_print_setting("postscript", MACOS) is False
    assert Project.load(tmp_path / "Q").print_setting("postscript") == MACOS


# ---- (e) a "Preview" run by the direct route --------------------------------
@pytest.fixture
def direct(monkeypatch, tmp_path):
    ppd = tmp_path / "q.ppd"
    ppd.write_text('*PPD-Adobe: "4.3"\n', encoding="utf-8")   # no filter: PostScript
    monkeypatch.setattr(ppd_color, "ppd_path_for_queue", lambda q: str(ppd))
    return ppd


def test_a_preview_run_by_the_direct_route_is_asked_once_approved(
        qapp, tmp_path, mac, direct, monkeypatch):
    """MUTATION: drop the question and a "Preview" run's chart goes to a
    PostScript printer in the Photoshop form by the direct route, unasked."""
    s, fm, ctl = _env(tmp_path)
    fm.project().set_print_setting("postscript", MACOS)
    tab = _tab(s, ctl)
    assert not MM.M_PRINT_DIRECT_LIKE_PREVIEW.approved
    assert tab._ask_direct_like_preview("Q") is None       # hidden: as before
    monkeypatch.setattr(MM, "M_PRINT_DIRECT_LIKE_PREVIEW",
                        replace(MM.M_PRINT_DIRECT_LIKE_PREVIEW, approved=True))
    seen = []

    def clicked(box):
        seen.append((box.text(), box.informativeText(), [b.text() for b in box.buttons()]))
        return next(b for b in box.buttons() if b.text() == "Use the print dialog")
    monkeypatch.setattr(mac.QMessageBox, "exec", lambda box: 0)
    monkeypatch.setattr(mac.QMessageBox, "clickedButton", clicked)
    assert tab._ask_direct_like_preview("Q") == "dialog"
    title, body = MM.M_PRINT_DIRECT_LIKE_PREVIEW.render()
    assert seen[0][0] == title and seen[0][1] == body
    assert sorted(seen[0][2]) == ["Cancel", "Print anyway", "Use the print dialog"]
    # the Photoshop form, or a printer that is not PostScript: never asked
    fm.project().set_print_setting("postscript", DEVICE)
    assert tab._ask_direct_like_preview("Q") is None
    fm.project().set_print_setting("postscript", MACOS)
    direct.write_text('*cupsFilter: "application/vnd.cups-raster 0 rastertoqq"\n',
                      encoding="utf-8")
    assert tab._ask_direct_like_preview("Q") is None
    assert len(seen) == 1


def test_the_direct_route_asks_before_it_sends_anything():
    from ui.tabs import tab_print as tp
    src = inspect.getsource(tp.TabPrint._print_pages)
    asked = src.index("self._ask_direct_like_preview(printer)")
    assert asked < src.index("self._send_page(")
    assert asked < src.index("self._show_preflight(")
    assert 'self._print_native(pages, printer=printer)' in src[asked:asked + 300]
