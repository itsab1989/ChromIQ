"""A profile built for "Müller-Prüfdruck" must not be called "M?ller-Pr?fdruck".

ArgyllCMS drops the accent twice over: its ASCII converter substitutes ``'?'``
for every non-ASCII character (``icc/icc_util.c::icmUTF8toASCIIZSn``,
``replacement_char = '?'``) and ``colprof`` never fills the Unicode field the
same tag provides (``profile/profout.c:1293`` sets only ``wo->desc``). Measured
against real Argyll 3.5.0 on 2026-09-02: the bytes in the file literally read
``M?ller-Pr?fdruck``, and macOS ColorSync shows that too — Windows is not
mangling anything, it is displaying the only string the file contains.

ICC.1:2001-04 §6.5.17 is explicit that this is a producer choice, not a format
limit: "The 7-bit ASCII description is to be an invariant, nonlocalizable name
for consistent reference. It is preferred that both the Unicode and ScriptCode
structures be properly localized."

So ChromIQ writes both — a transliterated ASCII field (``Mueller-Pruefdruck``,
what an ASCII-only reader such as littleCMS shows) and a real UTF-16 Unicode
field (``Müller-Prüfdruck``, what macOS ColorSync prefers).
"""
from __future__ import annotations

import logging
import struct
from pathlib import Path

import pytest

from core.icc_text import (ascii_fallback, parse_text_description,
                           repair_descriptions, text_description)


# The exact bytes ChromIQ's engine wrote before this feature, and the exact
# bytes Argyll writes: ASCII field only, zero Unicode, zero ScriptCode.
def _argyll_style_desc(text: str) -> bytes:
    t = text.encode("ascii", "replace") + b"\0"
    return (b"desc" + b"\0" * 4 + struct.pack(">I", len(t)) + t
            + b"\0" * 4 + b"\0" * 4 + struct.pack(">H", 0) + b"\0" + b"\0" * 67)


# --------------------------------------------------------------------------
# ascii_fallback
# --------------------------------------------------------------------------

@pytest.mark.parametrize("src,want", [
    ("Müller-Prüfdruck", "Mueller-Pruefdruck"),   # the reported name
    ("Straße", "Strasse"),
    ("Öko-Änderung", "Oeko-Aenderung"),
    ("Café-Noël", "Cafe-Noel"),                   # generic diacritic strip
    ("Smørrebrød", "Smorrebrod"),                 # no canonical decomposition
    ("plain-ASCII_1", "plain-ASCII_1"),
])
def test_ascii_fallback_spells_the_name_out(src, want):
    assert ascii_fallback(src) == want


def test_ascii_fallback_leaves_ascii_untouched_identically():
    for s in ("", "Canon-Pro300", "a b/c.d", "~!@#$%^&*()"):
        assert ascii_fallback(s) == s


def test_ascii_fallback_still_falls_back_to_question_marks():
    # Nothing sensible exists for CJK in 7 bits — the ASCII field keeps
    # Argyll's behaviour there, because there is nothing better to put.
    assert ascii_fallback("日本語") == "???"


# --------------------------------------------------------------------------
# text_description — the tag bytes
# --------------------------------------------------------------------------

def test_ascii_name_produces_exactly_the_bytes_it_always_did():
    """Nothing that already works may change."""
    for name in ("Canon-Pro300-CanonSG-i1Pro", "run1", "x"):
        assert text_description(name) == _argyll_style_desc(name)


def test_accented_name_fills_both_fields():
    blob = text_description("Müller-Prüfdruck")
    assert parse_text_description(blob) == ("Mueller-Pruefdruck",
                                            "Müller-Prüfdruck")
    # ...and it is NOT what Argyll writes, which is the whole point.
    assert blob != _argyll_style_desc("Müller-Prüfdruck")


