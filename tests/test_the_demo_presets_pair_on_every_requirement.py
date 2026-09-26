"""#182, beta 26: the demo presets, TWO PER REQUIREMENT, one each side of it.

Knut, 2026-09-19:

    *"Recreate the chart presets so that every metric that can be tested has
    one preset for each condition a metric uses to select if a patch set can be
    used in verification to test against that metric. […] create one preset for
    each requirement of a metric, where each threshold is on the border of the
    threshold, but not complying with that specific requirement. And then one
    preset for each requirement of a metric, where each threshold is on the
    border of the threshold, but complying with that specific requirement. Then
    use the demo files in testing on-screen and mathematically to verify that
    they work […] This should make sure that every metric defined works as they
    where intended."*

**WHAT THIS FILE IS FOR, AND WHY IT IS NOT THE ONE IT REPLACES.** The pack
before it had one preset per REASON CODE. A reason code is not a requirement:
``control_strip_too_small`` is two of them (eight ids for the average, twenty
for the 95th percentile), ``too_few_surface_patches`` is two (what counts as a
surface patch, and how many are needed) and ``no_ramp`` is two (how many steps,
and how far apart). One preset per code cannot say which half of a code went
dead. Thirteen pairs can.

THE THREE THINGS EVERY PAIR HAS TO PROVE
----------------------------------------
1. the FAIL preset, one notch outside the line, withholds the rows that
   requirement decides, with that requirement's own reason code;
2. the PASS preset, exactly ON the line, answers them;
3. **nothing else moves.** Every other row reads the same on both sides. Two
   charts that differ in two ways prove nothing about either, which is the
   fault the pack before this one carried on its smallest chart.

AND THE SECOND OPINION IS IN HERE TOO
-------------------------------------
``_independent`` judges each chart from its ``.ti1`` with its own arithmetic
and its own literal thresholds, importing nothing from ``preset_eligibility``
or ``measurement_report``. ``test_the_independent_arithmetic_agrees_with_the_app``
compares the two over every preset and every row; the app agreeing with itself
is worth nothing and is how three of this project's green suites stayed green
over real faults. ``test_the_thresholds_the_pack_claims_are_the_apps_own`` is
the other end of the same rope: the literals here are compared against the
app's constants, so retuning one turns this file red instead of quietly moving
every boundary in the pack.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt                                        # noqa: E402
from PyQt6.QtWidgets import QApplication                           # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from core.argyll_runner import ArgyllRunner                        # noqa: E402
from core.file_manager import FileManager                          # noqa: E402
from core.preset_store import tab_dir                              # noqa: E402
from core.settings import AppSettings                              # noqa: E402
from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from ui.tabs.tab_chart import TabChart                             # noqa: E402
from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

import make_verification_preset_demos as GEN                       # noqa: E402

#: The strictest combination ChromIQ offers: all sixteen computable rows are
#: asked, so every reason a chart can give has somewhere to appear. A demo that
#: fails a row nobody asked about would go unnoticed on any softer pair.
STRICT = (MR.REPORT_TYPE_FULL, "custom_iso_12647_7")

#: The one code every preset carries and no preset causes: a preset chart never
#: has a colorimetric reference. Excluded wherever a claim is checked.
CONSTANT = MR.REASON_NEEDS_REFERENCE_FILE
#: …and a second one since the evenness rows became computable (#182,
#: 2026-09-22). It was "laid out later" until K40-1 (Knut, 5832026677), when
#: the window began to lay every preset out behind the scenes: every 78-patch
#: demo is a printtarg preset, which printtarg lays out as 3 i1Pro strips on
#: A4, under the 9 by 9 page both evenness rows need. The larger demos of K43
#: (R16, L1) do not carry it: their page is judged.
CONSTANT_LAYOUT = MR.REASON_EVENNESS_GRID_TOO_SMALL
CONSTANTS = (CONSTANT, CONSTANT_LAYOUT)


# ---------------------------------------------------------------------------
# The second opinion: the same question, none of the same code
# ---------------------------------------------------------------------------
#: Typed out from the help text the user is shown (the ``_D_*`` sentences in
#: `workflow/compliance_sets.py`) and from Knut's own paragraph, NOT read from
#: the app. `test_the_thresholds_the_pack_claims_are_the_apps_own` is what
#: holds the two together.
IND = {
    "grey_within": 1.0, "grey_steps": 8, "grey_apart": 0.5,
    "grey_white_at": 90.0, "grey_black_at": 10.0, "grey_paper_at": 99.5,
    "paper_at": 99.5,
    "grey_even_within": 4.0,
    "ramp_low": 30.0, "ramp_high": 70.0, "ramp_steps": 3, "ramp_span": 20.0,
    # K31 rule A (Knut, #182 5801677743): the grey ramp's spacing, on the band
    "ramp_even_within": 4.0,
    "ramp_others_at": 99.0,
    "strip_min": 8, "strip_p95_min": 20,
    "surface_within": 2.0, "surface_min": 10,
    "outer_fraction": 0.25, "outer_min": 20,
    "worst5_min": 20,
    # K43 (the larger demos): the evenness page, Knut's two floors
    "evenness_grid": 9, "evenness_coverage": 0.60,
}

#: K43: printtarg's page for these presets (i1Pro, A4, 300 dpi, -L), MEASURED
#: off its page image with a ruler, not asked of the app, by patch size (-a):
#: patches to a strip, strips to a page, a strip's width and the block's
#: height in mm, on a 210 by 297 mm sheet.
PAGE = {1.0: {"strip_patches": 21, "page_strips": 24, "strip_mm": 8.005,
              "block_mm": 232.07},
        0.8: {"strip_patches": 27, "page_strips": 30, "strip_mm": 6.405,
              "block_mm": 238.50}}
SHEET_MM2 = 209.97 * 297.01

#: #182 K49, (b2): the two solid rows only; the paper row is answered by a
#: chart with a patch printed with no ink (`IND["paper_at"]`).
_REFERENCE_ROWS = ("solids_de00_max", "cmy_solids_dhab_max")
_FREE_ROWS = ("all_de00_avg", "best95_de00_avg", "all_de00_max",
              "all_de00_p95")


def _read_ti1(path: Path):
    """``(sample ids, device RGB on 0..100, keywords)``, with its own parser."""
    keywords, fields, rows, mode = {}, [], [], "header"
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s:
            continue
        if s in ("BEGIN_DATA_FORMAT", "END_DATA_FORMAT", "BEGIN_DATA",
                 "END_DATA"):
            mode = {"BEGIN_DATA_FORMAT": "format", "END_DATA_FORMAT": "header",
                    "BEGIN_DATA": "data", "END_DATA": "done"}[s]
            if mode == "done":
                # the patch list is the FIRST table; since K40-1 the demos
                # carry printtarg's two further tables after it
                break
            continue
        if mode == "format":
            fields = s.split()
        elif mode == "data":
            rows.append(s.split())
        elif mode == "header":
            m = re.match(r'^([A-Z][A-Z0-9_]*)\s+"?(.*?)"?\s*$', s)
            if m:
                keywords[m.group(1)] = m.group(2)
    ix = {n: i for i, n in enumerate(fields)}
    if any(k not in ix for k in ("SAMPLE_ID", "RGB_R", "RGB_G", "RGB_B")):
        raise ValueError("not a chart")
    ids = [r[ix["SAMPLE_ID"]] for r in rows]
    rgb = [[float(r[ix["RGB_R"]]), float(r[ix["RGB_G"]]), float(r[ix["RGB_B"]])]
           for r in rows]
    if rgb and max(max(t) for t in rgb) > 101.0:
        rgb = [[v * 100.0 / 255.0 for v in t] for t in rgb]
    return ids, rgb, keywords


def _distinct(values, apart: float) -> int:
    n, last = 0, None
    for v in sorted(values):
        if last is None or v - last > apart:
            n += 1
            last = v
    return n


def _evenly_spaced(values, need: int, within: float) -> bool:
    """Whether *need* or more positions spaced evenly from the lowest value to
    the highest each have a DIFFERENT value within *within* of them. Written
    here from Knut's words (#182 B8-483), not imported."""
    vals = sorted(set(round(v, 3) for v in values))
    lo, hi = vals[0], vals[-1]
    for m in range(need, len(vals) + 1):
        taken = []
        for k in range(m):
            at = lo + k * (hi - lo) / (m - 1)
            best = min(vals, key=lambda v: abs(v - at))
            if abs(best - at) > within or best in taken:
                break
            taken.append(best)
        else:
            return True
    return False


