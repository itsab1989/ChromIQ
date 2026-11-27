"""THE i1iSis CHARTS OF 4.3.67 ON PAPERS THAT FIT, AS THEY WERE (step 0 of
the i1iSis pieces work, challenge S7).

The pieces work changes what happens on a sheet the model cannot feed as
printed. On every paper it CAN feed nothing has a reason to change, so a
difference there is a fault. This module builds a fixed list of i1iSis charts
(fixed patch set, seed and date) through the app's own kwargs (Guided:
`ChartCreator._engine_kwargs`, Manual: the recipe's `build_kwargs`), writes
the chart's sidecars as Create Chart does (`chart_exports.write_sidecars`:
colour list, i1Profiler pair, the i1iSis ``.txf`` and its order file) and
makes a digest of every file. The digests of the GEOMETRY files of 4.3.67
are stored in ``tests/data/isis_baseline_4367.json``
(`test_isis_baseline_4367.py` compares); the whole files, page TIFFs
included, are kept outside the repository and compared by the maintainer's
script, which loads this module too.

What a digest leaves out: the ``CREATED`` line of a ``.ti1`` / ``.ti2``, the
``creationDate`` of an i1Profiler file and the order file's chart checksum
(it follows the ``CREATED`` line). The repository's digests also leave out
what a font decides (``wordmark_mm``, ``text_line``, ``text_ink``), because
fonts differ between machines; the outside comparison does not.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import _i1io_baseline as io

SEED = 4367
CHART_DATE = "2026-01-01"
DPI = 100

#: The papers each model feeds as printed (the challenge's S7 list).
PAPERS = {
    "standard": ("A4", "Letter", "148x210", "127x178", "203x254", "Legal"),
    "xl": ("A4", "Letter", "148x210", "127x178", "203x254", "Legal", "A3",
           "279x432", "305x457", "329x483"),
}
#: Guided's own lists (`workflow.isis.chart.GUIDED_PAPERS`, ``_XL``).
GUIDED = {
    "standard": ("A4", "Letter", "148x210", "127x178", "203x254"),
    "xl": ("A4", "Letter", "148x210", "127x178", "203x254", "A3", "279x432",
           "329x483"),
}


def cases() -> "dict[str, dict]":
    """``{name: {"door", "model", "paper", "count", ...}}``. *count* "page"
    is one full page, "pages" a page and a half, a number that many
    patches."""
    out: "dict[str, dict]" = {}

    def add(name, **kw):
        out[name] = {"door": "manual", "paper": "A4", "count": "page",
                     "rep": "RGB", "recipe": {}, "params": {},
                     "randomize": True, **kw}

    for model in ("standard", "xl"):
        for paper in GUIDED[model]:
            tag = f"{model}_{paper.replace('x', 'by')}"
            add(f"guided_{tag}", door="guided", model=model, paper=paper)
        for paper in PAPERS[model]:
            tag = f"{model}_{paper.replace('x', 'by')}"
            # Manual keeps the person's margins: on 5 x 7 in they must be
            # made smaller by hand, as a person would (M-ISIS-SHEET-CHECK)
            short = ({"margin_top": 3.4, "margin_bottom": 3.4}
                     if paper == "127x178" else {})
            add(f"manual_{tag}", model=model, paper=paper, recipe=short)
        for paper in ("A4", "Letter"):
            tag = f"{model}_{paper}"
            add(f"guided_{tag}_two_pages", door="guided", model=model,
                paper=paper, count="pages")
            add(f"guided_{tag}_ordered", door="guided", model=model,
                paper=paper, randomize=False)
            add(f"guided_{tag}_ordered_two_pages", door="guided",
                model=model, paper=paper, randomize=False, count="pages")
            add(f"manual_{tag}_ordered_three_pages", model=model, paper=paper,
                randomize=False, count=2600)
            add(f"manual_{tag}_16bit", model=model, paper=paper,
                recipe={"bit16": True}, count=300)
            add(f"manual_{tag}_cmyk", model=model, paper=paper, rep="CMYK",
                count=400)
            add(f"manual_{tag}_barcode", model=model, paper=paper,
                recipe={"isis_barcode": True})
            add(f"manual_{tag}_tight", model=model, paper=paper,
                recipe={"isis_tight": True}, count=500)
            add(f"manual_{tag}_8mm", model=model, paper=paper,
                recipe={"patch_w_mm": 8.0, "patch_h_mm": 8.0})
            add(f"guided_{tag}_notes", door="guided", model=model,
                paper=paper, params={"isis_notes_band": True}, count=500)
            add(f"manual_{tag}_calibration", model=model, paper=paper,
                count=96, ramps=True, params={"cal_target": True})
    return out


class _FileMgr:
    """The little of a FileManager a chart's sidecar needs."""


def _creator():
    from workflow.chart_creator import ChartCreator
    c = ChartCreator.__new__(ChartCreator)
    c._runner, c._file_mgr = None, _FileMgr()
    c._settings = {"use_chromiq_layout_engine": True}
    c._pending_patch_count = 0
    return c


