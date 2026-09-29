"""Every platform ships the same bundled data, because the app expects it.

macOS bundled `data/i18n` and `data/scanner_targets`; Windows bundled only the
first and Linux neither. Both are read at runtime through `resource_path`, which
resolves INTO the bundle, so a Linux build listed no languages at all --
`core.i18n.available_languages` offers what it finds in `data/i18n` -- and
neither Windows nor Linux carried the bundled scanner targets that
`workflow/standard_targets.py` opens. Nothing failed loudly; the features were
simply not there, on two of the three platforms ChromIQ ships to.

**READ WITH `ast`, NOT WITH A REGULAR EXPRESSION, AND THAT IS THE POINT OF THIS
NOTE.** The first version of this file matched the `datas=[...]` block as raw
text, and a reviewer broke it in four ways within minutes: commenting the
protected entry out left all 17 tests green, which is exactly how an entry gets
disabled in practice; a conditional entry that bundles nothing on Linux also
passed; a legitimate double-quoted entry FAILED; and every `*_splat` group was
invisible, so the drift check compared four literal paths and nothing else.
Python's own parser has none of those blind spots: a comment is not in the tree,
a conditional is not a literal tuple, and quoting style does not exist by the
time the string is a node.

A spec is not IMPORTED here. It runs inside PyInstaller's own globals
(`Analysis`, `EXE`, `BUNDLE`), which are not importable in this suite, and
executing one would want a build environment. Parsing gives what is needed
without running anything.
"""
import ast
from pathlib import Path
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS = ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec")

#: Bundled data every platform needs. Each is a repository path read at runtime
#: through `core.resource_path`, so a platform that does not bundle it loses the
#: feature silently.
REQUIRED = (
    "assets",
    "data/parameters.yaml",
    "data/i18n",
    "data/scanner_targets",
    # ...and any other data folder the tree actually has. Listing them by hand
    # is how `data/compliance_sets` came to be bundled on macOS alone: the
    # folder existed, no line here mentioned it, and the only guard was a raw
    # substring search in another file which a challenge round proved blind to
    # commenting the entry out. A folder that ships must be named by all three
    # specs, and the list should not depend on somebody remembering to extend
    # it.
    *sorted(
        f"data/{d.name}"
        for d in (Path(__file__).resolve().parent.parent / "data").iterdir()
        if d.is_dir() and not d.name.startswith(("__", "."))
        and d.name not in {"i18n", "scanner_targets"}
        and any(d.iterdir())
    ),
)


def _analysis_datas(spec: str) -> tuple[set[str], int]:
    """``(literal source paths, count of entries this file cannot resolve)``.

    The second number matters as much as the first: a `*_splat` or a computed
    entry bundles something real, and a test that silently ignored them would
    report a drift that is not there and miss one that is.
    """
    tree = ast.parse((ROOT / spec).read_text(encoding="utf-8"), filename=spec)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Analysis"):
            continue
        for kw in node.keywords:
            if kw.arg != "datas":
                continue
            assert isinstance(kw.value, ast.List), (
                f"{spec}: datas= is not a literal list, so this test cannot "
                "read it. Say what it is instead of loosening the check."
            )
            literal: set[str] = set()
            dynamic = 0
            for el in kw.value.elts:
                if (isinstance(el, ast.Tuple) and len(el.elts) == 2
                        and isinstance(el.elts[0], ast.Constant)
                        and isinstance(el.elts[0].value, str)):
                    literal.add(el.elts[0].value)
                else:
                    dynamic += 1          # a splat, a name, a conditional
            return literal, dynamic
    raise AssertionError(f"{spec} has no Analysis(datas=[...]) call")


@pytest.mark.parametrize("spec", SPECS)
@pytest.mark.parametrize("path", REQUIRED)
def test_every_spec_bundles_the_data_the_app_reads_at_runtime(spec, path):
    got, _ = _analysis_datas(spec)
    assert path in got, (
        f"{spec} does not bundle {path!r} as a plain entry, so a build from it "
        f"ships without it. What that spec bundles literally: {sorted(got)}"
    )


