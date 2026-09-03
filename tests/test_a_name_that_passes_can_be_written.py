"""A project name that passes the door can have its files written — Windows.

Finding B of the first Windows verification (2026-09-03,
`WINDOWS-VM-REPORT.md`). A name of 111 to 120 characters passed
`ui.dialogs.name_prompt.validate` and the chart file then could not be written
at all, because Windows caps the whole PATH at `MAX_PATH` while the cap was
chosen for macOS, which caps a single name COMPONENT. The person saw
`[2] No such file or directory` naming a path that looks perfectly ordinary,
with nothing anywhere saying "too long".

WHAT IS MEASURED HERE AND WHAT IS NOT. macOS cannot enforce `MAX_PATH`, so
nothing in this file proves that Windows accepts a path — it proves the
ARITHMETIC: that the longest path ChromIQ derives from a name the door now
accepts is inside the budget, that the constant this is all built on is still
the real worst case in `core/file_manager.py`, and that a name already on disk
is still let through. The Windows half is stated as reasoned, not measured, and
the steps to confirm it on the owner's VM are in the review's REPORT.md.
"""
from __future__ import annotations

import os
import re

import pytest

from core import file_manager as fm
from core import path_budget as pb

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# The constant the whole budget rests on
# ---------------------------------------------------------------------------

def _tails(name: str) -> "dict[str, str]":
    """Every path ChromIQ derives from a project called *name*, relative to the
    root, as {tail: where it came from}.

    Read off the classes rather than listed here, so a new artefact cannot
    silently make the budget wrong: adding a property to `Run` puts it in this
    sweep the moment it exists.
    """
    from pathlib import Path
    root = Path("/R")
    proj = root / name
    out: dict[str, str] = {}

    def note(p, src):
        try:
            out[str(Path(p).relative_to(root))] = src
        except ValueError:
            pass

    def walk(obj, label):
        cls = type(obj)
        for attr in dir(cls):
            if attr.startswith("_") or not isinstance(
                    getattr(cls, attr, None), property):
                continue
            try:
                v = getattr(obj, attr)
            except Exception:                       # noqa: BLE001
                continue
            if isinstance(v, Path):
                note(v, f"{label}.{attr}")

    # run99 and a same-second verification collision: the deepest ids ChromIQ
    # composes without help from the user.
    run = fm.Run.for_dir(proj / "runs" / "run99")
    cal = fm.Calibration(proj)
    ver = fm.Verification(run, "2026-09-03_120000_9")
    walk(run, "Run")
    walk(cal, "Calibration")
    walk(ver, "Verification")

    # …and the files built by name inside those folders, which are not
    # properties. Each is a real f-string in the product; the source it comes
    # from is named so a reader can check it.
    stem, cstem, vstem = run.stem, cal.stem, run.verify_stem
    for p, src in [
        (run.dir / f"{stem}_01.tif", "chart_creator page bitmap"),
        (run.dir / f"{stem}.ti3.engine-partial", "Run.engine_partial_ti3"),
        (run.dir / f"{stem}.strips.json", "Run chart .strips.json"),
        (run.dir / f"{stem}.print.json", "Run chart .print.json"),
        (run.dir / f"{stem}{fm.CONFLICT_MARKER}.ti2", "_move_aside_conflict"),
        (run.dir / f"{stem}{fm.CONFLICT_MARKER}_9.channels.json",
         "_move_aside_conflict, numbered"),
        (fm.exports_subdir(run.dir) / f"{stem}-i1profiler-shuffled.pxf",
         "tab_chart i1Profiler export"),
        (fm.exports_subdir(run.dir) / f"{stem}-colours.txt", "colours sidecar"),
        (fm.cache_subdir(run.dir) / f"{stem}-patchbox-sample.cht",
         "scanin_dialog working copy"),
        (fm.cache_subdir(run.dir) / f"{stem}-diag.tif", "scanin diagnostic"),
        (cal.dir / f"{cstem}_01.tif", "cal chart page bitmap"),
        (fm.exports_subdir(cal.dir) / f"{cstem}-i1profiler-shuffled.pxf",
         "cal i1Profiler export"),
        (run.verifications_dir / f"{vstem}_01.tif", "verify chart page bitmap"),
        (ver.dir / f"{vstem}.ti3", "Verification.measurement_ti3"),
    ]:
        note(p, src)
    return out


