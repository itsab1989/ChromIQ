"""#209: every path to an ArgyllCMS tool carries the platform's suffix.

A Windows 10 user on 4.3.4 imported an i1Profiler ``.txt`` on the Measure
tab's Import tab and was told *ChromIQ needs the ArgyllCMS tool "txt2ti3" to
convert this file, but couldn't find it*, while Tools > Convert i1Profiler
converted the same file with the same Argyll. The Tools dialog goes through
``ArgyllRunner``, which asks ``argyll_binary`` for ``txt2ti3.exe``;
``workflow/reference_convert._run`` built ``bin / "txt2ti3"``, a file that does
not exist on Windows, and refused at its ``.exists()`` check.

This file proves it on macOS by SIMULATING Windows: ``core.resource_path``
is told the platform is ``win32`` and the ArgyllCMS folder holds only
``<tool>.exe`` files, exactly what a Windows install holds. Only the naming is
simulated. The tools themselves are stood in for by a fake runner that checks
it was handed a file that exists, and writes what the real tool would.

And a source scan, so the next ``bin_dir / "colprof"`` fails the suite on
the Mac it was written on instead of on a user's Windows machine.
"""
from __future__ import annotations

import ast
import subprocess
import types
from pathlib import Path

import pytest

import core.resource_path as rp
from core.resource_path import argyll_tool_path

ROOT = Path(__file__).resolve().parent.parent

#: ArgyllCMS 3.5's bin folder, every tool in it.
ARGYLL_TOOLS = frozenset("""
applycal average cb2ti3 cctiff ccxxmake chartread collink colprof colverify
cxf2ti3 dispcal dispread dispwin extracticc extractttag fakeCMY fakeread
greytiff iccdump iccgamut icclu iccvcgt illumread invprofcheck jam kodak2ti3
ls2ti3 mppcheck mpplu mppprof oeminst printcal printtarg profcheck refine
revfix scanin spec2cie specplot splitti3 spotread synthcal synthread targen
tiffgamut timage txt2ti3 viewgam xicclu
""".split())


# --------------------------------------------------------------------------
# the simulated Windows install
# --------------------------------------------------------------------------

@pytest.fixture
def windows(monkeypatch, tmp_path):
    """``sys.platform`` reads ``win32`` inside ``core.resource_path`` only, and
    the ArgyllCMS folder holds nothing but ``<tool>.exe``."""
    monkeypatch.setattr(rp, "sys", types.SimpleNamespace(platform="win32"))
    bin_dir = tmp_path / "Argyll_V3.5.0" / "bin"
    bin_dir.mkdir(parents=True)
    for tool in ARGYLL_TOOLS:
        (bin_dir / f"{tool}.exe").write_bytes(b"MZ")
    return bin_dir


_SPECTRAL_ONLY_TI3 = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
ORIGINATOR "Argyll txt2ti3"
DEVICE_CLASS "OUTPUT"
COLOR_REP "iRGB_XYZ"
SPECTRAL_BANDS "3"
SPECTRAL_START_NM "380.000000"
SPECTRAL_END_NM "730.000000"
SPECTRAL_NORM "100.000000"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B SPEC_380 SPEC_555 SPEC_730
END_DATA_FORMAT

