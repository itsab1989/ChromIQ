"""A measurement's damaged copy of the printer calibration is put back (beta 7).

ChromIQ's measuring engine wrote the CAL table of every -K/-I measurement as
``nan`` before 4.3.3-beta.7, and colprof refused the file ("Field 'CMYK_C' has
unexpected type", the CMYK/CR30 forum report). Basti ruled on 2026-10-03:
repair the measurement in place from its chart, keep the original in old/, and
keep the yellow confirmed marks. ``workflow/cal_repair.py`` does that; this
file proves the rules and that every Argyll consumer of a .ti3 asks for it.

The hooks, each pinned below:

* colprof           workflow/profile_builder.py   ProfileBuilder.build
* ChromIQ engine    workflow/engine_builder.py    EngineProfileBuilder.build
* profcheck         workflow/profcheck_runner.py  ProfcheckRunner.run
                    (Check & Refine, Tools ▸ Verify profile, the .ti3 window)
* average           workflow/average_runner.py    AverageRunner.run
* average -m        workflow/ti3_merge.py         merge_preconditioning,
                                                  merge_measurements
* colverify         workflow/colverify_runner.py  ColverifyRunner.run
* chartread -r      workflow/measure_manager.py   MeasureManager.start
                    (stock chartread and the engine, CR30 included)
* printcal          workflow/printcal_runner.py   PrintcalRunner.run
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import cal_repair, confirmed_patches as cp   # noqa: E402

WHEN = datetime(2026, 10, 3, 12, 0, 0)

#: (COLOR_REP of the chart, device field names): RGB, CMY, CMYK and six inks.
REPS = {
    "RGB": ("iRGB", ["RGB_R", "RGB_G", "RGB_B"]),
    "CMY": ("CMY", ["CMY_C", "CMY_M", "CMY_Y"]),
    "CMYK": ("CMYK", ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]),
    "6-ink": ("CMYKOG", ["CMYKOG_C", "CMYKOG_M", "CMYKOG_Y", "CMYKOG_K",
                         "CMYKOG_O", "CMYKOG_G"]),
}


def _devvals(i: int, n: int) -> "list[float]":
    return [round(((i * 37 + k * 11) % 101) * 1.0, 4) for k in range(n)]


def _cal_block(rep: str, fields: "list[str]", how: str = "good",
               nig: int = 17) -> str:
    """A CAL table as printcal writes it; *how*: good / nan / garbage /
    other (a genuinely different calibration)."""
    pre = fields[0].split("_")[0]
    cols = [f"{pre}_I"] + fields
    lines = []
    for j in range(nig):
        x = j / (nig - 1)
        if how == "nan":
            vals = ["nan"] * len(fields)
        elif how == "garbage":
            vals = ["0.250000"] * len(fields)
        elif how == "range":                 # numbers, but not 0..1
            vals = [f"{37.0 * x + k:.6f}" for k in range(len(fields))]
        elif how == "zigzag":                # numbers, but not monotonic
            vals = [f"{(0.9 if j % 2 else 0.1):.6f}" for _ in fields]
        else:
            g = 0.8 if how == "good" else 1.3
            vals = [f"{x ** (g + 0.05 * k):.6f}" for k in range(len(fields))]
        lines.append(" ".join([f"{x:.6f}"] + vals) + " ")
    return ("CAL    \n\nDESCRIPTOR \"Argyll Device Calibration Curves\"\n"
            "ORIGINATOR \"Argyll printcal\"\n"
            f"CREATED \"Sat Oct  3 04:21:09 2026\"\nDEVICE_CLASS \"OUTPUT\"\n"
            f"COLOR_REP \"{rep}\"\n\nNUMBER_OF_FIELDS {len(cols)}\n"
            f"BEGIN_DATA_FORMAT\n{' '.join(cols)} \nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {nig}\nBEGIN_DATA\n" + "\n".join(lines)
            + "\nEND_DATA\n")


def _aim_block(rep: str, fields: "list[str]") -> str:
    """printcal's second table, which a .ti2 carries and a .ti3 does not."""
    pre = fields[0].split("_")[0]
    cols = ["PARAMTYPE", f"{pre}_I"] + fields
    return ("CAL    \n\nDESCRIPTOR \"Argyll Calibration Aim Target Definition File\"\n"
            f"COLOR_REP \"{rep}\"\n\nNUMBER_OF_FIELDS {len(cols)}\n"
            f"BEGIN_DATA_FORMAT\n{' '.join(cols)} \nEND_DATA_FORMAT\n\n"
            "NUMBER_OF_SETS 1\nBEGIN_DATA\n"
            "DEVMAX_USED 0.00000 " + " ".join("1.000000" for _ in fields)
            + " \nEND_DATA\n")


