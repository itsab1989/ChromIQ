"""The ISO 12647 values are PREPARED to ship, values only (#182 S-2, §23).

DIN's legal department answered the owner in writing on 2026-09-23: using only
a standard's values, with no images, pages or texts, is not reproduction. The
repository's `data/compliance_sets/iso12647.json` is therefore allowed to carry
ISO 12647-7 and ISO 12647-8 values, and filling it waits on the owner's
explicit go-ahead. Everything else is done, and this file holds it in place
for both states:

* the shipped file holds each set EMPTY or COMPLETE, never half of one;
* a shipped set judges its read-only column, and the Custom column beside it
  keeps Knut's researched figures (§2a: only a licence holder's own file comes
  before them);
* a licence holder's own number still wins its row, and a null they leave in
  the template does not blank a shipped figure;
* every sentence that said "ChromIQ ships none" says what actually ships;
* `scripts/install_iso_12647_values_into_repo.py` copies only the two set
  objects and prints no value.

**NO VALUE FROM EITHER STANDARD IS IN THIS FILE, AND NONE MAY BE.** The shipped
state is simulated with a fixture of made-up placeholders (`FAKE`, below),
stood in for the shipped file through `compliance_sets._bundled_iso_path`. A
test here asserts counts, kinds and sources, never a real limit, and never
reads the licence holder's own file.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import compliance_sets as cs                          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPO_FILE = ROOT / "data" / "compliance_sets" / "iso12647.json"
SCRIPT = ROOT / "scripts" / "install_iso_12647_values_into_repo.py"

#: A placeholder no standard uses for anything. Clearly fake, on purpose.
FAKE = 9.87


def _judgeable(set_id: str) -> "set[str]":
    return {r for r in cs._ISO_ROWS[set_id]
            if cs.ROW_BY_ID[r].status in ("now", "build", "ref")}


def _fake_set(set_id: str) -> "dict[str, float]":
    return {r: FAKE for r in cs._ISO_ROWS[set_id]}


def _cell_is_a_value(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return math.isfinite(float(v))
    if isinstance(v, list) and len(v) == 2 and v[1] == "should":
        return _cell_is_a_value(v[0])
    return False


@pytest.fixture
def shipped(tmp_path, monkeypatch):
    """Stand a FAKE file in for the SHIPPED one. `sets` names which ship."""
    def use(sets=("iso_12647_8",), user: "dict | None" = None):
        doc = {"_readme": "fake placeholders for a test",
               "iso_12647_7": {}, "iso_12647_8": {}}
        for sid in sets:
            doc[sid] = _fake_set(sid)
        bundled = tmp_path / "shipped-iso12647.json"
        bundled.write_text(json.dumps(doc), encoding="utf-8")
        monkeypatch.setattr(cs, "_bundled_iso_path", lambda: bundled)
        if user is None:
            # the rule every test and driver keeps: the variable is FORCED,
            # here at the file standing in for the shipped one
            monkeypatch.setenv(cs.ISO_DATA_ENV, str(bundled))
        else:
            own = tmp_path / "licence-holders-own.json"
            own.write_text(json.dumps(user), encoding="utf-8")
            monkeypatch.setenv(cs.ISO_DATA_ENV, str(own))
        cs.reset_iso_cache()
        return bundled
    yield use
    cs.reset_iso_cache()


# ------------------------------------------------------------ the data file
def test_each_set_in_the_shipped_file_is_empty_or_complete():
    """Half a set would be the worst state: some cells judging with the
    standard's values and the rest reading "?", under a column that says it
    holds the standard's values. So a set ships whole or not at all."""
    doc = json.loads(REPO_FILE.read_text(encoding="utf-8"))
    assert set(doc) == {"_readme", "iso_12647_7", "iso_12647_8"}, (
        "the shipped file carries a key nothing reads")
    for sid in ("iso_12647_7", "iso_12647_8"):
        cells = doc[sid]
        assert isinstance(cells, dict), sid
        if not cells:
            continue
        unknown = set(cells) - set(cs._ISO_ROWS[sid])
        assert not unknown, f"{sid} carries rows that standard does not limit: {sorted(unknown)}"
        missing = _judgeable(sid) - set(cells)
        assert not missing, f"{sid} is only partly filled; missing {sorted(missing)}"
        bad = sorted(r for r, v in cells.items() if not _cell_is_a_value(v))
        assert not bad, f"{sid}: cells that are not a number or [number, \"should\"]: {bad}"


def test_the_shipped_files_readme_says_what_it_rests_on():
    readme = json.loads(REPO_FILE.read_text(encoding="utf-8"))["_readme"]
    # DIN's own words, and an English translation beside them
    assert "nur Werte aus der Norm verwenden" in readme
    assert "nicht unter Vervielfältigung" in readme
    assert "does not count as reproduction" in readme
    assert "2026-09-23" in readme
    for std in ("ISO 12647-7", "ISO 12647-8"):
        assert std in readme
    assert "EMPTY or COMPLETE" in readme
    assert "go-ahead" in readme
    assert "—" not in readme, "no em dash"


