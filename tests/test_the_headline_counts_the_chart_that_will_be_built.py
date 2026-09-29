"""Create Chart's big number describes the chart Generate is going to build.

Knut, 2026-09-10, on his own 648-patch CR30 honeycomb:

    "I set 2 pages, the tab said 792 patches, and I got 648 over one full page
     and one 60 % page. I then set 1 page, the tab said 396, and the preview
     STILL showed 2 pages and 648 patches, and the folder STILL held 2 TIFFs."

Driven on screen on 2026-09-11: both builds were genuine, both wrote the same
two sheets, and the .ti1 and the .ti2 both held 648 throughout. **The files were
honest and the number was not.**

``per_sheet * pages`` is a CAPACITY estimate, right for exactly one case:
Generate is about to run targen and fill that many pages. With a patch set
already armed -- a preset's attached .ti1 or a built-in's bundled one --
Generate takes ``chart_creator.load_ti1_and_generate_preview``, and that path
never reads ``pages`` at all.

The second half of the same fault was two numbers on one screen: the
Chart-layout-information frame's "on screen" column read 648 over 2 pages,
correct, right beside its own estimate column saying 396 over 1. The headline
is now read off the layout that panel publishes, so they are one number rather
than two that happen to agree.
"""
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, **prefs):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    for k, v in prefs.items():
        s.set(k, v)
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _ti1(tmp_path, n: int) -> Path:
    """A patch set with *n* sets in it. Only NUMBER_OF_SETS is read here, and
    that is deliberate: the count the app must believe is the file's own."""
    p = tmp_path / f"armed{n}.ti1"
    rows = "\n".join(f"{i + 1} 100.0 100.0 100.0 100.0 100.0 100.0"
                     for i in range(n))
    p.write_text(
        "CTI1\n\nDESCRIPTOR \"Argyll Calibration Target chart information 1\"\n"
        "KEYWORD \"SAMPLE_LOC\"\n"
        f"NUMBER_OF_FIELDS 7\nNUMBER_OF_SETS {n}\n"
        "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n"
        f"BEGIN_DATA\n{rows}\nEND_DATA\n", encoding="utf-8")
    return p


def _headline(tab) -> int:
    """The big number, without the accent mark the label paints after it."""
    import re
    m = re.match(r"\s*(\d+)", tab._patch_count_lbl.text())
    assert m, f"no number in {tab._patch_count_lbl.text()!r}"
    return int(m.group(1))


def _detail_pages(tab) -> int:
    """The page count out of "PATCHES · N PAGES · A4"."""
    import re
    m = re.search(r"(\d+)\s+PAGES?", tab._patch_detail_lbl.text().upper())
    if m:
        return int(m.group(1))
    assert "1 PAGE" in tab._patch_detail_lbl.text().upper(), \
        tab._patch_detail_lbl.text()
    return 1


def _estimate(tab) -> "tuple[int, int]":
    """(total, pages) as the Chart-layout-information frame's estimate column
    prints them."""
    lab = tab._layout_info_panel._estimate_labels
    return int(lab["total"].text()), int(lab["pages"].text())


# ---------------------------------------------------------------------------
# the fault
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pages", [1, 2, 3, 5])
def test_an_armed_patch_set_decides_the_count_and_the_pages_box_does_not(
        qapp, tmp_path, pages):
    """THE NUMBER REPORTED IS THE NUMBER THAT WILL BE ON THE SHEETS, which is
    the armed set plus whatever paper-white fill-up the last strip takes -- the
    same total the frame beside it reads out of a generated chart's .ti2, and
    the number Knut compared his build against. The fill-up is named in its own
    row of that frame, so nothing is hidden inside this one."""
    tab = _tab(tmp_path)
    tab._preset_ti1_path = _ti1(tmp_path, 648)
    tab._pages_spin.setValue(pages)
    tab._update_patch_count()
    est_total, _ = _estimate(tab)
    rows = int(tab._layout_info_panel._estimate_labels["rows"].text())
    assert _headline(tab) == est_total
    assert 648 <= est_total < 648 + rows, (
        f"Pages = {pages} and the headline says {_headline(tab)}; the armed "
        f"patch set holds 648 and a partial last strip can add at most "
        f"{rows - 1} fill-up patches")


