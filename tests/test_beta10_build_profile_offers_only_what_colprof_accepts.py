"""Build Profile offers only what stock colprof accepts (beta 10, D-10).

Basti, 2026-10-04 (ProfileEngineResearch D-10): *"don't show d65m2 for stock
colprof ... the spinner should only allow values that colprof accepts."*

* ArgyllCMS 3.5.0 colprof takes -i / -f from "A, C, D50, D50M2, D65, F5, F8,
  F10 or file.sp" (-f also M0, M1, M2). "D65M2" stopped it with its usage
  text, exit 1, so no profile was built. It is gone from the lists, and a
  stored D65M2 reads as D65, with a log line.
* colprof -V accepts 1.0 to 3.0; both spinners allowed 4.0. A stored value
  above 3.0 is clamped and logged.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs import tab_profile as tp                       # noqa: E402

#: colprof 3.5.0's own -i list (usage text), and -f's (it adds M0, M1, M2).
COLPROF_I = {"A", "C", "D50", "D50M2", "D65", "F5", "F8", "F10"}


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_every_listed_illuminant_is_one_colprof_accepts():
    values = {v for _label, v in tp._ILLUMINANTS if v}
    assert "D65M2" not in values
    assert values <= COLPROF_I


def test_colprofs_own_usage_lists_them(tmp_path):
    """Read colprof's usage text (safe: no instrument, no input) when the
    binaries are here."""
    exe = shutil.which("colprof") or "/Applications/Argyll/bin/colprof"
    if not Path(exe).exists():
        pytest.skip("ArgyllCMS colprof is not installed here")
    out = subprocess.run([exe], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=30,
                         cwd=tmp_path)
    usage = out.stdout + out.stderr
    line = next(ln for ln in usage.splitlines()
                if "D50M2" in ln and "file.sp" in ln)
    assert "D65M2" not in line
    for v in COLPROF_I:
        assert v in line, v


def test_a_stored_d65m2_reads_as_d65_and_says_so(qapp, caplog):
    combo = tp._IlluminantCombo()
    for label, val in tp._ILLUMINANTS:
        combo.addItem(label, val)
    with caplog.at_level(logging.INFO, logger=tp.log.name):
        i = combo.findData("D65M2")
    assert i == combo.findData("D65") and i >= 0
    assert "D65M2" in caplog.text and "D65" in caplog.text
    assert combo.findData("A") >= 0 and combo.findData("nonsense") == -1


def test_the_dark_emphasis_spinner_stops_at_colprofs_limit(qapp, caplog):
    spin = tp._DarkEmphasisSpin()
    spin.setRange(1.0, tp.DARK_EMPHASIS_MAX)
    with caplog.at_level(logging.INFO, logger=tp.log.name):
        spin.setValue(4.0)
    assert spin.value() == 3.0 and spin.maximum() == 3.0
    assert "4.0" in caplog.text
    spin.setValue(2.5)
    assert spin.value() == 2.5


def test_the_build_profile_tab_uses_them():
    import inspect
    src = inspect.getsource(tp)
    assert src.count("_DarkEmphasisSpin(grp)") == 2
    assert "setRange(1.0, 4.0)" not in src
    for name in ("_m_illum_combo", "_m_fwa_illum_combo", "_illum_combo",
                 "_fwa_illum_combo"):
        assert f"self.{name} = _IlluminantCombo(" in src, name
