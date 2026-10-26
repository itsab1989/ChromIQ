"""Every file dialog's title and file-type filter speaks the user's language.

About thirty "Open" and "Save" dialogs showed an English title and an English
filter ("Select calibration file", "CAL files (*.cal)") in an otherwise German
window (4.3.16). They all go through ``ui.widgets``' helpers
(``open_file_dialog``, ``open_files_dialog``, ``save_file_dialog``,
``open_dir_dialog``), and ``scripts/i18n_extract.py --unwrapped`` looks at
``QFileDialog``'s own static calls only, so nothing noticed. The patch set
editor was fixed first and pinned by its own test; this one covers the app.

What it reads, for every call that opens a file dialog in ``SCAN_DIRS``:

* the title and the filter must reach the helper through ``tr()``, or be
  empty;
* a module constant must be handed over as ``tr(_NAME)`` (the extractor
  resolves that into a catalogue key);
* a local variable is followed to everything assigned to it;
* an attribute (``src.file_filter``) is followed to every ``file_filter=``
  keyword in the same module;
* a function that passes its own parameter on as the title or the filter is
  a helper itself, and ITS callers are read the same way (``_browse_file``,
  ``_pick_input_file``), to any depth.

A literal glued onto ``tr()`` is allowed only when it is nothing but a file
pattern, like ``tr("ChromIQ profile (project.json)") + " (project.json)"``.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from i18n_extract import _python_files  # noqa: E402

#: The calls that open a file dialog, and the positional index of each
#: argument the user reads (``self`` not counted for a bound call).
BASE_SINKS: "dict[str, dict[str, int]]" = {
    "open_file_dialog": {"title": 1, "name_filter": 2},
    "open_files_dialog": {"title": 1, "name_filter": 2},
    "save_file_dialog": {"title": 1, "name_filter": 2},
    "open_dir_dialog": {"title": 1},
    "getOpenFileName": {"caption": 1, "filter": 3},
    "getOpenFileNames": {"caption": 1, "filter": 3},
    "getSaveFileName": {"caption": 1, "filter": 3},
    "getExistingDirectory": {"caption": 1},
    "QFileDialog": {"caption": 1, "filter": 3},
    "setNameFilter": {"filter": 0},
    "setNameFilters": {"filters": 0},
}

#: A literal that is only a file pattern, such as " (project.json)".
_PATTERN_ONLY = re.compile(r"^[\s();*.,\w-]*$")


def _is_pattern_only(s: str) -> bool:
    inner = re.sub(r"\([^)]*\)", "", s)
    return bool(_PATTERN_ONLY.match(s)) and not any(c.isalpha() for c in inner)


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _is_tr(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "tr")


class _Module:
    def __init__(self, path: Path, source: str):
        self.path = path
        self.tree = ast.parse(source)
        self.consts = set()
        for stmt in self.tree.body:
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        self.consts.add(t.id)
        self.parent: "dict[ast.AST, ast.AST]" = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node

    def enclosing_function(self, node):
        while node in self.parent:
            node = self.parent[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node
        return None


def _params(fn) -> "list[str]":
    names = [a.arg for a in fn.args.posonlyargs + fn.args.args]
    if names and names[0] in ("self", "cls"):
        names = names[1:]
    return names


def _given(call: ast.Call, positions: "dict[str, int]"):
    """``{param name: argument node}`` for the text arguments of *call*."""
    out = {}
    for name, i in positions.items():
        if i < len(call.args):
            out[name] = call.args[i]
    for kw in call.keywords:
        if kw.arg in positions:
            out[kw.arg] = kw.value
    return out


def _local_values(fn, name: str):
    """Everything assigned to *name* inside *fn*, tuple unpacking included."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    yield node.value
                elif (isinstance(t, ast.Tuple)
                      and isinstance(node.value, ast.Tuple)):
                    for el, val in zip(t.elts, node.value.elts):
                        if isinstance(el, ast.Name) and el.id == name:
                            yield val
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name) and node.target.id == name:
                yield node.value


def _problems(mod: _Module, value, fn, seen=()) -> "list[str]":
    """Why *value* can reach a file dialog untranslated, or []."""
    if isinstance(value, ast.Constant):
        if value.value in ("", None):
            return []
        return [f"the literal {value.value!r}"]
    if _is_tr(value):
        return []
    if isinstance(value, ast.IfExp):
        return (_problems(mod, value.body, fn, seen)
                + _problems(mod, value.orelse, fn, seen))
    if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
        out = []
        for part in (value.left, value.right):
            if (isinstance(part, ast.Constant) and isinstance(part.value, str)
                    and _is_pattern_only(part.value)):
                continue
            out += _problems(mod, part, fn, seen)
        return out
    if isinstance(value, ast.Name):
        if fn is not None and value.id in _params(fn):
            return []        # a pass-through: its callers are read instead
        if fn is not None and value.id not in seen:
            vals = list(_local_values(fn, value.id))
            if vals:
                out = []
                for v in vals:
                    out += _problems(mod, v, fn, seen + (value.id,))
                return out
        if value.id in mod.consts:
            return [f"the module constant {value.id} without tr()"]
        return [f"{value.id}, which this guard cannot follow"]
    if isinstance(value, ast.Attribute):
        attr = value.attr
        vals = [kw.value for node in ast.walk(mod.tree)
                if isinstance(node, ast.Call)
                for kw in node.keywords if kw.arg == attr]
        if not vals:
            return [f".{attr}, which this guard cannot follow"]
        out = []
        for v in vals:
            out += _problems(mod, v, None, seen)
        return out
    return [f"{ast.unparse(value)[:60]}, which this guard cannot follow"]


