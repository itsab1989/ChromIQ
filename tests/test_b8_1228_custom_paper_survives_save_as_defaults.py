"""B8-1228: "Save as Defaults" on a Custom paper opened the next session on A2.

Found by the B8-1221 matrix (beta 43): Manual, Custom 130 x 180 mm, Save as
Defaults, restart, and both Paper fields showed A2 (a ColorMunki's first paper;
an i1Pro's is A2 Landscape).

THE STORE WAS RIGHT. ``chart_paper``, ``-p`` and the engine recipe all held
``130x180``, and the layout panel DID load it. Two things then undid it:

1. Guided has no Custom entry, so ``_restore_defaults`` found no ``130x180``
   in its Paper combo and left it where ``_rebuild_paper_combo`` put it: the
   first row, A2.
2. ``_restore_defaults`` ends with ``_switch_mode(chart_mode)``. At start-up
   Guided is on screen, and with no snapshot of its shared settings the switch
   to Manual took every Guided field as "changed" and carried Guided's A2 into
   Manual's ``-p`` and the layout panel.

Manual lost Custom when the session opened on Manual; Guided showed A2
always; both engine states. The fix: the restore's own switch carries nothing
(both modes snapshotted, the carry held off), Guided falls back to the same
dimensions under a Guided code, else A4, never its first row, and with the
engine on the hidden ``-p`` is put in step with the saved recipe first,
because every Guided -> Manual switch pushes ``-p`` into the panel
(``_sync_engine_panel_after_transfer``). That last part is what the old carry
had been doing by accident: it overwrote a stale ``-p`` with Guided's paper,
which happened to be the recipe's in Knut's store (B8-1221's
``test_knuts_start_then_a_preset_on_another_paper`` went red without it).

The restore's switch must still RUN its carry, though: its last step seeds the
layout panel's instrument and paper from ``-i`` / ``-p``. A first cut held the
whole carry off, and on screen a ColorMunki store came back as i1Pro (the
panel's default, mirrored into ``-i``); the round trip now checks the
instrument too.

MUTATIONS, each red here (scratch mutate.py, the results in the register):
* drop the two snapshots before the restore's switch: Manual opens on A2 /
  A2 Landscape;
* hold the restore's switch off entirely: the instrument comes back i1Pro;
* drop the A4 fallback: Guided opens on its first row;
* drop putting ``-p`` in step with the saved recipe: a stale ``-p`` replaces
  the recipe's paper when Manual opens.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def store(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _session(qapp, s):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    qapp.processEvents()
    return t


def _close(qapp, t):
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _choose(t, paper: str, engine: bool) -> None:
    """Pick *paper* where a person does: the layout panel's Paper (Custom
    through its W x H boxes) with the engine on, printtarg's with it off."""
    if not engine:
        t._manual_paper_pw.set_value(paper)
        return
    p = t._manual_layout_panel
    i = p.paper.findData(paper)
    if i < 0:
        w, h = (int(v) for v in paper.split("x"))
        p.custom_w.setValue(w)
        p.custom_h.setValue(h)
        i = p.paper.findData("__custom__")
    p.paper.setCurrentIndex(i)


def _round_trip(qapp, s, instr, engine, paper, start="manual"):
    s.set("chart_instrument", instr)
    s.set("use_chromiq_layout_engine", engine)
    s.set("chart_mode", start)       # the first session opens there too
    t = _session(qapp, s)
    if t._current_mode() != "manual":
        t._manual_btn.click()
        qapp.processEvents()
    assert (not t._manual_layout_grp.isHidden()) is engine
    _choose(t, paper, engine)
    qapp.processEvents()
    shown = t._manual_paper_on_screen()
    assert shown == paper
    # The instrument must survive too: the panel is seeded from -i by the
    # switch into Manual, and a restore that skipped that seeding put the
    # panel on its default i1Pro and mirrored it back into -i (found on
    # screen while fixing B8-1228).
    assert t._shared_get("manual")["instrument"] == instr
    if engine:
        assert t._manual_layout_panel.selection()[0] == instr
    t._on_save_defaults()
    s.set("chart_mode", start)       # as closing the window in that mode does
    _close(qapp, t)
    t2 = _session(qapp, s)
    if start == "guided":
        t2._switch_mode("manual")
        qapp.processEvents()
    assert t2._shared_get("manual")["instrument"] == instr
    assert t2._instr_combo.currentData() == instr
    if engine:
        assert t2._manual_layout_panel.selection()[0] == instr
    return t2


