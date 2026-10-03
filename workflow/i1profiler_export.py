"""Convert an Argyll TI1 target into i1Profiler patch-set formats.

i1iSis chart scanners are driven by i1Profiler, not by Argyll. When the user
selects "i1iSis" as the measurement instrument in ChromIQ, we still let `targen`
generate the patch list, then re-emit it in the formats i1Profiler can load:

  - <stem>.txt   CGATS.5 ASCII patch set   (RGB and CMYK only)
  - <stem>.pxf   CxF3 XML patch set        (all colorspaces)

The export is **colorspace-aware** — it reads the device channels straight from
the TI1 and emits the matching i1Profiler structure:

  | Argyll device | i1Profiler element   | scale            | .txt? |
  |---------------|----------------------|------------------|-------|
  | RGB           | <cc:ColorRGB>        | 0..100 ->0..255  | yes   |
  | CMYK          | <cc:ColorCMYK>       | 0..100 (as-is)   | yes   |
  | CMYK+N        | <cc:ColorCMYKPlusN>  | 0..100 (as-is)   | no    |

For CMYK / CMYK+N the .pxf additionally carries the X-Rite Prism
`ColorSpecification` + `ProfileSettings` blocks and per-ink `PLUS_n_COLOR`
definitions, matching i1Profiler's own shipped reference patch sets so its
CMYK / extended-gamut loader accepts them.

i1Profiler re-lays-out the chart and asks which i1iSis variant to use, so we do
not differentiate i1iSis / i1iSis 2 / i1iSis XL here.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from core.cgats_date import long_english_date
from pathlib import Path
from xml.sax.saxutils import escape

# --- colorant model -------------------------------------------------------

CMYK_NAME = {"C": "Cyan", "M": "Magenta", "Y": "Yellow", "K": "Black"}

# Argyll colorant letter -> (i1Profiler ink name, "L|a|b" reference Lab).
# O/G/V/B Lab values are copied verbatim from i1Profiler's shipped
# "Idealliance ECG ... CMYKOGV" PLUS_n_COLOR attributes; the others are
# best-effort placeholders flagged at export time.
EXTRA_INK = {
    "O": ("Orange", "71|33|71"),
    "G": ("Green", "57|-74|30"),
    "V": ("Violet", "39|75|-95"),
    "B": ("Blue", "29.57|67.02|-128"),
    "R": ("Red", "48|68|48"),            # placeholder Lab
    "c": ("Light Cyan", "83|-22|-22"),   # placeholder Lab
    "m": ("Light Magenta", "75|34|-13"), # placeholder Lab
}
_PLACEHOLDER_LAB = {"R", "c", "m"}

# Fallback names + rough Lab anchors for extra-ink channel letters that aren't
# in the verified EXTRA_INK table above (White, light yellow, light/medium
# inks). Without these the best-effort i1Profiler export crashed on any ink set
# containing one of them — e.g. a chart with a White ink raised KeyError 'W'
# (#125). i1Profiler only needs a name + a colour hint per spot ink here, so a
# placeholder Lab is fine; these inks carry no verified reference.
_EXTRA_INK_FALLBACK = {
    "W":  ("White", "100|0|0"),
    "y":  ("Light Yellow", "92|-6|55"),
    "k":  ("Light Black", "55|0|0"),
    "2c": ("Medium Cyan", "70|-25|-30"),
    "2m": ("Medium Magenta", "62|45|-10"),
    "2y": ("Medium Yellow", "88|-5|70"),
    "2k": ("Medium Black", "40|0|0"),
    "1k": ("Light Light Black", "75|0|0"),
}


def _extra_ink(letter: str) -> tuple[str, str]:
    """``(name, Lab)`` for an extra-ink channel letter, defensively.

    Falls back to :data:`_EXTRA_INK_FALLBACK` and then to a generic placeholder,
    so the export handles any ChromIQ ink set instead of raising ``KeyError`` on
    an unknown channel (#125)."""
    if letter in EXTRA_INK:
        return EXTRA_INK[letter]
    return _EXTRA_INK_FALLBACK.get(letter, (f"Ink {letter}", "50|0|0"))

# i1Profiler's internal ink-colorspace enum. Verified against shipped
# references: CMYK (4 ch) -> 9, CMYKOGV (7 ch) -> 15. Both fit 2*ch+1, which is
# used (and flagged) for the CMYK+1/+2/+4 cases that ship no reference anywhere.
_VERIFIED_ENUM = {4: 9, 7: 15}

# Non-device field prefixes in a TI1 data-format line.
_NON_DEVICE = {"XYZ", "LAB", "SPECTRAL", "D50", "D65", "SAMPLE"}

Patch = tuple[int, float, float, float]  # legacy RGB tuple (sample_id, R, G, B)


@dataclass
class Target:
    """Parsed TI1: device channels (0..100) plus the detected colorspace."""

    color_rep: str               # raw COLOR_REP, e.g. "iRGB", "CMYK", "CMYKOGV"
    kind: str                    # "RGB" | "CMYK" | "CMYKPLUSN"
    channels: list[str]          # device channel letters, column order
    rows: list[tuple[int, dict[str, float]]]  # (sample_id, {letter: 0..100})

    @property
    def n_channels(self) -> int:
        return len(self.channels)

    @property
    def extras(self) -> list[str]:
        """Extra-ink channels beyond CMYK (empty unless this is CMYK+N)."""
        if self.kind != "CMYKPLUSN":
            return []
        return [c for c in self.channels if c not in CMYK_NAME]


def ink_colorspace_enum(n_channels: int) -> tuple[int, bool]:
    """Return (enum, verified). Verified only for 4-channel and 7-channel."""
    if n_channels in _VERIFIED_ENUM:
        return _VERIFIED_ENUM[n_channels], True
    return 2 * n_channels + 1, False


# --- parsing ---------------------------------------------------------------


def parse_ti1(ti1_path: Path) -> Target:
    text = ti1_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    # Accept both the CTI1 header targen writes and the generic CGATS.17 header
    # the layout engine's ti1 reader/writer uses — the table below is parsed by
    # field name either way, so both dialects are valid input here.
    head = lines[0].strip() if lines else ""
    if not (head == "CTI1" or head.startswith("CGATS")):
        raise ValueError(f"{ti1_path}: not a CTI1/CGATS file (first line: {head!r})")

    color_rep = ""
    fmt_fields: list[str] = []
    in_format = in_data = False
    raw_rows: list[tuple[int, dict[str, str]]] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("COLOR_REP"):
            color_rep = line.split('"')[1] if '"' in line else line.split()[1]
            continue
        if line == "BEGIN_DATA_FORMAT":
            fmt_fields, in_format = [], True
            continue
        if line == "END_DATA_FORMAT":
            in_format = False
            continue
        if line == "BEGIN_DATA":
            in_data = True
            continue
        if line == "END_DATA":
            in_data = False
            if raw_rows:
                break
            continue
        if in_format:
            fmt_fields.extend(line.split())
            continue
        if in_data and line:
            raw_rows.append((0, dict(zip(fmt_fields, line.split()))))

    if not raw_rows:
        raise ValueError(f"{ti1_path}: no data rows found")

    # Device fields = format fields with a channel suffix that aren't SAMPLE_ID
    # or colorimetric (XYZ/LAB/...). The text before the last '_' is the
    # colorant string (e.g. "RGB", "CMYK", "CMYKOGV"); the suffix is the channel.
    device_fields = [
        f for f in fmt_fields
        if "_" in f and f != "SAMPLE_ID" and f.split("_", 1)[0] not in _NON_DEVICE
    ]
    if not device_fields:
        raise ValueError(f"{ti1_path}: no device channels in {fmt_fields!r}")
    channels = [f.split("_", 1)[1] for f in device_fields]

    rows: list[tuple[int, dict[str, float]]] = []
    for _sid, row in raw_rows:
        sid = int(row["SAMPLE_ID"])
        vals = {ch: float(row[f]) for ch, f in zip(channels, device_fields)}
        rows.append((sid, vals))

    kind = _detect_kind(channels, color_rep)
    return Target(color_rep=color_rep, kind=kind, channels=channels, rows=rows)


def _detect_kind(channels: list[str], color_rep: str) -> str:
    if set(channels) == {"R", "G", "B"}:
        return "RGB"
    if channels[:4] == ["C", "M", "Y", "K"]:
        return "CMYK" if len(channels) == 4 else "CMYKPLUSN"
    raise ValueError(
        f"unsupported colorspace for i1Profiler export: COLOR_REP {color_rep!r} "
        f"channels {channels!r} (RGB, CMYK and CMYK+N are supported)"
    )


# --- value formatting ------------------------------------------------------


def _to_255_float(v: float) -> float:
    return v * 2.55


def _to_255_int(v: float) -> int:
    return max(0, min(255, round(v * 2.55)))


def _trim(v: float) -> str:
    """Trim trailing zeros the way the reference files do (0, 69.8, 100)."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s or "0"


def _now_iso() -> str:
    s = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def _pwxf_utc_now() -> str:
    """UTC timestamp in the `...Z` form i1Profiler workflow files use."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- CGATS .txt ------------------------------------------------------------


def _txt_header(descriptor: str, fields: str, n_fields: int, n_sets: int) -> list[str]:
    return [
        "CGATS.5",
        "",
        'ORIGINATOR "ChromIQ"',
        f'DESCRIPTOR "{descriptor}"',
        f'CREATED "{long_english_date()}"',   # English, as i1Profiler writes it
        'INSTRUMENTATION "Not specified"',
        'MEASUREMENT_SOURCE "Not specified"',
        'PRINT_CONDITIONS "Not specified"',
        "",
        'KEYWORD "SampleID"',
        f"NUMBER_OF_FIELDS {n_fields}",
        "BEGIN_DATA_FORMAT",
        fields,
        "END_DATA_FORMAT",
        "",
        f"NUMBER_OF_SETS {n_sets}",
        "BEGIN_DATA",
    ]


def write_txt(target: Target, out_path: Path, descriptor: str) -> bool:
    """Write the CGATS .txt patch set. Returns False (no file) for CMYK+N."""
    if target.kind == "RGB":
        lines = _txt_header(descriptor, "SampleID RGB_R RGB_G RGB_B ", 4, len(target.rows))
        for sid, v in target.rows:
            lines.append(
                f"{sid} {_to_255_float(v['R']):.4f} "
                f"{_to_255_float(v['G']):.4f} {_to_255_float(v['B']):.4f} "
            )
    elif target.kind == "CMYK":
        lines = _txt_header(descriptor, "SampleID CMYK_C CMYK_M CMYK_Y CMYK_K ", 5, len(target.rows))
        for sid, v in target.rows:
            lines.append(
                f"{sid} {v['C']:.4f} {v['M']:.4f} {v['Y']:.4f} {v['K']:.4f} "
            )
    else:
        return False  # CMYK+N: i1Profiler ships no CGATS .txt for extended gamut
    lines.append("END_DATA")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return True


# --- CxF3 .pxf -------------------------------------------------------------


def _color_specification() -> list[str]:
    return [
        "\t\t<cc:ColorSpecificationCollection>",
        '\t\t\t<cc:ColorSpecification Id="Unknown">',
        "\t\t\t\t<cc:MeasurementSpec>",
        "\t\t\t\t\t<cc:MeasurementType>Colorimetric_Reflectance</cc:MeasurementType>",
        "\t\t\t\t\t<cc:GeometryChoice>",
        "\t\t\t\t\t\t<cc:UnknownGeometry>Target</cc:UnknownGeometry>",
        "\t\t\t\t\t</cc:GeometryChoice>",
        "\t\t\t\t</cc:MeasurementSpec>",
        "\t\t\t</cc:ColorSpecification>",
        "\t\t</cc:ColorSpecificationCollection>",
    ]


def _profile_settings(n_channels: int, n_plus: int) -> list[str]:
    """Reproduce the reference <ProfileSettings>, parametrised by colorspace.

    Fixed sub-elements are copied verbatim from the shipped CMYK / CMYKOGV
    references; only the ink limit, the colorspace enum, and the number of
    InkGeneration_k blocks vary with the colorspace.
    """
    enum, _ = ink_colorspace_enum(n_channels)
    ink_limit = 100 * n_channels  # CMYK->400, CMYKOGV->700 (matches references)
    out = [
        '\t\t<ProfileSettings DeviceType="Printer">',
        '\t\t\t<ProfileVersion value="4"/>',
        '\t\t\t<EmbeddedProfileVersion value="-1"/>',
        "\t\t\t<ChromaticAdaptation>Bradford</ChromaticAdaptation>",
        "\t\t\t<BlackGeneration>",
        "\t\t\t\t<BlackType>2</BlackType>",
        "\t\t\t\t<UseMaximumBlack>0</UseMaximumBlack>",
        "\t\t\t\t<UseIntelligentBlack>1</UseIntelligentBlack>",
        "\t\t\t\t<BlackWidth>50</BlackWidth>",
        "\t\t\t\t<NumberOfCurvePoints>4</NumberOfCurvePoints>",
        "\t\t\t\t<KPoints>0 0 18.9465 100 </KPoints>",
        "\t\t\t\t<LPoints>0 30 65 100 </LPoints>",
        "\t\t\t\t<CurveType>4</CurveType>",
        "\t\t\t</BlackGeneration>",
        "\t\t\t<InkLimiting>",
        f"\t\t\t\t<InkLimit>{ink_limit}</InkLimit>",
        f"\t\t\t\t<ColorSpace>{enum}</ColorSpace>",
        "\t\t\t</InkLimiting>",
    ]
    for k in range(1, n_plus + 1):
        out += [
            f"\t\t\t<InkGeneration_{k}>",
            "\t\t\t\t<NeutralAmount>50</NeutralAmount>",
            "\t\t\t\t<HueLikeness>50</HueLikeness>",
            "\t\t\t\t<UseIntelligentInk>1</UseIntelligentInk>",
            "\t\t\t\t<NumberOfCurvePoints>3</NumberOfCurvePoints>",
            "\t\t\t\t<INKPoints>0 1 1 </INKPoints>",
            "\t\t\t\t<LPoints>0 56 100 </LPoints>",
            f"\t\t\t</InkGeneration_{k}>",
        ]
    out += [
        f"\t\t\t<ProfileInkColorSpace>{enum}</ProfileInkColorSpace>",
        "\t\t\t<Saturation>50</Saturation>",
        "\t\t\t<UseMediaSmoothness>0</UseMediaSmoothness>",
        "\t\t\t<SmoothnessMedianOverall>-1</SmoothnessMedianOverall>",
        "\t\t\t<Smoothness>50</Smoothness>",
        "\t\t\t<Contrast>50</Contrast>",
        "\t\t\t<NeutralizeGray>0</NeutralizeGray>",
        "\t\t\t<ChromaAdjust>50</ChromaAdjust>",
        "\t\t\t<DarkeningForHighChroma>0</DarkeningForHighChroma>",
        "\t\t\t<WhitePointPaperDeltaEThreshold>3.5</WhitePointPaperDeltaEThreshold>",
        "\t\t\t<TableSizeAToB>Medium</TableSizeAToB>",
        "\t\t\t<TableSizeBToA>Medium</TableSizeBToA>",
        "\t\t\t<BitDepth>16</BitDepth>",
        "\t\t</ProfileSettings>",
    ]
    return out


def _pxf_open(descriptor: str, created: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<cc:CxF xmlns:cc="http://colorexchangeformat.com/CxF3-core" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
        "\t<cc:FileInformation>",
        "\t\t<cc:Creator>ChromIQ</cc:Creator>",
        f"\t\t<cc:CreationDate>{created}</cc:CreationDate>",
        f"\t\t<cc:Description>{escape(descriptor)}</cc:Description>",
        "\t</cc:FileInformation>",
        "\t<cc:Resources>",
        "\t\t<cc:ObjectCollection>",
    ]


def _rgb_object(idx: int, v: dict[str, float], created: str) -> list[str]:
    return [
        f'\t\t\t<cc:Object ObjectType="Target" Name="Target{idx}" Id="c{idx}">',
        f"\t\t\t\t<cc:CreationDate>{created}</cc:CreationDate>",
        "\t\t\t\t<cc:DeviceColorValues>",
        '\t\t\t\t\t<cc:ColorRGB ColorSpecification="Unknown">',
        f"\t\t\t\t\t\t<cc:R>{_to_255_int(v['R'])}</cc:R>",
        f"\t\t\t\t\t\t<cc:G>{_to_255_int(v['G'])}</cc:G>",
        f"\t\t\t\t\t\t<cc:B>{_to_255_int(v['B'])}</cc:B>",
        "\t\t\t\t\t</cc:ColorRGB>",
        "\t\t\t\t</cc:DeviceColorValues>",
        "\t\t\t</cc:Object>",
    ]


def _cmyk_object(idx: int, v: dict[str, float], extras: list[str], created: str) -> list[str]:
    elem = "ColorCMYK" if not extras else "ColorCMYKPlusN"
    out = [
        f'\t\t\t<cc:Object ObjectType="Target" Name="Target{idx}" Id="c{idx}">',
        f"\t\t\t\t<cc:CreationDate>{created}</cc:CreationDate>",
        "\t\t\t\t<cc:DeviceColorValues>",
        f'\t\t\t\t\t<cc:{elem} ColorSpecification="Unknown">',
    ]
    for letter in ("C", "M", "Y", "K"):
        out.append(f"\t\t\t\t\t\t<cc:{CMYK_NAME[letter]}>{_trim(v.get(letter, 0.0))}</cc:{CMYK_NAME[letter]}>")
    for letter in extras:
        out += [
            "\t\t\t\t\t\t<cc:SpotColor>",
            f"\t\t\t\t\t\t\t<cc:Name>{_extra_ink(letter)[0]}</cc:Name>",
            f"\t\t\t\t\t\t\t<cc:Percentage>{_trim(v.get(letter, 0.0))}</cc:Percentage>",
            "\t\t\t\t\t\t</cc:SpotColor>",
        ]
    out += [
        f"\t\t\t\t\t</cc:{elem}>",
        "\t\t\t\t</cc:DeviceColorValues>",
        "\t\t\t</cc:Object>",
    ]
    return out


def write_pxf(
    target: Target,
    out_path: Path,
    descriptor: str,
    measurement_device: str = "i1iSis",
) -> None:
    created = _now_iso()
    desc_x = escape(descriptor)
    parts = _pxf_open(descriptor, created)

    if target.kind == "RGB":
        for idx, (_sid, v) in enumerate(target.rows, start=1):
            parts += _rgb_object(idx, v, created)
        parts.append("\t\t</cc:ObjectCollection>")
        parts.append("\t</cc:Resources>")
        parts.append("\t<cc:CustomResources>")
        parts.append('\t\t<xrp:Prism xmlns:xrp="http://www.xrite.com/products/prism" release="2.0">')
        # WriteProtected="True" mirrors X-Rite's shipped reference charts. With
        # it False, i1Profiler shows the "Intelligente Messfelderstellung"
        # controls as editable — a stray click on the count slider or
        # "Messfelder mischen" would replace/scramble our patches, silently
        # desyncing the ChromIQ .ti2/.ti3 round-trip.
        parts.append(
            "  <xrp:CustomAttributes "
            'ColorSpace="RGB" '
            f'MeasurementDevice="{escape(measurement_device)}" '
            'MeasurementScanningMode="Strip" '
            'NumberPatchPages="1" '
            'ScramblePatches="False" '
            'TestChartType="RGB Variable" '
            f'TitleString="{desc_x}" '
            'WriteProtected="True" '
            f'numberCorePatches="{len(target.rows)}" '
            'numberImagePatches="0" '
            'numberSpotPatches="0"/>'
        )
        parts.append("</xrp:Prism>")
        parts.append("")
        parts.append("\t</cc:CustomResources>")
        parts.append("</cc:CxF>")
        parts.append("")
        out_path.write_text("\n".join(parts), encoding="utf-8")
        return

    # CMYK / CMYK+N: device patches + ColorSpecification + full ProfileSettings.
    extras = target.extras
    n_plus = len(extras)
    for idx, (_sid, v) in enumerate(target.rows, start=1):
        parts += _cmyk_object(idx, v, extras, created)
    parts.append("\t\t</cc:ObjectCollection>")
    parts += _color_specification()
    parts.append("\t</cc:Resources>")

    plus_attrs = ""
    for i, letter in enumerate(extras, start=1):
        name, lab = _extra_ink(letter)
        plus_attrs += f' PLUS_{i}_COLOR="{name}|{lab}|1|2|50|50|{i}"'
    colorspace = "CMYK" if n_plus == 0 else f"CMYK + {n_plus}"
    ink_limit = 100 * target.n_channels

    parts.append("\t<cc:CustomResources>")
    parts.append('\t\t<xrp:Prism xmlns:xrp="http://www.xrite.com/products/prism" release="2.0">')
    parts.append(
        "  <xrp:CustomAttributes "
        f'ColorSpace="{colorspace}" '
        f'InkLimit="{ink_limit}" '
        f'MeasurementDevice="{escape(measurement_device)}" '
        'MeasurementScanningMode="Strip" '
        'NumberPatchPages="1" '
        'ScramblePatches="False" '
        f'TestChartType="{colorspace}"'
        f"{plus_attrs} "
        f'TitleString="{desc_x}" '
        'WriteProtected="True" '  # see RGB block above for rationale
        f'numberCorePatches="{len(target.rows)}" '
        'numberImagePatches="0" '
        'numberSpotPatches="0"/>'
    )
    parts += _profile_settings(target.n_channels, n_plus)
    parts.append("</xrp:Prism>")
    parts.append("")
    parts.append("\t</cc:CustomResources>")
    parts.append("</cc:CxF>")
    parts.append("")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def _shuffled_target(target: Target, seed: int | None = None) -> Target:
    """Return *target* with its patch rows in random order.

    i1Profiler builds the printed chart in the order the patches appear in the
    file. A TI1 straight from ``targen`` keeps its colours in a systematic
    order, so a plain export can place near-identical patches side by side on
    the strip — a little harder to read and slightly worse for the instrument.
    Shuffling the row order spreads similar colours apart. The written ``.pxf``
    keeps ``ScramblePatches="False"``, so i1Profiler honours exactly this order
    on import instead of re-shuffling on top of it (Nelson / pharmacist)."""
    rows = list(target.rows)
    random.Random(seed).shuffle(rows)
    return replace(target, rows=rows)


def _write_pair(
    target: Target, out_dir: Path, base_name: str, descriptor: str
) -> tuple[Path | None, Path]:
    """Write ``<base_name>.pxf`` (always) and ``<base_name>.txt`` (RGB/CMYK
    only) for *target*. Returns (txt_or_None, pxf)."""
    txt_out = out_dir / f"{base_name}.txt"
    pxf_out = out_dir / f"{base_name}.pxf"
    wrote_txt = write_txt(target, txt_out, descriptor)
    write_pxf(target, pxf_out, descriptor)
    return (txt_out if wrote_txt else None), pxf_out


def export_from_ti1(
    ti1_path: Path,
    out_dir: Path,
    base_name: str = "i1profiler",
    descriptor: str | None = None,
    also_shuffled: bool = False,
    shuffle_seed: int | None = None,
) -> tuple[Path | None, Path]:
    """Read TI1, write ``<base_name>.pxf`` (always) and ``<base_name>.txt``
    (RGB/CMYK only) into ``out_dir``.

    Returns (txt_path_or_None, pxf_path) for the primary (patch-list-order)
    pair. txt_path is None for CMYK+N, which i1Profiler only accepts as a
    CxF3 .pxf.

    The default ``base_name="i1profiler"`` keeps tests / generic callers
    self-contained. The tab_chart caller passes ``<project>-i1profiler`` so
    the exported file is self-identifying when the user hands it to
    i1Profiler.

    ``descriptor`` controls the internal CxF/CGATS profile name (shown by
    i1Profiler in the workflow dropdown). Defaults to the TI1 stem, which
    under the per-run layout is the (sanitised) project name.

    When ``also_shuffled`` is set, a second copy with the patch order shuffled
    (see :func:`_shuffled_target`) is written alongside as
    ``<base_name>-shuffled.pxf`` (+ ``.txt``). The returned paths are always
    those of the primary, unshuffled pair. ``shuffle_seed`` makes the shuffle
    reproducible (used by tests); the UI leaves it None for a fresh order.
    """
    target = parse_ti1(ti1_path)
    desc = descriptor or ti1_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_out, pxf_out = _write_pair(target, out_dir, base_name, desc)
    if also_shuffled:
        _write_pair(_shuffled_target(target, seed=shuffle_seed),
                    out_dir, f"{base_name}-shuffled", desc)
    return txt_out, pxf_out


# --- CxF3 .pwxf (i1Profiler workflow) --------------------------------------
#
# A .pwxf is the same CxF3 file as the .pxf above, plus (1) a fuller
# <xrp:CustomAttributes> carrying the device + paper + grid, and (2) an
# optional per-patch <cc:TagCollection Name="Location">. The skeleton, the
# Object list (ti1 order, 0..255 RGB), the ColorSpecificationCollection, and
# the ProfileSettings block are structurally what write_pxf already produces.
#
# The format was reverse-engineered from 14 genuine i1Profiler 1.1.0 exports;
# full mapping in docs/dev_pxwf_format.md. RGB only — i1Profiler workflow
# export for CMYK/CMYK+N is out of scope until we have reference workflow files
# for those.

# The workflow <ProfileSettings> differs from the .pxf one (printer-profile
# black generation vs the .pxf's ink-generation form). Embedded verbatim from
# the reference i1Pro3 RGB workflow; only InkLimit varies in principle but all
# RGB references use 300, so it is fixed here.
_PWXF_PROFILE_SETTINGS_RGB = """  <ProfileSettings DeviceType="Printer">
    <!-- Members of ProfileParams -->
    <ProfileVersion value="4"/>
    <EmbeddedProfileVersion value="-1"/>
    <ChromaticAdaptation>Bradford</ChromaticAdaptation>
    <!-- Members of PrinterProfileParams -->
    <BlackGeneration>
      <BlackType>2</BlackType>
      <UseMaximumBlack>0</UseMaximumBlack>
      <BlackWidthType>1</BlackWidthType>
      <BlackWidth>50</BlackWidth>
      <NumberOfCurvePoints>4</NumberOfCurvePoints>
      <KPoints>0 0 18.9465 100 </KPoints>
      <LPoints>0 30 65 100 </LPoints>
      <CurveType>4</CurveType>
    </BlackGeneration>
    <InkLimiting>
      <InkLimit>300</InkLimit>
      <ColorSpace>5</ColorSpace>
    </InkLimiting>
    <ViewingEnvironment>
      <IlluminantName/>
      <IlluminantType>D50</IlluminantType>
    </ViewingEnvironment>
    <ProfileInkColorSpace>5</ProfileInkColorSpace>
    <Saturation>50</Saturation>
    <UseMediaSmoothness>0</UseMediaSmoothness>
    <SmoothnessMedianOverall>-1</SmoothnessMedianOverall>
    <Smoothness>50</Smoothness>
    <Contrast>50</Contrast>
    <NeutralizeGray>0</NeutralizeGray>
    <ChromaAdjust>50</ChromaAdjust>
    <DarkeningForHighChroma>0</DarkeningForHighChroma>
    <WhitePointPaperDeltaEThreshold>3.5</WhitePointPaperDeltaEThreshold>
    <TableSizeAToB>Medium</TableSizeAToB>
    <TableSizeBToA>Medium</TableSizeBToA>
    <BitDepth>16</BitDepth>
  </ProfileSettings>"""


@dataclass
class WorkflowOptions:
    """The 16 layout/device knobs that vary across i1Profiler workflow files.

    Defaults reproduce an A4-landscape i1Pro 3 single-scan chart. ``columns`` /
    ``rows`` / ``emit_locations`` drive the patch grid: with
    ``emit_locations=False`` (Phase 1 default) the grid attributes are still
    written but no per-patch Location tags are, so i1Profiler auto-lays-out.
    """

    device: str = "i1Pro 3"            # free string: "i1Pro 2", "i1Pro 3", "i1iO 2", ...
    measurement_mode: int = 1          # 1 = single scan, 2 = dual scan
    paper_format: int = 2              # 0 = Custom, 2 = A4
    paper_orientation: str = "Landscape"
    page_width_mm: float = 296.93
    page_height_mm: float = 210.06
    columns: int = 29
    rows: int = 20
    pages: int = 1
    patch_w_mm: float = 8.0
    patch_h_mm: float = 7.0
    # i1Profiler sizes patches from the slider PERCENT, not the mm value, and
    # percent 0 is the slider MINIMUM (6 mm on i1Pro 3), NOT "auto". These match
    # 8×7 mm on the i1Pro 3 range (6–25 / 6–12); callers recompute per device.
    patch_w_percent: float = (8.0 - 6) / (25 - 6) * 100
    patch_h_percent: float = (7.0 - 6) / (12 - 6) * 100
    use_patch_defaults: bool = False
    title: str = "ChromIQ Chart"
    emit_locations: bool = False
    # iSis lead-in ("Vorlauf"), as the HeaderEdgeSizePercent slider position.
    # None → write the -2147483648 sentinel that non-iSis devices use.
    header_edge_percent: float | None = None


def _b(v: bool) -> str:
    return "True" if v else "False"


def _mm(v: float) -> str:
    return f"{v:.2f}"


def _pct(v: float) -> str:
    """Format a slider percent: whole numbers as ints (matching i1Profiler's
    own files, e.g. "0"/"100"), otherwise a plain decimal."""
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def _pwxf_custom_attributes(n_patches: int, opt: WorkflowOptions) -> str:
    """Build the full 71-attribute <xrp:CustomAttributes>, reference order."""
    pairs: list[tuple[str, str]] = [
        ("BarCodeEnabled", "False"),
        ("ColorCorrectionPatchCount", "None"),
        ("ColorSpace", "RGB"),
        ("DarkLightRatio", "50"),
        ("DimensionUnit", "2"),
        ("HeaderEdgeSizePercent",
         "-2147483648" if opt.header_edge_percent is None
         else _pct(opt.header_edge_percent)),
        ("ImagePath", ""),
        ("InkLimit", "300"),
        ("LockWriteProtection", "False"),
        ("LowTestChartResolution", "False"),
        ("MeasurementDevice", opt.device),
        ("MeasurementDeviceSerialNumber", "0"),
        ("MeasurementMode", str(opt.measurement_mode)),
        ("MeasurementPerPatch", "0"),
        ("Media_Type", "Translucent Media"),
        ("NumberEmissiveSpotPatches", "0"),
        ("NumberLightTablePatches", "0"),
        ("NumberOfSecondaryPatchesToGenerate", "100"),
        ("NumberPatchColumns", str(opt.columns)),
        ("NumberPatchPages", str(opt.pages)),
        ("NumberPatchRows", str(opt.rows)),
        ("NumberReflectiveMediaSpotPatches", "0"),
        ("NumberReflectiveSpotPatches", "0"),
        ("NumberSecondChartPatches", "0"),
        ("NumberViewingEmissiveSpotPatches", "0"),
        ("NumberViewingReflectiveSpotPatches", "0"),
        ("OptimizeProfile", ""),
        ("PLUS_1_COLOR", "Orange|68.02|43.06|68.15|1|2|50|50|1"),
        ("PLUS_2_COLOR", "Green|87.82|-81.04|71.47|1|2|50|50|2"),
        ("PLUS_3_COLOR", "Red|54.28|78.98|64.91|1|2|50|50|3"),
        ("PLUS_4_COLOR", "Blue|29.57|67.02|-128|1|2|50|50|4"),
        ("PageHeight", _mm(opt.page_height_mm)),
        ("PageWidth", _mm(opt.page_width_mm)),
        ("Paper", "Plain"),
        ("PaperFormat", str(opt.paper_format)),
        ("PaperOrientation", opt.paper_orientation),
        ("PaperType", "Not Specified (default)"),
        ("PatchSizeHeightPercent", _pct(opt.patch_h_percent)),
        ("PatchSizeHeightValue", _mm(opt.patch_h_mm)),
        ("PatchSizeWidthPercent", _pct(opt.patch_w_percent)),
        ("PatchSizeWidthValue", _mm(opt.patch_w_mm)),
        ("PrintMarginBottom", "0.00"),
        ("PrintMarginLeft", "0.00"),
        ("PrintMarginRight", "0.00"),
        ("PrintMarginTop", "0.00"),
        ("PrinterName", "CMYK Printer"),
        ("PrinterType", "Not specified (default)"),
        ("ScramblePatches", "False"),
        ("SelectedMeasurementCondition", "-1"),
        ("TestChartType", "RGB Variable"),
        ("TightMarginsEnabled", "False"),
        ("TitleString", opt.title),
        ("UseLegacyTestChart", "False"),
        ("UsePatchSettingDefaults", _b(opt.use_patch_defaults)),
        ("ViewingLightgboxMeasurementsUsed", "False"),
        ("WriteProtected", "False"),
        ("linearMeasurements", ""),
        ("numLinearSteps", "28"),
        ("numberCorePatches", str(n_patches)),
        ("numberImagePatches", "0"),
        ("numberSpotPatches", "0"),
        ("PerceptualType", "Custom"),
        ("ProfileWhitePointType", "0"),
        ("TableType", "Custom"),
        ("UseLegacyGeneration", "1"),
        ("cmyRatio", "0.0000"),
        ("ControlWedgeType", ""),
        ("ProfileFilename", ""),
        ("ReferenceFileName", ""),
        ("WorkflowStep", "TestChart"),
        ("WorkflowType", "PrinterProfilePro"),
    ]
    attrs = " ".join(f'{k}="{escape(v)}"' for k, v in pairs)
    return f"  <xrp:CustomAttributes {attrs}/>"


def _pwxf_rgb_object(idx: int, v: dict[str, float], created: str,
                     location: tuple[int, int, int] | None) -> list[str]:
    """RGB Object, optionally with a column-major Location tag block."""
    out = _rgb_object(idx, v, created)
    if location is None:
        return out
    col, page, row = location
    loc = [
        '\t\t\t\t<cc:TagCollection Name="Location">',
        f'\t\t\t\t\t<cc:Tag Name="Column" Value="{col}"/>',
        f'\t\t\t\t\t<cc:Tag Name="Page" Value="{page}"/>',
        f'\t\t\t\t\t<cc:Tag Name="Row" Value="{row}"/>',
        '\t\t\t\t\t<cc:Tag Name="SampleID" Value="-1"/>',
        '\t\t\t\t\t<cc:Tag Name="SampleName" Value=""/>',
        "\t\t\t\t</cc:TagCollection>",
    ]
    # insert the Location block before the closing </cc:Object>
    return out[:-1] + loc + out[-1:]


def write_pwxf(
    target: Target,
    out_path: Path,
    descriptor: str,
    options: WorkflowOptions | None = None,
) -> None:
    """Write an i1Profiler workflow (.pwxf) for an RGB target.

    Mirrors a genuine i1Profiler "Prism" workflow file so i1Profiler opens it
    with the instrument/paper/grid pre-configured. RGB only.
    """
    if target.kind != "RGB":
        raise ValueError(
            "i1Profiler workflow (.pwxf) export currently supports RGB targets "
            f"only (got {target.kind}); use the .pxf patch set for CMYK/CMYK+N."
        )
    opt = options or WorkflowOptions()
    created = _pwxf_utc_now()
    n = len(target.rows)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<cc:CxF xmlns:cc="http://colorexchangeformat.com/CxF3-core" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
        "\t<cc:FileInformation>",
        # Mirror X-Rite's own header so i1Profiler's workflow loader accepts the
        # file; the PrismApp tags identify the producing app the way real
        # workflow files do.
        "\t\t<cc:Creator>X-Rite - Prism</cc:Creator>",
        f"\t\t<cc:CreationDate>{created}</cc:CreationDate>",
        "\t\t<cc:Description>Prism CXF3 file</cc:Description>",
        '\t\t<cc:Tag Name="PrismAppName" Value="i1Profiler"/>',
        '\t\t<cc:Tag Name="PrismAppVersion" Value="1.1.0"/>',
        "\t</cc:FileInformation>",
        "\t<cc:Resources>",
        "\t\t<cc:ObjectCollection>",
    ]
    for idx, (_sid, v) in enumerate(target.rows, start=1):
        loc = None
        if opt.emit_locations and opt.rows > 0:
            i = idx - 1
            per_page = opt.columns * opt.rows
            page = i // per_page + 1
            within = i % per_page
            loc = (within // opt.rows, page, within % opt.rows)
        parts += _pwxf_rgb_object(idx, v, created, loc)
    parts.append("\t\t</cc:ObjectCollection>")
    parts += _color_specification()
    parts.append("\t</cc:Resources>")
    parts.append("\t<cc:CustomResources>")
    parts.append('\t\t<xrp:Prism xmlns:xrp="http://www.xrite.com/products/prism" release="2.0">')
    parts.append(_pwxf_custom_attributes(n, opt))
    parts.append(_PWXF_PROFILE_SETTINGS_RGB)
    parts.append("</xrp:Prism>")
    parts.append("")
    parts.append("\t</cc:CustomResources>")
    parts.append("</cc:CxF>")
    parts.append("")
    # Real i1Profiler files use CRLF; emit the same for byte-level familiarity.
    out_path.write_text("\r\n".join(parts), encoding="utf-8")
