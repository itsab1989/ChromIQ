"""The Measure tab's option rows keep each label on ONE line, in every language
(B8-1051).

Basti, 2026-09-24, on a Ukrainian photograph of the Guided module: "Показувати
лише виміряні патчі" and "Показувати значення патча при наведенні" (the two
preview options side by side) and "Відтворення звуків під час вимірювання"
(beside "Зберегти звіт про вимірювання") each wrapped onto two lines, though
each fits on one line of its own. The rows are `ReflowRow`s now: side by side
where both fit, one per line where they do not. The left panel stays 580 px.

Measured here for all fourteen languages, Guided and Manual, at the window
the tab is built in; photographed on screen for uk, de and the longest
language by `~/Desktop/ChromIQ-beta42-proof/challenge3-fixes/drive_b8_1051.py`.

MUTATION, proven red: build the two rows as the old fixed `QHBoxLayout`s
(red in every language: 13 on a label narrower than its one-line hint, English on the missing row).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
LANGS = ["en"] + sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json")
                        if not p.name.startswith("parameters."))


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _boxes(tab):
    return {
        "g only measured": tab._g_only_measured,
        "g values on hover": tab._g_patch_tile,
        "m only measured": tab._m_only_measured,
        "m values on hover": tab._m_patch_tile,
        "sounds": tab._sound_cb,
        "save report": tab._save_report_cb,
    }


def one_line(cb) -> bool:
    """A `WrappingCheckBox`'s hint is its label on one line; given less, it
    wraps."""
    return cb.width() >= cb.sizeHint().width()


@pytest.mark.parametrize("lang", LANGS)
def test_every_option_label_is_on_one_line(qapp, tmp_path, lang):
    import core.i18n as i18n
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from ui.tabs.tab_measure import TabMeasure
    i18n.set_language(lang)
    try:
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        tab = TabMeasure(ArgyllRunner(s), s)
        for p in ("g", "m"):
            getattr(tab, f"_{p}_view_grp").setVisible(True)
        tab.resize(1500, 1000)
        tab.show()
        for _ in range(3):
            qapp.processEvents()
        bad = {}
        for name, cb in _boxes(tab).items():
            if not cb.isVisibleTo(tab):
                continue
            if not one_line(cb):
                bad[name] = (cb.text(), cb.width(), cb.sizeHint().width())
        assert not bad, f"[{lang}] wraps: {json.dumps(bad, ensure_ascii=False)}"
        # the left panel did not grow: still 580 px, and neither row asks
        # more than the panel's inner width as its minimum
        from PyQt6.QtWidgets import QWidget
        panels = [w for w in tab.findChildren(QWidget)
                  if w.minimumWidth() == w.maximumWidth() == 580]
        assert panels and all(w.width() == 580 for w in panels)
        assert tab._sound_row.minimumSizeHint().width() <= 580 - 32
        tab.hide()
        tab.deleteLater()
        qapp.processEvents()
    finally:
        i18n.set_language("en")


def _tip_after(tab, widget):
    """The TooltipButton that follows *widget* on its own line, and the gap
    between them in px (tab coordinates)."""
    from PyQt6.QtCore import QPoint
    from ui.tooltip_button import TooltipButton
    right = widget.mapTo(tab, QPoint(widget.width(), 0))
    mid_y = widget.mapTo(tab, QPoint(0, widget.height() // 2)).y()
    best = None
    for t in tab.findChildren(TooltipButton):
        if not t.isVisibleTo(tab):
            continue
        tl = t.mapTo(tab, QPoint(0, 0))
        if not (tl.y() <= mid_y <= tl.y() + t.height()):
            continue
        gap = tl.x() - right.x()
        if gap >= 0 and (best is None or gap < best[1]):
            best = (t, gap)
    return best


@pytest.mark.parametrize("lang", ["en", "de", "uk"])
def test_every_info_icon_sits_right_after_its_own_option(qapp, tmp_path, lang):
    """B8-1052. Basti, 2026-09-24, German: the ⓘ of "Töne während der
    Messung" sat at the far right of the line, after "Messbericht speichern"
    and its own ⓘ. Each ⓘ follows its own option (the gap is the row's
    spacing), and the one after "Each patch shows" follows its pulldown.

    MUTATIONS, proven red: the sounds ⓘ added as a group of its own after the
    report option (the old order); the stretch of the "Each patch shows" row
    back before its ⓘ."""
    import core.i18n as i18n
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from ui.tabs.tab_measure import TabMeasure
    i18n.set_language(lang)
    try:
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        tab = TabMeasure(ArgyllRunner(s), s)
        for p in ("g", "m"):
            getattr(tab, f"_{p}_view_grp").setVisible(True)
        tab.resize(1500, 1000)
        tab.show()
        for _ in range(3):
            qapp.processEvents()
        pairs = {
            "sounds": (tab._sound_cb, tab._sound_tip),
            "save report": (tab._save_report_cb, tab._save_report_tip),
        }
        for name, (cb, tip) in pairs.items():
            found = _tip_after(tab, cb)
            assert found is not None and found[0] is tip, (
                lang, name, "its ⓘ is not the next thing after it")
            assert found[1] <= 24, (lang, name, "gap", found[1])
        for p in ("g", "m"):
            if not getattr(tab, f"_{p}_view_grp").isVisible():
                continue
            for nm in ("overlay_mode", "only_measured", "patch_tile"):
                w = getattr(tab, f"_{p}_{nm}")
                if not w.isVisible():
                    continue
                found = _tip_after(tab, w)
                assert found is not None and found[1] <= 24, (
                    lang, p, nm, None if found is None else found[1])
        tab.hide()
        tab.deleteLater()
        qapp.processEvents()
    finally:
        i18n.set_language("en")


def test_a_long_label_cannot_widen_the_row(qapp):
    """`ReflowRow(shrink_groups=True)` asks a wrapping label's MINIMUM (its
    longest word), not its one-line hint, so a language longer than the
    panel wraps inside it instead of widening the 580 px panel (B8-1051).

    MUTATION, proven red: `shrink_groups` ignored (the minimum is the hint)."""
    from ui.widgets import ReflowRow, WrappingCheckBox
    row = ReflowRow(None, shrink_groups=True)
    cb = WrappingCheckBox("word " * 60, row)
    row.add_group(cb)
    assert cb.sizeHint().width() > 1000
    assert row.minimumSizeHint().width() < 200
    row.deleteLater()
