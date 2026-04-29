"""Tab 1: Chart Creation — Guided and Manual modes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.resource_path import resource_path
from data.patch_db import (
    EXCLUDED_PAPERS,
    INSTRUMENT_LABELS,
    PAPER_FALLBACK,
    PAPER_LABELS,
    PAPER_SIZES,
    query_patches,
)
from ui.parameter_widget import ParameterWidget
from ui.styles import SPEC_AMBER, SPEC_CYAN, SPEC_GREEN, SPEC_MAGENTA, SPEC_VIOLET
from ui.tab_header import TabHeader
from ui.tiff_preview import TiffPreview
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox, NoScrollSpinBox, load_folder_icon, open_file_dialog
from workflow.chart_creator import ChartCreator, ChartParams

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings

log = get_logger(__name__)


class TabChart(QWidget):
    """Step 1: create targen/printtarg test chart."""

    chart_finished = pyqtSignal(object, object)  # (list[Path] tiffs, Path ti2)

    def __init__(
        self,
        runner: "ArgyllRunner",
        file_mgr: "FileManager",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner  = runner
        self._file_mgr = file_mgr
        self._settings = settings
        self._creator  = ChartCreator(runner, file_mgr, settings)
        self._params   = self._load_yaml_params()

        self._build_ui()
        self._restore_defaults()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(4)

        # Left: controls
        left = QWidget(self)
        self._left_panel = left
        left.setFixedWidth(700)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 12, 16, 12)
        left_layout.setSpacing(14)

        left_layout.addWidget(TabHeader(
            "STEP 01 · GENERATE TARGET", "Create test chart", "#ff4573", left
        ))

        # Mode switcher
        mode_row = QHBoxLayout()
        _mode_font = QFont("Menlo", 11, QFont.Weight.Medium)
        self._guided_btn = QPushButton("GUIDED", self)
        self._guided_btn.setCheckable(True)
        self._guided_btn.setChecked(True)
        self._guided_btn.setObjectName("mode_btn")
        self._guided_btn.setFont(_mode_font)
        self._manual_btn = QPushButton("MANUAL", self)
        self._manual_btn.setCheckable(True)
        self._manual_btn.setObjectName("mode_btn")
        self._manual_btn.setFont(_mode_font)
        self._guided_btn.clicked.connect(lambda: self._switch_mode("guided"))
        self._manual_btn.clicked.connect(lambda: self._switch_mode("manual"))
        mode_row.addWidget(self._guided_btn)
        mode_row.addWidget(self._manual_btn)
        mode_row.addStretch()
        left_layout.addLayout(mode_row)

        # Stacked panel
        self._stack = QStackedWidget(self)
        self._guided_panel = self._make_guided_panel()
        self._manual_panel = self._make_manual_panel()
        self._stack.addWidget(self._guided_panel)
        self._stack.addWidget(self._manual_panel)
        left_layout.addWidget(self._stack, stretch=1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        self._generate_btn = QPushButton("Generate Chart", self)
        self._generate_btn.setObjectName("primary")
        self._generate_btn.setFixedHeight(36)
        self._generate_btn.clicked.connect(self._on_generate)

        self._load_ti1_btn = QPushButton("Load existing .ti1…", self)
        self._load_ti1_btn.setFixedHeight(36)
        self._load_ti1_btn.setIcon(load_folder_icon("folder_create"))
        self._load_ti1_btn.clicked.connect(self._on_load_ti1)

        self._save_defaults_btn = QPushButton("Save as Defaults", self)
        self._save_defaults_btn.setFixedHeight(36)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)

        btn_row.addWidget(self._generate_btn)
        btn_row.addWidget(self._load_ti1_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        left_layout.addLayout(btn_row)

        # Log output
        from PyQt6.QtWidgets import QPlainTextEdit
        self._log = QPlainTextEdit(self)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(67)
        self._log.setPlaceholderText("Output will appear here…")
        left_layout.addWidget(self._log)

        # Status bar (replaces main-window status bar)
        self._status_bar_lbl = QLabel("", left)
        self._status_bar_lbl.setWordWrap(True)
        self._status_bar_lbl.setVisible(False)
        left_layout.addWidget(self._status_bar_lbl)

        splitter.addWidget(left)

        # Right: TIFF preview
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 12)
        lbl = QLabel("CHART PREVIEW", right)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "color: #808080; background: transparent; padding: 4px;"
            " font-family: Menlo; font-size: 9pt; font-weight: 300;"
        )
        right_layout.addWidget(lbl)
        self._preview = TiffPreview(right)
        right_layout.addWidget(self._preview, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Guided panel
    # ------------------------------------------------------------------

    def _make_guided_panel(self) -> QWidget:
        outer = QWidget(self)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(outer)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)

        # Working folder / target name
        folder_grp = QGroupBox("Output", inner)
        folder_layout = QVBoxLayout(folder_grp)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Target name:", inner))
        self._target_name_edit = self._make_lineedit("", inner)
        name_row.addWidget(self._target_name_edit, stretch=1)
        name_row.addWidget(TooltipButton(
            "Target Name",
            "Name of the subfolder created in ~/ChromIQ/ (or your custom path).\n"
            "Default format: Printer_Paper_Papertype_Instrument_Date",
            inner,
        ))
        folder_layout.addLayout(name_row)
        layout.addWidget(folder_grp)

        # Instrument
        instr_grp = QGroupBox("Measurement Instrument", inner)
        instr_layout = QVBoxLayout(instr_grp)
        instr_layout.setSpacing(6)
        row = QHBoxLayout()
        row.addWidget(QLabel("Instrument:", inner))
        self._instr_combo = NoScrollComboBox(inner)
        for code, label in INSTRUMENT_LABELS.items():
            self._instr_combo.addItem(label, code)
        self._instr_combo.currentIndexChanged.connect(self._update_patch_count)
        self._instr_combo.currentIndexChanged.connect(self._update_dd_visibility)
        self._instr_combo.currentIndexChanged.connect(self._rebuild_paper_combo)
        row.addWidget(self._instr_combo, stretch=1)
        row.addWidget(TooltipButton(
            "Measurement Instrument",
            "Select the spectrophotometer you will use to measure the printed chart.\n"
            "The patch layout is optimised for the selected instrument's strip geometry.",
            inner,
        ))
        instr_layout.addLayout(row)

        # Double density (CM only)
        dd_row = QHBoxLayout()
        self._dd_check = QCheckBox("Double density (requires measuring rig)", inner)
        self._dd_check.toggled.connect(self._update_patch_count)
        self._dd_tooltip = TooltipButton(
            "Double Density (-h)",
            "Uses the measuring rig to double the number of patches per strip for "
            "ColorMunki / i1Studio / ColorChecker Studio. Requires the physical rig.",
            inner,
        )
        dd_row.addWidget(self._dd_check)
        dd_row.addWidget(self._dd_tooltip)
        dd_row.addStretch()
        instr_layout.addLayout(dd_row)
        layout.addWidget(instr_grp)

        # Paper
        paper_grp = QGroupBox("Paper", inner)
        paper_layout = QVBoxLayout(paper_grp)
        paper_row = QHBoxLayout()
        paper_row.addWidget(QLabel("Paper size:", inner))
        self._paper_combo = NoScrollComboBox(inner)
        self._paper_combo.currentIndexChanged.connect(self._update_patch_count)
        paper_row.addWidget(self._paper_combo, stretch=1)
        paper_row.addWidget(TooltipButton(
            "Paper Size",
            "Select the paper size you will print on.  The chart fills the page.\n"
            "Use landscape variants when your printer feeds landscape more reliably.",
            inner,
        ))
        paper_layout.addLayout(paper_row)
        layout.addWidget(paper_grp)

        # Pages + left border
        pages_grp = QGroupBox("Chart Size", inner)
        pages_layout = QVBoxLayout(pages_grp)
        pages_layout.setSpacing(6)

        pages_row = QHBoxLayout()
        pages_row.addWidget(QLabel("Number of pages:", inner))
        self._pages_spin = NoScrollSpinBox(inner)
        self._pages_spin.setRange(1, 20)
        self._pages_spin.setValue(1)
        self._pages_spin.valueChanged.connect(self._update_patch_count)
        pages_row.addWidget(self._pages_spin)
        pages_row.addWidget(TooltipButton(
            "Number of Pages",
            "How many physical sheets to print.  Each sheet contains as many\n"
            "patches as fit for the selected instrument and paper size.\n"
            "Total patches = patches/page × pages.",
            inner,
        ))
        pages_row.addStretch()
        pages_layout.addLayout(pages_row)

        lb_row = QHBoxLayout()
        self._lb_check = QCheckBox("Suppress left clip border (-L)", inner)
        self._lb_check.setChecked(True)
        self._lb_check.toggled.connect(self._update_patch_count)
        lb_row.addWidget(self._lb_check)
        self._lb_tooltip = TooltipButton(
            "Suppress Left Clip Border (-L)",
            "Removes the left-edge paper-clip border, gaining ~15 mm for extra patches.\n"
            "Enable unless you use a physical page-clamp jig.  Recommended: ON.",
            inner,
        )
        lb_row.addWidget(self._lb_tooltip)
        lb_row.addStretch()
        pages_layout.addLayout(lb_row)
        layout.addWidget(pages_grp)

        # Patch count display
        count_grp = QGroupBox("Calculated Patches", inner)
        count_grp.setStyleSheet(
            "QGroupBox { margin-top: 14px; padding-top: 0px;"
            " border: 1px solid #333333; border-radius: 4px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; top: 2px;"
            " color: #8a8a8a; font-size: 11px; text-transform: uppercase;"
            " letter-spacing: 1px; }"
        )
        count_layout = QVBoxLayout(count_grp)
        count_layout.setContentsMargins(8, 0, 8, 12)
        count_layout.setSpacing(4)

        self._patch_count_lbl = QLabel("—", inner)
        self._patch_count_lbl.setObjectName("patch_count")
        self._patch_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._patch_count_lbl.setStyleSheet(
            "color: #ffffff; background: transparent;"
            " font-family: Georgia; font-size: 56pt;"
        )
        count_font = QFont()
        count_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 85)
        self._patch_count_lbl.setFont(count_font)
        count_layout.addWidget(self._patch_count_lbl)

        self._patch_detail_lbl = QLabel("", inner)
        self._patch_detail_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._patch_detail_lbl.setStyleSheet(
            "color: #808080; background: transparent;"
            " font-family: Menlo; font-size: 9pt; font-weight: 300;"
        )
        count_layout.addWidget(self._patch_detail_lbl)

        # 5-segment spectrum bar, centered
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(0, 6, 0, 0)
        bar_row.setSpacing(0)
        bar_row.addStretch()
        for _color in (SPEC_MAGENTA, SPEC_AMBER, SPEC_GREEN, SPEC_CYAN, SPEC_VIOLET):
            _seg = QFrame(inner)
            _seg.setFixedSize(22, 2)
            _seg.setStyleSheet(f"background-color: {_color}; border: none;")
            bar_row.addWidget(_seg)
        bar_row.addStretch()
        count_layout.addLayout(bar_row)

        layout.addWidget(count_grp)

        # Hidden-defaults info box
        self._guided_info_lbl = QLabel("", inner)
        self._guided_info_lbl.setObjectName("info")
        self._guided_info_lbl.setWordWrap(True)
        layout.addWidget(self._guided_info_lbl)

        layout.addStretch()
        scroll.setWidget(inner)
        outer_layout.addWidget(scroll)
        return outer

    # ------------------------------------------------------------------
    # Manual panel
    # ------------------------------------------------------------------

    def _make_manual_panel(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Output (target name)
        output_grp = QGroupBox("Output", w)
        output_layout = QVBoxLayout(output_grp)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Target name:", w))
        self._manual_target_name_edit = self._make_lineedit("", w)
        name_row.addWidget(self._manual_target_name_edit, stretch=1)
        name_row.addWidget(TooltipButton(
            "Target Name",
            "Name of the subfolder created in ~/ChromIQ/ (or your custom path).",
            w,
        ))
        output_layout.addLayout(name_row)
        layout.addWidget(output_grp)

        # Presets
        presets_grp = QGroupBox("Presets", w)
        presets_row = QHBoxLayout(presets_grp)
        presets_row.setContentsMargins(8, 4, 8, 8)
        presets_row.addWidget(QLabel("Select preset:", w))
        self._preset_combo = NoScrollComboBox(w)
        self._preset_combo.addItem("Default", userData=None)
        presets_row.addWidget(self._preset_combo, stretch=1)
        self._preset_add_btn = QPushButton(w)
        self._preset_add_btn.setObjectName("icon_btn")
        self._preset_add_btn.setFixedSize(28, 28)
        self._preset_add_btn.setIcon(QIcon(str(resource_path("assets/plus.svg"))))
        self._preset_add_btn.setIconSize(QSize(14, 14))
        self._preset_add_btn.setToolTip("Save current settings as a new preset")
        self._preset_del_btn = QPushButton(w)
        self._preset_del_btn.setObjectName("icon_btn")
        self._preset_del_btn.setFixedSize(28, 28)
        self._preset_del_btn.setIcon(QIcon(str(resource_path("assets/minus.svg"))))
        self._preset_del_btn.setIconSize(QSize(14, 14))
        self._preset_del_btn.setToolTip("Delete selected preset")
        self._preset_del_btn.setEnabled(False)
        presets_row.addWidget(self._preset_add_btn)
        presets_row.addWidget(self._preset_del_btn)
        presets_row.addWidget(TooltipButton(
            "Manual Presets",
            "Save and recall named snapshots of all Manual mode settings.\n\n"
            "Use the + button to save the current parameter values as a named preset. "
            "Select a preset from the list to instantly restore those values. "
            "Use the − button to delete the selected preset.\n\n"
            "The target name field is not saved with presets.",
            w,
            min_width=520,
        ))
        layout.addWidget(presets_grp)

        scroll = QScrollArea(w)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(4, 4, 4, 4)

        self._manual_widgets: dict[str, list[ParameterWidget]] = {
            "targen": [], "printtarg": [],
        }
        self._manual_lb_pw: ParameterWidget | None = None
        self._manual_dd_pw: ParameterWidget | None = None
        self._manual_instr_pw: ParameterWidget | None = None
        self._bit8_radio: QRadioButton | None = None
        self._bit16_radio: QRadioButton | None = None

        for tool, params in [
            ("targen",    self._params.get("targen", [])),
            ("printtarg", self._params.get("printtarg", [])),
        ]:
            grp = QGroupBox(f"{tool} parameters", inner)
            grp_layout = QVBoxLayout(grp)

            basic_grp = QGroupBox("Basic", grp)
            basic_layout = QVBoxLayout(basic_grp)
            expert_grp = QGroupBox("Expert Options", grp)
            expert_layout = QVBoxLayout(expert_grp)

            for p in params:
                pw = ParameterWidget(p, inner)
                flag = p.get("flag", "")

                if tool == "printtarg" and flag == "-t":
                    # Shrink the DPI spinbox and add 8-bit/16-bit radio buttons
                    pw._control.setMaximumWidth(90)
                    bg = QButtonGroup(pw)
                    self._bit8_radio = QRadioButton("8-bit", pw)
                    self._bit16_radio = QRadioButton("16-bit", pw)
                    self._bit8_radio.setChecked(True)
                    bg.addButton(self._bit8_radio)
                    bg.addButton(self._bit16_radio)
                    # Insert before the last item (tooltip button)
                    insert_at = pw.layout().count() - 1
                    pw.layout().insertWidget(insert_at,     self._bit8_radio)
                    pw.layout().insertWidget(insert_at + 1, self._bit16_radio)

                if tool == "printtarg" and flag == "-L":
                    self._manual_lb_pw = pw
                if tool == "printtarg" and flag == "-h":
                    self._manual_dd_pw = pw
                if tool == "printtarg" and flag == "-i":
                    self._manual_instr_pw = pw
                    pw.value_changed.connect(self._update_manual_lb_visibility)

                if p.get("expert_only", False):
                    expert_layout.addWidget(pw)
                else:
                    basic_layout.addWidget(pw)
                self._manual_widgets[tool].append(pw)

            grp_layout.addWidget(basic_grp)
            grp_layout.addWidget(expert_grp)
            inner_layout.addWidget(grp)

        self._update_manual_lb_visibility()
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self._preset_add_btn.clicked.connect(self._on_preset_save)
        self._preset_del_btn.clicked.connect(self._on_preset_delete)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        return w

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_lineedit(self, text: str, parent: QWidget) -> Any:
        from PyQt6.QtWidgets import QLineEdit
        le = QLineEdit(parent)
        le.setText(text)
        return le

    def _load_yaml_params(self) -> dict:
        path = resource_path("data/parameters.yaml")
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("parameters", {})
        except Exception as exc:
            log.error("Cannot load parameters.yaml: %s", exc)
            return {}

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

    def _update_manual_lb_visibility(self) -> None:
        if self._manual_instr_pw is None:
            return
        instr = self._manual_instr_pw.get_raw_value() or "i1"
        is_cm = instr == "CM"
        if self._manual_lb_pw is not None:
            self._manual_lb_pw.setVisible(not is_cm)
        if self._manual_dd_pw is not None:
            self._manual_dd_pw.setVisible(is_cm)

    # ------------------------------------------------------------------
    # Preset helpers
    # ------------------------------------------------------------------

    def _load_presets_from_settings(self) -> dict:
        raw = self._settings.get("manual_presets", "")
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _save_presets_to_settings(self, presets: dict) -> None:
        self._settings.set("manual_presets", json.dumps(presets))

    def _populate_preset_combo(self, presets: dict, select_name: str | None = None) -> None:
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItem("Default", userData=None)
        for name in presets:
            self._preset_combo.addItem(name, userData=name)
        if select_name is not None:
            idx = self._preset_combo.findText(select_name)
            if idx >= 0:
                self._preset_combo.setCurrentIndex(idx)
        self._preset_combo.blockSignals(False)
        self._preset_del_btn.setEnabled(self._preset_combo.currentIndex() > 0)

    def _on_preset_selected(self, index: int) -> None:
        self._preset_del_btn.setEnabled(index > 0)
        s = self._settings
        if index == 0:
            for tool, widgets in self._manual_widgets.items():
                for pw in widgets:
                    v = s.get(f"manual_{tool}_{pw.flag}")
                    if v is not None:
                        pw.set_value(v)
            if self._bit8_radio is not None and self._bit16_radio is not None:
                is_16bit = bool(s.get("manual_printtarg_tiff_16bit", False))
                self._bit16_radio.setChecked(is_16bit)
                self._bit8_radio.setChecked(not is_16bit)
        else:
            name = self._preset_combo.currentData()
            presets = self._load_presets_from_settings()
            data = presets.get(name, {})
            for tool, widgets in self._manual_widgets.items():
                for pw in widgets:
                    v = data.get(f"{tool}_{pw.flag}")
                    if v is not None:
                        pw.set_value(v)
            if self._bit8_radio is not None and self._bit16_radio is not None:
                is_16bit = bool(data.get("tiff_16bit", False))
                self._bit16_radio.setChecked(is_16bit)
                self._bit8_radio.setChecked(not is_16bit)
        self._update_manual_lb_visibility()

    def _on_preset_save(self) -> None:
        capture: dict = {}
        for tool, widgets in self._manual_widgets.items():
            for pw in widgets:
                v = pw.get_raw_value()
                if v is not None:
                    capture[f"{tool}_{pw.flag}"] = v
        capture["tiff_16bit"] = (
            self._bit16_radio.isChecked() if self._bit16_radio is not None else False
        )
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Save Preset")
        dlg.setLabelText(
            "Give this preset a name.\n"
            "All current Manual mode parameter values will be saved under that name\n"
            "and can be recalled at any time from the preset list."
        )
        dlg.setMinimumWidth(460)
        if not dlg.exec():
            return
        name = dlg.textValue().strip()
        if not name:
            return
        presets = self._load_presets_from_settings()
        presets[name] = capture
        self._save_presets_to_settings(presets)
        self._populate_preset_combo(presets, select_name=name)

    def _on_preset_delete(self) -> None:
        name = self._preset_combo.currentText()
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
        bb.addButton("Delete", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        dlg_layout.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        presets = self._load_presets_from_settings()
        presets.pop(name, None)
        self._save_presets_to_settings(presets)
        self._populate_preset_combo(presets)

    # ------------------------------------------------------------------
    # Patch count display
    # ------------------------------------------------------------------

    def _update_patch_count(self) -> None:
        instr  = self._instr_combo.currentData() or "i1"
        paper  = self._paper_combo.currentData() or "A4"
        dd     = self._dd_check.isChecked()
        pages  = self._pages_spin.value()
        has_lb = self._lb_check.isChecked()  # True = -L active (left border suppressed)
        dpi    = int(self._settings.get("printtarg_dpi", 300))

        per_sheet = query_patches(instr, paper, dd, suppress_lb=has_lb)
        if per_sheet is not None:
            total = per_sheet * pages
            self._patch_count_lbl.setText(str(total))
            self._patch_detail_lbl.setText(
                f"PATCHES · {pages} PAGES · {paper.upper()}"
            )
        else:
            self._patch_count_lbl.setText("?")
            self._patch_detail_lbl.setText("CUSTOM LAYOUT")

        # Hidden-defaults info label (values mirror _collect_guided logic)
        base_white = int(self._settings.get("targen_white_patches", 4))
        base_black = int(self._settings.get("targen_black_patches", 4))
        ps = per_sheet or 504
        grey_steps = max(8, min((ps * pages) // 30, 64))
        wp = base_white + (pages - 1) * 2
        bp = base_black + (pages - 1) * 2
        lb_flag = "-L " if has_lb else ""
        dd_flag = "-h " if dd else ""
        info = (
            f"Guided mode applies these fixed settings:\n"
            f"targen -d2 -G -e{wp} -B{bp} -g{grey_steps}\n"
            f"printtarg -i{instr} -p{paper} -t{dpi} {lb_flag}{dd_flag}chart"
        )
        if hasattr(self, "_guided_info_lbl"):
            self._guided_info_lbl.setText(info)

    def _rebuild_paper_combo(self) -> None:
        instr    = self._instr_combo.currentData() or "i1"
        excluded = EXCLUDED_PAPERS.get(instr, set())
        current  = self._paper_combo.currentData()

        self._paper_combo.blockSignals(True)
        self._paper_combo.clear()
        for size in PAPER_SIZES:
            if size not in excluded:
                self._paper_combo.addItem(PAPER_LABELS.get(size, size), size)
        self._paper_combo.blockSignals(False)

        target = current if current not in excluded else PAPER_FALLBACK.get(current, "A4")
        idx = self._paper_combo.findData(target)
        self._paper_combo.setCurrentIndex(max(idx, 0))
        self._update_patch_count()

    def _update_dd_visibility(self) -> None:
        instr = self._instr_combo.currentData() or "i1"
        visible = instr == "CM"
        self._dd_check.setVisible(visible)
        self._dd_tooltip.setVisible(visible)
        lb_visible = instr != "CM"
        self._lb_check.setVisible(lb_visible)
        self._lb_tooltip.setVisible(lb_visible)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_generate(self) -> None:
        if self._runner.is_running:
            log.warning("A process is already running")
            return

        params = self._collect_params()
        name = (
            self._target_name_edit.text().strip()
            if self._current_mode() == "guided"
            else self._manual_target_name_edit.text().strip()
        )
        if name:
            self._file_mgr.set_target_name(name)
        params.target_name = self._file_mgr.get_target_name()
        self._last_target_name = params.target_name

        self._log.clear()
        self._preview.clear()
        self._generate_btn.setEnabled(False)

        self._creator.generate(
            params,
            on_line=self._on_log_line,
            on_finish=self._on_generate_finished,
        )

    def _on_load_ti1(self) -> None:
        path = open_file_dialog(
            self, "Load .ti1 file", "TI1 files (*.ti1)",
            extra_path=self._settings.get("custom_output_path", ""),
        )
        if not path:
            return
        ti1 = Path(path)
        self._file_mgr.set_target_name(ti1.stem)
        params = self._collect_params()
        self._log.clear()
        self._preview.clear()
        self._generate_btn.setEnabled(False)
        self._creator.load_ti1_and_generate_preview(
            ti1, params,
            on_line=self._on_log_line,
            on_finish=self._on_generate_finished,
        )

    def _on_log_line(self, line: str) -> None:
        self._log.appendPlainText(line)
        self._log.ensureCursorVisible()

    def _on_generate_finished(self, tiffs: list[Path]) -> None:
        self._generate_btn.setEnabled(True)
        if tiffs:
            self._preview.load_tiff(tiffs)
            log.info("Preview loaded: %d TIFF(s)", len(tiffs))
            stem = getattr(self, "_last_target_name", None) or "chart"
            ti2 = tiffs[0].parent / f"{stem}.ti2"
            self.chart_finished.emit(tiffs, ti2)
        else:
            self._log.appendPlainText("[ERROR] Chart generation failed.")
            self._log.ensureCursorVisible()

    def _on_save_defaults(self) -> None:
        params = self._collect_params()
        s = self._settings
        name = (
            self._target_name_edit.text().strip()
            if self._current_mode() == "guided"
            else self._manual_target_name_edit.text().strip()
        )
        s.set("chart_target_name",         name or "ChromIQ Test Chart")
        s.set("chart_instrument",          params.instrument)
        s.set("chart_paper",               params.paper)
        s.set("chart_pages",               params.pages)
        s.set("chart_double_density",      params.double_density)
        s.set("chart_disable_left_border", params.disable_left_border)
        s.set("targen_device_type",        params.device_type)
        s.set("targen_good_mode",          params.good_mode)
        s.set("targen_white_patches",      params.white_patches)
        s.set("targen_black_patches",      params.black_patches)
        s.set("printtarg_dpi",             params.tiff_dpi)
        # Save all manual widget values individually
        for tool, widgets in self._manual_widgets.items():
            for pw in widgets:
                v = pw.get_raw_value()
                if v is not None:
                    s.set(f"manual_{tool}_{pw.flag}", v)
        if self._bit16_radio is not None:
            s.set("manual_printtarg_tiff_16bit", self._bit16_radio.isChecked())
        log.info("Chart defaults saved")
        self._log.appendPlainText("Current settings saved as defaults.")
        self._log.ensureCursorVisible()

    # ------------------------------------------------------------------
    # Param collection
    # ------------------------------------------------------------------

    def _collect_params(self) -> ChartParams:
        if self._current_mode() == "guided":
            return self._collect_guided()
        return self._collect_manual()

    def _collect_guided(self) -> ChartParams:
        pages   = self._pages_spin.value()
        instr   = self._instr_combo.currentData() or "i1"
        paper   = self._paper_combo.currentData() or "A4"
        dd      = self._dd_check.isChecked()
        has_lb  = self._lb_check.isChecked()
        base_white = int(self._settings.get("targen_white_patches", 4))
        base_black = int(self._settings.get("targen_black_patches", 4))
        per_sheet  = query_patches(instr, paper, dd, suppress_lb=has_lb) or 504
        grey_steps = max(8, min((per_sheet * pages) // 30, 64))
        return ChartParams(
            instrument           = instr,
            paper                = paper,
            pages                = pages,
            double_density       = dd,
            disable_left_border  = has_lb,
            device_type          = self._settings.get("targen_device_type", "2"),
            patches              = 0,
            white_patches        = base_white + (pages - 1) * 2,
            black_patches        = base_black + (pages - 1) * 2,
            good_mode            = bool(self._settings.get("targen_good_mode", True)),
            grey_steps           = grey_steps,
            tiff_dpi             = int(self._settings.get("printtarg_dpi", 300)),
            patch_scale          = 1.0,
            margin_mm            = 6,
        )

    def _collect_manual(self) -> ChartParams:
        p = ChartParams()

        def _get(tool: str, flag: str, default: Any) -> Any:
            for pw in self._manual_widgets.get(tool, []):
                if pw.flag == flag:
                    v = pw.get_raw_value()
                    return v if v is not None else default
            return default

        p.device_type          = str(_get("targen",    "-d",  "2"))
        p.patches              = int(_get("targen",    "-f",  0))
        p.white_patches        = int(_get("targen",    "-e",  4))
        p.black_patches        = int(_get("targen",    "-B",  4))
        p.good_mode            = bool(_get("targen",   "-G",  True))
        p.grey_steps           = int(_get("targen",    "-g",  0))
        p.single_channel_steps = int(_get("targen",    "-s",  0))

        p.instrument           = str(_get("printtarg", "-i",  "i1"))
        p.paper                = str(_get("printtarg", "-p",  "A4"))
        p.tiff_dpi             = int(_get("printtarg", "-t",  300))
        p.tiff_16bit           = self._bit16_radio is not None and self._bit16_radio.isChecked()
        p.double_density       = bool(_get("printtarg", "-h", False))
        p.disable_left_border  = bool(_get("printtarg", "-L", True))
        p.patch_scale          = float(_get("printtarg", "-a", 1.0))
        p.margin_mm            = int(_get("printtarg",  "-m",  6))
        p.no_randomise         = bool(_get("printtarg", "-r",  False))
        p.bw_spacers           = bool(_get("printtarg", "-b",  False))
        return p

    # ------------------------------------------------------------------
    # Restore saved defaults
    # ------------------------------------------------------------------

    def _restore_defaults(self) -> None:
        s = self._settings

        default_name = s.get("chart_target_name", "ChromIQ Test Chart")
        self._target_name_edit.setText(default_name)
        self._manual_target_name_edit.setText(default_name)

        instr = s.get("chart_instrument", "i1")
        idx = self._instr_combo.findData(instr)
        if idx >= 0:
            self._instr_combo.setCurrentIndex(idx)
        self._rebuild_paper_combo()  # populate/filter even if instrument index didn't change

        paper = s.get("chart_paper", "A4")
        idx = self._paper_combo.findData(paper)
        if idx >= 0:
            self._paper_combo.setCurrentIndex(idx)

        self._pages_spin.setValue(int(s.get("chart_pages", 1)))
        self._dd_check.setChecked(bool(s.get("chart_double_density", False)))
        self._lb_check.setChecked(bool(s.get("chart_disable_left_border", True)))
        self._update_dd_visibility()
        self._update_patch_count()

        # Restore manual widget values
        for tool, widgets in self._manual_widgets.items():
            for pw in widgets:
                v = s.get(f"manual_{tool}_{pw.flag}")
                if v is not None:
                    pw.set_value(v)
        if self._bit8_radio is not None and self._bit16_radio is not None:
            is_16bit = bool(s.get("manual_printtarg_tiff_16bit", False))
            self._bit16_radio.setChecked(is_16bit)
            self._bit8_radio.setChecked(not is_16bit)
        self._update_manual_lb_visibility()

        presets = self._load_presets_from_settings()
        self._populate_preset_combo(presets)

        mode = s.get("chart_mode", "guided")
        self._switch_mode(mode)