NUMBER_OF_SETS 2
BEGIN_DATA
1 100.0 100.0 100.0 88.0 89.0 87.0
2 0.0 0.0 0.0 2.0 2.1 2.2
END_DATA
"""

_WITH_XYZ_TI3 = _SPECTRAL_ONLY_TI3.replace(
    "NUMBER_OF_FIELDS 7", "NUMBER_OF_FIELDS 10").replace(
    "SPEC_380 SPEC_555 SPEC_730",
    "SPEC_380 SPEC_555 SPEC_730 XYZ_X XYZ_Y XYZ_Z").replace(
    "88.0 89.0 87.0", "88.0 89.0 87.0 87.2 88.5 86.9").replace(
    "2.0 2.1 2.2", "2.0 2.1 2.2 2.0 2.1 2.2")


class FakeArgyll:
    """Stands in for ``subprocess.run``: refuses a tool path that does not
    exist (as Windows would), and writes what the real tool writes."""

    def __init__(self) -> None:
        self.ran: list[str] = []

    def __call__(self, cmd, **kw):
        exe = Path(str(cmd[0]))
        assert exe.is_file(), f"asked to run {exe}, which is not there"
        self.ran.append(exe.name)
        tool, args = exe.stem, [str(a) for a in cmd[1:]]
        if tool in ("txt2ti3", "cxf2ti3"):
            body = _SPECTRAL_ONLY_TI3 if tool == "txt2ti3" else _WITH_XYZ_TI3
            Path(args[-1] + ".ti3").write_text(body, encoding="utf-8")
        elif tool == "spec2cie":
            Path(args[-1]).write_text(_WITH_XYZ_TI3, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")


@pytest.fixture
def fake_argyll(monkeypatch):
    fake = FakeArgyll()
    import workflow.reference_convert as rc
    real = rc.run_text
    monkeypatch.setattr(rc, "run_text",
                        lambda cmd, runner=None, **kw: real(cmd, runner=fake,
                                                            **kw))
    return fake


def _i1profiler_txt(tmp_path: Path) -> Path:
    src = tmp_path / "from i1Profiler" / "полны.txt"
    src.parent.mkdir(parents=True)
    src.write_text('CGATS.17\nORIGINATOR "X-Rite i1Profiler"\n'
                   "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
                   "SampleID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
                   "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 255 255 255\nEND_DATA\n",
                   encoding="utf-8")
    return src


# --------------------------------------------------------------------------
# the helper
# --------------------------------------------------------------------------

def test_the_helper_names_the_exe_on_windows(windows):
    assert argyll_tool_path(windows, "txt2ti3") == windows / "txt2ti3.exe"
    assert argyll_tool_path(str(windows), "spec2cie").is_file()


def test_the_helper_names_the_bare_tool_elsewhere(monkeypatch, tmp_path):
    monkeypatch.setattr(rp, "sys", types.SimpleNamespace(platform="darwin"))
    assert argyll_tool_path(tmp_path, "txt2ti3") == tmp_path / "txt2ti3"


# --------------------------------------------------------------------------
# the converter #209 broke, every road into it
# --------------------------------------------------------------------------

def test_an_i1profiler_txt_converts_on_windows(windows, fake_argyll, tmp_path):
    """The exact failure of #209: txt2ti3 is found, and so is spec2cie, which
    the CIE repair runs on a spectral-only export like the reporter's."""
    from workflow.reference_convert import convert_i1profiler_measurement
    out = convert_i1profiler_measurement(_i1profiler_txt(tmp_path), windows,
                                         tmp_path / "out")
    assert out.is_file()
    assert fake_argyll.ran == ["txt2ti3.exe", "spec2cie.exe"]
    assert "XYZ_X" in out.read_text(encoding="utf-8")


def test_the_cie_repair_finds_spec2cie_on_windows(windows, fake_argyll,
                                                 tmp_path):
    """The Build Profile tab and Tools > Convert run txt2ti3 through
    ArgyllRunner and then this repair; before #209's fix it failed in silence
    on Windows and left the file without CIE columns."""
    from workflow.reference_convert import repair_converted_cie
    ti3 = tmp_path / "m.ti3"
    ti3.write_text(_SPECTRAL_ONLY_TI3, encoding="utf-8")
    assert repair_converted_cie(ti3, windows)
    assert fake_argyll.ran == ["spec2cie.exe"]
    assert "XYZ_X" in ti3.read_text(encoding="utf-8")


@pytest.mark.parametrize("name, ran", [
    ("ref.txt", ["txt2ti3.exe", "spec2cie.exe"]),
    ("ref.cxf", ["cxf2ti3.exe"]),
])
def test_a_scanner_reference_converts_on_windows(windows, fake_argyll,
                                                 tmp_path, name, ran):
    from workflow.reference_convert import convert_reference
    src = tmp_path / name
    src.write_text("SPECTRAL 380\n" if name.endswith(".txt") else "<cc:CxF/>",
                   encoding="utf-8")
    out = convert_reference(src, windows, tmp_path / "out")
    assert out.is_file()
    assert fake_argyll.ran == ran


def _a_stub_measure_tab(windows, tmp_path):
    said: list = []
    log = types.SimpleNamespace(appendPlainText=lambda *_: None,
                                ensureCursorVisible=lambda: None)
    tab = types.SimpleNamespace(
        _settings={"argyll_bin_path": str(windows)},
        _log=log,
        _say_on_screen=lambda title, body: said.append((title, body)))
    cache = tmp_path / "run" / "cache"
    run = types.SimpleNamespace(
        ensure_cache_dir=lambda: (cache.mkdir(parents=True, exist_ok=True)
                                  or cache))
    return tab, run, said


