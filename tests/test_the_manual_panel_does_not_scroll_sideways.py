"""Create Chart ▸ Manual must not be able to scroll sideways, in any language.

Basti reported FOUR times that the German Manual panel is cut off at the right.
The screenshot that finally settled it (2026-08-27 11:48) shows the ⓘ button
missing from every row inside the scroll area, the Messgerät combo's arrow
sliced in half and the Seiten spin box running under the vertical scrollbar.

WHY THE SISTER FILE IS NOT ENOUGH
---------------------------------
`test_the_layout_panel_fits_the_pane_in_every_language.py` measures the
`LayoutOptionsPanel` on its own against a hand-derived budget
(``540 - 26 px of nesting``). That models the chrome between the scroll content
and the panel with a constant, and the constant was 13 px optimistic: on the
build that shipped the fault the panel was 12 px over its modelled budget while
the scroll content was 25 px over the real viewport. It also cannot see any
overflow contributed by the parts of the Manual panel that are NOT that panel —
the engine tick row, the targen section, the preset override row.

So this file measures the thing the owner actually sees: the Manual scroll
area's own horizontal scroll RANGE.

THE ONE NUMBER THAT DOES NOT LIE
--------------------------------
`QAbstractScrollArea.horizontalScrollBar().maximum()`. It is the content width
minus the viewport width, and it is reported whether or not the bar is allowed
on screen. `TabChart._make_manual_panel` pins that bar `ScrollBarAlwaysOff`, so
`isVisible()` is always False and an earlier audit passed German while it was
19 px over — the content is not scrolled, it is CLIPPED, and a trackpad swipe
shoves it sideways. Ask `maximum()`, never `isVisible()`.

Measured against the real window on cocoa at dpr 2
(`.agent-reports/hscroll2-sweep.py`, all 13 languages x 4 instruments x clip
on/off x default/custom paper): 0 everywhere at this commit, and 25-34 px on
`da41d597`, the commit before the fix.

AND THE SECOND BLIND SPOT: THE APPLICATION EVENT FILTER
-------------------------------------------------------
The owner reported the same pane cut off a FIFTH time, with the layout-engine
preset row — "Auf Vorgabe zurücksetzen | Vorgabe aktualisieren | Vorgaben
bearbeiten…" — running off the right edge. This file was green while it
happened, and so were three separate probes, all for one reason:

**`main.py` installs `CompositeAppFilter`, and nothing here did.** That filter
runs `ButtonFontFilter`, which on every Polish/Show/StyleChange re-fonts each
`QPushButton` to Menlo AllUppercase and has `fit_button_width` write a
per-label ``QPushButton { min-width: Npx; }`` rule onto the button. **That rule
is the button's real layout floor**, and it is the only thing that makes a long
label cost the row anything.

Without the filter every button keeps the app stylesheet's flat
``min-width: 72px``, so the preset row's `minimumSizeHint()` is a CONSTANT
294 px in all thirteen languages and no label can ever widen the pane. With it:
German 592, Swedish 687, against a 540 px viewport. The row was on screen the
whole time — showing it changed nothing, because Qt was charging nothing for it.

So the filter is installed here, exactly as `main.py` installs it, and removed
again at teardown. `test_the_filter_that_makes_labels_cost_something_is_on`
proves it is actually doing its job, because a measurement taken without it
reports a comfortable fit for a pane that is 60 px over.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Every shipped language, English included — English has the most room and is
#: exactly why this went unseen for four reports.
_LANGS = ["en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
          "sv", "zh_CN"]

#: SpectroScan with the clip border on is the widest state the panel has: it
#: was 34 px over on the pre-fix build where the other instruments were 25.
_WORST_INSTRUMENT = "SS"

#: BOTH ENGINES. The engine panel and the printtarg parameter rows are
#: different widgets in the same pane, and only one of them is on screen at a
#: time. Polish overflowed by 1 px in the printtarg half while the engine half
#: fitted — the row that did it ("TIFF Output DPI", which also carries the
#: 8-bit / 16-bit radios) does not exist on the engine side at all.
_ENGINES = [True, False]


def _settle(qapp, area, rounds: int = 40):
    """Pump until the layout stops moving, and say how far it got.

    Qt propagates an invalidated size hint ONE level of the widget tree per
    event round, and this panel is six deep inside two collapsible frames. A
    single `processEvents()` after a change reads the OLD floor — measured:
    the panel's own minimum only moved on round 2, the scroll content's on
    round 5, and the scroll bar's range later still. Any check that asks once
    reports "fits" for a layout that does not.
    """
    last = None
    for _ in range(rounds):
        qapp.processEvents()
        now = (area.widget().minimumSizeHint().width(),
               area.widget().width(), area.horizontalScrollBar().maximum())
        if now == last:
            return now
        last = now
    return last


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _the_application_event_filter(qapp):
    """Install the filter `main.py` installs — the whole reason this file was
    blind to the preset row.

    Installed and REMOVED around every test. An application-wide event filter
    left behind would reach every widget the rest of the worker's tests create,
    which is exactly the class of cross-test leakage `tests/conftest.py` had to
    be written to stop.
    """
    from ui.widgets import CompositeAppFilter

    f = CompositeAppFilter(qapp)
    qapp.installEventFilter(f)
    try:
        yield f
    finally:
        qapp.removeEventFilter(f)
        f.setParent(None)


@pytest.fixture(autouse=True)
def _restore_the_ui_language():
    """PUT THE LANGUAGE BACK. `core.i18n` is global, and a file that switches it
    and walks away poisons every test that runs after it on the same xdist
    worker — the gate went 11 → 31 → 10 → 40 failures on four consecutive runs
    the last time it happened, a different set each time, every one passing
    alone.

    NO `importlib.reload` ANYWHERE IN THIS FILE: it swaps the class object while
    other tests still hold the old one. `TabChart` and `LayoutOptionsPanel` both
    call `tr()` in `__init__`, so setting the language and then CONSTRUCTING is
    enough.
    """
    import core.i18n as i18n

    previous = getattr(i18n, "_language", "en")
    try:
        yield
    finally:
        i18n.set_language(previous)


def _manual_scroll_area(qapp, lang, tmp_path, engine=True):
    """Create Chart ▸ Manual as the owner has it: the engine on, every section
    open, the widest instrument. Returns (tab, scroll area)."""
    import core.i18n as i18n
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QScrollArea

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.styles import APP_STYLESHEET
    from ui.widgets import CollapsibleGroupBox

    i18n.set_language(lang)
    import ui.tabs.tab_chart as tc

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / f"{lang}.ini"), QSettings.Format.IniFormat)
    tab = tc.TabChart(ArgyllRunner(s), FileManager(s), s)
    # On the WIDGET, never on the QApplication: an app-wide setStyleSheet
    # re-polishes every widget the suite has alive (two tests that took 0.2 s
    # alone once cost 29 s inside a full run). The stylesheet is worth ~35 px of
    # chrome per control, so leaving it off is what made three earlier probes
    # report a panel that fitted.
    tab.setStyleSheet(APP_STYLESHEET)
    tab.resize(1440, 1000)
    tab._switch_mode("manual")
    tab._manual_engine_check.setChecked(engine)
    tab.show()
    qapp.processEvents()

    panel = tab._manual_layout_panel
    assert panel.isVisible() == engine, (
        "the ChromIQ layout panel is not in the state this measurement asked "
        "for — Qt charges a hidden widget nothing, so the pane would be "
        "measured with a whole section missing")
    # …AND THE PRESET ROW. It is `setVisible(False)` at construction and only
    # appears with the engine on, which is precisely how it stayed unmeasured
    # through five reports. It is the widest single thing in this column.
    assert tab._manual_preset_bar.isVisible() == engine, (
        "the layout-engine preset row is not on screen — it is hidden at "
        "construction, and a hidden widget costs the layout nothing, so this "
        "measurement would not include the row that broke the pane")
    i = panel.instr.findData(_WORST_INSTRUMENT)
    if i >= 0:
        panel.instr.setCurrentIndex(i)
    ci = panel.clip_enable.findData("on")
    if ci >= 0:
        panel.clip_enable.setCurrentIndex(ci)
    qapp.processEvents()

    # EXPAND, do not "check". A `CollapsibleGroupBox` opens via
    # `set_collapsed(False)`; it is not checkable, so `setChecked(True)` is
    # silently ignored — two earlier probes measured the owner's screenshot
    # with the very section he photographed still folded.
    for _ in range(4):
        opened = False
        for grp in tab.findChildren(CollapsibleGroupBox):
            if grp.isVisible() and grp._collapsed:
                grp.set_collapsed(False)
                opened = True
        qapp.processEvents()
        if not opened:
            break
    qapp.processEvents()

    area = next(sa for sa in tab.findChildren(QScrollArea)
                if sa.isVisible() and sa.widget() is not None
                and sa.isAncestorOf(panel))
    _settle(qapp, area)
    return tab, area


@pytest.mark.parametrize("engine", _ENGINES, ids=["engine", "printtarg"])
@pytest.mark.parametrize("lang", _LANGS)
def test_the_manual_panel_never_scrolls_sideways(qapp, lang, engine, tmp_path):
    tab, area = _manual_scroll_area(qapp, lang, tmp_path, engine)
    try:
        over = area.horizontalScrollBar().maximum()
        half = "the ChromIQ layout engine" if engine else "the printtarg controls"
        assert over == 0, (
            f"{lang}, with {half} on screen: Create Chart ▸ Manual is {over} px "
            f"wider than the "
            f"{area.viewport().width()} px it is given, so its right-hand edge "
            f"— the ⓘ buttons, the instrument combo's arrow, the Pages spin box "
            f"— is CLIPPED (the horizontal bar is pinned off, so nothing shows "
            f"that it happened)")
    finally:
        tab.deleteLater()
        qapp.processEvents()


def test_this_file_can_see_the_fault_it_guards(qapp, monkeypatch, tmp_path):
    """Control — the measurement above must be able to SEE the original fault.

    It was a `QComboBox`: it computes its `minimumSizeHint()` over EVERY row in
    its model, so one sentence-long option ("Chart-Fläche priorisieren, dann
    Messfelder einpassen", 391 px) became a hard floor for the column, the
    group, and through them the whole 580 px pane. `ElidingComboBox` is what
    stops that.

    Take the override away and BUILD THE TAB AGAIN — the fault has to be
    present while the layout is first computed, exactly as it was on
    `da41d597`. Mutating a combo on a tab that is already laid out does not
    reproduce it: the widened floor does propagate (measured: the panel's own
    minimum on event round 2, the scroll content's on round 5), but a
    `QScrollArea` only re-fits its widget on a resize or layout request of its
    own, so the range stays 0 and the control would report a green that means
    nothing.
    """
    from ui.widgets import ElidingComboBox

    def plain_qcombobox_minimum(self):
        # `super()` reaches the C++ QComboBox implementation — the one that
        # measures every row in the model. Calling
        # `QComboBox.minimumSizeHint(self)` directly does not work: sip refuses
        # an unbound base method on an instance of a Python subclass that
        # reimplements it.
        return super(ElidingComboBox, self).minimumSizeHint()

    monkeypatch.setattr(ElidingComboBox, "minimumSizeHint",
                        plain_qcombobox_minimum, raising=True)
    tab, area = _manual_scroll_area(qapp, "de", tmp_path)
    try:
        over = area.horizontalScrollBar().maximum()
        assert over > 0, (
            "with ElidingComboBox's minimum taken away the German Manual panel "
            "still fits its viewport, so this file would not have caught the "
            "fault it was written for")
    finally:
        tab.deleteLater()
        qapp.processEvents()


def test_the_filter_that_makes_labels_cost_something_is_on(qapp, tmp_path):
    """Control — prove the measurement can SEE a long label at all.

    Not a proxy: the number checked is the one the packing uses. A German
    "Auf Vorgabe zurücksetzen" must arrive at the layout as a >=200 px floor.
    Without `CompositeAppFilter` it arrives as 94 px — the app stylesheet's flat
    72 px content box plus padding and border — in every language, and the whole
    file becomes an expensive way of measuring nothing.
    """
    tab, _area = _manual_scroll_area(qapp, "de", tmp_path)
    try:
        btn = tab._manual_preset_reset_btn
        assert btn.text() == "Auf Vorgabe zurücksetzen", btn.text()
        floor = btn.minimumSizeHint().width()
        assert floor >= 200, (
            f"the German 'Auf Vorgabe zurücksetzen' reaches the layout as a "
            f"{floor} px floor. ButtonFontFilter has not written its per-label "
            f"min-width rule, so no label in any language can widen this pane "
            f"and every assertion in this file is vacuous")
        assert btn.font().capitalization() == btn.font().capitalization().AllUppercase
    finally:
        tab.deleteLater()
        qapp.processEvents()


def test_this_file_can_see_the_preset_row_running_off_the_edge(qapp, monkeypatch,
                                                               tmp_path):
    """Control — the fault the owner reported five times, put back.

    The row used to be a plain `QHBoxLayout`, whose minimum is the SUM of its
    three buttons: 592 px in German against a 540 px viewport. Substitute that
    layout back and the file must fail; if it does not, the guard is decoration.

    Patched on `ui.widgets`, not on `tab_chart`: `_make_manual_panel` imports
    the name inside the function, so the module attribute is what it resolves.
    And the tab is BUILT afterwards — a `QScrollArea` only re-fits its widget on
    a resize or a layout request of its own, so mutating an already-laid-out
    pane leaves the range at 0 and would report a green that means nothing.
    """
    from PyQt6.QtWidgets import QHBoxLayout

    import ui.widgets as uiw
    monkeypatch.setattr(uiw, "WrappingButtonRow", QHBoxLayout, raising=True)
    tab, area = _manual_scroll_area(qapp, "de", tmp_path)
    try:
        over = area.horizontalScrollBar().maximum()
        assert over > 0, (
            "with the preset row back on a plain QHBoxLayout the German Manual "
            "panel still fits its viewport, so this file would not have caught "
            "the fault it was extended for")
    finally:
        tab.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("lang", _LANGS)
def test_the_preset_row_never_paints_a_label_it_cannot_fit(qapp, lang, tmp_path):
    """Every preset button gets at least the width its own label needs.

    The pane-level check above can be satisfied by a row that fits because its
    buttons were squeezed and are clipping their text — which is what the owner
    photographed. This asks the question the other way round, per button.
    """
    tab, _area = _manual_scroll_area(qapp, lang, tmp_path)
    try:
        for btn in (tab._manual_preset_reset_btn,
                    tab._manual_preset_update_btn,
                    tab._manual_preset_edit_btn):
            need = btn.minimumSizeHint().width()
            assert btn.width() >= need, (
                f"{lang}: the preset button {btn.text()!r} is {btn.width()} px "
                f"wide and its label needs {need} px, so it is painting text "
                f"that runs past its own frame")
        # …and the row itself must stay inside the column it lives in.
        bar = tab._manual_preset_bar
        assert bar.width() <= bar.parentWidget().width(), (
            f"{lang}: the preset row is {bar.width()} px inside a "
            f"{bar.parentWidget().width()} px column")
    finally:
        tab.deleteLater()
        qapp.processEvents()
