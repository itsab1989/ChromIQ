"""Factory-native TI3 export using ChromIQ's bundled D50/2-degree CIE data."""

import hashlib
import json
import math
from pathlib import Path

import numpy as np


def colour_data():
    from workflow.profile_engine.spectral import illuminant_spd, observer_cmf

    lam = np.arange(380, 731, 10, dtype=float)
    # The sensor has already produced the requested measurement condition.
    # Applying D50M2 here would introduce a second UV-cut transformation.
    spd = illuminant_spd("D50", lam)
    cmf = observer_cmf("1931_2", lam)
    digest = hashlib.sha256(
        json.dumps(
            {
                "wavelengths_nm": lam.tolist(),
                "D50": spd.tolist(),
                "1931_2": cmf.tolist(),
                "integration": "CIE15-discrete-Y100-v1",
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    return spd, cmf, digest


def native_colour(values):
    from workflow.profile_engine.ti3_data import xyz_to_lab

    refl = np.asarray(values, dtype=float)
    if refl.shape != (36,) or not np.isfinite(refl).all():
        raise ValueError("Require 36 finite factory-native reflectance values")
    spd, cmf, _ = colour_data()
    # Explicit fraction units: fluorescence can legitimately exceed 1 or 2.
    # Never use an automatic fraction/percent heuristic or clip this spectrum.
    xyz = (100.0 / float((spd * cmf[1]).sum())) * (cmf * spd * refl).sum(axis=1)
    return xyz.tolist(), xyz_to_lab(xyz.reshape(1, 3))[0].tolist()


def export_native(
    source, session, layout_path, output, condition, *, allow_partial=False
):
    from .native_evidence import verified_native_rows

    if condition not in ("M0", "M1", "M2"):
        raise ValueError("Choose M0, M1 or M2")
    report = json.loads((Path(session) / "progress.json").read_text(encoding="utf-8"))
    model_source = report.get("conversion_source") == "instrument_model"
    if model_source:
        from .factory_evidence import verified_factory_rows

        evidence = verified_factory_rows(
            source, session, layout_path, allow_partial=allow_partial
        )
    else:
        evidence = verified_native_rows(
            source, session, layout_path, allow_partial=allow_partial
        )
    layout = evidence["layout"]
    rep, tokens = layout["color_rep"], layout["channel_tokens"]
    if (
        not rep.isalnum()
        or any(not t.isalnum() for t in tokens)
        or len(set(tokens)) != len(tokens)
    ):
        raise ValueError("Malformed ink representation")
    rows = []
    ids = set()
    for patch, sample in zip(evidence["patches"], evidence["samples"]):
        device = patch["device_values"]
        if (
            type(patch["id"]) is not int
            or patch["id"] <= 0
            or patch["id"] in ids
            or len(device) != len(tokens)
            or any(
                type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 100
                for v in device
            )
        ):
            raise ValueError("Invalid native sample ID or device values")
        ids.add(patch["id"])
        spectrum = sample.for_condition(condition).values
        xyz, lab = native_colour(spectrum)
        rows.append(
            str(patch["id"])
            + " "
            + " ".join(
                f"{v:.10f}"
                for v in list(device) + xyz + lab + [100 * v for v in spectrum]
            )
        )
    _, _, cie_digest = colour_data()
    fields = (
        ["SAMPLE_ID"]
        + layout.get("device_fields", [rep + "_" + t for t in tokens])
        + ["XYZ_X", "XYZ_Y", "XYZ_Z", "LAB_L", "LAB_A", "LAB_B"]
        + [f"SPEC_{w}" for w in range(380, 731, 10)]
    )
    from core.cgats_date import created_stamp
    from .support import TARGET_INSTRUMENT

    metadata = {
        "DESCRIPTOR": "FD9 factory-native spectral measurement",
        "ORIGINATOR": "ChromIQ independent FD9",
        # When it was measured, as every other .ti3 says it (Inspect a
        # measurement shows it as "Measured on"; review M6).
        "CREATED": created_stamp(),
        "DEVICE_CLASS": "OUTPUT",
        "COLOR_REP": rep + "_XYZ",
        "TARGET_INSTRUMENT": TARGET_INSTRUMENT,
        "MEASUREMENT_CONDITION": condition,
        "CALIBRATED_REFLECTANCE": "YES",
        "FD9_CONVERSION_SOURCE": (
            "INSTRUMENT_MODEL" if model_source else "INSTRUMENT_FIRMWARE"
        ),
        "FD9_EXPERIMENTAL": "YES",
        "FD9_FACTORY_SHA256": evidence["factory_sections_sha256"],
        "FD9_HOST": evidence["manifest"]["host"],
        "FD9_LAYOUT_SHA256": hashlib.sha256(Path(layout_path).read_bytes()).hexdigest(),
        "FD9_COLOUR_DATA_SHA256": cie_digest,
        "FD9_ACQUISITION_COMPLETE": "YES" if evidence["acquisition_complete"] else "NO",
        "ILLUMINANT": "D50",
        "OBSERVER": "1931_2",
        "SPECTRAL_BANDS": "36",
        "SPECTRAL_START_NM": "380",
        "SPECTRAL_END_NM": "730",
        "SPECTRAL_NORM": "100",
        "COLORIMETRY_COVERAGE_NM": "380 730",
    }
    if model_source:
        metadata["FD9_MODEL_SHA256"] = evidence["model_sha256"]
    if any(
        '"' in str(v) or "\n" in str(v) or "\r" in str(v) for v in metadata.values()
    ):
        raise ValueError("Invalid native metadata")
    text = (
        ["CTI3"]
        + [f'{k} "{v}"' for k, v in metadata.items()]
        + [
            f"NUMBER_OF_FIELDS {len(fields)}",
            "BEGIN_DATA_FORMAT",
            " ".join(fields),
            "END_DATA_FORMAT",
            f"NUMBER_OF_SETS {len(rows)}",
            "BEGIN_DATA",
            *rows,
            "END_DATA",
            "",
        ]
    )
    with Path(output).open("x", encoding="utf-8") as f:
        f.write("\n".join(text))
    return {
        "conversion_source": (
            "instrument_model" if model_source else "instrument_firmware"
        ),
        "model_sha256": evidence.get("model_sha256"),
        "row_indices": evidence["row_indices"],
        "factory_sections_sha256": evidence["factory_sections_sha256"],
        "colour_data_sha256": cie_digest,
        "acquisition_complete": evidence["acquisition_complete"],
    }
