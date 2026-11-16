"""The Measure tab's "Spectral filter type (-F)" list says what each entry
is, M number first (4.3.42, the owner's ruling of 2026-11-16).

It used to read "None (M0)", "D50 (M1)", "D65", "UV Cut (M2)",
"Polarizing (M3)" in a fixed 130 px box, in English in every language. Now
every entry goes through tr(), the box is as wide as its longest entry, and
nothing else moves: chartread is given the same -F values, D50 (M1) is still
the entry selected when the row is switched on, and settings and presets,
which store the value and never the text, load as before.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from workflow.measurement_condition import (FILTER_CONDITIONS,  # noqa: E402
                                            filter_choice_label,
                                            filter_choices)

OLD = [("n", "None (M0)"), ("5", "D50 (M1)"), ("6", "D65"),
       ("u", "UV Cut (M2)"), ("p", "Polarizing (M3)")]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    t._ti1_path = tmp_path / "chart.ti1"
    return t


def _filter(opts):
    (o,) = [o for o in opts if o.key == "filter"]
    return o


def test_the_values_and_their_order_are_chartreads_as_before():
    assert [c for c, _ in filter_choices()] == [c for c, _ in OLD]
    assert [lbl for _, lbl in filter_choices()] == [
        "M0: no filter (lamp as it is)", "M1: D50 daylight (with UV)",
        "D65 daylight filter", "M2: UV cut (no UV)", "M3: polarising filter"]
    # the M number an entry names is the condition chartread measures in
    for code, lbl in filter_choices():
        cond = FILTER_CONDITIONS.get(code)
        if cond:
            assert lbl.startswith(f"{cond}: ")
        else:                                       # D65: no ISO condition
            assert lbl[:2] not in ("M0", "M1", "M2", "M3")


def test_every_entry_is_translated(monkeypatch):
    src = inspect.getsource(filter_choices)
    for _, lbl in filter_choices():
        assert f'tr("{lbl}")' in src
    monkeypatch.setattr("workflow.measurement_condition.tr",
                        lambda s: f"<{s}>")
    assert filter_choice_label("5") == "<M1: D50 daylight (with UV)>"
    assert filter_choice_label("X") == "X"


def test_the_row_sends_the_same_minus_f_and_keeps_its_default(tab):
    for opts in (tab._m_chartread_opts, tab._chartread_opts):
        if not any(o.key == "filter" for o in opts):
            continue
        o = _filter(opts)
        combo = o.widget
        assert [combo.itemData(i) for i in range(combo.count())] == \
            ["n", "5", "6", "u", "p"]
        assert combo.currentData() == "5"           # D50 (M1), as before
        assert o.build_args() == []                 # row off: no -F at all
        o.checkbox.setChecked(True)
        for i, (code, _) in enumerate(OLD):
            combo.setCurrentIndex(i)
            assert o.build_args() == ["-F", code]


def test_the_box_is_wide_enough_for_its_longest_entry(tab):
    o = _filter(tab._m_chartread_opts)
    combo = o.widget
    combo.ensurePolished()
    fm = combo.fontMetrics()
    widest = max(fm.horizontalAdvance(combo.itemText(i))
                 for i in range(combo.count()))
    assert combo.sizeHint().width() > widest
    assert combo.minimumWidth() >= 130


def test_a_saved_preset_and_saved_settings_load_the_same_entry(tab):
    o = _filter(tab._m_chartread_opts)
    data = tab._m_collect_preset_data()
    for code, _ in OLD:
        data = dict(data, filter_enabled=True, filter_value=code)
        o.widget.setCurrentIndex(0 if code != "n" else 1)
        tab._m_apply_preset_data(data)
        assert o.widget.currentData() == code
        assert o.build_args() == ["-F", code]
    # a preset written before 4.3.42 holds the value only, as now
    assert tab._m_collect_preset_data()["filter_value"] == "p"


def test_messages_name_the_entry_as_the_list_shows_it(tab):
    assert tab._filter_label("u") == "M2: UV cut (no UV)"
    from workflow.fwa_gate import _condition_reason
    assert "\u201cM0: no filter (lamp as it is)\u201d" in _condition_reason("M1")


def test_the_entries_and_the_fwa_line_have_every_language():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "data" / "i18n"
    fwa = ("To use FWA compensation, measure the chart again with the "
           "Measure tab's \u201cSpectral filter type (-F)\u201d set to "
           "\u201c{choice}\u201d, or switched off.")
    for f in sorted(root.glob("*.json")):
        cat = json.loads(f.read_text(encoding="utf-8"))
        for _, lbl in filter_choices():
            assert cat.get(lbl), (f.name, lbl)
        assert "{choice}" in cat[fwa] and "None (M0)" not in cat[fwa], f.name


# ── review 2 (2026-11-16): the row's own help names the entries the list shows,
# and says which instruments accept which, as the vendored ArgyllCMS does ──

def test_the_rows_help_names_the_entries_and_not_the_old_labels(tab):
    o = _filter(tab._m_chartread_opts)
    body = o.tooltip_body
    for _, lbl in filter_choices():
        assert f"“{lbl}”" in body, lbl
    for old in ("None  (M0", "D50 (M1) is selected", "Polarizing filter (M3)"):
        assert old not in body, old
    # which instruments accept which, and what happens on one that does not
    assert "the i1Pro 3 accepts M0, M1 and M2 (M3 only if it has a polariser)" in body
    assert "the Spectrolino accepts M0, the D65 daylight filter, M2 and M3" in body
    assert "i1Pro 2 and the ColorMunki, accept none of them" in body
    assert "Setting requested filter not supported by instrument" in body


def test_the_accepted_entries_are_what_the_vendored_argyll_does():
    """The help's claims, held against the source they were read from."""
    from pathlib import Path
    il = Path(__file__).resolve().parents[1] / "native" / "instlib"
    if not il.is_dir():
        pytest.skip("vendored ArgyllCMS sources not present")
    cr = (il / "chartread.c.orig").read_text(encoding="latin-1")
    assert "inst_opt_set_filter, fe)) != inst_ok" in cr
    assert "Setting requested filter not supported by instrument" in cr
    handlers = sorted(p.name for p in il.glob("*.c")
                      if "inst_opt_set_filter" in p.read_text(encoding="latin-1"))
    assert handlers == ["i1pro3.c", "ss.c"]
    p3 = (il / "i1pro3.c").read_text(encoding="latin-1")
    sw = p3[p3.index("if (ot == inst_opt_set_filter)"):]
    sw = sw[:sw.index("inst_stat_get_filter")]
    for case in ("filter_none", "filter_D50", "filter_UVCut"):
        assert f"case inst_opt_{case}:" in sw
    assert "inst_opt_filter_D65" not in sw
    pol = sw[sw.index("case inst_opt_filter_pol:"):]
    assert pol[len("case inst_opt_filter_pol:"):].lstrip().startswith(
        "/* M3 */\n\t\t\t\tif (m->capabilities & I1PRO3_CAP_POL)")
    ss = (il / "ss.c").read_text(encoding="latin-1")
    sw = ss[ss.index("m == inst_opt_set_filter"):]
    sw = sw[:sw.index("inst_opt_set_custom_filter")]
    for case in ("filter_none", "filter_pol", "filter_D65", "filter_UVCut"):
        assert f"case inst_opt_{case}:" in sw
    assert "inst_opt_filter_D50" not in sw
