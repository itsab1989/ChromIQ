"""Verify automatic rows and live model data against the same connection wire."""

import json
import struct
from pathlib import Path

from .evidence import verified_rows


def verified_factory_rows(source, session, layout_path, *, allow_partial=False):
    evidence = verified_rows(
        source, session, layout_path, allow_partial=allow_partial, _factory_model=True
    )
    from fd9_independent.instrument_model import (
        InstrumentModel,
        model_data_request,
        model_data_reply,
    )
    from fd9_independent.factory import (
        FactoryCharacterization,
        SensorFactoryRecord,
        RECORD_SIZES,
    )

    root = Path(session)
    report = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    requests, messages = evidence["requests"], evidence["messages"]
    command = lambda p: struct.unpack_from("<I", p)[0]
    # Model reads must finish before loading or moving paper. Accept only the
    # fixed read-only spans supported by the version-gated public serializer.
    first_motion = next(
        (
            i
            for i, p in enumerate(requests)
            if command(p) in (4, 0x102, 0x104, 0x105, 0x106)
        ),
        len(requests),
    )
    info_requests = [i for i, p in enumerate(requests) if command(p) == 0x216]
    info_replies = [p for p in messages if command(p) == 0x216]
    if (
        len(info_requests) != 1
        or requests[info_requests[0]] != struct.pack("<I", 0x216)
        or info_requests[0] >= first_motion
        or len(info_replies) != 1
    ):
        raise ValueError("Require one pre-loading sensor-version query")
    info = info_replies[0]
    if (
        len(info) != 48
        or struct.unpack_from("<II", info) != (0x216, 0)
        or info[8:12] != bytes((1, 0, 0, 2))
    ):
        raise ValueError("Unsupported sensor model version")
    spans = [
        (0x0C02E520, 4),
        (0x0C04C378, 4),
        (0x0C02D4F8, 1600),
        (0x0C034C28, 8000),
        (0x0C036B68, 2584),
    ]
    model_requests = [(i, p) for i, p in enumerate(requests) if command(p) == 0x20E]
    model_replies = [p for p in messages if command(p) == 0x20E]
    if (
        len(model_requests) != len(spans)
        or len(model_replies) != len(spans)
        or any(i <= info_requests[0] or i >= first_motion for i, _ in model_requests)
        or [p for _, p in model_requests]
        != [model_data_request(*span) for span in spans]
    ):
        raise ValueError(
            "Require exactly the bounded read-only model requests before loading"
        )
    data = [model_data_reply(reply, *span) for reply, span in zip(model_replies, spans)]
    if (
        int.from_bytes(data[0], "big") != 0x0C034C28
        or int.from_bytes(data[1], "big") != 27
    ):
        raise ValueError("Unsupported spectral model layout")
    factory_requests = [(i, p) for i, p in enumerate(requests) if command(p) == 0x206]
    factory_replies = [p for p in messages if command(p) == 0x206]
    if (
        len(factory_requests) != len(RECORD_SIZES)
        or len(factory_replies) != len(RECORD_SIZES)
        or any(i >= first_motion for i, _ in factory_requests)
        or [p for _, p in factory_requests]
        != [struct.pack("<IBB", 0x206, 0, k) for k in RECORD_SIZES]
    ):
        raise ValueError("Require the pre-loading read-only factory snapshot")
    factory = FactoryCharacterization(
        tuple(
            SensorFactoryRecord.from_reply(p, k)
            for k, p in zip(RECORD_SIZES, factory_replies)
        )
    )
    model = InstrumentModel(
        data[2], b"".join(data[3:]), bytes(info), factory.verified_sections_sha256
    )
    if (
        report.get("factory_sections_sha256") != model.factory_sections_sha256
        or report.get("model_sha256") != model.model_sha256
    ):
        raise ValueError("Reported model or factory fingerprint differs from wire")
    saved_model = root / "spectral-model"
    if any(
        (saved_model / name).read_bytes() != expected
        for name, expected in (
            ("matrix.bin", model.matrix_bytes),
            ("conditions.bin", model.condition_bytes),
            ("sensor-info.bin", model.sensor_info),
        )
    ):
        raise ValueError("Saved spectral model differs from wire")
    metadata = json.loads((saved_model / "model.json").read_text(encoding="utf-8"))
    if any(
        metadata.get(k) != v
        for k, v in {
            "factory_sections_sha256": model.factory_sections_sha256,
            "model_sha256": model.model_sha256,
            "snapshot_sha256": model.snapshot_sha256,
            "sensor_version": [1, 0, 0, 2],
        }.items()
    ):
        raise ValueError("Saved model provenance differs from wire")
    # The fast route delivers spectra as part of a row. Additional finite
    # exposures or cached getters belong to the old point reference backend.
    if any(command(p) == 0x205 for p in requests):
        raise ValueError("Unexpected cached per-point read in automatic row capture")
    if any(command(p) == 0x203 and p != struct.pack("<II", 0x203, 5) for p in requests):
        raise ValueError("Unexpected finite exposure in automatic row capture")
    samples = report.get("native_samples", [])
    if not isinstance(samples, list) or len(samples) > len(evidence["all_raw"]):
        raise ValueError("Unexpected converted sample count")
    converted = []
    for raw, saved in zip(evidence["all_raw"], samples):
        measurement = model.convert(raw)
        if saved != measurement.to_dict():
            raise ValueError("Saved factory conversion differs from raw wire/model")
        converted.append(measurement)
    columns = len(evidence["layout"]["rows"][0])
    rows_complete = len(converted) // columns
    if (
        type(report.get("completed_native_rows")) is not int
        or report["completed_native_rows"] != rows_complete
    ):
        raise ValueError("Converted-row checkpoint disagrees with verified samples")
    if not rows_complete or (
        evidence["acquisition_complete"] and len(converted) != len(evidence["raw"])
    ):
        raise ValueError(
            "No complete converted rows, or incomplete successful acquisition"
        )
    indices = evidence["row_indices"][:rows_complete]
    from .independent import ordered_measurement_rows
    return {
        **evidence,
        "row_indices": indices,
        "patches": [p for row in ordered_measurement_rows(
            evidence["layout"]["rows"], indices, evidence["row_order"]) for p in row],
        "samples": converted[: rows_complete * columns],
        "factory_sections_sha256": model.factory_sections_sha256,
        "model_sha256": model.model_sha256,
        "conversion_source": "instrument_model",
    }
