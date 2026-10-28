"""Review 4.3.19 r1 and the i1Profiler 3.8.6 checks (2026-10-28_i1p386).

X-Rite removed the i1Pro 2 from i1Profiler in 3.8.7 (its own release notes),
and 3.8.8 opened every i1Pro 2 file without a word as an i1Pro 3 one, on
another grid. 3.8.6 laid out every i1Pro 2 file exactly. So the how-to note
and the Preferences help say which i1Profiler the i1Pro 2 needs, that 3.8.7
and newer open the i1Pro 2 file as an i1Pro 3 one on another grid, that the
i1Pro 2 file was checked in 3.8.6, and to leave "Use legacy charts" off, which
the files ask for too.

Review r2 made them say only what was observed: "Use legacy charts" changed
the grid for the i1Pro 2 in 3.8.6 alone (the i1Pro 3 in 3.8.8 changed only
the title, SF-C); only the i1Pro 2 family was ever missing (N-d); and in 3.8.6
either Default display device laid both files out exactly, so step 3 no longer
says the other family reads the patch size on the wrong scale (N-a).
"""
from __future__ import annotations

import re
from pathlib import Path

from core.file_manager import exports_subdir
from workflow import i1profiler_turned as T

from tests.test_i1profiler_turned_export import _chart

ROOT = Path(__file__).resolve().parents[1]


def _note(tmp_path) -> str:
    ti2 = _chart(tmp_path / "p", "P", 350)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "P")
    return T.TurnedFiles(exports_subdir(ti2.parent), "P").note.read_text(
        encoding="utf-8")


def test_the_note_says_3_8_6_and_legacy_charts_after_the_right_steps(tmp_path):
    note = _note(tmp_path)
    lines = note.splitlines()
    i3 = next(i for i, l in enumerate(lines) if l.startswith("3. "))
    i4 = next(i for i, l in enumerate(lines) if l.startswith("4. "))
    i5 = next(i for i, l in enumerate(lines) if l.startswith("5. "))
    assert lines[i3 + 1].strip() == T.I1PRO2_VERSION_NOTE
    assert i3 + 1 < i4
    assert lines[i4 + 1].strip() == T.LEGACY_CHARTS_NOTE
    assert i4 + 1 < i5
    assert "i1Profiler 3.8.6 or older" in T.I1PRO2_VERSION_NOTE
    assert "version 3.8.7" in T.I1PRO2_VERSION_NOTE
    # the i1Pro 2 file is no longer called unchecked
    assert "could not be opened" not in note
    assert "in i1Profiler 3.8.6, the last version that supports the i1Pro 2, with the i1Pro 2 file" in note
    assert "Nobody has yet read such a sheet with a real instrument" in note
    assert "—" not in note


def test_the_files_ask_for_legacy_charts_off(tmp_path):
    _note(tmp_path)
    txfs = list(exports_subdir((tmp_path / "p")).glob("*.txf"))
    assert txfs
    for txf in txfs:
        text = txf.read_text(encoding="utf-8")
        assert re.search(r'UseLegacyTestChart="False"', text), txf.name
        assert 'UseLegacyTestChart="True"' not in text


def test_the_preferences_help_says_the_same():
    src = (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")
    src = re.sub(r'"\s*\n\s*"', "", src)      # join wrapped literals
    assert "tr(I1PRO2_VERSION_NOTE)" in src
    assert "could not be opened in" not in src
    assert "the last version that supports the i1Pro 2" in src


def test_the_new_texts_are_in_every_catalogue():
    import json
    for cat in sorted((ROOT / "data/i18n").glob("*.json")):
        d = json.loads(cat.read_text(encoding="utf-8"))
        for key in (T.I1PRO2_VERSION_NOTE, T.LEGACY_CHARTS_NOTE):
            assert d.get(key), (cat.name, key[:40])
            assert "—" not in d[key]


def test_r2_the_texts_claim_only_what_was_observed(tmp_path):
    legacy = T.LEGACY_CHARTS_NOTE
    assert "i1Profiler 3.8.6 draws the i1Pro 2's older chart" in legacy
    assert "for either instrument" in legacy
    v = T.I1PRO2_VERSION_NOTE
    assert "as a file for the i1Pro 3 family" in v
    assert "the other family" not in v
    assert "does not offer the family of your instrument" not in v
    note = _note(tmp_path)
    step3 = next(l for l in note.splitlines() if l.startswith("3. "))
    assert "wrong scale" not in step3
    assert "set Default display device to the family" in step3