def _ladder_fills(ids, rgb) -> int:
    """How many of ChromIQ's twenty-nine rungs this chart fills, re-derived.

    The substrate, the seven other cube corners, a 25/50/75 tint of each of the
    six colours and three neutral tints; nearest unused patch within 12 device
    units on every channel, ties by sample id.
    """
    slots = [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0), (0.0, 100.0, 100.0),
             (100.0, 0.0, 100.0), (100.0, 100.0, 0.0), (100.0, 0.0, 0.0),
             (0.0, 100.0, 0.0), (0.0, 0.0, 100.0)]
    for ch in (0, 1, 2):
        for ink in (75, 50, 25):
            dev = [100.0, 100.0, 100.0]
            dev[ch] = 100.0 - ink
            slots.append(tuple(dev))
    for ch in (0, 1, 2):
        for ink in (75, 50, 25):
            dev = [100.0 - ink] * 3
            dev[ch] = 100.0
            slots.append(tuple(dev))
    for ink in (75, 50, 25):
        slots.append((100.0 - ink,) * 3)
    order = sorted(range(len(ids)),
                   key=lambda i: (0, int(ids[i]), "") if ids[i].isdigit()
                   else (1, 0, ids[i]))
    alive, filled = set(order), 0
    for slot in slots:
        best, best_d = None, None
        for i in order:
            if i not in alive:
                continue
            d = max(abs(rgb[i][j] - slot[j]) for j in range(3))
            if best_d is None or d < best_d:
                best, best_d = i, d
        if best is not None and best_d <= 12.0:
            alive.discard(best)
            filled += 1
    return filled


