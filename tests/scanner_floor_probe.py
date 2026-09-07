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
from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox,  # noqa: E402
                             QApplication, QComboBox, QLabel,
                             QLineEdit, QScrollArea, QWidget)

# The narrowest screen the window has to fit, and the room insisted on beyond
# it. Kept here so the probe and the tests cannot drift apart.
SMALLEST_SCREEN = 1280
HEADROOM = 60

# …and the same question for HEIGHT, which was never asked. The window came out
# of the two-panel rework with a floor of 675 logical pixels on the Windows VM
# and 716 measured here — on a 1920x1080 laptop at 150 % scaling, which has 720
# logical pixels minus a 48 px taskbar, so 672. A window whose minimum exceeds
# the screen cannot be used at all (finding C of the Windows verification,
# 2026-09-03). `minimumHeight` is a CLIENT height, so the caption comes off too.
SMALLEST_SCREEN_H = 720
TASKBAR_H = 48
TITLEBAR_H = 32
SMALLEST_CLIENT_H = SMALLEST_SCREEN_H - TASKBAR_H - TITLEBAR_H
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


#: The controls the checks below look at. A control not in this list is not
#: measured, so it is also not what "leaf" means — see `clipped`.
CHECKED = (QAbstractButton, QLabel, QLineEdit, QComboBox, QAbstractSpinBox)
#: Controls built OUT OF other controls. A combo owns its popup container, a
#: spin box owns a line edit and two buttons — those parts are not separate
#: controls and the whole is what the user sees, so a compound is always a leaf
#: and nothing inside it is ever one.
COMPOUND = (QComboBox, QAbstractSpinBox)


def _leaves(root):
    """Every visible control the user sees as one thing.

    "Leaf" cannot mean *has no child widget*. A QComboBox owns its popup
    container and a QSpinBox owns a QLineEdit, so that version dropped both —
    on the real window with Advanced open it checked **0 of 7 combos and 0 of
    1 spin boxes**, the exact widget type this window's width was trimmed on.
    Every clip figure printed here had been measured over labels, buttons,
    checkboxes and line edits only.

    Nor can it mean *has no child of a CHECKED kind*: that lets a combo back in
    but still drops a spin box, whose inner QLineEdit is itself CHECKED — and
    the line edit is not where a spin box is widest, its buttons are.
    """
    compounds = [w for w in root.findChildren(QWidget)
                 if w.isVisible() and isinstance(w, COMPOUND)]
    for w in root.findChildren(QWidget):
        if not w.isVisible() or not isinstance(w, CHECKED):
            continue
        if isinstance(w, COMPOUND):
            yield w
            continue
        if any(c.isAncestorOf(w) for c in compounds):
            continue            # a part of a compound control, not a control
        if any(c.isVisible() and isinstance(c, CHECKED)
               for c in w.findChildren(QWidget)):
            continue
        yield w


def clipped(dlg):
    """Every leaf control whose right edge falls outside its scroll viewport.

    A width the window can be dragged to but at which a control is cut in half
    is not a floor: both panes pin their horizontal scrollbar off, so there is
    nothing to scroll the missing part back into view.

    This is GEOMETRY. It says nothing about whether the text inside a control
    that does fit can be read — `unreadable` below is that question, and it is
    the one that matters for a combo.
    """
    bad = []
    for scroll, side in ((dlg._scroll, "left"), (dlg._scroll_right, "right")):
        vp = scroll.viewport()
        for w in _leaves(scroll.widget()):
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


def width_for(combo, text):
    """The width Qt says *combo* needs to show *text*, in pixels.

    Qt's own arithmetic, not an estimate: `sizeFromContents(CT_ComboBox, …)`
    over `fontMetrics().boundingRect(text)` is the same computation
    `QComboBox.sizeHint()` runs, and it reproduces the hint of an
    AdjustToContents combo holding exactly that string to the pixel.

    A ruler matters here. The obvious one — `width() - 30` for the arrow and
    the frame — is 2-3 px pessimistic, which is inside the noise for a long
    string and outside it for a short one: it reports the profile-quality
    combo's own default as cut in all thirteen catalogues, and that combo sits
    at its own size hint and is not cut at all.
    """
    from PyQt6.QtCore import QSize
    from PyQt6.QtWidgets import QStyle, QStyleOptionComboBox
    opt = QStyleOptionComboBox()
    combo.initStyleOption(opt)
    fm = combo.fontMetrics()
    return combo.style().sizeFromContents(
        QStyle.ContentsType.CT_ComboBox, opt,
        QSize(fm.boundingRect(text).width(), fm.height()), combo).width()


