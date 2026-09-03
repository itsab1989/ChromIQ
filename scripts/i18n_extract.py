#!/usr/bin/env python3
"""Extract tr() source strings and check catalog completeness.

Usage:
    python scripts/i18n_extract.py              # list all keys to stdout
    python scripts/i18n_extract.py --missing de # keys absent from de.json
    python scripts/i18n_extract.py --stale de   # de.json keys no longer in code
    python scripts/i18n_extract.py --stats de   # one-line coverage summary
    python scripts/i18n_extract.py --unwrapped  # literals that never reach tr()

The catalog key is the exact English source string passed to tr().
Both literal arguments (incl. implicitly concatenated) and module-level
string constants are resolved:  tr(_TT_TITLE_PRINT) contributes the
constant's value as a key.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("ui", "workflow", "core", "main.py")


def _python_files() -> "list[Path]":
    """Every source file both halves of this tool look at — one list, so the
    sweep for unwrapped literals can never cover less ground than the sweep for
    keys."""
    files: list[Path] = []
    for entry in SCAN_DIRS:
        p = ROOT / entry
        if p.is_file():
            files.append(p)
        else:
            files.extend(sorted(p.rglob("*.py")))
    return [f for f in files if "__pycache__" not in f.parts]


def extract_keys() -> set[str]:
    keys: set[str] = set()
    for f in _python_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        # module-level NAME = "literal" assignments, for tr(NAME) resolution
        consts: dict[str, str] = {}
        for stmt in tree.body:
            if (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)):
                consts[stmt.targets[0].id] = stmt.value.value
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "tr"
                    and node.args):
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keys.add(arg.value)
            elif isinstance(arg, ast.Name) and arg.id in consts:
                keys.add(consts[arg.id])
    keys |= _message_catalogue_keys()
    return keys


# ---------------------------------------------------------------------------
# The blind spot: a literal that never reaches tr() at all
# ---------------------------------------------------------------------------
#
# `extract_keys` collects `tr(...)` calls, so "0 missing" only ever meant
# "everything already wrapped has a translation". It said exactly that while
# `ui/scan_grid_marquee.py` painted "Load a scan of the printed chart" as a
# bare literal, in English, in all thirteen languages — found by a person
# looking at a German window on Windows, not by this tool (2026-09-03).
#
# So the tool now also looks for the other shape: a string LITERAL handed
# straight to a call that puts text on screen. That is a different question
# from "is this key translated", it needs its own answer, and it cannot be
# perfect — which is why the allow-list below is explicit rather than clever.

#: Text sinks and WHICH argument of each is the text the user reads. A sink
#: not listed here is not swept; a wrong index is worse than a missing one,
#: because it makes the sweep quietly report on the wrong string.
_TEXT_SINKS = {
    "setText": (0,), "setWindowTitle": (0,), "setTitle": (0,),
    "setPlaceholderText": (0,), "setToolTip": (0,), "setStatusTip": (0,),
    "setWhatsThis": (0,), "setLabelText": (0,), "setInformativeText": (0,),
    "setDetailedText": (0,), "setSuffix": (0,), "setPrefix": (0,),
    "setHtml": (0,), "setPlainText": (0,), "setMarkdown": (0,),
    "setAccessibleName": (0,), "setAccessibleDescription": (0,),
    "addItem": (0,), "addTab": (1,), "addAction": (0,),
    "insertItem": (1,), "insertTab": (2,),
    "setItemText": (1,), "setTabText": (1,), "setTabToolTip": (1,),
    # ChromIQ's OWN text sinks. Qt's are not the whole surface: eight progress
    # labels ("Build Profile", "Applying calibration…") were painted from bare
    # literals through `SpectrumProgress.set_label`, and no sweep of Qt method
    # names would ever have reached them. Found by grepping ui/ for
    # `def set_…(self, label|text|title|…)`; a new one of those belongs here.
    "set_label": (0, 1), "set_content": (0, 1), "set_caption": (0,),
    "set_notice": (0,), "set_banner": (0,), "set_tooltip": (0, 1),
    "set_chart_notice": (0,), "set_primary_label": (0,),
    "set_display_text": (0, 1, 2), "set_status": (0,),
}
#: Widgets whose first constructor argument is the label the user reads.
_TEXT_CTORS = {
    "QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox",
    "QAction", "QToolButton", "QCommandLinkButton", "QRadioButton",
}
#: `QMessageBox.warning(parent, title, text)` and friends. Keyed by the
#: RECEIVER as well as the method, because `log.warning("…%s")` is the same
#: method name on a logger and is not user-facing at all — sweeping it caught
#: 380 logging calls and buried the eight real hits.
_DIALOG_CALLS = {
    ("QMessageBox", "warning"): (1, 2),
    ("QMessageBox", "information"): (1, 2),
    ("QMessageBox", "critical"): (1, 2),
    ("QMessageBox", "question"): (1, 2),
    ("QMessageBox", "about"): (1, 2),
    ("QInputDialog", "getText"): (1, 2),
    ("QInputDialog", "getItem"): (1, 2),
    ("QFileDialog", "getOpenFileName"): (1,),
    ("QFileDialog", "getSaveFileName"): (1,),
    ("QFileDialog", "getExistingDirectory"): (1,),
}
#: `painter.drawText(rect, flags, text)` — the shape the missed string used.
#: Swept by method name alone: no logger has a `drawText`.
_DRAW_TEXT = "drawText"

#: An identifier, a key, a file extension, a stylesheet — not a sentence.
_NOT_TEXT = re.compile(r"""
      ^[a-z0-9_.-]+$           # snake_case key, extension, css class
    | %[sdrf]                  # a logging/printf format
    | ^\s*<                    # markup
    | ://                      # a URL