def test_unicode_count_counts_code_units_including_the_nul():
    """ICC.1:2001-04 §6.5.17: "the count is the number of characters
    including a Unicode null where a character is always two bytes"."""
    name = "Müller-Prüfdruck"                       # 16 characters
    blob = text_description(name)
    n = struct.unpack(">I", blob[8:12])[0]          # ASCII count
    lang, count = struct.unpack(">II", blob[12 + n:20 + n])
    assert lang == 0
    assert count == len(name) + 1 == 17
    payload = blob[20 + n:20 + n + count * 2]
    assert len(payload) == 34
    assert payload.decode("utf-16-be") == name + "\0"
    assert not payload.startswith(b"\xfe\xff"), "no BOM — Argyll flags it"


def test_scriptcode_block_is_the_specs_fixed_67_zero_bytes():
    for name in ("plain", "Müller-Prüfdruck"):
        blob = text_description(name)
        assert blob[-70:] == b"\0" * 70          # scCode(2) + count(1) + 67


def test_tag_length_matches_the_fields_it_declares():
    for name in ("plain", "Müller-Prüfdruck", "日本語"):
        blob = text_description(name)
        n = struct.unpack(">I", blob[8:12])[0]
        count = struct.unpack(">I", blob[16 + n:20 + n])[0]
        assert len(blob) == 12 + n + 8 + count * 2 + 3 + 67


# --------------------------------------------------------------------------
# repair_descriptions — rewriting what colprof already wrote
# --------------------------------------------------------------------------

def _fake_profile(tags: list[tuple[bytes, bytes]]) -> bytes:
    """A minimally valid ICC: header + tag table + 4-byte-aligned data."""
    off = 128 + 4 + 12 * len(tags)
    table, body = b"", b""
    for sig, data in tags:
        table += struct.pack(">4sII", sig, off + len(body), len(data))
        body += data + b"\0" * (-len(data) % 4)
        off = off
    header = bytearray(128)
    header[4:8] = b"ChIQ"
    header[8:12] = bytes.fromhex("02200000")
    header[12:16] = b"prtr"
    header[36:40] = b"acsp"
    blob = bytes(header) + struct.pack(">I", len(tags)) + table + body
    return struct.pack(">I", len(blob)) + blob[4:]


def test_ascii_only_names_leave_the_file_completely_alone():
    src = _fake_profile([(b"desc", _argyll_style_desc("Plain-Name")),
                         (b"wtpt", b"XYZ " + b"\0" * 16)])
    assert repair_descriptions(src, {b"desc": "Plain-Name"}) is src


def test_the_accented_name_comes_back_and_nothing_else_moves():
    other = b"XYZ " + b"\0" * 16
    src = _fake_profile([(b"desc", _argyll_style_desc("Müller-Prüfdruck")),
                         (b"wtpt", other),
                         (b"dmdd", _argyll_style_desc("Müller-Prüfdruck"))])
    out = repair_descriptions(src, {b"desc": "Müller-Prüfdruck",
                                    b"dmdd": "Müller-Prüfdruck",
                                    b"dmnd": "ChromIQ"})
    assert out != src
    assert struct.unpack(">I", out[:4])[0] == len(out)      # header size fixed
    assert out[:128] == src[:128] or out[4:128] == src[4:128]

    entries = {}
    for i in range(struct.unpack(">I", out[128:132])[0]):
        sig, off, size = struct.unpack(">4sII", out[132 + 12 * i:144 + 12 * i])
        entries[sig] = out[off:off + size]
    assert entries[b"wtpt"] == other                        # untouched tag
    for sig in (b"desc", b"dmdd"):
        assert parse_text_description(entries[sig]) == ("Mueller-Pruefdruck",
                                                        "Müller-Prüfdruck")
    # The new tag data is APPENDED, so every original data byte is still
    # exactly where it was: only the two tag-table entries and the header's
    # size field differ, and the whole data region is byte-identical.
    table_end = 132 + 12 * 3
    assert out[table_end:len(src)] == src[table_end:]
    assert len(out) > len(src)


def test_a_tag_that_is_not_the_one_we_asked_for_is_left_alone():
    """The guard: repair only fires when the stored ASCII is exactly Argyll's
    '?' spelling of the name we requested."""
    src = _fake_profile([(b"desc", _argyll_style_desc("Something-Else"))])
    assert repair_descriptions(src, {b"desc": "Müller-Prüfdruck"}) is src


