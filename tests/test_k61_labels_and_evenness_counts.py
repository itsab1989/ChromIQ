"""K61 (Knut, #182 5851645723, on beta 44): two findings and what they led to.

1. **A metric's name, quoted, is exactly the name the Report Limits window
   shows.** *"The 'within gamut' is added in a way that it looks like it is
   part of the metric label ... Make sure labels match, and added information
   is clearly separated from the labels."* So on a split report the words
   follow the name in brackets, outside the quotes: “Average ΔE00, all
   patches” (within gamut).
2. **"Too few patches in each ninth" on a page of 72 in every ninth.** Under
   the ISO 12647-7:2016 value (0.5 between two areas) a typical print's
   noise on that page is 0.87: the rule was right and the sentence was not.
   The window now names both numbers, the patches in a ninth and about how
   many the limit takes.
3. What the systematic check of every requirement found on the way
   (`scripts/k61_threshold_matrix.py`): printtarg prints, and writes into
   the .ti2, device values rounded to its page image, and its padding
   patches (id 0) are no patch of any area.

Every test names the mutation it was proven red against.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                       # noqa: E402

from core import i18n                                          # noqa: E402
from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DE = json.loads((ROOT / "data" / "i18n" / "de.json").read_text("utf-8"))
ARGYLL = Path("/Applications/Argyll/bin")

#: a quoted stretch of text, in the report's quotation marks (English “…”,
#: German „…“) or in plain ones
_QUOTED = re.compile(r"[“„\"]([^”“\"]*)[”“\"]")


def _names_a_metric(text: str) -> bool:
    """Whether a quoted stretch is written as a metric's name: it carries a
    Δ unit and more than the unit ("ΔE" alone is the unit)."""
    return "Δ" in text and ", " in text


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# 1. the names
# ---------------------------------------------------------------------------
def test_every_quoted_metric_name_in_the_source_is_a_report_limits_label():
    """Every user-facing string, English and German: a quoted metric name is
    a label of the Report Limits window, word for word.

    MUTATION, proven red: restore “Average ΔE00, all patches within gamut”
    in the Dictionary entry of `ui/dialogs/welcome_dialog.py`."""
    from scripts.i18n_extract import extract_keys
    en = {r.label for r in CS.ROWS}
    de = {DE.get(r.label, r.label) for r in CS.ROWS}
    bad = []
    for key in extract_keys():
        for m in _QUOTED.finditer(key):
            if _names_a_metric(m.group(1)) and m.group(1) not in en:
                bad.append(("en", m.group(1), key[:70]))
        for m in _QUOTED.finditer(DE.get(key, "")):
            if _names_a_metric(m.group(1)) and m.group(1) not in de:
                bad.append(("de", m.group(1), key[:70]))
    assert not bad, bad


def test_within_gamut_follows_the_name_and_is_never_part_of_it():
    """MUTATION, proven red: `IN_GAMUT_LABELS` built as
    ``f"{label} within gamut"``."""
    for rid in CS.WITHIN_GAMUT_ROWS:
        label = CS.ROW_BY_ID[rid].label
        assert CS.row_name(rid, True) == label + " (within gamut)"
        assert CS.row_name(rid, False) == label
    assert DE["{metric} (within gamut)"] == "{metric} (im Gamut)"
    # no translation key carries a name with the words glued in
    assert not [k for k in DE if re.search(r"[^(]within gamut", k)
                and "ΔE00," in k], "a glued within-gamut name is still a key"


def _split_report_text(tmp_path, qapp, lang):
    from tests.test_k31_metrics import _split
    from tests.test_trend_graphs_for_judged_metrics import _open
    i18n.set_language(lang)
    try:
        dlg = _open(tmp_path, qapp, CS.effective_limits("chromiq_default", {}))
        try:
            dlg._detail_check.setChecked(True)
            runs = _split(dlg._runs_for_report())
            body = dlg._report_body_html(runs, for_pdf=True)
            notes = []
            dlg._runs_for_report = lambda: runs
            for grp in [dlg._trend_de] + list(dlg._trend_groups.values()):
                notes += [n for n in dlg._trend_extras(grp)["line_notes"] if n]
            text = _html.unescape(re.sub(r"<[^>]+>", " ", body))
            return re.sub(r"\s+", " ", text + " " + " ".join(notes))
        finally:
            dlg.deleteLater()
    finally:
        i18n.set_language("en")


@pytest.mark.parametrize("lang", ["en", "de"])
def test_a_split_report_quotes_only_report_limits_labels(tmp_path, qapp, lang):
    """Knut's own report, rendered: Report Results, How to read, the notes,
    the Overview, the detailed chapters and every graph's limit-line
    sentences. Each quoted name is a Report Limits label, and "within gamut"
    only ever appears in brackets after one.

    MUTATION, proven red: `_quoted_row_name` returning
    ``_quoted(_within_gamut(name))`` (the words inside the quotes again)."""
    text = _split_report_text(tmp_path, qapp, lang)
    labels = {(DE.get(r.label, r.label) if lang == "de" else r.label)
              for r in CS.ROWS}
    quoted = [m.group(1) for m in _QUOTED.finditer(text)
              if _names_a_metric(m.group(1))]
    assert quoted, "the split report quoted no metric at all"
    assert [q for q in quoted if q not in labels] == []
    words = "im Gamut" if lang == "de" else "within gamut"
    loose = [text[max(0, m.start() - 50):m.end() + 5]
             for m in re.finditer(re.escape(words), text)
             if text[m.start() - 1:m.start()] != "("]
    assert not loose, loose
    # and it is there, after the closing quote, where a name is quoted
    close = "“" if lang == "de" else "”"
    assert f"{close} ({words})" in text


# ---------------------------------------------------------------------------
# 2. the evenness counts
# ---------------------------------------------------------------------------
def test_the_count_is_derived_from_the_noise_and_the_limit():
    """72 patches in every ninth against 0.5 between two areas: the model
    wants 238, whatever the chart (B8-1451; K61 said "about 220" off the
    chart's own random draw).

    MUTATION, proven red: ``need = have * noise / limit`` (linear)."""
    lim = CS.Limit.value(0.5)
    cell = {"area_effective": 72, "area_min": 72, "area_max": 72,
            "area_pages": 1}
    assert PE.noise_shortfall("uniformity_sd", cell, lim) == \
        PE.NoiseCount(72, 238, 1, 72, 72)
    assert PE.noise_shortfall("uniformity_sd", cell,
                              CS.Limit.none()) is None
    assert PE.noise_shortfall("uniformity_sd", {"area_min": 72}, lim) is None


def test_the_noise_falls_as_one_over_the_root_of_the_patches_in_a_ninth():
    """What `noise_shortfall` rests on, measured on the estimate itself:
    four times the patches in a ninth, half the noise, within 10 %.

    MUTATION, proven red: `evenness_from_residuals` dividing the area sums
    by the count squared."""
    def noise(n):
        g = MR.evenness_grid_from_layout([n], n, n * n,
                                         coverage=[{"coverage": 0.8}])
        rng = np.random.default_rng(MR.EVENNESS_SEED)
        b = MR.evenness_from_residuals(
            g, rng.normal(0, MR.EVENNESS_TYPICAL_SIGMA, (n * n, 3)),
            shuffles=MR.EVENNESS_ESTIMATE_SHUFFLES)
        return b["noise_pairwise_p95"], b["noise_from_mean_p95"]
    for small, big in ((18, 36), (24, 48), (45, 90)):
        a, b = noise(small), noise(big)
        for x, y in zip(a, b):
            assert 1.8 < x / y < 2.2, (small, big, x, y)


def test_the_window_names_both_numbers_not_too_few():
    """MUTATION, proven red: `reason_line` ignoring *counts*."""
    from ui.dialogs import preset_verification_dialog as PVD
    line = PVD.reason_line(MR.REASON_EVENNESS_NOISY_PAIRWISE, (72, 238))
    assert "holds 72 patches" in line and "at least 238" in line, line
    assert "Too few" not in line
    plain = PVD.reason_line(MR.REASON_EVENNESS_NOISY_PAIRWISE)
    assert "Too few" not in plain and "noise" in plain


def test_the_lever_and_the_help_say_no_fixed_patch_count():
    """"about 30" was true of a limit of 1.5 only.

    MUTATION, proven red: restore "about 30" in `_R_EVENNESS`."""
    for text in (CS._R_EVENNESS, CS._D_EVENNESS):
        assert "about 30" not in text and "270" not in text
    assert "the lower the limit, the more patches" in CS._R_EVENNESS


def _knuts_648():
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS
    p = next(x for x in KNUT_PRESETS
             if x.slug == "i1_w75_a4_648p_1page_portrait_w7_5mm")
    return Path(resource_path(p.ti1_asset)), dict(p.layout_recipe)


def test_knuts_648_page_under_iso_12647_7_and_chromiq_default(qapp):
    """Knut's case, through the window's own call: 24 strips by 27 rows, 72
    in every ninth, 69 % covered. Under ISO 12647-7:2016 values the pairwise
    row is withheld for the noise, with 72 and 238 (B8-1451); under ChromIQ
    default it is answered.

    MUTATION, proven red: `assess_rows` passing no limits to
    `evenness_withheld` (answered under ISO 12647-7 too)."""
    chart, recipe = _knuts_648()
    ev = PE._estimated_evenness(chart, recipe, True)
    assert ev["pages"] == [[24, 27]] and set(ev["counts"]) == {72}
    assert ev["coverage"][0] >= MR.EVENNESS_MIN_PAGE_COVERAGE
    iso = PE.assess(chart, MR.REPORT_TYPE_FULL, "iso_12647_7", recipe=recipe)
    assert dict(iso.missing).get("uniformity_sd") == \
        MR.REASON_EVENNESS_NOISY_PAIRWISE
    have, need, pages, low, high = iso.noise_count("uniformity_sd")
    assert (have, need, pages, low, high) == (72, 238, 1, 72, 72)
    assert "uniformity_de00_max_from_mean" in iso.answered
    cq = PE.assess(chart, MR.REPORT_TYPE_FULL, "chromiq_default",
                   recipe=recipe)
    assert "uniformity_sd" in cq.answered


# ---------------------------------------------------------------------------
# 3. what the printed sheet carries
# ---------------------------------------------------------------------------
def _printtarg_chart(tmp_path, levels):
    """A .ti1 of neutrals at *levels* and fillers, laid out by printtarg on
    an 8-bit A4 page."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_verification_preset_demos as GEN
    ti1 = tmp_path / "chart.ti1"
    patches = [(v, v, v) for v in levels] + GEN.fillers(75)
    GEN.write_ti1(ti1, patches)
    # write_ti1 writes the 16-bit levels; put the plain values back so the
    # 8-bit page is what rounds them
    text = ti1.read_text(encoding="utf-8")
    for v in levels:
        text = re.sub(rf"\b{GEN.printed(v):.5f}\b", f"{v:.5f}", text)
    ti1.write_text(text, encoding="utf-8")
    from workflow.preset_layout import printtarg_spec
    spec = printtarg_spec(["-ii1", "-pA4", "-t300", "-L", "-R", "182"],
                          ARGYLL)
    return ti1, spec


@pytest.mark.skipif(not (ARGYLL / "printtarg").is_file(),
                    reason="printtarg is needed to lay the chart out")
def test_the_window_judges_the_values_printtarg_prints(tmp_path):
    """A darkest neutral of exactly 10.0 is "black" in the .ti1, and is
    printed on an 8-bit page as 10.196, which the measurement carries and the
    report judges: not black. The window lays the preset out and says so.

    MUTATION, proven red: drop the ``laid`` override in `_perfect_print`
    (the window answers the grey rows)."""
    levels = (10.0, 22.0, 34.0, 46.0, 58.0, 70.0, 82.0, 100.0)
    ti1, spec = _printtarg_chart(tmp_path, levels)
    from workflow import preset_layout as PL
    grid = PL.grid_for(ti1, spec, wait=True)
    darkest = min(float(v[0]) for sid, v in grid["rgb"].items()
                  if max(v) - min(v) <= MR.GREY_SPREAD_TOL)
    assert darkest > MR.GREY_DARKEST_MAX, darkest
    values = PE.chart_row_values(ti1, spec, lay_out=True)
    assert values["grey_balance_neutral_ramp_avg"]["reason"] == \
        MR.REASON_NO_BLACK


@pytest.mark.skipif(not (ARGYLL / "printtarg").is_file(),
                    reason="printtarg is needed to lay the chart out")
def test_a_padding_patch_is_in_no_area(tmp_path):
    """printtarg pads a partial last strip with patches of id 0 (B8-407);
    no measurement carries them, so the page grid has none either.

    MUTATION, proven red: drop the `_is_padding_id` skip in `chart_grid`."""
    ti1, spec = _printtarg_chart(tmp_path, (0.0, 50.0, 100.0))
    folder = tmp_path / "laid"
    folder.mkdir()
    shutil.copyfile(ti1, folder / "c.ti1")
    subprocess.run([str(ARGYLL / "printtarg"), *spec["printtarg_argv"], "c"],
                   cwd=str(folder), capture_output=True, text=True,
                   encoding="utf-8", timeout=120, check=True)
    ti2 = folder / "c.ti2"
    assert re.search(r'^0 "', ti2.read_text(encoding="utf-8"), re.M), \
        "printtarg did not pad this chart, so the test proves nothing"
    grid = MR.chart_grid(ti2)
    assert "0" not in grid["slot"] and "0" not in grid["rgb"]
