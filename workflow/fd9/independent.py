"""SDK-free FD9 research capture/export; preserves CMYK+N chart values."""

import csv, hashlib, importlib, json, math, struct, sys
from pathlib import Path


def driver(source):
    if source is None or not str(source).strip():
        try:
            return importlib.import_module("fd9_independent.conversion_profile")
        except ModuleNotFoundError as error:
            if error.name not in (
                "fd9_independent",
                "fd9_independent.conversion_profile",
            ):
                raise
            bundled = Path(__file__).resolve().parents[2] / "vendor/fd9-independent"
            if not (bundled / "src/fd9_independent/conversion_profile.py").is_file():
                raise ValueError(
                    "Independent FD9 package is not installed or bundled"
                ) from error
            source = bundled
    src = Path(source).expanduser().resolve() / "src"
    if not (src / "fd9_independent/conversion_profile.py").is_file():
        raise ValueError("Select the independent FD9 package source directory")
    sys.path.insert(0, str(src))
    module = importlib.import_module("fd9_independent.conversion_profile")
    if not Path(module.__file__).resolve().is_relative_to(src):
        raise RuntimeError(
            "Another independent driver is loaded; restart before switching source"
        )
    return module


def chart_grid(layout):
    rows = layout["rows"]
    marks = layout["fiducials_mm"]
    if (
        not 1 <= len(rows) <= 128
        or not rows
        or not 1 <= len(rows[0]) <= 64
        or any(len(row) != len(rows[0]) for row in rows)
        or len(marks) != 4
    ):
        raise ValueError(
            "Require a regular FD9 grid within 64 columns and 128 rows, with four marks"
        )
    x = [p["centre_mm"][0] for p in rows[0]]
    y = [row[0]["centre_mm"][1] for row in rows]
    if any(
        [p["centre_mm"][0] for p in row] != x
        or any(p["centre_mm"][1] != yy for p in row)
        for row, yy in zip(rows, y)
    ):
        raise ValueError("Require a regular printed grid")
    tl, tr, bl, br = marks
    if tl[1] != tr[1] or bl[1] != br[1] or tl[0] != bl[0] or tr[0] != br[0]:
        raise ValueError("Require rectangular four-mark definition")
    return {
        "x_mm": x,
        "y_mm": y,
        "mark_origin_mm": tl,
        "mark_span_mm": [tr[0] - tl[0], bl[1] - tl[1]],
        "mirrored_image": True,
        "image_width_px": 3638,
    }


class CaptureFailed(RuntimeError):
    def __init__(self, session, message):
        super().__init__(message)
        self.session = Path(session)


