"""The Neutral appearance in the configurations and states nothing had rendered.

WHY THIS FILE EXISTS. Five sweeps measured Neutral with
``scripts/find_non_neutral_pixels.py`` against a freshly-opened app in its
default configuration, and the last reported zero hued pixels app-wide. The
owner then found six things it had never drawn, in under an hour, just by using
the app. Driving the same app into three configurations and one busy state
found 4,695,243 hued pixels.

TWO BLIND SPOTS, AND THE SECOND IS THE LARGER:

1. A hidden widget has no pixels. Everything behind a setting, a run type, a
   busy state or a failure was never in the sample.
2. **The pixel census can only see a HUE, never a wrong LIGHTNESS.** ``#2a2a2a``
   and ``#d8d8d8`` are perfect greys, chroma 0, so a near-black slab on the
   light-grey ground and text at 1.10:1 both score exactly zero. No amount of
   re-running that census would have found them.

Both come from one shape: ``X if mode == "light" else Y`` has room for two
answers, so the third appearance is filed under DARK. ``ui.theme.by_mode`` is
the shape with room for three.

**LIGHT AND DARK MAY NOT MOVE.** Every assertion below that names a Light or a
Dark value is checking exactly that.
"""
from __future__ import annotations

import inspect

from PyQt6.QtGui import QColor

from ui import neutral_styles as N
from ui.theme import APPEARANCE_DARK, APPEARANCE_LIGHT, APPEARANCE_NEUTRAL


def _code_only(src: str) -> str:
    """The source with its comments stripped.

    A test that greps for a fold shape has to read CODE, not prose: every fix in
    this sweep carries a comment quoting the fold it replaced, and a naive
    ``'!= "light"' not in src`` then fails on the explanation of why it is gone.
    """
    out = []
    for line in src.split("\n"):
        stripped = line.split("#", 1)[0] if line.lstrip().startswith("#") else line
        out.append(stripped)
    return "\n".join(out)


def _in_appearance(mode: str) -> None:
    """Put the named appearance's PALETTE on the application.

    A widget that resolves its colour at paint time asks ``ui.theme`` which
    appearance is on, and ``active_mode`` identifies the live palette — so a
    behavioural test has to paint the palette, not just name the mode. Only the
    palette is set: ``setStyleSheet`` re-polishes every widget the suite has
    alive and is banned in tests for that reason.
    """
    from PyQt6.QtWidgets import QApplication
    from ui.theme import _APPEARANCE_STYLE
    app = QApplication.instance()
    _stylesheet, make_palette = _APPEARANCE_STYLE[mode]
    app.setPalette(make_palette())


def chroma(hexc: str) -> int:
    c = QColor(hexc)
    return max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue())


def _lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexc: str) -> float:
    c = QColor(hexc)
    return 0.2126 * _lin(c.red()) + 0.7152 * _lin(c.green()) + 0.0722 * _lin(c.blue())


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ======================================================================
# info_box_qss — the titled box, three times over
# ======================================================================

def test_info_box_hands_light_and_dark_exactly_what_they_asked_for():
    """The AirPrint box, the IMPORT box and the calibration card are one shape,
    and all three folded. Light and Dark must get their four values back."""
    from ui.widgets import info_box_qss
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        qss = info_box_qss("airprint", bg="#2a2000", border="#f9a825",
                           title="#fdd835", body="#e0d5b0", mode=mode,
                           kind="warn")
        assert "background-color: #2a2000" in qss
        assert "border: 1px solid #f9a825" in qss
        assert "color: #fdd835" in qss
        assert "color: #e0d5b0" in qss
        # …and no Neutral value has leaked in.
        assert N.NM_BG_SURFACE not in qss


def test_info_box_has_no_hue_in_neutral():
    from ui.widgets import info_box_qss
    qss = info_box_qss("import", bg="#0b1f18", border="#56d6a5",
                       title="#56d6a5", body="#cfe9dd",
                       mode=APPEARANCE_NEUTRAL, kind="note")
    for hue in ("#0b1f18", "#56d6a5", "#cfe9dd"):
        assert hue not in qss, f"{hue} survived into Neutral"
    assert N.NM_BG_SURFACE in qss
    assert N.NM_TEXT_MAIN in qss


