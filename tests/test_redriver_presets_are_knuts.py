"""The six Red River presets ARE Knut's six exported files — field for field.

WHY THIS TEST EXISTS
--------------------
Knut sent six ``.json`` preset exports for the Red River "Standard Patch Set
v25" chart on 2026-08-24 and again, byte-identical, on 2026-08-26:

    "The red river presets were manipulated by the AI, changing the settings
     and markings. … They must be implemented as is. The margins etc are
     different for Colormunki and i1Pro."

They were "manipulated" not by anyone deciding to change them but by a shared
base dict: a later change wrote one ``helper_marker_per_patch`` across
``_REDRIVER_BASE``, silently overwriting the per-chart values (5 on the i1Pro
charts, 7 on ColorMunki A4 8-pages) that he had chosen on paper. Nothing
failed, because nothing compared the shipped recipe with the file it came from.

So this test does exactly that: it reads HIS files out of a committed fixture
and asserts every ``LayoutRecipe`` field of every shipped Red River preset
equals his, resolved to EFFECTIVE values — a field left out of a dict is not
"equal", it is the dataclass default, and the two must be compared after that
default is applied or an omission reads as agreement.

Three fields are deliberately NOT copied verbatim, and each is asserted in its
own right rather than skipped (a skipped field is how the last drift got in):

  * ``clip_image_path`` — his files carry
    ``/Applications/ChromIQ.app/Contents/Frameworks/assets/…/clip_logo.png``,
    an absolute path into HIS installed bundle. It must go through
    ``core.resource_path`` or it resolves nowhere in a dev checkout, nowhere on
    Windows/Linux, and nowhere in a differently-installed .app. The test asserts
    the shipped path is ``resource_path(<the same tail he used>)`` and that the
    file exists.
  * ``data["pages"]`` — his 9-page exports both say ``"pages": 8``. The stored
    field is stale session state; the NAME and the grid arithmetic
    (2052 ÷ cols × rows, rounded up) agree with each other on all six, so the
    test derives the count and pins ``_Ti1Preset.pages`` to it. It never reads
    his ``pages``.
  * ``editor_recipe`` — every one of the six carries the same leftover
    200-patch p3/A4 *generator* recipe from his session. It has nothing to do
    with a locked 2052-patch chart and is not imported at all.

WHY THE FIXTURE IS HIS FILES VERBATIM AND NOT A DISTILLED TABLE
---------------------------------------------------------------
A distilled table is exactly what already exists in ``tab_chart.py``, and
transcribing his numbers into a second hand-written table would give the drift
a second place to happen — the test would then agree with the code and both
would be wrong together. The fixture is the artefact he sent, unedited, so the
next time he sends a revision the whole verification is "drop the new files in
and run the suite". Their provenance is pinned by sha256 below, so an edited
fixture is itself a failure.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from pathlib import Path

import pytest

from core.resource_path import resource_path
from ui.tabs.tab_chart import KNUT_PRESETS
from workflow.layout_engine.presets import LayoutRecipe

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "redriver_presets_v25"

#: His file → the shipped slug it must equal. Written out rather than derived
#: from the names, because the pairing is the thing under test: two of his six
#: are NINE-page charts and the presets they replace were named "10pages".
PAIRS = {
    "i1Pro-A4-2052p-4pages-Portrait-Standard Patch Set v25.json":
        "redriver_i1pro_a4_2052p_4pages",
    "i1Pro-Letter-2052p-4pages-Portrait-Standard Patch Set v25.json":
        "redriver_i1pro_letter_2052p_4pages",
    "ColorMunki-A4-2052p-8pages-Portrait-Standard Patch Set v25.json":
        "redriver_colormunki_a4_2052p_8pages",
    "ColorMunki-Letter-2052p-8pages-Portrait-Standard Patch Set v25.json":
        "redriver_colormunki_letter_2052p_8pages",
    "ColorMunki-A4-2052p-9pages-Portrait-Standard Patch Set v25.json":
        "redriver_colormunki_a4_2052p_9pages",
    "ColorMunki-Letter-2052p-9pages-Portrait-Standard Patch Set v25.json":
        "redriver_colormunki_letter_2052p_9pages",
}

#: sha256 of each fixture as he sent it (zip
#: 0493fdfe2e8e7ed320e8065f3a36356dd8ce93f336a3aa8d46cf32acda5e672d,
#: "presets Red River.zip", 2026-08-26 — byte-identical to "Updated presets
#: Red River.zip", 2026-08-24).
SHA256 = {
    "ColorMunki-A4-2052p-8pages-Portrait-Standard Patch Set v25.json":
        "edcf325ea8a0f15a59840f490f2acc3f01683013c4eac2a416c6ff5184cb5463",
    "ColorMunki-A4-2052p-9pages-Portrait-Standard Patch Set v25.json":
        "956ee5cd28735418e815d9051cc7a97d9c5980b2ec35d957ec88c14508693142",
    "ColorMunki-Letter-2052p-8pages-Portrait-Standard Patch Set v25.json":
        "c5c8a444760542e3039330af3faac5d479b60218816cb859572c6d642df4ccfd",
    "ColorMunki-Letter-2052p-9pages-Portrait-Standard Patch Set v25.json":
        "dc5b53cd7ec68ac900d398691a76b938ccb05e97b813fb8af1ac51f5425de87c",
    "i1Pro-A4-2052p-4pages-Portrait-Standard Patch Set v25.json":
        "8731fb66388efb0f52710b7a501f763c96b31b62f218bcefed87eeb973affcfb",
    "i1Pro-Letter-2052p-4pages-Portrait-Standard Patch Set v25.json":
        "93215e072e085c9b1ec2a1625d8b67bd2c73dcb4e5bc46f1bb2f70ccd0207520",
}

#: The one field that is legitimately different, and the reason. Anything else
#: that differs is the bug this file exists to catch.
NOT_VERBATIM = {"clip_image_path"}

PATCHES = 2052
LOGO_TAIL = ("assets/charts/redriver/rgb/standard_patch_set_v25/clip_logo.png")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _his(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _effective(d: dict) -> dict:
    """His / our recipe dict resolved through the dataclass defaults.

    ``LayoutRecipe.from_dict`` drops unknown keys and fills in every field it
    was not given, which is the only fair basis for "same": our recipes omit
    ~50 fields that his exports spell out in full, and an omission must be
    compared as the default it becomes, not silently passed over.
    """
    return dataclasses.asdict(LayoutRecipe.from_dict(d))


def _redriver_presets() -> dict:
    return {p.slug: p for p in KNUT_PRESETS if p.file_group == "Red River Paper"}


# --------------------------------------------------------------------------
# the fixture itself
# --------------------------------------------------------------------------
def test_fixture_is_his_files_unedited():
    """The fixture is what he sent. Editing it would defeat the whole test."""
    for name, want in SHA256.items():
        path = FIXTURE_DIR / name
        assert path.is_file(), f"missing fixture {name}"
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        assert got == want, (
            f"{name} is not the file Knut sent (sha256 {got}). A fixture is "
            f"evidence: replace it only with a NEW export from him, and update "
            f"SHA256 in the same commit.")


def test_exactly_six_red_river_presets_and_they_are_his():
    slugs = set(_redriver_presets())
    assert slugs == set(PAIRS.values()), (
        "the Red River family must be exactly Knut's six charts — "
        f"extra: {sorted(slugs - set(PAIRS.values()))}, "
        f"missing: {sorted(set(PAIRS.values()) - slugs)}")


# --------------------------------------------------------------------------
# the field-for-field comparison — the point of the file
# --------------------------------------------------------------------------
@pytest.mark.parametrize("filename,slug", sorted(PAIRS.items()))
def test_shipped_recipe_equals_his_file_field_for_field(filename, slug):
    preset = _redriver_presets()[slug]
    assert preset.layout_recipe is not None, f"{slug} lost its engine recipe"

    his = _effective(_his(filename)["data"]["layout_recipe"])
    ours = _effective(preset.layout_recipe)

    differing = {k: (his[k], ours[k]) for k in his
                 if his[k] != ours[k] and k not in NOT_VERBATIM}
    assert not differing, (
        f"{slug} no longer matches {filename}. Knut: \"They must be "
        f"implemented as is.\" Changed fields (his → shipped): "
        + ", ".join(f"{k}: {h!r} → {o!r}" for k, (h, o) in
                    sorted(differing.items())))


@pytest.mark.parametrize("filename,slug", sorted(PAIRS.items()))
def test_clip_logo_goes_through_resource_path(filename, slug):
    """The one value that must NOT be copied verbatim, asserted rather than
    skipped: same asset, resolved for THIS installation."""
    his_path = _his(filename)["data"]["layout_recipe"]["clip_image_path"]
    assert his_path.endswith(LOGO_TAIL), (
        "his export points at a different asset than the bundled logo — "
        f"{his_path}")

    ours = _redriver_presets()[slug].layout_recipe["clip_image_path"]
    assert ours == str(resource_path(LOGO_TAIL)), (
        "the clip logo must be resolved through core.resource_path, or the "
        "preset only works on the machine the export came from")
    assert Path(ours).is_file(), f"bundled clip logo missing: {ours}"


# --------------------------------------------------------------------------
# the page count: from the name and the grid, never from his stale field
# --------------------------------------------------------------------------
@pytest.mark.parametrize("filename,slug", sorted(PAIRS.items()))
def test_page_count_comes_from_the_grid_and_the_name(filename, slug):
    preset = _redriver_presets()[slug]
    rec = LayoutRecipe.from_dict(preset.layout_recipe)
    assert rec.area_method == "by_grid" and rec.area_cols and rec.area_rows

    from_grid = math.ceil(PATCHES / (rec.area_cols * rec.area_rows))
    from_name = int(preset.name.split("2052p-")[1].split("pages")[0])

    assert from_grid == from_name == preset.pages, (
        f"{slug}: grid {rec.area_cols}×{rec.area_rows} gives {from_grid} "
        f"pages, the name says {from_name}, the preset carries "
        f"{preset.pages}. The Pages control on screen is seeded from "
        f"_Ti1Preset.pages, so a wrong value is visible to the user.")


def test_his_stored_pages_field_is_not_trusted():
    """Both 9-page exports say ``"pages": 8``. This asserts the known-bad
    state, so that the day he sends a corrected export the test says so
    instead of quietly letting a derived-vs-stored rule outlive its reason."""
    stale = {n for n in PAIRS
             if _his(n)["data"]["pages"] != int(
                 n.split("2052p-")[1].split("pages")[0])}
    assert stale == {
        "ColorMunki-A4-2052p-9pages-Portrait-Standard Patch Set v25.json",
        "ColorMunki-Letter-2052p-9pages-Portrait-Standard Patch Set v25.json",
    }, ("which exports carry a stale `pages` has changed — re-read them "
        f"before trusting the field. Stale now: {sorted(stale)}")


def test_editor_recipe_is_session_leftover_and_is_not_imported():
    """Every export carries the same unrelated 200-patch p3/A4 generator
    recipe. It describes a chart that is not this one, and a Red River preset
    must carry no design at all (the patch set is a locked, bundled .ti1)."""
    from ui.tabs.tab_chart import builtin_preset_recipe

    seen = set()
    for name in PAIRS:
        er = _his(name).get("data", {}).get("editor_recipe") or {}
        seen.add((er.get("mode"), er.get("instr"), er.get("paper"),
                  er.get("count")))
    assert seen == {("generate", "p3", "A4", 200)}, (
        f"the leftover editor_recipe in his exports has changed: {seen}. "
        "Re-check whether it is still session junk before dropping it.")

    for slug in PAIRS.values():
        preset = _redriver_presets()[slug]
        assert builtin_preset_recipe(preset.key) is None, (
            f"{slug} must not carry a generator design — its patch set is the "
            "bundled Red River .ti1")


# --------------------------------------------------------------------------
# the two answers he gave by sending the files
# --------------------------------------------------------------------------
def test_helper_marker_density_is_per_chart_not_shared():
    """The exact drift that caused the complaint: one value written across a
    shared base. His charts do NOT share it."""
    got = {slug: _redriver_presets()[slug].layout_recipe.get(
        "helper_marker_per_patch") for slug in PAIRS.values()}
    assert got == {
        "redriver_i1pro_a4_2052p_4pages": 5,
        "redriver_i1pro_letter_2052p_4pages": 5,
        "redriver_colormunki_a4_2052p_8pages": 7,
        "redriver_colormunki_letter_2052p_8pages": 3,
        "redriver_colormunki_a4_2052p_9pages": 3,
        "redriver_colormunki_letter_2052p_9pages": 3,
    }, ("helper_marker_per_patch is Knut's per-chart choice (7 on ColorMunki "
        f"A4 8-pages is deliberate). Got {got}")


def test_the_clip_band_side_split_is_deliberate():
    """ColorMunki right + flipped, i1Pro left + unflipped. Both come straight
    from his files; the split is not an oversight in one of them."""
    for slug, side, flip in (
        ("redriver_i1pro_a4_2052p_4pages", "left", False),
        ("redriver_i1pro_letter_2052p_4pages", "left", False),
        ("redriver_colormunki_a4_2052p_8pages", "right", True),
        ("redriver_colormunki_letter_2052p_8pages", "right", True),
        ("redriver_colormunki_a4_2052p_9pages", "right", True),
        ("redriver_colormunki_letter_2052p_9pages", "right", True),
    ):
        rec = LayoutRecipe.from_dict(_redriver_presets()[slug].layout_recipe)
        assert (rec.clip_side, rec.clip_flip_180) == (side, flip), (
            f"{slug}: clip band must sit on the {side} "
            f"{'flipped' if flip else 'unflipped'}. A right-side band is "
            "auto-turned 180°, so clip_flip_180=True is what makes the Red "
            "River branding read the SAME way as it does on the i1Pro charts "
            "— dropping it prints the logo upside down.")


# --------------------------------------------------------------------------
# it still builds what it says it builds
# --------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("slug", sorted(PAIRS.values()))
def test_every_red_river_chart_builds_the_pages_its_name_promises(slug, tmp_path):
    """End to end through the real engine: the page count on the tin, all
    2052 patches placed, and the user's margin minimums met.

    Slow (six multi-page 300 dpi rasterisations), so it carries the marker and
    runs in the release gate rather than the everyday tier."""
    from collections import Counter

    from core.settings import default_margin_thresholds, thresholds_for_combo
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine import geometry as le_geom
    from workflow.layout_engine import instruments as le_instr
    from workflow.layout_engine import papers as le_papers

    preset = _redriver_presets()[slug]
    recipe = LayoutRecipe.from_dict(preset.layout_recipe)
    ti1 = resource_path(preset.ti1_asset)
    result, _ = le_chart.build_from_recipe(ti1, tmp_path / slug, recipe)

    assert len(result.tiff_paths) == preset.pages, (
        f"{slug} built {len(result.tiff_paths)} pages, not {preset.pages}")

    def rgb(path):
        lines = Path(path).read_text(encoding="utf-8", errors="replace").split("\n")
        fmt = lines[lines.index("BEGIN_DATA_FORMAT") + 1].split()
        cols = [fmt.index(k) for k in ("RGB_R", "RGB_G", "RGB_B")]
        body = lines[lines.index("BEGIN_DATA") + 1:lines.index("END_DATA")]
        # 2 dp: the .ti1 and the .ti2 round the same value differently in the
        # 4th decimal, which is not a dropped patch.
        return Counter(tuple(round(float(ln.split()[c]), 2) for c in cols)
                       for ln in body if ln.split())

    missing = rgb(ti1) - rgb(result.ti2_path)
    assert not missing, (
        f"{slug} dropped {sum(missing.values())} of {PATCHES} patches, e.g. "
        f"{list(missing)[:3]}")

    w_mm, h_mm = le_papers.dimensions_mm(recipe.paper)
    geom = le_instr.geom_from_build_kwargs(recipe.build_kwargs())
    left, right, top, bottom = le_geom.realized_margins_mm(
        geom, w_mm, h_mm, result.layout)
    thr = thresholds_for_combo(
        default_margin_thresholds(), recipe.instrument, w_mm, h_mm)
    assert thr, f"no default margin thresholds for {recipe.instrument}/{recipe.paper}"
    for side, realized in (("L", left), ("R", right),
                           ("T", top), ("B", bottom)):
        minimum = thr.get(side)
        if isinstance(minimum, (int, float)):
            assert realized + 1e-6 >= minimum, (
                f"{slug}: {side} margin {realized:.2f} mm is under the "
                f"{minimum} mm minimum for {recipe.instrument} on "
                f"{recipe.paper}")
