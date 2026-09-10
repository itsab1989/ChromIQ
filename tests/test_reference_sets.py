"""Reference sets (#182): the bundled Fogra data, the credit gate, and the
rules for what a CMYK printing condition may judge on an RGB sheet.

Each test here was mutation-proved: the mutation is named in the test's own
docstring, and the check was watched to go red under it before being kept.
"""
import json
import shutil

import pytest

from workflow import reference_sets as rs


@pytest.fixture(autouse=True)
def _fresh_cache():
    rs.reset_cache()
    yield
    rs.reset_cache()


# ---------------------------------------------------------------------------
# The data that ships
# ---------------------------------------------------------------------------
def test_eleven_printing_conditions_are_bundled_and_all_are_credited():
    """MUTATION: delete the "source" of one entry in SOURCE.json and this drops
    to ten. Proved by the credit-gate test below."""
    sets = rs.available()
    assert len(sets) == 11, [s.id for s in sets]
    for s in sets:
        assert s.source, s.id
        assert s.terms, s.id
        assert "Fogra" in s.source, s.source


def test_every_bundled_file_is_byte_for_byte_the_one_fogra_published():
    """Fogra's grant is conditional on unmodified redistribution, so this is
    checked rather than asserted.

    MUTATION: append one byte to FOGRA51_MW3_Subset.txt and this goes red. It
    was watched to; see test_a_tampered_file_is_detected, which is the same
    mutation kept as a test, because an assertion that only ever expects True
    cannot tell a working check from one that always says yes.
    """
    for s in rs.available():
        assert rs.verify_unmodified(s), f"{s.id} does not match its sha256"


def test_a_tampered_file_keeps_its_place_and_loses_its_claim(tmp_path, monkeypatch):
    """The other half of the check above, and the half that can actually fail.

    This went through two wrong shapes before it settled, and both are worth
    keeping in view.

    First it only asked whether the CHECKER worked, and a challenge round
    pointed out that `verify_unmodified` had no caller outside this file: the
    promise that the data travels unaltered was kept by a developer's gate run
    and by nothing on a user's machine.

    Then `available()` DROPPED a set whose bytes had moved, and the next round
    was right that this reasons about the wrong event. Fogra's condition is on
    DISTRIBUTION, which happens when the bundle is built and is checked by the
    gate. A mismatch here is on a user's disk, where it means a truncated
    download, a re-signed bundle or a sync tool touching line endings, and the
    answer to that is not to make a printing condition disappear.

    What ChromIQ cannot do with a changed file is present it as Fogra's own
    data. So the set stays and the CREDIT changes, which is the ICC's condition
    applied where it fits.

    MUTATION: make verify_unmodified return True unconditionally, or drop the
    call from available(), and this goes red where the all-True assertion above
    stays green.
    """
    dst = _stage(tmp_path, monkeypatch)
    p = dst / "FOGRA51_MW3_Subset.txt"
    p.write_bytes(p.read_bytes() + b"\n")
    rs.reset_cache()

    offered = rs.available()
    assert len(offered) == 11, (
        "a set vanished because the file on disk changed; a user is left with "
        "a shorter list and no way to find out why")
    s = rs.by_id("FOGRA51")
    assert s is not None
    assert s.verified is False, "the changed file is still marked as verified"
    assert "no longer matches" in s.credit_line, (
        "the credit still presents a changed file as Fogra's original data: "
        f"{s.credit_line!r}")

    for other in offered:
        if other.id != "FOGRA51":
            assert other.verified, other.id
            assert "no longer matches" not in other.credit_line, other.id


def test_the_credit_does_not_end_a_sentence_twice(tmp_path):
    """Fogra's name ends in "e.V." and the template added a stop of its own, so
    the sentence their permission requires printed "e.V..", twice a line."""
    for s in rs.available():
        assert ".." not in s.credit_line, s.credit_line


def test_the_terms_carry_fogras_own_no_endorsement_sentence():
    """The clause the whole design has to satisfy must actually be recorded,
    not paraphrased away.

    MUTATION: shorten the terms string in SOURCE.json to the first sentence and
    this goes red.
    """
    for s in rs.available():
        assert "does not imply certification, approval or endorsement" in s.terms
        assert "unmodified" in s.terms


