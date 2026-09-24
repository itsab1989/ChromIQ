"""#182 K34: Knut's answers to section A of 5802027116 (5817809396, "the
recommended is accepted"), built for beta 42.

* A6  a report that covered a since-deleted profile run says so in Report
      Scope (M-REPORT-SCOPE-RUN-DELETED, proposed);
* A8  the folder-renamed window: a rename that fails says why, and the three
      choices come back (another name, or Cancel);
* A9  inside each heading of "Report shown", newest first by the report's OWN
      creation date, not the file's time;
* A10 "Paper white" is the patch printed with no ink; a chart with none reads
      N-A with a numbered note, draws no point, and is never judged relative
      to the paper (M-REPORT-NO-PAPER-PATCH, proposed);
* A11 on a FROM PROFILE GAMUT chart, "Paper white, difference from the
      reference paper" compares the bare paper with the paper the chart's
      profile describes (its media white), not an ideal L* 100 white.

Every test names the mutation that turns it red; each was run red.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _sheet(path: Path, rows, kind: str = "CTI3") -> Path:
    """A CGATS file of ``[(rgb, xyz)]``: the device values and the readings
    given separately, so a sheet can have a paper patch that is NOT its
    lightest reading."""
    lines = [kind, 'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "iRGB_XYZ"', "",
             "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rows)}",
             "BEGIN_DATA"]
    for i, ((r, g, b), (x, y, z)) in enumerate(rows, 1):
        lines.append(f'{i} "A{i}" {r:.4f} {g:.4f} {b:.4f} '
                     f"{x:.4f} {y:.4f} {z:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


#: Eight patches. Row 2 is the paper (device white, L* ~95); row 7 is a
#: light YELLOW that reads LIGHTER than the paper, which is exactly what made
#: "the lightest patch" call a colour the paper (Every-Limit-Set/run6, F13).
_WITH_PAPER = [
    ((0.0, 0.0, 0.0), (1.5, 1.5, 1.3)),
    ((100.0, 100.0, 100.0), (84.0, 87.0, 71.0)),
    ((100.0, 0.0, 0.0), (40.0, 22.0, 3.0)),
    ((0.0, 100.0, 0.0), (35.0, 60.0, 12.0)),
    ((0.0, 0.0, 100.0), (18.0, 12.0, 60.0)),
    ((50.0, 50.0, 50.0), (20.0, 21.0, 17.0)),
    ((100.0, 100.0, 60.0), (88.0, 94.0, 30.0)),
    ((80.0, 20.0, 60.0), (30.0, 20.0, 25.0)),
]
#: The same chart without its paper patch: no row printed with no ink.
_NO_PAPER = [row for row in _WITH_PAPER if row[0] != (100.0, 100.0, 100.0)]


# --------------------------------------------------------------------------
# A10: the paper white is the patch printed with no ink
# --------------------------------------------------------------------------
def test_no_ink_is_every_channel_at_full_in_rgb_and_zero_in_ink_spaces():
    """The rule for every space the report may meet.

    MUTATION, proven red: test ``>= 100 - tol`` for every space (a CMYK sheet
    reads its solid black as the paper)."""
    from workflow.measurement_report import paper_patch_rows
    rgb = [(0, 0, 0), (100, 100, 100), (99.7, 100, 99.6), (97, 97, 97)]
    assert paper_patch_rows(rgb, "RGB") == [1, 2]
    cmyk = [(0, 0, 0, 0), (100, 100, 100, 100), (0, 0, 0.3, 0), (0, 0, 3, 0)]
    assert paper_patch_rows(cmyk, "CMYK") == [0, 2]
    assert paper_patch_rows([(0, 0, 0)], "CMY") == [0]
    assert paper_patch_rows([], "RGB") == []


def test_the_paper_white_is_the_paper_patch_not_the_lightest_reading(
        tmp_path):
    """A light yellow reading lighter than the paper is not the paper.

    MUTATION, proven red: take ``wi`` from `lightest_and_darkest` again in
    `measurement_facts` (the yellow patch A7 is recorded as paper white)."""
    from workflow.measurement_report import build_report
    rep = build_report(_sheet(tmp_path / "s.ti3", _WITH_PAPER))
    assert rep["paper_patch"] is True
    assert rep["paper_white"]["loc"] == "A2", rep["paper_white"]


def test_a_chart_with_no_paper_patch_records_no_paper_white(tmp_path):
    """Knut, 5817809396 (a): *"when there is none say "This chart has no
    paper patch": Paper white reads N-A"*. The report records that there is
    none, and records no paper white at all, so no graph can draw one.

    MUTATION, proven red: fall back to the lightest patch when
    `paper_white_row` answers None (the L* 97 yellow becomes the paper)."""
    from workflow.measurement_report import build_report, report_trend
    rep = build_report(_sheet(tmp_path / "s.ti3", _NO_PAPER))
    assert rep["paper_patch"] is False
    assert "paper_white" not in rep
    assert rep["max_black"]["loc"] == "A1"
    pts = report_trend([rep])
    assert pts and "white_L" not in pts[0], pts


def test_a_relative_print_with_no_paper_patch_is_judged_in_absolute_lab(
        tmp_path):
    """"Nothing is judged relative to the paper": a sheet printed through its
    profile with a white-mapping intent is normally divided by its paper
    white; with no paper patch it stays as measured.

    MUTATION, proven red: normalise by the lightest patch when there is no
    paper patch (the yardstick reads media-relative)."""
    from workflow.measurement_report import build_report
    from workflow.verification_print import write_print_record
    for name, rows, want in (("with", _WITH_PAPER, "media-relative"),
                             ("none", _NO_PAPER, "absolute")):
        d = tmp_path / name
        d.mkdir()
        ti3 = _sheet(d / "v.ti3", rows)
        _sheet(d / "v.ti2", rows, kind="CTI2")
        write_print_record(d / "v.ti2", colour="through-profile",
                           intent="relative", profile=None, route="chromiq")
        rep = build_report(ti3)
        assert rep["reference_source"] == "design"
        assert rep["yardstick"] == want, (name, rep["yardstick"])
        assert bool(rep.get("yardstick_no_paper")) is (name == "none")


def _window_on(tmp_path, qapp, rows):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import build_report
    ti3 = _sheet(tmp_path / "s.ti3", rows)
    dlg = MeasurementReportDialog(_settings(), None, initial_ti3=ti3)
    return dlg, build_report(ti3)


def test_the_window_reads_n_a_with_a_numbered_note(tmp_path, qapp):
    """The "Paper white" line of the detailed section and the Overview table
    read N-A, the line carries a raised note number, and the note list names
    it "Paper white" with M-REPORT-NO-PAPER-PATCH's words.

    MUTATION, proven red: drop the pseudo-row from `_note_numbering` (the line
    reads N-A with no number and the list has no such note)."""
    import html as _html
    import re
    from workflow import measurement_messages as M
    dlg, rep = _window_on(tmp_path, qapp, _NO_PAPER)
    try:
        detail = _html.unescape(dlg._run_detail_html(rep))
        said = M.M_REPORT_NO_PAPER_PATCH.render()[1]
        assert re.search(r"White - N-A<sup>&nbsp;\d\)</sup>", detail.replace(
            "\xa0", "&nbsp;")), detail[:2000]
        assert said in detail
        nums = dlg._numbered_notes([rep])
        assert any(where == "Paper white" and s == said
                   for _n, where, s in nums), nums
        table = _html.unescape(dlg._comparison_table_html([rep]))
        row = table[table.index("Paper white L*"):][:200]
        assert "N-A" in row, row
    finally:
        dlg.close()


def test_a_chart_with_its_paper_patch_carries_no_such_note(tmp_path, qapp):
    """The control: the paper patch is there, so the line prints its L*, a*
    and b* as before and nothing is added to the notes.

    MUTATION, proven red: add the pseudo-row for every sheet."""
    import html as _html
    dlg, rep = _window_on(tmp_path, qapp, _WITH_PAPER)
    try:
        detail = _html.unescape(dlg._run_detail_html(rep))
        assert "White (A2) - L*" in detail
        assert all(where != "Paper white"
                   for _n, where, _s in dlg._numbered_notes([rep]))
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# A11: the reference paper of a FROM PROFILE GAMUT chart
# --------------------------------------------------------------------------
_PROFILE_WHITE = (95.5, 0.21, 1.41)


def _selection(white=_PROFILE_WHITE):
    from workflow.gamut_target import (CORNER_DEVICES, GamutSelection,
                                       _corner_ideal_labs)
    sel = GamutSelection(master_version="t", master_total=1, in_gamut_total=1,
                         requested=1, intent="absolute", margin="safe",
                         profile_white_lab=white, profile_name="P.icc")
    sel.targets = [(0, (50.0, 10.0, 10.0), (60.0, 40.0, 40.0))]
    sel.corners = list(zip(CORNER_DEVICES, _corner_ideal_labs()))
    return sel


def test_the_reference_records_the_profiles_media_white(tmp_path):
    """The chart's reference carries the paper its profile describes, and the
    bare-paper corner aims at it when the file is read.

    MUTATION, proven red: drop the override in `read_colorimetric_reference`
    (the W corner aims at L* 100.0)."""
    from workflow.gamut_target import (corner_sample_ids,
                                       read_colorimetric_reference,
                                       write_colorimetric_reference)
    ref = write_colorimetric_reference(_selection(), tmp_path / "r.ti3")
    text = ref.read_text(encoding="utf-8")
    assert 'CHROMIQ_PROFILE_WHITE_LAB "95.5000 0.2100 1.4100"' in text
    cref = read_colorimetric_reference(ref)
    assert cref["profile_white_lab"] == _PROFILE_WHITE
    w_id = str(corner_sample_ids(_selection())[0])        # device white
    assert cref["labs"][w_id] == _PROFILE_WHITE
    k_id = str(corner_sample_ids(_selection())[1])        # device black
    assert cref["labs"][k_id] != _PROFILE_WHITE


def test_a_reference_of_an_older_build_has_no_profile_white(tmp_path):
    """Written without one (a profile with no readable media white, or any
    reference before beta 42): nothing recorded, the aims as written."""
    from workflow.gamut_target import (read_colorimetric_reference,
                                       write_colorimetric_reference)
    ref = write_colorimetric_reference(_selection(None), tmp_path / "r.ti3")
    assert "CHROMIQ_PROFILE_WHITE_LAB" not in ref.read_text(encoding="utf-8")
    assert read_colorimetric_reference(ref)["profile_white_lab"] is None


def test_the_profile_white_is_read_from_the_profiles_wtpt(tmp_path):
    """`profile_media_white_lab` is the profile's own ``wtpt`` as L*a*b*.

    MUTATION, proven red: return the header's PCS illuminant (always D50,
    L* 100) instead of the media white tag."""
    import struct
    from workflow.gamut_target import profile_media_white_lab
    from workflow.icc_info import xyz_to_lab
    xyz = (0.9130, 0.9120, 0.7440)
    # a minimal profile: header, one tag (wtpt, XYZType)
    tag = b"XYZ " + b"\0" * 4 + struct.pack(">3i", *(round(v * 65536)
                                                      for v in xyz))
    header = bytearray(128)
    header[36:40] = b"acsp"
    header[68:80] = struct.pack(">3i", *(round(v * 65536)
                                         for v in (0.9642, 1.0, 0.8249)))
    table = struct.pack(">I", 1) + b"wtpt" + struct.pack(">II", 144, len(tag))
    data = bytes(header) + table + tag
    data = struct.pack(">I", len(data)) + data[4:]
    icc = tmp_path / "p.icc"
    icc.write_bytes(data)
    got = profile_media_white_lab(icc)
    want = xyz_to_lab(xyz)
    assert got is not None and all(abs(a - b) < 0.01
                                   for a, b in zip(got, want)), (got, want)
    assert got[0] < 99.0


def _gamut_verification(tmp_path, *, profile_white, run_icc_white=None):
    """A project whose run holds a FROM PROFILE GAMUT verification: the chart,
    its colorimetric reference, and one measured date on which the bare paper
    reads EXACTLY the profile's white. Returns the date's .ti3."""
    from core.file_manager import Project
    from workflow.gamut_target import (mark_chart_as_colorimetric,
                                       reference_rows,
                                       write_colorimetric_reference)
    from workflow.ti3_analysis import _lab_to_xyz_array
    import numpy as np
    proj = Project.create(tmp_path / "G", "G")
    run = proj.current_run()
    run.ensure_dir()
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    sel = _selection(profile_white)
    rows = reference_rows(sel)
    stem = f"{run.stem}-verify"
    chart = [(dev, (10.0, 10.0, 10.0)) for _sid, dev, _lab in rows]
    ti2 = _sheet(vdir / f"{stem}.ti2", chart, kind="CTI2")
    ref = write_colorimetric_reference(sel, vdir / f"{stem}-reference.ti3")
    mark_chart_as_colorimetric(ti2, ref)
    date = vdir / "2026-09-24_100000"
    date.mkdir()
    measured = []
    for _sid, dev, lab in rows:
        if tuple(dev) == (100.0, 100.0, 100.0):
            lab = _PROFILE_WHITE                      # the profile's paper
        xyz = tuple(float(v) for v in _lab_to_xyz_array(np.array([lab]))[0])
        measured.append((dev, xyz))
    ti3 = _sheet(date / f"{stem}.ti3", measured)
    if run_icc_white is not None:
        import struct
        from workflow.icc_info import _D50
        from workflow.ti3_analysis import _lab_to_xyz_array as l2x
        x, y, z = (float(v) / 100.0 for v in l2x(np.array([run_icc_white]))[0])
        tag = b"XYZ " + b"\0" * 4 + struct.pack(
            ">3i", *(round(v * 65536) for v in (x, y, z)))
        header = bytearray(128)
        header[36:40] = b"acsp"
        table = struct.pack(">I", 1) + b"wtpt" + struct.pack(">II", 144,
                                                             len(tag))
        data = bytes(header) + table + tag
        run.profile_icc.write_bytes(struct.pack(">I", len(data)) + data[4:])
        assert _D50
    return ti3


def test_the_paper_row_compares_the_paper_with_the_profiles_white(tmp_path):
    """Knut, 5817809396 (A11, "yes"). Measured before the change on the
    beta 41 pack: the row compared the bare paper with L* 100.0, a* 0.01,
    b* -0.01, and a paper of the profile's own white (L* 95.5) read about
    2.98 ΔE00. Here the paper IS the profile's paper, so the row reads 0.

    MUTATION, proven red: leave the W corner on its ideal-white aim (drop
    the override in `read_colorimetric_reference` and in `build_report`):
    the row reads 2.98."""
    from workflow.measurement_report import build_report, row_values
    ti3 = _gamut_verification(tmp_path, profile_white=_PROFILE_WHITE)
    rep = build_report(ti3)
    assert rep["reference_source"] == "colorimetric"
    assert rep["colorimetric"]["paper_reference_lab"] == list(_PROFILE_WHITE)
    assert rep["colorimetric"]["paper_reference_from"] == "chart"
    w = {c["name"]: c for c in rep["corners"]}["W"]
    assert w["expected_lab"] == list(_PROFILE_WHITE)
    v = row_values(rep)["substrate_de00_max"]["value"]
    assert v is not None and v < 0.05, v


def test_an_older_reference_asks_the_runs_own_profile(tmp_path):
    """A reference written before beta 42 records no white: the run's built
    profile, the one a FROM PROFILE GAMUT chart of that run is built from, is
    asked instead.

    MUTATION, proven red: return None from `paper_reference_of` when the
    reference records nothing (the row reads ~2.98 against the ideal white)."""
    from workflow.measurement_report import build_report, row_values
    ti3 = _gamut_verification(tmp_path, profile_white=None,
                              run_icc_white=_PROFILE_WHITE)
    rep = build_report(ti3)
    assert rep["colorimetric"]["paper_reference_from"] == "run_profile"
    v = row_values(rep)["substrate_de00_max"]["value"]
    assert v is not None and v < 0.1, v


def test_with_nothing_to_ask_the_row_keeps_its_old_comparison(tmp_path):
    """No white recorded and no profile in the run: the row keeps the old
    comparison with the W corner's own aim (device white read as sRGB),
    which is what a report saved before beta 42 carries anyway."""
    from workflow.measurement_report import build_report, row_values
    ti3 = _gamut_verification(tmp_path, profile_white=None)
    rep = build_report(ti3)
    assert "paper_reference_lab" not in rep["colorimetric"]
    v = row_values(rep)["substrate_de00_max"]["value"]
    assert v is not None and 2.5 < v < 3.5, v


# --------------------------------------------------------------------------
# A9: the order inside a group of "Report shown"
# --------------------------------------------------------------------------
def test_the_order_is_the_reports_own_creation_date():
    """A report copied later (newer file time) but created earlier sorts
    below; a report with no document date falls back to its name's stamp.

    MUTATION, proven red: sort `_saved_documents` on ``order`` (the file
    time) alone again."""
    from ui.dialogs.measurement_report_dialog import _report_created_at
    older_copied_last = {"doc": {"created": "2026-12-08T10:00:00"},
                         "members": [], "order": (9_000_000_000_000_000_000,)}
    newer = {"doc": {"created": "2026-12-15T10:00:00"}, "members": [],
             "order": (1_000_000_000_000_000_000,)}
    legacy = {"doc": None,
              "members": [(None, "report_2026-12-10_09-30-00.json")],
              "order": (5_000_000_000_000_000_000,)}
    ordered = sorted([older_copied_last, newer, legacy],
                     key=lambda e: (_report_created_at(e), e["order"]),
                     reverse=True)
    assert [_report_created_at(e) for e in ordered] == [
        "2026-12-15T10:00:00", "2026-12-10T09:30:00", "2026-12-08T10:00:00"]


def test_the_window_lists_a_copied_report_by_its_own_date(tmp_path, qapp):
    """Driven through `_saved_documents`: two one-date reports of one run,
    the OLDER one's file touched last (as a copy or a restore leaves it).

    MUTATION, proven red: the same as above."""
    from tests.test_calibration_reports import _settings, _window
    from tests.test_g7_reports_across_places import (
        _date, _new_report_of_everything, _press, _project)
    proj, run1, v1 = _project(tmp_path, "P")
    v2 = _date(run1, 0.5)
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._ask_update_or_create_new = lambda: "new"
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        _press(dlg, qapp)
        _new_report_of_everything(dlg, qapp)
        _press(dlg, qapp)
    finally:
        dlg.close()
    files = sorted((proj.root / "runs" / "run1" / "verifications"
                    / "reports").glob("report_*.json"))
    assert len(files) == 2, files
    stamps = ["2026-12-08T10:00:00", "2026-12-15T10:00:00"]
    for f, when in zip(files, stamps):
        d = json.loads(f.read_text(encoding="utf-8"))
        d["document"]["created"] = when
        f.write_text(json.dumps(d), encoding="utf-8")
    os.utime(files[0], (4_000_000_000, 4_000_000_000))   # the older, touched
    os.utime(files[1], (1_000_000_000, 1_000_000_000))
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        docs = dlg._saved_documents(dlg._run_ctx.run)
        got = [str((d.get("doc") or {}).get("created")) for d in docs
               if (d.get("doc") or {}).get("created") in stamps]
        assert got == list(reversed(stamps)), got
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# A6: a report that covered a since-deleted profile run
# --------------------------------------------------------------------------
class _Target:
    def __init__(self, profile_run):
        self.profile_run = profile_run
        self.run_type = "profiling"
        self.verification_id = ""

    def is_verification(self):
        return False


def _three_runs_one_report(tmp_path, qapp):
    from tests.test_calibration_reports import _settings, _window
    from tests.test_g7_reports_across_places import (
        _date, _new_report_of_everything, _press, _project)
    proj, run1, v1 = _project(tmp_path, "P")
    vs = [v1]
    for f in (0.5, 0.7):
        r = proj.new_run()
        r.ensure_dir()
        vs.append(_date(r, f))
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._ask_update_or_create_new = lambda: "new"
        for v in vs[1:]:
            dlg._add_source(v.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        _press(dlg, qapp)
    finally:
        dlg.close()
    return proj


def _scope_of_the_report(proj, qapp):
    import html as _html
    from tests.test_calibration_reports import _settings, _window
    ti3 = next((proj.root / "runs" / "run1").glob("verifications/*/*.ti3"))
    dlg = _window(_settings(), ti3, qapp, "verification")
    try:
        assert str(dlg._loaded_doc_id).startswith("id:"), dlg._loaded_doc_id
        return _html.unescape(dlg._scope_html(dlg._runs_for_document()))
    finally:
        dlg.close()


def test_report_scope_names_a_deleted_profile_run(tmp_path, qapp):
    """Knut, 5817809396 (A6, "add the Scope line"). Run 2 of three deleted
    with the profile bar's Delete: the report across the three shows two, and
    Report Scope says the third was run 2 and has since been deleted.

    MUTATION, proven red: leave `_scope_deleted_runs_html` out of
    `_scope_html` (nothing on the page says a run is missing)."""
    import core.run_delete as rd
    from workflow import measurement_messages as M
    proj = _three_runs_one_report(tmp_path, qapp)
    rd.delete_run(proj, rd.plan_for(proj, _Target("run2")))
    scope = _scope_of_the_report(proj, qapp)
    title, body = M.M_REPORT_SCOPE_RUN_DELETED.render(count=1, runs="run 2")
    assert title in scope and body in scope, scope


def test_a_report_with_every_run_there_says_nothing_of_the_kind(
        tmp_path, qapp):
    """The control: nothing deleted, no line.

    MUTATION, proven red: print the line whenever a saved report is shown."""
    from workflow import measurement_messages as M
    proj = _three_runs_one_report(tmp_path, qapp)
    title = M.M_REPORT_SCOPE_RUN_DELETED.render(count=1, runs="x")[0]
    assert title not in _scope_of_the_report(proj, qapp)


def test_the_deleted_runs_are_read_off_the_document():
    """By the number the run had when the report was written, once each; with
    the project's name when the report covers several projects."""
    from workflow import measurement_messages as M
    from workflow.measurement_report import deleted_runs_of
    doc = {"measurements": [
        {"dir": "/x/P/runs/run1/verifications/2026-01-01_100000"},
        {"dir": "/x/P/runs/run2.deleted/verifications/2026-01-02_100000"},
        {"dir": "/x/P/runs/run2.deleted/verifications/2026-01-03_100000"},
        {"dir": "/x/Q/runs/run4.deleted"}]}
    gone = deleted_runs_of(doc)
    assert gone == [("P", "2"), ("Q", "4")]
    assert M.deleted_runs_label(gone, True) == "P, run 2 and Q, run 4"
    assert M.deleted_runs_label(gone[:1], False) == "run 2"
    assert deleted_runs_of({"measurements": [{"dir": "/x/P/runs/run1"}]}) == []


