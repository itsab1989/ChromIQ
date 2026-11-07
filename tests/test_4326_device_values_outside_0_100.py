"""4.3.26: a loaded patch set with device values outside 0..100.

jctay (printerknowledge forum, 2026-11-07) loaded a patch set another program
had made, with a red of -23.1373 and a value of 104. ChromIQ's own generators
never write such values, and nothing in the chain agreed on them: printtarg
wraps -23.14 % round to 196 of 255 (a light colour where none was meant)
and 104 % to 10,
colprof and the .ti2 took -23.14 as it was, the layout engine and the
i1Profiler exports clamped it to 0.

Now the RUN'S COPY is held inside 0..100, the person's file is never touched,
a warning names every changed value, and a run that already holds such a
chart compares its measurements with the clamped values (§I.16).

The fixture is invented: four patches, two of them out of range.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import device_range as D                         # noqa: E402

_TABLES = """CTI1

DESCRIPTOR "Argyll Calibration Target chart information 1"
ORIGINATOR "ChromIQ"
DENSITY_EXTREME_VALUES "8"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
INDEX RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 8
BEGIN_DATA
0 100.0000 100.0000 100.0000 95.0500 100.0000 108.9000
1 0.0000 100.0000 100.0000 54.2224 78.9526 106.9893
2 100.0000 0.0000 100.0000 59.6476 29.1952 97.0992
3 0.0000 0.0000 100.0000 18.8200 8.1478 95.1885
4 100.0000 100.0000 0.0000 77.1805 92.8522 14.8005
5 0.0000 100.0000 0.0000 36.3529 71.8048 12.8898
6 100.0000 0.0000 0.0000 41.7781 22.0474 2.9997
7 0.0000 0.0000 0.0000 0.9505 1.0000 1.0890
END_DATA
CTI1

