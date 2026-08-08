"""Where does every Tool put the files it saves — and does it ask the run type?

Knut, 2026-08-08: *"any and all tools that save files need to be updated and
checked if the files saved are placed in the correct place or folder depending
on the profile run and run type selection."*

The hard part is not checking a tool. It is **knowing the list is complete**, so
this never works from a hand-written list of tools:

1. The tool keys are parsed out of ``open_tool_dialog``'s own branches
   (``ui/dialogs/tools_dialogs.py``) — the registry the app actually dispatches
   on. A tool that exists is in that function by construction.
2. Every key is cross-checked against the Tools popup (``ui/tools_popup.py``),
   in both directions: a popup entry with no branch is a button that does
   nothing, and a branch no popup offers is a tool nobody can reach.
3. Each key is mapped to the **class** it constructs, and the write sites are
   found by walking that class's own AST — not by grepping the file, because
   ``tools_dialogs.py`` alone hosts seven different tools and a grep credits
   every one of them with every other one's writes.
4. Anything the classifier cannot place goes to **UNCLASSIFIED** and is never
   counted as passing. A tool counted as fine because nobody looked at it is
   the failure this script exists to prevent (``drive_demo_package.py`` once
   reported 66/66 when 33 steps were never driven).

What it cannot do is say whether a destination is *right* — only whether it is
**derived from the folder model** (``Project`` / ``Run`` / ``Calibration``,
which is where run-type awareness lives) or hand-built. CLAUDE.md's rule is
"all path construction goes through Project / Run / Calibration", so a writer
that never mentions them cannot be run-type aware, and is the shortlist worth
driving on screen.

    python scripts/audit_tool_file_placement.py          # the report
    python scripts/audit_tool_file_placement.py --json   # machine-readable
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "ui" / "dialogs" / "tools_dialogs.py"
POPUP = ROOT / "ui" / "tools_popup.py"

#: Keys handled by MainWindow._launch_tool itself rather than open_tool_dialog.
SPECIAL_KEYS = {"patch_cube"}

#: Calls that put bytes on disk. ``painter.save()`` / ``painter.restore()`` are
#: QPainter state, not files — excluded by the receiver check below.
WRITE_ATTRS = {
    "write_text", "write_bytes", "writelines", "savefig",
    "copy", "copy2", "copyfile", "copytree", "move",
}
WRITE_FUNCS = {"open", "write_json_atomically"}
#: Saving through a dialog: the file lands where the user says, but the
#: directory ChromIQ *offers* is still a placement decision.
DIALOG_FUNCS = {"getSaveFileName", "getExistingDirectory"}
#: Receivers whose .save() is a picture/profile, not QPainter state.
IMAGE_SAVERS = {"img", "image", "pix", "pixmap", "qimg", "shot", "fig"}

#: Names that mean "this path came from the folder model".
MODEL_HINTS = re.compile(
    r"\b(project|current_run|run_for|Run\.for_dir|calibration|verification|"
    r"file_mgr|_fm|run_dir|exports_dir|reports_dir|cache_dir|"
    r"verifications_dir|_run\b|_project\b)", re.I)

#: A dialog can put a file on disk WITHOUT any write call of its own: it hands
#: a destination to a runner, or it takes one from a destination widget. The
#: first version of this audit missed exactly that and filed `average` and
#: `merge` — which plainly write a .ti3 — under "writes nothing". A bucket that
#: quietly absolves a tool is the failure this script exists to prevent, so
#: these are detected explicitly and counted as writers.
DELEGATED = re.compile(r"_OutputRow\(|\boutput\s*=|\bout_path\b|\bout\s*=\s*"
                       r"[\w.]*\s*/|_initial_dir\(")


def tool_keys_and_classes() -> "dict[str, tuple[str, str]]":
    """{key: (class, module)} straight out of ``open_tool_dialog``."""
    src = REGISTRY.read_text()
    pat = re.compile(
        r'key == "([a-z0-9_]+)":\s*\n((?:\s*(?:from|import)[^\n]*\n)*)\s*dlg = (\w+)\(')
    out = {}
    for m in pat.finditer(src):
        key, imports, cls = m.group(1), m.group(2), m.group(3)
        im = re.search(r"from ([\w.]+) import", imports)
        out[key] = (cls, im.group(1) if im else "ui.dialogs.tools_dialogs")
    if not out:
        raise SystemExit(
            "parsed no tools out of open_tool_dialog — the dispatch shape "
            "changed, and this audit must be repaired rather than trusted")
    return out


def popup_keys() -> "set[str]":
    return set(re.findall(r'ToolEntry\("([a-z0-9_]+)"', POPUP.read_text()))


def _module_path(dotted: str) -> Path:
    return ROOT / (dotted.replace(".", "/") + ".py")


def _class_node(path: Path, cls: str):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            return node
    return None


def _is_write(node: ast.Call) -> "str | None":
    """The kind of write this call is, or None."""
    f = node.func
    if isinstance(f, ast.Attribute):
        if f.attr in DIALOG_FUNCS:
            return "dialog"
        if f.attr == "save":
            recv = f.value.id if isinstance(f.value, ast.Name) else ""
            base = recv.lstrip("_").lower()
            return "write" if base in IMAGE_SAVERS else None
        if f.attr in WRITE_ATTRS:
            return "write"
    if isinstance(f, ast.Name):
        if f.id in DIALOG_FUNCS:
            return "dialog"
        if f.id in WRITE_FUNCS:
            if f.id == "open":
                for a in node.args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                            and ("w" in a.value or "a" in a.value):
                        return "write"
                return None
            return "write"
    return None


def audit_class(path: Path, cls: str) -> dict:
    node = _class_node(path, cls)
    if node is None:
        return {"error": f"class {cls} not found in {path.name}"}
    writes, dialogs = [], []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        kind = _is_write(sub)
        if kind is None:
            continue
        seg = ast.get_source_segment(path.read_text(), sub) or ""
        entry = {"line": sub.lineno, "src": " ".join(seg.split())[:110]}
        (dialogs if kind == "dialog" else writes).append(entry)
    body = ast.get_source_segment(path.read_text(), node) or ""
    delegated = sorted({m.group(0).strip() for m in DELEGATED.finditer(body)})
    return {
        "writes": writes,
        "dialogs": dialogs,
        "delegated": delegated,
        "model_aware": bool(MODEL_HINTS.search(body)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    reg = tool_keys_and_classes()
    pop = popup_keys()

    unreachable = sorted(set(reg) - pop)
    dead = sorted(pop - set(reg) - SPECIAL_KEYS)

    report, unclassified = {}, []
    for key, (cls, mod) in sorted(reg.items()):
        path = _module_path(mod)
        if not path.is_file():
            unclassified.append(f"{key}: module {mod} not on disk")
            continue
        res = audit_class(path, cls)
        if "error" in res:
            unclassified.append(f"{key}: {res['error']}")
            continue
        res.update(key=key, cls=cls, module=mod)
        report[key] = res

    if args.json:
        print(json.dumps({"tools": report, "unclassified": unclassified,
                          "unreachable": unreachable, "dead": dead}, indent=1))
        return 1 if unclassified or dead else 0

    print(f"Tools in the registry: {len(reg)}   in the popup: {len(pop)}")
    if dead:
        print(f"\n!! popup entries with no branch (a button that does nothing): {dead}")
    if unreachable:
        print(f"\n!! registry tools no popup offers: {unreachable}")

    writers = {k: v for k, v in report.items()
               if v["writes"] or v["dialogs"] or v["delegated"]}
    silent = sorted(set(report) - set(writers))

    print(f"\n=== {len(writers)} tools put files somewhere; {len(silent)} write "
          f"nothing ===")
    print(f"    write nothing: {', '.join(silent) or '—'}\n")

    risky = []
    for key, v in sorted(writers.items()):
        flag = "model" if v["model_aware"] else "NO MODEL"
        print(f"--- {key}  ({v['cls']})   [{flag}]")
        print(f"      direct writes: {len(v['writes'])}   "
              f"save dialogs: {len(v['dialogs'])}   "
              f"delegated: {len(v['delegated'])}")
        if v["delegated"]:
            print(f"        via {', '.join(v['delegated'][:4])}")
        for e in v["writes"][:4]:
            print(f"        w {e['line']:5d}  {e['src']}")
        for e in v["dialogs"][:3]:
            print(f"        d {e['line']:5d}  {e['src']}")
        if not v["model_aware"]:
            risky.append(key)

    print("\n=== SHORTLIST — writers that never mention the folder model ===")
    print("These cannot be run-type aware, because run-type awareness lives in")
    print("Project / Run / Calibration. Drive these on screen first.")
    for k in risky:
        print(f"    {k}")

    if unclassified:
        print("\n=== UNCLASSIFIED — never counted as passing ===")
        for u in unclassified:
            print(f"    {u}")

    print(f"\n{len(report)} tools examined, {len(risky)} on the shortlist, "
          f"{len(unclassified)} unclassified")
    return 1 if unclassified or dead else 0


if __name__ == "__main__":
    raise SystemExit(main())
