"""Saving any preset must not delete one whose file is spelt differently.

On a case- and normalisation-insensitive disk (APFS by default, NTFS),
writing ``Mine.json`` goes into an existing ``mine.json`` and the directory
keeps the old spelling. ``save_presets`` then found ``mine.json`` "not
wanted" and unlinked it: the preset it had just written was gone, together
with every other preset whose file was spelt that way. A preset file that was
downloaded, renamed by hand or copied from an HFS+ disk (decomposed umlauts)
reached that state, and the next save of ANY preset lost it.
"""
from __future__ import annotations

import json
import unicodedata

import pytest

from core import preset_store as PS


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    d = PS.tab_dir("create_chart")
    d.mkdir(parents=True)
    return d


def _case_insensitive(d) -> bool:
    probe = d / "CaseProbe"
    probe.write_text("x", encoding="utf-8")
    try:
        return (d / "caseprobe").exists()
    finally:
        probe.unlink()


def _write(d, stem: str, name: str) -> None:
    (d / f"{stem}.json").write_text(json.dumps(
        {"chromiq_preset_version": 1, "tab": "create_chart", "name": name,
         "data": {"attached_ti1": True, "stem": stem}}), encoding="utf-8")
    (d / f"{stem}.ti1").write_text("CTI1\n", encoding="utf-8")


def test_a_lower_case_file_survives_saving_another_preset(store):
    if not _case_insensitive(store):
        pytest.skip("case-sensitive disk: the two spellings are two files")
    _write(store, "mine", "Mine")
    presets = PS.load_presets("create_chart")
    assert list(presets) == ["Mine"]
    presets["Other"] = {"k": 1}
    PS.save_presets("create_chart", presets)
    assert set(PS.load_presets("create_chart")) == {"Mine", "Other"}
    assert PS.load_presets("create_chart")["Mine"]["stem"] == "mine"


def test_a_decomposed_umlaut_file_survives_saving_another_preset(store):
    nfd = unicodedata.normalize("NFD", "Grün")
    _write(store, nfd, "Grün")
    if not (store / "Grün.json").exists():
        pytest.skip("normalisation-sensitive disk")
    presets = PS.load_presets("create_chart")
    assert list(presets) == ["Grün"]
    presets["Other"] = {"k": 1}
    PS.save_presets("create_chart", presets)
    assert set(PS.load_presets("create_chart")) == {"Grün", "Other"}


def test_a_leftover_under_another_name_is_still_removed(store):
    """The guard keeps only the file that was just written."""
    PS.save_presets("create_chart", {"A": {}, "B": {}})
    PS.save_presets("create_chart", {"A": {}})
    assert {p.name for p in store.glob("*.json")} == {"A.json"}