def test_every_set_is_the_seventy_two_patch_mediawedge():
    """Knut, 2026-09-09: a 48 or 84 patch verification chart is fine. 72 fits;
    1617 is a profiling chart.

    MUTATION: swap in a full 1617-patch file and this goes red.
    """
    for s in rs.available():
        assert s.patches == 72, (s.id, s.patches)
        assert len(rs.read_aims(s)) == 72, s.id


def test_the_credit_line_names_fogra_and_denies_endorsement():
    """MUTATION: drop the second sentence from ReferenceSet.credit_line and the
    'not a certification' assertion goes red."""
    s = rs.by_id("FOGRA51")
    assert s is not None
    line = s.credit_line
    assert "FOGRA51" in line
    assert "Fogra" in line
    assert "not a certification" in line
    for word in ("conforms", "certified to", "qualifies as"):
        assert word not in line.lower()


def test_no_user_facing_string_here_carries_an_em_dash():
    """The project rule, enforced for this module's own catalogue.

    MUTATION: put an em dash into any REFUSAL_REASONS sentence and this goes
    red.
    """
    strings = list(rs.REFUSAL_REASONS.values()) + list(rs.GROUP_LABELS.values())
    strings += [s.label for s in rs.available()]
    strings += [s.blurb for s in rs.available()]
    for text in strings:
        assert "—" not in text, text


# ---------------------------------------------------------------------------
# The credit gate
# ---------------------------------------------------------------------------
def _stage(tmp_path, monkeypatch, mutate=None):
    """A copy of the shipped folder that a test may edit."""
    src = rs._data_dir()
    dst = tmp_path / "fogra"
    shutil.copytree(src, dst)
    if mutate is not None:
        doc = json.loads((dst / rs.SOURCE_FILE).read_text(encoding="utf-8"))
        mutate(doc)
        (dst / rs.SOURCE_FILE).write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(rs, "_data_dir", lambda: dst)
    rs.reset_cache()
    return dst


def _restamp(dst, set_id: str) -> None:
    """Record the sha256 the set's file NOW has, for a test that edits one.

    `available()` refuses a file whose bytes no longer match what SOURCE.json
    records, which is the point of that gate. A test that edits a file to ask a
    question about the READER has to move the recorded hash with it, or it is
    asking about the gate instead and gets no reader at all.
    """
    import hashlib
    doc = json.loads((dst / rs.SOURCE_FILE).read_text(encoding="utf-8"))
    entry = doc["sets"][set_id]
    data = (dst / entry["file"]).read_bytes()
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    (dst / rs.SOURCE_FILE).write_text(json.dumps(doc), encoding="utf-8")
    rs.reset_cache()


def test_a_data_file_with_no_credit_is_not_offered(tmp_path, monkeypatch):
    """The condition met by construction: strip FOGRA51's source and it
    disappears from the list, rather than appearing uncredited.

    MUTATION PROOF: the same staging WITHOUT the mutation returns 11 (asserted
    below), so the drop to 10 is caused by the missing credit and not by the
    staging.
    """
    _stage(tmp_path, monkeypatch)
    assert len(rs.available()) == 11

    def strip_source(doc):
        doc["sets"]["FOGRA51"]["source"] = ""

    _stage(tmp_path / "b", monkeypatch, strip_source)
    ids = [s.id for s in rs.available()]
    assert "FOGRA51" not in ids
    assert len(ids) == 10


def test_a_data_file_with_no_terms_is_not_offered(tmp_path, monkeypatch):
    """MUTATION PROOF: as above, the unmutated staging returns 11."""
    def strip_terms(doc):
        del doc["sets"]["FOGRA52"]["terms"]

    _stage(tmp_path, monkeypatch, strip_terms)
    ids = [s.id for s in rs.available()]
    assert "FOGRA52" not in ids
    assert len(ids) == 10


def test_an_entry_whose_file_is_missing_is_not_offered(tmp_path, monkeypatch):
    dst = _stage(tmp_path, monkeypatch)
    (dst / "FOGRA39_MW3_Subset.txt").unlink()
    rs.reset_cache()
    assert "FOGRA39" not in [s.id for s in rs.available()]


def test_an_unreadable_source_file_offers_nothing_and_never_raises(
        tmp_path, monkeypatch):
    dst = _stage(tmp_path, monkeypatch)
    (dst / rs.SOURCE_FILE).write_text("{ not json", encoding="utf-8")
    rs.reset_cache()
    assert rs.available() == []


