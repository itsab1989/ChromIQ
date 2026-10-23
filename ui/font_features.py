"""Letters as they are typed: no contextual alternates in ChromIQ's font.

Basti, 2026-10-23 (approved): the bundled Inter font turns "4x6" into
"4×6" on screen, and "100 x 148 mm" into "100 × 148 mm", by itself. That is
its contextual alternates feature, OpenType ``calt``: measured on Inter
4.x (``assets/fonts``), "4x6" shapes to the glyph of a multiplication sign
in the x's place with ``calt`` on and to the plain "x" with it off, and an
"x" between letters is never touched. A project or paper NAME then reads
differently on screen from what is on disk, and a real "×" in a dimension
can no longer be told from a typed "x". So ``calt`` is switched off for the
whole application, and every text that MEANS a multiplication sign carries
the real character "×" itself.

Set on the application font, it reaches every widget (style sheets that
name "Inter" keep it), every ``QPainter`` text (a ``QFont("Inter")`` made
anywhere resolves the feature against the application font), and every
``QTextDocument`` the app lays out, the Measurement Report and its PDF
included. ``tests/test_text_shows_as_typed.py`` keeps it that way.
"""
from __future__ import annotations

#: The OpenType feature switched off: contextual alternates.
FEATURE = "calt"
#: Every class Qt's platform themes may give a font of its own (Qt 6's
#: QApplicationPrivate::initializeWidgetFontHash); a subclass follows its
#: base class.
WIDGET_FONT_CLASSES = (
    "QMenu", "QMenuBar", "QMenuItem", "QMessageBox", "QLabel", "QTipLabel",
    "QStatusBar", "QWorkspaceTitleBar", "QMdiSubWindowTitleBar",
    "QDockWidgetTitle", "QPushButton", "QCheckBox", "QRadioButton",
    "QToolButton", "QAbstractItemView", "QListView", "QHeaderView",
    "QListBox", "QComboMenuItem", "QComboLineEdit", "QSmallFont",
    "QMiniFont", "QGroupBox", "QTabBar", "QLineEdit", "QTextEdit",
    "QPlainTextEdit", "QComboBox", "QSpinBox", "QAbstractSpinBox",
    "QTreeView", "QTableView", "QToolTip",
)


def show_text_as_typed(app) -> None:
    """Switch Inter's contextual alternates off for every text *app* draws.
    Call it once, right after the QApplication exists and before any window
    is built (``main()``, ``scripts/capture_screens.build_app``, the test
    suite's QApplication)."""
    from PyQt6.QtGui import QFont
    tag = QFont.Tag(FEATURE)
    font = app.font()
    font.setFeature(tag, 0)
    app.setFont(font)
    # THE PLATFORM'S PER-CLASS FONTS TOO. Measured on screen (macOS, agent 22,
    # 2026-10-23): with only the application font set, 1,369 of 2,810 widgets
    # of the main window still drew "4x6" as "4×6", the bar's "Location being
    # edited" line among them. Qt's macOS theme gives some classes a font of
    # their own (QApplicationPrivate::initializeWidgetFontHash: labels,
    # buttons, check boxes, item views, ...), and a widget of such a class,
    # or of a subclass, takes that font instead of the application's. The
    # offscreen platform has none, which is why the suite did not see it.
    for name in WIDGET_FONT_CLASSES:
        f = app.font(name)
        if not (f.isFeatureSet(tag) and f.featureValue(tag) == 0):
            f.setFeature(tag, 0)
            app.setFont(f, name)


def shows_as_typed(font) -> bool:
    """True when *font* draws text exactly as typed (``calt`` off)."""
    from PyQt6.QtGui import QFont
    tag = QFont.Tag(FEATURE)
    return font.isFeatureSet(tag) and font.featureValue(tag) == 0


def keep_widget_typed(obj) -> None:
    """Give one widget's own font contextual alternates off, when it lacks
    it. Called by the application event filter on every Polish and
    FontChange (``ui.widgets.CompositeAppFilter``).

    WHY A WIDGET AT A TIME, measured on screen (macOS, agent 22, 2026-10-23):
    with the application font and every per-class font set, 1,369 of the
    main window's 2,810 widgets still drew "4x6" as "4×6", the bar's
    "Location being edited" line among them. The macOS theme hands out its
    own per-class fonts again when the platform theme is applied (after
    start-up), and a widget a style sheet styles is given its font
    explicitly when it is polished. Both happen after any start-up setting,
    so the setting is put on the widget's font where it is decided. The
    font is otherwise the widget's own, unchanged: nothing is resized."""
    try:
        if not obj.isWidgetType():
            return
        from PyQt6.QtGui import QFont
        tag = QFont.Tag(FEATURE)
        f = obj.font()
        if f.isFeatureSet(tag) and f.featureValue(tag) == 0:
            return
        f.setFeature(tag, 0)
        obj.setFont(f)
    except Exception:          # noqa: BLE001 - a font is never worth a crash
        pass


def _typed_text_filter_class():
    from PyQt6.QtCore import QEvent, QObject

    class TypedTextFilter(QObject):
        """`keep_widget_typed` as a filter of its own, for main.py's
        CHROMIQ_SEPARATE_FILTERS=1 path (the composite does it otherwise)."""

        def eventFilter(self, obj, event):  # noqa: N802 - Qt's name
            if event.type() in (QEvent.Type.Polish, QEvent.Type.FontChange):
                keep_widget_typed(obj)
            return False
    return TypedTextFilter


def __getattr__(name):
    if name == "TypedTextFilter":
        return _typed_text_filter_class()
    raise AttributeError(name)
