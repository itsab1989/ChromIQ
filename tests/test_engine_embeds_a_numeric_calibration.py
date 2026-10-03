"""The measuring engine copies a chart's printer calibration into the .ti3
as NUMBERS, the same numbers the chart's .ti2 carries.

Forum report, 2026-10-03 (CMYK chart, CR30): the profile build failed with
colprof's "Field 'CMYK_C' has unexpected type". Every chart that carries a
printer calibration (``-K`` or ``-I``) and was read through ChromIQ's own
measuring engine (``native/chromiq-chartread``) got a .ti3 whose embedded
CAL table was all ``nan``, for every instrument and for RGB as well as CMYK.

The cause is one line in the vendored standalone Argyll library:
``native/instlib/rspl1.c`` ``set_rspl`` wrote the grid index at ``iv[-1-1]``
while ``xcal.c``'s callback reads it at ``in[-0-1]``. rspl1 is 1-D, and its
own comment, ``rspl.h`` and the full ``rspl.c`` all say ``iv[-e-1]``, i.e.
``iv[-1]``. Upstream Argyll 3.5.0 carries the same line but never reaches it
(stock chartread links the full rspl), so it is ChromIQ's to patch, and
``scripts/vendor_instlib.py`` re-applies the patch on every re-vendor.

Three things are pinned here:

* the source line, the vendoring script's patch table and PROVENANCE.md;
* the real committed helper, replaying CMYK ``-K``, iRGB ``-I``, CMY ``-K``
  and 6-ink CMYKOG ``-K`` charts, writes a CAL table equal to the .ti2's for
  every channel; colprof profiles the first three, and for CMYKOG (which
  colprof cannot profile) Argyll's own CAL reader gets the same curves back;
* ``printer_calibration.run_cal_source`` treats a ``nan`` table in an older
  .ti3 as absent and falls back to the .ti2's (nothing is written).
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
INSTLIB = REPO / "native" / "instlib"
ARGYLL = Path("/Applications/Argyll/bin")

FIXED = "*((int *)&iv[-0-1]) = n;"
UPSTREAM = "*((int *)&iv[-1-1]) = n;"


# ---------------------------------------------------------------------------
# The source line, and what keeps it there
# ---------------------------------------------------------------------------

def test_rspl1_writes_the_grid_index_where_xcal_reads_it():
    rspl1 = (INSTLIB / "rspl1.c").read_text(encoding="utf-8", errors="replace")
    assert rspl1.count(FIXED) == 1, "rspl1.c set_rspl must write iv[-0-1]"
    assert UPSTREAM not in rspl1, (
        "rspl1.c is back to upstream's iv[-1-1]: every -K/-I chart read by "
        "the engine gets an all-nan CAL table again")
    xcal = (INSTLIB / "xcal.c").read_text(encoding="utf-8", errors="replace")
    assert "*((int*)&in[-0-1])" in xcal, (
        "xcal.c no longer reads the index at in[-0-1]; re-check rspl1.c")


def _vendor_module():
    script = REPO / "scripts" / "vendor_instlib.py"
    src = script.read_text(encoding="utf-8")
    # Only the part up to the patch table: running the rest would vendor files.
    head = src.split("# (source-relative, dest-name)")[0]
    assert "PATCHES" in head
    ns: dict = {"__file__": str(script)}
    exec(compile(head, str(script), "exec"), ns)       # noqa: S102
    return ns


def test_re_vendoring_re_applies_the_patch():
    ns = _vendor_module()
    patches = ns["PATCHES"]
    assert "rspl1.c" in patches
    (old, new), = patches["rspl1.c"]
    assert UPSTREAM in old and FIXED in new
    rspl1 = (INSTLIB / "rspl1.c").read_text(encoding="utf-8", errors="replace")
    assert new in rspl1, "the committed rspl1.c is not what the script writes"
    for dest, pairs in patches.items():
        text = (INSTLIB / dest).read_text(encoding="utf-8", errors="surrogateescape")
        for _old, _new in pairs:
            assert _new in text, f"{dest}: a recorded patch is not in the tree"


def test_provenance_names_every_file_by_the_sha_it_really_has():
    """Unpatched files match the upstream sha; patched ones the shipped sha."""
    prov = (INSTLIB / "PROVENANCE.md").read_text(encoding="utf-8")
    shipped = dict(re.findall(
        r"^\| `([^`]+)` \| `[0-9a-f]{16}…` \| `([0-9a-f]{16})…` \|$", prov, re.M))
    assert set(shipped) == set(_vendor_module()["PATCHES"])
    # The "Files" table: | `dest` | `upstream/path` | `sha16…` |
    rows = re.findall(r"^\| `([^`]+)` \| `([^`]+)` \| `([0-9a-f]{16})…` \|$",
                      prov.split("## Files", 1)[1], re.M)
    assert len(rows) > 100
    for name, _upstream_path, upstream in rows:
        want = shipped.get(name, upstream)
        have = hashlib.sha256((INSTLIB / name).read_bytes()).hexdigest()[:16]
        assert have == want, f"{name}: PROVENANCE says {want}, file is {have}"


# ---------------------------------------------------------------------------
# The real helper, end to end
# ---------------------------------------------------------------------------

def _tool(name: str) -> str:
    found = shutil.which(name) or str(ARGYLL / name)
    if not Path(found).exists():
        pytest.skip(f"Argyll {name} not available")
    return found


def _write_cal(path: Path, rep: str, chans: "list[str]") -> None:
    """A smooth, clearly non-identity printer calibration, 256 steps, a
    different curve per channel so a channel mix-up shows."""
    pre = rep.lstrip("i")                  # iRGB's fields are RGB_*
    lines = ["CAL", "", 'DESCRIPTOR "Argyll Device Calibration Curves"',
             'ORIGINATOR "ChromIQ test"', 'DEVICE_CLASS "OUTPUT"',
             f'COLOR_REP "{rep}"', "",
             f"NUMBER_OF_FIELDS {len(chans) + 1}", "BEGIN_DATA_FORMAT",
             " ".join([f"{pre}_I"] + [f"{pre}_{c}" for c in chans]),
             "END_DATA_FORMAT", "", "NUMBER_OF_SETS 256", "BEGIN_DATA"]
    for i in range(256):
        x = i / 255.0
        vals = [x ** (1.0 + 0.15 * (k + 1)) for k in range(len(chans))]
        lines.append(" ".join(f"{v:.6f}" for v in [x] + vals))
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="ascii")


def _cal_rows(path: Path) -> "tuple[list[str], list[list[float]]]":
    text = path.read_text(encoding="latin-1")
    cal = text[re.search(r"^CAL[ \t]*$", text, re.M).start():]
    fields = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\n\s*END_DATA_FORMAT",
                       cal, re.S).group(1).split()
    data = re.search(r"BEGIN_DATA\s*\n(.*?)\n\s*END_DATA\b", cal, re.S).group(1)
    rows = [[float(t) for t in ln.split()] for ln in data.splitlines() if ln.strip()]
    return fields, rows


def _colorants(ti1: Path) -> "tuple[str, list[str]]":
    """(COLOR_REP, channel letters) of a targen chart, e.g. CMYKOG -> C..G."""
    from workflow import printer_calibration as pc
    fields, _rows, kw = pc.read_table(ti1)
    rep = kw["COLOR_REP"]
    pre = rep.lstrip("i")
    return rep, [f[len(pre) + 1:] for f in fields if f.startswith(pre + "_")]


def _chart(tmp: Path, *, targen_d: str, cal_flag: str) -> Path:
    targen, printtarg = _tool("targen"), _tool("printtarg")
    base = tmp / "chart"
    subprocess.run([targen, "-v0", f"-d{targen_d}", "-f30", str(base)],
                   check=True, capture_output=True, cwd=tmp, timeout=120)
    rep, chans = _colorants(base.with_suffix(".ti1"))
    cal = tmp / "printer.cal"
    _write_cal(cal, rep, chans)
    subprocess.run([printtarg, "-v0", "-ii1", "-pA4", "-r", cal_flag, str(cal),
                    str(base)], check=True, capture_output=True, cwd=tmp,
                   timeout=120)
    assert _cal_rows(base.with_suffix(".ti2"))[1], "printtarg embedded no CAL"
    return base


def _xyz_for(row: "dict[str, str]") -> "tuple[float, float, float]":
    """A plausible reading for a patch.

    targen gives a CMYK chart no expected XYZ, so for CMYK a crude
    subtractive ink model stands in (monotonic in every channel, which is all
    colprof needs); every other chart here carries targen's own estimate."""
    def lin(v: float) -> float:
        return 0.03 + 0.97 * v
    if "XYZ_X" in row:
        return float(row["XYZ_X"]), float(row["XYZ_Y"]), float(row["XYZ_Z"])
    if "CMYK_C" in row:
        c, m, y, k = (float(row[f"CMYK_{ch}"]) / 100.0 for ch in "CMYK")
        r, g, b = lin((1 - c) * (1 - k)), lin((1 - m) * (1 - k)), lin((1 - y) * (1 - k))
    else:
        r, g, b = (lin(float(row[f"RGB_{ch}"]) / 100.0) ** 2.2 for ch in "RGB")
    return (100 * (0.4124 * r + 0.3576 * g + 0.1805 * b),
            100 * (0.2126 * r + 0.7152 * g + 0.0722 * b),
            100 * (0.0193 * r + 0.1192 * g + 0.9505 * b))


