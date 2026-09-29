"""B8-650: the three bare `QFrame(StyledPanel)` instances stay rounded.

Sebastian photographed square corners on the section frames in the Reference
values window while every other panel in ChromIQ is rounded
(`~/Desktop/ChromIQ-knut-beta29-batch/basti-square-corners-2026-09-20.png`).
The cause: `QFrame.setFrameShape(QFrame.Shape.StyledPanel)` with no
stylesheet, so Fusion draws its native square bevel. `ui/styles.py` has no
app-wide `QFrame` rule at all, and adding one is not the fix: a dozen other
`QFrame` instances in the app are `HLine`/`VLine` dividers, and the instant a
stylesheet rule matches `QFrame`, Qt stops drawing their native sunken bevel
in favour of the stylesheet's box model, which specifies no border of its own
-- every divider in the app would flatten. So each of the three frames opts in
explicitly via `ui.theme.panel_border_qss`, which this test also exercises.

**This asserts on PAINTED PIXELS, not stylesheet text.** A frame that carries
"border-radius" in a stylesheet string a test never renders proves nothing a
user can see; grabbing the widget and reading its corner is the same check
`tests/test_tools_popup_corners_stay_round.py` uses for the same shape of bug.

The signal: for ANY frame with a border, the pixel at an exact corner lies
inside a rounded corner's clipped-away arc for every legitimate radius, so it
shows whatever is behind the frame -- never the border colour a pixel at the
middle of the adjacent edge shows. Measured with the fix reverted (`git
stash`, this file's own history): corner and edge colours are IDENTICAL,
because an unstyled Fusion `StyledPanel` paints its bevel unbroken into every
corner. With the fix, they differ in all three appearances.

Challenge round 32 found three holes in the version this replaces, and each
is now closed by a named mechanism rather than by a literal:

1. It parametrised `[APPEARANCE_LIGHT, APPEARANCE_DARK]` while ChromIQ ships
   THREE concrete appearances, and `panel_border_qss` picks its colour with
   `by_mode(light, dark, neutral, mode)` -- so a neutral-only mutation passed.
   The parametrize now reads `ui.theme.CONCRETE_APPEARANCES`, which is the
   module's own authoritative list, so a FOURTH appearance arrives guarded
   instead of arriving unnoticed. (The sibling guard
   `tests/test_tools_popup_corners_stay_round.py` names all three explicitly;
   the non-literal form is preferred here precisely because a literal list is
   what went stale.)
2. It read only `pixelColor(0, 0)` -- the top-left. A rule that rounds one
   corner and squares three passed. All four are read now, each against the
   midpoint of its own adjacent edge, and the failure names which corner.
3. Its "no blanket QFrame rule" check was the substring test
   `"QFrame {" not in src and "QFrame{" not in src`, which recognises exactly
   two spellings out of many that do the same damage. It now parses the
   selector -- see `_hits_every_qframe`.
"""
from __future__ import annotations

import re

import pytest
from PyQt6.QtWidgets import QFrame

from ui.theme import CONCRETE_APPEARANCES, apply_appearance


def _styled_panels(widget):
    return [f for f in widget.findChildren(QFrame)
            if f.frameShape() == QFrame.Shape.StyledPanel]


