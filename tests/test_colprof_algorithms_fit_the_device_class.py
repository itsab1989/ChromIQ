"""A `-a` letter colprof HAS is not a `-a` letter this measurement can USE.

Knut, on v4.1.5-beta.11's release note:

    "'Matrix only (forced)' … ArgyllCMS's colprof has no such setting"

He was right that the sentence is wrong, and the fault under it is larger than
the sentence. Beta 11 checked the letters against colprof's `-a` **parser** and
removed the one letter that never existed. But the parser reads `-a` long
before the measurement is opened, so all ten of its letters parse, and what
decides whether one can be used is the `DEVICE_CLASS` in the `.ti3`:

    colprof.c:1244-1246, the OUTPUT branch
        else if (ptype != prof_clutLab && ptype != prof_clutXYZ)
            error ("Output profile can only be a cLUT algorithm");

MEASURED against ArgyllCMS 3.5.0 on a real printer measurement: of the eight
entries the Build Profile tab offered, `g G s S m` all exited 1 having written
no profile, and `X` wrote a file BIT-IDENTICAL to `x` because the OUTPUT call
site passes `mtxtoo` as a hard-coded 0 (`colprof.c:1256`). Nothing in
`_COLPROF_ERROR_PATTERNS` matched that error line either, so the failure was
exactly what the beta 11 note described for the phantom `M`: no profile, no
window, one line in a log.

So this file checks the thing the previous test could not express: **every `-a`
letter a window offers is legal for the DEVICE CLASS that window builds**, with
the legal sets DERIVED from colprof's own three device-class branches rather
than transcribed, and with a slow tier that runs the real binary and demands a
real `.icc` for every letter still on offer.

Three windows, and they do not build the same thing:

* Build Profile, Guided and Manual  -> `DEVICE_CLASS "OUTPUT"`
* the scanner/camera window, tick ON  -> `DEVICE_CLASS "OUTPUT"`
* the scanner/camera window, tick OFF -> `DEVICE_CLASS "INPUT"`
"""
from __future__ import annotations

import inspect
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import profile_builder as PB                  # noqa: E402

from tests.argyll_env import argyll_tool                    # noqa: E402

#: Same location, and the same skip, as `test_printtarg_argument_vocabulary`.
ARGYLL_SRC = Path("/Users/Basti/Downloads/Argyll_V3.5.0_orig")
ROOT = Path(__file__).resolve().parent.parent


