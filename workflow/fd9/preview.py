"""Derived scan display geometry. Raw acquisition evidence stays untouched."""

import hashlib
import json
import math
import re
from pathlib import Path

from PIL import Image

from .independent import chart_grid, driver
from .measurement import _keywords, sha


def build_scan_preview(session, layout_path, source=None):
    driver(source)
    from fd9_independent.geometry import grid_rows

    session, layout_path = Path(session), Path(layout_path)
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    grid = chart_grid(layout)
    geometry = json.loads((session / "geometry.json").read_text(encoding="utf-8"))
    if geometry["rows"] != grid_rows(geometry["marks"], **grid):
        raise ValueError("Scan display geometry disagrees with acquisition")
    scan = session / "scan.pgm"
    with Image.open(scan) as raw:
        if raw.mode != "L" or raw.width != 3638:
            raise ValueError("Require the original FD9 grayscale scan")
        width, height = raw.size
        image = raw.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    marks = geometry["marks"]
    ox, oy = grid["mark_origin_mm"]
    sx, sy = grid["mark_span_mm"]
    patch = layout.get("patch_mm", [8, 8])
    if len(patch) != 2 or any(not math.isfinite(v) or v <= 0 for v in patch):
        raise ValueError("Invalid scan patch dimensions")

    def project(x, y):
        u, v = 1 - (x - ox) / sx, (y - oy) / sy
        left = [marks[0][i] * (1 - v) + marks[2][i] * v for i in (0, 1)]
        right = [marks[1][i] * (1 - v) + marks[3][i] * v for i in (0, 1)]
        raw_x, raw_y = [left[i] * (1 - u) + right[i] * u for i in (0, 1)]
        # Instrument X uses width - raw_X; a flipped pixel uses width - 1 - raw_X.
        point = [width - 1 - raw_x, raw_y]
        if not 0 <= point[0] < width or not 0 <= point[1] < height:
            raise ValueError("Measurement cell lies outside the scan")
        return point

    rows = []
    for row in layout["rows"]:
        cells = []
        for p in row:
            x, y = p["centre_mm"]
            dx, dy = patch[0] / 2, patch[1] / 2
            cells.append(
                [
                    project(x - dx, y - dy),
                    project(x + dx, y - dy),
                    project(x + dx, y + dy),
                    project(x - dx, y + dy),
                ]
            )
        rows.append(cells)
    image_path = session / "scan-preview.png"
    image.save(image_path)
    event = {
        "image": image_path.name,
        "layout_sha256": sha(layout_path),
        "scan_sha256": sha(scan),
        "rows": rows,
        "size": [width, height],
    }
    (session / "scan-preview.json").write_text(
        json.dumps(event) + "\n", encoding="utf-8"
    )
    return event | {
        "image": str(image_path.resolve()),
        "session": str(session.resolve()),
    }


def saved_scan_preview(chart):
    """Use only the scan belonging to the canonical measurement on this chart."""
    chart = Path(chart)
    try:
        canonical = chart.with_suffix(".ti3")
        session_name = _keywords(canonical.read_text(encoding="utf-8")).get(
            "CHROMIQ_FD9_SESSION", ""
        )
        if not re.fullmatch(r"[A-Za-z0-9_-]+", session_name):
            return None
        session = chart.parent / "fd9-sessions" / session_name
        meta = json.loads(
            (session / "measurement-metadata.json").read_text(encoding="utf-8")
        )
        event = json.loads((session / "scan-preview.json").read_text(encoding="utf-8"))
        if (
            meta["staged_sha256"] != sha(canonical)
            or event["layout_sha256"] != sha(chart.with_suffix(".fd9.json"))
            or event["image"] != "scan-preview.png"
            or not (session / event["image"]).is_file()
        ):
            return None
        return event | {
            "image": str((session / event["image"]).resolve()),
            "session": str(session.resolve()),
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None


def saved_patch_colours(measurement, chart, *, expected=None):
    """Read display-only XYZ for RGB, gray, CMYK and CMYK+N FD-9 charts.

    The general report overlay parser accepts RGB only. Match this backend's
    full device-value tuple and locations before putting readings on its scan.
    """
    from .measurement import checked_chart, first_table
    from workflow.measurement_report import engine_patch_de
    from workflow.verify_expected import apply_expected

    _, layout, locations = checked_chart(chart)
    _, _, design = first_table(chart)
    _, fields, records = first_table(measurement)
    patches = {p["id"]: p for row in layout["rows"] for p in row}
    references = {int(r["SAMPLE_ID"]): r for r in design}
    device_fields = layout.get(
        "device_fields",
        [layout["color_rep"] + "_" + t for t in layout["channel_tokens"]],
    )
    if not all(
        k in fields
        for k in ("SAMPLE_ID", "SAMPLE_LOC", "XYZ_X", "XYZ_Y", "XYZ_Z", *device_fields)
    ):
        return []
    seen, out = set(), []
    for record in records:
        sid = int(record["SAMPLE_ID"])
        if sid in seen or sid not in patches or record["SAMPLE_LOC"] != locations[sid]:
            return []
        seen.add(sid)
        values = [float(record[k]) for k in device_fields]
        if any(
            not math.isfinite(v) or abs(v - original) > 1e-7
            for v, original in zip(values, patches[sid]["device_values"])
        ):
            return []
        exyz = [float(references[sid][k]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
        xyz = [float(record[k]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
        if not all(math.isfinite(v) for v in xyz + exyz):
            return []
        out.append(
            {
                "loc": locations[sid],
                "exyz": exyz,
                "xyz": xyz,
                "de": round(float(engine_patch_de(exyz, xyz)), 2),
            }
        )
    return apply_expected(out, expected)
