"""Capture ChromIQ documentation screenshots from the real, running app.

Runs ON-SCREEN because the 3D gamut viewer is a QWebEngineView whose WebGL
canvas does not composite into an offscreen ``widget.grab()``. The window is
shown **frameless at full display size** so each grab is genuinely edge-to-edge
— no title bar, no menu bar — i.e. true full screen.

The script is autonomous: it opens the window, seeds every tab with sample data,
runs a real ``profcheck`` analysis and the 3D gamut render so the panels show
*actual results*, then walks a list of scenes (set state → wait → grab → save)
in **both dark and light** themes, and quits on its own.

Screenshots are taken from a **real** project under ``~/ChromIQ`` (a genuine
i1Pro chart with real ``chartread`` measurements and a real ``colprof``
profile), so the app treats it as a native project. Any file-load dialog is
monkeypatched to a no-op pass-through for the duration of the run, so no modal
can ever freeze the capture.

Usage:
    source .venv/bin/activate
    python scripts/capture_screens.py            # all scenes, both themes
    python scripts/capture_screens.py measure    # only scenes matching "measure"
"""
from __future__ import annotations

import pathlib

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication
import PyQt6.QtWebEngineWidgets  # noqa: F401  (must precede QApplication)

from core.resource_path import resource_path
from core.settings import AppSettings
from ui.styles import WinButtonLayoutStyle
from ui.theme import apply_appearance
from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter
from ui.main_window import MainWindow

HOME_PROJECTS = Path.home() / "ChromIQ"
DOCS = ROOT / "docs"
# Where the capture stages its disposable copy of the sample project. A real,
# readable folder rather than a temp dir, because tabs print their paths on
# screen. Created and removed by the run; never the user's own ChromIQ folder.
STAGING_ROOT = Path.home() / "ChromIQ-docs"
# Real project: a genuine i1Pro chart with real chartread measurements + a real
# colprof profile (dropped in under the project stem). No synthetic sample.
A_DIR = HOME_PROJECTS / "Canon-Pro300-CanonSG-i1Pro"
A = A_DIR / "Canon-Pro300-CanonSG-i1Pro"

A_TIF = sorted(A_DIR.glob("*.tif"))
A_TI2 = A.with_suffix(".ti2")

_ENGINE: dict = {}


def engine_preview() -> dict:
    """The layout-engine i1Pro chart WITH the clip-border notes band.

    After `stage_the_project()` this IS the run's own chart, so Create, Print
    and Measure all show the same sheet. It used to be a second chart built
    alongside the run's, which is why the Create tab showed one chart while
    Print and Measure showed another. Cached; falls back to building a separate
    preview, and finally to the project chart, if anything goes wrong.
    """
    if _ENGINE:
        return _ENGINE
    run1 = A_DIR / "runs" / "run1"
    tifs = sorted(run1.glob(f"{A.name}*.tif"))
    ti2 = (run1 / A.name).with_suffix(".ti2")
    if tifs and ti2.exists():
        _ENGINE["tif"], _ENGINE["ti2"] = tifs, ti2
        return _ENGINE
    try:
        import shutil
        import subprocess
        from workflow.layout_engine import chart as le_chart
        stem = A_DIR / "runs" / "run1" / "engine-preview"
        ti1 = stem.with_suffix(".ti1")
        # The project's own .ti1 is only 210 patches — too few to fill an i1Pro A4.
        # Make a fresh ~500-patch set so the strips fill the whole page.
        if not ti1.exists():
            targen = shutil.which("targen") or "/opt/homebrew/bin/targen"
            subprocess.run([targen, "-d2", "-e4", "-f500", str(stem)],
                           check=True, capture_output=True)
        res = le_chart.build_chart(
            str(ti1), stem, instrument="i1", paper="A4", dpi=200,
            randomize=True, clip_content_mode="notes",
            clip_text="Canon PRO-300  ·  Canon SG  ·  i1Pro")
        _ENGINE["tif"] = res.tiff_paths
        _ENGINE["ti2"] = res.ti2_path
    except Exception as e:  # noqa: BLE001
        log(f"engine preview build failed, using project chart: {e}")
        _ENGINE["tif"] = A_TIF
        _ENGINE["ti2"] = A_TI2
    return _ENGINE
