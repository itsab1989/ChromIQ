#!/usr/bin/env python3
"""Print every Help card to PDF and render the pages, so they can be LOOKED at.

The printing faults Knut reported — microscopic headings, a clipped diagram,
bullets run together into a block, a table row cut in half by a page break —
are all invisible in a test that only counts elements. This puts every page of
every card on the desk as a PNG.

    python scripts/proof_help_card_prints.py [--out DIR] [--page A4]
                                             [--landscape] [--only KEY]

Default output: ~/Desktop/chromiq-help-print-proof/<page>/<card>/page-N.png,
with the PDFs beside them.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QMarginsF, QSize                       # noqa: E402
from PyQt6.QtGui import QFontDatabase, QPageLayout, QPageSize   # noqa: E402
from PyQt6.QtPdf import QPdfDocument                            # noqa: E402
from PyQt6.QtPrintSupport import QPrinter                       # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.resource_path import resource_path                    # noqa: E402


def slug(text: str) -> str:
    keep = [c if (c.isalnum() or c in " -_") else "" for c in text]
    return "".join(keep).strip().replace(" ", "-")[:48] or "card"


def main() -> int:
    args = sys.argv[1:]
    out = Path.home() / "Desktop" / "chromiq-help-print-proof"
    if "--out" in args:
        out = Path(args[args.index("--out") + 1])
    page_name = args[args.index("--page") + 1] if "--page" in args else "A4"
    landscape = "--landscape" in args
    only = args[args.index("--only") + 1] if "--only" in args else None

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import render_card

    root = out / (page_name + ("-landscape" if landscape else ""))
    root.mkdir(parents=True, exist_ok=True)
    print(f"Printing {len(WORKFLOWS)} help cards to {page_name}"
          f"{' landscape' if landscape else ''}\n")

    for wf in WORKFLOWS:
        if only and wf["key"] != only:
            continue
        folder = root / slug(wf["title"])
        folder.mkdir(parents=True, exist_ok=True)
        pdf = folder / f"{slug(wf['title'])}.pdf"

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(pdf))
        printer.setPageSize(QPageSize(getattr(QPageSize.PageSizeId, page_name)))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape
                                   else QPageLayout.Orientation.Portrait)
        printer.setPageMargins(QMarginsF(15, 15, 15, 15),
                               QPageLayout.Unit.Millimeter)
        render_card(wf, printer)

        doc = QPdfDocument(None)
        doc.load(str(pdf))
        for i in range(doc.pageCount()):
            doc.render(i, QSize(1000, 1414)).save(
                str(folder / f"page-{i + 1:02d}.png"))
        print(f"  {wf['title'][:52]:52s} {doc.pageCount():2d} page(s)")

    print(f"\nProof: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
