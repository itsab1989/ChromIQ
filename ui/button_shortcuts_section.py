"""Preferences ▸ Measurement ▸ "Instrument button shortcuts".

Basti, 2026-10-25, after jctay's forum post 149841. A double or triple press of
the instrument's button moves the reader (`workflow.button_gestures`); this is
the section that switches it on, chooses the two actions and the wait, and
lets the user try the presses with the instrument connected ("Try it").

**Off by default, and off is today.** Unticked, the section's settings are
kept but nothing reaches the engine.

**Only the i1Pro line and the ColorMunki family.** For any other instrument
ChromIQ knows about, the section is greyed out with a short note saying why;
the engine checks the connected model again itself, so nothing changes during
a measurement with such an instrument either way.

**"Try it" opens the instrument the way a measurement does**, through the
engine (``chromiq-chartread --json --button-test``), and takes the same claim
on it (`core.instrument_lease`, ``BUTTON_TRY``). It refuses while anything else
is reading, never opens a system port (`core.instrument_port`), reads nothing,
writes nothing, and lets the instrument go when Stop is clicked or the dialog
closes, whichever way it closes.
"""
from __future__ import annotations

import json
import os

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt
from PyQt6.QtWidgets import (QCheckBox, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QListWidget, QPushButton, QVBoxLayout,
                             QWidget)

from core.i18n import tr
from core.logger import get_logger
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, set_ink
from workflow import button_gestures as BG

log = get_logger(__name__)

#: How many recognised groups the "Try it" list keeps (newest first).
TRY_LIST_MAX = 12


# ---------------------------------------------------------------------------
# The words (Basti's standing rule: friendly, extensive, easy, correct)
# ---------------------------------------------------------------------------

def section_help() -> str:
    return tr(
        "With this on, you can move around the chart from your instrument, "
        "without reaching for the computer. While the instrument lies on the "
        "sheet waiting for the next strip or patch, press its button twice "
        "quickly (a "
        "double press) or three times (a triple press). Below you choose what "
        "each one does.\n\n"
        "HOW IT WORKS\n"
        "A single press still does what it always does. ChromIQ only waits a "
        "moment after it, to be sure no second press is coming, before it acts "
        "on it; how long, you set with “Wait for further presses”. A real "
        "reading, where you hold the button down and slide the instrument "
        "along a strip, is never taken for a shortcut. A shortcut never reads "
        "or changes a measurement: the quick presses only take ChromIQ to "
        "another strip or patch, or let it wait.\n\n"
        "WHERE IT WORKS\n"
        "While a strip or patch is waiting to be read, and while the “Strip "
        "Read Failed” window is open. During a pause only “Pause / continue” "
        "does something: it goes on. Never while a strip is being read, "
        "during a calibration, or while a window that finishes the "
        "measurement is open.\n\n"
        "WHICH INSTRUMENTS\n"
        "The i1Pro, i1Pro 2, i1Pro 3 and i1Pro 3 Plus, and the ColorMunki, "
        "i1Studio and ColorChecker Studio. Only these tell the computer about "
        "every press of their button. With any other instrument this section "
        "is greyed out, and nothing changes when you measure.\n\n"
        "TURNED OFF\n"
        "Everything works exactly as before: a press is acted on at once, "
        "with no wait.\n\n"
        "**Default:** off.")


def actions_help() -> str:
    return tr(
        "What a double or a triple press does:\n\n"
        "• One strip / patch back: goes back to the strip before the one that "
        "is waiting, so you can read it again (from the first strip, to the "
        "last one).\n"
        "• One strip / patch forward: moves on to the next strip without "
        "reading this one. You can come back to it later.\n"
        "• Next unread strip / patch: goes to the next strip that has no "
        "reading yet.\n"
        "• Pause / continue: ChromIQ waits where it is and reads nothing, for "
        "example while you turn the sheet over. To go on, press the button "
        "once or press Return. In a pause between pages, it continues.\n"
        "• Nothing: the presses count as one single press.\n\n"
        "Each choice works on what you are reading: a strip when you read "
        "strips, a patch when you read patch by patch. The line under the "
        "chart in the Measure tab says where ChromIQ went, for example "
        "“Double press: back to strip C” or “Double press: back to patch "
        "C5”.\n\n"
        "**Defaults:** double press: one strip / patch back; triple press: "
        "next unread strip / patch.")


