"""FD-9 review r4 R4-1: WITH THE BETA OFF, THE CARRY TAKES ITS VALUES FROM THE
TARGET AS IT WAS OPENED, NEVER FROM ``meta.json`` AS IT READS AT WRITE TIME.

The reviewer's sequence: an FD-9 project opened with the Beta off shows A4;
the user picks Letter, a write happens without a reload (the Profile-run
pulldown opening), then the user picks A4 again and leaves the tab. A4 then
equals the screen at load, so the carry "restored the stored value", which by
then was the user's own Letter. The user's A4 was lost without a word.

The rules, proved here at the level of ``workflow/fd9/support.py`` over every
sequence of edits and writes (the on-screen half is in
``test_fd9_off_stale_project.py``):

* an untouched target is written back exactly as stored (byte-identical);
* every value the user changed is written as the user left it, in any
  sequence of edits and writes, also after changing it back;
* nothing is carried without a snapshot (after Generate, or for a chart that
  is not an FD-9 chart), and a target stored without the FD-9 is never given
  an FD-9 value;
* with the Beta on, nothing changes.
"""
from __future__ import annotations

import copy
import json
import random

import pytest


@pytest.fixture(autouse=True)
def fd9_beta_off():
    from workflow.fd9 import support
    before = support._latched
    support.set_enabled_for_this_process(False)
    try:
        yield
    finally:
        support._latched = before


#: As a Beta-on Guided FD-9 generate stores it (abridged, real key order).
STORED_PARAMS = {"printtarg-i": {"enabled": True, "value": "FD9"},
                 "printtarg-p": {"enabled": True, "value": "A4"},
                 "targen-f": {"enabled": True, "value": 300}}
STORED_UI = {"mode": "guided",
             "guided": {"instrument": "FD9", "paper": "A4", "pages": 1,
                        "precond": ""},
             "engine_recipe": {"instrument": "FD9", "paper": "A4",
                               "margin_top": 6.0, "margin_left": 6.0,
                               "patch_w_mm": 8.0, "fd9_gap_mm": 1.0,
                               "dpi": 300}}
#: What the off tab shows for it: the i1Pro it falls back to.
SCREEN_PARAMS = {"printtarg-i": {"enabled": True, "value": "i1"},
                 "printtarg-p": {"enabled": True, "value": "A4"},
                 "targen-f": {"enabled": True, "value": 300}}
SCREEN_UI = {"mode": "guided",
             "guided": {"instrument": "i1", "paper": "A4", "pages": 1,
                        "precond": ""},
             "engine_recipe": {"instrument": "i1", "paper": "A4",
                               "margin_top": 38.0, "margin_left": 6.0,
                               "patch_w_mm": 8.0, "dpi": 300}}


class Target:
    """The tab's write path in miniature: the screen, the file, the snapshot
    taken at load, and save_target_settings' carry + "nothing changed"."""

    def __init__(self, stored_params=STORED_PARAMS, stored_ui=STORED_UI,
                 screen_params=SCREEN_PARAMS, screen_ui=SCREEN_UI):
        from workflow.fd9.support import Fd9OffSnapshot, target_names_fd9
        self.file = json.dumps({"create_chart_settings": stored_params,
                                "create_chart_ui": stored_ui})
        self.params = copy.deepcopy(screen_params)
        self.ui = copy.deepcopy(screen_ui)
        self.snap = (Fd9OffSnapshot(self.params, self.ui, stored_params,
                                    stored_ui)
                     if target_names_fd9(stored_params, stored_ui) else None)

    def meta(self):
        return json.loads(self.file)

    def save(self):
        wanted, ui = copy.deepcopy(self.params), copy.deepcopy(self.ui)
        users = self.snap.carry(wanted, ui) if self.snap else set()
        m = self.meta()
        if not (m["create_chart_settings"] == wanted
                and m["create_chart_ui"] == ui):
            self.file = json.dumps({"create_chart_settings": wanted,
                                    "create_chart_ui": ui})
        if self.snap:
            self.snap.written(users)

    def generate(self):
        """Generate forgets the snapshot (tab_chart._forget_fd9_off_screen)."""
        self.snap = None
        self.save()


def test_the_reviewers_sequence_keeps_the_users_a4():
    t = Target()
    t.ui["guided"]["paper"] = "Letter"
    t.save()                         # the pulldown's write, no reload
    assert t.meta()["create_chart_ui"]["guided"]["paper"] == "Letter"
    t.ui["guided"]["paper"] = "A4"
    t.save()                         # leaving the tab
    guided = t.meta()["create_chart_ui"]["guided"]
    assert guided["paper"] == "A4", (
        f"the user's A4 was replaced by their own earlier Letter: {guided}")
    assert guided["instrument"] == "FD9"     # never touched: still carried


def test_an_untouched_target_is_written_back_byte_identical():
    t = Target()
    before = t.file
    for _ in range(3):
        t.save()
    assert t.file == before
    # And what the carry hands the write is the stored blocks in their
    # stored order, so even a forced write would not change a byte.
    wanted, ui = copy.deepcopy(t.params), copy.deepcopy(t.ui)
    assert t.snap.carry(wanted, ui) == set()
    assert json.dumps({"create_chart_settings": wanted,
                       "create_chart_ui": ui}) == before


def test_a_users_instrument_ends_the_carry_of_its_block():
    """A user who picks another instrument has made the block theirs: no FD-9
    margin or gap is filed beside it."""
    t = Target()
    t.ui["engine_recipe"]["instrument"] = "SS"
    t.save()
    recipe = t.meta()["create_chart_ui"]["engine_recipe"]
    assert recipe == SCREEN_UI["engine_recipe"] | {"instrument": "SS"}
    t.ui["engine_recipe"]["instrument"] = "i1"     # and back
    t.save()
    assert t.meta()["create_chart_ui"]["engine_recipe"] == \
        SCREEN_UI["engine_recipe"]


