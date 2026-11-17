"""NOTHING IN THE APP REACHES ``workflow.i1io.table`` YET (the i1iO table drive, build step 2).

The table modules moved into the app from the tester program chromiq-i1io-session 0.6.0 so that
the later steps can build on reviewed code. Until the owner approves the specification amendment
(``docs/design/i1io_table_support.md``) and the Beta's behaviour (build step 4), no code path of
the app may import or call them: no menu, no window, no setting. Two nets:

1. Statically: no Python file of the app outside the package (``main.py``, ``core/``, ``ui/``,
   ``workflow/``, ``scripts/``) imports it, at module level or inside a function, by any
   spelling (absolute, ``from workflow.i1io import table``, relative from ``workflow.i1io``,
   ``importlib`` with the name as a string).
2. At run time: a child process builds the real main window, with the i1iO Beta OFF and ON, opens
   Preferences, and with the Beta ON asks the Measure tab's Start check about an i1iO chart (the
   one place the drive will later hook in); ``workflow.i1io.table`` is never loaded.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "workflow.i1io.table"
TABLE_DIR = ROOT / "workflow" / "i1io" / "table"


def _app_files():
    files = [ROOT / "main.py"]
    for top in ("core", "ui", "workflow", "scripts"):
        files += sorted((ROOT / top).rglob("*.py"))
    return [f for f in files if TABLE_DIR not in f.parents and "__pycache__" not in f.parts]


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _targets(path: Path, tree) -> "list[str]":
    """Every module name an import statement in *tree* can bind (relative ones resolved)."""
    me = _module_name(path)
    pkg = me if path.name == "__init__.py" else me.rpartition(".")[0]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".")
                base = base[:len(base) - (node.level - 1)] if node.level > 1 else base
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            out.append(mod)
            out += [f"{mod}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.startswith(PACKAGE):           # importlib.import_module("...")
                out.append(node.value)
    return out


def test_the_package_exists_and_is_complete():
    assert {p.name for p in TABLE_DIR.glob("*.py")} == {
        "__init__.py", "session_table.py", "geometry.py", "lines.py", "scan.py", "reader.py",
        # build step 6: the job and its helpers (still reached by nothing in the app)
        "job.py", "caps.py", "usb_system.py", "diagnostics.py"}


def test_no_file_of_the_app_imports_the_table_package():
    offenders = []
    for f in _app_files():
        tree = ast.parse(f.read_text(encoding="utf-8"), str(f))
        for t in _targets(f, tree):
            if t == PACKAGE or t.startswith(PACKAGE + "."):
                offenders.append(f"{f.relative_to(ROOT)}: {t}")
    assert not offenders, offenders


def test_the_static_net_would_catch_every_spelling(tmp_path):
    """The net above, shown to fire (a net that never fires proves nothing)."""
    fake = ROOT / "workflow" / "i1io" / "__probe_spelling__.py"
    cases = ["import workflow.i1io.table.scan",
             "from workflow.i1io.table import scan",
             "from workflow.i1io import table",
             "from .table import scan",
             "from . import table",
             "def f():\n    from .table.session_table import Table",
             "import importlib\nimportlib.import_module('workflow.i1io.table.reader')"]
    for code in cases:
        hits = [t for t in _targets(fake, ast.parse(code))
                if t == PACKAGE or t.startswith(PACKAGE + ".")]
        assert hits, code


PROBE = r"""
import json, os, sys
sys.path.insert(0, os.environ["CHROMIQ_ROOT"])
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from ui.styles import WinButtonLayoutStyle
app.setStyle(WinButtonLayoutStyle("Fusion"))
from core.numeric_locale import pin_c_numeric_locale
pin_c_numeric_locale()
from core.settings import AppSettings
s = AppSettings()
s.set("custom_output_path", os.environ["CHROMIQ_PROBE_OUT"])
s.set("restore_last_session", False)
s.set("session_project", "")
on = os.environ["CHROMIQ_PROBE_BETA"] == "1"
s.set("i1io_support_beta", on)
from workflow.i1io.support import latch_from
assert latch_from(s) is on
from ui.main_window import MainWindow
win = MainWindow(s)
from ui.dialogs.settings_dialog import SettingsDialog
dlg = SettingsDialog(s, win)
asked = None
if on:
    tab = win._tab_measure
    shown = []
    tab._i1io_window = lambda title, body: shown.append(title)
    ti2 = os.environ["CHROMIQ_PROBE_CHART"]
    from pathlib import Path
    tab.set_ti1_path(Path(ti2[:-4] + ".ti1"))
    asked = [tab._refused_as_an_i1io_chart(), len(shown)]
loaded = sorted(m for m in sys.modules if m.startswith("workflow.i1io"))
print("PROBE" + json.dumps({"loaded": loaded, "asked": asked}), flush=True)
dlg.deleteLater(); win.close()
os._exit(0)
"""


def _chart(folder: Path) -> Path:
    ti2 = folder / "iochart.ti2"
    ti2.write_text(
        "CTI2\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        'TARGET_INSTRUMENT "X-Rite i1iO"\nCOLOR_REP "RGB"\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
        '1 "A1" 100 100 100 95 100 108\nEND_DATA\n', encoding="utf-8")
    ti2.with_suffix(".ti1").write_text(
        ti2.read_text(encoding="utf-8").replace("CTI2", "CTI1", 1), encoding="utf-8")
    return ti2


@pytest.mark.parametrize("beta", ["off", "on"])
def test_the_real_window_never_loads_the_table_package(tmp_path, beta):
    env = dict(os.environ)
    env.update(CHROMIQ_ROOT=str(ROOT), QT_QPA_PLATFORM="offscreen",
               CHROMIQ_SETTINGS_FILE=str(tmp_path / "settings.ini"),
               CHROMIQ_PROBE_OUT=str(tmp_path / "out"),
               CHROMIQ_PROBE_BETA="1" if beta == "on" else "0",
               CHROMIQ_PROBE_CHART=str(_chart(tmp_path)))
    try:
        r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, cwd=str(tmp_path),
                           timeout=600)
    except subprocess.TimeoutExpired:
        pytest.fail("the probe did not finish building the window in 600 s "
                    "(a loaded machine, or a window waiting for an answer)")
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("PROBE")), None)
    assert line, f"probe failed (exit {r.returncode}):\n{r.stderr[-3000:]}"
    got = json.loads(line[len("PROBE"):])
    assert not [m for m in got["loaded"] if m == PACKAGE or m.startswith(PACKAGE + ".")], got
    if beta == "on":
        # Start's i1iO check did run (and showed today's window), still without the package
        assert got["asked"] == [True, 1], got
        assert "workflow.i1io.support" in got["loaded"]