def _independent(path: Path, scale: float = 1.0) -> "dict[str, str | None]":
    """``{row_id: reason or None}``, computed from the .ti1 and the patch
    size the preset is saved with (*scale*), and nothing else."""
    ids, rgb, kw = _read_ti1(path)
    out: "dict[str, str | None]" = {r: CONSTANT for r in _REFERENCE_ROWS}
    out.update({r: None for r in _FREE_ROWS})
    # K49, (b2): the paper row, off the patch printed with no ink
    out["substrate_de00_max"] = (
        None if any(min(px) >= IND["paper_at"] for px in rgb)
        else MR.REASON_NO_PAPER_PATCH)
    # the evenness page, from the patch count and printtarg's page as
    # measured (PAGE): the first page's strips, its rows, and its block
    page = PAGE[round(float(scale), 2)]
    strips = min(page["page_strips"],
                 int(math.ceil(len(ids) / page["strip_patches"])))
    rows = min(len(ids), page["strip_patches"])
    cover = strips * page["strip_mm"] * page["block_mm"] / SHEET_MM2
    even = (CONSTANT_LAYOUT if min(strips, rows) < IND["evenness_grid"]
            else MR.REASON_EVENNESS_PAGE_COVERAGE
            if cover < IND["evenness_coverage"] else None)
    out.update({r: even for r in ("uniformity_sd",
                                  "uniformity_de00_max_from_mean")})

    # -- the control strip
    declared = [p for p in re.split(r"[,\s]+",
                                    kw.get("CONTROL_STRIP_IDS", "").strip())
                if p]
    if not declared and _ladder_fills(ids, rgb) >= IND["strip_min"]:
        declared = ["?"] * _ladder_fills(ids, rgb)     # a strip ChromIQ writes
    if not declared:
        strip_avg = strip_p95 = MR.REASON_NO_CONTROL_STRIP
    else:
        k = len([s for s in declared if s == "?" or s in set(ids)])
        strip_avg = (None if k >= IND["strip_min"]
                     else MR.REASON_CONTROL_STRIP_TOO_SMALL)
        strip_p95 = (None if k >= IND["strip_p95_min"]
                     else MR.REASON_CONTROL_STRIP_TOO_SMALL)
    out["control_strip_de00_avg"] = strip_avg
    out["control_strip_de00_max"] = strip_avg
    out["control_strip_de00_p95"] = strip_p95

    # -- the neutral ramp
    levels = [sum(t) / 3.0 for t in rgb
              if max(t) - min(t) <= IND["grey_within"]]
    if not levels:
        grey = MR.REASON_NO_GREYS
    elif _distinct(levels, IND["grey_apart"]) < IND["grey_steps"]:
        grey = MR.REASON_TOO_FEW_STEPS
    elif max(levels) < IND["grey_white_at"]:
        grey = MR.REASON_NO_WHITE
    elif min(levels) > IND["grey_black_at"]:
        grey = MR.REASON_NO_BLACK
    elif not _evenly_spaced(levels, IND["grey_steps"], IND["grey_even_within"]):
        grey = MR.REASON_GREY_STEPS_BUNCHED
    elif not [v for v in levels if v < IND["grey_paper_at"]]:
        grey = MR.REASON_NO_REFERENCE
    else:
        grey = None
    out["grey_balance_neutral_ramp_avg"] = grey
    out["grey_balance_neutral_ramp_max"] = grey

    # -- the 30 to 70 % ramps, four axes
    ok = bunched = False
    for ch, others in ((0, (1, 2)), (1, (0, 2)), (2, (0, 1)), (None, ())):
        if ch is None:
            tvs = [100.0 - sum(t) / 3.0 for t in rgb
                   if max(t) - min(t) <= IND["grey_within"]]
        else:
            tvs = [100.0 - t[ch] for t in rgb
                   if all(t[o] >= IND["ramp_others_at"] for o in others)]
        band = [tv for tv in tvs if IND["ramp_low"] <= tv <= IND["ramp_high"]]
        if not band:
            continue
        if (_distinct(band, IND["grey_apart"]) >= IND["ramp_steps"]
                and max(band) - min(band) >= IND["ramp_span"]):
            if _evenly_spaced(band, IND["ramp_steps"],
                              IND["ramp_even_within"]):
                ok = True
            else:
                bunched = True
    out["ramps_30_70_dl_max"] = (None if ok else
                                 MR.REASON_RAMP_STEPS_BUNCHED if bunched
                                 else MR.REASON_NO_RAMP)

    # -- the counted rows
    out["worst5_de00_avg"] = (None if len(ids) >= IND["worst5_min"]
                              else MR.REASON_SMALL_SAMPLE)
    n_surface = sum(1 for t in rgb
                    if min(min(v, 100.0 - v) for v in t)
                    <= IND["surface_within"])
    out["surface_gamut_de00_avg"] = (
        None if n_surface >= IND["surface_min"]
        else MR.REASON_TOO_FEW_SURFACE_PATCHES)
    quarter = max(1, int(math.ceil(len(ids) * IND["outer_fraction"])))
    out["outer_gamut_226_de00_avg"] = (
        None if quarter >= IND["outer_min"]
        else MR.REASON_TOO_FEW_OUTER_PATCHES)
    return out


