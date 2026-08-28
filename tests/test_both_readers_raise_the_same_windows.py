"""A window must not depend on which reader is running.

Knut's abort-window report (beta.160) turned out to be one instance of a class:
a condition the ChromIQ helper produces, recognised only by the stock-chartread
parser, so the window never appeared on the default reader. Auditing every
signal afterwards found three more — all startup failures the beta.141 fix
walked past when it moved its two neighbours into the shared checker.

Two kinds of test here:

* **Behavioural** — feed each reader the exact line the helper prints and
  require the same signals out of both.
* **Structural** — catch the next one automatically, by refusing to let a
  window-raising signal be emitted from the stock parser alone.
"""
import ast
import inspect
from pathlib import Path

import pytest

from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from workflow.measure_manager import MeasureManager

HELPER_C = (Path(__file__).resolve().parent.parent
            / "native" / "chartread_helper" / "chromiq_chartread.c")

#: label -> (line as the helper prints it at runtime,
#:           literal stem of the printf in the C, source line)
#: The stem is written out rather than derived from the runtime line: the C
#: holds "'%s'" where the runtime line holds a real filename, so deriving it
#: fails for the wrong reason.
#:
#: ⚠ THE SOURCE LINE NUMBERS DRIFT whenever chromiq_chartread.c gains or loses
#: lines above them, and a drift failure looks exactly like a behavioural
#: regression. #159 shifted all four by +21 and the failures were reported as
#: "pre-existing" for a while, which is precisely how a real regression would
#: hide. If these fail, FIRST check whether the literal simply moved:
#:
#:     grep -n "Setting instrument mode failed with error" \
#:         native/chartread_helper/chromiq_chartread.c
#:
#: and prove it is a move by running the same test on master in a separate
#: worktree before touching anything else.
HELPER_LINES = {
    "capability":  ("Need reflection spot, strip, xy or chart reading capability,",
                    "Need reflection spot, strip, xy or chart reading capability", 1043),
    "ccmx_set":    ("Setting Colorimeter Correction Matrix failed with error :'x' (0x1)",
                    "Setting Colorimeter Correction Matrix failed with error", 1102),
    "ccmx_read":   ("Reading CCMX/CCSS File 'x.ccmx' failed with error 2:'nope'",
                    "Reading CCMX/CCSS File", 1124),
    "mode_set":    ("Setting instrument mode failed with error :'unsupported' (0x2)",
                    "Setting instrument mode failed with error", 1448),
    "init_fail":   ("Initialising instrument failed with message 'Communications failure'",
                    None, None),
    "coms_fail":   ("Establishing communications with instrument failed with message 'timeout'",
                    None, None),
}

WATCHED = ("ccmx_load_failed", "instrument_wrong_type", "mode_set_failed",
           "inst_init_failed", "coms_init_failed", "abort_confirm",
           "info_message")

#: The notes chartread prints when the instrument drops a setting the user
#: chose. Not windows, but the same class: on the engine they appeared nowhere,
#: so the user believed a setting was active when the instrument had ignored
#: it — the shape of the `-T` tolerance problem that reached Knut once already.
HELPER_NOTES = {
    "chart_mismatch": "Warning: chart is for i1pro2, using instrument i1pro3",
    "no_spectral":    "Instrument isn't capable of spectral measurement",
    "highres":        "Warning - high resolution ignored",
    "uv":             "UV measurement mode requested, but instrument doesn't support it",
    "scan_tol":       "Modified patch consistency tolerance ignored",
    "patch_missing":  "Patch 'A1' not found",
}


def _signals_for(line: str, *, engine: bool) -> list:
    m = MeasureManager(ArgyllRunner(AppSettings()))
    seen: list = []
    for name in WATCHED:
        getattr(m, name).connect(lambda *a, s=name: seen.append(s))
    m._engine_active = engine
    handler = m._handle_engine_line if engine else m._handle_line
    handler(line, lambda _l: None)
    return seen


@pytest.mark.parametrize("label", sorted(HELPER_LINES))
def test_both_readers_raise_the_same_window(label, qapp):
    line = HELPER_LINES[label][0]
    stock = _signals_for(line, engine=False)
    engine = _signals_for(line, engine=True)
    assert stock == engine, (
        f"{label}: stock raises {stock or 'nothing'} but the engine raises "
        f"{engine or 'nothing'} — the window depends on the reader"
    )
    assert stock, f"{label}: neither reader raises anything for a line the helper prints"


@pytest.mark.parametrize("label", sorted(HELPER_LINES))
def test_each_window_is_raised_exactly_once(label, qapp):
    """The shared checker is called from both parsers.

    Leaving a copy behind in the stock parser as well would raise the window
    twice — two identical dialogs stacked on each other.
    """
    line = HELPER_LINES[label][0]
    for engine in (False, True):
        got = _signals_for(line, engine=engine)
        assert len(got) == len(set(got)), (
            f"{label} on {'engine' if engine else 'stock'}: {got} — raised twice"
        )


