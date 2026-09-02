"""The v1 -> v2 migration must not sweep a chart into `cache/`.

`Project._migrate_v1_to_v2` tidies a flat schema-1 run folder into
`reports/`, `exports/` and `cache/`. The chart chain itself is held back by
`_protected`, which is there for exactly one reason, in its own words: "a
project called 'X-sample' owns a chart 'X-sample.cht' that would otherwise
match the cache pattern".

That guard compared the two names RAW, and the two names come from different
places: `stem` is the FOLDER's spelling and `f.name` is the FILE's. A project
restored from a Mac OS Extended (HFS+) volume has its names decomposed, and a
chart dragged back into an otherwise-composed folder makes the two disagree
even inside one project. `_protected` then did not recognise its own chart, and
`Müller-diag.tif` — the printed page — was moved into `cache/`, the one folder
`ui/file_guide` tells the user is "always safe to delete".

Nothing is deleted by the migration itself, so this is not silent data loss;
it is the user's chart put where the app tells them to throw things away, and
`chart_tiffs()` cannot see it any more either. `Project.rename`,
`adopt_run_chart_as_verify` and `files_matching` were all taught to compare
NFC-to-NFC in this change set; the migration was missed.
"""
from __future__ import annotations

import json
import unicodedata

import pytest

from core.file_manager import Project

# `-diag` is the shortest of the four cache tails (`-patchbox`, `-sample`,
# `-aligned`, `-diag`) and the only one that also matches a `.tif`, so it is
# the one that can swallow a page bitmap rather than an intermediate `.cht`.
NAME = unicodedata.normalize("NFC", "Müller-diag")


def _flat_v1_project(root, *, file_spelling):
    """A schema-1 project whose run folder is flat, as pre-#127 ChromIQ left it.

    `file_spelling` is applied to the artefact NAMES only; the folder keeps the
    composed spelling, which is the mismatch a partial restore produces.
    """
    root.mkdir(parents=True)
    (root / "project.json").write_text(json.dumps({
        "schema_version": 1, "target_name": NAME,
        "current_run": "run1", "runs": ["run1"]}), encoding="utf-8")
    rd = root / "runs" / "run1"
    rd.mkdir(parents=True)
    stem = unicodedata.normalize(file_spelling, NAME)
    for ext in (".ti1", ".ti2", ".ti3"):
        (rd / f"{stem}{ext}").write_bytes(b"x")
    (rd / f"{stem}.tif").write_bytes(b"the printed page")       # single-page
    (rd / f"{stem}_01.tif").write_bytes(b"page one")            # multi-page
    return rd


@pytest.mark.parametrize("file_spelling", ["NFC", "NFD"])
def test_the_chart_stays_in_the_run_folder(tmp_path, file_spelling):
    root = tmp_path / NAME
    rd = _flat_v1_project(root, file_spelling=file_spelling)

    Project.load(root)

    left = sorted(p.name for p in rd.iterdir() if p.is_file())
    cached = sorted(p.name for p in (rd / "cache").iterdir()) \
        if (rd / "cache").is_dir() else []
    assert cached == [], (
        f"the migration moved {cached} into cache/, which the folder guide "
        "calls always safe to delete")
    assert len(left) == 5, f"artefacts left in the run folder: {left}"
    # And the page is findable again, which is the point of leaving it there.
    run = Project.load(root).run("run1")
    assert len(run.chart_tiffs()) == 2, [p.name for p in run.chart_tiffs()]


def test_a_genuine_cache_intermediate_is_still_swept(tmp_path):
    """The guard must not be widened into "move nothing".

    A scanner intermediate carries its own tail on top of the stem
    (`<stem>-diag.tif`, not `<stem>.tif`), so it is not the chart chain and
    still belongs in `cache/`.
    """
    root = tmp_path / "Plain"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({
        "schema_version": 1, "target_name": "Plain",
        "current_run": "run1", "runs": ["run1"]}), encoding="utf-8")
    rd = root / "runs" / "run1"
    rd.mkdir(parents=True)
    (rd / "Plain.ti2").write_bytes(b"x")
    (rd / "Plain.tif").write_bytes(b"the printed page")
    (rd / "Plain-diag.tif").write_bytes(b"a scanin diagnostic")
    (rd / "Plain-colours.txt").write_bytes(b"a sidecar")
    (rd / "Quality_Check_1_x.txt").write_bytes(b"a report")

    Project.load(root)

    assert sorted(p.name for p in (rd / "cache").iterdir()) == ["Plain-diag.tif"]
    assert sorted(p.name for p in (rd / "exports").iterdir()) == \
        ["Plain-colours.txt"]
    assert sorted(p.name for p in (rd / "reports").iterdir()) == \
        ["Quality_Check_1_x.txt"]
    assert sorted(p.name for p in rd.iterdir() if p.is_file()) == \
        ["Plain.ti2", "Plain.tif"]


def test_an_accented_sidecar_still_reaches_exports(tmp_path):
    """The other half of the same comparison.

    `<stem>-colours.txt` was matched with `f.name in (...)`, raw, so on a
    mixed-spelling tree the hand-off sidecars stayed in the run root instead of
    moving to `exports/`. Nothing is lost by that, but the folder model says
    where they live, so it has to hold.
    """
    root = tmp_path / NAME
    rd = _flat_v1_project(root, file_spelling="NFD")
    nfd = unicodedata.normalize("NFD", NAME)
    (rd / f"{nfd}-colours.txt").write_bytes(b"a sidecar")

    Project.load(root)

    exports = rd / "exports"
    assert exports.is_dir(), "no exports/ folder was made"
    assert [unicodedata.normalize("NFC", p.name) for p in exports.iterdir()] \
        == [f"{NAME}-colours.txt"]
