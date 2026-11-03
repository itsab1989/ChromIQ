"""SDK-free FD9 factory-native capture and M0/M1/M2 TI3 export."""

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow.fd9.independent import capture_layout, driver, chart_grid
from workflow.fd9.native_export import export_native

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--driver-source", type=Path)
p.add_argument("--session", type=Path, required=True)
p.add_argument("--layout", type=Path, required=True)
p.add_argument("--host", help="Explicit endpoint for a live capture")
p.add_argument(
    "--scan", action="store_true", help="Load, pre-scan and measure the retained sheet"
)
p.add_argument(
    "--allow-experimental",
    action="store_true",
    help="Opt in to the independent experimental driver",
)
p.add_argument(
    "--export-dir", type=Path, help="New folder for condition-labelled TI3 outputs"
)
a = p.parse_args()
if not a.allow_experimental:
    p.error("This workflow requires --allow-experimental")
driver(a.driver_source)
chart_grid(json.loads(a.layout.read_text(encoding="utf-8")))
if a.scan:
    if not a.host:
        p.error("Live acquisition requires --host")
    a.session = capture_layout(
        a.driver_source,
        a.layout,
        a.session,
        a.host,
        allow_experimental=True,
        native_factory=True,
    )
output = a.export_dir or a.session / ("export-" + uuid4().hex[:12])
output.mkdir(parents=True, exist_ok=False)
for mode in ("M0", "M1", "M2"):
    print(
        json.dumps(
            export_native(
                a.driver_source,
                a.session,
                a.layout,
                output / f"ChromIQ-{mode}-factory.ti3",
                mode,
            ),
            indent=2,
        ),
        flush=True,
    )