A_TI3 = A.with_suffix(".ti3")
A_ICC = A.with_suffix(".icc")
# Compare profile for the gamut-compare shot: ArgyllCMS's ClayRGB1998 (AdobeRGB)
# reference, so the two gamut meshes visibly differ from the printer profile.
B_ICC = Path("/Applications/Argyll/ref/ClayRGB1998.icm")
A_NAME = "Canon-Pro300 CanonSG i1Pro"

THEMES = ("dark", "light")

# Filled by run_real_analysis() with the exact args profcheck's result dialog was
# called with, so capture_dialogs() can replay it as a screenshot.
_QUALITY_ARGS: dict = {}


def log(msg: str) -> None:
    print(f"[capture] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Neutralise the file-load dialogs so nothing can freeze the headless run.
# resolve_ti2 / resolve_ti3 normally pop a modal ("Copy Chart Files" /
# "Load Test Session"); here we pass the path straight through.
# ---------------------------------------------------------------------------
def patch_loaders() -> None:
    import ui.ti2_loader as tl

    def _resolve_ti2(parent, ti2_path, settings):
        from ui.ti2_loader import _related_files
        _ti1, tiffs = _related_files(Path(ti2_path))
        return Path(ti2_path), tiffs

    def _resolve_ti3(parent, ti3_path, settings):
        return Path(ti3_path)

    tl.resolve_ti2 = _resolve_ti2
    tl.resolve_ti3 = _resolve_ti3


def build_app():
    app = QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))
    return app


def set_theme(app, win, mode: str) -> None:
    win._settings.set("appearance", mode)
    apply_appearance(app, win, mode)


def tabs(win):
    return {
        "chart": win._tab_chart,
        "print": win._tab_print,
        "measure": win._tab_measure,
        "profile": win._tab_profile,
        "check": win._tab_check,
    }


def show_tab(win, key: str) -> None:
    idx = {"chart": 0, "print": 1, "measure": 2, "profile": 3, "check": 4}[key]
    win._tabs.setCurrentIndex(idx)


