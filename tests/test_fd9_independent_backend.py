"""Independent FD9 adapter validation, no hardware connections."""

import json, sys, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
from workflow.fd9.independent import chart_grid, export_saved


class IndependentFD9Tests(unittest.TestCase):
    def layout(self):
        return {
            "rows": [
                [{"centre_mm": [19 + 9 * c, 42 + 9 * r]} for c in range(12)]
                for r in range(25)
            ],
            "fiducials_mm": [[9.5, 32.5], [127.5, 32.5], [9.5, 267.5], [127.5, 267.5]],
        }

    def test_supported_geometry_and_invalid_grid(self):
        p = self.layout()
        g = chart_grid(p)
        self.assertEqual(g["mark_span_mm"], [118, 235])
        self.assertTrue(g["mirrored_image"])
        p["rows"][1][3]["centre_mm"][1] += 1
        with self.assertRaises(ValueError):
            chart_grid(p)
        p = self.layout()
        p["rows"][0].pop()
        with self.assertRaises(ValueError):
            chart_grid(p)

    def test_explicit_research_opt_in_before_files_or_imports(self):
        with self.assertRaises(ValueError):
            export_saved(
                "missing",
                "missing",
                "missing",
                "missing",
                "missing",
                "M1",
                "missing",
                "missing",
            )

    def test_real_capture_interoperability_if_available(self):
        root = Path(__file__).resolve().parents[3]
        source = root / "drivers/fd9-independent"
        session = root / "outputs/fd9-independent-live/canon-til-m2-validation-01"
        profile = (
            root / "outputs/fd9-manufacturer-oracle/chromiq-independent-profile.json"
        )
        layout = root / "outputs/canon-bond-special6-ink-limits/target/layout.json"
        if not profile.exists() or not session.exists():
            self.skipTest("Private development reference fixture is not distributed")
        from workflow.profile_engine.ti3_data import read_ti3
        import numpy as np

        cie = root / "outputs/fd9-independent-conversion/cie-reference"
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "M1.ti3"
            before = set(sys.modules)
            with (
                patch(
                    "ctypes.CDLL",
                    side_effect=AssertionError("Native library loading forbidden"),
                ),
                patch(
                    "subprocess.Popen",
                    side_effect=AssertionError("External tool invocation forbidden"),
                ),
            ):
                result = export_saved(
                    source,
                    session,
                    layout,
                    profile,
                    p,
                    "M1",
                    cie / "CIE_std_illum_D50.csv",
                    cie / "CIE_xyz_1931_2deg.csv",
                    allow_research=True,
                )
            self.assertFalse(
                any(n.startswith("openrip") for n in set(sys.modules) - before)
            )
            got = read_ti3(p)
            expected = [
                q
                for row in json.loads(layout.read_text(encoding="utf-8"))["rows"]
                for q in row
            ]
            self.assertEqual(
                (got.n_channels, len(got.xyz), got.spectral.shape), (11, 300, (300, 36))
            )
            np.testing.assert_allclose(
                got.device,
                np.array([q["device_values"] for q in expected]) / 100,
                atol=1e-11,
            )
            self.assertEqual(got.keywords["CALIBRATED_REFLECTANCE"], "NO")
            self.assertFalse(result["SDK_runtime_dependency"])
