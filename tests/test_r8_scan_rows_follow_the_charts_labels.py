"""R8 (4.3.39): the scanner dialog's row / column check
(`locally_misaligned_groups`) grouped ids with a letters-then-digits rule, so
on a chart with number strips and letter patches ("12I", ChromIQ's own
engine charts can be made so) every id failed the rule and the check was
skipped in silence. In printer mode the dialog has the chart's .ti2, so it
now groups by the chart's own label scheme; scanner mode (a reference
target's ids) keeps the old rule, and gives exactly the old answers."""
from __future__ import annotations

import random
from pathlib import Path

from ui.dialogs.scanin_dialog import (chart_id_parts, locally_misaligned_groups,
                                      regex_id_parts)

REPO = Path(__file__).resolve().parents[1]


def _ti2(path: Path, strips: int, per: int, number_strips: bool) -> Path:
    letters = "ABCDEFGHIJKLMNOP"
    rows = []
    n = 0
    for s in range(strips):
        for p in range(per):
            n += 1
            loc = (f"{s + 1}{letters[p]}" if number_strips
                   else f"{letters[s]}{p + 1}")
            rows.append(f'{n} "{loc}" 0 0 0 1 1 1')
    pat = ('STRIP_INDEX_PATTERN "0-9,@-9,@-9;1-999"\nPATCH_INDEX_PATTERN "A-Z"\n'
           if number_strips else
           'STRIP_INDEX_PATTERN "A-Z, A-Z"\nPATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"\n')
    path.write_text(
        "CTI2\n\n" + f'STEPS_IN_PASS "{per}"\n' + pat
        + 'INDEX_ORDER "STRIP_THEN_PATCH"\nNUMBER_OF_FIELDS 8\n'
        "BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n" + f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="latin-1")
    return path


def _grid(locs_by_sp, shift_strip=None):
    rnd = random.Random(3)
    exp = {loc: rnd.random() * 100 for loc in locs_by_sp.values()}
    read = dict(exp)
    if shift_strip is not None:
        # one strip reads the next strip's colours: a grid edge a cell off
        for (s, p), loc in locs_by_sp.items():
            if s == shift_strip and (s + 1, p) in locs_by_sp:
                read[loc] = exp[locs_by_sp[(s + 1, p)]]
    return read, exp


def test_number_strips_are_grouped_and_a_shift_is_found(tmp_path):
    ti2 = _ti2(tmp_path / "n.ti2", 8, 8, number_strips=True)
    letters = "ABCDEFGH"
    locs = {(s, p): f"{s + 1}{letters[p]}" for s in range(8) for p in range(8)}
    read, exp = _grid(locs, shift_strip=3)
    # the old rule sees nothing at all on this chart
    assert locally_misaligned_groups(read, exp) == []
    flags = locally_misaligned_groups(read, exp, parts=chart_id_parts(ti2))
    assert flags and any("4" in f for f in flags)
    ok_read, ok_exp = _grid(locs)
    assert locally_misaligned_groups(ok_read, ok_exp,
                                     parts=chart_id_parts(ti2)) == []


def test_the_default_scheme_gives_the_old_answer(tmp_path):
    ti2 = _ti2(tmp_path / "a.ti2", 8, 8, number_strips=False)
    letters = "ABCDEFGH"
    locs = {(s, p): f"{letters[s]}{p + 1}" for s in range(8) for p in range(8)}
    for shift in (None, 2, 5):
        read, exp = _grid(locs, shift_strip=shift)
        assert locally_misaligned_groups(read, exp) == \
            locally_misaligned_groups(read, exp, parts=chart_id_parts(ti2))


def test_without_a_chart_the_old_rule_stays():
    assert chart_id_parts(None) is regex_id_parts
    assert regex_id_parts("H01") == ("H", "1", (1, "H"), 1)


def test_printer_mode_passes_the_charts_labels():
    src = (REPO / "ui/dialogs/scanin_dialog.py").read_text(encoding="utf-8")
    assert src.count("parts=chart_id_parts(") == 1
    assert "parts=(chart_id_parts(artefact(params.pbase, \".ti2\"))" in src