def _write_ti2(path: Path, kind: str, n: int = 12, *, cal: str = "good",
               shift: float = 0.0) -> Path:
    rep, fields = REPS[kind]
    head = ["SAMPLE_ID", "SAMPLE_LOC"] + fields + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    rows = []
    for i in range(1, n + 1):
        dv = [v + shift for v in _devvals(i, len(fields))]
        rows.append(" ".join([str(i), f'"A{i}"'] + [f"{v:.4f}" for v in dv]
                             + ["50.0", "50.0", "50.0"]))
    text = ("CTI2   \n\nDESCRIPTOR \"Argyll Calibration Target chart information 2\"\n"
            "ORIGINATOR \"ChromIQ layout engine\"\n"
            f"COLOR_REP \"{rep}\"\n\nNUMBER_OF_FIELDS {len(head)}\n"
            f"BEGIN_DATA_FORMAT\n{' '.join(head)} \nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n"
            + _cal_block(rep, fields, cal) + _aim_block(rep, fields))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_ti3(path: Path, kind: str, n: int = 12, *, cal: str = "nan",
               ids: "list[int] | None" = None) -> Path:
    rep, fields = REPS[kind]
    head = ["SAMPLE_ID", "SAMPLE_LOC"] + fields + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    rows = []
    for i in (ids or range(1, n + 1)):
        dv = _devvals(i, len(fields))
        rows.append(" ".join([str(i), f'"A{i}"'] + [f"{v:.5f}" for v in dv]
                             + [f"{10 + i:.6f}", f"{11 + i:.6f}", f"{12 + i:.6f}"]))
    dev = rep.replace("i", "", 1) if rep.startswith("i") else rep
    text = ("CTI3   \n\nDESCRIPTOR \"Argyll Calibration Target chart information 3\"\n"
            "ORIGINATOR \"Argyll chartread\"\nCREATED \"Sat Oct  3 04:28:35 2026\"\n"
            f"DEVICE_CLASS \"OUTPUT\"\nCOLOR_REP \"{dev}_XYZ\"\n\n"
            f"NUMBER_OF_FIELDS {len(head)}\n"
            f"BEGIN_DATA_FORMAT\n{' '.join(head)} \nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
            + "\nEND_DATA\n" + (_cal_block(rep, fields, cal) if cal else ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _project(tmp_path: Path, kind: str = "CMYK", **ti3kw) -> "tuple[Path, Path]":
    """A project ``Test_01`` with runs/run1 holding the chart and a damaged
    measurement. Returns (ti3, ti2)."""
    root = tmp_path / "Test_01"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    run = root / "runs" / "run1"
    ti2 = _write_ti2(run / "Test_01.ti2", kind)
    ti3 = _write_ti3(run / "Test_01.ti3", kind, **ti3kw)
    return ti3, ti2


def _first_cal(path: Path) -> str:
    text = path.read_bytes().decode("latin-1")
    a, b = cal_repair._first_cal_span(text)
    return text[a:b]


# ---------------------------------------------------------------------------
# The repair itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", sorted(REPS))
def test_a_nan_table_is_replaced_by_the_charts_own(tmp_path, kind):
    ti3, ti2 = _project(tmp_path, kind)
    before = ti3.read_bytes()
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    assert rep is not None and rep.chart == ti2
    # exactly the chart's FIRST calibration table, byte for byte...
    assert _first_cal(ti3) == _first_cal(ti2)
    # ...and only that: the readings and every keyword are untouched
    head = before.decode("latin-1").split("\nCAL")[0]
    assert ti3.read_bytes().decode("latin-1").startswith(head)
    # printcal's aim table from the .ti2 is not carried into the measurement
    assert "Aim Target" not in ti3.read_text(encoding="latin-1")
    assert cal_repair.cal_table_damaged(ti3) is False


@pytest.mark.parametrize("how", ["garbage", "range", "zigzag"])
@pytest.mark.parametrize("kind", sorted(REPS))
def test_numeric_garbage_is_repaired_too(tmp_path, kind, how):
    """On another compiler the fault may leave numbers, not nan: a channel
    that is constant, outside 0..1 or not monotonic is no calibration."""
    ti3, ti2 = _project(tmp_path, kind, cal=how)
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is not None
    assert _first_cal(ti3) == _first_cal(ti2)


@pytest.mark.parametrize("kind", sorted(REPS))
def test_a_plausible_calibration_that_differs_is_left_alone(tmp_path, kind, caplog):
    """Data safety first (Basti, review of aad896d8): a measurement printed
    with ANOTHER real calibration over the same patches carries exactly that
    calibration; it is never overwritten with the chart's, only logged."""
    import logging
    ti3, _ti2 = _project(tmp_path, kind, cal="other")
    before = ti3.read_bytes()
    with caplog.at_level(logging.INFO, logger="workflow.cal_repair"):
        assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None
    assert ti3.read_bytes() == before
    assert not (ti3.parent / "old").exists()
    assert any("plausible calibration" in r.getMessage() for r in caplog.records)


def test_a_table_a_hair_outside_0_1_is_still_plausible():
    t = cal_repair._Table(["RGB_I", "RGB_R"],
                          [["0.0", "-0.0004"], ["0.5", "0.6"], ["1.0", "1.0005"]])
    assert cal_repair._plausible(t)
    t.rows[2][1] = "1.01"
    assert not cal_repair._plausible(t)


def test_a_falling_curve_is_still_monotonic():
    t = cal_repair._Table(["RGB_I", "RGB_R"],
                          [["0.0", "1.0"], ["0.5", "0.4"], ["1.0", "0.0"]])
    assert cal_repair._plausible(t)


def test_the_original_is_kept_in_the_runs_old_folder(tmp_path):
    ti3, _ti2 = _project(tmp_path)
    original = ti3.read_bytes()
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    want = ti3.parent / "old" / "2026-10-03_120000" / "Test_01.ti3"
    assert rep.archive == want
    assert want.read_bytes() == original


def test_the_file_keeps_its_date(tmp_path):
    ti3, _ti2 = _project(tmp_path)
    os.utime(ti3, (1_700_000_000, 1_700_000_000))
    cal_repair.repair_embedded_cal(ti3, when=WHEN)
    assert int(ti3.stat().st_mtime) == 1_700_000_000


def test_confirmed_marks_survive_the_repair(tmp_path):
    ti3, _ti2 = _project(tmp_path)
    cp.write(ti3, {"A3": {"kind": "confirmed", "de": 3.0, "prev_de": 2.9,
                          "exp_lab": [1, 2, 3], "meas_lab": [1, 2, 3],
                          "shift": [0, 0, 0], "standout": None}}, cp.MODE_STRIP)
    old_sha = cp.ti3_sha256(ti3)
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    assert rep.confirmed_kept
    assert cp.ti3_sha256(ti3) != old_sha
    assert cp.confirmed_locations(ti3) == {"A3"}
    # the original's memory is kept beside the original, for the original
    kept = cp.confirmed_path(rep.archive)
    assert json.loads(kept.read_text(encoding="utf-8"))["ti3_sha256"] == old_sha


def test_a_stale_memory_is_not_brought_back_to_life(tmp_path):
    """A memory that did not describe the file before must not after."""
    ti3, _ti2 = _project(tmp_path)
    cp.write(ti3, {"A3": {"kind": "confirmed", "de": 3.0}}, cp.MODE_STRIP)
    ti3.write_bytes(ti3.read_bytes() + b"\n")      # memory now stale
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    assert rep is not None and not rep.confirmed_kept
    assert cp.confirmed_locations(ti3) == set()


def test_nothing_happens_when_the_tables_already_agree(tmp_path):
    ti3, _ti2 = _project(tmp_path, cal="good")
    before = ti3.read_bytes()
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None
    assert ti3.read_bytes() == before
    assert not (ti3.parent / "old").exists()


def test_nothing_happens_without_a_calibration(tmp_path):
    ti3, _ti2 = _project(tmp_path, cal="")
    before = ti3.read_bytes()
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None
    assert ti3.read_bytes() == before


def test_a_different_chart_is_refused(tmp_path):
    """Same patch count, other device values: not the chart measured."""
    root = tmp_path / "P"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    run = root / "runs" / "run1"
    _write_ti2(run / "P.ti2", "CMYK", shift=5.0)
    ti3 = _write_ti3(run / "P.ti3", "CMYK")
    before = ti3.read_bytes()
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None
    assert ti3.read_bytes() == before
    assert not (run / "old").exists()


def test_a_chart_of_another_device_type_is_refused(tmp_path):
    root = tmp_path / "P"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    run = root / "runs" / "run1"
    _write_ti2(run / "P.ti2", "RGB")
    ti3 = _write_ti3(run / "P.ti3", "CMYK")
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None


def test_a_chart_without_some_measured_patch_is_refused(tmp_path):
    root = tmp_path / "P"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    run = root / "runs" / "run1"
    _write_ti2(run / "P.ti2", "CMYK", n=8)
    ti3 = _write_ti3(run / "P.ti3", "CMYK", n=12)
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None


def test_a_genuinely_different_calibration_shape_is_refused(tmp_path):
    """A table with another grid is not this chart's copy."""
    ti3, ti2 = _project(tmp_path)
    text = ti3.read_text(encoding="latin-1")
    a, b = cal_repair._first_cal_span(text)
    ti3.write_text(text[:a] + _cal_block("CMYK", REPS["CMYK"][1], "nan", nig=9),
                   encoding="latin-1")
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None


def test_a_partial_measurement_is_repaired(tmp_path):
    ti3, ti2 = _project(tmp_path, ids=[1, 2, 3, 7])
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is not None
    assert _first_cal(ti3) == _first_cal(ti2)


def test_a_copy_under_old_is_repaired_from_the_runs_chart(tmp_path):
    """'Build anyway' on old/<stamp>/<stem>.ti3 builds from that copy."""
    _ti3, ti2 = _project(tmp_path)
    copy = ti2.parent / "old" / "2026-10-02_230006" / "Test_01.ti3"
    _write_ti3(copy, "CMYK")
    rep = cal_repair.repair_embedded_cal(copy, when=WHEN)
    assert rep is not None and rep.chart == ti2
    assert rep.archive == ti2.parent / "old" / "2026-10-03_120000" / "Test_01.ti3"
    assert _first_cal(copy) == _first_cal(ti2)


def test_reads_are_repaired_and_archived_in_the_run_not_in_reads(tmp_path):
    _ti3, ti2 = _project(tmp_path)
    read = _write_ti3(ti2.parent / "reads" / "read1.ti3", "CMYK")
    rep = cal_repair.repair_embedded_cal(read, when=WHEN)
    assert rep is not None
    assert rep.archive.parent == ti2.parent / "old" / "2026-10-03_120000"
    assert not (ti2.parent / "reads" / "old").exists()


def test_a_verification_keeps_its_verify_marks(tmp_path):
    root = tmp_path / "Test_01"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    run = root / "runs" / "run1"
    _write_ti2(run / "Test_01.ti2", "RGB", shift=7.0)          # profiling chart
    vroot = run / "verifications"
    vti2 = _write_ti2(vroot / "Test_01-verify.ti2", "CMYK")
    vti3 = _write_ti3(vroot / "2026-10-01" / "Test_01-verify.ti3", "CMYK")
    cp.write(vti3, {"A2": {"kind": "confirmed", "de": 1.0}}, cp.MODE_PATCH)
    rep = cal_repair.repair_embedded_cal(vti3, when=WHEN)
    assert rep is not None and rep.chart == vti2
    assert cp.confirmed_path(vti3).name == "Test_01-verify.confirmed.json"
    assert cp.confirmed_locations(vti3) == {"A2"}
    # §2a: a verification's history stays inside verifications/, in its
    # date's old/, as the session guard keeps it.
    assert rep.archive.parent == (vroot / "2026-10-01" / "old"
                                  / "2026-10-03_120000")
    assert not (run / "old").exists()


def test_a_file_in_the_verifications_root_is_kept_in_verifications_old(tmp_path):
    root = tmp_path / "Test_01"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    vroot = root / "runs" / "run1" / "verifications"
    _write_ti2(vroot / "Test_01-verify.ti2", "CMYK")
    staged = _write_ti3(vroot / "Test_01-verify.ti3", "CMYK")
    rep = cal_repair.repair_embedded_cal(staged, when=WHEN)
    assert rep is not None
    assert rep.archive.parent == vroot / "old" / "2026-10-03_120000"


@pytest.mark.xfail(os.name == "nt", strict=False, reason=(
    "REAL_BUGS RB-2: Windows refuses os.replace over a read-only file, "
    "so the repair is skipped there; app fix awaits Basti's decision"))
def test_a_read_only_measurement_stays_read_only(tmp_path):
    ti3, ti2 = _project(tmp_path)
    os.chmod(ti3, 0o444)
    try:
        assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is not None
        assert _first_cal(ti3) == _first_cal(ti2)
        assert (ti3.stat().st_mode & 0o777) == 0o444
    finally:
        os.chmod(ti3, 0o644)


def test_a_linked_measurement_is_repaired_through_the_link(tmp_path):
    ti3, ti2 = _project(tmp_path)
    real = ti3.with_name("elsewhere.ti3")
    ti3.rename(real)
    ti3.symlink_to(real)
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is not None
    assert ti3.is_symlink(), "the link was replaced by a file of its own"
    assert _first_cal(real) == _first_cal(ti2)
    assert not list(ti3.parent.glob("*.cal-repair"))


def test_a_replaced_chart_is_found_under_old_chart(tmp_path):
    """The date's chart was replaced; the one measured is in old/<ts>/chart/."""
    root = tmp_path / "Test_01"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    date = root / "runs" / "run1" / "verifications" / "2026-10-01"
    _write_ti2(date / "chart" / "Test_01-verify.ti2", "CMYK", shift=3.0)
    measured = _write_ti2(date / "old" / "2026-10-02_101010" / "chart"
                          / "Test_01-verify.ti2", "CMYK")
    vti3 = _write_ti3(date / "Test_01-verify.ti3", "CMYK")
    rep = cal_repair.repair_embedded_cal(vti3, when=WHEN)
    assert rep is not None and rep.chart == measured


def test_a_failed_archive_changes_nothing(tmp_path, monkeypatch):
    ti3, _ti2 = _project(tmp_path)
    before = ti3.read_bytes()

    def boom(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(cal_repair.shutil, "copy2", boom)
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None
    assert ti3.read_bytes() == before


def test_a_resume_keeps_the_original_once(tmp_path):
    """The session guard archives the .ti3 at Start; the repair the reader
    asks for a moment later reuses that copy instead of keeping a second."""
    ti3, _ti2 = _project(tmp_path)
    original = ti3.read_bytes()
    guard = ti3.parent / "old" / "2026-10-03_120000"
    guard.mkdir(parents=True)
    (guard / ti3.name).write_bytes(original)
    cp.write(ti3, {"A3": {"kind": "confirmed", "de": 3.0}}, cp.MODE_STRIP)
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    assert rep is not None and rep.archive == guard / ti3.name
    assert sorted(p.name for p in guard.glob("*.ti3")) == [ti3.name]
    assert cp.confirmed_path(rep.archive).is_file()


def test_an_older_different_copy_is_not_taken_for_the_original(tmp_path):
    ti3, _ti2 = _project(tmp_path)
    guard = ti3.parent / "old" / "2026-10-01_090000"
    guard.mkdir(parents=True)
    (guard / ti3.name).write_bytes(b"CTI3\nsomething else\n")
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    assert rep.archive == ti3.parent / "old" / "2026-10-03_120000" / ti3.name


def test_outside_a_project_the_original_is_kept_beside_it(tmp_path):
    folder = tmp_path / "Desktop"
    ti2 = _write_ti2(folder / "x.ti2", "CMYK")
    ti3 = _write_ti3(folder / "x.ti3", "CMYK")
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    assert rep is not None
    assert rep.archive == folder / "old" / "2026-10-03_120000" / "x.ti3"
    assert _first_cal(ti3) == _first_cal(ti2)


def test_outside_a_project_an_unwritable_folder_means_no_repair(tmp_path, monkeypatch):
    folder = tmp_path / "Desktop"
    _write_ti2(folder / "x.ti2", "CMYK")
    ti3 = _write_ti3(folder / "x.ti3", "CMYK")
    before = ti3.read_bytes()
    real = os.access
    monkeypatch.setattr(cal_repair.os, "access",
                        lambda p, m: False if Path(p) == folder else real(p, m))
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is None
    assert ti3.read_bytes() == before
    assert not (folder / "old").exists()


def test_the_notifier_hears_each_repair_once(tmp_path):
    ti3, _ti2 = _project(tmp_path)
    heard = []
    cal_repair.set_notifier(heard.append)
    try:
        cal_repair.repair_embedded_cal(ti3, when=WHEN)
        cal_repair.repair_embedded_cal(ti3, when=WHEN)   # now a no-op
    finally:
        cal_repair.set_notifier(None)
    assert [r.ti3 for r in heard] == [ti3]


def test_the_notifier_does_not_keep_a_window_alive():
    import gc

    class W:
        def hear(self, rep):
            pass
    w = W()
    cal_repair.set_notifier(w.hear)
    del w
    gc.collect()
    assert cal_repair._notifier() is None
    cal_repair.set_notifier(None)


def test_the_forum_shaped_file_is_repaired(tmp_path):
    """The real shape of the forum user's file: a 256-step CMYK table of nan
    beside a .ti2 carrying printcal's three tables."""
    root = tmp_path / "Test_01"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    run = root / "runs" / "run1"
    ti2 = _write_ti2(run / "Test_01.ti2", "CMYK", n=450)
    text = ti2.read_text(encoding="utf-8")
    a, b = cal_repair._first_cal_span(text)
    ti2.write_text(text[:a] + _cal_block("CMYK", REPS["CMYK"][1], "good", 256)
                   + text[b:], encoding="utf-8")
    ti3 = _write_ti3(run / "Test_01.ti3", "CMYK", n=450, cal="")
    ti3.write_text(ti3.read_text(encoding="utf-8")
                   + _cal_block("CMYK", REPS["CMYK"][1], "nan", 256), encoding="utf-8")
    assert cal_repair.cal_table_damaged(ti3)
    assert cal_repair.repair_embedded_cal(ti3, when=WHEN) is not None
    assert _first_cal(ti3) == _first_cal(ti2)


# ---------------------------------------------------------------------------
# The message and the build-failed text
# ---------------------------------------------------------------------------

def test_the_message_renders_for_one_and_for_several(tmp_path):
    from workflow import measurement_messages as M
    ti3, _ti2 = _project(tmp_path)
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    t1, b1 = M.cal_table_repaired_texts([rep])
    # The path is shown in the system's own spelling (backslashes on Windows).
    assert os.path.join("Test_01", "runs", "run1", "Test_01.ti3") in b1
    assert os.path.join("Test_01", "runs", "run1", "old",
                        "2026-10-03_120000") in b1
    t2, b2 = M.cal_table_repaired_texts([rep, rep])
    assert t1 != t2
    for text in (t1, b1, t2, b2):
        assert "{" not in text and "}" not in text
        assert "—" not in text


def test_the_build_failure_blames_the_table_not_the_user(tmp_path):
    from workflow.profile_builder import ProfileBuilder
    ti3, _ti2 = _project(tmp_path)
    b = ProfileBuilder(MagicMock())
    b._ti3_path = ti3
    b._scan_line("colprof: Error - CGATS file read error : Error in file "
                 "'Test_01.ti3': Field 'CMYK_C' has unexpected type, should "
                 "be 'real', is 'non-quoted char string'")
    key, body = b.primary_failure()
    assert key == "cal_table_damaged"
    assert "Test_01.ti3" in body and "by hand" not in body


def test_other_read_errors_keep_their_text(tmp_path):
    from workflow.profile_builder import ProfileBuilder
    ti3, _ti2 = _project(tmp_path, cal="good")
    b = ProfileBuilder(MagicMock())
    b._ti3_path = ti3
    b._scan_line("colprof: Error - CGATS file read error : something else")
    key, body = b.primary_failure()
    assert key == "ti3_read" and "by hand" in body


# ---------------------------------------------------------------------------
# Every Argyll consumer of a .ti3 asks for the repair first
# ---------------------------------------------------------------------------

class _Stop(Exception):
    pass


@pytest.fixture
def asked(monkeypatch):
    """Record what each hook hands the repair, then stop before any tool."""
    seen: "list[Path]" = []

    def one(ti3, ti2=None, **_k):
        seen.append(Path(ti3))
        raise _Stop

    def many(paths):
        seen.extend(Path(p) for p in paths if p is not None)
        raise _Stop
    monkeypatch.setattr(cal_repair, "repair_embedded_cal", one)
    monkeypatch.setattr(cal_repair, "repair_all", many)
    return seen


def test_colprof_asks(tmp_path, asked):
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    runner = MagicMock()
    with pytest.raises(_Stop):
        ProfileBuilder(runner).build(ProfileParams(ti3_path=tmp_path / "a.ti3"),
                                     lambda _l: None, lambda _c: None)
    assert asked == [tmp_path / "a.ti3"]
    runner.run.assert_not_called()


def test_the_engine_asks(tmp_path, asked):
    from workflow.engine_builder import EngineProfileBuilder
    from workflow.profile_builder import ProfileParams
    with pytest.raises(_Stop):
        EngineProfileBuilder().build(ProfileParams(ti3_path=tmp_path / "a.ti3"),
                                     lambda _l: None, lambda _c: None)
    assert asked == [tmp_path / "a.ti3"]


def test_profcheck_asks(tmp_path, asked):
    from workflow.profcheck_runner import ProfcheckParams, ProfcheckRunner
    runner = MagicMock()
    with pytest.raises(_Stop):
        ProfcheckRunner(runner).run(
            ProfcheckParams(ti3_path=tmp_path / "a.ti3",
                            icc_path=tmp_path / "a.icc"),
            lambda _l: None, lambda _c: None)
    assert asked == [tmp_path / "a.ti3"]
    runner.run.assert_not_called()


def test_average_asks_for_every_input(tmp_path, asked):
    from workflow.average_runner import AverageParams, AverageRunner
    ins = [tmp_path / "read1.ti3", tmp_path / "read2.ti3"]
    with pytest.raises(_Stop):
        AverageRunner(MagicMock()).run(
            AverageParams(inputs=ins, output=tmp_path / "out.ti3"),
            lambda _l: None, lambda _p: None)
    assert asked == ins


def test_both_merges_ask_for_every_input(tmp_path, asked):
    from workflow import ti3_merge
    with pytest.raises(_Stop):
        ti3_merge.merge_preconditioning(tmp_path / "f.ti3", tmp_path / "p.ti3",
                                        tmp_path / "m.ti3")
    with pytest.raises(_Stop):
        ti3_merge.merge_measurements([tmp_path / "a.ti3", tmp_path / "b.ti3"],
                                     tmp_path / "m.ti3")
    assert asked == [tmp_path / "f.ti3", tmp_path / "p.ti3",
                     tmp_path / "a.ti3", tmp_path / "b.ti3"]


def test_colverify_asks_for_both_files(tmp_path, asked):
    from workflow.colverify_runner import ColverifyParams, ColverifyRunner
    with pytest.raises(_Stop):
        ColverifyRunner(MagicMock()).run(
            ColverifyParams(ref_ti3=tmp_path / "ref.ti3",
                            measured_ti3=tmp_path / "m.ti3"),
            lambda _l: None, lambda _c: None)
    assert asked == [tmp_path / "ref.ti3", tmp_path / "m.ti3"]


def test_printcal_asks(tmp_path, asked):
    from workflow.printcal_runner import PrintcalParams, PrintcalRunner
    with pytest.raises(_Stop):
        PrintcalRunner(MagicMock(), MagicMock()).run(
            PrintcalParams(ti3_path=tmp_path / "c.ti3"),
            lambda _l: None, lambda _p: None)
    assert asked == [tmp_path / "c.ti3"]


def test_a_resumed_measurement_asks_and_a_fresh_one_does_not(tmp_path, asked,
                                                             qapp):
    from workflow.measure_manager import MeasureManager, MeasureParams
    runner = MagicMock()
    mgr = MeasureManager(runner)
    ti1 = tmp_path / "Test_01.ti1"
    with pytest.raises(_Stop):
        mgr.start(MeasureParams(ti1_path=ti1, resume=True),
                  lambda _l: None, lambda _c: None)
    assert asked == [tmp_path / "Test_01.ti3"]
    runner.run.assert_not_called()
    mgr.start(MeasureParams(ti1_path=ti1, resume=False),
              lambda _l: None, lambda _c: None)
    assert asked == [tmp_path / "Test_01.ti3"]


# ---------------------------------------------------------------------------
# When the window may appear (review of aad896d8, on screen: a resume showed
# it beside the engine's own question, after the reader had started)
# ---------------------------------------------------------------------------

def _window_stub(monkeypatch, *, measuring, modal=None):
    from types import SimpleNamespace
    import PyQt6.QtWidgets as W
    import ui.main_window as mw
    import ui.warning_sign as ws
    shown, timers = [], []

    class Box:
        class StandardButton:
            Ok = 1

        def __init__(self, parent):
            self.texts = []

        def setWindowTitle(self, t):
            self.texts.append(t)

        setText = setInformativeText = setWindowTitle

        def setStandardButtons(self, _b):
            pass

        def exec(self):
            shown.append(self.texts)

    monkeypatch.setattr(W, "QMessageBox", Box)
    monkeypatch.setattr(ws, "set_information_icon", lambda _b: None)
    monkeypatch.setattr(W.QApplication, "activeModalWidget",
                        staticmethod(lambda: modal))
    monkeypatch.setattr(mw.QTimer, "singleShot",
                        staticmethod(lambda ms, fn: timers.append(ms)))
    stub = SimpleNamespace(_measuring=measuring, _cal_repairs_pending=[],
                           CAL_REPAIRED_RETRY_MS=400)
    stub._show_cal_tables_repaired = lambda: \
        mw.MainWindow._show_cal_tables_repaired(stub)
    return mw, stub, shown, timers


def test_the_window_waits_while_a_measurement_runs(tmp_path, monkeypatch):
    ti3, _ti2 = _project(tmp_path)
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    mw, stub, shown, timers = _window_stub(monkeypatch, measuring=True)
    stub._cal_repairs_pending = [rep]
    mw.MainWindow._show_cal_tables_repaired(stub)
    assert shown == [] and timers == [400], "shown over a running measurement"
    assert stub._cal_repairs_pending == [rep], "the repair was dropped"
    stub._measuring = False                     # the measurement has ended
    mw.MainWindow._show_cal_tables_repaired(stub)
    assert len(shown) == 1 and stub._cal_repairs_pending == []


def test_the_window_waits_for_another_window(tmp_path, monkeypatch):
    ti3, _ti2 = _project(tmp_path)
    rep = cal_repair.repair_embedded_cal(ti3, when=WHEN)
    mw, stub, shown, timers = _window_stub(monkeypatch, measuring=False,
                                           modal=object())
    stub._cal_repairs_pending = [rep]
    mw.MainWindow._show_cal_tables_repaired(stub)
    assert shown == [] and timers == [400]
