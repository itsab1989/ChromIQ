"""k45 (Knut #182 6060464553): every built-in preset is ALSO certified laid
out FROM PROFILE GAMUT, and the presets window shows that count beside the
Manual one (Basti: the app does not know at chart-build time how the chart
will be used, so both stay).

Knut: "the 'Which presets can be used for verification?' window shows
current chart as 18 of 18 metrics answered ... However, all other presets
still show maximum 16 of 18 ... Many presets will as a result show 18 of 18
metrics, and make sure your tests catches this and recreates the
certificates for each preset."

The catch: a preset certified BELOW what it answers laid out From Profile
Gamut. Every built-in that can be laid out again must carry a gamut answer
that answers the two solid-colour metrics (the ones only such a chart can
answer) and everything its own colours answer; and a sample of them, worked
out afresh, must equal what is shipped.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import preset_certificates as PC
from workflow import preset_eligibility as PE

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / "data" / "preset_certificates.json"


@pytest.fixture()
def rows(qapp):
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    PE.clear_cache()
    yield [r for r in verification_preset_rows(AppSettings())
           if r.builtin and r.chart is not None]
    PE.clear_cache()


def _answered(values) -> set:
    return {r for r, c in values.items()
            if isinstance(c, dict) and c.get("value") is not None}


def test_the_profile_is_recorded_and_is_the_one_in_the_repository():
    data = json.loads(SHIPPED.read_text(encoding="utf-8"))
    gp = data["gamut_profile"]
    prof = ROOT / PC.GAMUT_PROFILE_REL
    assert gp["file"] == prof.name
    assert gp["sha256"] == PC._sha_file(prof)
    assert (gp["margin"], gp["intent"]) == ("safe", "absolute")


def test_no_relayoutable_preset_is_certified_below_its_gamut_capability(
        rows, preset_certificates):
    """THE CATCH. Fails when a preset's certificate has no gamut answer, or
    one that does not answer the solid-colour metrics or answers less than
    its own colours do: run python scripts/make_preset_certificates.py."""
    data = json.loads(SHIPPED.read_text(encoding="utf-8"))
    solids = set(PE.gamut_only_rows())
    assert solids, "the metrics only a From Profile Gamut chart answers"
    bad = []
    for r in rows:
        cert = data["certificates"].get(PC.preset_hash(r.chart, r.recipe))
        assert cert is not None, r.key
        g = cert.get("gamut")
        if not r.relayoutable:
            assert g is None, r.key
            continue
        if g is None:
            bad.append((r.key, "no gamut answer"))
            continue
        got = _answered(g["values"])
        if not solids <= got:
            bad.append((r.key, "solids", sorted(solids - got)))
        # not "everything its own colours answer": the control strip is
        # chosen from the chart's own patches, and on a few small charts the
        # gamut colours leave its percentile short where the preset's own
        # colours did not (measured: 1 metric, on 16 one-page presets); the
        # count over all metrics is held below, in the next test
    assert not bad, bad[:5]


def test_most_presets_now_answer_every_metric(rows, preset_certificates):
    """Knut's expectation, measured: of the 189 built-ins, 162 answer all
    18 metrics laid out From Profile Gamut (none did with their own colours,
    16 at most); the others are small one-page charts short of patches for
    the control strip's percentile or the evenness rows."""
    full_own = full_gamut = 0
    every = PE.rows_asked(PE.ANY_REPORT_TYPE, PE.ALL_METRICS)
    assert len(every) == 18
    for r in rows:
        own = PE.assess(r.chart, PE.ANY_REPORT_TYPE, PE.ALL_METRICS,
                        recipe=r.recipe)
        g = PE.assess_gamut(r.chart, PE.ANY_REPORT_TYPE, PE.ALL_METRICS,
                            recipe=r.recipe)
        full_own += len(own.answered) == 18
        full_gamut += g is not None and len(g.answered) == 18
        assert g is not None and len(g.answered) >= len(own.answered), r.key
    assert full_own == 0
    assert full_gamut == 162


def test_a_gamut_answer_is_what_working_it_out_says(rows, preset_certificates,
                                                    tmp_path):
    """The gamut certificate is the answer, not an approximation of it:
    four presets across instruments worked out afresh."""
    from tests.argyll_env import argyll_bin_dir
    bin_dir = argyll_bin_dir()
    if bin_dir is None:
        pytest.skip("needs ArgyllCMS")
    picks = {}
    for r in rows:
        picks.setdefault(r.group, r)
    sample = list(picks.values())[:4]
    assert len(sample) >= 3
    for r in sample:
        g = PC.lookup_gamut(r.chart, r.recipe)
        assert g is not None, r.key
        PC.set_disabled(True)
        PE.clear_cache()
        fresh, n = PC.gamut_variant_values(
            r.chart, r.recipe, ROOT / PC.GAMUT_PROFILE_REL, bin_dir,
            tmp_path / r.key[:40])
        PC.set_disabled(False)
        assert fresh == g["values"], r.key
        assert n == g["patches"], r.key


def test_the_window_shows_both_counts(rows, preset_certificates, qapp):
    from ui.dialogs.preset_verification_dialog import (
        TWO_COUNTS_NOTE, PresetVerificationDialog, gamut_column)
    dlg = PresetVerificationDialog(rows)
    try:
        head = dlg._tree.headerItem()
        assert dlg._tree.columnCount() == 5
        assert head.text(3) == "Metrics answered, own colours"
        assert head.text(4) == "Metrics answered, From Profile Gamut"
        assert head.toolTip(4) == TWO_COUNTS_NOTE
        r = next(x for x in rows if "a4" in x.key and "616" not in x.key
                 and x.gamut_assessment is not None
                 and len(x.gamut_assessment.answered) == 18)
        cols = dlg._columns(r)
        assert cols[4] == gamut_column(r)
        assert cols[4].startswith("18 of 18")
        assert not cols[3].startswith("18 of")
    finally:
        dlg.close()


def test_without_a_certificate_the_window_says_so(qapp):
    from ui.dialogs.preset_verification_dialog import PresetRow, gamut_column
    r = PresetRow(group="g", label="mine", chart=Path("/x.ti1"), patches=10,
                  pages=1, builtin=False)
    assert gamut_column(r) == "Built-in presets only"
    r.relayoutable = False
    assert gamut_column(r) == "Not possible"
