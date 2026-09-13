"""The scan's own device values, on the path where the ``.ti3`` has not got them.

**The fault this exists for.** *Build profile with scanner or camera* has two
modes. Untick *"Profile my printer from this scan"* and ``scanin`` writes a
``.ti3`` whose ``RGB_*`` are what the scanner saw; tick it and ``scanin -c``
writes a ``.ti3`` whose ``RGB_*`` are **the CHART's printer device values** and
whose ``XYZ_*`` are the scan converted through a scanner profile. Two of the
five checks in :mod:`workflow.scan_read_check` read the device column, so on the
ticked mode they were asking about the chart:

* **the clipped share** counted the chart's own solids and paper. Every
  profiling chart is full of both by design, so the figure never moved with the
  scan and never came under the 15 % limit. Measured on charts straight out of
  ``targen``: 61.0 % at 210 patches, 49.2 at 396, 40.4 at 800, 32.8 at 1500. The
  warning fired on every scan ever made on that path, and its advice — rescan
  with the automatic brightness off — could not help, because the number is not
  about the scan;
* **the highlight level** could never fire, because the chart's white is device
  100 by construction. A genuinely dark scan went through in silence, and that
  is the one that quietly builds a bad printer profile.

Measured 2026-09-13 on the CR30 demo pack, whose two scans differ only in
brightness: **23.3 % clipped for both** on the ticked path, with the highlight
level reading 100.0 for both, against 0.0 % / 96.3 and 37.9 % / 99.8 on the
unticked one. Same images, same corners; the numbers simply were not about them.
After this module they read 0.0 / 96.3 and 37.9 / 99.8 on BOTH paths.

**The route.** A second ``scanin`` pass over the same image, at the same
corners, with the same ``.cht``: ``scanin -o`` writes a ``.val`` of
``SAMPLE_ID RGB_R RGB_G RGB_B`` and nothing else. Four things recommend it over
every alternative considered:

* **it is the same measurement, not an approximation.** ``val * 100 / 255``
  reproduced the scanner path's own ``.ti3`` ``RGB_*`` to a maximum difference
  of **0.000024** over 396 patches — the rounding in scanin's text output. The
  checks therefore see exactly the numbers they were designed and calibrated
  against, so no threshold moves;
* **it cannot damage anything.** ``-o`` reads no reference and writes no
  ``.ti3``. The measurement the build depends on is written by the first pass
  and is not touched. ``scanin -r``, the obvious alternative, *replaces* the
  device values in ``pbase.ti2``/``.ti3`` — it would destroy the printer
  measurement to measure it;
* **it costs one recognition pass**: 0.27 s on a 10.1 MB scan, measured, the
  same as the pass beside it;
* **inverting the ``XYZ_*`` back through the scanner ICC cannot work at all.**
  Clipping is the information a profile conversion destroys: a patch pinned at
  the top of the scale and one just under it map to neighbouring colours, and
  the whole point of the check is to tell them apart.

``-o`` and ``-c`` are mutually exclusive modes and the last flag on the line
wins (measured: ``-c -o`` wrote only the ``.val``, ``-o -c`` only the ``.ti3``),
so this cannot be folded into the first invocation.

**Nothing here may raise, and nothing here may guess.** A pass that does not
produce numbers returns ``None``, and the checks then decline to judge rather
than falling back on the chart — which is the fault, not the fallback.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.logger import get_logger
from core.proc_text import run_text
from workflow.scanin_runner import parse_val, scanin_values_args

log = get_logger(__name__)

#: Seconds to allow the values pass. It is measured at 0.27 s on a 10.1 MB scan
#: and 0.28 s on the 2-page chart's larger sheet, so this is a margin of about a
#: thousand, and it is deliberately not tighter: 2026-09-02 cost a release gate a
#: phantom red because a subprocess measured at 1.2 s idle was given 60 s and the
#: loaded machine blew through it. A timeout here is not a failure of the build
#: either way — it means "not measured", and the checks say so.
VALUES_TIMEOUT = 300


@dataclass(frozen=True)
class ScanDeviceValues:
    """What one page's scan actually read, beside what its chart asked for.

    *scan_rgb* is the device value the scanner returned, 0-100, from the values
    pass. *chart_rgb* is the same patch's value in the chart's own ``.ti2``, or
    ``None`` when the chart could not be paired with the read — the clipped
    share needs only the first, so it survives a pairing that does not.
    """

    ids: tuple[str, ...]
    scan_rgb: tuple[tuple[float, float, float], ...]
    chart_rgb: "tuple[tuple[float, float, float], ...] | None"

    def __len__(self) -> int:
        return len(self.ids)


def _chart_device_by_loc(ti2: Path) -> "dict[str, tuple[float, float, float]] | None":
    """``{patch id: (R, G, B)}`` from a chart's ``.ti2``, keyed by ``SAMPLE_LOC``.

    ``SAMPLE_LOC`` is the name the ``.cht`` boxes carry and therefore the name a
    ``.val`` row is called by; ``SAMPLE_ID`` in a ``.ti2`` is a row number and
    would pair nothing. Ids are normalised through the same ``_plain_id`` rule
    both sides of this use.

    The CGATS is read directly rather than through
    :func:`workflow.ti3_analysis.parse_ti3`, which raises ``Ti3ParseError("No
    XYZ, Lab or spectral columns in the measurement")`` on a file that has none.
    That is right for a *measurement* and wrong here: the only two columns this
    needs are ``SAMPLE_LOC`` and ``RGB_*``, and a chart whose ``.ti2`` carries no
    aim colours is still a chart whose paper patch is device 100. Found by
    mutation testing on 2026-09-13 — the first version of this used ``parse_ti3``
    and the test that was supposed to catch it handed it a ``.ti2`` with no XYZ,
    so the helper returned ``None``, the mutation changed nothing, and the test
    passed by validating itself.
    """
    from workflow.scanin_runner import _plain_val_id
    from core.text_io import read_text
    try:
        lines = read_text(ti2, lenient=True).splitlines()
    except OSError:
        return None
    try:
        fs = next(i for i, l in enumerate(lines)
                  if l.strip().upper() == "BEGIN_DATA_FORMAT")
        fields = [f.upper() for f in lines[fs + 1].split()]
        ds = next(i for i, l in enumerate(lines)
                  if l.strip().upper() == "BEGIN_DATA")
        de = next(i for i, l in enumerate(lines[ds:], ds)
                  if l.strip().upper() == "END_DATA")
        cloc = fields.index("SAMPLE_LOC")
        crgb = [fields.index(c) for c in ("RGB_R", "RGB_G", "RGB_B")]
    except (StopIteration, IndexError, ValueError):
        return None
    out: dict[str, tuple[float, float, float]] = {}
    for line in lines[ds + 1:de]:
        row = re.findall(r'"[^"]*"|\S+', line)
        if len(row) <= max(cloc, *crgb):
            continue
        try:
            rgb = tuple(float(row[c]) for c in crgb)
        except ValueError:
            continue
        out[_plain_val_id(row[cloc].strip('"'))] = rgb  # type: ignore[assignment]
    return out or None


def measure_scan_device_values(
        scanin: Path, scan_tif: Path, cht: Path, into: Path,
        corners: "list[tuple[float, float]] | None" = None,
        perspective: bool = True, ti2: "Path | None" = None,
        timeout: int = VALUES_TIMEOUT) -> "ScanDeviceValues | None":
    """Run the values pass over *scan_tif* and pair it with the chart.

    *into* is where the ``.val`` is written and the pass is run; give it a
    temporary folder, never the folder the user keeps the scan in — scanin's
    default is ``<input>.val`` beside the image, which is why ``-O`` is always
    passed.

    ``None`` on any failure at all: a missing binary, a non-zero exit, a timeout,
    an unparseable ``.val``, an OS error. Every one of them means the same thing
    to the caller, which is *this was not measured*.
    """
    try:
        into.mkdir(parents=True, exist_ok=True)
        out_name = "read-values.val"
        args = scanin_values_args(scan_tif, cht, out_name, corners=corners,
                                  perspective=perspective)
        log.info("scanin values pass: %s %s  [cwd=%s]", scanin, " ".join(args), into)
        # `run_text` and not `subprocess.run(text=True)`: issue #178. The
        # latter decodes with `locale.getpreferredencoding(False)`, which is
        # US-ASCII under a POSIX-default locale and raises on the first umlaut
        # in a path. `core.proc_text` runs the child in binary and applies the
        # measured decode ladder, and `tests/test_encoding_is_named.py` fails
        # any call site that does not.
        proc = run_text([str(scanin), *args], cwd=str(into),
                        capture_output=True, timeout=timeout)
        if proc.returncode != 0:
            log.warning("scanin values pass exited %s: %s", proc.returncode,
                        (proc.stdout + proc.stderr).strip()[-400:])
            return None
        scan = parse_val(into / out_name)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # subprocess.TimeoutExpired is a SubprocessError. It is logged as
        # "not measured", never re-raised: a sanity check that can stop a build
        # is worse than no sanity check.
        log.warning("scanin values pass did not produce values: %s", exc)
        return None
    if not scan:
        return None

    ids = tuple(sorted(scan))
    scan_rgb = tuple(scan[i] for i in ids)
    chart_rgb: "tuple[tuple[float, float, float], ...] | None" = None
    if ti2 is not None:
        aim = _chart_device_by_loc(ti2)
        if aim is not None and all(i in aim for i in ids):
            chart_rgb = tuple(aim[i] for i in ids)
        elif aim is not None:
            # A partial pairing is not a pairing. The highlight check picks the
            # chart's near-white patches, and if the ones missing are exactly
            # those it would have picked, a partial join answers confidently
            # about the wrong patches. Decline instead; the clipped share, which
            # needs no chart at all, still answers.
            log.warning("values pass: %d of %d patch ids are not in %s",
                        sum(1 for i in ids if i not in aim), len(ids), ti2.name)
    return ScanDeviceValues(ids=ids, scan_rgb=scan_rgb, chart_rgb=chart_rgb)
