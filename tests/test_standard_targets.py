"""Bundled corrected scanner targets (Knut #2): the dropdown prefers ChromIQ's
bundled ``.cht`` over the user's Argyll ``ref/`` copies (which had wrong
fiducials for several targets)."""
from __future__ import annotations

from pathlib import Path

from workflow.standard_targets import (
    bundled_targets_dir, display_name, list_standard_targets)


class _S:
    def __init__(self, **o): self._s = o
    def get(self, k, d=None): return self._s.get(k, d)


# Only the .cht that pass real scanin registration are bundled (Knut #2).
_BUNDLED = {"Hutchcolor", "ISO12641_2_1", "LaserSoftDCPro", "it8Wolf",
            "QPcard_202", "SpyderChecker", "SpyderChecker24", "CMP_Digital_Target-4"}


def test_bundle_present_and_validated_set():
    d = bundled_targets_dir()
    assert d is not None and d.is_dir()
    assert {p.stem for p in d.glob("*.cht")} == _BUNDLED
    # Licence + attribution ship alongside the GPLv3 files.
    assert (d / "LICENSE").is_file() and (d / "README.md").is_file()


def test_bundle_listed_even_without_argyll_ref(tmp_path):
    # No Argyll ref/ available → the dropdown still lists the bundled targets.
    targets = list_standard_targets(_S(argyll_bin_path=str(tmp_path / "bin")))
    stems = {p.stem for _, p in targets}
    assert _BUNDLED <= stems