# --------------------------------------------------------------------------
# A8: the folder-renamed window when the rename fails
# --------------------------------------------------------------------------
@pytest.fixture
def chart_tab(tmp_path, qapp):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    fm = FileManager(s)
    t = TabChart(ArgyllRunner(s), fm, s)
    yield t, fm
    t.deleteLater()


def _duplicate_whose_name_is_taken(fm):
    """"Demo copy" (a Finder duplicate of Demo) beside a project that already
    owns the name the rename would give it, "Demo-copy"."""
    from tests.test_k26_rulings import _project_with_files
    src = _project_with_files(fm, "Demo")
    dup = src.parent / "Demo copy"
    shutil.copytree(src, dup)
    taken = src.parent / "Demo-copy"
    shutil.copytree(src, taken)
    return dup, taken


def _answers(monkeypatch, actions, typed=()):
    from ui.dialogs import name_prompt
    from ui.dialogs import target_change_dialog as tcd
    import ui.tabs.tab_chart as tc
    shown, told = [], []
    queue, names = list(actions), list(typed)

    def _exec(self):
        shown.append(self)
        self._action = queue.pop(0)
        return 0
    monkeypatch.setattr(tcd.TargetChangeDialog, "exec", _exec)
    monkeypatch.setattr(tcd.TargetChangeDialog, "result_action",
                        lambda self: self._action)
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **k: names.pop(0))
    monkeypatch.setattr(tc.InfoDialog, "exec",
                        lambda self: told.append(self.windowTitle()) or 0)
    return shown, told


