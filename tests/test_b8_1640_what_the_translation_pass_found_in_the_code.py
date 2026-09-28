"""B8-1640 to B8-1644: what the 4.3.0 translation pass found outside the
catalogues.

* B8-1640: the paper lists showed "Portrait"/"Landscape" in English in every
  language; the English table stays for names, stamps and parsers.
* B8-1641: "3 measurements" / "2 profile runs" put a counted noun after a
  number, which Polish, Russian and Ukrainian cannot inflect with only a
  singular and a plural; they are label values now.
* B8-1642: the relayout gap labels shared ``tr("H")`` with the Height fields.
* B8-1643: M-CR30-STOCK-READER named a "Chart-reading engine" setting the
  window no longer has (it is a checkbox).
* B8-1644: the results-table check called every break between two Japanese or
  Chinese characters a broken word.
"""
from __future__ import annotations

import pytest


# ---- B8-1640 --------------------------------------------------------------
def test_the_paper_list_keeps_its_english_table():
    from data.patch_db import PAPER_LABELS
    assert PAPER_LABELS["A4"].endswith(" Portrait")
    assert PAPER_LABELS["A4R"].endswith(" Landscape")


def test_the_orientation_word_is_translated_where_it_is_shown():
    from core.i18n import tr
    from data.patch_db import paper_display_label
    assert paper_display_label("A4") == (
        "A4 (210 × 297 mm) " + tr("Portrait"))
    assert paper_display_label("A4R") == (
        "A4 (297 × 210 mm) " + tr("Landscape"))
    # a row with no orientation word is the table's own
    assert paper_display_label("Legal") == "Legal (8.5 × 14\")"


def test_every_language_translates_the_two_words():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "data" / "i18n"
    de = json.loads((root / "de.json").read_text(encoding="utf-8"))
    assert de["Portrait"] == "Hochformat"
    assert de["Landscape"] == "Querformat"


def test_the_paper_combos_carry_the_code_not_the_label():
    """Nothing that reads the paper back may see the translated word."""
    import inspect
    import ui.dialogs.ti2_relayout_dialog as rd
    import ui.tabs.tab_chart as tc
    src = inspect.getsource(tc.TabChart._rebuild_paper_combo)
    assert "addItem(paper_display_label(size), size)" in src
    assert "_paper_row_label(code), code)" in inspect.getsource(rd)


# ---- B8-1641 --------------------------------------------------------------
def test_no_counted_noun_follows_a_number_in_the_report_window():
    import inspect
    import ui.dialogs.measurement_report_dialog as mrd
    src = inspect.getsource(mrd)
    for old in ('tr("measurement") if n == 1 else tr("measurements")',
                'tr("profile run") if n == 1 else tr("profile runs")'):
        assert old not in src
    assert 'tr("Measurements: {n}")' in src
    assert 'tr("Profile runs: {n}")' in src


# ---- B8-1642 --------------------------------------------------------------
def test_the_gap_letters_read_h_and_v_in_english():
    from ui.dialogs.ti2_relayout_dialog import _gap_letter
    assert _gap_letter("H (horizontal gap)", "H (horizontal gap)", "H") == "H"
    assert _gap_letter("Horiz.", "H (horizontal gap)", "H") == "Horiz."


def test_the_gap_labels_do_not_share_the_height_key():
    import inspect
    import ui.dialogs.ti2_relayout_dialog as rd
    src = inspect.getsource(rd)
    assert 'QLabel(tr("H"), self)' not in src
    assert 'tr("H (horizontal gap)")' in src
    assert 'tr("V (vertical gap)")' in src


# ---- B8-1643 --------------------------------------------------------------
def test_the_cr30_message_names_the_checkbox_the_window_has():
    from workflow.measurement_messages import M_CR30_STOCK_READER
    body = M_CR30_STOCK_READER.render()[1]
    assert "“ChromIQ chart-reading engine”" in body
    assert "“Chart-reading engine” set to" not in body
    import inspect
    import ui.dialogs.settings_dialog as sd
    assert 'tr("ChromIQ chart-reading engine")' in inspect.getsource(sd)


# ---- B8-1644 --------------------------------------------------------------
def test_a_break_between_japanese_or_chinese_characters_is_no_cut_word():
    from ui.dialogs.measurement_report_dialog import _is_word_cut
    for prev, nxt in (("領", "域"), ("の", "間"), ("区", "域"), ("、", "九"),
                      ("パ", "ッ"), ("E", "、"), ("0", "九"), ("）", "の")):
        assert not _is_word_cut(prev, nxt), (prev, nxt)


def test_a_latin_word_cut_inside_a_japanese_text_still_is():
    """MUTATION, proven red: let `_breaks_anywhere` answer True for every
    character, and the cut inside "recommended" passes."""
    from ui.dialogs.measurement_report_dialog import _is_word_cut
    assert _is_word_cut("e", "n")          # "recomm|ended" in a ja label
    assert _is_word_cut("9", "5")          # "P9|5"
    assert not _is_word_cut(" ", "r")
    assert not _is_word_cut("/", "M")


def test_the_full_japanese_and_chinese_labels_are_back():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "data" / "i18n"
    ja = json.loads((root / "ja.json").read_text(encoding="utf-8"))
    zh = json.loads((root / "zh_CN.json").read_text(encoding="utf-8"))
    assert ja["Average ΔCh, grey balance of the grey ramp"] == (
        "平均 ΔCh、グレーランプのグレーバランス")
    assert ja["Maximum ΔH*ab, cyan, magenta and yellow solids"] == (
        "最大 ΔH*ab、シアン・マゼンタ・イエローのベタ")
    assert zh["Maximum ΔE00, between two of the nine sheet areas"] == (
        "最大 ΔE00，印张九个区域中任意两个区域之间")
