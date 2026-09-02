"""No scroll-bar signal in `ui/` may be connected to a lambda.

WHAT THIS GUARDS, AND HOW IT WAS MEASURED
-----------------------------------------
`ui/fade_scroll.py` used to carry, twice:

    scrollbar.rangeChanged.connect(lambda _mn, _mx: self._refresh_fade())

and that line crashed the process. SIGSEGV, `EXC_BAD_ACCESS ...
address=0x0000000000000020`; under lldb the faulting instruction is
`ldr x12, [x8]` with `x8 = 0x20` at `_PyEval_EvalFrameDefault+2108`, followed by
the load-check-increment that is a `Py_INCREF` — a refcount bump on a pointer
read from NULL+0x20 while PyQt6 6.11 was setting up the lambda's own frame
(`PyQtSlotProxy::unislot` -> `PyQtSlot::invoke` -> `PyQtSlot::call` ->
`_PyEval_Vector`).

It needs `rangeChanged` to be emitted RE-ENTRANTLY, which the shipped app does
on its own: `main.py` installs `CompositeAppFilter`, whose `ButtonFontFilter`
calls `relayout_around()` -> `layout.invalidate(); layout.activate()`
synchronously from inside an application event filter, so
`QScrollAreaPrivate::updateScrollBars()` ends up running inside itself and calls
`QAbstractSlider::setRange` a second time.

Bisected against a standalone reproduction that faulted on the eighth widget
build, every time, in about seven seconds:

    self-capturing lambda                  -> crash on build 8
    same lambda, slot body emptied to None -> crash on build 8
    a bound method instead                 ->  52 builds, clean
    a lambda capturing nothing             ->  52 builds, clean
    the fix, as committed                  -> 208 builds, clean (twice)

So it is not what the slot does, and not the re-entrancy by itself. It is PyQt6
being handed a Python closure over the very widget whose child scroll bar owns
the proxy that holds the closure. A bound method is the shape PyQt is built for:
a weak reference to the receiver, and Qt severing the connection when the
receiver goes.

WHY THE RULE IS THIS NARROW
---------------------------
`ui/` has 88 other `connect(lambda …)` calls and they are fine; banning the
idiom everywhere would be a large change nobody has evidence for. What IS
evidenced is `rangeChanged`, the signal `updateScrollBars` emits from inside
itself. Nothing else in `ui/` connects to it, so this rule costs nothing today
and catches the next person who reaches for the idiom there.

A wider rule — the whole `QAbstractSlider` family — was written first and taken
back out; see the note on `SLIDER_SIGNALS` below for what it condemned and why
that was the wrong trade.

It reads the AST, not the text, so the explanation quoted inside
`ui/fade_scroll.py`'s own docstring does not trip it.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

#: The one signal this was proved on. `rangeChanged` is what
#: `QScrollAreaPrivate::updateScrollBars()` emits, from inside itself, via
#: `QAbstractSlider::setRange` — that re-entrancy is half of the fault.
#:
#: THE WIDER SLIDER FAMILY WAS TRIED FIRST AND TAKEN BACK OUT. Adding
#: `valueChanged`, `sliderMoved`, `actionTriggered` condemns five existing
#: lambdas in `tab_measure`, `tab_chart`, `scanin_dialog`, `softproof_dialog`
#: and `measurement_report_dialog` — and every one of them is on a QSlider or a
#: spin box, not on a scroll bar, and none is on the re-entrant path. Demanding
#: five refactors on no evidence is how a guard gets deleted. `rangeChanged` is
#: what was measured, so `rangeChanged` is what is banned; nothing else in `ui/`
#: uses it, so the rule costs nothing today.
SLIDER_SIGNALS = frozenset({"rangeChanged"})

UI = pathlib.Path(__file__).resolve().parents[1] / "ui"


def _lambda_connections(tree: ast.AST):
    """Yield (signal_name, lineno) for every `<x>.<signal>.connect(lambda …)`."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "connect"):
            continue
        signal = node.func.value
        if not isinstance(signal, ast.Attribute):
            continue
        if signal.attr not in SLIDER_SIGNALS:
            continue
        for arg in node.args:
            if isinstance(arg, (ast.Lambda,)):
                yield signal.attr, node.lineno


