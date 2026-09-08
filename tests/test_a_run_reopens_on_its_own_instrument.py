"""A CR30 project reopened as a ColorMunki, and then became one.

Basti, 2026-09-08: *"i have loaded the youtube project and the chart was made
for the cr30. but in guided mode it shows colormunki"*. His run's `.ti2` and
`channels.json` both said CR30; only `create_chart_ui.guided.instrument` said
CM, and the panel showed that faithfully.

ONE DEFECT WITH TWO ENDS, AND IT FEEDS ITSELF.

*Reading.* `_apply_ui_state` restored the Guided row first and the layout panel
second. The panel mirrors its instrument into the printtarg widgets, and
`_link_instrument_controls` mirrors those back into Guided, so the last writer
won and the last writer was a recipe: either the run's own, or, for a run with
none, the GLOBAL `manual_engine_recipe` that "Save as Defaults" leaves behind.
Captured by stack trace, not guessed. Fixed by applying the guided row LAST.

*Writing.* `create_chart_ui.engine_recipe` was taken from the Manual layout
panel unconditionally, whatever module the user was in, and nothing in a Guided
build ever writes a Guided choice into that panel. Measured on a CR30 sheet
with hexagons on: **12 of 85 fields disagreed** with what the build handed the
engine, the instrument (`i1`) and all four margins (the i1Pro's 26/38/19/9)
among them. NOT FIXED, and marked `xfail(strict=True)` below with the two
attempts that broke documented behaviour and the remaining candidate.

Fixing the reading end alone still breaks the loop where it does harm: a wrong
recipe no longer drags the Guided instrument with it, so the run stops becoming
a ColorMunki. What is left is a recipe that did not build this sheet being
carried by Duplicate run and "Load setup from preset".

WHY THESE ARE OFFSCREEN TESTS, when the report was an on-screen one. The first
review called this screen-only. It is not: crossing `win.show()` against the
presence of a saved layout default showed the platform makes no difference and
the saved default decides it. A fresh sandbox has none, which is why the whole
suite was blind. Setting it is all it takes, so there is no excuse for leaving
this to a driver.

Binding rules this restores: §2.0 (the target's own record is the single
writer), §4c D-2 (an instrument change may not overwrite a chosen value) and
§4c D-4 (saved defaults are not an answer).
"""
from __future__ import annotations

import json
import os

import pytest
from PyQt6.QtCore import QSettings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.file_manager import FileManager                        # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.tabs.tab_chart import TabChart                           # noqa: E402
from workflow.layout_engine.presets import (LayoutRecipe,        # noqa: E402
                                            default_recipe)

STORED_CR30 = {
    "mode": "guided",
    "engine_on": True,
    "guided": {"instrument": "CR30", "paper": "A4", "pages": 1,
               "double_density": True, "triple_density": False,
               "left_border": False, "no_strip_limit": False, "precond": ""},
}


def _tab(tmp_path, *, saved_default: str | None = None):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    if saved_default:
        # what "Save as Defaults" in the layout panel leaves behind, globally
        s.set("manual_engine_recipe",
              json.dumps(default_recipe(saved_default, "A4").to_dict()))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._user_switch_mode("guided")
    return t


def _pick(tab, code: str) -> None:
    i = tab._instr_combo.findData(code)
    tab._instr_combo.setCurrentIndex(i)
    tab._instr_combo.currentIndexChanged.emit(i)
    tab._instr_combo.activated.emit(i)


# ---------------------------------------------------------------------------
# reading: the run's own record wins
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("saved_default", [None, "CM", "i1"])
@pytest.mark.parametrize("run_recipe", [None, "CM", "i1"])
def test_the_guided_instrument_is_the_runs_own(qapp, tmp_path, saved_default,
                                               run_recipe):
    """Nine combinations of what else is lying around. The run wins every time.

    `run_recipe` is a recipe stored WITH the run that disagrees with its own
    Guided row, which is what the writing end used to produce; `saved_default`
    is the global one. Both used to beat the run.
    """
    tab = _tab(tmp_path, saved_default=saved_default)
    stored = dict(STORED_CR30)
    if run_recipe:
        stored["engine_recipe"] = default_recipe(run_recipe, "A4").to_dict()
    tab._apply_ui_state(stored)
    got = tab._shared_get("guided")
    assert got["instrument"] == "CR30", (
        f"saved default {saved_default!r} / run recipe {run_recipe!r} "
        "overwrote the instrument this run was built for"
    )
    assert got["double_density"] is True, \
        "the hexagon choice went with the instrument"


