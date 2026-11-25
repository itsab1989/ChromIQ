"""A chart Guided has just made, without building it: its record, and what the
tab keeps of it. Shared by the tests of the Guided to Manual switch."""
from __future__ import annotations

import json
from pathlib import Path


def made_in_guided(tab, folder: Path) -> Path:
    """Put the chart Guided would build now on *tab*'s screen; its .ti2."""
    from workflow.layout_engine.presets import (LayoutRecipe,
                                                guided_margin_fields)
    params = tab._collect_guided()
    recipe = LayoutRecipe.from_build_kwargs(
        tab._creator._engine_build_kwargs(params)).to_dict()
    recipe.update(guided_margin_fields(recipe))
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    ti2 = folder / "made.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    (folder / "made.channels.json").write_text(json.dumps({"layout": {
        "engine": "chromiq", "seed": 7, "recipe": recipe,
        "margins_chosen_by_user": False}}), encoding="utf-8")
    tab._shown_chart_ti2 = tab._guided_chart_ti2 = ti2
    tab._shown_chart_stamp = tab._guided_chart_stamp = tab._chart_stamp(ti2)
    tab._guided_chart_params, tab._guided_chart_taken = params, False
    tab._guided_transfer_pending = True
    return ti2
