"""Every preset list orders its instrument groups like the Create Chart
Instrument pulldown, and a paper change after loading a preset lists the new
paper's presets while the loaded one stays (#182, Knut 5833490026; register
B8-1146, B8-1147).

Knut: *"The sequence of the groups of presets, which are related to specific
instruments, should be placed in the "Select preset" and the "built-in
presets" button in the same sequence as in the dropdown list of the
Instrument field. So, "Colormunki / i1Studio..." heading with its presets
should not come first, but third. "i1Pro / i1Pro 2 ..." heading with its
presets come first, etc. Scanner and Red River Paper always come at the end
like before."* Basti's rule is one order for every preset list.
"""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import core.curated_presets as cp                               # noqa: E402
from data.patch_db import INSTRUMENT_LABELS                     # noqa: E402
from ui.tabs import tab_chart as TC                             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT_ORDER = [TC.INSTRUMENT_GROUP_LABELS["i1Pro"],
                    TC.INSTRUMENT_GROUP_LABELS["i1Pro 3 Plus"],
                    TC.INSTRUMENT_GROUP_LABELS["ColorMunki"],
                    TC.INSTRUMENT_GROUP_LABELS["CR30"]]
EXPECTED = INSTRUMENT_ORDER + ["Scanner", "Red River Paper"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


@pytest.fixture()
def tab(qapp, settings):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._populate_preset_combo({})
    yield t
    t.deleteLater()
    qapp.processEvents()


def _unique(seq):
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def test_the_registry_follows_the_instrument_pulldown():
    """MUTATION: drop the sort after BUILTIN_PRESET_GROUPS (red: ColorMunki
    first, as until beta 43)."""
    assert [h for h, _e in TC.BUILTIN_PRESET_GROUPS] == EXPECTED
    # the order is READ from the pulldown's source, not a second list
    ranks = [TC.instrument_group_rank(h) for h in INSTRUMENT_ORDER]
    assert ranks == sorted(ranks)
    assert [list(INSTRUMENT_LABELS.values()).index(h)
            for h in INSTRUMENT_ORDER] == ranks


def test_guided_and_manual_instrument_fields_list_the_same_order():
    """Guided's Instrument pulldown lists `INSTRUMENT_LABELS`; Manual's is
    printtarg -i in data/parameters.yaml. The group order is taken from the
    first, so the two must agree."""
    params = yaml.safe_load((ROOT / "data" / "parameters.yaml").read_text(
        encoding="utf-8"))
    choices = next(p["choices"] for p in params["parameters"]["printtarg"]
                   if p.get("flag") == "-i")
    assert choices == list(INSTRUMENT_LABELS)


def test_every_preset_list_walks_that_order(tab, settings, qapp):
    """The pulldown, the Built-in presets list, the gear window, its CSV,
    "Compare with profile", the verification window's rows and the table of
    scripts/make_preset_defaults.py."""
    settings.set(cp.PAPER_FILTER_KEY, False)
    tab._apply_preset_collapse()
    # "Select preset": its group headings in order
    cb = tab._preset_combo
    heads = [cb.itemData(r, cb.GROUP_ROLE) for r in range(cb.count())
             if cb.itemData(r, cb.GROUP_ROLE)]
    assert _unique(heads) == EXPECTED
    # the Built-in presets list, the gear window
    assert [h for h, _e in tab._curated_dialog_groups()] == EXPECTED
    # "Compare with profile" and every list built on preset_dropdown_groups
    assert [h for h, _e in TC.preset_dropdown_groups({})][1:] == EXPECTED
    # the facts the CSV and make_preset_defaults.py --table are written from
    facts = TC.builtin_preset_facts()
    assert _unique([f["group"] for f in facts]) == EXPECTED
    buf = io.StringIO(newline="")
    cp.write_table(buf, facts)
    names = {f["key"]: f["group"] for f in facts}
    rows = list(csv.reader(io.StringIO(buf.getvalue())))
    keys_in_file = [c for r in rows for c in r if c in names]
    assert _unique([names[k] for k in keys_in_file]) == EXPECTED
    # "Which presets can be used for verification?"
    vrows = TC.verification_preset_rows(settings)
    assert _unique([r.group for r in vrows if r.builtin]) == EXPECTED


def test_a_paper_change_after_loading_lists_the_new_paper_and_keeps_the_loaded(
        tab, settings, qapp):
    """Knut, 5833490026, point 1: after a paper change the filtered list
    shows the new paper's presets; the loaded preset stays loaded and
    visible in "Select preset" until another is chosen.

    MUTATION: filter the current row too (red: the loaded preset vanishes);
    stop re-filtering on a paper change (red: the old paper's presets stay)."""
    settings.set(cp.PAPER_FILTER_KEY, True)
    tab._switch_mode("manual")
    tab._set_manual_value("printtarg", "-p", "A3")
    qapp.processEvents()
    cb = tab._preset_combo
    view = cb.view()
    scanner = {x for h, e in TC.BUILTIN_PRESET_GROUPS if h == "Scanner"
               for _c, _o, x in e}

    def live_papers():
        return {TC.builtin_preset_paper(cb.itemData(r))
                for r in range(cb.count())
                if not view.isRowHidden(r)
                and cb.itemData(r) in TC.BUILTIN_PRESET_KEYS
                and cb.itemData(r) not in scanner
                and cb.itemData(r) != cb.currentData()}
    # the paper change alone refilters the list, live
    assert live_papers() == {"A3"}
    tab._set_manual_value("printtarg", "-p", "Letter")
    qapp.processEvents()
    assert live_papers() == {"Letter"}
    tab._set_manual_value("printtarg", "-p", "A3")
    qapp.processEvents()
    a3 = next(k for h, e in TC.BUILTIN_PRESET_GROUPS if h != "Scanner"
              for _c, _o, k in e if TC.builtin_preset_paper(k) == "A3")
    cb.setCurrentIndex(cb.findData(a3))
    tab._set_manual_value("printtarg", "-p", "A4")
    qapp.processEvents()
    # with a preset loaded, the list moves to A4 all the same
    assert live_papers() == {"A4"}
    tab._reveal_current_preset_group()
    assert cb.currentData() == a3
    assert not view.isRowHidden(cb.currentIndex())
    tab._open_preset_groups().update(h for h, _e in TC.BUILTIN_PRESET_GROUPS)
    tab._apply_preset_collapse()
    shown = [cb.itemData(r) for r in range(cb.count())
             if not view.isRowHidden(r) and isinstance(cb.itemData(r), str)
             and cb.itemData(r) in TC.BUILTIN_PRESET_KEYS]
    others = [k for k in shown if k != a3 and not any(
        k in {x for _c, _o, x in e} for h, e in TC.BUILTIN_PRESET_GROUPS
        if h == "Scanner")]
    assert others and all(TC.builtin_preset_paper(k) == "A4" for k in others)
    # another preset chosen: the A3 one leaves the list at the next opening
    cb.setCurrentIndex(cb.findData(others[0]))
    tab._reveal_current_preset_group()
    assert view.isRowHidden(cb.findData(a3))
