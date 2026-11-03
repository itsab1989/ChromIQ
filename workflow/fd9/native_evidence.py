"""Check factory-native spectra against their preserved wire and chart geometry.

No manufacturer host software, fitted conversion or reference reading is used.
Only full rows can be recovered from an interrupted acquisition.
"""

import hashlib
import json
import struct
from pathlib import Path


def verified_native_rows(source, session, layout_path, *, allow_partial=False):
    from .independent import driver, chart_grid

    driver(source)
    from fd9_independent.protocol import MessageDecoder, RawSpectrum
    from fd9_independent.geometry import find_marks, grid_rows
    from fd9_independent.motion import line_command
    from fd9_independent.native import (
        NativeMeasurement,
        NativeSpectrum,
        NativeCondition,
    )
    from fd9_independent.native import finite_native_request, native_controls
    from fd9_independent.sensor_data import CachedSensorData, cached_data_request
    from fd9_independent.factory import FactoryCharacterization, SensorFactoryRecord

    root = Path(session)
    report = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    complete = report.get("success") is True and report.get("phase") == "done"
    if (
        report.get("conversion_source") != "instrument_firmware"
        or report.get("calibrated_reflectance") is not True
        or not (complete or allow_partial)
    ):
        raise ValueError("Require factory-native acquisition evidence")
    layout_bytes = Path(layout_path).read_bytes()
    layout = json.loads(layout_bytes)
    if json.loads((root / "chart-definition.json").read_bytes()) != layout:
        raise ValueError("Chart definition changed since acquisition")
    grid = chart_grid(layout)
    geometry = json.loads((root / "geometry.json").read_text(encoding="utf-8"))
    scan = (root / "scan.pgm").read_bytes()
    head, pixels = scan.split(b"\n255\n", 1)
    width, height = map(int, head.splitlines()[1].split())
    if (
        head.splitlines()[0] != b"P5"
        or width != 3638
        or height != report["image_height"]
        or len(pixels) != width * height
        or geometry["grid"] != grid
        or grid_rows(find_marks(pixels, width, height), **grid) != geometry["rows"]
    ):
        raise ValueError("Native geometry does not match preserved chart scan")
    selected = report.get("measurement_row_indices")
    if (
        not isinstance(selected, list)
        or not selected
        or any(type(i) is not int or i < 0 for i in selected)
        or selected != list(range(selected[0], len(layout["rows"])))
    ):
        raise ValueError("Native acquisition needs a contiguous remaining-row suffix")
    manifest = json.loads((root / "wire/manifest.json").read_text(encoding="utf-8"))
    sent = (root / "wire/sent.bin").read_bytes()
    received = (root / "wire/received.bin").read_bytes()
    for data, key in ((sent, "sent_sha256"), (received, "received_sha256")):
        if hashlib.sha256(data).hexdigest() != manifest[key]:
            raise ValueError("Native transcript hash mismatch")
    requests = []
    offset = 0
    while offset < len(sent):
        if offset + 4 > len(sent):
            raise ValueError("Truncated native request transcript")
        side, continuation, size = struct.unpack_from("<BBH", sent, offset)
        if side != 0 or continuation != 0 or size < 4 or offset + 4 + size > len(sent):
            raise ValueError("Invalid native request transcript")
        requests.append(sent[offset + 4 : offset + 4 + size])
        offset += 4 + size
    command = lambda p: struct.unpack_from("<I", p)[0]
    ids = list(map(command, requests))
    if ids.count(3) != 1:
        raise ValueError("Require one registered native acquisition")
    decoder = MessageDecoder()
    messages = decoder.feed(received)
    if complete:
        decoder.finish()
    columns = len(layout["rows"][0])
    plan = [
        (p, r % 6 == 0 and c == 0)
        for r, row_index in enumerate(selected)
        for c, p in enumerate(geometry["rows"][row_index])
    ]
    # Every position ends its ordinary row. A fresh finite entry is then
    # peeked for all three conditions and consumed once, before moving again.
    getters = (
        [(0, (0, 0, 0, 0))]
        + [(1, native_controls(m)) for m in ("M0", "M1", "M2")]
        + [(0, (0, 0, 0, 0)), (0, (1, 0, 0, 0))]
    )
    expected = []
    for point, calibrate in plan:
        expected.extend(
            [line_command([point], calibrate, False), finite_native_request(2)]
        )
        expected.extend(cached_data_request(s, c) for s, c in getters)
    try:
        start = ids.index(0x106)
    except ValueError:
        raise ValueError("No native positioning request") from None
    operations = [p for p in requests[start:] if command(p) in (0x106, 0x203, 0x205)]
    # A failed, owned finite start may end with the documented sensor stop.
    # That cleanup is not another acquired point and must not discard earlier
    # full rows. No other off-sequence command is accepted.
    if not complete and operations and operations[-1] == struct.pack("<IB", 0x203, 4):
        operations = operations[:-1]
    saved = report.get("native_samples", [])
    n = len(saved)
    if (
        not n
        or n > len(plan)
        or operations != expected[: len(operations)]
        or len(operations) < 8 * n
        or len(operations) > min(len(expected), 8 * (n + 1))
        or (complete and (n != len(plan) or operations != expected))
    ):
        raise ValueError("Native request sequence/count disagrees with chart positions")

    # Factory records stay opaque. Their checksums and observed stable sections
    # bind a resumed measurement to the same characterization without shipping
    # any unit's numerical data in the application.
    factory_requests = [p for p in requests if command(p) == 0x206]
    factory_replies = [p for p in messages if command(p) == 0x206]
    if (
        not factory_requests
        or len(factory_requests) != len(factory_replies)
        or len(factory_requests) % 11
        or any(
            p != struct.pack("<IBB", 0x206, 0, i % 11)
            for i, p in enumerate(factory_requests)
        )
    ):
        raise ValueError("Require complete read-only factory snapshots")
    digests = []
    for begin in range(0, len(factory_replies), 11):
        snapshot = FactoryCharacterization(
            tuple(
                SensorFactoryRecord.from_reply(p, i)
                for i, p in enumerate(factory_replies[begin : begin + 11])
            )
        )
        digests.append(snapshot.verified_sections_sha256)
    digest = report.get("factory_sections_sha256")
    if any(d != digest for d in digests):
        raise ValueError("Factory characterization changed during acquisition")

    raw = [RawSpectrum.decode(p) for p in messages if command(p) == 0x305]
    raw_saved = report.get("raw_samples", [])
    if (
        len(raw_saved) > len(raw)
        or len(raw) > len(plan)
        or len(raw_saved) < n
        or (complete and len(raw) != n)
    ):
        raise ValueError("Unexpected native positioning sample count")
    for sample, record in zip(raw, raw_saved):
        if (
            sample.header[1] != 1
            or list(sample.header) != record["header"]
            or [list(b) for b in sample.blocks] != record["blocks"]
        ):
            raise ValueError("Native positioning values disagree with wire")
    cached = [p for p in messages if command(p) == 0x205]
    if len(cached) < 6 * n or (complete and len(cached) != 6 * n):
        raise ValueError("Missing or extra native sensor replies")
    samples = []
    for i, record in enumerate(saved):
        data = [
            CachedSensorData.from_reply(p, selector, controls)
            for p, (selector, controls) in zip(cached[6 * i : 6 * i + 6], getters)
        ]
        basic = data[0]
        if any(
            (d.sum_count, d.data_count, d.measurement_flags) != (2, 1, 0) for d in data
        ):
            raise ValueError("Native entry has invalid integration/data/flag values")
        if data[4] != basic or (data[5].values, data[5].opaque_header) != (
            basic.values,
            basic.opaque_header,
        ):
            raise ValueError("Native peeks/advance did not preserve the same raw entry")
        measurement = NativeMeasurement(
            basic,
            tuple(
                NativeSpectrum(
                    NativeCondition(m),
                    d.values,
                    d.sum_count,
                    d.data_count,
                    d.measurement_flags,
                )
                for m, d in zip(("M0", "M1", "M2"), data[1:4])
            ),
            digest,
            manifest["host"],
            manifest.get("port", 49152),
        )
        if measurement.to_dict() != record:
            raise ValueError("Saved native spectra/condition/order disagree with wire")
        samples.append(measurement)
    # The ordinary positioning point must be followed by fresh readiness and
    # all six queue reads before another positioning point can be accepted.
    positions = [i for i, p in enumerate(messages) if command(p) == 0x305]
    from fd9_independent.protocol import SheetStatus

    for i in range(n):
        segment = messages[
            positions[i] + 1 : positions[i + 1] if i + 1 < len(positions) else None
        ]
        first_cached = next(
            (j for j, p in enumerate(segment) if command(p) == 0x205), -1
        )
        starts = [p for p in segment[:first_cached] if command(p) == 0x203]
        if (
            first_cached < 0
            or sum(command(p) == 0x205 for p in segment) != 6
            or starts != [struct.pack("<IIBB", 0x203, 0, 0, 0)]
            or not any(
                (s.mechanism, s.paper, s.stop, s.fatal) == (5, 1, 0, 0)
                for p in segment[:first_cached]
                if command(p) == 0x300
                for s in [SheetStatus.decode(p)]
            )
        ):
            raise ValueError(
                "Native point lacks fresh ready barrier or complete queue reads"
            )
    acks = [p for p in messages if command(p) == 0x106]
    if len(acks) < n or any(p != struct.pack("<II", 0x106, 0) for p in acks[:n]):
        raise ValueError("Native point lacks successful positioning acknowledgement")
    if complete and (
        any(ids.count(c) != 1 for c in (0x100, 0x101))
        or not max(i for i, c in enumerate(ids) if c == 0x205)
        < ids.index(0x100)
        < ids.index(0x101)
    ):
        raise ValueError("Require final native home/ejection order")
    if complete and any(
        [p for p in messages if command(p) == c] != [struct.pack("<II", c, 0)]
        for c in (0x100, 0x101)
    ):
        raise ValueError("Native home/ejection acknowledgement failed")
    count = n if complete else n // columns * columns
    if (
        not count
        or count % columns
        or report.get("completed_native_rows") != n // columns
    ):
        raise ValueError(
            "No complete verified native rows, or invalid completed-row marker"
        )
    measured = selected[: count // columns]
    return {
        "layout": layout,
        "patches": [p for i in measured for p in layout["rows"][i]],
        "samples": samples[:count],
        "manifest": manifest,
        "factory_sections_sha256": digest,
        "row_indices": measured,
        "acquisition_complete": complete,
    }
