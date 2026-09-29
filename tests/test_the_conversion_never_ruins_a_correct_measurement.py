"""The owner's question about the measurement import, answered as a test.

    *"are you sure this adjustments to the measurement import / conversion
    causes no regressions? a conversion happened before this already, how does
    the app know when it should use what kind of conversion."*  — Basti,
    2026-09-11

The 2026-09-11 import round taught ChromIQ to put right an i1Profiler export
whose XYZ columns arrive on the 0..1 reflectance-factor scale instead of the
0..100 one ArgyllCMS means. It decided on ONE NUMBER: the largest XYZ anywhere
in the file, against a ceiling of 1.5. That is a guess, and this file is what
found where the guess is wrong and what replaced it.

**IT RUINED A CORRECT MEASUREMENT, AND ARGYLLCMS HELPED.** Measured with the
real ``/Applications/Argyll/bin/txt2ti3`` (case D below): a chart with no light
patch in it — a rich-black / Dmax comparison set, which ChromIQ's own
``patch_generators_nd.rich_black_ramp`` builds — converts to a ``.ti3`` whose
XYZ columns are RIGHT and whose peak is 1.3068, under the ceiling. The old rule
multiplied every correct number by 100 and wrote the file back.

And the spectral columns of that same file cannot arbitrate, which is the whole
reason this is not solved by a consistency check: ``txt2ti3`` guesses the
SPECTRAL scale with a test of exactly the same shape (``profile/txt2ti3.c``
~L714, ``if (maxv < 10.0) spec_scale = 100.0``), so on a dark chart it turns a
correct 1.2 % into 120 % — and a spectral-vs-XYZ ratio would have read 100 and
agreed with the threshold, just as wrongly.

So the rule now needs a WITNESS, and a file that carries none is left alone:

1. **the bare paper** — the patch printed with no ink. No printable medium is
   black, so its Y cannot sit at or below 1.5 (L\\* 12.6). A file whose no-ink
   patch is also its lightest patch and reads inside the band is on the wrong
   scale and cannot be anything else;
2. **the spectral columns**, when their own peak is at or below 110 % and they
   are therefore still on the percent scale txt2ti3 can write without guessing;
3. otherwise nothing is said and nothing is written.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.reference_convert import (                           # noqa: E402
    _table, _xyz_scale_verdict, cie_columns_are_unscaled,
    finalize_converted_ti3, repair_converted_cie)

_ARGYLL = Path("/Applications/Argyll/bin")
_needs_argyll = pytest.mark.skipif(
    not (_ARGYLL / "txt2ti3").is_file(),
    reason="ArgyllCMS is not installed here")

_REPO = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# fixtures: a .ti3 of any shape, and an i1Profiler export of any shape
# ---------------------------------------------------------------------------

_N_BANDS = 5


def ti3(rows, *, cie=False, cie_scale=1.0, lab=False, spectral=False,
        device_class="OUTPUT", eol="\n", bom="") -> str:
    """*rows* = ``[(device_0_100, Y_on_0_100, [reflectance %])]``."""
    fields = ["SAMPLE_ID", "SAMPLE_LOC", "RGB_R", "RGB_G", "RGB_B"]
    if cie:
        fields += ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    if lab:
        fields += ["LAB_L", "LAB_A", "LAB_B"]
    if spectral:
        fields += [f"SPEC_{380 + 10 * i}" for i in range(_N_BANDS)]
    body = []
    for i, (dev, y, refl) in enumerate(rows, 1):
        c = [str(i), f'"A{i}"', f"{dev:.4f}", f"{dev:.4f}", f"{dev:.4f}"]
        if cie:
            c += [f"{y * k * cie_scale:.6f}" for k in (0.9505, 1.0, 1.089)]
        if lab:
            ll = (116 * (y / 100.0) ** (1 / 3.0) - 16 if y / 100.0 > 0.008856
                  else 903.3 * y / 100.0)
            c += [f"{ll:.4f}", "0.0000", "0.0000"]
        if spectral:
            c += [f"{v:.4f}" for v in refl]
        body.append(" ".join(c))
    return bom + (
        f'CTI3   {eol}{eol}DESCRIPTOR "x"{eol}DEVICE_CLASS "{device_class}"{eol}'
        f'COLOR_REP "iRGB_XYZ"{eol}{eol}NUMBER_OF_FIELDS {len(fields)}{eol}'
        f'BEGIN_DATA_FORMAT{eol}{" ".join(fields)}{eol}END_DATA_FORMAT{eol}'
        f'{eol}NUMBER_OF_SETS {len(body)}{eol}BEGIN_DATA{eol}'
        + eol.join(body) + f"{eol}END_DATA{eol}")


def rows(ys, *, paper=True):
    """A chart's rows. The first is BARE PAPER (device 100/100/100) unless
    *paper* is False — a set of nothing but rich blacks has no such patch."""
    top = max(ys) or 1.0
    out = []
    for i, y in enumerate(ys):
        dev = 100.0 if (paper and i == 0) else 92.0 * (y / top) ** 0.45
        out.append((dev, y, [y * f for f in (0.98, 0.99, 1.0, 1.01, 1.02)]))
    return out


BRIGHT = rows([88.0, 50.0, 18.0, 0.9])                  # an ordinary chart
DARK = rows([1.2, 0.8, 0.4, 0.1], paper=False)          # a rich-black set


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _write(tmp_path: Path, text: str, name="m.ti3") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8", newline="")
    return p


# ---------------------------------------------------------------------------
# 1 · the inventory — every shape, and what it gets
# ---------------------------------------------------------------------------

# (name, the file, does the repair fire?)
_INVENTORY = [
    ("XYZ on 0..100, an ordinary chart", ti3(BRIGHT, cie=True), False),
    ("XYZ on 0..1, the fault", ti3(BRIGHT, cie=True, cie_scale=0.01), True),
    ("Lab only", ti3(BRIGHT, lab=True), False),
    ("XYZ on 0..100 with spectral", ti3(BRIGHT, cie=True, spectral=True), False),
    ("XYZ on 0..1 with spectral", ti3(BRIGHT, cie=True, cie_scale=0.01,
                                      spectral=True), True),
    ("XYZ on 0..100 with Lab", ti3(BRIGHT, cie=True, lab=True), False),
    ("XYZ on 0..1 with Lab", ti3(BRIGHT, cie=True, cie_scale=0.01, lab=True),
     True),
    ("a dim emissive read", ti3([(100.0, 1.2, []), (50.0, 0.4, [])], cie=True,
                                device_class="DISPLAY"), False),
    ("a rich-black set, correctly scaled", ti3(DARK, cie=True), False),
    ("a rich-black set with spectral", ti3(DARK, cie=True, spectral=True),
     False),
    ("a rich-black set with Lab", ti3(DARK, cie=True, lab=True), False),
    ("one row, bare paper on 0..100", ti3(BRIGHT[:1], cie=True), False),
    ("one row, bare paper on 0..1", ti3(BRIGHT[:1], cie=True, cie_scale=0.01),
     True),
    ("one row, a single black patch", ti3(rows([0.35], paper=False), cie=True),
     False),
    ("no rows at all", ti3([], cie=True), False),
    ("numbers that are not numbers",
     ti3(BRIGHT, cie=True, cie_scale=0.01).replace("0.836440", "n/a"), False),
    ("a UTF-8 byte-order mark",
     ti3(BRIGHT, cie=True, cie_scale=0.01, bom="﻿"), True),
    ("CRLF line endings, on 0..1",
     ti3(BRIGHT, cie=True, cie_scale=0.01, eol="\r\n"), True),
    ("CRLF line endings, on 0..100", ti3(BRIGHT, cie=True, eol="\r\n"), False),
    ("not a CGATS file at all", "hello, I am not a measurement\n", False),
]


@pytest.mark.parametrize("name,text,repairs",
                         _INVENTORY, ids=[c[0] for c in _INVENTORY])
def test_the_inventory(tmp_path, name, text, repairs):
    """Every input shape, through the repair and through the warning."""
    p = _write(tmp_path, text)
    before = _sha(p)
    note = repair_converted_cie(p, _ARGYLL)
    assert bool(note) is repairs, f"{name}: {note!r}"
    assert (_sha(p) != before) is repairs, f"{name}: the file changed anyway"

    q = _write(tmp_path, text, "w.ti3")
    was = _sha(q)
    assert cie_columns_are_unscaled(q) is repairs, name
    assert _sha(q) == was, f"{name}: the READING wrote to the file"


@pytest.mark.parametrize("short", [True, False])
def test_a_ragged_row_stops_everything(tmp_path, short):
    """The rewrite works by column POSITION, so a row that does not hold every
    column must stop it dead rather than be indexed into (short) or have its
    columns read one place along (long)."""
    lines = ti3(BRIGHT, cie=True, cie_scale=0.01).splitlines()
    at = next(i for i, ln in enumerate(lines) if ln.startswith('4 "A4"'))
    lines[at] = '4 "A4" 0.9000' if short else lines[at] + " 99.0"
    p = _write(tmp_path, "\n".join(lines) + "\n")
    before = p.read_bytes()

    assert repair_converted_cie(p, _ARGYLL) == ""     # and does not raise
    assert p.read_bytes() == before
    assert cie_columns_are_unscaled(p) is False


def test_the_warning_and_the_repair_are_never_about_different_files(tmp_path):
    """One verdict, asked once. A user warned about a file must be able to fix
    it by importing again, and a file nobody warned about must not be rewritten
    behind their back."""
    for name, text, repairs in _INVENTORY:
        p = _write(tmp_path, text)
        warned = cie_columns_are_unscaled(p)
        repaired = bool(repair_converted_cie(p, _ARGYLL))
        assert warned is repaired, name


# ---------------------------------------------------------------------------
# 2 · the false positive, with the real ArgyllCMS
# ---------------------------------------------------------------------------

_BANDS = [380 + 10 * i for i in range(36)]


def _export(ys, *, xyz_scale, spectral=True) -> str:
    """An i1Profiler CGATS measurement export, the file txt2ti3 reads."""
    f = ["SampleID", "RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z"]
    if spectral:
        f += [f"SPECTRAL_NM_{b}" for b in _BANDS]
    out = ["CGATS.17", "", 'ORIGINATOR "i1Profiler"',
           'CREATED "July 19, 2026"', 'INSTRUMENTATION "i1Pro 2"', "",
           f"NUMBER_OF_FIELDS {len(f)}", "BEGIN_DATA_FORMAT", "\t".join(f),
           "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(ys)}", "BEGIN_DATA"]
    # THE DEVICE RAMP IS ABSOLUTE, NOT NORMALISED TO THE SET'S OWN TOP. A
    # rich-black set's patches carry LOW device values — that is what makes it
    # a rich-black set — and a fixture that rescales them until its darkest
    # chart still holds a 255/255/255 patch would be a chart of black paper,
    # which is not the thing being tested (and which the paper anchor would be
    # right to call out).
    for i, y in enumerate(ys, 1):
        dev = 255.0 * min(1.0, y / 88.0) ** 0.45
        c = [str(i)] + [f"{dev:.4f}"] * 3
        c += [f"{y * k * xyz_scale:.6f}" for k in (0.9505, 1.0, 1.089)]
        if spectral:
            # in PERCENT, which is what i1Profiler exports.
            c += [f"{y:.6f}"] * len(_BANDS)
        out.append("\t".join(c))
    return "\n".join(out + ["END_DATA", ""])


def _txt2ti3(tmp_path: Path, text: str) -> Path:
    src = tmp_path / "e.txt"
    src.write_text(text, encoding="utf-8")
    # A loaded gate saturates every core; budget for that, not for an idle
    # machine, and say "did not finish" rather than let it read as a crash.
    try:
        r = subprocess.run([str(_ARGYLL / "txt2ti3"), str(src), str(tmp_path / "o")],
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8")
    except subprocess.TimeoutExpired:                      # pragma: no cover
        pytest.fail("txt2ti3 did not finish inside 180 s")
    assert r.returncode == 0, r.stderr or r.stdout
    out = tmp_path / "o.ti3"
    assert out.is_file()
    return src, out


@_needs_argyll
def test_a_rich_black_set_survives_the_import(tmp_path):
    """THE FALSE POSITIVE, end to end. A correct measurement of a chart with no
    light patch, converted by the real txt2ti3 and finalised by ChromIQ."""
    src, out = _txt2ti3(tmp_path, _export([1.2, 0.9, 0.6, 0.35, 0.1],
                                          xyz_scale=1.0))
    fields = out.read_text(encoding="utf-8").split("BEGIN_DATA_FORMAT\n")[1].splitlines()[0].split()
    row = out.read_text(encoding="utf-8").split("BEGIN_DATA\n")[1].splitlines()[0].split()
    y = float(row[fields.index("XYZ_Y")])
    assert y == pytest.approx(1.2, abs=1e-3), "fixture is not the dark set"
    assert y <= 1.5, "fixture does not reach into the old rule's band"
    # ArgyllCMS's own guess has already inflated the spectral columns here,
    # which is why they cannot be asked.
    assert float(row[fields.index("SPEC_550")]) > 110.0

    before = _sha(out)
    finalize_converted_ti3(out, src, _ARGYLL)

    kept = out.read_text(encoding="utf-8").split("BEGIN_DATA\n")[1].splitlines()[0].split()
    assert float(kept[fields.index("XYZ_Y")]) == pytest.approx(1.2, abs=1e-3)
    assert cie_columns_are_unscaled(out) is False
    assert before  # the instrument/date stamps are allowed to change the file


@_needs_argyll
def test_the_reported_fault_is_still_put_right(tmp_path):
    """And the case the repair exists for still works: her export, whose XYZ
    columns arrive on the 0..1 scale with the paper white at 0.88."""
    src, out = _txt2ti3(tmp_path, _export([88.0, 50.0, 18.0, 4.0, 0.9],
                                          xyz_scale=0.01))
    assert cie_columns_are_unscaled(out) is True

    finalize_converted_ti3(out, src, _ARGYLL)

    fields = out.read_text(encoding="utf-8").split("BEGIN_DATA_FORMAT\n")[1].splitlines()[0].split()
    row = out.read_text(encoding="utf-8").split("BEGIN_DATA\n")[1].splitlines()[0].split()
    assert float(row[fields.index("XYZ_Y")]) == pytest.approx(88.0, abs=1e-2)
    assert cie_columns_are_unscaled(out) is False


# ---------------------------------------------------------------------------
# 3 · the second witness, on its own
# ---------------------------------------------------------------------------

def test_a_partial_measurement_is_judged_by_its_own_spectra(tmp_path):
    """No bare-paper patch, but spectral columns still on the percent scale:
    the spectra say the lightest patch reflects 88 % where the XYZ column says
    0.88, and a hundred is not a rounding error."""
    p = _write(tmp_path, ti3(rows([88.0, 50.0, 18.0], paper=False), cie=True,
                             cie_scale=0.01, spectral=True))
    assert cie_columns_are_unscaled(p) is True
    assert "0..1 scale" in repair_converted_cie(p, _ARGYLL)


def test_spectra_that_txt2ti3_inflated_are_not_asked(tmp_path):
    """The same shape, with the spectral columns above 110 % — which only
    txt2ti3's own x100 can produce. They are not evidence and are not used."""
    inflated = [(d, y, [v * 100.0 for v in r]) for d, y, r in DARK]
    p = _write(tmp_path, ti3(inflated, cie=True, spectral=True))
    before = p.read_bytes()
    assert cie_columns_are_unscaled(p) is False
    assert repair_converted_cie(p, _ARGYLL) == ""
    assert p.read_bytes() == before


