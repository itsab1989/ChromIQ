"""The neighbour check in the Measure tab (#182 beta 11, Knut 5983470377
item 5, and the threshold box of 5983725218).

The rule itself is tests/test_neighbour_check.py. Here: the live preview
draws a suspect red even below the limit, with its own card; a re-read with
the same colour turns it yellow; a patch read before its comparisons is
judged again when they arrive; the buffer is the user's; and the check, and
the summary in the closing window, are absent on a verification, a
calibration chart and a chart made from a profile.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from workflow import measurement_messages as M  # noqa: E402
from workflow import patch_flags as pf  # noqa: E402

STRIPS = "ABCDEF"
PER = 12


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self, d=None):
        self._d = {"chartread_engine": "chromiq", **dict(d or {})}

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


def _exp(letter, n):
    """A lattice of expected colours: each patch has patches of the next and
    previous strip within ΔE 15, so every patch has comparisons."""
    s = STRIPS.index(letter)
    return [18.0 + 2.0 * s, 20.0 + 1.5 * n, 22.0 + 1.0 * s]


def _meas(letter, n, factor=1.0):
    """Every patch read 10 % dark against its rough estimate, as a print is;
    *factor* darkens one reading further (a misread)."""
    return [v * 0.9 * factor for v in _exp(letter, n)]


def _de(e, m):
    from workflow.icc_info import xyz_to_lab
    a = xyz_to_lab(tuple(v / 100 for v in e))
    b = xyz_to_lab(tuple(v / 100 for v in m))
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _strip(letter, bad=None):
    """strip_read event; *bad* maps a loc to its darkening factor."""
    out = []
    for n in range(1, PER + 1):
        loc = f"{letter}{n}"
        e = _exp(letter, n)
        m = _meas(letter, n, (bad or {}).get(loc, 1.0))
        out.append({"id": loc, "loc": loc, "exyz": e, "xyz": m,
                    "de": round(_de(e, m), 2)})
    return {"strip": letter, "patches": out}


def _chart(folder, accurate=False):
    folder.mkdir(parents=True, exist_ok=True)
    ti2 = folder / "chart.ti2"
    ti2.write_text('CTI2\n\nORIGINATOR "ChromIQ layout engine"\n'
                   + ('ACCURATE_EXPECTED_VALUES "true"\n' if accurate else "")
                   + "NUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC\n"
                   "END_DATA_FORMAT\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n",
                   encoding="utf-8")
    return ti2


def _tab(folder, accurate=False, settings=None):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings(settings)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._ti1_path = _chart(folder, accurate)
    tab._page_stripe_rects = [[QRect(0, 20 * i, 600, 18)
                               for i in range(len(STRIPS))]]
    tab._strips_per_page = [len(STRIPS)]
    tab._engine_strips = [{"strip": c} for c in STRIPS]
    tab._patch_boxes = [{f"{c}{n}": QRect(22 * (n - 1), 20 * i, 20, 18)
                         for i, c in enumerate(STRIPS)
                         for n in range(1, PER + 1)}]
    return tab


def _flags(tab):
    by_box = {(b.x(), b.y()): loc for loc, b in tab._patch_boxes[0].items()}
    return {by_box[(it[0].x(), it[0].y())]: it[3]
            for it in tab._preview._patch_overlay.get(0, [])}


def _red(tab):
    return sorted(loc for loc, f in _flags(tab).items() if f is True)


def _info(tab, loc):
    box = tab._patch_boxes[0][loc]
    for b, info in tab._preview._patch_info.get(0, []):
        if (b.x(), b.y()) == (box.x(), box.y()):
            return info
    raise AssertionError(loc)


def _card(info):
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content(info, "both")
    return [text for _sw, text in tile._rows]


def _read_all(tab, bad=None):
    for c in STRIPS:
        tab._on_strip_measured(_strip(c, bad))


def test_the_misread_is_below_the_limit(qapp):
    """The point of the check: the limit 95 cannot see this misread."""
    e, m = _exp("D", 6), _meas("D", 6, 0.55)
    assert _de(e, m) < 95


def test_a_misread_below_the_limit_is_red_with_its_own_card(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == ["D6"]
    info = _info(tab, "D6")
    assert not info["warn"] and info["neighbour"]["n"] >= 3
    lines = _card(info)
    assert M._CARD_NB_RED in lines
    assert M._CARD_NB_5 in lines and M._CARD_RED_READ_AGAIN in lines
    # Exact (review of beta 11): the very figure the buffer is compared
    # with, and the buffer, so the card cannot seem to contradict itself.
    f = tab._nb_check.finding("D6")
    assert f.excess > 10.0
    assert M._CARD_NB_3.format(excess=f"{f.excess:.1f}") in lines
    assert M._CARD_NB_4.format(buffer="10.0") in lines
    assert not any("reached your limit" in l for l in lines)


def test_a_clean_chart_has_no_neighbour_outline(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab)
    assert _red(tab) == []
    assert tab._misread_summary().startswith(M._SUM_NB_NONE)


def test_the_same_reading_again_turns_it_yellow(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._on_strip_measured(_strip("D", {"D6": 0.55}))
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
    lines = _card(_info(tab, "D6"))
    assert "Yellow outline: confirmed by a re-read" in lines
    assert tab.neighbour_summary_facts()["kept"] == ["D6"]
    assert tab.neighbour_summary_facts()["red"] == []


def test_a_good_reading_again_clears_it(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._on_strip_measured(_strip("D"))
    # Green: a misread a re-read corrected (Knut 5984277558).
    assert _flags(tab)["D6"] == pf.FLAG_CORRECTED
    assert _info(tab, "D6")["neighbour"] is None


def test_a_patch_read_first_is_judged_again_when_its_comparisons_arrive(
        qapp, tmp_path):
    """A6 is read before any other strip: no comparisons, not judged. Two
    strips later it has them, and the preview turns it red without A being
    read again."""
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A", {"A6": 0.55}))
    assert _red(tab) == []
    tab._on_strip_measured(_strip("B"))
    tab._on_strip_measured(_strip("C"))
    assert "A6" in _red(tab)
    assert _info(tab, "A6")["neighbour"]["n"] >= 3


def test_the_buffer_is_the_users(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_neighbour_buffer_de": 50.0})
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == []
    tab._settings.set("patch_neighbour_buffer_de", 10.0)
    tab._on_strip_measured(_strip("A"))      # the next batch takes the new value
    assert _red(tab) == ["D6"]


def test_painted_from_disk_it_is_the_same(qapp, tmp_path):
    tab = _tab(tmp_path)
    patches = [p for c in STRIPS for p in _strip(c, {"D6": 0.55})["patches"]]
    tab._on_chart_measured({"patches": patches}, live=False, strip_fence=True)
    assert _red(tab) == ["D6"]


def test_a_chart_made_with_a_pre_conditioning_profile_is_checked(
        qapp, tmp_path):
    """Knut, #182 5984174575: the check also runs on a profiling chart made
    with a pre-conditioning profile (ACCURATE_EXPECTED_VALUES)."""
    tab = _tab(tmp_path / "run2", accurate=True)
    assert tab._chart_expected_is_accurate()
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == ["D6"]
    assert tab.neighbour_summary_facts()["red"] == ["D6"]


@pytest.mark.parametrize("case", ["verification", "calibration"])
def test_not_on_these_charts(qapp, tmp_path, monkeypatch, case):
    folder = tmp_path / ("cal" if case == "calibration" else "run1")
    tab = _tab(folder)
    if case == "verification":
        monkeypatch.setattr(type(tab), "_is_verification_run", lambda self: True)
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == []
    assert tab.neighbour_summary_facts() is None
    if case == "verification":
        tab._read_twice_log = [("B", "A", "keep")]
        monkeypatch.setattr(type(tab), "_read_twice_was_active",
                            lambda self: True)
        assert tab._misread_summary() == ""


def test_the_summary_names_what_is_still_red(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55, "B11": 0.5})
    text = tab._misread_summary()
    assert text.splitlines()[0] == M._SUM_NB_RED.format(n=2, locs="B11, D6")
    tab._on_strip_measured(_strip("B", {"B11": 0.5}))      # kept as real
    lines = tab._misread_summary().splitlines()
    assert lines[0] == M._SUM_NB_RED_ONE.format(locs="D6")
    assert lines[1] == M._SUM_NB_KEPT_ONE


def test_the_summary_says_what_the_strip_test_found(qapp, tmp_path,
                                                    monkeypatch):
    tab = _tab(tmp_path)
    _read_all(tab)
    monkeypatch.setattr(type(tab), "_read_twice_was_active", lambda self: True)
    tab._read_twice_log = []
    assert tab._misread_summary().splitlines()[-1] == M._SUM_TWICE_NONE
    tab._read_twice_log = [("C", "B", "reread"), ("E", "D", None)]
    assert tab._misread_summary().splitlines()[-1] == M._SUM_TWICE.format(
        n=2, list="C (like B, read again), E (like D, kept)")
    monkeypatch.setattr(type(tab), "_read_twice_was_active", lambda self: False)
    assert M._SUM_TWICE_NONE not in tab._misread_summary()


def test_the_completion_summary_puts_it_under_the_reading_times(qapp,
                                                                tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._measurement_summary = lambda: "Total measuring time: 00:01:00"
    text = tab._completion_summary().splitlines()
    assert text[0] == "Total measuring time: 00:01:00"
    assert text[1] == M._SUM_NB_RED_ONE.format(locs="D6")


def test_suspects_off_alike_in_other_strips_do_not_confirm_each_other(
        qapp, tmp_path):
    """Knut, #182 5984174575: "The neighbour check needs a re-read to
    confirm." Two suspects of different strips, expected nearly the same
    colour and off in the same way, would be similar patches under the
    limit's rule; here both stay red until each is read again."""
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55, "B3": 0.5})
    assert _flags(tab)["D6"] is pf.FLAG_RED
    assert _flags(tab)["B3"] is pf.FLAG_RED
    lines = _card(_info(tab, "D6"))
    assert M._CARD_PEER_1 not in lines
    assert M._CARD_NB_REREAD_1 in lines and M._CARD_NB_REREAD_2 in lines
    assert tab.neighbour_summary_facts()["red"] == ["B3", "D6"]
    tab._on_strip_measured(_strip("D", {"D6": 0.55}))      # its own re-read
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
    assert _flags(tab)["B3"] is pf.FLAG_RED
    facts = tab.neighbour_summary_facts()
    assert facts["red"] == ["B3"] and facts["kept"] == ["D6"]


