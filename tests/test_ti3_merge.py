"""Pre-conditioning measurement merge (ChromIQ-style refinement).

Covers workflow.ti3_merge: combining a pre-conditioning profile's measurement
data into a freshly measured .ti3 so colprof builds from the larger set. The
concatenation is delegated to ArgyllCMS ``average -m``; this module's own job is
to refuse incompatible pairings before invoking it.

Invariants exercised here:
  * a colour-space / data-format mismatch is refused, not silently merged;
  * a file with no usable measurement data is refused;
  * when ``average`` is available, the merge concatenates both patch sets.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.resource_path import argyll_binary
from tests.argyll_env import argyll_tool
from workflow.ti3_merge import Ti3MergeError, merge_preconditioning


def _ti3(color_rep: str, fmt: str, rows: list[str]) -> str:
    body = "\n".join(rows)
    return (
        "CTI3\n\n"
        'DESCRIPTOR "test"\n'
        'ORIGINATOR "test"\n'
        f'COLOR_REP "{color_rep}"\n'
        "\n"
        f"NUMBER_OF_FIELDS {len(fmt.split())}\n"
        "BEGIN_DATA_FORMAT\n"
        f"{fmt}\n"
        "END_DATA_FORMAT\n"
        "\n"
        f"NUMBER_OF_SETS {len(rows)}\n"
        "BEGIN_DATA\n"
        f"{body}\n"
        "END_DATA\n"
    )


_FMT = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"


def _write(tmp_path, name, color_rep, rows):
    p = tmp_path / name
    p.write_text(_ti3(color_rep, _FMT, rows), encoding="utf-8")
    return p


def _data_rows(start, count, loc_prefix):
    return [
        f'{i} "{loc_prefix}{i}" 10 20 30 11.0 12.0 13.0'
        for i in range(start, start + count)
    ]


def _read_data(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    b = lines.index("BEGIN_DATA")
    e = lines.index("END_DATA")
    return [ln for ln in lines[b + 1:e] if ln.strip()]


def _find_average() -> str | None:
    """Locate the ArgyllCMS 'average' binary, or None if it isn't installed."""
    return argyll_tool("average") or shutil.which(argyll_binary("average"))


_AVERAGE = _find_average()
requires_average = pytest.mark.skipif(
    _AVERAGE is None, reason="ArgyllCMS 'average' binary not available"
)


@requires_average
def test_merge_concatenates_both_sets(tmp_path):
    # Mirrors the run layout: chart.ti3 (fresh) + preconditioning.ti3 → merged.ti3
    fresh = _write(tmp_path, "chart.ti3", "iRGB_XYZ", _data_rows(1, 3, "A"))
    pre = _write(tmp_path, "preconditioning.ti3", "iRGB_XYZ", _data_rows(1, 2, "B"))
    out = tmp_path / "merged.ti3"

    total = merge_preconditioning(fresh, pre, out,
                                  bin_dir=str(Path(_AVERAGE).parent))
    assert total == 5
    assert out.exists()
    assert len(_read_data(out)) == 5
    assert any(
        ln.strip() == "NUMBER_OF_SETS 5" for ln in out.read_text(encoding="utf-8").splitlines()
    )


def test_color_rep_mismatch_refused(tmp_path):
    fresh = _write(tmp_path, "chart.ti3", "iRGB_XYZ", _data_rows(1, 2, "A"))
    pre = _write(tmp_path, "preconditioning.ti3", "iRGB_LAB", _data_rows(1, 2, "B"))
    out = tmp_path / "merged.ti3"
    with pytest.raises(Ti3MergeError):
        merge_preconditioning(fresh, pre, out)
    assert not out.exists()


def test_data_format_mismatch_refused(tmp_path):
    fresh = _write(tmp_path, "chart.ti3", "iRGB_XYZ", _data_rows(1, 2, "A"))
    # pre file with a different (spectral-ish) format
    pre = tmp_path / "preconditioning.ti3"
    pre.write_text(_ti3("iRGB_XYZ", _FMT + " SPEC_380", ['1 "B1" 10 20 30 11 12 13 0.5']), encoding="utf-8")
    out = tmp_path / "merged.ti3"
    with pytest.raises(Ti3MergeError):
        merge_preconditioning(fresh, pre, out)
    assert not out.exists()


def test_missing_data_block_refused(tmp_path):
    fresh = _write(tmp_path, "chart.ti3", "iRGB_XYZ", _data_rows(1, 2, "A"))
    bad = tmp_path / "preconditioning.ti3"
    bad.write_text("CTI3\nnot a real measurement file\n", encoding="utf-8")
    out = tmp_path / "merged.ti3"
    with pytest.raises(Ti3MergeError):
        merge_preconditioning(fresh, bad, out)
    assert not out.exists()