@pytest.mark.parametrize("label", sorted(HELPER_LINES))
def test_the_helper_really_prints_that_line(label, qapp):
    """Guard the contract at its source, not just our side of it."""
    _line, stem, src_line = HELPER_LINES[label]
    if src_line is None or not HELPER_C.is_file():
        pytest.skip("no pinned helper source line for this one")
    text = HELPER_C.read_text(errors="replace").splitlines()
    # Matched in a window around the pinned line, so a reflow of the C does not
    # fail the test for the wrong reason.
    window = "\n".join(text[max(0, src_line - 6):src_line + 5])
    assert stem in window, (
        f"{label}: the helper no longer prints {stem!r} near line {src_line} — "
        f"either it moved or the window is unreachable again"
    )


def test_no_failure_window_is_left_in_the_stock_parser_alone():
    """The structural guard — this is what catches the next one.

    Every one of these signals opens a window explaining a failure. If it is
    emitted from `_handle_line` (stock only) and not from the shared
    `_check_startup_failures`, the engine cannot raise it.
    """
    import workflow.measure_manager as mm

    tree = ast.parse(inspect.getsource(mm.MeasureManager))

    def emitted_in(fn_name: str) -> set:
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
        assert fn is not None, f"{fn_name} has been renamed"
        return {n.func.value.attr for n in ast.walk(fn)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "emit"
                and isinstance(n.func.value, ast.Attribute)}

    stock_only = emitted_in("_handle_line") - emitted_in("_check_startup_failures")
    offenders = sorted(stock_only & {
        "ccmx_load_failed", "instrument_wrong_type", "mode_set_failed",
        "inst_init_failed", "coms_init_failed",
    })
    assert not offenders, (
        f"{offenders} are emitted from the stock parser only. Move them into "
        f"_check_startup_failures, which both readers call, or the engine "
        f"stays silent on them."
    )


@pytest.mark.parametrize("label", sorted(HELPER_NOTES))
def test_both_readers_surface_the_same_notes(label, qapp):
    line = HELPER_NOTES[label]
    stock = _signals_for(line, engine=False)
    engine = _signals_for(line, engine=True)
    assert stock == engine, (
        f"{label}: stock says {stock or 'nothing'}, the engine says "
        f"{engine or 'nothing'} — the note depends on the reader"
    )
    assert stock, f"{label}: neither reader surfaces a line the helper prints"


@pytest.mark.parametrize("label", sorted(HELPER_NOTES))
def test_the_helper_prints_each_note(label, qapp):
    """Our half of the contract must not be able to pass alone."""
    if not HELPER_C.is_file():                 # pragma: no cover
        pytest.skip("helper source not in this checkout")
    text = HELPER_C.read_text(errors="replace")
    stems = {
        "chart_mismatch": "chart is for",
        "no_spectral":    "isn't capable of spectral",
        "highres":        "high resolution ignored",
        "uv":             "UV measurement mode requested",
        "scan_tol":       "patch consistency tolerance ignored",
        "patch_missing":  "not found",
    }
    assert stems[label] in text, (
        f"{label}: the helper no longer prints this — the note is unreachable "
        f"again, or it moved and the pattern needs updating"
    )


def test_no_informational_note_is_left_in_the_stock_parser_alone():
    """Structural twin of the failure-window guard, for the notes."""
    import ast
    import inspect

    import workflow.measure_manager as mm

    tree = ast.parse(inspect.getsource(mm.MeasureManager))

    def info_keys(fn_name: str) -> set:
        """The literal first argument of each info_message.emit in a method."""
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
        assert fn is not None, f"{fn_name} has been renamed"
        keys = set()
        for n in ast.walk(fn):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "emit"
                    and isinstance(n.func.value, ast.Attribute)
                    and n.func.value.attr == "info_message"):
                first = n.args[0] if n.args else None
                keys.add(first.value if isinstance(first, ast.Constant) else "?")
        return keys

    #: Stock-only on purpose, with the reason. The engine reports a finished XY
    #: sheet as a typed `xy_sheet_read` event carrying its patches, so the user
    #: is told either way; duplicating the prose note here would report it
    #: twice on the engine.
    ALLOWED_STOCK_ONLY = {"xy_sheet_ok"}

    stray = info_keys("_handle_line") - ALLOWED_STOCK_ONLY
    assert not stray, (
        f"{sorted(stray)} are emitted straight from the stock parser. Put them "
        f"in _check_informational, which both readers call, or the engine "
        f"stays silent on them. If one is genuinely stock-only, add it to "
        f"ALLOWED_STOCK_ONLY here with the reason."
    )
    assert info_keys("_check_informational"), "_check_informational emits nothing"
