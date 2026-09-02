"""Knut's 7.5 mm i1Pro family — the 19 charts added in 4.1.3-beta.15.

NOTHING TESTED THESE WHEN THEY SHIPPED. Renaming all nineteen `chart.ti1`
files away left 530 tests passing, and changing `area_cols` from 24 to 25 —
which makes the patch print 7.19 mm while every one of the names says 7.5 —
left 146 passing. A family is not shipped until something checks the number in
its own name.
"""
import json
import pathlib
import re

import pytest

from core.resource_path import resource_path

pytestmark = pytest.mark.usefixtures("qapp")

_SLUG = "i1_w75_"


def _family():
    from ui.tabs.tab_chart import KNUT_PRESETS

    return [p for p in KNUT_PRESETS if p.slug.startswith(_SLUG)]


def test_the_family_is_all_nineteen():
    fam = _family()
    assert len(fam) == 19, f"expected 19 charts, found {len(fam)}"
    assert len({p.slug for p in fam}) == 19, "duplicate slugs"
    assert len({p.key for p in fam}) == 19, "duplicate preset keys"


def test_every_chart_ships_its_patch_set():
    """The bundled .ti1 must exist and hold exactly the patches the name says."""
    missing, wrong = [], []
    for p in _family():
        f = pathlib.Path(resource_path(p.ti1_asset))
        if not f.is_file():
            missing.append(p.slug)
            continue
        m = re.search(r"NUMBER_OF_SETS\s+(\d+)", f.read_text(errors="replace"))
        got = int(m.group(1)) if m else -1
        if got != p.patches:
            wrong.append(f"{p.slug}: file has {got}, preset says {p.patches}")
    assert not missing, f"bundled patch set missing: {missing}"
    assert not wrong, "patch count disagrees with the file:\n  " + "\n  ".join(wrong)


def test_the_page_count_matches_the_name():
    """The exports declared `pages: 4` for eighteen of the nineteen, whatever
    their own names said. The name is the source of truth."""
    bad = []
    for p in _family():
        m = re.search(r"-(\d+)pages?-", p.name)
        assert m, f"{p.name} has no page count in its name"
        if int(m.group(1)) != p.pages:
            bad.append(f"{p.name}: name says {m.group(1)}, preset says {p.pages}")
    assert not bad, "\n  ".join(bad)


def test_the_patch_count_matches_the_name():
    bad = []
    for p in _family():
        m = re.search(r"-(\d+)p-", p.name)
        assert m, f"{p.name} has no patch count in its name"
        if int(m.group(1)) != p.patches:
            bad.append(f"{p.name}: name says {m.group(1)}, preset says {p.patches}")
    assert not bad, "\n  ".join(bad)


def test_the_grid_is_the_one_that_makes_7_5_mm():
    """`area_cols` is what sets the patch width, and every name promises 7.5 mm.

    Pinned because changing it by ONE column prints 7.19 mm under a name that
    still says 7.5, and nothing else in the suite notices.
    """
    for p in _family():
        rec = p.layout_recipe
        paper = rec["paper"]
        expect = 52 if paper == "420x297" else 24
        assert rec["area_cols"] == expect, (
            f"{p.slug}: area_cols {rec['area_cols']}, expected {expect} for "
            f"{paper} — the patch would not be 7.5 mm wide")
        assert rec["area_rows"] == 27, f"{p.slug}: area_rows {rec['area_rows']}"


def test_the_family_keeps_its_own_base():
    """`sscale` and `margin_right` are what make this a family of its own."""
    from ui.tabs.tab_chart import _I1_75_BASE

    for p in _family():
        rec = p.layout_recipe
        assert rec["sscale"] == 0.75, f"{p.slug}: sscale {rec['sscale']}"
        want = 9.0 if rec["paper"] == "Letter" else 4.0
        assert rec["margin_right"] == want, (
            f"{p.slug}: margin_right {rec['margin_right']}, expected {want} "
            f"for {rec['paper']}")
    assert _I1_75_BASE["sscale"] == 0.75
    assert _I1_75_BASE["margin_right"] == 4.0


def test_the_eight_millimetre_family_is_untouched():
    """Adding a second i1Pro family must not have moved the first."""
    from ui.tabs.tab_chart import _I1_BASE, KNUT_PRESETS

    assert _I1_BASE["sscale"] == 0.8
    assert _I1_BASE["margin_right"] == 6.0
    old = [p for p in KNUT_PRESETS if p.slug.startswith("i1_w8_")]
    assert len(old) == 19, f"the 8 mm family changed size: {len(old)}"
    for p in old:
        assert p.layout_recipe["sscale"] == 0.8, f"{p.slug} moved to 0.75"


def test_the_withdrawn_charts_are_gone_everywhere():
    """The two A4-924p charts Knut withdrew, and their assets."""
    from ui.tabs.tab_chart import KNUT_PRESETS

    gone = {"fls_i1pro_a4_924p_2pages_portrait",
            "fls_i1pro_a4_924p_2pages_portrait_nature_focus"}
    assert not (gone & {p.slug for p in KNUT_PRESETS}), "a withdrawn chart is back"
    for slug in gone:
        d = pathlib.Path(resource_path(f"assets/charts/knut/rgb/fulllayout/{slug}"))
        assert not d.exists(), f"withdrawn asset folder still on disk: {d}"


def test_every_chart_carries_its_colour_set_recipe():
    """The sidecar that lets "Load setup from preset" seed the New-chart window."""
    missing = []
    for p in _family():
        rec = pathlib.Path(resource_path(p.ti1_asset)).with_name("recipe.json")
        if not rec.is_file():
            missing.append(p.slug)
            continue
        json.loads(rec.read_text())          # must parse
    assert not missing, f"colour-set recipe missing: {missing}"


# --- the importer's family guard -------------------------------------------

def test_the_importer_refuses_a_batch_from_another_family(tmp_path):
    """A batch that differs from the shipped base in a non-varying field must
    be REFUSED, not folded in.

    Before this guard existed the validator compared each batch against its own
    first file, so a difference shared by the whole batch passed 19 out of 19
    and printed "✓ validated". That is how nineteen 7.5 mm charts nearly went
    into the 8 mm family, where they would have taken its 6.0 mm right margin.
    """
    import subprocess
    import sys

    src = pathlib.Path("/tmp/knut_i1pro2")
    if not src.is_dir():
        pytest.skip("the 7.5 mm export folder is not on this machine")

    out = subprocess.run(
        [sys.executable, "scripts/import_knut_presets.py", "i1", str(src)],
        capture_output=True, text=True, cwd=pathlib.Path(__file__).parent.parent,
        env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"}, encoding="utf-8")
    assert out.returncode != 0, (
        "the importer accepted a batch that belongs to another family:\n"
        + out.stdout[-800:])
    assert "does not belong" in out.stdout, out.stdout[-800:]
    assert "sscale" in out.stdout, "the guard did not name the field that differs"


def test_the_guard_covers_the_family_it_was_written_for(tmp_path):
    """`_shipped_base` mapped only cm/p3/i1, so the guard was a NO-OP for i175
    — the family it was added for. A drifting 7.5 mm batch validated rc=0."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_imp", pathlib.Path(__file__).parent.parent / "scripts"
        / "import_knut_presets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    for key in ("cm", "p3", "i1", "i175"):
        base = mod._shipped_base(mod.FAMILIES[key])
        assert base, f"no shipped base found for family {key!r}"
        assert "sscale" in base, f"family {key!r} base looks wrong: {sorted(base)[:5]}"
