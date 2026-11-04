"""FD-9 generated pixels, physical identity, and native GUI routing."""

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
import json
import numpy as np
import pytest
import tifffile
from workflow.fd9.chart import capacity, build_chart, dimensions
from workflow.fd9.measurement import checked_chart, first_table


def ti1(tmp_path, rep="CMYK", tokens=("C", "M", "Y", "K"), count=37):
    fields = [rep + "_" + t for t in tokens]
    values = [
        [float((i * 17 + j * 23) % 101) for j in range(len(tokens))]
        for i in range(count)
    ]
    text = [
        "CTI1",
        f'COLOR_REP "{rep}"',
        f"NUMBER_OF_FIELDS {1+len(fields)}",
        "BEGIN_DATA_FORMAT",
        "SAMPLE_ID " + " ".join(fields),
        "END_DATA_FORMAT",
        f"NUMBER_OF_SETS {count}",
        "BEGIN_DATA",
    ]
    text += [str(i + 1) + " " + " ".join(map(str, row)) for i, row in enumerate(values)]
    text += ["END_DATA", ""]
    p = tmp_path / "source.ti1"
    p.write_text("\n".join(text), encoding="utf-8")
    return p, values


@pytest.mark.parametrize(
    "paper,expected",
    [
        ("137x170", 132),
        ("137x300", 300),
        ("A4", 500),
        ("Letter", 460),
        ("A3", 1102),
        ("330x660", 2145),
    ],
)
def test_feed_envelope_capacity(paper, expected):
    assert capacity(paper) == expected


@pytest.mark.parametrize(
    "paper", ["136x300", "331x300", "137x169", "137x661", "A2", "420x297"]
)
def test_bad_feed_envelope(paper):
    with pytest.raises(ValueError):
        dimensions(paper)


@pytest.mark.parametrize(
    "rep,tokens",
    [
        ("CMYK", ("C", "M", "Y", "K")),
        ("CMYKcmk1kRGB", ("C", "M", "Y", "K", "c", "m", "k", "1k", "R", "G", "B")),
    ],
)
@pytest.mark.parametrize("randomize", [False, True])
def test_printed_pixels_match_physical_measurement_ids(
    tmp_path, rep, tokens, randomize
):
    source, values = ti1(tmp_path, rep, tokens)
    result = build_chart(
        source, tmp_path / "print", paper="A4", dpi=100, randomize=randomize, seed=42
    )
    _, definition, locations = checked_chart(result.ti2_path)
    pixels = tifffile.imread(result.tiff_paths[0])
    assert pixels.shape[2] == len(tokens)
    assert len(locations) == 40
    assert sorted(p["id"] for row in definition["rows"] for p in row) == list(
        range(1, 41)
    )
    for row in definition["rows"]:
        for patch in row:
            x, y = (round(v * 100 / 25.4) for v in patch["centre_mm"])
            expected = (
                values[patch["id"] - 1]
                if patch["id"] <= len(values)
                else [0] * len(tokens)
            )
            assert patch["device_values"] == expected
            assert (
                np.max(
                    np.abs(
                        pixels[y, x].astype(float) - np.rint(np.array(expected) * 2.55)
                    )
                )
                <= 1
            )
    _, fields, rows = first_table(result.ti2_path)
    assert all(rep + "_" + t in fields for t in tokens)
    assert len(rows) == 40
    x, y = (round(v * 100 / 25.4) for v in definition["fiducials_mm"][0])
    assert pixels[y, x].tolist() == [255 if t == "K" else 0 for t in tokens]
    side = json.loads(
        result.ti2_path.with_suffix(".strips.json").read_text(encoding="utf-8")
    )
    assert len(side["patches"]) == 40 and len(side["strips"]) == 20
    assert {p["loc"] for p in side["patches"]} == set(locations.values())


def test_rgb_chart_is_additive_and_measurable(tmp_path):
    source, values = ti1(tmp_path, "RGB", ("R", "G", "B"), 12)
    result = build_chart(source, tmp_path / "rgb", dpi=100, randomize=False)
    _, doc, _ = checked_chart(result.ti2_path)
    pixels = tifffile.imread(result.tiff_paths[0])
    for patch in doc["rows"][0]:
        x, y = (round(v * 100 / 25.4) for v in patch["centre_mm"])
        assert (
            np.max(
                np.abs(
                    pixels[y, x].astype(float)
                    - np.rint(np.array(patch["device_values"]) * 2.55)
                )
            )
            <= 1
        )


