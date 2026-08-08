"""The Tools file-placement audit stays complete, and stays honest.

Knut, 2026-08-08: *"any and all tools that save files need to be updated and
checked if the files saved are placed in the correct place or folder depending
on the profile run and run type selection."*

The audit itself is `scripts/audit_tool_file_placement.py`. These tests guard
the two ways an audit like it goes quietly wrong:

* **It stops being complete.** A tool added later is not audited, and nobody
  notices, because the audit still says "0 unclassified". So the tool list is
  re-derived here from the app's own dispatch and cross-checked with the popup.
* **It starts absolving tools it never looked at.** Its first version filed
  `average` and `merge` under "writes nothing" — both plainly write a `.ti3`,
  via a destination widget and a runner rather than a write call of their own.
  A bucket that quietly clears a tool is worse than no audit, so the known
  writers are pinned.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "audit_tool_file_placement", ROOT / "scripts" / "audit_tool_file_placement.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


#: Tools that are known NOT to put any file on disk. A tool leaving this set
#: means it started saving something and must be placed deliberately; a tool
#: joining it means someone decided it saves nothing, which deserves a look.
KNOWN_SILENT = {"spot_read", "translate", "verify_profile"}

#: Writers whose destination never mentions the folder model, so they cannot be
#: run-type aware. This is a WATCHLIST, not an approval — see the issue.
KNOWN_SHORTLIST = {
    "average", "devicelink_apply", "i1p_to_ti1", "i1p_to_ti3",
    "merge", "profile_info", "softproof",
}


@pytest.fixture(scope="module")
def report():
    reg = audit.tool_keys_and_classes()
    out = {}
    for key, (cls, mod) in reg.items():
        path = audit._module_path(mod)
        assert path.is_file(), f"{key}: module {mod} not on disk"
        res = audit.audit_class(path, cls)
        assert "error" not in res, f"{key}: {res['error']}"
        out[key] = res
    return out


def test_the_audit_can_still_find_the_tools():
    """If the dispatch shape changes, the audit must fail loudly, not return
    an empty list that reads as "nothing to check"."""
    assert len(audit.tool_keys_and_classes()) >= 15


def test_every_popup_entry_has_a_branch():
    """A popup entry with no branch is a button that silently does nothing."""
    reg = set(audit.tool_keys_and_classes())
    dead = audit.popup_keys() - reg - audit.SPECIAL_KEYS
    assert not dead, f"Tools popup offers keys nothing handles: {sorted(dead)}"


def test_every_tool_is_reachable_from_the_popup():
    reg = set(audit.tool_keys_and_classes())
    hidden = reg - audit.popup_keys()
    assert not hidden, f"tools nobody can open: {sorted(hidden)}"


def test_every_tool_is_classified(report):
    """No tool may sit outside the audit's buckets."""
    for key, v in report.items():
        placed = bool(v["writes"] or v["dialogs"] or v["delegated"])
        assert placed or key in KNOWN_SILENT, (
            f"{key} writes nothing according to the audit, but is not in "
            "KNOWN_SILENT. Either it really saves nothing — add it there "
            "deliberately — or the audit cannot see how it saves, which is "
            "the bug that filed 'average' and 'merge' as silent.")


def test_the_silent_tools_are_still_silent(report):
    started = {k for k in KNOWN_SILENT
               if report[k]["writes"] or report[k]["dialogs"]
               or report[k]["delegated"]}
    assert not started, (
        f"{sorted(started)} now save files. Decide where those files belong "
        "for each profile run and run type before removing them from "
        "KNOWN_SILENT.")


def test_no_new_tool_joins_the_shortlist_unnoticed(report):
    """A writer that never mentions Project / Run / Calibration cannot follow
    the run type. New ones must be a deliberate decision, not a discovery."""
    shortlist = {k for k, v in report.items()
                 if (v["writes"] or v["dialogs"] or v["delegated"])
                 and not v["model_aware"]}
    new = shortlist - KNOWN_SHORTLIST
    assert not new, (
        f"{sorted(new)} save files without consulting the folder model. "
        "Give the destination to Project / Run / Calibration, or add it to "
        "KNOWN_SHORTLIST with a reason.")
    fixed = KNOWN_SHORTLIST - shortlist
    assert not fixed, (
        f"{sorted(fixed)} now consult the folder model — remove them from "
        "KNOWN_SHORTLIST so the list keeps meaning something.")
