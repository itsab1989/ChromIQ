"""Shared pieces for Agent B's on-screen journeys (engine accuracy challenge).

A journey is a Python generator: every ``yield`` hands control back to the
Qt event loop for the given number of milliseconds, so a step can run while
a MODAL dialog (Preferences, the consent box, the failure dialog) holds its
own ``exec()`` loop — a plain sequential script would block behind that
``exec()`` and never reach the next click.

Nothing here answers a dialog by itself: every click is a line in the
journey, printed as it happens, so the log IS the click-by-click record.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESK = Path.home() / "Desktop" / "ChromIQ-engine-challenge"
CHARTS = DESK / "charts"
CHART_924 = CHARTS / "real-rgb-924p-spectral36.ti3"
CHART_1168 = CHARTS / "real-rgb-1168p-spectral106.ti3"
CHART_18 = CHARTS / "real-rgb-18p-cr30.ti3"
CHART_315 = CHARTS / "real-rgb-315p-scanner-measured.ti3"
WORK_B = DESK / "work-B"
WORK_B.mkdir(parents=True, exist_ok=True)


def say(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sandbox(name: str) -> Path:
    p = DESK / "sandboxes" / f"B-{name}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_journey(h, gen, *, timeout: float = 1800.0) -> None:
    """Drive ``gen`` (a generator yielding pause-ms) from a QTimer, then
    return once it is exhausted. Exceptions inside the journey are printed
    and stop the journey; the app stays alive so a screenshot can be taken."""
    from PyQt6.QtCore import QTimer
    state = {"done": False, "error": None, "next": 0.0, "busy": False}

    def _tick():
        if state["done"] or state["busy"] or time.monotonic() < state["next"]:
            return
        state["busy"] = True
        try:
            pause = next(gen)
            state["next"] = time.monotonic() + (pause or 0) / 1000.0
        except StopIteration:
            state["done"] = True
        except Exception as exc:          # noqa: BLE001 — recorded, not hidden
            import traceback
            traceback.print_exc()
            state["error"] = exc
            state["done"] = True
        finally:
            state["busy"] = False

    t = QTimer()
    t.timeout.connect(_tick)
    t.start(30)
    end = time.monotonic() + timeout
    while not state["done"] and time.monotonic() < end:
        h.pump(50)
    t.stop()
    if not state["done"]:
        say("!! journey timed out")
    if state["error"] is not None:
        say(f"!! journey raised: {state['error']!r}")


def click(widget, *, deferred: bool = True) -> None:
    """A real mouse click at the widget's centre (QTest), not ``.click()``.

    DEFERRED by default: a click that opens a modal runs ``dlg.exec()`` — a
    nested event loop — and a journey generator that performs the click
    synchronously would be stuck inside it (the stepper's timer then finds
    the generator already executing). ``QTimer.singleShot(0)`` lets the
    generator yield first; the click lands on the next loop iteration.
    """
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtTest import QTest
    if deferred:
        QTimer.singleShot(0, lambda: QTest.mouseClick(widget, Qt.MouseButton.LeftButton))
    else:
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)


def click_tab(tabwidget, label: str) -> int:
    """Click the tab whose text is ``label`` on the real tab bar."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    bar = tabwidget.tabBar()
    for i in range(bar.count()):
        if bar.tabText(i) == label:
            QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=bar.tabRect(i).center())
            return i
    raise LookupError(f"no tab {label!r}: {[bar.tabText(i) for i in range(bar.count())]}")


def screencapture(path: Path) -> Path:
    """Whole-screen PNG through macOS ``screencapture`` (the only way to
    see a popup or a modal exactly as the user does)."""
    subprocess.run(["screencapture", "-x", str(path)], timeout=15, check=False)
    return path


def grab(widget, path: Path) -> Path:
    widget.grab().save(str(path))
    return path


def active_modal(h):
    return h.app.activeModalWidget()


def modal_title(h) -> str | None:
    d = active_modal(h)
    return d.windowTitle() if d is not None else None


def buttons_of(dlg) -> list:
    from PyQt6.QtWidgets import QAbstractButton
    return [b for b in dlg.findChildren(QAbstractButton) if b.isVisible()]


def button_named(dlg, text: str):
    for b in buttons_of(dlg):
        if b.text().replace("&", "").strip() == text:
            return b
    return None


def text_fits(button) -> tuple[bool, int, int]:
    """(fits, needed px, available px) — does the label fit inside the
    button as painted?"""
    from PyQt6.QtGui import QFontMetrics
    need = QFontMetrics(button.font()).horizontalAdvance(button.text().replace("&", ""))
    have = button.width() - 16
    return need <= have, need, have


