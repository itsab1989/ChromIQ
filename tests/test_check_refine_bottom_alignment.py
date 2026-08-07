"""Check & Refine's two columns must end level, with the log on or off.

Basti, 2026-08-07: *"in check refine tab in the right panel the buttons run
gamut analysis, reset view and save as defaults should have the same distance
to the main window on their bottom like those buttons in the left panel"* and,
once that was done, *"in this case when the log is on the distance of the log
to the main window should also be the same. otherwise i see a difference"*.

Measured on screen the step was 5 px with the log off and 3 px with it on.
The agreed line is **13 px above the window edge**, which is where every other
tab's log already sat — a first attempt levelled the column at 15 instead and
made Check & Refine the one tab whose log was out of step with the rest
(*"in check refine log is 1px (?) higher than in the other tabs"* — 2 px).

**These are structural tests, not geometric ones.** The alignment can only be
measured with the real stylesheet on a real window, and MainWindow segfaults
under the offscreen platform the gate runs on — so the gate cannot see the
pixels. What it can do is guard the three decisions that produce them, each of
which was arrived at by measurement and none of which is self-evident from
reading the code:

  * the gamut row's bottom margin is deliberately larger than its top,
  * the log sits in a "log_container" so its 2 px is hidden along with it,
  * that wrapper is added **without** stretch.

The last one is the trap: with ``stretch=1`` the wrapper grows and the
fixed-height log floats 16 px clear of the bottom, which looks like the bug the
change was meant to fix. See ``scripts/``-style probes for the pixel numbers.
"""
from __future__ import annotations

import inspect
import re

from ui import gamut_panel
from ui.tabs import tab_check_refine


def _source_without_comments(obj) -> str:
    """Source with comment lines stripped.

    A test that greps source must not match its own explanation — one already
    passed on a phrase that appeared only in a comment.
    """
    out = []
    for line in inspect.getsource(obj).splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        out.append(line.split("  #")[0])
    return "\n".join(out)


def test_gamut_button_row_keeps_its_enlarged_bottom_margin():
    """15, not 12 — the value that lands the buttons 13 px above the window."""
    src = _source_without_comments(gamut_panel.GamutPanel)
    m = re.search(r"btn_row\.setContentsMargins\(\s*12,\s*6,\s*12,\s*(\d+)\s*\)", src)
    assert m, "the gamut button row's contentsMargins call has moved or changed shape"
    assert int(m.group(1)) == 15, (
        f"bottom margin is {m.group(1)}, expected 15. The buttons render 42 px "
        "tall from a QSS min-height despite setFixedHeight(36), so the overflow "
        "eats into this margin — 12 puts them 10 px above the window instead of "
        "the 13 every log in the app sits at."
    )


def test_the_log_sits_in_a_hideable_container():
    """2 px of the gap ABOVE the log must vanish when the log does."""
    src = _source_without_comments(tab_check_refine.TabCheckRefine)
    assert 'setObjectName("log_container")' in src, (
        "the log's wrapper must be named log_container, or "
        "MainWindow._apply_log_visibility will leave a blank 2 px strip behind "
        "when the log is switched off"
    )
    assert re.search(r"setContentsMargins\(\s*0,\s*2,\s*0,\s*0\s*\)", src), (
        "the wrapper's 2 px TOP margin is the hideable half of the gap above "
        "the log; below the log there is nothing, so it ends level with the "
        "gamut buttons at 13 px"
    )
    assert "left_layout.addSpacing(3)" in src, (
        "the other half of that gap is a plain 3 px spacer that STAYS when the "
        "log is hidden — it is what stops the buttons dropping to 10 px"
    )


def test_the_log_container_is_added_without_stretch():
    """With stretch the wrapper grows and the log floats short of the bottom."""
    src = _source_without_comments(tab_check_refine.TabCheckRefine)
    assert "left_layout.addWidget(log_outer)" in src, (
        "log_outer must be added with no stretch factor"
    )
    assert not re.search(r"addWidget\(\s*log_outer\s*,\s*stretch", src), (
        "log_outer must not be given a stretch: fit_log_height pins the log's "
        "height (min == max), so the stretch goes to the wrapper instead and "
        "leaves the log 16 px above the bottom edge"
    )
