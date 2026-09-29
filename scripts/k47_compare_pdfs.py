#!/usr/bin/env python3
"""Compare the before and after PDFs of `drive_k47_graph_limits.py`.

    python k47_compare_pdfs.py <proof-dir>

Reads ``<proof>/runs/{before,after}/<lang>/<lang>-<tag>.pdf`` and writes, for
each graph of each PDF, its title, the lines printed under it (the limit-line
sentences and the no-limit note), and the page it is on; renders every page
that carries a trend graph to PNG at 110 dpi into ``<proof>/pages/<lang>-<tag>/``
(``before-pNN.png``, ``after-pNN.png``); and writes ``compare.json`` and
``compare.md``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf

#: Graph titles, English and German, as the PDF prints them.
TITLES = {
    "en": ["Colour accuracy (ΔE00)", "Paper white (L*)",
           "Paper white difference (ΔE00)", "Darkest black (L*)",
           "Cube corners (ΔE00)", "Solid colours (ΔE00)",
           "Hue of the solids (ΔH*ab)", "Grey balance (ΔCh)",
           "Tone ramps 30 to 70 % (ΔL*)", "Control strip (ΔE00)",
           "Outer and surface gamut (ΔE00)", "Repeatability (ΔE00)",
           "Evenness (ΔE00)"],
}


def _de_titles() -> list:
    import os
    tree = os.environ.get("CHROMIQ_TREE") or str(
        Path(__file__).resolve().parents[1])
    cat = json.loads((Path(tree) / "data/i18n/de.json").read_text("utf-8"))
    return [cat.get(t, t) for t in TITLES["en"]]


def _lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                size = max(s["size"] for s in line["spans"])
                out.append((round(line["bbox"][1], 1), size, text))
    return sorted(out)


def analyse(pdf: Path, titles: list) -> dict:
    doc = pymupdf.open(str(pdf))
    graphs, pages_with = [], set()
    for n, page in enumerate(doc):
        lines = _lines(page)
        heads = [(k, ln) for k, ln in enumerate(lines)
                 if ln[2] in titles and ln[1] >= 11.5]
        for h, (k, ln) in enumerate(heads):
            end = heads[h + 1][0] if h + 1 < len(heads) else len(lines)
            under = [t for _y, size, t in lines[k + 1:end]
                     if 7.5 <= size <= 9.0 and not t.startswith("Page ")
                     and not t.startswith("Seite ")]
            graphs.append({"page": n + 1, "title": ln[2], "text": under})
            pages_with.add(n)
    return {"pages": doc.page_count, "graphs": graphs,
            "graph_pages": sorted(p + 1 for p in pages_with)}


def render(pdf: Path, pages: list, out: Path, side: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf))
    for p in pages:
        doc[p - 1].get_pixmap(dpi=110).save(str(out / f"{side}-p{p:02d}.png"))


def main() -> int:
    proof = Path(sys.argv[1])
    titles = {"en": TITLES["en"], "de": _de_titles()}
    # the German titles of the tabs the tree before K47 did not have are
    # English there, and the English ones are in the list anyway
    titles["de"] = sorted(set(titles["de"]) | set(TITLES["en"]))
    res = {}
    for lang in ("en", "de"):
        for pdf in sorted((proof / "runs/after" / lang).glob("*.pdf")):
            tag = pdf.stem
            before = proof / "runs/before" / lang / pdf.name
            r = {"after": analyse(pdf, titles[lang])}
            render(pdf, r["after"]["graph_pages"], proof / "pages" / tag,
                   "after")
            if before.is_file():
                r["before"] = analyse(before, titles[lang])
                render(before, r["before"]["graph_pages"],
                       proof / "pages" / tag, "before")
            res[tag] = r
    (proof / "compare.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# K47: the graphs and what is printed under them, before and after",
          ""]
    for tag, r in res.items():
        md.append(f"## {tag}")
        for side in ("before", "after"):
            if side not in r:
                continue
            md.append(f"### {side} ({r[side]['pages']} pages)")
            for g in r[side]["graphs"]:
                md.append(f"* p{g['page']} **{g['title']}**")
                for t in g["text"]:
                    md.append(f"  * {t}")
        md.append("")
    (proof / "compare.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(res)} cases compared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
