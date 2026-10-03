"""B8-1704: the sheet's "Chart layout" stamp line prints a built-in preset's
name exactly as written, with the instrument token in front.

Knut, #182 5879401111: *"The names given to the presets shall not be altered.
The sequence shall stay, as it was given when the preset was saved"*, and
5879774498 for the stamp line. Up to 4.3.1 `_sortable_builtin_name` moved the
``-w<number>mm`` width and any family suffix to the end, so the i1Pro
"A4-324p-1page-Portrait-w7.5mm-Uniform 6x6x6" was stamped as
"Chart layout i1Pro-A4-324p-1page-Portrait-Uniform 6x6x6-w7.5mm" (measured on
screen 2026-09-29, ~/Desktop/ChromIQ-430-stable-prep/b8-1704-stamp/).
"""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402

# Knut renamed his example in 4.3.3-beta.1 (#182 5943544919): "-Half Page" added.
KNUTS_EXAMPLE = "A4-324p-1page-Portrait-w7.5mm-Uniform 6x6x6-Half Page"
KNUTS_LINE = "Chart layout i1Pro-A4-324p-1page-Portrait-w7.5mm-Uniform 6x6x6-Half Page"
THE_OLD_LINE = "Chart layout i1Pro-A4-324p-1page-Portrait-Uniform 6x6x6-w7.5mm"


def _the_example():
    from ui.tabs.tab_chart import KNUT_PRESETS
    return next(p for p in KNUT_PRESETS
                if p.name == KNUTS_EXAMPLE and p.file_group == "i1Pro")


def test_every_builtin_is_stamped_with_its_name_unchanged():
    from ui.tabs.tab_chart import KNUT_PRESETS
    for p in KNUT_PRESETS:
        assert p.default_target_name == f"{p.file_group}-{p.name}", p.name


def test_knuts_example_keeps_the_width_where_he_wrote_it():
    p = _the_example()
    assert p.default_target_name == \
        "i1Pro-A4-324p-1page-Portrait-w7.5mm-Uniform 6x6x6-Half Page"


def test_a_suffix_stays_in_its_written_place():
    """The 14 built-ins whose name carries a family suffix print it where the
    name has it, " · " included, and the display-only "Full layout setup"
    marker of `marked_name` is not printed where the name does not carry it."""
    from ui.tabs.tab_chart import KNUT_PRESETS, KNUT_FLS_SUFFIX
    suffixed = [p for p in KNUT_PRESETS if p.suffix and p.name.endswith(p.suffix)]
    assert len(suffixed) == 14
    for p in suffixed:
        assert p.default_target_name.endswith(p.suffix), p.name
    fls = next(p for p in suffixed
               if p.name == "A4-484p-1page-Portrait-w7.5mm-Uniform 7x7x7"
                            " · Full layout setup")
    assert fls.default_target_name == (
        "i1Pro-A4-484p-1page-Portrait-w7.5mm-Uniform 7x7x7 · Full layout setup")
    marked_only = _the_example()
    assert marked_only.marked_name.endswith(KNUT_FLS_SUFFIX)
    assert KNUT_FLS_SUFFIX not in marked_only.default_target_name


def test_the_list_row_and_the_key_are_unchanged():
    p = _the_example()
    assert p.combo_label == (
        "★  i1Pro · A4-324p-1page-Portrait-w7.5mm-Uniform 6x6x6-Half Page"
        " · Full layout setup  ·  built-in")
    assert p.key.startswith("__chromiq_knut_") and p.key.endswith("__")


def test_the_stamper_prints_the_line_knut_asked_for():
    from workflow.chart_creator import ChartParams, ChartCreator
    p = ChartParams(chart_notes="", stamp_commands=True,
                    chart_layout_name=_the_example().default_target_name)
    cc = ChartCreator.__new__(ChartCreator)
    cc._should_use_engine = lambda _p: True
    cc._build_targen_args = lambda _p, n: ["-d2", f"-f{n}", "test"]
    lines = ChartCreator.stamp_lines(cc, p, 324)
    assert KNUTS_LINE in lines, lines
    assert THE_OLD_LINE not in lines, lines


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_the_tab_stamps_and_predicts_the_same_name(qapp, tmp_path):
    """`_active_layout_name` is what the build hands the stamper, and
    `_predicted_chart_layout_name` is what the "Measured from Preview"
    note-length warning measures; both must carry the name as written."""
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    p = _the_example()
    t._knut_active, t._knut_active_key = True, p.key
    t._knut_targen_sig = t._targen_signature()
    assert t._active_layout_name() == p.default_target_name
    assert t._predicted_chart_layout_name() == p.default_target_name