def test_info_box_says_warning_the_way_the_rest_of_the_app_does():
    """ONE VOCABULARY. `banner_qss` already spends the handoff's escalation —
    a 2px ACTION underline for a warning, a 3px left bar for a failure. With
    the amber gone, that mark is the only thing left saying "this is a
    warning" rather than "this is a panel", so the three surfaces that carry a
    warning in Neutral must all carry the same one."""
    from ui.widgets import banner_qss, info_box_qss
    warn = info_box_qss("airprint", bg="#2a2000", border="#f9a825",
                        title="#fdd835", body="#e0d5b0",
                        mode=APPEARANCE_NEUTRAL, kind="warn")
    note = info_box_qss("import", bg="#0b1f18", border="#56d6a5",
                        title="#56d6a5", body="#cfe9dd",
                        mode=APPEARANCE_NEUTRAL, kind="note")
    err = info_box_qss("x", bg="#000", border="#000", title="#000", body="#000",
                       mode=APPEARANCE_NEUTRAL, kind="error")
    assert f"border-bottom: 2px solid {N.NM_ACTION}" in warn
    assert f"border-left: 3px solid {N.NM_ACTION}" in err
    assert "border-bottom: 2px" not in note and "border-left: 3px" not in note
    # the same two marks the one-line banner already uses
    banner_warn = banner_qss("#fdd835", "#2a2000", mode=APPEARANCE_NEUTRAL,
                             kind="warn")
    banner_err = banner_qss("#ff4573", "rgba(0,0,0,0)", mode=APPEARANCE_NEUTRAL,
                            kind="error")
    assert f"border-bottom: 2px solid {N.NM_ACTION}" in banner_warn
    assert f"border-left: 3px solid {N.NM_ACTION}" in banner_err


def test_the_two_config_gated_boxes_go_through_that_door():
    """The AirPrint box needs the ``lp`` pipeline AND a driverless printer; the
    IMPORT box needs Run type = Verification (#133 §9.1). Neither had ever been
    drawn, and both wrote their QSS by hand."""
    from ui.tabs.tab_measure import TabMeasure
    from ui.tabs.tab_print import TabPrint
    assert "info_box_qss" in inspect.getsource(
        TabPrint._apply_airprint_box_styles)
    assert "info_box_qss" in inspect.getsource(
        TabMeasure._apply_import_box_style)


# ======================================================================
# The measurement progress bar — the owner's own guess, and he was right
# ======================================================================

def test_progress_bar_fill_follows_the_appearance():
    """*"in this case maybe the progress bar in measure tab is missed as well"*
    — it was. The fill only ever has a fraction while a chart is being
    measured, so no census had rendered it.

    ASKED OF THE WIDGET, NOT OF ITS SOURCE. The first version of this grepped
    ``_fill_colour`` for the word "accent_for" and stayed green when the call
    was deleted, because the DOCSTRING still said it — a guard that reads prose
    guards prose. The mutation run caught that; this asks the widget.
    """
    from ui.styles import SPEC_GREEN
    from ui.tiff_preview import _ProgressHeader
    hdr = _ProgressHeader()
    try:
        for mode, want in ((APPEARANCE_LIGHT, SPEC_GREEN),
                           (APPEARANCE_DARK, SPEC_GREEN),
                           (APPEARANCE_NEUTRAL, N.NM_ACTION)):
            _in_appearance(mode)
            got = hdr._fill_colour().name()
            assert got == want, f"{mode}: {got}"
        assert chroma(N.NM_ACTION) == 0
    finally:
        _in_appearance(APPEARANCE_DARK)
    # Resolved at PAINT time, not stored: the header outlives an appearance
    # switch made from Preferences while a measurement is running.
    assert "_fill_colour()" in inspect.getsource(_ProgressHeader.paintEvent)


