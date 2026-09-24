"""Reusable step-header widget shown at the top of each workflow tab."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui import index_rule
from ui.styles import SPEC_MAGENTA, TAB_COLORS
from ui.tooltip_button import TooltipButton
from core.i18n import tr


class _InkTitleLabel(QLabel):
    """A one-line label whose size hints cover its INK, not only its advance.

    B8-962 (Basti, 2026-09-24, beta.40): the "Update available" masthead cut
    the last "e". The earlier fix (`TabHeader._fit_title_ink`, 2026-09-21)
    measured the ink once and pinned it as a minimum width, and that number
    was measured in the WRONG FONT whenever nothing re-fitted after the
    stylesheet was applied. Measured on screen, 2x: the heading paints in
    Georgia 30 px at 85 % spacing, advance 189, ink 191, and the label was
    189 wide with a minimum of 88, which is the ink of the unpolished 13 px
    default font the fit ran on in `__init__`. The tabs escaped only because
    `apply_theme` calls `set_appearance`, which re-fits; a dialog built after
    the theme was applied never hears it, and a `FontChange` on the LABEL
    never reaches the header's `changeEvent` anyway.

    So the ink is no longer a number stored at one moment: it is part of the
    size hint, asked for by the layout each time it lays the label out, from
    the font the label is polished into.

    `SPARE` is 2 px past the integer ink box, and both are needed: at 2x the
    antialiased edge of a round last glyph lands one DEVICE pixel past the
    box the metrics round to ("Build ICC profile", "ICC-Profil erstellen",
    "Створіть тестову діаграму" each photographed with ink in the column the
    box said was empty), and the rest is the pixel of air the heading is
    promised.
    """

    SPARE = 2

    def __init__(self, text: str, parent=None, *, wrap: bool = False) -> None:
        super().__init__(text, parent)
        #: A DIALOG heading may wrap onto a second line (beta 42 challenge,
        #: item 2). B8-962 gave the label its ink as a MINIMUM, and a minimum is
        #: only a request: a dialog that sets its own minimum width
        #: (`setMinimumWidth(620)` in the patch set editor) switches off the
        #: layout's, so a row that cannot fit squeezes every item below its
        #: minimum. Measured on screen: "Упорядкуй і перефарбуй свої плями"
        #: 433 px wide for 482 px of ink, "Organize e recolora as suas
        #: amostras" 349 for 415, both cut mid-word. So a wrapping heading
        #: asks for its whole ink on one line (`sizeHint`), accepts its
        #: longest WORD as its minimum, and breaks between words when the
        #: window gives it less. The tabs keep one line (`wrap=False`): their
        #: column is sized by the heading, and a tab heading on two lines
        #: would move the module buttons under it.
        self._wrap = bool(wrap)
        if self._wrap:
            self.setWordWrap(True)
            # The spare pixels are a MARGIN here, so a line broken to the
            # label's width still has them for its last glyph's overhang.
            self.setContentsMargins(0, 0, self.SPARE, 0)

    def _ink(self, text: str) -> int:
        from PyQt6.QtGui import QFontMetrics
        if not text:
            return 0
        fm = QFontMetrics(self.font())
        return max(fm.tightBoundingRect(text).right() + 1,
                   fm.boundingRect(text).right() + 1)

    def _ink_width(self) -> int:
        self.ensurePolished()
        text = self.text()
        if not text:
            return 0
        m = self.contentsMargins()
        spare = 0 if self._wrap else self.SPARE     # the margin holds it
        return self._ink(text) + spare + m.left() + m.right()

    def _widest_word(self) -> int:
        self.ensurePolished()
        m = self.contentsMargins()
        return max((self._ink(w) for w in self.text().split()), default=0) \
            + m.left() + m.right()

    def sizeHint(self):  # noqa: N802
        if self._wrap:
            w = self._ink_width()
            return QSize(w, self.heightForWidth(w))
        s = super().sizeHint()
        s.setWidth(max(s.width(), self._ink_width()))
        return s

    def minimumSizeHint(self):  # noqa: N802
        if self._wrap:
            w = self._widest_word()
            return QSize(w, self.heightForWidth(self._ink_width()))
        s = super().minimumSizeHint()
        s.setWidth(max(s.width(), self._ink_width()))
        return s


class TabHeader(QWidget):
    """Inline accent stroke before step label, large title below.

    Optionally renders a ⓘ tooltip button next to the title when
    ``tooltip_title`` and ``tooltip_body`` are supplied.
    """

    def __init__(
        self,
        step_text: str,
        title_text: str,
        accent_color: str,
        parent: QWidget | None = None,
        *,
        tooltip_title: str | None = None,
        tooltip_body: str | None = None,
        tooltip_color: str | None = None,
        trailing_widget: QWidget | None = None,
        wrap_title: bool = False,
    ) -> None:
        super().__init__(parent)
        # A wrapping title needs the header to grow when it takes a second
        # line; a one-line header is never taller than its hint.
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Preferred if wrap_title
                           else QSizePolicy.Policy.Maximum)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 8)
        root.setSpacing(4)

        # First row: colored stroke + step text side by side
        step_row = QHBoxLayout()
        step_row.setContentsMargins(0, 0, 0, 0)
        step_row.setSpacing(8)

        self._accent = accent_color
        self._bar = bar = QFrame(self)
        bar.setFixedSize(22, 2)
        step_row.addWidget(bar, 0, Qt.AlignmentFlag.AlignVCenter)

        self._step_lbl = QLabel(step_text, self)
        self._paint_accent()
        step_row.addWidget(self._step_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        step_row.addStretch()

        root.addLayout(step_row)

        # Second row: large title (+ optional tooltip icon)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)

        self._title_lbl = _InkTitleLabel(title_text, self, wrap=wrap_title)
        # No color rule — inherit from active theme (LM_TEXT_MAIN in light,
        # TEXT_MAIN in dark) so the title stays legible on either bg.
        self._title_lbl.setStyleSheet(
            "background: transparent;"
            " font-family: Georgia; font-size: 30px;"
        )
        title_font = QFont()
        title_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 85)
        self._title_lbl.setFont(title_font)
        self._fit_title_ink()
        title_row.addWidget(self._title_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        self._tooltip_btn: TooltipButton | None = None
        if tooltip_title and tooltip_body:
            tip_kwargs = {"min_width": 560}
            if tooltip_color is not None:
                tip_kwargs["color"] = tooltip_color
            self._tooltip_btn = TooltipButton(
                tooltip_title, tooltip_body, self, **tip_kwargs
            )
            btn_wrap = QWidget(self)
            btn_layout = QVBoxLayout(btn_wrap)
            btn_layout.setContentsMargins(0, 4, 0, 0)
            btn_layout.setSpacing(0)
            btn_layout.addWidget(self._tooltip_btn)
            title_row.addWidget(btn_wrap, 0, Qt.AlignmentFlag.AlignVCenter)

        title_row.addStretch()
        # Optional far-right widget on the title row (e.g. the Print tab's
        # amber "load existing target" grid button), mirroring the star/folder
        # trio on the Create Chart tab (#70, Knut).
        if trailing_widget is not None:
            trailing_widget.setParent(self)
            title_row.addWidget(trailing_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        # THE TITLE ROW IS THE SAME HEIGHT ON EVERY TAB. Its natural height is
        # whatever its tallest child happens to be — 40 px where a trailing
        # button trio sits, 35 px where only the title label does — so the
        # module buttons underneath started on different lines from tab to tab
        # (Basti, 2026-08-09: Create Chart and Measure matched, Build Profile
        # sat lower, Check & Refine higher). A zero-width strut pins the
        # floor at the standard trailing-button height; tabs whose trailing
        # widget wants more must fit it into the same 40 px instead.
        _strut = QWidget(self)
        _strut.setFixedSize(0, 40)
        title_row.addWidget(_strut)
        root.addLayout(title_row)

    def _paint_accent(self) -> None:
        """The 22x2 stroke and the eyebrow, for the appearance now on screen.

        TWO VALUES CHANGE IN NEUTRAL AND NEITHER IS COSMETIC. The stroke is a
        per-tab hue — tab identity carried by a shade, which is the one thing
        the chosen accent draft replaces — so it becomes the single ACTION
        value; identity is the Index rule's job now. And `#808080` is 3.05:1 on
        the Neutral panel, which in this theme means "disabled" and nothing
        else (handoff rule 3), so the eyebrow takes TEXT_FAINT at 8.13:1. Light
        and Dark keep both values exactly as they were.
        """
        if index_rule.use_index_rule():
            from ui import neutral_styles
            stroke = neutral_styles.NM_ACTION
            eyebrow = neutral_styles.NM_TEXT_FAINT
        else:
            stroke = self._accent
            eyebrow = "#808080"
        self._bar.setStyleSheet(f"background-color: {stroke}; border: none;")
        self._step_lbl.setStyleSheet(
            f"color: {eyebrow}; background: transparent;"
            " font-family: Menlo; font-size: 12px; font-weight: 300;"
        )

    def set_appearance(self, _mode: str) -> None:
        """Re-paint the accent stroke and eyebrow for a new appearance.

        `MainWindow.apply_theme` broadcasts to every descendant that has this
        method. Both values are set with a per-widget stylesheet, so nothing
        else would refresh them: before this, a header built under Light kept
        its tab hue after a switch to Neutral.
        """
        self._fit_title_ink()
        self._paint_accent()

    def _fit_title_ink(self) -> None:
        """Give the title the width of its INK, not of its advance.

        Sebastian reported this three times and it was never marginal: *"the
        last letter has a few px cut off"* on the Print Chart heading. The
        string fits by every width calculation there is, and the final letter
        is still sliced.

        WHICH OF THE THREE CAUSES IT IS, measured on screen 2026-09-21 in a
        real window, this heading being Georgia at 30 px with
        `setLetterSpacing(85 %)`:

            lang  advance   ink right   label width   ink outside
            uk        354         356           354          2 px
            de        205         207           205          2 px
            en        169         170           170          0 px

        Not elision (the label is not narrower than its text) and not a clip
        rect. It is the **right side bearing**: Georgia's last glyph paints
        past the advance the layout reserved for it, and `QLabel.sizeHint()` is
        built from `horizontalAdvance`, so the widget is sized to the layout
        box while the ink needs one or two pixels more. The 85 % letter
        spacing pulls every advance in and makes the gap a little wider again.

        So the minimum is raised to the ink box. Measured across five headings
        in three languages, fourteen of the fifteen were losing 1-2 px and the
        one that was not is English "Print test chart", which happens to end in
        a `t`. This is why it looked like a Ukrainian problem: Ukrainian is
        merely the language whose headings are longest and whose final letters
        are round.

        B8-962 (2026-09-24): the ink is now part of the label's own size
        hints (`_InkTitleLabel`), computed from the polished font whenever the
        layout asks. A minimum width stored here was a measurement of whatever
        font the label had at the moment of the call, and a dialog masthead
        was measured in the 13 px default font and kept 88 px as its minimum.
        What is left is to drop any stored minimum and ask the layout again.
        """
        self._title_lbl.setMinimumWidth(0)
        self._title_lbl.updateGeometry()

    def changeEvent(self, event) -> None:  # noqa: N802
        """Re-fit whenever the FONT this is painted in can have changed.

        Measuring once in `__init__` is measuring the wrong font: the heading
        is Georgia 30 px because of the application stylesheet, which is
        applied after the widget is built. The first version of this fix did
        exactly that and moved one heading out of five.
        """
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange,
                            QEvent.Type.ApplicationFontChange):
            self._fit_title_ink()

    def set_texts(self, step_text: str, title_text: str) -> None:
        self._step_lbl.setText(step_text)
        self._title_lbl.setText(title_text)
        self._fit_title_ink()

    def set_tooltip(self, title: str, body: str) -> None:
        """Update the headline tooltip's title and body."""
        if self._tooltip_btn is None:
            return
        self._tooltip_btn._title = title
        self._tooltip_btn._body = body.strip()
        self._tooltip_btn.setToolTip(title + "\n\n" + tr("Click for details"))


