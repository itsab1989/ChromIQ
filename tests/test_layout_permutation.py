"""Tests for the reproducible shuffle + index-label generator."""
from workflow.layout_engine import permutation as perm


def test_alpha_label_odometer():
    assert perm.alpha_label(1) == "A"
    assert perm.alpha_label(26) == "Z"
    assert perm.alpha_label(27) == "AA"
    assert perm.alpha_label(52) == "AZ"
    assert perm.alpha_label(53) == "BA"
    assert perm.alpha_label(702) == "ZZ"
    assert perm.alpha_label(703) == "AAA"


def test_make_labeller():
    assert perm.make_labeller("A-Z, A-Z")(2) == "B"
    assert perm.make_labeller("0-9,@-9;1-99")(5) == "5"
    assert perm.make_labeller("0-9,@-9,@-9;1-999")(12) == "12"


def test_labels_follow_argylls_grammar_and_the_old_rule_survives():
    """"1-999" is not a numeric pattern to ArgyllCMS: it is ONE digit, 1 to 9
    and then 9 twice more. This file used to say it gave 1, 2, 3 ...; ChromIQ
    now labels as ArgyllCMS does (forum report and Knut's ruling, #182
    5965589190), so the tenth label is "9", and a new layout with more than
    eleven strips is refused. The old rule is kept for charts printed with it."""
    from workflow.layout_engine import alphix
    assert perm.make_labeller("1-999")(10) == "9"
    assert perm.make_labeller("1-999", "legacy")(10) == "10"
    assert alphix.check_patterns("A-Z, A-Z", "1-999", 2, 12) is not None


def test_location_label_grid():
    # 21 steps per pass: slot 0 -> A1, slot 20 -> A21, slot 21 -> B1.
    assert perm.location_label(0, 21) == "A1"
    assert perm.location_label(20, 21) == "A21"
    assert perm.location_label(21, 21) == "B1"
    # custom numeric strip + alpha patch, in a pattern ArgyllCMS reads the
    # same way ("1-999" is one digit to Argyll, see the test above)
    assert perm.location_label(0, 21, strip_pattern="0-9,@-9;1-99",
                               patch_pattern="A-Z") == "1A"


def test_permutation_reproducible():
    a = perm.location_permutation(63, 42)
    b = perm.location_permutation(63, 42)
    assert a == b                                   # same seed -> same layout
    assert a != perm.location_permutation(63, 7)    # different seed -> different
    assert sorted(a) == list(range(63))             # a true permutation


def test_no_randomize_is_identity():
    assert perm.location_permutation(10, 999, randomize=False) == list(range(10))


def test_preview():
    head, last = perm.preview(63, 21, count=3)
    assert head == ["A1", "A2", "A3"]
    assert last == "C21"      # slot 62 -> strip 2 (C), pos 20 (21)
