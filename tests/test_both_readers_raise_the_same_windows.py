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
#: regression. #159 shifted all four by +21, the button shortcuts (4.3.14) by +65 and their exit guard by +27, the i1Pro 3 lights choices (2026-11-14) by +36, the ruler check (2026-11-14) by +145, the 4.3.36 USB-step detail and i1Pro 2 pause by +51, the 4.3.37 lights hold event and ruler reason by +15, and the failures were reported as
#: "pre-existing" for a while, which is precisely how a real regression would
#: hide. If these fail, FIRST check whether the literal simply moved:
#:
#:     grep -n "Setting instrument mode failed with error" \
#:         native/chartread_helper/chromiq_chartread.c
#:
#: and prove it is a move by running the same test on master in a separate
#: worktree before touching anything else.
# +54 on 2026-11-19 (4.3.49): cq_dd_held_command and its prototype inserted
# above these lines in chromiq_chartread.c (a move, nothing else changed)
# +139 on 2026-11-19 (4.3.49, helper 19d): the kept conditions record (cq_cond_keep, the
# partial files, cq_cond_resume) inserted above these lines (a move, nothing else changed)
# +54 on 2026-11-20 (4.3.52, helper 20a): the lights' quiet-time flag and the dual scan's blue
# (cq_lights_second_pass_*) inserted above these lines (a move, nothing else changed)
# +11 on 2026-11-20 (4.3.52 fix round, helper 20b): the hold after the blue and the session
# line's blue_quiet_ms (cq_lights_held2, cq_lights_for_session) above these lines (a move)
# +39 on 2026-11-20 (4.3.53, helper 20d): the waits as values (cq_wait_arg and its statics)
# above these lines (a move, nothing else changed)
# +7 on 2026-11-20 (4.3.53 release, helper 20e): the blue light's side in the lights' log line
# (cq_lights_sent2, cq_lights_name2) above these lines (a move, nothing else changed)
# +9 on 2026-11-21 (4.3.55, helper 21f): +4 for the i1Pro 2's own lamp wait (cq_lamp_off_i1pro2_set_ms
# and its usage lines) above these lines (lines 3560-4100 of v4.3.54 are byte-identical at +4: a
# move), and +5 that had already built up by 4.3.54, when each string sat on its window's last line;
# the pins are now the strings' own lines again
# +8 on 2026-11-23 (4.3.58, helper 23a, item 17): the refused first pass of an i1Pro 2 dual strip
# asks for no second pass, inserted above these lines (a move, nothing else changed)
# +1 on 2026-11-23 (4.3.58, helper 23b, item 40): the #include of chromiq_dualcal.h above these
# lines (a move, nothing else changed)
# +59 on 2026-11-24 (helper 24a, item 43 steps 2-3): the spot session's flag and the test-only
# instrument seam's declaration above these lines, and the patch loop's per-press block moved
# into cq_spot_read_once (a move, nothing else changed)
HELPER_LINES = {
    "capability":  ("Need reflection spot, strip, xy or chart reading capability,",
                    "Need reflection spot, strip, xy or chart reading capability", 3692),
    "ccmx_set":    ("Setting Colorimeter Correction Matrix failed with error :'x' (0x1)",
                    "Setting Colorimeter Correction Matrix failed with error", 3751),
    "ccmx_read":   ("Reading CCMX/CCSS File 'x.ccmx' failed with error 2:'nope'",
                    "Reading CCMX/CCSS File", 3773),
    "mode_set":    ("Setting instrument mode failed with error :'unsupported' (0x2)",
                    "Setting instrument mode failed with error", 4119),
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
    text = HELPER_C.read_text(errors="replace", encoding="utf-8").splitlines()
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
    text = HELPER_C.read_text(errors="replace", encoding="utf-8")
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
