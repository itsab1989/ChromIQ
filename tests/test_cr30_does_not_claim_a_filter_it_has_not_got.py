"""#159 (report 19): `-F` wrote a false claim into the user's measurement file.

Proved against the real helper: run with `--json -v -c 1 -xx -p -F 6`, answer
one value, and the .ti3 comes back carrying

    INSTRUMENT_FILTER "D65"

although no instrument was ever opened — the external-value path opens none —
and the CR30 has no filter at all. The instrument's own phone app settles that
independently: it offers no measurement condition and no UV filter anywhere, so
this is not a setting that could be made to work by configuring the device.

That is a false record of HOW the data was gathered, in the user's own file. It
does not change the profile numbers (colprof ignores the keyword), which is
precisely what makes it the dangerous kind of wrong: nothing downstream
disagrees with it.

Greying the row is not enough, because the option's arguments are built from
its checkbox and never from whether the widget is enabled. It has to stop
speaking.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                    # noqa: E402

from PyQt6.QtWidgets import QApplication, QCheckBox, QSpinBox    # noqa: E402

from ui.tabs.tab_measure import _ChartreadOption                 # noqa: E402


@pytest.fixture(autouse=True)
def _app():
    QApplication.instance() or QApplication([])


def _opt(**kw):
    box = QCheckBox()
    box.setChecked(True)
    return _ChartreadOption(key="filter", flag="-F", label="", tooltip_title="",
                            tooltip_body="", checkbox=box, **kw)


def test_a_suppressed_option_emits_nothing():
    o = _opt()
    assert o.build_args() == ["-F"]
    o.suppressed = True
    assert o.build_args() == [], (
        "the flag is still sent, so the measurement file still carries a claim "
        "about a filter the instrument does not have")


def test_suppressing_does_not_untick_the_user_s_choice():
    """The value belongs to the target, not to whichever instrument happens to
    be attached today. It must survive for the day the same chart is measured
    with something that does honour it."""
    o = _opt()
    o.suppressed = True
    o.build_args()
    assert o.checkbox.isChecked() is True, (
        "suppressing the option rewrote the user's stored setting")


def test_a_suppressed_option_with_a_value_is_silent_too():
    spin = QSpinBox()
    spin.setValue(6)
    o = _opt(widget=spin)
    assert o.build_args() == ["-F", "6"]
    o.suppressed = True
    assert o.build_args() == []
    assert spin.value() == 6, "the stored value was lost"
