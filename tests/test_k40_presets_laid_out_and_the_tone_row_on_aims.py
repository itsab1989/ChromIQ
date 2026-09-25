"""K40 (Knut, #182 5832026677, 2026-09-25): the presets window lays every
preset out, and a FROM PROFILE GAMUT chart's tone row takes its neutral aims.

K40-1, Knut: *"the presets are mostly created with ChromIQ layout engine, not
printtarg. Also, each preset has all layout information, so the "Which presets
can be used for verification" must layout that preset behind the scenes, if
needed, so that the window can judge it."* Every preset the window lists now
reaches the evenness rows with its layout: an engine recipe (the built-ins, the
Full-layout-setup engine presets, a user preset saved with the engine on), or
printtarg, run behind the scenes on a copy of the patch set with the argument
list Generate builds (`workflow.preset_layout`). While that runs the row reads
"Working…"; nothing waits for it.

K40-2, Knut: *"Yes"* to row 20 (the 30 to 70 % tone ramps) using the neutral
aims on a FROM PROFILE GAMUT chart, as the grey rows do (§26.5).

Each test names the mutation it was proved red on.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                           # noqa: E402

from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402
from workflow import preset_layout as PL                           # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
needs_printtarg = pytest.mark.skipif(
    not (ARGYLL / "printtarg").exists(), reason="ArgyllCMS printtarg is needed")
FPG = ROOT / "tests" / "fixtures" / "charts" / "fpg_k31"

#: A user preset saved with the layout engine OFF, as `_on_preset_save`
#: stores it: printtarg's rows by flag.
PRINTTARG_PRESET = {"printtarg_-i": "i1", "printtarg_-p": "A4",
                    "printtarg_-t": 300, "printtarg_-L": True,
                    "printtarg_-a": 1.0, "attached_ti1": True}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _fresh():
    PE.clear_cache()
    yield
    PE.clear_cache()


def _get(extra: "dict | None" = None):
    values = {"argyll_bin_path": str(ARGYLL)}
    values.update(extra or {})
    return lambda k, d=None: values.get(k, d)


def _chart(tmp_path: Path, n: int, name: str = "c") -> Path:
    """A patch set of *n* patches in the three tables printtarg reads."""
    from workflow.i1profiler_import import RgbPatch, write_ti1
    lv = [0, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    pts = [RgbPatch(r, g, b) for r in lv for g in lv for b in lv][:n]
    out = tmp_path / f"{name}.ti1"
    write_ti1(pts, out)
    return out


# ---------------------------------------------------------------------------
# K40-1: every preset is laid out
# ---------------------------------------------------------------------------
@needs_printtarg
def test_a_printtarg_preset_is_laid_out_by_printtarg_and_judged(tmp_path):
    """500 patches on an i1Pro A4 page: printtarg lays them out as 24 strips
    by 21 rows covering 71 % of the page, so both evenness rows are answered;
    300 patches cover 45 %, under the 60 % floor, and say so. Before K40-1
    both read "laid out later".

    MUTATION, proven red: drop the printtarg branch of
    `preset_eligibility._evenness_grid_for` (both read laid_out_later)."""
    spec = PL.layout_for_user_preset(PRINTTARG_PRESET, _get())
    assert PL.is_printtarg_spec(spec)
    big = PE.chart_row_values(_chart(tmp_path, 500, "big"), spec, lay_out=True)
    for rid in ("uniformity_sd", "uniformity_de00_max_from_mean"):
        assert big[rid].get("value") is not None, big[rid]
    small = PE.chart_row_values(_chart(tmp_path, 300, "small"), spec,
                                lay_out=True)
    for rid in ("uniformity_sd", "uniformity_de00_max_from_mean"):
        assert small[rid].get("reason") == MR.REASON_EVENNESS_PAGE_COVERAGE


@needs_printtarg
def test_the_layout_is_the_page_printtarg_writes(tmp_path):
    """The grid is read off printtarg's own .ti2 by the report's own
    `chart_grid`: a direct printtarg run of the same arguments gives the same
    strips, rows, patches and coverage.

    MUTATION, proven red: printtarg run with no arguments in
    `lay_out_with_printtarg` (its own default instrument and paper)."""
    import subprocess
    chart = _chart(tmp_path, 500)
    spec = PL.layout_for_user_preset(PRINTTARG_PRESET, _get())
    got = PL.grid_for(chart, spec, wait=True)
    direct = tmp_path / "direct"
    direct.mkdir()
    shutil.copy2(chart, direct / "x.ti1")
    subprocess.run([str(ARGYLL / "printtarg"), *spec[PL.PRINTTARG_ARGV], "x"],
                   cwd=direct, capture_output=True, timeout=120, check=True)
    want = MR.chart_grid(direct / "x.ti2")
    assert got["pages"] == want["pages"] and got["rows"] == want["rows"]
    # printtarg shuffles the patches on every run (its -r is off), so the
    # places differ between two runs; the page, and what is on it, do not
    assert set(got["slot"]) == set(want["slot"])
    assert [round(c["coverage"], 3) for c in got["coverage"]] == \
        [round(c["coverage"], 3) for c in want["coverage"]]
    assert got["laid_out_by"] == "printtarg"


def test_the_arguments_are_the_ones_generate_builds(qapp, tmp_path):
    """The preset loaded into a real Create Chart tab, Manual, engine off:
    `ChartCreator._build_printtarg_args` over the tab's own `_collect_manual`
    is exactly the argument list the window lays the preset out with.

    MUTATION, proven red: `p.margin_mm = int(get("-m", ...))` removed from
    `preset_layout.params_for_user_preset` (the tab says -m10, the window
    did not)."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    data = dict(PRINTTARG_PRESET, **{"printtarg_-m": 10, "printtarg_-a": 1.2,
                                    "printtarg_-P": True, "printtarg_-L": False,
                                    "printtarg_-r": True})
    s = AppSettings()
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    try:
        tab._manual_btn.click()
        qapp.processEvents()
        s.set("use_chromiq_layout_engine", False)
        tab._restore_user_preset(data)
        qapp.processEvents()
        params = tab._collect_manual()
        want = tab._creator._build_printtarg_args(params)[:-1]
    finally:
        tab.close()
        tab.deleteLater()
        qapp.processEvents()
    spec = PL.layout_for_user_preset(data, s.get)
    assert spec[PL.PRINTTARG_ARGV] == want


