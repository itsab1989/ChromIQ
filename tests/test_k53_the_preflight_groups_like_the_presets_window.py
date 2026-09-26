"""K53 (Knut, #182 5846376222): the Measure tab's check before measuring
groups its "It cannot answer these" list the way the presets window groups
"This chart cannot answer" (B8-1321).

The question put to him: *"The Measure tab's check before measuring ("this
chart cannot answer…") still lists one line per metric. Should it be grouped
the same way?"* His answer: *"Answer: yes"*.

The same function (`group_by_messages`), over the lines the pre-flight
prints under a metric: its one reason (the lever stays in the full pane, as
Knut asked the popup to stay short). Metrics whose lines are identical are
listed together with the line once; anything else is listed on its own; the
groups keep the order of their first metric.

MUTATIONS (k53 mutations.txt): the one-line-per-metric loop restored in
`summary_lines`; the groups keyed on the metric instead of its lines.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                           # noqa: E402

from core.settings import AppSettings                              # noqa: E402
from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from ui.tabs.tab_chart import verification_preset_rows             # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

HEADING = "It cannot answer these"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def rows(qapp):
    """Every preset the presets window lists, assessed as the pre-flight
    assesses a chart (`assess_any`, every report type and limit set)."""
    out = []
    for row in verification_preset_rows(AppSettings()):
        if row.pending or row.chart is None:
            continue
        row.assessment = PE.assess_any(row.chart, None, row.recipe)
        if row.assessment.checked and row.assessment.asked:
            out.append(row)
    assert out, "no preset could be assessed"
    return out


def _blocks(lines):
    """[(metric labels, reason lines)] read back from the list."""
    texts = [ln.text for ln in lines]
    start = texts.index(HEADING)
    blocks, cur = [], None
    for ln in lines[start + 1:]:
        if ln.text.startswith("✕  "):
            if cur is None or cur[1]:
                cur = ([ln.text[3:]], [])
                blocks.append(cur)
            else:
                cur[0].append(ln.text[3:])
        elif ln.indent == 22 and cur is not None:
            cur[1].append(ln.text)
        else:
            break
    return blocks


def test_the_preflight_list_uses_the_presets_windows_grouping(rows,
                                                              monkeypatch):
    """REUSED, not rewritten: the list is built by `group_by_messages`."""
    calls = []
    real = PVD.group_by_messages

    def spy(items):
        calls.append(items)
        return real(items)

    monkeypatch.setattr(PVD, "group_by_messages", spy)
    row = next(r for r in rows if len(r.assessment.missing) >= 2)
    PVD.summary_lines(row, generic=True)
    assert calls, "summary_lines did not group with group_by_messages"
    assert [rid for rid, _m in calls[0]] == [
        rid for rid, _w in row.assessment.missing]


def test_every_group_carries_its_metrics_reason_once(rows):
    """On every preset: each ✕ line's reason is that metric's own, every
    metric the chart cannot answer is named exactly once, and no two groups
    carry the same line (identical lines are one group)."""
    grouped_somewhere = False
    for row in rows:
        missing = row.assessment.missing
        if not missing:
            continue
        own = {PE.row_label(rid): (PVD.reason_line(why),)
               for rid, why in missing}
        blocks = _blocks(PVD.summary_lines(row, generic=True))
        named = [n for names, _m in blocks for n in names]
        assert sorted(named) == sorted(own), row.label
        seen = []
        for names, msgs in blocks:
            for n in names:
                assert tuple(msgs) == own[n], (row.label, n)
            assert tuple(msgs) not in seen, (row.label, msgs)
            seen.append(tuple(msgs))
            grouped_somewhere |= len(names) > 1
    assert grouped_somewhere, "no preset has two metrics with one reason"


def test_the_solid_rows_are_one_group_with_the_reason_once(rows):
    """As in the presets window: a preset not built FROM PROFILE GAMUT
    cannot answer the two solid rows, for one reason. Two ✕ lines, one after
    the other, then the reason ONCE."""
    solids = PE.gamut_only_rows()
    row = next(r for r in rows
               if set(solids) <= {rid for rid, _w in r.assessment.missing})
    lines = [ln.text for ln in PVD.summary_lines(row, generic=True)]
    labels = ["✕  " + PE.row_label(rid) for rid in solids]
    i = lines.index(labels[0])
    assert lines[i:i + len(labels)] == labels, lines
    reason = PVD.reason_line(dict(row.assessment.missing)[solids[0]])
    assert lines[i + len(labels)] == reason
    assert lines.count(reason) == 1, lines


def test_a_metric_with_a_reason_of_its_own_is_listed_on_its_own(rows):
    """Partial overlaps are not merged: a metric whose reason no other
    missing metric shares is a group of one, directly followed by it."""
    for row in rows:
        reasons = [PVD.reason_line(w) for _r, w in row.assessment.missing]
        lonely = [(rid, PVD.reason_line(w))
                  for rid, w in row.assessment.missing
                  if reasons.count(PVD.reason_line(w)) == 1]
        if not lonely:
            continue
        blocks = _blocks(PVD.summary_lines(row, generic=True))
        for rid, reason in lonely:
            block = next(b for b in blocks if PE.row_label(rid) in b[0])
            assert block == ([PE.row_label(rid)], [reason]), row.label
        return
    pytest.fail("no preset has a metric with a reason of its own")
