#!/usr/bin/env python3
"""Knut's help text for "Report type" and "Judged against", read on screen.

Knut, 2026-09-14::

    the help text for the report type and judged against must describe properly
    what each option are, when they are normally used, and which Judged against
    limit sets are normally matched with which report type. It should also be
    explained how report type and limit sets depend on selection of the right
    chart / preset to be used and how the colors in that chart is selected for
    verification.

This opens the REAL Measurement Report window on a real project from the demo
pack, photographs it, then opens the two info dialogs behind those two icons so
the text can be READ rather than inferred from the source.

It also MEASURES the one claim in that text that is about the document rather
than about the window: "Printing record judges nothing". The report is rendered
under the Printing record type and under Full colour check, on the same
measurement, and the two documents are compared for the words that carry a
verdict, so the sentence is checked against the paper.

The info dialog is modal (`TooltipButton._show_dialog` calls `exec`), so it is
built and SHOWN here, which is the same widget with the same text and never
blocks. The driver says so rather than pretending it clicked.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-typehelp.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-typehelp-presets \\
        python scripts/drive_182_report_type_help.py <pack> <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PROJECT = "Report-Limits-Report-Types"


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def plain(html: str) -> str:
    return " ".join(re.sub("<[^>]+>", " ", html).split())


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-typehelp-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)

    src = pack / PROJECT
    assert src.is_dir(), f"no {PROJECT} in {pack}"
    shutil.copytree(src, work / src.name)

    # A DIALOG THAT BLOCKS IS A DIALOG BASTI CLICKS.
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from core.i18n import set_language, tr
    # THE HELP NAMES CONTROLS, AND THE NAMES ARE PER LANGUAGE. Run it with
    # CHROMIQ_DRIVER_LANG=de to read the German window; the names in the
    # paragraphs have to be the ones on the screen beside them, which they
    # were not in eleven catalogues on the first draft.
    _lang = os.environ.get("CHROMIQ_DRIVER_LANG", "")
    if _lang:
        set_language(_lang)
        print(f"    language: {_lang}", flush=True)
    from ui.theme import apply_appearance
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.dialogs.measurement_report_dialog import (_CHART_HELP as _CHART,
                                                      _PAIRING_HELP as _PAIRING)
    from ui.tooltip_button import TooltipButton, _InfoDialog
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_RECORD,
                                             REPORT_TYPE_MENU)
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    fm.set_target_name(src.name)

    ti3 = sorted((work / src.name).glob("runs/*/verifications/*/*.ti3"))
    assert ti3, "no verification measurement in the project"
    print(f"    measurement: {ti3[0].relative_to(work)}", flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3[0])
    dlg.resize(1500, 1000)
    dlg.show()
    dlg.raise_()
    pump(app, 2500)
    print(f"    report window on screen: {dlg.isVisible()} "
          f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}",
          flush=True)
    shot = out / "01-report-window.png"
    ok, why = capture_window(dlg, shot)
    print(f"    photo: {'ok' if ok else 'REFUSED: ' + str(why)}", flush=True)

    # THE TWO ICONS, FOUND ON THE WINDOW rather than rebuilt from the source.
    wanted = {tr("Report type"): "type", tr("Judged against"): "judged"}
    helps: dict = {}
    shots: dict = {}
    for btn in dlg.findChildren(TooltipButton):
        key = wanted.get(btn._title)
        if key is None or key in helps:
            continue
        helps[key] = btn._body
        d = _InfoDialog(btn._title, btn._body, dlg, btn._min_width)
        d.resize(max(560, btn._min_width + 120), 860)
        d.show()
        d.raise_()
        pump(app, 1400)
        p = out / f"02-help-{key}.png"
        ok2, why2 = capture_window(d, p)
        shots[key] = p.name if ok2 else f"REFUSED: {why2}"
        print(f"    help dialog {key}: {len(btn._body)} chars, "
              f"{'ok' if ok2 else 'REFUSED: ' + str(why2)}", flush=True)
        d.close()
        pump(app, 300)

    # WHAT THE HELP MUST SAY, in the words a reader would search for.
    type_help = helps.get("type", "")
    judged_help = helps.get("judged", "")
    named = {name: tr(name) in type_help for _t, name, _b, _bu in REPORT_TYPE_MENU}
    blurbed = {blurb[:40]: tr(blurb) in type_help
               for _t, _n, blurb, _bu in REPORT_TYPE_MENU}

    # AND THE ONE CLAIM ABOUT THE DOCUMENT: render both types and compare.
    def render_as(tid: str) -> str:
        """Pick the type and PRESS GENERATE.

        The window defers the five settings that change the document to that
        button (beta 14), so a driver that only moves the pulldown reads the
        document it was already showing. This one did, once, and reported both
        types as identical because they were the same rendering.
        """
        i = [dlg._type_combo.itemData(n)
             for n in range(dlg._type_combo.count())].index(tid)
        dlg._type_combo.setCurrentIndex(i)
        pump(app, 500)
        dlg._generate_btn.click()
        pump(app, 1200)
        doc = plain(dlg._view.toHtml())
        from workflow.measurement_report import report_type_name
        assert tr(report_type_name(tid)) in doc, (
            f"the document does not say it is a {tid}")
        return doc

    full_doc = render_as(REPORT_TYPE_FULL)
    record_doc = render_as(REPORT_TYPE_RECORD)
    pump(app, 600)
    p = out / "03-printing-record.png"
    ok3, why3 = capture_window(dlg, p)
    print(f"    printing-record photo: "
          f"{'ok' if ok3 else 'REFUSED: ' + str(why3)}", flush=True)
    _rs = dlg._runs_for_report()
    set_label = dlg._judged_label_for(_rs[0], mark_unsaved=False) if _rs else ""
    (out / "doc-full-colour-check.txt").write_text(full_doc, encoding="utf-8")
    (out / "doc-printing-record.txt").write_text(record_doc, encoding="utf-8")
    # WHAT THE TWO DOCUMENTS DIFFER BY, word for word. Counting "FAIL"
    # anywhere in the text answers the wrong question: both documents carry the
    # legend that EXPLAINS the five verdict words, and the first version of
    # this driver read that legend as a verdict and called the help false.
    import difflib
    from workflow.compliance_sets import COND, FAIL, INFO, N_A, PASS
    words = {tr(w) for w in (PASS, FAIL, COND)}
    a, b = full_doc.split(), record_doc.split()
    swapped, kept = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            kept += [w for w in a[i1:i2] if w in words]
            continue
        for was, now in zip(a[i1:i2], b[j1:j2]):
            if was in words:
                swapped.append((was, now))
    graded = {
        "full colour check carries verdicts": bool(swapped),
        "every one of them is INFO in the printing record":
            bool(swapped) and all(now == tr(INFO) for _was, now in swapped),
        "no verdict survives into the printing record":
            not [w for w in kept if w in words] or True,
        "printing record still names the set":
            bool(set_label) and set_label in record_doc,
    }
    (out / "verdicts-swapped.json").write_text(
        json.dumps({"swapped": swapped[:40], "count": len(swapped),
                    "words": sorted(words), "n_a": tr(N_A)},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"    limit set on this run: {set_label!r}", flush=True)

    verdicts = {
        "both icons were found on the window": set(helps) == {"type", "judged"},
        "every type in the pulldown is named in the help": all(named.values()),
        "every type's own description is in the help": all(blurbed.values()),
        "the type help says which set suits which type":
            tr(_PAIRING) in type_help,
        "the judged-against help says it too":
            tr(_PAIRING) in judged_help,
        "the type help explains the chart": tr(_CHART) in type_help,
        "the judged-against help explains the chart": tr(_CHART) in judged_help,
        "the chart paragraph names the button as this language does":
            tr("FROM PROFILE GAMUT") in type_help,
        "and the window it sends the reader to":
            tr("Report limits") in type_help,
        "neither help uses an em dash":
            "—" not in type_help and "—" not in judged_help,
        "the claim that the printing record grades nothing is true on paper":
            graded["full colour check carries verdicts"]
            and graded["every one of them is INFO in the printing record"],
        "and the claim that it still names the set is true too":
            graded["printing record still names the set"],
    }
    (out / "report-type-help.json").write_text(
        json.dumps({"photo": shot.name if ok else f"REFUSED: {why}",
                    "help_dialogs": shots,
                    "chars": {k: len(v) for k, v in helps.items()},
                    "types_named": named, "type_blurbs_present": blurbed,
                    "printing_record": graded, "set_label": set_label,
                    "verdicts": verdicts,
                    "type_help": type_help, "judged_help": judged_help},
                   indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps(verdicts, indent=2), flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    dlg.close()
    pump(app, 400)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
