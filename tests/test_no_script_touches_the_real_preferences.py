"""No script or test may open or write the user's REAL ChromIQ preferences.

~/Library/Preferences/com.chromiq.ChromIQ.plist (Qt domain
QSettings("ChromIQ", "ChromIQ")) is the preferences store the owner works with
every day. QSettings on that path can write back on sync/destruction, and a
"restore from backup" writes it directly. Drivers seed their sandbox from
`scripts/real_settings_copy.py::copy_of_real_preferences()` (a COPY) instead.
Reading its bytes for a hash comparison stays allowed.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKERS = ("com.chromiq.ChromIQ.plist", "Library/Preferences")
CMD_MARKERS = ("defaults write com.chromiq", "defaults delete com.chromiq",
               "defaults import com.chromiq")
# path -> reason. Empty on purpose: nothing legitimate needs an exception.
ALLOWLIST: dict[str, str] = {}

# `core.settings.QSettings` is REPLACED by a sandboxed ini opener in the suite
# (tests/conftest.py guards each use with `isinstance(_cs.QSettings, type)`),
# so `_cs.QSettings("ChromIQ", "ChromIQ")` never reaches the real store.
_SANDBOXED_MODULES = {"_cs", "CS", "cs"}
_WRITE_METHODS = {"write_text", "write_bytes", "unlink", "rename", "replace", "touch"}
_COPY_FUNCS = {"copy", "copy2", "copyfile", "move", "replace", "rename"}


def _strs(node):
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value


def _has_marker(node) -> bool:
    return any(m in s for s in _strs(node) for m in MARKERS)


def _name_of(n):
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        return n.attr
    return None


def _mentions(node, names) -> bool:
    return any(_name_of(n) in names for n in ast.walk(node)
               if isinstance(n, (ast.Name, ast.Attribute)))


def scan_source(src: str) -> list[tuple[int, str]]:
    tree = ast.parse(src)
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and _has_marker(n.value):
            for t in n.targets:
                if _name_of(t):
                    names.add(_name_of(t))
        elif isinstance(n, ast.AnnAssign) and n.value is not None and _has_marker(n.value):
            if _name_of(n.target):
                names.add(_name_of(n.target))

    def real(node) -> bool:
        return _has_marker(node) or _mentions(node, names)

    out: list[tuple[int, str]] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if any(c in n.value for c in CMD_MARKERS):
                out.append((n.lineno, "defaults command on the real domain"))
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        fname = _name_of(fn)
        args = list(n.args) + [k.value for k in n.keywords]
        if fname == "QSettings":
            lits = [a.value for a in n.args[:2]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            sandboxed = isinstance(fn, ast.Attribute) and _name_of(fn.value) in _SANDBOXED_MODULES
            if sandboxed:
                pass
            elif lits == ["ChromIQ", "ChromIQ"]:
                out.append((n.lineno, 'QSettings("ChromIQ", "ChromIQ")'))
            elif any(real(a) for a in args):
                out.append((n.lineno, "QSettings opened on the real plist"))
        elif fname in _COPY_FUNCS and isinstance(fn, ast.Attribute) \
                and _name_of(fn.value) in ("shutil", "os") and len(n.args) >= 2:
            if real(n.args[1]):
                out.append((n.lineno, f"{fname} writes the real plist"))
        elif isinstance(fn, ast.Attribute) and fname in _WRITE_METHODS \
                and real(fn.value):
            out.append((n.lineno, f".{fname}() on the real plist"))
        elif fname == "remove" and isinstance(fn, ast.Attribute) \
                and _name_of(fn.value) == "os" and n.args and real(n.args[0]):
            out.append((n.lineno, "os.remove of the real plist"))
        elif fname == "open" and n.args and real(n.args[0]):
            mode = n.args[1] if len(n.args) > 1 else next(
                (k.value for k in n.keywords if k.arg == "mode"), None)
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
                    and set(mode.value) & set("wax+"):
                out.append((n.lineno, "open() for writing on the real plist"))
        elif fname == "open" and isinstance(fn, ast.Attribute) and real(fn.value):
            mode = n.args[0] if n.args else None
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
                    and set(mode.value) & set("wax+"):
                out.append((n.lineno, "Path.open() for writing on the real plist"))
    return sorted(set(out))


def test_the_scanner_flags_a_qsettings_open():
    src = ('from pathlib import Path\n'
           'REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"\n'
           'src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)\n')
    assert [l for l, _ in scan_source(src)] == [3]
    assert scan_source('q = QSettings("ChromIQ", "ChromIQ")\n')


def test_the_scanner_flags_a_restore_and_a_defaults_write():
    src = ('REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"\n'
           'shutil.copy2(BACKUP, REAL_PLIST)\n'
           'REAL_PLIST.write_bytes(b"")\n'
           'os.system("defaults write com.chromiq.ChromIQ x 1")\n')
    assert [l for l, _ in scan_source(src)] == [2, 3, 4]


def test_the_scanner_allows_a_read_only_hash():
    src = ('REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"\n'
           'h = hashlib.sha256(REAL_PLIST.read_bytes()).hexdigest()\n'
           'shutil.copy2(REAL_PLIST, BACKUP)\n'
           'ok = REAL_PLIST.exists()\n'
           'q = QSettings(str(copy_of_real_preferences()), QSettings.Format.NativeFormat)\n')
    assert scan_source(src) == []


def test_no_script_or_test_touches_the_real_preferences():
    me = Path(__file__).resolve()
    bad = []
    for base in ("scripts", "tests"):
        for p in sorted((ROOT / base).rglob("*.py")):
            if ".venv" in p.parts or p.resolve() == me:
                continue
            rel = str(p.relative_to(ROOT))
            if rel in ALLOWLIST:
                continue
            try:
                hits = scan_source(p.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            bad += [f"{rel}:{ln}: {why}" for ln, why in hits]
    assert not bad, "the real preferences are touched:\n" + "\n".join(bad)
