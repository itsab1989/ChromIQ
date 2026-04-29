"""Tab 3: Measure Chart."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QRect, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
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

        left_scroll = QScrollArea(left_container)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(left_scroll.Shape.NoFrame)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 12, 16, 12)
        ll.setSpacing(10)

        ll.addWidget(TabHeader(
            "STEP 03 · MEASURE TARGET", "Measure printed chart", "#56d6a5", left
        ))

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
            row.addWidget(TooltipButton(tt_title, tt_body, left))
            cg.addLayout(row)
            return cb

        self._bidir_cb = _bool_row(
            "Disable bidirectional strip recognition (-B)", True,
            "Disable Bidirectional Reading (-B)",
            "Strongly recommended ON.  Prevents mis-reads from scanning\n"
            "strips in the wrong direction.",
        )
        self._suppress_cb = _bool_row(
            "Suppress warning messages (-S)", True,
            "Suppress Warnings (-S)",
            "Suppresses non-fatal instrument warnings during measurement.",
        )
        self._nocal_cb = _bool_row(
            "Skip initial calibration (-N)", False,
            "Skip Initial Calibration (-N)",
            "Skips the white-tile calibration at startup.  Only use if you\n"
            "have already calibrated in this session.",
        )
        self._pbp_cb = _bool_row(
            "Patch-by-patch mode (-p)", False,
            "Patch-by-Patch Mode (-p)",
            "Measure each patch individually instead of reading strips.\n"
            "Much slower but useful if strip reading fails.",
        )

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

            # Enable checkbox
            cb = QCheckBox(opt.label, left)
            cb.setChecked(False)
            opt.checkbox = cb

            # Value widget setup
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

        # File selection
        self._file_grp = file_grp = QGroupBox("Target File (.ti2)", left)
        file_grp.setFlat(True)
        fg = QVBoxLayout(file_grp)
        fg.setContentsMargins(8, 6, 8, 8)
        file_row = QHBoxLayout()
        self._load_ti1_btn = QPushButton("Load .ti2 file…", left)
        self._load_ti1_btn.setIcon(load_folder_icon("folder_measure"))
        self._load_ti1_btn.clicked.connect(self._on_load_ti2)
        self._ti1_lbl = QLabel("No file selected", left)
        self._ti1_lbl.setStyleSheet("color: #909090; font-size: 11px;")
        self._ti1_lbl.setWordWrap(True)
        file_row.addWidget(self._load_ti1_btn)
        file_row.addWidget(self._ti1_lbl, stretch=1)
        fg.addLayout(file_row)
        ll.addWidget(file_grp)
        ll.addStretch(1)

        # Buttons
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Measurement", left)
        self._start_btn.setObjectName("primary")
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn = QPushButton("Stop", left)
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.setStyleSheet(
            "QPushButton { background: #f4f4f4; color: #121212; border: 1px solid #cccccc; font-weight: 600; }"
            "QPushButton:hover { background: #e0e0e0; border-color: #bbbbbb; }"
            "QPushButton:disabled { background: #2a2a2a; color: #555555; border-color: #333333; }"
        )
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        self._save_defaults_btn = QPushButton("Save as Defaults", left)
        self._save_defaults_btn.setFixedHeight(36)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        ll.addLayout(btn_row)

        # Log
        self._log = QPlainTextEdit(left)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(100)
        self._log.setMaximumHeight(100)
        self._log.setPlaceholderText("chartread output will appear here…")
        ll.addWidget(self._log)

        left_scroll.setWidget(left)
        lc_layout.addWidget(left_scroll, stretch=1)

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
    # Chartread option rows
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
            self._resume_cb.setVisible(False)
            self._resume_tip.setVisible(False)
            self._resume_cb.setChecked(False)
            self._refine_cb.setEnabled(False)
            self._refine_cb.setChecked(False)
            self._refine_strips_path = None
            self._strip_list = []
            return
        ti3 = self._ti1_path.with_suffix(".ti3")
        has_ti3 = ti3.exists()
        self._resume_cb.setVisible(has_ti3)
        self._resume_tip.setVisible(has_ti3)
        if not has_ti3:
            self._resume_cb.setChecked(False)
        # Auto-detect Refine_Strips file
        refine_file = self._ti1_path.parent / f"Refine_Strips_{self._ti1_path.stem}.txt"
        if refine_file.exists():
            self._refine_strips_path = refine_file
            self._load_refine_strips(refine_file)
            self._refine_cb.setEnabled(True)
            self._refine_cb.setChecked(True)
        else:
            self._refine_strips_path = None
            self._strip_list = []
            self._refine_cb.setEnabled(False)
            self._refine_cb.setChecked(False)

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
        for w in (self._instr_grp, self._core_grp, self._adv_grp,
                  self._file_grp, self._save_defaults_btn):
            w.setEnabled(enabled)

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

        guided = (
            self._resume_cb.isChecked()
            and self._refine_cb.isChecked()
            and bool(self._strip_list)
        )
        self._guided_refinement_active = guided
        self._resume_active = self._resume_cb.isChecked()
        self._manager.set_guided_strips(self._strip_list if guided else [])

        self._manager.start(
            params,
            on_line=self._on_log_line,
            on_finish=self._on_measure_done,
        )

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
            "&nbsp;&nbsp;3. Press <b>OK</b> \u2014 chartread is still waiting and you can scan straight away.",
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
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        if self._guided_refinement_active and self._strip_list:
            # Semi-automatic: app navigates to each strip automatically
            first = self._strip_list[0]
            n = len(self._strip_list)
            dlg.setWindowTitle("Calibration Complete \u2014 Guided Refinement Ready")
            msg = QLabel(
                "<b>Calibration complete. The app will guide you to each strip.</b><br><br>"
                f"There are <b>{n} strip(s)</b> to re-measure. "
                "The app will automatically navigate chartread to each one \u2014 "
                "<b>you do not need to press f or b yourself.</b><br><br>"
                "To know which strip to scan:<br>"
                "&nbsp;&nbsp;\u2022&nbsp; Watch the <b>highlighted strip</b> in the preview panel on the right.<br>"
                "&nbsp;&nbsp;\u2022&nbsp; Or follow the <b>output field</b> below \u2014 it will name the strip you should place your instrument on.<br><br>"
                f"<b>First strip: {first}</b> \u2014 place your instrument there and scan when ready.<br><br>"
                "<span style='color:#909090;'>When all strips are done, the output field will tell you to press \u2018d\u2019 to finish and save.</span>",
                dlg,
            )
        elif self._resume_active:
            # Manual resume: user navigates to strips themselves
            dlg.setWindowTitle("Calibration Complete \u2014 Manual Re-measurement")
            msg = QLabel(
                "<b>Calibration complete. You are ready to re-measure strips manually.</b><br><br>"
                "chartread will show you each strip in order. Strips that were already "
                "measured are marked with <i>(!! ALL ROWS READ !!)</i> \u2014 you can "
                "skip those or scan them again if you want to update them.<br><br>"
                "<b>To re-measure a specific strip:</b><br>"
                "&nbsp;&nbsp;1. Press <b>f</b> to move forward or <b>b</b> to move back "
                "until chartread shows the strip you want.<br>"
                "&nbsp;&nbsp;2. Place your instrument on that strip and scan it.<br>"
                "&nbsp;&nbsp;3. Repeat for each strip you want to update.<br><br>"
                "When you are done, press <b>d</b> to finish and save.<br><br>"
                "<span style='color:#909090;'><b>n</b> jumps to the next unread strip &nbsp;\u2014&nbsp; "
                "<b>Esc / q</b> quits without saving.</span>",
                dlg,
            )
        else:
            # Standard fresh measurement
            dlg.setWindowTitle("Calibration Complete \u2014 How to Measure")
            msg = QLabel(
                "<b>Calibration complete. You are ready to start measuring.</b><br><br>"
                "Put your instrument into measuring position, place it at the beginning "
                "of the first stripe and trigger it to read that stripe. "
                "Then proceed stripe by stripe until all are done.<br><br>"
                "<b>Navigation keys:</b><br>"
                "&nbsp;&nbsp;<b>f</b> &nbsp;\u2014 move to the next stripe<br>"
                "&nbsp;&nbsp;<b>b</b> &nbsp;\u2014 move back to the previous stripe<br>"
                "&nbsp;&nbsp;<b>n</b> &nbsp;\u2014 jump to the next unread stripe<br>"
                "&nbsp;&nbsp;<b>d</b> &nbsp;\u2014 finish and save when all stripes are done<br>"
                "&nbsp;&nbsp;<b>Esc&nbsp;/&nbsp;q</b> &nbsp;\u2014 quit without saving<br><br>"
                "<span style='color:#909090;'>These instructions are always visible "
                "in the output log below.</span>",
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
                "&nbsp;&nbsp;\u2022&nbsp; <b>Build Profile</b> \u2014 saves the measurement "
                "and takes you straight to the Build Profile tab to create your updated "
                "ICC profile.<br><br>"
                "&nbsp;&nbsp;\u2022&nbsp; <b>Continue Measuring Manually</b> \u2014 keeps "
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
                "to the Build Profile tab \u2014 the next and final step.<br><br>"
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
        build_btn = btn_box.addButton("Build Profile \u2192", QDialogButtonBox.ButtonRole.AcceptRole)
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

    def _collect_params(self) -> MeasureParams:
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

    def _on_save_defaults(self) -> None:
        s = self._settings
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
        self._log.appendPlainText("Measurement settings saved as defaults.")
        self._log.ensureCursorVisible()

    def _restore_defaults(self) -> None:
        s = self._settings
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
