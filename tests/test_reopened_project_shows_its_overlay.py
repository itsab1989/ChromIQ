"""#159 (Basti, 2026-08-28): the split-patch overlay was missing.

Opening a project is the ONE route that hands the Measure tab the `.ti1`
(`ui/main_window.py::_restore_last_session` → `set_ti1_path(run.chart_ti1)`);
every other caller passes the `.ti2`. `_show_overlay_from_existing_ti3` then
asked `per_patch_overlay` to name each patch from that `.ti1` — and a `.ti1`
is a patch SET, so the only name it can give is the SAMPLE_ID ("103"), while
`_patch_boxes` and `_locate_patch` are keyed by chart location ("A2").

Nothing matched, every patch was dropped by the `page < 0` guard inside
`_on_chart_measured`, and the method still returned True — so the caller
believed the overlay was up and never offered "Tools ▸ Inspect a measurement".
The user saw an unchanged chart and no message at all.

Measured on the real project before the fix: `.ti1` → overlay {} (and True),
`.ti2` → overlay {0: 3}. After: both {0: 3}.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect                                   # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402

from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.tabs.tab_measure import TabMeasure                       # noqa: E402


@pytest.fixture
def tab():
    QApplication.instance() or QApplication([])
    s = AppSettings()
    return TabMeasure(ArgyllRunner(s), s)


@pytest.mark.parametrize("given", ["chart.ti1", "chart.ti2"])
def test_the_reference_chart_is_always_the_ti2(tab, tmp_path, monkeypatch, given):
    """Whichever chart file the tab was handed, the overlay is built from the
    .ti2 — the only file that knows where a patch sits on the sheet."""
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("stub")
    tab._ti1_path = tmp_path / given
    tab._patch_boxes = [{"A1": QRect(0, 0, 10, 10)}]
    monkeypatch.setattr(tab, "_existing_ti3_for_chart", lambda: ti3)

    seen: list[Path] = []

    def _fake(ti3_path, ref):
        seen.append(Path(ref))
        return [{"loc": "A1", "exyz": [50, 50, 50],
                 "xyz": [50, 50, 50], "de": 0.0}]

    import workflow.measurement_report as mr
    monkeypatch.setattr(mr, "per_patch_overlay", _fake)

    tab._show_overlay_from_existing_ti3()

    assert seen, "per_patch_overlay was never called"
    assert seen[0].suffix.lower() == ".ti2", (
        f"overlay built from {seen[0].name} — a .ti1 can only name patches by "
        "SAMPLE_ID, which matches no box and silently paints nothing")


def test_it_does_not_claim_success_when_nothing_was_painted(tab, tmp_path,
                                                            monkeypatch):
    """The silent half of the bug: True with an empty overlay meant the caller
    never fell back to pointing the user at Tools ▸ Inspect a measurement."""
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("stub")
    tab._ti1_path = tmp_path / "chart.ti2"
    tab._patch_boxes = [{"A1": QRect(0, 0, 10, 10)}]
    monkeypatch.setattr(tab, "_existing_ti3_for_chart", lambda: ti3)

    import workflow.measurement_report as mr
    # Every patch names a location this chart does not have, so every one is
    # dropped by the page<0 guard and nothing can be drawn.
    monkeypatch.setattr(mr, "per_patch_overlay", lambda *_a: [
        {"loc": "ZZ99", "exyz": [50, 50, 50], "xyz": [50, 50, 50], "de": 0.0}])

    assert tab._show_overlay_from_existing_ti3() is False, (
        "reported the overlay was painted when the preview is still empty")