def _write_replay(ti2: Path, out: Path) -> None:
    from workflow import printer_calibration as pc
    _fields, rows, kw = pc.read_table(ti2)
    strips: "dict[str, list[tuple[int, tuple[float, float, float]]]]" = {}
    for row in rows.values():
        loc = row["SAMPLE_LOC"]
        letter = "".join(ch for ch in loc if ch.isalpha())
        num = int("".join(ch for ch in loc if ch.isdigit()))
        strips.setdefault(letter, []).append((num, _xyz_for(row)))
    steps = int(kw["STEPS_IN_PASS"])
    paper = _xyz_for({"RGB_R": "100", "RGB_G": "100", "RGB_B": "100"})
    with out.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        for letter in sorted(strips, key=lambda t: (len(t), t)):
            fp.write(f"STRIP {letter}\n")
            vals = [xyz for _n, xyz in sorted(strips[letter])]
            vals += [paper] * (steps - len(vals))    # a short last strip
            for x, y, z in vals:
                fp.write(f"{x:.4f} {y:.4f} {z:.4f}\n")


def _measure(base: Path) -> Path:
    replay = base.parent / "replay.txt"
    _write_replay(base.with_suffix(".ti2"), replay)
    with ReplaySession(base, replay) as s:
        ev = s.wait_event("session_start", timeout=30)
        for _ in ev["strips"]:
            idx = s.event_index()
            s.wait_event("strip_ready", timeout=30)
            s.send(cmd="swipe")
            s.wait_event("saved", timeout=30, after=idx)
        s.send(cmd="done")
        s.wait_event("done", timeout=30)
        assert s.finish(timeout=30) == 0
    ti3 = base.with_suffix(".ti3")
    assert ti3.is_file()
    return ti3


