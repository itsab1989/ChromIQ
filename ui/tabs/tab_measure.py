"""Tab 3: Measure Chart."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.resource_path import resource_path
from core.strip_utils import letter_to_idx
from ui.tab_header import TabHeader
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox, load_folder_icon, make_browse_button, open_file_dialog, tint_dialog_primary

_TAB_COLOR = "#56d6a5"  # Measure tab accent
from workflow.measure_manager import MeasureManager, MeasureParams
from ui.tiff_preview import TiffPreview

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)



def _detect_stripe_rects(tiff_path: Path) -> list[QRect]:
    """Locate vertical strip columns in a printtarg TIFF.

    Strategy
    --------
    1. Find the label zone: the first contiguous block of rows that have a
       "moderate" number of dark pixels (printed label characters — neither
       blank white rows nor full-width separator lines).
    2. Build a per-column dark-pixel count from those rows; merge adjacent
       non-zero runs to get one cluster per strip label.
    3. Convert label-cluster centres → strip x-boundaries (midpoints between
       centres, extrapolated at the edges).
    4. Derive the vertical extent from the full content bounding box.
    """
    from PIL import Image
    try:
        img = Image.open(tiff_path).convert("L")
        orig_w, orig_h = img.size

        ANALYSIS_W = 1000
        scale  = ANALYSIS_W / orig_w if orig_w > ANALYSIS_W else 1.0
        aw     = max(1, int(orig_w * scale))
        ah     = max(1, int(orig_h * scale))
        small  = img.resize((aw, ah), Image.BOX)
        pix    = small.load()

        DARK            = 80
        WHITE           = 240
        MIN_LABEL_DARK  = max(5, aw // 200)   # at least this many dark px/row
        MAX_LABEL_FRAC  = 0.30                 # exclude separator lines (>30% dark)
        EMPTY_STOP      = 8                    # white rows before stopping label scan
        MERGE_GAP       = max(3, aw // 200)   # merge within-label character gaps

        # ── 1. Locate the label zone ─────────────────────────────────────────
        max_label_dark = int(aw * MAX_LABEL_FRAC)
        y_lab_start: int | None = None
        y_lab_end:   int | None = None
        empty_streak = 0
        for y in range(ah * 30 // 100):
            count = sum(1 for x in range(aw) if pix[x, y] < DARK)
            if MIN_LABEL_DARK <= count <= max_label_dark:
                if y_lab_start is None:
                    y_lab_start = y
                y_lab_end = y
                empty_streak = 0
            else:
                empty_streak += 1
                if y_lab_start is not None and empty_streak >= EMPTY_STOP:
                    break

        if y_lab_start is None or y_lab_end is None:
            log.debug("Strip detection: no label zone found")
            return []

        # ── 2. Column dark-pixel profile → merge into per-strip clusters ─────
        col_dark = [0] * aw
        for y in range(y_lab_start, y_lab_end + 1):
            for x in range(aw):
                if pix[x, y] < DARK:
                    col_dark[x] += 1

        runs: list[tuple[int, int]] = []
        in_run = False
        r_start = 0
        for x in range(aw):
            if col_dark[x] > 0 and not in_run:
                in_run, r_start = True, x
            elif col_dark[x] == 0 and in_run:
                in_run = False
                runs.append((r_start, x - 1))
        if in_run:
            runs.append((r_start, aw - 1))

        merged: list[list[int]] = []
        for s, e in runs:
            if merged and s - merged[-1][1] <= MERGE_GAP:
                merged[-1][1] = e
            else:
                merged.append([s, e])

        n_strips = len(merged)
        if n_strips < 1:
            log.debug("Strip detection: no label clusters found")
            return []

        centers = [(s + e) / 2 for s, e in merged]

        # ── 3. Vertical extent ───────────────────────────────────────────────
        y_top_a    = next((y for y in range(ah)
                           if any(pix[x, y] < WHITE for x in range(0, aw, 4))), 0)
        y_bottom_a = next((y for y in range(ah - 1, -1, -1)
                           if any(pix[x, y] < WHITE for x in range(0, aw, 4))), ah - 1)

        inv           = 1.0 / scale
        y_top         = max(0,      int(y_top_a    * inv))
        y_bottom      = min(orig_h, int((y_bottom_a + 1) * inv))
        strip_h       = max(1, y_bottom - y_top)
        y_label_bot   = min(orig_h, int((y_lab_end + 1) * inv))

        # ── 4. Build vertical column rects ───────────────────────────────────
        rects: list[QRect] = []
        for i, cx in enumerate(centers):
            half_l = (cx - centers[i - 1]) / 2 if i > 0         else (centers[1] - centers[0]) / 2
            half_r = (centers[i + 1] - cx) / 2 if i < n_strips-1 else (centers[-1] - centers[-2]) / 2
            x0 = max(0,      int((cx - half_l) * inv))
            x1 = min(orig_w, int((cx + half_r) * inv))
            rects.append(QRect(x0, y_label_bot, max(1, x1 - x0), strip_h))

        log.info("Strip detection: %d strips, label y=%d–%d (scaled), content y=%d–%d (orig)",
                 n_strips, y_lab_start, y_lab_end, y_top, y_bottom)
        return rects

    except Exception as exc:
        log.warning("Strip detection failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Per-option chartread row helper
# ---------------------------------------------------------------------------

@dataclass
class _ChartreadOption:
    """One chartread option row with enable-checkbox and optional value widget."""
    key: str           # settings key suffix
    flag: str          # CLI flag
    label: str
    tooltip_title: str
    tooltip_body: str
    widget: QWidget | None = None   # value widget (spinbox, combo…)
    checkbox: QCheckBox | None = None

    def build_args(self) -> list[str]:
        """Return CLI tokens for this option if enabled."""
        if self.checkbox is None or not self.checkbox.isChecked():
            return []
        if self.widget is None:
            return [self.flag]
        val = self._read_widget()
        if val is None:
            return [self.flag]
        return [self.flag, str(val)]

    def _read_widget(self):
        if isinstance(self.widget, (QSpinBox, QDoubleSpinBox)):
            return self.widget.value()
        if isinstance(self.widget, QComboBox):
            return self.widget.currentData()
        return None


class TabMeasure(QWidget):
    """Step 3: interactive chart measurement with chartread."""

    measure_finished   = pyqtSignal(Path)  # emits the .ti3 path on success
    proceed_to_profile = pyqtSignal()      # emitted when user chooses to go straight to tab 4
    measurement_active = pyqtSignal(bool)  # True when chartread is running, False when done

    def __init__(
        self,
        runner: "ArgyllRunner",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner   = runner
        self._settings = settings
        self._manager  = MeasureManager(runner, self)
        self._ti1_path: Path | None = None
        self._tiff_pages: list[Path] = []
        self._chartread_opts: list[_ChartreadOption] = []
        self._measure_failed: bool = False
        self._strip_list: list[str] = []
        self._refine_strips_path: Path | None = None
        self._guided_refinement_active: bool = False
        self._resume_active: bool = False
        self._auto_proceed: bool = False
        self._all_done_shown: bool = False
        self._instrument_disconnected: bool = False
        self._device_busy: bool = False
        self._no_instrument: bool = False

        self._manager.stripe_changed.connect(self._on_stripe_changed)
        self._manager.all_stripes_done.connect(self._on_all_stripes_done)
        self._manager.calibration_prompt.connect(self._on_calibration_prompt)
        self._manager.calibration_done.connect(self._on_calibration_done)
        self._manager.strip_error.connect(self._on_strip_error)
        self._manager.instrument_disconnected.connect(self._on_instrument_disconnected)
        self._manager.device_busy.connect(self._on_device_busy)
        self._manager.no_instrument.connect(self._on_no_instrument)
        self._manager.wrong_strip.connect(self._on_wrong_strip)
        self._manager.unexpected_response.connect(self._on_unexpected_response)
        self._manager.sensor_wrong_position.connect(self._on_sensor_wrong_position)
        self._build_ui()
        self._restore_defaults()
        self._start_btn.setEnabled(False)

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

    def _current_mode(self) -> str:
        return "guided" if self._stack.currentIndex() == 0 else "manual"

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ---- Left ----
        left_container = QWidget(self)
        self._left_panel = left_container
        left_container.setFixedWidth(580)
        lc_layout = QVBoxLayout(left_container)
        lc_layout.setContentsMargins(0, 0, 0, 0)
        lc_layout.setSpacing(0)

        # Header + mode buttons (outside scroll/stack)
        top_widget = QWidget(left_container)
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(16, 12, 16, 6)
        top_layout.setSpacing(8)
        top_layout.addWidget(TabHeader(
            "STEP 03 · MEASURE TARGET", "Measure printed chart", "#56d6a5", top_widget
        ))
        _mode_font = QFont("Menlo", 11, QFont.Weight.Medium)
        mode_row = QHBoxLayout()
        self._guided_btn = QPushButton("GUIDED", top_widget)
        self._guided_btn.setCheckable(True)
        self._guided_btn.setChecked(True)
        self._guided_btn.setObjectName("mode_btn")
        self._guided_btn.setFont(_mode_font)
        self._manual_btn = QPushButton("MANUAL", top_widget)
        self._manual_btn.setCheckable(True)
        self._manual_btn.setObjectName("mode_btn")
        self._manual_btn.setFont(_mode_font)
        self._guided_btn.clicked.connect(lambda: self._switch_mode("guided"))
        self._manual_btn.clicked.connect(lambda: self._switch_mode("manual"))
        mode_row.addWidget(self._guided_btn)
        mode_row.addWidget(self._manual_btn)
        mode_row.addStretch()
        top_layout.addLayout(mode_row)
        lc_layout.addWidget(top_widget)

        # File selection — shared between modes
        file_outer = QWidget(left_container)
        fo_layout = QVBoxLayout(file_outer)
        fo_layout.setContentsMargins(16, 4, 16, 0)
        fo_layout.setSpacing(0)
        self._file_grp = file_grp = QGroupBox("Target File (.ti2)", file_outer)
        file_grp.setFlat(True)
        fg = QVBoxLayout(file_grp)
        fg.setContentsMargins(8, 6, 8, 8)
        file_row = QHBoxLayout()
        self._load_ti1_btn = QPushButton("Load .ti2 file…", file_outer)
        self._load_ti1_btn.setIcon(load_folder_icon("folder_measure"))
        self._load_ti1_btn.clicked.connect(self._on_load_ti2)
        self._ti1_lbl = QLabel("No file selected", file_outer)
        self._ti1_lbl.setStyleSheet("color: #909090; font-size: 11px;")
        self._ti1_lbl.setWordWrap(True)
        file_row.addWidget(self._load_ti1_btn)
        file_row.addWidget(self._ti1_lbl, stretch=1)
        fg.addLayout(file_row)
        fo_layout.addWidget(file_grp)
        lc_layout.addWidget(file_outer)

        # Stacked panels
        self._stack = QStackedWidget(left_container)
        self._guided_panel = self._make_guided_panel()
        self._manual_panel = self._make_manual_panel()
        self._stack.addWidget(self._guided_panel)
        self._stack.addWidget(self._manual_panel)
        lc_layout.addWidget(self._stack, stretch=1)

        # Buttons — shared
        btn_outer = QWidget(left_container)
        bo_layout = QVBoxLayout(btn_outer)
        bo_layout.setContentsMargins(16, 6, 16, 8)
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Measurement", btn_outer)
        self._start_btn.setObjectName("primary")
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn = QPushButton("Stop", btn_outer)
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.setStyleSheet(
            "QPushButton { background: #f4f4f4; color: #121212; border: 1px solid #cccccc; font-weight: 600; }"
            "QPushButton:hover { background: #e0e0e0; border-color: #bbbbbb; }"
            "QPushButton:disabled { background: #2a2a2a; color: #555555; border-color: #333333; }"
        )
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        self._save_defaults_btn = QPushButton("Save as Defaults", btn_outer)
        self._save_defaults_btn.setFixedHeight(36)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        bo_layout.addLayout(btn_row)
        lc_layout.addWidget(btn_outer)

        # Log — shared
        log_outer = QWidget(left_container)
        lo_layout = QVBoxLayout(log_outer)
        lo_layout.setContentsMargins(16, 0, 16, 6)
        self._log = QPlainTextEdit(log_outer)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(100)
        self._log.setMaximumHeight(100)
        self._log.setPlaceholderText("chartread output will appear here…")
        lo_layout.addWidget(self._log)
        lc_layout.addWidget(log_outer)

        # Status bar (replaces main-window status bar)
        self._status_bar_lbl = QLabel("", left_container)
        self._status_bar_lbl.setWordWrap(True)
        self._status_bar_lbl.setVisible(False)
        lc_layout.addWidget(self._status_bar_lbl)

        splitter.addWidget(left_container)

        # ---- Right preview ----
        right = QWidget(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 12)
        lbl = QLabel("CHART PREVIEW", right)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "color: #808080; background: transparent; padding: 4px;"
            " font-family: Menlo; font-size: 9pt; font-weight: 300;"
        )
        rl.addWidget(lbl)
        self._preview = TiffPreview(right)
        rl.addWidget(self._preview, stretch=1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Guided panel
    # ------------------------------------------------------------------

    def _make_guided_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 8, 16, 8)
        ll.setSpacing(10)

        # Instrument
        self._instr_grp = instr_grp = QGroupBox("Measurement Instrument", left)
        instr_grp.setFlat(True)
        ig = QVBoxLayout(instr_grp)
        ig.setContentsMargins(8, 6, 8, 8)
        instr_row = QHBoxLayout()
        instr_row.addWidget(QLabel("Instrument port number:", left))
        self._instr_spin = NoScrollSpinBox(left)
        self._instr_spin.setRange(1, 9)
        self._instr_spin.setValue(1)
        instr_row.addWidget(self._instr_spin)
        instr_row.addStretch()
        instr_row.addWidget(TooltipButton(
            "Instrument Port",
            "Port index passed to chartread via -c.\n"
            "Most setups use 1 (single instrument connected).\n"
            "If chartread lists multiple devices at startup, set the\n"
            "number shown next to your instrument in that list.",
            left,
        ))
        ig.addLayout(instr_row)
        ll.addWidget(instr_grp)
        instr_grp.setVisible(False)

        # Core measurement options (always shown)
        self._core_grp = core_grp = QGroupBox("Measurement Options", left)
        cg = QVBoxLayout(core_grp)
        cg.setContentsMargins(8, 14, 8, 8)
        cg.setSpacing(8)

        def _bool_row(label, default, tt_title, tt_body):
            row = QHBoxLayout()
            cb = QCheckBox(label, left)
            cb.setChecked(default)
            row.addWidget(cb)
            row.addStretch()
            tip = TooltipButton(tt_title, tt_body, left)
            row.addWidget(tip)
            cg.addLayout(row)
            return cb, tip

        self._bidir_cb, _ = _bool_row(
            "Disable bidirectional strip recognition (-B)", True,
            "Disable Bidirectional Reading (-B)",
            "Strongly recommended ON.  Prevents mis-reads from scanning\n"
            "strips in the wrong direction.",
        )
        self._suppress_cb, _ = _bool_row(
            "Suppress warning messages (-S)", True,
            "Suppress Warnings (-S)",
            "Suppresses non-fatal instrument warnings during measurement.",
        )
        self._nocal_cb, _nocal_tip = _bool_row(
            "Skip initial calibration (-N)", False,
            "Skip Initial Calibration (-N)",
            "Skips the white-tile calibration at startup.  Only use if you\n"
            "have already calibrated in this session.",
        )
        self._nocal_cb.setVisible(False)
        _nocal_tip.setVisible(False)
        self._pbp_cb, _pbp_tip = _bool_row(
            "Patch-by-patch mode (-p)", False,
            "Patch-by-Patch Mode (-p)",
            "Measure each patch individually instead of reading strips.\n"
            "Much slower but useful if strip reading fails.",
        )
        self._pbp_cb.setVisible(False)
        _pbp_tip.setVisible(False)

        resume_row = QHBoxLayout()
        self._resume_cb = QCheckBox("Refine existing measurement (-r)", left)
        self._resume_cb.setChecked(False)
        self._resume_cb.setVisible(False)
        resume_row.addWidget(self._resume_cb)
        resume_row.addStretch()
        self._resume_tip = TooltipButton(
            "Refine Existing Measurement (-r)",
            "Resumes from the existing .ti3 file in the same folder as the\n"
            ".ti2 file. Previously measured strips are kept — you only need\n"
            "to scan the strips you want to update or add.\n\n"
            "Use this after a quality check to re-measure problem strips,\n"
            "or to continue a measurement that was interrupted.\n\n"
            "This option appears only when a matching .ti3 file is found.",
            left,
        )
        self._resume_tip.setVisible(False)
        resume_row.addWidget(self._resume_tip)
        cg.addLayout(resume_row)

        # Refinement file row — shown only when resume is checked
        self._refine_row = QWidget(left)
        refine_rl = QHBoxLayout(self._refine_row)
        refine_rl.setContentsMargins(20, 0, 0, 0)
        refine_rl.setSpacing(6)
        self._refine_cb = QCheckBox(
            "Use refinement strips file for guided re-measurement",
            self._refine_row,
        )
        self._refine_cb.setEnabled(False)
        refine_rl.addWidget(self._refine_cb, stretch=1)
        refine_rl.addWidget(TooltipButton(
            "Refinement Strips File",
            "Available when a Refine_Strips_<name>.txt file exists next\n"
            "to your .ti2 file.\n\n"
            "That file is created automatically by the Check && Refine\n"
            "tab after a quality check. It lists the strips with the\n"
            "highest colour errors, sorted worst-first.\n\n"
            "When active, the app navigates chartread to each of those\n"
            "strips automatically — you only need to scan them.",
            self._refine_row,
        ))
        self._refine_row.setVisible(False)
        cg.addWidget(self._refine_row)

        self._resume_cb.stateChanged.connect(
            lambda state: self._refine_row.setVisible(
                state == Qt.CheckState.Checked.value
            )
        )

        ll.addWidget(core_grp)

        # Additional chartread arguments — structured
        self._adv_grp = adv_grp = QGroupBox("Additional Options", left)
        ag = QVBoxLayout(adv_grp)
        ag.setContentsMargins(8, 14, 8, 8)
        ag.setSpacing(6)

        self._chartread_opts = self._make_chartread_options(left)
        for opt in self._chartread_opts:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)

            cb = QCheckBox(opt.label, left)
            cb.setChecked(False)
            opt.checkbox = cb

            if opt.widget is not None:
                opt.widget.setEnabled(False)
                cb.toggled.connect(opt.widget.setEnabled)
                row.addWidget(cb, stretch=1)
                row.addWidget(opt.widget)
            else:
                row.addWidget(cb, stretch=1)

            row.addWidget(TooltipButton(opt.tooltip_title, opt.tooltip_body, left))
            ag.addLayout(row)

        ll.addWidget(adv_grp)
        adv_grp.setVisible(False)
        ll.addStretch(1)

        scroll.setWidget(left)
        return scroll

    # ------------------------------------------------------------------
    # Manual panel
    # ------------------------------------------------------------------

    def _make_manual_panel(self) -> QWidget:
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(16, 8, 16, 0)
        cl.setSpacing(0)

        # Presets group
        presets_grp = QGroupBox("Presets", container)
        presets_row = QHBoxLayout(presets_grp)
        presets_row.setContentsMargins(8, 4, 8, 8)
        presets_row.addWidget(QLabel("Select preset:", container))
        self._m_preset_combo = NoScrollComboBox(container)
        self._m_preset_combo.addItem("Default", userData=None)
        presets_row.addWidget(self._m_preset_combo, stretch=1)
        self._m_preset_add_btn = QPushButton(container)
        self._m_preset_add_btn.setObjectName("icon_btn")
        self._m_preset_add_btn.setFixedSize(28, 28)
        self._m_preset_add_btn.setIcon(QIcon(str(resource_path("assets/plus.svg"))))
        self._m_preset_add_btn.setToolTip("Save current settings as a new preset")
        self._m_preset_del_btn = QPushButton(container)
        self._m_preset_del_btn.setObjectName("icon_btn")
        self._m_preset_del_btn.setFixedSize(28, 28)
        self._m_preset_del_btn.setIcon(QIcon(str(resource_path("assets/minus.svg"))))
        self._m_preset_del_btn.setToolTip("Delete selected preset")
        self._m_preset_del_btn.setEnabled(False)
        presets_row.addWidget(self._m_preset_add_btn)
        presets_row.addWidget(self._m_preset_del_btn)
        presets_row.addWidget(TooltipButton(
            "Manual Presets",
            "Save and recall named snapshots of all Manual mode settings.\n\n"
            "Use the + button to save the current parameter values as a named preset. "
            "Select a preset from the list to instantly restore those values. "
            "Use the − button to delete the selected preset.",
            container,
            min_width=480,
        ))
        self._m_preset_combo.currentIndexChanged.connect(self._on_m_preset_selected)
        self._m_preset_add_btn.clicked.connect(self._on_m_preset_save)
        self._m_preset_del_btn.clicked.connect(self._on_m_preset_delete)
        cl.addWidget(presets_grp)
        cl.addSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 8, 0, 8)
        ll.setSpacing(10)

        # Instrument — mirrors guided "Measurement Instrument" group
        m_instr_grp = QGroupBox("Measurement Instrument", left)
        m_instr_grp.setFlat(True)
        mig = QVBoxLayout(m_instr_grp)
        mig.setContentsMargins(8, 6, 8, 8)
        m_instr_row = QHBoxLayout()
        m_instr_row.addWidget(QLabel("Instrument port number:", left))
        self._m_instr_spin = NoScrollSpinBox(left)
        self._m_instr_spin.setRange(1, 9)
        self._m_instr_spin.setValue(1)
        m_instr_row.addWidget(self._m_instr_spin)
        m_instr_row.addStretch()
        m_instr_row.addWidget(TooltipButton(
            "Instrument Port",
            "Port index passed to chartread via -c.\n"
            "Most setups use 1 (single instrument connected).\n"
            "If chartread lists multiple devices at startup, set the\n"
            "number shown next to your instrument in that list.",
            left,
        ))
        mig.addLayout(m_instr_row)
        ll.addWidget(m_instr_grp)

        # Measurement Options — mirrors guided "Measurement Options" group
        m_core_grp = QGroupBox("Measurement Options", left)
        mcg = QVBoxLayout(m_core_grp)
        mcg.setContentsMargins(8, 14, 8, 8)
        mcg.setSpacing(8)

        def _bool_row_m(label, default, tt_title, tt_body):
            row = QHBoxLayout()
            cb = QCheckBox(label, left)
            cb.setChecked(default)
            row.addWidget(cb)
            row.addStretch()
            row.addWidget(TooltipButton(tt_title, tt_body, left))
            mcg.addLayout(row)
            return cb

        self._m_bidir_cb = _bool_row_m(
            "Disable bidirectional strip recognition (-B)", True,
            "Disable Bidirectional Reading (-B)",
            "Strongly recommended ON.  Prevents mis-reads from scanning\n"
            "strips in the wrong direction.",
        )
        self._m_suppress_cb = _bool_row_m(
            "Suppress warning messages (-S)", True,
            "Suppress Warnings (-S)",
            "Suppresses non-fatal instrument warnings during measurement.",
        )
        self._m_nocal_cb = _bool_row_m(
            "Skip initial calibration (-N)", False,
            "Skip Initial Calibration (-N)",
            "Skips the white-tile calibration at startup.  Only use if you\n"
            "have already calibrated in this session.",
        )
        self._m_pbp_cb = _bool_row_m(
            "Patch-by-patch mode (-p)", False,
            "Patch-by-Patch Mode (-p)",
            "Measure each patch individually instead of reading strips.\n"
            "Much slower but useful if strip reading fails.",
        )

        m_resume_row = QHBoxLayout()
        self._m_resume_cb = QCheckBox("Refine existing measurement (-r)", left)
        self._m_resume_cb.setChecked(False)
        self._m_resume_cb.setVisible(False)
        m_resume_row.addWidget(self._m_resume_cb)
        m_resume_row.addStretch()
        self._m_resume_tip = TooltipButton(
            "Refine Existing Measurement (-r)",
            "Resumes from the existing .ti3 file in the same folder as the\n"
            ".ti2 file. Previously measured strips are kept — you only need\n"
            "to scan the strips you want to update or add.\n\n"
            "Use this after a quality check to re-measure problem strips,\n"
            "or to continue a measurement that was interrupted.\n\n"
            "This option appears only when a matching .ti3 file is found.",
            left,
        )
        self._m_resume_tip.setVisible(False)
        m_resume_row.addWidget(self._m_resume_tip)
        mcg.addLayout(m_resume_row)

        self._m_refine_row = QWidget(left)
        m_refine_rl = QHBoxLayout(self._m_refine_row)
        m_refine_rl.setContentsMargins(20, 0, 0, 0)
        m_refine_rl.setSpacing(6)
        self._m_refine_cb = QCheckBox(
            "Use refinement strips file for guided re-measurement",
            self._m_refine_row,
        )
        self._m_refine_cb.setEnabled(False)
        m_refine_rl.addWidget(self._m_refine_cb, stretch=1)
        m_refine_rl.addWidget(TooltipButton(
            "Refinement Strips File",
            "Available when a Refine_Strips_<name>.txt file exists next\n"
            "to your .ti2 file.\n\n"
            "That file is created automatically by the Check && Refine\n"
            "tab after a quality check. It lists the strips with the\n"
            "highest colour errors, sorted worst-first.\n\n"
            "When active, the app navigates chartread to each of those\n"
            "strips automatically — you only need to scan them.",
            self._m_refine_row,
        ))
        self._m_refine_row.setVisible(False)
        mcg.addWidget(self._m_refine_row)

        self._m_resume_cb.stateChanged.connect(
            lambda state: self._m_refine_row.setVisible(
                state == Qt.CheckState.Checked.value
            )
        )

        ll.addWidget(m_core_grp)

        # Additional Options — mirrors guided "Additional Options" group
        m_adv_grp = QGroupBox("Additional Options", left)
        mag = QVBoxLayout(m_adv_grp)
        mag.setContentsMargins(8, 14, 8, 8)
        mag.setSpacing(6)

        self._m_chartread_opts = self._make_manual_chartread_options(left)
        for opt in self._m_chartread_opts:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            cb = QCheckBox(opt.label, left)
            cb.setChecked(False)
            opt.checkbox = cb
            if opt.widget is not None:
                opt.widget.setEnabled(False)
                cb.toggled.connect(opt.widget.setEnabled)
                row.addWidget(cb, stretch=1)
                row.addWidget(opt.widget)
            else:
                row.addWidget(cb, stretch=1)
            row.addWidget(TooltipButton(opt.tooltip_title, opt.tooltip_body, left))
            mag.addLayout(row)

        ll.addWidget(m_adv_grp)
        ll.addStretch(1)

        scroll.setWidget(left)
        cl.addWidget(scroll, stretch=1)
        return container

    # ------------------------------------------------------------------
    # Manual preset helpers (Measure tab)
    # ------------------------------------------------------------------

    def _m_load_presets(self) -> dict:
        raw = self._settings.get("manual2_measure_presets", "")
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _m_save_presets(self, presets: dict) -> None:
        self._settings.set("manual2_measure_presets", json.dumps(presets))

    def _m_populate_preset_combo(self, presets: dict, select_name: str | None = None) -> None:
        self._m_preset_combo.blockSignals(True)
        self._m_preset_combo.clear()
        self._m_preset_combo.addItem("Default", userData=None)
        for name in presets:
            self._m_preset_combo.addItem(name, userData=name)
        if select_name is not None:
            idx = self._m_preset_combo.findText(select_name)
            if idx >= 0:
                self._m_preset_combo.setCurrentIndex(idx)
        self._m_preset_combo.blockSignals(False)
        self._m_preset_del_btn.setEnabled(self._m_preset_combo.currentIndex() > 0)

    def _m_collect_preset_data(self) -> dict:
        data: dict = {
            "instr":    self._m_instr_spin.value(),
            "bidir":    self._m_bidir_cb.isChecked(),
            "suppress": self._m_suppress_cb.isChecked(),
            "nocal":    self._m_nocal_cb.isChecked(),
            "pbp":      self._m_pbp_cb.isChecked(),
        }
        for opt in self._m_chartread_opts:
            if opt.checkbox:
                data[f"{opt.key}_enabled"] = opt.checkbox.isChecked()
            if opt.widget is not None:
                if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                    data[f"{opt.key}_value"] = opt.widget.value()
                elif isinstance(opt.widget, QComboBox):
                    data[f"{opt.key}_value"] = opt.widget.currentData()
        return data

    def _m_apply_preset_data(self, data: dict) -> None:
        try:
            self._m_instr_spin.setValue(int(data.get("instr", 1)))
        except (ValueError, TypeError):
            pass
        self._m_bidir_cb.setChecked(bool(data.get("bidir", True)))
        self._m_suppress_cb.setChecked(bool(data.get("suppress", True)))
        self._m_nocal_cb.setChecked(bool(data.get("nocal", False)))
        self._m_pbp_cb.setChecked(bool(data.get("pbp", False)))
        for opt in self._m_chartread_opts:
            if opt.checkbox:
                opt.checkbox.setChecked(bool(data.get(f"{opt.key}_enabled", False)))
            if opt.widget is not None:
                val = data.get(f"{opt.key}_value")
                if val is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        try:
                            opt.widget.setValue(float(val))
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(opt.widget, QComboBox):
                        idx = opt.widget.findData(str(val))
                        if idx >= 0:
                            opt.widget.setCurrentIndex(idx)

    def _on_m_preset_selected(self, index: int) -> None:
        self._m_preset_del_btn.setEnabled(index > 0)
        s = self._settings
        if index == 0:
            # Restore from individual manual2_chartread_* settings
            try:
                self._m_instr_spin.setValue(int(s.get("manual2_chartread_instr", 1)))
            except (ValueError, TypeError):
                pass
            self._m_bidir_cb.setChecked(bool(s.get("manual2_chartread_bidir", True)))
            self._m_suppress_cb.setChecked(bool(s.get("manual2_chartread_suppress", True)))
            self._m_nocal_cb.setChecked(bool(s.get("manual2_chartread_nocal", False)))
            self._m_pbp_cb.setChecked(bool(s.get("manual2_chartread_pbp", False)))
            for opt in self._m_chartread_opts:
                if opt.checkbox:
                    opt.checkbox.setChecked(bool(s.get(f"manual2_chartread_{opt.key}_enabled", False)))
                if opt.widget is not None:
                    val = s.get(f"manual2_chartread_{opt.key}_value")
                    if val is not None:
                        if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                            try:
                                opt.widget.setValue(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif isinstance(opt.widget, QComboBox):
                            idx = opt.widget.findData(str(val))
                            if idx >= 0:
                                opt.widget.setCurrentIndex(idx)
        else:
            name = self._m_preset_combo.currentData()
            presets = self._m_load_presets()
            self._m_apply_preset_data(presets.get(name, {}))

    def _on_m_preset_save(self) -> None:
        data = self._m_collect_preset_data()
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Save Preset")
        dlg.setLabelText(
            "Give this preset a name.\n"
            "All current Manual mode settings will be saved under that name\n"
            "and can be recalled at any time from the preset list."
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
        dlg.setWindowTitle("Delete Preset")
        dlg.setMinimumWidth(460)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(20, 20, 20, 16)
        heading = QLabel(f'Delete the preset "{name}"?', dlg)
        heading.setStyleSheet("font-weight: bold;")
        heading.setWordWrap(True)
        dlg_layout.addWidget(heading)
        info = QLabel(
            "All parameter values saved in this preset will be permanently removed. "
            "This cannot be undone.",
            dlg,
        )
        info.setWordWrap(True)
        dlg_layout.addWidget(info)
        bb = QDialogButtonBox(dlg)
        bb.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        del_btn = bb.addButton("Delete", QDialogButtonBox.ButtonRole.AcceptRole)
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
    # Chartread option rows (guided panel)
    # ------------------------------------------------------------------

    def _make_chartread_options(self, parent: QWidget) -> list[_ChartreadOption]:
        opts = []

        def _spinbox(lo, hi, step, default, decimals=0):
            if decimals > 0:
                sb = NoScrollDoubleSpinBox(parent)
                sb.setRange(lo, hi)
                sb.setSingleStep(step)
                sb.setDecimals(decimals)
                sb.setValue(default)
                sb.setFixedWidth(90)
            else:
                sb = NoScrollSpinBox(parent)
                sb.setRange(int(lo), int(hi))
                sb.setSingleStep(int(step))
                sb.setValue(int(default))
                sb.setFixedWidth(90)
            sb.setObjectName("compact_input")
            return sb

        opts.append(_ChartreadOption(
            key="highres", flag="-H",
            label="High resolution spectral mode (-H)",
            tooltip_title="High Resolution Spectral Mode (-H)",
            tooltip_body="Enables high-resolution spectral sampling on instruments that\n"
                         "support it (i1Pro 2/3).  Slightly slower but more accurate Lab values.",
        ))

        filter_combo = NoScrollComboBox(parent)
        filter_combo.setFixedWidth(130)
        filter_combo.setObjectName("compact_input")
        for code, lbl in [("n", "None (M0)"), ("5", "D50 (M1)"), ("6", "D65"), ("u", "UV Cut (M2)"), ("p", "Polarizing (M3)")]:
            filter_combo.addItem(lbl, code)
        filter_combo.setCurrentIndex(1)  # default to D50 (M1)
        opts.append(_ChartreadOption(
            key="filter", flag="-F",
            label="Spectral filter type (-F)",
            tooltip_title="Spectral Filter (-F)",
            tooltip_body=(
                "Overrides the filter configuration used by the instrument.\n"
                "Select the filter physically in use on your spectrophotometer:\n\n"
                "  n = None (M0 — default, no filter)\n"
                "  5 = D50 (M1 illuminant)\n"
                "  6 = D65 illuminant\n"
                "  u = UV Cut (M2)\n"
                "  p = Polarizing filter (M3)\n\n"
                "Only set this if you are using a specific filter or illuminant\n"
                "condition. Wrong selection will silently skew measured values."
            ),
            widget=filter_combo,
        ))

        opts.append(_ChartreadOption(
            key="tolerance", flag="-T",
            label="Patch consistency tolerance (-T)",
            tooltip_title="Patch Tolerance Multiplier (-T)",
            tooltip_body="Multiplies the default patch consistency tolerance.\n"
                         "Increase to 2.0–3.0 on textured or matte papers.\n"
                         "Default: 1.0",
            widget=_spinbox(0.1, 10.0, 0.1, 1.0, decimals=1),
        ))

        opts.append(_ChartreadOption(
            key="save_lab", flag="-l",
            label="Save L*a*b* instead of XYZ (-l)",
            tooltip_title="Save L*a*b* Values (-l)",
            tooltip_body="Saves measurement data as D50 L*a*b* instead of XYZ.\n"
                         "Most workflows use XYZ (default).  Enable only if downstream\n"
                         "tools require L*a*b* input.",
        ))

        opts.append(_ChartreadOption(
            key="save_lab_and_xyz", flag="-L",
            label="Save L*a*b* AND XYZ (-L)",
            tooltip_title="Save L*a*b* AND XYZ (-L)",
            tooltip_body="Saves both D50 L*a*b* and XYZ values in the .ti3 file.",
        ))

        # XRGA conversion combo
        xrga_combo = NoScrollComboBox(parent)
        xrga_combo.setFixedWidth(110)
        xrga_combo.setObjectName("compact_input")
        for code, lbl in [("N", "None"), ("A", "XRGA"), ("X", "XRDI"), ("G", "GMDI")]:
            xrga_combo.addItem(lbl, code)
        opts.append(_ChartreadOption(
            key="xrga", flag="-A",
            label="XRGA instrument correction (-A)",
            tooltip_title="XRGA Correction (-A)",
            tooltip_body="Apply an XRGA colorimetric correction to convert between\n"
                         "different spectrophotometer calibration standards.\n"
                         "N = none (default), A = XRGA, X = XRDI, G = GMDI.",
            widget=xrga_combo,
        ))

        return opts

    def _make_manual_chartread_options(self, parent: QWidget) -> list[_ChartreadOption]:
        """Mirror of _make_chartread_options for the manual panel."""
        opts = []

        def _spinbox(lo, hi, step, default, decimals=0):
            if decimals > 0:
                sb = NoScrollDoubleSpinBox(parent)
                sb.setRange(lo, hi)
                sb.setSingleStep(step)
                sb.setDecimals(decimals)
                sb.setValue(default)
                sb.setFixedWidth(90)
            else:
                sb = NoScrollSpinBox(parent)
                sb.setRange(int(lo), int(hi))
                sb.setSingleStep(int(step))
                sb.setValue(int(default))
                sb.setFixedWidth(90)
            sb.setObjectName("compact_input")
            return sb

        opts.append(_ChartreadOption(
            key="highres", flag="-H",
            label="High resolution spectral mode (-H)",
            tooltip_title="High Resolution Spectral Mode (-H)",
            tooltip_body="Enables high-resolution spectral sampling on instruments that\n"
                         "support it (i1Pro 2/3).  Slightly slower but more accurate Lab values.",
        ))

        filter_combo = NoScrollComboBox(parent)
        filter_combo.setFixedWidth(130)
        filter_combo.setObjectName("compact_input")
        for code, lbl in [("n", "None (M0)"), ("5", "D50 (M1)"), ("6", "D65"), ("u", "UV Cut (M2)"), ("p", "Polarizing (M3)")]:
            filter_combo.addItem(lbl, code)
        filter_combo.setCurrentIndex(1)
        opts.append(_ChartreadOption(
            key="filter", flag="-F",
            label="Spectral filter type (-F)",
            tooltip_title="Spectral Filter (-F)",
            tooltip_body=(
                "Overrides the filter configuration used by the instrument.\n"
                "Select the filter physically in use on your spectrophotometer:\n\n"
                "  n = None (M0 — default, no filter)\n"
                "  5 = D50 (M1 illuminant)\n"
                "  6 = D65 illuminant\n"
                "  u = UV Cut (M2)\n"
                "  p = Polarizing filter (M3)\n\n"
                "Only set this if you are using a specific filter or illuminant\n"
                "condition. Wrong selection will silently skew measured values."
            ),
            widget=filter_combo,
        ))

        opts.append(_ChartreadOption(
            key="tolerance", flag="-T",
            label="Patch consistency tolerance (-T)",
            tooltip_title="Patch Tolerance Multiplier (-T)",
            tooltip_body="Multiplies the default patch consistency tolerance.\n"
                         "Increase to 2.0–3.0 on textured or matte papers.\n"
                         "Default: 1.0",
            widget=_spinbox(0.1, 10.0, 0.1, 1.0, decimals=1),
        ))

        opts.append(_ChartreadOption(
            key="save_lab", flag="-l",
            label="Save L*a*b* instead of XYZ (-l)",
            tooltip_title="Save L*a*b* Values (-l)",
            tooltip_body="Saves measurement data as D50 L*a*b* instead of XYZ.\n"
                         "Most workflows use XYZ (default).  Enable only if downstream\n"
                         "tools require L*a*b* input.",
        ))

        opts.append(_ChartreadOption(
            key="save_lab_and_xyz", flag="-L",
            label="Save L*a*b* AND XYZ (-L)",
            tooltip_title="Save L*a*b* AND XYZ (-L)",
            tooltip_body="Saves both D50 L*a*b* and XYZ values in the .ti3 file.",
        ))

        xrga_combo = NoScrollComboBox(parent)
        xrga_combo.setFixedWidth(110)
        xrga_combo.setObjectName("compact_input")
        for code, lbl in [("N", "None"), ("A", "XRGA"), ("X", "XRDI"), ("G", "GMDI")]:
            xrga_combo.addItem(lbl, code)
        opts.append(_ChartreadOption(
            key="xrga", flag="-A",
            label="XRGA instrument correction (-A)",
            tooltip_title="XRGA Correction (-A)",
            tooltip_body="Apply an XRGA colorimetric correction to convert between\n"
                         "different spectrophotometer calibration standards.\n"
                         "N = none (default), A = XRGA, X = XRDI, G = GMDI.",
            widget=xrga_combo,
        ))

        return opts

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def set_ti1_path(self, path: Path) -> None:
        self._ti1_path = path
        self._ti1_lbl.setText(str(path))
        self._start_btn.setEnabled(True)
        self._try_load_tiffs(path)
        self._update_resume_availability()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_load_ti2(self) -> None:
        from ui.ti2_loader import resolve_ti2
        path = open_file_dialog(
            self, "Load .ti2 file", "TI2 files (*.ti2)",
            extra_path=self._settings.get("custom_output_path", ""),
        )
        if not path:
            return
        result = resolve_ti2(self, Path(path), self._settings)
        if result is None:
            return
        ti2_path, _ = result   # TIFFs re-discovered by set_ti1_path → _try_load_tiffs
        self.set_ti1_path(ti2_path)

    def _update_resume_availability(self) -> None:
        if self._ti1_path is None:
            for cb, tip, rcb in [
                (self._resume_cb,   self._resume_tip,   self._refine_cb),
                (self._m_resume_cb, self._m_resume_tip, self._m_refine_cb),
            ]:
                cb.setVisible(False)
                tip.setVisible(False)
                cb.setChecked(False)
                rcb.setEnabled(False)
                rcb.setChecked(False)
            self._refine_strips_path = None
            self._strip_list = []
            return
        ti3 = self._ti1_path.with_suffix(".ti3")
        has_ti3 = ti3.exists()
        for cb, tip in [
            (self._resume_cb,   self._resume_tip),
            (self._m_resume_cb, self._m_resume_tip),
        ]:
            cb.setVisible(has_ti3)
            tip.setVisible(has_ti3)
            if not has_ti3:
                cb.setChecked(False)
        # Auto-detect Refine_Strips file
        refine_file = self._ti1_path.parent / f"Refine_Strips_{self._ti1_path.stem}.txt"
        if refine_file.exists():
            self._refine_strips_path = refine_file
            self._load_refine_strips(refine_file)
            for rcb in (self._refine_cb, self._m_refine_cb):
                rcb.setEnabled(True)
                rcb.setChecked(True)
        else:
            self._refine_strips_path = None
            self._strip_list = []
            for rcb in (self._refine_cb, self._m_refine_cb):
                rcb.setEnabled(False)
                rcb.setChecked(False)

    def _load_refine_strips(self, path: Path) -> None:
        from workflow.profcheck_runner import parse_refine_strips
        try:
            self._strip_list = parse_refine_strips(path)
        except Exception:
            self._strip_list = []

    def start_guided_refinement(self, ti3: Path, strips_file: Path) -> None:
        """Called by main window when user launches guided refinement from Check & Refine tab."""
        ti2 = ti3.with_suffix(".ti2")
        if ti2.exists():
            self.set_ti1_path(ti2)
        self._resume_cb.setChecked(True)
        self._refine_strips_path = strips_file
        self._load_refine_strips(strips_file)
        self._refine_cb.setEnabled(True)
        self._refine_cb.setChecked(True)

    def _try_load_tiffs(self, base_path: Path) -> None:
        stem   = base_path.with_suffix("").stem
        folder = base_path.parent
        tiffs  = sorted(folder.glob(f"{stem}*.tif"))
        if tiffs:
            self._tiff_pages = tiffs
            self._preview.load_tiff(tiffs)
            self._setup_stripe_rects()
        else:
            self._preview.clear()
            self._log.appendPlainText(
                "[WARNING] No matching TIFF preview found. "
                "Ensure you scan the correct target."
            )
            self._log.ensureCursorVisible()

    def _setup_stripe_rects(self) -> None:
        """Detect strip positions from the first TIFF page and push to preview."""
        if not self._tiff_pages:
            return
        rects = _detect_stripe_rects(self._tiff_pages[0])
        if rects:
            self._preview.set_stripe_rects(rects)

    def _set_settings_enabled(self, enabled: bool) -> None:
        self._stack.setEnabled(enabled)
        self._file_grp.setEnabled(enabled)
        self._save_defaults_btn.setEnabled(enabled)

    def _on_start(self) -> None:
        if not self._ti1_path:
            self._log.appendPlainText("[ERROR] No .ti2 file selected.")
            self._log.ensureCursorVisible()
            return
        if self._runner.is_running:
            return

        params = self._collect_params()
        self._log.clear()
        self._auto_proceed = False
        self._all_done_shown = False
        self._instrument_disconnected = False
        self._device_busy = False
        self._no_instrument = False
        subprocess.run(["killall", "-q", "chartread"], capture_output=True)
        self._set_settings_enabled(False)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        QApplication.instance().installEventFilter(self)

        if self._current_mode() == "guided":
            resume_cb  = self._resume_cb
            refine_cb  = self._refine_cb
        else:
            resume_cb  = self._m_resume_cb
            refine_cb  = self._m_refine_cb
        guided = (
            resume_cb.isChecked()
            and refine_cb.isChecked()
            and bool(self._strip_list)
        )
        self._guided_refinement_active = guided
        self._resume_active = resume_cb.isChecked()

        self._manager.set_guided_strips(self._strip_list if guided else [])

        self._manager.start(
            params,
            on_line=self._on_log_line,
            on_finish=self._on_measure_done,
        )
        self.measurement_active.emit(True)

    def _on_stop(self) -> None:
        self._manager.abort()

    def _on_log_line(self, line: str) -> None:
        self._log.appendPlainText(line)
        self._log.ensureCursorVisible()
        # Only flag fatal errors — strip read failures are recoverable and handled
        # separately via the strip_error signal / dialog.
        if "communications failure" in line.lower():
            self._measure_failed = True

    def _on_wrong_strip(self, read: str, expected: str) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle("Wrong Strip Read")
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            f"<b>Strip {read} was read, but strip {expected} was expected.</b><br><br>"
            "This happens when the instrument is placed on the wrong stripe. "
            "You have three options:<br><br>"
            "&nbsp;&nbsp;<b>Use Anyway</b> — accept the reading for strip "
            f"{read} and continue. Use this if you intentionally read "
            f"{read} out of order.<br><br>"
            "&nbsp;&nbsp;<b>Retry</b> — discard this reading and try again. "
            f"Place your instrument at the correct position for strip {expected}.<br><br>"
            "&nbsp;&nbsp;<b>Give Up</b> — stop the measurement without saving.",
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["\r"]   # default: use anyway

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        use_btn   = QPushButton("Use Anyway", dlg)
        retry_btn = QPushButton("Retry",      dlg)
        give_btn  = QPushButton("Give Up",    dlg)
        use_btn.setObjectName("primary")
        use_btn.setFixedHeight(32)
        retry_btn.setFixedHeight(32)
        give_btn.setFixedHeight(32)

        def _use():
            chosen[0] = "\r"
            dlg.accept()

        def _retry():
            chosen[0] = " "
            dlg.accept()

        def _give_up():
            chosen[0] = "\x1b"
            dlg.accept()

        use_btn.clicked.connect(_use)
        retry_btn.clicked.connect(_retry)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(use_btn)
        btn_row.addWidget(retry_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])

        if chosen[0] != "\x1b":
            QApplication.instance().installEventFilter(self)
        # If giving up, chartread will exit and _on_measure_done re-enables UI.

    def _on_unexpected_response(self, delta_e: str) -> None:
        from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle("Unexpected Color Response")
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            f"<b>An unexpected color response was detected (ΔE {delta_e}).</b><br><br>"
            "This usually means the instrument was not aligned correctly with "
            "the stripe, was moved during the scan, or the wrong stripe was read. "
            "A ΔE this high indicates the measured colors are very far from what "
            "is expected.<br><br>"
            "&nbsp;&nbsp;<b>Use Anyway</b> — accept the reading and continue. "
            "Only use this if you are sure the scan was correct.<br><br>"
            "&nbsp;&nbsp;<b>Retry</b> — discard this reading, re-position your "
            "instrument carefully on the correct stripe, and try again.<br><br>"
            "&nbsp;&nbsp;<b>Give Up</b> — stop the measurement without saving.",
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["\r"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        use_btn   = QPushButton("Use Anyway", dlg)
        retry_btn = QPushButton("Retry",      dlg)
        give_btn  = QPushButton("Give Up",    dlg)
        use_btn.setObjectName("primary")
        use_btn.setFixedHeight(32)
        retry_btn.setFixedHeight(32)
        give_btn.setFixedHeight(32)

        def _use():
            chosen[0] = "\r"
            dlg.accept()

        def _retry():
            chosen[0] = " "
            dlg.accept()

        def _give_up():
            chosen[0] = "\x1b"
            dlg.accept()

        use_btn.clicked.connect(_use)
        retry_btn.clicked.connect(_retry)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(use_btn)
        btn_row.addWidget(retry_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])

        if chosen[0] != "\x1b":
            QApplication.instance().installEventFilter(self)

    def _on_sensor_wrong_position(self) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle("Instrument in Wrong Position")
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            "<b>The measurement device is in the wrong position.</b><br><br>"
            "It looks like the instrument is still in its <b>calibration position</b> "
            "(sensor facing up or to the side). "
            "To scan a strip, it needs to be switched to <b>measuring position</b> "
            "(sensor facing down, resting on the paper).<br><br>"
            "How to fix it:<br>"
            "&nbsp;&nbsp;1. Flip or slide the sensor head so it faces <b>downward</b>.<br>"
            "&nbsp;&nbsp;2. Place the instrument at the beginning of the strip.<br>"
            "&nbsp;&nbsp;3. Press <b>OK</b> — chartread is still waiting and you can scan straight away.",
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        QApplication.instance().installEventFilter(self)

    def _on_device_busy(self) -> None:
        if self._device_busy:
            return
        self._device_busy = True

    def _on_no_instrument(self) -> None:
        self._no_instrument = True

    def _on_instrument_disconnected(self) -> None:
        if self._instrument_disconnected:
            return
        self._instrument_disconnected = True
        self._log.appendPlainText(
            "\n[ERROR] Instrument disconnected — stopping measurement."
        )
        self._log.ensureCursorVisible()
        self._manager.abort()

    def _on_strip_error(self, reason: str) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle("Strip Read Failed")
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            f"<b>The stripe could not be read:</b> {reason}<br><br>"
            "Re-position your instrument at the beginning of the stripe and try again. "
            "If the error keeps occurring, try scanning more slowly and steadily.<br><br>"
            "Click <b>Retry</b> to read the stripe again, or <b>Give Up</b> to skip "
            "it and continue with the remaining stripes.",
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_box = QDialogButtonBox()
        retry_btn = btn_box.addButton("Retry", QDialogButtonBox.ButtonRole.AcceptRole)
        retry_btn.setObjectName("primary")
        btn_box.addButton("Give Up", QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._manager.send_key("\r")   # any key = retry
        else:
            self._manager.send_key("\x1b") # Esc = give up on this stripe

        QApplication.instance().installEventFilter(self)

    def _on_calibration_prompt(self) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle("Calibration Required")
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            "<b>Your instrument needs to be calibrated before measuring.</b><br><br>"
            "Place the instrument in the <b>calibration position</b> as described "
            "in its manual, then click <b>Start Calibration</b>.<br><br>"
            "The calibration takes only a few seconds. Once it is complete, another "
            "message will appear with instructions on how to start measuring the "
            "stripes.",
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_box = QDialogButtonBox()
        ok_btn = btn_box.addButton("Start Calibration", QDialogButtonBox.ButtonRole.AcceptRole)
        ok_btn.setObjectName("primary")
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        # Send any key to tell chartread to proceed with calibration.
        self._manager.send_key("\r")
        QApplication.instance().installEventFilter(self)

    def _on_calibration_done(self) -> None:
        from PyQt6.QtWidgets import (
            QDialog, QDialogButtonBox, QFrame, QGridLayout, QLabel, QVBoxLayout,
        )

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        _frame_style = (
            "QFrame { background: #181818; border: 1px solid #2a2a2a; border-radius: 6px; }"
        )
        _key_style = (
            f"font-family: Menlo, monospace; font-weight: 700; color: {_TAB_COLOR};"
            " background: transparent; border: none;"
        )
        _dim_style = "color: #909090; background: transparent; border: none;"
        _plain_style = "background: transparent; border: none;"

        if self._guided_refinement_active and self._strip_list:
            first = self._strip_list[0]
            n = len(self._strip_list)
            dlg.setWindowTitle("Calibration Complete — Guided Refinement Ready")

            msg = QLabel(
                "<b>Calibration complete. The app will guide you to each strip.</b><br><br>"
                f"There are <b>{n} strip(s)</b> to re-measure. "
                "The app will automatically navigate chartread to each one — "
                "<b>you do not need to press f or b yourself.</b>",
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)

            hint_frame = QFrame(dlg)
            hint_frame.setStyleSheet(_frame_style)
            hfl = QVBoxLayout(hint_frame)
            hfl.setContentsMargins(16, 12, 16, 12)
            hfl.setSpacing(6)
            hdr = QLabel("To identify which strip to scan:", dlg)
            hdr.setStyleSheet("font-weight: 600; " + _plain_style)
            hfl.addWidget(hdr)
            for bullet_text in (
                "Watch the <b>highlighted strip</b> in the preview panel on the right.",
                "Or follow the <b>output field</b> below — it will name the strip.",
            ):
                b = QLabel(f"  •  {bullet_text}", dlg)
                b.setWordWrap(True)
                b.setStyleSheet(_plain_style)
                hfl.addWidget(b)
            layout.addWidget(hint_frame)

            first_lbl = QLabel(
                f"<b>First strip: {first}</b> — place your instrument there and scan when ready.",
                dlg,
            )
            first_lbl.setWordWrap(True)
            layout.addWidget(first_lbl)

            footnote = QLabel(
                "When all strips are done, the output field will tell you to press ‘d’ to finish and save.",
                dlg,
            )
            footnote.setWordWrap(True)
            footnote.setStyleSheet(_dim_style)
            layout.addWidget(footnote)

        elif self._resume_active:
            dlg.setWindowTitle("Calibration Complete — Manual Re-measurement")

            msg = QLabel(
                "<b>Calibration complete. You are ready to re-measure strips manually.</b><br><br>"
                "chartread will show you each strip in order. Strips already measured are "
                "marked with <i>(!! ALL ROWS READ !!)</i> — skip or re-scan as needed.",
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)

            step_frame = QFrame(dlg)
            step_frame.setStyleSheet(_frame_style)
            sfl = QGridLayout(step_frame)
            sfl.setContentsMargins(16, 12, 16, 12)
            sfl.setHorizontalSpacing(14)
            sfl.setVerticalSpacing(7)
            sfl.setColumnStretch(1, 1)
            steps = [
                ("1.", "Press <b>f</b> (forward) or <b>b</b> (back) until chartread shows the strip you want."),
                ("2.", "Place your instrument on that strip and scan it."),
                ("3.", "Repeat for each strip you want to update, then press <b>d</b> to finish and save."),
            ]
            for row, (num, text) in enumerate(steps):
                n_lbl = QLabel(num)
                n_lbl.setStyleSheet(_key_style)
                n_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
                t_lbl = QLabel(text)
                t_lbl.setWordWrap(True)
                t_lbl.setStyleSheet(_plain_style)
                sfl.addWidget(n_lbl, row, 0)
                sfl.addWidget(t_lbl, row, 1)
            layout.addWidget(step_frame)

            footnote = QLabel(
                "<b>n</b> jumps to the next unread strip  —  <b>Esc / q</b> quits without saving.",
                dlg,
            )
            footnote.setWordWrap(True)
            footnote.setStyleSheet(_dim_style)
            layout.addWidget(footnote)

        else:
            dlg.setWindowTitle("Calibration Complete — How to Measure")

            msg = QLabel(
                "<b>Calibration complete. You are ready to start measuring.</b><br><br>"
                "Place your instrument at the beginning of the first stripe and trigger it to scan. "
                "Then proceed stripe by stripe until all are done.",
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)

            key_frame = QFrame(dlg)
            key_frame.setStyleSheet(_frame_style)
            kfl = QGridLayout(key_frame)
            kfl.setContentsMargins(16, 12, 16, 12)
            kfl.setHorizontalSpacing(20)
            kfl.setVerticalSpacing(6)
            kfl.setColumnStretch(1, 1)
            key_rows = [
                ("f", "Move to the next stripe"),
                ("b", "Move back to the previous stripe"),
                ("n", "Jump to the next unread stripe"),
                ("d", "Finish and save when all stripes are done"),
                ("Esc / q", "Quit without saving"),
            ]
            for row, (key, desc) in enumerate(key_rows):
                k = QLabel(key)
                k.setStyleSheet(_key_style)
                d = QLabel(desc)
                d.setStyleSheet(_plain_style)
                kfl.addWidget(k, row, 0, Qt.AlignmentFlag.AlignLeft)
                kfl.addWidget(d, row, 1, Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(key_frame)

            footnote = QLabel("These instructions are always visible in the output log below.", dlg)
            footnote.setWordWrap(True)
            footnote.setStyleSheet(_dim_style)
            layout.addWidget(footnote)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setObjectName("primary")
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        QApplication.instance().installEventFilter(self)

    def _on_all_stripes_done(self) -> None:
        if self._all_done_shown:
            return
        self._all_done_shown = True

        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        # Suspend the event filter while the dialog is open so that keyboard
        # interactions with the dialog (Enter, Space, Esc) are not forwarded
        # to chartread as spurious keystrokes.
        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        if self._guided_refinement_active:
            n = len(self._strip_list)
            dlg.setWindowTitle("Re-measurement Complete")
            msg = QLabel(
                f"<b>All {n} target strip(s) have been re-measured successfully.</b><br><br>"
                "What would you like to do next?<br><br>"
                "&nbsp;&nbsp;•&nbsp; <b>Build Profile</b> — saves the measurement "
                "and takes you straight to the Build Profile tab to create your updated "
                "ICC profile.<br><br>"
                "&nbsp;&nbsp;•&nbsp; <b>Continue Measuring Manually</b> — keeps "
                "chartread running so you can scan additional strips yourself. "
                "You will have <b>full manual control</b>: use <b>f</b>&nbsp;/&nbsp;<b>b</b> "
                "to move between strips, <b>n</b> to jump to the next unread one, and "
                "<b>d</b> when you are done. "
                "The automatic strip navigation is switched off for the rest of this session.",
                dlg,
            )
        else:
            dlg.setWindowTitle("All Stripes Read")
            msg = QLabel(
                "<b>All stripes have been read successfully.</b><br><br>"
                "Click <b>Build Profile</b> to finalise the measurement and go directly "
                "to the Build Profile tab — the next and final step.<br><br>"
                "If you would like to re-read any stripe first, click <b>Re-read Stripes</b>. "
                "Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move forward and back between stripes, "
                "<b>n</b> to jump to the next unread stripe, and press <b>d</b> when you "
                "are done.<br><br>"
                "<span style='color:#909090;'>These instructions are always visible in "
                "the output log below.</span>",
                dlg,
            )

        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_box = QDialogButtonBox()
        build_btn = btn_box.addButton("Build Profile →", QDialogButtonBox.ButtonRole.AcceptRole)
        build_btn.setObjectName("primary")
        cont_label = "Continue Measuring Manually" if self._guided_refinement_active else "Re-read Stripes"
        btn_box.addButton(cont_label, QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._auto_proceed = True
            self._manager.send_key("d")
            # Event filter stays off — chartread will finish momentarily.
        else:
            if self._guided_refinement_active:
                # Hand back full keyboard control; disable auto-navigation.
                self._guided_refinement_active = False
                self._manager.set_guided_strips([])
            QApplication.instance().installEventFilter(self)

    def _on_measure_done(self, code: int) -> None:
        self.measurement_active.emit(False)
        QApplication.instance().removeEventFilter(self)
        self._set_settings_enabled(True)
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        if self._no_instrument:
            self._no_instrument = False
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle("No Instrument Found")
            dlg.setMinimumWidth(460)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                "<b>No measurement instrument was detected.</b><br><br>"
                "Please make sure your instrument is:<br>"
                "&nbsp;&nbsp;• connected to your Mac via USB<br>"
                "&nbsp;&nbsp;• switched on<br>"
                "&nbsp;&nbsp;• not in use by another application<br><br>"
                "Once the instrument is ready, press <b>Start Measurement</b> again.",
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        if self._device_busy:
            self._device_busy = False
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle("Instrument Not Available")
            dlg.setMinimumWidth(480)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                "<b>The instrument could not be opened — it is already in use by "
                "another process.</b><br><br>"
                "This usually happens when a previous measurement session was not "
                "stopped properly before closing the app. ChromIQ automatically "
                "tries to free the device when starting a new measurement.<br><br>"
                "Please click OK and then press <b>Start Measurement</b> again.",
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        if self._instrument_disconnected:
            self._instrument_disconnected = False
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle("Instrument Disconnected")
            dlg.setMinimumWidth(460)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                "<b>The measurement instrument was disconnected.</b><br><br>"
                "The measurement has been stopped automatically. Please check "
                "the USB connection, reconnect your instrument, and start a "
                "new measurement.",
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        # chartread exits non-zero even on a clean 'd' (done) completion.
        # Treat as success if the .ti3 file was actually written.
        ti3 = self._ti1_path.with_suffix(".ti3") if self._ti1_path else None
        ti3_exists = ti3 is not None and ti3.exists()
        failed = self._measure_failed or (code != 0 and not ti3_exists)
        self._measure_failed = False

        if failed:
            self._log.appendPlainText("\n[ERROR] Measurement failed — see output above.")
        else:
            self._log.appendPlainText(
                "\n[OK] Measurement complete.\n"
                f"Saved: {ti3}\n\n"
                "→ Next step: go to the '4. Build Profile' tab to create your ICC profile."
            )
            if ti3_exists:
                self.measure_finished.emit(ti3)
                if self._auto_proceed:
                    self.proceed_to_profile.emit()
        self._auto_proceed = False
        self._log.ensureCursorVisible()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self._manager.send_key("\x1b")
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._manager.send_key("\r")
            elif key == Qt.Key.Key_Space:
                self._manager.send_key(" ")
            elif key == Qt.Key.Key_Left:
                self._manager.send_key("\x1b[D")
            elif key == Qt.Key.Key_Right:
                self._manager.send_key("\x1b[C")
            else:
                text = event.text()
                if text:
                    self._manager.send_key(text)
            return True   # consume — don't let widgets act on it
        return False

    def _on_stripe_changed(self, strip_id: str) -> None:
        self._log.appendPlainText(f"[→ strip {strip_id}]")
        self._log.ensureCursorVisible()
        letter = "".join(c for c in strip_id if c.isalpha()).upper()
        if not letter:
            return
        rects = self._preview._stripe_rects
        if not rects:
            return
        global_idx     = letter_to_idx(letter)
        strips_per_page = len(rects)
        page            = global_idx // strips_per_page
        local_idx       = global_idx % strips_per_page
        n_pages         = max(1, len(self._tiff_pages))
        if 0 <= page < n_pages:
            self._preview.show_page(page)
        self._preview.highlight_stripe(local_idx)

    # ------------------------------------------------------------------
    # Param collection
    # ------------------------------------------------------------------

    def _collect_guided(self) -> MeasureParams:
        extra_args: list[str] = []
        for opt in self._chartread_opts:
            extra_args += opt.build_args()

        return MeasureParams(
            ti1_path            = self._ti1_path,
            instrument          = str(self._instr_spin.value()),
            disable_bidir       = self._bidir_cb.isChecked(),
            suppress_warnings   = self._suppress_cb.isChecked(),
            disable_initial_cal = self._nocal_cb.isChecked(),
            patch_by_patch      = self._pbp_cb.isChecked(),
            resume              = self._resume_cb.isChecked(),
            extra_args          = " ".join(extra_args),
        )

    def _collect_manual(self) -> MeasureParams:
        extra_args: list[str] = []
        for opt in self._m_chartread_opts:
            extra_args += opt.build_args()

        return MeasureParams(
            ti1_path            = self._ti1_path,
            instrument          = str(self._m_instr_spin.value()),
            disable_bidir       = self._m_bidir_cb.isChecked(),
            suppress_warnings   = self._m_suppress_cb.isChecked(),
            disable_initial_cal = self._m_nocal_cb.isChecked(),
            patch_by_patch      = self._m_pbp_cb.isChecked(),
            resume              = self._m_resume_cb.isChecked(),
            extra_args          = " ".join(extra_args),
        )

    def _collect_params(self) -> MeasureParams:
        if self._current_mode() == "guided":
            return self._collect_guided()
        return self._collect_manual()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _on_save_defaults(self) -> None:
        s = self._settings
        if self._current_mode() == "guided":
            s.set("measure_disable_bidir",     self._bidir_cb.isChecked())
            s.set("measure_suppress_warnings", self._suppress_cb.isChecked())
            s.set("measure_no_cal",            self._nocal_cb.isChecked())
            s.set("measure_patch_by_patch",    self._pbp_cb.isChecked())
            for opt in self._chartread_opts:
                if opt.checkbox:
                    s.set(f"measure_{opt.key}_enabled", opt.checkbox.isChecked())
                if opt.widget is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        s.set(f"measure_{opt.key}_value", opt.widget.value())
                    elif isinstance(opt.widget, QComboBox):
                        s.set(f"measure_{opt.key}_value", opt.widget.currentData())
        else:
            s.set("manual2_chartread_instr",    self._m_instr_spin.value())
            s.set("manual2_chartread_bidir",    self._m_bidir_cb.isChecked())
            s.set("manual2_chartread_suppress", self._m_suppress_cb.isChecked())
            s.set("manual2_chartread_nocal",    self._m_nocal_cb.isChecked())
            s.set("manual2_chartread_pbp",      self._m_pbp_cb.isChecked())
            for opt in self._m_chartread_opts:
                if opt.checkbox:
                    s.set(f"manual2_chartread_{opt.key}_enabled", opt.checkbox.isChecked())
                if opt.widget is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        s.set(f"manual2_chartread_{opt.key}_value", opt.widget.value())
                    elif isinstance(opt.widget, QComboBox):
                        s.set(f"manual2_chartread_{opt.key}_value", opt.widget.currentData())
        self._log.appendPlainText("Measurement settings saved as defaults.")
        self._log.ensureCursorVisible()

    def _restore_defaults(self) -> None:
        s = self._settings
        # Guided defaults
        self._bidir_cb.setChecked(bool(s.get("measure_disable_bidir", True)))
        self._suppress_cb.setChecked(bool(s.get("measure_suppress_warnings", True)))
        self._nocal_cb.setChecked(bool(s.get("measure_no_cal", False)))
        self._pbp_cb.setChecked(bool(s.get("measure_patch_by_patch", False)))
        for opt in self._chartread_opts:
            if opt.checkbox:
                enabled = bool(s.get(f"measure_{opt.key}_enabled", False))
                opt.checkbox.setChecked(enabled)
            if opt.widget is not None:
                val = s.get(f"measure_{opt.key}_value")
                if val is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        try:
                            opt.widget.setValue(float(val))
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(opt.widget, QComboBox):
                        idx = opt.widget.findData(str(val))
                        if idx >= 0:
                            opt.widget.setCurrentIndex(idx)
        # Manual defaults
        m_instr = s.get("manual2_chartread_instr")
        if m_instr is not None:
            try:
                self._m_instr_spin.setValue(int(m_instr))
            except (ValueError, TypeError):
                pass
        self._m_bidir_cb.setChecked(bool(s.get("manual2_chartread_bidir", True)))
        self._m_suppress_cb.setChecked(bool(s.get("manual2_chartread_suppress", True)))
        self._m_nocal_cb.setChecked(bool(s.get("manual2_chartread_nocal", False)))
        self._m_pbp_cb.setChecked(bool(s.get("manual2_chartread_pbp", False)))
        for opt in self._m_chartread_opts:
            if opt.checkbox:
                enabled = bool(s.get(f"manual2_chartread_{opt.key}_enabled", False))
                opt.checkbox.setChecked(enabled)
            if opt.widget is not None:
                val = s.get(f"manual2_chartread_{opt.key}_value")
                if val is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        try:
                            opt.widget.setValue(float(val))
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(opt.widget, QComboBox):
                        idx = opt.widget.findData(str(val))
                        if idx >= 0:
                            opt.widget.setCurrentIndex(idx)
        presets = self._m_load_presets()
        self._m_populate_preset_combo(presets)