class SpectrumStripe(QWidget):
    """The dialog masthead's rule — the same part the main-window masthead wears.

    In Light and Dark it is a thin full-width band of the five ChromIQ tab hues
    painted as equal blocks. The hues (TAB_COLORS) are plain spectrum colours,
    identical in both, so it needs no per-mode palette there.

    In Neutral it is the **Index rule** (:mod:`ui.index_rule`): five cells
    filled up to ``step``. One component replaces the spectrum bar at every
    screen site, and a dialog masthead is one of them — this stripe measured
    100 % non-neutral, five hues wide, in a theme that has none.

    ``step`` is where in the run this window belongs, which
    :func:`dialog_masthead` derives from the accent it was given: a Measure
    tool's masthead is at step 3 whether or not it is green. A window with no
    place in the run leaves it at :data:`ui.index_rule.ALL`.
    """

    HEIGHT = 4

    def __init__(self, parent: QWidget | None = None, *,
                 step: int = index_rule.ALL) -> None:
        super().__init__(parent)
        self._step = step
        self.setFixedHeight(self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def step(self) -> int:
        return self._step

    def set_step(self, step: int) -> None:
        if step != self._step:
            self._step = step
            self.update()

    def set_appearance(self, _mode: str) -> None:
        """Repaint. The appearance itself is read at paint time, from the live
        application palette, so there is no stored mode here to go stale."""
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        w = self.width()
        if index_rule.use_index_rule():
            index_rule.paint_index_rule(p, 0, 0, w, self.HEIGHT, self._step)
        else:
            n = len(TAB_COLORS)
            for i, col in enumerate(TAB_COLORS):
                x0 = int(round(i * w / n))
                x1 = int(round((i + 1) * w / n)) if i < n - 1 else w
                p.fillRect(x0, 0, x1 - x0, self.HEIGHT, QColor(col))
        p.end()


def dialog_masthead(
    parent: QWidget,
    eyebrow: str,
    title: str,
    *,
    tooltip_title: str | None = None,
    tooltip_body: str | None = None,
    accent: str = SPEC_MAGENTA,
    side: int = 22,
    top: int = 18,
    bottom: int = 12,
    wrap_title: bool = True,
):
    """Build the standard ChromIQ dialog masthead: an inset :class:`TabHeader`
    (uppercase eyebrow + large serif title, optional ⓘ) above a full-width
    :class:`SpectrumStripe` — the same look the chart-design windows use.

    Returns ``(head_layout, header, stripe)``. The caller adds ``head_layout``
    then ``stripe`` to an outer layout whose side margins are **0** so the
    stripe runs edge to edge; the header carries its own ``side`` inset, and the
    body below should re-add the same inset.

    Also installs an accent-coloured :class:`~ui.gradient_overlay.GradientOverlay`
    over the top of ``parent`` — the same colour wash the main-window tabs have
    behind their headline (it's parented to the dialog, so it lives as long as
    the dialog and refits/raises itself).
    """
    # ONE ACCENT UNDER NEUTRAL, for every dialog masthead in the app — the
    # header stroke, the ⓘ ring and the GradientOverlay wash installed below
    # all take their colour from here. Light and Dark are handed back exactly
    # what the caller asked for.
    from ui.theme import accent_for
    accent = accent_for(accent)
    head = QHBoxLayout()
    head.setContentsMargins(side, top, side, bottom)
    header = TabHeader(
        eyebrow, title, accent, parent,
        tooltip_title=tooltip_title, tooltip_body=tooltip_body,
        tooltip_color=accent, wrap_title=wrap_title,
    )
    head.addWidget(header, 1, Qt.AlignmentFlag.AlignVCenter)
    # WHERE IN THE RUN THIS WINDOW BELONGS, taken from the accent it already
    # declares: a Measure tool passes SPEC_GREEN, which is tab 3. In Light and
    # Dark the accent paints the hue and the step is unused; in Neutral the hue
    # is gone and the step is the only thing left saying which part of the
    # workflow you are in. An accent that is not one of the five (a tool with
    # its own colour) means "no position" and fills the rule.
    try:
        step = TAB_COLORS.index(accent) + 1
    except ValueError:
        step = index_rule.ALL
    stripe = SpectrumStripe(parent, step=step)
    if parent is not None:
        from ui.gradient_overlay import GradientOverlay
        # Same peak saturation as the main-window tab wash (alpha 15), but taller
        # so the subtle gradient still reaches the headline, which sits lower in a
        # dialog than in a tab pane.
        GradientOverlay(accent, parent=parent, alpha=15, height=95, on_top=False)
    return head, header, stripe