def test_with_no_witness_at_all_nothing_is_decided(tmp_path):
    """A set with no paper patch and no spectra. It may well be on the wrong
    scale, and ChromIQ still says nothing: a guess that can destroy a correct
    measurement is worth less than silence."""
    p = _write(tmp_path, ti3(rows([88.0, 50.0], paper=False), cie=True,
                             cie_scale=0.01))
    before = p.read_bytes()
    assert cie_columns_are_unscaled(p) is False
    assert repair_converted_cie(p, _ARGYLL) == ""
    assert p.read_bytes() == before


def test_a_no_ink_patch_that_is_not_the_lightest_decides_nothing(tmp_path):
    """The anchor is "bare paper is the lightest thing on the sheet", not
    "there is a bare-paper row somewhere". One misread paper patch — the head
    slipping onto its neighbour, a fingerprint, a chart on black media — must
    not authorise rewriting every patch in the file."""
    r = rows([88.0, 50.0, 18.0], paper=True)
    r[0] = (100.0, 4.0, r[0][2])            # the no-ink patch reads DARK
    p = _write(tmp_path, ti3(r, cie=True, cie_scale=0.01))
    before = p.read_bytes()

    assert cie_columns_are_unscaled(p) is False
    assert repair_converted_cie(p, _ARGYLL) == ""
    assert p.read_bytes() == before


