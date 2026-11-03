"""Native FD-9 shapes, touching-cell pixels and the shared edit route."""

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
import json
from pathlib import Path

import numpy as np
import pytest
import tifffile
from tests.test_fd9_chart_creation import ti1
from workflow.fd9.chart import build_chart, capacity, grid_shape
from workflow.fd9.measurement import checked_chart
from workflow.layout_engine.chart import build_chart as normal_build
from workflow.layout_engine.geometry import patches_per_sheet
from workflow.layout_engine.instruments import geom_from_build_kwargs
from workflow.layout_engine.presets import LayoutRecipe


@pytest.mark.parametrize(
    "width,height,gap,dpi",
    [
        (8, 6, 0, 300),
        (6, 8, 0, 300),
        (6, 6, 0, 72),
        (6, 6, 0, 300),
        (6, 30, 0, 150),
        (30, 6, 0.5, 150),
        (8, 12, 1, 100),
    ],
)
def test_rectangles_and_gaps_match_every_printed_cell_and_sidecar(
    tmp_path, width, height, gap, dpi
):
    import fitz

    paper = "A4"
    total = capacity(paper, width, height, gap, dpi)
    source, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=total)
    kwargs = dict(
        instrument="FD9",
        paper=paper,
        patch_w=width,
        patch_h=height,
        fd9_gap=gap,
        dpi=dpi,
    )
    geom = geom_from_build_kwargs(kwargs)
    assert patches_per_sheet(geom, 210, 297) == total
    result = normal_build(
        source, tmp_path / "rect", **kwargs, export_pdf=True, randomize=False
    )
    _, layout, _ = checked_chart(result.ti2_path)
    assert layout["gap_mm"] == [gap, gap]
    assert layout["generation"]["requested_patch_mm"] == [width, height]
    assert layout["patch_mm"] == pytest.approx([geom.pwid, geom.plen])
    assert len(layout["rows"]) * len(layout["rows"][0]) == total
    image = tifffile.imread(result.tiff_paths[0])
    side = json.loads(
        result.ti2_path.with_suffix(".strips.json").read_text(encoding="utf-8")
    )
    rects = {p["loc"]: p for p in side["patches"]}
    for row_index, row in enumerate(layout["rows"]):
        for col, p in enumerate(row):
            from workflow.layout_engine.labels import alpha_label

            rect = rects[f"{alpha_label(col+1)}{row_index+1}"]
            x, y, w, h = [rect[k] for k in ("x", "y", "w", "h")]
            expected = np.rint(np.array(p["device_values"]) * 2.55).astype(image.dtype)
            assert (
                np.max(np.abs(image[y : y + h, x : x + w].astype(float) - expected))
                <= 1
            ), (row_index, col, rect)
            assert min(w, h) * 25.4 / dpi >= 6
            if gap == 0 and col:
                prev = rects[f"{alpha_label(col)}{row_index+1}"]
                assert prev["x"] + prev["w"] == x
            if gap == 0 and row_index:
                prev = rects[f"{alpha_label(col+1)}{row_index}"]
                assert prev["y"] + prev["h"] == y
    assert (
        layout["rows"][-1][0]["centre_mm"][1] + layout["patch_mm"][1] / 2
        <= 297 - 33 + 1e-6
    )
    with fitz.open(result.pdf_path) as pdf:
        cells = [
            d["rect"]
            for d in pdf[0].get_drawings()
            if any(item[0] == "re" for item in d["items"])
            and 5 * 72 / 25.4 < d["rect"].width < 31 * 72 / 25.4
            and 5 * 72 / 25.4 < d["rect"].height < 31 * 72 / 25.4
        ]
        assert len(cells) == total
        assert all(
            r.width * 25.4 / 72 == pytest.approx(layout["patch_mm"][0], abs=4e-4)
            and r.height * 25.4 / 72 == pytest.approx(layout["patch_mm"][1], abs=4e-4)
            for r in cells
        )


