"""Three doors take a `.ti3` in, and only one of them asked about its scale.

`repair_converted_cie` puts i1Profiler's 0-to-1 XYZ right on every path that
CONVERTS an export. A `.ti3` that was converted before that repair existed is
never converted again, so only a READING can catch it - and
`reference_convert.cie_columns_are_unscaled` was referenced in exactly ONE
place in the app, `tab_profile.set_ti3_path`.

Driven on screen, combined round 10, with a real 240-patch measurement whose
XYZ columns were divided by 100 (the exact shape the fault produces, so names,
counts and device values all still match the run's own chart):

* **Build ICC profile** marked it "colour values on the wrong scale";
* **the profiling import door** filed it, said "The measurement was imported",
  and SAVED A DATED MEASUREMENT REPORT from it, saying nothing about the scale;
* **the verification import door** filed it into a new dated verification
  folder and said nothing either.

INHERITED, NOT INTRODUCED: the verification door has shipped this way since the
reading was written on 2026-09-11, and the profiling door was built the same
way. The lesson of B8-199 is that a fourth door will be written one day against
whichever base is current then, so this fails when ANY of the three stops
asking, and when the sentence grows a second copy.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.measurement_filing import (the_colour_scale_note,       # noqa: E402
                                   the_colour_scale_tag)

#: (module, class, method) for every door that takes a `.ti3` from the user.
#: A door added here without the call is the fault this file exists for.
THE_DOORS = [
    ("ui.tabs.tab_profile", "TabProfile", "set_ti3_path"),
    ("ui.tabs.tab_measure", "TabMeasure", "_update_import_panel"),
    ("ui.tabs.tab_measure", "TabMeasure", "_convert_import_file"),
]


def _ti3(tmp_path, *, scale: float, name: str = "m.ti3") -> "os.PathLike":
    """A small OUTPUT measurement whose paper patch is the lightest.

    `_xyz_scale_verdict` needs a WITNESS before it will accuse a file of being
    on the wrong scale: an OUTPUT device class and a no-ink patch that is the
    lightest thing in the table. Both are here, so this is the real shape and
    not a number small enough to look suspicious.
    """
    rows = [
        # no ink (RGB 100 100 100 = paper), then progressively darker
        ("1", 100.0, 100.0, 100.0, 95.0, 100.0, 108.0),
        ("2", 50.0, 50.0, 50.0, 20.0, 21.0, 23.0),
        ("3", 0.0, 0.0, 0.0, 1.8, 1.9, 2.1),
    ]
    body = "\n".join(
        "{} {:.4f} {:.4f} {:.4f} {:.6f} {:.6f} {:.6f}".format(
            i, r, g, b, x * scale, y * scale, z * scale)
        for i, r, g, b, x, y, z in rows)
    p = tmp_path / name
    p.write_text(
        'CTI3\n\n'
        'DESCRIPTOR "Argyll Calibration Target chart information 3"\n'
        'DEVICE_CLASS "OUTPUT"\n'
        'COLOR_REP "RGB_XYZ"\n\n'
        'NUMBER_OF_FIELDS 7\n'
        'BEGIN_DATA_FORMAT\n'
        'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        'END_DATA_FORMAT\n\n'
        f'NUMBER_OF_SETS {len(rows)}\n'
        'BEGIN_DATA\n'
        f'{body}\n'
        'END_DATA\n', encoding="utf-8")
    return p


# ---- the shared reading itself -------------------------------------------
def test_the_note_fires_on_a_measurement_on_the_wrong_scale(tmp_path):
    note = the_colour_scale_note(_ti3(tmp_path, scale=0.01))
    assert note, "the shared check said nothing about a 0-to-1 measurement"
    assert "0 to 1 scale" in note
    assert "paper white" in note


def test_the_note_is_silent_on_an_ordinary_measurement(tmp_path):
    assert the_colour_scale_note(_ti3(tmp_path, scale=1.0)) == ""


def test_the_note_is_silent_on_nothing_at_all():
    """A tab with no measurement loaded asks this on every refresh."""
    assert the_colour_scale_note(None) == ""


def test_the_tag_is_the_mark_that_goes_after_the_name():
    tag = the_colour_scale_tag()
    assert "colour values on the wrong scale" in tag
    assert tag.strip() != tag, "the separator is part of the key on purpose"


# ---- and every door asks it ----------------------------------------------
@pytest.mark.parametrize("module,cls,method", THE_DOORS)
def test_the_door_asks_about_the_colour_scale(module, cls, method):
    mod = __import__(module, fromlist=[cls])
    src = inspect.getsource(getattr(getattr(mod, cls), method))
    assert "the_colour_scale_note" in src, (
        f"{cls}.{method} takes a .ti3 from the user and never asks whether "
        f"its colour values are on the scale ArgyllCMS means")


def test_all_three_doors_are_still_listed():
    """The list must not shrink either: deleting a row is not a fix."""
    assert len(THE_DOORS) == 3


# ---- one sentence, one copy ----------------------------------------------
def test_the_sentence_lives_in_exactly_one_module():
    """A second copy is how two doors describe one file differently.

    The words are the ones the Build ICC profile tab has shown since
    2026-09-11 and are already in all twelve catalogues; moving them into a
    shared function added no new message text, and a copy would.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    needle = "on the 0 to 1 scale"
    holders = sorted(
        str(p.relative_to(root))
        for d in ("ui", "workflow", "core")
        for p in (root / d).rglob("*.py")
        if needle in p.read_text(encoding="utf-8", errors="replace"))
    assert holders == ["ui/measurement_filing.py"], holders


def test_the_sentence_is_not_new_text():
    """It is already translated, so no door is showing unapproved words."""
    import json
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    de = json.loads((root / "data" / "i18n" / "de.json").read_text(
        encoding="utf-8"))
    key = next(k for k in de if k.startswith(
        "The XYZ columns in this measurement are on the 0 to 1 scale"))
    assert de[key], "the sentence is in the catalogue but untranslated"
