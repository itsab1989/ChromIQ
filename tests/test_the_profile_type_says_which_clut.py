"""B8-19 — the Profile type control tells the truth, and tells it per mode.

The shipped help said the two cLUTs were interchangeable and that the Lab one
"sometimes gives slightly smoother neutrals". Nothing measured that. What AGENT-
AD then measured, on two real scans with every figure scored on patches the fit
never saw, was a different difference entirely: below about a hundred fit
patches shaper+matrix is the most accurate type, above it a cLUT is — and a Lab
cLUT cannot encode anything above its chart's white, so a neutral ramp through
one reads L* 100.4 flat from device 82 upward where the XYZ table and
shaper+matrix both run on to L* ~119.5. An IT8's own white is only ~80 of 100 on
a real scan, so that ceiling sits inside the range a scanner uses every day.

Three things follow, and this file holds all three in place:

1. the unsupported sentence is gone, from the source AND from every catalogue;
2. a user who wants a cLUT is pointed at the XYZ one — in SCANNER/CAMERA mode
   only, because Argyll's own default for an OUTPUT profile is the Lab cLUT and
   nothing a printer prints is lighter than the paper it prints on, so the
   measurement does not transfer. The window must never carry both markers on
   one item, or contradict the "(default)" one it already shows;
3. once the window knows the patch count, it says so — as a note inside the ⓘ
   that changes no setting and disappears when it stops being true.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication            # noqa: E402

from ui.dialogs import scanner_colprof              # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

#: The exact sentence this whole item exists to remove. It must not come back,
#: in the source or in a translation that outlived its key.
UNSUPPORTED = "sometimes gives slightly smoother neutrals"


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def _dialog(_app, out_dir):
    from tests.test_scanin_dialog import _FakeSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    return ScannerProfileDialog(
        object(), _FakeSettings(custom_output_path=str(out_dir)))


def _labels(combo) -> list[str]:
    return [combo.itemText(i) for i in range(combo.count())]


# ---------------------------------------------------------------- 1. the claim
def test_no_user_facing_string_anywhere_still_makes_the_claim():
    """Every `tr()` source string in the app, not just this window's — the same
    sentence was in two places and the second one is easy to miss."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from i18n_extract import extract_keys
    guilty = sorted(k for k in extract_keys() if UNSUPPORTED in k)
    assert not guilty, (
        f"{len(guilty)} user-facing string(s) still tell the user the Lab "
        f"cLUT gives smoother neutrals. Nothing measured that — B8-19 "
        f"measured the two cLUTs landing close together, with neither "
        f"consistently ahead: {[g[:70] for g in guilty]}")


def test_the_help_the_window_actually_shows_does_not_make_the_claim():
    for printer in (False, True):
        assert UNSUPPORTED not in scanner_colprof.ptype_help(printer)[1]


def test_the_unsupported_neutrals_claim_is_gone_from_every_catalogue():
    """A retired English key leaves twelve translations of it behind."""
    guilty = []
    for cat in sorted((ROOT / "data" / "i18n").glob("*.json")):
        with open(cat, encoding="utf-8") as fh:
            if any(UNSUPPORTED in k for k in json.load(fh)):
                guilty.append(cat.name)
    assert not guilty, f"the retired claim is still a key in: {guilty}"


# ------------------------------------------------- 2. which cLUT, and per mode
def test_the_recommended_clut_is_xyz_for_a_scanner_and_nothing_for_a_printer():
    assert scanner_colprof.PTYPE_RECOMMENDED_CLUT[False] == "x"
    assert scanner_colprof.PTYPE_RECOMMENDED_CLUT[True] is None
    # …and it is keyed exactly like the default it has to sit beside.
    assert (set(scanner_colprof.PTYPE_RECOMMENDED_CLUT)
            == set(scanner_colprof.PTYPE_DEFAULT))


def test_the_dropdown_points_at_the_xyz_clut_in_scanner_mode(_app, tmp_path):
    dlg = _dialog(_app, tmp_path)
    try:
        labels = _labels(dlg._ptype)
        assert "cLUT — XYZ table (recommended cLUT)" in labels
        assert "cLUT — Lab table" in labels          # plain: still a real choice
        assert "Shaper + matrix (default)" in labels  # the default has not moved
        # Neither marker may be dropped, and neither may land twice.
        assert sum("(recommended cLUT)" in l for l in labels) == 1
        assert sum("(default)" in l for l in labels) == 1
    finally:
        dlg.deleteLater()