def test_the_measure_tab_import_converts_on_windows(windows, fake_argyll,
                                                    tmp_path):
    """Both of the Measure tab's import doors (a profiling run and a
    verification) convert through this one method, and a calibration run has
    no import door (§I.9), so this is every Measure tab import."""
    from ui.tabs.tab_measure import TabMeasure
    tab, run, said = _a_stub_measure_tab(windows, tmp_path)
    got = TabMeasure._convert_import_file(tab, run, _i1profiler_txt(tmp_path))
    assert said == [], said
    assert got is not None and got.is_file()
    assert fake_argyll.ran == ["txt2ti3.exe", "spec2cie.exe"]


def test_before_the_fix_the_measure_tab_said_what_the_reporter_saw(
        monkeypatch, windows, fake_argyll, tmp_path):
    """The stub is honest: given a folder WITHOUT the suffix, the same method
    shows the #209 window, so the test above is not passing by accident."""
    monkeypatch.setattr(rp, "argyll_binary", lambda name: name)
    from ui.tabs.tab_measure import TabMeasure
    tab, run, said = _a_stub_measure_tab(windows, tmp_path)
    got = TabMeasure._convert_import_file(tab, run, _i1profiler_txt(tmp_path))
    assert got is None
    assert len(said) == 1 and "txt2ti3" in said[0][1]
    assert "couldn't find it" in said[0][1]


