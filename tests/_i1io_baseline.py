"""THE i1iO CHARTS OF 4.3.65, AS THEY WERE: the cases and the digests.

The new i1iO chart layout must not change a one-piece standard chart. This
module builds a fixed list of i1iO charts (fixed patch set, shuffle seed and
date) through the app's own kwargs (Guided: `ChartCreator._engine_kwargs`,
Manual: the recipe's `build_kwargs`) and makes a digest of every file. The
digests of the GEOMETRY files of release 4.3.65 are stored in
``tests/data/i1io_baseline_4365.json`` (`test_i1io_baseline_4365.py` compares);
the whole files of that release, TIFF and PDF included, are kept outside the
repository and compared by the maintainer's ``baseline.py``, which loads this
file too. It needs nothing but the tree it is run in.

What a digest leaves out: the ``CREATED`` line of a ``.ti2`` and the
``table_facts`` block of the side file (it is allowed to change: it names the
facts, not the sheet), and the recipe's ``i1io_limits`` marker, which recipes
made from now on carry. The repository's digests also leave out what a font
decides (``wordmark_mm``, ``text_line``, ``label_band_bottom_px``), because
fonts differ between machines; the outside comparison does not.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

SEED = 4365
CHART_DATE = "2026-01-01"
DPI = 150

#: Every sheet 4.3.65 lays an i1iO chart out on that differs in a rule: A4 and
#: Letter, the small listed sheets, the largest inside the reach, and a strip.
PAPERS = ("A4", "Letter", "203x254", "148x210", "127x178", "4x6", "230x320",
          "216x310", "60x297")


def _xyz(rgb):
    """sRGB (0..100) to XYZ, D50-ish scale: only a plausible expected colour."""
    lin = []
    for v in rgb:
        c = v / 100.0
        lin.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin
    return (100 * (0.4361 * r + 0.3851 * g + 0.1431 * b),
            100 * (0.2225 * r + 0.7169 * g + 0.0606 * b),
            100 * (0.0139 * r + 0.0971 * g + 0.7141 * b))


def write_ti1(path: Path, n: int, rep: str = "RGB", ramps: bool = False) -> Path:
    rnd = random.Random(SEED)
    fields = {"RGB": ["RGB_R", "RGB_G", "RGB_B"],
              "CMYK": ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]}[rep]
    rows = []
    if ramps:
        # targen's pure ramp set: the white, then every channel's own ramp
        rows.append([100.0] * len(fields))
        steps = max(2, (n - 1) // len(fields))
        for k in range(len(fields)):
            for i in range(1, steps + 1):
                dev = [100.0] * len(fields)
                dev[k] = round(100.0 - 100.0 * i / steps, 4)
                rows.append(dev)
    else:
        rows.append([100.0] * 3 if rep == "RGB" else [0.0] * 4)
        while len(rows) < n:
            rows.append([round(rnd.uniform(0, 100), 4) for _ in fields])
    body = []
    for i, dev in enumerate(rows, 1):
        rgb = dev if rep == "RGB" else [
            (100 - dev[j]) * (100 - dev[3]) / 100.0 for j in range(3)]
        body.append("%d " % i + " ".join("%.4f" % v for v in dev)
                    + " " + " ".join("%.4f" % v for v in _xyz(rgb)))
    path.write_text(
        'CTI1\n\nDESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        'APPROX_WHITE_POINT "96.422 100.0 82.521"\n'
        + ('SINGLE_DIM_STEPS "%d"\n' % (n // len(fields)) if ramps else "")
        + 'COLOR_REP "%s"\n\nNUMBER_OF_FIELDS %d\nBEGIN_DATA_FORMAT\n'
          "SAMPLE_ID %s XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
          "NUMBER_OF_SETS %d\nBEGIN_DATA\n%s\nEND_DATA\n"
        % (rep, len(fields) + 4, " ".join(fields), len(body), "\n".join(body)),
        encoding="utf-8")
    return path


def cases() -> "dict[str, dict]":
    """``{name: {"door", "paper", "count", ...}}``. *count* "page" is one full
    page, a number that many patches. *recipe* are LayoutRecipe fields set by
    hand, *params* ChartParams fields."""
    out: "dict[str, dict]" = {}

    def add(name, **kw):
        out[name] = {"door": "manual", "paper": "A4", "count": "page",
                     "rep": "RGB", "recipe": {}, "params": {}, **kw}

    for paper in PAPERS:
        tag = paper.replace("x", "by")
        add(f"guided_{tag}", door="guided", paper=paper)
        add(f"manual_{tag}", paper=paper)
        add(f"manual_{tag}_nocross", paper=paper,
            recipe={"i1io_crosses": False})
    for paper in ("A4", "Letter"):
        add(f"guided_{paper}_two_pages", door="guided", paper=paper, count=700)
        add(f"guided_{paper}_nocross", door="guided", paper=paper,
            params={"i1io_crosses": False})
        add(f"guided_{paper}_clip", door="guided", paper=paper,
            params={"i1io_clip_border": True})
        add(f"manual_{paper}_bw", paper=paper, recipe={"spacer_mode": "bw"})
        add(f"manual_{paper}_none", paper=paper,
            recipe={"spacer_mode": "none", "spacer_on": False})
        add(f"manual_{paper}_clip", paper=paper,
            recipe={"i1io_clip_border": True, "clip_content_mode": "notes"})
        add(f"manual_{paper}_nolabels", paper=paper,
            recipe={"show_strip_indicators": False,
                    "show_row_indicators": False})
        add(f"manual_{paper}_noletters", paper=paper,
            recipe={"show_strip_indicators": False})
        add(f"manual_{paper}_89x8", paper=paper, recipe={"patch_h_mm": 8.9})
        add(f"manual_{paper}_12x10", paper=paper,
            recipe={"patch_h_mm": 12.0, "patch_w_mm": 10.0})
        add(f"manual_{paper}_label6", paper=paper,
            recipe={"indicator_size_mm": 6.0})
        add(f"manual_{paper}_gaps", paper=paper,
            recipe={"inter_patch_mm": 1.0, "strip_gap_mm": 1.5,
                    "spacer_width_mm": 1.5})
        add(f"manual_{paper}_edge_spacers", paper=paper,
            recipe={"edge_spacers": True})
        add(f"manual_{paper}_sheet_text", paper=paper,
            recipe={"chart_text": "Paper {paper}, {patchcount} patches, "
                                  "page {page}"}, count=700)
        add(f"manual_{paper}_cmyk", paper=paper, rep="CMYK")
        add(f"manual_{paper}_16bit", paper=paper, recipe={"bit16": True},
            count=200)
        add(f"manual_{paper}_pdf", paper=paper, recipe={"export_pdf": True},
            count=200)
        add(f"manual_{paper}_calibration", paper=paper, count=96, ramps=True,
            params={"cal_target": True})
        add(f"guided_{paper}_calibration", door="guided", paper=paper,
            count=96, ramps=True, params={"cal_target": True})
        add(f"manual_{paper}_verification", paper=paper, count=150,
            params={"target_name": "Proof-verify"})
    return out


class _FileMgr:
    """The little of a FileManager a chart's sidecar needs."""