def pump(ms: int) -> None:
    """Spin the event loop for ~ms so async work (profcheck, WebGL) progresses.
    Also flush DeferredDelete events — plain processEvents() doesn't, so widgets
    cleared via deleteLater() (e.g. the old printer-options box on a printer
    switch) would otherwise stay painted behind the rebuilt rows in a grab."""
    import time
    from PyQt6.QtCore import QEvent
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.02)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def stage_the_project(settings) -> bool:
    """Copy the sample project somewhere disposable and give it a modern chart.

    TWO REASONS, and the first is not negotiable: this script opens a REAL
    project of the user's under ~/ChromIQ, and giving that run a freshly built
    chart would overwrite files he owns. The project is copied to a temp root
    and `custom_output_path` is pointed at it, so every write the capture makes
    lands on the copy.

    The second is what the pictures show. The project's own chart is an
    old-engine printtarg sheet, so the Create scenes used to paint a different
    chart from the Print and Measure scenes — Basti caught both halves of that
    on 2026-08-08 ("in print chart and measure tab the chart looks nice but in
    create chart it is a different chart"). Building the ChromIQ layout-engine
    chart, with the notes clip border, AS THE RUN'S OWN CHART makes one sheet
    serve every tab, and makes the Create panel's own numbers agree with it:
    the patch count matches the guided estimate instead of reading 484 beside
    "on screen 210", and the engine's margin clamping removes the red
    "left margin below the instrument minimum" banner that the old 6 mm sheet
    tripped.
    """
    import shutil
    import subprocess

    global A_DIR, A, A_TIF, A_TI2, A_TI3, A_ICC

    try:
        # NOT tempfile.mkdtemp(): several tabs SHOW their file path on screen,
        # and a "/var/folders/1b/yjhqw46j5y78ssphpcnfrs1r0000gp/T/…" string in
        # the Chart File box is noise in a documentation shot. A named folder
        # beside the user's own ChromIQ folder reads like the real thing —
        # which it is — and STAGING_ROOT is removed again at the end of the run.
        root = STAGING_ROOT
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        dst = root / A_DIR.name
        shutil.copytree(A_DIR, dst)
    except Exception as e:                       # noqa: BLE001
        log(f"!! could not stage a copy ({e}) — NOT touching the real project")
        return False

    settings.set("custom_output_path", str(root))
    A_DIR, A = dst, dst / A.name
    A_TIF, A_TI2 = sorted(dst.glob("*.tif")), A.with_suffix(".ti2")
    A_TI3, A_ICC = A.with_suffix(".ti3"), A.with_suffix(".icc")
    log(f"project staged at {dst} — the real one is untouched")

    run1 = dst / "runs" / "run1"
    stem = run1 / A.name                          # the RUN'S own chart stem
    try:
        from workflow.layout_engine import chart as le_chart
        ti1 = stem.with_suffix(".ti1")
        # BUILD EXACTLY WHAT THE GUIDED PANEL SAYS IT WOULD BUILD.
        #
        # The panel prints its own recipe on screen ("targen -d2 -G -e4 -B4
        # -g28 · i1 · A4 · 300 dpi · margin 10 mm · patch ×0.95 · clip border
        # on") and estimates 484 patches on one A4 sheet. Approximating it
        # instead put 500 patches over two pages, so the shot read "968
        # estimated" beside "504 on screen". Matching it exactly makes the two
        # columns agree, which is the whole point of the panel.
        #
        # use_instrument_margins clamps each side to the i1Pro's own minimum,
        # which is what clears the red "margin below the instrument minimum"
        # banner rather than hiding it.
        targen = shutil.which("targen") or "/opt/homebrew/bin/targen"
        subprocess.run([targen, "-d2", "-G", "-e4", "-B4", "-g28", "-f484",
                        str(stem)],
                       check=True, capture_output=True, timeout=300)
        for leftover in run1.glob(f"{A.name}*.tif"):
            leftover.unlink()
        le_chart.build_chart(
            str(ti1), stem, instrument="i1", paper="A4", dpi=300,
            randomize=True, pscale=0.95, margins=(26.0, 9.0, 38.0, 19.0),
            use_instrument_margins=True, clip_content_mode="notes",
            clip_text="Canon PRO-300  ·  Canon SG  ·  i1Pro")
        log("run chart rebuilt with the layout engine + notes clip border")
        return True
    except Exception as e:                        # noqa: BLE001
        log(f"engine chart build failed ({e}) — falling back to the copied chart")
        return True


def open_the_project(win, settings) -> bool:
    """Open the sample project the way the app itself does, before seeding.

    WITHOUT THIS EVERY SCREENSHOT SHOWS THE APP WITH NOTHING OPEN. `seed()`
    pushes files straight into each tab's widgets, which paints a chart preview
    and a profile — but the run bar never learns of a project, so it sits at
    "Profile run: New run" with Run type greyed out, and the masthead prints its
    "Load a profile project…" instruction across the top of all 34 shots. For
    4.0.0, whose headline is that every run keeps its own chart, measurement and
    settings, that is the one feature the pictures had switched off.

    It also produced a self-contradicting frame that Basti caught on
    2026-08-08: the Create Chart tab showed a chart preview with
    "No chart for this profile run yet … its files may have been moved or
    deleted" printed directly underneath. The caption was right — no run was
    open — and the preview was the seeding talking past it. A documentation
    screenshot must never imply the user's files went missing.

    `set_target_name()` alone is not enough: it points the FileManager at the
    folder but tells the run bar nothing. `_restore_last_session()` is the app's
    own path, and it keys off ``session_target_name``, not ``target_name``.
    """
    settings.set("session_target_name", A_DIR.name)
    settings.set("session_project_root", "")
    try:
        win._restore_last_session()
    except Exception as e:                      # never let this stop a capture
        log(f"open project: {e}")
        return False
    pump(900)
    try:
        run = win._target_bar._run_combo.currentText().strip()
    except Exception as e:
        log(f"open project (bar check): {e}")
        return False
    if not run or run.lower().startswith("new run"):
        log(f"  !! run bar still reads {run!r} — shots will show no project open")
        return False
    log(f"project open — Profile run = {run!r}")
    return True


