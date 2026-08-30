#!/usr/bin/env python3
"""On-screen gate checks for v4.1.5-beta.3.

Same sandboxing as scripts/drive_49_legend_hover_verify.py: the plist is backed
up and compared, core.settings.QSettings is redirected to a sandbox .ini,
CHROMIQ_PRESETS_DIR and custom_output_path are sandboxed, ~/ChromIQ is never
written.

Pointer-driven results are avoided; where a pointer is unavoidable the widget is
asked to confirm it received the move.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SANDBOX = Path(os.environ.get(
    "CR30_50_SANDBOX",
    "/private/tmp/claude-502/-Users-Basti-develop-ChromIQ/"
    "79c89ec2-11d6-4bdc-93a1-f4dcdc3c108d/scratchpad/sandbox50"))
SANDBOX.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import QSettings, Qt          # noqa: E402
from PyQt6.QtGui import QFontDatabase           # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QLabel,  # noqa: E402
                             QMessageBox)
from core.resource_path import resource_path    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
PLIST_BACKUP = SANDBOX / "plist.backup"
SHOTS = Path.home() / "Desktop" / "cr30-beta3-gate"
WORK = SANDBOX / "ChromIQ"
INI = SANDBOX / "settings.ini"
LOG: list = []


def say(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s); print(s, flush=True)


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.005)


def shot(w, name, note=""):
    SHOTS.mkdir(parents=True, exist_ok=True)
    w.grab().save(str(SHOTS / f"{name}.png"))
    say(f"    saved {name}.png   {note}")


def guard_in():
    if REAL_PLIST.exists():
        shutil.copy2(REAL_PLIST, PLIST_BACKUP)
        h = hashlib.sha256(REAL_PLIST.read_bytes()).hexdigest()[:16]
        say(f"    plist backed up (sha {h})"); return h
    return None


def guard_out(before):
    if before is None:
        return
    if not REAL_PLIST.exists():
        shutil.copy2(PLIST_BACKUP, REAL_PLIST); say("    plist restored"); return
    now = hashlib.sha256(REAL_PLIST.read_bytes()).hexdigest()[:16]
    if now != before:
        shutil.copy2(PLIST_BACKUP, REAL_PLIST)
        say(f"    !! plist CHANGED ({before} -> {now}) -- restored")
    else:
        say(f"    plist untouched (sha {now})")


def make_settings():
    import core.settings as CS
    if not INI.exists() and REAL_PLIST.exists():
        src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
        dst = QSettings(str(INI), QSettings.Format.IniFormat)
        for k in src.allKeys():
            dst.setValue(k, src.value(k))
        dst.sync()
    CS.QSettings = lambda *a, **k: QSettings(str(INI), QSettings.Format.IniFormat)
    s = CS.AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    s.set("custom_output_path", str(WORK))
    s.set("restore_last_session", False)
    s.set("margin_inspector_show", True)
    return s


def labels_in(w):
    return [q.text() for q in w.findChildren(QLabel) if q.text()]


def set_manual_area_first(app, tab, *, left_mm, instr="CR30", shape="hex",
                          cols=26, rows=44, t=6.0, r=2.0, b=1.0):
    tab._user_switch_mode("manual")
    pump(app, 700)
    pnl = tab._manual_layout_panel
    i = pnl.instr.findData(instr)
    if i >= 0:
        pnl.instr.setCurrentIndex(i)
    pump(app, 700)
    j = pnl.mode.findData(shape)
    if j >= 0:
        pnl.mode.setCurrentIndex(j)
    pump(app, 300)
    k = pnl.layout_mode.findData("area_first")
    if k >= 0:
        pnl.layout_mode.setCurrentIndex(k)
    pump(app, 400)
    m = pnl.area_method.findData("by_grid")
    if m >= 0:
        pnl.area_method.setCurrentIndex(m)
    pump(app, 300)
    pnl.area_cols.setValue(cols)
    pnl.area_rows.setValue(rows)
    for key, val in (("l", left_mm), ("t", t), ("r", r), ("b", b)):
        pnl.margins[key].setValue(val)
    pump(app, 800)
    return pnl


def phase_A(app, win, settings):
    """The margin inspector labels, and the row-number warning."""
    say("\nPHASE A - margin inspector labels + the row-number warning")
    settings.set("use_chromiq_layout_engine", True)
    tab = win._tab_chart
    win._tabs.setCurrentWidget(tab)
    pump(app, 800)
    mp = tab._margin_panel
    say("  A1 labels on the panel that mention the first patch:")
    for t in labels_in(mp):
        if "first patch" in t or "patch)" in t:
            say(f"      {t!r}")
    shot(mp, "A1_margin_inspector_labels",
         "the four rows now read '(to first patch)'")

    say("  A2 the warning, across left margins (Basti's chart: CR30 hex, "
        "26x44, T6 R2 B1)")
    for L in (0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 7.5, 8.0, 12.0):
        set_manual_area_first(app, tab, left_mm=L)
        try:
            warns = tab._engine_text_overflow_warnings()
        except Exception as exc:      # noqa: BLE001
            warns = [f"RAISED {type(exc).__name__}: {exc}"]
        rown = [w for w in warns if "row numbers" in w]
        say(f"      L={L:5.1f} mm -> {len(warns)} warning(s); "
            f"row-number warning: {'YES' if rown else 'no '}"
            + (f"   {rown[0][:90]}" if rown else ""))
    say("  A3 …and in PATCH-FIRST, where nothing overflows, at L=1")
    set_manual_area_first(app, tab, left_mm=1.0)
    pnl = tab._manual_layout_panel
    k = pnl.layout_mode.findData("patch_first")
    if k >= 0:
        pnl.layout_mode.setCurrentIndex(k)
    pump(app, 900)
    warns = tab._engine_text_overflow_warnings()
    say(f"      patch-first L=1: {len(warns)} warning(s) "
        f"{'(correct: none)' if not warns else warns}")
    say("  A4 GENERATE the chart so the inspector actually has numbers")
    from ui.tabs.tab_chart import TabChart
    for L, name in ((1.0, "gate-L1"), (5.0, "gate-L5")):
        TabChart._prompt_target_name = lambda self, *a, _n=name, **k: _n
        TabChart._confirm_displacing_results = lambda self, *a, **k: True
        set_manual_area_first(app, tab, left_mm=L)
        tab._target_name_edit.setText(name)
        tab._margin_ti2 = None
        pump(app, 600)
        tab._on_generate()
        for _ in range(400):
            pump(app, 500)
            if getattr(tab, "_margin_ti2", None):
                break
        ok = bool(getattr(tab, "_margin_ti2", None))
        pump(app, 2500)
        say(f"      L={L} built={ok}")
        rows = [t for t in labels_in(mp)]
        say(f"      panel now reads: {rows[:14]}")
        warns = tab._engine_text_overflow_warnings()
        for w in warns:
            say(f"      WARNING SHOWN: {w}")
        shot(mp, f"A4_margin_inspector_L{L:g}",
             f"the panel for a REAL generated chart at left margin {L} mm")
        shot(win, f"A5_window_L{L:g}",
             f"the whole window, area-first CR30 hex 26x44, L={L} mm")
    return None


def phase_B(app, win, settings):
    """9024bdfc -- Patch size / Patch scale in Basic, patch-first only."""
    say("\nPHASE B - Patch size / Patch scale moved to Basic")
    settings.set("use_chromiq_layout_engine", True)
    tab = win._tab_chart
    win._tabs.setCurrentWidget(tab)
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 900)
    pnl = tab._manual_layout_panel

    def state(tag):
        pump(app, 500)
        pf = pnl._patch_fields_w
        af = pnl._area_fields_w
        say(f"      {tag:34s} patch-fields shown={not pf.isHidden()} "
            f"(h={pf.height()})  area-fields shown={not af.isHidden()} "
            f"(h={af.height()})  pscale={pnl.pscale.value()} "
            f"sscale={pnl.sscale.value()} "
            f"patch_x={pnl.patch_x.value()} patch_y={pnl.patch_y.value()}")
        return not pf.isHidden()

    say("  B1 the two modes in Manual")
    for mode in ("patch_first", "area_first", "patch_first"):
        k = pnl.layout_mode.findData(mode)
        if k >= 0:
            pnl.layout_mode.setCurrentIndex(k)
        state(f"layout_mode={mode}")
        if mode == "patch_first":
            shot(pnl, "B1_patch_first_layout_group")
        else:
            shot(pnl, "B2_area_first_layout_group")

    say("  B2 are the rows really inside the BASIC Layout group, not Expert?")
    pf = pnl._patch_fields_w
    chain, w = [], pf
    while w is not None and w is not pnl:
        chain.append(f"{type(w).__name__}({w.title() if hasattr(w, 'title') else ''})")
        w = w.parentWidget()
    say(f"      parent chain of the patch-size container: {' <- '.join(chain)}")

    say("  B3 the defaults on an UNSEEDED panel (the 0.5 trap)")
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    fresh = LayoutOptionsPanel()
    say(f"      fresh panel: pscale={fresh.pscale.value()} "
        f"sscale={fresh.sscale.value()} "
        f"(range {fresh.pscale.minimum()}..{fresh.pscale.maximum()})")
    fresh.deleteLater()

    say("  B4 the round-trip: set a scale, read the recipe, re-apply it")
    k = pnl.layout_mode.findData("patch_first")
    if k >= 0:
        pnl.layout_mode.setCurrentIndex(k)
    pump(app, 500)
    pnl.pscale.setValue(1.4)
    pnl.sscale.setValue(0.8)
    pnl.patch_x.setValue(9.0)
    pnl.patch_y.setValue(11.0)
    pump(app, 600)
    rec = tab._current_layout_recipe()
    say(f"      recipe: pscale={rec.pscale} sscale={rec.sscale} "
        f"patch_w_mm={rec.patch_w_mm} patch_h_mm={rec.patch_h_mm}")
    pnl.pscale.setValue(1.0); pnl.sscale.setValue(1.0)
    pnl.patch_x.setValue(0.0); pnl.patch_y.setValue(0.0)
    pump(app, 400)
    pnl.set_recipe(rec)
    pump(app, 700)
    say(f"      after set_recipe: pscale={pnl.pscale.value()} "
        f"sscale={pnl.sscale.value()} patch_x={pnl.patch_x.value()} "
        f"patch_y={pnl.patch_y.value()}  "
        f"-> {'ROUND-TRIP OK' if abs(pnl.pscale.value()-1.4) < 1e-6 and abs(pnl.sscale.value()-0.8) < 1e-6 and abs(pnl.patch_x.value()-9.0) < 1e-6 else '*** ROUND-TRIP BROKEN ***'}")
    say(f"      …and the rows are still visible: "
        f"{not pnl._patch_fields_w.isHidden()}")

    say("  B5 FROM PROFILE GAMUT -- does the same panel reach it?")
    btn = getattr(tab, "_gamut_btn", None) or getattr(tab, "_profile_btn", None)
    say(f"      third-mode button: {btn.text() if btn else 'NOT FOUND'}")
    for name in ("_user_switch_mode",):
        pass
    try:
        tab._user_switch_mode("gamut")
        pump(app, 1200)
        say(f"      mode now: {getattr(tab, '_current_mode', lambda: '?')()}")
        p2 = getattr(tab, "_manual_layout_panel", None)
        say(f"      same panel object in gamut mode: {p2 is pnl}; "
            f"patch-fields shown={not p2._patch_fields_w.isHidden()}")
        shot(win, "B5_from_profile_gamut_window")
    except Exception as exc:      # noqa: BLE001
        say(f"      could not switch: {type(exc).__name__}: {exc}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--phases", default="A")
    args = ap.parse_args()
    before = guard_in()
    try:
        app = QApplication.instance() or QApplication(sys.argv[:1])
        app.setApplicationName("ChromIQ")
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
        from ui.styles import APP_STYLESHEET
        app.setStyleSheet(APP_STYLESHEET)
        settings = make_settings()
        say(f"    sandbox {SANDBOX}")
        QDialog.exec = lambda self: 1                # type: ignore[assignment]

        def _mb(kind, yes):
            def f(*a, **k):
                say(f"      [dialog {kind}] " +
                    " | ".join(str(x)[:150] for x in a[1:3]))
                return yes
            return staticmethod(f)
        for m in ("warning", "critical", "information"):
            setattr(QMessageBox, m, _mb(m, 0))
        setattr(QMessageBox, "question",
                _mb("question", QMessageBox.StandardButton.Yes))
        from ui.main_window import MainWindow
        win = MainWindow(settings)
        win.resize(1700, 1050)
        win.show(); win.raise_(); win.activateWindow()
        pump(app, 2500)
        g = globals()
        for ch in args.phases.upper():
            fn = g.get(f"phase_{ch}")
            if fn:
                fn(app, win, settings)
        pump(app, 300)
        win.close(); pump(app, 300)
    finally:
        guard_out(before)
        (SANDBOX / "log.txt").write_text("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
