"""#130 (Knut, beta.120): two faults in the "loaded chart" messages.

**It named a button that had moved.** Open .ti2 now lives at the top left of
the window, but two messages still sent people to Print and Measure:

    *"There text '.... and you can open it again any time from Print and
    Measure.' This should refer to the new Open ti2 button location in
    top-left of window (does not exist in Print and Measure tabs)."*

    *"I then get message 'This chart is loaded from elsewhere', and this window
    also mentions it was loaded from Print and Measure tab. This is again
    wrong."*

**It appeared when nothing had happened.** Choosing a .ti2 that already lives
inside the open project and picking "Continue" copies nothing and moves
nothing:

    *"This is strange, as no import action was performed in this case, so this
    window could be removed in the case when the opened ti2 file came from
    within the same project."*

The same reasoning already kept it away from Duplicate, which shows its own
window because this one is written for a chart arriving from elsewhere.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---- the button is named, and named consistently ------------------------
def test_the_masthead_buttons_lead_with_their_names(qapp):
    """An icon-only button's name IS its tooltip's first line — otherwise a
    message can refer to a name the user has no way to discover."""
    from ui.masthead_header import MastheadHeader
    m = MastheadHeader()
    assert m._load_project_btn.toolTip().startswith("Open Project")
    assert m._load_ti2_btn.toolTip().startswith("Open Chart File (.ti2)")


def test_no_message_sends_anyone_to_print_or_measure_for_the_chart_file():
    """The button is not there any more, so the instruction cannot be followed."""
    import sys
    sys.path.insert(0, ".")
    from scripts.i18n_extract import extract_keys
    guilty = [k for k in extract_keys()
              if "open it again any time from Print" in k
              or "loaded in the Print or Measure tab" in k]
    assert not guilty, guilty


def test_both_messages_point_at_the_real_place():
    import sys
    sys.path.insert(0, ".")
    from scripts.i18n_extract import extract_keys
    joined = "\n".join(extract_keys())
    assert "“Open Chart File (.ti2)” at the top left of the window" in joined


# ---- and it stays quiet when nothing was imported ------------------------
def test_the_notice_is_skipped_for_a_file_already_in_the_project():
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._maybe_warn_reflected_backfill)
    assert "_ti2_is_inside_current_project" in src
    i = src.index("_ti2_is_inside_current_project")
    assert "return" in src[i:i + 120], "it has to actually skip, not just ask"


def test_inside_means_under_the_projects_own_root(tmp_path):
    """A path check, not a name check: two projects can hold files with the
    same name, and the question is which folder owns this one."""
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._ti2_is_inside_current_project)
    assert ".parents" in src, "must test containment, not equality of names"
    assert "resolve()" in src, "symlinks and .. must not decide it"


def test_a_missing_project_is_not_inside_anything():
    """The guard must never turn a broken lookup into "skip the message"."""
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._ti2_is_inside_current_project)
    assert "return False" in src.split("except")[-1]
