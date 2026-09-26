"""K48 (Knut, #182 5840677938 and 5840692243, beta 43): the preset lists and
the gear window, B8-1237 to B8-1243.

* B8-1237: a group with presets on the paper and none ticked shows its heading
  and "▸ N more presets" (B8-1227's listing them directly is withdrawn);
  pinned in ``test_b8_1221_the_filter_reads_the_paper_on_screen.py``.
* B8-1238: Custom lists every custom-size built-in whatever the W x H boxes
  say, never the paper before (Knut's screenshot: Custom 210 x 297 showing
  A3 Landscape's lists, beta 43's B8-1222).
* B8-1239: the gear window's help states the rule for when a preset shows.
* B8-1240: the gear window's two ⓘ are the app's flat ⓘ: the style sheets
  draw it by the object name ``tooltip_btn``, which this window used to
  replace with names of its own, so they were drawn as framed buttons.
* B8-1241: Scanner is filtered like every other group (Knut's ruling of
  2026-09-25: *"I also think the Scanner presets now should obey the same
  filtering according to paper size."*).

MUTATIONS, each red here: rename either ⓘ again (B8-1240); exempt Scanner in
``paper_filter_groups`` or in ``_mark_preset_group_rows`` (B8-1241); put
B8-1227's rule back in either list (B8-1237, with the B8-1221 file); put
"The Scanner presets are always shown" back into the paper filter's help
(B8-1239). Reading printtarg's hidden Paper again (B8-1238's cause) is red in
``test_b8_1221_the_filter_reads_the_paper_on_screen.py``, not here: the Custom
tests below choose the paper where a person does, and B8-1223 keeps the hidden
Paper in step with that choice.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import core.curated_presets as cp                               # noqa: E402
from ui.tabs import tab_chart as TC                             # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCANNER = next(h for h, _e in TC.BUILTIN_PRESET_GROUPS if h == "Scanner")


def _named_papers() -> set:
    """The named entries of Manual's Paper field, read from its definition
    (``data/parameters.yaml``), not from the filter's ``paper_class``: the
    expected lists must not come from the code under test (beta 44
    challenge F1, B8-1260)."""
    import yaml
    root = Path(__file__).resolve().parents[1]
    data = yaml.safe_load((root / "data" / "parameters.yaml").read_text(
        encoding="utf-8"))
    return next({c for c in p["choices"] if c != "custom"}
                for p in data["parameters"]["printtarg"]
                if p.get("flag") == "-p")


_NAMED = _named_papers()


def _on(preset_paper, sel: str) -> bool:
    """Whether a preset on *preset_paper* belongs to the Paper field entry
    *sel* ("custom" for Custom), judged without the filter's functions."""
    p = str(preset_paper or "")
    return (p if p in _NAMED else cp.CUSTOM_PAPER) == sel


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


def _panel_paper(tab, code, dims=None):
    panel = tab._manual_layout_panel
    if dims:
        panel.custom_w.setValue(dims[0])
        panel.custom_h.setValue(dims[1])
    panel.paper.setCurrentIndex(panel.paper.findData(code))


def _expected(settings, sel):
    """(heading, ticked keys, count under the arrow) for every group the rule
    lists on the Paper field entry *sel*: every group filtered, Scanner too."""
    shown = cp.shown_keys(settings, TC.BUILTIN_PRESET_KEYS)
    out = []
    for h, es in TC.BUILTIN_PRESET_GROUPS:
        keys = [k for *_x, k in es
                if _on(TC.builtin_preset_paper(k), sel)]
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


# ---------------------------------------------------------------------------
# B8-1241: Scanner is filtered like every other group
# ---------------------------------------------------------------------------

def test_a3_landscape_lists_no_scanner_preset(tab, settings, qapp):
    """The addendum's own check: A3 Landscape shows no A4 or Letter scanner
    preset, in either list."""
    _panel_paper(tab, "420x297")
    qapp.processEvents()
    exp = _expected(settings, "420x297")
    assert SCANNER not in [h for h, *_ in exp]
    assert _pulldown(tab) == exp
    assert _popup(tab) == exp