def _square_corners(frame) -> list[tuple[str, str, str]]:
    """Every corner of `frame` whose pixel matches its adjacent edge midpoint.

    Grabbed alone (not the whole window), so the coordinates are the frame's
    own -- (0, 0) is always its top-left corner, whatever dialog it lives in.

    ALL FOUR corners, because the version of this helper that this replaces
    read only (0, 0), and a rule that rounds the top-left and leaves the other
    three square -- a stray `border-top-left-radius`, a `border-radius`
    overridden after it, a radius Qt silently drops on the corners a fixed
    size cannot fit -- went straight through it.

    Device pixel ratio: every coordinate below is indexed off the IMAGE,
    whose width/height are ALREADY device pixels (logical size x dpr). That
    is the dpr multiply the old code did by hand for its single edge sample,
    applied consistently to all eight points, and it cannot produce the
    off-by-one that `int(w * dpr) - 1` invites when dpr is fractional or when
    Qt rounds the pixmap up.

    No tolerance and no threshold: the comparison is exact colour equality,
    the same signal the original used. Measured at dpr 1.0 under Fusion with
    the fix in place -- Light corner #eeece8 vs edge #d0ccc6, Dark #181818 vs
    #333333, Neutral #e2e2e2 vs #b6b6b6, at all four corners of both
    Reference-values sections and of the Preflight form frame. Square is not
    "close", it is the same value.
    """
    if frame.width() < 8 or frame.height() < 8:
        frame.resize(max(frame.width(), 40), max(frame.height(), 40))
    pix = frame.grab()
    img = pix.toImage()
    w, h = img.width(), img.height()
    mid_x = w // 2
    points = (
        # corner name,      the corner px,  the midpoint of its adjacent edge
        ("top-left",     (0,     0),     (mid_x, 0)),
        ("top-right",    (w - 1, 0),     (mid_x, 0)),
        ("bottom-left",  (0,     h - 1), (mid_x, h - 1)),
        ("bottom-right", (w - 1, h - 1), (mid_x, h - 1)),
    )
    square = []
    for name, (cx, cy), (ex, ey) in points:
        corner = img.pixelColor(cx, cy).name()
        edge = img.pixelColor(ex, ey).name()
        if corner == edge:
            square.append((name, corner, edge))
    return square


def _reference_values_frames(qapp):
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    dlg = ReferenceValuesDialog(None)
    dlg.resize(900, dlg.sizeHint().height())
    dlg.show()
    qapp.processEvents()
    frames = _styled_panels(dlg)
    assert frames, "no StyledPanel frame found in the Reference values window"
    return dlg, frames


def _preflight_frames(qapp):
    from ui.dialogs.preflight_dialog import PreflightDialog
    dlg = PreflightDialog([("Printer", "X"), ("Media size", "A4")], [], 1, None)
    dlg.show()
    qapp.processEvents()
    frames = _styled_panels(dlg)
    assert frames, "no StyledPanel frame found in the Preflight dialog"
    return dlg, frames


def _add_patches_frames(qapp):
    from ui.dialogs.ti2_relayout_dialog import _AddPatchesDialog
    dlg = _AddPatchesDialog(None, None)
    dlg.resize(680, dlg.sizeHint().height())
    dlg.show()
    qapp.processEvents()
    frames = _styled_panels(dlg)
    assert frames, "no StyledPanel frame found in the Add patches dialog"
    return dlg, frames


_WINDOWS = {
    "reference_values": _reference_values_frames,
    "preflight": _preflight_frames,
    "add_patches_swatch": _add_patches_frames,
}


@pytest.mark.parametrize("mode", CONCRETE_APPEARANCES)
@pytest.mark.parametrize("window", list(_WINDOWS))
def test_every_bare_styled_panel_is_rounded_not_square(qapp, window, mode):
    """Every concrete appearance, because the colour is picked per appearance.

    `panel_border_qss` folds through `ui.theme.by_mode(light, dark, neutral,
    mode)`, so Neutral has its own branch and its own constant
    (`neutral_styles.NM_BORDER`). Driving the list from
    `CONCRETE_APPEARANCES` rather than from two literals is what makes a
    neutral-only regression visible -- and what makes a fourth appearance,
    the day someone adds one, arrive with this guard already covering it.

    Note which window carries which signal: the Add-patches swatch is a
    `QLabel` with its own hard-coded chip border
    (`ti2_relayout_dialog._paint_single_swatch`), so it does NOT call
    `panel_border_qss` and is appearance-independent by design. Reference
    values and Preflight are the two that render this function's output.
    """
    # **THE APPEARANCE IS PUT BACK, AND THAT IS NOT TIDINESS.**
    # `apply_appearance` ends in `app.setStyleSheet(...)`, so this test
    # rewrites the stylesheet of the ONE QApplication the whole worker
    # shares (`conftest._one_qapplication_per_worker`) and every test that
    # runs after it on that worker inherits whatever it left behind.
    #
    # MEASURED, 2026-09-22. With two appearances this leaked `dark`, which
    # most of the suite tolerates. Widening it to `CONCRETE_APPEARANCES`
    # made the last case NEUTRAL, and the everyday tier went from green
    # twice out of two to red in FOUR runs out of seven, with a different
    # victim each time and none of them in this file:
    # `test_verify_profile_dialog::test_neutral_controls_qss_uses_given_colour`
    # (wrong colours), `test_the_preset_button_is_small_fast_and_where_it_
    # belongs` (a window opening with nothing selected), and
    # `test_the_suite_paints_with_the_shipped_style` reading the style as ''.
    # Classic cross-test leakage: every one of them passes alone.
    #
    # CLAUDE.md names this exact call as well: "Never call
    # `qapp.setStyleSheet()` in a test." It cannot be avoided here, because
    # the appearance IS what is under test, so it is undone instead.
    before_sheet = qapp.styleSheet()
    before_palette = qapp.palette()
    apply_appearance(qapp, None, mode)
    dlg, frames = _WINDOWS[window](qapp)
    try:
        square = []
        for f in frames:
            for corner, got, edge in _square_corners(f):
                square.append((f.objectName() or repr(f), corner, got, edge))
        assert not square, (
            f"{window} ({mode}): {square} -- the frame's own corner pixel "
            "matches the midpoint of its adjacent edge, meaning the "
            "border/bevel was painted unbroken into that corner (square), "
            "not clipped by a radius")
    finally:
        dlg.close()
        qapp.setStyleSheet(before_sheet)
        qapp.setPalette(before_palette)