def tooltip_bodies(widget) -> dict[str, str]:
    """title → body of every TooltipButton under ``widget``."""
    from ui.tooltip_button import TooltipButton
    return {t._title: t.dialog_body() for t in widget.findChildren(TooltipButton)}


def build_log(h) -> list[str]:
    return h.win._tab_profile._log.toPlainText().splitlines()


def wait_for_build(h, gen_timeout: float = 900.0):
    """Generator: wait until the Build button is enabled again, printing a
    heartbeat; yields control to the loop while waiting."""
    prof = h.win._tab_profile
    t0 = time.monotonic()
    last = 0.0
    while time.monotonic() - t0 < gen_timeout:
        if time.monotonic() - last > 10.0:
            last = time.monotonic()
            tail = (prof._log.toPlainText().splitlines() or [""])[-1]
            say(f"  [build {time.monotonic()-t0:4.0f}s] running={prof._engine_builder.is_running or prof._runner.is_running} "
                f"modal={modal_title(h)} last={tail[:100]!r}")
        if prof._build_btn.isEnabled() and not prof._engine_builder.is_running \
                and not prof._runner.is_running:
            return
        yield 200
    say("!! build did not finish in time")


def defaults_read() -> str:
    r = subprocess.run(["defaults", "read", "com.chromiq.ChromIQ", "custom_output_path"],
                       capture_output=True, text=True, timeout=10, encoding="utf-8")
    return (r.stdout.strip() or r.stderr.strip())


def pick(combo, text: str) -> bool:
    """Open the combo's popup with a real click and click the row ``text``.
    Returns False (and selects by index, i.e. ASSISTED) when the popup did
    not open."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    row = combo.findText(text)
    if row < 0:
        raise LookupError(f"{text!r} not in {[combo.itemText(i) for i in range(combo.count())]}")
    QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
    view = combo.view()
    for _ in range(20):
        QTest.qWait(30)
        if view.isVisible():
            break
    if view.isVisible():
        r = view.visualRect(combo.model().index(row, 0))
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=r.center())
        QTest.qWait(50)
        if combo.currentIndex() == row:
            return True
    combo.hidePopup()
    combo.setCurrentIndex(row)
    return False


def build_and_answer(h, out: Path, tag: str, seen: list, *, shots=(15,),
                     answer=("Done", "OK", "Close"), timeout: float = 900.0):
    """Generator: press the REAL Build button, stream the log, photograph
    the window at ``shots`` seconds, photograph the first modal that
    appears and answer it with the first button named in ``answer`` —
    recording (title, button) in ``seen``. Yields to the loop throughout.
    Returns (elapsed_s, modal_title_or_None)."""
    win, prof = h.win, h.win._tab_profile
    prof._log.clear()
    say(f"[{tag}] Build Profile clicked (mode={prof._current_mode()})")
    t0 = time.monotonic()
    click(prof._build_btn)
    yield 500
    taken, log_seen, title = set(), 0, None
    while True:
        el = time.monotonic() - t0
        for s in shots:
            if el >= s and s not in taken:
                taken.add(s)
                grab(win, out / f"{tag}-building-{s:02d}s.png")
        lines = prof._log.toPlainText().splitlines()
        for ln in lines[log_seen:]:
            say(f"  [{tag} +{el:4.0f}s] {ln}")
        log_seen = len(lines)
        m = active_modal(h)
        if m is not None:
            yield 400
            title = m.windowTitle()
            grab(m, out / f"{tag}-modal.png")
            say(f"  [{tag}] MODAL {title!r} after {el:.0f}s; buttons={[b.text() for b in buttons_of(m)]}")
            from PyQt6.QtWidgets import QLabel
            for lbl in m.findChildren(QLabel):
                if lbl.isVisible() and lbl.text().strip():
                    say(f"      label: {lbl.text()[:300]!r}")
            b = None
            for want in answer:
                b = button_named(m, want)
                if b is not None:
                    break
            seen.append((title, b.text() if b else "?"))
            if b is None:
                say("  !! none of the wanted buttons; leaving the dialog open")
                return el, title
            click(b)
            yield 500
            break
        if prof._build_btn.isEnabled() and not prof._engine_builder.is_running \
                and not prof._runner.is_running and el > 2:
            say(f"  [{tag}] build ended without a modal after {el:.0f}s")
            break
        if el > timeout:
            say("  !! build timeout")
            break
        yield 200
    el = time.monotonic() - t0
    yield 300
    grab(win, out / f"{tag}-after.png")
    (out / f"{tag}-log.txt").write_text(prof._log.toPlainText(), encoding="utf-8")
    say(f"[{tag}] done in {el:.0f}s, modal was {title!r}")
    return el, title


def icc_version(path: Path) -> str:
    b = path.read_bytes()
    return f"{b[8]}.{b[9] >> 4}.{b[9] & 15}"
