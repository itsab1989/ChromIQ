"""Sample area is capped, per chart, at what a hexagon can actually give.

`scanin` reads a RECTANGLE inside each patch. A hexagonal patch is stored as the
rectangle w x h (flat-to-flat width, row pitch) but the ink is a pointy-top
hexagon whose slanted sides cut that rectangle's corners off — so the read box
escapes the patch long before the 80 % a square patch allows, and because the
next hexagon is flush against this one, escaping means reading the NEIGHBOUR.
That is a switch, not a rate: one percent too far and it happens on every patch.

The limit depends on the patch proportions, so it is computed
(`scanin_runner.hex_max_sample_fraction`) and applied to the spinbox, rather
than being written in a message as "keep it at or below 60 %" — which was both
approximate (60 % is unsafe from h/w ≈ 2.58 upwards) and shown only to the users
who had the feature switched OFF and so could never reach the control.

**AND THAT GEOMETRIC LIMIT IS A CLIFF EDGE, NOT A SETTING.** At it the read
box's corner lands exactly ON the slanted side with nothing to spare: measured
on the real CR30 honeycomb (pwid 12.000, plen 10.392) the paper between them is
+0.021 mm at 64 %, +0.214 mm at 60 % and +0.464 mm at 55 %; on a 6 mm
honeycomb, +0.010 / +0.107 / +0.232 mm. Knut was asked on #182 whether 64 %
should come down so a small alignment error cannot put a corner on the patch
next door, and ruled: *"Yes, a maximum of 55% is good."* So
`scanin_runner.HEX_SAMPLE_AREA_MAX` stands in front of the geometry and
`hex_sample_area_cap` offers the SMALLER of the two — a ringed patch whose ink
supports only 49 % still gets 49. Rectangular charts keep 80 %, and the
measurement behind that decision is in `HEX_SAMPLE_AREA_MAX`'s own note.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.scanin_runner import (HEX_SAMPLE_AREA_MAX,
                                    hex_max_sample_fraction,
                                    hex_sample_area_cap, sample_margin)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _in_hexagon(x: float, y: float, w: float, h: float) -> bool:
    """Pointy-top hexagon, vertices (0, ±2h/3) and (±w/2, ±h/3), centred on 0."""
    x, y = abs(x), abs(y)
    return y <= 2.0 * h / 3.0 + 1e-12 and x <= (w / 2.0) * (2.0 - 3.0 * y / h) + 1e-12


@pytest.mark.parametrize("hw", [0.5, 0.75, 0.866, 1.0, 1.25, 1.5, 2.0, 2.58, 3.0, 4.0])
def test_the_cap_is_exactly_where_the_box_leaves_the_hexagon(hw):
    """Both halves, or the number is decoration: AT the cap the read box still
    fits, and one percent above it does not. The second assert is the one that
    matters — a cap that is merely 'safe' could be needlessly small, and a test
    that only checks the safe side passes for a hard-coded 20 %."""
    w, h = 1.0, hw
    f = hex_max_sample_fraction(w, h)

    def corner(frac):
        m = sample_margin(w, h, frac)
        return (w / 2.0 - m, h / 2.0 - m)

    assert _in_hexagon(*corner(f), w, h), f"h/w={hw}: the cap itself does not fit"
    x, y = corner(min(1.0, f + 0.01))
    assert not _in_hexagon(x, y, w, h), (
        f"h/w={hw}: {f:.4f} is not the limit — {f + 0.01:.4f} still fits, so the "
        "cap is smaller than it needs to be")


def test_the_cap_moves_with_the_shape_and_60_percent_is_not_always_safe():
    """The numbers that made this a computation instead of a constant."""
    assert round(hex_max_sample_fraction(1.0, 1.0) * 100, 2) == 64.00
    assert round(hex_max_sample_fraction(1.0, 2.0) * 100, 2) == 61.22
    assert round(hex_max_sample_fraction(1.0, 0.866) * 100, 2) == 64.43
    # The old advice, tested where it fails: a tall patch cannot take 60 %.
    assert hex_max_sample_fraction(1.0, 2.59) < 0.60
    assert hex_max_sample_fraction(1.0, 3.0) < 0.60
    # Scale-free: only the ratio can matter.
    assert hex_max_sample_fraction(7.0, 6.06) == pytest.approx(
        hex_max_sample_fraction(70.0, 60.6))
    assert hex_max_sample_fraction(0.0, 1.0) == 1.0        # nothing to clamp


def _hex_chart(tmp_path, n=60, w_mm=12.0, hflag=True):
    from workflow.layout_engine import chart as le_chart
    ti1 = tmp_path / "p.ti1"
    lines = ["CTI1", "", 'DESCRIPTOR "x"', 'ORIGINATOR "x"', 'KEYWORD "SAMPLE_LOC"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    lines += [f"{i+1} {float((i*37) % 101)} {float((i*53) % 101)} "
              f"{float((i*71) % 101)} 40 45 50" for i in range(n)]
    lines += ["END_DATA", ""]
    ti1.write_text("\n".join(lines), encoding="utf-8")
    stem = tmp_path / "HexChart"
    le_chart.build_chart(ti1, stem, instrument="SS", hflag=hflag,
                         pscale=w_mm / 7.0, paper="A4", border=6.0, dpi=200,
                         randomize=False)
    strips = json.loads(stem.with_suffix(".strips.json").read_text(encoding="utf-8"))
    return {"engine": "chromiq", "dpi": 200, "paper_mm": [210.0, 297.0],
            "patches": strips["patches"],
            "recipe": {"instrument": "SS", "hflag": hflag}}


def _dialog(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    s = AppSettings()
    # THE OUTPUT ROOT HAS TO BE PINNED. `custom_output_path` defaults to "",
    # and "" IS ~/ChromIQ — the owner's own projects folder. This window
    # provisions the user's `scanner-test-targets` folder as it opens, so a
    # bare AppSettings() writes into it on every gate run; the session tripwire
    # in conftest caught `scanner-test-targets/.provisioned.json` being
    # rewritten. Sandboxing QSettings is NOT enough on its own, which is the
    # trap that guard's own message names.
    s.set("custom_output_path", str(tmp_path / "out"))
    return ScannerProfileDialog(ArgyllRunner(s), s)


@pytest.mark.parametrize("hflag,expect_capped", [(True, True), (False, False)])
def test_the_dialog_caps_the_spinbox_from_the_chart_it_loaded(qapp, tmp_path,
                                                             hflag, expect_capped):
    """Driven through `_load_page_grid`, the real code path the page selector
    runs — not by calling the helper directly, which would still pass if nobody
    ever called it. A rectangular chart must keep the full 80 %."""
    d = _dialog(qapp, tmp_path)
    d._layout = _hex_chart(tmp_path, hflag=hflag)
    d._page = 0
    d._sample_area.setValue(80)
    d._load_page_grid()

    patches = [p for p in d._layout["patches"] if p["page"] == 0]
    w = sorted(p["w"] for p in patches)[len(patches) // 2]
    h = sorted(p["h"] for p in patches)[len(patches) // 2]
    # `hex_sample_area_cap`, not the geometric function: Knut's #182 ruling of
    # 2026-09-11 puts a policy ceiling of 55 % in front of the geometry, so the
    # spin box offers the SMALLER of the two.
    want = int(hex_sample_area_cap(w, h) * 100) if expect_capped else 80

    assert d._sample_area.maximum() == want
    assert d._sample_area.value() == want, (
        "a value above the cap must come DOWN — leaving it there would read the "
        "neighbouring hexagons on every patch")
    if expect_capped:
        assert want == int(HEX_SAMPLE_AREA_MAX * 100), (
            f"{want} % — a honeycomb of ordinary proportions is offered "
            f"{int(HEX_SAMPLE_AREA_MAX * 100)} %, Knut's ceiling, because the "
            "geometry allows more than that")
        assert "%" in d._sample_area.toolTip(), "the cap must explain itself"
    else:
        assert d._sample_area.toolTip() == ""
    d.deleteLater()


def test_a_stored_sixty_per_cent_comes_down_on_a_honeycomb(qapp, tmp_path):
    """What happens to somebody who already saved 60 % as their default.

    Sample area is not a per-project setting: it lives in the one
    `scanner_read_options` bucket that "Save as Defaults" writes, and
    `_apply_read_vals` puts it into the spin box when the window is built,
    before any chart has been chosen and while the maximum is still 80. So a
    stored 60 arrives intact and is only pulled down when a honeycomb is
    loaded — by `setMaximum`, which emits `valueChanged`, so the drawn read
    boxes and every read follow it without extra wiring.

    Both halves: it comes down on a honeycomb and it is LEFT ALONE on a
    rectangular chart, where Knut's ruling does not apply and 60 is a perfectly
    good setting the user chose.
    """
    d = _dialog(qapp, tmp_path)
    d._apply_read_vals({"sample_area": 60})
    assert d._sample_area.value() == 60, "the stored default did not arrive"

    seen = []
    d._sample_area.valueChanged.connect(seen.append)
    d._page = 0
    (tmp_path / "hex").mkdir()
    d._layout = _hex_chart(tmp_path / "hex", hflag=True)
    d._load_page_grid()
    assert d._sample_area.value() == int(HEX_SAMPLE_AREA_MAX * 100)
    assert seen, ("the value changed without telling anyone, so the drawn read "
                  "boxes still show 60 % of each patch")

    (tmp_path / "rect").mkdir()
    d._layout = _hex_chart(tmp_path / "rect", hflag=False)
    d._load_page_grid()
    assert d._sample_area.maximum() == 80
    assert d._sample_area.value() == int(HEX_SAMPLE_AREA_MAX * 100), (
        "a value pulled down by a honeycomb stays where it was put when the "
        "cap lifts; Qt does not remember what it was before")
    d.deleteLater()


def test_the_cap_lifts_again_when_a_rectangular_chart_is_loaded(qapp, tmp_path):
    """The clamp is a property of the chart on screen, not a one-way latch —
    a user who opens a hexagonal chart and then a square one gets 80 % back."""
    d = _dialog(qapp, tmp_path)
    d._page = 0
    (tmp_path / "hex").mkdir()
    d._layout = _hex_chart(tmp_path / "hex", hflag=True)
    d._load_page_grid()
    capped = d._sample_area.maximum()
    assert capped < 80

    (tmp_path / "rect").mkdir()
    d._layout = _hex_chart(tmp_path / "rect", hflag=False)
    d._load_page_grid()
    assert d._sample_area.maximum() == 80
    d.deleteLater()


def test_a_chart_with_no_patch_geometry_is_not_capped(qapp, tmp_path):
    """A printtarg chart arrives as captured .cht pages, with no per-patch
    rects to measure — it must fall back to 80 %, never to a guess."""
    d = _dialog(qapp, tmp_path)
    d._page = 0
    d._layout = {"cht_pages": [], "patches": []}
    d._load_page_grid()
    assert d._sample_area.maximum() == 80
    d.deleteLater()


def test_a_printtarg_honeycomb_is_capped_although_it_has_no_recipe(qapp, tmp_path):
    """The layout engine is the default and writes a recipe, but Manual mode can
    still lay a SpectroScan chart out with printtarg, and `printtarg -h` draws
    hexagons there too. Such a chart reaches the tool with per-patch geometry and
    NO recipe: printtarg will not emit a .cht for hexagons at all ("Can only
    select hexagonal patches if no scan recognition is needed - ignored!"), so
    the capture is re-run without them, its locs disagree with the chart's .ti2,
    ChromIQ's guard drops it, and the geometry is derived from the rendered sheet
    instead. A shape test that reads only the recipe sees a rectangular chart and
    lifts the cap on a honeycomb."""
    d = _dialog(qapp, tmp_path)
    d._page = 0
    d._layout = _hex_chart(tmp_path, hflag=True)
    d._layout.pop("recipe")                      # as the render-derived path leaves it
    d._chart_settings = {"printtarg-i": {"enabled": True, "value": "SS"},
                         "printtarg-h": {"enabled": True, "value": True}}
    d._sample_area.setValue(80)
    d._load_page_grid()
    assert d._sample_area.maximum() < 80, (
        "a printtarg honeycomb was left at 80 % — it would read the "
        "neighbouring hexagon on every patch")
    d.deleteLater()


def test_the_same_flag_on_a_colormunki_is_not_a_honeycomb(qapp, tmp_path):
    """`-h` means double density on the ColorMunki: squares, twice as many.
    Reading the flag without the instrument would cap a chart that has no
    hexagons anywhere near it."""
    from workflow.hex_support import settings_are_hexagonal
    cm = {"printtarg-i": {"enabled": True, "value": "CM"},
          "printtarg-h": {"enabled": True, "value": True}}
    assert settings_are_hexagonal(cm) is False
    assert settings_are_hexagonal({"printtarg-i": {"value": "SS"},
                                   "printtarg-h": {"value": True}}) is True
    assert settings_are_hexagonal({"printtarg-i": {"value": "SS"}}) is False
    for junk in (None, {}, {"printtarg-i": "SS"}, "nonsense", 7):
        assert settings_are_hexagonal(junk) in (True, False)


def test_a_chart_record_cannot_leak_into_the_next_chart(qapp, tmp_path):
    """`_set_chart` clears the record before it reads the new one. Without that,
    opening a honeycomb and then a square chart with no sidecar would keep
    capping the square one — a limit the user cannot explain or clear."""
    import inspect
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._set_chart)
    body = src.split("base = _chart_base(picked)", 1)[1]
    assert "self._chart_settings = {}" in body.split("chart_is_hexagonal")[0], (
        "the previous chart's shape record must be cleared before the new "
        "chart is examined, not after"
    )


def test_knuts_ceiling_stands_in_front_of_the_geometry():
    """#182, 2026-09-11. He was asked whether 64 % should come down so a small
    alignment error cannot put a corner on the patch next door: *"Yes, a
    maximum of 55% is good."*

    Both halves, or the number is decoration. The ceiling must BITE on a
    honeycomb whose geometry allows more — a regular hexagon allows 64.43 % —
    and it must NOT raise a chart whose geometry allows less, which a ringed
    patch does: the ink a scanner may read there is the inset hexagon, and
    offering 55 % of the slot would average spacer colour into every patch.
    """
    # 1. it bites where the geometry is generous
    for w, h in ((1.0, 0.866), (1.0, 1.0), (12.0, 10.392)):
        assert hex_max_sample_fraction(w, h) > HEX_SAMPLE_AREA_MAX
        assert hex_sample_area_cap(w, h) == pytest.approx(HEX_SAMPLE_AREA_MAX)
    # 2. and the geometry still wins where it is the smaller of the two
    dpi_scale = 300.0 / 25.4
    tight = hex_sample_area_cap(12.0 * dpi_scale, 10.392 * dpi_scale,
                                ring_mm=1.3 * dpi_scale)
    assert tight < HEX_SAMPLE_AREA_MAX, (
        f"a 1.3 mm ring leaves {tight:.4f}; the policy ceiling must never "
        "raise a chart above what its own ink can give")
    assert tight == pytest.approx(
        hex_max_sample_fraction(12.0 * dpi_scale, 10.392 * dpi_scale,
                                ring_mm=1.3 * dpi_scale))
    # 3. a tall patch whose geometry is already under the ceiling is untouched.
    #    h/w = 8 allows 0.5485, and h/w = 4 does NOT (0.5785) -- the shape has
    #    to be genuinely tighter than 55 % for this half to mean anything.
    assert hex_max_sample_fraction(1.0, 8.0) < HEX_SAMPLE_AREA_MAX
    assert hex_sample_area_cap(1.0, 8.0) == pytest.approx(
        hex_max_sample_fraction(1.0, 8.0))


def test_the_ceiling_leaves_real_paper_between_the_box_and_the_hexagon():
    """The number is a distance, so measure the distance. At the geometric
    limit the read box's corner lands ON the slanted side with nothing to
    spare; the point of Knut's ceiling is that it does not.

    Measured here on the real CR30 honeycomb (pwid 12.000, plen 10.392) and on
    a small 6 mm one, in millimetres of paper between the box corner and the
    side it must stay behind."""
    from math import sqrt

    def clearance(w, h, frac):
        m = sample_margin(w, h, frac)
        px, py = w / 2.0 - m, h / 2.0 - m
        a, b, c = h / 3.0, w / 2.0, -w * h / 3.0
        return -(a * px + b * py + c) / sqrt(a * a + b * b)

    for w, h, at_64, at_55 in ((12.0, 10.392, 0.021, 0.464),
                               (6.0, 5.196, 0.010, 0.232)):
        assert clearance(w, h, 0.64) == pytest.approx(at_64, abs=0.005)
        assert clearance(w, h, HEX_SAMPLE_AREA_MAX) == pytest.approx(
            at_55, abs=0.005)
        # the whole point: the ceiling buys back at least a fifth of a
        # millimetre on the smallest honeycomb in the family
        assert clearance(w, h, HEX_SAMPLE_AREA_MAX) > 0.2


def test_square_patches_keep_the_full_eighty_percent():
    """Knut's 55 % is an answer about a HONEYCOMB, and it is not applied to
    rectangular charts. Measured, because the claim is a measurement: on a
    square patch the inset IS the clearance (there is no slanted side to escape
    past), and at 80 % it is already more paper than a honeycomb gets at 60 %.
    """
    for w in (6.0, 7.5, 8.0, 12.0):
        assert sample_margin(w, w, 0.80) >= 0.31
    # …and a 6 mm honeycomb at 60 % has 0.107 mm, an order of magnitude less
    # than the 0.317 mm a 6 mm square patch has at 80 %.
    assert sample_margin(6.0, 6.0, 0.80) > 0.3
    # the cap function is never consulted for a rectangular chart at all: the
    # dialog branches on `hexagonal` first (see
    # test_the_cap_lifts_again_when_a_rectangular_chart_is_loaded).
    import inspect
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._clamp_sample_area)
    assert "cap = 80" in src and "if hexagonal and patches:" in src
