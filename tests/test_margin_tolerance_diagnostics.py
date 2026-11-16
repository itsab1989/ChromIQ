"""The margin tolerance in the ruler diagnostics file (Beta, 2026-11-16).

Every decision the tolerance makes must be easy to find and to judge after
the session (the help asks testers for this file): a ``margin_summary`` at
the top of the file with the counts, the refusals grouped by reason and, per
kept strip, the numbers the rule used. Additive (revision 3): a file without
the tolerance is exactly as before. The Measure log keeps ONE line per kept
strip."""
from __future__ import annotations

import json

from workflow import ruler_diagnostics as rd
from workflow.ruler_session import RulerSession

KEPT = {"tried": True, "accepted": True, "rule": "M", "left_start": 1,
        "left_end": 0, "standing": 0, "leader": True, "fit": 3.1,
        "rival": 24.8, "segments": 24, "back": 0,
        "refused_because": "Too many patches", "rules": "M+L 4 (2026-11-16)",
        "travel": {"net": 330, "back": 0, "back_limit": 3,
                   "median_segment": 15.0, "pitch": 15.2, "span": 304.0,
                   "largest_step": 1.07, "largest_step_limit": 1.5,
                   "kept_steps": [15] * 21, "kept_readings": [12] * 21},
        "ratios": {"fit_to_rival": 0.125, "halves_worst": 0.2,
                   "limit": 0.5, "fit_limit": 35}}


def _refused(why):
    return {"tried": True, "accepted": False, "why": why, "segments": 23,
            "back": 0, "rules": "M+L 4 (2026-11-16)"}


def _file(tmp_path, entries, tolerance="on"):
    d = rd.Diagnostics(tmp_path / "ruler.json", instrument="i1pro2",
                       firmware=None)
    d.doc["margin_tolerance"] = tolerance
    for strip, margin, verdict in entries:
        rec = {"instrument": "i1pro2", "readings": 300}
        if margin is not None:
            rec["margin"] = margin
        d.add_strip(rec, strip=strip, figures={}, verdict=verdict)
    return json.loads((tmp_path / "ruler.json").read_text("utf-8")), d


def test_a_kept_and_a_refused_strip_are_found_at_the_top_of_the_file(tmp_path):
    doc, _ = _file(tmp_path, [
        ("A", None, "ok"),
        ("B", KEPT, "ok"),
        ("C", _refused("M: fit 41.2 dE is above 35; L: the first segment is "
                       "not a whole patch"), "refused"),
        ("D", _refused("M: fit 38.0 dE is above 35; L: the first segment is "
                       "not a whole patch"), "refused"),
        ("E", _refused("the ruler shows the instrument moved back 40 steps"),
         "refused"),
    ])
    assert list(doc)[:4] == ["format", "version", "revision", "margin_summary"]
    s = doc["margin_summary"]
    assert (s["tried"], s["kept"], s["refused"]) == (4, 1, 3)
    assert s["refused_by_reason"] == {
        "M: fit # dE is above #; L: the first segment is not a whole patch": 2,
        "the ruler shows the instrument moved back # steps": 1}
    assert list(s["refused_by_reason"].values()) == [2, 1]   # most first
    k, = s["kept_strips"]
    assert k["strip"] == "B" and doc["strips"][k["entry"]]["strip"] == "B"
    assert (k["rule"], k["left_start"], k["left_end"]) == ("M", 1, 0)
    assert k["refused_because"] == "Too many patches"
    assert (k["fit_to_rival"], k["halves_worst"], k["largest_step"]) == (
        0.125, 0.2, 1.07)
    assert k["verdict"] == "ok"
    assert [r["strip"] for r in s["refused_strips"]] == ["C", "D", "E"]
    assert doc["strips"][s["refused_strips"][2]["entry"]]["strip"] == "E"
    # the strip's own record is untouched, travel accounting included
    assert doc["strips"][1]["record"]["margin"] == KEPT


def test_without_the_tolerance_the_file_is_as_before(tmp_path):
    doc, d = _file(tmp_path, [("A", None, "ok")], tolerance="not asked")
    assert "margin_summary" not in doc
    assert list(doc) == list(d.doc)          # same keys, same order


def test_the_tolerance_on_with_nothing_refused_says_so(tmp_path):
    doc, _ = _file(tmp_path, [("A", None, "ok")], tolerance="on")
    assert doc["margin_summary"] == {"tried": 0, "kept": 0, "refused": 0,
                                     "refused_by_reason": {},
                                     "kept_strips": [], "refused_strips": []}


def test_the_measure_log_line_for_a_kept_strip_stays_one_calm_line():
    line = RulerSession._margin_line("B", KEPT)
    assert "\n" not in line
    for word in ("pitch", "ratio", "largest_step", "0.125", "1.07"):
        assert word not in line
