"""The turned i1Profiler export writes the i1Pro 2 file from 7 mm (4.3.18).

Basti, 2026-10-27: allow the i1Pro 2 from 7 mm along the strip, like the
i1Pro 3, and show no warning about small patches: *"we don't show warnings
for small sizes at the moment even within chromiq so this will be on the
users own risk. if we have no similar warning i don't want one only for
i1profiler"*. 4.3.17 wrote the i1Pro 2 file only from 10 mm, the length
i1Profiler recommends; its i1Pro 2 patch-width slider goes to 7 mm (measured,
``SLIDER``), so a 7 mm file is still inside the slider (0 %).

What is pinned here: an i1Pro 2 chart at 7, 8.88 and 9.95 mm gets its file,
written like a 10 mm one; 6.9 mm is refused for both families with one plain
reason; no text says 10 mm, X-Rite or anything that warns; the strip WIDTH
limit (i1Profiler's patch height, 8 to 12 mm for the i1Pro 2) is unchanged;
and with the option off nothing changes.
"""
from __future__ import annotations

import inspect
import os
import re
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import i1profiler_turned as T                       # noqa: E402
from tests.test_i1profiler_turned_export import (                  # noqa: E402
    _attrs, _chart, _create_chart_sidecars)


@pytest.fixture(scope="module")
def short_charts(tmp_path_factory):
    d = tmp_path_factory.mktemp("short")
    # patch_h_mm is the length ALONG the strip, patch_w_mm the strip width
    return {L: _chart(d / str(L), f"L{str(L).replace('.', '_')}", 200,
                      patch_w_mm=8.0, patch_h_mm=L)
            for L in (6.9, 7.0, 8.88, 9.95)}


def test_both_families_share_one_length_range_inside_their_sliders():
    for fam in T.FAMILIES:
        lo, hi = T.PATCH_LEN_MM[fam]
        assert (lo, hi) == (7.0, 25.0)
        wlo, whi, _hlo, _hhi = T.SLIDER[fam]
        assert wlo <= lo and hi <= whi, fam
    assert not hasattr(T, "SCAN_MIN_W")


@pytest.mark.parametrize("L", [7.0, 8.88, 9.95])
def test_an_i1pro2_chart_from_7_mm_gets_its_file(short_charts, tmp_path, L):
    ti2 = short_charts[L]
    plan = T.plan_for(ti2)
    assert plan.patch_len_mm == pytest.approx(L, abs=0.02)
    assert plan.families == ["i1Pro 2", "i1Pro 3"], plan.family_reasons
    assert plan.family_reasons["i1Pro 2"] == []
    out = tmp_path / "exports"
    res = T.write_turned_export(ti2, out, "S")
    assert not res.skipped
    files = T.TurnedFiles(out, "S")
    a = _attrs(files.txf("i1Pro 2"))
    d = T.design_settings(plan, "i1Pro 2")
    # The width is ChromIQ's patch length, on the i1Pro 2 slider (7..25 mm)
    assert a["PatchSizeWidthValue"] == f"{plan.patch_len_mm:.2f}"
    assert 0.0 <= d["patch_w_percent"] <= 100.0
    assert d["patch_w_percent"] == pytest.approx(
        (plan.patch_len_mm - 7.0) / 18.0 * 100)
    # The strip width stays held inside the i1Pro 2's 8..12 mm height slider
    assert 8.0 <= d["patch_h_mm"] <= 12.0
    assert 0.0 <= d["patch_h_percent"] <= 100.0
    # one strip per i1Profiler row, as for every other length
    w = T.page_width_mm(plan, "i1Pro 2")
    assert int(min(241.5, w - 31) // plan.patch_len_mm) == plan.columns
    note = files.note.read_text(encoding="utf-8")
    assert "i1Pro 2: load the file ending in -i1profiler-turned-i1Pro2.txf" \
        in note
    # the i1Pro 2 file is still said to be unchecked in i1Profiler
    assert "The i1Pro 2 file is written by the same rules, but it could not " \
           "be opened in i1Profiler" in note


def test_a_7_mm_file_sits_at_the_bottom_of_the_i1pro2_slider(short_charts,
                                                             tmp_path):
    plan = T.plan_for(short_charts[7.0])
    if plan.patch_len_mm != 7.0:
        pytest.skip(f"this build made {plan.patch_len_mm} mm patches")
    T.write_turned_export(short_charts[7.0], tmp_path, "S")
    a = _attrs(T.TurnedFiles(tmp_path, "S").txf("i1Pro 2"))
    assert a["PatchSizeWidthPercent"] == "0"


def test_6_9_mm_is_refused_for_both_with_one_plain_reason(short_charts,
                                                          tmp_path):
    ti2 = short_charts[6.9]
    plan = T.plan_for(ti2)
    assert plan.patch_len_mm < 7.0
    assert plan.families == []
    for fam in T.FAMILIES:
        why = plan.family_reasons[fam]
        assert why == [
            f"the patches are {plan.patch_len_mm:.2f} mm long along the "
            f"strip, and the {fam} file is written only for patches 7 to 25 "
            f"mm long"], why
    res = T.write_turned_export(ti2, tmp_path, "S")
    assert res.written == [T.TurnedFiles(tmp_path, "S").note]
    note = T.TurnedFiles(tmp_path, "S").note.read_text(encoding="utf-8")
    assert "7 to 25 mm long (for the i1Pro 2 and the i1Pro 3 alike)" in note


def test_no_text_names_10_mm_x_rite_or_a_warning():
    from ui import file_guide
    from ui.dialogs import settings_dialog
    srcs = (inspect.getsource(T), inspect.getsource(file_guide),
            inspect.getsource(settings_dialog))
    for src in srcs:
        for gone in ("10 to 25", "X-Rite asks for when scanning",
                     "So 10 mm patches work for both"):
            assert gone not in src, gone
    tip = inspect.getsource(settings_dialog)
    assert ("Along the strip the patches must be 7 to 25 \"\n"
            "                  \"mm long, for the i1Pro 2 and the i1Pro 3 "
            "alike") in tip
    # no new warning about small patches anywhere in the turned texts
    notes = (inspect.getsource(T.note_qualified)
             + inspect.getsource(T.note_not_qualified)
             + inspect.getsource(T.plan_for))
    assert not re.search(r"(?i)small patch|too short|recommend|X-Rite", notes)


def test_with_the_option_off_a_7_mm_chart_gets_no_turned_file(short_charts,
                                                              tmp_path):
    src = short_charts[7.0]
    for p in src.parent.glob(f"{src.stem}*"):
        if p.is_file():
            shutil.copy2(p, tmp_path / p.name)
    files, log = _create_chart_sidecars(tmp_path / src.name, src.stem,
                                        on=False)
    assert not any("i1profiler-turned" in n for n in files), files
    assert not any("turned" in l.lower() for l in log), log