def _modules():
    return [_Module(f, f.read_text(encoding="utf-8")) for f in _python_files()]


def _sinks_for(modules):
    """The base sinks, plus every function that passes its own parameter on
    as a title or a filter. A private name (``_browse_file``) is a sink in its
    own module only; a public one everywhere."""
    public = {k: dict(v) for k, v in BASE_SINKS.items()}
    private: "dict[Path, dict[str, dict[str, int]]]" = {m.path: {} for m in modules}
    changed = True
    while changed:
        changed = False
        for mod in modules:
            table = {**public, **private[mod.path]}
            for call in ast.walk(mod.tree):
                if not isinstance(call, ast.Call):
                    continue
                positions = table.get(_call_name(call))
                if not positions:
                    continue
                fn = mod.enclosing_function(call)
                if fn is None:
                    continue
                params = _params(fn)
                for value in _given(call, positions).values():
                    if isinstance(value, ast.Name) and value.id in params:
                        target = (private[mod.path] if fn.name.startswith("_")
                                  else public)
                        entry = target.setdefault(fn.name, {})
                        if value.id not in entry:
                            entry[value.id] = params.index(value.id)
                            changed = True
    return public, private


def file_dialog_problems(modules=None):
    modules = _modules() if modules is None else modules
    public, private = _sinks_for(modules)
    calls, bad = 0, []
    for mod in modules:
        table = {**public, **private[mod.path]}
        for call in ast.walk(mod.tree):
            if not isinstance(call, ast.Call):
                continue
            positions = table.get(_call_name(call))
            if not positions:
                continue
            calls += 1
            fn = mod.enclosing_function(call)
            for name, value in _given(call, positions).items():
                for why in _problems(mod, value, fn):
                    rel = mod.path.relative_to(ROOT).as_posix() \
                        if mod.path.is_relative_to(ROOT) else str(mod.path)
                    bad.append(f"{rel}:{call.lineno} {_call_name(call)} "
                               f"{name}: {why}")
    return calls, sorted(bad)


def test_the_guard_reads_the_app_s_file_dialogs():
    calls, _ = file_dialog_problems()
    # 80 helper calls in the tree on 2026-10-26, plus the wrappers' callers.
    assert calls >= 80, calls


def test_every_file_dialog_title_and_filter_goes_through_tr():
    _, bad = file_dialog_problems()
    assert not bad, (
        "file dialog text that would show in English in every language; "
        "wrap it in tr() and translate it in all thirteen catalogues:\n  "
        + "\n  ".join(bad))


def _check(src: str, tmp_path: Path):
    p = tmp_path / "planted.py"
    p.write_text(src, encoding="utf-8")
    return file_dialog_problems([_Module(p, src)])[1]


def test_the_guard_catches_what_it_is_for(tmp_path):
    """Planted faults, one per shape the app used before 4.3.16."""
    bad = _check(
        '_F = "CAL files (*.cal)"\n'
        "class W:\n"
        "    def _browse(self, caption, name_filter):\n"
        "        return open_file_dialog(self, caption, name_filter)\n"
        "    def a(self):\n"
        '        open_file_dialog(self, "Select file", tr("X (*.x)"))\n'
        "    def b(self):\n"
        '        save_file_dialog(self, tr("T"), _F)\n'
        "    def c(self):\n"
        '        self._browse(tr("T"), "Images (*.tif)")\n'
        "    def d(self):\n"
        '        title, flt = tr("T"), "Scans (*.tif)"\n'
        "        open_file_dialog(self, title, flt)\n"
        "    def e(self, src):\n"
        "        open_file_dialog(self, tr(\"T\"), src.file_filter)\n"
        "    def f(self):\n"
        '        make(file_filter="Reference data (*.txt)")\n'
        "    def g(self):\n"
        '        open_dir_dialog(self, "Choose a folder")\n',
        tmp_path)
    text = "\n".join(bad)
    assert "'Select file'" in text
    assert "_F without tr()" in text
    assert "'Images (*.tif)'" in text
    assert "'Scans (*.tif)'" in text
    assert "'Reference data (*.txt)'" in text
    assert "'Choose a folder'" in text


def test_the_guard_lets_translated_text_through(tmp_path):
    assert _check(
        '_F = "CAL files (*.cal)"\n'
        "class W:\n"
        "    def a(self, is_x):\n"
        '        open_file_dialog(self, tr("T"), tr(_F))\n'
        '        open_file_dialog(self, tr("T"), tr("A") if is_x else "")\n'
        '        open_file_dialog(self, tr("T"),\n'
        '                         tr("ChromIQ profile") + " (project.json)")\n'
        '        open_dir_dialog(self, tr("Choose a folder"))\n',
        tmp_path) == []