DESCRIPTOR "Argyll Calibration Target chart information 1"
ORIGINATOR "ChromIQ"
DEVICE_COMBINATION_VALUES "9"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
INDEX RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 9
BEGIN_DATA
0 100.0000 100.0000 100.0000 95.0500 100.0000 108.9000
1 0.0000 100.0000 100.0000 54.2224 78.9526 106.9893
2 100.0000 0.0000 100.0000 59.6476 29.1952 97.0992
3 0.0000 0.0000 100.0000 18.8200 8.1478 95.1885
4 100.0000 100.0000 0.0000 77.1805 92.8522 14.8005
5 0.0000 100.0000 0.0000 36.3529 71.8048 12.8898
6 100.0000 0.0000 0.0000 41.7781 22.0474 2.9997
7 0.0000 0.0000 0.0000 0.9505 1.0000 1.0890
8 50.0000 50.0000 50.0000 21.0917 22.1901 24.1650
END_DATA
"""


def _ti1(rows: str) -> str:
    return ("CTI1\n\nDESCRIPTOR \"Argyll Calibration Target chart information "
            "1\"\nORIGINATOR \"Invented for ChromIQ tests\"\nAPPROX_WHITE_POINT "
            "\"95.050000 100.000000 108.900000\"\nCOLOR_REP \"iRGB\"\n\n"
            "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B "
            "XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 4\n"
            "BEGIN_DATA\n" + rows + "END_DATA\n" + _TABLES)


OUT_OF_RANGE = _ti1(
    "1 100.0000 100.0000 100.0000 95.0500 100.0000 108.9000\n"
    "2 0.0000 0.0000 0.0000 0.9505 1.0000 1.0890\n"
    "3 -23.1373 50.0000 50.0000 15.0000 20.0000 22.0000\n"
    "4 104.0000 20.0000 0.0000 40.0000 25.0000 3.0000\n")
IN_RANGE = _ti1(
    "1 100.0000 100.0000 100.0000 95.0500 100.0000 108.9000\n"
    "2 0.0000 0.0000 0.0000 0.9505 1.0000 1.0890\n"
    "3 0.0000 50.0000 50.0000 15.0000 20.0000 22.0000\n"
    "4 100.0000 20.0000 0.0000 40.0000 25.0000 3.0000\n")


# --- the pure clamp ----------------------------------------------------------

def test_the_run_copy_is_clamped_and_names_both_values():
    text, changes = D.clamp_text(OUT_OF_RANGE)
    assert [(c.sample_id, c.channel, c.old_text, c.new) for c in changes] == [
        ("3", "R", "-23.1373", 0.0), ("4", "R", "104.0000", 100.0)]
    # Only the two numbers changed, each keeping its four decimals.
    assert text == IN_RANGE


def test_an_in_range_file_comes_back_byte_for_byte():
    data = IN_RANGE.encode("utf-8")
    out, changes = D.clamp_bytes(data)
    assert changes == [] and out is data


def test_the_warning_lists_each_patch_with_a_real_minus_sign():
    title, body = D.warning(D.clamp_text(OUT_OF_RANGE)[1], "jctay.ti1")
    assert title == "Some values in this patch set were outside 0 to 100"
    assert "Patch 3: red −23.1373 → 0" in body
    assert "Patch 4: red 104.0000 → 100" in body
    assert "2 values in jctay.ti1" in body
    assert "—" not in title + body      # no em dash


def test_a_ti2_names_the_location_too():
    ti2 = ("CTI2\n\nCOLOR_REP \"RGB\"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
           "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
           "END_DATA_FORMAT\n\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
           "13 C1 -23.14 50.00 50.00 15.0 20.0 22.0\nEND_DATA\n")
    text, changes = D.clamp_text(ti2)
    assert "13 C1 0.00 50.00 50.00" in text
    assert D.change_line(changes[0]) == "Patch 13 (C1): red −23.14 → 0"
    title, body = D.warning(changes, "c.ti2")
    assert title == "A value in this patch set was outside 0 to 100"
    assert "one value in c.ti2" in body


def test_cmyk_names_the_ink():
    t = ("CTI1\nCOLOR_REP \"CMYK\"\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
         "SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K\nEND_DATA_FORMAT\n"
         "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 0 0 101.5 -2\nEND_DATA\n")
    _text, changes = D.clamp_text(t)
    assert [D.change_line(c) for c in changes] == [
        "Patch 1: yellow 101.5 → 100", "Patch 1: black −2 → 0"]


# --- the build: the run's copy, never the person's file ---------------------

class _NoRunner:
    """Nothing is laid out; the copy is all this test looks at."""
    def run(self, tool, args, cwd, on_line=None, on_finish=None):
        pass


class _FM:
    def __init__(self, root: Path) -> None:
        self.root, self._project = root, None

    def project(self):
        from core.file_manager import Project
        if self._project is None:
            self._project = Project.create_or_load(self.root, self.root.name)
        return self._project

    def ensure_folder(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def clean_folder(self, exts):
        pass

    def cwd_for_chart(self, *, cal_target: bool) -> Path:
        return self.project().current_run().ensure_dir()

    def chart_stem(self, *, cal_target: bool) -> str:
        return self.project().current_run().stem


class _Settings:
    def __init__(self, engine: bool = False) -> None:
        self.engine = engine

    def get(self, key, default=None):
        if key == "use_chromiq_layout_engine":
            return self.engine
        return default


def _creator(root: Path, runner=None):
    from workflow.chart_creator import ChartCreator
    return ChartCreator(runner or _NoRunner(), _FM(root), _Settings())


def test_the_build_clamps_the_run_copy_and_leaves_the_file_alone(tmp_path):
    from workflow.chart_creator import ChartParams
    src = tmp_path / "jctay.ti1"
    src.write_text(OUT_OF_RANGE, encoding="utf-8")
    before = src.read_bytes()
    c = _creator(tmp_path / "proj")
    lines = []
    c.load_ti1_and_generate_preview(
        src, ChartParams(instrument="i1", paper="A4", is_manual=True),
        on_line=lines.append, on_finish=lambda _t: None)
    run = c._file_mgr.project().current_run()
    assert run.chart_ti1.read_text(encoding="utf-8") == IN_RANGE
    assert src.read_bytes() == before
    assert len(c.last_clamped) == 2
    assert any("your own file is unchanged" in l for l in lines)


def test_an_in_range_build_copies_the_file_byte_for_byte(tmp_path):
    from workflow.chart_creator import ChartParams
    src = tmp_path / "fine.ti1"
    src.write_text(IN_RANGE, encoding="utf-8")
    c = _creator(tmp_path / "proj")
    lines = []
    c.load_ti1_and_generate_preview(
        src, ChartParams(instrument="i1", paper="A4", is_manual=True),
        on_line=lines.append, on_finish=lambda _t: None)
    assert c._file_mgr.project().current_run().chart_ti1.read_bytes() \
        == src.read_bytes()
    assert c.last_clamped == [] and not any("0 to 100" in l for l in lines)


def test_a_redraw_of_a_run_chart_keeps_its_values(tmp_path):
    """Restore Used Chart redraws the pages of the chart a run already holds,
    and must not change a value in it."""
    from workflow.chart_creator import ChartParams
    src = tmp_path / "old.ti1"
    src.write_text(OUT_OF_RANGE, encoding="utf-8")
    c = _creator(tmp_path / "proj")
    c.load_ti1_and_generate_preview(
        src, ChartParams(instrument="i1", paper="A4", is_manual=True),
        on_line=lambda _l: None, on_finish=lambda _t: None,
        keep_results=True, clamp_device_values=False)
    assert c._file_mgr.project().current_run().chart_ti1.read_text(
        encoding="utf-8") == OUT_OF_RANGE


# --- exports -----------------------------------------------------------------

def test_the_exports_of_the_run_copy_show_0_and_100(tmp_path):
    from workflow.i1profiler_export import export_from_ti1
    run_copy = tmp_path / "chart.ti1"
    run_copy.write_text(D.clamp_text(OUT_OF_RANGE)[0], encoding="utf-8")
    txt, pxf = export_from_ti1(run_copy, tmp_path / "out")
    rows = txt.read_text(encoding="utf-8").splitlines()
    assert "3 0.0000 128.0000 128.0000 " in rows
    assert "4 255.0000 51.0000 0.0000 " in rows
    assert "-" not in "".join(r for r in rows if r[:1].isdigit())


# --- a run that already holds such a chart: the comparisons (§I.16) ---------

def _ti2_with(value: str, path: Path) -> Path:
    path.write_text(
        "CTI2\n\nCOLOR_REP \"RGB\"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 4\nBEGIN_DATA\n"
        "1 A1 100.0000 100.0000 100.0000 95.05 100.0 108.9\n"
        "2 A2 0.0000 0.0000 0.0000 0.95 1.0 1.09\n"
        f"3 A3 {value} 50.0000 50.0000 15.0 20.0 22.0\n"
        "4 A4 104.0000 20.0000 0.0000 40.0 25.0 3.0\nEND_DATA\n",
        encoding="utf-8")
    return path


class _Measured:
    def __init__(self, rgb, ids=("1", "2", "3", "4")):
        import numpy as np
        self.rgb = np.asarray(rgb, dtype=float)
        self.sample_ids = list(ids)
        self.has_device = True


@pytest.mark.parametrize("reading", [
    # i1Profiler: 0..255, printed and exported as 0 and 255
    [[255, 255, 255], [0, 0, 0], [0, 128, 128], [255, 51, 0]],
    # a reading of the clamped run copy, on 0..100
    [[100, 100, 100], [0, 0, 0], [0, 50, 50], [100, 20, 0]],
    # ChromIQ's own reading of the old chart repeats its values
    [[100, 100, 100], [0, 0, 0], [-23.1373, 50, 50], [104, 20, 0]],
])
def test_a_reading_of_0_matches_a_chart_value_of_minus_23(tmp_path, reading):
    from workflow.measurement_report import verify_patch_identity
    ti2 = _ti2_with("-23.1373", tmp_path / "old.ti2")
    v = verify_patch_identity(_Measured(reading), ti2)
    assert v["verdict"] == "verified", v


def test_a_really_different_patch_is_still_refused(tmp_path):
    from workflow.measurement_report import verify_patch_identity
    ti2 = _ti2_with("-23.1373", tmp_path / "old.ti2")
    v = verify_patch_identity(_Measured(
        [[100, 100, 100], [0, 0, 0], [30, 50, 50], [100, 20, 0]]), ti2)
    assert v["verdict"] == "mismatch" and v["mismatched"] == 1


def test_a_ti3_with_0_is_accepted_by_the_import(tmp_path):
    from workflow.measurement_import import assess
    ti2 = _ti2_with("-23.1373", tmp_path / "old.ti2")
    ti3 = tmp_path / "m.ti3"
    ti3.write_text(
        "CTI3\n\nCOLOR_REP \"RGB_XYZ\"\n\nNUMBER_OF_FIELDS 8\n"
        "BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y "
        "XYZ_Z\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 4\nBEGIN_DATA\n"
        "1 A1 100.0000 100.0000 100.0000 90.0 95.0 100.0\n"
        "2 A2 0.0000 0.0000 0.0000 1.0 1.0 1.0\n"
        "3 A3 0.0000 50.0000 50.0000 15.0 20.0 22.0\n"
        "4 A4 100.0000 20.0000 0.0000 40.0 25.0 3.0\nEND_DATA\n",
        encoding="utf-8")
    v = assess(ti3, ti2)
    assert v.ok, v.reason


# --- printtarg, layout engine off: 0, not 196 --------------------------------

ARGYLL = Path("/Applications/Argyll/bin")


class _SubprocessRunner:
    """Runs the real Argyll tool, synchronously, with a timeout."""
    def run(self, tool, args, cwd, on_line=None, on_finish=None):
        try:
            r = subprocess.run([str(ARGYLL / tool), *args], cwd=str(cwd),
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=180)
            rc = r.returncode
            for l in (r.stdout + r.stderr).splitlines():
                if on_line:
                    on_line(l)
        except subprocess.TimeoutExpired:
            pytest.fail(f"{tool} did not finish within 180 s")
        if on_finish:
            on_finish(rc)


@pytest.mark.skipif(not (ARGYLL / "printtarg").exists(),
                    reason="ArgyllCMS printtarg is not installed")
def test_printtarg_prints_0_not_196(tmp_path):
    import numpy as np
    from PIL import Image

    from workflow.chart_creator import ChartParams
    src = tmp_path / "jctay.ti1"
    src.write_text(OUT_OF_RANGE, encoding="utf-8")
    c = _creator(tmp_path / "proj", _SubprocessRunner())
    done = []
    c.load_ti1_and_generate_preview(
        src, ChartParams(instrument="i1", paper="A4", tiff_dpi=100, is_manual=True),
        on_line=lambda _l: None, on_finish=done.append)
    run = c._file_mgr.project().current_run()
    tifs = sorted(run.dir.glob("*.tif"))
    assert tifs, f"printtarg wrote no TIFF ({done})"
    colours = set()
    for t in tifs:
        a = np.asarray(Image.open(t).convert("RGB")).reshape(-1, 3)
        colours |= {tuple(x) for x in np.unique(a, axis=0).tolist()}
    assert (0, 128, 128) in colours          # patch 3 printed with no red
    # Without the clamp printtarg printed (196, 128, 128) and (10, 51, 0):
    # measured with Argyll 3.5 on this very fixture.
    assert (196, 128, 128) not in colours    # not wrapped round
    assert (255, 51, 0) in colours           # patch 4 at 100 %
    assert (10, 51, 0) not in colours
    ti2 = run.dir / f"{run.stem}.ti2"
    text = ti2.read_text(encoding="utf-8")
    assert "-23.1373" not in text and "104.0000" not in text


# --- the tab: Load patch set shows the warning, without blocking ------------

def test_load_patch_set_names_both_values_in_a_window_that_does_not_block(
        tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication

    import ui.tabs.tab_chart as tc
    import ui.ti2_loader as L
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController

    QApplication.instance() or QApplication([])
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", False)
    fm = FileManager(s)
    tab = tc.TabChart(ArgyllRunner(s), fm, s)
    tab.set_target_controller(MeasurementTargetController(fm))
    src = tmp_path / "jctay.ti1"
    src.write_text(OUT_OF_RANGE, encoding="utf-8")
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(src))
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda _s: "new")
    monkeypatch.setattr(L, "_ask_project_name",
                        lambda *a, **k: ("Jctay", False))
    built = []
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: built.append(a))
    try:
        tab._on_load_ti1()
        dlg = tab._clamped_note
        assert dlg is not None and dlg.isVisible() and not dlg.isModal()
        from PyQt6.QtWidgets import QLabel
        text = "\n".join(l.text() for l in dlg.findChildren(QLabel))
        assert "Patch 3: red −23.1373 → 0" in text
        assert "Patch 4: red 104.0000 → 100" in text
        assert built, "the chart is still built"
        assert src.read_text(encoding="utf-8") == OUT_OF_RANGE
    finally:
        if getattr(tab, "_clamped_note", None) is not None:
            tab._clamped_note.close()
        tab.deleteLater()


# --- review r1: nan, quoted values, lines that do not match (L6) ------------

def test_nan_and_inf_are_left_as_they_are():
    """"nan" compared false with everything and came out as 100."""
    t = OUT_OF_RANGE.replace("4 104.0000 20.0000", "4 nan 20.0000").replace(
        "2 0.0000 0.0000 0.0000", "2 inf 0.0000 0.0000")
    text, changes = D.clamp_text(t)
    assert [(c.sample_id, c.old_text) for c in changes] == [("3", "-23.1373")]
    assert "4 nan 20.0000" in text and "2 inf 0.0000" in text


def test_a_quoted_value_with_spaces_counts_as_one():
    t = ('CTI2\nCOLOR_REP "RGB"\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n'
         'SAMPLE_ID SAMPLE_NAME RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n'
         'NUMBER_OF_SETS 1\nBEGIN_DATA\n7 "Patch seven" -5 50 50\nEND_DATA\n')
    text, changes = D.clamp_text(t)
    assert '7 "Patch seven" 0 50 50' in text
    assert [(c.sample_id, c.channel, c.new) for c in changes] == [
        ("7", "R", 0.0)]


def test_a_line_that_does_not_match_its_format_is_refused_not_skipped():
    bad = OUT_OF_RANGE.replace("3 -23.1373 50.0000 50.0000 15.0000 20.0000 "
                               "22.0000", "3 -23.1373 50.0000 50.0000")
    with pytest.raises(D.UnreadablePatchLine) as caught:
        D.clamp_text(bad)
    msg = str(caught.value)
    assert "line has 4" in msg and "format names 7" in msg
    assert msg[:1].islower() and not msg.endswith(".")


def _real_tab(tmp_path):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    import ui.tabs.tab_chart as tc
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    QApplication.instance() or QApplication([])
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", False)
    fm = FileManager(s)
    tab = tc.TabChart(ArgyllRunner(s), fm, s)
    tab.set_target_controller(MeasurementTargetController(fm))
    return tab, fm


def test_load_patch_set_refuses_a_line_that_does_not_match(
        tmp_path, monkeypatch):
    import ui.tabs.tab_chart as tc
    tab, fm = _real_tab(tmp_path)
    src = tmp_path / "broken.ti1"
    src.write_text(OUT_OF_RANGE.replace(
        "4 104.0000 20.0000 0.0000 40.0000 25.0000 3.0000",
        "4 104.0000 20.0000 0.0000"), encoding="utf-8")
    before = src.read_bytes()
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(src))
    asked, built, shown = [], [], []
    monkeypatch.setattr(tab, "_ti1_load_destination",
                        lambda _s: asked.append(1) or "new")
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: built.append(a))
    monkeypatch.setattr(tc.InfoDialog, "exec",
                        lambda self: shown.append(self.windowTitle()) or 0)
    try:
        tab._on_load_ti1()
        assert shown == ["Couldn't read that patch set"]
        assert not asked and not built
        assert tab._preset_ti1_path is None
        assert src.read_bytes() == before
    finally:
        tab.deleteLater()


# --- review r1 L5: a .ti1 preset gets the same window -----------------------

def test_a_ti1_preset_with_values_outside_gets_the_window(
        tmp_path, monkeypatch):
    tab, fm = _real_tab(tmp_path)
    src = tmp_path / "preset.ti1"
    src.write_text(OUT_OF_RANGE, encoding="utf-8")
    fm.start_new_project("Preset-Test")
    tab._update_name_fields()
    built = []
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: built.append(a))
    try:
        assert tab._generate_from_ti1(src, ask=False) is True
        dlg = tab._clamped_note
        assert dlg is not None and dlg.isVisible() and not dlg.isModal()
        assert built
        # …and never for the live preview, which re-lays out on every knob.
        dlg.close()
        tab._clamped_note = None
        tab._generate_from_ti1(src, ask=False, preview=True)
        assert tab._clamped_note is None
    finally:
        if getattr(tab, "_clamped_note", None) is not None:
            tab._clamped_note.close()
        tab.deleteLater()


# --- review r2: forms ArgyllCMS accepts, from real targen output ------------

def _argyll(tool, args, cwd):
    return subprocess.run([str(ARGYLL / tool), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)


@pytest.fixture
def targen_ti1(tmp_path):
    if not (ARGYLL / "targen").exists() or not (ARGYLL / "printtarg").exists():
        pytest.skip("ArgyllCMS targen/printtarg is not installed")
    r = _argyll("targen", ["-v0", "-d2", "-G", "-f30", "real"], tmp_path)
    if r.returncode != 0:
        pytest.fail(f"targen did not make a patch set: {r.stderr[-400:]}")
    return (tmp_path / "real.ti1").read_text(encoding="utf-8")


def _first_block(text):
    lines = text.splitlines(keepends=True)
    b = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    e = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    return lines, b, e


def _with_comments(text):
    lines, b, e = _first_block(text)
    rows = lines[b + 1:e]
    rows = (["# a comment line inside the data\n"]
            + [rows[0].rstrip("\n") + "   # a comment after the values\n"]
            + rows[1:])
    return "".join(lines[:b + 1] + rows + lines[e:])


def _split_patch(text):
    lines, b, e = _first_block(text)
    rows = lines[b + 1:e]
    vals = rows[2].split()
    rows[2] = " ".join(vals[:3]) + "\n" + " ".join(vals[3:]) + "\n"
    return "".join(lines[:b + 1] + rows + lines[e:])


def _negative_red_in_patch_3(text):
    lines, b, e = _first_block(text)
    vals = lines[b + 3].split()
    vals[1] = "-23.1373"
    lines[b + 3] = " ".join(vals) + "\n"
    return "".join(lines)


@pytest.mark.parametrize("form", [_with_comments, _split_patch])
def test_forms_argyll_accepts_are_loaded_and_clamped(tmp_path, targen_ti1,
                                                     form):
    in_range = form(targen_ti1)
    # printtarg accepts the form itself …
    (tmp_path / "form.ti1").write_text(in_range, encoding="utf-8")
    assert _argyll("printtarg", ["-ii1", "-pA4", "-T72", "form"],
                   tmp_path).returncode == 0
    # … ChromIQ reads it and changes nothing when nothing is out of range …
    same, none = D.clamp_text(in_range)
    assert same == in_range and none == []
    # … and clamps it when a value is out of range.
    out = form(_negative_red_in_patch_3(targen_ti1))
    text, changes = D.clamp_text(out)
    assert [(c.sample_id, c.channel, c.new) for c in changes] == [
        ("3", "R", 0.0)]
    (tmp_path / "clamped.ti1").write_text(text, encoding="utf-8")
    assert _argyll("printtarg", ["-ii1", "-pA4", "-T72", "clamped"],
                   tmp_path).returncode == 0
    assert "-23.1373" not in text


def test_comments_are_kept_and_never_read_as_values():
    t = OUT_OF_RANGE.replace(
        "4 104.0000 20.0000 0.0000 40.0000 25.0000 3.0000",
        "4 104.0000 20.0000 0.0000 40.0000 25.0000 3.0000 # was -5 \"x\"")
    text, changes = D.clamp_text(t)
    assert "4 100.0000 20.0000 0.0000 40.0000 25.0000 3.0000 # was -5" in text
    assert [c.sample_id for c in changes] == ["3", "4"]


def test_a_split_patch_with_nothing_to_clamp_keeps_its_lines():
    lines = IN_RANGE.splitlines(keepends=True)
    i = lines.index("3 0.0000 50.0000 50.0000 15.0000 20.0000 22.0000\n")
    lines[i] = "3 0.0000 50.0000\n50.0000 15.0000 20.0000 22.0000\n"
    t = "".join(lines)
    assert D.clamp_text(t) == (t, [])


def test_only_the_patch_table_is_clamped_never_a_calibration_curve():
    """A printtarg/printcal .ti2 may carry a calibration-curve table, where
    values above 100 are legitimate."""
    ti2 = ('CTI2\n\nCOLOR_REP "CMYK_XYZ"\n\nNUMBER_OF_FIELDS 6\n'
           "BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC CMYK_C CMYK_M CMYK_Y "
           "CMYK_K\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
           '1 "A1" 104 0 0 0\nEND_DATA\nCAL\n\nKEYWORD "DEVICE_CLASS"\n'
           'COLOR_REP "CMYK"\n\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n'
           "CMYK_I CMYK_C CMYK_M CMYK_Y CMYK_K\nEND_DATA_FORMAT\n\n"
           "NUMBER_OF_SETS 2\nBEGIN_DATA\n0 0 0 0 0\n100 104.5 101 100 "
           "120\nEND_DATA\n")
    text, changes = D.clamp_text(ti2)
    assert [(c.sample_id, c.channel) for c in changes] == [("1", "C")]
    assert "100 104.5 101 100 120\n" in text