def test_a4_landscape_lists_only_its_own_scanner_presets(tab, settings, qapp):
    _panel_paper(tab, "A4R")
    qapp.processEvents()
    exp = _expected(settings, "A4R")
    scanner = dict((h, (t, n)) for h, t, n in exp)[SCANNER]
    assert sum(1 for _ in scanner[0]) + scanner[1] == len(
        [k for *_x, k in dict(TC.BUILTIN_PRESET_GROUPS)[SCANNER]
         if TC.builtin_preset_paper(k) == "A4R"])
    assert _pulldown(tab) == exp
    assert _popup(tab) == exp


# ---------------------------------------------------------------------------
# B8-1238: Custom, whatever the boxes say, never the paper before
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dims", [(210, 297), (100, 150), (500, 500),
                                  (420, 297)])  # B8-1260: A3 L's own size
def test_custom_after_a3_landscape_lists_the_custom_size_presets(
        tab, settings, qapp, dims):
    """Knut's screenshot: A3 Landscape, then Custom 210 x 297 (an A4's size),
    and the Built-in presets list still showed A3 Landscape's groups. Custom
    is one class whatever its size: every custom-size built-in, ticked ones
    directly, the rest under the arrow; never A4's and never A3 Landscape's."""
    _panel_paper(tab, "420x297")
    qapp.processEvents()
    _panel_paper(tab, "__custom__", dims)
    qapp.processEvents()
    assert tab._preset_paper_selected() == cp.CUSTOM_PAPER
    exp = _expected(settings, cp.CUSTOM_PAPER)
    assert exp and exp != _expected(settings, "420x297") \
        and exp != _expected(settings, "A4")
    assert _pulldown(tab) == exp
    assert _popup(tab) == exp


# ---------------------------------------------------------------------------
# B8-1239 and B8-1240: the gear window
# ---------------------------------------------------------------------------

@pytest.fixture()
def gear(tab, qapp):
    from ui.dialogs.builtin_presets_shown_dialog import (
        BuiltinPresetsShownDialog)
    dlg = BuiltinPresetsShownDialog(
        tab._curated_dialog_groups(), set(), tab, paper_filter=True)
    yield dlg
    dlg.deleteLater()
    qapp.processEvents()


def test_the_gear_windows_info_icons_are_the_apps_flat_icons(gear):
    """The style sheets draw the flat ⓘ by ``QToolButton#tooltip_btn``; a
    renamed icon falls back to a framed tool button (Knut's screenshot)."""
    from ui.tooltip_button import TooltipButton
    icons = gear.findChildren(TooltipButton)
    assert len(icons) == 2
    assert {id(gear._help), id(gear._paper_filter_help)} == {
        id(i) for i in icons}
    for icon in icons:
        assert icon.objectName() == "tooltip_btn"


def test_no_window_renames_an_info_icon():
    """Every ⓘ in the app keeps the name its look is keyed on. A scan of the
    source: ``x = TooltipButton(...)`` followed by ``x.setObjectName(``."""
    bad = []
    for p in (ROOT / "ui").rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        for m in re.finditer(r"([\w\.]+)\s*=\s*TooltipButton\(", src):
            var = m.group(1)
            if var == "btn":
                continue            # parameter_widget's generic name
            if re.search(re.escape(var) + r"\.setObjectName\(", src):
                bad.append(f"{p.relative_to(ROOT)}: {var}")
    assert not bad, bad


def test_the_gear_help_states_the_rule(gear):
    window = gear._help.dialog_body()
    box = gear._paper_filter_help.dialog_body()
    for text in (window, box):
        assert "always shown" not in text
        assert "Scanner" in text
        assert "none of them ticked" in text
        assert "“▸ N more presets” only" in text
        assert "Custom paper" in text
        assert "whatever the width and height boxes say" in text
        assert "—" not in text
    assert "Paper filter off" in window
    assert "A ticked preset for that paper is listed directly" in window


def test_the_german_help_is_by_hand_and_says_the_same():
    import json
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    bodies = [v for k, v in de.items()
              if k.startswith(("“Settings for built-in presets” chooses",
                               "While this box is ticked (the default)"))]
    assert len(bodies) == 2
    for v in bodies:
        assert "auch Scanner" in v
        assert "keines angehakt" in v
        assert "immer angezeigt" not in v
        assert " du " in v or "Klicke" in v or "Nimm" in v    # Du-Form
