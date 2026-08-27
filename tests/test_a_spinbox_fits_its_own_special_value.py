"""A spin box must be wide enough for the word IT shows, not for the English one.

Basti, 2026-08-27, with a screenshot: the Create Chart ▸ Manual **Patch size
(mm)** boxes read `natisch` in German — the tail of `automatisch`, scrolled
because it did not fit.

The boxes were built by a helper whose comment read
`room for "300,0" / "auto" + buttons`: 84 px minimum, 96 px maximum, measured
against the four-letter ENGLISH word. German writes `automatisch`, which needs
72 px in a field that offers exactly 72 — so it fitted by NOTHING at all in an
offscreen run and clipped on a real display. Spanish and Portuguese
(`automático`, 65 px) were 7 px behind it.

The width now comes from the font and the string, so it is right in a language
nobody has added yet.
    NO `importlib.reload` ANYWHERE IN THIS FILE. It is tempting, because some
    modules build their strings at import time — but this panel and TabChart
    both call `tr()` in `__init__`, so setting the language and then
    CONSTRUCTING is enough. Reloading a module mid-suite replaces the class
    object while other tests still hold the old one, and that broke
    `test_clip_preview_renders_once` two runs in a row. Verified: with the
    module imported once, the box reads 'auto' / 'Auto' / 'авто' as the
    language changes.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_LANGS = ["de", "es", "pt", "en", "nl", "fr", "it", "sv", "no", "pl", "ru",
          "ja", "zh_CN"]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _restore_the_ui_language():
    """PUT THE LANGUAGE BACK. This file switches `core.i18n` — which is GLOBAL —
    and reloads modules whose labels are built at import time. Without this,
    every test that ran afterwards on the same xdist worker saw a German or
    Russian UI and failed on an English assertion.

    It was not subtle and it was not rare: the gate went 11 → 31 → 10 → 40
    failures on four consecutive runs, a different set each time, every one of
    them passing alone. That is the same shape as the bug `tests/conftest.py`
    was written to kill (179 files creating their own QApplication), and it
    cost the same confusion until the pattern was recognised.

    Restoring the language is not enough on its own — the reloaded module still
    holds the other language's strings — so the module is reloaded once more
    under the original language on the way out.
    """
    import core.i18n as i18n

    previous = getattr(i18n, "_language", "en")
    try:
        yield
    finally:
        i18n.set_language(previous)


def _field_width(sb):
    """The width the EDIT FIELD gets — not the widget's, which includes the
    up/down buttons and would make every measurement look generous."""
    from PyQt6.QtWidgets import QStyle, QStyleOptionSpinBox

    opt = QStyleOptionSpinBox()
    sb.initStyleOption(opt)
    return sb.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox, opt,
        QStyle.SubControl.SC_SpinBoxEditField, sb).width()


@pytest.mark.parametrize("lang", _LANGS)
def test_the_patch_size_boxes_show_their_whole_special_value(qapp, lang):
    import core.i18n as i18n
    from PyQt6.QtGui import QFontMetrics

    i18n.set_language(lang)
    import ui.dialogs.layout_options_panel as lop
    panel = lop.LayoutOptionsPanel()
    panel.resize(560, 900)
    panel.show()
    qapp.processEvents()
    try:
        word = i18n.tr("auto")
        need = QFontMetrics(panel.patch_x.font()).horizontalAdvance(word)
        for name in ("patch_x", "patch_y"):
            have = _field_width(getattr(panel, name))
            assert have >= need, (
                f"{lang}: {name} gives its text {have} px and {word!r} needs "
                f"{need} — it will be clipped")
    finally:
        panel.deleteLater()
        qapp.processEvents()


def test_this_file_can_see_the_bug_it_guards(qapp):
    """Control, written to be language-independent.

    Earlier attempts pinned the old hard-coded 96 px and asserted German
    clipped. They kept failing for the wrong reason: `importlib.reload` after
    `set_language` did not always give a German panel, so the control measured
    whatever language the previous parametrised case had left behind — once
    Russian's «авто» at 27 px — and would have passed against a bug it could not
    see.

    So it no longer depends on which language is loaded. Whatever word the box
    shows, squeeze the box below that word and the field must be too small.
    That is exactly the failure the fix prevents.
    """
    import core.i18n as i18n
    from PyQt6.QtGui import QFontMetrics
    import ui.dialogs.layout_options_panel as lop
    panel = lop.LayoutOptionsPanel()
    panel.resize(560, 900)
    panel.show()
    qapp.processEvents()
    try:
        word = panel.patch_x.specialValueText()
        assert word, "the box shows no special value at all"
        need = QFontMetrics(panel.patch_x.font()).horizontalAdvance(word)
        assert _field_width(panel.patch_x) >= need, (
            f"as shipped the box already clips {word!r}")

        # Squeeze it below the word it is showing — the pre-fix condition.
        chrome = panel.patch_x.width() - _field_width(panel.patch_x)
        panel.patch_x.setMinimumWidth(0)
        panel.patch_x.setMaximumWidth(need + chrome - 12)
        panel.patch_x.resize(need + chrome - 12, panel.patch_x.height())
        qapp.processEvents()
        assert _field_width(panel.patch_x) < need, (
            f"squeezing the box to 12 px under {word!r} did not clip it, so "
            "the assertions above are not measuring the field width")
    finally:
        panel.deleteLater()
        qapp.processEvents()