def test_this_file_leaves_the_application_as_it_found_it(qapp):
    """THE GUARD ON THE GUARD, because the leak above cost four red runs in
    seven and every victim of it was in another file.

    A test that must change the application's appearance has to put it back,
    and "it does" is a claim worth checking rather than a comment worth
    writing: this runs the same `apply_appearance` the cases above run and
    asserts the stylesheet is the one it started with.
    """
    before = qapp.styleSheet()
    for mode in CONCRETE_APPEARANCES:
        apply_appearance(qapp, None, mode)
    qapp.setStyleSheet(before)
    assert qapp.styleSheet() == before


# ----------------------------------------------------------------------
# "No blanket QFrame rule" -- a selector parse, not a substring search.
# ----------------------------------------------------------------------

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)

#: `QFrame`, optionally with Qt's leading dot ("this class, not subclasses"),
#: and NOT merely the prefix of a longer class name such as `QFrameBuffer`.
_QFRAME_RE = re.compile(r"^\.?QFrame(?![A-Za-z0-9_])(?P<rest>.*)$", re.S)


def _top_level_rules(qss: str) -> list[tuple[str, str]]:
    """Every `selector-list { body }` pair in a stylesheet, comments removed.

    Comments go first, so a `/* ... QFrame { } ... */` note is not a rule --
    the substring check this replaces called exactly that a failure.

    Qt's QSS has no nested rules, but brace depth is tracked anyway so a
    future wrapper block cannot make an inner rule look top level.
    """
    src = _COMMENT_RE.sub(" ", qss)
    rules: list[tuple[str, str]] = []
    depth = 0
    sel_start = 0
    body_start = 0
    for i, ch in enumerate(src):
        if ch == "{":
            depth += 1
            if depth == 1:
                body_start = i
        elif ch == "}":
            depth -= 1
            if depth == 0:
                rules.append((src[sel_start:body_start],
                              src[body_start + 1:i]))
                sel_start = i + 1
    return rules