def test_the_page_count_follows_the_patches_rather_than_the_box(qapp, tmp_path):
    """The line under the number said "1 PAGE" over a build that made two."""
    tab = _tab(tmp_path)
    tab._preset_ti1_path = _ti1(tmp_path, 648)
    seen = set()
    for pages in (1, 2, 3, 5):
        tab._pages_spin.setValue(pages)
        tab._update_patch_count()
        seen.add((_headline(tab), _detail_pages(tab)))
    assert len(seen) == 1, (
        f"the headline and its page count moved with the Pages box: {seen}")
    (total, shown), = seen
    assert total >= 648
    assert shown > 1, (
        "648 patches do not fit one A4 sheet at the default layout, so this "
        "test is not measuring what it claims")


@pytest.mark.parametrize("pages", [1, 2, 4])
def test_the_two_numbers_on_the_screen_are_one_number(qapp, tmp_path, pages):
    """The headline and the estimate column are read off the same layout."""
    tab = _tab(tmp_path)
    tab._preset_ti1_path = _ti1(tmp_path, 648)
    tab._pages_spin.setValue(pages)
    tab._update_patch_count()
    assert (_headline(tab), _detail_pages(tab)) == _estimate(tab)


@pytest.mark.parametrize("n", [24, 210, 648, 1500])
def test_it_is_the_file_s_own_count_whatever_that_is(qapp, tmp_path, n):
    tab = _tab(tmp_path)
    tab._preset_ti1_path = _ti1(tmp_path, n)
    tab._pages_spin.setValue(1)
    tab._update_patch_count()
    # The laid-out total is the designed count plus whatever fill-up the last
    # strip takes, and the panel's own estimate column is where that is stated.
    est_total, _est_pages = _estimate(tab)
    assert _headline(tab) == est_total
    assert est_total >= n


def test_the_mutation_lands(qapp, tmp_path):
    """The old arithmetic, restored by hand, must break the checks above.

    `per_sheet * pages` is what the label used to print. If that number happens
    to equal the armed set's own count, every assertion here would pass on the
    broken code and prove nothing.
    """
    tab = _tab(tmp_path)
    # The sheet capacity, read the honest way: with nothing armed and one page
    # asked for, the headline IS `per_sheet`. Deriving it from the armed
    # estimate instead would divide a padded total by a page count and give a
    # number that is not the capacity at all.
    tab._pages_spin.setValue(1)
    tab._update_patch_count()
    per_sheet = _headline(tab)
    assert per_sheet > 0

    tab._preset_ti1_path = _ti1(tmp_path, 648)
    tab._update_patch_count()
    fixed_answer = _headline(tab)
    old = {pages: per_sheet * pages for pages in (1, 2, 3, 5)}
    assert len(set(old.values())) == 4, (
        f"the old arithmetic gives the same answer at several page counts: {old}")
    assert fixed_answer not in old.values(), (
        f"the old arithmetic already lands on {fixed_answer} here: {old} -- "
        "pick a different patch count or the tests above cannot see the bug")


# ---------------------------------------------------------------------------
# …and the case that must keep the arithmetic it has
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pages", [1, 2, 3, 5])
def test_with_nothing_armed_the_pages_box_still_multiplies(qapp, tmp_path, pages):
    """No patch set means Generate really will run targen and fill that many
    pages, so the capacity estimate is the honest answer and is untouched."""
    tab = _tab(tmp_path)
    assert tab._preset_ti1_path is None
    tab._pages_spin.setValue(1)
    tab._update_patch_count()
    one = _headline(tab)
    tab._pages_spin.setValue(pages)
    tab._update_patch_count()
    assert _headline(tab) == one * pages
    assert _detail_pages(tab) == pages


def test_arming_a_patch_set_is_what_changes_the_answer(qapp, tmp_path):
    """Same tab, same Pages box, one difference: whether a set is armed."""
    tab = _tab(tmp_path)
    tab._pages_spin.setValue(2)
    tab._update_patch_count()
    free = _headline(tab)
    tab._preset_ti1_path = _ti1(tmp_path, 648)
    tab._update_patch_count()
    armed = _headline(tab)
    tab._preset_ti1_path = None
    tab._update_patch_count()
    assert _headline(tab) == free, "disarming did not put the estimate back"
    assert armed != free
