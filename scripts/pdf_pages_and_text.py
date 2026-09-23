#!/usr/bin/env python3
"""Read a saved report PDF back: its text per page, and each page as a PNG.

This photographs the FILE, the way a reader opening it sees it; it is not a
substitute for photographing the app, which the drivers do on screen.

    python scripts/pdf_pages_and_text.py <file.pdf> [<out-dir>]
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(pdf: Path, out: Path) -> int:
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtPdf import QPdfDocument
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    doc = QPdfDocument(None)
    doc.load(str(pdf))
    out.mkdir(parents=True, exist_ok=True)
    text = []
    for i in range(doc.pageCount()):
        pts = doc.pagePointSize(i)
        img = doc.render(i, QSize(int(pts.width() * 2), int(pts.height() * 2)))
        img.save(str(out / f"{pdf.stem}-page{i + 1:02d}.png"))
        text.append(f"===== page {i + 1} =====\n" + doc.getAllText(i).text())
    (out / f"{pdf.stem}.txt").write_text("\n".join(text), encoding="utf-8")
    print(f"{pdf.name}: {doc.pageCount()} pages -> {out}")
    return 0


if __name__ == "__main__":
    p = Path(sys.argv[1])
    sys.exit(main(p, Path(sys.argv[2]) if len(sys.argv) > 2 else p.parent))
