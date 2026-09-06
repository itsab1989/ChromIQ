"""What an Argyll tool accepts is a FACT, and it belongs next to the argv.

Knut, v4.1.5-beta.10, opening Tools > Edit / create chart patch set on a CR30
chart:

    printtarg failed (1): Generate Target PostScrip file, Version 3.5.0
    …
    Diagnostic: Argument to -i wasn't recognised

51 lines of printtarg's usage text, in a QMessageBox 1433 px tall on a 1079 px
work area, with its only button 372 px below the bottom of the screen.

The value came from `workflow/ti2_relayout.py`. `instrument_to_flag` returns the
ChromIQ-only sentinel "CR30" for a CR30 chart and line 991 handed it straight to
`-i`. **The rule against that existed and lived in one module:**
`chart_creator._build_printtarg_args` refuses to build an argv for an
ENGINE_ONLY instrument, with a comment saying exactly why — and `ti2_relayout`
builds its own argv and does not import it.

So this file holds the vocabulary as data, checked against ArgyllCMS's own
source where that source is on disk, and checks every place in the app that
puts one of these letters on a command line against it.

Three separate claims, and each of them was wrong somewhere in the shipped app:

* printtarg `-i` accepts `20 22 41 51 SS ss i1 3p cm CM`. NOT `p3` — printtarg's
  own usage line prints `p3` and then contradicts itself two lines later, and
  ChromIQ's `data/parameters.yaml` still offers `p3` as an internal key.
* printtarg custom `-p WWWxHHH` accepts 1..4000 mm on each axis. Both custom
  paper spin boxes in the patch editor were `setRange(10, 9999)`.
* colprof `-a` accepts `l L x X Y g G s S m`. The Profile tab offered `M`.
"""
from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import ti2_relayout as R                      # noqa: E402
from workflow import chart_creator as CC                    # noqa: E402
from workflow import profile_builder as PB                  # noqa: E402


#: Where the ArgyllCMS 3.5.0 sources sit when they are on this machine. Every
#: test that needs them SKIPS without them and says so; the constants are still
#: checked against the excerpts quoted in the code, which travel with the repo.
ARGYLL_SRC = Path("/Users/Basti/Downloads/Argyll_V3.5.0_orig")


# ---------------------------------------------------------------------------
# 1. the constants say what the tool's source says
# ---------------------------------------------------------------------------
def _printtarg_c() -> str:
    src = ARGYLL_SRC / "target" / "printtarg.c"
    if not src.is_file():
        pytest.skip(f"ArgyllCMS sources not on this machine ({src})")
    return src.read_text(encoding="utf-8", errors="ignore")


def _colprof_c() -> str:
    src = ARGYLL_SRC / "profile" / "colprof.c"
    if not src.is_file():
        pytest.skip(f"ArgyllCMS sources not on this machine ({src})")
    return src.read_text(encoding="utf-8", errors="ignore")


def test_the_instrument_set_is_printtargs_own_strcmp_chain():
    """Parsed out of the parser, not transcribed from the usage text.

    The usage text is the thing that is WRONG about this ("p3"), so reading it
    would reproduce the defect this file exists to prevent.
    """
    text = _printtarg_c()
    start = text.index("argv[fa][1] == 'i'")
    block = text[start:text.index("Argument to -i wasn't recognised", start)]
    found = set(re.findall(r'strcmp\("([^"]+)",\s*na\)', block))
    assert found == set(R.PRINTTARG_INSTRUMENTS), (
        f"printtarg.c accepts {sorted(found)}, "
        f"PRINTTARG_INSTRUMENTS says {sorted(R.PRINTTARG_INSTRUMENTS)}")


def test_p3_is_not_one_of_them_and_3p_is():
    """The single correction the whole CR30 hunt turned on.

    printtarg prints `-i 20 | 22 | 41 | 51 | SS | i1 | p3 | CM` and then, two
    lines below, `3p = i1Pro3+`. The parser only knows the second.
    """
    assert "p3" not in R.PRINTTARG_INSTRUMENTS
    assert "3p" in R.PRINTTARG_INSTRUMENTS