# ---------------------------------------------------------------------------
# Reading, and the header that lies
# ---------------------------------------------------------------------------
def test_the_row_count_is_counted_and_not_read_from_the_header(tmp_path,
                                                               monkeypatch):
    """Fogra's own FOGRA43.txt declares 216 sets over 1617 rows. A reader that
    trusts NUMBER_OF_SETS drops seven eighths of a file and reports a confident
    number computed from the rest.

    MUTATION: this test writes the lie itself. If read_aims ever starts reading
    the header, the count comes back 3 instead of 72 and this goes red.
    """
    dst = _stage(tmp_path, monkeypatch)
    p = dst / "FOGRA51_MW3_Subset.txt"
    text = p.read_text(encoding="utf-8")
    assert "NUMBER_OF_SETS" in text
    p.write_text(text.replace("NUMBER_OF_SETS\t72", "NUMBER_OF_SETS\t3")
                     .replace("NUMBER_OF_SETS 72", "NUMBER_OF_SETS 3"),
                 encoding="utf-8")
    _restamp(dst, "FOGRA51")
    s = rs.by_id("FOGRA51")
    assert s is not None, "the re-stamp did not take, so this proves nothing"
    assert len(rs.read_aims(s)) == 72


def test_the_paper_white_is_the_patch_with_every_channel_at_zero():
    """FOGRA51's paper, measured from Fogra's file on 2026-09-10:
    L* 95.00, a* 1.50, b* -6.00.

    MUTATION: change the expected b* to -5.0 and this goes red, so the test is
    reading the file and not a constant of its own.
    """
    s = rs.by_id("FOGRA51")
    assert s is not None
    lab = rs.paper_lab(s)
    assert lab is not None
    assert lab == pytest.approx((95.00, 1.50, -6.00), abs=0.01)


def test_the_two_likeliest_candidates_differ_enough_to_matter():
    """FOGRA51 and FOGRA52 are the coated and uncoated current conditions, and
    a user picking the wrong one of the two changes the paper verdict on its
    own. Measured: they are more than 3 dE00 apart.

    MUTATION: compare FOGRA51 against itself and the difference is 0, which
    fails the assertion.
    """
    coated, uncoated = rs.by_id("FOGRA51"), rs.by_id("FOGRA52")
    assert coated is not None and uncoated is not None
    de = rs.substrate_de00(coated, rs.paper_lab(uncoated))
    assert de is not None
    assert de > 3.0, de


def test_the_substrate_row_compares_a_measured_paper_against_the_reference():
    """MUTATION: return the reference lab unchanged from substrate_de00 and the
    perfect-match case still reads 0, but the 4-unit case below reads 0 too and
    goes red."""
    s = rs.by_id("FOGRA51")
    assert s is not None
    assert rs.substrate_de00(s, rs.paper_lab(s)) == pytest.approx(0.0, abs=1e-6)
    drifted = tuple(v + d for v, d in zip(rs.paper_lab(s), (0.0, 0.0, 4.0)))
    assert rs.substrate_de00(s, drifted) > 1.0


# ---------------------------------------------------------------------------
# The elephant: what a CMYK condition may judge on an RGB sheet
# ---------------------------------------------------------------------------
def test_the_paper_row_is_allowed_on_an_rgb_sheet():
    """A paper's colour is a property of the paper, not of the process.

    MUTATION: set ROW_PAIRING["substrate_de00_max"] to "same" and this goes
    red.
    """
    s = rs.by_id("FOGRA51")
    ok, reason = rs.can_fill("substrate_de00_max", s, "RGB")
    assert ok and reason is None


@pytest.mark.parametrize("row", ["solids_de00_max", "cmy_solids_dhab_max"])
def test_the_solids_rows_are_refused_on_an_rgb_sheet(row):
    """Pairing a printer's most saturated cyan with a 100 % cyan offset solid
    because both are called C is pairing two things because their labels rhyme.

    MUTATION: set ROW_PAIRING[row] to "any" and this goes red.
    """
    s = rs.by_id("FOGRA51")
    ok, reason = rs.can_fill(row, s, "RGB")
    assert not ok
    assert reason == rs.REFUSE_CROSS_SPACE
    text = rs.refusal_text(reason)
    assert "CMYK printing condition" in text
    assert "—" not in text