def seed(win, project_is_open: bool = False) -> None:
    t = tabs(win)
    try:
        t["chart"]._target_name_edit.setText(A_NAME)
        t["chart"]._manual_target_name_edit.setText(A_NAME)
        # LET AN OPEN RUN SHOW ITS OWN CHART.
        #
        # Forcing engine-preview in on top of an opened project puts two
        # different charts in one frame: the left panel counted the guided
        # settings (484 patches) while the right read the pixels it was handed
        # (210), and the engine-preview layout tripped a red "left margin below
        # the instrument minimum" warning across a documentation shot. The run
        # already has a chart; showing it is both truthful and self-consistent.
        if not project_is_open:
            t["chart"]._preview.load_tiff(engine_preview()["tif"])
    except Exception as e:
        log(f"chart seed: {e}")
    try:
        t["print"].load_tiffs(list(engine_preview()["tif"]))
        t["print"].set_ti2_path(engine_preview()["ti2"])
    except Exception as e:
        log(f"print seed: {e}")
    try:
        t["measure"].set_ti1_path(engine_preview()["ti2"])
    except Exception as e:
        log(f"measure seed: {e}")
    try:
        t["profile"].set_ti3_path(A_TI3, propagate=False)
        t["profile"].set_icc_path(A_ICC)
    except Exception as e:
        log(f"profile seed: {e}")
    try:
        t["check"].set_paths(A_TI3, A_ICC, propagate=False)
    except Exception as e:
        log(f"check seed: {e}")


def run_real_analysis(win) -> None:
    """Run profcheck + gamut render so the Check tab shows real results.

    The result dialog is non-modal-ised by patching exec→show via a flag, but
    simpler: we drive the checker directly and skip the dialog by pre-setting
    state, then call the public button handler and suppress its modal.
    """
    check = win._tab_check
    gp = check._gamut_panel
    # 1) profcheck — fill the log + grade. Suppress the modal result dialog, but
    # capture the args it was called with so we can replay it later as a
    # screenshot (see capture_dialogs / the Quality Assessment shot).
    orig_show = check._show_result_dialog

    def _swallow(*a, **k):
        _QUALITY_ARGS["args"] = a
        _QUALITY_ARGS["kwargs"] = k  # keep results in the log; skip the modal
    check._show_result_dialog = _swallow
    try:
        check.set_paths(A_TI3, A_ICC, propagate=False)
        check._on_run()
        # profcheck runs via QProcess; pump until the run finishes.
        for _ in range(400):
            pump(50)
            if not win._runner.is_running:
                break
    except Exception as e:
        log(f"profcheck run: {e}")
    finally:
        check._show_result_dialog = orig_show
    # 2) gamut render (primary)
    try:
        gp.set_icc_path(A_ICC)
        gp._on_run()
        for _ in range(200):
            pump(50)
            if not win._runner.is_running:
                break
        pump(2500)  # let WebGL paint
    except Exception as e:
        log(f"gamut run: {e}")


def prep_compare(win) -> None:
    gp = win._tab_check._gamut_panel
    try:
        gp._compare_path = B_ICC
        gp._compare_edit.setText(str(B_ICC))
        gp._on_run()
        for _ in range(400):
            pump(50)
            if not win._runner.is_running:
                break
        pump(3500)
        # Auto-fit the camera (X3DOM showAll) so the solid is centered, then let
        # it settle — otherwise the mesh can sit off-frame in the grab.
        gp._on_reset_view()
        pump(1200)
    except Exception as e:
        log(f"compare prep: {e}")