def test_the_paper_ceiling_is_printtargs_own_sanity_check():
    text = _printtarg_c()
    start = text.index("Argument to -p was of unexpected size")
    block = text[max(0, start - 400):start]
    lo = set(re.findall(r"cwidth < ([\d.]+)", block))
    hi = set(re.findall(r"cwidth > ([\d.]+)", block))
    assert lo == {f"{R.PRINTTARG_PAPER_MIN_MM:g}.0"} or \
           lo == {str(R.PRINTTARG_PAPER_MIN_MM)}, lo
    assert hi == {str(R.PRINTTARG_PAPER_MAX_MM)}, (
        f"printtarg.c refuses above {hi}, "
        f"PRINTTARG_PAPER_MAX_MM says {R.PRINTTARG_PAPER_MAX_MM}")


def test_the_colprof_algorithm_set_is_colprofs_own_switch():
    text = _colprof_c()
    # Anchored on the switch itself: `argv[fa][1] == 'a'` also appears in
    # other tools' parsers and, in this file, above the flag this is about.
    start = text.index("Expect argument to algorithm flag -a")
    block = text[start:text.index("Unknown argument '%c' to algorithm flag",
                                  start)]
    found = set(re.findall(r"case '(.)':", block))
    assert found == set(PB.COLPROF_ALGORITHMS), (
        f"colprof.c switches on {sorted(found)}, "
        f"COLPROF_ALGORITHMS says {sorted(PB.COLPROF_ALGORITHMS)}")


# ---------------------------------------------------------------------------
# 2. every value the app can put on a command line is in the set
# ---------------------------------------------------------------------------
def test_every_flag_instrument_to_flag_can_return_is_known():
    """Either printtarg accepts it, or the app must refuse it before spawning.

    "CR30" is the one value deliberately outside the accepted set: #159 took it
    OUT of this function's catch-all `return "i1"` so a CR30 chart would not be
    silently re-laid as an i1Pro strip chart. That was right, and nothing
    downstream was told — which is the whole defect.
    """
    names = ["CR30", "cr30", "ChnSpec CR30", "X-Rite ColorMunki",
             "GretagMacbeth SpectroScan", "GretagMacbeth i1 Pro", "i1Pro3 Plus",
             "i1pro 3+", "X-Rite DTP41", "X-Rite DTP51", "i1iSis",
             "X-Rite i1iSis", "", None, "something nobody has heard of"]
    refused = set()
    for name in names:
        flag = R.instrument_to_flag(name)
        if flag in R.PRINTTARG_INSTRUMENTS:
            continue
        refused.add(flag)
        with pytest.raises(R.PrinttargCannotLayOutChart):
            R.check_printtarg_can_lay_out(flag, "A4")
    assert refused == {"CR30"}, (
        f"instrument_to_flag can return {sorted(refused)}, which printtarg "
        f"does not accept — every one of those needs a decision, not a guess")


def test_no_path_in_the_app_can_hand_printtarg_the_string_p3():
    """`p3` is ChromIQ's OWN key for the i1Pro3 Plus, and printtarg's is `3p`.

    The whole app speaks `p3` internally (`ENGINE_INSTRUMENTS`, the layout
    engine, `data/parameters.yaml:626`), and exactly two places turn one of
    those keys into a printtarg `-i`. Both must translate. This reads them off
    the source rather than trusting that they still do.
    """
    a = inspect.getsource(CC.ChartCreator._build_printtarg_args)
    assert '"3p" if p.instrument == "p3"' in a, (
        "chart_creator no longer translates p3 -> 3p on the way to printtarg")
    # The second builder does not translate: it never sees `p3`, because the
    # only two things that set `ChartSpec.instrument_flag` are
    # `instrument_to_flag` (which returns "3p") and a combo restored with
    # `findData`. Pin both halves of that.
    b = inspect.getsource(R.instrument_to_flag)
    assert '"p3"' not in b and 'return "3p"' in b
    from ui.dialogs import ti2_relayout_dialog as D
    assert "p3" not in [code for code, _label in D._INSTRUMENTS]
    for code, _label in D._INSTRUMENTS:
        assert code in R.PRINTTARG_INSTRUMENTS, code


