"""The right-edge stamp the panel predicts must be the one the sheet carries.

Adversary round 22, 2026-09-15, measured and photographed on screen
(`scripts/adv22c_press_generate_twice_and_the_warning_changes.py`).

`_engine_text_notes` predicts how much of the right-edge note will be cut off
by building the stamped line itself:

    _pm.chart_layout_name = self._predicted_chart_layout_name()
    _stamped_line = _JOIN.join(self._creator.stamp_lines(_pm, _np))

That field used to be filled from `_active_layout_name()`, which answers *"what
would this chart's layout be called"* and falls back to
``Path(self._current_ti1_path).stem``. Every finished build sets
`_current_ti1_path`, an ordinary targen build included — but the BUILD only
carries a layout name down the `_generate_from_ti1` route; `_on_generate`
leaves the field None and the stamper prints the targen command.

So from the first Manual build onwards the panel predicted

    Canon Pro-1000 / Photo Rag 308  |  Chart layout adv22c  |  …      (122 ch)

for a sheet that stamps

    Canon Pro-1000 / Photo Rag 308  |  targen -d2 -f609 -e4 -B4 -G -g35 adv22c  |  …   (145 ch)

and the difference is not academic: at i1Pro / A4 / 14 pt the sheet ends
"…ChromI…" with 15 characters cut, and the panel said NOTHING about it, at
every right margin from 6.0 to 30.0 mm
(`scripts/adv22d_the_margin_where_the_panel_says_nothing.py`, 49 margins swept,
49 of them silent). The rendered right-edge strip is in
`~/Desktop/ChromIQ-adversary-22-2026-09-15/C-second-right-margin-tail.png`.

Both directions are guarded here: a plain targen build must predict NO layout
name, and every route that really does lay out an armed patch set must still
predict one, which is Knut's ColorMunki report of 2026-09-13 and the reason the
field is set at all.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from ui.tabs.tab_chart import TabChart


class _Check:
    def __init__(self, on: bool):
        self._on = on

    def isChecked(self) -> bool:
        return self._on


class _Tab:
    """A stand-in carrying only what `_predicted_chart_layout_name` reads."""

    _gamut_active = False
    _reflected_active = False
    _applied_active = False
    _applied_src_dir = None
    _applied_targen_sig = None
    _prebuilt_active = False
    _prebuilt_key = None
    _prebuilt_targen_sig = None
    _preset_ti1_path = None
    _preset_ti1_targen_sig = None
    _override_targen_check = None
    _tc918_active = False
    _tc918_targen_sig = None
    _knut_active = False
    _knut_targen_sig = None

    def __init__(self, mode: str = "manual", signature: str = "sig",
                 name: str | None = "adv22", **kw):
        self._mode = mode
        self._signature = signature
        self._name = name
        for k, v in kw.items():
            setattr(self, k, v)

    def _current_mode(self) -> str:
        return self._mode

    def _targen_signature(self) -> str:
        return self._signature

    def _active_layout_name(self):
        return self._name


def _predict(tab) -> "str | None":
    return TabChart._predicted_chart_layout_name(tab)


# ---- the fault ------------------------------------------------------------
def test_an_ordinary_manual_build_predicts_the_targen_line():
    """`_current_ti1_path` is set by every finished build, so
    `_active_layout_name()` answers with a stem here — and the sheet still
    stamps targen. This is the state a user is in whenever the "Measured from
    Preview" frame has anything to measure."""
    tab = _Tab(name="adv22c")
    assert tab._active_layout_name() == "adv22c", "the stand-in proves nothing"
    assert _predict(tab) is None, (
        "the panel predicts “Chart layout adv22c” for a sheet that will stamp "
        "“targen -d2 -f… adv22c”, so its note-length warning is 23 characters "
        "short and can fall silent altogether")


def test_guided_predicts_the_targen_line():
    assert _predict(_Tab(mode="guided")) is None


