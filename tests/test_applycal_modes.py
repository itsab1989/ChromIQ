"""Apply Calibration's three modes, as applycal wants them (issue 217
verification, P1, 2026-11-21).

applycal's usage (ArgyllCMS 3.5.0): ``applycal [-options] [calfile.cal]
inprof.icc [outprof.icc]``: only applying takes the .cal. ChromIQ passed the
.cal to "Remove" and "Check" too, and applycal refused both with "Extra
argument" (exit 2): neither mode had ever worked. "Check" answers with its
exit code and, verbose, one line: 0 "Profile has NOT had calibration
applied", 1 "Profile has had calibration applied".

The first half needs no ArgyllCMS (the argument lists and how a check's
answer is read); the second runs real applycal on a copy of the repo's test
profile with a small OUTPUT calibration written here (every call has a
timeout; skipped without ArgyllCMS).
"""
from __future__ import annotations

import filecmp
import shutil
import subprocess
from pathlib import Path

import pytest

from workflow import applycal_runner as AR
from workflow.applycal_runner import ApplycalRunner

ROOT = Path(__file__).resolve().parents[1]
PROFILE = (ROOT / "tests/data/g_basti_et8550_run1_verify"
           / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26.icc")
CAL, IN, OUT = Path("c.cal"), Path("in.icc"), Path("out.icc")


@pytest.mark.parametrize("mode,verbose,want", [
    ("apply", False, ["c.cal", "in.icc", "out.icc"]),
    ("apply", True, ["-v", "c.cal", "in.icc", "out.icc"]),
    ("remove", False, ["-u", "in.icc", "out.icc"]),
    ("remove", True, ["-v", "-u", "in.icc", "out.icc"]),
    ("check", False, ["-v", "-c", "in.icc"]),
    ("check", True, ["-v", "-c", "in.icc"]),
])
def test_the_arguments_are_what_applycal_wants(mode, verbose, want):
    assert ApplycalRunner._build_args(CAL, IN, OUT, mode, verbose) == want


class _Stub:
    def __init__(self, code, lines):
        self.code, self.lines = code, lines

    def run(self, tool, args, cwd, on_line, on_finish):
        for ln in self.lines:
            on_line(ln)
        on_finish(self.code)


@pytest.mark.parametrize("code,lines,state", [
    (0, [AR._CHECK_NOT_APPLIED], AR.CHECK_NOT_APPLIED),
    (1, [AR._CHECK_APPLIED], AR.CHECK_APPLIED),
    (2, ["  Diagnostic: Extra argument 'in.icc'"], None),
    (1, ["argyll: Error - Can't open file 'in.icc'"], None),
])
def test_a_checks_answer_is_read_from_its_exit_and_its_line(code, lines,
                                                           state):
    r = ApplycalRunner(_Stub(code, lines), None)
    got = []
    r.run(CAL, IN, OUT, "check", False, lambda _l: None, got.append)
    assert r.check_state == state
    assert got == [OUT if state is not None else None]


# ---------------------------------------------------------------------------
# real ArgyllCMS
# ---------------------------------------------------------------------------

def _applycal() -> "str | None":
    p = Path("/Applications/Argyll/bin/applycal")
    return str(p) if p.is_file() else shutil.which("applycal")


def _output_cal(path: Path) -> Path:
    lines = ["CAL    ", "", 'DESCRIPTOR "Argyll Device Calibration Curves"',
             'ORIGINATOR "Argyll printcal"', 'DEVICE_CLASS "OUTPUT"',
             'COLOR_REP "RGB"', "", "NUMBER_OF_FIELDS 4",
             "BEGIN_DATA_FORMAT", "RGB_I RGB_R RGB_G RGB_B ",
             "END_DATA_FORMAT", "", "NUMBER_OF_SETS 256", "BEGIN_DATA"]
    for i in range(256):
        x = i / 255
        lines.append(f"{x:.6f} {x ** 1.1:.6f} {x ** 1.05:.6f} {x ** 0.95:.6f}")
    lines.append("END_DATA")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run(args, cwd) -> "tuple[int, str]":
    out = subprocess.run([_applycal(), *args], cwd=cwd, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=60)
    return out.returncode, out.stdout + out.stderr


@pytest.mark.skipif(_applycal() is None, reason="ArgyllCMS applycal missing")
def test_all_three_modes_work_with_real_applycal(tmp_path):
    shutil.copy(PROFILE, tmp_path / "in.icc")
    _output_cal(tmp_path / "c.cal")
    a = lambda *x: ApplycalRunner._build_args(  # noqa: E731
        Path("c.cal"), Path(x[0]), Path(x[1]), x[2], False)
    # check, before: no calibration
    code, text = _run(a("in.icc", "-", "check"), tmp_path)
    assert code == 0 and AR._CHECK_NOT_APPLIED in text, text
    # apply writes the file, and a check then finds the curves
    code, text = _run(a("in.icc", "cal.icc", "apply"), tmp_path)
    assert code == 0 and (tmp_path / "cal.icc").is_file(), text
    code, text = _run(a("cal.icc", "-", "check"), tmp_path)
    assert code == 1 and AR._CHECK_APPLIED in text, text
    # remove writes the file and gives back the profile exactly
    code, text = _run(a("cal.icc", "uncal.icc", "remove"), tmp_path)
    assert code == 0, text
    assert filecmp.cmp(tmp_path / "uncal.icc", tmp_path / "in.icc",
                       shallow=False)
    code, text = _run(a("uncal.icc", "-", "check"), tmp_path)
    assert code == 0 and AR._CHECK_NOT_APPLIED in text, text
    # what 4.3.54 passed for check and remove is refused (the old fault)
    code, text = _run(["-c", "c.cal", "cal.icc"], tmp_path)
    assert code == 2 and "Extra argument" in text


@pytest.mark.skipif(_applycal() is None, reason="ArgyllCMS applycal missing")
def test_the_tab_reports_a_real_check(tmp_path, qtbot, monkeypatch):
    """Apply Calibration's Check mode through the tab with real applycal:
    the log says what applycal found, no file is written, and the colour
    settings record stays as it was (V1)."""
    from PyQt6.QtCore import QCoreApplication

    from tests.test_the_new_profile_engine_is_one_switch import (
        _run_with_ti3, _tab)
    tab = _tab(tmp_path, profile_engine_beta=False)
    qtbot.addWidget(tab)
    tab._settings.set("argyll_bin_path", str(Path(_applycal()).parent))
    run, ti3 = _run_with_ti3(tab, tmp_path)
    icc = ti3.with_suffix(".icc")
    shutil.copy(PROFILE, icc)
    run.record_profile_build({"builder": "colprof", "profile": icc.name})
    before = run.load_meta().profile_build
    tab._ac_in_edit.setText(str(icc))
    tab._ac_cal_edit.setText("")                 # check needs no .cal
    tab._ac_mode_combo.setCurrentIndex(tab._ac_mode_combo.findData("check"))
    tab._on_applycal_run()
    qtbot.waitUntil(lambda: not tab._runner.is_running, timeout=60000)
    QCoreApplication.processEvents()
    log = tab._ac_log.toPlainText()
    assert "This profile has no calibration curves applied" in log, log
    assert "applycal failed" not in log
    assert not run.calibrated_icc.exists()
    assert run.load_meta().profile_build == before
