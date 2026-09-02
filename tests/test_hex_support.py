"""SpectroScan hexagonal-chart detection (Knut #126).

Detection decides where the hexagon SHAPE matters — the measure overlay, the
strip zigzag, the scanner tools' alignment cells — so it must be exact. It no
longer blocks anything: the scanner features were refused on the premise that a
CHT cannot describe a hexagon, which is true of the printed shape and irrelevant
to the sampling rectangle a CHT actually carries.
"""
from __future__ import annotations

import json

from workflow.hex_support import chart_is_hexagonal, recipe_is_hexagonal


def test_recipe_is_hexagonal_dict_and_object():
    assert recipe_is_hexagonal({"instrument": "SS", "hflag": True}) is True
    assert recipe_is_hexagonal({"instrument": "SS", "hflag": False}) is False
    # hflag is SpectroScan-only: a stray hflag on another instrument is not hex.
    assert recipe_is_hexagonal({"instrument": "i1", "hflag": True}) is False
    assert recipe_is_hexagonal({}) is False
    assert recipe_is_hexagonal(None) is False

    class _R:
        instrument = "SS"
        hflag = True
    assert recipe_is_hexagonal(_R()) is True


def test_chart_is_hexagonal_reads_channels_json(tmp_path):
    # A SpectroScan hex chart's sidecar.
    (tmp_path / "chart.channels.json").write_text(
        json.dumps({"layout": {"recipe": {"instrument": "SS", "hflag": True}}}), encoding="utf-8")
    (tmp_path / "chart.ti2").write_text("x", encoding="utf-8")
    assert chart_is_hexagonal(tmp_path / "chart.ti2") is True
    assert chart_is_hexagonal(tmp_path / "chart.ti3") is True   # by stem
    assert chart_is_hexagonal(tmp_path / "chart.channels.json") is True

    # A rectangular SpectroScan chart is fine.
    (tmp_path / "flat.channels.json").write_text(
        json.dumps({"layout": {"recipe": {"instrument": "SS", "hflag": False}}}), encoding="utf-8")
    assert chart_is_hexagonal(tmp_path / "flat.ti2") is False

    # Fail open: no sidecar, unreadable, or None → not hex (never blocks blindly).
    assert chart_is_hexagonal(tmp_path / "missing.ti2") is False
    assert chart_is_hexagonal(None) is False


def test_nothing_refuses_a_hexagonal_chart_any_more():
    """The refusal is gone from all three places it lived, and so is the message
    that justified it. Measured end to end before removing them: real scanin
    returned 0 on a 150-hexagon chart and real colprof built a profile from the
    result."""
    import inspect
    import ui.dialogs.scanin_dialog as sd
    import ui.dialogs.scanin_target_dialog as std
    import ui.tabs.tab_chart as tc
    from workflow import hex_support

    assert not hasattr(hex_support, "hex_unsupported_message")
    for mod in (sd, std, tc):
        assert "hex_unsupported_message" not in inspect.getsource(mod), (
            f"{mod.__name__} still refuses hexagonal charts")
    # the target dialog keeps the hook, and it must answer "not rejected"
    assert std.ScaninTargetDialog._reject_if_hexagonal(None, None) is False
