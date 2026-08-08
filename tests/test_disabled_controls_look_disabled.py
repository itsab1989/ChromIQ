"""A switched-off control has to *look* switched off.

Basti, 2026-08-08, reviewing a mockup: *"the mockup screenshot does not really
show that 'through this runs profile' option is not available (it is not greyed,
looks selectable although the info says the opposite)"*.

He was right, and it was not the mockup. Measured on the dark theme, an enabled
radio label and a disabled one both rendered **#e6e6e6 — pixel for pixel
identical**, while a checkbox in the same state rendered #6a6a6a. The stylesheet
carried `QCheckBox:disabled` but never the radio equivalent; only radios with
`objectName="param_label"` were covered.

That matters beyond tidiness. The plan for verification printing
(`docs/design/verification_printing_and_target.md` §3.1a) requires an option to
be **disabled rather than merely deselected**, because choosing it would convert
a chart's colours twice — an error nothing downstream can detect. A disabled
control that looks live cannot carry that design.

These tests measure rendered pixels rather than reading the stylesheet, because
the stylesheet said the right thing about checkboxes for years while radios went
uncovered, and no test noticed.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QCheckBox, QRadioButton, QVBoxLayout, QWidget

from ui import styles

#: How much darker a disabled label must be than an enabled one. The real
#: values are 230 vs 106 on the dark theme, so 60 is a wide margin that still
#: fails loudly if the rule is dropped.
MIN_LIGHTNESS_DROP = 60


def _brightest(img, widget):
    """The label's text colour: the brightest pixel right of the indicator."""
    r = widget.geometry()
    best = None
    for y in range(r.top() + 2, r.bottom() - 2):
        for x in range(r.left() + 22, r.right() - 2):
            c = img.pixelColor(x, y)
            if best is None or c.lightness() > best.lightness():
                best = c
    return best


@pytest.fixture
def rendered(qapp):
    """Enabled/disabled × checked/unchecked, drawn with the real stylesheet.

    ⚠️ The stylesheet goes on **this widget**, never on the application.
    ``qapp.setStyleSheet()`` re-polishes every widget the suite has alive: the
    first version of this file did that and turned a 3¾-minute gate into one
    that had not finished in ten. CLAUDE.md warns about it in as many words —
    *"Style the widget under test instead; it measures the same thing"* — and
    it does: a stylesheet set on the parent cascades to these children, so the
    pixels are identical.
    """
    w = QWidget()
    w.setStyleSheet(styles.APP_STYLESHEET)
    lay = QVBoxLayout(w)
    made = {}
    for cls, name in ((QRadioButton, "radio"), (QCheckBox, "check")):
        for on in (True, False):
            for checked in (False, True):
                c = cls(f"{name} sample text", w)
                c.setEnabled(on)
                c.setChecked(checked)
                lay.addWidget(c)
                made[(name, on, checked)] = c
    w.adjustSize()
    w.show()
    for _ in range(5):
        qapp.processEvents()
    img = w.grab().toImage()
    yield img, made
    w.close()


@pytest.mark.parametrize("kind", ["radio", "check"])
@pytest.mark.parametrize("checked", [False, True])
def test_a_disabled_label_is_visibly_dimmer(rendered, kind, checked):
    img, made = rendered
    on = _brightest(img, made[(kind, True, checked)])
    off = _brightest(img, made[(kind, False, checked)])
    drop = on.lightness() - off.lightness()
    assert drop >= MIN_LIGHTNESS_DROP, (
        f"a disabled {kind} ({'checked' if checked else 'unchecked'}) renders "
        f"{off.name()} against {on.name()} enabled — a difference of {drop}. "
        "It has to read as switched off; see §3.1a of the verification-printing "
        "plan, which relies on a disabled option being recognisable as one.")


@pytest.mark.parametrize("kind", ["radio", "check"])
def test_the_accent_does_not_survive_being_disabled(rendered, kind):
    """A checked-and-disabled control must not keep a bright accent dot.

    The `:checked` fill outranks Qt's own disabled greying, so this needs its
    own selector — the checkbox rules already say so in a comment, and the
    radio ones now do too.
    """
    img, made = rendered
    off_checked = _brightest(img, made[(kind, False, True)])
    on_checked = _brightest(img, made[(kind, True, True)])
    assert off_checked.lightness() < on_checked.lightness(), (
        f"a disabled, checked {kind} is as bright as a live one")


def test_the_stylesheet_covers_radios_and_checkboxes_alike():
    """The gap was that one had the rules and the other did not.

    A structural check as well as the pixel ones above, so the *reason* is
    recorded where someone editing the stylesheet will meet it.
    """
    qss = styles.APP_STYLESHEET
    for selector in ("QRadioButton:disabled",
                     "QRadioButton::indicator:disabled",
                     "QCheckBox:disabled",
                     "QCheckBox::indicator:disabled"):
        assert selector in qss, f"{selector} is missing from the app stylesheet"