def capture_layout(
    source,
    layout_path,
    output,
    host,
    *,
    allow_experimental=False,
    wait_seconds=3600,
    progress=print,
    cancelled=None,
    expected_calibration_sha256=None,
    row_indices=None,
    on_readings=lambda count: None,
    on_scan=lambda session: None,
    on_sample=None,
    native_factory=False,
    expected_factory_sha256=None,
    factory_row_sequencing=True,
    expected_model_sha256=None,
):
    if allow_experimental is not True:
        raise ValueError("Explicit experimental capture opt-in required")
    driver(source)
    from fd9_independent import Instrument
    from fd9_independent.motion import RawAcquisition
    from fd9_independent.factory_motion import FactoryRowAcquisition
    from fd9_independent.native_motion import NativeAcquisition
    from fd9_independent.geometry import find_marks, grid_rows
    from fd9_independent.operator_controls import fresh_output

    if not 60 <= wait_seconds <= 86400:
        raise ValueError("Insertion wait must be 60–86400 seconds")
    layout_bytes = Path(layout_path).read_bytes()
    layout = json.loads(layout_bytes)
    grid = chart_grid(layout)
    grid_rows([(100, 100), (1500, 100), (100, 2900), (1500, 2900)], **grid)
    selected = (
        list(range(len(layout["rows"]))) if row_indices is None else list(row_indices)
    )
    if (
        not selected
        or selected != list(range(selected[0], len(layout["rows"])))
        or any(type(i) is not int or i < 0 for i in selected)
    ):
        raise ValueError("Require remaining-row suffix")
    root = fresh_output(output)
    progress("Independent capture output: " + str(root.resolve()))
    (root / "chart-definition.json").write_bytes(layout_bytes)
    instrument = Instrument(host, timeout=10, cancelled=cancelled)
    fast_factory = native_factory and factory_row_sequencing
    acq = (
        FactoryRowAcquisition(
            instrument, enable_experimental_motion=True, enable_experimental_model=True
        )
        if fast_factory
        else (
            NativeAcquisition(
                instrument,
                enable_experimental_motion=True,
                enable_experimental_native=True,
            )
            if native_factory
            else RawAcquisition(instrument, enable_experimental_motion=True)
        )
    )
    report = {
        "success": False,
        "calibrated_reflectance": bool(native_factory),
        "conversion_source": (
            "instrument_model"
            if fast_factory
            else "instrument_firmware" if native_factory else "local_profile"
        ),
        "stages": [],
        "measurement_row_indices": selected,
    }

    def save():
        (root / "progress.json").write_text(
            json.dumps(
                {
                    **report,
                    "phase": acq.phase.value,
                    "raw_samples": [
                        {"header": s.header, "blocks": s.blocks}
                        for s in acq.raw_samples
                    ],
                    **(
                        {
                            "native_samples": [s.to_dict() for s in acq.native_samples],
                            "completed_native_rows": acq.completed_native_rows,
                        }
                        if native_factory
                        else {}
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    try:
        with instrument:
            if native_factory:
                # Check this device before displaying the insertion screen. No
                # reference reading, host profile or numerical table is needed.
                if fast_factory:
                    model = acq.prepare_model()
                    model.save(root / "spectral-model")
                    factory_digest = model.factory_sections_sha256
                    report["model_sha256"] = model.model_sha256
                    if (
                        expected_model_sha256 is not None
                        and model.model_sha256 != expected_model_sha256
                    ):
                        raise ValueError("Resume spectral model differs from this FD-9")
                else:
                    factory_digest = (
                        instrument.factory_characterization().verified_sections_sha256
                    )
                report["factory_sections_sha256"] = factory_digest
                if (
                    expected_factory_sha256 is not None
                    and factory_digest != expected_factory_sha256
                ):
                    raise ValueError(
                        "Resume factory characterization differs from this FD-9"
                    )
            progress(
                "Remove any previously ejected sheet completely from the FD-9. "
                "Keep the next chart outside until the insertion screen is ready."
            )
            acq.begin_loading()
            report["stages"].append("original insertion screen acknowledged")
            save()
            if (
                expected_calibration_sha256 is not None
                and hashlib.sha256(acq.calibration).hexdigest()
                != expected_calibration_sha256
            ):
                raise ValueError(
                    "Instrument calibration data does not match the external profile"
                )
            progress(
                "FD9 insertion screen ready. Insert chart arrow first, printed face up."
            )
            acq.wait_ready(wait_seconds)
            report["stages"].append("sheet readiness verified")
            save()
            progress("Sheet detected. Starting pre-scan.")
            pixels = acq.prescan()
            report["image_height"] = len(acq.image)
            (root / "scan.pgm").write_bytes(
                f"P5\n3638 {len(acq.image)}\n255\n".encode() + pixels
            )
            marks = find_marks(pixels, 3638, len(acq.image))
            rows = grid_rows(marks, **grid)
            (root / "geometry.json").write_text(
                json.dumps({"marks": marks, "rows": rows, "grid": grid}, indent=2)
                + "\n",
                encoding="utf-8",
            )
            report["stages"].append("independent pre-scan complete")
            save()
            on_scan(root)
            progress(
                f"Four marks verified. Measuring {len(layout['rows'][0])*len(selected)} "
                + (
                    "factory-calibrated M0/M1/M2 points"
                    if native_factory
                    else "raw points"
                )
                + " on the retained sheet."
            )

            def row_done(count, total):
                # Native progress is per point. Checkpoint the growing JSON at
                # row boundaries to avoid rewriting large charts thousands of
                # times. The finally block also preserves an interrupted row.
                if not native_factory or count % len(layout["rows"][0]) == 0:
                    save()
                on_readings(count)
                if native_factory and on_sample is not None:
                    on_sample(count, acq.native_samples[-1], root)
                progress(f"FD9 measurement: {count}/{total} patches")

            if fast_factory:
                acq.measure_rows([rows[i] for i in selected], on_point=row_done)
            elif native_factory:
                acq.measure_native([rows[i] for i in selected], on_point=row_done)
            else:
                acq.measure([rows[i] for i in selected], on_row=row_done)
            report["stages"].append("raw measurement and ejection complete")
            report["success"] = True
            progress(
                "Measurement complete. Remove the ejected sheet fully past the "
                "paper sensor before starting another FD-9 measurement."
            )
    except (Exception, KeyboardInterrupt) as e:
        report["error"] = str(e)
        report["cancelled"] = bool(cancelled is not None and cancelled())
    finally:
        instrument.close()
        save()
        instrument.save_transcript(root / "wire")
        if acq.calibration:
            (root / "instrument-calibration.bin").write_bytes(acq.calibration)
    if not report["success"]:
        raise CaptureFailed(
            root,
            "Capture failed; evidence preserved: " + report.get("error", "unknown"),
        )
    return root


def export_saved(
    source,
    session,
    layout_path,
    profile_path,
    output,
    condition,
    illuminant_path,
    observer_path,
    *,
    allow_research=False,
    allow_partial=False,
):
    if allow_research is not True:
        raise ValueError("Explicit research export opt-in required")
    profile = driver(source).ConversionProfile.load(profile_path)
    from .evidence import verified_rows
    from fd9_independent.spectral import Curve, colorimetry

    evidence = verified_rows(source, session, layout_path, allow_partial=allow_partial)
    layout = evidence["layout"]
    patches = evidence["patches"]
    raw = evidence["raw"]
    manifest = evidence["manifest"]
    tokens = layout["channel_tokens"]
    rep = layout["color_rep"]
    if (
        not rep.isalnum()
        or any(not t.isalnum() for t in tokens)
        or len(set(tokens)) != len(tokens)
    ):
        raise ValueError("Malformed ink representation")
    ids = [p["id"] for p in patches]
    if len(set(ids)) != len(ids) or any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError("Invalid or duplicated chart IDs")

    def table(path):
        return [
            [float(v) for v in row]
            for row in csv.reader(Path(path).read_text(encoding="utf-8").splitlines())
        ]

    it = table(illuminant_path)
    ot = table(observer_path)
    ill = Curve([r[0] for r in it], [r[1] for r in it])
    obs = tuple(Curve([r[0] for r in ot], [r[i] for r in ot]) for i in (1, 2, 3))
    calibration = evidence["calibration"]
    rows = []
    for patch, s in zip(patches, raw):
        device = patch["device_values"]
        if len(device) != len(tokens) or any(
            not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 100
            for v in device
        ):
            raise ValueError("Malformed device values")
        spectrum = profile.convert(
            s.blocks,
            condition,
            host=manifest["host"],
            calibration=calibration,
            allow_research=True,
        ).spectrum
        color = colorimetry(spectrum, ill, obs)
        rows.append(
            str(patch["id"])
            + " "
            + " ".join(
                f"{v:.10f}"
                for v in device
                + list(color.xyz)
                + list(color.lab)
                + [100 * v for v in spectrum.values]
            )
        )
    fields = (
        ["SAMPLE_ID"]
        + layout.get("device_fields", [rep + "_" + t for t in tokens])
        + ["XYZ_X", "XYZ_Y", "XYZ_Z", "LAB_L", "LAB_A", "LAB_B"]
        + ["SPEC_" + str(w) for w in range(380, 731, 10)]
    )
    header = [
        "CTI3",
        'DESCRIPTOR "Independent FD9 uncalibrated research compatibility measurement"',
        'ORIGINATOR "ChromIQ independent FD9"',
        'DEVICE_CLASS "OUTPUT"',
        f'COLOR_REP "{rep}_XYZ"',
        'TARGET_INSTRUMENT "Konica Minolta FD-9"',
        f'MEASUREMENT_CONDITION "{condition}"',
        'CALIBRATED_REFLECTANCE "NO"',
        'FD9_RESEARCH_ONLY "YES"',
        f'FD9_LAYOUT_SHA256 "{hashlib.sha256(Path(layout_path).read_bytes()).hexdigest()}"',
        f'FD9_ACQUISITION_COMPLETE "{"YES" if evidence["acquisition_complete"] else "NO"}"',
        f'FD9_PROFILE_SHA256 "{profile.profile_sha256}"',
        f'ILLUMINANT_SOURCE_SHA256 "{hashlib.sha256(Path(illuminant_path).read_bytes()).hexdigest()}"',
        f'OBSERVER_SOURCE_SHA256 "{hashlib.sha256(Path(observer_path).read_bytes()).hexdigest()}"',
        'SPECTRAL_BANDS "36"',
        'SPECTRAL_START_NM "380"',
        'SPECTRAL_END_NM "730"',
        'SPECTRAL_NORM "100"',
        'COLORIMETRY_COVERAGE_NM "380 730"',
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
    with Path(output).open("x", encoding="utf-8") as f:
        f.write("\n".join(header))
    return {
        "output": str(Path(output).resolve()),
        "patches": len(rows),
        "channels": len(tokens),
        "condition": condition,
        "calibrated": False,
        "row_indices": evidence["row_indices"],
        "acquisition_complete": evidence["acquisition_complete"],
        "profile_sha256": profile.profile_sha256,
        "SDK_runtime_dependency": False,
    }