# ---------------------------------------------------------------------------
# The window, driven the way a user reaches it
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def installed(qapp, tmp_path_factory):
    """The presets, installed THE WAY A USER INSTALLS THEM: the generator
    writes the downloadable folder and its contents are copied into the Create
    Chart preset folder. No app code is asked to import anything, because a
    user has no such door."""
    pack = tmp_path_factory.mktemp("pack") / GEN.FOLDER
    GEN.build(pack)
    dest = tab_dir("create_chart")
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(pack.iterdir()):
        if src.suffix not in (".json", ".ti1"):
            continue
        shutil.copy2(src, dest / src.name)
        copied.append(dest / src.name)
    PE.clear_cache()
    yield pack
    for p in copied:
        p.unlink(missing_ok=True)
    PE.clear_cache()


@pytest.fixture(scope="module")
def dialog(qapp, installed):
    """The window, opened by a real click on the real button of a real tab."""
    s = AppSettings()
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab.show()
    qapp.processEvents()
    tab._manual_btn.click()
    qapp.processEvents()

    opened: list = []
    real_exec = PVD.PresetVerificationDialog.exec

    def _no_block(self):
        opened.append(self)
        return 0

    PVD.PresetVerificationDialog.exec = _no_block
    try:
        tab._preset_verify_btn.click()
        qapp.processEvents()
    finally:
        PVD.PresetVerificationDialog.exec = real_exec
    assert opened, "clicking the real button opened no window"
    dlg = opened[0]
    # K40-1: the demos are printtarg presets, laid out behind the scenes; a
    # user reads the window once that is done, so the fixture waits for it.
    assert dlg.wait_for_layouts(180.0), "the background layouts never finished"
    # WHAT A USER SEES FIRST, kept before the fixture moves anything: this
    # file judged every pair under STRICT and never looked at the choice the
    # window opens on, which is where Knut looked (K15).
    dlg._k15_opened_on = (dlg.current_type(), dlg.current_set())
    dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(STRICT[0]))
    dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(STRICT[1]))
    qapp.processEvents()
    yield dlg
    dlg.close()
    tab.close()
    tab.deleteLater()
    qapp.processEvents()


def _row_for(dlg, label: str):
    for i in range(dlg._tree.topLevelItemCount()):
        head = dlg._tree.topLevelItem(i)
        for j in range(head.childCount()):
            child = head.child(j)
            row = child.data(0, Qt.ItemDataRole.UserRole)
            if row is not None and row.label == label:
                return head, child, row
    return None, None, None


def _withheld(dlg, demo) -> "dict[str, str]":
    """What the real window withholds from this preset, minus the constant."""
    _head, item, row = _row_for(dlg, demo.name)
    assert item is not None, f"{demo.name} is not in the window"
    return {rid: why for rid, why in row.assessment.missing
            if why not in CONSTANTS}


def _detail_text(dlg, item) -> "list[str]":
    dlg._tree.setCurrentItem(item)
    QApplication.instance().processEvents()
    out = []
    for i in range(dlg._detail_layout.count()):
        w = dlg._detail_layout.itemAt(i).widget()
        if w is not None and hasattr(w, "text"):
            out.append(w.text())
    return out


_PAIRS = GEN.pairs()
_IDS = [r.key for r, _f, _p in _PAIRS]


