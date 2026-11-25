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
from PyQt6.QtGui import QColor, QPen
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
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.i18n import decimal_text, tr
from ui.cr30_calibration import Cr30CalibrationMixin
from ui.dialogs.tools_dialogs import _indicator_color, _popup_pair, neutral_controls_qss
from ui.styles import SPEC_GREEN
from ui.tab_header import dialog_masthead
from ui.warning_sign import inform, set_warning_icon, warn
from ui.widgets import (NoScrollComboBox, TailFollowLog, reserve_button_labels,
                        set_ink, tint_dialog_primary)
from workflow.spot_read_io import (MixedConditions, SpotReading, average_readings,
                                   write_csv, write_ti3_files)
from workflow.spot_read_manager import SpotReadManager, SpotReadParams, is_i1pro3
from workflow.helper_spot_manager import HelperSpotManager, HelperSpotParams

import logging
import re

from ui.ti2_loader import calibration_instructions_html

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

_ACCENT = "#56d6a5"   # share the Measure tab's accent — this is measurement work

#: The list and the notes under it share a splitter. Neither may be dragged
#: smaller than these: the list keeps its heading and two readings, the notes
#: two lines (the app's own floor for a log, `ui.widgets.LOG_MIN_LINES`).
_MIN_LIST_ROWS = 2
_MIN_LOG_LINES = 2
#: The height the notes get when they first appear; after that, the user's.
_INITIAL_LOG_LINES = 4
#: How many readings the list shows at the window's default size, with the
#: notes open at their first height (Basti's beta-17 hand test: "about 7").
_DEFAULT_LIST_ROWS = 7
#: What a macOS title bar adds above the window's own height.
_TITLE_BAR = 32


