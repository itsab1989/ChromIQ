"""Build a **scanner-recognition target** (``.cht`` + ``.cie``) from a measured
chart, so ArgyllCMS ``scanin`` can read the printed chart off a flatbed scan and
``colprof`` can turn that into a scanner input profile (#97).

The two halves and how they line up:

* ``.cht`` (:mod:`~workflow.layout_engine.cht_writer`) — *where* every patch
  sits on the page, per page, plus an ``F`` fiducial line for ``scanin -F``.
  Geometry comes from the engine's exact ``channels.json["layout"]["patches"]``
  (top-left px), flipped to the ``.cht``'s bottom-left mm.
* ``.cie`` (:mod:`~workflow.layout_engine.cie_writer`) — *what colour* every
  patch truly is, the **measured** XYZ from the run's ``.ti3``.

Both are keyed by the patch **loc** (``A01`` …): the ``.cht`` box loc, the
``.cie`` ``SAMPLE_ID`` and the ``.ti3`` ``SAMPLE_LOC`` are one and the same
because they all come from the engine's single permutation. We *assert* that
alignment and fail loudly rather than let ``scanin`` misregister silently.

Multi-page charts get one ``.cht`` **per page** (``<stem>_01.cht`` …) and a
single whole-chart ``.cie`` (a superset the per-page ``.cht`` indexes into).

This module needs only data ChromIQ already holds — the engine geometry and the
measurement — so it never calls an Argyll binary. It requires an **engine**
chart (an exact ``layout`` block); inferring geometry for older/printtarg charts
from the ``.ti2`` is a separate, validated follow-up (#97 item 7). The ``.cie``
half, by contrast, works from *any* measured ``.ti3``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.stem_paths import artefact

from workflow.layout_engine import cht_writer, cie_writer
from workflow.ti3_analysis import Ti3Data, parse_ti3


class ScaninTargetError(ValueError):
    """Base for scanner-target build failures (all carry a user-facing message)."""


class NotAnEngineChart(ScaninTargetError):
    """The chart has no exact engine geometry, so a trustworthy ``.cht`` can't be
    built from it yet (older / imported / printtarg chart — see #97 item 7)."""


class GeometryMismatch(ScaninTargetError):
    """The measured ``.ti3`` doesn't line up with the chart geometry (a patch is
    missing a measurement, or vice-versa) — refuse rather than misregister."""


@dataclass
class ScaninTargetResult:
    cht_paths: list[Path]      # one per page
    cie_path: Path
    n_patches: int
    n_pages: int


def _load_scanner_layout(channels_json: str | Path) -> dict:
    """Return the ``layout`` block for a chart ChromIQ can build a scanner target
    from — either an **engine** chart (``engine=="chromiq"`` with exact
    ``patches``) or a **printtarg** chart whose exact ``.cht`` geometry was
    captured at creation (``engine=="printtarg"`` with ``cht_pages``). Raises
    :class:`NotAnEngineChart` otherwise."""
    p = Path(channels_json)
    if not p.is_file():
        raise NotAnEngineChart(
            "This chart has no layout sidecar, so ChromIQ doesn't know where "
            "its patches sit. ChromIQ looks for <chart>.channels.json next to "
            "the file you pick — the names must match, as saved when the chart "
            "was created. Measure a chart created with ChromIQ and its scanner "
            "files can be built from it.")
    try:
        layout = json.loads(p.read_text()).get("layout") or {}
    except (OSError, ValueError) as exc:
        raise NotAnEngineChart(f"Couldn't read the chart layout: {exc}") from exc
    engine = layout.get("engine")
    # "chromiq" = the engine's own exact geometry; "derived" = the same schema
    # recovered from the rendered TIFF + .ti2 (workflow.layout_from_render) for
    # charts whose creation left no geometry (prebuilt bundles, discarded -s
    # captures). Both carry per-patch px rects → the engine .cht path.
    if engine in ("chromiq", "derived") and layout.get("patches") \
            and "dpi" in layout and "paper_mm" in layout:
        return layout
    if engine == "printtarg" and layout.get("cht_pages"):
        return layout
    raise NotAnEngineChart(
        "ChromIQ doesn't have this chart's exact patch positions, so it can't "
        "build scanner files from it. Recreate the chart in a current ChromIQ "
        "version and this will work automatically.")


# Back-compat alias (older callers / tests).
_load_engine_layout = _load_scanner_layout


def _cht_x_box_locs(cht_text: str) -> list[str]:
    """The patch (``X``) box locations of a printtarg ``.cht`` — its ``F``
    fiducial and ``D`` marker/ID boxes are skipped."""
    return [ln.split()[1] for ln in cht_text.splitlines()
            if ln.strip().startswith("X ")]


def layout_from_cht_files(cht_paths: list, ref_path: str | Path) -> dict:
    """A printtarg-shaped layout block from user-supplied ``.cht`` page files,
    validated against the chart's ``.ti2``/``.ti3`` (#105).

    For charts made outside ChromIQ (e.g. a manual ``printtarg -s`` run) there
    is no ``channels.json`` — but printtarg's own per-page ``.cht`` files carry
    the exact geometry. This builds the same ``{"engine": "printtarg",
    "cht_pages": …, "locs": …}`` dict the creation-time capture stores, so the
    whole downstream pipeline (grid overlay, per-page ``.cht``, scanin) treats
    the chart like a captured one. Pages follow the order of *cht_paths* (sort
    by filename before calling — printtarg numbers them ``_01 … _NN``).

    Raises :class:`ScaninTargetError` when a file isn't a patch ``.cht``, when
    pages overlap, or when the combined patch locations don't exactly cover the
    reference — a wrong or missing page would silently profile from partial
    data otherwise.
    """
    texts: list[str] = []
    geom_locs: list[str] = []
    for p in cht_paths:
        p = Path(p)
        try:
            text = p.read_text(errors="ignore")
        except OSError as exc:
            raise ScaninTargetError(f"Couldn't read “{p.name}”: {exc}") from exc
        locs = _cht_x_box_locs(text)
        if not locs:
            raise ScaninTargetError(
                f"“{p.name}” has no patch (X) boxes — it doesn't look like a "
                "printtarg/scanin .cht file.")
        texts.append(text)
        geom_locs += locs
    data: Ti3Data = parse_ti3(ref_path)
    geom_set, ref_set = set(geom_locs), set(data.sample_locs)
    if len(geom_set) != len(geom_locs):
        raise ScaninTargetError(
            "The .cht files overlap — the same patch location appears on more "
            "than one page. Pick each page's .cht exactly once.")
    missing = ref_set - geom_set
    if missing:
        raise ScaninTargetError(
            f"The .cht files don't cover the whole chart: {len(missing)} "
            f"patch(es) of the reference have no box (e.g. "
            f"{sorted(missing)[:3]}). Did you pick every page's .cht?")
    extra = geom_set - ref_set
    if extra:
        raise ScaninTargetError(
            f"The .cht files don't belong to this chart: {len(extra)} box(es) "
            f"have no patch in the reference (e.g. {sorted(extra)[:3]}). Pick "
            "the .cht files printtarg wrote for exactly this chart.")
    return {"engine": "printtarg", "cht_pages": texts, "locs": geom_locs}


def build_scanin_target_from_cht_files(cht_paths: list, ref_path: str | Path,
                                       out_base: str | Path):
    """One-call worker for user-supplied ``.cht`` pages (#105): validate them
    against the reference (:func:`layout_from_cht_files`), then write the
    per-page ``<out_base>[_NN].cht`` + ``<out_base>.cie`` exactly like the
    captured-printtarg path. Returns ``(layout, ScaninTargetResult)``."""
    layout = layout_from_cht_files(cht_paths, ref_path)
    res = _build_from_printtarg(layout, parse_ti3(ref_path), Path(out_base))
    return layout, res


def _check_measured(geom_locs: list[str], data: Ti3Data) -> None:
    """Assert every geometry loc has a measurement (the loc-alignment guarantee),
    raising :class:`GeometryMismatch` on a duplicate or an unmeasured patch."""
    geom_set = set(geom_locs)
    if len(geom_set) != len(geom_locs):
        raise GeometryMismatch("The chart geometry has duplicate patch locations.")
    missing = geom_set - set(data.sample_locs)
    if not missing:
        return
    # A .ti3 converted from an i1Profiler measurement (txt2ti3) carries the
    # exported SampleID in SAMPLE_LOC — plain numbers — instead of the chart's
    # "A1"/"B2" patch locations, so EVERY patch reads as unmeasured. Say that,
    # rather than let it look like a corrupt measurement (#120).
    if data.sample_locs and all(loc.strip().isdigit()
                                for loc in data.sample_locs):
        raise GeometryMismatch(
            "This .ti3 numbers its patches (1, 2, 3, …) instead of naming "
            "their positions on the chart (A1, B2, …), so ChromIQ cannot tell "
            "which patch each measurement belongs to. That is what you get "
            "from converting an i1Profiler measurement (Tools → Convert "
            "i1Profiler → TI3). Such a measurement still builds a PRINTER "
            "profile — load it in Build Profile — but a scanner/camera target "
            "additionally needs to know where each patch sits on the sheet. "
            "Measure this chart with ChromIQ (Measure tab) and build the "
            "target from that .ti3.")
    raise GeometryMismatch(
        f"{len(missing)} chart patch(es) have no measurement — the .ti3 "
        f"doesn't match this chart (e.g. {sorted(missing)[:3]}). Re-measure "
        "the whole chart before building scanner files.")


def build_scanin_target_from_paths(channels_json: str | Path, ti3_path: str | Path,
                                   out_base: str | Path) -> ScaninTargetResult:
    """Core worker: from a chart's ``channels.json`` + a measured ``.ti3``, write
    per-page ``<out_base>[_NN].cht`` and one ``<out_base>.cie``. *out_base* is a
    path without extension (e.g. ``run.dir / run.stem``). Overwrites any existing
    pair, so it always reflects the latest measurement. Handles both engine and
    printtarg charts (:func:`_load_scanner_layout`).
    """
    layout = _load_scanner_layout(channels_json)
    data: Ti3Data = parse_ti3(ti3_path)
    out_base = Path(out_base)
    if layout.get("engine") == "printtarg":
        return _build_from_printtarg(layout, data, out_base)

    patches: list[dict] = layout["patches"]
    dpi = int(layout["dpi"])
    paper_h_mm = float(layout["paper_mm"][1])
    measured = {loc: (float(x), float(y), float(z))
                for loc, (x, y, z) in zip(data.sample_locs, data.xyz)}
    geom_locs = [p["loc"] for p in patches]
    _check_measured(geom_locs, data)

    pages = sorted({int(p.get("page", 0)) for p in patches})
    single = len(pages) == 1
    cht_paths: list[Path] = []
    for pg in pages:
        boxes = cht_writer.boxes_from_patch_rects(patches, paper_h_mm, dpi, page=pg)
        expected = [(b["loc"], *measured[b["loc"]]) for b in boxes]
        # `out_base` is a project-name STEM and may contain a dot
        # ("…-w10.0mm"), which with_suffix() would eat — see core/stem_paths.py.
        cht = (artefact(out_base, ".cht") if single
               else out_base.parent / f"{out_base.name}_{pg + 1:02d}.cht")
        cht_paths.append(cht_writer.write_cht(cht, boxes, expected))

    cie_path = cie_writer.write_cie(artefact(out_base, ".cie"), data,
                                    descriptor=out_base.name)
    return ScaninTargetResult(cht_paths=cht_paths, cie_path=cie_path,
                              n_patches=len(geom_locs), n_pages=len(pages))


def _build_from_printtarg(layout: dict, data: Ti3Data,
                          out_base: Path) -> ScaninTargetResult:
    """Write the stored printtarg ``.cht`` page(s) verbatim (exact geometry +
    fiducials, captured at creation) and build the measured ``.cie``. The stored
    ``.cht`` is seed-independent geometry, so it matches the printed sheet; we
    still assert its locs against the measurement."""
    cht_pages: list[str] = layout["cht_pages"]
    geom_locs: list[str] = []
    for text in cht_pages:
        geom_locs += _cht_x_box_locs(text)
    _check_measured(geom_locs, data)

    single = len(cht_pages) == 1
    cht_paths: list[Path] = []
    for i, text in enumerate(cht_pages):
        cht = (artefact(out_base, ".cht") if single
               else out_base.parent / f"{out_base.name}_{i + 1:02d}.cht")
        cht.write_text(text, encoding="utf-8")
        cht_paths.append(cht)
    cie_path = cie_writer.write_cie(artefact(out_base, ".cie"), data,
                                    descriptor=out_base.name)
    return ScaninTargetResult(cht_paths=cht_paths, cie_path=cie_path,
                              n_patches=len(set(geom_locs)), n_pages=len(cht_pages))


def _ordered_rgb100(patch_set_path: str | Path):
    """The exported patch list as ``(N, 3)`` device RGB 0..100 **in list order**
    (= i1Profiler's column-major fill order), from any of the formats ChromIQ
    hands to i1Profiler: a ``.ti1``, a CGATS ``.txt`` or a CxF ``.pxf``. Raises
    :class:`ScaninTargetError` on an unreadable or non-RGB set."""
    import numpy as np

    p = Path(patch_set_path)
    try:
        if p.suffix.lower() == ".ti1":
            from workflow.i1profiler_export import parse_ti1
            target = parse_ti1(p)
            if target.kind != "RGB":
                raise ScaninTargetError(
                    "Only RGB charts can be built into a scanner target; this "
                    f"patch set is {target.kind}.")
            rgb = [[vals["R"], vals["G"], vals["B"]] for _sid, vals in target.rows]
        else:
            from workflow.i1profiler_import import parse_cgats, parse_pxf
            patches = (parse_pxf(p) if p.suffix.lower() == ".pxf"
                       else parse_cgats(p))
            rgb = [[pt.r, pt.g, pt.b] for pt in patches]
    except ScaninTargetError:
        raise
    except (OSError, ValueError) as exc:
        raise ScaninTargetError(
            f"Couldn't read the patch set “{p.name}”: {exc}") from exc
    if not rgb:
        raise ScaninTargetError(f"The patch set “{p.name}” has no patches.")
    return np.asarray(rgb, dtype=float)


def build_scanin_target_from_render(patch_set_path: str | Path, tiff_paths: list,
                                    ti3_path: str | Path, out_base: str | Path,
                                    ) -> ScaninTargetResult:
    """Build a scanner target for a chart **i1Profiler laid out** (#120).

    ChromIQ has no ``channels.json`` for such a chart — i1Profiler ignores the
    positions a ``.pwxf`` carries and re-lays the grid itself. So the geometry is
    recovered from the chart i1Profiler saved as a TIFF
    (:func:`workflow.grid_layout_from_render.derive_grid_layout`), using the
    exported patch set for the fill order and colour verification, then the
    ``.cht``/``.cie`` are built from that geometry + the measurement exactly like
    an engine chart.

    * *patch_set_path* — the patch set handed to i1Profiler (``.ti1`` / ``.txt``
      / ``.pxf``); its order is i1Profiler's column-major fill order.
    * *tiff_paths* — the chart page(s) i1Profiler saved, in print order.
    * *ti3_path* — the measurement of the printed sheet. Its ``SAMPLE_LOC`` must
      be the patch numbers (``1…N``) — which is what ``txt2ti3`` writes from an
      i1Profiler measurement (Tools → Convert i1Profiler → TI3).
    * *out_base* — output stem (no extension). A ``<out_base>.channels.json`` is
      written alongside so the chart is re-usable without re-deriving.

    Returns a :class:`ScaninTargetResult`. Raises :class:`ScaninTargetError`
    (incl. :class:`~workflow.grid_layout_from_render.GridGeometryError`) if the
    geometry can't be recovered or the measurement doesn't line up.
    """
    from workflow.grid_layout_from_render import (
        GridGeometryError, derive_grid_layout,
    )

    if not tiff_paths:
        raise ScaninTargetError("No chart TIFF was given to read the layout from.")
    rgb100 = _ordered_rgb100(patch_set_path)
    locs = [str(i + 1) for i in range(len(rgb100))]
    try:
        layout = derive_grid_layout(list(tiff_paths), rgb100, locs=locs)
    except GridGeometryError as exc:
        raise ScaninTargetError(str(exc)) from exc

    out_base = Path(out_base)
    channels = artefact(out_base, ".channels.json")
    channels.write_text(json.dumps({"layout": layout}, indent=2), encoding="utf-8")
    return build_scanin_target_from_paths(channels, ti3_path, out_base)


def build_scanin_target(run) -> ScaninTargetResult:
    """Build the scanner target for a :class:`~core.file_manager.Run` — reads its
    chart geometry (``chart_channels_json``) + measurement (``measurement_ti3``)
    and writes the pair next to the chart (``<stem>.cht`` / ``<stem>.cie``)."""
    ti3 = run.measurement_ti3
    if not Path(ti3).is_file():
        raise ScaninTargetError(
            "This chart hasn't been measured yet — measure it first, then ChromIQ "
            "can build scanner files from the measurement.")
    return build_scanin_target_from_paths(run.chart_channels_json, ti3,
                                          Path(run.dir) / run.stem)


def has_scanner_geometry(channels_json: str | Path) -> bool:
    """True if ChromIQ has this chart's exact patch geometry (engine ``patches``
    *or* a captured printtarg ``.cht``) — the gate for *offering* the
    scanner-target option (the ``.ti3`` need not exist yet, so it can be shown
    right after measuring, before the file is finalised). Never raises."""
    try:
        _load_scanner_layout(channels_json)
    except ScaninTargetError:
        return False
    return True


# Back-compat alias — the gate now covers printtarg charts too, not just engine.
is_engine_geometry = has_scanner_geometry


def can_build_scanin_target(run) -> bool:
    """True if *run* is an engine chart with a measurement — the gate for showing
    the checkbox / enabling the Tool. Never raises."""
    try:
        _load_engine_layout(run.chart_channels_json)
    except ScaninTargetError:
        return False
    return Path(run.measurement_ti3).is_file()
