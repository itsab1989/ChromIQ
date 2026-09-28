"""Every preset's names agree with its files (Knut, #182 5872273862).

*"Verify that all presets in the app have correct names of ti1 file, json file,
and the name of the preset inside the json file."*

Three kinds of preset, three places a name lives:

* **built-in** — its key, its display name, its asset folder's ``chart.ti1``
  and ``recipe.json``. The display name states a patch count and a page count,
  and the bundled patch set and the design must say the same.
* **own** (``core/preset_store.py``) — the ``.json`` file name, the ``name``
  inside it, and the ``.ti1`` beside it.
* **the demo pack** (``scripts/make_verification_preset_demos.py``) — written
  with the store's own rule, and read back through it here.

The audit found, at 4fd43ca5: five "by Pharmacist" designs naming A4 portrait
for Letter and A4-landscape charts (fixed here), the same fault in the six
scanner designs (below, not fixable in this change), and three ways an own
preset's files could stop agreeing (fixed in ``core/preset_store.py``).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core import preset_store as PS                          # noqa: E402
from core.resource_path import resource_path                  # noqa: E402
from ui.tabs import tab_chart as T                            # noqa: E402

#: Designs that still name the wrong paper, and why they are still here.
#: THIS LIST ONLY SHRINKS: a test below fails when an entry has been put right,
#: so the entry has to go with the fix.
KNOWN_WRONG_PAPER = {
    # assets/charts/knut/ was being renamed in a parallel change when this was
    # found (B8-1692): the six scanner designs say "A4" portrait for their
    # A4R / LetterR sheets. The editor has no scanner instrument, so their
    # "i1" is the nearest it can show and is not the fault.
    "__chromiq_knut_scanner_a4_3430p_1page_landscape__",
    "__chromiq_knut_scanner_letter_3250p_1page_landscape__",
    "__chromiq_knut_scanner_a4_6860p_2pages_landscape__",
    "__chromiq_knut_scanner_letter_6500p_2pages_landscape__",
    "__chromiq_knut_scanner_a4_10290p_3pages_landscape__",
    "__chromiq_knut_scanner_letter_9750p_3pages_landscape__",
}

#: The instruments the New Patch Set window can show.
EDITOR_INSTRUMENTS = {"i1", "3p", "CM"}


def _sets(ti1: Path) -> int:
    for line in ti1.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("NUMBER_OF_SETS"):
            return int(line.split()[1])
    raise AssertionError(f"{ti1} has no NUMBER_OF_SETS")


def _recipe(p) -> dict | None:
    side = resource_path(p.ti1_asset).parent / "recipe.json"
    if p.ti1_asset == T.KNUT_TI1_ASSET or not side.is_file():
        return None
    return json.loads(side.read_text(encoding="utf-8"))


# --- built-in ---------------------------------------------------------------

def test_every_built_in_key_and_name_is_unique():
    keys = [p.key for p in T.KNUT_PRESETS]
    assert len(keys) == len(set(keys))
    labels = [p.combo_label for p in T.KNUT_PRESETS]
    dup = {x for x in labels if labels.count(x) > 1}
    assert not dup, f"two built-ins read the same in the dropdown: {dup}"


@pytest.mark.parametrize("p", T.KNUT_PRESETS, ids=lambda p: p.slug)
def test_a_built_in_s_name_says_what_its_patch_set_holds(p):
    ti1 = resource_path(p.ti1_asset)
    assert ti1.is_file(), f"{p.key}: {p.ti1_asset} is missing"
    assert p.slug in p.key, (p.slug, p.key)
    m = re.search(r"(\d+)p\b|(\d+)p-", p.name)
    if m:
        named = int(m.group(1) or m.group(2))
        assert named == _sets(ti1), (
            f"{p.name!r} says {named} patches, {p.ti1_asset} holds {_sets(ti1)}")
    m = re.search(r"(\d+)pages?\b", p.name)
    if m:
        assert int(m.group(1)) == p.pages, (p.name, p.pages)


@pytest.mark.parametrize("p", [p for p in T.KNUT_PRESETS if _recipe(p)],
                         ids=lambda p: p.slug)
def test_a_built_in_s_design_names_its_chart(p):
    rec = _recipe(p)
    if p.instrument in EDITOR_INSTRUMENTS:
        assert rec.get("instr") == p.instrument, (p.key, rec.get("instr"))
    if p.key in KNOWN_WRONG_PAPER:
        return
    assert rec.get("paper") == p.paper, (
        f"{p.key}: the design says {rec.get('paper')!r}, the chart is "
        f"{p.paper!r}; New Patch Set… opens it on the wrong sheet")
    cb, sp = rec.get("cb") or {}, rec.get("sp") or {}
    if cb.get("fill") and sp.get("fill_to"):
        assert sp["fill_to"] == _sets(resource_path(p.ti1_asset)), p.key


def test_the_known_wrong_designs_are_still_wrong():
    """When one is put right, take it off the list with the fix."""
    for key in KNOWN_WRONG_PAPER:
        p = T.KNUT_PRESETS_BY_KEY.get(key)
        assert p is not None, f"{key} is no longer a built-in: drop it"
        assert _recipe(p).get("paper") != p.paper, (
            f"{key}'s design names its paper now: drop it from the list")


def test_the_shown_by_default_list_names_real_presets():
    doc = json.loads(resource_path("data/preset_defaults.json")
                     .read_text(encoding="utf-8"))
    unknown = set(doc.get("shown", {})) - set(T.BUILTIN_PRESET_KEYS)
    assert not unknown, unknown


# --- own presets --------------------------------------------------------------

@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    return PS.tab_dir("create_chart")


@pytest.mark.parametrize("name", ["Mine", "a/b", "w11.5mm", "Grün ✓",
                                  "  spaced  ", "x:y?"])
def test_a_saved_preset_s_three_names_agree(store, name):
    PS.save_presets("create_chart", {name: {"attached_ti1": True}})
    files = list(store.glob("*.json"))
    assert len(files) == 1
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    assert doc["name"] == name
    assert PS.sidecar_path("create_chart", name, ".ti1").stem == files[0].stem
    assert list(PS.load_presets("create_chart")) == [name]


def test_a_file_renamed_outside_keeps_its_name_and_its_patch_set(store):
    """A download renames an attachment ("Wide gamut.json" arrives as
    "Wide-gamut.json"); the name inside is the preset's, and its .ti1 sits
    under the new file name. It was not found, and the first save orphaned
    it."""
    PS.save_presets("create_chart", {"Wide gamut": {"attached_ti1": True}})
    (store / "Wide gamut.json").rename(store / "Wide-gamut.json")
    (store / "Wide-gamut.ti1").write_text("CTI1\n", encoding="utf-8")
    presets = PS.load_presets("create_chart")
    assert list(presets) == ["Wide gamut"]
    assert PS.find_sidecar("create_chart", "Wide gamut", ".ti1") == \
        store / "Wide-gamut.ti1"
    PS.save_presets("create_chart", presets)
    assert {p.name for p in store.iterdir()} == {"Wide gamut.json",
                                                  "Wide gamut.ti1"}


def test_a_duplicate_made_in_finder_is_two_presets_and_survives_a_save(store):
    """Finder's "Mine copy.json" still says "Mine" inside: the two showed as
    one preset, and the next save deleted the copy."""
    PS.save_presets("create_chart", {"Mine": {"k": 1}})
    (store / "Mine copy.json").write_bytes((store / "Mine.json").read_bytes())
    presets = PS.load_presets("create_chart")
    assert set(presets) == {"Mine", "Mine copy"}
    PS.save_presets("create_chart", presets)
    assert {p.name for p in store.glob("*.json")} == {"Mine.json",
                                                       "Mine copy.json"}


def test_a_patch_set_left_under_the_name_is_still_found(store):
    PS.save_presets("create_chart", {"Mine": {"attached_ti1": True}})
    (store / "Mine.ti1").write_text("CTI1\n", encoding="utf-8")
    (store / "Mine.json").rename(store / "Theirs.json")
    assert list(PS.load_presets("create_chart")) == ["Mine"]
    assert PS.find_sidecar("create_chart", "Mine", ".ti1") == store / "Mine.ti1"


def test_names_sharing_a_file_are_recognised():
    assert PS.same_file_name("a/b", "a_b")
    assert PS.same_file_name("Mine", "mine")
    assert not PS.same_file_name("w11.5mm", "w11_5mm")


# --- the demo pack -----------------------------------------------------------

def test_every_demo_preset_s_names_agree(store):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import make_verification_preset_demos as M
    built = M.build(store)
    presets = PS.load_presets("create_chart")
    for demo, chart in built:
        assert demo.name in presets, f"{demo.name!r} is not listed by that name"
        stem = PS._sanitize(demo.name)
        assert (store / f"{stem}.json").is_file()
        data = presets[demo.name]
        if chart is None:
            assert not data.get("attached_ti1"), demo.name
        else:
            assert chart.stem == stem, (chart.name, demo.name)
            assert data.get("attached_ti1"), demo.name
            assert PS.find_sidecar("create_chart", demo.name, ".ti1") == chart
