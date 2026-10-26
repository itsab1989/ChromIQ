"""No QMessageBox may be shown without `keep_message_box_inside_the_work_area`.

4.3.16 (approved by Basti): about a hundred message boxes were built with
`QMessageBox(...)` and shown straight away, and nine more came from the static
`QMessageBox.critical`. None of them met the helper, so a long one was still
set all in bold on macOS and could open taller than the screen, its buttons
below the bottom edge. Every one of them now calls the helper once, after its
text and buttons are set and before it is shown (before the button fit too,
because a box the helper shortens gains a "Show Details" button that the fit
must size, and the layout Qt rebuilds for the details drops a spacer added
earlier).

This reads the app's source, so a box added later without the helper fails
here, with the file, the line and the function named. A real exception goes
into ALLOWED with the reason it is one; nothing else may be listed.
"""
from __future__ import annotations

import ast
import functools
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = "keep_message_box_inside_the_work_area"

#: (file, function) -> why that box does not call the helper before it is shown.
ALLOWED = {
    ("ui/tabs/tab_measure.py", "_show_verification_preflight_now"):
        "The verification pre-flight (design spec §21.3) is measured as the "
        "SHOWN window: on the first turn of its own exec it swaps in the "
        "one-line version when the full one does not fit, and only then calls "
        "the helper (in _fit_the_screen, and again in "
        "_scroll_the_preflight_text after the last-resort scroll area). "
        "Calling it before exec would size the wide version that is about to "
        "be replaced.",
}

#: Calls that show a box: its own methods, and the app's one-door wrappers
#: (`_ask` of the spot-read window, `_exec` of the earlier-profile offer,
#: `_exec_box` of the built-in presets window, the Measure tab's
#: `_exec_measurement_window`).
SHOW_METHODS = {"exec", "open", "show"}
SHOW_WRAPPERS = {"_ask", "_exec", "_exec_box", "_exec_measurement_window"}


def _app_files():
    for sub in ("ui", "core", "workflow"):
        yield from sorted((ROOT / sub).rglob("*.py"))
    yield ROOT / "main.py"


@functools.lru_cache(maxsize=None)
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _boxes():
    return _scan()


@functools.lru_cache(maxsize=1)
def _scan() -> tuple:
    return tuple(_scan_boxes())


def _scan_boxes():
    """(file, function, line, var, keep lines, first show line) per box."""
    for path in _app_files():
        rel = str(path.relative_to(ROOT))
        tree = _tree(path)
        parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}

        def enclosing(node):
            p = parents.get(node)
            while p is not None and not isinstance(
                    p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                p = parents.get(p)
            return p

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("QMessageBox", "_QMB")):
                continue
            fn = enclosing(node)
            stmt = parents.get(node)
            var = (stmt.targets[0].id if isinstance(stmt, ast.Assign)
                   and isinstance(stmt.targets[0], ast.Name) else None)
            keeps, shows = [], []
            for n in ast.walk(fn) if fn is not None else ():
                if not isinstance(n, ast.Call) or n.lineno <= node.lineno:
                    continue
                if enclosing(n) is not fn:
                    continue          # a nested def runs later, not here
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                on_var = (isinstance(f, ast.Attribute)
                          and isinstance(f.value, ast.Name) and f.value.id == var)
                takes_var = any(isinstance(a, ast.Name) and a.id == var
                                for a in n.args)
                if name == HELPER and takes_var:
                    keeps.append(n.lineno)
                elif (on_var and name in SHOW_METHODS) or (
                        takes_var and name in SHOW_WRAPPERS):
                    shows.append(n.lineno)
            yield (rel, getattr(fn, "name", "<module>"), node.lineno, var,
                   keeps, min(shows) if shows else None)


def test_the_scan_finds_the_boxes_it_is_meant_to_guard():
    """The mutation control: a scan that finds nothing proves nothing."""
    found = list(_boxes())
    assert len(found) >= 90, f"only {len(found)} QMessageBox constructions found"
    assert any(f == "ui/tabs/tab_measure.py" and fn == "_confirm_end_of_session"
               for f, fn, *_ in found)


def test_every_message_box_is_routed_once_before_it_is_shown():
    bad = []
    for rel, fn, line, var, keeps, show in _boxes():
        if (rel, fn) in ALLOWED:
            continue
        where = f"{rel}:{line} ({fn})"
        if var is None:
            bad.append(f"{where}: the box is not kept in a name, so nothing "
                       "can route it")
            continue
        if show is None:
            bad.append(f"{where}: `{var}` is never shown here; route it where "
                       "it is shown, and list the function in SHOW_WRAPPERS")
            continue
        before = [k for k in keeps if k < show]
        if not before:
            bad.append(f"{where}: `{var}` is shown at line {show} without "
                       f"{HELPER}({var}, ...) before it")
        elif len(before) > 1:
            bad.append(f"{where}: {HELPER} is applied {len(before)} times to "
                       f"`{var}` before it is shown (lines {before})")
    assert not bad, "\n".join(bad)


def test_the_helper_comes_before_the_button_fit():
    """A box the helper shortens gains "Show Details", and Qt builds it a new
    layout, which drops a spacer the fit added: so the fit comes after."""
    later = {"fit_message_box_buttons", "spread_message_box_buttons",
             "order_message_box_buttons", "widen_message_box"}
    bad = []
    for path in _app_files():
        rel = str(path.relative_to(ROOT))
        tree = _tree(path)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (rel, fn.name) in ALLOWED:
                continue
            calls = list(
                (n.lineno, getattr(n.func, "id", getattr(n.func, "attr", "")),
                 n.args[0].id if n.args and isinstance(n.args[0], ast.Name)
                 else None)
                for n in ast.walk(fn) if isinstance(n, ast.Call))
            calls.sort(key=lambda c: c[0])
            built = [(n.lineno, n.targets[0].id) for n in ast.walk(fn)
                     if isinstance(n, ast.Assign)
                     and isinstance(n.targets[0], ast.Name)
                     and isinstance(n.value, ast.Call)
                     and getattr(n.value.func, "id", "") in ("QMessageBox",
                                                             "_QMB")]
            for line, name, var in calls:
                if name != HELPER or var is None:
                    continue
                # only this box: from its own construction on (a function may
                # build several boxes in the same name)
                since = max([ln for ln, v in built if v == var and ln < line],
                            default=0)
                fitted_before = [ln for ln, nm, v in calls
                                 if nm in later and v == var
                                 and since < ln < line]
                if fitted_before:
                    bad.append(f"{rel}:{line} ({fn.name}): `{var}` is sized "
                               f"at {fitted_before} before the helper runs")
    assert not bad, "\n".join(bad)


def test_every_allowed_exception_still_exists_and_says_why():
    present = {(f, fn) for f, fn, *_ in _boxes()}
    for key, why in ALLOWED.items():
        assert key in present, f"{key} is allowed but no longer builds a box"
        assert len(why) > 40, f"{key} needs a real reason"


def test_no_class_inherits_qmessagebox_out_of_reach_of_the_scan():
    found = []
    for path in _app_files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ClassDef) and any(
                    getattr(b, "id", getattr(b, "attr", "")) == "QMessageBox"
                    for b in node.bases):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not found, ("a QMessageBox subclass is built without "
                       "`QMessageBox(...)`, so the guard above cannot see it: "
                       + ", ".join(found))
