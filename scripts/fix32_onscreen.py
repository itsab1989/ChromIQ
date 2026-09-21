#!/usr/bin/env python3
"""ON SCREEN: every user-visible sentence the round-32 fix set changed.

Real windows, `onscreen_capture.capture_window` (the window's own buffer via
Quartz), two pixel-identical frames per shot, `ui.theme.apply_appearance`
called before each. Never `widget.grab()`, never `QT_QPA_PLATFORM=offscreen`.

What it photographs and reads back:

  1  the one-page colour summary (T1), whose PASS sentence claimed a
     completeness it did not have;
  2  the full colour check (T2): Knut's numbered note on each N-A cell, the
     note list under the table, and the closing sentence;
  3  the "Report type" help window, English and German, which named a control
     that no longer exists and promised a freeze that was removed;
  4  Getting Started, whose glossary taught COND as a row word;
  5  Preferences, where the Ukrainian translator was credited nowhere.

No ISO value is printed by this script.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import QTimer                                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,                # noqa: E402
                             QMessageBox)
from onscreen_capture import capture_window, session_is_locked     # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _match(a, b, tol=8):
    import numpy as np
    from PIL import Image
    x = np.asarray(Image.open(a).convert("RGB")).astype(int)
    y = np.asarray(Image.open(b).convert("RGB")).astype(int)
    return x.shape == y.shape and bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)


def shoot(app, win, out, stem, tries=3):
    """Two frames, kept only when they are pixel-identical."""
    a, b = out / f"{stem}-a.png", out / f"{stem}-b.png"
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 700)
        ok, w1 = capture_window(win, a)
        pump(app, 700)
        ok2, w2 = capture_window(win, b)
        why = w1 or w2 or why
        if ok and ok2 and _match(a, b):
            return {"taken": True, "identical": True, "tries": n,
                    "files": [a.name, b.name]}
    return {"taken": bool(ok and ok2), "identical": False, "tries": tries,
            "why": why}


def plain(h):
    t = re.sub(r"<[^>]+>", " ", h)
    for a, b in (("&middot;", "·"), ("&nbsp;", " "), ("&amp;", "&"),
                 ("&ndash;", "-"), ("&#x27;", "'"), ("&#x2026;", "…"),
                 ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">")):
        t = t.replace(a, b)
    return re.sub(r"[ \t]+", " ", t)


def answer_boxes(app, prefer=("Create New", "Create new report", "OK", "Yes")):
    log = []

    def _act(n=0):
        box = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, QMessageBox) and w.isVisible()), None)
        if box is None:
            if n < 30:
                QTimer.singleShot(250, lambda: _act(n + 1))
            return
        log.append({"text": box.text()[:200],
                    "buttons": [b.text().replace("&", "") for b in box.buttons()]})
        for want in prefer:
            for b in box.buttons():
                if b.text().replace("&", "") == want:
                    log[-1]["pressed"] = want
                    b.click()
                    QTimer.singleShot(400, lambda: _act(0))
                    return
        box.reject()
        QTimer.singleShot(400, lambda: _act(0))

    QTimer.singleShot(300, _act)
    return log


def a_first_verification(work, name):
    """One flawless first verification of a chart that repeats no colour."""
    from core.file_manager import Project
    from workflow import measurement_report as mr
    from workflow import run_compliance as rc
    from workflow.ti3_analysis import mark_verification_ti3
    sys.path.insert(0, str(ROOT))
    from tests.test_report_judging import _colours, _ramp, _write_ti3
    proj = Project.create(work / name, name)
    run = proj.current_run()
    run.ensure_dir()
    rc.bind_run(run, "chromiq_default", {})
    v = run.new_verification(datetime(2026, 1, 1, 10, 0, 0))
    v.ensure_dir()
    raw = v.dir / f"{name}.ti3"
    tgt = v.dir / f"{run.verify_stem}.ti3"
    _write_ti3(raw, _ramp(16) + _colours(), verification=False)
    mark_verification_ti3(raw).rename(tgt)
    rep = mr.build_report(tgt)
    rep["printing"] = {"colour": "through-profile", "intent": "relative",
                       "route": "chromiq"}
    mr.stamp_verdict(rep, rc.run_limits(run, {}).limits,
                     set_id="chromiq_default",
                     set_label="ChromIQ default (recommended)")
    mr.save_report(rep, v.dir)
    return run, tgt, rep


def language(app, code, work):
    from core.i18n import install_qt_translator, set_language
    from core.settings import AppSettings
    from ui.theme import apply_appearance
    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("appearance", "light")
    s.set("language", code)
    assert s.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    set_language(code)
    install_qt_translator(app)
    apply_appearance(app, None, "light")
    return s


def main():
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
    assert os.environ.get("CHROMIQ_COMPLIANCE_ISO_FILE"), "FORCE THE REPO ISO FILE"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    res = {"locked_at_start": session_is_locked(), "mode": "ON SCREEN"}

    # =================================================================== 1+2
    work = Path(tempfile.mkdtemp(prefix="chromiq-fix32-report-"))
    s = language(app, "en", work)
    run, tgt, rep = a_first_verification(work, "Fix32")
    summ = (rep.get("verdict") or {}).get("summary") or {}
    res["verdict"] = {"overall": (rep.get("verdict") or {}).get("overall"),
                      "checked": summ.get("checked"), "total": summ.get("total"),
                      "not_computed": summ.get("not_computed"),
                      "cond": summ.get("cond")}

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_SUMMARY)
    dlg = MeasurementReportDialog(s, None, initial_ti3=str(tgt))
    dlg.resize(1420, 980)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(app, 2600)
    res["report_window_visible"] = dlg.isVisible()

    # **SCROLL TO THE SENTENCE, NOT TO A FRACTION.** A first pass guessed
    # 0.46 for the full check and landed on the guide instead of the notes;
    # the picture was still useful (it caught a fifth false sentence nothing
    # in the suite reads), but it did not photograph what it claimed to. The
    # view is searched for the text now, and the fraction is only a fallback.
    for tag, tid, frac in (("t1", REPORT_TYPE_SUMMARY, 0.18),
                           ("t2", REPORT_TYPE_FULL, 0.46),
                           ("t2-notes", REPORT_TYPE_FULL,
                            "Notes on the verdicts above"),
                           ("t2-guide", REPORT_TYPE_FULL,
                            "every row that could be checked passed")):
        dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(tid))
        pump(app, 1500)
        boxes = []
        if not tag.startswith("t2-"):          # already generated for t2
            boxes = answer_boxes(app)
            dlg._generate_btn.click()
            pump(app, 6500)
        view = getattr(dlg, "_view", None)
        if view is not None and hasattr(view, "verticalScrollBar"):
            sb = view.verticalScrollBar()
            if isinstance(frac, str):
                from PyQt6.QtGui import QTextDocument
                cur = view.document().find(frac)
                res[f"{tag}_found_the_text"] = not cur.isNull()
                if not cur.isNull():
                    view.setTextCursor(cur)
                    view.ensureCursorVisible()
                    pump(app, 300)
                    # PUT IT NEAR THE TOP, not "a bit above the bottom".
                    # `ensureCursorVisible` leaves the match at the bottom
                    # edge, so a fixed nudge upward scrolls the thing that
                    # FOLLOWS it (the note list) off the page, which is what
                    # the first attempt photographed. The cursor's own
                    # rectangle says where it actually is.
                    top = view.cursorRect().top()
                    sb.setValue(max(0, sb.value() + top - 70))
                    # DROP THE SELECTION BEFORE THE SHUTTER. Searching the
                    # document leaves the match highlighted in blue, and a
                    # highlight the DRIVER painted must not end up in a
                    # photograph offered as a picture of the app.
                    cur.clearSelection()
                    view.setTextCursor(cur)
                else:
                    sb.setValue(int(sb.maximum() * 0.5))
            else:
                sb.setValue(int(sb.maximum() * frac))
        pump(app, 1400)
        res[f"{tag}_popups"] = boxes
        res[f"{tag}_shot"] = shoot(app, dlg, out, f"{tag}-report")
        body = plain(dlg._report_body_html(dlg._runs_for_report(), for_pdf=True))
        res[f"{tag}_says"] = {
            "the old false completeness claim":
                "Every value this limit set requires was checked" in body,
            "the corrected count sentence":
                "7 of 9 values checked" in body,
            "and why that is still PASS":
                "is not counted as a failure" in body,
            "the false 'Not computed on this chart' heading":
                "Not computed on this chart" in body,
            "Knut's numbered notes":
                "Notes on the verdicts above" in body,
            "the note that names the first-measurement row":
                "this is the first measurement of this chart" in body,
        }
        k = body.find("Result")
        res[f"{tag}_result_line"] = body[k:k + 320] if k >= 0 else None
        k = body.find("Notes on the verdicts above")
        res[f"{tag}_notes_block"] = body[k:k + 820] if k >= 0 else None

    grid = dlg._report_results_html(dlg._runs_for_report())
    res["na_cells_carry_a_raised_number"] = len(re.findall(r"N-A<sup", grid))
    res["na_cells_with_no_number"] = len(re.findall(r"N-A(?!<sup)", grid))
    dlg.close()
    pump(app, 600)

    # ===================================================================== 3
    res["type_help"] = {}
    for code in ("en", "de"):
        w2 = Path(tempfile.mkdtemp(prefix=f"chromiq-fix32-help-{code}-"))
        s2 = language(app, code, w2)
        _r, tgt2, _rep = a_first_verification(w2, f"Help{code}")
        d2 = MeasurementReportDialog(s2, None, initial_ti3=str(tgt2))
        d2.resize(1400, 940)
        d2.show()
        d2.raise_()
        d2.activateWindow()
        pump(app, 2400)
        entry = {"removed_widget_still_built":
                 getattr(d2, "_all_runs_check", None) is not None}
        from ui.tooltip_button import TooltipButton
        btn = None
        for b in d2.findChildren(TooltipButton):
            blob = " ".join(str(getattr(b, a, "") or "")
                            for a in ("_title", "_body", "_text"))
            if "single measurement" in blob or "einzigen Messung" in blob:
                btn = b
                full = blob
                # THE EXCERPT IS FOR THE RECORD; THE CLAIMS BELOW ARE MEASURED
                # ON THE WHOLE STRING. A first pass truncated to 700 characters
                # and then asked whether the removed control was named in it,
                # which is a probe that finds its answer somewhere else: the
                # sentence in question begins past that cut.
                k = full.find("single measurement")
                if k < 0:
                    k = full.find("einzigen Messung")
                entry["snippet"] = full[max(0, k - 40):k + 460]
                entry["blob_chars"] = len(full)
                break
        entry["button_found"] = btn is not None
        if btn is not None:
            state = {}

            def _shoot(n=0, _d=d2, _st=state, _c=code):
                pop = next((w for w in QApplication.topLevelWidgets()
                            if isinstance(w, QDialog) and w.isVisible()
                            and w is not _d), None)
                if pop is None:
                    if n < 30:
                        QTimer.singleShot(250, lambda: _shoot(n + 1))
                    else:
                        _st["why"] = "no help window appeared in 7.5 s"
                    return
                _st["cls"] = pop.metaObject().className()
                _st.update(shoot(app, pop, out, f"type-help-{_c}"))
                pop.close()

            QTimer.singleShot(600, _shoot)
            btn.click()
            pump(app, 2500)
            entry["shot"] = state
        blob = full if btn is not None else ""
        entry["still_names_the_removed_box"] = (
            "Show all measurement runs" in blob or "Messläufe anzeigen" in blob)
        entry["still_promises_the_freeze"] = (
            "fixed to that sheet" in blob or "auf diesen Bogen festgelegt" in blob)
        entry["says_what_the_window_does"] = (
            "asks you to choose" in blob or "bittet Sie zu wählen" in blob)
        # THE CONTROL: the probe can see this string at all. Without it every
        # negative above would also be produced by an empty blob.
        entry["probe_can_see_the_sentence"] = (
            "single measurement" in blob or "einzigen Messung" in blob)
        entry["list_is_live"] = d2._profile_list.isEnabled()
        res["type_help"][code] = entry
        d2.close()
        pump(app, 600)

    # =================================================================== 4+5
    w3 = Path(tempfile.mkdtemp(prefix="chromiq-fix32-help-"))
    s3 = language(app, "en", w3)
    from ui.dialogs.welcome_dialog import WelcomeDialog
    wd = WelcomeDialog(s3, None, "light")
    wd.resize(1180, 900)
    wd.show()
    wd.raise_()
    wd.activateWindow()
    pump(app, 2200)
    res["getting_started_visible"] = wd.isVisible()
    # **EACH CARD IS OPENED AND PHOTOGRAPHED, not scraped from whatever page
    # happens to be showing.** A first pass read the menu page's labels and
    # reported the corrected sentences absent. They were not absent; they were
    # on cards nobody had opened. A probe that looks in the wrong place gives
    # the wrong answer with the same confidence as a right one.
    from PyQt6.QtWidgets import QLabel, QTextBrowser, QTextEdit

    def _page_text():
        parts = [plain(w.text()) for w in wd.findChildren(QLabel)
                 if w.isVisible()]
        for cls in (QTextBrowser, QTextEdit):
            parts += [plain(w.toHtml()) for w in wd.findChildren(cls)
                      if w.isVisible()]
        return " ".join(parts)

    text = ""
    res["cards_opened"] = {}
    for key, stem in (("glossary", "card-glossary"),
                      ("verify", "card-verification")):
        try:
            wd._on_card_clicked(key)
            pump(app, 900)
            # **THE NOTES ARE COLLAPSED, AND A COLLAPSED NOTE IS NOT TEXT.**
            # The verification card came back with 977 characters and the
            # corrected sentence reported missing; it is inside a `StepNote`,
            # which renders nothing until it is opened. Opening them is what a
            # reader does, so it is what the driver does.
            from ui.dialogs.welcome_dialog import StepNote
            opened = 0
            for note in wd.findChildren(StepNote):
                btn = getattr(note, "_btn", None)
                if btn is not None and not btn.isChecked():
                    btn.setChecked(True)
                    opened += 1
            pump(app, 1200)
            res.setdefault("notes_opened", {})[key] = opened
            got = _page_text()
            text += " " + got
            res["cards_opened"][key] = {
                "chars": len(got),
                "title": wd._detail_title.text(),
                "shot": shoot(app, wd, out, stem),
            }
        except Exception as e:                                   # noqa: BLE001
            res["cards_opened"][key] = {"error": repr(e)}
    res["glossary_chars_read"] = len(text)
    res["glossary_says"] = {
        "COND means the row missed a limit": "COND means the row missed" in text,
        "COND when it missed a limit": "COND when it missed" in text,
        "missing a recommended one reads COND":
            "recommended one reads COND" in text,
        "COND is not a row word": "COND is not a row word" in text,
        "the only place COND appears": "the only place COND appears" in text,
    }
    wd.close()
    pump(app, 600)

    from ui.dialogs.settings_dialog import SettingsDialog
    sd = SettingsDialog(s3, None)
    sd.resize(1040, 880)
    sd.show()
    sd.raise_()
    sd.activateWindow()
    pump(app, 2200)
    from PyQt6.QtWidgets import QLabel
    labels = [lb.text() for lb in sd.findChildren(QLabel)]
    res["credit_line_on_screen"] = [t for t in labels if "LackiUA" in t]
    res["preferences_shot"] = shoot(app, sd, out, "preferences-credit")
    sd.close()
    pump(app, 600)

    (out / "fix32-report.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False)[:9000])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
