"""Probe: what happens to a device-less measurement with NO chart beside it.

Before 1494986b `parse_ti3` refused such a file outright, so both profile-build
import doors refused it.  Now it parses.  This asks `assess` what it says.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TI3 = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
ORIGINATOR "Argyll target"
KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "OUTPUT"
COLOR_REP "XYZ"

NUMBER_OF_FIELDS 6
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC XYZ_X XYZ_Y XYZ_Z SAMPLE_NAME
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 80.0 85.0 90.0 "A1"
2 "A2" 40.0 42.0 45.0 "A2"
3 "A3" 10.0 11.0 12.0 "A3"
END_DATA
"""


def main() -> int:
    from workflow.measurement_import import assess
    from workflow.ti3_analysis import parse_ti3

    d = Path(tempfile.mkdtemp(prefix="adv2-deviceless-"))
    p = d / "loose.ti3"
    p.write_text(TI3, encoding="utf-8")

    data = parse_ti3(p)
    print("parse_ti3:      n_patches=%d has_device=%s len(rgb)=%d"
          % (data.n_patches, data.has_device, len(data.rgb)))

    v = assess(p, None)          # no .ti2 beside it
    print("assess(no chart): ok=%s device_from_chart=%s partial=%s reason=%r"
          % (v.ok, v.device_from_chart, v.partial, v.reason))
    if v.ok and not v.device_from_chart:
        print("VERDICT: a measurement with NO device values is ACCEPTED and "
              "will be filed with none, and nothing will ever supply them.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