# ======================================================================
# The lightness blind spot — greys the hue census cannot see
# ======================================================================

def test_disabled_stop_button_is_not_a_dark_slab_in_neutral():
    """The DEFAULT state of the Measure tab: Stop is disabled until a
    measurement runs. It painted `#2a2a2a` on `#e2e2e2` — 16,493 px of
    near-black on light grey — and the hue census scored it zero, because
    `#2a2a2a` is a perfect grey."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._apply_stop_btn_style)
    assert "APPEARANCE_NEUTRAL" in src
    assert "NM_DISABLED" in src
    # Light and Dark keep their four values.
    for v in ("#eeeae5", "#a8a4a0", "#ccc9c3", "#2a2a2a", "#555555", "#333333"):
        assert v in src
    # And the dark slab is inside the non-Neutral branch, not before it.
    neutral_at = src.index("APPEARANCE_NEUTRAL")
    assert src.index('"#2a2a2a"') > neutral_at


def test_margin_values_are_readable_in_neutral():
    """`#d8d8d8` on `#e2e2e2` is 1.10:1 — not faint, unreadable — and chroma 0,
    so invisible to the hue census. The table is also empty until a preview
    exists, so nothing had rendered it either."""
    assert contrast("#d8d8d8", N.NM_BG_PANEL) < 1.2      # what it was
    assert contrast(N.NM_TEXT_MAIN, N.NM_BG_PANEL) > 12  # what it is
    from ui.margin_inspector_panel import MarginInspectorPanel
    src = inspect.getsource(MarginInspectorPanel.update_report)
    assert "by_mode" in src and "set_ink" in src
    # The violated edge is still flagged — by weight, which was always there.
    assert '"600" if bad else "400"' in src


def test_tools_dialog_detail_text_is_readable_in_neutral():
    """Both info dialogs returned the DARK theme's near-white ink for Neutral:
    `#e6e6e6` on `#e2e2e2` is 1.02:1. Two perfect greys, so zero hued pixels."""
    from ui.dialogs.profile_info_dialog import ProfileInfoDialog
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    assert contrast("#e6e6e6", N.NM_BG_PANEL) < 1.1
    for cls in (ProfileInfoDialog, Ti3InfoDialog):
        src = inspect.getsource(cls._resolve_text_colors)
        assert "by_mode" in src, f"{cls.__name__} still folds two answers"
        assert "NM_TEXT_MAIN" in src


def test_scanner_hint_lines_are_readable_in_neutral():
    """`#b8b8b8` is 1.53:1 on the Neutral dialog."""
    import ui.dialogs.scanin_dialog as sd
    import ui.dialogs.scanin_target_dialog as std
    assert contrast("#b8b8b8", N.NM_BG_PANEL) < 1.6
    for mod in (sd, std):
        src = _code_only(inspect.getsource(mod))
        one_line = " ".join(src.split())
        assert 'by_mode( "#4a4a4a", "#b8b8b8", _n.NM_TEXT_FAINT' in one_line \
            or 'by_mode("#4a4a4a", "#b8b8b8", _n.NM_TEXT_FAINT' in one_line, \
            f"{mod.__name__} still folds two answers for its hint colour"


# ======================================================================
# The states that only exist while something happens
# ======================================================================

def test_strip_time_verdict_keeps_its_severity_without_the_hue():
    """CASE 2, not case 1. Red / amber / green was saying the severity at a
    glance while you swipe an instrument. In Neutral the WEIGHT says it —
    bold when the strip must be read again — and Light and Dark keep all three
    hues and their normal weight."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._refresh_pace_panel)
    assert "set_ink" in src
    assert 'font-weight: 700' in src
    assert 'APPEARANCE_NEUTRAL' in src
    assert '"#ff6b6b", "#e0a63a"' in src        # which two mean "act"