def test_an_engine_user_preset_keeps_its_recipe():
    """A preset saved with the engine on carries its recipe, and the window
    judges it with that recipe (`_predicted_grid`), not with printtarg.

    MUTATION, proven red: ignore ``layout_recipe`` in
    `layout_for_user_preset` (a printtarg spec comes back)."""
    rec = {"instrument": "i1", "paper": "A4", "area_cols": 24}
    got = PL.layout_for_user_preset(dict(PRINTTARG_PRESET, layout_recipe=rec),
                                    _get())
    assert got == rec and not PL.is_printtarg_spec(got)


def test_every_built_in_preset_reaches_the_window_with_its_layout(qapp):
    """The two Full-layout-setup ENGINE presets read "laid out later" until
    K40-1 because the window was handed no recipe for them; now no built-in
    preset reads it.

    MUTATION, proven red: drop the ``engine`` branch of
    `tab_chart.builtin_preset_layout` (two presets read laid_out_later)."""
    from core.settings import AppSettings
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY, verification_preset_rows
    rows = [r for r in verification_preset_rows(AppSettings()) if r.builtin]
    assert len(rows) > 150
    engine = [r for r in rows
              if getattr(KNUT_PRESETS_BY_KEY.get(r.key), "engine", False)]
    assert engine, "no Full-layout-setup engine preset found"
    # laid out the way selecting them lays them out: the engine, not printtarg
    wrong = [r.label for r in engine
             if r.recipe is None or PL.is_printtarg_spec(r.recipe)]
    assert not wrong, wrong
    later = []
    for r in rows:
        if r.chart is None:
            continue
        v = PE.chart_row_values(r.chart, r.recipe, lay_out=True)
        if (v.get("uniformity_sd") or {}).get("reason") == \
                PE.REASON_EVENNESS_LAID_OUT_LATER:
            later.append(r.label)
    assert not later, later


def test_a_user_preset_row_carries_its_layout(qapp, tmp_path, monkeypatch):
    """`verification_preset_rows` hands a user preset's layout to the window.

    MUTATION, proven red: ``recipe=None`` for the "Custom presets" rows."""
    import json
    from core.preset_store import tab_dir
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    d = tab_dir("create_chart")
    d.mkdir(parents=True, exist_ok=True)
    name = "K40 layout test preset"
    (d / f"{name}.json").write_text(json.dumps(
        {"chromiq_preset_version": 1, "tab": "create_chart", "name": name,
         "data": PRINTTARG_PRESET}), encoding="utf-8")
    shutil.copy2(_chart(tmp_path, 120), d / f"{name}.ti1")
    try:
        row = next(r for r in verification_preset_rows(AppSettings())
                   if r.label == name)
        assert PL.is_printtarg_spec(row.recipe)
        assert row.recipe[PL.PRINTTARG_ARGV][:2] == ["-ii1", "-pA4"]
    finally:
        (d / f"{name}.json").unlink(missing_ok=True)
        (d / f"{name}.ti1").unlink(missing_ok=True)