def test_the_solids_rows_are_still_refused_on_a_matching_cmyk_sheet():
    """Same device space is not enough. The patches still have no partner
    unless the chart was built from the reference.

    MUTATION: drop the chart_built_from_reference branch and return True for a
    matching space, and this goes red.
    """
    s = rs.by_id("FOGRA51")
    ok, reason = rs.can_fill("solids_de00_max", s, "CMYK")
    assert not ok
    assert reason == rs.REFUSE_NEEDS_BUILT_CHART


def test_a_chart_built_from_the_reference_unlocks_the_solids_rows():
    """The one legitimate route to the full comparison.

    MUTATION: ignore chart_built_from_reference and this goes red.
    """
    s = rs.by_id("FOGRA51")
    ok, reason = rs.can_fill("solids_de00_max", s, "CMYK",
                             chart_built_from_reference=True)
    assert ok and reason is None


def test_an_exchange_space_cannot_fill_the_paper_row(tmp_path, monkeypatch):
    """FOGRA53, FOGRA55 and FOGRA59 have a paper white that is a construction,
    not a measurement of stock. None is bundled; this proves the guard works if
    one ever is.

    MUTATION: drop the is_real_paper branch from can_fill and this goes red.
    """
    def make_exchange_space(doc):
        doc["sets"]["FOGRA51"]["is_real_paper"] = False

    _stage(tmp_path, monkeypatch, make_exchange_space)
    s = rs.by_id("FOGRA51")
    ok, reason = rs.can_fill("substrate_de00_max", s, "RGB")
    assert not ok
    assert reason == rs.REFUSE_NOT_A_PAPER
    assert rs.substrate_de00(s, (95.0, 0.0, 0.0)) is None


def test_a_row_this_version_cannot_fill_says_so_rather_than_guessing():
    s = rs.by_id("FOGRA51")
    ok, reason = rs.can_fill("all_de00_avg", s, "RGB")
    assert not ok
    assert reason == rs.REFUSE_UNKNOWN_ROW


# ---------------------------------------------------------------------------
# Never a silent partial answer
# ---------------------------------------------------------------------------
def test_partial_coverage_is_stated_with_both_numbers():
    """MUTATION: drop {total} from the sentence and the '72' assertion goes
    red."""
    text = rs.coverage_text(40, 72)
    assert "40" in text and "72" in text


def test_a_sheet_with_nothing_in_common_says_so_and_says_what_to_do():
    text = rs.coverage_text(0, 72)
    assert "no patch in common" in text
    assert "Choose a reference" in text


def test_one_aim_gets_a_singular_sentence():
    """The project rule: count-bearing messages get explicit singular and
    plural variants, never '(s)'.

    MUTATION: fold the singular branch into the plural one and this goes red.
    """
    assert "1 aim colour " in rs.coverage_text(1, 72)
    assert "aim colours " in rs.coverage_text(2, 72)


# ---------------------------------------------------------------------------
# The chooser
# ---------------------------------------------------------------------------
def test_the_groups_are_the_users_vocabulary_not_the_files():
    """MUTATION: put a FOGRAxx name into a group label and this goes red."""
    for gid, members in rs.grouped():
        assert members
        assert "FOGRA" not in rs.GROUP_LABELS[gid]


def test_the_display_label_leads_with_what_the_user_has_in_front_of_them():
    """The set's name is IN the row, never AS the row.

    MUTATION: make display_label return self.id and this goes red.
    """
    s = rs.by_id("FOGRA51")
    assert s.display_label.startswith("Coated commercial print")
    assert "(FOGRA51)" in s.display_label


def test_nothing_in_this_module_produces_a_verdict_word():
    """A reference supplies aims; the verdict comes from a limit set, so PASS
    is always under ChromIQ's name. This is the structural half of the promise
    made to Fogra in writing.

    MUTATION: add a function returning "PASS" and this goes red.
    """
    import inspect
    src = inspect.getsource(rs)
    body = "\n".join(line for line in src.splitlines()
                     if not line.lstrip().startswith("#"))
    for word in ('"PASS"', "'PASS'", '"FAIL"', "'FAIL'"):
        assert word not in body, word
