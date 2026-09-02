"""Turn a manufacturer's target reference file into something ``scanin`` can read.

Standard scanner/camera targets ship their reference data in three shapes
(ArgyllCMS "Usage Scenarios"):

* **Ready to use** — a CGATS ``.txt`` / ``.cie`` / ``.ti3`` that already lists
  each patch's XYZ or Lab (Wolf Faust, HutchColor HCT, LaserSoft DCPro, CMP
  DT‑003/‑4). ``scanin`` reads these directly.
* **X‑Rite CxF** (``.cxf``) — LaserSoft's ISO 12641‑2 targets. Convert with
  ``cxf2ti3``.
* **Raw / spectral ``.txt``** — the CMP DT‑7/2019/Studio/Mini targets. Convert
  with ``txt2ti3`` then ``spec2cie`` to add the XYZ ``scanin`` needs.

ChromIQ runs the right Argyll converter for the user so they never have to touch
a command line. The converted file is written to *out_dir* (a scratch folder) so
the user's original download is left untouched. ``scanin`` happily reads a
``.ti3`` reference, so ``cxf2ti3``'s ``.ti3`` output is used as-is.
"""
from __future__ import annotations

import re
import subprocess
from enum import Enum
from pathlib import Path
from typing import Callable

from core.stem_paths import artefact
from core.text_io import read_text


class ReferenceKind(Enum):
    DIRECT = "direct"          # already has XYZ/Lab — use as-is
    CXF = "cxf"                # X-Rite CxF → cxf2ti3
    SPECTRAL_TXT = "spectral"  # raw/spectral .txt → txt2ti3 + spec2cie


class ReferenceConvertError(RuntimeError):
    """Conversion failed (carries a user-facing message)."""


# CGATS colorimetric columns that mean "ready to use".
_COLORIMETRIC = re.compile(r"\b(XYZ_[XYZ]|LAB_[LAB]|LAB_L)\b", re.IGNORECASE)