def _colprof_c() -> str:
    src = ARGYLL_SRC / "profile" / "colprof.c"
    if not src.is_file():
        pytest.skip(f"ArgyllCMS sources not on this machine ({src})")
    return src.read_text(encoding="utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# 1. the legal set per device class, DERIVED from colprof.c
# ---------------------------------------------------------------------------
def _letter_to_ptype(text: str) -> "dict[str, str]":
    """`{-a letter: the prof_* enum it selects}` out of colprof's own switch.

    Read from the parser, never from the usage text, for the reason
    `test_printtarg_argument_vocabulary` gives: the usage text is the half that
    can be wrong (it omits `L` entirely).
    """
    start = text.index("Expect argument to algorithm flag -a")
    block = text[start:text.index("Unknown argument '%c' to algorithm flag",
                                  start)]
    out: "dict[str, str]" = {}
    pending: "list[str]" = []
    for line in block.splitlines():
        m = re.match(r"\s*case '(.)':", line)
        if m:
            pending.append(m.group(1))
            continue
        m = re.match(r"\s*ptype\s*=\s*(\w+);", line)
        if m and pending:
            for letter in pending:
                out[letter] = m.group(1)
            pending = []
    return out


def _branch(text: str, device_class: str) -> str:
    """The body of colprof's `if (… DEVICE_CLASS == "<class>")` branch."""
    marker = f'kdata[dti],"{device_class}") == 0'
    # The last occurrence: the same strings appear earlier, in the code that
    # decides whether a display .ti3 may carry spectral data.
    start = text.rindex(marker)
    ends = [text.find(f'kdata[dti],"{c}") == 0', start)
            for c in ("OUTPUT", "INPUT", "DISPLAY")]
    ends = [e for e in ends if e > start]
    stop = min(ends) if ends else text.index(
        "DEVICE_CLASS has unknown value", start)
    return text[start:stop]


def _legal_letters(text: str, device_class: str) -> "set[str]":
    """Which letters that branch permits, by reading its own guard.

    A branch that refuses algorithms does it with one `ptype != <enum>` chain
    in front of an `error(...)`; a branch with no such chain permits every
    letter the switch above accepts.
    """
    letters = _letter_to_ptype(text)
    body = _branch(text, device_class)
    # The condition must be the ptype chain and NOTHING ELSE. The INPUT branch
    # carries `if (clipovwp && ptype != prof_clutLab && ptype != prof_clutXYZ)`,
    # which refuses a COMBINATION and not an algorithm: -as is perfectly legal
    # for a scanner, it is -as WITH -uc that is not. A looser regex read that
    # as "an input profile can only be a cLUT" and was wrong about the whole
    # scanner side of the window.
    m = re.search(r"\bif\s*\(\s*(ptype\s*!=\s*\w+(?:\s*&&\s*ptype\s*!=\s*\w+)*)"
                  r"\s*\)\s*\{?\s*\n\s*error", body)
    if m is None:
        return set(letters)
    allowed = set(re.findall(r"ptype\s*!=\s*(\w+)", m.group(1)))
    return {ltr for ltr, enum in letters.items() if enum in allowed}


def test_the_device_class_table_is_colprofs_own_three_branches():
    """`COLPROF_ALGORITHMS_BY_DEVICE_CLASS` is not a transcription.

    Everything here comes out of colprof.c: the letter/enum mapping from the
    `-a` switch, and the permitted enums from each branch's own guard.
    """
    text = _colprof_c()
    for device_class in ("OUTPUT", "INPUT", "DISPLAY"):
        got = _legal_letters(text, device_class)
        assert got == set(PB.COLPROF_ALGORITHMS_BY_DEVICE_CLASS[device_class]), (
            f"colprof.c permits {sorted(got)} for {device_class}, "
            f"the table says "
            f"{sorted(PB.COLPROF_ALGORITHMS_BY_DEVICE_CLASS[device_class])}")


def test_an_output_profile_is_a_clut_or_it_is_nothing():
    """The one fact the whole change rests on, stated on its own so a failure
    names it rather than a table entry."""
    text = _colprof_c()
    assert "Output profile can only be a cLUT algorithm" in _branch(text, "OUTPUT")
    assert set(PB.COLPROF_ALGORITHMS_BY_DEVICE_CLASS["OUTPUT"]) < \
        set(PB.COLPROF_ALGORITHMS), "the OUTPUT set must be a strict subset"
    for letter in "gGsSm":
        assert letter not in PB.COLPROF_ALGORITHMS_BY_DEVICE_CLASS["OUTPUT"]


def test_every_device_class_the_table_names_exists_in_colprof():
    text = _colprof_c()
    for device_class in PB.COLPROF_ALGORITHMS_BY_DEVICE_CLASS:
        assert f'kdata[dti],"{device_class}") == 0' in text, device_class


def test_aX_and_aY_are_inert_in_an_output_profile():
    """Why `X` and `Y` are legal for a printer and still not offered.

    `X` and `Y` exist to set `mtxtoo`, and the OUTPUT call site passes a
    literal `0` for it while the DISPLAY one passes `mtxtoo` through. Read off
    the source, because "they made the same file" is a measurement that only
    holds for the one .ti3 it was made on, and this is the reason it holds for
    all of them.
    """
    text = _colprof_c()
    out = _branch(text, "OUTPUT")
    disp = _branch(text, "DISPLAY")
    assert re.search(r"make_output_icc\(ptype,\s*0,", out), (
        "the OUTPUT branch no longer hard-codes mtxtoo to 0 — -aX/-aY may "
        "now do something for a printer, and the offered list should say so")
    assert re.search(r"make_output_icc\(ptype,\s*mtxtoo,", disp)
    for letter in "XY":
        assert letter in PB.COLPROF_ALGORITHMS_BY_DEVICE_CLASS["OUTPUT"]
        assert letter not in PB.OUTPUT_ALGORITHM_CHOICES


# ---------------------------------------------------------------------------
# 2. what each window offers, read off that window
# ---------------------------------------------------------------------------
def _tab_profile_combos() -> "dict[str, list[tuple[str, str]]]":
    """The Guided and Manual Algorithm combos, as (letter, label) pairs.

    Read out of `tab_profile`'s own source rather than by building a whole
    `TabProfile`: both combos are an inline list right after an
    `"Algorithm (-a):"` label, which is how the beta 11 test reads them too.
    """
    from ui.tabs import tab_profile as TP
    src = inspect.getsource(TP)
    chunks = src.split('QLabel(tr("Algorithm (-a):")')[1:]
    assert len(chunks) == 2, (
        f"expected the Guided and the Manual algorithm combo, found "
        f"{len(chunks)} — this test has gone blind")
    out = {}
    for name, chunk in zip(("guided_or_manual_1", "guided_or_manual_2"), chunks):
        head = chunk[:chunk.index("]:")]
        pairs = re.findall(r'\(\s*"(.)",\s*"([^"]*)"\s*\)', head)
        assert pairs, f"no (letter, label) pairs found in {name}"
        out[name] = pairs
    return out


def _yaml_algorithm_row() -> dict:
    import yaml
    params = yaml.safe_load(
        (ROOT / "data" / "parameters.yaml").read_text(encoding="utf-8"))
    for entry in params["parameters"]["colprof"]:
        if entry.get("flag") == "-a":
            return entry
    raise AssertionError("no colprof -a row in parameters.yaml")


def _offered() -> "list[tuple[str, str, list[str]]]":
    """`(where, device class it builds, letters offered)` for every window."""
    from ui.dialogs import scanner_colprof as SC
    out = [(f"tab_profile {name}", "OUTPUT", [d for d, _ in pairs])
           for name, pairs in _tab_profile_combos().items()]
    out.append(("data/parameters.yaml colprof -a", "OUTPUT",
                list(_yaml_algorithm_row()["choices"])))
    out.append(("scanner window, printer tick ON", "OUTPUT",
                list(SC.PTYPE_CHOICES_BY_MODE[True])))
    out.append(("scanner window, printer tick OFF", "INPUT",
                list(SC.PTYPE_CHOICES_BY_MODE[False])))
    return out


def test_every_letter_a_window_offers_is_legal_for_what_that_window_builds():
    """THE RULE. `test_printtarg_argument_vocabulary`'s own words: "Either the
    tool accepts it, or the app must refuse it before spawning." It checked the
    letter set and passed while five entries could not build a profile,
    because the device class is what refuses them."""
    bad = []
    for where, device_class, letters in _offered():
        legal = PB.COLPROF_ALGORITHMS_BY_DEVICE_CLASS[device_class]
        for letter in letters:
            if letter not in legal:
                bad.append(f"{where} offers -a{letter}, which colprof refuses "
                           f"for a {device_class} profile")
    assert not bad, "\n  " + "\n  ".join(bad)


def test_no_window_offers_a_letter_colprof_does_not_have():
    """The beta 11 check, kept: the device-class rule is on TOP of it, not
    instead of it."""
    for where, _device_class, letters in _offered():
        bad = [ltr for ltr in letters if ltr not in PB.COLPROF_ALGORITHMS]
        assert not bad, f"{where} offers {bad}, which colprof has no case for"


def test_the_printer_windows_offer_exactly_the_letters_that_do_distinct_work():
    """Two, not five. `X` and `Y` are legal for a printer and produce the same
    file as `x`, so offering them is offering the same profile twice under
    three names, one of which promised a matrix that is not in the file."""
    for where, device_class, letters in _offered():
        if device_class != "OUTPUT":
            continue
        assert set(letters) == set(PB.OUTPUT_ALGORITHM_CHOICES), (
            f"{where} offers {sorted(letters)}, "
            f"OUTPUT_ALGORITHM_CHOICES says "
            f"{sorted(PB.OUTPUT_ALGORITHM_CHOICES)}")


def test_the_scanner_window_offers_all_four_types_off_the_printer_tick():
    """The other direction: the filter must not quietly eat the scanner side.
    Shaper + matrix is the DEFAULT there and the right answer for a small
    target, and every one of the four is legal for an INPUT profile."""
    from ui.dialogs import scanner_colprof as SC
    assert set(SC.PTYPE_CHOICES_BY_MODE[False]) == {d for d, _ in SC.PTYPE_CHOICES}
    assert SC.PTYPE_DEFAULT[False] in SC.PTYPE_CHOICES_BY_MODE[False]
    assert SC.PTYPE_DEFAULT[True] in SC.PTYPE_CHOICES_BY_MODE[True]


# ---------------------------------------------------------------------------
# 3. a label names the algorithm the letter selects
# ---------------------------------------------------------------------------
#: The words that describe an algorithm FAMILY, in colprof's own usage text.
#: "matrix" is deliberately not among the words a label may not add: every one
#: of the formula types has a matrix in it, and a label is free to mention it.
_FAMILY_WORDS = ("clut", "gamma", "shaper", "single")


def _usage_names(text: str) -> "dict[str, str]":
    """`{letter: colprof's own name for it}` from the `-a` usage block."""
    start = text.index("Algorithm type override")
    block = text[start:text.index('" -u ', start)]
    return {m.group(1): m.group(2).strip().rstrip(",")
            for m in re.finditer(r"(?<![\w-])(\w) = ([^,\\]+)", block)}


def _families(name: str) -> "set[str]":
    low = name.lower()
    return {w for w in _FAMILY_WORDS if w in low}


def test_the_usage_block_still_names_every_letter_we_read_from_it():
    text = _colprof_c()
    names = _usage_names(text)
    # `L` is the undocumented synonym; the usage text really does omit it.
    assert set(names) == set(PB.COLPROF_ALGORITHMS) - {"L"}, sorted(names)
    assert "shaper" in names["s"].lower() and "gamma" not in names["s"].lower()
    assert "single" in names["G"].lower()


def test_no_label_names_an_algorithm_the_letter_does_not_select():
    """The defect that survived beta 11 in fourteen files.

    ChromIQ labelled `s` "Single gamma + matrix". colprof's own usage says
    `s = shaper+matrix`: a different algorithm, and the one ArgyllCMS calls
    "superior to gamma curve profiles". `G` ("Gamma + matrix (forced)") and
    `S` dropped the word colprof uses for what actually separates them, which
    is that they fit ONE curve shared by all three channels.

    The label-count check that existed could not see any of this: it compared
    the LENGTH of the label list with the length of the choice list.
    """
    from ui.dialogs import scanner_colprof as SC
    names = _usage_names(_colprof_c())
    labelled: "list[tuple[str, str, str]]" = []
    for name, pairs in _tab_profile_combos().items():
        labelled += [(f"tab_profile {name}", ltr, lbl) for ltr, lbl in pairs]
    row = _yaml_algorithm_row()
    labelled += [("parameters.yaml", ltr, lbl)
                 for ltr, lbl in zip(row["choices"], row["labels"])]
    labelled += [("scanner window", ltr, lbl) for ltr, lbl in SC.PTYPE_CHOICES]
    assert labelled, "no labels found at all — this test has gone blind"

    bad = []
    for where, letter, label in labelled:
        want = _families(names[letter])
        got = _families(label)
        # A label may be shorter than colprof's name, but it may not claim a
        # family the letter does not select. "cLUT" is required rather than
        # optional: it is the one word that says whether the profile is a
        # stored table, which is the difference that decides everything else.
        for word in got - want:
            bad.append(f'{where}: "{label}" says "{word}", but colprof says '
                       f'-a{letter} is "{names[letter]}"')
        if "clut" in want and "clut" not in got:
            bad.append(f'{where}: "{label}" does not say cLUT, but -a{letter} '
                       f'is "{names[letter]}"')
    assert not bad, "\n  " + "\n  ".join(bad)


# ---------------------------------------------------------------------------
# 4. the failure can never be silent again
# ---------------------------------------------------------------------------
def test_the_output_clut_error_has_a_pattern_and_a_message():
    """`-aM` failed silently because no pattern matched colprof's answer.
    `-am` on a printer failed the same way, for the same reason, and did it
    with a letter that really exists.
    """
    line = ("/Applications/Argyll/bin/colprof: Error - Output profile can "
            "only be a cLUT algorithm")
    hits = [(key, fmt) for pat, key, fmt in PB._COLPROF_ERROR_PATTERNS
            if pat.search(line)]
    assert hits, ("no _COLPROF_ERROR_PATTERNS entry matches colprof's own "
                  "refusal of a non-cLUT output profile")
    key, fmt = hits[0]
    assert fmt.strip(), f"{key} matches but carries no message for the user"
    assert "cLUT" in fmt or "lookup table" in fmt


def test_the_pattern_matches_the_string_colprof_actually_prints():
    text = _colprof_c()
    m = re.search(r'error\s*\(\s*"([^"]*cLUT algorithm[^"]*)"', text)
    assert m, "colprof.c no longer prints that error at all"
    assert any(pat.search(m.group(1))
               for pat, _k, _f in PB._COLPROF_ERROR_PATTERNS), m.group(1)


# ---------------------------------------------------------------------------
# 4b. Quality applies to every profile type, and is no longer greyed out
# ---------------------------------------------------------------------------
def test_quality_is_never_greyed_out_again():
    """It was disabled for the matrix types and SENT ANYWAY.

    `make_profile_params` passes `quality=main_vals.get("quality", "m")`
    unconditionally, so the greyed value went on the command line regardless:
    the user was told the control did not apply, could not change it, and it
    was used. ArgyllCMS's own `-q` documentation says it applies to matrix
    profiles too ("the per channel curve detail level and fitting 'effort'"),
    and MEASURED with `-q l/m/h/u` against `-as`, `-am`, `-ag`, `-aS` and
    `-aG`, every one of them produces four different profiles.

    Read off the source, because what is being pinned is the ABSENCE of a
    call: there is no widget state left to assert once the row is always
    enabled.
    """
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._on_colprof_changed)
    assert "setEnabled" not in src, (
        "the Quality row is being enabled or disabled from the profile type "
        "again; -q applies to every type colprof has")
    # …and the value really is sent for a matrix type, which is the half that
    # makes the greying indefensible rather than merely wrong.
    from pathlib import Path as _P
    from ui.dialogs import scanner_colprof as SC
    from workflow.profile_builder import ProfileBuilder
    for ptype in SC.MATRIX_ALGOS:
        params = SC.make_profile_params(_P("x.ti3"), "d",
                                        {"ptype": ptype, "quality": "h"}, {})
        assert "-qh" in ProfileBuilder(None)._build_args(params)