def rerender_gamut(win) -> None:
    """Re-run the single-profile gamut render so the WebGL/X3DOM canvas repaints
    in the current theme — a theme switch alone does not redraw it, which left
    the dark-mode 3D view blank."""
    gp = win._tab_check._gamut_panel
    try:
        gp._compare_path = None
        gp._compare_edit.setText("")
        gp.set_icc_path(A_ICC)
        gp._on_run()
        for _ in range(400):
            pump(50)
            if not win._runner.is_running:
                break
        pump(3500)
        # Auto-fit the camera (X3DOM showAll) so the solid is centered, then let
        # it settle — without this the dark-mode render framed mostly background.
        gp._on_reset_view()
        pump(1200)
    except Exception as e:
        log(f"gamut rerender: {e}")


# ---------------------------------------------------------------------------
# Scenes: name → setup(app, win). Each captured in BOTH themes.
# Heavy async prep (analysis, compare) happens once via prep hooks keyed by name.
# ---------------------------------------------------------------------------
def _keep_the_runs_own_chart(win) -> None:
    """Show the chart the open run actually holds, not a second one on top of it.

    The Create scenes used to force `engine_preview()` into the preview even
    when a project was open. That put two different charts in one frame: the
    left panel counted the guided settings while the layout table read the
    pixels it had been handed, so the shot said "484 patches" beside
    "on screen 210", and the engine-preview sheet tripped a red
    "left margin below the instrument minimum" banner across the picture.

    If for any reason no run chart is loaded, fall back to the engine preview
    so the frame is not simply empty.
    """
    ch = win._tab_chart
    tiffs = getattr(ch, "_margin_tiffs", None)
    if tiffs:
        return                                   # the run's chart is already up
    ch._preview.load_tiff(engine_preview()["tif"])


