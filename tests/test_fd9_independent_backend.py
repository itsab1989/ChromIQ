"""Independent FD9 adapter validation, no hardware connections."""

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
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

    def test_invented_eleven_channel_export_needs_no_private_files_or_sdk(self):
        from tests.test_fd9_partial import setup as fixture, capture
        from workflow.fd9.measurement import prepare_chart
        from workflow.profile_engine.ti3_data import read_ti3
        import numpy as np

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            s = fixture.__wrapped__(root)
            tokens = list(("C", "M", "Y", "K", "c", "m", "k", "1k", "R", "G", "B"))
            s.layout.update(color_rep="CMYKcmk1kRGB", channel_tokens=tokens)
            s.layout["rows"] = [[dict(id=r*12+c+1,
                centre_mm=[19+9*c,42+9*r], device_values=[r*4,c*5,0,0]+[0]*7)
                for c in range(12)] for r in range(25)]
            definition = root / "invented-layout.json"
            definition.write_text(json.dumps(s.layout), encoding="utf-8")
            chart = prepare_chart(definition, root/"invented-chart")
            session = capture(s, root/"invented-session", list(range(25)), 25, complete=True)
            out = root/"M1.ti3"
            before = set(sys.modules)
            with (patch("ctypes.CDLL", side_effect=AssertionError("Native library loading forbidden")),
                  patch("subprocess.Popen", side_effect=AssertionError("External tool invocation forbidden"))):
                result = export_saved(s.settings.driver_source, session,
                    chart.with_suffix(".fd9.json"), s.settings.profile, out, "M1",
                    s.settings.illuminant, s.settings.observer, allow_research=True)
            self.assertFalse(any(n.startswith("openrip") for n in set(sys.modules)-before))
            got = read_ti3(out)
            expected = [p for row in s.layout["rows"] for p in row]
            self.assertEqual((got.n_channels,len(got.xyz),got.spectral.shape), (11,300,(300,36)))
            np.testing.assert_allclose(got.device,
                np.array([p["device_values"] for p in expected])/100, atol=1e-11)
            self.assertEqual(got.keywords["CALIBRATED_REFLECTANCE"],"NO")
            self.assertFalse(result["SDK_runtime_dependency"])
