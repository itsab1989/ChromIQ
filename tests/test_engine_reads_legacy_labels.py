"""ChromIQ's own engine reads a sheet printed with the OLD labels as printed.

Forum report and Knut's ruling, 2026-10-03 (#182 5965589190). Before
4.3.3-beta.7 the layout engine labelled strips and patches with its own rule
(letters A, B .. AA when the pattern contains "A-Z", otherwise 1, 2, 3 ..)
while writing the user's patterns into the .ti2 untouched. chartread parses
SAMPLE_LOC with those patterns, so such a chart was either refused ("Bad
location field value") or, silently, read into the WRONG patches.

``chromiq-chartread`` now notices a layout-engine chart whose locations do not
fit its stated patterns and reads it with the old labels, in memory, without
changing the chart file. These tests drive the REAL helper through its replay
instrument:

(a) strip "0-9" + patch "A-Z", 20 strips: reads completely, strips "1".."20";
(b) strip "A-Z, A-Z" + patch "A-Z", 30 steps (both halves letters, "AAA" is
    strip A patch 27): every reading lands on the location it was given for;
(c) a default-pattern chart: the .ti3 is byte-identical to the one the helper
    wrote before this change (the committed binary of 5221b42d);
(d) strip "0-9" + patch "1-999", 20 strips x 21 steps: "111" is strip 1
    patch 11 or strip 11 patch 1, so the helper says so as a typed
    ``chart_unreadable`` event and exits non-zero;
(e) ``--caps`` lists ``legacy_labels``.
"""
from __future__ import annotations

import json
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ARGYLL = Path("/Applications/Argyll/bin")

#: The last helper binary before the legacy-label change. If the .ti3 format
#: is ever changed ON PURPOSE, test (c) names this; move it to the new commit.
BEFORE_LEGACY_LABELS = "5221b42d"

pytestmark = pytest.mark.skipif(
    not HELPER.exists(), reason="chromiq-chartread helper not built")


# ---- chart and replay helpers ----------------------------------------------
def _targen(tmp: Path, patches: int) -> Path:
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", f"-f{patches}", str(base)],
                   check=True, capture_output=True, cwd=tmp, timeout=120)
    return base


def _build(tmp: Path, patches: int, **kw) -> Path:
    from workflow.layout_engine.chart import build_chart
    base = _targen(tmp, patches)
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=False, **kw)
    return base


def _rows(path: Path) -> "tuple[dict, list[dict]]":
    """Keywords and data rows (dicts by field) of a CGATS file's first table."""
    kw: dict = {}
    fields: list[str] = []
    rows: list[dict] = []
    state = "head"
    for raw in path.read_text(encoding="latin-1").splitlines():
        line = raw.strip()
        if state == "head":
            m = re.match(r'^([A-Z_][A-Z0-9_]*)\s+"([^"]*)"$', line)
            if m and m.group(1) not in kw:
                kw[m.group(1)] = m.group(2)
            if line == "BEGIN_DATA_FORMAT":
                state = "format"
        elif state == "format":
            if line == "END_DATA_FORMAT":
                state = "between"
            else:
                fields += line.split()
        elif state == "between":
            if line == "BEGIN_DATA":
                state = "data"
        elif state == "data":
            if line == "END_DATA":
                break
            if line:
                toks = [t.strip('"') for t in re.findall(r'"[^"]*"|\S+', line)]
                rows.append(dict(zip(fields, toks)))
    return kw, rows


def _legacy_labels(ti2: Path):
    from workflow.layout_engine.labels import LEGACY, ChartLabels
    kw, rows = _rows(ti2)
    n_strips = sum(int(x) for x in kw["PASSES_IN_STRIPS2"].split(","))
    return ChartLabels(kw["STRIP_INDEX_PATTERN"], kw["PATCH_INDEX_PATTERN"],
                       rule=LEGACY, n_strips=n_strips,
                       steps=int(kw["STEPS_IN_PASS"])), kw, rows, n_strips


