"""A run must state up front what it is not able to prove.

The gate header named the platform, PyQt, the rootdir, the plugins and the
worker count. It never named the two things that decide how much of the suite
actually ran, and both had already produced a wrong claim in writing:

* Seven files carry a module-level `skipif` on a GITIGNORED build artefact
  (`chromiq-chartread`), and an eighth skips part of itself on the same thing.
  Absent, those seven skip WHOLESALE. Measured 2026-09-03 in a
  worktree of the very commit a release was being judged on: 9,867 passed /
  227 skipped, where the machine that had built the helper reported 9,952 /
  142. Same tree, 85 fewer tests, and the only difference in the log was the
  total. A written claim that "the helper was present so nothing was silently
  skipped" was therefore an inference from a remembered number, and there was
  no artefact that could have falsified it.

* At least fourteen files skip on BUILD SHAPE ("no engine panel in this
  build"). Those turn a REMOVAL into a pass.

So: the header states the capability facts before the first test, the census at
the end groups every skip the run actually took, and a release gate refuses to
start without the helper rather than dropping 85 tests quietly.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import tests.conftest as ct

REPO = Path(__file__).resolve().parents[1]


class _Cfg:
    def __init__(self, **opts):
        self._o = opts

    def getoption(self, name):
        return self._o.get(name.lstrip("-").replace("-", "_"), False)


# ---------------------------------------------------------------------------
# The header
# ---------------------------------------------------------------------------

def test_the_header_names_the_helper_either_way():
    lines = "\n".join(ct.pytest_report_header(_Cfg(runslow=True)))
    assert "chart-reading engine:" in lines
    assert ("helper PRESENT" in lines) or ("helper ABSENT" in lines)


def test_the_header_says_which_tier_this_is():
    gate = "\n".join(ct.pytest_report_header(_Cfg(runslow=True)))
    daily = "\n".join(ct.pytest_report_header(_Cfg(runslow=False)))
    assert "THE RELEASE GATE" in gate
    assert "NOT a gate" in daily, (
        "an everyday run must say it is not a gate; reading one as a gate is "
        "how a release decision gets made on the wrong evidence")


def test_the_header_says_where_the_output_root_points():
    """The other thing a reader cannot check afterwards: whether this run could
    reach the owner's real projects folder."""
    lines = "\n".join(ct.pytest_report_header(_Cfg(runslow=True)))
    assert "output root:" in lines
    assert "NOT SANDBOXED" not in lines, (
        "this run's output root is the real ~/ChromIQ")


def test_the_header_promises_the_census():
    lines = "\n".join(ct.pytest_report_header(_Cfg(runslow=True)))
    assert "census" in lines


# ---------------------------------------------------------------------------
# The census
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reason,bucket", [
    ("the engine layout panel is not available in this build", "BUILD SHAPE"),
    ("no engine panel in this build", "BUILD SHAPE"),
    ("this build has no row-indicator checkbox", "BUILD SHAPE"),
    ("the sentence is not shown in this state", "BUILD SHAPE"),
    ("this one does not open the dialog itself", "BUILD SHAPE"),
    ("chromiq-chartread helper not built", "the helper is not built"),
    ("Argyll targen not available", "ArgyllCMS is not installed here"),
    ("offscreen platform doesn't report app-level focus here",
     "the platform cannot show it"),
    # Names Windows for a good reason and must not land in the platform
    # bucket because of it.
    ("wdi_simple.exe is a Windows binary and cannot be run here",
     "wdi-simple is not here"),
    ("wdi_simple.exe is not on this host (looked in …)",
     "wdi-simple is not here"),
    # …while the Argyll half of the same test file still reads as Argyll,
    # even though its reason mentions wdi-simple.
    ("ArgyllCMS is not installed on this host, so its usb/ArgyllCMS.inf "
     "cannot be read; wdi-simple's own numbering still applies",
     "ArgyllCMS is not installed here"),
    ("slow end-to-end build — use --runslow", "the slow tier was not asked for"),
])
def test_a_reason_lands_in_the_bucket_that_describes_it(reason, bucket):
    assert ct._skip_bucket(reason).startswith(bucket)


def test_an_unknown_reason_is_reported_rather_than_absorbed():
    """The property that stops the table rotting: a reason nobody has
    classified must be visible, not folded into whichever bucket is nearest."""
    assert ct._skip_bucket("mumble mumble something new").startswith(
        "UNCATEGORISED")


def test_the_census_prints_the_shape_bucket_loudly():
    class _W:
        def __init__(self):
            self.lines = []
            self.stats = {"skipped": [
                _Rep("no engine panel in this build"),
                _Rep("no engine panel in this build"),
                _Rep("Argyll targen not available"),
            ]}

        def write_sep(self, _c, title, **kw):
            self.lines.append(title)

        def write_line(self, text, **kw):
            self.lines.append(text)

    class _Rep:
        def __init__(self, reason):
            self.longrepr = ("some_test.py", 12, f"Skipped: {reason}")

    w = _W()
    ct._skip_census(w, _Cfg())
    out = "\n".join(w.lines)
    assert "WHAT THIS RUN DID NOT TEST - 3 skips" in out
    assert "BUILD SHAPE" in out
    assert "2 x no engine panel in this build" in out
    assert "ArgyllCMS is not installed here" in out


# ---------------------------------------------------------------------------
# The helper, and where it is looked for
# ---------------------------------------------------------------------------

