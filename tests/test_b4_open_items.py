"""4.3.5 beta 4, open items of the beta 3 reviews.

a. Russian and Ukrainian: {run} ("запуск 3", "Запуск 3") never follows a
   preposition that would need another case ("в {run}" meaning "in run 3");
   it stands where the nominative (or the identical accusative) is right.
b. Ukrainian M-GAMUT-NO-PROFILE: the module buttons as the Ukrainian tab
   shows them, the verification chart in the catalogue's usual words, and
   «Тип запуску» as the label reads.
c. The 3D dialog opens inside the work area of a 1280 x 800 screen.
e. "100 g/m²" never breaks across lines in the underlay paragraph.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent


def _cat(code):
    return json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text("utf-8"))


# ---- a ------------------------------------------------------------------------
#: "в {run}" / "у {run}" are right only where they mean INTO the run (the
#: accusative, which for "запуск" is the nominative): these keys.
_INTO = ("File it in {run}", "not into {run}", "To build into {run}")


@pytest.mark.parametrize("code", ["ru", "uk"])
def test_run_never_follows_a_locative_preposition(code):
    bad = []
    from core.i18n import catalog_texts
    for en, text in catalog_texts(_cat(code)):
        for m in re.finditer(r"(?<!\w)(в|во|у|из|із|з|для|о|об|про|при|от|від|до|после|після)\s+\{run\}", text):
            # "в {run}" in the sense of "into" (accusative = nominative)
            if m.group(1) in ("в", "у") and any(k in en for k in _INTO):
                continue
            bad.append((en[:60], text[max(0, m.start() - 30):m.end() + 20]))
    assert not bad, bad


# ---- b ------------------------------------------------------------------------
def test_ukrainian_no_profile_text_uses_the_tabs_own_words():
    from workflow import measurement_messages as M
    uk = _cat("uk")
    body = uk[M.M_GAMUT_NO_PROFILE.body]
    assert uk["GUIDED"] in body and uk["MANUAL"] in body
    assert "GUIDED" not in body and "MANUAL" not in body
    assert "верифікаційн" not in body and "перевірочної діаграми" in body
    assert body.count("«Тип запуску»") == 2 and "тип запуску" not in body
    assert uk["Run type:"].rstrip(":") == "Тип запуску"


# ---- c ------------------------------------------------------------------------
class _Screen:
    def __init__(self, w, h):
        from PyQt6.QtCore import QRect
        self._r = QRect(0, 0, w, h)

    def availableGeometry(self):
        return self._r


def test_the_3d_dialog_fits_a_1280_by_800_work_area(monkeypatch):
    w = (1280, 705)
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialogs import patch_cube_dialog as d
    monkeypatch.setattr(QGuiApplication, "primaryScreen",
                        staticmethod(lambda: _Screen(*w)))
    got = d.default_dialog_size(820, 760)
    assert got[1] + d._FRAME_H <= 705 and got[0] == 820
    assert d.default_dialog_size(1040, 760)[0] == 1040
    # a large screen keeps the designed size
    monkeypatch.setattr(QGuiApplication, "primaryScreen",
                        staticmethod(lambda: _Screen(1728, 1079)))
    assert d.default_dialog_size(820, 760) == (820, 760)
    # never under the dialog's minimum
    monkeypatch.setattr(QGuiApplication, "primaryScreen",
                        staticmethod(lambda: _Screen(600, 400)))
    assert d.default_dialog_size(820, 760) == (584, 480)


# ---- e ------------------------------------------------------------------------
@pytest.mark.parametrize("code", sorted(p.stem for p in (ROOT / "data/i18n").glob("*.json")))
def test_the_paper_weight_is_glued_in_every_language(code, monkeypatch):
    from core import i18n
    from ui import ti2_loader
    from workflow import measurement_messages as M
    cat = _cat(code)
    monkeypatch.setattr(i18n, "tr", lambda s: cat.get(s, s))
    monkeypatch.setattr(M, "tr", lambda s: cat.get(s, s))
    html = ti2_loader.underlay_tip_html("cr30")
    assert html, code
    assert re.search(r"\d [gг]⁠/⁠[mм]²", html), html
    assert not re.search(r"\d [gг]/", html)
    # nothing else changed: without the invisible characters it is the text
    plain = html.replace(" ", " ").replace("⁠", "")
    import html as _h
    title, body = M.M_CAL_DONE_UNDERLAY.render()
    assert plain == f"<br><br><b>{_h.escape(title)}</b><br>{_h.escape(body)}"


# ---- d ------------------------------------------------------------------------
def test_the_measured_from_preview_frames_scroll_instead_of_crushing():
    """At 1280 x 800 the right pane has about 480 px; the frames under the
    preview used to be squeezed below their minimum (rows drawn over one
    another, seen on screen). In `_InfoRowScroll` the content keeps its own
    height and the area asks for exactly that when there is room."""
    import inspect
    from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    QApplication.instance() or QApplication([])
    from ui.tabs import tab_chart as tc
    content = QWidget()
    lay = QVBoxLayout(content)
    for i in range(12):
        lay.addWidget(QLabel(f"row {i}"))
    sa = tc._InfoRowScroll()
    sa.setWidget(content)
    full = content.sizeHint().height()
    assert sa.sizeHint().height() == full
    assert sa.minimumSizeHint().height() == min(full, tc._InfoRowScroll.MIN_H)
    sa.resize(300, 120)
    sa.show()
    QApplication.processEvents()
    assert content.height() >= content.minimumSizeHint().height()
    assert sa.verticalScrollBar().maximum() > 0
    src = inspect.getsource(tc.TabChart._build_ui) if hasattr(tc.TabChart, "_build_ui") \
        else inspect.getsource(tc)
    assert "self._info_scroll = _InfoRowScroll(right)" in src
    sa.close()
