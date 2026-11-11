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
    QDoubleSpinBox,
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

from core.i18n import decimal_text, tr
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

from workflow.reading_compare import (
    DEFAULT_TOLERANCE,
    TOLERANCE_MAX,
    TOLERANCE_MIN,
    TOLERANCE_PRESETS,
    TOLERANCE_STEP,
    WORST_SHOWN,
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



def _instrument_text(kw: dict) -> str:
    """The instrument row: ArgyllCMS's name, and i1Profiler's own beside it
    for a measurement imported from i1Profiler (4.3.23 writes ArgyllCMS's
    name, so that FWA compensation can find the instrument)."""
    name = kw.get("TARGET_INSTRUMENT") or "\u2014"
    i1p = kw.get("CHROMIQ_I1P_INSTRUMENT")
    if i1p and i1p != name:
        return tr("{name} (in i1Profiler: {i1p})").format(name=name, i1p=i1p)
    return name

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
        # another reading of the same chart (4.3.32)
        self._second_path: Path | None = None
        self._second = None             # reading_compare.Comparison | None
        self._second_error: tuple[str, str] | None = None
        self._tolerance = DEFAULT_TOLERANCE
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

        # --- Another reading of this chart (4.3.32, both modes) -----------
        self._build_second_reading_rows()

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
        self._save_btn = QPushButton(tr("Save inspection…"), self)
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
        # K44 (Knut, #182 5833983335): the button Return presses is drawn
        # filled. Qt made the first button created the default here, a
        # file chooser; this window has no main action for Return (C9).
        from ui.dialogs.no_default_button import no_default_button
        no_default_button(self)
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
        # A CMYK OR MULTI-INK MEASUREMENT (beta 7) is not a read error: this
        # view reads RGB device values only, and says so in M-VIEW-RGB-ONLY's
        # words instead of "Could not read this measurement: No device RGB
        # columns".
        from workflow.ti3_analysis import non_rgb_note
        _note = non_rgb_note(path)
        if _note is not None:
            self._analysis = None
            self._clear_grid()
            self._banner.setText(_note[0] + "\n\n" + _note[1])
            self._banner.setStyleSheet(
                banner_qss("#3b82f6", "rgba(59,130,246,0.10)", kind="warn"))
            self._banner.setVisible(True)
            self._save_btn.setEnabled(False)
            return
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
        self._recompute_second()     # and against another reading, if any
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

    # ------------------------------------------------------------------
    # Another reading of this chart (4.3.32, jctay)
    # ------------------------------------------------------------------
    def _build_second_reading_rows(self) -> None:
        """The row that takes a second reading of the same chart, and the
        tolerance row under it. Shown in both modes: two readings of a raw
        chart are the usual case."""
        tip = tr(
            "Compare this measurement with another reading of the same chart: "
            "the same printed sheet measured again, or a second print of the "
            "same chart. ChromIQ pairs every patch with the same patch in the "
            "other file and shows how far apart the two readings are (as "
            "ΔE₀₀, where about 1 is a difference you can just see), which "
            "patches and strips disagree most, and how many patches lie above "
            "a tolerance you choose.\n\n"
            "The second reading can be a measurement file (.ti3), a CGATS text "
            "file with XYZ or L*a*b* values, or an i1Profiler measurement "
            "(.mxf or .cxf), which ChromIQ reads directly.\n\n"
            "Before comparing, ChromIQ checks that both files hold the same "
            "chart: the same number of patches, and the same device values "
            "(the colour numbers each patch was printed with) on every pair. "
            "Files of different charts are refused rather than compared patch "
            "by wrong patch.\n\n"
            "Nothing is changed: not this measurement, not the second reading, "
            "and no profile.")
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(tr("Another reading:"), self)
        lbl.setToolTip(tip)
        lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        row.addWidget(lbl)
        self._second_edit = QLineEdit(self)
        self._second_edit.setReadOnly(True)
        self._second_edit.setPlaceholderText(
            tr("Optional: a second reading of the same chart…"))
        self._second_edit.setToolTip(tip)
        row.addWidget(self._second_edit, 1)
        self._second_browse = make_browse_button(
            self, tr("Browse for another reading of this chart"),
            "folder_build")
        self._second_browse.clicked.connect(self._on_second_browse)
        row.addWidget(self._second_browse)
        self._second_clear = QPushButton(tr("Clear"), self)
        self._second_clear.setToolTip(
            tr("Stop comparing with the second reading."))
        self._second_clear.setEnabled(False)
        self._second_clear.clicked.connect(self._on_second_clear)
        row.addWidget(self._second_clear)
        row.addWidget(TooltipButton(
            tr("Another reading of this chart"), tip, self, color=_ACCENT))
        self._inner.addLayout(row)

        tol_tip = tr(
            "The colour difference (ΔE₀₀) above which a patch counts as a "
            "disagreement between the two readings. About 1.0 suits a chart "
            "scanned with an instrument such as the i1Pro. 0.5 suits a very "
            "consistent setup, for example an instrument guided by a ruler "
            "and both readings taken one after the other. 2.0 suits readings "
            "taken by hand. Choose Custom to type your own value.")
        self._tol_box = QWidget(self)
        tl = QHBoxLayout(self._tol_box)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)
        tlbl = QLabel(tr("Tolerance:"), self._tol_box)
        tlbl.setToolTip(tol_tip)
        tl.addWidget(tlbl)
        self._tol_combo = NoScrollComboBox(self._tol_box)
        names = {0.5: tr("{value}  (very consistent setup)"),
                 1.0: tr("{value}  (scanned with an i1Pro or similar)"),
                 2.0: tr("{value}  (readings taken by hand)")}
        for v in TOLERANCE_PRESETS:
            self._tol_combo.addItem(
                names.get(v, "{value}").format(value=decimal_text(v, 1)), v)
        self._tol_combo.addItem(tr("Custom"), "custom")
        self._tol_combo.setCurrentIndex(
            list(TOLERANCE_PRESETS).index(DEFAULT_TOLERANCE))
        self._tol_combo.setToolTip(tol_tip)
        self._tol_combo.currentIndexChanged.connect(self._on_tolerance_changed)
        tl.addWidget(self._tol_combo)
        self._tol_spin = QDoubleSpinBox(self._tol_box)
        self._tol_spin.setDecimals(1)
        self._tol_spin.setRange(TOLERANCE_MIN, TOLERANCE_MAX)
        self._tol_spin.setSingleStep(TOLERANCE_STEP)
        self._tol_spin.setValue(DEFAULT_TOLERANCE)
        self._tol_spin.setPrefix("ΔE₀₀ ")
        self._tol_spin.setToolTip(tol_tip)
        self._tol_spin.setVisible(False)
        self._tol_spin.valueChanged.connect(self._on_tolerance_changed)
        tl.addWidget(self._tol_spin)
        tl.addStretch(1)
        tl.addWidget(TooltipButton(tr("Tolerance"), tol_tip, self._tol_box,
                                   color=_ACCENT))
        self._tol_box.setVisible(False)
        self._inner.addWidget(self._tol_box)

    def _on_second_browse(self) -> None:
        start = (str(self._analysis.data.path.parent)
                 if self._analysis is not None
                 else str(_chromiq_root(self._settings)))
        path = open_file_dialog(
            self, tr("Select another reading of this chart"),
            tr("Readings (*.ti3 *.txt *.mxf *.cxf);;All files (*)"),
            start_dir=start)
        if path:
            self.load_second_reading(Path(path))

    def load_second_reading(self, path: "Path | None") -> None:
        """Compare with *path* (None stops comparing)."""
        self._second_path = Path(path) if path else None
        self._second_edit.setText(str(path) if path else "")
        self._second_clear.setEnabled(path is not None)
        self._tol_box.setVisible(path is not None)
        self._recompute_second()
        self._render()

    def _on_second_clear(self) -> None:
        self.load_second_reading(None)

    def _on_tolerance_changed(self, *_a) -> None:
        data = self._tol_combo.currentData()
        custom = data == "custom"
        self._tol_spin.setVisible(custom)
        self._tolerance = (float(self._tol_spin.value()) if custom
                           else float(data))
        self._render()

    def _recompute_second(self) -> None:
        """Pair and compare the second reading with the measurement shown.
        Pure Python; the files are only read."""
        from workflow.reading_compare import (ReadingsNotComparable, compare,
                                              load_reading, reading_from_ti3)
        self._second = None
        self._second_error = None
        if self._analysis is None or self._second_path is None:
            return
        try:
            a = reading_from_ti3(self._analysis.data.path)
            b = load_reading(self._second_path, a.condition)
            self._second = compare(a, b)
        except ReadingsNotComparable as exc:
            self._second_error = exc.render(self._second_path.name)
            log.info("compare readings: refused %s: %s",
                     self._second_path.name, exc.reason)

    def _second_section(self) -> None:
        """The result of the comparison with another reading, or why there
        is none."""
        if self._second_path is None:
            return
        self._section(tr("Another reading of this chart"), tr(
            "How far a second reading of the same chart is from this "
            "measurement, patch by patch, as a colour difference (ΔE₀₀; about "
            "1 is a difference you can just see)."))
        if self._second_error is not None:
            title, body = self._second_error
            self._row_kv(tr("Not compared"), f"{title}\n\n{body}")
            return
        c = self._second
        if c is None:
            return
        tol = self._tolerance
        name = c.b.path.name
        if c.b.converted_from_cxf and c.b.condition:
            name = tr("{name} (i1Profiler measurement, condition {cond})"
                      ).format(name=name, cond=c.b.condition)
        self._row_kv(tr("Second reading"), name, tr(
            "The file this measurement is compared with. An i1Profiler "
            "measurement is read directly; ChromIQ takes the same measurement "
            "condition as this measurement when the file holds it."))
        if c.paired_by == "device":
            how = tr("device values, because the patch numbers of the two "
                     "files do not line up (for example, one file was saved "
                     "on another grid or in another order)")
        else:
            how = tr("patch number")
        self._row_kv(tr("Paired by"), how, tr(
            "How each patch of this measurement found its partner in the "
            "second reading. Both ways were checked against the device values "
            "(the colour numbers each patch was printed with), so every pair "
            "is the same patch of the chart."))
        if not c.device_checked:
            self._row_kv(tr("Same chart?"), tr(
                "not checked: one of the files holds no device values, so "
                "ChromIQ paired the patches by patch number alone. Make sure "
                "both files are readings of the same chart."))
        if c.left_out:
            self._row_kv(tr("Left out"), (tr(
                "1 patch, because its device value appears more than once in "
                "the chart and ChromIQ cannot tell those copies apart")
                if c.left_out == 1 else tr(
                "{n} patches, because their device values appear more than "
                "once in the chart and ChromIQ cannot tell those copies "
                "apart").format(n=c.left_out)))
        self._row_kv(tr("Compared"),
                     tr("1 patch") if c.n == 1 else
                     tr("{n} patches").format(n=c.n))
        self._row_kv(tr("Average ΔE₀₀"), decimal_text(c.mean, 2), tr(
            "The average difference between the two readings over all "
            "compared patches. Two careful readings of the same print with "
            "the same instrument often average a few tenths; much more points "
            "to noise, a moving instrument or a misread strip."))
        self._row_kv(tr("Median ΔE₀₀"), decimal_text(c.median, 2), tr(
            "The middle value: half of the patches differ less than this, "
            "half more. A few badly read patches do not pull it up, so a "
            "median well below the average means that a few patches disagree "
            "strongly."))
        self._row_kv(tr("95th percentile ΔE₀₀"), decimal_text(c.p95, 2), tr(
            "95 out of every 100 patches differ by this much or less. It "
            "shows how large the bigger differences are, without being "
            "decided by one single patch."))
        self._row_kv(tr("Largest ΔE₀₀"), decimal_text(c.worst, 2), tr(
            "The largest difference of all, on the first patch in the list "
            "below."))
        above = c.above(tol)
        share = decimal_text(100.0 * len(above) / c.n, 1) if c.n else "0"
        if not above:
            txt = (tr("none") if c.n == 1 else
                   tr("none of the {n} patches").format(n=c.n))
        elif len(above) == 1:
            txt = tr("1 of {n} patches ({share} %)").format(n=c.n,
                                                             share=share)
        else:
            txt = tr("{k} of {n} patches ({share} %)").format(
                k=len(above), n=c.n, share=share)
        self._row_kv(tr("Above the tolerance"), txt, tr(
            "How many patches differ by more than the tolerance chosen above "
            "(ΔE₀₀ {tol}). These are the patches worth measuring a third "
            "time.").format(tol=decimal_text(tol, 1)))

        worst = c.worst_patches(WORST_SHOWN)
        self._row_kv(tr("Largest differences"), tr(
            "the patches where the two readings differ most, largest first"))
        for p in worst:
            self._row_kv(self._patch_key(p), self._patch_value(p, tol))

        strips = c.strips(tol)
        if strips:
            flagged = [s for s in strips if s.whole_strip_off]
            shown = strips[:5] + [s for s in flagged if s not in strips[:5]]
            self._row_kv(tr("By strip"), tr(
                "the printed strips whose patches differ most on average"),
                tr("A whole strip that disagrees points at one strip read "
                   "badly in one of the two readings (a slipped strip, or "
                   "the wrong strip read), rather than at the instrument's "
                   "ordinary scatter."))
            for s in shown:
                val = tr("average {mean}, largest {worst}, {k} of {n} "
                         "patches above the tolerance").format(
                    mean=decimal_text(s.mean, 2),
                    worst=decimal_text(s.worst, 2), k=s.above, n=s.n)
                if s.whole_strip_off:
                    val += "\n" + tr(
                        "Nearly the whole strip disagrees: one of the two "
                        "readings of this strip is probably off (a slipped "
                        "or misread strip). Read this strip again.")
                self._row_kv(tr("Strip {label}").format(label=s.label), val)

        self._row_kv(tr("What this tells you"), tr(
            "Two readings show where they disagree and by how much. They "
            "cannot show which of the two is right: ChromIQ has nothing else "
            "to judge them by, and a difference looks the same whichever "
            "reading is off. To find out, measure the patches above the "
            "tolerance a third time and keep the two readings that agree. A "
            "whole strip that disagrees usually means that one reading of "
            "that strip slipped or was taken on the wrong strip, so read that "
            "strip again. Small differences spread over the whole chart are "
            "normal: no instrument reads the same patch exactly the same "
            "twice, and the backing under the paper, the position of the "
            "instrument, the temperature and ink that is still drying all add "
            "a little. Nothing here changes either file or any profile."))
        if above:
            # The saved inspection lists EVERY patch above the tolerance.
            self._report.append("")
            self._report.append(tr("All patches above the tolerance"))
            for p in above:
                self._report.append(
                    f"  {self._patch_key(p)}: "
                    + self._patch_value(p, tol).replace("\n", "  ·  "))

    @staticmethod
    def _patch_key(p) -> str:
        return tr("Patch {id}").format(id=p.sid)

    @staticmethod
    def _patch_value(p, tol: float) -> str:
        if p.strip is not None and p.position is not None:
            where = tr("strip {strip}, patch {pos} as printed").format(
                strip=p.strip, pos=p.position)
        elif p.loc and p.loc != p.sid:
            where = tr("location {loc}").format(loc=p.loc)
        else:
            where = ""
        head = tr("ΔE₀₀ {de}").format(de=decimal_text(p.de, 2))
        if p.de > tol + 1e-9:
            head += "  " + tr("(above the tolerance)")
        if where:
            head += "  ·  " + where

        def _lab(v) -> str:
            return tr("L* {l}  a* {a}  b* {b}").format(
                l=decimal_text(v[0], 1), a=decimal_text(v[1], 1),
                b=decimal_text(v[2], 1))
        return (head + "\n" + tr("this measurement: {lab}").format(
            lab=_lab(p.lab_a)) + "\n" + tr("second reading: {lab}").format(
            lab=_lab(p.lab_b)))

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
                    self._analysis.data, res.patch_errors, res.patch_rows)
                self._accuracy_msg = ""
            else:
                fail = self._pc_runner.primary_failure()
                self._accuracy_msg = (fail[1] if fail else
                                      tr("profcheck returned no per-patch results."))
            self._render()

        self._pc_runner.run(params, on_line=lambda _l: None, on_finish=_finish)

    def _on_save_report(self) -> None:
        """Save the inspection as text into the measurement owner's reports
        folder (#182 (b); Knut's B1, #182 5943085974).

        **NAMED SO IT CANNOT BE TAKEN FOR THE MEASUREMENT REPORT.** The file
        was ``<stem>-report.txt`` headed "ChromIQ — Measurement report", the
        name and the title of a different document. It is now
        ``"Measurement inspection - <name> - <date_time>.txt"``, the Measurement
        Report's own naming structure without its configurable title, and the
        text says "Measurement inspection" at the top. No PDF (B1)."""
        if self._analysis is None:
            return
        from ui.inspection_save import save_inspection
        src = self._analysis.data.path
        kind = tr("Measurement inspection")
        saved = save_inspection(
            self, src, kind, kind, self._report,
            dialog_title=tr("Save measurement inspection"),
            subject_line=tr("Measurement: {name}").format(name=src.name),
            ask=save_file_dialog)
        if saved.error:
            self._show_save_error(saved.error)
        elif saved.path is not None:
            self._banner.setVisible(False)

    def _show_save_error(self, msg: str) -> None:
        """A save that failed says so, and the inspection stays on screen.

        R182-1 (K_review_beta1): this went through `_show_error`, which
        empties the grid and says *"Could not read this measurement"*, so a
        read-only folder threw away an inspection that had been read perfectly
        well and blamed the measurement for it. Reading and saving are two
        different failures with two different messages."""
        self._banner.setText(
            tr("Could not save the report: {msg}").format(msg=msg))
        self._banner.setStyleSheet(
            banner_qss("#ff4573", "rgba(255,69,115,0.12)", kind="error"))
        self._banner.setVisible(True)

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
            tr("On average, how far the greys moved away from truly neutral "
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
        bd = "  ".join(f"{_bucket_text(name)} {decimal_text(mean, 1)}"
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
            tr("Instrument"), _instrument_text(kw),
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
        # A measurement imported from i1Profiler has no CREATED (the import
        # writes when it was MEASURED, CHROMIQ_MEASURED, not when it was
        # converted), so the date it was read is shown from that (4.3.23).
        measured_on = kw.get("CREATED") or kw.get("CHROMIQ_MEASURED")
        if measured_on:
            self._row_kv(tr("Measured on"), measured_on, tr(
                "When the chart was read. Inks and paper can change over time, so "
                "an old measurement may no longer match today's prints."))
        condition = kw.get("MEASUREMENT_CONDITION")
        if condition:
            from workflow.measurement_condition import condition_name
            self._row_kv(tr("Measurement condition"), condition_name(condition), tr(
                "How much ultraviolet light reached the paper while it was "
                "measured. M0 is the instrument's own lamp, M1 is like D50 "
                "daylight with its ultraviolet, and M2 cuts the ultraviolet "
                "out, as if the paper had no optical brighteners. Brightener "
                "compensation (FWA) only works with M0 readings."))

        # --- Another reading of this chart (4.3.32) ---------------------
        self._second_section()

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