# ---------------------------------------------------------------------------
# 5. a stored letter that is no longer offered
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("stored,expect,changed", [
    ("l", "l", False),
    ("x", "x", False),
    ("L", "l", True),          # the undocumented synonym
    ("X", "x", True),          # bit-identical on a printer
    ("Y", "x", True),
    ("g", "l", True),          # never built anything
    ("G", "l", True),
    ("s", "l", True),
    ("S", "l", True),
    ("m", "l", True),
    ("", "l", False),          # nothing stored is not a change
    (None, "l", False),
])
def test_a_stored_algorithm_lands_on_one_that_works(stored, expect, changed):
    assert PB.output_algorithm(stored) == (expect, changed)


def test_every_letter_the_app_could_have_stored_has_somewhere_to_go():
    for letter in PB.COLPROF_ALGORITHMS:
        got, _changed = PB.output_algorithm(letter)
        assert got in PB.OUTPUT_ALGORITHM_CHOICES, letter


def test_a_stored_scanner_profile_type_lands_on_one_that_works():
    from ui.dialogs import scanner_colprof as SC
    assert SC.coerce_ptype("s", printer=False) == ("s", False)
    assert SC.coerce_ptype("m", printer=False) == ("m", False)
    assert SC.coerce_ptype("l", printer=True) == ("l", False)
    assert SC.coerce_ptype("x", printer=True) == ("x", False)
    # …and the two the printer bucket could be holding from before it filtered
    assert SC.coerce_ptype("s", printer=True) == (SC.PTYPE_DEFAULT[True], True)
    assert SC.coerce_ptype("m", printer=True) == (SC.PTYPE_DEFAULT[True], True)
    assert SC.coerce_ptype("", printer=True) == (SC.PTYPE_DEFAULT[True], False)