def test_the_two_modes_still_agree_afterwards(qapp, tmp_path):
    """The tempting fix was to suppress the mirror. That leaves Manual showing
    one instrument while Guided shows another, and the next write stores the
    disagreement: a loud fault turned into a quiet one. Ordering must fix it
    without breaking what the mirror is for."""
    tab = _tab(tmp_path, saved_default="CM")
    tab._apply_ui_state(dict(STORED_CR30,
                             engine_recipe=default_recipe("CM", "A4").to_dict()))
    guided = tab._shared_get("guided")["instrument"]
    manual = str(tab._manual_get("printtarg", "-i", ""))
    assert guided == manual == "CR30", \
        f"the modes disagree: Guided {guided!r}, Manual {manual!r}"


def test_a_load_round_trips_every_guided_field(qapp, tmp_path):
    """Apply, collect, compare. Anything that does not survive the round trip
    is a field the next write will file wrongly."""
    tab = _tab(tmp_path, saved_default="CM")
    tab._apply_ui_state(dict(STORED_CR30,
                             engine_recipe=default_recipe("i1", "A4").to_dict()))
    back = tab._collect_ui_state()["guided"]
    for field, want in STORED_CR30["guided"].items():
        assert back[field] == want, f"{field}: stored {want!r}, came back {back[field]!r}"


# ---------------------------------------------------------------------------
# writing: the record describes the chart this run builds
# ---------------------------------------------------------------------------
@pytest.mark.xfail(strict=True, reason=(
    "KNOWN, REPORTED, NOT FIXED. `create_chart_ui.engine_recipe` is taken from "
    "the Manual layout panel whatever module the user is in, and nothing in a "
    "Guided build writes a Guided choice into that panel, so a Guided session "
    "records a recipe describing a different chart: 12 of 85 fields, the "
    "instrument (i1 on a CR30 run) and all four margins (the i1Pro's "
    "26/38/19/9) among them. Two fixes were tried at the RECORDING end and "
    "each broke a documented behaviour: preferring the chart's own "
    "channels.json threw away a live panel edit "
    "(test_the_chart_sidecar_never_files_into_the_target.py), and deriving "
    "from the Guided row did the same. The remaining candidate is at the "
    "AUTHORING end -- have a Guided build seed the panel through "
    "`_apply_guided_engine_recipe`, which today runs only on the post-Generate "
    "module switch -- and that is a build-time change needing its own round. "
    "Its harm is now bounded: the reading end is fixed above, so a wrong "
    "recipe no longer drags the Guided instrument with it. What is left is "
    "Duplicate run and 'Load setup from preset' carrying a recipe that did not "
    "build this sheet."))
def test_a_guided_session_records_the_layout_it_would_build(qapp, tmp_path):
    """THE SUPPLY SIDE. With no chart yet, the record must describe what a build
    from what is on screen would produce, not what the Manual panel happens to
    hold. 12 of 85 fields disagree."""
    tab = _tab(tmp_path)
    _pick(tab, "CR30")
    tab._dd_check.setChecked(True)
    snap = tab._collect_ui_state()
    stored = snap.get("engine_recipe") or {}
    truth = LayoutRecipe.from_build_kwargs(
        tab._creator._engine_build_kwargs(tab._collect_guided())).to_dict()
    differ = {k: (stored.get(k), v) for k, v in truth.items()
              if stored.get(k) != v}
    assert not differ, (
        f"{len(differ)} of {len(truth)} fields describe a different chart: "
        f"{dict(list(differ.items())[:6])}"
    )
    assert stored.get("instrument") == "CR30"
    assert stored.get("hflag") is True, "the hexagon choice reached the record"


def test_the_record_is_never_simply_dropped(qapp, tmp_path):
    """"Stop recording it" was the other candidate fix and it re-opens the
    reading end: an absent key sends `_apply_ui_state` to the branch that resets
    the panel from the GLOBAL saved default. Duplicate run carries this key
    deliberately too (`DUPLICATE_META_CARRY`), so a duplicate builds the same
    sheet."""
    tab = _tab(tmp_path)
    _pick(tab, "CR30")
    assert tab._collect_ui_state().get("engine_recipe"), \
        "no recipe recorded at all"


def test_manual_still_records_the_panel(qapp, tmp_path):
    """The Guided branch must not have taken the Manual one's record away."""
    tab = _tab(tmp_path)
    tab._user_switch_mode("manual")
    rec = tab._collect_ui_state().get("engine_recipe")
    assert rec, "Manual stopped recording its own layout"
