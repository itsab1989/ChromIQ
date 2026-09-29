"""A chart's fill-up rows are discounted at EVERY door, not at one of them.

2026-09-11's measurement-import round found that a chart's last strip is filled
out with rows that are not part of the design, that ChromIQ's own layout engine
pads exactly as printtarg does, and that a user's complete 4,000-patch
measurement of a 4,014-row chart had been filed as "part of the chart was not
measured". It put `workflow.measurement_import._chart_patch_count` through
`measurement_state.expected_patches`, which is the one place that knows the
rule, and its own comment named the sibling it was copying away from:
``tab_measure._chart_patch_count``.

That sibling was left reading the raw ``NUMBER_OF_SETS``, and it is the harsher
door of the two. It does not label a measurement partial; it REFUSES it:

    the verification chart has 4014 patches, but this file holds 4000
    measurements

Measured on both kinds of padded chart, before the fix:

    ==========  =================  ============================  ==============
    chart       expected_patches   measurement_import            TabMeasure
    ==========  =================  ============================  ==============
    printtarg   4000               4000                          **4014**
    engine      4000               4000                          **4014**
    ==========  =================  ============================  ==============

The same count also names the chart's size in the import panel's own
description, so the box said 4,014 while the file that matched it held 4,000.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_import import _chart_patch_count as IMPORT_COUNT  # noqa: E402
from workflow.measurement_state import expected_patches                     # noqa: E402

_FIELDS = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"


def _ti2(path: Path, originator: str, designed: int, pad: int,
         *, engine_ids: bool) -> Path:
    rows = [f'{i} "A{i}" 50.0 50.0 50.0 50.0 50.0 50.0'
            for i in range(1, designed + 1)]
    for k in range(1, pad + 1):
        sid = designed + k if engine_ids else 0
        rows.append(f'{sid} "Z{k}" 100.0 100.0 100.0 95.0 100.0 108.0')
    path.write_text(
        f'CTI2\n\nDESCRIPTOR "x"\nORIGINATOR "{originator}"\n'
        'STEPS_IN_PASS "20"\n\n'
        f"NUMBER_OF_FIELDS {len(_FIELDS.split())}\n"
        f"BEGIN_DATA_FORMAT\n{_FIELDS}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    if engine_ids:
        d = [f"{i} 50.0 50.0 50.0" for i in range(1, designed + 1)]
        path.with_suffix(".ti1").write_text(
            'CTI1\n\nDESCRIPTOR "x"\n\nNUMBER_OF_FIELDS 4\n'
            "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {designed}\nBEGIN_DATA\n" + "\n".join(d)
            + "\nEND_DATA\n", encoding="utf-8")
    return path


@pytest.fixture
def printtarg_chart(tmp_path):
    return _ti2(tmp_path / "p.ti2", "Argyll printtarg", 400, 14,
                engine_ids=False)


@pytest.fixture
def engine_chart(tmp_path):
    return _ti2(tmp_path / "e.ti2", "ChromIQ layout engine", 400, 14,
                engine_ids=True)


@pytest.fixture
def measure_tab(qtbot):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    qtbot.addWidget(tab)
    return tab


@pytest.mark.parametrize("which", ["printtarg_chart", "engine_chart"])
def test_every_door_counts_the_designed_patches(which, request, measure_tab):
    ti2 = request.getfixturevalue(which)

    assert expected_patches(ti2) == 400, "the rule itself"
    assert IMPORT_COUNT(ti2) == 400, "the profile-build import"
    assert measure_tab._chart_patch_count(ti2) == 400, \
        "the Measure tab's verification import"


def test_an_unpadded_chart_is_unchanged(tmp_path, measure_tab):
    ti2 = _ti2(tmp_path / "u.ti2", "Argyll printtarg", 400, 0,
               engine_ids=False)
    assert measure_tab._chart_patch_count(ti2) == 400


def test_nothing_to_read_is_still_None(tmp_path, measure_tab):
    assert measure_tab._chart_patch_count(None) is None
    assert measure_tab._chart_patch_count(tmp_path / "gone.ti2") is None


def test_a_complete_measurement_of_a_padded_chart_is_not_refused(
        engine_chart, measure_tab, tmp_path):
    """The sentence the user met. 400 readings of a 414-row chart is complete."""
    ti3 = tmp_path / "m.ti3"
    rows = [f'{i} "A{i}" 50.0 50.0 50.0 50.0 50.0 50.0'
            for i in range(1, 401)]
    ti3.write_text(
        f'CTI3\n\nDESCRIPTOR "x"\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        f"NUMBER_OF_FIELDS {len(_FIELDS.split())}\n"
        f"BEGIN_DATA_FORMAT\n{_FIELDS}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")

    reason = measure_tab._import_mismatch_reason(ti3, engine_chart)

    assert reason is None or "414" not in reason, reason