def scene_list():
    def s(name, fn, wait=700, target=lambda w: w):
        return {"name": name, "fn": fn, "wait": wait, "target": target}

    def create_guided(app, win):
        win._tab_chart._switch_mode("guided")
        win._tab_chart._target_name_edit.setText(A_NAME)
        _keep_the_runs_own_chart(win)
        show_tab(win, "chart")

    def create_manual(app, win):
        win._tab_chart._switch_mode("manual")
        win._tab_chart._manual_target_name_edit.setText(A_NAME)
        # Match the sample target's identity (built i1Pro / A4) so the manual
        # panel doesn't show the user's saved instrument/paper.
        try:
            win._tab_chart._manual_instr_pw.set_value("i1")
            win._tab_chart._manual_paper_pw.set_value("A4")
        except Exception as e:
            log(f"manual instr/paper: {e}")
        _keep_the_runs_own_chart(win)
        show_tab(win, "chart")

    def _pick_printer(win):
        # Prefer a native-driver printer matching the project over a driverless
        # one (the shot shouldn't show the Canon G6000 AirPrint queue).
        cb = win._tab_print._printer_combo
        for want in ("Canon_PRO_300_series", "EPSON_ET_8550"):
            idx = cb.findData(want)
            if idx >= 0:
                cb.setCurrentIndex(idx)
                return

    def print_native_dialog(app, win):
        # macOS default: print through the native OS dialog (with the driver's
        # colour controls locked off). This is the path most users see.
        win._settings.set("use_native_print_dialog", True)
        win._tab_print.apply_native_dialog_mode()
        win._tab_print.load_tiffs(list(engine_preview()["tif"]))
        _pick_printer(win)
        pump(1200)
        show_tab(win, "print")

    def print_postscript(app, win):
        # The alternative direct PostScript pipeline (colour management bypassed
        # automatically, no OS dialog).
        win._settings.set("use_native_print_dialog", False)
        win._tab_print.apply_native_dialog_mode()
        win._tab_print.load_tiffs(list(engine_preview()["tif"]))
        _pick_printer(win)
        pump(1200)
        show_tab(win, "print")

    def measure_guided(app, win):
        win._tab_measure._switch_mode("guided")
        win._tab_measure.set_ti1_path(engine_preview()["ti2"])
        show_tab(win, "measure")

    def measure_manual(app, win):
        win._tab_measure._switch_mode("manual")
        win._tab_measure.set_ti1_path(engine_preview()["ti2"])
        show_tab(win, "measure")

    def profile_guided(app, win):
        win._settings.set("calibration_mode", False)
        win._apply_calibration_mode()
        win._tab_profile._switch_mode("guided")
        win._tab_profile.set_ti3_path(A_TI3, propagate=False)
        win._tab_profile.set_icc_path(A_ICC)
        show_tab(win, "profile")

    def profile_manual(app, win):
        win._tab_profile._switch_mode("manual")
        show_tab(win, "profile")

    def cal_create(app, win):
        # Calibration mode adds three sub-modules. Show the one that is unique to
        # it: Create Calibration File (printcal, outer-stack page 1).
        p = win._tab_profile
        win._settings.set("calibration_mode", True)
        win._apply_calibration_mode()      # resets to page 0; switch after
        p.set_ti3_path(A_TI3, propagate=False)
        p._switch_cal_mode(1)
        show_tab(win, "profile")

    def cal_apply(app, win):
        # Apply Calibration (applycal, outer-stack page 2).
        p = win._tab_profile
        win._settings.set("calibration_mode", True)
        win._apply_calibration_mode()
        p._switch_cal_mode(2)
        try:
            p._ac_in_edit.setText(str(A_ICC))
        except Exception as e:
            log(f"cal_apply seed: {e}")
        show_tab(win, "profile")

    def check_results(app, win):
        # Leaving calibration mode here (after the cal scenes) keeps the profile
        # tab back in plain Build-Profile state for later passes/dialogs.
        win._settings.set("calibration_mode", False)
        win._apply_calibration_mode()
        # Results are already computed in prep; just show the tab.
        win._tab_check._switch_mode("guided")
        show_tab(win, "check")

    def check_manual(app, win):
        win._tab_check._switch_mode("manual")
        show_tab(win, "check")

    def gamut_compare(app, win):
        show_tab(win, "check")  # compare prepped beforehand

    return [
        s("01-create-chart-guided", create_guided),
        s("02-create-chart-manual", create_manual),
        s("03-print-chart-native-dialog", print_native_dialog),
        s("04-print-chart-postscript", print_postscript),
        s("05-measure-guided", measure_guided),
        s("06-measure-manual", measure_manual),
        s("07-build-profile-guided", profile_guided),
        s("08-build-profile-manual", profile_manual),
        s("09-calibration-create-file", cal_create),
        s("10-calibration-apply", cal_apply),
        s("11-check-results", check_results, wait=1200),
        s("12-check-manual", check_manual, wait=900),
        s("13-gamut-compare", gamut_compare, wait=1200),
    ]


def grab_save(widget, name: str, theme: str) -> None:
    out = DOCS / f"{name}-{theme}.png"
    pix = widget.grab()
    pix.save(str(out))
    log(f"saved {out.name}  ({pix.width()}x{pix.height()})")


