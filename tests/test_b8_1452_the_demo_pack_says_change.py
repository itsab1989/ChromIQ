"""B8-1452 (beta 45 challenge 1, F6): "drift" reached users through the demo
pack, in Report-Limits-Evenness's run descriptions, README.txt and
COVERAGE.md. Knut, #182 5849392788: "The word drift is not used at all".

The generators write the pack, so the texts they carry are what is held
here; `make_release_demo_package --verify` checks the built pack itself
(`retired_words_in`)."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_release_demo_package as PKG                         # noqa: E402

_WORD = re.compile(r"(?i)\bdrift")


def _strings(path: Path) -> "list[str]":
    """Every string literal of a generator, docstrings included (the README
    quotes them); identifiers such as ``_drift`` are code, not text."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_the_generators_of_the_readers_texts_say_change():
    """MUTATION, proven red: "with a drift across the strips" back in
    `make_evenness_demo`'s run 1 description."""
    bad = []
    for name in ("make_evenness_demo.py", "make_every_metric_demo.py"):
        for s in _strings(ROOT / "scripts" / name):
            if _WORD.search(s):
                bad.append((name, s[:100]))
    assert not bad, bad


def test_the_index_rows_the_pack_prints_say_change():
    """The design record quotes the word where it records the ruling; the
    pack prints those rows in the app's words.

    MUTATION, proven red: an empty `_RETIRED_WORDING`."""
    for row in PKG.spec_index_rows():
        for k in ("subject", "status"):
            assert not _WORD.search(PKG.in_the_words_users_read(row[k])), \
                (row["section"], row[k][:120])


def test_verify_finds_the_word_in_a_run_description(tmp_path):
    """MUTATION, proven red: `retired_words_in` reading no meta.json."""
    run = tmp_path / "Demo" / "runs" / "run1"
    run.mkdir(parents=True)
    meta = run / "meta.json"
    meta.write_text(json.dumps({"description": "with a drift across"}),
                    encoding="utf-8")
    assert PKG.retired_words_in(tmp_path)
    meta.write_text(json.dumps({"description": "with a change across"}),
                    encoding="utf-8")
    assert PKG.retired_words_in(tmp_path) == []
