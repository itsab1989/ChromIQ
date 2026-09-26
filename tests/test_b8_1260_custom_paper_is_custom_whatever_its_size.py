"""B8-1260 (beta 44 challenge F1): on "Custom", the paper filter is the Custom
class WHATEVER THE BOXES HOLD.

C7, and Knut in K48 (#182 5840677938): *"All Custom papers should then show
(disregarding any setting in the Custom size input boxes)"*. Beta 44 read the
Paper field on screen as a ``-p`` code, Custom as ``WxH``, and
``paper_class`` calls any code the paper list names a named paper. So a Custom
420 x 297 was A3 Landscape, and both lists showed A3 Landscape's presets; so
were 127 x 178 (5 x 7 in), 594 x 420 (A2 Landscape), 329 x 483 and 483 x 329
(A3+), 203 x 254 (8 x 10 in). Every one of the 5 instruments, engine on and
off (the challenge round, on screen).

THE EXPECTED VALUES DO NOT COME FROM THE CODE UNDER TEST. The B8-1221 and K48
drivers judged through ``paper_class`` too, so they agreed with the fault.
Here the named papers are read from ``data/parameters.yaml`` (the Paper
field's own list), and the expected class is "custom" because the test put the
field on Custom, not because a function said so.

MUTATIONS (each red here, see mutations.txt of the fixes-1 proof):
* ``_preset_paper_selected`` without the Custom-entry check (the beta 44
  code): every colliding size red, engine on and off; the non-colliding
  130 x 180 stays green, which is why the old tests never saw it.
* ``_manual_paper_is_custom_on_screen`` asking only the layout panel: the
  engine-off cases red.
* it asking only printtarg's widget: the engine-on cases red.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import core.curated_presets as cp                               # noqa: E402
from ui.tabs import tab_chart as TC                             # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

#: Custom sizes that spell a named paper's code (the challenge round's six)
COLLIDING = [(420, 297), (127, 178), (594, 420), (329, 483), (483, 329),
             (203, 254)]


def _named_papers() -> set:
    """The named entries of Manual's Paper field, from its own definition."""
    data = yaml.safe_load((ROOT / "data" / "parameters.yaml").read_text(
        encoding="utf-8"))
    for p in data["parameters"]["printtarg"]:
        if p.get("flag") == "-p":
            return {c for c in p["choices"] if c != "custom"}
    raise AssertionError("printtarg -p is not in parameters.yaml")


NAMED = _named_papers()


def _class(paper) -> str:
    paper = str(paper or "")
    return paper if paper in NAMED else "custom"


def test_the_colliding_sizes_really_are_named_codes():
    """The premise: each size is a code the Paper field names, so a filter
    that reads the size finds a named paper."""
    for w, h in COLLIDING:
        assert f"{w}x{h}" in NAMED


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set(cp.PAPER_FILTER_KEY, True)
    s.set("use_chromiq_layout_engine", True)
    s.set("chart_instrument", "i1")
    return s


@pytest.fixture()
def tab(qapp, settings):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    qapp.processEvents()
    yield t
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _expected(settings, sel):
    """(heading, ticked keys, count under the arrow) for every group the rule
    lists on the class *sel*, computed without the filter's functions."""
    shown = cp.shown_keys(settings, TC.BUILTIN_PRESET_KEYS)
    out = []
    for h, es in TC.BUILTIN_PRESET_GROUPS:
        keys = [k for *_x, k in es if _class(TC.builtin_preset_paper(k)) == sel]
        if keys:
            out.append((h, [k for k in keys if k in shown],
                        len([k for k in keys if k not in shown])))
    return out


def _pulldown(tab):
    from PyQt6.QtCore import Qt
    tab._reveal_current_preset_group()
    cb = tab._preset_combo
    view = cb.view()
    heads = {h for h, _e in TC.BUILTIN_PRESET_GROUPS}
    out, cur = [], None
    for r in range(cb.count()):
        if view.isRowHidden(r):
            continue
        text, key = cb.itemText(r), cb.itemData(r)
        if key is None and text in heads:
            cur = [text, [], 0]
            out.append(cur)
        elif cur is not None and cb.itemData(r, cb.MORE_ROLE):
            cur[2] = int(cb.itemData(r, Qt.ItemDataRole.UserRole + 44) or 0)
        elif cur is not None and isinstance(key, str):
            cur[1].append(key)
    return [tuple(x) for x in out]