def capture_dialogs(app, win) -> None:
    """Capture the app's result/notification dialogs as screenshots.

    These are normally modal (``dlg.exec()``). We temporarily shadow
    ``QDialog.exec`` so each dialog is shown non-modally, grabbed, and dismissed
    — replaying the *real* dialogs the app builds, in both themes.
    """
    from PyQt6.QtWidgets import QDialog
    from PyQt6.QtGui import QPainter, QColor

    orig_exec = QDialog.exec

    def make_capture(name, theme):
        def fake_exec(self):
            # Composite the dialog over its parent window (with a dim overlay) so
            # the screenshot shows the dialog *in context*, not floating bare.
            self.setModal(False)
            self.show()
            self.raise_()
            pump(700)
            try:
                base = win.grab()
                dlg = self.grab()
                painter = QPainter(base)
                # The real app does NOT dim the window behind a modal, so composite
                # the dialog straight over it. A hairline drop shadow just lifts the
                # dialog off the background without the (inaccurate) dark overlay.
                x = (base.width() - dlg.width()) // 2
                y = (base.height() - dlg.height()) // 2
                for i, a in ((8, 22), (4, 34), (2, 46)):
                    painter.fillRect(x - i, y - i, dlg.width() + 2 * i,
                                     dlg.height() + 2 * i, QColor(0, 0, 0, a))
                painter.drawPixmap(x, y, dlg)
                painter.end()
                out = DOCS / f"{name}-{theme}.png"
                base.save(str(out))
                log(f"saved {out.name}  ({base.width()}x{base.height()})")
            finally:
                self.close()
            return 0
        return fake_exec

    def t_profile_built():
        # cal_mode is off here → the standard 4-button "Profile Built" dialog.
        win._tab_profile._show_build_result_dialog(A_ICC, [])

    def t_quality():
        if "args" in _QUALITY_ARGS:
            win._tab_check._show_result_dialog(
                *_QUALITY_ARGS["args"], **_QUALITY_ARGS["kwargs"]
            )

    def t_measure():
        m = win._tab_measure
        # Neutralise the post-exec side effects (key send + watchdog timer) so a
        # screenshot grab can't kick off chartread control flow.
        m._manager.send_key = lambda *a, **k: None
        m._arm_key_watchdog = lambda *a, **k: None
        m._show_all_stripes_averaging_dialog()

    dialogs = [
        ("15-dialog-profile-built", "profile", t_profile_built),
        ("16-dialog-quality-assessment", "check", t_quality),
        ("17-dialog-measure-stripes", "measure", t_measure),
    ]

    for theme in THEMES:
        set_theme(app, win, theme)
        pump(300)
        for name, tab, trigger in dialogs:
            show_tab(win, tab)
            pump(150)
            QDialog.exec = make_capture(name, theme)
            try:
                trigger()
            except Exception as e:
                log(f"dialog {name} ({theme}): {e}")
            finally:
                QDialog.exec = orig_exec
            pump(150)


def _sandbox_the_settings_store() -> None:
    """Copy the user's settings into a temp INI and work from that instead.

    This script deliberately overrides a dozen preferences — theme, language,
    welcome dialog, instrument, paper — to stage each screenshot. Written to the
    real store, those overrides are simply left behind afterwards.

    That is not hypothetical. On 2026-08-08 the user's live `custom_output_path`
    was found pointing at a deleted pytest sandbox, so ChromIQ could not see any
    of his projects, and `chartread_engine` had been flipped from "chromiq" to
    "argyll" — he had reported the engine "disabling itself" twice before anyone
    joined it up. The test suite is isolated now (tests/conftest.py); a script
    that runs the real app has to do the same for itself.

    The values are COPIED first, so the app still behaves as his does — the
    sandbox is about where writes land, not about starting from defaults.

    Note for macOS: QSettings.setDefaultFormat/setPath cannot do this.
    `QSettings("ChromIQ", "ChromIQ")` resolves to the native plist and ignores
    both, so the redirect has to replace the name `core.settings.QSettings`.
    """
    import tempfile

    from PyQt6.QtCore import QSettings

    import core.settings as _cs

    real = QSettings("ChromIQ", "ChromIQ")
    ini = pathlib.Path(tempfile.mkdtemp(prefix="chromiq-shots-")) / "ChromIQ.ini"
    copy = QSettings(str(ini), QSettings.Format.IniFormat)
    for key in real.allKeys():
        copy.setValue(key, real.value(key))
    copy.sync()

    _cs.QSettings = lambda *_a, **_k: QSettings(str(ini), QSettings.Format.IniFormat)
    log(f"settings sandboxed at {ini} — the real store is not written to")


