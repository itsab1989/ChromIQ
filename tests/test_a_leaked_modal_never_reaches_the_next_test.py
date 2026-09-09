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


def test_the_snapshot_was_taken_before_collection(qapp):
    """The repair can only restore what it recorded, and it must have recorded
    the REAL objects: a snapshot taken after a test module patched one at
    import time would record the stub and repair a worker into the fault."""
    c = _conftest()
    recorded = {(o.__name__, n): v for o, n, v in c._PRISTINE_MODALS}
    assert len(recorded) == 5, (
        f"the snapshot holds {len(recorded)} entry points, not 5: {sorted(recorded)}"
    )
    for name in ("warning", "critical", "information", "question"):
        assert recorded[("QMessageBox", name)] is QMessageBox.__dict__[name]
    assert recorded[("QDialog", "exec")] is QDialog.__dict__["exec"]