def wait_help() -> str:
    return tr(
        "How long ChromIQ waits after a press for the next one. Presses that "
        "each follow the one before within this time belong together: two of "
        "them are a double press, three a triple press.\n\n"
        "If your double presses are often taken for single ones, make it "
        "longer. If the wait after a single press feels too long, make it "
        "shorter. “Try it” below shows how your presses are recognised, with "
        "the time between them, so you can find the setting that suits your "
        "hand.\n\n"
        "A single press waits this long too before ChromIQ acts on it: for "
        "example before “Strip Read Failed” appears after a press that was "
        "too short to read a strip, or before a pause continues. Reading "
        "patch by patch, each patch is kept this long after its press before "
        "the next one is ready.\n\n"
        "**Default:** 0.60 s (from 0.30 to 1.50 s).")


def try_help() -> str:
    return tr(
        "Here you can practise the presses and see how ChromIQ recognises "
        "them, before you measure.\n\n"
        "Connect your instrument and click Start. When the line above the "
        "list says it is ready, press the button on your instrument: once, "
        "twice or three times. Each group of presses appears at the top of "
        "the list, with the time between the presses and what it would do "
        "while you measure.\n\n"
        "Nothing is measured and nothing is saved. You do not need to place "
        "the instrument on anything, and the dial of a ColorMunki can stay "
        "where it is.\n\n"
        "While it runs, ChromIQ holds the instrument, so nothing else can use "
        "it. It lets it go when you click Stop or close Preferences. A change "
        "to “Wait for further presses” applies to the next group straight "
        "away.")


def unsupported_note(name: str) -> str:
    return tr(
        "These shortcuts are not available for the {instrument}: only the "
        "i1Pro family and the ColorMunki, i1Studio and ColorChecker Studio "
        "tell the computer about every press of their button. Nothing changes "
        "when you measure with it.").format(instrument=name)


def _family_name(family: "str | None", name: str) -> str:
    return {"cr30": "CR30", "spectroscan": "SpectroScan"}.get(
        family or "", name or tr("instrument"))


def group_line(presses: int, gaps_ms, cfg: BG.GestureConfig) -> str:
    """One line of the "Try it" list."""
    who = BG.press_name(presses)
    if presses == 1:
        return tr("Single press: an ordinary press")
    gaps = BG.gaps_text(gaps_ms)
    if presses > 3:
        return tr("{press} ({gaps} apart): too many for a shortcut, counts as "
                  "a single press").format(press=who, gaps=gaps)
    action = cfg.action_for(presses)
    if action == "none":
        return tr("{press} ({gaps} apart): no shortcut chosen, counts as a "
                  "single press").format(press=who, gaps=gaps)
    return tr("{press} ({gaps} apart): {action}").format(
        press=who, gaps=gaps, action=BG.action_label(action))


# ---------------------------------------------------------------------------
# The section
# ---------------------------------------------------------------------------