def _popup(tab):
    tab._open_builtin_preset_overlay()
    pop = tab._builtin_preset_popup
    try:
        return [(h, [k for _l, k in e], len(pop._more.get(h, [])))
                for h, e in pop._groups]
    finally:
        pop.close()


def _choose(tab, qapp, engine: bool, code: str, dims=None) -> None:
    """A person's pick in the Paper field on screen: the layout panel's with
    the engine on, printtarg's with it off. The boxes are typed first, as a
    person who had them on that size before would find them."""
    if engine:
        panel = tab._manual_layout_panel
        want = "__custom__" if code == "custom" else code
        if dims:
            panel.custom_w.setValue(dims[0])
            panel.custom_h.setValue(dims[1])
        i = panel.paper.findData(want)
        assert i >= 0, want
        panel.paper.setCurrentIndex(i)
    else:
        pw = tab._manual_paper_pw
        if dims:
            pw._custom_w_spin.setValue(dims[0])
            pw._custom_h_spin.setValue(dims[1])
        i = pw._custom_combo.findData(code)
        assert i >= 0, code
        pw._custom_combo.setCurrentIndex(i)
    qapp.processEvents()


def _engine(tab, qapp, on: bool) -> None:
    tab._manual_engine_check.setChecked(on)
    qapp.processEvents()
    assert tab._manual_layout_grp.isHidden() is (not on)


@pytest.mark.parametrize("engine", [True, False], ids=["engine-on",
                                                        "engine-off"])
@pytest.mark.parametrize("dims", COLLIDING,
                         ids=[f"{w}x{h}" for w, h in COLLIDING])
def test_custom_on_a_named_papers_size_lists_the_custom_presets(
        tab, settings, qapp, engine, dims):
    """The named paper first (so a filter reading the size shows exactly the
    lists it already had), then Custom with the boxes on that paper's size:
    both lists are Custom's, never the named paper's."""
    _engine(tab, qapp, engine)
    named = f"{dims[0]}x{dims[1]}"
    _choose(tab, qapp, engine, named)
    exp_named = _expected(settings, named)
    assert _pulldown(tab) == exp_named
    _choose(tab, qapp, engine, "custom", dims)
    assert tab._manual_paper_on_screen() == named     # the size is kept
    assert tab._preset_paper_selected() == cp.CUSTOM_PAPER
    exp = _expected(settings, "custom")
    assert exp and exp != exp_named
    assert _pulldown(tab) == exp
    assert _popup(tab) == exp


@pytest.mark.parametrize("engine", [True, False], ids=["engine-on",
                                                        "engine-off"])
def test_back_from_custom_to_the_named_paper_is_that_paper_again(
        tab, settings, qapp, engine):
    """The Custom rule goes no further than the Custom entry: back on A3
    Landscape the lists are A3 Landscape's."""
    _engine(tab, qapp, engine)
    _choose(tab, qapp, engine, "custom", (420, 297))
    assert _pulldown(tab) == _expected(settings, "custom")
    _choose(tab, qapp, engine, "420x297")
    assert tab._preset_paper_selected() == "420x297"
    assert _pulldown(tab) == _expected(settings, "420x297")
    assert _popup(tab) == _expected(settings, "420x297")


def test_a_box_changed_on_custom_keeps_the_custom_class(tab, settings, qapp):
    """Typing a named paper's size into the boxes while Custom is selected
    (the entry does not move) must not bring the named paper's lists."""
    _engine(tab, qapp, True)
    _choose(tab, qapp, True, "custom", (100, 150))
    panel = tab._manual_layout_panel
    panel.custom_w.setValue(420)
    panel.custom_h.setValue(297)
    qapp.processEvents()
    assert tab._manual_paper_on_screen() == "420x297"
    assert tab._preset_paper_selected() == cp.CUSTOM_PAPER
    assert _pulldown(tab) == _expected(settings, "custom")
    assert _popup(tab) == _expected(settings, "custom")


def test_guided_has_no_custom_and_filters_by_its_named_paper(
        tab, settings, qapp):
    """Guided has no Custom entry (C7), so its A3 Landscape is A3 Landscape;
    the fix must not turn a named Guided paper into Custom."""
    tab._switch_mode("guided")
    qapp.processEvents()
    c = tab._paper_combo
    assert c.findData("custom") < 0 and c.findData("__custom__") < 0
    c.setCurrentIndex(c.findData("420x297"))
    qapp.processEvents()
    assert tab._preset_paper_selected() == "420x297"
    assert _pulldown(tab) == _expected(settings, "420x297")
