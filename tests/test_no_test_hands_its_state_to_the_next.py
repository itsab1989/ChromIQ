"""Three leaks from one test into whichever test the same worker ran next,
found 2026-10-03 while the beta-7 gates kept turning red with tests that pass
alone. Each one is closed where it happened; this file keeps them closed.

1. ``importlib.reload`` of an application module inside the test process
   (``tests/test_hex_overlay_geometry.py`` reloaded ``ui.tabs.tab_measure``).
   A reload makes a NEW ``TabMeasure`` class; files imported before it keep the
   old one, so their ``monkeypatch.setattr(TabMeasure, ...)`` patches a class
   their tabs are not instances of. All three Measure-tab tests of
   ``test_replacing_a_stored_chart_keeps_the_old_one.py`` went red together.
2. A file written into ``tmp_path / ".."``, the worker's shared basetemp
   (two #182 files). ``build_report`` pairs a ``.ti3`` with a ``.ti2`` one and
   two folders up, so a later ``c.ti3`` read that ``c.ti2`` as its design
   reference: ``test_report_without_reference_uses_device_values`` got
   "design" for "device". `tests/conftest.py::
   _nothing_is_written_beside_the_tests_own_folders` now fails the writer.
3. The calibration-repair notifier of a MainWindow an earlier test had closed
   but the (deferred) collector had not yet freed: `test_cal_repair.py`'s
   repairs opened its real message box, and the modal watchdog failed a test
   with "a modal dialog was left open". `tests/conftest.py::
   _no_main_window_hears_another_tests_repair` clears it before every test.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent
APP_PACKAGES = ("ui", "core", "workflow", "data", "scripts")

#: Files allowed to reload an application module in-process, and why.
RELOAD_ALLOWED = {
    # Reloads core.platform_paths under a patched sys.platform. The module
    # holds no class and no state (one string constant), and nothing else
    # monkeypatches it, so a reload cannot split an identity.
    "test_platform_paths.py",
}


def _tree(path: Path):
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:          # pragma: no cover - the suite would not run
        return None


def _is_reload(call: ast.Call) -> bool:
    f = call.func
    return ((isinstance(f, ast.Attribute) and f.attr == "reload"
             and isinstance(f.value, ast.Name) and f.value.id == "importlib")
            or (isinstance(f, ast.Name) and f.id == "reload"))


def _imports_app_module(tree) -> bool:
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        if any(n.split(".")[0] in APP_PACKAGES for n in names):
            return True
    return False


def test_no_test_reloads_an_application_module_in_process():
    """Leak 1. A reload inside a string run by a CHILD process is fine (the
    AST does not see it); one in this process splits class identities for
    every file the worker runs afterwards. Patch with ``monkeypatch``."""
    found = []
    for path in sorted(TESTS.rglob("test_*.py")):
        if path.name in RELOAD_ALLOWED:
            continue
        tree = _tree(path)
        if tree is None or not _imports_app_module(tree):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_reload(node):
                found.append(f"{path.relative_to(TESTS.parent)}:{node.lineno}")
    assert not found, (
        "importlib.reload of an application module inside the test process "
        "replaces its classes for every later test of the worker; use "
        f"monkeypatch instead: {found}")


def _is_tmp_path(node) -> bool:
    return isinstance(node, ast.Name) and node.id in ("tmp_path", "tmpdir")


def test_no_test_writes_beside_its_own_tmp_path():
    """Leak 2, by its source shape: ``tmp_path / ".."`` and
    ``tmp_path.parent / "<fixed name>"`` both point into the worker's shared
    basetemp. (A uniquely named sibling such as ``f"{tmp_path.name}-away"``
    cannot collide with anything, and is allowed.)"""
    found = []
    for path in sorted(TESTS.rglob("test_*.py")):
        tree = _tree(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                    and isinstance(node.right, ast.Constant)
                    and isinstance(node.right.value, str)):
                continue
            left = node.left
            up = (_is_tmp_path(left) and node.right.value in ("..", "../")) or (
                isinstance(left, ast.Attribute) and left.attr == "parent"
                and _is_tmp_path(left.value))
            if up:
                found.append(f"{path.relative_to(TESTS.parent)}:{node.lineno}")
    assert not found, (
        "these write into the worker's shared basetemp, where every later "
        f"test's tmp_path sits; use a subfolder of tmp_path: {found}")


class _ClosedWindow:
    """Stands in for a MainWindow a test closed and the collector has not
    reached yet: alive, and registered."""

    def __init__(self) -> None:
        self.heard: list = []

    def _on_cal_table_repaired(self, rep) -> None:
        self.heard.append(rep)


_KEPT_ALIVE: list = []


def test_a_window_registers_for_repairs_and_is_left_alive():
    """Leak 3, performed on purpose, as MainWindow.__init__ does it."""
    from workflow import cal_repair
    w = _ClosedWindow()
    _KEPT_ALIVE.append(w)                 # the uncollected cycle
    cal_repair.set_notifier(w._on_cal_table_repaired)
    assert cal_repair._notifier() is not None


def test_the_next_test_is_heard_by_nobody():
    """…and the next test in the same worker starts with nobody listening,
    though that window is still alive."""
    from workflow import cal_repair
    assert _KEPT_ALIVE, "run in file order: the test above must run first"
    assert cal_repair._notifier is None or cal_repair._notifier() is None, (
        "a window an earlier test left alive still hears this test's "
        "calibration repairs, and would open its message box in this test")
    _KEPT_ALIVE.clear()
