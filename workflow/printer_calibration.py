"""Which printer calibration a chart was printed with, and what that means.

ArgyllCMS's printtarg offers two ways to use a printer calibration (``.cal``)
when a chart is made, and ChromIQ's layout engine copies both:

* ``-K`` **apply**: the page pixels carry the calibrated values, the ``.ti2``
  keeps the uncalibrated ones and embeds the CAL table. chartread copies the
  ``.ti2`` values into the ``.ti3``, so the profile describes the CALIBRATED
  printer, and anything printed through it must be calibrated too
  (``cctiff ... profile.icc calibration.cal``, or ``applycal``'s
  ``calibrated.icc``).
* ``-I`` **include**: the CAL is embedded, nothing is applied. The printer or
  RIP applies it natively; ChromIQ prints raw.

printtarg writes the same ``.ti2`` for both (printtarg.c:3348-3352 and
3791-3795): only the pixels differ. So the choice cannot be read back from the
chart file, and until 4.3.3-beta.3 it was recorded only for printtarg charts
made from the Create Chart tab (the registry snapshot). This module:

* writes the choice into the chart's ``.channels.json`` at build time
  (:func:`calibration_record`, key :data:`RECORD_KEY`), for both engines;
* answers it for any chart, including older ones, through ONE function,
  :func:`calibration_mode_of`, in a fixed order (see there);
* recognises the older layout-engine ``-K`` chart (before 62e26e4e), which
  wrote the calibrated values into the ``.ti2`` as well. Its profile already
  describes the uncalibrated printer, so applying the calibration to it again
  calibrates twice (#182 5958466861, approved 5959070209).

Nothing here changes a file except :func:`extract_cal`, which writes a copy
of the CAL table into a cache folder the caller names.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shlex
from pathlib import Path
from typing import Iterable

from core.logger import get_logger

log = get_logger(__name__)

#: The answers of :func:`calibration_mode_of`.
MODE_APPLY = "apply"                        # -K: printed pixels calibrated
MODE_INCLUDE = "include"                    # -I: embedded, not applied
MODE_OFF = "off"                            # no calibration
MODE_UNKNOWN = "unknown"                    # a CAL is there, how it was used is not known
MODE_OLD_ENGINE_APPLY = "old_engine_apply"  # pre-62e26e4e engine -K: calibrated twice

ENGINE_PRINTTARG = "printtarg"
ENGINE_CHROMIQ = "chromiq"

#: The key in ``<stem>.channels.json``.
RECORD_KEY = "printer_calibration"

#: How far a ``.ti3`` device value may sit from the ``.ti1`` before it counts
#: as different. Both files carry 4-5 decimals of a 0-100 scale, and chartread
#: re-prints what it read, so an honest copy differs by rounding (<= 0.0005);
#: an old engine ``-K`` chart differs by whole units wherever the curve is not
#: the identity. 0.05 is a hundred times the rounding and far below any real
#: calibration curve.
DEVICE_TOLERANCE = 0.05

ENGINE_ORIGINATOR = "ChromIQ layout engine"


# ---------------------------------------------------------------------------
# Small CGATS readers (first table only; the CAL table follows it)
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    from core.text_io import read_text
    return read_text(Path(path), lenient=True)


def _split_cal(text: str) -> "tuple[str, str]":
    """(first table, the CAL table text or '') — the CAL table starts with a
    line that is exactly ``CAL``."""
    m = re.search(r"^CAL[ \t]*$", text, re.M)
    if not m or m.start() == 0:
        return text, ""
    return text[:m.start()], text[m.start():]


def _tokens(line: str) -> "list[str]":
    return [t.strip('"') for t in re.findall(r'"[^"]*"|\S+', line)]


def read_table(path: "Path | str") -> "tuple[list[str], dict[str, dict[str, str]], dict[str, str]]":
    """``(fields, {SAMPLE_ID: {field: value}}, keywords)`` of the FIRST table
    of a CGATS file (.ti1 / .ti2 / .ti3). Raises ``ValueError`` on a file
    with no data table."""
    text, _cal = _split_cal(_read(Path(path)))
    fm = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\n\s*END_DATA_FORMAT", text, re.S)
    dm = re.search(r"BEGIN_DATA\s*\n(.*?)\n\s*END_DATA\b", text, re.S)
    if not (fm and dm):
        raise ValueError(f"{Path(path).name}: no data table")
    fields = fm.group(1).split()
    rows: "dict[str, dict[str, str]]" = {}
    for line in dm.group(1).splitlines():
        t = _tokens(line)
        if len(t) < len(fields):
            continue
        row = dict(zip(fields, t))
        sid = row.get("SAMPLE_ID", str(len(rows) + 1))
        rows[sid] = row
    kw: "dict[str, str]" = {}
    for line in text[:fm.start()].splitlines():
        t = _tokens(line)
        if len(t) >= 2 and re.fullmatch(r"[A-Z_][A-Z0-9_]*", t[0]):
            kw.setdefault(t[0], " ".join(t[1:]))
    return fields, rows, kw


def _raw_cal_text(path: "Path | str | None") -> str:
    """The CAL table text of a .ti2 / .ti3 as written, numeric or not."""
    if path is None or not Path(path).is_file():
        return ""
    try:
        _first, cal = _split_cal(_read(Path(path)))
    except OSError:
        return ""
    if "BEGIN_DATA" not in cal:
        return ""
    return cal.strip() + "\n"


def cal_table_is_numeric(cal_text: str) -> bool:
    """Whether every value in a CAL table's data block is a finite number.

    ChromIQ's measuring engine wrote an all-``nan`` table into the .ti3 of
    every ``-K``/``-I`` chart before 4.3.3-beta.7 (a one-line fault in the
    vendored ``rspl1.c``, see ``native/instlib/PROVENANCE.md``). colprof,
    cctiff and every other Argyll reader refuse such a table."""
    m = re.search(r"BEGIN_DATA\s*\n(.*?)\n\s*END_DATA\b", cal_text, re.S)
    if not m:
        return False
    seen = False
    for tok in m.group(1).split():
        try:
            if not math.isfinite(float(tok)):
                return False
        except ValueError:
            return False
        seen = True
    return seen


def embedded_cal_text(path: "Path | str | None") -> str:
    """The CAL table embedded in a .ti2 / .ti3 (``-K`` and ``-I`` both embed
    it, and chartread copies it into the .ti3), or '' when there is none.

    A table that is not all numbers counts as none (:func:`cal_table_is_numeric`):
    no caller can use it, and :func:`run_cal_source` then falls back to the
    chart's own .ti2, which carries the same table intact."""
    text = _raw_cal_text(path)
    if text and not cal_table_is_numeric(text):
        log.debug("%s: embedded calibration table is not numeric; treated as absent",
                  Path(path).name)
        return ""
    return text