def test_the_report_window_and_build_profile_take_the_same_converter():
    """The Measurement Report's batch adder, the Build Profile tab's import
    and the scanner chart dialog convert an i1Profiler file through the same
    `convert_i1profiler_measurement`, handed the configured ArgyllCMS folder,
    so the test above covers them as well."""
    for rel in ("ui/dialogs/measurement_report_dialog.py",
                "ui/tabs/tab_profile.py", "ui/tabs/tab_measure.py",
                "ui/dialogs/scanin_target_dialog.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "convert_i1profiler_measurement(" in src, rel


# --------------------------------------------------------------------------
# the other places that looked for a tool themselves
# --------------------------------------------------------------------------

def test_argyll_runner_resolves_the_exe_on_windows(windows):
    from core.argyll_runner import ArgyllRunner
    runner = types.SimpleNamespace(
        _settings={"argyll_bin_path": str(windows)})
    assert ArgyllRunner._resolve(runner, "txt2ti3") == windows / "txt2ti3.exe"


def test_average_is_found_on_windows(windows):
    from workflow.ti3_merge import _resolve_average
    assert _resolve_average(windows) == str(windows / "average.exe")


def test_the_layout_round_trip_finds_its_tools_on_windows(windows):
    from workflow.layout_engine.preflight import _bin, roundtrip_available
    assert _bin("fakeread", str(windows)) == str(windows / "fakeread.exe")
    assert roundtrip_available(str(windows))


def test_the_issue_report_reads_the_version_on_windows(windows, monkeypatch):
    import core.issue_report as ir
    asked: list = []

    def fake(cmd, **kw):
        asked.append(Path(cmd[0]).name)
        return subprocess.CompletedProcess(cmd, 1, "", "Version 3.5.0")
    monkeypatch.setattr(ir, "run_text", fake)
    assert "3.5.0" in ir.detect_argyll_version(windows)
    assert asked == ["targen.exe"]


class _Ran(Exception):
    pass


def _stop_at_the_run(monkeypatch, module):
    ran: list = []

    def fake(cmd, **kw):
        ran.append(Path(str(cmd[0])).name)
        raise _Ran()
    monkeypatch.setattr(module, "run_text", fake)
    return ran


def test_the_n_channel_check_finds_icclu_and_spec2cie_on_windows(
        windows, monkeypatch, tmp_path):
    import numpy as np
    import workflow.profcheck_nchannel as pn
    ran = _stop_at_the_run(monkeypatch, pn)
    with pytest.raises(_Ran):
        pn._icclu_forward(tmp_path / "x.icc", windows, np.zeros((1, 6)), "r")
    ti3 = tmp_path / "s.ti3"
    ti3.write_text(_SPECTRAL_ONLY_TI3, encoding="utf-8")
    with pytest.raises(_Ran):
        pn._recompute_spectral_xyz(ti3, windows, illum="D50", observer="1931_2",
                                   fwa=False, fwa_illum="")
    assert ran == ["icclu.exe", "spec2cie.exe"]


def test_the_gamut_port_finds_iccgamut_on_windows(windows, monkeypatch,
                                                  tmp_path):
    import workflow.profile_engine.gammap_port.wire as wire
    ran = _stop_at_the_run(monkeypatch, wire)
    icc = tmp_path / "src.icc"
    icc.write_bytes(b"")
    with pytest.raises(_Ran):
        wire.source_gam_jab(icc, windows)
    with pytest.raises(_Ran):
        wire._iccgamut_to(tmp_path / "o.gam", icc, windows, 10.0)
    assert ran == ["iccgamut.exe", "iccgamut.exe"]


def test_relayout_runs_the_exe_on_windows(windows, monkeypatch):
    import workflow.ti2_relayout as tr
    ran = _stop_at_the_run(monkeypatch, tr)
    with pytest.raises(_Ran):
        tr.seed_from_targen(windows, 10)
    assert ran == ["targen.exe"]


# --------------------------------------------------------------------------
# the source scan
# --------------------------------------------------------------------------

def _app_sources():
    for top in ("core", "workflow", "ui"):
        yield from sorted((ROOT / top).rglob("*.py"))
    yield ROOT / "main.py"


def _names_a_folder(node: ast.AST) -> bool:
    text = ast.unparse(node).lower()
    return "bin" in text or "argyll" in text


def _is_the_suffix_helper(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call)
            and ast.unparse(node.func).split(".")[-1] == "argyll_binary")


def _offences(tree: ast.AST) -> list[tuple[int, str]]:
    bad = []
    for node in ast.walk(tree):
        # <anything> / "txt2ti3"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            right = node.right
            if (isinstance(right, ast.Constant)
                    and isinstance(right.value, str)
                    and right.value in ARGYLL_TOOLS):
                bad.append((node.lineno, ast.unparse(node)))
            # <the bin folder> / tool   (a variable, without the helper)
            elif (isinstance(right, (ast.Name, ast.Attribute))
                  and _names_a_folder(node.left)
                  and not _is_the_suffix_helper(right)):
                bad.append((node.lineno, ast.unparse(node)))
        # os.path.join(bin_dir, "txt2ti3") and Path(bin_dir, "txt2ti3")
        if isinstance(node, ast.Call) and ast.unparse(node.func) in (
                "os.path.join", "Path", "pathlib.Path"):
            if any(isinstance(a, ast.Constant) and a.value in ARGYLL_TOOLS
                   for a in node.args[1:]):
                bad.append((node.lineno, ast.unparse(node)))
        # f"{bin_dir}/txt2ti3"
        if isinstance(node, ast.JoinedStr):
            lit = "".join(v.value for v in node.values
                          if isinstance(v, ast.Constant))
            if any(f"/{t}" in lit or f"\\{t}" in lit for t in ARGYLL_TOOLS) \
                    and any(isinstance(v, ast.FormattedValue)
                            and _names_a_folder(v.value)
                            for v in node.values):
                bad.append((node.lineno, ast.unparse(node)))
    return bad


#: Folder joins the scan would flag that are not tool paths. Each one is read
#: and named, never a pattern.
_NOT_A_TOOL = {
    # a folder beside bin/, not a program in it
    ("ui/gamut_panel.py", "Path(argyll_bin).parent / 'ref'"),
}


def test_no_code_builds_an_argyll_tool_path_without_the_helper():
    found = []
    for path in _app_sources():
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for line, expr in _offences(tree):
            if (rel, expr) not in _NOT_A_TOOL:
                found.append(f"{rel}:{line}: {expr}")
    assert not found, (
        "These build a path to an ArgyllCMS tool by hand, which names a file "
        "that does not exist on Windows (#209). Use "
        "core.resource_path.argyll_tool_path(bin_dir, tool):\n  "
        + "\n  ".join(found))


def test_the_scan_catches_what_209_was():
    """The scan is not vacuous: each shape the bug can take is caught."""
    for src in ('exe = argyll_bin / tool',
                'exe = Path(bin_dir) / "txt2ti3"',
                'p = os.path.join(bin_dir, "spec2cie")',
                'p = f"{bin_dir}/colprof"'):
        assert _offences(ast.parse(src)), src
    for src in ('exe = argyll_tool_path(argyll_bin, tool)',
                'exe = bin_dir / argyll_binary("txt2ti3")',
                'ref = Path(bin_path).parent / "ref"'):
        assert not _offences(ast.parse(src)), src