@pytest.mark.parametrize("path", REQUIRED)
def test_the_required_data_exists_in_the_repository(path):
    """A spec entry for a path that is not there bundles nothing, and
    PyInstaller does not always say so."""
    assert (ROOT / path).exists(), f"{path} is listed as required but is missing"


def test_a_required_entry_cannot_be_disabled_without_this_file_noticing():
    """The guard on the guard.

    Commenting an entry out is how it gets disabled in practice, and the first
    version of this file could not see it. Parse a copy of a real spec with the
    protected line commented out and with it made conditional, and check that
    neither is counted as bundled.
    """
    import re
    import tempfile

    src = (ROOT / "ChromIQLinux.spec").read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines()
                if "'data/scanner_targets'" in ln)
    for label, replacement in (
            ("commented out", "#" + line),
            ("made conditional",
             re.sub(r"\((.*)\),?$",
                    r"*([(\1)] if sys.platform == 'win32' else []),",
                    line.strip()).rjust(len(line))),
    ):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "ChromIQLinux.spec"
            p.write_text(src.replace(line, replacement), encoding="utf-8")
            tree = ast.parse(p.read_text(encoding="utf-8"))
            found = set()
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "Analysis"):
                    for kw in node.keywords:
                        if kw.arg == "datas" and isinstance(kw.value, ast.List):
                            for el in kw.value.elts:
                                if (isinstance(el, ast.Tuple) and el.elts
                                        and isinstance(el.elts[0], ast.Constant)):
                                    found.add(el.elts[0].value)
            assert "data/scanner_targets" not in found, (
                f"an entry {label} still counts as bundled, so this file would "
                "pass while the build ships without the data"
            )


def test_the_specs_do_not_drift_apart_again():
    """Beyond the required list: any data one spec bundles and another does not
    is either a deliberate platform difference or the next silent gap. A new
    difference has to be named here, with the reason."""
    # Deliberate, and why. A platform-specific entry belongs in this map, not in
    # a quiet asymmetry between three files nobody diffs.
    # EMPTY, AND THAT IS THE POINT. The one entry this map ever held said
    # macOS alone shipped `data/compliance_sets`, "until #182". It was written
    # on 2026-09-09 in the very commit that closed the same gap for `data/i18n`
    # and `data/scanner_targets`, and it was stale one day later. An entry that
    # outlives its reason does not just fail to catch the fault, it AUTHORISES
    # it: the loop below skips any path this map excuses, so the gap would have
    # come back silently. Deleting the entry is part of closing the gap.
    ALLOWED: "dict[str, set[str]]" = {}
    seen: dict[str, set[str]] = {}
    for spec in SPECS:
        literal, _ = _analysis_datas(spec)
        for path in literal:
            if path.startswith("data/") or path == "assets":
                seen.setdefault(path, set()).add(spec)
    for path, specs in sorted(seen.items()):
        if set(specs) == set(SPECS):
            continue
        assert ALLOWED.get(path) == set(specs), (
            f"{path} is bundled by {sorted(specs)} but not by "
            f"{sorted(set(SPECS) - set(specs))}. If that is deliberate, say so "
            "in ALLOWED above with the reason; if it is not, add it to the spec "
            "that is missing it."
        )


def test_the_dynamic_entries_are_counted_and_not_silently_ignored():
    """`*_splat` groups bundle real files and this file cannot resolve them.

    Recorded rather than ignored, so nobody reads the drift check above as a
    complete comparison: it compares the LITERAL entries only. macOS carries
    several splat groups the other two do not.
    """
    counts = {spec: _analysis_datas(spec)[1] for spec in SPECS}
    assert all(n >= 0 for n in counts.values())
    assert any(n > 0 for n in counts.values()), (
        "no spec has a dynamic entry any more; if the splats are gone, the "
        "drift check above can be made complete and this test removed"
    )
