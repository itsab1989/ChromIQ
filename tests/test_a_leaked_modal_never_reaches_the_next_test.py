"""The repair that keeps one file's modal stub out of the next file.

A test file that patches a modal entry point with a bare `setattr` and never
puts it back hands every file xdist schedules onto the same worker afterwards a
UI with no modal dialogs. It happened, and it turned the release gate into a
coin toss: `12620 passed` on one `--runslow` run and `25 failed` on the next,
from an unchanged tree, decided only by how `--dist loadfile` happened to order
the files.

`conftest.py::_repair_a_leaked_qmessagebox_exec` is the containment, and the
first version of it that covered the whole family DELETED the four
`QMessageBox` statics instead of restoring them, which destroyed them for the
rest of the worker and failed four innocent tests. Both mistakes are the same
mistake -- assuming what the repair does instead of measuring it -- so this
file leaks each entry point exactly as the real file did and checks what comes
back.
"""
import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox


def _conftest():
    """The conftest module PYTEST loaded, not a second copy of it.

    `import conftest` in a test finds a fresh import whose module globals were
    never touched by `pytest_configure`, so its snapshot list is empty and the
    repair it exposes is not the one that runs. The project has already lost a
    test to that trap once. Ask `sys.modules` for the module whose `__file__`
    is the real `tests/conftest.py` instead.
    """
    import pathlib
    import sys

    want = pathlib.Path(__file__).with_name("conftest.py").resolve()
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if f and pathlib.Path(f).resolve() == want and hasattr(
                mod, "_restore_the_modal_entry_points"):
            return mod
    raise AssertionError(f"pytest's own {want} is not in sys.modules")


@pytest.mark.parametrize("name", ["warning", "critical", "information",
                                  "question"])
def test_a_leaked_qmessagebox_static_is_put_back_not_deleted(qapp, name):
    real = QMessageBox.__dict__[name]
    try:
        setattr(QMessageBox, name, staticmethod(lambda *a, **k: 0))  # the leak
        assert QMessageBox.__dict__[name] is not real, (
            "the leak did not land, so this test proves nothing"
        )
        _conftest()._restore_the_modal_entry_points()
        assert name in QMessageBox.__dict__, (
            f"the repair DELETED QMessageBox.{name}; PyQt defines it, so there "
            "is nothing left to inherit and every later test in this worker "
            "dies with AttributeError"
        )
        assert QMessageBox.__dict__[name] is real, (
            f"QMessageBox.{name} is still the stub after the repair"
        )
    finally:
        setattr(QMessageBox, name, real)


def test_a_leaked_qdialog_exec_is_put_back(qapp):
    real = QDialog.__dict__["exec"]
    try:
        QDialog.exec = lambda self: 1                  # the leak
        assert QDialog.__dict__["exec"] is not real
        _conftest()._restore_the_modal_entry_points()
        assert QDialog.__dict__["exec"] is real, (
            "QDialog.exec is still the stub, so every dialog opened by a later "
            "file in this worker returns 1 without being shown"
        )
    finally:
        QDialog.exec = real


def test_a_leaked_qmessagebox_exec_is_deleted_because_it_is_inherited(qapp):
    """The one member that IS repaired by deletion, and why the two cannot
    share a rule: `exec` is not defined on `QMessageBox` at all, so a copy in
    its `__dict__` is by definition the leak -- and the copy no longer binds,
    which is what produced `TypeError: first argument of unbound method must
    have type 'QDialog'` in whatever file ran next."""
    assert "exec" not in QMessageBox.__dict__, (
        "something already leaked QMessageBox.exec into this worker"
    )
    QMessageBox.exec = QDialog.__dict__["exec"]        # the classic idiom
    assert "exec" in QMessageBox.__dict__
    _conftest()._restore_the_modal_entry_points()
    assert "exec" not in QMessageBox.__dict__, (
        "the copy is still on QMessageBox, so box.exec() is called with no self"
    )
    box = QMessageBox()
    assert callable(box.exec), "QMessageBox.exec no longer resolves"


def test_the_snapshot_recorded_pyqt_s_own_objects(qapp):
    """The snapshot must hold what PyQt installed, not what a test left behind.

    THE FIRST VERSION OF THIS TEST WAS CIRCULAR AND WAS CAUGHT BY A REVIEWER.
    It asserted `recorded[name] is QMessageBox.__dict__[name]`, which the repair
    in this very test's SETUP has just made true by writing every recorded
    object back onto the class -- so it held whether the recording happened in
    `pytest_configure` or a microsecond earlier from an already-poisoned class.
    Measured: with the snapshot moved to a lazy call inside the repair, a
    throwaway file that patches `QMessageBox.warning` at IMPORT time (during
    collection) poisons the worker for the rest of its life, an honest probe in
    a later file sees a `staticmethod` where PyQt puts a descriptor, and this
    file still reported 7 passed.

    So compare against a source the suite cannot have touched: a FRESH
    interpreter. What comes back is what PyQt installs on a clean import, and a
    snapshot taken too late records a Python object instead.
    """
    import json
    import os
    import subprocess
    import sys

    c = _conftest()
    assert c._PRISTINE_MODALS, (
        "the snapshot is empty, so the repair has nothing to put back"
    )

    prog = (
        "from PyQt6.QtWidgets import QDialog, QMessageBox\n"
        "import json\n"
        "print(json.dumps({\n"
        "    'QMessageBox.' + n: type(QMessageBox.__dict__[n]).__name__\n"
        "    for n in ('warning', 'critical', 'information', 'question')}\n"
        "    | {'QDialog.exec': type(QDialog.__dict__['exec']).__name__}))\n"
    )
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    # Budgeted for a LOADED machine, not an idle one: this costs well under a
    # second alone, and the gate saturates every core.
    try:
        out = subprocess.run([sys.executable, "-c", prog], env=env,
                             capture_output=True, encoding="utf-8",
                             timeout=180)
    except subprocess.TimeoutExpired:
        pytest.fail("the clean-interpreter probe did not finish in 180 s")
    assert out.returncode == 0, out.stderr[-2000:]
    clean = json.loads(out.stdout.strip().splitlines()[-1])

    for owner, name, val in c._PRISTINE_MODALS:
        key = f"{owner.__name__}.{name}"
        assert type(val).__name__ == clean[key], (
            f"the snapshot recorded a {type(val).__name__} for {key} where a "
            f"clean interpreter has a {clean[key]}; it was taken after "
            "something had already patched the class, so the repair would "
            "reinstall that patch on every test instead of removing it"
        )
