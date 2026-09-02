"""One process per language: the scanner/camera window's real floor.

    python tests/scanner_floor_probe.py <language> <output-root>

Prints one JSON object on stdout. Imported by
`tests/test_scanner_two_panel_layout.py`, which runs it once per language.

WHY A WHOLE PROCESS PER LANGUAGE. `core.i18n.set_language()` swaps the
catalogue, but every string already captured in a module-level constant or a
class attribute keeps the language it was imported in — and this window's width
is set by exactly such strings, the run button's own label among them. Measured
2026-09-03, in-process against one-process-per-language:

    es  1076 vs 1186   (-110)      sv  1048 vs 1083   (-35)
    de  1081 vs 1164   ( -83)      no  1048 vs 1107   (-59)
    fr  1090 vs 1167   ( -77)      ru  1109 vs 1123   (-14)

Swedish and Norwegian came back as English to the digit. A sweep that measures
that is not measuring the twelve languages; it is measuring English twelve
times, and it would pass with a hundred pixels of regression sitting in it.
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Run as a script, sys.path[0] is tests/ — the app itself is one level up.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QPoint, QRect, QSize                    # noqa: E402
from PyQt6.QtWidgets import (QAbstractButton, QApplication,      # noqa: E402
                             QComboBox, QLabel, QLineEdit,
                             QScrollArea, QSpinBox, QWidget)

# The narrowest screen the window has to fit, and the room insisted on beyond
# it. Kept here so the probe and the tests cannot drift apart.
SMALLEST_SCREEN = 1280
HEADROOM = 60
LANGUAGES = ["en", "de", "fr", "es", "it", "nl", "no", "pl", "pt", "ru", "sv",
             "ja", "zh_CN"]


class FakeSettings:
    """A settings double built from DEFAULTS, with its own output root.

    `custom_output_path` defaults to "", and "" means `~/ChromIQ` — the real
    projects folder. This window provisions standard scanner targets under the
    output root when it opens, so the root is pinned per instance.
    """

    def __init__(self, out_dir, **overrides):
        from core.settings import DEFAULTS
        self._store = {**DEFAULTS, **overrides}
        self._store["custom_output_path"] = str(out_dir)

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


def settle(app, dlg, n=6):
    for _ in range(n):
        app.processEvents()
    dlg.layout().activate()
    app.processEvents()


def clipped(dlg):
    """Every leaf control whose right edge falls outside its scroll viewport.

    A width the window can be dragged to but at which a control is cut in half
    is not a floor: both panes pin their horizontal scrollbar off, so there is
    nothing to scroll the missing part back into view.
    """
    bad = []
    for scroll, side in ((dlg._scroll, "left"), (dlg._scroll_right, "right")):
        vp = scroll.viewport()
        for w in scroll.widget().findChildren(QWidget):
            if not w.isVisible() or w.findChildren(QWidget):
                continue
            if not isinstance(w, (QAbstractButton, QLabel, QLineEdit,
                                  QComboBox, QSpinBox)):
                continue
            left = w.mapTo(vp, w.rect().topLeft()).x()
            if left + w.width() > vp.width() + 1:
                text = ""
                getter = getattr(w, "text", None)
                if callable(getter):
                    try:
                        text = getter()[:40]
                    except Exception:
                        pass
                bad.append(f"{side}: {type(w).__name__}({text!r}) "
                           f"+{left + w.width() - vp.width()}px")
    return bad


def handle_reach(dlg):
    """Each of the eight drag handles, and how much of its grab area is inside
    the preview pane's viewport and clear of that pane's scrollbar."""
    import ui.scan_grid_marquee as sgm
    corner, side = int(sgm._HANDLE_R * 2.4), int(sgm._SIDE_R * 2.8)
    mq = dlg._marquee
    host = mq
    while host is not None and not isinstance(host, QScrollArea):
        host = host.parentWidget()
    vp = host.viewport()
    vp_rect = QRect(vp.mapTo(dlg, QPoint(0, 0)), vp.size())
    vbar = host.verticalScrollBar()
    bar = (QRect(vbar.mapTo(dlg, QPoint(0, 0)), vbar.size())
           if vbar.isVisible() else QRect())

    names = ["top-left", "top-right", "bottom-right", "bottom-left",
             "top", "right", "bottom", "left"]
    out = {}
    for i, name in enumerate(names):
        p = mq._handle_pos(i) if i < 4 else mq._side_handle_pos(i - 4)
        r = corner if i < 4 else side
        box = QRect(mq.mapTo(dlg, QPoint(int(p.x()) - r, int(p.y()) - r)),
                    QSize(r * 2, r * 2))
        area = box.width() * box.height()
        seen = vp_rect.intersected(box)
        hidden = bar.intersected(box)
        out[name] = round(((seen.width() * seen.height())
                           - (hidden.width() * hidden.height())) / area, 3)
    return out


def dress_the_app(app, mode="light"):
    """Put the process in the state the real app runs in.

    Widths depend on it and the difference is not small: without the Fusion
    style and the appearance stylesheet, Spanish measures 1076 px where the
    running app needs 1186. `main.py` does exactly this at start-up, and
    nothing else in the suite may — `qapp.setStyle` and `qapp.setStyleSheet`
    reach every widget the process has alive, which is why this measurement
    gets a process of its own.
    """
    from main import WinButtonLayoutStyle
    from ui.widgets import CompositeAppFilter
    from ui.theme import apply_appearance
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app._probe_filter = CompositeAppFilter(app)     # keep it referenced
    app.installEventFilter(app._probe_filter)
    apply_appearance(app, None, mode)
    app.processEvents()


def measure(app, lang, out_dir):
    from core.i18n import set_language
    set_language(lang)
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    dlg = ScannerProfileDialog(object(), FakeSettings(out_dir))
    dlg.show()
    settle(app, dlg)

    def chart():
        dlg._mode_chromiq.setChecked(True)
        dlg._printer_cb.setChecked(False)

    def standard():
        dlg._printer_cb.setChecked(False)
        dlg._mode_standard.setChecked(True)

    def printer():
        dlg._mode_chromiq.setChecked(True)
        dlg._printer_cb.setChecked(True)

    # Every state that changes how wide the window has to be: the three source
    # modes, each with the Advanced section closed and open. The left column
    # swaps a whole sub-panel between the modes, and the Advanced section shows
    # a wider set of options for a printer profile than for a scanner one.
    states = []
    for name, setup in (("a ChromIQ chart", chart),
                        ("a standard target", standard),
                        ("printer from a scan", printer)):
        for advanced in (False, True):
            setup()
            settle(app, dlg)
            dlg._adv_inline_head.setChecked(advanced)
            settle(app, dlg)
            label = name + (", Advanced open" if advanced else
                            ", Advanced closed")
            states.append((label, setup, advanced, dlg.minimumWidth()))
    dlg._adv_inline_head.setChecked(False)
    settle(app, dlg)

    worst_state, worst = max(((s[0], s[3]) for s in states),
                             key=lambda sw: sw[1])

    # …and now sit the window on each state's own floor and look for damage.
    bad = []
    for label, setup, advanced, floor in states:
        setup()
        settle(app, dlg)
        dlg._adv_inline_head.setChecked(advanced)
        settle(app, dlg)
        dlg.resize(floor, 900)
        settle(app, dlg, 8)
        bad += [f"{label}, at {floor}px: {b}" for b in clipped(dlg)]
    dlg._adv_inline_head.setChecked(False)
    settle(app, dlg)

    # The handles, with a real target loaded, at the size the window opens and
    # at the floor it reports. Both are language-dependent: the left pane is
    # fixed at the width this language needs, so the preview beside it is a
    # different size in every one of the twelve.
    dlg._mode_standard.setChecked(True)
    dlg._refresh()
    dlg._reveal_target_files()
    settle(app, dlg, 8)
    opened = (dlg.width(), dlg.height())
    handles = {}
    for tag, size in (("as it opens", opened),
                      ("at its floor", (dlg.minimumWidth(),
                                        dlg.minimumHeight()))):
        dlg.resize(*size)
        settle(app, dlg, 4)
        dlg._marquee._recompute_fit()
        settle(app, dlg, 4)
        handles[tag] = handle_reach(dlg)

    return {
        "lang": lang,
        "worst": worst,
        "worst_state": worst_state,
        "floors": {s[0]: s[3] for s in states},
        "clipped": bad,
        "opens_at": opened[0],
        "handles": handles,
        "handles_out_of_reach": [f"{tag}: {name} {reach:.0%}"
                                 for tag, hs in handles.items()
                                 for name, reach in hs.items()
                                 if reach <= 0.6],
    }


def main(argv):
    lang = argv[1] if len(argv) > 1 else "en"
    out_dir = argv[2] if len(argv) > 2 else "."
    app = QApplication.instance() or QApplication([])
    dress_the_app(app)
    print(json.dumps(measure(app, lang, out_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
