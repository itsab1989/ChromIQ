"""CMY printers for the research battery (Agent 66, 2026-10-15).

Until now no CMY device (3 inks, no black) was in the battery although the
engine builds CMY profiles (ProfileEngineResearch Findings agent65-02 s0).
They live in their own module because ``printers.py`` is part of the sealed
set's generator hash (tests/test_benchmarks_research_v31.py); ``run.py`` and
``v31tools/preseed.py`` use :func:`build_printers_all`.

Two are the existing CMYK truths with the K ink removed (same inks, paper,
dot gain), one is an independent CMY device:

* ``S3c``  S3 (YNSN, September's inks) without K, no ink limit (300 %)
* ``X3c``  X3 (Clapper-Yule, ink spreading, trapping) without K, TAC 260 %
* ``X3cm`` Clapper-Yule CMY on warm matte stock with much more dot gain (TVI
  0.30 alone / 0.18 on other inks vs 0.17 / 0.09), weaker trapping (0.80 vs
  0.88), less internal reflection (r_i 0.55) and a 240 % limit: a different
  tone response and a lighter, warmer CMY black.
"""
from __future__ import annotations

from benchmarks.research.printers import (ClapperYuleTruth, TruthPrinter, YnsnTruth,
                                          build_printers)

CMY_PRINTERS = ("S3c", "X3c", "X3cm")


def cmy_printers() -> dict[str, TruthPrinter]:
    from benchmarks.synthetic import SyntheticPrinter
    return {"S3c": YnsnTruth(SyntheticPrinter("S3c", "CMY", tac=None, yn_nu=4.0)),
            "X3c": ClapperYuleTruth("X3c", "CMY", tac=260.0),
            "X3cm": ClapperYuleTruth("X3cm", "CMY", tac=240.0, paper="matte", r_i=0.55,
                                     trap=0.80, gain_alone=0.30, gain_super=0.18)}


def build_printers_all() -> dict[str, TruthPrinter]:
    out = build_printers()
    out.update(cmy_printers())
    return out
