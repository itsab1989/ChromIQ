"""The suite must survive a test that leaves `QMessageBox.exec` patched.

`exec` is INHERITED from `QDialog`, so the common way of faking a modal —
capture the attribute, replace it, put it back in a `finally` — does not put it
back. It installs a plain method object on `QMessageBox` which no longer binds,
and every later `box.exec()` **in that worker process** is then called with no
`self` and dies with

    TypeError: first argument of unbound method must have type 'QDialog'

The victim is whatever file xdist schedules next, so the failure names an
innocent test and reads as flakiness. It cost two full gates on 2026-08-08 —
the tests it broke passed alone and passed under `-n 4` alone.

Only TWO tests ever used that idiom, both migrated to `monkeypatch.setattr` on
2026-08-08; the other 68 patch sites always used monkeypatch, which restores an
inherited attribute correctly by deleting it. `tests/conftest.py` still repairs
the class in SETUP (`_repair_a_leaked_qmessagebox_exec`) as defence in depth,
because the broken idiom is an easy one to reach for again.
These two tests are the proof, and they depend on running in this order, which
`--dist loadfile` guarantees by keeping a file on one worker. Verified by
mutation: disabling the repair fails `test_b`.
"""
import PyQt6.QtWidgets as W


def test_a_leaves_exec_broken():
    """Reproduce the leak exactly as the two original offenders created it."""
    real = W.QMessageBox.exec
    W.QMessageBox.exec = lambda self: 0
    try:
        pass
    finally:
        W.QMessageBox.exec = real       # looks restored; is not
    assert "exec" in W.QMessageBox.__dict__, (
        "premise failed: QMessageBox should now carry a broken own 'exec'"
    )


def test_b_can_still_open_a_dialog(qapp):
    """The next test must be unharmed — this is the whole point of the repair."""
    from PyQt6.QtCore import QTimer

    assert "exec" not in W.QMessageBox.__dict__, (
        "the setup-time repair in conftest did not run; every dialog opened "
        "from here on would fail with \"must have type 'QDialog'\""
    )
    box = W.QMessageBox()
    box.setText("x")
    QTimer.singleShot(0, box.reject)
    box.exec()                          # the call that used to explode
