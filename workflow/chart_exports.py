"""Extra deliverable files written alongside every generated chart.

A chart build leaves the load-bearing files (``.ti1`` / ``.ti2`` / ``.tif`` /
``.cht``) in the run folder.  This module adds the *hand-off* sidecars that let
the same chart be used outside ChromIQ's own measure tab:

* ``<stem>-colours.txt`` — a plain hex list of the device RGB values, the same
  format the New-chart "paste colour values" mode reads (RGB charts only).
* ``<stem>-i1profiler.txt`` / ``.pxf`` — the i1Profiler patch set (via
  :mod:`workflow.i1profiler_export`).

Everything here is best-effort and pure-Python; callers log what was written.
"""
from __future__ import annotations

from pathlib import Path


def _parse_cgats(path: Path) -> tuple[list[str], list[list[str]]]:
    """Return (field names, data rows) from a CGATS ``.ti1``/``.ti2`` file.

    Only the file's **first** table — the patch set. An Argyll ``.ti1`` carries
    two reference tables after it, and reading straight through the file used to
    concatenate all three: the field list came out as 21 names with ``RGB_R``
    appearing three times, so the column lookup resolved to index 15 on rows
    only 7 wide, every row was skipped as malformed, and the ``-colours.txt``
    hand-off sidecar was written **empty** for every chart ChromIQ generates.
    """
    from workflow.i1profiler_import import read_first_cgats_table
    return read_first_cgats_table(Path(path))


def write_colours_txt(ti1_path: str | Path, txt_path: str | Path) -> Path | None:
    """Write a ``<stem>-colours.txt`` hex list from an RGB chart's device values.

    Returns the path, or ``None`` when the chart isn't RGB (nothing written).
    """
    ti1_path, txt_path = Path(ti1_path), Path(txt_path)
    fields, rows = _parse_cgats(ti1_path)
    idx = {f: i for i, f in enumerate(fields)}
    if not all(c in idx for c in ("RGB_R", "RGB_G", "RGB_B")):
        return None
    out = []
    for r in rows:
        try:
            rgb = [float(r[idx[c]]) for c in ("RGB_R", "RGB_G", "RGB_B")]
        except (ValueError, IndexError):
            continue
        out.append("#" + "".join(f"{max(0, min(255, round(v / 100 * 255))):02x}"
                                 for v in rgb))
    txt_path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
    return txt_path


def write_sidecars(ti1_path: str | Path, out_dir: str | Path,
                   base_name: str, also_shuffled: bool = False) -> list[Path]:
    """Write the colour list and i1Profiler pair into *out_dir*.

    Best-effort: a failure of one file logs and skips it, never raising. Returns
    the list of files actually written. The ``.cht`` is produced by the chart
    build itself (engine ``emit_cht`` / printtarg), not here.

    When *also_shuffled* is set, a patch-order-shuffled copy of the i1Profiler
    files is written too (``<base_name>-i1profiler-shuffled.pxf`` (+ ``.txt``)),
    for users who load the chart into i1Profiler and want its layout kept as-is
    rather than regenerated in patch-list order (Nelson).
    """
    import logging
    log = logging.getLogger(__name__)
    ti1_path, out_dir = Path(ti1_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if not ti1_path.is_file():
        return written

    try:
        p = write_colours_txt(ti1_path, out_dir / f"{base_name}-colours.txt")
        if p is not None:
            written.append(p)
    except OSError:
        log.warning("colour-list export failed", exc_info=True)
    try:
        from workflow.i1profiler_export import export_from_ti1
        txt, pxf = export_from_ti1(ti1_path, out_dir,
                                   base_name=f"{base_name}-i1profiler",
                                   descriptor=base_name,
                                   also_shuffled=also_shuffled)
        written += [q for q in (txt, pxf) if q is not None]
        if also_shuffled:
            for suffix in (".pxf", ".txt"):
                shuf = out_dir / f"{base_name}-i1profiler-shuffled{suffix}"
                if shuf.is_file():
                    written.append(shuf)
    except Exception:  # noqa: BLE001 — never block on the i1Profiler export
        log.warning("i1Profiler export failed", exc_info=True)
    return written
