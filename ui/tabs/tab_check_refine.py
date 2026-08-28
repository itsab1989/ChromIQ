"""Tab 5: Check & Refine — profcheck quality assessment and guided re-measurement."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.file_manager import Run
from core.platform_paths import file_manager_name
from core.logger import get_logger
from core.preset_store import (
    load_presets as _load_tab_presets,
    reveal_in_file_manager,
    save_presets as _save_tab_presets,
    tab_dir,
)
from core.resource_path import resource_path
from ui.fade_scroll import FadeScrollArea
from ui.gamut_panel import GamutPanel
from ui.tab_header import TabHeader
from ui.tooltip_button import InfoDialog, TooltipButton
from ui.widgets import add_log_row, fit_log_height, GatedOption, NoScrollComboBox, NoScrollDoubleSpinBox, make_browse_button, open_file_dialog, replace_log_line, set_folder_icon, set_preset_icon, tint_dialog_primary
from ui.ti2_loader import (has_spectral_data, instrument_label, is_colormunki,
                          read_target_instrument, spectral_options_unavailable)

_TAB_COLOR = "#9f82ff"  # Check & Refine tab accent
from ui.styles import SPEC_VIOLET, TAB_COLORS
from workflow.profile_builder import _profile_dir as _get_profile_dir
from workflow.scanin_target import has_scanner_geometry
from workflow.profcheck_runner import (
    REFINE_DE_THRESHOLD,
    REFINE_START_OVER_RATIO,
    REFINE_START_OVER_STRIP_RATIO,
    ProfcheckParams,
    ProfcheckRunner,
    group_by_strip,
    parse_refine_strips,
    grade_display,
    quality_explanation,
    quality_grade,
    strips_to_refine,
    total_strip_count,
    write_quality_report,
    write_refine_strips,
)
from core.i18n import tr

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)

_ILLUMINANTS = [
    ("D50 (default)", "D50"),
    ("D50M2 (D50 + UV filter)", "D50M2"),
    ("D65 (daylight 6500 K)", "D65"),
    ("A (tungsten / incandescent)", "A"),
    ("C (daylight sim., older)", "C"),
    ("F5 (fluorescent CWF)", "F5"),
    ("F8 (fluorescent D50 sim.)", "F8"),
    ("F10 (fluorescent Ultralume)", "F10"),
]

_OBSERVERS = [
    ("1931 2° (default)", "1931_2"),
    ("1964 10°", "1964_10"),
    ("2015 2°", "2015_2"),
    ("2015 10°", "2015_10"),
    ("Shaw & Fairchild", "shaw"),
]


class TabCheckRefine(QWidget):
    """Step 5: check an ICC profile against .ti3 data and guide strip re-measurement."""

    guide_refinement_requested = pyqtSignal(Path, Path)  # (ti3_path, strips_file_path)
    preconditioning_requested  = pyqtSignal(Path)         # user clicked "Use as pre-conditioning profile"
    ti2_found                  = pyqtSignal(Path)         # emitted when a matching .ti2 exists next to the .ti3
    ti3_selected               = pyqtSignal(Path)         # emitted when the user manually browses a .ti3
    about_to_load_ti3          = pyqtSignal()             # emitted before state changes, for snapshot saving

    def __init__(
        self,
        runner: "ArgyllRunner",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner   = runner
        self._settings = settings
        self._checker  = ProfcheckRunner(runner)
        self._ti3_path: Path | None = None
        self._icc_path: Path | None = None
        self._last_result = None

        # Instrument detected from the loaded .ti3 (and whether it carries
        # spectral data), used to gate options profcheck can't apply.
        self._detected_instrument: str | None = None
        self._detected_has_spectral: bool = False
        self._instr_log_text: str | None = None
        # Options greyed out / stripped from the profcheck command while the gate
        # is active. EMPTY for now — populate once the incompatible options are
        # confirmed (e.g. the spectral-only options).
        self._gated_options: list[GatedOption] = []

        self._build_ui()
        self._restore_defaults()
        self._run_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _switch_mode(self, mode: str) -> None:
        if mode == "guided":
            self._stack.setCurrentIndex(0)
            self._guided_btn.setChecked(True)
            self._manual_btn.setChecked(False)
        else:
            self._stack.setCurrentIndex(1)
            self._guided_btn.setChecked(False)
            self._manual_btn.setChecked(True)
        self._nervous_box.setVisible(mode == "guided")
        self._apply_instrument_constraints()

    def _current_mode(self) -> str:
        return "guided" if self._stack.currentIndex() == 0 else "manual"

    def set_calibration_mode(self, enabled: bool) -> None:
        """Hide guided mode toggle and lock to manual when calibration mode is active."""
        self._mode_row_widget.setVisible(not enabled)
        if enabled:
            self._switch_mode("manual")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _update_run_btn(self) -> None:
        self._run_btn.setEnabled(
            self._ti3_path is not None and self._icc_path is not None
        )

    def set_paths(self, ti3: Path, icc: Path, propagate: bool = True) -> None:
        """Pre-populate both file fields after a successful profile build."""
        self._ti3_path = ti3
        self._icc_path = icc
        self._ti3_edit.setText(str(ti3))
        self._icc_edit.setText(str(icc))
        self._update_run_btn()
        self._gamut_panel.set_icc_path(icc)
        self._detect_instrument(ti3)
        if propagate:
            self._notify_ti2(ti3)

    def clear_files(self) -> None:
        self._ti3_path = None
        self._icc_path = None
        self._ti3_edit.clear()
        self._icc_edit.clear()
        self._update_run_btn()
        self._gamut_panel.set_icc_path(None)
        self._detect_instrument(None)

    @property
    def ti3_path(self) -> "Path | None":
        return self._ti3_path

    @property
    def icc_path(self) -> "Path | None":
        return self._icc_path

    @property
    def detected_instrument(self) -> str | None:
        """TARGET_INSTRUMENT read from the loaded .ti3, or None."""
        return self._detected_instrument

    @property
    def detected_has_spectral(self) -> bool:
        """Whether the loaded .ti3 contains spectral data."""
        return self._detected_has_spectral

    def shutdown_webengine(self) -> None:
        panel = getattr(self, "_gamut_panel", None)
        if panel is not None:
            panel.shutdown_webengine()

    def _notify_ti2(self, ti3: Path) -> None:
        ti2 = ti3.with_suffix(".ti2")
        if ti2.exists():
            self.ti2_found.emit(ti2)

    # ------------------------------------------------------------------
    # Instrument detection / option gating
    # ------------------------------------------------------------------

    def _detect_instrument(self, path: Path | None) -> None:
        """Read TARGET_INSTRUMENT + spectral flag from the loaded .ti3 and record it.

        Stores the result, shows a single replace-in-place log line, and re-applies
        the option gate. Pass ``path=None`` to reset (e.g. on clear).
        """
        instr = read_target_instrument(path) if path and path.exists() else None
        spectral = has_spectral_data(path) if path and path.exists() else False
        self._detected_instrument = instr
        self._detected_has_spectral = spectral

        msg = None
        if instr:
            spectral_note = "spectral data present" if spectral else "no spectral data"
            msg = f"Detected instrument: {instrument_label(instr)} ({spectral_note})."
        self._instr_log_text = replace_log_line(self._log, self._instr_log_text, msg)

        self._apply_instrument_constraints()

    def _gate_active(self) -> bool:
        """Whether incompatible options should be disabled for the loaded .ti3.

        The gated options (colprof ``-f`` FWA, illuminant, observer) are all
        computed from the spectral curve, so the gate now asks BOTH questions
        the docstring here used to promise for "later": is this an instrument
        whose light cannot excite optical brighteners (ColorMunki, and the CR30
        alongside it — same blue-pump white LED), and does this measurement
        carry spectra at all. A CR30 ``.ti3`` is colorimetric by design (#159),
        so the second test is what protects it even if the first cannot see the
        instrument name.
        """
        return spectral_options_unavailable(self._detected_instrument,
                                            self._detected_has_spectral)

    def _apply_instrument_constraints(self) -> None:
        """Grey out the gated option widgets according to the active gate."""
        active = self._gate_active()
        for opt in self._gated_options:
            for w in opt.widgets:
                w.setEnabled(not active)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(4)

        # Left panel — all existing check/refine controls
        left = QWidget(self)
        self._left_panel = left
        left.setFixedWidth(580)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 12, 16, 12)
        left_layout.setSpacing(8)

        left_layout.addWidget(TabHeader(
            tr("STEP 05 · SANITY CHECK"), tr("Check & refine"), "#9f82ff", left,
            tooltip_title=tr("Step 5 — Check the profile"),
            tooltip_body=tr(
                "On this final screen you sanity-check the profile you just built. "
                "ChromIQ compares the measurements (.ti3) against the profile "
                "(.icc) and reports how accurately the profile predicts your "
                "printer's behaviour, so you know whether to trust it for real "
                "prints.\n\n"
                "How to use this screen:\n"
                "• The .ti3 and .icc fields are pre-filled if you came from step 4. "
                "You can also load any older pair to re-check an existing profile.\n"
                "• Click “Analyse Profile Quality” to see the error report. Lower "
                "Delta-E (ΔE) values "
                "mean the profile is more accurate. As a rough rule: average ΔE "
                "under 2 is great, under 4 is fine for most uses, above 6 means "
                "something likely went wrong earlier (bad measurements, wrong "
                "paper, smudged patches).\n"
                "• When the report appears, “← Guide Me Through Refinement” at the "
                "bottom of it walks you through feeding those errors back into a "
                "slightly better profile. This is entirely optional — your profile "
                "is already usable.\n\n"
                "The 3D viewer on the right shows your profile's gamut — the volume "
                "of colours your printer can reproduce. Bigger and smoother is "
                "generally better; sharp dents usually indicate measurement issues.\n\n"
                "When you're happy: install the .icc and use it in your image "
                "editor's “soft-proofing” or print dialog."
            ),
        ))

        # --- Mode buttons ---
        _mode_font = QFont()
        _mode_font.setFamilies(["Menlo", "Consolas", "Courier New", "monospace"])
        _mode_font.setPointSize(11)
        _mode_font.setWeight(QFont.Weight.Bold)
        self._mode_row_widget = QWidget(self)
        mode_row = QHBoxLayout(self._mode_row_widget)
        mode_row.setContentsMargins(0, 0, 0, 0)
        self._guided_btn = QPushButton(tr("GUIDED"), self._mode_row_widget)
        self._guided_btn.setCheckable(True)
        self._guided_btn.setChecked(True)
        self._guided_btn.setObjectName("mode_btn")
        self._guided_btn.setFont(_mode_font)
        self._manual_btn = QPushButton(tr("MANUAL"), self._mode_row_widget)
        self._manual_btn.setCheckable(True)
        self._manual_btn.setObjectName("mode_btn")
        self._manual_btn.setFont(_mode_font)
        self._guided_btn.clicked.connect(lambda: self._switch_mode("guided"))
        self._manual_btn.clicked.connect(lambda: self._switch_mode("manual"))
        mode_row.addWidget(self._guided_btn)
        mode_row.addWidget(self._manual_btn)
        mode_row.addStretch()
        left_layout.addWidget(self._mode_row_widget)

        # ── File selection (shared, outside stack) ──────────────────────
        file_grp = QGroupBox(tr("Test Data && Profile"), self)
        file_grp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        fg = QVBoxLayout(file_grp)
        fg.setContentsMargins(8, 10, 8, 6)
        fg.setSpacing(4)

        ti3_row = QHBoxLayout()
        ti3_row.addWidget(QLabel(tr(".ti3 test data file:"), self))
        self._ti3_edit = QLineEdit(self)
        self._ti3_edit.setPlaceholderText(tr("Path to .ti3 measurement file"))
        self._ti3_edit.setReadOnly(True)
        ti3_row.addWidget(self._ti3_edit, stretch=1)
        ti3_browse = make_browse_button(self, tr("Browse for .ti3 file"), icon="folder_check")
        ti3_browse.clicked.connect(self._on_browse_ti3)
        ti3_row.addWidget(ti3_browse)
        fg.addLayout(ti3_row)

        icc_row = QHBoxLayout()
        icc_row.addWidget(QLabel(tr("ICC / ICM profile:"), self))
        self._icc_edit = QLineEdit(self)
        self._icc_edit.setPlaceholderText(tr("Path to .icc or .icm profile (auto-filled when .ti3 is loaded)"))
        self._icc_edit.setReadOnly(True)
        icc_row.addWidget(self._icc_edit, stretch=1)
        icc_browse = make_browse_button(self, tr("Browse for ICC/ICM profile"), icon="folder_check")
        icc_browse.clicked.connect(self._on_browse_icc)
        icc_row.addWidget(icc_browse)
        fg.addLayout(icc_row)

        left_layout.addWidget(file_grp)

        # ── Stacked panels ──────────────────────────────────────────────
        self._stack = QStackedWidget(self)
        self._guided_panel = self._make_guided_panel()
        self._manual_panel = self._make_manual_panel()
        self._stack.addWidget(self._guided_panel)
        self._stack.addWidget(self._manual_panel)
        left_layout.addWidget(self._stack, stretch=1)

        # Nervous block — guided mode only, sits directly above buttons
        nervous_box = QGroupBox(self)
        # Only override layout; let border + radius come from the global theme.
        nervous_box.setStyleSheet(
            "QGroupBox { margin-top: 0px; padding: 14px 8px 12px 8px; }"
        )
        nervous_layout = QVBoxLayout(nervous_box)
        nervous_layout.setContentsMargins(0, 0, 0, 0)
        nervous_layout.setSpacing(4)
        headline = QLabel(
            tr("Are you nervous<span style=\"color: {SPEC_VIOLET}; font-style: italic;\">?</span>").format(SPEC_VIOLET=SPEC_VIOLET),
            nervous_box,
        )
        headline.setTextFormat(Qt.TextFormat.RichText)
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setStyleSheet(
            "background: transparent;"
            " font-family: Georgia; font-size: 28px;"
        )
        nervous_layout.addWidget(headline)
        subtext = QLabel(tr("Your colors are in good hands."), nervous_box)
        subtext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtext.setStyleSheet(
            "color: #808080; background: transparent;"
            " font-family: Menlo; font-size: 9px; font-weight: 300;"
        )
        nervous_layout.addWidget(subtext)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(0, 6, 0, 0)
        bar_row.setSpacing(0)
        bar_row.addStretch()
        for _color in TAB_COLORS:
            _seg = QFrame(nervous_box)
            _seg.setFixedSize(22, 2)
            _seg.setStyleSheet(f"background-color: {_color}; border: none;")
            bar_row.addWidget(_seg)
        bar_row.addStretch()
        nervous_layout.addLayout(bar_row)
        self._nervous_box = nervous_box
        left_layout.addWidget(nervous_box)

        # ── Action buttons (outside stack) ──────────────────────────────
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton(tr("Analyse Profile Quality"), self)
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._on_run)
        self._save_defaults_btn = QPushButton(tr("Save as Defaults"), self)
        self._save_defaults_btn.setFixedHeight(36)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        left_layout.addLayout(btn_row)

        # ── Log (outside stack) ────────────────────────────────────────
        self._log = QPlainTextEdit(self)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        # Sized like every other log panel, and resizable with them (Basti:
        # "resizing them on one tab should resize them on all"). It used to be
        # pinned at 67 px — about four lines — which made it the one panel that
        # ignored both Knut's nine-line request and the user's own size.
        fit_log_height(self._log)
        self._log.setPlaceholderText(tr("profcheck output will appear here…"))
        # Breathing room above the log, so the buttons are not sitting on it.
        # Basti, 2026-08-07: measured WITH the real styling, the gap was 6px
        # here and 0 on Check & Refine, against 13px below the log — the
        # buttons looked stuck to it. Basti settled on 11px, and the value
        # here is the DELTA on top of this layout's own spacing — measured
        # with the real styling, because QSS padding only lands at polish.
        add_log_row(left_layout, self._log, left)

        splitter.addWidget(left)

        # Right panel — Gamut Volume viewer
        self._gamut_panel = GamutPanel(
            runner=self._runner, settings=self._settings, parent=self
        )
        splitter.addWidget(self._gamut_panel)

        # The left pane is pinned by setFixedWidth(580) above, so the RIGHT one
        # is the only pane that can absorb a narrow window. Without this the
        # gamut panel's 389 px minimum (448 in fr/es/nl/ru) plus the pinned 580
        # exceeds the 900 px MainWindow minimum and QSplitter OVERLAPS the two
        # panes — measured at 128 px in 12 of the 13 languages, with the
        # results box painted across the left pane's file rows. 200 matches the
        # effective right minimum on Print and Measure.
        self._gamut_panel.setMinimumWidth(200)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Guided panel
    # ------------------------------------------------------------------

    def _make_guided_panel(self) -> QWidget:
        scroll = FadeScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 4, 0)
        inner_layout.setSpacing(8)

        # ── Check options ───────────────────────────────────────────────
        opts_grp = QGroupBox(tr("Check Options"), inner)
        og = QVBoxLayout(opts_grp)
        og.setContentsMargins(8, 14, 8, 8)
        og.setSpacing(8)

        # Delta E formula (hidden)
        _de_w = QWidget(opts_grp)
        de_row = QHBoxLayout(_de_w)
        de_row.setContentsMargins(0, 0, 0, 0)
        de_row.addWidget(QLabel(tr("Delta E formula:"), _de_w))
        self._de_combo = NoScrollComboBox(_de_w)
        self._de_combo.addItem(tr("CIEDE2000 (recommended)"), "k")
        self._de_combo.addItem(tr("CIE76 (classic)"), "")
        self._de_combo.addItem(tr("CIE94"), "c")
        de_row.addWidget(self._de_combo)
        de_row.addStretch()
        de_row.addWidget(TooltipButton(
            tr("Delta E Formula"),
            tr("Selects the colour-difference formula used to compute errors.\n"
            "CIEDE2000 is the most perceptually accurate and is recommended\n"
            "for modern RGB printer profiling workflows."),
            _de_w,
        ))
        og.addWidget(_de_w)
        _de_w.setVisible(False)

        # Rendering intent (hidden)
        _intent_w = QWidget(opts_grp)
        intent_row = QHBoxLayout(_intent_w)
        intent_row.setContentsMargins(0, 0, 0, 0)
        intent_row.addWidget(QLabel(tr("Rendering intent:"), _intent_w))
        self._intent_combo = NoScrollComboBox(_intent_w)
        self._intent_combo.addItem(tr("Absolute colorimetric (default)"), "a")
        self._intent_combo.addItem(tr("Relative colorimetric"), "r")
        intent_row.addWidget(self._intent_combo)
        intent_row.addStretch()
        intent_row.addWidget(TooltipButton(
            tr("Rendering Intent"),
            tr("Absolute colorimetric checks the profile's absolute colour\n"
            "accuracy including white-point, which is the standard for\n"
            "printer profiling. Relative colorimetric normalises to\n"
            "the media white point."),
            _intent_w,
        ))
        og.addWidget(_intent_w)
        _intent_w.setVisible(False)

        # Sort by delta E (hidden)
        _sort_w = QWidget(opts_grp)
        sort_row = QHBoxLayout(_sort_w)
        sort_row.setContentsMargins(0, 0, 0, 0)
        self._sort_cb = QCheckBox(tr("Sort patches by ΔE (worst first)"), _sort_w)
        sort_row.addWidget(self._sort_cb)
        sort_row.addStretch()
        sort_row.addWidget(TooltipButton(
            tr("Sort by ΔE"),
            tr("Sorts profcheck output so the worst-performing patches appear\n"
            "first. Useful for quickly identifying problem areas."),
            _sort_w,
        ))
        og.addWidget(_sort_w)
        _sort_w.setVisible(False)

        # Verbosity (hidden)
        _verb_w = QWidget(opts_grp)
        verb_row = QHBoxLayout(_verb_w)
        verb_row.setContentsMargins(0, 0, 0, 0)
        verb_row.addWidget(QLabel(tr("Verbosity:"), _verb_w))
        self._verb_combo = NoScrollComboBox(_verb_w)
        self._verb_combo.addItem(tr("Per-patch (required for strip analysis)"), "2")
        self._verb_combo.addItem(tr("Summary only"), "1")
        verb_row.addWidget(self._verb_combo)
        verb_row.addStretch()
        verb_row.addWidget(TooltipButton(
            tr("Verbosity"),
            tr("Per-patch mode outputs each patch's individual ΔE value,\n"
            "which is required for strip-level analysis and guided\n"
            "refinement. Summary mode only shows average and peak errors."),
            _verb_w,
        ))
        og.addWidget(_verb_w)
        _verb_w.setVisible(False)

        def _on_verbosity_changed() -> None:
            per_patch = self._verb_combo.currentData() == "2"
            self._sort_cb.setEnabled(per_patch)
            if not per_patch:
                self._sort_cb.setChecked(False)

        self._verb_combo.currentIndexChanged.connect(_on_verbosity_changed)

        # Re-measurement threshold
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel(tr("Flag strips for re-measurement above ΔE:"), inner))
        self._threshold_spin = NoScrollDoubleSpinBox(inner)
        self._threshold_spin.setRange(0.5, 10.0)
        self._threshold_spin.setSingleStep(0.5)
        self._threshold_spin.setDecimals(1)
        self._threshold_spin.setValue(REFINE_DE_THRESHOLD)
        threshold_row.addWidget(self._threshold_spin)
        threshold_row.addStretch()
        threshold_row.addWidget(TooltipButton(
            tr("Re-measurement Threshold (ΔE)"),
            tr("Sets how sensitive the quality check is when deciding which strips\n"
            "need to be re-measured.\n\n"
            "A strip is flagged if any single patch on it has a colour error (ΔE)\n"
            "higher than this value.\n\n"
            "Lower value (e.g. 1.0) — more strict: flags strips with even small\n"
            "errors. Use this for critical colour work where accuracy matters most.\n\n"
            "Higher value (e.g. 3.0 or 4.0) — more lenient: only flags strips with\n"
            "clearly visible errors. Use this to limit re-measurement to the worst\n"
            "offenders only.\n\n"
            "The default of 2.0 is a good balance for most RGB printer profiles.\n"
            "Note: this does not affect the profcheck analysis itself — only which\n"
            "strips appear in the re-measurement recommendation."),
            inner,
        ))
        og.addLayout(threshold_row)

        inner_layout.addWidget(opts_grp)

        # ── Advanced options ────────────────────────────────────────────
        adv_grp = QGroupBox(tr("Advanced Options"), inner)
        adv_grp.setCheckable(True)
        adv_grp.setChecked(False)
        adv_layout = QVBoxLayout(adv_grp)
        adv_layout.setContentsMargins(8, 14, 8, 8)
        adv_layout.setSpacing(8)

        # FWA compensation
        fwa_row = QHBoxLayout()
        self._fwa_cb = QCheckBox(tr("FWA compensation (-f):"), inner)
        fwa_row.addWidget(self._fwa_cb)
        self._fwa_combo = NoScrollComboBox(inner)
        for label, val in _ILLUMINANTS:
            self._fwa_combo.addItem(label, val)
        self._fwa_combo.setEnabled(False)
        self._fwa_cb.toggled.connect(self._fwa_combo.setEnabled)
        fwa_row.addWidget(self._fwa_combo)
        fwa_row.addStretch()
        fwa_row.addWidget(TooltipButton(
            tr("FWA Compensation (-f)"),
            tr("Some papers contain optical brighteners (fluorescent whitening agents)\n"
            "that make the paper look extra white under certain lighting. This option\n"
            "compensates for that effect during the check.\n\n"
            "Only works if your .ti3 file contains spectral measurement data\n"
            "(not all instruments produce this). If you are unsure, leave it off.\n\n"
            "Set the illuminant to match the light source you view your prints under\n"
            "(D50 = standard daylight, D65 = cooler daylight)."),
            inner,
        ))
        adv_layout.addLayout(fwa_row)

        # Illuminant
        illum_row = QHBoxLayout()
        illum_row.addWidget(QLabel(tr("Illuminant (-i):"), inner))
        self._illum_combo = NoScrollComboBox(inner)
        for label, val in _ILLUMINANTS:
            self._illum_combo.addItem(label, val)
        illum_row.addWidget(self._illum_combo)
        illum_row.addStretch()
        illum_row.addWidget(TooltipButton(
            tr("Illuminant (-i)"),
            tr("Selects the light source used when converting spectral measurements\n"
            "to colour values. Only relevant if your .ti3 contains spectral data.\n\n"
            "D50 is the standard for print profiling and the right choice for most\n"
            "workflows. D65 is used in some video and photography contexts.\n\n"
            "Leave at D50 unless you have a specific reason to change it."),
            inner,
        ))
        adv_layout.addLayout(illum_row)

        # Observer
        obs_row = QHBoxLayout()
        obs_row.addWidget(QLabel(tr("CIE Observer (-o):"), inner))
        self._obs_combo = NoScrollComboBox(inner)
        for label, val in _OBSERVERS:
            self._obs_combo.addItem(label, val)
        obs_row.addWidget(self._obs_combo)
        obs_row.addStretch()
        obs_row.addWidget(TooltipButton(
            tr("CIE Observer (-o)"),
            tr("Defines the mathematical model used to represent how the human eye\n"
            "sees colour.\n\n"
            "1931 2° is the international standard for print and ICC profiling\n"
            "and the correct choice for virtually all printer profiling work.\n\n"
            "The 1964 10° observer can be used for large-area colour matching,\n"
            "but is rarely needed here. Leave at 1931 2° unless specifically\n"
            "requested by your colour management workflow."),
            inner,
        ))
        adv_layout.addLayout(obs_row)

        # Prune
        prune_row = QHBoxLayout()
        self._prune_cb = QCheckBox(tr("Prune .ti3 to patches with ΔE ≤ (-P):"), inner)
        prune_row.addWidget(self._prune_cb)
        self._prune_spin = NoScrollDoubleSpinBox(inner)
        self._prune_spin.setRange(0.0, 20.0)
        self._prune_spin.setSingleStep(0.5)
        self._prune_spin.setDecimals(2)
        self._prune_spin.setValue(3.0)
        self._prune_spin.setEnabled(False)
        self._prune_cb.toggled.connect(self._prune_spin.setEnabled)
        prune_row.addWidget(self._prune_spin)
        prune_row.addWidget(QLabel(tr("ΔE"), inner))
        prune_row.addStretch()
        prune_row.addWidget(TooltipButton(
            tr("Prune .ti3 (-P)"),
            tr("Creates a reduced copy of your .ti3 file containing only patches\n"
            "whose colour error is at or below the threshold you set.\n\n"
            "Useful if a small number of badly measured patches are pulling\n"
            "the profile down. Pruning them out lets you build a cleaner\n"
            "profile from the remaining good patches — at the cost of\n"
            "having fewer data points overall.\n\n"
            "The pruned file is saved next to the original .ti3 and can be\n"
            "loaded directly in the Build Profile tab."),
            inner,
        ))
        adv_layout.addLayout(prune_row)

        # X3DOM visualisation
        x3d_row = QHBoxLayout()
        self._x3dom_cb = QCheckBox(tr("Create X3DOM 3D visualisation (-w)"), inner)
        x3d_row.addWidget(self._x3dom_cb)
        x3d_row.addStretch()
        x3d_row.addWidget(TooltipButton(
            tr("X3DOM Visualisation (-w)"),
            tr("Generates an interactive 3D visualisation of your profile's colour\n"
            "errors and saves it as an HTML file next to your .ti3.\n\n"
            "Open the .x3d.html file in any modern web browser to explore a\n"
            "3D diagram showing where errors are largest — useful for seeing\n"
            "which parts of the colour gamut your profile handles well and\n"
            "which areas need improvement."),
            inner,
        ))
        adv_layout.addLayout(x3d_row)

        inner_layout.addWidget(adv_grp)
        adv_grp.setVisible(False)
        inner_layout.addStretch()

        scroll.setWidget(inner)
        return scroll

    # ------------------------------------------------------------------
    # Manual panel
    # ------------------------------------------------------------------

    def _make_manual_panel(self) -> QWidget:
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Presets group
        presets_grp = QGroupBox(tr("Presets"), container)
        presets_row = QHBoxLayout(presets_grp)
        presets_row.setContentsMargins(8, 4, 8, 8)
        presets_row.addWidget(QLabel(tr("Select preset:"), container))
        self._m_preset_combo = NoScrollComboBox(container)
        self._m_preset_combo.addItem(tr("none"), userData=None)
        presets_row.addWidget(self._m_preset_combo, stretch=1)
        self._m_preset_add_btn = QPushButton(container)
        self._m_preset_add_btn.setObjectName("icon_btn")
        self._m_preset_add_btn.setFixedSize(28, 28)
        set_preset_icon(self._m_preset_add_btn, "plus")
        self._m_preset_add_btn.setToolTip(tr("Save current settings as a new preset"))
        self._m_preset_del_btn = QPushButton(container)
        self._m_preset_del_btn.setObjectName("icon_btn")
        self._m_preset_del_btn.setFixedSize(28, 28)
        set_preset_icon(self._m_preset_del_btn, "minus")
        self._m_preset_del_btn.setToolTip(tr("Delete selected preset"))
        self._m_preset_del_btn.setEnabled(False)
        self._m_preset_reveal_btn = QPushButton(container)
        self._m_preset_reveal_btn.setObjectName("icon_btn")
        self._m_preset_reveal_btn.setFixedSize(28, 28)
        set_folder_icon(self._m_preset_reveal_btn, "folder_check")
        self._m_preset_reveal_btn.setToolTip(
            tr("Open this tab's presets folder in {manager}.\n"
            "Each preset is a plain .json file — copy one to a colleague\n"
            "and they can drop it into their own folder to share.").format(manager=file_manager_name())
        )
        self._m_preset_reveal_btn.clicked.connect(
            lambda: reveal_in_file_manager(tab_dir("check_refine"))
        )
        presets_row.addWidget(self._m_preset_add_btn)
        presets_row.addWidget(self._m_preset_del_btn)
        presets_row.addWidget(self._m_preset_reveal_btn)
        presets_row.addWidget(TooltipButton(
            tr("Manual Presets"),
            tr("Save and recall named snapshots of all Manual mode settings.\n\n"
            "  +  Save current parameter values as a new named preset.\n"
            "  −  Delete the currently selected preset.\n"
            "  ▢  Open this tab's presets folder in {manager}.\n\n"
            "Select a preset from the dropdown to instantly restore all\n"
            "values. The Default entry always resets to built-in defaults.\n\n"
            "Presets are stored as plain .json files — one per preset —\n"
            "in a ChromIQ folder under your system's Preferences / AppData\n"
            "/ config location. Use the folder button (▢) on the right of\n"
            "the preset row to open it. To share a preset, copy the .json\n"
            "out of that folder and send it to a colleague; to install a\n"
            "shared preset, drop the .json into the matching folder on the\n"
            "target machine and ChromIQ will pick it up on the next launch.\n\n"
            "Presets persist between sessions.").format(manager=file_manager_name()),
            container,
            min_width=600,
        ))
        self._m_preset_combo.currentIndexChanged.connect(self._on_m_preset_selected)
        self._m_preset_add_btn.clicked.connect(self._on_m_preset_save)
        self._m_preset_del_btn.clicked.connect(self._on_m_preset_delete)
        cl.addWidget(presets_grp)
        cl.addSpacing(8)

        scroll = FadeScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)

        # ── Check Options ───────────────────────────────────────────────
        m_opts_grp = QGroupBox(tr("Check Options"), inner)
        mog = QVBoxLayout(m_opts_grp)
        mog.setContentsMargins(8, 14, 8, 8)
        mog.setSpacing(8)

        de_row = QHBoxLayout()
        de_row.addWidget(QLabel(tr("Delta E formula:"), inner))
        self._m_de_combo = NoScrollComboBox(inner)
        self._m_de_combo.addItem(tr("CIEDE2000 (recommended)"), "k")
        self._m_de_combo.addItem(tr("CIE76 (classic)"), "")
        self._m_de_combo.addItem(tr("CIE94"), "c")
        self._m_de_combo.setObjectName("compact_input")
        self._m_de_combo.style().unpolish(self._m_de_combo)
        self._m_de_combo.style().polish(self._m_de_combo)
        de_row.addWidget(self._m_de_combo)
        de_row.addStretch()
        de_row.addWidget(TooltipButton(
            tr("Delta E Formula"),
            tr("Selects the colour-difference formula used to compute errors.\n"
            "CIEDE2000 is the most perceptually accurate and is recommended\n"
            "for modern RGB printer profiling workflows."),
            inner,
        ))
        mog.addLayout(de_row)

        intent_row = QHBoxLayout()
        intent_row.addWidget(QLabel(tr("Rendering intent:"), inner))
        self._m_intent_combo = NoScrollComboBox(inner)
        self._m_intent_combo.addItem(tr("Absolute colorimetric (default)"), "a")
        self._m_intent_combo.addItem(tr("Relative colorimetric"), "r")
        self._m_intent_combo.setObjectName("compact_input")
        self._m_intent_combo.style().unpolish(self._m_intent_combo)
        self._m_intent_combo.style().polish(self._m_intent_combo)
        intent_row.addWidget(self._m_intent_combo)
        intent_row.addStretch()
        intent_row.addWidget(TooltipButton(
            tr("Rendering Intent"),
            tr("Absolute colorimetric checks the profile's absolute colour\n"
            "accuracy including white-point, which is the standard for\n"
            "printer profiling. Relative colorimetric normalises to\n"
            "the media white point."),
            inner,
        ))
        mog.addLayout(intent_row)

        m_sort_row = QHBoxLayout()
        self._m_sort_cb = QCheckBox(tr("Sort patches by ΔE (worst first)"), inner)
        m_sort_row.addWidget(self._m_sort_cb)
        m_sort_row.addStretch()
        m_sort_row.addWidget(TooltipButton(
            tr("Sort by ΔE"),
            tr("Sorts profcheck output so the worst-performing patches appear\n"
            "first. Useful for quickly identifying problem areas."),
            inner,
        ))
        mog.addLayout(m_sort_row)

        verb_row = QHBoxLayout()
        verb_row.addWidget(QLabel(tr("Verbosity:"), inner))
        self._m_verb_combo = NoScrollComboBox(inner)
        self._m_verb_combo.addItem(tr("Per-patch (required for strip analysis)"), "2")
        self._m_verb_combo.addItem(tr("Summary only"), "1")
        self._m_verb_combo.setObjectName("compact_input")
        self._m_verb_combo.style().unpolish(self._m_verb_combo)
        self._m_verb_combo.style().polish(self._m_verb_combo)
        verb_row.addWidget(self._m_verb_combo)
        verb_row.addStretch()
        verb_row.addWidget(TooltipButton(
            tr("Verbosity"),
            tr("Per-patch mode outputs each patch's individual ΔE value,\n"
            "which is required for strip-level analysis and guided\n"
            "refinement. Summary mode only shows average and peak errors."),
            inner,
        ))
        mog.addLayout(verb_row)

        m_threshold_row = QHBoxLayout()
        m_threshold_row.addWidget(QLabel(tr("Flag strips for re-measurement above ΔE:"), inner))
        self._m_threshold_spin = NoScrollDoubleSpinBox(inner)
        self._m_threshold_spin.setRange(0.5, 10.0)
        self._m_threshold_spin.setSingleStep(0.5)
        self._m_threshold_spin.setDecimals(1)
        self._m_threshold_spin.setValue(REFINE_DE_THRESHOLD)
        self._m_threshold_spin.setObjectName("compact_input")
        self._m_threshold_spin.style().unpolish(self._m_threshold_spin)
        self._m_threshold_spin.style().polish(self._m_threshold_spin)
        m_threshold_row.addWidget(self._m_threshold_spin)
        m_threshold_row.addStretch()
        m_threshold_row.addWidget(TooltipButton(
            tr("Re-measurement Threshold (ΔE)"),
            tr("Sets how sensitive the quality check is when deciding which strips\n"
            "need to be re-measured.\n\n"
            "A strip is flagged if any single patch on it has a colour error (ΔE)\n"
            "higher than this value.\n\n"
            "Lower value (e.g. 1.0) — more strict: flags strips with even small\n"
            "errors. Use this for critical colour work where accuracy matters most.\n\n"
            "Higher value (e.g. 3.0 or 4.0) — more lenient: only flags strips with\n"
            "clearly visible errors. Use this to limit re-measurement to the worst\n"
            "offenders only.\n\n"
            "The default of 2.0 is a good balance for most RGB printer profiles.\n"
            "Note: this does not affect the profcheck analysis itself — only which\n"
            "strips appear in the re-measurement recommendation."),
            inner,
        ))
        mog.addLayout(m_threshold_row)

        layout.addWidget(m_opts_grp)

        # ── Advanced Options ────────────────────────────────────────────
        m_adv_grp = QGroupBox(tr("Advanced Options"), inner)
        m_adv_grp.setCheckable(True)
        m_adv_grp.setChecked(False)
        madv = QVBoxLayout(m_adv_grp)
        madv.setContentsMargins(8, 14, 8, 8)
        madv.setSpacing(8)

        m_fwa_row = QHBoxLayout()
        self._m_fwa_cb = QCheckBox(tr("FWA compensation (-f):"), inner)
        m_fwa_row.addWidget(self._m_fwa_cb)
        self._m_fwa_combo = NoScrollComboBox(inner)
        for label, val in _ILLUMINANTS:
            self._m_fwa_combo.addItem(label, val)
        self._m_fwa_combo.setEnabled(False)
        self._m_fwa_cb.toggled.connect(self._m_fwa_combo.setEnabled)
        self._m_fwa_combo.setObjectName("compact_input")
        self._m_fwa_combo.style().unpolish(self._m_fwa_combo)
        self._m_fwa_combo.style().polish(self._m_fwa_combo)
        m_fwa_row.addWidget(self._m_fwa_combo)
        m_fwa_row.addStretch()
        m_fwa_row.addWidget(TooltipButton(
            tr("FWA Compensation (-f)"),
            tr("Some papers contain optical brighteners (fluorescent whitening agents)\n"
            "that make the paper look extra white under certain lighting. This option\n"
            "compensates for that effect during the check.\n\n"
            "Only works if your .ti3 file contains spectral measurement data\n"
            "(not all instruments produce this). If you are unsure, leave it off.\n\n"
            "Set the illuminant to match the light source you view your prints under\n"
            "(D50 = standard daylight, D65 = cooler daylight)."),
            inner,
        ))
        madv.addLayout(m_fwa_row)

        m_illum_row = QHBoxLayout()
        m_illum_row.addWidget(QLabel(tr("Illuminant (-i):"), inner))
        self._m_illum_combo = NoScrollComboBox(inner)
        for label, val in _ILLUMINANTS:
            self._m_illum_combo.addItem(label, val)
        self._m_illum_combo.setObjectName("compact_input")
        self._m_illum_combo.style().unpolish(self._m_illum_combo)
        self._m_illum_combo.style().polish(self._m_illum_combo)
        m_illum_row.addWidget(self._m_illum_combo)
        m_illum_row.addStretch()
        m_illum_row.addWidget(TooltipButton(
            tr("Illuminant (-i)"),
            tr("Selects the light source used when converting spectral measurements\n"
            "to colour values. Only relevant if your .ti3 contains spectral data.\n\n"
            "D50 is the standard for print profiling and the right choice for most\n"
            "workflows. D65 is used in some video and photography contexts.\n\n"
            "Leave at D50 unless you have a specific reason to change it."),
            inner,
        ))
        madv.addLayout(m_illum_row)

        m_obs_row = QHBoxLayout()
        m_obs_row.addWidget(QLabel(tr("CIE Observer (-o):"), inner))
        self._m_obs_combo = NoScrollComboBox(inner)
        for label, val in _OBSERVERS:
            self._m_obs_combo.addItem(label, val)
        self._m_obs_combo.setObjectName("compact_input")
        self._m_obs_combo.style().unpolish(self._m_obs_combo)
        self._m_obs_combo.style().polish(self._m_obs_combo)
        m_obs_row.addWidget(self._m_obs_combo)
        m_obs_row.addStretch()
        m_obs_row.addWidget(TooltipButton(
            tr("CIE Observer (-o)"),
            tr("Defines the mathematical model used to represent how the human eye\n"
            "sees colour.\n\n"
            "1931 2° is the international standard for print and ICC profiling\n"
            "and the correct choice for virtually all printer profiling work.\n\n"
            "The 1964 10° observer can be used for large-area colour matching,\n"
            "but is rarely needed here. Leave at 1931 2° unless specifically\n"
            "requested by your colour management workflow."),
            inner,
        ))
        madv.addLayout(m_obs_row)

        m_prune_row = QHBoxLayout()
        self._m_prune_cb = QCheckBox(tr("Prune .ti3 to patches with ΔE ≤ (-P):"), inner)
        m_prune_row.addWidget(self._m_prune_cb)
        self._m_prune_spin = NoScrollDoubleSpinBox(inner)
        self._m_prune_spin.setRange(0.0, 20.0)
        self._m_prune_spin.setSingleStep(0.5)
        self._m_prune_spin.setDecimals(2)
        self._m_prune_spin.setValue(3.0)
        self._m_prune_spin.setEnabled(False)
        self._m_prune_cb.toggled.connect(self._m_prune_spin.setEnabled)
        self._m_prune_spin.setObjectName("compact_input")
        self._m_prune_spin.style().unpolish(self._m_prune_spin)
        self._m_prune_spin.style().polish(self._m_prune_spin)
        m_prune_row.addWidget(self._m_prune_spin)
        m_prune_row.addWidget(QLabel(tr("ΔE"), inner))
        m_prune_row.addStretch()
        m_prune_row.addWidget(TooltipButton(
            tr("Prune .ti3 (-P)"),
            tr("Creates a reduced copy of your .ti3 file containing only patches\n"
            "whose colour error is at or below the threshold you set.\n\n"
            "Useful if a small number of badly measured patches are pulling\n"
            "the profile down. Pruning them out lets you build a cleaner\n"
            "profile from the remaining good patches — at the cost of\n"
            "having fewer data points overall.\n\n"
            "The pruned file is saved next to the original .ti3 and can be\n"
            "loaded directly in the Build Profile tab."),
            inner,
        ))
        madv.addLayout(m_prune_row)

        m_x3d_row = QHBoxLayout()
        self._m_x3dom_cb = QCheckBox(tr("Create X3DOM 3D visualisation (-w)"), inner)
        m_x3d_row.addWidget(self._m_x3dom_cb)
        m_x3d_row.addStretch()
        m_x3d_row.addWidget(TooltipButton(
            tr("X3DOM Visualisation (-w)"),
            tr("Generates an interactive 3D visualisation of your profile's colour\n"
            "errors and saves it as an HTML file next to your .ti3.\n\n"
            "Open the .x3d.html file in any modern web browser to explore a\n"
            "3D diagram showing where errors are largest — useful for seeing\n"
            "which parts of the colour gamut your profile handles well and\n"
            "which areas need improvement."),
            inner,
        ))
        madv.addLayout(m_x3d_row)

        layout.addWidget(m_adv_grp)
        layout.addStretch()

        scroll.setWidget(inner)
        cl.addWidget(scroll, stretch=1)
        return container

    # ------------------------------------------------------------------
    # Manual preset helpers (Check & Refine tab)
    # ------------------------------------------------------------------

    def _m_load_presets(self) -> dict:
        return _load_tab_presets("check_refine", self._settings)

    def _m_save_presets(self, presets: dict) -> None:
        _save_tab_presets("check_refine", presets)

    def _m_populate_preset_combo(self, presets: dict, select_name: str | None = None) -> None:
        self._m_preset_combo.blockSignals(True)
        self._m_preset_combo.clear()
        self._m_preset_combo.addItem(tr("none"), userData=None)
        for name in presets:
            self._m_preset_combo.addItem(name, userData=name)
        if select_name is not None:
            idx = self._m_preset_combo.findText(select_name)
            if idx >= 0:
                self._m_preset_combo.setCurrentIndex(idx)
        self._m_preset_combo.blockSignals(False)
        self._m_preset_del_btn.setEnabled(self._m_preset_combo.currentIndex() > 0)

    def _m_collect_preset_data(self) -> dict:
        return {
            "de_formula":    self._m_de_combo.currentData() or "k",
            "intent":        self._m_intent_combo.currentData() or "a",
            "sort":          self._m_sort_cb.isChecked(),
            "verbosity":     self._m_verb_combo.currentData() or "2",
            "fwa_enabled":   self._m_fwa_cb.isChecked(),
            "fwa_illum":     self._m_fwa_combo.currentData() or "D50",
            "illum":         self._m_illum_combo.currentData() or "D50",
            "observer":      self._m_obs_combo.currentData() or "1931_2",
            "prune_enabled": self._m_prune_cb.isChecked(),
            "prune_value":   self._m_prune_spin.value(),
            "x3dom":         self._m_x3dom_cb.isChecked(),
        }

    def _m_apply_preset_data(self, data: dict) -> None:
        def _set(combo: NoScrollComboBox, key: str, default: str) -> None:
            idx = combo.findData(data.get(key, default))
            if idx >= 0:
                combo.setCurrentIndex(idx)
        _set(self._m_de_combo,     "de_formula", "k")
        _set(self._m_intent_combo, "intent",     "a")
        self._m_sort_cb.setChecked(bool(data.get("sort", True)))
        _set(self._m_verb_combo,   "verbosity",  "2")
        self._m_fwa_cb.setChecked(bool(data.get("fwa_enabled", False)))
        _set(self._m_fwa_combo,    "fwa_illum",  "D50")
        self._m_fwa_combo.setEnabled(self._m_fwa_cb.isChecked())
        _set(self._m_illum_combo,  "illum",      "D50")
        _set(self._m_obs_combo,    "observer",   "1931_2")
        self._m_prune_cb.setChecked(bool(data.get("prune_enabled", False)))
        try:
            self._m_prune_spin.setValue(float(data.get("prune_value", 3.0)))
        except (TypeError, ValueError):
            pass
        self._m_prune_spin.setEnabled(self._m_prune_cb.isChecked())
        self._m_x3dom_cb.setChecked(bool(data.get("x3dom", False)))

    def _on_m_preset_selected(self, index: int) -> None:
        self._m_preset_del_btn.setEnabled(index > 0)
        s = self._settings
        if index == 0:
            def _set(combo: NoScrollComboBox, key: str, default: str) -> None:
                idx = combo.findData(s.get(key, default))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            _set(self._m_de_combo,     "manual2_profcheck_de_formula", "k")
            _set(self._m_intent_combo, "manual2_profcheck_intent",     "a")
            self._m_sort_cb.setChecked(bool(s.get("manual2_profcheck_sort", True)))
            _set(self._m_verb_combo,   "manual2_profcheck_verbosity",  "2")
            self._m_fwa_cb.setChecked(bool(s.get("manual2_profcheck_fwa_enabled", False)))
            _set(self._m_fwa_combo,    "manual2_profcheck_fwa_illum",  "D50")
            self._m_fwa_combo.setEnabled(self._m_fwa_cb.isChecked())
            _set(self._m_illum_combo,  "manual2_profcheck_illum",      "D50")
            _set(self._m_obs_combo,    "manual2_profcheck_observer",   "1931_2")
            self._m_prune_cb.setChecked(bool(s.get("manual2_profcheck_prune_enabled", False)))
            try:
                self._m_prune_spin.setValue(float(s.get("manual2_profcheck_prune_value", 3.0)))
            except (TypeError, ValueError):
                pass
            self._m_prune_spin.setEnabled(self._m_prune_cb.isChecked())
            self._m_x3dom_cb.setChecked(bool(s.get("manual2_profcheck_x3dom", False)))
        else:
            name = self._m_preset_combo.currentData()
            presets = self._m_load_presets()
            self._m_apply_preset_data(presets.get(name, {}))

    def _on_m_preset_save(self) -> None:
        data = self._m_collect_preset_data()
        dlg = QInputDialog(self)
        dlg.setWindowTitle(tr("Save Preset"))
        dlg.setLabelText(
            tr("Give this preset a name.\n"
            "All current Manual mode settings will be saved under that name\n"
            "and can be recalled at any time from the preset list.")
        )
        dlg.setMinimumWidth(460)
        if not dlg.exec():
            return
        name = dlg.textValue().strip()
        if not name:
            return
        presets = self._m_load_presets()
        presets[name] = data
        self._m_save_presets(presets)
        self._m_populate_preset_combo(presets, select_name=name)

    def _on_m_preset_delete(self) -> None:
        name = self._m_preset_combo.currentText()
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Delete Preset"))
        dlg.setMinimumWidth(460)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(20, 20, 20, 16)
        heading = QLabel(tr("Delete the preset \"{name}\"?").format(name=name), dlg)
        heading.setStyleSheet("font-weight: bold;")
        heading.setWordWrap(True)
        dlg_layout.addWidget(heading)
        info = QLabel(
            tr("All parameter values saved in this preset will be permanently removed. "
            "This cannot be undone."),
            dlg,
        )
        info.setWordWrap(True)
        dlg_layout.addWidget(info)
        bb = QDialogButtonBox(dlg)
        bb.addButton(tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        del_btn = bb.addButton(tr("Delete"), QDialogButtonBox.ButtonRole.AcceptRole)
        del_btn.setObjectName("primary")
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        dlg_layout.addWidget(bb)
        tint_dialog_primary(dlg, _TAB_COLOR)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        presets = self._m_load_presets()
        presets.pop(name, None)
        self._m_save_presets(presets)
        self._m_populate_preset_combo(presets)

    # ------------------------------------------------------------------
    # File selection
    # ------------------------------------------------------------------

    def _on_browse_ti3(self) -> None:
        path = open_file_dialog(
            self, "Select .ti3 file", "Test chart data (*.ti3)",
            extra_path=self._settings.get("custom_output_path", ""),
        )
        if not path:
            return
        from ui.ti2_loader import resolve_ti3
        # External / old-flat-layout .ti3s get imported into a fresh project
        # (Project.create writes the "Where are my files.txt" README too).
        # Inside an existing project, resolve_ti3 returns the path unchanged.
        resolved = resolve_ti3(self, Path(path), self._settings)
        if resolved is None:
            return
        self.about_to_load_ti3.emit()
        self._ti3_path = resolved
        self._ti3_edit.setText(str(resolved))
        self._auto_fill_icc(resolved)
        self._notify_ti2(resolved)
        self._update_run_btn()
        self._detect_instrument(resolved)
        self.ti3_selected.emit(resolved)

    def _on_browse_icc(self) -> None:
        path = open_file_dialog(
            self, "Select ICC / ICM profile", "ICC profiles (*.icc *.icm)",
            extra_path=self._settings.get("custom_output_path", ""),
        )
        if path:
            self._icc_path = Path(path)
            self._icc_edit.setText(str(self._icc_path))
            self._update_run_btn()
            self._gamut_panel.set_icc_path(self._icc_path)

    def _auto_fill_icc(self, ti3: Path) -> None:
        """Try to find a matching ICC/ICM in the same folder.

        Prefers the run's refinement-merged profile (merged.icc) when one was
        built, falling back to the same-stem profile (chart.icc / chart.icm).
        """
        candidates: list[Path] = []
        run = Run.for_dir(ti3.parent)
        if run.merged_icc.exists():
            candidates.append(run.merged_icc)
        candidates += [ti3.with_suffix(ext) for ext in (".icc", ".icm")]
        for candidate in candidates:
            if candidate.exists():
                self._icc_path = candidate
                self._icc_edit.setText(str(candidate))
                self._update_run_btn()
                self._gamut_panel.set_icc_path(candidate)
                return
        # No match — clear ICC field and warn
        self._icc_path = None
        self._icc_edit.clear()
        self._update_run_btn()
        self._gamut_panel.set_icc_path(None)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self,
            tr("Profile Not Found"),
            tr("No matching .icc or .icm file was found in:\n{folder}\n\n"
               "Please browse for the profile file manually.").format(folder=ti3.parent),
        )

    # ------------------------------------------------------------------
    # Run / stop
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        if not self._ti3_path:
            self._log.appendPlainText("[ERROR] No .ti3 file selected.")
            return
        if not self._icc_path:
            self._log.appendPlainText("[ERROR] No ICC/ICM profile selected.")
            return
        if self._runner.is_running:
            return
        if not self._warn_converted_measurement():
            return

        params = self._collect_params()
        self._log.clear()
        self._last_result = None
        self._run_btn.setEnabled(False)

        self._checker.run(
            params,
            on_line=self._on_log_line,
            on_finish=self._on_done,
        )

    def _warn_converted_measurement(self) -> bool:
        """The §2b trap of verification_printing_and_target.md (test T13).

        profcheck pushes the chart's device values forward through the
        profile, so those values must be what was actually printed. A sheet
        printed with "Colour" = "Through this run's profile" was converted at
        print time — its chart file still holds the unconverted values, so
        the check would produce confident, meaningless figures and nothing
        downstream could tell. Warn, and let Cancel be the default. Returns
        True when the check may proceed.
        """
        try:
            from workflow.verification_print import (COLOUR_THROUGH,
                                                     read_print_record)
            rec = read_print_record(self._ti3_path) if self._ti3_path else None
        except Exception:      # noqa: BLE001 — the guard must never block a check
            log.warning("Could not read the print record", exc_info=True)
            return True
        if not rec or rec.get("colour") != COLOUR_THROUGH:
            return True
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        title, body = M.M_CM_PROFCHECK_CONVERTED.render()
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setWindowTitle(title)
        # House pattern (every other §M window): the title as the bold
        # setText line, the body as informative text — this window had the
        # body alone, so it opened with no headline at all.
        dlg.setText(title)
        dlg.setInformativeText(body)
        anyway = dlg.addButton(tr("Run the check anyway"),
                               QMessageBox.ButtonRole.DestructiveRole)
        cancel = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(cancel)
        dlg.exec()
        return dlg.clickedButton() is anyway

    def _on_log_line(self, line: str) -> None:
        self._log.appendPlainText(line)
        self._log.ensureCursorVisible()

    def _on_done(self, code: int) -> None:
        self._run_btn.setEnabled(True)

        # profcheck exits with 1 when it detects colour errors — that is normal.
        # Only treat it as a hard failure if we also got no parseable output.
        result = self._checker.parse_results()
        self._last_result = result

        if code != 0 and result.avg_de is None:
            self._log.appendPlainText(f"\n[ERROR] profcheck exited with code {code} and produced no results.")
            failure = self._checker.primary_failure()
            if failure is not None:
                InfoDialog("Profile Quality Check Failed", failure[1], self, min_width=520).exec()
            return

        if code != 0:
            self._log.appendPlainText(f"\n[WARNING] profcheck exited with code {code}.")

        threshold          = self._threshold_spin.value()
        all_strips_display = group_by_strip(result.patch_errors) if result.patch_errors else []
        refine_strips      = strips_to_refine(result.patch_errors, threshold=threshold) if result.patch_errors else []
        n_total_strips     = total_strip_count(result.patch_errors) if result.patch_errors else 1
        n_flagged          = len(refine_strips)
        n_patches_above    = sum(1 for _, de in result.patch_errors if de > threshold)
        n_total_patches    = len(result.patch_errors) if result.patch_errors else 1
        recommend_start_over = (
            n_patches_above / n_total_patches > REFINE_START_OVER_RATIO        # >50% of patches bad
            or n_flagged / n_total_strips   > REFINE_START_OVER_STRIP_RATIO    # >75% of strips flagged
        )

        # Write output files (best-effort — a failure must not prevent the dialog)
        strips_file: Path | None = None
        if self._ti3_path:
            try:
                stem = self._ti3_path.stem
                # Quality reports + refine lists live in reports/ next to the
                # measurement (#127) — works for run folders and for a browsed
                # external .ti3 alike.
                from core.file_manager import ensure_subdir, reports_subdir
                folder = ensure_subdir(reports_subdir(self._ti3_path.parent))
                grade = quality_grade(result.avg_de, result.peak_de)
                explanation = quality_explanation(result.avg_de, result.peak_de)
                summary_text = tr("Profile Quality Assessment: {grade}").format(
                    grade=grade_display(grade)) + f"\n\n{explanation}"
                if all_strips_display:
                    strip_lines = "\n".join(
                        f"  {s:4s}  avg ΔE: {de:.2f}" for s, de in all_strips_display[:10]
                    )
                    summary_text += f"\n\nStrips with highest error (worst first, avg ΔE):\n{strip_lines}"
                if refine_strips and not recommend_start_over:
                    refine_lines = "\n".join(
                        f"  {s:4s}  max ΔE: {de:.2f}" for s, de in refine_strips
                    )
                    summary_text += (
                        f"\n\nStrips flagged for re-measurement (in measurement order, "
                        f"threshold ΔE > {threshold:.1f}):\n{refine_lines}"
                    )

                report_path = write_quality_report(folder, stem, summary_text, result.raw_log)
                self._log.appendPlainText(
                    f"\n[OK] Quality report saved: {folder.name}/{report_path.name}")

                if refine_strips and not recommend_start_over:
                    strips_file = write_refine_strips(folder, stem, refine_strips)
                    self._log.appendPlainText(
                        f"[OK] Refinement strips file saved: {folder.name}/{strips_file.name}")
            except Exception as exc:
                log.warning("Could not write quality report: %s", exc)
                self._log.appendPlainText(f"[WARNING] Could not write output files: {exc}")

        # Always show the assessment dialog if we have results
        self._show_result_dialog(
            result, all_strips_display, refine_strips, strips_file,
            recommend_start_over,
            n_flagged, n_total_strips, n_patches_above, n_total_patches,
        )

    # ------------------------------------------------------------------
    # Result dialog
    # ------------------------------------------------------------------

    def _show_result_dialog(
        self,
        result,
        all_strips_display: list[tuple[str, float]],
        refine_strips: list[tuple[str, float]],
        strips_file: Path | None,
        recommend_start_over: bool,
        n_flagged: int = 0,
        n_total_strips: int = 1,
        n_patches_above: int = 0,
        n_total_patches: int = 1,
    ) -> None:
        grade       = quality_grade(result.avg_de, result.peak_de)
        explanation = quality_explanation(result.avg_de, result.peak_de)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Profile Quality Assessment"))
        dlg.setMinimumWidth(640)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # Grade headline
        grade_lbl = QLabel(tr("Profile Quality: <b>{grade}</b>").format(
            grade=grade_display(grade)), dlg)
        grade_lbl.setStyleSheet("font-size: 15px;")
        layout.addWidget(grade_lbl)

        # Explanation
        exp_lbl = QLabel(explanation, dlg)
        exp_lbl.setWordWrap(True)
        layout.addWidget(exp_lbl)

        # Worst strips (left) and worst individual patches (right), side by side
        # so both fit without making the dialog tall.
        if all_strips_display or result.patch_errors:
            cols = QHBoxLayout()
            cols.setSpacing(24)

            if all_strips_display:
                strip_lines = "\n".join(
                    f"  • Strip {s}  (avg ΔE: {de:.2f})"
                    for s, de in all_strips_display[:5]
                )
                strip_lbl = QLabel(
                    tr("<b>Strips with the highest error</b><br>(worst first, avg ΔE):<pre>{strip_lines}</pre>").format(strip_lines=strip_lines),
                    dlg,
                )
                strip_lbl.setWordWrap(True)
                strip_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
                cols.addWidget(strip_lbl, 1)

            if result.patch_errors:
                worst_patches = sorted(
                    result.patch_errors, key=lambda pe: pe[1], reverse=True
                )[:5]
                patch_lines = "\n".join(
                    f"  • Patch {p}  (ΔE: {de:.2f})" for p, de in worst_patches
                )
                patch_lbl = QLabel(
                    tr("<b>Patches with the highest error</b><br>(worst first, ΔE):<pre>{patch_lines}</pre>").format(patch_lines=patch_lines),
                    dlg,
                )
                patch_lbl.setWordWrap(True)
                patch_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
                cols.addWidget(patch_lbl, 1)

            layout.addLayout(cols)

        # Action recommendation
        if recommend_start_over and refine_strips:
            thr = self._threshold_spin.value()
            patch_pct = round(100 * n_patches_above / n_total_patches)
            strip_pct = round(100 * n_flagged / n_total_strips)
            if n_patches_above / n_total_patches > REFINE_START_OVER_RATIO:
                reason = (
                    f"{n_patches_above} out of {n_total_patches} patches ({patch_pct}%) "
                    f"exceed ΔE {thr:.1f} — more than half of your measurement data."
                )
            else:
                reason = (
                    f"{n_flagged} out of {n_total_strips} strips ({strip_pct}%) need "
                    f"re-measuring — more than three-quarters of your chart."
                )
            action_lbl = QLabel(
                tr("<b>{reason}</b><br><br>Re-measuring individual strips is unlikely to reliably fix this. <b>Starting over with a freshly printed and measured chart is strongly recommended.</b>").format(reason=reason),
                dlg,
            )
            action_lbl.setWordWrap(True)
            layout.addWidget(action_lbl)
        elif refine_strips:
            refine_lines = "  " + "   ".join(
                f"{s} (max ΔE: {de:.2f})" for s, de in refine_strips
            )
            n_refine = len(refine_strips)
            if n_refine == 1:
                head = tr("<b>1 strip has at least one patch above "
                          "ΔE {limit:.1f} and should be re-measured:</b>").format(
                    limit=self._threshold_spin.value())
            else:
                head = tr("<b>{n} strips have at least one patch above "
                          "ΔE {limit:.1f} and should be re-measured:</b>").format(
                    n=n_refine, limit=self._threshold_spin.value())
            action_lbl = QLabel(
                head
                + "<br><pre>" + refine_lines + "</pre>"
                + tr("Listed in measurement order — the app will navigate to each "
                     "one automatically."),
                dlg,
            )
            action_lbl.setWordWrap(True)
            layout.addWidget(action_lbl)

        # Description for the "Use as pre-conditioning" path
        if self._icc_path:
            precond_desc = QLabel(
                tr("<b>Use as pre-conditioning profile</b> — start a second profiling pass "
                "that uses this profile to place the new test patches more intelligently. "
                "The next chart will sample more in the colour regions your printer "
                "reproduces least accurately, producing a noticeably better profile on "
                "the second round. This profile and its measurements are kept intact "
                "in their own run folder so nothing is lost. Recommended once "
                "you've confirmed a working profile for this paper."),
                dlg,
            )
            precond_desc.setWordWrap(True)
            precond_desc.setStyleSheet("color: #b0b0b0; font-size: 11px;")
            layout.addWidget(precond_desc)

        # Scanner-target opt-in (engine/printtarg charts only) — same feature as
        # the measure tab's "All Strips Read" dialog. Ticking it (re)builds this
        # chart's .cht + .cie from the measurement so the same printed chart can
        # profile a scanner later, whichever action the user picks below (#97/#98).
        scanner_run = None
        scanner_cb = None
        try:
            if self._ti3_path is not None:
                candidate = Run.for_dir(self._ti3_path.parent)
                if has_scanner_geometry(candidate.chart_channels_json):
                    scanner_run = candidate
        except Exception:  # noqa: BLE001 — never block the assessment dialog
            scanner_run = None
        if scanner_run is not None:
            from ui.tabs.tab_measure import make_scanner_target_row
            # Tint the card with this tab's violet accent (not the scanner-family
            # green) so it matches the dialog it lives in; readable helper colours
            # per theme (see readability requirement).
            scanner_row, scanner_cb = make_scanner_target_row(
                dlg, scanner_run.load_meta().scanner_target_enabled,
                accent=_TAB_COLOR, hint_light="#5a3fc0", hint_dark="#cabfff")
            layout.addWidget(scanner_row)

            # Weigh up the two ways to make a scanner target, so that right after
            # a printer profiling the user knows reuse is fine but a colour-managed
            # reprint is more accurate for scanning their own prints (Knut, #97).
            from PyQt6.QtGui import QPalette
            _dark = QApplication.palette().color(
                QPalette.ColorRole.Window).lightness() < 128
            scanner_tip = QLabel(
                tr("This saves recognition files from the chart you just measured "
                   "— great for general use, and they work for profiling a scanner "
                   "or a camera (scan the printed chart, or photograph it). For the "
                   "most accurate scanner profile of your own colour-managed "
                   "prints, print a fresh chart through your normal print workflow "
                   "and measure it too. (For a camera, accuracy depends on the "
                   "light you shoot under rather than a reprint — see “Profiling a "
                   "camera” in the Build window.)"),
                dlg)
            scanner_tip.setWordWrap(True)
            scanner_tip.setStyleSheet(
                f"color: {'#b8b8b8' if _dark else '#4a4a4a'}; font-size: 11px;")
            layout.addWidget(scanner_tip)

        # Buttons — laid out individually with stretches between each so they
        # spread evenly across the dialog width regardless of how many are shown.
        _install_labels = {
            "Excellent":  tr("Install Profile"),
            "Good":       tr("Install Profile As Is"),
            "Acceptable": tr("Install Profile As Is"),
            "Needs Work": tr("Install Profile Anyway"),
        }

        # Renamed "Close" → "Confirm": on any action (this one included) a ticked
        # scanner checkbox writes the .cht + .cie before the dialog closes.
        def _persist_and_build_scanner() -> None:
            if scanner_cb is None or scanner_run is None:
                return
            meta = scanner_run.load_meta()
            if meta.scanner_target_enabled != scanner_cb.isChecked():
                meta.scanner_target_enabled = scanner_cb.isChecked()
                scanner_run.save_meta(meta)
            if scanner_cb.isChecked():
                self._build_scanner_target(scanner_run, self._ti3_path)

        confirm_btn = QPushButton(tr("Confirm"), dlg)

        def _on_confirm() -> None:
            _persist_and_build_scanner()
            dlg.reject()

        confirm_btn.clicked.connect(_on_confirm)
        close_btn = confirm_btn

        install_btn: QPushButton | None = None
        if self._icc_path:
            install_label = _install_labels.get(grade, tr("Install Profile Anyway"))
            install_btn = QPushButton(install_label, dlg)

        precond_btn: QPushButton | None = None
        if self._icc_path:
            precond_btn = QPushButton(tr("← Use as Pre-conditioning"), dlg)
            precond_btn.setObjectName("primary")

        guide_btn: QPushButton | None = None
        if strips_file and refine_strips and not recommend_start_over and self._ti3_path:
            # The ← matches "← Use as Pre-conditioning" beside it: both leave
            # this tab leftwards (Measure and Create Chart), and the arrow
            # rule puts it on the side the button points (Sebastian,
            # 2026-08-12, spotting the lone arrow).
            guide_btn = QPushButton(tr("← Guide Me Through Refinement"), dlg)
            guide_btn.setObjectName("primary")
        elif install_btn and grade == "Excellent":
            install_btn.setObjectName("primary")

        # Action buttons left-to-right: Guide → Pre-conditioning → Install;
        # Close is pinned to the far right after a stretch.
        buttons: list[QPushButton] = [close_btn]
        for b in (guide_btn, precond_btn, install_btn):
            if b is not None:
                buttons.append(b)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for b in buttons[1:]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        btn_row.addWidget(buttons[0])
        layout.addLayout(btn_row)

        if guide_btn:
            ti3 = self._ti3_path

            def _on_guide():
                _persist_and_build_scanner()
                dlg.accept()
                self.guide_refinement_requested.emit(ti3, strips_file)

            guide_btn.clicked.connect(_on_guide)

        if install_btn:
            icc = self._icc_path

            def _on_install():
                try:
                    _persist_and_build_scanner()
                    profile_dir = _get_profile_dir()
                    profile_dir.mkdir(parents=True, exist_ok=True)
                    # Install under the project name (Run.stem), so the system
                    # ColorSync folder ends up with descriptive,
                    # non-colliding filenames even when the on-disk profile is
                    # the build-time `merged.icc`.
                    install_stem = Run.for_dir(icc.parent).stem
                    dest = profile_dir / f"{install_stem}{icc.suffix}"
                    shutil.copy2(icc, dest)
                    dlg.accept()
                    self._log.appendPlainText(f"[OK] Profile installed to {dest}")
                except Exception as exc:
                    self._log.appendPlainText(f"[ERROR] Install failed: {exc}")

            install_btn.clicked.connect(_on_install)

        if precond_btn:
            icc_for_precond = self._icc_path

            def _on_precond():
                _persist_and_build_scanner()
                dlg.accept()
                self.preconditioning_requested.emit(icc_for_precond)

            precond_btn.clicked.connect(_on_precond)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()

    def _build_scanner_target(self, run: Run, ti3: Path | None) -> None:
        """(Re)build the chart's ``.cht`` + ``.cie`` from this assessed
        measurement, so the same printed chart can profile a scanner later
        (#97/#98). Triggered by the opt-in checkbox in the quality-assessment
        dialog, for whichever action the user then takes.

        Best-effort and engine/printtarg-only: it must never disturb the
        check/refine flow. Silently skips non-engine charts and
        partial/mismatched reads (which raise :class:`ScaninTargetError`)."""
        try:
            source_ti3 = ti3 if ti3 is not None else run.measurement_ti3
            from workflow.scanin_target import (
                ScaninTargetError, build_scanin_target_from_paths)
            try:
                res = build_scanin_target_from_paths(
                    run.chart_channels_json, source_ti3, run.dir / run.stem)
            except ScaninTargetError:
                return   # e.g. a partial read → not every patch measured yet
            self._log.appendPlainText(
                "\n" + tr("[OK] Recognition files (.cht + .cie) saved for {n} "
                          "patches — scan or photograph the printed chart, then "
                          "use Tools ▸ Build profile with scanner or camera."
                          ).format(n=res.n_patches))
        except Exception:  # noqa: BLE001 — never let this break the assessment
            log.exception("Scanner-target build failed (non-fatal)")

    # ------------------------------------------------------------------
    # Param collection
    # ------------------------------------------------------------------

    def _collect_params(self) -> ProfcheckParams:
        params = (self._collect_guided_check() if self._current_mode() == "guided"
                  else self._collect_manual_check())
        # Strip options the detected instrument can't support, even if they were
        # enabled before the .ti3 was loaded (the widgets are also greyed out).
        if self._gate_active():
            for opt in self._gated_options:
                opt.neutralise(params)
        return params

    def _collect_guided_check(self) -> ProfcheckParams:
        de_map = {"k": "-k", "c": "-c", "": ""}
        de_raw = self._de_combo.currentData() or ""
        return ProfcheckParams(
            ti3_path      = self._ti3_path,
            icc_path      = self._icc_path,
            de_formula    = de_map.get(de_raw, ""),
            intent        = self._intent_combo.currentData() or "a",
            sort          = self._sort_cb.isChecked(),
            verbosity     = self._verb_combo.currentData() or "2",
            fwa_enabled   = self._fwa_cb.isChecked(),
            fwa_illum     = self._fwa_combo.currentData() or "D50",
            illum         = self._illum_combo.currentData() or "D50",
            observer      = self._obs_combo.currentData() or "1931_2",
            prune_enabled = self._prune_cb.isChecked(),
            prune_value   = self._prune_spin.value(),
            x3dom         = self._x3dom_cb.isChecked(),
        )

    def _collect_manual_check(self) -> ProfcheckParams:
        de_map = {"k": "-k", "c": "-c", "": ""}
        de_raw = self._m_de_combo.currentData() or ""
        return ProfcheckParams(
            ti3_path      = self._ti3_path,
            icc_path      = self._icc_path,
            de_formula    = de_map.get(de_raw, ""),
            intent        = self._m_intent_combo.currentData() or "a",
            sort          = self._m_sort_cb.isChecked(),
            verbosity     = self._m_verb_combo.currentData() or "2",
            fwa_enabled   = self._m_fwa_cb.isChecked(),
            fwa_illum     = self._m_fwa_combo.currentData() or "D50",
            illum         = self._m_illum_combo.currentData() or "D50",
            observer      = self._m_obs_combo.currentData() or "1931_2",
            prune_enabled = self._m_prune_cb.isChecked(),
            prune_value   = self._m_prune_spin.value(),
            x3dom         = self._m_x3dom_cb.isChecked(),
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _on_save_defaults(self) -> None:
        s = self._settings
        if self._current_mode() == "guided":
            s.set("profcheck_de_formula",    self._de_combo.currentData() or "k")
            s.set("profcheck_intent",        self._intent_combo.currentData() or "a")
            s.set("profcheck_sort",          self._sort_cb.isChecked())
            s.set("profcheck_verbosity",     self._verb_combo.currentData() or "2")
            s.set("profcheck_fwa_enabled",   self._fwa_cb.isChecked())
            s.set("profcheck_fwa_illum",     self._fwa_combo.currentData() or "D50")
            s.set("profcheck_illum",         self._illum_combo.currentData() or "D50")
            s.set("profcheck_observer",      self._obs_combo.currentData() or "1931_2")
            s.set("profcheck_prune_enabled", self._prune_cb.isChecked())
            s.set("profcheck_prune_value",   self._prune_spin.value())
            s.set("profcheck_x3dom",             self._x3dom_cb.isChecked())
            s.set("profcheck_refine_threshold",  self._threshold_spin.value())
        else:
            s.set("manual2_profcheck_de_formula",    self._m_de_combo.currentData() or "k")
            s.set("manual2_profcheck_intent",        self._m_intent_combo.currentData() or "a")
            s.set("manual2_profcheck_sort",          self._m_sort_cb.isChecked())
            s.set("manual2_profcheck_verbosity",     self._m_verb_combo.currentData() or "2")
            s.set("manual2_profcheck_fwa_enabled",   self._m_fwa_cb.isChecked())
            s.set("manual2_profcheck_fwa_illum",     self._m_fwa_combo.currentData() or "D50")
            s.set("manual2_profcheck_illum",         self._m_illum_combo.currentData() or "D50")
            s.set("manual2_profcheck_observer",      self._m_obs_combo.currentData() or "1931_2")
            s.set("manual2_profcheck_prune_enabled", self._m_prune_cb.isChecked())
            s.set("manual2_profcheck_prune_value",   self._m_prune_spin.value())
            s.set("manual2_profcheck_x3dom",         self._m_x3dom_cb.isChecked())
        self._log.appendPlainText("Check & Refine settings saved as defaults.")

    def _restore_defaults(self) -> None:
        s = self._settings

        # Guided defaults
        de = s.get("profcheck_de_formula", "k")
        idx = self._de_combo.findData(de)
        if idx >= 0:
            self._de_combo.setCurrentIndex(idx)

        intent = s.get("profcheck_intent", "a")
        idx = self._intent_combo.findData(intent)
        if idx >= 0:
            self._intent_combo.setCurrentIndex(idx)

        self._sort_cb.setChecked(bool(s.get("profcheck_sort", True)))

        verb = s.get("profcheck_verbosity", "2")
        idx = self._verb_combo.findData(verb)
        if idx >= 0:
            self._verb_combo.setCurrentIndex(idx)

        self._fwa_cb.setChecked(bool(s.get("profcheck_fwa_enabled", False)))
        fwa_illum = s.get("profcheck_fwa_illum", "D50")
        idx = self._fwa_combo.findData(fwa_illum)
        if idx >= 0:
            self._fwa_combo.setCurrentIndex(idx)
        self._fwa_combo.setEnabled(self._fwa_cb.isChecked())

        illum = s.get("profcheck_illum", "D50")
        idx = self._illum_combo.findData(illum)
        if idx >= 0:
            self._illum_combo.setCurrentIndex(idx)

        obs = s.get("profcheck_observer", "1931_2")
        idx = self._obs_combo.findData(obs)
        if idx >= 0:
            self._obs_combo.setCurrentIndex(idx)

        self._prune_cb.setChecked(bool(s.get("profcheck_prune_enabled", False)))
        try:
            prune_val = float(s.get("profcheck_prune_value", 3.0))
        except (TypeError, ValueError):
            prune_val = 3.0
        self._prune_spin.setValue(prune_val)
        self._prune_spin.setEnabled(self._prune_cb.isChecked())

        self._x3dom_cb.setChecked(bool(s.get("profcheck_x3dom", False)))

        try:
            threshold_val = float(s.get("profcheck_refine_threshold", REFINE_DE_THRESHOLD))
        except (TypeError, ValueError):
            threshold_val = REFINE_DE_THRESHOLD
        self._threshold_spin.setValue(threshold_val)

        # Manual defaults
        def _set_m(combo: NoScrollComboBox, key: str, default: str) -> None:
            idx = combo.findData(s.get(key, default))
            if idx >= 0:
                combo.setCurrentIndex(idx)

        _set_m(self._m_de_combo,     "manual2_profcheck_de_formula", "k")
        _set_m(self._m_intent_combo, "manual2_profcheck_intent",     "a")
        self._m_sort_cb.setChecked(bool(s.get("manual2_profcheck_sort", True)))
        _set_m(self._m_verb_combo,   "manual2_profcheck_verbosity",  "2")
        self._m_fwa_cb.setChecked(bool(s.get("manual2_profcheck_fwa_enabled", False)))
        _set_m(self._m_fwa_combo,    "manual2_profcheck_fwa_illum",  "D50")
        self._m_fwa_combo.setEnabled(self._m_fwa_cb.isChecked())
        _set_m(self._m_illum_combo,  "manual2_profcheck_illum",      "D50")
        _set_m(self._m_obs_combo,    "manual2_profcheck_observer",   "1931_2")
        self._m_prune_cb.setChecked(bool(s.get("manual2_profcheck_prune_enabled", False)))
        try:
            m_prune_val = float(s.get("manual2_profcheck_prune_value", 3.0))
        except (TypeError, ValueError):
            m_prune_val = 3.0
        self._m_prune_spin.setValue(m_prune_val)
        self._m_prune_spin.setEnabled(self._m_prune_cb.isChecked())
        self._m_x3dom_cb.setChecked(bool(s.get("manual2_profcheck_x3dom", False)))
        presets = self._m_load_presets()
        self._m_populate_preset_combo(presets)
