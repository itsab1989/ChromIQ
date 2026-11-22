"""Final fix round, M-1: every table test is also a walk through its questions. The job's motion
guard refuses a movement line while a hands-off confirmation is owed after an answered question
(``job.HANDS_OFF_BREACHES``); a test in which that ever happened fails here, whatever it asserted
itself. A test that plants the breach on purpose clears the list itself.

The job module is never imported here (some tests check what is imported): only looked up."""
from __future__ import annotations

import sys

import pytest

_JOB = "workflow.i1io.table.job"
_WIN = "ui.i1io_table_window"


@pytest.fixture(autouse=True)
def _no_move_without_the_hands_off_confirmation():
    mod = sys.modules.get(_JOB)
    if mod is not None:
        mod.HANDS_OFF_BREACHES.clear()
    yield
    mod = sys.modules.get(_JOB)
    if mod is None:
        return
    breaches = list(mod.HANDS_OFF_BREACHES)
    mod.HANDS_OFF_BREACHES.clear()
    assert not breaches, ("a movement was refused because it followed an answered question "
                          f"without the hands-off confirmation: {breaches}")


@pytest.fixture(autouse=True)
def _hands_off_answers_pressable_at_once(request):
    """Review 14, S-1: the window holds an answer that IS the hands-off confirmation for
    ``HANDS_OFF_READY_MS`` (0.6 s) after its page is shown. The scripted person of these walks
    presses the moment a page is there, which stands for a person who waited: the walks check
    WHICH answers lead to a move, not how fast a person clicks. A test about the hold itself
    asks for ``hands_off_hold`` and gets the shipped 0.6 s. (Looked up, never imported here.)"""
    if "hands_off_hold" in request.fixturenames:
        yield
        return
    mod = sys.modules.get(_WIN)
    if mod is not None:
        if not hasattr(mod, "HANDS_OFF_READY_MS"):
            yield
            return
        old = mod.HANDS_OFF_READY_MS
        mod.HANDS_OFF_READY_MS = 0
        try:
            yield
        finally:
            mod.HANDS_OFF_READY_MS = old
        return
    # 4.3.57 part C: not imported yet. The first test of a fresh worker that opens the window
    # imports it DURING the test, so the look-up above found nothing and the shipped 0.6 s hold
    # stayed: the person pressed a held answer and failed ([manual] of
    # test_window_in_the_measure_tab, red alone and green in the gate only by file order).
    # Zero it the moment it is imported, still without importing it here.
    finder = _ZeroHoldOnImport()
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        try:
            sys.meta_path.remove(finder)
        except ValueError:
            pass
        mod = sys.modules.get(_WIN)
        if finder.zeroed and mod is not None:
            mod.HANDS_OFF_READY_MS = finder.shipped


class _ZeroHoldOnImport:
    """A meta path finder that only watches for the window module: it lets the normal finders
    find it, then sets ``HANDS_OFF_READY_MS`` to 0 right after the module has run."""

    def __init__(self):
        self.zeroed = False
        self.shipped = None

    def find_spec(self, fullname, path=None, target=None):
        if fullname != _WIN:
            return None
        import importlib.machinery
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec is None or spec.loader is None:
            return spec
        loader, watcher = spec.loader, self

        class _Loader:
            def create_module(self, spec):
                return loader.create_module(spec)

            def exec_module(self, module):
                loader.exec_module(module)
                if hasattr(module, "HANDS_OFF_READY_MS"):
                    watcher.shipped = module.HANDS_OFF_READY_MS
                    module.HANDS_OFF_READY_MS = 0
                    watcher.zeroed = True

        spec.loader = _Loader()
        return spec


@pytest.fixture
def hands_off_hold():
    """The shipped hold of the hands-off answers (review 14, S-1)."""
    import importlib
    mod = importlib.import_module(_WIN)
    assert mod.HANDS_OFF_READY_MS == 600
    return mod.HANDS_OFF_READY_MS
