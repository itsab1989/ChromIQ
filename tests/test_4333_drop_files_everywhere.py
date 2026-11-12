"""4.3.33: files dragged from the file manager onto every Browse row where
that is safe (the owner, after 4.3.32's Measurement info: "in the other
places where safe and beneficial"). The inventory and the rule are in
docs/design/tool_availability.md ("Files dropped on every Browse row").

ONE TABLE, ONE ROW PER WINDOW ROW THAT TAKES A DROP. For each it is pinned
that

* a fitting file dropped on the row reaches the very method the row's Browse
  hands its chosen file to, with the same argument (the method is patched on
  the class before the window is built, so the zone's connection and the
  Browse call both reach the recorder);
* a file of another kind is not accepted (no call, no highlight, the field
  unchanged), and neither is a folder on a file row or a file on a folder
  row;
* a greyed or busy row accepts nothing;
* a file dropped on an editable field is not pasted into it as text, and
  plain text dropped there still is.

And, from a second table, that every row the inventory SKIPS takes no file.

The drags are sent to the WINDOW at the row's field, as a real drag is:
Qt picks the widget under the pointer and walks up to the first that takes
drops, so a field that swallowed the drag would fail here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PyQt6.QtGui import (QDragEnterEvent, QDragMoveEvent,  # noqa: E402
                         QDropEvent)
from PyQt6.QtWidgets import (QAbstractScrollArea, QApplication,  # noqa: E402
                             QLineEdit, QScrollArea, QWidget)

from tests.test_profile_tools import _runner, _Settings  # noqa: E402


_KEEP: list = []      # mime data must outlive the events that point at it


def _mime(*paths, text: "str | None" = None) -> QMimeData:
    m = QMimeData()
    if paths:
        m.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    if text is not None:
        m.setText(text)
    _KEEP.append(m)
    return m


def _pump(qapp, n: int = 4) -> None:
    for _ in range(n):
        qapp.processEvents()


def _bring_into_view(w: QWidget) -> None:
    from PyQt6.QtWidgets import QStackedWidget
    child, p = w, w.parentWidget()
    while p is not None:          # the page it is on comes to the front
        if isinstance(p, QStackedWidget):
            p.setCurrentWidget(child)
        child, p = p, p.parentWidget()
    p = w.parentWidget()
    while p is not None:
        if isinstance(p, QScrollArea):
            p.ensureWidgetVisible(w, 0, 0)
        p = p.parentWidget()


def drag_to(qapp, w: QWidget, mime: QMimeData, *, drop: bool = True) -> bool:
    """Enter, move and drop *mime* on the middle of *w*, sent to its WINDOW
    (so Qt routes it as a real drag). True when the drag was accepted."""
    win = w.window()
    _bring_into_view(w)
    _pump(qapp, 2)
    if not w.isVisible():
        # A row on a page that needs a project in another run type to be
        # shown: its hidden containers are shown, so the drag still goes
        # through the window as a real one does. (Sending a drag straight to
        # a hidden widget crashed a worker once, gate 2026-11-12.)
        p = w
        while p is not None and p is not win:
            if not p.isVisibleTo(win):
                p.setVisible(True)
            p = p.parentWidget()
        _bring_into_view(w)
        _pump(qapp, 2)
    pos = w.mapTo(win, w.rect().center())
    handle = win.windowHandle()
    hit = win.childAt(pos)
    while hit is not None and hit is not w:
        hit = hit.parentWidget()
    if hit is None:
        # Deep in a collapsed section or scrolled past the test window's
        # size: a file drag goes to the row's own drop zone instead, as the
        # 4.3.32 Measurement info tests do; plain text to the field itself
        # (its own handling). Never a file drag to a plain hidden widget:
        # that crashed a worker (gate, 2026-11-12).
        if mime.hasUrls():
            try:
                owner = _drop_of(w)._row
            except AssertionError:
                return False        # no drop zone there: nothing can take it
        else:
            owner = w
        pos = owner.rect().center()
        handle = owner
    act = Qt.DropAction.CopyAction
    btn = Qt.MouseButton.LeftButton
    mod = Qt.KeyboardModifier.NoModifier
    enter = QDragEnterEvent(QPoint(pos), act, mime, btn, mod)
    QApplication.sendEvent(handle, enter)
    move = QDragMoveEvent(QPoint(pos), act, mime, btn, mod)
    QApplication.sendEvent(handle, move)
    ok = move.isAccepted()
    if drop:
        d = QDropEvent(QPointF(pos), act, mime, btn, mod)
        QApplication.sendEvent(handle, d)
        ok = ok and d.isAccepted()
        _pump(qapp)
    return ok


# ---------------------------------------------------------------------------
# the table
# ---------------------------------------------------------------------------

@dataclass
class Row:
    id: str
    build: Callable            # (settings) -> window
    owner: Callable            # () -> the class whose method is the handler
    handler: str               # the method Browse hands its file to
    drop_on: Callable          # (win) -> the widget the file is dropped on
    browse: Callable           # (win) -> press the row's Browse
    dialog: str                # "module:attr" of the chooser Browse calls
    good: tuple                # suffixes of fitting files
    bad: str = ".pdf"          # a kind the row does not take
    several: bool = False      # a list: several files at once
    folder: bool = False       # a folder row
    closed: "Callable | None" = None   # (win) -> make the row refuse
    editable: "Callable | None" = None  # (win) -> its editable field
    prepare: "Callable | None" = None   # (win) -> make the row visible
    extra_patches: dict = field(default_factory=dict)
    # the accent the window's own accent elements are painted from (its
    # masthead, primary button and focus ring), before `accent_for`
    accent: Callable = lambda w: type(w).ACCENT


def _tools(name):
    def build(settings):
        from ui.dialogs import tools_dialogs as T
        cls = getattr(T, name)
        try:
            return cls(_runner(), settings)
        except TypeError:
            return cls(settings)
    return build


def _cls(module, name):
    def get():
        import importlib
        return getattr(importlib.import_module(module), name)
    return get


def _busy(win):
    win._busy = True


_TD = "ui.dialogs.tools_dialogs"
_OPEN = _TD + ":open_file_dialog"
_OPENS = _TD + ":open_files_dialog"

ROWS: list[Row] = [
    # -- Tools > Average / Merge (R04-R06) ---------------------------------
    Row("average-list", _tools("AverageMeasurementsDialog"),
        _cls(_TD, "AverageMeasurementsDialog"), "_use_files",
        lambda w: w._list, lambda w: w._add_files(), _OPENS, (".ti3",),
        several=True, closed=_busy),
    Row("merge-primary", _tools("MergeMeasurementsDialog"),
        _cls(_TD, "MergeMeasurementsDialog"), "_use_primary",
        lambda w: w._primary_field, lambda w: w._pick_primary(), _OPEN,
        (".ti3",), closed=_busy),
    Row("merge-additional", _tools("MergeMeasurementsDialog"),
        _cls(_TD, "MergeMeasurementsDialog"), "_use_additional",
        lambda w: w._list, lambda w: w._add_additional(), _OPENS, (".ti3",),
        several=True, closed=_busy),
    # -- converters (R07-R09) ------------------------------------------------
    Row("ti1-to-i1profiler", _tools("Ti1ToI1ProfilerDialog"),
        _cls(_TD, "Ti1ToI1ProfilerDialog"), "_use_ti1",
        lambda w: w._ti1_field, lambda w: w._pick_ti1(), _OPEN, (".ti1",),
        closed=_busy),
    Row("i1profiler-to-ti3", _tools("I1ProfilerToTi3Dialog"),
        _cls(_TD, "I1ProfilerToTi3Dialog"), "_use_txt",
        lambda w: w._txt_field, lambda w: w._pick_txt(), _OPEN,
        (".txt", ".mxf", ".cxf"), bad=".ti3", closed=_busy),
    Row("i1profiler-to-ti1", _tools("I1ProfilerToTi1Dialog"),
        _cls(_TD, "I1ProfilerToTi1Dialog"), "_use_src",
        lambda w: w._src_field, lambda w: w._pick_src(), _OPEN,
        (".pxf", ".pwxf", ".cgats", ".txt"), bad=".ti3", closed=_busy),
    # -- Verify against reference (R10-R13) ----------------------------------
    Row("verify-ref-expected-box", _tools("VerifyAgainstReferenceDialog"),
        _cls(_TD, "VerifyAgainstReferenceDialog"), "_use_reference_file",
        lambda w: w._ref_edit, lambda w: w._load_reference_file(), _OPEN,
        (".txt", ".cgats", ".ti3", ".csv"), closed=_busy,
        editable=lambda w: w._ref_edit),
    Row("verify-ref-measured", _tools("VerifyAgainstReferenceDialog"),
        _cls(_TD, "VerifyAgainstReferenceDialog"), "_use_measured",
        lambda w: w._measured_field, lambda w: w._pick_measured(), _OPEN,
        (".ti3",), closed=_busy),
    Row("verify-ref-chart", _tools("VerifyAgainstReferenceDialog"),
        _cls(_TD, "VerifyAgainstReferenceDialog"), "_use_chart",
        lambda w: w._chart_field, lambda w: w._pick_chart(), _OPEN,
        (".ti1", ".ti2"), closed=_busy),
    Row("verify-ref-profile", _tools("VerifyAgainstReferenceDialog"),
        _cls(_TD, "VerifyAgainstReferenceDialog"), "_use_profile",
        lambda w: w._profile_field, lambda w: w._pick_profile(), _OPEN,
        (".icc", ".icm"), closed=_busy),
    # -- Verify a profile (R14-R15) -------------------------------------------
    Row("verify-profile-profile", _tools("VerifyProfileDialog"),
        _cls(_TD, "VerifyProfileDialog"), "_use_profile",
        lambda w: w._profile_field, lambda w: w._pick_profile(), _OPEN,
        (".icc", ".icm"), closed=_busy),
    Row("verify-profile-measured", _tools("VerifyProfileDialog"),
        _cls(_TD, "VerifyProfileDialog"), "_use_measured",
        lambda w: w._measured_field, lambda w: w._pick_measured(), _OPEN,
        (".ti3",), closed=_busy),
    # -- every Tools window's destination folder (R16) -----------------------
    Row("tools-destination-folder", _tools("MergeMeasurementsDialog"),
        _cls(_TD, "_OutputRow"), "_use_dir",
        lambda w: w._output._dir_edit, lambda w: w._output._browse(),
        _TD + ":open_dir_dialog", (), folder=True, closed=_busy,
        editable=lambda w: w._output._dir_edit),
    # -- Device link (R17-R21) ------------------------------------------------
]

_DL = "ui.dialogs.devicelink_dialog"
_DLA = "ui.dialogs.devicelink_apply_dialog"


def _dl(settings):
    from ui.dialogs.devicelink_dialog import DeviceLinkDialog
    return DeviceLinkDialog(_runner(), settings)


def _dla(settings):
    from ui.dialogs.devicelink_apply_dialog import DeviceLinkApplyDialog
    return DeviceLinkApplyDialog(_runner(), settings)


def _expert_open(w):
    from ui.widgets import CollapsibleGroupBox
    for g in w.findChildren(CollapsibleGroupBox):
        if hasattr(g, "set_collapsed"):
            g.set_collapsed(False)
        elif hasattr(g, "setCollapsed"):
            g.setCollapsed(False)


def _images_on(w):
    _expert_open(w)
    w._image_cb.setChecked(True)


def _images_off(w):
    w._image_cb.setChecked(False)


ROWS += [
    Row("devicelink-source", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_use_source", lambda w: w._src_field, lambda w: w._pick_source(),
        _DL + ":open_file_dialog", (".icc", ".icm"), closed=_busy),
    Row("devicelink-destination", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_set_destination", lambda w: w._dst_field,
        lambda w: w._pick_destination(), _DL + ":open_file_dialog",
        (".icc", ".icm"), closed=_busy),
    Row("devicelink-abstract", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_use_abstract", lambda w: w._abstract_field,
        lambda w: w._pick_abstract(), _DL + ":open_file_dialog",
        (".icc", ".icm"), closed=_busy, prepare=_expert_open),
    Row("devicelink-cal", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_use_cal", lambda w: w._cal_field, lambda w: w._pick_cal(),
        _DL + ":open_file_dialog", (".cal",), closed=_busy,
        prepare=_expert_open),
    Row("devicelink-images", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_use_images", lambda w: w._image_list, lambda w: w._pick_images(),
        _DL + ":open_files_dialog", (".tif", ".jpg", ".png"), several=True,
        closed=_images_off, prepare=_images_on),
    # -- Apply device link (R22-R24) -------------------------------------------
    Row("devicelink-apply-link", _dla, _cls(_DLA, "DeviceLinkApplyDialog"),
        "_set_link", lambda w: w._link_field, lambda w: w._pick_link(),
        _DLA + ":open_file_dialog", (".icc", ".icm"), closed=_busy),
    Row("devicelink-apply-source", _dla, _cls(_DLA, "DeviceLinkApplyDialog"),
        "_use_source", lambda w: w._src_field, lambda w: w._pick_source(),
        _DLA + ":open_file_dialog", (".icc", ".icm"), closed=_busy),
    Row("devicelink-apply-images", _dla, _cls(_DLA, "DeviceLinkApplyDialog"),
        "_use_images", lambda w: w._image_list, lambda w: w._pick_images(),
        _DLA + ":open_files_dialog", (".tif", ".jpeg"), several=True,
        closed=_busy),
]


_SC = "ui.dialogs.scanin_dialog"
_ST = "ui.dialogs.scanin_target_dialog"


def _scanner(settings):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    return ScannerProfileDialog(_runner(), settings)


def _scanin_target(settings):
    from ui.dialogs.scanin_target_dialog import ScaninTargetDialog
    return ScaninTargetDialog(settings)


def _printer_on(w):
    w._printer_cb.setChecked(True)


def _standard_other(w):
    w._mode_standard.setChecked(True)
    w._target_combo.setCurrentIndex(w._target_combo.count() - 1)


def _i1p_mode(w):
    for name in ("_mode_i1p", "_i1p_radio", "_rb_i1p"):
        rb = getattr(w, name, None)
        if rb is not None:
            rb.setChecked(True)
            return
    w._panel_i1p.setVisible(True)


ROWS += [
    # -- Scanner profile (R25-R29) ---------------------------------------------
    Row("scanner-chart", _scanner, _cls(_SC, "ScannerProfileDialog"),
        "_set_chart", lambda w: w._ti3_field, lambda w: w._pick_chart(),
        _SC + ":open_file_dialog", (".ti3",), bad=".ti2", closed=_busy),
    Row("scanner-chart-printer-mode", _scanner,
        _cls(_SC, "ScannerProfileDialog"), "_set_chart",
        lambda w: w._ti3_field, lambda w: w._pick_chart(),
        _SC + ":open_file_dialog", (".ti2",), bad=".ti3", closed=_busy,
        prepare=_printer_on),
    Row("scanner-scan", _scanner, _cls(_SC, "ScannerProfileDialog"),
        "_on_scan_dropped", lambda w: w._scan_field, None,
        _SC + ":open_file_dialog", (".tif", ".jpg", ".png"), closed=_busy),
    Row("scanner-cht", _scanner, _cls(_SC, "ScannerProfileDialog"),
        "_use_cht", lambda w: w._cht_field, lambda w: w._pick_cht(),
        _SC + ":open_file_dialog", (".cht",), closed=_busy,
        prepare=_standard_other),
    Row("scanner-reference", _scanner, _cls(_SC, "ScannerProfileDialog"),
        "_use_ref", lambda w: w._ref_field, lambda w: w._pick_ref(),
        _SC + ":open_file_dialog", (".cie", ".txt", ".ti3", ".cxf"),
        closed=_busy, prepare=_standard_other),
    Row("scanner-printer-scanner-profile", _scanner,
        _cls(_SC, "ScannerProfileDialog"), "_use_scanner_profile",
        lambda w: w._printer_prof_field, lambda w: w._pick_scanner_profile(),
        _SC + ":open_file_dialog", (".icc", ".icm"), closed=_busy,
        prepare=_printer_on),
    # -- Scanner target from a chart (R31-R34) --------------------------------
    Row("scanin-target-ti3", _scanin_target, _cls(_ST, "ScaninTargetDialog"),
        "_use_ti3", lambda w: w._ti3_field, lambda w: w._pick_ti3(),
        _ST + ":open_file_dialog", (".ti3",), closed=_busy),
    Row("scanin-target-patch-set", _scanin_target,
        _cls(_ST, "ScaninTargetDialog"), "_use_pset",
        lambda w: w._pset_field, lambda w: w._pick_pset(),
        _ST + ":open_file_dialog", (".ti1", ".txt", ".pxf"), closed=_busy,
        prepare=_i1p_mode),
    Row("scanin-target-pages", _scanin_target,
        _cls(_ST, "ScaninTargetDialog"), "_use_tiffs",
        lambda w: w._tiff_field, lambda w: w._pick_tiffs(),
        _ST + ":open_files_dialog", (".tif", ".tiff"), several=True,
        closed=_busy, prepare=_i1p_mode),
    Row("scanin-target-measurement", _scanin_target,
        _cls(_ST, "ScaninTargetDialog"), "_use_meas",
        lambda w: w._meas_field, lambda w: w._pick_meas(),
        _ST + ":open_file_dialog", (".ti3", ".mxf", ".txt", ".cxf"),
        closed=_busy, prepare=_i1p_mode),
    # -- Scanner advanced: gamut source (R35) -----------------------------------
    Row("scanner-advanced-gamut", lambda s: _scanner_adv(),
        _cls("ui.dialogs.scanner_colprof", "ScannerAdvancedDialog"),
        "_use_gamut", lambda w: w._gam_path, lambda w: w._browse_gamut(),
        "ui.dialogs.scanner_colprof:open_file_dialog", (".icc", ".icm"),
        closed=lambda w: w._gam_mode.setCurrentIndex(0),
        prepare=lambda w: w._gam_mode.setCurrentIndex(1),
        editable=lambda w: w._gam_path,
        accent=lambda w: __import__("ui.styles").styles.SPEC_GREEN),
]


def _scanner_adv():
    from ui.dialogs.scanner_colprof import ScannerAdvancedDialog
    return ScannerAdvancedDialog({}, printer=True)


def _softproof(settings):
    from ui.dialogs.softproof_dialog import SoftproofDialog
    return SoftproofDialog(_runner(), settings)


def _profile_info(settings):
    from ui.dialogs.profile_info_dialog import ProfileInfoDialog
    return ProfileInfoDialog(_runner(), settings)


def _report(settings):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(settings)


def _prefs(_settings):
    from core.settings import AppSettings    # the suite's sandboxed store
    from ui.dialogs.settings_dialog import SettingsDialog
    return SettingsDialog(AppSettings(), None)


def _mod_const(module, name):
    def get(_w):
        import importlib
        return getattr(importlib.import_module(module), name)
    return get


def _grey(attr):
    def close(w):
        getattr(w, attr).setEnabled(False)
    return close


_SP = "ui.dialogs.softproof_dialog"
_PI = "ui.dialogs.profile_info_dialog"
_MR = "ui.dialogs.measurement_report_dialog"
_SD = "ui.dialogs.settings_dialog"


def _press_browse_in(attr):
    """Press the folder button inside a row whose Browse is a closure."""
    def press(w):
        from PyQt6.QtWidgets import QAbstractButton
        btns = [b for b in getattr(w, attr).findChildren(QAbstractButton)]
        btns[-1].click()
    return press


ROWS += [
    # -- Profile info, Soft-proof, Measurement report (R36-R41) ----------------
    Row("profile-info", _profile_info, _cls(_PI, "ProfileInfoDialog"),
        "load_profile", lambda w: w._path_edit, lambda w: w._on_browse(),
        _PI + ":open_file_dialog", (".icc", ".icm"),
        accent=_mod_const(_PI, "_ACCENT")),
    Row("softproof-image", _softproof, _cls(_SP, "SoftproofDialog"),
        "_set_image", lambda w: w._image_edit, lambda w: w._on_browse_image(),
        _SP + ":open_file_dialog", (".tif", ".jpg", ".png"),
        accent=_mod_const(_SP, "_ACCENT")),
    Row("softproof-printer-profile", _softproof,
        _cls(_SP, "SoftproofDialog"), "_use_profile",
        lambda w: w._profile_edit, lambda w: w._on_browse_profile(),
        _SP + ":open_file_dialog", (".icc", ".icm"),
        accent=_mod_const(_SP, "_ACCENT")),
    Row("softproof-monitor-profile", _softproof,
        _cls(_SP, "SoftproofDialog"), "_use_monitor",
        lambda w: w._monitor_edit, lambda w: w._on_browse_monitor(),
        _SP + ":open_file_dialog", (".icc", ".icm"),
        accent=_mod_const(_SP, "_ACCENT")),
    Row("measurement-report-list", _report,
        _cls(_MR, "MeasurementReportDialog"), "_add_measurements",
        lambda w: w._profile_list, lambda w: w._on_add_project(),
        _MR + ":open_files_dialog", (".ti3", ".mxf", ".txt", ".cxf"),
        several=True, closed=_grey("_add_btn"),
        accent=_mod_const("ui.styles", "SPEC_GREEN")),
    # -- Settings folder rows (R43-R46) -----------------------------------------
    Row("settings-argyll-folder", _prefs, _cls(_SD, "SettingsDialog"),
        "_use_argyll_dir", lambda w: w._argyll_edit,
        lambda w: w._browse_argyll(), _SD + ":open_dir_dialog", (),
        folder=True, editable=lambda w: w._argyll_edit,
        accent=lambda w: w._indicator_for),
    Row("settings-output-folder", _prefs, _cls(_SD, "SettingsDialog"),
        "_use_output_dir", lambda w: w._folder_edit,
        lambda w: w._browse_folder(), _SD + ":open_dir_dialog", (),
        folder=True, editable=lambda w: w._folder_edit,
        accent=lambda w: w._indicator_for),
    Row("settings-profile-install-folder", _prefs,
        _cls(_SD, "SettingsDialog"), "_use_profile_dir",
        lambda w: w._profile_dir_edit, _press_browse_in("_profile_dir_zone"),
        _SD + ":open_dir_dialog", (), folder=True,
        editable=lambda w: w._profile_dir_edit,
        accent=lambda w: w._indicator_for),
    Row("settings-sounds-folder", _prefs, _cls(_SD, "SettingsDialog"),
        "_use_sound_dir", lambda w: w._sound_dir_edit,
        _press_browse_in("_sound_dir_zone"), _SD + ":open_dir_dialog", (),
        folder=True, editable=lambda w: w._sound_dir_edit,
        accent=lambda w: w._indicator_for),
]


def _tab_settings():
    from core.settings import AppSettings    # the suite's sandboxed store
    return AppSettings()


def _chart_tab(_s):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart
    s = _tab_settings()
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _measure_tab(_s):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _tab_settings()
    return TabMeasure(ArgyllRunner(s), s)


def _check_tab(_s):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = _tab_settings()
    return TabCheckRefine(ArgyllRunner(s), s)


def _profile_tab(_s):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_profile import TabProfile
    s = _tab_settings()
    return TabProfile(ArgyllRunner(s), s)


def _tab_accent(w):
    return type(w).TAB_ACCENT


def _precond_on(w):
    w._switch_mode("guided")
    w._guided_precond_check.setChecked(True)


def _precond_off(w):
    w._guided_precond_check.setChecked(False)


def _show_import(w):
    w._import_panel.setVisible(True)


def _grey_load_icon(w):
    w._load_btn.setEnabled(False)


_TC = "ui.tabs.tab_chart"
_TM = "ui.tabs.tab_measure"
_TCR = "ui.tabs.tab_check_refine"
_TP = "ui.tabs.tab_profile"


def _param_row(flag):
    def find(w):
        from ui.parameter_widget import ParameterWidget
        for pw in w.findChildren(ParameterWidget):
            if pw._param.get("flag") == flag and \
                    pw._param.get("type") == "file_path":
                return pw
        raise AssertionError(f"no {flag} file row")
    return find


def _manual_and(then):
    def prep(w):
        w._switch_mode("manual")
        then(w)
    return prep


def _enable_param(flag):
    def prep(w):
        pw = _param_row(flag)(w)
        if pw._enable_check is not None:
            pw._enable_check.setChecked(True)
        else:
            pw.set_control_enabled(True)
    return prep


def _disable_param(flag):
    def close(w):
        pw = _param_row(flag)(w)
        if pw._enable_check is not None:
            pw._enable_check.setChecked(False)
        else:
            pw.set_control_enabled(False)
    return close


ROWS += [
    # -- Create Chart (R52) -------------------------------------------------------
    Row("create-chart-refinement-profile", _chart_tab, _cls(_TC, "TabChart"),
        "_use_guided_precond", lambda w: w._guided_precond_path,
        lambda w: w._on_guided_precond_browse(), _TC + ":open_file_dialog",
        (".icc", ".icm", ".mpp"), closed=_precond_off, prepare=_precond_on,
        accent=_tab_accent),
    # -- Measure, IMPORT (R57) -------------------------------------------------------
    Row("measure-import", _measure_tab, _cls(_TM, "TabMeasure"),
        "_use_import_file", lambda w: w._import_file_lbl,
        lambda w: w._on_import_browse(), _TM + ":open_file_dialog",
        (".mxf", ".cxf", ".txt", ".ti3"), bad=".ti2",
        closed=lambda w: w._import_browse_btn.setEnabled(False),
        prepare=_show_import, accent=_tab_accent),
    # -- Check & Refine (R58-R60) --------------------------------------------------
    Row("check-refine-measurement", _check_tab, _cls(_TCR, "TabCheckRefine"),
        "_use_ti3", lambda w: w._ti3_edit, lambda w: w._on_browse_ti3(),
        _TCR + ":open_file_dialog", (".ti3",), accent=_tab_accent),
    Row("check-refine-profile", _check_tab, _cls(_TCR, "TabCheckRefine"),
        "_use_icc", lambda w: w._icc_edit, lambda w: w._on_browse_icc(),
        _TCR + ":open_file_dialog", (".icc", ".icm"), accent=_tab_accent),
    Row("check-refine-gamut-compare", _check_tab,
        _cls("ui.gamut_panel", "GamutPanel"), "_use_compare",
        lambda w: w._gamut_panel._compare_edit,
        lambda w: w._gamut_panel._on_browse_compare(),
        "ui.gamut_panel:open_file_dialog", (".icc", ".icm"),
        accent=_mod_const("ui.gamut_panel", "_ACCENT")),
    # -- Build Profile (R61-R66) ----------------------------------------------------
    Row("build-profile-measurement", _profile_tab, _cls(_TP, "TabProfile"),
        "_use_measurement", lambda w: w._file_lbl,
        lambda w: w._on_load_ti3(), _TP + ":open_file_dialog",
        (".ti3", ".txt", ".mxf", ".cxf"), bad=".ti2",
        closed=_grey_load_icon, accent=_tab_accent),
    Row("build-profile-previous-cal", _profile_tab, _cls(_TP, "TabProfile"),
        "_pc_use_prev", lambda w: w._pc_prev_edit,
        lambda w: w._pc_browse_prev(), _TP + ":open_file_dialog", (".cal",),
        editable=lambda w: w._pc_prev_edit, accent=_tab_accent),
    Row("build-profile-apply-cal-file", _profile_tab, _cls(_TP, "TabProfile"),
        "_ac_use_cal", lambda w: w._ac_cal_edit,
        lambda w: w._ac_browse_cal(), _TP + ":open_file_dialog", (".cal",),
        editable=lambda w: w._ac_cal_edit, accent=_tab_accent),
    Row("build-profile-apply-cal-input", _profile_tab,
        _cls(_TP, "TabProfile"), "_ac_use_in", lambda w: w._ac_in_edit,
        lambda w: w._ac_browse_in(), _TP + ":open_file_dialog",
        (".icc", ".icm"), editable=lambda w: w._ac_in_edit,
        accent=_tab_accent),
    Row("build-profile-gamut-source-guided", _profile_tab,
        _cls(_TP, "TabProfile"), "_use_gam", lambda w: w._gam_path_edit,
        lambda w: w._browse_gam(), _TP + ":open_file_dialog",
        (".icc", ".icm"),
        closed=lambda w: w._gam_path_browse.setEnabled(False),
        prepare=lambda w: w._gam_path_browse.setEnabled(True),
        accent=_tab_accent),
    Row("build-profile-gamut-source-manual", _profile_tab,
        _cls(_TP, "TabProfile"), "_use_m_gam", lambda w: w._m_gam_path_edit,
        lambda w: w._browse_m_gam(), _TP + ":open_file_dialog",
        (".icc", ".icm"),
        closed=lambda w: w._m_gam_path_browse.setEnabled(False),
        prepare=lambda w: w._m_gam_path_browse.setEnabled(True),
        accent=_tab_accent),
    # -- parameters.yaml file rows (R67) ----------------------------------------------
    Row("parameter-file-row-targen-precond", _chart_tab,
        _cls("ui.parameter_widget", "ParameterWidget"), "_use_file",
        lambda w: _param_row("-c")(w)._control,
        lambda w: _param_row("-c")(w)._browse(),
        "ui.parameter_widget:open_file_dialog", (".icc", ".icm"),
        closed=_disable_param("-c"), prepare=_manual_and(_enable_param("-c")),
        editable=lambda w: _param_row("-c")(w)._control,
        accent=_tab_accent),
    Row("parameter-file-row-printtarg-cal", _chart_tab,
        _cls("ui.parameter_widget", "ParameterWidget"), "_use_file",
        lambda w: _param_row("-K")(w)._control,
        lambda w: _param_row("-K")(w)._browse(),
        "ui.parameter_widget:open_file_dialog", (".cal",),
        closed=_disable_param("-K"), prepare=_manual_and(_enable_param("-K")),
        editable=lambda w: _param_row("-K")(w)._control,
        accent=_tab_accent),
    # -- Layout options panel (R68-R69) -------------------------------------------------
    Row("layout-panel-clip-image", _chart_tab,
        _cls("ui.dialogs.layout_options_panel", "LayoutOptionsPanel"),
        "_use_clip_image", lambda w: _layout_panel(w).clip_image_path,
        lambda w: _layout_panel(w)._browse_clip_image(),
        "ui.widgets:open_file_dialog", (".png", ".jpg", ".tif"),
        closed=lambda w: _layout_panel(w).clip_image_browse.setEnabled(False),
        prepare=lambda w: _layout_panel(w).clip_image_browse.setEnabled(True),
        editable=lambda w: _layout_panel(w).clip_image_path,
        accent=_tab_accent),
]


def _layout_panel(w):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panels = w.findChildren(LayoutOptionsPanel)
    assert panels, "no layout options panel"
    return panels[0]


# ---------------------------------------------------------------------------
# the harness
# ---------------------------------------------------------------------------

def _norm(arg):
    if isinstance(arg, (list, tuple)):
        return [Path(a) for a in arg]
    return Path(arg)


class _Recorder:
    def __init__(self):
        self.calls: list = []

    def make(self):
        calls = self.calls

        def handler(self_, *args, **_kw):
            calls.append(_norm(args[0]) if args else None)
        return handler


def _files(tmp_path, row, n=1, *, kind=None):
    out = []
    for i in range(n):
        suf = kind or row.good[i % len(row.good)]
        p = tmp_path / f"drop {i} äö{suf}"
        p.write_text("x\n", encoding="utf-8")
        out.append(p)
    return out


def _open(row, monkeypatch, qapp):
    rec = _Recorder()
    monkeypatch.setattr(row.owner(), row.handler, rec.make())
    win = row.build(_Settings())
    win.resize(900, 900)
    win.show()
    _pump(qapp)
    if row.prepare is not None:
        row.prepare(win)
        _pump(qapp)
    return win, rec


def _choose_with_browse(row, monkeypatch, value):
    mod, attr = row.dialog.split(":")
    import importlib
    monkeypatch.setattr(importlib.import_module(mod), attr,
                        lambda *a, **k: value)


@pytest.mark.parametrize("row", ROWS, ids=[r.id for r in ROWS])
def test_a_dropped_file_reaches_what_browse_reaches(row, qapp, tmp_path,
                                                    monkeypatch):
    win, rec = _open(row, monkeypatch, qapp)
    try:
        if row.folder:
            good = [tmp_path / "a folder äö"]
            good[0].mkdir()
        else:
            good = _files(tmp_path, row, 2 if row.several else 1)
        chosen = ([str(p) for p in good] if row.several else str(good[0]))
        _choose_with_browse(row, monkeypatch, chosen)
        if row.browse is None:
            # Browse and the drop share the step after the chooser in a
            # method of their own; the drop is pinned to reach it with the
            # file, Browse is pinned by `test_the_scan_row_*` below.
            by_browse = _norm(chosen)
        else:
            row.browse(win)
            assert rec.calls, "Browse did not reach the handler"
            by_browse = rec.calls[-1]
        rec.calls.clear()
        field = row.drop_on(win)
        before = field.text() if isinstance(field, QLineEdit) else None
        assert drag_to(qapp, field, _mime(*good, text="file://" + str(good[0])))
        assert rec.calls == [by_browse]
        if before is not None:
            assert "file://" not in field.text()
    finally:
        win.close()
        win.deleteLater()


@pytest.mark.parametrize("row", ROWS, ids=[r.id for r in ROWS])
def test_a_file_of_another_kind_is_not_accepted(row, qapp, tmp_path,
                                                monkeypatch):
    win, rec = _open(row, monkeypatch, qapp)
    try:
        field = row.drop_on(win)
        before = field.text() if isinstance(field, QLineEdit) else None
        if row.folder:
            wrong = _files(tmp_path, row, kind=".ti3")
        else:
            wrong = _files(tmp_path, row, kind=row.bad)
        folder = tmp_path / "a folder"
        folder.mkdir()
        for mime in (_mime(*wrong), _mime(*wrong, text=str(wrong[0])),
                     *(() if row.folder else (_mime(folder),))):
            assert not drag_to(qapp, field, mime)
        assert rec.calls == []
        if before is not None:
            assert field.text() == before
    finally:
        win.close()
        win.deleteLater()


@pytest.mark.parametrize("row", [r for r in ROWS if r.closed],
                         ids=[r.id for r in ROWS if r.closed])
def test_a_greyed_or_busy_row_accepts_nothing(row, qapp, tmp_path,
                                              monkeypatch):
    win, rec = _open(row, monkeypatch, qapp)
    try:
        row.closed(win)
        _pump(qapp)
        if row.folder:
            good = [tmp_path / "f"]
            good[0].mkdir()
        else:
            good = _files(tmp_path, row)
        field = row.drop_on(win)
        assert not drag_to(qapp, field, _mime(*good))
        assert rec.calls == []
    finally:
        win.close()
        win.deleteLater()


@pytest.mark.parametrize("row", [r for r in ROWS if r.editable],
                         ids=[r.id for r in ROWS if r.editable])
def test_plain_text_still_drops_into_an_editable_field(row, qapp,
                                                       monkeypatch):
    win, rec = _open(row, monkeypatch, qapp)
    try:
        edit = row.editable(win)
        drag_to(qapp, edit, _mime(text="typed by hand"))
        text = (edit.toPlainText() if hasattr(edit, "toPlainText")
                else edit.text())
        assert "typed by hand" in text
        assert rec.calls == []
    finally:
        win.close()
        win.deleteLater()


def _drop_of(w):
    """The drop zone or drop target that owns the row *w* sits in."""
    from PyQt6.QtCore import Qt as _Qt
    from ui.file_drop import FileDropZone, _Drops
    while w is not None:
        if isinstance(w, FileDropZone):
            return w._drops
        for d in w.findChildren(
                _Drops, options=_Qt.FindChildOption.FindDirectChildrenOnly):
            return d
        w = w.parentWidget()
    raise AssertionError("no drop zone around the row")


@pytest.mark.parametrize("appearance", ["light", "dark", "neutral"])
@pytest.mark.parametrize("row", ROWS, ids=[r.id for r in ROWS])
def test_the_highlight_is_the_accent_of_its_own_window(row, appearance, qapp,
                                                       tmp_path, monkeypatch):
    """The owner, 2026-11-12: the frame always matches the accent of the
    tool or tab it is in. Compared with what the window's own accent
    elements are painted from, through the same `accent_for`, for the
    appearance on screen at the moment of the drag."""
    from ui import theme
    win, _rec = _open(row, monkeypatch, qapp)
    try:
        monkeypatch.setattr(theme, "active_mode", lambda *a: appearance)
        a = row.accent(win)
        want = (a(appearance) if callable(a)
                else theme.accent_for(a, appearance)).lower()
        drops = _drop_of(row.drop_on(win))
        assert drops.highlight_colour().lower() == want
        if row.folder:
            good = [tmp_path / "f"]
            good[0].mkdir()
        else:
            good = _files(tmp_path, row)
        assert drag_to(qapp, row.drop_on(win), _mime(*good), drop=False)
        assert drops._overlay.colour.lower() == want
    finally:
        win.close()
        win.deleteLater()


# ---------------------------------------------------------------------------
# the rows the inventory SKIPS take no file
# ---------------------------------------------------------------------------

def _print_tab(_s):
    from ui.tabs.tab_print import TabPrint
    return TabPrint(_tab_settings())


def _masthead(_s):
    from ui.masthead_header import MastheadHeader
    return MastheadHeader(None, "test")


SKIPPED = [
    # (id, build, the widget a file would be dropped on, a kind Browse offers)
    ("R30 scanner byo .cht pages", _scanner, lambda w: w._byo_field, ".cht"),
    ("R40 soft-proof colour space combo", _softproof,
     lambda w: w._source_combo, ".icc"),
    ("R53 Create Chart Load patch set icon", _chart_tab,
     lambda w: w._load_ti1_btn, ".ti1"),
    ("R54 masthead Open Project", _masthead,
     lambda w: w._load_project_btn, ".json"),
    ("R55 masthead Open Chart File", _masthead,
     lambda w: w._load_ti2_btn, ".ti2"),
    ("R56 Print Chart Load image", _print_tab,
     lambda w: w._load_image_btn, ".tif"),
    ("R56 Print Chart preview", _print_tab, lambda w: w._preview, ".tif"),
]


@pytest.mark.parametrize("rid, build, target, kind", SKIPPED,
                         ids=[r[0] for r in SKIPPED])
def test_a_skipped_row_takes_no_file(rid, build, target, kind, qapp,
                                     tmp_path):
    win = build(_Settings())
    win.resize(900, 900)
    win.show()
    _pump(qapp)
    try:
        f = tmp_path / f"a file{kind}"
        f.write_text("x\n", encoding="utf-8")
        w = target(win)
        with pytest.raises(AssertionError):
            _drop_of(w)            # no drop zone or drop target around it
        assert not drag_to(qapp, w, _mime(f))
    finally:
        win.close()
        win.deleteLater()


@pytest.mark.parametrize("path, cls", [
    ("ui/tabs/tab_chart.py", "TabChart"),
    ("ui/tabs/tab_print.py", "TabPrint"),
    ("ui/tabs/tab_measure.py", "TabMeasure"),
    ("ui/tabs/tab_profile.py", "TabProfile"),
    ("ui/tabs/tab_check_refine.py", "TabCheckRefine")])
def test_a_tabs_drop_accent_is_its_header_hue(path, cls):
    """TAB_ACCENT, which a drop frame on the tab takes, is the hue the tab
    hands its step header (`test_a_tab_header_keeps_its_hue` reads it)."""
    import importlib
    from tests.test_a_tab_header_keeps_its_hue import ROOT, _accent_argument
    mod = importlib.import_module(path[:-3].replace("/", "."))
    hue = _accent_argument((ROOT / path).read_text(encoding="utf-8"))
    assert f'"{getattr(mod, cls).TAB_ACCENT}"' == hue