def test_instrument_noise_around_the_paper_patch_still_decides(tmp_path):
    """…and the other half of the same rule: a near-white ink patch reading a
    whisker above the paper is noise, not a different chart. 2 % of the peak
    still counts as "the paper is the lightest patch"."""
    r = rows([88.0, 50.0, 18.0], paper=True)
    r.insert(1, (99.0, 89.5, r[0][2]))      # a 99-%-white patch, 2 % brighter
    p = _write(tmp_path, ti3(r, cie=True, cie_scale=0.01))

    assert cie_columns_are_unscaled(p) is True
    assert "0..1 scale" in repair_converted_cie(p, _ARGYLL)


def test_an_emissive_measurement_is_never_judged(tmp_path):
    """"No ink" means nothing on a display, and a display really can be this
    dim. Only DEVICE_CLASS "OUTPUT" is judged at all."""
    for cls in ("DISPLAY", "INPUT", "EMISSION"):
        p = _write(tmp_path, ti3([(100.0, 1.2, []), (50.0, 0.4, [])],
                                 cie=True, device_class=cls))
        before = p.read_bytes()
        assert cie_columns_are_unscaled(p) is False, cls
        assert repair_converted_cie(p, _ARGYLL) == "", cls
        assert p.read_bytes() == before, cls


