"""THE "OPEN CHART FILE" TOOLTIP IS TRUE OF ANY CHART FILE (4.3.47).

It said "This is the laid-out chart ChromIQ made for you", but the button
opens any .ti2: one ArgyllCMS's printtarg wrote, one from another program, one
copied from another computer. Now it says what a chart file is, that it can
come from ChromIQ or elsewhere, and that a file from outside the projects is
copied into one after ChromIQ asks.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_the_tooltip_no_longer_says_every_chart_is_chromiqs(qapp):
    from ui.masthead_header import MastheadHeader
    m = MastheadHeader()
    tip = m._load_ti2_btn.toolTip()
    assert tip.startswith("Open Chart File (.ti2)")
    assert "This is the laid-out chart ChromIQ made for you" not in tip
    assert "ArgyllCMS or another program" in tip
    assert "copied into a project" in tip
    assert "Unavailable while a measurement is running." in tip
    assert "—" not in tip
    m.deleteLater()
