"""Right-side Gamut Volume panel for the Check & Refine tab."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, QTimer, QUrl, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.webengine_shutdown import drain_web_view
from ui import neutral_styles
from ui.fade_scroll import FadeScrollArea
from ui.styles import SPEC_VIOLET, TEXT_DIM
from ui.tooltip_button import InfoDialog, TooltipButton
from ui.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, make_browse_button, open_file_dialog
from workflow.gamut_viewer import GamutViewer, GamutViewerParams
from workflow.viewgam_runner import ViewgamResult, ViewgamRunner
from core.i18n import tr

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)

#: The violet this panel accented with in every appearance. It is now the
#: light/dark entry of :data:`_PALETTES` and nothing reads it directly; kept as
#: a name because it is the value Light and Dark must keep painting.
_ACCENT = SPEC_VIOLET

#: THE PANEL'S OWN COLOURS, PER APPEARANCE.
#:
#: THE 3D GAMUT IS THE USER'S DATA and nothing here reaches it — the shape, its
#: hues and its translucency are produced by ``workflow/gamut_viewer.py`` and
#: are identical in all three appearances. What this table themes is the well
#: the viewer sits in and the panel's own labels, sliders and accents.
#:
#: Neutral's well is ``BG_PANEL``, the panel grey. That is the owner's
#: instruction for the preview well ("the same background colours as the light
#: grey used for the majority of the main window panel") applied to its
#: neighbour: these two wells sit on the same screen, and a gamut in a darker
#: hole beside a preview on the panel would read as two different kinds of
#: place. The 1 px ``BORDER`` edge is what says "well".
#:
#: ``accent`` replaces the module-level violet: a colourless theme has ONE
#: accent value, and a hairline rule in ``ACTION`` is what the handoff asks for
#: here.
_PALETTE_LIGHT = {
    "frame_bg": "#efebe6", "frame_border": "#d0ccc6",
    "hdr": "#7a7570", "profile": "#7a7570", "placeholder": "#7a7570",
    "groove": "#1c1b18", "accent": SPEC_VIOLET,
}
_PALETTE_DARK = {
    "frame_bg": "#111111", "frame_border": "#333",
    "hdr": TEXT_DIM, "profile": "#b8b8b8", "placeholder": TEXT_DIM,
    "groove": "#333333", "accent": SPEC_VIOLET,
}
_PALETTE_NEUTRAL = {
    "frame_bg":     neutral_styles.NM_BG_PANEL,
    "frame_border": neutral_styles.NM_BORDER,
    "hdr":          neutral_styles.NM_TEXT_DIM,
    "profile":      neutral_styles.NM_TEXT_MAIN,
    # Nothing that works is allowed to be faint: the "run gamut analysis" line
    # is tertiary ink at 8.13:1, not a pale grey.
    "placeholder":  neutral_styles.NM_TEXT_FAINT,
    # Rule 1 — nothing is lighter than its ground. The unfilled groove is a
    # step DOWN from the panel; the filled part and the handle are ACTION.
    "groove":       neutral_styles.NM_BORDER,
    "accent":       neutral_styles.NM_ACTION,
}
_PALETTES = {
    "light":   _PALETTE_LIGHT,
    "dark":    _PALETTE_DARK,
    "neutral": _PALETTE_NEUTRAL,
}


class GamutPanel(QWidget):
    """Embedded iccgamut/viewgam runner: 3D viewer + volume + coverage comparison."""

    def __init__(
        self,
        runner:   "ArgyllRunner",
        settings: "AppSettings",
        parent:   QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner   = runner
        self._settings = settings
        from ui.theme import resolve_mode
        self._mode: str = resolve_mode(settings.get("appearance", "auto"))

        # Workflow objects
        self._viewer         = GamutViewer(runner, self)
        self._viewgam_runner = ViewgamRunner(runner, self)

        # State
        self._icc_path:         Path | None = None
        self._compare_path:     Path | None = None
        self._saved_camera:     str = ""      # M1: rotation kept across view switches
        self._primary_volume:   float | None = None
        self._compare_volume:   float | None = None
        self._primary_html:     str | None = None
        self._compare_html:     str | None = None
        self._combined_html:    str | None = None
        self._primary_gam:      str | None = None
        self._compare_gam:      str | None = None
        self._viewgam_result:   ViewgamResult | None = None
        self._pending_compare   = False

        self._viewer.finished.connect(self._on_viewer_finished)
        self._viewer.error.connect(self._on_viewer_error)
        self._viewgam_runner.finished.connect(self._on_viewgam_finished)
        self._viewgam_runner.error.connect(self._on_viewgam_error)

        self._build_ui()
        self._load_defaults()
        # THE HEADER AND THE PROFILE LINE ARE STYLED INLINE WHILE _build_ui
        # RUNS, WITH THE DARK VALUES, and `set_appearance` early-returns when
        # the mode it is handed is the one the panel was born with — so a panel
        # BORN in an appearance never runs `_apply_mode_styles` at all and
        # keeps those dark values for ever. That is why "GAMUT VOLUME" is
        # #8a8a8a and the profile line #b8b8b8 in Light, where the light
        # palette says #7a7570.
        #
        # IT IS A FAULT IN LIGHT TOO, AND IT IS DELIBERATELY LEFT THERE. This
        # change may not move Light or Dark by a pixel — that is proved by
        # hashing every grab in both — and calling this unconditionally moves
        # 633 of them. Fixing Light belongs in a commit that is allowed to.
        # Neutral is new, has no pixels to preserve, and gets its values from
        # the start.
        if self._mode not in ("light", "dark"):
            self._apply_mode_styles()

    # ------------------------------------------------------------------
    def _palette(self) -> dict:
        """This appearance's frame colours. A fourth is a row in _PALETTES."""
        return _PALETTES.get(self._mode, _PALETTE_DARK)

    def _current_bg(self) -> str:
        """Page background that should match the surrounding viewer frame.

        This is the ground the 3D gamut is drawn ON, not part of the gamut: the
        shape, its hues and its opacity are the same in every appearance, and
        the light theme has always handed the page a light ground here.
        """
        return self._palette()["frame_bg"]

    def _slider_stylesheet(self) -> str:
        """QSlider QSS for the opacity / saturation sliders, theme-aware.

        The unfilled groove uses the masthead wordmark colour for the
        current mode (#1c1b18 light "Chrom" / #ffffff dark "Chrom") so
        the dark portion of the track harmonises with the rest of the
        light-mode palette instead of staying at the hardcoded cool
        #333333 that looked out of place against the warm light frame.
        Dark mode falls back to the original #333333 — a white groove
        would clash with the dark surround. Neutral's groove is BORDER
        and its fill and handle are ACTION: one accent, and the track
        never brightens above the panel it is cut into.
        """
        pal = self._palette()
        groove, accent = pal["groove"], pal["accent"]
        return (
            f"QSlider::groove:horizontal {{ height: 4px; background: {groove};"
            " border-radius: 2px; }"
            f"QSlider::handle:horizontal {{ background: {accent}; border: none;"
            " width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }"
            f"QSlider::sub-page:horizontal {{ background: {accent};"
            " border-radius: 2px; }"
        )

    def _value_style(self) -> str:
        """The headline volume figure: the accent, in this appearance."""
        return (f"color: {self._palette()['accent']};"
                " font-family: Menlo, Consolas, 'Courier New', monospace;"
                " font-size: 12px; font-weight: bold;")

    def set_appearance(self, mode: str) -> None:
        """Switch viewer + header colors between dark and light themes."""
        from ui.theme import accept_mode
        new_mode = accept_mode(mode)
        if new_mode == self._mode:
            return
        self._mode = new_mode
        self._apply_mode_styles()

    def _apply_mode_styles(self) -> None:
        pal = self._palette()
        frame_bg         = pal["frame_bg"]
        frame_border     = pal["frame_border"]
        hdr_color        = pal["hdr"]
        profile_color    = pal["profile"]
        placeholder_text = pal["placeholder"]

        viewer_frame = self.findChild(QWidget, "gamutViewerFrame")
        if viewer_frame is not None:
            viewer_frame.setStyleSheet(
                "QWidget#gamutViewerFrame {"
                f" background: {frame_bg};"
                f" border: 1px solid {frame_border};"
                " border-left: none;"
                "}"
            )
        if getattr(self, "_web_view", None) is not None:
            self._web_view.page().setBackgroundColor(QColor(frame_bg))
            # Re-patch the bg in any HTML the runners have already written to
            # disk, so reloading picks up the new theme without re-running the
            # gamut tools.
            from workflow.gamut_viewer import repatch_background
            for html_path in (self._primary_html, self._compare_html, self._combined_html):
                if html_path:
                    repatch_background(Path(html_path), frame_bg)
            # Refresh whichever HTML is loaded so the in-page bg matches.
            current_html = (
                self._combined_html if self._view_combined_btn.isChecked()
                else self._primary_html if self._view_primary_btn.isChecked()
                else self._compare_html if self._view_compare_btn.isChecked()
                else None
            )
            if current_html:
                self._load_html(current_html)
            else:
                self._show_placeholder()
        self._hdr_lbl.setStyleSheet(
            f"color: {hdr_color}; background: transparent; padding: 4px;"
            " font-family: Menlo, Consolas, 'Courier New', monospace;"
            " font-size: 9px; font-weight: 300;"
        )
        self._profile_lbl.setStyleSheet(
            f"color: {profile_color}; background: transparent; padding: 0 8px 0 8px;"
            " font-family: Menlo, Consolas, 'Courier New', monospace;"
            " font-size: 11px;"
        )
        self._placeholder_text_color = placeholder_text
        # Re-tint the opacity / saturation slider grooves to match the
        # new mode's wordmark colour.
        if getattr(self, "_opacity_slider", None) is not None:
            ss = self._slider_stylesheet()
            self._opacity_slider.setStyleSheet(ss)
            self._sat_slider.setStyleSheet(ss)
        # The volume figure carried a module-level violet baked in at build
        # time, so it kept it through every theme switch. It follows the
        # appearance now.
        if getattr(self, "_vol_label", None) is not None:
            self._vol_label.setStyleSheet(self._value_style())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_icc_path(self, path: Path | None) -> None:
        """Called by TabCheckRefine when the active profile changes."""
        self._icc_path = path
        self._primary_edit.setText(str(path) if path else "")
        self._run_btn.setEnabled(path is not None)
        self._reset_results()
        self._update_profile_header()

    def _update_profile_header(self) -> None:
        """Show 'A: <stem>   B: <stem>' under the header, full paths on hover.

        Mirrors TiffPreview's caption+filename pattern. The header→viewer gap
        is hidden when no profile is loaded so the section title hugs the
        viewer like it did before the change.
        """
        primary = self._icc_path
        compare = self._compare_path
        if not primary and not compare:
            self._profile_lbl.clear()
            self._profile_lbl.setVisible(False)
            self._profile_gap.setVisible(False)
            for w in (self._hdr_lbl, self._profile_lbl, self._viewer_widget):
                w.setToolTip("")
                w.unsetCursor()
            return
        parts: list[str] = []
        tooltip_lines: list[str] = []
        if primary:
            parts.append(f"A: {self._elide_middle(primary.stem, 28)}")
            tooltip_lines.append(f"A: {primary}")
        if compare:
            parts.append(f"B: {self._elide_middle(compare.stem, 28)}")
            tooltip_lines.append(f"B: {compare}")
        self._profile_lbl.setText("   ".join(parts))
        tooltip = "\n".join(tooltip_lines)
        for w in (self._hdr_lbl, self._profile_lbl, self._viewer_widget):
            w.setToolTip(tooltip)
        self._hdr_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
        self._profile_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
        self._profile_lbl.setVisible(True)
        self._profile_gap.setVisible(True)

    @staticmethod
    def _elide_middle(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        keep = max_len - 1
        head = keep // 2
        tail = keep - head
        return f"{text[:head]}…{text[-tail:]}"

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Section header — caption + loaded-profile names (auto-updated)
        self._hdr_lbl = QLabel(tr("GAMUT VOLUME"), self)
        self._hdr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hdr_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; background: transparent; padding: 4px;"
            " font-family: Menlo, Consolas, 'Courier New', monospace;"
            " font-size: 9px; font-weight: 300;"
        )
        root.addWidget(self._hdr_lbl)

        self._profile_lbl = QLabel("", self)
        self._profile_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._profile_lbl.setStyleSheet(
            "color: #b8b8b8; background: transparent; padding: 0 8px 0 8px;"
            " font-family: Menlo, Consolas, 'Courier New', monospace;"
            " font-size: 11px;"
        )
        self._profile_lbl.setVisible(False)
        root.addWidget(self._profile_lbl)

        # Gap below the profile row — only shown when a profile is loaded
        self._profile_gap = QWidget(self)
        self._profile_gap.setFixedHeight(12)
        self._profile_gap.setVisible(False)
        root.addWidget(self._profile_gap)

        # 3D viewer
        self._viewer_widget = self._make_viewer_widget()
        self._viewer_widget.setMinimumHeight(280)
        self._viewer_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._viewer_widget, stretch=1)
        root.addSpacing(6)

        # ── View toggle (hidden until combined view is ready) ───────────
        _mode_font = QFont()
        _mode_font.setFamilies(["Menlo", "Consolas", "Courier New", "monospace"])
        _mode_font.setPointSize(9)
        _mode_font.setWeight(QFont.Weight.Bold)

        self._view_toggle_row = QWidget(self)
        toggle_layout = QHBoxLayout(self._view_toggle_row)
        toggle_layout.setContentsMargins(12, 6, 12, 6)
        toggle_layout.setSpacing(8)

        self._view_primary_btn  = QPushButton(tr("PROFILE A"), self._view_toggle_row)
        self._view_combined_btn = QPushButton(tr("COMBINED"),  self._view_toggle_row)
        self._view_compare_btn  = QPushButton(tr("PROFILE B"), self._view_toggle_row)
        for btn in (self._view_primary_btn, self._view_combined_btn, self._view_compare_btn):
            btn.setCheckable(True)
            btn.setObjectName("mode_btn")
            btn.setFont(_mode_font)
            btn.setFixedHeight(30)
        self._view_combined_btn.setChecked(True)

        self._view_primary_btn.clicked.connect(self._on_view_primary)
        self._view_combined_btn.clicked.connect(self._on_view_combined)
        self._view_compare_btn.clicked.connect(self._on_view_compare)

        toggle_layout.addWidget(self._view_primary_btn)
        toggle_layout.addWidget(self._view_combined_btn)
        toggle_layout.addWidget(self._view_compare_btn)

        # ── Per-compare-profile controls (shown only in Combined mode) ──
        self._compare_controls = QWidget(self._view_toggle_row)
        _cl = QHBoxLayout(self._compare_controls)
        _cl.setContentsMargins(0, 10, 0, 0)
        _cl.setSpacing(6)
        _cl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal, self._compare_controls)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(50)
        self._opacity_slider.setFixedWidth(80)
        self._opacity_slider.setStyleSheet(self._slider_stylesheet())
        self._opacity_label = QLabel("50%", self._compare_controls)
        self._opacity_label.setFixedWidth(34)
        self._sat_slider = QSlider(Qt.Orientation.Horizontal, self._compare_controls)
        self._sat_slider.setRange(0, 100)
        self._sat_slider.setValue(100)
        self._sat_slider.setFixedWidth(80)
        self._sat_slider.setStyleSheet(self._slider_stylesheet())
        self._sat_label = QLabel("100%", self._compare_controls)
        self._sat_label.setFixedWidth(34)
        _cl.addWidget(QLabel(tr("Opacity:")))
        _cl.addWidget(self._opacity_slider)
        _cl.addWidget(self._opacity_label)
        _cl.addSpacing(10)
        _cl.addWidget(QLabel(tr("Sat.:")))
        _cl.addWidget(self._sat_slider)
        _cl.addWidget(self._sat_label)
        self._compare_controls.setVisible(False)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self._sat_slider.valueChanged.connect(self._on_saturation_changed)

        toggle_layout.addSpacing(16)
        toggle_layout.addWidget(self._compare_controls)
        toggle_layout.setAlignment(self._compare_controls, Qt.AlignmentFlag.AlignVCenter)
        toggle_layout.addStretch()

        self._view_toggle_row.setVisible(False)
        root.addWidget(self._view_toggle_row)

        # ── Scrollable options area ─────────────────────────────────────
        scroll = FadeScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(12, 10, 12, 8)
        inner_layout.setSpacing(6)

        # ── Volume results ──────────────────────────────────────────────
        vol_grp = QGroupBox(tr("Results"), inner)
        vg = QVBoxLayout(vol_grp)
        vg.setContentsMargins(8, 10, 8, 8)
        vg.setSpacing(3)

        _dim_style  = (f"color: {TEXT_DIM}; font-family: Menlo, Consolas, 'Courier New', monospace;"
                       " font-size: 11px;")
        _bold_style = self._value_style()

        self._vol_label             = QLabel(tr("Volume: —"), vol_grp)
        self._compare_vol_label     = QLabel(tr("Compare: —"), vol_grp)
        self._intersection_label    = QLabel(tr("Intersection: —"), vol_grp)
        self._coverage_ab_label     = QLabel(tr("A covered by B: —"), vol_grp)
        self._coverage_ba_label     = QLabel(tr("B covered by A: —"), vol_grp)

        # WHAT THE NUMBER IS, on the label that shows it. ArgyllCMS's iccgamut
        # prints "Total volume of gamut is %f cubic colorspace units"
        # (xicc/iccgamut.c:602) — a volume in the working colour space, so ΔE³,
        # not millilitres. ChromIQ used to label it "cc", which reads as cubic
        # centimetres: a typical printer gamut then claimed several hundred
        # litres. Found on 2026-08-08 when a translator asked what "cc" meant.
        _unit_tip = tr(
            "The volume of the gamut, in cubic units of the colour space shown "
            "above — ArgyllCMS calls these cubic colorspace units. It is not a "
            "physical volume, and two figures are only comparable when both "
            "were measured in the same space.")
        for _lbl in (self._vol_label, self._compare_vol_label,
                     self._intersection_label):
            _lbl.setToolTip(_unit_tip)
        self._vol_label.setStyleSheet(_bold_style)
        for lbl in (self._compare_vol_label, self._intersection_label,
                    self._coverage_ab_label, self._coverage_ba_label):
            lbl.setStyleSheet(_dim_style)

        vg.addWidget(self._vol_label)
        vg.addWidget(self._compare_vol_label)
        vg.addWidget(self._intersection_label)
        vg.addWidget(self._coverage_ab_label)
        vg.addWidget(self._coverage_ba_label)

        inner_layout.addWidget(vol_grp)

        # ── Profile selectors ───────────────────────────────────────────
        profile_grp = QGroupBox(tr("Profiles"), inner)
        pg = QVBoxLayout(profile_grp)
        pg.setContentsMargins(8, 10, 8, 8)
        pg.setSpacing(8)

        prim_row = QHBoxLayout()
        prim_row.addWidget(QLabel(tr("Profile:"), profile_grp))
        self._primary_edit = QLineEdit(profile_grp)
        self._primary_edit.setObjectName("compact_path")
        self._primary_edit.setReadOnly(True)
        self._primary_edit.setPlaceholderText(tr("Auto-filled from left panel"))
        prim_row.addWidget(self._primary_edit, stretch=1)
        pg.addLayout(prim_row)

        cmp_row = QHBoxLayout()
        cmp_row.setSpacing(4)
        cmp_row.addWidget(QLabel(tr("Compare with:"), profile_grp))
        self._compare_edit = QLineEdit(profile_grp)
        self._compare_edit.setObjectName("compact_path")
        self._compare_edit.setReadOnly(True)
        self._compare_edit.setPlaceholderText(tr("Optional — browse a second ICC/ICM"))
        cmp_row.addWidget(self._compare_edit, stretch=1)
        cmp_browse = make_browse_button(profile_grp, tr("Browse for comparison ICC/ICM"), "folder_check")
        cmp_browse.setObjectName("browse_compact")
        cmp_browse.setIconSize(QSize(14, 14))
        cmp_browse.setFixedHeight(22)
        cmp_browse.clicked.connect(self._on_browse_compare)
        cmp_row.addWidget(cmp_browse)
        cmp_clear = QPushButton("✕", profile_grp)
        cmp_clear.setObjectName("browse_compact")
        cmp_clear.setFixedWidth(28)
        cmp_clear.setFixedHeight(22)
        cmp_clear.setToolTip(tr("Clear comparison profile"))
        cmp_clear.clicked.connect(self._on_clear_compare)
        cmp_row.addWidget(cmp_clear)
        pg.addLayout(cmp_row)

        inner_layout.addWidget(profile_grp)

        # ── iccgamut Options ────────────────────────────────────────────
        opts_grp = QGroupBox(tr("iccgamut Options"), inner)
        og = QVBoxLayout(opts_grp)
        og.setContentsMargins(8, 10, 8, 8)
        og.setSpacing(8)

        intent_row = QHBoxLayout()
        intent_row.addWidget(QLabel(tr("Rendering intent:"), opts_grp))
        self._intent_combo = NoScrollComboBox(opts_grp)
        self._intent_combo.addItem(tr("Absolute colorimetric (default)"), "a")
        self._intent_combo.addItem(tr("Relative colorimetric"), "r")
        self._intent_combo.addItem(tr("Perceptual"), "p")
        self._intent_combo.addItem(tr("Saturation"), "s")
        self._intent_combo.setObjectName("compact_input")
        self._intent_combo.style().unpolish(self._intent_combo)
        self._intent_combo.style().polish(self._intent_combo)
        intent_row.addWidget(self._intent_combo, stretch=1)
        intent_row.addWidget(TooltipButton(
            tr("Rendering Intent"),
            tr("Selects which ICC rendering table iccgamut uses to compute the gamut boundary.\n\n"
            "• Absolute colorimetric (default) — shows the true colorimetric gamut of the\n"
            "  device including its media white point. Best for comparing one profile against\n"
            "  another or against a reference colour space such as sRGB or AdobeRGB.\n\n"
            "• Relative colorimetric — normalises to the media white before computing the gamut.\n"
            "  Shows how much of the colour space the device covers relative to white, which\n"
            "  reflects how colours are reproduced in a standard print workflow.\n\n"
            "• Perceptual — uses the perceptual rendering table. The gamut may appear smaller or\n"
            "  differently shaped because this table compresses or re-maps colours to avoid hard\n"
            "  clipping at the gamut boundary.\n\n"
            "• Saturation — uses the saturation rendering table, which prioritises vivid colours\n"
            "  over colorimetric accuracy.\n\n"
            "For most ICC profile analysis, use Absolute colorimetric."),
            opts_grp,
            min_width=520,
        ))
        og.addLayout(intent_row)

        pcs_row = QHBoxLayout()
        pcs_row.addWidget(QLabel(tr("Colour space:"), opts_grp))
        self._pcs_combo = NoScrollComboBox(opts_grp)
        self._pcs_combo.addItem(tr("Lab (default)"), "l")
        self._pcs_combo.addItem(tr("CIECAM02 Jab"), "j")
        self._pcs_combo.setObjectName("compact_input")
        self._pcs_combo.style().unpolish(self._pcs_combo)
        self._pcs_combo.style().polish(self._pcs_combo)
        pcs_row.addWidget(self._pcs_combo, stretch=1)
        pcs_row.addWidget(TooltipButton(
            tr("Profile Connection Space"),
            tr("Controls which colour space the gamut volume is computed and displayed in.\n\n"
            "• Lab (default) — CIELAB D50, the standard ICC profile connection space. The three\n"
            "  axes represent L* (lightness, 0–100), a* (green↔red), and b* (blue↔yellow).\n"
            "  Easy to interpret and the correct choice for comparing ICC profiles.\n\n"
            "• CIECAM02 Jab — uses a modern perceptual appearance model that accounts for\n"
            "  chromatic adaptation and luminance-level effects. More perceptually uniform across\n"
            "  lightness levels, but harder to interpret directly and slower to compute.\n\n"
            "For everyday profile analysis, Lab is the right choice."),
            opts_grp,
            min_width=500,
        ))
        og.addLayout(pcs_row)

        sres_row = QHBoxLayout()
        sres_row.addWidget(QLabel(tr("Surface resolution:"), opts_grp))
        self._sres_spin = NoScrollDoubleSpinBox(opts_grp)
        self._sres_spin.setRange(1.0, 50.0)
        self._sres_spin.setSingleStep(1.0)
        self._sres_spin.setDecimals(0)
        self._sres_spin.setValue(20.0)
        self._sres_spin.setFixedWidth(70)
        self._sres_spin.setObjectName("compact_input")
        self._sres_spin.style().unpolish(self._sres_spin)
        self._sres_spin.style().polish(self._sres_spin)
        sres_row.addWidget(self._sres_spin)
        sres_row.addStretch()
        sres_row.addWidget(TooltipButton(
            tr("Surface Resolution"),
            tr("Controls how densely iccgamut samples the gamut surface (range 1–50).\n\n"
            "A higher value produces a finer mesh — the 3D shape looks smoother and more\n"
            "accurate, but takes longer to compute.\n\n"
            "   5–10   fast, coarse — good for quick checks\n"
            "  15–25   balanced, suitable for most work  (default: 20)\n"
            "  30–50   very fine and detailed — slow\n\n"
            "If the gamut surface appears jagged or has visible holes, increase this value."),
            opts_grp,
            min_width=460,
        ))
        og.addLayout(sres_row)

        func_row = QHBoxLayout()
        func_row.addWidget(QLabel(tr("Mapping:"), opts_grp))
        self._function_combo = NoScrollComboBox(opts_grp)
        self._function_combo.addItem(tr("Forward — output gamut (default)"), "f")
        self._function_combo.addItem(tr("Backward — input gamut"), "b")
        self._function_combo.setObjectName("compact_input")
        self._function_combo.style().unpolish(self._function_combo)
        self._function_combo.style().polish(self._function_combo)
        func_row.addWidget(self._function_combo, stretch=1)
        func_row.addWidget(TooltipButton(
            tr("Mapping Direction"),
            tr("Controls which direction iccgamut traverses the ICC profile tables.\n\n"
            "• Forward — output gamut (default): maps device values (e.g. RGB ink percentages)\n"
            "  through the profile to Lab and builds the gamut from the resulting Lab points.\n"
            "  This shows every Lab colour the device can physically reproduce.\n\n"
            "• Backward — input gamut: maps Lab values back through the profile to device values.\n"
            "  Shows which Lab colours can be addressed by the profile's lookup tables — this\n"
            "  can differ from the forward gamut due to LUT quantisation or non-invertibility.\n\n"
            "Use Forward for almost all profiling work. Backward is mainly useful for diagnosing\n"
            "profile inversion quality or gamut mapping behaviour."),
            opts_grp,
            min_width=520,
        ))
        og.addLayout(func_row)

        self._axes_cb  = QCheckBox(tr("Show axes && white/black point"), opts_grp)
        self._cusps_cb = QCheckBox(tr("Mark cusp points"), opts_grp)
        self._edges_cb = QCheckBox(tr("Show edge plot"), opts_grp)
        self._axes_cb.setChecked(True)

        _cb_rows = [
            (self._axes_cb, TooltipButton(
                tr("Lab Axes & Reference Points"),
                tr("Draws the CIELAB coordinate axes and two reference points inside the 3D viewer.\n\n"
                "The axes show the direction of each colour dimension:\n"
                "  • L* axis (vertical) — lightness, from black at the bottom to white at the top\n"
                "  • a* axis — green (−a*) toward red/magenta (+a*)\n"
                "  • b* axis — blue/violet (−b*) toward yellow/amber (+b*)\n\n"
                "Two small spheres mark the white point (lightest reproducible colour) and the\n"
                "black point (darkest reproducible colour) of the profile.\n\n"
                "Keeping this enabled makes it much easier to read and orient the 3D gamut model."),
                opts_grp,
                min_width=460,
            )),
            (self._cusps_cb, TooltipButton(
                tr("Mark Cusp Points"),
                tr("Marks the primary and secondary colour cusp points on the gamut surface\n"
                "(iccgamut -k flag).\n\n"
                "Cusps are the most saturated colours in each of the six main hue directions:\n"
                "red, yellow, green, cyan, blue, and magenta. On a printer profile these represent\n"
                "the extremes of what the ink set can achieve.\n\n"
                "Marking them helps you:\n"
                "  • See at a glance how far the gamut extends in each hue direction\n"
                "  • Compare the saturation envelope of one profile against another\n"
                "  • Spot compression or irregularities in specific hue regions"),
                opts_grp,
                min_width=460,
            )),
            (self._edges_cb, TooltipButton(
                tr("Show Edge Plot"),
                tr("Overlays the triangle edges of the gamut mesh on the 3D model\n"
                "(iccgamut -e flag).\n\n"
                "Instead of only showing the solid shaded surface, this draws lines along every\n"
                "triangle edge, giving a wireframe-like appearance that can reveal:\n"
                "  • The resolution and density of the underlying mesh\n"
                "  • Sharp corners or unusual topology in the gamut shape\n"
                "  • Areas where the boundary has been smoothed or interpolated\n\n"
                "Most useful at higher surface resolution values where the mesh structure\n"
                "is meaningful."),
                opts_grp,
                min_width=460,
            )),
        ]
        for cb, tip in _cb_rows:
            _row = QHBoxLayout()
            _row.addWidget(cb)
            _row.addStretch()
            _row.addWidget(tip)
            og.addLayout(_row)

        inner_layout.addWidget(opts_grp)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # ── Buttons (outside scroll — always visible at the bottom) ─────
        btn_row = QHBoxLayout()
        # Bottom margin 15, not 12, so these buttons end 13 px above the window
        # edge — level with Check & Refine's left panel and with every log in
        # the app (Basti, measured with the real styling: here it was 10). The
        # two rows carry the same 12 px margin in source and still differ,
        # because a QSS min-height renders these 36 px buttons at 42 and the
        # overflow eats into the margin by a different amount in each layout.
        # Measure the result, never the margin.
        btn_row.setContentsMargins(12, 6, 12, 15)
        self._run_btn = QPushButton(tr("Run Gamut Analysis"), self)
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedHeight(36)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run)
        self._reset_view_btn = QPushButton(tr("Reset View"), self)
        self._reset_view_btn.setFixedHeight(36)
        self._reset_view_btn.clicked.connect(self._on_reset_view)
        self._save_btn = QPushButton(tr("Save as Defaults"), self)
        self._save_btn.setFixedHeight(36)
        self._save_btn.clicked.connect(self._on_save_defaults)
        btn_row.addWidget(self._run_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(self._reset_view_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

    def _make_viewer_widget(self) -> QWidget:
        # The QWebEngineView's Chromium surface paints over the widget's own
        # stylesheet border, so the border must live on a wrapper QWidget. The
        # wrapper draws the border via an objectName-scoped stylesheet and uses
        # contentsMargins to inset the view by the border thickness on the
        # three bordered sides (top/right/bottom).
        container = QWidget(self)
        container.setObjectName("gamutViewerFrame")
        # Initial styling — _apply_mode_styles() can rewrite this on theme
        # switch. Kept here so the very first paint isn't bare.
        _init_bg = self._current_bg()
        _init_border = self._palette()["frame_border"]
        container.setStyleSheet(
            "QWidget#gamutViewerFrame {"
            f" background: {_init_bg};"
            f" border: 1px solid {_init_border};"
            " border-left: none;"
            "}"
        )
        wrap_layout = QVBoxLayout(container)
        wrap_layout.setContentsMargins(1, 1, 1, 1)
        wrap_layout.setSpacing(0)
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            view = QWebEngineView(container)
            # Set the Chromium page surface colour BEFORE any content loads —
            # otherwise the first compositor frame on first tab open paints at
            # the default white, flashing through before the placeholder HTML
            # renders.
            view.page().setBackgroundColor(QColor(_init_bg))
            try:
                from PyQt6.QtWebEngineCore import QWebEngineSettings
                view.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
                )
            except (ImportError, AttributeError):
                pass
            view.loadFinished.connect(self._on_page_loaded)
            self._web_view = view
            wrap_layout.addWidget(view)
            self._show_placeholder()
            return container
        except ImportError:
            log.warning("PyQt6-WebEngine not available — using fallback placeholder")
            self._web_view = None
            lbl = QLabel(
                tr("Install PyQt6-WebEngine to view\nthe interactive 3D gamut"),
                container,
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _fallback_color = self._palette()["placeholder"]
            lbl.setStyleSheet(
                f"color: {_fallback_color}; background: {_init_bg};"
                " font-family: Menlo, Consolas, 'Courier New', monospace; font-size: 10px;"
            )
            wrap_layout.addWidget(lbl)
            return container

    def _show_placeholder(self) -> None:
        if self._web_view is None:
            return
        bg = self._palette()["frame_bg"]
        fg = getattr(self, "_placeholder_text_color", self._palette()["placeholder"])
        html = (
            f"<html><body style='background:{bg}; margin:0; display:flex;"
            " align-items:center; justify-content:center; height:100vh;'>"
            f"<p style='color:{fg}; font-family:Menlo, Consolas, \"Courier New\", monospace; font-size:12px;"
            " text-align:center;'>"
            + tr("Run gamut analysis<br>to view the 3D gamut") +
            "</p>"
            "</body></html>"
        )
        self._web_view.setHtml(html)

    def _load_html(self, html_path: str) -> None:
        if self._web_view is None or not html_path:
            return
        self._web_view.setUrl(QUrl.fromLocalFile(html_path))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset_results(self) -> None:
        self._primary_volume  = None
        self._compare_volume  = None
        self._primary_html    = None
        self._compare_html    = None
        self._combined_html   = None
        self._primary_gam     = None
        self._compare_gam     = None
        self._viewgam_result  = None
        self._view_toggle_row.setVisible(False)
        self._update_volume_labels()

    def _set_toggle_checked(self, active: QPushButton) -> None:
        for btn in (self._view_primary_btn, self._view_combined_btn, self._view_compare_btn):
            btn.setChecked(btn is active)

    # ------------------------------------------------------------------
    # Slots — view toggle
    # ------------------------------------------------------------------

    # --- M1 (mavtop): keep the 3-D rotation when switching PROFILE A / B /
    # COMBINED. Each view is a separate scene that gets reloaded, which reset the
    # x3dom camera. We capture the camera's transform BEFORE the switch and
    # restore it once the new scene has loaded (_on_page_loaded), so the shape
    # stays where the user rotated it. Uses this bundled x3dom build's viewarea
    # matrices; every access is guarded so a failure only skips the restore.
    _CAPTURE_CAMERA_JS = (
        "(function(){try{var x=document.querySelector('x3d');"
        "var va=x.runtime.canvas.doc._viewarea;"
        "return JSON.stringify({t:va._transMat.toGL(),r:va._rotMat.toGL()});}"
        "catch(e){return '';}})()")

    def _switch_view(self, btn, html: str, *, show_compare: bool) -> None:
        def _after_capture(res) -> None:
            if isinstance(res, str) and res:
                self._saved_camera = res
            self._set_toggle_checked(btn)
            self._compare_controls.setVisible(show_compare)
            self._load_html(html or "")
        if self._web_view is not None:
            self._web_view.page().runJavaScript(self._CAPTURE_CAMERA_JS,
                                                _after_capture)
        else:
            _after_capture("")

    def _restore_camera(self) -> None:
        cam = getattr(self, "_saved_camera", "")
        if not cam or self._web_view is None:
            return
        # x3dom builds its scene asynchronously AFTER the page 'load' event, so
        # try immediately and, if the viewarea isn't up yet, retry twice.
        # x3dom 1.6.3 has no SFMatrix4f.fromGL; rebuild from the toGL() array
        # (column-major) via the 16-arg constructor (row-major) — hence the
        # transpose indexing g[0],g[4],g[8],g[12], …
        self._web_view.page().runJavaScript(
            "(function(){var c=" + cam + ";"
            "function mk(g){return new x3dom.fields.SFMatrix4f("
            "g[0],g[4],g[8],g[12],g[1],g[5],g[9],g[13],"
            "g[2],g[6],g[10],g[14],g[3],g[7],g[11],g[15]);}"
            "function apply(){try{var x=document.querySelector('x3d');"
            "var va=x.runtime.canvas.doc._viewarea;"
            "va._transMat=mk(c.t);va._rotMat=mk(c.r);"
            "x.runtime.canvas.doc.needRender=true;return true;}catch(e){return false;}}"
            "if(!apply()){setTimeout(apply,150);setTimeout(apply,400);}})()")

    def _on_view_primary(self) -> None:
        self._switch_view(self._view_primary_btn, self._primary_html or "",
                          show_compare=False)

    def _on_view_combined(self) -> None:
        self._switch_view(self._view_combined_btn, self._combined_html or "",
                          show_compare=True)

    def _on_view_compare(self) -> None:
        self._switch_view(self._view_compare_btn, self._compare_html or "",
                          show_compare=False)

    def _on_page_loaded(self, ok: bool) -> None:
        if not ok or self._web_view is None:
            return
        # M1: put the rotation back after the scene reloads (all three views).
        self._restore_camera()
        if not self._view_combined_btn.isChecked():
            return
        t = 1.0 - self._opacity_slider.value() / 100.0
        s = self._sat_slider.value() / 100.0
        # M2 (mavtop): switching to A/B and back to Combined RELOADS the scene,
        # which re-initialises at its default opacity/saturation while the Qt
        # sliders keep their values — so the view looked wrong until a slider was
        # nudged. Re-APPLY the current values here (not just set the vars), exactly
        # as _on_opacity_changed / _on_saturation_changed do.
        self._web_view.page().runJavaScript(
            f"window._chromiqCompareOpacity={t:.2f};"
            f" window._chromiqCompareSat={s:.2f};"
            " if(window._chromiqApplyCompare) window._chromiqApplyCompare();"
        )

    def _on_opacity_changed(self, value: int) -> None:
        self._opacity_label.setText(tr("{value}%").format(value=value))
        if self._web_view is None or not self._view_combined_btn.isChecked():
            return
        t = 1.0 - value / 100.0
        self._web_view.page().runJavaScript(
            f"window._chromiqCompareOpacity={t:.2f};"
            " if(window._chromiqApplyCompare) window._chromiqApplyCompare();"
        )

    def _on_saturation_changed(self, value: int) -> None:
        self._sat_label.setText(tr("{value}%").format(value=value))
        if self._web_view is None or not self._view_combined_btn.isChecked():
            return
        s = value / 100.0
        self._web_view.page().runJavaScript(
            f"window._chromiqCompareSat={s:.2f};"
            " if(window._chromiqApplyCompare) window._chromiqApplyCompare();"
        )

    # ------------------------------------------------------------------
    # Slots — file browse
    # ------------------------------------------------------------------

    def _on_browse_compare(self) -> None:
        argyll_bin = self._settings.get("argyll_bin_path", "")
        argyll_ref = ""
        if argyll_bin:
            candidate = Path(argyll_bin).parent / "ref"
            if candidate.exists():
                argyll_ref = str(candidate)

        sidebar = _system_icc_paths()
        if argyll_ref:
            sidebar.insert(0, argyll_ref)

        path = open_file_dialog(
            self,
            "Select comparison ICC/ICM profile",
            "ICC profiles (*.icc *.icm);;All files (*)",
            start_dir=argyll_ref or (sidebar[0] if sidebar else ""),
            extra_paths=sidebar,
        )
        if path:
            self._compare_path = Path(path)
            self._compare_edit.setText(path)
            self._compare_volume = None
            self._update_volume_labels()
            self._update_profile_header()

    def _on_clear_compare(self) -> None:
        self._compare_path = None
        self._compare_edit.clear()
        self._compare_volume = None
        self._combined_html = None
        self._compare_html  = None
        self._compare_gam   = None
        self._viewgam_result = None
        self._view_toggle_row.setVisible(False)
        self._update_volume_labels()
        self._update_profile_header()

    # ------------------------------------------------------------------
    # Slots — analysis workflow
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        if self._icc_path is None:
            return
        self._run_btn.setEnabled(False)
        self._reset_results()
        self._pending_compare = self._compare_path is not None
        self._run_primary()

    def _run_primary(self) -> None:
        params  = self._collect_params(self._icc_path)
        themed  = bool(self._settings.get("gamut_themed_colors", True))
        self._viewer.run(params, on_line=lambda _: None, on_finish=lambda _: None,
                         themed=themed, bg=self._current_bg())

    def _run_compare(self) -> None:
        if self._compare_path is None:
            return
        themed = bool(self._settings.get("gamut_themed_colors", True))
        params = self._collect_params(self._compare_path)
        sub = GamutViewer(self._runner, self)
        sub.finished.connect(self._on_compare_finished)
        sub.error.connect(self._on_compare_error)
        sub.run(params, on_line=lambda _: None, on_finish=lambda _: None,
                themed=themed, bg=self._current_bg())

    def _run_viewgam(self) -> None:
        if not self._primary_gam or not self._compare_gam:
            return
        themed = bool(self._settings.get("gamut_themed_colors", True))
        self._viewgam_runner.run(
            primary_gam  = Path(self._primary_gam),
            compare_gam  = Path(self._compare_gam),
            primary_html = Path(self._primary_html) if self._primary_html else None,
            compare_html = Path(self._compare_html) if self._compare_html else None,
            on_line      = lambda _: None,
            on_finish    = lambda _: None,
            themed       = themed,
            bg           = self._current_bg(),
        )

    def _on_viewer_finished(self, volume: float, html_path: str, gam_path: str) -> None:
        self._primary_volume = volume
        self._primary_html   = html_path
        self._primary_gam    = gam_path
        if html_path:
            self._load_html(html_path)
        self._update_volume_labels()
        if self._pending_compare and self._compare_path is not None:
            self._pending_compare = False
            # Defer so ArgyllRunner's QProcess is fully torn down before next run
            QTimer.singleShot(0, self._run_compare)
        else:
            self._pending_compare = False
            self._run_btn.setEnabled(self._icc_path is not None)

    def _on_compare_finished(self, volume: float, html_path: str, gam_path: str) -> None:
        self._compare_volume = volume
        self._compare_html   = html_path
        self._compare_gam    = gam_path
        self._update_volume_labels()
        if self._primary_gam and self._compare_gam:
            self._run_viewgam()
        else:
            self._run_btn.setEnabled(self._icc_path is not None)

    def _on_viewgam_finished(self, result: ViewgamResult) -> None:
        self._combined_html  = result.html_path
        self._viewgam_result = result
        self._update_volume_labels()
        if result.html_path:
            self._load_html(result.html_path)
            self._view_toggle_row.setVisible(True)
            self._compare_controls.setVisible(True)
            self._set_toggle_checked(self._view_combined_btn)
        self._run_btn.setEnabled(self._icc_path is not None)

    def _on_viewgam_error(self, msg: str) -> None:
        log.warning("viewgam: %s", msg)
        self._run_btn.setEnabled(self._icc_path is not None)

    def _on_compare_error(self, msg: str) -> None:
        log.warning("compare iccgamut: %s", msg)
        self._run_btn.setEnabled(self._icc_path is not None)
        self._show_gamut_error_dialog(msg)

    def _on_viewer_error(self, msg: str) -> None:
        self._run_btn.setEnabled(self._icc_path is not None)
        self._pending_compare = False
        log.warning("GamutViewer error: %s", msg)
        self._show_gamut_error_dialog(msg)

    def _show_gamut_error_dialog(self, msg: str) -> None:
        if msg.startswith("empty:"):
            path = msg[len("empty:"):]
            body = (
                f"The ICC profile file could not be analysed because it is empty (0 bytes):\n\n"
                f"{path}\n\n"
                "Why this happens:\n"
                "An empty ICC profile is usually left behind when a profiling run was\n"
                "interrupted, aborted, or failed before colprof could finish writing the\n"
                "output file. The file exists on disk but contains no data.\n\n"
                "What to do:\n"
                "• Go to the Build Profile tab and run the profiling workflow again for\n"
                "  this printer/paper combination to generate a valid ICC profile.\n"
                "• If the file was created by a different application, re-export or\n"
                "  re-create it from your profiling software."
            )
            InfoDialog("Gamut Analysis Failed — Empty Profile File", body, self, min_width=520).exec()
        elif msg.startswith("tool_error:"):
            details = msg[len("tool_error:"):]
            body = (
                "iccgamut was not able to analyse the ICC profile and exited with an error.\n\n"
                f"Technical detail:\n{details}\n\n"
                "Common causes:\n"
                "• The ICC profile file is corrupt or was not written correctly.\n"
                "• The profile was created by an application using a non-standard ICC\n"
                "  structure that this version of Argyll cannot parse.\n"
                "• The file was modified or truncated after it was created.\n\n"
                "What to do:\n"
                "• Try rebuilding the profile via the Build Profile tab.\n"
                "• If the file came from a different application, check whether it opens\n"
                "  correctly in ColorSync Utility (macOS) or ICC Profile Inspector.\n"
                "• Check the log file at ~/Library/Logs/ChromIQ/chromiq.log for the\n"
                "  full iccgamut output."
            )
            InfoDialog("Gamut Analysis Failed", body, self, min_width=540).exec()
        elif "Another process is already running" not in msg:
            InfoDialog(
                "Gamut Analysis Failed",
                f"The gamut analysis could not complete:\n\n{msg}",
                self,
                min_width=480,
            ).exec()

    def shutdown_webengine(self) -> None:
        # PyQt6 + QtWebEngine shutdown race: if the view (and its Chromium
        # child objects) is still alive when the interpreter finalises, SIP
        # walks the wrapper graph and follows a dangling pointer into the
        # Chromium subtree — EXC_BAD_ACCESS. Called from MainWindow.closeEvent
        # so the event loop is still running; drain_web_view destroys the view
        # synchronously there (deleteLater would never flush — see #38 and
        # core.webengine_shutdown).
        drain_web_view(self._web_view)
        self._web_view = None
        # …and the pages themselves. AFTER the drain: the X3D page resolves
        # x3dom.js relatively out of its own folder, so removing it while a
        # view still lived would blank the scene. Nothing removed these before
        # and there is no production sweeper — main.py exits via os._exit().
        self._drop_html_temp_dirs()

    def _drop_html_temp_dirs(self) -> None:
        import shutil
        from pathlib import Path as _P

        for attr in ("_primary_html", "_compare_html", "_combined_html"):
            path = getattr(self, attr, None)
            if not path:
                continue
            try:
                shutil.rmtree(_P(path).parent, ignore_errors=True)
            except Exception:      # noqa: BLE001 — shutdown must not raise
                pass
            setattr(self, attr, None)

    def _on_reset_view(self) -> None:
        if self._web_view is not None:
            self._web_view.page().runJavaScript(
                "var x = document.querySelector('x3d');"
                " if (x && x.runtime) x.runtime.resetView();"
            )

    def _update_volume_labels(self) -> None:
        if self._primary_volume is not None:
            self._vol_label.setText(tr("Volume: {v:,.0f} units³").format(v=self._primary_volume))
        else:
            self._vol_label.setText(tr("Volume: —"))

        if self._compare_volume is not None and self._primary_volume is not None:
            delta = (self._compare_volume - self._primary_volume) / self._primary_volume * 100
            sign  = "+" if delta >= 0 else ""
            self._compare_vol_label.setText(
                tr("Compare: {v:,.0f} units³  (Δ {sign}{delta:.1f}%)").format(
                    v=self._compare_volume, sign=sign, delta=delta)
            )
        elif self._compare_volume is not None:
            self._compare_vol_label.setText(tr("Compare: {v:,.0f} units³").format(v=self._compare_volume))
        else:
            self._compare_vol_label.setText(tr("Compare: —"))

        r = self._viewgam_result
        if r and r.intersection_volume is not None:
            self._intersection_label.setText(tr("Intersection: {v:,.0f} units³").format(v=r.intersection_volume))
            self._coverage_ab_label.setText(
                tr("A covered by B: {pct:.1f}%").format(pct=r.primary_coverage_pct)
                if r.primary_coverage_pct is not None else tr("A covered by B: —")
            )
            self._coverage_ba_label.setText(
                tr("B covered by A: {pct:.1f}%").format(pct=r.compare_coverage_pct)
                if r.compare_coverage_pct is not None else tr("B covered by A: —")
            )
        else:
            self._intersection_label.setText(tr("Intersection: —"))
            self._coverage_ab_label.setText(tr("A covered by B: —"))
            self._coverage_ba_label.setText(tr("B covered by A: —"))

    def _collect_params(self, icc_path: Path) -> GamutViewerParams:
        return GamutViewerParams(
            icc_path = icc_path,
            intent   = self._intent_combo.currentData(),
            pcs      = self._pcs_combo.currentData(),
            sres     = self._sres_spin.value(),
            axes     = self._axes_cb.isChecked(),
            cusps    = self._cusps_cb.isChecked(),
            edges    = self._edges_cb.isChecked(),
            function = self._function_combo.currentData(),
        )

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _load_defaults(self) -> None:
        s = self._settings
        _set_combo(self._intent_combo, s.get("gamut_intent", "a"))
        _set_combo(self._pcs_combo, s.get("gamut_pcs", "l"))
        _set_combo(self._function_combo, s.get("gamut_function", "f"))
        self._sres_spin.setValue(float(s.get("gamut_sres", 20.0)))
        self._axes_cb.setChecked(bool(s.get("gamut_axes", True)))
        self._cusps_cb.setChecked(bool(s.get("gamut_cusps", False)))
        self._edges_cb.setChecked(bool(s.get("gamut_edges", False)))
        self._opacity_slider.setValue(int(s.get("gamut_compare_opacity", 50)))
        self._sat_slider.setValue(int(s.get("gamut_compare_sat", 100)))

    def _on_save_defaults(self) -> None:
        s = self._settings
        s.set("gamut_intent",    self._intent_combo.currentData())
        s.set("gamut_pcs",       self._pcs_combo.currentData())
        s.set("gamut_function",  self._function_combo.currentData())
        s.set("gamut_sres",      self._sres_spin.value())
        s.set("gamut_axes",      self._axes_cb.isChecked())
        s.set("gamut_cusps",     self._cusps_cb.isChecked())
        s.set("gamut_edges",     self._edges_cb.isChecked())
        s.set("gamut_compare_opacity", self._opacity_slider.value())
        s.set("gamut_compare_sat",     self._sat_slider.value())


# ---------------------------------------------------------------------------

def _set_combo(combo: NoScrollComboBox, value: str) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return


def _system_icc_paths() -> list[str]:
    """Return existing platform-specific ICC/ICM profile directories."""
    from core.platform_paths import icc_system_dirs
    seen: set[str] = set()
    result: list[str] = []
    for p in (str(d) for d in icc_system_dirs()):
        if p not in seen and Path(p).exists():
            seen.add(p)
            result.append(p)
    return result