# ---------------------------------------------------------------------------
# 1. they arrive, the way a user's own presets arrive
# ---------------------------------------------------------------------------
def test_every_demo_preset_reaches_the_window(dialog):
    labels = {r.label for r in dialog._rows}
    missing = [d.name for d in GEN.DEMOS if d.name not in labels]
    assert not missing, missing


def test_every_demo_preset_reaches_the_dropdown(qapp, installed):
    """The pulldown half of Knut's sentence, on a freshly built tab, which is
    what a restart gives the user."""
    s = AppSettings()
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    try:
        tab.show()
        qapp.processEvents()
        tab._manual_btn.click()
        qapp.processEvents()
        combo = tab._preset_combo
        listed = {combo.itemText(i) for i in range(combo.count())}
        missing = [d.name for d in GEN.DEMOS
                   if not any(d.name in t for t in listed)]
        assert not missing, missing
    finally:
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


def test_the_demos_are_grouped_as_the_users_own_presets(dialog):
    for d in GEN.DEMOS:
        head, _item, row = _row_for(dialog, d.name)
        assert not row.builtin, d.name
        assert head.text(0) == "Custom presets", (d.name, head.text(0))


# ---------------------------------------------------------------------------
# 2. the three things every pair has to prove
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("req,fail,ok", _PAIRS, ids=_IDS)
def test_the_fail_side_withholds_exactly_its_own_rows(dialog, req, fail, ok):
    """One notch outside the line, and the rows that requirement decides are
    withheld with that requirement's own reason code."""
    got = _withheld(dialog, fail)
    for rid in req.rows:
        assert got.get(rid) == req.reason, (req.key, rid, got)


@pytest.mark.parametrize("req,fail,ok", _PAIRS, ids=_IDS)
def test_the_pass_side_answers_them(dialog, req, fail, ok):
    """Exactly ON the line, and the same rows are answered. This is the half
    that catches a threshold quietly moved one notch the other way."""
    got = _withheld(dialog, ok)
    for rid in req.rows:
        assert rid not in got, (req.key, rid, got[rid])


@pytest.mark.parametrize("req,fail,ok", _PAIRS, ids=_IDS)
def test_nothing_else_moves_across_the_pair(dialog, req, fail, ok):
    """**THE ONE THAT MAKES A PAIR EVIDENCE.** Two charts that differ in two
    ways prove nothing about either: the old pack's smallest chart failed three
    things at once and could not be read as saying anything about any of them.
    Every row outside this requirement's own must read the same on both sides.
    """
    got_f, got_p = _withheld(dialog, fail), _withheld(dialog, ok)
    moved = {rid for rid in set(got_f) | set(got_p)
             if rid not in req.rows and got_f.get(rid) != got_p.get(rid)}
    assert not moved, (req.key, {rid: (got_f.get(rid), got_p.get(rid))
                                 for rid in moved})
    constant = sorted({why for rid, why in got_f.items()
                       if rid not in req.rows})
    assert constant == sorted(set(req.also)), (req.key, constant,
                                               sorted(set(req.also)))


@pytest.mark.parametrize("req,fail,ok", _PAIRS, ids=_IDS)
def test_the_window_says_what_is_missing_in_its_own_words(dialog, req, fail,
                                                          ok):
    """Knut asked the window to *"report what is wrong/missing"*: the detail
    pane carries the sentence for the reason and the metric's own remedy."""
    _head, item, _row = _row_for(dialog, fail.name)
    shown = _detail_text(dialog, item)
    assert PVD.reason_line(req.reason) in shown, (req.key, shown)
    for rid in req.rows:
        assert "✕  " + PE.row_label(rid) in shown, (req.key, rid)
        remedy = PE.row_remedy(rid, req.reason)
        if remedy:
            assert remedy in shown, (req.key, rid)


# ---------------------------------------------------------------------------
# 2b. where a reader has to look (K15, Knut on beta 34)
# ---------------------------------------------------------------------------
def _choose(dlg, choice) -> None:
    dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(choice[0]))
    dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(choice[1]))
    QApplication.instance().processEvents()


def test_the_pack_knows_which_choice_the_window_opens_on(dialog):
    """The tags are decided against the window's opening choice, so that
    choice is asked of the WINDOW here, not only of the lists it is built
    from."""
    assert dialog._k15_opened_on == GEN.opening_choice()


