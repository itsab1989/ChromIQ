"""-T is not forced on any more, and a stored echo of the old default is dropped.

Knut, beta.139: *"When I now start a measurement, strip mode, no strip is ever
finished without the 'Strip Read Failed' window, and message in window saying
'Swipe didn't start and end on the media', but that is never the case when I
tested."*

chartread's ``-T`` is not a warning threshold. It is passed to the instrument,
which multiplies its own patch-recognition threshold by it while a strip is
being swiped (``PATCH_CONS_THR * m->scan_toll_ratio``, munki_imp.c:5353 and
i1pro_imp.c:6666) — the rule that decides where one patch ends and the next
begins. ChromIQ shipped the option ticked at 0.7, so every strip anybody ever
measured was judged around a third stricter than the manufacturer's setting.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

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


def test_the_default_leaves_the_instrument_alone(qapp):
    """Out of the box, no -T reaches chartread at all, so the driver keeps the
    threshold its maker chose."""
    t = TabMeasure(ArgyllRunner(_Settings()), _Settings())
    for name, opts in (("guided", t._chartread_opts),
                       ("manual", t._m_chartread_opts)):
        opt = {o.key: o for o in opts}["tolerance"]
        assert opt.checkbox is not None and not opt.checkbox.isChecked(), \
            f"{name}: -T is ticked out of the box"
        assert opt.build_args() == [], f"{name}: -T reaches the command line"


def test_argylls_own_value_is_what_the_box_offers(qapp):
    """When somebody does switch it on, the number waiting for them is 1.0 —
    the manufacturer's setting — not a stricter one they never chose."""
    t = TabMeasure(ArgyllRunner(_Settings()), _Settings())
    for opts in (t._chartread_opts, t._m_chartread_opts):
        opt = {o.key: o for o in opts}["tolerance"]
        assert opt.widget.value() == 1.0


def test_switching_it_on_still_sends_the_flag(qapp):
    t = TabMeasure(ArgyllRunner(_Settings()), _Settings())
    opt = {o.key: o for o in t._chartread_opts}["tolerance"]
    opt.checkbox.setChecked(True)
    opt.widget.setValue(0.4)
    assert opt.build_args() == ["-T", "0.4"]


# ---- the migration -------------------------------------------------------
def _stored(tmp_path, value, enabled=True):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", 16)          # pre-schema-17
    s._qs.setValue("measure_tolerance_enabled", enabled)
    s._qs.setValue("manual2_chartread_tolerance_enabled", enabled)
    if value is not None:
        s._qs.setValue("measure_tolerance_value", value)
    return s


@pytest.mark.parametrize("stored", [0.5, 0.7])
def test_a_stored_echo_of_an_old_default_is_dropped(tmp_path, stored):
    """Both old defaults shipped: the spinbox was built at 0.5 and the row was
    then force-ticked at 0.7, so a saved file can carry either."""
    s = _stored(tmp_path, stored)
    dropped = s.migrate()
    assert any("tolerance" in d for d in dropped), dropped
    assert s._qs.value("measure_tolerance_value", None) is None
    assert s._qs.value("measure_tolerance_enabled", None) is None
    assert s._qs.value("manual2_chartread_tolerance_enabled", None) is None
    # …so both resolve to the new defaults.
    assert s.get("measure_tolerance_enabled") is False
    assert float(s.get("measure_tolerance_value")) == 1.0


def test_a_value_the_user_chose_survives(tmp_path):
    """0.4 is a deliberate choice — some i1 Pro 2 / 3 owners run it. Keep it,
    and keep the tick that goes with it."""
    s = _stored(tmp_path, 0.4)
    s.migrate()
    assert float(s._qs.value("measure_tolerance_value")) == 0.4
    assert s.get("measure_tolerance_enabled") is True


def test_the_enable_flag_alone_is_dropped_too(tmp_path):
    """Somebody who never touched the spinbox has only the forced tick stored;
    it must not survive as an enabled -T at the new 1.0."""
    s = _stored(tmp_path, None)
    dropped = s.migrate()
    assert any("tolerance" in d for d in dropped), dropped
    assert s.get("measure_tolerance_enabled") is False