def has_embedded_cal(path: "Path | str | None") -> bool:
    return bool(embedded_cal_text(path))


def _sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest() if text else ""


def _sha1_file(path: "Path | str | None") -> str:
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except (OSError, TypeError):
        return ""


def extract_cal(source: "Path | str", out_path: "Path | str") -> "Path | None":
    """Write the CAL table embedded in *source* (a .ti3 or .ti2) to
    *out_path* as a stand-alone ``.cal`` that cctiff and applycal read.
    Returns the path, or None when *source* carries no CAL."""
    text = embedded_cal_text(source)
    if not text:
        return None
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# The record written at build time
# ---------------------------------------------------------------------------

def calibration_record(engine: str, cal_path: "str | Path | None",
                       apply: bool) -> dict:
    """``{"mode", "cal_sha1", "cal_name", "engine"}`` for a chart being built.

    *apply* True is ``-K``, False with a *cal_path* is ``-I``; no path is
    "off". ``cal_sha1`` fingerprints the file as it was at build time, so a
    later reader can tell the CAL it finds from the one that was printed.
    """
    cal = str(cal_path or "").strip()
    if not cal:
        return {"mode": MODE_OFF, "cal_sha1": "", "cal_name": "",
                "engine": engine}
    return {"mode": MODE_APPLY if apply else MODE_INCLUDE,
            "cal_sha1": _sha1_file(cal), "cal_name": Path(cal).name,
            "engine": engine}