def test_every_algorithm_letter_the_ui_offers_is_one_colprof_has():
    """Guided, Manual and parameters.yaml, all three read off their own source.

    `-aM` produced no profile, no window and one line in a log, because
    `_COLPROF_ERROR_PATTERNS` has no entry that matches colprof's answer to it.
    """
    import yaml
    from ui.tabs import tab_profile as TP

    # Both combos (Guided and Manual) are built from an inline list of
    # (code, label) pairs right after an "Algorithm (-a):" label, so the pairs
    # are read out of the module's own source rather than by constructing a
    # whole TabProfile.
    src = inspect.getsource(TP)
    chunks = src.split('QLabel(tr("Algorithm (-a):")')[1:]
    assert len(chunks) >= 2, (
        f"expected the Guided and the Manual algorithm combo, found "
        f"{len(chunks)} — this test has gone blind")
    offered: "set[str]" = set()
    for chunk in chunks:
        head = chunk[:chunk.index("]:")]
        offered |= set(re.findall(r'\(\s*"(.)",\s*"', head))
    assert offered, "no algorithm combo found in tab_profile — test is blind"

    root = Path(__file__).resolve().parent.parent
    params = yaml.safe_load(
        (root / "data" / "parameters.yaml").read_text(encoding="utf-8"))
    yaml_choices: "set[str]" = set()
    for entry in params["parameters"]["colprof"]:
        if entry.get("flag") == "-a":
            yaml_choices = set(entry["choices"])
    assert yaml_choices, "no colprof -a row in parameters.yaml"

    bad = sorted((offered | yaml_choices) - set(PB.COLPROF_ALGORITHMS))
    assert not bad, (
        f"the UI offers colprof algorithm letters colprof does not have: {bad}")


def test_the_labels_still_match_the_choices_in_every_language():
    """Removing "M" removed a CHOICE and a LABEL, in thirteen files.

    The overlays are keyed by flag rather than being a list, so a label list
    that is one entry too long does not fail to load: it just puts the wrong
    words against the wrong letter, silently, from the point of the mismatch.
    """
    import yaml
    root = Path(__file__).resolve().parent.parent
    base = None
    params = yaml.safe_load(
        (root / "data" / "parameters.yaml").read_text(encoding="utf-8"))
    for entry in params["parameters"]["colprof"]:
        if entry.get("flag") == "-a":
            base = entry
    assert base is not None
    assert len(base["choices"]) == len(base["labels"])
    checked = 0
    for overlay in sorted((root / "data" / "i18n").glob("parameters.*.yaml")):
        data = yaml.safe_load(overlay.read_text(encoding="utf-8"))
        row = (data.get("parameters") or {}).get("colprof", {}).get("-a")
        if not isinstance(row, dict) or "labels" not in row:
            continue
        checked += 1
        assert len(row["labels"]) == len(base["choices"]), (
            f"{overlay.name} offers {len(row['labels'])} labels for "
            f"{len(base['choices'])} choices")
    assert checked >= 10, f"only {checked} overlays checked"



# ---------------------------------------------------------------------------
# 3. the boundary actually refuses, before anything is spawned
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("flag", sorted(R.PRINTTARG_INSTRUMENTS))
def test_an_accepted_instrument_passes_the_boundary(flag):
    R.check_printtarg_can_lay_out(flag, "A4")


@pytest.mark.parametrize("flag", ["CR30", "p3", "isis", "I1", "3P", "", "i1 "])
def test_a_rejected_instrument_is_refused_at_the_boundary(flag):
    with pytest.raises(R.PrinttargCannotLayOutChart):
        R.check_printtarg_can_lay_out(flag, "A4")


@pytest.mark.parametrize("paper", ["A4", "A4R", "Letter", "483x329",
                                   "210x297", "4000x4000", "50x50"])
def test_an_accepted_paper_passes_the_boundary(paper):
    R.check_printtarg_can_lay_out("i1", paper)


@pytest.mark.parametrize("paper", ["4001x4001", "5000x5000", "9999x9999",
                                   "0.5x100", "100x0.5"])
def test_a_paper_outside_printtargs_range_is_refused(paper):
    with pytest.raises(R.PrinttargCannotLayOutChart):
        R.check_printtarg_can_lay_out("i1", paper)


def test_a_paper_NAME_is_left_for_printtarg_to_judge():
    """Only the custom WWWxHHH form is range-checked here.

    A name this module did not choose is printtarg's to reject, with its own
    one-line "Failed to recognise argument to -p" — which the error table now
    turns into a sentence. Guessing at the name list here would be a second
    copy of a thing that changes with the tool.
    """
    R.check_printtarg_can_lay_out("i1", "SomeNameOnlyPrinttargKnows")


