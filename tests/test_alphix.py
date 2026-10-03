"""ArgyllCMS's location-label grammar, ported, and the pattern checks built on it.

Forum report, 2026-10-03: the strip pattern "0-9" made a 14-strip chart that
neither ArgyllCMS chartread nor ChromIQ's engine could read ("Bad location field
value '(null)' on patch 266"). ChromIQ printed strip 10 as "10"; by Argyll's
grammar "0-9" is one digit and stops at 9.

The port is checked against ArgyllCMS ITSELF, not against ChromIQ's labeller:
`tests/data/alphix_argyll_table.json` is frozen from ArgyllCMS 3.5.0's
`target/alphix.c` (identical to `native/instlib/alphix.c`) compiled into a
small harness, for 38 patterns (both directions, capacity, every refusal) and
`patch_location_order` for 9 strip/patch pairs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow.layout_engine import alphix, permutation
from workflow.layout_engine.alphix import (Alphix, PatternError, check_patterns,
                                           chart_locations_problem,
                                           patch_location_order)

TABLE = json.loads((Path(__file__).parent / "data" /
                    "alphix_argyll_table.json").read_text(encoding="utf-8"))


# ---- the port against ArgyllCMS's own code --------------------------------
@pytest.mark.parametrize("pattern", sorted(TABLE["patterns"]))
def test_the_port_labels_and_counts_exactly_as_argyll_does(pattern):
    want = TABLE["patterns"][pattern]
    if "error" in want:
        with pytest.raises(PatternError):
            Alphix(pattern, strict=False)
        return
    a = Alphix(pattern, strict=False)
    assert a.maxlen() == want["cmct"]
    n = len(want["aix"])
    assert [a.aix(i) for i in range(n)] == want["aix"]
    for label, nix in zip(want["aix"], want["nix"]):
        if label is not None:
            assert a.nix(label) == nix, (pattern, label)
    assert a.aix(want["cmct"]) is None           # one past the end


@pytest.mark.parametrize("case", TABLE["orders"],
                         ids=lambda c: f"{c['strip']}|{c['patch']}|{c['ixord']}")
def test_location_order_is_argylls(case):
    sa = Alphix(case["strip"], strict=False)
    pa = Alphix(case["patch"], strict=False)
    for loc, order in case["order"].items():
        assert patch_location_order(sa, pa, case["ixord"], loc) == order, loc


def test_the_table_really_holds_refusals_and_both_index_orders():
    """A frozen table with no refusals in it would prove nothing about them."""
    refused = [p for p, v in TABLE["patterns"].items() if "error" in v]
    assert {"A-Z;1-999", "A-Z;A", "A-Z;Z-A"} <= set(refused)
    assert {c["ixord"] for c in TABLE["orders"]} == {0, 1}


def test_the_default_patterns_label_exactly_what_chromiq_prints():
    """Exhaustive over Argyll's whole range: 702 strips, 999 patches. This is
    why nothing printed with the defaults changes."""
    s = Alphix(permutation.DEFAULT_STRIP_PATTERN)
    p = Alphix(permutation.DEFAULT_PATCH_PATTERN)
    ls = permutation.make_labeller(permutation.DEFAULT_STRIP_PATTERN)
    lp = permutation.make_labeller(permutation.DEFAULT_PATCH_PATTERN)
    assert s.maxlen() == 702 and p.maxlen() == 999
    assert [s.aix(i) for i in range(702)] == [ls(i + 1) for i in range(702)]
    assert [p.aix(i) for i in range(999)] == [lp(i + 1) for i in range(999)]


# ---- inputs the C side cannot survive are refused --------------------------
@pytest.mark.parametrize("pattern,kind", [
    ('A-Z"', "chars"),                 # breaks the CGATS line ti2_writer writes
    ("A-\x7f", "chars"),               # C loops for ever on a range ending at 127
    ("A-Ä", "chars"),                  # a negative `char` in C
    ("0-9\t", "chars"),
    ("", "empty"),
    ("9-0", "empty_digit"),            # a digit with no symbols: no labels at all
    (",A-Z", "empty_digit"),
    ("@-9", "blank_label"),            # index 0 is the label ""
    (" A-Z", "blank_label"),
    ("A-Z;AAAAAAAAAAAAAAAA-B", "range_length"),   # overruns _tb[11] in C
    ("A-Z, A-Z;AAA-B", "range_length"),
    ("A-Z;1-999", "range_start"),
    ("A-Z;A", "range_dash"),
    ("A-Z;A-1", "range_end"),
    ("A-Z;Z-A", "range_order"),
])
def test_a_pattern_the_c_side_cannot_take_is_refused(pattern, kind):
    with pytest.raises(PatternError) as exc:
        Alphix(pattern)
    assert exc.value.kind == kind


def test_a_blank_label_outside_the_ranges_is_fine():
    """"@-9,@-9;1-99" can make "" at index 0, but its range starts at 1."""
    a = Alphix("@-9,@-9;1-99")
    assert a.aix(0) == "1" and a.maxlen() == 99


# ---- check_patterns: a NEW layout ------------------------------------------
def test_the_forum_report_is_refused_and_says_why():
    """"0-9" for 14 strips: ten labels, fourteen strips."""
    problem = check_patterns("0-9", "A-Z", 14, 19)
    assert problem is not None and problem.field == "strip"
    assert "10" in problem.reason and "14" in problem.reason


@pytest.mark.parametrize("strip,patch,n_strips,steps,field", [
    ("0-9", "A-Z", 11, 19, "strip"),                      # 11+ strips
    ("1-999", "0-9,@-9,@-9;1-999", 12, 19, "strip"),      # one digit, 11 labels
    ("A-Z, A-Z", "1-999", 4, 12, "patch"),
    ("A-Z;1-999", "0-9,@-9,@-9;1-999", 4, 12, "strip"),   # Argyll refuses it
    ("A-Z, A-Z", "A-Z;1-999", 4, 12, "patch"),
    ("0-9,@-9;1-99", "0-9,@-9;1-99", 3, 10, ""),          # both numeric: "11"
    ("A-Z, A-Z", "A-Z, A-Z", 30, 30, ""),                 # both alphabetic
    ("A-Z", "0-9,@-9,@-9;1-999", 27, 10, "strip"),        # 27 strips, two pages
    ("A-Z, A-Z", "A-Z", 30, 27, "patch"),                 # the silent case
    ('A-Z"', "0-9,@-9,@-9;1-999", 4, 10, "strip"),
    ("A-Z;AAAAAAAAAAAAAAAAAAAAAAA-B", "0-9,@-9,@-9;1-999", 4, 10, "strip"),
    ("@-9", "A-Z", 2, 5, "strip"),
    ("A-Z, 2-9;A-X,2A-9Z", "A-Z, A-Z", 10, 10, ""),       # ECI strips, letter patches
])
def test_a_pair_the_readers_cannot_read_back_is_refused(strip, patch,
                                                        n_strips, steps, field):
    problem = check_patterns(strip, patch, n_strips, steps)
    assert problem is not None, (strip, patch)
    assert problem.field == field, problem
    assert problem.reason and "—" not in problem.reason


@pytest.mark.parametrize("strip,patch,n_strips,steps", [
    ("A-Z, A-Z", "0-9,@-9,@-9;1-999", 1, 1),
    ("A-Z, A-Z", "0-9,@-9,@-9;1-999", 60, 120),
    ("A-Z, A-Z", "0-9,@-9,@-9;1-999", 702, 30),          # every strip label
    ("A-Z, A-Z", "0-9,@-9,@-9;1-999", 27, 999),
    ("A-Z", "0-9,@-9,@-9;1-999", 26, 40),
    ("A-Z, A-Z", "0-9,@-9;1-99", 30, 99),
    # Knut, #182 5965589190: numbers for strips and letters for patches too.
    ("0-9", "A-Z", 10, 19),                               # strips 0 to 9
    ("0-9,@-9;1-99", "A-Z", 14, 19),                      # the forum layout, fixed
    ("0-9,@-9", "A-Z, A-Z", 30, 40),
    ("A-Z", "0-9", 3, 10),                                # patches 0 to 9
    ("a-z, a-z", "0-9,@-9,@-9;1-999", 3, 10),             # lower case, as typed
    ("A-Z, 2-9;A-X,2A-9Z", "0-9,@-9,@-9;1-999", 40, 20),  # ECI 2002R strips
    ("A-H,J-N,P-Z", "0-9,@-9;1-99", 30, 25),              # no I and no O
])
def test_a_pair_both_readers_read_back_is_accepted(strip, patch, n_strips,
                                                   steps):
    assert check_patterns(strip, patch, n_strips, steps) is None


def test_a_strip_count_is_every_page_together():
    assert alphix.strips_of(0, 19) == 0
    assert alphix.strips_of(266, 19) == 14
    assert alphix.strips_of(267, 19) == 15


# ---- the labels ChromIQ prints are ArgyllCMS's ------------------------------
def test_a_new_chart_is_labelled_as_argyll_labels_it():
    assert permutation.make_labeller("0-9")(1) == "0"
    assert permutation.make_labeller("A-Z")(1) == "A"
    assert permutation.location_label(0, 19, "0-9,@-9;1-99", "A-Z") == "1A"
    assert permutation.location_label(19 * 13 + 18, 19, "0-9,@-9;1-99",
                                      "A-Z") == "14S"


def test_the_old_rule_is_kept_for_charts_printed_with_it():
    assert permutation.make_labeller("0-9", "legacy")(14) == "14"
    assert permutation.location_label(19 * 13, 19, "0-9", "A-Z",
                                      "legacy") == "14A"


def test_both_rules_agree_on_the_default_patterns():
    for pat, n in ((permutation.DEFAULT_STRIP_PATTERN, 702),
                   (permutation.DEFAULT_PATCH_PATTERN, 999)):
        new = permutation.make_labeller(pat)
        old = permutation.make_labeller(pat, "legacy")
        assert [new(i) for i in range(1, n + 1)] == \
            [old(i) for i in range(1, n + 1)]


# ---- the build: a new layout is checked, a redraw of an old one is not -----
def _ti1(d: Path, n: int) -> Path:
    lines = ["CTI1", "", 'DESCRIPTOR "p"', 'ORIGINATOR "ChromIQ"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {(i*7)%100}.0 {(i*13)%100}.0 {(i*29)%100}.0 40 45 50")
    lines += ["END_DATA", ""]
    p = d / "p.ti1"
    if not p.exists():
        p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _build(tmp_path, name, strip="0-9", patch="A-Z", **kw):
    from workflow.layout_engine import chart as le_chart
    out = tmp_path / name
    out.mkdir()
    return le_chart.build_chart(_ti1(tmp_path, 400), out / "c", instrument="i1",
                                paper="A4", dpi=72, seed=7,
                                strip_pattern=strip, patch_pattern=patch,
                                **kw), out


def test_a_new_layout_with_the_forum_pattern_is_refused_before_any_file(tmp_path):
    from workflow.layout_engine import chart as le_chart
    out = tmp_path / "new"
    out.mkdir()
    with pytest.raises(alphix.PatternRefused) as exc:
        le_chart.build_chart(_ti1(tmp_path, 400), out / "c", instrument="i1",
                             paper="A4", dpi=72, seed=7, strip_pattern="0-9",
                             patch_pattern="A-Z")
    assert "0-9" in str(exc.value)
    assert list(out.iterdir()) == [], "nothing may be written"


def test_a_new_layout_with_numeric_strips_reads_back_in_both_directions(tmp_path):
    from workflow.layout_engine.labels import labels_for_chart
    res, out = _build(tmp_path, "n", strip="0-9,@-9;1-99")
    ti2 = out / "c.ti2"
    assert chart_locations_problem(ti2) is None
    cl = labels_for_chart(ti2)
    assert cl.rule == "argyll"
    text = ti2.read_text(encoding="utf-8")
    assert '"1A"' in text and 'STRIP_INDEX_PATTERN "0-9,@-9;1-99"' in text
    strips = res.layout.total_patches // res.layout.steps_in_pass
    assert cl.split(f"{strips}A") == (strips - 1, 0)


def test_a_redraw_of_a_printed_chart_keeps_its_labels_and_is_unchanged(tmp_path):
    """Restore Used Chart redraws a chart printed with ChromIQ's old rule with
    that rule, so a sheet already printed with "0-9" comes back exactly as it
    was printed, labels included."""
    res_a, out_a = _build(tmp_path, "a", label_rule="legacy")
    res_b, out_b = _build(tmp_path, "b", label_rule="legacy")
    assert res_a.layout.total_patches // res_a.layout.steps_in_pass > 10, \
        "the premise: more strips than '0-9' has labels"
    ti2_a = (out_a / "c.ti2").read_text(encoding="utf-8").splitlines()
    ti2_b = (out_b / "c.ti2").read_text(encoding="utf-8").splitlines()
    keep = lambda t: [ln for ln in t if not ln.startswith("CREATED")]  # noqa: E731
    assert keep(ti2_a) == keep(ti2_b)
    assert 'STRIP_INDEX_PATTERN "0-9"' in ti2_a
    assert any('"14' in ln for ln in ti2_a), "the old rule's strip 14"
    import hashlib
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    assert [h(p) for p in sorted(out_a.glob("*.tif"))] == \
        [h(p) for p in sorted(out_b.glob("*.tif"))]
    from workflow.layout_engine.labels import label_rule_of_chart
    assert label_rule_of_chart(out_a / "c.ti2") == "legacy"


# ---- Measure: a chart already printed -------------------------------------
def test_the_forum_chart_is_unreadable_and_names_the_first_bad_location(tmp_path):
    _res, out = _build(tmp_path, "forum", label_rule="legacy")
    detail = chart_locations_problem(out / "c.ti2")
    assert detail is not None
    assert "“" in detail


def test_a_default_chart_is_readable(tmp_path):
    _res, out = _build(tmp_path, "d", strip=permutation.DEFAULT_STRIP_PATTERN,
                       patch=permutation.DEFAULT_PATCH_PATTERN)
    assert chart_locations_problem(out / "c.ti2") is None


def _ti2(path: Path, locs, *, strip="A-Z, A-Z", patch="0-9,@-9,@-9;1-999",
         steps=3, passes="2", originator="ChromIQ layout engine",
         randomised=True) -> Path:
    head = ["CTI2", "", f'ORIGINATOR "{originator}"',
            f'STEPS_IN_PASS "{steps}"', f'PASSES_IN_STRIPS2 "{passes}"',
            f'STRIP_INDEX_PATTERN "{strip}"', f'PATCH_INDEX_PATTERN "{patch}"',
            'INDEX_ORDER "STRIP_THEN_PATCH"',
            'RANDOM_START "5"' if randomised else 'CHART_ID "5"',
            "", "NUMBER_OF_FIELDS 2", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID SAMPLE_LOC ", "END_DATA_FORMAT", "",
            f"NUMBER_OF_SETS {len(locs)}", "BEGIN_DATA"]
    rows = [f'{i + 1} "{loc}" ' for i, loc in enumerate(locs)]
    path.write_text("\n".join(head + rows + ["END_DATA", ""]), encoding="utf-8")
    return path


def test_a_chart_that_parses_but_sorts_wrongly_is_caught(tmp_path):
    """The silent case of the challenge: 'A-Z, A-Z' strips with 'A-Z' patches
    past 26 steps. "AAA" is strip A patch 27 on paper, and strip AA patch A to
    Argyll, so the readings would land on the wrong patches without an error."""
    locs = ([f"A{permutation.alpha_label(p)}" for p in range(1, 28)]
            + [f"B{permutation.alpha_label(p)}" for p in range(1, 28)])
    ti2 = _ti2(tmp_path / "c.ti2", locs, patch="A-Z", steps=27)
    assert chart_locations_problem(ti2) is not None


def test_a_numeric_strip_chart_off_by_one_is_caught(tmp_path):
    """"0-9" with five strips parses, and announces 0 to 4 for a sheet printed
    1 to 5."""
    locs = [f"{s}{permutation.alpha_label(p)}" for s in range(1, 6)
            for p in range(1, 4)]
    ti2 = _ti2(tmp_path / "c.ti2", locs, strip="0-9", patch="A-Z", passes="5")
    assert chart_locations_problem(ti2) is not None


def test_a_printtarg_chart_with_its_own_patterns_is_readable(tmp_path):
    """Not ChromIQ's: Argyll made the labels with its own patterns, so the
    ECI scheme printtarg documents reads fine, while the same labels under a
    patch pattern they do not fit do not."""
    sa, pa = Alphix("A-Z, 2-9;A-X,2A-9Z"), Alphix("0-9,@-9,@-9;1-999")
    locs = [sa.aix(s) + pa.aix(p) for s in range(30) for p in range(2)]
    ti2 = _ti2(tmp_path / "c.ti2", locs, strip="A-Z, 2-9;A-X,2A-9Z", steps=2,
               passes="30", originator="Argyll printtarg")
    assert chart_locations_problem(ti2) is None
    ti2 = _ti2(tmp_path / "d.ti2", locs, strip="A-Z, 2-9;A-X,2A-9Z",
               patch="A-Z", steps=2, passes="30", originator="Argyll printtarg")
    assert chart_locations_problem(ti2) is not None


def test_an_unrandomised_foreign_chart_with_odd_locations_is_left_alone(tmp_path):
    """chartread reads such a chart in file order (no sort), so it works today
    and must not be blocked."""
    ti2 = _ti2(tmp_path / "c.ti2", ["P-1", "P-2", "P-3"], steps=3, passes="1",
               originator="someone else", randomised=False)
    assert chart_locations_problem(ti2) is None
    ti2 = _ti2(tmp_path / "d.ti2", ["P-1", "P-2", "P-3"], steps=3, passes="1",
               originator="someone else", randomised=True)
    assert chart_locations_problem(ti2) is not None


def test_two_locations_argyll_reads_as_one_patch_are_caught(tmp_path):
    ti2 = _ti2(tmp_path / "c.ti2", ["A1", "A01"], steps=2, passes="1",
               originator="someone else")
    assert chart_locations_problem(ti2) is not None


def test_a_chart_with_a_pattern_argyll_refuses_is_unreadable(tmp_path):
    ti2 = _ti2(tmp_path / "c.ti2", ["A1", "A2"], strip="A-Z;1-999", steps=2,
               passes="1")
    assert chart_locations_problem(ti2) is not None


def test_a_file_without_locations_is_not_this_checks_business(tmp_path):
    p = tmp_path / "c.ti2"
    p.write_text("CTI2\n\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n",
                 encoding="utf-8")
    assert chart_locations_problem(p) is None
    assert chart_locations_problem(tmp_path / "missing.ti2") is None
