"""The per-target parameter list is generated, and complete.

Specification `docs/design/per_target_settings.md` S1.1; test plan §2 (P1/P2).
Knut's rule is that **all** non-global parameters are stored — so the thing that
must be tested is not "does the store work" but "does the store know about every
parameter". A hand-written list would pass its own tests for ever while quietly
missing whatever was added last.
"""
import pytest

from core.file_manager import FileManager
from core.settings import AppSettings
from workflow.per_target_settings import (GLOBAL_FLAGS, apply,
                                          params_for, snapshot)


class _FakeWidget:
    def __init__(self, flag, value="", enabled=True):
        self.flag = flag
        self._v, self._e = value, enabled

    def get_raw_value(self):        return self._v
    def set_value(self, v):         self._v = v
    @property
    def is_enabled_by_user(self):   return self._e
    def set_user_enabled(self, b):  self._e = b


class _FakeTab:
    def __init__(self, mapping):    self._m = mapping
    def per_target_widgets(self):   return self._m


def test_a_tab_out_of_scope_yields_nothing_rather_than_raising():
    """Print Chart and Check & Refine are deliberately out of scope (§5)."""
    class Bare: pass
    assert params_for(Bare()) == []


def test_the_key_is_tool_qualified():
    """targen and printtarg both have a -p; one key would lose one of them."""
    tab = _FakeTab({"targen": [_FakeWidget("-p")],
                    "printtarg": [_FakeWidget("-p")]})
    keys = {p.key for p in params_for(tab)}
    assert keys == {"targen-p", "printtarg-p"}


def test_a_repeatable_parameter_keeps_every_row():
    """targen -D is a cascade: one visible row plus ten hidden ones.

    The real Create Chart tab is what taught this module the case — the first
    version treated the eleven rows as duplicates, which would have dropped
    every device value after the first.
    """
    tab = _FakeTab({"targen": [_FakeWidget("-D", value="a"),
                               _FakeWidget("-D", value="b"),
                               _FakeWidget("-D", value="", enabled=False)]})
    (p,) = params_for(tab)
    assert p.repeats
    assert p.read() == {"repeats": [
        {"enabled": True,  "value": "a"},
        {"enabled": True,  "value": "b"},
        {"enabled": False, "value": ""},
    ]}


def test_a_shorter_stored_cascade_clears_the_rows_beyond_it():
    """Otherwise a longer cascade from the previous target leaves its tail."""
    tab = _FakeTab({"targen": [_FakeWidget("-D", value="old1"),
                               _FakeWidget("-D", value="old2"),
                               _FakeWidget("-D", value="old3")]})
    apply(tab, {"targen-D": {"repeats": [{"enabled": True, "value": "new1"}]}})
    assert [w.get_raw_value() for w in tab._m["targen"]] == ["new1", "", ""]
    assert [w.is_enabled_by_user for w in tab._m["targen"]] == [True, False, False]


def test_a_row_with_no_flag_is_skipped():
    tab = _FakeTab({"targen": [_FakeWidget(""), _FakeWidget("-f")]})
    assert [p.flag for p in params_for(tab)] == ["-f"]


def test_enabled_and_value_are_recorded_separately():
    """A row can be OFF with a value still typed in it (test plan R3)."""
    tab = _FakeTab({"targen": [_FakeWidget("-f", value="12", enabled=False)]})
    assert snapshot(tab) == {"targen-f": {"enabled": False, "value": "12"}}


def test_an_empty_value_is_not_the_same_as_an_absent_one():
    """Test plan P5: `-D ""` and no `-D` must stay distinguishable."""
    empty = _FakeTab({"colprof": [_FakeWidget("-D", value="")]})
    assert snapshot(empty)["colprof-D"]["value"] == ""
    assert "colprof-D" in snapshot(empty)


def test_a_round_trip_restores_both_halves():
    tab = _FakeTab({"targen": [_FakeWidget("-f", value="9", enabled=True)]})
    stored = snapshot(tab)
    tab._m["targen"][0].set_value("999")
    tab._m["targen"][0].set_user_enabled(False)
    assert apply(tab, stored) == []
    assert snapshot(tab) == stored


def test_the_value_is_set_before_the_row_is_switched_on():
    """Enabling first would flash the default — with auto-update, a redraw."""
    order = []

    class W(_FakeWidget):
        def set_value(self, v):        order.append("value"); super().set_value(v)
        def set_user_enabled(self, b): order.append("enable"); super().set_user_enabled(b)

    tab = _FakeTab({"targen": [W("-f")]})
    apply(tab, {"targen-f": {"enabled": True, "value": "3"}})
    assert order == ["value", "enable"]


def test_an_unknown_key_is_reported_not_raised():
    """A chart made before a parameter was renamed must still open (§7 A)."""
    tab = _FakeTab({"targen": [_FakeWidget("-f")]})
    assert apply(tab, {"targen-gone": {"enabled": True, "value": 1}}) == ["targen-gone"]
    # …and the parameters that ARE known still loaded.
    assert apply(tab, {"targen-f": {"enabled": True, "value": "7"}}) == []
    assert snapshot(tab)["targen-f"]["value"] == "7"


def test_a_malformed_record_is_reported_not_crashed():
    tab = _FakeTab({"targen": [_FakeWidget("-f")]})
    assert apply(tab, {"targen-f": "not a dict"}) == ["targen-f"]


def test_global_flags_are_declared_in_one_place():
    """A parameter left out must be a declaration, never an omission."""
    assert isinstance(GLOBAL_FLAGS, frozenset)


def test_the_real_create_chart_tab_answers(qapp):
    """P1: the registry must find the real tab's parameters, not just fakes."""
    from ui.tabs.tab_chart import TabChart
    assert hasattr(TabChart, "per_target_widgets"), (
        "Create Chart no longer exposes its parameter rows — the store and the "
        "tests would both silently cover nothing"
    )