@pytest.mark.parametrize(
    "width,height,gap", [(6, 8, 0), (8, 6, 0), (6, 6, 0), (30, 6, 1), (6, 30, 1)]
)
def test_corner_recognition_does_not_need_patch_gaps(tmp_path, width, height, gap):
    from PIL import Image
    from workflow.fd9.independent import driver, chart_grid

    package = Path(__file__).resolve().parents[1] / "vendor/fd9-independent"
    driver(package)
    from fd9_independent.geometry import find_marks, grid_rows

    total = capacity("137x300", width, height, gap)
    source, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=total)
    result = build_chart(
        source,
        tmp_path / "scan",
        paper="137x300",
        patch_mm=width,
        patch_height_mm=height,
        gap_mm=gap,
        dpi=300,
    )
    _, layout, _ = checked_chart(result.ti2_path)
    with Image.open(result.tiff_paths[0]) as im:
        gray = im.convert("L")
    scan = Image.new("L", (3638, 4252), 255)
    scan.paste(gray, ((3638 - gray.width) // 2, 490))
    scan = scan.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    marks = find_marks(scan.tobytes(), *scan.size)
    rows = grid_rows(marks, **chart_grid(layout))
    assert len(rows) == len(layout["rows"]) and len(rows[0]) == len(layout["rows"][0])


def test_recipe_keeps_zero_gap_rectangular_size_and_legacy_default():
    r = LayoutRecipe(instrument="FD9", patch_w_mm=8, patch_h_mm=6, fd9_gap_mm=0)
    for restored in (
        LayoutRecipe.from_dict(r.to_dict()),
        LayoutRecipe.from_build_kwargs(r.build_kwargs()),
    ):
        assert (restored.patch_w_mm, restored.patch_h_mm, restored.fd9_gap_mm) == (
            8,
            6,
            0,
        )
    assert (
        LayoutRecipe.from_dict({"instrument": "FD9", "patch_w_mm": 8}).fd9_gap_mm == 1
    )
    assert "fd9_gap_mm" not in LayoutRecipe().to_dict()
    assert "fd9_gap" not in LayoutRecipe().build_kwargs()


@pytest.mark.parametrize(
    "height,gap", [(5.9, 1), (30.1, 1), (8, -0.1), (8, 5.1), (8, float("nan"))]
)
def test_invalid_native_sizes_fail_before_output(tmp_path, height, gap):
    source, _ = ti1(tmp_path, count=10)
    with pytest.raises(ValueError):
        build_chart(source, tmp_path / "bad", patch_height_mm=height, gap_mm=gap)
    assert not list(tmp_path.glob("bad.*"))


@pytest.mark.parametrize("mode", ["guided", "manual", "gamut"])
def test_native_editor_opens_shared_preferences_and_keeps_printtarg_off(
    qapp, qtbot, tmp_path, monkeypatch, mode
):
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QDialog
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart, _layout_panel_lays_out
    from ui.dialogs import settings_dialog

    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path / "isolated.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(tmp_path / "projects"))
    settings.set("use_chromiq_layout_engine", False)
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    qtbot.addWidget(tab)
    tab._user_switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("FD9"))
    tab._set_engine_recipe(
        LayoutRecipe(
            instrument="FD9", paper="A4", patch_w_mm=8, patch_h_mm=6, fd9_gap_mm=0
        )
    )
    if mode in ("manual", "gamut"):
        tab._user_switch_mode("manual")
    if mode == "gamut":
        tab._user_switch_mode("gamut")
    assert tab._active_instrument_flag() == "FD9"

    seen=[]
    class Preferences:
        def __init__(self, *args, **kwargs):
            seen.append(kwargs["layout_combo"])
        def exec(self):
            return QDialog.DialogCode.Rejected
    monkeypatch.setattr(settings_dialog, "SettingsDialog", Preferences)
    tab._edit_layout_defaults()
    assert seen and seen[0][0] == "FD9"
    assert _layout_panel_lays_out("FD9", False)
    assert settings.get("use_chromiq_layout_engine") is False



@pytest.mark.parametrize("mode", ["guided", "manual"])
@pytest.mark.parametrize("legacy_square", [False, True])
def test_native_dimensions_survive_startup_and_mode_switches(
    qapp, qtbot, tmp_path, mode, legacy_square
):
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart

    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path / "restart.ini"), QSettings.Format.IniFormat)
    for key, value in {
        "custom_output_path": str(tmp_path / "projects"),
        "use_chromiq_layout_engine": False,
        "chart_instrument": "FD9",
        "chart_paper": "A4",
        "chart_mode": mode,
        "manual_printtarg_-i": "FD9",
        "chart_fd9_patch_mm": 8,
    }.items():
        settings.set(key, value)
    if not legacy_square:
        settings.set("chart_fd9_patch_h_mm", 6)
        settings.set("chart_fd9_gap_mm", 0)
    expected = (8, 8, 1) if legacy_square else (8, 6, 0)
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    qtbot.addWidget(tab)
    for destination in (mode, "manual", "guided", "manual", "guided"):
        tab._user_switch_mode(destination)
        params = tab._collect_params()
        assert params.instrument == "FD9"
        r = params.layout_recipe
        assert (r.patch_w_mm, r.patch_h_mm,
                r.fd9_gap_mm if r.fd9_gap_mm is not None else r.inter_patch_mm) == expected
        assert settings.get("use_chromiq_layout_engine") is False


def test_eleven_channel_touching_rectangles_preserve_each_ink(tmp_path):
    rep = "CMYKcmk1kRGB"
    tokens = ("C", "M", "Y", "K", "c", "m", "k", "1k", "R", "G", "B")
    source, _ = ti1(tmp_path, rep=rep, tokens=tokens, count=40)
    result = build_chart(
        source, tmp_path / "inks", patch_mm=8, patch_height_mm=6, gap_mm=0, dpi=100
    )
    _, layout, _ = checked_chart(result.ti2_path)
    image = tifffile.imread(result.tiff_paths[0])
    assert image.shape[2] == 11 and layout["channel_tokens"] == list(tokens)
    for row in layout["rows"]:
        for p in row:
            x, y = [round(v * 100 / 25.4) for v in p["centre_mm"]]
            assert (
                np.max(
                    np.abs(
                        image[y, x].astype(float) - np.array(p["device_values"]) * 2.55
                    )
                )
                <= 1
            )
