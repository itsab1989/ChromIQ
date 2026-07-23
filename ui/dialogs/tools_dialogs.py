"""Stand-alone utility dialogs launched from the masthead Tools popup.

Project-free file-in/file-out utilities, each wrapping logic that also lives in
the regular workflow:

  * Average measurements        (workflow.average_runner)
  * Merge measurements          (workflow.ti3_merge)
  * TI1  -> i1Profiler          (workflow.i1profiler_export)
  * i1Profiler .txt -> TI3      (Argyll txt2ti3 via ArgyllRunner)
  * i1Profiler -> TI1           (workflow.i1profiler_import)

Each dialog explains the tool in plain language, takes one or more input files,
asks for an output destination + filename, and runs the underlying logic. File
pickers default to the configured ChromIQ working folder on first open, then
remember the last-used directory per tool across sessions.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from datetime import datetime

from core.i18n import tr
from core.logger import get_logger
from ui.fade_scroll import FadeScrollArea
from ui.spectrum_progress import SpectrumSegmentsBar
from ui.styles import BG_INPUT, BORDER, SPEC_GREEN, SPEC_MAGENTA, SPEC_VIOLET, TEXT_MAIN
from ui.theme import resolve_mode
from ui.tab_header import dialog_masthead
from ui.tooltip_button import TooltipButton
from ui.widgets import (
    confirm, make_browse_button, NoScrollComboBox, NoScrollSpinBox,
    open_dir_dialog, open_file_dialog, open_files_dialog,
)


def _indicator_color(settings: "AppSettings") -> str:
    """The Tools-dialog ⓘ accent — the same light/dark indicator the Settings
    window uses (near-black on light, light-grey on dark)."""
    return "#1c1b18" if resolve_mode(settings.get("appearance", "auto")) == "light" else "#d0d0d0"


def neutral_controls_qss(color: str) -> str:
    """Dialog-scoped QSS that swaps the global cyan/blue ACCENT on interactive
    controls for the neutral light/dark *indicator* colour.

    The Settings window already does this for checkboxes and line-edit focus so
    its controls read as neutral chrome rather than the tab-accent cyan that has
    no meaning inside a dialog body. Tool dialogs share that look via this helper
    (checkbox/radio when checked, and the focus ring on every text/number/combo
    input), so every dialog in the app highlights its controls the same way.
    """
    return (
        f"QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{"
        f" border-color: {color}; }}"
        f"QCheckBox::indicator:checked {{ background: {color}; border-color: {color}; }}"
        f"QCheckBox::indicator:hover {{ border-color: {color}; }}"
        f"QRadioButton::indicator:checked {{ background: {color}; border-color: {color}; }}"
        f"QRadioButton::indicator:hover {{ border-color: {color}; }}"
        # A disabled checkbox/radio must read as off even when checked — without
        # this the accent :checked fill wins over Qt's disabled greying, so a
        # greyed-out option (e.g. "Highlight out-of-gamut" while soft-proof is
        # off) kept its bright tick. The two-state selector outranks :checked.
        f"QCheckBox::indicator:checked:disabled,"
        f" QRadioButton::indicator:checked:disabled {{"
        f" background: #4a4a4a; border-color: #4a4a4a; }}"
    )
from workflow.average_runner import AverageParams, AverageRunner
from workflow.colverify_runner import (
    ColverifyParams,
    ColverifyRunner,
    chart_patch_count,
    interpret,
    parse_reference_values,
    vrml_output_path,
    write_reference_ti3,
)
from ui.dialogs.drift_plot_dialog import DriftPlotDialog, webengine_available
from workflow.i1profiler_export import (
    WorkflowOptions, export_from_ti1, parse_ti1, write_pwxf,
)
from workflow.i1profiler_import import import_to_ti1
from workflow.profcheck_runner import (
    ProfcheckParams,
    ProfcheckRunner,
    quality_explanation,
    quality_grade,
)


# Instrument / paper presets for the optional i1Profiler workflow (.pwxf)
# output. The device string is free-form in the format; these are the values
# observed in real i1Profiler 1.1.0 exports. Paper maps to (PaperFormat enum,
# width_mm, height_mm, orientation) — A4 (enum 2) is the validated case; the
# others use Custom (enum 0). i1Profiler re-lays-out the chart on load anyway,
# so the page geometry is a starting point the user can change in-app.
_PWXF_SCAN_MODES = ((tr("Single scan"), 1), (tr("Dual scan"), 2))
_PWXF_PAPERS: dict[str, tuple[int, float, float, str]] = {
    "A4":        (2, 296.93, 210.06, "Landscape"),
    "A3":        (0, 420.00, 297.00, "Landscape"),
    "US Letter": (0, 279.40, 215.90, "Landscape"),
}

# Per-device data reverse-engineered from i1Profiler workflow files the user
# saved at each slider extreme (see docs/dev_pxwf_format.md). Tuple is
#   (w_lo, w_hi, h_lo, h_hi, mode, vorlauf)
#   w/h_lo,hi : patch-size slider range, mm. i1Profiler stores the patch size as
#               the slider position — PatchSize*Percent = (mm-lo)/(hi-lo)*100 —
#               and *ignores* the mm Value we write, so we emit the right percent.
#   mode      : forced MeasurementMode (PLUS → 1, M3 → 6, i1iSis → 1) or None to
#               let the user pick Single (1) / Dual (2).
#   vorlauf   : True for i1iSis. These sheet scanners have a "Vorlauf" (English:
#               header length) lead-in stored as HeaderEdgeSizePercent; non-iSis
#               write the -2147483648 sentinel. See _PWXF_VORLAUF_MM below for the
#               reverse-engineered range — it is *not* user-settable (see note).
# Observed scan-recommended minimums (warning thresholds, ≥ the slider min):
#   i1Pro 3 = 7, i1iO 3 = 7.5, PLUS M3 = 20 mm. Defaults sit at/above these.
_PWXF_DEVICES: dict[str, tuple[int, int, int, int, "int | None", bool]] = {
    "i1Pro 2":         (7, 25, 8, 12, None, False),
    "i1Pro 3":         (6, 25, 6, 12, None, False),
    "i1Pro 3 PLUS":    (16, 40, 16, 20, 1, False),
    "i1Pro 3 PLUS M3": (16, 40, 16, 20, 6, False),
    "i1iO 2":          (6, 20, 7, 20, None, False),
    "i1iO 3":          (6, 20, 7, 20, None, False),
    "i1iO 3 PLUS":     (16, 40, 16, 40, 1, False),
    "i1iO 3 PLUS M3":  (16, 40, 16, 40, 6, False),
    "i1iSis":          (6, 20, 6, 20, 1, True),
    "i1iSis 2":        (6, 20, 6, 20, 1, True),
    "i1iSis XL":       (6, 20, 6, 20, 1, True),
    "i1iSis 2 XL":     (6, 20, 6, 20, 1, True),
}
# i1iSis "Vorlauf" / header-length lead-in range, reverse-engineered from files
# saved at the slider extremes: HeaderEdgeSizePercent = (mm - 32) / 48 * 100
# (verified 32→0, 56→50, 80→100). Preserved as knowledge but DELIBERATELY NOT
# wired to any control: i1Profiler does not persist the lead-in — it resets to the
# 32 mm minimum on load no matter what the file contains (confirmed: even
# i1Profiler's *own* re-saved 56 mm file reopens at 32 mm). So we always write 0
# (= 32 mm) for i1iSis and offer no header-length UI.
_PWXF_VORLAUF_MM = (32, 80)


def _patch_percent(mm: float, lo: float, hi: float) -> float:
    """Slider position (0..100) for a ``mm`` value on a [lo, hi] mm range."""
    if hi <= lo:
        return 0.0
    return max(0.0, min(100.0, (mm - lo) / (hi - lo) * 100.0))


def _device_default_size(w_lo: int, w_hi: int, h_lo: int, h_hi: int) -> tuple[int, int]:
    """Warning-free default patch size for a device's slider range: 20×20 for the
    big-patch PLUS/M3 devices (20 mm scan min), else 8×7 clamped into range."""
    if w_lo >= 16:                       # PLUS / M3
        return min(20, w_hi), min(20, h_hi)
    return max(8, w_lo), max(7, h_lo)
from workflow.ti3_merge import Ti3MergeError, merge_measurements

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _working_dir(settings: "AppSettings") -> Path:
    custom = settings.get("custom_output_path", "")
    return Path(custom) if custom else Path.home() / "ChromIQ"


def _last_dir_key(tool_key: str) -> str:
    return f"tools_last_dir_{tool_key}"


def _initial_dir(settings: "AppSettings", tool_key: str) -> Path:
    stored = str(settings.get(_last_dir_key(tool_key), ""))
    if stored:
        p = Path(stored)
        if p.exists() and p.is_dir():
            return p
    return _working_dir(settings)


def _remember_dir(settings: "AppSettings", tool_key: str, path: Path) -> None:
    settings.set(_last_dir_key(tool_key), str(path))


# ---------------------------------------------------------------------------
# Base dialog
# ---------------------------------------------------------------------------

class _ToolDialogBase(QDialog):
    """Shared chrome: title, descriptive body, content area, log, Run/Close."""

    TOOL_KEY: str   = ""
    TITLE: str      = ""
    EYEBROW: str    = ""    # uppercase masthead eyebrow above the title
    ACCENT: str     = SPEC_MAGENTA   # masthead accent (stroke + ⓘ tint)
    DESCRIPTION: str = ""
    HELP: str       = ""    # extended ⓘ popup text; falls back to DESCRIPTION
    RUN_LABEL: str  = tr("Run")
    MIN_WIDTH: int  = 620
    SCROLLABLE_CONTENT: bool = False   # tall dialogs opt in (scroll + edge fade)
    # Set to a short idle label (e.g. tr("Ready")) to show an always-visible
    # spectrum busy bar above the log, animated only while a run is under way.
    BUSY_BAR_IDLE_LABEL: str | None = None

    def __init__(self, settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._sized_once = False
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        outer = QVBoxLayout(self)
        # Zero side margins so the masthead's spectrum stripe runs edge to edge;
        # the header and the inner content re-add the side inset themselves.
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Tab-style masthead (uppercase eyebrow + large serif title + ⓘ) over a
        # full-width spectrum stripe — the same look as the chart-design windows.
        head, self._header, stripe = dialog_masthead(
            self, self.EYEBROW, self.TITLE,
            tooltip_title=self.TITLE, tooltip_body=self.HELP or self.DESCRIPTION,
            accent=self.ACCENT)
        outer.addLayout(head)
        outer.addWidget(stripe)

        # Everything below the stripe is inset like the original dialog body.
        inner = QVBoxLayout()
        inner.setContentsMargins(22, 14, 22, 16)
        inner.setSpacing(14)
        outer.addLayout(inner)
        self._inner = inner

        self._body = QLabel(self.DESCRIPTION, self)
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.TextFormat.PlainText)
        inner.addWidget(self._body)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        inner.addWidget(sep)

        # Subclasses populate this area with their input rows. Tall dialogs opt
        # into SCROLLABLE_CONTENT: the input rows go inside a fade-edged scroll
        # area (log + buttons stay pinned below), so the window fits small
        # screens without hiding Run/Close.
        self._content = QVBoxLayout()
        self._content.setSpacing(10)
        if self.SCROLLABLE_CONTENT:
            cw = QWidget()
            cw.setLayout(self._content)
            self._scroll = FadeScrollArea(self, surface="dialog")
            self._scroll.set_appearance(resolve_mode(settings.get("appearance", "auto")))
            self._scroll.setWidgetResizable(True)
            self._scroll.setWidget(cw)
            self._scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll.setMinimumHeight(200)
            inner.addWidget(self._scroll, 1)
        else:
            self._scroll = None
            inner.addLayout(self._content)

        # Busy indicator (opt-in via BUSY_BAR_IDLE_LABEL): an always-visible
        # spectrum bar above the log, animated only while a run is under way —
        # external tools can stay silent for a long time and the window looked
        # frozen (Knut). Mirrors the Build Profile tab's bar.
        self._busy_bar = None
        if self.BUSY_BAR_IDLE_LABEL is not None:
            self._busy_bar = SpectrumSegmentsBar(self)
            self._busy_bar.set_label(self.BUSY_BAR_IDLE_LABEL, "")
            self._busy_bar.set_value(0)
            inner.addWidget(self._busy_bar)
        self._busy_note = ""
        self._busy_started = 0.0
        self._busy_tick = QTimer(self)
        self._busy_tick.setInterval(1000)
        self._busy_tick.timeout.connect(self._update_busy_label)

        # Log / status area
        self._log = QPlainTextEdit(self)
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setFixedHeight(120)
        self._log.setPlaceholderText(tr("Status messages will appear here."))
        inner.addWidget(self._log)

        # Buttons
        bb = QDialogButtonBox(self)
        self._run_btn   = bb.addButton(self.RUN_LABEL, QDialogButtonBox.ButtonRole.AcceptRole)
        self._close_btn = bb.addButton(tr("Close"),        QDialogButtonBox.ButtonRole.RejectRole)
        self._run_btn.setDefault(True)
        self._run_btn.clicked.connect(self._on_run_clicked)
        self._close_btn.clicked.connect(self.reject)
        self._button_box = bb          # subclasses may add ActionRole buttons
        inner.addWidget(bb)

        # Highlight checkboxes, focused inputs and combos with the same neutral
        # indicator the Settings window uses, instead of the global tab-accent
        # cyan/blue. (The TI2 layout editor is a plain QDialog, not a subclass of
        # this base, so it deliberately keeps its own accent.)
        qss = neutral_controls_qss(_indicator_color(settings))
        if resolve_mode(settings.get("appearance", "auto")) == "dark":
            # Generic QPlainTextEdit (the status field, paste boxes) has no
            # explicit background rule, so it falls back to the dark panel
            # background and reads darker than the QLineEdit inputs beside it.
            # Match it to the input background. (Dark mode only — light mode reads
            # fine as-is.)
            qss += (
                f"QPlainTextEdit {{ background: {BG_INPUT}; color: {TEXT_MAIN};"
                f" border: 1px solid {BORDER}; border-radius: 3px;"
                f" padding: 4px 6px; }}"
            )
        self.setStyleSheet(qss)

        # Defer building the input rows + first refresh until the subclass __init__
        # has finished setting up its own attributes.
        # Subclasses must call self._build_inputs() once their fields are wired.

    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802
        """Open at the height the (now fully built) content needs, and lock a
        minimum height so the user can't drag the window short enough to make
        the layout overlap its widgets.

        Subclasses add their input rows after ``__init__``, so the dialog's
        natural sizeHint is only complete by first show. The layout's
        ``minimumSize`` is the floor below which widgets (the file list, the
        fixed-height log) can no longer shrink and start overlapping — pin the
        dialog's minimum height to it. Cap both at 90 % of the screen so a very
        long body can't push the dialog off-screen."""
        super().showEvent(event)
        if self._sized_once:
            return
        self._sized_once = True
        layout = self.layout()

        # Word-wrapped QLabels report a tiny minimumSize height (they can wrap
        # to one word), so the layout's own minimumSize underestimates the
        # space they actually need at the dialog's real width — which is what
        # let the window shrink until widgets overlapped. Pin each wrapping
        # label's height to its true heightForWidth at the content width so the
        # floor we read back below is accurate.
        target_w = max(self.MIN_WIDTH, layout.sizeHint().width())
        # The body label is inset by the inner layout's side margins (the outer
        # layout now spans full width so the spectrum stripe can bleed to edge).
        margins = self._inner.contentsMargins()
        avail = target_w - margins.left() - margins.right()
        self._body.setMinimumHeight(max(0, self._body.heightForWidth(avail)))

        # Recompute the layout's minimum *after* the body's height is pinned, or
        # minimumSize() still reflects the un-wrapped (one-line) body height and
        # the floor comes out too low.
        layout.activate()
        hint  = layout.sizeHint()
        floor = layout.minimumSize()
        screen = self.screen() or QGuiApplication.primaryScreen()
        cap_h = (int(screen.availableGeometry().height() * 0.9)
                 if screen is not None else hint.height())
        # The minimum is the layout's floor (where every widget is at its own
        # minimum) — never below it, or the user could drag the window short
        # enough for rows to overlap. Only the *opening* size is capped to the
        # screen; the floor itself isn't, so it stays overlap-free.
        self.setMinimumHeight(floor.height())
        self.resize(target_w, max(floor.height(), min(hint.height(), cap_h)))

    # ------------------------------------------------------------------
    def _refit_height(self) -> None:
        """Re-fit the dialog height after dynamically showing/hiding rows.

        Subclasses that reveal optional content (e.g. an expandable options
        section) must call this so the dialog grows to fit instead of squashing
        the newly-shown widgets into the leftover space. No-op until the initial
        ``showEvent`` sizing has run; capped at 90 % of the screen height."""
        if not self._sized_once:
            return
        layout = self.layout()
        layout.activate()
        hint = layout.sizeHint()
        floor = layout.minimumSize()
        screen = self.screen() or QGuiApplication.primaryScreen()
        cap_h = (int(screen.availableGeometry().height() * 0.9)
                 if screen is not None else hint.height())
        self.setMinimumHeight(floor.height())  # never below the no-overlap floor
        self.resize(self.width(), max(floor.height(), min(hint.height(), cap_h)))

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------
    def _build_inputs(self) -> None:
        """Subclasses populate ``self._content`` with their input rows."""
        raise NotImplementedError

    def _can_run(self) -> bool:
        """Whether the Run button should be enabled."""
        return False

    def _execute(self) -> None:
        """Perform the work. Must call ``self._finish(success)`` when done."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        self._run_btn.setEnabled(self._can_run())

    def _on_run_clicked(self) -> None:
        if not self._can_run():
            return
        self._set_busy(True)
        try:
            self._execute()
        except Exception as exc:
            log.exception("Tool '%s' failed", self.TOOL_KEY)
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)

    def _set_busy(self, busy: bool) -> None:
        self._run_btn.setEnabled(not busy and self._can_run())
        self._close_btn.setEnabled(not busy)
        if self._busy_bar is None:
            return
        if busy:
            import time
            self._busy_started = time.monotonic()
            self._busy_bar.reset()
            self._update_busy_label()
            self._busy_bar.start()
            self._busy_tick.start()
            self.setCursor(Qt.CursorShape.BusyCursor)
        else:
            self._busy_tick.stop()
            self._busy_bar.stop()
            self._busy_note = ""
            self._busy_bar.set_value(0)
            self._busy_bar.set_label(self.BUSY_BAR_IDLE_LABEL, "")
            self.unsetCursor()

    def _set_busy_note(self, note: str, fraction: float | None = None) -> None:
        """Name the running step (and optionally its 0..1 position in the whole
        run) on the busy bar — e.g. "Step 2 of 6 — Reading page 2…"."""
        self._busy_note = note
        if self._busy_bar is None:
            return
        if fraction is not None:
            self._busy_bar.set_value(fraction)
        self._update_busy_label()

    def _update_busy_label(self) -> None:
        import time
        secs = int(time.monotonic() - self._busy_started)
        self._busy_bar.set_label(
            self._busy_note or tr("Working…"),
            tr("{n} s — still working").format(n=secs) if secs >= 3 else "")

    def _finish(self, success: bool) -> None:
        self._set_busy(False)
        if success:
            self._log.appendPlainText("[DONE]")

    # ------------------------------------------------------------------
    # Picker helpers
    # ------------------------------------------------------------------
    def _pick_input_file(self, caption: str, name_filter: str,
                         start_dir: "Path | None" = None) -> Path | None:
        # An explicit start_dir (e.g. the Verify-a-Profile cascade, #130) wins
        # over the tool's remembered last-used folder.
        sd = str(start_dir) if start_dir is not None \
            else str(_initial_dir(self._settings, self.TOOL_KEY))
        path = open_file_dialog(self, caption, name_filter, start_dir=sd)
        if not path:
            return None
        p = Path(path)
        _remember_dir(self._settings, self.TOOL_KEY, p.parent)
        return p

    def _pick_input_files(self, caption: str, name_filter: str) -> list[Path]:
        paths = open_files_dialog(
            self, caption, name_filter,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
        )
        if not paths:
            return []
        result = [Path(p) for p in paths]
        _remember_dir(self._settings, self.TOOL_KEY, result[0].parent)
        return result

    def _pick_output_dir(self, caption: str) -> Path | None:
        path = open_dir_dialog(
            self, caption,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
        )
        if not path:
            return None
        p = Path(path)
        _remember_dir(self._settings, self.TOOL_KEY, p)
        return p


# ---------------------------------------------------------------------------
# Reusable output-row widget
# ---------------------------------------------------------------------------

class _OutputRow(QWidget):
    """Folder picker + filename field, used as the destination of every tool.

    The filename is shown without its extension; the dialog appends the correct
    extension(s) when it builds the actual output paths.
    """

    def __init__(
        self,
        parent: QWidget,
        ext_hint: str,
        on_change: Callable[[], None],
        initial_dir: Path,
        initial_name: str = "",
        browse_color: "str | None" = None,
    ) -> None:
        super().__init__(parent)
        self._on_change = on_change

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._dir_edit = QLineEdit(str(initial_dir), self)
        self._dir_edit.setPlaceholderText(tr("Destination folder"))
        self._dir_edit.textChanged.connect(lambda _t: self._on_change())
        row.addWidget(self._dir_edit, 3)

        if browse_color is not None:
            # Icon-only folder button tinted to the dialog's accent (matches the
            # Soft-proof dialog's browse buttons), instead of a text "Browse…".
            browse = make_browse_button(
                self, tr("Choose destination folder"), color=browse_color)
        else:
            browse = QPushButton(tr("Browse…"), self)
        browse.clicked.connect(self._browse)
        self._browse_btn = browse
        row.addWidget(browse)

        self._name_edit = QLineEdit(initial_name, self)
        self._name_edit.setPlaceholderText(tr("Filename"))
        self._name_edit.textChanged.connect(lambda _t: self._on_change())
        row.addWidget(self._name_edit, 2)

        ext_lbl = QLabel(ext_hint, self)
        ext_lbl.setStyleSheet("color: #888;")
        row.addWidget(ext_lbl)

    def _browse(self) -> None:
        start = self._dir_edit.text() or str(Path.home())
        path = open_dir_dialog(self, tr("Choose destination folder"), start_dir=start)
        if path:
            self._dir_edit.setText(path)

    @property
    def directory(self) -> Path | None:
        text = self._dir_edit.text().strip()
        return Path(text) if text else None

    @property
    def name(self) -> str:
        return self._name_edit.text().strip()

    def is_complete(self) -> bool:
        d = self.directory
        return bool(self.name) and d is not None


# ---------------------------------------------------------------------------
# Average measurements
# ---------------------------------------------------------------------------

class AverageMeasurementsDialog(_ToolDialogBase):
    TOOL_KEY    = "average"
    TITLE       = tr("Average measurements")
    EYEBROW     = tr("MEASUREMENTS · AVERAGE")
    ACCENT      = SPEC_GREEN
    RUN_LABEL   = tr("Average")
    HELP = (
        tr("Measured the same chart a few times? This tool blends those readings "
        "into one cleaner result.\n\n"
        "Every measurement has a little random noise in it. If you read the same "
        "chart two or three times and combine the results, those random wobbles "
        "tend to cancel out, so each patch ends up with a steadier, more "
        "trustworthy colour — and one unlucky bad sweep matters far less.\n\n"
        "Here's how:\n\n"
        "1. Add two or more measurement files (.ti3), each one a separate reading "
        "of the very same printed chart.\n"
        "2. Choose how to combine them. \"Mean\" simply averages all the readings. "
        "\"Median\" instead takes the middle reading and ignores the odd one out, "
        "which is handy if one sweep went wrong — it just needs at least three "
        "files to do anything different from Mean.\n"
        "3. Pick where to save the result and what to call it.\n"
        "4. Click Average.\n\n"
        "You'll get a single measurement file that you can take straight to the "
        "Build Profile tab.\n\n"
        "Just one thing to watch: every file you add has to be the same chart "
        "(same patches, same instrument) — otherwise there's nothing matching to "
        "average together."))
    DESCRIPTION = (
        tr("Combine two or more readings of the same printed chart into a single "
        "averaged measurement. Reading the chart several times and averaging "
        "the results reduces instrument noise — every patch's colour value "
        "becomes the mean across the reads, so a stray bad sweep has less "
        "influence on the final profile.\n\n"
        "Method: 'mean' averages every value; 'median' picks the middle value "
        "and ignores the extremes, which is more robust to a single bad "
        "reading. Median needs at least three input files to behave "
        "differently from mean — with only two reads the two methods are "
        "mathematically identical, so the choice is locked to mean.\n\n"
        "Requirements: every input must be a .ti3 measurement of the SAME chart "
        "(identical patch list, made with the same instrument). The averaged "
        ".ti3 can then be loaded into Build Profile.")
    )

    def __init__(self, runner: "ArgyllRunner", settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._runner = runner
        self._avg_runner = AverageRunner(runner)
        self._inputs: list[Path] = []
        self._build_inputs()
        self._refresh()

    def _build_inputs(self) -> None:
        info = QLabel(tr("Measurement files to average (.ti3) — pick at least two:"), self)
        self._content.addWidget(info)

        self._list = QListWidget(self)
        self._list.setMinimumHeight(110)
        self._content.addWidget(self._list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton(tr("Add…"), self)
        add_btn.clicked.connect(self._add_files)
        btn_row.addWidget(add_btn)
        rem_btn = QPushButton(tr("Remove selected"), self)
        rem_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(rem_btn)
        btn_row.addStretch(1)
        self._content.addLayout(btn_row)

        # Method selector — median only meaningful for 3+ inputs.
        method_row = QHBoxLayout()
        method_row.addWidget(QLabel(tr("Method:"), self))
        self._mean_btn   = QRadioButton(tr("Mean (average)"), self)
        self._median_btn = QRadioButton(tr("Median"),        self)
        self._mean_btn.setChecked(True)
        self._method_group = QButtonGroup(self)
        self._method_group.addButton(self._mean_btn)
        self._method_group.addButton(self._median_btn)
        method_row.addWidget(self._mean_btn)
        method_row.addWidget(self._median_btn)
        self._median_hint = QLabel(tr("(needs 3+ files)"), self)
        self._median_hint.setStyleSheet("color: #888;")
        method_row.addWidget(self._median_hint)
        method_row.addStretch(1)
        self._content.addLayout(method_row)

        self._content.addWidget(QLabel(tr("Save the averaged measurement as:"), self))
        self._output = _OutputRow(
            self,
            ext_hint=".ti3",
            on_change=self._refresh,
            initial_dir=_initial_dir(self._settings, self.TOOL_KEY),
            initial_name="averaged",
        )
        self._content.addWidget(self._output)
        self._update_method_state()

    def _add_files(self) -> None:
        files = self._pick_input_files(
            tr("Add measurement files"),
            tr("Measurement files (*.ti3);;All files (*)"),
        )
        for p in files:
            if p not in self._inputs:
                self._inputs.append(p)
                self._list.addItem(str(p))
        if files and not self._output.name:
            # Borrow the first input's stem as a starting point.
            self._output._name_edit.setText(f"{files[0].stem}-averaged")
        self._update_method_state()
        self._refresh()

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            row = self._list.row(item)
            self._list.takeItem(row)
            del self._inputs[row]
        self._update_method_state()
        self._refresh()

    def _update_method_state(self) -> None:
        """Median needs 3+ inputs (with 2, Argyll's `average` falls back to mean
        anyway). Lock the radio to mean below the threshold."""
        can_median = len(self._inputs) >= 3
        self._median_btn.setEnabled(can_median)
        self._median_hint.setVisible(not can_median)
        if not can_median and self._median_btn.isChecked():
            self._mean_btn.setChecked(True)

    def _can_run(self) -> bool:
        return len(self._inputs) >= 2 and self._output.is_complete()

    def _execute(self) -> None:
        if self._runner.is_running:
            self._log.appendPlainText("[BUSY] Another operation is running — please wait.")
            self._finish(False)
            return

        out_dir = self._output.directory
        assert out_dir is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{self._output.name}.ti3"

        if out.exists():
            choice = confirm(
                self,
                tr("Overwrite existing file?"),
                tr("'{name}' already exists in:\n  {folder}\n\nOverwrite it?"
                   ).format(name=out.name, folder=out.parent),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self._finish(False)
                return

        method = "median" if self._median_btn.isChecked() else "mean"
        self._log.clear()
        self._log.appendPlainText(
            f"Averaging {len(self._inputs)} measurement files ({method}) → {out.name}"
        )

        params = AverageParams(inputs=list(self._inputs), output=out, method=method)

        def _on_line(line: str) -> None:
            self._log.appendPlainText(line.rstrip())
            self._log.ensureCursorVisible()

        def _on_finish(result: Path | None) -> None:
            if result is not None:
                self._log.appendPlainText(f"[OK] Wrote {result}")
                _remember_dir(self._settings, self.TOOL_KEY, result.parent)
                self._finish(True)
            else:
                fail = self._avg_runner.primary_failure()
                if fail is not None:
                    self._log.appendPlainText(f"[ERROR] {fail[1]}")
                else:
                    self._log.appendPlainText("[ERROR] Averaging failed — see messages above.")
                self._finish(False)

        self._avg_runner.run(params, _on_line, _on_finish)


# ---------------------------------------------------------------------------
# Merge measurements
# ---------------------------------------------------------------------------

class MergeMeasurementsDialog(_ToolDialogBase):
    TOOL_KEY    = "merge"
    TITLE       = tr("Merge measurements")
    EYEBROW     = tr("MEASUREMENTS · MERGE")
    ACCENT      = SPEC_GREEN
    RUN_LABEL   = tr("Merge")
    HELP = (
        tr("This tool joins several measurement files together into one bigger set "
        "of patches.\n\n"
        "It's easy to mix this up with averaging, so here's the difference in "
        "plain terms: averaging is for when you measured the SAME chart a few "
        "times and want to blend those reads into one. Merging is for when you "
        "have DIFFERENT sets of patches and want to pool them — for example an "
        "earlier \"pre-conditioning\" chart plus a fresh one. The more (well "
        "spread out) patches a profile is built from, the better it usually turns "
        "out.\n\n"
        "Here's how:\n\n"
        "1. Add the measurement files you'd like to combine.\n"
        "2. Pick where to save the result and what to call it.\n"
        "3. Click Merge.\n\n"
        "You'll get a single measurement file containing all of the patches from "
        "your inputs, ready to build a profile from."))
    DESCRIPTION = (
        tr("Combine the patches of several measurement files into one. Unlike "
        "averaging (which mixes repeated reads of the same chart), merging "
        "stacks the patches from DIFFERENT charts so the profiler has more data "
        "points to fit — useful for combining a pre-conditioning chart with a "
        "refinement chart, or for fusing complementary patch sets.\n\n"
        "Requirements: every file must use the same colour space and the same "
        "data layout (e.g. all spectral, all made with comparable instruments). "
        "Header information is taken from the primary file; the additional "
        "files contribute only their patches.")
    )

    def __init__(self, settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._primary: Path | None    = None
        self._additional: list[Path]  = []
        self._build_inputs()
        self._refresh()

    def _build_inputs(self) -> None:
        self._primary_lbl = QLabel(tr("Primary measurement (.ti3) — its header is kept:"), self)
        self._content.addWidget(self._primary_lbl)
        row = QHBoxLayout()
        self._primary_field = QLineEdit(self)
        self._primary_field.setReadOnly(True)
        self._primary_field.setPlaceholderText(tr("No file selected"))
        row.addWidget(self._primary_field, 1)
        primary_btn = QPushButton(tr("Browse…"), self)
        primary_btn.clicked.connect(self._pick_primary)
        row.addWidget(primary_btn)
        self._content.addLayout(row)

        self._additional_lbl = QLabel(
            tr("Additional measurements (.ti3) — their patches are appended:"), self
        )
        self._content.addWidget(self._additional_lbl)

        self._list = QListWidget(self)
        self._list.setMinimumHeight(90)
        self._content.addWidget(self._list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton(tr("Add…"), self)
        add_btn.clicked.connect(self._add_additional)
        btn_row.addWidget(add_btn)
        rem_btn = QPushButton(tr("Remove selected"), self)
        rem_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(rem_btn)
        btn_row.addStretch(1)
        self._content.addLayout(btn_row)

        self._content.addWidget(QLabel(tr("Save the merged measurement as:"), self))
        self._output = _OutputRow(
            self,
            ext_hint=".ti3",
            on_change=self._refresh,
            initial_dir=_initial_dir(self._settings, self.TOOL_KEY),
            initial_name="merged",
        )
        self._content.addWidget(self._output)

    def _pick_primary(self) -> None:
        p = self._pick_input_file(tr("Choose primary measurement"), tr("Measurement files (*.ti3);;All files (*)"))
        if p:
            self._primary = p
            self._primary_field.setText(str(p))
            if not self._output.name or self._output.name == "merged":
                self._output._name_edit.setText(f"{p.stem}-merged")
            self._refresh()

    def _add_additional(self) -> None:
        files = self._pick_input_files(
            tr("Add measurements to merge in"), tr("Measurement files (*.ti3);;All files (*)")
        )
        for p in files:
            if p not in self._additional and p != self._primary:
                self._additional.append(p)
                self._list.addItem(str(p))
        self._refresh()

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            row = self._list.row(item)
            self._list.takeItem(row)
            del self._additional[row]
        self._refresh()

    def _can_run(self) -> bool:
        return (self._primary is not None
                and len(self._additional) >= 1
                and self._primary not in self._additional
                and self._output.is_complete())

    def _execute(self) -> None:
        out_dir = self._output.directory
        assert out_dir is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{self._output.name}.ti3"

        if out.exists():
            choice = confirm(
                self,
                tr("Overwrite existing file?"),
                tr("'{name}' already exists in:\n  {folder}\n\nOverwrite it?"
                   ).format(name=out.name, folder=out.parent),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self._finish(False)
                return

        inputs = [self._primary, *self._additional]
        self._log.clear()
        self._log.appendPlainText(
            f"Merging {len(inputs)} measurement files "
            f"(primary '{self._primary.name}') → {out.name}"
        )

        bin_dir = Path(self._settings.get("argyll_bin_path", "/Applications/Argyll/bin"))
        try:
            total = merge_measurements(inputs, out, bin_dir=bin_dir)
        except Ti3MergeError as exc:
            self._log.appendPlainText(f"[ERROR] {exc.message}")
            self._finish(False)
            return

        self._log.appendPlainText(f"[OK] Wrote {out} ({total} patches)")
        _remember_dir(self._settings, self.TOOL_KEY, out.parent)
        self._finish(True)


# ---------------------------------------------------------------------------
# TI1 → i1Profiler
# ---------------------------------------------------------------------------

class Ti1ToI1ProfilerDialog(_ToolDialogBase):
    TOOL_KEY    = "ti1_to_i1p"
    TITLE       = tr("Convert TI1 → i1Profiler")
    EYEBROW     = tr("FORMAT CONVERSION")
    RUN_LABEL   = tr("Convert")
    HELP = (
        tr("Want to measure a ChromIQ chart using X-Rite's i1Profiler software (for "
        "example to drive an i1iSis scanner)? This tool gets your chart ready for "
        "it.\n\n"
        "ChromIQ describes charts in Argyll's own \"TI1\" format, which i1Profiler "
        "doesn't understand. This converts that description into files i1Profiler "
        "can open, so the very same chart can be measured over there.\n\n"
        "Here's how:\n\n"
        "1. Pick the ChromIQ chart definition (.ti1) you want to measure.\n"
        "2. Choose what to write out (the patch set, and/or a ready-made "
        "i1Profiler workflow file).\n"
        "3. Pick where to save it and what to call it.\n"
        "4. Click Convert.\n\n"
        "Then open the result in i1Profiler, print and measure as usual. When "
        "you're done, come back and use the \"i1Profiler → TI3\" tool to bring "
        "those measurements into ChromIQ.\n\n"
        "Good to know: this works with RGB charts."))
    DESCRIPTION = (
        tr("Convert an Argyll TI1 chart definition into the formats that X-Rite "
        "i1Profiler reads. Use this when you want an i1iSis (or another "
        "i1Profiler-driven instrument) to measure a chart that Argyll's targen "
        "produced.\n\n"
        "Patch set (always written):\n"
        "  • RGB    — writes both .txt (CGATS) and .pxf (CxF3)\n"
        "  • CMYK   — writes both .txt and .pxf\n"
        "  • CMYK+N — writes .pxf only (i1Profiler accepts extended-gamut sets "
        "only as CxF3)\n\n"
        "Optionally also write a workflow file (.pwxf) — RGB only — that opens "
        "in i1Profiler with the instrument, paper and patch layout already set "
        "up, so you don't have to configure them by hand.")
    )

    def __init__(self, settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._ti1: Path | None = None
        self._ti1_kind: str | None = None   # "RGB" | "CMYK" | "CMYKPLUSN"
        # This dialog uses its masthead magenta as the live accent for checkboxes
        # and focused inputs (not the neutral indicator the other tool dialogs
        # keep). Appended after the base QSS so the magenta rules win.
        self.setStyleSheet(self.styleSheet() + neutral_controls_qss(self.ACCENT))
        self._build_inputs()
        self._refresh()

    def _build_inputs(self) -> None:
        self._content.addWidget(QLabel(tr("Argyll chart definition (.ti1):"), self))
        row = QHBoxLayout()
        self._ti1_field = QLineEdit(self)
        self._ti1_field.setReadOnly(True)
        self._ti1_field.setPlaceholderText(tr("No file selected"))
        row.addWidget(self._ti1_field, 1)
        btn = make_browse_button(
            self, tr("Browse for the chart definition"), color=self.ACCENT)
        btn.clicked.connect(self._pick_ti1)
        row.addWidget(btn)
        self._content.addLayout(row)

        self._content.addWidget(QLabel(tr("Save the i1Profiler files as:"), self))
        self._output = _OutputRow(
            self,
            ext_hint=".pxf (+ .txt / .pwxf)",
            on_change=self._refresh,
            initial_dir=_initial_dir(self._settings, self.TOOL_KEY),
            initial_name="i1profiler",
            browse_color=self.ACCENT,
        )
        self._content.addWidget(self._output)

        shuf_row = QHBoxLayout()
        self._shuffle_check = QCheckBox(
            tr("Also save a shuffled copy for i1Profiler"), self)
        self._shuffle_check.setChecked(
            bool(self._settings.get("export_shuffled_pxf", False)))
        self._shuffle_check.toggled.connect(
            lambda on: self._settings.set("export_shuffled_pxf", bool(on)))
        shuf_row.addWidget(self._shuffle_check)
        shuf_row.addStretch(1)
        shuf_row.addWidget(
            TooltipButton(
                tr("Keep your chart layout in i1Profiler"),
                tr("When you load a patch set into i1Profiler, it arranges the "
                "patches on the page in the order they appear in the file. A "
                "chart straight out of ChromIQ lists its colours in a tidy, "
                "systematic order — which can put very similar colours right "
                "next to each other on the printed strip. That is a little "
                "harder to read by eye and slightly less ideal for the "
                "instrument.\n\n"
                "Tick this box and ChromIQ saves a second copy whose patches "
                "are shuffled into a mixed-up order, with “-shuffled” "
                "added to the file name. Hand that shuffled copy to i1Profiler "
                "and it keeps exactly this mixed order instead of lining the "
                "colours back up — so similar colours end up spread apart "
                "across the chart.\n\n"
                "Both copies are always written, so you can pick whichever you "
                "prefer. If you are unsure, the shuffled copy is the safer one "
                "to print and measure."),
                self, min_width=460, color=self.ACCENT),
            0, Qt.AlignmentFlag.AlignVCenter)
        self._content.addLayout(shuf_row)

        self._build_workflow_section()

    def _build_workflow_section(self) -> None:
        wf_row = QHBoxLayout()
        self._wf_check = QCheckBox(
            tr("Also write an i1Profiler workflow file (.pwxf)"), self
        )
        self._wf_check.toggled.connect(self._update_workflow_state)
        wf_row.addWidget(self._wf_check)
        wf_row.addStretch(1)
        wf_row.addWidget(
            TooltipButton(
                tr("What an i1Profiler workflow file does"),
                tr("A workflow file (.pwxf) is a ready-made i1Profiler project, "
                "not just the list of colour patches. On top of the patches it "
                "also remembers which measuring instrument you use, the paper "
                "size, and how the patches should be laid out on the page.\n\n"
                "When you open a .pwxf in i1Profiler, all of that is already "
                "filled in — you can go straight to printing and measuring the "
                "chart, without clicking through i1Profiler's setup screens or "
                "picking those settings by hand every time.\n\n"
                "This is only offered for RGB charts. Leave it off if you just "
                "want the plain patch set (.pxf / .txt) and prefer to choose "
                "the instrument and layout inside i1Profiler yourself."),
                self, min_width=460, color=self.ACCENT),
            0, Qt.AlignmentFlag.AlignVCenter)
        self._content.addLayout(wf_row)

        self._wf_note = QLabel("", self)
        self._wf_note.setWordWrap(True)
        self._wf_note.setStyleSheet("color: #888;")
        self._content.addWidget(self._wf_note)

        self._wf_box = QWidget(self)
        grid = QGridLayout(self._wf_box)
        grid.setContentsMargins(18, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel(tr("Instrument:"), self._wf_box), 0, 0)
        self._wf_instrument = NoScrollComboBox(self._wf_box)
        self._wf_instrument.addItems(list(_PWXF_DEVICES))
        grid.addWidget(self._wf_instrument, 0, 1)

        grid.addWidget(QLabel(tr("Scan mode:"), self._wf_box), 1, 0)
        self._wf_scan = NoScrollComboBox(self._wf_box)
        self._wf_scan.addItems([label for label, _ in _PWXF_SCAN_MODES])
        grid.addWidget(self._wf_scan, 1, 1)

        grid.addWidget(QLabel(tr("Paper:"), self._wf_box), 2, 0)
        self._wf_paper = NoScrollComboBox(self._wf_box)
        self._wf_paper.addItems(list(_PWXF_PAPERS))
        grid.addWidget(self._wf_paper, 2, 1)

        # Optional patch-size override. Off = i1Profiler picks its own sensible
        # size. On = write the exact patch size, encoded as the per-device slider
        # percent (see _PWXF_DEVICES). i1iSis adds a "Lead-in" (Vorlauf) field.
        self._wf_size = QCheckBox(tr("Set patch size (otherwise i1Profiler decides)"),
                                  self._wf_box)
        self._wf_size.toggled.connect(self._update_size_state)
        grid.addWidget(self._wf_size, 3, 0, 1, 2)

        self._wf_size_row = QWidget(self._wf_box)
        srow = QHBoxLayout(self._wf_size_row)
        srow.setContentsMargins(18, 0, 0, 0)
        srow.setSpacing(6)
        srow.addWidget(QLabel(tr("W"), self._wf_size_row))
        self._wf_w = NoScrollSpinBox(self._wf_size_row)
        self._wf_w.setSuffix(" mm")
        srow.addWidget(self._wf_w)
        srow.addSpacing(6)
        srow.addWidget(QLabel(tr("H"), self._wf_size_row))
        self._wf_h = NoScrollSpinBox(self._wf_size_row)
        self._wf_h.setSuffix(" mm")
        srow.addWidget(self._wf_h)
        srow.addStretch(1)
        grid.addWidget(self._wf_size_row, 4, 0, 1, 2)

        grid.setColumnStretch(1, 1)
        self._content.addWidget(self._wf_box)
        # Connect + initialise only after every widget the handler touches exists.
        self._wf_instrument.currentTextChanged.connect(self._on_instrument_changed)
        self._wf_instrument.setCurrentText("i1Pro 3")
        self._on_instrument_changed()
        self._wf_size_row.setVisible(False)
        self._update_workflow_state()

    def _on_instrument_changed(self) -> None:
        """Apply the selected device's slider ranges and forced measurement mode."""
        wlo, whi, hlo, hhi, mode, _vorlauf = _PWXF_DEVICES.get(
            self._wf_instrument.currentText(), (6, 25, 6, 20, None, False))
        self._wf_w.setRange(wlo, whi)
        self._wf_h.setRange(hlo, hhi)
        dw, dh = _device_default_size(wlo, whi, hlo, hhi)
        self._wf_w.setValue(dw)
        self._wf_h.setValue(dh)
        # PLUS/M3/i1iSis carry a fixed measurement mode — no Single/Dual choice.
        self._wf_scan.setEnabled(mode is None)

    def _update_size_state(self) -> None:
        self._wf_size_row.setVisible(self._wf_size.isChecked())
        self._refit_height()

    def _update_workflow_state(self) -> None:
        is_rgb = self._ti1_kind == "RGB"
        no_file = self._ti1 is None
        self._wf_check.setEnabled(is_rgb or no_file)
        if not is_rgb and not no_file:
            self._wf_check.setChecked(False)
            self._wf_note.setText(
                tr("Workflow files are RGB-only — this chart is "
                   "{kind}, so only the patch set will be written."
                   ).format(kind=self._ti1_kind)
            )
            self._wf_note.setVisible(True)
        else:
            self._wf_note.setVisible(False)
        self._wf_box.setVisible(self._wf_check.isChecked())
        self._refit_height()

    def _pick_ti1(self) -> None:
        p = self._pick_input_file(
            tr("Choose chart definition"), tr("Argyll chart files (*.ti1);;All files (*)")
        )
        if p:
            self._ti1 = p
            self._ti1_field.setText(str(p))
            try:
                self._ti1_kind = parse_ti1(p).kind
            except ValueError:
                self._ti1_kind = None
            if not self._output.name or self._output.name == "i1profiler":
                self._output._name_edit.setText(f"{p.stem}-i1profiler")
            self._update_workflow_state()
            self._refresh()

    def _can_run(self) -> bool:
        return self._ti1 is not None and self._output.is_complete()

    def _want_workflow(self) -> bool:
        return self._ti1_kind == "RGB" and self._wf_check.isChecked()

    def _execute(self) -> None:
        out_dir = self._output.directory
        assert out_dir is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        base = self._output.name
        want_wf = self._want_workflow()

        want_shuffle = self._shuffle_check.isChecked()

        pxf = out_dir / f"{base}.pxf"
        txt = out_dir / f"{base}.txt"
        pwxf = out_dir / f"{base}.pwxf"
        candidates = [pxf, txt] + ([pwxf] if want_wf else [])
        if want_shuffle:
            candidates += [out_dir / f"{base}-shuffled.pxf",
                           out_dir / f"{base}-shuffled.txt"]
        existing = [p for p in candidates if p.exists()]
        if existing:
            names = ", ".join(p.name for p in existing)
            choice = confirm(
                self,
                tr("Overwrite existing file(s)?"),
                tr("These files already exist in:\n  {folder}\n\n  {names}\n\nOverwrite?"
                   ).format(folder=out_dir, names=names),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self._finish(False)
                return

        self._log.clear()
        self._log.appendPlainText(f"Converting {self._ti1.name} → {base}.pxf / {base}.txt")

        try:
            txt_out, pxf_out = export_from_ti1(
                self._ti1, out_dir, base_name=base, also_shuffled=want_shuffle)
        except ValueError as exc:
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)
            return

        self._log.appendPlainText(f"[OK] Wrote {pxf_out}")
        if txt_out is not None:
            self._log.appendPlainText(f"[OK] Wrote {txt_out}")
        if want_shuffle:
            for suffix in (".pxf", ".txt"):
                shuf = out_dir / f"{base}-shuffled{suffix}"
                if shuf.exists():
                    self._log.appendPlainText(f"[OK] Wrote {shuf} (shuffled)")
        if txt_out is None:
            self._log.appendPlainText(
                "Note: CMYK+N targets are only written as .pxf — i1Profiler does "
                "not accept extended-gamut patch sets in CGATS .txt form."
            )

        if want_wf:
            try:
                self._write_workflow(pwxf, base)
            except ValueError as exc:
                self._log.appendPlainText(f"[ERROR] workflow file: {exc}")
                self._finish(False)
                return
            self._log.appendPlainText(f"[OK] Wrote {pwxf}")

        _remember_dir(self._settings, self.TOOL_KEY, out_dir)
        self._finish(True)

    def _write_workflow(self, out_path: Path, base: str) -> None:
        target = parse_ti1(self._ti1)
        fmt, w, h, orient = _PWXF_PAPERS[self._wf_paper.currentText()]
        device = self._wf_instrument.currentText()
        wlo, whi, hlo, hhi, forced_mode, vorlauf = _PWXF_DEVICES.get(
            device, (6, 25, 6, 20, None, False))
        # PLUS/M3/i1iSis pin the measurement mode; others use the Single/Dual chooser.
        mode = forced_mode if forced_mode is not None else _PWXF_SCAN_MODES[
            self._wf_scan.currentIndex()][1]
        opt = WorkflowOptions(
            device=device,
            measurement_mode=mode,
            paper_format=fmt,
            paper_orientation=orient,
            page_width_mm=w,
            page_height_mm=h,
            title=base,
        )
        # i1Profiler reads the patch size from the per-device slider *percent*,
        # not the mm value — and percent 0 is the slider MINIMUM (6 mm on an
        # i1Pro 3, below its 7 mm scan minimum), NOT "let i1Profiler decide". A
        # .pwxf with UsePatchSettingDefaults="True" + percent 0 was verified to
        # render at that minimum, so we never write that combination: every
        # genuine X-Rite workflow file sets UsePatchSettingDefaults="False" with
        # a real percent. With the box unchecked we substitute the device's
        # warning-free default size (8×7 for i1Pro/i1iO); when checked we encode
        # the requested size. i1Profiler still computes the column/row grid itself.
        if self._wf_size.isChecked():
            pw, ph = float(self._wf_w.value()), float(self._wf_h.value())
        else:
            pw, ph = (float(v) for v in _device_default_size(wlo, whi, hlo, hhi))
        opt.use_patch_defaults = False
        opt.patch_w_mm, opt.patch_h_mm = pw, ph
        opt.patch_w_percent = _patch_percent(pw, wlo, whi)
        opt.patch_h_percent = _patch_percent(ph, hlo, hhi)
        # i1iSis needs a valid HeaderEdgeSizePercent (the "Vorlauf" lead-in)
        # rather than the non-iSis -2147483648 sentinel. We write 0 (=32 mm):
        # i1Profiler does not persist the lead-in — it resets to that minimum
        # on load regardless of what any file (even its own) contains — so the
        # value is fixed, not user-controllable, and there is no UI for it.
        if vorlauf:
            opt.header_edge_percent = 0.0
        write_pwxf(target, out_path, base, opt)