def test_bundled_cht_preferred_over_argyll_ref(tmp_path):
    # A fake Argyll ref/ with a same-named .cht must be overridden by the bundle.
    ref = tmp_path / "ref"; ref.mkdir()
    (ref / "Hutchcolor.cht").write_text("stale argyll copy", encoding="utf-8")
    (tmp_path / "bin").mkdir()
    targets = dict((p.stem, p) for _, p in
                   list_standard_targets(_S(argyll_bin_path=str(tmp_path / "bin"),
                                            custom_output_path=str(tmp_path))))
    hutch = targets["Hutchcolor"]
    assert hutch == bundled_targets_dir() / "Hutchcolor.cht"   # bundle wins
    assert "stale argyll copy" not in hutch.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The user scanner-test-targets folder (#127 / Knut's beta.5 report): copies
# of the bundled .cht are provisioned into the output root, missing files come
# back, edits survive, and a user's copy overrides the bundled one.
# ---------------------------------------------------------------------------

def test_ensure_user_targets_dir_provisions_and_never_overwrites(tmp_path):
    from workflow.standard_targets import ensure_user_targets_dir
    s = _S(custom_output_path=str(tmp_path))
    d = ensure_user_targets_dir(s)
    assert d == tmp_path / "scanner-test-targets"
    for stem in _BUNDLED:
        assert (d / f"{stem}.cht").is_file()
    assert (d / "About this folder.txt").is_file()
    assert (d / "README.md").is_file()

    # A user edit survives re-provisioning; a deleted file comes back.
    (d / "it8Wolf.cht").write_text("MY TWEAKED VERSION", encoding="utf-8")
    (d / "Hutchcolor.cht").unlink()
    ensure_user_targets_dir(s)
    assert (d / "it8Wolf.cht").read_text(encoding="utf-8") == "MY TWEAKED VERSION"
    assert (d / "Hutchcolor.cht").is_file()


def test_user_copy_overrides_bundled(tmp_path):
    from workflow.standard_targets import ensure_user_targets_dir
    s = _S(argyll_bin_path=str(tmp_path / "bin"),
           custom_output_path=str(tmp_path))
    d = ensure_user_targets_dir(s)
    (d / "it8Wolf.cht").write_text("USER OVERRIDE", encoding="utf-8")
    targets = dict((p.stem, p) for _, p in list_standard_targets(s))
    assert targets["it8Wolf"] == d / "it8Wolf.cht"
    assert targets["it8Wolf"].read_text(encoding="utf-8") == "USER OVERRIDE"
    # A stray .cht that matches no known target must NOT invent a new entry.
    (d / "my-own-notes.cht").write_text("not a target", encoding="utf-8")
    targets = dict((p.stem, p) for _, p in list_standard_targets(s))
    assert "my-own-notes" not in targets


def test_bundled_cht_parses_and_registers():
    """The bundled corrected .cht parse cleanly with ChromIQ's own parser."""
    from workflow.cht_parser import parse_cht
    d = bundled_targets_dir()
    for cht in d.glob("*.cht"):
        g = parse_cht(cht.read_text(errors="ignore", encoding="utf-8"))
        assert g.patches and len(g.fiducials) == 4, f"{cht.name} parse looks wrong"


# --- multi-page sets + patch counts (Knut) ---------------------------------

def test_iso12641_2_3_folds_into_one_multipage_target():
    """The three ISO 12641-2 pages are one physical target, so they collapse to a
    single multi-page entry (each page's .cht kept, in order) — never three
    separate rows — and every entry carries its per-page patch count."""
    import pytest
    from tests.argyll_env import argyll_bin_dir
    from workflow.standard_targets import grouped_standard_targets
    bd = argyll_bin_dir()
    if bd is None:
        pytest.skip("Argyll not installed")
    targets = grouped_standard_targets(_S(argyll_bin_path=str(bd)))
    keys = [t.key for t in targets]
    if "ISO12641_2_3" not in keys:
        pytest.skip("ISO 12641-2 3-page set not in this Argyll ref/")
    assert "ISO12641_2_3_1" not in keys and "ISO12641_2_3_3" not in keys
    iso = next(t for t in targets if t.key == "ISO12641_2_3")
    assert iso.is_multipage and iso.n_pages == 3 and len(iso.cht_paths) == 3
    assert [p.stem for p in iso.cht_paths] == [
        "ISO12641_2_3_1", "ISO12641_2_3_2", "ISO12641_2_3_3"]
    assert all(c > 0 for c in iso.patch_counts)
    # An ordinary single-sheet target stays single, with its own patch count.
    single = next(t for t in targets if t.key == "it8Wolf")
    assert not single.is_multipage and single.patch_counts[0] > 0


def test_merge_demo_references_concatenates(tmp_path):
    """Merging per-page demo references keeps every page's rows (disjoint names)
    under one summed NUMBER_OF_SETS — the shared reference a set is read against."""
    import re
    from workflow.standard_targets import merge_demo_references

    def _cie(names):
        rows = "\n".join(f"{n} 10 10 10" for n in names)
        return ("CGATS.17\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
                "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n"
                f"NUMBER_OF_SETS {len(names)}\nBEGIN_DATA\n{rows}\nEND_DATA\n")

    a = tmp_path / "a.cie"; a.write_text(_cie(["A1", "A2"]), encoding="utf-8")
    b = tmp_path / "b.cie"; b.write_text(_cie(["B1", "B2", "B3"]), encoding="utf-8")
    out = merge_demo_references([a, b], tmp_path / "m.cie")
    txt = out.read_text(encoding="utf-8")
    assert int(re.search(r"NUMBER_OF_SETS (\d+)", txt).group(1)) == 5
    for name in ("A1", "A2", "B1", "B2", "B3"):
        assert re.search(rf"(?m)^{name} ", txt)
    # exactly one data block (BEGIN_DATA_FORMAT must not be miscounted)
    assert [l.strip() for l in txt.splitlines()].count("BEGIN_DATA") == 1


def test_unmodified_copy_refreshes_on_bundle_update(tmp_path, monkeypatch):
    """An untouched provisioned copy follows a bundle update; an edited one
    never does (the manifest records what ChromIQ copied)."""
    import workflow.standard_targets as st
    bundle = tmp_path / "bundle"; bundle.mkdir()
    (bundle / "it8Wolf.cht").write_text("v1 content", encoding="utf-8")
    (bundle / "Hutchcolor.cht").write_text("v1 content", encoding="utf-8")
    monkeypatch.setattr(st, "bundled_targets_dir", lambda: bundle)
    s = _S(custom_output_path=str(tmp_path))

    d = st.ensure_user_targets_dir(s)
    assert (d / "it8Wolf.cht").read_text(encoding="utf-8") == "v1 content"

    (d / "Hutchcolor.cht").write_text("USER EDIT", encoding="utf-8")     # user tweaks one file
    (bundle / "it8Wolf.cht").write_text("v2 corrected", encoding="utf-8")  # update ships fixes
    (bundle / "Hutchcolor.cht").write_text("v2 corrected", encoding="utf-8")
    st.ensure_user_targets_dir(s)
    assert (d / "it8Wolf.cht").read_text(encoding="utf-8") == "v2 corrected"   # refreshed
    assert (d / "Hutchcolor.cht").read_text(encoding="utf-8") == "USER EDIT"   # preserved


def test_looking_at_the_targets_twice_does_not_rewrite_the_manifest(tmp_path):
    """Nothing the user owns has its modification time moved by an operation
    that changed nothing in it.

    The manifest was rewritten unconditionally, and because
    `custom_output_path` defaults to "" - which IS the owner's own ~/ChromIQ -
    every gate run that built a scanner window rewrote a file in his real
    projects folder. Two agents hunted it separately: one could not reproduce
    it, and the suite's own guard then caught it intermittently while naming
    whichever test tore down next rather than the writer.
    """
    import os

    from workflow.standard_targets import ensure_user_targets_dir

    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))

    d = ensure_user_targets_dir(settings)
    manifest = d / ".provisioned.json"
    assert manifest.exists(), "the first call should provision"
    before = manifest.read_bytes()
    stamp = os.stat(manifest).st_mtime_ns

    os.utime(manifest, ns=(stamp - 5_000_000_000, stamp - 5_000_000_000))
    older = os.stat(manifest).st_mtime_ns

    ensure_user_targets_dir(settings)            # nothing has changed

    assert manifest.read_bytes() == before, "the manifest's content moved"
    assert os.stat(manifest).st_mtime_ns == older, (
        "the manifest was rewritten even though nothing in it changed")


