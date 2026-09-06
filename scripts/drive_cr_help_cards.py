#!/usr/bin/env python3
"""Drive the real ChromIQ Help window, on screen, and prove the scanner cards.

B8-93. Opens the Welcome/Help dialog, walks to every card, opens every note on
the two scanner cards, grabs the window, and prints each card to a real PDF
through the same `render_card` the Print button uses. Then reads the PDF's own
text back with pypdf and reports whether every step and every note is on it,
because a card once printed 29 of 79 entries and looked finished.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cr.ini      # DO THIS FIRST
    python scripts/drive_cr_help_cards.py --out ~/Desktop/… [--lang de]

SANDBOX THE SETTINGS FIRST. This builds a real `AppSettings`, which is the real
preferences store; `CHROMIQ_SETTINGS_FILE` is what stops it reaching the store
the owner works in every day. The script refuses to run without it rather than
trusting whoever started it to have remembered.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
    raise SystemExit(
        "CHROMIQ_SETTINGS_FILE is not set. This driver builds a real "
        "AppSettings; without the sandbox it writes into the owner's own "
        "preferences. Set it and run again.")

from PyQt6.QtCore import QEvent, QMarginsF, QTimer                  # noqa: E402
from PyQt6.QtGui import (QFontDatabase, QPageLayout, QPageSize)     # noqa: E402
from PyQt6.QtPrintSupport import QPrinter                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton               # noqa: E402

from core.resource_path import resource_path                        # noqa: E402

#: The two cards this change is about, plus three it must have left alone.
CARDS = ("scanner_profile", "printer_from_scan",
         "first_profile", "glossary", "keyboard_shortcuts")

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}


def flat(s: str) -> str:
    """Normalise for comparing against PDF text.

    THE LIGATURES ARE NOT OPTIONAL. A PDF really carries "Proﬁle" (U+FB01)
    where the source says "Profile", and pypdf hands the glyph back as it is.
    Without this the first run of this comparison reported 54 missing
    fragments, every one of them present.
    """
    import re
    for lig, plain in _LIGATURES.items():
        s = s.replace(lig, plain)
    return re.sub(r"\s+", " ", s).strip()


def notes_of(step):
    return tuple(step[3]) if len(step) > 3 else ()


def main() -> int:
    args = sys.argv[1:]
    out = Path(args[args.index("--out") + 1]) if "--out" in args else \
        Path.home() / "Desktop" / "cr-help-cards"
    lang = args[args.index("--lang") + 1] if "--lang" in args else "en"
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    # THE STYLE THE APP SHIPS ON. `main.py` sets Fusion before it builds a
    # window, on every platform, and every size and rect comes out of the
    # style; a driver on the platform default is measuring another app.
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core import i18n
    i18n.set_language(lang)

    from core.settings import AppSettings
    settings = AppSettings()
    # Say the store OUT LOUD before anything writes to it. A driver
    # that only claims to be sandboxed is how one left
    # `custom_output_path` pointing at a swept temp folder.
    print(f"settings store: {settings._qs.fileName()}")

    # THE APP'S OWN APPEARANCE, NOT A STRING PASSED TO THE DIALOG.
    #
    # The first run of this driver constructed `WelcomeDialog(..., "dark")`
    # without ever calling `apply_appearance`, so the dialog painted its text
    # in the dark theme's near-white ink on the light default surface of an
    # unstyled scroll area. Every step came out all but invisible and the note
    # headings looked like the loudest thing on the card, which is the exact
    # opposite of what the change is for. The app-wide stylesheet is what
    # decides that surface, so the driver applies it the way `main.py` does.
    from ui.theme import apply_appearance

    mode = apply_appearance(app, None, args[args.index("--appearance") + 1]
                            if "--appearance" in args else "dark")
    print(f"appearance: {mode}")

    from ui.dialogs.welcome_dialog import WORKFLOWS, StepNote, WelcomeDialog
    from ui.help_card_print import card_html, render_card

    dlg = WelcomeDialog(settings, None, mode)
    dlg.resize(1180, 900)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    for _ in range(20):
        app.processEvents()

    import pypdf

    problems: list[str] = []
    for key in CARDS:
        wf = next(w for w in WORKFLOWS if w["key"] == key)
        dlg._on_card_clicked(key)
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        for _ in range(20):
            app.processEvents()

        notes = dlg._steps_host.findChildren(StepNote)
        buttons = dlg._steps_host.findChildren(QPushButton,
                                               "welcome_note_head")
        dlg.grab().save(str(out / f"{lang}-{mode}-{key}-closed.png"), "PNG")

        # …and again with every note OPEN, which is the state a reader who
        # wants the reasoning is in.
        for n in notes:
            n.set_open(True)
        for _ in range(20):
            app.processEvents()
        dlg.grab().save(str(out / f"{lang}-{mode}-{key}-open.png"), "PNG")

        pdf = out / f"{lang}-{key}.pdf"
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(pdf))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageMargins(QMarginsF(15, 15, 15, 15),
                               QPageLayout.Unit.Millimeter)
        pages = render_card(wf, printer, lang=lang)
        text = flat("\n".join(p.extract_text() or ""
                              for p in pypdf.PdfReader(str(pdf)).pages))

        missing = []
        for i, step in enumerate(wf.get("steps") or (), 1):
            if flat(str(step[1]))[:60] not in text:
                missing.append(f"step {i}")
            for heading, body in notes_of(step):
                if flat(heading)[:40] not in text:
                    missing.append(f"step {i} note heading {heading!r}")
                if flat(body)[:60] not in text:
                    missing.append(f"step {i} note body {heading!r}")
        if missing:
            problems += [f"{key}: {m}" for m in missing]
        print(f"{lang} {key:20s} {len(notes):2d} notes, {len(buttons):2d} "
              f"headings, {pages} printed page(s), "
              f"{'ALL PRESENT' if not missing else 'MISSING ' + str(missing)}")
        # A card with no notes must not have grown one.
        if not any(notes_of(s) for s in wf.get("steps") or ()) and notes:
            problems.append(f"{key}: has no notes in the data but "
                            f"{len(notes)} on screen")
        if 'class="note"' in card_html(wf) and not notes_of(
                (wf.get("steps") or [(0, "")])[0]) and not notes:
            problems.append(f"{key}: printed a note it does not have")

    dlg.close()
    QTimer.singleShot(0, app.quit)
    app.processEvents()

    print()
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  ", p)
        return 1
    print("every step and every note reached the printed PDF's own text")
    print(f"screenshots and PDFs: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
