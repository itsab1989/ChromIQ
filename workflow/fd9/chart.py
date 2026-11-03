"""Printable single-sheet FD-9 grids for the independently supported geometry.

The grid fills the selected sheet with fixed-size patches. The
sheet envelope is deliberately narrower than the manufacturer's hardware spec.
No SDK is used to generate, render, or measure these charts.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

MAX_COLUMNS = 64
MAX_ROWS = 128
MIN_WIDTH, MAX_WIDTH = 137.0, 330.0
MIN_HEIGHT, MAX_HEIGHT = 170.0, 660.0
#: The sheets offered for the FD-9, named the way they go INTO the FD-9 (width
#: across the feed x length along it). A4R / LetterR are the landscape sheets:
#: 297 x 210 and 279.4 x 215.9 mm, inside the 137..330 x 170..660 envelope.
PAPERS = ("137x300", "A4", "A4R", "Letter", "LetterR", "A3", "329x483",
          "330x660")
PATCH = 8.0
PITCH = 9.0


def dimensions(paper):
    from workflow.layout_engine.papers import dimensions_mm

    width, height = dimensions_mm(paper)
    if not (
        math.isfinite(width)
        and math.isfinite(height)
        and MIN_WIDTH <= width <= MAX_WIDTH
        and MIN_HEIGHT <= height <= MAX_HEIGHT
    ):
        raise ValueError(
            "FD-9 sheets must be 137..330 mm wide and 170..660 mm long, in feed orientation"
        )
    return width, height


def patch_size(value=8.0):
    value = float(value)
    if not math.isfinite(value) or not 6 <= value <= 30:
        raise ValueError("FD-9 patch size must be 6..30 mm")
    return value


def patch_dimensions(patch_mm=8.0, patch_height_mm=None, gap_mm=1.0, dpi=300):
    width = patch_size(patch_mm)
    height = patch_size(width if patch_height_mm is None else patch_height_mm)
    gap = float(gap_mm)
    if not math.isfinite(gap) or not 0 <= gap <= 5:
        raise ValueError("FD-9 patch gap must be 0..5 mm")
    # With touching cells, shared pixel boundaries must never produce a patch
    # below the six-mm floor. Realise that small increase in the definition and
    # PDF too, so scan coordinates and both print formats describe one grid.
    if gap == 0 and dpi is not None:
        if not 72 <= int(dpi) <= 600:
            raise ValueError("FD-9 chart resolution must be 72..600 dpi")
        minimum = math.ceil(6 * dpi / 25.4) * 25.4 / dpi
        width, height = max(width, minimum), max(height, minimum)
    return width, height, gap


def grid_shape(paper, patch_mm=8.0, patch_height_mm=None, gap_mm=1.0, dpi=300):
    width, height = dimensions(paper)
    pw, ph, gap = patch_dimensions(patch_mm, patch_height_mm, gap_mm, dpi)
    columns = min(MAX_COLUMNS, 1 + math.floor((width - 30 - pw) / (pw + gap)))
    rows = min(MAX_ROWS, 1 + math.floor((height - 33 - ph / 2 - 42) / (ph + gap)))
    return columns, rows


def capacity(paper, patch_mm=8.0, patch_height_mm=None, gap_mm=1.0, dpi=300):
    columns, rows = grid_shape(paper, patch_mm, patch_height_mm, gap_mm, dpi)
    return columns * rows


def packing(paper, count, patch_mm=8.0, patch_height_mm=None, gap_mm=1.0, dpi=300):
    from workflow.layout_engine.geometry import Layout

    columns, max_rows = grid_shape(paper, patch_mm, patch_height_mm, gap_mm, dpi)
    cap = columns * max_rows
    if count < 1:
        raise ValueError("An FD-9 chart needs at least one patch")
    rows = min(max_rows, math.ceil(count / columns))
    pages = math.ceil(count / cap)
    padded = math.ceil(count / columns) * columns
    return Layout(rows, columns, 1, columns, cap, pages, padded - count, padded, rows)


def _calibration_target(
    target,
    ti1_path,
    paper,
    enabled,
    patch_mm=8.0,
    patch_height_mm=None,
    gap_mm=1.0,
    dpi=300,
):
    """One pure single-ink ramp per printed column; preserve targen tables."""
    if not enabled:
        return target, None, 0, None
    from workflow.layout_engine.calibration_ramps import find_ramps, rewrite_ti1_text
    from workflow.layout_engine.ti1_reader import ColorTarget
    import re

    ramps = find_ramps([dev for dev, xyz in target.patches])
    if ramps is None:
        return target, None, 0, None
    text = Path(ti1_path).read_text(encoding="utf-8")
    header = text.split("NUMBER_OF_FIELDS", 1)[0]
    previously_arranged = bool(
        re.search(r'^FD9_CALIBRATION_ROWS\s+"\d+"', header, re.M)
    )
    if not ramps.is_targen_order and not previously_arranged:
        return target, None, 0, None
    available_columns, max_rows = grid_shape(
        paper, patch_mm, patch_height_mm, gap_mm, dpi
    )
    rows = min(max(len(steps) + 1 for steps in ramps.ramps), max_rows)
    columns = sum(math.ceil((len(steps) + 1) / rows) for steps in ramps.ramps)
    if columns > available_columns:
        raise ValueError(
            "FD-9 calibration ramps do not fit on one sheet; reduce the steps or use a larger sheet"
        )
    order = []
    for steps in ramps.ramps:
        block = [ramps.whites[0], *steps]
        block += [ramps.whites[0]] * (-len(block) % rows)
        order += block
    order += [ramps.whites[0]] * (available_columns * rows - len(order))
    patches = [target.patches[i] for i in order]
    rewritten = rewrite_ti1_text(text, order)
    rewritten = re.sub(r'^FD9_CALIBRATION_ROWS\s+"\d+"\s*\n', "", rewritten, flags=re.M)
    rewritten = re.sub(r'^KEYWORD\s+"FD9_CALIBRATION_ROWS"\s*\n', "", rewritten,
                       flags=re.M)
    first_line, rest = rewritten.split("\n", 1)
    # Declared, as CGATS wants for a keyword of its own (review Low).
    rewritten = (first_line + '\nKEYWORD "FD9_CALIBRATION_ROWS"\n'
                 + f'FD9_CALIBRATION_ROWS "{rows}"\n' + rest)
    return (
        ColorTarget(target.color_rep, target.device_fields, patches, target.ink_limit),
        rows,
        max(0, len(patches) - len(target.patches)),
        rewritten,
    )


def build_chart(
    ti1_path,
    out_base,
    *,
    paper="A4",
    dpi=300,
    randomize=True,
    seed=None,
    bit16=False,
    cal_path=None,
    apply_cal=False,
    export_pdf=False,
    ramps_per_strip=False,
    patch_mm=8.0,
    patch_height_mm=None,
    gap_mm=1.0,
    compression="lzw",
    **unused,
):
    """Create device-native TIFF + matching TI2 and FD9 physical definition.

    A single sheet is the current measurement implementation's explicit limit.
    Reject larger requests before writing rather than dropping/splitting patches.
    """
    from workflow.layout_engine.ti1_reader import read_ti1
    from workflow.layout_engine.chart import ChartResult
    from core.stem_paths import artefact
    from workflow.layout_engine.labels import alpha_label
    from workflow.layout_engine.raster import (
        save_separated_tiffs,
        ink_names_from_fields,
    )
    from PIL import Image, ImageDraw
    import numpy as np

    requested = [
        patch_size(patch_mm),
        patch_size(patch_mm if patch_height_mm is None else patch_height_mm),
    ]
    pw, ph, gap = patch_dimensions(*requested, gap_mm, dpi)
    pitch_x, pitch_y = pw + gap, ph + gap
    width, height = dimensions(paper)
    target = read_ti1(ti1_path)
    target, ramp_rows, added_whites, rewritten_ti1 = _calibration_target(
        target, ti1_path, paper, ramps_per_strip, pw, ph, gap, None
    )
    if ramp_rows is not None:
        randomize = False
    count = len(target.patches)
    if count > capacity(paper, pw, ph, gap, None):
        raise ValueError(
            f"FD-9 currently supports one sheet: this size fits {capacity(paper, pw, ph, gap, None)} patches; reduce the patch count or use a larger sheet"
        )
    cal = None
    if cal_path:
        from workflow.layout_engine.calibration import read_cal, check_matches

        cal = read_cal(cal_path)
        check_matches(target, cal)
    if not 72 <= int(dpi) <= 600:
        raise ValueError("FD-9 chart resolution must be 72..600 dpi")
    rep = "RGB" if target.color_rep == "iRGB" else target.color_rep
    fields = target.device_fields
    if not 1 <= len(fields) <= 16:
        raise ValueError("FD-9 charts support 1..16 device channels")
    tokens = [f.split("_", 1)[1] for f in fields]
    # Argyll's lower-case light inks are distinct physical channels.
    aliases = {"c": "LC", "m": "LM", "y": "LY", "k": "LK", "1k": "LLK"}
    print_fields = [rep + "_" + aliases.get(t, t) for t in tokens]
    if (
        len(set(tokens)) != len(tokens)
        or not rep.isalnum()
        or any(not t.isalnum() for t in tokens)
    ):
        raise ValueError("Unsupported FD-9 ink channel names")
    if any(
        not math.isfinite(v) or not 0 <= v <= 100
        for dev, xyz in target.patches
        for v in dev
    ):
        raise ValueError("FD-9 patch values must be finite percentages from 0 to 100")
    if any(not math.isfinite(v) for dev, xyz in target.patches for v in xyz):
        raise ValueError("FD-9 patch aim values must be finite")
    base = Path(out_base)
    layout = packing(paper, count, pw, ph, gap, None)
    columns, _ = grid_shape(paper, pw, ph, gap, None)
    nrows = math.ceil(count / columns)
    size = (round(width * dpi / 25.4), round(height * dpi / 25.4))
    gray_ink = target.color_rep == "K" and len(fields) == 1
    additive = (
        target.color_rep in ("RGB", "iRGB", "W") and len(fields) <= 3
    ) or gray_ink
    channels = 3 if additive else len(fields)
    if not additive and channels < 4:
        raise ValueError(
            "FD-9 separated output requires CMYK or CMYK+N; use RGB for a three-channel printer"
        )
    if size[0] * size[1] * channels * (2 if bit16 else 1) > 512 * 1024 * 1024:
        raise ValueError("FD-9 raster exceeds 512 MiB; reduce resolution or sheet size")
    white = tuple(100.0 if additive and not gray_ink else 0.0 for _ in fields)
    from workflow.layout_engine.ti2_writer import DEFAULT_WHITE_POINT

    # Padding cells are paper white, with the same media-white aim the layout
    # engine gives its padding (D50, not D65; review Low).
    patches = list(target.patches) + [(white, DEFAULT_WHITE_POINT)] * layout.padding
    order = list(range(len(patches)))
    seed = random.SystemRandom().randrange(1, 2**31) if seed is None else int(seed)
    if randomize:
        from workflow.layout_engine.permutation import location_permutation

        slots = location_permutation(len(patches), seed, True)
        for canonical, slot in enumerate(slots):
            order[slot] = canonical
    first_x = (width - ((columns - 1) * pitch_x + pw)) / 2 + pw / 2
    marks = [
        [x, y]
        for x, y in (
            (5.5, 32.5),
            (width - 5.5, 32.5),
            (5.5, 42 + (nrows - 1) * pitch_y + 9.5),
            (width - 5.5, 42 + (nrows - 1) * pitch_y + 9.5),
        )
    ]
    # Isolated 3 mm squares and a narrow arrow match the independently tested
    # detector; labels are outside the mark rectangle and cannot join a patch.
    arrow = [
        (width / 2 - 1, 29),
        (width / 2 + 1, 29),
        (width / 2 + 1, 20),
        (width / 2 + 4.5, 20),
        (width / 2, 15),
        (width / 2 - 4.5, 20),
        (width / 2 - 1, 20),
    ]
    from .support import TARGET_INSTRUMENT

    doc = {
        "schema": 1,
        "name": base.name,
        "instrument": TARGET_INSTRUMENT,
        "paper_mm": [width, height],
        "patch_mm": [pw, ph],
        "gap_mm": [gap, gap],
        "fiducials_mm": marks,
        "color_rep": rep,
        "channel_tokens": tokens,
        "device_fields": fields,
        "channels": tokens,
        "feed_orientation": "Arrow first, printed face up",
        "rows": [],
        "generation": {
            "requested_patch_mm": requested,
            "designed_patches": count,
            "padding_patches": layout.padding,
            "seed": seed,
            "randomize": bool(randomize),
            "dpi": int(dpi),
            "paper": paper,
            "single_sheet": True,
        },
    }
    rows = []
    for row in range(nrows):
        cells = []
        for col in range(columns):
            slot = col * nrows + row
            index = order[slot]
            x, y = first_x + col * pitch_x, 42 + row * pitch_y
            dev, xyz = patches[index]
            cells.append(
                {"id": index + 1, "centre_mm": [x, y], "device_values": list(dev)}
            )
            rows.append((index + 1, f"{alpha_label(col+1)}{row+1}", dev, xyz))
        doc["rows"].append(cells)
    # Check the exact same geometry that the measurement route accepts.
    from .independent import chart_grid

    chart_grid(doc)
    maxval = 65535 if bit16 else 255
    dtype = np.uint16 if bit16 else np.uint8
    arr = np.full((size[1], size[0], channels), maxval if additive else 0, dtype=dtype)
    mask = Image.new("1", size, 0)
    draw = ImageDraw.Draw(mask)

    def box(x0, y0, x1, y1):
        return tuple(round(v * dpi / 25.4) for v in (x0, y0, x1, y1))

    for x, y in marks:
        draw.rectangle(box(x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=1)
    draw.polygon(
        [(round(x * dpi / 25.4), round(y * dpi / 25.4)) for x, y in arrow], fill=1
    )
    ink = np.zeros(channels, dtype=dtype)
    if not additive:
        # Furniture in the actual black channel, never in every ink.
        black = next((i for i, t in enumerate(tokens) if t == "K"), None)
        if black is None:
            raise ValueError(
                "FD-9 separated charts need a K channel for registration marks"
            )
        ink[black] = maxval
    arr[np.asarray(mask, dtype=bool)] = ink
    for ri, row in enumerate(doc["rows"]):
        for ci, cell in enumerate(row):
            x, y = cell["centre_mm"]
            x0, y0, x1, y1 = box(x - pw / 2, y - ph / 2, x + pw / 2, y + ph / 2)
            if gap == 0:
                scale = dpi / 25.4
                anchor_x = round((first_x - pw / 2) * scale)
                anchor_y = round((42 - ph / 2) * scale)
                x0, x1 = (anchor_x + round(c * pw * scale) for c in (ci, ci + 1))
                y0, y1 = (anchor_y + round(r * ph * scale) for r in (ri, ri + 1))
            # Quantization must not make a nominal 6 mm patch smaller than
            # the instrument's minimum in either raster dimension.
            minimum = math.ceil(6 * dpi / 25.4)
            x1, y1 = max(x1, x0 + minimum), max(y1, y0 + minimum)
            dev = cell["device_values"]
            if cal is not None and apply_cal:
                dev = cal.apply(tuple(dev))
            values = dev if not additive or len(dev) == 3 else [dev[0]] * 3
            val = [(100 - v if gray_ink else v) / 100 * maxval for v in values]
            arr[y0:y1, x0:x1] = np.rint(val).astype(dtype)
    base.parent.mkdir(parents=True, exist_ok=True)
    tiff_compression = None if compression in (None, "", "none") else compression
    if additive:
        import tifffile

        tifffile.imwrite(
            str(artefact(base, ".tif")),
            arr,
            photometric="rgb",
            resolution=(dpi, dpi),
            resolutionunit="inch",
            compression=tiff_compression,
        )
        tiffs = [artefact(base, ".tif")]
    else:
        tiffs = save_separated_tiffs(
            [arr],
            artefact(base, ".tif"),
            dpi,
            ink_names=ink_names_from_fields(print_fields),
            compression=compression or "none",
        )
    from core.cgats_date import created_stamp
    from workflow.layout_engine.ti2_writer import DEFAULT_WHITE_POINT as _wp

    # The header the layout engine writes for every chart (ti2_writer), so an
    # FD-9 chart reads like the others: DESCRIPTOR, CREATED, the instrument's
    # full name and the media white point (review M6).
    lines = [
        "CTI2",
        "",
        'DESCRIPTOR "Argyll Calibration Target chart information 2"',
        'ORIGINATOR "ChromIQ independent FD9 layout"',
        f'CREATED "{created_stamp()}"',
        f'TARGET_INSTRUMENT "{TARGET_INSTRUMENT}"',
        'APPROX_WHITE_POINT "%s"' % " ".join(f"{c:.6f}" for c in _wp),
        f'COLOR_REP "{rep}"',
        f'PAPER_SIZE "{width:g}x{height:g}"',
        f'STEPS_IN_PASS "{nrows}"',
        f'PASSES_IN_STRIPS2 "{columns}"',
        'STRIP_INDEX_PATTERN "A-Z, A-Z"',
        'PATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"',
        'INDEX_ORDER "STRIP_THEN_PATCH"',
        f'{"RANDOM_START" if randomize else "CHART_ID"} "{seed}"',
    ]
    if target.ink_limit is not None:
        lines.append(f'TOTAL_INK_LIMIT "{target.ink_limit:g}"')
    fmt = ["SAMPLE_ID", "SAMPLE_LOC"] + fields + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    lines += [
        f"NUMBER_OF_FIELDS {len(fmt)}",
        "BEGIN_DATA_FORMAT",
        " ".join(fmt),
        "END_DATA_FORMAT",
        f"NUMBER_OF_SETS {len(rows)}",
        "BEGIN_DATA",
    ]
    lines += [
        f'{i} "{loc}" ' + " ".join(f"{v:.10f}" for v in tuple(dev) + tuple(xyz))
        for i, loc, dev, xyz in sorted(rows)
    ]
    lines += ["END_DATA", ""]
    if cal is not None:
        from workflow.layout_engine.calibration import cal_table_text

        lines.append(cal_table_text(cal))
    artefact(base, ".ti2").write_text("\n".join(lines), encoding="utf-8")
    artefact(base, ".fd9.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )
    # Standard sidecar retained by the existing chart archive/import machinery.
    side = artefact(base, ".strips.json")
    from workflow.layout_engine import geometry, instruments

    geom = instruments.geom_from_build_kwargs(
        {"instrument": "FD9", "patch_w": pw, "patch_h": ph, "fd9_gap": gap, "dpi": dpi}
    )
    strips = geometry.strip_rects_px(geom, width, height, layout, dpi)
    rects = geometry.patch_rects_px(geom, width, height, layout, dpi)
    side.write_text(
        json.dumps(
            {
                "dpi": dpi,
                "paper_mm": [width, height],
                "steps_in_pass": nrows,
                "strip_pattern": "A-Z, A-Z",
                "patch_pattern": "0-9,@-9,@-9;1-999",
                "label_rule": "argyll",
                "strips": strips,
                "patches": rects,
            }
        ),
        encoding="utf-8",
    )
    pdf_path = None
    if export_pdf:
        from types import SimpleNamespace
        from workflow.layout_engine.vector_pdf import save_vector_pdf

        def vector_box(*coords):
            return tuple(v * dpi / 25.4 for v in coords)

        ink_values = tuple(float(v) / maxval * 100 for v in ink)
        if gray_ink:
            ink_values = (0.0,)
        elements = [
            ("rect", vector_box(x - 1.5, y - 1.5, x + 1.5, y + 1.5), ink_values)
            for x, y in marks
        ]
        elements.append(
            ("hex", [(x * dpi / 25.4, y * dpi / 25.4) for x, y in arrow], ink_values)
        )
        for row in doc["rows"]:
            for cell in row:
                x, y = cell["centre_mm"]
                values = cell["device_values"]
                if cal is not None and apply_cal:
                    values = cal.apply(tuple(values))
                if gray_ink:
                    values = [100 - v for v in values]
                elements.append(
                    (
                        "rect",
                        vector_box(
                            x - pw / 2,
                            y - ph / 2,
                            x + pw / 2,
                            y + ph / 2,
                        ),
                        values,
                    )
                )
        pdf_path = save_vector_pdf(
            SimpleNamespace(patch_geom=[elements]),
            SimpleNamespace(device_fields=print_fields, color_rep=target.color_rep),
            artefact(base, ".pdf"),
            paper_w_mm=width,
            paper_h_mm=height,
            dpi=dpi,
        )
    if rewritten_ti1 is not None:
        Path(ti1_path).write_text(rewritten_ti1, encoding="utf-8")
    return ChartResult(
        artefact(base, ".ti2"),
        seed,
        bool(randomize),
        rep,
        layout,
        tiffs,
        strips,
        pdf_path=pdf_path,
        ramp_whites_added=added_whites,
    )
