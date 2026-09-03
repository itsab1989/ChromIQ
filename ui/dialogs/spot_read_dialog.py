"""Single-patch (spot) reading tool — Tools ▸ "Read single patches".

Drives ArgyllCMS ``spotread`` via ``SpotReadManager`` to measure individual
colour patches off any material (or a display / light source), shows each
reading's L*a*b* with an on-screen sRGB swatch, and saves the set to a CSV plus
an Argyll ``.ti3``.

This is a standalone ``QDialog`` (its interactive Start/Take-reading/table shape
doesn't fit the Run/Close+log ``_ToolDialogBase``), but it reuses that module's
styling helpers and the calibration-popup pattern from the Measure tab so it
looks and behaves like the rest of the app.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from core.stem_paths import artefact, without_ext

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from ui.cr30_calibration import Cr30CalibrationMixin
from ui.dialogs.tools_dialogs import _indicator_color, neutral_controls_qss
from ui.styles import SPEC_GREEN
from ui.tab_header import dialog_masthead
from ui.warning_sign import set_warning_icon
from ui.widgets import NoScrollComboBox, set_ink, tint_dialog_primary
from workflow.spot_read_io import SpotReading, average_readings, write_csv, write_ti3
from workflow.spot_read_manager import SpotReadManager, SpotReadParams

import logging
import re

from ui.ti2_loader import calibration_instructions_html

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

_ACCENT = "#56d6a5"   # share the Measure tab's accent — this is measurement work


#: The instruments this window can read with, in the app's own vocabulary.
#:
#: ChromIQ NAMES its instruments in a list — `data/parameters.yaml`'s printtarg
#: `-i` row offers i1Pro, i1Pro 3 Plus, ColorMunki, SpectroScan, CR30 and i1iSis
#: — and `ui.ti2_loader.KNOWN_INSTRUMENTS` names the four ChromIQ can act on,
#: the CR30 among them. So the CR30 belongs in a list here too, not behind a
#: button of its own.
#:
#: What this list names is the READER, not the model, and that is the honest
#: distinction: `spotread` cannot be told which instrument to use (`-c` picks a
#: communication port, never a device), so naming individual ArgyllCMS models
#: here would be offering a choice ChromIQ cannot act on. There are exactly two
#: readers, and the CR30 is the one ArgyllCMS has never heard of.
_INSTRUMENT_KEYS = ("auto", "argyll", "cr30")


def _instrument_labels() -> "list[str]":
    return [tr("Detect automatically"),
            tr("Any ArgyllCMS instrument"),
            tr("CR30 (ChnSpec)")]


def cr30_is_probably_attached() -> bool:
    """Is a CR30 plugged in over USB, on the evidence already on this machine?

    **Nothing is opened and nothing is written.** It lists the serial ports
    (`serial.tools.list_ports`, an IORegistry read) and asks two questions of
    them: is a CH340 bridge plugged in *now*, and has this machine ever
    confirmed a CR30 over USB before.

    BOTH HALVES ARE NEEDED, and neither is enough on its own.

    * `0x1A86:0x7523` is the generic CH340 bridge: an Arduino, a 3D printer or
      a CNC controller answers to it. On its own it is not evidence of an
      instrument, and treating it as one would hand a ColorMunki owner a broken
      spot tool by default — the exact thing this feature must not do.
      Confirming a candidate means WRITING an identify frame to it, which is
      not something to do to somebody's devices on the strength of a guess.
    * The remembered port on its own is not evidence either, and this is the
      part that used to be missing. It was the WHOLE test until 2026-09-03,
      when the owner's own Mac disproved it: `cr30_usb_port` remembered
      `/dev/cu.usbserial-10` while his CR30 was sitting on
      `/dev/cu.usbserial-110`. A `cu.usbserial-*` node number is not stable
      across replugs — `workflow/cr30/discovery.py` says so in its own
      docstring — so the strict comparison quietly stopped recognising the
      instrument it was written for, and only the remembered Bluetooth address
      was still finding it.

    Together they say: *this machine has confirmed a CR30 over USB before, and
    something that could be it is plugged in now.* That is live evidence with a
    history behind it, and it is what makes the port node irrelevant.

    It can still only ever be wrong in the safe direction. A missed CR30 costs
    one choice from a dropdown. A CH340 gadget mistaken for one costs nothing
    to anybody who has never used a CR30 here (no remembered port, so this is
    False), and for anybody who has, an ArgyllCMS instrument that is actually
    attached outranks this answer anyway — see :meth:`SpotReadDialog._automatic_reader`.
    """
    try:
        from workflow.cr30.discovery import candidates
        from workflow.cr30.measure_bridge import DeviceReader
        remembered = DeviceReader._remembered(DeviceReader.REMEMBERED_PORT_KEY)
        if not remembered:
            return False
        return bool(candidates())
    except Exception:      # noqa: BLE001 — a guess, never worth an error
        log.debug("could not look for a CR30 on USB", exc_info=True)
        return False


def argyll_is_attached() -> "bool | None":
    """Is an instrument ArgyllCMS can drive plugged in over USB right now?

    THE MISSING HALF OF THE COMPARISON. Until this existed, automatic could see
    a CR30 and it could see a *remembered* CR30, but it could not see a
    ColorMunki at all — so the weakest evidence there is, an address stored at
    some point in the past, outranked an instrument sitting on the desk. The
    owner hit it the day it shipped: *"had my colormunki connected via usb and
    set to detect automatically. it defaulted to the cr30 via blutooth and did
    not leave me a choice."*

    `core.argyll_instruments` answers it from the operating system's own device
    list, against ArgyllCMS's own `inst_usb_match()` table. Nothing is opened,
    nothing is claimed, and `spotread` is NOT launched to find out — launching
    it is slow, it takes the instrument, and its usage text is what filled his
    log.

    **Three answers, not two.** None means this host could not be enumerated,
    which is not the same as "nothing is attached" and must never be read as
    it: an unknown may not contradict anything.
    """
    try:
        from core.argyll_instruments import any_attached
        return any_attached()
    except Exception:      # noqa: BLE001 — a guess, never worth an error
        log.debug("could not look for an ArgyllCMS instrument", exc_info=True)
        return None


def cr30_is_remembered_over_bluetooth() -> bool:
    """Has this computer ever reached a CR30 over Bluetooth?

    THE OTHER HALF OF AUTOMATIC, AND IT WAS MISSING. The owner tried the tool
    with a CR30 paired over Bluetooth on 2026-09-02: automatic did not find it,
    fell through to ArgyllCMS, and spotread offered him
    `/dev/cu.Bluetooth-Incoming-Port` — macOS's own incoming serial port, which
    is not an instrument and never will be. ArgyllCMS cannot drive a CR30 at
    all, so that route could only ever end in "no instrument detected".

    The reason was structural rather than a bug in the search:
    :func:`cr30_is_probably_attached` asks `discovery.candidates()`, which
    filters on the CH340 bridge's `0x1A86:0x7523` — and a Bluetooth CR30 is not
    a USB serial port, so it can never appear in that list however many times it
    has been used.

    **The evidence used here is exactly as strong as the USB rule's**, which is
    what makes it safe to add: `DeviceReader` writes
    ``REMEMBERED_ADDRESS_KEY`` only after ``identify()`` has come back from that
    address with the model string — i.e. only for a device that has answered as
    a CR30 on this machine. Nothing is opened, nothing is written, and no
    Bluetooth scan is started: this reads one remembered setting.

    It cannot report a device that is out of range — a scan is the only thing
    that could, and a scan measured 15.4 s on the owner's Mac, which is not
    something to spend before a dropdown can answer. When the instrument is
    away, ChromIQ's own reader says so in its own words, which name both
    transports; that is a far better ending than spotread's port list.
    """
    try:
        from workflow.cr30.measure_bridge import DeviceReader
        return bool(DeviceReader._remembered_address())
    except Exception:      # noqa: BLE001 — a guess, never worth an error
        log.debug("could not look for a remembered CR30 address", exc_info=True)
        return False

_HELP = tr(
    "Read individual colour patches with your measuring instrument, off any "
    "material — printed sheets, fabric, paint chips, or even a display.\n\n"
    "Click Start session, calibrate the instrument if prompted, then place it "
    "on a colour and click Take reading — or press the button on the instrument "
    "itself, which does the same thing. Each reading is added to the table with "
    "its L*a*b* value and an approximate on-screen colour. Save writes a CSV (for "
    "a spreadsheet) and an Argyll .ti3 (for other tools).\n\n"
    "If a reading comes out inconsistent — usually because the instrument moved "
    "while it was measuring — it is discarded and the status line says so. Click "
    "Take reading to clear that and measure again; the instrument's own button "
    "cannot clear it."
)


def _without_call_to_action(html: str) -> str:
    """Drop a trailing "then click <b>Start Calibration</b>." from shared text.

    `calibration_instructions_html` is written for the Measure tab, whose button
    is Start Calibration. Reused verbatim in a window with a different button it
    tells the user to click something that is not there (Knut, #130 2026-08-01).
    """
    out = re.sub(r",?\s*(?:and\s+)?then click <b>Start Calibration</b>\.?",
                 ".", html, flags=re.IGNORECASE)
    return re.sub(r"\.\.", ".", out)


class SpotReadDialog(Cr30CalibrationMixin, QDialog):
    _MODE_KEYS = ("reflective", "emissive", "ambient")

    def __init__(
        self,
        runner: "ArgyllRunner",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._manager = SpotReadManager(runner, self)
        #: ChromIQ's own reader, built only when a CR30 session actually
        #: starts. A user who has no CR30 never reaches any of it, and while
        #: this is None every route through this window is the one that has
        #: always run.
        self._cr30 = None
        #: The open :class:`DeviceReader`, which is also what holds the claim
        #: on the instrument (`core.instrument_lease`).
        self._cr30_reader = None
        self._sound = None
        #: The last automatic answer and the evidence behind it, so the label's
        #: refresh can log a CHANGE and not repeat itself once a second.
        self._auto_evidence: "tuple | None" = None
        #: Keeps the "→ <reader>" label honest while a cable is plugged in or
        #: pulled out under an open window. A bound method, never a lambda —
        #: see CLAUDE.md on `ui/fade_scroll.py`.
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(2000)
        self._auto_timer.timeout.connect(self._refresh_auto_choice)
        self._readings: list[SpotReading] = []
        #: What the last Clear took away, kept so it can be put back. Nothing
        #: the user made is destroyed without a way back; see `_on_clear`.
        self._cleared: list[SpotReading] = []
        #: True once a reading exists that has not been written to a file, so
        #: closing the window can say so instead of binning a session.
        self._unsaved = False
        #: True while `_set_read_enabled(False)` moved the focus out of the
        #: way, so re-enabling can hand it back.
        self._focus_parked = False
        #: True once the unsaved-work question has been answered "go ahead",
        #: so the second route into `_may_close` does not ask again.
        self._closing = False
        #: True between a misread and the next ready prompt. While set, Take
        #: reading clears the error before it reads (see _on_take_reading).
        self._misread = False

        self.setWindowTitle(tr("Read single patches"))
        self.setMinimumWidth(960)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Tab-style masthead (eyebrow + serif title + ⓘ) over a full-width
        # spectrum stripe, matching the chart-design windows. The outer layout
        # spans full width so the stripe bleeds to the edges; the content below
        # re-adds the side inset.
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head, _header, stripe = dialog_masthead(
            self, tr("INSTRUMENT · SPOT READ"), tr("Read single patches"),
            tooltip_title=tr("Read single patches"), tooltip_body=_HELP,
            accent=SPEC_GREEN)
        root.addLayout(head)
        root.addWidget(stripe)

        outer = QVBoxLayout()
        outer.setContentsMargins(22, 14, 22, 16)
        outer.setSpacing(12)
        root.addLayout(outer)

        body = QLabel(
            tr("Measure single colours off any material and save their L*a*b* values."),
            self,
        )
        body.setWordWrap(True)
        outer.addWidget(body)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(sep)

        # --- Session controls (disabled once a session runs) ---------------
        # The instrument number (spotread -c) is left at 1: almost everyone has a
        # single measuring device connected, so we don't ask. Multi-instrument
        # users can still use the strip-based Measure tab.
        controls = QHBoxLayout()
        controls.setSpacing(10)

        # THE INSTRUMENT IS NAMED, LIKE EVERYWHERE ELSE IN CHROMIQ. Create
        # Chart names its instruments in a list and the CR30 is already a peer
        # in it; this window used to name none, because ArgyllCMS `spotread`
        # cannot be told which device to open. Now there are two readers to
        # choose between, so the choice is a row, in the same place a chart's
        # instrument row is — not a button off to one side.
        controls.addWidget(QLabel(tr("Instrument"), self))
        self._instrument = NoScrollComboBox(self)
        for _label in _instrument_labels():
            self._instrument.addItem(_label)
        _stored = str(settings.get("spot_read_instrument", "auto") or "auto")
        self._instrument.setCurrentIndex(
            _INSTRUMENT_KEYS.index(_stored) if _stored in _INSTRUMENT_KEYS else 0)
        self._instrument.setToolTip(tr(
            "Leave this on automatic unless you want to insist on one reader."))
        self._instrument.currentIndexChanged.connect(self._on_instrument_changed)
        controls.addWidget(self._instrument)

        # WHAT AUTOMATIC SETTLED ON, SAID OUT LOUD. Half of the owner's report
        # was *"did not leave me a choice"* — and there WAS a choice, one
        # control to the left of this label, but nothing on screen said which
        # reader "Detect automatically" had landed on or that it had landed on
        # anything at all. A window that decides silently has not left anybody
        # a choice, whatever its dropdown offers.
        #
        # No new sentence is invented here: the arrow points at one of this
        # combo's OWN entries, already written and already translated. The
        # decision is shown in the row that changes it, so changing it is one
        # click and no hunting.
        self._auto_choice = QLabel("", self)
        self._auto_choice.setObjectName("spotAutoChoice")
        set_ink(self._auto_choice, "#909090", level="dim")
        controls.addWidget(self._auto_choice)

        controls.addWidget(QLabel(tr("Mode"), self))
        self._mode = NoScrollComboBox(self)
        self._mode.addItem(tr("Reflective (material)"))
        self._mode.addItem(tr("Emissive (display)"))
        self._mode.addItem(tr("Ambient (light)"))
        controls.addWidget(self._mode)

        # NEITHER COMBO MAY SHRINK BELOW ITS OWN WIDEST ENTRY.
        #
        # The row grew by one control, and a QHBoxLayout answers that by taking
        # the space out of whatever will give it. What gave was Mode: it
        # rendered "Reflective (materia" — clipped, with no ellipsis to say so —
        # and only while DISABLED, which is exactly when a session is running
        # and nobody can widen it. Seen on screen; the before/after pictures are
        # beside this branch's report.
        #
        # Pinned to the content rather than to a number, so a longer
        # translation moves the floor with it (a fixed width turns cramped into
        # overlapping, which is worse).
        for _combo in (self._instrument, self._mode):
            _fm = _combo.fontMetrics()
            _widest = max((_fm.horizontalAdvance(_combo.itemText(i))
                           for i in range(_combo.count())), default=0)
            _combo.setMinimumWidth(_widest + 44)   # frame + the drop indicator

        self._skip_cal = QCheckBox(tr("Skip initial calibration"), self)
        controls.addWidget(self._skip_cal)
        # Knut, #130 2026-07-31: *"add an help icon to the right of the checkbox
        # text and in that help text explain how argyllcms handles this request,
        # and that some instruments (like the ColorMunki / i1Studio) will still
        # often require a calibration the first time, but skip calibration if
        # you stop your measurement session and start another shortly after."*
        # He reported the box as broken; it is not, and the honest fix is to say
        # what it can and cannot promise.
        from ui.tooltip_button import TooltipButton
        controls.addWidget(TooltipButton(
            tr("About skipping the initial calibration"),
            tr("Ticking this asks ArgyllCMS to start measuring without "
               "calibrating first. ChromIQ passes it on as the -N option.\n\n"
               "It is a request, not a command. ArgyllCMS skips the calibration "
               "only where the instrument allows it, and several do not: a "
               "ColorMunki or i1Studio will usually still ask the first time you "
               "use it after plugging it in, however this box is set. That is "
               "the instrument protecting the accuracy of your readings, and "
               "nothing ChromIQ can overrule.\n\n"
               "Where it does help is a run of short sessions. Once the "
               "instrument is calibrated, it stays calibrated for a while — so "
               "if you stop a session and start another one shortly after, "
               "ticking this lets you go straight to reading instead of "
               "calibrating again.\n\n"
               "If you are unsure, leave it unticked. Calibrating takes a few "
               "seconds and is never the wrong thing to do."),
            self, color=_ACCENT))
        controls.addStretch(1)
        outer.addLayout(controls)

        self._status = QLabel(tr("Idle — click Start session to begin."), self)
        self._status.setWordWrap(True)
        set_ink(self._status, "#909090", level="faint")
        outer.addWidget(self._status)

        # --- Results table -------------------------------------------------
        self._table = QTableWidget(0, 8, self)
        self._table.setHorizontalHeaderLabels([
            tr("Name"), tr("L*"), tr("a*"), tr("b*"),
            tr("X"), tr("Y"), tr("Z"), tr("Colour"),
        ])
        self._table.verticalHeader().setVisible(False)
        # Taller rows so each cell — especially the Colour swatch — has more
        # breathing room.
        self._table.verticalHeader().setDefaultSectionSize(34)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hdr = self._table.horizontalHeader()
        # Name keeps the lion's share (stretches to fill), but the value /
        # Colour columns get comfortable fixed widths — wider than auto-sizing to
        # their short contents — so they're not cramped while Name stays the
        # biggest column by far.
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 7):                       # L* a* b* X Y Z — kept small
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(c, 50)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(7, 128)          # Colour swatch (bigger)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(self._update_average_btn)
        outer.addWidget(self._table, 1)

        # --- Session notes -------------------------------------------------
        # The same status pane every other tool window carries
        # (`_ToolDialogBase`), down to its placeholder. HIDDEN UNTIL THERE IS
        # SOMETHING IN IT: the ArgyllCMS session has never written here and
        # must not start to, so for everybody else this window is exactly the
        # window it was. The CR30's calibration writes the notes that matter —
        # which way it connected, what the dark reference read back at — and
        # they have to be readable somewhere.
        self._log = QPlainTextEdit(self)
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setFixedHeight(120)
        self._log.setPlaceholderText(tr("Status messages will appear here."))
        self._log.setVisible(False)
        outer.addWidget(self._log)

        # --- Bottom buttons ------------------------------------------------
        # Session controls (Start / Take reading) live on the far left next to
        # Clear; Save / Close sit on the right — one unified action row.
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self._start_btn = QPushButton(tr("Start session"), self)
        self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self._on_start_stop)
        bottom.addWidget(self._start_btn)

        self._read_btn = QPushButton(tr("Take reading"), self)
        self._read_btn.setEnabled(False)
        self._read_btn.clicked.connect(self._on_take_reading)
        bottom.addWidget(self._read_btn)
        # The shared CR30 calibration windows hold "the controls that could
        # start or stop a read" across a nested event loop, and on the Measure
        # tab those are Start and Stop. Here they are Start and Take reading —
        # this window's Start button is its own Stop. Named rather than special
        # cased, so the shared code needs no branch.
        self._stop_btn = self._read_btn

        self._avg_btn = QPushButton(tr("Average selected"), self)
        self._avg_btn.setEnabled(False)
        self._avg_btn.setToolTip(
            tr("Select two or more readings, then average them into a new entry.")
        )
        self._avg_btn.clicked.connect(self._on_average_selected)
        bottom.addWidget(self._avg_btn)

        self._clear_btn = QPushButton(tr("Clear"), self)
        self._clear_btn.setEnabled(False)
        self._clear_btn.clicked.connect(self._on_clear)
        bottom.addWidget(self._clear_btn)

        bottom.addStretch(1)

        self._save_btn = QPushButton(tr("Save…"), self)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        bottom.addWidget(self._save_btn)

        close_btn = QPushButton(tr("Close"), self)
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(close_btn)

        outer.addLayout(bottom)

        # Neutral indicators, but the dropdown wears this tool's own green.
        self.setStyleSheet(
            neutral_controls_qss(_indicator_color(settings), popup=_ACCENT))
        # Tint the Start button with the Measure tab's green accent — this tool
        # is measurement work and reads as part of that family.
        tint_dialog_primary(self, _ACCENT)

        # --- Manager signals ----------------------------------------------
        m = self._manager
        m.reading_ready.connect(self._on_reading)
        m.ready_to_read.connect(self._on_ready)
        m.instrument_detected.connect(self._on_instrument_detected)
        m.calibration_prompt.connect(self._on_calibration_prompt)
        m.calibration_finished.connect(self._on_calibration_finished)
        m.calibration_position_wrong.connect(self._on_calibration_position_wrong)
        m.misread.connect(self._on_misread)
        m.sensor_wrong_position.connect(self._on_sensor_wrong_position)
        m.no_instrument.connect(self._on_no_instrument)
        m.device_busy.connect(self._on_device_busy)
        m.instrument_disconnected.connect(self._on_disconnected)
        m.coms_init_failed.connect(lambda s: self._on_init_failed(s))
        m.inst_init_failed.connect(lambda s: self._on_init_failed(s))
        m.session_ended.connect(self._on_session_ended)

        # Name the settled reader before the window is ever shown, so it is
        # right in the first frame and in a `.grab()` that never shows it.
        #
        # …AND GREY WHAT THE REMEMBERED READER CANNOT DO. Found while
        # photographing this row, 2026-09-03: `setCurrentIndex` above runs
        # BEFORE `currentIndexChanged` is connected, so a window reopened with
        # "CR30 (ChnSpec)" remembered came up offering Mode and Skip initial
        # calibration — both ArgyllCMS's, both dead for a CR30, and both
        # already refused for a CR30 chosen during the session. Same call, at
        # the one moment nothing had made it.
        self._apply_reader_capabilities()
        self._refresh_auto_choice()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def _active_manager(self):
        """Whichever reader this session is running on.

        Nothing below asks WHICH: both managers present the same signals and
        the same five methods, which is the whole point of the second one. This
        exists only so that "is a session running?" and "stop it" have one
        answer.
        """
        return self._cr30 if self._cr30 is not None else self._manager

    def _automatic_reader(self) -> "tuple[str, bool | None, bool, bool]":
        """What "Detect automatically" settles on, and the evidence it used.

        **WHAT IS CONNECTED NOW BEATS WHAT WAS CONNECTED ONCE.** That is the
        whole rule, and getting it wrong is what the owner reported on
        2026-09-03: a `cr30_ble_address` stored at some point in the past made
        automatic choose the CR30 for ever, on a Mac with a ColorMunki plugged
        into it. A remembered address is the weakest evidence there is — it
        says a CR30 answered here once, not that one is here now, and nothing
        ever clears it.

        The precedence, strongest first:

        1. **A choice made by hand.** Not decided here at all; see
           :meth:`_chosen_reader`. It always wins and it is remembered.
        2. **An ArgyllCMS instrument attached now** (`argyll_is_attached`).
        3. **A CR30 attached now** (`cr30_is_probably_attached`), or one this
           machine has reached over Bluetooth before
           (`cr30_is_remembered_over_bluetooth`).
        4. Nothing at all: ArgyllCMS, which is what this window has always
           done and what its "no instrument detected" ending is written for.

        **WHY 2 BEATS 3 WHEN BOTH ARE LIVE**, which is a real decision and not
        a fallout of the order:

        * It is his stated requirement for the entire feature: *"supporting the
          cr30 should not affect the other supported instruments so i should be
          able to still use my colormunki for example."* A CR30 left plugged in
          from yesterday must not take his ColorMunki away from him.
        * ArgyllCMS was this window's only reader until the CR30 was added, so
          this keeps automatic meaning what it has always meant for everybody
          who is not deliberately reaching for the CR30.
        * The evidence is not quite equal either. An ArgyllCMS match is a
          vendor/product id that names an instrument. The CR30's is a CH340
          bridge plus a history — true of an Arduino on a machine that has used
          a CR30 before.
        * It is cheap to be wrong in this direction and dear in the other: the
          Instrument row NAMES the reader automatic settled on and changing it
          is one click in that same row, and the choice is then remembered.

        Neither 2 nor 3 opens a device, claims one, or starts a Bluetooth scan.

        Returns ``(reader, argyll_attached, cr30_on_usb, cr30_over_bluetooth)``
        so that the window can show its reasoning without asking twice.
        """
        argyll = argyll_is_attached()
        on_usb = cr30_is_probably_attached()
        over_bt = cr30_is_remembered_over_bluetooth()
        if argyll is True:
            chosen = "argyll"
        elif on_usb or over_bt:
            chosen = "cr30"
        else:
            chosen = "argyll"
        return chosen, argyll, on_usb, over_bt

    def _chosen_reader(self) -> str:
        """"argyll" or "cr30" — which reader a Start would use, right now.

        The decision is logged, because it was not. His log of the failed
        session (2026-09-02 23:29) records the spotread launch and nothing at
        all about why ChromIQ chose spotread, so the first question anybody
        asked of it could not be answered from the file.
        """
        key = _INSTRUMENT_KEYS[self._instrument.currentIndex()]
        if key != "auto":
            log.info("spot read: reader chosen by hand: %s", key)
            return key
        chosen, argyll, on_usb, over_bt = self._automatic_reader()
        log.info("spot read: Detect automatically -> %s (ArgyllCMS instrument "
                 "attached now: %s; CR30 on USB now: %s; CR30 reached over "
                 "Bluetooth before: %s)", chosen, argyll, on_usb, over_bt)
        return chosen

    def _on_instrument_changed(self, _index: int) -> None:
        """Remember the choice, and grey out what the chosen reader cannot do.

        Mode and "Skip initial calibration" are ArgyllCMS's, both of them: a
        CR30 is reflective only, and its calibration is its own two-step affair
        with a magnetic cap, driven by ChromIQ rather than requested through a
        command-line flag. Leaving them live would offer settings that go
        nowhere, which is how somebody comes to believe they measured a display.
        """
        try:
            self._settings.set(
                "spot_read_instrument",
                _INSTRUMENT_KEYS[self._instrument.currentIndex()])
        except Exception:      # noqa: BLE001 — remembering is never worth a crash
            log.debug("could not store the spot-read instrument", exc_info=True)
        self._apply_reader_capabilities()
        self._refresh_auto_choice()

    def _apply_reader_capabilities(self) -> None:
        cr30 = _INSTRUMENT_KEYS[self._instrument.currentIndex()] == "cr30"
        self._mode.setEnabled(not cr30)
        self._skip_cal.setEnabled(not cr30)

    # ------------------------------------------------------------------
    # Saying which reader automatic settled on
    # ------------------------------------------------------------------
    def _refresh_auto_choice(self) -> None:
        """Put the settled reader's own name beside the Instrument combo.

        Only while the combo says "Detect automatically" — with a reader chosen
        by hand the combo already names it, and an arrow repeating it would
        read as a second, different answer.

        Recomputed rather than remembered, because the answer changes when a
        cable does. Both probes are OS device lists: 17 ms together on the
        owner's Mac, nothing opened and nothing claimed.
        """
        if _INSTRUMENT_KEYS[self._instrument.currentIndex()] != "auto":
            self._auto_choice.setText("")
            self._auto_choice.setVisible(False)
            return
        if not self._instrument.isEnabled():
            # A session owns the instrument. The reader is settled, the combo
            # is greyed, and nothing may be asked of the device list under a
            # running measurement.
            return
        chosen, argyll, on_usb, over_bt = self._automatic_reader()
        label = _instrument_labels()[_INSTRUMENT_KEYS.index(chosen)]
        self._auto_choice.setText(f"→ {label}")
        self._auto_choice.setVisible(True)
        if (chosen, argyll, on_usb, over_bt) != self._auto_evidence:
            self._auto_evidence = (chosen, argyll, on_usb, over_bt)
            log.info("spot read: automatic now points at %s (ArgyllCMS "
                     "instrument attached now: %s; CR30 on USB now: %s; CR30 "
                     "reached over Bluetooth before: %s)",
                     chosen, argyll, on_usb, over_bt)

    def showEvent(self, event) -> None:  # noqa: N802, D102
        super().showEvent(event)
        self._refresh_auto_choice()
        # A window that names the reader has to keep naming the right one: he
        # can plug the ColorMunki in while this is open, and a label that went
        # stale would be worse than no label. Idle only — nothing is asked of
        # the operating system while a session owns the instrument.
        self._auto_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802, D102
        self._auto_timer.stop()
        super().hideEvent(event)

    def _on_start_stop(self) -> None:
        active = self._active_manager()
        if active.is_running:
            active.quit()
            active.abort()
            return
        if self._chosen_reader() == "cr30":
            self._start_cr30_session()
            return
        params = SpotReadParams(
            mode=self._MODE_KEYS[self._mode.currentIndex()],
            disable_initial_cal=self._skip_cal.isChecked(),
        )
        self._set_session_running(True)
        self._set_status(tr("Starting instrument…"))
        self._manager.start(params, lambda _line: None)

    # ------------------------------------------------------------------
    # The CR30 — ChromIQ's own reader, for the one instrument ArgyllCMS
    # cannot open at all
    # ------------------------------------------------------------------
    def _start_cr30_session(self) -> None:
        """Claim the instrument, calibrate it, then read until Stop.

        The order is the Measure tab's order and for its reasons: the claim
        first, because refusing costs nothing before anything is opened, then
        the calibration, which is what actually opens the device.
        """
        from core import instrument_lease

        elsewhere = instrument_lease.held_by_other(self._cr30_reader)
        if elsewhere is not None:
            self._show_instrument_busy(elsewhere)
            return
        self._set_session_running(True)
        self._log.setVisible(True)
        self._log.clear()
        self._set_status(tr("Starting instrument…"))
        # The shared calibration windows (ui/cr30_calibration.py) — the same
        # ones the Measure tab shows, not a second set that could drift from
        # them. They open the reader through _open_cr30_bridge below.
        if not self._run_cr30_calibration():
            self._close_cr30_bridge()
            self._set_session_running(False)
            self._set_status(tr("Session ended."))
            return
        from workflow.cr30_spot_manager import Cr30SpotManager
        mgr = self._cr30 = Cr30SpotManager(self)
        mgr.reader = self._cr30_reader
        mgr.reading_ready.connect(self._on_reading)
        mgr.ready_to_read.connect(self._on_ready)
        mgr.instrument_detected.connect(self._on_instrument_detected)
        mgr.instrument_disconnected.connect(self._on_disconnected)
        mgr.read_refused.connect(self._on_cr30_refused)
        mgr.magnet_gated.connect(self._on_cr30_magnet)
        mgr.trigger_not_armed.connect(self._on_cr30_trigger_not_armed)
        mgr.session_ended.connect(self._on_session_ended)
        mgr.start(None, self._note)

    def _note(self, text: str) -> None:
        if not text:
            return
        self._log.setVisible(True)
        self._log.appendPlainText(text)
        self._log.ensureCursorVisible()

    def _show_instrument_busy(self, where: str) -> None:
        """M-INSTRUMENT-BUSY. The other half of it lives in the Measure tab."""
        from workflow import measurement_messages as M
        from core import instrument_lease
        title, body = M.M_INSTRUMENT_BUSY.render(
            where=instrument_lease.where_label(where))
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _on_cr30_refused(self, reason: str) -> None:
        """One reading was refused by a guard. The press is lost; the session
        is not — the reader is already waiting for the next one.

        The instrument's own words, unwrapped. They are technical and they stay
        technical: this is the same detail the Measure tab shows in
        M-CR30-READ-FAILED's "{reason}" slot, and wrapping a sentence of my own
        around it here would be new wording in a window, which §M forbids until
        it is approved.
        """
        self._set_status(reason)
        self._note(reason)

    def _on_cr30_magnet(self, reason: str) -> None:
        """M-CR30-MAGNET. A magnet at the aperture is not a refused reading.

        The instrument has ALREADY performed a white calibration against
        whatever it was resting on, so every reading after it would be wrong by
        a factor nothing downstream could see. The session stops, and the only
        two real ways on are to recalibrate or to end it.
        """
        from workflow import measurement_messages as M
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        title, body = M.M_CR30_MAGNET.render(reason=reason)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("The instrument has recalibrated itself"))
        box.setText(title)
        box.setInformativeText(body)
        again = box.addButton(tr("Recalibrate now"),
                              QMessageBox.ButtonRole.AcceptRole)
        stop = box.addButton(tr("Stop session"),
                             QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(again)
        fit_message_box_buttons(box)
        order_message_box_buttons(box, [again, stop])
        box.exec()
        if box.clickedButton() is again and self._run_cr30_calibration(
                keep_bridge=True):
            mgr = self._cr30
            if mgr is not None:
                mgr.start(None, self._note)
                return
        self._end_cr30_session()

    def _on_cr30_trigger_not_armed(self) -> None:
        """M-CR30-TRIGGER-NOT-ARMED, the Measure tab's case reached the other
        way round.

        A reading ChromIQ asks for cannot report the magnet gate, so this
        instrument's learned tile signature is what replaces it — and without
        one there is nothing to replace it with. The instrument's own button
        still works, and still refuses a capped reading on the flag.
        """
        from workflow import measurement_messages as M
        title, body = M.M_CR30_TRIGGER_NOT_ARMED.render()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _end_cr30_session(self) -> None:
        mgr, self._cr30 = self._cr30, None
        if mgr is not None:
            mgr.quit()
            mgr.detach()
        self._close_cr30_bridge()
        self._set_session_running(False)
        self._set_status(tr("Session ended."))

    # --- what the shared calibration windows need from their host --------
    def _start_button_name(self) -> str:
        return tr("Start session")

    def _flash_status(self, text: str, duration_ms: int = 6000) -> None:
        self._set_status(text)

    def _open_cr30_bridge(self) -> None:
        """Stand up the reader, and claim the instrument with it.

        There is no bridge here in the Measure tab's sense — a bridge pairs
        readings with a chart's patch ids, and this window has no chart. The
        name is the shared code's; the reader is the half that matters.
        """
        if self._cr30_reader is not None:
            return
        from core import instrument_lease
        from workflow.cr30.measure_bridge import DeviceReader
        reader = DeviceReader()
        if not instrument_lease.acquire(reader,
                                        instrument_lease.SPOT_TOOL):
            log.warning("the instrument is claimed elsewhere; "
                        "not opening it for the spot window")
            return
        self._cr30_reader = reader
        if self._sound is None:
            from core import sound as _snd
            self._sound = _snd.SoundManager(self._settings)
        self._sound.arm(reading_engine=True)

    def _close_cr30_bridge(self) -> None:
        from core import instrument_lease
        reader, self._cr30_reader = self._cr30_reader, None
        if reader is not None:
            try:
                reader.close()
            except Exception:      # noqa: BLE001 — teardown only
                log.debug("CR30 reader close failed", exc_info=True)
            instrument_lease.release(reader)
        if self._sound is not None:
            self._sound.disarm()

    def _show_cr30_measuring_window(self) -> None:
        """How to measure, once the instrument is calibrated.

        The one window the two hosts do NOT share, and deliberately: the
        Measure tab's version describes a highlighted patch on a chart and
        promises to move to the next one. There is no chart here. This window's
        own Calibration Complete already says what to do, in wording Knut
        settled for exactly this tool, so it is shown instead of a second one
        being invented.
        """
        self._on_calibration_finished()

    # ------------------------------------------------------------------
    # Keyboard: Space is the trigger, and a disabled button never hands the
    # focus to a destructive one
    # ------------------------------------------------------------------
    def _set_read_enabled(self, on: bool) -> None:
        """Enable or disable Take reading WITHOUT throwing the focus at Clear.

        Knut, 2026-09-03: *"pressing spacebar there which is a trigger in
        measure tab closes the read single patches window even in an active
        session."*

        The window never handled a key. What it did was disable the focused
        button: `QWidget::setEnabled(false)` on the focus widget calls
        `focusNextChild()`, which SKIPS every disabled button, so the focus
        walked on to the next enabled one in the bottom row. Measured on the
        real dialog:

        * nothing measured yet — the next enabled button is **Close**, and
          Space closed the window. That is what he reported.
        * readings in the table — **Clear** is enabled by then and catches it
          first, so Space emptied the whole session and left the window open,
          which says nothing at all. That is worse, and it is the one he was
          most likely to hit, because he was measuring.

        Three separate things fix that, and each is worth having on its own:
        this method (the focus never lands on a destructive button), the event
        filter below (Space means "take a reading", as it does in the Measure
        tab), and the guards on Clear and on closing (nothing is lost even if a
        press does get through).
        """
        # ASKED OF THE INSTANCE DICT, for the reason `_on_take_reading` gives
        # below: the misread-recovery tests build this window with `__new__`
        # and never call `__init__`, and on a PyQt wrapper in that state a
        # MISSING attribute raises RuntimeError out of sip, which
        # `getattr(..., default)` does not catch. Those tests hand in a plain
        # stand-in for the button, so the focus half is skipped and the enable
        # half — the part they are about — still runs.
        btn = self.__dict__.get("_read_btn")
        if btn is None:
            return
        table = self.__dict__.get("_table")
        parked = bool(self.__dict__.get("_focus_parked"))
        has_focus = getattr(btn, "hasFocus", None)
        if not on and table is not None and callable(has_focus) and has_focus():
            # The readings table is the one safe parking place in this window:
            # every other focusable widget either ends the session, clears the
            # list or closes the window.
            table.setFocus(Qt.FocusReason.OtherFocusReason)
            self._focus_parked = True
        btn.setEnabled(on)
        # AFTER the enable, never before: a disabled widget cannot take focus,
        # so handing it back first silently did nothing at all.
        if on and parked:
            self._focus_parked = False
            if table is not None and table.hasFocus():
                btn.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:   # noqa: D102
        # SPACE IS THE TRIGGER, HERE TOO.
        #
        # His mental model comes from the Measure tab, where Space takes the
        # reading (`ui/tabs/tab_measure.py`, the CR30 branch of its filter).
        # This window measures the same way with the same instruments, so the
        # key means the same thing — and claiming it is also what stops it
        # reaching a button nobody aimed at.
        #
        # Installed on the application, like the Measure tab's, because a key
        # press goes to the focus widget and a QPushButton swallows Space
        # before any parent sees it. Scoped by ancestry rather than by
        # `isActiveWindow`, which offscreen cannot answer: a child window (a
        # message box, a combo popup) is not an ancestor of this dialog, so its
        # keys are left alone.
        if event.type() != QEvent.Type.KeyPress:
            return False
        if not (obj is self or (isinstance(obj, QWidget) and self.isAncestorOf(obj))):
            return False
        if event.key() != Qt.Key.Key_Space:
            return False
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                | Qt.KeyboardModifier.MetaModifier
                                | Qt.KeyboardModifier.AltModifier):
            return False          # a shortcut is not a trigger
        # A SPACE TYPED INTO A BOX IS A SPACE. The readings table renames a
        # patch in place, and the name may well have one in it.
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
            return False
        if not self._read_btn.isEnabled():
            # Nothing to trigger — the session is not running, or the misread
            # two-step is in its 300 ms gap. Left alone rather than swallowed,
            # so a keyboard user can still work the buttons; Clear and closing
            # carry their own guards.
            return False
        self._on_take_reading()
        return True

    def showEvent(self, event) -> None:   # noqa: N802, D102
        super().showEvent(event)
        # A window shown again is a new session's worth of work to protect.
        self._closing = False
        app = QApplication.instance()
        if app is not None:
            # Qt moves an already-installed filter to the front rather than
            # installing it twice, so a reopened window cannot stack them.
            app.installEventFilter(self)

    def hideEvent(self, event) -> None:   # noqa: N802, D102
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().hideEvent(event)

    def _set_session_running(self, running: bool) -> None:
        self._instrument.setEnabled(not running)
        self._mode.setEnabled(not running)
        self._skip_cal.setEnabled(not running)
        self._start_btn.setText(tr("Stop session") if running else tr("Start session"))
        if not running:
            self._set_read_enabled(False)
            self._apply_reader_capabilities()
            self._refresh_auto_choice()

    def _on_session_ended(self, code: int) -> None:
        self._set_session_running(False)
        self._set_status(tr("Session ended."))

    def _on_ready(self) -> None:
        # spotread's menu prompt is the only proof the error mode is over, so
        # it — not a timer — is what ends the misread state.
        self._misread = False
        self._set_read_enabled(True)
        # Knut, #130 2026-08-01: *"the 'Ready ….' message is inaccurate, as
        # using instrument button is also possible. Revise text."* Both ways of
        # reading are named now.
        self._set_status(tr("Ready — place the instrument on a colour, then "
                            "click Take reading or press the button on the "
                            "instrument."))

    # ------------------------------------------------------------------
    # Misread recovery
    # ------------------------------------------------------------------
    #: How long the "Ready" line stays visible between clearing the error and
    #: taking the reading. Knut asked for 0.3 s so the change is *seen*: without
    #: a pause the two steps collapse into one and the user cannot tell that the
    #: error was cleared at all.
    _MISREAD_CLEAR_PAUSE_MS = 300

    def _on_misread(self) -> None:
        """spotread discarded a reading as inconsistent.

        Knut, #130 2026-08-01: *"if I try to press instrument button nothing
        happens … if I click Take Reading, then the message changes to Ready.
        The misread text is a little lacking in information, as it gives the
        impression that pressing take reading will try again. This is not what
        happens."*

        He was right on both counts. spotread leaves a retry prompt that only a
        keypress clears — the instrument's own button is not read there — so one
        click used to cost the user a reading without saying why. The button now
        does both steps (see :meth:`_on_take_reading`), which is what the text
        always implied, and the text says which control works.
        """
        self._misread = True
        self._set_read_enabled(True)
        self._set_status(tr(
            "Misread — that reading was inconsistent and has been discarded, "
            "usually because the instrument moved while it was measuring. Place "
            "it on the colour again and click Take reading. The button on the "
            "instrument cannot clear this."))

    def _on_take_reading(self) -> None:
        """Take a reading — clearing a misread first, when there is one."""
        # ASKED OF THE INSTANCE DICT, NOT OF THE OBJECT. The misread-recovery
        # tests build this window with `__new__` and never call `__init__`, and
        # on a PyQt wrapper in that state a MISSING attribute raises
        # RuntimeError from sip — which `getattr(..., default)` does not catch,
        # because it only swallows AttributeError. The line below it survives
        # for the opposite reason: `_misread` is one of the attributes those
        # tests do set.
        if self.__dict__.get("_cr30") is not None:
            # ChromIQ asks the instrument itself, which is measurably steadier
            # than pressing its button: the press shifts the reading by about
            # 0.5 %R, ten times the instrument's own repeat noise. There is no
            # misread state to clear — the CR30 refuses a bad reading outright
            # rather than leaving a prompt behind — so none of the two-step
            # recovery below applies.
            self._cr30.take_reading()
            return
        if not getattr(self, "_misread", False):
            self._manager.take_reading()
            return
        # Two keypresses with a visible gap: the first leaves spotread's retry
        # prompt (which is what puts "Ready" on screen), the second is the
        # reading itself. Disabled in between so a second click cannot queue a
        # third keypress and read twice.
        self._set_read_enabled(False)
        self._manager.send_key("\r")

        def _then_read() -> None:
            self._misread = False
            self._set_read_enabled(True)
            self._manager.take_reading()

        QTimer.singleShot(self._MISREAD_CLEAR_PAUSE_MS, _then_read)

    # ------------------------------------------------------------------
    # Readings
    # ------------------------------------------------------------------
    def _on_reading(self, xyz: tuple, lab: tuple) -> None:
        name = tr("Patch {n}").format(n=len(self._readings) + 1)
        reading = SpotReading(name=name, xyz=tuple(xyz), lab=tuple(lab))
        self._readings.append(reading)
        self._append_row(reading)
        self._unsaved = True
        self._save_btn.setEnabled(True)
        self._forget_undo()
        self._set_status(
            tr("Read {name}: L* {l:.1f}  a* {a:.1f}  b* {b:.1f}").format(
                name=name, l=lab[0], a=lab[1], b=lab[2])
        )

    def _append_row(self, r: SpotReading) -> None:
        self._table.blockSignals(True)
        row = self._table.rowCount()
        self._table.insertRow(row)

        name_item = QTableWidgetItem(r.name)
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, 0, name_item)

        vals = (*r.lab, *r.xyz)
        for col, v in enumerate(vals, start=1):
            item = QTableWidgetItem(f"{v:.2f}")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, col, item)

        swatch = QTableWidgetItem(r.hex)
        swatch.setFlags(swatch.flags() & ~Qt.ItemFlag.ItemIsEditable)
        swatch.setBackground(QColor(r.hex))
        swatch.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 7, swatch)

        self._table.blockSignals(False)
        self._table.scrollToBottom()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        row = item.row()
        if 0 <= row < len(self._readings):
            self._readings[row].name = item.text()

    def _selected_rows(self) -> list[int]:
        return sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})

    def _update_average_btn(self) -> None:
        self._avg_btn.setEnabled(len(self._selected_rows()) >= 2)

    def _on_average_selected(self) -> None:
        rows = self._selected_rows()
        if len(rows) < 2:
            return
        averaged = average_readings([self._readings[r] for r in rows], tr("Average"))
        self._readings.append(averaged)
        self._append_row(averaged)
        self._unsaved = True
        self._save_btn.setEnabled(True)
        self._forget_undo()
        self._set_status(
            tr("Averaged {n} readings: L* {l:.1f}  a* {a:.1f}  b* {b:.1f}").format(
                n=len(rows), l=averaged.lab[0], a=averaged.lab[1], b=averaged.lab[2])
        )

    #: What the Clear button says once it can put the readings back.
    def _clear_button_text(self) -> str:
        return tr("Undo clear") if (self._cleared and not self._readings) \
            else tr("Clear")

    def _sync_clear_btn(self) -> None:
        self._clear_btn.setText(self._clear_button_text())
        self._clear_btn.setEnabled(bool(self._readings) or bool(self._cleared))

    def _forget_undo(self) -> None:
        """A new reading replaces what Undo would put back."""
        if self._cleared:
            self._cleared = []
        self._sync_clear_btn()

    def _on_clear(self) -> None:
        """Clear the list, or put back the list that was cleared.

        NOTHING THE USER MADE IS DESTROYED WITHOUT A WAY BACK. This used to
        empty the table on one click with no question and no undo, and the
        spacebar could deliver that click by itself (see `_set_read_enabled`) —
        a whole measuring session gone, in a window that stayed open and said
        nothing. Two answers, because they cover different mistakes: the
        question stops the click that was never meant, and the undo covers the
        one that was meant and regretted.
        """
        if not self._readings and self._cleared:
            restored, self._cleared = self._cleared, []
            for r in restored:
                self._readings.append(r)
                self._append_row(r)
            self._unsaved = True
            self._save_btn.setEnabled(True)
            self._sync_clear_btn()
            self._update_average_btn()
            self._set_status(tr("Readings restored."))
            return
        if not self._readings:
            return
        if not self._confirm_clear():
            return
        self._cleared = list(self._readings)
        self._readings.clear()
        self._table.setRowCount(0)
        self._save_btn.setEnabled(False)
        self._avg_btn.setEnabled(False)
        self._sync_clear_btn()

    def _ask(self, box: QMessageBox):
        """Show a question window and return the button that was pressed.

        ONE SEAM, so a test can answer a modal without patching
        `QMessageBox.exec` for the whole process. That patch has bitten this
        suite twice — `tests/test_qmessagebox_exec_patch_leak.py` exists
        because saving and restoring it does not restore it — and a repeating
        `QTimer` never fires inside a nested `exec()`, so there is no honest
        way to click one from outside. A subclass overrides this, and every
        other line of the window is the real one.
        """
        box.exec()
        return box.clickedButton()

    def _confirm_clear(self) -> bool:
        """M-SPOT-CLEAR — the second look before the list is emptied."""
        from workflow import measurement_messages as M
        title, body = M.M_SPOT_CLEAR.render(n=len(self._readings))
        box = QMessageBox(self)
        set_warning_icon(box)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        clear = box.addButton(tr("Clear"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        return self._ask(box) is clear

    def _suggested_save_path(self) -> "Path":
        """Where a set of spot readings belongs: the current run's exports."""
        from ui.widgets import chromiq_root_dir

        name = "spot-readings.csv"
        try:
            from core.file_manager import FileManager

            fm = getattr(self, "_file_mgr", None)
            if fm is not None and getattr(fm, "has_project", lambda: False)():
                run = fm.project().current_run()
                exports = getattr(run, "exports", None)
                if exports is not None:
                    return Path(exports) / name
                return Path(run.dir) / name
        except Exception:      # noqa: BLE001 — a suggestion is never worth a crash
            pass
        return chromiq_root_dir() / name

    def _on_save(self) -> bool:
        """Write the readings out. Returns whether anything reached disk.

        The answer is load-bearing now: the close guard offers Save as one of
        its three ways out, and a save the user backed out of must leave the
        window open rather than close it on the readings it did not write.
        """
        if not self._readings:
            return False
        from ui.widgets import save_file_dialog
        # SAVE IT BESIDE THE THING IT DESCRIBES. This pointed at
        # `~/spot-readings/`, a folder nothing in ChromIQ ever creates — the
        # string appeared exactly once in the whole tree, at this line — so the
        # dialog was handed a directory that was not there. A spot reading
        # belongs to the run being worked on, so its `exports/` is the honest
        # default, and the ChromIQ folder is the fallback when nothing is open.
        start = self._suggested_save_path()
        chosen = save_file_dialog(
            self, tr("Save spot readings"), tr("Spot readings (*.csv)"),
            start_path=str(start))
        if not chosen:
            return False
        # A typed save name is a NAME: "readings.v2" has no extension to strip
        # (core/stem_paths.py). Remove only a .csv/.ti3 the user actually typed.
        base = without_ext(without_ext(chosen, ".csv"), ".ti3")
        try:
            csv_path = write_csv(artefact(base, ".csv"), self._readings)
            ti3_path = write_ti3(artefact(base, ".ti3"), self._readings)
        except OSError as exc:
            QMessageBox.warning(self, tr("Save failed"), str(exc))
            return False
        self._unsaved = False
        QMessageBox.information(
            self, tr("Saved"),
            tr("Readings saved to:\n{csv}\n{ti3}").format(
                csv=csv_path.name, ti3=ti3_path.name),
        )
        return True

    # ------------------------------------------------------------------
    # Calibration + error pop-ups
    # ------------------------------------------------------------------
    def _on_instrument_detected(self, model: str) -> None:
        """Remember what spotread says is attached (#130, Knut 2026-07-31)."""
        self._detected_instrument = model or ""
        log.info("spot read: instrument reported as %s", model)

    def _instrument_family(self) -> "str | None":
        """Which instrument's wording to use, or None for the generic text.

        Knut, #130 2026-07-31: *"one window for each instrument, wired to the
        detection of each instrument type during connection, so that the window
        shows correct text for each instrument."*

        spotread does not announce its model in anything ChromIQ parses, and
        inventing a pattern for output I have not seen is how four wrong theories
        about Save Partial happened. What IS known is the instrument the user has
        chosen in ChromIQ — the same value the Measure tab compares a chart
        against — and his own log confirms spotread is launched with the device
        ChromIQ picked. So the wording follows that, and falls back to the
        generic text whenever it is unset or unrecognised, which is exactly what
        the SpectroScan and any unknown instrument should get anyway.
        """
        try:
            from ui.ti2_loader import instrument_family
            # What spotread actually found beats what the chart was made for:
            # the whole point is describing the device in the user's hand.
            found = getattr(self, "_detected_instrument", "") or ""
            return (instrument_family(found) if found else
                    instrument_family(str(self._settings.get("chart_instrument", "") or "")))
        except Exception:      # noqa: BLE001 — wording must never break a read
            return None

    # ------------------------------------------------------------------
    # The drawn instrument, in the windows that ask for a physical move
    # ------------------------------------------------------------------
    def _dial_column(self, dlg: QDialog, lay: QVBoxLayout,
                     position: str) -> QVBoxLayout:
        """Put the ColorMunki dial beside this window's text, and return the
        layout the text belongs in.

        THE MEASURE TAB HAS HAD THIS SINCE 2026-09-01 AND THIS TOOL HAD NOT.
        The owner used Read single patches on real hardware on 2026-09-02 and
        said so: *"i noticed it did not use the nice graphics to help the user
        during calibration (calibration position and measurement position)."*
        Every window here that asks him to turn the dial now shows the same
        drawing the Measure tab shows for the same instruction, so the two
        places read as one instrument rather than two different products.

        Same rules as the Measure tab's copy, and they are not cosmetic:

        * **Only the ColorMunki family.** The drawing is a ColorMunki's dial.
          An i1Pro has no wheel to point at and keeps the words alone, which is
          what `ui/dial_pictogram.py` was built for and what its docstring says.
        * **Nothing sits under the picture.** The picture takes a column of its
          own and every line of text takes the column beside it, so the text
          starts on one left edge instead of stepping back under the wheel
          (Basti, 2026-09-01).
        * `position` is "calibrate" (the gear) or "measure" (the target mark) —
          the same wheel turned two ways, so the windows read as one movement
          of one physical thing.

        Nothing is redrawn here. `dial()` is the drawing he approved over a
        dozen rounds at the instrument; this only places it.
        """
        if self._instrument_family() != "colormunki":
            return lay
        try:
            from ui.dial_pictogram import dial
        except Exception:      # noqa: BLE001 — a picture is never worth a crash
            log.debug("could not draw the instrument dial", exc_info=True)
            return lay
        dlg.setMinimumWidth(620)
        pic = QLabel(dlg)
        pic.setPixmap(dial(position, dlg, 150))
        pic.setAlignment(Qt.AlignmentFlag.AlignTop)
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addWidget(pic, 0, Qt.AlignmentFlag.AlignTop)
        text_col = QVBoxLayout()
        text_col.setSpacing(16)
        row.addLayout(text_col, 1)
        lay.addLayout(row)
        return text_col

    def _on_calibration_position_wrong(self) -> None:
        """The calibration was asked for again — the instrument was not ready.

        Knut, #130 2026-07-31: he left the dial in measurement mode, pressed
        Start Calibration, *"got no warning that instrument was in wrong mode,
        and window disappeared and the main Read Single Patches window now says
        'Calibrating...' and is stuck … Had to stop session."*

        spotread simply re-prints its prompt in that case, which is what this
        reacts to. The window is deliberately general: only some instruments
        have a dial to turn, so it says what is needed without claiming every
        device works the same way.
        """
        self._set_status(tr("Waiting — the instrument is not in its calibration position."))
        if getattr(self, "_cal_pos_open", False):
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Instrument Not Ready to Calibrate"))
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        outer = lay          # the buttons stay on the dialog, not in the text column
        lay = self._dial_column(dlg, lay, "calibrate")
        msg = QLabel(
            tr("<b>The calibration cannot start yet — the instrument is not in "
               "its calibration position.</b><br><br>")
            # The shared instructions end with "then click Start Calibration",
            # which is the Measure tab's button, not this window's. Knut caught
            # it (#130, 2026-08-01) — the same fault as naming "Read patch"
            # earlier, so the trailing call to action is dropped here and this
            # window names its own button. He also asked for the reassurance
            # sentence to go; it was padding.
            + _without_call_to_action(
                calibration_instructions_html(self._instrument_family()))
            + tr("<br><br>Put the instrument in position, then click "
                 "<b>Try again</b>."),
            dlg,
        )
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(msg)
        box = QDialogButtonBox(dlg)
        again = box.addButton(tr("Try again"), QDialogButtonBox.ButtonRole.AcceptRole)
        again.setObjectName("primary")
        box.addButton(tr("Cancel session"), QDialogButtonBox.ButtonRole.RejectRole)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        outer.addWidget(box)
        tint_dialog_primary(dlg, _ACCENT)
        self._cal_pos_open = True
        try:
            accepted = dlg.exec() == QDialog.DialogCode.Accepted
        finally:
            self._cal_pos_open = False
        if accepted:
            self._manager.send_key("\r")          # re-try the calibration
            self._set_status(tr("Calibrating…"))
        else:
            self._manager.send_key("\x1b")        # leave spotread cleanly

    def _on_sensor_wrong_position(self) -> None:
        """Say — properly — that the instrument is not in its reading position.

        Knut, #130 2026-07-31 (item 5): with the dial still on calibration,
        *"the instrument button and Take Reading button registers ('Ready...'
        text blinks), but nothing happens"*, and he asked for what patch-by-patch
        does: *"a window saying 'The patch could not be read: Sensor should be
        in surface position', then Retry button."*

        This used to set a line of status text only, which is easy to miss while
        you are looking at the instrument rather than the screen.
        """
        self._set_status(tr("Instrument is in the wrong position."))
        if getattr(self, "_sensor_pos_open", False):
            return          # one window, however many times it is reported
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Instrument in the Wrong Position"))
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        outer = lay          # the buttons stay on the dialog, not in the text column
        lay = self._dial_column(dlg, lay, "measure")
        msg = QLabel(
            tr("<b>That reading could not be taken — the instrument is not in "
               "its measuring position.</b><br><br>"
               "On most instruments this means the dial or head is still set to "
               "calibration. Turn it back to the measuring position, place the "
               "instrument on the colour you want to read, and try again."),
            dlg,
        )
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(msg)
        box = QDialogButtonBox(dlg)
        again = box.addButton(tr("Try again"), QDialogButtonBox.ButtonRole.AcceptRole)
        again.setObjectName("primary")
        box.accepted.connect(dlg.accept)
        outer.addWidget(box)
        tint_dialog_primary(dlg, _ACCENT)
        self._sensor_pos_open = True
        try:
            dlg.exec()
        finally:
            self._sensor_pos_open = False

    def _on_calibration_finished(self) -> None:
        """Say that the calibration is done — and what to do with the device now.

        Knut, #130 2026-07-30: *"When I complete the calibration, there is no
        infomation window that calibration is done and to turn the unit back to
        measure mode."* Patch-by-patch mode has said this for a while; single
        patches went straight back to a ready button with the instrument still
        sitting on its calibration tile.

        Deliberately shorter than the Measure tab's version: he also said
        *"parts of the calibration complete window is not relevant for read
        single patches tool"*, and the parts about strips and charts are exactly
        those, so they are left out.
        """
        # Knut, #130 2026-07-31 (item 4): *"Before pressing Start Calibration in
        # the Calibration Complete window, I press the instrument button. That
        # results in another Calibration Complete window to appear on top of the
        # previous, every time I click the button."* Each press makes spotread
        # print its ready prompt again, and each one opened another window.
        if getattr(self, "_cal_done_open", False):
            return
        self._set_read_enabled(True)
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Calibration Complete"))
        from ui.ti2_loader import spot_measurement_instructions_html
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        outer = lay          # the buttons stay on the dialog, not in the text column
        lay = self._dial_column(dlg, lay, "measure")
        msg = QLabel(
            # Knut, #130 2026-07-31, on the first version of this text: *"The
            # text mentions 'Take it off the calibration tile', which does not
            # exist for this instrument … the button in the Read Single Patches
            # window is called Take Reading."* Both were mine and both were
            # wrong: a ColorMunki is turned by a dial, and no button here has
            # ever been called "Read patch". Named after what is actually on
            # screen, and worded for any instrument until the per-instrument
            # texts he asked for are wired to device detection.
            tr("<b>Your instrument is calibrated and ready.</b><br><br>")
            + spot_measurement_instructions_html(self._instrument_family())
            # Knut's own wording (#130, 2026-08-01): the old text described only
            # the instrument's side button, which is one of two ways to read and
            # not the one on screen. Both are named now.
            + tr("<br><br>Use <b>Take reading</b> for each measurement, or press "
                 "and hold the side button on the instrument, then hold still "
                 "until the reading is taken.<br><br>"
                 "The instrument stays calibrated for the whole session, so you "
                 "will not be asked again unless it needs it."),
            dlg,
        )
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(msg)
        box = QDialogButtonBox(dlg)
        ok = box.addButton(tr("Start Reading"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("primary")
        box.accepted.connect(dlg.accept)
        outer.addWidget(box)
        tint_dialog_primary(dlg, _ACCENT)
        self._cal_done_open = True
        try:
            dlg.exec()
        finally:
            self._cal_done_open = False

    def _on_calibration_prompt(self) -> None:
        # Same wording as the Measure tab's calibration pop-up — generic but
        # clear — with the strip-specific tail swapped for a spot-read one.
        self._set_read_enabled(False)
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Calibration Required"))
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)

        # The same per-instrument instructions patch-by-patch has always shown
        # (Knut asked for exactly that); generic wording when the instrument is
        # unknown.
        from ui.ti2_loader import calibration_instructions_html
        outer = lay          # the buttons stay on the dialog, not in the text column
        lay = self._dial_column(dlg, lay, "calibrate")
        msg = QLabel(calibration_instructions_html(self._instrument_family()), dlg)
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(msg)

        box = QDialogButtonBox(dlg)
        ok = box.addButton(tr("Start Calibration"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("primary")
        # Knut, #130 2026-07-31 (item 2): *"the Calibration Required window is
        # lacking a Cancel Measurement button, like used in patch-by-patch mode
        # … There should be a chance to change my mind and exit the measurement
        # session."* Without it the only way out was the Stop session button
        # behind the window.
        cancel = box.addButton(tr("Cancel session"),
                               QDialogButtonBox.ButtonRole.RejectRole)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        outer.addWidget(box)

        tint_dialog_primary(dlg, _ACCENT)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._manager.send_key("\r")
            self._set_status(tr("Calibrating…"))
        else:
            # Dismissed — exit spotread cleanly.
            self._manager.send_key("\x1b")

    def _on_no_instrument(self) -> None:
        """Knut, 2026-08-13: Read Single Patches failed to see his ColorMunki
        on a 2019 MacBook exactly as the measurement did, and "Faster
        instrument connection" was the cause. So this window names the same
        shortcut and carries the same switch as the measurement's
        no-instrument window, rather than the bare "connect it and try again"
        it used to show."""
        self._set_status(tr("No instrument detected."))
        # ONE WINDOW, HOWEVER MANY TIMES IT IS REPORTED — the same guard its
        # four siblings in this file already carry, and the same one the
        # Measure tab keeps as `_no_instrument_shown`. spotread can print the
        # line more than once (an instrument that drops off the bus reports it
        # every retry), and each match opened another modal on top of the
        # unanswered one. Knut has reported that shape twice, #130 2026-07-31
        # for this window's siblings and again for the Measure tab's.
        if getattr(self, "_no_instrument_open", False):
            return
        fast_on = bool(self._settings.get("fast_instrument_connect", True))
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("No instrument detected"))
        box.setText(tr("No measuring instrument was found."))
        if fast_on:
            box.setInformativeText(tr(
                "Check that the instrument is plugged in, try a different USB "
                "port and plug straight into the computer rather than through "
                "a hub, and close any other program that may be holding it.\n\n"
                "If it still is not found, the likeliest cause on an older "
                "computer is a shortcut ChromIQ uses called “Faster "
                "instrument connection”: it skips the ports an instrument is "
                "never plugged into, and on some computers that is what stops "
                "the instrument being seen at all. The button below turns it "
                "off straight away. Try again afterwards. You can switch it "
                "back on whenever you like in Preferences ▸ Measurement."))
            # ResetRole keeps OK on the right (Sebastian), as in the same
            # window in the Measure tab.
            turn_off = box.addButton(tr("Turn off faster connection"),
                                     QMessageBox.ButtonRole.ResetRole)
        else:
            turn_off = None
            box.setInformativeText(tr(
                "Check that the instrument is plugged in, try a different USB "
                "port and plug straight into the computer rather than through "
                "a hub, and close any other program that may be holding it."))
        box.addButton(tr("OK"), QMessageBox.ButtonRole.AcceptRole)
        self._no_instrument_open = True
        try:
            box.exec()
        finally:
            self._no_instrument_open = False
        if turn_off is not None and box.clickedButton() is turn_off:
            self._settings.set("fast_instrument_connect", False)
            log.info("Read single patches: faster instrument connection "
                     "switched OFF at the user's request")

    def _on_device_busy(self) -> None:
        self._set_status(tr("Instrument is in use by another program."))
        QMessageBox.warning(
            self, tr("Instrument busy"),
            tr("The instrument is being used by another program. Close it and try again."),
        )

    def _on_disconnected(self) -> None:
        self._set_status(tr("Instrument disconnected."))

    def _on_init_failed(self, detail: str) -> None:
        self._set_status(tr("Could not start the instrument: {detail}").format(detail=detail))

    # ------------------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    def _release_instrument(self) -> None:
        """End the session and let go of the shared runner (#145).

        Both closing routes come through here. The detach is the important
        half: the process is killed at once, but the reader thread can still
        report the exit a moment later, and by then this window and its
        manager may be gone. Knut's app died exactly there after his
        ColorMunki dropped off the USB bus over and over.
        """
        if self._manager.is_running:
            self._manager.quit()
            self._manager.abort()
        self._manager.detach()
        # …and the same for ChromIQ's own reader, which has no process to kill
        # and would otherwise be left holding the instrument — over Bluetooth,
        # a CR30 that accepts one connection at a time and has stopped
        # advertising to everybody else.
        cr30, self._cr30 = self._cr30, None
        if cr30 is not None:
            cr30.quit()
            cr30.detach()
        self._close_cr30_bridge()

    def _may_close(self) -> bool:
        """M-SPOT-UNSAVED — ask before a whole session goes out with the window.

        `self._readings` is in memory and nowhere else; the only thing that
        writes it out is Save. Until now Close, the red window button and
        Escape all went straight to `_release_instrument` and out, so a
        measuring session could be binned without a word by any of the three.
        """
        # ASKED ONCE, HOWEVER THE WINDOW IS CLOSED.
        #
        # `QDialog::closeEvent` CALLS `reject()`, so the red window button
        # reaches this twice: once from `closeEvent` and once from the reject
        # that Qt raises out of it. Found by driving the real window on screen,
        # 2026-09-03 — the second question had nobody left to answer it and the
        # app simply stopped. The offscreen tests never saw it, because
        # answering "Cancel" stops at the first window and `reject()` on its own
        # only reaches this once.
        if self._closing:
            return True
        if not self._readings or not self._unsaved:
            return True
        from workflow import measurement_messages as M
        title, body = M.M_SPOT_UNSAVED.render(n=len(self._readings))
        box = QMessageBox(self)
        set_warning_icon(box)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        save = box.addButton(tr("Save"), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr("Discard"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        clicked = self._ask(box)
        if clicked is discard:
            self._closing = True
            return True
        if clicked is save:
            self._closing = bool(self._on_save())
            return self._closing
        assert clicked is cancel or clicked is None
        return False

    def reject(self) -> None:  # noqa: D102
        if not self._may_close():
            return
        self._release_instrument()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._may_close():
            event.ignore()
            return
        self._release_instrument()
        super().closeEvent(event)