# ---------------------------------------------------------------------------
# 4 · no regression on anything that already worked
# ---------------------------------------------------------------------------

def _every_measurement_in_the_tree():
    for p in sorted(_REPO.rglob("*")):
        if (p.suffix.lower() in (".ti3", ".cie", ".ti1", ".ti2")
                and p.is_file() and ".venv" not in p.parts
                and ".git" not in p.parts):
            yield p


def test_every_measurement_this_repository_holds_is_left_alone(tmp_path):
    """The owner's question, restated. A conversion happened before this change
    and people have been using it: every measurement file in the tree — the
    demo projects, the golden project, the fixtures — must come back BYTE FOR
    BYTE, and must not be accused."""
    seen = 0
    for src in _every_measurement_in_the_tree():
        seen += 1
        dst = tmp_path / f"m{src.suffix}"
        shutil.copy2(src, dst)
        before = dst.read_bytes()
        note = repair_converted_cie(dst, _ARGYLL)
        assert note == "", f"{src}: {note}"
        assert dst.read_bytes() == before, f"{src} was rewritten"
        assert cie_columns_are_unscaled(dst) is False, f"{src} was accused"
    assert seen > 50, f"only {seen} measurement files found — did the glob break?"


def test_the_demo_projects_the_gate_builds_are_left_alone(tmp_path,
                                                          demo_projects_root):
    """The same, for the projects the gate builds with the real ArgyllCMS."""
    seen = 0
    for src in sorted(Path(demo_projects_root).rglob("*.ti3")):
        seen += 1
        dst = tmp_path / "m.ti3"
        shutil.copy2(src, dst)
        before = dst.read_bytes()
        assert repair_converted_cie(dst, _ARGYLL) == "", src
        assert dst.read_bytes() == before, src
        assert cie_columns_are_unscaled(dst) is False, src
    assert seen > 5, f"only {seen} demo measurements found"