class ButtonShortcutsSection(QGroupBox):
    """The whole section. *context* is a callable returning what the app
    knows about the instrument: ``{"family", "name", "port", "busy"}``
    (`TabMeasure.button_shortcut_context`); missing keys are fine."""

    def __init__(self, settings, context=None, parent: "QWidget | None" = None):
        super().__init__(tr("Instrument button shortcuts"), parent)
        self.setObjectName("buttonShortcutsGroup")
        self._settings = settings
        self._context_fn = context
        cfg = BG.config_from(settings)
        self._proc: "QProcess | None" = None
        self._buf = b""
        self._model = ""

        v = QVBoxLayout(self)
        v.setSpacing(8)

        self._enable_cb = QCheckBox(
            tr("Use double and triple presses of the instrument's button"), self)
        self._enable_cb.setChecked(cfg.enabled)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._enable_cb)
        row.addStretch()
        row.addWidget(TooltipButton(tr("Instrument Button Shortcuts"),
                                    section_help(), self))
        v.addLayout(row)

        grid = QGridLayout()
        grid.setContentsMargins(28, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self._double_combo = self._action_combo(cfg.double)
        self._triple_combo = self._action_combo(cfg.triple)
        self._double_lbl = QLabel(tr("Double press:"), self)
        self._triple_lbl = QLabel(tr("Triple press:"), self)
        grid.addWidget(self._double_lbl, 0, 0)
        grid.addWidget(self._double_combo, 0, 1)
        grid.addWidget(TooltipButton(tr("What a Shortcut Can Do"),
                                     actions_help(), self), 0, 2)
        grid.addWidget(self._triple_lbl, 1, 0)
        grid.addWidget(self._triple_combo, 1, 1)
        self._wait_lbl = QLabel(tr("Wait for further presses:"), self)
        self._wait_spin = NoScrollDoubleSpinBox(self)
        self._wait_spin.setDecimals(2)
        self._wait_spin.setRange(BG.WAIT_MIN_MS / 1000.0, BG.WAIT_MAX_MS / 1000.0)
        self._wait_spin.setSingleStep(BG.WAIT_STEP_MS / 1000.0)
        # The unit as the reader's language writes "0.6 s", from the key the
        # measuring windows already use, so no bare " s" needs translating.
        self._wait_spin.setSuffix(tr("{secs} s").replace("{secs}", ""))
        self._wait_spin.setValue(cfg.wait_ms / 1000.0)
        self._wait_spin.setMaximumWidth(120)
        grid.addWidget(self._wait_lbl, 2, 0)
        grid.addWidget(self._wait_spin, 2, 1, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(TooltipButton(tr("Wait for Further Presses"),
                                     wait_help(), self), 2, 2)
        # "Try it" and its Start button sit in the same columns as the boxes
        # above, so the button lines up with them (Basti, 2026-10-25).
        self._try_title = QLabel("<b>" + tr("Try it") + "</b>", self)
        self._try_btn = QPushButton(tr("Start"), self)
        self._try_btn.clicked.connect(self._on_try_clicked)
        # NO TALLER THAN THE BOXES ABOVE IT (Basti, 2026-10-25: the app's
        # button rule made it much taller than it needs to be).
        self._try_btn.setObjectName("buttonTryStart")
        self._try_btn.setStyleSheet(
            "QPushButton#buttonTryStart { padding: 2px 16px; min-height: 0px; }")
        self._try_btn.setFixedHeight(self._wait_spin.sizeHint().height())
        self._try_btn.setMinimumWidth(110)
        self._try_tip = TooltipButton(tr("Try It"), try_help(), self)
        grid.addWidget(self._try_title, 3, 0)
        grid.addWidget(self._try_btn, 3, 1, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self._try_tip, 3, 2)
        grid.setColumnStretch(3, 1)
        v.addLayout(grid)

        # Try it
        self._try_box = QWidget(self)
        tl = QVBoxLayout(self._try_box)
        tl.setContentsMargins(28, 4, 0, 0)
        tl.setSpacing(6)
        self._try_intro = QLabel(tr(
            "Connect your instrument, click Start and press its button once, "
            "twice or three times. Each group of presses is listed here. "
            "Nothing is measured and nothing is saved."), self._try_box)
        self._try_intro.setWordWrap(True)
        set_ink(self._try_intro, "#909090", " font-size: 11px;", level="faint")
        tl.addWidget(self._try_intro)
        self._try_status = QLabel("", self._try_box)
        self._try_status.setWordWrap(True)
        tl.addWidget(self._try_status)
        self._try_list = QListWidget(self._try_box)
        self._try_list.setObjectName("buttonTryList")
        self._try_list.setMinimumHeight(80)
        self._try_list.setMaximumHeight(110)
        self._try_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tl.addWidget(self._try_list)
        v.addWidget(self._try_box)

        self._note = QLabel("", self)
        self._note.setWordWrap(True)
        self._note.setObjectName("buttonShortcutsNote")
        v.addWidget(self._note)

        self._enable_cb.toggled.connect(self._sync_enabled)
        self._wait_spin.valueChanged.connect(self._on_wait_changed)
        self._supported = True
        self.refresh_instrument()

    # -- building --------------------------------------------------------
    def _action_combo(self, current: str) -> NoScrollComboBox:
        c = NoScrollComboBox(self)
        for a in BG.ACTIONS:
            c.addItem(BG.action_label(a), a)
        i = c.findData(current)
        c.setCurrentIndex(i if i >= 0 else 0)
        c.setMinimumWidth(240)
        return c

    def _context(self) -> dict:
        try:
            return dict(self._context_fn() or {}) if self._context_fn else {}
        except Exception:     # noqa: BLE001 - a guess, never a failure
            log.debug("button shortcuts: no instrument context", exc_info=True)
            return {}

    def refresh_instrument(self) -> None:
        """Grey the section out for an instrument that cannot do it."""
        ctx = self._context()
        fam = ctx.get("family")
        ok = BG.supported(fam)
        self._supported = ok is not False
        if ok is False:
            self._note.setText(unsupported_note(
                _family_name(fam, str(ctx.get("name") or ""))))
            self._note.setVisible(True)
        else:
            self._note.setVisible(False)
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        on = self._enable_cb.isChecked() and self._supported
        self._enable_cb.setEnabled(self._supported)
        for w in (self._double_lbl, self._double_combo, self._triple_lbl,
                  self._triple_combo, self._wait_lbl, self._wait_spin,
                  self._try_title, self._try_btn, self._try_box):
            w.setEnabled(on)
        if not on and self._proc is not None:
            self.stop_try()

    # -- values ------------------------------------------------------------
    def config(self) -> BG.GestureConfig:
        return BG.GestureConfig(
            enabled=self._enable_cb.isChecked(),
            double=str(self._double_combo.currentData() or "none"),
            triple=str(self._triple_combo.currentData() or "none"),
            wait_ms=BG.clamp_wait(self._wait_spin.value() * 1000.0))

    def save(self, settings) -> None:
        cfg = self.config()
        settings.set("button_gestures_enabled", cfg.enabled)
        settings.set("button_gesture_double", cfg.double)
        settings.set("button_gesture_triple", cfg.triple)
        settings.set("button_gesture_wait_ms", cfg.wait_ms)

    # -- Try it ------------------------------------------------------------
    def _on_try_clicked(self) -> None:
        if self._proc is not None:
            self.stop_try()
        else:
            self.start_try()

    def _say(self, text: str) -> None:
        self._try_status.setText(text)

    def _busy_reason(self) -> "str | None":
        """Why the instrument cannot be opened now, or None."""
        ctx = self._context()
        if ctx.get("busy"):
            return tr("Your instrument is being used for a measurement right "
                      "now. Try it again once the measurement has finished.")
        from core import instrument_lease
        other = instrument_lease.held_by_other(self)
        if other is not None:
            return tr("Your instrument is in use right now ({where}). Try it "
                      "again once it is free.").format(
                          where=instrument_lease.where_label(other))
        return None

    def _helper_args(self) -> "list[str] | None":
        from workflow import chartread_engine
        try:
            helper = chartread_engine.helper_path()
        except chartread_engine.EngineUnavailable:
            self._say(tr("ChromIQ's measuring engine is not available on this "
                         "computer, so the presses cannot be watched here."))
            return None
        cfg = self.config()
        args = ["--json", "--button-test", "--gestures",
                f"{cfg.wait_ms}:23"]
        replay = os.environ.get("CHROMIQ_REPLAY")
        if replay:
            args += ["--replay", replay]
        else:
            port = int(self._context().get("port") or 1)
            args += ["-c", str(port)]
            from core.instrument_port import refused_port
            if refused_port(str(helper), args) is not None:
                self._say(tr(
                    "No instrument was found. Connect your i1Pro or "
                    "ColorMunki and click Start again."))
                return None
        return [str(helper)] + args

    def start_try(self) -> None:
        if self._proc is not None:
            return
        why = self._busy_reason()
        if why:
            self._say(why)
            return
        cmd = self._helper_args()
        if cmd is None:
            return
        from core import instrument_lease
        if not instrument_lease.acquire(self, instrument_lease.BUTTON_TRY):
            self._say(self._busy_reason() or tr(
                "Your instrument is in use right now. Try it again once it is "
                "free."))
            return
        proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        try:
            from core.argyll_env import argyll_env
            for k, val in argyll_env().items():
                env.insert(k, str(val))
        except Exception:     # noqa: BLE001
            log.debug("button shortcuts: no Argyll environment", exc_info=True)
        proc.setProcessEnvironment(env)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        proc.readyReadStandardOutput.connect(self._on_try_output)
        proc.finished.connect(self._on_try_finished)
        self._proc = proc
        self._buf = b""
        self._model = ""
        self._try_list.clear()
        self._try_btn.setText(tr("Stop"))
        self._say(tr("Opening the instrument…"))
        log.info("button shortcuts: Try it: %s", " ".join(cmd))
        proc.start(cmd[0], cmd[1:])

    def send_to_try(self, cmd: dict) -> None:
        """Write one command to the running "Try it" engine (also used by
        tests and on-screen drivers with the replay instrument)."""
        if self._proc is not None:
            self._proc.write((json.dumps(cmd) + "\n").encode())

    def _on_wait_changed(self, _v: float) -> None:
        self.send_to_try({"cmd": "gesture_wait",
                          "ms": str(self.config().wait_ms)})

    def _on_try_output(self) -> None:
        proc = self._proc
        if proc is None:
            return
        self._buf += bytes(proc.readAllStandardOutput())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            s = line.decode("utf-8", "replace").strip()
            if not s.startswith("{"):
                continue
            try:
                ev = json.loads(s)
            except ValueError:
                continue
            self._on_try_event(ev)

    def _on_try_event(self, ev: dict) -> None:
        kind = ev.get("event")
        if kind == "instrument":
            self._model = str(ev.get("model") or "")
            if ev.get("button"):
                text = tr("Ready. Press the button on your {model}.").format(
                    model=self._model)
                if "colormunki" in self._model.lower():
                    # The driver reads the button apart from the dial
                    # (munki_imp.c: switch presses and dial changes are
                    # separate events), so the dial need not be moved.
                    text += " " + tr("The dial can stay in any position: "
                                     "only the button is used here.")
                self._say(text)
            else:
                self._say(tr(
                    "Your {model} does not tell the computer when its button "
                    "is pressed, so these shortcuts cannot work with it. "
                    "Nothing changes when you measure with it.").format(
                        model=self._model))
        elif kind == "press_group":
            n = int(ev.get("presses") or 0)
            if n <= 0:
                return
            self._try_list.insertItem(0, group_line(n, ev.get("gaps_ms"),
                                                    self.config()))
            while self._try_list.count() > TRY_LIST_MAX:
                self._try_list.takeItem(self._try_list.count() - 1)
        elif kind == "error" and ev.get("kind") == "no_instrument":
            self._say(tr("No instrument was found. Connect your i1Pro or "
                         "ColorMunki and click Start again."))

    def _on_try_finished(self, *_a) -> None:
        proc = self._proc
        self._proc = None
        if proc is not None:
            proc.deleteLater()
        from core import instrument_lease
        instrument_lease.release(self)
        self._try_btn.setText(tr("Start"))
        if self._try_status.text() in ("", tr("Opening the instrument…")) \
                or self._model:
            self._say(tr("Stopped. The instrument is free again."))

    def stop_try(self) -> None:
        """Let the instrument go: quit, wait a moment for the engine to close
        it properly, and only then make sure the process is gone."""
        proc = self._proc
        if proc is None:
            from core import instrument_lease
            instrument_lease.release(self)
            return
        try:
            self.send_to_try({"cmd": "quit"})
            proc.closeWriteChannel()
            if not proc.waitForFinished(4000):
                log.warning("button shortcuts: Try it did not end; stopping it")
                proc.kill()
                proc.waitForFinished(2000)
        finally:
            if self._proc is not None:
                self._on_try_finished()

    def is_trying(self) -> bool:
        return self._proc is not None
