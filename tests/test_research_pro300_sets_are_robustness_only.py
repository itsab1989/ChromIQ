"""The two PRO-300-labelled real sets are robustness data only (2026-10-05).

ProfileEngineResearch Validation/pro300-impact-audit.md: R-Pro300-EpsonPremSG
was printed with the wrong colour management (Basti, 2026-10-05), and
R-Pro300-CanonSG is of unknown origin. They may still serve fit, held-out and
identity checks, but no confirmatory or claim-eligible table may rest on them,
and every table that shows them must say so.
"""
from __future__ import annotations

from benchmarks.research import datasets as dsm

PRO300 = ("R-Pro300-CanonSG", "R-Pro300-EpsonPremSG")


def test_both_pro300_sets_are_listed_as_non_representative():
    for name in PRO300:
        assert name in dsm.NON_REPRESENTATIVE
        assert name in dsm.ROBUSTNESS_ONLY
        assert dsm.is_robustness_only(name)
        assert dsm.is_robustness_only(name + "@F8")


def test_trustworthy_real_sets_are_not_robustness_only():
    for name in ("R-FOGRA39L", "R-GRACoL2006", "R-Knut-printer", "R-CMYK-default-i1Pro", "S1", "Z04"):
        assert not dsm.is_robustness_only(name)


def test_they_are_never_confirmatory_and_never_sealed():
    for name in PRO300:
        assert dsm.role_of(name) == "development"
        assert dsm.role_v3(name) == "development"


def test_their_provenance_notes_no_longer_call_them_the_owners_printer():
    for name in PRO300:
        note = dsm.REAL_SOURCES[name][3]
        assert "robustness data only" in note
        assert not note.startswith("owner")
    assert "wrong colour management" in dsm.REAL_SOURCES["R-Pro300-EpsonPremSG"][3]
    assert "unknown origin" in dsm.REAL_SOURCES["R-Pro300-CanonSG"][3]


def test_a_pro300_row_can_never_carry_a_claim_even_if_mislabelled_sealed():
    from benchmarks.research import stats3
    base = {"variant": "typical-targen900", "reader": "argyll", "reader_group": "cmm",
            "endpoint": "b2a.p95", "role": "sealed", "level": "typical", "chart": "targen",
            "chart_role": "primary", "ink_class": "RGB", "a": 1.0, "b": 0.7, "diff": -0.3,
            "ci95": [-0.4, -0.2], "p": 1e-9, "rel": -0.3}
    rows = [dict(base, dataset="Z04")] + [dict(base, dataset=n) for n in PRO300]
    stats3.decide(rows, "colprof", "accurate", None)
    assert [r["claim_eligible"] for r in rows] == [True, False, False]


def test_the_summary_marks_them_robustness_only(tmp_path):
    from benchmarks.research import summary
    import inspect
    src = inspect.getsource(summary.write_summary)
    assert "is_robustness_only" in src and "ROBUSTNESS_LABEL" in src
    assert dsm.ROBUSTNESS_LABEL == "robustness only, not quality evidence"
