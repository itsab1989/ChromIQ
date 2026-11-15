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


def i1profiler_device_for(ti1_path: "str | Path") -> "str | None":
    """The device i1Profiler itself names for the chart beside *ti1_path*,
    or None to keep the ``.pxf`` exactly as it has always been written.

    Only for the instruments whose Beta is on, and only then is the chart
    file read: an i1iSis chart (`workflow.isis`) gets "i1iSis" or
    "i1iSis XL" (its side file's model width), an i1iO chart (`workflow.
    i1io`) "i1iO 2", the name in i1Profiler's own shipped i1iO 2 charts.
    Every other chart keeps the long-standing default ("i1iSis"), so its
    files stay byte for byte as they were. Never raises."""
    try:
        ti2 = Path(str(ti1_path)[:-4] + ".ti2") \
            if str(ti1_path).lower().endswith(".ti1") else None
        if ti2 is None or not ti2.is_file():
            return None
        from workflow.isis.support import (chart_names_isis, device_name,
                                           isis_enabled, read_side_file)
        if isis_enabled() and chart_names_isis(ti2):
            return device_name((read_side_file(ti2) or {}).get("model"))
        from workflow.i1io.support import chart_names_i1io, i1io_enabled
        if i1io_enabled() and chart_names_i1io(ti2):
            return "i1iO 2"
    except Exception:  # noqa: BLE001 - the default name, never a failure
        return None
    return None


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
                                   also_shuffled=also_shuffled,
                                   measurement_device=i1profiler_device_for(
                                       ti1_path))
        written += [q for q in (txt, pxf) if q is not None]
        if also_shuffled:
            for suffix in (".pxf", ".txt"):
                shuf = out_dir / f"{base_name}-i1profiler-shuffled{suffix}"
                if shuf.is_file():
                    written.append(shuf)
    except Exception as exc:  # noqa: BLE001 — never block on the i1Profiler export
        from workflow.i1profiler_export import UnsupportedInkSet
        if isinstance(exc, UnsupportedInkSet):
            # 4.3.5 B2: CMY, CMY + orange, ...: i1Profiler has no patch set
            # for these inks. One line, no traceback: nothing went wrong.
            log.info("i1Profiler export skipped: %s", exc)
        else:
            log.warning("i1Profiler export failed", exc_info=True)
    # An i1iSis chart (a Beta): the test chart that makes i1Profiler expect
    # exactly this sheet, and its order file (`workflow.isis.export`).
    try:
        from workflow.isis.support import chart_names_isis, isis_enabled
        ti2 = ti1_path.with_name(ti1_path.name[:-4] + ".ti2") \
            if ti1_path.name.lower().endswith(".ti1") else None
        if isis_enabled() and ti2 is not None and chart_names_isis(ti2):
            from workflow.isis.export import write_isis_export
            res = write_isis_export(ti2, out_dir, base_name)
            written += res.written
            if res.skipped:
                log.info("%s", res.skipped)
    except Exception:  # noqa: BLE001 - never block on the sidecars
        log.warning("i1iSis i1Profiler export failed", exc_info=True)
    return written