def printtarg_cal_choice(extra_args: str) -> "tuple[str, bool]":
    """``(cal path, applied?)`` from printtarg's extra arguments: ``-K x`` is
    applied, ``-I x`` embedded only; ('', False) when neither is given. Both
    the spaced (``-K x``) and the joined (``-Kx``) spelling are understood."""
    try:
        toks = shlex.split(extra_args or "")
    except ValueError:
        toks = (extra_args or "").split()
    path, applied = "", False
    i = 0
    while i < len(toks):
        t = toks[i]
        for flag, is_apply in (("-K", True), ("-I", False)):
            if t == flag and i + 1 < len(toks):
                path, applied = toks[i + 1], is_apply
                i += 1
                break
            if t.startswith(flag) and len(t) > 2:
                path, applied = t[2:], is_apply
                break
        i += 1
    return path, applied


def record_for_params(params, engine: str) -> dict:
    """The record for a chart built from Create Chart's ``ChartParams``.

    The layout engine reads its calibration from the layout panel
    (``engine_cal_path`` / ``engine_apply_cal``) and ignores printtarg's rows;
    printtarg reads ``-K`` / ``-I`` from its extra arguments. Each engine is
    asked what IT used, so a hidden row of the other one cannot be recorded.
    """
    if engine == ENGINE_CHROMIQ:
        return calibration_record(engine, getattr(params, "engine_cal_path", None),
                                  bool(getattr(params, "engine_apply_cal", False)))
    path, applied = printtarg_cal_choice(
        getattr(params, "extra_printtarg_args", "") or "")
    return calibration_record(engine, path, applied)


# ---------------------------------------------------------------------------
# Answering it for any chart
# ---------------------------------------------------------------------------

def _sidecar_for(ti2: Path) -> Path:
    name = ti2.name
    stem = name[:-4] if name.lower().endswith(".ti2") else ti2.stem
    return ti2.with_name(f"{stem}.channels.json")


def _ti1_for(ti2: Path) -> Path:
    name = ti2.name
    stem = name[:-4] if name.lower().endswith(".ti2") else ti2.stem
    return ti2.with_name(f"{stem}.ti1")


def _load_sidecar(ti2: Path) -> dict:
    p = _sidecar_for(ti2)
    if not p.is_file():
        return {}
    try:
        data = json.loads(_read(p))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def is_engine_chart(ti2: "Path | str", sidecar: "dict | None" = None) -> bool:
    """A chart the ChromIQ layout engine laid out: its .ti2 says so in its
    ORIGINATOR, or its sidecar carries the engine's layout marker."""
    ti2 = Path(ti2)
    if sidecar is None:
        sidecar = _load_sidecar(ti2)
    layout = sidecar.get("layout") if isinstance(sidecar, dict) else None
    if isinstance(layout, dict) and layout.get("engine") == ENGINE_CHROMIQ:
        return True
    try:
        _f, _r, kw = read_table(ti2)
    except (OSError, ValueError):
        return False
    return kw.get("ORIGINATOR", "").strip() == ENGINE_ORIGINATOR


def device_fields_of(fields: "Iterable[str]") -> "list[str]":
    """The device columns of a CGATS table: everything that is not the
    sample's identity, its place, or a measurement."""
    skip_prefix = ("XYZ_", "LAB_", "SPEC_", "STDEV", "MEAN_DE", "CHI_SQUARED",
                   "SPECTRAL_", "D_", "LCH_")
    return [f for f in fields
            if f not in ("SAMPLE_ID", "SAMPLE_LOC", "SAMPLE_NAME", "LOCATION")
            and not f.startswith(skip_prefix)]