""", re.X)

#: Strings that ARE handed to a text sink and are deliberately not translated.
#: Every entry needs the reason, because an allow-list with no reasons becomes
#: the place unwrapped strings go to hide.
UNTRANSLATED_ON_PURPOSE = {
    # A unit symbol. "dpi" and "patches" are the same word in every catalogue
    # ChromIQ ships, and a suffix is appended to a number by the spin box.
    " dpi",
    " patches",
    # The name of a file format, as its own vendor spells it.
    "Excel (XLSX)",
    # A tool's own command line, echoed so the user can copy it.
    "colprof …",
    # The product word-mark, drawn as artwork in the masthead and the splash.
    # `ChromIQ` is not translated anywhere, and these two are set in the logo's
    # own letterforms; a longer word in another language does not fit the mark.
    "PRINTER PROFILING",
    "Printer profiling with ArgyllCMS",
    "Chrom",
    "IQ",
    # A GLYPH, not a word: the dictionary icon on the Welcome card draws a big
    # "Aa" over an accent underline. It is the shape of two letters, and it is
    # "Aa" in every language ChromIQ ships.
    "Aa",
    # UNIT SYMBOLS, appended to a number by a spin box. Millimetres, points and
    # CIE ΔE are written the same way in all thirteen catalogues, and a spin
    # box's suffix is not a sentence — translating it would only give somebody
    # the chance to get a unit wrong.
    " mm",
    " pt",
    " ΔE",
    # The name of a file format, as its own spec spells it. `Excel (XLSX)`
    # above is the same case.
    "CSV",
}


def _sink_positions(node):
    """Which of *node*'s arguments hold text a user reads, or ()."""
    func = node.func
    if isinstance(func, ast.Name):
        return (0,) if func.id in _TEXT_CTORS else ()
    if not isinstance(func, ast.Attribute):
        return ()
    recv = func.value
    recv_name = (recv.id if isinstance(recv, ast.Name)
                 else recv.attr if isinstance(recv, ast.Attribute) else "")
    hit = _DIALOG_CALLS.get((recv_name, func.attr))
    if hit is not None:
        return hit
    if func.attr == _DRAW_TEXT:
        # The text is the LAST argument in every overload Qt offers.
        return (len(node.args) - 1,) if node.args else ()
    return _TEXT_SINKS.get(func.attr, ())


def is_user_facing_text(s: str) -> bool:
    """Whether *s* is a sentence a person reads, rather than a token."""
    if len(s) < 2:
        return False
    if not any(c.isalpha() for c in s):
        return False
    if _NOT_TEXT.search(s):
        return False
    return True