def _write_replay(ti2: Path, out: Path) -> "tuple[list[str], dict]":
    """A replay giving every location the chart's own expected XYZ, filed
    under the strip and patch the OLD labels say it is printed at. Returns the
    strip labels in order and {loc: (X, Y, Z)}."""
    cl, kw, rows, n_strips = _legacy_labels(ti2)
    steps = int(kw["STEPS_IN_PASS"])
    grid: dict = {}
    want: dict = {}
    for r in rows:
        sp = cl.split(r["SAMPLE_LOC"])
        assert sp is not None, r["SAMPLE_LOC"]
        xyz = (float(r["XYZ_X"]), float(r["XYZ_Y"]), float(r["XYZ_Z"]))
        grid[sp] = xyz
        want[r["SAMPLE_LOC"]] = xyz
    strips = [cl.strip(s) for s in range(n_strips)]
    with out.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        for s, label in enumerate(strips):
            fp.write(f"STRIP {label}\n")
            for p in range(steps):
                if (s, p) in grid:
                    x, y, z = grid[(s, p)]
                    fp.write(f"{x:.4f} {y:.4f} {z:.4f}\n")
    return strips, want


def _read_everything(base: Path, replay: Path, n_strips: int) -> dict:
    """Read every strip in order and finish; returns the session_start event."""
    s = ReplaySession(base, replay)
    try:
        start = s.wait_event("session_start", timeout=20)
        for _ in range(n_strips):
            idx = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("strip_read", after=idx, timeout=20)
            s.wait_event("saved", after=idx, timeout=20)
        s.send(cmd="done")
        s.wait_event("done", timeout=10)
        assert s.finish(timeout=20) == 0
        return start
    finally:
        s.finish(timeout=5)


def _assert_readings_on_their_locations(ti3: Path, want: dict) -> None:
    _kw, rows = _rows(ti3)
    assert len(rows) == len(want)
    wrong = []
    for r in rows:
        got = (float(r["XYZ_X"]), float(r["XYZ_Y"]), float(r["XYZ_Z"]))
        exp = want[r["SAMPLE_LOC"]]
        if max(abs(a - b) for a, b in zip(got, exp)) > 0.01:
            wrong.append((r["SAMPLE_LOC"], exp, got))
    assert not wrong, f"{len(wrong)} readings on the wrong patch, first: {wrong[:3]}"


# ---- (a) numeric strips, letter patches -------------------------------------
def test_numeric_strips_with_letter_patches_read_as_printed(tmp_path):
    base = _build(tmp_path, 400, strip_pattern="0-9", patch_pattern="A-Z",
                  label_rule="legacy")
    ti2 = base.with_suffix(".ti2")
    kw, rows = _rows(ti2)
    assert kw["ORIGINATOR"] == "ChromIQ layout engine"
    assert kw["STRIP_INDEX_PATTERN"] == "0-9"
    n_strips = sum(int(x) for x in kw["PASSES_IN_STRIPS2"].split(","))
    assert n_strips > 10, "the case needs more strips than '0-9' can name"
    assert "11A" in {r["SAMPLE_LOC"] for r in rows}

    before = ti2.read_bytes()
    replay = tmp_path / "replay.txt"
    strips, want = _write_replay(ti2, replay)
    assert strips == [str(n) for n in range(1, n_strips + 1)]

    start = _read_everything(base, replay, n_strips)
    assert [x["strip"] for x in start["strips"]] == strips
    _assert_readings_on_their_locations(base.with_suffix(".ti3"), want)
    assert ti2.read_bytes() == before, "the chart file must not be changed"


# ---- (b) letters on both halves, more than 26 steps -------------------------
def test_letter_strips_with_long_letter_patches_land_on_the_right_patch(tmp_path):
    base = _build(tmp_path, 200, strip_pattern="A-Z, A-Z", patch_pattern="A-Z",
                  label_rule="legacy", patch_w=7.0, patch_h=7.0)
    ti2 = base.with_suffix(".ti2")
    kw, rows = _rows(ti2)
    steps = int(kw["STEPS_IN_PASS"])
    n_strips = sum(int(x) for x in kw["PASSES_IN_STRIPS2"].split(","))
    assert steps > 26 and n_strips < 27
    # Strip A patch 27, which ArgyllCMS's own parser files as strip AA patch A.
    assert rows[26]["SAMPLE_LOC"] == "AAA"

    replay = tmp_path / "replay.txt"
    strips, want = _write_replay(ti2, replay)
    start = _read_everything(base, replay, n_strips)
    assert [x["strip"] for x in start["strips"]] == strips
    _assert_readings_on_their_locations(base.with_suffix(".ti3"), want)


