"""Check & Refine never reads the confirmed-patches memory (Knut, #182 5980560281).

Knut, 2026-10-04: *"for Check & Refine we already agreed that confirmed or
non-confirmed high-error patches has no influence, as this feature checks on
the measurements through the built profile, and the resulting high errors from
the Check feature will all be used as part of the recommendations for the
Refining"*, and *"make sure this is remembered as a purpose for the Check &
Refine feature"*.

Beta 7 to 9 left out patches a re-read (and, in beta 9, similar patches)
confirmed. This file fails if anything on the Check & Refine side reaches for
``<stem>.confirmed.json`` again: by its source, and by behaviour with a memory
on disk that confirms patches above the limit.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).parent / "data" / "check_refine"
RUN3 = (DATA / "knut_run3_profcheck.txt").read_text(encoding="utf-8")

#: The Check & Refine side: the tab, the plan it builds, the checker it runs.
CHECK_REFINE_SOURCES = (
    "ui/tabs/tab_check_refine.py",
    "workflow/refine_plan.py",
    "workflow/profcheck_runner.py",
)
#: Anything that would read the memory: the module, its readers, its suffix.
_MEMORY = re.compile(
    r"confirmed_patches|confirmed_locations|confirmed_path|\.confirmed\.json"
    r"|KIND_CONFIRMED|KIND_PEER|CHECK_REFINE_LEAVES_OUT_PEERS")


def _code_only(text: str) -> str:
    """The source without comments and docstrings, which may cite the rule."""
    import ast
    import io
    import tokenize
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING:
            try:
                ast.literal_eval(tok.string)
            except Exception:  # noqa: BLE001 — f-strings stay in
                out.append(tok.string)
            continue
        out.append(tok.string)
    return " ".join(out)


@pytest.mark.parametrize("rel", CHECK_REFINE_SOURCES)
def test_no_check_and_refine_source_names_the_memory(rel):
    code = _code_only((ROOT / rel).read_text(encoding="utf-8"))
    hits = sorted(set(_MEMORY.findall(code)))
    assert not hits, (
        f"{rel} reaches for the confirmed-patches memory ({hits}). Check & "
        "Refine judges every high error through the built profile, whatever "
        "the Measure tab's outlines say (Knut, #182 5980560281).")


def test_the_switch_is_gone():
    import workflow.confirmed_patches as cp
    assert not hasattr(cp, "CHECK_REFINE_LEAVES_OUT_PEERS")


def test_build_plan_takes_no_confirmed_patches():
    import inspect

    from workflow import refine_plan as rp
    params = inspect.signature(rp.build_plan).parameters
    assert "confirmed" not in params
    assert not hasattr(rp.RefinePlan(1.0, 1, 0, 1.0, False), "confirmed_skipped")


def test_the_not_offered_again_lines_are_gone():
    from workflow import measurement_messages as mm
    assert not hasattr(mm, "_CR_CONFIRMED_ONE")
    assert not hasattr(mm, "_CR_CONFIRMED_MANY")
    assert "Not offered again" not in mm.M_CR_STRIPS.body


def test_a_memory_on_disk_changes_nothing_in_the_plan(qapp, tmp_path,
                                                     monkeypatch):
    """A real `.confirmed.json` confirming patches above the limit, beside the
    measurement the check reads: the plan is the same as with none, and the
    memory's readers are never called."""
    import workflow.confirmed_patches as cp
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_check_refine import TabCheckRefine
    from workflow.profcheck_runner import ProfcheckResult

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "work"))
    tab = TabCheckRefine(ArgyllRunner(s), s)
    res = ProfcheckResult(avg_de=0.67, peak_de=4.34, raw_log=RUN3)

    tab._ti3_path = tmp_path / "x.ti3"
    tab._ti3_path.write_text("CTI3\n", encoding="utf-8")
    before = tab._plan_for(res, 2.0)

    cp.write(tab._ti3_path,
             {"I27": {"kind": "confirmed", "de": 4.0, "prev_de": 4.1},
              "C1": {"kind": "peer", "with": ["L26"]},
              "L26": {"kind": "peer", "with": ["C1"]}}, "strip")
    assert cp.confirmed_locations(tab._ti3_path) == {"I27", "C1", "L26"}

    def _never(*_a, **_k):
        raise AssertionError("Check & Refine read the confirmed-patches memory")
    for name in ("load", "read_raw", "confirmed_locations", "confirmed_path"):
        monkeypatch.setattr(cp, name, _never)

    after = tab._plan_for(res, 2.0)
    assert [(a.strip, a.patch) for a in after.offered] == \
        [(a.strip, a.patch) for a in before.offered]
    assert {"I", "C", "L"} <= {a.strip for a in after.offered}