# ---- review of beta 11 ------------------------------------------------------

def test_the_card_follows_its_comparisons_after_later_strips(qapp, tmp_path):
    """D6 turns red after strip E; strip F changes its comparisons and its
    figure without changing the verdict. The card shows the figures of now,
    not those of strip E (review of beta 11)."""
    tab = _tab(tmp_path)
    seen = []
    for c in STRIPS:
        tab._on_strip_measured(_strip(c, {"D6": 0.55}))
        f = tab._nb_check.finding("D6")
        if f is not None and f.suspect:
            seen.append(round(f.excess, 1))
            nb = _info(tab, "D6")["neighbour"]
            assert nb["locs"] == list(f.compared)
            assert nb["excess"] == pytest.approx(f.excess)
    assert len(set(seen)) > 1          # the figure did change on the way


def test_the_card_shows_the_users_buffer(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_neighbour_buffer_de": 7.5})
    _read_all(tab, {"D6": 0.55})
    lines = _card(_info(tab, "D6"))
    assert M._CARD_NB_4.format(buffer="7.5") in lines


def test_nothing_checked_is_not_called_no_misreads(qapp, tmp_path):
    """One strip read: no patch has a comparison in another strip, so the
    closing window says nothing could be checked, not "no suspected
    misreads"."""
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A"))
    facts = tab.neighbour_summary_facts()
    assert facts["checked"] == 0 and facts["total"] == PER
    lines = tab._misread_summary().splitlines()
    assert lines == [M._SUM_NB_NONE_CHECKED.format(total=PER)]


def test_kept_without_red_does_not_say_more(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._on_strip_measured(_strip("D", {"D6": 0.55}))
    lines = tab._misread_summary().splitlines()
    assert lines[:2] == [M._SUM_NB_NONE, M._SUM_NB_KEPT_ONE]
    assert "more" not in M._SUM_NB_KEPT_ONE and "more" not in M._SUM_NB_KEPT


class _AsideManager:
    """The manager's side of "Was a strip read twice?" for one question."""

    def __init__(self, strip, like, locs):
        self.pending = [(strip, like)]
        self.aside = set()
        self.locs = set(locs)
        self.engine_active = True

    def read_twice_pending(self):
        return self.pending[0] if self.pending else None

    def answer_read_twice(self, choice):
        self.pending.pop(0)
        if choice in ("reread", "was_like"):
            self.aside = set(self.locs)

    def set_aside_locs(self):
        return set(self.aside)


@pytest.mark.parametrize("choice", ["reread", "was_like"])
def test_a_reading_set_aside_leaves_the_neighbour_check_at_once(
        qapp, tmp_path, monkeypatch, choice):
    """Strip E was read where strip D's colours are (the reader on the wrong
    strip): its readings are misfits. Answered "read again" or "it was
    strip D", they are set aside: the neighbour check forgets them at once
    (review of beta 11), so they are no suspects in the closing window and
    compare with nothing, before E is read again."""
    tab = _tab(tmp_path)
    for c in STRIPS:
        ev = _strip(c)
        if c == "E":
            for p, q in zip(ev["patches"], _strip("A")["patches"]):
                p["xyz"] = q["xyz"]
        tab._on_strip_measured(ev)
    e_locs = [f"E{n}" for n in range(1, PER + 1)]
    assert set(tab.neighbour_summary_facts()["red"]) & set(e_locs)
    mgr = _AsideManager("E", "A", e_locs)
    tab._manager = mgr
    tab._session_live = True
    monkeypatch.setattr(type(tab), "_a_question_is_open", lambda self: False)
    monkeypatch.setattr(type(tab), "_strip_read_twice_window",
                        lambda self, strip, like: choice)
    tab._ask_read_twice()
    facts = tab.neighbour_summary_facts()
    assert not set(facts["red"]) & set(e_locs)
    assert facts["total"] == (len(STRIPS) - 1) * PER
    assert not any(tab._nb_check.is_suspect(x) for x in e_locs)
    assert not set(_red(tab)) & set(e_locs) or all(
        _info(tab, x)["neighbour"] is None for x in e_locs)


# ---- Knut 5984174575: a neighbour suspect needs its own re-read ------------

def _judge_with_a_learned_range(reread_only):
    """Three patches of one colour range confirmed by re-reads, then a fourth
    of the same range, in another strip, off in the same way."""
    j = pf.FlagJudge()
    exp = (50.0, -40.0, 30.0)                        # a green
    shift = (-12.0, 6.0, -4.0)
    for i, strip in enumerate("ABC"):
        e = (exp[0] + i, exp[1], exp[2] + i)
        m = tuple(a + b for a, b in zip(e, shift))
        for live in (True, True):
            j.judge(f"{strip}1", e, m, 99.0, True, live=live, strip=strip)
    e = (exp[0] + 0.5, exp[1], exp[2] + 0.5)
    m = tuple(a + b for a, b in zip(e, shift))
    return j.judge("D1", e, m, 99.0, True, strip="D", reread_only=reread_only)


def test_similar_patches_and_a_learned_range_do_not_clear_a_neighbour_suspect():
    """Under the limit's rule the fourth is yellow (similar patches, its
    range learned); as a neighbour suspect it stays red."""
    assert pf.is_yellow(_judge_with_a_learned_range(False).flag)
    v = _judge_with_a_learned_range(True)
    assert v.flag is pf.FLAG_RED and v.reread_only and not v.misfit


def test_red_for_both_reasons_needs_a_re_read_and_its_card_says_so(
        qapp, tmp_path):
    """Over the limit AND a neighbour suspect: red until its own re-read; the
    card is the limit's red card, then the neighbour lines and the re-read
    lines in place of what its colour range would have said."""
    tab = _tab(tmp_path, settings={"patch_read_warn_de_estimated": 15.0,
                                   "patch_warn_outlier_fence": False})
    _read_all(tab, {"D6": 0.55})
    info = _info(tab, "D6")
    assert info["warn"] and info["neighbour"] and info["reread_only"]
    assert _flags(tab)["D6"] is pf.FLAG_RED
    lines = _card(info)
    assert "Red outline: a large difference" in lines
    i = lines.index(M._CARD_NB_1_ALSO.format(n=info["neighbour"]["n"]))
    # beta 15 (k43): the two lines Knut approved follow the figures
    assert lines[i + 4:i + 6] == [M._CARD_NB_LATER_1, M._CARD_NB_LATER_2]
    assert lines[i + 7:i + 9] == [M._CARD_NB_REREAD_1, M._CARD_NB_REREAD_2]
    assert M._CARD_RANGE_RED_LEARNED_1 not in lines
    tab._on_strip_measured(_strip("D", {"D6": 0.55}))
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