@pytest.mark.parametrize("req,fail,ok", _PAIRS, ids=_IDS)
def test_each_pair_shows_under_the_choice_its_name_gives(dialog, req, fail,
                                                         ok):
    """Knut: the verification demos *"seamed not to trigger FAIL properly on
    many of the demo presets"*. Measured: under the choice the window opens
    on, eight of thirteen pairs read identically, because ChromIQ's own sets
    ask nothing about the control strip, the tone ramps, the surface or the
    outer gamut. Every assertion above ran under STRICT, which no user lands
    on by opening the window.

    So each pair names the choice that shows it, and here the window is put
    on exactly that choice and must show FAIL on one side and not the other.

    MUTATION, proved to land: make `shown_under` return the opening choice
    unconditionally and the eight tagged pairs go red here.
    """
    choice = GEN.shown_under(req)
    try:
        _choose(dialog, choice)
        got_f, got_p = _withheld(dialog, fail), _withheld(dialog, ok)
        for rid in req.rows:
            assert got_f.get(rid) == req.reason, (req.key, choice, rid, got_f)
            assert rid not in got_p, (req.key, choice, rid, got_p)
    finally:
        _choose(dialog, STRICT)


@pytest.mark.parametrize("req,fail,ok", _PAIRS, ids=_IDS)
def test_a_pair_is_tagged_exactly_when_the_opening_choice_hides_it(
        dialog, req, fail, ok):
    """The tag is the fix, so it must be neither missing nor gratuitous: a
    pair the opening choice already shows carries none, and a pair that
    carries one really does read the same on both presets there."""
    tagged = "[judge with " in fail.name
    assert tagged == ("[judge with " in ok.name)
    opening = dialog._k15_opened_on
    try:
        _choose(dialog, opening)
        got_f = _withheld(dialog, fail)
        shows_at_opening = all(got_f.get(rid) == req.reason
                               for rid in req.rows)
    finally:
        _choose(dialog, STRICT)
    assert tagged == (not shows_at_opening), (
        f"{req.key}: tagged={tagged} but at the opening choice the FAIL "
        f"preset {'shows' if shows_at_opening else 'does not show'} its "
        f"shortfall ({got_f})")


# ---------------------------------------------------------------------------
# 3. the control, and the two that ask a question instead of making a claim
# ---------------------------------------------------------------------------
def test_the_control_answers_every_row_its_patches_decide(dialog):
    """A control that quietly fails something makes every other row in this
    file unreadable."""
    demo = next(d for d in GEN.DEMOS if d.kind == "control")
    _head, _item, row = _row_for(dialog, demo.name)
    assert row.assessment.checked
    assert not row.assessment.patch_shortfalls, row.assessment.missing
    assert not _withheld(dialog, demo)


def test_the_larger_control_answers_the_evenness_rows_too(dialog):
    """K43 (Knut, #182 5833695633: "use also larger demo charts/presets to
    catch and test more metrics and combinations"): the 650-patch control,
    two pages, answers every row a preset can decide, the two evenness rows
    included, which no 78-patch demo can.

    MUTATION, proven red: build it with 78 patches (``chart_page(78)``)."""
    demo = next(d for d in GEN.DEMOS if d.name.startswith("Verify L1 "))
    _head, _item, row = _row_for(dialog, demo.name)
    missing = dict(row.assessment.missing)
    assert "uniformity_sd" not in missing, missing
    assert "uniformity_de00_max_from_mean" not in missing, missing
    assert not _withheld(dialog, demo), missing


def test_no_open_question_is_left_in_the_pack(dialog):
    """Knut's own paragraph expects a spacing requirement: *"the selected
    patches have a certain distance between each other … so that they are not
    clumped together in one end or in the middle"*. For the GREY ramp he ruled
    it on 2026-09-23 (#182 B8-483): its Q1 became R14's FAIL side. For the 30
    to 70 % ramp he ruled it the same day (K31, #182 5801677743, "Implement
    rule A"): its Q2 became R15's FAIL side, and the chart it was is withheld
    with ``ramp_steps_bunched``.

    MUTATION, proven red: put ``pick_even_grey_steps`` out of
    `measurement_report.ramps_block` (the R15 FAIL side answers the row
    again, and the pair test above goes red with it)."""
    assert not [d for d in GEN.DEMOS if d.kind == "open"]
    r15 = GEN.REQ_BY_KEY["R15"]
    fail = next(d for d in GEN.DEMOS if d.key == "R15" and d.kind == "FAIL")
    got = _withheld(dialog, fail)
    assert got.get("ramps_30_70_dl_max") == r15.reason == \
        MR.REASON_RAMP_STEPS_BUNCHED, got


def test_a_preset_with_no_patch_set_is_listed_and_told_which_tick_box(dialog):
    demo = next(d for d in GEN.DEMOS if d.no_chart)
    _head, item, row = _row_for(dialog, demo.name)
    assert row.chart is None
    assert not row.assessment.checked
    shown = _detail_text(dialog, item)
    assert any("attach its .ti1" in t for t in shown), shown


