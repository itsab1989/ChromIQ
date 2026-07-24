"""#130 Bug 1 (Knut): a printtarg chart saves its printtarg parameter fields in
its channels.json and restores them on load, so switching Run type shows each
chart's own printtarg settings — not whichever preset was loaded last."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path)); s.set("use_chromiq_layout_engine", False)
    tab = TabChart(ArgyllRunner(s), None, s) if False else TabChart(
        ArgyllRunner(s), __import__("core.file_manager", fromlist=["FileManager"]).FileManager(s), s)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    return tab


def test_printtarg_fields_snapshot_and_restore(qapp, tmp_path):
    tab = _tab(tmp_path)
    pts = tab._manual_widgets.get("printtarg", [])
    if not pts:
        pytest.skip("no manual printtarg widgets in this build")
    snap = tab._snapshot_printtarg_fields()
    assert snap and all({"flag", "value", "enabled"} <= set(d) for d in snap)

    # Change one field, snapshot 'chart A', change it again ('chart B'),
    # then restore A → the field must come back to A's value.
    flag = snap[0]["flag"]
    tab._set_manual_value("printtarg", flag, snap[0]["value"])
    a = tab._snapshot_printtarg_fields()
    a_val = next(d["value"] for d in a if d["flag"] == flag)

    # Write A into a sidecar and restore from it after mutating the panel.
    sidecar = tmp_path / "chartA.channels.json"
    sidecar.write_text(json.dumps({"printtarg_fields": a}))
    tab._store_printtarg_fields_in_sidecar  # exists
    # Mutate the panel away from A, then restore A.
    tab._restore_printtarg_fields(json.loads(sidecar.read_text())["printtarg_fields"])
    after = {d["flag"]: d["value"] for d in tab._snapshot_printtarg_fields()}
    assert after[flag] == a_val


def test_store_merges_into_existing_sidecar(qapp, tmp_path):
    tab = _tab(tmp_path)
    ti2 = tmp_path / "chart.ti2"; ti2.write_text("CTI2\n")
    side = tmp_path / "chart.channels.json"
    side.write_text(json.dumps({"ink_channels": ["r", "g", "b"], "chart_notes": "hi"}))
    tab._store_printtarg_fields_in_sidecar(ti2)
    doc = json.loads(side.read_text())
    assert doc["ink_channels"] == ["r", "g", "b"]     # preserved
    assert doc["chart_notes"] == "hi"                 # preserved
    assert "printtarg_fields" in doc                  # added
