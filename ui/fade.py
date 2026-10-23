"""A short opacity fade, shared by the preview's legend chip and the Measure
tab's pause note (Basti, 2026-10-23: the note "should take an example on the
measured vs expected overlay ... the animation when it comes and goes, so it
is not completely instant but a fast fade").

ONE animation object per fade, retargeted, never stopped and replaced: the
legend's first version created a fresh animation each time and stopped the
old one, and sweeping the pointer on and off the chip SEGFAULTED, because the
reversal happens inside the running animation's own callback chain. Reusing
one object cannot hit that, and a reversal continues from where the fade had
got to instead of snapping to the far end.

The step callback must be a BOUND METHOD (CLAUDE.md: never a self-capturing
lambda on a signal a widget's own child emits).
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QEasingCurve, QObject, QVariantAnimation

#: How long a fade takes, in ms. Short on purpose: something getting out of
#: the way (or arriving), not an effect; long enough that the eye reads it as
#: movement rather than a blink.
FADE_MS = 110


class Fade(QObject):
    """Drive a value between 0.0 and 1.0 with an OutCubic curve.

    ``run(current, target)``: STOP FIRST, THEN DECIDE. A fade already close
    enough to its target settles there exactly (the step is called once with
    *target*), and the running one is stopped either way, so a re-hide asked
    for while a show is just starting can never be carried on to 1.0 by the
    show (the legend's F1).
    """

    def __init__(self, parent: QObject, step: Callable[[float], None],
                 duration_ms: int = FADE_MS,
                 finished: "Callable[[], None] | None" = None) -> None:
        super().__init__(parent)
        self._step = step
        self._finished = finished
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(int(duration_ms))
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._on_value)
        self.animation.finished.connect(self._on_finished)
        self.target = 1.0

    def run(self, current: float, target: float) -> None:
        self.animation.stop()
        self.target = float(target)
        if abs(float(current) - self.target) < 0.01:
            self._step(self.target)
            self._on_finished()
            return
        self.animation.setStartValue(float(current))
        self.animation.setEndValue(self.target)
        self.animation.start()

    def stop(self) -> None:
        self.animation.stop()

    def running(self) -> bool:
        from PyQt6.QtCore import QAbstractAnimation
        return self.animation.state() == QAbstractAnimation.State.Running

    def _on_value(self, value) -> None:
        self._step(float(value))

    def _on_finished(self) -> None:
        if self._finished is not None:
            self._finished()
