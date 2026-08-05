"""-T is on by default at 0.7, and its help text says why that is useful.

beta.140 switched this off, reading a high misread count in Knut's logs as
evidence that the option was making strips fail. **That reading was wrong** —
Knut, beta.140: *"previous measurements that you refer to as part of your
diagnosis (misreads vs strips read OK) for the past betas is completely wrong to
make judgements by, as this was testing where I deliberately failed readings to
provoke messages to appear for bug-fixing."* He asked for the default back.

He is also right about what the option is for. ``-T`` multiplies the
instrument's patch consistency threshold — how far the many readings taken
across ONE patch may disagree before the strip is rejected
(``(maxavg - minavg)/norm > PATCH_CONS_THR``, i1pro_imp.c:6596; the constant is
0.1 on the i1Pro and 0.05 on the ColorMunki). That is a print-quality check, and
a lower value warns EARLIER about a clogging nozzle or a banding roller — an
advantage when profiling, not an obstacle.
"""
from __future__ import annotations

import pytest

from core.settings import DEFAULTS
from core.argyll_runner import ArgyllRunner
from ui.tabs.tab_measure import TabMeasure


class _Settings:
    def __init__(self, over=None):
        self.d = dict(DEFAULTS)
        self.d.update(over or {})

    def get(self, k, d=None):
        return self.d.get(k, d)

    def set(self, k, v):
        self.d[k] = v


@pytest.fixture
def tab(qapp):
    return TabMeasure(ArgyllRunner(_Settings()), _Settings())


def test_it_is_on_by_default_at_the_tested_value(tab):
    for name, opts in (("guided", tab._chartread_opts),
                       ("manual", tab._m_chartread_opts)):
        opt = {o.key: o for o in opts}["tolerance"]
        assert opt.checkbox.isChecked(), f"{name}: -T is off out of the box"
        assert opt.widget.value() == 0.7, f"{name}: {opt.widget.value()}"
        assert opt.build_args() == ["-T", "0.7"], name


def test_the_settings_defaults_agree_with_the_widgets():
    assert DEFAULTS["measure_tolerance_enabled"] is True
    assert DEFAULTS["measure_tolerance_value"] == 0.7
    assert DEFAULTS["manual2_chartread_tolerance_enabled"] is True


def test_switching_it_off_drops_the_flag(tab):
    opt = {o.key: o for o in tab._chartread_opts}["tolerance"]
    opt.checkbox.setChecked(False)
    assert opt.build_args() == []


def test_a_chosen_value_is_used(tab):
    opt = {o.key: o for o in tab._chartread_opts}["tolerance"]
    opt.widget.setValue(1.5)
    assert opt.build_args() == ["-T", "1.5"]


# ---- the help text -------------------------------------------------------
def test_the_help_text_describes_patch_consistency(tab):
    """Knut: *"make sure the help description is factual and not deterring
    users from using the feature on false grounds … Rewrite the help text from
    a positive viewpoint and factual pros and cons for lower and higher
    values."*"""
    body = {o.key: o for o in tab._chartread_opts}["tolerance"].tooltip_body
    # What it actually measures.
    assert "WITHIN a\nsingle patch" in body or "WITHIN a single patch" in body
    assert "takes many as it slides along" in body
    # Why it is worth having — the positive framing he asked for.
    assert "WHY THAT IS WORTH HAVING" in body
    assert "clog" in body and "banding" in body
    assert "switched on by default" in body
    # Pros AND cons, both directions.
    assert "Lower (0.4–0.7)" in body and "Higher (1.0–2.0)" in body
    assert "cost is" in body                       # the con of going lower
    assert "more forgiving" in body                # the pro of going higher
    # The facts from the ArgyllCMS doc.
    assert "1.0 means exactly what the manufacturer set" in body
    assert "1.5 or 2.0" in body
    assert "laser printers" in body


def test_the_help_text_does_not_deter(tab):
    """The beta.140 wording opened with "LEAVE THIS OFF UNLESS YOU HAVE A
    REASON" and told the user a low value makes good strips fail. That is the
    false ground Knut objected to."""
    body = {o.key: o for o in tab._chartread_opts}["tolerance"].tooltip_body
    assert "LEAVE THIS OFF" not in body
    assert "Swipe didn't start and end" not in body
    assert "less willing to accept" not in body


def test_both_modules_carry_the_same_text(tab):
    g = {o.key: o for o in tab._chartread_opts}["tolerance"]
    m = {o.key: o for o in tab._m_chartread_opts}["tolerance"]
    assert g.tooltip_body == m.tooltip_body
    assert g.tooltip_title == m.tooltip_title
