"""A Guided chart's recipe describes a roomier page than the sheet the user is
looking at, so the "there's a little room left" hint must not be shown at all.

Guided writes no layout recipe of its own. The sidecar therefore carries the
LayoutRecipe dataclass defaults — 6 mm all round — while the sheet was laid out
at the instrument's own border (10 mm for the i1Pro). Re-deriving the geometry
from those defaults yields a bigger page than the real one: measured, 506
patches for a real 484-patch i1Pro A4 sheet.

Suppressing only the capacity number was worse than leaving it alone. The hint
still fired and read:

    "space for about 22 more patches on it (the page holds about 0 in total)"

which contradicts itself inside one sentence. Both numbers come from the same
bad rebuild, so the whole hint goes.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.file_manager import FileManager            # noqa: E402
from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def tab(qapp, tmp_path_factory):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path_factory.mktemp("s") / "s.ini"),
                      QSettings.Format.IniFormat)
    from ui.tabs.tab_chart import TabChart
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _chart(tmp_path, *, flag):
    """A chart sidecar carrying a real engine recipe; `flag` is what the
    provenance field says, or None to leave it out entirely."""
    ti2 = tmp_path / "P.ti2"
    ti2.write_text("NUMBER_OF_SETS 484\n", encoding="utf-8")
    layout = {
        "engine": "chromiq",
        "recipe": {"instrument": "i1", "paper": "A4",
                   "use_instrument_margins": False,
                   "margin_top": 6.0, "margin_right": 6.0,
                   "margin_bottom": 6.0, "margin_left": 6.0},
    }
    if flag is not None:
        layout["margins_chosen_by_user"] = flag
    (tmp_path / "P.channels.json").write_text(json.dumps({"layout": layout}), encoding="utf-8")
    return ti2


def test_a_guided_chart_says_its_recipe_cannot_rebuild_its_sheet(tab, tmp_path):
    assert tab._recipe_rebuilds_its_own_sheet(_chart(tmp_path, flag=False)) is False


def test_a_chart_whose_margins_the_user_chose_is_rebuildable(tab, tmp_path):
    assert tab._recipe_rebuilds_its_own_sheet(_chart(tmp_path, flag=True)) is True


def test_a_chart_built_before_the_flag_existed_is_trusted_as_before(tab, tmp_path):
    """Absent must not read as False, or every Manual chart and every chart on
    disk today would silently lose its hint."""
    assert tab._recipe_rebuilds_its_own_sheet(_chart(tmp_path, flag=None)) is True


def test_an_unreadable_sidecar_does_not_change_the_old_behaviour(tab, tmp_path):
    ti2 = tmp_path / "Q.ti2"
    ti2.write_text("NUMBER_OF_SETS 484\n", encoding="utf-8")
    (tmp_path / "Q.channels.json").write_text("{ not json", encoding="utf-8")
    assert tab._recipe_rebuilds_its_own_sheet(ti2) is True

    missing = tmp_path / "R.ti2"
    missing.write_text("NUMBER_OF_SETS 484\n", encoding="utf-8")
    assert tab._recipe_rebuilds_its_own_sheet(missing) is True


def test_the_hint_is_silent_for_a_chart_we_cannot_rebuild(tab, tmp_path):
    """The whole point: no blank count, so `_maybe_warn_partial_last_page`
    returns before it can compose a sentence about a page it misread."""
    assert tab._partial_last_page_blank(_chart(tmp_path, flag=False)) is None


def test_the_capacity_is_unknown_rather_than_guessed(tab, tmp_path):
    """0 is the "not known" answer; nothing may present it as a real capacity.
    It is unreachable from the hint now, but the two must agree."""
    assert tab._last_page_capacity(_chart(tmp_path, flag=False)) == 0


def test_this_file_can_see_the_bug_it_guards(tab, tmp_path, monkeypatch):
    """Proof the suppression is what makes the tests above pass.

    Force the helper to call every chart rebuildable — the state before the
    fix — and the same 484-patch sheet is described as having room for 198 more
    patches on a page that "holds 682". That is the wrong sheet, in numbers, and
    it is what the user was shown.
    """
    ti2 = _chart(tmp_path, flag=False)
    assert tab._partial_last_page_blank(ti2) is None       # as shipped

    monkeypatch.setattr(type(tab), "_recipe_rebuilds_its_own_sheet",
                        staticmethod(lambda _p: True))
    blank = tab._partial_last_page_blank(ti2)
    capacity = tab._last_page_capacity(ti2)
    assert blank is not None and blank > 0, (
        "the mutation did not land — with the provenance guard removed the "
        "hint MUST come back, or these tests are not testing the guard"
    )
    assert capacity > 0
    # The shape of the original complaint: a full sheet told it has room, and a
    # capacity that cannot be reconciled with the patch count on screen.
    assert blank + 484 != capacity or capacity != 484
