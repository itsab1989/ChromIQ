#!/usr/bin/env python3
"""Compare the before and after PDFs of `drive_k45_pdf_layout.py`, page by page.

    python k45_compare_pdfs.py <proof-dir>

Reads ``<proof>/runs/{before,after}/<lang>/<lang>-<tag>.pdf`` and writes, for
each pair, the pages rendered to PNG and one contact sheet per side into
``<proof>/pages/<lang>-<tag>/``, and a table of what K45 is about into
``<proof>/compare.json`` and ``compare.md``:

* the page count;
* on which page "How to read this report" starts, on which its last line of
  text lands, and the size its text is printed at;
* for every "For information (no limit applies)" heading (12 pt), its page
  and whether it is the first line of that page's body;
* the lines printed under the Colour accuracy graph.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf

HEAD_Y = 68.0            # below the header band: 15 mm margin + 34 px band


def _lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                size = max(s["size"] for s in line["spans"])
                out.append((line["bbox"][1], line["bbox"][3], size, text))
    return sorted(out)


def analyse(pdf: Path, words: dict) -> dict:
    doc = pymupdf.open(str(pdf))
    pages = [_lines(p) for p in doc]
    res = {"pages": doc.page_count, "how_to_read": None, "for_information": [],
           "accuracy_key": [], "page_fill": []}
    for n, lines in enumerate(pages):
        body = [ln for ln in lines if HEAD_Y < ln[0] < 790]
        res["page_fill"].append(round(max((ln[1] for ln in body), default=0)))
    # How to read: from its heading to the heading after it
    start = end = None
    sizes = set()
    for n, lines in enumerate(pages):
        for y0, _y1, size, text in lines:
            if text == words["how"]:
                start = (n, y0)
            elif start and text == words["results"] and end is None:
                end = n
    if start:
        last = start[0]
        for n in range(start[0], (end if end is not None else start[0] + 1)):
            for y0, _y1, size, text in pages[n]:
                if HEAD_Y < y0 < 790 and (n > start[0] or y0 > start[1]):
                    last = n
                    sizes.add(round(size, 2))
        res["how_to_read"] = {"first_page": start[0] + 1,
                              "last_text_page": last + 1,
                              "text_sizes_pt": sorted(sizes)}
    section_page = None
    for n, lines in enumerate(pages):
        body = [ln for ln in lines if HEAD_Y < ln[0] < 790]
        for k, (y0, _y1, size, text) in enumerate(body):
            if text == words["section"]:
                section_page = n
            if text == words["info"] and size > 11:
                # "top": the first line of its page; "after overflow": the
                # colour section in front of it began on an earlier page;
                # "mid": neither, which is what K45-3 removes
                where = ("top" if k == 0 else "after overflow"
                         if section_page is not None and section_page < n
                         else "mid")
                res["for_information"].append(
                    {"page": n + 1, "first_on_page": k == 0,
                     "where": where, "y": round(y0)})
    for n, lines in enumerate(pages):
        texts = [t for _a, _b, _s, t in lines]
        if words["accuracy"] in texts:
            i = texts.index(words["accuracy"])
            block = []
            for t in texts[i + 1:]:
                if t == words["white"]:
                    break
                block.append(t)
            # a key line starts with the dotted stroke; a long one wraps
            for t in block:
                if t.startswith("┈┈"):
                    res["accuracy_key"].append(t)
                elif res["accuracy_key"] and not t.startswith("┈┈"):
                    res["accuracy_key"][-1] += " " + t
            break
    return res


def render(pdf: Path, out: Path, prefix: str, dpi: int = 60) -> None:
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf))
    pix = []
    for i, page in enumerate(doc):
        p = page.get_pixmap(dpi=110)
        p.save(str(out / f"{prefix}-p{i + 1:02d}.png"))
        pix.append(page.get_pixmap(dpi=dpi))
    w, h = pix[0].width, pix[0].height
    cols = min(6, len(pix))
    rows = (len(pix) + cols - 1) // cols
    sheet = pymupdf.Pixmap(pymupdf.csRGB,
                           pymupdf.IRect(0, 0, cols * (w + 6), rows * (h + 6)),
                           False)
    sheet.set_rect(sheet.irect, (90, 90, 90))
    for k, p in enumerate(pix):
        r, c = divmod(k, cols)
        p.set_origin(c * (w + 6), r * (h + 6))
        sheet.copy(p, p.irect)
    sheet.save(str(out / f"{prefix}-sheet.png"))


WORDS = {
    "en": {"how": "How to read this report", "results": "Report Results",
           "info": "For information (no limit applies)",
           "section": "Colour accuracy (ΔE00 against the chart's design)",
           "accuracy": "Colour accuracy (ΔE00)", "white": "Paper white (L*)"},
}


def main() -> int:
    proof = Path(sys.argv[1])
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.i18n import set_language, tr
    set_language("de")
    WORDS["de"] = {k: tr(v) for k, v in WORDS["en"].items()}
    table = {}
    for after_dir in sorted((proof / "runs" / "after").iterdir()):
        run = after_dir.name                     # "en", "de", "k40pack-en" …
        lang = run.rsplit("-", 1)[-1]
        if lang not in WORDS:
            continue
        for pdf in sorted(after_dir.glob(f"{lang}-*.pdf")):
            tag = pdf.stem if run == lang else f"{run}-{pdf.stem}"
            before = proof / "runs" / "before" / run / pdf.name
            row = {"after": analyse(pdf, WORDS[lang])}
            if before.is_file():
                row["before"] = analyse(before, WORDS[lang])
                render(before, proof / "pages" / tag, "before")
            render(pdf, proof / "pages" / tag, "after")
            table[tag] = row
    (proof / "compare.json").write_text(
        json.dumps(table, indent=1, ensure_ascii=False), encoding="utf-8")
    md = ["| case | pages before | pages after | How to read: pages before / after | For information heading, before / after | Colour accuracy key lines before / after |",
          "|---|---|---|---|---|---|"]
    for tag, row in table.items():
        b, a = row.get("before", {}), row["after"]

        def hr(x):
            h = x.get("how_to_read") if x else None
            return (f"p{h['first_page']}-p{h['last_text_page']}"
                    if h else "-")

        def fi(x):
            f = x.get("for_information", []) if x else []
            tags = {"top": "", "after overflow": " (after its overflow)",
                    "mid": " (MID-PAGE)"}
            return ", ".join(f"p{e['page']}{tags[e['where']]}"
                             for e in f) or "-"
        md.append(f"| {tag} | {b.get('pages', '-')} | {a['pages']} | "
                  f"{hr(b)} / {hr(a)} | {fi(b)} / {fi(a)} | "
                  f"{len(b.get('accuracy_key', []))} / {len(a['accuracy_key'])} |")
    (proof / "compare.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