def _argyll_reads_back(ti3: Path, targen_d: str) -> None:
    """Argyll's own CAL reader (xcal, via printtarg -K) must get the same
    curves out of the .ti3's table.

    This is the check that matters past four inks. CMYK_C and RGB_R are
    standard CGATS fields, so a nan there fails loudly (colprof's "unexpected
    type"). CMYKOG_C is not: cgats keeps nan as a string, xcal reads it as a
    double anyway, and every curve silently comes out 0 (measured 2026-10-03
    on the unpatched helper). colprof cannot profile more than four inks at
    all, so it cannot stand in for this."""
    tmp = ti3.parent / "readback"
    tmp.mkdir()
    text = ti3.read_text(encoding="latin-1")
    cal = tmp / "from_ti3.cal"
    cal.write_text(text[re.search(r"^CAL[ \t]*$", text, re.M).start():],
                   encoding="latin-1")
    probe = tmp / "probe"
    subprocess.run([_tool("targen"), "-v0", f"-d{targen_d}", "-f20", str(probe)],
                   check=True, capture_output=True, cwd=tmp, timeout=120)
    subprocess.run([_tool("printtarg"), "-v0", "-ii1", "-pA4", "-K", str(cal),
                    str(probe)], check=True, capture_output=True, cwd=tmp,
                   timeout=120)
    f_src, src = _cal_rows(ti3)
    f_back, back = _cal_rows(probe.with_suffix(".ti2"))
    assert f_back == f_src
    off = [(a, b) for a, b in zip(src, back)
           if not all(math.isclose(x, y, abs_tol=1e-5) for x, y in zip(a, b))]
    assert not off, (f"Argyll read {len(off)} of {len(src)} CAL rows of the "
                     f".ti3 differently, e.g. wrote {off[-1][0]} read {off[-1][1]}")


