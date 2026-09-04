"""`ui.warning_sign.warn` replaced 51 `QMessageBox.warning` calls. A drop-in has
to be a drop-in in two ways the existing guard does not look at.

**1. It must not be fussier about `parent` than the static it replaced.**
`QMessageBox.warning(parent, …)` is a static helper; `warn` CONSTRUCTS a
`QMessageBox`, and a constructor is stricter. Measured the day the conversion
landed: three suite tests that had called these paths with a stand-in `self`
went red from inside the warning itself —

    TypeError: argument 1 has unexpected type 'types.SimpleNamespace'
    RuntimeError: super-class __init__() of type Ti2RelayoutDialog was never called

A warning is what the app reaches for when something has already gone wrong. It
must not be the thing that raises.

**2. Stubbing `QMessageBox.warning` no longer stubs anything.**
It was this suite's convention — `tests/conftest.py` still counts "41
`QMessageBox.warning`" among the modal entry points — and after the conversion
a test that stubs it opens a REAL modal instead. The conftest watchdog closes it
after four seconds and fails the test, so it is not a hang; it is four seconds
and a red test per occurrence, and the failure names the watchdog rather than
the stub. Three tests were found this way. The stub point is now the importing
module's own `warn` attribute (`monkeypatch.setattr(ui.tabs.tab_measure, "warn",
…)`), because every module does `from ui.warning_sign import warn`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def _no_modal(monkeypatch):
    """Answer every box instead of showing it, so these tests can call `warn`
    for real without a four-second watchdog sweep."""
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: QMessageBox.StandardButton.Ok)


def test_a_warning_survives_a_parent_that_is_not_a_widget(_app, _no_modal):
    import types

    from ui.warning_sign import warn
    got = warn(types.SimpleNamespace(), "Title", "Body")
    assert got is not None


def test_a_warning_survives_a_widget_whose_init_never_ran(_app, _no_modal):
    from ui.warning_sign import warn

    class _Half(QWidget):
        pass

    half = _Half.__new__(_Half)          # no QWidget.__init__ — as in the suite
    got = warn(half, "Title", "Body")
    assert got is not None


def test_a_real_parent_still_parents_the_box(_app, _no_modal):
    from ui.warning_sign import warn
    seen = {}
    real = QMessageBox.exec

    def spy(self):
        seen["parent"] = self.parent()
        return QMessageBox.StandardButton.Ok

    QMessageBox.exec = spy
    try:
        w = QWidget()
        warn(w, "Title", "Body")
    finally:
        QMessageBox.exec = real
    assert seen["parent"] is w, "the forgiving path must not drop a good parent"


_STATIC_STUB = re.compile(
    r"""setattr\(\s*QMessageBox\s*,\s*["']warning["']""")


def test_no_test_stubs_the_static_warning_any_more():
    """It is no longer the entry point, so such a stub is a silent no-op that
    lets a real modal open."""
    here = Path(__file__).resolve().parent
    offenders = []
    for f in sorted(here.glob("test_*.py")):
        if f.name == Path(__file__).name:
            continue
        for i, line in enumerate(f.read_text(errors="ignore", encoding="utf-8").splitlines(), 1):
            if _STATIC_STUB.search(line):
                offenders.append(f"{f.name}:{i}: {line.strip()}")
    assert not offenders, (
        "these stub `QMessageBox.warning`, which nothing calls any more — "
        "stub the importing module's own `warn` instead:\n  "
        + "\n  ".join(offenders))


def test_that_guard_can_actually_see_an_offence():
    """A guard that cannot fail guards nothing."""
    assert _STATIC_STUB.search(
        '    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)')
    assert _STATIC_STUB.search(
        "    monkeypatch.setattr(QMessageBox, 'warning', staticmethod(f))")
    assert not _STATIC_STUB.search(
        '    monkeypatch.setattr(tm, "warn", lambda *a: None)')