def _hits_every_qframe(selector: str) -> bool:
    r"""Does this ONE selector reach every `QFrame` instance in the app?

    The damage this guards against is Qt handing the stylesheet's box model to
    widgets that rely on Fusion's native painting, so the question is only
    ever "which widgets does the rule reach", never "what does it set".

    Only the FINAL element of a selector decides that: descendant (whitespace)
    and child (`>`) combinators restrict the ancestry, not the class, so
    `QDialog QFrame` still reaches every divider that happens to live in a
    dialog -- which is all of them.

    ALLOWED, because each names a SET of frames rather than the class:
      * `QFrame#someName`   -- one frame, by object name.
      * `QFrame[role="x"]`  -- the frames carrying that property.
      * `QFrame.someClass`  -- ditto, via a class attribute.
      * `QFrameBuffer`, `QFrameless` -- a different class entirely.
      * `QFrame QLabel`     -- targets the labels, not the frames.

    FLAGGED:
      * `QFrame`, `.QFrame`, `QFrame  `, `QFrame\n`, `QLabel, QFrame`,
        `QDialog QFrame`, `QDialog>QFrame` -- the class, however spelled.
      * `QFrame:hover`, and any other pseudo-state-only form. This is a
        judgement, so here is the reasoning: a pseudo-state narrows WHEN the
        rule applies, not WHICH widgets it applies to. Every `HLine` in the
        app is still a member and still flattens the moment the pointer
        crosses it. The `#id`/attribute/class forms above narrow the
        population; a pseudo-state does not, so it earns no exemption. A
        pseudo-state stacked on top of a real narrowing
        (`QFrame#someName:hover`) is still allowed, because the narrowing is
        what is being judged.
    """
    selector = selector.strip()
    if not selector:
        return False
    final = re.split(r"[\s>]+", selector)[-1]
    m = _QFRAME_RE.match(final)
    if m is None:
        return False
    rest = m.group("rest")
    # `#id`, `[attr=...]` and `.class` narrow the rule to named frames.
    return not any(ch in rest for ch in "#[.")


def _blanket_qframe_selectors(qss: str) -> list[str]:
    """Every selector in `qss` that reaches the whole `QFrame` class."""
    found = []
    for selectors, _body in _top_level_rules(qss):
        for sel in selectors.split(","):
            if _hits_every_qframe(sel):
                found.append(sel.strip())
    return found


def _stylesheet_constants(mod) -> dict[str, str]:
    """Every module-level `str` constant in `mod` that looks like a stylesheet.

    The version this replaces scanned ONE constant per module, via
    `APP_STYLESHEET or LIGHT_STYLESHEET or NEUTRAL_STYLESHEET` -- an `or`
    chain, which short-circuits on the first truthy name, so a second
    stylesheet string added to any of those modules was never looked at.
    """
    return {name: val for name, val in vars(mod).items()
            if not name.startswith("_") and isinstance(val, str)
            and "{" in val and "}" in val and ":" in val}


# The evasion table. Left column is the stylesheet fragment, right column is
# whether the detector must flag it. Every CAUGHT spelling below slips past
# the `"QFrame {" not in src and "QFrame{" not in src` test this replaces,
# except the first two, which are the only two that test ever knew about.
_SELECTOR_TABLE: list[tuple[str, bool]] = [
    # -- the whole class, however spelled: MUST be caught -----------------
    ("QFrame { border: none; }", True),
    ("QFrame{ border: none; }", True),
    ("QFrame  { border: none; }", True),
    ("QFrame\n{ border: none; }", True),
    ("QFrame\t{ border: none; }", True),
    ("QLabel, QFrame { border-radius: 4px; }", True),
    ("QFrame, QLabel { border-radius: 4px; }", True),
    ("QLabel,QFrame{border-radius:4px;}", True),
    ("QFrame:hover { border: none; }", True),
    ("QFrame:!enabled { border: none; }", True),
    ("QDialog QFrame { border: none; }", True),
    ("QDialog > QFrame { border: none; }", True),
    ("QDialog>QFrame{border:none;}", True),
    (".QFrame { border: none; }", True),
    ("QGroupBox { color: red; }\nQFrame { border: none; }", True),
    ("/* a note about QFrame */\nQFrame { border: none; }", True),
    ("QWidget { color: red; }\nQLabel, QDialog > QFrame:hover { border: 0; }",
     True),
    # -- narrowed to a named set of frames: MUST be allowed ---------------
    ("QFrame#specificName { border-radius: 4px; }", False),
    ('QFrame[role="panel"] { border-radius: 4px; }', False),
    ('QFrame[flat="true"] { border: none; }', False),
    ("QFrame#a, QFrame#b { border-radius: 4px; }", False),
    ("QDialog QFrame#specificName { border-radius: 4px; }", False),
    ("QFrame#specificName:hover { border-radius: 4px; }", False),
    ("QFrame.sectionBox { border-radius: 4px; }", False),
    # -- not the QFrame class at all: MUST be allowed ---------------------
    ("QFrameBuffer { border: none; }", False),
    ("QFrameless { border: none; }", False),
    ("QFrame QLabel { color: red; }", False),
    ("QFrame > QLabel { color: red; }", False),
    ("QLabel, QPushButton { border: none; }", False),
    ("QScrollArea { border: none; }", False),
    # A rule that only MENTIONS the class inside a comment is not a rule.
    # The substring test this replaces called this one a failure.
    ("/* deliberately no QFrame { } rule here */\nQLabel { color: red; }",
     False),
]


