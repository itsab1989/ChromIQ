#!/usr/bin/env python3
"""Challenge 2, target 3: the collapsible margin warnings, driven ON SCREEN.

`4580aedf` gave the "Measured from Preview" panel a clickable header in front
of its red warning paragraph, and remembers the fold in
``margin_warnings_expanded``. Basti, 2026-09-13: *"the red warning text in the
measured from preview section can become quite a lot in some instances. can
this be made collapsible and the app remembers the state it was in so it does
not always take up this much space?"*

This drives the REAL `MainWindow` in a REAL window and asks the six questions
the brief names:

1. does the fold survive a chart REBUILD;
2. does it survive a PRESET change;
3. does it survive an INSTRUMENT change;
4. does it survive a RESTART (phase 2 is a second process on the same .ini);
5. can a green "Margins: OK" ever be hidden by it;
6. does the count read correctly at 1 and at 0.

Every warning count is taken from the app's OWN arguments, by wrapping
`MarginInspectorPanel.update_report` where `TabChart` calls it, so the header
is checked against what the tab passed and not against a re-derivation.

The click is a real `QTest.mouseClick` on the header label, so it goes through
Qt's event delivery into the handler the panel installed.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-c2-fold.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-c2-fold-presets \
        python scripts/drive_182_c2_margin_fold.py --phase 1 --out DIR
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import Qt                                       # noqa: E402
from PyQt6.QtTest import QTest                                    # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox    # noqa: E402

from onscreen_capture import capture_window, session_is_locked    # noqa: E402

CLAIMS: list[dict] = []
SHOTS: list[str] = []


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def claim(name: str, ok: bool, detail: str) -> None:
    CLAIMS.append({"claim": name, "ok": bool(ok), "detail": detail})
    print(f"    [{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def shoot(win, out: Path, name: str) -> None:
    p = out / name
    ok, why = capture_window(win, p)
    SHOTS.append(f"{name}: {'taken' if ok else 'REFUSED - ' + why}")
    print(f"    photo {name}: {'taken' if ok else 'REFUSED - ' + why}",
          flush=True)


_BUILD_N = [0]


def build(app, tab, spy, combo, key, timeout=45.0) -> bool:
    """Load a preset the way a person does and wait for the panel to speak.

    The target NAME is typed first, because the Manual panel will not lay a
    chart out for a nameless target and the auto-preview then never runs, which
    is what the panel is fed from.
    """
    idx = combo.findData(key)
    if idx < 0:
        return False
    _BUILD_N[0] += 1
    if getattr(tab, "_manual_target_name_edit", None) is not None:
        tab._manual_target_name_edit.setText(f"C2Fold{_BUILD_N[0]:03d}")
        pump(app, 200)
    spy.clear()
    tab._margin_ti2 = None
    combo.setCurrentIndex(idx)
    combo.activated.emit(idx)          # the tab listens on `activated`
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        pump(app, 200)
        if getattr(tab, "_margin_ti2", None) and spy:
            pump(app, 600)
            return True
    return False


def run(app, phase: int, out: Path) -> int:
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    from ui.margin_inspector_panel import MarginInspectorPanel
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    from ui.theme import apply_appearance

    settings = AppSettings()
    work = Path(os.environ["CHROMIQ_C2_WORK"])
    work.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    # THE PANEL IS FED BY A PREVIEW, AND THE PREVIEW IS OFF BY DEFAULT.
    # `auto_update_preview` defaults to False, so a preset loaded without it
    # lays nothing out and `_set_margin_chart` is never called: the first run
    # of this driver waited 90 s per preset for a panel that could not speak.
    settings.set("auto_update_preview", True)
    stored_before = settings.is_stored("margin_warnings_expanded")
    value_before = settings.get("margin_warnings_expanded", True)
    print(f"    settings file: {settings._qs.fileName()}", flush=True)
    print(f"    margin_warnings_expanded stored={stored_before} "
          f"value={value_before}", flush=True)

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    spy: dict = {}
    _orig = MarginInspectorPanel.update_report

    def _spy(self, report, violations, **kw):
        spy.clear()
        spy.update({
            "violations": [f"{v.edge} {v.measured_mm:.1f}<{v.threshold_mm:.1f}"
                           for v in violations],
            "thresholds_defined": bool(kw.get("thresholds_defined")),
            "notify": bool(kw.get("notify")),
            "text_warnings": list(kw.get("text_warnings") or []),
            "overlap_warnings": list(kw.get("overlap_warnings") or []),
        })
        return _orig(self, report, violations, **kw)

    MarginInspectorPanel.update_report = _spy          # type: ignore[assignment]

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 1200)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}, "
          f"screen locked: {session_is_locked()}", flush=True)

    panel = tab._margin_panel
    combo = tab._preset_combo

    def state() -> dict:
        return {
            "expanded": panel.warnings_expanded(),
            "header_visible": panel._warn_toggle.isVisible(),
            "header_text": panel._warn_toggle.text(),
            "paragraph_visible": panel._status.isVisible(),
            "paragraph_text": panel.status_message(),
            "count_the_app_passed": (len(spy.get("violations") or [])
                                     + len(spy.get("overlap_warnings") or [])),
            "notify": spy.get("notify"),
            "thresholds_defined": spy.get("thresholds_defined"),
            "text_warnings": len(spy.get("text_warnings") or []),
        }

    # ---------------------------------------------------------------- phase 4
    if phase == 4:
        # WHAT ELSE THE HEADER ANSWERS TO. `MarginInspectorPanel.__init__`
        # installs the handler by assigning over the label's own
        # `mousePressEvent`, which Qt calls for EVERY button, and a QLabel
        # takes no keyboard focus, so this phase measures both.
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText("C2FoldButtons")
        if not tab._manual_engine_check.isChecked():
            tab._manual_engine_check.setChecked(True)
            pump(app, 1200)
        pnl = tab._manual_layout_panel
        if pnl.use_instr_margins.isChecked():
            pnl.use_instr_margins.setChecked(False)
            pump(app, 400)
        for k in ("t", "r", "b", "l"):
            pnl.margins[k].setValue(0.0)
        pump(app, 500)
        spy.clear()
        tab._margin_ti2 = None
        tab._generate_btn.click()
        end = time.monotonic() + 150.0
        while time.monotonic() < end:
            pump(app, 200)
            if getattr(tab, "_margin_ti2", None) and spy:
                pump(app, 1200)
                break
        panel.set_warnings_expanded(True)
        pump(app, 300)
        s = state()
        claim("the header is on screen with a warning to fold",
              s["header_visible"] and s["count_the_app_passed"] >= 1,
              json.dumps(s, ensure_ascii=False))
        before = panel.warnings_expanded()
        QTest.mouseClick(panel._warn_toggle, Qt.MouseButton.RightButton)
        pump(app, 400)
        after_right = panel.warnings_expanded()
        claim("a RIGHT click on the header does not fold it",
              after_right == before,
              f"expanded was {before}, after a right click it is {after_right}."
              " The handler is installed by assigning over the label's "
              "`mousePressEvent`, which Qt calls for every button, so a right "
              "or middle click toggles the paragraph as a left click does.")
        panel.set_warnings_expanded(True)
        pump(app, 200)
        before = panel.warnings_expanded()
        QTest.mouseClick(panel._warn_toggle, Qt.MouseButton.MiddleButton)
        pump(app, 400)
        claim("a MIDDLE click on the header does not fold it",
              panel.warnings_expanded() == before,
              f"expanded was {before}, after a middle click it is "
              f"{panel.warnings_expanded()}")
        claim("the header can be reached from the keyboard",
              panel._warn_toggle.focusPolicy() != Qt.FocusPolicy.NoFocus,
              f"focusPolicy={panel._warn_toggle.focusPolicy().name}, "
              f"accessibleName={panel._warn_toggle.accessibleName()!r}. A "
              "QLabel takes no focus, so the fold is mouse-only.")
        shoot(win, out, "11-header-button-and-keyboard-probe.png")
        win.close()
        pump(app, 400)
        return 0

    # ---------------------------------------------------------------- phase 3
    if phase == 3:
        # THE GREEN VERDICT, WITH THE FOLD SHUT AND NOTHING ELSE TOUCHED.
        # Phases 1 and 2 both tried to reach a clean sheet by typing margins
        # and both landed on a sheet with one notice, in two different ways:
        # phase 1's instrument round-trip left the paper somewhere else, and
        # phase 2's freshly started app defaults to the i1Pro, whose 26 mm clip
        # border the typed 25 mm left margin cannot satisfy. A chart built with
        # the panel's own defaults untouched is what measured clean, so that is
        # what this phase builds: one press of Generate Chart, nothing else.
        claim("the fold is still shut when the app starts",
              panel.warnings_expanded() is False,
              f"warnings_expanded={panel.warnings_expanded()} "
              f"(stored={stored_before}, value={value_before})")
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText("C2FoldGreen")
        pump(app, 400)
        pnl = tab._manual_layout_panel
        # THE MARGIN BOXES ONLY REACH A CHART THE ChromIQ ENGINE LAID OUT.
        # With printtarg driving, raising "Left" from 10 to 30 mm left the
        # measured left margin at 10.0 mm and the same notice on screen, twice
        # in a row, because printtarg's own parameters decide that sheet.
        if not tab._manual_engine_check.isChecked():
            tab._manual_engine_check.setChecked(True)
            pump(app, 1200)
        _EDGE = {"Left": "l", "Right": "r", "Top": "t", "Bottom": "b"}

        def one_build(tag):
            spy.clear()
            tab._margin_ti2 = None
            tab._generate_btn.click()
            end = time.monotonic() + 150.0
            while time.monotonic() < end:
                pump(app, 200)
                if getattr(tab, "_margin_ti2", None) and spy:
                    pump(app, 1200)
                    break
            s = state()
            print(f"    {tag}: {s['count_the_app_passed']} notice(s), "
                  f"violations={spy.get('violations')}, "
                  f"overlaps={len(spy.get('overlap_warnings') or [])}, "
                  f"text={[t[:70] for t in (spy.get('text_warnings') or [])]}",
                  flush=True)
            return s

        # A CLEAN SHEET IS FOUND BY ANSWERING THE PANEL, NOT BY GUESSING.
        # Two earlier attempts typed margins that looked generous and still
        # came back with one notice: whatever the panel names as too small is
        # raised to what it asks for, and the chart is built again.
        g = one_build("defaults untouched")
        for _ in range(4):
            if g["count_the_app_passed"] == 0 and g["text_warnings"] == 0:
                break
            if pnl.use_instr_margins.isChecked():
                pnl.use_instr_margins.setChecked(False)
                pump(app, 400)
            moved = False
            for v in (spy.get("violations") or []):
                edge, rest = v.split(" ", 1)
                need = float(rest.split("<")[1])
                k = _EDGE.get(edge)
                if k and pnl.margins[k].value() < need + 4.0:
                    pnl.margins[k].setValue(min(60.0, need + 4.0))
                    moved = True
            if not moved:
                break
            pump(app, 500)
            g = one_build("after raising the edge the panel named")
        # A TEXT NOTICE ALSO SUPPRESSES THE GREEN LINE, and always has: the
        # panel says so in its own comment ("NO GREEN 'Margins: OK' WHILE A
        # TEXT NOTICE IS LIVE"). It is nothing to do with the fold, but it does
        # have to be cleared before the green line can be seen at all.
        if g["text_warnings"]:
            for mset in ((15.0, 15.0, 15.0, 30.0), (20.0, 20.0, 20.0, 30.0),
                         (10.0, 10.0, 10.0, 28.0), (25.0, 15.0, 15.0, 30.0)):
                if pnl.use_instr_margins.isChecked():
                    pnl.use_instr_margins.setChecked(False)
                    pump(app, 400)
                for k, v in zip(("t", "r", "b", "l"), mset):
                    pnl.margins[k].setValue(float(v))
                pump(app, 500)
                g = one_build(f"clearing the text notice with {mset}")
                if g["count_the_app_passed"] == 0 and g["text_warnings"] == 0:
                    break
        claim("a chart with no warnings can be built at all",
              g["count_the_app_passed"] == 0 and g["text_warnings"] == 0
              and g["thresholds_defined"],
              json.dumps(g, ensure_ascii=False))
        claim("at zero notices the header is gone entirely",
              not g["header_visible"],
              f"header_visible={g['header_visible']}, "
              f"header_text={g['header_text']!r}")
        claim("a green 'Margins: OK' is NOT hidden by a fold left shut",
              g["paragraph_visible"] and "OK" in g["paragraph_text"],
              f"the fold is {'shut' if not g['expanded'] else 'open'} and the "
              f"verdict is "
              f"{'visible' if g['paragraph_visible'] else 'HIDDEN'}: "
              f"{g['paragraph_text']!r}")
        claim("and the fold is STILL shut, so the green line is not the fold "
              "springing open",
              panel.warnings_expanded() is False,
              f"warnings_expanded={panel.warnings_expanded()}, "
              f"stored={settings.get('margin_warnings_expanded')!r}")
        shoot(win, out, "10-green-verdict-with-the-fold-shut.png")
        win.close()
        pump(app, 400)
        return 0

    # ---------------------------------------------------------------- phase 2
    if phase == 2:
        claim("the remembered fold is restored on a RESTART",
              panel.warnings_expanded() is False,
              f"a second process on the same .ini opened with "
              f"warnings_expanded={panel.warnings_expanded()} "
              f"(stored={stored_before}, value={value_before})")
        keys = json.loads(
            (out / "phase1-keys.json").read_text(encoding="utf-8"))
        pnl = tab._manual_layout_panel
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText("C2FoldRestart")
        pump(app, 300)

        def rebuild(margins, tag):
            if pnl.use_instr_margins.isChecked():
                pnl.use_instr_margins.setChecked(False)
                pump(app, 500)
            for k, v in zip(("t", "r", "b", "l"), margins):
                pnl.margins[k].setValue(float(v))
            pump(app, 500)
            spy.clear()
            tab._margin_ti2 = None
            tab._generate_btn.click()
            end = time.monotonic() + 120.0
            while time.monotonic() < end:
                pump(app, 200)
                if getattr(tab, "_margin_ti2", None) and spy:
                    pump(app, 900)
                    break
            s = state()
            print(f"    {tag} {margins}: {s['count_the_app_passed']} notice(s), "
                  f"overlaps={len(spy.get('overlap_warnings') or [])}, "
                  f"violations={spy.get('violations')}", flush=True)
            return s

        s = rebuild(keys["made"]["many"], "many after the restart")
        claim("and the paragraph really is folded after the restart",
              s["count_the_app_passed"] >= 1 and s["header_visible"]
              and not s["paragraph_visible"],
              json.dumps(s, ensure_ascii=False))
        shoot(win, out, "09-still-folded-after-a-restart.png")

        # THE GREEN LINE, WITH THE FOLD STILL SHUT. This is the question the
        # brief asks and the one phase 1 could not answer: its instrument
        # round-trip left the sheet in a different state, so the "green"
        # margins came back with a warning after all. Here the app has just
        # started, the fold is shut from the stored value, and the margins are
        # the ones that measured clean.
        g = rebuild(keys["made"]["green"], "green after the restart")
        claim("at zero notices the header is gone entirely",
              g["count_the_app_passed"] == 0 and not g["header_visible"],
              json.dumps(g, ensure_ascii=False))
        claim("a green 'Margins: OK' is NOT hidden by a fold left shut",
              g["count_the_app_passed"] == 0 and g["paragraph_visible"]
              and "OK" in g["paragraph_text"],
              f"the fold is {'shut' if not g['expanded'] else 'open'} and the "
              f"verdict is "
              f"{'visible' if g['paragraph_visible'] else 'HIDDEN'}: "
              f"{g['paragraph_text']!r}")
        shoot(win, out, "10-green-verdict-with-the-fold-shut.png")
        claim("the fold is still shut, so the green line is not a side effect "
              "of it springing open",
              panel.warnings_expanded() is False,
              f"warnings_expanded={panel.warnings_expanded()}, "
              f"stored value={settings.get('margin_warnings_expanded')!r}")
        win.close()
        pump(app, 400)
        return 0

    # ---------------------------------------------------------------- phase 1
    claim("a fresh settings file has never STORED the fold",
          not stored_before and value_before is True,
          f"stored={stored_before}, value={value_before}: the app follows the "
          "default rather than a written value, which is what a new key on an "
          "existing preferences file has to do")

    # THE THREE CASES ARE MADE, NOT HUNTED FOR. A first attempt scanned the
    # built-in presets for one chart with several warnings, one with exactly
    # one and one that came out green: forty ColorMunki built-ins in a row all
    # produced EXACTLY ONE notice, so the scan found neither of the other two.
    # The four margin boxes on the Manual layout panel reach all three states
    # directly, and they are the real widgets a person types into.
    #
    # AND NOT THROUGH A BUILT-IN PRESET EITHER. The first attempt loaded
    # "TC3.00 by Pharmacist" and drove its margins: the measured Top margin
    # came back as 26.0 mm with the box at 0, at 30, at 35 and at 40, because a
    # bundled-`.ti1` built-in lays its sheet out with printtarg and the layout
    # panel's margins do not reach it. So the chart below is an ordinary
    # Manual one, built by the Generate Chart button with no preset loaded.
    pnl = tab._manual_layout_panel
    base_key = "__chromiq_tc300_builtin__"
    if combo.findData(base_key) < 0:
        base_key = [k for _i, es in BUILTIN_PRESET_GROUPS for (_l, _o, k) in es][0]
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("C2FoldBase")
    pump(app, 300)
    spy.clear()
    tab._margin_ti2 = None
    tab._generate_btn.click()
    _end = time.monotonic() + 120.0
    while time.monotonic() < _end:
        pump(app, 200)
        if getattr(tab, "_margin_ti2", None) and spy:
            pump(app, 900)
            break
    if not spy:
        claim("an ordinary Manual chart lays out at all", False,
              "the Generate Chart button never produced a preview, so nothing "
              "below can be measured")
        win.close()
        return 1

    LONG_TEXT = ("a deliberately long sheet text for the second challenge "
                 "round, long enough that it cannot fit the reserve it is "
                 "given and has to be reported as printing over the patches")

    def set_text(on: bool) -> None:
        if getattr(pnl, "chart_text", None) is None:
            return
        want = LONG_TEXT if on else ""
        if pnl.chart_text.text() != want:
            pnl.chart_text.setText(want)
            pump(app, 300)

    def set_margins(t, r, b, left, tag, longtext=False) -> dict:
        """Type four margins into the REAL spin boxes and PRESS Generate.

        Typing alone was not enough and that is worth writing down: with
        "Auto-update preview" on, four `setValue` calls produced no rebuild at
        all in 45 s, so the panel kept the previous chart's verdict. Pressing
        the button is the path a person uses after typing anyway, and it is
        the one that cannot be missed.
        """
        if getattr(pnl, "use_instr_margins", None) is not None \
                and pnl.use_instr_margins.isChecked():
            pnl.use_instr_margins.setChecked(False)
            pump(app, 500)
        set_text(longtext)
        for k, v in (("t", t), ("r", r), ("b", b), ("l", left)):
            pnl.margins[k].setValue(float(v))
        pump(app, 500)
        got = {k: pnl.margins[k].value() for k in ("t", "r", "b", "l")}
        spy.clear()
        tab._margin_ti2 = None
        tab._generate_btn.click()
        end = time.monotonic() + 90.0
        while time.monotonic() < end:
            pump(app, 200)
            if getattr(tab, "_margin_ti2", None) and spy:
                pump(app, 900)
                break
        s = state()
        print(f"    margins {tag} asked t{t} r{r} b{b} l{left}, boxes {got}: "
              f"{s['count_the_app_passed']} notice(s), "
              f"violations={spy.get('violations')}, "
              f"overlaps={len(spy.get('overlap_warnings') or [])}, "
              f"text={len(spy.get('text_warnings') or [])}, "
              f"thresholds={spy.get('thresholds_defined')}, "
              f"instr_margins={pnl.use_instr_margins.isChecked()}", flush=True)
        return s

    base_state = state()
    print(f"    the plain Manual chart: {base_state['count_the_app_passed']} "
          f"notice(s) {spy.get('violations')}", flush=True)
    made: dict = {}
    for trial in ((0.0, 0.0, 0.0, 0.0), (2.0, 1.0, 1.0, 1.0),
                  (5.0, 2.0, 2.0, 2.0)):
        z = set_margins(*trial, "tight")
        if z["count_the_app_passed"] >= 2 and "many" not in made:
            made["many"] = trial
        if z["count_the_app_passed"] == 1 and "one" not in made:
            made["one"] = trial
        if (z["count_the_app_passed"] == 0 and z["text_warnings"] == 0
                and z["thresholds_defined"] and "green" not in made):
            made["green"] = trial
        if len(made) == 3:
            break
    for trial in ((40.0, 25.0, 25.0, 25.0), (35.0, 20.0, 20.0, 20.0),
                  (33.0, 12.0, 12.0, 12.0)):
        if "green" in made:
            break
        g = set_margins(*trial, "wide")
        if (g["count_the_app_passed"] == 0 and g["text_warnings"] == 0
                and g["thresholds_defined"]):
            made["green"] = trial
        elif g["count_the_app_passed"] == 1 and "one" not in made:
            made["one"] = trial
    for trial in ((33.0, 12.0, 0.0, 12.0), (0.0, 12.0, 12.0, 12.0)):
        if "one" in made:
            break
        o = set_margins(*trial, "one")
        if o["count_the_app_passed"] == 1:
            made["one"] = trial
    if "many" not in made:
        # A SECOND KIND OF NOTICE, so the paragraph really carries two. A
        # margin violation and a text overlap stand side by side in the same
        # red (the panel says so in its own comment), and the overlap is what
        # a long sheet text on a full sheet produces.
        for trial in ((0.0, 0.0, 0.0, 0.0), (2.0, 1.0, 1.0, 1.0),
                      (5.0, 2.0, 2.0, 2.0)):
            t = set_margins(*trial, "tight+longtext", longtext=True)
            if t["count_the_app_passed"] >= 2:
                made["many"] = trial
                made["many_longtext"] = True
                break
    print(f"    made: {made}", flush=True)
    if "many" not in made:
        claim("a chart with two or more warnings can be produced", False,
              f"four margins at zero gave {zero['count_the_app_passed']} "
              "notice(s); the fold cannot be measured on a paragraph with one "
              "line")
        win.close()
        return 1
    (out / "phase1-keys.json").write_text(
        json.dumps({"base": base_key, "made": made}), encoding="utf-8")

    # 1. open, with two or more warnings
    set_margins(*made["many"], "many", longtext=made.get("many_longtext", False))
    s0 = state()
    claim("with warnings present the header appears and the paragraph is open",
          s0["header_visible"] and s0["paragraph_visible"] and s0["expanded"],
          json.dumps(s0, ensure_ascii=False))
    claim("the header counts the NOTICES the app passed",
          str(s0["count_the_app_passed"]) in s0["header_text"],
          f"header {s0['header_text']!r} against "
          f"{s0['count_the_app_passed']} notices")
    shoot(win, out, "02-warnings-open.png")

    # 2. a REAL click on the header
    QTest.mouseClick(panel._warn_toggle, Qt.MouseButton.LeftButton)
    pump(app, 400)
    s1 = state()
    claim("a click folds the paragraph away and leaves the header",
          s1["header_visible"] and not s1["paragraph_visible"]
          and not s1["expanded"],
          json.dumps(s1, ensure_ascii=False))
    claim("the folded header says how to get the text back",
          "click" in s1["header_text"].lower(),
          f"header {s1['header_text']!r}")
    claim("the fold was written to the settings by the click",
          settings.is_stored("margin_warnings_expanded")
          and settings.get("margin_warnings_expanded") is False,
          f"stored={settings.is_stored('margin_warnings_expanded')}, "
          f"value={settings.get('margin_warnings_expanded')!r}")
    shoot(win, out, "03-warnings-folded.png")

    # 3. a chart REBUILD, by pressing the real Generate Chart button
    spy.clear()
    tab._margin_ti2 = None
    tab._generate_btn.click()
    end = time.monotonic() + 90.0
    while time.monotonic() < end:
        pump(app, 200)
        if getattr(tab, "_margin_ti2", None) and spy:
            pump(app, 900)
            break
    s2 = state()
    claim("the fold survives a chart rebuild (the Generate Chart button)",
          not s2["expanded"] and not s2["paragraph_visible"]
          and s2["header_visible"],
          json.dumps(s2, ensure_ascii=False))
    shoot(win, out, "04-still-folded-after-a-rebuild.png")

    # 4. a PRESET change, and an INSTRUMENT change
    build(app, tab, spy, combo, base_key)
    s3 = state()
    claim("the fold survives a preset change",
          not s3["expanded"],
          json.dumps(s3, ensure_ascii=False))
    inst_combo = getattr(tab, "_instr_combo", None)
    if inst_combo is not None and inst_combo.count() > 1:
        before = inst_combo.currentIndex()
        inst_combo.setCurrentIndex((before + 1) % inst_combo.count())
        inst_combo.activated.emit(inst_combo.currentIndex())
        pump(app, 2500)
        s4 = state()
        claim("the fold survives an instrument change",
              not s4["expanded"],
              f"instrument {inst_combo.currentText()!r}: "
              + json.dumps(s4, ensure_ascii=False))
        inst_combo.setCurrentIndex(before)
        inst_combo.activated.emit(before)
        pump(app, 2000)
    else:
        claim("the fold survives an instrument change", False,
              "no instrument combobox found on the Manual panel")

    # 5. the count at ONE
    if "one" in made:
        set_margins(*made["one"], "one")
        s5 = state()
        claim("at one notice the header says '1 warning', not '1 warnings'",
              s5["count_the_app_passed"] == 1
              and "1 warning" in s5["header_text"]
              and "1 warnings" not in s5["header_text"],
              f"header {s5['header_text']!r} for "
              f"{s5['count_the_app_passed']} notice")
        shoot(win, out, "05-one-warning-folded.png")
    else:
        claim("at one notice the header says '1 warning'", False,
              "no built-in preset produced exactly one notice")

    # 6. the count at ZERO, and the green line
    if "green" in made:
        set_margins(*made["green"], "green")
        s6 = state()
        claim("at zero notices the header is gone entirely",
              s6["count_the_app_passed"] == 0 and not s6["header_visible"]
              and "0 warning" not in s6["header_text"],
              json.dumps(s6, ensure_ascii=False))
        claim("a green 'Margins: OK' is NOT hidden by a fold left shut",
              s6["paragraph_visible"] and "OK" in s6["paragraph_text"],
              f"fold is {'shut' if not s6['expanded'] else 'open'} and the "
              f"verdict is {'visible' if s6['paragraph_visible'] else 'HIDDEN'}"
              f": {s6['paragraph_text']!r}")
        shoot(win, out, "06-green-verdict-while-folded.png")
    else:
        claim("a green 'Margins: OK' is not hidden by a fold left shut", False,
              "no margin set produced a green verdict in this run")

    # 7. reopen
    set_margins(*made["many"], "many again",
                longtext=made.get("many_longtext", False))
    QTest.mouseClick(panel._warn_toggle, Qt.MouseButton.LeftButton)
    pump(app, 400)
    s7 = state()
    claim("clicking again brings the paragraph back",
          s7["expanded"] and s7["paragraph_visible"],
          json.dumps(s7, ensure_ascii=False))
    claim("and reopening is written back to the settings",
          settings.get("margin_warnings_expanded") is True,
          f"value={settings.get('margin_warnings_expanded')!r}")
    shoot(win, out, "07-warnings-reopened.png")

    # 8. leave it FOLDED for the restart phase
    QTest.mouseClick(panel._warn_toggle, Qt.MouseButton.LeftButton)
    pump(app, 400)
    claim("left folded for the restart phase",
          panel.warnings_expanded() is False,
          f"value written: {settings.get('margin_warnings_expanded')!r}")
    shoot(win, out, "08-folded-before-the-restart.png")
    settings._qs.sync()
    win.close()
    pump(app, 500)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    rc = run(app, a.phase, out)
    res = out / f"phase{a.phase}-claims.json"
    res.write_text(json.dumps({"claims": CLAIMS, "shots": SHOTS}, indent=1,
                              ensure_ascii=False), encoding="utf-8")
    bad = [c for c in CLAIMS if not c["ok"]]
    print(f"\n    {len(CLAIMS) - len(bad)}/{len(CLAIMS)} claims held; "
          f"{len(bad)} did not", flush=True)
    for c in bad:
        print(f"      FAIL {c['claim']}: {c['detail']}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
