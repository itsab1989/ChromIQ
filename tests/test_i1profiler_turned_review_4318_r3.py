"""Review 4.3.18 r3.

* SF-1: the "Edge spacers" info text said ticking it "doesn't reduce the patch
  count" and that it is "optional". Ticking keeps one inter-patch space at each
  end of every strip (geometry.py), so a strip can hold a patch fewer and a
  chart can need another page; on the i1Pro, i1Pro 3 Plus and ColorMunki it is
  always on. The text now says so, and the engine is held to it here.
* SF-2: txt2ti3 writes ORIGINATOR "Argyll target" (ArgyllCMS 3.5.0), not
  "Argyll txt2ti3". Such a file is still asked "straight or turned"; the real
  tool is run when it is installed.
* N-1: the greyed box's tooltip on a strip reader says the build "treats every
  strip as if this box were ticked", not that it "brackets" it.
* N-2: a chart's snapshot keeps every order of both places, so Restore Used
  Chart pairs and refuses exactly like the original.
* N-4: the (i) button of "Straight strips" is hidden with its box.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import exports_subdir                       # noqa: E402
from workflow import i1profiler_turned as T                       # noqa: E402
from workflow.measurement_import import (                         # noqa: E402
    assess, read_from_the_sheet_as_printed, straight_or_turned_reason,
    turned_ambiguous_reason)

from tests.test_i1profiler_turned_export import _chart             # noqa: E402
from tests.test_i1profiler_turned_review_4318 import (             # noqa: E402
    _half_turn_symmetric_chart, _layout)
from tests.test_i1profiler_turned_review_4318_r2 import (          # noqa: E402
    _candidates, _source_run, _straight_ti3, _txfs, _verdicts, uniform)

__all__ = ["uniform"]       # the fixture is used by name below


# ---------------------------------------------------------------------------
# SF-1 / N-1: the texts, and the engine they describe
# ---------------------------------------------------------------------------

def _panel_source() -> str:
    return Path("ui/dialogs/layout_options_panel.py").read_text(
        encoding="utf-8")


def _info_text() -> str:
    src = _panel_source()
    i = src.index('tr("When this box is ticked')
    j = src.index('difference."),', i) + len('difference."')
    import ast
    return ast.literal_eval("(" + src[i + 3:j] + ")")


def test_the_info_text_no_longer_says_it_costs_nothing():
    text = _info_text()
    assert "reduce the patch count" not in text
    assert "optional" not in text.lower()
    assert "—" not in text
    for needed in ("one patch fewer", "another page",
                   "space between the patches",
                   "i1Pro, i1Pro 3 Plus and ColorMunki, ChromIQ always",
                   "SpectroScan and the CR30"):
        assert needed in text, needed


def test_n1_the_greyed_tooltip_says_treats_as_if_ticked(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        p.instr.setCurrentIndex(p.instr.findData("i1"))
        tip = p.edge_spacers_cb.toolTip()
        assert "treats every strip as if this box were ticked" in tip
        assert "brackets every strip the way this box would" not in tip
        assert "—" not in tip
    finally:
        p.deleteLater()


def _ti1(path: Path, n: int) -> Path:
    import random
    rnd = random.Random(1)
    lines = ["CTI1", "", 'DESCRIPTOR "t"', 'COLOR_REP "RGB"', "",
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(1, n + 1):
        r, g, b = (round(rnd.uniform(0, 100), 4) for _ in range(3))
        lines.append(f"{i} {r} {g} {b} 10 10 10")
    path.write_text("\n".join(lines + ["END_DATA", ""]), encoding="utf-8")
    return path


def test_ticking_it_can_cost_a_patch_per_strip_and_a_page(tmp_path):
    """The reviewer's case: CR30, Spacers None, 1 mm gap, patch-first, A4,
    600 patches: 22 -> 21 per strip, 2 -> 3 pages."""
    from dataclasses import replace
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe, edge_spacers_effect
    base = LayoutRecipe(instrument="CR30", layout_mode="patch_first",
                        spacer_mode="none", inter_patch_mm=1.0, paper="A4",
                        seed=1, dpi=100)
    assert edge_spacers_effect(base) == "changes"
    t = _ti1(tmp_path / "c.ti1", 600)
    got = {}
    for edge in (False, True):
        sub = tmp_path / str(edge)
        sub.mkdir()
        r, _ = build_from_recipe(t, sub / "c", replace(base, edge_spacers=edge))
        got[edge] = (r.layout.steps_in_pass, r.layout.pages)
    assert got[True][0] == got[False][0] - 1
    assert got[True][1] == got[False][1] + 1


# ---------------------------------------------------------------------------
# SF-2: what txt2ti3 really writes
# ---------------------------------------------------------------------------

TXT2TI3_ORIGINATOR = "Argyll target"     # ArgyllCMS 3.5.0, measured


def test_a_txt2ti3_file_is_still_asked(uniform, tmp_path):
    ti3 = _straight_ti3(uniform, tmp_path / "t.ti3", TXT2TI3_ORIGINATOR)
    assert not read_from_the_sheet_as_printed(ti3)
    v = assess(ti3, uniform)
    assert not v.ok and v.reason == straight_or_turned_reason()


def _argyll_txt2ti3() -> "Path | None":
    from core.resource_path import argyll_tool_path
    for folder in (os.environ.get("CHROMIQ_ARGYLL_BIN"),
                   "/Applications/Argyll/bin", "/opt/homebrew/bin",
                   "/usr/local/bin"):
        if folder:
            exe = argyll_tool_path(Path(folder), "txt2ti3")
            if exe.is_file():
                return exe
    which = shutil.which("txt2ti3")
    return Path(which) if which else None


def _ti2_rows(ti2: Path) -> "list[tuple[str, list[float]]]":
    """(SAMPLE_LOC, [R, G, B] 0..100) of every row of *ti2*, in file order."""
    fields, rows, data = None, [], False
    for ln in ti2.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if fields is None and s.startswith("SAMPLE_ID"):
            fields = s.split()
        elif s == "BEGIN_DATA":
            data = True
        elif s == "END_DATA":
            data = False
        elif data and s:
            v = dict(zip(fields, s.split()))
            rows.append((v["SAMPLE_LOC"].strip('"'),
                         [float(v[k]) for k in ("RGB_R", "RGB_G", "RGB_B")]))
    return rows


def _i1profiler_txt(ti2: Path, out: Path) -> Path:
    """An i1Profiler CGATS measurement of *ti2* in the chart's own order."""
    rows = []
    for k, (loc, rgb) in enumerate(_ti2_rows(ti2), start=1):
        r, g, b = (round(v * 2.55) for v in rgb)
        rows.append(f"{k}\t{loc}\t{r}\t{g}\t{b}\t50.0\t0.0\t0.0")
    out.write_text("\n".join([
        "CGATS.17", 'ORIGINATOR\t"i1Profiler"',
        'CREATED\t"October 27, 2026"', 'INSTRUMENTATION\t"i1Pro 3"',
        'KEYWORD\t"SampleID"', 'KEYWORD\t"SAMPLE_NAME"',
        "NUMBER_OF_FIELDS\t8", "BEGIN_DATA_FORMAT",
        "SampleID\tSAMPLE_NAME\tRGB_R\tRGB_G\tRGB_B\tLAB_L\tLAB_A\tLAB_B",
        "END_DATA_FORMAT", f"NUMBER_OF_SETS\t{len(rows)}", "BEGIN_DATA",
        *rows, "END_DATA", ""]), encoding="utf-8")
    return out


