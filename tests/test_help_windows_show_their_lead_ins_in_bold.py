"""Help windows show their topic lead-ins in bold (Knut, #182 5856723428).

*"When you write a heading or a bold font to indicate a new topic or section,
that disappears in the app, but this should be visible in the help windows,
everywhere in the app. This increases the readability considerably."*

The lead-in is MARKED in the text (``**How it works:**``), because nothing in
the punctuation tells a topic ("How the sheet is divided.") from an ordinary
short sentence ("Mutually exclusive with Double density."). These tests hold
the three things that make that safe:

* the ⓘ window turns the marks into bold and keeps everything else exactly as
  the plain text laid it out, a "<" included;
* no mark is ever shown as two asterisks, in any language, anywhere a window
  prints text that is not a help body;
* the evenness help carries Knut's lead-ins, its three headings, and the
  wording he asked for ("may come from the instrument").
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings, Qt                          # noqa: E402
from PyQt6.QtGui import QTextDocument                           # noqa: E402
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QComboBox,  # noqa: E402
                             QGroupBox, QLabel, QTabWidget, QWidget)

from core.help_markup import (bold_runs, has_markup, strip_markup,  # noqa: E402
                              to_html)

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "data" / "i18n"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- the renderer ------------------------------------------------------------

def test_marks_become_bold_and_everything_else_is_escaped():
    html = to_html("**How it works:** a < b and c > d.\n\nNext line & more.")
    assert "<b>How it works:</b>" in html
    assert "a &lt; b and c &gt; d." in html
    assert "&amp; more" in html
    assert "white-space: pre-wrap" in html, "line breaks must survive"
    assert "**" not in html


def test_strip_and_detect():
    s = "**Default:** 10 %.\n\nL*, a* and b* stay as they are."
    assert has_markup(s)
    assert strip_markup(s) == "Default: 10 %.\n\nL*, a* and b* stay as they are."
    assert bold_runs(s) == ["Default:"]
    # single asterisks of L*, a*, b* are never a mark
    assert not has_markup("L*, a* and b*")
    assert strip_markup("L*, a* and b*") == "L*, a* and b*"


def test_a_placeholder_still_formats_after_the_marks():
    s = "**The reason:** {reason}."
    assert s.format(reason="disk full") == "**The reason:** disk full."
    assert "<b>The reason:</b> disk full." in to_html(s.format(reason="disk full"))


# ---- the ⓘ window ------------------------------------------------------------

def _body_label(dlg) -> QLabel:
    labels = [lab for lab in dlg.findChildren(QLabel) if lab.wordWrap()]
    return max(labels, key=lambda lab: len(lab.text()))


def test_the_info_window_shows_a_marked_body_in_bold(qapp):
    from ui.tooltip_button import InfoDialog
    body = "Intro line.\n\n**How it works:** it works.\n\n**Default:** on"
    dlg = InfoDialog("Title", body, None)
    lab = _body_label(dlg)
    assert lab.textFormat() == Qt.TextFormat.RichText
    assert "<b>How it works:</b>" in lab.text()
    doc = QTextDocument()
    doc.setHtml(lab.text())
    plain = doc.toPlainText()
    assert "**" not in plain
    assert plain.replace(" ", "\n").strip() == strip_markup(body)
    dlg.deleteLater()


def test_an_unmarked_body_is_still_plain_text(qapp):
    from ui.tooltip_button import InfoDialog
    dlg = InfoDialog("Title", "Plain <b>not bold</b> text.\n\nSecond.", None)
    lab = _body_label(dlg)
    assert lab.textFormat() == Qt.TextFormat.PlainText
    assert lab.text().startswith("Plain <b>not bold</b>")
    dlg.deleteLater()


# ---- the catalogues: no stray marks, and a translation never adds one --------

def _catalogues():
    return sorted(p for p in I18N.glob("*.json"))


@pytest.mark.parametrize("path", _catalogues(), ids=lambda p: p.stem)
def test_every_mark_in_a_catalogue_is_a_pair_on_one_line(path):
    cat = json.loads(path.read_text(encoding="utf-8"))
    bad = []
    for k, v in cat.items():
        if k.startswith("@") or not isinstance(v, str):
            continue
        for s in (k, v):
            if s.count("**") != 2 * len(bold_runs(s)):
                bad.append(s[:70])
        if len(bold_runs(v)) > len(bold_runs(k)):
            bad.append("more bold in the translation: " + k[:60])
    assert not bad, bad[:10]


def test_the_parameter_help_marks_are_pairs_in_every_language():
    bad = []
    for path in [ROOT / "data" / "parameters.yaml",
                 *sorted(I18N.glob("parameters.*.yaml"))]:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "**" in line and line.count("**") != 2 * len(bold_runs(line)):
                bad.append(f"{path.name}:{n}")
    assert not bad, bad


def test_the_german_catalogue_carries_the_marks_of_its_english():
    """German is kept current by hand (Basti and Knut read it), so a marked
    English help text must have a marked German one, run for run."""
    de = json.loads((I18N / "de.json").read_text(encoding="utf-8"))
    missing = [k[:60] for k, v in de.items()
               if not k.startswith("@") and has_markup(k) and v != k
               and len(bold_runs(v)) != len(bold_runs(k))]
    assert not missing, missing


# ---- the evenness help (Knut's own lead-ins and wording) ----------------------

def test_the_evenness_help_has_its_headings_and_lead_ins_in_bold():
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from workflow.compliance_sets import ROW_BY_ID
    rows = [r for r in ROW_BY_ID.values() if r.group == "evenness"]
    assert len(rows) == 2, [r.id for r in rows]
    for row in rows:
        rid = row.id
        help_text = ThresholdsDialog._row_help(row)
        runs = bold_runs(help_text)
        for h in ("How ChromIQ decides your chart can be judged on this row",
                  "What you can do about it",
                  "How this row relates to the others",
                  "How the sheet is divided.", "What is compared.",
                  "The noise, and the filter.", "Choosing the two limits.",
                  "From a standard's figures."):
            assert h in runs, (rid, h)
        assert ("a difference that turns round with the reading may come "
                "from the instrument.") in help_text
        assert "reading comes from the instrument" not in help_text


# ---- nothing shows two asterisks: every window, every label -------------------

def _texts_of(top: QWidget):
    for w in top.findChildren(QWidget):
        if isinstance(w, QLabel):
            yield "label", w.text()
        if isinstance(w, QAbstractButton):
            yield "button", w.text()
        if isinstance(w, QGroupBox):
            yield "group", w.title()
        if isinstance(w, QComboBox):
            for i in range(w.count()):
                yield "combo", w.itemText(i)
                tip = w.itemData(i, Qt.ItemDataRole.ToolTipRole)
                if isinstance(tip, str):
                    yield "combo tip", tip
        if isinstance(w, QTabWidget):
            for i in range(w.count()):
                yield "tab", w.tabText(i)
        yield "tooltip", w.toolTip()
        yield "title", w.windowTitle()


def _no_marks(where: str, top: QWidget) -> "tuple[int, int]":
    """Assert no text on *top* shows a mark; return (texts looked at, help
    bodies that DO carry marks), so the test can prove it looked at a window
    that had some to leak."""
    from ui.tooltip_button import TooltipButton
    texts = list(_texts_of(top))
    shown = [(kind, t[:80]) for kind, t in texts
             if t and has_markup(strip_html(t))]
    assert not shown, f"{where}: a mark is shown as asterisks: {shown[:5]}"
    marked = sum(1 for b in top.findChildren(TooltipButton)
                 if has_markup(b.dialog_body()))
    return len(texts), marked


def strip_html(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t)


def test_no_window_shows_a_mark_as_asterisks(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.main_window import MainWindow
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    win = MainWindow(s)
    try:
        for i in range(win._tabs.count()):
            win._tabs.setCurrentIndex(i)
            qapp.processEvents()
        n_main, m_main = _no_marks("main window", win)
        sd = SettingsDialog(s, win)
        n_prefs, m_prefs = _no_marks("Preferences", sd)
        sd.deleteLater()
        td = ThresholdsDialog(s, None)
        n_lim, m_lim = _no_marks("Report Limits", td)
        td.deleteLater()
        # It looked, and there was something to leak: each window carries
        # help bodies with marks in them.
        assert n_main > 1000 and n_prefs > 300 and n_lim > 100, (
            n_main, n_prefs, n_lim)
        assert m_main >= 10 and m_prefs >= 10 and m_lim >= 20, (
            m_main, m_prefs, m_lim)
    finally:
        win.close()
        win.deleteLater()
