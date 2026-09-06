"""The Chart-layout-information panel's two columns must describe ONE chart.

Basti, 4.1.5-beta.11, with Knut's CR30 presets: loading the 360-patch preset
made the panel read *on screen 360, estimate 192*, and loading the 192-patch one
next made it read *192 / 360* — each column showing the other preset's chart.
The estimate also claimed **8** strips against the panel's own "Strips
(columns)" control saying **15**.

Both symptoms are one number. The estimate lays out a patch count taken from the
chart in the PREVIEW, and nothing recomputed it when the preview changed — so
every Generate left it describing the chart from before the build. The strip
count went with it, because the estimate derives its strips from that total: 192
patches occupy 8 of the 15 strips the grid offers, 360 occupy all 15.

These tests pin the wiring (a chart landing in the preview refreshes the
estimate), the arithmetic (the strips row agrees with the grid control), and the
source (an armed patch set beats the chart on screen, because that is what
Generate would lay out).
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402

# Knut's CR30 preset, reduced to the fields that decide the layout.
GRID_COLS, GRID_ROWS = 15, 24
RECIPE = dict(
    instrument="CR30", paper="A4", dpi=200,
    layout_mode="area_first", area_method="by_grid",
    area_cols=GRID_COLS, area_rows=GRID_ROWS,
    use_instrument_margins=False,
    margin_top=17.0, margin_right=26.0, margin_bottom=12.0, margin_left=15.0,
    border=6.0, nolimit=True, layout_explicit=True,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    s.set("layout_info_show", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._manual_btn.setChecked(True)
    tab._manual_engine_check.setChecked(True)
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(False)
    from workflow.layout_engine.presets import LayoutRecipe
    base = tab._manual_layout_panel.get_recipe()
    tab._manual_layout_panel.set_recipe(
        LayoutRecipe(**{**base.__dict__, **RECIPE}))
    return tab


def _ti1(path: Path, n: int) -> Path:
    """A .ti1 with *n* patches — only NUMBER_OF_SETS is ever read from it."""
    path.write_text(
        'CTI1\n\nDESCRIPTOR "test"\nORIGINATOR "chromiq patch editor"\n'
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
        "END_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n"
        + "".join(f"{i + 1} 100 100 100\n" for i in range(n))
        + "END_DATA\n", encoding="utf-8")
    return path


def _chart_on_screen(tab, tmp_path: Path, n: int, name: str) -> None:
    """Put a chart of *n* patches into the preview, the way a finished build
    does — `_set_margin_chart` is the single door every chart comes through."""
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    strips = math.ceil(n / GRID_ROWS)
    ti2 = d / f"{name}.ti2"
    ti2.write_text(
        'CTI2\n\nDESCRIPTOR "test"\nORIGINATOR "ChromIQ layout engine"\n'
        f'TARGET_INSTRUMENT "CR30"\nPAPER_SIZE "210.0x297.0"\n'
        f'STEPS_IN_PASS "{GRID_ROWS}"\nPASSES_IN_STRIPS2 "{strips}"\n'
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G\nEND_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    _ti1(d / f"{name}.ti1", n)
    tif = d / f"{name}.tif"
    tif.write_bytes(b"II*\x00")
    tab._current_ti1_path = d / f"{name}.ti1"
    tab._set_margin_chart([tif], ti2)


def _est(tab, key):
    return tab._layout_info_panel._estimate_labels[key].text()


def _actual(tab, key):
    return tab._layout_info_panel._actual_labels[key].text()


def test_a_new_chart_on_screen_refreshes_the_estimate(qapp, tmp_path):
    """Basti's journey, in the order he walked it. Before the fix the estimate
    lagged exactly one chart, which a two-preset A/B makes look like a swap."""
    tab = _tab(tmp_path)

    _chart_on_screen(tab, tmp_path, 192, "c192")
    assert _actual(tab, "total") == "192"
    assert _est(tab, "total") == "192", "the estimate must follow the new chart"

    _chart_on_screen(tab, tmp_path, 360, "c360")
    assert _actual(tab, "total") == "360"
    # THIS is the reported fault: it used to still say 192 here.
    assert _est(tab, "total") == "360"

    _chart_on_screen(tab, tmp_path, 192, "c192b")
    assert _actual(tab, "total") == "192"
    assert _est(tab, "total") == "192"


def test_the_estimate_strip_count_agrees_with_the_grid_control(qapp, tmp_path):
    """"Strips (this page)" must be the strips the estimated patches occupy in
    the grid the control asks for — never more than the grid offers, and exactly
    the grid when the page is full. Basti read 8 against a control saying 15."""
    tab = _tab(tmp_path)
    for n, expect_cols in ((192, 8), (360, 15), (24, 1)):
        _chart_on_screen(tab, tmp_path, n, f"g{n}")
        total = int(_est(tab, "total"))
        rows = int(_est(tab, "rows"))
        cols = int(_est(tab, "cols"))
        assert rows == GRID_ROWS
        assert cols == expect_cols
        assert cols == math.ceil(total / rows)
        assert cols <= GRID_COLS
    # A full page uses every strip the control asks for.
    _chart_on_screen(tab, tmp_path, GRID_COLS * GRID_ROWS, "gfull")
    assert int(_est(tab, "cols")) == GRID_COLS


def test_an_armed_patch_set_beats_the_chart_still_on_screen(qapp, tmp_path):
    """Selecting a preset arms its .ti1 long before the build finishes. Until
    then the estimate answered with the patch count of the chart still on
    screen — the PREVIOUS preset's. The estimate is "what Generate would give",
    so the armed set wins."""
    tab = _tab(tmp_path)
    _chart_on_screen(tab, tmp_path, 192, "s192")
    assert _est(tab, "total") == "192"

    tab._preset_ti1_path = _ti1(tmp_path / "armed360.ti1", 360)
    tab._preset_ti1_targen_sig = tab._targen_signature()
    tab._refresh_layout_estimate()
    assert _actual(tab, "total") == "192", "the shown chart has not changed"
    assert _est(tab, "total") == "360"
    assert _est(tab, "cols") == "15"


def test_editing_the_targen_recipe_drops_the_armed_patch_set(qapp, tmp_path):
    """Ticking the targen override and then changing a targen value is how a
    user opts out of a preset's patches — `_on_generate` builds a fresh set, so
    the estimate must stop quoting the armed .ti1 too."""
    tab = _tab(tmp_path)
    _chart_on_screen(tab, tmp_path, 192, "o192")
    tab._preset_ti1_path = _ti1(tmp_path / "armed360b.ti1", 360)
    tab._preset_ti1_targen_sig = "a signature from before the edit"
    tab._refresh_layout_estimate()
    assert _est(tab, "total") == "360", "not opted out yet"

    tab._override_targen_check.setChecked(True)
    tab._refresh_layout_estimate()
    assert _est(tab, "total") == "192", "back to the chart on screen"


def test_refreshing_the_estimate_writes_nothing(qapp, tmp_path):
    """The panel is a READOUT. Wiring it to `_set_margin_chart` may not put one
    byte on disk, or a passive refresh would be rewriting the user's chart."""
    import hashlib
    tab = _tab(tmp_path)
    _chart_on_screen(tab, tmp_path, 192, "w192")
    d = tmp_path / "w192"
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(d.iterdir())}
    for _ in range(3):
        tab._refresh_layout_estimate()
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(d.iterdir())}
    assert before == after


def test_set_margin_chart_still_refreshes_the_estimate_in_source(qapp):
    """The wiring itself, named. `_set_margin_chart` is the one door every chart
    comes through; the estimate refresh has to be behind it."""
    import inspect
    src = inspect.getsource(TabChart._set_margin_chart)
    assert "_refresh_layout_estimate" in src
