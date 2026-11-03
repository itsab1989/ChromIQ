"""Shared by the FD-9 test files: FD-9 support (Preferences > Beta) is OFF by
default, so a test of the FD-9 itself turns it on for this process first, and
its windows are recorded instead of shown (a modal in an offscreen run waits
for ever).

Import the fixtures into the test module::

    from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
"""
import pytest


@pytest.fixture(autouse=True)
def fd9_beta_on():
    from workflow.fd9 import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.fixture(autouse=True)
def fd9_windows(monkeypatch):
    """Every M-FD9-* window the mixin raises, as (id, rendered kwargs)."""
    shown = []

    def record(self, message, **kw):
        message.render(**kw)          # a placeholder left over fails here
        shown.append((message.id, kw))
        return None

    from ui.fd9_measurement import FD9MeasureMixin
    monkeypatch.setattr(FD9MeasureMixin, "_fd9_window", record)
    monkeypatch.setattr(FD9MeasureMixin, "_fd9_show_insert_window",
                        lambda self: shown.append(("M-FD9-INSERT-SHEET", {})))
    return shown
