"""Soft-proof / Check image — Tools ▸ "Soft-proof / check an image".

Loads an image and a printer ICC profile and answers one question two ways:

  * **Preview** — an approximate on-screen soft-proof (how the image will look
    printed), with out-of-gamut colours optionally highlighted.
  * **Gamut fit** — the image's colour gamut overlaid on the printer's gamut in
    the 3D viewer, so you can see *which* colours fall outside.

plus a headline **% out of gamut** metric. The soft-proof + out-of-gamut math
lives in :mod:`workflow.softproof_runner`; the 3D overlay reuses
:class:`workflow.gamut_viewer.GamutViewer`, :class:`workflow.tiffgamut_runner`
and :class:`workflow.viewgam_runner.ViewgamRunner`.

ArgyllCMS only reads ICC **v2**, so the printer profile is checked with
:func:`workflow.icc_info.is_v4` up front and the run is blocked (with a pointer
to the Profile info tool) for v4 profiles. The 3D viewer is torn down via
:func:`core.webengine_shutdown.drain_web_view` on close (issue #38), generated
lazily and only from a downsampled image, so it can neither crash nor hang.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.logger import get_logger
from core.platform_paths import detect_display_profile, icc_system_dirs
from core.webengine_shutdown import drain_web_view
from ui import neutral_styles
from ui.dialog_sizing import pin_min_height
from ui.dialogs.tools_dialogs import neutral_controls_qss
from ui.styles import SPEC_AMBER, SPEC_VIOLET, TEXT_DIM, TEXT_MAIN
from ui.tab_header import dialog_masthead
from ui.theme import resolve_mode
from ui.tiff_preview import TiffPreview
from ui.tooltip_button import InfoDialog, TooltipButton
from ui.widgets import (
    NoScrollComboBox, NoScrollDoubleSpinBox, make_browse_button, open_file_dialog,
    save_file_dialog, tint_dialog_primary,
)
from workflow.icc_info import is_v4
from workflow.softproof_runner import (
    SoftproofParams, SoftproofResult, SoftproofRunner, prepare_input_tiff,
    resolve_source_profile,
)

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)

#: The violet this window has always been themed in. Kept as a name because it
#: is the value Light and Dark must keep painting — read :data:`_PALETTES`.
_ACCENT = SPEC_VIOLET

#: THIS WINDOW'S OWN COLOURS, PER APPEARANCE.
#:
#: THE PROOF IS THE USER'S IMAGE and the 3D gamut is the user's data; neither
#: is touched here. What this themes is the frame: the well both of them are
#: shown in, the option labels, the metric, the toggle and the v4 banner.
#:
#: Neutral's well is ``BG_PANEL``, matching the TIFF preview this dialog embeds
#: — it *is* a ``TiffPreview``, and a well that disagreed with itself between
#: the tab and the tool would be the same picture in two different places.
#:
#: ``accent`` is the handoff's single ``ACTION`` value: a colourless theme has
#: one accent, and "this window is violet-themed throughout" is a statement
#: about the other two appearances.
_PALETTE_LIGHT = {
    "bg": "#efebe6", "border": "#d0ccc6", "placeholder": "#7a7570",
    "toggle_bg": "#ffffff", "toggle_fg": "#1c1b18", "toggle_bd": "#cfcac3",
    "on_accent": "white", "groove": "#555", "dim": TEXT_DIM,
    "warn_bg": "rgba(255,180,45,0.12)", "warn_fg": SPEC_AMBER,
    "warn_bd": SPEC_AMBER, "accent": SPEC_VIOLET,
}
_PALETTE_DARK = {
    "bg": "#111111", "border": "#333", "placeholder": TEXT_DIM,
    "toggle_bg": "#2a2a28", "toggle_fg": "#d0d0d0", "toggle_bd": "#454340",
    "on_accent": "white", "groove": "#555", "dim": TEXT_DIM,
    "warn_bg": "rgba(255,180,45,0.12)", "warn_fg": SPEC_AMBER,
    "warn_bd": SPEC_AMBER, "accent": SPEC_VIOLET,
}
_PALETTE_NEUTRAL = {
    "bg":     neutral_styles.NM_BG_PANEL,
    "border": neutral_styles.NM_BORDER,
    # Nothing that works is faint: the empty-well line is tertiary ink.
    "placeholder": neutral_styles.NM_TEXT_FAINT,
    # An unchecked toggle is an enabled control, so it keeps a fill and a solid
    # edge; the checked one is an ACTION fill with ON_ACTION on it — the one
    # sanctioned light-on-dark pairing, and it is a fill.
    "toggle_bg": neutral_styles.NM_BG_SURFACE,
    "toggle_fg": neutral_styles.NM_TEXT_MAIN,
    "toggle_bd": neutral_styles.NM_BORDER,
    "on_accent": neutral_styles.NM_ON_ACTION,
    # Rule 1 — the unfilled groove is a step DOWN from the panel, never up.
    "groove": neutral_styles.NM_BORDER,
    "dim":    neutral_styles.NM_TEXT_DIM,
    # The v4 banner loses the amber wash and takes the handoff's warning
    # treatment: the raised surface, a solid edge, dark ink.
    "warn_bg": neutral_styles.NM_BG_SURFACE,
    "warn_fg": neutral_styles.NM_TEXT_MAIN,
    "warn_bd": neutral_styles.NM_BORDER_HI,
    "accent":  neutral_styles.NM_ACTION,
}
_PALETTES = {
    "light":   _PALETTE_LIGHT,
    "dark":    _PALETTE_DARK,
    "neutral": _PALETTE_NEUTRAL,
}

_HELP = tr(
    "This tool gives you a rough on-screen preview of how a photo will look once "
    "it's printed on a particular printer and paper — a “soft-proof” — so you can "
    "spot trouble before you commit ink and paper to it.\n\n"
    "It's simple to use: pick an image and your printer's ICC profile (the same one "
    "you'd print it with). The preview then appears on its own and refreshes "
    "automatically whenever you change a setting — there's no button to press.\n\n"
    "There are two ways to look at it:\n"
    "• Preview re-renders the image the way the printer would reproduce it. Turn on "
    "“Highlight out-of-gamut” to mark the colours your printer can't quite hit, and "
    "read the “Out of gamut” figure for the percentage of the image affected.\n"
    "• Gamut fit shows your image's colours as a 3D shape sitting inside your "
    "printer's colour space, so you can see exactly where — and how far — colours "
    "fall outside it.\n\n"
    "The settings, in plain terms:\n"
    "• Colour space — how the numbers in your image should be read. “Embedded” "
    "trusts the profile saved inside the file (most phone and web images are sRGB); "
    "pick “Other ICC profile…” to choose your own.\n"
    "• Intent — how colours the printer can't reproduce are handled. Relative "
    "colorimetric (the default) keeps everything else accurate and is what the "
    "out-of-gamut check relies on; Perceptual gently squeezes the whole image to fit.\n"
    "• Simulate paper white — shows the paper's real, often slightly warm white "
    "instead of bright screen white, for a more honest preview.\n"
    "• Monitor profile — set this to your display's own profile for a truer match; "
    "left empty, the preview assumes a standard sRGB screen.\n\n"
    "Two honest caveats: the preview is an approximation, not a fully colour-managed "
    "proof, and it assumes an sRGB-like display unless you set a monitor profile. "
    "Also, ArgyllCMS reads only ICC v2 profiles, so v4 profiles (often from "
    "i1Profiler) can't be used here — open those in the Profile info tool instead."
)


class SoftproofDialog(QDialog):
    def __init__(
        self,
        runner: "ArgyllRunner",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._settings = settings
        self._mode = resolve_mode(settings.get("appearance", "auto"))

        self._image_path: Path | None = None
        self._profile_path: Path | None = None
        self._display_path: Path | None = None
        self._custom_source_path: Path | None = None   # "Other ICC profile…"
        self._result: SoftproofResult | None = None
        self._web_view = None
        self._combined_html: str | None = None
        self._gamut_busy = False

        # The proof runs automatically (no button) — option changes are
        # coalesced through a short debounce so spinning a value doesn't queue
        # a cctiff run per tick.
        self._closed = False        # set on teardown → suppress queued/late work
        self._rerun_timer = QTimer(self)
        self._rerun_timer.setSingleShot(True)
        self._rerun_timer.setInterval(350)
        self._rerun_timer.timeout.connect(self._do_rerun)

        # 3D pipeline workflow objects (created lazily / reused)
        self._iccgamut = None
        self._tiffgamut = None
        self._viewgam = None
        self._printer_gam: str | None = None
        self._image_gam: str | None = None
        self._printer_html: str | None = None
        self._image_html: str | None = None

        self.setWindowTitle(tr("Soft-proof / check image"))
        self.setMinimumWidth(1180)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._softproof = SoftproofRunner(runner, settings, self)
        self._softproof.finished.connect(self._on_softproof_done)
        self._softproof.error.connect(self._on_softproof_error)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head, _header, stripe = dialog_masthead(
            self, tr("PROFILE · SOFT-PROOF"), tr("Soft-proof / check image"),
            tooltip_title=tr("Soft-proof / check image"), tooltip_body=_HELP,
            accent=self._pal()["accent"])
        root.addLayout(head)
        root.addWidget(stripe)

        self._inner = QVBoxLayout()
        self._inner.setContentsMargins(22, 14, 22, 22)
        self._inner.setSpacing(12)
        root.addLayout(self._inner)

        self._body = QLabel(
            tr("See roughly how a photo will look once it's printed on a particular "
               "printer and paper — so you can catch problems before spending ink and "
               "paper. Pick an image and your printer's ICC profile; the preview appears "
               "on its own and updates as you change the options."), self)
        self._body.setWordWrap(True)
        self._inner.addWidget(self._body)
        self._inner.addSpacing(8)   # breathing room before the Image: row

        # Side by side: all the options on the left, the image / 3D preview on
        # the right (so the preview gets the room, not the path fields).
        split = QHBoxLayout()
        split.setSpacing(16)
        left_panel = QWidget(self)
        left_panel.setFixedWidth(380)
        self._left = QVBoxLayout(left_panel)
        self._left.setContentsMargins(0, 0, 0, 0)
        self._left.setSpacing(12)
        split.addWidget(left_panel, 0)

        self._build_inputs()         # image … banner  → self._left (top)
        self._left.addStretch(1)     # push the action group to the bottom

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        self._left.addWidget(sep)

        self._build_action_group()   # status, toggles, Preview/Gamut, Soft-proof btn
        viewer = self._build_viewer()  # stack + out-of-gamut metric + Close (right)
        split.addWidget(viewer, 1)
        self._inner.addLayout(split, 1)

        # This window is violet-themed throughout (masthead, primary button,
        # metric), so its checkboxes / focus rings use the violet accent too,
        # rather than the neutral indicator the other tool dialogs use.
        # Flat-styled Preview / Gamut-fit toggle (the bottom-most control now
        # the Soft-proof button is gone). Native macOS push buttons clip under a
        # forced fixed height, so give them an explicit flat look; the active one
        # wears the accent.
        pal = self._pal()
        accent = pal["accent"]
        t_bg, t_fg, t_bd = pal["toggle_bg"], pal["toggle_fg"], pal["toggle_bd"]
        self.setStyleSheet(
            neutral_controls_qss(accent, popup=accent)
            + (f"QPushButton#view_toggle {{ background: {t_bg}; color: {t_fg};"
               f" border: 1px solid {t_bd}; border-radius: 4px; padding: 6px 10px; }}"
               f"QPushButton#view_toggle:checked {{ background: {accent};"
               f" color: {pal['on_accent']}; border: 1px solid {accent};"
               " font-weight: bold; }"
               # A disabled QLabel keeps the app-wide QSS text colour (QSS beats
               # the disabled palette), so grey the option names explicitly.
               f"QLabel:disabled {{ color: {pal['dim']}; }}"
               # Per-gamut opacity / saturation sliders, in the accent colour.
               f"QSlider::groove:horizontal {{ height: 4px; background: {pal['groove']};"
               " border-radius: 2px; }"
               f"QSlider::sub-page:horizontal {{ background: {accent};"
               " border-radius: 2px; }"
               f"QSlider::handle:horizontal {{ background: {accent};"
               " width: 12px; margin: -5px 0; border-radius: 6px; }"))
        tint_dialog_primary(self, accent)
        self._preselect_display_profile()
        # Pre-fill the last image used, as a convenience across sessions.
        last_image = str(settings.get("softproof_last_image", "") or "")
        if last_image and Path(last_image).is_file():
            self._set_image(Path(last_image))
        # Establish the initial enabled/greyed state and status (no image yet
        # ⇒ every proof option starts greyed out).
        self._auto_update()

    def _preselect_display_profile(self) -> None:
        """Pre-fill the monitor profile with the OS's currently active display
        profile, so soft-proofing is tuned to this screen out of the box. Best
        effort — silently leaves it empty (approximate sRGB) if undetectable."""
        path = detect_display_profile()
        if path is None or not path.exists():
            return
        self._display_path = path
        # Show the profile's own description when we can read it, else the file
        # name; full path on hover.
        label = path.name
        try:
            from workflow.icc_info import read_icc
            desc = read_icc(path).description
            if desc:
                label = desc
        except Exception:  # noqa: BLE001
            pass
        self._monitor_edit.setText(label)
        self._monitor_edit.setToolTip(str(path))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _path_row(self, label: str, placeholder: str, tip: str, on_browse) -> QLineEdit:
        """A 'label / read-only path edit / browse' block stacked in the left column."""
        self._left.addWidget(QLabel(label, self))
        row = QHBoxLayout()
        row.setSpacing(6)
        edit = QLineEdit(self)
        edit.setReadOnly(True)
        edit.setPlaceholderText(placeholder)
        row.addWidget(edit, 1)
        btn = make_browse_button(self, tip, "folder_check")
        btn.clicked.connect(on_browse)
        row.addWidget(btn)
        self._left.addLayout(row)
        return edit

    def _build_inputs(self) -> None:
        self._image_edit = self._path_row(
            tr("Image:"), tr("Browse for an image (TIFF, JPEG, PNG)…"),
            tr("Browse for an image"), self._on_browse_image)
        # Quick-pick a bundled photographic test target (no file hunting).
        test_row = QHBoxLayout()
        test_row.setContentsMargins(0, 0, 0, 0)
        test_btn = QPushButton(tr("Use built-in test image"), self)
        test_btn.setToolTip(tr("Load the bundled PhotoDisc colour test image "
                               "(Adobe RGB) — good for trying the soft-proof."))
        test_btn.clicked.connect(self._load_test_target)
        test_row.addWidget(test_btn)
        test_row.addStretch(1)
        self._left.addLayout(test_row)

        self._profile_edit = self._path_row(
            tr("Printer profile:"), tr("Browse for the printer's ICC profile (v2)…"),
            tr("Browse for the printer ICC profile"), self._on_browse_profile)

        # Optional monitor profile — when set, the preview is rendered for that
        # display (a truer proof); empty = approximate sRGB.
        self._left.addWidget(QLabel(tr("Monitor profile (optional):"), self))
        mon_row = QHBoxLayout()
        mon_row.setSpacing(6)
        self._monitor_edit = QLineEdit(self)
        self._monitor_edit.setReadOnly(True)
        self._monitor_edit.setPlaceholderText(tr("Approximate sRGB display"))
        mon_row.addWidget(self._monitor_edit, 1)
        mon_browse = make_browse_button(self, tr("Browse for your monitor's ICC profile"), "folder_check")
        mon_browse.clicked.connect(self._on_browse_monitor)
        mon_row.addWidget(mon_browse)
        mon_clear = QPushButton("✕", self)
        mon_clear.setObjectName("browse_compact")
        mon_clear.setFixedWidth(28)
        mon_clear.setToolTip(tr("Clear monitor profile"))
        mon_clear.clicked.connect(self._on_clear_monitor)
        mon_row.addWidget(mon_clear)
        self._left.addLayout(mon_row)

        # Colour space + intent (each on its own row to fit the narrow column).
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        # Option labels are kept so they grey out together with their controls.
        self._opt_labels: list[QLabel] = []
        cs_lbl = QLabel(tr("Colour space:"), self)
        self._opt_labels.append(cs_lbl)
        grid.addWidget(cs_lbl, 0, 0)
        self._source_combo = NoScrollComboBox(self)
        self._source_combo.addItem(tr("Embedded (else sRGB)"), "embedded")
        self._source_combo.addItem(tr("sRGB"), "srgb")
        self._source_combo.addItem(tr("Adobe RGB (1998)"), "adobergb")
        self._source_combo.addItem(tr("Display P3"), "p3")
        self._source_combo.addItem(tr("ProPhoto RGB"), "prophoto")
        self._source_combo.addItem(tr("Other ICC profile…"), "custom")
        grid.addWidget(self._source_combo, 0, 1)
        grid.addWidget(TooltipButton(
            tr("Soft-proof options"),
            tr("Colour space — how the image's RGB numbers should be interpreted. "
               "“Embedded” uses the profile stored in the image (falling back to sRGB if "
               "there is none or it's ICC v4). Most web/phone images are sRGB.\n\n"
               "Intent — how out-of-gamut colours are handled when mapping to the printer. "
               "Relative colorimetric (recommended) keeps in-gamut colours exact and clips "
               "the rest to the gamut boundary, which is what the out-of-gamut detection "
               "relies on. Perceptual compresses the whole image to fit."),
            self, min_width=520, color=self._pal()["accent"]), 0, 2)

        int_lbl = QLabel(tr("Intent:"), self)
        self._opt_labels.append(int_lbl)
        grid.addWidget(int_lbl, 1, 0)
        self._intent_combo = NoScrollComboBox(self)
        self._intent_combo.addItem(tr("Relative colorimetric"), "r")
        self._intent_combo.addItem(tr("Perceptual"), "p")
        self._intent_combo.addItem(tr("Saturation"), "s")
        self._intent_combo.addItem(tr("Absolute colorimetric"), "a")
        grid.addWidget(self._intent_combo, 1, 1)

        # Simulate paper white (absolute colorimetric), directly under Intent:
        # show the paper's actual off-white instead of mapping it to display
        # white. Overrides the intent for the preview, so grey the intent while
        # it's on.
        self._paper_white_cb = QCheckBox(tr("Simulate paper white"), self)
        self._paper_white_cb.setToolTip(
            tr("Render the preview with the paper's actual (often cream) white "
               "instead of bright display white — a more realistic proof. The "
               "out-of-gamut figure is unaffected."))
        self._paper_white_cb.toggled.connect(self._on_paper_white_toggled)
        grid.addWidget(self._paper_white_cb, 2, 1)

        de_lbl = QLabel(tr("Out-of-gamut ΔE:"), self)
        self._opt_labels.append(de_lbl)
        grid.addWidget(de_lbl, 3, 0)
        self._threshold_spin = NoScrollDoubleSpinBox(self)
        self._threshold_spin.setRange(0.5, 20.0)
        self._threshold_spin.setSingleStep(0.5)
        self._threshold_spin.setDecimals(1)
        self._threshold_spin.setValue(2.0)
        self._threshold_spin.setMinimumWidth(96)   # room for value + spin arrows
        thr_wrap = QHBoxLayout()
        thr_wrap.setContentsMargins(0, 0, 0, 0)
        thr_wrap.addWidget(self._threshold_spin)
        thr_wrap.addStretch(1)
        grid.addLayout(thr_wrap, 3, 1)
        grid.addWidget(TooltipButton(
            tr("Out-of-gamut sensitivity"),
            tr("A pixel counts as out of gamut when the printer would shift its colour by "
               "more than this ΔE. Lower = stricter (flags more pixels); 2 is a good "
               "default. The mark colour is what those pixels are painted in the preview."),
            self, min_width=460, color=self._pal()["accent"]), 3, 2)

        mark_lbl = QLabel(tr("Mark colour:"), self)
        self._opt_labels.append(mark_lbl)
        grid.addWidget(mark_lbl, 4, 0)
        self._highlight_combo = NoScrollComboBox(self)
        self._highlight_combo.addItem(tr("Grey"), "gray")
        self._highlight_combo.addItem(tr("Magenta"), "magenta")
        self._highlight_combo.addItem(tr("Cyan"), "cyan")
        grid.addWidget(self._highlight_combo, 4, 1)
        self._left.addLayout(grid)

        # v4 / advisory banner
        self._banner = QLabel("", self)
        self._banner.setWordWrap(True)
        self._banner.setTextFormat(Qt.TextFormat.RichText)
        self._banner.setVisible(False)
        self._left.addWidget(self._banner)

        # Any option that changes the actual proof maths re-runs it live.
        # (Connected after the combos are populated so seeding doesn't fire.)
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        self._intent_combo.currentIndexChanged.connect(self._schedule_rerun)
        self._threshold_spin.valueChanged.connect(self._schedule_rerun)
        self._highlight_combo.currentIndexChanged.connect(self._schedule_rerun)

    def _build_action_group(self) -> None:
        """Bottom-of-left group: status, on/off + highlight display options, and
        the Preview/Gamut-fit toggle (last — the proof itself runs
        automatically, so there is no longer a Soft-proof button)."""
        self._status = QLabel(tr("Pick an image and a printer profile to begin."), self)
        self._status.setStyleSheet(f"color: {TEXT_DIM};")
        self._status.setWordWrap(True)
        self._left.addWidget(self._status)

        # Display-only toggles (don't re-run the proof, just re-show it).
        self._softproof_cb = QCheckBox(tr("Show soft-proof"), self)
        self._softproof_cb.setChecked(True)
        self._softproof_cb.toggled.connect(self._refresh_preview)
        self._left.addWidget(self._softproof_cb)

        self._highlight_cb = QCheckBox(tr("Highlight out-of-gamut"), self)
        self._highlight_cb.setChecked(True)
        self._highlight_cb.toggled.connect(self._refresh_preview)
        self._left.addWidget(self._highlight_cb)

        # Out-of-gamut metric, sitting just above the Preview / Gamut-fit toggle.
        self._oog_label = QLabel(tr("Out of gamut: —"), self)
        self._oog_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._oog_label.setStyleSheet(
            f"color: {self._pal()['accent']}; font-family: Menlo, Consolas, monospace;"
            " font-size: 13px; font-weight: bold;")
        self._left.addWidget(self._oog_label)

        # Preview / Gamut-fit view toggle — the bottom-most control, where the
        # Soft-proof button used to be. The active one carries the accent.
        toggle = QHBoxLayout()
        toggle.setSpacing(8)
        self._preview_btn = QPushButton(tr("Preview"), self)
        self._gamut_btn = QPushButton(tr("Gamut fit"), self)
        for b in (self._preview_btn, self._gamut_btn):
            b.setCheckable(True)
            b.setObjectName("view_toggle")
            b.setMinimumHeight(36)   # min, not fixed — never clips its own label
        self._preview_btn.setChecked(True)
        self._preview_btn.clicked.connect(lambda: self._show_view(0))
        self._gamut_btn.clicked.connect(lambda: self._show_view(1))
        toggle.addWidget(self._preview_btn, 1)
        toggle.addWidget(self._gamut_btn, 1)
        self._left.addLayout(toggle)

    def _build_viewer(self) -> QWidget:
        right = QWidget(self)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)

        self._stack = QStackedWidget(right)
        self._stack.setMinimumHeight(360)
        self._stack.setMinimumWidth(720)

        self._preview = TiffPreview(self._stack)
        self._preview.set_appearance(self._mode)
        self._preview.set_caption(self._caption_with_hint(tr("APPROXIMATE SOFT-PROOF")))
        self._preview.set_navigation_visible(False)   # always one image at a time
        self._preview.set_interactive(True)            # wheel-zoom + drag-pan (#65)
        self._stack.addWidget(self._preview)

        self._gamut_frame = self._make_web_view()
        self._stack.addWidget(self._gamut_frame)
        rv.addWidget(self._stack, 1)

        # Bottom strip: the per-gamut display controls (separate opacity +
        # saturation for the image and printer gamut, shown only on the
        # Gamut-fit view) on the left, Close on the right — where the metric
        # used to sit. Tweaks apply to the 3D scene live via JavaScript.
        self._gamut_controls = self._build_gamut_controls()
        self._gamut_controls.setVisible(False)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self._gamut_controls)
        bottom.addStretch(1)
        # Save the proof exactly as shown (PNG / TIFF / JPEG) for sharing (#65).
        self._save_btn = QPushButton(tr("Save proof as…"), self)
        self._save_btn.setToolTip(
            tr("Save the soft-proof preview as an image (PNG, TIFF or JPEG). "
               "Note: it's an approximate, non-colour-managed rendering — good "
               "for illustration, not a colour-accurate file."))
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_proof)
        bottom.addWidget(self._save_btn, 0, Qt.AlignmentFlag.AlignBottom)
        close_btn = QPushButton(tr("Close"), self)
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignBottom)
        rv.addLayout(bottom)
        return right

    def _current_display_path(self) -> "Path | None":
        """The image file currently shown — original, proof, or highlighted —
        matching the toggles, so Save exports exactly what's on screen."""
        if not self._result:
            return None
        if not (self._softproof_cb.isChecked() and self._softproof_cb.isEnabled()):
            return self._image_path or Path(self._result.original_path)
        if self._highlight_cb.isChecked():
            return Path(self._result.highlight_path)
        return Path(self._result.proof_path)

    def _on_save_proof(self) -> None:
        src = self._current_display_path()
        if src is None or not src.is_file():
            return
        base = self._image_path.stem if self._image_path else "softproof"
        from PyQt6.QtCore import QStandardPaths
        pics = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.PicturesLocation) or str(Path.home())
        start = str(Path(pics) / f"{base}-softproof.png")
        path = save_file_dialog(
            self, tr("Save proof as"),
            tr("PNG image (*.png);;TIFF image (*.tif *.tiff);;JPEG image (*.jpg *.jpeg)"),
            start_path=start)
        if not path:
            return
        try:
            img = Image.open(src)
            if Path(path).suffix.lower() in (".jpg", ".jpeg") and img.mode != "RGB":
                img = img.convert("RGB")
            img.save(path)
            self._status.setText(tr("Saved proof to {name}.").format(name=Path(path).name))
        except (OSError, ValueError) as exc:
            InfoDialog(tr("Could not save"), str(exc), self, min_width=420).exec()

    def _set_oog(self, text: str) -> None:
        self._oog_label.setText(text)

    @staticmethod
    def _caption_with_hint(base: str) -> str:
        # The preview is zoomable/pannable — say so right in the caption so the
        # controls are discoverable (#65).
        return tr("{base}   ·   scroll to zoom · drag to pan · double-click to fit"
                  ).format(base=base)

    def _build_gamut_controls(self) -> QWidget:
        """Two rows — Image and Printer — each with an opacity and a saturation
        slider, so the user can dial each gamut's look in the 3D view
        independently (Knut's request)."""
        w = QWidget(self)
        grid = QGridLayout(w)
        grid.setContentsMargins(2, 2, 2, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(5, 1)
        # Header row.
        grid.addWidget(QLabel(tr("Opacity"), w), 0, 1, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel(tr("Saturation"), w), 0, 4, Qt.AlignmentFlag.AlignLeft)

        def add_row(row: int, name: str, opacity: int):
            grid.addWidget(QLabel(name, w), row, 0)
            op = QSlider(Qt.Orientation.Horizontal, w)
            op.setRange(0, 100)
            op.setValue(opacity)
            op.setFixedWidth(110)
            op_lbl = QLabel(f"{opacity}%", w)
            op_lbl.setFixedWidth(38)
            sat = QSlider(Qt.Orientation.Horizontal, w)
            sat.setRange(0, 100)
            sat.setValue(100)
            sat.setFixedWidth(110)
            sat_lbl = QLabel("100%", w)
            sat_lbl.setFixedWidth(38)
            wire = QCheckBox(tr("Wireframe"), w)
            grid.addWidget(op, row, 1)
            grid.addWidget(op_lbl, row, 2)
            grid.addWidget(sat, row, 4)
            grid.addWidget(sat_lbl, row, 5)
            grid.addWidget(wire, row, 6)
            for s, lbl in ((op, op_lbl), (sat, sat_lbl)):
                s.valueChanged.connect(
                    lambda v, l=lbl: l.setText(tr("{value}%").format(value=v)))
                s.valueChanged.connect(self._push_gamut_settings)
            # Wireframe changes geometry, so re-merge the (cached) scenes.
            wire.toggled.connect(self._rebuild_combined_html)
            return op, sat, wire

        # Image is opaque by default (it keeps its natural colours); the printer
        # gamut is the semi-transparent shell laid over it. A wireframe gamut is
        # drawn as a cage that never hides the other one.
        self._img_opacity, self._img_sat, self._img_wire = add_row(1, tr("Image"), 100)
        self._prn_opacity, self._prn_sat, self._prn_wire = add_row(2, tr("Printer"), 50)
        return w

    def _rebuild_combined_html(self, *_args) -> None:
        """Re-merge the cached image + printer gamut scenes with the current
        wireframe choices and reload — cheap (no iccgamut/tiffgamut re-run)."""
        if not (self._image_html and self._printer_html):
            return
        from workflow.viewgam_runner import _build_compare_overlay_html
        # Write next to an existing gamut HTML so the relative x3dom.js / .css
        # Argyll emitted there resolve — a fresh temp dir would have neither and
        # the scene would render blank.
        base = Path(self._combined_html).parent if self._combined_html \
            else Path(self._image_html).parent
        out = base / "combined_wire.html"
        ok = _build_compare_overlay_html(
            Path(self._image_html), Path(self._printer_html), out,
            primary_wire=self._img_wire.isChecked(),
            compare_wire=self._prn_wire.isChecked())
        if ok:
            self._combined_html = str(out)
            self._load_html(self._combined_html)

    def _push_gamut_settings(self, *_args) -> None:
        """Send the four slider values to the 3D scene (opacity = 100−transparency)."""
        if self._web_view is None:
            return
        img_t = 1.0 - self._img_opacity.value() / 100.0
        img_s = self._img_sat.value() / 100.0
        prn_t = 1.0 - self._prn_opacity.value() / 100.0
        prn_s = self._prn_sat.value() / 100.0
        self._web_view.page().runJavaScript(
            f"window._chromiqPrimaryOpacity={img_t:.2f};"
            f"window._chromiqPrimarySat={img_s:.2f};"
            f"window._chromiqCompareOpacity={prn_t:.2f};"
            f"window._chromiqCompareSat={prn_s:.2f};"
            "if(window._chromiqApplyPrimary)window._chromiqApplyPrimary();"
            "if(window._chromiqApplyCompare)window._chromiqApplyCompare();")

    def _make_web_view(self) -> QWidget:
        bg = self._pal()["bg"]
        border = self._pal()["border"]
        container = QWidget(self)
        container.setObjectName("gamutViewerFrame")
        container.setStyleSheet(
            "QWidget#gamutViewerFrame {"
            f" background: {bg}; border: 1px solid {border}; }}")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(1, 1, 1, 1)
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            view = QWebEngineView(container)
            view.page().setBackgroundColor(QColor(bg))
            try:
                from PyQt6.QtWebEngineCore import QWebEngineSettings
                view.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            except (ImportError, AttributeError):
                pass
            self._web_view = view
            # When a scene finishes loading, push the current slider values into
            # it (after X3DOM has initialised) so the gamuts honour them.
            view.loadFinished.connect(self._on_gamut_loaded)
            lay.addWidget(view)
            self._set_web_placeholder(tr("Select an image and a printer profile, then open "
                                         "this tab to build the 3D image-vs-printer gamut."))
        except ImportError:
            self._web_view = None
            lbl = QLabel(tr("Install PyQt6-WebEngine to view the 3D gamut."), container)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {self._pal()['placeholder']};")
            lay.addWidget(lbl)
        return container

    def _on_gamut_loaded(self, ok: bool) -> None:
        # X3DOM initialises asynchronously after load; give it a beat, then apply
        # the slider values to the (just-loaded) scene.
        if ok:
            QTimer.singleShot(300, self._push_gamut_settings)

    def _set_web_placeholder(self, text: str) -> None:
        if self._web_view is None:
            return
        bg = self._pal()["bg"]
        fg = self._pal()["placeholder"]
        self._web_view.setHtml(
            f"<html><body style='background:{bg};margin:0;display:flex;"
            "align-items:center;justify-content:center;height:100vh;'>"
            f"<p style='color:{fg};font-family:Menlo,monospace;font-size:12px;"
            f"text-align:center;'>{text}</p></body></html>")

    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        pin_min_height(
            self, min_width=1180, min_height=600,
            wrap_labels=(self._body, self._banner, self._status),
            inner_margins=self._inner.contentsMargins(), resize_width=True)

    # ------------------------------------------------------------------
    # File pickers + v4 guard
    # ------------------------------------------------------------------
    def _on_browse_image(self) -> None:
        # Start where the user last picked an image (the file's folder), for
        # convenience across sessions.
        last = str(self._settings.get("softproof_last_image", "") or "")
        start = str(Path(last).parent) if last and Path(last).parent.is_dir() \
            else str(Path.home())
        path = open_file_dialog(
            self, tr("Select an image"),
            tr("Images (*.tif *.tiff *.jpg *.jpeg *.png);;All files (*)"),
            start_dir=start, preview=True)
        if path:
            self._set_image(Path(path))

    def _load_test_target(self) -> None:
        from core.resource_path import resource_path
        path = resource_path("assets/test_images/photodisc-pdi-target.jpg")
        if not path.is_file():
            return
        # The target embeds an Adobe RGB profile — read the colour space from it.
        self._source_combo.setCurrentIndex(
            max(0, self._source_combo.findData("embedded")))
        self._set_image(path)

    def _set_image(self, path: Path) -> None:
        self._image_path = path
        self._image_edit.setText(str(path))
        self._settings.set("softproof_last_image", str(path))
        # A new image invalidates the previous proof / 3D result; show the raw
        # image straight away (instant feedback) and let the proof catch up.
        self._result = None
        self._combined_html = None
        self._set_oog(tr("Out of gamut: —"))
        self._show_original(reset_view=True)   # a new image starts fit-to-window
        self._auto_update()

    def _show_original(self, reset_view: bool = False) -> None:
        """Display the picked image as-is (no proof) and switch to the preview."""
        if self._image_path is None:
            return
        self._preview.set_caption(self._caption_with_hint(tr("ORIGINAL IMAGE")))
        self._preview.set_frame_color(None)
        self._preview.load_tiff([self._image_path], preserve_view=not reset_view)
        self._show_view(0)

    def _on_browse_profile(self) -> None:
        sidebar = [str(d) for d in icc_system_dirs() if Path(d).exists()]
        path = open_file_dialog(
            self, tr("Select the printer ICC profile"),
            tr("ICC profiles (*.icc *.icm);;All files (*)"),
            start_dir=(sidebar[0] if sidebar else ""), extra_paths=sidebar)
        if path:
            self._profile_path = Path(path)
            self._profile_edit.setText(path)
            self._check_profile_version()
            self._auto_update()

    def _on_browse_monitor(self) -> None:
        sidebar = [str(d) for d in icc_system_dirs() if Path(d).exists()]
        path = open_file_dialog(
            self, tr("Select your monitor's ICC profile"),
            tr("ICC profiles (*.icc *.icm);;All files (*)"),
            start_dir=(sidebar[0] if sidebar else ""), extra_paths=sidebar)
        if path:
            self._display_path = Path(path)
            self._monitor_edit.setText(path)
            self._schedule_rerun()

    def _on_clear_monitor(self) -> None:
        self._display_path = None
        self._monitor_edit.clear()
        self._schedule_rerun()

    def _on_source_changed(self, *_args) -> None:
        """Colour-space dropdown changed. 'Other ICC profile…' opens a browser so
        the user can point at their own working-space profile (Knut's request —
        works even when Argyll's bundled profiles can't be found)."""
        if self._source_combo.currentData() == "custom":
            self._browse_custom_source()
            if self._custom_source_path is None:
                # Cancelled with nothing chosen — fall back to the first entry.
                self._source_combo.setCurrentIndex(0)
                return
        self._schedule_rerun()

    def _browse_custom_source(self) -> None:
        sidebar = [str(d) for d in icc_system_dirs() if Path(d).exists()]
        path = open_file_dialog(
            self, tr("Select a colour-space ICC profile"),
            tr("ICC profiles (*.icc *.icm);;All files (*)"),
            start_dir=(sidebar[0] if sidebar else ""), extra_paths=sidebar)
        if path:
            self._custom_source_path = Path(path)
            idx = self._source_combo.findData("custom")
            if idx >= 0:
                self._source_combo.setItemText(
                    idx, tr("Custom: {name}").format(name=Path(path).name))

    def _check_profile_version(self) -> None:
        if self._profile_path and is_v4(self._profile_path):
            self._banner.setText(tr(
                "<b>This printer profile is ICC v4.</b> ArgyllCMS can only read v2 "
                "profiles, so it can't be soft-proofed here. Open it in the "
                "<b>Profile info</b> tool for details, or use a v2 profile."))
            _wp = self._pal()
            self._banner.setStyleSheet(
                f"QLabel {{ background: {_wp['warn_bg']}; color: {_wp['warn_fg']};"
                f" border: 1px solid {_wp['warn_bd']}; border-radius: 4px;"
                " padding: 8px 10px; }")
            self._banner.setVisible(True)
        else:
            self._banner.setVisible(False)

    # ------------------------------------------------------------------
    # Auto-update: show the image immediately, proof as soon as it can
    # ------------------------------------------------------------------
    def _update_controls_enabled(self) -> None:
        """Grey every proof option out until there's an actual proof to show —
        i.e. both an image and a usable (v2) printer profile are present."""
        ready = self._can_proof()
        for w in (self._source_combo, self._threshold_spin,
                  self._highlight_combo, self._paper_white_cb):
            w.setEnabled(ready)
        for lbl in self._opt_labels:           # grey the option names too
            lbl.setEnabled(ready)
        # Intent is additionally suppressed while "Simulate paper white" is on.
        self._intent_combo.setEnabled(ready and not self._paper_white_cb.isChecked())
        self._softproof_cb.setEnabled(ready)
        self._highlight_cb.setEnabled(ready and self._softproof_cb.isChecked())
        self._save_btn.setEnabled(self._result is not None)

    def _can_proof(self) -> bool:
        return bool(self._image_path and self._profile_path
                    and not is_v4(self._profile_path))

    def _on_paper_white_toggled(self, on: bool) -> None:
        # Paper white overrides the intent for the preview, so grey it; and the
        # change alters the proof maths, so re-run.
        self._intent_combo.setEnabled(not on)
        self._schedule_rerun()

    def _auto_update(self) -> None:
        """Decide what to show after any input change — original image while a
        profile is still missing, a live proof once both are present."""
        self._update_controls_enabled()
        if self._image_path is None:
            self._status.setText(tr("Pick an image and a printer profile to begin."))
            return
        if self._profile_path is None:
            self._status.setText(tr(
                "Showing the original image — pick a printer profile to soft-proof it."))
            return
        if is_v4(self._profile_path):
            # The v4 banner already explains; keep the original on screen.
            self._status.setText(tr("This printer profile can't be soft-proofed (ICC v4)."))
            return
        self._schedule_rerun()

    def _schedule_rerun(self, *_args) -> None:
        """Coalesce option changes — (re)start the debounce; the timer fires
        the actual proof once things settle."""
        if self._can_proof():
            self._rerun_timer.start()

    def _do_rerun(self) -> None:
        if not self._can_proof():
            return
        if self._runner.is_running:
            self._rerun_timer.start()   # busy (e.g. building 3D) — try again soon
            return
        self._run_softproof()

    # ------------------------------------------------------------------
    # Soft-proof run
    # ------------------------------------------------------------------
    def _run_softproof(self) -> None:
        if not (self._image_path and self._profile_path):
            return
        if self._runner.is_running:
            self._rerun_timer.start()
            return
        self._status.setText(tr("Soft-proofing…"))
        # Invalidate any previous 3D result (inputs changed).
        self._combined_html = None
        self._printer_gam = None
        self._image_gam = None
        self._set_web_placeholder(tr("Open this tab to build the 3D gamut for the new image."))
        params = SoftproofParams(
            image_path=self._image_path,
            printer_profile=self._profile_path,
            source_choice=self._source_combo.currentData(),
            custom_source=self._custom_source_path,
            intent=self._intent_combo.currentData(),
            threshold=self._threshold_spin.value(),
            highlight=self._highlight_combo.currentData(),
            paper_white=self._paper_white_cb.isChecked(),
            display_profile=self._display_path,
        )
        self._softproof.run(params)

    def _on_softproof_done(self, result: SoftproofResult) -> None:
        self._result = result
        self._set_oog(tr("Out of gamut: {pct:.1f}%").format(pct=result.oog_percent))
        self._status.setText(tr("Done — {note}.").format(note=result.source_note))
        self._refresh_preview()
        # The proof changed, so the (lazy) 3D is stale — rebuild it only if the
        # user is actually looking at the Gamut-fit view right now.
        if self._stack.currentIndex() == 1:
            self._ensure_gamut()

    def _on_softproof_error(self, msg: str) -> None:
        # A late signal from an in-flight cctiff can arrive after the dialog was
        # dismissed; don't pop a modal into a dead window.
        if getattr(self, "_closed", False):
            return
        self._status.setText(tr("Soft-proof failed."))
        InfoDialog(tr("Soft-proof failed"), msg, self, min_width=480).exec()

    def _refresh_preview(self, *_args) -> None:
        self._update_controls_enabled()
        if not self._result:
            # No proof yet — keep the raw image on screen if we have one.
            if self._image_path is not None:
                self._show_original()
            return
        show_proof = self._softproof_cb.isChecked()
        if not show_proof:
            # Show the crisp full-resolution original, not the 2400-px copy the
            # proof was computed from (which looks soft next to the proof).
            path = self._image_path or Path(self._result.original_path)
            self._preview.set_caption(self._caption_with_hint(tr("ORIGINAL IMAGE")))
        else:
            path = (self._result.highlight_path if self._highlight_cb.isChecked()
                    else self._result.proof_path)
            self._preview.set_caption(self._caption_with_hint(tr("APPROXIMATE SOFT-PROOF")))
        # Tint the margin to the simulated paper white — but only while the
        # (paper-white) soft-proof is shown; the original image keeps plain white.
        pw = self._result.paper_white_rgb if show_proof else None
        self._preview.set_frame_color(QColor(*pw) if pw else None)
        # Same image, just re-rendered/toggled → keep the user's zoom & pan.
        self._preview.load_tiff([Path(path)], preserve_view=True)

    # ------------------------------------------------------------------
    # View toggle + lazy 3D
    # ------------------------------------------------------------------
    def _show_view(self, index: int) -> None:
        self._preview_btn.setChecked(index == 0)
        self._gamut_btn.setChecked(index == 1)
        self._stack.setCurrentIndex(index)
        # The per-gamut opacity/saturation sliders only make sense in 3D.
        self._gamut_controls.setVisible(index == 1)
        if index == 1:
            self._ensure_gamut()

    def _ensure_gamut(self) -> None:
        if self._combined_html:
            self._load_html(self._combined_html)
            return
        if self._gamut_busy or self._result is None or self._profile_path is None:
            if self._result is None:
                self._set_web_placeholder(
                    tr("Select an image and a printer profile first."))
            return
        if self._runner.is_running:
            self._set_web_placeholder(tr("Another process is running — try again in a moment."))
            return
        self._gamut_busy = True
        self._set_web_placeholder(tr("Building the 3D gamut… this can take a few seconds."))
        self._start_printer_gamut()

    def _pal(self) -> dict:
        """This appearance's frame colours. A fourth is a row in _PALETTES."""
        return _PALETTES.get(self._mode, _PALETTE_DARK)

    def _bg(self) -> str:
        return self._pal()["bg"]

    def _start_printer_gamut(self) -> None:
        from workflow.gamut_viewer import GamutViewer, GamutViewerParams
        self._iccgamut = GamutViewer(self._runner, self)
        self._iccgamut.finished.connect(self._on_printer_gamut)
        self._iccgamut.error.connect(self._on_gamut_error)
        self._iccgamut.run(
            GamutViewerParams(icc_path=self._profile_path, sres=10.0),
            on_line=lambda _l: None, on_finish=lambda _c: None,
            themed=True, bg=self._bg())

    def _on_printer_gamut(self, _vol: float, html: str, gam: str) -> None:
        self._printer_gam = gam
        self._printer_html = html
        QTimer.singleShot(0, self._start_image_gamut)

    def _start_image_gamut(self) -> None:
        from workflow.tiffgamut_runner import TiffgamutRunner, TiffgamutParams
        work = Path(self._result.proof_path).parent
        # A small copy of the image keeps tiffgamut fast (bounded, no hang).
        try:
            small = prepare_input_tiff(self._image_path, work, max_dim=500)
        except (OSError, ValueError) as exc:
            self._on_gamut_error(str(exc))
            return
        src, _note = resolve_source_profile(
            self._image_path, self._source_combo.currentData(), self._settings, work,
            self._custom_source_path)
        if src is None:
            self._on_gamut_error(tr("No source colour-space profile found."))
            return
        self._tiffgamut = TiffgamutRunner(self._runner, self)
        self._tiffgamut.finished.connect(self._on_image_gamut)
        self._tiffgamut.error.connect(self._on_gamut_error)
        self._tiffgamut.run(
            TiffgamutParams(image_path=small, profile_path=src, sres=10.0, filter_perc=90.0),
            themed=True, bg=self._bg())

    def _on_image_gamut(self, _vol: float, html: str, gam: str) -> None:
        self._image_gam = gam
        self._image_html = html
        QTimer.singleShot(0, self._start_viewgam)

    def _start_viewgam(self) -> None:
        from workflow.viewgam_runner import ViewgamRunner
        if not (self._printer_gam and self._image_gam):
            self._on_gamut_error(tr("Gamut files missing."))
            return
        self._viewgam = ViewgamRunner(self._runner, self)
        self._viewgam.finished.connect(self._on_viewgam_done)
        self._viewgam.error.connect(self._on_gamut_error)
        # primary = image (opaque, keeps its colours); compare = printer (shell).
        self._viewgam.run(
            primary_gam=Path(self._image_gam),
            compare_gam=Path(self._printer_gam),
            primary_html=Path(self._image_html) if self._image_html else None,
            compare_html=Path(self._printer_html) if self._printer_html else None,
            on_line=lambda _l: None, on_finish=lambda _c: None,
            themed=True, bg=self._bg())

    def _on_viewgam_done(self, result) -> None:
        self._gamut_busy = False
        self._combined_html = result.html_path
        if not result.html_path:
            self._set_web_placeholder(tr("Could not build the combined 3D gamut."))
        elif self._img_wire.isChecked() or self._prn_wire.isChecked():
            self._rebuild_combined_html()   # honour a pre-set wireframe choice
        else:
            self._load_html(result.html_path)

    def _on_gamut_error(self, msg: str) -> None:
        self._gamut_busy = False
        log.warning("softproof 3D gamut: %s", msg)
        self._set_web_placeholder(tr("The 3D gamut could not be built:\n{msg}").format(msg=msg))

    def _load_html(self, html_path: str) -> None:
        if self._web_view is not None and html_path:
            self._web_view.setUrl(QUrl.fromLocalFile(html_path))

    # ------------------------------------------------------------------
    # WebEngine teardown (issue #38) — never leave a live Chromium subtree
    # ------------------------------------------------------------------
    def _teardown_webengine(self) -> None:
        # Dismissing the dialog must not leave a proof queued: a pending rerun
        # would fire after we're gone, launch cctiff, and (on failure) pop a
        # modal into a dead dialog — which wedged the test suite. Stop it.
        self._closed = True
        if self._rerun_timer.isActive():
            self._rerun_timer.stop()
        drain_web_view(self._web_view)
        self._web_view = None
        # …and the files. AFTER the web view is drained: the 3D gamut pages
        # live in sibling temp folders and the page resolves x3dom.js out of
        # its own directory, so deleting before the drain would pull the scene
        # out from under a still-live view.
        self._drop_temp_work()

    def _drop_temp_work(self) -> None:
        """Delete every temp folder this dialog is still holding.

        None of these was ever removed. main.py exits via ``os._exit()`` and
        says so — *"There are no atexit hooks of our own to lose"* — so nothing
        reclaims them at quit either, and there is no production sweeper.
        """
        import shutil
        from pathlib import Path

        # `self._softproof`, NEVER `self._runner`. `_runner` is the APP-WIDE
        # ArgyllRunner singleton, and it happens to have a `cleanup()` of its
        # own that disconnects `line_received`, `finished` and `_pty_done` for
        # the whole process and kills any running tool. Calling it from here
        # meant that closing this dialog silently deafened the entire app: the
        # next measurement's chartread (a PTY run) would finish and nobody
        # would hear it, so the tabs and the masthead stayed greyed until
        # restart. A duck-typed `getattr(..., "cleanup")` is what made the
        # wrong object look right — so this names the object outright.
        sp = getattr(self, "_softproof", None)
        if sp is not None:
            try:
                sp.cleanup()
            except Exception:      # noqa: BLE001 — teardown must not raise
                log.debug("softproof work dir could not be removed", exc_info=True)

        # The gamut HTML folders: deliberate while the dialog lives (the
        # wireframe toggle re-reads them), garbage once it does not.
        for attr in ("_printer_html", "_image_html", "_combined_html"):
            path = getattr(self, attr, None)
            if not path:
                continue
            try:
                shutil.rmtree(Path(path).parent, ignore_errors=True)
            except Exception:      # noqa: BLE001
                log.debug("gamut temp dir could not be removed", exc_info=True)
            setattr(self, attr, None)

    def reject(self) -> None:  # noqa: D102
        self._teardown_webengine()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._teardown_webengine()
        super().closeEvent(event)