@needs_printtarg
def test_the_window_never_waits_and_says_working(qapp, tmp_path):
    """Opened with a printtarg preset nobody has laid out, the window is up at
    once with that row reading "Working…" and its metrics "still being
    checked"; when the background layout arrives the row is redrawn with its
    count, with no click.

    MUTATION, proven red: drop the ``if not wait`` branch of
    `preset_layout.grid_for`, so it always lays out at once (the window lays
    the preset out before it opens; no "Working…")."""
    from core.i18n import tr
    from ui.dialogs import preset_verification_dialog as PVD
    chart = _chart(tmp_path, 500)
    spec = PL.layout_for_user_preset(PRINTTARG_PRESET, _get())
    row = PVD.PresetRow(group="Custom presets", label="P", chart=chart,
                        patches=500, pages=1, builtin=False, key="P",
                        recipe=spec)
    dlg = PVD.PresetVerificationDialog([row], None, None, select="P")
    try:
        assert PE.is_being_laid_out(row.assessment)
        assert dlg._columns(row)[3] == tr("Working…")
        text = [ln.text for ln in PVD.detail_lines(row, every_metric=True)]
        assert tr("Still being checked") in text
        assert dlg.wait_for_layouts(120.0)
        assert not PE.is_being_laid_out(row.assessment)
        assert dlg._columns(row)[3] == tr("{n} of {total} metrics").format(
            n=len(row.assessment.answered), total=len(row.assessment.asked))
        assert "uniformity_sd" in row.assessment.answered
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


@needs_printtarg
def test_a_preset_printtarg_refuses_says_why_in_printtargs_words(qapp, tmp_path):
    """A patch set with only its colours (printtarg wants three tables): both
    evenness rows read "could not lay it out", and the pane quotes printtarg.
    That was every demo verification preset until K40-1.

    MUTATION, proven red: return an empty grid instead of the refusal in
    `lay_out_with_printtarg` (no refusal, no printtarg line)."""
    from core.i18n import tr
    from ui.dialogs import preset_verification_dialog as PVD
    bare = tmp_path / "bare.ti1"
    full = _chart(tmp_path, 120).read_text(encoding="utf-8")
    bare.write_text(full.split("\nEND_DATA\n", 1)[0] + "\nEND_DATA\n",
                    encoding="utf-8")
    spec = PL.layout_for_user_preset(PRINTTARG_PRESET, _get())
    PE.chart_row_values(bare, spec, lay_out=True)
    row = PVD.PresetRow(group="g", label="bare", chart=bare, patches=120,
                        pages=1, builtin=False, key="bare", recipe=spec)
    row.assessment = PE.assess(bare, PE.ANY_REPORT_TYPE, PE.ALL_METRICS,
                               recipe=spec)
    whys = dict(row.assessment.missing)
    assert whys["uniformity_sd"] == PE.REASON_EVENNESS_LAYOUT_REFUSED
    text = " ".join(ln.text for ln in PVD.detail_lines(row, every_metric=True))
    assert "two or three tables" in text
    assert tr("printtarg, which lays this preset's page out, could not lay "
              "it out, so where its patches will sit on the page is not "
              "known.") in text


def test_no_printtarg_says_so(tmp_path):
    """printtarg not where Preferences says ArgyllCMS is.

    MUTATION, proven red: `REASON_LAYOUT_REFUSED` in place of
    `REASON_LAYOUT_NO_TOOL` in `lay_out_with_printtarg`."""
    chart = _chart(tmp_path, 120)
    spec = PL.layout_for_user_preset(
        PRINTTARG_PRESET, _get({"argyll_bin_path": str(tmp_path / "nowhere")}))
    v = PE.chart_row_values(chart, spec, lay_out=True)
    assert v["uniformity_sd"]["reason"] == PE.REASON_EVENNESS_LAYOUT_NO_TOOL