MARK = "N" * 40


def test_the_longest_tail_is_the_number_the_budget_uses():
    """`LONGEST_TAIL` is the real worst case, not a remembered one.

    The tail is measured by putting a marker name through every path ChromIQ
    builds and subtracting the marker back out. If somebody adds an artefact
    with a longer suffix — or a deeper sub-folder — this fails and the budget
    is re-derived instead of quietly going stale.
    """
    worst_const, worst_tail = -1, ""
    for tail in _tails(MARK):
        occ = tail.count(MARK)
        if occ != pb.NAME_OCCURRENCES:
            continue
        const = len(tail) - occ * len(MARK)
        if const > worst_const:
            worst_const, worst_tail = const, tail
    assert worst_const == pb.LONGEST_TAIL, (
        f"the longest name-bearing tail is now {worst_const} characters, and "
        f"core.path_budget.LONGEST_TAIL says {pb.LONGEST_TAIL}. The worst is:\n"
        f"    {worst_tail}")


def test_no_path_carries_the_name_more_than_twice():
    """The budget divides by two. A third copy of the name in one path would
    make every number in `core.path_budget` wrong, silently."""
    bad = {t: s for t, s in _tails(MARK).items()
           if t.count(MARK) > pb.NAME_OCCURRENCES}
    assert bad == {}, bad


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------

def test_a_name_the_door_accepts_fits_under_max_path():
    """The whole point: accepted implies writable.

    Built as a real string, at the reference root, through the same classes the
    app uses — not as a sum of the constants, which would only prove that the
    constants add up to themselves.
    """
    from pathlib import PureWindowsPath
    root = PureWindowsPath("C:/Users/" + "u" * 20 + "/ChromIQ")
    assert len(str(root)) == pb.REFERENCE_WINDOWS_ROOT
    name = "N" * pb.name_budget()
    worst = max((len(str(root / t)) for t in _tails(name)), default=0)
    assert worst <= pb.WINDOWS_PATH_MAX, (
        f"a name of {len(name)} characters — which the door accepts — reaches "
        f"{worst} characters of path, and Windows stops at "
        f"{pb.WINDOWS_PATH_MAX}")


def test_one_character_more_would_not_fit():
    """…and the cap is not simply generous.

    A budget that is far below the real limit would pass the test above while
    costing everyone name length for nothing. One character more must break it,
    or the number has drifted low.
    """
    from pathlib import PureWindowsPath
    root = PureWindowsPath("C:/Users/" + "u" * 20 + "/ChromIQ")
    name = "N" * (pb.name_budget() + 1)
    worst = max(len(str(root / t)) for t in _tails(name))
    assert worst > pb.WINDOWS_PATH_MAX


def test_the_budget_shrinks_as_the_project_folder_gets_deeper():
    """A fixed number cannot be right: the window widens the deeper the user's
    ChromIQ folder is, which is what the Windows report says."""
    shallow = pb.budget_for_root("C:\\ChromIQ")
    default = pb.budget_for_root("C:\\Users\\sebas\\ChromIQ")
    onedrive = pb.budget_for_root(
        "C:\\Users\\sebastian\\OneDrive\\Documents\\ChromIQ")
    assert shallow > default > onedrive
    assert onedrive >= pb.MIN_BUDGET


def test_the_window_the_windows_report_measured_is_now_closed():
    """111 to 120 characters: accepted by the old door, then unwritable.

    Every length in that window is refused now, and so is everything between
    the new cap and it — the old cap was not merely a few characters out, it
    was the wrong limit. The boundary itself is checked both ways so the cap
    cannot drift without this failing.
    """
    from ui.dialogs.name_prompt import validate
    cap = pb.name_budget()
    assert validate("N" * cap) is None
    for n in (cap + 1, 111, 115, 120):
        why = validate("N" * n)
        assert why is not None, n
        assert "too long" in why


