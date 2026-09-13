"""#130 — the run description on the chart: the sidecar record and the token.

Test Plan Specification §3 and §7 (docs/design/per_run_description.md).

Two rules, both of them Knut's:

* the description is written into the chart's ``.channels.json`` as a **record
  only** and is never read back — a restore that took it from there could let
  an old chart silently rewrite the run's description, which is the failure his
  §2 ruling exists to prevent;
* ``{rundescription}`` must **not** be empty on a calibration chart (his R2
  ruling), because a calibration chart is a printed sheet like any other.
"""
from __future__ import annotations

import inspect
import json

import pytest


# ---- H6: the sidecar carries it, and nothing reads it back --------------
def test_the_sidecar_records_the_description():
    from workflow import chart_creator

    src = inspect.getsource(chart_creator)
    i = src.index('"run_description": params.run_description')
    assert '"chart_notes": params.chart_notes' in src[i - 400:i], (
        "the description should be written beside the notes, in the same "
        "sidecar write, so a chart can never carry one without the other"
    )


def test_nothing_ever_reads_the_description_back_from_a_sidecar():
    """T4.5 — asserted by absence, because the failure it prevents is not
    visible in behaviour until two copies have already diverged."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in list((root / "ui").rglob("*.py")) + list((root / "workflow").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if 'get("run_description"' in line or "['run_description']" in line:
                offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, (
        "the run description is being READ from a chart sidecar:\n  "
        + "\n  ".join(offenders)
        + "\nThe run's own meta.json is the only copy that decides."
    )


def test_the_chart_params_carry_it():
    from workflow.chart_creator import ChartParams

    assert ChartParams().run_description == ""


# ---- H7: the token ------------------------------------------------------
def test_the_token_is_offered_in_the_insert_menu():
    from ui.dialogs.layout_options_panel import SHEET_TOKENS

    names = [n for n, _ in SHEET_TOKENS]
    assert "rundescription" in names
    label = dict(SHEET_TOKENS)["rundescription"]
    assert "calibration" in label.lower(), (
        "the menu entry should say it covers the calibration's description "
        "too, or a user on a calibration chart will not know it applies"
    )


def test_the_engine_accepts_and_renders_the_token():
    """The engine's build takes explicit keywords and no ``**kwargs``, so a new
    placeholder that is not in its signature raises rather than being ignored.
    That is how this one was caught — by a chart build failing, not by the
    token silently rendering empty."""
    from workflow.layout_engine.chart import build_chart

    sig = inspect.signature(build_chart)
    assert "rundescription" in sig.parameters

    # THE TOKEN REALLY RESOLVES, which is what the source check below is for.
    # This used to be `assert '"rundescription": rundescription' in src`, a
    # match on the literal dict inside `build_chart`; the dict moved into
    # `chart.text_placeholder_context` so the panel could predict a line's
    # width from the same table the sheet prints from, and the check went red
    # on a wiring that was still correct. A test that names a line of code
    # rather than a behaviour breaks on every refactor and guards none of them.
    from workflow.layout_engine.chart import text_placeholder_context
    from workflow.layout_engine.raster import resolve_placeholders
    ctx = text_placeholder_context(rundescription="Baryta, gloss")
    assert resolve_placeholders("{rundescription}", ctx) == "Baryta, gloss"

    # …AND `build_chart` HANDS ITS OWN PARAMETER TO THAT TABLE. Read off the
    # syntax tree, because the name appearing in a comment is not a wiring.
    import ast
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(build_chart)))
    wired = [
        kw for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "text_placeholder_context"
        for kw in node.keywords
        if kw.arg == "rundescription" and isinstance(kw.value, ast.Name)
        and kw.value.id == "rundescription"
    ]
    assert wired, (
        "the parameter is accepted but never reaches the placeholder table, "
        "so {rundescription} would render as nothing"
    )


def test_the_token_is_passed_from_the_chart_params():
    from workflow import chart_creator

    src = inspect.getsource(chart_creator)
    assert 'kw["rundescription"] = params.run_description' in src