def test_the_layout_is_cached_by_content_not_by_name(tmp_path, monkeypatch):
    """The same patch set under another name is not laid out again; a changed
    one is.

    MUTATION, proven red: key `layout_key` on the path instead of the bytes
    (the copy is laid out twice)."""
    calls = []

    def fake(chart, spec):
        calls.append(Path(chart).name)
        return {"reason": MR.REASON_EVENNESS_GRID_TOO_SMALL}
    monkeypatch.setattr(PL, "lay_out_with_printtarg", fake)
    spec = PL.printtarg_spec(["-ii1", "-pA4"], ARGYLL)
    a = _chart(tmp_path, 120, "a")
    b = tmp_path / "b.ti1"
    shutil.copy2(a, b)
    PL.grid_for(a, spec, wait=True)
    PL.grid_for(b, spec, wait=True)
    assert calls == ["a.ti1"]
    c = _chart(tmp_path, 121, "c")
    PL.grid_for(c, spec, wait=True)
    assert calls == ["a.ti1", "c.ti1"]


# ---------------------------------------------------------------------------
# K40-2: the tone row of a FROM PROFILE GAMUT chart takes its neutral aims
# ---------------------------------------------------------------------------
def _ramps(aims: dict, rgb_of=None, corners=()):
    ids = list(aims)
    rgb = np.asarray([rgb_of(s) if rgb_of else (40.0, 55.0, 70.0)
                      for s in ids])
    lab = [aims[s] for s in ids]
    return MR.ramps_block(rgb, lab, aims, ids, neutral_aims=aims,
                          corner_ids=set(corners))


def test_neutral_aims_between_l30_and_l70_are_the_grey_axis():
    """Device values that are never grey (and no single-ink ramp), aims that
    are neutral at L* 65, 50 and 35: the tone row is answered, at tone values
    35, 50 and 65, and its ΔL* is measured against each aim.

    MUTATION, proven red: drop the ``neutral_aims`` branch of `ramps_block`
    (no axis, `ramp_too_few_neutral_aims`)."""
    aims = {"1": (65.0, 0.2, -0.1), "2": (50.0, -0.3, 0.2),
            "3": (35.0, 0.1, 0.4), "4": (80.0, 30.0, 10.0)}
    b = _ramps(aims)
    grey = b["axes"]["grey"]
    assert grey["eligible"] and grey["source"] == "neutral_aims"
    assert grey["picked"] == [35.0, 50.0, 65.0]
    assert b["reason"] is None and b["max_dl"] == 0.0


def test_device_greys_do_not_count_on_such_a_chart():
    """R = G = B device values whose aims are coloured are not neutral aims:
    on a FROM PROFILE GAMUT chart the grey axis is the AIMS, as for the grey
    rows. The same chart with no reference keeps its device greys.

    MUTATION, proven red: skip the neutral-aim branch (``and False``), so the
    device greys are the axis again."""
    aims = {"1": (65.0, 20.0, 0.0), "2": (50.0, 20.0, 0.0),
            "3": (35.0, 20.0, 0.0)}
    level = {"1": 35.0, "2": 50.0, "3": 65.0}

    def rgb_of(s):
        return (level[s],) * 3
    on_aims = _ramps(aims, rgb_of)
    assert not on_aims["axes"]["grey"]["eligible"]
    assert on_aims["reason"] == MR.REASON_RAMP_TOO_FEW_NEUTRAL_AIMS
    ids = list(aims)
    device = MR.ramps_block(np.asarray([rgb_of(s) for s in ids]),
                            [aims[s] for s in ids], aims, ids)
    assert device["axes"]["grey"]["eligible"] and device["reason"] is None


def test_bunched_aims_are_named_by_their_lightness():
    """Aims at L* 69, 68 and 41 have three steps and a span of 28 but not
    the spacing: nothing lies near the middle of their band, tone value 45,
    which is L* 55, and the reason names the LIGHTNESS.

    MUTATION, proven red: report `missing_level` as the tone value (45)."""
    aims = {"1": (69.0, 0.0, 0.0), "2": (68.0, 0.0, 0.0),
            "3": (41.0, 0.0, 0.0)}
    b = _ramps(aims)
    assert b["reason"] == MR.REASON_RAMP_NEUTRAL_AIMS_BUNCHED
    assert b["missing_level"] == 55.0


def test_the_corners_are_never_steps():
    """The eight cube corners carry the IDEAL device corner as their aim,
    not a neutral the profile prints.

    MUTATION, proven red: drop ``sid not in corners``."""
    aims = {"1": (65.0, 0.0, 0.0), "2": (50.0, 0.0, 0.0),
            "3": (35.0, 0.0, 0.0)}
    b = _ramps(aims, corners=("2",))
    assert not b["axes"]["grey"]["eligible"]