def test_strip_times_are_not_mistaken_for_disabled_in_neutral():
    """`#909090` is 2.53:1 on the panel, and in this theme low contrast means
    "disabled" and nothing else (rule 3). A time being written under a strip
    as you swipe it is the opposite of disabled."""
    from ui.strip_times_panel import StripTimesPanel
    assert contrast("#909090", N.NM_BG_PANEL) < 3.0
    assert contrast(N.NM_TEXT_DIM, N.NM_BG_PANEL) > 8.0
    # ASKED OF THE PANEL. Grepping `_muted_ink` for "ink_for" stayed green with
    # the call deleted, because the docstring says it too.
    panel = StripTimesPanel()
    try:
        for mode, want in ((APPEARANCE_LIGHT, "#909090"),
                           (APPEARANCE_DARK, "#909090"),
                           (APPEARANCE_NEUTRAL, N.NM_TEXT_DIM)):
            _in_appearance(mode)
            assert panel._muted_ink() == want, f"{mode}: {panel._muted_ink()}"
    finally:
        _in_appearance(APPEARANCE_DARK)
        panel.deleteLater()
    # Asked at PAINT time, so the panel follows a theme switched under it.
    assert "_muted_ink()" in inspect.getsource(StripTimesPanel.paintEvent)


def test_validation_error_lines_go_through_the_ink_door():
    """Empty until the typed name is refused — the same shape as the owner's
    "this project already exists" line, which no census had drawn either."""
    import ui.ti2_loader as ti2
    import ui.txt_loader as txt
    for mod in (ti2, txt):
        src = inspect.getsource(mod)
        assert 'set_ink(err' in src or 'set_ink(error_lbl' in src
        assert 'setStyleSheet("color: #e05555;")' not in src
        assert 'setStyleSheet("color:#e05555;")' not in src


