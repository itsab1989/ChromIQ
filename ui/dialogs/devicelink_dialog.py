"""Tools → "Create device-link profile" (collink wrapper).

Builds an ICC **device-link** from a source profile + a destination (printer)
profile, with gamut-mapping control collink offers beyond colprof's stock
intents. The result is applied later in Photoshop ("Convert to Profile") or a
RIP — it is an export artifact, not part of ChromIQ's measure→profile loop.

Follows the shared Tools-dialog chrome (:class:`_ToolDialogBase`): cyan masthead,
a ⓘ help button on every option, and ChromIQ's own (non-native) file pickers.
The input rows live in a fade-edged scroll area so the optional **Expert**
section (per-image source gamut, abstract profile, calibration, 3DLUT export,
inverse gamut mode, forced white point) can't push the window off-screen. v4
source profiles are transcoded to v2 first (Argyll is v2-only); temp files are
deleted afterwards.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.logger import get_logger
from ui.dialogs.tools_dialogs import (
    _OutputRow,
    _ToolDialogBase,
    _initial_dir,
    _remember_dir,
    neutral_controls_qss,
)
from ui.fade_scroll import FadeScrollArea
from ui.styles import SPEC_CYAN
from ui.theme import accent_for, resolve_mode
from ui.tooltip_button import TooltipButton
from ui.widgets import (
    disabled_primary_qss,
    primary_hover,
    primary_label,
    CollapsibleGroupBox,
    NoScrollComboBox,
    NoScrollSpinBox,
    confirm,
    icc_profile_paths,
    load_folder_icon,
    make_browse_button,
    open_file_dialog,
    open_files_dialog,
)
from workflow.collink_runner import CollinkParams, CollinkRunner
from workflow.icc_convert import NotConvertible, to_v2
from workflow.icc_info import IccParseError, read_icc

log = get_logger(__name__)

_ICC_FILTER = "ICC profiles (*.icc *.icm);;All files (*)"
_CAL_FILTER = "Calibration files (*.cal);;All files (*)"
_IMG_FILTER = "Images (*.tif *.tiff *.jpg *.jpeg *.png);;All files (*)"


class DeviceLinkDialog(_ToolDialogBase):
    TOOL_KEY  = "device_link"
    TITLE     = tr("Create device-link profile")
    EYEBROW   = tr("PROFILES · DEVICE-LINK")
    ACCENT    = SPEC_CYAN
    RUN_LABEL = tr("Create device-link")
    MIN_WIDTH = 700

    HELP = (
        tr("A device-link profile bakes a fixed 'source → your printer' colour "
        "conversion into one file, with the gamut mapping decided up front.\n\n"
        "Normally a colour-managed app converts a photo through a neutral middle "
        "step (Lab) every time you print, and the result can vary between apps and "
        "software versions. A device-link skips that live round-trip: you apply "
        "one pre-tested transform, so a stable printer/ink/paper setup gives the "
        "exact same colour across a whole series of prints — handy for photo books, "
        "exhibitions and art reproduction.\n\n"
        "How to use it:\n\n"
        "1. Pick the source profile — the colour space your images are in "
        "(sRGB, AdobeRGB, ProPhoto…).\n"
        "2. Pick the destination — the printer profile you built in ChromIQ.\n"
        "3. Choose how colours outside the printer's range are mapped (the "
        "rendering style) and the viewing conditions.\n"
        "4. Save the device-link, then in Photoshop open Edit → Convert to "
        "Profile, switch on 'Advanced' (device-links only appear there), pick "
        "yours under 'Device Link', and print with the printer's colour "
        "management turned off. Or load it in your RIP.\n\n"
        "Tip: it pays off most when you reuse the same printer/ink/paper for many "
        "images — especially on matte fine-art paper, where the standard "
        "perceptual and relative intents are often unsatisfying. For a one-off "
        "print the normal workflow is simpler."))
    DESCRIPTION = (
        tr("Create a fixed source→printer transform (an ICC device-link) with "
        "explicit gamut-mapping control, to apply in Photoshop's Convert to "
        "Profile or a RIP. Source profiles in ICC v4 are converted to v2 "
        "automatically (Argyll only reads v2)."))

    # (label, collink -i gamut-mapping intent code). The first four are the
    # everyday choices; the rest are collink's finer gamut-mapping intents,
    # exposed for expert use (e.g. 'lp' luminance-preserving perceptual, which
    # often suits matte fine-art paper).
    _INTENTS = (
        (tr("Photographic (perceptual) — recommended"), "p"),
        (tr("Luminance-preserving perceptual (matte paper)"), "lp"),
        (tr("Perceptual appearance"), "pa"),
        (tr("Accurate colours (relative colorimetric)"), "r"),
        (tr("Luminance-matched appearance"), "la"),
        (tr("Saturation (smoother)"), "ms"),
        (tr("Punchy (saturation)"), "s"),
        (tr("Proof another device (absolute colorimetric)"), "a"),
        (tr("Absolute, scaled to paper white"), "aw"),
    )
    # (label, tiffgamut -f popularity filter %). 0 = omit -f (keep every colour,
    # gradations of even rare colours preserved). A lower % tightens the gamut
    # around the image's popular colours, holding their saturation better.
    # -1 = "Custom…", which reveals a raw 0–100 spinner.
    _CUSTOM_DETAIL = -1
    _IMAGE_DETAIL = (
        (tr("Favour the main colours (recommended)"), 80),
        (tr("Preserve all gradations"), 0),
        (tr("Balanced"), 90),
        (tr("Strongly favour saturation"), 60),
        (tr("Custom…"), -1),
    )
    # (label, collink -c code) — where the source images are viewed (a screen)
    _SRC_VIEWCONDS = (
        (tr("Monitor in a typical room (recommended)"), "mt"),
        (tr("Bright monitor in a bright room"), "mb"),
        (tr("Monitor in a darkened room"), "md"),
    )
    # (label, collink -d code) — where the finished print is viewed
    _DST_VIEWCONDS = (
        (tr("Normal indoor light (recommended)"), "pp"),
        (tr("D50 viewing booth (critical)"), "pc"),
        (tr("Print evaluation (CIE 116-1995)"), "pe"),
        (tr("Print, partial mid-tone adaptation"), "pm"),
    )
    # (label, collink -q code)
    _QUALITIES = (
        (tr("High (recommended)"), "h"),
        (tr("Ultra (slowest, finest)"), "u"),
        (tr("Medium (faster)"), "m"),
    )
    # (label, collink -3 code)  "" = off
    _LUT3D = (
        (tr("Off"), ""),
        (tr("IRIDAS / Resolve (.cube)"), "c"),
        (tr("eeColor (.txt)"), "e"),
        (tr("MadVR (.3dlut)"), "m"),
    )

    def __init__(self, runner, settings, parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._runner = runner
        self._collink = CollinkRunner(runner)
        self._src_path: Path | None = None
        self._dst_path: Path | None = None
        self._abstract_path: Path | None = None
        self._cal_path: Path | None = None
        self._image_paths: list[Path] = []
        self._temp_files: list[Path] = []
        self._build_inputs()
        self._autofill_destination()
        # The base styles interactive controls with the neutral indicator; this
        # window is cyan-themed throughout, so re-tint checkboxes, focus rings,
        # combos and the primary button to the masthead accent (appended so the
        # cyan rules win over the base's neutral ones, keeping its dark-mode
        # status-field fix intact).
        self._run_btn.setObjectName("primary")
        self.setStyleSheet(self.styleSheet() + neutral_controls_qss(SPEC_CYAN))
        self._style_primary_button()
        self._refresh()

    def _style_primary_button(self) -> None:
        """Cyan primary button that mirrors the Build Profile button: filled when
        enabled, and — when the required fields aren't filled — a muted fill with
        a cyan accent border so it reads as inactive but on-brand."""
        mode = resolve_mode(self._settings.get("appearance", "auto"))
        light = mode == "light"
        c = accent_for(SPEC_CYAN, mode)
        hover = primary_hover(c, mode)
        # White on cyan in Light, near-black in Dark, ON_ACTION in Neutral.
        text = "#ffffff" if light else primary_label(mode)
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background: {c}; border: 1px solid {c}; color: {text};"
            f" font-weight: 700; }}"
            f"QPushButton:hover {{ background: {hover}; border-color: {hover}; }}"
            + disabled_primary_qss(c, mode))

    # ------------------------------------------------------------------ UI
    def _file_row(self, layout: QVBoxLayout, placeholder: str, on_pick):
        """A read-only path field + Browse button appended to ``layout``."""
        row = QHBoxLayout()
        field = QLineEdit(self)
        field.setReadOnly(True)
        field.setPlaceholderText(placeholder)
        row.addWidget(field, 1)
        browse = make_browse_button(self, tr("Browse…"), icon="folder_build")
        browse.clicked.connect(on_pick)
        row.addWidget(browse)
        layout.addLayout(row)
        return field

    def _label_row(self, layout: QVBoxLayout, text: str,
                   tip_title: str, tip_body: str) -> None:
        head = QHBoxLayout()
        head.addWidget(QLabel(text, self))
        head.addStretch(1)
        head.addWidget(self._tip(tip_title, tip_body), 0,
                       Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(head)

    def _tip(self, title: str, body: str, min_width: int = 520) -> TooltipButton:
        return TooltipButton(title, body, self, min_width=min_width, color=SPEC_CYAN)

    def _combo_row(self, layout: QVBoxLayout, label: str, tip_title: str,
                   tip_body: str, entries) -> NoScrollComboBox:
        row = QHBoxLayout()
        row.addWidget(QLabel(label, self))
        combo = NoScrollComboBox(self)
        for text, data in entries:
            combo.addItem(text, data)
        row.addWidget(combo, 1)
        row.addWidget(self._tip(tip_title, tip_body, 500), 0,
                      Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(row)
        return combo

    def _check_row(self, layout: QVBoxLayout, label: str,
                   tip_title: str, tip_body: str, checked: bool = False) -> QCheckBox:
        row = QHBoxLayout()
        cb = QCheckBox(label, self)
        cb.setChecked(checked)
        row.addWidget(cb)
        row.addStretch(1)
        row.addWidget(self._tip(tip_title, tip_body, 480), 0,
                      Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(row)
        return cb

    def _build_inputs(self) -> None:
        # All input rows live inside a fade-edged scroll area so the Expert
        # section can't push the dialog off a short screen.
        host = QWidget(self)
        form = QVBoxLayout(host)
        # Right inset so the scrollbar leaves a gap to the section frames /
        # inputs instead of butting against them.
        form.setContentsMargins(0, 0, 10, 0)
        form.setSpacing(10)
        self._form = form
        self._build_basic(form)
        self._build_expert(form)
        self._build_output(form)

        scroll = FadeScrollArea(self, surface="panel")
        # No frame: the QScrollArea's default border insets the viewport, which
        # offsets the fade overlay from the content edge and lets a sliver of
        # text show through. Without it the fade aligns flush with the rows.
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.FADE_H = 34          # taller, smoother fade than the 24px default
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        scroll.set_appearance(resolve_mode(self._settings.get("appearance", "auto")))
        scroll.setMinimumHeight(240)
        avail = QGuiApplication.primaryScreen().availableGeometry().height()
        scroll.setMaximumHeight(max(320, int(avail * 0.9) - 300))
        self._scroll = scroll
        self._content.addWidget(scroll)

    def _build_basic(self, form: QVBoxLayout) -> None:
        self._label_row(
            form, tr("Source profile — the colour space your images are in:"),
            tr("Source profile"),
            tr("The colour space your photos are saved in — most often sRGB, "
            "AdobeRGB (1998) or ProPhoto/ROMM. This tells the device-link where "
            "the colours are coming from. If the file is an ICC version-4 profile, "
            "ChromIQ converts a copy to version 2 automatically, because the "
            "ArgyllCMS engine only reads version 2."))
        self._src_field = self._file_row(
            form, tr("Pick an ICC profile (e.g. sRGB, AdobeRGB)…"),
            self._pick_source)

        self._label_row(
            form, tr("Destination profile — your printer profile:"),
            tr("Destination (printer) profile"),
            tr("The printer profile you built in ChromIQ for this printer, ink and "
            "paper. The device-link maps your source colours straight onto what "
            "this printer can reproduce. If you have a current project open, "
            "ChromIQ fills this in for you."))
        self._dst_field = self._file_row(
            form, tr("Pick your printer .icc (auto-filled from the current project)…"),
            self._pick_destination)

        self._intent_combo = self._combo_row(
            form, tr("Rendering style:"), tr("Rendering style"),
            tr("How colours that fall outside the printer's range are handled.\n\n"
            "• Photographic (perceptual) gently squeezes the whole picture so "
            "relationships between colours stay natural — the best default for "
            "photos.\n"
            "• Accurate keeps in-range colours exact and clips the rest — good for "
            "logos and spot colours.\n"
            "• Punchy favours vivid saturation.\n"
            "• Proof reproduces another device's colours as-is, for proofing.\n"
            "• The remaining entries are collink's finer gamut-mapping intents. "
            "Luminance-preserving perceptual is well worth a try on matte fine-art "
            "paper, where the standard perceptual and relative intents often "
            "disappoint.\n\n"
            "Note: perceptual and its variants can nudge very saturated colours — "
            "magenta especially — a few degrees warmer to keep gradations smooth; "
            "if a hue must stay exact, choose Accurate colours.\n\n"
            "The choice is baked into the link — when you apply it in Photoshop the "
            "intent dropdown no longer matters (pick the link under any intent)."),
            self._INTENTS)

        self._src_view_combo = self._combo_row(
            form, tr("Screen viewing conditions:"), tr("Screen viewing conditions"),
            tr("This tells the device-link how bright the room is where you look at "
            "your images on screen, so it can match the print to what your eyes are "
            "adapted to while editing.\n\n"
            "• Monitor in a typical room — normal home or office lighting. This is "
            "the safe default for most people.\n"
            "• Bright monitor in a bright room — a daylight-bright workspace, or a "
            "monitor turned up high.\n"
            "• Monitor in a darkened room — a dim editing suite with the lights "
            "down low.\n\n"
            "If you're not sure, leave it on 'typical room' — the difference is "
            "subtle and only matters for very precise work."),
            self._SRC_VIEWCONDS)

        self._dst_view_combo = self._combo_row(
            form, tr("Print viewing conditions:"), tr("Print viewing conditions"),
            tr("This tells the device-link the light your finished print will be "
            "seen under, so its colours are adapted to that setting.\n\n"
            "• Normal indoor light — everyday viewing on a wall or desk under "
            "typical room lighting (the ISO 3664 P2 standard). The best default.\n"
            "• D50 viewing booth (critical) — a colour-managed proofing booth set "
            "to the D50 standard (ISO 3664 P1). Choose this when prints are judged "
            "in a booth, e.g. exhibition or reproduction work.\n"
            "• Print evaluation (CIE 116-1995) — an alternative standard print-"
            "viewing setting, for matching that specification.\n"
            "• Print, partial mid-tone adaptation — adapts the mid-tones only part "
            "of the way; occasionally helps in critical colour-matching cases.\n\n"
            "If in doubt, use 'Normal indoor light'."),
            self._DST_VIEWCONDS)

        self._quality_combo = self._combo_row(
            form, tr("Quality:"), tr("Quality"),
            tr("How finely the conversion table is computed. High is the right "
            "choice for a saved link you'll reuse. Ultra is a touch finer but much "
            "slower; Medium is faster if you're just experimenting."),
            self._QUALITIES)

        self._black_cb = self._check_row(
            form, tr("Map source black to printer black"), tr("Map black to black"),
            tr("Lines up the darkest source colour with the darkest the printer "
            "can make, so shadows use the paper's full depth instead of looking "
            "washed out or plugged. Recommended on for RGB photo printing."),
            checked=True)

        self._diag_cb = self._check_row(
            form, tr("Also save a gamut-mapping diagnostic (3D)"),
            tr("Gamut-mapping diagnostic"),
            tr("Writes an extra interactive 3D web page next to the link showing "
            "how colours were moved to fit the printer. Useful if you want to see "
            "what the mapping did; leave it off otherwise."))

    def _build_expert(self, form: QVBoxLayout) -> None:
        group = CollapsibleGroupBox(tr("Expert options"), self, collapsed=True)
        body = QVBoxLayout(group.body)
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(10)

        # 1 — per-image source gamut (runs tiffgamut before collink). Accepts a
        # whole set of images (one shared gamut) and a popularity-filter detail.
        self._image_cb = self._check_row(
            body, tr("Optimise the mapping for specific images"),
            tr("Optimise for specific images"),
            tr("Normally the link is built to fit the whole source colour space — "
            "on a big space like ProPhoto that can over-compress and dull strong "
            "colours. Tick this and add one or more images, and ChromIQ measures "
            "the colours actually in them (in the same appearance space the "
            "mapping uses) and tunes the link to those, so the colours you care "
            "about get the most faithful treatment. Add a whole series (e.g. an "
            "exhibition set) to map every image identically. Best when you'll "
            "reprint the same pictures, or a set with similar colours."))
        self._image_cb.toggled.connect(self._on_image_toggled)

        self._image_list = QListWidget(self)
        self._image_list.setMaximumHeight(192)
        self._image_list.setEnabled(False)
        self._image_list.itemSelectionChanged.connect(self._on_image_selection)
        body.addWidget(self._image_list)

        # Compact buttons: the app-wide `QPushButton { min-height: 28px }` beats a
        # setFixedHeight(), and #compact_input (min-height:0) lets them collapse to
        # a sliver. Force an exact height via a per-widget stylesheet (min == max),
        # keeping the themed background/border from the app-wide QPushButton rule.
        _COMPACT_BTN = "QPushButton { min-height: 24px; max-height: 24px; padding: 2px 12px; }"
        img_btns = QHBoxLayout()
        img_btns.setContentsMargins(0, 2, 0, 6)   # gap to the detail row below
        self._img_add = QPushButton(tr("Add images…"), self)
        self._img_add.setStyleSheet(_COMPACT_BTN)
        self._img_add.setIcon(load_folder_icon("folder_build"))
        self._img_add.setIconSize(QSize(14, 14))
        self._img_add.setEnabled(False)
        self._img_add.clicked.connect(self._pick_images)
        self._img_remove = QPushButton(tr("Remove"), self)
        self._img_remove.setStyleSheet(_COMPACT_BTN)
        self._img_remove.setEnabled(False)
        self._img_remove.clicked.connect(self._remove_selected_images)
        img_btns.addWidget(self._img_add)
        img_btns.addWidget(self._img_remove)
        img_btns.addStretch(1)
        body.addLayout(img_btns)

        # Detail = presets + a "Custom…" entry that reveals a raw 0–100 spinner.
        detail_row = QHBoxLayout()
        detail_row.addWidget(QLabel(tr("Image-gamut detail:"), self))
        self._detail_combo = NoScrollComboBox(self)
        for text, data in self._IMAGE_DETAIL:
            self._detail_combo.addItem(text, data)
        self._detail_combo.currentIndexChanged.connect(self._on_detail_changed)
        detail_row.addWidget(self._detail_combo, 1)
        self._detail_spin = NoScrollSpinBox(self)
        self._detail_spin.setRange(0, 100)
        self._detail_spin.setSuffix(" %")
        self._detail_spin.setFixedWidth(78)
        self._detail_spin.setToolTip(
            tr("Exact popularity filter — 0 keeps every colour; a lower value "
               "favours the main colours' saturation."))
        detail_row.addWidget(self._detail_spin)
        detail_row.addWidget(self._tip(
            tr("Image-gamut detail"),
            tr("How tightly the link hugs the colours in your images.\n\n"
            "• Favour the main colours — tightens the gamut around the image's "
            "popular colours so their saturation is held best (Argyll's suggested "
            "starting point).\n"
            "• Preserve all gradations — keeps even rarely-used colours, at the "
            "cost of compressing the gamut more.\n"
            "• Custom — set the exact popularity filter yourself (0–100).\n\n"
            "Only used when 'Optimise for specific images' is on. If unsure, leave "
            "it on 'Favour the main colours'."), 500), 0,
            Qt.AlignmentFlag.AlignVCenter)
        body.addLayout(detail_row)
        self._detail_combo.setEnabled(False)
        self._on_detail_changed()

        # 2 — abstract "tweak" profile.
        self._label_row(
            body, tr("Abstract 'tweak' profile (optional):"),
            tr("Abstract profile"),
            tr("An optional creative adjustment baked into the link — for example a "
            "profile that warms the whole image slightly or lifts contrast. Leave "
            "empty unless you've made one on purpose; it changes every colour the "
            "link touches."))
        self._abstract_field = self._file_row(
            body, tr("Pick an abstract profile…"), self._pick_abstract)

        # 3 — bake-in calibration.
        self._label_row(
            body, tr("Bake in calibration curves (optional):"),
            tr("Bake-in calibration"),
            tr("If your printer was calibrated to a known state (a .cal file), "
            "folding those curves into the link keeps the printer on that target "
            "without a separate calibration step. Only use the .cal that belongs to "
            "this exact printer/paper — the wrong one will skew every colour."))
        self._cal_field = self._file_row(
            body, tr("Pick a calibration (.cal) file…"), self._pick_cal)

        # 4 — 3DLUT export.
        self._lut3d_combo = self._combo_row(
            body, tr("Also export a 3DLUT:"), tr("3DLUT export"),
            tr("As well as the ICC device-link, write a 3D look-up table in a "
            "format that hardware boxes and some RIPs use. Leave it Off unless your "
            "workflow specifically asks for a .cube, eeColor or MadVR file."),
            self._LUT3D)

        # 5 — inverse-A2B gamut mode.
        self._inverse_cb = self._check_row(
            body, tr("Use inverse-table gamut mapping (advanced)"),
            tr("Inverse-table gamut mapping"),
            tr("Two ways of working out the mapping. The normal method is fine for "
            "almost everyone. The inverse-table method can occasionally place "
            "out-of-range colours a little more precisely on some printer profiles, "
            "at the cost of slower building. Try it only if you're comparing "
            "results."))

        # 6 — forced white point.
        self._white_cb = self._check_row(
            body, tr("Force source white to map exactly to paper white"),
            tr("Forced white point"),
            tr("Pins the brightest source colour to the paper's own white so a "
            "neutral white stays neutral, even if the paper is a little warm or "
            "cool. Helpful for clean whites on tinted art papers; usually not "
            "needed otherwise."))

        # Refit the dialog when the section is opened/closed so it grows if there
        # is room (and otherwise the scroll area takes over). The group toggles
        # itself on a title click; wrap that bound method to also refit.
        _orig_toggle = group.toggle
        def _toggle_and_refit():  # noqa: ANN202
            _orig_toggle()
            self._refit_height()
        group.toggle = _toggle_and_refit  # type: ignore[method-assign]
        form.addWidget(group)

    def _build_output(self, form: QVBoxLayout) -> None:
        form.addWidget(QLabel(tr("Save the device-link as:"), self))
        self._output = _OutputRow(
            self, ext_hint=".icc", on_change=self._refresh,
            initial_dir=_initial_dir(self._settings, self.TOOL_KEY),
            initial_name="")
        # Match the folder-icon browse buttons used elsewhere in this dialog
        # (the shared _OutputRow ships a text "Browse…" button).
        for b in self._output.findChildren(QPushButton):
            if "Browse" in b.text():
                b.setText("")
                b.setObjectName("browse")
                b.setFixedWidth(36)
                b.setIcon(load_folder_icon("folder_build"))
                b.setProperty("themed_folder_icon", "folder_build")
                b.setIconSize(QSize(20, 20))
        form.addWidget(self._output)

    def _on_image_toggled(self, on: bool) -> None:
        self._image_list.setEnabled(on)
        self._img_add.setEnabled(on)
        self._detail_combo.setEnabled(on)
        self._detail_spin.setEnabled(
            on and self._detail_combo.currentData() == self._CUSTOM_DETAIL)
        self._img_remove.setEnabled(on and bool(self._image_list.selectedItems()))
        if not on:
            self._image_paths = []
            self._image_list.clear()
        self._refresh()

    def _on_detail_changed(self) -> None:
        """Reveal the raw spinner only for 'Custom…'; otherwise mirror the preset's
        value in the (disabled) spinner so the effective filter is always visible."""
        custom = self._detail_combo.currentData() == self._CUSTOM_DETAIL
        self._detail_spin.setEnabled(custom and self._image_cb.isChecked())
        if not custom:
            self._detail_spin.blockSignals(True)
            self._detail_spin.setValue(int(self._detail_combo.currentData()))
            self._detail_spin.blockSignals(False)

    def _detail_filter_perc(self) -> float:
        d = self._detail_combo.currentData()
        return float(self._detail_spin.value() if d == self._CUSTOM_DETAIL else d)

    # --------------------------------------------------------------- pickers
    def _browse_file(self, caption: str, name_filter: str, *,
                     icc: bool = False, preview: bool = False) -> Path | None:
        """Open ChromIQ's own file dialog with sidebar shortcuts. ``icc`` adds the
        OS ICC/ICM profile folders; ``preview`` shows an image thumbnail pane."""
        extra = tuple(icc_profile_paths()) if icc else ()
        path = open_file_dialog(
            self, caption, name_filter,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
            extra_paths=extra, preview=preview)
        if not path:
            return None
        p = Path(path)
        _remember_dir(self._settings, self.TOOL_KEY, p.parent)
        return p

    def _pick_source(self) -> None:
        p = self._browse_file(tr("Choose source profile"), _ICC_FILTER, icc=True)
        if p:
            self._src_path = p
            self._src_field.setText(str(p))
            self._maybe_default_output_name()
            self._refresh()

    def _pick_destination(self) -> None:
        p = self._browse_file(tr("Choose printer profile"), _ICC_FILTER, icc=True)
        if p:
            self._set_destination(p)

    def _pick_abstract(self) -> None:
        p = self._browse_file(tr("Choose abstract profile"), _ICC_FILTER, icc=True)
        if p:
            self._abstract_path = p
            self._abstract_field.setText(str(p))

    def _pick_cal(self) -> None:
        p = self._browse_file(tr("Choose calibration file"), _CAL_FILTER)
        if p:
            self._cal_path = p
            self._cal_field.setText(str(p))

    def _pick_images(self) -> None:
        """Add one or more images to the gamut set (ChromIQ's own picker, with the
        OS image-folder sidebar shortcuts and a live preview pane)."""
        paths = open_files_dialog(
            self, tr("Choose images to optimise for"), _IMG_FILTER,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
            preview=True)
        if not paths:
            return
        added = False
        for s in paths:
            p = Path(s)
            if p not in self._image_paths:
                self._image_paths.append(p)
                # Show just the file name; keep the full path on the item so it
                # survives look-ups (and the tooltip shows where it came from).
                item = QListWidgetItem(p.name)
                item.setData(Qt.ItemDataRole.UserRole, str(p))
                item.setToolTip(str(p))
                self._image_list.addItem(item)
                added = True
        if added:
            _remember_dir(self._settings, self.TOOL_KEY, Path(paths[0]).parent)
            self._refresh()

    def _remove_selected_images(self) -> None:
        for item in self._image_list.selectedItems():
            p = Path(item.data(Qt.ItemDataRole.UserRole))
            if p in self._image_paths:
                self._image_paths.remove(p)
            self._image_list.takeItem(self._image_list.row(item))
        self._refresh()

    def _set_destination(self, p: Path) -> None:
        self._dst_path = p
        self._dst_field.setText(str(p))
        self._output._dir_edit.setText(str(p.parent))
        self._maybe_default_output_name()
        self._refresh()

    def _autofill_destination(self) -> None:
        try:
            from core.file_manager import FileManager
            icc = FileManager(self._settings).project().current_run().icc
        except Exception:  # noqa: BLE001 — best-effort convenience only
            return
        if icc and icc.exists():
            self._set_destination(icc)

    def _maybe_default_output_name(self) -> None:
        if self._output.name:
            return
        if self._dst_path and self._src_path:
            self._output._name_edit.setText(
                f"{self._dst_path.stem}-from-{self._src_path.stem}-devicelink")
        elif self._dst_path:
            self._output._name_edit.setText(f"{self._dst_path.stem}-devicelink")

    # --------------------------------------------------------------- run
    def _on_image_selection(self) -> None:
        self._img_remove.setEnabled(
            self._image_cb.isChecked() and bool(self._image_list.selectedItems()))

    def _can_run(self) -> bool:
        if self._image_cb.isChecked() and not self._image_paths:
            return False
        return (self._src_path is not None and self._dst_path is not None
                and self._output.is_complete())

    def _execute(self) -> None:
        if self._runner.is_running:
            self._log.appendPlainText(tr("[BUSY] Another operation is running — please wait."))
            self._finish(False)
            return

        assert self._src_path and self._dst_path
        out_dir = self._output.directory
        assert out_dir is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{self._output.name}.icc"

        if out.exists():
            choice = confirm(
                self, tr("Overwrite existing file?"),
                tr("'{name}' already exists in:\n  {folder}\n\nOverwrite it?"
                   ).format(name=out.name, folder=out.parent),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                self._finish(False)
                return

        self._log.clear()
        try:
            self._src_v2 = self._ensure_v2(self._src_path, tr("source"))
            self._dst_v2 = self._ensure_v2(self._dst_path, tr("destination"))
        except _ConversionError as exc:
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)
            return

        # If optimising for images, build their shared gamut first (tiffgamut),
        # then link; otherwise go straight to collink.
        if self._image_cb.isChecked() and self._image_paths:
            self._build_image_gamut_then_link(out)
        else:
            self._run_collink(out, src_gamut=None)

    def _build_image_gamut_then_link(self, out: Path) -> None:
        from workflow.tiffgamut_runner import TiffgamutParams, TiffgamutRunner
        self._log.appendPlainText(
            tr("Measuring the image's colours (this can take a moment)…"))
        tg = TiffgamutRunner(self._runner)
        self._gam_path: Path | None = None

        def _on_gamut_ready(_vol: float, _html: str, gam: str) -> None:
            self._gam_path = Path(gam) if gam else None

        tg.finished.connect(_on_gamut_ready)
        tg.error.connect(lambda msg: self._log.appendPlainText(f"[ERROR] {msg}"))

        def _on_done(code: int) -> None:
            if code != 0 or not self._gam_path or not self._gam_path.exists():
                self._log.appendPlainText(
                    tr("[ERROR] Could not analyse the image gamut — see messages above."))
                self._cleanup_temps()
                self._finish(False)
                return
            self._temp_files.append(self._gam_path)
            self._run_collink(out, src_gamut=self._gam_path)

        # Build the image gamut in CIECAM02 Jab appearance space (-pj) with the
        # same source viewing conditions the link uses (-c), so it lines up with
        # collink's perceptual gamut mapping; a popularity filter (-f) tightens
        # it around the images' main colours. This is Argyll's documented
        # image-dependent device-link recipe.
        tg.run(
            TiffgamutParams(
                image_path=self._image_paths[0], image_paths=self._image_paths,
                profile_path=self._src_v2, intent="p", appearance=True,
                viewcond=self._src_view_combo.currentData(),
                filter_perc=self._detail_filter_perc()),
            on_line=lambda ln: self._log_line(ln), on_finish=_on_done)

    def _run_collink(self, out: Path, src_gamut: Path | None) -> None:
        intent = self._intent_combo.currentData()
        src_vc = self._src_view_combo.currentData()
        dst_vc = self._dst_view_combo.currentData()
        params = CollinkParams(
            src_path=self._src_v2, dst_path=self._dst_v2, out_path=out,
            intent=intent, src_viewcond=src_vc, dst_viewcond=dst_vc,
            quality=self._quality_combo.currentData(),
            black_point_hack=self._black_cb.isChecked(),
            diagnostic=self._diag_cb.isChecked(),
            src_gamut=src_gamut,
            abstract=self._abstract_path,
            calibration=self._cal_path,
            lut3d=self._lut3d_combo.currentData(),
            inverse_gamut=self._inverse_cb.isChecked(),
            forced_white=self._white_cb.isChecked(),
            description=f"{out.stem} (ChromIQ device-link)",
            manufacturer="ChromIQ")
        self._log.appendPlainText(
            tr("Building device-link → {name}").format(name=out.name))

        def _on_finish(code: int) -> None:
            if code == 0 and out.exists():
                # Drop a portable "source space" sidecar next to the link (a copy
                # of the v2 source profile) so the "Apply device-link" tool knows
                # what colour space the link expects and can convert images into
                # it. Done before _cleanup_temps, since _src_v2 may be a tempfile.
                try:
                    import shutil
                    shutil.copyfile(self._src_v2, out.with_name(out.stem + ".source.icc"))
                except OSError:
                    pass
                self._settings.set("devicelink_last_link", str(out))
                self._cleanup_temps()
                self._log.appendPlainText(tr("[OK] Wrote {path}").format(path=out))
                _remember_dir(self._settings, self.TOOL_KEY, out.parent)
                self._finish(True)
            else:
                self._cleanup_temps()
                fail = self._collink.primary_failure()
                msg = fail[1] if fail else tr("collink failed — see messages above.")
                self._log.appendPlainText(f"[ERROR] {msg}")
                self._finish(False)

        self._collink.run(params, lambda ln: self._log_line(ln), _on_finish)

    def _log_line(self, line: str) -> None:
        text = line.rstrip()
        if text and not text.endswith("%"):     # swallow the % progress spam
            self._log.appendPlainText(text)
            self._log.ensureCursorVisible()

    def _ensure_v2(self, path: Path, role: str) -> Path:
        try:
            info = read_icc(path)
        except IccParseError as exc:
            raise _ConversionError(
                tr("The {role} profile isn't a readable ICC file: {err}"
                   ).format(role=role, err=exc))
        if not info.is_v4:
            return path
        self._log.appendPlainText(
            tr("Converting {role} profile from ICC v4 to v2…").format(role=role))
        try:
            v2 = to_v2(path)
        except NotConvertible:
            raise _ConversionError(
                tr("The {role} profile is an ICC v4 profile that ChromIQ can't "
                   "convert automatically (it isn't a standard matrix RGB profile). "
                   "Please supply a version-2 profile.").format(role=role))
        self._temp_files.append(v2)
        return v2

    def _cleanup_temps(self) -> None:
        for p in self._temp_files:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        self._temp_files.clear()

    def reject(self) -> None:  # noqa: D102
        self._cleanup_temps()
        super().reject()


class _ConversionError(Exception):
    """Raised internally when a profile can't be made v2-usable."""