def test_every_other_chart_is_unchanged():
    """No reference, no change: a device grey ramp and a single-ink ramp are
    read exactly as before K40-2."""
    ids = [str(i) for i in range(1, 7)]
    rgb = np.asarray([(70, 70, 70), (50, 50, 50), (30, 30, 30),
                      (70, 100, 100), (50, 100, 100), (30, 100, 100)], float)
    lab = [(60.0, 0.0, 0.0)] * 6
    ref = {s: (59.0, 0.0, 0.0) for s in ids}
    b = MR.ramps_block(rgb, lab, ref, ids)
    assert b["axes"]["grey"]["eligible"] and b["axes"]["R"]["eligible"]
    assert "source" not in b["axes"]["grey"]
    assert b["max_dl"] == 1.0


@pytest.mark.parametrize("n", [100, 400])
def test_the_report_and_the_window_read_the_aims(tmp_path, n):
    """The challenge A charts of K31, a perfect print filed beside the chart:
    the report's tone row and the presets window's current-chart line both
    take the grey axis from the neutral aims.

    MUTATION, proven red: ``neutral_aims=None`` in `build_report`'s call of
    `ramps_block` (no "source"), and in `_perfect_print`'s."""
    from workflow.ti3_analysis import mark_verification_ti3
    dst = tmp_path / f"c{n}"
    shutil.copytree(FPG / f"c{n}", dst)
    chart = dst / "FPG-verify.ti2"
    window = PE._perfect_print(chart)["ramps_30_70"]
    assert window["axes"]["grey"].get("source") == "neutral_aims"
    assert PE.chart_row_values(chart)["ramps_30_70_dl_max"]["value"] is not None
    ti3 = chart.with_suffix(".ti3")
    shutil.copy2(dst / "FPG-verify-reference.ti3", ti3)
    marked = mark_verification_ti3(ti3)
    if marked != ti3:
        marked.replace(ti3)
    rep = MR.build_report(ti3)
    assert rep["reference_source"] == "colorimetric"
    assert rep["ramps_30_70"]["axes"]["grey"].get("source") == "neutral_aims"
    assert MR.row_values(rep)["ramps_30_70_dl_max"]["value"] is not None


def test_the_lever_on_such_a_chart_is_a_larger_chart():
    """The tone row's help lever, narrowed to the reason: a step setting on
    an ordinary chart, a larger chart on a FROM PROFILE GAMUT one.

    MUTATION, proven red: drop the ``_R_RAMPS`` branch of `remedy_for`."""
    from workflow import compliance_sets as CS
    aims = CS.remedy_for("ramps_30_70_dl_max",
                         MR.REASON_RAMP_TOO_FEW_NEUTRAL_AIMS)
    device = CS.remedy_for("ramps_30_70_dl_max", MR.REASON_NO_RAMP)
    assert "more patches" in aims and "(-s)" not in aims
    assert "(-s)" in device and "FROM PROFILE GAMUT" not in device
    assert CS.RAMP_AIM_REASONS == {MR.REASON_RAMP_TOO_FEW_NEUTRAL_AIMS,
                                   MR.REASON_RAMP_NEUTRAL_AIMS_BUNCHED}


def test_the_help_text_states_the_rule():
    """The metric's help icon says how such a chart's grey axis is found."""
    from workflow import compliance_sets as CS
    d = CS.ROW_BY_ID["ramps_30_70_dl_max"].detect
    assert "neutral aims" in d and "100 minus its aim's L*" in d


def test_a_preset_nobody_has_checked_yet_is_checked_behind_the_scenes(qapp):
    """The app opens the window with ``background=True``: a preset whose
    answer is not known yet (the tab's idle warming has not reached it) reads
    "Working…" and is worked out on the background thread, where before K40-1
    the window computed every such answer before it could open (about 13 s
    for the 185 built-ins, cold). The reader's own chart is answered at once.

    MUTATION, proven red: ``row.pending = False`` always in `refresh` (the
    window computes the answer before it opens)."""
    from core.i18n import tr
    from core.settings import AppSettings
    from ui.dialogs import preset_verification_dialog as PVD
    from ui.tabs.tab_chart import verification_preset_rows
    rows = [r for r in verification_preset_rows(AppSettings())
            if r.builtin and r.recipe and r.chart is not None][:3]
    assert len(rows) == 3
    PE.clear_cache()
    dlg = PVD.PresetVerificationDialog(rows, None, None, background=True)
    try:
        assert all(r.pending for r in rows)
        assert dlg._columns(rows[0])[3] == tr("Working…")
        assert "Still being checked: 3" in dlg._figures.text()
        assert dlg.wait_for_layouts(120.0)
        assert not any(r.pending for r in rows)
        assert all(r.assessment.checked for r in rows)
        assert "Still being checked" not in dlg._figures.text()
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()