def test_the_real_txt2ti3_writes_argyll_target_and_is_asked(uniform,
                                                            tmp_path):
    exe = _argyll_txt2ti3()
    if exe is None:
        pytest.skip("ArgyllCMS txt2ti3 is not installed")
    txt = _i1profiler_txt(uniform, tmp_path / "m.txt")
    base = tmp_path / "m"
    r = subprocess.run([str(exe), str(txt), str(base)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    assert r.returncode == 0, r.stderr or r.stdout
    ti3 = base.with_suffix(".ti3")
    head = ti3.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^ORIGINATOR\s+"([^"]*)"', head, re.MULTILINE)
    assert m and m.group(1) == TXT2TI3_ORIGINATOR, head[:300]
    assert not read_from_the_sheet_as_printed(ti3)
    v = assess(ti3, uniform)
    assert not v.ok and v.reason == straight_or_turned_reason(), v.reason


# ---------------------------------------------------------------------------
# N-2: a restored chart pairs and refuses like the original
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("symmetric", [False, True],
                         ids=["ordinary", "half-turn-symmetric"])
def test_restore_used_chart_pairs_and_refuses_like_the_original(tmp_path,
                                                                symmetric):
    from workflow.chart_slot import slot_for_run
    from workflow.verify_chart_snapshot import restore_slot, snapshot_slot
    src = (_half_turn_symmetric_chart(tmp_path / "src") if symmetric
           else _chart(tmp_path / "src", "Sym", 350))
    _proj, run = _source_run(tmp_path, src, symmetric)
    txfs = _txfs(run.chart_ti2, run.stem)
    before = _verdicts(run.chart_ti2, txfs, tmp_path)
    if symmetric:
        assert before == [(False, False, turned_ambiguous_reason())] * 2
    else:
        assert all(ok and turned for ok, turned, _r in before), before
    cands = _candidates(run.chart_ti2)
    a = run.chart_ti2.read_bytes()
    slot = slot_for_run(run)
    assert snapshot_slot(slot) is not None
    # another chart replaces it, then the used one is restored
    run.chart_ti2.write_bytes(a + b"\n")
    res = restore_slot(slot)
    assert res.ok and run.chart_ti2.read_bytes() == a
    assert not T.TurnedFiles(run.dir, run.stem).order.is_file()
    assert _candidates(run.chart_ti2) == cands
    assert _verdicts(run.chart_ti2, txfs, tmp_path) == before


def test_a_snapshot_without_an_earlier_order_is_the_file_itself(tmp_path):
    from workflow.chart_slot import slot_for_run
    from workflow.verify_chart_snapshot import snapshot_slot
    from tests.test_i1profiler_turned_restore_used_chart import _run_with_chart
    run = _run_with_chart(tmp_path, turned=True)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    stored = T.TurnedFiles(slot.snapshot_dir / "exports", run.stem).order
    assert stored.read_bytes() == run.i1profiler_turned.order.read_bytes()


# ---------------------------------------------------------------------------
# N-4: the (i) of "Straight strips" goes with its box
# ---------------------------------------------------------------------------

def test_n4_the_straight_strips_info_button_is_hidden_with_its_box(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    try:
        cb, info = p.hex_flat_top_cb, p.hex_flat_top_info
        for inst in ("SS", "CR30", "i1", "p3", "CM"):
            p.instr.setCurrentIndex(p.instr.findData(inst))
            for mode in ("hex", "flat"):
                i = p.mode.findData(mode)
                if i < 0:
                    continue
                p.mode.setCurrentIndex(i)
                assert info.isHidden() == cb.isHidden(), (inst, mode)
                if inst == "SS" and mode == "hex":
                    assert info.isHidden()
                if inst == "CR30" and mode == "hex":
                    assert not info.isHidden()
    finally:
        p.deleteLater()