def _ink_on(hex_colour: str) -> str:
    """The text colour that reads on a swatch of *hex_colour*: near-black on a
    light swatch, white on a dark one, whichever has the higher contrast.

    The hex code is written ON its own colour, so the window's ink colour
    cannot be used: white on a pale swatch and black on #34312e (Basti's
    beta-17 hand test) both vanish.
    """
    c = QColor(hex_colour)
    if not c.isValid():
        return "#0a0a0a"

    def _lin(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    lum = (0.2126 * _lin(c.redF()) + 0.7152 * _lin(c.greenF())
           + 0.0722 * _lin(c.blueF()))
    dark = 0.0030   # relative luminance of #0a0a0a
    on_dark = (lum + 0.05) / (dark + 0.05)
    on_white = 1.05 / (lum + 0.05)
    return "#0a0a0a" if on_dark >= on_white else "#ffffff"



class _SwatchCellDelegate(QStyledItemDelegate):
    """The Colour cell keeps its own colour when its row is selected.

    The row's selection fill used to cover the swatch too, so the selected
    reading's colour was the one colour the list did not show (#d43d49 came
    up green; review of beta 17's hand-test fixes). The cell is painted as if
    unselected, swatch and contrast ink intact, and the selection is drawn as
    a frame in the selection colour around it, so the band across the row
    still runs through the cell.
    """

    _FRAME = 3

    def __init__(self, frame_colour: str, parent=None) -> None:
        super().__init__(parent)
        self._frame_colour = QColor(frame_colour)

    def initStyleOption(self, option, index) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_Selected

    def paint(self, painter, option, index) -> None:  # noqa: D102
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        super().paint(painter, option, index)
        if not selected:
            return
        painter.save()
        pen = QPen(self._frame_colour)
        pen.setWidth(self._FRAME)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        half = self._FRAME // 2
        painter.drawRect(option.rect.adjusted(half, half, -half - 1, -half - 1))
        painter.restore()

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

#: Item 43: the measurement conditions the row offers an i1Pro 3, in list
#: order, with the -F value whose entry (already in the Measure tab's
#: "Spectral filter type (-F)" list, and translated) names each.
_CONDITION_KEYS = ("M0", "M1", "M2")
_CONDITION_FILTER_CODES = {"M0": "n", "M1": "5", "M2": "u"}
#: where the chosen condition is remembered (across sessions and app runs)
_CONDITION_SETTING = "spot_read_condition"


def _instrument_labels() -> "list[str]":
    return [tr("Detect automatically"),
            tr("Any ArgyllCMS instrument"),
            tr("CR30")]


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


def usb_fingerprint_now() -> "tuple | None":
    """What the label's 2-second tick asks: did anything on USB change?

    `core.argyll_instruments.usb_fingerprint`, an in-process read of the
    operating system's USB list (macOS: IOKit, about 0.03 ms). It starts no
    program, so no `ioreg` and never an ArgyllCMS tool, opens no device and
    touches no serial port and no Bluetooth. Only when the answer changes does
    the window ask the full question (:meth:`SpotReadDialog._automatic_reader`,
    an `ioreg` run of 25 to 40 ms). Module level so a test can plug a device in.
    """
    try:
        from core.argyll_instruments import usb_fingerprint
        return usb_fingerprint()
    except Exception:      # noqa: BLE001 — a change detector, never an error
        log.debug("could not fingerprint the USB devices", exc_info=True)
        return None

#: Item 43: the help of the Measurement condition row (its tooltip and its
#: (i) button). Plain words for each condition, and the one rule the row has.
_CONDITION_HELP = tr(
    "Which light the i1Pro 3 measures each colour with. It can measure the "
    "same patch in three ways, called M0, M1 and M2 (an ISO standard).\n\n"
    "M0: the instrument's own lamp, as it is. This is how ChromIQ has always "
    "measured here, and how most profiles are measured.\n\n"
    "M1: light like daylight, with its ultraviolet part. Paper brighteners "
    "and fluorescent inks glow as they do in daylight, so a bright white "
    "paper reads a little bluer and brighter than in M0.\n\n"
    "M2: the ultraviolet part left out. Brighteners do not glow at all, so "
    "you see the paper and the inks without that glow.\n\n"
    "Choose the condition before you click Start session. Every reading of "
    "the session is taken in it, and the list shows it beside each reading. "
    "To measure in another condition, stop the session, choose it here and "
    "start again. Saving writes one .ti3 file per condition, so readings of "
    "different conditions are never mixed, and Average selected only "
    "averages readings of one condition.")


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


def _calibration_tip_html() -> str:
    """M-SPOT-CAL-TIP, for the rich-text Calibration Complete window."""
    import html as _html
    from workflow import measurement_messages as M
    return _html.escape(M.M_SPOT_CAL_TIP.render()[1])


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
        #: Item 43 steps 2-3: the two ArgyllCMS readers. stock spotread (one
        #: condition per reading) and ChromIQ's own spot session, which keeps
        #: M0, M1 and M2 of every reading (an i1Pro 3 with the conditions
        #: Beta, an i1Pro 2 with the dual scan Beta). Both have the same
        #: signals; `_manager` is the one the running (or last) session uses.
        self._spotread = self._manager
        self._helper_mgr = HelperSpotManager(runner, self)
        #: every condition of the reading whose `reading_ready` comes next
        self._pending_conds: "dict | None" = None
        #: shown once above the Ready line of a session (item 43 steps 2-3)
        self._session_note = ""
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
        #:
        #: Each tick asks only whether the USB device list CHANGED
        #: (`usb_fingerprint_now`, in process, no program started); the full
        #: question, which runs `ioreg`, is asked only when it did. Runs while
        #: the window is shown and no session owns the instrument.
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(2000)
        self._auto_timer.timeout.connect(self._on_auto_tick)
        #: The USB list the label was last worked out against.
        self._usb_fingerprint: "tuple | None" = None
        self._readings: list[SpotReading] = []
        #: What the last Clear took away, kept so it can be put back. Nothing
        #: the user made is destroyed without a way back; see `_on_clear`.
        self._cleared: list[SpotReading] = []
        #: The patch number the last automatic name used. Names are never
        #: re-used: deleting "Patch 2" of three makes the next reading
        #: "Patch 4", not a second "Patch 3".
        self._patch_counter = 0
        #: What each Delete took away, newest last, as (row, reading) pairs,
        #: so "Undo delete" and Cmd+Z put them back where they were. Forgotten
        #: by the next reading, like the Clear undo.
        self._deleted: "list[list[tuple[int, SpotReading]]]" = []
        #: The counter Clear wiped, kept with `_cleared` for its undo.
        self._cleared_counter = 0
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
        #: True between "Calibrate again" (item 41) and the ready prompt that
        #: lets the calibration key through (see :meth:`_on_ready`).
        self._recalibrate_pending = False

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
        self._outer = outer

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

        # --- Measurement condition (item 43) ------------------------------
        # ONE ROW, ONLY FOR AN i1PRO 3. Its driver computes M0, M1 and M2 from
        # every reading (lamp and UV light in turn) and stock spotread -F
        # chooses which one comes back. Nothing else ArgyllCMS drives can do
        # that, so for every other instrument the row is not there and the
        # command line and the saved files are the ones they always were.
        # Default M0, the instrument's normal light.
        self._cond_row = QWidget(self)
        self._cond_row.setObjectName("spotConditionRow")
        cond_lay = QHBoxLayout(self._cond_row)
        cond_lay.setContentsMargins(0, 0, 0, 0)
        cond_lay.setSpacing(10)
        cond_lay.addWidget(QLabel(tr("Measurement condition"), self._cond_row))
        self._condition = NoScrollComboBox(self._cond_row)
        from workflow.measurement_condition import filter_choice_label
        for _key in _CONDITION_KEYS:
            self._condition.addItem(
                filter_choice_label(_CONDITION_FILTER_CODES[_key]), _key)
        _stored_cond = str(settings.get(_CONDITION_SETTING, "M0") or "M0")
        self._condition.setCurrentIndex(
            _CONDITION_KEYS.index(_stored_cond)
            if _stored_cond in _CONDITION_KEYS else 0)
        self._condition.setToolTip(_CONDITION_HELP)
        self._condition.currentIndexChanged.connect(self._on_condition_changed)
        cond_lay.addWidget(self._condition)
        cond_lay.addWidget(TooltipButton(
            tr("About the measurement condition"), _CONDITION_HELP,
            self._cond_row, color=_ACCENT))
        cond_lay.addStretch(1)
        self._cond_row.setVisible(False)
        outer.addWidget(self._cond_row)
        # Item 43 steps 2-3: an i1Pro (2) with the conditions Beta on and the
        # dual scan off gets one line saying where M1 and M2 are switched on
        # (study 2.1); everything else never sees it.
        from workflow import measurement_messages as _MM
        self._dual_hint = QLabel(_MM.M_SPOT_DUAL_HINT.render()[0], self)
        self._dual_hint.setObjectName("spotDualHint")
        self._dual_hint.setWordWrap(True)
        self._dual_hint.setToolTip(_MM.M_SPOT_DUAL_HINT.render()[1])
        set_ink(self._dual_hint, "#909090", level="dim")
        self._dual_hint.setVisible(False)
        outer.addWidget(self._dual_hint)
        #: The condition the running session reads under ("M0", "M1", "M2"),
        #: or None: not an i1Pro 3, not reflective, or not known yet.
        self._session_condition: "str | None" = None
        #: The USB list the row was last decided against (_on_auto_tick).
        self._cond_fingerprint: "tuple | None" = None
        self._mode.currentIndexChanged.connect(self._on_mode_changed)

        self._status = QLabel(tr("Idle — click Start session to begin."), self)
        self._status.setWordWrap(True)
        set_ink(self._status, "#909090", level="faint")
        outer.addWidget(self._status)

        # --- Show the readings in (item 43 steps 2-3) ----------------------
        # ONLY WHILE A READING IN THE LIST KEEPS SEVERAL CONDITIONS. ChromIQ's
        # own spot session keeps M0, M1 and M2 of every reading; this switches
        # the whole list between them without measuring again. A reading
        # that has only one condition keeps showing its own.
        self._view_row = QWidget(self)
        self._view_row.setObjectName("spotViewRow")
        view_lay = QHBoxLayout(self._view_row)
        view_lay.setContentsMargins(0, 0, 0, 0)
        view_lay.setSpacing(10)
        view_lay.addWidget(QLabel(tr("Show the readings in"), self._view_row))
        self._view = NoScrollComboBox(self._view_row)
        for _key in _CONDITION_KEYS:
            self._view.addItem(
                filter_choice_label(_CONDITION_FILTER_CODES[_key]), _key)
        self._view.setToolTip(tr(
            "Every reading of this list keeps M0, M1 and M2. Choose which one "
            "the list shows; nothing is measured again. A reading taken with "
            "one condition only keeps showing that one."))
        self._view.currentIndexChanged.connect(self._on_view_changed)
        view_lay.addWidget(self._view)
        view_lay.addStretch(1)
        self._view_row.setVisible(False)
        outer.addWidget(self._view_row)

        # --- Results table -------------------------------------------------
        self._table = QTableWidget(0, 9, self)
        self._table.setHorizontalHeaderLabels([
            tr("Name"), tr("L*"), tr("a*"), tr("b*"),
            tr("X"), tr("Y"), tr("Z"), tr("Colour"),
            tr("Condition"),
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
        # Item 43: the condition each reading was taken under ("M1"), shown
        # only once a reading has one; for every other list it is not there.
        hdr.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnHidden(8, True)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(self._update_average_btn)
        # A reading can be deleted from where it is: right-click, as well as
        # the Delete button and the Backspace / Delete keys (eventFilter).
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_menu)

        # THE LIST AND THE NOTES SHARE ONE COLUMN, AND THE USER SETS THE
        # DIVIDE (Basti's beta-17 hand test: the notes "take a lot of space").
        # A splitter, neither side collapsible: the list keeps its heading and
        # two readings, the notes two lines. Not remembered across openings,
        # because this window does not remember its size either.
        self._split = QSplitter(Qt.Orientation.Vertical, self)
        self._split.setObjectName("spotListLogSplit")
        self._split.setChildrenCollapsible(False)
        self._split.setHandleWidth(8)
        self._split.addWidget(self._table)
        self._table.setMinimumHeight(self._rows_height(_MIN_LIST_ROWS))
        #: True once the notes have been given their first height; after that
        #: the divide is the user's.
        self._log_sized = False
        outer.addWidget(self._split, 1)

        # --- Session notes -------------------------------------------------
        # The same status pane every other tool window carries
        # (`_ToolDialogBase`), down to its placeholder. HIDDEN UNTIL THERE IS
        # SOMETHING IN IT: the ArgyllCMS session has never written here and
        # must not start to, so for everybody else this window is exactly the
        # window it was. The CR30's calibration writes the notes that matter —
        # which way it connected, what the dark reference read back at — and
        # they have to be readable somewhere.
        self._log = TailFollowLog(self._split)
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setMinimumHeight(self._log_lines_height(_MIN_LOG_LINES))
        self._log.setPlaceholderText(tr("Status messages will appear here."))
        self._log.setVisible(False)
        self._split.addWidget(self._log)
        self._split.setStretchFactor(0, 1)
        self._split.setStretchFactor(1, 0)

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

        # Item 41 (4.3.60): a way to calibrate again in the middle of a
        # session. ArgyllCMS can accept a calibration that was too weak, and
        # the person may only notice later (the bare paper reads lighter than
        # it used to); stopping and starting the session again does not help
        # with "Skip initial calibration" ticked. Sends spotread's own
        # calibration key; the usual Calibration Required window follows.
        self._cal_btn = QPushButton(tr("Calibrate"), self)
        self._cal_btn.setEnabled(False)
        self._cal_btn.setToolTip(tr(
            "Calibrate the instrument again without ending the session, for "
            "example when the bare paper reads lighter than it used to."))
        self._cal_btn.clicked.connect(self._calibrate_again)
        bottom.addWidget(self._cal_btn)

        self._avg_btn = QPushButton(tr("Average selected"), self)
        self._avg_btn.setEnabled(False)
        self._avg_btn.setToolTip(
            tr("Select two or more readings, then average them into a new entry.")
        )
        self._avg_btn.clicked.connect(self._on_average_selected)
        bottom.addWidget(self._avg_btn)

        self._del_btn = QPushButton(tr("Delete"), self)
        self._del_btn.setEnabled(False)
        self._del_btn.setToolTip(tr(
            "Delete the selected readings. The Backspace and Delete keys do "
            "the same while the list has the focus, and Undo delete puts "
            "them back."))
        self._del_btn.clicked.connect(self._on_delete_button)
        bottom.addWidget(self._del_btn)

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
        self._close_btn = close_btn

        outer.addLayout(bottom)
        #: The button row, and whether Save / Close were moved to a second
        #: row because the whole row is wider than the screen (_settle_size).
        self._bottom = bottom
        self._row_wrapped = False

        # THREE BUTTONS CHANGE THEIR WORDS, SO EACH IS AS WIDE AS ITS LONGEST.
        # Fitted to "Delete" when the window opened, the button then painted
        # "Undo delete" into that width ("NDO DELET", Basti's beta-17 hand
        # test). Reserving every label also keeps the row from shifting.
        reserve_button_labels(self._start_btn,
                              (tr("Start session"), tr("Stop session")))
        reserve_button_labels(self._del_btn, (tr("Delete"), tr("Undo delete")))
        reserve_button_labels(self._clear_btn, (tr("Clear"), tr("Undo clear")))

        # Neutral indicators, but the dropdown wears this tool's own green…
        #
        # …AND SO DO THE LIST'S SELECTED ROW AND ITS RIGHT-CLICK MENU. Both
        # wore the appearance's own selection colour, blue in Light and cyan
        # in Dark, which belongs to no window (Basti's beta-17 hand test). The
        # same pair the dropdown's hovered row uses, so all three agree, and
        # the main window's rule for a tab's lists (`_apply_tab_widget_styling`):
        # only the two selection properties, nothing else of the sheet moves.
        _sel_bg, _sel_fg = _popup_pair(_ACCENT)
        # The Colour cell is the reading itself: selected, it keeps its own
        # colour and shows the selection as a frame (_SwatchCellDelegate).
        self._table.setItemDelegateForColumn(
            7, _SwatchCellDelegate(_sel_bg, self._table))
        self.setStyleSheet(
            neutral_controls_qss(_indicator_color(settings), popup=_ACCENT)
            + f"QTableView, QMenu {{ selection-background-color: {_sel_bg};"
              f" selection-color: {_sel_fg}; }}")
        # Tint the Start button with the Measure tab's green accent — this tool
        # is measurement work and reads as part of that family.
        tint_dialog_primary(self, _ACCENT)

        # --- Manager signals ----------------------------------------------
        # Both ArgyllCMS readers speak the same signals (item 43 steps 2-3).
        for m in (self._spotread, self._helper_mgr):
            m.reading_ready.connect(self._on_reading)
            m.ready_to_read.connect(self._on_ready)
            m.instrument_detected.connect(self._on_instrument_detected)
            m.calibration_prompt.connect(self._on_calibration_prompt)
            m.calibration_finished.connect(self._on_calibration_finished)
            m.calibration_position_wrong.connect(self._on_calibration_position_wrong)
            m.misread.connect(self._on_misread)
            m.calibration_suspect.connect(self._on_calibration_suspect)
            m.sensor_wrong_position.connect(self._on_sensor_wrong_position)
            m.no_instrument.connect(self._on_no_instrument)
            m.device_busy.connect(self._on_device_busy)
            m.instrument_disconnected.connect(self._on_disconnected)
            m.coms_init_failed.connect(self._on_init_failed)
            m.inst_init_failed.connect(self._on_init_failed)
            m.session_ended.connect(self._on_session_ended)
            m.condition_dropped.connect(self._on_condition_dropped)
        h = self._helper_mgr
        h.reading_conditions.connect(self._on_reading_conditions)
        h.conditions_ended.connect(self._on_conditions_ended)
        h.dual_spot_refused.connect(self._on_dual_spot_refused)
        h.calibration_failed.connect(self._on_helper_calibration_failed)
        h.calibration_ended_session.connect(
            self._on_helper_calibration_ended_session)
        h.fallback_requested.connect(self._on_helper_fallback)

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
        self._sync_condition_row()

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
        self._sync_condition_row()

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
        self._usb_fingerprint = usb_fingerprint_now()
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

    def _on_auto_tick(self) -> None:
        """The 2-second tick: re-decide the label only when USB changed.

        A cheap in-process look at the USB list (`usb_fingerprint_now`); the
        `ioreg` run behind :meth:`_refresh_auto_choice` follows only when a
        device was plugged in or pulled out. Nothing at all while a session
        owns the instrument or the CR30 is chosen by hand. With ArgyllCMS
        chosen by hand the label is not refreshed, but the cheap look still
        runs, because the i1Pro 3's Measurement condition row (item 43)
        follows the cable too.
        """
        if not self._instrument.isEnabled():
            return
        if _INSTRUMENT_KEYS[self._instrument.currentIndex()] == "cr30":
            return
        fp = usb_fingerprint_now()
        if fp != self.__dict__.get("_cond_fingerprint"):
            self._sync_condition_row()
        if _INSTRUMENT_KEYS[self._instrument.currentIndex()] != "auto":
            return
        if fp != self._usb_fingerprint:
            self._refresh_auto_choice()

    def _keep_auto_choice_fresh(self) -> None:
        """Start the tick when the window is shown and idle; stop it otherwise."""
        if self.isVisible() and self._instrument.isEnabled():
            self._auto_timer.start()
        else:
            self._auto_timer.stop()

    def _on_start_stop(self) -> None:
        if self._cr30 is not None and self._cr30.is_running:
            # STOP MEANS STOPPED, AT ONCE, WHATEVER THE INSTRUMENT IS DOING.
            # This used to ask the read loop to finish and then wait for it to
            # say so -- and a loop listening to a CR30 that had switched
            # itself off never said anything, so Stop did nothing at all
            # (Basti, beta 16). The session ends here, the instrument is let
            # go (over Bluetooth that is what lets it advertise again), and
            # the loop is left to finish in the background.
            self._end_cr30_session()
            return
        active = self._active_manager()
        if active.is_running:
            active.quit()
            active.abort()
            return
        if self._cr30 is None and self._manager.restart_pending():
            # Stop between a start that ended and its queued restart (the
            # -F or -s restart): nothing runs, so the restart is called off
            # and the session ends here, instead of a second spotread.
            self._manager.cancel_restart()
            return
        # Item 43: nothing of an earlier session's condition is carried into
        # the next one, whichever reader it uses (review S1: a CR30 session
        # showed an ArgyllCMS restart note on every Ready line).
        self._session_condition = None
        self._condition_note = ""
        self._start_condition = None
        self._detected_this_session = False
        self._session_note = ""
        self._pending_conds = None
        self._helper_start_failed = ""
        if self._chosen_reader() == "cr30":
            self._start_cr30_session()
            return
        plan = self._helper_plan()
        if plan is not None:
            self._start_helper_session(plan)
            return
        self._manager = self._spotread
        params = SpotReadParams(
            mode=self._MODE_KEYS[self._mode.currentIndex()],
            disable_initial_cal=self._skip_cal.isChecked(),
            condition=self._condition_for_start(),
        )
        #: what this start asked for (None: no -F)
        self._start_condition = params.condition
        self._set_session_running(True)
        self._set_status(tr("Starting instrument…"))
        self._manager.start(params, lambda _line: None)

    # ------------------------------------------------------------------
    # ChromIQ's own spot session: M0, M1 and M2 of every reading (item 43
    # steps 2-3)
    # ------------------------------------------------------------------
    def _i1pro2_family_known(self) -> bool:
        """The instrument a Start would open is of the i1Pro family (an
        i1Pro or an i1Pro 2: the USB id cannot tell them apart), or reported
        itself as an i1Pro 2 in this window while the USB list is unchanged.
        The helper itself starts the dual spot only on a real i1Pro 2 as its
        driver identifies it; anything else is handed to spotread before a
        reading is made."""
        from core.measure_pace import model_key
        reported = self.__dict__.get("_detected_instrument", "")
        if reported and self.__dict__.get(
                "_detected_fingerprint", ()) == usb_fingerprint_now():
            return model_key(reported) == "i1pro2"
        from workflow.dual_scan import instrument_model as IM
        return IM.attached_family() == IM.FAMILY_I1PRO

    def _dual_offered(self) -> bool:
        """Preferences > Beta: the i1Pro 2 dual scan is on (with the
        conditions Beta it belongs to) and the helper can read a dual spot
        in its spot session."""
        from workflow.dual_scan import session as DS
        from workflow.helper_spot_manager import helper_can_spot
        if not DS.switched_on(self._settings) or not helper_can_spot():
            return False
        try:
            from workflow.chartread_engine import helper_caps, helper_path
            return DS.helper_can(helper_caps(helper_path()))
        except Exception:      # noqa: BLE001 - no helper: no dual scan
            return False

    def _i1pro3_all_offered(self) -> bool:
        """Preferences > Beta, "X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and
        M2 from every scan", and the helper's spot session."""
        from workflow import i1pro3_conditions as C
        from workflow.helper_spot_manager import helper_can_spot
        try:
            on = bool(C.stored_value(self._settings))
        except Exception:      # noqa: BLE001 - a broken store means "off"
            on = False
        return on and helper_can_spot()

    def _helper_plan(self) -> "HelperSpotParams | None":
        """Which reader a Start uses (item 43 steps 2-3). ChromIQ's own spot
        session, keeping M0, M1 and M2 of every reading, only when:

        * an i1Pro 3 is known and the conditions Beta is on; or
        * an i1Pro (2) is known, the dual scan Beta is on, and its own rule
          says the dual scan runs: "always", or "only for M1 or M2" with M1
          or M2 chosen here (decision 3 of the study, 2026-11-24).

        Everything else is stock spotread, exactly as before (step 1's -F for
        an i1Pro 3 with the Beta off). Reflective, ArgyllCMS only."""
        if self._MODE_KEYS[self._mode.currentIndex()] != "reflective":
            return None
        if _INSTRUMENT_KEYS[self._instrument.currentIndex()] == "cr30":
            return None
        row = self.__dict__.get("_cond_row")
        chosen = (self._condition.currentData() or "M0") if (
            row is not None and not row.isHidden()) else "M0"
        if self._i1pro3_known():
            if not self._i1pro3_all_offered():
                return None
            return HelperSpotParams(
                disable_initial_cal=self._skip_cal.isChecked(), chosen=chosen)
        if self._i1pro2_family_known() and self._dual_offered():
            from workflow.dual_scan import session as DS, storage
            from workflow.dual_scan.scale import ScaleChoice
            if DS.mode(self._settings) == DS.MODE_M1_M2 and chosen == "M0":
                log.info("spot read: dual scan only for M1 or M2, and M0 is "
                         "chosen: an ordinary spot reading")
                return None
            return HelperSpotParams(
                disable_initial_cal=self._skip_cal.isChecked(), chosen=chosen,
                dual_args=storage.helper_args(ScaleChoice.standard(),
                                              "instrument", chosen))
        return None

    def _start_helper_session(self, plan: "HelperSpotParams") -> None:
        from workflow import measurement_messages as M
        self._manager = self._helper_mgr
        log.info("spot read: ChromIQ's own spot session, every reading keeps "
                 "M0, M1 and M2%s; shown first: %s",
                 " (i1Pro 2 dual spot)" if plan.dual else "", plan.chosen)
        self._show_view(plan.chosen)
        notes = []
        if plan.dual and plan.disable_initial_cal:
            notes.append(M.M_SPOT_DUAL_SKIP_CAL.render()[1])
        notes.append(M.M_SPOT_ALL_CONDITIONS.render()[1])
        self._session_note = "\n".join(notes)
        self._set_session_running(True)
        self._set_status(tr("Starting instrument…"))
        self._helper_mgr.start(plan, lambda _line: None)

    def _on_helper_fallback(self) -> None:
        """The instrument gave no other condition (the guess before Start was
        wrong): stock spotread, as before, before anything was read."""
        from workflow import measurement_messages as M
        model = self.__dict__.get("_detected_instrument", "") or tr("another instrument")
        _title, body = M.M_SPOT_CONDITION_FALLBACK.render(model=model)
        self._condition_note = body
        self._session_note = ""
        self._session_condition = None
        self._start_condition = None
        self._manager = self._spotread
        self._set_status(body)
        self._spotread.start(SpotReadParams(
            mode="reflective",
            disable_initial_cal=self._skip_cal.isChecked(), condition=None),
            lambda _line: None)

    def _on_reading_conditions(self, conds) -> None:
        self._pending_conds = dict(conds) if conds else None

    def _on_conditions_ended(self, sentence: str) -> None:
        from workflow import measurement_messages as M
        _title, body = M.M_SPOT_CONDITIONS_ENDED.render(reason=sentence)
        self._session_note = body
        self._set_status(body)

    def _on_dual_spot_refused(self, why: str, calibrate: bool) -> None:
        """An i1Pro 2 dual spot was refused: nothing was kept, the patch is
        read again (after a calibration when that mends it)."""
        from workflow import measurement_messages as M
        from workflow.dual_scan.session import reason_sentence
        self._misread = True
        self._set_read_enabled(True)
        text = reason_sentence(why)
        if calibrate:
            text += "\n" + M.M_SPOT_DUAL_CALIBRATE.render()[1]
        self._set_status(text)

    def _on_helper_calibration_failed(self, detail: str) -> None:
        from workflow import measurement_messages as M
        _title, body = M.M_SPOT_CAL_FAILED.render(reason=detail or tr("unknown"))
        log.info("spot read (helper): calibration failed: %s", detail)
        self._set_read_enabled(False)
        cal = self.__dict__.get("_cal_btn")
        if cal is not None:
            cal.setEnabled(True)
        self._set_status(body)

    def _on_helper_calibration_ended_session(self, detail: str) -> None:
        """A calibration ArgyllCMS asked for later in the session failed after
        every attempt: the session ends and its reason stays on screen. The
        instrument had started, so not "Could not start the instrument"."""
        from workflow import measurement_messages as M
        title, _body = M.M_SPOT_CAL_FAILED.render(reason=detail or tr("unknown"))
        self._helper_start_failed = title + "\n" + (detail or tr("unknown"))
        self._set_status(self._helper_start_failed)

    def _show_view(self, key: str) -> None:
        """Put *key* in the view switch without re-showing the list."""
        self._view.blockSignals(True)
        try:
            self._view.setCurrentIndex(
                _CONDITION_KEYS.index(key) if key in _CONDITION_KEYS else 0)
        finally:
            self._view.blockSignals(False)

    def _sync_view_row(self) -> None:
        show = any(getattr(r, "keeps_several", False) for r in self._readings)
        self._view_row.setVisible(show)

    def _on_view_changed(self, _index: int) -> None:
        """Show the whole list in another condition (item 43 steps 2-3).
        Nothing is measured; a reading with one condition keeps its own."""
        key = self._view.currentData() or "M0"
        changed = sum(1 for r in self._readings if r.show(key))
        log.info("spot read: the list now shows %s (%d readings changed)",
                 key, changed)
        if changed:
            rows = self._selected_rows()
            self._table.blockSignals(True)
            try:
                self._table.setRowCount(0)
            finally:
                self._table.blockSignals(False)
            for r in self._readings:
                self._append_row(r)
            from PyQt6.QtCore import QItemSelectionModel
            sel = self._table.selectionModel()
            for row in rows:
                if 0 <= row < self._table.rowCount():
                    sel.select(self._table.model().index(row, 0),
                               QItemSelectionModel.SelectionFlag.Select
                               | QItemSelectionModel.SelectionFlag.Rows)

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
        # The CR30 is calibrated by ChromIQ's own windows at the start and has
        # no calibration key: Calibrate is hidden, so it takes no room.
        self._cal_btn.setVisible(False)
        self._set_session_running(True)
        self._show_log()
        self._log.clear()
        self._set_status(tr("Starting instrument…"))
        # Set by the calibration once it has written "Connected to your CR30
        # over ..." into this log (ui/cr30_calibration.py).
        self._cr30_transport_said = ""
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
        # The calibration has just said which way it connected; the session
        # start would say it again on the very next line.
        mgr.say_transport_at_start = not self._cr30_transport_said
        mgr.reading_ready.connect(self._on_reading)
        mgr.ready_to_read.connect(self._on_ready)
        mgr.instrument_detected.connect(self._on_instrument_detected)
        mgr.instrument_disconnected.connect(self._on_disconnected)
        mgr.read_refused.connect(self._on_cr30_refused)
        mgr.magnet_gated.connect(self._on_cr30_magnet)
        mgr.trigger_not_armed.connect(self._on_cr30_trigger_not_armed)
        mgr.instrument_lost.connect(self._on_cr30_lost)
        mgr.presses_discarded.connect(self._on_cr30_early_press)
        mgr.session_ended.connect(self._on_session_ended)
        mgr.start(None, self._note)

    def _note(self, text: str) -> None:
        if not text:
            return
        self._show_log()
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
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
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
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
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
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
        box.exec()

    def _on_cr30_early_press(self, n: int) -> None:
        """M-SPOT-CR30-EARLY-PRESS. Presses from before Ready were not used.

        The instrument announced them before the session was listening (most
        often while the calibration's last window was still open, which itself
        says to press the button), so they belong to no reading anybody asked
        for and are dropped. The person who pressed must not be left waiting
        for a row that will never come. It speaks through the window's log,
        which is visible for the whole of a CR30 session (wording approved by
        Basti, 2026-10-10).
        """
        from workflow import measurement_messages as M
        _title, body = M.M_SPOT_CR30_EARLY_PRESS.render(n=int(n))
        self._note(body)

    def _on_cr30_lost(self, reason: str) -> None:
        """M-SPOT-CR30-GONE. The instrument stopped answering mid-session.

        Basti, beta 16: the CR30 switched itself off, and once it was on again
        nothing happened until the window was closed. The session is paused
        rather than ended, every reading stays in the list, and the window
        asks: reconnect, which looks for the instrument again and carries on,
        or stop. A reconnect that still finds nothing comes back here.
        """
        if self.__dict__.get("_lost_window_open"):
            return
        from workflow import measurement_messages as M
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        log.info("spot read: the CR30 stopped answering (%s)", reason)
        self._set_read_enabled(False)
        self._note(reason)
        title, body = M.M_SPOT_CR30_GONE.render()
        self._set_status(title)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        again = box.addButton(tr("Reconnect"),
                              QMessageBox.ButtonRole.AcceptRole)
        stop = box.addButton(tr("Stop session"),
                             QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(again)
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
        fit_message_box_buttons(box)
        order_message_box_buttons(box, [again, stop])
        self._lost_window_open = True
        try:
            clicked = self._ask(box)
        finally:
            self._lost_window_open = False
        mgr = self._cr30
        if clicked is again and mgr is not None:
            self._set_status(tr("Looking for your CR30…"))
            mgr.reconnect()
            return
        self._end_cr30_session()

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
        cal = self.__dict__.get("_cal_btn")
        if cal is not None:
            # spotread sessions only: the CR30 is calibrated by ChromIQ's own
            # windows at its start, and has no calibration key to send.
            cal.setEnabled(bool(on) and self.__dict__.get("_cr30") is None)
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
        if self._delete_key(obj, event):
            return True
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

    def _delete_key(self, obj, event) -> bool:
        """Backspace / Delete remove the selected readings, Cmd+Z puts them
        back -- ONLY while the readings list itself has the focus.

        Not while a name is being edited (the editor is a QLineEdit, and a
        Backspace there deletes a character), and not anywhere else in the
        window, where the keys mean nothing to the list.
        """
        from PyQt6.QtGui import QKeySequence
        # The key's RECEIVER, which is the focus widget: the list itself, and
        # never the name editor (a QLineEdit inside it) or another control.
        table = self.__dict__.get("_table")
        if table is None or obj is not table:
            return False
        if table.state() == QAbstractItemView.State.EditingState:
            return False
        if event.matches(QKeySequence.StandardKey.Undo):
            return self._undo_delete()
        if event.key() not in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            return False
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                | Qt.KeyboardModifier.MetaModifier
                                | Qt.KeyboardModifier.AltModifier):
            return False
        return self._delete_selected() > 0

    def _rows_height(self, rows: int) -> int:
        """How tall the list is when it shows its heading and *rows* readings."""
        t = self._table
        return (t.horizontalHeader().sizeHint().height()
                + t.verticalHeader().defaultSectionSize() * rows
                + 2 * t.frameWidth())

    def _log_lines_height(self, lines: int) -> int:
        """How tall the notes are when they show *lines* lines."""
        log_ = self._log
        return (log_.fontMetrics().lineSpacing() * lines
                + int(log_.document().documentMargin()) * 2
                + 2 * log_.frameWidth())

    def _show_log(self) -> None:
        """Open the notes under the list. The first time, at a modest height
        taken from the list; after that wherever the user left the divide."""
        if self._log.isHidden():
            self._log.setVisible(True)
        if not self._log_sized:
            self._log_sized = True
            want = self._log_lines_height(_INITIAL_LOG_LINES)
            total = sum(self._split.sizes())
            if total > 0:
                self._split.setSizes([max(total - want, 1), want])

    def _default_height(self) -> int:
        """The window's height at first show: the list shows
        `_DEFAULT_LIST_ROWS` readings with the notes open at their first
        height, and the window still fits the screen it opens on (a 13-inch
        MacBook's 1440x900, menu bar and Dock taken off, is the smallest this
        is held to)."""
        lay = self.layout()
        others = lay.sizeHint().height() - self._split.sizeHint().height()
        want = (others + self._rows_height(_DEFAULT_LIST_ROWS)
                + self._split.handleWidth()
                + self._log_lines_height(_INITIAL_LOG_LINES))
        screen = self.screen()
        if screen is not None:
            want = min(want, screen.availableGeometry().height() - _TITLE_BAR)
        return max(want, self.minimumSizeHint().height())

    def _work_area_width(self) -> int:
        """The width of the screen this window opens on, menu bar and Dock
        taken off; 0 when there is no screen to ask."""
        screen = self.screen()
        return screen.availableGeometry().width() if screen is not None else 0

    def _wrap_button_row(self) -> None:
        """Move Save and Close from the end of the button row to a row of
        their own under it, right-aligned as before.

        Calibrate (4.3.60, item 41) goes down too, to the left of that row:
        it is the newest and least used button, and moving it keeps the first
        row exactly as wide as it was in 4.3.59, so every language fits a
        1024 px work area again once the row wraps."""
        bottom = self._bottom
        for i in reversed(range(bottom.count())):
            item = bottom.itemAt(i)
            if item.widget() is None:          # the stretch before Save
                bottom.takeAt(i)
        bottom.removeWidget(self._save_btn)
        bottom.removeWidget(self._close_btn)
        bottom.removeWidget(self._cal_btn)
        bottom.addStretch(1)
        second = QHBoxLayout()
        second.setSpacing(bottom.spacing())
        second.addWidget(self._cal_btn)
        second.addStretch(1)
        second.addWidget(self._save_btn)
        second.addWidget(self._close_btn)
        outer = self._outer
        at = next(i for i in range(outer.count())
                  if outer.itemAt(i).layout() is bottom)
        outer.insertLayout(at + 1, second)
        self._row_wrapped = True

    def _settle_size(self) -> None:
        """Floors and the first size, measured once the buttons and the list
        carry the fonts they are painted in."""
        self._table.setMinimumHeight(self._rows_height(_MIN_LIST_ROWS))
        self._log.setMinimumHeight(self._log_lines_height(_MIN_LOG_LINES))
        # THE WINDOW MAY NOT BE NARROWER THAN ITS BUTTON ROW. A fixed 960 sat
        # below what the row needs, so at the minimum width "Average selected"
        # and "Delete" were painted over each other; in French and German the
        # row needs more again.
        #
        # …NOR WIDER THAN THE SCREEN IT OPENS ON. French needs 1283 px for the
        # row, more than a 1280-wide screen has. Then Save and Close move to a
        # second row under the others, and only if even that is too wide is
        # the minimum held to the screen.
        lay = self.layout()
        if lay is not None:
            lay.activate()
            need = lay.minimumSize().width()
            avail = self._work_area_width()
            if avail and need > avail and not self._row_wrapped:
                self._wrap_button_row()
                lay.activate()
                need = lay.minimumSize().width()
            if avail:
                need = min(need, avail)
            if need > self.minimumWidth():
                self.setMinimumWidth(need)
        # A window nobody has sized gets the default height. Qt's own first
        # size is capped at two thirds of the screen, which on a 13-inch
        # screen left the list room for five readings.
        if not self.testAttribute(Qt.WidgetAttribute.WA_Resized):
            self.resize(max(self.width(), self.minimumWidth()),
                        max(self.height(), self._default_height()))
            self.setAttribute(Qt.WidgetAttribute.WA_Resized, False)

    # ONE showEvent and ONE hideEvent. Until beta 18 this class defined each
    # twice (2026-09-03, eae7bc5bf and f0d6d24cd); Python keeps only the last
    # definition, so the earlier pair, which started the "→ <reader>" label's
    # refresh, never ran and the label could go stale with the window open.
    # `tests/test_b18_spot_reader_label_follows_usb.py` holds them together.
    def showEvent(self, event) -> None:   # noqa: N802, D102
        if not event.spontaneous():
            self._settle_size()
        super().showEvent(event)
        # A window shown again is a new session's worth of work to protect.
        self._closing = False
        app = QApplication.instance()
        if app is not None:
            # Qt moves an already-installed filter to the front rather than
            # installing it twice, so a reopened window cannot stack them.
            app.installEventFilter(self)
        # A window that names the reader has to keep naming the right one: he
        # can plug the ColorMunki in while this is open, and a label that went
        # stale would be worse than no label. Idle only: nothing is asked of
        # the operating system while a session owns the instrument.
        self._refresh_auto_choice()
        self._keep_auto_choice_fresh()

    def hideEvent(self, event) -> None:   # noqa: N802, D102
        self._auto_timer.stop()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().hideEvent(event)

    def _set_session_running(self, running: bool) -> None:
        self._instrument.setEnabled(not running)
        self._mode.setEnabled(not running)
        self._skip_cal.setEnabled(not running)
        cond = self.__dict__.get("_condition")
        if cond is not None:
            # one condition per session: chosen before Start, like Mode
            cond.setEnabled(not running)
        self._start_btn.setText(tr("Stop session") if running else tr("Start session"))
        if not running:
            self._set_read_enabled(False)
            # back after a CR30 session, which hides it
            cal = self.__dict__.get("_cal_btn")
            if cal is not None:
                cal.setVisible(True)
            self._apply_reader_capabilities()
            self._refresh_auto_choice()
            if "_cond_row" in self.__dict__:
                stored = str(self._settings.get(_CONDITION_SETTING, "M0")
                             or "M0")
                if self._condition.currentData() != stored:
                    self._show_condition(stored)
                self._sync_condition_row()
        self._keep_auto_choice_fresh()

    def _on_session_ended(self, code: int) -> None:
        # A "Calibrate again" still waiting for its ready prompt belongs to
        # the session that ended, never to the next one.
        self._recalibrate_pending = False
        self._set_session_running(False)
        ended = tr("Session ended.")
        why = self.__dict__.get("_helper_start_failed")
        if why:
            # ChromIQ's own spot session ends right after saying why it could
            # not start; the reason stays (safety review S1)
            ended = why + "\n" + ended
        self._set_status(ended)

    def _on_ready(self) -> None:
        # spotread's menu prompt is the only proof the error mode is over, so
        # it — not a timer — is what ends the misread state.
        self._misread = False
        if self.__dict__.get("_recalibrate_pending"):
            # "Calibrate again" after a misread: spotread's retry prompt has
            # been left, and this ready prompt is where 'k' is read.
            self._recalibrate_pending = False
            self._set_read_enabled(False)
            self._manager.request_calibration()
            self._set_status(tr("Calibrating…"))
            return
        self._set_read_enabled(True)
        if self.__dict__.get("_cal_suspect_open"):
            # The calibration warning is open and its headline is on the
            # status line; the prompt that follows the reading must not
            # replace it with "Ready".
            return
        # Knut, #130 2026-08-01: *"the 'Ready ….' message is inaccurate, as
        # using instrument button is also possible. Revise text."* Both ways of
        # reading are named now.
        note = self.__dict__.get("_condition_note") or self.__dict__.get(
            "_session_note")
        if note:
            # Item 43: the session was started again without M1/M2. Said
            # above the Ready line for the whole session; a status line that
            # said it once was replaced within a second by the restarted
            # session's own lines (seen on screen).
            self._set_status(note + "\n" + self._ready_text())
            return
        self._set_status(self._ready_text())

    @staticmethod
    def _ready_text() -> str:
        return tr("Ready — place the instrument on a colour, then "
                  "click Take reading or press the button on the "
                  "instrument.")

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
            self._hold_calibrate_until_ready()
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
            self._hold_calibrate_until_ready()
            self._manager.take_reading()

        QTimer.singleShot(self._MISREAD_CLEAR_PAUSE_MS, _then_read)

    # ------------------------------------------------------------------
    # Readings
    # ------------------------------------------------------------------
    def _next_patch_number(self) -> int:
        """The number for the next automatic name, never one already used.

        It was `len(readings) + 1`, which was right only while nothing could
        leave the list: with readings deletable, "Patch 2" of three deleted
        would have made the next reading a second "Patch 3". Taking the larger
        of the two keeps every earlier behaviour (an Average still counts as a
        place in the list) and never repeats a number.
        """
        self._patch_counter = max(self._patch_counter, len(self._readings)) + 1
        return self._patch_counter

    def _on_reading(self, xyz: tuple, lab: tuple) -> None:
        name = tr("Patch {n}").format(n=self._next_patch_number())
        cond = self.__dict__.get("_session_condition")
        if (cond is None and self.__dict__.get("_start_condition")
                and not self.__dict__.get("_detected_this_session")):
            # -F was asked for and accepted, and no "Instrument Type:" line
            # came (spotread prints it only for some drivers): the reading
            # was taken under the filter that was asked for (review S3)
            cond = self._start_condition
        conds, self._pending_conds = self.__dict__.get("_pending_conds"), None
        if conds:
            # item 43 steps 2-3: ChromIQ's own spot session gave every
            # condition of this reading; the list shows the one chosen in
            # "Show the readings in" when the reading has it, else M0
            view = self._view.currentData() or "M0"
            cond = view if view in conds else ("M0" if "M0" in conds else None)
            if cond is not None:
                xyz, lab = conds[cond]
        reading = SpotReading(name=name, xyz=tuple(xyz), lab=tuple(lab),
                              condition=cond,
                              conditions=dict(conds) if conds and len(conds) > 1
                              else None)
        if conds:
            log.info("spot read: %s read, keeps %s, shown in %s", name,
                     ", ".join(sorted(conds)), cond)
        elif cond:
            log.info("spot read: %s read in %s", name, cond)
        self._readings.append(reading)
        self._append_row(reading)
        self._sync_view_row()
        self._unsaved = True
        self._save_btn.setEnabled(True)
        self._forget_undo()
        self._set_status(
            tr("Read {name}: L* {l:.1f}  a* {a:.1f}  b* {b:.1f}").format(
                name=name, l=reading.lab[0], a=reading.lab[1], b=reading.lab[2])
        )

    def _append_row(self, r: SpotReading, row: "int | None" = None) -> None:
        # Follow the newest reading only while the reader is already looking at
        # it — the same rule as the log panes (`ui.widgets.TailFollowLog`), and
        # asked BEFORE the row exists, because a row added first makes the
        # maximum grow and a reader who has not moved look as if they had.
        sb = self._table.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum()
        self._table.blockSignals(True)
        if row is None or not 0 <= row <= self._table.rowCount():
            row = self._table.rowCount()
        self._table.insertRow(row)

        name_item = QTableWidgetItem(r.name)
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, 0, name_item)

        vals = (*r.lab, *r.xyz)
        for col, v in enumerate(vals, start=1):
            item = QTableWidgetItem(decimal_text(v, 2))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, col, item)

        swatch = QTableWidgetItem(r.hex)
        swatch.setFlags(swatch.flags() & ~Qt.ItemFlag.ItemIsEditable)
        swatch.setBackground(QColor(r.hex))
        swatch.setForeground(QColor(_ink_on(r.hex)))
        swatch.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 7, swatch)

        cond = getattr(r, "condition", None)
        if self._table.columnCount() > 8:
            tag = QTableWidgetItem(cond or "")
            tag.setFlags(tag.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tag.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if cond:
                from workflow.measurement_condition import condition_name
                tag.setToolTip(condition_name(cond))
            self._table.setItem(row, 8, tag)
            if cond and self._table.isColumnHidden(8):
                self._table.setColumnHidden(8, False)

        self._table.blockSignals(False)
        if at_bottom:
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
        self._sync_delete_btn()

    # ------------------------------------------------------------------
    # Deleting single readings
    # ------------------------------------------------------------------
    def _sync_delete_btn(self) -> None:
        """Delete while something is selected; Undo delete while nothing is
        and a delete can still be put back. The Clear button's pattern."""
        btn = self.__dict__.get("_del_btn")
        if btn is None:
            return
        if self._selected_rows():
            btn.setText(tr("Delete"))
            btn.setEnabled(True)
        elif self._deleted:
            btn.setText(tr("Undo delete"))
            btn.setEnabled(True)
        else:
            btn.setText(tr("Delete"))
            btn.setEnabled(False)

    def _on_delete_button(self) -> None:
        if self._selected_rows():
            self._delete_selected()
        elif self._deleted:
            self._undo_delete()

    def _delete_selected(self) -> int:
        """Remove the selected readings from the list and the table.

        No question first, because nothing is lost: Undo delete (or Cmd+Z in
        the list) puts them back in their places until the next reading. The
        names of the readings that stay are not touched, so a number written
        down beside a sample still points at the same reading, and the next
        reading never re-uses a number (`_next_patch_number`). Returns how
        many went.
        """
        rows = self._selected_rows()
        if not rows:
            return 0
        # Remember the counter before anything leaves, so a later reading
        # cannot take the number of one that was deleted.
        self._patch_counter = max(self._patch_counter, len(self._readings))
        batch = [(r, self._readings[r]) for r in rows
                 if 0 <= r < len(self._readings)]
        self._table.blockSignals(True)
        try:
            for r, _reading in sorted(batch, reverse=True):
                del self._readings[r]
                self._table.removeRow(r)
        finally:
            self._table.blockSignals(False)
        self._table.clearSelection()
        self._deleted.append(batch)
        # The list no longer matches anything saved, so closing asks again
        # while there is something left to lose.
        self._unsaved = bool(self._readings)
        self._save_btn.setEnabled(bool(self._readings))
        self._avg_btn.setEnabled(False)
        self._sync_clear_btn()
        self._sync_delete_btn()
        if len(batch) == 1:
            self._set_status(tr("Deleted {name}.").format(name=batch[0][1].name))
        else:
            self._set_status(tr("Deleted {n} readings.").format(n=len(batch)))
        return len(batch)

    def _undo_delete(self) -> bool:
        """Put the last deleted readings back where they were."""
        if not self._deleted:
            return False
        batch = self._deleted.pop()
        for r, reading in sorted(batch):
            r = min(r, len(self._readings))
            self._readings.insert(r, reading)
            self._append_row(reading, r)
        self._unsaved = True
        self._save_btn.setEnabled(True)
        self._sync_clear_btn()
        self._sync_delete_btn()
        if len(batch) == 1:
            self._set_status(tr("Put back {name}.").format(name=batch[0][1].name))
        else:
            self._set_status(tr("Put back {n} readings.").format(n=len(batch)))
        return True

    def _table_menu(self):
        """The list's right-click menu. Built here, shown by the caller, so a
        test can read it without opening a popup."""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self._table)
        act = menu.addAction(tr("Delete"))
        act.setEnabled(bool(self._selected_rows()))
        act.triggered.connect(self._delete_selected)
        if self._deleted:
            undo = menu.addAction(tr("Undo delete"))
            undo.triggered.connect(self._undo_delete)
        return menu

    def _on_table_menu(self, pos) -> None:
        # A right-click on a row that is not selected acts on THAT row, the
        # way a list in Finder does, rather than on a selection elsewhere.
        idx = self._table.indexAt(pos)
        if idx.isValid() and idx.row() not in self._selected_rows():
            self._table.selectRow(idx.row())
        self._table_menu().exec(self._table.viewport().mapToGlobal(pos))

    def _on_average_selected(self) -> None:
        rows = self._selected_rows()
        if len(rows) < 2:
            return
        try:
            averaged = average_readings([self._readings[r] for r in rows],
                                        tr("Average"))
        except MixedConditions as exc:
            # Item 43: only readings of one condition make an average.
            from workflow import measurement_messages as M
            _title, body = M.M_SPOT_AVERAGE_CONDITIONS.render(
                conditions=", ".join(c or tr("unknown") for c in exc.conditions))
            log.info("spot read: average refused, the selected readings are "
                     "of different measurement conditions (%s)",
                     ", ".join(c or "none" for c in exc.conditions))
            self._set_status(body)
            return
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
        if "_view_row" in self.__dict__:
            self._sync_view_row()

    def _forget_undo(self) -> None:
        """A new reading replaces what Undo would put back."""
        if self._cleared:
            self._cleared = []
        self._deleted = []
        self._sync_clear_btn()
        self._sync_delete_btn()

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
            self._patch_counter = max(self._patch_counter,
                                      self._cleared_counter)
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
        # A cleared list starts again at "Patch 1", as it always has; the
        # count is kept with the readings so Undo clear restores both.
        self._cleared_counter = max(self._patch_counter, len(self._readings))
        self._patch_counter = 0
        self._deleted = []
        self._readings.clear()
        self._table.setRowCount(0)
        self._save_btn.setEnabled(False)
        self._avg_btn.setEnabled(False)
        self._sync_clear_btn()
        self._sync_delete_btn()

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
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
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
                # `exports_dir`, ASKED DIRECTLY (adversary round on 528b7cfc).
                # This read `getattr(run, "exports", None)`; `Run` has no
                # `exports`, so the default hid the mistake and every save was
                # offered the run folder instead of its exports/ folder.
                return Path(run.exports_dir) / name
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
        if not self._may_write_condition_files(base):
            return False
        try:
            csv_path = write_csv(artefact(base, ".csv"), self._readings)
            # one .ti3 per measurement condition (item 43); a list of one
            # condition, or of none, is the one file it always was
            ti3_paths = write_ti3_files(base, self._readings)
        except OSError as exc:
            warn(self, tr("Save failed"), str(exc))
            return False
        self._unsaved = False
        if len(ti3_paths) > 1:
            log.info("spot read: saved one .ti3 per measurement condition: %s",
                     ", ".join(p.name for p in ti3_paths))
        inform(
            self, tr("Saved"),
            tr("Readings saved to:\n{csv}\n{ti3}").format(
                csv=csv_path.name,
                ti3="\n".join(p.name for p in ti3_paths)),
        )
        return True

    def _may_write_condition_files(self, base) -> bool:
        """M-SPOT-SAVE-CONDITION-FILES (item 43): the folder already holds
        ``<base>-M0/M1/M2.ti3`` from an earlier save of the same name. The
        file dialog asked about the CSV only; these are replaced silently
        otherwise, and one this list does not write again would stay beside
        the new files with older readings, unmentioned (review). Asked once;
        nothing is deleted."""
        existing = [artefact(f"{base}-{c}", ".ti3") for c in _CONDITION_KEYS]
        existing = [p for p in existing if p.exists()]
        if not existing:
            return True
        from workflow import measurement_messages as M
        title, body = M.M_SPOT_SAVE_CONDITION_FILES.render(
            files=", ".join(p.name for p in existing))
        box = QMessageBox(self)
        set_warning_icon(box)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        replace = box.addButton(tr("Replace"),
                                QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
        ok = self._ask(box) is replace
        log.info("spot read: earlier condition files %s: %s",
                 ", ".join(p.name for p in existing),
                 "replace" if ok else "save cancelled")
        return ok

    # ------------------------------------------------------------------
    # Calibration + error pop-ups
    # ------------------------------------------------------------------
    def _on_instrument_detected(self, model: str) -> None:
        """Remember what spotread says is attached (#130, Knut 2026-07-31)."""
        self._detected_instrument = model or ""
        self._detected_this_session = True
        #: the USB list when it reported, so its report keeps winning over
        #: the USB guess until a cable changes (item 43)
        self._detected_fingerprint = usb_fingerprint_now()
        log.info("spot read: instrument reported as %s", model)
        if "_cond_row" not in self.__dict__:
            return
        if self.__dict__.get("_manager") is self.__dict__.get("_helper_mgr") \
                and self.__dict__.get("_helper_mgr") is not None:
            # Item 43 steps 2-3: ChromIQ's own spot session records every
            # condition per reading (_on_reading_conditions); the row keeps
            # the choice it was started with
            self._session_condition = None
            self._sync_condition_row()
            return
        # Item 43: the instrument's own report wins over the USB guess. An
        # i1Pro 3 reads under the condition this start asked for (M0 without
        # -F); anything else records none, exactly as before.
        reflective = self._MODE_KEYS[self._mode.currentIndex()] == "reflective"
        if is_i1pro3(model) and reflective:
            asked = self.__dict__.get("_start_condition") or "M0"
            self._session_condition = asked
            log.info("spot read: readings of this session are recorded as %s",
                     asked)
            # The row may appear only now (the USB list could not tell): it
            # shows what this session reads under, not a choice it did not
            # make. The remembered choice comes back when the session ends.
            if self._condition.currentData() != asked:
                self._show_condition(asked)
        else:
            self._session_condition = None
        self._sync_condition_row()

    def _show_condition(self, key: str) -> None:
        """Put *key* in the list without storing it as the choice."""
        self._condition.blockSignals(True)
        try:
            self._condition.setCurrentIndex(
                _CONDITION_KEYS.index(key) if key in _CONDITION_KEYS else 0)
        finally:
            self._condition.blockSignals(False)

    # ------------------------------------------------------------------
    # The measurement condition (item 43)
    # ------------------------------------------------------------------
    def _i1pro3_known(self) -> bool:
        """Whether the instrument a Start would open is an i1Pro 3.

        Nothing is opened to find out. What the instrument itself reported in
        this window wins while the USB list has not changed since (a report
        that contradicted the USB guess must not lead to the same wrong start
        again). Otherwise the USB list: 0765:6009 is an
        i1Pro 3 (or 3 Plus) and nothing else, and an answer from it about any
        other instrument stands too. When the list cannot tell (it cannot be
        read, nothing or several instruments are attached), no row. After Start the instrument's own report decides
        (:meth:`_on_instrument_detected`, and the manager's restart without
        -F when it is not an i1Pro 3)."""
        from workflow.dual_scan import instrument_model as IM
        reported = self.__dict__.get("_detected_instrument", "")
        if reported and self.__dict__.get(
                "_detected_fingerprint", ()) == usb_fingerprint_now():
            return is_i1pro3(reported)
        family = IM.attached_family()
        if family == IM.FAMILY_I1PRO3:
            return True
        # Not readable, nothing attached, or several instruments: a report
        # counts only while the USB list is the one it was made with (above),
        # so an i1Pro 3 unplugged since takes its row with it.
        return False

    def _sync_condition_row(self) -> None:
        """Show the row only for an i1Pro 3, read through ArgyllCMS, in
        Reflective mode. While a session runs the instrument's report
        decides; while idle the USB list (:meth:`_i1pro3_known`)."""
        row = self.__dict__.get("_cond_row")
        if row is None:
            return
        reader = _INSTRUMENT_KEYS[self._instrument.currentIndex()]
        reflective = self._MODE_KEYS[self._mode.currentIndex()] == "reflective"
        if not self._instrument.isEnabled():
            # a session owns the instrument: nothing is asked of the device
            # list, and the instrument's own report decides
            from core.measure_pace import model_key
            reported = self.__dict__.get("_detected_instrument", "")
            show = (reflective and reader != "cr30"
                    and (is_i1pro3(reported)
                         or (model_key(reported) == "i1pro2"
                             and self._dual_offered())))
        else:
            self._cond_fingerprint = usb_fingerprint_now()
            show = reflective and reader != "cr30" and (
                self._i1pro3_known()
                # item 43 steps 2-3: an i1Pro 2 with the dual scan Beta
                or (self._dual_offered() and self._i1pro2_family_known()))
        if show != (not row.isHidden()):
            log.info("spot read: the measurement condition row is %s",
                     "shown (an i1Pro 3)" if show else "hidden")
        row.setVisible(show)
        hint = self.__dict__.get("_dual_hint")
        if hint is not None:
            want = (not show and reflective and reader != "cr30"
                    and self._instrument.isEnabled() and self._dual_hint_wanted())
            hint.setVisible(want)

    def _dual_hint_wanted(self) -> bool:
        """The i1Pro family is known, "keep M0, M1 and M2" is on, and the dual
        scan is not (item 43 steps 2-3: "M1 and M2 need the dual scan")."""
        from workflow import i1pro3_conditions as C
        from workflow.dual_scan import session as DS
        try:
            if not C.stored_value(self._settings) or DS.switched_on(self._settings):
                return False
        except Exception:      # noqa: BLE001 - a broken store means "off"
            return False
        return self._i1pro2_family_known()

    def _condition_for_start(self) -> "str | None":
        """The condition a Start asks spotread for: "M1" or "M2" when the
        row is shown and set to it, else None (no -F, today's command line)."""
        row = self.__dict__.get("_cond_row")
        if row is None or row.isHidden():
            return None
        if not self._i1pro3_known():
            # the row is shown for an i1Pro 2's dual scan (steps 2-3), whose
            # driver refuses every -F: a stock start sends none
            return None
        key = self._condition.currentData()
        return key if key in ("M1", "M2") else None

    def _on_condition_changed(self, _index: int) -> None:
        key = self._condition.currentData() or "M0"
        log.info("spot read: measurement condition chosen: %s", key)
        try:
            self._settings.set(_CONDITION_SETTING, key)
        except Exception:      # noqa: BLE001 — remembering is never worth a crash
            log.debug("could not store the spot-read condition", exc_info=True)

    def _on_mode_changed(self, _index: int) -> None:
        self._sync_condition_row()

    def _on_condition_dropped(self, model: str) -> None:
        """M-SPOT-CONDITION-NOT-I1PRO3: -F reached an instrument that is not
        an i1Pro 3, and the session starts again without it."""
        from workflow import measurement_messages as M
        self._session_condition = None
        self._start_condition = None
        _title, body = M.M_SPOT_CONDITION_NOT_I1PRO3.render(
            model=model or tr("another instrument"))
        #: kept above the Ready line for the rest of this session (_on_ready)
        self._condition_note = body
        self._set_status(body)
        self._sync_condition_row()

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
                 "will not be asked again unless it needs it.")
            # Item 41 (4.3.60): what the calibration check cannot see, a
            # calibration only a little too weak, the person can.
            + "<br><br>" + _calibration_tip_html(),
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

    def _on_calibration_suspect(self, verdict) -> None:
        """M-SPOT-CAL-TOO-LIGHT / M-SPOT-CAL-SATURATED (item 41, 4.3.60).

        A reflective reading lighter than any print can be, or a saturated
        sensor, right after a calibration: ArgyllCMS accepted a white
        calibration that was too weak (the instrument not flat on its tile),
        and every reading of the session is too light by one factor. The
        manager asks at most once per calibration and has already passed the
        reading on unchanged; this window only offers to calibrate again.
        """
        from workflow import measurement_messages as M
        if self.__dict__.get("_cal_suspect_open"):
            return
        if verdict.reason == "saturated":
            title, body = M.M_SPOT_CAL_SATURATED.render()
        else:
            title, body = M.M_SPOT_CAL_TOO_LIGHT.render(
                percent=f"{verdict.percent:.0f}")
            if self.__dict__.get("_session_condition") == "M1":
                # item 43: more UV light, more glow from a fluorescent ink
                body += "\n\n" + M.M_SPOT_CAL_CONDITION_M1.render()[1]
        self._set_status(title)
        box = QMessageBox(self)
        set_warning_icon(box)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        again = box.addButton(tr("Calibrate again"),
                              QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Carry on measuring"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(again)
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
        self._cal_suspect_open = True
        try:
            chosen = self._ask(box)
        finally:
            self._cal_suspect_open = False
        if chosen is not again:
            log.info("spot read: calibration warning answered: carry on")
            # Put back what the status line said before the warning took it.
            if getattr(self, "_misread", False):
                self._on_misread()
            elif self._read_btn.isEnabled():
                self._set_status(self._ready_text())
            return
        log.info("spot read: calibration warning answered: calibrate again")
        self._calibrate_again()

    def _hold_calibrate_until_ready(self) -> None:
        """Calibrate is off from the reading key until spotread's next
        prompt (item 41 challenge, S-A1). spotread reads no key while it is
        measuring: a 'k' sent then waits, and if that reading misreads,
        spotread empties its input and the 'k' is lost, after the window had
        already said "Calibrating…". The next ready or misread prompt turns
        it back on (`_set_read_enabled`)."""
        cal = self.__dict__.get("_cal_btn")
        if cal is not None:
            cal.setEnabled(False)

    def _calibrate_again(self) -> None:
        """Ask spotread for a calibration now (the warning's "Calibrate
        again" and the Calibrate button). The usual Calibration Required and
        Calibration Complete windows follow."""
        log.info("spot read: calibration asked for by the user")
        self._set_read_enabled(False)
        self._set_status(tr("Calibrating…"))
        if getattr(self, "_misread", False):
            # spotread waits at its retry prompt; leave it first, and send
            # the calibration key at the ready prompt that follows.
            self._recalibrate_pending = True
            self._manager.send_key("\r")
        else:
            self._manager.request_calibration()

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
        html = calibration_instructions_html(self._instrument_family())
        if (self.__dict__.get("_manager") is self.__dict__.get("_helper_mgr")
                and self._helper_mgr.dual):
            # item 43 steps 2-3: the dual calibration reads the tile again
            from workflow import measurement_messages as M
            html += "<br><br>" + M.M_SPOT_DUAL_CAL_TILE.render()[1]
        msg = QLabel(html, dlg)
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
        set_warning_icon(box)
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
            from ui.widgets import keep_message_box_inside_the_work_area
            keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
            box.exec()
        finally:
            self._no_instrument_open = False
        if turn_off is not None and box.clickedButton() is turn_off:
            self._settings.set("fast_instrument_connect", False)
            log.info("Read single patches: faster instrument connection "
                     "switched OFF at the user's request")

    def _on_device_busy(self) -> None:
        self._set_status(tr("Instrument is in use by another program."))
        warn(
            self, tr("Instrument busy"),
            tr("The instrument is being used by another program. Close it and try again."),
        )

    def _on_disconnected(self) -> None:
        self._set_status(tr("Instrument disconnected."))

    def _on_init_failed(self, detail: str) -> None:
        text = tr("Could not start the instrument: {detail}").format(detail=detail)
        mgr = self.__dict__.get("_helper_mgr")
        if mgr is not None and self.__dict__.get("_manager") is mgr:
            self._helper_start_failed = text
        self._set_status(text)

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
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        from ui.widgets import keep_message_box_inside_the_work_area
        keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
        clicked = self._ask(box)
        if clicked is discard:
            self._closing = True
            return True
        if clicked is save:
            self._closing = bool(self._on_save())
            return self._closing
        # Cancel, or the window dismissed some other way. NOT an assert: this
        # runs inside `closeEvent`, an assert is removed under -O and raises
        # everywhere else, and "I could not identify the button" must never be
        # the reason a window closes on work nobody saved. Anything that is not
        # Save or Discard keeps the readings.
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
