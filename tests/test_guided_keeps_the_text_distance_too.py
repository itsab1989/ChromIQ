"""The distance from the paper edge must reach GUIDED, which is where it was
reported.

Knut's report of 2026-09-10 was a **Guided** CR30 chart with hexagon patches:
*"Right says 5.8 mm but text goes to the edge almost."* The fix that followed
read the setting off `params.layout_recipe`, and only `_collect_manual` ever
attaches one (`ui/tabs/tab_chart.py:19991`). `_collect_guided` never has. So the
fix closed the Manual half of his report and left the half he actually sent,
which a challenge round caught by driving four Guided builds and recording
`text_edge_mm: 0.0` every time while Manual passed 7.5 correctly.

Guided has no control for this, so it gets the DEFAULT of the setting, which is
what he asked for:

> the text needs to stay within the default "Text distance from edge" settings
> in preferences chart layout. **For all sides, for Guided mode. Not a hardwired
> margin.**

A printtarg chart still passes zero, deliberately: nothing in that path ever had
the setting, and changing it would move text on charts that print correctly
today.

**AND "THE DEFAULT OF THE SETTING" MUST NOT MEAN "THE DATACLASS DEFAULT".** Both
of those paths read `LayoutRecipe().text_edge_clip_mm` straight off the
dataclass, which gave the right number for one reason only: there is no
preference for it to disagree with. A challenge round called that right by
accident, and it is, because the day a preference exists these two paths ignore
it in silence and the note goes back to disagreeing with the box the user just
typed into. They now ask `ChartCreator.default_text_edge_clip_mm`, which reads
the stored preference and falls back to the dataclass, so nothing moves today
and the preference reaches them the moment one is stored.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import tifffile

from workflow import tiff_metadata as tm
from workflow.chart_creator import (TEXT_EDGE_CLIP_SETTING_KEY, ChartCreator,
                                    ChartParams)
from workflow.layout_engine.presets import LayoutRecipe

from tests.test_chart_creator import _make_creator


def _sheet(tmp_path: Path):
    creator, _ = _make_creator(tmp_path)
    run = creator._file_mgr.project().current_run()
    run.ensure_dir()
    (run.dir / f"{run.stem}.ti1").write_text("NUMBER_OF_SETS 484\n", encoding="utf-8")
    tiff = run.dir / f"{run.stem}_01.tif"
    tifffile.imwrite(str(tiff), np.zeros((100, 100, 3), np.uint8),
                     resolution=(200, 200), resolutionunit="INCH")
    return creator, run, tiff


def _edge_passed(creator, tiff, params, monkeypatch) -> float:
    seen: list[float] = []
    monkeypatch.setattr(
        tm, "stamp_chart_metadata",
        lambda tiffs, lines, edge=0.0, band=0.0, family="", size_pt=0.0:
            seen.append(float(edge)))
    creator._stamp_tiff_metadata([tiff], params)
    assert seen, "the stamper was never called"
    return seen[0]


def test_a_guided_engine_chart_gets_the_default_distance(tmp_path, monkeypatch):
    creator, run, tiff = _sheet(tmp_path)
    got = _edge_passed(
        creator, tiff,
        # Guided: is_manual False, and no layout_recipe, exactly as
        # `_collect_guided` builds it.
        ChartParams(target_name=run.stem, device_type="2", is_manual=False,
                    instrument="CR30", stamp_commands=True),
        monkeypatch)
    assert got == LayoutRecipe().text_edge_clip_mm, got
    assert got > 0.0, "Guided is back to letting the note run to the paper edge"


def test_manual_still_uses_the_users_own_number(tmp_path, monkeypatch):
    creator, run, tiff = _sheet(tmp_path)
    got = _edge_passed(
        creator, tiff,
        ChartParams(target_name=run.stem, device_type="2", is_manual=True,
                    instrument="CR30", stamp_commands=True,
                    layout_recipe=LayoutRecipe(text_edge_clip_mm=7.5)),
        monkeypatch)
    assert got == 7.5, got


def test_a_printtarg_chart_takes_the_settings_default(tmp_path, monkeypatch):
    """This test used to assert 0.0, and said so deliberately: nothing in the
    printtarg path ever had the setting, and giving it one moves text on charts
    that print correctly today.

    **Knut overruled that on 2026-09-10**, and the reason is worth keeping in
    view. Passing 0.0 did not mean "no distance"; it meant the stamper fell back
    to its own `_PATCH_SAFETY_PAD_PX`, a 4 px constant that is 0.5 mm at 200 dpi
    and 0.25 mm at 400. His words: *"the Clip setting shall be used as limit for
    the "Text distance from edge" on both left and right sides, and there shall
    not be any hard-coded values in the code"*. Half a millimetre from the paper
    edge is also the complaint he opened this whole thread with.

    So a path with no control of its own takes the DEFAULT OF THE SETTING,
    exactly as Guided does above, and the number lives in `LayoutRecipe` where
    the box that shows it to a user reads it from.

    **The consequence is visible on paper and is flagged to him**: on a
    printtarg chart the note moves from 0.5 mm off the paper edge to whatever
    the default says, 4.0 mm today.
    """
    from workflow.layout_engine.presets import LayoutRecipe

    creator, run, tiff = _sheet(tmp_path)
    got = _edge_passed(
        creator, tiff,
        ChartParams(target_name=run.stem, device_type="2", is_manual=True,
                    instrument="i1", stamp_commands=True),
        monkeypatch)
    want = float(LayoutRecipe().text_edge_clip_mm)
    assert got == want, (
        f"a printtarg chart passed {got}, not the setting's default {want}; "
        "passing 0.0 hands the stamper back to its 4 px constant")
    assert want > 0.0, "the default is zero, so this test proves nothing"


# ---------------------------------------------------------------------------
# The default is READ, not assumed. See the module docstring.
# ---------------------------------------------------------------------------

class _StoredSettings:
    """A settings store that HAS the preference, which today nothing writes."""

    def __init__(self, value):
        self.value = value

    def get(self, key, default=None):
        if key == TEXT_EDGE_CLIP_SETTING_KEY:
            return self.value
        return default


def test_the_stored_preference_reaches_guided(tmp_path, monkeypatch):
    """The whole point. Guided has no control of its own, so if a preference
    exists it is the only thing that can move Guided's note, and a direct read
    of the dataclass could never see it."""
    creator, run, tiff = _sheet(tmp_path)
    creator._settings = _StoredSettings(9.25)
    got = _edge_passed(
        creator, tiff,
        ChartParams(target_name=run.stem, device_type="2", is_manual=False,
                    instrument="CR30", stamp_commands=True),
        monkeypatch)
    assert got == 9.25, (
        f"Guided stamped at {got} mm while the stored preference said 9.25; "
        "it is reading the dataclass default and ignoring the setting")
    assert got != LayoutRecipe().text_edge_clip_mm, (
        "the stored value equals the dataclass default, so this test cannot "
        "tell the two apart")


def test_the_stored_preference_reaches_a_printtarg_chart(tmp_path, monkeypatch):
    creator, run, tiff = _sheet(tmp_path)
    creator._settings = _StoredSettings(9.25)
    got = _edge_passed(
        creator, tiff,
        ChartParams(target_name=run.stem, device_type="2", is_manual=True,
                    instrument="i1", stamp_commands=True),
        monkeypatch)
    assert got == 9.25, got


def test_a_users_own_number_still_beats_the_preference(tmp_path, monkeypatch):
    """Manual has a control, so the box wins. A preference is a DEFAULT, and a
    default that overrode what the user typed would be a worse fault than the
    one being fixed."""
    creator, run, tiff = _sheet(tmp_path)
    creator._settings = _StoredSettings(9.25)
    got = _edge_passed(
        creator, tiff,
        ChartParams(target_name=run.stem, device_type="2", is_manual=True,
                    instrument="CR30", stamp_commands=True,
                    layout_recipe=LayoutRecipe(text_edge_clip_mm=7.5)),
        monkeypatch)
    assert got == 7.5, got


def test_an_unreadable_preference_falls_back_and_does_not_raise(tmp_path):
    """Rubbish in the store must not move the note and must not stop a build."""
    creator, _run, _tiff = _sheet(tmp_path)
    want = float(LayoutRecipe().text_edge_clip_mm)
    for junk in ("", None, "four", [], -3.0):
        creator._settings = _StoredSettings(junk)
        assert creator.default_text_edge_clip_mm() == want, junk


def test_no_path_reads_the_dataclass_default_behind_the_accessor():
    """The accessor is worth nothing if a call site still goes round it.

    `_stamp_tiff_metadata` is the method that decides the distance, and the
    round-3 note is precisely that it constructed a `LayoutRecipe` there.
    """
    src = inspect.getsource(ChartCreator._stamp_tiff_metadata)
    assert "LayoutRecipe()" not in src, (
        "_stamp_tiff_metadata builds a LayoutRecipe to read its default again; "
        "that is the read that ignores a preference. Call "
        "self.default_text_edge_clip_mm() instead.")
    assert "default_text_edge_clip_mm" in src