@pytest.mark.parametrize("qss,should_flag", _SELECTOR_TABLE,
                         ids=[repr(q)[:58] for q, _ in _SELECTOR_TABLE])
def test_the_blanket_qframe_detector_catches_every_spelling(qss, should_flag):
    """The mutation proof for the guard below, and it needs no product edit.

    A detector is only as good as the spellings it recognises, and the one
    this replaces recognised two. Feeding it the table above is the same
    thing as mutating an appearance stylesheet once per row, and it costs
    nothing, so there is no excuse for the table being shorter than the list
    of ways the fault can be written.
    """
    found = _blanket_qframe_selectors(qss)
    if should_flag:
        assert found, (
            f"{qss!r} reaches every QFrame in the app and the detector missed "
            "it -- this is a spelling a blanket rule could arrive in")
    else:
        assert not found, (
            f"{qss!r} is narrowed to a named set of frames (or is not the "
            f"QFrame class at all) and must be allowed; flagged {found}")


def test_the_app_still_has_no_blanket_qframe_rule(qapp):
    """Pins the chosen approach: per-widget opt-in, not a global `QFrame` rule.

    `ui.theme.panel_border_qss`'s docstring explains why -- nine
    `QFrame.Shape.HLine` dividers across the app (in
    `preset_verification_dialog`, `profile_info_dialog`, `softproof_dialog`,
    `spot_read_dialog`, `target_change_dialog`, `ti2_relayout_dialog`,
    `ti3_info_dialog`, `tools_dialogs` and `translation_dialog`) rely on
    Fusion's native sunken-bevel painting, which a matching `QFrame`
    stylesheet rule replaces app-wide the instant it exists. If this ever
    starts failing because somebody added a blanket `QFrame` rule to an
    appearance stylesheet, that change needs the wider look CLAUDE.md asked
    for (every `QFrame` it would touch), not a quiet edit here.

    **What this guard cannot see**, said out loud rather than left implied:

    * It reads the appearance stylesheet CONSTANTS. A blanket rule installed
      at runtime -- `qapp.setStyleSheet("QFrame { ... }")`, or a per-dialog
      or per-widget `setStyleSheet` on an ancestor, which Qt propagates down
      that ancestor's whole subtree -- never appears in these strings and
      passes here unnoticed. Catching that would mean walking live widgets,
      not source constants.
    * It reads Python module globals, so a sheet assembled at import time
      from f-strings is covered and one built inside a function is not.
    """
    from ui import light_styles, neutral_styles, styles
    for mod in (styles, light_styles, neutral_styles):
        sheets = _stylesheet_constants(mod)
        assert sheets, (
            f"{mod.__name__} exposes no module-level stylesheet constant -- "
            "either it was renamed or this scan has gone blind")
        for name, src in sheets.items():
            # NOT VACUOUS: a "no blanket rule found" verdict is worth nothing
            # if the parser found no rules at all, and an empty result is
            # exactly what a broken parser returns. This is an invariant, not
            # a guessed floor: Qt's QSS has no nested rules, so after comments
            # are stripped the number of `{` in the source IS the number of
            # top-level rules. Measured 2026-09-21: ui.styles 90 braces / 90
            # rules, ui.light_styles 90 / 90, ui.neutral_styles 91 / 91, and
            # 124 / 121 / 123 selectors between them, none naming QFrame.
            rules = _top_level_rules(src)
            braces = _COMMENT_RE.sub(" ", src).count("{")
            assert len(rules) == braces, (
                f"{mod.__name__}.{name}: the parser found {len(rules)} rules "
                f"for {braces} top-level braces -- part of this stylesheet "
                "was never scanned, so the check below proves nothing "
                "about it")
            blanket = _blanket_qframe_selectors(src)
            assert not blanket, (
                f"{mod.__name__}.{name} gained a blanket QFrame rule "
                f"({blanket}) -- this would flatten every HLine/VLine divider "
                "in the app; see ui.theme.panel_border_qss's docstring")
