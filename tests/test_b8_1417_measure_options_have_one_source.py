"""B8-1417: chartread's options have ONE source, and its -T text names the
default the app really has.

`data/parameters.yaml` carried a `chartread:` block (-B -b -S -N -p -H -T -l
-X, with tooltips, translated in thirteen overlays) that nothing ever read.
`ParameterWidget` rows are built for targen and printtarg only
(`TabChart`), and the Measure tab has built its own chartread rows, with its
own texts through `tr()`, since the first public commit (689bb115), the same
commit that added the yaml block. So the yaml text was never on screen, and it
had gone wrong where nobody could see it: its -T tooltip said "the default of
0.7" beside `default: 0.5`, while the app's default is on at 0.7
(`core.settings.DEFAULTS`, restored by 37d70704), and it described -T as a
re-read of each patch where chartread hands the number to the instrument's
own patch-recognition threshold. The block is removed, with its overlays.

The second half is the rule the wrong number broke: the -T text a user
actually reads names the default the settings actually have.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("parameters", data)


def test_parameters_yaml_has_no_chartread_block_and_no_overlay_does():
    files = [ROOT / "data/parameters.yaml",
             *sorted((ROOT / "data/i18n").glob("parameters.*.yaml"))]
    assert len(files) == 14, [f.name for f in files]
    carrying = [f.name for f in files if "chartread" in _yaml(f)]
    assert not carrying, (
        f"a chartread block is back in {carrying}. Nothing builds rows from "
        "it: the Measure tab's `_ChartreadOption` rows are the one source "
        "of chartread's options and their texts (B8-1417).")


def test_the_app_builds_yaml_rows_for_targen_and_printtarg_only():
    """What made the chartread block dead. If a tab starts building rows from
    another tool's block, the block may come back, with this test."""
    src = (ROOT / "ui/tabs/tab_chart.py").read_text(encoding="utf-8")
    assert re.findall(r'self\._params\.get\("(\w+)"', src) == [
        "targen", "printtarg"]
    for path in (ROOT / "ui").rglob("*.py"):
        if path.name in ("tab_chart.py", "parameter_widget.py"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "ParameterWidget(" not in text, path


def _measure_tolerance_text() -> str:
    tree = ast.parse((ROOT / "ui/tabs/tab_measure.py").read_text(
        encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "tr" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.startswith(
                    "How much colour variation ChromIQ accepts WITHIN")):
            return node.args[0].value
    raise AssertionError("the Measure tab's -T help text was not found")


def test_the_tolerance_help_names_the_default_the_settings_have():
    from core.settings import DEFAULTS
    text = _measure_tolerance_text()
    m = re.search(r"ChromIQ starts you at (\d+(?:\.\d+)?)", text)
    assert m, "the -T help no longer names its starting value"
    assert float(m.group(1)) == DEFAULTS["measure_tolerance_value"], (
        f"the -T help says {m.group(1)}, the default is "
        f"{DEFAULTS['measure_tolerance_value']}")
    assert "switched on by default" in text
    assert DEFAULTS["measure_tolerance_enabled"] is True
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    value = f"{DEFAULTS['measure_tolerance_value']:g}"
    assert value in de[text] or value.replace(".", ",") in de[text], (
        "the German -T help does not name the default")