def device_values_differ(ti1: "Path | str", other: "Path | str",
                         tol: float = DEVICE_TOLERANCE) -> "bool | None":
    """Whether any device value of *other* (.ti3 or .ti2) differs from the
    .ti1 by more than *tol*.

    Only SAMPLE_IDs the .ti1 has are compared (the engine pads a last strip
    with paper-white patches the .ti1 never had), and device fields are
    matched by NAME, not by position. None when there is nothing to compare
    (a file missing or unreadable, no shared id or device field).
    """
    try:
        f1, r1, _ = read_table(ti1)
        f2, r2, _ = read_table(other)
    except (OSError, ValueError):
        return None
    fields = [f for f in device_fields_of(f1) if f in f2]
    if not fields:
        return None
    compared = 0
    for sid, row1 in r1.items():
        row2 = r2.get(sid)
        if row2 is None:
            continue
        for f in fields:
            try:
                a, b = float(row1[f]), float(row2[f])
            except (KeyError, ValueError):
                continue
            compared += 1
            if abs(a - b) > tol:
                return True
    return False if compared else None


def is_old_engine_apply(ti2: "Path | str", ti3: "Path | str | None",
                        ti1: "Path | str | None" = None) -> bool:
    """The C1 rule: an older layout-engine ``-K`` measurement.

    All of: the .ti2 was laid out by the ChromIQ layout engine (its
    ORIGINATOR), a CAL is embedded (in the .ti2 or the .ti3), and a device
    value of the .ti3 for a SAMPLE_ID the .ti1 has differs from the .ti1 by
    more than :data:`DEVICE_TOLERANCE`, fields matched by name. Without a
    .ti1 there is no answer, and the answer is no.
    """
    ti2 = Path(ti2)
    ti1 = Path(ti1) if ti1 is not None else _ti1_for(ti2)
    if ti3 is None or not Path(ti3).is_file() or not ti1.is_file():
        return False
    try:
        _f, _r, kw = read_table(ti2)
    except (OSError, ValueError):
        return False
    if kw.get("ORIGINATOR", "").strip() != ENGINE_ORIGINATOR:
        return False
    if not (has_embedded_cal(ti2) or has_embedded_cal(ti3)):
        return False
    return bool(device_values_differ(ti1, ti3))


def _pages_for(ti2: Path) -> "list[Path]":
    from core.file_manager import stem_files
    name = ti2.name
    stem = name[:-4] if name.lower().endswith(".ti2") else ti2.stem
    return sorted({*stem_files(ti2.parent, stem, "*.tif", "*.TIF", "*.tiff")})