def main() -> int:
    name_filter = sys.argv[1] if len(sys.argv) > 1 else ""
    DOCS.mkdir(exist_ok=True)
    if not A_TIF or not A_ICC.exists() or not B_ICC.exists():
        log("ERROR: sample projects missing — run scripts/make_sample_projects.sh first")
        return 2

    patch_loaders()
    app = build_app()
    _sandbox_the_settings_store()
    settings = AppSettings()
    settings.set("show_welcome_dialog", False)
    settings.set("calibration_mode", False)
    # The sample target is built/named i1Pro on A4; the guided Create panel reads
    # the instrument/paper from settings, so pin them here (overriding whatever
    # the user happens to have saved) to keep the chart's identity coherent.
    settings.set("chart_instrument", "i1")
    settings.set("chart_paper", "A4")
    stage_the_project(settings)
    apply_appearance(app, None, "dark")
    # Clean marketing shots: the masthead shows APP_VERSION, so drop the
    # "-beta.N" suffix here (MainWindow reads it at construction).
    import core.version as _ver
    _ver.APP_VERSION = _ver.APP_VERSION.split("-")[0]
    win = MainWindow(settings)

    # True full screen: frameless window covering the whole display. widget.grab()
    # renders only the app content, so the result is edge-to-edge with no chrome.
    scr = QApplication.primaryScreen().geometry()
    win.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    win.setGeometry(scr)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(800)

    opened = open_the_project(win, settings)
    seed(win, project_is_open=opened)
    pump(300)
    # Heavy, one-time async work so the Check tab shows REAL analysis output.
    # Skip it on a filtered run that doesn't touch the analysis/dialog output.
    needs_analysis = (not name_filter) or any(
        k in name_filter for k in ("check", "gamut", "dialog")
    )
    if needs_analysis:
        log("running real profcheck + gamut analysis…")
        run_real_analysis(win)

    scenes = scene_list()
    if name_filter:
        scenes = [sc for sc in scenes if name_filter in sc["name"]]

    # Capture every scene in both themes.
    for theme in THEMES:
        set_theme(app, win, theme)
        pump(500)
        for sc in scenes:
            # The 3D gamut WebGL canvas does not repaint on a theme switch, so
            # re-render it per theme: scene 11 (single profile) and scene 13
            # (with the compare profile loaded).
            if sc["name"].startswith("11-"):
                rerender_gamut(win)
            if sc["name"].startswith("13-"):
                prep_compare(win)
            try:
                sc["fn"](app, win)
            except Exception as e:
                log(f"  setup {sc['name']}: {e}")
            pump(sc["wait"])
            try:
                grab_save(sc["target"](win), sc["name"], theme)
            except Exception as e:
                log(f"  grab {sc['name']}: {e}")

    # Settings dialog (its own window) in both themes.
    if (not name_filter) or "preferences" in name_filter:
        from ui.dialogs.settings_dialog import SettingsDialog
        for theme in THEMES:
            set_theme(app, win, theme)
            pump(300)
            dlg = SettingsDialog(win._settings, win)
            dlg.setModal(False)
            dlg.show()
            dlg.raise_()
            pump(900)
            grab_save(dlg, "14-preferences", theme)
            dlg.close()
            pump(200)

    # Result / notification dialogs (Profile Built, Quality Assessment, Measure).
    if (not name_filter) or "dialog" in name_filter:
        log("capturing result dialogs…")
        capture_dialogs(app, win)

    log("done — quitting")
    try:
        win._tab_check.shutdown_webengine()
    except Exception:
        pass
    # Take the staged copy away again. Guarded on the exact folder this script
    # created, so a changed STAGING_ROOT can never delete anything else.
    try:
        import shutil
        if STAGING_ROOT.exists() and STAGING_ROOT.name == "ChromIQ-docs":
            shutil.rmtree(STAGING_ROOT)
            log(f"removed the staged copy at {STAGING_ROOT}")
    except Exception as e:                        # noqa: BLE001
        log(f"could not remove {STAGING_ROOT}: {e}")
    QTimer.singleShot(300, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