def test_a_desc_that_already_has_a_unicode_name_is_left_alone():
    """A tag that already carries the accents is not rewritten.

    THE FIXTURE HAS TO REACH THAT GUARD. The first version used
    `text_description`, whose ASCII field is the transliteration
    "Mueller-Pruefdruck" - rejected one line earlier by the "is this
    Argyll's ? spelling" comparison, so the guard under test never ran and
    the test passed with it deleted. This tag has Argyll's exact ASCII
    spelling AND a Unicode name, which is the only shape that gets that far.
    """
    tag = _argyll_style_desc("Müller-Prüfdruck")          # ASCII "M?ller-Pr?fdruck"
    n = struct.unpack(">I", tag[8:12])[0]
    uni = "Müller-Prüfdruck\0".encode("utf-16-be")
    tag = (tag[:12 + n]
           + struct.pack(">II", 0, len(uni) // 2) + uni
           + struct.pack(">HB", 0, 0) + b"\0" * 67)
    assert parse_text_description(tag) == ("M?ller-Pr?fdruck", "Müller-Prüfdruck")
    src = _fake_profile([(b"desc", tag)])
    assert repair_descriptions(src, {b"desc": "Müller-Prüfdruck"}) is src


def test_repair_is_idempotent():
    src = _fake_profile([(b"desc", _argyll_style_desc("Müller-Prüfdruck"))])
    once = repair_descriptions(src, {b"desc": "Müller-Prüfdruck"})
    assert repair_descriptions(once, {b"desc": "Müller-Prüfdruck"}) == once


def test_a_non_icc_file_is_returned_unchanged():
    """Including one that only the 'acsp' check can reject.

    The three original cases were all stopped earlier - by the length check
    or by a tag count of zero - so the signature check never decided
    anything and the test passed with it deleted. The last case here is a
    plausible-looking file with a real tag table and the wrong signature.
    """
    not_icc = bytearray(_fake_profile([(b"desc", _argyll_style_desc("Müller"))]))
    not_icc[36:40] = b"junk"
    for junk in (b"", b"not an icc file at all", b"\0" * 300, bytes(not_icc)):
        assert repair_descriptions(junk, {b"desc": "Müller"}) is junk


def test_a_profile_id_is_recomputed_when_the_file_carries_one():
    import hashlib
    src = bytearray(_fake_profile([(b"desc", _argyll_style_desc("Müller"))]))
    src[84:100] = b"\x11" * 16
    # THE FIXTURE MUST HAVE SOMETHING IN THE ZEROED FIELDS. `_fake_profile`
    # starts from `bytearray(128)`, so flags and rendering intent were
    # already zero and blanking them changed nothing: the test passed with
    # two of the three ranges deleted. A real Argyll profile carries a
    # non-zero intent, so this one does too.
    src[44:48] = b"\x00\x00\x00\x02"          # flags
    src[64:68] = b"\x00\x00\x00\x01"          # rendering intent
    out = repair_descriptions(bytes(src), {b"desc": "Müller"})
    assert out[84:100] not in (b"\x11" * 16, b"\0" * 16)
    check = bytearray(out)
    for lo, hi in ((44, 48), (64, 68), (84, 100)):
        check[lo:hi] = b"\0" * (hi - lo)
    assert out[84:100] == hashlib.md5(bytes(check)).digest()


# --------------------------------------------------------------------------
# The engine (a) and the shared colprof path (b)
# --------------------------------------------------------------------------

def test_engine_make_desc_is_the_shared_builder():
    from workflow.profile_engine import icc_writer as icw
    assert icw.make_desc("Canon-Pro300") == _argyll_style_desc("Canon-Pro300")
    assert parse_text_description(icw.make_desc("Müller-Prüfdruck")) == (
        "Mueller-Pruefdruck", "Müller-Prüfdruck")


def test_engine_v4_uses_mluc_which_was_never_ascii_limited():
    from workflow.profile_engine import icc_writer as icw
    blob = icw.make_mluc("Müller-Prüfdruck")
    assert blob[:4] == b"mluc"
    assert blob[28:].decode("utf-16-be") == "Müller-Prüfdruck"


def test_engine_v2_cprt_transliterates_because_texttype_has_no_unicode():
    """ICC.1:2001-04 §6.4.13: cprt is textType, "7-bit ASCII text"."""
    from workflow.profile_engine import icc_writer as icw
    assert icw.make_text("Copyright Müller") == (
        b"text" + b"\0" * 4 + b"Copyright Mueller\0")
    assert icw.make_text("Copyright ChromIQ") == (
        b"text" + b"\0" * 4 + b"Copyright ChromIQ\0")


def _params(tmp_path: Path, description: str):
    from workflow.profile_builder import ProfileParams
    ti3 = tmp_path / "Target.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    return ProfileParams(ti3_path=ti3, description=description)


def test_a_plain_ascii_build_never_even_opens_the_profile(tmp_path, monkeypatch,
                                                        caplog):
    """The strongest form of "nothing that works may change": for an ASCII
    name the finished file is not read, not written and not touched."""
    from workflow.profile_builder import ProfileBuilder

    # NOT AN AssertionError. `_restore_accents` ends in `except Exception`,
    # and AssertionError IS an Exception - so the old trap was caught,
    # logged, and this test passed with the ASCII early-out deleted. Proven
    # by a challenge agent. BaseException walks straight out.
    class _Opened(BaseException):
        pass

    def _boom(self, *a, **k):                    # pragma: no cover - must not run
        raise _Opened("the profile was opened for an ASCII name")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    ProfileBuilder(runner=None)._restore_accents(_params(tmp_path, "Plain-Name"))
    # ...and belt and braces: nothing was even attempted, so nothing complained.
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_the_shared_path_repairs_a_real_colprof_style_profile(tmp_path):
    from workflow.profile_builder import ProfileBuilder
    params = _params(tmp_path, "Müller-Prüfdruck")
    icc = tmp_path / "Target.icc"
    icc.write_bytes(_fake_profile([
        (b"desc", _argyll_style_desc("Müller-Prüfdruck")),
        (b"dmdd", _argyll_style_desc("Müller-Prüfdruck")),
        (b"dmnd", _argyll_style_desc("ChromIQ"))]))

    ProfileBuilder(runner=None)._restore_accents(params)

    data = icc.read_bytes()
    found = {}
    for i in range(struct.unpack(">I", data[128:132])[0]):
        sig, off, size = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        found[sig] = parse_text_description(data[off:off + size])
    assert found[b"desc"] == ("Mueller-Pruefdruck", "Müller-Prüfdruck")
    assert found[b"dmdd"] == ("Mueller-Pruefdruck", "Müller-Prüfdruck")
    assert found[b"dmnd"] == ("ChromIQ", "")


def test_a_repair_failure_never_fails_the_build(tmp_path, caplog):
    """A '?' in a name is a blemish; a build that reports failure is not."""
    from workflow.profile_builder import ProfileBuilder
    params = _params(tmp_path, "Müller-Prüfdruck")     # no .icc on disk at all
    ProfileBuilder(runner=None)._restore_accents(params)   # must not raise


def test_the_repair_runs_only_after_a_successful_colprof(tmp_path):
    from workflow.profile_builder import ProfileBuilder

    class _Runner:
        def run(self, tool, args, cwd, on_line, on_finish):
            self.on_finish = on_finish

    calls: list = []
    builder = ProfileBuilder(runner=_Runner())
    builder._restore_accents = lambda p: calls.append(p)     # type: ignore
    params = _params(tmp_path, "Müller-Prüfdruck")

    builder.build(params, on_line=lambda _l: None, on_finish=lambda _c: None)
    builder._runner.on_finish(1)
    assert calls == [], "a failed build must not be post-processed"
    builder._runner.on_finish(0)
    assert calls == [params]


def _builder_over(icc_path, name="Müller-Prüfdruck"):
    """A real ProfileBuilder pointed at one file, and the params for it."""
    from workflow import profile_builder

    class _Params:
        description = name
        model = None
        manufacturer = None
        ti3_path = icc_path.with_suffix(".ti3")

    b = profile_builder.ProfileBuilder.__new__(profile_builder.ProfileBuilder)
    b.expected_icc_path = lambda params: icc_path
    return b, _Params()


@pytest.mark.parametrize("dies_at", ["writing", "fsync", "copystat"])
def test_a_failed_name_fix_never_costs_the_profile(tmp_path, dies_at):
    """The rewrite is atomic, because the thing being rewritten is the
    deliverable.

    The old code called `write_bytes` on the profile itself, which truncates
    and then fills: a crash, a power cut or a full disk between those two
    moments left a truncated ICC — somebody's finished profile destroyed by a
    change that only fixes how its name is spelled.

    Failure is injected at each of the three moments that can now fail. In
    every one the profile must be exactly as Argyll left it and no sibling
    may be left behind. An earlier version of this test raised before
    anything was written, so it passed just as happily with the non-atomic
    version put back — it could not fail.
    """
    import os
    import shutil
    from unittest import mock

    from workflow import profile_builder

    icc = tmp_path / "Müller-Prüfdruck.icc"
    original = b"ORIGINAL-PROFILE-BYTES" * 40
    icc.write_bytes(original)
    b, params = _builder_over(icc)

    boom = OSError("disk full")
    if dies_at == "writing":
        real_open = open

        def _die(path, *a, **k):
            fh = real_open(path, *a, **k)
            if str(path).endswith(".name-fix"):
                fh.write(b"HALF")          # some of it lands, then the disk dies
                raise boom
            return fh
        patch = mock.patch("builtins.open", _die)
    elif dies_at == "fsync":
        patch = mock.patch.object(os, "fsync", side_effect=boom)
    else:
        patch = mock.patch.object(shutil, "copystat", side_effect=boom)

    with mock.patch.object(profile_builder.icc_text, "repair_descriptions",
                           return_value=b"NEW"), patch:
        b._restore_accents(params)         # must not raise

    assert icc.read_bytes() == original, "the profile was damaged by a failed fix"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Müller-Prüfdruck.icc"], \
        "a temp file was left beside the profile"


def test_the_fix_goes_through_a_symlink_instead_of_replacing_it(tmp_path):
    """A profile the user linked somewhere keeps being that link.

    `os.replace` swaps the NAME it is given. Pointed at a symlink it deletes
    the link and drops a regular file in its place: the real profile keeps
    `M?ller`, everything else that reads it silently sees the old spelling,
    and the link the user made into ~/Library/ColorSync/Profiles or a shared
    job folder is gone with no message. This was a regression the atomic
    write introduced, found by a challenge agent - the previous, unsafe
    version wrote through the link correctly.
    """
    real = tmp_path / "real" / "Müller-Prüfdruck.icc"
    real.parent.mkdir()
    real.write_bytes(b"ORIGINAL" * 20)
    link = tmp_path / "linked.icc"
    link.symlink_to(real)

    b, params = _builder_over(link)
    from workflow import profile_builder
    from unittest import mock
    with mock.patch.object(profile_builder.icc_text, "repair_descriptions",
                           return_value=b"REPAIRED"):
        b._restore_accents(params)

    assert link.is_symlink(), "the symlink was replaced by a regular file"
    assert real.read_bytes() == b"REPAIRED", "the real profile was not repaired"


def test_the_profile_keeps_its_permissions_and_finder_metadata(tmp_path):
    """Mode, times and extended attributes belong to the user's file.

    A profile they made read-only must not come back writable, and a Finder
    comment or tag must survive a change to how the name is spelled.
    `install_profile` uses `shutil.copy2`, which preserves all of it, so
    without this the app was inconsistent with itself.
    """
    import os
    from unittest import mock

    from workflow import profile_builder

    icc = tmp_path / "Müller-Prüfdruck.icc"
    icc.write_bytes(b"ORIGINAL" * 20)
    os.chmod(icc, 0o444)
    try:
        os.setxattr(icc, "user.chromiq.test", b"keep me")
        had_xattr = True
    except (AttributeError, OSError):
        had_xattr = False                  # not every filesystem carries them

    b, params = _builder_over(icc)
    with mock.patch.object(profile_builder.icc_text, "repair_descriptions",
                           return_value=b"REPAIRED"):
        b._restore_accents(params)

    assert icc.read_bytes() == b"REPAIRED"
    assert oct(icc.stat().st_mode)[-3:] == "444", "a read-only profile came back writable"
    if had_xattr:
        assert os.getxattr(icc, "user.chromiq.test") == b"keep me"


def test_a_truncated_tag_table_is_refused_rather_than_crashing():
    """The bounds check on the tag table is load-bearing and had no test.

    A challenge agent removed it and got an UNCAUGHT `struct.error` - the
    unpack that reads each entry sits outside the try - while the whole file
    still passed. In the app that lands in `_restore_accents`'s catch-all and
    costs only the name, but `repair_descriptions` is a library function and
    must not raise at its own callers.
    """
    src = _fake_profile([(b"desc", _argyll_style_desc("Müller"))])
    # Claim twenty tags, then cut the file off inside the table.
    lying = bytearray(src)
    lying[128:132] = struct.pack(">I", 20)
    truncated = bytes(lying[:132 + 12 * 3])
    assert repair_descriptions(truncated, {b"desc": "Müller"}) is truncated


def test_a_tag_pointing_past_the_end_of_the_file_is_refused():
    """The other bounds check, also untested until a challenge agent asked."""
    src = bytearray(_fake_profile([(b"desc", _argyll_style_desc("Müller"))]))
    sig, off, size = struct.unpack(">4sII", src[132:144])
    src[132:144] = struct.pack(">4sII", sig, off, size + len(src))
    blob = bytes(src)
    assert repair_descriptions(blob, {b"desc": "Müller"}) is blob


# --------------------------------------------------------------------------
# The name has to be right in ChromIQ's OWN windows too (challenge finding F2)
# --------------------------------------------------------------------------

def test_chromiqs_own_profile_reader_shows_the_accents():
    """Our own Profile Info window read the ASCII field, so it showed the
    name the user never typed.

    A challenge agent measured it: with the build path fixed, macOS showed
    `Müller-Prüfdruck` and ChromIQ showed `Mueller-Pruefdruck`; a Russian or
    Japanese name still read as nothing but question marks in the one place
    we control. The Unicode field is exactly what the tag has one for.
    """
    from workflow.icc_info import _read_desc
    for name in ("Müller-Prüfdruck", "Профиль", "日本語プロファイル", "Profil 😀"):
        src = _fake_profile([(b"desc", text_description(name))])
        assert _read_desc(src, len(src)) == name, f"{name!r} came back wrong"


def test_a_profile_with_no_unicode_name_still_reads_its_ascii_one():
    """A profile from another application, or one of ours from before the
    repair existed, has an empty Unicode field and must still show its name."""
    from workflow.icc_info import _read_desc
    src = _fake_profile([(b"desc", _argyll_style_desc("Canon-Pro300"))])
    assert _read_desc(src, len(src)) == "Canon-Pro300"


def test_the_convert_tool_no_longer_re_loses_the_accents():
    """The fourth writer of this tag (challenge finding F6)."""
    from workflow.icc_convert import _text_desc_tag, _text_tag
    assert parse_text_description(_text_desc_tag("Müller-Prüfdruck")) == (
        "Mueller-Pruefdruck", "Müller-Prüfdruck")
    # A v2 `text` tag is ASCII by definition and has no Unicode field, so the
    # best it can do is say what the line means.
    assert _text_tag("© 2026 Müller")[8:].rstrip(b"\0") == b"(c) 2026 Mueller"


def test_the_copyright_reaches_colprof_transliterated(tmp_path):
    """`? 2026 M?ller Druckerei` was what colprof wrote (challenge finding F5).

    The engine path already transliterated; the two build paths disagreed.
    """
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    b = ProfileBuilder(runner=None)
    ti3 = tmp_path / "x.ti3"
    ti3.write_text("dummy", encoding="utf-8")
    p = ProfileParams(ti3_path=ti3, description="Test",
                      copyright="© 2026 Müller Druckerei")
    args = b._build_args(p)
    assert "(c) 2026 Mueller Druckerei" in args
    assert "©" not in " ".join(args)
    assert "?" not in " ".join(args)
