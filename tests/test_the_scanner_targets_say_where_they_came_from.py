"""Where `data/scanner_targets/*.cht` came from, and why nobody should re-derive it.

A licensing sweep (`THIRD-PARTY-NOTICES.md`, B8-76) flagged that the folder
states **GPLv3** while its own README calls the files *derived from* ArgyllCMS,
whose `ref/` material is **AGPLv3**. It left two honest ways out: establish that
the geometry was **regenerated** — original work, GPLv3 the author's to choose —
or mark the folder AGPLv3. It could not choose, because the only measurement it
had was that "every one of the eight differs byte-wise from Argyll's copy".
The measurement below settled it, and the folder is now AGPLv3.

That measurement was the wrong instrument, and this file exists so the mistake
is not repeated. Argyll states a whole grid on one line
(`Y 01 29 A V 24.689655 24.545454 99.5 25.5 24.689655 24.545454`); these files
state one line per patch. The two never match byte-wise even when they describe
the identical grid, so a byte diff — and any "percent similar" taken from one —
answers a question nobody asked. Expand both sides to per-patch boxes first, the
way ArgyllCMS's own reader does (`scanin/scanrd.c`, `read_elist()` / `strinc()`),
and the answer is not close: `BOX_SHRINK` and the patch size are Argyll's in 8
of 8 files, and three files sit at Argyll's absolute coordinates over 864, 288
and 528 patches.

So these tests hold three things still:

* every `.cht` in the folder is named in the README — `it8Wolf.cht` shipped
  unlisted from the first commit, which is how the sweep came to call the folder
  a seven-file folder when it holds eight, and audited seven;
* the README keeps the measurement, per file, rather than an impression;
* the folder's licence, its README and the notices agree with one another. The
  licence question was decided on 2026-09-06 — AGPLv3, matching the upstream
  the geometry comes from — and the folder had carried the wrong one since its
  first commit precisely because nothing checked.

The last test re-measures against the installed Argyll and skips when there is
none. It is the only one that can tell you the README has gone stale rather than
merely gone missing.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.argyll_env import argyll_ref_dir

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ROOT / "data" / "scanner_targets"
README = TARGETS / "README.md"
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"


def _chts() -> list[Path]:
    return sorted(TARGETS.glob("*.cht"))


# --------------------------------------------------------------------------
# a faithful expansion of ArgyllCMS 3.5.0 scanin/scanrd.c read_elist()
# --------------------------------------------------------------------------

def _strinc(s: str) -> str:
    """`strinc()`, scanrd.c L1955 — the label increment Argyll walks a grid with."""
    out = list(s)
    carry, i = 1, len(out) - 1
    while i >= 0 and carry:
        if out[i] == "9":
            out[i], sval, carry = "0", "1", 1
        elif out[i] == "z":
            out[i], sval, carry = "a", "a", 1
        elif out[i] == "Z":
            out[i], sval, carry = "A", "A", 1
        else:
            out[i], carry = chr(ord(out[i]) + 1), 0
            sval = " "
        if i == 0 and carry:
            out.insert(0, sval)
            break
        i -= 1
    return "".join(out)


def _boxes(path: Path) -> dict[str, tuple[float, float, float, float]]:
    """Every SAMPLE box as ``name -> (x1, y1, x2, y2)``.

    Diagnostic (``D``) boxes and the fiducial (``F``) line are not samples and
    are left out. Names are compared with zero-padding normalised, because
    Argyll's own `A01` and rectarg's `A1` are the same patch.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    hdr = next(i for i, ln in enumerate(lines) if re.match(r"^\s*BOXES\s+\d+", ln))
    want = int(re.match(r"^\s*BOXES\s+(\d+)", lines[hdr]).group(1))
    toks: list[str] = []
    for ln in lines[hdr + 1:]:
        toks.extend(ln.split())

    out: dict[str, tuple[float, float, float, float]] = {}
    seen, p = 0, 0
    while seen < want:
        kind, xf1, xf2, yf1, yf2 = toks[p:p + 5]
        w, h, ox, oy, xi, yi = (float(t) for t in toks[p + 5:p + 11])
        p += 11
        if kind[0] == "F":
            continue
        y, ylab = oy, yf1
        while True:
            x, xlab = ox, xf1
            while True:
                if xlab[0] == "_":
                    name = ylab
                elif ylab[0] == "_":
                    name = xlab
                elif kind[0] == "Y":
                    name = ylab + xlab
                else:
                    name = xlab + ylab
                seen += 1
                if kind[0] != "D":
                    m = re.match(r"^([A-Za-z]*)0*(\d+)$", name)
                    key = f"{m.group(1)}{int(m.group(2))}" if m else name
                    out[key] = (x, y, x + w, y + h)
                x += xi
                if xlab == xf2:
                    break
                xlab = _strinc(xlab)
            if ylab == yf2:
                break
            y += yi
            ylab = _strinc(ylab)
    return out


