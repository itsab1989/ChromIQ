"""The em-dash rule's collector must keep seeing the Create Chart dropdowns.

Until 2026-09-10 `scripts/em_dash_check.py` gathered a key that does not exist
in `data/parameters.yaml` (`label`) and missed the two that do: `name`, the
caption beside a control, 77 of them, and `labels`, the entries of a dropdown,
12 lists. So 145 user-facing strings were invisible to it and 23 dropdown
entries carried an em dash with the rule green.

A challenge round then pointed out that the widened collector was pinned on the
feature branch and NOT on master, and proved the gap by planting a dash in a
real dropdown entry after removing `"labels"`: the entry went invisible and the
test stayed green. This is that pin, on master, where the collector lives.

It names strings that exist ONLY under those keys. An earlier attempt at this
assertion named a phrase that also appears in a tooltip, so a mutation blinding
the key entirely still passed it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import em_dash_check as E                                        # noqa: E402


def test_the_sweep_reaches_the_dropdown_entries():
    english = E.english_strings()
    assert "OFPS: optimised farthest point (recommended)" in english, (
        "the sweep no longer reaches data/parameters.yaml `labels`. Every "
        "dropdown entry in Create Chart has just gone invisible to the em-dash "
        "rule and to anything else built on english_strings().")


def test_the_sweep_reaches_the_control_captions():
    english = E.english_strings()
    assert "B2A Table Quality" in english, (
        "the sweep no longer reaches data/parameters.yaml `name`, the captions "
        "beside the controls.")


def test_the_collector_names_only_keys_that_exist():
    """`label` was collected for months and occurs zero times in the file.

    A key list that names something absent looks like coverage and is not, so
    every key the collector asks for must actually appear in the file it reads.
    """
    import yaml
    doc = yaml.safe_load((ROOT / "data" / "parameters.yaml").read_text(encoding="utf-8"))
    seen: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                seen.add(k)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    for key in ("name", "labels", "tooltip_title", "tooltip_body"):
        assert key in seen, f"the collector asks for {key!r}, which the file has none of"