def test_a_preset_whose_chart_cannot_be_read_says_so(dialog):
    demo = next(d for d in GEN.DEMOS if d.corrupt)
    _head, item, row = _row_for(dialog, demo.name)
    assert row.chart is not None, "the unreadable .ti1 was not even found"
    assert not row.assessment.checked
    shown = _detail_text(dialog, item)
    assert any("could not read" in t for t in shown), shown


# ---------------------------------------------------------------------------
# 4. the second opinion
# ---------------------------------------------------------------------------
def test_the_independent_arithmetic_agrees_with_the_app(dialog, installed):
    """Every preset, every row, judged twice by two routes that share no code.

    The app's answer comes out of the real window's own assessment; the other
    is :func:`_independent`, which parses the ``.ti1`` itself and applies its
    own literal thresholds. A row where they part is the finding Knut asked
    for, and it says which is wrong, the requirement or the preset. As of
    beta 26 there are none, over 29 charts and 16 rows each.
    """
    from core.preset_store import sidecar_path
    bad = []
    for d in GEN.DEMOS:
        if d.no_chart or d.corrupt:
            continue
        chart = sidecar_path("create_chart", d.name, ".ti1")
        want = _independent(chart, d.scale)
        got = dict(_row_for(dialog, d.name)[2].assessment.missing)
        for rid, why in want.items():
            if got.get(rid) != why:
                bad.append((d.name, rid, got.get(rid), why))
    assert not bad, bad


def test_the_thresholds_the_pack_claims_are_the_apps_own():
    """The literals above, against the constants the app really applies.

    Without this the second opinion could be retuned into agreement with a
    changed app and nobody would see it move.
    """
    assert IND["grey_within"] == MR.GREY_SPREAD_TOL
    assert IND["grey_steps"] == MR.GREY_MIN_LEVELS
    assert IND["grey_apart"] == MR.GREY_LEVEL_TOL
    assert IND["grey_white_at"] == MR.GREY_LIGHTEST_MIN
    assert IND["grey_black_at"] == MR.GREY_DARKEST_MAX
    assert IND["grey_paper_at"] == MR.GREY_PAPER_LEVEL
    assert IND["paper_at"] == 100.0 - MR.PAPER_PATCH_TOL
    assert IND["grey_even_within"] == MR.GREY_SPACING_TOL
    assert (IND["ramp_low"], IND["ramp_high"]) == (MR.RAMP_TV_LOW,
                                                   MR.RAMP_TV_HIGH)
    assert IND["ramp_steps"] == MR.RAMP_MIN_STEPS
    assert IND["ramp_span"] == MR.RAMP_MIN_SPAN
    assert IND["ramp_even_within"] == MR.RAMP_SPACING_TOL
    assert IND["ramp_others_at"] == MR.RAMP_OTHER_CHANNELS_MIN
    assert IND["strip_min"] == MR.CONTROL_STRIP_MIN
    assert IND["strip_p95_min"] == MR.CONTROL_STRIP_P95_MIN
    assert IND["surface_within"] == MR.SURFACE_GAMUT_TOL
    assert IND["surface_min"] == MR.SURFACE_GAMUT_MIN
    assert IND["outer_fraction"] == MR.OUTER_GAMUT_FRACTION
    assert IND["outer_min"] == MR.OUTER_GAMUT_MIN
    assert IND["evenness_grid"] == MR.EVENNESS_MIN_GRID
    assert IND["evenness_coverage"] == MR.EVENNESS_MIN_PAGE_COVERAGE
    #: the worst-5 % line is not a constant, it is where `_stats` stops having
    #: a worst twentieth: ceil(0.95 n) == n for every n below it
    assert MR._stats([0.0] * (IND["worst5_min"] - 1))["small_sample"]
    assert not MR._stats([0.0] * IND["worst5_min"])["small_sample"]


@pytest.mark.parametrize("req", [r for r, _f, _p in _PAIRS],
                         ids=[r.key for r, _f, _p in _PAIRS])
def test_every_requirement_quotes_a_number_the_app_really_holds(req):
    """The comparison each preset's README line carries has to contain the
    number that is really in the source. A retuned constant with a stale
    sentence beside it is a demo pack that teaches the wrong boundary."""
    names = re.findall(r"\b([A-Z][A-Z0-9_]{3,})\b", req.comparison)
    numbers = re.findall(r"\d+(?:\.\d+)?", req.comparison)
    known = {n: getattr(MR, n) for n in names if hasattr(MR, n)}
    if not known:
        # R01 is a presence, not a number ("declaration is None"), and R08's
        # line lives inside `_stats` rather than in a constant. Both are
        # checked by name in the test above; there is nothing to compare here.
        return
    assert numbers, req.key
    for name, value in known.items():
        assert any(abs(float(t) - float(value)) < 1e-9 for t in numbers), (
            req.key, name, value, numbers)


