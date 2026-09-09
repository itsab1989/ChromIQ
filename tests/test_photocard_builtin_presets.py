"""Nelson Lau's two photo-card built-ins (10 x 15 cm and 13 x 18 cm, i1Pro).

The first built-in charts for the sizes photo paper is actually sold in.
Prebuilt-files presets (kind 1 in ``docs/dev_builtin_presets.md``): a complete
target is bundled and copied into the run, so nothing runs at selection and
everything a user gets is decided by what is on disk here.

WHAT THESE TESTS EXIST TO CATCH. A prebuilt bundle can be replaced by a
regenerated one without a line of code changing, so every property the preset's
NAME promises is asserted against the FILES, not against the registry:

* the sheet really is 100 x 150 / 130 x 180 mm at the dpi the TIFF declares;
* the patch count, the page count and the strip layout match the name;
* the .ti1 and the .ti2 are the same patch set in the same order;
* every strip is full, so no page carries a short final strip;
* the layout panel is seeded with the sheet the chart was laid out for, as a
  printtarg CUSTOM size, and never with the silent "A4" fallback.

The last one is the one that would fail silently in the app: an unknown paper
folder used to return "A4", so unlocking the layout and re-generating would lay
a photo-card chart out on A4 with nothing said.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import tifffile

from core.resource_path import resource_path
from ui.tabs.tab_chart import (BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS,
                               BUILTIN_PRESET_LABELS, PHOTOCARD600_PRESET_KEY,
                               PHOTOCARD600_PRESET_LABEL,
                               PHOTOCARD648_PRESET_KEY,
                               PHOTOCARD648_PRESET_LABEL, PREBUILT_PRESETS,
                               PREBUILT_PRESET_NOTES, TabChart,
                               _prebuilt_paper)
from workflow.ti2_relayout import analyze_randomisation

#: key -> everything the preset's own name and label claim about the chart.
#: (asset leaf, patches, pages, strips per page, steps in pass, sheet mm,
#:  printtarg -p, paper as it is shown)
CHARTS = {
    PHOTOCARD600_PRESET_KEY: dict(
        leaf="i1pro/100x150/photocard600", patches=600, pages=4,
        strips_per_page=10, steps=15, sheet_mm=(100.0, 150.0),
        paper_code="100x150", paper_label="10 × 15 cm (100 × 150 mm)"),
    PHOTOCARD648_PRESET_KEY: dict(
        leaf="i1pro/130x180/photocard648", patches=648, pages=3,
        strips_per_page=12, steps=18, sheet_mm=(130.0, 180.0),
        paper_code="130x180", paper_label="13 × 18 cm (130 × 180 mm)"),
}

KEYS = list(CHARTS)


def _stem(key: str) -> Path:
    return resource_path(PREBUILT_PRESETS[key][0])


def _cgats(path: Path) -> tuple[dict, list[dict]]:
    """(keywords, rows) for a .ti1 / .ti2, rows keyed by the declared fields."""
    txt = path.read_text("latin-1")
    kw = dict(re.findall(r'^([A-Z_0-9]+)\s+"([^"]*)"\s*$', txt, re.M))
    fields = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\nEND_DATA_FORMAT",
                       txt, re.S).group(1).split()
    body = re.search(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", txt, re.S).group(1)
    rows = [dict(zip(fields, re.findall(r'"[^"]*"|\S+', line.strip())))
            for line in body.strip().splitlines()]
    return kw, rows


# --------------------------------------------------------------------------
# the registry
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", KEYS)
def test_the_preset_is_registered_everywhere_one_registry_feeds(key):
    """One row must reach the dropdown, the overlay and the delete guard."""
    assert key in PREBUILT_PRESETS
    assert key in BUILTIN_PRESET_KEYS
    label = {PHOTOCARD600_PRESET_KEY: PHOTOCARD600_PRESET_LABEL,
             PHOTOCARD648_PRESET_KEY: PHOTOCARD648_PRESET_LABEL}[key]
    assert label in BUILTIN_PRESET_LABELS, \
        "a built-in missing from BUILTIN_PRESET_LABELS can be shadowed by a " \
        "user preset file of the same name"
    rows = [r for _g, entries in BUILTIN_PRESET_GROUPS for r in entries]
    assert [r for r in rows if r[2] == key], \
        "not in BUILTIN_PRESET_GROUPS, so neither the Presets dropdown nor " \
        "the ★ overlay would list it"


def test_the_photo_cards_head_the_i1pro_group():
    """Smallest sheet first, which is all this block has ever done: it ran
    A4-1110, A4-1160, A4-1944, Letter-1160, Letter-1944, i.e. paper then count.
    These are the two smallest sheets ChromIQ ships a chart for.

    NOT Knut's paper-then-width-then-count rule, which belongs to the Knut
    families further down the same group: a prebuilt bundle stores no patch
    width, which is why these labels carry none."""
    group = next(entries for name, entries in BUILTIN_PRESET_GROUPS
                 if name.startswith("i1Pro /"))
    assert [r[2] for r in group[:2]] == [PHOTOCARD600_PRESET_KEY,
                                         PHOTOCARD648_PRESET_KEY]


@pytest.mark.parametrize("key", KEYS)
def test_the_bundle_is_complete_on_disk(key):
    stem = _stem(key)
    want = CHARTS[key]
    assert str(stem).endswith(want["leaf"].rsplit("/", 1)[-1])
    assert want["leaf"] in PREBUILT_PRESETS[key][0]
    assert stem.with_suffix(".ti1").is_file()
    assert stem.with_suffix(".ti2").is_file()
    assert stem.with_suffix(".channels.json").is_file(), \
        "no derived geometry sidecar — run scripts/derive_prebuilt_geometry.py"
    tiffs = sorted(stem.parent.glob(f"{stem.name}_*.tif"))
    assert len(tiffs) == want["pages"], \
        f"{len(tiffs)} page TIFFs, the name promises {want['pages']}"


# --------------------------------------------------------------------------
# the sheet
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", KEYS)
def test_the_sheet_is_the_size_its_name_promises(key):
    """Measured from each page TIFF's own pixel size and resolution tag, which
    is what the print path uses (`PostScriptGenerator` defaults the page to the
    TIFF's own dimensions).

    THE UNIT IS NOT THE SAME ON EVERY PAGE, and that is not a defect: page 1 of
    each bundle tags its resolution in inches and the rest in centimetres, the
    same mixture the already-shipped bundles carry. Both resolve to 360 dpi.
    What is asserted is the physical size, which is what a printer is given.
    """
    want = CHARTS[key]
    stem = _stem(key)
    pages = sorted(stem.parent.glob(f"{stem.name}_*.tif"))
    assert pages
    for tif in pages:
        with tifffile.TiffFile(tif) as t:
            page = t.pages[0]
            xr = page.tags["XResolution"].value
            yr = page.tags["YResolution"].value
            unit = int(page.tags["ResolutionUnit"].value)
            w_px = int(page.tags["ImageWidth"].value)
            h_px = int(page.tags["ImageLength"].value)
        assert unit in (2, 3), f"{tif.name}: resolution unit {unit} is neither"
        per_inch = 2.54 if unit == 3 else 1.0     # unit 3 counts per centimetre
        dpi_x = xr[0] / xr[1] * per_inch
        dpi_y = yr[0] / yr[1] * per_inch
        assert dpi_x == pytest.approx(360.0, abs=0.01)
        assert dpi_y == pytest.approx(360.0, abs=0.01)
        got = (w_px / dpi_x * 25.4, h_px / dpi_y * 25.4)
        assert got == pytest.approx(want["sheet_mm"], abs=0.1), \
            f"{tif.name} is {got[0]:.2f} x {got[1]:.2f} mm"


@pytest.mark.parametrize("key", KEYS)
def test_the_ti2_paper_size_agrees_with_the_sheet(key):
    """The bundles arrived saying 120x195 / 135x225 for sheets that are
    100x150 / 130x180. `ChartSpec.from_ti2` turns PAPER_SIZE into the paper the
    run records and the Create Chart panel shows when a saved project is
    reopened, so a wrong value is visible to the user."""
    kw, _rows = _cgats(_stem(key).with_suffix(".ti2"))
    w, h = (float(v) for v in kw["PAPER_SIZE"].split("x"))
    assert (w, h) == pytest.approx(CHARTS[key]["sheet_mm"], abs=0.1)


# --------------------------------------------------------------------------
# the patch set
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", KEYS)
def test_the_ti1_and_the_ti2_are_the_same_patch_set(key):
    """Same rows, same order. The device columns differ in the 5th decimal
    (printtarg writes its render quantisation back), so this compares with a
    tolerance rather than by string."""
    stem = _stem(key)
    _k1, r1 = _cgats(stem.with_suffix(".ti1"))
    _k2, r2 = _cgats(stem.with_suffix(".ti2"))
    assert len(r1) == len(r2) == CHARTS[key]["patches"]
    for a, b in zip(r1, r2):
        assert a["SAMPLE_ID"] == b["SAMPLE_ID"]
        for col in ("RGB_R", "RGB_G", "RGB_B"):
            assert float(a[col]) == pytest.approx(float(b[col]), abs=0.01)
        for col in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
            assert float(a[col]) == pytest.approx(float(b[col]), abs=0.001)


@pytest.mark.parametrize("key", KEYS)
def test_every_strip_is_full_so_no_page_ends_short(key):
    """600 = 4 x 10 x 15 and 648 = 3 x 12 x 18, exactly. A regenerated bundle
    that no longer divides evenly would leave a partial final strip, which is
    the case printtarg pads for and this family has never had to."""
    want = CHARTS[key]
    kw, rows = _cgats(_stem(key).with_suffix(".ti2"))
    assert int(kw["STEPS_IN_PASS"]) == want["steps"]
    per_page = [int(n) for n in kw["PASSES_IN_STRIPS2"].split(",")]
    assert per_page == [want["strips_per_page"]] * want["pages"]
    assert sum(per_page) * want["steps"] == want["patches"]

    locs = [r["SAMPLE_LOC"].strip('"') for r in rows]
    assert len(set(locs)) == want["patches"], "a location is used twice"
    by_strip: dict[str, list[int]] = {}
    for loc in locs:
        m = re.fullmatch(r"([A-Z]+)(\d+)", loc)
        by_strip.setdefault(m.group(1), []).append(int(m.group(2)))
    assert len(by_strip) == want["strips_per_page"] * want["pages"]
    for strip, idx in by_strip.items():
        assert sorted(idx) == list(range(1, want["steps"] + 1)), \
            f"strip {strip} is not a full 1..{want['steps']}"


@pytest.mark.parametrize("key", KEYS)
def test_the_layout_is_well_mixed_for_chartread(key):
    """A fixed-order or poorly shuffled chart makes chartread misrecognise
    strips. Run the app's own gate, not a re-implementation."""
    ti2 = _stem(key).with_suffix(".ti2")
    kw, _rows = _cgats(ti2)
    assert "RANDOM_START" in kw, "not randomised, so no bidirectional strip ID"
    report = analyze_randomisation(ti2)
    assert report.safe, report.reason


@pytest.mark.parametrize("key", KEYS)
def test_the_derived_geometry_covers_every_patch(key):
    """The sidecar `_create_prebuilt_target` copies into the run, so a scanner
    target can be built from a chart nothing generated."""
    doc = json.loads(_stem(key).with_suffix(".channels.json")
                     .read_text(encoding="utf-8"))
    layout = doc["layout"]
    assert doc["ink_channels"] == ["r", "g", "b"]
    assert len(layout["patches"]) == CHARTS[key]["patches"]
    assert {p["page"] for p in layout["patches"]} == set(range(CHARTS[key]["pages"]))
    assert layout["paper_mm"] == pytest.approx(list(CHARTS[key]["sheet_mm"]),
                                               abs=0.1)


# --------------------------------------------------------------------------
# what the tab does with it
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", KEYS)
def test_the_layout_panel_is_seeded_with_the_real_sheet(key):
    """THE SILENT ONE. `_prebuilt_paper_code` used to fall back to "A4" for any
    paper folder it did not recognise, so unlocking the layout and
    re-generating would have laid a photo card out on A4 without a word."""
    assert TabChart._prebuilt_paper_code(key) == CHARTS[key]["paper_code"]
    assert TabChart._prebuilt_instrument(key) == "i1"


@pytest.mark.parametrize("key", KEYS)
def test_the_paper_is_named_the_way_the_paper_is_sold(key):
    assert _prebuilt_paper(key) == CHARTS[key]["paper_label"]


def test_an_unknown_paper_folder_still_falls_back_rather_than_raising():
    """The named-folder map and the WxH branch must not have replaced the old
    behaviour for a folder that is neither."""
    assert TabChart._prebuilt_paper_code("__no_such_preset__") == "A4"
    assert _prebuilt_paper("__no_such_preset__") == "A4"


@pytest.mark.parametrize("key", KEYS)
def test_the_tooltip_says_the_sheet_is_printed_to_the_edge(key):
    """These two carry ink within about 1 mm of the paper edge, where every
    other bundled chart keeps 12 mm or more top and bottom, so a bordered print
    trims the crop marks and part of the printed text. The preset's own tooltip
    is where the user meets that, before the Print tab's borderless warning."""
    assert key in PREBUILT_PRESET_NOTES
    tip = TabChart._prebuilt_tooltip(None, _prebuilt_paper(key),
                                     PREBUILT_PRESET_NOTES[key])
    assert CHARTS[key]["paper_label"] in tip
    assert "edge to edge" in tip
    assert "borderless" in tip


def test_no_other_prebuilt_preset_grew_a_note_by_accident():
    assert set(PREBUILT_PRESET_NOTES) == set(KEYS)
    for key in set(PREBUILT_PRESETS) - set(KEYS):
        assert TabChart._prebuilt_tooltip(None, _prebuilt_paper(key)) == \
            TabChart._prebuilt_tooltip(None, _prebuilt_paper(key), "")


@pytest.mark.parametrize("folder,mm", [
    ("100x150", True), ("130x180", True), ("60x90", True), ("210x297", True),
    # NOT millimetres: these are real ChromIQ paper codes meaning INCHES.
    ("4x6", False), ("11x17", False), ("127x178", False), ("203x254", False),
    ("329x483", False), ("483x329", False), ("594x420", False), ("420x297", False),
    ("a4", False), ("letter", False), ("", False),
])
def test_a_folder_named_like_an_inch_paper_is_not_read_as_millimetres(folder, mm):
    """`4x6` is a ChromIQ paper code for 4 by 6 INCHES (102 x 152 mm).

    A future photo-card bundle filed under `.../i1pro/4x6/...` would otherwise
    be described as a 4 by 6 MILLIMETRE sheet and seed printtarg with `-p4x6`
    meaning something else again. The check is against `PAPER_LABELS`, so it
    cannot drift from the papers the rest of the app offers.
    """
    from ui.tabs.tab_chart import _prebuilt_paper_is_mm
    assert _prebuilt_paper_is_mm(folder) is mm