def mode_from_pixels(ti2: "Path | str", sidecar: "dict | None" = None,
                     pages: "list[Path] | None" = None) -> str:
    """Read the answer off the printed pages, for an engine chart with no
    record: sample each patch's centre in the page TIFF and compare it with
    the .ti2 value (``-I``) and with the CAL applied to it (``-K``), within
    half a step of 8 bits. Needs the engine's patch rectangles (the sidecar's
    ``layout.patches``); :data:`MODE_UNKNOWN` without them, or when the two
    readings cannot be told apart.
    """
    ti2 = Path(ti2)
    sidecar = _load_sidecar(ti2) if sidecar is None else sidecar
    layout = sidecar.get("layout") if isinstance(sidecar, dict) else None
    rects = (layout or {}).get("patches") if isinstance(layout, dict) else None
    cal_text = embedded_cal_text(ti2)
    if not rects or not cal_text:
        return MODE_UNKNOWN
    try:
        import numpy as np
        import tifffile
        from workflow.layout_engine.calibration import read_cal
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cp = Path(td) / "c.cal"
            cp.write_text(cal_text, encoding="utf-8")
            cal = read_cal(cp)
        fields, rows, _ = read_table(ti2)
        dev_fields = device_fields_of(fields)
        by_loc = {r.get("SAMPLE_LOC", ""): r for r in rows.values()}
        pages = list(pages) if pages is not None else _pages_for(ti2)
        if not pages:
            return MODE_UNKNOWN
        imgs = {}
        tol = 0.6 / 255.0
        n_disc = n_apply = n_raw = 0
        for rect in rects:
            row = by_loc.get(str(rect.get("loc", "")))
            pg = int(rect.get("page", 0))
            if row is None or pg >= len(pages):
                continue
            try:
                dev = tuple(float(row[f]) for f in dev_fields)
            except (KeyError, ValueError):
                continue
            if len(dev) != cal.n_channels:
                return MODE_UNKNOWN
            if pg not in imgs:
                im = tifffile.imread(str(pages[pg]))
                if im.ndim == 3 and im.shape[0] < 8 and im.shape[-1] > 8:
                    im = np.moveaxis(im, 0, -1)
                imgs[pg] = im
            im = imgs[pg]
            mx = 65535.0 if im.dtype == np.uint16 else 255.0
            x, y, w, h = (int(round(float(rect[k]))) for k in ("x", "y", "w", "h"))
            cx, cy = x + w // 2, y + h // 2
            rw, rh = max(1, w // 6), max(1, h // 6)
            win = im[max(0, cy - rh):cy + rh + 1, max(0, cx - rw):cx + rw + 1]
            if win.size == 0:
                continue
            pix = win.reshape(-1, win.shape[-1] if win.ndim == 3 else 1)
            pix = np.median(pix, axis=0)[:len(dev)] / mx
            raw = np.array(dev) / 100.0
            caled = np.array(cal.apply(dev)) / 100.0
            if np.max(np.abs(raw - caled)) <= 2 * tol:
                continue                     # this patch cannot tell them apart
            n_disc += 1
            if np.max(np.abs(pix - caled)) <= tol:
                n_apply += 1
            elif np.max(np.abs(pix - raw)) <= tol:
                n_raw += 1
        if n_disc == 0:
            return MODE_UNKNOWN
        if n_apply >= 0.95 * n_disc:
            return MODE_APPLY
        if n_raw >= 0.95 * n_disc:
            return MODE_INCLUDE
    except Exception:      # noqa: BLE001 — a guess that fails is "unknown"
        log.debug("pixel calibration check failed for %s", ti2, exc_info=True)
    return MODE_UNKNOWN


def calibration_mode_of(ti2: "Path | str | None",
                        ti3: "Path | str | None" = None) -> str:
    """How the printer calibration was used for the chart *ti2*:
    :data:`MODE_APPLY`, :data:`MODE_INCLUDE`, :data:`MODE_OFF`,
    :data:`MODE_OLD_ENGINE_APPLY` or :data:`MODE_UNKNOWN`.

    Asked in this order, first answer wins:

    1. the record in the chart's ``.channels.json`` (written at build time
       since 4.3.3-beta.3, both engines);
    2. a printtarg chart: no CAL in the .ti2 is "off"; otherwise the Create
       Chart registry snapshot in the sidecar (``printtarg-K`` /
       ``printtarg-I``), and failing that the pixels;
    3. an engine chart with no record: no CAL is "off"; a measurement
       (*ti3*, else the .ti2 itself) whose device values differ from the
       .ti1 is the older engine ``-K`` (:data:`MODE_OLD_ENGINE_APPLY`);
       otherwise the printed pixels decide, and :data:`MODE_UNKNOWN` when
       they cannot.
    """
    if ti2 is None:
        return MODE_UNKNOWN
    ti2 = Path(ti2)
    if not ti2.is_file():
        return MODE_UNKNOWN
    side = _load_sidecar(ti2)
    rec = side.get(RECORD_KEY)
    if isinstance(rec, dict) and rec.get("mode") in (MODE_APPLY, MODE_INCLUDE,
                                                     MODE_OFF):
        return rec["mode"]
    cal_here = has_embedded_cal(ti2)
    if not is_engine_chart(ti2, side):
        if not cal_here:
            return MODE_OFF
        snap = side.get("create_chart_settings")
        if isinstance(snap, dict):
            k = snap.get("printtarg-K") or {}
            i = snap.get("printtarg-I") or {}
            if isinstance(k, dict) and k.get("enabled") and str(k.get("value") or "").strip():
                return MODE_APPLY
            if isinstance(i, dict) and i.get("enabled") and str(i.get("value") or "").strip():
                return MODE_INCLUDE
        return mode_from_pixels(ti2, side)
    if not cal_here and not (ti3 and has_embedded_cal(ti3)):
        return MODE_OFF
    ti1 = _ti1_for(ti2)
    if ti1.is_file():
        probe = Path(ti3) if ti3 and Path(ti3).is_file() else ti2
        if device_values_differ(ti1, probe):
            return MODE_OLD_ENGINE_APPLY
    return mode_from_pixels(ti2, side)


def run_calibration_mode(run) -> str:
    """:func:`calibration_mode_of` for a run's PROFILING chart and the
    measurement its profile was built from."""
    try:
        ti3 = run.measurement_ti3
        if not Path(ti3).is_file():
            ti3 = None
        return calibration_mode_of(run.chart_ti2, ti3)
    except Exception:      # noqa: BLE001
        log.debug("calibration mode of the run could not be read", exc_info=True)
        return MODE_UNKNOWN


def run_cal_source(run) -> "Path | None":
    """The file that carries the calibration the run's chart was PRINTED
    with: the measurement (.ti3, chartread copies the CAL into it) first,
    then the chart's .ti2. None when neither carries one.

    A .ti3 whose table is not numeric (the engine fault before
    4.3.3-beta.7) is skipped with a log line, so the .ti2's table is used.
    Nothing is written to either file."""
    ti3 = getattr(run, "measurement_ti3", None)
    ti2 = getattr(run, "chart_ti2", None)
    for cand in (ti3, ti2):
        if cand is None:
            continue
        if has_embedded_cal(cand):
            return Path(cand)
        if cand is ti3 and _raw_cal_text(cand):
            log.warning(
                "%s carries a calibration table that is not numbers (nan), "
                "written by the measuring engine before 4.3.3-beta.7; using "
                "the calibration table of the chart %s instead",
                Path(cand).name, Path(ti2).name if ti2 is not None else "(none)")
    return None


def run_is_old_engine_apply(run) -> bool:
    """:func:`is_old_engine_apply` for a run's profiling chart and its
    measurement (the C1 warning in Build Profile ▸ Apply Calibration)."""
    try:
        return is_old_engine_apply(run.chart_ti2, run.measurement_ti3,
                                   run.chart_ti1)
    except Exception:      # noqa: BLE001
        return False


def is_in_verifications(path: "Path | str") -> bool:
    """Whether *path* sits inside a run's verifications folder."""
    from core.file_manager import VERIFICATIONS_DIRNAME
    return VERIFICATIONS_DIRNAME in Path(path).parts


def run_for_profile(icc: "Path | str") -> "object | None":
    """The run whose folder holds the profile *icc*, or None for a profile
    outside a ``runs/runN`` folder (or inside a verification)."""
    from core.file_manager import Run
    icc = Path(icc)
    if is_in_verifications(icc) or icc.parent.parent.name != "runs":
        return None
    try:
        return Run.for_dir(icc.parent)
    except Exception:      # noqa: BLE001
        return None


def cal_sha1_of_text(text: str) -> str:
    return _sha1_text(text)