def test_the_build_profile_tab_says_when_it_moves_a_stored_algorithm(qapp,
                                                                     tmp_path):
    """A project saved with "Matrix only" must still open, AND the user must be
    told the algorithm moved. Silence here is the migration failure CLAUDE.md
    names: the next profile would quietly differ."""
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_profile import TabProfile
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    tab = TabProfile(ArgyllRunner(s), s)
    try:
        tab._log.clear()
        tab._m_apply_preset_data({"algorithm": "m", "quality": "m"})
        assert tab._m_algo_combo.currentData() == "l"
        said = tab._log.toPlainText()
        assert "-a m" in said and "Lab cLUT" in said, said
        # The alias case is a note, not a warning: the built file is unchanged.
        tab._log.clear()
        tab._algo_moves_said.clear()
        tab._m_apply_preset_data({"algorithm": "X", "quality": "m"})
        assert tab._m_algo_combo.currentData() == "x"
        assert "unchanged" in tab._log.toPlainText()
        # …and a letter that IS offered says nothing at all.
        tab._log.clear()
        tab._m_apply_preset_data({"algorithm": "x", "quality": "m"})
        assert tab._log.toPlainText().strip() == ""
    finally:
        tab.deleteLater()


# ---------------------------------------------------------------------------
# 6. THE SLOW TIER — the real binary, one build per offered letter
# ---------------------------------------------------------------------------
def _synthetic_ti3(directory: Path, device_class: str) -> Path:
    """A real, buildable measurement of *device_class*, from the benchmark
    printer model the engine tests already use. Deterministic, ~16 kB, and it
    needs no ArgyllCMS to produce."""
    from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
    printer = PRINTERS["S1"]
    chart = make_chart(printer, 300)
    xyz, _refl, _ = measure(printer, chart)
    path = write_ti3(directory / "chart.ti3", printer, chart, xyz)
    if device_class != "OUTPUT":
        # A scanner measurement is the same numbers read the other way round:
        # the device is the RGB the scanner reported and XYZ is the reference.
        path.write_text(
            path.read_text(encoding="utf-8")
            .replace('DEVICE_CLASS "OUTPUT"', f'DEVICE_CLASS "{device_class}"')
            .replace(f'COLOR_REP "{printer.color_rep}"', 'COLOR_REP "XYZ_RGB"'),
            encoding="utf-8")
    return path