def test_oversize_charts_span_sheets(tmp_path):
    source, _ = ti1(tmp_path, count=501)
    result = build_chart(source, tmp_path / "too-many", dpi=72)
    assert result.layout.pages == 2 and len(result.tiff_paths) == 2
    source, _ = ti1(tmp_path, count=12)
    with pytest.raises(FileNotFoundError):
        build_chart(source, tmp_path / "cal", cal_path=tmp_path / "missing.cal")
    assert not (tmp_path / "cal.tif").exists()


def test_normal_engine_dispatch_and_geometry_estimate(tmp_path):
    from workflow.layout_engine.chart import build_chart as normal
    from workflow.layout_engine.instruments import geom_from_build_kwargs
    from workflow.layout_engine.geometry import patches_per_sheet
    from workflow.chart_creator import ENGINE_ONLY_INSTRUMENTS

    source, _ = ti1(tmp_path, count=300)
    assert "FD9" in ENGINE_ONLY_INSTRUMENTS
    geom = geom_from_build_kwargs(
        {"instrument": "FD9", "paper": "A4", "patch_w": 8, "hflag": True}
    )
    assert patches_per_sheet(geom, 210, 297) == 500
    result = normal(source, tmp_path / "normal", instrument="FD9", paper="A4", dpi=100)
    assert len(checked_chart(result.ti2_path)[2]) == 300


def test_shared_custom_sheet_limits_and_capacity(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
    assert panel.custom_w.maximum() == 330 and panel.custom_h.maximum() == 660
    assert capacity("330x660") == 2145


def test_guided_fd9_selection_collects_native_parameters(qapp, tmp_path, qtbot):
    from core.settings import AppSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart

    settings = AppSettings()
    from PyQt6.QtCore import QSettings

    settings._qs = QSettings(str(tmp_path / "isolated.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(tmp_path / "projects"))
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    qtbot.addWidget(tab)
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("FD9"))
    assert tab._paper_combo.findData("137x300") >= 0
    assert tab._paper_combo.findData("A2") < 0
    assert not hasattr(tab, "_fd9_sheet_btn")
    assert tab._pages_spin.maximum() == 20
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("137x300"))
    params = tab._collect_guided()
    assert (
        params.instrument == "FD9" and params.pages == 1 and params.paper == "137x300"
    )
    assert tab._predicted_patch_count == 300
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("i1"))
    assert tab._pages_spin.maximum() == 20


def test_native_vector_pdf_retains_multichannel_colorants(tmp_path):
    source, _ = ti1(
        tmp_path,
        "CMYKcmk1kRGB",
        ("C", "M", "Y", "K", "c", "m", "k", "1k", "R", "G", "B"),
        12,
    )
    result = build_chart(source, tmp_path / "vector", dpi=100, export_pdf=True)
    assert result.pdf_path.is_file()
    data = result.pdf_path.read_bytes()
    assert b"/DeviceN" in data and b"/Cyan" in data and b"/Black" in data