def unwrapped_literals():
    """Every string literal handed straight to a text sink, never through tr().

    Returns ``[(relative path, line, sink, argument index, text), …]``, sorted.
    """
    out = []
    for f in _python_files():
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:                    # pragma: no cover — defensive
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for i in _sink_positions(node):
                if not 0 <= i < len(node.args):
                    continue
                a = node.args[i]
                if not (isinstance(a, ast.Constant)
                        and isinstance(a.value, str)):
                    continue                   # tr(…), a variable, an f-string
                if a.value in UNTRANSLATED_ON_PURPOSE:
                    continue
                if not is_user_facing_text(a.value):
                    continue
                name = (node.func.id if isinstance(node.func, ast.Name)
                        else node.func.attr)
                out.append((f.relative_to(ROOT).as_posix(), a.lineno,
                            name, i, a.value))
    return sorted(out)


def _message_catalogue_keys() -> set[str]:
    """Every text in ``workflow/measurement_messages.py``.

    That module holds the reviewed §M catalogue and hands its strings to
    ``tr()`` as ``tr(self.body)`` — an attribute, not a literal, so the walk
    above cannot see any of them. Without this the whole catalogue silently
    dropped out of the translations: 4009 keys became 3966, and every window in
    the Measurement Management model would have shown English in every
    language. Read the values from the module itself rather than trying to
    pattern-match the source, so a new message cannot be missed.
    """
    sys.path.insert(0, str(ROOT))
    try:
        from workflow import measurement_messages as mm
    except Exception as exc:      # noqa: BLE001 — never break the extractor
        print(f"# WARNING: message catalogue not readable: {exc}",
              file=sys.stderr)
        return set()

    out: set[str] = set()
    for msg in mm.CATALOGUE.values():
        out.add(msg.title)
        out.add(msg.body)
        if msg.body_one:
            out.add(msg.body_one)
    out |= set(mm.FRAGMENTS.values())
    # EVERY STRING CONSTANT IN THE MODULE, not a hand-kept list of names.
    #
    # The list this replaces named ten of them, and the module now holds
    # twenty-eight. Three were missing when it was swept programmatically on
    # 2026-09-02: `M_CHART_CORRUPT_WITH_PROFILE`, which is handed to `tr()` at
    # two call sites in the Create Chart tab and had therefore been showing
    # English in all twelve translated languages since it was written, and the
    # two `{runs_line}` sentences of M-CAL-REPLACE-MEASURED, added that day.
    #
    # This is the blind spot the module's own comments already warn about:
    # `tr(NAME)` passes an attribute, not a literal, so the AST walk cannot see
    # it and the only protection was somebody remembering to edit this file.
    # Nobody did, twice. A sweep cannot forget.
    #
    # Fragments are message text by construction here: this module holds
    # nothing else. Anything added to it that is NOT for the screen would need
    # a leading double underscore, which is excluded below.
    out |= {v for k, v in vars(mm).items()
            if isinstance(v, str) and not k.startswith("__")
            and (k.startswith("M_") or k.startswith("_"))}
    return out


def load_catalog(code: str) -> dict[str, str]:
    path = ROOT / "data" / "i18n" / f"{code}.json"
    with open(path, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("@")}


def main() -> int:
    args = sys.argv[1:]
    keys = extract_keys()
    if not args:
        for k in sorted(keys):
            print(json.dumps(k, ensure_ascii=False))
        print(f"# {len(keys)} keys", file=sys.stderr)
        return 0
    if args[0] == "--unwrapped":
        hits = unwrapped_literals()
        for path, line, sink, arg, text in hits:
            print(f"{path}:{line}: {sink}(arg{arg}) "
                  f"{json.dumps(text, ensure_ascii=False)}")
        print(f"# {len(hits)} user-facing literals never reach tr()",
              file=sys.stderr)
        return 1 if hits else 0
    mode, code = args[0], args[1]
    catalog = load_catalog(code)
    if mode == "--missing":
        missing = sorted(keys - set(catalog))
        for k in missing:
            print(json.dumps(k, ensure_ascii=False))
        print(f"# {len(missing)} missing of {len(keys)}", file=sys.stderr)
        return 1 if missing else 0
    if mode == "--stale":
        stale = sorted(set(catalog) - keys)
        for k in stale:
            print(json.dumps(k, ensure_ascii=False))
        print(f"# {len(stale)} stale", file=sys.stderr)
        return 0
    if mode == "--stats":
        done = len(keys & set(catalog))
        print(f"{code}: {done}/{len(keys)} translated "
              f"({100 * done / max(1, len(keys)):.1f}%), "
              f"{len(set(catalog) - keys)} stale")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