def test_regenerate_refuses_a_cr30_chart_without_spawning_printtarg(
        tmp_path, monkeypatch):
    """The failure Knut hit, at the point it is now stopped.

    `run_text` is replaced with something that FAILS the test if it is called,
    so this cannot pass by the process merely erroring out somewhere else.
    """
    called = []
    monkeypatch.setattr(R, "run_text",
                        lambda *a, **k: called.append(a) or (_ for _ in ()).throw(
                            AssertionError("printtarg was spawned")))
    spec = R.ChartSpec.new("i1", "A4")
    spec.instrument_flag = "CR30"
    with pytest.raises(R.PrinttargCannotLayOutChart):
        R.regenerate(spec, [(100.0, 100.0, 100.0)], tmp_path,
                     "/Applications/Argyll/bin", basename="c",
                     options=R.LayoutOptions(), with_twin=False)
    assert not called


def test_the_refusal_says_something_a_person_can_read():
    """Not fifty-one lines of usage text. That is the entire point of CK-2."""
    try:
        R.check_printtarg_can_lay_out("CR30", "A4")
    except R.PrinttargCannotLayOutChart as exc:
        msg = str(exc)
    assert len(msg) < 400, msg
    assert "usage" not in msg.lower()
    assert "\n" not in msg


# ---------------------------------------------------------------------------
# 4. the error table can match the failure it was written for
# ---------------------------------------------------------------------------
def test_the_table_now_matches_the_message_printtarg_actually_prints():
    """`_PRINTTARG_ERROR_PATTERNS` had an entry for "Unsupported instrument
    type" and a comment claiming that is what a bad `-i` produces.

    It is not. That message is raised at `printtarg.c:2247` for an itype that
    PARSED; a `-i` string printtarg has never heard of dies in the argument
    parser, long before. So the one entry written for this case could never
    match it, and even a caller that routed the failure through
    `primary_failure()` would still have shown the raw dump.
    """
    dump = ("Generate Target PostScrip file, Version 3.5.0\n"
            "  Diagnostic: Argument to -i wasn't recognised\n"
            "usage: printtarg [-v] [-i instr] [-p paper] outfile\n"
            " -v              Verbose mode\n")
    got = CC.match_printtarg_error(dump)
    assert got is not None, "still no pattern for the message Knut saw"
    assert got[0] == "instrument_not_a_printtarg_code"
    assert "usage" not in got[1].lower()


def test_the_one_useful_line_is_what_is_quoted():
    dump = ("Generate Target PostScrip file, Version 3.5.0\n"
            "  Diagnostic: Argument to -p was of unexpected size\n"
            + "\n".join(f" -{c}   some usage line" for c in "abcdefgh"))
    assert CC.printtarg_said(dump) == "Argument to -p was of unexpected size"
    one = "printtarg: Error - Paper size not long enough for a single patch per row!"
    assert CC.printtarg_said(one) == \
        "Paper size not long enough for a single patch per row!"


def test_a_dump_with_nothing_useful_in_it_still_yields_a_line():
    assert CC.printtarg_said("something went wrong") == "something went wrong"
    assert CC.printtarg_said("") == ""


# ---------------------------------------------------------------------------
# 5. an argument that reaches a tool must reach it whole
# ---------------------------------------------------------------------------
def test_chartread_extra_args_survive_a_path_with_a_space():
    """`" ".join` on the way out and `shlex.split` on the way back is not a
    round trip: it tears a value with a space in two.

    Latent rather than live today, because no chartread option row carries a
    space — but `data/parameters.yaml` already declares a `-X file.ccmx` row,
    and a path with a space is the ordinary case the day that is wired up.
    `tab_chart` has always done this correctly with `shlex.join`, which is what
    makes the Measure tab's version an oversight rather than a policy.
    """
    import shlex
    from ui.tabs import tab_measure as TM

    for name in ("_collect_guided", "_collect_manual"):
        src = inspect.getsource(getattr(TM.TabMeasure, name))
        assert "shlex.join(extra_args)" in src, (
            f"{name} still joins chartread arguments with a plain space")
        assert '" ".join(extra_args)' not in src

    # …and the property that matters, exercised rather than asserted about.
    args = ["-X", "/Users/me/My Profiles/i1 pro.ccmx", "-Y", "A"]
    assert shlex.split(shlex.join(args)) == args
    assert shlex.split(" ".join(args)) != args