# ---------------------------------------------------------------------------
# 5. the pack's arithmetic about itself, and the shipping of it
# ---------------------------------------------------------------------------
def test_the_package_accounts_for_every_reason_the_window_can_show(dialog):
    covered = {r.reason for r in GEN.REQUIREMENTS}
    covered |= {c for r in GEN.REQUIREMENTS for c in r.also}
    unreachable = set(GEN.UNREACHABLE)
    assert not (covered & unreachable), covered & unreachable
    assert covered | unreachable == PE.classified_reasons(), (
        "unaccounted: "
        f"{sorted(PE.classified_reasons() - covered - unreachable)}")


def test_every_reachable_reason_has_at_least_one_requirement_behind_it(dialog):
    """And the other direction: a code no requirement claims is a detection
    nothing in the pack exercises."""
    seen = set()
    for d in GEN.DEMOS:
        if d.no_chart or d.corrupt:
            continue
        seen |= set(_withheld(dialog, d).values())
    claimed = {r.reason for r in GEN.REQUIREMENTS}
    claimed |= {c for r in GEN.REQUIREMENTS for c in r.also}
    assert seen == claimed, (sorted(seen), sorted(claimed))


def test_the_unreachable_four_really_are_unreachable_here(dialog):
    seen = set()
    for row in dialog._rows:
        seen |= {why for _rid, why in row.assessment.missing}
    for code in GEN.UNREACHABLE:
        if code in CONSTANTS:
            assert code in seen, f"every preset should read {code}"
        elif code in GEN.SHOWN_BY_BUILTINS:
            # the evenness codes the built-in ENGINE presets show, from their
            # predicted page grid (#182, 2026-09-22); no demo here can
            assert code in seen, f"no built-in preset showed {code}"
        else:
            assert code not in seen, code


def test_each_demo_carries_its_own_patch_set(dialog, installed):
    from core.preset_store import sidecar_path
    for d in GEN.DEMOS:
        sc = sidecar_path("create_chart", d.name, ".ti1")
        assert sc.is_file() is (not d.no_chart), d.name


def test_the_readme_names_every_requirement_its_line_and_both_folders(
        installed):
    """The download is useless without the folder, and the pack is useless as
    evidence without the operator beside each boundary: "at least 8" fails at 7
    and passes at 8, and a reader has to be able to check that rather than
    believe it."""
    text = (installed / "README.txt").read_text(encoding="utf-8")
    assert "Library/Preferences/ChromIQ/presets/Create Chart" in text
    assert "%APPDATA%\\ChromIQ\\presets\\Create Chart" in text
    assert "RESTART" in text.upper()
    for d in GEN.DEMOS:
        assert d.name in text, d.name
    for r in GEN.REQUIREMENTS:
        assert r.comparison in text, r.key
        assert r.source in text, r.key


def test_no_demo_name_or_blurb_carries_an_em_dash():
    for d in GEN.DEMOS:
        assert "—" not in d.name, d.name
        assert "—" not in d.blurb, d.name
    for r in GEN.REQUIREMENTS:
        assert "—" not in r.text, r.key
        assert "—" not in r.also_why, r.key
    assert "—" not in GEN.readme()


def test_a_pack_without_the_preset_folder_is_incomplete(tmp_path):
    """Knut asked for them IN the downloadable package, and a pack has been
    published missing part of itself before (B8-393)."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import make_report_limit_demos as PACK

    pack = tmp_path / "ChromIQ-Report-Limit-Demos"
    pack.mkdir()
    for name, _plans in PACK.PROJECTS:
        (pack / name).mkdir()
    (pack / "README.txt").write_text("x", encoding="utf-8")
    (pack / "intended-vs-actual.json").write_text("[]", encoding="utf-8")
    gaps = PACK.verify_pack(pack)
    assert f"file missing: {GEN.FOLDER}" in gaps, gaps

    GEN.build(pack / GEN.FOLDER)
    gaps = PACK.verify_pack(pack)
    assert not [g for g in gaps if GEN.FOLDER in g], gaps


def test_the_pack_readme_sends_the_user_to_the_right_folder(tmp_path):
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import make_report_limit_demos as PACK

    text = PACK.readme([], [], PACK.coverage(tmp_path, []), tmp_path)
    assert GEN.FOLDER in text
    assert "~/Library/Preferences/ChromIQ/presets/Create Chart" in text
    assert "%APPDATA%\\ChromIQ\\presets\\Create Chart" in text
    assert "restart ChromIQ" in text
