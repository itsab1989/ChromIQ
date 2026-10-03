"""Twenty-two strip/patch pattern pairs that ArgyllCMS allows, each laid out by
ChromIQ, checked against ArgyllCMS itself and read through by BOTH readers.

Knut, #182 5965589190 (2026-10-03): *"at least 20 supported variants of the
strip and patch patterns should be simulated and tested working ... for both
commands, chartread and ChromIQ engine."* The pairs come from ArgyllCMS's
printtarg documentation (the default, "0-9, 1-9", "0-9, 1-9;1-19,30-39", the
ECI2002R "A-Z, 2-9;A-X,2A-9Z", and its note that the two halves must be
distinguishable) and from its grammar (``target/alphix.c``): letters or
numbers on either side, '@' blanks, zero padding, ranges, skipped letters,
lower case, and charts of more than one page.

For every pair:

1. ChromIQ builds the chart (labels by ArgyllCMS's rules, randomised, so the
   readers have to SORT the locations), and the pair passes ChromIQ's own
   check;
2. stock ArgyllCMS ``printtarg -x/-y`` accepts the same pair and labels its
   own chart with the same strip and patch labels ChromIQ uses;
3. stock ArgyllCMS ``chartread``'s own location code accepts the chart: the
   labels and ``patch_location_order`` come from ArgyllCMS's ``alphix.c``
   compiled into a small harness (``tests/data/alphix_harness``), and the
   chart passes exactly the checks ``spectro/chartread.c`` makes before it
   reads (every location ordered, none twice, sorted into the printed
   strip-and-patch order). Stock chartread itself is NOT launched: with no
   instrument it opens serial port 1, and on a Mac whose Bluetooth serial port
   is stuck that open never returns and the process cannot be killed
   (2026-10-03, 36 of them left behind by an earlier version of this test);
4. ChromIQ's engine reads the whole chart through its replay instrument,
   announces the strips with the chart's own labels, and every reading lands
   on the location it was given for.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession  # noqa: E402

from workflow.layout_engine import alphix                       # noqa: E402
from workflow.layout_engine.labels import (ChartLabels,         # noqa: E402
                                           labels_for_chart)

ARGYLL = Path("/Applications/Argyll/bin")

#: (strip pattern, patch pattern, patches, max strip length in mm or None,
#:  where the pair comes from)
VARIANTS = [
    ("A-Z, A-Z", "0-9,@-9,@-9;1-999", 1000, None, "the default, two pages"),
    ("A-Z", "0-9,@-9,@-9;1-999", 300, None, "single letters"),
    ("A-Z, A-Z", "0-9,@-9;1-99", 400, None, "patches up to 99"),
    ("0-9,@-9;1-99", "A-Z", 1000, None, "numbered strips, lettered patches, two pages"),
    ("0-9,@-9", "A-Z", 300, None, "strips counted from 0"),
    ("0-9", "A-Z", 150, None, "strips 0 to 9"),
    ("0-9,@-9;1-99", "A-Z, A-Z", 400, None, "lettered patches past Z"),
    ("A-Z, 2-9;A-X,2A-9Z", "0-9,@-9,@-9;1-999", 700, None, "ECI2002R (printtarg docs)"),
    ("A-HJ-NP-Z, A-HJ-NP-Z", "0-9,@-9;1-99", 700, None, "no I and no O"),
    ("a-z, a-z", "0-9,@-9,@-9;1-999", 700, None, "lower case"),
    ("A-Z, A-Z", "0-9,0-9;01-99", 400, None, "zero padded 01, 02"),
    ("A-Z, A-Z", "0-9, 1-9", 400, None, "0 to 99 (printtarg docs)"),
    ("A-Z, A-Z", "0-9, 1-9;1-19,30-39", 400, None, "1-19 then 30-39 (printtarg docs)"),
    ("1-9", "A-Z", 150, None, "strips 1 to 9"),
    ("0-9,0-9;01-99", "A-Z", 400, None, "strips 01, 02"),
    ("A-Z;B-Z", "0-9,@-9,@-9;1-999", 300, None, "strips from B"),
    ("A-Z, A-Z", "1-9", 200, 100, "patches 1 to 9"),
    ("A-Z, A-Z;A-ZZ", "0-9,@-9,@-9;1-999", 400, None, "the default range written out"),
    ("0-9,@-9,@-9;1-999", "A-Z", 400, None, "strips up to 999"),
    ("A-Z, A-Z", "0-9,@-9;1-50", 400, None, "patches up to 50"),
    ("A-Z", "0-9", 100, 100, "patches 0 to 9"),
    ("0-9,@-9;1-99", "A-Z;A-H,J-N,P-Z", 400, None, "lettered patches without I and O"),
]


def _ids(v):
    return f"{v[0]}|{v[1]}"


def _ti1(d: Path, n: int) -> Path:
    """A patch set whose every patch has its own expected XYZ, so a reading
    filed under the wrong location cannot pass."""
    lines = ["CTI1", "", 'DESCRIPTOR "variants"', 'ORIGINATOR "ChromIQ"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {(i*7)%100}.0 {(i*13)%100}.0 {(i*29)%100}.0 "
                     f"{5 + (i % 90):.1f} {10 + (i * 3) % 80:.1f} "
                     f"{3 + (i * 7) % 95:.1f}")
    lines += ["END_DATA", ""]
    p = d / "p.ti1"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _build(d: Path, strip, patch, n, max_strip) -> Path:
    from workflow.layout_engine.chart import build_chart
    d.mkdir(parents=True, exist_ok=True)
    build_chart(_ti1(d, n), d / "chart", instrument="i1", paper="A4", dpi=72,
                seed=4242, randomize=True, max_strip=max_strip,
                strip_pattern=strip, patch_pattern=patch)
    return d / "chart"


def _rows(ti2: Path):
    from workflow.layout_engine.labels import read_chart_text
    text = ti2.read_text(encoding="latin-1")
    kw, _locs = read_chart_text(text)
    fields: list = []
    rows: list = []
    state = "head"
    for raw in text.splitlines():
        line = raw.strip()
        if state == "head" and line == "BEGIN_DATA_FORMAT":
            state = "format"
        elif state == "format":
            if line == "END_DATA_FORMAT":
                state = "between"
            else:
                fields += line.split()
        elif state == "between" and line == "BEGIN_DATA":
            state = "data"
        elif state == "data":
            if line == "END_DATA":
                break
            if line:
                toks = [t.strip('"') for t in re.findall(r'"[^"]*"|\S+', line)]
                rows.append(dict(zip(fields, toks)))
    return kw, rows


@pytest.fixture(scope="module")
def argyll_alphix(tmp_path_factory):
    """ArgyllCMS's alphix.c compiled with the test harness, or a skip."""
    cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if cc is None:
        pytest.skip("no C compiler to build ArgyllCMS's alphix")
    repo = Path(__file__).resolve().parents[1]
    src = repo / "tests" / "data" / "alphix_harness"
    work = tmp_path_factory.mktemp("alphix")
    # alphix.c includes "numsup.h" from its OWN folder first, so it is
    # compiled beside the stub rather than in native/instlib.
    for f in (src / "harness.c", src / "numsup.h",
              repo / "native" / "instlib" / "alphix.c",
              repo / "native" / "instlib" / "alphix.h"):
        shutil.copy2(f, work / f.name)
    out = work / "harness"
    res = subprocess.run(
        [cc, "-O1", f"-I{work}", "-o", str(out), str(work / "harness.c"),
         str(work / "alphix.c")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120)
    if res.returncode != 0:
        pytest.skip("could not build ArgyllCMS's alphix: " + res.stderr[-300:])
    return out


def _argyll_labels(harness: Path, pattern: str) -> "list[str]":
    out = subprocess.run([str(harness), "a", pattern], capture_output=True,
                         text=True, encoding="utf-8", timeout=60).stdout
    lines = out.splitlines()
    assert lines and not lines[0].startswith("ERR"), (pattern, lines[:1])
    return [ln.split("|")[1] for ln in lines[1:]]


def _argyll_orders(harness: Path, strip: str, patch: str,
                   locs: "list[str]") -> "dict[str, int]":
    out = subprocess.run([str(harness), "o", strip, patch, "0"],
                         input="\n".join(locs) + "\n", capture_output=True,
                         text=True, encoding="utf-8", timeout=60).stdout
    got = {}
    for ln in out.splitlines():
        loc, o = ln.rsplit("|", 1)
        got[loc] = int(o)
    return got


def test_there_are_at_least_twenty_and_each_is_different():
    assert len(VARIANTS) >= 20
    assert len({(v[0], v[1]) for v in VARIANTS}) == len(VARIANTS)


@pytest.mark.parametrize("variant", VARIANTS, ids=_ids)
def test_chromiq_builds_it_and_argyll_reads_its_locations(variant, tmp_path):
    strip, patch, n, max_strip, _why = variant
    base = _build(tmp_path, strip, patch, n, max_strip)
    ti2 = base.with_suffix(".ti2")
    kw, rows = _rows(ti2)
    n_strips = sum(int(x) for x in kw["PASSES_IN_STRIPS2"].split(","))
    steps = int(kw["STEPS_IN_PASS"])
    assert alphix.check_patterns(strip, patch, n_strips, steps) is None
    assert alphix.chart_locations_problem(ti2) is None
    cl = labels_for_chart(ti2)
    assert cl.rule == "argyll"
    # every location is ArgyllCMS's own label for its strip and patch
    sa, pa = alphix.Alphix(strip), alphix.Alphix(patch)
    for r in rows:
        o = alphix.patch_location_order(sa, pa, 0, r["SAMPLE_LOC"])
        assert o >= 0, r["SAMPLE_LOC"]
        s, p = divmod(o, pa.maxlen())
        assert sa.aix(s) + pa.aix(p) == r["SAMPLE_LOC"]


@pytest.mark.parametrize("variant", VARIANTS, ids=_ids)
def test_stock_printtarg_accepts_it_and_labels_the_same_way(variant, tmp_path):
    printtarg = shutil.which("printtarg") or str(ARGYLL / "printtarg")
    if not Path(printtarg).exists():
        pytest.skip("ArgyllCMS printtarg not available")
    strip, patch, n, _ms, _why = variant
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    subprocess.run([targen, "-v0", "-d2", "-G", f"-f{n}", "pt"], cwd=tmp_path,
                   check=True, capture_output=True, timeout=120)
    # printtarg has no strip-length option; a short page gives short strips
    # for the two patterns with only nine or ten patch labels.
    paper = "210x120" if _ms else "A4"
    res = subprocess.run([printtarg, "-v0", "-ii1", f"-p{paper}", "-s", "-t72",
                          "-x", strip, "-y", patch, "pt"],
                         cwd=tmp_path, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120)
    assert res.returncode == 0, res.stderr[-800:]
    kw, rows = _rows(tmp_path / "pt.ti2")
    assert kw["STRIP_INDEX_PATTERN"] == strip
    cl = ChartLabels(strip, patch)
    for r in rows:
        if r.get("SAMPLE_ID", "1") in ("0",):
            continue
        sp = cl.split(r["SAMPLE_LOC"])
        assert sp is not None and cl.location(*sp) == r["SAMPLE_LOC"], \
            r["SAMPLE_LOC"]


@pytest.mark.parametrize("variant", VARIANTS, ids=_ids)
def test_stock_chartreads_own_location_code_accepts_it(variant, tmp_path,
                                                       argyll_alphix):
    """spectro/chartread.c, before it reads: new_alphix() on both patterns
    (an error ends the run), patch_location_order() on every SAMPLE_LOC (a -1
    on a randomised chart is "Bad location field value"), then a sort by that
    order, which must give the strips and patches as printed."""
    strip, patch, n, max_strip, _why = variant
    base = _build(tmp_path, strip, patch, n, max_strip)
    kw, rows = _rows(base.with_suffix(".ti2"))
    assert "RANDOM_START" in kw, "randomised, so chartread must sort"
    n_strips = sum(int(x) for x in kw["PASSES_IN_STRIPS2"].split(","))
    steps = int(kw["STEPS_IN_PASS"])
    slabels = _argyll_labels(argyll_alphix, strip)
    plabels = _argyll_labels(argyll_alphix, patch)
    locs = [r["SAMPLE_LOC"] for r in rows]
    orders = _argyll_orders(argyll_alphix, strip, patch, locs)
    assert all(orders[loc] >= 0 for loc in locs), \
        [loc for loc in locs if orders[loc] < 0][:5]
    assert len(set(orders.values())) == len(locs), "two locations sort as one"
    printed = [slabels[s_] + plabels[p] for s_ in range(n_strips)
               for p in range(steps)]
    in_sort_order = sorted(locs, key=lambda loc: orders[loc])
    assert in_sort_order == [x for x in printed if x in set(locs)]


def test_the_control_argylls_location_code_refuses_the_forum_chart(
        tmp_path, argyll_alphix):
    """Without this, the check above could pass on a harness that refuses
    nothing. The forum report's chart, printed with ChromIQ's old labels,
    makes ArgyllCMS's own patch_location_order answer -1, which on a
    randomised chart is chartread's "Bad location field value"."""
    from workflow.layout_engine.chart import build_chart
    build_chart(_ti1(tmp_path, 400), tmp_path / "chart", instrument="i1",
                paper="A4", dpi=72, seed=1, strip_pattern="0-9",
                patch_pattern="A-Z", label_rule="legacy")
    kw, rows = _rows(tmp_path / "chart.ti2")
    locs = [r["SAMPLE_LOC"] for r in rows]
    orders = _argyll_orders(argyll_alphix, "0-9", "A-Z", locs)
    assert "RANDOM_START" in kw
    assert any(o < 0 for o in orders.values())


@pytest.mark.skipif(not HELPER.exists(), reason="chromiq-chartread not built")
@pytest.mark.parametrize("variant", VARIANTS, ids=_ids)
def test_chromiq_engine_reads_the_whole_chart_onto_the_right_patches(
        variant, tmp_path):
    strip, patch, n, max_strip, _why = variant
    base = _build(tmp_path, strip, patch, n, max_strip)
    ti2 = base.with_suffix(".ti2")
    kw, rows = _rows(ti2)
    cl = labels_for_chart(ti2)
    n_strips = sum(int(x) for x in kw["PASSES_IN_STRIPS2"].split(","))
    steps = int(kw["STEPS_IN_PASS"])
    grid, want = {}, {}
    for r in rows:
        sp = cl.split(r["SAMPLE_LOC"])
        xyz = (float(r["XYZ_X"]), float(r["XYZ_Y"]), float(r["XYZ_Z"]))
        grid[sp] = xyz
        want[r["SAMPLE_LOC"]] = xyz
    strips = [cl.strip(s) for s in range(n_strips)]
    replay = tmp_path / "replay.txt"
    with replay.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        for s, label in enumerate(strips):
            fp.write(f"STRIP {label}\n")
            for p in range(steps):
                if (s, p) in grid:
                    x, y, z = grid[(s, p)]
                    fp.write(f"{x:.4f} {y:.4f} {z:.4f}\n")
    s = ReplaySession(base, replay)
    try:
        start = s.wait_event("session_start", timeout=30)
        assert [x["strip"] for x in start["strips"]] == strips
        for _ in range(n_strips):
            idx = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("strip_read", after=idx, timeout=30)
            s.wait_event("saved", after=idx, timeout=30)
        s.send(cmd="done")
        s.wait_event("done", timeout=15)
        assert s.finish(timeout=30) == 0
    finally:
        s.finish(timeout=5)
    _kw, got = _rows(base.with_suffix(".ti3"))
    assert len(got) == len(want)
    wrong = [r["SAMPLE_LOC"] for r in got
             if max(abs(float(r[k]) - v) for k, v in
                    zip(("XYZ_X", "XYZ_Y", "XYZ_Z"), want[r["SAMPLE_LOC"]]))
             > 0.01]
    assert not wrong, f"{len(wrong)} readings on the wrong patch: {wrong[:5]}"
