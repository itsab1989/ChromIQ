"""B8-1310 (Knut, #182 5845519118, 2026-09-26): a Custom size that EQUALS a
named paper is that named paper, in both preset lists.

*"if the custom side equals to a named paper size, that preset should be
treated as that named paper size."* This REVERSES B8-1260 (beta 44 challenge
F1), which made the Custom entry decide whatever the boxes held. So:

* Custom 420 x 297 lists A3 Landscape's presets, 210 x 297 A4 Portrait's,
  297 x 210 A4 Landscape's, 216 x 279 Letter's (the boxes take whole
  millimetres, and Letter is 215.9 x 279.4).
* The orientation is matched exactly, as the paper codes spell it: 152 x 102
  (a 4 x 6 in card turned) names no paper, so it is Custom.
* A size equal to no named paper keeps the Custom lists: every Custom preset,
  whatever the boxes say (K48).

THE EXPECTED VALUES DO NOT COME FROM THE CODE UNDER TEST. The named papers are
read from ``data/parameters.yaml`` (the Paper field's own list), and their
millimetre sizes are written out here from the paper standards (ISO 216, ANSI),
not taken from ``workflow.layout_engine.papers`` or ``paper_class``.

MUTATIONS (mutations.txt of the k50 proof): ``paper_class`` without the
size match (B8-1260's rule for W x H codes): 210 x 297, 297 x 210, 216 x 279,
102 x 152 red; the B8-1260 Custom-entry check put back into
``_preset_paper_selected``: every named-size case red, engine on and off;
the orientation dropped from the match (sorted sides): 152 x 102 red.
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

#: Each named paper's size in mm, width x height as the code orients it.
#: Written from the standards, NOT read from the app.
SIZES_MM = {
    "A2": (420, 594), "594x420": (594, 420),
    "329x483": (329, 483), "483x329": (483, 329),
    "A3": (297, 420), "420x297": (420, 297),
    "11x17": (279.4, 431.8), "Legal": (215.9, 355.6),
    "A4": (210, 297), "A4R": (297, 210),
    "Letter": (215.9, 279.4), "LetterR": (279.4, 215.9),
    "203x254": (203, 254), "127x178": (127, 178),
    "4x6": (101.6, 152.4),
}

#: (Custom W x H as typed in whole millimetres, the class a person expects)
CASES = [
    ((420, 297), "420x297"),
    ((210, 297), "A4"),
    ((297, 210), "A4R"),
    ((216, 279), "Letter"),
    ((102, 152), "4x6"),
    ((127, 178), "127x178"),
    ((297, 420), "A3"),
    ((152, 102), "custom"),     # 4 x 6 in turned: no such named paper
    ((250, 300), "custom"),
    ((100, 150), "custom"),
]


def _named_papers() -> set:
    data = yaml.safe_load((ROOT / "data" / "parameters.yaml").read_text(
        encoding="utf-8"))
    for p in data["parameters"]["printtarg"]:
        if p.get("flag") == "-p":
            return {c for c in p["choices"] if c != "custom"}
    raise AssertionError("printtarg -p is not in parameters.yaml")


NAMED = _named_papers()


def _class(paper) -> str:
    """A preset's paper as a person reads it: its named paper, the named
    paper its millimetre size equals, or Custom."""
    paper = str(paper or "")
    if paper in NAMED:
        return paper
    try:
        w, h = (float(x) for x in paper.split("x"))
    except ValueError:
        return "custom"
    for code, (nw, nh) in SIZES_MM.items():
        if code in NAMED and abs(nw - w) < 0.5 and abs(nh - h) < 0.5:
            return code
    return "custom"


def test_every_named_paper_has_a_size_here():
    assert NAMED <= set(SIZES_MM), NAMED - set(SIZES_MM)


@pytest.mark.parametrize("dims,want", CASES,
                         ids=[f"{w}x{h}" for (w, h), _ in CASES])
def test_the_class_of_a_custom_size(dims, want):
    assert cp.paper_class(f"{dims[0]}x{dims[1]}") == want
    assert _class(f"{dims[0]}x{dims[1]}") == want      # the test agrees too


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
    the engine on, printtarg's with it off."""
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
@pytest.mark.parametrize("dims,want", CASES,
                         ids=[f"{w}x{h}" for (w, h), _ in CASES])
def test_custom_lists_what_its_size_is(tab, settings, qapp, engine, dims,
                                       want):
    """Custom with the boxes on each size, after A4 (so a stale list would
    show A4's): both lists are the named paper's when the size equals one,
    Custom's otherwise."""
    _engine(tab, qapp, engine)
    _choose(tab, qapp, engine, "A4")
    _choose(tab, qapp, engine, "custom", dims)
    assert tab._manual_paper_on_screen() == f"{dims[0]}x{dims[1]}"
    assert tab._preset_paper_selected() == want
    exp = _expected(settings, want)
    assert _pulldown(tab) == exp
    assert _popup(tab) == exp


def test_a_custom_size_is_the_named_papers_list_not_customs(tab, settings,
                                                            qapp):
    """The point of the ruling, stated as a difference: on Custom 420 x 297
    the lists are A3 Landscape's, which are not Custom's."""
    _engine(tab, qapp, True)
    _choose(tab, qapp, True, "custom", (420, 297))
    a3l, custom = _expected(settings, "420x297"), _expected(settings, "custom")
    assert a3l and custom and a3l != custom
    assert _pulldown(tab) == a3l


def test_a_box_changed_on_custom_follows_the_size(tab, settings, qapp):
    """Typing a named paper's size into the boxes while Custom is selected
    brings that paper's lists; typing it away again brings Custom's."""
    _engine(tab, qapp, True)
    _choose(tab, qapp, True, "custom", (100, 150))
    assert _pulldown(tab) == _expected(settings, "custom")
    panel = tab._manual_layout_panel
    panel.custom_w.setValue(420)
    panel.custom_h.setValue(297)
    qapp.processEvents()
    assert tab._preset_paper_selected() == "420x297"
    assert _pulldown(tab) == _expected(settings, "420x297")
    assert _popup(tab) == _expected(settings, "420x297")
    panel.custom_w.setValue(250)
    panel.custom_h.setValue(300)
    qapp.processEvents()
    assert tab._preset_paper_selected() == "custom"
    assert _pulldown(tab) == _expected(settings, "custom")


def test_guided_filters_by_its_named_paper(tab, settings, qapp):
    """Guided has no Custom entry (C7); its A3 Landscape is A3 Landscape."""
    tab._switch_mode("guided")
    qapp.processEvents()
    c = tab._paper_combo
    assert c.findData("custom") < 0 and c.findData("__custom__") < 0
    c.setCurrentIndex(c.findData("420x297"))
    qapp.processEvents()
    assert tab._preset_paper_selected() == "420x297"
    assert _pulldown(tab) == _expected(settings, "420x297")
