"""Lengths shown in millimetres or inches (the page-output Beta's "Units").

THE VALUE IS ALWAYS MILLIMETRES. A :class:`LengthSpinBox` is a
``NoScrollDoubleSpinBox`` whose ``value()``, ``setValue()``, ``setRange()``,
``minimum()``, ``maximum()`` and ``valueChanged`` speak millimetres whatever
the person sees, so every line of the layout panel that reads or writes a
length (the recipe, the presets, the instrument defaults, an instrument's own ranges)
is untouched by the choice. Inches are a DISPLAY: the text in the box, what
is typed into it, and the arrow steps.

With millimetres chosen the box is its base class exactly: every override
hands straight to it, so ranges, steps, decimals and values are 4.3.43's
(``tests/test_units_choice.py`` probes them against a plain box).

With inches chosen:

* the box shows ``mm / 25.4`` with :data:`IN_EXTRA` more decimals than its
  millimetres had (one decimal of a millimetre becomes three of an inch:
  0.001 in is 0.0254 mm), and the suffix " mm" becomes " in"; a box that
  showed no unit gets " in", so a bare number never reads as millimetres;
* what is typed is the inch value; it is stored as ``inches x 25.4`` with one
  decimal more than it was typed with, which holds it EXACTLY (0.25 in is
  stored as 6.35 mm and shown as 0.25 again). A text that is still what the
  box shows (Return, or leaving the box, with nothing typed) gives back the
  stored value untouched, so looking at a value in inches never moves it;
* a value set by the program (a recipe, a preset, an instrument's default) is
  rounded exactly as the millimetre box would have rounded it, so a preset
  saved with inches chosen is byte for byte the one saved with millimetres;
  EXCEPT a value that could only have been typed in inches (one on the inch
  grid of this box, finer than its millimetres: 6.35 is 0.25 in), which is
  kept exactly in either unit, so a length typed in inches survives a
  project reopened, a preset loaded and Save as Defaults read back (review
  P1-1). Every value a 4.3.43 recipe holds has the box's own decimals and
  loads exactly as before;
* the arrows step :data:`IN_STEP` inches from the value shown, and steps
  that add up to nothing give the value back exactly (review P1-3); the
  largest and smallest values shown can be typed back to the exact limit.

Back to millimetres, a value typed in inches that the millimetre box cannot
show at its own decimals (6.35 in a box of one decimal) is kept, and the box
shows the decimals it needs until the value is one it can show again: the
switch itself never changes a length.
"""
from __future__ import annotations

import re

from ui.widgets import NoScrollDoubleSpinBox

MM_PER_INCH = 25.4
#: Units a length can be shown in.
LEN_MM = "mm"
LEN_IN = "in"
#: How many more decimals a length shows in inches than in millimetres.
IN_EXTRA = 2
#: One arrow step in inches.
IN_STEP = 0.01

_NUMBER = re.compile(r"^[+-]?\d*(?:[.,]\d*)?$")


def _round_like_qt(value: float, decimals: int) -> float:
    """What a QDoubleSpinBox of *decimals* holds for *value*.

    Qt rounds by printing the number with that many decimals in the C
    locale, and its printing takes an exact half AWAY from zero (2.25 holds
    as 2.3), where Python's own formatting takes it to the even neighbour
    (2.2). So this prints the way Qt prints (review P1-2: 620 of 80,002
    values differed, and a recipe value ending in 25 loaded 0.1 mm apart
    with inches shown and with millimetres shown)."""
    from PyQt6.QtCore import QLocale
    return float(QLocale.c().toString(float(value), "f", int(decimals)))


def _decimals_needed(value: float, most: int) -> int:
    """The fewest decimals (up to *most*) that hold *value* exactly."""
    for d in range(0, int(most) + 1):
        if abs(_round_like_qt(value, d) - float(value)) < 1e-9:
            return d
    return int(most)


