"""Tab 5: Check && Refine — profcheck quality assessment and guided re-measurement."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, make_browse_button, open_file_dialog
from workflow.profcheck_runner import (
    REFINE_DE_THRESHOLD,
    REFINE_START_OVER_RATIO,
    REFINE_START_OVER_STRIP_RATIO,
    ProfcheckParams,
    ProfcheckRunner,
    group_by_strip,
    parse_refine_strips,
    quality_explanation,
    quality_grade,
    strips_to_refine,
    total_strip_count,
    write_quality_report,
    write_refine_strips,
)

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
    ti2_found                  = pyqtSignal(Path)         # emitted when a matching .ti2 exists next to the .ti3

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

        self._build_ui()
        self._restore_defaults()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_paths(self, ti3: Path, icc: Path) -> None:
        """Pre-populate both file fields after a successful profile build."""
        self._ti3_path = ti3
        self._icc_path = icc
        self._ti3_edit.setText(str(ti3))
        self._icc_edit.setText(str(icc))
        self._notify_ti2(ti3)

    def _notify_ti2(self, ti3: Path) -> None:
        ti2 = ti3.with_suffix(".ti2")
        if ti2.exists():
            self.ti2_found.emit(ti2)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ── File selection ──────────────────────────────────────────────
        file_grp = QGroupBox("Test Data && Profile", self)
        file_grp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        fg = QVBoxLayout(file_grp)
        fg.setContentsMargins(8, 10, 8, 6)
        fg.setSpacing(4)

        ti3_row = QHBoxLayout()
        ti3_row.addWidget(QLabel(".ti3 test data file:", self))
        self._ti3_edit = QLineEdit(self)
        self._ti3_edit.setPlaceholderText("Path to .ti3 measurement file")
        self._ti3_edit.setReadOnly(True)
        ti3_row.addWidget(self._ti3_edit, stretch=1)
        ti3_browse = make_browse_button(self, "Browse for .ti3 file")
        ti3_browse.clicked.connect(self._on_browse_ti3)
        ti3_row.addWidget(ti3_browse)
        fg.addLayout(ti3_row)

        icc_row = QHBoxLayout()
        icc_row.addWidget(QLabel("ICC / ICM profile:", self))
        self._icc_edit = QLineEdit(self)
        self._icc_edit.setPlaceholderText("Path to .icc or .icm profile (auto-filled when .ti3 is loaded)")
        self._icc_edit.setReadOnly(True)
        icc_row.addWidget(self._icc_edit, stretch=1)
        icc_browse = make_browse_button(self, "Browse for ICC/ICM profile")
        icc_browse.clicked.connect(self._on_browse_icc)
        icc_row.addWidget(icc_browse)
        fg.addLayout(icc_row)

        root.addWidget(file_grp)

        # ── Check options ───────────────────────────────────────────────
        opts_container = QWidget(self)
        opts_layout = QVBoxLayout(opts_container)
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.setSpacing(8)

        opts_grp = QGroupBox("Check Options", opts_container)
        og = QVBoxLayout(opts_grp)
        og.setContentsMargins(8, 14, 8, 8)
        og.setSpacing(8)

        # Delta E formula
        de_row = QHBoxLayout()
        de_row.addWidget(QLabel("Delta E formula:", self))
        self._de_combo = NoScrollComboBox(self)
        self._de_combo.addItem("CIEDE2000 (recommended)", "k")
        self._de_combo.addItem("CIE76 (classic)", "")
        self._de_combo.addItem("CIE94", "c")
        de_row.addWidget(self._de_combo)
        de_row.addStretch()
        de_row.addWidget(TooltipButton(
            "Delta E Formula",
            "Selects the colour-difference formula used to compute errors.\n"
            "CIEDE2000 is the most perceptually accurate and is recommended\n"
            "for modern RGB printer profiling workflows.",
            self,
        ))
        og.addLayout(de_row)

        # Rendering intent
        intent_row = QHBoxLayout()
        intent_row.addWidget(QLabel("Rendering intent:", self))
        self._intent_combo = NoScrollComboBox(self)
        self._intent_combo.addItem("Absolute colorimetric (default)", "a")
        self._intent_combo.addItem("Relative colorimetric", "r")
        intent_row.addWidget(self._intent_combo)
        intent_row.addStretch()
        intent_row.addWidget(TooltipButton(
            "Rendering Intent",
            "Absolute colorimetric checks the profile's absolute colour\n"
            "accuracy including white-point, which is the standard for\n"
            "printer profiling. Relative colorimetric normalises to\n"
            "the media white point.",
            self,
        ))
        og.addLayout(intent_row)

        # Sort by delta E
        sort_row = QHBoxLayout()
        self._sort_cb = QCheckBox("Sort patches by \u0394E (worst first)", self)
        sort_row.addWidget(self._sort_cb)
        sort_row.addStretch()
        sort_row.addWidget(TooltipButton(
            "Sort by \u0394E",
            "Sorts profcheck output so the worst-performing patches appear\n"
            "first. Useful for quickly identifying problem areas.",
            self,
        ))
        og.addLayout(sort_row)

        # Verbosity
        verb_row = QHBoxLayout()
        verb_row.addWidget(QLabel("Verbosity:", self))
        self._verb_combo = NoScrollComboBox(self)
        self._verb_combo.addItem("Per-patch (required for strip analysis)", "2")
        self._verb_combo.addItem("Summary only", "1")
        verb_row.addWidget(self._verb_combo)
        verb_row.addStretch()
        verb_row.addWidget(TooltipButton(
            "Verbosity",
            "Per-patch mode outputs each patch's individual \u0394E value,\n"
            "which is required for strip-level analysis and guided\n"
            "refinement. Summary mode only shows average and peak errors.",
            self,
        ))
        og.addLayout(verb_row)

        # Re-measurement threshold
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Flag strips for re-measurement above ΔE:", self))
        self._threshold_spin = NoScrollDoubleSpinBox(self)
        self._threshold_spin.setRange(0.5, 10.0)
        self._threshold_spin.setSingleStep(0.5)
        self._threshold_spin.setDecimals(1)
        self._threshold_spin.setValue(REFINE_DE_THRESHOLD)
        threshold_row.addWidget(self._threshold_spin)
        threshold_row.addStretch()
        threshold_row.addWidget(TooltipButton(
            "Re-measurement Threshold (ΔE)",
            "Sets how sensitive the quality check is when deciding which strips\n"
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
            "strips appear in the re-measurement recommendation.",
            self,
        ))
        og.addLayout(threshold_row)

        opts_layout.addWidget(opts_grp)

        # ── Advanced options ────────────────────────────────────────────
        adv_grp = QGroupBox("Advanced Options", opts_container)
        adv_grp.setCheckable(True)
        adv_grp.setChecked(False)
        adv_layout = QVBoxLayout(adv_grp)
        adv_layout.setContentsMargins(8, 14, 8, 8)
        adv_layout.setSpacing(8)

        # FWA compensation
        fwa_row = QHBoxLayout()
        self._fwa_cb = QCheckBox("FWA compensation (-f):", self)
        fwa_row.addWidget(self._fwa_cb)
        self._fwa_combo = NoScrollComboBox(self)
        for label, val in _ILLUMINANTS:
            self._fwa_combo.addItem(label, val)
        self._fwa_combo.setEnabled(False)
        self._fwa_cb.toggled.connect(self._fwa_combo.setEnabled)
        fwa_row.addWidget(self._fwa_combo)
        fwa_row.addStretch()
        fwa_row.addWidget(TooltipButton(
            "FWA Compensation (-f)",
            "Some papers contain optical brighteners (fluorescent whitening agents)\n"
            "that make the paper look extra white under certain lighting. This option\n"
            "compensates for that effect during the check.\n\n"
            "Only works if your .ti3 file contains spectral measurement data\n"
            "(not all instruments produce this). If you are unsure, leave it off.\n\n"
            "Set the illuminant to match the light source you view your prints under\n"
            "(D50 = standard daylight, D65 = cooler daylight).",
            self,
        ))
        adv_layout.addLayout(fwa_row)

        # Illuminant
        illum_row = QHBoxLayout()
        illum_row.addWidget(QLabel("Illuminant (-i):", self))
        self._illum_combo = NoScrollComboBox(self)
        for label, val in _ILLUMINANTS:
            self._illum_combo.addItem(label, val)
        illum_row.addWidget(self._illum_combo)
        illum_row.addStretch()
        illum_row.addWidget(TooltipButton(
            "Illuminant (-i)",
            "Selects the light source used when converting spectral measurements\n"
            "to colour values. Only relevant if your .ti3 contains spectral data.\n\n"
            "D50 is the standard for print profiling and the right choice for most\n"
            "workflows. D65 is used in some video and photography contexts.\n\n"
            "Leave at D50 unless you have a specific reason to change it.",
            self,
        ))
        adv_layout.addLayout(illum_row)

        # Observer
        obs_row = QHBoxLayout()
        obs_row.addWidget(QLabel("CIE Observer (-o):", self))
        self._obs_combo = NoScrollComboBox(self)
        for label, val in _OBSERVERS:
            self._obs_combo.addItem(label, val)
        obs_row.addWidget(self._obs_combo)
        obs_row.addStretch()
        obs_row.addWidget(TooltipButton(
            "CIE Observer (-o)",
            "Defines the mathematical model used to represent how the human eye\n"
            "sees colour.\n\n"
            "1931 2° is the international standard for print and ICC profiling\n"
            "and the correct choice for virtually all printer profiling work.\n\n"
            "The 1964 10° observer can be used for large-area colour matching,\n"
            "but is rarely needed here. Leave at 1931 2° unless specifically\n"
            "requested by your colour management workflow.",
            self,
        ))
        adv_layout.addLayout(obs_row)

        # Prune
        prune_row = QHBoxLayout()
        self._prune_cb = QCheckBox("Prune .ti3 to patches with \u0394E \u2264 (-P):", self)
        prune_row.addWidget(self._prune_cb)
        self._prune_spin = NoScrollDoubleSpinBox(self)
        self._prune_spin.setRange(0.0, 20.0)
        self._prune_spin.setSingleStep(0.5)
        self._prune_spin.setDecimals(2)
        self._prune_spin.setValue(3.0)
        self._prune_spin.setEnabled(False)
        self._prune_cb.toggled.connect(self._prune_spin.setEnabled)
        prune_row.addWidget(self._prune_spin)
        prune_row.addWidget(QLabel("\u0394E", self))
        prune_row.addStretch()
        prune_row.addWidget(TooltipButton(
            "Prune .ti3 (-P)",
            "Creates a reduced copy of your .ti3 file containing only patches\n"
            "whose colour error is at or below the threshold you set.\n\n"
            "Useful if a small number of badly measured patches are pulling\n"
            "the profile down. Pruning them out lets you build a cleaner\n"
            "profile from the remaining good patches \u2014 at the cost of\n"
            "having fewer data points overall.\n\n"
            "The pruned file is saved next to the original .ti3 and can be\n"
            "loaded directly in the Build Profile tab.",
            self,
        ))
        adv_layout.addLayout(prune_row)

        # X3DOM visualisation
        x3d_row = QHBoxLayout()
        self._x3dom_cb = QCheckBox("Create X3DOM 3D visualisation (-w)", self)
        x3d_row.addWidget(self._x3dom_cb)
        x3d_row.addStretch()
        x3d_row.addWidget(TooltipButton(
            "X3DOM Visualisation (-w)",
            "Generates an interactive 3D visualisation of your profile's colour\n"
            "errors and saves it as an HTML file next to your .ti3.\n\n"
            "Open the .x3d.html file in any modern web browser to explore a\n"
            "3D diagram showing where errors are largest — useful for seeing\n"
            "which parts of the colour gamut your profile handles well and\n"
            "which areas need improvement.",
            self,
        ))
        adv_layout.addLayout(x3d_row)

        opts_layout.addWidget(adv_grp)

        root.addWidget(opts_container)

        # ── Action buttons ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Analyse Profile Quality", self)
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._on_run)
        self._save_defaults_btn = QPushButton("Save as Defaults", self)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        root.addLayout(btn_row)

        # ── Log ────────────────────────────────────────────────────────
        self._log = QPlainTextEdit(self)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(67)
        self._log.setPlaceholderText("profcheck output will appear here…")
        root.addWidget(self._log, stretch=1)

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
        ti3 = Path(path)
        self._ti3_path = ti3
        self._ti3_edit.setText(str(ti3))
        self._auto_fill_icc(ti3)
        self._notify_ti2(ti3)

    def _on_browse_icc(self) -> None:
        path = open_file_dialog(
            self, "Select ICC / ICM profile", "ICC profiles (*.icc *.icm)",
            extra_path=self._settings.get("custom_output_path", ""),
        )
        if path:
            self._icc_path = Path(path)
            self._icc_edit.setText(str(self._icc_path))

    def _auto_fill_icc(self, ti3: Path) -> None:
        """Try to find a matching ICC/ICM in the same folder."""
        for ext in (".icc", ".icm"):
            candidate = ti3.with_suffix(ext)
            if candidate.exists():
                self._icc_path = candidate
                self._icc_edit.setText(str(candidate))
                return
        # No match — clear ICC field and warn
        self._icc_path = None
        self._icc_edit.clear()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self,
            "Profile Not Found",
            f"No matching .icc or .icm file was found in:\n{ti3.parent}\n\n"
            "Please browse for the profile file manually.",
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

        params = self._collect_params()
        self._log.clear()
        self._last_result = None
        self._run_btn.setEnabled(False)

        self._checker.run(
            params,
            on_line=self._on_log_line,
            on_finish=self._on_done,
        )

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
                folder = self._ti3_path.parent
                grade = quality_grade(result.avg_de, result.peak_de)
                explanation = quality_explanation(result.avg_de, result.peak_de)
                summary_text = f"Profile Quality Assessment: {grade}\n\n{explanation}"
                if all_strips_display:
                    strip_lines = "\n".join(
                        f"  {s:4s}  avg \u0394E: {de:.2f}" for s, de in all_strips_display[:10]
                    )
                    summary_text += f"\n\nStrips with highest error (worst first, avg \u0394E):\n{strip_lines}"
                if refine_strips and not recommend_start_over:
                    refine_lines = "\n".join(
                        f"  {s:4s}  max \u0394E: {de:.2f}" for s, de in refine_strips
                    )
                    summary_text += (
                        f"\n\nStrips flagged for re-measurement (in measurement order, "
                        f"threshold \u0394E > {threshold:.1f}):\n{refine_lines}"
                    )

                report_path = write_quality_report(folder, stem, summary_text, result.raw_log)
                self._log.appendPlainText(f"\n[OK] Quality report saved: {report_path.name}")

                if refine_strips and not recommend_start_over:
                    strips_file = write_refine_strips(folder, stem, refine_strips)
                    self._log.appendPlainText(f"[OK] Refinement strips file saved: {strips_file.name}")
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
        dlg.setWindowTitle("Profile Quality Assessment")
        dlg.setMinimumWidth(560)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # Grade headline
        grade_lbl = QLabel(f"Profile Quality: <b>{grade}</b>", dlg)
        grade_lbl.setStyleSheet("font-size: 15px;")
        layout.addWidget(grade_lbl)

        # Explanation
        exp_lbl = QLabel(explanation, dlg)
        exp_lbl.setWordWrap(True)
        layout.addWidget(exp_lbl)

        # Strip overview — always show if data is available
        if all_strips_display:
            top_n = all_strips_display[:5]
            strip_lines = "\n".join(
                f"  \u2022 Strip {s}  (avg \u0394E: {de:.2f})" for s, de in top_n
            )
            overview_lbl = QLabel(
                f"<b>Strips with the highest error</b> (worst first, avg \u0394E):"
                f"<br><pre>{strip_lines}</pre>",
                dlg,
            )
            overview_lbl.setWordWrap(True)
            layout.addWidget(overview_lbl)

        # Action recommendation
        if recommend_start_over and refine_strips:
            thr = self._threshold_spin.value()
            patch_pct = round(100 * n_patches_above / n_total_patches)
            strip_pct = round(100 * n_flagged / n_total_strips)
            if n_patches_above / n_total_patches > REFINE_START_OVER_RATIO:
                reason = (
                    f"{n_patches_above} out of {n_total_patches} patches ({patch_pct}%) "
                    f"exceed \u0394E\u202f{thr:.1f} \u2014 more than half of your measurement data."
                )
            else:
                reason = (
                    f"{n_flagged} out of {n_total_strips} strips ({strip_pct}%) need "
                    f"re-measuring \u2014 more than three-quarters of your chart."
                )
            action_lbl = QLabel(
                f"<b>{reason}</b><br><br>"
                "Re-measuring individual strips is unlikely to reliably fix this. "
                "<b>Starting over with a freshly printed and measured chart is "
                "strongly recommended.</b>",
                dlg,
            )
            action_lbl.setWordWrap(True)
            layout.addWidget(action_lbl)
        elif refine_strips:
            refine_lines = "  " + "   ".join(
                f"{s} (max \u0394E:\u202f{de:.2f})" for s, de in refine_strips
            )
            action_lbl = QLabel(
                f"<b>{len(refine_strips)} strip(s) have at least one patch above "
                f"\u0394E\u202f{self._threshold_spin.value():.1f} and should be re-measured:</b>"
                f"<br><pre>{refine_lines}</pre>"
                "Listed in measurement order \u2014 the app will navigate to each one "
                "automatically.",
                dlg,
            )
            action_lbl.setWordWrap(True)
            layout.addWidget(action_lbl)

        # Buttons
        btn_box = QDialogButtonBox()
        close_btn = btn_box.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        close_btn.clicked.connect(dlg.reject)

        guide_btn: QPushButton | None = None
        if strips_file and refine_strips and not recommend_start_over and self._ti3_path:
            guide_btn = btn_box.addButton(
                "Guide Me Through Refinement",
                QDialogButtonBox.ButtonRole.ActionRole,
            )
            guide_btn.setObjectName("primary")

        layout.addWidget(btn_box)

        if guide_btn:
            ti3 = self._ti3_path

            def _on_guide():
                dlg.accept()
                self.guide_refinement_requested.emit(ti3, strips_file)

            guide_btn.clicked.connect(_on_guide)

        dlg.exec()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _collect_params(self) -> ProfcheckParams:
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

    def _on_save_defaults(self) -> None:
        s = self._settings
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
        self._log.appendPlainText("Check & Refine settings saved as defaults.")

    def _restore_defaults(self) -> None:
        s = self._settings

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