def _creator():
    """A `ChartCreator` that only works out kwargs and writes side files."""
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
    from workflow.layout_engine import (chart, geometry, instruments, papers,
                                        presets)
    out.mkdir(parents=True, exist_ok=True)
    recipe = None
    if spec["door"] == "manual":
        recipe = presets.default_recipe("IO2", spec["paper"])
        recipe = replace(recipe, dpi=DPI, seed=SEED, **spec["recipe"])
    params = ChartParams(instrument="IO2", paper=spec["paper"],
                         is_manual=recipe is not None, tiff_dpi=DPI,
                         layout_recipe=recipe, chart_date=CHART_DATE,
                         **{"target_name": "Proof", **spec["params"]})
    creator = _creator()
    kw = creator._engine_kwargs(params)
    kw["seed"], kw["chart_date"] = SEED, CHART_DATE
    if tweak is not None:
        kw = tweak(dict(kw)) or kw
    count = spec["count"]
    if count == "page":
        geom = instruments.geom_from_build_kwargs(kw)
        w, h = papers.dimensions_mm(kw["paper"])
        count = geometry.patches_per_sheet(geom, w, h)
    stem = "chart"
    ti1 = write_ti1(out / f"{stem}.ti1", int(count), spec["rep"],
                    bool(spec.get("ramps")))
    result = chart.build_chart(ti1, out / stem, label_rule="argyll",
                               ramps_per_strip=bool(params.cal_target), **kw)
    creator._write_channel_sidecar(out, stem, params, engine="chromiq")
    # the geometry files are kept as they are: `_embed_layout_geometry` folds
    # strips.json into channels.json and removes it
    strips = (out / f"{stem}.strips.json").read_bytes()
    creator._embed_layout_geometry(out, stem, result, params)
    (out / f"{stem}.strips.json").write_bytes(strips)
    return sorted(p for p in out.iterdir() if p.is_file())


#: What a font decides, left out of the repository's digests (dropped from the
#: pages of the side file, and from the strips file).
FONT_KEYS = ("wordmark_mm", "text_line", "label_band_bottom_px")


def _drop(doc, keys):
    if isinstance(doc, dict):
        return {k: _drop(v, keys) for k, v in doc.items() if k not in keys}
    if isinstance(doc, list):
        return [_drop(v, keys) for v in doc]
    return doc


def digest(p: Path, fonts: bool = True) -> str:
    """The SHA-256 of *p* without its clock and without ``table_facts``; with
    *fonts* False also without what a font decides."""
    data = p.read_bytes()
    if p.suffix in (".ti1", ".ti2"):
        data = b"\n".join(ln for ln in data.replace(b"\r\n", b"\n").split(b"\n")
                          if not ln.startswith(b"CREATED "))
    elif p.suffix == ".json":
        doc = json.loads(data.decode("utf-8"))
        # the facts block names the facts behind a sheet, not the sheet
        # ...and a recipe made from now on says which limits it was made under
        # (`i1io_limits`, the new chart layout); 4.3.65's had no such key
        doc = _drop(doc, () if fonts else FONT_KEYS)
        if p.name == "chart.channels.json":
            # only there, only in the recipe, and only with today's value
            recipe = (doc.get("layout") or {}).get("recipe")
            if isinstance(recipe, dict) and recipe.get("i1io_limits") == 2:
                del recipe["i1io_limits"]
                # ...and a Guided one without crosses says the margins it was
                # laid out to (item 60); 4.3.65's said 6 mm, the only change
                if (recipe.get("i1io_crosses") is False and
                        doc["layout"].get("margins_chosen_by_user") is False):
                    for side in ("top", "right", "bottom", "left"):
                        recipe[f"margin_{side}"] = 6.0
        if isinstance(doc, dict):
            doc.pop("table_facts", None)
        data = json.dumps(doc, indent=0, sort_keys=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


#: The files whose digests the repository keeps (no pixels, no PDF).
GEOMETRY_FILES = ("chart.ti2", "chart.i1io.json", "chart.strips.json",
                  "chart.channels.json")
