"""Every window in the sounds table actually plays its sound.

Knut, #130 (2026-08-06): *"Also make sure all the warning messages implemented
for ChromIQ chartread engine have the correct defined sound before/upon loading
the window. Sounds used for messages are specified in list in help icon in
preferences sounds tab."*

`core.measure_windows.WINDOW_ROWS` is that list. It is what the user is
promised, so it is the specification here and the code is checked against it —
the audit that produced these tests found two windows that opened in silence:
**Instrument in Wrong Position** and **Instrument Error (anything else the
instrument reports)**.

The check is structural because the alternative is a real instrument fault.
`_cue_window` must be called from the TOP of the slot that opens the window: a
modal dialog blocks inside the slot, so a cue placed after `.exec()` is not
heard until the window is dismissed.
"""
import ast
import inspect

import pytest

import core.sound as snd
from core.measure_windows import EVENT_ROWS, WINDOW_ROWS

#: handler → the `core.sound` constant its window must play.
#: Keyed by method name so a rename fails loudly rather than silently skipping.
EXPECTED_CUE = {
    "_on_sensor_wrong_position":              "INSTRUMENT_ERROR",
    "_on_generic_instrument_error":           "INSTRUMENT_ERROR",
    "_on_abort_confirm":                      "INSTRUMENT_ERROR",
    "_on_calibration_prompt":                 "INSTRUMENT_ERROR",
    "_show_no_instrument_window":             "INSTRUMENT_ERROR",
    "_show_instrument_disconnected_window":   "INSTRUMENT_ERROR",
    "_warn_if_instrument_does_not_match_chart": "INSTRUMENT_ERROR",
    "_on_wrong_strip":                        "STRIP_FAIL",
    "_on_strip_interrupted":                  "STRIP_FAIL",
    "_on_strip_misaligned":                   "STRIP_FAIL",
    "_show_average_failed_dialog":            "STRIP_FAIL",
    "_on_unexpected_response":                "PATCH_OUT_OF_TOL",
}


def _class_tree():
    import ui.tabs.tab_measure as tm
    return ast.parse(inspect.getsource(tm.TabMeasure))


def _method(name: str):
    fn = next((n for n in ast.walk(_class_tree())
               if isinstance(n, ast.FunctionDef) and n.name == name), None)
    assert fn is not None, f"{name} has been renamed — update EXPECTED_CUE"
    return fn


def _cues(fn) -> list:
    return [n.args[0].value for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_cue_window" and n.args
            and isinstance(n.args[0], ast.Constant)]


@pytest.mark.parametrize("handler,expected", sorted(EXPECTED_CUE.items()))
def test_the_window_plays_its_sound(handler, expected):
    got = _cues(_method(handler))
    assert got, f"{handler} opens a window in silence — it should play {expected}"
    assert expected in got, f"{handler} plays {got}, the table says {expected}"


@pytest.mark.parametrize("handler,expected", sorted(EXPECTED_CUE.items()))
def test_the_cue_is_not_stranded_behind_the_modal(handler, expected):
    """A cue after `.exec()` is heard only once the window is dismissed."""
    fn = _method(handler)
    cue_lines = [n.lineno for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "_cue_window"]
    exec_lines = [n.lineno for n in ast.walk(fn)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr in ("exec", "warning", "critical",
                                      "information", "question")]
    if not exec_lines:
        pytest.skip("this one does not open the dialog itself")
    assert min(cue_lines) < min(exec_lines), (
        f"{handler} cues at line {min(cue_lines)} but opens its window at "
        f"{min(exec_lines)} — the sound would arrive after the window closes"
    )


def test_every_cue_names_a_real_sound_event():
    """A typo in the constant name is a silent window, not a crash."""
    for handler in EXPECTED_CUE:
        for cue in _cues(_method(handler)):
            assert hasattr(snd, cue), (
                f"{handler} cues {cue!r}, which core.sound does not define — "
                f"_cue_window swallows the AttributeError, so this window "
                f"would simply be silent"
            )


def test_the_user_facing_table_still_covers_these_windows():
    """The table is the promise; it must not quietly lose a row."""
    labels = {row[0] for row in WINDOW_ROWS}
    for expected in ("Instrument in Wrong Position",
                     "Confirm abort",
                     "No instrument found"):
        assert expected in labels, f"{expected!r} has gone from WINDOW_ROWS"
    assert WINDOW_ROWS and EVENT_ROWS


def test_every_row_names_a_sound_the_preferences_tab_offers():
    """A row promising a sound that does not exist is worse than no row."""
    offered = {
        "Patch read OK", "Patch reading looks off", "Strip read OK",
        "Strip read failed", "Instrument error", "Slow down",
        "Measurement finished", "Profile build finished",
    }
    for label, _mode, sound in WINDOW_ROWS + EVENT_ROWS:
        # One row deliberately names two sounds and explains the choice.
        if "," in sound or "—" in sound:
            continue
        assert sound in offered, (
            f"the table row {label!r} promises the sound {sound!r}, which is "
            f"not one of the sounds Preferences offers"
        )


def test_the_specification_tables_match_the_app():
    """`docs/design/measurement_window_sounds.md` is generated from these rows.

    Knut asked for the tables to be in the design specification. A specification
    that has drifted from the app is worse than none, so every row the app shows
    must appear in the document.
    """
    from pathlib import Path

    doc = (Path(__file__).resolve().parent.parent
           / "docs" / "design" / "measurement_window_sounds.md")
    assert doc.is_file(), "the window-sounds specification is missing"
    text = doc.read_text(encoding="utf-8")
    missing = [row[0] for row in WINDOW_ROWS + EVENT_ROWS
               if row[0].replace("|", "\\|") not in text]
    assert not missing, f"rows in the app but not in the specification: {missing}"
