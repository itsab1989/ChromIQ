"""A warning about a line must measure the line the sheet prints.

Knut's own report of 2026-09-13 used this custom sheet text::

    {project}-{rundescription}-{page}-{paper}-{date}-{pages}-{patchcount}-{dpi}-{seed}

and observed that 13 pt warned and 12 pt did not. The panel was measuring that
string with the braces still in it. The sheet prints the resolved one, and on a
plausible ColorMunki A4 chart that is two characters longer and **12.6 mm
wider** at 12 pt, because digits and capitals are wider than braces and
lowercase.

The error goes both ways, which is why it is not "close enough":

* `{seed}` alone measures 23.3 mm NARROWER than "seed 1270124825", so a line
  that runs off the sheet can be called fine;
* a long chain of token names measures 11.3 mm WIDER than what it resolves to,
  so a sheet that comes out clean can be called broken.

Both bottom lines and the clip-border text take the same placeholders and are
drawn by the same renderer through the same `resolve_placeholders`. The panel
asks that function and `chart.text_placeholder_context`, the two the build
itself uses, so a token cannot be filled one way for the prediction and another
for the sheet.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow.layout_engine.presets import LayoutRecipe    # noqa: E402

KNUT = ("{project}-{rundescription}-{page}-{paper}-{date}-{pages}-"
        "{patchcount}-{dpi}-{seed}")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    t.deleteLater()


def _recipe(**kw) -> LayoutRecipe:
    r = LayoutRecipe()
    r.instrument, r.paper = "CM", "A4"
    r.layout_mode, r.use_instrument_margins = "area_first", False
    r.margin_top = r.margin_bottom = 15.0
    r.margin_left = r.margin_right = 12.0
    r.text_edge_top_mm = r.text_edge_mm = r.text_edge_clip_mm = 4.0
    r.chart_text, r.stamp_command = KNUT, False
    r.chart_text_size_mm = 12.0 * 25.4 / 72.0
    r.helper_markers = False
    r.helper_marker_edge_mm, r.helper_marker_len_mm = 4.0, 2.0
    r.helper_markers_top_bottom = r.helper_markers_sides = True
    r.clip_border = False
    r.randomize, r.seed_fixed, r.seed = True, True, 1270124825
    for k, v in kw.items():
        setattr(r, k, v)
    return r


# ------------------------------------------------------- the two functions
def test_the_context_and_the_build_agree_on_every_token():
    """`build_chart` must fill a token exactly as the panel predicts it."""
    from workflow.layout_engine.chart import text_placeholder_context
    ctx = text_placeholder_context(
        project="Proj", rundescription="Run 1", instrument="CM", paper="A4",
        dpi=200, patches=84, pages=2, seed=42, chart_date="2026-09-13")
    assert ctx["instrument"] == "ColorMunki"
    assert ctx["paper"] == "A4 portrait"
    assert ctx["dpi"] == "200 dpi"
    assert ctx["patchcount"] == "84 patches"
    assert ctx["pages"] == "2"
    assert ctx["seed"] == "seed 42"
    assert ctx["date"] == "2026-09-13"
    # `{page}` needs a page index and belongs to the renderer, not here.
    assert "page" not in ctx


def test_unknown_placeholders_are_left_alone():
    """A typo must print as typed, not blow up the prediction."""
    from workflow.layout_engine.raster import resolve_placeholders
    assert resolve_placeholders("{nosuchtoken}", {"a": "b"}) == "{nosuchtoken}"
    assert resolve_placeholders("", {}) == ""
    assert resolve_placeholders("{a}", {"a": "x"}) == "x"


def test_the_renderer_uses_that_same_function():
    """MUTATION: give `render_pages` a private copy again and this goes red."""
    import inspect
    from workflow.layout_engine import raster
    src = inspect.getsource(raster.render_pages)
    assert "_resolve_with = resolve_placeholders" in src, (
        "render_pages defines its own resolver again, so the panel and the "
        "sheet can fill a token differently")


# ------------------------------------------------------------- the panel
def test_the_bottom_line_is_measured_resolved(tab):
    """MUTATION: measure `r.chart_text` raw and this goes red."""
    r = _recipe()
    lines = tab._bottom_sheet_text_lines(r)
    assert len(lines) == 1
    assert "{" not in lines[0], f"the panel still measures the braces: {lines[0]}"
    assert "seed 1270124825" in lines[0], lines[0]
    assert "A4 portrait" in lines[0], lines[0]


def test_the_difference_is_big_enough_to_change_a_verdict(tab):
    """The control: if resolving moved the width by a fraction of a millimetre
    this whole file would be pedantry."""
    from workflow.layout_engine.raster import sheet_text_width_mm
    from ui.tabs.tab_chart import TabChart
    r = _recipe()
    resolved = tab._sheet_text_width_mm(r)
    raw = sheet_text_width_mm([KNUT], r.chart_text_size_mm,
                              TabChart._DEFAULT_SHEET_TEXT_FONT, False, False,
                              float(getattr(r, "dpi", 300) or 300))
    assert abs(resolved - raw) > 5.0, (
        f"resolving the tokens moved the width by only {abs(resolved-raw):.2f} mm")


def test_every_clip_text_call_site_resolves_first(tab):
    """The identical fault one frame over. `{seed}` in the clip text was
    measured as six characters and prints as fifteen.

    **EVERY call site, and read off the SYNTAX TREE.** Two ways of writing this
    test were wrong before this one:

    * `src.index("clip_text_lines(")` takes the FIRST occurrence, which landed
      on a site that had not been fixed, and reported the fix missing while the
      one it was written for was in place;
    * searching the text finds the occurrence inside a code COMMENT
      (``# round: `len(clip_text_lines(...)) ...` ``) and calls it a raw call
      site. A comment defeated an identical wiring test earlier the same day.

    So the calls come from `ast`, where a comment does not exist, and each
    one's first argument must itself be a call to `resolve_placeholders`.
    """
    import ast
    import inspect
    import textwrap
    from ui.tabs.tab_chart import TabChart

    tree = ast.parse(textwrap.dedent(
        inspect.getsource(TabChart._engine_text_notes)))
    raw = []
    seen = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "clip_text_lines"):
            continue
        seen += 1
        arg = node.args[0] if node.args else None
        if not (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name)
                and arg.func.id == "resolve_placeholders"):
            raw.append(getattr(node, "lineno", "?"))
    assert seen >= 2, f"expected several call sites, found {seen}"
    assert not raw, (
        f"{len(raw)} of {seen} clip_text_lines calls still measure the raw "
        f"placeholders, at offsets {raw} inside _engine_text_notes")


# ------------------------------------------------------------------ the seed
def test_a_seed_of_zero_is_a_seed(tab):
    """ADVERSARY REPRODUCTION, and it was a false WARNING, which is the worse
    direction.

    The stand-in was reached with `getattr(r, "seed", None) or _WIDEST_SEED`,
    and 0 is falsy, so a recipe carrying seed 0 predicted ten digits where the
    sheet prints one. It is reachable without trying: the seed box ranges from
    0 and the panel writes whatever it holds the moment "Use a fixed seed" is
    ticked. Driven on screen, the panel said 3 mm ran off at 13 pt while the
    rendered ink stopped 10.61 mm inside the bound.
    """
    zero = tab._seed_for_prediction(_recipe(seed=0))
    assert zero == 0, f"a seed of 0 was replaced by {zero}"
    assert tab._seed_for_prediction(_recipe(seed=7)) == 7
    lines = tab._bottom_sheet_text_lines(_recipe(seed=0, stamp_command=True,
                                                 chart_text=""))
    assert lines and lines[0].endswith("seed 0"), lines


def test_an_absent_seed_is_never_predicted_wider_than_it_can_be(tab):
    """The stand-in must not INVENT an overflow.

    `pick_seed` draws `randint(0, 2_147_483_647)`: nine digits or fewer 46.6 %
    of the time and ten the rest. A ten-digit stand-in is therefore one
    character too wide almost half the time, and one character is 2.71 mm at
    13 pt on Inter. Nine digits is either exact or one short, never long, which
    is the right way round for a figure nobody can control.
    """
    n = tab._seed_for_prediction(_recipe(seed=None))
    assert 100_000_000 <= n <= 999_999_999, (
        f"the stand-in seed {n} is not nine digits, so the prediction can be "
        f"wider than any seed the build will draw")


def test_the_remedy_is_only_offered_when_it_works(tab):
    """ADVERSARY REPRODUCTION. The sentence naming the stamp tick was appended
    whenever the stamp was the WIDEST line, so with a long custom line as well
    it could be right about that and still useless: switching the stamp off
    left the sheet just as far over, 19.61 mm at 13 pt and 23.93 at 14. A
    remedy that changes nothing is worse than none."""
    r = _recipe(stamp_command=True, chart_text="X" * 400)
    widths = tab._bottom_line_widths_mm(r)
    assert len(widths) == 2, widths
    # Room the custom line alone still overflows: removing the stamp cannot
    # help, so the sentence must not be offered.
    assert tab._stamp_is_the_line_to_remove(r, widths[0] - 10.0) is False
    # Room the custom line fits in but the pair does not: now it helps.
    assert tab._stamp_is_the_line_to_remove(r, widths[0] + 1.0) is True
    # No stamp at all, nothing to offer.
    assert tab._stamp_is_the_line_to_remove(
        _recipe(stamp_command=False), 1000.0) is False


# --------------------------------------------- the block that swallows errors
def test_the_placeholder_context_can_never_silence_the_panel(tab):
    """`_engine_text_notes` wraps its whole body in one `except Exception:
    pass`, so anything that throws inside it does not lose one placeholder, it
    loses EVERY warning on the panel.

    That is not hypothetical: adding the context lookup turned 37 tests red
    reporting "no clip-text warning at all" for a chart that has one, because
    the lookup reached for a widget that was not there. The message was about
    the wrong thing and the code it accused was correct, which is the worst
    shape a failure can take.

    So the context is built from a recipe that answers badly to everything.
    """
    class _Hostile:
        def __getattr__(self, name):
            if name in ("seed",):
                return "not a number"
            raise AttributeError(name)

    ctx = tab._text_placeholder_context(_Hostile())
    assert isinstance(ctx, dict) and "seed" in ctx and "page" in ctx
    assert tab._seed_for_prediction(_Hostile()) > 0
    # And the real method still produces its notices for a real recipe.
    from ui.tabs.tab_chart import TabChart
    everything, _over = TabChart._engine_text_notes(tab)
    assert isinstance(everything, list)
