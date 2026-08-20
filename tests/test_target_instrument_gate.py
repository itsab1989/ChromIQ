"""What a chart's TARGET_INSTRUMENT does to the readers — proved, not assumed.

Adding a new instrument to ChromIQ means deciding what goes in the ``.ti2``'s
``TARGET_INSTRUMENT`` keyword, and that decision is constrained by code we do
not own. These tests pin the constraint by running the **real** binaries
(ChromIQ issue #159, where the CR30 study that turned this up lives; the
long-form notes stay on the ``feature/new-instrument-feasibility`` branch):

* an unrecognised instrument name is **fatal** — in our fork *and* in stock
  ArgyllCMS chartread (``chromiq_chartread.c:3628``, ``inst_enum`` in Argyll's
  ``spectro/insttypes.c``);
* a name Argyll knows gets past that check;
* **omitting the keyword is more permissive than an honest unknown name** —
  chartread then falls back to ``instI1Pro``. That asymmetry is the surprising
  part, and it is why "just write the new name" is not free.

So a new instrument must either use a name Argyll already knows, or our fork
must be taught that one name (Basti, 2026-08-20: teach it this one instrument
rather than downgrading the error to a warning — a warning would silently
accept *any* wrong instrument string, which is the #155 class of bug).

When the CR30 (or any new device) is implemented, the first test here is the
one that must change, deliberately.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER  # noqa: E402

STOCK = Path("/Applications/Argyll/bin/chartread")

pytestmark = pytest.mark.skipif(
    not HELPER.exists(), reason="chromiq-chartread helper not built")

#: A minimal .ti2 carrying the keywords ChromIQ's layout engine writes
#: (``workflow/layout_engine/ti2_writer.py``). It is deliberately incomplete —
#: STEPS_IN_PASS is missing — so a run that gets *past* the instrument check
#: still stops immediately, with a different and recognisable message.
_TI2 = """CTI2   

DESCRIPTOR "Argyll Calibration Target chart information 2"
ORIGINATOR "ChromIQ layout engine"
CREATED "Thu Aug 20 08:00:00 2026"
{instrument}APPROX_WHITE_POINT "96.422000 100.000000 82.521000"
COLOR_REP "RGB"
PAPER_SIZE "210.0x297.0"
CHART_ID "1"
NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 2
BEGIN_DATA
1 "A1" 100.00 100.00 100.00 96.42 100.00 82.52
2 "A2" 0.00 0.00 0.00 0.20 0.21 0.17
END_DATA
"""

#: The message both readers print when the keyword names something unknown.
UNRECOGNISED = "Unrecognised chart target instrument"
#: The message a chart that PASSES the instrument check stops on instead.
PAST_THE_GATE = "STEPS_IN_PASS"


def _chart(tmp_path: Path, instrument: str | None) -> Path:
    kw = "" if instrument is None else f'TARGET_INSTRUMENT "{instrument}"\n'
    base = tmp_path / "probe"
    base.with_suffix(".ti2").write_text(_TI2.format(instrument=kw))
    return base


def _run(binary: Path, base: Path) -> str:
    """First line of output. No instrument is connected, so every run stops
    early — which is the point: we are testing the file gate, not a read."""
    r = subprocess.run([str(binary), str(base)], capture_output=True,
                       text=True, timeout=60)
    return ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[0]


@pytest.mark.parametrize("name", ["Itohi CR30", "CR30", "Some Unknown Device"])
def test_an_unknown_instrument_name_is_fatal_for_our_fork(tmp_path, name):
    out = _run(HELPER, _chart(tmp_path, name))
    assert UNRECOGNISED in out, out
    assert name in out                      # it names the offender


def test_a_known_instrument_name_gets_past_the_gate(tmp_path):
    out = _run(HELPER, _chart(tmp_path, "GretagMacbeth i1 Pro"))
    assert UNRECOGNISED not in out
    assert PAST_THE_GATE in out, out        # stopped later, for another reason


def test_omitting_the_keyword_is_more_permissive_than_an_unknown_name(tmp_path):
    """The asymmetry: no keyword at all falls back to instI1Pro and proceeds,
    while an honest unknown name stops the read dead."""
    out = _run(HELPER, _chart(tmp_path, None))
    assert UNRECOGNISED not in out
    assert PAST_THE_GATE in out, out


@pytest.mark.skipif(not STOCK.exists(), reason="stock ArgyllCMS chartread not installed")
def test_stock_chartread_behaves_identically(tmp_path):
    """The constraint is Argyll's, not ours — so a new name cannot simply be
    invented, whatever our own fork is taught. ``chartread_engine: "argyll"``
    (core/settings.py) is a supported setting and the fallback when the helper
    is missing, so this path is reachable for real users."""
    assert UNRECOGNISED in _run(STOCK, _chart(tmp_path, "Itohi CR30"))
    assert PAST_THE_GATE in _run(STOCK, _chart(tmp_path, "GretagMacbeth i1 Pro"))
