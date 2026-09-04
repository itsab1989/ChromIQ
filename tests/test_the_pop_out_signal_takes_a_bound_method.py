"""The pop-out's `finished` signal may never be handed a lambda that captures `self`.

WHY THIS FILE EXISTS SEPARATELY FROM THE SCROLL-BAR GUARD
---------------------------------------------------------
`test_a_scrollbar_signal_never_takes_a_lambda.py` guards scroll bars, because a
scroll bar is where this crash was first paid for: `ui/fade_scroll.py` connected
`rangeChanged` to a lambda capturing `self`, and PyQt6 6.11 faulted invoking that
closure when the signal was emitted re-entrantly — SIGSEGV, `EXC_BAD_ACCESS`
at `address=0x20`, a `Py_INCREF` on a pointer read from NULL+0x20.

But scroll bars were never the hazard. The hazard is the OWNERSHIP CYCLE: a
Python closure holding `self`, stored inside a C++ object that `self` owns, on a
signal that object emits. `ScannerProfileDialog._toggle_popout` had exactly that
shape on its pop-out window's `finished` — a different widget, a different
signal, the same cycle — and the scroll-bar guard is scoped so that it could
never have seen it.

So this is not a copy of that test with the noun changed. It marks the second
place the shape was found, and it is deliberately written against the
CONNECTION rather than against a file, so that renaming or moving the dialog
does not quietly retire it.

THE FIX IT PINS
---------------
A bound method. PyQt keeps a WEAK reference to a bound receiver and lets Qt
sever the connection when the receiver dies, instead of parking a Python
closure inside a C++ object on the far side of the cycle.
"""
import ast
import inspect
import textwrap

from ui.dialogs.scanin_dialog import ScannerProfileDialog


def _connect_calls(func):
    """Every ``<something>.connect(arg)`` in ``func``, as ``(receiver, arg)``."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "connect"
                and node.args):
            out.append((ast.unparse(node.func.value), node.args[0]))
    return out


def test_the_pop_out_signal_takes_a_bound_method_not_a_lambda():
    calls = _connect_calls(ScannerProfileDialog._toggle_popout)
    finished = [(recv, arg) for recv, arg in calls if recv.endswith("finished")]
    assert finished, (
        "no `finished.connect(...)` in _toggle_popout any more. If the pop-out "
        "stopped signalling its close, delete this test deliberately — do not "
        "let it pass by finding nothing.")
    for recv, arg in finished:
        assert not isinstance(arg, ast.Lambda), (
            f"`{recv}.connect(...)` was handed a lambda.\n\n"
            "The pop-out is a window this dialog OWNS, and `finished` is a "
            "signal it emits, so a lambda capturing `self` closes a reference "
            "cycle through a C++ object — the shape CLAUDE.md records as "
            "faulting PyQt6 6.11 (SIGSEGV, Py_INCREF on NULL+0x20).\n\n"
            "Use a bound method: `self._popout.finished.connect(self._dock_marquee)`.")


def test_the_slot_it_names_exists_and_can_take_the_signals_argument():
    """A bound method that does not exist, or cannot be called with what the
    signal carries, fails at RUNTIME on a window nobody opens in a hurry. The
    connection above is only safe if this holds, so it is checked here rather
    than assumed."""
    calls = _connect_calls(ScannerProfileDialog._toggle_popout)
    named = [ast.unparse(arg) for recv, arg in calls if recv.endswith("finished")]
    assert named, "nothing connected to finished"
    for expr in named:
        attr = expr.rsplit(".", 1)[-1]
        slot = getattr(ScannerProfileDialog, attr, None)
        assert callable(slot), f"_toggle_popout connects `{expr}`, which is not callable"
        params = [p for p in inspect.signature(slot).parameters
                  if p != "self"]
        # `finished` carries an int. PyQt will call a slot that takes fewer
        # arguments, but NOT one that requires more than it can supply.
        required = [p for p in inspect.signature(slot).parameters.values()
                    if p.name != "self" and p.default is inspect.Parameter.empty
                    and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        assert len(required) <= 1, (
            f"`{expr}` requires {len(required)} arguments {[p.name for p in required]}, "
            f"but `finished` supplies at most one (an int). Qt would raise at "
            f"emit time, when the user closes the pop-out.")
        del params