# ---------------------------------------------------------------------------
# 5 · the third door, and the ArgyllCMS folder it reads
# ---------------------------------------------------------------------------

def test_all_three_convert_doors_go_through_the_one_finalise_step():
    """Tools → Convert i1Profiler → TI3, the Build Profile .txt import and the
    scanner-target import all call ``finalize_converted_ti3``, so the scale
    question is asked once and answered the same way whichever door was used."""
    import inspect

    from ui.dialogs import tools_dialogs
    from ui.tabs import tab_profile
    from workflow import reference_convert

    for mod in (tools_dialogs, tab_profile, reference_convert):
        assert "finalize_converted_ti3" in inspect.getsource(mod), mod.__name__


def test_a_blank_argyllcms_setting_is_never_a_folder_full_of_tools(tmp_path):
    """``settings.get`` falls back only when the KEY IS ABSENT, so a stored
    empty string comes straight through and ``Path("")`` is the CURRENT
    DIRECTORY. The repair must treat that as "no ArgyllCMS", not as a folder."""
    spectral_only = ti3(BRIGHT, spectral=True)          # would need spec2cie
    for blank in ("", "   ", None):
        p = _write(tmp_path, spectral_only)
        before = p.read_bytes()
        assert repair_converted_cie(p, blank) == "", repr(blank)
        assert p.read_bytes() == before, repr(blank)


# ---------------------------------------------------------------------------
# 6 · the verdict function itself
# ---------------------------------------------------------------------------

def test_no_verdict_is_a_third_answer_and_not_a_false(tmp_path):
    """``_xyz_scale_verdict`` answers None when it cannot know, and both
    callers read None as "say nothing". A bool would have collapsed "this file
    is fine" into "I have no idea", which is how the first version got here."""
    unknown = ti3(rows([88.0, 50.0], paper=False), cie=True, cie_scale=0.01)
    verdict, peak = _xyz_scale_verdict(*_table(unknown))
    assert verdict is None and peak > 0

    fine = ti3(BRIGHT, cie=True)
    assert _xyz_scale_verdict(*_table(fine))[0] is False

    faulty = ti3(BRIGHT, cie=True, cie_scale=0.01)
    assert _xyz_scale_verdict(*_table(faulty))[0] is True
