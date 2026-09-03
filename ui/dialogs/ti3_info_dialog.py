"""Measurement info — Tools ▸ "Inspect a measurement".

Opens an ArgyllCMS ``.ti3`` (the raw per-patch measurement behind a profile)
and explains, in plain language, what the paper-and-ink actually did: the true
measured contrast, how neutral the greys really are (the cast the profile then
corrects), how far the gamut reaches, whether the read looks trustworthy, and —
from the spectral data — how the paper behaves under other lighting.

Companion to :mod:`ui.dialogs.profile_info_dialog`. Where that inspects the
fitted ``.icc`` model, this inspects the ground-truth data it was built from.
All maths is in :mod:`workflow.ti3_analysis`; no ArgyllCMS call, so nothing here
can hang or crash on quit.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.logger import get_logger
from core.platform_paths import default_output_root
from ui import neutral_styles
from ui.dialog_sizing import pin_min_height
from ui.dialogs.tools_dialogs import neutral_controls_qss
from ui.fade_scroll import FadeScrollArea
from ui.styles import SPEC_CYAN, TEXT_DIM, TEXT_MAIN
from ui.tab_header import dialog_masthead
from ui.tooltip_button import TooltipButton
from ui.widgets import (
    banner_qss,
    NoScrollComboBox,
    make_browse_button,
    open_file_dialog,
    save_file_dialog,
)
from workflow.ti3_analysis import (
    AccuracyResult,
    Ti3Analysis,
    Ti3ParseError,
    accuracy_from_profcheck,
    accuracy_vs_reference,
    analyse_ti3,
    is_verification_ti3,
    neutral_residual,
    parse_reference_labs,
    parse_ti3,
)

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)

_ACCENT = SPEC_CYAN

_HELP = tr(
    "Open a measurement file (.ti3) — the raw readings of every patch on a "
    "printed chart, taken with your instrument before any profile is built. "
    "Because it's the real data a profile is fitted to, it can tell you things "
    "the finished profile only smooths over:\n\n"
    "  •  the true contrast between paper white and the deepest black,\n"
    "  •  how neutral your greys actually measured (the colour cast the profile "
    "then has to correct),\n"
    "  •  how saturated a colour your paper-and-ink reached,\n"
    "  •  whether the measurement looks clean or a strip was misread, and\n"
    "  •  how the paper behaves under different lighting (from its spectral data).\n\n"
    "Hover any value for a friendly explanation of what it means and what you "
    "can learn from it."
)



def _chromiq_root(settings) -> Path:
    """The folder the user thinks of as "the ChromIQ folder" — their custom
    output folder when they have set one, otherwise ~/ChromIQ.

    Knut, #130 2026-07-30: *"The Inspect Measurement tool: when opening the file
    dialog to browse for ti3 file it does not start in the default ChromIQ
    folder."* Both browse handlers here hard-coded ``~/ChromIQ`` and so ignored
    Preferences → Paths entirely. Every other place in the app already consults
    the setting first; these two were the only ones that did not.
    """
    custom = ""
    try:
        custom = settings.get("custom_output_path", "") if settings else ""
    except Exception:      # noqa: BLE001 — a browse must never fail on this
        custom = ""
    root = Path(custom).expanduser() if custom else default_output_root()
    return root if root.exists() else Path.home()


class Ti3InfoDialog(QDialog):
    def __init__(
        self,
        runner: "ArgyllRunner",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._settings = settings
        self._analysis: Ti3Analysis | None = None
        # verification state
        self._mode = "inspect"          # "inspect" | "verify"
        self._compare_kind = "none"     # "none" | "profile" | "reference"
        self._compare_path: Path | None = None
        self._basis = "media"           # "media" | "absolute"
        self._accuracy: AccuracyResult | None = None
        self._accuracy_msg = ""         # status/error shown in place of accuracy rows
        self._pc_runner = None          # lazily-created ProfcheckRunner
        self._report: list[str] = []    # plain-text lines mirroring the shown rows
        # Theme-aware detail-text colours (hardcoded dark-theme greys are
        # invisible on a light background).
        self._text_main, self._text_dim = self._resolve_text_colors()

        self.setWindowTitle(tr("Measurement info"))
        self.setMinimumWidth(720)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head, _header, stripe = dialog_masthead(
            self, tr("MEASUREMENT · INSPECT"), tr("Measurement info"),
            tooltip_title=tr("Measurement info"), tooltip_body=_HELP,
            accent=_ACCENT)
        root.addLayout(head)
        root.addWidget(stripe)

        self._inner = QVBoxLayout()
        self._inner.setContentsMargins(22, 14, 22, 16)
        self._inner.setSpacing(12)
        root.addLayout(self._inner)

        self._body = QLabel(
            tr("Open a measurement file to inspect what your printer and paper "
               "actually did."), self)
        self._body.setWordWrap(True)
        self._inner.addWidget(self._body)

        # --- File picker row ----------------------------------------------
        pick = QHBoxLayout()
        pick.setSpacing(8)
        pick.addWidget(QLabel(tr("Measurement:"), self))
        self._path_edit = QLineEdit(self)
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText(tr("Browse for a .ti3 measurement…"))
        pick.addWidget(self._path_edit, 1)
        # Reuse the cyan "folder_build" glyph (as on the Build Profile tab) so
        # the browse button matches this dialog's cyan masthead, not the violet
        # "folder_check" used by the violet Profile-info dialog.
        browse = make_browse_button(
            self, tr("Browse for a .ti3 measurement"), "folder_build")
        browse.clicked.connect(self._on_browse)
        pick.addWidget(browse)
        self._inner.addLayout(pick)

        # --- Mode: Inspect (raw chart) vs Verify (managed print) ----------
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        mode_lbl = QLabel(tr("Mode:"), self)
        mode_tip = tr(
            "Choose how to read this measurement — ChromIQ can't tell from the "
            "file alone, so you decide:\n\n"
            "• Inspect (raw chart): the chart was printed with colour management "
            "OFF — the normal profiling chart. The figures describe what your "
            "paper-and-ink can do and the printer's uncorrected character.\n\n"
            "• Verify (managed print): the chart was printed THROUGH a profile. "
            "The greys are re-read as the cast left over AFTER correction, and you "
            "can attach the profile or a reference to score colour accuracy.\n\n"
            "What it can't do: it can't judge accuracy in Verify mode without a "
            "profile or reference attached — it can only show the residual cast.")
        mode_lbl.setToolTip(mode_tip)
        mode_row.addWidget(mode_lbl)
        self._mode_group = QButtonGroup(self)
        self._rb_inspect = QRadioButton(tr("Inspect (raw chart)"), self)
        self._rb_verify = QRadioButton(tr("Verify (managed print)"), self)
        self._rb_inspect.setChecked(True)
        for rb in (self._rb_inspect, self._rb_verify):
            rb.setToolTip(mode_tip)
            self._mode_group.addButton(rb)
            mode_row.addWidget(rb)
        mode_row.addStretch(1)
        mode_row.addWidget(TooltipButton(
            tr("Inspect vs Verify"), mode_tip, self, color=_ACCENT))
        self._rb_inspect.toggled.connect(self._on_mode_changed)
        self._inner.addLayout(mode_row)

        # --- Verify-only controls (hidden in Inspect mode) ----------------
        self._verify_box = QWidget(self)
        vbl = QVBoxLayout(self._verify_box)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(8)

        cmp_row = QHBoxLayout()
        cmp_row.setSpacing(8)
        cmp_lbl = QLabel(tr("Compare against:"), self)
        cmp_tip = tr(
            "Optional — attach something to score how accurate the managed print "
            "is, patch by patch:\n\n"
            "• Profile (.icc): checks the round trip — does the print match what "
            "this profile predicts those values should look like? Best for "
            "verifying the profile you just built. (Uses ArgyllCMS; v2 profiles "
            "only.)\n\n"
            "• Reference: compares each patch to a target Lab/XYZ table (another "
            ".ti3 or reference file), matched by patch ID. Best when you have "
            "known target values to hit.\n\n"
            "Leave on “None” to just see the residual grey cast without a score.")
        cmp_lbl.setToolTip(cmp_tip)
        # Pin the label so it can't absorb the leftover width when the path is
        # hidden (which would shove the combo to the right edge).
        cmp_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        cmp_row.addWidget(cmp_lbl)
        self._cmp_combo = NoScrollComboBox(self)
        # Don't let the combo grab leftover width when the path field is hidden
        # (otherwise it stretches to the right edge in the "None" state).
        self._cmp_combo.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._cmp_combo.addItem(tr("None"), "none")
        self._cmp_combo.addItem(tr("Profile (.icc)"), "profile")
        self._cmp_combo.addItem(tr("Reference (.ti3 / table)"), "reference")
        self._cmp_combo.setToolTip(cmp_tip)
        self._cmp_combo.currentIndexChanged.connect(self._on_compare_kind_changed)
        cmp_row.addWidget(self._cmp_combo)
        self._cmp_path = QLineEdit(self)
        self._cmp_path.setReadOnly(True)
        self._cmp_path.setVisible(False)
        cmp_row.addWidget(self._cmp_path, 8)
        self._cmp_browse = make_browse_button(
            self, tr("Browse for a profile or reference"), "folder_build")
        self._cmp_browse.setVisible(False)
        self._cmp_browse.clicked.connect(self._on_compare_browse)
        cmp_row.addWidget(self._cmp_browse)
        # Always-present trailing stretch keeps the combo left when the path is
        # hidden ("None"); the path's larger stretch still lets it fill when shown.
        cmp_row.addStretch(1)
        cmp_row.addWidget(TooltipButton(
            tr("Compare against"), cmp_tip, self, color=_ACCENT))
        vbl.addLayout(cmp_row)

        basis_row = QHBoxLayout()
        basis_row.setSpacing(8)
        basis_lbl = QLabel(tr("Neutral basis:"), self)
        basis_tip = tr(
            "Which white the leftover grey cast is measured against — match it to "
            "the rendering intent the print used:\n\n"
            "• Relative to paper white (default): treats the paper's own tint as "
            "neutral, so only the profile's residual error shows. This is right "
            "for a relative-colorimetric print (what almost every photo print "
            "uses).\n\n"
            "• Absolute (D50): measures against the fixed D50 white, so a tinted "
            "or brightened paper still reads as a cast. Right for an absolute / "
            "paper-simulating (proofing) print.")
        basis_lbl.setToolTip(basis_tip)
        basis_row.addWidget(basis_lbl)
        self._basis_combo = NoScrollComboBox(self)
        self._basis_combo.addItem(tr("Relative to paper white"), "media")
        self._basis_combo.addItem(tr("Absolute (D50)"), "absolute")
        self._basis_combo.setToolTip(basis_tip)
        self._basis_combo.currentIndexChanged.connect(self._on_basis_changed)
        basis_row.addWidget(self._basis_combo)
        basis_row.addStretch(1)
        basis_row.addWidget(TooltipButton(
            tr("Neutral basis"), basis_tip, self, color=_ACCENT))
        vbl.addLayout(basis_row)

        self._verify_box.setVisible(False)
        self._inner.addWidget(self._verify_box)

        # --- error banner (hidden until needed) ---------------------------
        self._banner = QLabel("", self)
        self._banner.setWordWrap(True)
        self._banner.setVisible(False)
        self._inner.addWidget(self._banner)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        self._inner.addWidget(sep)

        # --- Scrollable details -------------------------------------------
        self._scroll = FadeScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        # A LOW floor here — the generous one is set per-screen in showEvent.
        # A hard 720 floor entered the dialog's overlap-free minimum, so on a
        # display where header+720+buttons exceed the screen the window could
        # not shrink, its bottom sat off-screen and the details never showed a
        # scrollbar (their 720 px was granted in full) — Basti, 2026-08-10,
        # twice during the hardware session.
        self._scroll.setMinimumHeight(240)

        self._details = QWidget()
        self._grid = QGridLayout(self._details)
        self._grid.setContentsMargins(2, 2, 2, 2)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(7)
        self._grid.setColumnStretch(1, 1)
        self._scroll.setWidget(self._details)
        self._inner.addWidget(self._scroll, 1)

        self._placeholder = QLabel(tr("No measurement loaded yet."), self._details)
        self._placeholder.setStyleSheet(f"color: {self._text_dim};")
        self._grid.addWidget(self._placeholder, 0, 0, 1, 2,
                             Qt.AlignmentFlag.AlignHCenter)

        # --- Bottom buttons -----------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._save_btn = QPushButton(tr("Save report…"), self)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_report)
        btn_row.addWidget(self._save_btn)
        close_btn = QPushButton(tr("Close"), self)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        self._inner.addLayout(btn_row)

        # Use the cyan masthead accent (not the neutral indicator) for the
        # focus ring, so a highlighted field matches the rest of the dialog.
        self.setStyleSheet(neutral_controls_qss(_ACCENT, popup=_ACCENT))

    # ------------------------------------------------------------------
    def _resolve_text_colors(self) -> tuple[str, str]:
        """(main, dim) detail-text colours for the appearance on screen.

        Same fold, same result, as ``ProfileInfoDialog``: a two-answer choice
        gave the light-grey appearance the dark theme's near-white ink, so the
        whole detail column measured 1.02:1 and was not readable at all. Both
        values are greys, so the hue census scored it zero, and this window is
        empty until a ``.ti3`` is loaded, so nothing had drawn it.
        """
        from ui.theme import by_mode, resolve_mode
        return by_mode(("#1c1b18", "#5a5a5a"), (TEXT_MAIN, TEXT_DIM),
                       (neutral_styles.NM_TEXT_MAIN, neutral_styles.NM_TEXT_DIM),
                       resolve_mode(self._settings.get("appearance", "auto")))

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # Give the details as much of the 720 px comfort floor as THIS screen
        # affords: everything-but-the-details keeps its overlap-free minimum,
        # and the details floor is what's left under 90 % of the screen — so
        # the whole dialog always fits, and smaller screens get a working
        # scrollbar instead of an off-screen bottom.
        from PyQt6.QtGui import QGuiApplication
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None and self.layout() is not None:
            self.layout().activate()
            others = (self.layout().minimumSize().height()
                      - self._scroll.minimumHeight())
            avail = int(screen.availableGeometry().height() * 0.9)
            self._scroll.setMinimumHeight(max(240, min(720, avail - others)))
        pin_min_height(
            self, min_width=720, wrap_labels=(self._body, self._banner),
            inner_margins=self._inner.contentsMargins(), resize_width=True)

    # ------------------------------------------------------------------
    def _on_browse(self) -> None:
        start = str(_chromiq_root(self._settings))
        path = open_file_dialog(
            self, tr("Select a .ti3 measurement"),
            tr("Measurements (*.ti3);;All files (*)"), start_dir=start)
        if path:
            self.load_measurement(Path(path))

    def load_measurement(self, path: Path) -> None:
        self._path_edit.setText(str(path))
        try:
            data = parse_ti3(path)
            self._analysis = analyse_ti3(data)
        except (OSError, Ti3ParseError) as exc:
            self._analysis = None
            self._show_error(str(exc))
            return
        self._banner.setVisible(False)
        self._accuracy = None
        self._accuracy_msg = ""
        # A file the Measure tab tagged as a colour-managed verification read
        # → default straight into Verify mode.
        if is_verification_ti3(data):
            self._rb_verify.setChecked(True)
        self._recompute_accuracy()   # re-score against any attached comparison
        self._render()
        self._save_btn.setEnabled(True)
        self._body.setText(
            tr("Showing the measurement “{name}”.").format(name=path.name))

    # ------------------------------------------------------------------
    # Verification controls
    # ------------------------------------------------------------------
    def _render(self) -> None:
        if self._analysis is not None:
            self._populate(self._analysis)

    def _on_mode_changed(self, _checked: bool = False) -> None:
        self._mode = "inspect" if self._rb_inspect.isChecked() else "verify"
        self._verify_box.setVisible(self._mode == "verify")
        self._render()

    def _on_basis_changed(self, _i: int = 0) -> None:
        self._basis = self._basis_combo.currentData()
        self._render()

    def _on_compare_kind_changed(self, _i: int = 0) -> None:
        self._compare_kind = self._cmp_combo.currentData()
        self._compare_path = None
        self._cmp_path.clear()
        self._accuracy = None
        self._accuracy_msg = ""
        want = self._compare_kind != "none"
        self._cmp_path.setVisible(want)
        self._cmp_browse.setVisible(want)
        self._render()

    def _on_compare_browse(self) -> None:
        if self._compare_kind == "profile":
            title, filt = tr("Select a profile (.icc)"), \
                tr("ICC profiles (*.icc *.icm);;All files (*)")
        else:
            title, filt = tr("Select a reference (.ti3 / table)"), \
                tr("Reference (*.ti3 *.ti1 *.ti2 *.cie *.txt);;All files (*)")
        start = str(_chromiq_root(self._settings))
        path = open_file_dialog(self, title, filt, start_dir=start)
        if not path:
            return
        self._compare_path = Path(path)
        self._cmp_path.setText(path)
        self._recompute_accuracy()
        self._render()

    def _recompute_accuracy(self) -> None:
        """Score the measurement against the attached comparison. Reference is
        pure Python; profile defers to ArgyllCMS profcheck (async)."""
        self._accuracy = None
        self._accuracy_msg = ""
        if (self._analysis is None or self._compare_kind == "none"
                or self._compare_path is None):
            return
        if self._compare_kind == "reference":
            try:
                refs = parse_reference_labs(self._compare_path)
                self._accuracy = accuracy_vs_reference(self._analysis.data, refs)
                if self._accuracy is None:
                    self._accuracy_msg = tr(
                        "No patch IDs in the reference matched this measurement.")
            except (OSError, Ti3ParseError) as exc:
                self._accuracy_msg = tr("Couldn't read the reference: {msg}").format(
                    msg=str(exc))
        else:  # profile → profcheck
            self._run_profcheck()

    def _run_profcheck(self) -> None:
        from workflow.icc_info import is_v4
        if is_v4(self._compare_path):
            self._accuracy_msg = tr(
                "This is an ICC v4 profile — ArgyllCMS can only score v2 profiles.")
            return
        if self._runner.is_running:
            self._accuracy_msg = tr("Another ArgyllCMS process is running — try again.")
            return
        from workflow.profcheck_runner import ProfcheckParams, ProfcheckRunner
        self._accuracy_msg = tr("Scoring against the profile…")
        # Relative basis ↔ relative intent, so the score matches how the print
        # was rendered; CIEDE2000 to match the reference path.
        params = ProfcheckParams(
            ti3_path=self._analysis.data.path, icc_path=self._compare_path,
            de_formula="-k", intent="r" if self._basis == "media" else "a")
        self._pc_runner = ProfcheckRunner(self._runner)

        def _finish(code: int) -> None:
            res = self._pc_runner.parse_results()
            if res.patch_errors:
                self._accuracy = accuracy_from_profcheck(
                    self._analysis.data, res.patch_errors)
                self._accuracy_msg = ""
            else:
                fail = self._pc_runner.primary_failure()
                self._accuracy_msg = (fail[1] if fail else
                                      tr("profcheck returned no per-patch results."))
            self._render()

        self._pc_runner.run(params, on_line=lambda _l: None, on_finish=_finish)

    def _on_save_report(self) -> None:
        if self._analysis is None:
            return
        src = self._analysis.data.path
        from datetime import datetime

        from core.version import APP_VERSION
        header = [
            tr("ChromIQ — Measurement report"),
            tr("Measurement: {name}").format(name=src.name),
            tr("Generated by ChromIQ {ver} on {date}").format(
                ver=APP_VERSION, date=datetime.now().strftime("%Y-%m-%d %H:%M")),
            "=" * 60,
        ]
        text = "\n".join(header + self._report) + "\n"
        default = f"{src.stem}-report.txt"
        out = save_file_dialog(
            self, tr("Save measurement report"),
            tr("Text files (*.txt);;All files (*)"),
            start_path=str(src.parent / default),
            extra_paths=[str(src.parent)])
        if not out:
            return
        if not out.lower().endswith(".txt"):
            out += ".txt"
        try:
            Path(out).write_text(text, encoding="utf-8")
        except OSError as exc:
            self._show_error(tr("Could not save the report: {msg}").format(msg=str(exc)))

    def _show_error(self, msg: str) -> None:
        self._clear_grid()
        self._banner.setText(tr("Could not read this measurement: {msg}").format(msg=msg))
        self._banner.setStyleSheet(
            banner_qss("#ff4573", "rgba(255,69,115,0.12)", kind="error"))
        self._banner.setVisible(True)

    # ------------------------------------------------------------------
    # Details grid
    # ------------------------------------------------------------------
    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._row = 0
        self._report = []

    def _section(self, title: str, tooltip: str = "") -> None:
        lbl = QLabel(title, self._details)
        lbl.setStyleSheet(
            f"color: {_ACCENT}; font-weight: 600; font-size: 12px;"
            f" padding-top: {'10px' if self._row else '0px'}; padding-bottom: 2px;")
        if tooltip:
            lbl.setToolTip(tooltip)
        self._grid.addWidget(lbl, self._row, 0, 1, 2)
        self._row += 1
        self._report.append("")
        self._report.append(f"{title}")

    def _row_kv(self, key: str, value: str, tooltip: str = "") -> None:
        k = QLabel(key, self._details)
        k.setStyleSheet(
            f"color: {self._text_dim}; font-family: Menlo, Consolas, monospace; font-size: 11px;")
        k.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v = QLabel(value or "—", self._details)
        v.setWordWrap(True)
        v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.setStyleSheet(
            f"color: {self._text_main}; font-family: Menlo, Consolas, monospace; font-size: 12px;")
        if tooltip:
            k.setToolTip(tooltip)
            v.setToolTip(tooltip)
        self._grid.addWidget(k, self._row, 0)
        self._grid.addWidget(v, self._row, 1)
        self._row += 1
        self._report.append(f"  {key}: {value or '—'}")

    def _grey_raw_section(self, a: Ti3Analysis) -> None:
        """Inspect mode: the printer's native (uncorrected) grey cast vs D50."""
        self._section(tr("Grey balance"), tr(
            "How neutral your greys measured before profiling. A printer's raw "
            "greys almost always have a colour tint — this is exactly what the "
            "profile then corrects, so a bigger cast here means the profile is "
            "working harder, not that your prints will look wrong."))
        self._row_kv(
            tr("Neutral patches"), tr("{n}").format(n=a.n_neutral),
            tr("How many patches had equal amounts of R, G and B (the grey "
               "ramp). These are what we measure the cast from."))
        self._row_kv(
            tr("Average cast"), tr("{c:.1f} C*").format(c=a.mean_cast),
            tr("On average, how far the greys drifted away from truly neutral "
               "(their chroma). 0 would be perfectly neutral; a few units is "
               "normal for an unprofiled printer."))
        self._row_kv(
            tr("Largest cast"), tr("{c:.1f} C*  at L* {l:.0f}").format(
                c=a.max_cast, l=a.max_cast_lstar),
            tr("The strongest tint found in the grey ramp, and the lightness it "
               "happened at. Casts often peak in the shadows or highlights."))
        self._row_kv(
            tr("Tendency"), _cast_text(a.cast_token),
            tr("Which way the greys lean overall — for example slightly warm/"
               "yellow or cool/blue. Tells you the character of your raw output "
               "that the profile neutralises."))

    def _grey_residual_section(self, a: Ti3Analysis) -> None:
        """Verify mode: the cast LEFT OVER after the profile corrected the
        greys, measured against the chosen white."""
        r = neutral_residual(a, self._basis)
        basis_word = (tr("relative to paper white") if r.basis == "media"
                      else tr("absolute (D50)"))
        self._section(tr("Grey balance — residual"), tr(
            "How neutral the greys are AFTER correction, now that the chart was "
            "printed through a profile. This is the cast the profile couldn't "
            "remove — so here, lower is better (a good profile lands near 0). "
            "Measured {basis}.").format(basis=basis_word))
        self._row_kv(
            tr("Neutral patches"), tr("{n}").format(n=a.n_neutral),
            tr("How many equal-R-G-B patches were checked for leftover cast."))
        self._row_kv(
            tr("Average residual"), tr("{c:.1f} C*").format(c=r.mean_c),
            tr("Average leftover chroma on the greys after correction, measured "
               "{basis}. Under ~1 is excellent; lower is better.").format(
                   basis=basis_word))
        self._row_kv(
            tr("Worst residual"), tr("{c:.1f} C*  at L* {l:.0f}").format(
                c=r.worst_c, l=r.worst_lstar),
            tr("The greatest leftover cast among the greys and where it sits. "
               "Residual cast often lingers in the deep shadows."))
        self._row_kv(
            tr("Tendency"), _cast_text(r.cast_token),
            tr("Which way any leftover cast leans. With a good profile this is "
               "negligible; a clear lean points to a profile or print-setup issue."))

    def _accuracy_section(self) -> None:
        """Verify mode: per-patch colour accuracy vs the attached profile/reference."""
        if self._compare_kind == "none":
            return
        self._section(tr("Colour accuracy"), tr(
            "How closely each patch matched its target, patch by patch, as a "
            "colour difference (ΔE₀₀ — roughly, 1 is a just-noticeable change). "
            "This needs the attached profile or reference; without one, only the "
            "residual grey cast above is available."))
        acc = self._accuracy
        if acc is None:
            self._row_kv(tr("Status"), self._accuracy_msg or tr("—"),
                         self._accuracy_msg)
            return
        src = (tr("vs the profile's prediction") if acc.source == "profile"
               else tr("vs the reference target"))
        self._row_kv(
            tr("Compared"), tr("{n} patches  ·  {src}").format(n=acc.n, src=src),
            tr("How many patches were matched (by patch ID) and what they were "
               "compared against."))
        self._row_kv(
            tr("Average ΔE₀₀"), tr("{de:.2f}").format(de=acc.mean_de),
            tr("The typical colour error across all matched patches. As a rough "
               "guide: under 1 is excellent, under 2 very good, under 3 good; "
               "above ~5 something is off (wrong intent, wrong profile, or a "
               "misprint)."))
        self._row_kv(
            tr("Worst ΔE₀₀"), tr("{de:.2f}  (patch {id}, {hue})").format(
                de=acc.peak_de, id=acc.worst_id, hue=_bucket_text(acc.worst_hue)),
            tr("The single largest colour error and which patch it was. One bad "
               "patch is often a misread or an out-of-gamut colour rather than a "
               "profile fault."))
        # Per-hue/neutral breakdown, worst-first.
        order = sorted(acc.buckets.items(), key=lambda kv: kv[1][0], reverse=True)
        bd = "  ".join(f"{_bucket_text(name)} {mean:.1f}"
                       for name, (mean, _pk, _n) in order)
        self._row_kv(
            tr("By colour"), bd,
            tr("Average error split by colour direction (and the neutrals). It "
               "shows where the profile is weakest — for example a high blue "
               "number means blues are the hardest for this paper-and-ink."))

    def _populate(self, a: Ti3Analysis) -> None:
        self._clear_grid()
        self._text_main, self._text_dim = self._resolve_text_colors()
        kw = a.data.keywords

        # --- Measurement -------------------------------------------------
        self._section(tr("Measurement"), tr(
            "The basic facts about this chart and how it was read."))
        self._row_kv(
            tr("Patches"), tr("{n:,}").format(n=a.data.n_patches),
            tr("How many colour patches were printed and measured. More patches "
               "generally let the profile describe your printer more accurately."))
        self._row_kv(
            tr("Instrument"), kw.get("TARGET_INSTRUMENT", "—"),
            tr("The measuring device that read the chart. Different instruments "
               "can disagree slightly, so it's good to know which one produced "
               "these numbers."))
        self._row_kv(
            tr("Device"), kw.get("DEVICE_CLASS", "—") + "  ·  "
            + kw.get("COLOR_REP", ""),
            tr("What kind of device was measured (here an OUTPUT printer) and the "
               "colour encoding — for example iRGB_XYZ means device RGB in, "
               "measured XYZ out."))
        spec = (tr("yes — {b} bands, {lo:.0f}–{hi:.0f} nm").format(
                    b=len(a.data.wavelengths), lo=a.data.wavelengths[0],
                    hi=a.data.wavelengths[-1])
                if a.data.has_spectral else tr("no (XYZ/Lab only)"))
        self._row_kv(
            tr("Spectral data"), spec,
            tr("Whether the file stores the full colour spectrum of each patch, "
               "not just a single XYZ value. Spectral data lets ChromIQ "
               "recompute the colours under different lighting (see below)."))
        if kw.get("CREATED"):
            self._row_kv(tr("Measured on"), kw["CREATED"], tr(
                "When the chart was read. Inks and paper can drift over time, so "
                "an old measurement may no longer match today's prints."))

        # --- Tone & contrast ---------------------------------------------
        self._section(tr("Tone & contrast"), tr(
            "How light the paper is, how dark the black is, and the range "
            "between them — taken straight from the lightest and darkest "
            "patches actually measured."))
        self._row_kv(
            tr("Paper white L*"), tr("{l:.1f}").format(l=a.white_lab[0]),
            tr("Lightness of the blank paper on the 0–100 L* scale — the "
               "brightest your prints can be. Higher is a whiter paper."))
        self._row_kv(
            tr("Max black L*"), tr("{l:.1f}").format(l=a.black_lab[0]),
            tr("Lightness of the deepest black this paper-and-ink reached. "
               "Lower is a richer black and usually means more contrast and "
               "better shadow detail."))
        self._row_kv(
            tr("Contrast ratio"), tr("{r:,.0f} : 1").format(r=a.contrast_ratio),
            tr("How many times brighter the paper white is than the deepest "
               "black. Bigger means punchier prints. This is the measured "
               "contrast — the honest figure for this paper-and-ink, which is "
               "what you started out asking about."))
        self._row_kv(
            tr("Dynamic range"), tr("{d:.2f} D").format(d=a.dynamic_range),
            tr("The same contrast written as optical density, the way print and "
               "photo people measure it — the span from lightest to darkest "
               "tone. Each whole step is a ten-fold change in reflected light; "
               "around 2.2 D and up is excellent for inkjet."))
        self._row_kv(
            tr("Lightness range ΔL*"), tr("{d:.1f}").format(d=a.delta_lstar),
            tr("The plain lightness gap between paper white and max black on the "
               "L* scale — a quick, perceptual feel for the contrast."))

        # --- Grey balance (wording + maths depend on mode) ---------------
        if self._mode == "verify":
            self._grey_residual_section(a)
            self._accuracy_section()
        else:
            self._grey_raw_section(a)

        # --- Gamut --------------------------------------------------------
        self._section(tr("Gamut reach"), tr(
            "The most saturated colours your paper-and-ink managed to print. "
            "A wider reach means more vivid colours are possible."))
        self._row_kv(
            tr("Most saturated"), tr("C* {c:.0f}  ({hue})").format(
                c=a.max_chroma, hue=_hue_text(a.max_chroma_hue)),
            tr("The single most vivid patch measured and roughly its hue. On "
               "most inkjet papers this is a yellow or orange, which the eye "
               "sees as the punchiest colour."))
        prim = a.primary_chroma
        # Universal channel letters (R Y G C B M) — not translated.
        letters = {"red": "R", "yellow": "Y", "green": "G",
                   "cyan": "C", "blue": "B", "magenta": "M"}
        prim_txt = "  ".join(
            f"{letters[p]}{int(round(prim[p]))}" for p in letters)
        self._row_kv(
            tr("Per-hue peak C*"), prim_txt,
            tr("The strongest chroma reached in each colour direction (Red, "
               "Yellow, Green, Cyan, Blue, Magenta). Lets you see if one "
               "direction — say, a weak cyan — is limiting your gamut."))
        if a.has_rolloff:
            self._row_kv(
                tr("Note"), tr("⚠ see tooltip"),
                tr("Full-ink primaries measured notably less saturated than "
                   "mid-tone ones — sometimes a sign the printer driver applied "
                   "colour management despite a “No Correction” setting. Worth "
                   "checking if the print looked dull."))

        # --- Quality ------------------------------------------------------
        self._section(tr("Measurement quality"), tr(
            "Sanity checks that catch a bad read before you build a profile "
            "from it."))
        mono = (tr("clean — greys get lighter step by step")
                if a.neutral_non_monotonic == 0
                else tr("1 reversal — possible misread")
                if a.neutral_non_monotonic == 1
                else tr("{n} reversals — possible misread")
                .format(n=a.neutral_non_monotonic))
        self._row_kv(
            tr("Neutral ramp"), mono,
            tr("Going up the grey ramp, each step should measure lighter than "
               "the last. A step that goes darker usually means a strip was "
               "read in the wrong order or place — a classic cause of broken "
               "profiles. Clean is what you want here."))
        if a.duplicate_max_de is not None:
            self._row_kv(
                tr("Repeat scatter"),
                tr("{de:.2f} ΔE  over {n} repeats").format(
                    de=a.duplicate_max_de, n=a.duplicate_count),
                tr("Some charts print the same colour more than once. This is "
                   "the biggest colour difference between copies of the same "
                   "patch — a direct measure of how repeatable the read was. "
                   "Under ~1 ΔE is excellent; large values hint at instrument "
                   "noise or a smudged chart."))

        # --- Under other light -------------------------------------------
        if a.illuminant_points:
            self._section(tr("Under other light"), tr(
                "Using the spectral data, the paper white recomputed as if lit "
                "by different standard light sources. Shows how your paper's "
                "tint and contrast change with the lighting it's viewed in — "
                "useful if prints are shown under shop or gallery lights rather "
                "than daylight."))
            for p in a.illuminant_points:
                self._row_kv(
                    p.name,
                    tr("L* {l:.1f}   a* {a:+.1f}   b* {b:+.1f}   ·   {r:,.0f}:1").format(
                        l=p.lab[0], a=p.lab[1], b=p.lab[2], r=p.contrast_ratio),
                    tr("The paper white's lightness (L*) and tint (a* green↔red, "
                       "b* blue↔yellow) under {name}, plus the contrast ratio. "
                       "Compare the rows: if a*/b* change a lot between lights, "
                       "your paper is metameric or brightened and will look "
                       "different depending on where it's displayed.").format(
                           name=p.name))
            if a.paper_shift_d50_d65 is not None:
                self._row_kv(
                    tr("Daylight shift"),
                    tr("{de:.1f} ΔE  (D50 → D65)").format(de=a.paper_shift_d50_d65),
                    tr("How much the paper white's colour shifts between warm "
                       "daylight (D50, the printing standard) and cool daylight "
                       "(D65, a typical screen white). A small number means the "
                       "paper looks consistent across lighting; a large one "
                       "means it's strongly brightened (lots of optical "
                       "brightener) and will change noticeably."))


def _bucket_text(name: str) -> str:
    return {
        "neutral": tr("neutral"), "red": tr("red"), "yellow": tr("yellow"),
        "green": tr("green"), "cyan": tr("cyan"), "blue": tr("blue"),
        "magenta": tr("magenta"),
    }.get(name, name)


def _cast_text(token: str) -> str:
    return {
        "neutral": tr("neutral (no significant cast)"),
        "warm": tr("slightly warm / yellow"),
        "cool": tr("slightly cool / blue"),
        "green": tr("slightly green"),
        "magenta": tr("slightly magenta"),
        "none": tr("no neutral patches found"),
    }.get(token, token)


def _hue_text(deg: float) -> str:
    # Lab hue angles: red ≈ 40°, yellow ≈ 95°, green ≈ 135°, cyan ≈ 195°,
    # blue ≈ 270°, magenta ≈ 330°.
    table = [(40, tr("red")), (70, tr("orange")), (105, tr("yellow")),
             (160, tr("green")), (210, tr("cyan")), (280, tr("blue")),
             (340, tr("magenta")), (360, tr("red"))]
    for edge, name in table:
        if deg < edge:
            return name
    return tr("red")
