"""Every platform ships the same bundled data, because the app expects it.

macOS bundled `data/i18n` and `data/scanner_targets`; Windows bundled only the
first and Linux neither. Both are read at runtime through `resource_path`, which
resolves INTO the bundle, so a Linux build listed no languages at all --
`core.i18n.available_languages` offers what it finds in `data/i18n` -- and
neither Windows nor Linux carried the bundled scanner targets that
`workflow/standard_targets.py` opens. Nothing failed loudly; the features were
simply not there, on two of the three platforms ChromIQ ships to.

The specs are read as TEXT rather than executed: a PyInstaller spec runs inside
PyInstaller's own globals (`Analysis`, `EXE`, `BUNDLE`), which are not importable
here, and executing one would need a build environment this suite does not have.
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS = ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec")

#: Bundled data every platform needs. Each entry is a repository path that is
#: read at runtime through `core.resource_path`, so a platform that does not
#: bundle it loses the feature silently.
REQUIRED = (
    "assets",
    "data/parameters.yaml",
    "data/i18n",
    "data/scanner_targets",
)


def _datas(spec: str) -> set[str]:
    """The repository paths a spec bundles, from its `datas=[...]` list."""
    text = (ROOT / spec).read_text(encoding="utf-8")
    block = re.search(r"datas=\[(.*?)\n    \],", text, re.S)
    assert block, f"{spec} has no datas=[...] list this test can read"
    return set(re.findall(r"\(\s*'([^']+)'\s*,\s*'[^']*'\s*\)", block.group(1)))


@pytest.mark.parametrize("spec", SPECS)
@pytest.mark.parametrize("path", REQUIRED)
def test_every_spec_bundles_the_data_the_app_reads_at_runtime(spec, path):
    got = _datas(spec)
    assert path in got, (
        f"{spec} does not bundle {path!r}, so a build from it ships without "
        f"it. What that spec does bundle: {sorted(got)}"
    )


@pytest.mark.parametrize("path", REQUIRED)
def test_the_required_data_exists_in_the_repository(path):
    """A spec entry for a path that is not there would bundle nothing, and
    PyInstaller does not always say so."""
    assert (ROOT / path).exists(), f"{path} is listed as required but is missing"


def test_the_specs_do_not_drift_apart_again():
    """Beyond the required list: any data one spec bundles and another does not
    is either a deliberate platform difference or the next silent gap. New
    differences have to be named here, with the reason."""
    # Deliberate, and why. A platform-specific entry belongs in this map, not in
    # a quiet asymmetry between three files nobody diffs.
    ALLOWED = {
        # macOS ships the compliance limit sets; they arrive on the other two
        # platforms with #182, which is where that data is still being built.
        "data/compliance_sets": {"ChromIQ.spec"},
    }
    seen: dict[str, set[str]] = {}
    for spec in SPECS:
        for path in _datas(spec):
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