def unreadable(dlg):
    """Every visible combo that cannot show the value it is set to.

    THE QUESTION `clipped` DOES NOT ASK. A combo can sit entirely inside its
    viewport, be measured as fine, and still be showing a word cut in half:
    Qt paints a combo's label into the room the style gives it and does not
    elide, so text that does not fit is simply gone. That is how a cap of
    eighteen characters put `Отобразить белое мишени в белое (по` on screen —
    the combo's own DEFAULT, mid-word, in a window with no clip anywhere.

    Checked for every combo the window shows, including the ones behind an
    unticked checkbox: a disabled combo still displays its value.
    """
    bad = []
    for c in dlg.findChildren(QComboBox):
        if not c.isVisible():
            continue
        text = c.currentText()
        need = width_for(c, text)
        if need > c.width():
            bad.append(f"{type(c).__name__}({text[:44]!r}) needs {need}px, "
                       f"has {c.width()}px")
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


def require_language(lang):
    """Fail LOUDLY if the catalogue did not actually load.

    A process per language fixes the cause of the old sweep's lie; it does not
    make the sweep NOTICE the next one. `set_language()` falls back to English
    silently on three paths (a missing file, a broken file, an unknown code),
    and this probe reports the language it was ASKED for — so a fallback is
    byte-for-byte indistinguishable from a real measurement, and the sweep goes
    straight back to measuring English thirteen times with nothing red.
    Measured: `set_language("es_ES")` returns quietly and the probe then prints
    1048, which is English to the digit and passes every assertion above it.
    """
    from core.i18n import current_language, tr
    got = current_language()
    if got != lang:
        raise SystemExit(
            f"the catalogue for {lang!r} did not load — core.i18n is in "
            f"{got!r}. Every number this probe printed would be {got!r}'s, "
            f"under {lang!r}'s name.")
    if lang != "en":
        # …and it holds strings, not just the code. This one is on the window
        # under measurement, in every catalogue.
        probe = "Build profile with scanner or camera"
        if tr(probe) == probe:
            raise SystemExit(
                f"the catalogue for {lang!r} loaded but translates nothing — "
                f"{probe!r} came back in English.")
    return got


#: THE WINDOW MUST NOT MOVE WHEN A RADIO IS PRESSED (Basti, beta 9): *"when
#: switching the radio for 'create profile using' the window's size changes
#: sometimes a bit, things jump around a bit."* It did both, and the two halves
#: had different causes:
#:
#:  * the window was dragged back to its sizeHint height on every switch that
#:    changed the settings bucket, because `_sync_inline_advanced` re-applied
#:    the Advanced pane width by calling the disclosure's own toggle handler,
#:    which ends in `_refit_height()`. Measured: a window at 700 px jumped to
#:    796, one at its 640 px floor jumped 156 px;
#:  * `_mode_note`, the five-line "why the printer option is not offered for a
#:    bought target" paragraph, sat ABOVE "Create profile using:" and appears
#:    exactly when that question is answered "a standard target", so both
#:    source radios slid 79 px down in English and 94 in Russian.
#:
#: Measured here in every language, because the size of the fault is the size
#: of a translated paragraph.
def _steadiness_anchors(dlg):
    """The controls a radio click must never move: every radio in both groups.

    Not the input boxes below them. The source click swaps a whole sub-panel
    (115 px against 157 px in English) because that is the content the click is
    ABOUT, and content that changes is not a jump. A radio is what the pointer
    is on.
    """
    out = {"source: a chart I made in ChromIQ": dlg._mode_chromiq,
           "source: a standard target I own": dlg._mode_standard}
    for key, rb in dlg._scenario_radios.items():
        out[f"scenario: {key}"] = rb
    return out


def _anchor_ys(dlg):
    content = dlg._scroll.widget()
    return {name: w.mapTo(content, w.rect().topLeft()).y()
            for name, w in _steadiness_anchors(dlg).items()}