# ---- and the cases the field exists for -----------------------------------
def test_the_gamut_module_predicts_a_layout_name():
    """FROM PROFILE GAMUT hands every build to `_generate_from_ti1`."""
    assert _predict(_Tab(_gamut_active=True, name="gam")) == "gam"


def test_a_bundled_patch_set_preset_predicts_its_layout_name():
    """Knut's ColorMunki report, 2026-09-13, and the on-screen re-measurement
    of round 22: selecting the built-in still answers with the preset's own
    name."""
    assert _predict(_Tab(_knut_active=True, _knut_targen_sig="sig",
                         name="ColorMunki-A4-84p")) == "ColorMunki-A4-84p"
    assert _predict(_Tab(_tc918_active=True, _tc918_targen_sig="sig",
                         name="TC9.18")) == "TC9.18"


def test_a_loaded_patch_set_predicts_its_layout_name():
    assert _predict(_Tab(_preset_ti1_path="/tmp/x.ti1", name="x")) == "x"


@pytest.mark.parametrize("kw,label", [
    (dict(_tc918_active=True, _tc918_targen_sig="other"), "TC9.18"),
    (dict(_knut_active=True, _knut_targen_sig="other"), "a Knut preset"),
    (dict(_preset_ti1_path="/tmp/x.ti1", _preset_ti1_targen_sig="other",
          _override_targen_check=_Check(True)), "a loaded patch set"),
    (dict(_prebuilt_active=True, _prebuilt_key="k",
          _prebuilt_targen_sig="other"), "a prebuilt preset"),
    (dict(_applied_active=True, _applied_src_dir="/tmp",
          _applied_targen_sig="other"), "an applied editor chart"),
])
def test_an_edited_recipe_falls_back_to_the_targen_line(kw, label):
    """Every one of these drops its patch set and runs targen once the targen
    recipe has been edited, which is what `_on_generate` does."""
    assert _predict(_Tab(**kw)) is None, (
        f"{label} with an edited targen recipe still predicts a layout name, "
        f"but that build runs targen and the sheet stamps its command")


def test_a_loaded_patch_set_keeps_its_name_while_the_panel_is_locked():
    """A signature difference with the override box UNTICKED is something the
    app did to itself, not the user opting in — `_on_generate` reuses the .ti1,
    so the prediction must too."""
    assert _predict(_Tab(_preset_ti1_path="/tmp/x.ti1",
                         _preset_ti1_targen_sig="other",
                         _override_targen_check=_Check(False),
                         name="x")) == "x"


# ---- and the wiring -------------------------------------------------------
def test_the_prediction_asks_the_predicate_not_the_label():
    """MUTATION: put `_active_layout_name` back at the call site and this goes
    red. Read off the syntax tree, because both names appear in comments."""
    tree = ast.parse(textwrap.dedent(
        inspect.getsource(TabChart._engine_text_notes)))
    calls = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "chart_layout_name"
                for t in n.targets)
    ]
    assert calls, "the prediction no longer sets chart_layout_name at all"
    for c in calls:
        assert (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and c.func.attr == "_predicted_chart_layout_name"), (
            "the stamp prediction is back on `_active_layout_name`, which "
            "answers for the chart already built rather than for the build "
            "the Generate button will run")


def test_the_predicate_never_answers_from_the_ti1_path_alone():
    """The whole fault was the `_current_ti1_path` fallback leaking into a
    prediction, so the predicate must not read that attribute itself."""
    fn = ast.parse(textwrap.dedent(
        inspect.getsource(TabChart._predicted_chart_layout_name))).body[0]
    names = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    names |= {c.value for c in ast.walk(fn)
              if isinstance(c, ast.Constant) and isinstance(c.value, str)
              and c is not (fn.body[0].value if isinstance(fn.body[0], ast.Expr)
                            else None)}
    assert "_current_ti1_path" not in names, (
        "the predicate reaches for `_current_ti1_path`, which is set by every "
        "finished build and is exactly what made the panel lie")