def build_case(name: str, spec: dict, out: Path, tweak=None) -> "list[Path]":
    """Build case *name* into *out* (a new folder) and return its files.
    *tweak*(kwargs) may change the build kwargs (a planted fault)."""
    from dataclasses import replace

    from workflow.chart_creator import ChartParams
    from workflow.chart_exports import write_sidecars
    from workflow.isis.chart import capacity
    from workflow.layout_engine import chart, presets
    out.mkdir(parents=True, exist_ok=True)
    recipe = None
    model = "xl" if spec["model"] == "xl" else ""
    if spec["door"] == "manual":
        recipe = presets.default_recipe("XRISIS", spec["paper"])
        recipe = replace(recipe, dpi=DPI, seed=SEED, isis_model=model,
                         randomize=spec["randomize"], **spec["recipe"])
    params = ChartParams(instrument="XRISIS", paper=spec["paper"],
                         is_manual=recipe is not None, tiff_dpi=DPI,
                         layout_recipe=recipe, chart_date=CHART_DATE,
                         isis_model=model,
                         no_randomise=not spec["randomize"],
                         **{"target_name": "Proof", **spec["params"]})
    creator = _creator()
    kw = creator._engine_kwargs(params)
    kw["seed"], kw["chart_date"] = SEED, CHART_DATE
    if tweak is not None:
        kw = tweak(dict(kw)) or kw
    count = spec["count"]
    if count in ("page", "pages"):
        one = capacity(kw)
        count = one if count == "page" else one + one // 2
    stem = "chart"
    ti1 = io.write_ti1(out / f"{stem}.ti1", int(count), spec["rep"],
                       bool(spec.get("ramps")))
    result = chart.build_chart(ti1, out / stem, label_rule="argyll",
                               ramps_per_strip=bool(params.cal_target), **kw)
    creator._write_channel_sidecar(out, stem, params, engine="chromiq")
    creator._embed_layout_geometry(out, stem, result, params)
    write_sidecars(ti1, out / "exports", stem)
    return sorted(p for p in out.rglob("*") if p.is_file())


#: What a font decides, left out of the repository's digests.
FONT_KEYS = ("wordmark_mm", "text_line", "text_ink", "label_band_bottom_px")
_CLOCK = re.compile(rb'(creationDate|CreationDate)="[^"]*"')
_CLOCK_EL = re.compile(rb"<cc:CreationDate>[^<]*</cc:CreationDate>")


def digest(p: Path, fonts: bool = True) -> str:
    """The SHA-256 of *p* without its clocks; with *fonts* False also
    without what a font decides."""
    data = p.read_bytes()
    if p.suffix in (".ti1", ".ti2", ".ti3", ".txt", ".cht"):
        data = b"\n".join(ln for ln in data.replace(b"\r\n", b"\n").split(b"\n")
                          if not ln.startswith(b"CREATED ")
                          and not ln.startswith(b'CREATED\t'))
    elif p.suffix in (".txf", ".pxf", ".mxf"):
        data = _CLOCK_EL.sub(b"<cc:CreationDate/>", _CLOCK.sub(b"", data))
    elif p.suffix == ".json":
        doc = json.loads(data.decode("utf-8"))
        doc = io._drop(doc, () if fonts else FONT_KEYS)
        if isinstance(doc, dict):
            doc.pop("chart_sha256", None)
        data = json.dumps(doc, indent=0, sort_keys=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def relname(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


#: The files whose digests the repository keeps (no pixels).
def geometry_files(root: Path) -> "list[str]":
    keep = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in (".ti2", ".json", ".txf", ".pxf",
                                         ".txt", ".cht"):
            keep.append(relname(p, root))
    return keep


# ---------------------------------------------------------------------------
# The import verdicts of 4.3.67 (one page and several, randomised or not)
# ---------------------------------------------------------------------------

#: Chart sets of `test_isis_import_not_randomised` the verdicts are taken on.
IMPORT_SETS = ("random60", "random900", "sorted", "grid6", "grid9", "cal",
               "ramps", "grey", "even", "few", "refine", "pages")


def import_cases(root: Path) -> "dict[str, tuple]":
    """``{case: (ok, reason, partial, turned_order, isis_ask_why)}`` for
    every chart set, randomised or not, read right and every wrong way the
    item 63 tests know, with and without the order file. Built in *root*."""
    import shutil

    from test_isis_import_not_randomised import CHARTS, Chart

    from workflow.measurement_import import assess
    out = {}
    for name in IMPORT_SETS:
        for randomize in (False, True):
            c = Chart(root / f"{name}-{randomize}", CHARTS[name], randomize)
            ways = {"right": None, **c.ways()}
            k = c.R * c.C
            if c.P > 1:
                ways["pages swapped"] = [
                    (j + k if j + k < c.n else j) if j < k else j - k
                    for j in range(c.n)]
                ways["page twice"] = [j if j < k else j - k
                                      for j in range(c.n)]
            for way, p in ways.items():
                for order in ("order", "no order"):
                    if order == "no order":
                        moved = c.order_file.with_suffix(".away")
                        c.order_file.rename(moved)
                    try:
                        m = c.measure(root / "m.ti3", p)
                        v = assess(m, c.ti2)
                    finally:
                        if order == "no order":
                            moved.rename(c.order_file)
                    out[f"{name}|{randomize}|{way}|{order}"] = (
                        bool(v.ok), v.reason, bool(v.partial),
                        bool(v.turned_order), v.isis_ask_why, c.P)
            shutil.rmtree(c.folder, ignore_errors=True)
    return out