def test_a_recommendation_is_never_the_default_and_is_never_swallowed(_app, tmp_path):
    """A "(default)" that also said "(recommended cLUT)" would be the window
    contradicting itself — and the printer default IS a cLUT.

    Written this way after the mutation run: `_mark_default_combos` lets the
    default win, so setting the recommendation EQUAL to the default does not
    produce a double-marked item at all — it silently drops the recommendation,
    and a test that only looked for a double marker would have passed. The
    invariant that actually holds is the pair: a recommendation must differ from
    that mode's default, and when there is one it must be on screen exactly
    once.
    """
    dlg = _dialog(_app, tmp_path)
    try:
        for printer in (False, True):
            dlg._printer_cb.setChecked(printer)
            labels = _labels(dlg._ptype)
            rec = scanner_colprof.PTYPE_RECOMMENDED_CLUT[printer]
            assert not [l for l in labels
                        if "(default)" in l and "(recommended cLUT)" in l], labels
            assert sum("(default)" in l for l in labels) == 1, labels
            if rec is None:
                assert not any("(recommended cLUT)" in l for l in labels), labels
                continue
            assert rec != scanner_colprof.PTYPE_DEFAULT[printer], (
                "recommending the default is not a recommendation, and this "
                "window would show nothing for it")
            assert sum("(recommended cLUT)" in l for l in labels) == 1, labels
            marked = dlg._ptype.itemData(
                next(i for i, l in enumerate(labels) if "(recommended cLUT)" in l))
            assert marked == rec
    finally:
        dlg.deleteLater()


def test_printer_mode_recommends_nothing_and_keeps_the_lab_default(_app, tmp_path):
    """Argyll's own default for an output profile is -al, and the scanner
    measurement is about capturing above a chart's white — which a printer never
    has to do. So nothing is claimed here, and the "(default)" marker stands
    alone."""
    dlg = _dialog(_app, tmp_path)
    try:
        dlg._printer_cb.setChecked(True)
        labels = _labels(dlg._ptype)
        assert "cLUT — Lab table (default)" in labels
        assert not any("(recommended cLUT)" in l for l in labels), labels
        # …and it comes back when the tick does.
        dlg._printer_cb.setChecked(False)
        assert "cLUT — XYZ table (recommended cLUT)" in _labels(dlg._ptype)
    finally:
        dlg.deleteLater()


# --------------------------------------------------------- 3. the help, by mode
def test_the_help_is_mode_aware_and_each_mode_names_its_own_default():
    scanner_title, scanner = scanner_colprof.ptype_help(False)
    printer_title, printer = scanner_colprof.ptype_help(True)
    assert scanner_title == printer_title == "Profile type and quality"
    assert scanner != printer
    # Each body must say when each type is worth choosing, in a size a beginner
    # can act on, and must point at where they can read their own count.
    assert "about a hundred patches" in scanner
    assert "two hundred patches or more" in scanner
    assert "288" in scanner and "864" in scanner
    assert "patch count is printed beside each target's name" in scanner
    # The lightness ceiling in plain words, never as "L* 100.4".
    assert "lighter than your target's own white patch" in scanner
    assert "L*" not in scanner and "PCS" not in scanner
    assert "L*" not in printer and "PCS" not in printer
    # The printer body must not carry the scanner recommendation.
    assert "the Lab default stands" in printer
    assert "the XYZ table is the one to take" in scanner


def test_the_help_follows_the_printer_tick_in_the_real_window(_app, tmp_path):
    dlg = _dialog(_app, tmp_path)
    try:
        assert dlg._ptype_tip.dialog_body() == scanner_colprof.ptype_help(False)[1]
        dlg._printer_cb.setChecked(True)
        assert dlg._ptype_tip.dialog_body() == scanner_colprof.ptype_help(True)[1]
        dlg._printer_cb.setChecked(False)
        assert dlg._ptype_tip.dialog_body() == scanner_colprof.ptype_help(False)[1]
    finally:
        dlg.deleteLater()