def radio_steadiness(app, dlg):
    """Click every radio in both groups, at two window heights, and report
    everything that moved. An empty list is the whole of the requirement.

    Two heights, because the resize half of the fault is invisible at the
    height the window opens at: `_refit_height` resizes TO the sizeHint, so a
    window already at its sizeHint does not appear to move. It is only a user
    who has made the window shorter who sees it, which is why the report said
    "sometimes".
    """
    from ui.dialogs import scanner_colprof as sc

    def chart():
        dlg._mode_chromiq.setChecked(True)

    def standard():
        dlg._mode_standard.setChecked(True)

    def scenario(key):
        def go():
            rb = dlg._scenario_radios[key]
            if rb.isEnabled():
                rb.setChecked(True)
        return go

    # Each transition is (a state to start from, the click, what to call it).
    # Every one starts from a named state, so the order of this list cannot
    # change what any single row measures.
    transitions = [
        (chart, standard, "Create profile using: chart -> standard target"),
        (standard, chart, "Create profile using: standard target -> chart"),
        (scenario(sc.SCENARIO_EVERYDAY), scenario(sc.SCENARIO_INSTRUMENT),
         "Usage scenario: everyday -> measuring instrument"),
        (scenario(sc.SCENARIO_INSTRUMENT), scenario(sc.SCENARIO_PRINTER),
         "Usage scenario: measuring instrument -> printer"),
        (scenario(sc.SCENARIO_PRINTER), scenario(sc.SCENARIO_EVERYDAY),
         "Usage scenario: printer -> everyday"),
    ]

    opens_at = dlg.height()
    findings = []
    for height in (opens_at, 700):
        for start, click, label in transitions:
            dlg._mode_chromiq.setChecked(True)
            dlg._scenario_radios[sc.SCENARIO_EVERYDAY].setChecked(True)
            start()
            dlg.resize(dlg.width(), height)
            settle(app, dlg, 8)
            was_h, was = dlg.height(), _anchor_ys(dlg)
            click()
            settle(app, dlg, 8)
            now_h, now = dlg.height(), _anchor_ys(dlg)
            if now_h != was_h:
                findings.append(
                    f"at {height}px, {label}: the WINDOW changed height "
                    f"{was_h} -> {now_h}")
            for name, y in was.items():
                if now[name] != y:
                    findings.append(
                        f"at {height}px, {label}: “{name}” moved "
                        f"{y} -> {now[name]} ({now[name] - y:+d}px)")
    dlg._mode_chromiq.setChecked(True)
    dlg._scenario_radios[sc.SCENARIO_EVERYDAY].setChecked(True)
    dlg.resize(dlg.width(), opens_at)
    settle(app, dlg, 8)
    return findings


def gloss_heights(dlg):
    """The height of each usage-scenario gloss, in pixels.

    They are levelled (`_LevelHint`), so a language in which one wraps and the
    others do not still has ONE block height and the rows below it do not move
    in that language alone.
    """
    return [g.height() for g in dlg._scenario_glosses]


def measure(app, lang, out_dir):
    from core.i18n import set_language
    set_language(lang)
    require_language(lang)
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
            # HEIGHT AS WELL AS WIDTH, and per state for the same reason width
            # is: Advanced open adds rows to the left column, which is the
            # column that sets this window's height floor.
            states.append((label, setup, advanced, dlg.minimumWidth(),
                           max(dlg.minimumHeight(),
                               dlg.minimumSizeHint().height())))
    dlg._adv_inline_head.setChecked(False)
    settle(app, dlg)

    worst_state, worst = max(((s[0], s[3]) for s in states),
                             key=lambda sw: sw[1])
    worst_h_state, worst_h = max(((s[0], s[4]) for s in states),
                                 key=lambda sh: sh[1])

    # …and now sit the window on each state's own floor and look for damage.
    bad = []
    cut = []
    combos_seen = 0
    for label, setup, advanced, floor, _floor_h in states:
        setup()
        settle(app, dlg)
        dlg._adv_inline_head.setChecked(advanced)
        settle(app, dlg)
        dlg.resize(floor, 900)
        settle(app, dlg, 8)
        bad += [f"{label}, at {floor}px: {b}" for b in clipped(dlg)]
        cut += [f"{label}, at {floor}px: {b}" for b in unreadable(dlg)]
        combos_seen = max(combos_seen, len([c for c in dlg.findChildren(QComboBox)
                                            if c.isVisible()]))
    dlg._adv_inline_head.setChecked(False)
    settle(app, dlg)

    # …and now the same window's STEADINESS: what a radio click moves, in this
    # language, at the height it opens at and at one the user has shrunk.
    dlg._mode_chromiq.setChecked(True)
    dlg._printer_cb.setChecked(False)
    settle(app, dlg)
    jumps = radio_steadiness(app, dlg)
    glosses = gloss_heights(dlg)

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

    from core.i18n import current_language
    return {
        "lang": lang,
        # The language the process is ACTUALLY in, not the one it was asked
        # for — see require_language above.
        "language_applied": current_language(),
        "worst": worst,
        "worst_state": worst_state,
        "floors": {s[0]: s[3] for s in states},
        "worst_h": worst_h,
        "worst_h_state": worst_h_state,
        "floors_h": {s[0]: s[4] for s in states},
        "clipped": bad,
        # Combos that cannot show the value they are set to, and how many
        # combos were looked at to say so — a zero here is only worth
        # something next to a non-zero there.
        "unreadable": cut,
        "combos_checked": combos_seen,
        "opens_at": opened[0],
        # Everything a radio click moved. Empty is the requirement.
        "jumps": jumps,
        # The three usage-scenario glosses, which are levelled against one
        # another, so these three numbers must be one number.
        "gloss_heights": glosses,
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
