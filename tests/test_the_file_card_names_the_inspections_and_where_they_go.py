""""Where are my files?" names the 4.3.3 report files and where they go.

Knut, #182 5950106034 (2026-10-02): *"Make sure changes in report names and
save location is recorded in the help cards "Where are my files?" and any other
help card mentioning save location or file name of the reports."* The changes
were the two Inspect tools' saved files (named like the Measurement Report's,
#182 B1/B2), and the rule that outside a ChromIQ project an inspection, a
Check & Refine report and a Verify report go straight beside the measurement
(#182 5944210498).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core import i18n  # noqa: E402


@pytest.fixture(params=["en", "de"])
def card(request, monkeypatch):
    i18n.set_language(request.param)
    from ui.file_guide import file_guide_html
    try:
        yield request.param, file_guide_html()
    finally:
        i18n.set_language("en")


def test_the_inspection_files_are_named(card):
    lang, html = card
    from core.i18n import tr
    for kind in ("Measurement inspection", "Profile inspection"):
        assert f"{tr(kind)} - {{name}} - &lt;date_time&gt;.txt" in html or \
            f"{tr(kind)} - {{name}} - <date_time>.txt" in html, (lang, kind)
    assert html.count(tr("Inspect a measurement (Tools)")) >= 2
    assert html.count(tr("Inspect a profile (Tools)")) >= 2


def test_outside_a_project_is_said_for_every_tool_that_does_it(card):
    _lang, html = card
    from core.i18n import tr
    beside = tr("(beside the measurement when it is not in a ChromIQ project)")
    # Check & Refine, Verify a profile, Verify against reference
    assert html.count(beside) == 3
