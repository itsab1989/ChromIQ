"""Small drivers of the Measurement Report window for tests (K31).

Until K31 a test made the window produce a report type by storing the type on
the RUN (`set_run_report_type`), because a one-run window followed the run's
type. Since K31 the type is the REPORT's (Knut, #182 5801677743: *"settings
belongs to the report"*), so a test chooses it the way a user does: in the
"Report type" pulldown, or as the Preferences default a new report starts on.
"""
from __future__ import annotations


def choose_report_type(dlg, type_id: str) -> None:
    """Pick *type_id* in the window's "Report type" pulldown, as a user does.

    Goes through `_on_type_chosen`, so a type the measurement's kind does not
    allow, or one this build cannot produce, is refused exactly as on screen.
    """
    dlg._sync_limit_controls()
    combo = dlg._type_combo
    i = combo.findData(type_id)
    if i < 0:
        raise AssertionError(f"the pulldown does not offer {type_id!r}")
    if combo.currentIndex() == i:
        dlg._on_type_chosen(i)
    else:
        combo.setCurrentIndex(i)


def prefer_report_type(settings, type_id: str) -> None:
    """Make *type_id* the Preferences > Reports default a NEW report starts
    on, which is what a window opening on "New report..." and the report
    written after a measurement use (K31)."""
    settings.set("report_default_type", type_id)
