"""A label in the Layout section must be given the height it needs.

Basti photographed "Minimum patch width (mm):" with the top of its first line
cut in half. Measured on screen in a real window: the label needed 32 px and
the row gave it 22.

THE ALIGNMENT FIX CAUSED IT, AND THERE WAS ALREADY SOME. Across thirteen
languages and both calculation methods:

    before the alignment fix     5 clipped labels, combo moves up to 193 px
    the alignment fix as shipped 18 clipped labels, combo moves 0
    now                          0 clipped labels, combo moves 0

The cause was pinning the label COLUMN. These labels are right-aligned, so
each is only as wide as its own text however wide the column is: a label
narrower than the column still wrapped to two lines while the row was sized
for one. Bisected on screen, both halves separately, with the spacer removed
and with the stretch wrappers removed. Giving every label the same minimum
WIDTH keeps the controls in one place and leaves no label needing a second
line it will not get.

The cost is the panel's own minimum width, 403 px to 440 in the widest
language. The Create Chart pane gives it 504 at the app's smallest window, so
the horizontal scrollbar Basti reported twice does not come back; that is
checked in `test_the_layout_panel_fits_the_pane_in_every_language.py` and by
driving the real app.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

LANGS = ("en", "de", "fr", "es", "it", "nl", "no", "pl", "pt", "ru", "sv",
         "ja", "zh_CN")

#: What the Create Chart pane gives the panel at the app's smallest window,
#: measured by driving it. The floor must stay under this.
PANE_WIDTH = 504


@pytest.fixture(autouse=True)
def _restore_the_ui_language():
    """PUT THE LANGUAGE BACK. `core.i18n` is global, and a file that walks
    through thirteen languages and leaves the last one set poisons every test
    that runs afterwards on the same xdist worker.

    This file did exactly that on its first gate: 31 failures across eight
    files, every one of which passed on its own.
    `test_the_layout_panel_fits_the_pane_in_every_language.py` carries the same
    fixture and the same warning, which is where this was borrowed from rather
    than rediscovered.
    """
    import core.i18n as i18n

    previous = getattr(i18n, "_language", "en")
    try:
        yield
    finally:
        i18n.set_language(previous)


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    from ui.styles import WinButtonLayoutStyle
    a = QApplication.instance() or QApplication(["chromiq"])
    a.setStyle(WinButtonLayoutStyle("Fusion"))
    return a


def _panel(app, lang):
    from PyQt6.QtWidgets import QMainWindow, QScrollArea
    from core import i18n
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    i18n.set_language(lang)
    win = QMainWindow()
    panel = LayoutOptionsPanel()
    sa = QScrollArea(); sa.setWidget(panel); sa.setWidgetResizable(True)
    win.setCentralWidget(sa); win.resize(PANE_WIDTH, 900); win.show()
    app.processEvents(); app.processEvents()
    return win, panel


@pytest.mark.parametrize("lang", LANGS)
def test_no_label_in_the_layout_section_is_clipped(app, lang):
    """MUTATION: pin the label COLUMN instead of the labels and this goes red,
    in several languages at once."""
    from PyQt6.QtWidgets import QLabel
    win, panel = _panel(app, lang)
    try:
        bad = []
        for i in range(panel.area_method.count()):
            panel.area_method.setCurrentIndex(i)
            app.processEvents(); app.processEvents()
            for lab in panel.findChildren(QLabel):
                if lab.isVisible() and lab.height() < lab.sizeHint().height():
                    bad.append(f"{lab.text()[:44]!r} got {lab.height()} px, "
                               f"needs {lab.sizeHint().height()}")
        assert not bad, (
            f"[{lang}] {len(set(bad))} label(s) are given less height than "
            "their text needs, so a line is cut in half:\n  "
            + "\n  ".join(sorted(set(bad))))
    finally:
        win.close(); app.processEvents()


@pytest.mark.parametrize("lang", LANGS)
def test_the_controls_do_not_move_when_the_method_changes(app, lang):
    """Knut's requirement: changing the calculation method must move neither
    the position nor the size of the input boxes, only the labels and the
    options inside them.

    MUTATION: stop giving the labels a common minimum width and this goes red.
    """
    win, panel = _panel(app, lang)
    try:
        xs, ws = [], []
        for i in range(panel.area_method.count()):
            panel.area_method.setCurrentIndex(i)
            app.processEvents(); app.processEvents()
            c = panel.area_method
            xs.append(c.mapTo(panel, c.rect().topLeft()).x())
            ws.append(c.width())
        assert max(xs) - min(xs) == 0, (
            f"[{lang}] the calculation-method box moves {max(xs) - min(xs)} px")
        assert max(ws) - min(ws) == 0, (
            f"[{lang}] it changes width by {max(ws) - min(ws)} px, which is "
            "what made it read 'By colum…'")
    finally:
        win.close(); app.processEvents()


@pytest.mark.parametrize("lang", LANGS)
def test_the_panel_still_fits_the_pane_it_is_given(app, lang):
    """The label widths are bought with the panel's minimum width, so that
    number has to stay under what the pane actually offers."""
    win, panel = _panel(app, lang)
    try:
        floor = panel.minimumSizeHint().width()
        assert floor <= PANE_WIDTH, (
            f"[{lang}] the panel now needs {floor} px and the Create Chart "
            f"pane gives {PANE_WIDTH} at the app's smallest window, so the "
            "horizontal scrollbar is back")
    finally:
        win.close(); app.processEvents()