def classify_reference(path: str | Path) -> ReferenceKind:
    """Decide how *path* must be handled. ``.cxf`` → CxF; a ``.txt`` that already
    carries XYZ/Lab → direct, otherwise raw/spectral; ``.cie``/``.ti3`` → direct."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".cxf":
        return ReferenceKind.CXF
    if ext in (".cie", ".ti3"):
        return ReferenceKind.DIRECT
    # .txt (or anything else): sniff for colorimetric columns.
    try:
        head = read_text(p, lenient=True)[:8000]
    except OSError:
        return ReferenceKind.DIRECT
    return (ReferenceKind.DIRECT if _COLORIMETRIC.search(head)
            else ReferenceKind.SPECTRAL_TXT)


def needs_conversion(path: str | Path) -> bool:
    return classify_reference(path) is not ReferenceKind.DIRECT


def is_ti3(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".ti3"


def convert_i1profiler_measurement(path: str | Path, argyll_bin: str | Path,
                                   out_dir: str | Path,
                                   runner: Callable[..., subprocess.CompletedProcess]
                                   = subprocess.run) -> Path:
    """Turn an i1Profiler **measurement** export into a ``.ti3`` ``scanin_target``
    can use, running ``txt2ti3`` for the user (the same tool as Tools → Convert
    i1Profiler → TI3). A file that is already a ``.ti3`` is returned unchanged.

    ``txt2ti3`` copies the export's ``SampleID`` into ``SAMPLE_LOC`` — the patch
    numbers ``1…N`` — which is exactly what the render-derived geometry is keyed
    on. Writes ``<out_dir>/<stem>.ti3``. Raises :class:`ReferenceConvertError`.
    """
    p = Path(path)
    if is_ti3(p):
        return p
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # CxF3 (i1Profiler's native .mxf / .cxf): a pure-Python parse, no txt2ti3 —
    # instrument + date are stamped as part of the write (Basti).
    if is_cxf(p):
        return cxf_measurement_to_ti3(p, out_dir / f"{p.stem}.ti3")
    # `base` is a STEM built from the imported file's name, which routinely
    # carries a version dot ("Epson P900 v1.2.txt"). txt2ti3 APPENDS ".ti3" to
    # the outbase it is given, so the path we look for must be built the same
    # way — with_suffix() here looked for "Epson P900 v1.ti3" and reported the
    # user's own file as unconvertible. See core/stem_paths.py.
    base = out_dir / p.stem
    _run(Path(argyll_bin), "txt2ti3", [str(p), str(base)], runner)
    out = artefact(base, ".ti3")
    if not out.is_file():
        raise ReferenceConvertError(
            "txt2ti3 ran but produced no .ti3 — is this an i1Profiler "
            "measurement export?")
    finalize_converted_ti3(out, p)
    return out


# i1Profiler / X-Rite CGATS values that mean "no instrument recorded".
_UNKNOWN_INSTRUMENTATION = {
    "", "not specified", "unspecified", "unknown", "n/a", "na", "none",
}
# What an imported measurement shows in the report when the source names no
# instrument — clearer than a blank, and honest that it came from outside.
_IMPORTED_INSTRUMENT_FALLBACK = "i1Profiler (unspecified)"


def read_instrumentation(txt_path: str | Path) -> "str | None":
    """The i1Profiler / X-Rite ``INSTRUMENTATION`` header value (e.g.
    ``"i1Pro 2"``), or ``None`` when the file names no real instrument."""
    try:
        text = read_text(Path(txt_path), lenient=True)
    except OSError:
        return None
    m = re.search(r'^\s*INSTRUMENTATION\s+"?(.*?)"?\s*$', text,
                  re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    val = m.group(1).strip()
    return None if val.lower() in _UNKNOWN_INSTRUMENTATION else val


# The report ('created') and its over-time trend need each measurement's DATE.
# txt2ti3 overwrites CREATED with the conversion time, so read the measurement
# date from the source export's CREATED header and preserve it (i1Profiler writes
# e.g. `CREATED "July 19, 2026"`). Kept as a CHROMIQ_MEASURED keyword the report
# reads, so imported runs trend by when they were measured, not when converted.
# English month names are matched OURSELVES (not via strptime %B, which is
# locale-dependent — under a non-English process locale it silently fails).
_MONTHS = {}
for _i, _name in enumerate(
        ("january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"), 1):
    _MONTHS[_name] = _i
    _MONTHS[_name[:3]] = _i


def read_measurement_date(txt_path: str | Path) -> "str | None":
    """The measurement date from an i1Profiler export's ``CREATED`` header, as an
    ISO date (``YYYY-MM-DD``), or ``None`` if absent/unparseable. Locale-safe."""
    try:
        text = read_text(Path(txt_path), lenient=True)
    except OSError:
        return None
    m = re.search(r'^\s*CREATED\s+"?(.*?)"?\s*$', text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    raw = m.group(1).strip()
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)             # ISO / prefix
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    us = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*$", raw)      # US m/d/Y
    if us:
        return f"{us.group(3)}-{int(us.group(1)):02d}-{int(us.group(2)):02d}"
    eu = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*$", raw)    # d.m.Y
    if eu:
        return f"{eu.group(3)}-{int(eu.group(2)):02d}-{int(eu.group(1)):02d}"
    # English month name: "January 06, 2026", "Jan 6 2026", ctime "Tue Jul 21
    # 00:44:31 2026". Find the month + day, and the 4-digit year separately (the
    # ctime form puts a time between them).
    mn = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})\b", raw)
    yr = re.search(r"\b(\d{4})\b", raw)
    if mn and yr and mn.group(1).lower() in _MONTHS:
        return f"{yr.group(1)}-{_MONTHS[mn.group(1).lower()]:02d}-{int(mn.group(2)):02d}"
    return None


def stamp_measurement_date_from_source(ti3_path: str | Path,
                                       source_txt: str | Path) -> "str | None":
    """Copy the source export's measurement date into the converted ``.ti3`` as a
    ``CHROMIQ_MEASURED`` keyword, so the report dates the run by when it was
    measured. No-op when the source has no parseable date or the ``.ti3`` already
    carries one. Returns the ISO date written (or already present), else None."""
    ti3_path = Path(ti3_path)
    try:
        text = read_text(ti3_path, lenient=True)
    except OSError:
        return None
    m = re.search(r'^\s*CHROMIQ_MEASURED\s+"?(.*?)"?\s*$', text,
                  re.IGNORECASE | re.MULTILINE)
    if m:
        return m.group(1).strip()
    date = read_measurement_date(source_txt)
    if not date:
        return None
    lines = text.splitlines()
    at = 1 if lines and lines[0].strip().upper().startswith("CTI3") else 0
    lines[at:at] = ['KEYWORD "CHROMIQ_MEASURED"', f'CHROMIQ_MEASURED "{date}"']
    ti3_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return date


# txt2ti3 hard-codes the Spectrolino as the TARGET_INSTRUMENT of every file it
# writes (profile/txt2ti3.c: `add_kword(…, "TARGET_INSTRUMENT",
# inst_name(instSpectrolino))`, with a source comment noting it *could* read the
# file's INSTRUMENTATION but doesn't). Argyll's inst_name returns the LONG name
# "GretagMacbeth Spectrolino" (not the bare "Spectrolino"), so match on the
# substring — any "…Spectrolino…" tag on a converted .ti3 is that placeholder, not
# the real instrument, and must be replaced.
def _is_txt2ti3_placeholder_instrument(value: "str | None") -> bool:
    return not value or "spectrolino" in value.lower()


def stamp_instrument_from_source(ti3_path: str | Path, source_txt: str | Path,
                                 fallback: str = _IMPORTED_INSTRUMENT_FALLBACK
                                 ) -> str:
    """Give a converted ``.ti3`` a ``TARGET_INSTRUMENT`` the measurement report
    can show. ``txt2ti3`` doesn't carry the real instrument across — it stamps a
    hard-coded ``"Spectrolino"`` placeholder — so read the instrument from the
    source export's ``INSTRUMENTATION`` header and write it in; when the source
    names no real instrument, use *fallback* so imported files still identify
    themselves in Report Scope. A genuine, non-placeholder ``TARGET_INSTRUMENT``
    already on the file is kept. Returns the value the file ends up with.
    """
    ti3_path = Path(ti3_path)
    try:
        text = read_text(ti3_path, lenient=True)
    except OSError:
        return ""
    m = re.search(r'^\s*TARGET_INSTRUMENT\s+"?(.*?)"?\s*$', text,
                  re.IGNORECASE | re.MULTILINE)
    existing = m.group(1).strip() if m else None
    if existing and not _is_txt2ti3_placeholder_instrument(existing):
        return existing                       # a real instrument — leave it
    name = read_instrumentation(source_txt) or fallback
    if m:
        # Replace txt2ti3's placeholder value in place (its KEYWORD line stays).
        text = re.sub(r'^(\s*TARGET_INSTRUMENT\s+).*$', rf'\1"{name}"', text,
                      count=1, flags=re.MULTILINE)
        ti3_path.write_text(text, encoding="utf-8")
    else:
        # No tag at all: insert one, declared with a KEYWORD line so ArgyllCMS
        # tools still parse the file (mirrors ti3_analysis.mark_verification_ti3).
        lines = text.splitlines()
        at = 1 if lines and lines[0].strip().upper().startswith("CTI3") else 0
        lines[at:at] = ['KEYWORD "TARGET_INSTRUMENT"',
                        f'TARGET_INSTRUMENT "{name}"']
        ti3_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return name


_CXF_NS = {"cc": "http://colorexchangeformat.com/CxF3-core"}
# Preferred measurement mode (ISO 13655 illumination condition): M2 = UV-cut is
# the safest default for modern OBA papers; fall back to M1 (D50) then M0.
_CXF_MODES = ("M2_Measurement", "M1_Measurement", "M0_Measurement")


def is_cxf(path: str | Path) -> bool:
    """True for X-Rite CxF3 files (i1Profiler's native ``.mxf`` measurements and
    ``.cxf``) — as opposed to the CGATS ``.txt`` exports txt2ti3 reads."""
    return Path(path).suffix.lower() in (".mxf", ".cxf")


def cxf_measurement_to_ti3(cxf_path: str | Path, out_ti3: str | Path) -> Path:
    """Convert an i1Profiler CxF3 measurement (``.mxf`` / ``.cxf``) straight to an
    Argyll ``.ti3`` — txt2ti3 can't read CxF, and this needs no export step.

    The CxF3 file holds device patches (``Target`` objects, ``ColorRGB``) and the
    readings (``M0/M1/M2_Measurement`` objects, a ``ReflectanceSpectrum`` each) as
    two PARALLEL, index-aligned object lists; we pair them by order, convert the
    reflectance to XYZ under D50 / CIE 1931 2° (matching the report's colorimetry),
    rescale device RGB to Argyll's 0..100, and stamp the instrument + measurement
    date. RGB only (raises for CMYK/other, like the .txt import).
    """
    import numpy as np
    import xml.etree.ElementTree as ET
    from workflow.profile_engine.spectral import spectra_to_xyz

    cxf_path = Path(cxf_path)
    try:
        root = ET.parse(cxf_path).getroot()
    except ET.ParseError as exc:
        raise ReferenceConvertError(
            f"{cxf_path.name}: not a readable CxF3 file ({exc}).") from exc
    objs = root.findall(".//cc:Object", _CXF_NS)

    targets = [o for o in objs if o.get("ObjectType") == "Target"]
    rgb = []
    for o in targets:
        c = o.find("cc:DeviceColorValues/cc:ColorRGB", _CXF_NS)
        if c is None:
            raise ReferenceConvertError(
                f"{cxf_path.name}: no RGB device values — only RGB i1Profiler "
                "measurements can be imported (CMYK/other isn't supported).")
        rgb.append([float(c.find(f"cc:{k}", _CXF_NS).text) for k in "RGB"])
    if not rgb:
        raise ReferenceConvertError(
            f"{cxf_path.name}: no measurement patches found.")

    meas = next(([o for o in objs if o.get("ObjectType") == m] for m in _CXF_MODES
                if any(o.get("ObjectType") == m for o in objs)), [])
    if len(meas) != len(targets):
        raise ReferenceConvertError(
            f"{cxf_path.name}: {len(targets)} patches but {len(meas)} readings — "
            "the file's device and measurement lists don't line up.")

    refl, start_wl = [], None
    for o in meas:
        sp = o.find("cc:ColorValues/cc:ReflectanceSpectrum", _CXF_NS)
        if sp is None or not sp.text:
            raise ReferenceConvertError(
                f"{cxf_path.name}: a reading has no reflectance spectrum.")
        start_wl = float(sp.get("StartWL") or 380.0)
        refl.append([float(v) for v in sp.text.split()])
    bands = len(refl[0])
    if any(len(r) != bands for r in refl):
        raise ReferenceConvertError(
            f"{cxf_path.name}: readings have unequal spectrum lengths.")

    lam = start_wl + 10.0 * np.arange(bands)           # i1Pro: 10 nm intervals
    xyz = spectra_to_xyz(np.asarray(refl), lam, illuminant="D50")   # Y=100, D50
    rgb100 = np.asarray(rgb) * (100.0 / 255.0)         # CxF ColorRGB is 0..255

    instrument = _cxf_instrument(root)
    date = _cxf_measured_date(root, meas)
    lines = ["CTI3", "", 'DESCRIPTOR "Measurement data converted from i1Profiler CxF"',
             'ORIGINATOR "ChromIQ"',
             'KEYWORD "TARGET_INSTRUMENT"', f'TARGET_INSTRUMENT "{instrument}"']
    if date:
        lines += ['KEYWORD "CHROMIQ_MEASURED"', f'CHROMIQ_MEASURED "{date}"']
    lines += ['DEVICE_CLASS "OUTPUT"', 'COLOR_REP "iRGB_XYZ"', "",
              "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
              "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
              "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rgb100)}", "BEGIN_DATA"]
    for i, ((r, g, b), (x, y, z)) in enumerate(zip(rgb100, xyz), 1):
        lines.append(f'{i} "{i}" {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}')
    lines += ["END_DATA", ""]
    out_ti3 = Path(out_ti3)
    if not out_ti3.name.lower().endswith(".ti3"):
        # By name, not by suffix: a stem like "Epson P900 v1.2" has a "suffix"
        # of ".2", and with_suffix() would REPLACE it (core/stem_paths.py).
        out_ti3 = artefact(out_ti3, ".ti3")
    out_ti3.write_text("\n".join(lines), encoding="utf-8")
    return out_ti3


def _cxf_instrument(root) -> str:
    """Instrument name from a CxF3 tree. i1Profiler records it as a
    ``MeasurementDevice`` attribute (e.g. ``"i1Pro 2"``) on its measurement spec;
    fall back to the imported-file label when it's absent."""
    for tag in root.iter():
        dev = tag.get("MeasurementDevice")
        if dev and dev.strip():
            return dev.strip()
        name = (tag.get("Name") or "").lower()      # some writers use a Tag
        if name in ("measurementdevice", "devicemodel", "instrument") and tag.get("Value"):
            return tag.get("Value").strip()
    return _IMPORTED_INSTRUMENT_FALLBACK


def _cxf_measured_date(root, meas) -> "str | None":
    """ISO measurement date from a CxF3 tree (a measurement's CreationDate, else
    the file's), or None."""
    for src in (meas[0] if meas else None, root):
        if src is None:
            continue
        cd = src.find("cc:CreationDate", _CXF_NS) if src is not root \
            else root.find(".//cc:FileInformation/cc:CreationDate", _CXF_NS)
        if cd is not None and cd.text:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", cd.text.strip())
            if m:
                return m.group(1)
    return None


def finalize_converted_ti3(ti3_path: str | Path,
                           source_txt: str | Path) -> "tuple[str, str | None]":
    """Finalise a just-converted (txt2ti3) ``.ti3`` from its i1Profiler source:
    stamp the real instrument (over txt2ti3's Spectrolino placeholder) and the
    measurement date, so the measurement report shows the right instrument and
    trends by when the chart was measured, not when it was converted. Returns
    ``(instrument, iso_date_or_None)``. THE single place all three convert paths
    call — the Convert i1Profiler → TI3 tool, convert_i1profiler_measurement (the
    scanner-target import), and the Build Profile .txt import — so they behave
    identically (Knut)."""
    instrument = stamp_instrument_from_source(ti3_path, source_txt)
    date = stamp_measurement_date_from_source(ti3_path, source_txt)
    return instrument, date


def _run(argyll_bin: Path, tool: str, args: list[str],
         runner: Callable[..., subprocess.CompletedProcess]) -> None:
    exe = argyll_bin / tool
    if not exe.exists():
        raise ReferenceConvertError(
            f"ChromIQ needs the ArgyllCMS tool “{tool}” to convert this file, but "
            f"couldn't find it. Check the ArgyllCMS folder in Settings.")
    r = runner([str(exe), *args], capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]
        raise ReferenceConvertError(f"{tool} couldn't convert the file: {tail[0]}")


def convert_reference(
    path: str | Path,
    argyll_bin: str | Path,
    out_dir: str | Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Path:
    """Return a reference file ``scanin`` can read. Ready-to-use files are
    returned unchanged; ``.cxf`` and raw/spectral ``.txt`` are converted into
    *out_dir* via Argyll. Raises :class:`ReferenceConvertError` on failure."""
    p = Path(path)
    kind = classify_reference(p)
    if kind is ReferenceKind.DIRECT:
        return p

    argyll_bin = Path(argyll_bin)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / p.stem

    if kind is ReferenceKind.CXF:
        # cxf2ti3 <in.cxf> <outbase>  ->  <outbase>.ti3
        _run(argyll_bin, "cxf2ti3", [str(p), str(base)], runner)
        out = artefact(base, ".ti3")
    else:
        # txt2ti3 <in.txt> <tmpbase>  ->  <tmpbase>.ti3   (raw/spectral)
        # spec2cie <tmpbase>.ti3 <out>.cie  ->  adds the XYZ scanin needs
        tmp = out_dir / (p.stem + "_spec")
        _run(argyll_bin, "txt2ti3", [str(p), str(tmp)], runner)
        out = artefact(base, ".cie")
        _run(argyll_bin, "spec2cie", [str(artefact(tmp, ".ti3")), str(out)], runner)

    if not out.is_file():
        raise ReferenceConvertError(
            "The converter ran but produced no reference file. The download may "
            "not be a target reference of this type.")
    return out
