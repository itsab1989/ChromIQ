"""The i1Pro 2's default quiet time is written ONCE (review S5, 4.3.52 fix round).

It was written in six places (settings DEFAULTS, the module, Preferences twice,
the Measure tab twice, MeasureParams, the helper's session line); they agreed,
and a plant of the settings default turned only 2 tests red. Now every Python
site reads core/i1pro2_lights_quiet.DEFAULT_S, the helper reads the driver's
own i1pro2_cq_lights_quiet_default_ms, and this test fails on a second literal.
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ["core/settings.py", "workflow/measure_manager.py", "ui/tabs/tab_measure.py",
         "ui/dialogs/settings_dialog.py", "workflow/measure_log.py",
         "workflow/measure_settings.py", "core/beta_registry.py"]


def _numbers(path: Path) -> "list[tuple[int, str]]":
    src = path.read_text(encoding="utf-8")
    return [(t.start[0], t.string) for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type == tokenize.NUMBER and t.string in ("2.1", "2100", "2100.0")]


def test_no_second_python_literal():
    for rel in SITES:
        assert _numbers(ROOT / rel) == [], rel
    own = _numbers(ROOT / "core" / "i1pro2_lights_quiet.py")
    assert [n for _l, n in own] == ["2.1"], own


def test_the_module_agrees_with_the_driver():
    from core import i1pro2_lights_quiet as lq
    c = (ROOT / "native" / "instlib" / "i1pro_imp.c").read_text(encoding="utf-8",
                                                                errors="surrogateescape")
    m = re.search(r"^#define CQ_LIGHTS_QUIET_MS\s+(\d+)\s*$", c, re.M)
    assert m and int(m.group(1)) == lq.DEFAULT_MS == round(lq.DEFAULT_S * 1000)
    assert "const int i1pro2_cq_lights_quiet_default_ms = CQ_LIGHTS_QUIET_MS;" in c


def test_the_simulators_copy_is_pinned():
    """tests/helpers/dual_sim_helper.py runs on its own (no imports from the
    app): its one copy must equal the module's."""
    from core import i1pro2_lights_quiet as lq
    sim = ROOT / "tests" / "helpers" / "dual_sim_helper.py"
    assert [n for _l, n in _numbers(sim)] == ["2100"]
    assert f"\nQUIET_DEFAULT_MS = {lq.DEFAULT_MS}\n" in sim.read_text(encoding="utf-8")


def test_every_site_reads_the_module():
    from core.settings import DEFAULTS
    from core import i1pro2_lights_quiet as lq
    from workflow.measure_manager import MeasureParams
    assert DEFAULTS["i1pro2_lights_quiet_s"] is lq.DEFAULT_S
    assert MeasureParams.__dataclass_fields__["engine_lights_quiet_s"].default is lq.DEFAULT_S
    assert lq.seconds(None) == lq.DEFAULT_S and lq.to_ms(None) == lq.DEFAULT_MS