# ---- (c) default patterns: the old path, byte for byte ----------------------
def _helper_before(tmp: Path) -> Path:
    out = tmp / "chromiq-chartread-before"
    try:
        blob = subprocess.run(
            ["git", "show", f"{BEFORE_LEGACY_LABELS}:native/chromiq-chartread"],
            cwd=REPO, capture_output=True, check=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip(f"the helper of {BEFORE_LEGACY_LABELS} is not in this clone")
    if sys.platform != "darwin":
        pytest.skip("the committed helper is the macOS build")
    out.write_bytes(blob)
    out.chmod(out.stat().st_mode | stat.S_IXUSR)
    return out


def _read_with(helper: Path, base: Path, replay: Path, n_strips: int) -> bytes:
    # ReplaySession starts `replay_tools.HELPER`; point it at *helper* for
    # this one read.
    import replay_tools
    saved = replay_tools.HELPER
    replay_tools.HELPER = helper
    try:
        _read_everything(base, replay, n_strips)
    finally:
        replay_tools.HELPER = saved
    text = base.with_suffix(".ti3").read_bytes()
    base.with_suffix(".ti3").unlink()
    # The only line that may differ between two runs is the creation time.
    return re.sub(rb'\nCREATED "[^"]*"', b'\nCREATED ""', text)


@pytest.mark.parametrize("randomize", [False, True])
def test_a_default_pattern_chart_reads_exactly_as_before(tmp_path, randomize):
    old = _helper_before(tmp_path)
    from workflow.layout_engine.chart import build_chart
    base = _targen(tmp_path, 120)
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=randomize)
    ti2 = base.with_suffix(".ti2")
    kw, _rows_ = _rows(ti2)
    assert kw["STRIP_INDEX_PATTERN"] == "A-Z, A-Z"
    n_strips = sum(int(x) for x in kw["PASSES_IN_STRIPS2"].split(","))
    replay = tmp_path / "replay.txt"
    _write_replay(ti2, replay)

    now = _read_with(HELPER, base, replay, n_strips)
    then = _read_with(old, base, replay, n_strips)
    assert now == then


# ---- (d) old labels that cannot be told apart -------------------------------
def test_ambiguous_old_labels_are_refused_as_a_typed_event(tmp_path):
    base = _build(tmp_path, 400, strip_pattern="0-9", patch_pattern="1-999",
                  label_rule="legacy")
    ti2 = base.with_suffix(".ti2")
    kw, rows = _rows(ti2)
    locs = [r["SAMPLE_LOC"] for r in rows]
    # Strip 1 patch 11 and strip 11 patch 1 are both printed "111".
    assert locs.count("111") == 2

    replay = tmp_path / "replay.txt"
    # Never read: the chart is refused before the instrument is asked.
    replay.write_text("PATCHES 21\nSTRIP 1\n50 50 50\n", encoding="utf-8")
    s = ReplaySession(base, replay)
    try:
        ev = s.wait_event("error", timeout=20, kind="chart_unreadable")
        rc = s.finish(timeout=20)
    finally:
        s.finish(timeout=5)
    assert rc != 0
    assert "'111'" in ev["detail"], ev["detail"]
    assert "—" not in ev["detail"]
    assert not any(e.get("event") == "session_start" for e in s.events)
    assert not base.with_suffix(".ti3").exists()


# ---- (e) the capability is announced ----------------------------------------
def test_caps_lists_legacy_labels():
    out = subprocess.run([str(HELPER), "--caps"], capture_output=True,
                         text=True, timeout=30)
    assert out.returncode == 0
    caps = json.loads(out.stdout.strip().splitlines()[-1])
    assert "legacy_labels" in caps["caps"]