@pytest.mark.parametrize("instr", ["CM", "i1"])
@pytest.mark.parametrize("engine", [True, False], ids=["engine", "printtarg"])
@pytest.mark.parametrize("paper", ["130x180", "100x150"])
def test_a_custom_paper_saved_in_manual_opens_on_custom(qapp, store, instr,
                                                        engine, paper):
    t = _round_trip(qapp, store, instr, engine, paper)
    try:
        assert t._current_mode() == "manual"
        assert t._manual_paper_on_screen() == paper
        assert t._manual_paper_pw.get_raw_value() == paper
        if engine:
            p = t._manual_layout_panel
            assert p.paper.currentData() == "__custom__"
            w, h = (int(v) for v in paper.split("x"))
            assert (int(p.custom_w.value()), int(p.custom_h.value())) == (w, h)
        # B8-1221: the lists follow the field on screen, so they are Custom's.
        assert t._preset_paper_selected() == "custom"
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("instr", ["CM", "i1"])
def test_guided_cannot_show_custom_and_opens_on_a4_not_its_first_row(
        qapp, store, instr):
    t = _round_trip(qapp, store, instr, True, "130x180")
    try:
        t._switch_mode("guided")
        qapp.processEvents()
        assert t._paper_combo.currentData() == "A4"
        assert t._paper_combo.currentIndex() != 0
        # …and leaving Guided untouched does not carry A4 back into Manual.
        t._switch_mode("manual")
        qapp.processEvents()
        assert t._manual_paper_on_screen() == "130x180"
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("engine", [True, False], ids=["engine", "printtarg"])
@pytest.mark.parametrize("start", ["manual", "guided"])
@pytest.mark.parametrize("paper", ["A4", "420x297", "483x329", "Letter",
                                   "127x178", "4x6"])
def test_the_named_papers_still_round_trip(qapp, store, engine, start, paper):
    t = _round_trip(qapp, store, "CM", engine, paper, start)
    try:
        assert t._manual_paper_on_screen() == paper
        assert t._paper_combo.currentData() == paper
        assert t._preset_paper_selected() == paper
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("start", ["manual", "guided"])
def test_a_stale_hidden_paper_does_not_replace_the_saved_recipes(qapp, store,
                                                                 start):
    """Knut's store: the engine recipe saved on A4, printtarg's hidden -p on
    A3 Landscape (an older save, B8-1223). Every Guided -> Manual switch pushes
    -p into the layout panel, so a stale -p replaced the recipe's paper the
    moment Manual opened, at start-up or on the first click. The recipe is the
    paper that was on screen; -p is put in step with it at start-up."""
    from workflow.layout_engine.presets import default_recipe
    for k, v in {"chart_mode": start, "chart_instrument": "CM",
                 "chart_paper": "A4", "use_chromiq_layout_engine": True,
                 "manual_printtarg_-i_l": "CM",
                 "manual_engine_recipe": default_recipe("CM", "A4").to_dict(),
                 "manual_printtarg_-p_l": "420x297"}.items():
        store.set(k, v)
    t = _session(qapp, store)
    try:
        if start == "guided":
            t._manual_btn.click()
            qapp.processEvents()
        assert t._current_mode() == "manual"
        assert t._manual_layout_panel.selection()[1] == "A4"
        assert t._manual_paper_pw.get_raw_value() == "A4"
        assert t._preset_paper_selected() == "A4"
    finally:
        _close(qapp, t)


def test_a_paper_changed_by_hand_in_guided_still_carries_into_manual(qapp, store):
    """The snapshot must not swallow a real edit: after a Custom restart, A3
    Landscape picked in Guided reaches Manual on the switch (Knut #9)."""
    t = _round_trip(qapp, store, "CM", True, "130x180")
    try:
        t._switch_mode("guided")
        t._paper_combo.setCurrentIndex(t._paper_combo.findData("420x297"))
        t._switch_mode("manual")
        qapp.processEvents()
        assert t._manual_paper_on_screen() == "420x297"
    finally:
        _close(qapp, t)