def test_the_suite_looks_for_the_helper_where_the_app_does():
    """It used to look in ONE place - the CMake build tree, which is
    gitignored - while the app has always had a second: `native/chromiq-
    chartread`, the binary that is committed and that ships. A worktree, a
    fresh clone and any CI runner have the second and not the first."""
    sys.path.insert(0, str(REPO / "tests" / "helpers"))
    import replay_tools
    from workflow.chartread_engine import helper_path
    assert replay_tools.HELPER == Path(helper_path())


def test_the_committed_helper_is_in_the_tree():
    """If this ever fails, a fresh clone silently loses the engine tests
    again."""
    shipped = REPO / "native" / "chromiq-chartread"
    assert shipped.is_file(), (
        "the shipped chart-reading helper is not in the tree, so a checkout "
        "with no build directory can prove nothing about the engine")


def test_eight_files_skip_wholesale_without_it():
    """Pins the count the header quotes, so the header cannot go stale in
    silence. Wholesale means a module-level `pytestmark` - the whole file
    disappears - which is the case a reader cannot notice from a total."""
    whole, partial = [], []
    for p in sorted((REPO / "tests").glob("test_*.py")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.name == Path(__file__).name:
            continue
        if not re.search(r"\bHELPER\b(?!_)", text) \
                or "replay_tools" not in text:
            continue
        head = text.split("def test_", 1)[0]
        (whole if re.search(r"^pytestmark\s*=", head, re.M) and "HELPER" in head
         else partial).append(p.name)
    assert len(whole) == 8 and len(partial) == 1, (
        "the number of files gated on the chart-reading helper has changed "
        f"({len(whole)} wholesale, {len(partial)} in part) -> update the "
        f"header in tests/conftest.py. wholesale={whole} partial={partial}")


def test_a_gate_without_the_helper_refuses_to_start(tmp_path, monkeypatch):
    """The judgement, made explicit: a plain run stays green (a fresh clone is
    the normal case for a build artefact), a RELEASE GATE does not."""
    monkeypatch.setattr(ct, "_helper_path", lambda: None)
    with pytest.raises(pytest.UsageError) as exc:
        ct._enforce_the_helper(_Cfg(runslow=True))
    assert "release gate" in str(exc.value)
    assert "cmake" in str(exc.value)

    # an everyday run is untouched…
    ct._enforce_the_helper(_Cfg(runslow=False))
    # …and the gate can still be run knowingly.
    ct._enforce_the_helper(_Cfg(runslow=True, allow_missing_helper=True))


def test_a_gate_with_the_helper_starts():
    ct._enforce_the_helper(_Cfg(runslow=True))


def test_a_real_gate_run_without_the_helper_stops(tmp_path):
    """The one above proves the FUNCTION refuses. This proves the RUN calls it.

    Written because deleting the call from `pytest_configure` left the other
    test green: a check nothing invokes is not a check. `$CHROMIQ_CHARTREAD` is
    the app's own override and pointing it at a missing file is the cheapest
    way to make a real run believe the helper is gone.
    """
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-n", "0",
         "--runslow", "--collect-only", "-q",
         f"tests/{Path(__file__).name}"],
        cwd=str(REPO), timeout=300, capture_output=True, text=True,
        encoding="utf-8",
        env={**__import__("os").environ,
             "CHROMIQ_CHARTREAD": str(tmp_path / "no-such-helper")})
    text = out.stdout + out.stderr
    assert out.returncode != 0, text[-2000:]
    assert "release gate" in text, text[-2000:]
    assert "--allow-missing-helper" in text

    # …and the escape hatch really is one.
    ok = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-n", "0",
         "--runslow", "--allow-missing-helper", "--collect-only", "-q",
         f"tests/{Path(__file__).name}"],
        cwd=str(REPO), timeout=300, capture_output=True, text=True,
        encoding="utf-8",
        env={**__import__("os").environ,
             "CHROMIQ_CHARTREAD": str(tmp_path / "no-such-helper")})
    assert ok.returncode == 0, (ok.stdout + ok.stderr)[-2000:]
    assert "helper ABSENT" in ok.stdout, (
        "the run continued without saying, in the header, that it cannot "
        "prove anything about the chart-reading engine")


# ---------------------------------------------------------------------------
# End to end: what a reader actually sees
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quiet", [True, False])
@pytest.mark.parametrize("workers", ["0", "2"])
def test_the_header_really_reaches_the_top_of_a_run(tmp_path, quiet, workers):
    """Not the hook in isolation - a real pytest run, and the header in its
    output above the first test.

    Both verbosities AND both scheduler shapes, because both can lose it and
    the gate uses both at once:

    * `-q` DISCARDS `pytest_report_header` - pytest calls the hook and prints
      nothing. (The 41 gate logs on the Desktop were run at normal verbosity
      and would have shown it; `-q` is still how this suite is usually driven.)
    * under xdist the CONTROLLER does not run `pytest_collection_finish`, which
      is where the `-q` fallback lived first. It printed perfectly at `-n0` and
      printed nothing at all in the `-n auto` gate: absent exactly where it was
      needed, correct everywhere else.
    """
    # One fast node inside tests/, so the repo's own conftest is loaded - a
    # file written into tmp_path has a different rootdir and never sees it.
    node = (f"tests/{Path(__file__).name}"
            "::test_a_gate_with_the_helper_starts")
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-n", workers,
         node] + (["-q"] if quiet else []),
        cwd=str(REPO), timeout=300, capture_output=True, text=True, encoding="utf-8")
    text = out.stdout + out.stderr
    assert "what this run can and cannot prove:" in text, text[-3000:]
    assert "chart-reading engine:" in text
    assert text.index("what this run can and cannot prove:") < text.index(
        "1 passed"), "the header is not at the top of the run"
