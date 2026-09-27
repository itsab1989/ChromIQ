"""Beta 45 challenge 2: the texts.

B8-1471 (F2): Red River "ColorMunki · A4-2052p-9pages" said "the same ninth
of all 8 pages" while its Pages column said 9: the report leaves page 9 out
(its patches cover too little of the page) and the sentence did not say so.
It now counts the pages read OF the chart's pages and names each page left
out in the report's own words.

B8-1473 (F5): the R18 and R19 demo presets (printtarg at -a 1.5, a patch
scale the fast page table has no measurement for) showed an empty Pages
cell. The window lays them out for the evenness rows anyway, and now takes
the count from that layout.

B8-1474 (Knut, #182 5853818821): the Build Profile tab's help with
calibration on puts the advice for someone new EARLY, so they can decide
whether to read on.

B8-1475 (F4, b): the beta 45 changelog states B8-1461's known limit, and
says the measurement-windows help is translated into German, not "translated".
"""
import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.dialogs import preset_verification_dialog as PVD  # noqa: E402
from workflow import measurement_report as MR  # noqa: E402
from workflow import preset_eligibility as PE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- B8-1471 ----------------------------------------------------------------

def test_the_report_cell_carries_the_pages_it_leaves_out():
    """`row_values` puts the report's own left-out lists into the cell."""
    ev = {"eligible": True, "pairwise": 0.4, "from_mean": 0.3,
          "noise_pairwise_p95": 0.9, "noise_from_mean_p95": 0.5,
          "counts": [160, 240, 160, 224, 336, 224, 160, 240, 160],
          "pages_used": [1, 2, 3, 4, 5, 6, 7, 8],
          "pages_small": [], "pages_uncovered": [9],
          "pages_unmeasured": [], "coverage": [0.8] * 8 + [0.31]}
    cells = MR.row_values({"evenness": ev})
    cell = cells["uniformity_sd"]
    assert cell["area_pages"] == 8
    assert cell["area_pages_left"] == [["uncovered", 9, 0.31]]


def test_red_rivers_nine_page_sentence_counts_eight_of_nine():
    cell = {"area_effective": 206, "area_pages": 8, "area_min": 160,
            "area_max": 336, "area_pages_left": [["uncovered", 9, 0.31]]}

    class _Lim:
        is_numeric = True
        number = 0.5
    c = PE.noise_shortfall("uniformity_sd", cell, _Lim())
    assert c.pages == 8 and c.left_out == (("uncovered", 9, 0.31),)
    line = PVD.noise_count_line(*c)
    assert "all 8 pages" not in line, line
    assert "the same ninth of 8 of the chart's 9 pages together" in line, line
    assert "The patches on page 9 cover 31.0 % of the page" in line, line
    assert "so it is not counted." in line, line


@pytest.mark.parametrize("left,words", [
    ((("small", 3, None),), "Page 3 has fewer than 9 strips or rows"),
    ((("small", 3, None), ("small", 4, None)),
     "Pages 3, 4 have fewer than 9 strips or rows"),
    ((("unmeasured", 5, None),), "Where the patches sit on page 5"),
    ((("uncovered", 6, 0.2), ("uncovered", 7, 0.1)),
     "The patches on pages 6, 7 cover less than"),
])
def test_each_reason_is_the_reports_own_sentence(left, words):
    line = PVD.noise_count_line(100, 200, 2, 100, 100, left)
    assert words in line, line
    assert f"of 2 of the chart's {2 + len(left)} pages" in line, line


def test_a_chart_with_every_page_read_keeps_all():
    line = PVD.noise_count_line(100, 200, 3, 100, 100, ())
    assert "the same ninth of all 3 pages together" in line


def test_the_new_sentences_are_german_by_hand():
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    keys = [k for k in de if "of the chart's {total} pages" in k]
    assert len(keys) == 2
    for k in keys:
        assert de[k] != k and "von {pages} der {total} Seiten" in de[k]
        assert "—" not in k and "—" not in de[k]


# ---- B8-1473 ----------------------------------------------------------------

