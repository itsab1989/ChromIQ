#!/usr/bin/env python3
"""Photograph the ChromIQ modules that only exist in SOME configuration, or
only WHILE something is happening.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_neutral_states.py <outdir> <mode> [group]

WHY THIS EXISTS. Five sweeps measured the Neutral appearance with
``scripts/find_non_neutral_pixels.py`` against a freshly-opened app in its
default configuration, and the last one reported zero hued pixels app-wide. That
number is true and worthless: a census can only measure what is on screen, and
the owner found six things it had never rendered in under an hour of using the
app. A module that is off by default has never been drawn by anything.

So this driver renders the parts a default launch does not:

* **configs** - the run-type-, preference- and mode-gated modules. The
  from-profile gamut module (#133) exists only in a Verification run; the
  Measure tab's IMPORT module only there too; the AirPrint options box only on
  the ``lp`` pipeline; the Calibration options only with ``calibration_mode``.
* **states**  - what is only on screen while something happens or after it goes
  wrong: the measurement progress bar, the strip-times panel and its verdict,
  the "chart already has a measurement" window, the calibration-finished
  window, a validation error line, the ArgyllCMS-missing status bar.
* **interaction** - hover, focus, pressed, checked, a combo popup's highlighted
  row, and hover on a DISABLED control.

Each group grabs a picture, runs the pixel census over it, AND records the
top-left ground colour, because the pixel census is deliberately blind to a
grey: ``#181818`` and ``#909090`` have chroma 0 and score zero however wrong
they are on a light-grey ground. Read ``ground`` and ``dark_slabs`` in the JSON
as well as ``scan``.

ONE APPEARANCE AND ONE CONFIGURATION PER PROCESS. Several modules read the
appearance at construction time, and several settings are only read as a panel
is built, so switching either under a live window measures a hybrid.

Sandboxed: ``CHROMIQ_SETTINGS_FILE``, ``CHROMIQ_PRESETS_DIR`` and a
``custom_output_path`` written into the .ini BEFORE anything builds an
``AppSettings`` - without the last one a sandboxed settings file still falls
back to the owner's real ``~/ChromIQ``.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/states.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/states-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/states-work"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/states-shots")
MODE = sys.argv[2] if len(sys.argv) > 2 else "neutral"
GROUP = sys.argv[3] if len(sys.argv) > 3 else "all"

SUBJECT = "Demo-Full-RGB"

#: Settings written into the sandbox .ini before AppSettings is built, per
#: group. A key here is a module that does not otherwise exist.
CONFIG: dict[str, dict[str, object]] = {
    # CALIBRATION MODE IS ITS OWN GROUP, and finding out why cost a pass.
    # `TabMeasure.set_calibration_mode` hides the whole Guided/Manual/IMPORT
    # mode row and locks the tab to Manual — so with it on, the IMPORT module
    # is unreachable even in a Verification run, and a driver that sets both at
    # once photographs the box's stylesheet without ever showing the module.
    "configs":     {"use_native_print_dialog": "false",
                    "profile_engine_beta": "true",
                    "chromiq_refinement": "true",
                    "averaging_enabled": "true",
                    "chart_mode": "manual"},
    "cal":         {"calibration_mode": "true"},
    "states":      {},
    "interaction": {},
    # Every appearance-affecting preference the brief names, at once: another
    # language (which changes every string and every width), the two info
    # panels hidden, the log panel hidden, and the ChromIQ layout engine off so
    # the Manual panel shows printtarg's rows instead of the engine's.
    "prefs":       {"language": "de",
                    "layout_info_show": "false",
                    "margin_inspector_show": "false",
                    "hide_log_output": "true",
                    "use_chromiq_layout_engine": "false",
                    "chart_mode": "manual"},
}

WORK.mkdir(parents=True, exist_ok=True)


def _write_ini() -> None:
    lines = [f"custom_output_path={WORK}", f"appearance={MODE}"]
    for k, v in CONFIG.get(GROUP, {}).items():
        lines.append(f"{k}={v}")
    SETTINGS_INI.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_INI.write_text("[General]\n" + "\n".join(lines) + "\n", encoding="utf-8")


_write_ini()

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import QPoint, Qt, QTimer                        # noqa: E402
from PyQt6.QtGui import QFontDatabase, QPixmap                     # noqa: E402
from PyQt6.QtWidgets import (QApplication, QComboBox, QPushButton,  # noqa: E402
                             QWidget)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def sha(pixmap) -> str:
    img = pixmap.toImage()
    b = img.bits()
    b.setsize(img.sizeInBytes())
    return hashlib.sha256(bytes(b)).hexdigest()[:16]


def tree_hash(root: Path) -> "dict[str, str]":
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        out[rel + ("/" if p.is_dir() else "")] = (
            "dir" if p.is_dir() else hashlib.sha1(p.read_bytes()).hexdigest())
    return out


def find_subject() -> "Path | None":
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "chromiq-demo-projects-cache"
    for cand in sorted(cache.glob(f"*/{SUBJECT}")):
        if (cand / "project.json").is_file():
            return cand
    return None


def dark_slabs(pixmap, floor: int = 0x60) -> list:
    """Grey pixels DARKER than *floor*, and how many. The blind spot the pixel
    census cannot see: a perfect grey has chroma 0 and scores zero there
    however wrong it is on a light-grey ground."""
    from collections import Counter
    img = pixmap.toImage()
    counts: Counter = Counter()
    w, h = img.width(), img.height()
    step = max(1, min(w, h) // 400)          # sample; a slab is never 1 px
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = img.pixelColor(x, y)
            if c.alpha() < 8:
                continue
            r, g, b = c.red(), c.green(), c.blue()
            if max(r, g, b) - min(r, g, b) > 6:
                continue                      # a hue: the other census
            if (r + g + b) // 3 < floor:
                counts[c.name()] += 1
    return counts.most_common(6)


class Shots:
    def __init__(self, outdir: Path, mode: str, group: str):
        self.dir = outdir / f"{mode}-{group}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.record: dict[str, object] = {}
        self.scan: list = []

    def take(self, name: str, w, *, census: bool = True,
             keep_focus: bool = False) -> str:
        # DROP THE KEYBOARD FOCUS unless the shot is ABOUT focus. A focused
        # field wears the accent as a 1 px ring, and which widget holds it in an
        # on-screen window is decided by the window manager, not by the code
        # under test - two otherwise identical runs differ by hundreds of border
        # pixels because of it.
        if not isinstance(w, QPixmap) and not keep_focus:
            fw = w.focusWidget()
            if fw is not None:
                fw.clearFocus()
            QApplication.processEvents()
        pm = w if isinstance(w, QPixmap) else w.grab()
        if pm.isNull() or pm.width() <= 0:
            self.record[name] = "ungrabbable"
            print(f"    {name}: UNGRABBABLE", flush=True)
            return ""
        pm.save(str(self.dir / f"{name}.png"))
        h = sha(pm)
        img = pm.toImage()
        slabs = dark_slabs(pm)
        self.record[name] = {
            "sha": h, "size": [pm.width(), pm.height()],
            "ground": img.pixelColor(2, 2).name(),
            "dark_slabs": slabs,
        }
        note = f" DARK={slabs[0][0]}x{slabs[0][1]}" if slabs else ""
        print(f"    {name}: {pm.width()}x{pm.height()} {h} "
              f"ground={img.pixelColor(2, 2).name()}{note}", flush=True)
        # CHROMIQ_SKIP_CENSUS=1 for the Light/Dark hash proof, which needs the
        # grabs and nothing else. The census grabs every descendant widget
        # separately and reads it pixel by pixel — on a 3400x2100 window that is
        # most of the run's wall time, and it cannot change a hash.
        if (census and not isinstance(w, QPixmap)
                and not os.environ.get("CHROMIQ_SKIP_CENSUS")):
            from scripts.find_non_neutral_pixels import scan_widget
            for hit in scan_widget(w, skip=("TiffPreview", "PatchCubePanel",
                                            "GamutPanel", "ScanGridMarquee")):
                self.scan.append({"where": name, "widget": hit.widget,
                                  "objectName": hit.object_name,
                                  "pixels": hit.pixels,
                                  "share": round(hit.share, 2),
                                  "colours": hit.colours[:5], "path": hit.path})
        return h


def main() -> int:   # noqa: PLR0915, PLR0912
    OUT.mkdir(parents=True, exist_ok=True)
    real_root = Path.home() / "ChromIQ"
    before_real = tree_hash(real_root)
    print(f"~/ChromIQ before: {len(before_real)} entries")

    src = find_subject()
    dest = WORK / SUBJECT
    if src is not None:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)          # Project.load migrates IN PLACE
    else:
        print("No cached Demo-Full-RGB; run the test suite once to build it.")

    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
              DialogFocusFilter):
        app.installEventFilter(F(app))

    from core.settings import AppSettings
    settings = AppSettings()
    opened = Path(settings._qs.fileName())
    if opened != SETTINGS_INI:
        raise SystemExit(f"REFUSING TO RUN: settings escaped the sandbox: {opened}")
    if str(settings.get("custom_output_path", "")) != str(WORK):
        raise SystemExit("REFUSING TO RUN: custom_output_path is not the sandbox")
    print(f"settings: {opened}  out={settings.get('custom_output_path')}  "
          f"appearance={settings.get('appearance')}  group={GROUP}")

    # THE LANGUAGE IS SET IN `main()`, NOT BY THE WINDOW, and every string is
    # translated at CONSTRUCTION time (restart-to-apply). A driver that skips
    # this builds an English tree from a German .ini and reports that the
    # German layout is fine.
    from core.i18n import install_qt_translator, set_language
    set_language(settings.get("language", "en"))
    install_qt_translator(app)
    print(f"    language: {settings.get('language', 'en')}")

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance

    # SEED THE APPEARANCE BEFORE THE WINDOW IS BUILT, exactly as ``main()``
    # does. Several widgets resolve a colour once, at construction: build first
    # and the tree polishes against the previous appearance, so what is measured
    # is a hybrid of two themes rather than either of them. (That an icon can be
    # born in the wrong appearance at all is itself a finding - see the live
    # appearance-switch checks - but it must not be measured here by accident.)
    apply_appearance(app, None, MODE)
    win = MainWindow(settings)
    apply_appearance(app, win, MODE)
    win.resize(1700, 1050)
    win.show()
    if ONSCREEN:
        win.raise_()
        win.activateWindow()
    pump(app, 1500)

    # ANSWER OUR OWN MODALS, from inside the event loop. A modal that blocks the
    # driver gets clicked by the owner, and everything after that point is
    # human-assisted rather than proof. Every window this closes is recorded by
    # title with the button that was pressed.
    dismissed: list[str] = []

    def _dismiss_modal() -> None:
        m = app.activeModalWidget()
        if m is not None and m.isVisible():
            dismissed.append(f"{m.windowTitle() or type(m).__name__} -> reject")
            m.reject()

    wd = QTimer()
    wd.timeout.connect(_dismiss_modal)
    wd.start(400)

    s = Shots(OUT, MODE, GROUP)
    tabs = win._tabs

    if dest.exists():
        win._file_mgr.set_target_name(SUBJECT)
        win._target_bar.refresh()
        pump(app, 1200)
        proj = win._file_mgr.project()
        print("project:", getattr(proj, "root", None),
              "runs", [r.id for r in proj.all_runs()] if proj else [])

    # ------------------------------------------------------------- configs
    if GROUP in ("configs", "cal", "all"):
        print("\n--- CONFIG-GATED MODULES ---")
        from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                             RUN_TYPE_VERIFICATION)
        ctl = getattr(win, "_target_ctl", None)
        want = (RUN_TYPE_CALIBRATION if GROUP == "cal"
                else RUN_TYPE_VERIFICATION)
        if ctl is not None:
            ctl.set_run_type(want)
            pump(app, 1200)
            print(f"    run type -> {ctl.target.run_type}")

        # #133: Create Chart's FROM PROFILE GAMUT module. It is
        # setVisible(False) until the run type is Verification, so nothing that
        # opened the app in its default configuration has ever drawn it.
        tabs.setCurrentIndex(0)
        pump(app, 900)
        tc = win._tab_chart
        gbtn = getattr(tc, "_gamut_btn", None)
        print(f"    gamut button visible: "
              f"{gbtn.isVisible() if gbtn is not None else 'absent'}")
        if gbtn is not None and gbtn.isVisible():
            gbtn.click()
            pump(app, 1200)
            s.take("C30-gamut-module", getattr(tc, "_gamut_container", tc))
            s.take("C31-chart-tab-gamut", win)
        s.take("C32-chart-tab", win)

        # The Measure tab's IMPORT module: `_import_available` is
        # `_is_verification_run()`, so it too exists only here.
        tabs.setCurrentIndex(2)
        pump(app, 1200)
        tm = win._tab_measure
        # REACH THE MODULE, do not just grab the widget that holds its style.
        # IMPORT is the third page of the Measure tab's stack and its button is
        # `setVisible(_import_available())`, i.e. Verification only.
        ibtn = getattr(tm, "_import_btn", None)
        print(f"    import button visible: "
              f"{ibtn.isVisible() if ibtn is not None else 'absent'}")
        if ibtn is not None and ibtn.isVisible():
            ibtn.click()
            pump(app, 1000)
        box = getattr(tm, "_import_box", None)
        if box is not None:
            print(f"    import box visible: {box.isVisible()}")
            s.take("C40-import-box", box)
        s.take("C41-measure-tab", win)

        # The lp pipeline's own controls (use_native_print_dialog=false). The
        # printer combo is filled from a CUPS query that settles on its own
        # schedule, so give it room: a grab taken mid-query differs from one
        # taken after it, and a hash comparison then reports the app's own
        # timing as a regression.
        tabs.setCurrentIndex(1)
        pump(app, 3000)
        s.take("C50-print-tab-lp", win)

        tabs.setCurrentIndex(3)
        pump(app, 1200)
        s.take("C60-profile-tab-engine-beta", win)

        tabs.setCurrentIndex(4)
        pump(app, 1200)
        s.take("C70-check-refine", win)

    # -------------------------------------------------------------- states
    if GROUP in ("states", "all"):
        print("\n--- BUSY / WARNING / ERROR STATES ---")
        tm = win._tab_measure

        # S3 the measurement progress bar. It lives in the preview's header and
        # only ever has a fraction while a chart is being measured.
        tabs.setCurrentIndex(2)
        pump(app, 900)
        pv = getattr(tm, "_preview", None)
        if pv is not None and hasattr(pv, "set_measurement_progress"):
            pv.set_measurement_progress(42.5, tracking=True)
            pump(app, 500)
            hdr = getattr(pv, "_header", None)
            if hdr is not None:
                s.take("S30-progress-bar", hdr)
            s.take("S31-preview-measuring", pv, census=False)

        # S3 the strip-times panel and its verdict, all three bands.
        for tag, verdict, colour in (
                ("fast", "Too fast — read more slowly", "#ff6b6b"),
                ("marginal", "Close to the limit", "#e0a63a"),
                ("good", "Good reading speed", "#5cb85c")):
            try:
                tm._pace_times = {"A": (2.1, tag != "fast"), "B": (3.4, True)}
                tm._pace_patches = 15
                tm._refresh_pace_panel(verdict, colour)
                pump(app, 400)
                grp = getattr(tm, "_pace_group", None)
                if grp is not None:
                    s.take(f"S32-strip-times-{tag}", grp)
            except Exception as exc:            # noqa: BLE001
                print(f"    strip times {tag}: {exc}")

        # S4 the Stop button, disabled - the DEFAULT state of the Measure tab,
        # and a perfect grey, so the hue census has always scored it zero.
        stop = getattr(tm, "_stop_btn", None)
        if stop is not None:
            print(f"    stop button enabled: {stop.isEnabled()}")
            s.take("S40-stop-button-disabled", stop)

        # The ArgyllCMS-missing status bar. warning=True paints a dark slab with
        # amber text across three tabs; on a machine with Argyll installed it
        # has never been on screen.
        win._set_tab_status(
            "⚠  ArgyllCMS not found. Open Preferences (⚙) to set the path.",
            warning=True)
        pump(app, 400)
        for idx, attr, tag in ((0, "_tab_chart", "chart"),
                               (1, "_tab_print", "print"),
                               (2, "_tab_measure", "measure")):
            tabs.setCurrentIndex(idx)
            pump(app, 500)
            lbl = getattr(getattr(win, attr), "_status_bar_lbl", None)
            if lbl is not None and lbl.isVisible():
                s.take(f"S50-argyll-warning-{tag}", lbl)
        win._set_tab_status("")
        pump(app, 300)

        # S9/S10 the two panels that are empty until a preview exists.
        tabs.setCurrentIndex(0)
        pump(app, 700)
        tc = win._tab_chart
        for attr, tag in (("_margin_panel", "margins"),
                          ("_layout_info_panel", "layout-info")):
            p = getattr(tc, attr, None)
            if p is not None:
                s.take(f"S60-{tag}", p)

    # --------------------------------------------------------- interaction
    if GROUP in ("interaction", "all"):
        # ONLY THE STATES THIS ENVIRONMENT CAN ACTUALLY PAINT.
        #
        # `hover_positive_control.py` settles which those are, with a throwaway
        # button whose stylesheet turns it magenta on `:hover`. `:checked`,
        # `:disabled`, `:pressed` and `:focus` all paint 16,179 magenta pixels
        # into a grab; NINE hover techniques paint none — a synthesised
        # QEnterEvent, WA_UnderMouse (which `underMouse()` then reports True),
        # QTest.mouseMove, QHoverEvent, a synchronous repaint(), and a real
        # QCursor.setPos warp that provably lands on the button, with and
        # without the window activated.
        #
        # So a QSS `:hover` is NOT MEASURED HERE and no zero is reported for
        # it. `scripts/audit_interaction_state_rules.py` reads those rules from
        # source instead, which is an instrument that works. What IS measured
        # below is the hover the two popups draw THEMSELVES, from a
        # `_hover_index` attribute — code, not a pseudo-state, and therefore
        # drivable.
        print("\n--- INTERACTION STATES (only the ones that can be painted) ---")
        tabs.setCurrentIndex(0)
        pump(app, 800)
        tc = win._tab_chart

        btn = getattr(tc, "_generate_btn", None)
        if btn is not None:
            s.take("I10-primary-idle", btn)
            btn.setDown(True)
            btn.repaint()
            s.take("I12-primary-pressed", btn)
            btn.setDown(False)
            # :focus needs the WINDOW to be active — `setFocus` alone leaves
            # `hasFocus()` False in an app that is not frontmost, and that is
            # how a focus census reports a zero it never measured.
            app.setActiveWindow(win)
            btn.setFocus(Qt.FocusReason.TabFocusReason)
            btn.repaint()
            s.take("I13-primary-focus", btn, keep_focus=True)
            print(f"    focus really taken: {btn.hasFocus()}")
            btn.clearFocus()
            btn.setEnabled(False)
            btn.repaint()
            s.take("I14-primary-disabled", btn)
            btn.setEnabled(True)

        # The two popups that paint their own hover row, driven through the
        # attribute they paint from.
        from ui.tools_popup import ToolsPopup
        for name, pop in (("tools", ToolsPopup(win)),):
            try:
                # THE POPUP OPENS IN DARK AND IS TOLD ITS APPEARANCE AFTER —
                # `_mode = "dark"` in its __init__, `set_appearance` from the
                # window. A driver that builds one directly and forgets this
                # measures the dark palette and reports it as a Neutral bug.
                if hasattr(pop, "set_appearance"):
                    pop.set_appearance(MODE)
                pop.show()
                pump(app, 400)
                s.take(f"I30-{name}-popup-idle", pop)
                if hasattr(pop, "_hover_index"):
                    pop._hover_index = 1
                    pop.repaint()
                    s.take(f"I31-{name}-popup-hover-row", pop)
                    print(f"    {name} popup hover row driven: "
                          f"{pop._hover_index}")
                    pop._hover_index = -1
                pop.hide()
                pump(app, 200)
            except Exception as exc:              # noqa: BLE001
                print(f"    {name} popup: {exc}")

        # A combo popup's highlighted row - painted by the popup's own view,
        # which is a separate top-level window and is invisible to a grab of
        # the tab it belongs to.
        combos = [c for c in tc.findChildren(QComboBox) if c.isVisible()]
        if combos:
            c = combos[0]
            c.showPopup()
            pump(app, 600)
            view = c.view()
            if view is not None and view.window() is not None:
                if view.model().rowCount() > 1:
                    view.setCurrentIndex(view.model().index(1, 0))
                pump(app, 300)
                s.take("I20-combo-popup", view.window())
            c.hidePopup()
            pump(app, 300)

    # --------------------------------------------------------------- prefs
    if GROUP in ("prefs", "all"):
        print("\n--- APPEARANCE-AFFECTING PREFERENCES ---")
        # The settings are already in the .ini, so the whole tree was BUILT
        # under them - which is the point: several of these are only read as a
        # panel is constructed, and switching one under a live window measures
        # a hybrid.
        for idx, tag in ((0, "chart"), (1, "print"), (2, "measure"),
                         (3, "profile"), (4, "check")):
            tabs.setCurrentIndex(idx)
            pump(app, 1400)
            s.take(f"P10-{tag}", win)
        tc = win._tab_chart
        for attr, tag in (("_margin_panel", "margins"),
                          ("_layout_info_panel", "layout-info")):
            p = getattr(tc, attr, None)
            if p is not None:
                print(f"    {tag} panel visible: {p.isVisible()}")

    # -------------------------------------------------------------- report
    tot = sum(h["pixels"] for h in s.scan)
    print(f"\n  {len(s.scan)} widgets painting a hue, {tot} px")
    for h in sorted(s.scan, key=lambda x: -x["pixels"])[:20]:
        print(f"    {h['where']:>28} {h['widget']}#{h['objectName']}: "
              f"{h['pixels']} px ({h['share']}%) {[c for c, _ in h['colours'][:3]]}")

    slabs = {k: v["dark_slabs"] for k, v in s.record.items()
             if isinstance(v, dict) and v.get("dark_slabs")}
    if slabs:
        print(f"\n  DARK GREY (chroma 0, invisible to the hue census) in "
              f"{len(slabs)} shots:")
        for k, v in slabs.items():
            print(f"    {k}: {v[:3]}")

    (OUT / f"states-{MODE}-{GROUP}.json").write_text(
        json.dumps({"mode": MODE, "group": GROUP, "shots": s.record,
                    "scan": s.scan, "modals": dismissed}, indent=2,
                   sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT / f'states-{MODE}-{GROUP}.json'}")
    print(f"modals answered: {dismissed}")

    win.close()
    pump(app, 500)

    after_real = tree_hash(real_root)
    gained = sorted(set(after_real) - set(before_real))
    print(f"~/ChromIQ after: {len(after_real)} entries; gained {len(gained)}")
    if gained:
        print("LEAKED:", gained[:20])
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
