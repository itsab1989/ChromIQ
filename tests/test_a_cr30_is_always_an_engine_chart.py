"""A CR30 chart is laid out by ChromIQ in EVERY mode, so Manual gets B8-560.

Sebastian asked whether the stamp clearance built for Guided could be reached
in Manual as well, or whether it needed options that do not exist yet, such as
independent font sizes for the strip labels and the row labels.

It needs nothing. B8-560's clearance comes from `Geom.side_stamp_freed_mm`,
which records what ChromIQ's own row-label walk gave up and is handed to the
stamper as a minimum patch-side gap. `chart_creator` computes it only for an
engine chart, deliberately: printtarg lays its own pages out, so asking OUR
geometry what it freed would hand the stamper a number about a page that was
never drawn.

And a CR30 is always an engine chart. `ENGINE_ONLY_INSTRUMENTS` is tested ahead
of the mode and ahead of the Manual engine toggle, because printtarg cannot lay
a CR30 out at all. Measured with the real geometry, same params in both modes,
A3: Guided 0.40481250000000024 mm and Manual 0.40481250000000024 mm.

So the answer is about the INSTRUMENT, not the mode, and this test pins the
half that makes it true.
"""
from __future__ import annotations

import dataclasses

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.settings import AppSettings
from workflow.chart_creator import (ENGINE_ONLY_INSTRUMENTS, ChartCreator,
                                    ChartParams)


@pytest.fixture()
def creator(qapp, tmp_path):
    s = AppSettings()
    from PyQt6.QtCore import QSettings
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return ChartCreator(ArgyllRunner(s), FileManager(s), s), s


def _params(**kw) -> ChartParams:
    fields = {f.name for f in dataclasses.fields(ChartParams)}
    return ChartParams(**{k: v for k, v in kw.items() if k in fields})


@pytest.mark.parametrize("manual", [False, True], ids=["guided", "manual"])
@pytest.mark.parametrize("engine_setting", [True, False],
                         ids=["engine-on", "engine-off"])
def test_a_cr30_is_always_an_engine_chart(creator, manual, engine_setting):
    """All four combinations, because any one of them falling through to
    printtarg would silently cost that chart the stamp clearance.

    MUTATION: drop "CR30" from `ENGINE_ONLY_INSTRUMENTS` in
    `workflow/chart_creator.py` and the manual/engine-off case goes red.
    """
    cc, s = creator
    s.set("use_chromiq_layout_engine", engine_setting)
    assert "CR30" in ENGINE_ONLY_INSTRUMENTS, (
        "a CR30 is no longer forced onto ChromIQ's engine, so a Manual CR30 "
        "chart can reach printtarg, which cannot lay one out at all"
    )
    assert cc._should_use_engine(_params(instrument="CR30", paper="A4",
                                         is_manual=manual)), (
        f"a CR30 chart went to printtarg with is_manual={manual} and the "
        f"engine setting {engine_setting}; it would lose the stamp clearance "
        f"and printtarg cannot lay a CR30 out in the first place"
    )


def test_the_clearance_is_the_same_in_both_modes_on_a_cr30(creator):
    """The geometry, not just the branch: same number, both modes.

    Asked of A3, because A4 at bare defaults frees nothing on either side and
    a test that compares 0.0 with 0.0 would pass with the mechanism removed.
    """
    from workflow.layout_engine import instruments as inst
    cc, _s = creator

    def gap(manual: bool) -> float:
        p = _params(instrument="CR30", paper="A3", is_manual=manual)
        assert cc._should_use_engine(p)
        g = inst.geom_from_build_kwargs(cc._engine_kwargs(p))
        return float(getattr(g, "side_stamp_freed_mm", 0.0) or 0.0)

    guided, manual = gap(False), gap(True)
    assert guided > 0.0, (
        "A3 frees nothing on either side, so this comparison cannot tell the "
        "mechanism from its absence. Pick a paper where the row-label walk "
        "gives something up."
    )
    assert guided == manual, (
        f"the stamp clearance differs between the modes on a CR30: Guided "
        f"{guided!r}, Manual {manual!r}"
    )