def test_the_argyll_warning_bar_carries_the_escalation_mark():
    """Only reachable on a machine where ArgyllCMS is missing, which is why a
    healthy install never renders it. With the amber gone the box alone reads
    as an ordinary panel, so it takes the same mark every other warning
    surface in this theme takes."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._set_tab_status)
    assert "by_mode" in src
    assert f"border-bottom: 2px solid {{_nm.NM_ACTION}}" in src
    assert "font-weight: 700" in src
    # Light and Dark keep the exact slab they had.
    assert "background: #3a2a00; color: #ffb42d; " in src
    assert "border: 1px solid #ffb42d; " in src


# ======================================================================
# A live appearance switch must reach what was already on screen
# ======================================================================

def test_the_margin_panel_remembers_the_report_it_was_given():
    """The replay needs something to replay. (The switch itself is proved by
    driving the widgets — see ``test_the_margin_panel_really_repaints_its_values``,
    which is the guard that goes red when the replay is removed.)"""
    from ui.margin_inspector_panel import MarginInspectorPanel
    assert "_last_report" in inspect.getsource(
        MarginInspectorPanel.update_report)


def test_the_margin_panel_really_repaints_its_values(qapp):
    """Not a grep — the widgets themselves. Build the panel, give it numbers in
    Light, switch it to Neutral, and read the stylesheet the labels are wearing.

    A source check can only say the call is there. This says the ink moved, and
    that it moved to a value you can actually read on the Neutral ground."""
    from workflow.margin_inspector import MarginReport
    from ui.margin_inspector_panel import MarginInspectorPanel

    panel = MarginInspectorPanel()
    panel.set_appearance(APPEARANCE_LIGHT)
    report = MarginReport(left_mm=10.0, right_mm=10.0, top_mm=24.0,
                          bottom_mm=11.0, strip_width_mm=8.0,
                          page_w_mm=210.0, page_h_mm=297.0)
    panel.update_report(report, [], thresholds_defined=False, notify=True)
    mm_lbl = panel._value_labels["L"][0]
    light_ss = mm_lbl.styleSheet()
    assert "#1c1b18" in light_ss, light_ss

    panel.set_appearance(APPEARANCE_NEUTRAL)
    neutral_ss = mm_lbl.styleSheet()
    assert neutral_ss != light_ss, "the switch never reached the value labels"
    assert N.NM_TEXT_MAIN in neutral_ss, neutral_ss
    # …and the dark theme's near-invisible grey is nowhere near it.
    assert "#d8d8d8" not in neutral_ss
    panel.deleteLater()


def test_the_drag_over_line_is_the_one_accent_in_neutral():
    """The patch editor's drop indicator exists for the length of a drag and no
    longer. No census renders it, and none in this environment could — a
    `:hover` rule cannot be made to paint here, let alone a drag — so it was
    found by reading the source instead."""
    from ui.dialogs.ti2_relayout_dialog import _ReorderListWidget
    src = inspect.getsource(_ReorderListWidget.paintEvent)
    assert "accent_for(SPEC_MAGENTA)" in src
    from ui.theme import accent_for
    from ui.styles import SPEC_MAGENTA
    assert accent_for(SPEC_MAGENTA, APPEARANCE_LIGHT) == SPEC_MAGENTA
    assert accent_for(SPEC_MAGENTA, APPEARANCE_DARK) == SPEC_MAGENTA
    assert chroma(accent_for(SPEC_MAGENTA, APPEARANCE_NEUTRAL)) == 0


def test_appearance_switch_reaches_a_status_line_already_up():
    """The one message that matters here is on screen exactly while the user is
    in Preferences fixing the ArgyllCMS path — the one place they can also
    change the theme."""
    from ui.main_window import MainWindow
    assert "_set_tab_status" in inspect.getsource(MainWindow.apply_theme)


# ======================================================================
# The fold itself: no site fixed here may quietly grow one back
# ======================================================================

def test_the_sites_fixed_here_no_longer_fold_two_answers():
    """``X if mode == "light" else Y`` is the shape that produced almost every
    finding in this sweep. Each site below now answers three appearances."""
    import ui.dialogs.drift_plot_dialog as drift
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.tabs.tab_measure import TabMeasure

    # the 3D difference map's page, which opened near-black from a light window
    assert 'by_mode(_BG_LIGHT, _BG_DARK' in inspect.getsource(drift)
    # the report's trend charts, told they sat on a dark ground
    src = _code_only(inspect.getsource(MeasurementReportDialog))
    assert 'has_dark_ground(' in src
    assert '!= "light"' not in src
    # the calibration-finished card and the #134 overlay prompt
    for fn in (TabMeasure._on_calibration_done,):
        s = inspect.getsource(fn)
        assert "APPEARANCE_NEUTRAL" in s
        assert "accent_for" in s


def test_scanner_target_card_answers_the_third_appearance():
    """Its own docstring used to end "a third appearance needs a third hint
    colour here", and none had been supplied — because the card is only built
    at the end of a real measurement of a chart that carries scanner geometry.
    """
    from ui.tabs.tab_measure import make_scanner_target_row
    from PyQt6.QtWidgets import QLabel, QWidget
    parent = QWidget()
    try:
        # ASKED OF THE CARD. Grepping the function for "accent_for" stayed
        # green with the call deleted, because the IMPORT line still named it.
        for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK, APPEARANCE_NEUTRAL):
            _in_appearance(mode)
            row, _cb = make_scanner_target_row(parent, False)
            qss = row.styleSheet()
            hint = [w for w in row.findChildren(QLabel) if w.styleSheet()]
            hint_qss = hint[-1].styleSheet() if hint else ""
            if mode == APPEARANCE_NEUTRAL:
                assert "86,214,165" not in qss, qss   # the green, as rgb()
                assert "#56d6a5" not in qss
                assert N.NM_TEXT_DIM in hint_qss, hint_qss
            else:
                assert "#56d6a5" in qss, f"{mode}: {qss}"
                assert ("#a6e3ca" if mode == APPEARANCE_DARK
                        else "#2f6b52") in hint_qss, f"{mode}: {hint_qss}"
    finally:
        _in_appearance(APPEARANCE_DARK)
        parent.deleteLater()
