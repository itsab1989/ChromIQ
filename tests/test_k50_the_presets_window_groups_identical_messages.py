"""K50 (Knut, #182 5845519118, B8-1321): in "Which presets can be used for
verification", the metrics a chart cannot answer that carry IDENTICAL
messages are listed together, and the messages are printed once under the
group.

    *"all those metrics that have identical messages should be grouped
    togheter then shown the message for that group"* [...] *"If there are
    other metrics that share the exact same messaging they can also be
    grouped, but only if some of the messages of a metric is common with
    another, they need to be listed separately."*

So a metric is grouped by its COMPLETE message set (what the chart is short
of, printtarg's words where it refused, the lever), and the groups keep the
order of their first metric (`measurement_report_limits.md` §44.2).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                           # noqa: E402

from core.settings import AppSettings                              # noqa: E402
from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from ui.tabs.tab_chart import verification_preset_rows             # noqa: E402
from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

ISO7 = (MR.REPORT_TYPE_FULL, "iso_12647_7")
ALL = (MR.REPORT_TYPE_FULL, PE.ALL_METRICS)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def rows(qapp):
    return verification_preset_rows(AppSettings())


# ---------------------------------------------------------------------------
# 1. the rule, on its own
# ---------------------------------------------------------------------------
def test_identical_message_sets_are_one_group_in_first_metric_order():
    """MUTATION, proven red: key the groups on the first message alone (a,
    c and d then merge)."""
    got = PVD.group_by_messages([
        ("a", ("short", "lever")),
        ("b", ("other", "lever2")),
        ("c", ("short", "lever")),
        ("d", ("short", "another lever")),
        ("e", ("other", "lever2")),
    ])
    assert got == [(["a", "c"], ("short", "lever")),
                   (["b", "e"], ("other", "lever2")),
                   (["d"], ("short", "another lever"))]


def test_a_metric_sharing_only_some_messages_is_listed_on_its_own():
    """Knut: *"only if some of the messages of a metric is common with
    another, they need to be listed separately."*

    MUTATION, proven red: form the groups on the reason alone, leaving the
    lever out of the key (a and b then merge, and b is printed a lever that
    is not its own)."""
    got = PVD.group_by_messages([
        ("a", ("one", "two")),
        ("b", ("one",)),
        ("c", ("two", "one")),
    ])
    assert [r for r, _m in got] == [["a"], ["b"], ["c"]]


def test_no_metric_is_lost_or_repeated():
    items = [(str(i), (str(i % 3),)) for i in range(10)]
    got = PVD.group_by_messages(items)
    flat = [r for rids, _m in got for r in rids]
    assert sorted(flat) == sorted(i for i, _m in items)
    assert len(flat) == len(set(flat))


# ---------------------------------------------------------------------------
# 2. the pane, on the real preset list
# ---------------------------------------------------------------------------
def _pane(qapp, rows, choice):
    dlg = PVD.PresetVerificationDialog(rows)
    dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(choice[0]))
    dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(choice[1]))
    qapp.processEvents()
    return dlg


def _solid_preset(dlg):
    solids = set(PE.gamut_only_rows())
    for r in dlg._rows:
        if r.pending or not r.assessment.checked:
            continue
        if solids <= {rid for rid, _w in r.assessment.missing}:
            return r
    raise AssertionError("no preset misses the two solid rows")


@pytest.mark.parametrize("choice", [ISO7, ALL], ids=["iso_12647_7", "all"])
def test_the_solid_rows_share_one_message_block(qapp, rows, choice):
    """Under ISO 12647-7 and under All metrics a preset not built FROM
    PROFILE GAMUT cannot answer the two solid rows, for one reason and with
    one lever: two ✕ lines, one after the other, then the reason and the
    lever ONCE.

    MUTATION, proven red: restore the one-block-per-metric loop in
    `detail_lines`."""
    dlg = _pane(qapp, rows, choice)
    try:
        row = _solid_preset(dlg)
        lines = [ln.text for ln in PVD.detail_lines(
            row, every_metric=choice[1] == PE.ALL_METRICS)]
        labels = ["✕  " + PE.row_label(rid) for rid in PE.gamut_only_rows()]
        i = lines.index(labels[0])
        assert lines[i:i + len(labels)] == labels, lines[i:i + 4]
        why = dict(row.assessment.missing)[PE.gamut_only_rows()[0]]
        reason = PVD.reason_line(why)
        assert lines.count(reason) == 1, lines
        assert lines[i + len(labels)] == reason
        remedy = PE.row_remedy(PE.gamut_only_rows()[0], why)
        assert remedy and lines.count(remedy) == 1
        # every metric the chart cannot answer is still named, once
        crosses = [t for t in lines if t.startswith("✕  ")]
        assert len(crosses) == len(set(crosses)) == len(
            [m for m in row.assessment.missing
             if m[1] != PE.REASON_EVENNESS_LAYING_OUT])
    finally:
        dlg.close()


def test_every_group_carries_exactly_its_metrics_messages(qapp, rows):
    """On every preset under ISO 12647-7: read back from the pane, each ✕
    line's block of messages is that metric's own complete set, and two
    neighbouring groups never carry the same set.

    MUTATION, proven red: one block per metric again (two neighbouring
    groups then carry the same set)."""
    dlg = _pane(qapp, rows, ISO7)
    try:
        for row in dlg._rows:
            if row.pending or not row.assessment.checked \
                    or not row.assessment.asked:
                continue
            missing = [(rid, w) for rid, w in row.assessment.missing
                       if w != PE.REASON_EVENNESS_LAYING_OUT]
            if not missing:
                continue
            said = PE.layout_failure_detail(row.chart, row.recipe)
            own = {rid: PVD._missing_messages(rid, w, said)
                   for rid, w in missing}
            lines = PVD.detail_lines(row)
            start = next(i for i, ln in enumerate(lines)
                         if ln.text == "This chart cannot answer")
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
            label = {PE.row_label(rid): rid for rid, _w in missing}
            seen = []
            for names, msgs in blocks:
                for n in names:
                    assert tuple(msgs) == own[label[n]], (row.label, n)
                assert tuple(msgs) not in seen, row.label
                seen.append(tuple(msgs))
    finally:
        dlg.close()
