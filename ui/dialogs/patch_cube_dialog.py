"""Pop-up 3D RGB-cube view of the layout editor's patch set.

Launched from the editor's Patches controls ("3D distribution…"). Embeds the
shared :class:`ui.patch_cube_panel.PatchCubePanel` (a self-contained Plotly page
in a ``QWebEngineView``) and shows it modally — a one-shot snapshot of the
current patch set. The generator dialogs reuse the same panel *inline* for their
live preview; see :mod:`ui.patch_cube_panel`.

View-only: the cube doesn't edit the chart, so the dialog holds no editor
state. It takes a snapshot of the current program and renders it; reopening
after edits re-renders the new snapshot.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from core.logger import get_logger
from core.i18n import tr
from ui.patch_cube_panel import PatchCubePanel
from ui.styles import SPEC_MAGENTA, combo_popup_qss
from ui.tab_header import dialog_masthead

log = get_logger(__name__)


#: The ⓘ of the "Show:" choice (Knut, #182 6113365581).
_VIEW_HELP = (
    "Ink amounts: each patch sits at the red, green and blue values the "
    "printer is asked for, from 0 to 100.\n\n"
    "Colours through the profile: each patch sits where the profile says it "
    "lands as a colour (L* up, a* and b* across). The lines and the faint "
    "skin are the edges and sides of everything the profile can print.\n\n"
    "A chart made From Profile Gamut spaces its colours evenly as colours. "
    "A printer does not respond evenly to ink amounts, so the same chart can "
    "look crowded in one part of the RGB cube and sparse in another.")


def _view_help() -> str:
    """The "Show:" choice's help: M-HELP-COLOUR-VIEW-SEAMS once approved
    (Knut, #182 6144104040: the lines are seams on the skin, not its outline),
    until then the text shipped in beta 2."""
    from workflow.measurement_messages import M_HELP_COLOUR_VIEW_SEAMS as M
    return M.render()[1] if M.approved else tr(_VIEW_HELP)


def _legend_lines() -> "list[str] | None":
    """The colour view's key, M-HELP-COLOUR-VIEW-LEGEND, one line per item
    (skin, lines, dots) once approved (Knut, #182 6148467471); until then
    None, and the view looks exactly as in beta 2."""
    from workflow.measurement_messages import M_HELP_COLOUR_VIEW_LEGEND as M
    if not M.approved:
        return None
    lines = M.render()[1].split("\n")
    return lines if len(lines) == 3 else None


#: Room the window frame takes above and around the dialog (the macOS title
#: bar is 28 px), so the whole window, frame included, fits the work area.
_FRAME_W, _FRAME_H = 16, 40


def default_dialog_size(want_w: int, want_h: int, parent=None) -> "tuple[int, int]":
    """*want_w* x *want_h*, held to the available screen geometry (the work
    area, without menu bar and Dock) of the screen the dialog opens on: at
    1280 x 800 the work area is about 1280 x 705, and 760 px plus the title
    bar did not fit (4.3.5 beta 4). Never below the dialog's minimum."""
    from PyQt6.QtGui import QGuiApplication
    screen = None
    try:
        if parent is not None and parent.window() is not None:
            screen = parent.window().screen()
    except Exception:  # noqa: BLE001 - fall back to the primary screen
        screen = None
    screen = screen or QGuiApplication.primaryScreen()
    if screen is None:
        return want_w, want_h
    avail = screen.availableGeometry()
    return (max(520, min(want_w, avail.width() - _FRAME_W)),
            max(480, min(want_h, avail.height() - _FRAME_H)))


def _blend(fg: QColor, bg: QColor, alpha: float) -> QColor:
    """``fg`` laid over ``bg`` at ``alpha``, as the plot composites it."""
    return QColor(*(round(alpha * f + (1 - alpha) * b) for f, b in
                    ((fg.red(), bg.red()), (fg.green(), bg.green()),
                     (fg.blue(), bg.blue()))))


class _LegendSample(QWidget):
    """A drawn sample of one item of the colour view, in the plot's own
    colours and on its background: the skin (the theme's foreground seen
    through the skin's two sides), a line on it (foreground at the lines'
    opacity and width) or dots (patches, each in its own colour)."""

    #: The patch dots of the sample: a red, a green and a blue patch.
    DOTS = ((214, 48, 49), (46, 160, 67), (52, 101, 206))

    def __init__(self, kind: str, bg: str, fg: str, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._bg = QColor(bg)
        self._fg = QColor(fg)
        self.setFixedSize(QSize(34, 18))

    def paintEvent(self, _ev) -> None:  # noqa: N802
        from workflow.patch_cube import LINE_OPACITY, SKIN_OPACITY
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(r, 4, 4)
        # The skin is a closed see-through surface, so the eye looks through
        # two layers of it (near side and far side): measured on screen, the
        # plot's skin is the foreground at 1 - (1 - SKIN_OPACITY)^2 over the
        # background, not at SKIN_OPACITY. The lines lie on the skin.
        skin = _blend(self._fg, self._bg, 1 - (1 - SKIN_OPACITY) ** 2)
        if self.kind in ("skin", "line"):
            p.setBrush(skin)
            p.drawRoundedRect(r.adjusted(4, 3, -4, -3), 5, 5)
        if self.kind == "line":
            p.setPen(QPen(_blend(self._fg, skin, LINE_OPACITY), 2.0))
            p.drawLine(QPointF(r.left() + 4, r.center().y()),
                       QPointF(r.right() - 4, r.center().y()))
        elif self.kind == "dots":
            step = r.width() / (len(self.DOTS) + 1)
            for n, rgb in enumerate(self.DOTS, start=1):
                p.setBrush(QColor(*rgb))
                p.drawEllipse(QPointF(r.left() + n * step, r.center().y()),
                              3.0, 3.0)
        p.end()


class ColourViewLegend(QFrame):
    """The key to "Colours through the profile": the grey skin, the lines
    and the dots, each beside a sample drawn as the plot draws it. It sits
    above the plot, in the plot's colours, and never over it, so it cannot
    hide a patch (Knut, #182 6148467471)."""

    def __init__(self, lines: "list[str]", bg: str, fg: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("colourViewLegend")
        self.setStyleSheet(
            f"QFrame#colourViewLegend {{ background: {bg}; border: none; }}"
            f"QFrame#colourViewLegend QLabel {{ color: {fg}; background: transparent; }}")
        grid = QGridLayout(self)
        grid.setContentsMargins(12, 6, 12, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(3)
        self.samples = []
        self.labels = []
        for row, (kind, text) in enumerate(zip(("skin", "line", "dots"), lines)):
            sample = _LegendSample(kind, bg, fg, self)
            label = QLabel(text, self)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            grid.addWidget(sample, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(label, row, 1)
            self.samples.append(sample)
            self.labels.append(label)
        grid.setColumnStretch(1, 1)


class PatchCubeDialog(QDialog):
    """Modal-ish popup showing the patch set as a rotatable 3D RGB cube.

    ``target_name`` labels the cube (the currently loaded chart). When
    ``compare_presets`` (``[(label, .ti1 path), …]``) is given, a "Compare with
    profile:" dropdown lets the user open a second, camera-synced cube of that
    preset's patches alongside (#66)."""

    def __init__(self, program: list[tuple], *, mode: str = "dark",
                 target_name: str = "",
                 compare_presets: list[tuple[str, Path]] | None = None,
                 numbered: bool = False,
                 lab_cloud: "tuple[list, list] | None" = None,
                 colour_view: "tuple[list, list, object] | None" = None,
                 parent=None) -> None:
        super().__init__(parent)
        # The same patches as COLOURS, through the run's profile, inside the
        # outline of that profile's gamut: (Lab, display colours, outline).
        # Offered beside the RGB cube, never instead of it (Knut, #182
        # 6113365581: a From Profile Gamut chart is spaced evenly as colours,
        # which the ink-amount cube cannot show).
        self._program = list(program)
        self._colour_view = None if lab_cloud else colour_view
        self._view_combo = None
        self._compare_combo = None
        self._numbered = numbered
        self._target_name = target_name or tr("Current chart")
        # Lab mode (#72): a multi-ink chart shown as a true Lab-space scatter
        # (positions via its preconditioning profile). RGB preset comparison
        # doesn't apply there, so the compare combo is dropped.
        self._lab_cloud = lab_cloud
        self._compare_presets = [] if lab_cloud else list(compare_presets or [])
        self.setWindowTitle(
            tr("Patch distribution — Lab space") if lab_cloud
            else tr("Patch distribution — 3D RGB cube"))
        self.resize(*default_dialog_size(
            1040 if self._compare_presets else 820, 760, parent))
        self.setMinimumSize(520, 480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Tab-style masthead (eyebrow + serif title) over a full-width spectrum
        # stripe, matching the chart-design windows; the cube sits beneath it.
        head, _header, stripe = dialog_masthead(
            self, tr("PATCH SET · 3D VIEW"), tr("Patch distribution"),
            top=14, bottom=10,
            tooltip_title=tr("Patch distribution (3D)"),
            tooltip_body=tr(
                "Shows the chart's patches as points in the RGB cube, so you can "
                "see how evenly the colours are spread.\n\n"
                "Move the view to inspect it from any angle:\n"
                "• Mouse — drag to rotate, scroll to zoom, right-drag or "
                "middle-drag (wheel-click) to pan.\n"
                "• Keyboard (click the cube first) — arrow keys rotate, "
                "Shift+arrow keys pan, + / − zoom.\n\n"
                "Pick a preset in “Compare with profile” to open a second cube "
                "beside this one; the two cameras stay locked together, so the "
                "same rotate/zoom/pan moves both and you can compare coverage "
                "from any angle."))
        lay.addLayout(head)
        lay.addWidget(stripe)

        # Target name + (optional) "Compare with profile" dropdown.
        bar = QHBoxLayout()
        bar.setContentsMargins(12, 8, 12, 6)
        bar.setSpacing(8)
        # Post-#70 the profile name no longer describes the chart layout, so the
        # caller passes no name and we show a neutral label rather than implying
        # the profile name is the layout's (Knut, #70 follow-up). A specific name,
        # if ever given, still renders as "Chart: <name>".
        name_text = (tr("Chart: {name}").format(name=target_name) if target_name
                     else self._target_name)
        self._name_lbl = QLabel(name_text, self)
        self._name_lbl.setStyleSheet("font-weight: bold;")
        bar.addWidget(self._name_lbl)
        if self._colour_view is not None or self._compare_presets:
            # This window declares no accent of its own, so its dropdowns
            # wear the one the user is already looking at: dialog_masthead's
            # default magenta, the stroke drawn above, and the colour the
            # patch-set editor that opens the other cube uses. Without this
            # the popup falls through to the global cyan, which belongs to
            # Build Profile and means nothing here.
            self.setStyleSheet(self.styleSheet() + combo_popup_qss(SPEC_MAGENTA))
        if self._colour_view is not None:
            bar.addSpacing(16)
            bar.addWidget(QLabel(tr("Show:"), self))
            self._view_combo = QComboBox(self)
            self._view_combo.addItem(tr("Ink amounts (RGB cube)"), "rgb")
            self._view_combo.addItem(
                tr("Colours through the profile (L*a*b*)"), "lab")
            self._view_combo.setToolTip(_view_help())
            self._view_combo.currentIndexChanged.connect(self._on_view_changed)
            bar.addWidget(self._view_combo)
        bar.addStretch(1)
        if self._compare_presets:
            bar.addWidget(QLabel(tr("Compare with profile:"), self))
            self._compare_combo = QComboBox(self)
            # Cap the popup at 15 rows + scroll. On macOS maxVisibleItems is
            # honoured ONLY when combobox-popup:0 (which replaces the native menu
            # with a scrollable list) — :1 keeps the native menu and shows every
            # row.
            self._compare_combo.setMaxVisibleItems(15)
            self._compare_combo.setStyleSheet("QComboBox { combobox-popup: 0; }")
            self._compare_combo.addItem(tr("None"), None)
            for group, items in self._compare_presets:
                # An empty heading is the user's own presets, which Create
                # Chart lists straight under "none" with no heading and no
                # separator (`preset_dropdown_groups`); so does this list.
                indent = "    " if group else ""
                if group:
                    self._compare_combo.insertSeparator(self._compare_combo.count())
                    self._compare_combo.addItem(group)          # instrument header
                    hdr = self._compare_combo.model().item(self._compare_combo.count() - 1)
                    if hdr is not None:
                        f = hdr.font(); f.setBold(True); hdr.setFont(f)
                        # Bold, but the same colour as the entries (not greyed) — and
                        # still not selectable (Enabled flag kept, Selectable dropped).
                        hdr.setFlags(Qt.ItemFlag.ItemIsEnabled)
                for label, path in items:
                    self._compare_combo.addItem(indent + label, str(path))
            self._compare_combo.currentIndexChanged.connect(self._on_compare_changed)
            bar.addWidget(self._compare_combo)
        lay.addLayout(bar)

        self._panel = PatchCubePanel(mode=mode, numbered=numbered, parent=self)
        self._panel.set_primary_label(self._target_name)
        # The colour view's key (M-HELP-COLOUR-VIEW-LEGEND), above the plot
        # and only while the colour view is shown; none until approved.
        self._legend = None
        legend = _legend_lines() if self._colour_view is not None else None
        if legend:
            th = self._panel._theme
            self._legend = ColourViewLegend(legend, th["bg"], th["fg"], self)
            self._legend.setVisible(False)
            lay.addWidget(self._legend)
        lay.addWidget(self._panel, 1)
        if self._lab_cloud is not None:
            self._panel.set_lab_cloud(*self._lab_cloud)
        else:
            self._panel.set_program(program)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.setContentsMargins(8, 6, 8, 6)
        lay.addWidget(buttons)

    # ------------------------------------------------------------------
    def _on_view_changed(self, _index: int) -> None:
        """Ink amounts (the RGB cube) or colours through the profile."""
        if self._view_combo is None or self._colour_view is None:
            return
        if self._view_combo.currentData() == "lab":
            if self._compare_combo is not None:
                # The comparison is a second RGB cube; it has no colour view.
                self._compare_combo.setCurrentIndex(0)
                self._compare_combo.setEnabled(False)
            from workflow.patch_cube import lab_spacing_summary
            labs, colors, outline = self._colour_view
            self._panel.set_lab_cloud(labs, colors, outline,
                                      stats=lab_spacing_summary(labs))
            self.setWindowTitle(tr("Patch distribution — Lab space"))
            if self._legend is not None:
                self._legend.setVisible(True)
        else:
            if self._legend is not None:
                self._legend.setVisible(False)
            if self._compare_combo is not None:
                self._compare_combo.setEnabled(True)
            self._panel.set_program(self._program)
            self.setWindowTitle(tr("Patch distribution — 3D RGB cube"))

    def _on_compare_changed(self, _index: int) -> None:
        """Open / close the side-by-side comparison cube for the picked preset."""
        path = self._compare_combo.currentData()
        if not path:
            self._panel.clear_compare()
            self._name_lbl.setVisible(True)
            return
        label = self._compare_combo.currentText().strip()   # drop the indent
        from workflow.ti2_relayout import load_rgb_program
        try:
            program_b = load_rgb_program(Path(path))
        except (ValueError, OSError) as exc:
            log.warning("compare preset %s: %s", path, exc)
            program_b = []
        if program_b:
            self._panel.set_compare(program_b, label, self._target_name)
            # Two cubes: each cube now carries its own title, so the bar's
            # name label would just repeat the left cube's — hide it (#77, Knut).
            self._name_lbl.setVisible(False)
        else:
            self._panel.clear_compare()
            self._name_lbl.setVisible(True)

    # ------------------------------------------------------------------
    def exec(self) -> int:  # noqa: A003
        """Build the cube's web view *before* entering the modal loop.

        Instantiating a ``QWebEngineView`` creates a native surface; doing that
        while this dialog already holds the application-modal grab wedges the
        grab on Windows and freezes the app (issue #38 follow-up). So realise
        the dialog non-modally, build the view off the grab, let the surface
        settle, then go modal with the cube already in place."""
        self.show()                      # non-modal: realize the dialog
        self._panel.ensure_view()        # build the web view off the grab
        QApplication.processEvents()     # let the native surface settle
        return super().exec()

    # ------------------------------------------------------------------
    def done(self, result: int) -> None:  # noqa: N802
        # done() is the single chokepoint for both accept() and reject().
        self._panel.teardown()
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._panel.teardown()
        super().closeEvent(event)