def _ui_sources():
    return sorted(p for p in UI.rglob("*.py"))


@pytest.mark.parametrize("path", _ui_sources(), ids=lambda p: p.name)
def test_no_slider_signal_is_connected_to_a_lambda(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = list(_lambda_connections(tree))
    assert not offenders, (
        f"{path.relative_to(UI.parent)} connects a lambda to "
        + ", ".join(f"{sig} (line {ln})" for sig, ln in offenders)
        + ".\nA lambda on a scroll-bar signal SEGFAULTS this app — see this "
          "file's docstring and `FadeScrollArea._on_range_changed`. Give the "
          "class a small named method and connect that instead; a bound method "
          "is what PyQt keeps a weak reference to."
    )


def test_this_file_can_see_the_fault_it_guards():
    """Control — the scanner must actually catch the line that crashed.

    Not a proxy for it: the exact source that was in `ui/fade_scroll.py`.
    """
    was_the_crash = (
        "class FadeScrollArea:\n"
        "    def __init__(self):\n"
        "        self.verticalScrollBar().rangeChanged.connect(\n"
        "            lambda _mn, _mx: self._refresh_fade()\n"
        "        )\n"
    )
    found = list(_lambda_connections(ast.parse(was_the_crash)))
    assert found and found[0][0] == "rangeChanged", (
        "the scanner does not recognise the very line that segfaulted the "
        "process, so every assertion in this file is vacuous")


def test_the_scanner_does_not_ban_a_bound_method():
    """…and the fix must pass it, or the rule is unimplementable."""
    the_fix = (
        "class FadeScrollArea:\n"
        "    def __init__(self):\n"
        "        self.verticalScrollBar().rangeChanged.connect("
        "self._on_range_changed)\n"
    )
    assert list(_lambda_connections(ast.parse(the_fix))) == []


def test_the_scanner_leaves_other_signals_alone():
    """88 lambda connections in `ui/` are fine and must stay fine."""
    elsewhere = (
        "b.clicked.connect(lambda: self._go())\n"
        "combo.currentIndexChanged.connect(lambda i: self._pick(i))\n"
        "spin.valueChanged.connect(lambda v: self._set(v))\n"
    )
    assert list(_lambda_connections(ast.parse(elsewhere))) == []


def test_fade_scroll_is_actually_covered():
    """A parametrised sweep that silently collected nothing would pass.

    `ui/fade_scroll.py` is the module the crash was proved in; if it ever stops
    being in the swept set, this file has quietly stopped guarding anything.
    """
    names = {p.name for p in _ui_sources()}
    assert "fade_scroll.py" in names
    assert len(names) > 10, f"only {len(names)} ui modules were swept"


# ---------------------------------------------------------------------------
# …and the fades must still actually refresh. A guard that only reads source
# would be satisfied by deleting the connection altogether.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_a_range_change_still_refreshes_the_fades(qapp, monkeypatch):
    """`rangeChanged` -> `_refresh_fade`, through the bound method.

    The rule above is satisfied by a file with NO connection at all, which
    would leave the gradients frozen at whatever they were when the area was
    built — the fade would simply stop working and nothing would say so.
    """
    from ui.fade_scroll import FadeScrollArea

    area = FadeScrollArea()
    calls = []
    monkeypatch.setattr(FadeScrollArea, "_refresh_fade",
                        lambda self: calls.append(self), raising=True)
    area.verticalScrollBar().setRange(0, 500)
    assert calls, (
        "changing the scroll range no longer refreshes the fade overlays — "
        "the connection has been removed rather than converted")
    area.setParent(None)


def test_the_edge_fades_helper_still_refreshes_too(qapp, monkeypatch):
    """The same conversion was made in `EdgeFades`, which is attached to
    somebody else's scroll area (the measurement report's text view)."""
    from PyQt6.QtWidgets import QTextBrowser

    from ui.fade_scroll import EdgeFades

    view = QTextBrowser()
    calls = []
    fades = EdgeFades(view)
    monkeypatch.setattr(EdgeFades, "_refresh",
                        lambda self: calls.append(self), raising=True)
    view.verticalScrollBar().setRange(0, 500)
    assert calls, (
        "EdgeFades no longer refreshes on a range change")
    assert fades is not None
    view.setParent(None)