def test_a_demo_preset_the_page_table_cannot_count_takes_its_layouts(
        qapp, tmp_path, monkeypatch):
    """R16's FAIL preset: printtarg at -a 0.80. `_preset_sheet_count` says 0
    (no measured table for that scale); the window's own layout says 1.
    (It was R19's at -a 1.5 until R19 left the pack with Knut's filter,
    #182 5855780690.)"""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_verification_preset_demos as D
    from core.settings import AppSettings
    from ui.tabs.tab_chart import _preset_sheet_count
    from workflow.preset_layout import layout_for_user_preset
    built = D.build(tmp_path / "presets")
    demo, chart = next((d, c) for d, c in built
                       if d.name.startswith("Verify R16 FAIL"))
    data = D.payload(True, demo.scale)
    s = AppSettings()
    assert _preset_sheet_count(data, chart, s) == 0     # the cause
    row = PVD.PresetRow(group="Custom presets", label=demo.name, chart=chart,
                        patches=PE.patch_count(chart), pages=0,
                        builtin=False, key=demo.name,
                        recipe=layout_for_user_preset(data, s.get))
    PE._evenness_grid_for(Path(chart), row.recipe, True)  # laid out
    row.assessment = PE.assess(chart, PE.ANY_REPORT_TYPE, PE.ALL_METRICS,
                               recipe=row.recipe)
    PVD._count_laid_out_pages(row)
    assert row.pages == 1
    dlg_cols = PVD.PresetVerificationDialog._columns(None, row)
    assert dlg_cols[2] == "1"


def test_a_layout_still_being_worked_out_leaves_the_cell(tmp_path):
    row = PVD.PresetRow(group="g", label="x", chart=tmp_path / "x.ti1",
                        patches=10, pages=0, builtin=False,
                        recipe=None, assessment=PE.Assessment((), (), ()))
    PVD._count_laid_out_pages(row)
    assert row.pages == 0


def test_the_count_never_starts_a_layout(tmp_path, monkeypatch):
    """A layout not yet worked out is waited for, not started here."""
    row = PVD.PresetRow(group="g", label="x", chart=tmp_path / "x.ti1",
                        patches=10, pages=0, builtin=False,
                        recipe={"printtarg": True},
                        assessment=PE.Assessment((), (), ()))
    monkeypatch.setattr(PE, "layout_is_ready", lambda *_a: False)
    monkeypatch.setattr(PE, "_evenness_grid_for",
                        lambda *_a, **_k: pytest.fail("a layout was asked"))
    PVD._count_laid_out_pages(row)
    assert row.pages == 0


def test_the_window_counts_the_pages_where_it_assesses():
    import inspect
    src = inspect.getsource(PVD.PresetVerificationDialog)
    assert src.count("_count_laid_out_pages(row)") == 2


# ---- B8-1474 ----------------------------------------------------------------

def test_the_newcomer_advice_comes_early_in_the_calibration_help():
    from ui.tabs.tab_profile import _TOOLTIP_BODY_CAL as body
    paras = body.split("\n\n")
    assert paras[0].startswith("Calibration is an optional extra")
    assert paras[1].startswith("New to this")
    assert "turn calibration mode off in Preferences" in paras[1]
    assert "read on" in paras[1]
    # said once, not again at the end
    assert body.count("calibration mode off") == 1
    assert paras[-1].startswith("In short:")
    assert "—" not in body


def test_the_calibration_help_is_german_by_hand_and_du():
    from ui.tabs.tab_profile import _TOOLTIP_BODY_CAL as body
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    g = de[body]
    paras = g.split("\n\n")
    assert paras[1].startswith("Neu hier")
    assert "Schalte den Kalibrierungsmodus" in paras[1]
    assert "lies weiter" in paras[1]
    assert g.count("Kalibrierungsmodus") == 1
    assert " Sie " not in g and "—" not in g
    for code in ("es", "fr", "nl", "zh_CN"):
        cat = json.loads((ROOT / f"data/i18n/{code}.json").read_text(
            encoding="utf-8"))
        assert body in cat, code


# ---- B8-1475 ----------------------------------------------------------------

def _beta45() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = text.index("## v4.3.0-beta.45")
    return text[start:text.index("\n## v", start + 5)]


def test_the_changelog_states_the_loaded_set_limit():
    entry = _beta45()
    assert ("a beta 44 project whose patch set was loaded with the layout "
            "engine off keeps its patches, but may lay them out on a "
            "different sheet") in entry


def test_the_changelog_says_which_language_the_help_is_in():
    entry = _beta45()
    assert "help is translated into German." in entry
    assert "help is translated.\n" not in entry
