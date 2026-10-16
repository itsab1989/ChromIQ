"""No class in the app defines the same method twice (dup1, 4.3.5 beta 9).

Python keeps the LAST definition of a name in a class body and drops the
earlier one without a word. Four were found by an AST scan on 2026-10-16:

* ``MeasurementTargetBar.resizeEvent``: the first one, which re-pinned the
  selection row when the width changed (``_pin_row_when_alone``, added
  2026-08-05), never ran, because an older one further down that only
  re-elided the location line replaced it;
* ``MeasurementTargetBar.showEvent``: the first one re-fitted the boxes on
  every show, the second only on the first;
* ``TabChart._tc918_tooltip`` and ``Project.run``: identical copies.

Each pair is merged so no behaviour is lost. This keeps it that way: any
class in ``ui/``, ``workflow/`` or ``core/`` that binds the same method name
twice fails here, naming the file, the class and both lines. Property
setters and deleters (``@x.setter`` re-using the getter's name) and
``@overload`` stubs are the legitimate ways to repeat a name and are allowed.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("ui", "workflow", "core")


def _decorator_allows_repeat(dec: ast.expr) -> bool:
    text = ast.unparse(dec)
    return (text.endswith((".setter", ".deleter", ".getter"))
            or text in ("overload", "typing.overload"))


def duplicate_methods(source: str, filename: str = "<src>") -> list[str]:
    """Every method a class body binds twice, as readable lines."""
    found = []
    tree = ast.parse(source, filename)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        first: dict[str, int] = {}
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_decorator_allows_repeat(d) for d in item.decorator_list):
                continue
            if item.name in first:
                found.append(f"{filename}: {node.name}.{item.name} is defined "
                             f"at line {first[item.name]} and again at line "
                             f"{item.lineno}; only the second one runs")
            else:
                first[item.name] = item.lineno
    return found


def test_no_class_in_the_app_defines_a_method_twice():
    problems = []
    for pkg in PACKAGES:
        for path in sorted((ROOT / pkg).rglob("*.py")):
            rel = str(path.relative_to(ROOT))
            problems += duplicate_methods(path.read_text(encoding="utf-8"), rel)
    assert not problems, "\n".join(problems)


def test_the_scan_finds_a_duplicate_and_spares_a_property_setter():
    src = (
        "class A:\n"
        "    def f(self): return 1\n"
        "    @property\n"
        "    def p(self): return 1\n"
        "    @p.setter\n"
        "    def p(self, v): pass\n"
        "    def f(self): return 2\n"
        "class B:\n"
        "    def f(self): return 3\n"
    )
    assert duplicate_methods(src) == [
        "<src>: A.f is defined at line 2 and again at line 7; "
        "only the second one runs"]


def test_the_scan_looks_inside_nested_classes():
    src = ("def outer():\n"
           "    class Inner:\n"
           "        def g(self): pass\n"
           "        def g(self): pass\n")
    assert len(duplicate_methods(src)) == 1


def test_the_merged_bar_still_pins_on_resize_and_fits_on_every_show():
    """The two merges keep both halves (dup1): read from the class, so a
    later edit that drops one half again fails here."""
    from ui.measurement_target_bar import MeasurementTargetBar
    import inspect
    resize = inspect.getsource(MeasurementTargetBar.resizeEvent)
    assert "_pin_row_when_alone" in resize
    assert "_apply_location_text" in resize
    show = inspect.getsource(MeasurementTargetBar.showEvent)
    assert "ensurePolished" in show and show.count("_fit_widths") == 2