def test_shipped_iso_sets_names_exactly_the_sets_the_repository_file_fills(
        monkeypatch):
    """What the rest of the suite measures against, read off the file."""
    doc = json.loads(REPO_FILE.read_text(encoding="utf-8"))
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(REPO_FILE))
    try:
        cs.reset_iso_cache()
        want = tuple(sid for sid in ("iso_12647_7", "iso_12647_8") if doc[sid])
        assert cs.shipped_iso_sets() == want
    finally:
        cs.reset_iso_cache()


# ----------------------------------------------------- a set that ships
def test_a_shipped_set_judges_its_read_only_column(shipped):
    shipped(("iso_12647_8",))
    assert cs.shipped_iso_sets() == ("iso_12647_8",)
    ro = cs.factory_limits("iso_12647_8")
    judged = cs.limit_bearing(ro)
    assert set(judged) == _judgeable("iso_12647_8")
    # a row ChromIQ cannot measure still reads ✕ whatever the file holds
    assert all(ro[r].kind == "unmeasurable" for r in cs._ISO_ROWS["iso_12647_8"]
               if cs.ROW_BY_ID[r].status == "unmeasurable")
    assert "iso_12647_8" in cs.selectable_set_ids({})
    # the set that did not ship is untouched: "?" and not a choice
    assert not cs.limit_bearing(cs.factory_limits("iso_12647_7"))
    assert "iso_12647_7" not in cs.selectable_set_ids({})
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"].kind == "unknown"


@pytest.mark.parametrize("sets", [("iso_12647_8",), ("iso_12647_7",),
                                  ("iso_12647_7", "iso_12647_8")])
def test_a_shipped_set_leaves_the_custom_column_on_knuts_figures(shipped, sets):
    """Knut, 2026-09-21: his researched figures are the Custom columns'
    starting numbers. A shipped standard's value is not a licence holder's
    own, so it changes the read-only column and nothing in the Custom one."""
    shipped(sets)
    for sid in ("iso_12647_7", "iso_12647_8"):
        custom = cs.limit_bearing(cs.factory_limits("custom_" + sid))
        want = {r: l for r, l in cs.custom_defaults(sid).items()
                if cs.ROW_BY_ID[r].status in ("now", "build", "ref")}
        assert custom == want, sid
        assert not any(l.number == FAKE for l in custom.values()), sid
        counts = cs.custom_default_counts("custom_" + sid)
        assert counts["supplied"] == 0, sid
        assert counts["industry"] == len(cs._CUSTOM_INDUSTRY[sid]), sid


def test_a_licence_holders_number_wins_its_row_and_a_null_keeps_the_shipped_one(
        shipped):
    row, kept = "all_de00_avg", "all_de00_p95"
    shipped(("iso_12647_8",), user={
        "iso_12647_8": {row: 1.25, kept: None},
        "iso_12647_7": {row: 1.5},
    })
    ro8 = cs.factory_limits("iso_12647_8")
    assert ro8[row].number == 1.25, "the licence holder's own figure wins"
    assert ro8[kept].number == FAKE, "a null left in the template blanked a shipped figure"
    assert set(cs.limit_bearing(ro8)) == _judgeable("iso_12647_8")
    # their -7 figure fills that read-only column, which ships nothing
    assert set(cs.limit_bearing(cs.factory_limits("iso_12647_7"))) == {row}
    # and a Custom column starts from THEIR number, not from a shipped one
    assert cs.factory_limits("custom_iso_12647_8")[row].number == 1.25
    assert cs.factory_limits("custom_iso_12647_8")[kept] == \
        cs.custom_defaults("iso_12647_8")[kept]
    assert cs.supplied_iso_rows("iso_12647_8") == frozenset({row})
    assert cs.shipped_iso_sets() == ("iso_12647_8",)


# ------------------------------------------------ what the windows say
def _texts(qapp):
    from ui.dialogs import thresholds_dialog as td
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.dialogs.reference_values_dialog import iso_source
    from workflow.measurement_report import REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8
    return {
        "columns": td._columns_paragraph(),
        "why": iso_source().why,
        "type7": MeasurementReportDialog._not_built_line(REPORT_TYPE_ISO_7),
        "type8": MeasurementReportDialog._not_built_line(REPORT_TYPE_ISO_8),
    }


def test_nothing_says_chromiq_ships_no_values_once_a_set_ships(shipped, qapp):
    shipped(("iso_12647_8",))
    t = _texts(qapp)
    assert "ISO 12647-8:2021 values” holds that standard's published " \
           "values, which ship with ChromIQ" in t["columns"], t["columns"]
    assert "ISO 12647-7:2016 values” is empty" in t["columns"], t["columns"]
    assert "no permission" not in t["columns"]
    assert "does not ship these numbers" not in t["why"], t["why"]
    assert "ChromIQ ships the published values of" in t["why"], t["why"]
    # the ISO 12647-8 document is now simply unbuilt; -7 still waits on values
    assert "may not include" not in t["type8"], t["type8"]
    assert "may not include" in t["type7"], t["type7"]


