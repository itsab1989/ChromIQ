"""A newer Fogra file, without a newer ChromIQ, and the line it may not cross.

ChromIQ ships eleven Fogra characterisation files and works offline out of the
box. Fogra's archive does not stand still: conditions are revised, FOGRA61 is
still beta and ships nowhere, and none of that waits for a ChromIQ release.
Sebastian, 2026-09-20: *"we could ship the most recent version and allow for a
way to use newer values if they are released at some point in the future
without relying on an update to ChromIQ for it."*

So a user may put their own file in, per set, and take it out again.

**AND THE LINE THIS FILE EXISTS TO HOLD.** `data/reference_sets/LICENSE` and
the licence page inside the app both make a claim about the bundled files: they
are Fogra's own bytes, recorded with a sha256 in `SOURCE.json`, checked byte
for byte on every run. ChromIQ can make no such claim about a file somebody
dropped into a folder on their own machine. It knows only when the file
arrived, what it was called, and what its checksum was at that moment, and
every guard below is about the two records staying separate: the bundled claim
survives only because nothing the user supplies is ever folded into it.

The files are synthesised here rather than downloaded. The real FOGRA51 subset
that ships is used where a genuine Fogra file is wanted, and every other case
is built in the test, so nothing here depends on a folder on one machine.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from workflow import reference_sets as rs


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------
def _cgats(descriptor: str, fields: str, rows: "list[str]", *,
           extra: str = "") -> bytes:
    """A CGATS file with Fogra's own shape, CRLF and all.

    **CRLF IS NOT A DETAIL HERE.** Every Fogra file measured on 2026-09-20 uses
    it, the bundled FOGRA51 subset included, and the reader on this path takes
    BYTES out of a zip rather than going through `Path.read_text`, which would
    have translated them. Writing LF in the fixture would have made every test
    in this file pass over a reader that refuses every real file as "not a
    reference data file".
    """
    body = [
        "ISO28178",
        f'FILE_DESCRIPTOR\t"{descriptor}"',
        'ORIGINATOR\t"Fogra, www.fogra.org"',
        'CREATED\t"May 2015"',
    ]
    if extra:
        body.append(extra)
    body += [
        f"NUMBER_OF_FIELDS\t{len(fields.split())}",
        "BEGIN_DATA_FORMAT",
        fields,
        "END_DATA_FORMAT",
        f"NUMBER_OF_SETS\t{len(rows)}",
        "BEGIN_DATA",
        *rows,
        "END_DATA",
        "",
    ]
    return "\r\n".join(body).encode("utf-8")


def _cmyk_file(descriptor: str = "FOGRA51_MW3_Subset") -> bytes:
    """A four-patch CMYK set: paper, and one of each solid."""
    return _cgats(descriptor,
                  "SAMPLE_ID\tCMYK_C\tCMYK_M\tCMYK_Y\tCMYK_K\tLAB_L\tLAB_A\tLAB_B",
                  ["1\t0\t0\t0\t0\t95.10\t1.40\t-6.10",
                   "2\t100\t0\t0\t0\t56.12\t-34.90\t-52.52",
                   "3\t0\t100\t0\t0\t48.06\t75.29\t-5.18",
                   "4\t0\t0\t100\t0\t89.00\t-4.00\t93.00"])


def _rgb_file(descriptor: str = "3D-DesignRGB_FOGRA61(beta)") -> bytes:
    """An RGB exchange set, the shape the real FOGRA61 beta has.

    Black FIRST, so a reader that takes "every channel at zero" to mean paper
    finds something and returns it. That is the fault this material exists to
    catch and it is a silent one: L* 11 as a paper white produces a large
    substrate number and no error anywhere.
    """
    return _cgats(descriptor,
                  "SAMPLE_ID\tRGB_R\tRGB_G\tRGB_B\tLAB_L\tLAB_A\tLAB_B",
                  ["1\t0.00\t0.00\t0.00\t11.000\t0.000\t0.000",
                   "2\t128.00\t128.00\t128.00\t53.000\t0.000\t0.000",
                   "3\t255.00\t255.00\t255.00\t91.000\t-1.000\t4.000"])


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """The user's own folder, somewhere harmless, and an empty cache."""
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    rs.reset_cache()
    assert str(tmp_path) in str(rs.user_dir()), rs.user_dir()
    yield tmp_path
    rs.reset_cache()