# ------------------------------------------------------ 4. the live patch-count note
@pytest.mark.parametrize("printer,ptype,n,expect", [
    # nothing is known yet -> nothing is said, in any mode or type
    (False, "s", None, ""),
    (False, "l", None, ""),
    (False, "x", 0, ""),
    # a big target and the formula type -> point at the XYZ table
    (False, "s", 288, "big enough for a look-up table"),
    (False, "s", 200, "big enough for a look-up table"),
    # …but not in the shallow middle, and never for a type already on a table
    (False, "s", 199, ""),
    (False, "s", 150, ""),
    (False, "x", 288, ""),
    # a small target and a table type -> point back at shaper+matrix
    (False, "l", 48, "on the small side for a look-up table"),
    (False, "x", 24, "on the small side for a look-up table"),
    (False, "x", 100, ""),                  # the crossover itself: say nothing
    # the Lab ceiling, whenever Lab is chosen and the size does not overrule it
    (False, "l", 288, "cannot describe anything lighter"),
    (False, "l", 150, "cannot describe anything lighter"),
    # printer mode says nothing at all: nothing was measured about it
    (True, "s", 288, ""),
    (True, "l", 24, ""),
    (True, "l", 288, ""),
])
def test_the_live_note_fires_only_where_the_measurement_is_unambiguous(
        printer, ptype, n, expect):
    note = scanner_colprof.ptype_advice(printer, ptype, n)
    if expect:
        assert expect in note
        # It is a suggestion. It must say so, and say nothing was changed.
        assert "suggestion" in note or "choice stands" in note
    else:
        assert note == ""


def test_the_note_reaches_the_tooltip_and_leaves_again(_app, tmp_path):
    """The note lives inside the ⓘ — `set_live_note` — so it costs no layout and
    cannot nag. Its first line reaches the hover tooltip; the whole of it goes
    in front of the standing help."""
    dlg = _dialog(_app, tmp_path)
    try:
        assert dlg._known_patch_count() is None
        assert dlg._ptype_tip.live_note() == ""        # nothing known, nothing said
        dlg._layout = {"patches": [{"page": 0} for _ in range(288)]}
        dlg._refresh()
        assert dlg._known_patch_count() == 288
        note = dlg._ptype_tip.live_note()
        assert "288 patches" in note
        assert note in dlg._ptype_tip.dialog_body()    # carried in FRONT of the help
        assert dlg._ptype_tip.dialog_body().endswith(
            scanner_colprof.ptype_help(False)[1])
        assert note.splitlines()[0] in dlg._ptype_tip.toolTip()
        # Take the advice and the note goes: it never nags about a done thing.
        dlg._ptype.setCurrentIndex(dlg._ptype.findData("x"))
        assert dlg._ptype_tip.live_note() == ""
        # Ticking the printer box silences it too — nothing was measured there.
        dlg._ptype.setCurrentIndex(dlg._ptype.findData("s"))
        assert dlg._ptype_tip.live_note()
        dlg._printer_cb.setChecked(True)
        assert dlg._ptype_tip.live_note() == ""
    finally:
        dlg.deleteLater()


def test_the_note_never_changes_a_setting(_app, tmp_path):
    """An automatic switch was considered and rejected (B8-19): the window
    learns the count only after the type is set, and the crossover is shallow.
    So the advice must be advice."""
    dlg = _dialog(_app, tmp_path)
    try:
        before = dlg._current_main_vals()
        dlg._layout = {"patches": [{"page": 0} for _ in range(864)]}
        dlg._refresh()
        assert dlg._ptype_tip.live_note()          # it did fire…
        assert dlg._current_main_vals() == before  # …and it moved nothing
        assert "-as" in dlg._cmd_preview.text()
    finally:
        dlg.deleteLater()


def test_a_multipage_target_is_counted_whole(_app, tmp_path):
    """One profile is built from every page, so the count that decides the type
    is the whole set's — a 3 × 288 set is a big target, not a 288-patch one."""
    from workflow.standard_targets import StandardTarget
    dlg = _dialog(_app, tmp_path)
    try:
        cht = tmp_path / "fake.cht"
        cht.write_text("", encoding="utf-8")
        target = StandardTarget(key="fake", name="Fake set",
                                cht_paths=(cht, cht, cht),
                                patch_counts=(288, 288, 288))
        dlg._std_targets["fake"] = target
        dlg._target_combo.addItem("Fake set", "fake")
        dlg._mode_standard.setChecked(True)
        dlg._target_combo.setCurrentIndex(dlg._target_combo.findData("fake"))
        assert dlg._known_patch_count() == 864
    finally:
        dlg.deleteLater()
