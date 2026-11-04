"""Factory-native TI3 export using ChromIQ's bundled D50/2-degree CIE data."""

import hashlib
import json
import math
from pathlib import Path

import numpy as np


#: How a measurement's XYZ is worked out from its 36 bands (4.3.24).
#:
#: * ``XYZ_METHOD_ARGYLL``: ArgyllCMS's own method
#:   (`workflow.argyll_colorimetry`, the same as ``spec2cie`` to < 0.0001
#:   dE), D50, 1931 2 degree, 1 nm. Every new FD-9 measurement. The .ti3
#:   says so in ``CHROMIQ_XYZ_METHOD``, as the i1Profiler import does.
#: * ``XYZ_METHOD_SUMS``: the 10 nm sums of 4.3.22 and 4.3.23 (about 0.05 dE76
#:   mean and 0.35 max away from ArgyllCMS). A .ti3 without the keyword was
#:   made this way, and a Resume of it goes on this way, so one measurement
#:   never mixes the two.
#:
#: Both use D50 for every condition: the sensor has already produced M0, M1
#: or M2, and applying D50M2 here would be a second UV-cut transformation.
XYZ_METHOD_SUMS = "10 nm sums"
from workflow.reference_convert import (  # noqa: E402 - beside the methods
    XYZ_METHOD_ARGYLL, XYZ_METHOD_KEYWORD)

_WAVELENGTHS = np.arange(380, 731, 10, dtype=float)


def xyz_method_of(keywords: dict) -> str:
    """The method a saved FD-9 .ti3 was converted with, from its header
    keywords: no keyword is the earlier 10 nm sums."""
    value = keywords.get(XYZ_METHOD_KEYWORD)
    if value is None:
        return XYZ_METHOD_SUMS
    if value != XYZ_METHOD_ARGYLL:
        raise ValueError(
            "Resume measurement uses an unknown colour calculation: " + value)
    return XYZ_METHOD_ARGYLL


def colour_data(method=XYZ_METHOD_ARGYLL):
    """(D50, 1931 2 degree, digest) at the FD-9's 36 bands. The digest names
    the method too; for the 10 nm sums it is exactly the digest 4.3.22 and
    4.3.23 recorded, so their sessions still resume."""
    from workflow.profile_engine.spectral import illuminant_spd, observer_cmf

    lam = _WAVELENGTHS
    spd = illuminant_spd("D50", lam)
    cmf = observer_cmf("1931_2", lam)
    if method == XYZ_METHOD_SUMS:
        record = {
            "wavelengths_nm": lam.tolist(),
            "D50": spd.tolist(),
            "1931_2": cmf.tolist(),
            "integration": "CIE15-discrete-Y100-v1",
        }
    elif method == XYZ_METHOD_ARGYLL:
        from workflow.argyll_colorimetry import xyz_weights
        record = {
            "wavelengths_nm": lam.tolist(),
            "method": XYZ_METHOD_ARGYLL,
            "weights": np.round(xyz_weights(lam, illuminant="D50",
                                            observer="1931_2"), 12).tolist(),
            "integration": "ArgyllCMS-xspect-1nm-v1",
        }
    else:
        raise ValueError("Unknown FD-9 colour calculation")
    digest = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode()
    ).hexdigest()
    return spd, cmf, digest


def native_colour(values, method=XYZ_METHOD_ARGYLL):
    from workflow.profile_engine.ti3_data import xyz_to_lab

    refl = np.asarray(values, dtype=float)
    if refl.shape != (36,) or not np.isfinite(refl).all():
        raise ValueError("Require 36 finite factory-native reflectance values")
    # Explicit fraction units: fluorescence can legitimately exceed 1 or 2.
    # Never use an automatic fraction/percent heuristic or clip this spectrum.
    if method == XYZ_METHOD_ARGYLL:
        from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll
        xyz = spectra_to_xyz_like_argyll(
            refl, _WAVELENGTHS, illuminant="D50", observer="1931_2",
            percent=False, clamp=False)[0]
    elif method == XYZ_METHOD_SUMS:
        spd, cmf, _ = colour_data(XYZ_METHOD_SUMS)
        xyz = (100.0 / float((spd * cmf[1]).sum())) * (
            cmf * spd * refl).sum(axis=1)
    else:
        raise ValueError("Unknown FD-9 colour calculation")
    return list(map(float, xyz)), xyz_to_lab(
        np.asarray(xyz, dtype=float).reshape(1, 3))[0].tolist()


def export_native(
    source, session, layout_path, output, condition, *, allow_partial=False,
    method=XYZ_METHOD_ARGYLL,
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
    # Pair in acquisition order first, then restore logical row order for a
    # stable complete-row prefix, including partial saves and later resumes.
    ranks = {p["id"]: i for i, p in enumerate(
        p for row in layout["rows"] for p in row)}
    pairs = sorted(zip(evidence["patches"], evidence["samples"]),
                   key=lambda pair: ranks[pair[0]["id"]])
    for patch, sample in pairs:
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
        xyz, lab = native_colour(spectrum, method)
        rows.append(
            str(patch["id"])
            + " "
            + " ".join(
                f"{v:.10f}"
                for v in list(device) + xyz + lab + [100 * v for v in spectrum]
            )
        )
    _, _, cie_digest = colour_data(method)
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
    if method == XYZ_METHOD_ARGYLL:
        metadata[XYZ_METHOD_KEYWORD] = XYZ_METHOD_ARGYLL
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
        "xyz_method": method,
        "acquisition_complete": evidence["acquisition_complete"],
    }