@pytest.mark.skipif(not HELPER.exists(), reason="chromiq-chartread helper not built")
@pytest.mark.parametrize("targen_d, cal_flag, colprof_can", [
    ("4", "-K", True),     # CMYK: the forum case
    ("2", "-I", True),     # iRGB, included rather than applied
    ("5", "-K", True),     # CMY
    ("9", "-K", False),    # CMYK + orange + green: 6 inks, colprof has no profile for it
], ids=["cmyk-K", "irgb-I", "cmy-K", "cmykog-K"])
def test_the_engine_copies_the_charts_calibration_as_numbers(
        tmp_path, targen_d, cal_flag, colprof_can):
    base = _chart(tmp_path, targen_d=targen_d, cal_flag=cal_flag)
    ti3 = _measure(base)

    f2, rows2 = _cal_rows(base.with_suffix(".ti2"))
    f3, rows3 = _cal_rows(ti3)
    assert f3 == f2
    assert len(rows3) == len(rows2) == 256
    bad = [r3 for r3 in rows3 if not all(math.isfinite(v) for v in r3)]
    assert not bad, (f"{len(bad)} of 256 CAL rows in the .ti3 are not numbers, "
                     f"e.g. {bad[-1]}: the rspl1.c grid-index fault")
    # NOT max(abs(a - b)): every comparison with nan is False, so a max over
    # nan differences quietly comes out as the first finite one.
    off = [(r2, r3) for r2, r3 in zip(rows2, rows3)
           if not all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(r2, r3))]
    assert not off, f"{len(off)} CAL rows differ from the .ti2's, e.g. {off[0]}"

    from workflow import printer_calibration as pc
    assert pc.cal_table_is_numeric(pc._raw_cal_text(ti3))

    if colprof_can:
        r = subprocess.run([_tool("colprof"), "-v0", "-qf", "-al", base.name],
                           cwd=tmp_path, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        assert r.returncode == 0, f"colprof refused the .ti3:\n{r.stdout}{r.stderr}"
        assert base.with_suffix(".icc").is_file()
    else:
        _argyll_reads_back(ti3, targen_d)


# ---------------------------------------------------------------------------
# Older .ti3 files: a nan table is absent, the .ti2's is used
# ---------------------------------------------------------------------------

def _cgats_with_cal(path: Path, cal_value: str) -> None:
    body = ("CTI3\n\nNUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R\n"
            "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 50.0\nEND_DATA\n\n"
            "CAL\n\nDEVICE_CLASS \"OUTPUT\"\nCOLOR_REP \"RGB\"\n\n"
            "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\nRGB_I RGB_R RGB_G RGB_B\n"
            "END_DATA_FORMAT\nNUMBER_OF_SETS 2\nBEGIN_DATA\n"
            f"0.0 {cal_value} {cal_value} {cal_value}\n"
            f"1.0 {cal_value} {cal_value} {cal_value}\nEND_DATA\n")
    path.write_text(body, encoding="ascii")


@pytest.mark.parametrize("bad", ["nan", "-nan", "-nan(ind)", "inf"])
def test_a_non_numeric_ti3_table_falls_back_to_the_ti2(tmp_path, caplog, bad):
    from workflow import printer_calibration as pc
    ti3, ti2 = tmp_path / "m.ti3", tmp_path / "m.ti2"
    _cgats_with_cal(ti3, bad)
    _cgats_with_cal(ti2, "0.5")
    before = (ti3.read_bytes(), ti2.read_bytes())

    assert pc.embedded_cal_text(ti3) == ""
    assert not pc.has_embedded_cal(ti3)
    run = SimpleNamespace(measurement_ti3=ti3, chart_ti2=ti2)
    with caplog.at_level(logging.WARNING):
        assert pc.run_cal_source(run) == ti2
    assert any("not numbers" in r.getMessage() and "m.ti2" in r.getMessage()
               for r in caplog.records), "no log line names the fallback"
    assert pc.extract_cal(ti3, tmp_path / "x.cal") is None
    assert (ti3.read_bytes(), ti2.read_bytes()) == before, "a file was written"


def test_a_numeric_ti3_table_is_still_preferred(tmp_path):
    from workflow import printer_calibration as pc
    ti3, ti2 = tmp_path / "m.ti3", tmp_path / "m.ti2"
    _cgats_with_cal(ti3, "0.25")
    _cgats_with_cal(ti2, "0.5")
    assert pc.run_cal_source(SimpleNamespace(measurement_ti3=ti3, chart_ti2=ti2)) == ti3


def test_both_tables_nan_is_no_calibration(tmp_path):
    from workflow import printer_calibration as pc
    ti3, ti2 = tmp_path / "m.ti3", tmp_path / "m.ti2"
    _cgats_with_cal(ti3, "nan")
    _cgats_with_cal(ti2, "nan")
    assert pc.run_cal_source(SimpleNamespace(measurement_ti3=ti3, chart_ti2=ti2)) is None