def _drop(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


# ---------------------------------------------------------------------------
# The upgrade path itself
# ---------------------------------------------------------------------------
def test_a_newer_file_for_a_shipped_set_takes_over_and_keeps_its_condition(
        sandbox):
    """The ordinary case: Fogra revises FOGRA51 and the user has the new file.

    What must change is everything about the FILE. What must NOT change is
    everything about the CONDITION: a revision of FOGRA51 is still coated
    commercial print, and dropping the label would file the user's own file
    under a bare code in a group called "Supplied by you", which is worse for
    them in every way.

    MUTATION, run: make `_wearing_the_shipped_metadata` return `supplied`
    unchanged and this goes red on the label; delete the whole overlay in
    `available()` and it goes red on `supplied_by_user`.
    """
    shipped = rs.by_id("FOGRA51")
    assert shipped is not None and not shipped.supplied_by_user

    rs.install_user_file(_drop(sandbox, "FOGRA51_new.txt", _cmyk_file()))

    now = rs.by_id("FOGRA51")
    assert now.supplied_by_user, "the user's copy is not in force"
    assert now.path != shipped.path, "it is still reading the bundled file"
    assert now.original_filename == "FOGRA51_new.txt"
    assert now.imported, "nothing recorded WHEN it arrived"
    # the condition survives
    assert now.label == shipped.label
    assert now.group == shipped.group == "coated"
    assert now.is_real_paper is True
    # and the aims come from the new file
    assert rs.paper_lab(now) == pytest.approx((95.10, 1.40, -6.10))


def test_a_set_chromiq_ships_nothing_for_can_arrive_from_the_user(sandbox):
    """FOGRA61 is the case that makes this an upgrade path and not an override.

    It is still beta in Fogra's archive, ChromIQ ships nothing for it, and a
    design that could only REPLACE a shipped set could never hold it. It is
    also RGB, which is why the paper rule below had to change.

    MUTATION, run: make `available()` skip a supplied id that `bundled()` does
    not know and this goes red.
    """
    assert rs.by_id("FOGRA61") is None, "this test is pointless if it ships"
    before = len(rs.available())

    ids = rs.install_user_file(_drop(sandbox, "FOGRA61_beta.txt", _rgb_file()))
    assert ids == ["FOGRA61"], ids

    s = rs.by_id("FOGRA61")
    assert s is not None
    assert len(rs.available()) == before + 1
    assert s.group == rs.SUPPLIED_GROUP
    assert s.device_space == "RGB"
    assert s.patches == 3
    assert len(rs.bundled()) == 11, "it must not reach the bundled list"


def test_the_set_is_read_out_of_the_file_and_not_out_of_its_name(sandbox):
    """Fogra's own naming is not uniform: ``FOGRA51_MW3_Subset``,
    ``3D-DesignRGB_FOGRA61(beta)``, ``MW7C_Ref_FOGRA55_CMYKOGV``. A user's
    download may be called anything at all, so the descriptor inside the file
    is asked first and the file name is the fallback.

    MUTATION, run: swap the two so the file name wins, and this goes red.

    **AND THE FIRST VERSION OF THIS COULD NOT SEE THAT MUTATION.** It used a
    file called ``download (3).txt``, which carries no set name at all, so the
    two orders gave the same answer and the swap stayed green. The material has
    to make the two sources DISAGREE or the test is only asserting that one of
    them works. Measured: with the file named for FOGRA39 and the descriptor
    naming FOGRA52, the swap goes red.
    """
    # the name a download often has, with nothing in it
    anon = _drop(sandbox, "download (3).txt", _cmyk_file("FOGRA52_MW3_Subset"))
    assert rs.install_user_file(anon) == ["FOGRA52"]
    assert rs.by_id("FOGRA52").supplied_by_user
    assert rs.forget_user_set("FOGRA52")

    # and the two disagreeing: the file SAYS what it is, so the file wins
    wrong = _drop(sandbox, "FOGRA39_MW3_Subset.txt",
                  _cmyk_file("FOGRA52_MW3_Subset"))
    assert rs.install_user_file(wrong) == ["FOGRA52"]
    assert rs.by_id("FOGRA52").supplied_by_user
    assert not rs.by_id("FOGRA39").supplied_by_user, \
        "a misnamed download overwrote a different printing condition"

    # a name is still enough when the file's own header has no set in it
    bare = _drop(sandbox, "FOGRA45_MW3_Subset.txt",
                 _cmyk_file("Ugra/Fogra MediaWedge"))
    assert rs.install_user_file(bare) == ["FOGRA45"]


def test_stop_using_it_drops_back_to_what_shipped(sandbox):
    """Both directions of it, because they differ.

    For a set ChromIQ ships, "back" is the bundled file. For one it does not,
    "back" is the set not being offered at all, and neither may leave a file
    of the user's lying in ChromIQ's folder afterwards.

    MUTATION, run: make `forget_user_set` drop the record and leave the file,
    and the `list(...)` assertion below goes red.
    """
    rs.install_user_file(_drop(sandbox, "a.txt", _cmyk_file()))
    rs.install_user_file(_drop(sandbox, "b.txt", _rgb_file()))
    assert rs.by_id("FOGRA51").supplied_by_user
    assert rs.by_id("FOGRA61") is not None

    assert rs.forget_user_set("FOGRA51") is True
    assert rs.by_id("FOGRA51").supplied_by_user is False, "still on the user's"
    assert rs.by_id("FOGRA51").verified, "the bundled file is back and intact"

    assert rs.forget_user_set("FOGRA61") is True
    assert rs.by_id("FOGRA61") is None, "a set with no shipped copy must go"

    left = [p.name for p in rs.user_dir().glob("*.txt")]
    assert left == [], left
    assert rs.user_record() == {}
    assert rs.forget_user_set("FOGRA51") is False, "it removed something twice"


def test_a_zip_installs_every_set_in_it_and_says_so(sandbox):
    """Fogra publishes an archive, so ChromIQ reads one. Asking a user to
    unpack it first is a step that exists only for ChromIQ's convenience.

    The readme that travels beside the data must not stop the install, and an
    archive with nothing usable in it must not report success.
    """
    zp = sandbox / "MK3_Subsets.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("subs/FOGRA51_MW3_Subset.txt", _cmyk_file())
        z.writestr("subs/FOGRA52_MW3_Subset.txt", _cmyk_file("FOGRA52_MW3"))
        z.writestr("subs/readmeMW3_Subsets.txt", b"Fogra, www.fogra.org\r\n")
    assert sorted(rs.install_user_file(zp)) == ["FOGRA51", "FOGRA52"]

    empty = sandbox / "nothing.zip"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", b"hello\r\n")
    with pytest.raises(ValueError) as exc:
        rs.install_user_file(empty)
    assert "Nothing in that archive" in str(exc.value)


@pytest.mark.parametrize("name,data,says", [
    ("empty.txt", b"", "not a reference data file"),
    ("prose.txt", b"Dear Fogra,\r\nplease send data.\r\n",
     "not a reference data file"),
    ("nolab.txt", _cgats("FOGRA51", "SAMPLE_ID\tCMYK_C\tCMYK_M\tCMYK_Y\tCMYK_K",
                         ["1\t0\t0\t0\t0"]), "no CIELAB columns"),
    ("nodev.txt", _cgats("FOGRA51", "SAMPLE_ID\tLAB_L\tLAB_A\tLAB_B",
                         ["1\t95\t1\t-6"]), "no device columns"),
    ("noname.txt", _cgats("Some other target",
                          "SAMPLE_ID\tCMYK_C\tCMYK_M\tCMYK_Y\tCMYK_K\t"
                          "LAB_L\tLAB_A\tLAB_B",
                          ["1\t0\t0\t0\t0\t95\t1\t-6"]),
     "cannot tell which reference set"),
])
def test_rubbish_is_refused_at_the_door_and_told_why(sandbox, name, data, says):
    """Every refusal a user can provoke, with the sentence they get.

    The refusal is the useful half. A file installed and only then found to
    hold nothing readable becomes a set that shows no aims and explains
    nothing, with no way back to the moment a different file could have been
    picked.
    """
    with pytest.raises(ValueError) as exc:
        rs.install_user_file(_drop(sandbox, name, data))
    assert says in str(exc.value), str(exc.value)
    assert rs.user_record() == {}, "it was recorded anyway"
    assert not list(rs.user_dir().glob("*.txt")), "it was written anyway"


def test_a_file_inside_a_zip_cannot_choose_where_it_lands(sandbox):
    """A zip member names its own path, and a member called
    ``../../SUPPLIED.json`` must not be able to use it.

    The stored name is ChromIQ's: the set id, which `_SET_ID_RE` can only ever
    match as FOGRA plus digits. Nothing a user or an archive supplies reaches
    the filesystem as a path.

    MUTATION, run: write the member's own name instead of ``f"{set_id}.txt"``
    and this goes red on the escaped file.
    """
    zp = sandbox / "nasty.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("../../FOGRA51_escape.txt", _cmyk_file())
        z.writestr("nested/deep/SUPPLIED.json.txt", _cmyk_file("FOGRA52_MW3"))
    assert sorted(rs.install_user_file(zp)) == ["FOGRA51", "FOGRA52"]

    written = sorted(q.name for q in rs.user_dir().iterdir())
    assert written == ["FOGRA51.txt", "FOGRA52.txt", "SUPPLIED.json"], written
    assert not (rs.user_dir().parent.parent / "FOGRA51_escape.txt").exists()
    assert not (sandbox.parent / "FOGRA51_escape.txt").exists()
    # the record is still a record, not the CGATS file that tried for its name
    assert set(rs.user_record()) == {"FOGRA51", "FOGRA52"}
    assert json.loads((rs.user_dir() / rs.USER_RECORD_FILE)
                      .read_text(encoding="utf-8"))["sets"]
    # and the original names are kept, as a record, without being obeyed
    assert rs.user_record()["FOGRA52"]["original_filename"] == \
        "SUPPLIED.json.txt"


# ---------------------------------------------------------------------------
# The line: what ChromIQ vouches for, and what it merely holds
# ---------------------------------------------------------------------------
def test_a_supplied_file_never_claims_chromiqs_own_provenance(sandbox):
    """The credit is the same, because Fogra's grant is a condition on the
    DATA and a Fogra file the user downloaded is the same data. What changes is
    what ChromIQ says about where the file came from.

    MUTATION, run: delete the `supplied_by_user` branch of `credit_line` and
    this goes red on both the date and the "does not vouch" sentence.
    """
    rs.install_user_file(_drop(sandbox, "mine.txt", _cmyk_file()))
    s = rs.by_id("FOGRA51")
    line = s.credit_line

    assert "Fogra Forschungsinstitut" in line, "the grant's credit is gone"
    assert "not a certification" in line
    assert "You supplied this file" in line
    assert s.imported in line, "it does not say WHEN"
    assert "mine.txt" in line, "it does not say what the file was called"
    assert "does not vouch" in line
    assert "—" not in line, "em dash"


def test_the_licence_page_lists_only_what_ships(sandbox):
    """`ui/licences.py` states what ChromIQ SHIPS and on whose terms. A file
    somebody dropped into their own folder is not that, and listing it there
    would put it under a heading that says ChromIQ checked it.

    MUTATION, run: point `reference_data_credits` back at `available()` and
    this goes red.
    """
    from ui import licences

    before = licences.reference_data_credits()
    rs.install_user_file(_drop(sandbox, "mine.txt", _rgb_file()))
    assert rs.by_id("FOGRA61") is not None, "the fixture did not take"

    after = licences.reference_data_credits()
    assert after == before, "a supplied file reached the licence page"
    assert len(after) == 11
    assert not any("You supplied" in c for c in after)
    assert not any("FOGRA61" in c for c in after)


def test_the_two_records_are_two_files_and_the_shipped_one_is_untouched(
        sandbox):
    """`SOURCE.json` is ChromIQ's provenance record and is checked byte for
    byte on every run. The user's is a separate file in a separate folder, and
    installing anything must not write one character into the first.
    """
    shipped = rs._data_dir() / rs.SOURCE_FILE
    before = shipped.read_bytes()

    rs.install_user_file(_drop(sandbox, "mine.txt", _cmyk_file()))

    assert shipped.read_bytes() == before, "the shipped record was edited"
    mine = rs.user_dir() / rs.USER_RECORD_FILE
    assert mine.is_file() and mine != shipped
    doc = json.loads(mine.read_text(encoding="utf-8"))
    assert doc["sets"]["FOGRA51"]["supplied_by_user"] is True
    assert doc["sets"]["FOGRA51"]["sha256"] == \
        hashlib.sha256(_cmyk_file()).hexdigest()


def test_a_supplied_file_that_changed_since_import_says_so(sandbox):
    """The same treatment a tampered bundled file gets: the set keeps its
    place and loses the claim, because by then the file is on a user's disk
    and a set that vanishes with no explanation helps nobody.
    """
    rs.install_user_file(_drop(sandbox, "mine.txt", _cmyk_file()))
    assert rs.by_id("FOGRA51").verified

    (rs.user_dir() / "FOGRA51.txt").write_bytes(_cmyk_file() + b"# edited\r\n")
    rs.reset_cache()

    s = rs.by_id("FOGRA51")
    assert s is not None, "it disappeared instead of explaining itself"
    assert s.supplied_by_user and not s.verified
    assert "changed since you supplied it" in s.credit_line


# ---------------------------------------------------------------------------
# What an RGB reference does to two rules written when every set was CMYK
# ---------------------------------------------------------------------------
def test_an_rgb_reference_takes_its_paper_from_the_maximum_not_from_zero(
        sandbox):
    """Every bundled set is CMYK, where no ink is every channel at zero. In an
    additive space zero is BLACK, and Fogra publishes at least two RGB exchange
    sets that can now arrive this way.

    Measured on the real FOGRA61 beta file, 2026-09-20: the zero patch is
    L* 11.0 and the maximum patch is L* 91.0. A substrate figure computed from
    the first is nonsense with no symptom but a large number.

    MUTATION, run: delete the RGB branch of `paper_lab` and this goes red with
    11.0 where 91.0 belongs.
    """
    rs.install_user_file(_drop(sandbox, "mine.txt", _rgb_file()))
    s = rs.by_id("FOGRA61")
    assert rs.paper_lab(s) == pytest.approx((91.0, -1.0, 4.0))

    cmyk = rs.by_id("FOGRA52")
    assert rs.paper_lab(cmyk)[0] > 90, "the subtractive rule moved"


def test_a_supplied_set_is_not_called_an_exchange_space_on_no_evidence(
        sandbox):
    """"This is a colour exchange space" is a statement about the reference,
    and ChromIQ can make it only about a set whose own entry in `SOURCE.json`
    records it. For a file the user supplied there is no such entry, and
    saying it about a real paper would be a false sentence in the place a
    reader goes to find out why a row is empty.

    So there is a third answer, and it says who does not know.

    MUTATION, run: make `is_real_paper` default to False for a supplied set
    and this goes red, because the refusal then names an exchange space.
    """
    rs.install_user_file(_drop(sandbox, "mine.txt", _rgb_file()))
    s = rs.by_id("FOGRA61")
    assert s.is_real_paper is None

    ok, why = rs.can_fill("substrate_de00_max", s, "RGB")
    assert ok is False
    assert why == rs.REFUSE_SUBSTRATE_UNKNOWN
    text = rs.refusal_text(why)
    assert "You supplied this reference" in text
    assert "exchange space" in text and "guess" in text
    assert "—" not in text

    # a set ChromIQ DOES know still answers the old way, both ways round
    assert rs.can_fill("substrate_de00_max", rs.by_id("FOGRA52"), "RGB") == \
        (True, None)


def test_the_window_says_which_copy_is_in_force_per_set(sandbox):
    """A control can offer an action; only a sentence can say what is true now.

    MUTATION, run: drop the archive version and date from the ChromIQ's-copy
    line and this goes red.
    """
    lines = rs.in_force_lines()
    assert len(lines) == 11
    assert "FOGRA51: ChromIQ's copy, archive V1.0 of 2022-01-27" in lines

    rs.install_user_file(_drop(sandbox, "mine.txt", _cmyk_file()))
    lines = rs.in_force_lines()
    mine = [ln for ln in lines if ln.startswith("FOGRA51:")]
    assert mine == [f"FOGRA51: your copy, added "
                    f"{rs.by_id('FOGRA51').imported}"], mine
    assert "FOGRA52: ChromIQ's copy, archive V1.0 of 2022-01-27" in lines, \
        "one set's file changed what another says"
    for ln in lines:
        assert "—" not in ln, ln
