"""Create Chart ▸ Manual must not scroll sideways — in any of the languages.

Basti, 2026-08-27, twice, the second time to say it had been reported and not
fixed: in GERMAN the Manual panel scrolls sideways, and in English it does not.

Measured on the real screen with every section open, the scroll content needed
559 px of a 540 px viewport in German — and 494 in English, which is why nobody
saw it in English. Nine of the thirteen languages overflowed: Italian 611,
Portuguese 609, Russian 600, Portuguese/Spanish/Swedish/Norwegian/Polish/French
in between.

WHY THREE EARLIER AUDITS SAID IT WAS FINE
-----------------------------------------
1. The first compared ``sizeHint()`` — what a widget would LIKE — and reported
   English as the worst case, which the owner disproved by looking at the app.
2. The second asked ``horizontalScrollBar().isVisible()``. That bar is pinned
   off (``ScrollBarAlwaysOff`` in ``TabChart._make_manual_panel``), so it is
   never visible and the answer is always "clean": the content is CLIPPED
   instead, and shoved sideways by a trackpad swipe.
3. Both were blamed on "offscreen metrics are not his metrics". They are.
   With the app's own stylesheet applied — which is the part that was missing —
   an offscreen run reproduces the on-screen floor to within 3 px in every
   language (measured against `.agent-reports/hscroll-probe3.py`, which drives
   the real window on cocoa).

So this test measures the one number that decides it: the **minimum** width the
panel cannot go below, against the width the pane gives it.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Every shipped language, English included.
_LANGS = ["en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
          "sv", "zh_CN"]

#: What the panel actually gets, measured on screen (cocoa, 1440x900,
#: `.agent-reports/hscroll-probe3.py`): the Manual scroll area's viewport is
#: 540 px — the left pane is locked at 580 (see the comment at
#: `ui/tabs/tab_chart.py`), less its 16 px side margins and the vertical
#: scrollbar — and 26 px of that goes on the nesting between the scroll content
#: and this panel (4+4 content margins, the "ChromIQ layout" group's frame, and
#: its 8+8 body margins). Re-measure with that script if either changes.
_VIEWPORT = 540
_NESTING_CHROME = 26
_BUDGET = _VIEWPORT - _NESTING_CHROME          # 514

#: As shipped after the fix the worst language (Norwegian) sits at 452, so this
#: is not a knife-edge assertion — there are ~60 px of room for a longer string
#: before it trips.


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _restore_the_ui_language():
    """PUT THE LANGUAGE BACK. `core.i18n` is global, and a test file that
    switches it and walks away poisons every test that runs afterwards on the
    same xdist worker — the gate went 11 → 31 → 10 → 40 failures on four
    consecutive runs the last time it happened, a different set each time.

    NO `importlib.reload` ANYWHERE IN THIS FILE either: it swaps the class
    object while other tests still hold the old one. `LayoutOptionsPanel` calls
    `tr()` in `__init__`, so setting the language and then CONSTRUCTING is
    enough.
    """
    import core.i18n as i18n

    previous = getattr(i18n, "_language", "en")
    try:
        yield
    finally:
        i18n.set_language(previous)


def _panel(qapp, lang):
    """The panel as Create Chart ▸ Manual builds it, in *lang*.

    The app's stylesheet is put on the PANEL, not on the QApplication: an
    app-wide `setStyleSheet` re-polishes every widget the suite has alive (two
    tests that took 0.2 s alone once cost 29 s inside a full run). Verified to
    measure the same thing — panel-scoped and app-wide give identical floors in
    all thirteen languages.
    """
    import core.i18n as i18n
    from ui.styles import APP_STYLESHEET
    import ui.dialogs.layout_options_panel as lop

    i18n.set_language(lang)
    panel = lop.LayoutOptionsPanel(with_selectors=True, with_calibration=True)
    panel.setStyleSheet(APP_STYLESHEET)
    # The owner's screenshot is of the Expert section, and a user can open both.
    panel._basic_frame.set_collapsed(False)
    panel._expert_frame.set_collapsed(False)
    panel.resize(_BUDGET, 3000)
    panel.show()
    qapp.processEvents()
    return panel


@pytest.mark.parametrize("lang", _LANGS)
def test_the_engine_panel_fits_the_pane_it_is_given(qapp, lang):
    panel = _panel(qapp, lang)
    try:
        floor = panel.minimumSizeHint().width()
        assert floor <= _BUDGET, (
            f"{lang}: the ChromIQ-layout panel cannot go below {floor} px and "
            f"the pane gives it {_BUDGET} — Create Chart ▸ Manual scrolls "
            f"sideways by {floor - _BUDGET} px in this language"
        )
    finally:
        panel.hide()
        panel.deleteLater()
        qapp.processEvents()


def test_a_sentence_in_a_combo_would_still_be_caught(qapp):
    """Control — the measurement above must be able to SEE the original fault.

    The fault was a `QComboBox`: it computes both `sizeHint()` **and**
    `minimumSizeHint()` over every row in its model, so one sentence-long option
    ("Chart-Fläche priorisieren, dann Messfelder einpassen", 391 px) became a
    hard floor for the column, the group and the whole pane. `ElidingComboBox`
    is what stops that.

    Put the plain `QComboBox` minimum back on that one combo, in German, and the
    panel must go over budget again. The mutation is asserted to LAND — a
    control that silently fails to change anything proves nothing.
    """
    from PyQt6.QtWidgets import QComboBox

    panel = _panel(qapp, "de")
    try:
        before = panel.minimumSizeHint().width()
        assert before <= _BUDGET, (
            "as shipped the German panel is already over budget — the "
            "parametrised assertions above have nothing to prove")

        combo = panel.layout_mode
        unelided = QComboBox.minimumSizeHint(combo).width()
        assert unelided > combo.minimumSizeHint().width(), (
            "ElidingComboBox is not actually reporting a smaller minimum than "
            "a plain QComboBox would, so this control changes nothing")
        combo.setMinimumWidth(unelided)
        panel.updateGeometry()
        qapp.processEvents()

        after = panel.minimumSizeHint().width()
        assert after > before, (
            f"the mutation did not land: the floor stayed at {after} px")
        assert after > _BUDGET, (
            f"giving one combo its full {unelided} px back only took the panel "
            f"to {after} px, still inside the {_BUDGET} px pane — this file "
            f"would not have caught the fault it was written for")
    finally:
        panel.hide()
        panel.deleteLater()
        qapp.processEvents()
