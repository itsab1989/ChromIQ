"""FD9 measurement-tab workflow: checked chart association and atomic filing."""

from __future__ import annotations
from workflow.layout_engine.labels import alpha_label
from dataclasses import dataclass
import hashlib, json, math, os, re, shlex, shutil, tempfile
from pathlib import Path
from .independent import driver, chart_grid, capture_layout, export_saved, CaptureFailed
from .support import TARGET_INSTRUMENT, is_fd9_instrument_name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def first_table(path):
    # Through core.text_io, like every other chart read: a chart edited on a
    # Windows machine may be cp1252 (#178, review H2).
    from core.text_io import read_text

    text = read_text(path)
    fm = re.search(
        r"^BEGIN_DATA_FORMAT\s*$(.*?)^END_DATA_FORMAT\s*$", text, re.M | re.S
    )
    dm = re.search(r"^BEGIN_DATA\s*$(.*?)^END_DATA\s*$", text, re.M | re.S)
    if not fm or not dm:
        raise ValueError("Chart needs a complete CGATS table")
    fields = shlex.split(fm.group(1))
    rows = [
        shlex.split(line)
        for line in dm.group(1).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not fields or not rows or any(len(r) != len(fields) for r in rows):
        raise ValueError("Malformed chart table")
    return text, fields, [dict(zip(fields, row)) for row in rows]


_FD9_NAME = re.compile(
    # Any letter case, quoted with " or ' or not at all (review r1 minor),
    # the same names `is_fd9_instrument_name` accepts.
    rb'^TARGET_INSTRUMENT[ \t]+(["\']?)[ \t]*(?:FD-9|Konica Minolta FD-9)[ \t]*\1[ \t]*\r?$',
    re.M | re.I
)
_IS_FD9_CACHE: "dict[str, tuple[tuple[int, int], bool]]" = {}


def is_fd9_chart(path):
    """True when the chart file at *path* names the FD-9 in TARGET_INSTRUMENT.

    NEVER RAISES, AND READS NO TEXT DECODING (review H2): a chart made on a
    German Windows is cp1252, and a strict UTF-8 read of it raised
    UnicodeDecodeError and broke the Measure tab for every instrument. The
    keyword is ASCII, so only the header BYTES are searched. The answer is
    cached per path, file size and modification time, because the Measure tab
    asks on every Start-label refresh. Callers in the app ask only while FD-9
    support is on (`workflow.fd9.support.fd9_enabled`)."""
    try:
        p = Path(path)
        st = p.stat()
        key = str(p)
        stamp = (st.st_mtime_ns, st.st_size)
        hit = _IS_FD9_CACHE.get(key)
        if hit is not None and hit[0] == stamp:
            return hit[1]
        with open(p, "rb") as f:
            head = f.read(65536)
        head = head.split(b"BEGIN_DATA_FORMAT", 1)[0]
        answer = bool(_FD9_NAME.search(head))
        if len(_IS_FD9_CACHE) > 256:
            _IS_FD9_CACHE.clear()
        _IS_FD9_CACHE[key] = (stamp, answer)
        return answer
    except Exception:  # noqa: BLE001 - a chart we cannot read is not FD-9's
        return False


def checked_chart(chart):
    chart = Path(chart)
    layout_path = chart.with_suffix(".fd9.json")
    if not is_fd9_chart(chart):
        raise ValueError("This chart does not name the FD-9")
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    from .chart import chart_pages
    chart_pages(layout)
    text, fields, rows = first_table(chart)
    rep = layout["color_rep"]
    tokens = layout["channel_tokens"]
    if not re.search(r'^COLOR_REP\s+"' + re.escape(rep) + r'"\s*$', text, re.M):
        raise ValueError("Chart ink representation disagrees with FD9 layout")
    device_fields = layout.get("device_fields", [rep + "_" + t for t in tokens])
    expected_fields = [rep + "_" + t for t in tokens]
    if rep in ("W", "K") and tokens == [rep]:
        expected_fields = ["GRAY_" + rep]
    if device_fields != expected_fields:
        raise ValueError("Unsupported FD9 device field names")
    needed = ["SAMPLE_ID", "SAMPLE_LOC"] + device_fields
    if any(k not in fields for k in needed):
        raise ValueError("Missing sample IDs, locations or device channels")
    patches = [p for row in layout["rows"] for p in row]
    by_id = {int(r["SAMPLE_ID"]): r for r in rows}
    if (
        len(by_id) != len(rows)
        or len(rows) != len(patches)
        or len({r["SAMPLE_LOC"] for r in rows}) != len(rows)
    ):
        raise ValueError("Chart sample IDs/locations must be complete and unique")
    if any(not re.fullmatch(r'[^\s"\\]+', r["SAMPLE_LOC"]) for r in rows):
        raise ValueError("Unsupported chart location label")
    if set(by_id) != {p["id"] for p in patches}:
        raise ValueError("Chart IDs disagree with physical layout")
    for p in patches:
        values = [float(by_id[p["id"]][f]) for f in device_fields]
        if len(values) != len(p["device_values"]) or any(
            not math.isfinite(a) or abs(a - b) > 1e-7
            for a, b in zip(values, p["device_values"])
        ):
            raise ValueError("Chart ink values disagree with physical layout")
    return layout_path, layout, {i: r["SAMPLE_LOC"] for i, r in by_id.items()}


def prepare_chart(layout_path, directory, *, stem="fd9-chart"):
    """Wrap an existing printed layout in normal TI1/TI2 chart files.

    No printing or colour conversion. The physical source chart is unchanged.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]+", stem):
        raise ValueError("Use a simple chart name")
    layout = json.loads(Path(layout_path).read_text(encoding="utf-8"))
    chart_grid(layout)
    rep = layout["color_rep"]
    tokens = layout["channel_tokens"]
    if not rep.isalnum() or any(not t.isalnum() for t in tokens):
        raise ValueError("Malformed ink names")
    rows = []
    for r, row in enumerate(layout["rows"]):
        for c, p in enumerate(row):
            rows.append((p["id"], f"{alpha_label(c+1)}{r+1}", p["device_values"]))
    if len({i for i, _, _ in rows}) != len(rows):
        raise ValueError("Duplicated patch IDs")
    fields = (
        ["SAMPLE_ID", "SAMPLE_LOC"]
        + [rep + "_" + t for t in tokens]
        + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    )
    text = "\n".join(
        [
            "CTI2",
            'DESCRIPTOR "FD9 physical-layout chart"',
            'ORIGINATOR "ChromIQ FD9"',
            f'TARGET_INSTRUMENT "{TARGET_INSTRUMENT}"',
            f'COLOR_REP "{rep}"',
            f'STEPS_IN_PASS "{len(layout["rows"])}"',
            f'PASSES_IN_STRIPS2 "{len(layout["rows"][0])}"',
            'STRIP_INDEX_PATTERN "A-Z, A-Z"',
            'PATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"',
            'INDEX_ORDER "STRIP_THEN_PATCH"',
            'CHART_ID "1"',
            f"NUMBER_OF_FIELDS {len(fields)}",
            "BEGIN_DATA_FORMAT",
            " ".join(fields),
            "END_DATA_FORMAT",
            f"NUMBER_OF_SETS {len(rows)}",
            "BEGIN_DATA",
            *[
                str(i)
                + " "
                + loc
                + " "
                + " ".join(f"{v:.10f}" for v in vals)
                + " 0 0 0"
                for i, loc, vals in sorted(rows)
            ],
            "END_DATA",
            "",
        ]
    )
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    chart = root / f"{stem}.ti2"
    chart.write_text(text, encoding="utf-8")
    chart.with_suffix(".ti1").write_text(
        text.replace("CTI2", "CTI1", 1), encoding="utf-8"
    )
    chart.with_suffix(".fd9.json").write_bytes(Path(layout_path).read_bytes())
    checked_chart(chart)
    return chart


@dataclass(frozen=True)
class FD9Settings:
    driver_source: Path | None
    profile: Path | None
    illuminant: Path | None
    observer: Path | None
    host: str
    condition: str
    allow_research: bool
    resume: bool = False
    resume_source: Path | None = None
    # Legacy local-profile sessions remain readable for ongoing research. The
    # normal GUI always sets this to instrument_firmware, without profile files.
    conversion_source: str = "local_profile"

    def validate(self):
        if self.allow_research is not True:
            raise ValueError("Enable the experimental independent FD9 driver first")
        if self.condition not in ("M0", "M1", "M2"):
            raise ValueError("Choose M0, M1 or M2")
        if self.conversion_source == "instrument_firmware":
            if not self.host or any(c.isspace() or c in '"\\' for c in self.host):
                raise ValueError("Enter the FD-9 Ethernet address")
            driver(self.driver_source)
            from .native_export import colour_data

            colour_data()
            return None
        if self.conversion_source != "local_profile":
            raise ValueError("Unknown FD9 conversion source")
        profile = driver(self.driver_source).ConversionProfile.load(self.profile)
        if self.condition not in profile.conditions:
            raise ValueError(
                "Selected condition is not calibrated by this external profile"
            )
        if profile.host != self.host:
            raise ValueError("FD9 address does not match the selected profile")
        # Verify spectral data before starting a device session.
        import csv
        from fd9_independent.spectral import Curve, colorimetry

        it = [
            [float(v) for v in row]
            for row in csv.reader(
                self.illuminant.read_text(encoding="utf-8").splitlines()
            )
        ]
        ot = [
            [float(v) for v in row]
            for row in csv.reader(
                self.observer.read_text(encoding="utf-8").splitlines()
            )
        ]
        colorimetry(
            Curve((380, 730), (1, 1)),
            Curve([r[0] for r in it], [r[1] for r in it]),
            tuple(Curve([r[0] for r in ot], [r[i] for r in ot]) for i in (1, 2, 3)),
        )
        return profile


def stamp_locations(source, target, locations, session, chart=None):
    text, fields, rows = first_table(source)
    if "SAMPLE_LOC" in fields:
        raise ValueError("Unexpected existing location column")
    if len(rows) != len(locations) or {int(r["SAMPLE_ID"]) for r in rows} != set(
        locations
    ):
        raise ValueError("Converted measurement IDs changed")
    fields.insert(1, "SAMPLE_LOC")
    body = []
    for r in rows:
        r["SAMPLE_LOC"] = locations[int(r["SAMPLE_ID"])]
        body.append(" ".join(r[f] for f in fields))
    head = text[: text.index("NUMBER_OF_FIELDS")]
    # Path is not embedded: evidence is adjacent to the selected run and in metadata.
    head += f'CHROMIQ_FD9_SESSION "{Path(session).name}"\n'
    from workflow.printer_calibration import embedded_cal_text

    calibration = embedded_cal_text(chart) if chart is not None else ""
    if chart is not None:
        chart_header = (
            Path(chart).read_text(encoding="utf-8").split("NUMBER_OF_FIELDS", 1)[0]
        )
        ink_limit = _keywords(chart_header).get("TOTAL_INK_LIMIT")
        if ink_limit is not None:
            value = float(ink_limit)
            if not math.isfinite(value) or not 0 <= value <= 1600:
                raise ValueError("Invalid chart ink limit")
            head += f'TOTAL_INK_LIMIT "{value:g}"\n'
    with Path(target).open("x", encoding="utf-8") as f:
        f.write(
            head
            + "\n".join(
                [
                    f"NUMBER_OF_FIELDS {len(fields)}",
                    "BEGIN_DATA_FORMAT",
                    " ".join(fields),
                    "END_DATA_FORMAT",
                    f"NUMBER_OF_SETS {len(rows)}",
                    "BEGIN_DATA",
                    *body,
                    "END_DATA",
                    "",
                ]
            )
            + calibration
        )


_UNSPECIFIED = object()


def publish_measurement(
    source,
    destination,
    chart,
    *,
    allow_partial=False,
    expected_base_sha256=_UNSPECIFIED,
    archive=None,
):
    """File checked data atomically; never overwrite another session's change."""
    from workflow.measurement_session import MeasurementSession
    from workflow.measurement_state import classify, Ti3State

    source, destination, chart = map(Path, (source, destination, chart))
    permitted = (
        (Ti3State.COMPLETE, Ti3State.PARTIAL) if allow_partial else (Ti3State.COMPLETE,)
    )
    if classify(source, chart).state not in permitted:
        raise ValueError("Only checked nonempty FD9 measurement data can be filed")
    current = sha(destination) if destination.exists() else None
    if expected_base_sha256 is not _UNSPECIFIED and current != expected_base_sha256:
        raise ValueError(
            "Previous measurement changed while measuring; replacement refused"
        )
    if destination.exists():
        protected = (
            archive is not None and Path(archive).is_file() and sha(archive) == current
        )
        if not protected and MeasurementSession(destination, chart).begin() is None:
            raise OSError(
                "Could not preserve the previous measurement; replacement refused"
            )
    fd, tmp = tempfile.mkstemp(prefix=".fd9-", suffix=".ti3", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(source.read_bytes())
            f.flush()
            os.fsync(f.fileno())
        if (sha(destination) if destination.exists() else None) != current:
            raise ValueError(
                "Previous measurement changed before commit; replacement refused"
            )
        os.replace(tmp, destination)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return destination


def _keywords(text):
    text = text.split("NUMBER_OF_FIELDS", 1)[0]
    return dict(re.findall(r'^([A-Z][A-Z0-9_]*)\s+"([^"\n]*)"\s*$', text, re.M))


def _write_rows(source, target, rows, extra):
    text, fields, _ = first_table(source)
    header = text[: text.index("NUMBER_OF_FIELDS")]
    for key, value in extra.items():
        header = re.sub(r"^" + key + r"\s+.*\n", "", header, flags=re.M)
        header += f'{key} "{value}"\n'
    from workflow.printer_calibration import embedded_cal_text

    calibration = embedded_cal_text(source)
    body = [" ".join(row[f] for f in fields) for row in rows]
    Path(target).write_text(
        header
        + "\n".join(
            [
                f"NUMBER_OF_FIELDS {len(fields)}",
                "BEGIN_DATA_FORMAT",
                " ".join(fields),
                "END_DATA_FORMAT",
                f"NUMBER_OF_SETS {len(rows)}",
                "BEGIN_DATA",
                *body,
                "END_DATA",
                "",
            ]
        )
        + calibration,
        encoding="utf-8",
    )


def resume_plan(chart, settings):
    """Only a checked whole-row prefix from this same conversion can resume."""
    layout_path, layout, locations = checked_chart(chart)
    if not settings.resume:
        return None, [], list(range(len(layout["rows"])))
    base = settings.resume_source or Path(chart).with_suffix(".ti3")
    from workflow.measurement_state import classify, Ti3State

    if classify(base, chart).state is not Ti3State.PARTIAL:
        raise ValueError("Only a consistent partial measurement can resume")
    from workflow.printer_calibration import embedded_cal_text

    if embedded_cal_text(base) != embedded_cal_text(chart):
        raise ValueError(
            "Saved measurement printer calibration differs from this chart"
        )
    text, fields, records = first_table(base)
    metadata = _keywords(text)
    required = {
        "MEASUREMENT_CONDITION": settings.condition,
        "FD9_LAYOUT_SHA256": sha(layout_path),
        "SPECTRAL_NORM": "100",
        "COLOR_REP": layout["color_rep"] + "_XYZ",
        "SPECTRAL_BANDS": "36",
        "SPECTRAL_START_NM": "380",
        "SPECTRAL_END_NM": "730",
    }
    if settings.conversion_source == "instrument_firmware":
        from .native_export import colour_data

        required.update(
            {
                "FD9_CONVERSION_SOURCE": metadata.get("FD9_CONVERSION_SOURCE"),
                "CALIBRATED_REFLECTANCE": "YES",
                # Not FD9_HOST: the factory and model fingerprints below
                # identify the FD-9, and an address handed out again by a
                # router must not make a partial run unresumable (review M11).
                "FD9_COLOUR_DATA_SHA256": colour_data()[2],
            }
        )
        if metadata.get("FD9_CONVERSION_SOURCE") not in (
            "INSTRUMENT_FIRMWARE",
            "INSTRUMENT_MODEL",
        ):
            raise ValueError("Resume requires a factory-calibrated conversion source")
        if metadata.get(
            "FD9_CONVERSION_SOURCE"
        ) == "INSTRUMENT_MODEL" and not re.fullmatch(
            r"[0-9a-f]{64}", metadata.get("FD9_MODEL_SHA256", "")
        ):
            raise ValueError("Resume needs the saved spectral model fingerprint")
        if not re.fullmatch(r"[0-9a-f]{64}", metadata.get("FD9_FACTORY_SHA256", "")):
            raise ValueError(
                "Resume needs the saved factory characterization fingerprint"
            )
    else:
        required.update(
            {
                "FD9_PROFILE_SHA256": sha(settings.profile),
                "FD9_RESEARCH_ONLY": "YES",
                "CALIBRATED_REFLECTANCE": "NO",
                "ILLUMINANT_SOURCE_SHA256": sha(settings.illuminant),
                "OBSERVER_SOURCE_SHA256": sha(settings.observer),
            }
        )
    # Either spelling: "FD-9" (charts made before the Beta switch) or the full
    # "Konica Minolta FD-9" ChromIQ writes now.
    if not is_fd9_instrument_name(metadata.get("TARGET_INSTRUMENT")) or any(
        metadata.get(k) != v for k, v in required.items()
    ):
        raise ValueError(
            "Resume requires the same chart, condition, conversion source and colour data"
        )
    patches = [p for row in layout["rows"] for p in row]
    count = len(records)
    row_ends = []
    for row in layout["rows"]:
        row_ends.append((row_ends[-1] if row_ends else 0) + len(row))
    if not count or count not in row_ends or count >= len(patches):
        raise ValueError("Resume requires an incomplete measurement of complete rows")
    if [int(r["SAMPLE_ID"]) for r in records] != [p["id"] for p in patches[:count]]:
        raise ValueError("Resume measurement must be a complete leading-row prefix")
    rep = layout["color_rep"]
    for record, patch in zip(records, patches):
        if record.get("SAMPLE_LOC") != locations[patch["id"]]:
            raise ValueError("Resume sample locations disagree with the chart")
        for token, value in zip(layout["channel_tokens"], patch["device_values"]):
            if (
                not math.isfinite(float(record[rep + "_" + token]))
                or abs(float(record[rep + "_" + token]) - value) > 1e-7
            ):
                raise ValueError("Resume ink values disagree with the chart")
        required_values = ["XYZ_X", "XYZ_Y", "XYZ_Z"] + [
            "SPEC_" + str(w) for w in range(380, 731, 10)
        ]
        if any(not math.isfinite(float(record[f])) for f in required_values):
            raise ValueError(
                "Resume measurement has missing or nonfinite spectral data"
            )
    return Path(base), records, list(range(row_ends.index(count) + 1, len(layout["rows"])))


def measure_chart(
    chart,
    settings,
    session,
    *,
    progress=print,
    cancelled=lambda: False,
    on_readings=lambda count: None,
    on_scan=lambda event: None,
    on_patch=None,
    capture=capture_layout,
    on_page=lambda page, pages: None,
    _expected_identity=None,
    _wait_for_sheet_clear=False,
):
    chart = Path(chart)
    layout_path, layout, locations = checked_chart(chart)
    if layout.get("schema") == 2:
        from .pages import measure_pages
        settings.validate()
        return measure_pages(chart, settings, session, progress=progress,
                             cancelled=cancelled, on_readings=on_readings,
                             on_scan=on_scan, on_patch=on_patch, on_page=on_page,
                             capture=capture)
    profile = settings.validate()
    base_path, base_rows, remaining = resume_plan(chart, settings)
    native = settings.conversion_source == "instrument_firmware"
    watched = [chart, layout_path]
    if not native:
        watched.extend([settings.profile, settings.illuminant, settings.observer])
    from .native_export import colour_data, export_native

    cie_digest = colour_data()[2] if native else None
    if base_path is not None:
        watched.append(base_path)
    hashes = {p: sha(p) for p in watched}
    destination = chart.with_suffix(".ti3")
    base_sha = sha(destination) if destination.exists() else None
    acquisition_error = None
    acquisition_cause = None

    def scan_ready(root):
        # A presentation failure must never turn a valid acquisition into a failure.
        try:
            from .preview import build_scan_preview

            event = build_scan_preview(root, layout_path, settings.driver_source)
            event["measurement_locations"] = [locations[p["id"]] for p in selected_patches]
            on_scan(event)
        except Exception as error:
            progress("[FD9 preview] " + str(error))

    # Display events use the same selected-condition XYZ as TI3 export, but
    # cannot change acquisition or measurement values. Never poll the device
    # or a growing JSON file from the GUI thread.
    selected_patches = [p for i in remaining for p in layout["rows"][i]]
    design = {int(r["SAMPLE_ID"]): r for r in first_table(chart)[2]} if on_patch else {}

    def sample_ready(count, sample, root):
        if on_patch is None:
            return
        try:
            from .native_export import native_colour
            from workflow.measurement_report import engine_patch_de

            patch = selected_patches[count - 1]
            reference = design[patch["id"]]
            expected = [float(reference[k]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
            xyz, _ = native_colour(sample.for_condition(settings.condition).values)
            on_patch(
                {
                    "session": str(Path(root).resolve()),
                    "layout_sha256": hashes[layout_path],
                    "condition": settings.condition,
                    "patches": [
                        {
                            "loc": locations[patch["id"]],
                            "exyz": expected,
                            "xyz": xyz,
                            "de": round(float(engine_patch_de(expected, xyz)), 2),
                        }
                    ],
                }
            )
        except Exception as error:
            progress("[FD9 preview] " + str(error))

    try:
        capture_options = {}
        if native:
            capture_options["native_factory"] = True
            if _expected_identity:
                capture_options["expected_factory_sha256"] = _expected_identity["FD9_FACTORY_SHA256"]
                capture_options["factory_row_sequencing"] = _expected_identity["FD9_CONVERSION_SOURCE"] == "INSTRUMENT_MODEL"
                if capture_options["factory_row_sequencing"]:
                    capture_options["expected_model_sha256"] = _expected_identity["FD9_MODEL_SHA256"]
            if base_path:
                base_metadata = _keywords(base_path.read_text(encoding="utf-8"))
                capture_options["expected_factory_sha256"] = base_metadata[
                    "FD9_FACTORY_SHA256"
                ]
                # Retain the algorithm of an older partial session; fresh jobs
                # always use automatic rows with the live instrument model.
                capture_options["factory_row_sequencing"] = (
                    base_metadata["FD9_CONVERSION_SOURCE"] == "INSTRUMENT_MODEL"
                )
                if capture_options["factory_row_sequencing"]:
                    capture_options["expected_model_sha256"] = base_metadata[
                        "FD9_MODEL_SHA256"
                    ]
        from .independent import (ordered_measurement_rows, ALTERNATING_ROW_ORDER,
                                  FORWARD_ROW_ORDER)
        capture_options["row_order"] = (
            ALTERNATING_ROW_ORDER if native and capture_options.get("factory_row_sequencing", True)
            else FORWARD_ROW_ORDER)
        selected_patches = [p for row in ordered_measurement_rows(
            layout["rows"], remaining, capture_options["row_order"]) for p in row]
        session = capture(
            settings.driver_source,
            layout_path,
            session,
            settings.host,
            allow_experimental=True,
            progress=progress,
            cancelled=cancelled,
            expected_calibration_sha256=None if native else profile.calibration_sha256,
            row_indices=remaining,
            on_readings=on_readings,
            on_scan=scan_ready,
            on_sample=sample_ready if on_patch else None,
            wait_for_sheet_clear=_wait_for_sheet_clear,
            **capture_options,
        )
    except CaptureFailed as error:
        acquisition_error = str(error)
        acquisition_cause = getattr(error, "cause", None)
        session = error.session
    session = Path(session)
    if acquisition_error and not (session / "geometry.json").is_file():
        # Stopping before the pre-scan has no geometry or rows to export.
        # Keep the actual transport/cancel error instead of a missing-file error.
        raise CaptureFailed(session, acquisition_error,
                            cause=acquisition_cause)
    raw_export = (
        session / f"{settings.condition}-{'factory' if native else 'research'}.ti3"
    )
    if native:
        converted = export_native(
            settings.driver_source,
            session,
            layout_path,
            raw_export,
            settings.condition,
            allow_partial=acquisition_error is not None,
        )
        if (
            converted["colour_data_sha256"] != cie_digest
            or colour_data()[2] != cie_digest
        ):
            raise ValueError("Colour data changed during native measurement")
        if (
            base_path
            and converted["factory_sections_sha256"]
            != capture_options["expected_factory_sha256"]
        ):
            raise ValueError("Resume factory characterization changed; merging refused")
        if (
            base_path
            and capture_options.get("factory_row_sequencing")
            and (
                converted.get("model_sha256")
                != capture_options["expected_model_sha256"]
                or converted.get("conversion_source") != "instrument_model"
            )
        ):
            raise ValueError("Resume spectral model changed; merging refused")
        if (
            base_path
            and not capture_options.get("factory_row_sequencing")
            and converted.get("conversion_source") != "instrument_firmware"
        ):
            raise ValueError("Resume conversion source changed; merging refused")
    else:
        converted = export_saved(
            settings.driver_source,
            session,
            layout_path,
            settings.profile,
            raw_export,
            settings.condition,
            settings.illuminant,
            settings.observer,
            allow_research=True,
            allow_partial=acquisition_error is not None,
        )
    if any(sha(p) != digest for p, digest in hashes.items()):
        raise ValueError(
            "Chart, profile or measurement inputs changed; result kept in session only"
        )
    # A resume may only contribute the next rows, never overwrite prior readings.
    indices = converted["row_indices"]
    if indices != remaining[: len(indices)]:
        raise ValueError("Captured rows do not follow the resume prefix")
    subset = {p["id"]: locations[p["id"]] for i in indices for p in layout["rows"][i]}
    located = session / "located.ti3"
    stamp_locations(raw_export, located, subset, session, chart=chart)
    _, _, new_rows = first_table(located)
    rows = base_rows + new_rows
    sessions = []
    if base_path:
        old = _keywords(base_path.read_text(encoding="utf-8"))
        sessions = old.get(
            "FD9_SOURCE_SESSIONS", old.get("CHROMIQ_FD9_SESSION", "")
        ).split(",")
    sessions = [s for s in sessions if s] + [session.name]
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", s) for s in sessions):
        raise ValueError("Invalid source-session provenance")
    staged = session / "measurement.ti3"
    _write_rows(
        located,
        staged,
        rows,
        {
            "FD9_SOURCE_SESSIONS": ",".join(sessions),
            "FD9_LAYOUT_SHA256": hashes[layout_path],
            "FD9_PARENT_MEASUREMENT_SHA256": hashes[base_path] if base_path else "",
        },
    )
    result = {
        "chart": str(chart),
        "condition": settings.condition,
        "profile_sha256": None if native else hashes[settings.profile],
        "conversion_source": converted.get(
            "conversion_source", settings.conversion_source
        ),
        "model_sha256": converted.get("model_sha256"),
        "factory_sections_sha256": converted.get("factory_sections_sha256"),
        "colour_data_sha256": cie_digest,
        "chart_sha256": hashes[chart],
        "layout_sha256": hashes[layout_path],
        "session": str(session),
        "research_only": not native,
        "SDK_runtime_dependency": False,
        "patches": len(rows),
        "new_readings": len(new_rows),
        "complete": len(rows) == len(locations),
        "acquisition_error": acquisition_error,
        "base_sha256": base_sha,
        "staged_sha256": sha(staged),
        "cancelled": bool(cancelled()),
    }
    (session / "measurement-metadata.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    # The exception itself, for the window it belongs to (review r2 M2). Not
    # in measurement-metadata.json: only its words are, above.
    return result | {"staged": str(staged), "destination": str(destination),
                     "acquisition_exception": acquisition_cause}
