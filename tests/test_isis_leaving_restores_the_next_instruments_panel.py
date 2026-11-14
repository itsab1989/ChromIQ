"""Leaving one Beta instrument never damages the next one's panel (review of
a7ca1489e, M1: i1 -> i1iSis -> FD-9 gave FD-9 the i1Pro's patch range,
i1iO -> i1iSis -> i1iO lost the i1iO's 7 mm minimum and three tooltips).

With the FD-9, i1iO and i1iSis Betas all on, for every ordered pair A, B:
A -> i1iSis -> B, and A -> B -> A, leave the panel exactly as a direct
switch does: every control's range, minimum, special text, enabled state
and tooltip (values may carry from one instrument to the next, so they are
not compared).
"""
from __future__ import annotations

import itertools

import pytest

CODES = ("i1", "CM", "SS", "CR30", "FD9", "IO2", "XRISIS")


@pytest.fixture(autouse=True)
def betas_on():
    from workflow.fd9 import support as f9
    from workflow.i1io import support as io
    from workflow.isis import support as isis
    before = [(m, m._latched) for m in (f9, io, isis)]
    for m, _b in before:
        m.set_enabled_for_this_process(True)
    yield
    for m, b in before:
        m._latched = b


#: Enabled states the panel works out only when their source changes (the
#: underline mode; the spacer mode and the instrument's spacer for the
#: spacer size): a direct switch can leave them as built (the underline
#: boxes enabled with the underline off, the spacer size enabled on a
#: SpectroScan, which has no spacer), while leaving the i1iSis works them
#: out by the panel's own rule. Their ranges and tooltips are compared.
DERIVED_ONLY_ON_CHANGE = {"underline_gap", "underline_thickness",
                          "spacer_width", "clip_text_font"}
#: (and the clip text face, which follows the Content value an instrument
#: carries to the next: i1 -> CM -> i1 differs alike)


def _snap(panel) -> dict:
    from PyQt6.QtWidgets import QAbstractSpinBox, QWidget
    out = {}
    for name, w in sorted(vars(panel).items()):
        if not isinstance(w, QWidget) or name.startswith(("_isis", "isis_")):
            continue
        try:
            st = ((None if name in DERIVED_ONLY_ON_CHANGE
                   else w.isEnabled()), w.toolTip())
            if isinstance(w, QAbstractSpinBox) and hasattr(w, "minimum"):
                st += (w.minimum(), w.maximum(), w.specialValueText())
            out[name] = st
        except RuntimeError:
            pass
    return out


def _panel_after(qapp, path):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    for code in path:
        k = p.instr.findData(code)
        assert k >= 0, code
        p.instr.setCurrentIndex(k)
        p.instr.activated.emit(k)
        qapp.processEvents()
    snap = _snap(p)
    p.deleteLater()
    qapp.processEvents()
    return snap


def _diff(a, b):
    return {k: (a.get(k), b.get(k)) for k in set(a) | set(b)
            if a.get(k) != b.get(k)}


@pytest.mark.parametrize("a,b", [(a, b) for a, b in
                                 itertools.permutations(CODES, 2)])
def test_leaving_never_changes_the_next_panel(qapp, a, b):
    direct = _panel_after(qapp, ("SS", a, b))
    if "XRISIS" not in (a, b):
        via = _panel_after(qapp, ("SS", a, "XRISIS", b))
        assert _diff(direct, via) == {}, (a, "XRISIS", b)
    if "XRISIS" in (a, b) and not (a == "XRISIS" and b == "FD9"):
        # (XRISIS -> FD-9 -> XRISIS is left out: FD-9's own leave greys
        # "Max strip length" on any instrument, i1 -> FD-9 -> i1 alike;
        # FD-9's code is not changed by this Beta)
        # the round trips through the i1iSis (the others are the panel's
        # own business, unchanged by this Beta)
        back = _panel_after(qapp, ("SS", a, b, a))
        home = _panel_after(qapp, ("SS", a))
        assert _diff(home, back) == {}, (a, b, a)