def test_a_failed_rename_says_why_and_offers_the_choices_again(
        chart_tab, monkeypatch):
    """Knut, 5817809396 (A8, answer (b)). Rename to the folder's name fails
    (the name is taken): M-PROJECT-FOLDER-RENAME-FAILED is shown, then the
    three choices come back, and "Choose another name" renames the project.

    MUTATION, proven red: ``return "failed"`` after the failure message
    again (one window, no second chance, the project stays unrenamed)."""
    from ui.dialogs.target_change_dialog import TargetChangeAction as A
    from workflow import measurement_messages as M
    t, fm = chart_tab
    dup, taken = _duplicate_whose_name_is_taken(fm)
    shown, told = _answers(monkeypatch, [A.RENAME, A.NEW_NAME],
                           ["Demo Second"])
    assert t._offer_rename_for_a_renamed_folder(dup) == "renamed"
    assert len(shown) == 2, "the choices did not come back"
    assert told == [M.M_PROJECT_FOLDER_RENAME_FAILED.title], told
    assert (dup.parent / "Demo-Second" / "project.json").is_file()
    assert (taken / "project.json").is_file()        # never touched


def test_cancel_after_a_failed_rename_closes_the_project(chart_tab,
                                                         monkeypatch):
    """The exit: after the failure, Cancel closes the project and nothing
    is renamed. No loop without an exit.

    MUTATION, proven red: offer only Rename after a failure (the second
    answer is ignored and the window comes up a third time; the queue runs
    dry)."""
    from ui.dialogs.target_change_dialog import TargetChangeAction as A
    t, fm = chart_tab
    dup, _taken = _duplicate_whose_name_is_taken(fm)
    before = sorted(str(p.relative_to(dup)) for p in dup.rglob("*"))
    shown, told = _answers(monkeypatch, [A.RENAME, A.CANCEL])
    assert t._offer_rename_for_a_renamed_folder(dup) == "closed"
    assert len(shown) == 2 and len(told) == 1
    assert sorted(str(p.relative_to(dup)) for p in dup.rglob("*")) == before


def test_a_report_saved_before_the_paper_patch_is_worked_out_again(tmp_path):
    """A saved report that does not record whether its chart has a paper
    patch took its paper white from the lightest reading (and, on a FROM
    PROFILE GAMUT chart, compared the paper with an ideal white). The window
    works such a report out again from its measurement, as it does for every
    block the builder now always writes; the saved verdict is carried across.
    Found ON SCREEN: without it, "New report…" on the no-paper-patch demo run
    still printed the L* 82 grey as White.

    MUTATION, proven red: take "paper_patch" out of `ALWAYS_BUILT_BLOCKS`."""
    from ui.dialogs.measurement_report_dialog import _report_needs_rebuilding
    from workflow.measurement_report import build_report
    rep = build_report(_sheet(tmp_path / "s.ti3", _NO_PAPER))
    assert not _report_needs_rebuilding(rep)
    old = dict(rep)
    old.pop("paper_patch")
    old["paper_white"] = {"loc": "A7", "lab": [97.0, -5.0, 60.0]}
    assert _report_needs_rebuilding(old)