def test_the_empty_state_keeps_its_own_sentences(shipped, qapp):
    shipped(())
    t = _texts(qapp)
    assert "no permission to include" in t["columns"], t["columns"]
    assert "does not ship these numbers" in t["why"]
    assert "may not include" in t["type7"] and "may not include" in t["type8"]


def test_both_sets_shipped_says_so_once(shipped, qapp):
    shipped(("iso_12647_7", "iso_12647_8"))
    t = _texts(qapp)
    assert t["columns"].count("which ship with ChromIQ") == 2, t["columns"]
    assert "is empty" not in t["columns"]
    assert "both ISO columns" in t["why"], t["why"]
    assert "may not include" not in t["type7"] + t["type8"]


# --------------------------------------------------------- the install step
def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          encoding="utf-8",
                          capture_output=True, text=True, timeout=120,
                          cwd=str(ROOT))


def test_the_install_script_copies_only_the_sets_and_prints_no_value(tmp_path):
    target = tmp_path / "iso12647.json"
    target.write_text(REPO_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    readme = json.loads(target.read_text(encoding="utf-8"))["_readme"]
    src = tmp_path / "source.json"
    src.write_text(json.dumps({
        "_readme": "a licence holder's own notes", "_rows": {"x": "y"},
        "iso_12647_7": _fake_set("iso_12647_7"),
        "iso_12647_8": _fake_set("iso_12647_8")}), encoding="utf-8")
    got = _run(src, "--target", target)
    assert got.returncode == 0, got.stdout + got.stderr
    assert str(FAKE) not in got.stdout + got.stderr, "the script printed a value"
    assert "equal to the source: True" in got.stdout
    back = json.loads(target.read_text(encoding="utf-8"))
    assert set(back) == {"_readme", "iso_12647_7", "iso_12647_8"}
    assert back["_readme"] == readme, "the repository's own _readme was replaced"
    assert back["iso_12647_8"] == _fake_set("iso_12647_8")
    assert back["iso_12647_7"] == _fake_set("iso_12647_7")


def test_the_install_script_copies_one_set_when_asked(tmp_path):
    target = tmp_path / "iso12647.json"
    target.write_text(REPO_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    before = json.loads(target.read_text(encoding="utf-8"))
    src = tmp_path / "source.json"
    src.write_text(json.dumps({"iso_12647_7": _fake_set("iso_12647_7"),
                               "iso_12647_8": _fake_set("iso_12647_8")}),
                   encoding="utf-8")
    assert _run(src, "--set", "8", "--target", target).returncode == 0
    back = json.loads(target.read_text(encoding="utf-8"))
    assert back["iso_12647_8"] == _fake_set("iso_12647_8")
    assert back["iso_12647_7"] == before["iso_12647_7"]


def test_the_install_script_refuses_half_a_set_and_names_rows_not_values(tmp_path):
    target = tmp_path / "iso12647.json"
    target.write_text(REPO_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    half = dict(list(_fake_set("iso_12647_8").items())[:5])
    half["all_de00_avg"] = "about two"
    src = tmp_path / "source.json"
    src.write_text(json.dumps({"iso_12647_8": half}), encoding="utf-8")
    got = _run(src, "--set", "8", "--target", target)
    assert got.returncode == 1
    assert "refused" in got.stdout and "missing" in got.stdout
    assert "all_de00_avg" in got.stdout            # the row id, which is ours
    assert "about two" not in got.stdout and str(FAKE) not in got.stdout
    assert target.read_text(encoding="utf-8") == before, "a refused set was written"


def test_the_install_script_check_writes_nothing(tmp_path):
    target = tmp_path / "iso12647.json"
    target.write_text(REPO_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    src = tmp_path / "source.json"
    src.write_text(json.dumps({"iso_12647_8": _fake_set("iso_12647_8")}),
                   encoding="utf-8")
    got = _run(src, "--set", "8", "--check", "--target", target)
    assert got.returncode == 0 and "nothing written" in got.stdout
    assert target.read_text(encoding="utf-8") == before


# ------------------------------------------------------------- the demo pack
@pytest.mark.parametrize("script", ["make_report_limit_demos.py",
                                    "make_verification_preset_demos.py"])
def test_a_public_demo_generator_reads_only_the_repositorys_iso_file(script):
    """The demo pack is published, and a licence holder's own values must not
    reach it. Both generators work through `compliance_sets`, which prefers a
    licence holder's file in ChromIQ's settings folder over the repository's,
    so each forces the variable at the repository's own file for the call.
    MUTATION: delete the assignment from either `main` and this goes red."""
    import ast
    src = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    main = next(n for n in ast.parse(src).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = ast.get_source_segment(src, main)
    assert 'os.environ[key] = str(_HERE.parent / "data" / "compliance_sets"' in body
    assert 'key = "CHROMIQ_COMPLIANCE_ISO_FILE"' in body
    assert "setdefault" not in body
    assert "_main(argv)" in body
