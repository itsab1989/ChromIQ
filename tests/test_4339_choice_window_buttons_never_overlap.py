"""The owner, during the 4.3.39 integration: in a German window two buttons
overlapped ("Nur das Chart ersetzen"). Reproduced on screen: the four-choice
window "Where should this patch set's chart go?" (a run holding a chart and a
measurement) laid "Lieber als neuen Lauf bauen" under "Nur das Chart ersetzen":
four choices and Cancel need more than the 1000 px Qt allows a message box,
and the row was squeezed.

`_choice_box` now keeps the buttons side by side in one row when they fit,
else lays them out in as few rows as fit, side by side and of one width; only
when the window would still be taller than the work area does its text go
into a scroll area. For every language, on this screen and on simulated
1280 x 800 and 1366 x 768 laptops: no two buttons intersect, no label is
wider than its button, the window fits the work area and every button lies
inside it. Escape and Return still mean Cancel; a button in a wrapped row
still answers its own choice.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QRect, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

LANGS = ["en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
         "sv", "uk", "zh_CN"]
#: Work areas: this machine's own, and two common laptops (the macOS menu
#: bar on the first, a Windows taskbar on the second).
SCREENS = {"own": None,
           "1280x800": QRect(0, 25, 1280, 775),
           "1366x768": QRect(0, 0, 1366, 728)}
CAPTION = 28        # a title bar, which the frame adds above the box


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def language():
    from core import i18n
    before = i18n.current_language()
    yield i18n.set_language
    i18n.set_language(before)


def _four_choices():
    from core.i18n import tr
    run = tr("Run {n}").format(n=1)
    desc = tr(
        "Swap the chart in <b>{label}</b> and leave everything else "
        "standing: the measurement, the profile, the reports and the "
        "verifications stay put, and nothing moves to <code>old/</code>. "
        "<b>ChromIQ cannot check that these patches are the ones your "
        "measurement was taken with</b> — only you can, and if they are "
        "not, the run keeps a measurement that no longer matches its "
        "chart. {sidecar}").format(label=run, sidecar=tr(
            "No chart settings file was found beside it, so only the "
            "patches are replaced and the settings now on screen decide "
            "the layout."))
    return [(tr("Replace {run}").format(run=run), desc, "into_replace"),
            (tr("Build it as a new run instead"), desc, "into_new"),
            (tr("Replace only the chart"), desc, "into_chart"),
            (tr("Start a new project"), desc, "new")]


def _visible_buttons(box):
    return [b for b in box.findChildren(QPushButton) if b.isVisible()]


def _measure(qapp, box):
    box.show()
    for _ in range(6):
        qapp.processEvents()
    rects = [(b.text(), QRect(b.mapTo(box, b.rect().topLeft()), b.size()))
             for b in _visible_buttons(box)]
    cut = [(b.text(), b.fontMetrics().horizontalAdvance(b.text()), b.width())
           for b in _visible_buttons(box)
           if b.width() < b.fontMetrics().horizontalAdvance(b.text())]
    return dict(size=(box.width(), box.height()), rects=rects, cut=cut)


def _open(qapp, monkeypatch, screen, door_action=None):
    import ui.ti2_loader as L
    import ui.widgets as Wd
    from core.i18n import tr
    if SCREENS[screen] is not None:
        monkeypatch.setattr(Wd, "long_buttons_work_area",
                            lambda box: SCREENS[screen])
    seen = {}

    def door(box):
        seen.update(_measure(qapp, box))
        seen["work"] = Wd.long_buttons_work_area(box)
        answer = door_action(box) if door_action else None
        box.hide()
        box.deleteLater()
        return answer
    key = L._choice_box(None, tr("Where should this patch set's chart go?"),
                        "", _four_choices(), _exec_choice_box=door)
    qapp.processEvents()
    return key, seen


@pytest.mark.parametrize("screen", sorted(SCREENS))
@pytest.mark.parametrize("code", LANGS)
def test_no_overlap_no_cut_and_inside_the_work_area(qapp, language,
                                                    monkeypatch, code,
                                                    screen):
    language(code)
    _key, m = _open(qapp, monkeypatch, screen)
    rects = m["rects"]
    assert len(rects) == 5, (code, screen, [t for t, _r in rects])
    for i, (ta, ra) in enumerate(rects):
        for tb, rb in rects[i + 1:]:
            assert not ra.intersects(rb), (code, screen, ta, ra, tb, rb)
    assert not m["cut"], (code, screen, m["cut"])
    w, h = m["size"]
    work = m["work"]
    assert w <= work.width() and h + CAPTION <= work.height(), (
        code, screen, (w, h), (work.width(), work.height()))
    # placed at the work area's top left, every button lies inside it
    box_at = QRect(work.x(), work.y() + CAPTION, w, h)
    for t, r in rects:
        assert work.contains(r.translated(box_at.topLeft())), (code, screen, t)
        assert QRect(0, 0, w, h).contains(r), (code, screen, t)


def test_one_row_when_they_fit(qapp, language, monkeypatch):
    """English on this screen: all five side by side, as before."""
    language("en")
    _key, m = _open(qapp, monkeypatch, "own")
    if len({r.y() for _t, r in m["rects"]}) != 1:
        pytest.skip("this screen's font is too wide for one row")
    xs = [r.x() for _t, r in m["rects"]]
    assert xs == sorted(xs)


def test_wrapped_rows_are_even_and_cancel_is_last(qapp, language,
                                                  monkeypatch):
    language("de")
    _key, m = _open(qapp, monkeypatch, "1280x800")
    rects = m["rects"]
    rows = sorted({r.y() for _t, r in rects})
    if len(rows) == 1:
        pytest.skip("one row fits on this screen's font")
    assert len({r.width() for _t, r in rects}) == 1      # one width
    assert len({r.x() for _t, r in rects if r.y() == rows[0]}) > 1, \
        "side by side in a row, never a single column when two fit"
    assert rects[-1][1].y() == rows[-1]                  # Cancel last
    from core.i18n import tr
    assert rects[-1][0] == tr("Cancel")


@pytest.mark.parametrize("screen", ["own", "1280x800"])
def test_escape_still_cancels(qapp, language, monkeypatch, screen):
    from PyQt6.QtTest import QTest
    language("de")

    def press(box):
        QTest.keyClick(box, Qt.Key.Key_Escape)
        qapp.processEvents()
        return box.clickedButton()
    key, _m = _open(qapp, monkeypatch, screen, press)
    assert key is None, screen


@pytest.mark.parametrize("screen", ["own", "1280x800"])
def test_return_presses_cancel_while_shown(qapp, language, monkeypatch,
                                           screen):
    """Return presses Cancel, as before, in one row and wrapped (round-2
    review: Qt clears a default flag set before the box is shown)."""
    from PyQt6.QtTest import QTest
    language("de")
    seen = {}

    def press(box):
        seen["rows"] = len({r.y() for _t, r in _measure(qapp, box)["rects"]})
        target = box.focusWidget() or box
        QTest.keyClick(target, Qt.Key.Key_Return)
        qapp.processEvents()
        seen["open"] = box.isVisible()
        seen["clicked"] = box.clickedButton()
        return box.clickedButton()
    key, _m = _open(qapp, monkeypatch, screen, press)
    from core.i18n import tr
    assert not seen["open"], (screen, "Return left the window open")
    assert key is None and seen["clicked"] is not None, (screen, seen)
    assert seen["clicked"].text() == tr("Cancel"), (screen, seen)


def test_a_button_in_a_wrapped_row_answers_its_own_choice(qapp, language,
                                                          monkeypatch):
    language("de")
    from core.i18n import tr

    def press(box):
        target = [b for b in _visible_buttons(box)
                  if b.text() == tr("Replace only the chart")][0]
        target.click()
        qapp.processEvents()
        return box.clickedButton()
    key, _m = _open(qapp, monkeypatch, "1280x800", press)
    assert key == "into_chart"


def test_on_a_very_short_screen_the_text_scrolls_and_the_buttons_stay(
        qapp, language, monkeypatch):
    """Only when rows of buttons still leave the window taller than the work
    area does the text go into a scroll area: forced here with a work area
    of 1024 x 420."""
    from PyQt6.QtWidgets import QScrollArea
    language("de")
    SCREENS["short"] = QRect(0, 0, 1024, 420)
    try:
        seen = {}

        def door_action(box):
            seen["scroll"] = box.findChild(QScrollArea, "long_buttons_text_scroll")
            return None
        _key, m = _open(qapp, monkeypatch, "short", door_action)
    finally:
        del SCREENS["short"]
    assert seen["scroll"] is not None
    w, h = m["size"]
    assert h + CAPTION <= 420, (w, h)
    assert len(m["rects"]) == 5
