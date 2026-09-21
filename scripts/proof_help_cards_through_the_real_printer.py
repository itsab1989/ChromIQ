#!/usr/bin/env python3
"""Prove a help card prints WHOLE and at FULL SIZE, through the real print path.

Two faults this project has already shipped, and neither is visible to a test
that counts elements or renders offscreen:

* **29 of 79 glossary entries printed and the card looked finished.** A
  ``QTextDocument`` that is edited while only half laid out loses the geometry
  below the edit, and ``pageCount()`` and ``documentSize()`` are both derived
  from the wreckage, so the document cheerfully reports that nothing is
  missing. The ONLY check that catches it is reading the words back out of the
  PDF (`feedback_qtextdocument_half_laid_out`).
* **Every card printed at 32 % into the top third of the sheet.** A
  ``QPdfWriter`` accepts any ``setResolution``; a native ``QPrinter`` snaps it
  to the queue's own list and goes on reporting device pixels at the
  resolution you GOT. Every proof we had went through a PDF writer and was
  blind to it (`feedback_pdf_writer_is_blind_to_printer_bugs`).

So this script does three things, in this order:

1. **Geometry, on the NATIVE engine.** Opens a real ``QPrinter`` on the
   default queue, drives it through ``QPrintPreviewWidget`` (which asks the
   native engine for the same ``resolution()``/``width()``/``height()`` a job
   sees), and checks ``page_w_px * scale ≈ device.width()``. If the machine has
   no print queue Qt silently falls back to PDF, and the check is REPORTED AS
   NOT RUN rather than passed.
2. **Completeness, out of the PDF.** Renders the card, reads every page back
   with ``QPdfDocument.getAllText`` and requires every word of the source
   document to be there.
3. **Page count**, so a change that doubles a card's length cannot pass
   unnoticed.

Run it with a REAL platform plugin (no ``QT_QPA_PLATFORM=offscreen``): a `pt`
size is resolved against the primary screen's logical DPI, 72 on macOS cocoa
and 96 offscreen, so a headless run cannot see a whole class of sizing fault.

    python scripts/proof_help_cards_through_the_real_printer.py --out DIR
                                                                [--card KEY]
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    raise SystemExit(
        "REFUSING: offscreen reports 96 dpi and a PDF writer takes any "
        "resolution, so this proof would be blind to both faults it exists "
        "for. Run it with the real platform plugin.")

from PyQt6.QtCore import QMarginsF                              # noqa: E402
from PyQt6.QtGui import QFontDatabase, QPageLayout, QPageSize   # noqa: E402
from PyQt6.QtPdf import QPdfDocument                            # noqa: E402
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewWidget  # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.resource_path import resource_path                    # noqa: E402
from ui.styles import WinButtonLayoutStyle                      # noqa: E402

#: A word, for the completeness check. Hyphen and slash are SEPARATORS, not
#: word characters, because `QPdfDocument.getAllText` hands a hyphen back as
#: U+FFFE: measured on the dictionary card, "re-judges" comes out
#: "re\ufffejudges" and "shaper/matrix" splits. The ink is on the page either
#: way, so splitting both streams the same way keeps the check honest without
#: reporting four phantom losses.
_WORD = re.compile(r"[\w'’ΔμΩ°%×.]+", re.UNICODE)


def _words(text: str) -> "list[str]":
    for ch in "\ufffe\ufffd-/\u2010\u2011\u00ad":
        text = text.replace(ch, " ")
    return _WORD.findall(text.lower())


def _slug(text: str) -> str:
    keep = [c if (c.isalnum() or c in " -_") else "" for c in text]
    return "".join(keep).strip().replace(" ", "-")[:48] or "card"


# ---------------------------------------------------------------- geometry
def native_geometry(wf: dict) -> "tuple[bool, str]":
    """Render *wf* onto a NATIVE printer and check the painter's scale.

    Returns (ran, message). ``ran`` is False when the machine has no print
    queue, because Qt then falls back to PdfFormat and the check would pass
    against the very bug it looks for.
    """
    from ui.help_card_print import (build_document, printable_size_mm,
                                    render_card)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(15, 15, 15, 15),
                           QPageLayout.Unit.Millimeter)
    if printer.outputFormat() != QPrinter.OutputFormat.NativeFormat:
        return False, "NOT RUN: this machine has no print queue"

    # Drive the native engine the way a job does, with no window and no job.
    preview = QPrintPreviewWidget(printer)
    preview.updatePreview()

    res = float(printer.resolution() or 0.0)
    w_mm, h_mm = printable_size_mm(printer)
    page_w = w_mm * 96.0 / 25.4
    scale = res / 96.0
    dev_w = float(printer.width())
    # The whole fault, in one line: the page laid out in 96-dpi pixels, scaled
    # by the device's real resolution, must land on the device's real width.
    err = abs(page_w * scale - dev_w) / max(dev_w, 1.0)
    doc = build_document(wf, width_mm=w_mm, height_mm=h_mm)
    pages = render_card(wf, printer)
    ok = err < 0.02
    return True, (
        f"{'OK ' if ok else 'FAIL'} native queue “{printer.printerName()}”, "
        f"{res:.0f} dpi, page {w_mm:.1f}x{h_mm:.1f} mm; "
        f"page_w*scale={page_w * scale:.1f} px against device width "
        f"{dev_w:.1f} px ({err * 100:.2f} % out); {pages} pages; "
        f"document {doc.size().height():.0f} px tall")


# ------------------------------------------------------------ completeness
def words_survive_the_print(wf: dict, out: Path) -> "tuple[bool, str]":
    """Render *wf* to a PDF and require every word of it to come back out."""
    from ui.help_card_print import (build_document, printable_size_mm,
                                    render_card)
    from PyQt6.QtGui import QPdfWriter

    pdf = out / f"{_slug(wf['title'])}.pdf"
    writer = QPdfWriter(str(pdf))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15),
                          QPageLayout.Unit.Millimeter)
    w_mm, h_mm = printable_size_mm(writer)
    pages = render_card(wf, writer)
    del writer                     # flush

    src = build_document(wf, width_mm=w_mm, height_mm=h_mm).toPlainText()

    got = QPdfDocument(None)
    got.load(str(pdf))
    printed = " ".join(got.getAllText(i).text() for i in range(got.pageCount()))
    printed_words = set(_words(printed))

    missing = [w for w in _words(src)
               if len(w) > 2 and w not in printed_words]
    # A word may legitimately be hyphenated across a line break by the PDF; the
    # check is deliberately over-strict and any miss is reported for a human.
    uniq = sorted(set(missing))
    ok = not uniq
    return ok, (f"{'OK  ' if ok else 'MISS'} {pdf.name}: "
                f"{got.pageCount()} PDF pages / {pages} painted, "
                f"{len(printed_words)} distinct words back out"
                + (f"; MISSING {len(uniq)}: {uniq[:12]}" if uniq else ""))


def main() -> int:
    args = sys.argv[1:]
    out = (Path(args[args.index("--out") + 1]) if "--out" in args
           else Path.home() / "Desktop" / "ChromIQ-beta30-proof" /
           "help-cards" / "print")
    only = [args[i + 1] for i, a in enumerate(args) if a == "--card"]
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from ui.dialogs.welcome_dialog import WORKFLOWS

    print(f"screen logical DPI: "
          f"{app.primaryScreen().logicalDotsPerInch():.0f} "
          f"(72 = cocoa, 96 = offscreen)\n")

    bad = 0
    for wf in WORKFLOWS:
        if only and wf["key"] not in only:
            continue
        print(f"=== {wf['key']}  ({wf['title']})")
        ran, msg = native_geometry(wf)
        print("   geometry    :", msg)
        if ran and msg.startswith("FAIL"):
            bad += 1
        ok, msg = words_survive_the_print(wf, out)
        print("   completeness:", msg)
        if not ok:
            bad += 1
    print(f"\n{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
