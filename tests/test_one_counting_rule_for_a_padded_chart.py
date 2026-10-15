"""A chart is counted by ONE rule at every door.

2026-09-11's measurement-import round put every door through
`measurement_state.expected_patches` after the Measure tab's verification
import had been left reading the raw ``NUMBER_OF_SETS`` (it refused a
measurement the other door filed). That one-place rule stays; WHAT it counts
changed on 2026-10-15 with Knut's ruling (#182 6191934889): the fill-up
squares of ChromIQ's layout engine are patches, counted and to be read, so
an engine chart of 400 designed + 14 fill-up has 414 patches. printtarg's
``SAMPLE_ID`` 0 padding is still left out, because no reader records it.
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


@pytest.mark.parametrize("which, n", [("printtarg_chart", 400),
                                      ("engine_chart", 414)])
def test_every_door_counts_the_same_patches(which, n, request, measure_tab):
    ti2 = request.getfixturevalue(which)

    assert expected_patches(ti2) == n, "the rule itself"
    assert IMPORT_COUNT(ti2) == n, "the profile-build import"
    assert measure_tab._chart_patch_count(ti2) == n, \
        "the Measure tab's verification import"


def test_an_unpadded_chart_is_unchanged(tmp_path, measure_tab):
    ti2 = _ti2(tmp_path / "u.ti2", "Argyll printtarg", 400, 0,
               engine_ids=False)
    assert measure_tab._chart_patch_count(ti2) == 400


def test_nothing_to_read_is_still_None(tmp_path, measure_tab):
    assert measure_tab._chart_patch_count(None) is None
    assert measure_tab._chart_patch_count(tmp_path / "gone.ti2") is None


def _measurement(path, n):
    rows = [f'{i} "A{i}" 50.0 50.0 50.0 50.0 50.0 50.0'
            for i in range(1, 401)]
    rows += [f'{400 + k} "Z{k}" 100.0 100.0 100.0 95.0 100.0 108.0'
             for k in range(1, 15)]
    rows = rows[:n]
    path.write_text(
        f'CTI3\n\nDESCRIPTOR "x"\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        f"NUMBER_OF_FIELDS {len(_FIELDS.split())}\n"
        f"BEGIN_DATA_FORMAT\n{_FIELDS}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


def test_every_square_read_is_not_refused(engine_chart, measure_tab,
                                          tmp_path):
    """414 readings of a 414-square chart is complete."""
    ti3 = _measurement(tmp_path / "m.ti3", 414)
    assert measure_tab._import_mismatch_reason(ti3, engine_chart) is None


def test_the_designed_patches_alone_are_a_partial(engine_chart, measure_tab,
                                                  tmp_path):
    """400 readings of a 414-square chart: 14 squares unread (Knut,
    #182 6191934889), so the verification door treats it as it treats any
    partial measurement, and states the chart's real count."""
    ti3 = _measurement(tmp_path / "m.ti3", 400)
    reason = measure_tab._import_mismatch_reason(ti3, engine_chart)
    assert reason and "414" in reason and "400" in reason