def _build(colprof: str, ti3: Path, letter: str) -> "tuple[int, Path | None, str]":
    work = Path(tempfile.mkdtemp())
    try:
        base = work / "chart"
        shutil.copy(ti3, base.with_suffix(".ti3"))
        # Budget for a LOADED machine, not an idle one (CLAUDE.md): -ql on 300
        # patches is about a second here, and the gate saturates every core.
        r = subprocess.run([colprof, "-ql", "-a", letter, str(base)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        icc = next((p for p in (base.with_suffix(".icc"), base.with_suffix(".icm"))
                    if p.is_file() and p.stat().st_size > 1000), None)
        if icc is not None:
            icc = Path(shutil.copy(icc, tempfile.mkdtemp()))
        return r.returncode, icc, (r.stdout + r.stderr)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@pytest.mark.slow
@pytest.mark.parametrize("where,device_class,letters", _offered())
def test_real_colprof_builds_a_profile_for_every_letter_we_still_offer(
        where, device_class, letters, tmp_path):
    """Not a list check. The binary, one run per entry, and a file on disk.

    This is the test that would have caught the whole thing: the letters were
    all in colprof's parser, and five of them still wrote nothing.
    """
    colprof = argyll_tool("colprof")
    if colprof is None:
        pytest.skip("colprof not present")
    ti3 = _synthetic_ti3(tmp_path, device_class)
    failures = []
    for letter in letters:
        rc, icc, out = _build(colprof, ti3, letter)
        if rc != 0 or icc is None:
            reason = next((ln for ln in out.splitlines() if "Error" in ln),
                          out.strip().splitlines()[-1:] or [""])
            failures.append(f"{where}: -a{letter} rc={rc} icc={icc} :: {reason}")
    assert not failures, "\n  " + "\n  ".join(failures)


@pytest.mark.slow
def test_real_colprof_refuses_the_letters_this_app_stopped_offering():
    """The other half, and the one that makes the half above mean something.

    Without it, a list of `l` alone would pass the test above for ever. This
    proves the removed letters really are refused, so the filter is doing work
    rather than being decoration.
    """
    colprof = argyll_tool("colprof")
    if colprof is None:
        pytest.skip("colprof not present")
    work = Path(tempfile.mkdtemp())
    try:
        ti3 = _synthetic_ti3(work, "OUTPUT")
        for letter in "gGsSm":
            rc, icc, out = _build(colprof, ti3, letter)
            assert rc != 0 and icc is None, (
                f"-a{letter} now builds an OUTPUT profile — colprof has "
                f"changed and the offered list should be revisited")
            assert "cLUT algorithm" in out, out[-400:]
            # …and the message the user gets is the one this app writes.
            assert any(pat.search(out) for pat, _k, _f
                       in PB._COLPROF_ERROR_PATTERNS)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@pytest.mark.slow
def test_aX_really_does_make_the_same_printer_profile_as_ax():
    """The measurement behind leaving `X` off the printer list.

    Compared with the ICC header's creation date-time (bytes 24..35) zeroed,
    because two builds a second apart differ there and nowhere else, and an
    uncontrolled first run of this comparison is exactly how a "they differ"
    non-result gets reported.
    """
    colprof = argyll_tool("colprof")
    if colprof is None:
        pytest.skip("colprof not present")
    work = Path(tempfile.mkdtemp())
    try:
        ti3 = _synthetic_ti3(work, "OUTPUT")
        blobs = {}
        for letter in "xXY":
            rc, icc, out = _build(colprof, ti3, letter)
            assert rc == 0 and icc is not None, out[-400:]
            raw = bytearray(icc.read_bytes())
            raw[24:36] = b"\0" * 12
            blobs[letter] = bytes(raw)
        assert blobs["x"] == blobs["X"] == blobs["Y"], (
            "-aX / -aY now produce a different printer profile from -ax; "
            "colprof's OUTPUT branch must have stopped discarding mtxtoo, "
            "and the offered list should be revisited")
    finally:
        shutil.rmtree(work, ignore_errors=True)
