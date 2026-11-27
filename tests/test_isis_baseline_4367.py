"""AN i1iSis CHART ON A PAPER ITS MODEL FEEDS IS THE CHART 4.3.67 MADE, AND A
ONE-PAGE MEASUREMENT IS JUDGED AS 4.3.67 JUDGED IT (step 0 of the i1iSis
pieces work, challenge S7).

The pieces work changes only what happens on a sheet the model cannot feed as
printed, and the import of several pages. Every case of
`_isis_baseline.cases` is built here and the digests of its geometry files
(``.ti2``, side file, channels, colour list, i1Profiler pair, ``.txf``, order
file) are compared with the stored ones of release 4.3.67
(``tests/data/isis_baseline_4367.json``); clocks and what a font decides are
left out. The import verdicts of every one-page case (randomised or not, read
right and every wrong way, with and without the order file) must be the same
word for word; several pages are what the work changes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _isis_baseline as base     # noqa: E402

STORED = json.loads((Path(__file__).parent / "data"
                     / "isis_baseline_4367.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _on():
    from workflow.isis import support
    was = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = was


def test_the_stored_cases_are_the_cases():
    assert set(STORED["cases"]) == set(base.cases())


@pytest.mark.parametrize("name", sorted(base.cases()))
def test_the_chart_is_the_one_4367_made(name, tmp_path):
    d = tmp_path / "c"
    base.build_case(name, base.cases()[name], d)
    got = {f: base.digest(d / f, fonts=False) for f in base.geometry_files(d)}
    assert got == STORED["cases"][name]


def test_a_tenth_of_a_millimetre_is_seen(tmp_path):
    """The comparison can fail: one margin 0.1 mm larger."""
    def wider(kw):
        m = kw.get("margins") or (5.0, 5.0, 5.0, 5.0)
        kw["margins"] = (m[0] + 0.1,) + tuple(m[1:])
        return kw
    d = tmp_path / "c"
    base.build_case("manual_standard_A4", base.cases()["manual_standard_A4"],
                    d, wider)
    stored = STORED["cases"]["manual_standard_A4"]
    assert base.digest(d / "chart.isis.json", fonts=False) \
        != stored["chart.isis.json"]


def _as_now(stored: list) -> list:
    """4.3.67's verdict with the one change made since on purpose: a
    randomised chart whose readings fit more than one order is refused with
    the i1iSis's own sentence (M-IMPORT-ISIS-ORDER-UNKNOWN), no longer the
    turned chart's (review of part 1 of the pieces work, S3)."""
    from workflow import measurement_messages as MM
    from workflow.measurement_import import (straight_or_turned_reason,
                                             turned_ambiguous_reason)
    if stored[1] in (straight_or_turned_reason(), turned_ambiguous_reason()):
        return [stored[0], MM.isis_order_unknown_reason(), *stored[2:]]
    return list(stored)


def test_every_one_page_verdict_is_the_one_4367_gave(tmp_path):
    got = base.import_cases(tmp_path)
    assert set(got) == set(STORED["verdicts"])
    differ = [k for k, v in got.items()
              if STORED["verdicts"][k][5] == 1 and list(v) != _as_now(
                  STORED["verdicts"][k])]
    assert not differ, differ[:10]
    changed = [k for k, v in STORED["verdicts"].items()
               if v[5] == 1 and _as_now(v) != v]
    assert changed and all(k.startswith("even|True|") for k in changed)
    # the stored several-page cases are the ones the import of several
    # pages is about: 4.3.67 refused every one of them
    several = [v for v in STORED["verdicts"].values() if v[5] > 1]
    assert several and not any(v[0] for v in several)
