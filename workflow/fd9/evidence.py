"""Validate completed rows against preserved FD-9 wire and geometry evidence."""

import hashlib
import json
import struct
from pathlib import Path


def verified_rows(
    source, session, layout_path, *, allow_partial=False, _factory_model=False
):
    from .independent import driver, chart_grid

    driver(source)
    from fd9_independent.protocol import MessageDecoder, RawSpectrum
    from fd9_independent.geometry import find_marks, grid_rows
    from fd9_independent.motion import line_command

    root = Path(session)
    report = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    complete = report.get("success") is True and report.get("phase") == "done"
    expected_calibrated = True if _factory_model else False
    if _factory_model and report.get("conversion_source") != "instrument_model":
        raise ValueError("Require instrument-model acquisition")
    if report.get("calibrated_reflectance") is not expected_calibrated or not (
        complete or allow_partial
    ):
        raise ValueError(
            "Require completed acquisition or explicit partial-row recovery"
        )
    layout = json.loads(Path(layout_path).read_text(encoding="utf-8"))
    expected = chart_grid(layout)
    geometry = json.loads((root / "geometry.json").read_text(encoding="utf-8"))
    if any(
        geometry["grid"].get(k) != v
        for k, v in expected.items()
        if k not in ("mark_origin_mm", "mark_span_mm") or k in geometry["grid"]
    ):
        raise ValueError("Chart axes do not match acquisition grid")
    scan = (root / "scan.pgm").read_bytes()
    head, pixels = scan.split(b"\n255\n", 1)
    width, height = map(int, head.splitlines()[1].split())
    if (
        width != 3638
        or height != report["image_height"]
        or grid_rows(find_marks(pixels, width, height), **expected) != geometry["rows"]
    ):
        raise ValueError("Chart geometry does not match preserved scan")

    selected = report.get("measurement_row_indices", list(range(len(layout["rows"]))))
    if (
        not isinstance(selected, list)
        or not selected
        or any(type(i) is not int or i < 0 for i in selected)
        or selected != list(range(selected[0], len(layout["rows"])))
    ):
        raise ValueError(
            "Only a complete chart or a contiguous remaining-row suffix is supported"
        )
    manifest = json.loads((root / "wire/manifest.json").read_text(encoding="utf-8"))
    wire = (root / "wire/received.bin").read_bytes()
    sent = (root / "wire/sent.bin").read_bytes()
    if (
        hashlib.sha256(wire).hexdigest() != manifest["received_sha256"]
        or hashlib.sha256(sent).hexdigest() != manifest["sent_sha256"]
    ):
        raise ValueError("Transcript hash mismatch")
    requests = []
    offset = 0
    while offset < len(sent):
        if offset + 4 > len(sent):
            raise ValueError("Truncated request transcript")
        side, continuation, size = struct.unpack_from("<BBH", sent, offset)
        if side != 0 or continuation != 0 or size < 4 or offset + 4 + size > len(sent):
            raise ValueError("Invalid request transcript")
        requests.append(sent[offset + 4 : offset + 4 + size])
        offset += 4 + size
    command_ids = [struct.unpack_from("<I", p)[0] for p in requests]
    lines = [p for p in requests if struct.unpack_from("<I", p)[0] == 0x106]
    if not lines or len(lines) > len(selected):
        raise ValueError("Unexpected measurement row count")
    for i, command in enumerate(lines):
        if command != line_command(
            geometry["rows"][selected[i]], i % 6 == 0, i < len(selected) - 1
        ):
            raise ValueError("Acquisition commands do not match chart geometry")
    if command_ids.count(3) != 1:
        raise ValueError("Require one registered acquisition")
    if complete and (
        len(lines) != len(selected)
        or any(command_ids.count(c) != 1 for c in (0x100, 0x101))
        or not max(i for i, c in enumerate(command_ids) if c == 0x106)
        < command_ids.index(0x100)
        < command_ids.index(0x101)
    ):
        raise ValueError("Require completed measurement/home/eject order")

    decoder = MessageDecoder()
    messages = decoder.feed(wire)
    if complete:
        decoder.finish()
    # A stopped socket may end inside its last frame. Only fully decoded,
    # delivered rows before that tail can become measurement data.
    raw = [
        RawSpectrum.decode(p)
        for p in messages
        if struct.unpack_from("<I", p)[0] == 0x305
    ]
    saved = report["raw_samples"]
    columns = len(layout["rows"][0])
    if len(saved) > len(raw) or len(raw) > len(selected) * columns:
        raise ValueError("Unexpected saved/raw sample count")
    for i, (sample, record) in enumerate(zip(raw, saved)):
        if (
            sample.header[1] != i % columns + 1
            or list(sample.header) != record["header"]
            or [list(b) for b in sample.blocks] != record["blocks"]
        ):
            raise ValueError("Saved raw values/order disagree with wire")
    count = len(saved) if complete else len(saved) // columns * columns
    if not count or count % columns or (complete and count != len(selected) * columns):
        raise ValueError(
            "No complete measured rows, or incomplete successful acquisition"
        )
    if complete and len(raw) != count:
        raise ValueError("Unexpected extra raw values")
    measured = selected[: count // columns]
    acknowledgements = [p for p in messages if struct.unpack_from("<I", p)[0] == 0x106]
    if len(acknowledgements) < len(measured) or any(
        len(p) != 8 or struct.unpack_from("<I", p, 4)[0] != 0
        for p in acknowledgements[: len(measured)]
    ):
        raise ValueError("Measured row lacks a successful acknowledgement")
    patches = [p for i in measured for p in layout["rows"][i]]
    return {
        "layout": layout,
        "patches": patches,
        "raw": raw[:count],
        "all_raw": raw[: len(saved)],
        "requests": requests,
        "messages": messages,
        "manifest": manifest,
        "calibration": (root / "instrument-calibration.bin").read_bytes(),
        "acquisition_complete": complete,
        "row_indices": measured,
    }