def test_a_multibyte_name_is_held_to_the_byte_rule_as_well():
    """Windows counts characters and a POSIX component limit counts bytes, so
    only checking both catches a name that is short in one and long in the
    other. 80 Japanese characters are 240 bytes."""
    ja = "あ" * pb.name_budget()
    assert len(ja) <= pb.name_budget()
    assert len(ja.encode("utf-8")) > pb.MAX_NAME_BYTES
    assert not pb.fits(ja)


def test_the_message_names_a_length_that_actually_passes():
    """The number in the sentence has to be usable.

    Two rules in two units means naming either cap alone can misdirect: told
    "80 characters", a Japanese name cut to 80 still fails the byte rule. The
    message names the length this name must come down to, so cutting to it
    always works.
    """
    from ui.dialogs.name_prompt import validate
    for name in ("N" * 200, "あ" * 200, "Prüfdruck-" * 30):
        why = validate(name)
        assert why is not None, name
        n = int(re.search(r"(\d+)", why).group(1))
        assert validate(name[:n]) is None, (name[:20], n)


# ---------------------------------------------------------------------------
# A name already on disk is a fixed point
# ---------------------------------------------------------------------------

def test_a_name_already_on_disk_is_not_refused_for_length():
    """Basti's ruling, and the thing a tightened cap could most easily break.

    ChromIQ made names of up to 120 bytes under the old cap. Such a project
    exists on somebody's disk, its name is what the name box holds the moment
    it is opened, and it must still build."""
    from ui.dialogs.name_prompt import validate
    legacy = "N" * 118
    assert validate(legacy) is not None            # refused as a NEW name
    assert validate(legacy, on_disk=True) is None  # and allowed as an old one


@pytest.mark.parametrize("bad", ["CON", "bad:name", ".hidden", "..."])
def test_on_disk_relaxes_the_length_rule_and_nothing_else(bad):
    """A folder cannot hold `:` or be called `CON` on Windows at all, so a name
    like that can never be the name of a project that exists — and the escape
    hatch must not become a way past the other rules."""
    from ui.dialogs.name_prompt import validate
    assert validate(bad, on_disk=True) is not None


def test_the_build_gate_lets_an_over_long_open_project_through(tmp_path):
    """The route that would actually have locked somebody out.

    `TabChart._name_needs_asking` validates whatever is in the name box, and
    opening a project puts its own name there. Driven through the real method
    with a real folder on disk.
    """
    from ui.tabs.tab_chart import TabChart

    legacy = "N" * 118
    (tmp_path / legacy).mkdir()
    (tmp_path / legacy / "project.json").write_text("{}", encoding="utf-8")

    class _FM:
        def resolved_root_for_name(self, name):
            p = tmp_path / name
            return p if p.is_dir() else None

    tab = TabChart.__new__(TabChart)
    tab._file_mgr = _FM()
    assert tab._name_is_a_project_on_disk(legacy) is True
    assert tab._name_needs_asking(legacy) is False
    # …and a name that long which is NOT on disk is still stopped at the door.
    assert tab._name_needs_asking("M" * 118) is True


def test_the_app_never_suggests_a_name_it_would_refuse():
    """The suggestion and the door must agree.

    Four real descriptions joined together are 97 characters — over the cap —
    and the suggestion is what sits in the box when nobody types. Before this,
    pressing Generate would have told the person to shorten a name ChromIQ
    itself wrote.
    """
    from ui.dialogs.name_prompt import validate

    long_one = fm.FileManager.default_target_name(
        "Canon PIXMA PRO-300 series", "Hahnemuehle Photo Rag 308",
        "Matte Fine Art", "i1Pro 3 Plus")
    assert len(long_one) > 60, "the fixture stopped being a long name"
    assert validate(long_one) is None, long_one

    # …and the timestamp survives whole, because it is what makes two
    # suggestions a minute apart different from each other.
    assert re.search(r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$", long_one), long_one
    assert validate(fm.FileManager.default_target_name()) is None
