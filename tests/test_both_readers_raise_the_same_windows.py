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
HELPER_LINES = {
    "capability":  ("Need reflection spot, strip, xy or chart reading capability,",
                    "Need reflection spot, strip, xy or chart reading capability", 1004),
    "ccmx_set":    ("Setting Colorimeter Correction Matrix failed with error :'x' (0x1)",
                    "Setting Colorimeter Correction Matrix failed with error", 1063),
    "ccmx_read":   ("Reading CCMX/CCSS File 'x.ccmx' failed with error 2:'nope'",
                    "Reading CCMX/CCSS File", 1085),
    "mode_set":    ("Setting instrument mode failed with error :'unsupported' (0x2)",
                    "Setting instrument mode failed with error", 1409),
    "init_fail":   ("Initialising instrument failed with message 'Communications failure'",
                    None, None),
    "coms_fail":   ("Establishing communications with instrument failed with message 'timeout'",
                    None, None),
}

WATCHED = ("ccmx_load_failed", "instrument_wrong_type", "mode_set_failed",
           "inst_init_failed", "coms_init_failed", "abort_confirm")


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