def test_a_real_change_is_still_written(tmp_path):
    """...and the guard above must not have turned the manifest read-only."""
    import json

    from workflow.standard_targets import ensure_user_targets_dir

    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))

    d = ensure_user_targets_dir(settings)
    manifest = d / ".provisioned.json"
    manifest.write_text(json.dumps({"stale": "value"}), encoding="utf-8")

    ensure_user_targets_dir(settings)

    assert json.loads(manifest.read_text(encoding="utf-8")) != {"stale": "value"}, (
        "a manifest that no longer describes the folder was left alone")


# --- the edge lists the AUTOMATIC recogniser matches on -------------------
#
# `scanin -F` (four corners by hand) never reads XLIST/YLIST, so the bundled
# files could be — and were — validated end to end through the real scanin at
# 100/200/300/600 dpi with column 2 wrong by a factor of hundreds. Auto align
# is the first caller that asks scanin to FIND the chart, and it got
# `r0 = nan, r90 = nan, r180 = nan, r270 = nan`, zero candidate rotations and
# "Pattern match wasn't good enough" on every bought target ChromIQ ships.
#
# ArgyllCMS `doc/cht_format.html` on that column: "the second number is used to
# improve the correlation by representing the strength of that 'tick' relative
# to the strongest tick which will have a value 1.0". ChromIQ's own generator
# already obeys this (`layout_engine/cht_writer.py::_edge_list`, "normalised to
# their maxima, the way printtarg's XLIST/YLIST are") — only the static files
# did not.

def _edge_blocks(text: str):
    """Every XLIST/YLIST block in *text* as a list of (pos, strength, cross)."""
    import re
    hdr = re.compile(r"^(XLIST|YLIST)\s+\d+$")
    blocks, cur = [], None
    for line in text.splitlines() + [""]:
        s = line.strip()
        if hdr.match(s):
            if cur:
                blocks.append(cur)
            cur = []
            continue
        if cur is None:
            continue
        p = s.split()
        if len(p) == 3:
            try:
                cur.append(tuple(float(v) for v in p))
                continue
            except ValueError:
                pass
        if cur:
            blocks.append(cur)
        cur = None
    if cur:
        blocks.append(cur)
    return blocks


def test_every_bundled_edge_list_is_normalised_the_way_argyll_defines_it():
    """Columns 2 and 3 are strengths relative to the strongest tick, so each
    block must top out at exactly 1.0 and never exceed it. A file that puts an
    absolute edge LENGTH there (it8Wolf shipped 385.125) makes scanin's
    automatic recogniser return nan and find nothing."""
    d = bundled_targets_dir()
    checked = 0
    for cht in sorted(d.glob("*.cht")):
        blocks = _edge_blocks(cht.read_text(encoding="utf-8", errors="ignore"))
        assert len(blocks) == 2, f"{cht.name}: expected an XLIST and a YLIST"
        for block in blocks:
            assert block, f"{cht.name}: empty edge list"
            for col in (1, 2):
                vals = [row[col] for row in block]
                assert all(0.0 < v <= 1.0 for v in vals), (
                    f"{cht.name}: column {col + 1} outside (0, 1] — "
                    f"max {max(vals)!r}; it must be relative to the strongest "
                    f"tick, not an absolute length")
                assert abs(max(vals) - 1.0) < 1e-9, (
                    f"{cht.name}: column {col + 1} never reaches 1.0 "
                    f"(max {max(vals)!r}) — nothing is the strongest tick")
            checked += 1
    assert checked == 2 * len(_BUNDLED), "every bundled target must be checked"