class LengthSpinBox(NoScrollDoubleSpinBox):
    """A length field whose value is millimetres, shown in mm or inches."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._len_unit = LEN_MM
        #: the box's millimetre settings, kept while inches are shown
        self._mm_decimals = None
        self._mm_step = None
        self._mm_suffix = None
        #: (value before the first arrow step, net steps, value after them)
        self._step_memo = None
        self.editingFinished.connect(self._settle_mm_decimals)

    # ---- the unit ---------------------------------------------------------------

    def length_unit(self) -> str:
        return self._len_unit

    def _own_mm_decimals(self) -> int:
        """The decimals the box has in millimetres (the panel's own)."""
        return int(self._mm_decimals if self._mm_decimals is not None
                   else super().decimals())

    def _in_decimals(self) -> int:
        return self._own_mm_decimals() + IN_EXTRA

    def _inch_typed(self, value: float) -> "float | None":
        """*value* as kept when it could only have been typed in inches (on
        this box's inch grid and finer than its millimetres), else None."""
        mm_dec = self._own_mm_decimals()
        d_in = mm_dec + IN_EXTRA
        v = float(value)
        inches = v / MM_PER_INCH
        if abs(_round_like_qt(inches, d_in) - inches) > 1e-9:
            return None
        kept = _round_like_qt(v, d_in + 1)
        if _decimals_needed(kept, d_in + 1) <= mm_dec:
            return None
        return kept

    def set_length_unit(self, unit: str) -> None:
        """Show the length in *unit* ("mm" or "in"). Never changes the value."""
        unit = LEN_IN if unit == LEN_IN else LEN_MM
        if unit == self._len_unit:
            return
        before = self.value()
        self._step_memo = None
        if unit == LEN_IN:
            if self._mm_decimals is None:
                # the box's own millimetre decimals, taken once: later they
                # may be raised for a value typed in inches, and
                # `setDecimals` keeps this up to date
                self._mm_decimals = super().decimals()
            # the step and the suffix shown in millimetres right now
            self._mm_step = super().singleStep()
            self._mm_suffix = self.suffix()
            self._len_unit = LEN_IN
            # more decimals hold every value the box held, unchanged
            super().setDecimals(self._in_decimals() + 1)
            super().setSingleStep(IN_STEP * MM_PER_INCH)
            from core.i18n import tr
            # a box whose row label names the unit ("Margins (in):") shows
            # a bare number, as it did in millimetres; any other says "in"
            bare = getattr(self, "_unit_in_label", False) and \
                not self._mm_suffix
            self.setSuffix("" if bare else " " + tr("in"))
        else:
            self._len_unit = LEN_MM
            mm_dec = int(self._mm_decimals)
            # a value typed in inches the box cannot show at its own decimals
            # is kept: the box shows what it needs (never rounded by a switch)
            super().setDecimals(max(mm_dec, _decimals_needed(
                before, super().decimals())))
            super().setSingleStep(self._mm_step)
            self.setSuffix(self._mm_suffix or "")    # redraws the text

    def _settle_mm_decimals(self) -> None:
        """Millimetres shown with extra decimals (a value typed in inches):
        back to the box's own decimals once the value fits them."""
        if self._len_unit != LEN_MM or self._mm_decimals is None:
            return
        mm_dec = int(self._mm_decimals)
        if super().decimals() > mm_dec and \
                _decimals_needed(self.value(), super().decimals()) <= mm_dec:
            super().setDecimals(mm_dec)

    # ---- settings the panel makes in millimetres --------------------------------

    def setDecimals(self, decimals):          # noqa: N802 - Qt's name
        if self._len_unit == LEN_IN:
            self._mm_decimals = int(decimals)
            super().setDecimals(self._in_decimals() + 1)
            return
        if self._mm_decimals is not None:
            self._mm_decimals = int(decimals)
        super().setDecimals(decimals)

    def setSingleStep(self, step):            # noqa: N802 - Qt's name
        if self._len_unit == LEN_IN:
            self._mm_step = float(step)
            return
        super().setSingleStep(step)

    def setValue(self, value):                # noqa: N802 - Qt's name
        """A value set by the program: held exactly as the millimetre box
        holds it, whatever unit is shown; a value typed in inches earlier
        (6.35, 0.25 in) is held exactly too (:meth:`_inch_typed`)."""
        mm_dec = self._own_mm_decimals()
        kept = self._inch_typed(value)
        if self._len_unit == LEN_IN:
            super().setValue(kept if kept is not None
                             else _round_like_qt(value, mm_dec))
            return
        want = mm_dec if kept is None else max(
            mm_dec, _decimals_needed(kept, mm_dec + IN_EXTRA + 1))
        if super().decimals() != want:
            # millimetres shown with the decimals the value needs (raised
            # for a value typed in inches, back to the box's own otherwise)
            if self._mm_decimals is None:
                self._mm_decimals = mm_dec
            old, old_text = self.value(), self.text()
            blocked = self.blockSignals(True)
            try:
                super().setDecimals(want)
                super().setValue(value if kept is None else kept)
            finally:
                self.blockSignals(blocked)
            if self.value() != old:
                self.valueChanged.emit(self.value())
            if self.text() != old_text:
                self.textChanged.emit(self.text())
            return
        super().setValue(value if kept is None else kept)

    # ---- the display ----------------------------------------------------------

    def textFromValue(self, value):           # noqa: N802 - Qt's name
        if self._len_unit != LEN_IN:
            return super().textFromValue(value)
        d = self._in_decimals()
        text = self.locale().toString(float(value) / MM_PER_INCH, "f", d)
        group = self.locale().groupSeparator()
        return text.replace(group, "") if group else text

    def _core_text(self, text: str) -> str:
        core = text
        pre, suf = self.prefix(), self.suffix()
        if pre and core.startswith(pre):
            core = core[len(pre):]
        if suf:
            if core.endswith(suf):
                core = core[:-len(suf)]
            elif suf.strip() and core.rstrip().endswith(suf.strip()):
                core = core.rstrip()[:-len(suf.strip())]
        return core.strip()

    def _inches_of(self, text: str) -> "float | None":
        core = self._core_text(text).replace(",", ".")
        try:
            return float(core)
        except ValueError:
            return None

    def valueFromText(self, text):            # noqa: N802 - Qt's name
        if self._len_unit != LEN_IN:
            value = super().valueFromText(text)
            mm_dec = self._own_mm_decimals()
            if super().decimals() > mm_dec and value != self.value() and \
                    self._inch_typed(value) is None:
                # millimetres shown with extra decimals for a value typed in
                # inches: a millimetre value typed there is the box's own
                # kind, at its own decimals, as a program set would keep it
                value = _round_like_qt(value, mm_dec)
            return value
        # nothing typed: the stored value, untouched (no drift from looking)
        if self._core_text(text) == self._core_text(
                self.textFromValue(self.value())):
            return self.value()
        inches = self._inches_of(text)
        if inches is None:
            return self.value()
        d = self._in_decimals()
        # the largest (smallest) value shown, typed back, is the limit itself
        # (300 mm shows as 11.811 in, which is 299.9994 mm; review P1-4)
        for limit in (self.maximum(), self.minimum()):
            if _round_like_qt(inches, d) == _round_like_qt(
                    limit / MM_PER_INCH, d):
                return float(limit)
        return _round_like_qt(inches * MM_PER_INCH, d + 1)

    def validate(self, text, pos):            # noqa: N802 - Qt's name
        if self._len_unit != LEN_IN:
            return super().validate(text, pos)
        from PyQt6.QtGui import QValidator
        S = QValidator.State
        special = self.specialValueText()
        if special and text == special:
            return S.Acceptable, text, pos
        core = self._core_text(text)
        if core in ("", "+", "-", ".", ",", "-.", "-,", "+.", "+,"):
            if core.startswith("-") and self.minimum() >= 0:
                return S.Invalid, text, pos
            return S.Intermediate, text, pos
        if not _NUMBER.match(core):
            return S.Invalid, text, pos
        frac = re.split(r"[.,]", core)
        if len(frac) == 2 and len(frac[1]) > self._in_decimals():
            return S.Invalid, text, pos
        inches = self._inches_of(text)
        if inches is None:
            return S.Intermediate, text, pos
        mm = inches * MM_PER_INCH
        lo, hi = self.minimum(), self.maximum()
        eps = 0.5 * 10 ** -self._in_decimals() * MM_PER_INCH
        if mm > hi + eps or (inches < 0 and lo >= 0):
            return S.Invalid, text, pos
        if mm < lo - eps:
            return (S.Invalid if inches < 0 else S.Intermediate), text, pos
        return S.Acceptable, text, pos

    def fixup(self, text):                    # noqa: N802 - Qt's name
        if self._len_unit != LEN_IN:
            return super().fixup(text)
        return text

    def stepBy(self, steps):                  # noqa: N802 - Qt's name
        if self._len_unit != LEN_IN:
            return super().stepBy(steps)
        d = self._in_decimals()
        memo = self._step_memo
        if memo is not None and self.value() == memo[2]:
            # still stepping: from the value before the first step
            origin, net = memo[0], memo[1] + int(steps)
        else:
            origin, net = self.value(), int(steps)
        if net == 0:
            # up and down again: the value is given back exactly (P1-3)
            mm = origin
        else:
            shown = _round_like_qt(origin / MM_PER_INCH, d)
            target = _round_like_qt(shown + net * IN_STEP, d)
            mm = _round_like_qt(target * MM_PER_INCH, d + 1)
            mm = min(max(mm, self.minimum()), self.maximum())
        super().setValue(mm)
        self._step_memo = (origin, net, self.value())
        self.selectAll()
