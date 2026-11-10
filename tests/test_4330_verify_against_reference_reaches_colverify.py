"""Tools > Verify against reference reaches colverify, with every kind of reference.

Two faults found on 2026-11-11 by driving 4.3.29 on screen (report folder
``2026-11-11_jctay``, shots 05 and 06):

1. **Pasted values failed unless "Create a 3D difference map" was ticked.**
   colverify said ``Unable to open file '<stem>-reference.ti3'``. Since
   ``c56c1061c`` (4.3.3-beta.3, W review) the reference is always written into
   the tool's staging folder, while colverify ran in the MEASUREMENT's folder
   and was handed the reference by bare name (``ColverifyRunner._build_args``,
   ``ref_ti3.name``, since ``d93e41025``). Only the 3D-map run, which copies the
   measurement into the staging folder too, had both files in colverify's
   working folder. The W-review test replaced colverify by a stub, so nothing
   ever ran the real tool with the real paths.

2. **"Load from file…" refused a measurement (.ti3) as the reference**, with
   ``Line 1 doesn't have three numbers: 'CTI3'``, although the help promises "a
   reference measurement file" and the file filter offers ``*.ti3``: the
   loaded file went into the paste box, whose parser reads number triples
   only (since ``d93e41025``, 3.8.0-beta.24).

So these tests run the REAL colverify, through the real dialog, from folders
whose names carry spaces and non-ASCII letters, with and without the 3D map,
and with a .ti3 reference that holds the same chart (including a
spectral-only one) or a different one, which must be refused before colverify
is asked, because colverify pairs patches by SAMPLE_ID and would otherwise
print numbers for pairs of different colours.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.resource_path import argyll_binary  # noqa: E402
from tests.argyll_env import argyll_tool  # noqa: E402
from tests.test_profile_tools import _Settings  # noqa: E402
from workflow.colverify_runner import (  # noqa: E402
    ColverifyParams,
    ColverifyRunner,
    write_reference_ti3,
)

COLVERIFY = argyll_tool("colverify") or shutil.which(argyll_binary("colverify"))
needs_colverify = pytest.mark.skipif(
    not COLVERIFY, reason="colverify binary not available")

REAL_TI3 = (Path(__file__).resolve().parent / "data"
            / "g_basti_et8550_run1_verify"
            / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti3")

#: Folder names colverify must be able to work from.
ODD_DIRS = ["plain", "with space", "Grüße ø 日本 x"]

LAB_ROWS = [(95.0, 0.5, -2.0), (50.0, 10.0, -20.0), (20.0, -5.0, 8.0),
            (70.0, 30.0, 40.0)]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _SyncRunner:
    """Stands in for ArgyllRunner: runs the REAL tool synchronously, in the
    working folder it is given, and records what it was asked."""

    is_running = False

    def __init__(self) -> None:
        self.calls: "list[tuple[str, list[str], Path]]" = []

    def run(self, tool, args, cwd, on_line=None, on_finish=None, **_kw):
        self.calls.append((tool, list(args), Path(cwd)))
        try:
            p = subprocess.run(
                [COLVERIFY, *args], cwd=str(cwd), capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=240)
        except subprocess.TimeoutExpired:
            pytest.fail(f"colverify did not finish within 240 s: {args}")
        for ln in (p.stdout + p.stderr).splitlines():
            if on_line is not None:
                on_line(ln)
        if on_finish is not None:
            on_finish(p.returncode)


def _measured_lab(folder: Path) -> Path:
    """A small RGB+Lab measurement, SAMPLE_ID 1..N, in *folder*."""
    folder.mkdir(parents=True, exist_ok=True)
    return write_reference_ti3(
        folder / "Chart ü.ti3", LAB_ROWS, space="LAB",
        rgb=[(100, 100, 100), (20, 40, 80), (0, 0, 0), (80, 50, 10)])


def _paste(rows) -> str:
    return "\n".join(f"{a} {b} {c}" for a, b, c in rows) + "\n"


def _dialog(runner, monkeypatch, *, plot_stub=None):
    import ui.dialogs.tools_dialogs as td
    monkeypatch.setattr(td, "webengine_available", lambda: True)
    shown = []

    class _Plot:
        def __init__(self, html, *_a, **_k):
            shown.append(Path(html))

        def exec(self):
            return 0

    monkeypatch.setattr(td, "DriftPlotDialog", plot_stub or _Plot)
    dlg = td.VerifyAgainstReferenceDialog(runner, _Settings())
    dlg._shown_plots = shown
    return dlg


def _log(dlg) -> str:
    return dlg._log.toPlainText()


# --- 1. the arguments: every file colverify is given can be opened ---------

@pytest.mark.parametrize("vrml", [False, True])
def test_every_file_argument_opens_from_colverifys_working_folder(
        tmp_path, vrml):
    """Reference in one folder, measurement in another, profile in a third:
    each file argument, read from the folder colverify runs in, is the file."""
    ref = tmp_path / "staging" / "Chart ü-reference.ti3"
    meas = tmp_path / "run folder" / "Chart ü.ti3"
    prof = tmp_path / "Profile ø" / "matte paper.icc"
    for p in (ref, meas, prof):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    cv = ColverifyRunner(_SyncRunner())
    recorded = []
    cv._runner = type("R", (), {
        "run": lambda self, tool, args, cwd, **k: recorded.append(
            (list(args), Path(cwd)))})()
    params = ColverifyParams(ref_ti3=ref, measured_ti3=meas,
                             gamut_profile=prof, vrml=vrml)
    cv.run(params, lambda _l: None, lambda _c: None)
    (args, cwd), = recorded
    files = args[-2:]
    assert (cwd / files[0]).resolve() == ref.resolve(), (args, cwd)
    # relative, so the folders both share (on Windows perhaps a user name
    # the ANSI code page cannot hold) are not in it
    assert not os.path.isabs(files[0]), files[0]
    assert str(tmp_path.resolve()) not in files[0]
    assert (cwd / files[1]).resolve() == meas.resolve(), (args, cwd)
    assert (cwd / args[args.index("-L") + 1]).resolve() == prof.resolve()
    # -w writes <measured stem>.x3d.html into the working folder; the dialog
    # looks for it beside the measurement, so the two must be one folder.
    assert cwd.resolve() == meas.parent.resolve()


# --- 2. pasted values, with and without the 3D map (real colverify) --------

@needs_colverify
@pytest.mark.parametrize("folder", ODD_DIRS)
@pytest.mark.parametrize("want_plot", [False, True])
def test_pasted_lab_values_are_verified(tmp_path, qapp, monkeypatch,
                                        folder, want_plot):
    meas = _measured_lab(tmp_path / folder)
    runner = _SyncRunner()
    dlg = _dialog(runner, monkeypatch)
    try:
        dlg._measured = meas
        dlg._ref_edit.setPlainText(_paste(LAB_ROWS))
        dlg._vrml_cb.setChecked(want_plot)
        dlg._execute()
        text = _log(dlg)
        assert "Unable to open" not in text, text
        assert runner.calls, text
        res = dlg._cv.parse_results()
        assert res.avg_de == pytest.approx(0.0, abs=1e-3), text
        assert len(res.patch_errors) == len(LAB_ROWS), text
        assert "[DONE]" in text, text
        if want_plot:
            assert dlg._shown_plots and dlg._shown_plots[0].is_file(), text
        # no reference and no 3D map left beside the measurement (only the
        # report, wherever reports_dir_for files it)
        left = sorted(p.name for p in meas.parent.iterdir())
        assert not [n for n in left
                    if n.endswith(("-reference.ti3", ".x3d.html"))], left
    finally:
        dlg.close()
        dlg.done(0)


# --- 3. a measurement (.ti3) loaded as the reference (real colverify) ------

def _cgats_parts(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    fi = lines.index("BEGIN_DATA_FORMAT")
    b = lines.index("BEGIN_DATA")
    e = lines.index("END_DATA")
    return lines, fi, b, e


def _variant(src: Path, dst: Path, *, rows=None, drop_xyz=False,
             rotate_ids=0, renumber=0) -> Path:
    """A copy of the real measurement with its table changed."""
    lines, fi, b, e = _cgats_parts(src)
    head, data, tail = lines[:b + 1], lines[b + 1:e], lines[e:]
    if rows is not None:
        data = data[:rows]
    toks = [ln.split() for ln in data]
    if rotate_ids:
        ids = [t[0] for t in toks]
        for k, t in enumerate(toks):
            t[0] = ids[(k + rotate_ids) % len(ids)]
    if renumber:
        for t in toks:
            t[0] = str(int(t[0]) + renumber)
    if drop_xyz:
        fields = lines[fi + 1].split()
        keep = [i for i, f in enumerate(fields) if not f.startswith("XYZ_")]
        head[fi + 1] = " ".join(fields[i] for i in keep)
        toks = [[t[i] for i in keep] for t in toks]
        head = [f"NUMBER_OF_FIELDS {len(keep)}"
                if ln.startswith("NUMBER_OF_FIELDS") else
                ln.replace('"iRGB_XYZ"', '"iRGB"') for ln in head]
    head = [f"NUMBER_OF_SETS {len(toks)}"
            if ln.startswith("NUMBER_OF_SETS") else ln for ln in head]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(head + [" ".join(t) for t in toks] + tail)
                   + "\n", encoding="utf-8")
    return dst


def _load(dlg, path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dlg, "_pick_input_file", lambda *_a, **_k: path)
    dlg._load_reference_file()


@needs_colverify
@pytest.mark.parametrize("kind", ["same", "spectral-only"])
@pytest.mark.parametrize("want_plot", [False, True])
def test_a_measurement_loaded_as_the_reference_is_verified(
        tmp_path, qapp, monkeypatch, kind, want_plot):
    meas = tmp_path / "run 1 ü" / "Chart.ti3"
    meas.parent.mkdir(parents=True)
    shutil.copyfile(REAL_TI3, meas)
    ref = _variant(REAL_TI3, tmp_path / "Referenz ø" / "reference read.ti3",
                   drop_xyz=(kind == "spectral-only"))
    runner = _SyncRunner()
    dlg = _dialog(runner, monkeypatch)
    try:
        dlg._measured = meas
        _load(dlg, ref, monkeypatch)
        dlg._vrml_cb.setChecked(want_plot)
        assert dlg._can_run()
        dlg._execute()
        text = _log(dlg)
        assert "doesn't have three numbers" not in text, text
        assert runner.calls, text
        res = dlg._cv.parse_results()
        assert res.avg_de is not None, text
        # the same readings: identical, or (spectral-only) within the
        # rounding of colverify's own spectrum-to-XYZ
        assert res.avg_de == pytest.approx(0.0, abs=0.05), text
        assert len(res.patch_errors) == 616, text
        # the user's reference file was not changed or moved
        assert ref.is_file()
    finally:
        dlg.close()
        dlg.done(0)


@needs_colverify
@pytest.mark.parametrize("change", ["ids rotated", "patch missing",
                                    "other ids"])
def test_a_reference_of_another_chart_is_refused(tmp_path, qapp, monkeypatch,
                                                 change):
    from workflow.measurement_messages import M_VERIFY_REFERENCE_MISMATCH
    meas = tmp_path / "run" / "Chart.ti3"
    meas.parent.mkdir(parents=True)
    shutil.copyfile(REAL_TI3, meas)
    kw = {"ids rotated": {"rotate_ids": 6}, "patch missing": {"rows": 615},
          "other ids": {"renumber": 1000}}[change]
    ref = _variant(REAL_TI3, tmp_path / "ref" / "other.ti3", **kw)
    runner = _SyncRunner()
    dlg = _dialog(runner, monkeypatch)
    try:
        dlg._measured = meas
        _load(dlg, ref, monkeypatch)
        dlg._execute()
        assert not runner.calls, "colverify must not be asked"
        title = M_VERIFY_REFERENCE_MISMATCH.render(file="x", reason="y")[0]
        assert title in dlg._banner.text(), dlg._banner.text()
        assert "other.ti3" in dlg._banner.text()
        assert dlg._cv.parse_results().avg_de is None
    finally:
        dlg.close()
        dlg.done(0)


@needs_colverify
def test_a_rotated_reference_really_gives_nonsense_from_colverify(tmp_path):
    """Why the refusal exists: colverify itself accepts the rotated file and
    prints large errors for pairs of different patches."""
    ref = _variant(REAL_TI3, tmp_path / "rot.ti3", rotate_ids=6)
    p = subprocess.run([COLVERIFY, "-k", str(ref), str(REAL_TI3)],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=240)
    res = ColverifyRunner(None).parse_results(p.stdout)
    assert res.avg_de is not None and res.avg_de > 5


def test_a_plain_table_file_still_fills_the_paste_box(tmp_path, qapp,
                                                      monkeypatch):
    table = tmp_path / "werte ü.txt"
    table.write_text("# expected\n1 95 0.5 -2\n2 50 10 -20\n", encoding="utf-8")
    dlg = _dialog(_SyncRunner(), monkeypatch)
    try:
        _load(dlg, table, monkeypatch)
        assert "95 0.5 -2" in dlg._ref_edit.toPlainText()
        assert dlg._ref_edit.isEnabled()
    finally:
        dlg.close()
        dlg.done(0)


# --- 4. the other kinds of reference file ----------------------------------

def _lab_only_without_ids(src: Path, dst: Path) -> Path:
    """The real measurement's patches as a CGATS table of L*a*b* only, no
    SAMPLE_ID and no device values (a reference another program wrote)."""
    from workflow.ti3_analysis import parse_ti3
    from workflow.icc_info import xyz_to_lab
    d = parse_ti3(src)
    rows = [" ".join(f"{v:.5f}" for v in xyz_to_lab(tuple(x / 100.0 for x in xyz)))
            for xyz in d.xyz]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join([
        "CGATS.17", "", 'ORIGINATOR "elsewhere"', "NUMBER_OF_FIELDS 3",
        "BEGIN_DATA_FORMAT", "LAB_L LAB_A LAB_B", "END_DATA_FORMAT",
        f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA", *rows, "END_DATA", ""]),
        encoding="utf-8")
    return dst


@needs_colverify
def test_a_table_without_patch_numbers_is_paired_in_file_order(
        tmp_path, qapp, monkeypatch):
    meas = tmp_path / "run" / "Chart.ti3"
    meas.parent.mkdir(parents=True)
    shutil.copyfile(REAL_TI3, meas)
    ref = _lab_only_without_ids(REAL_TI3, tmp_path / "ref ü" / "lab.cgats")
    runner = _SyncRunner()
    dlg = _dialog(runner, monkeypatch)
    try:
        dlg._measured = meas
        _load(dlg, ref, monkeypatch)
        assert "order" in dlg._ref_file_label.text()
        dlg._execute()
        text = _log(dlg)
        res = dlg._cv.parse_results()
        assert res.avg_de == pytest.approx(0.0, abs=0.05), text
        assert len(res.patch_errors) == 616, text
        # the user's file was read, not rewritten
        assert "SAMPLE_ID" not in ref.read_text(encoding="utf-8")
    finally:
        dlg.close()
        dlg.done(0)


@needs_colverify
def test_a_table_without_patch_numbers_and_another_count_is_refused(
        tmp_path, qapp, monkeypatch):
    from workflow.measurement_messages import M_VERIFY_REFERENCE_MISMATCH
    meas = tmp_path / "run" / "Chart.ti3"
    meas.parent.mkdir(parents=True)
    _variant(REAL_TI3, meas, rows=600)
    ref = _lab_only_without_ids(REAL_TI3, tmp_path / "ref" / "lab.cgats")
    runner = _SyncRunner()
    dlg = _dialog(runner, monkeypatch)
    try:
        dlg._measured = meas
        _load(dlg, ref, monkeypatch)
        dlg._execute()
        assert not runner.calls
        assert M_VERIFY_REFERENCE_MISMATCH.render(file="", reason="")[0] \
            in dlg._banner.text()
        assert "616" in dlg._banner.text() and "600" in dlg._banner.text()
    finally:
        dlg.close()
        dlg.done(0)


def test_the_chosen_chart_definition_is_cross_checked_for_a_file_too(tmp_path):
    from workflow.colverify_runner import load_reference_file, reference_mismatch
    chart = tmp_path / "chart.ti2"
    chart.write_text("CTI2\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
                     "END_DATA_FORMAT\nBEGIN_DATA\n1 0 0 0\n2 100 100 100\n"
                     "END_DATA\n", encoding="utf-8")
    from workflow.measurement_messages import M_VERIFY_REFERENCE_CHART
    message, kw = reference_mismatch(load_reference_file(REAL_TI3), REAL_TI3,
                                     chart)
    assert message is M_VERIFY_REFERENCE_CHART
    assert kw == {"ref_n": 616, "chart_n": 2}


def test_the_same_chart_passes_the_check(tmp_path):
    from workflow.colverify_runner import load_reference_file, reference_mismatch
    other = _variant(REAL_TI3, tmp_path / "copy.ti3")
    assert reference_mismatch(load_reference_file(other), REAL_TI3) is None


def test_a_device_value_mismatch_names_a_patch_and_both_values(tmp_path):
    from workflow.colverify_runner import load_reference_file, reference_mismatch
    rot = _variant(REAL_TI3, tmp_path / "rot.ti3", rotate_ids=6)
    _message, kw = reference_mismatch(load_reference_file(rot), REAL_TI3)
    assert "of 616 pairs" in kw["reason"], kw


def test_a_file_without_colour_values_is_refused_on_loading(
        tmp_path, qapp, monkeypatch):
    from workflow.measurement_messages import M_VERIFY_REFERENCE_UNUSABLE
    f = tmp_path / "Gerät ü.ti1"
    f.write_text("CTI1\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
                 "END_DATA_FORMAT\nBEGIN_DATA\n1 0 0 0\nEND_DATA\n",
                 encoding="utf-8")
    dlg = _dialog(_SyncRunner(), monkeypatch)
    try:
        _load(dlg, f, monkeypatch)
        assert dlg._ref_file is None
        assert M_VERIFY_REFERENCE_UNUSABLE.render(file="", reason="")[0] \
            in dlg._banner.text()
        assert "Gerät ü.ti1" in dlg._banner.text()
    finally:
        dlg.close()
        dlg.done(0)


@needs_colverify
def test_a_measurement_pasted_as_text_is_used_as_a_file(tmp_path, qapp,
                                                        monkeypatch):
    meas = tmp_path / "run" / "Chart.ti3"
    meas.parent.mkdir(parents=True)
    shutil.copyfile(REAL_TI3, meas)
    runner = _SyncRunner()
    dlg = _dialog(runner, monkeypatch)
    try:
        dlg._measured = meas
        dlg._ref_edit.setPlainText(REAL_TI3.read_text(encoding="utf-8"))
        dlg._execute()
        text = _log(dlg)
        assert "doesn't have three numbers" not in text, text
        res = dlg._cv.parse_results()
        assert res.avg_de == pytest.approx(0.0, abs=1e-4), text
    finally:
        dlg.close()
        dlg.done(0)


def test_typed_values_can_take_over_from_a_loaded_file(tmp_path, qapp,
                                                       monkeypatch):
    dlg = _dialog(_SyncRunner(), monkeypatch)
    try:
        dlg._measured = REAL_TI3
        _load(dlg, REAL_TI3, monkeypatch)
        assert dlg._ref_file is not None and not dlg._space.isEnabled()
        assert dlg._can_run()
        dlg._ref_file_clear.click()
        assert dlg._ref_file is None and dlg._space.isEnabled()
        assert not dlg._can_run()        # the box is empty
    finally:
        dlg.close()
        dlg.done(0)


def test_a_patch_line_with_a_location_is_parsed():
    """colverify prints "<id> <loc>:" when either file has SAMPLE_LOC, as
    every chartread measurement used as the reference does."""
    res = ColverifyRunner(None).parse_results(
        "2 AF9: 9.806039 8.234323 -23.153750 <=> 9.806039 8.234323 "
        "-23.153750  de 0.000000\n"
        "  Total errors (CIEDE2000):     peak = 0.000000, avg = 0.000000\n")
    assert [p.sample_id for p in res.patches] == ["2"]
    assert res.patch_errors == [("2", 0.0)]


def test_a_patch_line_cut_by_a_pipe_read_is_put_back_together():
    """ArgyllRunner emits what one pipe read holds; measured on screen on a
    616-patch run, patch 389's line arrived as "389: " and the rest, and the
    result said 615 patches."""
    res = ColverifyRunner(None).parse_results(
        "156: 47.654 45.766 -45.812 <=> 47.868 46.000 -46.034  de 0.226787\n"
        "389: \n"
        "17.417000 0.873000 -11.562000 <=> 17.456797 1.020845 -11.434530  "
        "de 0.226562\n"
        "600: 91.644 -2.260 0.594 <=> 91.567 -2.094 0.539  de 0.226176\n")
    assert [sid for sid, _ in res.patch_errors] == ["156", "389", "600"]
    assert res.patches[1].target == (17.417, 0.873, -11.562)


def test_a_patch_line_cut_inside_a_number_is_put_back_together():
    res = ColverifyRunner(None).parse_results(
        "52 AP8: 37.492753 -3.723912 -33.537\n"
        "450 <=> 37.713860 -3.742987 -33.903144  de 0.231351\n")
    assert res.patch_errors == [("52", 0.231351)]
    assert res.patches[0].target == (37.492753, -3.723912, -33.53745)



# --- review of 2dd09fc23 ----------------------------------------------------

def test_on_windows_the_reference_path_is_taken_as_written(tmp_path,
                                                          monkeypatch):
    """Windows resolves ".." lexically from the working folder AS WRITTEN,
    so through a junction or a subst drive a path between resolved folders
    would point elsewhere: there the paths are not resolved."""
    from workflow import colverify_runner as cr
    resolved = []

    def _real(p):
        resolved.append(p)
        return "/junction-target/" + os.path.basename(os.fspath(p))

    monkeypatch.setattr(cr.os.path, "realpath", _real)
    monkeypatch.setattr(cr.os, "name", "nt")
    ref = tmp_path / "staging" / "r.ti3"
    cwd = tmp_path / "run"
    out = cr._path_from(ref, cwd)
    assert not resolved
    assert out == os.path.relpath(os.path.abspath(ref), os.path.abspath(cwd))
    monkeypatch.setattr(cr.os, "name", "posix")
    cr._path_from(ref, cwd)
    assert resolved            # POSIX still climbs from the real folder


def test_device_values_on_0_to_1_are_compared_on_0_to_100(tmp_path):
    from workflow.colverify_runner import load_reference_file, reference_mismatch
    lines, fi, b, e = _cgats_parts(REAL_TI3)
    fields = lines[fi + 1].split()
    dev = [fields.index(f"RGB_{c}") for c in "RGB"]
    rows = []
    for ln in lines[b + 1:e]:
        t = ln.split()
        for i in dev:
            t[i] = f"{float(t[i]) / 100.0:.6f}"
        rows.append(" ".join(t))
    ref = tmp_path / "fractions.ti3"
    ref.write_text("\n".join(lines[:b + 1] + rows + lines[e:]) + "\n",
                   encoding="utf-8")
    assert reference_mismatch(load_reference_file(ref), REAL_TI3) is None
    rot = _variant(ref, tmp_path / "fractions-rotated.ti3", rotate_ids=6)
    assert reference_mismatch(load_reference_file(rot), REAL_TI3) is not None


def test_a_comment_line_inside_the_data_is_not_a_patch(tmp_path):
    from workflow.colverify_runner import load_reference_file, reference_mismatch
    lines, fi, b, e = _cgats_parts(REAL_TI3)
    ref = tmp_path / "commented.ti3"
    # a patch line commented out: as many words as a real one
    ref.write_text("\n".join(lines[:b + 1] + ["# " + lines[b + 1]]
                             + lines[b + 1:e] + lines[e:]) + "\n",
                   encoding="utf-8")
    loaded = load_reference_file(ref)
    assert loaded.n_patches == 616
    assert reference_mismatch(loaded, REAL_TI3) is None


def test_a_patch_line_cut_inside_its_delta_e_is_put_back_together():
    res = ColverifyRunner(None).parse_results(
        "52 AP8: 37.492753 -3.723912 -33.53745 <=> 37.713860 -3.742987 "
        "-33.903144  de 0.23\n"
        "1351\n"
        "53: 1.0 2.0 3.0 <=> 1.0 2.0 3.0  de 0.000000\n")
    assert res.patch_errors == [("52", 0.231351), ("53", 0.0)]


@needs_colverify
def test_a_chart_definition_of_another_chart_gets_its_own_message_and_can_be_cleared(
        tmp_path, qapp, monkeypatch):
    from workflow.measurement_messages import M_VERIFY_REFERENCE_CHART
    meas = tmp_path / "run" / "Chart.ti3"
    meas.parent.mkdir(parents=True)
    shutil.copyfile(REAL_TI3, meas)
    chart = tmp_path / "other.ti2"
    chart.write_text("CTI2\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
                     "END_DATA_FORMAT\nBEGIN_DATA\n1 0 0 0\nEND_DATA\n",
                     encoding="utf-8")
    runner = _SyncRunner()
    dlg = _dialog(runner, monkeypatch)
    try:
        dlg._measured = meas
        dlg._chart = chart
        dlg._chart_field.setText(str(chart))
        _load(dlg, REAL_TI3, monkeypatch)
        dlg._execute()
        assert not runner.calls
        title = M_VERIFY_REFERENCE_CHART.render(file="", ref_n=0,
                                                chart_n=0)[0]
        assert title in dlg._banner.text()
        assert "Clear" in dlg._banner.text()
        dlg._clear_chart()
        assert dlg._chart is None and not dlg._chart_field.text()
        dlg._execute()
        assert runner.calls
        assert dlg._cv.parse_results().avg_de == pytest.approx(0.0, abs=1e-4)
    finally:
        dlg.close()
        dlg.done(0)


def test_a_refused_file_lets_go_of_the_file_chosen_before(tmp_path, qapp,
                                                          monkeypatch):
    bad = tmp_path / "no colour.ti1"
    bad.write_text("CTI1\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
                   "END_DATA_FORMAT\nBEGIN_DATA\n1 0 0 0\nEND_DATA\n",
                   encoding="utf-8")
    dlg = _dialog(_SyncRunner(), monkeypatch)
    try:
        _load(dlg, REAL_TI3, monkeypatch)
        assert dlg._ref_file is not None
        _load(dlg, bad, monkeypatch)
        assert dlg._ref_file is None
        assert dlg._ref_file_row.isHidden() and not dlg._ref_edit.isHidden()
        assert "no colour.ti1" in dlg._banner.text()
    finally:
        dlg.close()
        dlg.done(0)


def test_a_pasted_measurement_greys_out_the_colour_space_too(qapp,
                                                            monkeypatch):
    dlg = _dialog(_SyncRunner(), monkeypatch)
    try:
        assert dlg._space.isEnabled()
        dlg._ref_edit.setPlainText(REAL_TI3.read_text(encoding="utf-8"))
        assert not dlg._space.isEnabled()
        dlg._ref_edit.setPlainText("95 0 0\n")
        assert dlg._space.isEnabled()
    finally:
        dlg.close()
        dlg.done(0)