# ---------------------------------------------------------------------------
# i1Profiler .txt → TI3
# ---------------------------------------------------------------------------

class I1ProfilerToTi3Dialog(_ToolDialogBase):
    TOOL_KEY    = "i1p_to_ti3"
    TITLE       = tr("Convert i1Profiler → TI3")
    EYEBROW     = tr("FORMAT CONVERSION")
    ACCENT      = SPEC_GREEN
    RUN_LABEL   = tr("Convert")
    HELP = (
        tr("Measured your chart in X-Rite's i1Profiler? This brings those readings "
        "back into ChromIQ so you can build a profile from them.\n\n"
        "This tool translates an i1Profiler measurement into the format ChromIQ "
        "uses everywhere else. It reads two kinds of file:\n"
        "  • i1Profiler's own saved measurement (.mxf) — no export step needed, "
        "just point at it.\n"
        "  • a measurement you exported from i1Profiler as text/CGATS (.txt), or "
        "an .cxf.\n\n"
        "Here's how:\n\n"
        "1. Pick the i1Profiler measurement (.mxf, .txt or .cxf).\n"
        "2. Pick where to save the result and what to call it. ChromIQ suggests "
        "the same folder as your i1Profiler file, so everything stays together.\n"
        "3. Click Convert.\n\n"
        "You'll get a ChromIQ measurement file (.ti3) you can take straight to the "
        "Build Profile tab — which neatly closes the loop after measuring in "
        "i1Profiler.\n\n"
        "It's also ready for the Measurement Report (Tools → “Measurement "
        "report”): just add the .ti3 there and you get the full colour-accuracy "
        "figures — no extra reference file needed.\n\n"
        "Instrument and date: ChromIQ reads the measuring instrument and the "
        "measurement date from the i1Profiler file and carries them into the .ti3, "
        "so the report shows the right instrument and plots each run on the date "
        "it was measured. If the file names no instrument, the report shows "
        "“i1Profiler (unspecified)”."))
    DESCRIPTION = (
        tr("Bring an i1Profiler measurement into ChromIQ as an Argyll .ti3 file. "
        "Use this when you measured a chart in i1Profiler — often because you have "
        "an i1iSis or i1iO that lays out and reads its own chart — and want to "
        "build the ICC profile (or check accuracy) in ChromIQ.\n\n"
        "Two kinds of file work:\n"
        "  • i1Profiler's own saved measurement (.mxf) — pick it directly, no "
        "export step; ChromIQ reads the readings, the measuring instrument and "
        "the measurement date straight from it.\n"
        "  • a measurement you exported from i1Profiler as text/CGATS (.txt), or "
        "an .cxf file.\n\n"
        "Either way you need REAL measured colour (spectral or Lab/XYZ) for every "
        "patch, not just a reference patch list. The resulting .ti3 loads into "
        "Build Profile and into the Measurement Report.")
    )

    def __init__(self, runner: "ArgyllRunner", settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._runner = runner
        self._txt: Path | None = None
        self._build_inputs()
        self._refresh()

    def _build_inputs(self) -> None:
        self._content.addWidget(QLabel(
            tr("i1Profiler measurement file (.txt, .mxf, .cxf):"), self))
        row = QHBoxLayout()
        self._txt_field = QLineEdit(self)
        self._txt_field.setReadOnly(True)
        self._txt_field.setPlaceholderText(tr("No file selected"))
        row.addWidget(self._txt_field, 1)
        btn = QPushButton(tr("Browse…"), self)
        btn.clicked.connect(self._pick_txt)
        row.addWidget(btn)
        self._content.addLayout(row)

        self._content.addWidget(QLabel(tr("Save the Argyll measurement as:"), self))
        self._output = _OutputRow(
            self,
            ext_hint=".ti3",
            on_change=self._refresh,
            initial_dir=_initial_dir(self._settings, self.TOOL_KEY),
            initial_name="",
        )
        self._content.addWidget(self._output)

    def _pick_txt(self) -> None:
        p = self._pick_input_file(
            tr("Choose i1Profiler measurement"),
            tr("i1Profiler measurements (*.txt *.mxf *.cxf);;All files (*)")
        )
        if p:
            self._txt = p
            self._txt_field.setText(str(p))
            # Auto-fill the output name from the input stem, and KEEP it in sync
            # when a different file is picked next — but never clobber a name the
            # user typed themselves (recognised because it no longer matches the
            # last stem we filled in). (Knut: picking a second file left the name
            # stuck on the first file's.)
            prev_auto = getattr(self, "_auto_name", "")
            if not self._output.name or self._output.name == prev_auto:
                self._output._name_edit.setText(p.stem)
                self._auto_name = p.stem
            # Default the destination to the i1Profiler file's own folder, so the
            # converted .ti3 lands beside the measurement — keeping i1Profiler
            # data together and away from ChromIQ profile folders (Knut).
            self._output._dir_edit.setText(str(p.parent))
            self._refresh()

    def _can_run(self) -> bool:
        return self._txt is not None and self._output.is_complete()

    def _execute(self) -> None:
        if self._runner.is_running:
            self._log.appendPlainText("[BUSY] Another operation is running — please wait.")
            self._finish(False)
            return

        out_dir = self._output.directory
        assert out_dir is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        base = self._output.name
        out = out_dir / f"{base}.ti3"

        if out.exists():
            choice = confirm(
                self,
                tr("Overwrite existing file?"),
                tr("'{name}' already exists in:\n  {folder}\n\nOverwrite it?"
                   ).format(name=out.name, folder=out.parent),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self._finish(False)
                return

        # i1Profiler's native CxF3 (.mxf / .cxf): a direct, synchronous parse —
        # txt2ti3 can't read CxF, and no export step is needed (Basti).
        from workflow.reference_convert import (is_cxf, cxf_measurement_to_ti3,
                                                ReferenceConvertError)
        if is_cxf(self._txt):
            self._log.clear()
            self._log.appendPlainText(f"Converting {self._txt.name} → {out.name}")
            try:
                cxf_measurement_to_ti3(self._txt, out)
            except ReferenceConvertError as exc:
                self._log.appendPlainText(f"[ERROR] {exc}")
                self._finish(False)
                return
            from workflow.ti3_analysis import parse_ti3
            kw = parse_ti3(out).keywords
            if kw.get("TARGET_INSTRUMENT"):
                self._log.appendPlainText(
                    tr("Instrument: {name}").format(name=kw["TARGET_INSTRUMENT"]))
            if kw.get("CHROMIQ_MEASURED"):
                self._log.appendPlainText(
                    tr("Measured: {date}").format(date=kw["CHROMIQ_MEASURED"]))
            self._log.appendPlainText(f"[OK] Wrote {out}")
            _remember_dir(self._settings, self.TOOL_KEY, out.parent)
            self._finish(True)
            return

        # txt2ti3 wants both files in the cwd and writes <base>.ti3 next to <base>.txt.
        # Copy the input alongside the desired base name so we don't pollute the
        # source folder and so txt2ti3's output ends up where the user asked.
        import shutil
        staged_txt = out_dir / f"{base}.txt"
        if staged_txt.resolve() != self._txt.resolve():
            shutil.copy2(self._txt, staged_txt)

        self._log.clear()
        self._log.appendPlainText(f"Converting {self._txt.name} → {out.name}")

        collected: list[str] = []

        def _on_line(line: str) -> None:
            collected.append(line)
            self._log.appendPlainText(line.rstrip())
            self._log.ensureCursorVisible()

        def _on_finish(code: int) -> None:
            ok = code == 0 and out.exists()
            if ok:
                # txt2ti3 doesn't carry the instrument across; read it from the
                # i1Profiler export's INSTRUMENTATION header and stamp it so the
                # measurement report can show it (falls back to a clear label
                # when the file names none) (Knut).
                try:
                    from workflow.reference_convert import finalize_converted_ti3
                    instr, date = finalize_converted_ti3(out, self._txt)
                    if instr:
                        self._log.appendPlainText(
                            tr("Instrument: {name}").format(name=instr))
                    if date:
                        self._log.appendPlainText(
                            tr("Measured: {date}").format(date=date))
                except Exception:
                    pass
                self._log.appendPlainText(f"[OK] Wrote {out}")
                _remember_dir(self._settings, self.TOOL_KEY, out.parent)
                self._finish(True)
            else:
                detail = next(
                    (l.strip() for l in collected if "error" in l.lower()),
                    "",
                )
                self._log.appendPlainText("[ERROR] txt2ti3 could not convert the file.")
                if detail:
                    self._log.appendPlainText(detail)
                self._finish(False)

        self._runner.run(
            "txt2ti3",
            ["-v", staged_txt.name, base],
            cwd=out_dir,
            on_line=_on_line,
            on_finish=_on_finish,
        )


# ---------------------------------------------------------------------------
# i1Profiler → TI1
# ---------------------------------------------------------------------------

class I1ProfilerToTi1Dialog(_ToolDialogBase):
    TOOL_KEY    = "i1p_to_ti1"
    TITLE       = tr("Convert i1Profiler → TI1")
    EYEBROW     = tr("FORMAT CONVERSION")
    RUN_LABEL   = tr("Convert")
    HELP = (
        tr("Have a chart from X-Rite's i1Profiler that you'd like to print and "
        "measure in ChromIQ? This brings it across.\n\n"
        "It takes i1Profiler's chart description and turns it into the format "
        "ChromIQ uses, so you can lay the chart out, print it, and measure it just "
        "like any other.\n\n"
        "Here's how:\n\n"
        "1. Pick your i1Profiler chart — a patch set (.pxf), a workflow file "
        "(.pwxf), or an exported list.\n"
        "2. Pick where to save the result and what to call it.\n"
        "3. Click Convert.\n\n"
        "You'll get a ChromIQ chart definition (.ti1) you can open in the chart "
        "layout editor, print, and then measure.\n\n"
        "Good to know: this works with RGB charts; ChromIQ reconstructs the patch "
        "colours so it can lay the chart out for printing."))
    DESCRIPTION = (
        tr("Convert an i1Profiler patch set (.pxf), a workflow file (.pwxf), or a "
        ".cgats table into an Argyll TI1 chart definition. Use this to bring a "
        "chart that only exists in i1Profiler — for example a TC9.18 target, or "
        "a workflow someone sent you — into the Argyll workflow, so you can lay "
        "it out with printtarg, print it, and read it with chartread.\n\n"
        "This is the reverse of 'Convert TI1 → i1Profiler'. The input only "
        "carries device RGB values, so ChromIQ reconstructs each patch's "
        "approximate colour (treating the values as sRGB) — printtarg needs "
        "that to space the patches for reliable strip reading.\n\n"
        "Supported colour space: RGB only. A .pwxf carries its layout/instrument "
        "settings too, but only the patch list is read; the patch order is "
        "preserved and printtarg re-lays-out the chart anyway.")
    )

    def __init__(self, settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._src: Path | None = None
        self._build_inputs()
        self._refresh()

    def _build_inputs(self) -> None:
        self._content.addWidget(QLabel(tr("i1Profiler patch set (.pxf / .pwxf / .cgats):"), self))
        row = QHBoxLayout()
        self._src_field = QLineEdit(self)
        self._src_field.setReadOnly(True)
        self._src_field.setPlaceholderText(tr("No file selected"))
        row.addWidget(self._src_field, 1)
        btn = QPushButton(tr("Browse…"), self)
        btn.clicked.connect(self._pick_src)
        row.addWidget(btn)
        self._content.addLayout(row)

        self._content.addWidget(QLabel(tr("Save the Argyll chart definition as:"), self))
        self._output = _OutputRow(
            self,
            ext_hint=".ti1",
            on_change=self._refresh,
            initial_dir=_initial_dir(self._settings, self.TOOL_KEY),
            initial_name="",
        )
        self._content.addWidget(self._output)

    def _pick_src(self) -> None:
        p = self._pick_input_file(
            tr("Choose i1Profiler patch set"),
            tr("i1Profiler patch sets (*.pxf *.pwxf *.cgats *.txt);;All files (*)"),
        )
        if p:
            self._src = p
            self._src_field.setText(str(p))
            if not self._output.name:
                self._output._name_edit.setText(p.stem)
            self._refresh()

    def _can_run(self) -> bool:
        return self._src is not None and self._output.is_complete()

    def _execute(self) -> None:
        out_dir = self._output.directory
        assert out_dir is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{self._output.name}.ti1"

        if out.exists():
            choice = confirm(
                self,
                tr("Overwrite existing file?"),
                tr("'{name}' already exists in:\n  {folder}\n\nOverwrite it?"
                   ).format(name=out.name, folder=out.parent),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self._finish(False)
                return

        self._log.clear()
        self._log.appendPlainText(f"Converting {self._src.name} → {out.name}")

        try:
            out_path, n = import_to_ti1(self._src, out)
        except ValueError as exc:
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)
            return

        self._log.appendPlainText(f"[OK] Wrote {out_path} ({n} patches)")
        _remember_dir(self._settings, self.TOOL_KEY, out_dir)
        self._finish(True)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class VerifyAgainstReferenceDialog(_ToolDialogBase):
    TOOL_KEY    = "verify"
    TITLE       = tr("Verify against reference")
    EYEBROW     = tr("QUALITY CHECK")
    ACCENT      = SPEC_VIOLET
    RUN_LABEL   = tr("Verify")
    HELP = (
        tr("This tool tells you how close your colours came out compared to where "
        "they were supposed to be — without building a profile first.\n\n"
        "The idea is simple: you give it what you actually measured, and what the "
        "colours were meant to be, and it tells you how far apart they are. That "
        "gap is measured as \"ΔE\" (delta-E) — think of it as a colour-difference "
        "score where smaller is better and 0 would be a perfect match.\n\n"
        "Here's how:\n\n"
        "1. Pick the chart you measured (your .ti3 measurement file).\n"
        "2. Give it the reference to compare against — either a reference "
        "measurement file, or a set of expected values you load or paste in.\n"
        "3. Click Verify.\n\n"
        "You'll see the ΔE for every single patch plus an overall average. If most "
        "patches are low and only a handful are high, those few usually point to a "
        "misread or a problem patch on the print.\n\n"
        "A tip if the numbers look alarmingly high: if your reference values were "
        "made for a different paper or finish (for example glossy values checked "
        "against a matte print), the deep shadows can't match — matte simply can't "
        "go as dark. ChromIQ tells you when an error is mostly *lightness* (a "
        "black-point limit you can't avoid) versus a real *colour* shift. You can "
        "also point it at your own profile (.icc) and it will skip the colours your "
        "paper physically can't reproduce, so they stop dominating the score.\n\n"
        "It's a quick way to sanity-check a profile, compare one paper or ink "
        "batch against another, or keep an eye on a printer drifting over time — "
        "all without building anything."))
    MIN_WIDTH   = 660
    DESCRIPTION = (
        tr("Compare a measured chart against a set of expected colour values and "
        "report the colour error (ΔE) per patch — without building a "
        "profile. Use this to check how closely a print matches known target "
        "values, e.g. a profile-evaluation target someone shared with you.\n\n"
        "Paste (or load) the expected values — one patch per line, in the same "
        "order as the chart — pick your measured .ti3, and optionally the "
        "chart's .ti1/.ti2 so the patch count is cross-checked. ChromIQ builds "
        "a reference file whose patch IDs line up with your measurement and "
        "runs Argyll's colverify.")
    )

    def __init__(self, runner: "ArgyllRunner", settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._runner    = runner
        self._cv        = ColverifyRunner(runner)
        self._measured: Path | None = None
        self._chart: Path | None = None
        self._profile: Path | None = None
        self._temp_dirs: list[Path] = []   # staging dirs for 3D-map runs, cleaned on close
        self._build_inputs()
        self._refresh()

    def _cleanup_temp(self) -> None:
        for d in self._temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        self._temp_dirs.clear()

    def done(self, result: int) -> None:  # noqa: D102 — covers both Run-accept and Close
        self._cleanup_temp()
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cleanup_temp()
        super().closeEvent(event)

    def _file_row(self, on_browse: "Callable[[], None]") -> tuple[QHBoxLayout, QLineEdit]:
        row = QHBoxLayout()
        field = QLineEdit(self)
        field.setReadOnly(True)
        field.setPlaceholderText(tr("No file selected"))
        row.addWidget(field, 1)
        btn = QPushButton(tr("Browse…"), self)
        btn.clicked.connect(on_browse)
        row.addWidget(btn)
        return row, field

    def _build_inputs(self) -> None:
        # Expected values: colour-space picker + load-from-file + paste box.
        head = QHBoxLayout()
        head.addWidget(QLabel(tr("Expected values:"), self))
        self._space = NoScrollComboBox(self)
        self._space.addItem(tr("CIE L*a*b*"), "LAB")
        self._space.addItem(tr("CIE XYZ"), "XYZ")
        head.addWidget(self._space)
        head.addStretch(1)
        load_btn = QPushButton(tr("Load from file…"), self)
        load_btn.clicked.connect(self._load_reference_file)
        head.addWidget(load_btn)
        self._content.addLayout(head)

        self._ref_edit = QPlainTextEdit(self)
        self._ref_edit.setPlaceholderText(
            tr("One patch per line, in chart order, e.g.:\n"
            "100  0  0\n95.2  -1.1  2.3\n…")
        )
        self._ref_edit.setFixedHeight(110)
        self._ref_edit.textChanged.connect(self._refresh)
        self._content.addWidget(self._ref_edit)

        self._content.addWidget(QLabel(tr("Measured chart (.ti3):"), self))
        row, self._measured_field = self._file_row(self._pick_measured)
        self._content.addLayout(row)

        self._content.addWidget(
            QLabel(tr("Chart definition (.ti1 / .ti2) — optional, cross-checks patch count:"), self)
        )
        row, self._chart_field = self._file_row(self._pick_chart)
        self._content.addLayout(row)

        prof_row = QHBoxLayout()
        prof_row.addWidget(
            QLabel(
                tr("Your profile (.icc) — optional, skips reference colours this "
                "paper can't print:"), self
            )
        )
        prof_row.addWidget(
            TooltipButton(
                tr("Skip unprintable colours"),
                tr("If your reference values were made for a different paper or finish "
                "(say glossy values checked on matte), some of them are colours your "
                "paper simply can't produce — most often the very darkest shadows, "
                "because matte paper can't go as dark as glossy. Comparing against "
                "those is unfair and makes the error look alarmingly high.\n\n"
                "Point this at the profile for the paper you actually printed on, and "
                "ChromIQ asks Argyll to leave those unreachable colours out of the "
                "score, then tells you how many it skipped. What's left is a fair "
                "measure of how well the colours your paper CAN make were reproduced."),
                self, min_width=520, color=_indicator_color(self._settings),
            ),
            0, Qt.AlignmentFlag.AlignVCenter,
        )
        prof_row.addStretch(1)
        self._content.addLayout(prof_row)
        row, self._profile_field = self._file_row(self._pick_profile)
        self._content.addLayout(row)

        opts = QHBoxLayout()
        opts.addWidget(QLabel(tr("ΔE formula:"), self))
        self._formula = NoScrollComboBox(self)
        self._formula.addItem(tr("CIEDE2000"), "-k")
        self._formula.addItem(tr("CIE94"), "-c")
        self._formula.addItem(tr("CIE76"), "")
        opts.addWidget(self._formula)
        opts.addWidget(
            TooltipButton(
                tr("ΔE formula"),
                tr("How the colour difference is scored. CIEDE2000 is the modern "
                "standard and best matches what your eye sees — leave it on this "
                "unless you need to match an older report. CIE94 and CIE76 are older "
                "formulas kept for comparison."),
                self, min_width=460, color=_indicator_color(self._settings),
            ),
            0, Qt.AlignmentFlag.AlignVCenter,
        )
        self._sort_cb = QCheckBox(tr("List worst patches first"), self)
        self._sort_cb.setChecked(True)
        opts.addSpacing(16)
        opts.addWidget(self._sort_cb)
        opts.addStretch(1)
        self._content.addLayout(opts)

        plot_row = QHBoxLayout()
        self._vrml_cb = QCheckBox(tr("Create a 3D difference map"), self)
        plot_row.addWidget(self._vrml_cb)
        plot_row.addWidget(
            TooltipButton(
                tr("3D difference map"),
                tr("Opens an interactive 3D picture of the result when the check "
                "finishes. Every patch is drawn as a short line from the colour you "
                "asked for (a green dot) to the colour you actually measured (a red "
                "dot), placed in 3D colour space. Long lines all leaning the same way "
                "tell you the print drifts consistently in that direction; a few long "
                "lines among short ones point to specific problem patches. Drag to "
                "rotate, scroll to zoom."),
                self, min_width=500, color=_indicator_color(self._settings),
            ),
            0, Qt.AlignmentFlag.AlignVCenter,
        )
        plot_row.addStretch(1)
        self._content.addLayout(plot_row)
        if not webengine_available():
            self._vrml_cb.setEnabled(False)
            self._vrml_cb.setToolTip(tr("Install PyQt6-WebEngine to enable the 3D map."))

        self._banner = QLabel("", self)
        self._banner.setWordWrap(True)
        self._banner.setStyleSheet("font-weight: bold;")
        self._content.addWidget(self._banner)

    # -- pickers --------------------------------------------------------
    def _load_reference_file(self) -> None:
        p = self._pick_input_file(
            tr("Choose expected-values file"),
            tr("Reference values (*.txt *.cgats *.ti3 *.csv);;All files (*)"),
        )
        if not p:
            return
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self._log.appendPlainText(f"[ERROR] Could not read {p.name}: {exc}")
            return
        self._ref_edit.setPlainText(text)
        self._refresh()

    def _pick_measured(self) -> None:
        p = self._pick_input_file(tr("Choose measured chart"), tr("Measurements (*.ti3);;All files (*)"))
        if p:
            self._measured = p
            self._measured_field.setText(str(p))
            self._refresh()

    def _pick_chart(self) -> None:
        p = self._pick_input_file(tr("Choose chart definition"), tr("Charts (*.ti1 *.ti2);;All files (*)"))
        if p:
            self._chart = p
            self._chart_field.setText(str(p))
            self._refresh()

    def _pick_profile(self) -> None:
        p = self._pick_input_file(tr("Choose your profile"), tr("ICC profiles (*.icc *.icm);;All files (*)"))
        if p:
            self._profile = p
            self._profile_field.setText(str(p))
            self._refresh()

    # -- run ------------------------------------------------------------
    def _can_run(self) -> bool:
        return self._measured is not None and bool(self._ref_edit.toPlainText().strip())

    def _execute(self) -> None:
        if self._runner.is_running:
            self._log.appendPlainText("[BUSY] Another operation is running — please wait.")
            self._finish(False)
            return

        assert self._measured is not None
        try:
            rows = parse_reference_values(self._ref_edit.toPlainText())
        except ValueError as exc:
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)
            return

        if self._chart is not None:
            try:
                n_chart = chart_patch_count(self._chart)
            except OSError as exc:
                self._log.appendPlainText(f"[ERROR] Could not read the chart: {exc}")
                self._finish(False)
                return
            if n_chart and n_chart != len(rows):
                self._log.appendPlainText(
                    f"[ERROR] The chart has {n_chart} patches but you supplied "
                    f"{len(rows)} expected values. They must match — check the "
                    "pasted table."
                )
                self._finish(False)
                return

        space     = self._space.currentData()
        want_plot = self._vrml_cb.isChecked() and self._vrml_cb.isEnabled()

        # For the 3D map, colverify writes the .x3d.html (plus sibling x3dom.js/
        # css) next to the measured file. Stage that run in a temp dir so the run
        # folder isn't littered; the normal run writes only the reference beside
        # the measurement, as before.
        if want_plot:
            work = Path(tempfile.mkdtemp(prefix="chromiq_drift_"))
            self._temp_dirs.append(work)
            measured_path = work / self._measured.name
            try:
                shutil.copyfile(self._measured, measured_path)
            except OSError as exc:
                self._log.appendPlainText(f"[ERROR] Could not stage the measurement: {exc}")
                self._finish(False)
                return
            ref_path = work / f"{self._measured.stem}-reference.ti3"
        else:
            measured_path = self._measured
            ref_path = self._measured.parent / f"{self._measured.stem}-reference.ti3"

        try:
            write_reference_ti3(ref_path, rows, space=space)
        except (ValueError, OSError) as exc:
            self._log.appendPlainText(f"[ERROR] Could not write reference file: {exc}")
            self._finish(False)
            return

        self._log.clear()
        self._banner.setText("")
        self._log.appendPlainText(
            f"Built reference: {ref_path.name} ({len(rows)} patches, {space})"
        )
        _remember_dir(self._settings, self.TOOL_KEY, self._measured.parent)

        params = ColverifyParams(
            ref_ti3=ref_path,
            measured_ti3=measured_path,
            de_formula=self._formula.currentData(),
            sort=self._sort_cb.isChecked(),
            gamut_profile=self._profile,
            vrml=want_plot,
        )
        if self._profile is not None:
            self._log.appendPlainText(
                f"Skipping out-of-gamut colours using profile: {self._profile.name}"
            )

        def _on_line(line: str) -> None:
            self._log.appendPlainText(line.rstrip())
            self._log.ensureCursorVisible()

        def _on_finish(code: int) -> None:
            result = self._cv.parse_results()
            if code == 0 and result.avg_de is not None:
                self._banner.setText(interpret(result))
                # Leave a readable report in reports/ next to the ORIGINAL
                # measurement (the 3D-map run verifies a staged temp copy),
                # like the quality check does (Knut, beta.5). Best-effort.
                try:
                    from core.file_manager import ensure_subdir, reports_subdir
                    from workflow.profcheck_runner import write_named_report
                    summary = "\n".join([
                        tr("Verification against reference values"),
                        datetime.now().isoformat(timespec="seconds"),
                        "",
                        tr("Measured file: {p}").format(p=self._measured),
                        tr("Reference: {n} patches ({space})").format(
                            n=len(rows), space=space),
                        "",
                        interpret(result),
                    ])
                    rp = write_named_report(
                        ensure_subdir(reports_subdir(self._measured.parent)),
                        "Verify_Reference", self._measured.stem,
                        summary, result.raw_log,
                        log_title="Full colverify output")
                    self._log.appendPlainText(tr(
                        "Report saved: {name} (in the reports folder next to "
                        "your measurement)").format(
                            name=f"{rp.parent.name}/{rp.name}"))
                except Exception:  # noqa: BLE001 — a report must never block the verdict
                    log.warning("could not write verification report",
                                exc_info=True)
                self._finish(True)
                if want_plot:
                    html = vrml_output_path(measured_path)
                    if html.exists():
                        DriftPlotDialog(html, self._settings, self).exec()
                    else:
                        self._log.appendPlainText(
                            "[NOTE] A 3D map was requested but colverify produced no "
                            "plot file."
                        )
            else:
                self._log.appendPlainText(
                    "[ERROR] colverify did not return a result. Check that the "
                    "measured .ti3 has the same patches (matched by SAMPLE_ID)."
                )
                self._finish(False)

        self._cv.run(params, _on_line, _on_finish)


class VerifyProfileDialog(_ToolDialogBase):
    TOOL_KEY    = "verify_profile"
    TITLE       = tr("Verify a profile (independent check)")
    EYEBROW     = tr("QUALITY CHECK")
    ACCENT      = SPEC_VIOLET
    RUN_LABEL   = tr("Verify profile")
    MIN_WIDTH   = 660
    DESCRIPTION = (
        tr("Check how accurate a finished profile really is by testing it against a "
        "chart it has never seen.\n\n"
        "Pick your profile (.icc) and a measured chart (.ti3) that you printed "
        "through that profile and read back. ChromIQ runs Argyll's profcheck, "
        "which asks the profile what each patch should look like and compares that "
        "to what you actually measured — then grades the result for you.")
    )
    HELP = (
        tr("This is the most honest way to answer “is my profile any good?”.\n\n"
        "Why a *separate* chart? When you build a profile, it is tuned to the exact "
        "patches you measured — so checking it against those same patches almost "
        "always looks great, even if the profile is weak elsewhere. Printing and "
        "measuring a *different* chart and checking the profile against that is a "
        "real test: the profile has to predict colours it was never trained on. "
        "Colour managers call this a round-trip or cross-check.\n\n"
        "How to do it:\n\n"
        "1. In ChromIQ, create a small chart (a few hundred patches is plenty) that "
        "is different from the one you built the profile with. The Create Chart tab "
        "can make one for you.\n"
        "2. Print it through the profile you want to test, then read it back on the "
        "Measure tab — that gives you a .ti3 measurement file.\n"
        "3. Come back here, pick that profile and that measurement, and click "
        "Verify profile.\n\n"
        "You'll get an average and a peak ΔE (colour-difference score, where smaller "
        "is better and 0 is perfect) plus a plain-language grade. A good printer "
        "profile typically lands in the “excellent/good” range; a high peak with a "
        "low average usually means one or two odd patches rather than a bad profile.\n\n"
        "Tip: this checks the profile itself. If instead you want to compare your "
        "print to colour targets someone else gave you, use “Verify against "
        "reference”.")
    )

    def __init__(self, runner: "ArgyllRunner", settings: "AppSettings",
                 parent: QWidget | None = None, project=None) -> None:
        super().__init__(settings, parent)
        self._runner   = runner
        self._checker  = ProfcheckRunner(runner)
        self._project_obj = project          # loaded Project, for #130 browse defaults
        self._profile: Path | None = None
        self._measured: Path | None = None
        self._build_inputs()
        self._refresh()

    def _file_row(self, on_browse: "Callable[[], None]") -> tuple[QHBoxLayout, QLineEdit]:
        row = QHBoxLayout()
        field = QLineEdit(self)
        field.setReadOnly(True)
        field.setPlaceholderText(tr("No file selected"))
        row.addWidget(field, 1)
        btn = QPushButton(tr("Browse…"), self)
        btn.clicked.connect(on_browse)
        row.addWidget(btn)
        return row, field

    def _label_with_tip(self, text: str, tip_title: str, tip_body: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(text, self))
        tip = TooltipButton(
            tip_title, tip_body, self,
            min_width=520, color=_indicator_color(self._settings),
        )
        row.addWidget(tip, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)
        return row

    def _build_inputs(self) -> None:
        self._content.addLayout(self._label_with_tip(
            "Profile to test (.icc):",
            "Profile to test",
            "The ICC profile whose accuracy you want to measure — the file Build "
            "Profile produced. ChromIQ asks this profile what colour each patch "
            "should be and compares that to your measurement.",
        ))
        row, self._profile_field = self._file_row(self._pick_profile)
        self._content.addLayout(row)

        self._content.addLayout(self._label_with_tip(
            "Measured chart (.ti3):",
            "Measured chart — use a fresh one",
            "A chart you printed through the profile above and then read back on "
            "the Measure tab. For a meaningful test use a chart that is DIFFERENT "
            "from the one you built the profile with — checking a profile against "
            "its own training patches almost always looks good even when the "
            "profile isn't. A few hundred fresh patches are plenty.",
        ))
        row, self._measured_field = self._file_row(self._pick_measured)
        self._content.addLayout(row)

        opts = QHBoxLayout()
        opts.addWidget(QLabel(tr("ΔE formula:"), self))
        self._formula = NoScrollComboBox(self)
        self._formula.addItem(tr("CIEDE2000"), "-k")
        self._formula.addItem(tr("CIE94"), "-c")
        self._formula.addItem(tr("CIE76"), "")
        opts.addWidget(self._formula)
        formula_tip = TooltipButton(
            tr("ΔE formula"),
            tr("How the colour difference is scored. CIEDE2000 is the modern standard "
            "and best matches what your eye sees — leave it on this unless you need "
            "to match an older report. CIE94 and CIE76 are older formulas kept for "
            "comparison."),
            self, min_width=460, color=_indicator_color(self._settings),
        )
        opts.addWidget(formula_tip, 0, Qt.AlignmentFlag.AlignVCenter)

        opts.addSpacing(16)
        opts.addWidget(QLabel(tr("Intent:"), self))
        self._intent = NoScrollComboBox(self)
        self._intent.addItem(tr("Absolute"), "a")
        self._intent.addItem(tr("Relative"), "r")
        opts.addWidget(self._intent)
        intent_tip = TooltipButton(
            tr("Rendering intent"),
            tr("Which way the profile is asked to reproduce colour for the check. "
            "Absolute compares exact colours including the paper white, and is the "
            "usual choice for judging accuracy. Relative ignores the paper-white "
            "difference, which can look kinder on papers whose white isn't neutral."),
            self, min_width=460, color=_indicator_color(self._settings),
        )
        opts.addWidget(intent_tip, 0, Qt.AlignmentFlag.AlignVCenter)

        self._sort_cb = QCheckBox(tr("List worst patches first"), self)
        self._sort_cb.setChecked(True)
        opts.addSpacing(16)
        opts.addWidget(self._sort_cb)
        opts.addStretch(1)
        self._content.addLayout(opts)

        self._banner = QLabel("", self)
        self._banner.setWordWrap(True)
        self._banner.setStyleSheet("font-weight: bold;")
        self._content.addWidget(self._banner)

    # -- pickers --------------------------------------------------------
    def _pick_profile(self) -> None:
        prof_dir, _meas_dir = self._verify_dirs()
        p = self._pick_input_file(tr("Choose profile to test"),
                                  tr("ICC profiles (*.icc *.icm);;All files (*)"),
                                  start_dir=prof_dir)
        if p:
            self._profile = p
            self._profile_field.setText(str(p))
            self._refresh()

    def _pick_measured(self) -> None:
        _prof_dir, meas_dir = self._verify_dirs()
        p = self._pick_input_file(tr("Choose measured chart"),
                                  tr("Measurements (*.ti3);;All files (*)"),
                                  start_dir=meas_dir)
        if p:
            self._measured = p
            self._measured_field.setText(str(p))
            self._refresh()

    def _verify_dirs(self) -> "tuple[Path | None, Path | None]":
        """Browse-default folders (profile, measurement) for this tool, pointing
        at the loaded project's run and its verification history (#130). Falls
        back to the tool's remembered folders when no project is open."""
        from core.measurement_target import verify_tool_dirs
        try:
            return verify_tool_dirs(self._project_obj)
        except Exception:      # noqa: BLE001 — a browse default must never break
            return None, None

    # -- run ------------------------------------------------------------
    def _can_run(self) -> bool:
        return self._profile is not None and self._measured is not None

    def _execute(self) -> None:
        if self._runner.is_running:
            self._log.appendPlainText("[BUSY] Another operation is running — please wait.")
            self._finish(False)
            return

        assert self._profile is not None and self._measured is not None
        self._log.clear()
        self._banner.setText("")
        _remember_dir(self._settings, self.TOOL_KEY, self._measured.parent)

        params = ProfcheckParams(
            ti3_path   = self._measured,
            icc_path   = self._profile,
            de_formula = self._formula.currentData(),
            intent     = self._intent.currentData() or "a",
            sort       = self._sort_cb.isChecked(),
            verbosity  = "2",
        )

        def _on_line(line: str) -> None:
            self._log.appendPlainText(line.rstrip())
            self._log.ensureCursorVisible()

        def _on_finish(code: int) -> None:
            result = self._checker.parse_results()
            # profcheck exits 1 when it finds colour errors — that's normal, so we
            # judge success on whether it produced numbers, not the exit code.
            if result.avg_de is not None:
                grade = quality_grade(result.avg_de, result.peak_de)
                self._banner.setText(
                    f"Verdict: {grade}\n\n"
                    + quality_explanation(result.avg_de, result.peak_de)
                )
                for _key, msg in self._checker.captured_warnings():
                    self._log.appendPlainText(f"[NOTE] {msg}")
                # Leave a readable report in reports/ next to the measurement,
                # like the quality check does (Knut, beta.5). Best-effort.
                try:
                    from core.file_manager import ensure_subdir, reports_subdir
                    from workflow.profcheck_runner import write_named_report
                    summary = "\n".join([
                        tr("Profile verification (independent check)"),
                        datetime.now().isoformat(timespec="seconds"),
                        "",
                        tr("Profile tested: {p}").format(p=self._profile),
                        tr("Measured chart: {p}").format(p=self._measured),
                        tr("ΔE formula: {f}   Intent: {i}").format(
                            f=self._formula.currentText(),
                            i=self._intent.currentText()),
                        "",
                        tr("Verdict: {grade}").format(grade=grade),
                        "",
                        quality_explanation(result.avg_de, result.peak_de),
                    ])
                    rp = write_named_report(
                        ensure_subdir(reports_subdir(self._measured.parent)),
                        "Verify_Profile", self._measured.stem,
                        summary, result.raw_log,
                        log_title="Full profcheck output")
                    self._log.appendPlainText(tr(
                        "Report saved: {name} (in the reports folder next to "
                        "your measurement)").format(
                            name=f"{rp.parent.name}/{rp.name}"))
                except Exception:  # noqa: BLE001 — a report must never block the verdict
                    log.warning("could not write verification report",
                                exc_info=True)
                self._finish(True)
            else:
                failure = self._checker.primary_failure()
                if failure is not None:
                    self._log.appendPlainText(f"[ERROR] {failure[1]}")
                else:
                    self._log.appendPlainText(
                        "[ERROR] profcheck did not return a result. Check that the "
                        ".ti3 was measured through this profile's chart and that the "
                        "files match."
                    )
                self._finish(False)

        self._checker.run(params, _on_line, _on_finish)


def open_tool_dialog(
    key: str,
    runner: "ArgyllRunner",
    settings: "AppSettings",
    parent: QWidget | None = None,
    on_apply: "Callable[[Path, str], bool | None] | None" = None,
    initial_chart: "Path | None" = None,
    project=None,
) -> None:
    """Open the dialog for the given tool key (no-op for unknown keys).

    ``on_apply`` is forwarded to the TI2 layout editor so its "Save & apply"
    button can hand a freshly-saved chart folder back to the Create Chart tab.
    ``initial_chart`` pre-loads that editor with the Create Chart tab's current
    chart so it opens ready to edit (#45).
    """
    if key == "spot_read":
        from ui.dialogs.spot_read_dialog import SpotReadDialog
        dlg = SpotReadDialog(runner, settings, parent)
    elif key == "ti2_relayout":
        from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
        dlg = Ti2RelayoutDialog(runner, settings, parent, on_apply=on_apply,
                                initial_chart=initial_chart)
    elif key == "average":
        dlg = AverageMeasurementsDialog(runner, settings, parent)
    elif key == "merge":
        dlg = MergeMeasurementsDialog(settings, parent)
    elif key == "ti1_to_i1p":
        dlg = Ti1ToI1ProfilerDialog(settings, parent)
    elif key == "i1p_to_ti3":
        dlg = I1ProfilerToTi3Dialog(runner, settings, parent)
    elif key == "i1p_to_ti1":
        dlg = I1ProfilerToTi1Dialog(settings, parent)
    elif key == "verify":
        dlg = VerifyAgainstReferenceDialog(runner, settings, parent)
    elif key == "verify_profile":
        dlg = VerifyProfileDialog(runner, settings, parent, project=project)
    elif key == "profile_info":
        from ui.dialogs.profile_info_dialog import ProfileInfoDialog
        dlg = ProfileInfoDialog(runner, settings, parent)
    elif key == "ti3_info":
        from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
        dlg = Ti3InfoDialog(runner, settings, parent)
    elif key == "measurement_report":
        from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
        dlg = MeasurementReportDialog(settings, parent)
    elif key == "softproof":
        from ui.dialogs.softproof_dialog import SoftproofDialog
        dlg = SoftproofDialog(runner, settings, parent)
    elif key == "device_link":
        from ui.dialogs.devicelink_dialog import DeviceLinkDialog
        dlg = DeviceLinkDialog(runner, settings, parent)
    elif key == "devicelink_apply":
        from ui.dialogs.devicelink_apply_dialog import DeviceLinkApplyDialog
        dlg = DeviceLinkApplyDialog(runner, settings, parent)
    elif key == "scanner_target":
        from ui.dialogs.scanin_target_dialog import ScaninTargetDialog
        dlg = ScaninTargetDialog(settings, parent)
    elif key == "scanner_profile":
        from ui.dialogs.scanin_dialog import ScannerProfileDialog
        dlg = ScannerProfileDialog(runner, settings, parent)
    elif key == "translate":
        from ui.dialogs.translation_dialog import TranslationDialog
        dlg = TranslationDialog(settings, parent)
    else:
        log.warning("Unknown tool key: %s", key)
        return
    dlg.exec()