def test_a_target_that_is_not_an_fd9_one_is_never_given_fd9():
    plain_params = copy.deepcopy(SCREEN_PARAMS)
    plain_ui = copy.deepcopy(SCREEN_UI)
    t = Target(plain_params, plain_ui, SCREEN_PARAMS, SCREEN_UI)
    assert t.snap is None
    t.ui["guided"]["paper"] = "Letter"
    t.save()
    assert "FD9" not in t.file


def test_nothing_is_carried_after_generate():
    t = Target()
    t.ui["guided"]["paper"] = "Letter"
    t.save()
    t.generate()
    assert "FD9" not in t.file
    assert t.meta()["create_chart_ui"] == t.ui


def test_with_the_beta_on_nothing_is_carried():
    from workflow.fd9 import support
    support.set_enabled_for_this_process(True)
    wanted, ui = copy.deepcopy(SCREEN_PARAMS), copy.deepcopy(SCREEN_UI)
    snap = support.Fd9OffSnapshot(wanted, ui, STORED_PARAMS, STORED_UI)
    assert snap.carry(wanted, ui) == set()
    assert (wanted, ui) == (SCREEN_PARAMS, SCREEN_UI)
    assert support.carry_fd9_chart_keys(
        wanted, ui, STORED_PARAMS, STORED_UI, (SCREEN_PARAMS, SCREEN_UI)) \
        == set()
    assert (wanted, ui) == (SCREEN_PARAMS, SCREEN_UI)


#: What a user can do to the screen: (where, block, key, values).
EDITS = [
    ("params", None, "printtarg-p", ["A4", "Letter", "A3"]),
    ("params", None, "printtarg-i", ["i1", "SS"]),
    ("params", None, "targen-f", [300, 400]),
    ("ui", "guided", "paper", ["A4", "Letter", "A3"]),
    ("ui", "guided", "pages", [1, 2, 3]),
    ("ui", "guided", "instrument", ["i1", "SS"]),
    ("ui", "engine_recipe", "paper", ["A4", "Letter"]),
    ("ui", "engine_recipe", "margin_top", [38.0, 6.0, 10.0]),
    ("ui", "engine_recipe", "instrument", ["i1", "SS"]),
    ("ui", "mode", None, ["guided", "manual"]),
]


def _get(t, where, block, key):
    if where == "params":
        return t.params[key]["value"]
    return t.ui[block] if key is None else t.ui[block][key]


def _set(t, where, block, key, value):
    if where == "params":
        t.params[key]["value"] = value
    elif key is None:
        t.ui[block] = value
    else:
        t.ui[block][key] = value


@pytest.mark.parametrize("seed", range(300))
def test_any_sequence_of_edits_and_writes_keeps_every_user_change(seed):
    """Property: after every write, a value the user has had on screen at a
    write while it differed from the load (or, for a value the carry never
    touches, any value at all) is in the file exactly as on screen; every
    other value is the stored one; and a run of writes with no edit is the
    stored file, byte for byte."""
    from workflow.fd9.support import CHART_PARAM_KEYS
    rng = random.Random(seed)
    t = Target()
    seen_changed = set()       # keys written while differing from the load
    edited = False
    for _ in range(rng.randint(1, 14)):
        if rng.random() < 0.6:
            where, block, key, values = rng.choice(EDITS)
            _set(t, where, block, key, rng.choice(values))
            edited = True
            continue
        if rng.random() < 0.05:
            t.generate()
            assert "FD9" not in t.file
            assert t.meta() == {"create_chart_settings": t.params,
                                "create_chart_ui": t.ui}
            return
        t.save()
        for where, block, key, _v in EDITS:
            if key is None:
                continue
            at_load = (SCREEN_PARAMS[key]["value"] if where == "params"
                       else SCREEN_UI[block][key])
            if _get(t, where, block, key) != at_load:
                seen_changed.add((block or "params", key))
        m = t.meta()
        cs, ui = m["create_chart_settings"], m["create_chart_ui"]
        # Every value the carry never touches is the screen's.
        assert cs["targen-f"] == t.params["targen-f"]
        assert ui["mode"] == t.ui["mode"]
        # The instrument decides for its block.
        for block, inst, got, screen, stored in (
                ("params", "printtarg-i", cs, t.params, STORED_PARAMS),
                ("guided", "instrument", ui["guided"], t.ui["guided"],
                 STORED_UI["guided"]),
                ("engine_recipe", "instrument", ui["engine_recipe"],
                 t.ui["engine_recipe"], STORED_UI["engine_recipe"])):
            keys = (CHART_PARAM_KEYS if block == "params"
                    else [k for k in stored if k in
                          {k2 for _w, b, k2, _ in EDITS if b == block}
                          | {"margin_left", "patch_w_mm", "fd9_gap_mm"}])
            users_block = (block, inst) in seen_changed
            for key in keys:
                if users_block or (block, key) in seen_changed:
                    # The user's: exactly as on screen (absent if absent).
                    assert got.get(key) == screen.get(key), (
                        seed, block, key, got.get(key), screen.get(key))
                else:
                    assert got.get(key) == stored.get(key), (
                        seed, block, key, got.get(key), stored.get(key))
    if not edited:
        assert t.file == json.dumps({"create_chart_settings": STORED_PARAMS,
                                     "create_chart_ui": STORED_UI})
