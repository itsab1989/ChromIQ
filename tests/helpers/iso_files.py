"""The two states of the shipped ISO 12647 values file, for tests (#182 S-2, §23).

Since the S-2 commit the repository's `data/compliance_sets/iso12647.json`
SHIPS both sets. A test that guards what the app does with an EMPTY shipped
set must therefore make that state itself, instead of reading the repository's
file and finding it empty. :func:`use_empty_shipped_iso` does that: it stands
a file holding both sets as ``{}`` in for the shipped one
(`compliance_sets._bundled_iso_path`) and points the environment variable at
the same file, so it is read once, as the shipped file, and never as a
licence holder's own. The licence holder's real file is never read either
way, because the variable always wins.

:func:`use_repo_iso` is the other state: the variable forced at the
repository's own file, which is what every driver and generator does.

:func:`shipped_limits` returns what the repository's file gives a row, read
from the file itself, so that a test asserts the shipped truth without its
source carrying a single number of either standard.
"""
from __future__ import annotations

import json
from pathlib import Path

from workflow import compliance_sets as cs

ROOT = Path(__file__).resolve().parents[2]
REPO_ISO_FILE = ROOT / cs.ISO_DATA_FILE


def use_empty_shipped_iso(tmp_path: Path, monkeypatch) -> Path:
    """Make both ISO sets EMPTY as shipped, for the rest of the test."""
    path = Path(tmp_path) / "shipped-empty-iso12647.json"
    path.write_text(json.dumps({"iso_12647_7": {}, "iso_12647_8": {}}),
                    encoding="utf-8")
    monkeypatch.setattr(cs, "_bundled_iso_path", lambda: path)
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(path))
    cs.reset_iso_cache()
    return path


def use_repo_iso(monkeypatch) -> Path:
    """Force the repository's own shipped file, as the drivers do. It is
    also stood back in as the shipped file, in case this test made the empty
    state first."""
    monkeypatch.setattr(cs, "_bundled_iso_path", lambda: REPO_ISO_FILE)
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(REPO_ISO_FILE))
    cs.reset_iso_cache()
    return REPO_ISO_FILE


def shipped_doc() -> dict:
    return json.loads(REPO_ISO_FILE.read_text(encoding="utf-8"))


def shipped_limits(set_id: str) -> "dict[str, cs.Limit]":
    """The rows of *set_id* the repository's file carries a NUMBER for."""
    cells = shipped_doc().get(set_id) or {}
    out = {}
    for rid, raw in cells.items():
        lim = cs.Limit.from_json(raw)
        if rid in cs.ROW_BY_ID and lim.is_numeric:
            out[rid] = lim
    return out