def _declared_sizes(path: Path) -> set[tuple[float, float]]:
    """The box ``w h`` as WRITTEN on each sample-box line.

    Not ``x2 - x1`` of an expanded box: these files write every patch corner
    rounded to four decimals where Argyll accumulates a group from one origin,
    so a derived width wobbles in the fourth decimal (Hutchcolor gives both
    24.5455 and 24.5456) while the DECLARED size — the arbitrary constant that
    was copied — is one number.

    Compared with a tolerance rather than exactly, because these files carry
    Argyll's constant at their own precision: Hutchcolor writes 24.5455 for
    Argyll's 24.545454. That is the same number, not a different one, and a
    strict equality here would report a provenance change every run.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    hdr = next(i for i, ln in enumerate(lines) if re.match(r"^\s*BOXES\s+\d+", ln))
    want = int(re.match(r"^\s*BOXES\s+(\d+)", lines[hdr]).group(1))
    toks: list[str] = []
    for ln in lines[hdr + 1:]:
        toks.extend(ln.split())
    sizes: set[tuple[float, float]] = set()
    seen, p = 0, 0
    while seen < want:
        kind, xf1, xf2, yf1, yf2 = toks[p:p + 5]
        w, h, ox, oy, xi, yi = (float(t) for t in toks[p + 5:p + 11])
        p += 11
        if kind[0] == "F":
            continue
        n = 1
        lab = xf1
        while lab != xf2:
            lab = _strinc(lab); n += 1
        m = 1
        lab = yf1
        while lab != yf2:
            lab = _strinc(lab); m += 1
        seen += n * m
        if kind[0] != "D":
            sizes.add((w, h))
    return sizes


#: Tolerance for "the same declared constant". These files write four decimals;
#: Argyll writes six. 1e-3 is well inside any deliberate change to a box size
#: (the smallest patch here is 12.675 units across) and well outside that.
_SAME = 1e-3


def _same_sizes(ours: set, theirs: set) -> bool:
    def matched(a, pool):
        return any(abs(a[0] - b[0]) <= _SAME and abs(a[1] - b[1]) <= _SAME
                   for b in pool)
    return (all(matched(a, theirs) for a in ours)
            and all(matched(b, ours) for b in theirs))


def _box_shrink(path: Path) -> float:
    m = re.search(r"^[ \t]*BOX_SHRINK[ \t]+(\S+)", path.read_text(
        encoding="utf-8", errors="replace"), re.M)
    assert m, f"{path.name}: no BOX_SHRINK"
    return float(m.group(1))


# --------------------------------------------------------------------------


def test_every_bundled_cht_is_named_in_the_folder_readme():
    """An unlisted file is a file no audit sees.

    `it8Wolf.cht` was bundled from the first commit of this folder and named
    nowhere in its README until 2026-09-06. The licensing sweep that examined
    the folder therefore described it as holding seven `.cht` files, and checked
    seven. Whatever else the README says, it has to at least admit what ships.
    """
    chts = _chts()
    assert chts, f"{TARGETS} holds no .cht — has the folder moved?"
    text = README.read_text(encoding="utf-8")
    unlisted = [p.name for p in chts if p.name not in text]
    assert not unlisted, (
        "these .cht files ship in data/scanner_targets/ and the folder README "
        "does not name any of them:\n  " + "\n  ".join(unlisted)
        + "\n\nAdd them to the bundled list AND to the provenance table — a "
          "target nobody wrote down is a target the next licensing sweep will "
          "not audit.")


def test_the_readme_states_the_measured_provenance_for_every_file():
    """The provenance is a measurement with numbers, not a recollection.

    It has been re-derived at least twice, badly, because the answer was never
    written down with its method. So the README must carry the section, must
    carry each file inside it, and must not have quietly reverted to claiming
    the files are ChromIQ's own.
    """
    text = README.read_text(encoding="utf-8")
    assert "## Provenance — measured, not assumed" in text, (
        "data/scanner_targets/README.md has lost its Provenance section. It "
        "records HOW the derivation was established (both sides expanded to "
        "per-patch boxes through Argyll's own reader) and the per-file numbers. "
        "Without it the next sweep re-measures — and the last one that tried a "
        "byte-wise diff got the wrong answer.")
    prov = text.split("## Provenance — measured, not assumed", 1)[1]
    prov = prov.split("## Credit & licence", 1)[0]
    missing = [p.name for p in _chts() if p.name not in prov]
    assert not missing, (
        "the Provenance section does not give a per-file result for:\n  "
        + "\n  ".join(missing)
        + "\n\n'Do not settle for an overall impression' — every file needs its "
          "own row.")
    assert "not original files" in prov, (
        "the Provenance section no longer states the conclusion it measured. "
        "All eight carry ArgyllCMS's patch geometry; if that has genuinely "
        "changed, re-run the measurement and rewrite the section — do not "
        "soften the sentence.")


def test_the_folder_carries_the_licence_of_the_geometry_it_ships():
    """The folder is AGPLv3, and reverting it to GPLv3 must not be quiet.

    This started as a reminder that a decision was owed. It was made on
    2026-09-06: the geometry measured above is ArgyllCMS's, ArgyllCMS's `ref/`
    is AGPLv3, and a derivative of an AGPLv3 work cannot be shipped under the
    plain GPLv3 — that drops the §13 network clause the AGPL exists for. So the
    folder now states the AGPL.

    A reminder that retires when the decision lands leaves nothing behind, and
    the wrong licence was sitting in this folder from its first commit precisely
    because nothing was watching it. This is what watches it now.

    Note what is NOT asserted: nothing here claims the AGPL is the only
    defensible reading, and the argument is recorded in prose, not in an
    assertion. What is asserted is that the licence file, the README and the
    notices agree with each other — the failure mode that actually happened.
    """
    licence = (TARGETS / "LICENSE").read_text(encoding="utf-8", errors="replace")
    head = licence[:400].upper()
    assert "AFFERO" in head and "VERSION 3" in head, (
        "data/scanner_targets/LICENSE is no longer the AGPLv3.\n\n"
        "These files carry ArgyllCMS's patch geometry (measured — see the "
        "folder README's Provenance section), and Argyll's ref/ is AGPLv3. If "
        "the licence is genuinely being changed, the README's 'Credit & "
        "licence' section and THIRD-PARTY-NOTICES.md have to change with it, "
        "and the reasoning has to survive the measurement.")

    readme = (TARGETS / "README.md").read_text(encoding="utf-8")
    licence_sec = readme.split("## Credit & licence", 1)
    assert len(licence_sec) == 2, "the folder README has lost its 'Credit & licence' section"
    assert "Affero" in licence_sec[1], (
        "the folder ships the AGPL but its README does not say so — a reader "
        "who takes the README at its word would state the wrong licence.")

    notices = NOTICES.read_text(encoding="utf-8")
    sec = notices.split("## Scanner target recognition files", 1)
    assert len(sec) == 2, "THIRD-PARTY-NOTICES.md no longer covers data/scanner_targets/"
    sec = sec[1].split("\n## ", 1)[0]
    assert re.search(r"\*\*Licence: AGPLv3[^*]*\*\*", sec), (
        "THIRD-PARTY-NOTICES.md no longer STATES the folder's licence in its "
        "own section — a passing mention of AGPLv3 somewhere in the prose is "
        "not the same thing. This is the file a redistributor reads to find "
        "out what terms these eight files come under; it cannot be the one "
        "that is vague.")
    assert "remains GPLv3" in sec or "ChromIQ's own licence is untouched" in sec, (
        "the notices no longer say that ChromIQ itself stays GPLv3. One folder "
        "of AGPLv3 data files does not relicense the application, and leaving "
        "that unsaid invites exactly the wrong conclusion.")

    still_open = notices.split("## Still open", 1)
    assert len(still_open) == 2, "THIRD-PARTY-NOTICES.md has lost its 'Still open' section"
    assert "data/scanner_targets/" not in still_open[1], (
        "the scanner-target licence is listed as still open, but the folder "
        "states a decided licence. Either the decision was reverted, or the "
        "open item outlived it — the two must not disagree.")


@pytest.mark.skipif(argyll_ref_dir() is None, reason="ArgyllCMS ref/ not installed")
def test_the_geometry_still_matches_argylls_the_way_the_readme_says():
    """Re-measure, so the README can go stale loudly instead of quietly.

    Two invariants, both chosen because they survive the rescaling four of these
    files got and are free choices rather than facts about the physical chart:
    `BOX_SHRINK`, a tuning constant in the file's own units, and the patch size.
    A file that stops matching on either is a file whose provenance has genuinely
    changed — re-run the full comparison and rewrite the README's table before
    touching this test.
    """
    ref = argyll_ref_dir()
    mismatched, checked = [], 0
    for ours in _chts():
        theirs = ref / ours.name
        if not theirs.exists():
            continue
        checked += 1
        if _box_shrink(ours) != _box_shrink(theirs):
            mismatched.append(
                f"{ours.name}: BOX_SHRINK {_box_shrink(ours)} vs Argyll's "
                f"{_box_shrink(theirs)}")
        shared = set(_boxes(ours)) & set(_boxes(theirs))
        assert shared, f"{ours.name}: no patch names in common with Argyll's copy"
        sizes, theirsz = _declared_sizes(ours), _declared_sizes(theirs)
        if not _same_sizes(sizes, theirsz):
            mismatched.append(
                f"{ours.name}: declared patch sizes {sorted(sizes)} vs Argyll's "
                f"{sorted(theirsz)}")
    assert checked >= 8, (
        f"only {checked} bundled targets had an Argyll counterpart to compare "
        "against — the comparison this README rests on has stopped running")
    assert not mismatched, (
        "the bundled .cht no longer carry ArgyllCMS's arbitrary constants:\n  "
        + "\n  ".join(mismatched)
        + "\n\nThat is a provenance change. Re-run the per-file comparison and "
          "rewrite data/scanner_targets/README.md before editing this test.")