def test_manual_fd9_limits_papers_pages_and_explains_fixed_grid(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel

    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
    assert panel.paper.findData("A2") < 0
    assert panel.pages.maximum() == 20
    # 4.3.25: no note box; the greyed controls' tooltip explains instead.
    assert not hasattr(panel, "fd9_notice") and panel._fd9_support
    assert panel.custom_w.maximum() == 330 and panel.custom_h.maximum() == 660


def test_printer_calibration_changes_printed_inks_only(tmp_path):
    source, _ = ti1(tmp_path, count=12)
    cal = tmp_path / "halved.cal"
    cal.write_text(
        'CAL\nCOLOR_REP "CMYK"\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\nCMYK_I CMYK_C CMYK_M CMYK_Y CMYK_K\nEND_DATA_FORMAT\nNUMBER_OF_SETS 2\nBEGIN_DATA\n0 0 0 0 0\n1 .5 .5 .5 .5\nEND_DATA\n',
        encoding="utf-8",
    )
    result = build_chart(
        source,
        tmp_path / "calibrated",
        dpi=100,
        cal_path=cal,
        apply_cal=True,
        randomize=False,
    )
    _, doc, _ = checked_chart(result.ti2_path)
    pixels = tifffile.imread(result.tiff_paths[0])
    for patch in doc["rows"][0]:
        x, y = (round(v * 100 / 25.4) for v in patch["centre_mm"])
        expected = np.array(patch["device_values"]) * 2.55 * 0.5
        assert np.max(np.abs(pixels[y, x].astype(float) - np.rint(expected))) <= 1
    assert "CAL\n" in result.ti2_path.read_text(encoding="utf-8")


def test_custom_sheet_defaults_survive_restart(qapp, tmp_path, qtbot):
    from core.settings import AppSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart

    settings = AppSettings()
    from PyQt6.QtCore import QSettings

    settings._qs = QSettings(str(tmp_path / "isolated.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(tmp_path / "projects"))
    settings.set("chart_instrument", "FD9")
    settings.set("chart_paper", "250x360")
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    qtbot.addWidget(tab)
    assert tab._instr_combo.currentData() == "FD9"
    assert tab._paper_combo.currentData() == "250x360"


@pytest.mark.parametrize("patch_mm", [6, 8])
def test_generated_square_marks_are_recognised_at_scanner_scale(tmp_path, patch_mm):
    from PIL import Image
    from workflow.fd9.independent import driver, chart_grid

    from pathlib import Path

    package = Path(__file__).resolve().parents[1] / "vendor/fd9-independent"
    driver(package)
    from fd9_independent.geometry import find_marks, grid_rows

    source, _ = ti1(tmp_path, count=300)
    result = build_chart(
        source,
        tmp_path / "marks",
        paper="137x300",
        dpi=300,
        randomize=False,
        patch_mm=patch_mm,
    )
    _, doc, _ = checked_chart(result.ti2_path)
    with Image.open(result.tiff_paths[0]) as im:
        gray = im.convert("L")
    scan = Image.new("L", (3638, 4252), 255)
    left = (3638 - gray.width) // 2
    top = 490
    scan.paste(gray, (left, top))
    scan = scan.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    marks = find_marks(scan.tobytes(), *scan.size)
    rows = grid_rows(marks, **chart_grid(doc))
    assert len(rows) == len(doc["rows"])
    # The actual image is mirrored; generated physical X must use that mapping.
    for row, cells in zip(rows, doc["rows"]):
        for (x, y), cell in zip(row, cells):
            assert x == pytest.approx(
                left + cell["centre_mm"][0] * 300 / 25.4 + 1, abs=2
            )
            assert y == pytest.approx(top + cell["centre_mm"][1] * 300 / 25.4, abs=2)


def test_measurement_filing_retains_printer_calibration_and_ink_limit(tmp_path):
    from workflow.fd9.measurement import stamp_locations, _write_rows, _keywords
    from workflow.printer_calibration import embedded_cal_text

    source = tmp_path / "raw.ti3"
    source.write_text(
        'CTI3\nCOLOR_REP "CMYK_XYZ"\nNUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID LAB_L\nEND_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 90\nEND_DATA\n',
        encoding="utf-8",
    )
    cal = 'CAL\nCOLOR_REP "CMYK"\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\nCMYK_I CMYK_C CMYK_M CMYK_Y CMYK_K\nEND_DATA_FORMAT\nNUMBER_OF_SETS 2\nBEGIN_DATA\n0 0 0 0 0\n1 1 1 1 1\nEND_DATA\n'
    chart = tmp_path / "chart.ti2"
    chart.write_text('CTI2\nTOTAL_INK_LIMIT "220"\n' + cal, encoding="utf-8")
    located = tmp_path / "located.ti3"
    stamp_locations(source, located, {1: "A1"}, "session", chart=chart)
    assert embedded_cal_text(located) == embedded_cal_text(chart)
    assert _keywords(located.read_text(encoding="utf-8"))["COLOR_REP"] == "CMYK_XYZ"
    assert _keywords(located.read_text(encoding="utf-8"))["TOTAL_INK_LIMIT"] == "220"
    _, _, rows = first_table(located)
    joined = tmp_path / "joined.ti3"
    _write_rows(located, joined, rows, {"FD9_SOURCE_SESSIONS": "session"})
    assert embedded_cal_text(joined) == embedded_cal_text(chart)
    assert _keywords(joined.read_text(encoding="utf-8"))["COLOR_REP"] == "CMYK_XYZ"


def test_dotted_project_stem_is_never_shortened(tmp_path):
    source, _ = ti1(tmp_path, count=12)
    result = build_chart(source, tmp_path / "chart.v1", dpi=100)
    assert result.ti2_path.name == "chart.v1.ti2"
    assert result.tiff_paths[0].name == "chart.v1.tif"
    checked_chart(result.ti2_path)


def test_16bit_rgb_keeps_more_than_eight_bit_precision(tmp_path):
    source, _ = ti1(tmp_path, "RGB", ("R", "G", "B"), 12)
    text = source.read_text(encoding="utf-8").replace(
        "0.0 23.0 46.0", "0.1234 23.4567 46.7891"
    )
    source.write_text(text, encoding="utf-8")
    result = build_chart(
        source, tmp_path / "sixteen", dpi=100, bit16=True, randomize=False
    )
    pixels = tifffile.imread(result.tiff_paths[0])
    assert pixels.dtype == np.uint16
    _, doc, _ = checked_chart(result.ti2_path)
    p = doc["rows"][0][0]
    x, y = (round(v * 100 / 25.4) for v in p["centre_mm"])
    assert (
        pixels[y, x].tolist()
        == np.rint(np.array(p["device_values"]) * 655.35).astype("uint16").tolist()
    )


def test_print_gray_uses_white_zero_ink_and_black_marks(tmp_path):
    source = tmp_path / "gray.ti1"
    source.write_text(
        'CTI1\nCOLOR_REP "K"\nBEGIN_DATA_FORMAT\nSAMPLE_ID GRAY_K\nEND_DATA_FORMAT\nBEGIN_DATA\n1 0\n2 100\nEND_DATA\n',
        encoding="utf-8",
    )
    result = build_chart(source, tmp_path / "gray", dpi=100, randomize=False)
    _, doc, _ = checked_chart(result.ti2_path)
    pixels = tifffile.imread(result.tiff_paths[0])
    for p in doc["rows"][0][:2]:
        x, y = (round(v * 100 / 25.4) for v in p["centre_mm"])
        assert (
            pixels[y, x].tolist() == [round((100 - p["device_values"][0]) * 2.55)] * 3
        )


from tests.test_fd9_partial import setup


def test_stop_before_prescan_reports_original_error_without_export(setup):
    from workflow.fd9.measurement import measure_chart
    from workflow.fd9.independent import CaptureFailed

    def stopped(source, layout, dest, host, **kwargs):
        dest.mkdir()
        raise CaptureFailed(dest, "Stopped before sheet insertion")

    with pytest.raises(CaptureFailed, match="Stopped before sheet insertion"):
        measure_chart(
            setup.chart, setup.settings, setup.tmp / "no-scan", capture=stopped
        )


def test_light_ink_names_remain_distinct_in_print_files(tmp_path):
    source, _ = ti1(
        tmp_path,
        "CMYKcmk1kRGB",
        ("C", "M", "Y", "K", "c", "m", "k", "1k", "R", "G", "B"),
        12,
    )
    result = build_chart(source, tmp_path / "light-inks", dpi=100, export_pdf=True)
    with tifffile.TiffFile(result.tiff_paths[0]) as f:
        names = f.pages[0].tags["InkNames"].value.split("\0")
    assert len(set(n for n in names if n)) == 11
    assert "Light Cyan" in names and "Light Light Black" in names
    assert b"/LightCyan" in result.pdf_path.read_bytes()
    assert b"/LightLightBlack" in result.pdf_path.read_bytes()


def test_manual_fixed_seed_and_bit_depth_reach_fd9_builder():
    from workflow.chart_creator import ChartCreator, ChartParams
    from workflow.layout_engine.presets import LayoutRecipe
    from types import SimpleNamespace

    recipe = LayoutRecipe(
        instrument="FD9", paper="137x300", seed=42, randomize=False, bit16=True
    )
    params = ChartParams(instrument="FD9", paper="137x300", layout_recipe=recipe)
    kw = ChartCreator._engine_kwargs(SimpleNamespace(), params)
    assert kw["seed"] == 42 and kw["randomize"] is False and kw["bit16"] is True


@pytest.mark.parametrize("action_name", ["RENAME", "KEEP", "DELETE"])
def test_project_choice_buttons_end_dialog_with_the_requested_action(
    qtbot, tmp_path, action_name
):
    from ui.dialogs.target_change_dialog import TargetChangeDialog, TargetChangeAction
    from PyQt6.QtWidgets import QPushButton
    from PyQt6.QtCore import Qt, QTimer

    action = TargetChangeAction[action_name]
    dlg = TargetChangeDialog("old", "new", tmp_path / "old", tmp_path / "new")
    qtbot.addWidget(dlg)
    frame = dlg._option_button("Test action", "Description", action)
    button = frame.findChild(QPushButton)
    # Exercise the actual modal unwind, which source/stub tests never reached.
    QTimer.singleShot(0, button.click)
    dlg.exec()
    assert dlg.result_action() is action


def ramp_ti1(tmp_path, tokens, levels):
    source, _ = ti1(
        tmp_path, "RGB" if len(tokens) == 3 else "CMYKcmk1kRGB", tokens, count=1
    )
    additive = len(tokens) == 3
    white = [100.0 if additive else 0.0] * len(tokens)
    values = [white]
    for ch in range(len(tokens)):
        for step in range(1, levels):
            patch = white.copy()
            patch[ch] = (
                (100 - step * 100 / (levels - 1))
                if additive
                else step * 100 / (levels - 1)
            )
            values.append(patch)
    text = source.read_text(encoding="utf-8")
    text = (
        text.split("NUMBER_OF_SETS", 1)[0]
        + f"NUMBER_OF_SETS {len(values)}\nBEGIN_DATA\n"
    )
    text += (
        "\n".join(
            str(i + 1) + " " + " ".join(map(str, row)) for i, row in enumerate(values)
        )
        + "\nEND_DATA\n"
    )
    text = text.replace(
        "NUMBER_OF_FIELDS", f'SINGLE_DIM_STEPS "{levels}"\nNUMBER_OF_FIELDS', 1
    )
    source.write_text(text, encoding="utf-8")
    return source


def test_eleven_ink_linearization_has_one_ramp_per_column_and_rebuilds(tmp_path):
    tokens = ("C", "M", "Y", "K", "c", "m", "k", "1k", "R", "G", "B")
    source = ramp_ti1(tmp_path, tokens, 25)
    from workflow.layout_engine.chart import build_chart as normal

    result = normal(
        source,
        tmp_path / "ramps",
        instrument="FD9",
        paper="137x300",
        dpi=72,
        ramps_per_strip=True,
    )
    assert result.ramp_whites_added == 35 and not result.randomize
    assert result.layout.steps_in_pass == 25
    original = source.read_bytes()
    assert b'SINGLE_DIM_STEPS "25"' in original
    _, definition, _ = checked_chart(result.ti2_path)
    for c in range(11):
        assert definition["rows"][0][c]["device_values"] == [0] * 11
        for r in range(1, 25):
            values = definition["rows"][r][c]["device_values"]
            assert values[c] == pytest.approx(r * 100 / 24)
            assert sum(v != 0 for v in values) == 1
    assert all(not any(row[11]["device_values"]) for row in definition["rows"])
    rebuilt = normal(
        source,
        tmp_path / "rebuilt",
        instrument="FD9",
        paper="137x300",
        dpi=72,
        ramps_per_strip=True,
    )
    assert source.read_bytes() == original and rebuilt.ramp_whites_added == 0
    assert np.array_equal(
        tifffile.imread(result.tiff_paths[0]), tifffile.imread(rebuilt.tiff_paths[0])
    )


def test_long_calibration_ramp_continues_before_next_ink(tmp_path):
    source = ramp_ti1(tmp_path, ("R", "G", "B"), 32)
    result = build_chart(source, tmp_path / "long", dpi=72, ramps_per_strip=True)
    assert result.layout.steps_in_pass == 25
    _, definition, _ = checked_chart(result.ti2_path)
    assert definition["rows"][0][2]["device_values"] == [100] * 3
    assert definition["rows"][1][2]["device_values"][1] < 100
    assert definition["rows"][6][1]["device_values"][0] == 0
    assert definition["rows"][7][1]["device_values"] == [100] * 3


def test_calibration_spans_sheets_when_ramp_columns_do_not_fit(tmp_path):
    source = ramp_ti1(
        tmp_path, ("C", "M", "Y", "K", "c", "m", "k", "1k", "R", "G", "B"), 25
    )
    result = build_chart(source, tmp_path / "ramps", paper="137x170", dpi=72, ramps_per_strip=True)
    assert result.layout.pages > 1 and len(result.tiff_paths) == result.layout.pages
    assert result.ramp_whites_added > 0



@pytest.mark.parametrize("paper", ["A3", "330x660"])
def test_large_sheet_uses_width_and_measures_all_locations(tmp_path, paper):
    from workflow.fd9.chart import grid_shape
    from workflow.layout_engine.labels import alpha_label

    columns, rows = grid_shape(paper)
    source, _ = ti1(tmp_path, count=columns * rows)
    result = build_chart(source, tmp_path / "large", paper=paper, dpi=72, seed=42)
    _, layout, locations = checked_chart(result.ti2_path)
    assert len(locations) > 1000
    assert len(layout["rows"]) == rows and len(layout["rows"][0]) == columns
    assert alpha_label(columns) + str(rows) in locations.values()
    w, h = layout["paper_mm"]
    assert layout["fiducials_mm"][0][0] - 1.5 == 4
    assert w - layout["fiducials_mm"][1][0] - 1.5 == 4
    pixels = tifffile.imread(result.tiff_paths[0])
    for row in layout["rows"]:
        for patch in row:
            x, y = [round(v * 72 / 25.4) for v in patch["centre_mm"]]
            assert (
                np.max(
                    np.abs(
                        pixels[y, x].astype(float)
                        - np.rint(np.array(patch["device_values"]) * 2.55)
                    )
                )
                <= 1
            )


def test_large_chart_partial_resume_retains_verified_prefix(setup):
    from tests.test_fd9_partial import action
    from workflow.fd9.measurement import measure_chart, publish_measurement

    source, _ = ti1(setup.tmp, count=2145)
    result = build_chart(
        source, setup.tmp / "large-chart", paper="330x660", dpi=72, randomize=False
    )
    setup.chart = result.ti2_path
    setup.layout = checked_chart(setup.chart)[1]
    first = measure_chart(
        setup.chart, setup.settings, setup.tmp / "large-first", capture=action(setup, 2)
    )
    assert first["patches"] == 66
    target = publish_measurement(
        first["staged"], first["destination"], setup.chart, allow_partial=True
    )
    prefix = first_table(target)[2]
    from dataclasses import replace

    resumed = measure_chart(
        setup.chart,
        replace(setup.settings, resume=True),
        setup.tmp / "large-resumed",
        capture=action(setup, 63, complete=True),
    )
    assert resumed["patches"] == 2145 and resumed["new_readings"] == 2079
    assert first_table(resumed["staged"])[2][:66] == prefix


@pytest.mark.parametrize(
    "size,paper,expected",
    [
        (6, "A4", 800),
        (6, "A3", 1862),
        (6, "330x660", 3612),
        (7.5, "A4", 546),
        (8, "A4", 500),
        (30, "A4", 35),
    ],
)
def test_patch_size_drives_capacity_print_pixels_and_geometry(
    tmp_path, size, paper, expected
):
    assert capacity(paper, size) == expected
    source, _ = ti1(tmp_path, count=expected)
    from workflow.layout_engine.chart import build_chart as normal
    from workflow.layout_engine.instruments import geom_from_build_kwargs
    from workflow.layout_engine.geometry import patches_per_sheet

    geom = geom_from_build_kwargs({"instrument": "FD9", "patch_w": size})
    w, h = dimensions(paper)
    assert patches_per_sheet(geom, w, h) == expected
    result = normal(
        source,
        tmp_path / "variable",
        instrument="FD9",
        paper=paper,
        patch_w=size,
        dpi=100,
        export_pdf=True,
    )
    _, layout, locations = checked_chart(result.ti2_path)
    assert layout["patch_mm"] == [size, size] and len(locations) == expected
    side = json.loads(
        result.ti2_path.with_suffix(".strips.json").read_text(encoding="utf-8")
    )
    assert len(side["patches"]) == expected
    pixels = tifffile.imread(result.tiff_paths[0])
    for row in layout["rows"]:
        for patch in row:
            x, y = [round(v * 100 / 25.4) for v in patch["centre_mm"]]
            assert (
                np.max(
                    np.abs(
                        pixels[y, x].astype(float)
                        - np.rint(np.array(patch["device_values"]) * 2.55)
                    )
                )
                <= 1
            )
    assert side["patches"][0]["w"] == pytest.approx(size * 100 / 25.4, abs=1)


@pytest.mark.parametrize("size", [0, 5.9, 30.1, float("nan"), float("inf")])
def test_invalid_patch_size_never_creates_outputs(tmp_path, size):
    source, _ = ti1(tmp_path, count=1)
    with pytest.raises(ValueError, match="6..30"):
        build_chart(source, tmp_path / "invalid", patch_mm=size)
    assert not (tmp_path / "invalid.tif").exists()


def test_shared_patch_size_controls_and_manual_recipe_restore(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.presets import LayoutRecipe

    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.set_recipe(
        LayoutRecipe(instrument="FD9", paper="A4", patch_w_mm=6, patch_h_mm=6)
    )
    recipe = panel.get_recipe()
    assert recipe.build_kwargs()["patch_w"] == 6 and recipe.patch_h_mm == 6
    assert panel.patch_x.isEnabled() and panel.patch_y.isEnabled()


def test_guided_small_patch_size_reaches_creator_and_restore(qapp, qtbot, tmp_path):
    from core.settings import AppSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.presets import LayoutRecipe

    settings = AppSettings()
    from PyQt6.QtCore import QSettings

    settings._qs = QSettings(str(tmp_path / "isolated.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(tmp_path / "projects"))
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    qtbot.addWidget(tab)
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("FD9"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    # A target or chart being loaded (review r1 L5: a Manual preset is not).
    tab._set_engine_recipe(
        LayoutRecipe(instrument="FD9", paper="A4", patch_w_mm=6, patch_h_mm=6),
        for_guided=True,
    )
    params = tab._collect_guided()
    assert params.fd9_patch_mm == 6
    assert tab._creator._engine_total_patches(params) == 800
    assert tab._creator._engine_kwargs(params)["patch_w"] == 6
    assert tab._creator._engine_build_kwargs(params)["patch_w"] == 6


def test_minimum_patch_never_rounds_below_six_mm(tmp_path):
    import math
    import fitz

    source, _ = ti1(tmp_path, count=40)
    result = build_chart(
        source,
        tmp_path / "minimum",
        paper="A4",
        patch_mm=6,
        dpi=300,
        randomize=False,
        export_pdf=True,
    )
    _, layout, _ = checked_chart(result.ti2_path)
    pixels = tifffile.imread(result.tiff_paths[0])
    side = json.loads(
        result.ti2_path.with_suffix(".strips.json").read_text(encoding="utf-8")
    )
    assert all(
        min(p["w"], p["h"]) >= math.ceil(6 * 300 / 25.4) for p in side["patches"]
    )
    for row in layout["rows"]:
        for p in row:
            if p["id"] > 40:
                continue
            x, y = [round(v * 300 / 25.4) for v in p["centre_mm"]]
            color = pixels[y, x]
            left = right = x
            while np.array_equal(pixels[y, left - 1], color):
                left -= 1
            while np.array_equal(pixels[y, right + 1], color):
                right += 1
            top = bottom = y
            while np.array_equal(pixels[top - 1, x], color):
                top -= 1
            while np.array_equal(pixels[bottom + 1, x], color):
                bottom += 1
            assert (right - left + 1) * 25.4 / 300 >= 6 and (
                bottom - top + 1
            ) * 25.4 / 300 >= 6
    with fitz.open(result.pdf_path) as pdf:
        patches = [
            d["rect"]
            for d in pdf[0].get_drawings()
            if d["rect"].width > 4 * 72 / 25.4 and d["rect"].height < 7 * 72 / 25.4
        ]
        assert len(patches) == len(layout["rows"]) * len(layout["rows"][0])
        assert all(
            r.width * 25.4 / 72 == pytest.approx(6, abs=0.0001)
            and r.height * 25.4 / 72 == pytest.approx(6, abs=0.0001)
            for r in patches
        )
